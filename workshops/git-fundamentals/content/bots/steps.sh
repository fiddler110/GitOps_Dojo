# Workshop bot steps for git-fundamentals (see engine/web-terminal/bot-runner.sh's BOT_STEPS_FILE).
# Keeps the engine's default steps, which already walk Labs 1-5, and adds the three challenges (c1 The
# Hotfix, c2 The Detective, capstone The Great Merge) right before step_wrap_round, each one the way the
# lab page says to do it: `dojo-challenge start`, work in ~/lab/challenge-repo, `dojo-check`.
# Each step ends with `dojo-check ID`, so the result is in the bot's log (~/.dojo-bot.log) and in
# `dojo-check status` for that account.

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

# Challenges go after the labs, just before the round ends.
if command -v dojo-challenge >/dev/null 2>&1; then
  gf_steps=()
  for s in "${STEPS[@]}"; do
    [ "$s" = step_wrap_round ] && gf_steps+=(step_gf_c1 step_gf_c2 step_gf_capstone)
    gf_steps+=("$s")
  done
  STEPS=("${gf_steps[@]}")
fi
