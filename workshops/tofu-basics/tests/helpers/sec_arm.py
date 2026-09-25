"""Cross-tenant and token-forgery probes, run INSIDE a student's shell (tests/e2e/60_security.sh feeds it to python3).

    python3 - OTHER_SUBSCRIPTION_ID OTHER_CLIENT_ID FACILITATOR_USERNAME

It uses the calling student's own ARM_* environment (the broker put it there) and prints one `name=value` line per
probe, where value is an HTTP status. It never prints a token or a secret. Standard library only.
"""
import base64
import hashlib
import hmac
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

OTHER_SUB, OTHER_CID, FAC = sys.argv[1:4]
E = os.environ
MGMT = E.get("SEC_MGMT", "https://management.dojo.cloud")  # SEC_MGMT / SEC_LOGIN: an offline check points these at a local server
LOGIN = E.get("SEC_LOGIN", "https://login.dojo.cloud")
CTX = ssl.create_default_context(cafile=E.get("SSL_CERT_FILE") or None)
API = "api-version=2021-04-01"


def call(method, url, headers=None, data=None):
    """-> (status, parsed JSON or {})."""
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    except Exception as e:  # connection problems are their own answer, never a pass
        return "error:" + type(e).__name__, {}
    try:
        return status, json.loads(raw or b"{}")
    except ValueError:
        return status, {}


def token(client_id, secret):
    form = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": client_id,
                                   "client_secret": secret, "scope": MGMT + "/.default"}).encode()
    status, body = call("POST", f"{LOGIN}/{E['ARM_TENANT_ID']}/oauth2/v2.0/token", data=form,
                        headers={"Content-Type": "application/x-www-form-urlencoded"})
    return status, body.get("access_token", "")


def arm(method, path, tok, body=None):
    headers = {"Authorization": "Bearer " + tok} if tok else {}
    data = None
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    return call(method, f"{MGMT}{path}", headers, data)


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def show(name, value):
    print(f"{name}={value}")


own = E["ARM_SUBSCRIPTION_ID"]
status, tok = token(E["ARM_CLIENT_ID"], E["ARM_CLIENT_SECRET"])
show("own_login", status if tok else f"{status}-no-token")
if not tok:
    sys.exit(0)  # nothing below means anything without a valid token of our own

# ---- authorisation: the path subscription must be the token's own ----------------------------------------------------
show("own_subscription", arm("GET", f"/subscriptions/{own}/resourcegroups?{API}", tok)[0])
status, body = arm("GET", f"/subscriptions?{API}", tok)
show("subscriptions_listed", len(body.get("value", [])) if status == 200 else status)
show("other_subscription_read", arm("GET", f"/subscriptions/{OTHER_SUB}/resourcegroups?{API}", tok)[0])
show("other_subscription_write",
     arm("PUT", f"/subscriptions/{OTHER_SUB}/resourcegroups/rg-sectest-probe?{API}", tok,
         {"location": "canadacentral", "tags": {"owner": "sectest", "env": "dev"}})[0])
show("unknown_subscription_read",
     arm("GET", f"/subscriptions/00000000-0000-4000-8000-000000000000/resourcegroups?{API}", tok)[0])

# ---- authentication: no token, bad tokens, forged tokens -------------------------------------------------------------
show("no_bearer", arm("GET", f"/subscriptions/{own}/resourcegroups?{API}", "")[0])
show("garbage_bearer", arm("GET", f"/subscriptions/{own}/resourcegroups?{API}", "not.a.token")[0])
head, claims, sig = tok.split(".")
c = json.loads(unb64(claims))
c["preferred_username"] = FAC
show("payload_swapped_to_facilitator_keeping_signature",
     arm("GET", f"/subscriptions/{OTHER_SUB}/resourcegroups?{API}", f"{head}.{b64(json.dumps(c).encode())}.{sig}")[0])
none_head = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
show("alg_none", arm("GET", f"/subscriptions/{OTHER_SUB}/resourcegroups?{API}",
                     f"{none_head}.{b64(json.dumps(c).encode())}.")[0])
for label, key in (("empty_key", b""), ("guessed_key", b"dojo"), ("client_secret_as_key", E["ARM_CLIENT_SECRET"].encode())):
    signed = f"{head}.{b64(json.dumps(c).encode())}"
    forged = f"{signed}.{b64(hmac.new(key, signed.encode(), hashlib.sha256).digest())}"
    show("token_signed_with_" + label, arm("GET", f"/subscriptions/{OTHER_SUB}/resourcegroups?{API}", forged)[0])

# ---- the token endpoint itself ---------------------------------------------------------------------------------------
show("wrong_credential", token(E["ARM_CLIENT_ID"], "dojo~" + "0" * 40)[0])
show("other_client_with_my_credential", token(OTHER_CID, E["ARM_CLIENT_SECRET"])[0])
show("empty_credential", token(E["ARM_CLIENT_ID"], "")[0])
show("unknown_client", token("00000000-0000-4000-8000-000000000000", E["ARM_CLIENT_SECRET"])[0])
