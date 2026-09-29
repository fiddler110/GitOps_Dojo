#!/bin/sh
# vault-fundamentals lab 9 (with the stack up): CI logs in to OpenBao: AppRole, the job's OIDC identity, a branch refused. Replays lab 8's fork and clone.
# Resets what it leaves behind first, so it can run again. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/lab_9.sh [student03]
. "$(dirname "$0")/lib.sh"

echo "== reset $s"
reset_repo
as 'export BAO_NAMESPACE=students/$USER
    bao delete auth/jwt-ci/role/ci-main; bao delete auth/approle/role/ci
    bao kv metadata delete team/ci; bao policy delete ci-read' >/dev/null 2>&1
echo "== prerequisite: lab 8's fork and clone"
fork_clone
as 'cd ~/lab/vault-fundamentals && git config credential.helper "cache --timeout=3600"'

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
n=0
for wf in vault-approle vault-oidc; do  # the lab's first and second `yaml` file blocks
  n=$((n + 1))
  python3 -B -c 'import re, sys; print([c for l, c in re.findall(r"^```(\w+)\n(.*?)^```$", open(sys.argv[1]).read(), re.S | re.M) if l == "yaml"][int(sys.argv[2]) - 1], end="")' \
    workshops/vault-fundamentals/content/lab/lab9.md "$n" \
    | as "mkdir -p ~/lab/vault-fundamentals/.forgejo/workflows && cat > ~/lab/vault-fundamentals/.forgejo/workflows/$wf.yml.next"
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

finish "lab 9"
