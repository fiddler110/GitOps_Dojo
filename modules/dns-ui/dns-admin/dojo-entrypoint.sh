#!/bin/sh
# Wraps the base image's own /opt/scenario/entrypoint.sh rather than
# replacing it: that script still does `flask db upgrade` and builds the
# final gunicorn command line (--timeout/--workers/--bind/--log-level from
# env) exactly as upstream intends. This script only does the three things
# that have to happen before gunicorn ever imports dojo_wsgi.py:
#
#   1. Turn the workshop's own env var names into the ones PowerDNS-Admin's
#      Setting/AppSettings machinery actually reads (see dojo_seed.py's
#      docstring for why the env vars, not a DB write, are what enforces
#      these).
#   2. Run migrations ourselves first, so the seed step below always has
#      the schema it needs. (The base entrypoint runs `flask db upgrade`
#      again right after this exec's into it -- harmless, it's a no-op the
#      second time.)
#   3. Seed the settings snapshot + the facilitator's Administrator account.
set -eu
cd /app

# PATH_PREFIX/PDNS API/GATEWAY_TOKEN/FACILITATOR_USERNAME come from the
# module's compose.yml. PDNS_API_URL there is the bare PowerDNS base
# (http://dns-server:8081); PowerDNS-Admin's own `pdns_api_url` setting
# expects that plus "/api" (it appends "/v1/servers/..." itself -- passing
# the base alone, or the base plus "/api/v1", both 404 a level deep or
# double up the path; this was found by testing the real API against a
# spike of the app, not by reading a doc).
case "${PDNS_API_URL:-}" in
    */) PDNS_API_URL="${PDNS_API_URL%/}" ;;
esac
export PDNS_API_URL="${PDNS_API_URL:-}/api"
export PDNS_API_KEY="${POWERDNS_API_KEY:-}"
export SIGNUP_ENABLED=False
export LOCAL_DB_ENABLED=False
export REMOTE_USER_ENABLED=True
export REMOTE_USER_LOGOUT_URL="${REMOTE_USER_LOGOUT_URL:-/admin}"
export FLASK_CONF=/app/dojo_config.py
# Random per start, shared by all workers (see dojo_config.py). Never logged.
DOJO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export DOJO_SECRET_KEY

flask db upgrade
python3 /app/dojo_seed.py

exec /opt/scenario/entrypoint.sh gunicorn dojo_wsgi:application
