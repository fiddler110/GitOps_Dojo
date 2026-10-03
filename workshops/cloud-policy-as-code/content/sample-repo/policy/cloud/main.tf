data "azurerm_subscription" "current" {}

# Lab 3: first policy as code. Uncomment the definition and the assignment below, then read them.
# The rule is JSON in rules/; the effect is a parameter, so the same rule can audit or deny.
# resource "azurerm_policy_definition" "require_costcenter" {
#   name         = "require-costcenter-tag"
#   policy_type  = "Custom"
#   mode         = "All"
#   display_name = "Require a costCenter tag"
#
#   policy_rule = file("${path.module}/rules/require-costcenter-tag.json")
#
#   parameters = jsonencode({
#     effect = {
#       type          = "String"
#       allowedValues = ["audit", "deny", "disabled"]
#       defaultValue  = "deny"
#     }
#   })
# }
#
# # Assigned at subscription scope, so this folder never needs infra/ applied first.
# resource "azurerm_subscription_policy_assignment" "require_costcenter" {
#   name                 = "require-costcenter"
#   subscription_id      = data.azurerm_subscription.current.id
#   policy_definition_id = azurerm_policy_definition.require_costcenter.id
# }

# Lab 5: parameters and reuse. Uncomment the data source, the definition and both assignments.
# data "azurerm_resource_group" "infra" {
#   name = "rg-${var.owner}-app"
# }
#
# resource "azurerm_policy_definition" "allowed_images" {
#   name         = "allowed-images"
#   policy_type  = "Custom"
#   mode         = "Indexed"
#   display_name = "Allowed container images"
#
#   policy_rule = file("${path.module}/rules/allowed-images.json")
#
#   parameters = jsonencode({
#     allowedImages = {
#       type = "Array"
#     }
#     effect = {
#       type         = "String"
#       defaultValue = "deny"
#     }
#   })
# }
#
# # Same definition, two assignments, two different parameter values.
# resource "azurerm_subscription_policy_assignment" "images_subscription" {
#   name                 = "images-subscription"
#   subscription_id      = data.azurerm_subscription.current.id
#   policy_definition_id = azurerm_policy_definition.allowed_images.id
#   parameters = jsonencode({
#     allowedImages = { value = ["dojo/hello:1.0", "dojo/hello:2.0"] }
#   })
# }
#
# resource "azurerm_resource_group_policy_assignment" "images_strict" {
#   name                 = "images-strict"
#   resource_group_id    = data.azurerm_resource_group.infra.id
#   policy_definition_id = azurerm_policy_definition.allowed_images.id
#   parameters = jsonencode({
#     allowedImages = { value = ["dojo/hello:2.0"] }
#   })
#   enforce              = false
# }

# Lab 6: policy sets. Uncomment this, and delete the separate require_costcenter and images_subscription assignments (the set replaces them).
# resource "azurerm_policy_definition" "allowed_locations" {
#   name         = "allowed-locations"
#   policy_type  = "Custom"
#   mode         = "Indexed"
#   display_name = "Allowed locations"
#
#   policy_rule = file("${path.module}/rules/allowed-locations.json")
#
#   parameters = jsonencode({
#     allowedLocations = {
#       type = "Array"
#     }
#     effect = {
#       type         = "String"
#       defaultValue = "deny"
#     }
#   })
# }
#
# resource "azurerm_policy_set_definition" "team_baseline" {
#   name         = "team-baseline"
#   policy_type  = "Custom"
#   display_name = "Team baseline"
#
#   # Set parameters: what the assignment supplies, passed down to the members.
#   parameters = jsonencode({
#     effect           = { type = "String", defaultValue = "deny" }
#     allowedImages    = { type = "Array" }
#     allowedLocations = { type = "Array" }
#   })
#
#   policy_definition_reference {
#     policy_definition_id = azurerm_policy_definition.require_costcenter.id
#     reference_id         = "costcenter"
#     parameter_values     = jsonencode({ effect = { value = "[parameters('effect')]" } })
#   }
#   policy_definition_reference {
#     policy_definition_id = azurerm_policy_definition.allowed_images.id
#     reference_id         = "images"
#     parameter_values = jsonencode({
#       allowedImages = { value = "[parameters('allowedImages')]" }
#       effect        = { value = "[parameters('effect')]" }
#     })
#   }
#   policy_definition_reference {
#     policy_definition_id = azurerm_policy_definition.allowed_locations.id
#     reference_id         = "locations"
#     parameter_values = jsonencode({
#       allowedLocations = { value = "[parameters('allowedLocations')]" }
#       effect           = { value = "[parameters('effect')]" }
#     })
#   }
# }
#
# # One assignment for the whole baseline replaces the separate subscription assignments.
# resource "azurerm_subscription_policy_assignment" "team_baseline" {
#   name                 = "team-baseline"
#   subscription_id      = data.azurerm_subscription.current.id
#   policy_definition_id = azurerm_policy_set_definition.team_baseline.id
#   parameters = jsonencode({
#     effect           = { value = "deny" }
#     allowedImages    = { value = ["dojo/hello:1.0", "dojo/hello:2.0"] }
#     allowedLocations = { value = ["canadacentral", "canadaeast"] }
#   })
# }

# Lab 7: modify and remediation. Needs the Lab 5 data source.
# resource "azurerm_policy_definition" "add_managedby_tag" {
#   name         = "add-managedby-tag"
#   policy_type  = "Custom"
#   mode         = "Indexed"
#   display_name = "Add managedBy = policy tag"
#
#   policy_rule = file("${path.module}/rules/add-managedby-tag.json")
# }
#
# # Modify needs an identity (the real thing uses it to write to resources) and a
# # location for that identity. The role GUID in the rule is not checked by Dojo Cloud.
# resource "azurerm_subscription_policy_assignment" "add_managedby_tag" {
#   name                 = "add-managedby-tag"
#   subscription_id      = data.azurerm_subscription.current.id
#   policy_definition_id = azurerm_policy_definition.add_managedby_tag.id
#   location             = "canadacentral"
#
#   identity {
#     type = "SystemAssigned"
#   }
# }
#
# # New resources get the tag at once. Existing ones only when remediated.
# resource "azurerm_resource_group_policy_remediation" "managedby" {
#   name                 = "managedby"
#   resource_group_id    = data.azurerm_resource_group.infra.id
#   policy_assignment_id = azurerm_subscription_policy_assignment.add_managedby_tag.id
# }

# Lab 8: exemptions. Needs the Lab 6 set assignment and the Lab 4 legacy resource group.
# data "azurerm_resource_group" "legacy" {
#   name = "rg-${var.owner}-legacy"
# }
#
# # A waiver is a reviewed, dated exception. Set expires_on to a date about a week away.
# resource "azurerm_resource_group_policy_exemption" "legacy_costcenter" {
#   name                            = "legacy-costcenter"
#   resource_group_id               = data.azurerm_resource_group.legacy.id
#   policy_assignment_id            = azurerm_subscription_policy_assignment.team_baseline.id
#   policy_definition_reference_ids = ["costcenter"]
#   exemption_category              = "Waiver"
#   display_name                    = "Legacy RG costCenter waiver"
#   description                     = "Legacy resource group predates the tagging rule; migration ticket OPS-123."
#   expires_on                      = "2026-10-09T00:00:00Z"
# }
