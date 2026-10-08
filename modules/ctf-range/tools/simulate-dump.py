#!/usr/bin/env python3
"""Facilitator tool: post one `ctf`/`dump_success` event to achievements, as if
an attacker had just dumped a student's target (plan §8.12's wall of shame).

There is no real attacker-bot persona swarm yet (plan §8.2-8.11) - this is the
stand-in that lets the wall-of-shame wiring (modules/achievements:
store.wall_rows(), GET /achievements/wall) be exercised and demoed before that
swarm exists. Run it from anywhere that can reach the achievements container
(e.g. inside `workshop_terminal` as root, or on the host if you port-forward):

    python3 simulate-dump.py --user student07 --challenge customer-portal

Repeat the call every so often while watching /achievements/wall to see a row
stay LIVE; stop calling it and watch the same row flip to DISCONNECTED after
~90s, then disappear after ~30 min (store.py's WALL_LIVE_WINDOW/WALL_MAX_AGE).
"""
import argparse
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request


def post(url, secret, user, challenge):
    body = json.dumps({"source": "ctf", "event": "dump_success", "user": user, "challenge": challenge}).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Adapter-Signature": sig})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status, resp.read()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", required=True)
    ap.add_argument("--challenge", default="customer-portal")
    ap.add_argument("--url", default=os.environ.get("ACHIEVEMENTS_ADAPTER_URL", "http://achievements:8080/api/adapter"))
    ap.add_argument("--secret", default=os.environ.get("ACHIEVEMENTS_ADAPTER_SECRET", ""))
    args = ap.parse_args()
    if not args.secret:
        print("simulate-dump: no secret given (--secret or ACHIEVEMENTS_ADAPTER_SECRET); "
              "see .env's ACHIEVEMENTS_ADAPTER_SECRET for a running stack", file=sys.stderr)
        return 1
    try:
        status, body = post(args.url, args.secret, args.user, args.challenge)
    except urllib.error.URLError as exc:
        print(f"simulate-dump: could not reach {args.url}: {exc}", file=sys.stderr)
        return 1
    print(f"{status} {body.decode(errors='replace')}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
