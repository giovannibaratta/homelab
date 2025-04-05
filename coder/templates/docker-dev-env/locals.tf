locals {
  persistent_volumes = {
    "home" : "/home/${local.username}",
    "workspace" : "/workspace"
  }
}
