#!/bin/sh
# Central entry point for the project: select and build a workshop, and
# front the helper scripts under engine/scripts/. Run it from the repo root
# (./run.sh, a thin forwarder to this file) or from engine/ -- same thing.
#
# Usage:
#   ./run.sh setup [--default] [--force]  # create engine/.env (scripts/env-setup.sh; --rotate-class: new class password)
#   ./run.sh capacity --students N [...]  # size the terminal limits (scripts/capacity-calc.sh)
#   ./run.sh <workshop-name>              # e.g. ./run.sh dns-as-code
#   ./run.sh <workshop-name> --test       # also spin up demo/test bot students (3)
#   ./run.sh <workshop-name> --test 14    # ...or N bots: 1-3 fixed personas, rest random
#   ./run.sh <workshop-name> --dry-run    # preview: what would rebuild/start, builds nothing
#   ./run.sh <workshop-name> --env home   # also load engine/.env.home on top of engine/.env
#   ./run.sh list                         # show available workshops
#   ./run.sh modules                      # show available modules and who uses them
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
# non-interactive context such as CI or a --test bot run). Not offered
# ahead of help or stop either: asking a question before printing usage (or
# tearing down) is the wrong first thing to do.
case "${1:-}" in
  help | -h | --help | stop | teardown) ;;
  *)
    if [ "$dry_run" = "0" ] && [ -f ./scripts/install-completion.sh ]; then
      ./scripts/install-completion.sh
    fi ;;
esac

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
  <workshop-name> [--test [N]] [--env NAME] [--dry-run] [--allow-default-passwords]
                                build and start a workshop; --test also starts
                                demo bot students (3 by default, or N, max 35:
                                testuser1-3 are expert/intermediate/novice, any
                                beyond that get a random one of those three);
                                --env NAME loads engine/.env.NAME on top of
                                engine/.env (e.g. another address or port);
                                --dry-run only previews what would be rebuilt
                                and started; default passwords are refused
                                unless PUBLIC_BASE_URL and LAB_HOST_IP are
                                loopback (--allow-default-passwords overrides)
  list                          show available workshops
  modules                       show available modules (../modules/) and which
                                workshops use them (MODULES= in workshop.env)
  setup [--default] [--force]   create engine/.env (--rotate-class: new class
                                password only)
  capacity --students N [...]   size the terminal resource limits for this machine
  stop | teardown [--dry-run]   stop the stack and wipe ALL volumes (irreversible);
                                --dry-run lists what would be removed instead
  help | -h | --help            show this message

Run './run.sh <command> --help' for a command's own options,
e.g. './run.sh capacity --help'.
EOF
}

# Status colours for the change checks: green = unchanged, yellow = changed
# (build output itself stays in the default colours). Off when stdout isn't
# a terminal or NO_COLOR is set.
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  c_green="$(printf '\033[32m')"; c_yellow="$(printf '\033[33m')"
  c_red="$(printf '\033[31m')"; c_off="$(printf '\033[0m')"
  c_cyan="$(printf '\033[1;36m')"; c_dim="$(printf '\033[2m')"
else
  c_green=""; c_yellow=""; c_red=""; c_off=""; c_cyan=""; c_dim=""
fi
# A phase heading: bold cyan, so the steps stand out from build and compose output.
say_step() { printf '%s==> %s%s\n' "$c_cyan" "$*" "$c_off"; }
say_ok() { printf '  %s%s%s\n' "$c_green" "$*" "$c_off"; }
say_changed() { printf '  %s%s%s\n' "$c_yellow" "$*" "$c_off"; }
say_bad() { printf '  %s%s%s\n' "$c_red" "$*" "$c_off"; }

# Elapsed time as m:ss, for the progress lines below.
fmt_elapsed() { printf '%d:%02d' "$(($1 / 60))" "$(($1 % 60))"; }

# The same information as progress_watch as one block that redraws in place (a
# terminal only; compose's own output goes to a log so it can't scramble it).
# table_draw prints the block once, over the previous one; table_loop repeats it.
table_draw() {
  td_lines=0; [ ! -s "$tbl_state" ] || td_lines="$(cat "$tbl_state")"
  td_rows="$(ps_all --filter name=workshop_ --format '{{.Names}}|{{.Status}}' 2>/dev/null | awk -F'|' '
    { st = $2; s = "running"
      if (st ~ /\(unhealthy\)/) s = "unhealthy"
      else if (st ~ /\(healthy\)/) s = "healthy"
      else if (st ~ /health: starting|\(starting\)/) s = "starting"
      else if (st ~ /^Exited \(0\)/) s = "done"
      else if (st ~ /^Exited/) s = "FAILED"
      else if (st ~ /^(Created|Initialized)/) s = "waiting"
      print $1 "|" s }' | sort)"
  td_total="$(printf '%s\n' "$td_rows" | grep -c . || true)"
  td_ready="$(printf '%s\n' "$td_rows" | grep -c '|\(healthy\|running\|done\)$' || true)"
  td_vols="$(vol_ls -q 2>/dev/null | grep -c '^engine_' || true)"
  td_now="$(date +%s)"
  td_max="$(stty size 2>/dev/null | cut -d' ' -f1)"; [ "${td_max:-0}" -gt 0 ] 2>/dev/null || td_max=30
  out="$(printf '  %s%s%s   %s%s of %s ready%s   volumes: %s\n' "$c_dim" "$(fmt_elapsed $((td_now - up_start)))" "$c_off" "$c_cyan" "$td_ready" "$td_total" "$c_off" "$td_vols")"
  # Too many rows for the window: show only what isn't ready yet.
  if [ "$td_total" -gt $((td_max - 5)) ]; then
    td_show="$(printf '%s\n' "$td_rows" | grep -v '|\(healthy\|running\|done\)$')"
  else
    td_show="$td_rows"
  fi
  if [ -n "$td_show" ]; then
    out="${out}
$(printf '%s\n' "$td_show" | awk -F'|' -v g="$c_green" -v y="$c_yellow" -v r="$c_red" -v o="$c_off" '
      { col = y
        if ($2 == "healthy" || $2 == "running" || $2 == "done") col = g
        else if ($2 == "unhealthy" || $2 == "FAILED") col = r
        mark = (col == g) ? "+" : ((col == r) ? "x" : "~")
        printf "  %s%s %-36s %s%s\n", col, mark, $1, $2, o }')"
  fi
  waiting="$(printf '%s\n' "$td_rows" | awk -F'|' '$2 != "healthy" && $2 != "running" && $2 != "done" { printf "%s%s", sep, $1; sep = ", " }')"
  [ -z "$waiting" ] || out="${out}
  ${c_yellow}waiting on: ${waiting}${c_off}"
  # Erase and reprint in one go, after the slow docker calls above, so the block never sits blank.
  [ "$td_lines" -eq 0 ] || printf '\033[%dA' "$td_lines"
  printf '%s\n' "$out" | awk '{ printf "%s\033[K\n", $0 }'
  [ "$td_lines" -le "$(printf '%s\n' "$out" | wc -l)" ] || printf '\033[J'
  printf '%s\n' "$(printf '%s\n' "$out" | wc -l)" > "$tbl_state"
}
table_loop() {
  while :; do table_draw; sleep 1; done
}

# `compose up -d` can return while containers are still starting (health checks
# take longer than compose waits). Keep the progress display running until none
# is starting any more, or STARTUP_WAIT seconds (default 300) have passed.
not_ready_list() {
  ps_all --filter name=workshop_ --format '{{.Names}}|{{.Status}}' 2>/dev/null | awk -F'|' '$2 ~ /^Created|^Initialized|\(unhealthy\)|health: starting|\(starting\)|^Exited \([1-9]/ { printf "%s%s (%s)", sep, $1, $2; sep = ", " }'
}
wait_until_ready() {
  wr_end=$(($(date +%s) + ${STARTUP_WAIT:-300}))
  while [ -n "$(not_ready_list)" ] && [ "$(date +%s)" -lt "$wr_end" ]; do sleep 2; done
}

# `compose up -d` prints little while it waits on a container, so a slow start
# looks hung. This runs beside it and prints one line whenever a workshop_*
# container changes state (created, starting, healthy, exited), and every 30 s
# a list of what is still not ready, so you can see which one is holding things up.
progress_watch() {
  pw_start="$(date +%s)"; pw_prev="$(mktemp)"; pw_cur="$(mktemp)"; pw_quiet=0
  while :; do
    ps_all --filter name=workshop_ --format '{{.Names}}|{{.Status}}' 2>/dev/null | awk -F'|' '
      { st = $2; s = "running"
        if (st ~ /\(unhealthy\)/) s = "unhealthy"
        else if (st ~ /\(healthy\)/) s = "healthy"
        else if (st ~ /health: starting|\(starting\)/) s = "starting"
        else if (st ~ /^Exited \(0\)/) s = "done"
        else if (st ~ /^Exited/) s = "FAILED (" st ")"
        else if (st ~ /^(Created|Initialized)/) s = "waiting to start"
        print $1 "|" s }' | sort > "$pw_cur"
    changed="$(awk -F'|' -v pf="$pw_prev" 'BEGIN { while ((getline l < pf) > 0) { split(l, a, "|"); p[a[1]] = a[2] } } p[$1] != $2 { printf "%s: %s\n", $1, $2 }' "$pw_cur")"
    now="$(date +%s)"
    if [ -n "$changed" ]; then
      pw_quiet=0
      printf '%s\n' "$changed" | while IFS= read -r line; do
        case "$line" in
          *": healthy"|*": running"|*": done") col="$c_green" ;;
          *FAILED*|*unhealthy*) col="$c_red" ;;
          *) col="$c_yellow" ;;
        esac
        printf '  %s[%s]%s %s%s%s\n' "$c_dim" "$(fmt_elapsed $((now - pw_start)))" "$c_off" "$col" "$line" "$c_off"
      done
    else
      pw_quiet=$((pw_quiet + 5))
      if [ "$pw_quiet" -ge 30 ]; then
        pw_quiet=0
        waiting="$(awk -F'|' '$2 != "healthy" && $2 != "running" && $2 != "done" { printf "%s%s (%s)", sep, $1, $2; sep = ", " }' "$pw_cur")"
        [ -z "$waiting" ] || printf '  %s[%s]%s %sstill waiting on: %s%s\n' "$c_dim" "$(fmt_elapsed $((now - pw_start)))" "$c_off" "$c_yellow" "$waiting" "$c_off"
      fi
    fi
    cp "$pw_cur" "$pw_prev"
    sleep 5
  done
}

# Listed in learning-path order: WORKSHOP_ORDER= in workshop.env (0 = showcase,
# 1.. = the path); workshops without one come last, alphabetically.
list_workshops() {
  echo "Available workshops (in learning-path order):"
  for d in ../workshops/*/; do
    name="$(basename "$d")"
    [ -f "${d}workshop.env" ] || continue
    order="$(sed -n 's/^WORKSHOP_ORDER=//p' "${d}workshop.env" | head -1 | sed 's/[[:space:]]*#.*//' | tr -d '"')"
    case "$order" in '' | *[!0-9]*) order=99 ;; esac
    title="$(sed -n 's/^WORKSHOP_NAME=//p' "${d}workshop.env" | head -1 | tr -d '"')"
    case "$name" in
      setup | capacity | stop | teardown | help | list | modules)
        title="(unreachable: '${name}' is also a command, rename the folder)" ;;
    esac
    printf '%02d\t%s\t%s\n' "$order" "$name" "${title:-}"
  done | sort -t "$(printf '\t')" -k1,1n -k2,2 | while IFS="$(printf '\t')" read -r order name title; do
    if [ "$order" = 99 ]; then n=' '; else n="${order#0}"; n="${n:-0}"; fi
    printf '  %s  %-20s %s\n' "$n" "$name" "$title"
  done
}

# A module's summary is the first plain line of its README.md, after the
# heading (keep it to one short line); "used by" reads each MODULES= line.
list_modules() {
  echo "Available modules (add to a workshop with MODULES=\"name ...\" in its workshop.env):"
  for d in ../modules/*/; do
    [ -d "$d" ] || continue
    name="$(basename "$d")"
    summary=""
    if [ -f "${d}README.md" ]; then
      summary="$(grep -v -e '^#' -e '^[[:space:]]*$' "${d}README.md" | head -1 | tr -d '*' | cut -c1-80)"
    fi
    users=""
    for w in ../workshops/*/workshop.env; do
      [ -f "$w" ] || continue
      mods="$(sed -n 's/^MODULES=//p' "$w" | tail -1 | tr -d '"'"'")"
      case " ${mods} " in
        *" ${name} "*) users="${users:+${users}, }$(basename "$(dirname "$w")")" ;;
      esac
    done
    printf '  %-20s %s\n' "$name" "${summary}"
    printf '  %-20s used by: %s\n' "" "${users:-(none)}"
  done
}

# list and modules take no options; --help shows the overview, anything else
# is an error rather than silently ignored.
case "${1:-}" in
  list | modules)
    case "${2:-}" in
      '') ;;
      -h | --help)
        usage
        exit 0 ;;
      *)
        echo "Unrecognized argument: ${2} ('${1}' takes no options)" >&2
        exit 1 ;;
    esac ;;
esac

case "${1:-}" in
  modules)
    list_modules
    exit 0 ;;
  list)
    list_workshops
    exit 0 ;;
  help | -h | --help)
    usage
    echo
    list_workshops
    exit 0 ;;
  "")
    list_workshops
    echo
    usage
    exit 0 ;;
esac

workshop="$1"
shift
# Same rule as module names: the name becomes an image tag
# (gitopsdojo/web-terminal:<workshop>) and a state-file name, so a trailing
# '/' from path completion or a stray flag must fail here, before any build.
case "$workshop" in
  *[!a-z0-9-]* | -*)
    echo "'${workshop}' is not a workshop name (lowercase letters, digits and '-')." >&2
    echo "Usage: ./run.sh <workshop-name> [--test [N]] [--env NAME] [--dry-run] [--allow-default-passwords]" >&2
    echo "Run './run.sh list' to see available workshops." >&2
    exit 1 ;;
esac
test_mode=0
test_count=""
env_name=""
allow_default_passwords=0
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
    --env | --env=*)
      # Optional second env file, engine/.env.<NAME>, sourced after .env so
      # its values win. Keeps the everyday .env untouched while another
      # address (e.g. a LAN hostname with HTTPS) stays one flag away.
      if [ "$arg" = "--env" ]; then env_name="${1:-}"; [ "$#" -eq 0 ] || shift
      else env_name="${arg#--env=}"; fi
      case "$env_name" in
        '' | *[!a-z0-9-]* | -*)
          echo "--env expects a name (lowercase letters, digits and '-'), e.g. --env home" >&2
          exit 1 ;;
      esac ;;
    --dry-run) ;; # already picked up above
    --allow-default-passwords) allow_default_passwords=1 ;;
    -h | --help)
      usage
      exit 0 ;;
    *)
      echo "Unrecognized argument: ${arg}" >&2
      echo "Usage: ./run.sh <workshop-name> [--test [N]] [--env NAME] [--dry-run] [--allow-default-passwords]" >&2
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

if [ -n "$env_name" ] && [ ! -f ".env.${env_name}" ]; then
  echo "--env ${env_name}: engine/.env.${env_name} not found." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
if [ -n "$env_name" ]; then
  # shellcheck disable=SC1090
  . "./.env.${env_name}"
fi
# shellcheck disable=SC1091
. "$workshop_env"
set +a

# Modules (engine/MODULES-PLAN.md §4): MODULES="a b" in workshop.env pulls in
# ../modules/<name>/, found by convention. Each part is optional: module.env
# (defaults, sourced before workshop.env is re-read so the workshop wins),
# compose.yml, terminal/Dockerfile, extensions.json.
modules="${MODULES:-}"
for m in $modules; do
  case "$m" in
    *[!a-z0-9-]* | -*)
      echo "MODULES: '${m}' is not a module name (lowercase letters, digits and '-')." >&2
      exit 1 ;;
  esac
  if [ ! -d "../modules/${m}" ]; then
    echo "MODULES: no such module '${m}' (expected ../modules/${m}/)." >&2
    exit 1
  fi
done
if [ -n "$modules" ]; then
  set -a
  for m in $modules; do
    if [ -f "../modules/${m}/module.env" ]; then
      # shellcheck disable=SC1090
      . "../modules/${m}/module.env"
    fi
  done
  # shellcheck disable=SC1091
  . ./.env
  if [ -n "$env_name" ]; then
    # shellcheck disable=SC1090
    . "./.env.${env_name}"
  fi
  # shellcheck disable=SC1090
  . "$workshop_env"
  set +a
fi

# PUBLIC_BASE_URL is baked into links the lab prints (Forgejo clone URLs, the
# tofu-basics `url` output), so it has to name the port the gateway is
# published on. Warn rather than fail: a NAT or proxy in front can make a
# mismatch legitimate.
# Behind another proxy (GATEWAY_LISTEN set) the gateway's own address is the
# one that has to match the published port.
listen_url="${GATEWAY_LISTEN:-$PUBLIC_BASE_URL}"
url_scheme="${listen_url%%://*}"
url_hostport="${listen_url#*://}"; url_hostport="${url_hostport%%/*}"
case "$url_scheme" in
  https) gateway_port="${GATEWAY_HTTPS_PORT:-8443}"; url_port=443 ;;
  *)     gateway_port="${GATEWAY_HTTP_PORT:-8080}"; url_port=80 ;;
esac
case "$url_hostport" in *\]) ;; *:*) url_port="${url_hostport##*:}" ;; esac
if [ "$url_port" != "$gateway_port" ]; then
  echo "WARNING: ${listen_url} points at port ${url_port}, but the gateway" >&2
  echo "         is published on ${gateway_port}. Links the lab prints won't load; set" >&2
  echo "         PUBLIC_BASE_URL=${url_scheme}://${url_hostport%:*}:${gateway_port} in engine/.env." >&2
fi

# Default passwords (FIND-01): `setup --default`'s values and .env.example's
# placeholder are public, so they are only allowed when nothing but this
# machine can reach the gateway: a loopback PUBLIC_BASE_URL host and a loopback
# LAB_HOST_IP. Checked after .env.<name> and the modules, so --env wins.
public_host="${PUBLIC_BASE_URL#*://}"; public_host="${public_host%%/*}"
case "$public_host" in
  \[*\]*) public_host="${public_host%%\]*}"; public_host="${public_host#\[}" ;;
  *) public_host="${public_host%:*}" ;;
esac
case "$public_host:${LAB_HOST_IP:-}" in
  localhost:127.0.0.1 | 127.0.0.1:127.0.0.1 | ::1:127.0.0.1 | localhost:::1 | ::1:::1) local_only=1 ;;
  *) local_only=0 ;;
esac
default_passwords=""
# Without STUDENT_PASSWORD_SEED the shared STUDENT_PASSWORD is every
# student's Forgejo password, so it is checked instead of the seed.
if [ -n "${STUDENT_PASSWORD_SEED:-}" ]; then student_secret="STUDENT_PASSWORD_SEED:${STUDENT_PASSWORD_SEED}"
else student_secret="STUDENT_PASSWORD:${STUDENT_PASSWORD:-student123}"; fi
for pair in "TTYD_PASSWORD:${TTYD_PASSWORD:-}" "$student_secret" \
  "FACILITATOR_PASSWORD:${FACILITATOR_PASSWORD:-}" "FORGEJO_ADMIN_PASSWORD:${FORGEJO_ADMIN_PASSWORD:-}"; do
  case "${pair#*:}" in
    change-me | student | student123 | admin) default_passwords="${default_passwords} ${pair%%:*}" ;;
  esac
done
if [ -n "$default_passwords" ] && [ "$local_only" = "0" ]; then
  if [ "$allow_default_passwords" = "1" ] || [ "${ALLOW_DEFAULT_PASSWORDS:-0}" = "1" ]; then
    echo "WARNING: default passwords in use (${default_passwords# }) on ${PUBLIC_BASE_URL}," >&2
    echo "         reachable beyond this machine (--allow-default-passwords / ALLOW_DEFAULT_PASSWORDS=1)." >&2
  else
    echo "Refusing to start: default passwords (${default_passwords# }) with PUBLIC_BASE_URL=${PUBLIC_BASE_URL}" >&2
    echo "and LAB_HOST_IP=${LAB_HOST_IP:-<unset>}, i.e. reachable beyond this machine. Anyone who has seen" >&2
    echo "'./run.sh setup --default' can sign in. Generate real ones with './run.sh setup --force'" >&2
    echo "(then set PUBLIC_BASE_URL/LAB_HOST_IP again if engine/.env had them), or pass" >&2
    echo "--allow-default-passwords (or ALLOW_DEFAULT_PASSWORDS=1 in .env.<name>) to start anyway." >&2
    exit 1
  fi
fi

# An engine/.env from before per-student passwords (remediation T2.1b).
if [ -z "${STUDENT_PASSWORD_SEED:-}" ]; then
  echo "WARNING: no STUDENT_PASSWORD_SEED in engine/.env: every student's Forgejo password is the" >&2
  echo "         shared STUDENT_PASSWORD. Add one ('openssl rand -hex 32') or run './run.sh setup'." >&2
fi

# Plain HTTP off this machine (FIND-08): the class login, cookies and every
# keystroke in the terminal cross the network in the clear. A warning, not a
# refusal: a trusted LAN may be an accepted choice. Behind a TLS proxy
# (GATEWAY_LISTEN) PUBLIC_BASE_URL is https and this stays quiet.
case "${PUBLIC_BASE_URL%%://*}:$public_host" in
  http:localhost | http:127.0.0.1 | http:::1 | https:*) ;;
  *)
    echo "WARNING: PUBLIC_BASE_URL=${PUBLIC_BASE_URL} is plain HTTP beyond this machine: passwords," >&2
    echo "         cookies and terminal input travel unencrypted. For a class, use HTTPS: a real" >&2
    echo "         name, or a TLS proxy in front (engine/README.md, \"LAN class over HTTPS\")." >&2
    ;;
esac

if [ "$dry_run" = "1" ]; then
  echo "DRY RUN -- nothing will be built or started (manifests are checked in .generated/dry-run/)."
  echo "Workshop:  ${workshop} (${WORKSHOP_NAME:-$workshop})"
  echo "Content:   ${WORKSHOP_CONTENT_DIR:-<unset>}"
  echo "Modules:   ${modules:-none}"
  echo "Overlay:   ${COMPOSE_OVERLAY:-none}"
  echo
fi

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


# Prefer docker if it's actually present and working; fall back to podman
# otherwise (same detection teardown.sh uses, so both scripts agree on which
# engine is in play).
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  build() { docker build "$@"; }
  compose() { docker compose "$@"; }
  inspect() { docker inspect "$@"; }
  images() { docker images "$@"; }
  ps_all() { docker ps -a "$@"; }
  vol_ls() { docker volume ls "$@"; }
  rmi() { docker rmi "$@"; }
  # One-shot helper containers write into engine/ (render_extensions);
  # rootful docker would leave those files owned by root without --user.
  run_once() { docker run --rm --user "$(id -u):$(id -g)" "$@"; }
  build_salt=""
else
  build() { podman build "$@"; }
  compose() { podman-compose "$@"; }
  inspect() { podman inspect "$@"; }
  images() { podman images "$@"; }
  ps_all() { podman ps -a "$@"; }
  vol_ls() { podman volume ls "$@"; }
  rmi() { podman rmi "$@"; }
  # Rootless podman maps the container's root to the calling user already;
  # --user <uid> here would map to a subordinate uid that can't write engine/.
  run_once() { podman run --rm "$@"; }
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

# Mirrors content/lab/*.md into content/slides/lab/*.md.txt so the
# browser-only slides service (marp -s, ./presentation) can serve lab
# instructions read-only alongside the deck, without Marp trying to render
# them as slide decks -- Marp's server intercepts any .md path and converts
# it to a slide deck, but a .md.txt path falls through as a plain static
# file. workshops/assets/lab-reader.html fetches that raw text and renders
# it as a normal scrolling document. Runs on every `./run.sh <workshop>` so
# content/lab/*.md stays the single source of truth; the generated .md.txt
# copies are gitignored and never hand-edited.
sync_lab_docs() {
  content_dir="$1"
  lab_src="${content_dir}/lab"
  lab_dst="${content_dir}/slides/lab"
  [ -d "$lab_src" ] || return 0
  mkdir -p "$lab_dst"
  # Drop generated copies whose source was renamed or deleted since the
  # last run, before regenerating what's actually there now.
  for existing in "$lab_dst"/*.md.txt; do
    [ -e "$existing" ] || continue
    base="$(basename "$existing" .md.txt)"
    [ -f "${lab_src}/${base}.md" ] || rm -f "$existing"
  done
  for src in "$lab_src"/*.md; do
    [ -e "$src" ] || continue
    cp "$src" "${lab_dst}/$(basename "$src").txt"
  done
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
# track_superseded, which notes two kinds of image the build left untagged:
#   - one of ours (see our_tagged_image_ids) that had a tag before the build and
#     has none after it: exactly what that build displaced, whether or not it
#     carries our label;
#   - one that did not exist before the build at all: the non-final stage of a
#     multi-stage Dockerfile (presentation's `build`, cloud-host's `hello`).
#     Podman keeps those as <none> images; they never had a tag to lose.
# reap_superseded removes them at the very end of the run.
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

# IDs of the tagged images this project builds: gitopsdojo/* (our fixed tags)
# and Compose's own names for an overlay's services (engine_step-ca, or
# engine-step-ca on newer Compose). Only these are ever candidates for
# removal, so an image you tagged or built yourself in another terminal while
# a run is going is never mistaken for one this run displaced.
our_tagged_image_ids() {
  images --filter "dangling=false" --format '{{.ID}} {{.Repository}}' \
    | awk '$2 ~ /(^|\/)gitopsdojo\// || $2 ~ /(^|\/)engine[_-]/ { print $1 }' | sort -u
}

# Run the given build command, recording any image it left untagged.
track_superseded() {
  ids_before=" $(our_tagged_image_ids | tr '\n' ' ') "
  untagged_before=" $(image_ids true | tr '\n' ' ') "
  "$@"
  mkdir -p "$(dirname "$superseded_file")"
  for id in $(image_ids true); do
    case "$ids_before" in
      *" $id "*) echo "$id" >>"$superseded_file"; continue ;;
    esac
    case "$untagged_before" in
      *" $id "*) ;;
      *) echo "$id" >>"$superseded_file" ;;
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
    say_ok "${image}: unchanged"
    return 0
  fi
  if [ "$dry_run" = "1" ]; then
    say_changed "${image}: changed, would build"
    would_build="${would_build} ${image} "
    return 0
  fi
  say_changed "${image}: changed, building (this can take a few minutes)..."
  bstart="$(date +%s)"
  track_superseded build "$@" --label "dojo.src-hash=${new_hash}" -t "$image" "$context"
  say_ok "${image}: built in $(fmt_elapsed $(($(date +%s) - bstart)))"
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
#
# $1 is a space-separated list of directories (each module's, then the
# overlay's); a change in any of them rebuilds.
compose_overlay_build_if_changed() {
  overlay_dirs="$1"; state_file="$2"; shift 2
  new_hash="$(for d in $overlay_dirs; do hash_dir "$d"; done | sha256_cmd | awk '{print $1}')"
  old_hash=""
  [ -f "$state_file" ] && old_hash="$(cat "$state_file")"
  if [ "$old_hash" = "$new_hash" ]; then
    say_ok "overlay images: unchanged"
    return 0
  fi
  if [ "$dry_run" = "1" ]; then
    say_changed "overlay images: changed, would build"
    return 0
  fi
  say_changed "overlay images: changed, building..."
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
  say_step "Checking images (dry run)"
else
  say_step "Checking images"
fi
# A dry run builds nothing, so it can't see that a rebuilt base makes the
# workshop terminal (FROM base) stale too; build_if_changed records what it
# would build here so the workshop terminal below can say so.
would_build=""
# shellcheck disable=SC2086
build_if_changed gitopsdojo/web-terminal:base ./web-terminal $build_secret_args

# Terminal tools stack as a chain of builds (engine/MODULES-PLAN.md §4.2):
# :base -> each module's terminal/ (gitopsdojo/web-terminal:<workshop>.<module>)
# -> the workshop's compose/terminal/ (gitopsdojo/web-terminal:<workshop>).
# Every link's Dockerfile starts `ARG BASE` / `FROM ${BASE}` and is built with
# BASE set to the link before it. Never tagged ":base", which would clobber the
# shared base image for every other workshop. The last link is what the stack
# runs, passed to docker-compose.yml as WEB_TERMINAL_IMAGE.
terminal_links=""
for m in $modules; do
  if [ -d "../modules/${m}/terminal" ]; then
    terminal_links="${terminal_links} gitopsdojo/web-terminal:${workshop}.${m}=../modules/${m}/terminal"
  fi
done
if [ -d "${workshop_dir}/compose/terminal" ]; then
  terminal_links="${terminal_links} gitopsdojo/web-terminal:${workshop}=${workshop_dir}/compose/terminal"
fi
parent="gitopsdojo/web-terminal:base"
for link in $terminal_links; do
  image="${link%%=*}"
  # Each link is FROM its parent, so a rebuilt parent has to rebuild it too --
  # otherwise it stays on the old parent, which then can't be cleaned up.
  # Folding the parent's image ID into the hash does that; the directory's own
  # contents alone wouldn't change when only the parent did.
  saved_salt="$build_salt"
  build_salt="${build_salt}$(inspect -f '{{.Id}}' "$parent" 2>/dev/null || true)"
  case "$would_build" in
    *" ${parent} "*)
      say_changed "${image}: parent changed, would build"
      would_build="${would_build} ${image} " ;;
    *)
      # shellcheck disable=SC2086
      build_if_changed "$image" "${link#*=}" $build_secret_args --build-arg "BASE=${parent}" ;;
  esac
  build_salt="$saved_salt"
  parent="$image"
done
export WEB_TERMINAL_IMAGE="$parent"

build_if_changed gitopsdojo/allocator:local ./allocator
build_if_changed gitopsdojo/gateway:local ./gateway
build_if_changed gitopsdojo/presentation:local ./presentation

# Compose files: the engine's, each module's compose.yml in MODULES order,
# then the workshop's overlay (later files win on the same key).
extra_files=""
overlay_dirs=""
for m in $modules; do
  if [ -f "../modules/${m}/compose.yml" ]; then
    extra_files="${extra_files} ../modules/${m}/compose.yml"
    overlay_dirs="${overlay_dirs} ../modules/${m}"
  fi
done
if [ -n "${COMPOSE_OVERLAY:-}" ]; then
  extra_files="${extra_files} ${COMPOSE_OVERLAY}"
  overlay_dirs="${overlay_dirs} $(dirname "${COMPOSE_OVERLAY}")"
fi
compose_args="-f docker-compose.yml"
for f in $extra_files; do
  compose_args="$compose_args -f $f"
done

# terminal_ingress is the gateway's only path to the students' IDE and
# terminal ports (remediation T2.2a). A module or workshop service that
# joined it would get that path too, so no fragment may mention it.
for f in $extra_files; do
  if grep -n 'terminal_ingress\|web-terminal-ingress' "$f" >&2; then
    echo "Refusing to start: $f joins terminal_ingress, the gateway's private path to the" >&2
    echo "students' IDE and terminal ports. Use workshop_lab (see workshops/README.md)." >&2
    exit 1
  fi
done

# Any other build: blocks the modules and the overlay add beyond web-terminal
# (already handled above) -- e.g. forgejo-runner, cert-autorenewal's
# dns-seed/step-ca/demo-app -- only rebuild when one of those directories
# has actually changed since this workshop last ran.
if [ -n "$overlay_dirs" ]; then
  # shellcheck disable=SC2086
  compose_overlay_build_if_changed "$overlay_dirs" ".build-state/${workshop}.overlay-hash" $compose_args
fi

# Workshop extensions (engine/MODULES-PLAN.md §3): the workshop's
# extensions.json declares its routes, landing cards, /admin tabs and status
# checks. allocator/render_extensions.py checks it against this run's services and writes what the gateway imports
# and the allocator reads. A bad manifest stops here, before anything starts.
# A dry run renders into its own folder so a running stack's files stay put.
if [ "$dry_run" = "1" ]; then gen_dir=".generated/dry-run"; else gen_dir=".generated"; fi
rm -rf "${gen_dir:?}/in"
mkdir -p "${gen_dir}/in" "${gen_dir}/gateway" "${gen_dir}/allocator"
ext_env_args=""
# Modules first (50-...), in MODULES order, then the workshop (90-...).
n=10
for m in $modules; do
  if [ -f "../modules/${m}/extensions.json" ]; then
    cp "../modules/${m}/extensions.json" "${gen_dir}/in/50-${n}-module-${m}.json"
  fi
  n=$((n + 1))
done
if [ -f "${workshop_dir}/extensions.json" ]; then
  cp "${workshop_dir}/extensions.json" "${gen_dir}/in/90-workshop-${workshop}.json"
fi
# ${NAME} in a manifest may name any variable workshop.env or a module.env
# sets; pass just those (never .env, which holds secrets) through by name.
env_files="$workshop_env"
for m in $modules; do
  [ ! -f "../modules/${m}/module.env" ] || env_files="$env_files ../modules/${m}/module.env"
done
# shellcheck disable=SC2086
for key in $(cat $env_files | grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' | tr -d '=' | sort -u); do
  ext_env_args="$ext_env_args -e $key"
done
# shellcheck disable=SC2086
ext_services="$(compose $compose_args config --services 2>/dev/null | tr '\n' ' ')"
if [ -z "$ext_services" ]; then
  echo "Could not list this run's Compose services ('compose ${compose_args} config --services' failed)." >&2
  exit 1
fi
# The script is mounted from the source tree, not baked in, so a dry run
# (which builds nothing) still checks with the current rules; the image is
# only its Python.
if ! inspect gitopsdojo/allocator:local >/dev/null 2>&1; then
  echo "Extensions: not checked (the allocator image isn't built yet; a real run builds it first)."
else
  # shellcheck disable=SC2086
  # GATEWAY_TOKEN (by name, never on the command line) derives each
  # identity/facilitator upstream's own X-Gateway-Token (FIND-16).
  if ! run_once --network none $ext_env_args -e GATEWAY_TOKEN -v "$PWD/${gen_dir}:/gen" \
      -v "$PWD/allocator/render_extensions.py:/render_extensions.py:ro" gitopsdojo/allocator:local \
      python3 -B /render_extensions.py --in /gen/in --out /gen --services "$ext_services"; then
    echo "The workshop's extensions.json was rejected (see above); nothing was started." >&2
    exit 1
  fi
fi
# Each routed upstream's own gateway token, GATEWAY_TOKEN_<SERVICE>, for the
# compose fragments to pass in as that service's GATEWAY_TOKEN (FIND-16).
if [ -f "${gen_dir}/upstream-tokens.env" ]; then
  set -a
  # shellcheck disable=SC1090,SC1091
  . "./${gen_dir}/upstream-tokens.env"
  set +a
fi

# Record which module and overlay files this run used (in .last-overlay,
# below), so teardown.sh tears down with the exact same -f set instead of
# only ever seeing docker-compose.yml. Without this, `down` has no idea the
# extra services/volumes (e.g. forgejo-runner's runner-setup and
# runner_config volume) ever existed, and can't respect their depends_on
# ordering or clean up their volumes.
if [ "$dry_run" = "1" ]; then
  echo
  say_step "Checking the Compose config"
  # shellcheck disable=SC2086
  if compose $compose_args config >/dev/null 2>&1; then
    say_ok "valid"
  else
    say_bad "invalid: run 'compose ${compose_args} config' to see why"
  fi
  echo
  say_step "Checking image pins"
  # Every external FROM / image: needs a digest (FIND-18). Whole repo, so a
  # dry run of any workshop also catches a module or workshop it doesn't use.
  pins_ok=1
  if pins_out="$(sh scripts/check-pins.sh 2>&1)"; then
    say_ok "every external image pinned by digest"
  else
    pins_ok=0
    printf '%s\n' "$pins_out" | sed '$d' | sed '$d' | while IFS= read -r line; do say_bad "$line"; done
    say_bad "not pinned: add @sha256:<digest> (see scripts/check-pins.sh)"
  fi
  echo
  echo "Would run: compose ${compose_args} up -d"
  if [ "$pins_ok" = "0" ]; then
    echo "Dry run complete: nothing was built or started, but unpinned images were found." >&2
    exit 1
  fi
  echo "Dry run complete: nothing was built or started."
  exit 0
fi

# One extra -f file per line (modules, then the overlay); empty = engine only.
printf '%s\n' $extra_files > .last-overlay

sync_lab_docs "$WORKSHOP_CONTENT_DIR"
# A workshop that shows other workshops' slides (dojo-introduction) needs their
# lab copies too; they are cheap and git-ignored, so make them for every pack.
for other_content in ../workshops/*/content; do
  [ "$other_content" = "$WORKSHOP_CONTENT_DIR" ] || sync_lab_docs "$other_content"
done

say_step "Starting workshop '${workshop}' (${WORKSHOP_NAME:-$workshop})"
# No --build: every image Compose references was already brought up to
# date (or confirmed unchanged) above, either by build_if_changed (for the
# fixed-tag images) or compose_overlay_build_if_changed (for the rest of
# this workshop's overlay, if any).
say_step "Creating networks and volumes, then starting containers in dependency order"
echo "A line appears below whenever a container changes state; 'still waiting on' names what is holding things up."
up_start="$(date +%s)"
up_rc=0
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  # A terminal: one table that redraws in place. Compose's own output goes to a log.
  up_log="$(mktemp "${TMPDIR:-/tmp}/dojo-up.XXXXXX")"
  tbl_state="$(mktemp)"; echo 0 > "$tbl_state"
  echo "Compose output is in ${up_log}"
  printf '\033[?25l'
  table_loop &
  watch_pid=$!
  trap 'kill "$watch_pid" 2>/dev/null; printf "\033[?25h"' EXIT INT TERM
  # shellcheck disable=SC2086
  compose $compose_args up -d > "$up_log" 2>&1 || up_rc=$?
  [ "$up_rc" != 0 ] || wait_until_ready
  kill "$watch_pid" 2>/dev/null; wait "$watch_pid" 2>/dev/null || true
  table_draw
  printf '\033[?25h'
  trap - EXIT INT TERM
  rm -f "$tbl_state"
  if [ "$up_rc" != 0 ]; then
    say_bad "compose failed (exit ${up_rc}); the last lines of its output:"
    tail -n 20 "$up_log"
  fi
else
  echo "A line appears below whenever a container changes state; 'still waiting on' names what is holding things up."
  progress_watch &
  watch_pid=$!
  trap 'kill "$watch_pid" 2>/dev/null' EXIT INT TERM
  # shellcheck disable=SC2086
  compose $compose_args up -d || up_rc=$?
  [ "$up_rc" != 0 ] || wait_until_ready
  kill "$watch_pid" 2>/dev/null; wait "$watch_pid" 2>/dev/null || true
  trap - EXIT INT TERM
fi
say_ok "Compose finished in $(fmt_elapsed $(($(date +%s) - up_start)))"
not_ready="$(not_ready_list)"
[ -z "$not_ready" ] || say_changed "not ready yet: ${not_ready}"
[ "$up_rc" = 0 ] || exit "$up_rc"

# Containers now run on the freshly built images, so the ones those builds
# displaced are no longer pinned.
reap_superseded
