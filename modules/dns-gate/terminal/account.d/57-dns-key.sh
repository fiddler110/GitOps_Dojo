#!/bin/sh
# dns-gate account.d hook (engine/web-terminal/entrypoint.sh, workspace-control.py): one account's
# own dns-api key at ~/.config/dojo/dns-api-key (0600, the account's own), at start and again
# after a student reset (which removes the home). Same derivation as start.d/50-dns-key.sh and
# ../gate/gate.py (dns_key). Idempotent. Never fails: a failing account.d hook stops the container.
set -u
user="$1"
home="/home/$user"
if [ -z "${STUDENT_PASSWORD_SEED:-}" ]; then
  echo "dns-key: STUDENT_PASSWORD_SEED is empty; $user gets no DNS key" >&2
  exit 0
fi
[ -d "$home" ] || { echo "dns-key: no $home; skipping" >&2; exit 0; }
group="$(id -gn "$user")" || exit 0
dir="$home/.config/dojo"
[ -d "$home/.config" ] || install -d -m 0700 -o "$user" -g "$group" "$home/.config" || exit 0
[ -d "$dir" ] || install -d -m 0700 -o "$user" -g "$group" "$dir" || exit 0
(umask 077 && DNS_USER="$user" python3 -c '
import base64, hashlib, hmac, os
mac = hmac.new(os.environ["STUDENT_PASSWORD_SEED"].encode(), ("dns:" + os.environ["DNS_USER"]).encode(),
               hashlib.sha256).digest()
print(os.environ["DNS_USER"] + "." + base64.b32encode(mac).decode()[:32])' > "$dir/dns-api-key.tmp") \
  && chown "$user:$group" "$dir/dns-api-key.tmp" && mv "$dir/dns-api-key.tmp" "$dir/dns-api-key" \
  || echo "dns-key: could not write $user's key" >&2
exit 0
