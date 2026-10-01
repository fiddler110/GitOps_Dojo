"""Where things live. Everything is relative to this checkout, so a git worktree
beside the repo has its own state."""
from __future__ import annotations

from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
REPO = ENGINE.parent
WORKSHOPS = REPO / "workshops"
MODULES = REPO / "modules"

ENV_FILE = ENGINE / ".env"
STATE = ENGINE / ".build-state"
LAST_OVERLAY = ENGINE / ".last-overlay"       # teardown's -f files (one per line)
RUNNING_WORKSHOP = STATE / "running-workshop"
LAST_START = STATE / "last-start"             # the workshop and its flags, for restart


def env_variant(name: str) -> Path:
    """engine/.env.<name>, loaded on top of engine/.env by --env NAME."""
    return ENGINE / f".env.{name}"
