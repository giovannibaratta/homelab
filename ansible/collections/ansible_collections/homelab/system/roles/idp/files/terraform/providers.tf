provider "zitadel" {
  domain           = var.zitadel_instance.host
  insecure         = false
  port             = var.zitadel_instance.port
  jwt_profile_file = var.zitadel_instance.jwt_path
}
