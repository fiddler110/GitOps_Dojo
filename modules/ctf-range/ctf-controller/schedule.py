"""Defend schedule: which target order each student gets and when each target
starts. Pure functions (no I/O, no clock) so the dealing is testable.

Every permutation of the targets (6 for three targets) is shuffled once by the
seed and dealt to students round-robin by roster index, so any class gets each
permutation within one student of every other (20 students: 3 or 4 each) and,
over a full cycle of permutations, every target appears equally often in every
position. The same seed always yields the same schedule.
"""
import hashlib
import itertools
import random

DEFAULT_SEVERITY = {"customer-portal": "high", "policy-bypass": "medium", "leaky-config": "low"}
DEFAULT_WEIGHT = {"customer-portal": 3, "policy-bypass": 2, "leaky-config": 1}


def permutations(targets, seed):
    """All orderings of `targets`, shuffled deterministically by `seed`."""
    perms = [list(p) for p in itertools.permutations(targets)]
    # Seed through sha256 so any string works and the result does not depend on
    # the interpreter's hash randomisation.
    rng = random.Random(int.from_bytes(hashlib.sha256(str(seed).encode()).digest()[:8], "big"))
    rng.shuffle(perms)
    return perms


def deal(users, targets, seed):
    """{user: [target, ...]} round-robin over the shuffled permutations."""
    if not targets:
        return {u: [] for u in users}
    perms = permutations(targets, seed)
    return {u: list(perms[i % len(perms)]) for i, u in enumerate(users)}


def rows_for(order, targets, dwell_s, stagger, severity=None, weight=None):
    """Schedule rows for one student's `order`. `index` is the target's
    position in the configured `targets` list (the port/slot index)."""
    severity = severity or DEFAULT_SEVERITY
    weight = weight or DEFAULT_WEIGHT
    out = []
    for pos, t in enumerate(order):
        out.append({
            "target": t,
            "index": targets.index(t),
            "severity": severity.get(t, "medium"),
            "weight": weight.get(t, 1),
            "start_offset_s": int(round(pos * stagger * dwell_s)),
        })
    return out


def build(users, targets, seed, dwell_s, stagger, t0=None):
    dealt = deal(users, targets, seed)
    return {
        "seed": seed, "t0": t0, "dwell_s": dwell_s, "stagger": stagger,
        "users": {u: rows_for(o, targets, dwell_s, stagger) for u, o in dealt.items()},
    }
