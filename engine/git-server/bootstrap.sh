#!/bin/sh
# Idempotent Forgejo bootstrap. Runs once per `compose up` as a one-shot
# service sharing the git-server data volume and network. Safe to re-run:
# every step checks for existing state before creating anything.
set -eu

forgejo_config="/data/gitea/conf/app.ini"
base_url="http://git-server:3000"

admin_user="${FORGEJO_ADMIN_USER:?Set FORGEJO_ADMIN_USER}"
admin_password="${FORGEJO_ADMIN_PASSWORD:?Set FORGEJO_ADMIN_PASSWORD}"
admin_email="${FORGEJO_ADMIN_EMAIL:-admin@example.com}"
org_name="${FORGEJO_ORG:-training}"
org_desc="${FORGEJO_ORG_DESC:-Workshop repositories}"
repo_name="${FORGEJO_REPO:-sample-training-repo}"
seed_dir="${FORGEJO_SEED_DIR:-/seed}"

student_count="${STUDENT_COUNT:-30}"
student_prefix="${STUDENT_PREFIX:-student}"
student_password="${STUDENT_PASSWORD:-student123}"

# Demo/test bots (--test) -- see engine/run.sh and engine/README.md. 0 by
# default, so this whole block is a no-op unless a facilitator opted in.
bot_count="${BOT_COUNT:-0}"
bot_prefix="${BOT_PREFIX:-testuser}"
bot_password="${BOT_PASSWORD:-testuser123}"

api="$base_url/api/v1"

log() { printf '[bootstrap] %s\n' "$1"; }

# Credentials go through a netrc file (curl) and GIT_ASKPASS (git) instead
# of -u/URL-embedded values, so they don't sit in plaintext argv — visible
# via `ps aux`/`docker top` to anything with shell access to this host for
# the lifetime of each call. Both cleaned up on exit regardless of how the
# script ends.
#
# One exception: the `forgejo admin user create --password` call below.
# The Forgejo CLI has no stdin/file option for it, only the flag, so that
# single command's argv briefly does carry admin_password. Low risk in
# practice — it's one call, in a one-shot container on an internal-only
# network, and anyone who can already read this host's process table
# during that window has host shell access, which is a bigger problem than
# this one value. Flagging it rather than leaving it unmentioned.
netrc="$(mktemp)"
askpass="$(mktemp)"
cleanup() { rm -f "$netrc" "$askpass"; }
trap cleanup EXIT

chmod 600 "$netrc"
printf 'machine git-server\n\tlogin %s\n\tpassword %s\n' "$admin_user" "$admin_password" > "$netrc"

chmod 700 "$askpass"
printf '#!/bin/sh\necho "$BOOTSTRAP_GIT_PASSWORD"\n' > "$askpass"

api_curl() { curl --netrc-file "$netrc" "$@"; }

# ---------------------------------------------------------------------------
# 1. Admin user (CLI, operates directly on the shared /data volume)
# ---------------------------------------------------------------------------
if forgejo admin user list --config "$forgejo_config" --admin 2>/dev/null | awk '{print $2}' | grep -qx "$admin_user"; then
  log "admin user '$admin_user' already exists"
else
  log "creating admin user '$admin_user'"
  forgejo admin user create \
    --config "$forgejo_config" \
    --admin \
    --username "$admin_user" \
    --password "$admin_password" \
    --email "$admin_email" \
    --must-change-password=false
fi

# ---------------------------------------------------------------------------
# 2. Wait for the HTTP API (git-server is healthy per depends_on, but the
#    admin account we just created needs to be queryable too)
# ---------------------------------------------------------------------------
log "waiting for Forgejo API"
i=0
until api_curl -sf "$api/user" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then
    echo "[bootstrap] Forgejo API did not become ready in time" >&2
    exit 1
  fi
  sleep 2
done

http_status() {
  api_curl -s -o /dev/null -w '%{http_code}' "$@"
}

# ---------------------------------------------------------------------------
# 3. Organization
# ---------------------------------------------------------------------------
if [ "$(http_status "$api/orgs/$org_name")" = "200" ]; then
  log "org '$org_name' already exists"
else
  log "creating org '$org_name'"
  api_curl -sf -X POST "$api/orgs" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$org_name\",\"full_name\":\"$org_name\",\"description\":\"$org_desc\",\"visibility\":\"public\"}" \
    >/dev/null
fi

# ---------------------------------------------------------------------------
# 4. Repository (empty; seeded below)
# ---------------------------------------------------------------------------
if [ "$(http_status "$api/repos/$org_name/$repo_name")" = "200" ]; then
  log "repo '$org_name/$repo_name' already exists"
else
  log "creating repo '$org_name/$repo_name'"
  api_curl -sf -X POST "$api/orgs/$org_name/repos" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"$repo_name\",\"private\":false,\"auto_init\":false}" \
    >/dev/null
fi

# Pre-tick "Delete branch after merge" on the PR merge form, so a merged PR
# cleans up its branch on the server (labs rely on this before git fetch --prune).
# Applied on every run so repos created before this setting also pick it up.
api_curl -sf -X PATCH "$api/repos/$org_name/$repo_name" \
  -H 'Content-Type: application/json' \
  -d '{"default_delete_branch_after_merge":true}' \
  >/dev/null || log "warning: could not set delete-branch-after-merge on '$org_name/$repo_name'"

# ---------------------------------------------------------------------------
# 5. Seed content (only if the repo has no commits yet)
# ---------------------------------------------------------------------------
repo_empty="$(api_curl -sf "$api/repos/$org_name/$repo_name" | grep -o '"empty":[a-z]*' | cut -d: -f2)"
if [ "$repo_empty" = "true" ] && [ -d "$seed_dir" ]; then
  log "pushing seed content into '$org_name/$repo_name'"
  work="$(mktemp -d)"
  cp -R "$seed_dir"/. "$work/"
  git -C "$work" init -q -b main
  git -C "$work" config user.name "$admin_user"
  git -C "$work" config user.email "$admin_email"
  git -C "$work" add -A
  git -C "$work" commit -q -m "Initial workshop content"
  GIT_ASKPASS="$askpass" BOOTSTRAP_GIT_PASSWORD="$admin_password" \
    git -C "$work" push -q "http://$admin_user@git-server:3000/$org_name/$repo_name.git" main
  rm -rf "$work"
else
  log "repo already has content or no seed dir provided; skipping seed push"
fi

# ---------------------------------------------------------------------------
# 6. Student accounts + a write-access team, so each terminal account has a
#    matching Forgejo identity without needing open self-registration.
# ---------------------------------------------------------------------------
team_id="$(api_curl -sf "$api/orgs/$org_name/teams" | grep -o '"id":[0-9]*,"name":"students"' | head -1 | grep -o '^"id":[0-9]*' | cut -d: -f2)"
if [ -z "$team_id" ]; then
  log "creating 'students' team with write access"
  team_id="$(api_curl -sf -X POST "$api/orgs/$org_name/teams" \
    -H 'Content-Type: application/json' \
    -d '{"name":"students","permission":"write","units":["repo.code","repo.issues","repo.pulls"],"includes_all_repositories":true}' \
    | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)"
fi

counter=1
while [ "$counter" -le "$student_count" ]; do
  username="$(printf '%s%02d' "$student_prefix" "$counter")"

  if [ "$(http_status "$api/users/$username")" != "200" ]; then
    # -d @file instead of an inline string so student_password doesn't sit
    # in this curl call's argv either.
    user_json="$(mktemp)"
    printf '{"username":"%s","password":"%s","email":"%s@example.com","must_change_password":false}' \
      "$username" "$student_password" "$username" > "$user_json"
    api_curl -sf -X POST "$api/admin/users" \
      -H 'Content-Type: application/json' \
      -d "@$user_json" \
      >/dev/null
    rm -f "$user_json"
  fi

  if [ -n "$team_id" ]; then
    api_curl -sf -X PUT "$api/teams/$team_id/members/$username" >/dev/null || true
  fi

  counter=$((counter + 1))
done
log "ensured $student_count Forgejo account(s) with prefix '$student_prefix' in team 'students'"

# ---------------------------------------------------------------------------
# 7. Demo/test bot accounts (--test). Same team ("students", write access)
#    as real students, since bot-runner.sh pushes branches and opens PRs
#    under its own account, exactly like a student would -- traceable in
#    Forgejo by account name (testuserN) and by its branches'
#    "testuserN/..." prefix alike. See engine/web-terminal/bot-runner.sh.
# ---------------------------------------------------------------------------
bot_counter=1
while [ "$bot_counter" -le "$bot_count" ]; do
  bot_username="$(printf '%s%d' "$bot_prefix" "$bot_counter")"

  if [ "$(http_status "$api/users/$bot_username")" != "200" ]; then
    bot_user_json="$(mktemp)"
    printf '{"username":"%s","password":"%s","email":"%s@example.com","must_change_password":false}' \
      "$bot_username" "$bot_password" "$bot_username" > "$bot_user_json"
    api_curl -sf -X POST "$api/admin/users" \
      -H 'Content-Type: application/json' \
      -d "@$bot_user_json" \
      >/dev/null
    rm -f "$bot_user_json"
  fi

  if [ -n "$team_id" ]; then
    api_curl -sf -X PUT "$api/teams/$team_id/members/$bot_username" >/dev/null || true
  fi

  bot_counter=$((bot_counter + 1))
done
if [ "$bot_count" -gt 0 ]; then
  log "ensured $bot_count demo bot Forgejo account(s) with prefix '$bot_prefix' in team 'students'"
fi

log "bootstrap complete"
