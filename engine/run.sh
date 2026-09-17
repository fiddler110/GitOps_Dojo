#!/bin/sh
# Select and build a workshop dynamically.
#
# Usage:
#   ./run.sh <workshop-name>            # e.g. ./run.sh dns-as-code
#   ./run.sh <workshop-name> --test     # also spin up demo/test bot students
#   ./run.sh list                       # show available workshops
#   ./run.sh stop | teardown            # stop the stack, wipe all volumes
#
# What this does:
#   1. Loads account/secret/network settings from engine/.env (unchanged
#      from before — TTYD_*, STUDENT_*, FACILITATOR_*, FORGEJO_ADMIN_*,
#      PUBLIC_BASE_URL, LAB_HOST_IP, ports).
#   2. Loads workshop identity from workshops/<name>/workshop.env
#      (WORKSHOP_NAME, WORKSHOP_CONTENT_DIR, FORGEJO_ORG, FORGEJO_REPO,
#      COMPOSE_OVERLAY) — these override/extend whatever .env has, so a
#      workshop.env is always the source of truth for its own workshop.
#   3. Builds the base web-terminal image (tagged gitopsdojo/web-terminal:base)
#      so a workshop overlay's terminal Dockerfile can FROM it.
#   4. Runs `docker compose -f docker-compose.yml [-f <overlay>] up -d --build`.
#
# Editing engine/docker-compose.yml or the base web-terminal image is never
# required to add a workshop — see workshops/README.md.
set -eu

cd "$(dirname "$0")"

if [ "${1:-}" = "stop" ] || [ "${1:-}" = "teardown" ]; then
  exec ./scripts/teardown.sh
fi

if [ "${1:-}" = "" ] || [ "${1:-}" = "list" ]; then
  echo "Available workshops:"
  for d in ../workshops/*/; do
    name="$(basename "$d")"
    [ -f "${d}workshop.env" ] || continue
    title="$(sed -n 's/^WORKSHOP_NAME=//p' "${d}workshop.env" | head -1 | tr -d '"')"
    printf '  %-20s %s\n' "$name" "${title:-}"
  done
  echo
  echo "Usage: ./run.sh <workshop-name>"
  exit 0
fi

workshop="$1"
test_mode=0
if [ "${2:-}" != "" ]; then
  if [ "${2:-}" = "--test" ]; then
    test_mode=1
  else
    echo "Unrecognized argument: ${2}" >&2
    echo "Usage: ./run.sh <workshop-name> [--test]" >&2
    exit 1
  fi
fi

workshop_dir="../workshops/${workshop}"
workshop_env="${workshop_dir}/workshop.env"

if [ ! -f "$workshop_env" ]; then
  echo "No such workshop: ${workshop} (expected ${workshop_env})" >&2
  echo "Run './run.sh list' to see available workshops." >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo ".env not found — copy .env.example to .env and fill in account/secret values first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
# shellcheck disable=SC1091
. "$workshop_env"
set +a

# --test: spin up demo/test bot student accounts (see
# engine/web-terminal/bot-runner.sh and README.md's "Demo bots (--test)"
# section) -- three simulated students (an expert, an intermediate, and a
# terminal/git novice) that slowly, visibly work through the lab on
# testuserN/... branches, for demoing the workshop or exercising the
# facilitator dashboard without real students. Respects an explicit
# BOT_COUNT already set in .env; only supplies the default of 3 if that's
# unset, so --test is just a convenience on top of the same knob.
if [ "$test_mode" = "1" ]; then
  export BOT_COUNT="${BOT_COUNT:-3}"
  echo "Test mode: starting ${BOT_COUNT} demo bot student(s) (prefix: ${BOT_PREFIX:-testuser})."
fi

# Prefer docker if it's actually present and working; fall back to podman
# otherwise (same detection teardown.sh uses, so both scripts agree on which
# engine is in play).
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  build() { docker build "$@"; }
  compose() { docker compose "$@"; }
else
  build() { podman build "$@"; }
  compose() { podman-compose "$@"; }
fi

# web-terminal/Dockerfile's extension-preinstall step needs outbound HTTPS
# to Open VSX at BUILD time (not at runtime -- the running container has
# no internet route at all, see docker-compose.yml) to wget each pinned,
# checksum-verified .vsix. On a network with TLS inspection, that wget
# fails ("certificate ... not trusted") unless it trusts the inspecting
# proxy's CA. If CORP_CA_BUNDLE (or REQUESTS_CA_BUNDLE, already set on
# this shell for curl/pip/etc on a lot of corp laptops) points at a real
# file, pass it through as a build secret -- mounted only for that one RUN
# step, never written into the built image. Whatever combined CA bundle
# your shell already uses for other HTTPS tools is usually enough here
# too (verified against a real corp TLS-inspection proxy, not assumed).
# No effect on a network without TLS inspection.
corp_ca_bundle="${CORP_CA_BUNDLE:-${REQUESTS_CA_BUNDLE:-}}"
build_secret_args=""
if [ -n "$corp_ca_bundle" ] && [ -f "$corp_ca_bundle" ]; then
  echo "Using corporate CA bundle for the web-terminal build: ${corp_ca_bundle}"
  build_secret_args="--secret id=corp_ca_cert,src=${corp_ca_bundle}"
fi

echo "Building base web-terminal image (gitopsdojo/web-terminal:base)..."
# shellcheck disable=SC2086
build $build_secret_args -t gitopsdojo/web-terminal:base ./web-terminal

compose_args="-f docker-compose.yml"
if [ -n "${COMPOSE_OVERLAY:-}" ]; then
  compose_args="$compose_args -f ${COMPOSE_OVERLAY}"
fi

# Record which overlay (if any) this run used, so teardown.sh tears down
# with the exact same -f set instead of only ever seeing docker-compose.yml.
# Without this, `down` has no idea an overlay's extra services/volumes
# (e.g. dns-as-code's dns-server/runner-setup/forgejo-runner and
# dns_runner_config volume) ever existed, and can't respect their
# depends_on ordering or clean up their volumes.
echo "${COMPOSE_OVERLAY:-}" > .last-overlay

echo "Starting workshop '${workshop}' (${WORKSHOP_NAME:-$workshop})..."
# shellcheck disable=SC2086
compose $compose_args up -d --build
