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

data "azurerm_resource_group" "infra" {
  name = "rg-${var.owner}-app"
}

resource "azurerm_policy_definition" "allowed_images" {
  name         = "allowed-images"
  policy_type  = "Custom"
  mode         = "Indexed"
  display_name = "Allowed container images"

  policy_rule = file("${path.module}/rules/allowed-images.json")

  parameters = jsonencode({
    allowedImages = {
      type = "Array"
    }
    effect = {
      type         = "String"
      defaultValue = "deny"
    }
  })
}

# Same definition, two assignments, two different parameter values.
resource "azurerm_subscription_policy_assignment" "images_subscription" {
  name                 = "images-subscription"
  subscription_id      = data.azurerm_subscription.current.id
  policy_definition_id = azurerm_policy_definition.allowed_images.id
  parameters = jsonencode({
    allowedImages = { value = ["dojo/hello:1.0", "dojo/hello:2.0"] }
  })
}

resource "azurerm_resource_group_policy_assignment" "images_strict" {
  name                 = "images-strict"
  resource_group_id    = data.azurerm_resource_group.infra.id
  policy_definition_id = azurerm_policy_definition.allowed_images.id
  parameters = jsonencode({
    allowedImages = { value = ["dojo/hello:2.0"] }
  })
}
