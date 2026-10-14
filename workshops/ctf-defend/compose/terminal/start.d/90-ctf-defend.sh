#!/bin/sh
# ctf-defend's per-student repo provisioning. The engine's own bootstrap.sh seeds exactly one repo
# per workshop (FORGEJO_ORG/FORGEJO_REPO); defend-main.yml needs `github.repository_owner` to be a
# real ctf-controller slot (student01, ...), so this hook gives each student their OWN repo for EACH
# target in CTF_DEFEND_TARGETS (customer-portal, policy-bypass, leaky-config; the repo name is the
# target), seeded from /opt/workshop-content/sample-repos/<target>/ plus the shared workflows in
# sample-repos/_common/, and the Forgejo Actions secrets/variable the workflows read (CTF_BUILD_TOKEN,
# CTF_CONTROL_TOKEN, CTF_FLAG, vars.CTF_REGISTRY). The student repos hold app source only: no exploit
# script (the checker owns those). Same curl+netrc idiom as engine/git-server/bootstrap.sh.
#
# Runs as root, after student accounts exist. Never fails the container: every wait is bounded and a
# timeout just skips that student with a warning.
set -u

admin_user="${FORGEJO_ADMIN_USER:-}"
admin_password="${FORGEJO_ADMIN_PASSWORD:-}"
if [ -z "$admin_user" ] || [ -z "$admin_password" ]; then
  echo "[ctf-defend] FORGEJO_ADMIN_USER/PASSWORD not set, skipping provisioning" >&2
  exit 0
fi

base_url="http://git-server:3000"
api="$base_url/api/v1"
targets="${CTF_DEFEND_TARGETS:-customer-portal policy-bypass leaky-config}"
seeds_dir="/opt/workshop-content/sample-repos"
student_count="${STUDENT_COUNT:-0}"
student_prefix="${STUDENT_PREFIX:-student}"
build_token="${CTF_BUILD_TOKEN:-}"
control_token="${CTF_CONTROL_TOKEN:-}"
registry="${CTF_REGISTRY:-registry:5000}"

if [ -z "$build_token" ] || [ -z "$control_token" ]; then
  echo "[ctf-defend] CTF_BUILD_TOKEN/CTF_CONTROL_TOKEN not set, skipping provisioning" >&2
  exit 0
fi

netrc="$(mktemp)"
askpass="$(mktemp)"
cleanup() { rm -f "$netrc" "$askpass"; }
trap cleanup EXIT
chmod 600 "$netrc"
printf 'machine git-server\n\tlogin %s\n\tpassword %s\n' "$admin_user" "$admin_password" > "$netrc"
chmod 700 "$askpass"
printf '#!/bin/sh\necho "$CTF_PROVISION_GIT_PASSWORD"\n' > "$askpass"

api_curl() { curl --netrc-file "$netrc" "$@"; }
http_status() { api_curl -s -o /dev/null -w '%{http_code}' "$@"; }

log() { printf '[ctf-defend] %s\n' "$1"; }

# --- wait for the admin API (bounded: ~5 minutes) --------------------------
i=0
until [ "$(http_status "$api/user")" = "200" ]; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then
    log "Forgejo admin API never became ready; skipping provisioning"
    exit 0
  fi
  sleep 5
done

if [ ! -d "$seeds_dir" ]; then
  log "no seed dir at $seeds_dir; skipping provisioning"
  exit 0
fi

counter=1
while [ "$counter" -le "$student_count" ]; do
  username="$(printf '%s%02d' "$student_prefix" "$counter")"
  counter=$((counter + 1))

  # Wait (bounded: ~60s) for this student's Forgejo account to exist.
  j=0
  while [ "$(http_status "$api/users/$username")" != "200" ]; do
    j=$((j + 1))
    if [ "$j" -ge 30 ]; then
      log "no Forgejo account for $username yet; skipping this student"
      continue 2
    fi
    sleep 2
  done

  for repo_name in $targets; do
    seed_dir="$seeds_dir/$repo_name"
    if [ ! -d "$seed_dir" ]; then log "no seed for $repo_name; skipping"; continue; fi
    # --- repo: create (as that student, via admin sudo) if missing ---------
    if [ "$(http_status "$api/repos/$username/$repo_name")" = "200" ]; then
      log "repo '$username/$repo_name' already exists"
    else
      log "creating repo '$username/$repo_name'"
      api_curl -sf -X POST "$api/user/repos?sudo=$username" \
        -H 'Content-Type: application/json' \
        -d "{\"name\":\"$repo_name\",\"private\":false,\"auto_init\":false}" \
        >/dev/null || log "warning: could not create '$username/$repo_name'"
    fi

    api_curl -sf -X PATCH "$api/repos/$username/$repo_name" \
      -H 'Content-Type: application/json' \
      -d '{"default_delete_branch_after_merge":true}' \
      >/dev/null || true

    # --- seed content, only if the repo has no commits yet ------------------
    repo_empty="$(api_curl -sf "$api/repos/$username/$repo_name" 2>/dev/null | grep -o '"empty":[a-z]*' | cut -d: -f2)"
    if [ "$repo_empty" = "true" ]; then
      log "pushing seed content into '$username/$repo_name'"
      work="$(mktemp -d)"
      cp -R "$seed_dir"/. "$work/"
      [ -d "$seeds_dir/_common" ] && cp -R "$seeds_dir/_common"/. "$work/"
      git -C "$work" init -q -b main
      git -C "$work" config user.name "$admin_user"
      git -C "$work" config user.email "ctf-defend@example.com"
      git -C "$work" add -A
      git -C "$work" commit -q -m "Initial target content ($repo_name)"
      GIT_ASKPASS="$askpass" CTF_PROVISION_GIT_PASSWORD="$admin_password" \
        git -C "$work" push -q "http://$admin_user@git-server:3000/$username/$repo_name.git" main \
        || log "warning: could not push seed content to '$username/$repo_name'"
      rm -rf "$work"
    fi

    # --- Actions secrets + variable, matching defend-{pr,main}.yml ----------
    # CTF_FLAG must equal exactly what ctf-controller renders for this user's
    # live slot (modules/ctf-range/ctf-controller/flags.py), or defend-pr.yml's
    # gate's flag check silently calls a still-vulnerable app "patched" (it
    # only requires THIS string in the dump, not any flag{...}). flags.py is
    # HMAC-SHA256(STUDENT_PASSWORD_SEED, "ctf:<target>:<user>")[:16]
    # hex, empty seed -> "dev-<user>" -- python3 (present in the base image)
    # mirrors it exactly instead of reimplementing HMAC in shell (xxd isn't on
    # this image, unlike the Forgejo image engine/git-server/dojo-secret.sh
    # targets).
    flag="$(python3 -c '
import hashlib, hmac, os, sys
user, target = sys.argv[1], sys.argv[2]
seed = os.environ.get("STUDENT_PASSWORD_SEED", "")
if not seed:
    print(f"flag{{{target}-dev-{user}}}")
else:
    hexd = hmac.new(seed.encode(), f"ctf:{target}:{user}".encode(), hashlib.sha256).hexdigest()[:16]
    print(f"flag{{{target}-{hexd}}}")
' "$username" "$repo_name")"
    secrets_api="$api/repos/$username/$repo_name/actions/secrets"
    for pair in "CTF_BUILD_TOKEN=$build_token" "CTF_CONTROL_TOKEN=$control_token" "CTF_FLAG=$flag"; do
      name="${pair%%=*}"
      value="${pair#*=}"
      body="$(mktemp)"
      printf '{"data":"%s"}' "$value" > "$body"
      api_curl -sf -X PUT "$secrets_api/$name" -H 'Content-Type: application/json' -d "@$body" \
        >/dev/null || log "warning: could not set secret $name on '$username/$repo_name'"
      rm -f "$body"
    done

    # Forgejo's Actions-variables endpoint, unlike secrets: POST creates,
    # PUT only updates an existing one (PUT on a missing name 404s).
    vars_api="$api/repos/$username/$repo_name/actions/variables"
    body="$(mktemp)"
    printf '{"value":"%s"}' "$registry" > "$body"
    if [ "$(http_status "$vars_api/CTF_REGISTRY")" = "200" ]; then
      verb=PUT
    else
      verb=POST
    fi
    api_curl -sf -X "$verb" "$vars_api/CTF_REGISTRY" -H 'Content-Type: application/json' -d "@$body" \
      >/dev/null || log "warning: could not set variable CTF_REGISTRY on '$username/$repo_name'"
    rm -f "$body"

    log "provisioned '$username/$repo_name'"
  done
done

log "done"
exit 0
