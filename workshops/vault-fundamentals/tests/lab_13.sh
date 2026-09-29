#!/bin/sh
# vault-fundamentals lab 13 (with the stack up): the incident drill. Replays lab 8's fork and clone and lab 11's first deploy.
# Resets what it leaves behind first, so it can run again. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/lab_13.sh [student03]
. "$(dirname "$0")/lib.sh"

echo "== reset $s"
reset_labs_11_13
echo "== prerequisite: lab 8's fork and clone, lab 11's deploy"
fork_clone
replay_lab11
case "$log" in *'"state": "running"'*) ;; *) echo "FAIL: replaying lab 11: no deploy"; echo "$log" | tail -5; exit 1 ;; esac

echo "== lab 13: incident drill"
out="$(as "$(block lab13.md 1 hcl:1:~/lab/nightly-report.hcl 2 3 4 5 6 7 8 9 10)" 2>&1)"
echo "$out" | grep -E '^(attacker|TIME|20[0-9][0-9]-)' | sed 's/^/    /'
check "the attacker read team/app" "$out" 'attacker: read team/app'
check "and made a spare" "$out" 'attacker: made a spare token, and it works'
check "the audit shows the reads" "$out" 'team/data/ci'
check "the audit shows the refusal" "$out" 'denied'
check "the audit shows the spare" "$out" 'made token'
check "the spare died with its parent" "$out" 'invalid accessor'
check "the leaked token is dead" "$out" 'permission denied'
new="$(fp api_key app)"
[ "$(echo "$out" | grep -c "$new")" -ge 2 ] && echo "  ok:   the app recovered by itself ($new)" \
  || { echo "  FAIL: the app didn't pick up $new"; failed=1; }
check "remote_address shown" "$out" 'remote_address'

finish "lab 13"
