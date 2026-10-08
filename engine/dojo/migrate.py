"""One-time move from engine/.env + engine/.env.NAME to the root .env + dojo.local.toml.

Secrets (anything envfiles.SECRET_RE matches) go to the root .env, a profile's under
a `[NAME]` header. Everything else becomes a setting in dojo.local.toml. The old
files are renamed *.migrated, never deleted. Runs by itself the first time the CLI
starts in a checkout that has an engine/.env and no root .env.
"""
from __future__ import annotations

import os
from typing import Dict, List

from . import config, paths
from .envfiles import SECRET_RE, parse_literal

SKIP = {".env.example", ".env.previous", ".env.new", ".env.new.tmp"}


def variants() -> Dict[str, "paths.Path"]:
    out = {}
    for p in sorted(paths.ENGINE.glob(".env.*")):
        if p.name in SKIP or p.name.endswith(".migrated"):
            continue
        out[p.name[len(".env."):]] = p
    return out


def needed() -> bool:
    return paths.LEGACY_ENV.is_file() and not paths.ENV_FILE.is_file()


def _is_secret(key: str) -> bool:
    return key not in config.BY_ENV and bool(SECRET_RE.search(key))


def _defaults() -> Dict[str, str]:
    return {k: v for k, v, _ in config.base_rows(paths.CONFIG)}


def migrate() -> List[str]:
    msgs: List[str] = []
    defaults = _defaults()
    secrets: List[str] = []
    profile_secrets: Dict[str, List[str]] = {}

    def move(rows, profile):
        for key, value, _ in rows:
            if _is_secret(key):
                if profile and f"{key}={value}" in secrets:
                    continue   # same as the shared one
                (profile_secrets.setdefault(profile, []) if profile else secrets).append(f"{key}={value}")
            elif profile or defaults.get(key) != value:
                config.set_value(key, value, profile=profile)

    move(parse_literal(paths.LEGACY_ENV), None)
    sources = {None: paths.LEGACY_ENV, **variants()}
    for name, path in variants().items():
        move(parse_literal(path), name)

    old_umask = os.umask(0o077)
    try:
        lines = ["# Secrets only (git-ignored). Everything else is in dojo.toml / dojo.local.toml.",
                 "# Keys under a [name] header apply only with --env name.", ""] + secrets
        for name, rows in profile_secrets.items():
            lines += ["", f"[{name}]"] + rows
        paths.ENV_FILE.write_text("\n".join(lines) + "\n")
    finally:
        os.umask(old_umask)
    paths.ENV_FILE.chmod(0o600)

    for path in sources.values():
        path.rename(path.with_name(path.name + ".migrated"))
    msgs.append(f"Moved engine/.env into .env ({len(secrets)} secrets) and dojo.local.toml.")
    for name in variants_names(sources):
        msgs.append(f"Moved engine/.env.{name} into the '{name}' profile (--env {name}).")
    msgs.append("The old files are kept as engine/.env*.migrated; delete them once you are happy.")
    return msgs


def variants_names(sources) -> List[str]:
    return [n for n in sources if n]
