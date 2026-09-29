#!/bin/sh
# vault-fundamentals lab 12 (with the stack up): dynamic database credentials. Replays lab 8's fork and clone and lab 11's first deploy.
# Resets what it leaves behind first, so it can run again. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/lab_12.sh [student03]
. "$(dirname "$0")/lib.sh"

echo "== reset $s"
reset_labs_11_13
echo "== prerequisite: lab 8's fork and clone, lab 11's deploy"
fork_clone
replay_lab11
case "$log" in *'"state": "running"'*) ;; *) echo "FAIL: replaying lab 11: no deploy"; echo "$log" | tail -5; exit 1 ;; esac

echo "== lab 12: dynamic database credentials"
out="$(as "$(block lab12.md 1 2 3 4 5 6 7)" 2>&1)"
check "the connection is set up" "$out" "vault_$s"
check "a note written with a dynamic login" "$out" "written with a login that expires"
check "the author is the dynamic login" "$out" "| v-"
check "another student's database is refused" "$out" 'permission denied for database'
# Postgres says either, depending on whether the revoke's DROP ROLE ran yet.
case "$out" in *'password authentication failed'*|*'role "v-'*'" does not exist'*) echo "  ok:   revoked: the login is gone" ;;
  *) echo "  FAIL: revoked: the login is gone"; failed=1 ;; esac
log="$(run_and_read 1 "export BAO_NAMESPACE=students/\$USER; $(block lab12.md hcl:1:+app/agent.hcl 8)")"
check "deployed with the database template" "$log" '"state": "running"'
end=$(( $(date +%s) + 30 ))
until page="$(as 'curl -s http://app-host:8080/$USER/')"; echo "$page" | grep -q 'database: connected' || [ "$(date +%s)" -gt "$end" ]; do sleep 3; done
check "the app connects with its own login" "$page" "database: connected as v-"
out="$(as "export BAO_NAMESPACE=students/\$USER; $(block lab12.md 10)" 2>&1)"
[ "$(echo "$out" | grep -c .)" -ge 2 ] && echo "  ok:   the leases are listed" || { echo "  FAIL: leases: $out"; failed=1; }

finish "lab 12"
