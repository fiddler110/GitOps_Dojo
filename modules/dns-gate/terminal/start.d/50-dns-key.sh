#!/bin/sh
# dns-gate start.d hook, run by the base web-terminal entrypoint as root after
# every account exists. Writes each account's own dns-api key to
# ~/.config/dojo/dns-api-key (0600, the account's own), which every shell
# exports as DNS_API_KEY (the terminal Dockerfile). Root's shell is the
# facilitator's, so /root gets FACILITATOR_USERNAME's key. The key is
# derived from STUDENT_PASSWORD_SEED, which students never see; the same
# function is in ../gate/gate.py (dns_key).
set -eu

if [ -z "${STUDENT_PASSWORD_SEED:-}" ]; then
  echo "dns-key: STUDENT_PASSWORD_SEED is empty; no account gets a DNS key (dns-api allows reads only)" >&2
  exit 0
fi

write_key() {
  user="$1" home="$2" owner="$3"
  dir="$home/.config/dojo"
  [ -d "$home/.config" ] || install -d -m 0700 -o "$owner" -g "$(id -gn "$owner")" "$home/.config"
  install -d -m 0700 -o "$owner" -g "$(id -gn "$owner")" "$dir"
  (umask 077 && DNS_USER="$user" python3 -c '
import base64, hashlib, hmac, os
mac = hmac.new(os.environ["STUDENT_PASSWORD_SEED"].encode(), ("dns:" + os.environ["DNS_USER"]).encode(),
               hashlib.sha256).digest()
print(os.environ["DNS_USER"] + "." + base64.b32encode(mac).decode()[:32])' > "$dir/dns-api-key.tmp")
  chown "$owner:$(id -gn "$owner")" "$dir/dns-api-key.tmp"
  mv "$dir/dns-api-key.tmp" "$dir/dns-api-key"
}

n=0
for home in /home/*; do
  [ -d "$home" ] || continue
  user="$(stat -c %U "$home")"
  [ "$user" = "$(basename "$home")" ] || continue
  write_key "$user" "$home" "$user"
  n=$((n + 1))
done
write_key "${FACILITATOR_USERNAME:-root}" /root root
echo "dns-key: wrote ${n} account keys and the facilitator's"
