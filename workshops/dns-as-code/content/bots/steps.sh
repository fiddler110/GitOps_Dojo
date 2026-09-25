# DNS as Code demo bot steps -- sourced by engine/web-terminal/bot-runner.sh
# after its own helpers/defaults are defined (see BOT_STEPS_FILE there). Runs
# the dns-as-code labs instead of git-fundamentals. Part 1, in the bot's own
# zone (~/lab/my-zone, <bot>.dojo.test): preview/push/verify, add records and
# catch mistakes (Lab 1). Part 2, in the shared repo: a refused local push,
# then an A record on a branch + PR (Lab 3), the dnsctl.py wrapper (Lab 4,
# local-only -- see note on step_dns_lab4_dnsctl), history + a local rollback
# demo (Lab 5), and a dnsconfig.js merge conflict (Lab 6).
# step_ensure_clone/step_sync_main from bot-runner.sh are reused as-is;
# everything else here is dns-as-code-specific.

# Part 1 sandbox, made by compose/terminal/start.d/90-my-zone.sh.
MY_ZONE_DIR="$HOME/lab/my-zone"

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

# -- Lab 1 (Part 1) -- the bot's own zone: preview, push, verify, add a record
# Idempotent (preview/push both are), so safe to repeat every round: the
# first round creates <bot>.dojo.test, later ones MODIFY its app record.
step_dns_baseline() {
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

# -- Lab 3 (Part 2) -- a refused local push, then branch, add, commit -------
step_dns_lab1_branch_and_edit() {
  cd "$REPO_DIR" || return 1
  local branch; branch="$(branch_name "add-${BOT_USER}")"
  narrate "Lab 3, step 3 -- trying to push the shared zone from my terminal"
  run_cmd "git checkout -q main"
  sed -i 's/203.0.113.20/203.0.113.99/' dnsconfig.js
  run_cmd "dnscontrol push"
  narrate "refused with 403, as expected: only CI changes dojo.test"
  run_cmd "git restore dnsconfig.js"

  narrate "Lab 3, step 4 -- branch, add my own A record, review, commit"
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
  run_cmd "git log -1"
}

# -- Lab 3, steps 4-5 -- push and open a pull request ------------------------
# Same shape as bot-runner.sh's own step_lab1_push_and_pr, but DNS-flavored
# title/body and PR against dns-team/dns-as-code.
step_dns_lab1_push_and_pr() {
  cd "$REPO_DIR" || return 1
  local branch; branch="$(branch_name "add-${BOT_USER}")"
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

# -- Lab 1, step 7 (Part 1) -- a discarded scratch record and the trailing-dot
# mistake, in the bot's own zone. Entirely uncommitted (git restore at every
# discard point), so it leaves nothing behind.
step_dns_lab2_mistakes() {
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

  if [ $(( ROUND % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) missing trailing dot on a CNAME target -- previewing to see dnscontrol catch it"
    run_cmd "dnscontrol preview"
    narrate "right -- config error, no trailing dot. Fixing it."
  fi
  sed -i "s/CNAME(\"broken\", \"www.${BOT_USER}.dojo.test\")/CNAME(\"broken\", \"www.${BOT_USER}.dojo.test.\")/" dnsconfig.js
  run_cmd "dnscontrol preview"
  run_cmd "git restore dnsconfig.js"
  run_cmd "git status"
}

# -- Lab 4 -- the dnsctl.py CLI wrapper --------------------------------------
# Local-only commands (doctor/setup/record list/lint/show) plus a
# record-add-then-discard, all non-interactive (--yes/--type/--value/
# --no-proxy). Deliberately never calls submit/status/merge/rollback --
# those need a cached Forgejo login (dnsctl_lib/forgejo.py prompts for one
# with no non-interactive override besides FORGEJO_TOKEN, which this bot
# has no use for) and would open a second, untracked PR alongside the one
# Lab 3's step already tracks via PENDING_PR_BRANCH/NUMBER.
step_dns_lab4_dnsctl() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 4 -- dnsctl.py, the CLI wrapper (local commands)"
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

# -- Lab 5 -- investigating history, and a local (unpushed) rollback demo ---
# Uses the raw-git equivalent lab5.md itself offers as an alternative to
# `dnsctl.py history`/`rollback` (which, like Lab 4's submit/merge, need
# forge auth this bot doesn't set up) -- git log/show to investigate, then
# a revert on a disposable local branch to demonstrate the mechanism, never
# pushed, always cleaned up.
step_dns_lab5_history() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 5 -- investigating history and a local rollback demo"
  run_cmd "git checkout main"
  run_cmd "git pull"
  run_cmd "git log --oneline -5 -- dnsconfig.js"

  local last_hash; last_hash="$(git log -1 --format=%H -- dnsconfig.js 2>/dev/null)"
  if [ -n "$last_hash" ]; then
    run_cmd "git show --stat $last_hash"
    local branch; branch="$(branch_name "lab5-rollback-demo")"
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

# -- Lab 6 -- a merge conflict in dnsconfig.js -------------------------------
# All local, all throwaway branches, never pushed -- safe regardless of
# what any other step/round is mid-way through.
step_dns_lab6_conflict() {
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
      step_dns_lab2_mistakes
      step_dns_lab1_branch_and_edit
      step_dns_lab1_push_and_pr
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
      step_dns_lab2_mistakes
      step_dns_lab1_branch_and_edit
      step_dns_lab1_push_and_pr
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
      step_wrap_round
    )
    ;;
esac
