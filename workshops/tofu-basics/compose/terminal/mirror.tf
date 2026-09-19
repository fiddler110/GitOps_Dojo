# Build-time only: lists the providers to mirror into /opt/tofu-providers.
# Keep these pins identical to the ones in the sample repo's versions.tf files.
terraform {
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "3.9.1"
    }
    local = {
      source  = "hashicorp/local"
      version = "2.9.1"
    }
  }
}
