"""cert-trust-bypass — CTF target 3 (plan docs/CTF-WORKSHOP-PLAN.md §7.3,
CTF-1 "Access and identity", ties `cert-autorenewal`). An internal API that's
*meant* to require a trusted client certificate but only checks that the
presented PEM parses as a well-formed X.509 certificate and reads its
Subject CN — it never checks who signed it (any self-signed cert passes)
and never checks expiry. "It has a cert" is treated as "it has a *valid*
cert."

Env:
  CTF_FLAG      this slot's flag value (plan §5).
  PORT          listen port (default 5000).

**Why this is plain HTTP, not real mTLS:** this attack-ladder target gets one
published TCP port and the plan's bug is explicitly an application-layer
check ("skips chain/revocation checks" — a code bug, not a TLS handshake
setting). Modeling it as "POST your client certificate PEM to an internal
endpoint" tests the exact same mechanic (parse a real X.509 cert, check who
signed it, check its expiry) without needing a full mTLS handshake and a
trust store wired through this one port. A student generates a cert with
plain `openssl req -x509 ...` (already a terminal tool for `cert-autorenewal`)
and POSTs it — no special client needed.
"""
import os
import socket
import tempfile
import threading

from flask import Flask, Response, request

import ssl as _ssl_module  # noqa: F401  (imported for the module itself)
from ssl import _ssl  # the stdlib's own PEM/X.509 decoder, no extra dependency

app = Flask(__name__)

FLAG = os.environ.get("CTF_FLAG", "flag{cert-trust-bypass-dev0000000000}")

# The identity the privileged endpoint requires. A real deployment would also
# require the cert to chain to this CA and not be expired — see the comment
# in identify() for exactly what that fix looks like.
REQUIRED_CN = "ops-internal"


def decode_cert(pem_bytes):
    """Parse a PEM certificate and return its decoded fields (subject,
    notAfter, ...), the same shape ssl.SSLSocket.getpeercert() returns for a
    real TLS peer. Returns None if it doesn't parse as a certificate at all."""
    with tempfile.NamedTemporaryFile(suffix=".pem", mode="wb", delete=True) as f:
        f.write(pem_bytes)
        f.flush()
        try:
            return _ssl._test_decode_cert(f.name)
        except Exception:
            return None


def common_name(decoded):
    for rdn in decoded.get("subject", ()):
        for key, value in rdn:
            if key == "commonName":
                return value
    return None


# -- Presentation only (no behavior): each target wears the look of its own
# scenario. The stylesheet is a separate route so `curl` output stays readable.
_CSS = """
:root{--bg:#07110d;--card:#0c1a14;--ink:#d1fae5;--mute:#6ee7b7aa;--acc:#34d399;--line:#14382a}
*{box-sizing:border-box}body{margin:0;font:15px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--bg);color:var(--ink);min-height:100vh}
header{padding:.9rem 1.5rem;display:flex;align-items:center;gap:.7rem;border-bottom:1px solid var(--line)}
.logo{border:1px solid var(--acc);color:var(--acc);border-radius:4px;padding:0 .45rem;font-weight:700}.brand{letter-spacing:.08em;text-transform:uppercase;font-size:.8rem;color:var(--mute)}
main{max-width:640px;margin:2.5rem auto;padding:1.6rem;background:var(--card);border:1px solid var(--line);border-radius:10px}
h1{font-size:1.2rem;margin:0 0 1rem;color:var(--acc)}h1::before{content:"$ ";opacity:.6}
p{margin:.5rem 0;word-break:break-word}code{background:#0a2a1e;border:1px solid var(--line);border-radius:4px;padding:.05rem .35rem;color:var(--acc)}
"""


@app.get("/assets/theme.css")
def theme_css():
    return Response(_CSS, mimetype="text/css")


def _page(title, body):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title} &middot; Zero-Trust API Gateway</title>"
        '<link rel="stylesheet" href="/assets/theme.css"></head><body>'
        '<header><span class="logo">&#9919;</span><span class="brand">Zero-Trust API Gateway</span></header>'
        f'<main>{body}</main></body></html>'
    )


@app.get("/")
def index():
    return _page("Internal API", (
        "<h1>Internal API</h1>"
        "<p>POST a client certificate PEM to /internal/ops to authenticate.</p>"
        "<p>Endpoint: <code>POST /internal/ops</code> &mdash; mutual-auth required.</p>"
    ))


@app.post("/internal/ops")
def internal_ops():
    pem = request.get_data()
    decoded = decode_cert(pem)
    if decoded is None:
        return _page("Rejected", "<p>Not a certificate.</p>"), 400

    # THE BUG: only the Subject CN is checked. A correct implementation
    # also has to verify:
    #   1. the cert chains to a trusted CA (e.g. via
    #      ssl.SSLContext.load_verify_locations(cafile=TRUSTED_CA_PEM) and
    #      actually performing a TLS/cert-chain verification — not just
    #      parsing the bytes), and
    #   2. the cert hasn't expired:
    #        from datetime import datetime
    #        not_after = datetime.strptime(decoded["notAfter"], "%b %d %H:%M:%S %Y %Z")
    #        if datetime.utcnow() > not_after: reject
    # Neither check exists below — any self-signed, expired cert with the
    # right CN is accepted as proof of identity.
    cn = common_name(decoded)
    if cn != REQUIRED_CN:
        return _page("Rejected", "<p>Wrong identity.</p>"), 403

    return _page("Authenticated", f"<p>Welcome, {cn}. {FLAG}</p>")


# -- Decoy listener (plan §7.3's nmap primer: a student scans their box and
# finds more than the one port they'll actually use, same as a HackTheBox
# box) -----------------------------------------------------------------
# NOT a real sshd: every slot container drops every Linux capability and
# runs read-only as a non-root user (docker_api.py's build_create_request()),
# which makes a genuine sshd impossible here at all (host keys, privilege
# separation and setuid-per-connection all need root). This speaks just
# enough of the real SSH-2.0 handshake to fingerprint correctly under
# `nmap -sV`, then closes — there is no key exchange and no account behind
# it. ctf-controller's AttackManager always reserves this port
# (DECOY_SSH_CONTAINER_PORT); it has nothing to do with this target's bug.
def _decoy_ssh_handler(conn):
    try:
        conn.sendall(b"SSH-2.0-OpenSSH_9.7p1 Debian-7\r\n")
        conn.recv(256)
    except OSError:
        pass
    finally:
        conn.close()


def _start_decoy(port, handler):
    def _accept_loop():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(16)
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                continue
            threading.Thread(target=handler, args=(conn,), daemon=True).start()
    threading.Thread(target=_accept_loop, daemon=True).start()


_start_decoy(2222, _decoy_ssh_handler)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
