# DNS as Code demo bot steps -- sourced by engine/web-terminal/bot-runner.sh
# after its own helpers/defaults are defined (see BOT_STEPS_FILE there). Runs
# the dns-as-code labs instead of git-fundamentals: preview/apply the zone,
# add/edit an A record on a branch + PR (Lab 1), catch mistakes before a
# commit (Lab 2), the dnsctl.py wrapper (Lab 3, local-only -- see note on
# step_dns_lab3_dnsctl), history + a local rollback demo (Lab 4), and a
# dnsconfig.js merge conflict (Lab 5). step_ensure_clone/step_sync_main from
# bot-runner.sh are reused as-is; everything else here is dns-as-code-specific.

# -- helper: insert-or-update this bot's own A record -----------------------
# Mirrors lab1.md's python3 fallback for editing dnsconfig.js (the lab's own
# suggested non-interactive method). Uses argv, not string interpolation
# into the script body, so $BOT_USER never has to be quoted into Python
# source. Inserts before the "mail" A record if $BOT_USER has no record yet,
# otherwise updates its existing value in place (this is what makes round 2+
# look like lab2.md Part A -- editing an existing record).
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
else:
    s = s.replace(
        'A("mail"',
        'A("%s", "%s"),\n\tA("mail"' % (name, ip),
        1,
    )
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

# -- Lab 1, steps 2-3 -- preview then apply the starting zone ---------------
# Idempotent (preview/push both are), so safe to repeat every round: after
# the first apply it's just a quick "still clean" sanity check, same as a
# student would do out of habit.
step_dns_baseline() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 1, steps 2-3 -- preview, then apply, the starting zone"
  run_cmd "dnscontrol preview"
  run_cmd "dnscontrol push"
  run_cmd "dig @dns-server dojo.test A +short"
  run_cmd "dig @dns-server www.dojo.test A +short"
  run_cmd "dig @dns-server dojo.test MX +short"
  run_cmd "dnscontrol preview"
}

# -- Lab 1, steps 4-7 -- branch, add/edit my own A record, review, commit ---
step_dns_lab1_branch_and_edit() {
  cd "$REPO_DIR" || return 1
  local branch; branch="$(branch_name "add-${BOT_USER}")"
  narrate "Lab 1, steps 4-7 -- branch, add my own A record, review, commit"
  run_cmd "git checkout -B '$branch' main"

  dns_set_own_record "$BOT_USER" "203.0.113.$(dns_octet 0)"
  run_cmd "dnscontrol preview"
  orient
  run_cmd "git status"
  run_cmd "git diff"

  if [ $(( ROUND % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) committing before staging, on purpose, to show what that looks like"
    run_cmd "git commit -m 'Add A record for $BOT_USER'"
    narrate "right -- nothing was staged. Fixing that."
  fi

  orient
  run_cmd "git add dnsconfig.js"
  run_cmd "git commit -m 'Add/update A record for $BOT_USER (round $ROUND)'"
  run_cmd "git log -1"
}

# -- Lab 1, steps 7-8 -- push and open a pull request ------------------------
# Same shape as bot-runner.sh's own step_lab1_push_and_pr, but DNS-flavored
# title/body and PR against dns-team/dns-as-code.
step_dns_lab1_push_and_pr() {
  cd "$REPO_DIR" || return 1
  local branch; branch="$(branch_name "add-${BOT_USER}")"
  narrate "Lab 1, step 7 -- push (bare form first, like the lab shows)"
  run_cmd "git push"
  narrate "no upstream yet, as expected -- setting one"
  run_cmd "git push -u origin '$branch'"

  narrate "Lab 1, step 8 -- open a pull request"
  local pr_json pr_number
  pr_json="$(api_curl -X POST "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls" \
    -H 'Content-Type: application/json' \
    -d "{\"head\":\"$branch\",\"base\":\"main\",\"title\":\"[$BOT_USER] Add/update A record (round $ROUND)\",\"body\":\"Demo bot DNS change -- see the DNS Preview CI comment for the dnscontrol diff. Safe to review and merge live, or close.\"}")"
  pr_number="$(printf '%s' "$pr_json" | grep -o '"number":[0-9]*' | head -1 | cut -d: -f2)"
  if [ -n "$pr_number" ]; then
    narrate "opened PR #$pr_number for $branch -- watch for the 'DNS Preview' CI comment"
    PENDING_PR_BRANCH="$branch"
    PENDING_PR_NUMBER="$pr_number"
  else
    narrate "PR open failed or already exists for $branch -- will re-check next round"
  fi
}

# -- Lab 2 -- editing, a discarded scratch record, and the trailing-dot mistake
# Entirely uncommitted (git restore at every discard point), so it never
# competes with the Lab 1 branch/PR above and leaves nothing behind.
step_dns_lab2_mistakes() {
  cd "$REPO_DIR" || return 1
  local branch; branch="$(branch_name "add-${BOT_USER}")"
  narrate "Lab 2 -- editing, catching a scratch idea before it's committed, and the trailing-dot mistake"
  run_cmd "git checkout '$branch' 2>/dev/null || git checkout -B '$branch' main"

  # Part B: a scratch record, previewed, then thrown away uncommitted.
  dns_set_own_record "${BOT_USER}-scratch" "203.0.113.$(dns_octet 1)"
  run_cmd "dnscontrol preview"
  run_cmd "git diff dnsconfig.js"
  run_cmd "git restore dnsconfig.js"
  run_cmd "git status"

  # Part D: the classic missing-trailing-dot mistake, then the fix, then discard.
  printf '\tCNAME("%s-broken", "dojo.test"),\n' "$BOT_USER" >> dnsconfig.js

  if [ $(( ROUND % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) missing trailing dot on a CNAME target -- previewing to see dnscontrol catch it"
    run_cmd "dnscontrol preview"
    narrate "right -- config error, no trailing dot. Fixing it."
  fi
  sed -i "s/CNAME(\"${BOT_USER}-broken\", \"dojo.test\")/CNAME(\"${BOT_USER}-broken\", \"dojo.test.\")/" dnsconfig.js
  run_cmd "dnscontrol preview"
  run_cmd "git restore dnsconfig.js"
  run_cmd "git status"
}

# -- Lab 3 -- the dnsctl.py CLI wrapper --------------------------------------
# Local-only commands (doctor/setup/record list/lint/show) plus a
# record-add-then-discard, all non-interactive (--yes/--type/--value/
# --no-proxy). Deliberately never calls submit/status/merge/rollback --
# those need a cached Forgejo login (dnsctl_lib/forgejo.py prompts for one
# with no non-interactive override besides FORGEJO_TOKEN, which this bot
# has no use for) and would open a second, untracked PR alongside the one
# Lab 1's step already tracks via PENDING_PR_BRANCH/NUMBER.
step_dns_lab3_dnsctl() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 3 -- dnsctl.py, the CLI wrapper (local commands)"
  run_cmd "git checkout main"
  run_cmd "python3 scripts/dnsctl.py doctor"
  run_cmd "python3 scripts/dnsctl.py setup"
  run_cmd "python3 scripts/dnsctl.py doctor"
  run_cmd "python3 scripts/dnsctl.py record list"
  run_cmd "python3 scripts/dnsctl.py lint"

  narrate "trying the record wizard, non-interactively, then discarding it"
  run_cmd "python3 scripts/dnsctl.py record add ${BOT_USER}-wizard.dojo.test --type A --value 203.0.113.$(dns_octet 2) --no-proxy --yes"
  run_cmd "python3 scripts/dnsctl.py preview"
  run_cmd "git restore dnsconfig.js"
  run_cmd "git status"
}

# -- Lab 4 -- investigating history, and a local (unpushed) rollback demo ---
# Uses the raw-git equivalent lab4.md itself offers as an alternative to
# `dnsctl.py history`/`rollback` (which, like Lab 3's submit/merge, need
# forge auth this bot doesn't set up) -- git log/show to investigate, then
# a revert on a disposable local branch to demonstrate the mechanism, never
# pushed, always cleaned up.
step_dns_lab4_history() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 4 -- investigating history and a local rollback demo"
  run_cmd "git checkout main"
  run_cmd "git pull"
  run_cmd "git log --oneline -5 -- dnsconfig.js"

  local last_hash; last_hash="$(git log -1 --format=%H -- dnsconfig.js 2>/dev/null)"
  if [ -n "$last_hash" ]; then
    run_cmd "git show --stat $last_hash"
    local branch; branch="$(branch_name "lab4-rollback-demo")"
    orient
    run_cmd "git checkout -B '$branch'"
    narrate "reverting that commit locally to see the inverse diff -- never pushed"
    run_cmd "git revert --no-edit '$last_hash' || git revert --abort"
    run_cmd "dnscontrol preview"
    run_cmd "git checkout main"
    run_cmd "git branch -D '$branch'"
  else
    run_cmd "git status"
  fi
}

# -- Lab 5 -- a merge conflict in dnsconfig.js -------------------------------
# All local, all throwaway branches, never pushed -- safe regardless of
# what any other step/round is mid-way through.
step_dns_lab5_conflict() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 5 -- causing and resolving a DNS merge conflict"
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

  narrate "Lab 5 Part B -- always preview after resolving, before committing the merge"
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
      step_dns_lab1_branch_and_edit
      step_dns_lab1_push_and_pr
      step_dns_lab2_mistakes
      step_dns_lab3_dnsctl
      step_dns_lab4_history
      step_dns_lab5_conflict
      step_wrap_round
    )
    ;;
  intermediate)
    STEPS=(
      step_ensure_clone
      step_sync_main
      step_dns_baseline
      step_dns_lab1_branch_and_edit
      step_dns_lab1_push_and_pr
      step_dns_lab2_mistakes
      step_dns_lab3_dnsctl
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
      step_wrap_round
    )
    ;;
esac
