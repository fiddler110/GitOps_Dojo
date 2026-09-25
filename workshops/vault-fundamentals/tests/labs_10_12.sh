#!/bin/sh
# vault-fundamentals labs 10-12 (T4.8), with the stack up: runs every `bash`
# block of lab10.md, lab11.md and lab12.md as one student, as written, and
# checks what the terminal, the deploy jobs and the app show. Blocks that share
# shell variables run in one shell; a block that pushes is followed by a wait
# for its job logs. git's password prompt is replaced by a ~/.netrc (removed at
# the end). It first removes what an earlier run left (the fork, the clone, the
# roles and policies these labs write), so it can run again. Needs python3 >=
# 3.14 on the host (job logs are zstd). Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/labs_10_12.sh [student03]
s="${1:-student03}"
set -a; . engine/.env; set +a
labs=workshops/vault-fundamentals/content/lab
failed=0
as() { podman exec -i workshop_terminal su - "$s" -c "$1"; }
ok()   { if out="$(as "$2" 2>&1)"; then echo "  ok:   $1"; else echo "  FAIL: $1: $(echo "$out" | tail -3)"; failed=1; fi; }
check() { case "$2" in *"$3"*) echo "  ok:   $1" ;; *) echo "  FAIL: $1 (no '$3')"; echo "$2" | tail -8 | sed 's/^/        /'; failed=1 ;; esac; }
api() { podman exec workshop_terminal curl -s -u "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$1" "http://git-server:3000/api/v1$2" ${3:+-d "$3"}; }
logs() { podman exec workshop_forge sh -c "find /data/gitea/actions_log/$s/vault-fundamentals -name '*.log.zst' 2>/dev/null" | sort; }
# block FILE N...: the Nth ```bash blocks of a lab page, joined.
block() {
  f="$1"; shift
  python3 -B - "$labs/$f" "$@" <<'EOF'
import re, sys
text = open(sys.argv[1]).read()
blocks = re.findall(r"^```bash\n(.*?)^```$", text, re.S | re.M)
for n in sys.argv[2:]:
    sys.stdout.write(blocks[int(n) - 1])
EOF
}
# run_and_read N SCRIPT: run SCRIPT as the student (it pushes), wait for N new
# job logs, print its output then the logs decompressed.
run_and_read() {
  before="$(logs)"
  as "cd ~/lab/vault-fundamentals; $2" 2>&1
  end=$(( $(date +%s) + 240 ))
  while [ "$(logs | grep -vxF -e "$before" -e '' | wc -l)" -lt "$1" ] && [ "$(date +%s)" -lt "$end" ]; do sleep 3; done
  sleep 3  # the last lines of a finished job reach the archive a moment later
  for f in $(logs | grep -vxF -e "$before" -e ''); do
    podman exec workshop_forge cat "$f" | python3 -B -c 'import compression.zstd as z,sys; sys.stdout.write(z.decompress(sys.stdin.buffer.read()).decode())'
  done; }
fp() { as "export BAO_NAMESPACE=students/\$USER; printf %s \"\$(bao kv get -field=$1 team/$2)\" | sha256sum | cut -c1-12"; }

echo "== reset $s"
api DELETE "/repos/$s/vault-fundamentals" >/dev/null
as 'rm -rf ~/lab/vault-fundamentals ~/lab/nightly-report.hcl; export BAO_NAMESPACE=students/$USER
    bao delete auth/jwt-platform/role/app; bao delete database/roles/app
    for p in db-app nightly-report; do bao policy delete $p; done' >/dev/null 2>&1
printf 'machine git-server login %s password %s\n' "$s" "${STUDENT_PASSWORD:-student123}" \
  | as 'umask 077; cat > ~/.netrc'
as 'git config --global user.name "$USER"; git config --global user.email "$USER@dojo.test"' >/dev/null
ok "fork and clone (Lab 8)" 'curl -sf --netrc -H "Content-Type: application/json" -d "{}" http://git-server:3000/api/v1/repos/platform-team/vault-fundamentals/forks >/dev/null &&
    git clone -q http://git-server:3000/$USER/vault-fundamentals.git ~/lab/vault-fundamentals'

echo "== lab 10: deploy with workload identity"
out="$(as "$(block lab10.md 1 2 3)" 2>&1)"
check "catch-up, the platform's keys" "$out" '"alg": "RS256"'
check "jwt-platform is set up" "$out" 'http://app-host:8080'
log="$(run_and_read 1 "export BAO_NAMESPACE=students/\$USER; $(block lab10.md 4 5 6 7 8)")"
check "the deploy job deployed" "$log" '"state": "running"'
check "the pipeline can't read team/app" "$log" 'permission denied for the pipeline, as it should be'
page="$(as 'curl -s http://app-host:8080/$USER/')"
check "the app's platform identity" "$page" "sub=slot:$s"
check "another slot's identity is out of reach" "$page" "identity: Permission denied"
check "the app has the vault's api_key" "$page" "API_KEY fingerprint: $(fp api_key app)"
check "no database yet" "$page" "database: not set up"
out="$(as "export BAO_NAMESPACE=students/\$USER; $(block lab10.md 11)" 2>&1)"
new="$(fp api_key app)"
[ "$(echo "$out" | grep -c "$new")" -ge 2 ] && echo "  ok:   rotated with no deploy ($new)" \
  || { echo "  FAIL: rotation not seen: $out"; failed=1; }
log="$(run_and_read 1 "$(block lab10.md 12)")"
check "a branch can't deploy" "$log" "only main deploys; this run is on 'refs/heads/try-a-branch'"
ok "back to main" "cd ~/lab/vault-fundamentals && $(block lab10.md 13)"

echo "== lab 11: dynamic database credentials"
out="$(as "$(block lab11.md 1 2 3 4 5 6 7)" 2>&1)"
check "the connection is set up" "$out" "vault_$s"
check "a note written with a dynamic login" "$out" "written with a login that expires"
check "the author is the dynamic login" "$out" "| v-"
check "another student's database is refused" "$out" 'permission denied for database'
# Postgres says either, depending on whether the revoke's DROP ROLE ran yet.
case "$out" in *'password authentication failed'*|*'role "v-'*'" does not exist'*) echo "  ok:   revoked: the login is gone" ;;
  *) echo "  FAIL: revoked: the login is gone"; failed=1 ;; esac
log="$(run_and_read 1 "export BAO_NAMESPACE=students/\$USER; $(block lab11.md 8)")"
check "deployed with the database template" "$log" '"state": "running"'
end=$(( $(date +%s) + 30 ))
until page="$(as 'curl -s http://app-host:8080/$USER/')"; echo "$page" | grep -q 'database: connected' || [ "$(date +%s)" -gt "$end" ]; do sleep 3; done
check "the app connects with its own login" "$page" "database: connected as v-"
out="$(as "export BAO_NAMESPACE=students/\$USER; $(block lab11.md 10)" 2>&1)"
[ "$(echo "$out" | grep -c .)" -ge 2 ] && echo "  ok:   the leases are listed" || { echo "  FAIL: leases: $out"; failed=1; }

echo "== lab 12: incident drill"
out="$(as "$(block lab12.md 1 2 3 4 5 6 7 8 9)" 2>&1)"
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

as 'rm -f ~/.netrc'
[ "$failed" -eq 0 ] && echo "PASS: labs 10-12" || echo "FAIL: labs 10-12"
exit "$failed"
