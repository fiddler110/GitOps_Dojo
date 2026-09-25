#!/usr/bin/env python3
"""bao-audit: read your namespace's audit trail (the openbao-audit service).

    bao-audit                       the last 30 requests in students/$USER
    bao-audit --accessor ACC        what one token did (and the tokens it made)
    bao-audit --path team/          requests under a path
    bao-audit -n 100 --json         more, as JSON
    bao-audit --all                 with the CLI's own mount look-ups

Your own sign-in token (~/.vault-token) proves you administer the namespace
(--ns, default $BAO_NAMESPACE, else students/$USER). Times are UTC.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

AUDIT_URL = os.environ.get("BAO_AUDIT_ADDR", "http://openbao-audit:8080")


def token():
    """Your own sign-in token first (~/.vault-token, from openbao-login), so a
    BAO_TOKEN exported for something else doesn't stand in for you."""
    try:
        with open(os.path.expanduser("~/.vault-token")) as f:
            saved = f.read().strip()
    except OSError:
        saved = ""
    return saved or os.environ.get("BAO_TOKEN") or os.environ.get("VAULT_TOKEN") or ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ns", default=os.environ.get("BAO_NAMESPACE") or f"students/{os.environ.get('USER', '')}")
    ap.add_argument("--accessor")
    ap.add_argument("--path")
    ap.add_argument("-n", type=int, default=30, help="how many (default 30)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="also the CLI's own look-ups (sys/internal/ui/mounts/...) before each kv command")
    a = ap.parse_args()
    q = {"ns": a.ns, "limit": a.n}
    if a.accessor:
        q["accessor"] = a.accessor
    if a.path:
        q["path"] = a.path
    req = urllib.request.Request(f"{AUDIT_URL}/entries?{urllib.parse.urlencode(q)}",
                                 headers={"X-Vault-Token": token()})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            doc = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            why = json.load(e).get("error")
        except ValueError:
            why = e.reason
        sys.exit(f"bao-audit: {why}")
    except OSError as e:
        sys.exit(f"bao-audit: can't reach {AUDIT_URL}: {e}")
    entries = doc["entries"]
    if not a.all:
        entries = [e for e in entries if not (e.get("path") or "").startswith("sys/internal/ui/mounts/")]
    if a.json:
        json.dump(entries, sys.stdout, indent=2)
        print()
        return
    if not entries:
        print(f"No audit entries in {doc['namespace']} match.")
        return
    print(f"{'TIME (UTC)':19}  {'OP':6}  {'PATH':26}  {'ACCESSOR':31}  {'WHO':20}  RESULT")
    for e in entries:
        result = "denied" if "permission denied" in (e.get("error") or "") else ("error" if e.get("error") else "ok")
        if e.get("created_accessor"):
            result += f", made token {e['created_accessor']}"
        print(f"{(e.get('time') or '')[:19].replace('T', ' '):19}  {e.get('operation') or '':6}  "
              f"{e.get('path') or '':26}  {e.get('accessor') or '-':31}  "
              f"{(e.get('display_name') or '-')[:20]:20}  {result}")


if __name__ == "__main__":
    main()
