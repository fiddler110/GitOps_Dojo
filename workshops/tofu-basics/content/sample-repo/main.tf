# The resources: what should exist. Each block is `resource "<type>" "<name>"`.

# 1. A resource group: the folder everything else lives in.
resource "azurerm_resource_group" "main" {
  name     = local.rg_name
  location = var.location
  tags     = local.tags
}

# 2. A container group running the approved dojo/hello image. It refers to the
#    resource group's name and location, so OpenTofu knows to create the group
#    FIRST. You never write that ordering down yourself.
resource "azurerm_container_group" "hello" {
  name                = local.ci_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = local.dns_label

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = "dojo/hello:${var.image_tag}"
    cpu    = 0.25
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }

    environment_variables = {
      MESSAGE = var.message
      OWNER   = var.owner
    }
  }

  tags = local.tags
}
