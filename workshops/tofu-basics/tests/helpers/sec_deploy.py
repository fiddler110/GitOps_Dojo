"""Deploys, or deletes, one valid container group as the calling student, straight through ARM (run inside their shell).

    python3 - up|down

`up` makes rg-sectest and ci-sectest (policy-clean: 0.25 vCPU, 0.125 GB, dojo/hello:1.0); `down` deletes the resource group.
It exists so the security area has a real container to inspect. Prints `deploy_ok=yes|no deploy_status=` / `delete_status=` and nothing secret.
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

E = os.environ
CTX = ssl.create_default_context(cafile=E.get("SSL_CERT_FILE") or None)
MGMT = E.get("SEC_MGMT", "https://management.dojo.cloud")  # SEC_MGMT / SEC_LOGIN: an offline check points these at a local server
LOGIN = E.get("SEC_LOGIN", "https://login.dojo.cloud")
SUB, RG, CG = E["ARM_SUBSCRIPTION_ID"], "rg-sectest", "ci-sectest"
TAGS = {"owner": E.get("TF_VAR_owner", "sectest"), "env": "dev"}


def call(method, url, headers, data=None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120, context=CTX) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return "error:" + type(e).__name__


form = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": E["ARM_CLIENT_ID"],
                               "client_secret": E["ARM_CLIENT_SECRET"], "scope": MGMT + "/.default"}).encode()
req = urllib.request.Request(f"{LOGIN}/{E['ARM_TENANT_ID']}/oauth2/v2.0/token", data=form, method="POST")
with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
    tok = json.loads(r.read())["access_token"]
H = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
rg_url = f"{MGMT}/subscriptions/{SUB}/resourcegroups/{RG}"
cg_url = f"{rg_url}/providers/Microsoft.ContainerInstance/containerGroups/{CG}"

if sys.argv[1] == "up":
    st = call("PUT", f"{rg_url}?api-version=2021-04-01", H, json.dumps({"location": "canadacentral", "tags": TAGS}).encode())
    body = {"location": "canadacentral", "tags": TAGS, "properties": {
        "osType": "Linux",
        "containers": [{"name": "hello", "properties": {
            "image": "dojo/hello:1.0", "ports": [{"port": 80}],
            "environmentVariables": [{"name": "MESSAGE", "value": "security check"}],
            "resources": {"requests": {"cpu": 0.25, "memoryInGB": 0.125}}}}],
        "ipAddress": {"type": "Public", "ports": [{"port": 80}], "dnsNameLabel": f"sectest-{TAGS['owner']}"}}}
    st2 = call("PUT", f"{cg_url}?api-version=2023-05-01", H, json.dumps(body).encode())
    print("deploy_ok=" + ("yes" if st in (200, 201, 202) and st2 in (200, 201, 202) else "no"), f"deploy_status={st}/{st2}")
else:
    st = call("DELETE", rg_url + "?api-version=2021-04-01", H)
    print("delete_ok=" + ("yes" if st in (200, 202, 204) else "no"), f"delete_status={st}")
    time.sleep(1)
