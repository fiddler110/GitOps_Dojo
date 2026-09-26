#!/bin/sh
# start.d hook, run once by the base entrypoint (engine/web-terminal/
# entrypoint.sh) as root, after every account and its VS Code settings.json
# exist and before any workspace is served.
#
# VS Code hides .git by default (files.exclude). Lab 1 writes its pre-commit
# hook straight into .git/hooks/, so every account (students and the
# facilitator) sees .git in the Explorer. The key is only added when absent,
# so a student who sets it back to true keeps their choice across restarts.
set -eu

for settings in /root/.local/share/code-server/User/settings.json \
                /home/*/.local/share/code-server/User/settings.json; do
  [ -f "$settings" ] || continue
  python3 -B - "$settings" <<'EOF'
import json, os, sys

path = sys.argv[1]
try:
    with open(path) as f:
        settings = json.load(f)
except ValueError:
    # Hand-edited JSONC (comments): leave it alone rather than fail the start.
    print(f"90-show-git-folder: {path} is not plain JSON, skipped", file=sys.stderr)
    sys.exit(0)

exclude = settings.setdefault("files.exclude", {})
if "**/.git" in exclude:
    sys.exit(0)
exclude["**/.git"] = False

st = os.stat(path)
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
os.chown(tmp, st.st_uid, st.st_gid)
os.chmod(tmp, st.st_mode & 0o777)
os.replace(tmp, path)
EOF
done
