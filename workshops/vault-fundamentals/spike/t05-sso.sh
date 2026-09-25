#!/bin/sh
# P0 spike T0.5 (PLAN.md §10.3, §10.7): the OpenBao UI signs in with Forgejo
# as the OIDC provider, through the SSO shim in OpenBao's network namespace
# (S23). Throwaway; T1.2/T1.3 turn it into openbao-setup. Run from the repo
# root with the stack up and OpenBao unsealed (spike/init-bao.sh):
#   BAO_TOKEN=<root token> [DOJO_ENV=home] sh workshops/vault-fundamentals/spike/t05-sso.sh
# Re-runnable: it replaces the Forgejo app and rewrites the OpenBao config.
set -eu
: "${BAO_TOKEN:?Set BAO_TOKEN}"
set -a; . engine/.env; [ -z "${DOJO_ENV:-}" ] || . "engine/.env.${DOJO_ENV}"; set +a
BASE="${PUBLIC_BASE_URL%/}"
CALLBACK="$BASE/ui/vault/auth/oidc/oidc/callback"

bao() { podman exec -i -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$BAO_TOKEN" workshop_openbao bao "$@"; }
api() { # api METHOD PATH [JSON]
  podman exec workshop_terminal curl -s -u "${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}" \
    -H 'Content-Type: application/json' -X "$1" "http://git-server:3000/api/v1$2" ${3:+-d "$3"}; }
json() { python3 -B -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

echo "== UI framing header (T0.4): frame-ancestors 'self'"
csp="$(podman exec workshop_openbao wget -S -q -O /dev/null http://127.0.0.1:8200/ui/ 2>&1 \
  | sed -n 's/^ *[Cc]ontent-[Ss]ecurity-[Pp]olicy: *//p' | head -1 | tr -d '\r')"
[ -n "$csp" ] || { echo "no CSP header on /ui/" >&2; exit 1; }
bao write sys/config/ui/headers/Content-Security-Policy \
  values="$(printf '%s' "$csp" | sed "s/frame-ancestors 'none'/frame-ancestors 'self'/")" >/dev/null

echo "== Forgejo: OAuth2 app for OpenBao (owned by $FORGEJO_ADMIN_USER)"
for id in $(api GET /user/applications/oauth2 | json "' '.join(str(a['id']) for a in d if a['name']=='OpenBao')"); do
  api DELETE "/user/applications/oauth2/$id" >/dev/null
done
app="$(api POST /user/applications/oauth2 \
  "{\"name\":\"OpenBao\",\"confidential_client\":true,\"redirect_uris\":[\"$CALLBACK\"]}")"
cid="$(printf '%s' "$app" | json "d['client_id']")"
csec="$(printf '%s' "$app" | json "d['client_secret']")"

echo "== OpenBao: OIDC auth method on Forgejo ($BASE/git)"
bao auth enable oidc 2>/dev/null || true
case "$BASE" in
  https://*) # The shim's own CA signs the public name inside OpenBao's namespace.
    podman exec workshop_openbao_sso_shim cat /data/caddy/pki/authorities/local/root.crt > "${TMPDIR:-/tmp}/shim-ca.pem"
    podman cp "${TMPDIR:-/tmp}/shim-ca.pem" workshop_openbao:/tmp/shim-ca.pem
    ca_arg="oidc_discovery_ca_pem=@/tmp/shim-ca.pem" ;;
  *) ca_arg="" ;;
esac
bao write auth/oidc/config oidc_discovery_url="$BASE/git" \
  oidc_client_id="$cid" oidc_client_secret="$csec" default_role=forgejo $ca_arg >/dev/null
bao write auth/oidc/role/forgejo role_type=oidc user_claim=preferred_username \
  oidc_scopes=openid,profile allowed_redirect_uris="$CALLBACK" token_ttl=8h >/dev/null
acc="$(bao auth list -format=json | json "d['oidc/']['accessor']")"

echo "== Policies and one entity per account"
printf 'path "sys/namespaces/*" { capabilities = ["read", "list"] }\npath "students/%s/*" { capabilities = ["read", "list"] }\n' \
  '{{identity.entity.name}}' | bao policy write student - >/dev/null
printf 'path "*" { capabilities = ["create", "read", "update", "delete", "list", "sudo"] }\n' \
  | bao policy write facilitator - >/dev/null
bao namespace create students >/dev/null 2>&1 || true
entity() { # entity NAME ALIAS POLICY
  bao write -format=json identity/entity name="$1" policies="$3" >/dev/null
  eid="$(bao read -format=json "identity/entity/name/$1" | json "d['data']['id']")"
  bao write identity/entity-alias name="$2" canonical_id="$eid" mount_accessor="$acc" >/dev/null 2>&1 || true
}
i=1
while [ "$i" -le "${STUDENT_COUNT:-3}" ]; do
  s="$(printf '%s%02d' "$STUDENT_PREFIX" "$i")"
  bao namespace create -namespace=students "$s" >/dev/null 2>&1 || true
  entity "$s" "$s" student; i=$((i + 1))
done
entity facilitator "$FORGEJO_ADMIN_USER" facilitator
bao read -format=json auth/oidc/config | json "d['data']['oidc_discovery_url']"
echo "done: sign in at $BASE/ui/vault/auth?with=oidc"
