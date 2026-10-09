"""Building a run's environment, and remembering where each value came from.

Two kinds of input, on purpose:
  * The operator's data: dojo.toml and dojo.local.toml (settings, config.py) and
    the root .env (secrets). .env is read literally (parse_literal): a password
    with '$', '`' or spaces arrives as typed. It may have `[home]`-style
    sections; a section applies only when that profile is selected (--env).
  * workshop.env and module.env are shell code written by workshop authors:
    they derive tokens with $(...) and trim values with ${VAR#...}. They are
    run by sh with the environment built so far (source_shell), exactly as
    dojo sources them.

Operator layers, lowest first: dojo.toml, dojo.local.toml, .env; then, for each
selected profile (--env a,b), that profile's dojo.toml, dojo.local.toml and .env
section. Then workshop.env; and, if the workshop has modules, each module.env
followed by the operator layers and workshop.env again, so a module only
supplies defaults and the operator and the workshop win.
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

from . import config, paths

KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SECRET_RE = re.compile(r"PASSWORD|TOKEN|SEED|SECRET|_KEY$|^KEY$")


class EnvError(Exception):
    pass


SECTION_RE = re.compile(r"^\[([a-z0-9][a-z0-9-]*)\]$")


def parse_sections(path: Path, sections: bool = True) -> List[Tuple[Optional[str], str, str, int]]:
    """(section, key, value, line number) for each KEY=value line, values taken as written.
    section is None above the first `[name]` header (and always, with sections=False)."""
    rows = []
    section = None
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.rstrip("\r").lstrip(" \t")
        if sections:
            m = SECTION_RE.match(line.rstrip())
            if m:
                section = m.group(1)
                continue
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
        rows.append((section, key, value, n))
    return rows


def parse_literal(path: Path, profile: Optional[str] = None,
                  sections: bool = False) -> List[Tuple[str, str, int]]:
    """(key, value, line number) for each KEY=value line, values taken as written.
    With sections=True (the root .env) lines under `[name]` count only for profile=name."""
    return [(k, v, n) for sec, k, v, n in parse_sections(path, sections) if sec is None or sec == profile]


def env_sections(path: Path) -> List[str]:
    """The `[name]` headers of a .env."""
    return sorted({sec for sec, *_ in parse_sections(path) if sec})


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
    source: str   # e.g. ".env:12", "modules/openbao/module.env"
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

    def row(self, key: str, value: str, source: str) -> None:
        self.env[key] = value
        self._note(key, source, value)

    def operator(self, profiles: List[str]) -> None:
        try:
            self._operator(profiles)
        except config.ConfigError as exc:
            raise EnvError(str(exc))

    def _operator(self, profiles: List[str]) -> None:
        """The operator's layers, lowest first (see the module docstring)."""
        for path in (paths.CONFIG, paths.LOCAL_CONFIG):
            for key, value, source in config.base_rows(path):
                self.row(key, value, source)
        if paths.ENV_FILE.is_file():
            for key, value, n in parse_literal(paths.ENV_FILE, sections=True):
                self.row(key, value, f"{rel(paths.ENV_FILE)}:{n}")
        for name in profiles:
            for path in (paths.CONFIG, paths.LOCAL_CONFIG):
                for key, value, source in config.profile_rows(path, name):
                    self.row(key, value, source)
            if paths.ENV_FILE.is_file():
                for sec, key, value, n in parse_sections(paths.ENV_FILE):
                    if sec == name:
                        self.row(key, value, f"{rel(paths.ENV_FILE)}:{n} [{name}]")

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
        raise EnvError(f".env not found: run '{paths.PROG} setup' (or 'setup --default' for local use) first.")
    profiles = split_profiles(env_name)

    b = _Builder(base if base is not None else dict(os.environ))
    # The achievements toggle set in the shell beats the operator's files, so one run (or a
    # restart repeating the running start) can switch it without editing the file.
    shell_toggle = b.env.get("ACHIEVEMENTS_ENABLED")

    def operator_and_workshop() -> None:
        b.operator(profiles)
        if shell_toggle is not None:
            b.env["ACHIEVEMENTS_ENABLED"] = shell_toggle
            b._note("ACHIEVEMENTS_ENABLED", "environment", shell_toggle)
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


def split_profiles(env_name: Optional[str], strict: bool = True) -> List[str]:
    """`--env a,b` -> [a, b]; each must be defined in dojo.toml, dojo.local.toml or a .env section."""
    names = [n for n in (env_name or "").split(",") if n]
    known = known_profiles()
    if not strict:
        return [n for n in names if n in known]
    for n in names:
        if n not in known:
            raise EnvError(f"--env {n}: no such profile. Define [profiles.{n}.*] in dojo.local.toml "
                           f"or a [{n}] section in .env"
                           + (f" (known: {', '.join(sorted(known))})." if known else "."))
    return names


def known_profiles() -> set:
    names = set(config.profile_names(paths.CONFIG)) | set(config.profile_names(paths.LOCAL_CONFIG))
    if paths.ENV_FILE.is_file():
        names |= set(env_sections(paths.ENV_FILE))
    return names


def operator_env(env_name: Optional[str] = None) -> Dict[str, str]:
    """Only the operator's files (dojo.toml, dojo.local.toml, .env, any profile),
    read literally: enough for addresses and ports without running any
    workshop's shell code."""
    b = _Builder({})
    b.operator(split_profiles(env_name, strict=False))  # stop/status must work after a profile is deleted
    return b.env
