#!/usr/bin/env python3
"""sensei: the class helper. Ask it about the labs, have it explain an error, or raise your hand.

  sensei help             this text
  sensei ask "question"   search this workshop's labs (what do I run to undo a push?)
  sensei why              explain the last error on your screen, if it is one Sensei knows
  sensei hand "message"   raise your hand: the facilitator sees your message and your last screen of output
  sensei inbox            replies to your hand-raises
  sensei check            your progress: which steps of the current lab are done and what's next
  sensei status           where your pull request stands with Sensei
  sensei review           which pull request to review next (peer review unlocks your own approval)
  sensei approve          ask Sensei to approve your pull request (needs a review of someone else's first,
                          or a few minutes' wait)
  sensei approve --force  approve it right now, if it follows the rules (your own records only, one change)

Sensei never merges for you: the merge is yours to click (or run). Proves who you are with your own Forgejo
token (~/.git-credentials), the same way dojo-check does. Stdlib only.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SENSEI_URL", "http://sensei:8080")
HOST = "git-server:3000"
HOME = os.path.expanduser("~")


def token():
    try:
        with open(os.path.join(HOME, ".git-credentials")) as f:
            for line in f:
                line = line.strip().replace("%3a", ":").replace("%3A", ":")
                if line.startswith("http://") and line.endswith("@" + HOST):
                    return line[len("http://"):-len("@" + HOST)].split(":", 1)[1]
    except (OSError, IndexError):
        pass
    return None


def call(path, body=None):
    tok = token()
    if not tok:
        return 0, {"error": "no Forgejo token in ~/.git-credentials"}
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET",
                                 headers={"Authorization": "token " + tok, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.load(e)
        except ValueError:
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError):
        return 0, {"error": "Sensei isn't reachable"}


def say(msg):
    print("\U0001F94B Sensei: " + msg)


def fail(doc):
    say(doc.get("error") or doc.get("message") or "something went wrong")
    return 1


def status():
    code, doc = call("/api/student/status")
    if code != 200:
        return fail(doc)
    if not doc["prs"]:
        say("I don't see an open pull request of yours. Push a branch and open one first.")
        return 0
    for p in doc["prs"]:
        line = "PR #%d \"%s\": %s" % (p["number"], p["title"], p["status"])
        if p.get("reason"):
            line += " (%s)" % p["reason"]
        print("  " + line + ("  [%d min]" % p["minutes"] if p["status"] not in ("merged", "approved") else ""))
    if doc["mode"] == "approve":
        if any(p["status"] == "waiting" for p in doc["prs"]):
            print("  Next: `sensei review`, review what it gives you, then `sensei approve`.")
        elif any(p["status"] == "approved" for p in doc["prs"]):
            print("  Approved. Merge it when the DNS Preview check is green.")
    return 0


def review():
    code, doc = call("/api/student/review", {})
    if code != 200:
        return fail(doc)
    pr = doc.get("pr")
    if not pr:
        say(doc.get("message", "Nothing to review."))
        return 0
    who = "my own practice pull request" if pr["practice"] else "%s's pull request" % pr["author"]
    say("review #%d next: %s (\"%s\")." % (pr["number"], who, pr["title"]))
    print("  Read Files changed and the DNS Preview comment: exactly one new record of theirs, one + CREATE?")
    print("  In the dnsconfig repo:  python3 scripts/dnsctl.py review %d" % pr["number"])
    print("                          python3 scripts/dnsctl.py approve %d   (only if it's right)" % pr["number"])
    print("  Then `sensei approve` for your own.")
    return 0


def approve(force):
    code, doc = call("/api/student/approve", {"force": force})
    if code != 200:
        return fail(doc)
    if doc.get("message"):
        return fail(doc)
    result = doc.get("result")
    if result == "approved":
        say("approved #%d. %s" % (doc["number"], "(You skipped the peer review; Lab 3 step 6 is worth doing anyway.)"
                                   if force else "Merge it once the DNS Preview check is green."))
        return 0
    if result == "waiting":
        mins = max(1, (doc.get("patience") or 0) // 60)
        say("not yet: review someone else's pull request first (`sensei review`). Or wait about %d minutes, "
            "or use `sensei approve --force`." % mins)
        return 1
    if result == "conflicts":
        say("#%d conflicts with main, so there's nothing to approve yet." % doc["number"])
        print("  Bring main into your branch: git pull origin main, keep both records, preview, commit, push.")
        print("  (Lab 3, \"If your branch is behind main, or your pull request has conflicts\".) Then run `sensei approve` again.")
        return 1
    if result == "needs-review":
        say("I can't approve #%d: %s" % (doc["number"], doc.get("reason", "")))
        print("  Fix it on your branch and push; I'll look again. The facilitator can see it too.")
        return 1
    say("something got in the way (%s). The facilitator can see it." % (doc.get("reason") or result))
    return 1


def screen():
    """The last lines on this tmux pane, minus the `sensei` command that is running now."""
    if not os.environ.get("TMUX"):
        return ""
    try:
        out = subprocess.run(["tmux", "capture-pane", "-p", "-J", "-S", "-80"], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = out.rstrip().splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and "sensei" in lines[-1]:
        lines.pop()
    return "\n".join(lines[-60:])


def clip(text, n=420):
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " ..."


def ask(argv):
    q = " ".join(argv).strip()
    if not q:
        print('usage: sensei ask "how do I undo a pushed change"')
        return 2
    code, doc = call("/api/student/ask", {"q": q})
    if code != 200:
        return fail(doc)
    if not doc["found"]:
        say(doc["message"])
        return 1
    say("here is where the labs cover that:")
    for f in doc["found"]:
        print("\n  %s  >  %s" % (f["file"], f["heading"]))
        print("    " + clip(f["snippet"]))
    print("\n  Open the lab in the lab reader for the full steps.")
    return 0


def why():
    text = screen()
    if not text:
        say("I read your terminal's last lines, but I can only do that inside the terminal tab (tmux). Try there.")
        return 1
    code, doc = call("/api/student/why", {"text": text})
    if code != 200:
        return fail(doc)
    m = doc.get("match")
    if not m:
        say(doc["message"])
        return 1
    say("that looks like: %s" % m["title"])
    print("  What it means: " + clip(m["explain"], 600))
    if m.get("fix"):
        print("  What to do:    " + clip(m["fix"], 600))
    if m.get("where"):
        print("  The lab:       %s%s" % (m["where"], ("  >  " + m["section"]) if m.get("section") else ""))
    return 0


def hand(argv):
    msg = " ".join(argv).strip()
    if not msg:
        print('usage: sensei hand "what you are stuck on"')
        return 2
    code, doc = call("/api/student/hand", {"text": msg, "context": screen()})
    if code != 200:
        return fail(doc)
    if not doc.get("ok"):
        say(doc.get("message", "I couldn't take that."))
        return 1
    say("your hand is up (request #%d). The facilitator can see your message and your last screen of output." % doc["id"])
    if doc.get("why"):
        print("  While you wait: this looks like \"%s\". %s" % (doc["why"]["title"], clip(doc["why"].get("fix") or doc["why"]["explain"], 300)))
    elif doc.get("ask"):
        f = doc["ask"][0]
        print("  While you wait, the labs cover this in %s > %s." % (f["file"], f["heading"]))
    print("  Check for an answer with `sensei inbox`.")
    return 0


def inbox():
    code, doc = call("/api/student/inbox", {})
    if code != 200:
        return fail(doc)
    reqs = doc.get("requests", [])
    if not reqs:
        say("nothing in your inbox. `sensei hand \"...\"` raises your hand.")
        return 0
    for r in reqs:
        print("  #%d \"%s\"  [%s]" % (r["id"], clip(r["text"], 80), r["status"]))
        for x in r["replies"]:
            print("      %s: %s" % (x["from"], x["text"]))
        if not r["replies"]:
            print("      (no answer yet)")
    return 0


def check():
    code, doc = call("/api/student/check", {})
    if code != 200:
        return fail(doc)
    if doc.get("message"):
        say(doc["message"])
        return 1
    cur = doc["current"]
    if not cur:
        say("every step is done (%d of %d). Nice work." % (doc["done"], doc["total"]))
        return 0
    say("you're at %d%% of the workshop (%d of %d steps)." % (doc["percent"], doc["done"], doc["total"]))
    for l in doc["labs"]:
        print("  %s %-34s %d/%d" % ("\u2713" if l["done"] == l["total"] else " ", l["title"][:34], l["done"], l["total"]))
    print("\n  Still to do in \"%s\":" % cur["title"])
    for m in cur["missing"]:
        print("    - %s   (%s)" % (m["title"], m["when"]))
    if cur["done"]:
        print("  Done here: " + ", ".join(cur["done"]))
    print("\n  Stuck on one? `sensei why` explains the last error, `sensei hand \"...\"` asks the facilitator.")
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd in ("help", "-h", "--help"):
        print(__doc__.strip())
        return 0
    if cmd == "ask":
        return ask(argv[2:])
    if cmd == "why":
        return why()
    if cmd == "hand":
        return hand(argv[2:])
    if cmd == "inbox":
        return inbox()
    if cmd == "check":
        return check()
    if cmd == "status":
        return status()
    if cmd == "review":
        return review()
    if cmd == "approve":
        return approve("--force" in argv[2:])
    print("sensei: unknown command %r (try `sensei help`)" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
