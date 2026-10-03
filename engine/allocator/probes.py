"""Background status probes for the facilitator's status strip (/admin/api/status).
"""
import datetime
import http.client
import json
import os
import socket
import ssl
import threading
import time
import urllib.parse

from accounts import make_session, SESSION_COOKIE
from config import (
    CONTROL_PORT, CONTROL_TOKEN, EXTENSIONS, GATEWAY_LISTEN, GIT_SERVER_HOST, GIT_SERVER_PORT, PUBLIC_BASE_URL,
    _short, TTYD_USERNAME, WEB_TERMINAL_HOST,
)


# -- Facilitator service status (see the module docstring) -----------------
# One daemon thread per service (status_probe_loop, started by main()) probes
# it and republishes _status_snapshot; request handlers only
# read it. Nothing below is called from a request handler except
# handle_status_api, which does a plain read.
GATEWAY_HOST = "gateway"
STATUS_PROBE_TIMEOUT = 2.0


def _env_seconds(name, default, minimum):
    try:
        return max(minimum, float(os.environ.get(name, default)))
    except ValueError:
        return float(default)


# The three timings can be shortened for a test; the defaults suit a real class.
STATUS_INTERVAL = _env_seconds("STATUS_INTERVAL_SECONDS", 5, 0.2)
STATUS_STARTUP_GRACE = _env_seconds("STATUS_STARTUP_GRACE_SECONDS", 300, 0)
STATUS_LOSS_GRACE = _env_seconds("STATUS_LOSS_GRACE_SECONDS", 30, 0)
# Workshop-specific extras, "Label=URL" items separated by ";" (a workshop's
# compose overlay sets it, e.g. tofu-basics' Dojo Cloud). OK means HTTP 200.
STATUS_CHECKS = os.environ.get("STATUS_CHECKS", "")


class _SniHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS to one address while asking for another name (SNI), and without
    verifying the certificate. Only used by status probes, which send no
    credential and only look at the status code."""

    def __init__(self, host, port, sni=None, **kw):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        super().__init__(host, port, context=ctx, **kw)
        self._probe_ctx = ctx
        self._probe_sni = sni

    def connect(self):
        http.client.HTTPConnection.connect(self)
        self.sock = self._probe_ctx.wrap_socket(self.sock, server_hostname=self._probe_sni or self.host)


def _describe_error(exc):
    if isinstance(exc, socket.timeout):
        return f"no answer within {STATUS_PROBE_TIMEOUT:g} s"
    if isinstance(exc, ConnectionRefusedError):
        return "connection refused"
    if isinstance(exc, socket.gaierror):
        return "name not found"
    if isinstance(exc, ssl.SSLError):
        return "TLS error: " + str(exc)
    return f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__


def probe_http(host, port, path, tls=False, sni=None, host_header=None, headers=None, require_body=False):
    """One GET with a short timeout. Returns (ok, detail); never raises.
    ok is True only for HTTP 200 (a redirect is NOT ok: it means we asked the
    wrong address). On a non-200, detail is a JSON body's "detail" when
    there is one (cloud-api's /readyz sends that), else "HTTP <status>".
    require_body also demands a non-empty 200 body: Caddy answers an empty
    200 for a Host it has no site for, which would look healthy."""
    conn = None
    try:
        if tls:
            conn = _SniHTTPSConnection(host, port, sni=sni, timeout=STATUS_PROBE_TIMEOUT)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=STATUS_PROBE_TIMEOUT)
        hdrs = dict(headers or {})
        if host_header:
            hdrs["Host"] = host_header
        conn.request("GET", path, headers=hdrs)
        resp = conn.getresponse()
        if resp.status == 200:
            # Read the whole body (capped): closing with unread data makes the kernel reset the
            # connection, and the server then logs a ConnectionResetError traceback on every probe.
            body = resp.read(1 << 20)
            if require_body and not body:
                return False, "empty response (gateway has no site for this Host?)"
            return True, None
        detail = f"HTTP {resp.status}"
        try:
            parsed = json.loads(resp.read(4096))
            if isinstance(parsed, dict) and isinstance(parsed.get("detail"), str) and parsed["detail"].strip():
                detail = parsed["detail"]
        except ValueError:
            pass
        return False, _short(detail)
    except (OSError, http.client.HTTPException) as exc:  # socket.timeout and ssl errors are OSErrors
        return False, _short(_describe_error(exc))
    finally:
        if conn is not None:
            conn.close()


def probe_forgejo():
    return probe_http(GIT_SERVER_HOST, GIT_SERVER_PORT, "/api/healthz")


def probe_terminals():
    # Same call control_request("GET", "/status") makes, but through
    # probe_http so a failure has a reason and a 2 s timeout.
    return probe_http(WEB_TERMINAL_HOST, CONTROL_PORT, "/status", headers={"X-Control-Token": CONTROL_TOKEN})


def probe_slides():
    """The presentation container is on web_lab, which the allocator is not
    on, so go through the gateway (on both networks) exactly as a browser
    would: same scheme, port and Host as PUBLIC_BASE_URL. Not http://gateway:80:
    Caddy answers an empty 200 for Host "gateway" when the site is
    http://localhost, and a 308 redirect (or a TLS failure on 443) when the
    site is an https hostname, so neither would say anything about slides.
    Behind another proxy, GATEWAY_LISTEN is the address to call; with no
    host in it (http://:8080) Caddy takes any Host, so send the public one.
    /slides is behind the class login, so send a session for it: without one
    the probe would only see the login redirect."""
    public = urllib.parse.urlsplit(PUBLIC_BASE_URL)
    base = urllib.parse.urlsplit(GATEWAY_LISTEN) if GATEWAY_LISTEN else public
    tls = base.scheme == "https"
    host = base.hostname or public.hostname
    return probe_http(GATEWAY_HOST, base.port or (443 if tls else 80), "/slides/",
                      tls=tls, sni=host, host_header=base.netloc if base.hostname else public.netloc,
                      headers={"Cookie": f"{SESSION_COOKIE}={make_session(TTYD_USERNAME)}"}, require_body=True)


def _extra_probe(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return lambda: (False, "STATUS_CHECKS: not an http(s) URL")
    tls = parts.scheme == "https"
    target = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
    return lambda: probe_http(parts.hostname, parts.port or (443 if tls else 80), target, tls=tls)


def build_status_services():
    """[{name, probe, ok, last_ok, detail}] in display order. Only the probe
    threads write ok/last_ok/detail after this, under _probe_lock."""
    probes = [("Forgejo", probe_forgejo), ("Terminals", probe_terminals), ("Slides", probe_slides)]
    for item in STATUS_CHECKS.split(";"):
        label, sep, url = item.partition("=")
        label, url = label.strip()[:40], url.strip()
        if sep and label and url:
            probes.append((label, _extra_probe(url)))
    for check in EXTENSIONS["status_checks"]:
        probes.append((check["label"], _extra_probe(check["url"])))
    return [{"name": n, "probe": p, "ok": None, "last_ok": None, "detail": None} for n, p in probes]


_status_started = time.monotonic()
_status_services = build_status_services()


def classify_status(ok, last_ok, now, started=None):
    """green / yellow / red for one service; the allocator decides, not the
    service. Yellow = not OK but either never OK yet and still inside the
    startup grace, or OK within the loss grace (a blip or a restart)."""
    if ok:
        return "green"
    if last_ok is None:
        return "yellow" if now - (_status_started if started is None else started) < STATUS_STARTUP_GRACE else "red"
    return "yellow" if now - last_ok < STATUS_LOSS_GRACE else "red"


def _build_snapshot(now):
    services = []
    for svc in _status_services:
        if svc["ok"] is None:
            services.append({"name": svc["name"], "state": "yellow", "detail": "waiting for first check"})
            continue
        state = classify_status(svc["ok"], svc["last_ok"], now)
        services.append({"name": svc["name"], "state": state,
                         "detail": None if state == "green" else (svc["detail"] or "check failed")})
    return {"generatedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "services": services}


# Replaced wholesale by the probe thread, read by handle_status_api.
_status_snapshot = _build_snapshot(time.monotonic())


# Orders the probe threads' writes to `_status_services` and the snapshot
# rebuild; never held across a probe.
_probe_lock = threading.Lock()


def probe_once(svc):
    """Run one service's probe and publish a new snapshot."""
    global _status_snapshot
    try:
        ok, detail = svc["probe"]()
    except Exception as exc:  # a bad probe must not kill the thread
        ok, detail = False, _short(f"probe error: {type(exc).__name__}")
    with _probe_lock:
        now = time.monotonic()
        svc["ok"], svc["detail"] = ok, detail
        if ok:
            svc["last_ok"] = now
        _status_snapshot = _build_snapshot(now)


def status_probe_loop(svc):
    """One thread per service, so a hung probe (up to its timeout) never
    delays the others' green/yellow/red."""
    while True:
        probe_once(svc)
        time.sleep(STATUS_INTERVAL)


def start_status_probes():
    for svc in _status_services:
        threading.Thread(target=status_probe_loop, args=(svc,), name=f"status-{svc['name']}",
                         daemon=True).start()
