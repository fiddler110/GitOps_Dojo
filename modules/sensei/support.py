"""Sensei's support desk: search the labs, explain an error, take a help request. Pure; stdlib only.

Three pieces, all offline and deterministic (student terminals have no internet and Sensei has no model):

* `LabIndex`   searches the workshop's own lab and cheat-sheet text, section by section (`sensei ask`).
* `Patterns`   matches terminal output against known errors (`sensei why`). The table is derived from the labs
               themselves (every "You see / If it says" troubleshooting table), plus the shared git patterns
               and an optional per-workshop `sensei/patterns.json`.
* `Radar`      who looks stuck, from the achievements service's per-student activity (the facilitator's tab)
* `Achievements` that service's Sensei-only reads, and `current_lab` for `sensei check`
* `HelpDesk`   the raise-a-hand queue the facilitator answers (`sensei hand`, `sensei inbox`).

Challenge and capstone text never goes in: it is not in the lab files, and headings that name one are skipped, so
asking Sensei can never leak a hint or an answer.
"""
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

STOP = set("""a an and are as at be but by can do does for from how i if in is it its me my of on or so that the
their them then there these this to up was we what when where which who why will with you your should would could
have has had not no yes get got make made use using run running want need like into out about""".split())
SKIP_HEADINGS = re.compile(r"challenge|capstone", re.I)
TABLE_HEAD = re.compile(r"^(you see|if you see|if it says|symptom|error|message|problem|what you see)", re.I)
PLACEHOLDER = re.compile(r"\.\.\.|…|<[^>]*>")
WORD = re.compile(r"[a-z0-9][a-z0-9_.\-]*")
CLIP = 600


def tokens(text):
    out = []
    for w in WORD.findall(text.lower()):
        w = w.strip(".-_")
        if len(w) < 2 or w in STOP:
            continue
        out.append(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return out


def _clip(text, n=CLIP):
    text = text.strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " ..."


# -- search the labs ---------------------------------------------------------------------------
class LabIndex:
    def __init__(self, lab_dir):
        self.sections = []
        self.df = {}
        if lab_dir and os.path.isdir(lab_dir):
            for name in sorted(os.listdir(lab_dir)):
                if name.endswith(".md") and not name.startswith("."):
                    try:
                        with open(os.path.join(lab_dir, name), encoding="utf-8") as f:
                            self._add(name, f.read())
                    except OSError:
                        pass
        for s in self.sections:
            for t in set(s["tf"]) | set(s["head_tf"]):
                self.df[t] = self.df.get(t, 0) + 1

    def _add(self, name, text):
        lab, heading, body, fence = "", "", [], False

        def flush():
            if heading and not SKIP_HEADINGS.search(heading) and "".join(body).strip():
                joined = "\n".join(body).strip()
                tf = {}
                for t in tokens(joined):
                    tf[t] = tf.get(t, 0) + 1
                head_tf = {t: 1 for t in tokens(heading)}
                self.sections.append({"file": name, "lab": lab, "heading": heading, "text": joined, "tf": tf,
                                      "head_tf": head_tf, "len": max(1, sum(tf.values()))})

        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                fence = not fence
            m = None if fence else re.match(r"^(#{1,3})\s+(.*\S)\s*$", line)
            if m:
                flush()
                body = []
                if m.group(1) == "#" and not lab:
                    lab = m.group(2)
                heading = m.group(2)
                continue
            body.append(line)
        flush()

    def search(self, query, limit=3):
        """Best sections for `query`: [{file, lab, heading, snippet, score}], [] when nothing fits well."""
        q = tokens(query)
        if not q or not self.sections:
            return []
        n = len(self.sections)
        scored = []
        for s in self.sections:
            hit, score = 0, 0.0
            for t in set(q):
                tf, ht = s["tf"].get(t, 0), s["head_tf"].get(t, 0)
                if not (tf or ht):
                    continue
                hit += 1
                idf = math.log(1 + n / (1 + self.df.get(t, 0)))
                score += idf * ((1 + math.log(1 + tf)) / (1 + s["len"] / 400.0) + 2.5 * ht)
            if hit:
                scored.append((hit / len(set(q)), score, s))
        scored = [x for x in scored if x[0] >= 0.5]  # at least half the words of the question
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return [{"file": s["file"], "lab": s["lab"], "heading": s["heading"], "snippet": _clip(s["text"]),
                 "score": round(sc, 2)} for _, sc, s in scored[:limit]]


# -- explain an error --------------------------------------------------------------------------
def _literal_regex(text):
    """A regex for a backticked message from a lab: its `...`/`<link>` placeholders match anything."""
    parts = [p.strip() for p in PLACEHOLDER.split(text)]
    parts = [p for p in parts if p]
    if not parts or sum(len(p) for p in parts) < 10:
        return None
    return ".*?".join(re.escape(p) for p in parts)


def derive_patterns(lab_dir):
    """One pattern per row of a lab's "You see | Cause / fix" style table whose first cell is a backticked message."""
    out = []
    if not (lab_dir and os.path.isdir(lab_dir)):
        return out
    for name in sorted(os.listdir(lab_dir)):
        if not name.endswith(".md") or name.startswith("."):
            continue
        try:
            with open(os.path.join(lab_dir, name), encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        heading, in_table, fence = "", False, False
        for line in lines:
            if line.lstrip().startswith("```"):
                fence = not fence
            if fence:
                continue
            m = re.match(r"^#{1,3}\s+(.*\S)\s*$", line)
            if m:
                heading, in_table = m.group(1), False
                continue
            if not line.startswith("|"):
                in_table = False
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not cells:
                continue
            if re.match(r"^:?-{2,}", cells[0]):
                continue
            if not in_table:  # the header row decides whether this table is about messages
                in_table = TABLE_HEAD.match(cells[0]) is not None or "table-skip"
                continue
            if in_table == "table-skip":
                continue
            msg = re.match(r"^(`{1,2})\s*(.+?)\s*\1$", cells[0])
            rx = _literal_regex(msg.group(2)) if msg and len(cells) >= 2 else None
            if rx:
                explain = cells[1]
                fix = cells[2] if len(cells) > 2 else ""
                out.append({"id": "%s:%d" % (name, len(out)), "regex": rx, "title": msg.group(2),
                            "explain": explain, "fix": fix, "where": name, "section": heading})
    return out


class Patterns:
    def __init__(self, patterns):
        self.items = []
        for p in patterns:
            try:
                self.items.append(dict(p, rx=re.compile(p["regex"], re.I | re.S)))
            except (re.error, KeyError):
                pass

    @classmethod
    def load(cls, lab_dir=None, files=()):
        """Per-workshop first (the derived and `patterns.json` ones), then the shared ones."""
        items = derive_patterns(lab_dir)
        for path in files:
            try:
                with open(path, encoding="utf-8") as f:
                    items += json.load(f).get("patterns", [])
            except (OSError, ValueError):
                pass
        return cls(items)

    def match(self, text):
        """The pattern whose match ends nearest the bottom of `text` (the last thing that went wrong), or None."""
        best, at = None, -1
        for p in self.items:
            end = -1
            for m in p["rx"].finditer(text):
                end = m.end()
            if end > at:
                best, at = p, end
        if not best:
            return None
        return {k: best.get(k, "") for k in ("id", "title", "explain", "fix", "where", "section")}


# -- the raise-a-hand queue --------------------------------------------------------------------
MAX_OPEN = 3
MIN_GAP = 20
MAX_TEXT = 500
MAX_CONTEXT = 3000


class HelpDesk:
    def __init__(self, path=None, clock=time.time):
        self.path, self.clock = path, clock
        self.lock = threading.Lock()
        self.next, self.requests = 1, {}
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    d = json.load(f)
                self.next = d.get("next", 1)
                self.requests = {int(k): v for k, v in d.get("requests", {}).items()}
            except (OSError, ValueError):
                pass

    def _save(self):
        if not self.path:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"next": self.next, "requests": self.requests}, f)
        os.replace(tmp, self.path)

    def raise_hand(self, user, text, context="", auto=None):
        """(request or None, problem). One student can have a few open and can't flood the facilitator."""
        text = (text or "").strip()[:MAX_TEXT]
        if not text:
            return None, "Say what you're stuck on, e.g. sensei hand \"my push is rejected\"."
        with self.lock:
            mine = [r for r in self.requests.values() if r["user"] == user and r["status"] != "closed"]
            if len(mine) >= MAX_OPEN:
                return None, "You already have %d open requests: check `sensei inbox`, or wait for an answer." % len(mine)
            if mine and self.clock() - max(r["created"] for r in mine) < MIN_GAP:
                return None, "Give it a moment: your last request was just now."
            r = {"id": self.next, "user": user, "text": text, "context": (context or "")[-MAX_CONTEXT:],
                 "created": self.clock(), "status": "open", "replies": [], "auto": auto or {}}
            self.requests[self.next] = r
            self.next += 1
            self._save()
            return r, ""

    def reply(self, rid, text, who="facilitator"):
        with self.lock:
            r = self.requests.get(rid)
            text = (text or "").strip()[:MAX_TEXT * 2]
            if not r or not text:
                return False
            r["replies"].append({"from": who, "text": text, "at": self.clock(), "seen": False})
            r["status"] = "answered"
            self._save()
            return True

    def close(self, rid):
        with self.lock:
            r = self.requests.get(rid)
            if not r:
                return False
            r["status"] = "closed"
            self._save()
            return True

    def inbox(self, user, mark_seen=True):
        """The student's requests with their replies; unseen replies are marked seen."""
        with self.lock:
            out = []
            for r in sorted(self.requests.values(), key=lambda r: r["id"]):
                if r["user"] != user or r["status"] == "closed":
                    continue
                out.append({"id": r["id"], "text": r["text"], "status": r["status"],
                            "replies": [dict(x) for x in r["replies"]]})
                if mark_seen:
                    for x in r["replies"]:
                        x["seen"] = True
            if mark_seen:
                self._save()
            return out

    def snapshot(self):
        """Everything the facilitator's tab shows, open ones first, with minutes waiting."""
        now = self.clock()
        with self.lock:
            rows = [dict(r, minutes=int((now - r["created"]) // 60)) for r in self.requests.values()
                    if r["status"] != "closed"]
        rows.sort(key=lambda r: (r["status"] != "open", r["id"]))
        return rows

    def open_count(self):
        with self.lock:
            return sum(1 for r in self.requests.values() if r["status"] == "open")


# -- the stuck radar ---------------------------------------------------------------------------
LEVELS = {"failing": 0, "stalled": 1, "quiet": 2}


def stuck(students, helping=(), stuck_minutes=10):
    """Who to look at, worst first: [{user, level, why: [..], percent, hand}].

    `students` is the achievements service's activity snapshot (times and exit codes, never commands).
    failing = a run of failed commands (or most of the last ten minutes failed); stalled = busy at the
    terminal but no new milestone for `stuck_minutes`; quiet = no command for a while. Finished students and
    ones who never typed anything (not here yet) are left out, as is anyone gone for over an hour and a half."""
    out = []
    for user, a in students.items():
        if a.get("complete") or a.get("since_cmd") is None:
            continue
        why, level = [], None

        def flag(lv, text):
            nonlocal level
            why.append(text)
            level = lv if level is None or LEVELS[lv] < LEVELS[level] else level

        idle = a["since_cmd"]
        if idle > 90 * 60:
            continue
        if a.get("streak", 0) >= 5 and idle < 300:
            flag("failing", "%d failed commands in a row" % a["streak"])
        elif a.get("cmds", 0) >= 8 and a.get("fails", 0) * 10 >= a["cmds"] * 7 and idle < 300:
            flag("failing", "%d of the last %d commands failed" % (a["fails"], a["cmds"]))
        since = a["since_progress"] if a.get("since_progress") is not None else a.get("since_first", 0)
        if idle <= 180 and since >= stuck_minutes * 60:
            flag("stalled", "no new milestone for %d min" % (since // 60))
        if idle >= 15 * 60:
            flag("quiet", "no command for %d min" % (idle // 60))
        if level:
            out.append({"user": user, "level": level, "why": why, "percent": a.get("percent", 0),
                        "hand": user in helping})
    out.sort(key=lambda r: (LEVELS[r["level"]], r["user"]))
    return out


class Achievements:
    """The achievements service's Sensei-only reads (activity for everyone, progress for one student)."""

    def __init__(self, url, key, ttl=10, clock=time.time, opener=None):
        self.url, self.key, self.ttl, self.clock = (url or "").rstrip("/"), key, ttl, clock
        self.opener = opener or self._open
        self._cache = {}

    @property
    def on(self):
        return bool(self.url and self.key)

    def _open(self, path):
        req = urllib.request.Request(self.url + path, headers={"X-Sensei-Key": self.key})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.load(r)
        except (urllib.error.URLError, OSError, ValueError):
            return None

    def _get(self, path):
        if not self.on:
            return None
        now = self.clock()
        hit = self._cache.get(path)
        if hit and hit[1] > now:
            return hit[0]
        doc = self.opener(path)
        if len(self._cache) > 200:
            self._cache.clear()
        self._cache[path] = (doc, now + self.ttl)
        return doc

    def activity(self):
        doc = self._get("/api/sensei/activity")
        return doc.get("students") if isinstance(doc, dict) else None

    def progress(self, user):
        doc = self._get("/api/sensei/progress?user=" + urllib.parse.quote(user, safe=""))
        return doc if isinstance(doc, dict) and "labs" in doc else None


def current_lab(progress):
    """`sensei check`'s answer: per-lab counts, and the first lab with a milestone still to do.

    Milestones are the lab's own steps, so what is missing doubles as "what to do next"."""
    labs = [{"title": l["title"], "done": sum(m["done"] for m in l["milestones"]), "total": len(l["milestones"])}
            for l in progress["labs"]]
    now = next((l for l in progress["labs"] if not all(m["done"] for m in l["milestones"])), None)
    cur = None
    if now:
        cur = {"title": now["title"], "done": [m["title"] for m in now["milestones"] if m["done"]],
               "missing": [{"title": m["title"], "when": m["when"]} for m in now["milestones"] if not m["done"]]}
    return {"labs": labs, "current": cur, "percent": progress["percent"], "complete": progress["complete"],
            "done": progress["done"], "total": progress["total"]}
