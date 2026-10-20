variable "namespace" {
  description = "Existing Kubernetes namespace managed by the Coder provisioner."
  type        = string
  default     = "coder-workspaces"
}

variable "node_name" {
  description = "Node selector"
  type        = string
  default     = "node2"
}

variable "home_storage_gib" {
  description = "Persistent home capacity in GiB for configuration, credentials and Codex state."
  type        = number
  default     = 10
  validation {
    condition     = var.home_storage_gib >= 1 && floor(var.home_storage_gib) == var.home_storage_gib
    error_message = "home_storage_gib must be a positive whole number."
  }
}

variable "workspace_storage_gib" {
  description = "Persistent workspace capacity in GiB for Git source, previews and evidence."
  type        = number
  default     = 50
  validation {
    condition     = var.workspace_storage_gib >= 40 && floor(var.workspace_storage_gib) == var.workspace_storage_gib
    error_message = "Allocate at least 40 GiB using a whole number."
  }
}

variable "ephemeral_storage_gib" {
  description = "Disk-backed emptyDir capacity limit in GiB for rebuildable caches and build output."
  type        = number
  default     = 10
  validation {
    condition     = var.ephemeral_storage_gib >= 1 && floor(var.ephemeral_storage_gib) == var.ephemeral_storage_gib
    error_message = "ephemeral_storage_gib must be a positive whole number."
  }
}
