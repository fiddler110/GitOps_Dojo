# DNS as Code demo bot steps -- sourced by engine/web-terminal/bot-runner.sh
# after its own helpers/defaults are defined (see BOT_STEPS_FILE there). Runs
# the dns-as-code labs instead of git-fundamentals. Part 1, in the bot's own
# zone (~/lab/my-zone, <bot>.dojo.test): preview/push/verify, add, remove and
# catch mistakes (Lab 1), drift and a revert (Lab 2). Part 2, in the shared
# repo: a refused local push, then an A record on a branch + PR, reviewed
# (Sensei approves the bots' PRs, modules/sensei approve mode), merged and
# applied by CI (Lab 3); the dnsctl.py wrapper end to end (Lab 4); history and
# a rollback PR (Lab 5); and a dnsconfig.js merge conflict (Lab 6).
# step_ensure_clone/step_sync_main from bot-runner.sh are reused as-is;
# everything else here is dns-as-code-specific.

# Part 1 sandbox, made by compose/terminal/start.d/90-my-zone.sh.
MY_ZONE_DIR="$HOME/lab/my-zone"

# -- helper: this bot's own dns-api key ------------------------------------
# The dns-gate module's start.d hook writes it after bot-runner.sh has
# started (so it isn't in this shell's environment yet): read it from the
# file at the start of every step until it's there.
dns_key_env() {
  if [ -z "${DNS_API_KEY:-}" ] && [ -r "$HOME/.config/dojo/dns-api-key" ]; then
    DNS_API_KEY="$(cat "$HOME/.config/dojo/dns-api-key")"
    export DNS_API_KEY
  fi
}

# -- helper: insert-or-update this bot's own A record -----------------------
# Mirrors lab3.md's python3 option for editing dnsconfig.js (the lab's own
# suggested non-interactive method). Uses argv, not string interpolation
# into the script body, so $BOT_USER never has to be quoted into Python
# source. Inserts before the "mail" A record (or before the closing ");" in
# a zone without one) if the name has no record yet, otherwise updates its
# existing value in place (round 2+ then shows a MODIFY, like lab1.md step 5).
dns_set_own_record() { # $1 = record name, $2 = ip
  python3 - "$1" "$2" <<'PYEOF'
import re
import sys

name, ip = sys.argv[1], sys.argv[2]
p = "dnsconfig.js"
s = open(p, encoding="utf-8").read()
pattern = re.compile(r'A\("%s", "[0-9.]+"\)' % re.escape(name))
if pattern.search(s):
    s = pattern.sub('A("%s", "%s")' % (name, ip), s, count=1)
elif 'A("mail"' in s:
    s = s.replace(
        'A("mail"',
        'A("%s", "%s"),\n\tA("mail"' % (name, ip),
        1,
    )
else:
    head, sep, tail = s.rpartition(");")
    s = head + '\tA("%s", "%s"),\n' % (name, ip) + sep + tail
open(p, "w", encoding="utf-8").write(s)
PYEOF
}

# A stable-ish, bot- and round-varying last octet in the RFC 5737 lab range,
# staying well clear of the zone's own fixed records (.10/.20).
dns_octet() { # $1 = round offset (0 for the bot's own record, 1 for a scratch one)
  local bot_num
  bot_num="$(printf '%s' "$BOT_USER" | grep -o '[0-9]\+' | head -1)"
  [ -z "$bot_num" ] && bot_num=1
  echo $(( (bot_num * 10 + ROUND * 3 + ${1:-0}) % 190 + 30 ))
}

# -- helpers: the shared repo's pull requests -------------------------------
dns_pr_field() { # $1 = PR number, $2 = JSON key whose value is a bare word (true/false/...)
  api_curl "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls/$1" | grep -o "\"$2\":[a-z]*" | head -1 | cut -d: -f2
}

# Number of an open PR whose head branch starts with $1 (empty if none); $2 = "mine"
# limits it to this bot's own.
dns_pr_for_branch() { # $1 = branch prefix, $2 = mine | any
  api_curl "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls?state=open&limit=50" | python3 -c '
import json, sys
try:
    for p in json.load(sys.stdin):
        if not p["head"]["ref"].startswith(sys.argv[1]):
            continue
        if sys.argv[2] == "mine" and p["user"]["login"] != sys.argv[3]:
            continue
        print(p["number"])
        break
except ValueError:
    pass' "$1" "${2:-mine}" "$BOT_USER"
}

dns_pr_approved() { # $1 = PR number
  api_curl "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls/$1/reviews" | grep -q '"state":"APPROVED"'
}

# "If your pull request has conflicts" in lab3.md: bring main into the branch,
# keep both sides' records, preview, commit, push.
dns_resolve_stale() { # $1 = branch
  run_cmd "git checkout '$1'"
  run_cmd "git pull --no-rebase --no-edit origin main"
  if grep -q '^<<<<<<<' dnsconfig.js; then
    narrate "conflict in dnsconfig.js -- keeping both records"
    run_cmd "sed -i '/^<<<<<<</d; /^=======/d; /^>>>>>>>/d' dnsconfig.js"
    run_cmd "dnscontrol preview"
    run_cmd "git add dnsconfig.js"
    run_cmd "git commit --no-edit"
  fi
  run_cmd "git push"
}

# Lab 3 step 4: main keeps moving, and a preview of a branch that is behind it shows other people's
# new records as DELETEs. Bring main into the current branch (keeping both sides on a conflict).
dns_catch_up() {
  run_cmd "git fetch -q origin main"
  git merge-base --is-ancestor origin/main HEAD && return 0
  narrate "main moved while I was working -- bringing it into my branch before I push"
  run_cmd "git pull --no-rebase --no-edit origin main"
  if grep -q '^<<<<<<<' dnsconfig.js; then
    narrate "conflict in dnsconfig.js -- keeping both records"
    run_cmd "sed -i '/^<<<<<<</d; /^=======/d; /^>>>>>>>/d' dnsconfig.js"
    run_cmd "git add dnsconfig.js"
    run_cmd "git commit --no-edit"
  fi
  run_cmd "dnscontrol preview"
}

# Wait for Sensei's approval and the DNS Preview check, then merge: through the
# API (Lab 3, the Merge button) or `dnsctl.py merge` (Lab 4/5). Resolves a stale
# branch on the way. Returns 0 once merged.
dns_merge_when_ready() { # $1 = PR number, $2 = branch, $3 = api | dnsctl
  local n="$1" branch="$2" how="$3" i code
  for i in $(seq 1 30); do
    if [ "$(dns_pr_field "$n" mergeable)" = "false" ]; then
      narrate "PR #$n has conflicts with main -- bringing main into the branch"
      dns_resolve_stale "$branch"
    elif dns_pr_approved "$n"; then
      if [ "$how" = "dnsctl" ]; then
        run_cmd "python3 scripts/dnsctl.py merge $n --yes" && return 0
      else
        code="$(api_curl -o /dev/null -w '%{http_code}' -X POST "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls/$n/merge" \
          -H 'Content-Type: application/json' -d '{"Do":"merge","delete_branch_after_merge":true}')"
        case "$code" in
          200|204) narrate "merged PR #$n -- CI's DNS Apply job takes it from here"; return 0 ;;
        esac
      fi
    else
      [ $(( i % 3 )) -ne 1 ] || narrate "PR #$n: waiting for the DNS Preview check and an approval"
    fi
    sleep 10
  done
  narrate "PR #$n still not mergeable after five minutes -- moving on"
  return 1
}

# -- Lab 1 (Part 1) -- the bot's own zone: preview, push, verify, add a record
# Idempotent (preview/push both are), so safe to repeat every round: the
# first round creates <bot>.dojo.test, later ones MODIFY its app record.
step_dns_baseline() {
  dns_key_env
  cd "$MY_ZONE_DIR" || return 1
  narrate "Lab 1 -- my own zone: preview, push, verify"
  run_cmd "dnscontrol preview"
  run_cmd "dnscontrol push"
  run_cmd "dig @dns-server www.$BOT_USER.dojo.test A +short"
  dns_set_own_record "app" "203.0.113.$(dns_octet 0)"
  narrate "Lab 1, steps 4-5 -- add or change my app record"
  run_cmd "dnscontrol preview"
  run_cmd "dnscontrol push"
  run_cmd "dig @dns-server app.$BOT_USER.dojo.test A +short"
  run_cmd "git commit -qam 'Set app (round $ROUND)'"
  run_cmd "dnscontrol preview"
}

# -- Lab 1 (Part 1) -- a record with a very short TTL, then removing it -----
# Both pushed (that is what the achievements check: a TTL below 60, a push that
# removes a record), and the zone ends where it started.
step_dns_lab1_remove() {
  dns_key_env
  cd "$MY_ZONE_DIR" || return 1
  narrate "Lab 1 -- a record with a TTL of 1, pushed, then removed again"
  python3 - <<'PYEOF'
import re
p = "dnsconfig.js"
s = open(p, encoding="utf-8").read()
s = re.sub(r'\n\tA\("short", [^\n]*', "", s)
head, sep, tail = s.rpartition(");")
open(p, "w", encoding="utf-8").write(head + '\tA("short", "203.0.113.77", TTL(1)),\n' + sep + tail)
PYEOF
  run_cmd "dnscontrol preview"
  run_cmd "dnscontrol push"
  run_cmd "sed -i '/A(\"short\"/d' dnsconfig.js"
  run_cmd "dnscontrol preview"
  run_cmd "dnscontrol push"
  run_cmd "git status"
}

# -- Lab 2 (Part 1) -- drift, then undoing a pushed change -------------------
step_dns_lab2_drift() {
  dns_key_env
  cd "$MY_ZONE_DIR" || return 1
  narrate "Lab 2, part A -- someone changes the zone behind my back"
  run_cmd "curl -s -X PATCH -H \"X-API-Key: \$DNS_API_KEY\" -H 'Content-Type: application/json' http://dns-api:8081/api/v1/servers/localhost/zones/\$USER.dojo.test. -d '{\"rrsets\":[{\"name\":\"hotfix.'\"\$USER\"'.dojo.test.\",\"type\":\"A\",\"ttl\":300,\"changetype\":\"REPLACE\",\"records\":[{\"content\":\"203.0.113.99\",\"disabled\":false}]}]}'"
  run_cmd "dig @dns-server hotfix.$BOT_USER.dojo.test A +short"
  run_cmd "dnscontrol preview"
  run_cmd "dnscontrol push"
  narrate "the hotfix record is gone -- asking DNS in full this time"
  run_cmd "dig @dns-server hotfix.$BOT_USER.dojo.test A"

  narrate "Lab 2, part B -- a change I regret, then git revert"
  run_cmd "sed -i 's/A(\"www\", \"[0-9.]*\")/A(\"www\", \"203.0.113.66\")/' dnsconfig.js"
  run_cmd "dnscontrol preview"
  run_cmd "dnscontrol push"
  run_cmd "git commit -qam 'Move www to the new server'"
  run_cmd "git log --oneline"
  run_cmd "git revert --no-edit HEAD"
  run_cmd "dnscontrol preview"
  run_cmd "dnscontrol push"
  run_cmd "dig @dns-server www.$BOT_USER.dojo.test A +short"
}

# -- Lab 3 (Part 2) -- a refused local push, then branch, add, commit -------
step_dns_lab1_branch_and_edit() {
  dns_key_env
  cd "$REPO_DIR" || return 1
  local branch; branch="$(branch_name "add-${BOT_USER}")"
  run_cmd "git checkout -q main"
  run_cmd "git pull"
  narrate "Lab 3, step 2 -- preview the live shared zone"
  run_cmd "dnscontrol preview"
  narrate "Lab 3, step 3 -- trying to go around the process"
  sed -i "s/^\tA(\"mail\"/\tA(\"${BOT_USER}-quick\", \"203.0.113.99\"),\n&/" dnsconfig.js
  run_cmd "git diff"
  run_cmd "dnscontrol preview"
  run_cmd "dnscontrol push"
  narrate "refused with 403, as expected: only CI changes dojo.test. Now straight to main"
  run_cmd "git commit -am 'Quick add of ${BOT_USER}-quick'"
  run_cmd "git push"
  narrate "main is protected -- putting everything back, on the latest main"
  run_cmd "git fetch"
  run_cmd "git reset --hard origin/main"
  run_cmd "dnscontrol preview"

  narrate "Lab 3, step 4 -- branch, add my own A record, review, commit"
  run_cmd "git checkout main"
  run_cmd "git pull"
  run_cmd "git checkout -B '$branch' main"

  dns_set_own_record "${BOT_USER}-app" "203.0.113.$(dns_octet 0)"
  run_cmd "dnscontrol preview"
  orient
  run_cmd "git status"
  run_cmd "git diff"

  if [ $(( ROUND % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) committing before staging, on purpose, to show what that looks like"
    run_cmd "git commit -m 'Add A record for $BOT_USER-app'"
    narrate "right -- nothing was staged. Fixing that."
  fi

  orient
  run_cmd "git add dnsconfig.js"
  run_cmd "git commit -m 'Add/update A record for $BOT_USER (round $ROUND)'"
  dns_catch_up
  run_cmd "git log -1"
}

# -- Lab 3, steps 4-5 -- push and open a pull request ------------------------
# Same shape as bot-runner.sh's own step_lab1_push_and_pr, but DNS-flavored
# title/body and PR against dns-team/dns-as-code.
step_dns_lab1_push_and_pr() {
  dns_key_env
  cd "$REPO_DIR" || return 1
  local branch; branch="$(branch_name "add-${BOT_USER}")"
  dns_catch_up
  narrate "Lab 3, step 4 -- push (bare form first)"
  run_cmd "git push"
  narrate "no upstream yet, as expected -- setting one"
  run_cmd "git push -u origin '$branch'"

  narrate "Lab 3, step 5 -- open a pull request"
  local pr_json pr_number
  pr_json="$(api_curl -X POST "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls" \
    -H 'Content-Type: application/json' \
    -d "{\"head\":\"$branch\",\"base\":\"main\",\"title\":\"[$BOT_USER] Add/update A record (round $ROUND)\",\"body\":\"Demo bot DNS change -- see the DNS Preview CI comment for the dnscontrol diff. Safe to approve and merge live, or close.\"}")"
  pr_number="$(printf '%s' "$pr_json" | grep -o '"number":[0-9]*' | head -1 | cut -d: -f2)"
  if [ -n "$pr_number" ]; then
    narrate "opened PR #$pr_number for $branch -- watch for the 'DNS Preview' CI comment"
    PENDING_PR_BRANCH="$branch"
    PENDING_PR_NUMBER="$pr_number"
  else
    narrate "PR open failed or already exists for $branch -- will re-check next round"
  fi
}

# -- Lab 3, steps 6-7 -- review Sensei's practice PR, merge mine, CI applies it
# Sensei (approve mode) approves this bot's PR; the bot reviews Sensei's own
# practice PR, then merges and checks the record is live. The merged PR's
# number is kept for Lab 5's rollback.
step_dns_lab3_merge() {
  dns_key_env
  cd "$REPO_DIR" || return 1
  local practice
  practice="$(dns_pr_for_branch dns-bot/add-status any)"
  if [ -n "$practice" ] && ! api_curl "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls/$practice/reviews" | grep -q "\"login\":\"$BOT_USER\""; then
    narrate "Lab 3, step 6 -- asking Sensei what to review, then reviewing Sensei's practice pull request #$practice"
    command -v sensei >/dev/null && run_cmd "sensei review"
    run_cmd "git fetch -q origin dns-bot/add-status"
    run_cmd "git diff main origin/dns-bot/add-status"
    api_curl -o /dev/null -X POST "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls/$practice/reviews" \
      -H 'Content-Type: application/json' \
      -d '{"event":"APPROVED","body":"One new record and one CREATE in the preview. Looks right."}'
  fi

  [ -n "$PENDING_PR_NUMBER" ] || return 0
  command -v sensei >/dev/null && run_cmd "sensei status"
  narrate "Lab 3, step 7 -- merge once Sensei approves and the DNS Preview check is green"
  if dns_merge_when_ready "$PENDING_PR_NUMBER" "$PENDING_PR_BRANCH" api; then
    printf '%s\n' "$PENDING_PR_NUMBER" > "$HOME/.dojo-bot-lab3-pr"
    run_cmd "git checkout main"
    run_cmd "git pull"
    narrate "giving CI a moment to run DNS Apply"
    sleep 25
    run_cmd "dig @dns-server ${BOT_USER}-app.dojo.test A +short"
    run_cmd "dnscontrol preview"
    run_cmd "git branch -D '$PENDING_PR_BRANCH'"
    PENDING_PR_BRANCH=""
    PENDING_PR_NUMBER=""
  fi
}

# -- Lab 1, step 7 (Part 1) -- a discarded scratch record and the trailing-dot
# mistake, in the bot's own zone. Entirely uncommitted (git restore at every
# discard point), so it leaves nothing behind.
step_dns_lab2_mistakes() {
  dns_key_env
  cd "$MY_ZONE_DIR" || return 1
  narrate "Lab 1, step 7 -- a scratch idea, then the trailing-dot mistake, both discarded"

  dns_set_own_record "scratch" "203.0.113.$(dns_octet 1)"
  run_cmd "dnscontrol preview"
  run_cmd "git diff dnsconfig.js"
  run_cmd "git restore dnsconfig.js"
  run_cmd "git status"

  python3 - "$BOT_USER" <<'PYEOF'
import sys
p = "dnsconfig.js"
s = open(p, encoding="utf-8").read()
head, sep, tail = s.rpartition(");")
s = head + '\tCNAME("broken", "www.%s.dojo.test"),\n' % sys.argv[1] + sep + tail
open(p, "w", encoding="utf-8").write(s)
PYEOF

  narrate "missing trailing dot on a CNAME target -- previewing to see dnscontrol catch it"
  run_cmd "dnscontrol preview"
  narrate "right -- config error, no trailing dot. Fixing it."
  sed -i "s/CNAME(\"broken\", \"www.${BOT_USER}.dojo.test\")/CNAME(\"broken\", \"www.${BOT_USER}.dojo.test.\")/" dnsconfig.js
  run_cmd "dnscontrol preview"
  run_cmd "git restore dnsconfig.js"
  run_cmd "git status"
  narrate "the opposite mistake -- a record name that already contains the zone"
  python3 - "$BOT_USER" <<'PYEOF'
import sys
p = "dnsconfig.js"
s = open(p, encoding="utf-8").read()
head, sep, tail = s.rpartition(");")
s = head + '\tA("www.%s.dojo.test", "203.0.113.55"),\n' % sys.argv[1] + sep + tail
open(p, "w", encoding="utf-8").write(s)
PYEOF
  run_cmd "dnscontrol preview"
  narrate "the zone twice, right -- throwing that away"
  run_cmd "git restore dnsconfig.js"
  narrate "and a name that was never created -- asking DNS for it in full"
  run_cmd "dig @dns-server nothere.$BOT_USER.dojo.test A"
}

# -- Lab 4 -- the dnsctl.py CLI wrapper, end to end --------------------------
# doctor/setup, the record wizard (non-interactive flags), submit, status, then
# Sensei approves the PR, merge, validate. dnsctl reads the Forgejo login from
# git's credential helper, which the bot's git already uses.
step_dns_lab4_dnsctl() {
  dns_key_env
  cd "$REPO_DIR" || return 1
  narrate "Lab 4 -- dnsctl.py, the CLI wrapper"
  run_cmd "git checkout main"
  run_cmd "git pull"
  run_cmd "python3 scripts/dnsctl.py doctor"
  run_cmd "python3 scripts/dnsctl.py setup"
  run_cmd "python3 scripts/dnsctl.py doctor"
  run_cmd "python3 scripts/dnsctl.py record list"
  run_cmd "python3 scripts/dnsctl.py lint"

  local name="${BOT_USER}-api${ROUND}" branch="dns/${BOT_USER}-r${ROUND}-api"
  narrate "the record wizard, then preview and submit"
  run_cmd "python3 scripts/dnsctl.py record add $name.dojo.test --type A --value 203.0.113.$(dns_octet 2) --yes"
  run_cmd "python3 scripts/dnsctl.py preview"
  run_cmd "python3 scripts/dnsctl.py submit 'Add $name.dojo.test' --branch '$branch' --yes"
  run_cmd "python3 scripts/dnsctl.py status"

  local pr; pr="$(dns_pr_for_branch "$branch")"
  if [ -z "$pr" ]; then
    narrate "no pull request found for $branch -- moving on"
    run_cmd "git checkout main"
    return 0
  fi
  narrate "PR #$pr is open -- Sensei approves it, then merge and validate"
  if dns_merge_when_ready "$pr" "$branch" dnsctl; then
    run_cmd "git checkout main"
    run_cmd "git pull"
    narrate "giving CI a moment to run DNS Apply"
    sleep 20
    run_cmd "python3 scripts/dnsctl.py validate $pr"
    run_cmd "git branch -D '$branch'"
  fi
  run_cmd "git checkout main"
}

# -- Lab 5 -- investigating history, and rolling back the Lab 3 change -----
# history, then dnsctl.py rollback of this bot's own Lab 3 PR (remembered by
# step_dns_lab3_merge), which opens a revert PR; Sensei approves it (it removes
# one record of the bot's own), and it is merged like any other.
step_dns_lab5_history() {
  dns_key_env
  cd "$REPO_DIR" || return 1
  narrate "Lab 5 -- investigating history and rolling back my Lab 3 change"
  run_cmd "git checkout main"
  run_cmd "git pull"
  run_cmd "python3 scripts/dnsctl.py history"
  run_cmd "git log --oneline -5 -- dnsconfig.js"

  local target=""
  [ -r "$HOME/.dojo-bot-lab3-pr" ] && target="$(cat "$HOME/.dojo-bot-lab3-pr")"
  if [ -z "$target" ]; then
    narrate "no merged Lab 3 PR of mine to roll back yet"
    return 0
  fi
  run_cmd "git branch --list 'dns/revert-*' | xargs -r git branch -D"
  run_cmd "python3 scripts/dnsctl.py rollback $target --yes"
  # A classmate's record merged next to mine makes the revert conflict (likely in a class): keep their lines,
  # drop the ones my PR added, and submit, as dnsctl's message says.
  if [ -n "$(git ls-files -u dnsconfig.js)" ]; then
    narrate "the revert conflicts with a later change -- keeping theirs, dropping mine"
    run_cmd "git diff dnsconfig.js"
    local sha
    sha="$(git rev-parse REVERT_HEAD)"
    git diff "$sha^1" "$sha" -- dnsconfig.js | sed -n 's/^+\([^+]\)/\1/p' > "$HOME/.dojo-bot-revert-drop"
    python3 - "$HOME/.dojo-bot-revert-drop" <<'PYEOF'
import sys
drop = set(open(sys.argv[1], encoding="utf-8").read().splitlines())
out, side = [], None
for line in open("dnsconfig.js", encoding="utf-8").read().splitlines():
    if line.startswith("<<<<<<< "): side = "ours"; continue
    if (line.startswith("=======") or line.startswith("||||||| ")) and side: side = "theirs"; continue
    if line.startswith(">>>>>>> ") and side: side = None; continue
    if side == "theirs" or (side == "ours" and line in drop): continue
    out.append(line)
open("dnsconfig.js", "w", encoding="utf-8").write("\n".join(out) + "\n")
PYEOF
    rm -f "$HOME/.dojo-bot-revert-drop"
    run_cmd "git add dnsconfig.js"
    run_cmd "python3 scripts/dnsctl.py submit \"Revert: $(git log -1 --format=%s "$sha" | tr -d '\"')\" --yes"
  fi
  local pr branch
  pr="$(dns_pr_for_branch dns/revert-)"
  if [ -z "$pr" ]; then
    narrate "the rollback did not open a PR -- cleaning up"
    git rev-parse -q --verify REVERT_HEAD >/dev/null && run_cmd "git revert --abort"
    run_cmd "git checkout main"
    return 0
  fi
  branch="$(git rev-parse --abbrev-ref HEAD)"
  narrate "rollback PR #$pr is open -- Sensei approves it, then merge"
  if dns_merge_when_ready "$pr" "$branch" dnsctl; then
    rm -f "$HOME/.dojo-bot-lab3-pr"
    run_cmd "git checkout main"
    run_cmd "git pull"
    run_cmd "git branch -D '$branch'"
  fi
  run_cmd "git checkout main"
}

# -- Lab 6 -- a merge conflict in dnsconfig.js -------------------------------
# All local, all throwaway branches, never pushed -- safe regardless of
# what any other step/round is mid-way through.
step_dns_lab6_conflict() {
  dns_key_env
  cd "$REPO_DIR" || return 1
  narrate "Lab 6 -- causing and resolving a DNS merge conflict"
  orient
  local a b
  a="$(branch_name "conflict-a")"
  b="$(branch_name "conflict-b")"

  run_cmd "git checkout main"
  run_cmd "git checkout -B '$a'"
  run_cmd "sed -i 's/A(\"www\", \"[0-9.]*\")/A(\"www\", \"203.0.113.40\")/' dnsconfig.js"
  run_cmd "git add dnsconfig.js"
  run_cmd "git commit -m 'conflict-a: repoint www'"

  run_cmd "git checkout main"
  run_cmd "git checkout -B '$b'"
  run_cmd "sed -i 's/A(\"www\", \"[0-9.]*\")/A(\"www\", \"203.0.113.50\")/' dnsconfig.js"
  run_cmd "git add dnsconfig.js"
  run_cmd "git commit -m 'conflict-b: repoint www'"

  run_cmd "git merge '$a'"
  narrate "conflict, as expected -- resolving by keeping conflict-a's value"
  run_cmd "sed -i '/^<<<<<<</,/^=======/d; /^>>>>>>>/d' dnsconfig.js"
  run_cmd "grep 'A(\"www\"' dnsconfig.js"

  narrate "Lab 6 Part B -- always preview after resolving, before committing the merge"
  run_cmd "dnscontrol preview"
  run_cmd "git add dnsconfig.js"
  run_cmd "git commit --no-edit"

  run_cmd "git checkout main"
  run_cmd "git branch -D '$a' '$b'"
}

# -- persona-flavored orient() override --------------------------------------
# Same idea as bot-runner.sh's default (occasional look-around commands),
# but DNS-flavored: a preview/dig sanity check instead of just `git status`.
orient() {
  [ $(( RANDOM % 100 )) -lt "$ORIENT_FREQ" ] || return 0
  case "$PERSONA" in
    expert)
      run_cmd "git status -sb"
      ;;
    intermediate)
      case $(( RANDOM % 3 )) in
        0) run_cmd "dnscontrol preview" ;;
        1) run_cmd "git status" ;;
        2) run_cmd "dig @dns-server dojo.test A +short" ;;
      esac
      ;;
    novice)
      case $(( RANDOM % 5 )) in
        0) run_cmd "pwd" ;;
        1) run_cmd "ls -la" ;;
        2) run_cmd "whoami" ;;
        3)
          if [ $(( RANDOM % 100 )) -lt 40 ]; then
            run_cmd "dnscontol preview"
            narrate "typo -- trying again"
          fi
          run_cmd "dnscontrol preview"
          ;;
        4) run_cmd "cat docs/record-types.md 2>/dev/null | tail -5 || ls" ;;
      esac
      ;;
  esac
}

case "$PERSONA" in
  expert)
    STEPS=(
      step_ensure_clone
      step_sync_main
      step_dns_baseline
      step_dns_lab1_remove
      step_dns_lab2_mistakes
      step_dns_lab2_drift
      step_dns_lab1_branch_and_edit
      step_dns_lab1_push_and_pr
      step_dns_lab3_merge
      step_dns_lab4_dnsctl
      step_dns_lab5_history
      step_dns_lab6_conflict
      step_wrap_round
    )
    ;;
  intermediate)
    STEPS=(
      step_ensure_clone
      step_sync_main
      step_dns_baseline
      step_dns_lab1_remove
      step_dns_lab2_mistakes
      step_dns_lab2_drift
      step_dns_lab1_branch_and_edit
      step_dns_lab1_push_and_pr
      step_dns_lab3_merge
      step_dns_lab4_dnsctl
      step_wrap_round
    )
    ;;
  novice)
    STEPS=(
      step_ensure_clone
      step_sync_main
      step_dns_baseline
      step_dns_lab1_branch_and_edit
      step_dns_lab1_push_and_pr
      step_dns_lab3_merge
      step_wrap_round
    )
    ;;
esac
