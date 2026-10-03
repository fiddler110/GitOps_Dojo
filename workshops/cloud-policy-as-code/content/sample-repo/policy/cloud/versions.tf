terraform {
  required_version = ">= 1.6.0"

  backend "http" {
    address        = "https://management.dojo.cloud/_dojo/tfstate/policy"
    lock_address   = "https://management.dojo.cloud/_dojo/tfstate/policy"
    unlock_address = "https://management.dojo.cloud/_dojo/tfstate/policy"
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.6"
    }
  }
}
