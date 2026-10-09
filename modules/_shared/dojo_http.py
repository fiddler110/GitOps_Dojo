"""What every module web service shares: the gateway-token check, one set of
security headers, and JSON replies for http.server handlers.

One copy, here. A module lists it in its module.env (SHARED="<context>/dojo_http.py")
and ./dojo copies it into <context>/_shared/ before building, so it is inside a
build context and inside a folder a service bind-mounts. A service puts both
modules/_shared/ (the source tree: unit tests) and its own _shared/ (the
container) on sys.path before importing it.

Trust: X-Auth-User counts only alongside X-Gateway-Token, and only Caddy sets
both. Anything on workshop_lab can reach a service's port directly, so a
missing or wrong token means no identity at all. An unset token fails closed.
"""
import hmac
import json

# Strict enough for pages that load only their own files; a service with a looser
# need (dns-admin's PowerDNS-Admin, which uses inline script) keeps its own.
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Frame-Options": "SAMEORIGIN",   # only the /admin workspace (same origin) frames these pages
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def token_ok(given, expected):
    """The gateway token matches. False when either is empty."""
    if not given or not expected:
        return False
    return hmac.compare_digest(given.encode(), expected.encode())


def gateway_user(headers, token):
    """The user the gateway identified (X-Auth-User), or None without the right
    X-Gateway-Token. HEADERS is anything with .get (http.server's headers, a dict)."""
    if not token_ok(headers.get("X-Gateway-Token") or "", token):
        return None
    return headers.get("X-Auth-User") or None


def is_facilitator(headers, token, facilitator):
    """The gateway identified the facilitator account."""
    user = gateway_user(headers, token)
    return bool(user) and user == facilitator


def headers(extra=None):
    """SECURITY_HEADERS, with EXTRA added or overriding (e.g. a page's Cache-Control)."""
    out = dict(SECURITY_HEADERS)
    out.update(extra or {})
    return out


def send(handler, status, body, ctype, extra=None):
    """Reply from an http.server handler: status, Content-Type and -Length, the
    security headers (EXTRA overrides), and the body unless it is a HEAD."""
    handler.send_response(status)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    for k, v in headers(extra).items():
        handler.send_header(k, v)
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(body)


def send_json(handler, status, doc, extra=None):
    send(handler, status, json.dumps(doc).encode(), "application/json", extra)
