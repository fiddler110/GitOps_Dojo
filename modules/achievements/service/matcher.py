"""Turn raw activity into achievement ids. Pure: no I/O, no clock, no state.

Two event sources feed it (the `match` schema is documented in catalog/catalog.py):

  shell    one command line from the student's prompt hook (`dojo-check --shell`):
           {cmd, exit, branch, branch_before, in_repo, merging, merging_after}
  forgejo  one Forgejo webhook delivery, normalised by `forgejo_event` to
           {event, action, user, actor, repo, branch, tag, ref_type}

`Matcher(index).match(event)` returns the ids of every milestone or funny item whose `match`
fires for that event; the caller unlocks them (an id already unlocked scores nothing). The
service never keeps the command text: it is matched and dropped.
"""

import re
import shlex

MAX_CMD = 2000
CONTROL = {"&&", "||", ";", "|", "&", "|&", ";;", "(", ")"}
REDIRECT = re.compile(r"^[0-9]*(>>?|<<?<?|>&|<&|&>>?)$")
# git options that come before the subcommand and take a value (`git -C dir status`).
GIT_OPT_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
SHELL_WRAPPERS = {"command", "builtin", "noglob", "nocorrect", "time", "exec"}
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


# -- shell ---------------------------------------------------------------------------------
def _tokens(line):
    """shlex tokens with control operators and redirects as their own tokens. A newline
    separates commands, so it becomes ';' (inside quotes it stays part of the word)."""
    text = line.replace("\n", " ; ")
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        return list(lex)
    except ValueError:      # an unbalanced quote: fall back to plain words
        return text.split()


def _normalise_git(words):
    """`git -C dir --no-pager log` -> `git log`: drop git's own options before the subcommand."""
    if not words or words[0] != "git":
        return words
    out, i = ["git"], 1
    while i < len(words) and words[i].startswith("-"):
        w = words[i]
        i += 2 if w in GIT_OPT_ARG else 1
    return out + words[i:]


def segments(line):
    """The simple commands in one command line: [{"words": [...], "text": "..."}].

    `words` is the command and its arguments (redirects and their targets removed, leading
    VAR=value and `command`-style wrappers dropped, git's global options dropped); `text` is
    the same with redirects kept, for `regex`."""
    out, cur = [], []

    def flush():
        toks = list(cur)
        cur.clear()
        while toks and (ENV_ASSIGN.match(toks[0]) or toks[0] in SHELL_WRAPPERS):
            toks.pop(0)
        toks = _normalise_git(toks)
        if not toks:
            return
        words, i = [], 0
        while i < len(toks):
            if REDIRECT.match(toks[i]):
                i += 2          # the operator and its target
                continue
            words.append(toks[i])
            i += 1
        if words:
            out.append({"words": words, "text": " ".join(toks)})

    for t in _tokens(line[:MAX_CMD]):
        if t in CONTROL:
            flush()
        else:
            cur.append(t)
    flush()
    return out


def _has_flag(args, flag):
    """`flag` given in args: exactly, as --flag=value, or inside a short cluster (-fu has -f)."""
    for a in args:
        if a == "--":
            return False
        if a == flag or (flag.startswith("--") and a.startswith(flag + "=")):
            return True
        if (len(flag) == 2 and flag[0] == "-" and flag[1] != "-" and a.startswith("-")
                and not a.startswith("--") and flag[1] in a[1:]):
            return True
    return False


def _as_list(v):
    return v if isinstance(v, list) else [v]


def shell_event(body):
    """A validated shell event from the hook's request body, or None."""
    cmd = body.get("cmd")
    code = body.get("exit")
    if not isinstance(cmd, str) or not cmd.strip():
        return None
    if isinstance(code, str) and code.lstrip("-").isdigit():
        code = int(code)
    if not isinstance(code, int) or isinstance(code, bool):
        return None

    def text(k):
        v = body.get(k)
        return v[:200] if isinstance(v, str) and v else None

    def flag(k):
        v = body.get(k)
        return v in (True, 1, "1", "true")

    return {"source": "shell", "cmd": cmd[:MAX_CMD], "exit": code, "branch": text("branch"),
            "branch_before": text("branch_before"), "in_repo": flag("in_repo"),
            "merging": flag("merging"), "merging_after": flag("merging_after")}


def _exit_ok(want, code):
    if want is None or want == "any":
        return True
    if want == "nonzero":
        return code != 0
    return code in _as_list(want)


def _value_ok(m, ev, key, user):
    """`key` and `key_not` of a match against the event's value."""
    have = ev.get(key)
    if key in m:
        wants = [w.replace("{user}", user or "") for w in _as_list(m[key])]
        if have not in wants:
            return False
    if key + "_not" in m:
        nots = [w.replace("{user}", user or "") for w in _as_list(m[key + "_not"])]
        if have is None or have in nots:
            return False
    return True


def _shell_match(m, ev, rx):
    if not _exit_ok(m.get("exit"), ev["exit"]):
        return False
    for key in ("branch", "branch_before"):
        if not _value_ok(m, ev, key, None):
            return False
    for key in ("in_repo", "merging", "merging_after"):
        if key in m and ev.get(key) != m[key]:
            return False
    cmds = [c.split() for c in _as_list(m["cmd"])] if "cmd" in m else [None]
    for seg in segments(ev["cmd"]):
        words = seg["words"]
        for cw in cmds:
            if cw is not None and words[:len(cw)] != cw:
                continue
            args = words[len(cw):] if cw else words[1:]
            if "flags" in m and not any(_has_flag(args, f) for f in _as_list(m["flags"])):
                continue
            if "flags_none" in m and any(_has_flag(args, f) for f in _as_list(m["flags_none"])):
                continue
            if rx is not None and not rx.search(seg["text"]):
                continue
            return True
    return False


# -- forgejo -------------------------------------------------------------------------------
def _login(obj):
    if isinstance(obj, dict):
        v = obj.get("login") or obj.get("username")
        return v if isinstance(v, str) and v else None
    return None


REVIEW_ALIASES = {"pull_request_approved": "pull_request_review_approved",
                  "pull_request_rejected": "pull_request_review_rejected"}


def forgejo_event(kind, payload):
    """Normalise one webhook delivery. `kind` is the X-Forgejo-Event (or X-Gitea-Event) header.

    Returns {source, event, action, user, actor, repo, branch, tag, ref_type} or None for an
    event nothing matches on. `user` is who gets the credit: the pusher, the PR's author (a
    merge by the facilitator still credits the author), the reviewer."""
    if not isinstance(payload, dict) or not isinstance(kind, str):
        return None
    # Forgejo 16's X-Forgejo-Event for a review (X-Forgejo-Event-Type has the long form).
    kind = REVIEW_ALIASES.get(kind, kind)
    repo = payload.get("repository") if isinstance(payload.get("repository"), dict) else {}
    ev = {"source": "forgejo", "event": None, "action": None, "user": None, "actor": _login(payload.get("sender")),
          "repo": repo.get("full_name") if isinstance(repo.get("full_name"), str) else None,
          "branch": None, "tag": None, "ref_type": None, "head": None}

    def ref(value, ref_type=None):
        if not isinstance(value, str):
            return
        if value.startswith("refs/heads/"):
            ev["branch"], ev["ref_type"] = value[len("refs/heads/"):], "branch"
        elif value.startswith("refs/tags/"):
            ev["tag"], ev["ref_type"] = value[len("refs/tags/"):], "tag"
        elif ref_type in ("branch", "tag"):
            ev["branch" if ref_type == "branch" else "tag"], ev["ref_type"] = value, ref_type

    if kind == "push":
        ev["event"] = "push"
        ev["user"] = _login(payload.get("pusher")) or ev["actor"]
        ref(payload.get("ref"))
    elif kind in ("create", "delete"):
        ev["event"] = kind
        ev["user"] = ev["actor"]
        ref(payload.get("ref"), payload.get("ref_type"))
    elif kind == "pull_request":
        pr = payload.get("pull_request") if isinstance(payload.get("pull_request"), dict) else {}
        action = payload.get("action")
        if action == "closed" and pr.get("merged"):
            action = "merged"
        ev["event"], ev["action"] = "pull_request", action if isinstance(action, str) else None
        ev["user"] = _login(pr.get("user")) or ev["actor"]
        base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
        ev["branch"] = base.get("ref") if isinstance(base.get("ref"), str) else None
        head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
        ev["head"] = head.get("ref") if isinstance(head.get("ref"), str) else None
    elif kind.startswith("pull_request_review"):
        # pull_request_review_approved / _rejected / _comment
        action = kind[len("pull_request_review_"):] or None
        review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
        if not action and isinstance(review.get("type"), str):
            action = review["type"].split("_")[-1]
        ev["event"], ev["action"] = "pull_request_review", action
        ev["user"] = ev["actor"]
    else:
        return None
    return ev if ev["user"] else None


def _forgejo_match(m, ev):
    for key in ("event", "action", "ref_type", "branch", "tag", "repo", "head"):
        if not _value_ok(m, ev, key, ev["user"]):
            return False
    if "head_prefix" in m:
        head = ev.get("head") or ""
        if not any(head.startswith(p.replace("{user}", ev["user"] or "")) for p in _as_list(m["head_prefix"])):
            return False
    return True


# -- dns (posted by the dns-gate module, signed; see server.py /api/adapter) --------------------
DNS_EVENTS = ("zone_patch", "api_refused")


def dns_event(body):
    """A validated dns event from the gate's signed post, or None.

    zone_patch: one accepted change to a zone by an account's own key, with what it did to the
    zone: {zone, first, created, changed, deleted, min_ttl}. api_refused: a refused write by an
    account's own key. `user` is the account whose key it was."""
    if not isinstance(body, dict) or body.get("event") not in DNS_EVENTS:
        return None
    user, zone = body.get("user"), body.get("zone")
    if not isinstance(user, str) or not user or not isinstance(zone, str):
        return None

    def num(k):
        v = body.get(k)
        return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0

    ttl = body.get("min_ttl")
    return {"source": "dns", "event": body["event"], "user": user, "zone": zone[:200],
            "first": body.get("first") is True, "created": num("created"), "changed": num("changed"),
            "deleted": num("deleted"),
            "min_ttl": ttl if isinstance(ttl, int) and not isinstance(ttl, bool) and ttl >= 0 else None}


def _dns_match(m, ev):
    for key in ("event", "zone"):
        if not _value_ok(m, ev, key, ev["user"]):
            return False
    if "first" in m and ev["first"] != m["first"]:
        return False
    for key in ("created", "changed", "deleted"):
        if key + "_min" in m and ev[key] < m[key + "_min"]:
            return False
    if "ttl_below" in m and (ev["min_ttl"] is None or ev["min_ttl"] >= m["ttl_below"]):
        return False
    return True


# -- the matcher ---------------------------------------------------------------------------
class Matcher:
    """The matchable items of one catalog index (ledger.build_index), compiled once."""

    def __init__(self, index):
        self.rules = []     # (id, [(match, compiled regex or None)])
        for iid, entry in index.items():
            if entry["kind"] not in ("milestone", "funny") or entry.get("cheat"):
                continue
            m = entry["item"].get("match") or {}
            alts = m.get("any") if "any" in m else [m]
            compiled = []
            for a in alts:
                if isinstance(a, dict) and a.get("source") in ("shell", "forgejo", "dns"):
                    compiled.append((a, re.compile(a["regex"]) if "regex" in a else None))
            if compiled:
                self.rules.append((iid, compiled))

    def match(self, event, have=(), bump=None):
        """Ids whose match fires for this normalised event, in catalog order.

        `have`: ids the student already holds (for `requires`: every listed id must be held).
        `bump(id)`: counts one more matching event for this student and returns the new total
        (for `count: N`: fires from the Nth matching event on). Both are optional."""
        out = []
        for iid, alts in self.rules:
            for m, rx in alts:
                if m["source"] != event["source"]:
                    continue
                if "requires" in m and not all(r in have for r in _as_list(m["requires"])):
                    continue
                ok = {"shell": lambda: _shell_match(m, event, rx), "forgejo": lambda: _forgejo_match(m, event),
                      "dns": lambda: _dns_match(m, event)}[event["source"]]()
                if ok and "count" in m:
                    ok = bump is not None and bump(iid) >= m["count"]
                if ok:
                    out.append(iid)
                    break
        return out
