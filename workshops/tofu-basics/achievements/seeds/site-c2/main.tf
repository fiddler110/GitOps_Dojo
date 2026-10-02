# Challenge c2: Quota Whisperer. Five sites, but your subscription holds only 2
# container groups in total. Make `apply` succeed without asking for more quota.
locals {
  sites = ["alpha", "bravo", "charlie", "delta", "echo"]
}

resource "azurerm_resource_group" "c2" {
  name     = "rg-c2"
  location = "canadacentral"
  tags     = { owner = var.owner, env = "dev", challenge = "c2" }
}

resource "azurerm_container_group" "site" {
  for_each            = toset(local.sites)
  name                = "ci-${each.key}"
  location            = azurerm_resource_group.c2.location
  resource_group_name = azurerm_resource_group.c2.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "{user}-c2-${each.key}"

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

  tags = { owner = var.owner, env = "dev", challenge = "c2" }
}
