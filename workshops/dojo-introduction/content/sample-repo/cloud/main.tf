# One resource group in Dojo Cloud. `tofu plan` shows what would be created;
# `tofu apply` makes it, and the Dojo Cloud portal (the landing-page card) shows it.
# Dojo Cloud's policy wants an `rg-` name, a Canadian region and `owner` and `env` tags.
resource "azurerm_resource_group" "tour" {
  name     = "rg-tour-demo-cac"
  location = "canadacentral"
  tags = {
    owner = "dojo-tour"
    env   = "demo"
  }
}
