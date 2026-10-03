# Challenge c1. Everything here is scoped to rg-<you>-c1, so the lab's policy is not affected.
resource "azurerm_resource_group" "c1" {
  name     = "rg-${var.owner}-c1"
  location = "canadacentral"
  tags = {
    owner      = var.owner
    env        = "sandbox"
    costCenter = "cc-1001"
  }
}

# TODO 1: an azurerm_policy_definition named "allowed-envs-c1" that reads rules/allowed-envs.json and
#         declares the parameter allowedEnvs (type Array).
# TODO 2: an azurerm_resource_group_policy_assignment at azurerm_resource_group.c1.id only, with
#         allowedEnvs = ["dev", "test"].
