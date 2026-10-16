"""`dojo stop` saves what the class produced before it deletes the volumes.

Writes results/<date>_<time>_<workshop>/ (git-ignored; it holds student comments and scores):

  manifest.json    which workshop, the command that started it, when it started and stopped, how long, who
                   was in it, which services ran, and what was saved or skipped and why
  feedback.csv/.json   the feedback module's answers (no usernames, as in the /admin export)
  achievements.csv/.json   scores and unlocks per student (json adds CTF/SOC data)
  roster.csv       who signed in and whether they were a demo bot

Best effort: every part is tried on its own, a failure is recorded in the manifest and never stops the
teardown. A stack nobody used (no sign-ins, no feedback, no scores) saves nothing."""
from __future__ import annotations

import csv
import io
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import paths, results, state
from .runtime import Runtime
from .stackapi import StackError, call, running

RESULTS_DIR = paths.REPO / "results"


def fetch_feedback(rt: Runtime) -> Dict[str, Any]:
    """The feedback module's export as {"questions": ..., "answers": [...]} (raises StackError if it isn't running)."""
    status, doc = call(rt, "feedback", "GET", "/feedback-admin/api/export?format=json")
    if status != 200 or not isinstance(doc, dict):
        raise StackError(f"The feedback service refused the export (HTTP {status}).")
    return doc


def fetch_feedback_csv(rt: Runtime) -> str:
    status, text = call(rt, "feedback", "GET", "/feedback-admin/api/export?format=csv")
    if status != 200 or not isinstance(text, str):
        raise StackError(f"The feedback service refused the export (HTTP {status}).")
    return text


def _roster_csv(rows: List[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "name", "bot", "active"])
    for r in rows:
        w.writerow([r.get("studentId", ""), r.get("name") or "", r.get("ip") == "bot", bool(r.get("active"))])
    return buf.getvalue()


def _folder(workshop: str, now: float) -> Path:
    base = f"{time.strftime('%Y-%m-%d_%H%M', time.localtime(now))}_{workshop or 'stack'}"
    d, n = RESULTS_DIR / base, 2
    while d.exists():
        d = RESULTS_DIR / f"{base}-{n}"
        n += 1
    return d


def save(rt: Runtime, now: Optional[float] = None) -> Optional[Path]:
    """Write the session folder for the stack that is up now; None when there is nothing worth keeping."""
    now = now or time.time()
    cur = state.read_current()
    got: Dict[str, Any] = {}       # file -> text
    notes: Dict[str, str] = {}     # part -> why it was skipped
    services = sorted({c.service for c in running(rt)})

    roster: List[Dict[str, Any]] = []
    try:
        roster = results.roster(rt)
        got["roster.csv"] = _roster_csv(roster)
    except StackError as exc:
        notes["roster"] = str(exc)

    answers = 0
    try:
        fb = fetch_feedback(rt)
        answers = len(fb.get("answers") or [])
        got["feedback.json"] = json.dumps(fb, indent=2) + "\n"
        got["feedback.csv"] = fetch_feedback_csv(rt)
    except StackError as exc:
        notes["feedback"] = str(exc)

    scored = 0
    try:
        res = results.fetch_results(rt)
        scored = sum(1 for s in res.get("students", []) if s.get("score") or s.get("unlocks"))
        got["achievements.json"] = results.render(res, "json")
        got["achievements.csv"] = results.render(res, "csv")
    except StackError as exc:
        notes["achievements"] = str(exc)

    humans = [r for r in roster if r.get("ip") != "bot"]
    if not roster and not answers and not scored:
        return None
    started = cur.started_at if cur and cur.started_at else None
    manifest = {
        "workshop": cur.workshop if cur else "",
        "command": cur.command if cur else "",
        "profile": cur.env_name if cur else None,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(started)) if started else None,
        "stopped_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(now)),
        "duration_minutes": round((now - started) / 60, 1) if started else None,
        "students": len(humans), "demo_bots": len(roster) - len(humans),
        "feedback_answers": answers, "students_with_progress": scored,
        "services": services, "saved": sorted(got), "skipped": notes,
    }
    d = _folder(manifest["workshop"], now)
    d.mkdir(parents=True)
    for name, text in got.items():
        (d / name).write_text(text)
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return d
