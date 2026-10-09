#!/bin/sh
# Recommends WEB_TERMINAL_MEM_LIMIT / WEB_TERMINAL_PIDS_LIMIT /
# CODE_SERVER_MAX_HEAP_MB for .env, sized to the machine this script
# actually runs on (your Mac's podman machine, or the Azure VM) rather than
# the fixed formula in .env.example.
#
# Usage (normally via dojo; `./dojo capacity --help` lists every flag):
#   ./dojo capacity --students 30
#   ./dojo capacity --students 30 --heap-mb 512 --margin-pct 30
#   ./dojo capacity --students 30 --host-mem-mb 32768   # plan for
#     a VM you haven't provisioned yet -- skips auto-detection
#
# Best accuracy: run `./dojo <workshop> --test` first so a couple of bot
# students (see README's "Demo bots") are live in workshop_terminal, then run
# this script while they're up -- it measures their real per-student private memory and
# scales that to --students instead of estimating. Note: --test bots alone
# only exercise the terminal; they won't spawn a code-server's extensionHost/
# ptyHost/etc unless something actually opens /ide for them too (a real
# browser, or `wget --post-data='' http://127.0.0.1:7682/start/ide/<user>`
# from inside the container) -- calibration without that undercounts.
#
# Timing: CODE_SERVER_IDLE_TIMEOUT_SECONDS / RECONNECTION_GRACE_SECONDS
# (workspace-control.py) reap an IDE once its browser tab has been gone that
# long, so calibrate while the students you're measuring are actually
# connected. Readings that look like disconnected IDEs are ignored below.
#
# Run this ON the target machine (or pass --host-mem-mb for one you haven't
# provisioned yet). It needs *that* machine's memory (the Azure VM's, or --
# on a Mac -- the podman machine's allocated memory, not the Mac's own),
# because that's the actual constraint `mem_limit` has to fit inside.
set -eu

cd "$(dirname "$0")/.."

STUDENTS=""
HEAP_MB="${CODE_SERVER_MAX_HEAP_MB:-384}"
PROCS_PER_STUDENT=5     # code-server entry + extensionHost + ptyHost + fileWatcher + one language server, observed live -- see note below
RESERVE_MB=1024         # host OS + docker/podman daemon headroom
# git-server(2g) + presentation(512m) + allocator(256m) + gateway(256m) --
# matches the mem_limits docker-compose.yml sets on those four services, so
# this reserve is an enforced ceiling, not just an observed-idle guess.
OTHER_SERVICES_MB=3072
# What OTHER_SERVICES_MB counts, for the report. `./dojo capacity WORKSHOP` passes the real total of that
# workshop's services (modules included) and names it here.
OTHER_SERVICES_FROM="the engine's 4 services only; name a workshop to count its modules too"
MARGIN_PCT=15            # extra headroom applied on top of whichever per-student estimate is used
HOST_MEM_MB_OVERRIDE=""

usage() {
  cat <<'EOF'
Usage: ./dojo capacity [WORKSHOP] --students N [options]

With WORKSHOP, every service that workshop starts (its modules included) counts
towards the memory left for students, not just the engine's four.

Recommends WEB_TERMINAL_MEM_LIMIT / WEB_TERMINAL_PIDS_LIMIT /
CODE_SERVER_MAX_HEAP_MB for .env, sized to the machine it runs on.
Run it ON the target machine, ideally with a couple of './dojo <workshop>
--test' bot students live so it can measure real per-student memory.

Required:
  --students N              number of concurrent students to size for

Options:
  --heap-mb MB              per-process code-server heap cap
                            (default: $CODE_SERVER_MAX_HEAP_MB or 384)
  --margin-pct PCT          headroom added to the per-student estimate
                            (default: 15)
  --host-mem-mb MB          plan for a machine you haven't provisioned yet;
                            skips memory auto-detection
  --procs-per-student N     node processes assumed per student for the
                            worst-case ceiling (default: 5)
  --reserve-mb MB           host OS + container-daemon headroom (default: 1024)
  --other-services-mb MB    combined mem_limits of every service but the
                            terminal (default: 3072, the engine's four;
                            set for you when WORKSHOP is given)
  -h, --help                show this message
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --students) STUDENTS="$2"; shift 2 ;;
    --heap-mb) HEAP_MB="$2"; shift 2 ;;
    --procs-per-student) PROCS_PER_STUDENT="$2"; shift 2 ;;
    --reserve-mb) RESERVE_MB="$2"; shift 2 ;;
    --other-services-mb) OTHER_SERVICES_MB="$2"; shift 2 ;;
    --other-services-from) OTHER_SERVICES_FROM="$2"; shift 2 ;;
    --margin-pct) MARGIN_PCT="$2"; shift 2 ;;
    --host-mem-mb) HOST_MEM_MB_OVERRIDE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

if [ -z "$STUDENTS" ]; then
  echo "--students is required." >&2
  usage >&2
  exit 1
fi

# shellcheck source=lib.sh
. ./scripts/lib.sh
runtime() { "$dojo_cli" "$@"; }

# --- Detect the memory this container's mem_limit actually has to share --
# On a real Linux VM (the Azure path), that's just the host's own RAM. On a
# Mac, `docker`/`podman` talk to a VM (podman machine / Docker Desktop's
# own VM) with its own fixed memory allocation, which is what actually
# bounds the container -- not the Mac's physical RAM.
detect_host_mem_mb() {
  if [ -n "$HOST_MEM_MB_OVERRIDE" ]; then
    echo "$HOST_MEM_MB_OVERRIDE"
    return
  fi
  if [ "$(uname -s)" = "Linux" ]; then
    awk '/MemTotal/{printf "%d", $2/1024}' /proc/meminfo
    return
  fi
  # macOS: prefer the podman machine's own allocation if one is running.
  if command -v podman >/dev/null 2>&1; then
    pm_mem=$(podman machine inspect 2>/dev/null | awk -F': *' '/"Memory"/{gsub(/[," ]/,"",$2); print $2; exit}')
    if [ -n "${pm_mem:-}" ]; then
      echo "$pm_mem"
      return
    fi
  fi
  # Docker Desktop or no VM info available -- fall back to the Mac's own
  # RAM, with a note in the output that this is likely an overestimate.
  awk 'BEGIN{print int('"$(sysctl -n hw.memsize)"'/1024/1024)}'
}

HOST_MEM_MB=$(detect_host_mem_mb)
HOST_MEM_SOURCE="detected"
[ -n "$HOST_MEM_MB_OVERRIDE" ] && HOST_MEM_SOURCE="--host-mem-mb override (planning only -- not measured)"

# --- Try to calibrate from a live workshop_terminal container ------------
LIVE_STUDENTS=0
LIVE_TOTAL_MB=0
LIVE_BASE_MB=0
# Private memory per process (RssAnon + RssShmem from /proc/<pid>/status),
# not RSS: every code-server node process maps the same ~124MB `node`
# binary and shared libraries, and RSS (VmRSS) counts those file-backed
# pages in full for each process -- one student read ~1GB by RSS, of which
# ~200MB was RssFile, while the container cgroup was charged only ~30MB of
# file cache for the lot. RssAnon summed to 303MB against the cgroup's own
# anon counter of 314MB in a side-by-side check. /proc/<pid>/status is
# readable for every uid; PSS (smaps_rollup) would be closer still but
# needs CAP_SYS_PTRACE to read another uid's processes, which this
# container doesn't have -- it silently returns nothing for students.
# Emits "<user> <kB> <1 if this is a code-server extension host, else 0>"
# lines, same shape as the `ps` fallback below. The extension host only
# exists while that account's IDE is open in a browser, which is what
# decides whether a student counts for calibration (see below).
MEM_SCRIPT='for p in /proc/[0-9]*; do
  u=$(stat -c %U "$p" 2>/dev/null) || continue
  kb=$(awk "/^(RssAnon|RssShmem):/{s+=\$2} END{print s+0}" "$p/status" 2>/dev/null)
  eh=0; grep -qa -- --type=extensionHost "$p/cmdline" 2>/dev/null && eh=1
  [ -n "$kb" ] && echo "$u $kb $eh"
done'
if runtime inspect workshop_terminal >/dev/null 2>&1; then
  PS_OUT=$(runtime exec workshop_terminal sh -c "$MEM_SCRIPT" 2>/dev/null || true)
  # /proc/<pid>/status unreadable (unusual runtime): fall back to RSS,
  # which overstates a bit but errs on the safe side.
  [ -n "$PS_OUT" ] || PS_OUT=$(runtime exec workshop_terminal ps -eo user:20,rss,args --no-headers 2>/dev/null \
    | awk '{ print $1, $2, (index($0, "--type=extensionHost") ? 1 : 0) }' || true)
  if [ -n "$PS_OUT" ]; then
    LIVE_BASE_MB=$(echo "$PS_OUT" | awk '$1=="root"{sum+=$2} END{printf "%d", sum/1024}')
    STUDENT_PREFIX="${STUDENT_PREFIX:-student}"
    # Only students whose IDE is connected (an extension host is running)
    # count: one without it -- tab never opened, or already reaped after
    # CODE_SERVER_RECONNECTION_GRACE_SECONDS / IDLE_TIMEOUT_SECONDS -- holds
    # a fraction of what a full room costs and would drag the average down.
    CALIBRATION=$(echo "$PS_OUT" | awk -v pfx="$STUDENT_PREFIX" '
      $1 ~ "^"pfx"[0-9]+$" { sum[$1]+=$2; users[$1]=1; if ($3 == 1) connected[$1]=1 }
      END {
        n=0; total=0; idle=0
        for (u in users) { if (u in connected) { n++; total+=sum[u] } else idle++ }
        printf "%d %d %d", n, total/1024, idle
      }')
    LIVE_STUDENTS=$(echo "$CALIBRATION" | cut -d' ' -f1)
    LIVE_TOTAL_MB=$(echo "$CALIBRATION" | cut -d' ' -f2)
    LIVE_IDLE_STUDENTS=$(echo "$CALIBRATION" | cut -d' ' -f3)
  fi
fi

# Two theoretical numbers when there's no live data to calibrate from:
#   - BASELINE_PER_STUDENT_MB: a working rule of thumb, used for the actual
#     recommendation below. An earlier real 2-student session on a Mac
#     measured 3x+ over the engine/README.md's old 400MB/student figure
#     (partly real, partly that Mac's qemu-emulation tax before
#     web-terminal was rebuilt arm64-native), which set this to 800.
#     Re-measured natively on amd64 (PSS, fresh session, a .py and a .yml
#     file open): ~480MB, and 650 is that plus ~35% for terminals, git, and
#     a session that has been running an hour instead of a minute. Since
#     the extension trim and code-server node flags (f977209) a connected
#     student measures ~260MB PSS / ~240MB private (3 at once), so 650 is
#     now conservative; kept until a long session has been measured. Prefer
#     live calibration below when you can get it.
#   - CEILING_PER_STUDENT_MB: every node process a student can spawn
#     (entry + extensionHost + ptyHost + fileWatcher + a language server)
#     simultaneously maxing its own CODE_SERVER_MAX_HEAP_MB heap cap. This
#     is a pessimistic upper bound, not a typical case -- shown as a
#     stress-test sanity check, not used to size WEB_TERMINAL_MEM_LIMIT by
#     default, or you'll oversize the VM for a case that rarely happens.
BASELINE_PER_STUDENT_MB=650
CEILING_PER_STUDENT_MB=$(( PROCS_PER_STUDENT * HEAP_MB ))

LIVE_IGNORED_NOTE=""
if [ "${LIVE_IDLE_STUDENTS:-0}" -gt 0 ]; then
  LIVE_IGNORED_NOTE="Left out ${LIVE_IDLE_STUDENTS} live student(s) whose IDE isn't open in a browser (no extension host, or already reaped after CODE_SERVER_RECONNECTION_GRACE_SECONDS). Open /ide for each bot in a browser, then re-run within CODE_SERVER_IDLE_TIMEOUT_SECONDS. "
fi
if [ "$LIVE_STUDENTS" -gt 0 ]; then
  PER_STUDENT_MB=$(( (LIVE_TOTAL_MB * (100 + MARGIN_PCT) / 100) / LIVE_STUDENTS ))
  BASE_MB=$(( LIVE_BASE_MB > 128 ? LIVE_BASE_MB : 128 ))
  SOURCE="calibrated from $LIVE_STUDENTS live student(s) in workshop_terminal (measured ${LIVE_TOTAL_MB}MB total private memory, ${LIVE_BASE_MB}MB base) + ${MARGIN_PCT}% margin"
else
  PER_STUDENT_MB=$(( BASELINE_PER_STUDENT_MB * (100 + MARGIN_PCT) / 100 ))
  BASE_MB=512
  SOURCE="revised baseline (${BASELINE_PER_STUDENT_MB}MB/student + ${MARGIN_PCT}% margin) -- no live students found to calibrate against. For a real number instead of a rule of thumb, run './dojo <workshop> --test' first (then start /ide for each bot too -- see header comment), then re-run this script. Worst-case ceiling if every student maxes every node process's heap at once: ${CEILING_PER_STUDENT_MB}MB/student -- treat that as a stress-test check, not the sizing target."
fi

MEM_LIMIT_MB=$(( BASE_MB + STUDENTS * PER_STUDENT_MB ))
MEM_LIMIT_GB=$(( (MEM_LIMIT_MB + 1023) / 1024 ))
if [ "$MEM_LIMIT_GB" -lt 1 ]; then MEM_LIMIT_GB=1; fi

# Sustained-activity default (40 pids/student + a fixed base) rather than
# the lighter 30/student rule of thumb -- a full 1-2hr session with every
# student active the whole time tends to accumulate more terminal
# tabs/background processes per student than a quick smoke test does.
PIDS_LIMIT=$(( STUDENTS * 40 + 200 ))

TOTAL_NEEDED_MB=$(( MEM_LIMIT_MB + OTHER_SERVICES_MB + RESERVE_MB ))

echo "== Capacity calculator =========================================="
echo "Host/VM memory (${HOST_MEM_SOURCE}): ${HOST_MEM_MB}MB"
echo "Per-student estimate source: $SOURCE"
if [ -n "$LIVE_IGNORED_NOTE" ]; then
  echo "NOTE: ${LIVE_IGNORED_NOTE% }"
fi
if [ "$LIVE_STUDENTS" -eq 0 ]; then
  echo "NOTE: the ${BASELINE_PER_STUDENT_MB}MB baseline is a fresh-session figure. A session that has run for an hour, with"
  echo "      every student in their IDE, can use more; WEB_TERMINAL_MEM_LIMIT is the only backstop for that."
fi
echo "Per-student memory estimate: ${PER_STUDENT_MB}MB"
echo "Container base overhead:     ${BASE_MB}MB"
echo "Other services' mem_limits: ${OTHER_SERVICES_MB}MB (${OTHER_SERVICES_FROM})"
echo "OS/daemon reserve:           ${RESERVE_MB}MB"
echo "-------------------------------------------------------------------"
echo "Recommended .env values for --students $STUDENTS:"
echo ""
echo "  WEB_TERMINAL_MEM_LIMIT=${MEM_LIMIT_GB}g"
echo "  WEB_TERMINAL_PIDS_LIMIT=${PIDS_LIMIT}"
echo "  CODE_SERVER_MAX_HEAP_MB=${HEAP_MB}"
echo ""
echo "Total host memory this plan needs: ${TOTAL_NEEDED_MB}MB"

if [ "$TOTAL_NEEDED_MB" -gt "$HOST_MEM_MB" ]; then
  echo ""
  echo "WARNING: that exceeds the ${HOST_MEM_MB}MB detected on this machine"
  echo "by $(( TOTAL_NEEDED_MB - HOST_MEM_MB ))MB. Options:"
  echo "  - Size up the VM (or the podman machine: 'podman machine set --memory <MB>')."
  echo "  - Lower --students for this machine."
  FIT_HEAP=$(( (HOST_MEM_MB - RESERVE_MB - OTHER_SERVICES_MB - BASE_MB) / (STUDENTS * PROCS_PER_STUDENT) ))
  if [ "$FIT_HEAP" -ge 160 ]; then
    echo "  - Lower CODE_SERVER_MAX_HEAP_MB to about ${FIT_HEAP} to fit $STUDENTS students here."
  else
    echo "  - $STUDENTS students won't fit safely on this machine even at a tight heap cap; reduce --students."
  fi
fi
echo "===================================================================="
