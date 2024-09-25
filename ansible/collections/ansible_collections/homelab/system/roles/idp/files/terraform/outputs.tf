output "netbird_client_id" {
  value = zitadel_application_oidc.netbird.client_id
  sensitive = true
}

output "netbird_client_secret" {
  value = zitadel_machine_user.netbird.client_secret
  sensitive = true
}