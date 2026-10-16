# Workshop bot steps for git-fundamentals (see engine/web-terminal/bot-runner.sh's BOT_STEPS_FILE).
# Keeps the engine's default steps, which already walk Labs 1-5, and adds two things the engine's
# shared steps don't cover:
#   * Lab 1 step 9's wrong-branch drill (step_gf_wrong_branch), right after the Lab 1 PR step. It is
#     the only step that earns `l1-rescue`, so without it a --test run leaves every bot one core
#     milestone short and `l1-rescue` never gets a class-clear bonus.
#   * the three challenges (c1 The Hotfix, c2 The Detective, capstone The Great Merge) right before
#     step_wrap_round, each one the way the lab page says to do it: `dojo-challenge start`, work in
#     ~/lab/challenge-repo, `dojo-check`.
# Each challenge step ends with `dojo-check ID`, so the result is in the bot's log (~/.dojo-bot.log)
# and in `dojo-check status` for that account.

GF_REPO="$BOT_USER/challenge-repo"
GF_DIR="$HOME/lab/challenge-repo"

gf_start() { # start challenge $1 from a clean copy and cd into it
  cd "$HOME/lab" && rm -rf "$GF_DIR"
  printf '%s@dojo:~$ dojo-challenge reset %s\n' "$BOT_USER" "$1"
  GF_OUT="$(dojo-challenge reset "$1" 2>&1)"; local rc=$?
  printf '%s\n' "$GF_OUT"
  [ "$rc" = 0 ] || return 1
  cd "$GF_DIR" || return 1
  git config user.name "$BOT_USER"; git config user.email "$BOT_USER@example.com"
}

gf_open_pr() { # $1 = branch, $2 = title; echoes the PR number
  api_curl -X POST "$API/repos/$GF_REPO/pulls" -H 'Content-Type: application/json' \
    -d "{\"head\":\"$1\",\"base\":\"main\",\"title\":\"$2\"}" | grep -o '"number":[0-9]*' | head -1 | cut -d: -f2
}

step_gf_wrong_branch() {
  # Lab 1 step 9: commit on `main` by mistake, carry the commit to a branch, put `main` back.
  # Entirely local -- nothing is pushed and `main` is only ever reset to what the server already
  # has, so this touches no shared state. Earns f-main ("Living Dangerously", worth nothing) on the
  # commit and l1-rescue on the reset; the branch is what tells l1-rescue from Lab 5's l5-reset, so
  # the reset has to happen while on `main`.
  cd "$REPO_DIR" || return 1
  local branch notes; branch="$(branch_name "notes")"; notes="notes-${BOT_USER}.md"
  narrate "Lab 1, step 9 -- the mistake everyone makes once: editing straight on main"
  run_cmd "git checkout main"
  # A restart re-enters the whole step, so drop anything a half-finished run left behind.
  git branch -D "$branch" >/dev/null 2>&1
  run_cmd "printf '# Notes from round %s\\n' '$ROUND' > '$notes'"
  run_cmd "git add '$notes'"
  run_cmd "git commit -m 'Add $BOT_USER notes (round $ROUND)'"
  run_cmd "git log --oneline -2"
  narrate "...that went on main. Label the commit first, then move main off it"
  run_cmd "git branch '$branch'"
  run_cmd "git log --oneline --graph --decorate -2"
  run_cmd "git fetch"
  run_cmd "git reset --hard origin/main"
  run_cmd "git status"
  narrate "main is back to the server's version -- and the commit is safe on $branch"
  run_cmd "git checkout '$branch'"
  run_cmd "git log --oneline -1"
  run_cmd "git checkout main"
  run_cmd "git branch -d '$branch'"
  narrate "-d refuses an unmerged branch, as the lab says -- forcing it, this was only a drill"
  run_cmd "git branch -D '$branch'"
}

step_gf_c1() {
  narrate "Challenge c1 -- The Hotfix"
  gf_start c1 || return 1
  run_cmd "git switch -c hotfix-$BOT_USER"
  # Only the process is checked: change the line under my own name.
  run_cmd "sed -i '/^- name: $BOT_USER\$/{n;s/role: .*/role: Software Engineer/}' roster/team.yaml"
  run_cmd "git diff --stat"
  run_cmd "git commit -am 'hotfix: fix my role'"
  run_cmd "git push -u origin hotfix-$BOT_USER"
  local n; n="$(gf_open_pr "hotfix-$BOT_USER" "hotfix: fix my role")"
  narrate "opened PR #${n:-?} in $GF_REPO"
  [ -n "$n" ] || return 1
  run_cmd "dojo-check c1"
}

step_gf_c2() {
  narrate "Challenge c2 -- The Detective"
  gf_start c2 || return 1
  local line hash who
  line="$(printf '%s\n' "$GF_OUT" | sed -n 's/^Goal: .*introduced `\([^`]*\)`.*/\1/p' | head -1)"
  [ -n "$line" ] || { narrate "could not read the target line from the goal"; return 1; }
  run_cmd "git log -S'$line' --format='%h %an' -- config/settings.yaml"
  hash="$(git log -S"$line" --format=%h -- config/settings.yaml | tail -1)"
  who="$(git log -S"$line" --format=%an -- config/settings.yaml | tail -1)"
  run_cmd "git switch -c case-$BOT_USER"
  run_cmd "echo '$hash $who' > answer.txt"
  run_cmd "git add answer.txt"
  run_cmd "git commit -m 'Case closed'"
  run_cmd "git push -u origin case-$BOT_USER"
  run_cmd "dojo-check c2"
}

step_gf_capstone() {
  narrate "Capstone -- The Great Merge"
  gf_start capstone || return 1
  run_cmd "git switch -c merge-$BOT_USER"
  run_cmd "git merge origin/feature-a"
  run_cmd "git merge origin/feature-b"   # conflicts in CHANGELOG.md: expected
  run_cmd "sed -i '/^<<<<<<< /d;/^=======\$/d;/^>>>>>>> /d' CHANGELOG.md"
  run_cmd "git add CHANGELOG.md"
  run_cmd "git commit --no-edit"
  run_cmd "git log --oneline"
  run_cmd "git revert --no-edit \$(git log --format=%h --grep='Make deploys faster' -1)"
  run_cmd "git push -u origin merge-$BOT_USER"
  local n; n="$(gf_open_pr "merge-$BOT_USER" "Merge both features")"
  narrate "opened PR #${n:-?} in $GF_REPO"
  [ -n "$n" ] || return 1
  api_curl -X POST "$API/repos/$GF_REPO/pulls/$n/merge" -H 'Content-Type: application/json' -d '{"Do":"merge"}'
  run_cmd "dojo-check capstone"
}

# Lab 4 runs in the practice repo `lab-history` builds (~/lab/history-repo), not the sample repo, so
# this replaces the engine's step_lab4_history (it is sourced before this file, so the redefinition wins).
# It follows lab4.md: browse, filter, show, blame/log -p, the pickaxe hunt for the leaked key, then the
# throwaway-branch diff. Without `lab-history` (an image built before it existed) it falls back to the
# engine's sample-repo walk.
eval "$(declare -f step_lab4_history | sed '1s/step_lab4_history/gf_engine_lab4_history/')"
step_lab4_history() {
  if ! command -v lab-history >/dev/null 2>&1; then gf_engine_lab4_history; return; fi
  narrate "Lab 4 -- investigating a longer history (lab-history practice repo)"
  run_cmd "lab-history"
  cd "$HOME/lab/history-repo" || return 1
  git config user.name "$BOT_USER"; git config user.email "$BOT_USER@example.com"
  run_cmd "git log --oneline --graph --all"
  run_cmd "git log --oneline --author=Bob"
  run_cmd "git log --oneline --since=2026-08-07"
  run_cmd "git log --stat --oneline -4"
  local db; db="$(git log --format=%h --grep='Add database settings' -1)"
  run_cmd "git show $db"
  run_cmd "git blame config/app.yaml"
  run_cmd "git log -p config/app.yaml | head -60"
  narrate "hunting for the leaked key"
  run_cmd "git log -S'sk_live_' --oneline"
  local added; added="$(git log -S'sk_live_' --format=%h | tail -1)"
  run_cmd "git show $added"

  local branch; branch="$(branch_name "lab4-explore")"
  run_cmd "git checkout -b '$branch'"
  run_cmd "sed -i 's/port: 8080/port: 9090/' config/app.yaml"
  run_cmd "git add config/app.yaml"
  run_cmd "git commit -m 'Lab 4: branch comparison example'"
  run_cmd "git diff main..$branch"
  run_cmd "git checkout main"
  run_cmd "git branch -D '$branch'"
  cd "$REPO_DIR" || return 1
}

# The wrong-branch drill follows the Lab 1 PR step (every persona reaches Lab 1, so every bot runs
# it); the challenges go after the labs, just before the round ends, and only where dojo-challenge
# exists (achievements off = no challenges).
gf_challenges=0
command -v dojo-challenge >/dev/null 2>&1 && gf_challenges=1
gf_steps=()
for s in "${STEPS[@]}"; do
  [ "$s" = step_wrap_round ] && [ "$gf_challenges" = 1 ] && gf_steps+=(step_gf_c1 step_gf_c2 step_gf_capstone)
  gf_steps+=("$s")
  [ "$s" = step_lab1_push_and_pr ] && gf_steps+=(step_gf_wrong_branch)
done
STEPS=("${gf_steps[@]}")
