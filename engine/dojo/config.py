"""dojo.toml and dojo.local.toml: the non-secret settings, in sections.

  dojo.toml        committed: defaults that are right for any machine.
  dojo.local.toml  git-ignored: this machine's sizing, terminal flavor, and the
                   named profiles (home, live, ...) that `--env NAME` selects.

A setting is `[section] key = value`; SCHEMA maps each one to the environment
variable the compose files and services read. Unknown sections or keys are an
error (a typo should not silently do nothing). `[env]` is the escape hatch: any
VARIABLE = "value", passed through as written. A profile repeats the same
sections under `[profiles.NAME.<section>]` and is laid over the base settings.

Secrets do not belong here: they live in the git-ignored .env (envfiles.py).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import paths

try:                      # 3.11+; older Pythons use the pinned wheel boot.py unpacks
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# (section, key) -> (environment variable, kind)
SCHEMA: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("general", "student_count"): ("STUDENT_COUNT", "int"),
    ("general", "student_prefix"): ("STUDENT_PREFIX", "str"),
    ("general", "class_username"): ("TTYD_USERNAME", "str"),
    ("general", "facilitator_username"): ("FACILITATOR_USERNAME", "str"),
    ("general", "forgejo_admin_user"): ("FORGEJO_ADMIN_USER", "str"),
    ("general", "forgejo_admin_email"): ("FORGEJO_ADMIN_EMAIL", "str"),
    ("general", "achievements"): ("ACHIEVEMENTS_ENABLED", "bool"),
    ("network", "public_base_url"): ("PUBLIC_BASE_URL", "str"),
    ("network", "lab_host_ip"): ("LAB_HOST_IP", "str"),
    ("network", "http_port"): ("GATEWAY_HTTP_PORT", "int"),
    ("network", "https_port"): ("GATEWAY_HTTPS_PORT", "int"),
    ("network", "gateway_listen"): ("GATEWAY_LISTEN", "str"),
    ("network", "trusted_proxies"): ("GATEWAY_TRUSTED_PROXIES", "str"),
    ("network", "allow_default_passwords"): ("ALLOW_DEFAULT_PASSWORDS", "bool"),
    ("network", "terminal_ingress_subnet"): ("TERMINAL_INGRESS_SUBNET", "str"),
    ("terminal", "flavor"): ("TERMINAL_FLAVOR", "flavor"),
    ("terminal", "font_family"): ("TERMINAL_FONT_FAMILY", "str"),
    ("terminal", "font_size"): ("TERMINAL_FONT_SIZE", "int"),
    ("terminal", "mem_limit"): ("WEB_TERMINAL_MEM_LIMIT", "str"),
    ("terminal", "pids_limit"): ("WEB_TERMINAL_PIDS_LIMIT", "int"),
    ("terminal", "nproc_limit"): ("TERMINAL_NPROC_LIMIT", "int"),
    ("terminal", "code_server_max_heap_mb"): ("CODE_SERVER_MAX_HEAP_MB", "int"),
    ("terminal", "reconnection_grace_seconds"): ("CODE_SERVER_RECONNECTION_GRACE_SECONDS", "int"),
    ("terminal", "idle_timeout_seconds"): ("CODE_SERVER_IDLE_TIMEOUT_SECONDS", "int"),
    ("bots", "count"): ("BOT_COUNT", "int"),
    ("bots", "prefix"): ("BOT_PREFIX", "str"),
    ("build", "corp_ca_bundle"): ("CORP_CA_BUNDLE", "str"),
    ("engine", "workshop_content_dir"): ("WORKSHOP_CONTENT_DIR", "str"),
    ("engine", "workshop_name"): ("WORKSHOP_NAME", "str"),
    ("engine", "forgejo_org"): ("FORGEJO_ORG", "str"),
    ("engine", "forgejo_repo"): ("FORGEJO_REPO", "str"),
}
BY_ENV = {env: (section, key, kind) for (section, key), (env, kind) in SCHEMA.items()}
SECTIONS = {s for s, _ in SCHEMA} | {"env"}

# The terminal flavor's friendly names -> what TERMINAL_FLAVOR holds.
FLAVORS = {"code-server": "web", "web": "web", "zellij": "zellij"}
FLAVOR_NAME = {"web": "code-server", "zellij": "zellij"}


class ConfigError(Exception):
    pass


def _to_env(where: str, kind: str, value) -> str:
    if kind == "bool":
        if not isinstance(value, bool):
            raise ConfigError(f"{where}: expected true or false, got {value!r}")
        return "1" if value else "0"
    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{where}: expected a whole number, got {value!r}")
        return str(value)
    if not isinstance(value, str):
        raise ConfigError(f"{where}: expected a quoted string, got {value!r}")
    if kind == "flavor":
        if value.strip().lower() not in FLAVORS:
            raise ConfigError(f"{where}: must be one of {', '.join(sorted(FLAVORS))}, got {value!r}")
        return FLAVORS[value.strip().lower()]
    return value


def _tables(path: Path, tables: dict, label: str) -> List[Tuple[str, str, str]]:
    """(env var, value, source) for each setting in a dict of sections."""
    rows = []
    for section, body in tables.items():
        if section not in SECTIONS:
            raise ConfigError(f"{rel(path)}: unknown section [{label}{section}] "
                              f"(known: {', '.join(sorted(SECTIONS))})")
        if not isinstance(body, dict):
            raise ConfigError(f"{rel(path)}: [{label}{section}] must be a table")
        for key, value in body.items():
            where = f"{rel(path)} [{label}{section}] {key}"
            if section == "env":
                if not KEY_RE.match(key):
                    raise ConfigError(f"{where}: not a variable name")
                rows.append((key, _to_env(where, "str", value), where))
                continue
            if (section, key) not in SCHEMA:
                known = ", ".join(k for s, k in SCHEMA if s == section)
                raise ConfigError(f"{where}: unknown setting (known in [{section}]: {known})")
            env, kind = SCHEMA[(section, key)]
            rows.append((env, _to_env(where, kind, value), where))
    return rows


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(paths.REPO))
    except ValueError:
        return str(path)


def read(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{rel(path)}: {exc}")


def base_rows(path: Path) -> List[Tuple[str, str, str]]:
    doc = read(path)
    return _tables(path, {k: v for k, v in doc.items() if k != "profiles"}, "")


def profile_rows(path: Path, name: str) -> List[Tuple[str, str, str]]:
    profiles = read(path).get("profiles", {})
    if not isinstance(profiles, dict):
        raise ConfigError(f"{rel(path)}: [profiles] must hold tables like [profiles.home.network]")
    return _tables(path, profiles.get(name, {}), f"profiles.{name}.")


def profile_names(path: Path) -> List[str]:
    profiles = read(path).get("profiles", {})
    return sorted(profiles) if isinstance(profiles, dict) else []


# --- writing (dojo.local.toml) ------------------------------------------------------

def _literal(kind: str, value: str) -> str:
    if kind == "bool":
        return "true" if value in ("1", "true", "yes", "on") else "false"
    if kind == "int" and re.fullmatch(r"-?\d+", value):
        return value
    if kind == "flavor":
        value = FLAVOR_NAME.get(FLAVORS.get(value.strip().lower(), ""), value)
    return json.dumps(value, ensure_ascii=False)


def _parse_value(kind: str, value: str):
    """A typed value back from its environment string, for comparing with a default."""
    if kind == "bool":
        return value in ("1", "true", "yes", "on")
    if kind == "int" and re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def locate(env_key: str) -> Tuple[str, str, str]:
    """(section, key, kind) a variable is written under: its schema slot, else [env]."""
    return BY_ENV.get(env_key, ("env", env_key, "str"))


def set_value(env_key: str, value: str, profile: Optional[str] = None,
              path: Optional[Path] = None, skip_default: bool = False) -> None:
    """Set one variable in dojo.local.toml (or `path`), keeping everything else as written.
    skip_default: do not add a line that only repeats dojo.toml (an existing line is still updated)."""
    path = path or paths.LOCAL_CONFIG
    section, key, kind = locate(env_key)
    if skip_default and not profile:
        default = {k: v for k, v, _ in base_rows(paths.CONFIG)}.get(env_key)
        if default is not None and default == _to_env("", kind, _parse_value(kind, value)):
            if not (path.is_file() and re.search(rf"^\s*{re.escape(key)}\s*=", path.read_text(), re.M)):
                return
    header = f"[profiles.{profile}.{section}]" if profile else f"[{section}]"
    line = f"{key} = {_literal(kind, value)}"
    lines = path.read_text().splitlines() if path.is_file() else []
    start = next((i for i, l in enumerate(lines) if l.strip() == header), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines += [header, line]
    else:
        end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
        hit = next((i for i in range(start + 1, end) if re.match(rf"\s*{re.escape(key)}\s*=", lines[i])), None)
        if hit is not None:
            lines[hit] = line
        else:
            at = end
            while at > start + 1 and not lines[at - 1].strip():
                at -= 1
            lines.insert(at, line)
    path.write_text("\n".join(lines) + "\n")
    read(path)  # parses again: a bad write is reported now, not at the next start
