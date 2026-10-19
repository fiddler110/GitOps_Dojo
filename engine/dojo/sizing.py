"""The student terminal's resource limits: who may set them, and how many processes a class needs.

  * Floors. WEB_TERMINAL_PIDS_LIMIT, WEB_TERMINAL_MEM_LIMIT and WEB_TERMINAL_PIDS_PER_STUDENT
    are the operator's sizing for this machine. A workshop.env or module.env may raise them
    (a pack that needs more), never lower them: the pack can't know the machine or the class.
  * The class's need. All students share one terminal container, so its pids cap has to cover
    every account at once: (STUDENT_COUNT + demo bots + the facilitator) x the per-student need,
    plus a base for the platform's own processes. A start raises the cap to that and says so.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

FLOOR_KEYS = ("WEB_TERMINAL_PIDS_LIMIT", "WEB_TERMINAL_MEM_LIMIT", "WEB_TERMINAL_PIDS_PER_STUDENT")
PIDS_BASE = 200              # workspace-control, the reaper, sshd/ttyd parents and the like
PIDS_PER_STUDENT = 50        # used when no layer sets WEB_TERMINAL_PIDS_PER_STUDENT
STUDENT_COUNT_DEFAULT = 30   # what the compose files assume when STUDENT_COUNT is unset


def mem_mb(value: str) -> Optional[int]:
    """'6g' -> 6144; None when it isn't a size."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([kmgt]?)b?\s*", (value or "").lower())
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2)
    return int(n * {"": 1 / 1048576, "k": 1 / 1024, "m": 1, "g": 1024, "t": 1048576}[unit])


def _size(key: str, value: str) -> Optional[float]:
    if key == "WEB_TERMINAL_MEM_LIMIT":
        return mem_mb(value)
    return int(value) if (value or "").strip().isdigit() else None


def lowered(key: str, operator: str, final: str) -> bool:
    """True when a later layer set key below the operator's value (both must parse)."""
    a, b = _size(key, operator), _size(key, final)
    return a is not None and b is not None and b < a


def _int(env: Dict[str, str], key: str, default: int) -> int:
    v = (env.get(key) or "").strip()
    return int(v) if v.isdigit() else default


def class_pids(env: Dict[str, str], bots: int = 0) -> Tuple[int, str]:
    """(pids the class needs, how that was worked out)."""
    accounts = _int(env, "STUDENT_COUNT", STUDENT_COUNT_DEFAULT) + bots + 1
    per = _int(env, "WEB_TERMINAL_PIDS_PER_STUDENT", PIDS_PER_STUDENT)
    return accounts * per + PIDS_BASE, f"{accounts} accounts x {per} + {PIDS_BASE}"


def fit_pids(env: Dict[str, str], bots: int = 0) -> str:
    """Raise env's WEB_TERMINAL_PIDS_LIMIT to what the class needs. Returns what changed, or ""."""
    need, how = class_pids(env, bots)
    have = _int(env, "WEB_TERMINAL_PIDS_LIMIT", 0)
    if have >= need:
        return ""
    env["WEB_TERMINAL_PIDS_LIMIT"] = str(need)
    return f"Terminal pids cap raised from {have or 'unset'} to {need} ({how})."
