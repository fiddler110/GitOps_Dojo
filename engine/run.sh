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
#   3. Builds the base web-terminal image (gitopsdojo/web-terminal:base), the
#      workshop's own terminal image if it has a compose/terminal/Dockerfile,
#      and the allocator/gateway images — but only the ones whose source
#      actually changed since the last build (see build_if_changed below);
#      an unchanged one is reused as-is instead of rebuilt. Any other
#      build: blocks the workshop's own overlay adds (e.g. dns-as-code's
#      forgejo-runner) go through the same change detection, one directory
#      hash per workshop (see compose_overlay_build_if_changed below).
#   4. Runs `docker compose -f docker-compose.yml [-f <overlay>] up -d`
#      (no --build — step 3 already brought every image Compose references
#      up to date).
#
# Editing engine/docker-compose.yml or the base web-terminal image is never
# required to add a workshop — see workshops/README.md.
set -eu

cd "$(dirname "$0")"

# One-time, interactive offer to wire up shell tab-completion (workshop
# names, list/stop/teardown, --test) -- see the script for why this is
# safe to call on every run (no-ops after the first decision, and in any
# non-interactive context such as CI or a --test bot run).
[ -f ./scripts/install-completion.sh ] && ./scripts/install-completion.sh

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
  inspect() { docker inspect "$@"; }
else
  build() { podman build "$@"; }
  compose() { podman-compose "$@"; }
  inspect() { podman inspect "$@"; }
fi

sha256_cmd() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum
  else
    shasum -a 256
  fi
}

# Deterministic content hash of a build context directory. Docker's own
# layer cache can't be trusted to tell us "nothing changed" on its own --
# e.g. web-terminal's `apt-get update` layers legitimately cache-bust on
# every unrelated upstream Debian package-index change, which used to force
# a real rebuild (and leave the superseded image dangling on disk) on
# every single ./run.sh, whether or not anything in this repo changed.
hash_dir() {
  find "$1" -type f | LC_ALL=C sort | while IFS= read -r f; do
    sha256_cmd "$f"
  done | sha256_cmd | awk '{print $1}'
}

# Empty output (not an error) if the image doesn't exist yet or has no such
# label -- callers treat that the same as "needs building".
image_label() {
  inspect -f "{{ index .Config.Labels \"$2\" }}" "$1" 2>/dev/null || true
}

# Build $2 (context dir) into $1 (image tag) only if $2's contents differ
# from the hash baked into $1's current image, or $1 doesn't exist yet.
# Any further args are passed straight through to `build` (e.g. the
# --secret flag for the corporate CA bundle, below).
build_if_changed() {
  image="$1"; context="$2"; shift 2
  new_hash="$(hash_dir "$context")"
  old_hash="$(image_label "$image" dojo.src-hash)"
  if [ -n "$old_hash" ] && [ "$old_hash" = "$new_hash" ]; then
    echo "  ${image}: source unchanged, reusing existing image."
    return 0
  fi
  echo "  ${image}: building (source changed, or no cached image yet)..."
  build "$@" --label "dojo.src-hash=${new_hash}" -t "$image" "$context"
}

# Same idea as build_if_changed, for a workshop overlay's own build
# contexts (e.g. dns-as-code's compose/runner/, cert-autorenewal's
# compose/dns-seed|step-ca|demo-app/ -- whatever a given overlay happens to
# add; nothing here is hardcoded to a specific workshop). Those services
# don't get a fixed image: tag of our own the way web-terminal/allocator/
# gateway do above, so there's no image label to inspect -- instead this
# hashes the workshop's whole compose/ directory and remembers the result
# in a local state file, and only runs `compose build` when that hash has
# changed since the last time this workshop ran.
#
# Deliberately excludes web-terminal/allocator/gateway from that build:
# they already went through build_if_changed above under their own fixed
# tags, and re-running `compose build` on them here is worse than merely
# redundant -- Compose's own build doesn't set our dojo.src-hash label, so
# it would silently overwrite the tag build_if_changed just set, wipe the
# label, and make the *next* run think those images need rebuilding again
# even though nothing changed (confirmed: this actually happened while
# developing this function). Any service without a build: block at all
# (e.g. dns-server, git-server) is silently skipped by `compose build`.
compose_overlay_build_if_changed() {
  overlay_dir="$1"; state_file="$2"; shift 2
  new_hash="$(hash_dir "$overlay_dir")"
  old_hash=""
  [ -f "$state_file" ] && old_hash="$(cat "$state_file")"
  if [ "$old_hash" = "$new_hash" ]; then
    echo "  ${overlay_dir}: source unchanged, reusing existing overlay images."
    return 0
  fi
  echo "  ${overlay_dir}: building (source changed, or first run for this workshop)..."
  other_services="$(compose "$@" config --services | grep -v -x -e web-terminal -e allocator -e gateway || true)"
  if [ -n "$other_services" ]; then
    # shellcheck disable=SC2086
    compose "$@" build $other_services
  fi
  mkdir -p "$(dirname "$state_file")"
  echo "$new_hash" >"$state_file"
}

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

echo "Checking images (only rebuilding what actually changed)..."
# shellcheck disable=SC2086
build_if_changed gitopsdojo/web-terminal:base ./web-terminal $build_secret_args

# A workshop's own compose/terminal/Dockerfile (if any) FROMs the base
# image above and is tagged separately per-workshop
# (gitopsdojo/web-terminal:<name>), never reusing ":base" -- see the
# comment on the web-terminal block in that workshop's
# docker-compose.override.yml for why reusing ":base" here would silently
# clobber the shared base image for every other workshop.
workshop_terminal_dir="${workshop_dir}/compose/terminal"
if [ -d "$workshop_terminal_dir" ]; then
  # shellcheck disable=SC2086
  build_if_changed "gitopsdojo/web-terminal:${workshop}" "$workshop_terminal_dir" $build_secret_args
fi

build_if_changed gitopsdojo/allocator:local ./allocator
build_if_changed gitopsdojo/gateway:local ./gateway

compose_args="-f docker-compose.yml"
if [ -n "${COMPOSE_OVERLAY:-}" ]; then
  compose_args="$compose_args -f ${COMPOSE_OVERLAY}"
fi

# Any other build: blocks this workshop's overlay adds beyond web-terminal
# (already handled above) -- e.g. dns-as-code's forgejo-runner,
# cert-autorenewal's dns-seed/step-ca/demo-app -- only rebuild when that
# overlay's compose/ directory has actually changed since this workshop
# last ran.
if [ -n "${COMPOSE_OVERLAY:-}" ]; then
  overlay_dir="$(dirname "${COMPOSE_OVERLAY}")"
  # shellcheck disable=SC2086
  compose_overlay_build_if_changed "$overlay_dir" ".build-state/${workshop}.overlay-hash" $compose_args
fi

# Record which overlay (if any) this run used, so teardown.sh tears down
# with the exact same -f set instead of only ever seeing docker-compose.yml.
# Without this, `down` has no idea an overlay's extra services/volumes
# (e.g. dns-as-code's dns-server/runner-setup/forgejo-runner and
# dns_runner_config volume) ever existed, and can't respect their
# depends_on ordering or clean up their volumes.
echo "${COMPOSE_OVERLAY:-}" > .last-overlay

echo "Starting workshop '${workshop}' (${WORKSHOP_NAME:-$workshop})..."
# No --build: every image Compose references was already brought up to
# date (or confirmed unchanged) above, either by build_if_changed (for the
# fixed-tag images) or compose_overlay_build_if_changed (for the rest of
# this workshop's overlay, if any).
# shellcheck disable=SC2086
compose $compose_args up -d
