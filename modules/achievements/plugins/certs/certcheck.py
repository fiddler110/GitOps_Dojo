"""certs verifier verbs (see verifiers.json). Stdlib only. Every verb is `fn(api, args, ctx) -> (passed, message)`.
`api` is the Forgejo client the runner passes to every verb; these ignore it."""
import os
import socket
import ssl


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


VERBS = {"served_cert": served_cert, "served_same": served_same}
