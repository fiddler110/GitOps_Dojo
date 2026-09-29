#!/bin/sh
# vault-fundamentals lab 11 (with the stack up): deploy with workload identity. Replays lab 8's fork and clone.
# Resets what it leaves behind first, so it can run again. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/lab_11.sh [student03]
. "$(dirname "$0")/lib.sh"

echo "== reset $s"
reset_labs_11_13
echo "== prerequisite: lab 8's fork and clone"
fork_clone

echo "== lab 11: deploy with workload identity"
replay_lab11
check "catch-up, the platform's keys" "$out" '"alg": "RS256"'
check "jwt-platform is set up" "$out" 'http://app-host:8080'
check "the deploy job deployed" "$log" '"state": "running"'
check "the pipeline can't read team/app" "$log" 'permission denied for the pipeline, as it should be'
page="$(as 'curl -s http://app-host:8080/$USER/')"
check "the app's platform identity" "$page" "sub=slot:$s"
check "another slot's identity is out of reach" "$page" "identity: Permission denied"
check "the app has the vault's api_key" "$page" "API_KEY fingerprint: $(fp api_key app)"
check "no database yet" "$page" "database: not set up"
out="$(as "export BAO_NAMESPACE=students/\$USER; $(block lab11.md 10)" 2>&1)"
new="$(fp api_key app)"
[ "$(echo "$out" | grep -c "$new")" -ge 2 ] && echo "  ok:   rotated with no deploy ($new)" \
  || { echo "  FAIL: rotation not seen: $out"; failed=1; }
log="$(run_and_read 1 "$(block lab11.md 11)")"
check "a branch can't deploy" "$log" "only main deploys; this run is on 'refs/heads/try-a-branch'"
ok "back to main" "cd ~/lab/vault-fundamentals && $(block lab11.md 12)"

finish "lab 11"
