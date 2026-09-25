#!/bin/sh
# One-shot, run after the engine's bootstrap has created and seeded the
# workshop repo. Protects its main branch so the shared dojo.test zone only
# changes through the reviewed path (Part 2 of the labs):
#   - nobody pushes to main directly, not even the facilitator's account;
#   - a PR merges only once the "DNS Preview" check passed and
#     DNS_REQUIRED_APPROVALS people other than the author approved it.
# The PowerDNS side of the same rule is the dns-api gate (../dns-api/gate.py).
# Idempotent: replaces the rule on every start.
set -eu

api="http://git-server:3000/api/v1"
repo="${FORGEJO_ORG:?}/${FORGEJO_REPO:?}"
netrc="$(mktemp)"
trap 'rm -f "$netrc" "$netrc.json"' EXIT
chmod 600 "$netrc"
printf 'machine git-server\n\tlogin %s\n\tpassword %s\n' "${FORGEJO_ADMIN_USER:?}" "${FORGEJO_ADMIN_PASSWORD:?}" > "$netrc"

cat > "$netrc.json" <<JSON
{
  "rule_name": "main",
  "enable_push": false,
  "enable_status_check": true,
  "status_check_contexts": ["DNS Preview"],
  "required_approvals": ${DNS_REQUIRED_APPROVALS:-1},
  "block_on_rejected_reviews": true,
  "dismiss_stale_approvals": false
}
JSON

curl -sf --netrc-file "$netrc" -X DELETE "$api/repos/$repo/branch_protections/main" >/dev/null 2>&1 || true
curl -sf --netrc-file "$netrc" -X POST "$api/repos/$repo/branch_protections" \
  -H "Content-Type: application/json" -d @"$netrc.json" >/dev/null
echo "[dns-gates] protected main on $repo: PR + passing DNS Preview + ${DNS_REQUIRED_APPROVALS:-1} approval(s)"
