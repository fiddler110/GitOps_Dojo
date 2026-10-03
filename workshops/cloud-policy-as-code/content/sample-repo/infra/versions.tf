terraform {
  required_version = ">= 1.6.0"

  backend "http" {
    address        = "https://management.dojo.cloud/_dojo/tfstate/infra"
    lock_address   = "https://management.dojo.cloud/_dojo/tfstate/infra"
    unlock_address = "https://management.dojo.cloud/_dojo/tfstate/infra"
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.6"
    }
  }
}
