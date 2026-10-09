"""`dojo test`: the fast-bot check of one workshop, start to stop, with a verdict.

Starts `WORKSHOP --test N --fast`, waits for every bot's ~/.dojo-bot-done, reports
which bots finished and which steps they skipped, then stops the stack (always,
even on failure or Ctrl-C, unless --keep). --matrix KEY=a,b repeats the whole
sequence per value with KEY=value exported."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .runtime import Runtime
from .stackapi import StackError, find_container, project

MARKERS = 'ls /home/testuser*/.dojo-bot-done 2>/dev/null | wc -l'
SKIPS = 'grep -hE "FAST: .*(skipping it|still not ready)" /home/testuser*/.dojo-bot.log 2>/dev/null | head -20'


@dataclass
class RunResult:
    label: str
    ok: bool = False
    started: bool = False
    done: int = 0
    bots: int = 0
    seconds: float = 0.0
    skips: List[str] = field(default_factory=list)
    note: str = ""


def parse_matrix(spec: Optional[str]) -> Optional[Tuple[str, List[str]]]:
    if not spec:
        return None
    key, eq, vals = spec.partition("=")
    values = [v for v in vals.split(",") if v != ""]
    if not eq or not key.isidentifier() or not values:
        raise ValueError(f"--matrix expects KEY=value1,value2 (got '{spec}')")
    return key, values


def count_done(rt: Runtime) -> int:
    try:
        c = find_container(rt, "web-terminal", need_ready=False)
    except StackError:
        return 0
    res = rt.run("exec", c.name, "sh", "-c", MARKERS)
    return int(res.stdout.strip() or 0) if res.returncode == 0 and res.stdout.strip().isdigit() else 0


def skipped_steps(rt: Runtime) -> List[str]:
    try:
        c = find_container(rt, "web-terminal", need_ready=False)
    except StackError:
        return []
    res = rt.run("exec", c.name, "sh", "-c", SKIPS)
    return [l.strip() for l in res.stdout.splitlines() if l.strip()] if res.returncode == 0 else []


def wait_for_bots(rt: Runtime, bots: int, timeout: float, clock=time.monotonic, sleep=time.sleep, interval: float = 10.0,
                  on_progress: Optional[Callable[[int], None]] = None) -> int:
    """Poll the done markers until `bots` of them exist or the timeout; the count reached."""
    t0, n, last = clock(), 0, -1
    while True:
        n = count_done(rt)
        if on_progress and n != last:
            on_progress(n)
            last = n
        if n >= bots or clock() - t0 >= timeout:
            return n
        sleep(interval)


def run_matrix(workshop: str, bots: int, matrix: Optional[Tuple[str, List[str]]], keep: bool, timeout: float,
               env_name: Optional[str], start: Callable, stop: Callable, rt: Runtime,
               say: Callable[[str], None] = print, wait=wait_for_bots) -> List[RunResult]:
    """One run per matrix value (one plain run without). The stack is stopped after every run, except the
    last when `keep`. `start(workshop, bots, env_name) -> exit code`, `stop() -> exit code`."""
    runs = [(f"{matrix[0]}={v}", matrix[0], v) for v in matrix[1]] if matrix else [("default", None, None)]
    results: List[RunResult] = []
    for i, (label, key, value) in enumerate(runs):
        r = RunResult(label, bots=bots)
        results.append(r)
        saved = os.environ.get(key) if key else None
        if key:
            os.environ[key] = value
        t0 = time.monotonic()
        try:
            say(f"==> {label}: starting {workshop} with {bots} fast bot(s)")
            rc = start(workshop, bots, env_name)
            r.started = rc == 0
            if not r.started:
                r.note = f"start exited {rc}"
            else:
                r.done = wait(rt, bots, timeout, on_progress=lambda n: say(f"    bots done: {n} of {bots}"))
                r.skips = skipped_steps(rt)
                r.ok = r.done >= bots
                if not r.ok:
                    r.note = f"timed out after {timeout / 60:.0f} min with {r.done} of {bots} bots done"
        except KeyboardInterrupt:
            r.note = "interrupted"
            _finish(r, t0, key, saved)
            if not (keep and i == len(runs) - 1):
                stop()
            raise
        except Exception as exc:   # report it, but still tear down
            r.note = f"{type(exc).__name__}: {exc}"
        _finish(r, t0, key, saved)
        if not (keep and i == len(runs) - 1):
            say(f"==> {label}: stopping")
            stop()
    return results


def _finish(r: RunResult, t0: float, key: Optional[str], saved: Optional[str]) -> None:
    r.seconds = time.monotonic() - t0
    if key:
        if saved is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved
