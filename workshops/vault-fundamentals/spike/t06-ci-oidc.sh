#!/bin/sh
# P0 spike T0.6 (PLAN.md §10.4): can a Forgejo Actions job log in to OpenBao
# with its own OIDC token, bound to repo + branch? Throwaway. Run from the
# repo root with the stack up and OpenBao unsealed:
#   BAO_TOKEN=<root token> sh workshops/vault-fundamentals/spike/t06-ci-oidc.sh
# Needs podman. Writes the runner config (it holds a secret) to $SPIKE_DIR.
set -eu
SPIKE_DIR="${SPIKE_DIR:?Set SPIKE_DIR to a scratch directory}"
: "${BAO_TOKEN:?Set BAO_TOKEN}"
set -a; . engine/.env; set +a
ORG=platform-team; REPO=vault-fundamentals; OTHER=other-app; NS=students/student01
ISSUER="${PUBLIC_BASE_URL%/}/git/api/actions"

bao() { podman exec -i -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$BAO_TOKEN" -e BAO_NAMESPACE="$NS" workshop_openbao bao "$@"; }
api() { # api METHOD PATH [JSON]
  podman exec workshop_terminal curl -s -u "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$1" "http://git-server:3000/api/v1$2" ${3:+-d "$3"}; }

echo "== OpenBao: JWT auth in $NS trusting Forgejo Actions"
bao auth enable jwt 2>/dev/null || true
bao write auth/jwt/config jwks_url=http://git-server:3000/api/actions/.well-known/keys bound_issuer="$ISSUER" >/dev/null
bao secrets enable -path=kv kv-v2 2>/dev/null || true
sleep 2
bao kv put kv/ci/deploy api_key=ci-spike-value >/dev/null
printf 'path "kv/data/ci/*" { capabilities = ["read"] }\n' | bao policy write ci-read - >/dev/null
bao write auth/jwt/role/ci-main role_type=jwt user_claim=sub bound_audiences=openbao \
  bound_claims_type=string bound_claims="{\"repository\":\"$ORG/$REPO\",\"ref\":\"refs/heads/main\"}" \
  token_policies=ci-read token_ttl=5m >/dev/null 2>&1 || \
bao write auth/jwt/role/ci-main - >/dev/null <<EOF
{"role_type":"jwt","user_claim":"sub","bound_audiences":["openbao"],
 "bound_claims":{"repository":"$ORG/$REPO","ref":"refs/heads/main"},
 "token_policies":["ci-read"],"token_ttl":"5m"}
EOF
bao read -format=json auth/jwt/role/ci-main | grep -A3 '"bound_claims"'

echo "== Forgejo: register an instance-wide runner"
secret="$(head -c 20 /dev/urandom | od -An -tx1 | tr -d ' \n')"
uuid="$(podman exec -u 1000 workshop_forge forgejo forgejo-cli actions register \
  --config /data/gitea/conf/app.ini --name spike-runner --secret "$secret" \
  | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)"
mkdir -p "$SPIKE_DIR/runner"
cat > "$SPIKE_DIR/runner/config.yaml" <<EOF
log: {level: info, job_level: info}
runner: {capacity: 1, labels: ["host:host"]}
cache: {enabled: false}
container: {docker_host: "-"}
server:
  connections:
    spike: {url: "http://git-server:3000/", uuid: "$uuid", token: "$secret"}
EOF
podman rm -f spike_runner >/dev/null 2>&1 || true
podman run -d --name spike_runner --network engine_workshop_lab -v "$SPIKE_DIR/runner:/runner-config:Z" \
  data.forgejo.org/forgejo/runner:13 forgejo-runner daemon --config /runner-config/config.yaml >/dev/null

echo "== Forgejo: workflow that logs in with the job's OIDC token"
WF="$(cat <<'EOF'
name: vault-login
on: [push]
jobs:
  read-secret:
    runs-on: host
    enable-openid-connect: true
    steps:
      - name: log in to OpenBao with the job's own identity
        run: |
          set -eu
          echo "TOKEN URL (host part): $(printf '%s' "$ACTIONS_ID_TOKEN_REQUEST_URL" | cut -d? -f1)"
          # Forgejo builds this URL from its public ROOT_URL; inside the stack go to git-server directly.
          url=$(printf '%s' "$ACTIONS_ID_TOKEN_REQUEST_URL" | sed -E 's#^https?://[^/]+/git//git#http://git-server:3000/#; s#^https?://[^/]+/git/#http://git-server:3000/#')
          resp=$(wget -qO- --header "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" "$url&audience=openbao")
          jwt=$(printf '%s' "$resp" | sed -E 's/.*"value":"([^"]+)".*/\1/')
          payload=$(printf '%s' "$jwt" | cut -d. -f2 | tr '_-' '/+'); while [ $(( ${#payload} % 4 )) -ne 0 ]; do payload="$payload="; done
          echo "CLAIMS: $(printf '%s' "$payload" | base64 -d)"
          login=$(wget -qO- --header "X-Vault-Namespace: students/student01" --post-data "{\"role\":\"ci-main\",\"jwt\":\"$jwt\"}" http://openbao:8200/v1/auth/jwt/login 2>&1) || { echo "RESULT: LOGIN REFUSED $login"; exit 0; }
          tok=$(printf '%s' "$login" | sed -E 's/.*"client_token":"([^"]+)".*/\1/')
          val=$(wget -qO- --header "X-Vault-Token: $tok" --header "X-Vault-Namespace: students/student01" http://openbao:8200/v1/kv/data/ci/deploy | sed -E 's/.*"api_key":"([^"]+)".*/\1/')
          echo "RESULT: READ OK (length ${#val})"
EOF
)"
b64="$(printf '%s' "$WF" | base64 -w0)"
put_file() { # put_file REPO PATH BRANCH [NEW_BRANCH] -- create or update
  sha="$(api GET "/repos/$ORG/$1/contents/$2?ref=$3" | grep -oE '"sha":"[0-9a-f]{40}"' | head -1 | cut -d'"' -f4)"
  if [ -n "$sha" ] && [ -z "${4:-}" ]; then
    api PUT "/repos/$ORG/$1/contents/$2" "{\"content\":\"$b64\",\"branch\":\"$3\",\"sha\":\"$sha\",\"message\":\"spike: $2\"}"
  else
    api POST "/repos/$ORG/$1/contents/$2" "{\"content\":\"$b64\",\"branch\":\"$3\"${4:+,\"new_branch\":\"$4\"},\"message\":\"spike: $2\"}"
  fi | grep -oE '"commit":\{"url":"[^"]*' | grep -oE '[0-9a-f]{40}' | cut -c1-7; }
api POST "/orgs/$ORG/repos" "{\"name\":\"$OTHER\",\"auto_init\":true,\"default_branch\":\"main\"}" >/dev/null || true
for r in "$REPO" "$OTHER"; do api DELETE "/repos/$ORG/$r/branches/feature-x" >/dev/null; done
before="$(podman exec workshop_forge sh -c 'find /data/gitea/actions_log -name "*.log.zst" | wc -l')"
# main of the right repo (should read), a new branch of it (refused), main of another repo (refused)
echo "main:      $(put_file "$REPO" .forgejo/workflows/vault-login.yml main)"; sleep 5
echo "feature-x: $(put_file "$REPO" spike-branch-$(date +%s).txt main feature-x)"; sleep 5
echo "other-app: $(put_file "$OTHER" .forgejo/workflows/vault-login.yml main)"
echo "== waiting for 3 finished job logs"
timeout 180 sh -c "until [ \$(podman exec workshop_forge sh -c 'find /data/gitea/actions_log -name \"*.log.zst\" | wc -l') -ge $((before + 3)) ]; do sleep 5; done" || echo "timed out"
for log in $(podman exec workshop_forge sh -c 'find /data/gitea/actions_log -name "*.log.zst"' | sort -t/ -k8 -n | tail -3); do
  podman cp "workshop_forge:$log" "$SPIKE_DIR/job.log.zst"
  echo "-- $(echo "$log" | cut -d/ -f5-6)"
  python3 -B -c "import compression.zstd as z,sys;print(z.decompress(open(sys.argv[1],'rb').read()).decode())" "$SPIKE_DIR/job.log.zst" \
    | grep -E 'RESULT:|CLAIMS:|TOKEN URL|wget:' | cut -c30-420
done
