# Provider settings. Notice what is NOT here: no credentials and no endpoint.
# The terminal hands every student their own ARM_* environment variables
# (tenant, subscription, client id/secret), exactly like a service principal
# in a real pipeline. Keeping secrets out of .tf files is the point.
provider "azurerm" {
  features {}
}
