"""The attack-swarm engine for the single `attacker-bot` service (plan §8.2, revised 2026-10-05
per the user: one container, one thread per student, hitting each target the same way a
student's own terminal does - `http://ctf-host:<published port>` - rather than a fleet of
per-student bot containers living inside ctf-host. Pure logic, no network and no real clock by
default, so it is fully unit-testable: `bot.py` is the thin runtime that wires this to real
target URLs, a real clock and a real `AdapterClient`.

**The room is on ONE shared clock, not independent per-student timers** (the user's "should the
exploit check be synchronized" question - yes): every student passes through the same three
phases at the same elapsed time, so the room feels one rising wave of pressure rather than N
unrelated sieges:

  * **GREEN - recon** (0..DWELL_SECONDS): read-only probes only, every target.
  * **YELLOW - escalating** (DWELL_SECONDS..DWELL_SECONDS+RAMP_SECONDS): the delay between
    attempts ramps down toward RAMP_FLOOR and the chance that an attempt is the real payload
    climbs from 0 toward the style's ceiling, both as a function of how far into the ramp the
    room is (shared across students) - "something more aggressive the closer it gets."
  * **RED - detonated** (past DWELL_SECONDS+RAMP_SECONDS, plus a small 0-60s per-student
    jitter so it doesn't read as one perfectly simultaneous stampede): every attempt from here
    on IS the real payload. Still vulnerable -> breach; already patched -> a failed
    `exploit_attempt` (or `contained`, the first time after a breach).

`room_timer()` below is the single source of truth for the big GREEN/YELLOW/RED countdown the
SOC screen shows; achievements' store.py computes the identical thing from the same constants
(duplicated there with a comment back to here - no cross-module import between achievements and
ctf-range) so the bot and the countdown everyone watches can never disagree about the phase.
"""
import random

DWELL_SECONDS = 8 * 60          # S9 proposal: 8 minutes of recon-only before any ramp
RAMP_SECONDS = 10 * 60          # CTF-D18: 10 minute ramp from dwell end to detonation
RAMP_FLOOR = 7.5                # CTF-D18: "a floor well below 30s (starting guess 5-10s)"
DETONATE_JITTER = 60.0          # each student detonates up to this many seconds after the room
DELAY_MIN, DELAY_MAX = 30.0, 180.0
BENIGN_FRACTION = 0.15          # §8.6: a noise-only persona, flavor-assigned to ~1 in 7 students

# §8.2's traffic styles. `ceiling`: the most this style's attempts become the real payload
# DURING the ramp (before detonation, past which every attempt is the payload regardless of
# style - see Attacker.should_exploit). "benign" never escalates at all (§8.6).
STYLES = {
    "recon-heavy": {"ceiling": 0.15},     # mostly keeps scanning/header-grabbing even late
    "repeat-exploit": {"ceiling": 0.80},  # the same payload on a short fuse
    "variations": {"ceiling": 0.55},      # tries the exploit with small variations
    "benign": {"ceiling": 0.0},
}

# Flavor only (§8.2): never derived from a real IP or real geolocation - everything here is
# internal, synthetic traffic. Weighted toward a few commonly-cited regions, with real noise so
# it doesn't read as a single-country pile-on.
ORIGINS = (
    ("CN", 3), ("RU", 3), ("Eastern Europe", 2), ("US", 1), ("Other", 1),
)


def pick_origin(rng):
    pool, weights = zip(*ORIGINS)
    return rng.choices(pool, weights=weights, k=1)[0]


def pick_style(rng):
    if rng.random() < BENIGN_FRACTION:
        return "benign"
    styles = [s for s in STYLES if s != "benign"]
    return rng.choice(styles)


def room_phase(dwell_elapsed, ramp_seconds=RAMP_SECONDS):
    """GREEN/YELLOW/RED purely as a function of elapsed time since dwell end - the room-wide
    phase every student's countdown and the bot's own dwell-only gate (recon) agree on. A
    student's actual detonation also adds their own small jitter (Attacker.phase), so this is
    the room's shared floor, not any one student's exact moment."""
    if dwell_elapsed <= 0:
        return "green"
    if dwell_elapsed < ramp_seconds:
        return "yellow"
    return "red"


def room_timer(now, started_at, dwell_seconds=DWELL_SECONDS, ramp_seconds=RAMP_SECONDS):
    """{"phase", "seconds_remaining"} for the big SOC-screen countdown - green while dwelling,
    yellow through the ramp, red (0 remaining) once detonated. Mirrored in
    modules/achievements/service/store.py's Store.soc_timer() so the countdown matches the
    bot's own phase exactly without a cross-module import - DWELL_SECONDS/RAMP_SECONDS there
    must be kept equal to CTF_SOC_DWELL_SECONDS/CTF_SOC_RAMP_SECONDS here (module.env)."""
    dwell_elapsed = now - started_at - dwell_seconds
    phase = room_phase(dwell_elapsed, ramp_seconds)
    remaining = 0 if phase == "red" else max(0, int(dwell_seconds + ramp_seconds - (now - started_at)))
    return {"phase": phase, "seconds_remaining": remaining}


class Attacker:
    """One student's attacker, for the session's whole duration. `user` is who it targets -
    this object carries no target URL itself (bot.py maps user -> URL at request time, since
    that mapping is a deployment fact, not something the scheduler needs to know)."""

    def __init__(self, user, style, rng=None, ramp_seconds=RAMP_SECONDS):
        if style not in STYLES:
            raise ValueError(f"unknown persona style {style!r}")
        self.user = user
        self.style = style
        self.rng = rng or random.Random()
        self.ramp_seconds = ramp_seconds
        self.origin = pick_origin(self.rng)
        self.base_delay = self.rng.uniform(DELAY_MIN, DELAY_MAX)
        self.detonate_jitter = self.rng.uniform(0.0, DETONATE_JITTER)
        # Set the first time a dump_success fires, cleared the first time a later exploit
        # attempt against the same target comes back empty (the "contained" moment, §8.12).
        self.breached = False

    def phase(self, dwell_elapsed):
        if self.style == "benign" or dwell_elapsed <= 0:
            return "green" if dwell_elapsed <= 0 else "yellow"   # benign is never red (§8.6)
        if dwell_elapsed < self.ramp_seconds + self.detonate_jitter:
            return "yellow"
        return "red"

    def delay(self, dwell_elapsed):
        """Seconds to wait before the next attempt."""
        if dwell_elapsed <= 0 or self.style == "benign":
            return self.base_delay
        frac = min(1.0, dwell_elapsed / self.ramp_seconds)
        return self.base_delay + (RAMP_FLOOR - self.base_delay) * frac

    def should_exploit(self, dwell_elapsed):
        """Is THIS attempt the real payload, rather than a probe/recon variant?"""
        if self.style == "benign" or dwell_elapsed <= 0:
            return False
        if self.phase(dwell_elapsed) == "red":
            return True     # detonated: every attempt is the real payload from here on
        frac = min(1.0, dwell_elapsed / self.ramp_seconds)
        return self.rng.random() < STYLES[self.style]["ceiling"] * frac

    def force_exploit(self, exploit_fn):
        """Facilitator's "Inject" control (plan §8.5): the real payload, right now, bypassing
        this attacker's own delay and the ramp's exploit probability entirely - unlike
        `attempt()`, this is never a recon/probe outcome. Same breach/contained bookkeeping as
        `attempt()`, so an injected breach counts toward the wall of shame and the status light
        (8.10/8.12) exactly like one the regular schedule would have produced on its own."""
        if exploit_fn():
            self.breached = True
            return "dump_success"
        was_breached, self.breached = self.breached, False
        return "contained" if was_breached else "exploit_attempt"

    def attempt(self, dwell_elapsed, exploit_fn):
        """One attempt's outcome: ("recon"|"probe"|"exploit_attempt"|"dump_success"|"contained",
        {}). EXPLOIT_FN() -> True if the real payload would succeed right now; only called when
        this attempt rolls the real payload, so a recon/probe attempt never touches the
        target's exploit endpoint at all."""
        if dwell_elapsed <= 0:
            return "recon", {}
        if not self.should_exploit(dwell_elapsed):
            return "probe", {}
        if exploit_fn():
            self.breached = True
            return "dump_success", {}
        was_breached, self.breached = self.breached, False
        return ("contained" if was_breached else "exploit_attempt"), {}


class Swarm:
    """Every student's Attacker, on one shared clock. `started_at` is when the session's dwell
    clock began (not necessarily when the bot process started, so a restart mid-session can be
    told the real elapsed time instead of resetting to full dwell)."""

    def __init__(self, users, rng=None, started_at=0.0, dwell_seconds=DWELL_SECONDS, ramp_seconds=RAMP_SECONDS):
        self.rng = rng or random.Random()
        self.started_at = started_at
        self.dwell_seconds = dwell_seconds
        self.ramp_seconds = ramp_seconds
        self.attackers = [Attacker(u, pick_style(self.rng), self.rng, ramp_seconds=ramp_seconds) for u in users]

    def dwell_elapsed(self, now):
        return now - self.started_at - self.dwell_seconds

    def next_delay(self, attacker, now):
        return attacker.delay(self.dwell_elapsed(now))

    def attempt(self, attacker, now, exploit_fn):
        return attacker.attempt(self.dwell_elapsed(now), exploit_fn)

    def timer(self, now):
        return room_timer(now, self.started_at, self.dwell_seconds, self.ramp_seconds)
