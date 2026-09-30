"""Achievement ledger: who unlocked what, what it scored, and what is left to toast.

Pure logic with no I/O and no clock of its own (callers pass `now`, seconds since the epoch),
so every rule is unit-tested without containers. The service persists `to_dict()` in the
module volume and reloads it with `from_dict()`.

Rules implemented here (ROADMAP.md, decisions A4-A7, A9, A13, A30):
  * points are awarded once per unlock; a score never goes below 0
  * hints cost a percentage of a challenge's points, two hints at most count, and revealing
    the answer scores 0 (the challenge still counts as cleared)
  * first blood and class-clear bonuses, each switchable
  * cheating costs at most -1 per item, each fires once, switchable
  * every unlock (milestone, challenge, funny, cheat) queues a toast, shown once
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "catalog"))
import catalog as cat  # noqa: E402

TOAST_MS = {"funny": 5000, "cheat": 5000, "default": 4000}
COLLAPSE_OVER = 5


class LedgerError(Exception):
    pass


class UnknownItem(LedgerError):
    pass


class WrongKind(LedgerError):
    pass


class HintsRequired(LedgerError):
    pass


def _int_env(env, name, default):
    try:
        return int(env.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    """Tunables, all settable in engine/.env (defaults are the roadmap's A4 values)."""

    def __init__(self, hint_percent=25, forfeit_after=2, first_blood=25, capstone_first_blood=50,
                 class_clear=10, first_blood_on=True, class_clear_on=True, cheat_penalty_on=True,
                 completion_percent=80, points=None):
        self.hint_percent = hint_percent
        self.forfeit_after = forfeit_after
        self.first_blood = first_blood
        self.capstone_first_blood = capstone_first_blood
        self.class_clear = class_clear
        self.first_blood_on = first_blood_on
        self.class_clear_on = class_clear_on
        self.cheat_penalty_on = cheat_penalty_on
        self.completion_percent = completion_percent
        self.points = dict(cat.DEFAULT_POINTS, **(points or {}))

    @classmethod
    def from_env(cls, env):
        def flag(name):
            return str(env.get(name, "1")).strip().lower() not in ("0", "false", "no", "off", "")

        return cls(
            hint_percent=_int_env(env, "ACHIEVEMENTS_HINT_PERCENT", 25),
            first_blood_on=flag("ACHIEVEMENTS_FIRST_BLOOD"),
            class_clear_on=flag("ACHIEVEMENTS_CLASS_CLEAR"),
            cheat_penalty_on=flag("ACHIEVEMENTS_CHEAT_PENALTY"),
            completion_percent=_int_env(env, "ACHIEVEMENTS_COMPLETION_PERCENT", 80),
            points={
                "milestone": _int_env(env, "ACHIEVEMENTS_MILESTONE_POINTS", 10),
                "funny": _int_env(env, "ACHIEVEMENTS_FUNNY_POINTS", 0),
                "challenge": _int_env(env, "ACHIEVEMENTS_CHALLENGE_POINTS", 100),
                "capstone": _int_env(env, "ACHIEVEMENTS_CAPSTONE_POINTS", 300),
            },
        )


def build_index(catalog, config):
    """id -> {kind, item, points, cheat} for everything a student can unlock right now.

    Retired items are left out: they can't be earned any more, while unlocks already
    recorded keep the points they scored. Switched-off items (`"enabled": false`) are left
    out too, and the Ledger also hides what was already earned from them.
    """
    idx = {}

    def add(item, kind, cheat=False):
        if not cat.is_active(item):
            return
        pts = item.get("points")
        if pts is None:
            pts = config.points[kind]
        idx[item["id"]] = {"kind": kind, "item": item, "points": pts, "cheat": cheat}

    for m in cat.milestones(catalog):
        add(m, "milestone")
    for f in catalog["funny"]:
        add(f, "funny")
    for f in catalog["shared"].get("unlocks", []):
        add(f, "funny")
    for f in catalog["shared"].get("cheats", []):
        add(f, "funny", cheat=True)
    for c in catalog["challenges"]:
        add(c, "challenge")
    if catalog.get("capstone"):
        add(catalog["capstone"], "capstone")
    return idx


class Ledger:
    def __init__(self, catalog, config=None, state=None):
        self.catalog = catalog
        self.config = config or Config()
        self.index = build_index(catalog, self.config)
        # Switched-off ids: unlocks, bonuses and toasts recorded for them stay in the state (so
        # switching the item back on restores them) but count for nothing and are never shown.
        self.disabled = cat.disabled_ids(catalog)
        s = state or {}
        self.users = s.get("users", {})
        self.first_blood = s.get("first_blood", {})       # challenge id -> user
        self.class_cleared = s.get("class_cleared", [])   # challenge ids
        self.log = s.get("log", [])                       # facilitator awards and resets
        self._seq = s.get("seq", 0)

    # -- persistence -------------------------------------------------------------------
    def to_dict(self):
        return {"users": self.users, "first_blood": self.first_blood,
                "class_cleared": self.class_cleared, "log": self.log, "seq": self._seq}

    @classmethod
    def from_dict(cls, catalog, state, config=None):
        return cls(catalog, config, state)

    # -- users -------------------------------------------------------------------------
    def register(self, user):
        """Add a student to the roster (class-clear counts everyone registered)."""
        return self._user(user)

    def _user(self, user):
        if user not in self.users:
            self.users[user] = {"unlocked": {}, "bonuses": [], "adjust": [], "hints": {},
                                "revealed": [], "toasts": [], "joined": None}
        return self.users[user]

    def _toast(self, u, now, kind, title, joke, points, item_id, cheat=False, badge=None):
        self._seq += 1
        t = {"seq": self._seq, "id": item_id, "kind": kind, "title": title, "joke": joke,
             "points": points, "at": now, "delivered": False,
             "ms": TOAST_MS["cheat" if cheat else "funny" if kind == "funny" else "default"]}
        if badge:
            t["badge"] = badge
        u["toasts"].append(t)

    # -- unlocking ---------------------------------------------------------------------
    def unlock(self, user, item_id, now):
        """Record a milestone, funny unlock or cheat. Returns the new points, or None if the
        student already has it (points are awarded once)."""
        entry = self.index.get(item_id)
        if entry is None:
            raise UnknownItem(item_id)
        if entry["kind"] not in ("milestone", "funny"):
            raise WrongKind(f"{item_id} is a {entry['kind']}; use clear()")
        u = self._user(user)
        if item_id in u["unlocked"]:
            return None
        pts = entry["points"]
        if entry["cheat"] and not self.config.cheat_penalty_on:
            pts = 0
        elif entry["kind"] == "funny" and pts > 0:
            pts = 0      # the validator refuses this; a bad env value must not pay out either
        u["unlocked"][item_id] = {"kind": entry["kind"], "points": pts, "at": now,
                                  "cheat": entry["cheat"]}
        item = entry["item"]
        self._toast(u, now, entry["kind"], item["title"], item.get("joke", ""), pts, item_id,
                    cheat=entry["cheat"])
        return pts

    # -- challenges and hints ----------------------------------------------------------
    def _challenge(self, cid):
        entry = self.index.get(cid)
        if entry is None:
            raise UnknownItem(cid)
        if entry["kind"] not in ("challenge", "capstone"):
            raise WrongKind(f"{cid} is not a challenge")
        return entry

    def hint_cost(self, cid):
        return self._challenge(cid)["points"] * self.config.hint_percent // 100

    def hints_used(self, user, cid):
        return self._user(user)["hints"].get(cid, 0)

    def use_hint(self, user, cid):
        """Hand out the next hint. Returns {n, cost, counted}: `n` is which hint (1 or 2),
        `cost` what this one takes off the challenge (0 if already paid for or the challenge
        is cleared), `counted` False once cleared (looking afterwards costs nothing)."""
        entry = self._challenge(cid)
        u = self._user(user)
        if cid in u["unlocked"]:
            return {"n": min(self.config.forfeit_after, len(entry["item"]["hints"])), "cost": 0, "counted": False}
        used = u["hints"].get(cid, 0)
        cap = self.config.forfeit_after
        if used >= cap:
            return {"n": cap, "cost": 0, "counted": True}
        u["hints"][cid] = used + 1
        return {"n": used + 1, "cost": self.hint_cost(cid), "counted": True}

    def reveal(self, user, cid):
        """Allow the answer after the hints are used up; it scores 0 for this challenge."""
        self._challenge(cid)
        u = self._user(user)
        if cid in u["unlocked"]:
            return False
        if u["hints"].get(cid, 0) < self.config.forfeit_after:
            raise HintsRequired(cid)
        if cid not in u["revealed"]:
            u["revealed"].append(cid)
        return True

    def clear_points(self, user, cid):
        """What clearing `cid` would score for this student right now."""
        entry = self._challenge(cid)
        u = self._user(user)
        if cid in u["revealed"]:
            return 0
        return max(0, entry["points"] - u["hints"].get(cid, 0) * self.hint_cost(cid))

    def clear(self, user, cid, now):
        """Record a passed challenge or capstone. Returns the points it scored (0 is a valid
        answer), or None when the student had already cleared it: only the first clear scores."""
        entry = self._challenge(cid)
        u = self._user(user)
        if cid in u["unlocked"]:
            return None
        pts = self.clear_points(user, cid)
        item = entry["item"]
        u["unlocked"][cid] = {"kind": entry["kind"], "points": pts, "at": now, "cheat": False,
                              "hints": u["hints"].get(cid, 0), "revealed": cid in u["revealed"]}
        self._toast(u, now, entry["kind"], item["title"], item.get("joke", ""), pts, cid,
                    badge=item.get("badge_tier"))
        self._bonuses(user, cid, entry, now)
        return pts

    def _bonuses(self, user, cid, entry, now):
        cfg, u = self.config, self._user(user)
        if cfg.first_blood_on and cid not in self.first_blood and cid not in u["revealed"]:
            pts = cfg.capstone_first_blood if entry["kind"] == "capstone" else cfg.first_blood
            self.first_blood[cid] = user
            u["bonuses"].append({"kind": "first-blood", "id": cid, "points": pts, "at": now})
            self._toast(u, now, "bonus", "First blood!", "You got there before anyone else.", pts, cid)
        if cfg.class_clear_on and cid not in self.class_cleared and len(self.users) >= 2:
            if all(cid in v["unlocked"] for v in self.users.values()):
                self.class_cleared.append(cid)
                for v in self.users.values():
                    v["bonuses"].append({"kind": "class-clear", "id": cid, "points": cfg.class_clear, "at": now})
                    self._toast(v, now, "bonus", "Class clear!",
                                f"The whole class cleared {entry['item']['title']}.", cfg.class_clear, cid)

    # -- facilitator -------------------------------------------------------------------
    def award(self, user, points, reason, now, by="facilitator"):
        """Manual score change (positive or negative), logged."""
        u = self._user(user)
        u["adjust"].append({"points": points, "reason": reason, "at": now})
        self.log.append({"action": "award", "user": user, "points": points, "reason": reason, "at": now, "by": by})

    def reset(self, user, now, by="facilitator"):
        """Wipe one student's achievements (and free the first-blood and class-clear marks
        they held so the next student can earn them)."""
        removed = self.users.pop(user, None)
        for cid, holder in list(self.first_blood.items()):
            if holder == user:
                del self.first_blood[cid]
        self.log.append({"action": "reset", "user": user, "at": now, "by": by,
                         "score": self._score_of(removed) if removed else 0})
        return removed is not None

    # -- reading -----------------------------------------------------------------------
    def _score_of(self, u):
        off = self.disabled
        total = sum(x["points"] for i, x in u["unlocked"].items() if i not in off)
        total += sum(b["points"] for b in u["bonuses"] if b.get("id") not in off)
        total += sum(a["points"] for a in u["adjust"])
        return max(0, total)

    def score(self, user):
        u = self.users.get(user)
        return self._score_of(u) if u else 0

    def _last_change(self, u):
        off = self.disabled
        times = [x["at"] for i, x in u["unlocked"].items() if x["points"] and i not in off]
        times += [b["at"] for b in u["bonuses"] if b.get("id") not in off] + [a["at"] for a in u["adjust"]]
        return max(times) if times else 0

    def leaderboard(self):
        """[{user, score, rank}] for the whole class, best first; a tie goes to whoever got
        to that score first, equal on both counts share a rank."""
        rows = [(self._score_of(u), self._last_change(u), name) for name, u in self.users.items()]
        rows.sort(key=lambda r: (-r[0], r[1], r[2]))
        out, prev, rank = [], None, 0
        for i, (score, at, name) in enumerate(rows, 1):
            if (score, at) != prev:
                rank, prev = i, (score, at)
            out.append({"user": name, "score": score, "rank": rank})
        return out

    def unlocked_ids(self, user):
        """What the student has unlocked, switched-off items left out."""
        return set(self.users.get(user, {}).get("unlocked", {})) - self.disabled

    def visible_unlocked(self, user):
        """{id: unlock record} without the switched-off items."""
        return {i: x for i, x in self.users.get(user, {}).get("unlocked", {}).items() if i not in self.disabled}

    def completion(self, user):
        """(done, total, percent, complete) over the core milestones."""
        return cat.completion(self.catalog, self.unlocked_ids(user), self.config.completion_percent)

    def recent(self, user, n=10):
        """The student's latest unlocks, newest first (the landing page's permanent record)."""
        u = self.users.get(user)
        if not u:
            return []
        rows = [dict(id=i, **x) for i, x in self.visible_unlocked(user).items()
                if not x["cheat"] and x["kind"] != "funny"]
        rows.sort(key=lambda r: -r["at"])
        return [dict(r, title=self.index_title(r["id"])) for r in rows[:n]]

    def moments(self, user):
        """The private Moments table (A30): funny unlocks with title, joke, what did it, when.
        Cheat penalties are not listed here; they are in the certificate summary."""
        u = self.users.get(user)
        if not u:
            return []
        out = []
        for iid, x in sorted(self.visible_unlocked(user).items(), key=lambda kv: kv[1]["at"]):
            if x["kind"] == "funny" and not x["cheat"]:
                item = self._find(iid)
                out.append({"id": iid, "title": item.get("title", iid), "joke": item.get("joke", ""),
                            "when": item.get("when", ""), "at": x["at"]})
        return out

    def _find(self, iid):
        entry = self.index.get(iid)
        if entry:
            return entry["item"]
        for it in self.catalog["funny"] + self.catalog["shared"].get("unlocks", []) + self.catalog["shared"].get("cheats", []):
            if it["id"] == iid:
                return it
        return {}

    def index_title(self, iid):
        return self._find(iid).get("title", iid)

    # -- toast queue -------------------------------------------------------------------
    def pending(self, user):
        return [t for t in self.users.get(user, {}).get("toasts", [])
                if not t["delivered"] and t.get("id") not in self.disabled]

    def claim(self, user, surface, now, after=0):
        """Toasts a surface should show now. Shown once: the first toast-capable surface to
        ask takes them. The terminal echo asks with surface='terminal' and marks nothing
        (A13); it passes the last `seq` it printed as `after`, so a prompt never echoes the same
        unlock twice. More than COLLAPSE_OVER queued collapse into a single summary toast."""
        queue = self.pending(user)
        if surface == "terminal":
            queue = [t for t in queue if t["seq"] > after]
        if not queue:
            return []
        if surface != "terminal":
            for t in queue:
                t["delivered"] = True
        if len(queue) > COLLAPSE_OVER:
            return [{"kind": "summary", "title": f"You unlocked {len(queue)} achievements",
                     "joke": "See them all on the landing page.", "count": len(queue),
                     "points": sum(t["points"] for t in queue), "ms": TOAST_MS["default"], "link": "/",
                     "seq": max(t["seq"] for t in queue)}]
        return [dict(t) for t in queue]
