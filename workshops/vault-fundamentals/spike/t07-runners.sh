#!/bin/sh
# P0 spike T0.7 (PLAN.md §10.5 a-d): ephemeral one-job runners, what the
# Forgejo API reports about waiting jobs and runners, start-up time, memory.
# Throwaway. Run from the repo root with the stack up:
#   SPIKE_DIR=<scratch dir> sh workshops/vault-fundamentals/spike/t07-runners.sh
set -eu
SPIKE_DIR="${SPIKE_DIR:?Set SPIKE_DIR to a scratch directory}"
set -a; . engine/.env; set +a
ORG=platform-team; REPO=runner-test
api() { podman exec workshop_terminal curl -s -u "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$1" "http://git-server:3000/api/v1$2" ${3:+-d "$3"}; }
now() { date +%s.%N; }
jobs_waiting() { api GET "/admin/actions/runners/jobs?labels=host" | python3 -B -c 'import json,sys; j=json.load(sys.stdin) or []; print(len(j), [(x.get("id"), x.get("status"), x.get("name")) for x in j])'; }

podman rm -f spike_runner_shim >/dev/null 2>&1 || true; podman rm -f spike_runner spike_one >/dev/null 2>&1 || true

echo "== queue one job with no runner online"
WF="$(cat <<'EOF'
name: sleep
on: [push]
jobs:
  work:
    runs-on: host
    steps:
      - run: |
          echo "user=$(id -un) pid=$$ home=$HOME"
          i=0; while [ $i -lt 25 ]; do head -c 1048576 /dev/urandom | sha256sum >/dev/null; sleep 1; i=$((i+1)); done
          echo DONE
EOF
)"
api POST "/orgs/$ORG/repos" "{\"name\":\"$REPO\",\"auto_init\":true,\"default_branch\":\"main\"}" >/dev/null || true
b64="$(printf '%s' "$WF" | base64 -w0)"
api POST "/repos/$ORG/$REPO/contents/.forgejo/workflows/sleep-$(date +%s).yml" "{\"content\":\"$b64\",\"branch\":\"main\",\"message\":\"spike: queue a job\"}" >/dev/null
sleep 4
echo "jobs waiting: $(jobs_waiting)"

echo "== register an ephemeral runner through the API"
reg="$(api POST /admin/actions/runners '{"name":"eph-1","ephemeral":true,"description":"spike one-job runner"}')"
echo "register response keys: $(printf '%s' "$reg" | python3 -B -c 'import json,sys; print(sorted(json.load(sys.stdin)))')"
uuid="$(printf '%s' "$reg" | python3 -B -c 'import json,sys; print(json.load(sys.stdin)["uuid"])')"
token="$(printf '%s' "$reg" | python3 -B -c 'import json,sys; print(json.load(sys.stdin)["token"])')"
mkdir -p "$SPIKE_DIR/one"
cat > "$SPIKE_DIR/one/config.yaml" <<EOF
log: {level: info, job_level: info}
runner: {capacity: 1, labels: ["host:host"]}
cache: {enabled: false}
container: {docker_host: "-"}
server:
  connections:
    spike: {url: "http://git-server:3000/", uuid: "$uuid", token: "$token"}
EOF
api GET "/admin/actions/runners" | python3 -B -c 'import json,sys; d=json.load(sys.stdin); d=d.get("runners",d) if isinstance(d,dict) else d; [print("  runner", r["name"], r["status"], "ephemeral=%s" % r.get("ephemeral")) for r in d]'

echo "== start one-job runner"
t0="$(now)"
podman run -d --name spike_one --network engine_workshop_lab -v "$SPIKE_DIR/one:/runner-config:Z" \
  data.forgejo.org/forgejo/runner:13 forgejo-runner one-job --config /runner-config/config.yaml --wait >/dev/null
timeout 60 sh -c 'until podman logs spike_one 2>&1 | grep -q "task [0-9]* repo is"; do sleep 0.2; done' || true
t1="$(now)"
echo "container start -> job picked up: $(python3 -B -c "print(round($t1-$t0,1))") s"
sleep 8
echo "memory during the job: $(podman stats --no-stream --format '{{.MemUsage}}' spike_one)"
podman exec spike_one sh -c 'ps -o pid,user,rss,args | head -8' 2>/dev/null || true
timeout 90 sh -c 'while [ "$(podman inspect -f "{{.State.Running}}" spike_one)" = true ]; do sleep 1; done' || echo "still running after 90 s"
t2="$(now)"
echo "exited: $(podman inspect -f '{{.State.Running}} exit={{.State.ExitCode}}' spike_one); job start -> exit $(python3 -B -c "print(round($t2-$t1,1))") s"
podman logs spike_one 2>&1 | tail -4 | cut -c1-200
echo "jobs waiting now: $(jobs_waiting)"
echo "== runners after the job"
api GET "/admin/actions/runners" | python3 -B -c 'import json,sys; d=json.load(sys.stdin); d=d.get("runners",d) if isinstance(d,dict) else d; [print("  runner", r["name"], r["status"], "ephemeral=%s" % r.get("ephemeral")) for r in d]'
echo "== idle runner memory (no job): start a second one-job runner with nothing queued"
reg="$(api POST /admin/actions/runners '{"name":"eph-idle","ephemeral":true}')"
uuid="$(printf '%s' "$reg" | python3 -B -c 'import json,sys; print(json.load(sys.stdin)["uuid"])')"; token="$(printf '%s' "$reg" | python3 -B -c 'import json,sys; print(json.load(sys.stdin)["token"])')"
sed -e "s/uuid: \"[^\"]*\"/uuid: \"$uuid\"/" -e "s/token: \"[^\"]*\"/token: \"$token\"/" "$SPIKE_DIR/one/config.yaml" > "$SPIKE_DIR/one/idle.yaml"
podman rm -f spike_idle >/dev/null 2>&1 || true
podman run -d --name spike_idle --network engine_workshop_lab -v "$SPIKE_DIR/one:/runner-config:Z" \
  data.forgejo.org/forgejo/runner:13 forgejo-runner one-job --config /runner-config/idle.yaml --wait >/dev/null
sleep 10
echo "idle memory: $(podman stats --no-stream --format '{{.MemUsage}}' spike_idle)"
podman logs spike_idle 2>&1 | tail -2 | cut -c1-200
api GET "/admin/actions/runners" | python3 -B -c 'import json,sys; d=json.load(sys.stdin); d=d.get("runners",d) if isinstance(d,dict) else d; [print("  runner", r["name"], r["status"]) for r in d if r["name"].startswith("eph")]'
