"""`dojo validate`: static checks of every workshop pack, starting nothing."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from . import paths
from .envfiles import parse_literal
from .workshops import NAME_RE, Workshop, read_var, workshops


def _services_of(compose: Path) -> List[str]:
    """Top-level service names of a Compose file, read without a YAML library."""
    out, inside = [], False
    for line in compose.read_text().splitlines():
        if re.match(r"^services:\s*$", line):
            inside = True
        elif line and not line[0].isspace() and not line.startswith("#"):
            inside = False
        elif inside:
            m = re.match(r"^  ([A-Za-z0-9_.-]+):\s*(#.*)?$", line)
            if m:
                out.append(m.group(1))
    return out


def _check_env(ws: Workshop) -> List[str]:
    probs = []
    if not NAME_RE.match(ws.name):
        probs.append(f"folder name '{ws.name}' is not lowercase letters, digits and '-'")
    if not read_var(ws.env_file, "WORKSHOP_NAME"):
        probs.append("workshop.env has no WORKSHOP_NAME")
    if shutil.which("bash"):
        r = subprocess.run(["bash", "-n", str(ws.env_file)], capture_output=True, text=True)
        if r.returncode != 0:
            probs.append("workshop.env has a shell syntax error: " + r.stderr.strip().splitlines()[-1][:160])
    return probs


def _check_modules(ws: Workshop) -> List[str]:
    probs = []
    for m in ws.modules:
        d = paths.MODULES / m
        if not d.is_dir() or m.startswith("_"):
            probs.append(f"MODULES lists '{m}' but modules/{m}/ does not exist")
    return probs


def _check_extensions(ws: Workshop) -> List[str]:
    """The renderer --dry-run uses (engine/allocator/render_extensions.py), run on the host with
    the compose services found statically. Needs only the standard library."""
    manifests = [(f"50-{n}-module-{m}.json", paths.MODULES / m / "extensions.json") for n, m in enumerate(ws.modules, 10)
                 if (paths.MODULES / m / "extensions.json").is_file()]
    if (ws.dir / "extensions.json").is_file():
        manifests.append((f"90-workshop-{ws.name}.json", ws.dir / "extensions.json"))
    if not manifests:
        return []
    for _, f in manifests:
        try:
            json.loads(f.read_text())
        except ValueError as exc:
            return [f"{f.relative_to(paths.REPO)} is not valid JSON: {exc}"]
    composes = [paths.ENGINE / "docker-compose.yml"] + [paths.MODULES / m / "compose.yml" for m in ws.modules] + \
               [ws.dir / "compose" / "docker-compose.override.yml"]
    services = sorted({s for c in composes if c.is_file() for s in _services_of(c)})
    env = {k: v for k, v, _ in parse_literal(ws.env_file)}
    for m in ws.modules:
        me = paths.MODULES / m / "module.env"
        if me.is_file():
            env.update({k: v for k, v, _ in parse_literal(me)})
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "in").mkdir()
        for name, f in manifests:
            shutil.copyfile(f, tmp / "in" / name)
        for d in ("gateway", "allocator"):
            (tmp / "out" / d).mkdir(parents=True)
        r = subprocess.run([sys.executable, "-B", str(paths.ENGINE / "allocator" / "render_extensions.py"), "--in", str(tmp / "in"),
                            "--out", str(tmp / "out"), "--services", " ".join(services) + " "],
                           capture_output=True, text=True, env={**os.environ, **env, "GATEWAY_TOKEN": "validate"})
    if r.returncode != 0:
        return [l[len("extensions: "):] if l.startswith("extensions: ") else l for l in r.stderr.strip().splitlines()[-6:]]
    return []


def _check_catalog(ws: Workshop) -> List[str]:
    validator = paths.MODULES / "achievements" / "catalog" / "validate.py"
    if not validator.is_file() or not (ws.dir / "achievements" / "catalog.json").is_file():
        return []
    r = subprocess.run([sys.executable, "-B", str(validator), str(ws.dir)], capture_output=True, text=True)
    return [] if r.returncode == 0 else (r.stdout + r.stderr).strip().splitlines()[-8:]


CHECKS = (("workshop.env", _check_env), ("modules", _check_modules),
          ("extensions.json", _check_extensions), ("achievements catalog", _check_catalog))


def validate(names: List[str]) -> List[Tuple[str, List[Tuple[str, List[str]]]]]:
    """[(workshop, [(check, problems)])]. An unknown name is a problem of its own."""
    known = {w.name: w for w in workshops()}
    result = []
    for name in names or list(known):
        ws = known.get(name)
        if ws is None:
            result.append((name, [("workshop", [f"no such workshop (expected workshops/{name}/workshop.env)"])]))
            continue
        result.append((name, [(title, fn(ws)) for title, fn in CHECKS]))
    return result
