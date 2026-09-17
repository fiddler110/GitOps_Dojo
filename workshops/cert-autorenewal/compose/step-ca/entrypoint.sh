#!/bin/sh
# Initializes the CA on first start (idempotent — skips if config/ca.json
# already exists, e.g. after a container restart within the same
# `docker compose up` session), shortens the ACME provisioner's cert
# lifetime so renewal is observable within a lab session, publishes the
# public root cert to a volume web-terminal can read (never the private
# keys under $STEPPATH/secrets), then runs step-ca in the foreground.
#
# Runs as root only for the resolv.conf line below, then drops to the
# unprivileged `step` user (via su-exec) for everything else, including
# serving — same effective privilege as the upstream image's own `USER
# step`, just deferred a few lines.
set -eu

export STEPPATH="${STEPPATH:-/home/step}"
export PASSWORD_FILE="${STEPPATH}/secrets/password"
export STEP_CA_PASSWORD="${STEP_CA_PASSWORD:-workshop-not-a-secret}"

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

su-exec step sh -c '
set -eu
mkdir -p "${STEPPATH}/secrets"
printf "%s" "${STEP_CA_PASSWORD}" > "${PASSWORD_FILE}"

if [ ! -f "${STEPPATH}/config/ca.json" ]; then
  step ca init \
    --name "GitOps Dojo Lab CA" \
    --dns "step-ca" \
    --dns "localhost" \
    --address ":9000" \
    --provisioner "admin" \
    --password-file "${PASSWORD_FILE}" \
    --provisioner-password-file "${PASSWORD_FILE}" \
    --deployment-type standalone \
    --acme

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

mkdir -p /pub
cp "${STEPPATH}/certs/root_ca.crt" /pub/root_ca.crt
# step ca init writes root_ca.crt 600; it is public material meant for
# every student to read (step ca bootstrap, certbot REQUESTS_CA_BUNDLE,
# acme.sh --ca-bundle all need it), so make it world-readable in the
# shared volume.
chmod 644 /pub/root_ca.crt
'

exec su-exec step step-ca "${STEPPATH}/config/ca.json" --password-file "${PASSWORD_FILE}"
