"""Loading the optional local .env file.

Nothing in this repo needs .env to work: dnscontrol reads the PowerDNS API
URL and key from creds.json, and the Forgejo commands reuse your git login.
.env only holds optional per-person settings (e.g. FORGEJO_TOKEN) and is
git-ignored, so a real secret put there never reaches a commit."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path) -> dict:
    """Minimal KEY=VALUE .env parser. No external dependency required."""
    env = {}
    if not path.is_file():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            env[key] = value
    return env


def apply_env_file(path: Path) -> None:
    """Export .env's values into this process's environment, so dnscontrol
    and the Forgejo client both see them. A variable already set in the
    shell wins over .env."""
    for key, value in load_env_file(path).items():
        os.environ.setdefault(key, value)
