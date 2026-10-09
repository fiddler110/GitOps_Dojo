"""`dojo prune` and the safe automatic fixes of `dojo doctor --fix`."""
from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from . import paths
from .runtime import Runtime


# --- prune ---------------------------------------------------------------------------
def dangling_dojo_images(rt: Runtime) -> List[Dict[str, Any]]:
    """Dangling (untagged) images that used to be a gitopsdojo/ tag, with no container using
    them. Dangling images of other projects are not ours to touch."""
    try:
        rows = json.loads(rt.out("images", "--filter", "dangling=true", "--format", "json") or "[]")
    except ValueError:
        return []
    mine = []
    for r in rows or []:
        history = [str(h) for h in (r.get("History") or []) + (r.get("Names") or [])]
        if r.get("Containers", 0) == 0 and any("gitopsdojo/" in h for h in history):
            mine.append({"id": r["Id"][:12], "was": next(h for h in history if "gitopsdojo/" in h), "size": r.get("Size", 0)})
    return mine


def prune(rt: Runtime, dry_run: bool) -> Dict[str, Any]:
    """Remove those images one by one (an in-use image is refused by the engine and skipped).
    Volumes and containers are never touched. Docker has no per-image history: nothing is done."""
    if rt.cli != "podman":
        return {"supported": False, "removed": [], "skipped": [], "bytes": 0}
    removed, skipped = [], []
    for img in dangling_dojo_images(rt):
        if dry_run:
            removed.append(img)
            continue
        res = rt.run("image", "rm", img["id"])
        (removed if res.returncode == 0 else skipped).append(img)
    return {"supported": True, "removed": removed, "skipped": skipped, "bytes": sum(i["size"] for i in removed)}


# --- doctor --fix ---------------------------------------------------------------------
def _lock_dir() -> Path:
    return Path(f"/tmp/gitops-dojo-{os.getuid()}.lock")


def fix_stale_lock() -> str:
    lock = _lock_dir()
    if not lock.is_dir():
        return ""
    pid = (lock / "pid").read_text().strip() if (lock / "pid").is_file() else ""
    alive = pid.isdigit() and os.path.exists(f"/proc/{pid}")
    if alive:
        return ""
    for f in lock.iterdir():
        f.unlink()
    lock.rmdir()
    return f"removed the stale run lock {lock} (pid {pid or '?'} is gone)"


def fix_env_mode() -> str:
    if not paths.ENV_FILE.is_file():
        return ""
    mode = stat.S_IMODE(paths.ENV_FILE.stat().st_mode)
    if mode & 0o077 == 0:
        return ""
    paths.ENV_FILE.chmod(0o600)
    return f"set .env from mode {mode:o} to 600 (it holds every secret)"


def fix_missing_env() -> str:
    if paths.ENV_FILE.is_file():
        return ""
    res = subprocess.run(["sh", str(paths.ENGINE / "scripts" / "env-setup.sh"), "--default"],
                         capture_output=True, text=True, cwd=str(paths.REPO))
    if res.returncode != 0 or not paths.ENV_FILE.is_file():
        return "tried '" + paths.PROG + " setup --default' for the missing .env but it failed: " + (res.stderr or res.stdout).strip()[-200:]
    return f"created .env with '{paths.PROG} setup --default' (easy local credentials; run '{paths.PROG} setup' for real ones)"


def apply_fixes() -> List[str]:
    """Run every safe fix; the sentences for those that changed something. Never touches
    containers, images or volumes."""
    return [m for m in (fix_stale_lock(), fix_missing_env(), fix_env_mode()) if m]
