"""Picking the right dnscontrol release asset name for the current OS/arch -
used by `dnsctl.py install-dnscontrol`."""

from __future__ import annotations

import platform


def platform_asset_name(version: str) -> str | None:
    system = platform.system()
    machine = platform.machine().lower()

    arch_map = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    arch = arch_map.get(machine)
    if not arch:
        return None

    if system == "Linux":
        return f"dnscontrol_{version}_linux_{arch}.tar.gz"
    if system == "Darwin":
        return f"dnscontrol_{version}_darwin_all.tar.gz"
    if system == "Windows":
        return f"dnscontrol_{version}_windows_{arch}.zip"
    return None
