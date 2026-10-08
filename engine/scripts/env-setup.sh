#!/bin/sh
# Helper for creating .env (secrets) from .env.example, and for writing this
# machine's non-secret settings into dojo.local.toml.
#
# Normally run as `./run.sh setup [--default] [--force]` (same script, same
# flags; `./run.sh setup --help` prints the usage).
#
# Modes:
#   ./run.sh setup                      # interactive: walks through every
#                                        # setting with a short explanation.
#                                        # If .env already exists, its
#                                        # values are the defaults (Enter keeps
#                                        # them), and settings this script
#                                        # doesn't ask about are carried over,
#                                        # [profile] sections included.
#                                        # A password that is still a public
#                                        # default is replaced by a generated
#                                        # one on a bare Enter.
#
#   ./run.sh setup --default            # non-interactive: fixed, easy-to-
#                                        # remember "lazy" credentials from
#                                        # dojo.toml's defaults. Machine-
#                                        # to-machine secrets (CONTROL_TOKEN/
#                                        # GATEWAY_TOKEN/STUDENT_PASSWORD_SEED) and
#                                        # FORGEJO_ADMIN_PASSWORD (only the
#                                        # facilitator's SSO uses it) are
#                                        # still random. Also sizes the
#                                        # terminal limits via capacity-calc.sh.
#
#   ./run.sh setup --rotate-class       # only a new TTYD_PASSWORD in the
#                                        # existing .env.
#
# The new file is written to .env.new and moved into place only at the end, so
# stopping part way (Ctrl-C) leaves the old .env untouched. The old one is kept
# as .env.previous (git-ignored). Settings that are not secrets (URL, ports,
# student count, sizing ...) go to dojo.local.toml through `run.sh _config-set`.
#
# --force skips the ".env already exists -- overwrite?" prompt (also
# implied by --default, since that mode is meant to run unattended).
set -eu

usage() {
  cat <<'EOF'
Usage: ./run.sh setup [--default] [--force] | --rotate-class

Creates .env (the secrets) from .env.example and writes this machine's other
settings into dojo.local.toml (the committed defaults are in dojo.toml).

  (no flags)   interactive: prompts for every setting with a short
               explanation. With an existing .env, its values are the
               defaults (Enter keeps them) and everything it doesn't ask about
               is carried over, [profile] sections included. A password that is still a public default
               (change-me, student, student123, admin) is replaced by a
               generated one on a bare Enter.
  --default    non-interactive: fixed, easy-to-remember credentials for
               local/throwaway use (student/student123/admin/admin) and
               dojo.toml's other defaults (http://localhost:8080).
               CONTROL_TOKEN/GATEWAY_TOKEN and FORGEJO_ADMIN_PASSWORD are
               still random. './run.sh <workshop>' refuses these defaults
               unless the gateway is loopback-only. Implies --force.
  --force      overwrite an existing .env without asking ([profile] sections are kept).
  --rotate-class
               only generate a new TTYD_PASSWORD (the shared class login) in
               the existing .env; restart the workshop to apply it.
  -h, --help   show this message.

The old .env is kept as .env.previous. Stopping part way leaves
it untouched. Both modes try to size the terminal resource limits for this
machine via './run.sh capacity'.
EOF
}

cd "$(dirname "$0")/../.."
# shellcheck source=lib.sh
. ./engine/scripts/lib.sh
dojo=./engine/run.sh

mode="interactive"
force=0
for arg in "$@"; do
  case "$arg" in
    --default) mode="default" ;;
    --force) force=1 ;;
    --rotate-class) mode="rotate-class" ;;
    -h | --help) usage; exit 0 ;;
    *)
      echo "Unrecognized argument: ${arg}" >&2
      usage >&2
      exit 1 ;;
  esac
done
[ "$mode" = "default" ] && force=1

if [ ! -f .env.example ]; then
  echo ".env.example not found (expected at the repo root)." >&2
  exit 1
fi

# .env holds every master secret (GATEWAY_TOKEN, CONTROL_TOKEN,
# FORGEJO_ADMIN_PASSWORD...): owner-only, like every file made on the way
# (.env.new, .env.new.tmp, .env.previous). FIND-16.
umask 077

# The file set_var/current_value work on: .env.new while building one,
# .env itself for --rotate-class.
target=".env.new"

# Replace KEY=... in $target. awk with the value from the environment, so a
# value holding '#', '&' or '\' is written as typed (sed would mangle them).
# Only the shared lines, above the first [profile] header: a profile's own
# TTYD_PASSWORD stays as it is.
set_var() {
  SET_VAR_VALUE="$2" awk -v k="$1" '
    BEGIN { v = ENVIRON["SET_VAR_VALUE"] }
    /^\[/ { hdr = 1 }
    !hdr && index($0, k "=") == 1 { print k "=" v; next }
    { print }' "$target" > "${target}.tmp"
  mv "${target}.tmp" "$target"
}

# Non-secret settings live in dojo.local.toml, written and read by the CLI.
cfg_set() { "$dojo" _config-set "$1" "$2"; }
cfg_get() { "$dojo" _config-get "$1"; }

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

# A value from a KEY=value file (first match, quotes stripped).
file_value() {
  sed -n "s/^${1}=//p" "$2" | head -1 | tr -d '"'
}

# A secret is read from the file being built, anything else from the settings.
current_value() {
  case "$1" in
    *PASSWORD | *TOKEN | *SEED) file_value "$1" "$target" ;;
    *) cfg_get "$1" ;;
  esac
}

# Public values nobody should rely on off this machine: .env.example's
# placeholder and the `--default` passwords. run.sh refuses them off loopback.
is_weak() { [ -z "$1" ] || dojo_is_default_password "$1"; }

if [ "$mode" = "rotate-class" ]; then
  if [ ! -f .env ]; then
    echo ".env not found -- run './run.sh setup' first." >&2
    exit 1
  fi
  if ! grep -q '^TTYD_PASSWORD=' .env; then
    echo ".env has no TTYD_PASSWORD line to rotate." >&2
    exit 1
  fi
  target=".env"
  new_password="$(random_password)"
  set_var TTYD_PASSWORD "$new_password"
  chmod 600 .env
  echo "New class password (TTYD_PASSWORD): ${new_password}"
  echo "Restart the workshop ('./run.sh <workshop>') for the gateway to use it."
  exit 0
fi

if [ -f .env ] && [ "$force" -ne 1 ]; then
  printf '.env already exists. Its values will be the defaults and anything\n'
  printf 'not asked about is kept. Continue? [Y/n] '
  read -r ans
  case "$ans" in
    [Nn]*) echo "Leaving .env untouched."; exit 0 ;;
  esac
fi

# Build the new file beside the old one; a Ctrl-C or error removes it and
# leaves .env as it was.
trap 'rm -f .env.new .env.new.tmp' EXIT
trap 'echo; echo "Stopped: .env was not changed (answers already given stay in dojo.local.toml)."; exit 130' INT TERM
cp .env.example "$target"

# Move the finished file into place, keeping the old one. The old file's
# [profile] sections (home, live ... secrets) are carried over untouched.
install_env() {
  if [ -f .env ]; then
    cp .env .env.previous
    chmod 600 .env.previous
    if awk '/^\[/ { keep = 1 } keep' .env.previous | grep -q .; then
      { printf '\n'; awk '/^\[/ { keep = 1 } keep' .env.previous; } >> "$target"
    fi
  fi
  mv "$target" .env
  chmod 600 .env
  trap - EXIT
}

# Try to size WEB_TERMINAL_MEM_LIMIT/PIDS_LIMIT/CODE_SERVER_MAX_HEAP_MB for
# this machine via capacity-calc.sh instead of leaving dojo.toml's fixed
# rule-of-thumb numbers in place. Never fatal: capacity-calc.sh can fail for
# plenty of reasons (no docker/podman, can't detect host memory, etc.) --
# any failure just falls back to whatever's already in the file.
apply_capacity_sizing() {
  students="$1"
  echo "Sizing WEB_TERMINAL_MEM_LIMIT/PIDS_LIMIT/CODE_SERVER_MAX_HEAP_MB for this machine (./run.sh capacity --students ${students})..."
  if ! output="$(./engine/scripts/capacity-calc.sh --students "$students" 2>&1)"; then
    echo "  -> capacity-calc.sh couldn't size this machine; keeping the current values."
    return 1
  fi
  mem="$(echo "$output" | sed -n 's/^  WEB_TERMINAL_MEM_LIMIT=//p' | head -1)"
  pids="$(echo "$output" | sed -n 's/^  WEB_TERMINAL_PIDS_LIMIT=//p' | head -1)"
  heap="$(echo "$output" | sed -n 's/^  CODE_SERVER_MAX_HEAP_MB=//p' | head -1)"
  if [ -z "$mem" ] || [ -z "$pids" ] || [ -z "$heap" ]; then
    echo "  -> couldn't parse capacity-calc.sh's output; keeping the current values."
    return 1
  fi
  cfg_set WEB_TERMINAL_MEM_LIMIT "$mem"
  cfg_set WEB_TERMINAL_PIDS_LIMIT "$pids"
  cfg_set CODE_SERVER_MAX_HEAP_MB "$heap"
  echo "  -> WEB_TERMINAL_MEM_LIMIT=${mem} WEB_TERMINAL_PIDS_LIMIT=${pids} CODE_SERVER_MAX_HEAP_MB=${heap}"
  if echo "$output" | grep -q '^WARNING:'; then
    echo "  -> capacity-calc.sh warned this doesn't fit on this machine at ${students} students -- run it directly for details:"
    echo "     ./run.sh capacity --students ${students}"
  fi
}

# Profiles (./run.sh <workshop> --env NAME) that add to or override these settings.
note_env_overrides() {
  names="$(sed -n 's/^\[\([a-z0-9-]*\)\]$/\1/p' .env | tr '\n' ' ')"
  [ -n "$names" ] && echo "Note: .env keeps secrets for the profiles: ${names}(--env NAME; their settings are in dojo.local.toml)."
  return 0
}

if [ "$mode" = "default" ]; then
  echo "Writing .env with fixed lazy defaults (--default) ..."
  echo

  # Human-typed credentials: fixed, easy-to-remember values. Fine for local/
  # throwaway use; run without --default (interactive mode) for a real
  # workshop where credentials should be unique per session.
  cfg_set TTYD_USERNAME "student"
  set_var TTYD_PASSWORD "student"
  cfg_set FACILITATOR_USERNAME "admin"
  set_var FACILITATOR_PASSWORD "admin"

  # Machine-to-machine secrets: always random, even in --default mode --
  # nobody ever types these, so there's no lazy/careful tradeoff to make.
  set_var CONTROL_TOKEN "$(random_hex_32)"
  set_var GATEWAY_TOKEN "$(random_hex_32)"
  # Each student's own Forgejo password is derived from it (remediation
  # T2.1b); git uses a token, so nobody types those either.
  set_var STUDENT_PASSWORD_SEED "$(random_hex_32)"
  # Nobody types this one either: the facilitator reaches Forgejo through the
  # allocator's /forgejo-login SSO, which reads it from .env.
  set_var FORGEJO_ADMIN_PASSWORD "$(random_password)"

  echo "Set: TTYD_USERNAME=student, TTYD_PASSWORD=student,"
  echo "     FACILITATOR_USERNAME=admin, FACILITATOR_PASSWORD=admin"
  echo "     (PUBLIC_BASE_URL=$(current_value PUBLIC_BASE_URL) and everything else: dojo.toml's defaults)"
  echo "Generated random CONTROL_TOKEN / GATEWAY_TOKEN / STUDENT_PASSWORD_SEED / FORGEJO_ADMIN_PASSWORD."
  echo

  apply_capacity_sizing "$(current_value STUDENT_COUNT)" || true
  echo

  install_env
  echo "Wrote .env$( [ -f .env.previous ] && echo ' (the old one is .env.previous)')."
  note_env_overrides
  echo "These lazy credentials are for this machine only: './run.sh <workshop>'"
  echo "refuses them unless PUBLIC_BASE_URL and LAB_HOST_IP are loopback."
  echo
  ./engine/scripts/alias-setup.sh --check || echo "Optional: './run.sh alias-setup' installs the 'dojo' command (dojo <workshop> from anywhere)."
  echo "Next: ./run.sh <workshop-name>"
  exit 0
fi

# --- Interactive mode ------------------------------------------------------

# Start from the old .env's shared values: every KEY= above its first [profile]
# header is copied over (appended if .env.example has no such line, e.g. BOT_PASSWORD),
# so the prompts below default to them and nothing unasked is lost.
if [ -f .env ]; then
  carried=""
  while IFS= read -r line; do
    case "$line" in
      "["*) break ;;
      [A-Z_]*=*) ;;
      *) continue ;;
    esac
    key="${line%%=*}"
    case "$key" in *[!A-Z0-9_]*) continue ;; esac
    value="${line#*=}"
    if grep -q "^${key}=" "$target"; then
      set_var "$key" "$value"
    else
      if [ -z "$carried" ]; then
        printf '\n# --- Kept from the previous .env -------------------------------------------\n' >> "$target"
      fi
      printf '%s\n' "$line" >> "$target"
      carried="${carried} ${key}"
    fi
  done < .env
  echo "Using your existing .env as the defaults (Enter keeps a value)."
  [ -n "$carried" ] && echo "Also kept, not in .env.example:${carried}"
fi

# Plain setting: explain it, show the current value, keep it on a bare Enter.
ask() {
  var="$1"; label="$2"; default="${3:-$(current_value "$1")}"
  printf '%s [%s]: ' "$label" "$default"
  read -r ans
  cfg_set "$var" "${ans:-$default}"
}

# Secret setting. A good current value is kept on a bare Enter ('new'
# generates one); a public default or placeholder is replaced by a generated
# one on a bare Enter. Typed values are used as they are.
ask_secret() {
  var="$1"; label="$2"; genfn="$3"
  cur="$(current_value "$var")"
  if is_weak "$cur"; then
    printf '%s\n  Current: %s (a public default)\n  Enter generates a strong one, or type your own: ' "$label" "${cur:-<empty>}"
    read -r ans
    [ -n "$ans" ] || { ans="$("$genfn")"; echo "  -> generated: ${ans}"; }
  else
    printf '%s\n  Current: %s\n  Enter keeps it, "new" generates one, or type your own: ' "$label" "$cur"
    read -r ans
    case "$ans" in
      '') ans="$cur" ;;
      new) ans="$("$genfn")"; echo "  -> generated: ${ans}" ;;
    esac
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

echo "Setting up .env and dojo.local.toml -- press Enter on any prompt to accept the value shown in [brackets]."
echo "Stopping part way (Ctrl-C) leaves .env unchanged."
echo

cat <<'EOF'
--- Address and ports ---
  The gateway is the lab's one entry point. Podman (rootless) can't bind ports
  below 1024, so use 8080/8443, and put the port in the address students open
  unless something in front (a proxy, NAT) maps 80/443 to it.
  LAB_HOST_IP: 127.0.0.1 = this machine only; 0.0.0.0 = the LAN too (needed
  for other computers, or a proxy on another host, to reach the lab).
  Off loopback, './run.sh <workshop>' refuses the public default passwords.
EOF
# 80/443 were .env.example's defaults before 8080/8443; offer the new ones
# (type 80/443 to keep them, e.g. on a VM with Docker or rootful podman).
http_default="$(current_value GATEWAY_HTTP_PORT)"
case "$http_default" in '' | 80) http_default=8080 ;; esac
https_default="$(current_value GATEWAY_HTTPS_PORT)"
case "$https_default" in '' | 443) https_default=8443 ;; esac
ask GATEWAY_HTTP_PORT "Gateway HTTP port (80 needs root)" "$http_default"
ask GATEWAY_HTTPS_PORT "Gateway HTTPS port (443 needs root)" "$https_default"
url_default="$(current_value PUBLIC_BASE_URL)"
case "$url_default" in
  http://localhost | http://localhost:80 | http://localhost:[0-9]*)
    url_default="http://localhost:$(current_value GATEWAY_HTTP_PORT)" ;;
esac
ask PUBLIC_BASE_URL "Address students browse to (PUBLIC_BASE_URL)" "$url_default"
ask LAB_HOST_IP "Host interface the gateway binds to (LAB_HOST_IP)"
echo

cat <<'EOF'
--- Class login (the browser's sign-in box) ---
  One username/password for the whole class, shown on a slide. It opens the
  portal, where each student picks a name. Change it per class
  ('./run.sh setup --rotate-class' does only this).
EOF
ask TTYD_USERNAME "Class username"
ask_secret TTYD_PASSWORD "Class password (TTYD_PASSWORD)" random_password
echo

cat <<'EOF'
--- Student accounts ---
  studentNN Linux + Forgejo accounts. The count sizes the roster. Each student
  gets their own Forgejo password (from STUDENT_PASSWORD_SEED below) and a git
  token in the terminal; the Roster shows a password when you need one.
EOF
ask STUDENT_COUNT "Number of student accounts"
ask STUDENT_PREFIX "Student account username prefix"
echo

cat <<'EOF'
--- Terminal ---
  code-server: VS Code in the browser plus a tmux terminal.
  zellij:      a terminal only (file list, micro editor, shell): far less memory
               per student.
EOF
flavor_default="$(current_value TERMINAL_FLAVOR)"
case "$flavor_default" in web | '') flavor_default=code-server ;; esac
ask TERMINAL_FLAVOR "Terminal students get (code-server or zellij)" "$flavor_default"
echo

cat <<'EOF'
--- Facilitator (you) ---
  Signs in to /admin and everything else, has sudo in the terminal. Keep this
  one private.
EOF
ask FACILITATOR_USERNAME "Facilitator username"
ask_secret FACILITATOR_PASSWORD "Facilitator password" random_password
echo

cat <<'EOF'
--- Forgejo admin (machine account) ---
  Created at start-up; the facilitator reaches Forgejo through single sign-on,
  so nobody types this password. Avoid the reserved name "admin".
EOF
ask FORGEJO_ADMIN_USER "Forgejo admin username"
ask_secret FORGEJO_ADMIN_PASSWORD "Forgejo admin password" random_password
ask FORGEJO_ADMIN_EMAIL "Forgejo admin email"
echo

cat <<'EOF'
--- Internal tokens (machine to machine; nobody types these) ---
EOF
ask_secret CONTROL_TOKEN "CONTROL_TOKEN (allocator <-> web-terminal)" random_hex_32
ask_secret GATEWAY_TOKEN "GATEWAY_TOKEN (gateway <-> allocator)" random_hex_32
ask_secret STUDENT_PASSWORD_SEED "STUDENT_PASSWORD_SEED (each student's Forgejo password is derived from it)" random_hex_32
echo

cat <<'EOF'
--- Web-terminal resource ceiling ---
  Memory/process limits for all students' VS Code and terminals together.
EOF
if confirm "Run './run.sh capacity' to size these for this machine (recommended)?"; then
  apply_capacity_sizing "$(current_value STUDENT_COUNT)" || {
    echo "  Falling back to manual entry."
    ask WEB_TERMINAL_MEM_LIMIT "Container memory limit"
    ask WEB_TERMINAL_PIDS_LIMIT "Container pids limit"
    ask CODE_SERVER_MAX_HEAP_MB "Per-process code-server heap cap (MB)"
  }
else
  ask WEB_TERMINAL_MEM_LIMIT "Container memory limit"
  ask WEB_TERMINAL_PIDS_LIMIT "Container pids limit"
  ask CODE_SERVER_MAX_HEAP_MB "Per-process code-server heap cap (MB)"
fi
echo

install_env
echo "Wrote .env$( [ -f .env.previous ] && echo ' (the old one is .env.previous)')."
echo
echo "Summary:"
echo "  Address:      $(cfg_get PUBLIC_BASE_URL)  (bound on $(cfg_get LAB_HOST_IP))"
echo "  Class login:  $(cfg_get TTYD_USERNAME) / $(file_value TTYD_PASSWORD .env)  (on the slide)"
echo "  Facilitator:  $(cfg_get FACILITATOR_USERNAME) / $(file_value FACILITATOR_PASSWORD .env)  (private)"
echo "  Students:     $(cfg_get STUDENT_COUNT) x $(cfg_get STUDENT_PREFIX)NN, own Forgejo passwords (Roster > Password)"
note_env_overrides
echo
echo "Terminal flavor (VS Code or Zellij), ports and the rest: dojo.toml / dojo.local.toml."
echo "WORKSHOP_CONTENT_DIR/WORKSHOP_NAME/FORGEJO_ORG/FORGEJO_REPO come from"
echo "workshops/<name>/workshop.env when you run ./run.sh <workshop-name>."
echo "New passwords reach a running stack only after './run.sh stop' (wipes its"
echo "volumes) and './run.sh <workshop-name>': Forgejo keeps the accounts it seeded."
echo
if ! ./engine/scripts/alias-setup.sh --check && [ -t 0 ]; then
  if confirm "Install the 'dojo' command (dojo <workshop> from any directory, with tab completion)?"; then
    ./engine/scripts/alias-setup.sh || echo "  './run.sh alias-setup' tries again."
  else
    echo "  Skipped; './run.sh alias-setup' installs it any time."
  fi
  mkdir -p .build-state && echo "answered in setup" > .build-state/.completion-checked   # no second offer from run.sh
  echo
fi
echo "Next: ./run.sh <workshop-name>"
