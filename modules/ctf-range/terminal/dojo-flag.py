#!/usr/bin/env python3
# dojo-summary: submit a flag you found: dojo flag 'flag{...}'
"""dojo flag: submit a CTF flag (plan §5).

    dojo flag 'flag{...}'

The flag names its own challenge (flag{<challenge>-<hex>}), so the flag is all
you need. The older `dojo flag submit <challenge> <flag>` still works.

Talks to the ctf-flags service on workshop_lab, over the account's own uid
(ctf-flags trusts `user` only as far as crediting that account's own
achievements - see ctf-flags/service.py's header). A wrong flag never raises;
it just says so.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

CTF_FLAGS_URL = os.environ.get("CTF_FLAGS_ADDR", "http://ctf-flags:8080")


FLAG_RE = re.compile(r"^flag\{([a-z0-9][a-z0-9-]*?)-(?:[0-9a-f]{16}|dev-.+)\}$")
USAGE = "usage: dojo flag 'flag{...}'   (quote it; paste the whole flag, braces included)"


def submit(challenge, flag):
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if not user:
        print("dojo flag: could not tell who you are ($USER is unset)", file=sys.stderr)
        return 1
    body = json.dumps({"user": user, "challenge": challenge, "flag": flag}).encode()
    req = urllib.request.Request(f"{CTF_FLAGS_URL}/submit", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            doc = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"dojo flag: could not reach the flag service ({exc})", file=sys.stderr)
        return 1
    if doc.get("ok"):
        print(f"Correct! {challenge} is solved.")
        return 0
    print("That's not the right flag for this challenge. Keep looking.")
    return 1


def main():
    args = sys.argv[1:]
    if args[:1] == ["submit"]:
        args = args[1:]
    if args in ([], ["-h"], ["--help"]):
        print(__doc__.strip())
        sys.exit(0 if args else 2)
    if len(args) == 1:
        flag = args[0].strip()
        m = FLAG_RE.match(flag)
        if not m:
            print(f"dojo flag: that doesn't look like a flag.\n{USAGE}", file=sys.stderr)
            sys.exit(2)
        challenge = m.group(1)
    elif len(args) == 2:
        challenge, flag = args
    else:
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    sys.exit(submit(challenge, flag))


if __name__ == "__main__":
    main()
