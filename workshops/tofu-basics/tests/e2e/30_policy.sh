#!/usr/bin/env bash
# shellcheck shell=bash
# Area policy: every rule in compose/cloud-api/policy.py, refused by the real cloud through the real azurerm provider,
# with the message text the labs quote. Each refusal must be
#   * an error (non-zero exit) whose text names the code and the rule,
#   * fast (a request that is refused at the door, not a 35 s deployment),
#   * a NO-OP: nothing in the tofu state, no new resource group or container group in the portal, and a Failed
#     event in the student's activity log.
# The cases use small throw-away configurations (no variable validation, unlike the starter repo, so the request
# really reaches the cloud) in ~/e2e-<id>/policy/. One resource group "rg-e2e-policy" is created first so that the
# container-group cases have somewhere to go (a container group PUT into a missing group answers 404 before policy).
# Sourced by tests/e2e.sh; running this file directly hands over to e2e.sh with --only policy.

if [ "${BASH_SOURCE[0]}" = "$0" ]; then exec "$(dirname "$0")/../e2e.sh" --only policy "$@"; fi

_POLICY_HEADER='terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.6"
    }
  }
}

provider "azurerm" {
  features {}
}
'

_policy_base_tf() {  # the one valid resource group
  printf '%s\n' "$_POLICY_HEADER"
  cat <<'HCL'
resource "azurerm_resource_group" "rg" {
  name     = "rg-e2e-policy"
  location = "canadacentral"
  tags     = { owner = "e2e", env = "dev" }
}
HCL
}

_policy_rg_tf() {  # a resource group whose name / location / tags come from variables
  printf '%s\n' "$_POLICY_HEADER"
  cat <<'HCL'
variable "name" { default = "rg-e2e-bad" }
variable "location" { default = "canadacentral" }
variable "omit_tags" {
  type    = list(string)
  default = []
}

resource "azurerm_resource_group" "rg" {
  name     = var.name
  location = var.location
  tags     = { for k, v in { owner = "e2e", env = "dev" } : k => v if !contains(var.omit_tags, k) }
}
HCL
}

_policy_cg_tf() {  # a container group in the existing rg-e2e-policy, everything variable
  printf '%s\n' "$_POLICY_HEADER"
  cat <<'HCL'
variable "owner" {}
variable "name" { default = "ci-e2e-policy" }
variable "location" { default = "canadacentral" }
variable "image" { default = "dojo/hello:1.0" }
variable "cpu" { default = 0.25 }
variable "memory" { default = 0.125 }
variable "port" { default = 80 }
variable "omit_tags" {
  type    = list(string)
  default = []
}

resource "azurerm_container_group" "cg" {
  name                = var.name
  location            = var.location
  resource_group_name = "rg-e2e-policy"
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "e2e-policy-${var.owner}"

  exposed_port {
    port     = var.port
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = var.image
    cpu    = var.cpu
    memory = var.memory

    ports {
      port     = var.port
      protocol = "TCP"
    }

    environment_variables = {
      MESSAGE = "policy test"
      OWNER   = var.owner
    }
  }

  tags = { for k, v in { owner = "e2e", env = "dev" } : k => v if !contains(var.omit_tags, k) }
}
HCL
}

# _policy_case DIR DESC "-var args" NEEDLE...  : apply must fail with the needles in its output, fast, changing nothing.
_policy_case() {
  local dir=$1 desc=$2 vars=$3; shift 3
  local rg_before cg_before failed_before rg_after cg_after failed_after
  portal_counts "$STUDENT"; rg_before=$N_RG; cg_before=$N_CG
  failed_before=$(activity_failed "$STUDENT")
  as_student "$STUDENT" "cd '$dir' && terraform apply -auto-approve -no-color -input=false $vars" 240 "case-$desc"
  expect_rc "policy: $desc: apply is refused" nonzero
  expect_has "policy: $desc: the message names the code and the rule" "$@"
  expect_secs_le "policy: $desc: refused quickly" "$POLICY_MAX_SECS"
  as_student "$STUDENT" "cd '$dir' && terraform state list" 60 "state-$desc"
  expect_eq "policy: $desc: nothing in the tofu state" 0 "$(out_lines)"
  portal_counts "$STUDENT"; rg_after=$N_RG; cg_after=$N_CG
  expect_eq "policy: $desc: no resource group or container group was created" "$rg_before/$cg_before" "$rg_after/$cg_after"
  failed_after=$(activity_failed "$STUDENT")
  expect_ge "policy: $desc: a Failed event is in the activity log" "$failed_after" "$((failed_before + 1))"
}

area_policy() {
  prepare_repo || abort_area "cannot prepare the starter repo"
  local base="$WORK/policy/base" rgd="$WORK/policy/rg" cgd="$WORK/policy/cg" d
  register_tofu_dir "$STUDENT" "$base"

  section "Set up: one valid resource group, and two scratch configurations"
  for d in "$base" "$rgd" "$cgd"; do
    as_student "$STUDENT" "mkdir -p '$d' && cp '$REPO/.terraform.lock.hcl' '$d/'" 30 mkdir
  done
  _policy_base_tf | put_file "$STUDENT" "$base/main.tf"
  _policy_rg_tf | put_file "$STUDENT" "$rgd/main.tf"
  _policy_cg_tf | put_file "$STUDENT" "$cgd/main.tf"
  for d in "$base" "$rgd" "$cgd"; do
    as_student "$STUDENT" "cd '$d' && terraform init -no-color -input=false" 180 init
    expect_rc "init in ${d##*/}" 0
  done
  as_student "$STUDENT" "cd '$base' && terraform apply -auto-approve -no-color -input=false" 420 apply-base
  expect_has "the valid resource group rg-e2e-policy is created (name and tags satisfy policy)" 'Apply complete! Resources: 1 added, 0 changed, 0 destroyed.'
  portal_counts "$STUDENT"
  expect_eq "portal shows that one resource group and no container group" "1/0" "$N_RG/$N_CG"

  section "Resource group rules"
  _policy_case "$rgd" "rg missing owner tag" "-var 'omit_tags=[\"owner\"]'" \
    'unexpected status 403' 'RequestDisallowedByPolicy' "Policy: 'Require tag 'owner''" "The resource is missing the required tag 'owner'."
  _policy_case "$rgd" "rg missing env tag" "-var 'omit_tags=[\"env\"]'" \
    'RequestDisallowedByPolicy' "Policy: 'Require tag 'env''" "The resource is missing the required tag 'env'."
  _policy_case "$rgd" "rg bad region" "-var location=eastus" \
    'unexpected status 403' 'RequestDisallowedByPolicy' "Policy: 'Allowed locations'" \
    "Location 'eastus' is not allowed; use one of: canadacentral, canadaeast."
  _policy_case "$rgd" "rg name without the rg- prefix" "-var name=hello-rg" \
    'unexpected status 400' 'InvalidResourceGroupName' "must start with 'rg-'"

  section "Container group rules"
  _policy_case "$cgd" "cg name without the ci- prefix" "-var name=hello" \
    'unexpected status 400' 'InvalidContainerGroupName' "must start with 'ci-'"
  _policy_case "$cgd" "cg image not in the list" "-var image=dojo/hello:3.0" \
    'InvalidImage' "Image 'dojo/hello:3.0' is not in the approved image list: dojo/hello:1.0, dojo/hello:2.0."
  _policy_case "$cgd" "cg image from elsewhere" "-var image=nginx:latest" \
    'InvalidImage' "Image 'nginx:latest' is not in the approved image list"
  _policy_case "$cgd" "cg oversize cpu" "-var cpu=2" \
    'unexpected status 400' 'InvalidResourceRequest' \
    'Requested 2.0 vCPU / 0.125 GB exceeds the per-container limit of 0.25 vCPU / 0.125 GB.'
  _policy_case "$cgd" "cg oversize memory" "-var memory=1" \
    'InvalidResourceRequest' 'Requested 0.25 vCPU / 1.0 GB exceeds the per-container limit of 0.25 vCPU / 0.125 GB.'
  _policy_case "$cgd" "cg port other than 80" "-var port=22" \
    'InvalidRequestContent' 'Port 22 is not allowed; the hello image serves on 80.'
  _policy_case "$cgd" "cg missing owner tag" "-var 'omit_tags=[\"owner\"]'" \
    'RequestDisallowedByPolicy' "Resource 'ci-e2e-policy' was disallowed by policy." "Policy: 'Require tag 'owner''"
  _policy_case "$cgd" "cg bad region" "-var location=eastus" \
    'RequestDisallowedByPolicy' "Policy: 'Allowed locations'" "Location 'eastus' is not allowed"

  section "Clean up the scratch resource group"
  as_student "$STUDENT" "cd '$base' && terraform destroy -auto-approve -no-color -input=false" 420 destroy-base
  expect_has "the resource group is destroyed" 'Destroy complete! Resources: 1 destroyed.'
  portal_counts "$STUDENT"
  expect_eq "portal is empty again" "0/0/0" "$N_RG/$N_CG/$QUOTA_USED"
}
