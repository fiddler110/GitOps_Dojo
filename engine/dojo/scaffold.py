"""`new-workshop`: a new pack in workshops/<name>/ from workshops/assets/template/.

Every {{key}} in the template's files is replaced; compose/ (the terminal
Dockerfile) is copied only when asked for. Nothing is written if a check fails.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from . import paths
from .workshops import NAME_RE, modules, workshops

TEMPLATE = paths.WORKSHOPS / "assets" / "template"
# workshop.env is sourced as shell and the slides are HTML: keep the free text plain.
UNSAFE = re.compile(r'["$`\\<>\n]')


class ScaffoldError(Exception):
    pass


@dataclass
class Scaffold:
    name: str
    title: str = ""
    description: str = ""
    modules: str = ""
    order: int = -1          # -1: after the last workshop in the learning path
    duration: str = ""       # free text ("~2 h"), shown by `list`; "": a TODO
    org: str = "training"
    repo: str = ""           # "": the workshop's name
    terminal: bool = False   # also compose/terminal/Dockerfile

    def values(self) -> dict:
        return {"name": self.name, "title": self.title, "description": self.description,
                "modules": self.modules, "order": str(self.order), "duration": self.duration,
                "org": self.org, "repo": self.repo}


def prepare(s: Scaffold, reserved: Iterable[str]) -> Scaffold:
    """Check S and fill in its defaults; raise ScaffoldError saying what's wrong."""
    if not NAME_RE.match(s.name):
        raise ScaffoldError(f"'{s.name}' can't be a workshop name: lowercase letters, digits and dashes, "
                            "starting with a letter or digit.")
    if s.name in set(reserved) | {"assets"}:
        raise ScaffoldError(f"'{s.name}' is a command name; a workshop called that could never be started.")
    if (paths.WORKSHOPS / s.name).exists():
        raise ScaffoldError(f"workshops/{s.name} already exists.")
    if not TEMPLATE.is_dir():
        raise ScaffoldError(f"No template at {TEMPLATE}.")
    s.title = s.title or s.name.replace("-", " ").title()
    s.description = s.description or f"TODO: one sentence on what {s.title} teaches (shown on the login page)."
    s.duration = s.duration or "TODO: e.g. ~2 h"
    s.repo = s.repo or s.name
    for key in ("org", "repo"):
        if not NAME_RE.match(getattr(s, key)):
            raise ScaffoldError(f"--{key} '{getattr(s, key)}': lowercase letters, digits and dashes.")
    for key in ("title", "description", "duration"):
        if UNSAFE.search(getattr(s, key)):
            raise ScaffoldError(f'--{key} can\'t contain " $ ` \\ < > or a line break.')
    known = {m.name for m in modules()}
    wanted = s.modules.replace(",", " ").split()
    unknown = [m for m in wanted if m not in known]
    if unknown:
        raise ScaffoldError(f"No such module: {', '.join(unknown)} (known: {', '.join(sorted(known))}).")
    s.modules = " ".join(wanted)
    if s.order < 0:
        s.order = max((w.order for w in workshops() if w.order is not None), default=0) + 1
    return s


def plan(s: Scaffold) -> List[Path]:
    """The template files to copy (relative to the template), in order."""
    files = sorted(p.relative_to(TEMPLATE) for p in TEMPLATE.rglob("*") if p.is_file())
    return [f for f in files if s.terminal or f.parts[0] != "compose"]


def create(s: Scaffold) -> List[Path]:
    """Write workshops/<name>/ and return the files written (relative to it)."""
    dest = paths.WORKSHOPS / s.name
    values = s.values()
    files = plan(s)
    tmp = paths.WORKSHOPS / f".{s.name}.new"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        for rel in files:
            src, out = TEMPLATE / rel, tmp / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            text = re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], src.read_text())
            out.write_text(text)
            shutil.copymode(src, out)
        tmp.rename(dest)  # all or nothing: a half-made pack would show up in ./run.sh list
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return files
