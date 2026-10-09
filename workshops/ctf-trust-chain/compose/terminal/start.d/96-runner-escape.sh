#!/bin/sh
# Target 10 `runner-escape` (plan §7.3 row 10, CTF-4, needs `runner-pool`):
# give each student their OWN `ci-pipeline` Forgejo repo with a normal CI
# workflow on `main`. The foothold is the workflow itself: Forgejo runs a
# `pull_request` job using the PR BRANCH's version of the workflow file (not
# main's), so a student who edits `.forgejo/workflows/ci.yml` on a branch and
# opens a PR gets arbitrary shell code executed on a shared runner-pool
# runner -- "attacker-controlled code on a shared runner", plan row 10's
# foothold, exactly as real as a contributor's fork PR. This pack already
# proves the mechanism live: `defend-pr.yml` (target 14, CTF-5) runs on
# `pull_request` with `secrets.CTF_FLAG` injected and is live-verified
# end-to-end (CTF-WORKSHOP-PLAN.md's checkpoint, S6) -- that settles the
# open spike here too (docs/CTF-SPIKES.md's runner-escape bullet): this
# target never needs `pull_request_target` (whose reliability T0.3 left
# inconclusive, docs/archive/REMEDIATION-PLAN.md), only plain `pull_request`,
# already proven.
#
# The escalation step (plan row 10: "read another job's leftover state;
# expected to fail, which is the point") has no second flag: runner-pool
# gives every job its own user + PID namespace and wipes it after
# (modules/runner-pool/README.md), so a probe step that lists /home, /tmp
# and `ps aux` from inside the malicious job comes back with nothing from
# any other job -- the dead end IS the lesson.
#
# This pack only (workshop-level hook, 90+ prefix, same as
# 95-tfstate-treasure.sh): runner-escape is new/unproven outside this
# harness and needs `runner-pool` in MODULES, same scoping reasoning as
# tfstate-treasure needing `openbao` -- not yet promoted to a generic
# module-level hook gated on CTF_ATTACK_TARGETS the way 55-git-secrets.sh
# is, because this target has no attack-ladder container slot at all (no
# entry in CTF_ATTACK_TARGETS, same "no image" shape as tfstate-treasure).
#
# Reuses the curl+netrc idiom as 55-git-secrets.sh.
# Runs as root, after student accounts exist. Never fails the container:
# every wait is bounded, a timeout just skips that student with a warning.
set -u

admin_user="${FORGEJO_ADMIN_USER:-}"
admin_password="${FORGEJO_ADMIN_PASSWORD:-}"
if [ -z "$admin_user" ] || [ -z "$admin_password" ]; then
  echo "[runner-escape] FORGEJO_ADMIN_USER/PASSWORD not set, skipping provisioning" >&2
  exit 0
fi

base_url="http://git-server:3000"
api="$base_url/api/v1"
repo_name="ci-pipeline"
student_count="${STUDENT_COUNT:-0}"
student_prefix="${STUDENT_PREFIX:-student}"

netrc="$(mktemp)"
trap 'rm -f "$netrc"' EXIT
chmod 600 "$netrc"
printf 'machine git-server\n\tlogin %s\n\tpassword %s\n' "$admin_user" "$admin_password" > "$netrc"

api_curl() { curl --netrc-file "$netrc" "$@"; }
http_status() { api_curl -s -o /dev/null -w '%{http_code}' "$@"; }

log() { printf '[runner-escape] %s\n' "$1"; }

# --- the per-student flag, same derivation as every other target's --------
# ctf-controller's flags.render(user, seed, challenge="runner-escape").
flag_for() {
  python3 -c '
import hashlib, hmac, os, sys
user = sys.argv[1]
seed = os.environ.get("STUDENT_PASSWORD_SEED", "")
challenge = "runner-escape"
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

  # --- seed content, only if the repo has no commits yet -------------------
  repo_empty="$(api_curl -sf "$api/repos/$username/$repo_name" 2>/dev/null | grep -o '"empty":[a-z]*' | cut -d: -f2)"
  if [ "$repo_empty" = "true" ]; then
    log "pushing seed content into '$username/$repo_name'"
    work="$(mktemp -d)"
    mkdir -p "$work/.forgejo/workflows"
    cat > "$work/app.py" <<'PY'
"""A trivial app this repo's CI 'lints' -- the point of this repo is the
pipeline, not this file."""


def greet(name: str) -> str:
    return f"hello, {name}"


if __name__ == "__main__":
    print(greet("ci-pipeline"))
PY
    cat > "$work/.forgejo/workflows/ci.yml" <<'YAML'
# A normal CI job: checkout, lint. Nothing here ever touches a secret -- the
# target-10 lesson is that a PR can CHANGE this file, and `pull_request`
# always runs the PR branch's version of it, not this one.
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  build:
    runs-on: host
    steps:
      - name: Checkout
        run: |
          set -eu
          rm -rf repo
          git clone --quiet "http://git-server:3000/${GITHUB_REPOSITORY}.git" repo
          cd repo
          git checkout --quiet "$GITHUB_SHA"

      - name: Lint
        run: |
          set -eu
          cd repo
          python3 -c "import ast; ast.parse(open('app.py').read())"
          echo "app.py is valid Python"
YAML
    cat > "$work/README.md" <<'MD'
# ci-pipeline

A small repo with its own CI. Open a PR and see what the pipeline does with
your branch's version of `.forgejo/workflows/ci.yml` -- not main's.
MD
    git -C "$work" init -q -b main
    git -C "$work" config user.name "$admin_user"
    git -C "$work" config user.email "ctf-range@example.com"
    git -C "$work" add -A
    git -C "$work" commit -q -m "Initial CI pipeline"
    git -C "$work" push -q "http://$admin_user:$admin_password@git-server:3000/$username/$repo_name.git" main \
      || log "warning: could not push seed content to '$username/$repo_name'"
    rm -rf "$work"
  fi

  # --- the Actions secret the legit workflow never touches -----------------
  flag="$(flag_for "$username")"
  body="$(mktemp)"
  printf '{"data":"%s"}' "$flag" > "$body"
  api_curl -sf -X PUT "$api/repos/$username/$repo_name/actions/secrets/CTF_FLAG" \
    -H 'Content-Type: application/json' -d "@$body" \
    >/dev/null || log "warning: could not set secret CTF_FLAG on '$username/$repo_name'"
  rm -f "$body"

  log "provisioned '$username/$repo_name'"
done

log "done"
exit 0
