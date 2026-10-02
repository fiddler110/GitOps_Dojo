"""Workshop packs (workshops/<name>/) and modules (modules/<name>/)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from . import paths

# A workshop or module name becomes an image tag and a file name.
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def read_var(env_file: Path, key: str) -> str:
    """A plain KEY=value from a workshop.env without running it (first match,
    a trailing # comment and quotes dropped): for names and orders shown in lists."""
    for line in env_file.read_text().splitlines():
        if line.startswith(f"{key}="):
            value = re.sub(r"[ \t]+#.*$", "", line[len(key) + 1:]).strip()
            return value.strip("\"'")
    return ""


@dataclass
class Workshop:
    name: str
    dir: Path
    title: str
    order: Optional[int]   # WORKSHOP_ORDER: 0 = showcase, 1.. = the learning path

    @property
    def env_file(self) -> Path:
        return self.dir / "workshop.env"

    @property
    def modules(self) -> List[str]:
        return read_var(self.env_file, "MODULES").split()


def workshops() -> List[Workshop]:
    """Every folder with a workshop.env, in learning-path order (WORKSHOP_ORDER),
    then the rest alphabetically."""
    found = []
    for d in sorted(paths.WORKSHOPS.iterdir()) if paths.WORKSHOPS.is_dir() else []:
        env = d / "workshop.env"
        if not env.is_file():
            continue
        order = read_var(env, "WORKSHOP_ORDER")
        found.append(Workshop(d.name, d, read_var(env, "WORKSHOP_NAME"), int(order) if order.isdigit() else None))
    return sorted(found, key=lambda w: (w.order is None, w.order or 0, w.name))


def find(name: str) -> Optional[Workshop]:
    return next((w for w in workshops() if w.name == name), None)


@dataclass
class Module:
    name: str
    dir: Path
    summary: str
    used_by: List[str] = field(default_factory=list)


def modules() -> List[Module]:
    """Every module; its summary is the first plain line of its README.md."""
    shops = workshops()
    found = []
    for d in sorted(paths.MODULES.iterdir()) if paths.MODULES.is_dir() else []:
        if not d.is_dir() or d.name.startswith("_"):  # modules/_shared/: files modules copy, not a module
            continue
        summary = ""
        readme = d / "README.md"
        if readme.is_file():
            for line in readme.read_text().splitlines():
                if line.strip() and not line.startswith("#"):
                    summary = line.replace("*", "").strip()[:80]
                    break
        found.append(Module(d.name, d, summary, [w.name for w in shops if d.name in w.modules]))
    return found
