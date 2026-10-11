"""A workshop's Compose files and services."""
from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import paths
from .envfiles import Resolution
from .runtime import Runtime


def extra_files(res: Resolution) -> List[str]:
    """The -f files after docker-compose.yml, relative to engine/ as dojo writes
    them: each module's compose.yml in MODULES order, then the workshop overlay."""
    files = [f"../modules/{m}/compose.yml" for m in res.modules
             if (paths.MODULES / m / "compose.yml").is_file()]
    overlay = res.env.get("COMPOSE_OVERLAY", "")
    if overlay:
        files.append(overlay)
    return files


def compose_args(files: List[str]) -> List[str]:
    args = ["-f", "docker-compose.yml"]
    for f in files:
        args += ["-f", f]
    return args


def services(rt: Runtime, files: List[str], env: Dict[str, str]) -> List[str]:
    """This stack's Compose services; raises with Compose's own message if the
    merged config doesn't load."""
    res = subprocess.run([*rt.compose_cmd, *compose_args(files), "config", "--services"],
                         cwd=str(paths.ENGINE), env=env, capture_output=True, text=True, timeout=120)
    names = res.stdout.split()
    if res.returncode != 0 or not names:
        raise RuntimeError((res.stderr or res.stdout).strip() or "compose config printed no services")
    return names


_UNITS = {"b": 1 / 1048576, "k": 1 / 1024, "m": 1, "g": 1024}


def _mb(value: str) -> Optional[int]:
    """`512m`, `3g`, `2048k` or bytes as whole MB; None if it isn't a size."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([bkmg])?b?", value.strip().strip("'\"").lower())
    return int(float(m.group(1)) * _UNITS[m.group(2) or "b"]) if m else None


def parse_mem_limits(config: str) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """From `compose config` YAML: ({service: mem_limit in MB, or None when it has none}, one-shot
    services). A one-shot job (`restart: "no"`) exits once the stack is up, so it holds no memory."""
    limits: Dict[str, Optional[int]] = {}
    oneshot: List[str] = []
    in_services, svc = False, None
    for line in config.splitlines():
        if re.match(r"\S", line):
            in_services, svc = line.rstrip() == "services:", None
        elif in_services and re.match(r"  [^ #][^:]*:\s*$", line):
            svc = line.strip().rstrip(":")
            limits[svc] = None
        elif svc and line.startswith("    mem_limit:"):
            limits[svc] = _mb(line.split(":", 1)[1])
        elif svc and re.match(r"    restart:\s*['\"]?no['\"]?\s*$", line):
            oneshot.append(svc)
    return limits, oneshot


def parse_build_specs(config: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    """Return each Compose-built service's resolved image and build options."""
    services_config = config.get("services", {})
    if not isinstance(services_config, dict):
        raise ValueError("Compose config has no services mapping")
    found = {}
    for name, service in services_config.items():
        if not isinstance(service, dict) or not isinstance(service.get("build"), dict):
            continue
        image = service.get("image") or f"engine_{name}"
        found[name] = {"image": image, "build": service["build"]}
    return found


def parse_service_images(config: Dict[str, object]) -> Dict[str, str]:
    """Return resolved image references, including Compose's default names."""
    services_config = config.get("services", {})
    if not isinstance(services_config, dict):
        raise ValueError("Compose config has no services mapping")
    return {name: service.get("image") or f"engine_{name}"
            for name, service in services_config.items() if isinstance(service, dict)}


def render_image_override(images: Dict[str, str], hashes: Dict[str, str]) -> str:
    """Render stable image aliases and content labels for Compose builds."""
    rows = ["services:"]
    for service, image in sorted(images.items()):
        rows.extend((f"  {json.dumps(service)}:", f"    image: {json.dumps(image)}",
                     "    build:", "      labels:", f"        dojo.src-hash: {json.dumps(hashes[service])}"))
    return "\n".join(rows) + "\n"


def config_document(rt: Runtime, files: List[str], env: Dict[str, str]) -> Dict[str, object]:
    """Return Compose's resolved config as structured data."""
    command = [*rt.compose_cmd, *compose_args(files), "config"]
    docker_compose = (len(rt.compose_cmd) > 1 and Path(rt.compose_cmd[0]).name == "docker"
                      and rt.compose_cmd[1] == "compose")
    if docker_compose:
        command += ["--format", "json"]
    res = subprocess.run(command, cwd=str(paths.ENGINE), env=env, capture_output=True,
                         text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout).strip() or "compose config failed")
    if docker_compose:
        return json.loads(res.stdout)
    try:
        import yaml
        return yaml.safe_load(res.stdout)
    except ImportError:
        executable = shutil.which(rt.compose_cmd[0])
        if not executable:
            raise RuntimeError("could not locate the Compose provider to parse its YAML config")
        with open(executable, "rb") as provider:
            shebang = provider.readline().decode("utf-8", errors="replace").strip()
        interpreter = shlex.split(shebang[2:]) if shebang.startswith("#!") else []
        if interpreter and Path(interpreter[0]).name == "env":
            interpreter = interpreter[2:] if len(interpreter) > 1 and interpreter[1] == "-S" else interpreter[1:]
            if interpreter:
                interpreter[0] = shutil.which(interpreter[0]) or ""
        if not interpreter or not interpreter[0] or "python" not in Path(interpreter[0]).name.lower():
            raise RuntimeError("podman-compose's Python interpreter is unavailable to parse its YAML config")
        script = "import json,sys,yaml; sys.stdout.write(json.dumps(yaml.safe_load(sys.stdin.read())))"
        parsed = subprocess.run([interpreter[0], "-c", script], input=res.stdout,
                                capture_output=True, text=True, timeout=30)
        if parsed.returncode != 0:
            raise RuntimeError((parsed.stderr or "could not parse podman-compose config").strip())
        return json.loads(parsed.stdout)


def config_yaml(rt: Runtime, files: List[str], env: Dict[str, str]) -> str:
    """The merged Compose config, or a RuntimeError with Compose's own message."""
    res = subprocess.run([*rt.compose_cmd, *compose_args(files), "config"],
                         cwd=str(paths.ENGINE), env=env, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError((res.stderr or res.stdout).strip() or "compose config failed")
    return res.stdout


def mem_limits(rt: Runtime, files: List[str], env: Dict[str, str]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """This stack's services' memory limits (see parse_mem_limits); raises with Compose's message."""
    return parse_mem_limits(config_yaml(rt, files, env))


def read_state(path: Path) -> str:
    return path.read_text().strip() if path.is_file() else ""
