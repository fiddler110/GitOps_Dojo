#!/usr/bin/env python3
"""
dnsctl - cross-platform helper for this dnscontrol/Cloudflare project.

Wraps the common operations documented in docs/ (setup, preview, push,
zone re-baseline, dnscontrol install) behind one script that works the
same way on Windows, macOS, and Linux. Standard library only - no pip
install required.

Usage:
    python scripts/dnsctl.py <command> [options]

Commands:
    doctor              Check that the local environment is set up correctly.
    setup               One-time local setup: git hook + .env scaffold.
    install-dnscontrol  Download the pinned dnscontrol release for this OS/arch.
    preview             Run `dnscontrol preview` (loads .env automatically).
    push                Run `dnscontrol push` (requires confirmation).
    import              Snapshot the live Cloudflare zone to a JS file for
                         manual merging back into dnsconfig.js.
    submit              Commit your dnsconfig.js change, push a branch, and
                         open a pull request for review.
    status              List open pull requests and their DNS Preview check status.
    review              Show a PR's file diff and its DNS Preview comment.
    approve             Approve a PR (GitHub blocks approving your own PR - see below).
    merge               Merge a PR once its DNS Preview check has passed.
    validate            Confirm a merged change's DNS Apply run succeeded and live
                         Cloudflare matches dnsconfig.js.
    record add          Interactively add a record to dnsconfig.js, e.g.
                         `record add plex.example.com`.
    record remove       Interactively remove a record from dnsconfig.js.
    record list         List records currently in dnsconfig.js.
    record edit         Change an existing record's value/priority/proxy/TTL in place.
    record update-ip    Bulk-replace an IP across every A record that points at it.
    record prune-acme   List/remove stale _acme-challenge TXT records.
    record sync-acme    Fold live Cloudflare's _acme-challenge TXT records into
                         dnsconfig.js (add missing, remove stale).
    lint                Fast offline sanity checks on dnsconfig.js.
    show                Table view of all records (terminal, CSV, or Markdown).

The submit/status/review/approve/merge/validate commands need a git-forge
CLI: `gh` against a GitHub remote, or dnsctl_lib/forgejo.py's own API
client against a Forgejo remote (this lab's git-server) - picked
automatically per the 'origin' remote's host, see procutil.detect_forge().

This copy is pointed at this lab's PowerDNS zone (dojo.test) instead of
the upstream template's Cloudflare/example.com - see CREDKEY/ZONES below.
Everything named "Cloudflare" in this file's own output (the record
wizard's proxy prompt, CLOUDFLARE_API_TOKEN env var, the ACME-sync
commands) is inherited unmodified from the real production script; it's
mostly harmless noise against PowerDNS and left as-is on purpose - see
this workshop's slides for why.

Run `python scripts/dnsctl.py <command> --help` for command-specific options.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

# Needed so `import dnsctl_lib` resolves whether dnsctl.py is run directly
# (python scripts/dnsctl.py ...) or loaded by file path, as the test suite
# does - neither guarantees scripts/ is already on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dnsctl_lib import install, procutil, records, render  # noqa: E402
from dnsctl_lib import env as env_lib  # noqa: E402
from dnsctl_lib.env import load_env_file  # noqa: E402
from dnsctl_lib.cli_utils import (  # noqa: E402
    eprint,
    parse_index_arg,
    prompt,
    prompt_yes_no,
    slugify,
)
from dnsctl_lib.procutil import (  # noqa: E402
    exe_name,
    find_dnscontrol,
    git,
    git_output,
    gh,
    have_gh,
    require_gh,
    run_dnscontrol,
)
from dnsctl_lib.records import (  # noqa: E402
    RECORD_LINE_PATTERN,
    build_record_line,
    classify_zone_line,
    fqdn_for,
    parse_record_line_full,
    split_top_level_args,
)

# This lab has no CI, so there's no workflow file to keep this in sync
# with - just match whatever's installed in compose/terminal/Dockerfile.
DNSCONTROL_VERSION = "5.0.4"
# Matches the top-level key in creds.json - this lab's PowerDNS provider,
# not the upstream template's "cloudflare".
CREDKEY = "powerdns"
# Every zone managed in dnsconfig.js. Keep this in sync with the D("...", ...)
# blocks there - the record wizard needs it to figure out which zone a given
# name belongs to (and to require --zone when a bare relative name is ambiguous).
# This lab manages exactly one zone, so --zone is never actually required.
ZONES = ["dojo.test"]

REPO_ROOT = procutil.REPO_ROOT
ENV_FILE = REPO_ROOT / ".env"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
CREDS_FILE = REPO_ROOT / "creds.json"
DNSCONFIG_FILE = REPO_ROOT / "dnsconfig.js"


def load_cloudflare_env(env_file: Path = ENV_FILE) -> dict:
    return env_lib.load_cloudflare_env(env_file)


def detect_zone(spec: str) -> str | None:
    """Return the zone from ZONES that `spec` is fully-qualified under, if any."""
    return records.detect_zone(spec, ZONES)


def parse_record_target(spec: str, zone: str | None = None) -> tuple[str, str]:
    """Resolve `spec` (optionally pinned to `zone`) against ZONES - see
    dnsctl_lib.records.parse_record_target for the full docstring."""
    return records.parse_record_target(spec, ZONES, zone=zone)


def find_zone_block(zone: str) -> tuple[int, int]:
    """Return (start, end) line indices of D("zone", ...) ... ); in dnsconfig.js."""
    lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()
    return records.find_zone_block_in_lines(lines, zone, source_name=DNSCONFIG_FILE.name)


def fetch_live_acme_snapshot(zone: str, env: dict) -> list[dict] | None:
    """Snapshot live Cloudflare state for `zone` via `dnscontrol get-zones` and
    return the parsed records (name/value/ttl) for its _acme-challenge TXT
    entries. Returns None if the snapshot itself failed (network/auth/etc) so
    callers can tell that apart from "zero live records"."""
    fd, tmp_path = tempfile.mkstemp(suffix=".js", prefix="dnsctl-acme-live-")
    os.close(fd)
    try:
        rc = run_dnscontrol(
            ["get-zones", "--format=js", f"--out={tmp_path}", CREDKEY, zone], env
        )
        if rc != 0:
            return None
        lines = Path(tmp_path).read_text(encoding="utf-8").splitlines()
        start, end = find_zone_block_in_lines(lines, zone, source_name="the live snapshot")
        live = []
        for i in range(start + 1, end):
            parsed = parse_record_line_full(lines[i])
            if not parsed:
                continue
            if parsed["type"] == "TXT" and (
                parsed["name"] == "_acme-challenge" or parsed["name"].startswith("_acme-challenge.")
            ):
                live.append(parsed)
        return live
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def fetch_live_acme_entries(zone: str, env: dict) -> set[tuple[str, str]] | None:
    """Like fetch_live_acme_snapshot, but reduced to the (name, value) pairs
    used for the prune-acme live cross-check."""
    snapshot = fetch_live_acme_snapshot(zone, env)
    if snapshot is None:
        return None
    return {(p["name"], p["value"]) for p in snapshot}


def local_acme_entries(zone: str) -> list[tuple[int, str, dict]]:
    """(index, line, parsed) for every _acme-challenge TXT line in `zone`'s
    D(...) block in dnsconfig.js, current file state."""
    start, end = find_zone_block(zone)
    lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()
    out = []
    for i in range(start + 1, end):
        parsed = parse_record_line_full(lines[i])
        if not parsed:
            continue
        if parsed["type"] == "TXT" and (
            parsed["name"] == "_acme-challenge" or parsed["name"].startswith("_acme-challenge.")
        ):
            out.append((i, lines[i], parsed))
    return out


def find_record_lines(
    name: str, zone: str, record_type: str | None = None
) -> list[tuple[int, str]]:
    """Find matching record lines within `zone`'s D(...) block only - not the whole file,
    since the same relative name can validly exist in more than one zone's block."""
    start, end = find_zone_block(zone)
    lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()
    matches = []
    for i in range(start + 1, end):
        m = RECORD_LINE_PATTERN.match(lines[i])
        if not m:
            continue
        line_type, line_name = m.group(1), m.group(2)
        if line_name != name:
            continue
        if record_type and line_type != record_type:
            continue
        matches.append((i, lines[i]))
    return matches


def insert_record_line(line: str, zone: str) -> None:
    _, end = find_zone_block(zone)
    lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()
    lines.insert(end, line)
    DNSCONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def remove_line_at(index: int) -> None:
    lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()
    del lines[index]
    DNSCONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def replace_line_at(index: int, new_line: str) -> None:
    """Overwrite one line in place. Safe to call once per index computed from
    the same read - unlike insert/remove, this never shifts other line numbers."""
    lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()
    lines[index] = new_line
    DNSCONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def offer_preview_and_submit(default_message: str, interactive: bool) -> None:
    """After editing dnsconfig.js, optionally run preview and hand off to submit."""
    if not interactive:
        print(
            "\nNext: python scripts/dnsctl.py preview   (verify the diff)\n"
            '      python scripts/dnsctl.py submit "..." (open a PR)'
        )
        return

    if prompt_yes_no("\nRun `dnscontrol preview` now to verify?", default_yes=True):
        cmd_preview(argparse.Namespace())

    if prompt_yes_no("\nOpen a pull request for this change now?", default_yes=False):
        message = prompt("Commit message / PR title", default=default_message)
        submit_args = argparse.Namespace(
            message=message,
            files=["dnsconfig.js"],
            branch=None,
            base="main",
            body=None,
            skip_preview=True,
            yes=True,
        )
        cmd_submit(submit_args)


def cmd_doctor(_args) -> int:
    ok = True

    print("== dnsctl doctor ==")

    dnscontrol = find_dnscontrol()
    if dnscontrol:
        version_proc = subprocess.run(
            [dnscontrol, "version"], capture_output=True, text=True
        )
        version = version_proc.stdout.strip() or version_proc.stderr.strip()
        print(f"[ok]   dnscontrol found: {dnscontrol} ({version})")
        if DNSCONTROL_VERSION not in version:
            print(
                f"[warn] installed dnscontrol version does not match the pinned "
                f"DNSCONTROL_VERSION ({DNSCONTROL_VERSION}). CI uses the pinned version, so a "
                f"local/CI mismatch can produce confusing 'works locally, fails in CI' diffs. "
                f"Fix: python scripts/dnsctl.py install-dnscontrol"
            )
    else:
        print("[FAIL] dnscontrol not found on PATH or in the usual go install location.")
        print("       Fix: python scripts/dnsctl.py install-dnscontrol")
        ok = False

    raw_env = load_env_file(ENV_FILE) if ENV_FILE.is_file() else {}
    vault = raw_env.get("CLOUDFLARE_KEYVAULT_NAME") or os.environ.get("CLOUDFLARE_KEYVAULT_NAME")
    local_token_present = "CLOUDFLARE_API_TOKEN" in raw_env or "CLOUDFLARE_API_TOKEN" in os.environ

    if not ENV_FILE.is_file() and not vault:
        print("[FAIL] .env not found, and no CLOUDFLARE_KEYVAULT_NAME configured.")
        print(
            f"       Fix: python3 scripts/dnsctl.py setup (copies {ENV_EXAMPLE.name} to .env "
            "for you - the placeholder value it ships with is enough for this lab's PowerDNS "
            "provider, which doesn't use this token at all; see .env.example's own comment)."
        )
        ok = False
    else:
        env = load_cloudflare_env()
        token = env.get("CLOUDFLARE_API_TOKEN")
        if token:
            source = "local .env/environment" if local_token_present else f"Azure Key Vault '{vault}'"
            print(f"[ok]   CLOUDFLARE_API_TOKEN available (length {len(token)}, source: {source}).")
        else:
            print("[FAIL] CLOUDFLARE_API_TOKEN not available from .env, the environment, or Key Vault.")
            if vault:
                print(
                    f"       Key Vault '{vault}' is configured but the fetch failed (see the "
                    "warning above) - confirm 'az login' and the 'Key Vault Secrets User' role."
                )
            else:
                print("       Fix: fill in CLOUDFLARE_API_TOKEN in .env.")
            ok = False
        if raw_env.get("CLOUDFLARE_API_TOKEN_WRITE"):
            print(
                "[warn] .env contains CLOUDFLARE_API_TOKEN_WRITE. The write token should "
                "normally only exist as a GitHub Actions secret - see docs/security.md."
            )

    if CREDS_FILE.is_file():
        # The template hardcodes "apitoken" (Cloudflare's required field
        # name); this lab's PowerDNS provider needs "apiKey" instead - see
        # CREDKEY above and dnscontrol's PowerDNS provider docs.
        required_key = "apitoken" if CREDKEY == "cloudflare" else "apiKey"
        contents = CREDS_FILE.read_text(encoding="utf-8")
        if f'"{required_key}"' in contents:
            print(f"[ok]   creds.json uses the correct '{required_key}' key.")
        else:
            print(
                f"[FAIL] creds.json does not contain the literal key \"{required_key}\" - "
                f"dnscontrol's {CREDKEY} provider requires this exact field name."
            )
            ok = False
    else:
        print("[FAIL] creds.json not found.")
        ok = False

    hooks_path = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if hooks_path in (".githooks", str(REPO_ROOT / ".githooks")):
        print(f"[ok]   git hooks path is set to '{hooks_path}'.")
    else:
        print("[warn] git core.hooksPath is not set to .githooks - the pre-push safety "
              "check will not run.")
        print("       Fix: git config core.hooksPath .githooks")

    print()
    if ok:
        print("Environment looks good.")
    else:
        print("One or more checks failed - see [FAIL] lines above.")
    return 0 if ok else 1


def cmd_setup(_args) -> int:
    print("Setting up local environment...")

    subprocess.run(["git", "config", "core.hooksPath", ".githooks"], cwd=REPO_ROOT, check=True)
    print("[ok] git core.hooksPath set to .githooks")

    if ENV_FILE.is_file():
        print("[ok] .env already exists (leaving it as-is)")
    else:
        if not ENV_EXAMPLE.is_file():
            eprint("error: .env.example not found - cannot scaffold .env")
            return 1
        shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
        print(f"[ok] created .env from {ENV_EXAMPLE.name} - edit it and fill in your "
              "read-only Cloudflare API token")

    print()
    print("Next: install dnscontrol if needed (python scripts/dnsctl.py install-dnscontrol),")
    print("then fill in .env and run: python scripts/dnsctl.py doctor")
    return 0


def cmd_install_dnscontrol(args) -> int:
    version = args.version
    asset = install.platform_asset_name(version)
    if not asset:
        eprint(
            f"error: no known dnscontrol release asset for {platform.system()} "
            f"{platform.machine()}. Download manually from "
            "https://github.com/DNSControl/dnscontrol/releases"
        )
        return 1

    dest_dir = Path(args.dest).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / exe_name("dnscontrol")

    base_url = f"https://github.com/DNSControl/dnscontrol/releases/download/v{version}"
    url = f"{base_url}/{asset}"
    print(f"Downloading {url} ...")

    tmp_archive = dest_dir / asset
    urllib.request.urlretrieve(url, tmp_archive)

    checksums_url = f"{base_url}/checksums.txt"
    print(f"Verifying checksum against {checksums_url} ...")
    with urllib.request.urlopen(checksums_url) as resp:
        checksums_text = resp.read().decode("utf-8")

    expected_hash = None
    for line in checksums_text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == asset:
            expected_hash = parts[0]
            break

    if expected_hash is None:
        tmp_archive.unlink()
        eprint(f"error: {asset} not found in {checksums_url} - refusing to install unverified binary")
        return 1

    actual_hash = hashlib.sha256(tmp_archive.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        tmp_archive.unlink()
        eprint(
            f"error: checksum mismatch for {asset}: expected {expected_hash}, got {actual_hash} - "
            "refusing to install unverified binary"
        )
        return 1
    print(f"[ok] checksum verified: {actual_hash}")

    print(f"Extracting dnscontrol binary to {dest_path} ...")
    if asset.endswith(".zip"):
        with zipfile.ZipFile(tmp_archive) as zf:
            with zf.open(exe_name("dnscontrol")) as src, open(dest_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
    else:
        with tarfile.open(tmp_archive, "r:gz") as tf:
            member = tf.getmember("dnscontrol")
            with tf.extractfile(member) as src, open(dest_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

    tmp_archive.unlink()

    if platform.system() != "Windows":
        current = os.stat(dest_path).st_mode
        os.chmod(dest_path, current | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print(f"[ok] installed dnscontrol {version} to {dest_path}")
    if str(dest_dir) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"Note: {dest_dir} is not on your PATH. Add it, or reference the binary "
              "directly, to use the 'dnscontrol' command outside this script.")
    return 0


def cmd_preview(_args) -> int:
    env = load_cloudflare_env()
    if "CLOUDFLARE_API_TOKEN" not in env and "CLOUDFLARE_API_TOKEN" not in os.environ:
        eprint("error: CLOUDFLARE_API_TOKEN not set in .env, the environment, or Key Vault.")
        eprint("       Run: python scripts/dnsctl.py setup")
        return 1
    return run_dnscontrol(["preview"], env)


def cmd_push(args) -> int:
    env = load_cloudflare_env()
    if "CLOUDFLARE_API_TOKEN" not in env and "CLOUDFLARE_API_TOKEN" not in os.environ:
        eprint("error: CLOUDFLARE_API_TOKEN not set in .env, the environment, or Key Vault.")
        return 1

    print(
        "WARNING: this will apply changes directly to the live Cloudflare zones "
        f"managed here ({', '.join(ZONES)}). The normal workflow is: open a PR, review "
        "the DNS Preview comment, and merge to main so the apply.yml GitHub Actions "
        "workflow applies it with the write-scoped token. Running this locally requires "
        "the write token to be set yourself for this one command (e.g. via "
        "CLOUDFLARE_API_TOKEN_WRITE in .env) - see docs/security.md before doing this."
    )
    if not args.yes:
        confirm = input('Type "APPLY" to continue, anything else to abort: ')
        if confirm != "APPLY":
            print("Aborted.")
            return 1

    write_token = env.get("CLOUDFLARE_API_TOKEN_WRITE") or os.environ.get(
        "CLOUDFLARE_API_TOKEN_WRITE"
    )
    overrides = dict(env)
    if write_token:
        overrides["CLOUDFLARE_API_TOKEN"] = write_token

    return run_dnscontrol(["push"], overrides)


def cmd_import(args) -> int:
    env = load_cloudflare_env()
    if "CLOUDFLARE_API_TOKEN" not in env and "CLOUDFLARE_API_TOKEN" not in os.environ:
        eprint("error: CLOUDFLARE_API_TOKEN not set in .env, the environment, or Key Vault.")
        return 1

    zone = args.zone
    if not zone:
        if len(ZONES) == 1:
            zone = ZONES[0]
        else:
            eprint(f"error: --zone is required (this project manages: {', '.join(ZONES)}).")
            return 1
    elif zone not in ZONES:
        eprint(f"error: '{zone}' is not a zone this project manages ({', '.join(ZONES)}).")
        return 1

    out_path = args.out
    print(f"Snapshotting live zone '{zone}' to {out_path} ...")
    rc = run_dnscontrol(
        ["get-zones", "--format=js", f"--out={out_path}", CREDKEY, zone], env
    )
    if rc == 0:
        print(f"[ok] wrote {out_path}")
        print("Now manually merge any new/changed records into dnsconfig.js, delete "
              f"{out_path}, and run `python scripts/dnsctl.py preview` to confirm "
              "0 corrections before committing. See docs/operations.md#re-baselining-the-zone.")
    return rc


def cmd_submit(args) -> int:
    if not require_gh():
        return 1

    status = git_output(["status", "--porcelain"])
    if not status:
        eprint("error: no local changes to commit.")
        return 1

    if not args.skip_preview:
        print("Running dnscontrol preview to sanity-check your change before committing...\n")
        rc = cmd_preview(args)
        print()
        if rc != 0:
            eprint("error: dnscontrol preview failed - fix the error above before submitting.")
            return 1
        if not args.yes:
            confirm = input("Does the diff above look correct? [y/N]: ").strip().lower()
            if confirm != "y":
                print("Aborted.")
                return 1

    current_branch = git_output(["rev-parse", "--abbrev-ref", "HEAD"])
    base_branch = args.base
    created_branch = False

    if current_branch == base_branch:
        branch = args.branch or f"dns/{slugify(args.message)}"
        print(f"Creating branch '{branch}' from '{base_branch}'...")
        if git(["checkout", "-b", branch]).returncode != 0:
            return 1
        created_branch = True
    else:
        branch = current_branch
        print(f"Already on branch '{branch}' - using it.")

    files = args.files or ["dnsconfig.js"]
    git(["add", *files])

    staged = git_output(["diff", "--cached", "--name-only"])
    if not staged:
        eprint(f"error: nothing staged from {files} - check --files matches your edited file(s).")
        if created_branch:
            git(["checkout", base_branch])
            git(["branch", "-D", branch])
        return 1

    print(f"Staged: {', '.join(staged.splitlines())}")

    if git(["commit", "-m", args.message]).returncode != 0:
        return 1

    print(f"Pushing '{branch}'...")
    push_result = subprocess.run(["git", "push", "-u", "origin", branch], cwd=REPO_ROOT)
    if push_result.returncode != 0:
        eprint("error: git push failed (see above).")
        return push_result.returncode

    print("Opening pull request...")
    pr_args = [
        "pr", "create",
        "--title", args.message,
        "--body", args.body or "",
        "--base", base_branch,
        "--head", branch,
    ]
    result = gh(pr_args)
    if result.returncode != 0:
        eprint(result.stderr.strip() or result.stdout.strip())
        return result.returncode
    print(result.stdout.strip())

    print(
        "\nNext: wait for the 'DNS Preview' check (python scripts/dnsctl.py status), "
        "review it (python scripts/dnsctl.py review <PR#>), then "
        "python scripts/dnsctl.py merge <PR#>."
    )
    return 0


def cmd_status(_args) -> int:
    if not require_gh():
        return 1

    result = gh([
        "pr", "list", "--state", "open",
        "--json", "number,title,headRefName,url,isDraft,statusCheckRollup",
    ])
    if result.returncode != 0:
        eprint(result.stderr.strip())
        return result.returncode

    prs = json.loads(result.stdout)
    if not prs:
        print("No open pull requests.")
        return 0

    for pr in prs:
        checks = pr.get("statusCheckRollup") or []
        preview_checks = [
            c for c in checks
            if "preview" in (c.get("name") or c.get("context") or "").lower()
        ]
        if preview_checks:
            states = sorted({
                (c.get("conclusion") or c.get("state") or "unknown") for c in preview_checks
            })
            check_state = ", ".join(states)
        else:
            check_state = "no DNS Preview check found yet"

        draft = " [draft]" if pr.get("isDraft") else ""
        print(f"#{pr['number']}{draft}: {pr['title']}")
        print(f"    branch: {pr['headRefName']}")
        print(f"    DNS Preview: {check_state}")
        print(f"    {pr['url']}")
    return 0


def cmd_review(args) -> int:
    if not require_gh():
        return 1

    number = str(args.pr)

    print(f"=== dnsconfig.js diff for PR #{number} ===")
    diff_result = gh(["pr", "diff", number])
    if diff_result.returncode != 0:
        eprint(diff_result.stderr.strip())
        return diff_result.returncode
    print(diff_result.stdout or "(no diff)")

    print(f"\n=== DNS Preview comment for PR #{number} ===")
    view_result = gh(["pr", "view", number, "--json", "comments"])
    if view_result.returncode != 0:
        eprint(view_result.stderr.strip())
        return view_result.returncode

    data = json.loads(view_result.stdout)
    comments = data.get("comments", [])
    preview_comments = [
        c for c in comments if "dnscontrol preview" in (c.get("body") or "").lower()
    ]
    if preview_comments:
        print(preview_comments[-1]["body"])
    else:
        print("No DNS Preview comment yet - the check may still be running.")
    return 0


def cmd_approve(args) -> int:
    if not require_gh():
        return 1

    number = str(args.pr)
    result = gh(["pr", "review", number, "--approve", "--body", args.body or ""])
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "own pull request" in stderr.lower():
            print(
                "GitHub does not allow approving your own pull request - this will "
                "always happen on a solo-maintained repo like this one.\n"
                "This repo has no required-review branch rule, so approval isn't "
                "needed to merge anyway - once the DNS Preview check has passed, run:\n"
                f"  python scripts/dnsctl.py merge {number}"
            )
            return 1
        eprint(stderr or result.stdout.strip())
        return result.returncode
    print(result.stdout.strip())
    return 0


def cmd_merge(args) -> int:
    if not require_gh():
        return 1

    number = str(args.pr)

    view_result = gh(["pr", "view", number, "--json", "state,statusCheckRollup,title"])
    if view_result.returncode != 0:
        eprint(view_result.stderr.strip())
        return view_result.returncode

    data = json.loads(view_result.stdout)
    if data.get("state") != "OPEN":
        eprint(f"error: PR #{number} is not open (state: {data.get('state')}).")
        return 1

    checks = data.get("statusCheckRollup") or []
    preview_checks = [
        c for c in checks
        if "preview" in (c.get("name") or c.get("context") or "").lower()
    ]
    if not preview_checks:
        print("warning: no 'DNS Preview' check found yet on this PR.")
    else:
        failed = [c for c in preview_checks if (c.get("conclusion") or c.get("state")) != "SUCCESS"]
        if failed:
            eprint(
                f"error: DNS Preview check has not succeeded for PR #{number}. "
                f"Run: python scripts/dnsctl.py review {number}"
            )
            if not args.force:
                return 1
            print("warning: --force set, merging anyway.")

    print(f'PR #{number}: "{data.get("title")}"')
    print(
        "Merging will trigger the 'DNS Apply' GitHub Actions workflow, which applies "
        f"this change to the live Cloudflare zone(s) managed here ({', '.join(ZONES)})."
    )
    if not args.yes:
        confirm = input('Type "MERGE" to continue, anything else to abort: ')
        if confirm != "MERGE":
            print("Aborted.")
            return 1

    # Routed through pu.gh() (not a direct ["gh", ...] subprocess call) so
    # this also works against a Forgejo remote - see procutil.detect_forge().
    result = gh(["pr", "merge", number, "--merge", "--delete-branch"], capture=False)
    if result.returncode != 0:
        return result.returncode

    if not args.wait:
        print(
            "Merged. Run 'python scripts/dnsctl.py validate "
            f"{number}' to confirm 'DNS Apply' succeeded and live state matches "
            "dnsconfig.js, or watch the Actions tab yourself."
        )
        return 0

    print("Merged. Waiting for 'DNS Apply' to run and confirming live state...\n")
    return validate_apply(number, args.timeout)


def cmd_begin(args) -> int:
    """Start a new DNS change: sync main, catch drift, create a branch."""
    if not require_gh():
        return 1

    status = git_output(["status", "--porcelain"])
    if status:
        eprint(
            "error: you have uncommitted changes - commit, stash, or discard them "
            "before starting a new DNS change:"
        )
        eprint(status)
        return 1

    base = args.base
    current_branch = git_output(["rev-parse", "--abbrev-ref", "HEAD"])
    if current_branch != base:
        print(f"Switching from '{current_branch}' to '{base}'...")
        if git(["checkout", base]).returncode != 0:
            return 1

    print(f"Fetching latest '{base}' from origin...")
    if git(["fetch", "origin", base]).returncode != 0:
        return 1
    if git(["pull", "--ff-only", "origin", base]).returncode != 0:
        eprint(
            f"error: '{base}' could not be fast-forwarded to origin/{base}. "
            "Your local branch has diverged - resolve manually (do not force) before continuing."
        )
        return 1

    env = load_cloudflare_env()
    have_token = "CLOUDFLARE_API_TOKEN" in env or "CLOUDFLARE_API_TOKEN" in os.environ
    if have_token:
        print(
            f"\nChecking '{base}' matches live Cloudflare state "
            "(dnscontrol preview --expect-no-changes)..."
        )
        rc = run_dnscontrol(["preview", "--expect-no-changes"], env)
        if rc != 0:
            eprint(
                "\nwarning: live Cloudflare state does not match dnsconfig.js on "
                f"'{base}'. This usually means an out-of-band dashboard edit, or an "
                "apply that hasn't landed yet. See "
                "docs/operations.md#responding-to-detected-drift before building an "
                "unrelated change on top of this."
            )
            if not args.yes and not prompt_yes_no("Continue anyway?", default_yes=False):
                print("Aborted.")
                return 1
    else:
        print("\n[skip] no CLOUDFLARE_API_TOKEN in .env - skipping the live-state drift check.")

    description = args.description or prompt(
        "Short description for this change (used for the branch name)"
    )
    branch = args.branch or f"dns/{slugify(description)}"
    print(f"\nCreating branch '{branch}' from '{base}'...")
    if git(["checkout", "-b", branch]).returncode != 0:
        return 1

    if have_token:
        print(
            "\nChecking _acme-challenge records against live Cloudflare "
            "(these rotate out-of-band, outside this repo's control)..."
        )
        sync_args = argparse.Namespace(zone=None, yes=args.yes)
        rc = cmd_record_sync_acme(sync_args, offer_submit=False)
        if rc == 1:
            print("Continuing without the ACME sync - run 'record sync-acme' later if needed.")

    print(
        f"\nReady on branch '{branch}'. Now:\n"
        "  1. Edit dnsconfig.js\n"
        "  2. python scripts/dnsctl.py lint\n"
        "  3. python scripts/dnsctl.py preview\n"
        '  4. python scripts/dnsctl.py submit "<description of change>"'
    )
    return 0


def cmd_history(args) -> int:
    """List commits on main that touched dnsconfig.js, newest first.

    Past PRs here were merged with a mix of squash (single-parent) and true
    merge (two-parent) commits, so this deliberately does not filter to
    `--merges` only - either kind is a valid `rollback` target."""
    log = git_output([
        "log", f"-n{args.limit}", "--date=short",
        "--pretty=format:%H%x1f%P%x1f%ad%x1f%s", "main", "--", "dnsconfig.js",
    ])
    if not log:
        print("No commits touching dnsconfig.js found in main's history.")
        return 0

    print(f"{'COMMIT':<10} {'DATE':<12} {'PR':<6} SUBJECT")
    for line in log.splitlines():
        sha, parents, date, subject = line.split("\x1f")
        m = re.search(r"#(\d+)", subject)
        pr = f"#{m.group(1)}" if m else "-"
        kind = " (merge)" if len(parents.split()) > 1 else ""
        print(f"{sha[:8]:<10} {date:<12} {pr:<6} {subject}{kind}")

    print("\nRoll one back: python scripts/dnsctl.py rollback <PR#|commit>")
    return 0


def resolve_revert_target(target: str) -> tuple[str, bool] | None:
    """Resolve a PR number or commit-ish to (sha, is_merge_commit)."""
    if re.fullmatch(r"\d+", target):
        if not require_gh():
            return None
        result = gh(["pr", "view", target, "--json", "mergeCommit,state"])
        if result.returncode != 0:
            eprint(result.stderr.strip() or result.stdout.strip())
            return None
        data = json.loads(result.stdout)
        if data.get("state") != "MERGED":
            eprint(f"error: PR #{target} is not merged (state: {data.get('state')}).")
            return None
        commit = data.get("mergeCommit") or {}
        sha = commit.get("oid")
        if not sha:
            eprint(f"error: PR #{target} has no merge commit on record.")
            return None
    else:
        verify = git(["rev-parse", "--verify", f"{target}^{{commit}}"], capture=True)
        if verify.returncode != 0:
            eprint(f"error: '{target}' is not a valid PR number or commit.")
            return None
        sha = verify.stdout.strip()

    parents = git_output(["log", "-1", "--pretty=format:%P", sha])
    return sha, len(parents.split()) > 1


def cmd_rollback(args) -> int:
    """Revert a previously-merged dnsconfig.js change via a new PR (never pushes to main)."""
    if not require_gh():
        return 1

    status = git_output(["status", "--porcelain"])
    if status:
        eprint(
            "error: you have uncommitted changes - commit, stash, or discard them "
            "before starting a rollback:"
        )
        eprint(status)
        return 1

    resolved = resolve_revert_target(args.target)
    if resolved is None:
        return 1
    target_sha, is_merge = resolved

    base = "main"
    current_branch = git_output(["rev-parse", "--abbrev-ref", "HEAD"])
    if current_branch != base:
        if git(["checkout", base]).returncode != 0:
            return 1
    if git(["fetch", "origin", base]).returncode != 0:
        return 1
    if git(["pull", "--ff-only", "origin", base]).returncode != 0:
        eprint(f"error: '{base}' could not be fast-forwarded to origin/{base}.")
        return 1

    subject = git_output(["log", "-1", "--pretty=format:%s", target_sha])
    branch = f"dns/revert-{target_sha[:8]}"
    print(f"Reverting {target_sha[:8]} (\"{subject}\") on new branch '{branch}'...")
    if git(["checkout", "-b", branch]).returncode != 0:
        return 1

    revert_args = ["revert", "--no-edit"]
    if is_merge:
        revert_args += ["-m", "1"]
    revert_args.append(target_sha)
    revert = git(revert_args)
    if revert.returncode != 0:
        eprint(
            "error: git revert hit a conflict - resolve it manually (see `git status`), "
            "then run:\n"
            "  python scripts/dnsctl.py preview\n"
            f'  python scripts/dnsctl.py submit "Revert: {subject}"'
        )
        return 1

    print("\nRunning dnscontrol preview to confirm the revert diff...")
    rc = cmd_preview(argparse.Namespace())
    if rc != 0:
        eprint("error: dnscontrol preview failed on the revert - investigate before submitting.")
        return 1

    if not args.yes:
        confirm = input(
            "Does the diff above look like the exact inverse of the original change? [y/N]: "
        ).strip().lower()
        if confirm != "y":
            print(f"Aborted - branch '{branch}' left in place for manual inspection.")
            return 1

    print(f"Pushing '{branch}'...")
    push_result = subprocess.run(["git", "push", "-u", "origin", branch], cwd=REPO_ROOT)
    if push_result.returncode != 0:
        eprint("error: git push failed (see above).")
        return push_result.returncode

    pr_body = (
        f'Reverts {target_sha[:8]} ("{subject}").\n\n'
        "Opened by `dnsctl.py rollback` - review the DNS Preview diff before merging, "
        "exactly like any other DNS change."
    )
    result = gh([
        "pr", "create", "--title", f"Revert: {subject}", "--body", pr_body,
        "--base", base, "--head", branch,
    ])
    if result.returncode != 0:
        eprint(result.stderr.strip() or result.stdout.strip())
        return result.returncode
    print(result.stdout.strip())
    print(
        "\nNext: python scripts/dnsctl.py status / review <PR#> / merge <PR#> - "
        "same as any other change."
    )
    return 0


DEFAULT_VALIDATE_TIMEOUT = 300


def sync_local_main() -> bool:
    """Switch to main and fast-forward it to origin/main. Refuses (rather than
    stashing or discarding) if the working tree isn't clean - same guard
    `begin`/`rollback` use. `validate` needs this because it compares live
    Cloudflare against whatever dnsconfig.js is on disk; running it from a
    stale or unrelated branch would otherwise report phantom drift that's
    actually just local/main being out of sync, not a real problem."""
    status = git_output(["status", "--porcelain"])
    if status:
        eprint(
            "error: you have uncommitted changes - commit, stash, or discard them "
            "before running validate (it needs to sync 'main' to compare against):"
        )
        eprint(status)
        return False

    current_branch = git_output(["rev-parse", "--abbrev-ref", "HEAD"])
    if current_branch != "main":
        print(f"Switching from '{current_branch}' to 'main' to compare against its dnsconfig.js...")
        if git(["checkout", "main"]).returncode != 0:
            return False

    if git(["fetch", "origin", "main"]).returncode != 0:
        return False
    if git(["pull", "--ff-only", "origin", "main"]).returncode != 0:
        eprint(
            "error: 'main' could not be fast-forwarded to origin/main - your local "
            "main has diverged. Resolve manually (do not force) before running validate."
        )
        return False
    return True


# Keep in sync with the `paths:` filter in .github/workflows/apply.yml - a
# commit touching none of these never triggers DNS Apply at all, so `validate`
# has nothing to wait for and shouldn't burn its timeout polling for a run
# that will never appear.
APPLY_TRIGGER_PATHS = {"dnsconfig.js", "creds.json", ".github/workflows/apply.yml"}


def commit_triggers_apply(sha: str) -> bool | None:
    """Whether `sha` touched a path that triggers DNS Apply, based on its diff
    against its first parent (this is the PR's actual diff for both a
    two-parent merge commit and a single-parent squash commit). Returns None
    if that can't be determined (e.g. `sha` has no parent) - callers should
    treat that as "assume yes, wait as normal" rather than skip the wait."""
    result = git(["diff", "--name-only", f"{sha}^1", sha], capture=True)
    if result.returncode != 0:
        return None
    changed = set(result.stdout.split())
    return bool(changed & APPLY_TRIGGER_PATHS)


def resolve_validate_target_sha(target: str | None) -> str | None:
    """Resolve what `validate` should check: an explicit PR number/commit
    (via the same PR-or-commit resolution `rollback` uses), or - if omitted -
    the (now-synced) local tip of main."""
    if target is None:
        sha = git_output(["rev-parse", "main"])
        return sha or None

    resolved = resolve_revert_target(target)
    if resolved is None:
        return None
    return resolved[0]


def validate_apply(target: str | None, timeout: int) -> int:
    """Confirm a merged change actually landed: find the 'DNS Apply' run for
    the target commit, wait for it to finish, then re-run `dnscontrol preview
    --expect-no-changes` to confirm live Cloudflare now matches dnsconfig.js.
    This is the automated version of what merging a PR otherwise leaves as a
    manual "go check the Actions tab" step.

    Always compares against the *current* main, not whatever dnsconfig.js
    looked like at the target commit - what actually matters after any apply
    is "does live state match main's dnsconfig.js right now," regardless of
    which past commit's DNS Apply run triggered this check."""
    if not require_gh():
        return 1
    if not sync_local_main():
        return 1

    sha = resolve_validate_target_sha(target)
    if sha is None:
        return 1
    short = sha[:8]
    print(f"Validating commit {short}...")

    if commit_triggers_apply(sha) is False:
        print(
            f"Commit {short} doesn't touch dnsconfig.js/creds.json/apply.yml, so 'DNS "
            "Apply' never runs for it (see the `paths:` filter in "
            ".github/workflows/apply.yml) - nothing to wait for.\n"
            "Confirming live Cloudflare still matches the current dnsconfig.js anyway..."
        )
    else:
        print("Looking for the 'DNS Apply' workflow run for this commit...")
        run_id = None
        run_url = None
        deadline = time.time() + timeout
        while True:
            result = gh([
                "run", "list", "--workflow", "DNS Apply",
                "--json", "databaseId,headSha,status,conclusion,url", "--limit", "20",
            ])
            if result.returncode != 0:
                eprint(result.stderr.strip())
                return 1
            runs = json.loads(result.stdout)
            match = next((r for r in runs if r.get("headSha") == sha), None)
            if match:
                run_id, run_url = match["databaseId"], match["url"]
                break
            if time.time() >= deadline:
                eprint(
                    f"error: no 'DNS Apply' run found for {short} within {timeout}s - it "
                    "may not have started yet, or this commit never reached main via a "
                    "merge. Check the Actions tab, or re-run with a longer --timeout."
                )
                return 1
            time.sleep(5)

        print(f"Found run {run_id} - waiting for it to complete...\n")
        # Routed through pu.gh() so this also works against a Forgejo
        # remote - see procutil.detect_forge().
        watch = gh(["run", "watch", str(run_id), "--exit-status"], capture=False)
        if watch.returncode != 0:
            eprint(f"\nerror: 'DNS Apply' run {run_id} did not succeed - see {run_url}")
            return 1

        print("\n'DNS Apply' succeeded. Confirming live Cloudflare state matches dnsconfig.js...")

    env = load_cloudflare_env()
    rc = run_dnscontrol(["preview", "--expect-no-changes"], env)
    if rc != 0:
        eprint(
            "\nerror: 'DNS Apply' succeeded but live Cloudflare state still doesn't match "
            "dnsconfig.js (see the corrections above). This usually means a second, "
            "unrelated drift source (e.g. an out-of-band ACME renewal) rather than a "
            "problem with the apply itself - see "
            "docs/operations.md#responding-to-detected-drift."
        )
        return 1

    print(f"\nValidated: commit {short} is live on Cloudflare and matches dnsconfig.js exactly.")
    return 0


def cmd_validate(args) -> int:
    return validate_apply(args.target, args.timeout)


def cmd_record_add(args) -> int:
    try:
        name, zone = parse_record_target(args.target, zone=args.zone)
    except ValueError as e:
        eprint(f"error: {e}")
        return 1

    interactive = not args.yes

    record_type = (args.type or "").upper()
    if not record_type:
        if not interactive:
            eprint("error: --yes requires --type to be provided (no prompts allowed).")
            return 1
        record_type = prompt("Record type (A, CNAME, MX, TXT)", default="CNAME").upper()
    if record_type not in ("A", "CNAME", "MX", "TXT"):
        eprint(
            f"error: unsupported record type '{record_type}'. This wizard supports "
            "A, CNAME, MX, TXT - edit dnsconfig.js directly for anything else "
            "(see docs/record-types.md)."
        )
        return 1

    value = args.value
    priority = args.priority
    proxy = args.proxy
    ttl = args.ttl

    if value is None:
        if not interactive:
            eprint("error: --yes requires --value to be provided (no prompts allowed).")
            return 1
        label = {
            "A": "IPv4 address",
            "CNAME": "target hostname",
            "MX": "mail server hostname",
            "TXT": "text value",
        }[record_type]
        value = prompt(f"{label} for {fqdn_for(name, zone)}")

    if record_type in ("CNAME", "MX") and value and not value.endswith("."):
        if interactive:
            if prompt_yes_no(f"'{value}' has no trailing dot - add one?", default_yes=True):
                value += "."
        else:
            value += "."
            print(f"note: appended trailing dot -> {value}")

    if record_type == "MX" and priority is None:
        if not interactive:
            eprint("error: --yes with an MX record requires --priority.")
            return 1
        priority = int(prompt("Priority (lower number = preferred)", default="10"))

    if record_type in ("A", "CNAME") and proxy is None:
        if interactive:
            proxy = prompt_yes_no("Proxy through Cloudflare (orange cloud)?", default_yes=True)
        else:
            proxy = True
            print("note: defaulting to proxy ON (pass --no-proxy to disable)")

    if record_type == "TXT" and ttl is None and interactive:
        ttl_input = prompt("TTL override in seconds (blank = zone default)", default="")
        ttl = int(ttl_input) if ttl_input else None

    try:
        line = build_record_line(
            record_type, name, value, priority=priority, proxy=proxy, ttl=ttl
        )
    except ValueError as e:
        eprint(f"error: {e}")
        return 1

    start, end = find_zone_block(zone)
    zone_lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()[start + 1 : end]
    if line.strip() in {existing_line.strip() for existing_line in zone_lines}:
        eprint(
            f"error: this exact record already exists in the {zone} block of "
            f"{DNSCONFIG_FILE.name} - nothing to add."
        )
        return 1

    same_name_other_type = [
        (i, l) for i, l in find_record_lines(name, zone)
        if RECORD_LINE_PATTERN.match(l).group(1) != record_type
    ]
    if same_name_other_type:
        existing_types = sorted({RECORD_LINE_PATTERN.match(l).group(1) for _, l in same_name_other_type})
        if record_type == "CNAME" or "CNAME" in existing_types:
            print(
                f"\nWARNING: {fqdn_for(name, zone)} already has {'/'.join(existing_types)} record(s), "
                "and CNAME can't coexist with any other record type on the same name "
                "(DNS-wide rule, not specific to this project). Cloudflare will likely reject this."
            )
            for _, existing_line in same_name_other_type:
                print(f"  {existing_line.strip()}")

    existing_same_type = find_record_lines(name, zone, record_type)
    if existing_same_type:
        print(f"\nNote: {len(existing_same_type)} existing {record_type} record(s) already use this name:")
        for _, existing_line in existing_same_type:
            print(f"  {existing_line.strip()}")

    print(f"\nFull name: {fqdn_for(name, zone)}")
    print(f"About to add this line to the {zone} block of {DNSCONFIG_FILE.name}:")
    print(f"  {line}")
    if interactive and not prompt_yes_no("Add it?", default_yes=True):
        print("Aborted.")
        return 1

    insert_record_line(line, zone)
    print(f"[ok] added to {DNSCONFIG_FILE.name}")
    offer_preview_and_submit(f"Add {record_type} for {fqdn_for(name, zone)}", interactive=interactive)
    return 0


def cmd_record_edit(args) -> int:
    try:
        name, zone = parse_record_target(args.target, zone=args.zone)
    except ValueError as e:
        eprint(f"error: {e}")
        return 1

    interactive = not args.yes

    type_filter = args.type.upper() if args.type else None
    matches = find_record_lines(name, zone, type_filter)
    if not matches:
        eprint(
            f"error: no records found for '{fqdn_for(name, zone)}'"
            + (f" of type {type_filter}" if type_filter else "")
            + " in dnsconfig.js."
        )
        return 1

    if args.index is not None:
        try:
            selected = matches[args.index]
        except IndexError:
            eprint(f"error: --index {args.index} out of range (found {len(matches)} match(es)).")
            return 1
    elif len(matches) == 1:
        selected = matches[0]
    elif not interactive:
        eprint(
            f"error: {len(matches)} matches for '{fqdn_for(name, zone)}' and --yes was given - "
            "pass --index (see `record list`) or --type to disambiguate."
        )
        for i, (_, line) in enumerate(matches):
            eprint(f"  [{i}] {line.strip()}")
        return 1
    else:
        print(f"Found {len(matches)} matching records:")
        for i, (_, line) in enumerate(matches):
            print(f"  [{i}] {line.strip()}")
        choice = prompt("Which one to edit? (index)")
        try:
            selected = matches[int(choice)]
        except (ValueError, IndexError):
            eprint("error: invalid selection.")
            return 1

    idx, old_line = selected
    parsed = parse_record_line_full(old_line)
    if not parsed:
        eprint("error: could not parse the selected line - edit dnsconfig.js directly.")
        return 1

    record_type = parsed["type"]
    if record_type not in ("A", "CNAME", "MX", "TXT"):
        eprint(
            f"error: editing {record_type} records isn't supported by this wizard - "
            "edit dnsconfig.js directly (see docs/record-types.md)."
        )
        return 1

    value = args.value
    if value is None:
        if not interactive:
            eprint("error: --yes requires --value to be provided (no prompts allowed).")
            return 1
        label = {
            "A": "IPv4 address",
            "CNAME": "target hostname",
            "MX": "mail server hostname",
            "TXT": "text value",
        }[record_type]
        value = prompt(f"{label} for {fqdn_for(name, zone)}", default=parsed["value"])

    if record_type in ("CNAME", "MX") and value and not value.endswith("."):
        if interactive:
            if prompt_yes_no(f"'{value}' has no trailing dot - add one?", default_yes=True):
                value += "."
        else:
            value += "."
            print(f"note: appended trailing dot -> {value}")

    priority = args.priority
    if record_type == "MX" and priority is None:
        current_priority = parsed["priority"] or "10"
        if interactive:
            priority = int(prompt("Priority (lower number = preferred)", default=current_priority))
        else:
            priority = int(current_priority)

    proxy = args.proxy
    if record_type in ("A", "CNAME") and proxy is None:
        current_proxy = parsed["proxied"] == "yes"
        if interactive:
            proxy = prompt_yes_no("Proxy through Cloudflare (orange cloud)?", default_yes=current_proxy)
        else:
            proxy = current_proxy

    ttl = args.ttl
    if ttl is None and parsed["ttl"]:
        ttl = int(parsed["ttl"])
    if record_type == "TXT" and args.ttl is None and interactive:
        ttl_input = prompt("TTL override in seconds (blank = zone default)", default=str(ttl) if ttl else "")
        ttl = int(ttl_input) if ttl_input else None

    had_explicit_proxy_off = parsed["proxied"] == "no"
    try:
        new_line = build_record_line(
            record_type, name, value, priority=priority, proxy=proxy, ttl=ttl,
            proxy_off=had_explicit_proxy_off and not proxy,
            extras=parsed.get("extras"), comment=parsed.get("comment", ""),
        )
    except ValueError as e:
        eprint(f"error: {e}")
        return 1

    if new_line.strip() == old_line.strip():
        print("No change - the new line is identical to the existing one.")
        return 0

    print(f"\nAbout to change this line in the {zone} block of {DNSCONFIG_FILE.name}:")
    print(f"  - {old_line.strip()}")
    print(f"  + {new_line.strip()}")
    if interactive and not prompt_yes_no("Apply this edit?", default_yes=True):
        print("Aborted.")
        return 1

    replace_line_at(idx, new_line)
    print(f"[ok] updated {DNSCONFIG_FILE.name}")
    offer_preview_and_submit(f"Edit {record_type} for {fqdn_for(name, zone)}", interactive=interactive)
    return 0


def cmd_record_remove(args) -> int:
    try:
        name, zone = parse_record_target(args.target, zone=args.zone)
    except ValueError as e:
        eprint(f"error: {e}")
        return 1

    interactive = not args.yes

    record_type = args.type.upper() if args.type else None
    matches = find_record_lines(name, zone, record_type)
    if not matches:
        eprint(
            f"error: no records found for '{fqdn_for(name, zone)}'"
            + (f" of type {record_type}" if record_type else "")
            + " in dnsconfig.js."
        )
        return 1

    if args.index is not None:
        try:
            selected = matches[args.index]
        except IndexError:
            eprint(f"error: --index {args.index} out of range (found {len(matches)} match(es)).")
            return 1
    elif len(matches) == 1:
        selected = matches[0]
    elif not interactive:
        eprint(
            f"error: {len(matches)} matches for '{fqdn_for(name, zone)}' and --yes was given - "
            "pass --index (see `record list`) or --type to disambiguate."
        )
        for i, (_, line) in enumerate(matches):
            eprint(f"  [{i}] {line.strip()}")
        return 1
    else:
        print(f"Found {len(matches)} matching records:")
        for i, (_, line) in enumerate(matches):
            print(f"  [{i}] {line.strip()}")
        choice = prompt("Which one to remove? (index)")
        try:
            selected = matches[int(choice)]
        except (ValueError, IndexError):
            eprint("error: invalid selection.")
            return 1

    idx, line = selected
    print(f"\nAbout to remove this line from the {zone} block of {DNSCONFIG_FILE.name}:")
    print(f"  {line.strip()}")
    if interactive and not prompt_yes_no("Remove it?", default_yes=False):
        print("Aborted.")
        return 1

    remove_line_at(idx)
    print(f"[ok] removed from {DNSCONFIG_FILE.name}")
    offer_preview_and_submit(f"Remove record for {fqdn_for(name, zone)}", interactive=interactive)
    return 0


def cmd_record_list(args) -> int:
    name_filter = None
    zone_filter = None
    if args.name:
        try:
            name_filter, zone_filter = parse_record_target(args.name, zone=args.zone)
        except ValueError as e:
            eprint(f"error: {e}")
            return 1
    elif args.zone:
        if args.zone not in ZONES:
            eprint(f"error: '{args.zone}' is not a zone this project manages ({', '.join(ZONES)}).")
            return 1
        zone_filter = args.zone

    lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()
    zones_to_show = [zone_filter] if zone_filter else ZONES

    found = False
    for zone in zones_to_show:
        try:
            start, end = find_zone_block(zone)
        except RuntimeError as e:
            eprint(f"error: {e}")
            continue
        zone_found = False
        for i in range(start + 1, end):
            m = RECORD_LINE_PATTERN.match(lines[i])
            if not m:
                continue
            if name_filter and m.group(2) != name_filter:
                continue
            if not zone_found:
                print(f"# {zone}")
                zone_found = True
            print(lines[i].strip())
            found = True

    if not found:
        print("No matching records." if name_filter else "No records found.")
    return 0


def cmd_record_update_ip(args) -> int:
    if args.zone and args.zone not in ZONES:
        eprint(f"error: '{args.zone}' is not a zone this project manages ({', '.join(ZONES)}).")
        return 1
    zones_to_check = [args.zone] if args.zone else ZONES

    matches = []  # (zone, idx, line, parsed)
    for zone in zones_to_check:
        start, end = find_zone_block(zone)
        lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()
        for i in range(start + 1, end):
            parsed = parse_record_line_full(lines[i])
            if not parsed:
                continue
            if parsed["type"] == "A" and parsed["value"] == args.old_ip:
                matches.append((zone, i, lines[i], parsed))

    if not matches:
        eprint(f"error: no A records found with value {args.old_ip}.")
        return 1

    interactive = not args.yes

    print(f"Found {len(matches)} A record(s) pointing at {args.old_ip}:")
    for zone, _, line, parsed in matches:
        print(f"  {fqdn_for(parsed['name'], zone)}  ({zone})")
    print(f"\nWould change all of them to {args.new_ip}.")
    if interactive and not prompt_yes_no("Apply this change?", default_yes=True):
        print("Aborted.")
        return 1

    for zone, idx, _line, parsed in matches:
        ttl = int(parsed["ttl"]) if parsed["ttl"] else None
        proxy = parsed["proxied"] == "yes"
        new_line = build_record_line(
            "A", parsed["name"], args.new_ip,
            proxy=proxy, ttl=ttl,
            proxy_off=(parsed["proxied"] == "no" and not proxy),
            extras=parsed.get("extras"), comment=parsed.get("comment", ""),
        )
        replace_line_at(idx, new_line)

    print(f"[ok] updated {len(matches)} record(s) in {DNSCONFIG_FILE.name}")
    offer_preview_and_submit(
        f"Update A records from {args.old_ip} to {args.new_ip}", interactive=interactive
    )
    return 0


def cmd_record_prune_acme(args) -> int:
    if args.zone and args.zone not in ZONES:
        eprint(f"error: '{args.zone}' is not a zone this project manages ({', '.join(ZONES)}).")
        return 1
    zones_to_check = [args.zone] if args.zone else ZONES

    entries = []  # (zone, idx, line, parsed)
    for zone in zones_to_check:
        for i, line, parsed in local_acme_entries(zone):
            entries.append((zone, i, line, parsed))

    if not entries:
        print("No _acme-challenge TXT records found.")
        return 0

    live_by_zone: dict[str, set[tuple[str, str]]] = {}
    live_active = False
    if args.offline:
        pass
    else:
        env = load_cloudflare_env()
        if "CLOUDFLARE_API_TOKEN" not in env and "CLOUDFLARE_API_TOKEN" not in os.environ:
            eprint(
                "note: no CLOUDFLARE_API_TOKEN available (.env, environment, or Key Vault) - "
                "falling back to the token-count heuristic only. Set up .env (see "
                "docs/getting-started.md) or pass --offline to silence this."
            )
        else:
            live_active = True
            for zone in zones_to_check:
                print(f"Fetching live state for {zone} ...", file=sys.stderr)
                live = fetch_live_acme_entries(zone, env)
                if live is None:
                    eprint(
                        f"note: failed to fetch live state for {zone} (dnscontrol get-zones "
                        "failed) - falling back to the token-count heuristic only."
                    )
                    live_active = False
                    live_by_zone = {}
                    break
                live_by_zone[zone] = live

    groups = collections.defaultdict(list)
    for e in entries:
        groups[(e[0], e[3]["name"])].append(e)

    flat = []
    print("_acme-challenge TXT records (ACME/Let's Encrypt validation tokens):")
    for (zone, name), items in groups.items():
        flag = (
            f" - {len(items)} tokens, likely includes stale ones from past renewals"
            if len(items) > 1 else ""
        )
        print(f"\n{fqdn_for(name, zone)}{flag}")
        for e in items:
            marker = ""
            if live_active:
                key = (e[3]["name"], e[3]["value"])
                marker = (
                    "  [confirmed gone from Cloudflare - safe to remove]"
                    if key not in live_by_zone.get(zone, set())
                    else "  [still live on Cloudflare]"
                )
            print(f"  [{len(flat)}] {e[2].strip()}{marker}")
            flat.append(e)

    if live_active:
        for zone in zones_to_check:
            local_keys = {(e[3]["name"], e[3]["value"]) for e in entries if e[0] == zone}
            extra_live = live_by_zone.get(zone, set()) - local_keys
            if extra_live:
                print(
                    f"\n[!] Live on Cloudflare ({zone}) but NOT in {DNSCONFIG_FILE.name} - "
                    "the next `apply` (from any merged PR, not just an ACME-related one) would "
                    "DELETE these from Cloudflare, since dnscontrol makes Cloudflare match "
                    "dnsconfig.js:"
                )
                for name, value in sorted(extra_live):
                    print(f"    {fqdn_for(name, zone)}  {value!r}")
                print(
                    "    If one of these is mid-renewal, do nothing and re-run this check "
                    "shortly. Otherwise fold it into dnsconfig.js (see "
                    "docs/operations.md#re-baselining-a-zone) before merging anything else."
                )

    if not args.remove:
        print(
            "\nThese aren't deleted automatically - only your cert issuer/reverse proxy "
            "knows which tokens are still live. Re-run with --remove <index> [<index> ...] "
            "once you've confirmed which ones are stale"
            + (" (see the [confirmed gone from Cloudflare] markers above)." if live_active else ".")
        )
        return 0

    interactive = not args.yes
    indices = sorted(set(i for group in args.remove for i in group))
    selected = []
    for i in indices:
        if i < 0 or i >= len(flat):
            eprint(f"error: --remove index {i} out of range (0-{len(flat) - 1}).")
            return 1
        selected.append(flat[i])

    print(f"\nAbout to remove {len(selected)} record(s):")
    for e in selected:
        print(f"  {e[2].strip()}")
    if interactive and not prompt_yes_no("Remove these?", default_yes=False):
        print("Aborted.")
        return 1

    for _zone, idx, _line, _parsed in sorted(selected, key=lambda e: e[1], reverse=True):
        remove_line_at(idx)

    print(f"[ok] removed {len(selected)} record(s) from {DNSCONFIG_FILE.name}")
    offer_preview_and_submit("Prune stale _acme-challenge TXT records", interactive=interactive)
    return 0


def cmd_record_sync_acme(args, offer_submit: bool = True) -> int:
    """Fold live Cloudflare's _acme-challenge TXT records into dnsconfig.js -
    adding what's missing locally, removing what's gone upstream - since an
    out-of-band ACME client (e.g. Caddy) is the real source of truth for these
    specific records, unlike everything else dnsconfig.js manages."""
    env = load_cloudflare_env()
    if "CLOUDFLARE_API_TOKEN" not in env and "CLOUDFLARE_API_TOKEN" not in os.environ:
        eprint("error: CLOUDFLARE_API_TOKEN not set in .env, the environment, or Key Vault.")
        return 1

    if args.zone and args.zone not in ZONES:
        eprint(f"error: '{args.zone}' is not a zone this project manages ({', '.join(ZONES)}).")
        return 1
    zones_to_check = [args.zone] if args.zone else ZONES

    to_remove = []  # (zone, idx, line)
    to_add = []     # (zone, name, value, ttl)
    for zone in zones_to_check:
        print(f"Fetching live state for {zone} ...", file=sys.stderr)
        live = fetch_live_acme_snapshot(zone, env)
        if live is None:
            eprint(f"error: failed to fetch live state for {zone} (dnscontrol get-zones failed).")
            return 1

        local = local_acme_entries(zone)
        local_keys = {(p["name"], p["value"]) for _, _, p in local}
        live_keys = {(p["name"], p["value"]) for p in live}

        for i, line, parsed in local:
            if (parsed["name"], parsed["value"]) not in live_keys:
                to_remove.append((zone, i, line))
        for p in live:
            if (p["name"], p["value"]) not in local_keys:
                to_add.append((zone, p["name"], p["value"], p.get("ttl") or None))

    if not to_remove and not to_add:
        print("dnsconfig.js already matches live Cloudflare state for all _acme-challenge records.")
        return 0

    if to_remove:
        print(f"\nIn dnsconfig.js but not live on Cloudflare - would remove {len(to_remove)}:")
        for zone, _i, line in to_remove:
            print(f"  ({zone})  {line.strip()}")
    if to_add:
        print(f"\nLive on Cloudflare but not in dnsconfig.js - would add {len(to_add)}:")
        for zone, name, value, ttl in to_add:
            print(f"  ({zone})  {fqdn_for(name, zone)}  {value!r}")

    interactive = not args.yes
    if interactive and not prompt_yes_no(
        "\nApply this to dnsconfig.js so it matches live Cloudflare state?", default_yes=False
    ):
        print("Aborted.")
        return 1

    for zone in zones_to_check:
        # Re-resolve indices from the current file state right before editing
        # each zone - an earlier zone's edits in this same loop shift line
        # numbers for every zone below it, so the indices captured during the
        # diff pass above can no longer be trusted here.
        stale_lines = {line for z, _i, line in to_remove if z == zone}
        if stale_lines:
            current_indices = [
                i for i, line, _parsed in local_acme_entries(zone) if line in stale_lines
            ]
            for i in sorted(current_indices, reverse=True):
                remove_line_at(i)
        for z, name, value, ttl in to_add:
            if z != zone:
                continue
            new_line = build_record_line(
                "TXT", name, value, ttl=int(ttl) if ttl else None
            )
            insert_record_line(new_line, zone)

    print(
        f"[ok] dnsconfig.js updated: removed {len(to_remove)}, added {len(to_add)} "
        "_acme-challenge record(s)"
    )
    offer_preview_and_submit(
        "Sync _acme-challenge TXT records with live Cloudflare state", interactive=interactive
    )
    return 0


def cmd_lint(args) -> int:
    if args.zone and args.zone not in ZONES:
        eprint(f"error: '{args.zone}' is not a zone this project manages ({', '.join(ZONES)}).")
        return 1
    zones_to_check = [args.zone] if args.zone else ZONES

    issues = []  # (level, message)
    seen_exact = set()
    name_types = collections.defaultdict(lambda: collections.defaultdict(list))

    for zone in zones_to_check:
        try:
            start, end = find_zone_block(zone)
        except RuntimeError as e:
            issues.append(("error", str(e)))
            continue
        lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()
        for i in range(start + 1, end):
            parsed, skip_reason = classify_zone_line(lines[i])
            if skip_reason:
                issues.append((
                    "warn",
                    f"{zone}: line {i + 1} {skip_reason} - not checked: {lines[i].strip()}",
                ))
                continue
            if parsed is None:
                continue
            raw = lines[i].strip()
            key = (zone, raw)
            if key in seen_exact:
                issues.append(("error", f"{zone}: duplicate line (appears more than once): {raw}"))
            seen_exact.add(key)
            name_types[zone][parsed["name"]].append((parsed["type"], i, raw))
            if parsed["type"] in ("CNAME", "MX") and parsed["value"] and not parsed["value"].endswith("."):
                issues.append(("error", f"{zone}: {parsed['type']} target missing trailing dot: {raw}"))

    for zone, names in name_types.items():
        for name, records in names.items():
            types = {t for t, _, _ in records}
            cname_entries = [r for r in records if r[0] == "CNAME"]
            if cname_entries and len(types) > 1:
                issues.append((
                    "error",
                    f"{zone}: {fqdn_for(name, zone)} has CNAME alongside other record type(s) "
                    f"({', '.join(sorted(types))}) - CNAME can't coexist with anything else on the same name.",
                ))
            if len(cname_entries) > 1:
                issues.append((
                    "error",
                    f"{zone}: {fqdn_for(name, zone)} has more than one CNAME record - "
                    "only one CNAME is allowed per name.",
                ))

    if not issues:
        print("[ok] lint passed - no issues found.")
        return 0

    errors = [m for level, m in issues if level == "error"]
    warnings = [m for level, m in issues if level == "warn"]
    for m in errors:
        print(f"[error] {m}")
    for m in warnings:
        print(f"[warn] {m}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s).")
    return 1 if errors else 0


def collect_show_rows(zone_filter: str | None) -> tuple[list[list[str]], list[tuple[str, int, str]]]:
    """Return (rows, skipped) - `skipped` is (zone, 1-based line number, raw
    line) for anything classify_zone_line() couldn't parse as a record, so
    `show`'s inventory never silently disagrees with the file (see TOOL-1)."""
    zones_to_show = [zone_filter] if zone_filter else ZONES
    rows = []
    skipped = []
    for zone in zones_to_show:
        try:
            start, end = find_zone_block(zone)
        except RuntimeError as e:
            eprint(f"error: {e}")
            continue
        lines = DNSCONFIG_FILE.read_text(encoding="utf-8").splitlines()
        for i in range(start + 1, end):
            parsed, skip_reason = classify_zone_line(lines[i])
            if skip_reason:
                skipped.append((zone, i + 1, lines[i].strip()))
                continue
            if parsed is None:
                continue
            rows.append([
                zone,
                parsed["type"],
                parsed["name"],
                fqdn_for(parsed["name"], zone),
                parsed["value"],
                parsed["priority"],
                parsed["ttl"],
                parsed["proxied"],
            ])
    return rows, skipped


def cmd_show(args) -> int:
    zone_filter = None
    if args.zone:
        if args.zone not in ZONES:
            eprint(f"error: '{args.zone}' is not a zone this project manages ({', '.join(ZONES)}).")
            return 1
        zone_filter = args.zone

    rows, skipped = collect_show_rows(zone_filter)
    if skipped:
        eprint(f"note: {len(skipped)} line(s) could not be parsed and are not included below:")
        for zone, lineno, raw in skipped:
            eprint(f"  {zone} line {lineno}: {raw}")
    if args.grep:
        needle = args.grep.lower()
        rows = [
            row for row in rows
            if any(needle in cell.lower() for cell in row)
        ]
    if not rows:
        print("No records found." if not args.grep else f"No records match '{args.grep}'.")
        return 0

    if args.output == "csv":
        text = render.render_csv(render.SHOW_HEADERS, rows)
    elif args.output == "md":
        text = render.render_markdown(render.SHOW_HEADERS, rows)
    else:
        text = render.render_table(render.SHOW_HEADERS, rows)

    if args.file:
        Path(args.file).write_text(text, encoding="utf-8", newline="")
        print(f"Wrote {args.output} output to {args.file}")
    else:
        print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cross-platform helper for this dnscontrol/Cloudflare project."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="Check local environment setup.")
    p_doctor.set_defaults(func=cmd_doctor)

    p_setup = sub.add_parser("setup", help="One-time local setup (git hook + .env).")
    p_setup.set_defaults(func=cmd_setup)

    p_install = sub.add_parser(
        "install-dnscontrol", help="Download the pinned dnscontrol release binary."
    )
    p_install.add_argument(
        "--version", default=DNSCONTROL_VERSION, help="dnscontrol version to install."
    )
    p_install.add_argument(
        "--dest",
        default=str(Path.home() / ".local" / "bin"),
        help="Directory to install the binary into (default: ~/.local/bin).",
    )
    p_install.set_defaults(func=cmd_install_dnscontrol)

    p_preview = sub.add_parser("preview", help="Run `dnscontrol preview`.")
    p_preview.set_defaults(func=cmd_preview)

    p_push = sub.add_parser("push", help="Run `dnscontrol push` (asks for confirmation).")
    p_push.add_argument(
        "--yes", action="store_true", help="Skip the interactive confirmation prompt."
    )
    p_push.set_defaults(func=cmd_push)

    p_import = sub.add_parser(
        "import", help="Snapshot a live zone to a JS file for manual merging."
    )
    p_import.add_argument(
        "--zone", choices=ZONES, default=None,
        help=f"Which zone to snapshot (required if more than one: {', '.join(ZONES)}).",
    )
    p_import.add_argument(
        "--out", default="zone_import.js", help="Output file (default: zone_import.js)."
    )
    p_import.set_defaults(func=cmd_import)

    p_begin = sub.add_parser(
        "begin",
        help="Start a DNS change: sync main, check for drift, create a branch.",
    )
    p_begin.add_argument(
        "description", nargs="?",
        help="Short description used for the branch name (prompted if omitted).",
    )
    p_begin.add_argument("--branch", default=None, help="Branch name (default: auto from description).")
    p_begin.add_argument("--base", default="main", help="Base branch to sync from (default: main).")
    p_begin.add_argument(
        "--yes", action="store_true",
        help="Don't prompt on the drift/ACME-sync checks (auto-continue/auto-apply).",
    )
    p_begin.set_defaults(func=cmd_begin)

    p_submit = sub.add_parser(
        "submit", help="Commit your dnsconfig.js change, push a branch, and open a PR."
    )
    p_submit.add_argument("message", help="Commit message / PR title.")
    p_submit.add_argument(
        "--files", nargs="+", default=None,
        help="Files to stage (default: dnsconfig.js).",
    )
    p_submit.add_argument("--branch", default=None, help="Branch name (default: auto from message).")
    p_submit.add_argument("--base", default="main", help="Base branch to PR against (default: main).")
    p_submit.add_argument("--body", default=None, help="PR body text.")
    p_submit.add_argument(
        "--skip-preview", action="store_true",
        help="Skip running `dnscontrol preview` before committing.",
    )
    p_submit.add_argument(
        "--yes", action="store_true", help="Skip the interactive confirmation prompt."
    )
    p_submit.set_defaults(func=cmd_submit)

    p_status = sub.add_parser(
        "status", help="List open pull requests and their DNS Preview check status."
    )
    p_status.set_defaults(func=cmd_status)

    p_review = sub.add_parser(
        "review", help="Show a PR's dnsconfig.js diff and its DNS Preview comment."
    )
    p_review.add_argument("pr", type=int, help="Pull request number.")
    p_review.set_defaults(func=cmd_review)

    p_approve = sub.add_parser(
        "approve", help="Approve a PR (fails on your own PR - GitHub restriction)."
    )
    p_approve.add_argument("pr", type=int, help="Pull request number.")
    p_approve.add_argument("--body", default=None, help="Review comment body.")
    p_approve.set_defaults(func=cmd_approve)

    p_merge = sub.add_parser(
        "merge", help="Merge a PR once its DNS Preview check has passed."
    )
    p_merge.add_argument("pr", type=int, help="Pull request number.")
    p_merge.add_argument(
        "--yes", action="store_true", help="Skip the interactive confirmation prompt."
    )
    p_merge.add_argument(
        "--force", action="store_true",
        help="Merge even if the DNS Preview check failed or hasn't run.",
    )
    p_merge.add_argument(
        "--wait", action="store_true",
        help="After merging, wait for 'DNS Apply' to complete and confirm live Cloudflare "
        "state matches dnsconfig.js (equivalent to running `validate` immediately after).",
    )
    p_merge.add_argument(
        "--timeout", type=int, default=DEFAULT_VALIDATE_TIMEOUT,
        help=f"With --wait, max seconds to wait for 'DNS Apply' to appear/complete "
        f"(default: {DEFAULT_VALIDATE_TIMEOUT}).",
    )
    p_merge.set_defaults(func=cmd_merge)

    p_history = sub.add_parser(
        "history", help="List merges to main that touched dnsconfig.js, newest first."
    )
    p_history.add_argument(
        "--limit", type=int, default=20, help="Max merges to show (default: 20)."
    )
    p_history.set_defaults(func=cmd_history)

    p_rollback = sub.add_parser(
        "rollback",
        help="Revert a merged dnsconfig.js change via a new PR (never pushes to main).",
    )
    p_rollback.add_argument(
        "target", help="PR number (e.g. 17) or merge commit SHA - see `dnsctl.py history`."
    )
    p_rollback.add_argument(
        "--yes", action="store_true", help="Skip the interactive diff confirmation."
    )
    p_rollback.set_defaults(func=cmd_rollback)

    p_validate = sub.add_parser(
        "validate",
        help="Confirm a merged change's 'DNS Apply' run succeeded and live Cloudflare "
        "matches dnsconfig.js.",
    )
    p_validate.add_argument(
        "target", nargs="?", default=None,
        help="PR number or commit SHA to validate (default: current tip of origin/main).",
    )
    p_validate.add_argument(
        "--timeout", type=int, default=DEFAULT_VALIDATE_TIMEOUT,
        help=f"Max seconds to wait for the 'DNS Apply' run to appear/complete "
        f"(default: {DEFAULT_VALIDATE_TIMEOUT}).",
    )
    p_validate.set_defaults(func=cmd_validate)

    p_record = sub.add_parser("record", help="Add, remove, or list records in dnsconfig.js.")
    record_sub = p_record.add_subparsers(dest="record_command", required=True)

    p_record_add = record_sub.add_parser(
        "add", help='Add a record, e.g. `record add plex.example.com`.'
    )
    p_record_add.add_argument(
        "target",
        help='Record name - fully-qualified (e.g. "plex.example.com") or, with '
             '--zone, a bare relative name (e.g. "plex").',
    )
    p_record_add.add_argument(
        "--zone", choices=ZONES, default=None,
        help=f"Zone, required for a bare relative name ({', '.join(ZONES)}). "
             "Inferred automatically from a fully-qualified target.",
    )
    p_record_add.add_argument(
        "--type", choices=["A", "CNAME", "MX", "TXT"], default=None,
        help="Record type. Prompted for if omitted.",
    )
    p_record_add.add_argument("--value", default=None, help="Target/value. Prompted for if omitted.")
    p_record_add.add_argument("--priority", type=int, default=None, help="MX priority.")
    p_record_add.add_argument(
        "--proxy", dest="proxy", action="store_true", default=None,
        help="Enable the Cloudflare proxy (A/CNAME only).",
    )
    p_record_add.add_argument(
        "--no-proxy", dest="proxy", action="store_false",
        help="Disable the Cloudflare proxy (A/CNAME only).",
    )
    p_record_add.add_argument("--ttl", type=int, default=None, help="TTL override in seconds.")
    p_record_add.add_argument(
        "--yes", action="store_true",
        help="Skip confirmation prompts and the preview/submit offer (needs --type and --value).",
    )
    p_record_add.set_defaults(func=cmd_record_add)

    p_record_edit = record_sub.add_parser(
        "edit",
        help='Change the value/priority/proxy/TTL of an existing record in place '
             '(instead of remove + add).',
    )
    p_record_edit.add_argument(
        "target",
        help='Record name - fully-qualified (e.g. "plex.example.com") or, with '
             '--zone, a bare relative name (e.g. "plex").',
    )
    p_record_edit.add_argument(
        "--zone", choices=ZONES, default=None,
        help=f"Zone, required for a bare relative name ({', '.join(ZONES)}). "
             "Inferred automatically from a fully-qualified target.",
    )
    p_record_edit.add_argument(
        "--type", default=None, help="Restrict to this record type if there are multiple matches."
    )
    p_record_edit.add_argument(
        "--index", type=int, default=None,
        help="Pick a specific match by index (see `record list`) when there are multiple.",
    )
    p_record_edit.add_argument("--value", default=None, help="New target/value. Prompted for if omitted.")
    p_record_edit.add_argument("--priority", type=int, default=None, help="New MX priority.")
    p_record_edit.add_argument(
        "--proxy", dest="proxy", action="store_true", default=None,
        help="Enable the Cloudflare proxy (A/CNAME only).",
    )
    p_record_edit.add_argument(
        "--no-proxy", dest="proxy", action="store_false",
        help="Disable the Cloudflare proxy (A/CNAME only).",
    )
    p_record_edit.add_argument("--ttl", type=int, default=None, help="New TTL override in seconds.")
    p_record_edit.add_argument(
        "--yes", action="store_true",
        help="Skip confirmation prompts and the preview/submit offer (needs --value).",
    )
    p_record_edit.set_defaults(func=cmd_record_edit)

    p_record_remove = record_sub.add_parser(
        "remove", help='Remove a record, e.g. `record remove plex.example.com`.'
    )
    p_record_remove.add_argument(
        "target",
        help='Record name - fully-qualified (e.g. "plex.example.com") or, with '
             '--zone, a bare relative name (e.g. "plex").',
    )
    p_record_remove.add_argument(
        "--zone", choices=ZONES, default=None,
        help=f"Zone, required for a bare relative name ({', '.join(ZONES)}). "
             "Inferred automatically from a fully-qualified target.",
    )
    p_record_remove.add_argument(
        "--type", default=None, help="Restrict to this record type if there are multiple matches."
    )
    p_record_remove.add_argument(
        "--index", type=int, default=None,
        help="Pick a specific match by index (see `record list`) when there are multiple.",
    )
    p_record_remove.add_argument(
        "--yes", action="store_true",
        help="Skip confirmation prompts and the preview/submit offer.",
    )
    p_record_remove.set_defaults(func=cmd_record_remove)

    p_record_list = record_sub.add_parser(
        "list", help="List records, optionally filtered by zone and/or name."
    )
    p_record_list.add_argument(
        "name", nargs="?", default=None,
        help='Filter by name, e.g. "plex" or "plex.example.com". Omit to list all zones.',
    )
    p_record_list.add_argument(
        "--zone", choices=ZONES, default=None,
        help=f"Restrict to one zone ({', '.join(ZONES)}). Required with a bare relative `name`.",
    )
    p_record_list.set_defaults(func=cmd_record_list)

    p_record_update_ip = record_sub.add_parser(
        "update-ip",
        help="Bulk-replace an IP across every A record that currently points at it, "
             "e.g. after a residential IP change.",
    )
    p_record_update_ip.add_argument("old_ip", help="The current IP to find, e.g. 203.0.113.10.")
    p_record_update_ip.add_argument("new_ip", help="The new IP to replace it with.")
    p_record_update_ip.add_argument(
        "--zone", choices=ZONES, default=None,
        help=f"Restrict to one zone ({', '.join(ZONES)}). Default: all zones.",
    )
    p_record_update_ip.add_argument(
        "--yes", action="store_true",
        help="Skip the confirmation prompt and the preview/submit offer.",
    )
    p_record_update_ip.set_defaults(func=cmd_record_update_ip)

    p_record_prune_acme = record_sub.add_parser(
        "prune-acme",
        help="List _acme-challenge TXT records, cross-checked against live Cloudflare state "
             "by default, and optionally remove specific ones.",
    )
    p_record_prune_acme.add_argument(
        "--zone", choices=ZONES, default=None,
        help=f"Restrict to one zone ({', '.join(ZONES)}). Default: all zones.",
    )
    p_record_prune_acme.add_argument(
        "--remove", type=parse_index_arg, nargs="+", default=None, metavar="INDEX",
        help="Remove the record(s) at these indices (from the listing) instead of just reporting. "
             "Accepts plain indices, ranges ('1-6'), and comma-separated combos ('1,2,4-6'), "
             "space-separated or mixed, e.g. --remove 1-3 5 7-8.",
    )
    p_record_prune_acme.add_argument(
        "--offline", action="store_true",
        help="Skip the live Cloudflare cross-check (the default) and only use the token-count "
             "heuristic - no .env/network needed. By default, with .env configured, each entry "
             "is annotated against real Cloudflare state instead of only flagging by token "
             "count, and live records missing from dnsconfig.js (which a future apply would "
             "otherwise delete) are also reported. Read-only either way - never modifies "
             "dnsconfig.js by itself.",
    )
    p_record_prune_acme.add_argument(
        "--yes", action="store_true",
        help="Skip the confirmation prompt and the preview/submit offer (with --remove).",
    )
    p_record_prune_acme.set_defaults(func=cmd_record_prune_acme)

    p_record_sync_acme = record_sub.add_parser(
        "sync-acme",
        help="Fold live Cloudflare's _acme-challenge TXT records into dnsconfig.js "
             "(add what's missing, remove what's gone upstream).",
    )
    p_record_sync_acme.add_argument(
        "--zone", choices=ZONES, default=None,
        help=f"Restrict to one zone ({', '.join(ZONES)}). Default: all zones.",
    )
    p_record_sync_acme.add_argument(
        "--yes", action="store_true",
        help="Skip the confirmation prompt and the preview/submit offer.",
    )
    p_record_sync_acme.set_defaults(func=cmd_record_sync_acme)

    p_lint = sub.add_parser(
        "lint",
        help="Fast, offline sanity checks on dnsconfig.js (no dnscontrol/network call).",
    )
    p_lint.add_argument(
        "--zone", choices=ZONES, default=None,
        help=f"Restrict to one zone ({', '.join(ZONES)}). Default: all zones.",
    )
    p_lint.set_defaults(func=cmd_lint)

    p_show = sub.add_parser(
        "show",
        help="Show a table of all DNS records across managed zones "
             "(terminal, CSV, or Markdown).",
    )
    p_show.add_argument(
        "--zone", choices=ZONES, default=None,
        help=f"Restrict to one zone ({', '.join(ZONES)}). Default: all zones.",
    )
    p_show.add_argument(
        "--output", choices=["table", "csv", "md"], default="table",
        help="Output format (default: table).",
    )
    p_show.add_argument(
        "--file", default=None,
        help="Write output to this file instead of printing to the terminal.",
    )
    p_show.add_argument(
        "--grep", default=None,
        help="Filter rows to those where this substring appears in any column "
             "(case-insensitive) - e.g. an IP or hostname.",
    )
    p_show.set_defaults(func=cmd_show)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
