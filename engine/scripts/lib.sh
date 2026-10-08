# Shared by run.sh and the scripts under engine/scripts/: sourced, never run.
# One copy of the facts every script needs to agree on.

# Container engine: podman when podman-compose is installed too (rootless, no
# daemon), else docker.
if command -v podman >/dev/null 2>&1 && command -v podman-compose >/dev/null 2>&1; then
  dojo_cli=podman
  # On WSL2 the Windows folders (/mnt/c/...) are on PATH, and podman searches PATH for every OCI
  # runtime it knows, each miss crossing into Windows: ~1.2 s per podman call instead of ~0.06 s.
  # Nothing podman needs lives there. Only on WSL: elsewhere /mnt/... is an ordinary mount.
  if grep -qi microsoft /proc/version 2>/dev/null; then
    case ":$PATH:" in *:/mnt/*) PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/' | paste -sd:)"; export PATH ;; esac
  fi
else
  dojo_cli=docker
fi

dojo_compose() {
  if [ "$dojo_cli" = "podman" ]; then podman-compose "$@"; else docker compose "$@"; fi
}

# The Compose project: named after the folder docker-compose.yml is in, so its
# containers carry com.docker.compose.project=engine and its volumes engine_*.
dojo_project() { printf '%s' "${COMPOSE_PROJECT_NAME:-engine}"; }

# Passwords anyone can know: .env.example's placeholder and the values
# `./run.sh setup --default` writes. run.sh refuses them off loopback.
dojo_is_default_password() {
  case "$1" in
    change-me | student | student123 | admin) return 0 ;;
    *) return 1 ;;
  esac
}

# The operator's settings (dojo.toml, dojo.local.toml, the secrets in .env, any profile) are
# read by the CLI, literally: a password with '$', '`' or spaces is kept as typed.
# For a script that needs them:   eval "$(./run.sh _operator-env [--env NAME])"
# workshop.env and module.env are different: shell code by design (they derive tokens
# with $(...)), which the CLI sources itself.
