locals {
  # Dojo Cloud requires owner and env. The labs will also require costCenter,
  # which is deliberately missing here.
  tags = {
    owner = var.owner
    env   = "dev"
  }
}

resource "azurerm_resource_group" "app" {
  name     = "rg-${var.owner}-app"
  location = var.location
  tags     = local.tags
}

resource "azurerm_container_group" "app" {
  name                = "ci-${var.owner}-app"
  location            = azurerm_resource_group.app.location
  resource_group_name = azurerm_resource_group.app.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "${var.owner}-app"

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = "dojo/hello:1.0"
    cpu    = 0.25
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }
  }

  tags = local.tags
}
