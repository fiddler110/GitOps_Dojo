"""`dojo backup` / `dojo restore`: a tar snapshot of the stack's named volumes
(Forgejo, student homes, achievements ...) through `podman volume export/import`.

Layout: manifest.json (workshop, flags, compose files, volume names) plus
volumes/<name>.tar per volume. Podman only: Docker has no volume export."""
from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import state
from .runtime import Runtime
from .stackapi import StackError, project


def default_path(workshop: str) -> Path:
    return Path.cwd() / f"dojo-backup-{workshop or 'stack'}-{time.strftime('%Y%m%d-%H%M%S')}.tar"


def _need_podman(rt: Runtime) -> None:
    if rt.cli != "podman":
        raise StackError("backup and restore use 'podman volume export/import'; they need podman.")


def backup(rt: Runtime, dest: Optional[Path]) -> Dict[str, Any]:
    _need_podman(rt)
    proj = project()
    vols = rt.volumes(proj)
    if not vols:
        raise StackError("No volumes to back up: nothing has been started here (stop removes every volume).")
    cur = state.read_current()
    workshop = cur.workshop if cur else (state.last_start() or [""])[0]
    dest = Path(dest) if dest else default_path(workshop)
    if dest.is_dir():
        dest = dest / default_path(workshop).name
    live = [c for c in rt.containers(proj) if c.state in ("healthy", "running")]
    mode = "w:gz" if dest.suffix in (".gz", ".tgz") else "w"
    with tempfile.TemporaryDirectory() as tmp:
        manifest = {"version": 1, "project": proj, "workshop": workshop, "args": cur.args if cur else [],
                    "files": cur.files if cur else [], "env_name": cur.env_name if cur else None,
                    "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "volumes": vols}
        (Path(tmp) / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        with tarfile.open(dest, mode) as tar:
            tar.add(Path(tmp) / "manifest.json", arcname="manifest.json")
            for v in vols:
                part = Path(tmp) / f"{v}.tar"
                res = rt.run("volume", "export", v, "--output", str(part), timeout=600)
                if res.returncode != 0:
                    dest.unlink(missing_ok=True)
                    raise StackError(f"Exporting volume {v} failed: {res.stderr.strip()[-200:]}")
                tar.add(part, arcname=f"volumes/{v}.tar")
                part.unlink()
    return {"path": str(dest), "volumes": vols, "workshop": workshop, "live": len(live), "bytes": dest.stat().st_size}


def read_manifest(path: Path) -> Dict[str, Any]:
    try:
        with tarfile.open(path, "r:*") as tar:
            fh = tar.extractfile("manifest.json")
            return json.loads(fh.read()) if fh else {}
    except (OSError, KeyError, tarfile.TarError, ValueError):
        raise StackError(f"{path} is not a dojo backup (no readable manifest.json).")


def plan_restore(rt: Runtime, path: Path) -> Dict[str, Any]:
    """Everything that must hold before restoring; raises StackError otherwise. Returns the manifest
    plus `existing` (volumes that would be replaced)."""
    _need_podman(rt)
    if not Path(path).is_file():
        raise StackError(f"No such backup file: {path}")
    m = read_manifest(Path(path))
    proj = project()
    if rt.containers(proj):
        raise StackError("The stack has containers (running or not). Restore only into a stopped, fresh stack: "
                         "run 'stop' first (it deletes every volume), then restore.")
    last = state.last_start()
    if last and m.get("workshop") and last[0] != m["workshop"]:
        raise StackError(f"This backup is of workshop '{m['workshop']}' but this checkout last started '{last[0]}'. "
                         "Refusing to restore across workshops.")
    if m.get("project") and m["project"] != proj:
        raise StackError(f"This backup is of Compose project '{m['project']}', this machine uses '{proj}'.")
    m["existing"] = [v for v in rt.volumes(proj) if v in set(m.get("volumes", []))]
    return m


def restore(rt: Runtime, path: Path, manifest: Dict[str, Any]) -> List[str]:
    done = []
    with tempfile.TemporaryDirectory() as tmp, tarfile.open(path, "r:*") as tar:
        for v in manifest.get("volumes", []):
            member = f"volumes/{v}.tar"
            try:
                src = tar.extractfile(member)
            except KeyError:
                raise StackError(f"{path} lacks {member}.")
            part = Path(tmp) / f"{v}.tar"
            with open(part, "wb") as out:
                shutil.copyfileobj(src, out)
            if v in manifest.get("existing", []):
                rt.run("volume", "rm", v)
            if rt.run("volume", "create", v).returncode != 0:
                raise StackError(f"Could not create volume {v}.")
            res = rt.run("volume", "import", v, str(part), timeout=600)
            if res.returncode != 0:
                raise StackError(f"Importing volume {v} failed: {res.stderr.strip()[-200:]}")
            part.unlink()
            done.append(v)
    return done
