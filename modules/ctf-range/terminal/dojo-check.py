#!/usr/bin/env python3
# dojo-summary: ask the platform whether your targets are still exploitable
"""dojo check: ask the platform whether your targets are still exploitable.

    dojo check              all three targets
    dojo check <target>     one target

Talks to ctf-checker on workshop_lab as $USER, proven by the account's own
key (~/.config/dojo/ctf-key). Always exits 0 unless it could not ask.
"""
import json
import os
import sys
import urllib.error
import urllib.request

ADDR = os.environ.get("CTF_CHECKER_ADDR", "http://ctf-checker:9200")
SEVERITY = {"customer-portal": "HIGH", "policy-bypass": "MEDIUM", "leaky-config": "LOW"}
WORDS = {"exploitable": "still exploitable", "contained": "contained",
         "broke-normal-use": "broke normal use", "unreachable": "unreachable"}


def own_key():
    """This account's ctf key (account.d/57-ctf-key.sh writes it; "" if missing, which the
    service refuses). CTF_KEY_FILE overrides the path, so root can act for a student."""
    path = os.environ.get("CTF_KEY_FILE") or os.path.expanduser("~/.config/dojo/ctf-key")
    try:
        with open(path, encoding="ascii") as fh:
            return fh.read().strip()
    except (OSError, ValueError):
        return ""


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if not user:
        print("dojo check: could not tell who you are ($USER is unset)", file=sys.stderr)
        return 1
    body = {"user": user, "key": own_key()}
    if argv:
        body["target"] = argv[0]
    req = urllib.request.Request(f"{ADDR}/check", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            doc = json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
            msg = json.load(exc).get("error", exc.reason)
        except Exception:
            msg = exc.reason
        print(f"dojo check: {msg}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"dojo check: could not reach the checker ({exc})", file=sys.stderr)
        return 1
    for r in doc.get("results", []):
        t = r.get("target", "?")
        line = f"{t:<18}{SEVERITY.get(t, ''):<8}{WORDS.get(r.get('verdict'), r.get('verdict', '?'))}"
        if r.get("note"):
            line += f"  ({r['note']})"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
