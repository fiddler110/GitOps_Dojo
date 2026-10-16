#!/usr/bin/env python3
# dojo-summary(check): your score, and check a challenge: dojo check c1  (dojo check hint c1 for a hint)
# dojo-summary(challenge): start or reset your own challenge repo: dojo challenge start c1
"""dojo check / dojo challenge: the student's window on their achievements.

  dojo check                 your score, rank and completion
  dojo check hint ID         the next hint for a challenge (each one costs points)
  dojo check reveal ID       the answer, once both hints are used (scores 0)
  dojo check ID              check a challenge, e.g. dojo check c1 (a wrong answer costs nothing)
  dojo challenge start ID    make your own challenge repo and clone it into ~/lab (safe to repeat)
  dojo challenge reset ID    throw it away and start again from a fresh copy (as often as you like;
                             hints already used stay used)
  dojo-check --echo          print new unlocks in colour (the prompt hook calls this)
  dojo-check --shell         send one finished command to the service (the prompt hook
                             calls this in the background, with DOJO_SH_* in its environment)

The older names dojo-check ... and dojo-challenge ... still work.

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
            "merging_after": env.get("DOJO_SH_MERGING_AFTER") == "1",
            "out": env.get("DOJO_SH_OUT", "")[-4000:]}
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
    if doc.get("step"):
        print("\033[1;32mHalfway:\033[0m %s" % doc.get("message", ""))
        return 1
    print("\033[1;33mNot yet:\033[0m %s" % doc.get("message", ""))
    print("(Checking again is free. Stuck? dojo check hint %s)" % challenge_id(cid))
    return 1


def split_rules(text):
    """Split a constraints string on '; ' (not inside backticks) so each rule is its own bullet."""
    parts, cur = [], ""
    for chunk in text.split("; "):
        cur = cur + "; " + chunk if cur else chunk
        if cur.count("`") % 2 == 0:
            parts.append(cur.strip())
            cur = ""
    if cur:
        parts.append(cur.strip())
    return [x.rstrip(".") for x in parts if x]


def brief_markdown(cid, doc, dest):
    """The challenge as a Markdown brief: goal, rules, where to work, how to finish."""
    head = "# %s: %s" % ("Capstone" if cid == "capstone" else "Challenge " + cid, doc.get("title", ""))
    out = [head, "", "## Goal", "", doc.get("goal", "")]
    if doc.get("constraints"):
        out += ["", "## End result", ""] + ["- " + r for r in split_rules(doc["constraints"])]
    out += ["", "## Where to work", ""]
    out.append("Your repo is cloned at `%s`:" % dest.replace(HOME, "~", 1) if dest
               else "This one works in your own lab space: start where the lab left you.")
    if dest:
        out += ["", "```bash", "cd " + dest.replace(HOME, "~", 1), "```", "",
                "Other branches on the server show up as `origin/<name>` (`git branch -a`); "
                "`git fetch origin` refreshes them and `git switch <name>` makes a local copy."]
    out += ["", "## When you're done", "", "```bash", "dojo check " + cid, "```", "",
            "Stuck? `dojo check hint %s` (each hint costs points). Checking again is free." % cid,
            "", "## Start over", "", "```bash", "dojo challenge reset " + cid, "```", "",
            "That deletes your repo copy (and any uncommitted work) and gives you a fresh one. Hints already used stay used."]
    if doc.get("done"):
        out += ["", "> You already cleared %s; practising again scores nothing new." % cid]
    return "\n".join(out) + "\n"


def show_brief(cid, markdown):
    """Save the brief to ~/ (challenge-c2.md, capstone.md) and show it with glow; plain text if glow can't."""
    path = os.path.join(HOME, "capstone.md" if cid == "capstone" else "challenge-%s.md" % cid)
    try:
        with open(path, "w") as f:
            f.write(markdown)
    except OSError:
        path = None
    shown = False
    if sys.stdout.isatty():
        width = min(max(os.get_terminal_size().columns - 4, 40), 100)
        # Capture glow's output instead of letting it write to the tty: on a tty it asks the terminal for its
        # colours and waits, which web terminals don't always answer.
        try:
            r = subprocess.run(["glow", "-s", "dark", "-w", str(width), "-"], input=markdown, text=True,
                               capture_output=True, timeout=10, env=dict(os.environ, CLICOLOR_FORCE="1"))
            if r.returncode == 0 and r.stdout.strip():
                print("\n".join(line.rstrip() for line in r.stdout.splitlines()))
                shown = True
        except (OSError, subprocess.SubprocessError):
            pass
    if not shown:
        print(markdown)
    if path:
        print("Saved to %s  (read it again any time: glow -p %s)" % (path.replace(HOME, "~", 1), path.replace(HOME, "~", 1)))


def challenge(action, cid):
    """Build (or rebuild) your challenge repo on the server, then clone it into ~/lab."""
    cid = challenge_id(cid)
    os.chdir(HOME)  # `reset` removes the old copy, which may be the folder this was run from
    code, doc = call("POST", "/api/challenge", {"challenge": cid, "action": action}, timeout=120)
    if code != 200:
        return fail(code, doc)
    repo, url = doc.get("repo") or "", doc.get("clone_url") or ""
    if not repo:
        show_brief(cid, brief_markdown(cid, doc, None))
        return 0
    name = repo.rsplit("/", 1)[-1]
    if not name or "/" in name or name.startswith(".") or not url.startswith("http://" + HOST + "/"):
        return fail(0, {"error": "the service sent an odd repo name"})
    lab = os.path.join(HOME, "lab")
    dest = os.path.join(lab, name)
    if action == "reset" and os.path.isdir(dest):
        shutil.rmtree(dest)
        print("Removed your old copy at %s" % dest)
    if os.path.isdir(os.path.join(dest, ".git")):
        print("Your repo %s is already in %s (dojo challenge reset %s for a fresh one)." % (repo, dest, cid))
    else:
        os.makedirs(lab, exist_ok=True)
        if subprocess.call(["git", "clone", "-q", url, dest]) != 0:
            return fail(0, {"error": "git clone %s failed; the repo is there, try: git clone %s" % (url, url)})
        print("Cloned %s into %s" % (repo, dest))
    show_brief(cid, brief_markdown(cid, doc, dest))
    return 0


def fail(code, doc):
    print("dojo %s: %s" % (name(), doc.get("error") or "HTTP %s" % code), file=sys.stderr)
    return 1


def name():
    """Which command this is: `dojo challenge` sets DOJO_SUBCOMMAND; the old links are named after themselves."""
    n = os.environ.get("DOJO_SUBCOMMAND") or os.path.basename(sys.argv[0])
    return "challenge" if n in ("challenge", "dojo-challenge") else "check"


USAGE_CHECK = """dojo check                 your score, rank and completion
dojo check ID              check a challenge, e.g. dojo check c1 (a wrong answer costs nothing)
dojo check hint ID         the next hint for a challenge (each one costs points)
dojo check reveal ID       the answer, once both hints are used (scores 0)"""
USAGE_CHALLENGE = """dojo challenge start ID    make your own challenge repo and clone it into ~/lab (safe to repeat)
dojo challenge reset ID    throw it away and start again from a fresh copy (as often as you like;
                           hints already used stay used)
Then work in the repo and run: dojo check ID"""


def main(argv):
    if argv[:1] == ["--echo"]:
        return echo()
    if argv[:1] == ["--shell"]:
        return shell()
    if name() == "challenge":
        if argv[:1] in (["-h"], ["--help"]):
            print(USAGE_CHALLENGE)
            return 0
        if len(argv) == 2 and argv[0] in ("start", "reset"):
            return challenge(argv[0], argv[1])
        print(USAGE_CHALLENGE, file=sys.stderr)
        return 2
    if argv[:1] in (["-h"], ["--help"]):
        print(USAGE_CHECK)
        return 0
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
    print(USAGE_CHECK, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
