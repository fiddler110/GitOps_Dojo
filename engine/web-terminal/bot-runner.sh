#!/bin/bash
# Demo/test "student" bot -- see engine/README.md's "Demo bots (--test)"
# section. Runs as one of the testuserN Linux accounts, inside the tmux
# `main` session bot-supervisor.sh creates for it (same session name and
# mechanism workspace-control.py already uses for a real student's `term`
# tool -- see workspace-control.py's TMUX_SESSION -- so the facilitator's
# existing /admin/watch/<id> tile works on a bot with no special-casing on
# that side beyond allocator/server.py's BOT_IDS).
#
# Works through the git-fundamentals labs (clone, branch, edit, commit,
# push, PR, plus the lab2-5 review/stash/history/conflict/undo exercises)
# at a slow, human-ish pace, on branches named "<BOT_USER>/round<N>-...",
# deliberately typing a wrong command here and there and then correcting
# it -- so a facilitator watching gets constantly-changing terminal output
# and traceable Forgejo activity, without needing a real second person.
#
# Resumable by design: progress is a single (round, step) pair in
# ~/.dojo-bot-state, rewritten after each step completes. bot-supervisor.sh
# restarts this script (fresh process, same account, same home directory)
# any time the tmux session it runs in disappears -- most notably right
# after a facilitator clicks Release, which kills every process owned by
# this account. On restart, execution just skips every step index already
# recorded as done and continues from there -- see run_round below.
set -u

HOME="${HOME:-/home/$(whoami)}"
cd "$HOME" || exit 1

# Written by entrypoint.sh at container start: BOT_USER, BOT_PASSWORD,
# FORGEJO_ORG, FORGEJO_REPO. Kept in a file (not passed as argv/env from
# bot-supervisor.sh) so it survives this process being killed and restarted
# with no memory of how it was originally launched.
BOT_ENV_FILE="$HOME/.dojo-bot.env"
if [ ! -f "$BOT_ENV_FILE" ]; then
  echo "bot-runner: missing $BOT_ENV_FILE, cannot start" >&2
  exit 1
fi
# shellcheck disable=SC1090
. "$BOT_ENV_FILE"
: "${BOT_USER:?BOT_USER not set in $BOT_ENV_FILE}"
: "${BOT_PASSWORD:?BOT_PASSWORD not set in $BOT_ENV_FILE}"
: "${FORGEJO_ORG:=training}"
: "${FORGEJO_REPO:=sample-training-repo}"

REPO_DIR="$HOME/lab/sample-training-repo"
STATE_FILE="$HOME/.dojo-bot-state"
GIT_SERVER="git-server:3000"
API="http://$GIT_SERVER/api/v1"
NETRC="$HOME/.dojo-bot-netrc"
BOT_LOG="$HOME/.dojo-bot.log"
BOT_LOG_MAX_BYTES="${BOT_LOG_MAX_BYTES:-1048576}"

# A facilitator watching live sees this bot's tmux pane, but that
# scrollback (tmux.conf's history-limit) is lost every time
# bot-supervisor.sh restarts this process -- most notably right after a
# Release -- so if nobody was watching when something went wrong, there's
# no way to see why afterward. Mirror everything this script prints to a
# durable per-bot log (opened in append mode, so it survives restarts) and
# keep it capped at BOT_LOG_MAX_BYTES so a long-running workshop doesn't
# grow it unbounded -- this is scrollback for troubleshooting, not an
# audit trail, so truncating to the tail is fine.
trim_log() {
  [ -f "$BOT_LOG" ] || return 0
  local size
  size="$(wc -c < "$BOT_LOG" 2>/dev/null || echo 0)"
  if [ "$size" -gt "$BOT_LOG_MAX_BYTES" ]; then
    tail -c "$BOT_LOG_MAX_BYTES" "$BOT_LOG" > "$BOT_LOG.tmp" 2>/dev/null && mv -f "$BOT_LOG.tmp" "$BOT_LOG"
  fi
}
trim_log
exec > >(tee -a "$BOT_LOG") 2>&1

# Non-interactive git auth: the clone URL embeds the bot's own username, so
# git only ever prompts for a password, which GIT_ASKPASS supplies. See
# /opt/dojo-shell/bot-askpass.sh. GIT_TERMINAL_PROMPT=0 is a backstop --
# fail fast instead of hanging forever if askpass somehow isn't consulted.
export GIT_ASKPASS=/opt/dojo-shell/bot-askpass.sh
export GIT_TERMINAL_PROMPT=0
export BOT_PASSWORD

# No human is watching this tmux session to drive a pager or an editor, so
# any git command that would normally spawn one (log/diff/show through
# `less`, or a commit/merge/rebase without -m/--no-edit through $EDITOR)
# just hangs run_cmd forever -- and since the tmux session itself stays up,
# bot-supervisor.sh's "session missing" check never notices, so it never
# gets restarted. GIT_PAGER=cat sidesteps the pager unconditionally (more
# reliable than counting on `less -FRX`'s auto-exit-if-it-fits, which
# still pages once output outgrows the pty). GIT_EDITOR=true is a backstop
# for any editor invocation this script doesn't already avoid via -m/
# --no-edit: it exits 0 immediately, so e.g. a commit falls back to git's
# usual "aborting commit due to empty message" behavior instead of hanging.
export GIT_PAGER=cat
export GIT_EDITOR=true

printf 'machine %s\n\tlogin %s\n\tpassword %s\n' "$GIT_SERVER" "$BOT_USER" "$BOT_PASSWORD" > "$NETRC"
chmod 600 "$NETRC"
api_curl() { curl -s --netrc-file "$NETRC" "$@"; }

# -- persona -----------------------------------------------------------
# Each bot plays a different skill level, derived from its own trailing
# number (testuser1/4/7... -> expert, testuser2/5/8... -> intermediate,
# testuser3/6/9... -> novice) so a facilitator watching all of them side by
# side sees genuinely different pacing, command choices, and mistake
# frequency -- not three copies of the same script. Concretely this affects:
#   - think()/type_out() delays (an expert types fast and barely pauses; a
#     terminal novice hunts for keys and reads before acting)
#   - orient(): how often, and with what commands, a bot "looks around"
#     (pwd/ls/whoami/cat/extra git status) beyond what the lab strictly asks
#   - MISTAKE_MOD/REM: how often the scripted mistakes in
#     step_lab1_branch_and_edit / step_lab4_history fire
#   - which labs a round even attempts (see the PERSONA case below the STEPS
#     array) -- the expert works all the way through Lab 5 every round, the
#     novice never gets past Lab 2. Sized so a ~10-minute demo window shows
#     the expert cycling through the whole curriculum a couple of times
#     while the novice is still visibly stuck early on -- see
#     engine/README.md's "Demo bots (--test)" section for the walkthrough
#     this was tuned against.
bot_num="$(printf '%s' "$BOT_USER" | grep -o '[0-9]\+' | head -1)"
[ -z "$bot_num" ] && bot_num=1
case $(( (bot_num - 1) % 3 )) in
  0) PERSONA=expert ;;
  1) PERSONA=intermediate ;;
  2) PERSONA=novice ;;
esac

case "$PERSONA" in
  expert)
    : "${BOT_MIN_DELAY:=1}"; : "${BOT_MAX_DELAY:=3}"
    : "${BOT_TYPE_DELAY_MIN:=1}"; : "${BOT_TYPE_DELAY_MAX:=2}"
    : "${BOT_ROUND_BREAK_MIN:=10}"; : "${BOT_ROUND_BREAK_MAX:=20}"
    MISTAKE_MOD=8; MISTAKE_REM=0
    ORIENT_FREQ=10
    TYPO_FLICKER_PCT=0
    ;;
  intermediate)
    : "${BOT_MIN_DELAY:=3}"; : "${BOT_MAX_DELAY:=7}"
    : "${BOT_TYPE_DELAY_MIN:=2}"; : "${BOT_TYPE_DELAY_MAX:=4}"
    : "${BOT_ROUND_BREAK_MIN:=20}"; : "${BOT_ROUND_BREAK_MAX:=35}"
    MISTAKE_MOD=3; MISTAKE_REM=0
    ORIENT_FREQ=35
    TYPO_FLICKER_PCT=2
    ;;
  novice)
    : "${BOT_MIN_DELAY:=6}"; : "${BOT_MAX_DELAY:=14}"
    : "${BOT_TYPE_DELAY_MIN:=4}"; : "${BOT_TYPE_DELAY_MAX:=9}"
    : "${BOT_ROUND_BREAK_MIN:=25}"; : "${BOT_ROUND_BREAK_MAX:=45}"
    MISTAKE_MOD=2; MISTAKE_REM=0
    ORIENT_FREQ=70
    TYPO_FLICKER_PCT=6
    ;;
esac

# -- small "is this a live demo" presentation helpers ------------------------

rand_between() { # min max
  echo $(( $1 + RANDOM % ($2 - $1 + 1) ))
}

think() { sleep "$(rand_between "$BOT_MIN_DELAY" "$BOT_MAX_DELAY")"; }

narrate() { # a dim comment line, so a facilitator watching can follow along
  printf '\n\033[2m# %s\033[0m\n' "$1"
  sleep 1
}

type_out() { # print a string with a per-character delay, like slow typing.
  # Persona-paced via BOT_TYPE_DELAY_MIN/MAX (hundredths of a second, kept
  # single-digit so the "0.0<n>" literal below stays valid). A novice also
  # occasionally "fumbles" a keystroke on screen -- purely cosmetic, the
  # real command below is unaffected -- to look like someone still hunting
  # for keys, not a script.
  local s="$1" i c
  for (( i=0; i<${#s}; i++ )); do
    c="${s:$i:1}"
    if [ "$c" != " " ] && [ $(( RANDOM % 100 )) -lt "$TYPO_FLICKER_PCT" ]; then
      printf 'x'
      sleep 0.15
      printf '\b \b'
    fi
    printf '%s' "$c"
    sleep "0.0$(rand_between "$BOT_TYPE_DELAY_MIN" "$BOT_TYPE_DELAY_MAX")"
  done
  printf '\n'
}

# Occasional persona-flavored "looking around" commands beyond what the lab
# strictly asks for -- pwd/ls/whoami/cat for a novice getting their
# bearings, a quick `git status -sb` for an expert doing a final sanity
# check, a mix for someone in between. This is the main source of the
# "different commands at different times" variety between the three bots,
# on top of the delay/mistake differences above.
orient() {
  [ $(( RANDOM % 100 )) -lt "$ORIENT_FREQ" ] || return 0
  case "$PERSONA" in
    expert)
      run_cmd "git status -sb"
      ;;
    intermediate)
      case $(( RANDOM % 3 )) in
        0) run_cmd "ls" ;;
        1) run_cmd "git status" ;;
        2) run_cmd "pwd" ;;
      esac
      ;;
    novice)
      case $(( RANDOM % 5 )) in
        0) run_cmd "pwd" ;;
        1) run_cmd "ls -la" ;;
        2) run_cmd "whoami" ;;
        3)
          if [ $(( RANDOM % 100 )) -lt 40 ]; then
            run_cmd "gt status"
            narrate "typo -- trying again"
          fi
          run_cmd "git status"
          ;;
        4) run_cmd "cat roster/team.yaml 2>/dev/null | tail -5 || ls" ;;
      esac
      ;;
  esac
}

# Prints a fake shell prompt, "types" the command, then actually runs it.
# Failures are NOT fatal here -- several call sites deliberately run a
# command expected to fail (a typo, a forgotten `git add`, deleting a
# checked-out branch) to show the student-realistic error, then correct it.
run_cmd() {
  printf '%s@%s:~%s$ ' "$BOT_USER" "$(hostname 2>/dev/null || echo dojo)" "${PWD#"$HOME"}"
  type_out "$1"
  eval "$1"
  local rc=$?
  think
  return $rc
}

# -- resumable state -----------------------------------------------------
# Format: two lines, "ROUND=<n>" and "STEP=<n>", plus optional
# PENDING_PR_BRANCH=/PENDING_PR_NUMBER= carried between rounds so a
# not-yet-merged lab1 PR gets checked again (and cleaned up) once it is.

ROUND=1
STEP=0
PENDING_PR_BRANCH=""
PENDING_PR_NUMBER=""

load_state() {
  [ -f "$STATE_FILE" ] || return 0
  # shellcheck disable=SC1090
  . "$STATE_FILE"
}

save_state() {
  local tmp
  tmp="$(mktemp "$HOME/.dojo-bot-state.XXXXXX")"
  {
    printf 'ROUND=%s\n' "$ROUND"
    printf 'STEP=%s\n' "$STEP"
    printf 'PENDING_PR_BRANCH=%s\n' "$PENDING_PR_BRANCH"
    printf 'PENDING_PR_NUMBER=%s\n' "$PENDING_PR_NUMBER"
  } > "$tmp"
  mv -f "$tmp" "$STATE_FILE"
}

load_state
narrate "resuming $BOT_USER at round $ROUND, step $STEP"

branch_name() { # $1 = topic
  printf '%s/round%s-%s' "$BOT_USER" "$ROUND" "$1"
}

# -- lab step functions ---------------------------------------------------
# Each one is written to be safe to re-run from scratch (checkout -B instead
# of -b, existence checks before acting) since a restart always re-enters
# the step it was on, not partway through it.

step_ensure_clone() {
  if [ -d "$REPO_DIR/.git" ]; then
    return 0
  fi
  narrate "Lab 1, step 1 -- clone the sample repo"
  cd "$HOME/lab" || return 1
  run_cmd "git clone http://${BOT_USER}@${GIT_SERVER}/${FORGEJO_ORG}/${FORGEJO_REPO}.git"
  cd "$REPO_DIR" || return 1
  run_cmd "git config user.name '$BOT_USER'"
  run_cmd "git config user.email '${BOT_USER}@example.com'"
}

step_sync_main() {
  if [ "$PERSONA" = "novice" ] && [ $(( RANDOM % 100 )) -lt 30 ]; then
    narrate "(demo) checking status before actually being in the repo directory"
    run_cmd "git status"
    narrate "right -- wrong directory. Heading into the repo."
  fi
  if [ "$PERSONA" = "novice" ] && [ -d "$HOME/lab" ] && [ $(( RANDOM % 100 )) -lt 50 ]; then
    narrate "double-checking the lab instructions before diving in"
    run_cmd "ls ~/lab"
    [ -f "$HOME/lab/lab1.md" ] && run_cmd "head -n 15 ~/lab/lab1.md"
  fi

  cd "$REPO_DIR" || return 1
  narrate "start of round $ROUND -- syncing main and checking last round's PR"
  run_cmd "git checkout main"
  run_cmd "git pull"
  run_cmd "git fetch --prune"
  orient

  if [ -n "$PENDING_PR_NUMBER" ]; then
    local merged
    merged="$(api_curl "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls/$PENDING_PR_NUMBER" | grep -o '"merged":[a-z]*' | head -1 | cut -d: -f2)"
    if [ "$merged" = "true" ]; then
      narrate "PR #$PENDING_PR_NUMBER ($PENDING_PR_BRANCH) was merged -- cleaning up the local branch"
      # -D, not -d: a facilitator merging via Forgejo's squash option (not
      # guaranteed to happen promptly, or at all, during a live demo)
      # leaves this branch's commits unreachable from main, so the safe
      # "-d" fails with "not fully merged". The API already told us it's
      # merged, so force the local delete rather than leaving a stale
      # branch (and, since step_sync_main's exit status now controls
      # whether this step gets retried -- see the main loop below --
      # leaving that failure unhandled would also wedge this step
      # retrying forever instead of just cleaning up and moving on).
      run_cmd "git branch -D '$PENDING_PR_BRANCH'"
    else
      narrate "PR #$PENDING_PR_NUMBER ($PENDING_PR_BRANCH) not merged yet -- leaving it for the facilitator, moving on"
    fi
    PENDING_PR_BRANCH=""
    PENDING_PR_NUMBER=""
  fi
}

step_lab1_branch_and_edit() {
  cd "$REPO_DIR" || return 1
  local branch; branch="$(branch_name "add-${BOT_USER}")"
  narrate "Lab 1, steps 2-5 -- branch, edit the roster, review, commit"
  run_cmd "git checkout -B '$branch' main"

  local roster="roster/team.yaml"
  if [ ! -f "$roster" ]; then
    # A workshop other than git-fundamentals won't have this file --
    # fall back to something generic so the bot still has real content
    # to commit instead of failing outright.
    roster="NOTES-${BOT_USER}.md"
    narrate "roster/team.yaml not found (not the git-fundamentals content) -- using $roster instead"
  fi

  printf -- '- name: %s (demo bot, round %s)\n  role: QA\n' "$BOT_USER" "$ROUND" >> "$roster"
  orient
  run_cmd "git status"
  run_cmd "git diff"

  if [ $(( ROUND % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) committing before staging, on purpose, to show what that looks like"
    run_cmd "git commit -m 'Add $BOT_USER to team roster'"
    narrate "right -- nothing was staged. Fixing that."
  fi

  orient
  run_cmd "git add '$roster'"
  run_cmd "git commit -m 'Add $BOT_USER to team roster (round $ROUND)'"
  run_cmd "git log -1"
}

step_lab1_push_and_pr() {
  cd "$REPO_DIR" || return 1
  local branch; branch="$(branch_name "add-${BOT_USER}")"
  narrate "Lab 1, step 6 -- push (try the bare form first, like the lab shows)"
  run_cmd "git push"
  narrate "no upstream yet, as expected -- setting one"
  run_cmd "git push -u origin '$branch'"

  narrate "Lab 1, step 7 -- open a pull request"
  local pr_json pr_number
  pr_json="$(api_curl -X POST "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls" \
    -H 'Content-Type: application/json' \
    -d "{\"head\":\"$branch\",\"base\":\"main\",\"title\":\"[$BOT_USER] Add to roster (round $ROUND)\",\"body\":\"Demo bot activity -- safe to review and merge live, or close.\"}")"
  pr_number="$(printf '%s' "$pr_json" | grep -o '"number":[0-9]*' | head -1 | cut -d: -f2)"
  if [ -n "$pr_number" ]; then
    narrate "opened PR #$pr_number for $branch"
    PENDING_PR_BRANCH="$branch"
    PENDING_PR_NUMBER="$pr_number"
  else
    narrate "PR open failed or already exists for $branch -- will re-check next round"
  fi
}

step_lab2_review_and_undo() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 2 -- reviewing and undoing before a commit"
  orient
  run_cmd "echo '- name: Test Entry' >> roster/team.yaml"
  run_cmd "git status"
  run_cmd "git restore roster/team.yaml"
  run_cmd "git status"

  run_cmd "echo '- name: Another Test' >> roster/team.yaml"
  run_cmd "git add roster/team.yaml"
  run_cmd "git status"
  run_cmd "git restore --staged roster/team.yaml"
  run_cmd "git status"
  run_cmd "git restore roster/team.yaml"

  run_cmd "touch scratch.log"
  run_cmd "git status"
  run_cmd "echo '*.log' >> .gitignore"
  run_cmd "git status"
  run_cmd "rm -f scratch.log .gitignore"
  run_cmd "git status"
}

step_lab3_stash() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 3 -- stashing"
  orient
  run_cmd "echo '- name: Work In Progress' >> roster/team.yaml"
  run_cmd "git status"
  run_cmd "git stash"
  run_cmd "git status"
  run_cmd "git stash list"
  run_cmd "git checkout main"
  run_cmd "git status"
  local branch; branch="$(branch_name "add-${BOT_USER}")"
  run_cmd "git checkout '$branch'"
  run_cmd "git stash pop"
  run_cmd "git diff"
  run_cmd "git restore roster/team.yaml"
}

step_lab4_history() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 4 -- investigating history"
  run_cmd "git log --oneline -5"
  run_cmd "git log --oneline --graph --all -10"
  local last_hash; last_hash="$(git log -1 --format=%H 2>/dev/null)"
  [ -n "$last_hash" ] && run_cmd "git show --stat $last_hash"
  run_cmd "git blame roster/team.yaml | tail -5"

  local branch; branch="$(branch_name "lab4-explore")"
  orient
  run_cmd "git checkout -B '$branch'"
  run_cmd "echo '- name: Branch Explorer' >> roster/team.yaml"
  run_cmd "git add roster/team.yaml"
  run_cmd "git commit -m 'Lab 4: branch comparison example'"
  run_cmd "git diff main..$branch"

  if [ $(( (ROUND + 1) % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) trying to clean up without switching off the branch first"
    run_cmd "git branch -D '$branch'"
    narrate "right -- can't delete the branch you're currently on. Switching first."
  fi
  run_cmd "git checkout main"
  run_cmd "git branch -D '$branch'"
}

step_lab5_conflict() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 5, part A -- causing and resolving a merge conflict"
  orient
  local a b
  a="$(branch_name "conflict-a")"
  b="$(branch_name "conflict-b")"

  run_cmd "git checkout main"
  run_cmd "git checkout -B '$a'"
  run_cmd "sed -i 's/role: .*Engineer/role: Senior Engineer/' roster/team.yaml 2>/dev/null || echo '  role: Senior Engineer' >> roster/team.yaml"
  run_cmd "git add roster/team.yaml"
  run_cmd "git commit -m 'conflict-a: update role'"

  run_cmd "git checkout main"
  run_cmd "git checkout -B '$b'"
  run_cmd "sed -i 's/role: .*Engineer/role: Principal Engineer/' roster/team.yaml 2>/dev/null || echo '  role: Principal Engineer' >> roster/team.yaml"
  run_cmd "git add roster/team.yaml"
  run_cmd "git commit -m 'conflict-b: update role'"

  run_cmd "git merge '$a'"
  narrate "conflict, as expected -- resolving by keeping the incoming version"
  run_cmd "grep -v -E '^(<<<<<<<|=======|>>>>>>>)' roster/team.yaml > roster/team.yaml.resolved && mv roster/team.yaml.resolved roster/team.yaml"
  run_cmd "git add roster/team.yaml"
  run_cmd "git commit --no-edit"

  run_cmd "git checkout main"
  run_cmd "git branch -D '$a' '$b'"
}

step_lab5_undo() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 5, part B -- safely undoing a change"
  local branch; branch="$(branch_name "undo-demo")"
  run_cmd "git checkout -B '$branch'"
  run_cmd "echo '- name: Oops Entry' >> roster/team.yaml"
  run_cmd "git add roster/team.yaml"
  run_cmd "git commit -m 'Oops, wrong entry'"
  run_cmd "git reset --soft HEAD~1"
  run_cmd "git status"
  run_cmd "git reset --hard HEAD~1"
  run_cmd "git status"

  run_cmd "echo '- name: Reverted Later' >> roster/team.yaml"
  run_cmd "git add roster/team.yaml"
  run_cmd "git commit -m 'Example commit to revert'"
  run_cmd "git log --oneline -1"
  run_cmd "git revert HEAD --no-edit"
  run_cmd "git log --oneline -2"

  run_cmd "git checkout main"
  run_cmd "git branch -D '$branch'"
}

step_wrap_round() {
  cd "$REPO_DIR" || return 1
  run_cmd "git checkout main"
  narrate "round $ROUND done -- taking a short break before round $((ROUND + 1))"
  sleep "$(rand_between "$BOT_ROUND_BREAK_MIN" "$BOT_ROUND_BREAK_MAX")"
}

# How far into the curriculum each persona gets per round -- this, plus the
# delay ranges set above, is what makes the expert visibly "further along"
# than the novice over the course of a demo: the novice's round never even
# includes the Lab 3-5 steps, no matter how long it runs. Sized so that in
# roughly a 10-minute demo window (see engine/README.md) the expert cycles
# through the whole list a couple of times, the intermediate bot gets
# through Lab 4 once or twice, and the novice is still visibly working
# through Lab 1/Lab 2 material by the time you'd wrap up a live walkthrough.
case "$PERSONA" in
  expert)
    STEPS=(
      step_ensure_clone
      step_sync_main
      step_lab1_branch_and_edit
      step_lab1_push_and_pr
      step_lab2_review_and_undo
      step_lab3_stash
      step_lab4_history
      step_lab5_conflict
      step_lab5_undo
      step_wrap_round
    )
    ;;
  intermediate)
    STEPS=(
      step_ensure_clone
      step_sync_main
      step_lab1_branch_and_edit
      step_lab1_push_and_pr
      step_lab2_review_and_undo
      step_lab3_stash
      step_lab4_history
      step_wrap_round
    )
    ;;
  novice)
    STEPS=(
      step_ensure_clone
      step_sync_main
      step_lab1_branch_and_edit
      step_lab1_push_and_pr
      step_lab2_review_and_undo
      step_wrap_round
    )
    ;;
esac

narrate "=== GitOps Dojo demo bot: $BOT_USER ($PERSONA, round $ROUND) ==="

# Consecutive failures of whichever step is currently at index STEP --
# reset on any success, at any index. A step can fail transiently (e.g.
# git-server's bootstrap.sh hasn't finished creating this bot's Forgejo
# account yet when bot-runner.sh's first clone attempt races it): retrying
# that SAME step, instead of letting STEP advance past it regardless of
# its exit code (the old behavior), means the bot actually recovers rather
# than silently no-op'ing through every remaining step for the rest of the
# round (each guarded by its own `cd "$REPO_DIR" || return 1`) and only
# trying again next round. The backoff, capped at 60s, keeps a
# persistently-broken step (e.g. a genuinely wrong FORGEJO_ORG) from
# hammering git-server/Forgejo at full human-typing cadence forever.
step_fail_count=0

while true; do
  for (( i=0; i<${#STEPS[@]}; i++ )); do
    if [ "$i" -lt "$STEP" ]; then
      continue
    fi
    if "${STEPS[$i]}"; then
      step_fail_count=0
      STEP=$((i + 1))
      save_state
      continue
    fi
    step_fail_count=$((step_fail_count + 1))
    retry_delay=$(( step_fail_count * step_fail_count * BOT_MIN_DELAY ))
    [ "$retry_delay" -gt 60 ] && retry_delay=60
    narrate "${STEPS[$i]} failed (attempt $step_fail_count) -- retrying in ${retry_delay}s instead of skipping ahead"
    sleep "$retry_delay"
    break
  done
  if [ "$STEP" -ge "${#STEPS[@]}" ]; then
    ROUND=$((ROUND + 1))
    STEP=0
    save_state
    trim_log
    narrate "=== $BOT_USER starting round $ROUND ==="
  fi
done
