variable "owner" {
  description = "Your username. The terminal and CI set TF_VAR_owner for you. Used to name your resources."
  type        = string
}

variable "location" {
  description = "Region. Dojo Cloud only allows canadacentral and canadaeast."
  type        = string
  default     = "canadacentral"
}
