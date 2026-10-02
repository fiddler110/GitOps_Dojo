# tofu-basics demo bot steps (see engine/web-terminal/bot-runner.sh's BOT_STEPS_FILE) -- replaces the
# git-fundamentals default with Labs 0-10: the offline sandbox (Track A) always, and, only when this
# bot's own Dojo Cloud credentials come back from the broker (same dojo-env a real student's shell
# reads at login -- see modules/dojo-cloud/terminal/dojo-broker.py's roster, which includes testuserN), the Dojo
# Cloud lifecycle (Track B: deploy hello, the three Lab 6 policy refusals, in-place vs replace, Lab 9's for_each and quota, then destroy + commit
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
  if [ "$ROUND" = 1 ] && [ "$PERSONA" = novice ]; then
    narrate "(demo) destroy before anything was ever applied"
    run_cmd "terraform destroy -auto-approve -no-color -input=false"
  fi
  run_cmd "terraform init -no-color -input=false"
  run_cmd "terraform validate -no-color"
  if [ $(( ROUND % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) a typo in a variable name"
    run_cmd "sed -i 's/var\.learner}/var.lerner}/' main.tf"
    run_cmd "terraform validate -no-color"
    narrate "right -- 'Reference to undeclared input variable'. Undoing."
    run_cmd "git checkout -q -- main.tf"
  fi
  run_cmd "terraform plan -no-color -input=false"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
  orient
  run_cmd "cat out/hello.txt"
  if [ $(( ROUND % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) staging the state file, which .gitignore exists to stop"
    run_cmd "git add -f terraform.tfstate"
    narrate "no -- state can hold secrets. Unstaging it."
    run_cmd "git reset -q terraform.tfstate"
  fi

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

# Lab 6: the cloud's three policies (tag, region, size), each refused and then undone. Quick: a refused
# request creates nothing. Only runs once step_tb_deploy has deployed this round.
step_tb_policy() {
  cd "$REPO_DIR" || return 1
  ensure_cloud_creds
  if [ "$TB_HAS_CLOUD" != 1 ]; then
    narrate "Lab 6 -- still no Dojo Cloud credentials -- skipping"
    return 0
  fi
  narrate "Lab 6 -- policy: drop the required 'owner' tag"
  run_cmd "sed -i '/^    owner /d' locals.tf"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
  narrate "right -- the cloud refuses: missing required tag 'owner'. Undoing."
  run_cmd "git checkout -q -- locals.tf"

  narrate "Lab 6 -- policy: a region the cloud doesn't allow, in a scratch copy"
  run_cmd "rm -rf ~/scratch && mkdir ~/scratch && cp *.tf terraform.tfvars .terraform.lock.hcl ~/scratch/"
  run_cmd "cd ~/scratch && terraform init -no-color -input=false >/dev/null"
  run_cmd "sed -i 's/^location .*/location    = \"eastus\"/' terraform.tfvars"
  run_cmd "sed -i '26,29s/^/# /' variables.tf"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
  narrate "right -- refused by the cloud's region policy. Back to the real repo."
  run_cmd "cd '$REPO_DIR' && rm -rf ~/scratch"

  narrate "Lab 6 -- policy: a size over the limit"
  run_cmd "sed -i 's/cpu    = 0.25/cpu    = 2/' main.tf"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
  narrate "right -- too big for the size policy. Undoing (and re-applying: a replace may have removed hello first)."
  run_cmd "git checkout -q -- main.tf"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
}

# Lab 8: a tag edit is in place, the message forces a replace, a new image, then -replace by hand.
step_tb_edit() {
  cd "$REPO_DIR" || return 1
  ensure_cloud_creds
  [ "$TB_HAS_CLOUD" = 1 ] || return 0
  local branch; branch="$(branch_name "tb-changes")"
  run_cmd "git checkout -B '$branch' main"

  narrate "Lab 8 -- a tag edit is in place"
  run_cmd "sed -i '/managed_by = \"opentofu\"/a\    cost_center = \"training\"' locals.tf"
  run_cmd "terraform fmt"
  run_cmd "terraform plan -no-color -input=false"
  run_cmd "terraform apply -auto-approve -no-color -input=false"

  narrate "Lab 8 -- the message forces a replace"
  run_cmd "sed -i 's/^message .*/message     = \"Hello, Canada!\"/' terraform.tfvars"
  run_cmd "terraform plan -no-color -input=false"
  if [ "$ROUND" = 2 ] || [ "${BOT_FAST:-0}" = 1 ]; then   # --fast has only round 1
    # The replace takes ~25 s (destroy, then create), so the plan is sure to find the lock held.
    narrate "(demo) a second terminal plans while the first apply still holds the state lock"
    run_cmd "terraform apply -auto-approve -no-color -input=false & sleep 3; terraform plan -no-color -input=false -lock-timeout=0s; wait"
  else
    run_cmd "terraform apply -auto-approve -no-color -input=false"
  fi
  run_cmd "sed -i 's/^image_tag .*/image_tag   = \"2.0\"/' terraform.tfvars"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
  narrate "Lab 8 -- replace it on purpose"
  run_cmd "terraform apply -auto-approve -no-color -input=false -replace=azurerm_container_group.hello"
  orient
  run_cmd "terraform output"
}

# Lab 9: for_each asks for two more sites with one left in the quota, so one is refused; then the code
# is cut back to the site that exists. Skipped if main already has the block (a merged bot PR).
step_tb_scale() {
  cd "$REPO_DIR" || return 1
  ensure_cloud_creds
  [ "$TB_HAS_CLOUD" = 1 ] || return 0
  if grep -q '"extra"' main.tf; then
    narrate "Lab 9 -- main already has the for_each block"
  else
    narrate "Lab 9 -- two more sites from one for_each block"
    cat >> main.tf <<'HCL'

# Lab 9: more sites, built from ONE block. for_each makes one copy per name.
resource "azurerm_container_group" "extra" {
  for_each = toset(["blue", "green"])

  name                = "${local.ci_name}-${each.key}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "${local.dns_label}-${each.key}"

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = "dojo/hello:${var.image_tag}"
    cpu    = 0.25
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }

    environment_variables = {
      MESSAGE = "${var.message} (${each.key})"
      OWNER   = var.owner
    }
  }

  tags = local.tags
}
HCL
  fi
  run_cmd "terraform validate -no-color"
  run_cmd "terraform plan -no-color -input=false | grep -E '^  # |^Plan:'"
  run_cmd "terraform apply -auto-approve -no-color -input=false"
  narrate "right -- QuotaExceeded: two groups is the cap. Which one won?"
  run_cmd "terraform state list"
  local won
  won="$(terraform state list 2>/dev/null | sed -n 's/.*extra\["\([a-z]*\)"\].*/\1/p' | head -1)"
  [ -n "$won" ] || won=blue
  run_cmd "sed -i 's/for_each = toset(\[\"blue\", \"green\"\])/for_each = toset([\"$won\"])/' main.tf"
  run_cmd "grep -n 'for_each =' main.tf"
  run_cmd "terraform plan -no-color -input=false"
}

# Lab 10: destroy first (host memory matters more than demo continuity), then commit + push + PR
# whatever Track B edits are sitting in the working tree, whether or not step_tb_edit/step_tb_scale ran
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
      step_tb_policy
      step_tb_edit
      step_tb_scale
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
      step_tb_policy
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
