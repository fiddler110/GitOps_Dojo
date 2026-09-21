#!/bin/sh
# Central entry point for the project: select and build a workshop, and
# front the helper scripts under engine/scripts/. Run it from the repo root
# (./run.sh, a thin forwarder to this file) or from engine/ -- same thing.
#
# Usage:
#   ./run.sh setup [--default] [--force]  # create engine/.env (scripts/env-setup.sh)
#   ./run.sh capacity --students N [...]  # size the terminal limits (scripts/capacity-calc.sh)
#   ./run.sh <workshop-name>              # e.g. ./run.sh dns-as-code
#   ./run.sh <workshop-name> --test       # also spin up demo/test bot students (3)
#   ./run.sh <workshop-name> --test 14    # ...or N bots: 1-3 fixed personas, rest random
#   ./run.sh <workshop-name> --dry-run    # preview: what would rebuild/start, builds nothing
#   ./run.sh list                         # show available workshops
#   ./run.sh stop | teardown              # stop the stack, wipe all volumes
#   ./run.sh stop --dry-run               # preview what stop would remove, removes nothing
#   ./run.sh help | -h | --help           # this overview + available workshops
#
# `setup`, `capacity`, and `stop` hand every remaining argument straight to
# their script, so `./run.sh <command> --help` prints that script's own help
# (e.g. `./run.sh capacity --help`). `--setup` and `--capacity` are accepted
# as aliases.
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

# --dry-run (workshop start and stop): report what would happen without
# building, starting, deleting, or writing any state. Picked up here, ahead
# of everything else, so the completion offer below can be skipped too --
# a dry run shouldn't prompt for (or edit) your shell rc file.
dry_run=0
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then dry_run=1; fi
done

# One-time, interactive offer to wire up shell tab-completion (workshop
# names, list/stop/teardown, --test) -- see the script for why this is
# safe to call on every run (no-ops after the first decision, and in any
# non-interactive context such as CI or a --test bot run).
if [ "$dry_run" = "0" ] && [ -f ./scripts/install-completion.sh ]; then
  ./scripts/install-completion.sh
fi

case "${1:-}" in
  stop | teardown)
    shift
    exec ./scripts/teardown.sh "$@" ;;
  setup | --setup)
    shift
    exec ./scripts/env-setup.sh "$@" ;;
  capacity | --capacity)
    shift
    exec ./scripts/capacity-calc.sh "$@" ;;
esac

usage() {
  cat <<'EOF'
Usage: ./run.sh <command | workshop-name> [options]

Commands:
  <workshop-name> [--test [N]] [--dry-run]
                                build and start a workshop; --test also starts
                                demo bot students (3 by default, or N, max 35:
                                testuser1-3 are expert/intermediate/novice, any
                                beyond that get a random one of those three);
                                --dry-run only previews what would be rebuilt
                                and started
  list                          show available workshops
  setup [--default] [--force]   create engine/.env
  capacity --students N [...]   size the terminal resource limits for this machine
  stop | teardown [--dry-run]   stop the stack and wipe ALL volumes (irreversible);
                                --dry-run lists what would be removed instead
  help | -h | --help            show this message

Run './run.sh <command> --help' for a command's own options,
e.g. './run.sh capacity --help'.
EOF
}

list_workshops() {
  echo "Available workshops:"
  for d in ../workshops/*/; do
    name="$(basename "$d")"
    [ -f "${d}workshop.env" ] || continue
    title="$(sed -n 's/^WORKSHOP_NAME=//p' "${d}workshop.env" | head -1 | tr -d '"')"
    printf '  %-20s %s\n' "$name" "${title:-}"
  done
}

case "${1:-}" in
  help | -h | --help)
    usage
    echo
    list_workshops
    exit 0 ;;
  "" | list)
    list_workshops
    echo
    usage
    exit 0 ;;
esac

workshop="$1"
shift
test_mode=0
test_count=""
while [ "$#" -gt 0 ]; do
  arg="$1"
  shift
  case "$arg" in
    --test)
      test_mode=1
      # Optional bot count: `--test 14`. Only consumed if the next word is
      # all digits, so `--test --dry-run` still works.
      case "${1:-}" in
        '' | *[!0-9]*) ;;
        *) test_count="$1"; shift ;;
      esac ;;
    --test=*)
      test_mode=1
      test_count="${arg#--test=}"
      case "$test_count" in
        '' | *[!0-9]*)
          echo "--test expects a number of bots, e.g. --test 14 (got '${test_count}')" >&2
          exit 1 ;;
      esac ;;
    --dry-run) ;; # already picked up above
    -h | --help)
      usage
      exit 0 ;;
    *)
      echo "Unrecognized argument: ${arg}" >&2
      echo "Usage: ./run.sh <workshop-name> [--test [N]] [--dry-run]" >&2
      exit 1 ;;
  esac
done

if [ -n "$test_count" ]; then
  # Same ceiling web-terminal/entrypoint.sh enforces on BOT_COUNT; checked
  # here so a bad value fails up front instead of inside the container.
  # Leading zeros are stripped first so 08 isn't read as (invalid) octal.
  test_count="$(printf '%s' "$test_count" | sed 's/^0*//')"
  if [ -z "$test_count" ] || [ "${#test_count}" -gt 2 ] || [ "$test_count" -gt 35 ]; then
    echo "--test N: N must be between 1 and 35" >&2
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
  echo ".env not found — run './run.sh setup' (or './run.sh setup --default' for quick local use) first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
# shellcheck disable=SC1091
. "$workshop_env"
set +a

# --test [N]: spin up demo/test bot student accounts (see
# engine/web-terminal/bot-runner.sh and README.md's "Demo bots (--test)"
# section) -- simulated students (an expert, an intermediate, and a
# terminal/git novice) that slowly, visibly work through the lab on
# testuserN/... branches, for demoing the workshop or exercising the
# facilitator dashboard without real students. testuser1-3 always play
# those three personas in that order; with N > 3, every bot past the third
# is assigned one of the three at random (see web-terminal/entrypoint.sh),
# which makes it easy to load-test with a bigger, mixed cohort. An explicit
# N wins over BOT_COUNT in .env; a bare --test respects a BOT_COUNT already
# set in .env and only supplies the default of 3 if that's unset.
if [ "$test_mode" = "1" ]; then
  if [ -n "$test_count" ]; then
    export BOT_COUNT="$test_count"
  else
    export BOT_COUNT="${BOT_COUNT:-3}"
  fi
  if [ "$dry_run" = "1" ]; then verb="would start"; else verb="starting"; fi
  echo "Test mode: ${verb} ${BOT_COUNT} demo bot student(s) (prefix: ${BOT_PREFIX:-testuser})."
  if [ "$BOT_COUNT" -gt 3 ]; then
    echo "           testuser1-3 = expert/intermediate/novice; the other $((BOT_COUNT - 3)) get a random one of those."
  fi
fi

if [ "$dry_run" = "1" ]; then
  echo "DRY RUN -- nothing will be built, started, or written."
  echo "Workshop:  ${workshop} (${WORKSHOP_NAME:-$workshop})"
  echo "Content:   ${WORKSHOP_CONTENT_DIR:-<unset>}"
  echo "Overlay:   ${COMPOSE_OVERLAY:-none}"
  echo
fi

# Prefer docker if it's actually present and working; fall back to podman
# otherwise (same detection teardown.sh uses, so both scripts agree on which
# engine is in play).
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  build() { docker build "$@"; }
  compose() { docker compose "$@"; }
  inspect() { docker inspect "$@"; }
  images() { docker images "$@"; }
  rmi() { docker rmi "$@"; }
  build_salt=""
else
  build() { podman build "$@"; }
  compose() { podman-compose "$@"; }
  inspect() { podman inspect "$@"; }
  images() { podman images "$@"; }
  rmi() { podman rmi "$@"; }
  # Podman builds OCI-format images by default, and OCI has no HEALTHCHECK
  # instruction -- podman warns and silently drops it, so the allocator and
  # web-terminal images would never report healthy/unhealthy. Docker format
  # keeps it. BUILDAH_FORMAT is honoured by `podman build` and by the
  # `podman-compose build` in compose_overlay_build_if_changed below.
  export BUILDAH_FORMAT=docker
  # Mixed into hash_dir so images an earlier run cached in OCI format are
  # rebuilt once, instead of being reported "source unchanged" forever.
  build_salt="podman-build-format-docker"
fi

sha256_cmd() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$@"
  else
    shasum -a 256 "$@"
  fi
}

# Deterministic content hash of a build context directory. Docker's own
# layer cache can't be trusted to tell us "nothing changed" on its own --
# e.g. web-terminal's `apt-get update` layers legitimately cache-bust on
# every unrelated upstream Debian package-index change, which used to force
# a real rebuild (and leave the superseded image dangling on disk) on
# every single ./run.sh, whether or not anything in this repo changed.
#
# Skips __pycache__/ and *.pyc: Python writes those next to the source
# whenever someone imports or lints it locally, they never reach an image
# (the Dockerfiles COPY specific files), and counting them would trigger a
# pointless rebuild.
hash_dir() {
  {
    find "$1" -type f -not -path '*/__pycache__/*' -not -name '*.pyc' \
      | LC_ALL=C sort | while IFS= read -r f; do
        sha256_cmd "$f"
      done
    [ -z "$build_salt" ] || printf '%s\n' "$build_salt"
  } | sha256_cmd | awk '{print $1}'
}

# Old-image cleanup. Rebuilding a tag (web-terminal:base, allocator:local, a
# compose overlay's service image, ...) doesn't delete the image it used to
# point at -- that image just loses its tag and sits on disk as <none>, and
# the pile grows with every rebuild. So each build below is wrapped in
# track_superseded, which notes every image that had a tag before the build
# and has none after it: exactly what that build displaced, whatever the
# image is named and whether or not it carries our label. reap_superseded
# removes them at the very end of the run.
#
# Removal is deferred until after `compose up -d` because a still-running
# container pins the image it was created from; once `up -d` has recreated
# the containers on the new images, the old ones can go. Anything that still
# can't be removed stays listed in this file and is retried on the next run.
superseded_file=".build-state/superseded-images"

# IDs of the images that currently have a tag ("false") or none ("true").
image_ids() {
  images --filter "dangling=$1" --format '{{.ID}}' | sort -u
}

# Run the given build command, recording any image it left untagged.
track_superseded() {
  ids_before=" $(image_ids false | tr '\n' ' ') "
  "$@"
  mkdir -p "$(dirname "$superseded_file")"
  for id in $(image_ids true); do
    case "$ids_before" in
      *" $id "*) echo "$id" >>"$superseded_file" ;;
    esac
  done
}

reap_superseded() {
  [ -s "$superseded_file" ] || return 0
  candidates="$(sort -u "$superseded_file")"
  # Only ever remove an image that is untagged right now. An ID recorded on
  # an earlier run can be tagged again (revert a change, and the layer cache
  # rebuilds the very same image) -- `rmi <id>` on that would delete the
  # image the stack is running on.
  untagged=" $(image_ids true | tr '\n' ' ') "
  pending=""
  for id in $candidates; do
    case "$untagged" in
      *" $id "*) pending="$pending $id" ;;
    esac
  done
  removed=0
  # A superseded image can be the parent of another superseded one (a
  # workshop terminal image built on an old web-terminal:base), which has to
  # go first -- so keep passing over the list while that makes progress.
  progress=1
  while [ -n "$pending" ] && [ "$progress" = "1" ]; do
    progress=0
    still=""
    for id in $pending; do
      if rmi "$id" >/dev/null 2>&1; then
        removed=$((removed + 1))
        progress=1
      else
        still="$still $id"
      fi
    done
    pending="$still"
  done
  if [ -n "$pending" ]; then
    printf '%s\n' $pending >"$superseded_file"
  else
    rm -f "$superseded_file"
  fi
  if [ "$removed" -gt 0 ]; then
    echo "Removed ${removed} superseded image(s) left behind by rebuilds."
  fi
  if [ -n "$pending" ]; then
    echo "Could not remove $(echo $pending | wc -w | tr -d ' ') superseded image(s) (still in use?); will retry on the next run."
  fi
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
  if [ "$dry_run" = "1" ]; then
    echo "  ${image}: WOULD BUILD (source changed, or no cached image yet)."
    return 0
  fi
  echo "  ${image}: building (source changed, or no cached image yet)..."
  track_superseded build "$@" --label "dojo.src-hash=${new_hash}" -t "$image" "$context"
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
# Deliberately excludes web-terminal/allocator/gateway/presentation from that
# build (keep the list in the grep below in step with every image built by
# build_if_changed): they already went through build_if_changed above under their own fixed
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
  if [ "$dry_run" = "1" ]; then
    echo "  ${overlay_dir}: WOULD BUILD overlay images (source changed, or first run for this workshop)."
    return 0
  fi
  echo "  ${overlay_dir}: building (source changed, or first run for this workshop)..."
  other_services="$(compose "$@" config --services | grep -v -x -e web-terminal -e allocator -e gateway -e presentation || true)"
  if [ -n "$other_services" ]; then
    # shellcheck disable=SC2086
    track_superseded compose "$@" build $other_services
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

if [ "$dry_run" = "1" ]; then
  echo "Checking images (dry run: reporting only, building nothing)..."
else
  echo "Checking images (only rebuilding what actually changed)..."
fi
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
  # It's FROM the base image, so a rebuilt base has to rebuild this too --
  # otherwise it stays on the old base, which then can't be cleaned up.
  # Folding base's image ID into the hash does that; the directory's own
  # contents alone wouldn't change when only the base did.
  saved_salt="$build_salt"
  build_salt="${build_salt}$(inspect -f '{{.Id}}' gitopsdojo/web-terminal:base 2>/dev/null || true)"
  # shellcheck disable=SC2086
  build_if_changed "gitopsdojo/web-terminal:${workshop}" "$workshop_terminal_dir" $build_secret_args
  build_salt="$saved_salt"
fi

build_if_changed gitopsdojo/allocator:local ./allocator
build_if_changed gitopsdojo/gateway:local ./gateway
build_if_changed gitopsdojo/presentation:local ./presentation

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
if [ "$dry_run" = "1" ]; then
  echo
  echo "Validating the Compose config..."
  # shellcheck disable=SC2086
  if compose $compose_args config >/dev/null 2>&1; then
    echo "  valid."
  else
    echo "  'compose ${compose_args} config' failed (or compose isn't available) -- run it directly to see why."
  fi
  echo
  echo "Would run: compose ${compose_args} up -d"
  echo "Dry run complete: nothing was built, started, or written."
  exit 0
fi

echo "${COMPOSE_OVERLAY:-}" > .last-overlay

echo "Starting workshop '${workshop}' (${WORKSHOP_NAME:-$workshop})..."
# No --build: every image Compose references was already brought up to
# date (or confirmed unchanged) above, either by build_if_changed (for the
# fixed-tag images) or compose_overlay_build_if_changed (for the rest of
# this workshop's overlay, if any).
# shellcheck disable=SC2086
compose $compose_args up -d

# Containers now run on the freshly built images, so the ones those builds
# displaced are no longer pinned.
reap_superseded
