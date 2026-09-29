# Shared helpers for the per-lab test scripts (lab_N.sh), sourced with `.` (POSIX sh). Run the scripts from the repo
# root with the stack up: sh workshops/vault-fundamentals/tests/lab_8.sh [student03]. The first argument (default
# student03) is the student account the lab's steps run as. Each script resets what it leaves behind, and replays
# any earlier lab it depends on quietly, so it runs alone and can run again.
s="${1:-student03}"; other=student01
set -a; . engine/.env; set +a
labs=workshops/vault-fundamentals/content/lab
failed=0

# as CMD: run CMD in the student's login shell in the terminal container (stdin passes through).
as() { podman exec -i workshop_terminal su - "$s" -c "$1"; }
# ok NAME CMD: CMD must succeed. has/lacks NAME CMD TEXT: CMD's output must contain / not contain TEXT.
ok()   { if out="$(as "$2" 2>&1)"; then echo "  ok:   $1"; else echo "  FAIL: $1: $(echo "$out" | tail -3)"; failed=1; fi; }
has()  { out="$(as "$2" 2>&1)"; case "$out" in *"$3"*) echo "  ok:   $1" ;; *) echo "  FAIL: $1: $(echo "$out" | tail -3)"; failed=1 ;; esac; }
lacks() { out="$(as "$2" 2>&1)"; case "$out" in *"$3"*) echo "  FAIL: $1: $(echo "$out" | tail -3)"; failed=1 ;; *) echo "  ok:   $1" ;; esac; }
# check NAME OUTPUT TEXT / absent NAME OUTPUT TEXT: the same on output already captured.
check() { case "$2" in *"$3"*) echo "  ok:   $1" ;; *) echo "  FAIL: $1 (no '$3')"; echo "$2" | tail -8 | sed 's/^/        /'; failed=1 ;; esac; }
absent() { case "$2" in *"$3"*) echo "  FAIL: $1 ('$3' is there)"; failed=1 ;; *) echo "  ok:   $1" ;; esac; }
finish() { [ "$failed" = 0 ] && echo "PASS: $1" || { echo "FAIL: $1"; exit 1; }; }

# The Forgejo admin API, and the student's job logs (compressed; python3 >= 3.14 on the host reads them).
api() { podman exec workshop_terminal curl -s -u "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$1" "http://git-server:3000/api/v1$2" ${3:+-d "$3"}; }
logs() { podman exec workshop_forge sh -c "find /data/gitea/actions_log/$s/vault-fundamentals -name '*.log.zst' 2>/dev/null" | sort; }
new_logs() {  # new_logs BEFORE N: wait for N job logs not in BEFORE, print them decompressed
  end=$(( $(date +%s) + 240 ))
  while [ "$(logs | grep -vxF -e "$1" -e '' | wc -l)" -lt "$2" ] && [ "$(date +%s)" -lt "$end" ]; do sleep 3; done
  sleep 3  # the last lines of a finished job reach the archive a moment later
  for f in $(logs | grep -vxF -e "$1" -e ''); do
    podman exec workshop_forge cat "$f" | python3 -B -c 'import compression.zstd as z,sys; sys.stdout.write(z.decompress(sys.stdin.buffer.read()).decode())'
  done; }
# push_and_read N CMD: run CMD (a push) in the clone, wait for N new job logs, print them.
push_and_read() {
  before="$(logs)"
  ok "push: $2" "cd ~/lab/vault-fundamentals && $2" >&2
  new_logs "$before" "$1"; }
# run_and_read N SCRIPT: run SCRIPT in the clone (it pushes), print its output, then N new job logs.
run_and_read() {
  before="$(logs)"
  as "cd ~/lab/vault-fundamentals; $2" 2>&1
  new_logs "$before" "$1"; }
# block LAB N...: the lab's Nth `bash` blocks; LANG:N:PATH (+PATH appends) writes its Nth LANG file there.
block() {
  f="$1"; shift
  python3 -B - "$labs/$f" "$s" "$@" <<'PY'
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
PY
}
fp() { as "export BAO_NAMESPACE=students/\$USER; printf %s \"\$(bao kv get -field=$1 team/$2)\" | sha256sum | cut -c1-12"; }
page() { as 'curl -s http://app-host:8080/$USER/'; }
wait_page() {  # wait_page TEXT SECONDS
  end=$(( $(date +%s) + $2 ))
  until p="$(page)"; echo "$p" | grep -q "$1" || [ "$(date +%s)" -gt "$end" ]; do sleep 3; done
  echo "$p"; }

git_identity() { as 'git config --global user.name "$USER"; git config --global user.email "$USER@dojo.test"' >/dev/null; }
# The terminal signs git and curl in with the student's own token (~/.git-credentials, ~/.netrc).
need_netrc() { as 'test -s ~/.netrc' || { echo "FAIL: $s has no ~/.netrc (the terminal's token step)"; exit 1; }; }
# reset_repo: drop the student's fork and clone (what lab 8 makes).
reset_repo() { api DELETE "/repos/$s/vault-fundamentals" >/dev/null; as 'rm -rf ~/lab/vault-fundamentals' >/dev/null 2>&1; }
# fork_clone (quiet): lab 8's fork and clone, for labs that need the repository.
fork_clone() {
  need_netrc; git_identity
  ok "fork and clone (lab 8)" 'curl -sf --netrc -H "Content-Type: application/json" -d "{}" http://git-server:3000/api/v1/repos/platform-team/vault-fundamentals/forks >/dev/null &&
    git clone -q http://git-server:3000/$USER/vault-fundamentals.git ~/lab/vault-fundamentals'; }
# replay_lab11: lab 11's set-up and first deploy (jwt-platform, app/, deploy.yml); leaves its output in $out and $log.
replay_lab11() {
  out="$(as "$(block lab11.md 1 2 3)" 2>&1)"
  log="$(run_and_read 1 "export BAO_NAMESPACE=students/\$USER; $(block lab11.md 4 5 hcl:1:app/agent.hcl sh:1:app/start.sh python:1:app/app.py 6 yaml:1:.forgejo/workflows/deploy.yml 7)")"; }
# reset_labs_11_13: what labs 11-13 leave behind (they share one repository and one deployed app).
reset_labs_11_13() {
  reset_repo
  as 'rm -rf ~/lab/nightly-report.hcl; export BAO_NAMESPACE=students/$USER
    bao delete auth/jwt-platform/role/app; bao delete database/roles/app
    for p in db-app nightly-report; do bao policy delete $p; done' >/dev/null 2>&1; }
