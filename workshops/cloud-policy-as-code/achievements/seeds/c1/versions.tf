# Local state on purpose: this challenge has a state of its own (terraform.tfstate here, git-ignored),
# so it never touches the fork's `infra` or `policy` state.
terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.6"
    }
  }
}
