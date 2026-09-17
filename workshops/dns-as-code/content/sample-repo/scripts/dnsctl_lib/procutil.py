"""Wrappers around the external tools dnsctl shells out to: dnscontrol,
git, and a git-forge CLI (gh for GitHub, forgejo.py for Forgejo/Gitea -
see detect_forge() and gh() below; the two coexist, neither replaces the
other). REPO_ROOT here is this package's own repo checkout - identical
to the REPO_ROOT computed in dnsctl.py, just derived independently to avoid
a circular import."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from .cli_utils import eprint

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def exe_name(name: str) -> str:
    return f"{name}.exe" if platform.system() == "Windows" else name


def find_dnscontrol() -> str | None:
    found = shutil.which("dnscontrol")
    if found:
        return found
    # go install puts binaries in $GOBIN or $GOPATH/bin, which may not be on
    # PATH yet in this shell session - check the common locations directly.
    candidates = []
    gopath = os.environ.get("GOPATH")
    home = Path.home()
    if gopath:
        candidates.append(Path(gopath) / "bin" / exe_name("dnscontrol"))
    candidates.append(home / "go" / "bin" / exe_name("dnscontrol"))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def run_dnscontrol(args: list[str], env_overrides: dict) -> int:
    dnscontrol = find_dnscontrol()
    if not dnscontrol:
        eprint(
            "error: dnscontrol not found on PATH.\n"
            "  Run: python scripts/dnsctl.py install-dnscontrol\n"
            "  or:  go install github.com/DNSControl/dnscontrol/v4@latest"
        )
        return 1

    env = os.environ.copy()
    env.update(env_overrides)

    proc = subprocess.run([dnscontrol, *args], cwd=REPO_ROOT, env=env)
    return proc.returncode


def git(args: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=capture, text=capture
    )


def git_output(args: list[str]) -> str:
    return git(args, capture=True).stdout.strip()


# GitHub hosts gh already knows how to authenticate against out of the box.
# Anything else (git-server:3000 in this lab, or any other self-hosted
# Forgejo/Gitea) is assumed to be a Forgejo remote - see forgejo.py.
_GITHUB_HOSTS = {"github.com", "www.github.com"}


def detect_forge() -> str:
    """'github' or 'forgejo', based on the 'origin' remote's host. Cached
    per-process (dnsctl.py always runs as a single short-lived invocation,
    so there's no staleness concern from caching across a `git remote`
    change mid-run)."""
    global _forge_cache
    try:
        return _forge_cache
    except NameError:
        pass
    url = git_output(["remote", "get-url", "origin"])
    host = ""
    if "://" in url:
        host = url.split("://", 1)[1].split("/", 1)[0].split("@")[-1].split(":")[0]
    elif "@" in url and ":" in url:  # scp-like git@github.com:owner/repo.git
        host = url.split("@", 1)[1].split(":", 1)[0]
    _forge_cache = "github" if host in _GITHUB_HOSTS else "forgejo"
    return _forge_cache


def have_gh() -> bool:
    if detect_forge() == "github":
        return shutil.which("gh") is not None
    return True  # forgejo.py is pure stdlib - always "available"


def require_gh() -> bool:
    if have_gh():
        return True
    eprint("error: GitHub CLI ('gh') not found on PATH. Install it: https://cli.github.com/")
    return False


def gh(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    """Dispatches to the real `gh` binary against a GitHub remote, or to
    forgejo.py's API client against everything else. Same call shape and
    CompletedProcess return either way, so every dnsctl.py command function
    that calls gh([...]) works unmodified against either forge."""
    if detect_forge() == "github":
        return subprocess.run(
            ["gh", *args], cwd=REPO_ROOT, capture_output=capture, text=capture
        )
    from . import forgejo

    return forgejo.run(args, capture=capture)
