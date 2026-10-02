"""A workshop's Compose files and services."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List

from . import paths
from .envfiles import Resolution
from .runtime import Runtime


def extra_files(res: Resolution) -> List[str]:
    """The -f files after docker-compose.yml, relative to engine/ as run.sh writes
    them: each module's compose.yml in MODULES order, then the workshop overlay."""
    files = [f"../modules/{m}/compose.yml" for m in res.modules
             if (paths.MODULES / m / "compose.yml").is_file()]
    overlay = res.env.get("COMPOSE_OVERLAY", "")
    if overlay:
        files.append(overlay)
    return files


def compose_args(files: List[str]) -> List[str]:
    args = ["-f", "docker-compose.yml"]
    for f in files:
        args += ["-f", f]
    return args


def services(rt: Runtime, files: List[str], env: Dict[str, str]) -> List[str]:
    """This stack's Compose services; raises with Compose's own message if the
    merged config doesn't load."""
    res = subprocess.run([*rt.compose_cmd, *compose_args(files), "config", "--services"],
                         cwd=str(paths.ENGINE), env=env, capture_output=True, text=True, timeout=120)
    names = res.stdout.split()
    if res.returncode != 0 or not names:
        raise RuntimeError((res.stderr or res.stdout).strip() or "compose config printed no services")
    return names


def read_state(path: Path) -> str:
    return path.read_text().strip() if path.is_file() else ""
