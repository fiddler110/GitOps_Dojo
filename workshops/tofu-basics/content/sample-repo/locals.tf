# Locals: names and tags computed once, from the inputs, and reused everywhere.
# Names follow the Cloud Adoption Framework style used in real Azure shops:
#   <resource type prefix>-<workload>-<environment>[-<region>]
# Dojo Cloud policy enforces the prefixes: rg- for resource groups, ci- for
# container groups.
locals {
  region_short = lookup({ canadacentral = "cac", canadaeast = "cae" }, var.location, var.location)

  rg_name = "rg-${var.workload}-${var.environment}-${local.region_short}"
  ci_name = "ci-${var.workload}-${var.environment}"
  # Site names are shared by the whole class, so include your username.
  dns_label = "${var.workload}-${var.environment}-${var.owner}"

  # Policy requires the tags 'owner' and 'env' on everything.
  tags = {
    owner      = var.owner
    env        = var.environment
    managed_by = "opentofu"
  }
}
