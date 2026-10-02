#!/usr/bin/env python3
"""Achievement catalog editor: a local web page over every workshop's achievement JSON.

    python3 -B server.py --root <repo> [--workshop <name>|all] [--port 8099]

Binds 127.0.0.1 only, needs no stack and no network. Edits stay in the page until Save, which
validates the whole result with the catalog loader, writes the changed JSON files and
regenerates ACHIEVEMENTS.md (catalog_edit.py). modules/achievements/edit.sh starts it.
"""

import argparse
import json
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog_edit as ce  # noqa: E402

STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/editor.js": ("editor.js", "text/javascript; charset=utf-8"),
          "/editor.css": ("editor.css", "text/css; charset=utf-8")}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
MAX_BODY = 4 * 1024 * 1024


class Editor:
    """The server's settings: repo root, scope and the per-run token that POSTs must carry
    (a custom header, so another site in the same browser can't post here)."""

    def __init__(self, root, scope, token=None):
        self.root = root
        self.scope = scope
        self.token = token or secrets.token_urlsafe(24)
        self.lock = threading.Lock()
        self.hosts = set()


class Handler(BaseHTTPRequestHandler):
    editor = None
    server_version = "achievements-editor"

    def log_message(self, fmt, *args):   # quiet: one line per save is printed instead
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        # DNS rebinding: only answer to the loopback names this server was started on.
        return self.headers.get("Host", "") in self.editor.hosts

    def do_GET(self):
        if not self._host_ok():
            return self._send(421, {"errors": ["wrong host"]})
        path = self.path.split("?", 1)[0]
        if path in STATIC:
            name, ctype = STATIC[path]
            with open(os.path.join(HERE, "static", name), "rb") as fh:
                return self._send(200, fh.read(), ctype)
        if path == "/api/catalog":
            data = ce.load_all(self.editor.root, self.editor.scope)
            data["token"] = self.editor.token
            return self._send(200, data)
        self._send(404, {"errors": ["not found"]})

    def do_POST(self):
        if not self._host_ok():
            return self._send(421, {"errors": ["wrong host"]})
        if self.path != "/api/save":
            return self._send(404, {"errors": ["not found"]})
        if not secrets.compare_digest(self.headers.get("X-Editor-Token", ""), self.editor.token):
            return self._send(403, {"errors": ["missing or wrong editor token: reload the page"]})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            return self._send(400, {"errors": ["bad request size"]})
        try:
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._send(400, {"errors": ["body must be a JSON object"]})
        with self.editor.lock:
            try:
                res = ce.save(self.editor.root, self.editor.scope, body.get("changes"), body.get("bases"))
            except ce.EditError as exc:
                return self._send(exc.status, {"errors": exc.errors})
            print(f"saved: {', '.join(res['written']) or 'no JSON change'}"
                  + (f"; regenerated {', '.join(res['rendered'])}" if res["rendered"] else ""), flush=True)
            res["catalog"] = ce.load_all(self.editor.root, self.editor.scope)
            res["catalog"]["token"] = self.editor.token
        self._send(200, res)


def make_server(root, scope, port=0, token=None):
    ce.scope_names(root, scope)          # an unknown workshop stops here with the list
    editor = Editor(os.path.abspath(root), scope, token)
    handler = type("BoundHandler", (Handler,), {"editor": editor})
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    real = httpd.server_address[1]
    editor.hosts = {f"127.0.0.1:{real}", f"localhost:{real}"}
    return httpd, editor


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", required=True, help="repository root")
    ap.add_argument("--workshop", default="all", help="a workshop name, or all")
    ap.add_argument("--port", type=int, default=8099)
    args = ap.parse_args(argv)
    try:
        httpd, _ = make_server(args.root, args.workshop, args.port)
    except ce.EditError as exc:
        print("\n".join(exc.errors), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"can't listen on 127.0.0.1:{args.port}: {exc} (set PORT=... to pick another)", file=sys.stderr)
        return 1
    print(f"Achievement catalog editor ({args.workshop}): http://127.0.0.1:{httpd.server_address[1]}/", flush=True)
    print("Ctrl-C to stop. Edits stay in the page until you press Save.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
