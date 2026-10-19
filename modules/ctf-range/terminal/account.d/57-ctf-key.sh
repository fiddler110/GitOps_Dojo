#!/bin/sh
# ctf-range account.d hook (engine/web-terminal/entrypoint.sh, workspace-control.py): one account's
# own ctf key at ~/.config/dojo/ctf-key (0600, the account's own), at start and again after a
# student reset. `dojo check`, `dojo reset` and `dojo flag` send it, and ctf-checker / ctf-flags
# accept a request only for the account whose key it carries (REVIEW §1.1). The key is
# HMAC-SHA256(STUDENT_PASSWORD_SEED, "ctf-user:<user>"), 32 hex: user_key in
# ../../ctf-checker/checker.py and ../../ctf-flags/flags.py. The seed never reaches a student.
# Root (the facilitator) has no key of its own; to act for a student, run the command with
# USER=<student> CTF_KEY_FILE=/home/<student>/.config/dojo/ctf-key.
# Never fails: a failing account.d hook stops the container.
set -u
user="$1"
home="/home/$user"
if [ -z "${STUDENT_PASSWORD_SEED:-}" ]; then
  echo "ctf-key: STUDENT_PASSWORD_SEED is empty; $user gets no ctf key (dojo check/reset/flag are refused)" >&2
  exit 0
fi
[ -d "$home" ] || { echo "ctf-key: no $home; skipping" >&2; exit 0; }
group="$(id -gn "$user")" || exit 0
dir="$home/.config/dojo"
[ -d "$home/.config" ] || install -d -m 0700 -o "$user" -g "$group" "$home/.config" || exit 0
[ -d "$dir" ] || install -d -m 0700 -o "$user" -g "$group" "$dir" || exit 0
(umask 077 && CTF_USER="$user" python3 -c '
import hashlib, hmac, os
print(hmac.new(os.environ["STUDENT_PASSWORD_SEED"].encode(), ("ctf-user:" + os.environ["CTF_USER"]).encode(),
               hashlib.sha256).hexdigest()[:32])' > "$dir/ctf-key.tmp") \
  && chown "$user:$group" "$dir/ctf-key.tmp" && mv "$dir/ctf-key.tmp" "$dir/ctf-key" \
  || echo "ctf-key: could not write $user's key" >&2
exit 0
