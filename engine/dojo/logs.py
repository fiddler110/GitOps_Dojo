"""`dojo logs` beyond one service: all services, a time window, a filter, and an error scan."""
from __future__ import annotations

import re
import subprocess
import threading
from typing import Dict, List, Optional, Tuple

from .runtime import Container, Runtime

ERROR_RE = re.compile(r"Traceback|\bERROR\b|\bpanic\b|Exception")
COLOURS = ["cyan", "green", "yellow", "magenta", "blue", "bright_cyan", "bright_green", "bright_magenta", "bright_yellow"]
_TS = re.compile(r"^(\d{4}-\d\d-\d\dT[\d:.]+)\S*\s?")


def fetch(rt: Runtime, c: Container, tail: str = "all", since: Optional[str] = None) -> List[Tuple[str, str]]:
    """[(timestamp, line)] of a container's log (stdout and stderr), oldest first."""
    args = ["logs", "--timestamps", *(["--since", since] if since else []), *([] if tail == "all" else ["--tail", tail]), c.name]
    try:
        res = rt.run(*args, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = []
    for line in (res.stdout + res.stderr).splitlines():
        m = _TS.match(line)
        rows.append((m.group(1), line[m.end():]) if m else ("", line))
    rows.sort(key=lambda r: r[0])
    return rows


def merged(logs: Dict[str, List[Tuple[str, str]]]) -> List[Tuple[str, str, str]]:
    """(service, timestamp, line) across services, in time order."""
    rows = [(svc, ts, line) for svc, lines in logs.items() for ts, line in lines]
    rows.sort(key=lambda r: r[1])
    return rows


def grep_filter(rows, pattern: Optional[str]):
    if not pattern:
        return rows
    rx = re.compile(pattern)
    return [r for r in rows if rx.search(r[-1])]


def scan_errors(logs: Dict[str, List[Tuple[str, str]]]) -> Dict[str, Dict]:
    """Per service with any hit: {count, last, sample (first 3)}."""
    out = {}
    for svc, lines in logs.items():
        hits = [line for _, line in lines if ERROR_RE.search(line)]
        if hits:
            out[svc] = {"count": len(hits), "last": hits[-1], "sample": hits[:3]}
    return out


def follow(rt: Runtime, containers: List[Container], tail: str, since: Optional[str], emit, pattern: Optional[str]) -> None:
    """Stream every container's log through emit(service, line) until interrupted."""
    rx = re.compile(pattern) if pattern else None
    procs = []

    def pump(c: Container) -> None:
        cmd = [rt.cli, "logs", "-f", "--tail", tail, *(["--since", since] if since else []), c.name]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        procs.append(p)
        for line in p.stdout:
            line = line.rstrip("\n")
            if not rx or rx.search(line):
                emit(c.service, line)

    threads = [threading.Thread(target=pump, args=(c,), daemon=True) for c in containers]
    try:
        for t in threads:
            t.start()
        for t in threads:
            while t.is_alive():
                t.join(0.5)
    finally:
        for p in procs:
            p.terminate()
