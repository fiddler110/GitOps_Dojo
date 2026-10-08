"""`./run.sh stop` (also `teardown`): stop the stack and delete every volume.

Uses the same -f files the last start used (state.Current), so module and
overlay services and volumes go too; `down --remove-orphans` catches anything
older. Only the operator files (dojo.toml, dojo.local.toml, .env and the recorded profile) are loaded, never a
workshop.env, so a compose fragment must not require (${VAR:?}) a variable
only workshop.env or module.env sets. Nothing here can be undone.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import List

from rich.console import Group
from rich.live import Live
from rich.table import Table
from rich.text import Text

from . import paths, state
from .envfiles import operator_env
from .runtime import Runtime, project_name
from .ui import bad, console


def _volumes_in_config(text: str) -> List[str]:
    """Top-level `volumes:` keys of a merged Compose config (YAML), read without a
    YAML library: podman-compose has no `config --volumes`."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("volumes:"):
            inside = True
            continue
        if line and not line.startswith(" "):
            inside = False
        if inside and line.startswith("  ") and not line.startswith("   ") and ":" in line:
            out.append(line.strip().split(":", 1)[0])  # "name:" or "name: {}"
    return out


def run_stop(dry_run: bool) -> int:
    t0 = time.time()
    rt = Runtime()
    cur = state.read_current()
    env = {**os.environ, **operator_env(cur.env_name if cur else None)}
    project = project_name(env)
    files = cur.files if cur else []
    compose = [*rt.compose_cmd, "-f", "docker-compose.yml", *[a for f in files for a in ("-f", f)]]

    def run(*args: str, **kw) -> subprocess.CompletedProcess:
        return subprocess.run([*compose, *args], cwd=str(paths.ENGINE), env=env, **kw)

    if dry_run:
        console.print("DRY RUN -- nothing will be removed.\n")
        console.print("Compose files: docker-compose.yml " + (" ".join(files) + " (from the last start)" if files
                                                              else "only (no start recorded)"))
        cfg = run("config", capture_output=True, text=True)
        svcs = run("config", "--services", capture_output=True, text=True).stdout.split()
        console.print("\nServices in this Compose project:")
        console.print("\n".join(f"  {s}" for s in svcs) or "  (none found -- 'compose config' failed, e.g. no .env yet)")
        console.print("\nVolumes that --volumes would delete:")
        console.print("\n".join(f"  {v}" for v in _volumes_in_config(cfg.stdout)) or "  (none found)")
        console.print("\nContainers currently up for this project:")
        for c in rt.containers(project):
            console.print(f"  {c.name}  {c.status}")
        console.print(f"\nWould run: compose {' '.join(compose[len(rt.compose_cmd):])} down --volumes --remove-orphans")
        console.print("Dry run complete: nothing was removed.")
        return 0

    containers = rt.containers(project)
    vols = rt.volumes(project)
    if not containers and not vols:  # two cheap listings instead of a slow `down`
        state.clear_current()
        console.print("Nothing to tear down: no workshop containers or volumes.")
        return 0

    console.print("Tearing down the workshop stack and all volumes (student homes, Forgejo data)...")
    if console.is_terminal:
        rc = _down_live(rt, project, containers, len(vols), lambda out: run("down", "--volumes", "--remove-orphans",
                                                                             stdout=out, stderr=subprocess.STDOUT).returncode)
    else:
        rc = run("down", "--volumes", "--remove-orphans").returncode
    state.record("stop", cur.workshop if cur else "", [], time.time() - t0, "ok" if rc == 0 else f"exit {rc}")
    if rc != 0:
        bad(f"compose down failed (exit {rc}); the run stays recorded. Re-run `{paths.PROG} stop` to finish.")
        return rc
    state.clear_current()
    console.print("Done. No workshop data was retained.")
    return 0


def _down_live(rt: Runtime, project: str, before, vols_before: int, down) -> int:
    """`down` with a table of every container going from up to removed."""
    fd, log_path = tempfile.mkstemp(prefix="dojo-down.")
    console.print(f"Compose output is in {log_path}")
    status = {c.name: c.status for c in before}
    left = [vols_before]
    t0 = time.time()
    done = threading.Event()

    def poll() -> None:
        n = 0
        while not done.wait(1):
            now = {c.name: c.status for c in rt.containers(project)}
            for name in status:
                status[name] = now.get(name, "removed")
            if n % 3 == 0:
                left[0] = len(rt.volumes(project))
            n += 1

    def render():
        gone = sum(1 for s in status.values() if s == "removed")
        e = int(time.time() - t0)
        rows = Table.grid(padding=(0, 1))
        for name, s in sorted(status.items()):
            word = "removed" if s == "removed" else "stopped" if s.startswith("Exited") else "up"
            style = "green" if word == "removed" else "yellow"
            rows.add_row(Text("+" if word == "removed" else "~", style=style), Text(name, style=style), Text(word, style=style))
        return Group(Text.assemble((f"  {e // 60}:{e % 60:02d}   ", "dim"), (f"{gone} of {len(status)} containers removed", "cyan"),
                                   f"   volumes left: {left[0]} of {vols_before}"), rows)

    class View:
        def __rich__(self):
            return render()

    watcher = threading.Thread(target=poll, daemon=True)
    with os.fdopen(fd, "w") as out, Live(View(), console=console, refresh_per_second=4):
        watcher.start()
        rc = down(out)
        done.set()
        watcher.join(timeout=3)
        now = {c.name for c in rt.containers(project)}
        for name in status:
            status[name] = "removed" if name not in now else status[name]
        left[0] = len(rt.volumes(project))
    if rc != 0:
        bad(f"compose down failed (exit {rc}); the last lines of its output:")
        console.print("\n".join(Path(log_path).read_text().splitlines()[-20:]), markup=False)
    else:
        os.unlink(log_path)
    return rc
