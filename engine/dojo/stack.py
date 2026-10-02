"""A workshop's Compose files and services."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


_UNITS = {"b": 1 / 1048576, "k": 1 / 1024, "m": 1, "g": 1024}


def _mb(value: str) -> Optional[int]:
    """`512m`, `3g`, `2048k` or bytes as whole MB; None if it isn't a size."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([bkmg])?b?", value.strip().strip("'\"").lower())
    return int(float(m.group(1)) * _UNITS[m.group(2) or "b"]) if m else None


def parse_mem_limits(config: str) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """From `compose config` YAML: ({service: mem_limit in MB, or None when it has none}, one-shot
    services). A one-shot job (`restart: "no"`) exits once the stack is up, so it holds no memory."""
    limits: Dict[str, Optional[int]] = {}
    oneshot: List[str] = []
    in_services, svc = False, None
    for line in config.splitlines():
        if re.match(r"\S", line):
            in_services, svc = line.rstrip() == "services:", None
        elif in_services and re.match(r"  [^ #][^:]*:\s*$", line):
            svc = line.strip().rstrip(":")
            limits[svc] = None
        elif svc and line.startswith("    mem_limit:"):
            limits[svc] = _mb(line.split(":", 1)[1])
        elif svc and re.match(r"    restart:\s*['\"]?no['\"]?\s*$", line):
            oneshot.append(svc)
    return limits, oneshot


def mem_limits(rt: Runtime, files: List[str], env: Dict[str, str]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """This stack's services' memory limits (see parse_mem_limits); raises with Compose's message."""
    res = subprocess.run([*rt.compose_cmd, *compose_args(files), "config"],
                         cwd=str(paths.ENGINE), env=env, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout).strip() or "compose config failed")
    return parse_mem_limits(res.stdout)


def read_state(path: Path) -> str:
    return path.read_text().strip() if path.is_file() else ""
