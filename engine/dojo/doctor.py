"""`dojo doctor`: will a start work on this machine? Every check says what it
found and, when something is wrong, what to do about it. Failures make the
command exit 1, so it can gate a class or a CI job."""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from rich.markup import escape
from rich.table import Table

from . import checks, paths, state
from . import config
from .envfiles import EnvError, operator_env, parse_literal, resolve, split_profiles
from .runtime import Runtime, on_wsl, project_name
from .stack import extra_files, mem_limits, read_state, services
from .ui import console

OK, INFO, WARN, FAIL = "ok", "info", "warn", "fail"
_MARK = {OK: "[green]✔[/]", INFO: "[cyan]•[/]", WARN: "[yellow]![/]", FAIL: "[red]✖[/]"}


@dataclass
class Check:
    level: str
    title: str
    detail: str = ""
    fix: str = ""


def _mem_mb(value: str) -> Optional[int]:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([kmgt]?)b?\s*", value.lower())
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2)
    return int(n * {"": 1 / 1048576, "k": 1 / 1024, "m": 1, "g": 1024, "t": 1048576}[unit])


def _required_keys() -> List[str]:
    """Variables docker-compose.yml refuses to start without (${VAR:?...}) that
    the operator is meant to provide (.env.example's secrets, dojo.toml's settings)."""
    compose = (paths.ENGINE / "docker-compose.yml").read_text()
    needed = set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*):\?", compose))
    example_file = paths.REPO / ".env.example"
    example = {k for k, _, _ in parse_literal(example_file)} if example_file.is_file() else set()
    example |= set(config.BY_ENV)
    return sorted(needed & example) if example else sorted(needed)


def _port_free(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _strict_operator_env(env_name: str) -> Dict[str, str]:
    split_profiles(env_name)   # raises for an unknown profile
    return operator_env(env_name)


def run_checks(rt: Runtime, workshop: Optional[str], env_name: Optional[str]) -> List[Check]:
    out: List[Check] = []
    add = out.append

    # --- Container engine -------------------------------------------------
    if not rt.available:
        add(Check(FAIL, "Container engine", "neither podman (with podman-compose) nor docker found",
                  "Install podman and podman-compose (preferred) or Docker."))
        return out
    add(Check(OK, "Container engine", f"{rt.cli} {rt.version() or '?'}, compose: {rt.compose_version() or '?'}"))
    info: Dict = {}
    if rt.cli == "podman":
        try:
            info = json.loads(rt.out("info", "--format", "json") or "{}")
        except ValueError:
            info = {}
        host = info.get("host", {})
        ctl = host.get("cgroupControllers") or []
        if host.get("cgroupVersion") != "v2" or not {"memory", "pids"} <= set(ctl):
            add(Check(WARN, "Resource limits", f"cgroup {host.get('cgroupVersion', '?')}, controllers: {', '.join(ctl) or 'none'}",
                      "Rootless podman needs cgroup v2 with memory and pids delegated, or mem_limit and "
                      "pids_limit are not enforced (one student can starve the rest)."))
        else:
            add(Check(OK, "Resource limits", "cgroup v2 with memory and pids (mem_limit/pids_limit enforced)"))
        nbi = host.get("networkBackendInfo") or {}
        if host.get("networkBackend") == "netavark" and (nbi.get("dns") or {}).get("version"):
            add(Check(OK, "Service DNS", f"{nbi['dns']['version']} (containers find each other by name)"))
        else:
            add(Check(FAIL, "Service DNS", f"backend {host.get('networkBackend', '?')}, no aardvark-dns",
                      "Install netavark and aardvark-dns: the gateway reaches every service by name."))
        if on_wsl():
            add(Check(INFO, "WSL2", "Windows /mnt/* folders are dropped from PATH for podman calls (each would cost ~1.2 s)"))
        graphroot = (info.get("store") or {}).get("graphRoot")
    else:
        graphroot = None
    if graphroot and os.path.isdir(graphroot):
        free_gb = shutil.disk_usage(graphroot).free / 1024 ** 3
        level = FAIL if free_gb < 5 else WARN if free_gb < 15 else OK
        add(Check(level, "Disk space", f"{free_gb:.0f} GB free for images and volumes",
                  "" if level == OK else "A first build needs about 10 GB; free some space ('podman system prune')."))

    # --- .env, dojo.toml ---------------------------------------------------
    if not paths.ENV_FILE.is_file():
        add(Check(FAIL, ".env", "missing", f"Run '{paths.PROG} setup' (or '{paths.PROG} setup --default' for local use)."))
        return out
    mode = stat.S_IMODE(paths.ENV_FILE.stat().st_mode)
    add(Check(OK if mode & 0o077 == 0 else WARN, ".env", f"present, mode {mode:o}",
              "" if mode & 0o077 == 0 else "It holds every secret: chmod 600 .env"))
    try:
        env = operator_env(env_name) if not env_name else _strict_operator_env(env_name)
    except EnvError as exc:
        add(Check(FAIL, "dojo.toml / profile", str(exc)))
        return out
    missing = [k for k in _required_keys() if not env.get(k)]
    if missing:
        add(Check(FAIL, "Required settings", "empty or missing: " + ", ".join(missing),
                  f"Run '{paths.PROG} setup' to fill them in."))
    if not env.get("STUDENT_PASSWORD_SEED"):
        add(Check(WARN, "Student passwords", "no STUDENT_PASSWORD_SEED: every student shares one Forgejo password",
                  f"Add one ('openssl rand -hex 32') or run '{paths.PROG} setup'."))
    weak = checks.default_passwords(env)
    if weak and not checks.local_only(env):
        allowed = env.get("ALLOW_DEFAULT_PASSWORDS") == "1"
        add(Check(WARN if allowed else FAIL, "Passwords", f"public defaults ({', '.join(weak)}) reachable beyond this machine"
                  + (" (allowed by ALLOW_DEFAULT_PASSWORDS=1)" if allowed else ""),
                  "" if allowed else f"Generate real ones with '{paths.PROG} setup', or start with --allow-default-passwords."))
    elif weak:
        add(Check(INFO, "Passwords", f"public defaults ({', '.join(weak)}), fine while only this machine can connect"))
    else:
        add(Check(OK, "Passwords", "none of them is a public default"))
    mismatch = checks.port_mismatch(env)
    if mismatch:
        add(Check(WARN, "Address", mismatch))
    if checks.plain_http_offbox(env):
        add(Check(WARN, "HTTPS", f"{env.get('PUBLIC_BASE_URL')} is plain HTTP beyond this machine",
                  "Use a TLS proxy in front (engine/README.md, \"LAN class over HTTPS\")."))

    # --- The port, and what is running -----------------------------------
    project = project_name(env)
    containers = rt.containers(project)
    port = checks.gateway_port(env)
    bind = env.get("LAB_HOST_IP") or "0.0.0.0"
    ours = any(c.service == "gateway" for c in containers)
    if _port_free(bind, port):
        add(Check(OK, "Gateway port", f"{bind}:{port} is free"))
    elif ours:
        add(Check(OK, "Gateway port", f"{bind}:{port} is held by this stack's gateway"))
    else:
        add(Check(FAIL, "Gateway port", f"{bind}:{port} is in use by something else",
                  f"Find it with 'ss -ltnp | grep :{port}', or change GATEWAY_HTTP_PORT and PUBLIC_BASE_URL."))
    host_mb = int(((info.get("host") or {}).get("memTotal") or 0) / 1048576)
    term_mb = _mem_mb(env.get("WEB_TERMINAL_MEM_LIMIT", "") or "")
    if host_mb and term_mb:
        need = term_mb + 3072 + 1024
        add(Check(OK if need <= host_mb else WARN, "Memory",
                  f"{host_mb} MB here; terminals {term_mb} MB + engine services ~3072 + reserve 1024 = {need} MB"
                  " (name a workshop to count its modules too)",
                  "" if need <= host_mb else f"Run '{paths.PROG} capacity WORKSHOP --students N' to size the limits for this machine."))
    lock = Path(f"/tmp/gitops-dojo-{os.getuid()}.lock")
    if lock.is_dir():
        pid = read_state(lock / "pid")
        alive = pid.isdigit() and os.path.exists(f"/proc/{pid}")
        add(Check(INFO if alive else WARN, "Run lock", f"held by pid {pid}: {read_state(lock / 'what')}" if alive
                  else f"{lock} left by a run that no longer exists",
                  "" if alive else "Harmless: the next run reclaims it."))
    if containers:
        cur = state.read_current()
        recorded = cur.workshop if cur and cur.workshop else "an unrecorded workshop"
        add(Check(INFO, "Running now", f"{recorded}: {len(containers)} container(s) ('{paths.PROG} status' for detail)"))
    images = [i for i in ("gitopsdojo/web-terminal:core", "gitopsdojo/allocator:local",
                          "gitopsdojo/gateway:local", "gitopsdojo/presentation:local")
              if not rt.out("image", "inspect", "--format", "{{.Id}}", i)]
    add(Check(OK if not images else INFO, "Engine images",
              "all built" if not images else f"not built yet: {', '.join(images)} (the first start builds them, ~10 min)"))

    # --- One workshop -----------------------------------------------------
    if workshop:
        try:
            res = resolve(workshop, env_name)
        except EnvError as exc:
            add(Check(FAIL, f"Workshop {workshop}", str(exc)))
            return out
        for w in res.warnings:
            add(Check(WARN, f"Workshop {workshop}", w))
        try:
            names = services(rt, extra_files(res), res.env)
            add(Check(OK, f"Workshop {workshop}", f"env resolves, modules: {', '.join(res.modules) or 'none'}; "
                      f"Compose config loads ({len(names)} services)"))
        except (RuntimeError, OSError) as exc:
            add(Check(FAIL, f"Workshop {workshop}", "Compose config does not load", str(exc)[-600:]))
        else:
            try:
                limits, oneshot = mem_limits(rt, extra_files(res), res.env)
            except (RuntimeError, OSError):
                limits, oneshot = {}, []
            term_mb = limits.get("web-terminal")
            others = sum(v or 0 for k, v in limits.items() if k != "web-terminal" and k not in oneshot)
            if host_mb and term_mb and others:
                need = term_mb + others + 1024
                add(Check(OK if need <= host_mb else WARN, f"Memory for {workshop}",
                          f"terminals {term_mb} MB + its other services {others} MB + reserve 1024 = {need} MB of {host_mb}",
                          "" if need <= host_mb else f"Run '{paths.PROG} capacity {workshop} --students N' to size the limits."))
        cur = state.read_current()
        recorded = cur.workshop if cur else ""
        if containers and recorded and recorded != workshop:
            add(Check(WARN, "Switching workshop", f"{recorded} is running; starting {workshop} is refused until '{paths.PROG} stop'"))
    return out


def show(results: List[Check]) -> int:
    grid = Table.grid(padding=(0, 1))
    grid.add_column(no_wrap=True)
    grid.add_column(no_wrap=True, style="bold")
    grid.add_column()
    width = max((len(c.title) for c in results), default=0)
    for c in results:
        text = escape(c.detail) + (f"\n[dim]{escape(c.fix)}[/]" if c.fix else "")
        grid.add_row(_MARK[c.level], c.title, text)
        if not console.is_terminal:  # a log: plain lines, no padding to the console width
            console.print(f"{_MARK[c.level]} [bold]{c.title.ljust(width)}[/] {escape(c.detail)}")
            if c.fix:
                console.print(f"  {' ' * width} [dim]{escape(c.fix)}[/]")
    if console.is_terminal:
        console.print(grid)
    fails = sum(c.level == FAIL for c in results)
    warns = sum(c.level == WARN for c in results)
    console.print()
    if fails:
        console.print(f"[red]{fails} problem(s) to fix[/]" + (f", {warns} warning(s)" if warns else ""))
    elif warns:
        console.print(f"[yellow]Ready, with {warns} warning(s).[/]")
    else:
        console.print("[green]Ready.[/]")
    return 1 if fails else 0
