#!/bin/sh
# Helper for creating engine/.env from .env.example.
#
# Normally run as `./run.sh setup [--default] [--force]` (same script, same
# flags; `./run.sh setup --help` prints the usage).
#
# Two modes:
#   ./run.sh setup                      # interactive: walk through every
#                                        # setting, showing its current
#                                        # default -- press Enter to accept
#                                        # it or type your own. For passwords
#                                        # and tokens, pressing Enter instead
#                                        # auto-generates a strong random
#                                        # value. Use this when it matters
#                                        # that credentials are unique.
#
#   ./run.sh setup --default            # non-interactive: fills in every
#                                        # required setting with a fixed,
#                                        # easy-to-remember "lazy" value
#                                        # (below) instead of prompting.
#                                        # Machine-to-machine secrets
#                                        # (CONTROL_TOKEN/GATEWAY_TOKEN) are
#                                        # still randomly generated even in
#                                        # this mode -- nobody ever types
#                                        # those, so there's no reason to
#                                        # weaken them. Also tries to size
#                                        # WEB_TERMINAL_MEM_LIMIT/PIDS_LIMIT/
#                                        # CODE_SERVER_MAX_HEAP_MB for this
#                                        # machine via capacity-calc.sh.
#
# --force skips the "engine/.env already exists -- overwrite?" prompt (also
# implied by --default, since that mode is meant to run unattended).
set -eu

usage() {
  cat <<'EOF'
Usage: ./run.sh setup [--default] [--force]

Creates engine/.env from engine/.env.example.

  (no flags)   interactive: prompts for every setting, showing its default;
               Enter accepts it. Bare Enter on a password/token generates a
               strong random value.
  --default    non-interactive: fixed, easy-to-remember credentials for
               local/throwaway use (student/student123/admin/admin).
               CONTROL_TOKEN/GATEWAY_TOKEN are still random. Implies --force.
  --force      overwrite an existing engine/.env without asking.
  -h, --help   show this message.

Both modes try to size the terminal resource limits for this machine via
'./run.sh capacity'.
EOF
}

cd "$(dirname "$0")/.."

mode="interactive"
force=0
for arg in "$@"; do
  case "$arg" in
    --default) mode="default" ;;
    --force) force=1 ;;
    -h | --help) usage; exit 0 ;;
    *)
      echo "Unrecognized argument: ${arg}" >&2
      usage >&2
      exit 1 ;;
  esac
done
[ "$mode" = "default" ] && force=1

if [ ! -f .env.example ]; then
  echo ".env.example not found (expected at engine/.env.example)." >&2
  exit 1
fi

if [ -f .env ] && [ "$force" -ne 1 ]; then
  printf 'engine/.env already exists. Overwrite it? [y/N] '
  read -r ans
  case "$ans" in
    [Yy]*) ;;
    *) echo "Leaving .env untouched."; exit 0 ;;
  esac
fi

cp .env.example .env

# Portable in-place sed replace (BSD/macOS sed needs `-i ''`, GNU sed needs
# `-i`; this form works on both without a temp-file dance).
set_var() {
  key="$1"; value="$2"
  sed -i.bak "s#^${key}=.*#${key}=${value}#" .env
  rm -f .env.bak
}

# Prefer openssl (present almost everywhere); fall back to /dev/urandom.
random_hex() {
  n="$1"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$n"
  else
    od -An -tx1 -N "$n" /dev/urandom | tr -d ' \n'
  fi
}

# A shorter random value for passwords a student/facilitator actually types
# in -- easy to read off a screen or slide, unlike the 64-char tokens below.
random_password() {
  random_hex 6
}

random_hex_32() {
  random_hex 32
}

# .env.example's own default for a var (used as the interactive prompt's
# fallback).
example_default() {
  sed -n "s/^${1}=//p" .env.example | head -1 | tr -d '"'
}

# What's currently in .env (used to read back a value this same run just
# set, e.g. STUDENT_COUNT, before sizing the web-terminal resource limits).
current_value() {
  sed -n "s/^${1}=//p" .env | head -1 | tr -d '"'
}

# Try to size WEB_TERMINAL_MEM_LIMIT/PIDS_LIMIT/CODE_SERVER_MAX_HEAP_MB for
# this machine via capacity-calc.sh instead of leaving .env.example's fixed
# rule-of-thumb numbers in place. Never fatal: capacity-calc.sh can fail for
# plenty of reasons (no docker/podman, can't detect host memory, etc.) --
# any failure just falls back to whatever's already in .env.
apply_capacity_sizing() {
  students="$1"
  echo "Sizing WEB_TERMINAL_MEM_LIMIT/PIDS_LIMIT/CODE_SERVER_MAX_HEAP_MB for this machine (./run.sh capacity --students ${students})..."
  if ! output="$(./scripts/capacity-calc.sh --students "$students" 2>&1)"; then
    echo "  -> capacity-calc.sh couldn't size this machine; keeping .env.example's defaults."
    return 1
  fi
  mem="$(echo "$output" | sed -n 's/^  WEB_TERMINAL_MEM_LIMIT=//p' | head -1)"
  pids="$(echo "$output" | sed -n 's/^  WEB_TERMINAL_PIDS_LIMIT=//p' | head -1)"
  heap="$(echo "$output" | sed -n 's/^  CODE_SERVER_MAX_HEAP_MB=//p' | head -1)"
  if [ -z "$mem" ] || [ -z "$pids" ] || [ -z "$heap" ]; then
    echo "  -> couldn't parse capacity-calc.sh's output; keeping .env.example's defaults."
    return 1
  fi
  set_var WEB_TERMINAL_MEM_LIMIT "$mem"
  set_var WEB_TERMINAL_PIDS_LIMIT "$pids"
  set_var CODE_SERVER_MAX_HEAP_MB "$heap"
  echo "  -> WEB_TERMINAL_MEM_LIMIT=${mem} WEB_TERMINAL_PIDS_LIMIT=${pids} CODE_SERVER_MAX_HEAP_MB=${heap}"
  if echo "$output" | grep -q '^WARNING:'; then
    echo "  -> capacity-calc.sh warned this doesn't fit on this machine at ${students} students -- run it directly for details:"
    echo "     ./run.sh capacity --students ${students}"
  fi
}

if [ "$mode" = "default" ]; then
  echo "Writing engine/.env with fixed lazy defaults (--default) ..."
  echo

  # Human-typed credentials: fixed, easy-to-remember values. Fine for local/
  # throwaway use; run without --default (interactive mode) for a real
  # workshop where credentials should be unique per session.
  set_var TTYD_PASSWORD "student"
  set_var STUDENT_PASSWORD "student123"
  set_var FACILITATOR_USERNAME "admin"
  set_var FACILITATOR_PASSWORD "admin"
  set_var FORGEJO_ADMIN_PASSWORD "admin"

  # Machine-to-machine secrets: always random, even in --default mode --
  # nobody ever types these, so there's no lazy/careful tradeoff to make.
  set_var CONTROL_TOKEN "$(random_hex_32)"
  set_var GATEWAY_TOKEN "$(random_hex_32)"

  echo "Set: TTYD_PASSWORD=student, STUDENT_PASSWORD=student123,"
  echo "     FACILITATOR_USERNAME=admin, FACILITATOR_PASSWORD=admin, FORGEJO_ADMIN_PASSWORD=admin"
  echo "     (FORGEJO_ADMIN_USER, TTYD_USERNAME, and everything else kept .env.example's default)"
  echo "Generated random CONTROL_TOKEN / GATEWAY_TOKEN."
  echo

  apply_capacity_sizing "$(current_value STUDENT_COUNT)" || true
  echo

  echo "Wrote engine/.env."
  echo "Review PUBLIC_BASE_URL, LAB_HOST_IP, and STUDENT_COUNT in .env before a"
  echo "real workshop -- these lazy credentials are meant for quick/local use."
  echo
  echo "Next: ./run.sh <workshop-name>"
  exit 0
fi

# --- Interactive mode ------------------------------------------------------

# Plain setting: show the current default, take whatever the user types,
# fall back to the default on a bare Enter.
ask() {
  var="$1"; label="$2"; default="$3"
  printf '%s [%s]: ' "$label" "$default"
  read -r ans
  if [ -n "$ans" ]; then
    set_var "$var" "$ans"
  fi
}

# Secret setting: bare Enter auto-generates a strong random value instead of
# falling back to the (deliberately unsafe) `change-me` placeholder.
ask_secret() {
  var="$1"; label="$2"; genfn="$3"
  printf '%s\n  Press Enter to auto-generate a secure value, or type your own: ' "$label"
  read -r ans
  if [ -z "$ans" ]; then
    ans="$("$genfn")"
    echo "  -> generated: ${ans}"
  fi
  set_var "$var" "$ans"
}

# Yes/no prompt, defaulting to yes on a bare Enter.
confirm() {
  printf '%s [Y/n] ' "$1"
  read -r ans
  case "$ans" in
    [Nn]*) return 1 ;;
    *) return 0 ;;
  esac
}

echo "Setting up engine/.env -- press Enter on any prompt to accept the default shown in [brackets]."
echo

echo "--- Public address / networking ---"
ask PUBLIC_BASE_URL "Public base URL students will browse to" "$(example_default PUBLIC_BASE_URL)"
ask LAB_HOST_IP "Host interface the gateway binds to" "$(example_default LAB_HOST_IP)"
ask GATEWAY_HTTP_PORT "Gateway HTTP port" "$(example_default GATEWAY_HTTP_PORT)"
ask GATEWAY_HTTPS_PORT "Gateway HTTPS port" "$(example_default GATEWAY_HTTPS_PORT)"
echo

echo "--- Shared browser gate (terminal + Forgejo login) ---"
ask TTYD_USERNAME "Shared username" "$(example_default TTYD_USERNAME)"
ask_secret TTYD_PASSWORD "Shared password" random_password
echo

echo "--- Student accounts ---"
ask STUDENT_COUNT "Number of student accounts" "$(example_default STUDENT_COUNT)"
ask STUDENT_PREFIX "Student account username prefix" "$(example_default STUDENT_PREFIX)"
ask_secret STUDENT_PASSWORD "Student password (shared by all students)" random_password
echo

echo "--- Facilitator account (Linux shell, sudo-capable; gates /admin) ---"
ask FACILITATOR_USERNAME "Facilitator username" "$(example_default FACILITATOR_USERNAME)"
ask_secret FACILITATOR_PASSWORD "Facilitator password" random_password
echo

echo "--- Forgejo admin account ---"
ask FORGEJO_ADMIN_USER "Forgejo admin username" "$(example_default FORGEJO_ADMIN_USER)"
ask_secret FORGEJO_ADMIN_PASSWORD "Forgejo admin password" random_password
ask FORGEJO_ADMIN_EMAIL "Forgejo admin email" "$(example_default FORGEJO_ADMIN_EMAIL)"
echo

echo "--- Control-plane shared secrets (machine-to-machine only -- nobody types these) ---"
ask_secret CONTROL_TOKEN "CONTROL_TOKEN (allocator <-> web-terminal)" random_hex_32
ask_secret GATEWAY_TOKEN "GATEWAY_TOKEN (gateway <-> allocator)" random_hex_32
echo

echo "--- Web-terminal resource ceiling ---"
if confirm "Run './run.sh capacity' to size these for this machine (recommended)?"; then
  apply_capacity_sizing "$(current_value STUDENT_COUNT)" || {
    echo "  Falling back to manual entry."
    ask WEB_TERMINAL_MEM_LIMIT "Container memory limit" "$(example_default WEB_TERMINAL_MEM_LIMIT)"
    ask WEB_TERMINAL_PIDS_LIMIT "Container pids limit" "$(example_default WEB_TERMINAL_PIDS_LIMIT)"
    ask CODE_SERVER_MAX_HEAP_MB "Per-process code-server heap cap (MB)" "$(example_default CODE_SERVER_MAX_HEAP_MB)"
  }
else
  ask WEB_TERMINAL_MEM_LIMIT "Container memory limit" "$(example_default WEB_TERMINAL_MEM_LIMIT)"
  ask WEB_TERMINAL_PIDS_LIMIT "Container pids limit" "$(example_default WEB_TERMINAL_PIDS_LIMIT)"
  ask CODE_SERVER_MAX_HEAP_MB "Per-process code-server heap cap (MB)" "$(example_default CODE_SERVER_MAX_HEAP_MB)"
fi
echo

echo "Wrote engine/.env."
echo
echo "WORKSHOP_CONTENT_DIR/WORKSHOP_NAME/FORGEJO_ORG/FORGEJO_REPO were left at"
echo "their defaults -- ./run.sh <workshop-name> sets those from"
echo "workshops/<name>/workshop.env for you. CORP_CA_BUNDLE was left commented"
echo "out -- only needed on a network with TLS inspection (see .env.example)."
echo
echo "Next: ./run.sh <workshop-name>"
