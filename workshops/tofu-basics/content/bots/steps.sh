# tofu-basics demo bot steps (see engine/web-terminal/bot-runner.sh's BOT_STEPS_FILE) -- replaces the
# git-fundamentals default with Labs 0-10: the offline sandbox (Track A) always, and, only when this
# bot's own Dojo Cloud credentials come back from the broker (same dojo-env a real student's shell
# reads at login -- see compose/terminal/dojo-broker.py's roster, which includes testuserN), the Dojo
# Cloud lifecycle (Track B: deploy hello, a policy mistake, in-place vs replace, then destroy + commit
# + PR). Every round destroys whatever Dojo Cloud resources it created before touching git, so a round
# that gets killed partway through never leaves a cloud container burning host memory.

# -- Dojo Cloud credentials --------------------------------------------------
# /usr/local/bin/dojo-env asks the root-owned broker (over a unix socket, identified by our own uid --
# see dojo-broker.py) for this account's ARM_*/TF_VAR_owner values and prints `export NAME=value`
# lines, exactly what /etc/zsh/zshenv evals for an interactive student shell. bot-runner.sh runs under
# bash, not zsh, so that zshenv line never fires for us -- do the same eval ourselves. Silent no-op (an
# empty ARM_CLIENT_ID) if the broker/cloud-api isn't up yet or this bot isn't in its roster: every
# Track B step below checks TB_HAS_CLOUD and skips with a narrated reason instead of failing.
ensure_cloud_creds() {
  if [ -z "${ARM_CLIENT_ID:-}" ] && [ -x /usr/local/bin/dojo-env ]; then
    eval "$(/usr/local/bin/dojo-env 2>/dev/null)"
  fi
  if [ -n "${ARM_CLIENT_ID:-}" ]; then
    TB_HAS_CLOUD=1
  else
    TB_HAS_CLOUD=0
  fi
}

step_tb_lab0_tour() {
  cd "$REPO_DIR" || return 1
  narrate "Lab 0 -- the tour: is terraform really OpenTofu?"
  run_cmd "command -v terraform tofu; readlink -f \"\$(command -v terraform)\""
  run_cmd "terraform version"
  orient
  run_cmd "ls -a sandbox"
}

# Labs 1-3: the offline sandbox. Safe to re-run from scratch (init/apply are idempotent; the tfvars
# edit is always reverted at the end, whether or not Lab 3 ran). A novice stops after Lab 2, same as
# the git-fundamentals default never reaching its later labs -- Track A only ever touches local files,
# so leaving it mid-way costs nothing on the host.
step_tb_track_a() {
  cd "$REPO_DIR/sandbox" || return 1
  narrate "Lab 1 -- init, validate, plan, apply (offline sandbox)"
  if [ $(( ROUND % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) planning before init, on purpose, to show what that looks like"
    run_cmd "terraform plan -no-color -input=false"
    narrate "right -- no providers installed yet. init first."
  fi
  run_cmd "terraform init -no-color -input=false"
  run_cmd "terraform validate -no-color"
  run_cmd "terraform plan -no-color -input=false"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
  orient
  run_cmd "cat out/hello.txt"

  narrate "Lab 2 -- change an input, read the plan"
  local edit_cmd
  edit_cmd="sed -i 's/^learner .*/learner  = \"$BOT_USER\"/' terraform.tfvars"
  run_cmd "$edit_cmd"
  run_cmd "terraform plan -no-color -input=false"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
  run_cmd "terraform output"
  run_cmd "terraform state list"
  run_cmd "terraform plan -no-color -input=false -replace=random_pet.nickname"
  run_cmd "terraform plan -no-color -input=false -var pet_words=9"
  narrate "right -- pet_words must be between 2 and 4. That's the starter's own validation rule."

  if [ "$PERSONA" != "novice" ]; then
    narrate "Lab 3 -- tear it down"
    run_cmd "terraform plan -destroy -no-color -input=false"
    run_cmd "terraform destroy -auto-approve -no-color -input=false"
  fi
  run_cmd "cd '$REPO_DIR' && git checkout -q -- sandbox/terraform.tfvars"
}

# Labs 4-5: real Dojo Cloud resources (a resource group + one container group), so every apply here
# MUST be matched by step_tb_cleanup's destroy later in the same round.
step_tb_deploy() {
  cd "$REPO_DIR" || return 1
  ensure_cloud_creds
  if [ "$TB_HAS_CLOUD" != 1 ]; then
    narrate "Lab 4 -- no Dojo Cloud credentials for $BOT_USER yet (dojo-env/broker not ready) -- skipping Track B this round"
    return 0
  fi
  narrate "Lab 4 -- meet Dojo Cloud: credentials are already in the environment"
  run_cmd "env | grep -E '^(ARM_|TF_VAR_)' | grep -v SECRET | sort"
  run_cmd "terraform init -no-color -input=false"
  run_cmd "terraform validate -no-color"
  narrate "Lab 5 -- deploy hello"
  run_cmd "terraform plan -no-color -input=false"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
  orient
  run_cmd "curl -s -m 10 -w '\nHTTP %{http_code}\n' http://cloud-api:8080/cloud/site/hello-dev-${BOT_USER}/"
  run_cmd "terraform output"
}

# Lab 6 (one policy mistake, gated and corrected) + Lab 8 (a tag edit that's in place, a message edit
# that forces a replace). Only runs once step_tb_deploy has actually deployed something this round.
step_tb_policy_and_edit() {
  cd "$REPO_DIR" || return 1
  ensure_cloud_creds
  if [ "$TB_HAS_CLOUD" != 1 ]; then
    narrate "Lab 6/8 -- still no Dojo Cloud credentials -- skipping"
    return 0
  fi
  local branch; branch="$(branch_name "tb-changes")"
  run_cmd "git checkout -B '$branch' main"

  if [ $(( (ROUND + 1) % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "Lab 6 -- mistake: drop the required 'owner' tag on purpose"
    run_cmd "sed -i '/^    owner /d' locals.tf"
    run_cmd "terraform plan -no-color -input=false"
    run_cmd "terraform apply -auto-approve -no-color -input=false"
    narrate "right -- the cloud refuses: missing required tag 'owner'. Undoing."
    run_cmd "git checkout -q -- locals.tf"
    run_cmd "terraform plan -no-color -input=false"
  fi

  narrate "Lab 8 -- a tag edit is in place"
  run_cmd "sed -i '/managed_by = \"opentofu\"/a\    cost_center = \"training\"' locals.tf"
  run_cmd "terraform fmt"
  run_cmd "terraform plan -no-color -input=false"
  run_cmd "terraform apply -auto-approve -no-color -input=false"

  narrate "Lab 8 -- the message forces a replace"
  run_cmd "sed -i 's/^message .*/message     = \"Hello, Canada!\"/' terraform.tfvars"
  run_cmd "terraform plan -no-color -input=false"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
  orient
  run_cmd "terraform output"
}

# Lab 10: destroy first (host memory matters more than demo continuity), then commit + push + PR
# whatever Track B edits are sitting in the working tree, whether or not step_tb_policy_and_edit ran
# this round. step_sync_main (generic, reused) checks PENDING_PR_NUMBER next round and cleans up the
# local branch once it's merged. Always ends on a command that succeeds so this step is never retried
# just because there was nothing to clean up.
step_tb_cleanup() {
  cd "$REPO_DIR" || return 1
  ensure_cloud_creds
  if [ "$TB_HAS_CLOUD" = 1 ] && [ -d .terraform ]; then
    narrate "Lab 10 -- clean up: destroy the Dojo Cloud resources this round created"
    run_cmd "terraform plan -destroy -no-color -input=false"
    run_cmd "terraform destroy -auto-approve -no-color -input=false"
  else
    narrate "Lab 10 -- nothing deployed this round (no credentials or never initialised) -- nothing to destroy"
  fi

  local changes; changes="$(git status --porcelain -- locals.tf main.tf terraform.tfvars 2>/dev/null)"
  if [ -n "$changes" ]; then
    local branch; branch="$(branch_name "tb-changes")"
    narrate "Lab 10 -- commit the Track B edits and open a pull request"
    run_cmd "git status --short"
    run_cmd "git add locals.tf main.tf terraform.tfvars"
    run_cmd "git commit -m 'Track B: cost_center tag, Hello Canada message (round $ROUND)'"
    run_cmd "git push -u origin '$branch'"

    local pr_json pr_number head="$branch"
    [ "$FORGEJO_FORK_WORKFLOW" = 1 ] && head="$BOT_USER:$branch"
    pr_json="$(api_curl -X POST "$API/repos/$FORGEJO_ORG/$FORGEJO_REPO/pulls" \
      -H 'Content-Type: application/json' \
      -d "{\"head\":\"$head\",\"base\":\"main\",\"title\":\"[$BOT_USER] Track B changes (round $ROUND)\",\"body\":\"Demo bot Dojo Cloud activity -- resources were already destroyed before this PR was opened. Safe to review and merge live, or close.\"}")"
    pr_number="$(printf '%s' "$pr_json" | grep -o '"number":[0-9]*' | head -1 | cut -d: -f2)"
    if [ -n "$pr_number" ]; then
      narrate "opened PR #$pr_number for $branch"
      PENDING_PR_BRANCH="$branch"
      PENDING_PR_NUMBER="$pr_number"
    else
      narrate "PR open failed or already exists for $branch -- will re-check next round"
    fi
  else
    narrate "Lab 10 -- no tracked Track B edits this round to commit"
  fi

  run_cmd "git checkout main"
}

case "$PERSONA" in
  expert)
    STEPS=(
      step_ensure_clone
      step_sync_main
      step_tb_lab0_tour
      step_tb_track_a
      step_tb_deploy
      step_tb_policy_and_edit
      step_tb_cleanup
      step_wrap_round
    )
    ;;
  intermediate)
    STEPS=(
      step_ensure_clone
      step_sync_main
      step_tb_lab0_tour
      step_tb_track_a
      step_tb_deploy
      step_tb_cleanup
      step_wrap_round
    )
    ;;
  novice)
    STEPS=(
      step_ensure_clone
      step_sync_main
      step_tb_lab0_tour
      step_tb_track_a
      step_wrap_round
    )
    ;;
esac
