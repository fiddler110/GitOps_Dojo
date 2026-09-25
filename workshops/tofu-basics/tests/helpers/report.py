#!/usr/bin/env python3
"""Summarises a load-test run directory (written by tests/load.sh) and judges it against thresholds.

    report.py RUN_DIR [--max-failures 0] [--max-p95-apply 120] [--max-portal-p95-ms 2000] [--max-readyz-failures 0]

Reads, all optional except steps.csv:
    steps.csv     user,step,start_ms,ms,rc,ok           one row per student per step (ok is 1/0)
    stats.csv     epoch,name,mem_bytes,mem_pct,cpu_pct,pids   container samples (podman stats)
    portal.csv    epoch,kind,who,status,ms              portal pollers (overview / progress / readyz)
    meta.env      key=value lines: students, wave_size, wave_gap, wall_s, ...
    limits.txt    "<container> <memory limit in bytes>" (0 = unlimited)
    peaks.txt     "<container> <kernel memory.peak in bytes>"
    oom.txt       "<container> oomkilled=<true|false> restarts_before=<n> restarts_after=<n> oom_kill_before=<n> oom_kill_after=<n>"
    failures/     one file per failed step: the tail of its output (already masked)
Prints the report, and exits 0 if every threshold passed, 1 if any failed, 2 if the run has no step data.
"""
import argparse
import csv
import os
import sys

STEPS_FOR_THRESHOLD = ("apply",)  # the p95 bound is checked on these steps


def percentile(values, q):
    """Linear interpolation between closest ranks (the usual 'p95'); q in 0..100."""
    if not values:
        return None
    v = sorted(values)
    if len(v) == 1:
        return v[0]
    pos = (len(v) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def read_kv(path):
    out = {}
    if os.path.exists(path):
        for line in open(path):
            if "=" in line:
                k, _, v = line.strip().partition("=")
                out[k] = v
    return out


def read_pairs(path):
    out = {}
    if os.path.exists(path):
        for line in open(path):
            parts = line.split()
            if len(parts) >= 2:
                out[parts[0]] = parts[1:]
    return out


def fnum(text, default=None):
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def gb(nbytes):
    return f"{nbytes / 1e9:.2f} GB"


def fmt(x, unit="s", digits=1):
    return "-" if x is None else f"{x:.{digits}f}{unit}"


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--max-failures", type=int, default=0)
    ap.add_argument("--max-p95-apply", type=float, default=120.0)
    ap.add_argument("--max-portal-p95-ms", type=float, default=2000.0)
    ap.add_argument("--max-readyz-failures", type=int, default=0)
    args = ap.parse_args(argv)
    d = args.run_dir

    steps = read_csv(os.path.join(d, "steps.csv"))
    if not steps:
        print("report: no step data in", d)
        return 2
    meta = read_kv(os.path.join(d, "meta.env"))
    verdicts = []  # (ok, text)

    print("== Load test report")
    print(f"   run dir:  {d}")
    print(f"   students: {meta.get('students', '?')}   wave size: {meta.get('wave_size', '?')} "
          f"(gap {meta.get('wave_gap', '?')} s)   flows took {meta.get('wall_s', '?')} s wall time "
          f"(total run incl. setup and cleanup is longer)")

    # ---- per-step latency -------------------------------------------------------------------------------------------
    order = []
    by_step = {}
    for r in steps:
        s = r["step"]
        if s not in by_step:
            order.append(s)
        by_step.setdefault(s, []).append(r)
    print("\n-- Steps: wall time per student, seconds")
    print(f"   {'step':<12} {'n':>3} {'ok':>3} {'fail':>4} {'p50':>7} {'p95':>7} {'max':>7}")
    failed_rows = []
    for s in order:
        rows = by_step[s]
        secs = [fnum(r["ms"], 0) / 1000.0 for r in rows]
        ok = sum(1 for r in rows if r["ok"] == "1")
        failed_rows += [r for r in rows if r["ok"] != "1"]
        print(f"   {s:<12} {len(rows):>3} {ok:>3} {len(rows) - ok:>4} {fmt(percentile(secs, 50)):>7} "
              f"{fmt(percentile(secs, 95)):>7} {fmt(max(secs)):>7}")

    # ---- failures ---------------------------------------------------------------------------------------------------
    print(f"\n-- Failures: {len(failed_rows)}")
    for r in failed_rows:
        print(f"   {r['user']} step '{r['step']}' (exit status {r['rc']}, {fnum(r['ms'], 0) / 1000:.1f} s)")
        log = os.path.join(d, "failures", f"{r['user']}-{r['step']}.log")
        if os.path.exists(log):
            for line in open(log).read().splitlines()[-12:]:
                print(f"       | {line}")
    verdicts.append((len(failed_rows) <= args.max_failures,
                     f"failed steps: {len(failed_rows)} (allowed {args.max_failures})"))

    apply_secs = [fnum(r["ms"], 0) / 1000.0 for s in STEPS_FOR_THRESHOLD for r in by_step.get(s, [])]
    p95a = percentile(apply_secs, 95)
    if apply_secs:
        verdicts.append((p95a <= args.max_p95_apply,
                         f"p95 apply latency {p95a:.1f} s (limit {args.max_p95_apply:g} s, n={len(apply_secs)})"))
    else:
        verdicts.append((False, "no apply step ran, so there is no p95 apply latency to judge"))

    # ---- containers -------------------------------------------------------------------------------------------------
    stats = read_csv(os.path.join(d, "stats.csv"))
    limits, peaks = read_pairs(os.path.join(d, "limits.txt")), read_pairs(os.path.join(d, "peaks.txt"))
    print("\n-- Container memory and CPU (podman stats, sampled about every 2 s during the run)")
    if not stats:
        print("   no samples")
    else:
        names = sorted({r["name"] for r in stats})
        print(f"   {'container':<22} {'samples':>7} {'peak mem':>10} {'of limit':>9} {'kernel peak*':>13} {'peak cpu':>9} {'peak pids':>9}")
        for n in names:
            rows = [r for r in stats if r["name"] == n]
            mem = [fnum(r["mem_bytes"], 0) for r in rows]
            cpu = [fnum(r["cpu_pct"], 0) for r in rows]
            pids = [fnum(r["pids"], 0) for r in rows]
            limit = fnum((limits.get(n) or ["0"])[0], 0)
            kp = fnum((peaks.get(n) or [""])[0])
            of = f"{100 * max(mem) / limit:.0f}%" if limit else "no limit"
            print(f"   {n:<22} {len(rows):>7} {gb(max(mem)):>10} {of:>9} {(gb(kp) if kp else '-'):>13} "
                  f"{max(cpu):>8.0f}% {max(pids):>9.0f}")
        print("   * kernel peak = memory.peak of the container's cgroup since the CONTAINER started (not just this run)")
    oom = read_pairs(os.path.join(d, "oom.txt"))
    bad = []
    for n, parts in oom.items():
        kv = dict(p.split("=", 1) for p in parts if "=" in p)
        if kv.get("oomkilled") == "true":
            bad.append(f"{n} was OOM-killed")
        if kv.get("restarts_after") and kv.get("restarts_before") and kv["restarts_after"] != kv["restarts_before"]:
            bad.append(f"{n} restarted ({kv['restarts_before']} -> {kv['restarts_after']})")
        ob, oa = fnum(kv.get("oom_kill_before")), fnum(kv.get("oom_kill_after"))
        if ob is not None and oa is not None and oa > ob:
            bad.append(f"{n}: the kernel OOM-killed {int(oa - ob)} process(es) inside it (memory.events oom_kill)")
    if oom:
        verdicts.append((not bad, "no container was OOM-killed or restarted, and no process inside was OOM-killed" if not bad else "; ".join(bad)))

    # ---- the portal under load --------------------------------------------------------------------------------------
    portal = read_csv(os.path.join(d, "portal.csv"))
    print("\n-- Portal and readiness, polled from inside cloud-api while the students worked")
    if not portal:
        print("   no samples")
    else:
        print(f"   {'kind':<10} {'n':>5} {'non-200':>8} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
        for kind in ("overview", "progress", "readyz"):
            rows = [r for r in portal if r["kind"] == kind]
            if not rows:
                continue
            ms = [fnum(r["ms"], 0) for r in rows]
            bad_n = sum(1 for r in rows if r["status"] != "200")
            print(f"   {kind:<10} {len(rows):>5} {bad_n:>8} {fmt(percentile(ms, 50), '', 0):>8} "
                  f"{fmt(percentile(ms, 95), '', 0):>8} {fmt(max(ms), '', 0):>8}")
        ov = [fnum(r["ms"], 0) for r in portal if r["kind"] == "overview" and r["status"] == "200"]
        if ov:
            p = percentile(ov, 95)
            verdicts.append((p <= args.max_portal_p95_ms,
                             f"p95 class-overview latency {p:.0f} ms (limit {args.max_portal_p95_ms:g} ms, n={len(ov)})"))
        rz = [r for r in portal if r["kind"] == "readyz" and r["status"] != "200"]
        verdicts.append((len(rz) <= args.max_readyz_failures,
                         f"/readyz non-200 samples: {len(rz)} (allowed {args.max_readyz_failures})"))

    # ---- verdict ----------------------------------------------------------------------------------------------------
    print("\n-- Verdict")
    for ok, text in verdicts:
        print(f"   {'PASS' if ok else 'FAIL'}  {text}")
    all_ok = all(ok for ok, _ in verdicts)
    print(f"\n   LOAD RESULT: {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
