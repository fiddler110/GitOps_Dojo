"""The container engine: podman (when podman-compose is installed too) or docker.
Same rule as engine/scripts/lib.sh, so the shell scripts and the CLI agree."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional

READY = ("healthy", "running", "done")
# "working": a one-shot job (restart: "no", no health check, e.g. bootstrap) that
# is still running. Up is not ready for those: they are done when they exit 0.
PROBLEM = ("failed", "unhealthy")


def classify(status: str) -> str:
    """A container's `ps` status line as one word: healthy, running (up, no
    health check), done (exited 0), starting, waiting (created, not started),
    unhealthy or failed. Same buckets as run.sh's start-up display."""
    if "(unhealthy)" in status:
        return "unhealthy"
    if "(healthy)" in status:
        return "healthy"
    if "health: starting" in status or "(starting)" in status:
        return "starting"
    if status.startswith("Exited (0)"):
        return "done"
    if status.startswith("Exited"):
        return "failed"
    if status.startswith(("Created", "Initialized", "Configured")):
        return "waiting"
    return "running"


@dataclass
class Container:
    service: str
    name: str
    status: str   # as `ps` prints it, e.g. "Up 3 minutes (healthy)"
    id: str
    oneshot: bool = False

    @property
    def state(self) -> str:
        state = classify(self.status)
        return "working" if state == "running" and self.oneshot else state


def on_wsl() -> bool:
    """Running under WSL (its kernel names Microsoft in /proc/version)."""
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


class Runtime:
    def __init__(self) -> None:
        if shutil.which("podman") and shutil.which("podman-compose"):
            self.cli = "podman"
            # WSL2: Windows folders on PATH make every podman call search them
            # (~1.2 s each instead of ~0.06 s). Nothing podman needs is there.
            # Elsewhere /mnt/... is an ordinary mount, so leave PATH alone.
            if on_wsl():
                path = os.environ.get("PATH", "")
                os.environ["PATH"] = ":".join(p for p in path.split(":") if not p.startswith("/mnt/"))
        elif shutil.which("docker"):
            self.cli = "docker"
        else:
            self.cli = ""
        self._oneshot: dict = {}  # container ID -> one-shot job? (asked once per container)

    @property
    def available(self) -> bool:
        return bool(self.cli)

    @property
    def compose_cmd(self) -> List[str]:
        # DOJO_COMPOSE (experimental, ROADMAP C4): another Compose to drive the stack
        # with, e.g. docker-compose v2 through the podman socket (with DOCKER_HOST set).
        if os.environ.get("DOJO_COMPOSE"):
            return shlex.split(os.environ["DOJO_COMPOSE"])
        return ["podman-compose"] if self.cli == "podman" else ["docker", "compose"]

    def run(self, *args: str, timeout: Optional[float] = 60) -> subprocess.CompletedProcess:
        return subprocess.run([self.cli, *args], capture_output=True, text=True, timeout=timeout)

    def out(self, *args: str, timeout: Optional[float] = 60) -> str:
        """stdout of a successful call, '' otherwise."""
        if not self.cli:
            return ""
        try:
            res = self.run(*args, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return res.stdout if res.returncode == 0 else ""

    def containers(self, project: str) -> List[Container]:
        """Every container of a Compose project, by its label (module and
        overlay services included), sorted by service."""
        fmt = '{{.Label "com.docker.compose.service"}}|{{.Names}}|{{.Status}}|{{.ID}}'
        rows = []
        for line in self.out("ps", "-a", "--filter", f"label=com.docker.compose.project={project}",
                             "--format", fmt).splitlines():
            parts = line.split("|", 3)
            if len(parts) == 4:
                rows.append(Container(*parts))
        new = [c.id for c in rows if c.id not in self._oneshot]
        if new:
            fmt = "{{.Id}}|{{.HostConfig.RestartPolicy.Name}}|{{if .Config.Healthcheck}}hc{{end}}"
            for line in self.out("inspect", "--format", fmt, *new).splitlines():
                full, policy, hc = (line.split("|") + ["", ""])[:3]
                for short in new:
                    if full.startswith(short):
                        self._oneshot[short] = policy in ("no", "") and not hc
        for c in rows:
            c.oneshot = self._oneshot.get(c.id, False)
        return sorted(rows, key=lambda c: (c.service, c.name))

    def dependents(self, containers: List[Container], services: List[str]) -> List[str]:
        """The services whose containers depend on a container of `services`, directly or
        through another, by podman's own record (`depends_on` becomes a hard link under
        podman-compose). podman won't remove a container others depend on, so recreating
        one alone leaves the old one running. Docker keeps no such link: []."""
        if self.cli != "podman" or not containers:
            return []
        deps, svc = {}, {}
        for line in self.out("inspect", "--format", "{{.Id}}|{{json .Dependencies}}",
                             *[c.id for c in containers]).splitlines():
            full, _, raw = line.partition("|")
            try:
                deps[full] = json.loads(raw) or []
            except ValueError:
                deps[full] = []
            svc[full] = next((c.service for c in containers if full.startswith(c.id)), "")
        want = set(services)
        grew = True
        while grew:
            grew = False
            for full, needs in deps.items():
                if svc[full] and svc[full] not in want and any(svc.get(d) in want for d in needs):
                    want.add(svc[full])
                    grew = True
        return sorted(want - set(services))

    def volumes(self, project: str) -> List[str]:
        return [v for v in self.out("volume", "ls", "-q").split() if v.startswith(f"{project}_")]

    def version(self) -> str:
        if self.cli == "podman":
            return self.out("version", "--format", "{{.Client.Version}}").strip()
        return self.out("version", "--format", "{{.Server.Version}}").strip()

    def compose_version(self) -> str:
        try:
            res = subprocess.run([*self.compose_cmd, "version"], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        text = (res.stdout + res.stderr).strip().splitlines()
        return text[-1] if res.returncode == 0 and text else ""


def project_name(env: Optional[dict] = None) -> str:
    """The Compose project: named after engine/, unless COMPOSE_PROJECT_NAME is set."""
    return (env if env is not None else os.environ).get("COMPOSE_PROJECT_NAME") or "engine"
