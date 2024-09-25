data "zitadel_orgs" "orgs" {
  state = "ORG_STATE_ACTIVE"

  lifecycle {
    postcondition {
      condition     = length(self.ids) > 0
      error_message = "There are no active orgs"
    }
  }
}

data "zitadel_org" "org" {
  id = data.zitadel_orgs.orgs.ids[0]
}

resource "zitadel_project" "netbird" {
  name                     = "netbird"
  org_id                   = data.zitadel_org.org.id
  project_role_assertion   = false
  project_role_check       = false
  has_project_check        = false
  private_labeling_setting = "PRIVATE_LABELING_SETTING_ENFORCE_PROJECT_RESOURCE_OWNER_POLICY"
}

resource "zitadel_application_oidc" "netbird" {
  project_id = zitadel_project.netbird.id
  org_id     = data.zitadel_org.org.id

  name                        = "netbird"
  redirect_uris               = ["https://netbird.${var.app_domain}/auth", "https://netbird.${var.app_domain}/silent-auth", "http://localhost:53000"]
  response_types              = ["OIDC_RESPONSE_TYPE_CODE"]
  grant_types                 = ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN", "OIDC_GRANT_TYPE_DEVICE_CODE"]
  post_logout_redirect_uris   = ["https://netbird.${var.app_domain}"]
  app_type                    = "OIDC_APP_TYPE_USER_AGENT"
  auth_method_type            = "OIDC_AUTH_METHOD_TYPE_NONE"
  version                     = "OIDC_VERSION_1_0"
  clock_skew                  = "0s"
  # Dev mode is needed to use the redict localhost:5300
  dev_mode                    = true
  access_token_type           = "OIDC_TOKEN_TYPE_JWT"
  access_token_role_assertion = true
  id_token_role_assertion     = false
  id_token_userinfo_assertion = false
  additional_origins          = []
}

resource "zitadel_machine_user" "netbird" {
  org_id            = data.zitadel_org.org.id
  user_name         = "netbird"
  name              = "netbird"
  description       = "Netbird Service User"
  with_secret       = true
  access_token_type = "ACCESS_TOKEN_TYPE_JWT"
}

resource "zitadel_org_member" "netbird_machine_user_binding" {
  org_id  = data.zitadel_org.org.id
  user_id = zitadel_machine_user.netbird.id
  roles   = ["ORG_USER_MANAGER"]
}
