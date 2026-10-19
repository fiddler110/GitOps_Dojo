#!/usr/bin/env python3
# dojo-summary: put one of your broken targets back to its starting app
"""dojo reset: put one of your running targets back to its starting app.

    dojo reset <target>

Use it when you have broken a box (it is down, or your merge made it worse and you
want a clean start). It replaces the running container with the original, vulnerable
app. Your repo is not touched: your commits are still there, and the next merge to
main rebuilds and redeploys them. To undo a bad merge in the repo, `git revert` it.
Talks to ctf-checker as $USER, proven by the account's own key (~/.config/dojo/ctf-key).
"""
import json
import os
import sys
import urllib.error
import urllib.request

ADDR = os.environ.get("CTF_CHECKER_ADDR", "http://ctf-checker:9200")


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
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 1
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if not user:
        print("dojo reset: could not tell who you are ($USER is unset)", file=sys.stderr)
        return 1
    req = urllib.request.Request(f"{ADDR}/reset", method="POST",
                                 data=json.dumps({"user": user, "key": own_key(), "target": argv[0]}).encode(),
                                 headers={"Content-Type": "application/json"})
    print(f"dojo reset: redeploying {argv[0]}; this takes a couple of minutes...", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            doc = json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
            doc = json.load(exc)
        except Exception:
            doc = {}
        print(f"dojo reset: {doc.get('message') or doc.get('error') or exc.reason}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"dojo reset: could not reach the checker ({exc})", file=sys.stderr)
        return 1
    print(f"{argv[0]}: back to the starting app. Run `dojo check {argv[0]}` to confirm; "
          "your repo is unchanged, so the next merge to main redeploys your code.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
