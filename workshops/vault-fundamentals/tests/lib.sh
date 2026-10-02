# Shared helpers for the per-lab test scripts (lab_N.sh), sourced with `.` (POSIX sh). Run the scripts from the repo
# root with the stack up: sh workshops/vault-fundamentals/tests/lab_8.sh [student03]. The first argument (default
# student03) is the student account the lab's steps run as. Each script resets what it leaves behind, and replays
# any earlier lab it depends on quietly, so it runs alone and can run again.
s="${1:-student03}"; other=student01
. "$(dirname "$0")/../../assets/test-lib.sh"   # as, ok/has/lacks/check/absent/finish, api, job logs, md_blocks
load_env
labs=workshops/vault-fundamentals/content/lab

# The student's job logs in their fork.
logs() { log_files "$s/vault-fundamentals"; }
# push_and_read N CMD: run CMD (a push) in the clone, wait for N new job logs, print them.
push_and_read() {
  before="$(logs)"
  ok "push: $2" "cd ~/lab/vault-fundamentals && $2" >&2
  new_logs "$s/vault-fundamentals" "$before" "$1"; }
# run_and_read N SCRIPT: run SCRIPT in the clone (it pushes), print its output, then N new job logs.
run_and_read() {
  before="$(logs)"
  as "cd ~/lab/vault-fundamentals; $2" 2>&1
  new_logs "$s/vault-fundamentals" "$before" "$1"; }
# block LAB TOKEN...: the lab's code blocks as shell text (md_blocks in test-lib.sh says how).
block() { _lab="$1"; shift; md_blocks "$labs/$_lab" "$s" "$@"; }
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
