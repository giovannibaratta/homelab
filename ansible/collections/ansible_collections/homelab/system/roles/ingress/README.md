# Ingress

This role deploys Traefik as the entry point for homelab services running in
Podman and Kubernetes. It provides HTTPS routing, certificate management,
request filtering, and an authenticated administration dashboard.

The role also deploys the web application firewall (WAF) and, when configured,
an OAuth2 Proxy for dashboard authentication through an OpenID Connect identity
provider.

## Expose services

Podman services declare their routes through Traefik container labels.
Kubernetes services are routed through the cluster ingress using
`k8s_internal_routes` (LAN) and `k8s_public_routes` (WAN and LAN) in inventory.

Keys are DNS prefixes, suffixed with `internal_domain`:

```yaml
k8s_public_routes:
  approvio:
  idp:
k8s_internal_routes:
  git:
  overseerr:
    enabled: "{{ deploy_seerr }}"
```

Empty entries are enabled by default; conditional entries specify `enabled`.
`enabled` defaults to true and is interpreted as a boolean.

Provide DNS records and the certificate-provider credentials required by the
homelab deployment. Adding an entry to `k8s_public_routes` exposes that route publicly.

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

Set `ingress_traefik_enable_dhi: true` for a host to opt into Docker
Hardened Traefik. Configure Podman credentials for `dhi.io` first. See [defaults/main.yaml](defaults/main.yaml) for OAuth2
Proxy and WAF version settings.

Apply ingress changes through the homelab deployment workflow using the `ingress`
tag. That workflow also reads the published authentication credentials.
