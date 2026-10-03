data "azurerm_subscription" "current" {}

# Lab 3: require a costCenter tag. The rule is JSON in rules/; the effect is a
# parameter, so the same rule can audit or deny.
resource "azurerm_policy_definition" "require_costcenter" {
  name         = "require-costcenter-tag"
  policy_type  = "Custom"
  mode         = "All"
  display_name = "Require a costCenter tag"

  policy_rule = file("${path.module}/rules/require-costcenter-tag.json")

  parameters = jsonencode({
    effect = {
      type          = "String"
      allowedValues = ["audit", "deny", "disabled"]
      defaultValue  = "deny"
    }
  })
}

# Assigned at subscription scope, so this folder never needs infra/ applied first.
resource "azurerm_subscription_policy_assignment" "require_costcenter" {
  name                 = "require-costcenter"
  subscription_id      = data.azurerm_subscription.current.id
  policy_definition_id = azurerm_policy_definition.require_costcenter.id
  parameters = jsonencode({
    effect = { value = "audit" }
  })
}
