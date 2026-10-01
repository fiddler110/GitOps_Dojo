"""Building a run's environment, and remembering where each value came from.

Two kinds of file, on purpose:
  * engine/.env and engine/.env.NAME are the operator's data. They are read
    literally (parse_literal): a password with '$', '`' or spaces arrives as
    typed. Same rules as dojo_load_env in engine/scripts/lib.sh.
  * workshop.env and module.env are shell code written by workshop authors:
    they derive tokens with $(...) and trim values with ${VAR#...}. They are
    run by sh with the environment built so far (source_shell), exactly as
    run.sh sources them.

The order is run.sh's: .env, .env.NAME, workshop.env; then, if the workshop has
modules, each module.env followed by .env, .env.NAME and workshop.env again,
so a module only supplies defaults and the operator and the workshop win.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import paths

KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SECRET_RE = re.compile(r"PASSWORD|TOKEN|SEED|SECRET|_KEY$|^KEY$")


class EnvError(Exception):
    pass


def parse_literal(path: Path) -> List[Tuple[str, str, int]]:
    """(key, value, line number) for each KEY=value line, values taken as written."""
    rows = []
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.rstrip("\r").lstrip(" \t")
        if line.startswith("export ") or line.startswith("export\t"):
            line = line[7:].lstrip(" \t")
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if not KEY_RE.match(key):
            continue
        if value[:1] in ('"', "'") and value[0] in value[1:]:
            value = value[1:value.index(value[0], 1)]
        else:
            value = re.sub(r"[ \t]+#.*$", "", value).rstrip(" \t")
        rows.append((key, value, n))
    return rows


def source_shell(path: Path, env: Dict[str, str]) -> Dict[str, str]:
    """The environment after `set -a; . path` in sh, starting from env."""
    script = 'set -a; . "$1" >&2; set +a; exec "$2" -c "import json, os; print(json.dumps(dict(os.environ)))"'
    try:
        res = subprocess.run(["sh", "-c", script, "sh", str(path), sys.executable],
                             env=env, cwd=str(paths.ENGINE), capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise EnvError(f"{path}: took more than 60 s to run")
    if res.returncode != 0:
        raise EnvError(f"{path} failed:\n{res.stderr.strip()}")
    return json.loads(res.stdout)


@dataclass
class Origin:
    source: str   # e.g. "engine/.env:12", "modules/openbao/module.env"
    value: str


@dataclass
class Resolution:
    env: Dict[str, str]
    origins: Dict[str, List[Origin]] = field(default_factory=dict)  # key -> every value it was given, in order
    modules: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def source_of(self, key: str) -> str:
        chain = self.origins.get(key)
        return chain[-1].source if chain else "environment"


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(paths.REPO))
    except ValueError:
        return str(path)


def mask(key: str, value: str) -> str:
    """A secret's value shown only as its length (and whether it is a public default)."""
    if not SECRET_RE.search(key) or not value:
        return value
    from .checks import is_default_password
    return "<public default!>" if is_default_password(value) else f"<hidden, {len(value)} chars>"


class _Builder:
    def __init__(self, base: Dict[str, str]) -> None:
        self.env = dict(base)
        self.origins: Dict[str, List[Origin]] = {}

    def _note(self, key: str, source: str, value: str) -> None:
        """Record that source gave key this value. The second load pass (after
        the modules) re-applies the same files: an entry seen before moves to
        the end instead of repeating, so a chain reads once, in winning order."""
        chain = self.origins.setdefault(key, [])
        chain[:] = [o for o in chain if (o.source, o.value) != (source, value)]
        chain.append(Origin(source, value))

    def literal(self, path: Path) -> None:
        for key, value, n in parse_literal(path):
            self.env[key] = value
            self._note(key, f"{rel(path)}:{n}", value)

    def shell(self, path: Path) -> None:
        after = source_shell(path, self.env)
        for key, value in after.items():
            if self.env.get(key) != value and key not in ("_", "PWD", "SHLVL", "OLDPWD"):
                self._note(key, rel(path), value)
        self.env = after


def module_list(env: Dict[str, str], workshop_dir: Path) -> Tuple[List[str], List[str]]:
    """MODULES= from the workshop, plus `achievements` when ACHIEVEMENTS_ENABLED=1 and
    the workshop has a catalog. Returns (modules, warnings)."""
    mods = env.get("MODULES", "").split()
    warnings = []
    if env.get("ACHIEVEMENTS_ENABLED", "0") == "1":
        if (workshop_dir / "achievements" / "catalog.json").is_file():
            if "achievements" not in mods:
                mods.append("achievements")
        else:
            warnings.append(f"ACHIEVEMENTS_ENABLED=1 but {workshop_dir.name} has no achievements/catalog.json; "
                            "running without achievements.")
    return mods, warnings


def resolve(workshop: str, env_name: Optional[str] = None, base: Optional[Dict[str, str]] = None) -> Resolution:
    """The environment a start of this workshop runs with."""
    from .workshops import NAME_RE
    workshop_dir = paths.WORKSHOPS / workshop
    workshop_env = workshop_dir / "workshop.env"
    if not workshop_env.is_file():
        raise EnvError(f"No such workshop: {workshop} (expected {rel(workshop_env)})")
    if not paths.ENV_FILE.is_file():
        raise EnvError("engine/.env not found: run './run.sh setup' (or 'setup --default' for local use) first.")
    variant = paths.env_variant(env_name) if env_name else None
    if variant is not None and not variant.is_file():
        raise EnvError(f"--env {env_name}: engine/.env.{env_name} not found.")

    b = _Builder(base if base is not None else dict(os.environ))

    def operator_and_workshop() -> None:
        b.literal(paths.ENV_FILE)
        if variant is not None:
            b.literal(variant)
        b.shell(workshop_env)

    operator_and_workshop()
    mods, warnings = module_list(b.env, workshop_dir)
    for m in mods:
        if not NAME_RE.match(m):
            raise EnvError(f"MODULES: '{m}' is not a module name (lowercase letters, digits and '-').")
        if not (paths.MODULES / m).is_dir():
            raise EnvError(f"MODULES: no such module '{m}' (expected modules/{m}/).")
    if mods:
        for m in mods:
            module_env = paths.MODULES / m / "module.env"
            if module_env.is_file():
                b.shell(module_env)
        operator_and_workshop()
    return Resolution(b.env, b.origins, mods, warnings)


def operator_env(env_name: Optional[str] = None) -> Dict[str, str]:
    """Only engine/.env (+ .env.NAME), read literally: enough for addresses and
    ports without running any workshop's shell code."""
    out: Dict[str, str] = {}
    for path in (paths.ENV_FILE, paths.env_variant(env_name) if env_name else None):
        if path is not None and path.is_file():
            out.update({k: v for k, v, _ in parse_literal(path)})
    return out
