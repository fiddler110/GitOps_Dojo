# Shared by run.sh and the scripts under engine/scripts/: sourced, never run.
# One copy of the facts every script needs to agree on.

# Container engine: podman when podman-compose is installed too (rootless, no
# daemon), else docker.
if command -v podman >/dev/null 2>&1 && command -v podman-compose >/dev/null 2>&1; then
  dojo_cli=podman
  # On WSL2 the Windows folders (/mnt/c/...) are on PATH, and podman searches PATH for every OCI
  # runtime it knows, each miss crossing into Windows: ~1.2 s per podman call instead of ~0.06 s.
  # Nothing podman needs lives there.
  case ":$PATH:" in *:/mnt/*) PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/mnt/' | paste -sd:)"; export PATH ;; esac
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

# Load KEY=value lines from an env file the operator writes (engine/.env,
# engine/.env.NAME) and export them, taking each value literally: a password
# with '$', '`' or spaces is kept as typed, never expanded or run, which
# sourcing the file as shell did. Handles "quoted" and 'quoted' values, an
# optional `export `, comments and blank lines, ` # comments` after an
# unquoted value, and Windows line endings.
# workshop.env and module.env are different: they are shell code by design
# (they derive tokens with $(...)), so run.sh still sources those.
dojo_load_env() {
  eval "$(awk -v q="'" '
    { line = $0; sub(/\r$/, "", line); sub(/^[ \t]+/, "", line); sub(/^export[ \t]+/, "", line) }
    line ~ /^#/ || line !~ /^[A-Za-z_][A-Za-z0-9_]*=/ { next }
    {
      eq = index(line, "="); k = substr(line, 1, eq - 1); v = substr(line, eq + 1)
      if (v ~ /^"/ && match(substr(v, 2), /"/)) v = substr(v, 2, RSTART - 1)
      else if (substr(v, 1, 1) == q && match(substr(v, 2), q)) v = substr(v, 2, RSTART - 1)
      else { sub(/[ \t]+#.*$/, "", v); sub(/[ \t]+$/, "", v) }
      gsub(q, q "\"" q "\"" q, v)
      print "export " k "=" q v q
    }' "$1")"
}
