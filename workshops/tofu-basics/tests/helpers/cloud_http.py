#!/usr/bin/env python3
"""One HTTP request against cloud-api's plain-HTTP port, made from INSIDE the cloud-api container.

Why it runs there: the portal API (PLAN 5.6) trusts `X-Auth-User` only together with `X-Gateway-Token`, which
only Caddy normally sets. This container already has the token in its own environment, so the test scripts
never have to read, pass or log it: they feed this file to `python3 -` over stdin and get one JSON line back.
It talks to 127.0.0.1, so it does NOT exercise the gateway (Caddy, sessions); that route was tested in P5.

    podman exec -i workshop_cloud_api python3 - METHOD PATH [USER] [BODY_JSON] < cloud_http.py

USER  '-'            no identity headers (readyz, healthz, site pages, static portal files)
      '@facilitator' the facilitator: $FACILITATOR_USERNAME of this container (default 'root')
      anything else  that username (a roster member, e.g. student01)

Prints exactly one line of JSON and exits 0 whatever the HTTP status was:
    {"status": <int, 0 = could not connect>, "ms": <float>, "body": <parsed JSON, or the text if not JSON>}
The token is never printed and never returned.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request


def main(argv):
    if len(argv) < 2:
        print(json.dumps({"status": 0, "ms": 0, "body": "usage: METHOD PATH [USER] [BODY_JSON]"}))
        return 0
    method, path = argv[0].upper(), argv[1]
    user = argv[2] if len(argv) > 2 else "-"
    body = argv[3] if len(argv) > 3 else None
    if user == "@facilitator":
        user = os.environ.get("FACILITATOR_USERNAME", "root")

    port = os.environ.get("CLOUD_HTTP_PORT", "8080")
    url = f"http://127.0.0.1:{port}{path}"
    headers = {}
    if user != "-":
        headers["X-Auth-User"] = user
        headers["X-Gateway-Token"] = os.environ.get("GATEWAY_TOKEN", "")
    data = None
    if body is not None:
        data = body.encode()
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    started = time.monotonic()
    status, raw = 0, b""
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    except (urllib.error.URLError, OSError) as exc:
        status, raw = 0, str(exc).encode()
    ms = round((time.monotonic() - started) * 1000, 1)

    text = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text) if text.strip() else None
    except ValueError:
        parsed = text
    print(json.dumps({"status": status, "ms": ms, "body": parsed}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
