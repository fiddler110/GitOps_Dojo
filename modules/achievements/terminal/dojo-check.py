#!/usr/bin/env python3
"""dojo-check: the student's window on their achievements.

  dojo-check                 your score, rank and completion
  dojo-check hint ID         the next hint for a challenge (each one costs points)
  dojo-check reveal ID       the answer, once both hints are used (scores 0)
  dojo-check ID              check a challenge, e.g. dojo-check c1 (a wrong answer costs nothing)
  dojo-challenge start ID    make your own challenge repo and clone it into ~/lab (safe to repeat)
  dojo-challenge reset ID    throw it away and start again from a fresh copy (as often as you like;
                             hints already used stay used)
  dojo-check --echo          print new unlocks in colour (the prompt hook calls this)
  dojo-check --shell         send one finished command to the service (the prompt hook
                             calls this in the background, with DOJO_SH_* in its environment)

This file holds no answers and no checks: the achievements service holds the catalog and does
the checking. It proves who you are with your own Forgejo token (the one in ~/.git-credentials,
which the service confirms with Forgejo) and shows the service which client this is, so an
edited copy is noticed. Stdlib only.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("ACHIEVEMENTS_URL", "http://achievements:8080")
HOST = "git-server:3000"
HOME = os.path.expanduser("~")
SEEN = os.path.join(HOME, ".dojo-achievements-seen")


def token():
    try:
        with open(os.path.join(HOME, ".git-credentials")) as f:
            for line in f:
                line = line.strip().replace("%3a", ":").replace("%3A", ":")  # git may percent-encode the port
                if line.startswith("http://") and line.endswith("@" + HOST):
                    return line[len("http://"):-len("@" + HOST)].split(":", 1)[1]
    except (OSError, IndexError):
        pass
    return None


def my_hash():
    with open(os.path.realpath(__file__), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def call(method, path, body=None, timeout=10):
    """(status, parsed JSON or {}); status 0 when the service can't be reached."""
    tok = token()
    if not tok:
        return 0, {"error": "no Forgejo token in ~/.git-credentials"}
    headers = {"Authorization": "token " + tok, "X-Dojo-Client": my_hash(), "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError):
        return 0, {"error": "the achievements service isn't reachable"}


def paint(t):
    """One toast as a banner: a coloured label block, the title, the joke behind a coloured bar."""
    pts = t.get("points") or 0
    if t.get("kind") == "summary":
        label, bg = "ACHIEVEMENTS", "44"
    elif pts < 0:
        label, bg = "BUSTED", "41"
    elif t.get("kind") == "funny":
        label, bg = "MOMENT", "45"
    else:
        label, bg = "ACHIEVEMENT UNLOCKED", "44"
    tag = ("+%d" % pts) if pts > 0 else (str(pts) if pts < 0 else "")
    out = "\n\033[1;97;%sm \u2605 %s \033[0m \033[1;97m%s\033[0m" % (bg, label, t.get("title", ""))
    if tag:
        out += " \033[1;30;43m %s \033[0m" % tag
    if t.get("joke"):
        out += "\n\033[%sm \033[0m \033[3;37m%s\033[0m" % (bg, t["joke"])
    return out + "\n"


def echo():
    if not sys.stdout.isatty():
        return 0
    try:
        with open(SEEN) as f:
            after = int(f.read().strip() or 0)
    except (OSError, ValueError):
        after = 0
    status, doc = call("GET", "/api/toasts?surface=terminal&after=%d" % after, timeout=1)
    if status != 200:
        return 0
    toasts = doc.get("toasts") or []
    for t in toasts:
        print(paint(t))
    top = max([t.get("seq", 0) for t in toasts] or [after])
    if top > after:
        try:
            with open(SEEN, "w") as f:
                f.write(str(top))
        except OSError:
            pass
    return 0


def shell():
    """Report one command line (from the prompt hook's DOJO_SH_* variables). Silent."""
    env = os.environ
    cmd = env.get("DOJO_SH_CMD", "")
    try:
        code = int(env.get("DOJO_SH_EXIT", ""))
    except ValueError:
        return 0
    if not cmd.strip():
        return 0
    body = {"cmd": cmd[:1000], "exit": code,
            "branch": env.get("DOJO_SH_BRANCH", ""), "branch_before": env.get("DOJO_SH_BRANCH_BEFORE", ""),
            "in_repo": env.get("DOJO_SH_IN_REPO") == "1", "merging": env.get("DOJO_SH_MERGING") == "1",
            "merging_after": env.get("DOJO_SH_MERGING_AFTER") == "1"}
    call("POST", "/api/shell", body, timeout=3)
    return 0


def status():
    code, me = call("GET", "/api/me")
    if code != 200:
        return fail(code, me)
    c = me["completion"]
    print("%s  %d points, rank %d of %d" % (me["name"], me["score"], me["rank"], me["of"]))
    print("Completion: %d of %d steps (%d%%), %d needed%s" % (c["done"], c["total"], c["percent"], c["needed"],
                                                          " -- Workshop complete!" if c["complete"] else ""))
    for ch in me["challenges"]:
        print("  %-9s %-28s %s" % (ch["id"], ch["title"], "done" if ch["done"] else "worth %d" % ch["worth"]))
    return 0


def challenge_id(arg):
    """'1' or 'c1' -> 'c1'; 'capstone' stays."""
    return "c" + arg if arg.isdigit() else arg


def check(cid):
    code, doc = call("POST", "/api/check", {"challenge": challenge_id(cid)}, timeout=60)
    if code != 200:
        return fail(code, doc)
    if doc.get("already"):
        print("\033[1;36mAlready cleared.\033[0m Points are earned once.")
        return 0
    if doc.get("passed"):
        print("\033[1;32mPassed!\033[0m %s  +%d points" % (challenge_id(cid), doc.get("points") or 0))
        return 0
    print("\033[1;33mNot yet:\033[0m %s" % doc.get("message", ""))
    print("(Checking again is free. Stuck? dojo-check hint %s)" % challenge_id(cid))
    return 1


def challenge(action, cid):
    """Build (or rebuild) your challenge repo on the server, then clone it into ~/lab."""
    cid = challenge_id(cid)
    code, doc = call("POST", "/api/challenge", {"challenge": cid, "action": action}, timeout=120)
    if code != 200:
        return fail(code, doc)
    repo, url = doc.get("repo", ""), doc.get("clone_url", "")
    name = repo.rsplit("/", 1)[-1]
    if not name or "/" in name or name.startswith(".") or not url.startswith("http://" + HOST + "/"):
        return fail(0, {"error": "the service sent an odd repo name"})
    lab = os.path.join(HOME, "lab")
    dest = os.path.join(lab, name)
    print("\033[1;36m%s: %s\033[0m" % (cid, doc.get("title", "")))
    print("Goal: %s" % doc.get("goal", ""))
    if doc.get("constraints"):
        print("Rules: %s" % doc["constraints"])
    if action == "reset" and os.path.isdir(dest):
        shutil.rmtree(dest)
        print("Removed your old copy at %s" % dest)
    if os.path.isdir(os.path.join(dest, ".git")):
        print("Your repo %s is already in %s (dojo-challenge reset %s for a fresh one)." % (repo, dest, cid))
    else:
        os.makedirs(lab, exist_ok=True)
        if subprocess.call(["git", "clone", "-q", url, dest]) != 0:
            return fail(0, {"error": "git clone %s failed; the repo is there, try: git clone %s" % (url, url)})
        print("Cloned %s into %s" % (repo, dest))
    if doc.get("done"):
        print("(You already cleared %s; practising again scores nothing new.)" % cid)
    print("When you think you're done: dojo-check %s" % cid)
    return 0


def fail(code, doc):
    print("dojo-check: %s" % (doc.get("error") or "HTTP %s" % code), file=sys.stderr)
    return 1


def main(argv):
    if os.path.basename(sys.argv[0]) == "dojo-challenge":
        if len(argv) == 2 and argv[0] in ("start", "reset"):
            return challenge(argv[0], argv[1])
        print("usage: dojo-challenge start|reset ID   (e.g. dojo-challenge start c1)", file=sys.stderr)
        return 2
    if argv[:1] == ["--echo"]:
        return echo()
    if argv[:1] == ["--shell"]:
        return shell()
    if not argv or argv == ["status"]:
        return status()
    if argv[0] in ("hint", "reveal") and len(argv) == 2:
        code, doc = call("POST", "/api/" + argv[0], {"challenge": challenge_id(argv[1])})
        if code != 200:
            return fail(code, doc)
        if argv[0] == "hint":
            print("Hint %d: %s" % (doc["n"], doc["text"]))
            if doc.get("cost"):
                print("(that hint cost %d points off this challenge)" % doc["cost"])
        else:
            print("Answer: %s" % doc["answer"])
        return 0
    if len(argv) == 1 and not argv[0].startswith("-"):
        return check(argv[0])
    print(__doc__.strip().split("\n\n")[0], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
