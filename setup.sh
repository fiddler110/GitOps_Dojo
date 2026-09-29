#!/usr/bin/env bash
# Guided host setup for GitOps Dojo.
#
# Works out what this machine still needs before `./run.sh <workshop>` can run
# (a container engine plus git and openssl), tells you what it found, and only
# installs anything after you say yes. Podman is the recommended engine; Docker
# works too. It never touches the stack itself and never runs a workshop.
#
#   ./setup.sh                          guided, asks before every change
#   ./setup.sh --check                  report only, install nothing
#   ./setup.sh --engine docker          skip the engine question
#   ./setup.sh --os macos               skip OS detection (wsl|linux|macos|windows)
#
# Written for bash 3.2 (the macOS default), so no associative arrays.

cd "$(dirname "$0")" || exit 1

CHECK_ONLY=0
OS=""
ENGINE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK_ONLY=1 ;;
    --engine) ENGINE="${2:-}"; shift ;;
    --os) OS="${2:-}"; shift ;;
    -h | --help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  c_green="$(printf '\033[32m')"; c_yellow="$(printf '\033[33m')"; c_red="$(printf '\033[31m')"
  c_cyan="$(printf '\033[1;36m')"; c_dim="$(printf '\033[2m')"; c_off="$(printf '\033[0m')"
else
  c_green=""; c_yellow=""; c_red=""; c_cyan=""; c_dim=""; c_off=""
fi
step() { printf '\n%s==> %s%s\n' "$c_cyan" "$*" "$c_off"; }
ok() { printf '  %s✓%s %s\n' "$c_green" "$c_off" "$*"; }
bad() { printf '  %s✗%s %s\n' "$c_red" "$c_off" "$*"; }
warn() { printf '  %s!%s %s\n' "$c_yellow" "$c_off" "$*"; }
note() { printf '    %s%s%s\n' "$c_dim" "$*" "$c_off"; }
have() { command -v "$1" >/dev/null 2>&1; }

# ask "question" default(y|n): returns 0 for yes. Empty answer or EOF takes the default.
ask() {
  local reply hint="[y/N]"
  [ "$2" = y ] && hint="[Y/n]"
  printf '%s %s ' "$1" "$hint"
  read -r reply || reply=""
  [ -z "$reply" ] && reply="$2"
  case "$reply" in y | Y | yes | YES) return 0 ;; *) return 1 ;; esac
}

# --- 1. Which OS? ------------------------------------------------------------

detect_os() {
  case "$(uname -s 2>/dev/null)" in
    Darwin) echo macos ;;
    MINGW* | MSYS* | CYGWIN*) echo windows ;;
    Linux)
      if grep -qi microsoft /proc/version 2>/dev/null; then echo wsl; else echo linux; fi ;;
    *) echo unknown ;;
  esac
}

os_label() {
  case "$1" in
    wsl) echo "Windows with WSL2 (Linux shell inside Windows)" ;;
    linux) echo "Linux" ;;
    macos) echo "macOS" ;;
    windows) echo "Windows, native shell (Git Bash / MSYS / Cygwin)" ;;
    *) echo "unknown" ;;
  esac
}

step "GitOps Dojo host setup"
if [ -z "$OS" ]; then
  guess="$(detect_os)"
  echo "  This looks like: $(os_label "$guess")"
  if [ "$guess" = unknown ] || ! ask "  Is that right?" y; then
    echo "  Which are you on?"
    echo "    1) Linux (Ubuntu/Debian/Fedora)"
    echo "    2) Windows, inside WSL2 Ubuntu"
    echo "    3) macOS"
    echo "    4) Windows, not using WSL yet"
    printf '  Choose 1-4: '
    read -r pick || pick=""
    case "$pick" in
      1) OS=linux ;; 2) OS=wsl ;; 3) OS=macos ;; 4) OS=windows ;;
      *) echo "No valid choice, stopping." >&2; exit 2 ;;
    esac
  else
    OS="$guess"
  fi
fi

# --- 2. Windows without WSL: nothing to install from here --------------------

if [ "$OS" = windows ]; then
  step "Windows needs WSL2 first"
  cat <<'EOF'
  The stack runs in Linux containers and run.sh is a bash script, so on Windows
  you use it from inside WSL2 with Ubuntu. Native PowerShell/Git Bash is not supported.

  1. Open PowerShell as Administrator and run:
       wsl --install -d Ubuntu
     then reboot if it asks, and finish the Ubuntu first-run user setup.
  2. Open the Ubuntu terminal and clone this repo INSIDE it, in your Linux home
     (for example ~/GitOps_Dojo), not under /mnt/c, which is slow and breaks file permissions.
  3. In that Ubuntu shell, run ./setup.sh again and pick the WSL option.

  Docker Desktop users: install it, turn on Settings > Resources > WSL integration
  for Ubuntu, and run this script from the Ubuntu shell (choose docker when asked).
EOF
  exit 0
fi

# --- 3. Which engine? --------------------------------------------------------

# Look at what is installed rather than asking. This mirrors run.sh: podman when podman and
# podman-compose are both there, docker otherwise.
if [ -z "$ENGINE" ]; then
  step "Which container engine?"
  if have podman-compose && have podman; then
    ENGINE=podman; ok "podman and podman-compose are installed; ./run.sh will use podman"
  elif have docker && docker compose version >/dev/null 2>&1; then
    ENGINE=docker; ok "docker with the compose plugin is installed; ./run.sh will use docker"
    have podman && warn "podman is installed too but has no podman-compose, so run.sh falls back to docker. Install podman-compose to prefer podman."
  elif have podman; then
    ENGINE=podman; warn "podman is installed but podman-compose is not"
  elif have docker; then
    ENGINE=docker; warn "docker is installed but the compose plugin is not"
  else
    echo "  Neither podman nor docker is installed."
    echo "  Recommended: podman + podman-compose (rootless, no root daemon, so it is the safer choice)."
    if ask "  Install podman and podman-compose?" y; then ENGINE=podman; else ENGINE=docker; fi
  fi
fi
case "$ENGINE" in podman | docker) ;; *) echo "Engine must be podman or docker." >&2; exit 2 ;; esac

if [ "$OS" = wsl ]; then
  case "$PWD" in
    /mnt/[a-z]/*) warn "This repo is on the Windows drive ($PWD). Move it into your Linux home; bind mounts and permissions misbehave here." ;;
  esac
fi

# --- 4. What is already here? ------------------------------------------------

PKG=""
if have apt-get; then PKG=apt; elif have dnf; then PKG=dnf; elif have brew; then PKG=brew; fi
[ "$OS" = macos ] && PKG=brew

engine_installed() {
  if [ "$ENGINE" = podman ]; then have podman && have podman-compose
  else have docker && docker compose version >/dev/null 2>&1; fi
}
engine_running() {
  if [ "$ENGINE" = podman ]; then podman info >/dev/null 2>&1; else docker info >/dev/null 2>&1; fi
}

inspect_host() {
  step "What this machine has ($ENGINE)"
  MISSING_TOOLS=""
  for t in git openssl; do
    if have "$t"; then ok "$t"; else bad "$t missing"; MISSING_TOOLS="$MISSING_TOOLS $t"; fi
  done
  MISSING_ENGINE=""
  if [ "$ENGINE" = podman ]; then
    if have podman; then ok "podman $(podman --version 2>/dev/null | awk '{print $NF}')"; else bad "podman missing"; MISSING_ENGINE="$MISSING_ENGINE podman"; fi
    if ! have podman-compose; then bad "podman-compose missing"; MISSING_ENGINE="$MISSING_ENGINE podman-compose"
    elif podman-compose version >/dev/null 2>&1; then ok "podman-compose $(podman-compose version 2>/dev/null | awk '/podman-compose version/{print $NF; exit}')"
    else bad "podman-compose is installed but 'podman-compose version' fails"; MISSING_ENGINE="$MISSING_ENGINE podman-compose"; fi
  else
    if have docker; then ok "docker $(docker --version 2>/dev/null | awk '{print $3}' | tr -d ,)"; else bad "docker missing"; MISSING_ENGINE="$MISSING_ENGINE docker"; fi
    if have docker && docker compose version >/dev/null 2>&1; then ok "docker compose plugin"; else bad "docker compose plugin missing"; MISSING_ENGINE="$MISSING_ENGINE compose"; fi
  fi
  if [ -n "$MISSING_ENGINE" ]; then
    RUNNING="skip"
  elif engine_running; then
    ok "$ENGINE works (can talk to its engine)"; RUNNING=yes
  else
    bad "$ENGINE is installed but not usable yet"; RUNNING=no
  fi
  # run.sh uses podman whenever podman and podman-compose are installed, even if you chose docker here.
  if [ "$ENGINE" = docker ] && have podman && have podman-compose; then
    warn "podman and podman-compose are also installed. ./run.sh prefers podman when both are present, so it will use podman."
    note "To run on docker, uninstall podman-compose."
  fi
}

inspect_host

# --- 5. Plan the installs ----------------------------------------------------

STEPS=()   # commands we can run for you
AFTER=()   # things only you can do (log out, start a VM)

plan_linux() {
  local pk="$MISSING_TOOLS $MISSING_ENGINE"
  case "$PKG" in
    apt)
      local pkgs=""
      for p in $MISSING_TOOLS; do pkgs="$pkgs $p"; done
      if [ "$ENGINE" = podman ]; then
        for p in $MISSING_ENGINE; do pkgs="$pkgs $p"; done
      elif [ -n "$MISSING_ENGINE" ]; then
        pkgs="$pkgs docker.io docker-compose-v2"
        note "docker-compose-v2 needs Ubuntu 24.04+ / Debian 13+. On older releases follow"
        note "https://docs.docker.com/engine/install/ubuntu/ for docker-compose-plugin instead."
      fi
      [ -n "$pkgs" ] && STEPS+=("sudo apt-get update && sudo apt-get install -y$pkgs")
      if [ "$ENGINE" = docker ] && ! id -nG | tr ' ' '\n' | grep -qx docker; then
        STEPS+=("sudo usermod -aG docker \"$USER\"")
        if [ "$OS" = wsl ]; then
          AFTER+=("Restart WSL so the docker group applies: in PowerShell run 'wsl --shutdown', then reopen Ubuntu.")
        else
          AFTER+=("Log out and back in so the docker group applies (or run 'newgrp docker').")
        fi
      fi ;;
    dnf)
      local pkgs=""
      for p in $MISSING_TOOLS; do pkgs="$pkgs $p"; done
      if [ "$ENGINE" = podman ]; then
        for p in $MISSING_ENGINE; do pkgs="$pkgs $p"; done
      elif [ -n "$MISSING_ENGINE" ]; then
        pkgs="$pkgs moby-engine docker-compose"
        STEPS+=("sudo systemctl enable --now docker")
      fi
      [ -n "$pkgs" ] && STEPS=("sudo dnf install -y$pkgs" "${STEPS[@]}") ;;
    *)
      AFTER+=("No apt or dnf found. Install with your package manager:$pk (podman needs podman-compose; docker needs the compose plugin).") ;;
  esac
}

plan_macos() {
  if ! have brew; then
    AFTER+=("Install Homebrew first: https://brew.sh (copy its one-line installer; this script won't pipe a download into your shell).")
    AFTER+=("Then run ./setup.sh again.")
    return
  fi
  if [ "$ENGINE" = podman ]; then
    local pkgs=""
    for p in $MISSING_ENGINE; do pkgs="$pkgs $p"; done
    [ -n "$pkgs" ] && STEPS+=("brew install$pkgs")
    if [ "$RUNNING" != yes ]; then
      STEPS+=("podman machine init")
      STEPS+=("podman machine start")
    fi
  else
    [ -n "$MISSING_ENGINE" ] && STEPS+=("brew install --cask docker")
    [ -n "$MISSING_ENGINE" ] || [ "$RUNNING" != yes ] && AFTER+=("Open Docker Desktop once (Applications > Docker) and wait until it says it is running.")
  fi
  for p in $MISSING_TOOLS; do
    [ "$p" = git ] && AFTER+=("Install git: run 'xcode-select --install' (or brew install git).")
    [ "$p" = openssl ] && STEPS+=("brew install openssl")
  done
}

plan_running() {
  # Installed but the engine isn't answering.
  [ -n "$MISSING_ENGINE" ] || [ "$RUNNING" != no ] && return
  if [ "$ENGINE" = docker ]; then
    if [ "$OS" = wsl ]; then
      AFTER+=("Start Docker Desktop on Windows (with WSL integration on for this distro), or 'sudo service docker start' if you installed Docker Engine inside WSL.")
    elif [ "$OS" = linux ]; then
      AFTER+=("Start the daemon: sudo systemctl enable --now docker (and make sure you are in the docker group).")
    fi
  else
    [ "$OS" != macos ] && AFTER+=("Run 'podman info' and read the error. Rootless podman needs entries for your user in /etc/subuid and /etc/subgid (sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 \"$USER\").")
  fi
}

if [ -n "$MISSING_TOOLS$MISSING_ENGINE" ] || [ "$RUNNING" = no ]; then
  case "$OS" in
    linux | wsl) plan_linux ;;
    macos) plan_macos ;;
  esac
  plan_running

  step "What's needed"
  if [ ${#STEPS[@]} -gt 0 ]; then
    echo "  I can run these for you (you'll be asked for your password where sudo is used):"
    for s in "${STEPS[@]}"; do printf '    %s$ %s%s\n' "$c_dim" "$s" "$c_off"; done
  fi
  if [ ${#AFTER[@]} -gt 0 ]; then
    echo "  You need to do these yourself:"
    for a in "${AFTER[@]}"; do printf '    - %s\n' "$a"; done
  fi

  if [ "$CHECK_ONLY" = 1 ]; then
    echo; echo "  --check: nothing installed."; exit 1
  fi

  if [ ${#STEPS[@]} -gt 0 ]; then
    echo
    if ask "  Run the commands above now?" n; then
      for s in "${STEPS[@]}"; do
        printf '  %s$ %s%s\n' "$c_dim" "$s" "$c_off"
        if ! bash -c "$s"; then
          bad "Command failed. Fix the error above, then run ./setup.sh again."; exit 1
        fi
      done
      inspect_host
    else
      echo "  Nothing was changed. Run the commands yourself, then run ./setup.sh again."
      exit 1
    fi
  fi

  if [ ${#AFTER[@]} -gt 0 ]; then
    echo
    warn "Finish the manual steps listed above, then run ./setup.sh again to confirm."
    exit 1
  fi
fi

if [ -n "$MISSING_TOOLS$MISSING_ENGINE" ] || [ "$RUNNING" != yes ]; then
  echo; bad "Still not ready. See the checks above."; exit 1
fi

# --- 6. Dojo config and next steps -------------------------------------------

step "Dojo configuration"
if [ -f engine/.env ]; then
  ok "engine/.env already exists"
elif [ "$CHECK_ONLY" = 1 ]; then
  warn "engine/.env not created yet (./run.sh setup makes it)"
elif ask "  Create engine/.env now (generates the class and admin passwords)?" y; then
  ./run.sh setup
else
  echo "  Skipped. Run ./run.sh setup before starting a workshop."
fi

step "Ready"
cat <<'EOF'
  ./run.sh list                  see the workshops
  ./run.sh git-fundamentals      build and start one (first run builds images: expect several minutes)
  ./run.sh stop                  stop and wipe everything

  Then open http://localhost:8080
EOF
