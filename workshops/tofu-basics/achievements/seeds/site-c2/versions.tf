# Which OpenTofu / Terraform and which providers this configuration needs.
# Pinning versions means everyone (and every CI run) installs the same code.
# The exact version that was chosen is recorded in .terraform.lock.hcl.
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.6"
    }
  }
}
