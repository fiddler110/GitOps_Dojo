#!/bin/sh
# vault-fundamentals labs 8-9 (T3.9), with the stack up: runs the labs' steps
# as one student and checks what each job's log shows. The lab's password
# prompts are replaced by a ~/.netrc (removed at the end), and the Forgejo UI
# steps (adding and removing a repository secret) by the same API calls. It
# first removes what an earlier run left (the fork, the clone, the CI roles and
# secret in the student's namespace), so it can run again. Needs python3 >=
# 3.14 on the host (job logs are zstd). Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/labs_8_9.sh [student03]
s="${1:-student03}"
set -a; . engine/.env; set +a
failed=0
as() { podman exec -i workshop_terminal su - "$s" -c "$1"; }
ok()   { if out="$(as "$2" 2>&1)"; then echo "  ok:   $1"; else echo "  FAIL: $1: $(echo "$out" | tail -3)"; failed=1; fi; }
check() { case "$2" in *"$3"*) echo "  ok:   $1" ;; *) echo "  FAIL: $1 (no '$3')"; failed=1 ;; esac; }
api() { podman exec workshop_terminal curl -s -u "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$1" "http://git-server:3000/api/v1$2" ${3:+-d "$3"}; }
logs() { podman exec workshop_forge sh -c "find /data/gitea/actions_log/$s/vault-fundamentals -name '*.log.zst' 2>/dev/null" | sort; }
# push_and_read N CMD: run CMD (a push) as the student, wait for N new job
# logs, print them decompressed.
push_and_read() {
  before="$(logs)"
  ok "push: $2" "cd ~/lab/vault-fundamentals && $2" >&2
  end=$(( $(date +%s) + 240 ))
  while [ "$(logs | grep -vxF -e "$before" -e '' | wc -l)" -lt "$1" ] && [ "$(date +%s)" -lt "$end" ]; do sleep 3; done
  for f in $(logs | grep -vxF -e "$before" -e ''); do
    podman exec workshop_forge cat "$f" | python3 -B -c 'import compression.zstd as z,sys; sys.stdout.write(z.decompress(sys.stdin.buffer.read()).decode())'
  done; }

echo "== reset $s"
api DELETE "/repos/$s/vault-fundamentals" >/dev/null
as 'rm -rf ~/lab/vault-fundamentals; export BAO_NAMESPACE=students/$USER
    bao delete auth/jwt-ci/role/ci-main; bao delete auth/approle/role/ci
    bao kv metadata delete team/ci; bao policy delete ci-read' >/dev/null 2>&1
printf 'machine git-server login %s password %s\n' "$s" "${STUDENT_PASSWORD:-student123}" \
  | as 'umask 077; cat > ~/.netrc'
as 'git config --global user.name "$USER"; git config --global user.email "$USER@dojo.test"' >/dev/null

echo "== lab 8: Forgejo Actions secrets"
ok "fork" 'curl -sf --netrc -H "Content-Type: application/json" -d "{}" http://git-server:3000/api/v1/repos/platform-team/vault-fundamentals/forks >/dev/null'
ok "clone" 'cd ~/lab && git clone -q http://git-server:3000/$USER/vault-fundamentals.git && cd vault-fundamentals && git config credential.helper "cache --timeout=3600"'
key="demo-key-test-$(date +%s)"
ok "repository secret (the UI step, by API)" "printf '{\"data\":\"$key\"}' > ~/.b.json && curl -sf --netrc -X PUT -H 'Content-Type: application/json' -d @\$HOME/.b.json http://git-server:3000/api/v1/repos/\$USER/vault-fundamentals/actions/secrets/DEMO_API_KEY; rc=\$?; rm -f ~/.b.json; exit \$rc"
as 'mkdir -p ~/lab/vault-fundamentals/.forgejo/workflows && cat > ~/lab/vault-fundamentals/.forgejo/workflows/secrets-demo.yml' <<'EOF'
name: secrets-demo
on: push
jobs:
  demo:
    runs-on: host
    steps:
      - name: Where does this job run?
        run: |
          echo "runner user: $(id -un)   home: $HOME"
          echo "processes this job can see: $(ls -d /proc/[0-9]* | wc -l)"
      - name: Use the secret
        env:
          API_KEY: ${{ secrets.DEMO_API_KEY }}
        run: |
          echo "The key is $API_KEY"
          echo "It is ${#API_KEY} characters long"
      - name: Print it in a form the mask doesn't know
        env:
          API_KEY: ${{ secrets.DEMO_API_KEY }}
        run: |
          echo "$API_KEY" | base64
          echo "$API_KEY" | sed 's/./& /g'
EOF
log="$(push_and_read 1 'git add . && git commit -qm "secrets demo" && git push -q')"
check "the key is masked" "$log" 'The key is ***'
check "base64 gets round the mask" "$log" "$(printf '%s\n' "$key" | base64)"
check "a single-use runner user" "$log" 'runner user: pool-'
procs="$(echo "$log" | sed -n 's/.*processes this job can see: \([0-9]*\).*/\1/p' | head -1)"
[ -n "$procs" ] && [ "$procs" -lt 15 ] && echo "  ok:   the job sees $procs processes" || { echo "  FAIL: the job sees '$procs' processes"; failed=1; }
ok "delete the secret" 'curl -sf --netrc -X DELETE http://git-server:3000/api/v1/repos/$USER/vault-fundamentals/actions/secrets/DEMO_API_KEY'
push_and_read 0 'git rm -q .forgejo/workflows/secrets-demo.yml && git commit -qm "remove demo" && git push -q' >/dev/null

echo "== lab 9: CI logs in to OpenBao"
ok "catch-up and the deploy token" 'export BAO_NAMESPACE=students/$USER
    bao secrets list | grep -q "^team/" || bao secrets enable -path=team kv-v2
    bao auth list | grep -q "^approle/" || bao auth enable approle
    for i in 1 2 3 4 5; do bao kv put team/ci deploy_token="deploy-$USER-$RANDOM$RANDOM" && break; sleep 2; done
    printf "path \"team/data/ci\" {\n  capabilities = [\"read\"]\n}\n" | bao policy write ci-read -'
fp="$(as 'BAO_NAMESPACE=students/$USER; export BAO_NAMESPACE; printf %s "$(bao kv get -field=deploy_token team/ci)" | sha256sum | cut -c1-12')"
echo "    expected fingerprint: $fp"
ok "approle role and repository secrets" 'export BAO_NAMESPACE=students/$USER
    bao write auth/approle/role/ci token_policies=ci-read token_ttl=5m secret_id_ttl=24h >/dev/null &&
    put() { (umask 077; printf "{\"data\":\"%s\"}" "$2" > ~/.b.json)
      curl -sf --netrc -X PUT -H "Content-Type: application/json" -d @$HOME/.b.json \
        http://git-server:3000/api/v1/repos/$USER/vault-fundamentals/actions/secrets/$1; rc=$?; rm -f ~/.b.json; return $rc; }
    put BAO_ROLE_ID "$(bao read -field=role_id auth/approle/role/ci/role-id)" &&
    put BAO_SECRET_ID "$(bao write -f -field=secret_id auth/approle/role/ci/secret-id)"'
# The workflows, taken from the lab pages themselves. Lab 8's clean-up removed
# the folder with its last file; the lab's own mkdir -p comes later.
for wf in vault-approle vault-oidc; do
  sed -n "/cat > .forgejo\/workflows\/$wf.yml <<'EOF'/,/^EOF\$/p" workshops/vault-fundamentals/content/lab/lab9.md \
    | sed '1d;$d' | as "mkdir -p ~/lab/vault-fundamentals/.forgejo/workflows && cat > ~/lab/vault-fundamentals/.forgejo/workflows/$wf.yml.next"
done
as 'cd ~/lab/vault-fundamentals/.forgejo/workflows && test -s vault-approle.yml.next && test -s vault-oidc.yml.next' \
  || { echo "  FAIL: couldn't extract the workflows from lab9.md"; failed=1; }
log="$(push_and_read 1 'mv .forgejo/workflows/vault-approle.yml.next .forgejo/workflows/vault-approle.yml && git add .forgejo/workflows/vault-approle.yml && git commit -qm approle && git push -q')"
check "AppRole job reads the token" "$log" "deploy token fingerprint: $fp"
ok "the jwt-ci role" 'export BAO_NAMESPACE=students/$USER; bao write auth/jwt-ci/role/ci-main - <<EOF
{"role_type":"jwt","user_claim":"sub","bound_audiences":["openbao"],
 "bound_claims":{"repository":"$USER/vault-fundamentals","ref":"refs/heads/main"},
 "token_policies":["ci-read"],"token_ttl":"5m"}
EOF'
log="$(push_and_read 2 'mv .forgejo/workflows/vault-oidc.yml.next .forgejo/workflows/vault-oidc.yml && git add .forgejo/workflows/vault-oidc.yml && git commit -qm oidc && git push -q')"
check "OIDC claims name the repo" "$log" "\"repository\": \"$s/vault-fundamentals\""
check "the vault token has ci-read" "$log" '"ci-read"'
check "OIDC job reads the token" "$log" "$(printf 'deploy token fingerprint: %s' "$fp")"
[ "$(echo "$log" | grep -c "deploy token fingerprint: $fp")" -ge 2 ] && echo "  ok:   both jobs read it" \
  || { echo "  FAIL: expected two fingerprints"; failed=1; }
log="$(push_and_read 2 'git switch -q -c try-a-branch && git commit -q --allow-empty -m branch && git push -q -u origin try-a-branch')"
check "a branch is refused" "$log" 'claim "ref" does not match'
check "AppRole doesn't tell a branch from main" "$log" "deploy token fingerprint: $fp"
ok "back to main, branch deleted" 'cd ~/lab/vault-fundamentals && git switch -q main && git push -q origin --delete try-a-branch'
ok "retire AppRole" 'export BAO_NAMESPACE=students/$USER; bao delete auth/approle/role/ci >/dev/null &&
    for x in BAO_ROLE_ID BAO_SECRET_ID; do curl -sf --netrc -X DELETE http://git-server:3000/api/v1/repos/$USER/vault-fundamentals/actions/secrets/$x || exit 1; done'
log="$(push_and_read 1 'git rm -q .forgejo/workflows/vault-approle.yml && git commit -qm "drop approle" && git push -q')"
check "OIDC still works on main" "$log" "deploy token fingerprint: $fp"

as 'rm -f ~/.netrc; git credential-cache exit 2>/dev/null' >/dev/null 2>&1
[ "$failed" = 0 ] && echo PASS || { echo FAIL; exit 1; }
