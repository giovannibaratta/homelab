variable "zitadel_instance" {
  type = object({
    host = string
    port = number
    jwt_json = string
  })
}

variable "app_domain" {
  description = "Domain of the application"
}

