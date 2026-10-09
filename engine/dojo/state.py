"""What this checkout last started, a history of runs, and the run lock.

.build-state/current.json   the stack a start brought up: workshop, its flags,
                            the extra -f files, the --env name, when. Written
                            when containers are about to start; `stop` deletes it.
.build-state/history.jsonl  one line per start, restart, build or stop: when, what,
                            how long, the result. For "it worked last week".

A stack started by the old shell dojo left .last-overlay,
.build-state/running-workshop and .build-state/last-start instead; read_current
still understands those, and the next start replaces them.
"""
from __future__ import annotations

import json
import os
import shlex
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import paths

CURRENT = paths.STATE / "current.json"
HISTORY = paths.STATE / "history.jsonl"
LEGACY = (paths.LAST_OVERLAY, paths.RUNNING_WORKSHOP, paths.LAST_START)


@dataclass
class Current:
    workshop: str
    args: List[str] = field(default_factory=list)   # the flags after the workshop name
    files: List[str] = field(default_factory=list)  # extra -f files, relative to engine/
    env_name: Optional[str] = None
    started_at: float = 0.0

    @property
    def command(self) -> str:
        return "./dojo " + " ".join(shlex.quote(a) for a in [self.workshop, *self.args])


def write_current(cur: Current) -> None:
    paths.STATE.mkdir(exist_ok=True)
    tmp = CURRENT.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(cur), indent=2) + "\n")
    tmp.replace(CURRENT)
    # Last-start lets `restart` work even after `stop` removed current.json.
    paths.LAST_START.write_text(" ".join(shlex.quote(a) for a in [cur.workshop, *cur.args]) + "\n")
    for old in (paths.LAST_OVERLAY, paths.RUNNING_WORKSHOP):
        old.unlink(missing_ok=True)


def read_current() -> Optional[Current]:
    if CURRENT.is_file():
        try:
            return Current(**json.loads(CURRENT.read_text()))
        except (ValueError, TypeError):
            return None
    workshop = paths.RUNNING_WORKSHOP.read_text().strip() if paths.RUNNING_WORKSHOP.is_file() else ""
    if not workshop and not paths.LAST_OVERLAY.is_file():
        return None
    files = [l for l in paths.LAST_OVERLAY.read_text().splitlines() if l.strip()] if paths.LAST_OVERLAY.is_file() else []
    last = last_start()
    args = last[1:] if last and last[0] == workshop else []
    return Current(workshop or "", args, files, _env_name(args))


def clear_current() -> None:
    CURRENT.unlink(missing_ok=True)
    for old in (paths.LAST_OVERLAY, paths.RUNNING_WORKSHOP):
        old.unlink(missing_ok=True)


def last_start() -> List[str]:
    """[workshop, *flags] of the last real start from this checkout, [] if none."""
    if not paths.LAST_START.is_file():
        return []
    return shlex.split(paths.LAST_START.read_text())


def _env_name(args: List[str]) -> Optional[str]:
    for i, a in enumerate(args):
        if a == "--env" and i + 1 < len(args):
            return args[i + 1]
        if a.startswith("--env="):
            return a.split("=", 1)[1]
    return None


def record(action: str, workshop: str, args: List[str], seconds: float, result: str) -> None:
    paths.STATE.mkdir(exist_ok=True)
    line = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "action": action, "workshop": workshop,
            "args": args, "seconds": round(seconds, 1), "result": result}
    with HISTORY.open("a") as fh:
        fh.write(json.dumps(line) + "\n")


class LockBusy(Exception):
    pass


# Seconds a lock directory may sit without a pid file before it counts as left
# behind by a crash.
STALE_EMPTY_LOCK = 10


class RunLock:
    """One build or start at a time per user. Two at once (two terminals, or the
    main tree and a git worktree) share image tags, container names and volumes.
    In /tmp, not $TMPDIR, so every shell agrees; a lock whose process is gone
    (kill -9, a closed WSL window) is reclaimed."""

    def __init__(self, what: str) -> None:
        self.dir = Path(f"/tmp/gitops-dojo-{os.getuid()}.lock")
        self.what = what
        self.held = False

    @classmethod
    def peek(cls) -> Optional[Dict[str, Any]]:
        """Current lock holder, if any. Returns {pid, what, started_at} when
        a run is in flight, None otherwise. `dojo status` reads this so a
        start-in-progress shows up alongside the running containers."""
        d = Path(f"/tmp/gitops-dojo-{os.getuid()}.lock")
        if not d.is_dir():
            return None
        pid = (d / "pid").read_text().strip() if (d / "pid").is_file() else ""
        if pid and not _alive(pid):
            return None  # stale lock -- the next acquire will clear it
        what = (d / "what").read_text().strip() if (d / "what").is_file() else ""
        try:
            started_at = d.stat().st_mtime
        except OSError:
            started_at = 0.0
        return {"pid": pid, "what": what, "started_at": started_at}

    def acquire(self) -> None:
        try:
            self.dir.mkdir()
        except FileExistsError:
            pid = (self.dir / "pid").read_text().strip() if (self.dir / "pid").is_file() else ""
            # No pid yet is a start in its first instant, unless it has stayed
            # that way: a crash between mkdir and the pid write leaves it so.
            fresh = not pid and time.time() - self._mtime() < STALE_EMPTY_LOCK
            if fresh or (pid and _alive(pid)):
                what = (self.dir / "what").read_text().strip() if (self.dir / "what").is_file() else "just started"
                raise LockBusy(f"Another ./dojo is building or starting a stack: {what}.\n"
                               f"Wait for it to finish. If none is running, remove {self.dir} and try again.")
            for f in self.dir.iterdir():
                f.unlink()
            self.dir.rmdir()
            self.dir.mkdir()
        self.held = True
        (self.dir / "pid").write_text(f"{os.getpid()}\n")
        (self.dir / "what").write_text(f"pid {os.getpid()}, {self.what}, from {paths.REPO}\n")

    def _mtime(self) -> float:
        try:
            return self.dir.stat().st_mtime
        except OSError:
            return 0.0

    def release(self) -> None:
        if self.held:
            for f in self.dir.glob("*"):
                f.unlink(missing_ok=True)
            try:
                self.dir.rmdir()
            except OSError:
                pass
            self.held = False

    def __enter__(self) -> "RunLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def _alive(pid: str) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True
