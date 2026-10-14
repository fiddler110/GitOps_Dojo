"""Identity proxy for policy-bypass (defend slot). NOT part of the student repo.

Listens on CTF_PROXY_PORT (5000) and forwards to the app on 127.0.0.1:CTF_UPSTREAM_PORT (5001).
Replaces any client-supplied X-Caller-Role / X-Gateway-Token: role is `security-team` when the request carries
`Authorization: Bearer $CTF_SECTEAM_KEY`, otherwise `developer`; the token is $CTF_PROXY_TOKEN.
"""
import hmac
import http.client
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
       "transfer-encoding", "upgrade", "host", "content-length"}
STRIP = {"x-caller-role", "x-gateway-token"}


def role_for(authorization, key):
    if key and authorization and hmac.compare_digest(authorization, "Bearer " + key):
        return "security-team"
    return "developer"


def make_handler(upstream_port, key, token):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _fwd(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else None
            hdrs = {k: v for k, v in self.headers.items()
                    if k.lower() not in HOP and k.lower() not in STRIP}
            hdrs["X-Caller-Role"] = role_for(self.headers.get("Authorization"), key)
            hdrs["X-Gateway-Token"] = token
            try:
                c = http.client.HTTPConnection("127.0.0.1", upstream_port, timeout=10)
                c.request(self.command, self.path, body=body, headers=hdrs)
                r = c.getresponse()
                data = r.read()
            except OSError:
                msg = b"upstream unavailable"
                self.send_response(502)
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
                return
            self.send_response(r.status)
            for k, v in r.getheaders():
                if k.lower() not in HOP:
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            c.close()

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = _fwd
    return H


def serve(port=None, upstream_port=None, key=None, token=None):
    port = int(port or os.environ.get("CTF_PROXY_PORT", "5000"))
    up = int(upstream_port or os.environ.get("CTF_UPSTREAM_PORT", "5001"))
    key = key if key is not None else os.environ.get("CTF_SECTEAM_KEY", "")
    token = token if token is not None else os.environ.get("CTF_PROXY_TOKEN", "")
    srv = ThreadingHTTPServer(("0.0.0.0", port), make_handler(up, key, token))
    srv.daemon_threads = True
    return srv


if __name__ == "__main__":
    serve().serve_forever()
