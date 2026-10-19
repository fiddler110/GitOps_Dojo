#!/usr/bin/env python3
"""Summarise a ctf-defend pilot so the stagger and dwell can be tuned (docs/CTF-PILOT.md).

Reads the achievements admin state (GET /achievements-admin/api/state) from a file or stdin and prints,
per target, how long people took to fix a breach, how far apart each student's breaches landed and how
many were unfixed at once, then a suggested CTF_TARGET_STAGGER. Stdlib only; run it with python3 -B -I.
"""
import json
import statistics
import sys

DWELL_S = 480          # CTF_DWELL_S default; pass --dwell N when the pilot ran with another value
RULE = 0.5             # starting rule from the plan: stagger interval = half the median fix time


def load(argv):
    dwell, path = DWELL_S, None
    it = iter(argv)
    for a in it:
        if a == "--dwell":
            dwell = int(next(it))
        else:
            path = a
    text = open(path).read() if path and path != "-" else sys.stdin.read()
    return dwell, json.loads(text).get("target_status", [])


def fmt(sec):
    return "-" if sec is None else "%dm%02ds" % divmod(int(round(sec)), 60)


def peak_open(rows):
    """Most breaches of one student that were unfixed at the same moment."""
    events = sorted([(r["breached_at"], 1) for r in rows] +
                    [(r["fixed_at"], -1) for r in rows if r["fixed_at"] is not None])
    cur = best = 0
    for _, d in events:
        cur += d
        best = max(best, cur)
    return best


def main(argv):
    dwell, rows = load(argv)
    if not rows:
        print("no target_status rows: the swarm has not breached anyone yet")
        return 1
    print("%-16s %5s %5s %8s %8s %8s" % ("target", "hit", "fixed", "median", "mean", "slowest"))
    allfix = []
    for t in sorted({r["challenge"] for r in rows}):
        rs = [r for r in rows if r["challenge"] == t]
        fx = [r["mttp"] for r in rs if r["mttp"] is not None]
        allfix += fx
        print("%-16s %5d %5d %8s %8s %8s" % (t, len(rs), len(fx),
              fmt(statistics.median(fx)) if fx else "-", fmt(statistics.mean(fx)) if fx else "-",
              fmt(max(fx)) if fx else "-"))
    print("\n%-16s %-30s %s" % ("student", "gaps between breaches", "peak unfixed"))
    gaps_all = []
    for u in sorted({r["user"] for r in rows}):
        rs = sorted((r for r in rows if r["user"] == u), key=lambda r: r["breached_at"])
        gaps = [b["breached_at"] - a["breached_at"] for a, b in zip(rs, rs[1:])]
        gaps_all += gaps
        print("%-16s %-30s %d" % (u, ", ".join(fmt(g) for g in gaps) or "-", peak_open(rs)))
    if allfix:
        med = statistics.median(allfix)
        print("\nmedian time to fix %s over %d fixes; observed median gap %s (dwell %ds)"
              % (fmt(med), len(allfix), fmt(statistics.median(gaps_all)) if gaps_all else "-", dwell))
        print("suggested CTF_TARGET_STAGGER=%.2f  (%.1f x median fix %s / dwell %ds)"
              % (RULE * med / dwell, RULE, fmt(med), dwell))
    else:
        print("\nnobody fixed anything yet; no stagger suggestion")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
