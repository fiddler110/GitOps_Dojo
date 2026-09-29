#!/bin/sh
# vault-fundamentals lab 8 (with the stack up): Forgejo Actions secrets: fork, a repository secret, masking, a single-use runner.
# Resets what it leaves behind first, so it can run again. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/lab_8.sh [student03]
. "$(dirname "$0")/lib.sh"

echo "== reset $s"
reset_repo
need_netrc; git_identity

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
as 'git credential-cache exit 2>/dev/null' >/dev/null 2>&1
finish "lab 8"
