#!/bin/sh
# P0 spike T0.8 (PLAN.md §6.2 A, §10.5 e): two one-job runners side by side in
# one unprivileged container, one Linux user and namespace each; two jobs try
# to see each other's processes and files. Throwaway. From the repo root:
#   SPIKE_DIR=<scratch dir> sh workshops/vault-fundamentals/spike/t08-pool.sh
set -eu
SPIKE_DIR="${SPIKE_DIR:?}"; set -a; . engine/.env; set +a; ORG=platform-team
api() { podman exec workshop_terminal curl -s -u "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$1" "http://git-server:3000/api/v1$2" ${3:+-d "$3"}; }
# Start clean: drop every runner registration left from earlier spikes.
for id in $(api GET /admin/actions/runners | python3 -B -c 'import json,sys; print(" ".join(str(r["id"]) for r in json.load(sys.stdin)))'); do
  api DELETE "/admin/actions/runners/$id" >/dev/null; done
# ...and cancel every job still waiting (runners are instance-wide and would take them).
api GET "/admin/actions/runners/jobs" | python3 -B -c 'import json,sys; [print(j["repo_id"], j["run_id"]) for j in (json.load(sys.stdin) or [])]' | while read -r rid run; do
  full="$(api GET "/repositories/$rid" | python3 -B -c 'import json,sys; print(json.load(sys.stdin)["full_name"])')"
  api POST "/repos/$full/actions/runs/$run/cancel" >/dev/null; echo "cancelled waiting run $run in $full"; done
TS="$(date +%s)"; RA="pa-$TS"; RB="pb-$TS"
podman build -q -t gitopsdojo/spike-runner-pool workshops/vault-fundamentals/spike/pool >/dev/null
rm -rf "$SPIKE_DIR/pool"; mkdir -p "$SPIKE_DIR/pool"
for u in r1 r2; do
  reg="$(api POST /admin/actions/runners "{\"name\":\"pool-$u\",\"ephemeral\":true}")"
  uuid="$(printf '%s' "$reg" | python3 -B -c 'import json,sys; print(json.load(sys.stdin)["uuid"])')"
  token="$(printf '%s' "$reg" | python3 -B -c 'import json,sys; print(json.load(sys.stdin)["token"])')"
  cat > "$SPIKE_DIR/pool/$u.yaml" <<EOF
log: {level: info, job_level: info}
runner: {capacity: 1, labels: ["host:host"]}
cache: {enabled: false}
container: {docker_host: "-"}
server:
  connections:
    spike: {url: "http://git-server:3000/", uuid: "$uuid", token: "$token"}
EOF
done
podman rm -f spike_pool >/dev/null 2>&1 || true
podman run -d --name spike_pool --network engine_workshop_lab --pids-limit 512 --memory 1g \
  -v "$SPIKE_DIR/pool:/cfg:ro,Z" gitopsdojo/spike-runner-pool >/dev/null
sleep 3
WF="$(cat <<'EOF'
name: spy
on: [push]
jobs:
  spy:
    runs-on: host
    steps:
      - run: |
          me="${GITHUB_REPOSITORY#*/}"; other=$(echo "$me" | sed 's/^pa-/pb-/;t;s/^pb-/pa-/')
          echo "S3CRET-$other" > "$TMPDIR/pattern"
          echo "PLANT: me=$me user=$(id -un) uid=$(id -u) umask=$(umask) home=$HOME tmp=$TMPDIR pwd=$PWD"
          echo "S3CRET-$me" > planted.txt; echo "S3CRET-$me" > "$HOME/planted.txt"; echo "S3CRET-$me" > "/tmp/planted-$me.txt" 2>/dev/null || true
          sh -c "sleep 45; : S3CRET-$me" &
          sleep 12
          echo "PROBE: processes visible: $(ls -d /proc/[0-9]* | wc -l); other's secret in any cmdline: $(cat /proc/[0-9]*/cmdline 2>/dev/null | tr '\0' ' ' | grep -c -F -f "$TMPDIR/pattern")"
          echo "PROBE: /home: $(ls /home | tr '\n' ' ')"
          for f in /home/*/planted.txt /home/*/.cache/act/*/hostexecutor/planted.txt /tmp/planted-*.txt; do [ -e "$f" ] || continue; printf 'PROBE: %s -> %s\n' "$f" "$(cat "$f" 2>&1 | head -c 60)"; done
          echo "PROBE: other job's files readable anywhere: $(grep -rlsF -f "$TMPDIR/pattern" /home /tmp /data 2>/dev/null | grep -v "^$TMPDIR/" | tr '\n' ' ')"
          wait
EOF
)"
b64="$(printf '%s' "$WF" | base64 -w0)"
for r in "$RA" "$RB"; do
  api POST "/orgs/$ORG/repos" "{\"name\":\"$r\",\"auto_init\":true,\"default_branch\":\"main\"}" >/dev/null || true
  api POST "/repos/$ORG/$r/contents/.forgejo/workflows/spy-$(date +%s).yml" "{\"content\":\"$b64\",\"branch\":\"main\",\"message\":\"spike: spy\"}" >/dev/null
done
echo "== waiting for both runners to finish"
timeout 150 sh -c 'until [ "$(podman logs spike_pool 2>&1 | grep -c "finished and removed")" -ge 2 ]; do sleep 3; done' || echo "timed out"
podman logs spike_pool 2>&1 | grep -E '^\[supervise\]|task [0-9]+ repo is' | cut -c1-160
podman exec spike_pool sh -c 'echo "users left: $(ls /home | wc -l)"'
for task in $(podman logs spike_pool 2>&1 | grep -oE "task [0-9]+ repo is platform-team/p[ab]-$TS" | awk '{print $2 ":" $5}'); do
  id="${task%%:*}"; repo="${task#*:}"
  echo "-- $repo (task $id)"
  # Forgejo archives a finished job's log to this store a little later.
  log=""; n=0; while [ -z "$log" ] && [ $n -lt 30 ]; do
    log="$(podman exec workshop_forge find "/data/gitea/actions_log/$repo" -name "$id.log.zst" 2>/dev/null | head -1)"; n=$((n+1)); [ -n "$log" ] || sleep 3; done
  podman cp "workshop_forge:$log" "$SPIKE_DIR/job.log.zst"
  python3 -B -c "import compression.zstd as z,sys;print(z.decompress(open(sys.argv[1],'rb').read()).decode())" "$SPIKE_DIR/job.log.zst" \
    | grep -E 'PLANT:|PROBE:' | cut -c30-230
done
