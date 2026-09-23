#!/usr/bin/env python3
"""Build-time only: flip the OpenTofu VS Code extension's language server to
off-by-default (see the comment in the Dockerfile for why).

Usage: disable-tofu-ls.py <extensions-dir>
Fails loudly if the extension or the setting isn't found exactly once, so a
future version that renames it breaks the build instead of shipping silently.
"""
import glob
import json
import sys

SETTING = "opentofu.languageServer.enable"

pkgs = glob.glob(f"{sys.argv[1]}/opentofu.vscode-opentofu-*/package.json")
if len(pkgs) != 1:
    sys.exit(f"expected exactly one OpenTofu extension, found: {pkgs}")

with open(pkgs[0]) as f:
    pkg = json.load(f)

config = pkg["contributes"]["configuration"]
hits = [
    block["properties"][SETTING]
    for block in (config if isinstance(config, list) else [config])
    if SETTING in block.get("properties", {})
]
if len(hits) != 1:
    sys.exit(f"expected exactly one {SETTING} setting, found {len(hits)}")

hits[0]["default"] = False
with open(pkgs[0], "w") as f:
    json.dump(pkg, f, indent=2)
print(f"{SETTING} now defaults to false in {pkgs[0]}")
