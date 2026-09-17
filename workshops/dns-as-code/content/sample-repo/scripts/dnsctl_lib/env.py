"""Loading the Cloudflare API token: local .env file, falling back to Azure
Key Vault. See docs/security.md#key-vault-backed-tokens."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .cli_utils import eprint


def load_env_file(path: Path) -> dict:
    """Minimal KEY=VALUE .env parser. No external dependency required."""
    env = {}
    if not path.is_file():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            env[key] = value
    return env


def fetch_keyvault_secret(vault: str, secret_name: str) -> str | None:
    """Fetch a secret's current value from Azure Key Vault via the Azure CLI.

    Shells out to `az` rather than adding the azure-keyvault-secrets/azure-identity
    SDKs as a dependency - this project is deliberately Python-stdlib-only (see
    CLAUDE.md), and `az` is just another external tool in the same category as
    `gh`/`dnscontrol`. Returns None (with a warning on stderr) on any failure so
    callers can fall back to .env/the environment instead of hard-erroring."""
    az = shutil.which("az")
    if not az:
        eprint(
            "warning: Azure CLI ('az') not found on PATH - can't fetch "
            f"'{secret_name}' from Key Vault '{vault}'. Install it: "
            "https://learn.microsoft.com/cli/azure/install-azure-cli"
        )
        return None
    result = subprocess.run(
        [az, "keyvault", "secret", "show", "--vault-name", vault,
         "--name", secret_name, "--query", "value", "-o", "tsv"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        eprint(
            f"warning: could not fetch secret '{secret_name}' from Key Vault "
            f"'{vault}'{f' ({stderr})' if stderr else ''}. Run 'az login' if you "
            "haven't authenticated, and confirm you have the 'Key Vault Secrets "
            "User' role on this vault."
        )
        return None
    token = result.stdout.strip()
    return token or None


def load_cloudflare_env(env_file: Path) -> dict:
    """Load the local .env, then - if CLOUDFLARE_API_TOKEN isn't already set
    there or in the environment - fetch it from Azure Key Vault when a vault
    is configured (CLOUDFLARE_KEYVAULT_NAME, optionally CLOUDFLARE_KEYVAULT_SECRET_NAME
    in .env or the environment). The fetched value is only ever held in this
    in-memory dict for the current process/subprocess call - never written to
    .env or disk anywhere. .env/the environment take priority and are the only
    thing consulted if no vault is configured, so a solo operator who hasn't
    set one up sees no change in behavior. See docs/security.md#key-vault-backed-tokens."""
    env = load_env_file(env_file)
    if "CLOUDFLARE_API_TOKEN" in env or "CLOUDFLARE_API_TOKEN" in os.environ:
        return env

    vault = env.get("CLOUDFLARE_KEYVAULT_NAME") or os.environ.get("CLOUDFLARE_KEYVAULT_NAME")
    if not vault:
        return env

    secret_name = (
        env.get("CLOUDFLARE_KEYVAULT_SECRET_NAME")
        or os.environ.get("CLOUDFLARE_KEYVAULT_SECRET_NAME")
        or "cloudflare-api-token-readonly"
    )
    print(
        f"No local CLOUDFLARE_API_TOKEN - fetching from Key Vault '{vault}' "
        f"(secret '{secret_name}')...",
        file=sys.stderr,
    )
    token = fetch_keyvault_secret(vault, secret_name)
    if token:
        env["CLOUDFLARE_API_TOKEN"] = token
    return env
