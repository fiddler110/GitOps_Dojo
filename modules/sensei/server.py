"""Sensei's admin service: a background loop (bot.py) and a facilitator-only page.

  GET  /healthz        liveness
  GET  /               the page (facilitator, through the gateway)
  GET  /api/prs        every pull request Sensei has seen: status, reason, minutes stuck
  POST /api/merge      {number}: merge anyway (skips the review; still resolves the roster conflict)
  POST /api/comment    {number, text}
  POST /api/scan       look now
  POST /api/enabled    {on}: pause or resume the bot
Identity headers count only with X-Gateway-Token (the route is facilitator-gated at Caddy).
"""
import hmac
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
import bot  # noqa: E402
import seed  # noqa: E402
import challenges  # noqa: E402  (the achievements service's Forgejo client)

GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")
FACILITATOR = os.environ.get("FACILITATOR_USERNAME", "root")
FORGEJO_URL = os.environ.get("FORGEJO_URL", "http://git-server:3000")
INTERVAL = int(os.environ.get("SENSEI_INTERVAL", "5"))
STATIC = os.path.join(HERE, "static")
PAGES = {"/": "admin.html", "/admin.js": "admin.js", "/style.css": "style.css"}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; "
       "form-action 'none'; frame-ancestors 'self'")
sensei = None
lock = threading.Lock()


def log(msg):
    print(f"[sensei] {msg}", flush=True)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "sensei"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, doc):
        self._send(code, json.dumps(doc).encode())

    def _facilitator(self):
        given = (self.headers.get("X-Gateway-Token") or "").encode()
        ok = GATEWAY_TOKEN and hmac.compare_digest(given, GATEWAY_TOKEN.encode())
        return ok and self.headers.get("X-Auth-User") == FACILITATOR

    def do_GET(self):
        if self.path == "/healthz":
            return self._json(200, {"ok": True})
        if not self._facilitator():
            return self._json(403, {"error": "facilitator only"})
        if self.path in PAGES:
            name = PAGES[self.path]
            with open(os.path.join(STATIC, name), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8" if name.endswith("html")
                                  else "text/javascript" if name.endswith(".js") else "text/css")
        if self.path == "/api/prs":
            with lock:
                return self._json(200, {"prs": sensei.snapshot(), "enabled": sensei.enabled, "repo": sensei.repo,
                                     "watching": WATCHING,
                                     "attention": sensei.attention()})
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._facilitator() or self.headers.get("X-Requested-With") != "dojo-admin":
            return self._json(403, {"error": "facilitator only"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 8192)) or b"{}")
        except ValueError:
            return self._json(400, {"error": "bad json"})
        number = body.get("number")
        with lock:
            if self.path == "/api/scan":
                if WATCHING:
                    sensei.tick()
            elif self.path == "/api/enabled":
                sensei.enabled = bool(body.get("on"))
            elif self.path == "/api/merge" and isinstance(number, int):
                return self._json(200, {"result": sensei.handle(number, force=True)})
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
            with lock:
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
    global WATCHING
    cfg = {"repo": os.environ.get("SENSEI_REPO", ""),
           "base": os.environ.get("SENSEI_BASE", "main"),
           "file": os.environ.get("SENSEI_FILE", "roster/team.yaml")}
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
