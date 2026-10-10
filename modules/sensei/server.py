"""Sensei's admin service: a background loop (bot.py) and a facilitator-only page.

  GET  /healthz        liveness
  GET  /               the page (facilitator, through the gateway)
  GET  /api/prs        every pull request Sensei has seen: status, reason, minutes stuck
  POST /api/merge      {number}: merge anyway (skips the review; still resolves the roster conflict)
  POST /api/comment    {number, text}
  GET  /api/radar      who looks stuck (needs the achievements service)
  POST /api/student/{ask,why,hand,inbox,notify,check,status,review,approve}  the `sensei` command (Forgejo token auth, lab network only)
  POST /api/scan       look now
  POST /api/enabled    {on}: pause or resume the bot
Identity headers count only with X-Gateway-Token (the route is facilitator-gated at Caddy).
"""
import http.server
import json
import os
import signal
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "achievements", "service"))
# dojo_http: modules/_shared/ in the source tree, ./_shared/ once ./dojo has copied it (SHARED= in module.env).
sys.path[:0] = [os.path.join(HERE, "..", "_shared"), os.path.join(HERE, "_shared")]
import dojo_http  # noqa: E402
import bot  # noqa: E402
import support  # noqa: E402
import seed  # noqa: E402
import challenges  # noqa: E402  (the achievements service's Forgejo client)
import identity  # noqa: E402  (the same one: a Forgejo token -> the student's login)

GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")
FACILITATOR = os.environ.get("FACILITATOR_USERNAME", "root")
FORGEJO_URL = os.environ.get("FORGEJO_URL", "http://git-server:3000")
INTERVAL = int(os.environ.get("SENSEI_INTERVAL", "5"))
STATIC = os.path.join(HERE, "static")
PAGES = {"/": "admin.html", "/admin.js": "admin.js", "/style.css": "style.css"}
sensei = None
resolver = None
index = patterns = answers = desk = None  # support.LabIndex, .Patterns, .Answers, .HelpDesk
achievements = None             # support.Achievements
STUCK_MINUTES = int(os.environ.get("SENSEI_STUCK_MINUTES", "10") or 10)
# RV7: no lock spans the whole service. A student's status/review/approve waits only on their own earlier call;
# the bot's pass (the loop or /api/scan) has its own lock; the bot guards its PR table and each PR itself.
tick_lock = threading.Lock()
_user_locks, _user_locks_guard = {}, threading.Lock()


def user_lock(user):
    with _user_locks_guard:
        return _user_locks.setdefault(user, threading.Lock())


def log(msg):
    print(f"[sensei] {msg}", flush=True)


def ask(q):
    """`sensei ask`: the lab sections that best answer q. Nothing found is an honest "no", not a guess."""
    ready = answers.find(q) if answers else None
    found = index.search(q) if index else []
    if ready:  # a ready-made answer leads; the labs follow as pointers
        return {"answer": ready, "found": found, "message": ""}
    return {"found": found, "message": "" if found else
            "I couldn't find that in this workshop's labs. Try other words, or `sensei hand \"...\"` to ask the facilitator."}


def why(text):
    """`sensei why`: the known error nearest the bottom of the terminal output, if any."""
    m = patterns.match(text) if (patterns and text.strip()) else None
    return {"match": m, "message": "" if m else
            "I don't recognise an error in that output. `sensei ask \"...\"` searches the labs, and `sensei hand \"...\"` asks the facilitator."}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "sensei"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        dojo_http.send(self, code, body, ctype)

    def _json(self, code, doc):
        dojo_http.send_json(self, code, doc)

    def _facilitator(self):
        return dojo_http.is_facilitator(self.headers, GATEWAY_TOKEN, FACILITATOR)

    def _student(self, action, body):
        """The `sensei` command in a student's terminal. Identity is the student's own Forgejo token, which
        Forgejo confirms; this port is only reachable from the lab network, never through the gateway."""
        user = resolver.resolve(self.headers.get("Authorization")) if resolver else None
        if not user:
            return self._json(401, {"error": "no valid Forgejo token"})
        if action == "ask":
            return self._json(200, ask(str(body.get("q", ""))[:300]))
        if action == "why":
            return self._json(200, why(str(body.get("text", ""))[-6000:]))
        if action == "hand":
            text, context = str(body.get("text", "")), str(body.get("context", ""))[-6000:]
            auto = why(context) if context else {}
            auto_ask = ask(text) if text else {}
            req, problem = desk.raise_hand(user, text, context, {"why": auto.get("match"), "ask": auto_ask.get("found", [])[:1]})
            if not req:
                return self._json(200, {"ok": False, "message": problem})
            return self._json(200, {"ok": True, "id": req["id"], "why": auto.get("match"), "ask": auto_ask.get("found", [])[:2]})
        if action == "reply":
            rid = body.get("id")
            ok = isinstance(rid, int) and desk.reply(rid, str(body.get("text", "")), who=user)
            return self._json(200, {"ok": ok, "message": "" if ok else "I couldn't find an open request of yours with that number (`sensei inbox`)."})
        if action == "inbox":
            return self._json(200, {"requests": desk.inbox(user)})
        if action == "notify":
            surface = str(body.get("surface", "terminal"))
            wait = body.get("wait", 0)
            wait = min(float(wait), 25.0) if isinstance(wait, (int, float)) else 0.0
            return self._json(200, {"replies": desk.notify(user, surface, wait)})
        if action == "check":
            prog = achievements.progress(user) if achievements else None
            if not prog:
                return self._json(200, {"message": "I can't see your progress here: this workshop has no scoreboard "
                                                   "(or it isn't answering). The labs' checkpoints are your guide."})
            return self._json(200, support.current_lab(prog))
        with user_lock(user):
            if action == "status":
                return self._json(200, sensei.student_status(user))
            if action == "review":
                return self._json(200, sensei.student_review(user))
            if action == "approve":
                return self._json(200, sensei.student_approve(user, bool(body.get("force"))))
        self._json(404, {"error": "not found"})

    def do_GET(self):
        if self.path == "/healthz":
            return self._json(200, {"ok": True})
        if self.path == "/api/student/status":
            return self._student("status", {})
        if not self._facilitator():
            return self._json(403, {"error": "facilitator only"})
        if self.path in PAGES:
            name = PAGES[self.path]
            with open(os.path.join(STATIC, name), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8" if name.endswith("html")
                                  else "text/javascript" if name.endswith(".js") else "text/css")
        if self.path == "/api/help":
            return self._json(200, {"requests": desk.snapshot(), "open": desk.open_count()})
        if self.path == "/api/radar":
            students = achievements.activity() if achievements else None
            helping = {r["user"] for r in desk.snapshot() if r["status"] == "open"}
            return self._json(200, {"available": students is not None, "minutes": STUCK_MINUTES,
                                    "students": support.stuck(students or {}, helping, STUCK_MINUTES)})
        if self.path == "/api/prs":
            return self._json(200, {"prs": sensei.snapshot(), "enabled": sensei.enabled, "repo": sensei.repo,
                                    "watching": WATCHING, "mode": sensei.mode,
                                    "attention": sensei.attention(), "help_open": desk.open_count()})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.startswith("/api/student/"):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(min(n, 16384)) or b"{}")
            except ValueError:
                return self._json(400, {"error": "bad json"})
            return self._student(self.path.rsplit("/", 1)[1], body)
        if not self._facilitator() or self.headers.get("X-Requested-With") != "dojo-admin":
            return self._json(403, {"error": "facilitator only"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 8192)) or b"{}")
        except ValueError:
            return self._json(400, {"error": "bad json"})
        number = body.get("number")
        if self.path == "/api/scan":
            if WATCHING and tick_lock.acquire(blocking=False):  # a pass already running is as good as a new one
                try:
                    sensei.tick()
                finally:
                    tick_lock.release()
        elif self.path == "/api/enabled":
            sensei.enabled = bool(body.get("on"))
        elif self.path == "/api/merge" and isinstance(number, int):
            return self._json(200, {"result": sensei.handle(number, force=True)})
        elif self.path == "/api/help/reply" and isinstance(body.get("id"), int):
            return self._json(200, {"ok": desk.reply(body["id"], str(body.get("text", "")))})
        elif self.path == "/api/help/close" and isinstance(body.get("id"), int):
            return self._json(200, {"ok": desk.close(body["id"])})
        elif self.path == "/api/comment" and isinstance(number, int) and str(body.get("text", "")).strip():
            return self._json(200, {"ok": sensei.comment(number, str(body["text"])[:2000])})
        else:
            return self._json(404, {"error": "not found"})
        self._json(200, {"ok": True})


seeder = None
WATCHING = False  # a workshop sets SENSEI_REPO to have Sensei review its roster pull requests


def loop():
    while True:
        try:
            with tick_lock:
                if WATCHING:
                    sensei.tick()
                if seeder and sensei.enabled and seeder.seed():
                    log(f"opened the seeded pull request #{seeder.number}")
        except Exception as e:  # never let one bad PR stop the bot
            log(f"tick failed: {e}")
        time.sleep(INTERVAL)


def main():
    global sensei
    admin, password = os.environ.get("FORGEJO_ADMIN_USER"), os.environ.get("FORGEJO_ADMIN_PASSWORD")
    if not (admin and password):
        log("no Forgejo admin login: Sensei cannot act")
        sys.exit(1)
    global WATCHING, resolver, index, patterns, answers, desk, achievements
    workshop = os.environ.get("WORKSHOP_DIR", "/opt/workshop")
    lab_dir = os.path.join(workshop, "content", "lab")
    index = support.LabIndex(lab_dir)
    patterns = support.Patterns.load(lab_dir, [os.path.join(HERE, "patterns", "shared.json"),
                                              os.path.join(workshop, "sensei", "patterns.json")])
    answers = support.Answers.load([os.path.join(workshop, "sensei", "answers.json"),
                                    os.path.join(HERE, "answers", "shared.json")])
    desk = support.HelpDesk(os.path.join(os.environ.get("DATA_DIR", "/data"), "help.json"))
    log(f"support: {len(index.sections)} lab sections, {len(patterns.items)} error patterns, {len(answers.items)} ready answers")
    resolver = identity.Resolver(identity.forgejo_fetch(FORGEJO_URL))
    achievements = support.Achievements(os.environ.get("ACHIEVEMENTS_URL"), os.environ.get("ACHIEVEMENTS_KEY"))
    cfg = {"repo": os.environ.get("SENSEI_REPO", ""),
           "base": os.environ.get("SENSEI_BASE", "main"),
           "file": os.environ.get("SENSEI_FILE", "roster/team.yaml"),
           "mode": os.environ.get("SENSEI_MODE", "merge"),
           "approve_prefix": os.environ.get("SENSEI_APPROVE_PREFIX", ""),
           "self": admin,
           "patience": int(os.environ.get("SENSEI_PATIENCE_SECONDS", "180"))}
    WATCHING = bool(cfg["repo"])
    sensei = bot.Sensei(cfg, challenges.forgejo_http(FORGEJO_URL, admin, password), FORGEJO_URL,
                        secret=f"{admin}:{password}", state_path=os.path.join(os.environ.get("DATA_DIR", "/data"), "sensei.json"))
    sensei.enabled = os.environ.get("SENSEI_ENABLED", "1") not in ("0", "false", "no", "")
    global seeder
    if os.environ.get("SENSEI_SEED"):  # JSON: one PR for the class to review, see seed.py
        seeder = seed.Seeder(json.loads(os.environ["SENSEI_SEED"]), sensei.api,
                             os.path.join(os.environ.get("DATA_DIR", "/data"), "seed.json"))
    threading.Thread(target=loop, daemon=True).start()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    log(f"watching {cfg['repo']} ({cfg['file']} into {cfg['base']}), enabled={sensei.enabled}" if WATCHING
        else f"no SENSEI_REPO: not reviewing pull requests (seed only: {bool(seeder)}), enabled={sensei.enabled}")
    http.server.ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
