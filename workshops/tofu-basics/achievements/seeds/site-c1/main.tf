# Challenge c1: Tag Team. This second site was copied in a hurry and the cloud's
# policy rejects it. Make it deploy, then print its URL with an output named `url`.
#   - name:   the site is called "{user}-second" (the class-wide unique DNS label)
#   - policy: tags, region and size all have rules. `tofu plan` won't show them all,
#             `tofu apply` will.
resource "azurerm_resource_group" "c1" {
  name     = "rg-c1"
  location = "eastus"
  tags     = { challenge = "c1" }
}

resource "azurerm_container_group" "second" {
  name                = "ci-second"
  location            = azurerm_resource_group.c1.location
  resource_group_name = azurerm_resource_group.c1.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "second"

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = "dojo/hello:1.0"
    cpu    = 2
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }
  }

  tags = { challenge = "c1" }
}
