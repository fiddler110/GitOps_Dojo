#!/usr/bin/env python3
"""achievements: the class score service (stdlib only, runs on the allocator image).

Student routes (gateway identity gate, mounted at /achievements, prefix stripped):
  GET  /                  the leaderboard page
  GET  /widget            the landing-page widget (score, completion, recent, Moments)
  GET  /api/me            the caller's score, rank, completion, recent unlocks, Moments
  GET  /api/board         the whole class (anonymous names when ACHIEVEMENTS_ANONYMOUS=1)
  GET  /api/toasts?surface=NAME   toasts to show now (each shown once; surface=terminal keeps them)
  POST /api/event         a signed event {user, event, ts, nonce, sig}
  POST /api/hint, /api/reveal   {challenge};  POST /api/check {challenge} (not built yet: 501)
  POST /api/shell         one command line from the prompt hook {cmd, exit, branch, ...}:
                          terminal only (Forgejo token plus client hash); matched, never kept
  POST /api/forgejo       the Forgejo system webhook, HMAC-signed with the shared secret
  The student's terminal (`dojo-check`) calls the same routes directly with its own Forgejo
  token (Authorization: token ...), which Forgejo confirms, and the X-Dojo-Client hash.
Facilitator (route /achievements-admin, facilitator gate, prefix kept):
  GET  /achievements-admin/, /api/state;  POST /api/award, /api/reset, /api/reload
GET /healthz.

Trust: X-Auth-User counts only with X-Gateway-Token. workshop_lab reaches this port directly,
so a request without the token is anonymous: it may post a signed event (an adapter or
checker) and nothing else. A forged event is charged only to an identified caller.
"""
import hmac
import http.server
import json
import mimetypes
import os
import signal
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog as cat  # noqa: E402
import identity  # noqa: E402
import ledger as lg  # noqa: E402
import matcher  # noqa: E402
import webhook  # noqa: E402
from store import Denied, Store  # noqa: E402

GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")
FACILITATOR = os.environ.get("FACILITATOR_USERNAME", "root")
ADMIN_PREFIX = "/achievements-admin"
MAX_BODY = 8192
MAX_WEBHOOK_BODY = 1 << 20      # a push with many commits is large
STATIC_DIR = os.path.join(HERE, "static")
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                               "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'",
    "X-Frame-Options": "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
PAGES = {"/": "board.html", "/widget": "widget.html"}
ASSETS = ("board.js", "widget.js", "toast.js", "style.css", "admin.js")
ADMIN_PAGES = {"/": "admin.html"}
ADMIN_ASSETS = ("admin.js", "style.css")

CLIENT_FILE = os.environ.get("CLIENT_FILE", os.path.join(HERE, "..", "terminal", "dojo-check.py"))
FORGEJO_URL = os.environ.get("FORGEJO_URL", "http://git-server:3000")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://achievements:8080/api/forgejo")
WEBHOOK_SECRET = webhook.secret_from(GATEWAY_TOKEN)

store = None
resolver = None
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
    return Store(catalog, lg.Config.from_env(env), env.get("DATA_DIR", "/data"),
                 secret=GATEWAY_TOKEN or os.urandom(16).hex(),
                 anonymous=env.get("ACHIEVEMENTS_ANONYMOUS", "1") not in ("0", "false", "no", ""),
                 facilitator=FACILITATOR, ignore=(env.get("FORGEJO_ADMIN_USER"),))


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "achievements"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, doc):
        self._send(code, json.dumps(doc).encode(), "application/json")

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
        given = self.headers.get("X-Gateway-Token") or ""
        if not GATEWAY_TOKEN or not hmac.compare_digest(given.encode(), GATEWAY_TOKEN.encode()):
            return None
        return self.headers.get("X-Auth-User") or None

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
        caller = self._caller()
        if path == "/api/me":
            return self._json(200, store.me(self._need(caller)))
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
        if path == "/api/shell":
            # The terminal only: its Forgejo token, and the shipped client (a wrong one is -1).
            user = self._caller(mutating=True) if not self._gateway_user() else None
            if not user:
                raise Denied(403, "shell events come from the lab terminal")
            return self._json(200, store.shell(user, self._body()))
        caller = self._caller(mutating=path in ("/api/hint", "/api/reveal", "/api/check"))
        body = self._body()
        if path == "/api/event":
            return self._json(200, store.event(caller, body))
        if path in ("/api/hint", "/api/reveal"):
            cid = body.get("challenge")
            if not isinstance(cid, str):
                raise Denied(400, "challenge is required")
            user = self._need(caller)
            return self._json(200, store.hint(user, cid) if path == "/api/hint" else store.reveal(user, cid))
        if path == "/api/check":
            self._need(caller)
            raise Denied(501, "checking arrives with the challenge verifiers")
        self._json(404, {"error": "not found"})

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


def main():
    global store, resolver, CLIENT_HASH
    store = make_store()
    resolver = identity.Resolver(identity.forgejo_fetch(FORGEJO_URL))
    CLIENT_HASH = client_hash()
    admin, password = os.environ.get("FORGEJO_ADMIN_USER"), os.environ.get("FORGEJO_ADMIN_PASSWORD")
    if WEBHOOK_SECRET and admin and password:
        webhook.register_in_background(webhook.forgejo_api(FORGEJO_URL, admin, password),
                                       WEBHOOK_URL, WEBHOOK_SECRET, log)
    else:
        log("forgejo webhook: no gateway token or Forgejo admin login; Forgejo events will not score")
    port = int(os.environ.get("PORT", "8080"))
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    log(f"serving {store.catalog['title']} on :{port}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
