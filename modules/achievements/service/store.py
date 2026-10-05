"""The service's state: one Ledger, its anonymous names, event guards and persistence.

Everything mutating goes through `Store` under one lock, and the state is written to the
module volume (atomically), so a restart keeps the class's scores. With `save_delay` set (the
service), a change only marks the state dirty and a writer thread writes it at most that often,
off the request path; `flush()` writes what is left (the service calls it on SIGTERM). Without
it (tests, tools), every change is written at once. No
HTTP in here: server.py is a thin layer, and tests drive this directly.
"""

import json
import os
import re
import sys
import threading
import time
from collections import deque

import guards
import ledger as lg
import matcher
import names
from ledger import cat

STATE_FILE = "state.json"
ACTIVITY_WINDOW = 600      # seconds of terminal history the stuck radar looks at
ACTIVITY_SAVE = 30         # at most this often, a command that unlocks nothing still saves the activity

# Strikes for poking at a neighbour -> the shared cheat unlocked on reaching it.
STRIKE_TIERS = ((1, "cheat-bump"), (3, "cheat-curious"), (8, "cheat-persistent"))


def name_in(name, text):
    """`name` as a whole word in `text` (student1 is not in student10, nor in my-student1)."""
    return re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", text) is not None


def _activity(doc):
    """The saved stuck-radar activity, dropping anything malformed."""
    out = {}
    for user, a in (doc.items() if isinstance(doc, dict) else ()):
        try:
            out[user] = {"first": float(a["first"]), "last": float(a["last"]), "streak": int(a["streak"]),
                         "recent": [(float(t), bool(f)) for t, f in a["recent"]][-200:]}
        except (KeyError, TypeError, ValueError):
            continue
    return out


class Denied(Exception):
    """A request the service refuses; `code` is the HTTP status."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Store:
    def __init__(self, catalog, config, data_dir, secret, anonymous=True, facilitator="facilitator",
                 clock=time.time, rate=(20, 10), shell_rate=(40, 10), ignore=(), save_delay=None,
                 soc_dwell_seconds=480, soc_ramp_seconds=600):
        self.lock = threading.Lock()
        self.data_dir = data_dir
        self.anonymous = anonymous
        self.facilitator = facilitator
        self.signature = ""        # facilitator name under the signature line (blank line if empty)
        self.class_date = ""       # printed date; blank means the day it is printed
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
        # Challenge spaces: user -> seed plan -> {repo, commits, at, resets}; and the log of
        # check runs the facilitator sees (A9).
        self.seeds = state.get("seeds", {})
        self.checks = state.get("checks", [])
        # Challenges with "watch": true that a student's first `dojo-check` started: user -> [ids]. The
        # state sweep re-checks them until they pass.
        self.watching = {u: [c for c in ids if isinstance(c, str)] for u, ids in (state.get("watching") or {}).items()
                         if isinstance(ids, list)}
        # Two-step challenges ("then"): user -> {id: when step 1 passed}; the next check runs step 2, whose
        # verbs can compare against that time (ctx "step_at": "rotated since", "no push since").
        self.stepped = {u: {c: t for c, t in ids.items() if isinstance(c, str) and isinstance(t, (int, float))}
                        for u, ids in (state.get("stepped") or {}).items() if isinstance(ids, dict)}
        self.busy = set()                           # users whose seed is being built right now
        self._state_at = {}                         # user -> when their `verify` milestones last ran
        # Per-student terminal activity for Sensei's stuck radar: times and exit codes only, never the command
        # text. Saved with the rest of the state, so a restart keeps the radar.
        self.activity = _activity(state.get("activity"))
        # Wall of shame (plan §8.12): (user, challenge) -> last `ctf`/`dump_success` event time.
        # Deliberately IN-MEMORY ONLY, not part of _doc()/persistence - it is a rolling "is the
        # attacker still connected right now" signal, not a record worth keeping across a
        # restart. See wall_rows().
        self.ctf_dumps = {}
        # SOC feed (plan §8.2): one bounded deque per student (their own "SOC Alerts" card) plus
        # one room-wide deque (the facilitator admin tab). Same deliberately-ephemeral treatment
        # as ctf_dumps above - a rolling live feed, not a record worth a restart.
        self.soc_feed = {}
        self.soc_feed_all = deque(maxlen=self.SOC_ROOM_MAX)
        # The room-wide SOC countdown (plan §8.2, revised 2026-10-05 for the big green/yellow/
        # red timer): this process's own start is the dwell clock's start - the same assumption
        # attacker-bot's bot.py makes about its own start (both processes come up with the
        # stack). SOC_DWELL_SECONDS/SOC_RAMP_SECONDS must equal
        # modules/ctf-range/attacker-bot/personas.py's DWELL_SECONDS/RAMP_SECONDS
        # (CTF_SOC_DWELL_SECONDS/CTF_SOC_RAMP_SECONDS in module.env set both sides).
        self.soc_started_at = self.clock()
        self.soc_dwell_seconds = soc_dwell_seconds
        self.soc_ramp_seconds = soc_ramp_seconds
        self._saved_at = None
        self.save_delay = save_delay
        self._dirty = False
        self._write_lock = threading.Lock()     # one writer at a time: the thread or flush()
        self._wake = threading.Event()
        self._last_write = 0.0                  # time.monotonic() of the last write
        if save_delay is not None:
            threading.Thread(target=self._writer, daemon=True).start()
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

    def _doc(self):
        """The whole state as JSON text (caller holds the lock)."""
        return json.dumps({"ledger": self.ledger.to_dict(), "names": self.names.mapping(),
                           "name_seed": self.name_seed, "forged": self.forged[-200:], "seeds": self.seeds,
                           "checks": self.checks[-500:], "activity": self.activity,
                           "watching": self.watching, "stepped": self.stepped})

    def _write(self, text):
        path = self._path()
        tmp = path + ".tmp"
        os.makedirs(self.data_dir, exist_ok=True)
        with open(tmp, "w") as f:
            f.write(text)
        os.replace(tmp, path)

    def _save(self):
        """The state changed (caller holds the lock): write it now, or let the writer know."""
        if not self._path():
            return
        self._dirty = True
        if self.save_delay is None:
            self._write(self._doc())
            self._dirty = False
            self._saved_at = self.clock()
        else:
            self._wake.set()

    def flush(self):
        """Write the state if it changed since the last write. Never call it holding the lock.
        True if something was written."""
        if not self._path():
            return False
        with self._write_lock:
            with self.lock:
                if not self._dirty:
                    return False
                text = self._doc()
                self._dirty = False
            try:
                self._write(text)
            except OSError:
                with self.lock:
                    self._dirty = True      # try again on the next change or flush
                raise
            self._last_write = time.monotonic()
            with self.lock:
                self._saved_at = self.clock()
            return True

    def _writer(self):
        """Writes the dirty state at most every `save_delay` seconds; a burst of changes is one write."""
        while True:
            self._wake.wait()
            wait = self._last_write + self.save_delay - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._wake.clear()      # a change from here on wakes us again
            try:
                self.flush()
            except OSError as exc:
                print(f"achievements: saving {self._path()} failed: {exc}", file=sys.stderr, flush=True)
                time.sleep(self.save_delay)
                self._wake.set()

    # -- helpers -----------------------------------------------------------------------
    def _student(self, user):
        if not user or user == self.facilitator:
            raise Denied(403, "students only")
        self.ledger.register(user)
        self.names.name_for(user)

    def _label(self, user):
        return self.names.name_for(user) if self.anonymous else user

    def _strike(self, user, now, n=1):
        """One "poked a neighbour" strike (caller holds the lock). The count is per student, over
        the whole class, and never resets; crossing a tier unlocks it (0, 0, then -1)."""
        u = self.ledger._user(user)
        before = u.get("strikes", 0)
        u["strikes"] = before + n
        for need, cheat_id in STRIKE_TIERS:
            if before < need <= u["strikes"]:
                self._cheat(user, cheat_id, now)

    def _neighbours(self, user):
        """Other students the service has seen (the seat names a command could point at)."""
        return [o for o in self.ledger.users if o != user and o != self.facilitator]

    def _cheat(self, user, cheat_id, now):
        try:
            self.ledger.unlock(user, cheat_id, now)
        except lg.UnknownItem:
            pass    # a catalog without that cheat simply has no such penalty

    # -- student reads -----------------------------------------------------------------
    def me(self, user):
        with self.lock:
            new = user not in self.ledger.users
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
                            "joke": L._find(r["id"]).get("joke", ""),
                            "when": L._find(r["id"]).get("when", ""), "at": r["at"]} for r in L.recent(user)],
                "moments": L.moments(user),
                "challenges": self._challenge_rows(user),
            }
            if new:     # every widget polls this: save only when it registered someone
                self._save()
            return out

    def _challenge_rows(self, user):
        rows = []
        for ch in self.catalog["challenges"] + ([self.catalog["capstone"]] if self.catalog.get("capstone") else []):
            if not cat.is_active(ch):
                continue
            cid = ch["id"]
            done = cid in self.ledger.unlocked_ids(user)
            rows.append({"id": cid, "title": ch["title"], "done": done, "repo": bool(ch.get("seed_plan")),
                         "hints": self.ledger.hints_used(user, cid),
                         "worth": self.ledger.clear_points(user, cid) if not done else
                         self.ledger.users[user]["unlocked"][cid]["points"]})
        return rows

    def board(self, viewer):
        with self.lock:
            new = viewer not in self.ledger.users
            self._student(viewer)
            rows = [{"name": self._label(r["user"]), "score": r["score"], "rank": r["rank"],
                     "you": r["user"] == viewer} for r in self.ledger.leaderboard()]
            if new:
                self._save()
            return rows

    def certificate(self, user):
        """Everything the printable certificate and its summary page show, for the student
        themself. The name printed on it is typed in the browser and never comes here."""
        with self.lock:
            self._student(user)
            L = self.ledger
            done, total, pct, complete = L.completion(user)
            row = next(r for r in L.leaderboard() if r["user"] == user)
            unlocked = sorted(L.visible_unlocked(user).items(), key=lambda kv: kv[1]["at"])
            unlocks, cheats = [], []
            for iid, x in unlocked:
                title = L.index_title(iid)
                if x["cheat"]:
                    cheats.append({"title": title, "points": x["points"], "at": x["at"]})
                elif x["kind"] != "funny":
                    unlocks.append({"id": iid, "title": title, "kind": x["kind"], "points": x["points"],
                                    "at": x["at"], "hints": x.get("hints", 0), "revealed": bool(x.get("revealed"))})
            capstone = any(x["kind"] == "capstone" for x in unlocks)
            return {"workshop": self.catalog["title"], "board_name": self.names.name_for(user), "user": user,
                    "score": L.score(user), "rank": row["rank"], "of": len(L.users),
                    "completion": {"done": done, "total": total, "percent": pct, "complete": complete},
                    "tier": ("capstone" if capstone else "complete") if complete else None,
                    "signature": self.signature, "class_date": self.class_date,
                    "unlocks": unlocks, "moments": L.moments(user), "cheats": cheats}

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
            ok, why = self.verifier.verify(user, item, ts, nonce, sig, now, record=False)
            if not ok:
                if why == "forged":
                    return self._forged(caller, now, why)
                raise Denied(409 if why == "replay" else 400, why)
            self._student(user)     # refuses the facilitator before the nonce is spent
            self.verifier.remember(nonce, ts)
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
        for iid in self.matcher.match(event, self.ledger.unlocked_ids(user), lambda i: self.ledger.bump(user, i)):
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
            self._touch(user, event["exit"], now)
            if not self.shell_limiter.hit(user, now):
                raise Denied(429, "slow down")
            got = self._matched(user, event, now)
            if any(name_in(o, event["cmd"]) for o in self._neighbours(user)):
                self._strike(user, now)
                got = got or ["strike"]
            if got or now - (self._saved_at or 0) >= ACTIVITY_SAVE:
                self._save()
            else:
                self._dirty = True  # written with the next save, or by flush() at shutdown
            return {"unlocked": len(got)}

    def _touch(self, user, code, now):
        """Note one command's time and whether it failed (caller holds the lock)."""
        a = self.activity.setdefault(user, {"first": now, "last": now, "streak": 0, "recent": []})
        a["last"] = now
        a["streak"] = a["streak"] + 1 if code != 0 else 0
        a["recent"] = [(t, f) for t, f in a["recent"] if now - t < ACTIVITY_WINDOW][-199:] + [(now, code != 0)]

    def activity_snapshot(self):
        """For Sensei's stuck radar: per student, how long since their last command and their last progress,
        their run of failures, and how many commands and failures in the last ten minutes."""
        now = self.clock()
        with self.lock:
            L, out = self.ledger, {}
            for user in L.users:
                if user == self.facilitator or user in self.ignore:
                    continue
                a = self.activity.get(user)
                ats = [x["at"] for x in L.visible_unlocked(user).values()
                       if not x["cheat"] and x["kind"] != "funny"]
                done, total, pct, complete = L.completion(user)
                recent = [f for t, f in a["recent"] if now - t < ACTIVITY_WINDOW] if a else []
                out[user] = {"since_cmd": int(now - a["last"]) if a else None,
                             "since_progress": int(now - max(ats)) if ats else None,
                             "since_first": int(now - a["first"]) if a else None,
                             "streak": a["streak"] if a else 0, "cmds": len(recent), "fails": sum(recent),
                             "percent": pct, "complete": complete}
            return out

    def progress(self, user):
        """A student's core milestones by lab, done or not, for `sensei check`. Titles and the lab step only:
        challenges, funny unlocks and cheats stay out."""
        with self.lock:
            have = self.ledger.unlocked_ids(user)
            labs = []
            for lab in self.catalog["labs"]:
                rows = [{"id": m["id"], "title": m["title"], "when": m.get("when", ""), "done": m["id"] in have}
                        for m in lab["milestones"] if cat.is_active(m) and m.get("core")]
                if rows:
                    labs.append({"id": lab["id"], "title": lab.get("title", lab["id"]), "milestones": rows})
            done, total, pct, complete = self.ledger.completion(user)
            return {"labs": labs, "done": done, "total": total, "percent": pct, "complete": complete}

    def forgejo(self, event):
        """One normalised Forgejo webhook event (already verified by the caller)."""
        user = event.get("user") if event else None
        if not user or user == self.facilitator or user in self.ignore:
            return {"unlocked": 0}
        with self.lock:
            self._student(user)
            now = self.clock()
            got = self._matched(user, event, now)
            owner = (event.get("repo") or "").split("/")[0]
            if owner != user and owner in self._neighbours(user):
                self._strike(user, now)     # a write (or review) in a classmate's repo
            self._save()
            return {"unlocked": len(got)}

    def adapter(self, event):
        """One normalised event from a module's adapter (already signature-checked by the caller)."""
        user = event.get("user") if event else None
        if not user or user == self.facilitator or user in self.ignore:
            return {"unlocked": 0}
        with self.lock:
            self._student(user)
            if event.get("source") == "ctf" and event.get("event") == "dump_success":
                self.ctf_dumps[(user, event.get("challenge") or "")] = self.clock()
            if event.get("source") == "soc":
                self._soc_alert(user, event, self.clock())
            got = self._matched(user, event, self.clock())
            self._save()
            return {"unlocked": len(got)}

    # SOC feed (plan §8.2). One alert per persona attempt against a student's own target,
    # bounded per-student (their "SOC Alerts" card) and room-wide (the admin tab). Severity is
    # derived from `event` here, once, rather than trusted as a free-text field from the poster.
    SOC_SEVERITY = {"recon": "INFO", "probe": "WARN", "exploit_attempt": "CRITICAL", "contained": "INFO"}
    SOC_PER_STUDENT_MAX = 50
    SOC_ROOM_MAX = 300

    def _soc_alert(self, user, event, now):
        """Append one soc alert to both feeds (caller holds the lock)."""
        row = {"user": self._label(user), "event": event.get("event"),
               "severity": self.SOC_SEVERITY.get(event.get("event"), "INFO"),
               "persona": event.get("persona"), "origin": event.get("origin"),
               "challenge": event.get("challenge"), "at": now}
        self.soc_feed.setdefault(user, deque(maxlen=self.SOC_PER_STUDENT_MAX)).append(row)
        self.soc_feed_all.append(row)

    def soc_rows(self, user):
        """This student's own recent alerts, newest first (their "SOC Alerts" card)."""
        with self.lock:
            return list(reversed(self.soc_feed.get(user, ())))

    def admin_soc_rows(self):
        """Every student's recent alerts, newest first (the facilitator admin tab)."""
        with self.lock:
            return list(reversed(self.soc_feed_all))

    def soc_timer(self):
        """{"phase", "seconds_remaining"} for the big green/yellow/red countdown everyone sees
        (student card and admin tab alike - it's room-wide, not per-student). Mirrors
        modules/ctf-range/attacker-bot/personas.py's room_timer() exactly (see this class's
        soc_started_at comment for why the two never need to talk to agree)."""
        now = self.clock()
        dwell_elapsed = now - self.soc_started_at - self.soc_dwell_seconds
        if dwell_elapsed <= 0:
            phase = "green"
        elif dwell_elapsed < self.soc_ramp_seconds:
            phase = "yellow"
        else:
            phase = "red"
        remaining = 0 if phase == "red" else max(
            0, int(self.soc_dwell_seconds + self.soc_ramp_seconds - (now - self.soc_started_at)))
        return {"phase": phase, "seconds_remaining": remaining}

    # Wall of shame (plan §8.12). LIVE while dump_success events keep arriving for a
    # (student, target); DISCONNECTED once they stop (the moment a patch lands and the next
    # attacker probe comes back empty - containment, same signal MTTP already counts); dropped
    # once quiet long enough to age off. Driven entirely by the event payload (CTF-S11): nothing
    # here is specific to any one target.
    WALL_LIVE_WINDOW = 90     # seconds with no fresh dump -> DISCONNECTED
    WALL_MAX_AGE = 1800       # seconds quiet -> dropped (ages off)

    def wall_rows(self):
        now = self.clock()
        with self.lock:
            for key in [k for k, t in self.ctf_dumps.items() if now - t > self.WALL_MAX_AGE]:
                del self.ctf_dumps[key]
            rows = [{"user": self._label(user), "challenge": challenge,
                    "state": "LIVE" if now - t < self.WALL_LIVE_WINDOW else "DISCONNECTED",
                    "last_seen": t}
                   for (user, challenge), t in self.ctf_dumps.items()]
        rows.sort(key=lambda r: -r["last_seen"])
        return rows

    def sweep_state(self, runner, unavailable=(), gap=20, budget=40):
        """Run the `verify` milestones (state, not events: "the app serves a new certificate") for
        every student whose turn it is: at most one pass per student per `gap` seconds, and at most
        `budget` backend checks per call. The checks run outside the lock; a backend that is down
        just skips the student until the next pass. Returns how many unlocked."""
        from challenges import NotCheckable
        now = self.clock()
        with self.lock:
            todo = []
            for user in sorted(self.ledger.users, key=lambda u: self._state_at.get(u, 0)):
                if user == self.facilitator or user in self.ignore or now - self._state_at.get(user, 0) < gap:
                    continue
                have = self.ledger.unlocked_ids(user)
                items = [(iid, {"id": iid, "verify": verify}, None)
                         for iid, verify in (self.matcher.pending_state(have) if self.matcher.state_rules else [])]
                for cid in [c for c in self.watching.get(user, []) if c not in have]:
                    ch = (self.ledger.index.get(cid) or {}).get("item")
                    if ch and ch.get("watch"):
                        items.append((cid, ch, dict(self._seed_of(user, ch))))
                if items:
                    todo.append((user, items))
                    self._state_at[user] = now
        got = 0
        for user, items in todo:
            for iid, ch, seed in items:
                if budget <= 0:
                    return got
                budget -= 1
                try:
                    res = runner.verify(ch, user, seed) if seed is not None else runner.verify(ch, user)
                except NotCheckable:
                    continue
                except unavailable:
                    break
                if res["passed"]:
                    with self.lock:
                        if seed is not None:
                            got += self._watched_pass(user, iid)
                        elif self.ledger.unlock(user, iid, self.clock()) is not None:
                            got += 1
                            self._save()
        return got

    def _watched_pass(self, user, cid):
        """A watched challenge passed in the sweep: score it as a check would (caller holds the lock)."""
        mine = self.watching.get(user, [])
        if cid in mine:
            mine.remove(cid)
        if cid in self.ledger.unlocked_ids(user):
            return 0
        pts = self.ledger.clear(user, cid, self.clock())
        self.checks.append({"user": user, "id": cid, "at": self.clock(), "passed": True,
                            "hints": self.ledger.hints_used(user, cid), "points": pts, "watched": True})
        self._save()
        return 1

    def probe(self, user, body):
        """A check or challenge request naming another student's space (only a hand-made
        request can: dojo-check sends the challenge id and nothing else). Refused, one strike."""
        with self.lock:
            self._student(user)
            values = [body.get(k) for k in ("user", "repo", "space")]
            if not any(isinstance(v, str) and any(name_in(o, v) for o in self._neighbours(user))
                       for v in values):
                return
            self._strike(user, self.clock())
            self._save()
        raise Denied(403, "that space is not yours")

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

    # -- challenges: checking and seeding (the runner does the backend I/O, never under the lock)
    def _active_challenge(self, cid):
        entry = self.ledger.index.get(cid) if isinstance(cid, str) else None
        if not entry or entry["kind"] not in ("challenge", "capstone"):
            raise Denied(404, "unknown challenge")
        return entry["item"]

    def _seed_of(self, user, ch):
        return (self.seeds.get(user) or {}).get(ch.get("seed_plan") or "", {})

    def check(self, user, cid, runner, unavailable=()):
        """Run a challenge's verifiers for this student. A pass is recorded once and never
        undone; a wrong answer costs nothing (the masher limit still applies)."""
        now = self.clock()
        with self.lock:
            self._student(user)
            self._throttle(user, now)
            ch = self._active_challenge(cid)
            if cid in self.ledger.unlocked_ids(user):
                return {"passed": True, "already": True, "points": None,
                        "message": "already cleared; points are earned once"}
            seed = dict(self._seed_of(user, ch))
            then = ch.get("then")
            step_at = self.stepped.get(user, {}).get(cid) if then else None
        try:
            if step_at is not None:
                res = runner.verify(dict(ch, verify=then["verify"]), user, seed, step_at=step_at)
            else:
                res = runner.verify(ch, user, seed)
        except unavailable as exc:
            raise Denied(503, f"couldn't check right now ({exc}); try again in a moment")
        if then and step_at is None and res["passed"]:
            # Step 1 passed: remember it and say what's next; nothing is scored until step 2.
            with self.lock:
                self.stepped.setdefault(user, {})[cid] = now
                self.checks.append({"user": user, "id": cid, "at": now, "passed": False, "step": 1,
                                    "hints": self.ledger.hints_used(user, cid), "points": None})
                self._save()
            return {"passed": False, "already": False, "points": None, "step": 1,
                    "message": "step 1 of 2 passed. Next: " + runner.render(ch, user, then["text"])
                               + " Then run the check again."}
        with self.lock:
            pts = self.ledger.clear(user, cid, self.clock()) if res["passed"] else None
            if res["passed"] or (step_at is not None and res.get("restart")):
                self.stepped.get(user, {}).pop(cid, None)
            if step_at is not None and res.get("restart") and not res["passed"]:
                res = dict(res, message=res["message"] + ". Back to step 1: put it right and check again.")
            mine = self.watching.setdefault(user, [])
            if ch.get("watch") and not res["passed"] and cid not in mine:
                mine.append(cid)
            elif res["passed"] and cid in mine:
                mine.remove(cid)
            self.checks.append({"user": user, "id": cid, "at": now, "passed": res["passed"],
                                "hints": self.ledger.hints_used(user, cid), "points": pts})
            self._save()
        return {"passed": res["passed"], "already": pts is None and res["passed"], "points": pts,
                "message": res["message"]}

    def challenge_space(self, user, cid, action, runner, unavailable=()):
        """Start (create if missing) or reset (delete and re-create) the student's challenge
        space. Hints used and points earned are untouched: a reset never refunds or re-pays.
        A challenge with no seed plan works in the student's own lab space: start only
        answers with its goal (repo None), and there is nothing to reset."""
        if action not in ("start", "reset"):
            raise Denied(400, "action is start or reset")
        with self.lock:
            self._student(user)
            self._throttle(user, self.clock())
            ch = self._active_challenge(cid)
            if not ch.get("seed_plan"):
                if action == "reset":
                    raise Denied(400, f"{cid} has no repo to reset: it works in your own lab space")
                return {"repo": None, "created": False, "done": cid in self.ledger.unlocked_ids(user),
                        "hints": self.ledger.hints_used(user, cid)}
            if user in self.busy:
                raise Denied(409, "already building your challenge repo; wait a moment")
            self.busy.add(user)
        try:
            try:
                res = runner.seed(ch, user, reset=action == "reset")
            except unavailable as exc:
                raise Denied(503, f"couldn't build the challenge repo ({exc}); try again")
            with self.lock:
                if action == "reset":
                    self.stepped.get(user, {}).pop(cid, None)       # a fresh space starts again at step 1
                mine = self.seeds.setdefault(user, {})
                old = mine.get(res["plan"], {})
                if res["created"]:
                    mine[res["plan"]] = {"repo": res["repo"], "commits": res["commits"], "at": self.clock(),
                                         "resets": old.get("resets", -1) + 1}
                self._save()
            return {"repo": res["repo"], "created": res["created"],
                    "done": cid in self.ledger.unlocked_ids(user),
                    "hints": self.ledger.hints_used(user, cid)}
        finally:
            with self.lock:
                self.busy.discard(user)

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
                                 "override": bool(L.users[u].get("complete_override")),
                                 "unlocks": len(L.visible_unlocked(u)),
                                 "moments": [m["title"] for m in L.moments(u)],
                                 "cheats": [i for i, x in L.visible_unlocked(u).items() if x["cheat"]]})
            return {"students": students, "log": L.log[-100:], "forged": self.forged[-50:],
                    "checks": self.checks[-100:],
                    "anonymous": self.anonymous}

    def admin_award(self, user, points, reason):
        with self.lock:
            if user not in self.ledger.users:
                raise Denied(404, "no such student")
            if not isinstance(points, int) or isinstance(points, bool) or not -1000 <= points <= 1000:
                raise Denied(400, "points must be a whole number from -1000 to 1000")
            self.ledger.award(user, points, str(reason)[:200], self.clock())
            self._save()

    def admin_complete(self, user, on):
        with self.lock:
            if not self.ledger.set_complete(user, bool(on), self.clock()):
                raise Denied(404, "no such student")
            self._save()

    def student_reset(self, user, scores=False):
        """The facilitator's student reset (engine Roster, `resets` hooks): forget the student's
        in-flight challenge state (their repos go with their Forgejo account), and with `scores`
        their achievements too. Safe to run again. Returns a short detail."""
        with self.lock:
            for table in (self.seeds, self.watching, self.stepped, self.activity):
                table.pop(user, None)
            self.busy.discard(user)
            self._state_at.pop(user, None)
            cleared = scores and self.ledger.reset(user, self.clock(), by="student reset")
            self._save()
        if scores:
            return "achievements and score cleared" if cleared else "no achievements to clear"
        return "challenge progress forgotten; achievements kept"

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
