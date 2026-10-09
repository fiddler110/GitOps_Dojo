"""`dojo status`: what is running, from where, and whether it is healthy."""
from __future__ import annotations

import json
import time
from typing import Any, Dict

from rich.table import Table

from . import paths, state
from .envfiles import operator_env
from .runtime import READY, Runtime, project_name
from .ui import STATE_MARK, STATE_STYLE, console
from .workshops import find

# Asked inside the allocator container, with that container's own gateway
# token: the token never appears on a host command line or in `ps`.
_ALLOCATOR_QUERY = r'''
import json, os, urllib.request
def get(path):
    req = urllib.request.Request("http://127.0.0.1:8080" + path,
                                 headers={"X-Gateway-Token": os.environ["GATEWAY_TOKEN"]})
    return json.load(urllib.request.urlopen(req, timeout=4))
print(json.dumps({"sessions": get("/admin/api/sessions"), "status": get("/admin/api/status")}))
'''


def collect(rt: Runtime) -> Dict[str, Any]:
    cur = state.read_current()
    last = state.last_start()
    op_env = operator_env(cur.env_name if cur else None)
    project = project_name(op_env)
    containers = rt.containers(project)
    workshop = cur.workshop if cur else ""
    info: Dict[str, Any] = {
        "running": bool(containers),
        "workshop": workshop or None,
        "title": None,
        "started_as": cur.command if cur else ("./dojo " + " ".join(last) if last else None),
        "started_at": cur.started_at if cur and cur.started_at else None,
        "address": op_env.get("PUBLIC_BASE_URL"),
        "project": project,
        "volumes": len(rt.volumes(project)),
        "services": [{"service": c.service, "container": c.name, "state": c.state, "status": c.status}
                     for c in containers],
        "ready": sum(1 for c in containers if c.state in READY),
        "students": None,
        "checks": None,
        # A start in flight shows up here before any container has appeared,
        # so `dojo ps` can tell "nothing's up yet" from "another dojo is
        # mid-build": {pid, what, started_at} or None.
        "in_progress": state.RunLock.peek(),
    }
    ws = find(workshop) if workshop else None
    if ws:
        info["title"] = ws.title
    allocator = next((c for c in containers if c.service == "allocator" and c.state in READY), None)
    if allocator:
        res = rt.run("exec", allocator.name, "python3", "-c", _ALLOCATOR_QUERY, timeout=15)
        if res.returncode == 0:
            try:
                data = json.loads(res.stdout)
                rows = data.get("sessions") or []
                info["students"] = {
                    "signed_in": sum(1 for r in rows if r.get("ip") != "bot"),
                    "active": sum(1 for r in rows if r.get("ip") != "bot" and r.get("active")),
                    "bots": sum(1 for r in rows if r.get("ip") == "bot"),
                }
                info["checks"] = (data.get("status") or {}).get("services")
            except (ValueError, AttributeError):
                pass
    return info


def show(info: Dict[str, Any]) -> None:
    ip = info.get("in_progress")
    if ip:
        age = ""
        if ip.get("started_at"):
            secs = max(0, int(time.time() - ip["started_at"]))
            age = f"  [dim]({secs // 60}m {secs % 60:02d}s ago)[/]"
        detail = ip["what"] or f"pid {ip['pid']}"
        console.print(f"[yellow]A build or start is in progress:[/] {detail}{age}")
        console.print(f"  [dim]Another '{paths.PROG} <workshop>' will refuse until this finishes.[/]")
        console.print()
    if not info["running"]:
        if not ip:
            console.print("[yellow]No workshop stack is running.[/]")
        if info["volumes"]:
            console.print(f"  {info['volumes']} volume(s) left from an earlier run: "
                          f"'{paths.PROG} stop' removes them, or a start of the same workshop reuses them.")
        if info["started_as"]:
            console.print(f"  Last started here as: [cyan]{info['started_as']}[/]  "
                          f"('{paths.PROG} restart' starts it again)")
        return
    title = f" ({info['title']})" if info["title"] else ""
    console.print(f"[bold]Workshop:[/]  {info['workshop'] or '(not recorded: started from another checkout?)'}{title}")
    if info["started_as"]:
        since = ""
        if info.get("started_at"):
            mins = int((time.time() - info["started_at"]) // 60)
            since = f"  [dim]({mins // 60}h {mins % 60:02d}m ago)[/]" if mins >= 60 else f"  [dim]({mins} min ago)[/]"
        console.print(f"[bold]Started as:[/] {info['started_as']}{since}")
    if info["address"]:
        console.print(f"[bold]Address:[/]   {info['address']}")
    total = len(info["services"])
    colour = "green" if info["ready"] == total else "yellow"
    console.print(f"[bold]Stack:[/]     [{colour}]{info['ready']} of {total} ready[/]  ·  "
                  f"{info['volumes']} volume(s)  ·  project '{info['project']}'")
    s = info["students"]
    if s is not None:
        console.print(f"[bold]Students:[/]  {s['signed_in']} signed in, {s['active']} active"
                      + (f"  ·  {s['bots']} demo bot(s)" if s["bots"] else ""))
    if info["checks"]:
        marks = "  ".join(f"[{'green' if c.get('state') == 'green' else 'yellow' if c.get('state') == 'amber' else 'red'}]"
                          f"{c.get('name')}[/]" for c in info["checks"])
        console.print(f"[bold]Portal:[/]    {marks}")
    table = Table(box=None, pad_edge=False, show_edge=False, header_style="dim")
    table.add_column("  service")
    table.add_column("container")
    table.add_column("state")
    table.add_column("status", style="dim")
    for row in info["services"]:
        style = STATE_STYLE.get(row["state"], "yellow")
        table.add_row(f"[{style}]{STATE_MARK[style]}[/] {row['service']}", row["container"],
                      f"[{style}]{row['state']}[/]", row["status"])
    console.print()
    console.print(table)
