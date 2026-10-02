"""The start-up display.

While `compose up` runs and health checks settle, this watches the stack:
  * `podman events` (or `docker events`) for the project wakes it the moment a
    container is created, starts, changes health or exits; a `ps` snapshot then
    says where every service stands. Without an events stream it polls once a second.
  * each container that is still working has its log followed (`logs -f`), so
    the activity pane shows what is underway: bootstrap creating teams, the
    terminal minting tokens, a module's setup script. A follower stops once its
    container is ready.

In a terminal it is one Rich Live view: a progress bar over a services table
with the activity pane beside it (below it on a narrow window). In a log it
prints one line per event, and every 30 s without one, what it is waiting on.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple

from rich.console import Group
from rich.markup import escape
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from .runtime import PROBLEM, READY, Container, Runtime
from .ui import STATE_MARK, STATE_STYLE, console

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_JSON_MSG = re.compile(r'^\{.*"level":"([a-z]+)".*"msg":"([^"]*)"')
_STAMP = re.compile(r"^\d{4}[-/]\d\d[-/]\d\d[T ][0-9:.]*Z? *")
_BRACKET_STAMP = re.compile(r"^\[\d{4}-\d\d-\d\d [0-9:]+ [+-]\d{4}\] (\[\d+\] )?")  # gunicorn
_FORGEJO_SRC = re.compile(r"^\.\.\.\S* *")
KIND_STYLE = {"ok": "green", "bad": "red", "warn": "yellow", "log": ""}


def clean_log_line(line: str) -> str:
    """A container log line made short and safe to show: colour codes and
    control characters out; a JSON line (Caddy) as "level: msg"; a leading
    timestamp and a Forgejo "...file.go:12:func()" source tag dropped."""
    line = _ANSI.sub("", line)
    line = "".join(ch for ch in line if ch.isprintable())
    m = _JSON_MSG.match(line)
    if m:
        line = f"{m.group(1)}: {m.group(2)}"
    line = _FORGEJO_SRC.sub("", _STAMP.sub("", _BRACKET_STAMP.sub("", line))).strip()
    return line[:240]


def _elapsed(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60}:{s % 60:02d}"


class StartMonitor:
    def __init__(self, rt: Runtime, project: str, services: List[str], live: bool) -> None:
        self.rt, self.project, self.services, self.live_mode = rt, project, services, live
        self.t0 = time.time()
        self.containers: List[Container] = []
        self.states: Dict[str, str] = {}
        self.events: List[Tuple[float, str, str]] = []  # a start makes a few hundred at most
        self.printed = 0
        self.volumes = 0
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.followers: Dict[str, subprocess.Popen] = {}
        self.events_proc: Optional[subprocess.Popen] = None
        self.threads: List[threading.Thread] = []
        self.live = None
        self.quiet_since = time.time()

    # --- watching ------------------------------------------------------------
    def start(self) -> None:
        try:
            self.events_proc = subprocess.Popen(
                [self.rt.cli, "events", "--filter", f"label=com.docker.compose.project={self.project}",
                 "--format", "{{json .}}" if self.rt.cli == "docker" else "json"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            self._thread(self._read_events)
        except OSError:
            self.events_proc = None
        self._thread(self._loop)
        if self.live_mode:
            from rich.live import Live
            self.live = Live(self, console=console, refresh_per_second=4, transient=False)
            self.live.start()

    def _thread(self, target) -> None:
        t = threading.Thread(target=target, daemon=True)
        t.start()
        self.threads.append(t)

    def _read_events(self) -> None:
        for _ in self.events_proc.stdout:  # any event of ours: take a fresh snapshot now
            self.wake.set()
            if self.stopping.is_set():
                break

    def _loop(self) -> None:
        heartbeat = 2.0 if self.events_proc else 1.0
        n = 0
        while not self.stopping.is_set():
            self.wake.wait(heartbeat)
            self.wake.clear()
            if self.stopping.is_set():
                break
            self.snapshot(volumes=(n % 5 == 0))
            n += 1
            if not self.live_mode:
                self.print_new()
            time.sleep(0.2)  # a burst of events: one snapshot, not one per event

    def snapshot(self, volumes: bool = False) -> None:
        cs = self.rt.containers(self.project)
        now = time.time()
        with self.lock:
            for c in cs:
                state = c.state
                if self.states.get(c.service) != state:
                    kind = "ok" if state in READY else "bad" if state in PROBLEM else "warn"
                    detail = f"failed ({c.status})" if state == "failed" else state
                    self.events.append((now, kind, f"{c.service}: {detail}"))
                    self.states[c.service] = state
            self.containers = cs
        if volumes:
            self.volumes = len(self.rt.volumes(self.project))
        self._sync_followers(cs)

    def _sync_followers(self, cs: List[Container]) -> None:
        if self.stopping.is_set():
            return
        busy = {c.id: c for c in cs if c.state not in READY and c.state != "waiting"}
        for cid in list(self.followers):
            if cid not in busy:
                self._end(self.followers.pop(cid))
        for cid, c in busy.items():
            if cid in self.followers or len(self.followers) >= 8:
                continue
            try:
                proc = subprocess.Popen([self.rt.cli, "logs", "-f", "--tail", "1", cid],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
            except OSError:
                continue
            self.followers[cid] = proc
            threading.Thread(target=self._follow, args=(c.service, proc), daemon=True).start()

    def _follow(self, service: str, proc: subprocess.Popen) -> None:
        last = ""
        for raw in proc.stdout:
            line = clean_log_line(raw)
            if line and line != last:
                last = line
                with self.lock:
                    self._log_event(service, line)

    def _log_event(self, service: str, line: str) -> None:
        """A log line as activity. A burst from one service (a migration printing
        forty steps) updates one line in place instead of pushing every other
        service out of the pane: the previous line is replaced while it is the
        latest event, from the same service, and not yet printed (log mode)."""
        now, text = time.time(), f"{service}: {line}"
        if self.events and len(self.events) > self.printed:
            t, kind, prev = self.events[-1]
            if kind == "log" and prev.startswith(f"{service}: ") and now - t < 3:
                self.events[-1] = (t, "log", text)
                return
        self.events.append((now, "log", text))

    @staticmethod
    def _end(proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

    def note(self, kind: str, text: str) -> None:
        with self.lock:
            self.events.append((time.time(), kind, text))

    # --- waiting -------------------------------------------------------------
    def not_ready(self) -> List[Container]:
        with self.lock:
            return [c for c in self.containers if c.state not in READY]

    def wait_until_ready(self, timeout: float) -> None:
        """After `up` returned: until nothing is starting, one has failed (it won't
        recover, and its dependents stay "waiting" for good) or timeout."""
        time.sleep(1)
        self.wake.set()
        end = time.time() + timeout
        while time.time() < end:
            time.sleep(1)
            with self.lock:
                cs = list(self.containers)
            if cs and all(c.state in READY for c in cs):
                return
            if any(c.state == "failed" for c in cs):
                return

    def stop(self, final: bool = True) -> None:
        # The watch loop first: a snapshot it is in the middle of can still start
        # log followers, which must not outlive this.
        self.stopping.set()
        self.wake.set()
        for t in self.threads[1:] if self.events_proc is not None else self.threads:
            t.join(timeout=10)
        with self.lock:
            followers, self.followers = list(self.followers.values()), {}
        for proc in followers:
            self._end(proc)
        if self.events_proc is not None:
            self._end(self.events_proc)
            self.threads[0].join(timeout=3)
        if final:
            self.snapshot(volumes=True)
        if self.live is not None:
            self.live.refresh()
            self.live.stop()
        elif final:
            self.print_new()

    # --- log mode --------------------------------------------------------------
    def print_new(self) -> None:
        with self.lock:
            new = self.events[self.printed:]
            self.printed = len(self.events)
        now = time.time()
        for t, kind, text in new:
            style = KIND_STYLE[kind]
            body = f"[{style}]{escape(text)}[/]" if style else escape(text)
            console.print(f"  [dim][{_elapsed(t - self.t0)}][/] {body}")
        if new:
            self.quiet_since = now
        elif now - self.quiet_since >= 30:
            self.quiet_since = now
            waiting = ", ".join(f"{c.service} ({c.status})" for c in self.not_ready())
            if waiting:
                ready, total = self.progress()
                console.print(f"  [dim][{_elapsed(now - self.t0)}][/] [yellow]{ready} of {total} ready; "
                              f"still waiting on: {escape(waiting)}[/]")

    # --- the live view ---------------------------------------------------------
    def progress(self) -> Tuple[int, int]:
        with self.lock:
            seen = {c.service for c in self.containers}
            ready = sum(1 for c in self.containers if c.state in READY)
            total = len(self.containers) + sum(1 for s in self.services if s not in seen)
        return ready, total

    def rows(self) -> List[Tuple[str, str]]:
        with self.lock:
            rows = [(c.service, c.state) for c in self.containers]
            seen = {c.service for c in self.containers}
        rows += [(s, "pending") for s in self.services if s not in seen]
        return sorted(rows)

    def __rich__(self):
        width, height = console.size
        ready, total = self.progress()
        now = time.time()
        header = Table.grid(padding=(0, 2))
        header.add_row(Text(_elapsed(now - self.t0), style="dim"),
                       ProgressBar(total=max(total, 1), completed=ready, width=24 if width >= 80 else 12,
                                   complete_style="green" if total and ready == total else "cyan"),
                       Text(f"{ready} of {total} ready" + (f"   volumes: {self.volumes}" if self.volumes else "")))
        rows = self.rows()
        side = width >= 100
        body_max = max(3, height - 5)
        cap = body_max if side else max(3, body_max - 8)
        shown, hidden = rows, 0
        if len(rows) > cap:  # too many for the window: only what isn't ready, then a count
            shown = [r for r in rows if r[1] not in READY][:cap - 1]
            hidden = len(rows) - len(shown)
        svc = Table(box=None, pad_edge=False, show_edge=False, header_style="dim", padding=(0, 1))
        svc.add_column("SERVICES", no_wrap=True, min_width=30)
        svc.add_column("", no_wrap=True)
        for name, state in shown:
            style = STATE_STYLE.get(state, "yellow")
            svc.add_row(Text.assemble((STATE_MARK[style] + " ", style), name), Text(state, style=style))
        if hidden:
            svc.add_row(Text(f"  + {hidden} more", style="dim"), "")
        lines = max(len(shown) + (1 if hidden else 0), 8) if side else 6
        lines = min(lines, body_max)
        with self.lock:
            recent = self.events[-lines:]
        activity = [Text.assemble((_elapsed(t - self.t0) + " ", "dim"), (text, KIND_STYLE[kind] or "default"),
                                  no_wrap=True, overflow="ellipsis") for t, kind, text in recent]
        if side:
            grid = Table.grid(expand=True, padding=(0, 2))
            grid.add_column(no_wrap=True)
            grid.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
            grid.add_row(svc, Group(Text("ACTIVITY", style="dim"), *activity))
            return Group(header, grid)
        return Group(header, svc, Text(""), Text("ACTIVITY", style="dim"), *activity)


def explain_not_ready(rt: Runtime, containers: List[Container]) -> None:
    """For each container that failed, is unhealthy or is still starting: its last
    log lines and its health check's last results, so the cause is on screen.
    One merely "waiting" is blocked on another and is only named."""
    blocked = []
    for c in containers:
        if c.state in READY:
            continue
        if c.state == "waiting":
            blocked.append(c.service)
            continue
        console.print()
        console.print(f"  [red]{escape(c.service)} ({escape(c.name)}) is {c.state}. Its last log lines:[/]")
        res = rt.run("logs", "--tail", "25", c.name, timeout=20)
        for line in (res.stdout + res.stderr).splitlines()[-25:]:
            console.print(f"      {escape(_ANSI.sub('', line))}", soft_wrap=True)
        hc = rt.out("inspect", "-f", "{{json .State.Health}}", c.name).strip()
        try:
            logs = (json.loads(hc) or {}).get("Log") or []
        except ValueError:
            logs = []
        if logs:
            console.print("    Its health check's last results (exit code: output):")
            for entry in logs[-3:]:
                out = (entry.get("Output") or "").strip().replace("\n", " ")[:200] or "(no output)"
                console.print(f"      {entry.get('ExitCode')}: {escape(out)}")
    if blocked:
        console.print()
        console.print(f"  [yellow]waiting on the above: {escape(', '.join(blocked))}[/]")
