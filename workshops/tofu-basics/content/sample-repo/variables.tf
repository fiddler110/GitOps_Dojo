# Inputs: the knobs someone can turn without editing the resources themselves.
# Values come from terraform.tfvars, -var flags, or TF_VAR_* environment vars.
#
# The validation blocks below repeat rules that Dojo Cloud's policy enforces
# anyway. Checking them here fails fast, on your laptop, in plain language,
# before anything is sent to the cloud.

variable "owner" {
  description = "Who owns these resources. Becomes the required 'owner' tag and part of the site name."
  type        = string
  # No default on purpose: your terminal already sets TF_VAR_owner for you.
  # OpenTofu reads any environment variable named TF_VAR_<name> into var.<name>.
}

variable "portal_base_url" {
  description = "Base address of the Dojo portal, used to print a clickable site link. Set by TF_VAR_portal_base_url."
  type        = string
  default     = ""
}

variable "location" {
  description = "Azure-style region. Policy only allows the two Canadian regions."
  type        = string
  default     = "canadacentral"

  validation {
    condition     = contains(["canadacentral", "canadaeast"], var.location)
    error_message = "location must be canadacentral or canadaeast (the only regions Dojo Cloud policy allows)."
  }
}

variable "workload" {
  description = "Short name of what you are building. Used in resource names."
  type        = string
  default     = "hello"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{1,15}$", var.workload))
    error_message = "workload must be 2-16 characters: lowercase letters and digits, starting with a letter."
  }
}

variable "environment" {
  description = "Which environment this is. Becomes the required 'env' tag and part of the names."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment must be dev, test or prod."
  }
}

variable "message" {
  description = "The text your hello site shows."
  type        = string
  default     = "Hello from Dojo Cloud!"

  validation {
    condition     = length(var.message) > 0 && length(var.message) <= 100
    error_message = "message must be 1-100 characters."
  }
}

variable "image_tag" {
  description = "Version of the dojo/hello image to run. Only 1.0 and 2.0 are approved."
  type        = string
  default     = "1.0"

  validation {
    condition     = contains(["1.0", "2.0"], var.image_tag)
    error_message = "image_tag must be 1.0 or 2.0 (the approved dojo/hello versions)."
  }
}
