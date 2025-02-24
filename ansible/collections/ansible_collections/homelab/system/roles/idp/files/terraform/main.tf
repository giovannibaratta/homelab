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

# Action to inject the Role into the attribute group of the token
resource "zitadel_action" "group_claim" {
  org_id          = data.zitadel_org.org.id
  name            = "groupsClaim"
  script          = file("${path.module}/files/group-claim-action.js")
  timeout         = "5s"
  allowed_to_fail = true
}

resource "zitadel_trigger_actions" "pre_userinfo_creation" {
  org_id       = data.zitadel_org.org.id
  flow_type    = "FLOW_TYPE_CUSTOMISE_TOKEN"
  trigger_type = "TRIGGER_TYPE_PRE_USERINFO_CREATION"
  action_ids   = [zitadel_action.group_claim.id]
}

resource "zitadel_trigger_actions" "pre_accesstoken_creation" {
  org_id       = data.zitadel_org.org.id
  flow_type    = "FLOW_TYPE_CUSTOMISE_TOKEN"
  trigger_type = "TRIGGER_TYPE_PRE_ACCESS_TOKEN_CREATION"
  action_ids   = [zitadel_action.group_claim.id]
}

### Netbird resources

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

  name                      = "netbird"
  redirect_uris             = ["https://netbird.${var.app_domain}/auth", "https://netbird.${var.app_domain}/silent-auth", "http://localhost:53000"]
  response_types            = ["OIDC_RESPONSE_TYPE_CODE"]
  grant_types               = ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN", "OIDC_GRANT_TYPE_DEVICE_CODE"]
  post_logout_redirect_uris = ["https://netbird.${var.app_domain}"]
  app_type                  = "OIDC_APP_TYPE_USER_AGENT"
  auth_method_type          = "OIDC_AUTH_METHOD_TYPE_NONE"
  version                   = "OIDC_VERSION_1_0"
  clock_skew                = "0s"
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


### Coder resources

resource "zitadel_project" "coder" {
  name   = "coder"
  org_id = data.zitadel_org.org.id
  # This is needed to allow the group claim action to work.connection {
  # If set to false, no grants will be available in the context
  project_role_assertion   = true
  project_role_check       = false
  has_project_check        = false
  private_labeling_setting = "PRIVATE_LABELING_SETTING_ENFORCE_PROJECT_RESOURCE_OWNER_POLICY"
}

resource "zitadel_application_oidc" "coder" {
  project_id = zitadel_project.coder.id
  org_id     = data.zitadel_org.org.id

  name                        = "coder"
  redirect_uris               = ["https://coder.${var.app_domain}/api/v2/users/oidc/callback"]
  response_types              = ["OIDC_RESPONSE_TYPE_CODE"]
  grant_types                 = ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN", "OIDC_GRANT_TYPE_DEVICE_CODE"]
  post_logout_redirect_uris   = ["https://coder.${var.app_domain}"]
  app_type                    = "OIDC_APP_TYPE_WEB"
  auth_method_type            = "OIDC_AUTH_METHOD_TYPE_BASIC"
  version                     = "OIDC_VERSION_1_0"
  clock_skew                  = "0s"
  dev_mode                    = false
  access_token_type           = "OIDC_TOKEN_TYPE_JWT"
  access_token_role_assertion = true
  id_token_role_assertion     = false
  id_token_userinfo_assertion = false
  additional_origins          = []
}

resource "zitadel_project_role" "admin" {
  org_id       = data.zitadel_org.org.id
  project_id   = zitadel_project.coder.id
  role_key     = "admin"
  display_name = "Admin"
  group        = "admin"
}
