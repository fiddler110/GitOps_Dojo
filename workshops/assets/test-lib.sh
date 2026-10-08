# Shared helpers for the live-stack test scripts (RV18). POSIX sh: source it from the repo root,
#   . workshops/assets/test-lib.sh
# then call load_env if the script needs .env (passwords, gateway tokens). The scripts run on the
# host with the stack up and reach it through `podman exec` (or docker: DOJO_CLI picks).
#
# Reporting: every check prints "  ok:   NAME" or "  FAIL: NAME ..." and a failure sets failed=1, so a run
# carries on and `finish` ends it with PASS or FAIL (exit 1). A harness with its own reporting (tofu-basics)
# may source this for the other helpers and define its own pass/fail after it.
#
# Students: `as CMD` runs CMD in the login shell of the student in $s (the vault-fundamentals labs' style);
# `as_user USER CMD...` names the account. Both go through `su -`, so the shell's start-up (credentials,
# tokens, the achievements hook) runs as it does for a real student.

: "${DOJO_CLI:=$(command -v podman >/dev/null 2>&1 && echo podman || echo docker)}"
: "${DOJO_TERMINAL:=workshop_terminal}"
: "${DOJO_FORGE:=workshop_forge}"
failed=0

# load_env: the operator's settings and secrets (dojo.toml, .env, the DOJO_ENV profile), plus the
# per-upstream gateway tokens a start writes (FIND-16), exported.
load_env() {
  eval "$(./engine/run.sh _operator-env ${DOJO_ENV:+--env "$DOJO_ENV"})"
  set -a
  [ ! -r engine/.generated/upstream-tokens.env ] || . engine/.generated/upstream-tokens.env
  set +a
}

# ---- reporting ------------------------------------------------------------------------------------------------
pass() { echo "  ok:   $1"; }
# fail NAME [DETAIL]: DETAIL (an output) is shown indented, its last 8 lines.
fail() {
  echo "  FAIL: $1"
  [ -z "${2:-}" ] || printf '%s\n' "$2" | tail -8 | sed 's/^/        /'
  failed=1
}
# result RC NAME: pass when RC is 0, e.g. `[ "$a" = "$b" ]; result $? "same entity"`.
result() { if [ "$1" = 0 ]; then pass "$2"; else fail "$2"; fi; }
# check NAME OUTPUT TEXT / absent NAME OUTPUT TEXT: OUTPUT (already captured) must contain / not contain TEXT.
check() { case "$2" in *"$3"*) pass "$1" ;; *) fail "$1 (no '$3')" "$2" ;; esac; }
absent() { case "$2" in *"$3"*) fail "$1 ('$3' is there)" ;; *) pass "$1" ;; esac; }
# finish [NAME]: PASS, or FAIL and exit 1.
finish() {
  if [ "$failed" = 0 ]; then echo "PASS${1:+: $1}"; else echo "FAIL${1:+: $1}"; exit 1; fi
}

# ---- students -------------------------------------------------------------------------------------------------
# as_user USER CMD...: CMD (the words joined) in USER's login shell. stdin is not passed through.
as_user() { _u="$1"; shift; "$DOJO_CLI" exec "$DOJO_TERMINAL" su - "$_u" -c "$*"; }
# as CMD: CMD as the student in $s, with stdin passed through (for heredocs).
as() { "$DOJO_CLI" exec -i "$DOJO_TERMINAL" su - "$s" -c "$1"; }
# ok NAME CMD: CMD (as $s) must succeed. has / lacks NAME CMD TEXT: its output must contain / not contain TEXT.
# The output of the last one is left in $out.
ok() { if out="$(as "$2" 2>&1)"; then pass "$1"; else fail "$1" "$(echo "$out" | tail -3)"; fi; }
has() { out="$(as "$2" 2>&1)"; case "$out" in *"$3"*) pass "$1" ;; *) fail "$1" "$(echo "$out" | tail -3)" ;; esac; }
lacks() { out="$(as "$2" 2>&1)"; case "$out" in *"$3"*) fail "$1" "$(echo "$out" | tail -3)" ;; *) pass "$1" ;; esac; }
# denied NAME CMD: CMD (as $s) must be refused ("permission denied" or a 403).
denied() {
  out="$(as "$2" 2>&1)"
  case "$out" in *"permission denied"*|*403*) pass "$1" ;; *) fail "$1" "$(echo "$out" | head -3)" ;; esac
}

# ---- Forgejo --------------------------------------------------------------------------------------------------
# api METHOD PATH [JSON]: the Forgejo admin API (needs load_env), from inside the lab network.
api() {
  "$DOJO_CLI" exec "$DOJO_TERMINAL" curl -s -u "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$1" "http://git-server:3000/api/v1$2" ${3:+-d "$3"}
}
# log_files OWNER/REPO: the archived Actions job logs of a repository, one path per line, sorted.
log_files() {
  "$DOJO_CLI" exec "$DOJO_FORGE" sh -c "find /data/gitea/actions_log/$1 -name '*.log.zst' 2>/dev/null" | sort
}
# read_log PATH: one archived job log, decompressed (zstd: python3 >= 3.14 on the host).
read_log() {
  "$DOJO_CLI" exec "$DOJO_FORGE" cat "$1" |
    python3 -B -c 'import compression.zstd as z,sys; sys.stdout.write(z.decompress(sys.stdin.buffer.read()).decode())'
}
# job_logs OWNER/REPO: every archived job log of the repository, decompressed.
job_logs() { for _f in $(log_files "$1"); do read_log "$_f"; done; }
# wait_logs OWNER/REPO N SECONDS: until the repository has N archived job logs; 1 if it never does.
wait_logs() {
  _end=$(( $(date +%s) + $3 ))
  while [ "$(log_files "$1" | grep -c .)" -lt "$2" ]; do
    [ "$(date +%s)" -lt "$_end" ] || return 1
    sleep 3
  done
}
# new_logs OWNER/REPO BEFORE N [SECONDS=240]: wait for N job logs not in BEFORE (an earlier log_files), print them.
new_logs() {
  _end=$(( $(date +%s) + ${4:-240} ))
  while [ "$(log_files "$1" | grep -vxF -e "$2" -e '' | wc -l)" -lt "$3" ] && [ "$(date +%s)" -lt "$_end" ]; do
    sleep 3
  done
  sleep 3  # the last lines of a finished job reach the archive a moment later
  for _f in $(log_files "$1" | grep -vxF -e "$2" -e ''); do read_log "$_f"; done
}

# ---- lab text -------------------------------------------------------------------------------------------------
# The scripts run the labs' own commands, so a lab that changes makes its test follow (or fail loudly).
# md_line FILE PREFIX: the first line of FILE starting with PREFIX; 1 if none.
md_line() {
  _l=$(awk -v p="$2" 'index($0, p) == 1 {print; exit}' "$1")
  [ -n "$_l" ] || return 1
  printf '%s' "$_l"
}
# md_range FILE START END: from the first line matching the START regex to the next matching END; 1 if none.
md_range() {
  _b=$(awk -v s="$2" -v e="$3" '$0 ~ s {on=1} on {print} on && $0 ~ e {exit}' "$1")
  [ -n "$_b" ] || return 1
  printf '%s' "$_b"
}
# md_blocks FILE USER TOKEN...: shell text from FILE's code fences, studentXX replaced by USER in file bodies.
# A TOKEN N is the Nth `bash` block as is; LANG:N:PATH writes the Nth LANG block to PATH (+PATH appends).
md_blocks() {
  python3 -B - "$@" <<'PY'
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
