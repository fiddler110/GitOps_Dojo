# No credentials and no endpoint here. The terminal hands every account its own
# ARM_* environment variables (see `dojo-env`), like a service principal in a pipeline.
provider "azurerm" {
  features {}
}
