# Ingress

This role deploys Traefik as the entry point for homelab services running in
Podman and Kubernetes. It provides HTTPS routing, certificate management,
request filtering, and an authenticated administration dashboard.

The role also deploys the web application firewall (WAF) and, when configured,
an OAuth2 Proxy for dashboard authentication through an OpenID Connect identity
provider.

## Expose services

Podman services declare their routes through Traefik container labels.
Kubernetes services are routed through the cluster ingress using these inventory
lists:

| Variable | Purpose |
| --- | --- |
| `k8s_public_domains` | Domains accessible through the public HTTPS entry point |
| `k8s_internal_domains` | Domains accessible through the internal HTTPS entry point |

Provide DNS records and the certificate-provider credentials required by the
homelab deployment. Internal services should use the internal domain list;
adding a service to the public list exposes its route publicly.

Public web routes use `default-chain@file` for rate limiting, concurrent-request
limiting, and WAF inspection. Apply security policies to individual routes.
Services such as streaming or gRPC applications may need a compatible policy
that omits WAF inspection; avoid applying WAF middleware globally to the shared
public entry point.

## Dashboard access

The dashboard is available in two ways:

- Locally at `http://127.0.0.1:8080/dashboard/`, including through an SSH tunnel.
- On the LAN at
  `https://traefik-<inventory_hostname>.<internal_domain>:8443/dashboard/`,
  with source-network restrictions and identity-provider authentication.

The dashboard has no public route. LAN access requires a reachable identity
provider, valid client credentials, an allowed email address, and working DNS.
Missing authentication configuration leaves only local dashboard access.

| Variable | Purpose | Default |
| --- | --- | --- |
| `deploy_ingress_auth` | Enable dashboard authentication when its configuration is complete | `true` |
| `ingress_auth_issuer_url` | Identity provider's issuer URL | `https://idp.{{ internal_domain }}` |
| `ingress_auth_client_id` | OIDC client ID | Empty |
| `ingress_auth_client_secret` | OIDC client secret | Empty |
| `ingress_auth_allowed_emails` | Administrator email addresses allowed to log in | Empty list |

The homelab playbook supplies client credentials from published identity-provider
outputs and maps the secret-bundle variable `ingress_allowed_emails` to the
role's email list. For example:

```yaml
ingress_allowed_emails: "administrator@example.org, another-admin@example.org"
```

On a fresh installation, authenticated LAN access may require a second deployment
after the identity provider publishes its client credentials. Standalone callers
must supply the role's authentication inputs and register the dashboard callback
URLs with their identity provider.

An identity-provider outage can prevent dashboard logins; it does not remove
local dashboard access or make unrelated application routes depend on login.

## Request protection

The main tuning options are:

| Variable | Purpose | Default |
| --- | --- | --- |
| `ingress_waf_rule_engine` | `On` to enforce, `DetectionOnly` to log, or `Off` | `On` |
| `ingress_waf_paranoia_level` | WAF strictness, from 1 to 4 | `1` |
| `ingress_waf_anomaly_inbound` | Inbound anomaly threshold for blocking | `10` |
| `ingress_waf_anomaly_outbound` | Outbound anomaly threshold for blocking | `5` |
| `ingress_waf_rate_limit_average` | Average requests per client IP per period | `50` |
| `ingress_waf_rate_limit_period` | Rate-limit period | `1s` |
| `ingress_waf_rate_limit_burst` | Allowed request burst | `100` |
| `ingress_waf_inflight_limit` | Concurrent requests allowed per client IP | `50` |

Higher paranoia levels and lower thresholds can increase false positives.
Clients sharing a NAT address share the limits seen for that address.

## Monitoring and versions

Set `ingress_traefik_metrics_enabled: true` to expose Prometheus metrics on the
host's internal address. `ingress_traefik_metrics_port` defaults to `8082`.
This endpoint is unauthenticated, so keep it restricted to the trusted monitoring
network. Prometheus scraping is configured separately.

`ingress_traefik_version`, `ingress_auth_version`, and `ingress_waf_version`
select the component versions. See [defaults/main.yaml](defaults/main.yaml) for
all options and current defaults.

Apply ingress changes through the homelab deployment workflow using the `ingress`
tag. That workflow also reads the published authentication credentials.
