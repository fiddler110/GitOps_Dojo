#!/usr/bin/env python3
"""dojo-flag: submit a CTF flag (plan §5).

    dojo-flag submit <challenge> <flag>

Talks to the ctf-flags service on workshop_lab, over the account's own uid
(ctf-flags trusts `user` only as far as crediting that account's own
achievements - see ctf-flags/service.py's header). A wrong flag never raises;
it just says so.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

CTF_FLAGS_URL = os.environ.get("CTF_FLAGS_ADDR", "http://ctf-flags:8080")


def submit(challenge, flag):
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if not user:
        print("dojo-flag: could not tell who you are ($USER is unset)", file=sys.stderr)
        return 1
    body = json.dumps({"user": user, "challenge": challenge, "flag": flag}).encode()
    req = urllib.request.Request(f"{CTF_FLAGS_URL}/submit", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            doc = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"dojo-flag: could not reach the flag service ({exc})", file=sys.stderr)
        return 1
    if doc.get("ok"):
        print(f"Correct! {challenge} is solved.")
        return 0
    print("That's not the right flag for this challenge. Keep looking.")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit", help="submit a flag for a challenge")
    s.add_argument("challenge")
    s.add_argument("flag")
    args = ap.parse_args()
    sys.exit(submit(args.challenge, args.flag))


if __name__ == "__main__":
    main()
