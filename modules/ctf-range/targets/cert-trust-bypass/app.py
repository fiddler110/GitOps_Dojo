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
import tempfile

from flask import Flask, request

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


@app.get("/")
def index():
    return (
        "<h1>Internal API</h1>"
        "<p>POST a client certificate PEM to /internal/ops to authenticate.</p>"
    )


@app.post("/internal/ops")
def internal_ops():
    pem = request.get_data()
    decoded = decode_cert(pem)
    if decoded is None:
        return "<p>Not a certificate.</p>", 400

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
        return "<p>Wrong identity.</p>", 403

    return f"<p>Welcome, {cn}. {FLAG}</p>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
