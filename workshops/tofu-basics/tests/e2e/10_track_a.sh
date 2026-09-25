#!/usr/bin/env bash
# shellcheck shell=bash
# Area track_a: Labs 0-3, the offline sandbox (content/lab/lab0.md .. lab3.md), run as the student in a fresh clone.
# Sourced by tests/e2e.sh (which provides STUDENT, WORK, REPO and prepare_repo); running this file directly
# hands over to e2e.sh with --only track_a.
#
# Deviation from the labs, on purpose: `apply` and `destroy` run with -auto-approve (except Lab 1's apply, which
# answers the approval prompt by piping "yes") and every tofu command gets -no-color, because tofu colours its output
# even when piped, which would hide the text from the checks.

if [ "${BASH_SOURCE[0]}" = "$0" ]; then exec "$(dirname "$0")/../e2e.sh" --only track_a "$@"; fi

area_track_a() {
  prepare_repo || abort_area "cannot prepare the starter repo"
  local sbx="$REPO/sandbox" nick

  section "Lab 0: the repo and the tour"
  as_student "$STUDENT" 'terraform version' 60 version
  expect_rc "terraform version runs" 0
  expect_has "terraform prints OpenTofu (Lab 0)" 'OpenTofu v'
  as_student "$STUDENT" 'command -v terraform tofu; readlink -f "$(command -v terraform)"' 60 which
  expect_has "terraform is a link that points at tofu" '/usr/local/bin/tofu'
  as_student "$STUDENT" "ls -a '$sbx'" 60 ls-sandbox
  expect_has "sandbox/ has the files Lab 0 lists" versions.tf variables.tf main.tf outputs.tf terraform.tfvars .terraform.lock.hcl
  as_student "$STUDENT" "cat '$sbx/versions.tf' '$sbx/main.tf'" 60 cat-config
  expect_has "main.tf uses random_pet.nickname.id (the dependency Lab 0 points at)" 'random_pet.nickname.id'

  section "Lab 1: init, validate, plan, apply"
  as_student "$STUDENT" "cd '$sbx' && sha256sum .terraform.lock.hcl > '$WORK/sandbox-lock.sha' && terraform init -no-color -input=false" 180 init
  expect_rc "Lab 1 init succeeds offline" 0
  expect_has "init output (Lab 1)" \
    'Initializing provider plugins...' \
    'Reusing previous version of hashicorp/local from the dependency lock file' \
    'Reusing previous version of hashicorp/random from the dependency lock file' \
    'Installing hashicorp/random v3.9.1...' \
    'Installing hashicorp/local v2.9.1...' \
    'OpenTofu has been successfully initialized!'
  expect_secs_le "init is quick (offline mirror; Lab 4 says about 2 s)" 60
  as_student "$STUDENT" "cd '$sbx' && sha256sum -c '$WORK/sandbox-lock.sha'" 30 lock-check
  expect_has "init did not rewrite .terraform.lock.hcl" ': OK'
  as_student "$STUDENT" "cd '$REPO' && git status --short -- sandbox" 30 lock-git
  expect_lacks "git status does not list the lock file or .terraform/" '.terraform.lock.hcl' '.terraform/'

  as_student "$STUDENT" "cd '$sbx' && terraform validate -no-color" 60 validate
  expect_has "validate (Lab 1)" 'Success! The configuration is valid.'
  as_student "$STUDENT" "cd '$sbx' && terraform plan -no-color -input=false" 120 plan
  expect_rc "plan succeeds" 0
  expect_has "plan shows three creations (Lab 1)" \
    '# local_file.greeting will be created' '# random_pet.nickname will be created' \
    '# terraform_data.note will be created' 'Plan: 3 to add, 0 to change, 0 to destroy.'
  as_student "$STUDENT" "cd '$sbx' && printf 'yes\\n' | terraform apply -no-color" 180 apply
  expect_rc "apply (approval prompt answered with yes)" 0
  expect_has "apply output (Lab 1)" \
    'Do you want to perform these actions?' \
    'Apply complete! Resources: 3 added, 0 changed, 0 destroyed.' \
    'greeting_file = "./out/hello.txt"' 'nickname = "'
  as_student "$STUDENT" "cd '$sbx' && cat out/hello.txt" 30 cat-hello
  expect_has "out/hello.txt was written" 'Hello from OpenTofu!' 'From: student ('
  as_student "$STUDENT" "cd '$sbx' && test -f terraform.tfstate && echo state-present" 30 state-file
  expect_has "terraform.tfstate exists after apply" 'state-present'
  as_student "$STUDENT" "cd '$sbx' && terraform output -raw nickname" 60 nickname
  nick=$(head -n1 "$OUT")
  expect_ge "the pet name is 2 words (Lab 1)" "$(printf '%s' "$nick" | tr -cd '-' | wc -c)" 1

  section "Lab 2: change a value and read the plan"
  as_student "$STUDENT" "cd '$sbx' && terraform plan -no-color -input=false" 120 plan-clean
  expect_has "second plan is clean (idempotency)" 'No changes. Your infrastructure matches the configuration.'
  as_student "$STUDENT" "cd '$sbx' && sed -i 's/^learner .*/learner  = \"ada\"/' terraform.tfvars && cat terraform.tfvars" 30 edit-learner
  expect_has "learner edited" 'learner  = "ada"'
  as_student "$STUDENT" "cd '$sbx' && terraform plan -no-color -input=false" 120 plan-learner
  expect_has "one edit, two outcomes (Lab 2)" \
    '# local_file.greeting must be replaced' '# forces replacement' \
    '# terraform_data.note will be updated in-place' \
    "From: ada ($nick)" 'Plan: 1 to add, 1 to change, 1 to destroy.'
  expect_lacks "random_pet.nickname is not in the plan (its name is kept in state)" '# random_pet.nickname will'
  as_student "$STUDENT" "cd '$sbx' && terraform apply -auto-approve -no-color -input=false" 180 apply-learner
  expect_has "apply of the change" 'Apply complete! Resources: 1 added, 1 changed, 1 destroyed.'
  as_student "$STUDENT" "cd '$sbx' && cat out/hello.txt && terraform output nickname && terraform output" 60 outputs
  expect_has "hello.txt has the new text and the pet name did not change" 'From: ada' "nickname = \"$nick\""
  as_student "$STUDENT" "cd '$sbx' && terraform state list" 60 state-list
  expect_eq "state list has three resources" 3 "$(out_lines)"
  expect_has "state list addresses" 'local_file.greeting' 'random_pet.nickname' 'terraform_data.note'
  as_student "$STUDENT" "cd '$sbx' && terraform show -no-color" 60 show
  expect_has "terraform show prints the state" 'random_pet.nickname'
  as_student "$STUDENT" "cd '$sbx' && terraform plan -no-color -input=false -replace=random_pet.nickname" 120 plan-replace
  expect_has "-replace chains through the dependency (Lab 2 step 5)" \
    'random_pet.nickname will be replaced, as requested' '# local_file.greeting must be replaced'
  as_student "$STUDENT" "cd '$sbx' && terraform plan -no-color -input=false -var pet_words=9" 60 plan-validation
  expect_rc "validation rejects pet_words=9 (Lab 2 step 6)" nonzero
  expect_has "validation message" 'Invalid value for variable' 'pet_words must be between 2 and 4.'

  section "Lab 3: tear it down"
  as_student "$STUDENT" "cd '$sbx' && terraform plan -destroy -no-color -input=false" 120 plan-destroy
  expect_has "plan -destroy (Lab 3)" 'Plan: 0 to add, 0 to change, 3 to destroy.'
  as_student "$STUDENT" "cd '$sbx' && terraform destroy -auto-approve -no-color -input=false" 180 destroy
  expect_rc "destroy succeeds" 0
  expect_has "destroy output (Lab 3)" 'Destroy complete! Resources: 3 destroyed.'
  as_student "$STUDENT" "cd '$sbx' && test ! -e out/hello.txt && echo hello-gone; test -d .terraform && echo plugins-kept; test -f terraform.tfstate.backup && echo backup-kept" 30 leftovers
  expect_has "out/hello.txt is gone, .terraform/ and the state backup stay" 'hello-gone' 'plugins-kept' 'backup-kept'
  as_student "$STUDENT" "cd '$sbx' && terraform state list" 60 state-empty
  expect_rc "state list works after destroy" 0
  expect_eq "state list prints nothing" 0 "$(out_lines)"
  as_student "$STUDENT" "cd '$sbx' && cat terraform.tfstate" 30 cat-state
  expect_has "state file is left behind and records no resources" '"resources": []'
  as_student "$STUDENT" "cd '$sbx' && terraform plan -no-color -input=false" 120 plan-after
  expect_has "plan after destroy wants to build it all again" 'Plan: 3 to add'
  as_student "$STUDENT" "cd '$REPO' && git status --short" 30 git-status
  expect_has "git status shows the tfvars edit" 'sandbox/terraform.tfvars'
  expect_lacks "git status does not show state or .terraform/ (they are in .gitignore)" 'tfstate' '.terraform/'
  as_student "$STUDENT" "cd '$REPO' && git checkout -q -- sandbox/terraform.tfvars && git status --short | wc -l" 30 git-reset
  expect_eq "sandbox edit reverted; the repo is clean for Track B" 0 "$(head -n1 "$OUT")"
}
