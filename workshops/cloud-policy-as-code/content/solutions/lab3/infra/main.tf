locals {
  # owner and env are required by the built-in guardrails; Lab 3 adds costCenter.
  tags = {
    owner      = var.owner
    env        = "dev"
    costCenter = "cc-1001"
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
