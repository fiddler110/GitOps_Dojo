# Challenge c2. Everything here is scoped to rg-<you>-c2, so the lab's policy is not affected.
resource "azurerm_resource_group" "c2" {
  name     = "rg-${var.owner}-c2"
  location = "canadacentral"
  tags = {
    owner      = var.owner
    env        = "dev"
    costCenter = "cc-1001"
  }
}

resource "azurerm_policy_definition" "require_reviewedby" {
  name         = "require-reviewedby-c2"
  policy_type  = "Custom"
  mode         = "All"
  display_name = "Require a reviewedBy tag (challenge c2)"
  policy_rule  = file("${path.module}/rules/require-reviewedby.json")
}

# TODO 1: an azurerm_resource_group_policy_assignment of the definition at azurerm_resource_group.c2.id only.
# TODO 2: an azurerm_resource_group_policy_exemption for that assignment on the same resource group:
#         exemption_category = "Waiver", a description, and expires_on at most 14 days from today.
