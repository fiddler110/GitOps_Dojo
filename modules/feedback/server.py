"""Feedback: the end-of-class survey card (RV33). Stdlib only.

  Student (route /feedback, identity gate, prefix stripped):
    GET  /            the form          GET  /api/mine   their answers so far
    POST /api/submit  {ratings: {id: 1-5}, comment}   (X-Requested-With: dojo-feedback; replaces their last answer)
  Facilitator (route /feedback-admin, facilitator gate, prefix kept):
    GET  /feedback-admin/               the summary
    GET  /feedback-admin/api/summary    GET /feedback-admin/api/export?format=csv|json  (no usernames, a download)

Answers are anonymous to the facilitator: the username only keys "one answer per student".
Trust: X-Auth-User counts only with X-Gateway-Token (dojo_http); workshop_lab reaches this port directly.
"""
import csv
import io
import json
import os
import sys
import threading
import time
import urllib.parse
import http.server

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_shared"))
sys.path.insert(0, os.path.join(HERE, "..", "_shared"))
import dojo_http  # noqa: E402

QUESTIONS = [
    ("pace", "The pace was right for me"),
    ("clarity", "The labs were clear"),
    ("useful", "I can use this in my own work"),
    ("overall", "Overall, I would recommend this class"),
]
MAX_COMMENT = 1000
MAX_ANSWERS = 1000
STATIC = os.path.join(HERE, "static")


class Denied(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status, self.msg = status, msg


class Store:
    def __init__(self, path=None, clock=time.time):
        self.path, self.clock, self.lock = path, clock, threading.Lock()
        self.answers = {}      # user -> {"ratings": {id: n}, "comment": str, "at": float}
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    self.answers = json.load(f).get("answers", {})
            except (OSError, ValueError):
                self.answers = {}

    def _save(self):
        if not self.path:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"answers": self.answers}, f)
        os.replace(tmp, self.path)

    def submit(self, user, doc):
        ratings, comment = doc.get("ratings"), doc.get("comment", "")
        if not isinstance(ratings, dict) or not isinstance(comment, str):
            raise Denied(400, "ratings and comment are required")
        clean = {}
        for qid, _ in QUESTIONS:
            n = ratings.get(qid)
            if n is None:
                continue
            if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 5:
                raise Denied(400, "each rating is a whole number from 1 to 5")
            clean[qid] = n
        comment = comment.strip()[:MAX_COMMENT]
        if not clean and not comment:
            raise Denied(400, "answer at least one question or leave a comment")
        with self.lock:
            if user not in self.answers and len(self.answers) >= MAX_ANSWERS:
                raise Denied(429, "the survey is full")
            self.answers[user] = {"ratings": clean, "comment": comment, "at": self.clock()}
            self._save()

    def mine(self, user):
        with self.lock:
            a = self.answers.get(user)
            return {"ratings": a["ratings"], "comment": a["comment"]} if a else None

    def rows(self):
        """Anonymous answers, oldest first."""
        with self.lock:
            return [{"at": a["at"], "ratings": dict(a["ratings"]), "comment": a["comment"]}
                    for a in sorted(self.answers.values(), key=lambda a: a["at"])]

    def summary(self):
        rows = self.rows()
        out = []
        for qid, text in QUESTIONS:
            vals = [r["ratings"][qid] for r in rows if qid in r["ratings"]]
            out.append({"id": qid, "text": text, "count": len(vals),
                        "mean": round(sum(vals) / len(vals), 2) if vals else None,
                        "counts": [vals.count(n) for n in range(1, 6)]})
        return {"responses": len(rows), "questions": out,
                "comments": [r["comment"] for r in rows if r["comment"]]}


def csv_cell(value):
    """Student text must not run as a spreadsheet formula when the export is opened."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def export_csv(rows):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow([q for q, _ in QUESTIONS] + ["comment"])
    for r in rows:
        w.writerow([r["ratings"].get(q, "") for q, _ in QUESTIONS] + [csv_cell(r["comment"])])
    return out.getvalue()


GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")
FACILITATOR = os.environ.get("FACILITATOR_USERNAME", "root")
STORE = Store(os.path.join(os.environ.get("DATA_DIR", "/data"), "feedback.json")
              if __name__ == "__main__" else None)
ADMIN_PREFIX = "/feedback-admin"
ASSETS = {"feedback.js", "admin.js", "style.css"}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "feedback"

    def log_message(self, fmt, *args):
        pass

    def _json(self, code, doc, extra=None):
        dojo_http.send_json(self, code, doc, extra)

    def _static(self, name):
        try:
            with open(os.path.join(STATIC, name), "rb") as f:
                body = f.read()
        except OSError:
            return self._json(404, {"error": "not found"})
        ctype = {"html": "text/html", "js": "application/javascript", "css": "text/css"}[name.rsplit(".", 1)[1]]
        dojo_http.send(self, 200, body, ctype + "; charset=utf-8")

    def _user(self):
        user = dojo_http.gateway_user(self.headers, GATEWAY_TOKEN)
        if not user:
            raise Denied(401, "sign in first")
        return user

    def _facilitator(self):
        if self._user() != FACILITATOR:
            raise Denied(403, "facilitator only")

    def _route(self, method):
        parts = urllib.parse.urlsplit(self.path)
        path, query = parts.path, urllib.parse.parse_qs(parts.query)
        if path == "/healthz" and method == "GET":
            return self._json(200, {"ok": True})
        admin = path == ADMIN_PREFIX or path.startswith(ADMIN_PREFIX + "/")
        if admin:
            path = path[len(ADMIN_PREFIX):] or "/"
            self._facilitator()      # every facilitator-route request, pages and assets too
        if method == "GET" and path in ("/", "/index.html"):
            if not admin:
                self._user()
            return self._static("admin.html" if admin else "index.html")
        if method == "GET" and path.lstrip("/") in ASSETS:
            return self._static(path.lstrip("/"))
        if method == "GET" and path == "/api/mine":
            return self._json(200, {"mine": STORE.mine(self._user())})
        if method == "POST" and path == "/api/submit":
            user = self._user()
            if self.headers.get("X-Requested-With") != "dojo-feedback":
                raise Denied(403, "missing X-Requested-With")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                doc = json.loads(self.rfile.read(min(n, 8192)) or b"{}")
            except ValueError:
                raise Denied(400, "bad JSON")
            if not isinstance(doc, dict):
                raise Denied(400, "bad JSON")
            STORE.submit(user, doc)
            return self._json(200, {"ok": True})
        if method == "GET" and path == "/api/summary":
            self._facilitator()
            return self._json(200, STORE.summary())
        if method == "GET" and path == "/api/export":
            self._facilitator()
            fmt = (query.get("format") or ["csv"])[0]
            if fmt == "json":
                return self._json(200, {"questions": dict(QUESTIONS), "answers": STORE.rows()},
                                  {"Content-Disposition": 'attachment; filename="dojo-feedback.json"'})
            if fmt != "csv":
                raise Denied(400, "format must be csv or json")
            return dojo_http.send(self, 200, export_csv(STORE.rows()).encode(), "text/csv; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="dojo-feedback.csv"'})
        raise Denied(404, "not found")

    def _handle(self, method):
        try:
            self._route(method)
        except Denied as e:
            self._json(e.status, {"error": e.msg})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
