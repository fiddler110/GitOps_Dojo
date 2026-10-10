"""`dojo roster`, `dojo reset-student`, `dojo export-results`: the facilitator's
admin views from the command line, through the same HTTP endpoints the /admin
workspace uses (called from inside the allocator / achievements container)."""
from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List

from rich.markup import escape
from rich.table import Table

from .runtime import Runtime
from .stackapi import StackError, call, find_container
from .ui import console

CSV_COLUMNS = ["rank", "user", "name", "score", "percent", "complete", "unlocks", "cheats", "moments"]


def roster(rt: Runtime) -> List[Dict[str, Any]]:
    status, data = call(rt, "allocator", "GET", "/admin/api/sessions")
    if status != 200 or not isinstance(data, list):
        raise StackError(f"The allocator refused the roster request (HTTP {status}).")
    return data


def show_roster(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        console.print("[yellow]No students are signed in.[/]")
        return
    table = Table(box=None, pad_edge=False, header_style="dim")
    for col in ("id", "name", "from", "active", "reset"):
        table.add_column(col)
    for r in rows:
        reset = r.get("reset") or {}
        table.add_row(escape(str(r.get("studentId", ""))), escape(str(r.get("name") or "")),
                      "bot" if r.get("ip") == "bot" else escape(str(r.get("ip") or "")),
                      "[green]yes[/]" if r.get("active") else "[dim]no[/]",
                      escape(str(reset.get("state") or "")) if isinstance(reset, dict) else "")
    console.print(table)
    humans = sum(1 for r in rows if r.get("ip") != "bot")
    console.print(f"[dim]{humans} student(s), {len(rows) - humans} demo bot(s)[/]")


def reset_student(rt: Runtime, user: str, optional: str = "") -> str:
    """Queue the Roster's Reset for USER; returns a one-line result. Raises StackError on refusal."""
    status, data = call(rt, "allocator", "POST", f"/admin/reset/{user}",
                        form={"confirm": user, "optional": optional})
    msg = data.get("error") if isinstance(data, dict) else ""
    if status == 202:
        return f"Reset of {user} queued (progress shows in 'roster' and the /admin Roster)."
    if status == 404:
        raise StackError(f"No such student or bot: {user} ('roster' lists the ids).")
    if status == 409:
        raise StackError(f"A reset of {user} is already running.")
    raise StackError(f"The allocator refused the reset (HTTP {status}{': ' + msg if msg else ''}).")


def fetch_results(rt: Runtime) -> Dict[str, Any]:
    try:
        find_container(rt, "achievements")
    except StackError as exc:
        if "No 'achievements'" in str(exc):
            raise StackError("The achievements module is not running in this workshop, so there are no results "
                             "to export (it needs ACHIEVEMENTS_ENABLED=1 and an achievements/catalog.json).")
        raise
    status, state_doc = call(rt, "achievements", "GET", "/achievements-admin/api/state")
    if status != 200 or not isinstance(state_doc, dict):
        raise StackError(f"The achievements service refused the request (HTTP {status}).")
    out: Dict[str, Any] = {"students": state_doc.get("students", []), "mttp": state_doc.get("mttp"),
                           "target_status": state_doc.get("target_status")}
    st, soc = call(rt, "achievements", "GET", "/achievements-admin/api/soc")   # only meaningful for CTF packs
    if st == 200 and isinstance(soc, dict):
        out["soc"] = soc
    return out


def render(results: Dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(results, indent=2) + "\n"
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for s in results.get("students", []):
        w.writerow([s.get("rank"), s.get("user"), s.get("name"), s.get("score"), s.get("percent"),
                    s.get("complete"), s.get("unlocks"), ";".join(s.get("cheats") or []),
                    ";".join(s.get("moments") or [])])
    return buf.getvalue()
