#!/bin/sh
# ctf-defend-test's own provisioning, not a general mechanism (this pack is a facilitator test
# harness -- see workshop.env). The engine's own bootstrap.sh seeds exactly one repo per workshop
# (FORGEJO_ORG/FORGEJO_REPO); defend-main.yml needs `github.repository_owner` to be a real
# ctf-controller slot (student01, student02, ...), so this hook gives each student their OWN
# `customer-portal` repo (same source as the FORGEJO_ORG/FORGEJO_REPO master seed copy, already on
# this image at /opt/workshop-content/sample-repo) and the Forgejo Actions secrets/variable
# defend-main.yml and defend-pr.yml read (CTF_BUILD_TOKEN, CTF_CONTROL_TOKEN, CTF_FLAG,
# vars.CTF_REGISTRY). Reuses the same curl+netrc idiom as engine/git-server/bootstrap.sh and the
# same PUT .../actions/secrets/<name> call workshops/vault-fundamentals' lab 8 has students run by
# hand -- nothing new here, just run by the harness instead of a human.
#
# Runs as root, after student accounts exist (engine/web-terminal/entrypoint.sh's start.d
# contract). Never fails the container: Forgejo/bootstrap may still be settling when this runs, so
# every wait is bounded and a timeout just skips that student with a warning instead of aborting
# terminal start-up for everyone.
set -u

admin_user="${FORGEJO_ADMIN_USER:-}"
admin_password="${FORGEJO_ADMIN_PASSWORD:-}"
if [ -z "$admin_user" ] || [ -z "$admin_password" ]; then
  echo "[ctf-defend-test] FORGEJO_ADMIN_USER/PASSWORD not set, skipping provisioning" >&2
  exit 0
fi

base_url="http://git-server:3000"
api="$base_url/api/v1"
repo_name="${CTF_BUILDER_REPO_NAME:-customer-portal}"
seed_dir="/opt/workshop-content/sample-repo"
student_count="${STUDENT_COUNT:-0}"
student_prefix="${STUDENT_PREFIX:-student}"
build_token="${CTF_BUILD_TOKEN:-}"
control_token="${CTF_CONTROL_TOKEN:-}"
registry="${CTF_REGISTRY:-registry:5000}"

if [ -z "$build_token" ] || [ -z "$control_token" ]; then
  echo "[ctf-defend-test] CTF_BUILD_TOKEN/CTF_CONTROL_TOKEN not set, skipping provisioning" >&2
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

log() { printf '[ctf-defend-test] %s\n' "$1"; }

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

if [ ! -d "$seed_dir" ]; then
  log "no seed dir at $seed_dir; skipping provisioning"
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
    git -C "$work" init -q -b main
    git -C "$work" config user.name "$admin_user"
    git -C "$work" config user.email "ctf-defend-test@example.com"
    git -C "$work" add -A
    git -C "$work" commit -q -m "Initial target content (ctf-defend-test harness)"
    GIT_ASKPASS="$askpass" CTF_PROVISION_GIT_PASSWORD="$admin_password" \
      git -C "$work" push -q "http://$admin_user@git-server:3000/$username/$repo_name.git" main \
      || log "warning: could not push seed content to '$username/$repo_name'"
    rm -rf "$work"
  fi

  # --- Actions secrets + variable, matching defend-{pr,main}.yml ----------
  # CTF_FLAG must equal exactly what ctf-controller renders for this user's
  # live slot (modules/ctf-range/ctf-controller/flags.py), or defend-pr.yml's
  # --expect-flag check silently calls a still-vulnerable app "patched" (it
  # only requires THIS string in the dump, not any flag{...}). flags.py is
  # HMAC-SHA256(STUDENT_PASSWORD_SEED, "ctf:customer-portal:<user>")[:16]
  # hex, empty seed -> "dev-<user>" -- python3 (present in the base image)
  # mirrors it exactly instead of reimplementing HMAC in shell (xxd isn't on
  # this image, unlike the Forgejo image engine/git-server/dojo-secret.sh
  # targets).
  flag="$(python3 -c '
import hashlib, hmac, os, sys
user = sys.argv[1]
seed = os.environ.get("STUDENT_PASSWORD_SEED", "")
if not seed:
    print(f"flag{{customer-portal-dev-{user}}}")
else:
    hexd = hmac.new(seed.encode(), f"ctf:customer-portal:{user}".encode(), hashlib.sha256).hexdigest()[:16]
    print(f"flag{{customer-portal-{hexd}}}")
' "$username")"
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

log "done"
exit 0
