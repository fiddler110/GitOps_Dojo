#!/bin/sh
# git-secrets (target 8, plan §7.3 row 8) provisioning: give each student
# their OWN `internal-tools` Forgejo repo whose git HISTORY holds a deploy
# token a later commit "cleans up" out of the working tree -- the whole
# foothold for this target lives here, in Forgejo, not in the target
# container at all (see modules/ctf-range/targets/git-secrets/app.py).
#
# Runs for every pack that lists `git-secrets` in CTF_ATTACK_TARGETS
# (module.env's catalog, CTF-D20); a no-op (exits immediately) for every
# other pack, same opt-in shape as CTF_ATTACK_TARGETS itself -- this hook
# always runs (part of the ctf-range terminal link) but only ever acts when
# the pack actually enabled this target.
#
# Reuses the same curl+netrc idiom as 90-ctf-defend-test.sh and
# engine/git-server/bootstrap.sh. Runs as root, after student accounts
# exist (web-terminal's start.d contract). Never fails the container: every
# wait is bounded, a timeout just skips that student with a warning.
set -u

case "${CTF_ATTACK_TARGETS:-}" in
  *git-secrets*) ;;
  *) exit 0 ;;
esac

admin_user="${FORGEJO_ADMIN_USER:-}"
admin_password="${FORGEJO_ADMIN_PASSWORD:-}"
if [ -z "$admin_user" ] || [ -z "$admin_password" ]; then
  echo "[git-secrets] FORGEJO_ADMIN_USER/PASSWORD not set, skipping provisioning" >&2
  exit 0
fi

base_url="http://git-server:3000"
api="$base_url/api/v1"
repo_name="internal-tools"
student_count="${STUDENT_COUNT:-0}"
student_prefix="${STUDENT_PREFIX:-student}"
seed="${STUDENT_PASSWORD_SEED:-}"

netrc="$(mktemp)"
trap 'rm -f "$netrc"' EXIT
chmod 600 "$netrc"
printf 'machine git-server\n\tlogin %s\n\tpassword %s\n' "$admin_user" "$admin_password" > "$netrc"

api_curl() { curl --netrc-file "$netrc" "$@"; }
http_status() { api_curl -s -o /dev/null -w '%{http_code}' "$@"; }

log() { printf '[git-secrets] %s\n' "$1"; }

# --- the per-student deploy token, same derivation as ctf-controller's -----
# AttackManager._env_for (flags.render(user, seed, challenge="git-secrets-token")).
# Two independent copies by design (check-tool-pins.sh catches drift) -- the
# target container never holds the seed itself, only the rendered value.
deploy_token_for() {
  python3 -c '
import hashlib, hmac, os, sys
user = sys.argv[1]
seed = os.environ.get("STUDENT_PASSWORD_SEED", "")
challenge = "git-secrets-token"
if not seed:
    print(f"flag{{{challenge}-dev-{user}}}")
else:
    hexd = hmac.new(seed.encode(), f"ctf:{challenge}:{user}".encode(), hashlib.sha256).hexdigest()[:16]
    print(f"flag{{{challenge}-{hexd}}}")
' "$1"
}

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

counter=1
while [ "$counter" -le "$student_count" ]; do
  username="$(printf '%s%02d' "$student_prefix" "$counter")"
  counter=$((counter + 1))

  j=0
  while [ "$(http_status "$api/users/$username")" != "200" ]; do
    j=$((j + 1))
    if [ "$j" -ge 30 ]; then
      log "no Forgejo account for $username yet; skipping this student"
      continue 2
    fi
    sleep 2
  done

  if [ "$(http_status "$api/repos/$username/$repo_name")" = "200" ]; then
    log "repo '$username/$repo_name' already exists"
  else
    log "creating repo '$username/$repo_name'"
    api_curl -sf -X POST "$api/user/repos?sudo=$username" \
      -H 'Content-Type: application/json' \
      -d "{\"name\":\"$repo_name\",\"private\":false,\"auto_init\":false}" \
      >/dev/null || log "warning: could not create '$username/$repo_name'"
  fi

  repo_empty="$(api_curl -sf "$api/repos/$username/$repo_name" 2>/dev/null | grep -o '"empty":[a-z]*' | cut -d: -f2)"
  if [ "$repo_empty" != "true" ]; then
    log "'$username/$repo_name' already has history, leaving it alone"
    continue
  fi

  token="$(deploy_token_for "$username")"
  work="$(mktemp -d)"
  git -C "$work" init -q -b main
  git -C "$work" config user.name "$admin_user"
  git -C "$work" config user.email "ctf-range@example.com"

  # Commit 1: the token lands in the working tree, in plain sight.
  cat > "$work/deploy.sh" <<SH
#!/bin/sh
# Internal deploy trigger. TODO: move this out of source control before
# this repo goes anywhere near a real review.
DEPLOY_TOKEN="$token"
curl -sf -X POST -d "token=\$DEPLOY_TOKEN" "http://git-secrets-deploy.internal/deploy/trigger"
SH
  git -C "$work" add deploy.sh
  git -C "$work" commit -q -m "Add deploy trigger script"

  # Commit 2: "cleaned up" -- the token is gone from the tree, but git never
  # forgets what commit 1's blob held; it's still there under this commit's
  # parent.
  cat > "$work/deploy.sh" <<'SH'
#!/bin/sh
# Internal deploy trigger.
DEPLOY_TOKEN="${DEPLOY_TOKEN:?set this in the environment, not here}"
curl -sf -X POST -d "token=$DEPLOY_TOKEN" "http://git-secrets-deploy.internal/deploy/trigger"
SH
  git -C "$work" add deploy.sh
  git -C "$work" commit -q -m "Stop hardcoding the deploy token"

  git -C "$work" push -q "http://$admin_user:$admin_password@git-server:3000/$username/$repo_name.git" main \
    || log "warning: could not push history to '$username/$repo_name'"
  rm -rf "$work"
  log "provisioned '$username/$repo_name'"
done

log "done"
exit 0
