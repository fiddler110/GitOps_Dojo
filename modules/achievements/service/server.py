#!/usr/bin/env python3
"""achievements: the class score service (stdlib only, runs on the allocator image).

Student routes (gateway identity gate, mounted at /achievements, prefix stripped):
  GET  /                  the leaderboard page
  GET  /widget            the landing-page widget (score, completion, recent, Moments)
  GET  /api/me            the caller's score, rank, completion, recent unlocks, Moments
  GET  /api/board         the whole class (anonymous names when ACHIEVEMENTS_ANONYMOUS=1)
  GET  /api/toasts?surface=NAME   toasts to show now (each shown once; surface=terminal keeps them)
  POST /api/event         a signed event {user, event, ts, nonce, sig}
  POST /api/hint, /api/reveal   {challenge};  POST /api/check {challenge} runs its verifiers
  POST /api/challenge     {challenge, action: start|reset}: build (or re-build) the student's
                          own challenge space from the seed plan (dojo-challenge, a lab button)
  POST /api/shell         one command line from the prompt hook {cmd, exit, branch, ...}:
                          terminal only (Forgejo token plus client hash); matched, never kept
  POST /api/forgejo       the Forgejo system webhook, HMAC-signed with the shared secret
  POST /api/adapter       a module's event (dns-gate, cloud-api, openbao-audit), HMAC-signed with ACHIEVEMENTS_ADAPTER_SECRET
  The student's terminal (`dojo-check`) calls the same routes directly with its own Forgejo
  token (Authorization: token ...), which Forgejo confirms, and the X-Dojo-Client hash.
Facilitator (route /achievements-admin, facilitator gate, prefix kept):
  GET  /achievements-admin/, /api/state;  POST /api/award, /api/reset, /api/reload
GET /healthz.

Trust: X-Auth-User counts only with X-Gateway-Token. workshop_lab reaches this port directly,
so a request without the token is anonymous: it may post a signed event (an adapter or
checker) and nothing else. A forged event is charged only to an identified caller.
"""
import glob
import hmac
import http.server
import json
import mimetypes
import os
import re
import signal
import sys
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
# dojo_http: modules/_shared/ in the source tree, ./_shared/ once ./run.sh has copied it (SHARED= in module.env).
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
import catalog as cat  # noqa: E402
import dojo_http  # noqa: E402
import challenges  # noqa: E402
import identity  # noqa: E402
import ledger as lg  # noqa: E402
import matcher  # noqa: E402
import webhook  # noqa: E402
from store import Denied, Store  # noqa: E402

GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")
FACILITATOR = os.environ.get("FACILITATOR_USERNAME", "root")
# The engine's student reset calls /_dojo/reset/... with this (render_extensions.py derives it per service).
RESET_TOKEN = os.environ.get("RESET_TOKEN", "")
ADMIN_PREFIX = "/achievements-admin"
MAX_BODY = 8192
SAVE_DELAY = 1.0     # seconds: the state is written at most this often (RV2); every widget polls
MAX_WEBHOOK_BODY = 1 << 20      # a push with many commits is large
STATIC_DIR = os.path.join(HERE, "static")
PAGES = {"/": "board.html", "/widget": "widget.html", "/certificate": "certificate.html"}
ASSETS = ("board.js", "widget.js", "toast.js", "style.css", "admin.js", "certificate.js", "badge.js")
ADMIN_PAGES = {"/": "admin.html"}
ADMIN_ASSETS = ("admin.js", "style.css")

CLIENT_FILE = os.environ.get("CLIENT_FILE", os.path.join(HERE, "..", "terminal", "dojo-check.py"))
FORGEJO_URL = os.environ.get("FORGEJO_URL", "http://git-server:3000")
# What a student's terminal clones from (the same Forgejo, by the name the terminal uses).
PUBLIC_FORGEJO = os.environ.get("FORGEJO_CLONE_BASE", "http://git-server:3000").rstrip("/")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://achievements:8080/api/forgejo")
WEBHOOK_SECRET = webhook.secret_from(GATEWAY_TOKEN)
# Modules' adapters (dns-gate, cloud-api, openbao-audit; adapter_client.py) post signed events with this; unset means /api/adapter is off.
ADAPTER_SECRET = os.environ.get("ACHIEVEMENTS_ADAPTER_SECRET") or None
# Sensei's stuck radar and `sensei check` read activity and progress with this key (Sensei's own gateway token,
# which the compose file passes to both); unset means those two reads are off.
SENSEI_KEY = os.environ.get("SENSEI_KEY") or None

# Verifier and seed-builder plug-ins (A22): this module's own (Forgejo/git), every plugins/<name>/ folder
# (a backend's verbs, e.g. plugins/dns), plus any listed
# in ACHIEVEMENTS_PLUGIN_DIRS (colon-separated folders holding a verifiers.json).
PLUGIN_DIRS = [os.path.join(HERE, "..", "achievements")] + \
    sorted(glob.glob(os.path.join(HERE, "..", "plugins", "*"))) + \
    [d for d in os.environ.get("ACHIEVEMENTS_PLUGIN_DIRS", "").split(":") if d]

store = None
resolver = None
runner = None       # challenges.Runner, or None when there is no Forgejo admin login
CLIENT_HASH = ""


def log(msg):
    print(f"[achievements] {msg}", flush=True)


def load_catalog():
    workshop = os.environ.get("WORKSHOP_DIR", "/opt/workshop")
    shared = os.path.join(HERE, "..", "catalog", "shared.json")
    catalog, warnings = cat.load(workshop, shared, check_name=False)
    for w in warnings[:5]:
        log(f"catalog warning: {w}")
    return catalog


def client_hash():
    """sha256 of the dojo-check client baked into the terminal image (the same file)."""
    import hashlib
    try:
        with open(CLIENT_FILE, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return ""


def make_store():
    env = os.environ
    catalog = load_catalog()
    store = Store(catalog, lg.Config.from_env(env), env.get("DATA_DIR", "/data"),
                 secret=GATEWAY_TOKEN or os.urandom(16).hex(),
                 anonymous=env.get("ACHIEVEMENTS_ANONYMOUS", "1") not in ("0", "false", "no", ""),
                 facilitator=FACILITATOR, ignore=(env.get("FORGEJO_ADMIN_USER"),), save_delay=SAVE_DELAY)
    store.signature = env.get("ACHIEVEMENTS_SIGNATURE", "")[:80]
    store.class_date = env.get("ACHIEVEMENTS_CLASS_DATE", "")[:40]
    return store


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "achievements"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype):
        dojo_http.send(self, code, body, ctype)

    def _json(self, code, doc):
        dojo_http.send_json(self, code, doc)

    def _static(self, name):
        try:
            with open(os.path.join(STATIC_DIR, name), "rb") as f:
                body = f.read()
        except OSError:
            return self._json(404, {"error": "not found"})
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        self._send(200, body, ctype)

    def _gateway_user(self):
        """The user the gateway identified, or None when its token is missing or wrong."""
        return dojo_http.gateway_user(self.headers, GATEWAY_TOKEN)

    def _caller(self, mutating=False):
        """The identified user, or None. Two ways in: the gateway's headers (the browser), or
        the student's own Forgejo token (the terminal, `dojo-check`), which Forgejo vouches for.

        A token caller must use the client we shipped: a wrong hash costs -1 and refuses the
        request, and so does no hash on a request that changes something. Identity headers
        without the gateway token, next to a token, are someone else's name worn like a hat."""
        user = self._gateway_user()
        if user:
            return user
        user = resolver.resolve(self.headers.get("Authorization")) if resolver else None
        if not user:
            return None
        if self.headers.get("X-Auth-User") and self.headers.get("X-Auth-User") != user:
            store.spoof(user)
        sent = self.headers.get("X-Dojo-Client")
        if (sent is not None or mutating) and (not CLIENT_HASH or sent != CLIENT_HASH):
            store.tamper(user)
            raise Denied(403, "unrecognised client")
        return user

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 <= n <= MAX_BODY:
            raise Denied(413, "body too large")
        try:
            doc = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            raise Denied(400, "not JSON")
        if not isinstance(doc, dict):
            raise Denied(400, "expected an object")
        return doc

    def _webhook(self):
        """A Forgejo delivery: signature first, then normalise and match."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 <= n <= MAX_WEBHOOK_BODY:
            raise Denied(413, "body too large")
        raw = self.rfile.read(n)
        if not webhook.verify(WEBHOOK_SECRET, raw, self.headers):
            log("forgejo webhook: bad signature, refused")
            raise Denied(403, "bad signature")
        try:
            payload = json.loads(raw or b"{}")
        except ValueError:
            raise Denied(400, "not JSON")
        event = matcher.forgejo_event(webhook.event_kind(self.headers), payload)
        return self._json(200, store.forgejo(event) if event else {"ignored": True})

    def _adapter(self):
        """A module's signed event (dns-gate): the raw body is HMAC-signed, like the Forgejo webhook."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 <= n <= MAX_BODY:
            raise Denied(413, "body too large")
        raw = self.rfile.read(n)
        sent = (self.headers.get("X-Adapter-Signature") or "").strip().lower()
        if not ADAPTER_SECRET or not hmac.compare_digest(webhook.signature(ADAPTER_SECRET, raw).encode(), sent.encode()):
            log("adapter event: bad signature, refused")
            raise Denied(403, "bad signature")
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            raise Denied(400, "not JSON")
        src = body.get("source") if isinstance(body, dict) else None
        event = matcher.dns_event(body) if src == "dns" else matcher.adapter_event(body) if src else None
        return self._json(200, store.adapter(event) if event else {"ignored": True})

    def _run(self, fn):
        try:
            fn()
        except Denied as d:
            self._json(d.code, {"error": d.message})
        except Exception as exc:    # never leak a traceback to a student
            log(f"error on {self.command} {self.path}: {exc!r}")
            self._json(500, {"error": "server error"})

    def do_GET(self):
        self._run(self._get)

    def do_POST(self):
        self._run(self._post)

    def _get(self):
        url = urllib.parse.urlsplit(self.path)
        path, query = url.path, urllib.parse.parse_qs(url.query)
        if path == "/healthz":
            return self._json(200, {"ok": True})
        if path == ADMIN_PREFIX or path.startswith(ADMIN_PREFIX + "/"):
            return self._admin_get(path[len(ADMIN_PREFIX):] or "/")
        if path in PAGES:
            return self._static(PAGES[path])
        if path.lstrip("/") in ASSETS:
            return self._static(path.lstrip("/"))
        if path in ("/api/sensei/activity", "/api/sensei/progress"):
            given = self.headers.get("X-Sensei-Key") or ""
            if not SENSEI_KEY or not hmac.compare_digest(given.encode(), SENSEI_KEY.encode()):
                raise Denied(403, "sensei only")
            if path == "/api/sensei/activity":
                return self._json(200, {"students": store.activity_snapshot()})
            user = (query.get("user") or [""])[0][:100]
            if not user or user == FACILITATOR:
                raise Denied(400, "no such student")
            return self._json(200, store.progress(user))
        caller = self._caller()
        if path == "/api/me":
            return self._json(200, store.me(self._need(caller)))
        if path == "/api/certificate":
            return self._json(200, store.certificate(self._need(caller)))
        if path == "/api/board":
            return self._json(200, {"rows": store.board(self._need(caller))})
        if path == "/api/toasts":
            surface = (query.get("surface") or ["page"])[0][:20]
            try:
                after = int((query.get("after") or ["0"])[0])
            except ValueError:
                after = 0
            return self._json(200, {"toasts": store.toasts(self._need(caller), surface, after)})
        self._json(404, {"error": "not found"})

    @staticmethod
    def _need(caller):
        if not caller:
            raise Denied(403, "sign in through the lab first")
        return caller

    def _post(self):
        path = urllib.parse.urlsplit(self.path).path
        if path.startswith(ADMIN_PREFIX + "/"):
            return self._admin_post(path[len(ADMIN_PREFIX):])
        if path == "/api/forgejo":
            return self._webhook()
        if path == "/api/adapter":
            return self._adapter()
        if path.startswith("/_dojo/reset/"):
            return self._student_reset(path)
        if path == "/api/shell":
            # The terminal only: its Forgejo token, and the shipped client (a wrong one is -1).
            user = self._caller(mutating=True) if not self._gateway_user() else None
            if not user:
                raise Denied(403, "shell events come from the lab terminal")
            return self._json(200, store.shell(user, self._body()))
        caller = self._caller(mutating=path in ("/api/hint", "/api/reveal", "/api/check", "/api/challenge"))
        body = self._body()
        if path == "/api/event":
            return self._json(200, store.event(caller, body))
        if path in ("/api/hint", "/api/reveal"):
            cid = body.get("challenge")
            if not isinstance(cid, str):
                raise Denied(400, "challenge is required")
            user = self._need(caller)
            doc = store.hint(user, cid) if path == "/api/hint" else store.reveal(user, cid)
            key = "text" if path == "/api/hint" else "answer"
            if runner and doc.get(key):
                doc[key] = self._render(user, cid, doc[key])
            return self._json(200, doc)
        if path in ("/api/check", "/api/challenge"):
            user = self._need(caller)
            cid = body.get("challenge")
            if not isinstance(cid, str):
                raise Denied(400, "challenge is required")
            store.probe(user, body)
            if runner is None:
                raise Denied(501, "challenge checking needs the service's Forgejo login, which isn't set")
            try:
                if path == "/api/check":
                    return self._json(200, store.check(user, cid, runner, runner.errors()))
                doc = store.challenge_space(user, cid, body.get("action"), runner, runner.errors())
            except challenges.NotCheckable as exc:
                raise Denied(501, str(exc))
            ch = store.ledger.index[cid]["item"]
            doc.update(title=ch["title"], goal=runner.render(ch, user, ch.get("goal")),
                       constraints=runner.render(ch, user, ch.get("constraints")),
                       clone_url=f"{PUBLIC_FORGEJO}/{doc['repo']}.git" if doc["repo"] else None)
            return self._json(200, doc)
        self._json(404, {"error": "not found"})

    @staticmethod
    def _render(user, cid, text):
        entry = store.ledger.index.get(cid)
        try:
            return runner.render(entry["item"], user, text) if entry else text
        except challenges.NotCheckable:
            return text

    # -- student reset (engine `resets` hooks) -------------------------------------------
    def _student_reset(self, path):
        given = self.headers.get("X-Dojo-Reset-Token") or ""
        if not RESET_TOKEN or not hmac.compare_digest(given.encode(), RESET_TOKEN.encode()):
            raise Denied(403, "reset token required")
        parts = path.split("/")      # ["", "_dojo", "reset", what, user]
        phase = (urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("phase") or [""])[0]
        if len(parts) != 5 or parts[3] not in ("progress", "score") or phase not in ("teardown", "provision"):
            raise Denied(404, "not found")
        user = urllib.parse.unquote(parts[4])
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", user) or user == FACILITATOR:
            raise Denied(400, "no such student")
        if phase == "provision":
            return self._json(200, {"ok": True, "detail": "nothing to set up"})
        self._json(200, {"ok": True, "detail": store.student_reset(user, scores=parts[3] == "score")})

    # -- facilitator -------------------------------------------------------------------
    def _facilitator(self):
        if self._gateway_user() != FACILITATOR:
            raise Denied(403, "facilitator only")

    def _admin_get(self, path):
        self._facilitator()
        if path in ADMIN_PAGES:
            return self._static(ADMIN_PAGES[path])
        if path.lstrip("/") in ADMIN_ASSETS:
            return self._static(path.lstrip("/"))
        if path == "/api/state":
            return self._json(200, store.admin_state())
        self._json(404, {"error": "not found"})

    def _admin_post(self, path):
        self._facilitator()
        if self.headers.get("X-Requested-With") != "dojo-admin":
            raise Denied(403, "missing header")
        body = self._body()
        if path == "/api/award":
            store.admin_award(body.get("user"), body.get("points"), body.get("reason", ""))
        elif path == "/api/complete":
            store.admin_complete(body.get("user"), body.get("on", True))
        elif path == "/api/reset":
            store.admin_reset(body.get("user"))
        elif path == "/api/reload":
            try:
                store.reload(load_catalog())
            except cat.CatalogError as e:
                raise Denied(400, "; ".join(e.problems[:5]))
        else:
            raise Denied(404, "not found")
        self._json(200, {"ok": True})


def make_runner(admin, password):
    """The challenge runner, or None without a Forgejo admin login (checks then answer 501)."""
    plugins = challenges.load_plugins(PLUGIN_DIRS)
    for p in plugins["problems"]:
        log(f"verifier plug-in problem: {p}")
    if not (admin and password):
        log("challenges: no Forgejo admin login; dojo-check ID and dojo-challenge are off")
        return None
    seeds = os.path.join(os.environ.get("WORKSHOP_DIR", "/opt/workshop"), "achievements", "seeds")
    r = challenges.Runner(plugins, seeds, challenges.forgejo_http(FORGEJO_URL, admin, password), time.time)
    for cid, verb in r.unknown_verbs(store.catalog):
        log(f"challenge {cid}: verifier verb '{verb}' isn't provided by any plug-in; it can't be checked")
    log(f"challenges: {len(plugins['verbs'])} verifier verbs, {len(plugins['builders'])} seed builders "
        f"({', '.join(plugins['backends']) or 'none'})")
    return r


def state_loop():
    """Every few seconds, give each student's `verify` milestones and watched challenges a turn (Store.sweep_state)."""
    gap = int(os.environ.get("ACHIEVEMENTS_STATE_SECONDS", "20") or 20)
    while True:
        time.sleep(min(5, gap))
        if runner is None:
            continue
        try:
            store.sweep_state(runner, runner.errors(), gap=gap)
        except Exception as exc:    # noqa: BLE001 - a bad check must not stop the loop
            log(f"state sweep: {exc!r}")


def main():
    global store, resolver, runner, CLIENT_HASH
    store = make_store()
    resolver = identity.Resolver(identity.forgejo_fetch(FORGEJO_URL))
    CLIENT_HASH = client_hash()
    admin, password = os.environ.get("FORGEJO_ADMIN_USER"), os.environ.get("FORGEJO_ADMIN_PASSWORD")
    runner = make_runner(admin, password)
    if WEBHOOK_SECRET and admin and password:
        webhook.register_in_background(webhook.forgejo_api(FORGEJO_URL, admin, password),
                                       webhook.forgejo_web_create(FORGEJO_URL, admin, password),
                                       WEBHOOK_URL, WEBHOOK_SECRET, log)
    else:
        log("forgejo webhook: no gateway token or Forgejo admin login; Forgejo events will not score")
    threading.Thread(target=state_loop, daemon=True).start()
    port = int(os.environ.get("PORT", "8080"))
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    log(f"serving {store.catalog['title']} on :{port}")
    try:
        srv.serve_forever()
    finally:
        store.flush()   # SIGTERM (podman stop) or a crash: write what the writer hasn't yet


if __name__ == "__main__":
    main()
