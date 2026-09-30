"""The service's state: one Ledger, its anonymous names, event guards and persistence.

Everything mutating goes through `Store` under one lock, and the state is written to the
module volume (atomically) after each change, so a restart keeps the class's scores. No
HTTP in here: server.py is a thin layer, and tests drive this directly.
"""

import json
import os
import threading
import time

import guards
import ledger as lg
import matcher
import names
from ledger import cat

STATE_FILE = "state.json"


class Denied(Exception):
    """A request the service refuses; `code` is the HTTP status."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Store:
    def __init__(self, catalog, config, data_dir, secret, anonymous=True, facilitator="facilitator",
                 clock=time.time, rate=(20, 10), shell_rate=(40, 10), ignore=()):
        self.lock = threading.Lock()
        self.data_dir = data_dir
        self.anonymous = anonymous
        self.facilitator = facilitator
        self.clock = clock
        self.config = config
        self.catalog = catalog
        state = self._read()
        self.ledger = lg.Ledger(catalog, config, state.get("ledger"))
        self.names = names.NameBook(state.get("name_seed") or os.urandom(8).hex(), state.get("names"))
        self.name_seed = self.names.seed
        self.verifier = guards.Verifier(secret)
        self.limiter = guards.RateLimiter(*rate)
        # Shell events: a pasted block of lab commands is a burst, not a cheat, so going over
        # this limit only drops events (no masher). The masher stays on dojo-check's own calls.
        self.shell_limiter = guards.RateLimiter(*shell_rate)
        self.matcher = matcher.Matcher(self.ledger.index)
        # Forgejo accounts that are never students (the Forgejo admin), besides the facilitator.
        self.ignore = {u for u in ignore if u}
        self.forged = state.get("forged", [])       # unattributed forged events (logged only)
        self._save()

    # -- persistence -------------------------------------------------------------------
    def _path(self):
        return os.path.join(self.data_dir, STATE_FILE) if self.data_dir else None

    def _read(self):
        path = self._path()
        try:
            with open(path) as f:
                return json.load(f)
        except (OSError, TypeError, ValueError):
            return {}

    def _save(self):
        path = self._path()
        if not path:
            return
        doc = {"ledger": self.ledger.to_dict(), "names": self.names.mapping(),
               "name_seed": self.name_seed, "forged": self.forged[-200:]}
        tmp = path + ".tmp"
        os.makedirs(self.data_dir, exist_ok=True)
        with open(tmp, "w") as f:
            json.dump(doc, f)
        os.replace(tmp, path)

    # -- helpers -----------------------------------------------------------------------
    def _student(self, user):
        if not user or user == self.facilitator:
            raise Denied(403, "students only")
        self.ledger.register(user)
        self.names.name_for(user)

    def _label(self, user):
        return self.names.name_for(user) if self.anonymous else user

    def _cheat(self, user, cheat_id, now):
        try:
            self.ledger.unlock(user, cheat_id, now)
        except lg.UnknownItem:
            pass    # a catalog without that cheat simply has no such penalty

    # -- student reads -----------------------------------------------------------------
    def me(self, user):
        with self.lock:
            self._student(user)
            L = self.ledger
            board = L.leaderboard()
            rank = next(r["rank"] for r in board if r["user"] == user)
            done, total, pct, complete = L.completion(user)
            out = {
                "name": self.names.name_for(user), "user": user, "workshop": self.catalog["title"],
                "score": L.score(user), "rank": rank, "of": len(board),
                "completion": {"done": done, "total": total, "percent": pct, "complete": complete,
                               "needed": -(-total * self.config.completion_percent // 100)},
                "recent": [{"id": r["id"], "title": r["title"], "kind": r["kind"], "points": r["points"],
                            "at": r["at"]} for r in L.recent(user)],
                "moments": L.moments(user),
                "challenges": self._challenge_rows(user),
            }
            self._save()
            return out

    def _challenge_rows(self, user):
        rows = []
        for ch in self.catalog["challenges"] + ([self.catalog["capstone"]] if self.catalog.get("capstone") else []):
            if not cat.is_active(ch):
                continue
            cid = ch["id"]
            done = cid in self.ledger.unlocked_ids(user)
            rows.append({"id": cid, "title": ch["title"], "done": done,
                         "hints": self.ledger.hints_used(user, cid),
                         "worth": self.ledger.clear_points(user, cid) if not done else
                         self.ledger.users[user]["unlocked"][cid]["points"]})
        return rows

    def board(self, viewer):
        with self.lock:
            self._student(viewer)
            rows = [{"name": self._label(r["user"]), "score": r["score"], "rank": r["rank"],
                     "you": r["user"] == viewer} for r in self.ledger.leaderboard()]
            self._save()
            return rows

    def toasts(self, user, surface, after=0):
        with self.lock:
            self._student(user)
            out = self.ledger.claim(user, surface, self.clock(), after)
            self._save()
            return out

    # -- cheats seen at the door ---------------------------------------------------------
    def tamper(self, user):
        """The caller's client is not the one we shipped (an edited dojo-check, or their own)."""
        with self.lock:
            self._student(user)
            self._cheat(user, "cheat-client", self.clock())
            self._save()

    def spoof(self, user):
        """`user` (identified by their own Forgejo token) sent someone else's identity headers."""
        with self.lock:
            self._student(user)
            self._cheat(user, "cheat-identity", self.clock())
            self._save()

    # -- events ------------------------------------------------------------------------
    def _award(self, user, item_id, now):
        entry = self.ledger.index.get(item_id)
        if entry is None:
            raise Denied(404, "unknown achievement")
        if entry["kind"] in ("challenge", "capstone"):
            return self.ledger.clear(user, item_id, now)
        return self.ledger.unlock(user, item_id, now)

    def _throttle(self, user, now):
        if not self.limiter.hit(user, now):
            self._cheat(user, "cheat-masher", now)
            raise Denied(429, "slow down")

    def event(self, caller, body):
        """A signed event from an adapter, checker or the student's own client.

        `caller` is the student the gateway (or the Forgejo token) identified, or None when
        the request came straight over the lab network. A forged event is only ever charged to
        an identified caller: charging the user named in the body would let one student cost
        another a point."""
        now = self.clock()
        with self.lock:
            try:
                user, item, ts, nonce, sig = (body["user"], body["event"], int(body["ts"]),
                                              str(body["nonce"]), body["sig"])
                if not isinstance(user, str) or not isinstance(item, str):
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                return self._forged(caller, now, "malformed")
            if caller is not None and caller != user:
                return self._forged(caller, now, "claims to be someone else")
            ok, why = self.verifier.verify(user, item, ts, nonce, sig, now)
            if not ok:
                if why == "forged":
                    return self._forged(caller, now, why)
                raise Denied(409 if why == "replay" else 400, why)
            self._student(user)
            self._throttle(user, now)
            pts = self._award(user, item, now)
            self._save()
            return {"awarded": pts is not None, "points": pts}

    def _forged(self, caller, now, why):
        if caller and caller != self.facilitator:
            self._student(caller)
            self._cheat(caller, "cheat-forged", now)
        else:
            self.forged.append({"at": now, "why": why})
        self._save()
        raise Denied(403, "rejected")

    # -- activity: shell hook and Forgejo webhook -----------------------------------------
    def _matched(self, user, event, now):
        """Unlock whatever this normalised event fires. Returns the new ids."""
        got = []
        for iid in self.matcher.match(event):
            if self.ledger.unlock(user, iid, now) is not None:
                got.append(iid)
        return got

    def shell(self, user, body):
        """One command line from the student's prompt hook. The text is matched, never kept."""
        event = matcher.shell_event(body)
        if event is None:
            raise Denied(400, "expected {cmd, exit}")
        now = self.clock()
        with self.lock:
            self._student(user)
            if not self.shell_limiter.hit(user, now):
                raise Denied(429, "slow down")
            got = self._matched(user, event, now)
            if got:
                self._save()
            return {"unlocked": len(got)}

    def forgejo(self, event):
        """One normalised Forgejo webhook event (already verified by the caller)."""
        user = event.get("user") if event else None
        if not user or user == self.facilitator or user in self.ignore:
            return {"unlocked": 0}
        with self.lock:
            self._student(user)
            got = self._matched(user, event, self.clock())
            self._save()
            return {"unlocked": len(got)}

    def hint(self, user, cid):
        with self.lock:
            self._student(user)
            now = self.clock()
            self._throttle(user, now)
            try:
                res = self.ledger.use_hint(user, cid)
            except (lg.UnknownItem, lg.WrongKind):
                raise Denied(404, "unknown challenge")
            ch = self.ledger.index[cid]["item"]
            res["text"] = ch["hints"][res["n"] - 1]
            self._save()
            return res

    def reveal(self, user, cid):
        with self.lock:
            self._student(user)
            try:
                allowed = self.ledger.reveal(user, cid)
            except (lg.UnknownItem, lg.WrongKind):
                raise Denied(404, "unknown challenge")
            except lg.HintsRequired:
                raise Denied(409, "use both hints first")
            self._save()
            return {"answer": self.ledger.index[cid]["item"].get("answer", ""), "scores": 0 if allowed else None}

    # -- facilitator -------------------------------------------------------------------
    def admin_state(self):
        with self.lock:
            L = self.ledger
            students = []
            for row in L.leaderboard():
                u = row["user"]
                done, total, pct, complete = L.completion(u)
                students.append({"user": u, "name": self.names.name_for(u), "score": row["score"],
                                 "rank": row["rank"], "percent": pct, "complete": complete,
                                 "unlocks": len(L.visible_unlocked(u)),
                                 "moments": [m["title"] for m in L.moments(u)],
                                 "cheats": [i for i, x in L.visible_unlocked(u).items() if x["cheat"]]})
            return {"students": students, "log": L.log[-100:], "forged": self.forged[-50:],
                    "anonymous": self.anonymous}

    def admin_award(self, user, points, reason):
        with self.lock:
            if user not in self.ledger.users:
                raise Denied(404, "no such student")
            if not isinstance(points, int) or isinstance(points, bool) or not -1000 <= points <= 1000:
                raise Denied(400, "points must be a whole number from -1000 to 1000")
            self.ledger.award(user, points, str(reason)[:200], self.clock())
            self._save()

    def admin_reset(self, user):
        with self.lock:
            if not self.ledger.reset(user, self.clock()):
                raise Denied(404, "no such student")
            self._save()

    def reload(self, catalog):
        """Swap in an edited catalog; unlocks already recorded are kept."""
        with self.lock:
            self.catalog = catalog
            state = self.ledger.to_dict()
            self.ledger = lg.Ledger(catalog, self.config, state)
            self.matcher = matcher.Matcher(self.ledger.index)
            self._save()
