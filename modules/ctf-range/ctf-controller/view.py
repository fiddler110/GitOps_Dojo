"""ctf-view: a reverse proxy that lets a student open THEIR OWN live target in
a normal browser tab, through the gateway (/ctf-view/<target>/...).

Why a separate process: the controller is deliberately not on ctf_net (it holds
the ctf-host socket); this one is on ctf_net and workshop_lab and holds nothing.
It reuses controller.Config so the student -> target IP math has one copy.

Trust: identity is X-Auth-User alongside this upstream's own X-Gateway-Token
(dojo_http.gateway_user). A student can only ever reach the IP Config computes
for their own name; only the facilitator may name another student, as
/ctf-view/<student>/<target>/. A target is attacker-controlled content on the
dojo origin, so every reply carries a CSP that lets the page render and post its
own forms but forbids script from calling back to the gateway (connect-src
'none'). A CSP `sandbox` was tried and does not work: the opaque origin makes
the browser drop the login cookie on the page's own CSS and form posts (401).
The dojo login cookie is HttpOnly and is never forwarded to, or settable by,
the target.
"""
import concurrent.futures
import html
import http.client
import http.server
import os
import re
import signal
import socket
import socketserver
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared"), HERE]
import dojo_http  # noqa: E402
from controller import Config  # noqa: E402

MAX_BODY = 5 * 1024 * 1024
TIMEOUT = 10
FORWARD = ("content-type", "content-length", "cookie", "authorization", "user-agent", "accept", "accept-language")
DROP_RESP = {"connection", "keep-alive", "transfer-encoding", "content-length", "content-encoding",
             "content-security-policy", "x-frame-options", "set-cookie", "location"}
ATTR = re.compile(rb"""(\b(?:href|src|action)\s*=\s*["']?)/(?!/)""", re.I)
SANDBOX = {"Content-Security-Policy": ("default-src 'self' data:; script-src 'self' 'unsafe-inline'; "
                                       "style-src 'self' 'unsafe-inline'; connect-src 'none'; "
                                       "object-src 'none'; base-uri 'none'"),
           "X-Frame-Options": "SAMEORIGIN", "X-Content-Type-Options": "nosniff",
           "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"}


def resolve(cfg, user, is_fac, path):
    """(student, target, prefix, rest, needs_slash) for a request path, or
    (None, error, "", "", False)."""
    parts = path.strip("/").split("/") if path.strip("/") else [""]
    student, seg = user, ""
    if parts[0] in cfg.index:
        student, seg, parts = parts[0], parts[0] + "/", parts[1:] or [""]
        if student != user and not is_fac:
            return None, "not your target", "", "", False
    if student == user and is_fac:
        return None, "facilitator: use /ctf-view/<student>/<target>/", "", "", False
    if parts[0] not in cfg.attack_targets:
        return None, "unknown target", "", "", False
    prefix = "/ctf-view/" + seg + parts[0]
    return student, parts[0], prefix, "/" + "/".join(parts[1:]), len(parts) == 1 and not path.endswith("/")


# Friendly names for the picker (presentation only; unknown ids fall back to the id).
TITLES = {
    "sqli-login": ("Meridian Intranet", "Employee sign-in portal"),
    "weak-auth-portal": ("Northwind Ops Console", "Operations sign-in with password reset"),
    "idor-pcap": ("Helpdesk Ticket Archive", "Support tickets and their attachments"),
    "cert-trust-bypass": ("Zero-Trust API Gateway", "Internal API behind client certificates"),
    "customer-portal": ("Customer Portal", "Account lookup for customers"),
    "ping-tool": ("Network Diagnostics", "Ping and trace helper for ops"),
    "ssrf-fetcher": ("Link Preview Service", "Fetches a URL and shows a preview"),
    "api-mass-assignment": ("Accounts API", "Profile and account endpoints"),
    "api-bfla": ("Admin API", "Back-office endpoints"),
    "leaky-config": ("Config Service", "Service configuration and logs"),
    "git-secrets": ("Internal Git", "Source repository host"),
    "policy-bypass": ("Policy Engine", "Resource access policy"),
    "dns-resolver-cve": ("DNS Resolver", "Internal recursive resolver"),
    "runner-escape": ("CI Runner", "Pipeline runner for pull requests"),
    "tfstate-treasure": ("Terraform State", "Infrastructure state backend"),
}

UI_CSS = """
:root{color-scheme:light dark;--bg:#fafafa;--card:#fff;--line:#ddd;--ink:#1a1a1a;--mute:#6b7280;--live:#16a34a;--acc:#2563eb}
@media (prefers-color-scheme:dark){:root{--bg:#171717;--card:#1f1f1f;--line:#333;--ink:#eee;--mute:#9ca3af;--live:#22c55e;--acc:#60a5fa}}
*{box-sizing:border-box}body{margin:0;padding:1.2rem;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,sans-serif}
h1{font-size:1.2rem;margin:0 0 .3rem}.hint{color:var(--mute);margin:0 0 1rem;font-size:.9rem}.hint a{color:var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:.8rem}
.box{display:flex;flex-direction:column;gap:.35rem;padding:1rem;border:1px solid var(--line);border-radius:10px;background:var(--card);color:inherit;text-decoration:none}
.box b{font-size:1rem}.box span{color:var(--mute);font-size:.85rem}.box code{font-size:.8rem;color:var(--mute)}
.state{font-size:.72rem;letter-spacing:.05em;text-transform:uppercase}
a.live{border-color:var(--live);box-shadow:0 0 0 1px var(--live) inset}a.live:hover{background:color-mix(in srgb,var(--live) 8%,var(--card))}
a.live .state{color:var(--live);font-weight:700}
div.off{opacity:.5;cursor:not-allowed;filter:grayscale(1)}
ul.names{columns:3;list-style:none;padding:0}ul.names a{color:var(--acc)}
"""


def _live(ip, port):
    try:
        socket.create_connection((ip, port), timeout=0.5).close()
        return True
    except OSError:
        return False


def index_page(cfg, user, is_fac, path):
    """The /ctf-view/ landing page: the student's boxes as cards (only the live
    one is a link; the rest are greyed out), or for the facilitator a student
    list then that student's cards. None if PATH is not an index path. Every
    string is escaped; styling is the external /ctf-view/ui.css (strict CSP)."""
    seg = path.strip("/")
    if seg and not (is_fac and seg in cfg.index):
        return None
    esc = html.escape
    refresh = ""
    if is_fac and not seg:
        title = "Target Viewer"
        body = ('<p class="hint">Pick a student to see their live target.</p><ul class="names">'
                + "".join(f'<li><a href="/ctf-view/{esc(u)}/">{esc(u)}</a></li>' for u in cfg.users) + "</ul>")
    else:
        student = seg or user
        base = "/ctf-view/" + (seg + "/" if seg else "")
        ids = list(cfg.attack_targets)
        ips = [cfg.attack_target_ip(student, t) for t in ids]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            up = list(ex.map(lambda ip: bool(ip) and _live(ip, cfg.container_port), ips))
        cards = []
        for t, ip, on in zip(ids, ips, up):
            name, blurb = TITLES.get(t, (t, ""))
            inner = (f'<b>{esc(name)}</b><span>{esc(blurb)}</span><code>{esc(ip)}:{cfg.container_port}</code>'
                     f'<span class="state">{"Running - open" if on else "Not started"}</span>')
            cards.append(f'<a class="box live" href="{base}{esc(t)}/" target="_blank" rel="noopener">{inner}</a>'
                         if on else f'<div class="box off" aria-disabled="true">{inner}</div>')
        title = "Target Viewer" + (f" - {esc(student)}" if seg else "")
        hint = ("Open the web page of a box that is running. Start one on the "
                '<a href="/ctf-attack/">Attack Range</a> page; this list refreshes by itself.')
        body = f'<p class="hint">{hint}</p><div class="grid">{"".join(cards)}</div>'
        refresh = '<meta http-equiv="refresh" content="8">'
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">' + refresh +
            f'<title>{title}</title><link rel="stylesheet" href="/ctf-view/ui.css"></head>'
            f"<body><h1>{title}</h1>{body}</body></html>")
    return page.encode()


def rewrite_cookie(value):
    return re.sub(r"(?i);\s*path=[^;]*", "", value) + "; Path=/"


def make_handler(cfg):
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "ctf-view"

        def log_message(self, *a):
            pass

        def _text(self, status, msg):
            dojo_http.send(self, status, (msg + "\n").encode(), "text/plain; charset=utf-8", SANDBOX)

        def _proxy(self):
            if self.path == "/healthz":
                return self._text(200, "ok")
            user = dojo_http.gateway_user(self.headers, cfg.gateway_token)
            if not user:
                return self._text(403, "gateway token required")
            is_fac = bool(cfg.facilitator) and user == cfg.facilitator
            path, _, query = self.path.partition("?")
            if path == "/ui.css":
                return dojo_http.send(self, 200, UI_CSS.encode(), "text/css; charset=utf-8")
            page = index_page(cfg, user, is_fac, path)
            if page is not None:
                return dojo_http.send(self, 200, page, "text/html; charset=utf-8")
            student, target, prefix, rest, slash = resolve(cfg, user, is_fac, path)
            if student is None:
                return self._text(404, target)
            if slash:
                self.send_response(302)
                self.send_header("Location", prefix + "/" + ("?" + query if query else ""))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            ip = cfg.attack_target_ip(student, target)
            if not ip:
                return self._text(503, "no address for this target")
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._text(413, "body too large")
            body = self.rfile.read(n) if n else None
            hdrs = {k: self.headers[k] for k in FORWARD if self.headers.get(k)}
            ck = [c for c in hdrs.get("cookie", "").split(";") if not c.strip().startswith("dojo_login=")]
            hdrs.pop("cookie", None)
            if any(c.strip() for c in ck):
                hdrs["Cookie"] = ";".join(ck).strip()
            hdrs["Accept-Encoding"] = "identity"
            hdrs["Host"] = f"{ip}:{cfg.container_port}"
            try:
                c = http.client.HTTPConnection(ip, cfg.container_port, timeout=TIMEOUT)
                c.request(self.command, rest + ("?" + query if query else ""), body, hdrs)
                r = c.getresponse()
                data = r.read(MAX_BODY + 1)
            except (OSError, http.client.HTTPException):
                return self._text(503, f"{target} is not answering -- is it Started on the Attack Range page?")
            if len(data) > MAX_BODY:
                return self._text(502, "response too large")
            ctype = r.getheader("Content-Type", "application/octet-stream")
            if ctype.lower().startswith("text/html"):
                data = ATTR.sub(lambda m: m.group(1) + prefix.encode() + b"/", data)
            self.send_response(r.status)
            for k, v in r.getheaders():
                kl = k.lower()
                if kl in DROP_RESP:
                    if kl == "location":
                        loc = v if not v.startswith("/") or v.startswith("//") else prefix + v
                        self.send_header("Location", loc)
                    elif kl == "set-cookie" and not v.lstrip().lower().startswith("dojo_login="):
                        self.send_header("Set-Cookie", rewrite_cookie(v))
                    continue
                self.send_header(k, v)
            for k, v in SANDBOX.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        do_GET = do_POST = do_HEAD = do_PUT = do_DELETE = do_PATCH = _proxy

    return H


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    cfg = Config()
    print(f"[ctf-view] {len(cfg.attack_targets)} target(s), {len(cfg.users)} student(s)", flush=True)
    Server(("0.0.0.0", 9100), make_handler(cfg)).serve_forever()


if __name__ == "__main__":
    main()
