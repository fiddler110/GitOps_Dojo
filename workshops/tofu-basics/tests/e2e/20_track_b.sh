#!/usr/bin/env bash
# shellcheck shell=bash
# Area track_b: Labs 4-10, the Dojo Cloud lifecycle (PLAN T9.6), as the student in a fresh clone of the starter repo:
#   init (lock file untouched), apply, the site through the class URL path, the labs' own policy mistakes (Lab 6),
#   drift through the portal API (Lab 7), tag edit = in-place `~`, message/image edit = `-/+` replace, -replace,
#   create_before_destroy failing harmlessly (Lab 8), the quota (Lab 9), destroy and an empty portal (Lab 10).
# The labs' own edit commands (the sed lines, Lab 9's heredoc) are read out of content/lab/*.md and run as written.
# Sourced by tests/e2e.sh; running this file directly hands over to e2e.sh with --only track_b.

if [ "${BASH_SOURCE[0]}" = "$0" ]; then exec "$(dirname "$0")/../e2e.sh" --only track_b "$@"; fi

area_track_b() {
  prepare_repo || abort_area "cannot prepare the starter repo"
  local INIT='terraform init -no-color -input=false' PLAN='terraform plan -no-color -input=false'
  local APPLY='terraform apply -auto-approve -no-color -input=false' DESTROY='terraform destroy -auto-approve -no-color -input=false'
  local rg=rg-hello-dev-cac cg=ci-hello-dev label="hello-dev-$STUDENT" sub cmd body survivor other
  local cg_path
  tf() { as_student "$STUDENT" "cd '$REPO' && $1" "${2:-300}" "${3:-tf}"; }   # tf "command" [timeout] [label]
  sub=$(portal_sub "$STUDENT")
  cg_path="/cloud/api/containers/$sub/$rg/$cg"

  section "Lab 4: meet Dojo Cloud"
  portal_call GET /cloud/api/me "$STUDENT"
  expect_pj_eq "portal /me: the quota limit is 2 container groups (Lab 4)" body.quota.containerGroups.limit 2
  portal_counts "$STUDENT"
  expect_eq "portal Home shows 0 resource groups, 0 container instances, quota 0 / 2" "0/0/0" "$N_RG/$N_CG/$QUOTA_USED"
  as_student "$STUDENT" "env | grep -E '^(ARM_|TF_VAR_)' | grep -v SECRET | sort" 30 env
  expect_has "credentials in the environment (Lab 4 step 3)" \
    'ARM_CLIENT_ID=' 'ARM_METADATA_HOSTNAME=management.dojo.cloud' 'ARM_RESOURCE_PROVIDER_REGISTRATIONS=none' \
    "ARM_SUBSCRIPTION_ID=$sub" 'ARM_TENANT_ID=' 'ARM_USE_CLI=false' "TF_VAR_owner=$STUDENT" 'TF_VAR_portal_base_url='
  as_student "$STUDENT" 'test -n "$ARM_CLIENT_SECRET" && echo secret-is-set' 30 secret-set
  expect_has "ARM_CLIENT_SECRET is set (its value is never printed)" 'secret-is-set'
  tf "ls -a" 30 ls-root
  expect_has "Track B files are at the top of the repo" .terraform.lock.hcl locals.tf main.tf outputs.tf providers.tf terraform.tfvars variables.tf versions.tf sandbox
  tf "sha256sum .terraform.lock.hcl > '$WORK/root-lock.sha' && $INIT" 180 init
  expect_rc "Lab 4 init succeeds offline" 0
  expect_has "init output (Lab 4 step 5)" \
    'Reusing previous version of hashicorp/azurerm from the dependency lock file' \
    'Installing hashicorp/azurerm v5.6.0...' 'OpenTofu has been successfully initialized!'
  expect_secs_le "init takes about 2 s in the lab; limit 30 s" 30
  tf "sha256sum -c '$WORK/root-lock.sha'" 30 lock-check
  expect_has "the lock file is untouched by init" ': OK'
  tf "git status --short" 30 lock-git
  expect_eq "git status stays clean after init (lab: the lock file is not touched)" 0 "$(out_lines)"
  tf "du -sk .terraform | cut -f1" 30 du
  expect_le ".terraform is tiny (the provider is a symlink; lab says ~28 KB)" "$(head -n1 "$OUT")" 1024
  tf "terraform validate -no-color" 60 validate
  expect_has "validate (Lab 4)" 'Success! The configuration is valid.'

  section "Lab 5: deploy hello"
  local events_before events_after
  events_before=$(activity_total "$STUDENT")
  tf "$PLAN" 180 plan
  expect_rc "plan with no state succeeds" 0
  expect_has "plan (Lab 5 step 2)" \
    '# azurerm_container_group.hello will be created' '# azurerm_resource_group.main will be created' \
    "dns_name_label = \"$label\"" 'image = "dojo/hello:1.0"' 'location = "canadacentral"' \
    "name = \"$cg\"" "name = \"$rg\"" 'Plan: 2 to add, 0 to change, 0 to destroy.' 'Changes to Outputs:'
  events_after=$(activity_total "$STUDENT")
  expect_eq "plan in a folder with no state never contacts the cloud (activity log unchanged)" "$events_before" "$events_after"

  tf "$APPLY" 420 apply
  expect_rc "apply succeeds" 0
  expect_has "apply output (Lab 5 step 3)" \
    'azurerm_resource_group.main: Creation complete after' 'azurerm_container_group.hello: Creation complete after' \
    'Apply complete! Resources: 2 added, 0 changed, 0 destroyed.' \
    "fqdn = \"$label.canadacentral.dojo-cloud.test\"" \
    "resource_id = \"/subscriptions/$sub/resourceGroups/$rg/providers/Microsoft.ContainerInstance/containerGroups/$cg\""
  expect_secs_le "apply takes about 35 s in the labs; limit 120 s" 120
  say "  info: Lab 5 apply took ${SECS}s"

  portal_call GET '/cloud/api/overview?scope=mine' "$STUDENT"
  expect_pj_eq "portal: one resource group" body.resourceGroups.0.name "$rg"
  expect_pj_eq "portal: one container instance, named as in the lab" body.containerGroups.0.name "$cg"
  expect_pj_eq "portal: its image" body.containerGroups.0.image 'dojo/hello:1.0'
  expect_pj_eq "portal: its region" body.containerGroups.0.location canadacentral
  expect_pj_eq "portal: its site label" body.containerGroups.0.dnsLabel "$label"
  expect_wait "portal: the container instance is Running" 30 _cg_running
  portal_counts "$STUDENT"
  expect_eq "portal: Quota 1 / 2, 1 resource group, 1 container" "1/1/1" "$N_RG/$N_CG/$QUOTA_USED"
  expect_ge "activity log: the resource group create is recorded" "$(activity_count "$STUDENT" 'Create/Update resource group' Succeeded)" 1
  expect_ge "activity log: the container group create is recorded" "$(activity_count "$STUDENT" 'Create/Update container group' Succeeded)" 1

  # The site, through the class URL path the labs use (/cloud/site/<label>/ on cloud-api:8080, Lab 5's troubleshooting box).
  expect_wait "site answers with the message, owner and image (Lab 5 step 4)" 45 site_has "$STUDENT" "$label" '<h1>Hello from Dojo Cloud!</h1>'
  expect_has "site page: owner and image pills" "owner: $STUDENT" 'image: dojo/hello:1.0' 'HTTP 200'
  tf "terraform output -raw url; echo; echo BASE=\$TF_VAR_portal_base_url" 60 url
  local url_out base_out
  url_out=$(sed -n 1p "$OUT"); base_out=$(sed -n 's/^BASE=//p' "$OUT")
  expect_eq "the url output is <TF_VAR_portal_base_url>/site/<label>/ (outputs.tf)" "$base_out/site/$label/" "$url_out"
  expect_has "and TF_VAR_portal_base_url ends in /cloud, so the class URL path is /cloud/site/<label>/" "/cloud/site/$label/"
  _logs_have_startup() { portal_call GET "$cg_path/logs?tail=50" "$STUDENT"; pj body.logs | grep -qF "dojo/hello:1.0 starting for owner '$STUDENT'"; }
  expect_wait "portal Logs tab shows the container's startup line (Lab 5 step 5)" 20 _logs_have_startup

  tf "terraform output && terraform state list" 60 outputs
  expect_has "outputs (Lab 5 step 6)" 'fqdn = ' 'resource_id = ' 'url = ' 'azurerm_container_group.hello' 'azurerm_resource_group.main'
  tf "terraform state list" 60 state-list
  expect_eq "state list has two resources" 2 "$(out_lines)"
  tf "$PLAN" 180 plan-clean
  expect_has "plan after apply: refreshes and finds nothing to do" 'Refreshing state...' 'No changes. Your infrastructure matches the configuration.'
  tf "git status --short" 30 git-status
  expect_eq "git status --short prints nothing (state and .terraform/ are ignored)" 0 "$(out_lines)"

  section "Lab 6: break a policy on purpose"
  # (a) a missing required tag: the plan looks fine, the cloud refuses at apply, nothing changes
  cmd=$(lab_line lab6.md "sed -i '/^    owner /d' locals.tf") || abort_area "Lab 6's sed line is gone"
  tf "$cmd && git diff" 60 tag-edit
  expect_has "owner tag line removed (Lab 6 step 1)" 'owner = var.owner'
  tf "$PLAN" 180 plan-notag
  expect_has "plan looks reasonable: two in-place changes (it cannot see policy)" \
    'azurerm_container_group.hello will be updated in-place' 'azurerm_resource_group.main will be updated in-place' \
    "\"owner\" = \"$STUDENT\" -> null" 'Plan: 0 to add, 2 to change, 0 to destroy.'
  tf "$APPLY" 300 apply-notag
  expect_rc "apply is refused" nonzero
  expect_has "the cloud names the rule and the tag (Lab 6 step 1)" \
    'unexpected status 403' 'RequestDisallowedByPolicy' "Policy: 'Require tag 'owner''" \
    "The resource is missing the required tag 'owner'." 'with azurerm_resource_group.main' 'on main.tf line 4'
  expect_secs_le "the refusal is fast (lab says about 2 s)" 30
  tf "git checkout -q locals.tf && $PLAN" 180 plan-restored
  expect_has "nothing was changed: after undoing the edit the plan is clean" 'No changes. Your infrastructure matches the configuration.'

  # (b) a region that is not allowed: caught by the starter's own validation at plan, before the cloud is involved
  cmd=$(lab_line lab6.md "sed -i 's/^location .*/location    = \"eastus\"/' terraform.tfvars") || abort_area "Lab 6's location sed line is gone"
  tf "$cmd && $PLAN" 120 plan-eastus
  expect_rc "plan with location eastus fails" nonzero
  expect_has "starter validation message (Lab 6 step 2)" \
    'Invalid value for variable' 'var.location is "eastus"' \
    'location must be canadacentral or canadaeast (the only regions Dojo Cloud policy allows).'
  expect_secs_le "the validation failure is instant" 30
  tf "git checkout -q terraform.tfvars" 30 restore-tfvars

  # (c) too big: the plan is happy, apply destroys the old container first and then the create is refused
  cmd=$(lab_line lab6.md "sed -i 's/cpu    = 0.25/cpu    = 2/' main.tf") || abort_area "Lab 6's cpu sed line is gone"
  tf "$cmd && $PLAN" 180 plan-bigcpu
  expect_has "plan: a replacement (Lab 6 step 3)" \
    'azurerm_container_group.hello must be replaced' '# forces replacement' 'Plan: 1 to add, 0 to change, 1 to destroy.'
  tf "$APPLY" 420 apply-bigcpu
  expect_rc "the replacement is refused" nonzero
  expect_has "old container destroyed, then the size limit (Lab 6 step 3)" \
    'Destruction complete' 'unexpected status 400' \
    'InvalidResourceRequest: Requested 2.0 vCPU / 0.125 GB exceeds the per-container limit of 0.25 vCPU / 0.125 GB.'
  tf "terraform state list" 60 state-after-bigcpu
  expect_eq "state now lists only the resource group (the site is gone)" "azurerm_resource_group.main" "$(head -n1 "$OUT")"
  portal_counts "$STUDENT"
  expect_eq "portal: the container instance is gone, the resource group stays" "1/0" "$N_RG/$N_CG"
  site_get "$STUDENT" "$label"
  expect_has "site shows the 'not deployed' text" 'No site is deployed under that name (yet).' 'HTTP 404'
  tf "git checkout -q main.tf && $APPLY" 420 apply-recover
  expect_has "recovery: git checkout + apply brings the site back (Lab 6 step 3)" 'Apply complete! Resources: 1 added, 0 changed, 0 destroyed.'
  expect_wait "site is back" 45 site_has "$STUDENT" "$label" '<h1>Hello from Dojo Cloud!</h1>'

  section "Lab 7: drift (the portal API stands in for the clicks)"
  # (a) somebody adds a tag in the portal: PATCH replaces the whole tag set (PLAN 5.6)
  portal_call GET "$cg_path" "$STUDENT"
  body=$(pj_json body.summary.tags | python3 -B -c 'import json,sys; raw=sys.stdin.read().strip(); t=json.loads(raw) if raw else {}; t["edited_by"]="portal"; print(json.dumps({"tags": t}))')
  portal_call PATCH "$cg_path" "$STUDENT" "$body"
  expect_eq "portal tag edit is accepted" 200 "$P_STATUS"
  tf "$PLAN" 180 plan-tagdrift
  expect_has "plan sees the extra tag as drift (Lab 7 step 1)" \
    'azurerm_container_group.hello will be updated in-place' '"edited_by" = "portal" -> null' \
    'Plan: 0 to add, 1 to change, 0 to destroy.'
  tf "$APPLY" 300 apply-tagdrift
  expect_has "apply puts the code's tags back" 'Apply complete! Resources: 0 added, 1 changed, 0 destroyed.'
  portal_call GET "$cg_path" "$STUDENT"
  expect_eq "the edited_by tag is gone from the portal" "" "$(pj body.summary.tags.edited_by)"
  expect_ge "activity log labels the hand edit (portal)" "$(activity_count "$STUDENT" 'Update container group tags (portal)' Succeeded)" 1

  # (b) somebody deletes the container in the portal: plan shows + create, apply restores it
  portal_call DELETE "$cg_path" "$STUDENT"
  expect_eq "portal delete of the container group is accepted" 200 "$P_STATUS"
  expect_pj_eq "portal delete answers deleted: true" body.deleted true
  portal_counts "$STUDENT"
  expect_eq "portal: quota back to 0 / 2 after the delete" "1/0/0" "$N_RG/$N_CG/$QUOTA_USED"
  site_get "$STUDENT" "$label"
  expect_has "the site is gone" 'HTTP 404'
  tf "$PLAN" 180 plan-deleted
  expect_has "plan reports the drift and proposes + create (Lab 7 step 2)" \
    'Objects have changed outside of OpenTofu' 'azurerm_container_group.hello has been deleted' \
    '+ create' 'azurerm_container_group.hello will be created' 'Plan: 1 to add, 0 to change, 0 to destroy.'
  tf "$APPLY" 420 apply-restore
  expect_has "apply restores the container" 'Apply complete! Resources: 1 added, 0 changed, 0 destroyed.'
  expect_wait "site is back after the restore" 45 site_has "$STUDENT" "$label" '<h1>Hello from Dojo Cloud!</h1>'
  tf "$PLAN" 180 plan-after-drift
  expect_has "plan is clean again" 'No changes. Your infrastructure matches the configuration.'
  expect_ge "activity log names the portal delete (Lab 7 step 3)" "$(activity_count "$STUDENT" 'Delete container group (portal)' Succeeded)" 1

  section "Lab 8: in-place vs replace"
  # (a) a tag: ~ on both resources, no downtime
  cmd=$(lab_line lab8.md "sed -i '/managed_by = \"opentofu\"/a") || abort_area "Lab 8's tag sed line is gone"
  tf "$cmd && terraform fmt" 60 tag-add
  expect_has "terraform fmt reports the file it tidied" 'locals.tf'
  tf "$PLAN" 180 plan-tag
  expect_has "tag edit is in place on both resources (Lab 8 step 1)" \
    'azurerm_container_group.hello will be updated in-place' 'azurerm_resource_group.main will be updated in-place' \
    '"cost_center" = "training"' 'Plan: 0 to add, 2 to change, 0 to destroy.'
  expect_lacks "no replacement in a tag edit" '# forces replacement' 'must be replaced'
  tf "$APPLY" 300 apply-tag
  expect_has "tag apply (Lab 8 step 1)" 'Apply complete! Resources: 0 added, 2 changed, 0 destroyed.'
  expect_lacks "the container was not destroyed" 'Destroying...' 'Destruction complete'
  expect_secs_le "in-place edit takes a second or two in the lab; limit 60 s" 60

  # (b) the message (an environment variable): replace
  cmd=$(lab_line lab8.md "sed -i 's/^message .*/message") || abort_area "Lab 8's message sed line is gone"
  tf "$cmd && $PLAN" 180 plan-message
  expect_has "environment variable edit forces replacement (Lab 8 step 2)" \
    'azurerm_container_group.hello must be replaced' 'environment_variables = { # forces replacement' \
    '"MESSAGE" = "Hello from Dojo Cloud!" -> "Hello, Canada!"' 'Plan: 1 to add, 0 to change, 1 to destroy.'
  expect_lacks "the resource group is not replaced" 'azurerm_resource_group.main must be replaced'
  tf "$APPLY" 420 apply-message
  expect_has "message apply destroys, then creates (Lab 8 step 2)" \
    'Destroying...' 'Creating...' 'Apply complete! Resources: 1 added, 0 changed, 1 destroyed.'
  expect_wait "site shows the new message" 45 site_has "$STUDENT" "$label" '<h1>Hello, Canada!</h1>'

  # (c) the image: replace, and the site turns green
  cmd=$(lab_line lab8.md "sed -i 's/^image_tag .*/image_tag") || abort_area "Lab 8's image sed line is gone"
  tf "$cmd && $PLAN" 180 plan-image
  expect_has "image edit forces replacement (Lab 8 step 3)" \
    '"dojo/hello:1.0" -> "dojo/hello:2.0" # forces replacement' 'Plan: 1 to add, 0 to change, 1 to destroy.'
  tf "$APPLY" 420 apply-image
  expect_has "image apply" 'Apply complete! Resources: 1 added, 0 changed, 1 destroyed.'
  expect_wait "site runs the 2.0 image with the same message" 45 site_has "$STUDENT" "$label" 'image: dojo/hello:2.0'
  expect_has "message survived the image change" '<h1>Hello, Canada!</h1>'

  # (d) -replace: nothing changed in the config, rebuild anyway
  tf "$PLAN -replace=azurerm_container_group.hello" 180 plan-replace
  expect_has "-replace plan (Lab 8 step 4)" \
    'azurerm_container_group.hello will be replaced, as requested' 'Plan: 1 to add, 0 to change, 1 to destroy.'
  tf "$APPLY -replace=azurerm_container_group.hello" 420 apply-replace
  expect_has "-replace apply rebuilds the container" 'Apply complete! Resources: 1 added, 0 changed, 1 destroyed.'
  expect_wait "site is back after -replace" 45 site_has "$STUDENT" "$label" '<h1>Hello, Canada!</h1>'

  # (e) create_before_destroy cannot coexist with the same name: fails, harmlessly (optional section 5 of the lab)
  cmd=$(lab_line lab8.md "sed -i '\$i") || abort_area "Lab 8's create_before_destroy sed line is gone"
  tf "$cmd && $PLAN -replace=azurerm_container_group.hello | grep -E 'Plan:|replace'" 180 plan-cbd
  expect_has "create_before_destroy flips the symbol (Lab 8 step 5)" \
    '+/- create replacement and then destroy' 'will be replaced, as requested' 'Plan: 1 to add, 0 to change, 1 to destroy.'
  tf "$APPLY -replace=azurerm_container_group.hello" 300 apply-cbd
  expect_rc "the replacement cannot coexist with the old container" nonzero
  expect_has "error text (Lab 8 step 5)" 'a resource with the ID' 'already exists'
  tf "terraform state list" 60 state-after-cbd
  expect_has "the old container is still tracked and running" 'azurerm_container_group.hello'
  portal_counts "$STUDENT"
  expect_eq "portal: still one container group" 1 "$N_CG"
  tf "git checkout -q main.tf" 30 restore-main

  section "Lab 9: for_each and the quota"
  cmd=$(lab_block lab9.md "^cat >> main.tf <<'HCL'" '^HCL$') || abort_area "Lab 9's heredoc is gone"
  tf "$cmd" 60 append-extra
  expect_rc "the for_each block was appended" 0
  tf "terraform fmt -check && echo fmt-ok; terraform validate -no-color; $PLAN | grep -E '^  # |^Plan:'" 240 plan-extra
  expect_has "fmt, validate and plan (Lab 9 step 2)" \
    'fmt-ok' 'Success! The configuration is valid.' \
    '# azurerm_container_group.extra["blue"] will be created' '# azurerm_container_group.extra["green"] will be created' \
    'Plan: 2 to add, 0 to change, 0 to destroy.'
  tf "$APPLY" 420 apply-quota
  expect_rc "the third container group is refused (apply fails)" nonzero
  expect_has "QuotaExceeded with the policy message (Lab 9 step 3)" \
    'unexpected status 409' \
    'QuotaExceeded: Subscription quota reached: at most 2 container groups are allowed. Destroy one before creating another.'
  tf "terraform state list" 60 state-quota
  expect_eq "state lists exactly three resources: hello, the resource group and ONE extra" 3 "$(out_lines)"
  survivor=blue; other=green
  if out_has 'extra["green"]'; then survivor=green; other=blue; fi
  say "  info: the surviving extra instance is '$survivor' (which one wins is a race)"
  portal_counts "$STUDENT"
  expect_eq "portal: two container groups, Quota 2 / 2" "2/2" "$N_CG/$QUOTA_USED"
  # step 5: make the code say what exists
  cmd=$(lab_line lab9.md "sed -i 's/for_each = toset(") || abort_area "Lab 9's for_each sed line is gone"
  if [ "$survivor" = green ]; then cmd="sed -i 's/for_each = toset(\\[\"blue\", \"green\"\\])/for_each = toset([\"green\"])/' main.tf"; fi
  tf "$cmd && grep -n 'for_each =' main.tf && $PLAN" 240 plan-fix
  expect_has "code, state and cloud agree again (Lab 9 step 5)" "for_each = toset([\"$survivor\"])" 'No changes. Your infrastructure matches the configuration.'

  section "Lab 10: clean up"
  local del_rg_before del_cg_before
  del_rg_before=$(activity_count "$STUDENT" 'Delete resource group' Succeeded)
  del_cg_before=$(activity_count "$STUDENT" 'Delete container group' Succeeded)
  tf "$PLAN -destroy | grep -E '^  # |^Plan:'" 180 plan-destroy
  expect_has "destroy preview lists everything in state (Lab 10 step 1)" \
    "# azurerm_container_group.extra[\"$survivor\"] will be destroyed" '# azurerm_container_group.hello will be destroyed' \
    '# azurerm_resource_group.main will be destroyed' 'Plan: 0 to add, 0 to change, 3 to destroy.'
  tf "$DESTROY" 480 destroy
  expect_rc "destroy succeeds" 0
  expect_has "destroy output (Lab 10 step 2)" 'Destroy complete! Resources: 3 destroyed.' 'azurerm_resource_group.main: Destruction complete'
  expect_secs_le "destroy takes about 35 s in the lab; limit 180 s" 180
  say "  info: Lab 10 destroy took ${SECS}s"
  portal_counts "$STUDENT"
  expect_eq "portal is empty: 0 resource groups, 0 container instances, Quota 0 / 2 (Lab 10 step 3)" "0/0/0" "$N_RG/$N_CG/$QUOTA_USED"
  expect_eq "activity log records the resource group deletion (Lab 10 step 3)" "$((del_rg_before + 1))" "$(activity_count "$STUDENT" 'Delete resource group' Succeeded)"
  expect_eq "activity log records both container deletions" "$((del_cg_before + 2))" "$(activity_count "$STUDENT" 'Delete container group' Succeeded)"
  site_get "$STUDENT" "$label"
  expect_has "the site link says no site is deployed" 'No site is deployed under that name (yet).'
  tf "terraform state list" 60 state-final
  expect_rc "state list works after destroy" 0
  expect_eq "state list prints nothing" 0 "$(out_lines)"
  tf "ls -la terraform.tfstate*; cat terraform.tfstate" 30 tfstate
  expect_has "the state file and its backup are left behind, tracking nothing (Lab 10 step 3)" \
    'terraform.tfstate' 'terraform.tfstate.backup' '"resources": []' '"outputs": {}'
  tf "test -d .terraform && test -f .terraform.lock.hcl && echo plugins-and-lock-kept" 30 kept
  expect_has ".terraform/ and the lock file are still there" 'plugins-and-lock-kept'
  tf "$PLAN | grep '^Plan:'" 180 plan-rebuild
  expect_has "the code still describes three resources (Lab 10 step 3)" 'Plan: 3 to add, 0 to change, 0 to destroy.'
  tf "git status --short" 30 git-final
  expect_has "git status lists only the tracked files the labs edited (Lab 10 step 4)" 'locals.tf' 'main.tf' 'terraform.tfvars'
  expect_lacks "git status does not list state or plugins" 'tfstate' '.terraform/'
}

_cg_running() { [ "$(cg_state "$STUDENT")" = Running ]; }
