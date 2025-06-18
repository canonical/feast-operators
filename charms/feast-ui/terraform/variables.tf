variable "app_name" {
  description = "Application name"
  type        = string
  default     = "feast-ui"
}

variable "channel" {
  description = "Charm channel"
  type        = string
  default     = "0.49/stable"
}

variable "config" {
  description = "Map of charm configuration options"
  type        = map(string)
  default     = {}
}

variable "model_name" {
  description = "Model name"
  type        = string
}

variable "revision" {
  description = "Charm revision"
  type        = number
  default     = null
}
