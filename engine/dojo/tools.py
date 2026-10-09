"""Small stack tools: `exec`/`shell`, `urls`, `open`, `wait`, `version`."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from . import paths, state
from .envfiles import mask, operator_env
from .runtime import PROBLEM, READY, Runtime
from .stackapi import StackError, find_container, project

DEFAULT_SHELL = ["sh", "-c", "command -v bash >/dev/null 2>&1 && exec bash || exec sh"]


def exec_argv(rt: Runtime, service: str, cmd: List[str], tty: Optional[bool] = None) -> List[str]:
    """The `podman exec` command line for SERVICE: an interactive shell when CMD is empty."""
    c = find_container(rt, service, need_ready=False)
    if c.state in PROBLEM + ("waiting",):
        raise StackError(f"'{service}' is {c.state}; there is nothing to exec into.")
    tty = sys.stdin.isatty() if tty is None else tty
    return [rt.cli, "exec", "-i", *(["-t"] if tty else []), c.name, *(cmd or DEFAULT_SHELL)]


# --- urls ----------------------------------------------------------------------------
def _login_password(env: Dict[str, str], key: str) -> str:
    """Shown only when it is a public default anyone can know; otherwise its length."""
    from .checks import is_default_password
    value = env.get(key, "")
    return value if is_default_password(value) else mask(key, value)


def urls() -> Dict[str, Any]:
    cur = state.read_current()
    env = operator_env(cur.env_name if cur else None)
    base = (env.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if not base:
        raise StackError("No PUBLIC_BASE_URL is configured (dojo.toml [network]).")
    return {
        "workshop": cur.workshop if cur else None,
        "student": base + "/",
        "admin": base + "/admin",
        "slides": base + "/slides/",
        "logins": {
            "class": {"username": env.get("TTYD_USERNAME", "student"), "password": _login_password(env, "TTYD_PASSWORD")},
            "facilitator": {"username": env.get("FACILITATOR_USERNAME", "root"),
                            "password": _login_password(env, "FACILITATOR_PASSWORD")},
        },
    }


def open_in_browser(url: str) -> Optional[str]:
    """Try wslview (WSL), then xdg-open, then open (macOS). The launcher used, or None."""
    for tool in ("wslview", "xdg-open", "open"):
        if shutil.which(tool):
            try:
                subprocess.Popen([tool, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return tool
            except OSError:
                continue
    return None


# --- wait ----------------------------------------------------------------------------
def wait_ready(rt: Runtime, timeout: float, on_change=None, interval: float = 2.0,
               clock=time.monotonic, sleep=time.sleep) -> Dict[str, Any]:
    """Block until the stack has containers and every one is ready. Returns
    {ok, waited, not_ready: [(service, state)], failed: [...]}. Gives up early
    only at the timeout (a failed container may still be restarted)."""
    t0 = clock()
    last = None
    while True:
        cs = rt.containers(project())
        bad = [(c.service, c.state) for c in cs if c.state not in READY]
        if on_change and (len(cs), tuple(bad)) != last:
            on_change(len(cs), bad)
            last = (len(cs), tuple(bad))
        if cs and not bad:
            return {"ok": True, "waited": round(clock() - t0, 1), "not_ready": []}
        if clock() - t0 >= timeout:
            return {"ok": False, "waited": round(clock() - t0, 1), "not_ready": bad or [("(stack)", "no containers")]}
        sleep(interval)


# --- version -------------------------------------------------------------------------
def _git(*args: str) -> str:
    try:
        res = subprocess.run(["git", "-C", str(paths.REPO), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return res.stdout.strip() if res.returncode == 0 else ""


def wheel_pins() -> List[Dict[str, str]]:
    lock = paths.ENGINE / "dojo" / "requirements.lock"
    pins = []
    if lock.is_file():
        for line in lock.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 3 and not line.lstrip().startswith("#"):
                pins.append({"name": parts[0], "version": parts[1], "sha256": parts[2][:12]})
    return pins


def version_info(rt: Runtime) -> Dict[str, Any]:
    return {
        "git": {"rev": _git("rev-parse", "--short", "HEAD") or None, "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or None,
                "dirty": bool(_git("status", "--porcelain", "--untracked-files=no"))},
        "python": sys.version.split()[0],
        "engine": rt.cli or None,
        "engine_version": (rt.version() if rt.available else None) or None,
        "compose": (rt.compose_version() if rt.available else None) or None,
        "wheels": wheel_pins(),
    }
