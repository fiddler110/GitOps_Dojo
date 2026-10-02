#!/bin/sh
# certbot --manual-auth-hook: sets the dns-01 TXT record through dns-api, so
# issuance and renewal need nobody to paste a value (Lab 5 step 2, automated).
#
# certbot runs it once per challenge, with:
#   CERTBOT_DOMAIN      the name being proved, without any "*." prefix
#                       (here {user}.certs.dojo.test)
#   CERTBOT_VALIDATION  the value the TXT record must hold
#
# Use it as:
#   certbot certonly --manual --preferred-challenges dns-01 \
#     --manual-auth-hook "sh $HOME/lab/cert-heist/dns-hook.sh" ...
#
# Cron starts it with almost none of your shell's environment, so the key is
# read from the file your terminal keeps it in when DNS_API_KEY isn't set.
set -eu

: "${DNS_API_KEY:=$(cat "$HOME/.config/dojo/dns-api-key")}"

# TODO 1: set the TXT record "_acme-challenge.$CERTBOT_DOMAIN." to
#         "$CERTBOT_VALIDATION" through dns-api (Lab 5's curl PATCH).
# TODO 2: wait until `dig @dns-server` shows the new value before exiting,
#         or the CA may look before the record is there.

echo "dns-hook.sh: not written yet" >&2
exit 1
