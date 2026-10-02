#!/bin/sh
# Initializes the CA on first start (idempotent — skips if config/ca.json
# already exists, e.g. after a container restart within the same
# `docker compose up` session), shortens the ACME provisioner's cert
# lifetime so renewal is observable within a lab session, publishes the
# public root cert to a volume web-terminal can read (never the private
# keys under $STEPPATH/secrets), then runs step-ca in the foreground.
#
# Passwords (remediation T3.3, FIND-09): the CA's key password is random,
# made at first start and kept only in its own volume (secrets/, mode 600).
# The `admin` JWK provisioner gets a second random password that is thrown
# away after init: nothing in the labs uses it, and step-ca hands every
# client that provisioner's encrypted key, so a known password would let
# anyone mint any certificate. The CA signs only names matching
# ACME_ALLOWED_DNS (default *.certs.dojo.test: one label under the zone),
# names under each account's own label (*.studentNN.certs.dojo.test, for the
# challenges' shop/www/api/members and the capstone's wildcard: a policy
# wildcard matches exactly one label), plus its own server names, step-ca
# and localhost. allowWildcardNames lets a certificate *name* be a wildcard
# (the capstone's *.studentNN.certs.dojo.test; step-ca refuses those by
# default); only dns-01 can prove one, and each account's DNS key reaches
# only its own _acme-challenge names, so nobody gets another's wildcard.
#
# Runs as root only for the resolv.conf line below, then drops to the
# unprivileged `step` user (via su-exec) for everything else, including
# serving — same effective privilege as the upstream image's own `USER
# step`, just deferred a few lines.
set -eu

export STEPPATH="${STEPPATH:-/home/step}"
export PASSWORD_FILE="${STEPPATH}/secrets/password"
export ACME_ALLOWED_DNS="${ACME_ALLOWED_DNS:-*.certs.dojo.test}"

# One more allowed pattern per account (same names as dns-seed makes): the
# account's own subtree, *.<account>.<zone>. Passed into the step block below
# as a JSON list.
zone="${ACME_ALLOWED_DNS#\*.}"
ACCOUNT_DNS="[]"
i=1
while [ "${i}" -le "${STUDENT_COUNT:-30}" ]; do
  ACCOUNT_DNS="$(printf '%s' "${ACCOUNT_DNS}" | jq -c --arg n "*.${STUDENT_PREFIX:-student}$(printf '%02d' "${i}").${zone}" '. + [$n]')"
  i=$((i + 1))
done
ACCOUNT_DNS="$(printf '%s' "${ACCOUNT_DNS}" | jq -c --arg n "*.${FACILITATOR_USERNAME:-root}.${zone}" '. + [$n]')"
export ACCOUNT_DNS

# step-ca validates ACME challenges (http-01 and dns-01) by looking up the
# target hostname itself, and needs to resolve names in the private
# certs.dojo.test zone that the container's default resolver doesn't know
# about. Compose's `dns:` key is the documented way to do this, but
# podman-compose (unlike docker compose) doesn't honor it — the container
# keeps its default resolv.conf regardless — so it's set directly here
# instead, which works under either compose implementation.
printf 'nameserver %s\n' "${DNS_SERVER_IP:-172.30.0.10}" > /etc/resolv.conf

# /pub (unlike /home/step) has no content in the base image at that path,
# so a brand-new named volume mounted there is created root-owned — chown
# it once, as root, before the `step` user needs to write into it below.
mkdir -p /pub
chown step:step /pub
# The checker's client certificate (below) goes in its own volume, shared with
# the achievements service only (never a student terminal).
mkdir -p /client
chown step:step /client

su-exec step sh -c '
set -eu
umask 077
mkdir -p "${STEPPATH}/secrets"
if [ ! -s "${PASSWORD_FILE}" ]; then
  head -c 32 /dev/urandom | base64 | tr -d "\n=" > "${PASSWORD_FILE}"
fi

if [ ! -f "${STEPPATH}/config/ca.json" ]; then
  prov_pw="$(mktemp)"
  head -c 32 /dev/urandom | base64 | tr -d "\n=" > "${prov_pw}"
  step ca init \
    --name "GitOps Dojo Lab CA" \
    --dns "step-ca" \
    --dns "localhost" \
    --address ":9443" \
    --provisioner "admin" \
    --password-file "${PASSWORD_FILE}" \
    --provisioner-password-file "${prov_pw}" \
    --deployment-type standalone \
    --acme
  rm -f "${prov_pw}"

  # Short-lived certs are the point of this workshop: a 5-10 minute
  # lifetime makes automated renewal (Lab 4) something students actually
  # watch happen, instead of a fact they are told about. Matched by
  # whatever renewal cadence Lab 4 has students configure.
  jq "(.authority.provisioners[] | select(.type == \"ACME\")).claims = {
        \"minTLSCertDuration\": \"5m\",
        \"maxTLSCertDuration\": \"10m\",
        \"defaultTLSCertDuration\": \"5m\"
      }" "${STEPPATH}/config/ca.json" > "${STEPPATH}/config/ca.json.tmp"
  mv "${STEPPATH}/config/ca.json.tmp" "${STEPPATH}/config/ca.json"
fi

# Listen on 9443, never 9000: the student terminal firewall drops outbound
# 9000-9099 and 9500-9899 (engine/web-terminal/entrypoint.sh, DOJO_ISOLATION).
# Set on every start, not just at init, so a ca.json persisted from an
# older run that still says :9000 is moved too.
if [ "$(jq -r .address "${STEPPATH}/config/ca.json")" != ":9443" ]; then
  jq ".address = \":9443\"" "${STEPPATH}/config/ca.json" > "${STEPPATH}/config/ca.json.tmp"
  mv "${STEPPATH}/config/ca.json.tmp" "${STEPPATH}/config/ca.json"
fi

# Only names under the lab zone, set on every start (so a ca.json from an
# older run gets it too). Self-hosted step-ca reads a policy only at the
# authority level (one on a provisioner is ignored); an ACME order for any
# other name is refused at new-order. Names of other students are kept out
# by per-student DNS keys for dns-01 (the dns-gate module).
jq --arg dns "${ACME_ALLOWED_DNS}" --argjson accounts "${ACCOUNT_DNS}" \
  ".authority.policy = {x509: {allow: {dns: ([\$dns, \"step-ca\", \"localhost\"] + \$accounts)},
                            allowWildcardNames: true}}
   | del(.authority.provisioners[].policy)" \
  "${STEPPATH}/config/ca.json" > "${STEPPATH}/config/ca.json.tmp"
mv "${STEPPATH}/config/ca.json.tmp" "${STEPPATH}/config/ca.json"

mkdir -p /pub
cp "${STEPPATH}/certs/root_ca.crt" /pub/root_ca.crt
# step ca init writes root_ca.crt 600; it is public material meant for
# every student to read (step ca bootstrap, certbot REQUESTS_CA_BUNDLE,
# acme.sh --ca-bundle all need it), so make it world-readable in the
# shared volume.
chmod 644 /pub/root_ca.crt

# A client certificate for the achievements checker, so it can test the
# mTLS site of a student (challenge c3: served_mtls) as a member would.
# Signed directly with the intermediate (no provisioner, so the ACME name
# policy above does not apply), for 30 days, and made again at every start.
# The achievements service runs with no capabilities, so it can only read
# files other users may read: the key is 644 inside a volume that only
# step-ca and achievements mount.
step certificate create "dojo-checker" /client/client.crt /client/client.key \
  --profile leaf --not-after 720h --bundle --force \
  --ca "${STEPPATH}/certs/intermediate_ca.crt" \
  --ca-key "${STEPPATH}/secrets/intermediate_ca_key" \
  --ca-password-file "${PASSWORD_FILE}" \
  --no-password --insecure >/dev/null
chmod 644 /client/client.crt /client/client.key
'

exec su-exec step step-ca "${STEPPATH}/config/ca.json" --password-file "${PASSWORD_FILE}"
