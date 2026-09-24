#!/bin/sh
# Spike supervisor: for every /cfg/rN.yaml start one one-job runner as user
# rN (fresh home, 0700, umask 077, own TMPDIR) inside its own user + PID
# namespace. When it exits, kill anything left, delete the user and its files.
set -eu
# Users first, one at a time: useradd takes a lock on /etc/passwd.
for cfg in /cfg/*.yaml; do
  u="$(basename "$cfg" .yaml)"
  useradd -m -K UMASK=077 -s /bin/sh "$u"
  install -o "$u" -m 600 "$cfg" "/home/$u/config.yaml"
  mkdir -m 700 "/home/$u/tmp"; chown "$u" "/home/$u/tmp"
done
for cfg in /cfg/*.yaml; do
  u="$(basename "$cfg" .yaml)"
  (
    echo "[supervise] $u starting"
    su "$u" -s /bin/sh -c "umask 077; cd; TMPDIR=\$HOME/tmp exec unshare -U --map-current-user -p -f --mount-proc \
      forgejo-runner one-job --config \$HOME/config.yaml --wait" 2>&1 | sed "s/^/[$u] /" || true
    su "$u" -s /bin/sh -c 'kill -9 -1' 2>/dev/null || true
    # userdel locks /etc/passwd too: runners finishing together must take turns.
    flock /run/users.lock userdel -r "$u" 2>/dev/null || echo "[supervise] userdel $u failed"
    echo "[supervise] $u finished and removed"
  ) &
done
wait
echo "[supervise] all runners done"
sleep infinity
