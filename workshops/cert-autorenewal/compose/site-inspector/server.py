#!/usr/bin/env python3
"""Site Inspector: a browser's view of a student's site on demo-app, one step at a time. Stdlib only.

Students have no browser that can reach demo-app (the gateway only proxies plain HTTP to it), so this does
what a browser would and shows its working: it starts at http:// (or https:// once the site has sent HSTS),
follows redirects, verifies each certificate against the lab CA, reads the security headers, and keeps the
page for a sandboxed preview.

Routes (the gateway strips the /inspect prefix; identity gate):
  GET  /                 the page (static/)
  GET  /api/me           who is asking, and the names they may visit
  GET  /api/visit?url=   one visit: hops, certificates, headers, and a page id
  GET  /api/page/<id>    the last pages a visit fetched, served with CSP `sandbox` (no scripts, own origin)
  POST /api/forget       forget this viewer's HSTS memory (X-Requested-With: inspector)
  GET  /healthz          200 while the process is up

Trust: X-Auth-User counts only with X-Gateway-Token (this upstream's own, from the gateway); workshop_lab
reaches this port directly. A student may visit only their own names ({user}.<zone> and below), the
facilitator any name under the zone. Every request goes to demo-app (TARGET_HOST) whatever the name
resolves to, on port 80 or 443 only, with GET only: it can't be pointed at another service.
"""
import hmac
import http.client
import json
import os
import re
import secrets
import socket
import ssl
import tempfile
import threading
import time
import urllib.parse
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")
FACILITATOR = os.environ.get("FACILITATOR_USERNAME", "root")
ZONE = os.environ.get("ZONE", "certs.dojo.test").strip(".").lower()
TARGET = os.environ.get("TARGET_HOST", "demo-app")
HTTP_PORT = int(os.environ.get("HTTP_PORT", "80"))
TLS_PORT = int(os.environ.get("TLS_PORT", "443"))
CA_ROOT = os.environ.get("CA_ROOT", "/opt/step-ca-root/root_ca.crt")
TIMEOUT = float(os.environ.get("TIMEOUT_SECONDS", "5"))

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
       "frame-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
# A fetched page is the student's HTML: its own origin, no scripts, no requests, only inline styles.
PAGE_CSP = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}

MAX_HOPS = 6
MAX_BODY = 64 * 1024
MAX_HEADERS = 40
REDIRECTS = (301, 302, 303, 307, 308)
LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
HOST = re.compile(r"^(\*\.)?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
PROTOCOLS = (("TLSv1.2", ssl.TLSVersion.TLSv1_2), ("TLSv1.3", ssl.TLSVersion.TLSv1_3))

_lock = threading.Lock()
_hsts = {}          # viewer -> {host: expiry}: what this viewer's "browser" remembers (memory only)
_pages = {}         # viewer -> OrderedDict(id -> (content type, bytes)), the last few
_last = {}          # viewer -> time of their last visit
_slots = threading.BoundedSemaphore(8)
MAX_VIEWERS, MAX_REMEMBERED, KEEP_PAGES, MIN_GAP = 500, 50, 3, 0.5


# -- who may visit what ------------------------------------------------------------------
def may_visit(viewer, host):
    host = host.lower().rstrip(".")
    if viewer == FACILITATOR:
        return host == ZONE or host.endswith("." + ZONE)
    base = f"{viewer.lower()}.{ZONE}"
    return host == base or host.endswith("." + base)


def suggestions(viewer):
    if viewer == FACILITATOR:
        return [f"{viewer.lower()}.{ZONE}"]
    base = f"{viewer.lower()}.{ZONE}"
    return [base] + [f"{n}.{base}" for n in ("shop", "www", "api", "members")]


def parse_target(raw):
    """(scheme or None, host, path) from what was typed into the address bar; ValueError when it isn't a URL
    this tool visits (other ports, credentials, odd characters)."""
    raw = (raw or "").strip()
    if not raw or len(raw) > 2048:
        raise ValueError("type a name, such as your own site's")
    scheme = None
    if "://" in raw:
        u = urllib.parse.urlsplit(raw)
        if u.scheme not in ("http", "https"):
            raise ValueError("only http:// and https:// addresses")
        scheme, netloc, path, query = u.scheme, u.netloc, u.path, u.query
    else:
        netloc, _, rest = raw.partition("/")
        path, _, query = ("/" + rest).partition("?")
    if "@" in netloc:
        raise ValueError("no user names in the address")
    if ":" in netloc:
        raise ValueError("only the standard ports (80 for http, 443 for https)")
    host = netloc.lower().rstrip(".")
    if not HOST.match(host):
        raise ValueError(f"{netloc!r} isn't a host name")
    path = path or "/"
    if query:
        path += "?" + query
    if any(c in path for c in "\r\n ") or not path.startswith("/"):
        raise ValueError("that path can't be sent as typed")
    return scheme, host, path


# -- HSTS memory --------------------------------------------------------------------------
def hsts_active(viewer, host, now):
    with _lock:
        exp = _hsts.get(viewer, {}).get(host)
    return exp is not None and exp > now


def hsts_remember(viewer, host, header, now):
    """Apply a Strict-Transport-Security header seen over verified HTTPS. Returns the max-age, or None."""
    m = re.search(r"max-age\s*=\s*\"?(\d+)", header or "", re.I)
    if not m:
        return None
    age = int(m.group(1))
    with _lock:
        if viewer not in _hsts and len(_hsts) >= MAX_VIEWERS:
            _hsts.clear()
        mem = _hsts.setdefault(viewer, {})
        if age == 0:
            mem.pop(host, None)
        else:
            if host not in mem and len(mem) >= MAX_REMEMBERED:
                mem.pop(min(mem, key=mem.get))
            mem[host] = now + age
    return age


def hsts_list(viewer, now):
    with _lock:
        mem = dict(_hsts.get(viewer, {}))
    return [{"host": h, "seconds_left": int(e - now)} for h, e in sorted(mem.items()) if e > now]


# -- one request --------------------------------------------------------------------------
def _name(rdn):
    out = {}
    for part in rdn or ():
        for k, v in part:
            out[k] = v
    return out


def _decode_der(der):
    """A cert dict like getpeercert()'s, for a certificate that didn't verify (so getpeercert() is empty)."""
    pem = ssl.DER_cert_to_PEM_cert(der)
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
        f.write(pem)
    try:
        return ssl._ssl._test_decode_cert(f.name)   # stdlib's own decoder; there is no public one
    except Exception:
        return {}
    finally:
        os.unlink(f.name)


def cert_summary(cert, now):
    if not cert:
        return None
    subj, issuer = _name(cert.get("subject")), _name(cert.get("issuer"))
    after = cert.get("notAfter")
    left = None
    if after:
        try:
            left = int(ssl.cert_time_to_seconds(after) - now)
        except ValueError:
            pass
    return {"subject": subj.get("commonName", ""),
            "names": [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"],
            "issuer": issuer.get("commonName", "") or issuer.get("organizationName", ""),
            "serial": cert.get("serialNumber", ""),
            "not_before": cert.get("notBefore", ""), "not_after": after or "", "seconds_left": left}


def _trusting():
    ctx = ssl.create_default_context(cafile=CA_ROOT if os.path.exists(CA_ROOT) else None)
    ctx.set_alpn_protocols(["http/1.1"])
    return ctx


def _blind():
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    return ctx


def probe_protocols(host):
    """Which TLS versions the server accepts for this name (handshake only, no verification)."""
    out = {}
    for label, version in PROTOCOLS:
        ctx = _blind()
        ctx.minimum_version = ctx.maximum_version = version
        try:
            with socket.create_connection((TARGET, TLS_PORT), timeout=TIMEOUT) as raw:
                with ctx.wrap_socket(raw, server_hostname=host):
                    out[label] = True
        except (OSError, ssl.SSLError):
            out[label] = False
    return out


def fetch(scheme, host, path, now):
    """One GET to demo-app, as a browser would send it. A dict: status, reason, headers, body, tls, error."""
    hop = {"url": f"{scheme}://{host}{path}", "scheme": scheme, "host": host, "path": path,
           "status": None, "reason": "", "headers": [], "tls": None, "error": None}
    port = TLS_PORT if scheme == "https" else HTTP_PORT
    try:
        raw = socket.create_connection((TARGET, port), timeout=TIMEOUT)
    except OSError as e:
        hop["error"] = f"couldn't connect to demo-app on port {port} ({e.__class__.__name__})"
        return hop, b""
    sock = raw
    try:
        if scheme == "https":
            tls = {"verified": False, "error": None, "version": None, "cipher": None, "cert": None}
            hop["tls"] = tls
            try:
                sock = _trusting().wrap_socket(raw, server_hostname=host)
            except ssl.SSLCertVerificationError as e:
                raw.close()
                tls["error"] = getattr(e, "verify_message", None) or str(e)
                try:
                    with socket.create_connection((TARGET, port), timeout=TIMEOUT) as r2:
                        with _blind().wrap_socket(r2, server_hostname=host) as s2:
                            tls["version"], tls["cipher"] = s2.version(), (s2.cipher() or ("",))[0]
                            tls["cert"] = cert_summary(_decode_der(s2.getpeercert(binary_form=True)), now)
                except (OSError, ssl.SSLError):
                    pass
                hop["error"] = f"a browser stops here: the certificate doesn't verify ({tls['error']})"
                return hop, b""
            except ssl.SSLError as e:
                hop["error"] = (f"no HTTPS for {host}: the TLS handshake failed "
                                f"({getattr(e, 'reason', None) or e.__class__.__name__})")
                return hop, b""
            tls["verified"] = True
            tls["version"], tls["cipher"] = sock.version(), (sock.cipher() or ("",))[0]
            tls["cert"] = cert_summary(sock.getpeercert(), now)
        sock.settimeout(TIMEOUT)
        sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: dojo-site-inspector\r\n"
                      "Accept: text/html,*/*;q=0.8\r\nConnection: close\r\n\r\n").encode())
        resp = http.client.HTTPResponse(sock, method="GET")
        resp.begin()
        hop["status"], hop["reason"] = resp.status, resp.reason
        hop["headers"] = [[k, v[:400]] for k, v in resp.getheaders()[:MAX_HEADERS]]
        try:
            body = resp.read(MAX_BODY)
        except (http.client.IncompleteRead, OSError) as e:
            body = getattr(e, "partial", b"") or b""
        return hop, body
    except (OSError, ssl.SSLError, http.client.HTTPException) as e:
        if hop["status"] is None:
            hop["error"] = f"demo-app didn't answer the request ({e.__class__.__name__})"
        return hop, b""
    finally:
        sock.close()


def header(hop, name):
    vals = [v for k, v in hop["headers"] if k.lower() == name]
    return ", ".join(vals) if vals else None


# -- reading the final response's headers -------------------------------------------------
def security_report(hop):
    https = hop["scheme"] == "https"
    out = []

    def add(name, value, ok, note):
        out.append({"name": name, "value": value, "ok": ok, "note": note})

    sts = header(hop, "strict-transport-security")
    if sts and not https:
        add("Strict-Transport-Security", sts, False, "sent over plain HTTP, so browsers ignore it")
    elif sts:
        m = re.search(r"max-age\s*=\s*\"?(\d+)", sts, re.I)
        age = int(m.group(1)) if m else None
        add("Strict-Transport-Security", sts, bool(age),
            f"browsers go straight to https:// for {age} seconds" if age else "no usable max-age")
    else:
        add("Strict-Transport-Security", None, False,
            "missing: the next visit starts over plain http:// again" if https else "only counts over HTTPS")
    csp = header(hop, "content-security-policy")
    add("Content-Security-Policy", csp, bool(csp),
        "where scripts, styles and frames may come from" if csp else "missing: the page may load anything")
    nosniff = header(hop, "x-content-type-options")
    add("X-Content-Type-Options", nosniff, (nosniff or "").strip().lower() == "nosniff",
        "the browser trusts Content-Type" if nosniff else "missing: the browser may guess a file's type")
    xfo = header(hop, "x-frame-options")
    fa = bool(csp and "frame-ancestors" in csp.lower())
    add("Frame protection", ("CSP frame-ancestors" if fa else xfo), bool(fa or xfo),
        "other sites can't frame this page" if (fa or xfo) else "missing: any site can put this page in a frame")
    ref = header(hop, "referrer-policy")
    add("Referrer-Policy", ref, bool(ref), "what a link tells the next site" if ref else
        "missing: the browser's default applies")
    perm = header(hop, "permissions-policy")
    add("Permissions-Policy", perm, bool(perm), "camera, location and so on, switched off" if perm else
        "missing: the browser's defaults apply")
    for k, v in hop["headers"]:
        if k.lower() == "set-cookie":
            flags = v.lower()
            ok = "secure" in flags and "httponly" in flags and "samesite" in flags
            add("Set-Cookie", v.split(";", 1)[0][:60] + "; ...", ok,
                "Secure, HttpOnly and SameSite all set" if ok else "wants Secure; HttpOnly; SameSite")
    if not https:
        out.append({"name": "(plain HTTP)", "value": None, "ok": False,
                    "note": "anyone on the path can read or change this response, headers included"})
    return out


# -- a whole visit ------------------------------------------------------------------------
def visit(viewer, raw, now=None):
    now = time.time() if now is None else now
    scheme, host, path = parse_target(raw)
    if not may_visit(viewer, host):
        raise PermissionError(f"you can visit your own names only ({suggestions(viewer)[0]} and below)")
    hops, notes = [], []
    if scheme is None:
        scheme = "http"
        notes.append("typed without a scheme: a browser tries http:// first")
    if scheme == "http" and hsts_active(viewer, host, now):
        hops.append({"kind": "hsts", "url": f"http://{host}{path}",
                     "note": f"HSTS: this browser remembers {host} is HTTPS-only, so it never sends this "
                             "request; it goes straight to https:// (an internal 307)"})
        scheme = "https"
    final, body, stopped = None, b"", None
    for _ in range(MAX_HOPS):
        hop, body = fetch(scheme, host, path, now)
        hop["kind"] = "request"
        hops.append(hop)
        final = hop
        if hop["error"]:
            stopped = hop["error"]
            break
        tls = hop["tls"]
        if tls and tls["verified"] and scheme == "https":
            sts = header(hop, "strict-transport-security")
            if sts is not None:
                age = hsts_remember(viewer, host, sts, now)
                hop["note"] = (f"HSTS remembered for {age} seconds" if age else
                               ("HSTS max-age=0: forgotten" if age == 0 else "HSTS header without max-age"))
        elif scheme == "http" and header(hop, "strict-transport-security"):
            hop["note"] = "HSTS over plain HTTP is ignored: it only counts when it arrives over HTTPS"
        if b"No required SSL certificate was sent" in body:
            hop["note"] = "this site asks for a client certificate (mTLS); the inspector doesn't present one"
        loc = header(hop, "location")
        if hop["status"] not in REDIRECTS or not loc:
            break
        nxt = urllib.parse.urljoin(hop["url"], loc)
        try:
            n_scheme, n_host, n_path = parse_target(nxt)
        except ValueError as e:
            stopped = f"not followed: {nxt} ({e})"
            break
        if not may_visit(viewer, n_host):
            stopped = f"not followed: {nxt} is not one of your names"
            break
        if n_scheme == "http" and hsts_active(viewer, n_host, now):
            hops.append({"kind": "hsts", "url": nxt,
                         "note": f"HSTS: upgraded to https://{n_host} without sending the request"})
            n_scheme = "https"
        if (n_scheme, n_host, n_path) == (scheme, host, path):
            stopped = "redirects to itself: a browser shows 'too many redirects'"
            break
        scheme, host, path = n_scheme, n_host, n_path
    else:
        stopped = f"more than {MAX_HOPS} redirects: a browser gives up here"
    result = {"hops": hops, "notes": notes, "stopped": stopped, "final": None}
    if final and final["tls"] and final["tls"]["verified"]:
        final["tls"]["protocols"] = probe_protocols(final["host"])
    if final and final["status"] is not None:
        ctype = header(final, "content-type") or "application/octet-stream"
        result["final"] = {"url": final["url"], "status": final["status"], "content_type": ctype,
                           "bytes": len(body), "truncated": len(body) >= MAX_BODY,
                           "security": security_report(final),
                           "source": body[:8192].decode("utf-8", "replace"),
                           "page": keep_page(viewer, ctype, body) if body else None}
    result["hsts"] = hsts_list(viewer, now)
    return result


def keep_page(viewer, ctype, body):
    page_id = secrets.token_hex(8)
    with _lock:
        if viewer not in _pages and len(_pages) >= MAX_VIEWERS:
            _pages.clear()
        kept = _pages.setdefault(viewer, OrderedDict())
        kept[page_id] = ("text/html; charset=utf-8" if "html" in ctype.lower() else "text/plain; charset=utf-8",
                         body)
        while len(kept) > KEEP_PAGES:
            kept.popitem(last=False)
    return page_id


# -- HTTP ---------------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "site-inspector"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def viewer(self):
        given = self.headers.get("X-Gateway-Token") or ""
        user = (self.headers.get("X-Auth-User") or "").strip()
        if not GATEWAY_TOKEN or not hmac.compare_digest(given.encode(), GATEWAY_TOKEN.encode()):
            return None
        if user != FACILITATOR and not LABEL.match(user.lower()):
            return None
        return user

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        path = url.path
        if path == "/healthz":
            return self._send(200, b"ok\n", "text/plain")
        viewer = self.viewer()
        if viewer is None:
            return self._send(403, {"error": "open this through the workshop homepage"})
        if path in ("/", "/index.html"):
            return self._static("index.html")
        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        if path == "/api/me":
            return self._send(200, {"user": viewer, "facilitator": viewer == FACILITATOR, "zone": ZONE,
                                    "suggestions": suggestions(viewer),
                                    "hsts": hsts_list(viewer, time.time())})
        if path == "/api/visit":
            target = urllib.parse.parse_qs(url.query).get("url", [""])[0]
            now = time.time()
            with _lock:
                wait = _last.get(viewer, 0) + MIN_GAP - now
                if len(_last) >= MAX_VIEWERS:
                    _last.clear()
                _last[viewer] = now
            if wait > 0:
                return self._send(429, {"error": "one visit at a time; try again in a moment"})
            if not _slots.acquire(timeout=10):
                return self._send(503, {"error": "the inspector is busy; try again in a moment"})
            try:
                return self._send(200, visit(viewer, target, now))
            except PermissionError as e:
                return self._send(403, {"error": str(e)})
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            finally:
                _slots.release()
        m = re.fullmatch(r"/api/page/([0-9a-f]{16})", path)
        if m:
            with _lock:
                page = _pages.get(viewer, {}).get(m.group(1))
            if page is None:
                return self._send(404, "gone: visit the site again\n", "text/plain; charset=utf-8")
            return self._send(200, page[1], page[0], {"Content-Security-Policy": PAGE_CSP})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        viewer = self.viewer()
        if viewer is None:
            return self._send(403, {"error": "open this through the workshop homepage"})
        if self.path != "/api/forget" or self.headers.get("X-Requested-With") != "inspector":
            return self._send(404, {"error": "not found"})
        with _lock:
            _hsts.pop(viewer, None)
        return self._send(200, {"hsts": []})

    def _static(self, name):
        full = os.path.realpath(os.path.join(STATIC, name))
        ext = os.path.splitext(full)[1]
        if not full.startswith(STATIC + os.sep) or ext not in TYPES or not os.path.isfile(full):
            return self._send(404, {"error": "not found"})
        with open(full, "rb") as f:
            return self._send(200, f.read(), TYPES[ext], {"Content-Security-Policy": CSP})


def main():
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
