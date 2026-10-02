"""Where things live. Everything is relative to this checkout, so a git worktree
beside the repo has its own state."""
from __future__ import annotations

import os
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

# How the user ran us, for help and advice: ./run.sh, or `dojo` (the ~/.local/bin script sets DOJO_PROG).
PROG = os.environ.get("DOJO_PROG", "./run.sh")


def env_variant(name: str) -> Path:
    """engine/.env.<name>, loaded on top of engine/.env by --env NAME."""
    return ENGINE / f".env.{name}"
