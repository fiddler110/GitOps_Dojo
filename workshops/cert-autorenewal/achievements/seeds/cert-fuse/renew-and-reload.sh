#!/bin/sh
# Renewal script skeleton for Lab 4 — attempt renewal with your ACME client
# of choice, and copy the result into your own subdirectory of the shared
# demo-app volume. Copying a changed cert/key there is the whole reload
# story: demo-app watches that volume and runs `nginx -s reload` itself the
# moment either file changes (see workshops/cert-autorenewal/compose/demo-app/
# entrypoint.sh) — this script never needs to touch nginx directly.
#
# Run it from here (sh ~/lab/cert-fuse/renew-and-reload.sh). Pick ONE of
# the two blocks below (delete the other), then wire it into cron through
# renew.cron — see Lab 4 for the shape of the line.
set -eu

YOUR_STUDENT_ID="{user}"
DEST="/srv/webroot/${YOUR_STUDENT_ID}/certs"

mkdir -p "${DEST}"

# --- Option A: certbot -------------------------------------------------
# `certbot renew` only actually renews a cert within its renewal window
# (30 days before expiry, by default) — but that's longer than this whole
# certificate's lifetime, so in this lab every run renews, same as
# production use once a cert is genuinely close to expiry. Needs the same
# --config-dir/--work-dir/--logs-dir as Lab 2's issuance (certbot has
# nothing to renew in the system-wide /etc/letsencrypt you never used),
# and its own REQUESTS_CA_BUNDLE export since cron runs this without your
# interactive shell's environment.
#
# export REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt
# certbot renew \
#   --config-dir "$HOME/certbot/config" --work-dir "$HOME/certbot/work" --logs-dir "$HOME/certbot/logs" \
#   --no-random-sleep-on-renew \
#   --deploy-hook "cp -f $HOME/certbot/config/live/${YOUR_STUDENT_ID}.certs.dojo.test/fullchain.pem ${DEST}/fullchain.pem && cp -f $HOME/certbot/config/live/${YOUR_STUDENT_ID}.certs.dojo.test/privkey.pem ${DEST}/privkey.pem"
#
# --no-random-sleep-on-renew turns off certbot's default 0-8min random delay
# before an unattended renewal actually runs (real thundering-herd
# protection for Let's Encrypt at Internet scale) — without it, cron firing
# every minute could still sit idle past this cert's whole 5-10 minute
# lifetime before renewing anything.

# --- Option B: acme.sh ---------------------------------------------------
# acme.sh's own cron entry (installed by --install-cert below) already
# calls this same renew-and-install step; this line is what you'd also run
# by hand to test it before trusting the cron job.
#
# acme.sh --renew -d "${YOUR_STUDENT_ID}.certs.dojo.test" --server https://step-ca:9443/acme/acme/directory
# acme.sh --install-cert -d "${YOUR_STUDENT_ID}.certs.dojo.test" \
#   --cert-file      "${DEST}/cert.pem" \
#   --key-file       "${DEST}/privkey.pem" \
#   --fullchain-file "${DEST}/fullchain.pem"
