#!/bin/sh
# runner-pool on the real stack (vault-fundamentals T3.9), from the repo root
# with a workshop using the module up:
#   sh modules/runner-pool/tests/pool.sh
# Checks: the warm pool registers; two jobs running at once can't see each
# other's processes or files; each runner is removed after its job, with its
# files; a burst scales up to the max and every job finishes; the panel's API
# is facilitator-only and its POSTs need the CSRF header; Manual - / + work.
# Creates repos pool-a, pool-b, pool-burst-N in the workshop's org (removed at
# the end). Needs python3 >= 3.14 on the host (job logs are zstd). Exits 1 on
# any failure.
set -u
set -a; . engine/.env; set +a
[ ! -r engine/.generated/upstream-tokens.env ] || { set -a; . engine/.generated/upstream-tokens.env; set +a; }  # per-upstream tokens (FIND-16)
ORG="${FORGEJO_ORG:-training}"
[ -f "workshops/${WORKSHOP:-vault-fundamentals}/workshop.env" ] && ORG="$(sed -n 's/^FORGEJO_ORG=//p' "workshops/${WORKSHOP:-vault-fundamentals}/workshop.env")"
failed=0
ok()   { echo "  ok:   $1"; }
fail() { echo "  FAIL: $1"; failed=1; }
api() { # api METHOD PATH [JSON]: Forgejo admin API, from the terminal container
  podman exec workshop_terminal curl -s -u "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$1" "http://git-server:3000/api/v1$2" ${3:+-d "$3"}; }
panel() { # panel METHOD PATH USER [JSON] [CSRF]: the controller, as the gateway would call it
  podman exec workshop_terminal curl -s -o /dev/null -w '%{http_code}' -X "$1" \
    -H "X-Gateway-Token: ${GATEWAY_TOKEN_RUNNER_CONTROLLER}" -H "X-Auth-User: $3" -H 'Content-Type: application/json' \
    ${5:+-H "X-Requested-With: $5"} ${4:+-d "$4"} "http://runner-controller:8080$2"; }
state() { podman exec workshop_terminal curl -s -H "X-Gateway-Token: ${GATEWAY_TOKEN_RUNNER_CONTROLLER}" \
    -H "X-Auth-User: ${FACILITATOR_USERNAME}" http://runner-controller:8080/api/state; }
field() { python3 -B -c "import json,sys; d=json.load(sys.stdin); print($1)"; }
job_logs() { # job_logs REPO: every archived job log of ORG/REPO, decompressed
  for f in $(podman exec workshop_forge sh -c "find /data/gitea/actions_log/$ORG/$1 -name '*.log.zst' 2>/dev/null"); do
    podman exec workshop_forge cat "$f" | python3 -B -c 'import compression.zstd as z,sys; sys.stdout.write(z.decompress(sys.stdin.buffer.read()).decode())'
  done; }
push_workflow() { # push_workflow REPO FILE < workflow
  b64="$(base64 -w0)"
  api POST "/orgs/$ORG/repos" "{\"name\":\"$1\",\"auto_init\":true,\"default_branch\":\"main\"}" >/dev/null
  api POST "/repos/$ORG/$1/contents/.forgejo/workflows/$2" "{\"content\":\"$b64\",\"branch\":\"main\",\"message\":\"test\"}" >/dev/null; }
wait_logs() { # wait_logs REPO N SECONDS: until REPO has N archived job logs
  end=$(( $(date +%s) + $3 ))
  while [ "$(podman exec workshop_forge sh -c "find /data/gitea/actions_log/$ORG/$1 -name '*.log.zst' 2>/dev/null | wc -l")" -lt "$2" ]; do
    [ "$(date +%s)" -ge "$end" ] && return 1; sleep 3; done; }
cleanup() { for r in pool-a pool-b $(seq -f 'pool-burst-%g' 1 8); do api DELETE "/repos/$ORG/$r" >/dev/null; done; }
cleanup

echo "== warm pool"
min="$(state | field 'd["min_idle"]')"
end=$(( $(date +%s) + 60 ))
until [ "$(state | field 'sum(1 for r in d["runners"] if r["state"]=="idle")')" -ge "$min" ] || [ "$(date +%s)" -ge "$end" ]; do sleep 2; done
idle="$(state | field 'sum(1 for r in d["runners"] if r["state"]=="idle")')"
[ "$idle" -ge "$min" ] && ok "$idle idle runners (min $min)" || fail "only $idle idle runners, min $min"
regs="$(api GET '/admin/actions/runners?limit=100' | field 'len([r for r in (d.get("runners", d) if isinstance(d, dict) else d) if r["name"].startswith("pool-")])')"
[ "$regs" -ge "$min" ] && ok "$regs registered in Forgejo" || fail "$regs registered in Forgejo"

echo "== panel API: facilitator only, CSRF header on POST"
[ "$(podman exec workshop_terminal curl -s -o /dev/null -w '%{http_code}' http://runner-controller:8080/api/state)" = 403 ] \
  && ok "no token: 403" || fail "no token isn't 403"
[ "$(panel GET /api/state student01)" = 403 ] && ok "student: 403" || fail "student isn't 403"
[ "$(panel GET /api/state "$FACILITATOR_USERNAME")" = 200 ] && ok "facilitator: 200" || fail "facilitator isn't 200"
[ "$(panel POST /api/mode "$FACILITATOR_USERNAME" '{"mode":"manual"}')" = 403 ] && ok "POST without X-Requested-With: 403" \
  || fail "POST without X-Requested-With isn't 403"
[ "$(panel POST /api/mode student01 '{"mode":"manual"}' dojo-runners)" = 403 ] && ok "student POST: 403" || fail "student POST isn't 403"

echo "== two jobs at once can't see each other"
spy() { cat <<'EOF'
name: spy
on: [push]
jobs:
  spy:
    runs-on: host
    steps:
      - run: |
          me="${GITHUB_REPOSITORY#*/}"; other=$(echo "$me" | sed 's/^pool-a$/pool-b/;t;s/^pool-b$/pool-a/')
          echo "S3CRET-$other" > "$TMPDIR/pattern"
          echo "PLANT: user=$(id -un) home=$HOME tmp=$TMPDIR umask=$(umask)"
          echo "S3CRET-$me" > planted.txt; echo "S3CRET-$me" > "$HOME/planted.txt"; echo "S3CRET-$me" > "/tmp/planted-$me.txt"
          sh -c "sleep 40; : S3CRET-$me" &
          sleep 15
          echo "PROBE procs=$(ls -d /proc/[0-9]* | wc -l) other_cmdline=$(cat /proc/[0-9]*/cmdline 2>/dev/null | tr '\0' ' ' | grep -c -F -f "$TMPDIR/pattern")"
          echo "PROBE other_files=$(grep -rlsF -f "$TMPDIR/pattern" /home /tmp /data 2>/dev/null | grep -v "^$TMPDIR/" | wc -l)"
          echo "PROBE bao=$(command -v bao) sops=$(command -v sops)"
          wait
EOF
}
spy | push_workflow pool-a spy.yml
spy | push_workflow pool-b spy.yml
sleep 10
busy="$(state | field 'sum(1 for r in d["runners"] if r["state"]=="busy")')"
[ "$busy" -ge 2 ] && ok "$busy runners busy at once" || fail "$busy runners busy (want 2)"
podman exec workshop_runner_pool ps -o user,rss,args | grep -E 'forgejo-runner|sleep' | head -6
if wait_logs pool-a 1 180 && wait_logs pool-b 1 60; then
  for r in pool-a pool-b; do
    probe="$(job_logs "$r" | grep -E 'PROBE|PLANT' | sed 's/^.*\(PROBE\|PLANT\)/\1/')"
    echo "$probe" | sed "s/^/    $r: /"
    echo "$probe" | grep -q 'other_cmdline=0' && echo "$probe" | grep -q 'other_files=0' \
      && ok "$r saw nothing of the other job" || fail "$r saw the other job"
    echo "$probe" | grep -q 'bao=/usr/local/bin/bao sops=/usr/local/bin/sops' && ok "$r has bao and sops" || fail "$r lacks bao/sops"
  done
else fail "the spy jobs didn't finish in time"; fi
sleep 5
left="$(podman exec workshop_runner_pool sh -c 'ls /tmp | grep -c planted; true')"
[ "$left" = 0 ] && ok "no job files left in /tmp" || fail "$left job files left in /tmp"

echo "== burst: 8 jobs at once"
max="$(state | field 'd["max"]')"
quick() { printf 'name: quick\non: [push]\njobs:\n  q:\n    runs-on: host\n    steps:\n      - run: sleep 20; echo QUICK-DONE\n'; }
for i in $(seq 1 8); do quick | push_workflow "pool-burst-$i" quick.yml & done; wait
peak=0; end=$(( $(date +%s) + 60 ))
while [ "$(date +%s)" -lt "$end" ]; do
  n="$(state | field 'd["alive"]')"; [ "$n" -gt "$peak" ] && peak="$n"; sleep 2; done
[ "$peak" -eq "$max" ] && ok "scaled up to the max ($peak)" || fail "peak $peak runners, max $max"
done_n=0
for i in $(seq 1 8); do wait_logs "pool-burst-$i" 1 240 && job_logs "pool-burst-$i" | grep -q QUICK-DONE && done_n=$((done_n + 1)); done
[ "$done_n" = 8 ] && ok "all 8 jobs finished" || fail "$done_n of 8 jobs finished"
mem="$(podman stats --no-stream --format '{{.MemUsage}}' workshop_runner_pool)"
echo "    pool memory now: $mem"

echo "== Manual: - / +"
[ "$(panel POST /api/mode "$FACILITATOR_USERNAME" '{"mode":"manual"}' dojo-runners)" = 200 ] && ok "switched to Manual" || fail "switch to Manual"
sleep 4
a0="$(state | field 'd["alive"]')"
max="$(state | field 'd["max"]')"
# Take one away first: with few students the pool may already be at the max.
[ "$(panel POST /api/scale "$FACILITATOR_USERNAME" '{"delta":-1}' dojo-runners)" = 200 ] && ok "-" || fail "- refused"
sleep 5
a1="$(state | field 'd["alive"]')"
[ "$a1" -eq $((a0 - 1)) ] && ok "one fewer runner ($a0 -> $a1)" || fail "runners $a0 -> $a1 after -"
[ "$(panel POST /api/scale "$FACILITATOR_USERNAME" '{"delta":1}' dojo-runners)" = 200 ] && ok "+" || fail "+ refused"
sleep 8
a2="$(state | field 'd["alive"]')"
[ "$a2" -eq "$a0" ] && ok "back to $a0" || fail "runners $a1 -> $a2 after +"
if [ "$a2" -ge "$max" ]; then
  [ "$(panel POST /api/scale "$FACILITATOR_USERNAME" '{"delta":1}' dojo-runners)" = 409 ] && ok "+ at the max ($max) refused" || fail "+ at the max not refused"
fi
panel POST /api/mode "$FACILITATOR_USERNAME" '{"mode":"auto"}' dojo-runners >/dev/null

echo "== runner users match live runners"
users="$(podman exec workshop_runner_pool sh -c 'getent passwd | grep -c "^pool-"; true')"
alive="$(state | field 'd["alive"]')"
[ "$users" -le "$alive" ] && ok "$users runner users for $alive live runners" || fail "$users runner users for $alive live runners"

cleanup
[ "$failed" = 0 ] && echo PASS || { echo FAIL; exit 1; }
