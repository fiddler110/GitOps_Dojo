"""certs verifier verbs (see verifiers.json). Stdlib only. Every verb is `fn(api, args, ctx) -> (passed, message)`.
`api` is the Forgejo client the runner passes to every verb; these ignore it."""
import http.client
import os
import re
import socket
import ssl
import time


class Unavailable(Exception):
    """The demo app's HTTPS listener couldn't be reached (try again)."""


def _parent():
    return os.environ.get("CERTS_PARENT", "certs.dojo.test").strip(".").lower()


def _own(host, ctx):
    host = str(host).lower().rstrip(".")
    base = f"{ctx['user']}.{_parent()}"
    return host == base or host.endswith("." + base)


_roots = None


def _trust():
    """An SSL context that trusts the lab's CA. CERTS_CA_ROOT is a file; else CERTS_CA_URL is the CA's public
    /roots.pem, fetched once (it is a public root, so that one fetch isn't verified) and kept in memory."""
    global _roots
    path, url = os.environ.get("CERTS_CA_ROOT"), os.environ.get("CERTS_CA_URL")
    if path or not url:
        return ssl.create_default_context(cafile=path or None)
    if _roots is None:
        import urllib.request
        insecure = ssl.create_default_context()
        insecure.check_hostname, insecure.verify_mode = False, ssl.CERT_NONE
        try:
            with urllib.request.urlopen(url, timeout=8, context=insecure) as r:
                _roots = r.read().decode()
        except (OSError, ValueError) as e:
            raise Unavailable(f"the CA's root certificate isn't reachable ({e.__class__.__name__})")
    return ssl.create_default_context(cadata=_roots)


def _fetch(host):
    """The peer certificate dict for `host` (SNI), or raises ssl.SSLError when it doesn't verify."""
    addr = os.environ.get("CERTS_TLS_ADDR", "")
    if not addr:
        raise Unavailable("no CERTS_TLS_ADDR set")
    hostname, _, port = addr.rpartition(":")
    sslctx = _trust()
    try:
        with socket.create_connection((hostname, int(port)), timeout=8) as raw:
            with sslctx.wrap_socket(raw, server_hostname=host) as tls:
                return tls.getpeercert()
    except ssl.SSLError:
        raise
    except (OSError, ValueError) as e:
        raise Unavailable(f"demo-app isn't reachable ({e.__class__.__name__})")


def _cert(host, ctx):
    """(cert, None) or (None, failure message)."""
    if not _own(host, ctx):
        return None, "that check may only read your own hostnames"
    try:
        return _fetch(host), None
    except ssl.SSLCertVerificationError as e:
        return None, f"{host} is served a certificate that doesn't verify: {getattr(e, 'verify_message', None) or e.__class__.__name__}"
    except ssl.SSLError as e:
        return None, f"{host} has no HTTPS yet ({e.__class__.__name__})"


def _sans(cert):
    return {v.lower() for k, v in cert.get("subjectAltName", ()) if k == "DNS"}


def _san_ok(cert, san, host):
    have = _sans(cert)
    for name in san or []:
        if name.lower() not in have:
            return f"the certificate for {host} doesn't cover {name}"
    return None


def served_cert(api, args, ctx):
    host = args.get("host")
    cert, fail = _cert(host, ctx)
    if fail:
        return False, fail
    miss = _san_ok(cert, args.get("san"), host)
    if miss:
        return False, miss
    other = args.get("differs_from")
    if other:
        first, fail = _cert(other, ctx)
        if fail:
            return False, fail
        if first["serialNumber"] == cert["serialNumber"]:
            return False, f"{host} is served the same certificate as {other}: it needs its own"
    return True, "ok"


def served_same(api, args, ctx):
    serials = set()
    for host in args.get("hosts") or []:
        cert, fail = _cert(host, ctx)
        if fail:
            return False, fail
        miss = _san_ok(cert, args.get("san"), host)
        if miss:
            return False, miss
        serials.add(cert["serialNumber"])
    if len(serials) > 1:
        return False, "the hostnames are served different certificates"
    return True, "ok"


_seen = {}      # (user, host, key) -> serials this service has seen served, in order (memory only)
MAX_SEEN = 5000


def served_changed(api, args, ctx):
    """The host's served certificate has changed: `times` distinct valid serials (default 2) have been seen
    since this verb first looked at it (per `key`, so two items keep separate baselines). The memory is the
    service's own, so a restart starts a new baseline."""
    host = str(args.get("host"))
    cert, fail = _cert(host, ctx)
    if fail:
        return False, fail
    k = (ctx["user"], host.lower(), str(args.get("key", "")))
    if k not in _seen and len(_seen) >= MAX_SEEN:
        _seen.clear()
    serials = _seen.setdefault(k, [])
    if cert["serialNumber"] not in serials:
        serials.append(cert["serialNumber"])
    want = int(args.get("times", 2))
    if len(serials) < want:
        return False, f"{host} is still served the same certificate; it hasn't been renewed since I started watching"
    return True, "ok"


_watch = {}     # (user, host) -> {"since", "serials"}: a renewal watch in progress (memory only)


def served_renews(api, args, ctx):
    """The host keeps itself renewed: for `minutes` (default 20) every look found a valid certificate, and its
    serial changed at least `renewals` times (default 2). The first call starts the watch; the service's state
    sweep keeps calling it (a challenge with `"watch": true`). A look that finds no valid certificate starts the
    watch again, as does a restart of the service. Looks are a sweep apart, so a lapse shorter than that can be
    missed."""
    host = str(args.get("host"))
    minutes, want = float(args.get("minutes", 20)), int(args.get("renewals", 2))
    k = (ctx["user"], host.lower())
    now = ctx["now"] if "now" in ctx else time.time()
    cert, fail = _cert(host, ctx)
    if fail:
        _watch.pop(k, None)
        return False, f"{fail}; the {minutes:g}-minute watch starts again once it is valid"
    if k not in _watch and len(_watch) >= MAX_SEEN:
        _watch.clear()
    w = _watch.setdefault(k, {"since": now, "serials": []})
    if cert["serialNumber"] not in w["serials"]:
        w["serials"].append(cert["serialNumber"])
    done, renewed = (now - w["since"]) / 60, len(w["serials"]) - 1
    if done >= minutes and renewed >= want:
        return True, "ok"
    return False, (f"watching {host}: {int(done)} of {minutes:g} minutes, renewed {renewed} of {want} times; "
                   "I keep checking on my own, nothing else to run")


def served_expired(api, args, ctx):
    """The host is served a certificate that has expired (the handshake fails for that reason)."""
    host = str(args.get("host"))
    if not _own(host, ctx):
        return False, "that check may only read your own hostnames"
    try:
        _fetch(host)
    except ssl.SSLCertVerificationError as e:
        if "expired" in (getattr(e, "verify_message", "") or str(e)).lower():
            return True, "ok"
        return False, f"{host}'s certificate fails for another reason"
    except ssl.SSLError as e:
        return False, f"{host} has no HTTPS yet ({e.__class__.__name__})"
    return False, f"{host} is served a certificate that is still valid"


# -- HTTP behaviour: redirect to HTTPS, and HSTS ------------------------------------------
PERMANENT = (301, 308)


def _head(host, tls, client=None):
    """(status, {header: value}) for GET / with Host: host, over TLS to CERTS_TLS_ADDR (SNI, verified against
    the CA root like _fetch) or over plain HTTP to CERTS_HTTP_ADDR (default: the TLS address's host, port 80).
    client: a (cert file, key file) to present over TLS. Raises ssl.SSLError when the certificate doesn't
    verify, Unavailable when the demo app can't be reached."""
    tls_addr = os.environ.get("CERTS_TLS_ADDR", "")
    addr = tls_addr if tls else (os.environ.get("CERTS_HTTP_ADDR") or
                                 (tls_addr.rpartition(":")[0] + ":80" if tls_addr else ""))
    if not addr:
        raise Unavailable("no CERTS_TLS_ADDR set")
    hostname, _, port = addr.rpartition(":")
    try:
        with socket.create_connection((hostname, int(port)), timeout=8) as raw:
            sslctx = _trust() if tls else None
            if client:
                sslctx.load_cert_chain(*client)
            sock = sslctx.wrap_socket(raw, server_hostname=host) if tls else raw
            try:
                sock.sendall(f"GET / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: dojo-check\r\n"
                             "Connection: close\r\n\r\n".encode())
                resp = http.client.HTTPResponse(sock)
                resp.begin()
                return resp.status, {k.lower(): v for k, v in resp.getheaders()}
            finally:
                if tls:
                    sock.close()
    except ssl.SSLError:
        raise
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise Unavailable(f"demo-app isn't reachable ({e.__class__.__name__})")


def served_redirect(api, args, ctx):
    """Plain http://host/ answers with a permanent redirect (301 or 308) to https://host/..., for every host."""
    for host in args.get("hosts") or []:
        if not _own(host, ctx):
            return False, "that check may only read your own hostnames"
        status, headers = _head(host, tls=False)
        where = headers.get("location", "")
        if status in (301, 302, 303, 307, 308):
            if not where.lower().startswith(f"https://{host.lower()}"):
                return False, f"http://{host}/ redirects to {where or 'nowhere'}, not to https://{host}/"
            if status not in PERMANENT:
                return False, f"http://{host}/ redirects with {status}, a temporary redirect: make it permanent"
            continue
        return False, f"http://{host}/ answers {status} over plain HTTP: send it to https://{host}/ instead"
    return True, "ok"


def served_hsts(api, args, ctx):
    """https://host/ is served a valid certificate and a Strict-Transport-Security header whose max-age is at
    least min_age seconds (default 86400), for every host."""
    want = int(args.get("min_age", 86400))
    for host in args.get("hosts") or []:
        if not _own(host, ctx):
            return False, "that check may only read your own hostnames"
        try:
            _, headers = _head(host, tls=True)
        except ssl.SSLCertVerificationError as e:
            return False, (f"{host} is served a certificate that doesn't verify: "
                           f"{getattr(e, 'verify_message', None) or e.__class__.__name__}")
        except ssl.SSLError as e:
            return False, f"{host} has no HTTPS yet ({e.__class__.__name__})"
        hsts = headers.get("strict-transport-security")
        if not hsts:
            return False, f"https://{host}/ sends no Strict-Transport-Security header"
        m = re.search(r"max-age\s*=\s*\"?(\d+)", hsts, re.I)
        if not m or int(m.group(1)) < want:
            return False, f"{host}'s Strict-Transport-Security max-age is under {want} seconds"
    return True, "ok"


def _https_headers(host, ctx):
    """(headers, None) for GET https://host/, or (None, failure message)."""
    if not _own(host, ctx):
        return None, "that check may only read your own hostnames"
    try:
        status, headers = _head(host, tls=True)
    except ssl.SSLCertVerificationError as e:
        return None, (f"{host} is served a certificate that doesn't verify: "
                      f"{getattr(e, 'verify_message', None) or e.__class__.__name__}")
    except ssl.SSLError as e:
        return None, f"{host} has no HTTPS yet ({e.__class__.__name__})"
    return headers, None


def served_header(api, args, ctx):
    """https://host/ answers with header `name` whose value matches `regex` (case-insensitive), for every host."""
    name = str(args.get("name", ""))
    want = re.compile(str(args.get("regex", ".")), re.I)
    for host in args.get("hosts") or []:
        headers, fail = _https_headers(host, ctx)
        if fail:
            return False, fail
        value = headers.get(name.lower())
        if value is None:
            return False, f"https://{host}/ sends no {name} header"
        if not want.search(value):
            return False, f"https://{host}/ sends {name}: {value[:80]}, which isn't what's asked for"
    return True, "ok"


REFUSED = (400, 401, 403, 495, 496)


def _client_cert():
    cert, key = os.environ.get("CERTS_CLIENT_CERT", ""), os.environ.get("CERTS_CLIENT_KEY", "")
    if not (cert and key and os.path.isfile(cert) and os.path.isfile(key)):
        raise Unavailable("the checker's own client certificate isn't there yet")
    return cert, key


def served_mtls(api, args, ctx):
    """https://host/ wants a client certificate from the lab CA: without one it is refused (the handshake fails,
    or the answer is 400/401/403/495/496), and with the checker's own client certificate (CERTS_CLIENT_CERT,
    CERTS_CLIENT_KEY, issued by the lab CA) it answers 2xx."""
    host = str(args.get("host"))
    if not _own(host, ctx):
        return False, "that check may only read your own hostnames"
    client = _client_cert()
    try:
        status, _ = _head(host, tls=True)
    except ssl.SSLCertVerificationError as e:
        return False, (f"{host} is served a certificate that doesn't verify: "
                       f"{getattr(e, 'verify_message', None) or e.__class__.__name__}")
    except ssl.SSLError:
        status = None           # refused in the handshake: that counts as asking for a certificate
    except Unavailable:
        status = None           # a TLS 1.3 server may hang up after the handshake instead
    if status is not None and status not in REFUSED:
        return False, f"https://{host}/ answers {status} without a client certificate: it should refuse"
    try:
        status, _ = _head(host, tls=True, client=client)
    except ssl.SSLError as e:
        return False, f"{host} refuses a client certificate from the lab CA too ({e.__class__.__name__})"
    if not 200 <= status < 300:
        return False, f"https://{host}/ answers {status} with a client certificate from the lab CA: it should let it in"
    return True, "ok"


VERBS = {"served_cert": served_cert, "served_same": served_same, "served_changed": served_changed,
         "served_expired": served_expired, "served_renews": served_renews,
         "served_redirect": served_redirect, "served_hsts": served_hsts, "served_header": served_header,
         "served_mtls": served_mtls}
