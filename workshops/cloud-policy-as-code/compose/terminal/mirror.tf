# Build-time only: lists the providers to mirror into /opt/tofu-providers.
# Keep this pin identical to the ones in the sample repo's versions.tf files.
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "5.6.0"
    }
  }
}
