# Inputs: the knobs someone can turn without editing the resources themselves.
# Values come from terraform.tfvars, -var flags, or TF_VAR_* environment vars.

variable "learner" {
  description = "Your name, used in the greeting file."
  type        = string
  default     = "student"
}

variable "greeting" {
  description = "The message written to out/hello.txt."
  type        = string
  default     = "Hello from OpenTofu!"
}

variable "pet_words" {
  description = "How many words in the random pet name (2-4)."
  type        = number
  default     = 2

  validation {
    condition     = var.pet_words >= 2 && var.pet_words <= 4
    error_message = "pet_words must be between 2 and 4."
  }
}
