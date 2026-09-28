#!/bin/sh
# vault-fundamentals lab 10 (T5.16), with the stack up: runs every `bash` block
# of lab10.md as one student, as written (and writes the files it has them make), and checks what the terminal, the
# deploy jobs and the app show. Same helpers as labs_11_13.sh. It first removes
# what an earlier run left (the fork, the clone, the roles and the policy this
# lab writes), so it can run again. Needs python3 >= 3.14 on the host (job logs
# are zstd). Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/lab_10.sh [student03]
s="${1:-student03}"
set -a; . engine/.env; set +a
labs=workshops/vault-fundamentals/content/lab
failed=0
as() { podman exec -i workshop_terminal su - "$s" -c "$1"; }
ok()   { if out="$(as "$2" 2>&1)"; then echo "  ok:   $1"; else echo "  FAIL: $1: $(echo "$out" | tail -3)"; failed=1; fi; }
check() { case "$2" in *"$3"*) echo "  ok:   $1" ;; *) echo "  FAIL: $1 (no '$3')"; echo "$2" | tail -8 | sed 's/^/        /'; failed=1 ;; esac; }
lacks() { case "$2" in *"$3"*) echo "  FAIL: $1 ('$3' is there)"; failed=1 ;; *) echo "  ok:   $1" ;; esac; }
api() { podman exec workshop_terminal curl -s -u "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$1" "http://git-server:3000/api/v1$2" ${3:+-d "$3"}; }
logs() { podman exec workshop_forge sh -c "find /data/gitea/actions_log/$s/vault-fundamentals -name '*.log.zst' 2>/dev/null" | sort; }
block() {  # block LAB N...: the lab's Nth `bash` blocks; LANG:N:PATH (+PATH appends) writes its Nth LANG file there
  f="$1"; shift
  python3 -B - "$labs/$f" "$s" "$@" <<'EOF'
import re, sys
text, user = open(sys.argv[1]).read(), sys.argv[2]
fences = re.findall(r"^```(\w+)\n(.*?)^```$", text, re.S | re.M)
for tok in sys.argv[3:]:
    if ":" not in tok:
        sys.stdout.write([c for lang, c in fences if lang == "bash"][int(tok) - 1])
        continue
    lang, n, path = tok.split(":", 2)
    body = [c for l, c in fences if l == lang][int(n) - 1].replace("studentXX", user)
    op = ">>" if path.startswith("+") else ">"
    path = path.lstrip("+")
    sys.stdout.write(f"mkdir -p {path.rsplit('/', 1)[0] if '/' in path else '.'} && cat {op} {path} <<'LABFILE'\n{body}LABFILE\n")
EOF
}
run_and_read() {
  before="$(logs)"
  as "cd ~/lab/vault-fundamentals; $2" 2>&1
  end=$(( $(date +%s) + 240 ))
  while [ "$(logs | grep -vxF -e "$before" -e '' | wc -l)" -lt "$1" ] && [ "$(date +%s)" -lt "$end" ]; do sleep 3; done
  sleep 3
  for f in $(logs | grep -vxF -e "$before" -e ''); do
    podman exec workshop_forge cat "$f" | python3 -B -c 'import compression.zstd as z,sys; sys.stdout.write(z.decompress(sys.stdin.buffer.read()).decode())'
  done; }
fp() { as "export BAO_NAMESPACE=students/\$USER; printf %s \"\$(bao kv get -field=$1 team/$2)\" | sha256sum | cut -c1-12"; }
page() { as 'curl -s http://app-host:8080/$USER/'; }
wait_page() {  # wait_page TEXT SECONDS
  end=$(( $(date +%s) + $2 ))
  until p="$(page)"; echo "$p" | grep -q "$1" || [ "$(date +%s)" -gt "$end" ]; do sleep 3; done
  echo "$p"; }

echo "== reset $s"
api DELETE "/repos/$s/vault-fundamentals" >/dev/null
as 'rm -rf ~/lab/vault-fundamentals; export BAO_NAMESPACE=students/$USER
    bao delete auth/jwt-ci/role/deliver-main; bao policy delete app-deliver' >/dev/null 2>&1
# The terminal already signed git and curl in with the student's own token
# (~/.git-credentials, ~/.netrc: remediation T2.1c).
as 'test -s ~/.netrc' || { echo "FAIL: $s has no ~/.netrc (the terminal's token step)"; exit 1; }
as 'git config --global user.name "$USER"; git config --global user.email "$USER@dojo.test"' >/dev/null
ok "fork and clone (Lab 8)" 'curl -sf --netrc -H "Content-Type: application/json" -d "{}" http://git-server:3000/api/v1/repos/platform-team/vault-fundamentals/forks >/dev/null &&
    git clone -q http://git-server:3000/$USER/vault-fundamentals.git ~/lab/vault-fundamentals'

echo "== lab 10: deploy with a delivered secret ID"
out="$(as "$(block lab10.md 1 2 3 hcl:1:policies/app-deliver.hcl 4 5 6 7 8 9 hcl:2:app/agent.hcl sh:1:app/start.sh python:1:app/app.py)" 2>&1)"
check "the strict role" "$out" 'Data written to: auth/approle/role/app'
check "the deliverer's policy" "$out" 'Uploaded policy: app-deliver'
check "the deliverer can't read team/app" "$out" 'preflight capability check returned 403'
check "nor get an unwrapped secret ID" "$out" 'permission denied'
check "the wrapper's creation_path" "$out" 'auth/approle/role/app/secret-id'
check "unwrapped once" "$out" 'unwrapped: got a secret ID'
check "a second unwrap fails" "$out" 'wrapping token is not valid or does not exist'
check "the first login gets app-read" "$out" '"app-read"'
check "the second login is refused" "$out" 'invalid role or secret ID'
check "the CI role" "$out" 'Data written to: auth/jwt-ci/role/deliver-main'
ok "the role ID is in the repo" 'test -s ~/lab/vault-fundamentals/app/role-id'

log="$(run_and_read 1 "export BAO_NAMESPACE=students/\$USER; $(block lab10.md 10 yaml:1:.forgejo/workflows/deploy.yml 11)")"
check "the deliverer can't read team/app" "$log" 'permission denied for the deliverer, as it should be'
check "the wrapper's lookup is in the log" "$log" '"creation_path": "auth/approle/role/app/secret-id"'
check "the deploy job deployed" "$log" '"state": "running"'
lacks "no wrapping token in the job log" "$log" '"wrapping_token"'
p="$(wait_page 'API_KEY fingerprint' 30)"
check "the delivered file is gone" "$p" 'delivered secret-id file: gone'
check "the app has the vault's api_key" "$p" "API_KEY fingerprint: $(fp api_key app)"
out="$(as "export BAO_NAMESPACE=students/\$USER; $(block lab10.md 13)" 2>&1)"
check "no secret ID left" "$out" 'No value found'
check "the audit shows the mint, by app-deliver" "$out" '"app-deliver"'
check "the audit shows the login" "$out" 'auth/approle/login'

log="$(run_and_read 1 "$(block lab10.md 14)")"
check "a branch gets no secret ID" "$log" 'does not match any associated bound claim values'
ok "back to main" "cd ~/lab/vault-fundamentals && $(block lab10.md 15)"

out="$(as "$(block lab10.md 16)" 2>&1)"
check "the app restarted" "$out" 'app-host will start me again'
check "and has no secrets after it" "$out" 'secrets: none'
log="$(run_and_read 1 "export BAO_NAMESPACE=students/\$USER; $(block lab10.md 17)")"
check "the redeploy ran" "$log" '"state": "running"'
p="$(wait_page 'API_KEY fingerprint' 30)"
check "a new deploy brings the secrets back" "$p" "API_KEY fingerprint: $(fp api_key app)"

[ "$failed" -eq 0 ] && echo "PASS: lab 10" || echo "FAIL: lab 10"
exit "$failed"
