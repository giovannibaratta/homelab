# VPN role: commercial VPN client

This document describes the role's commercial VPN client, implemented with
Gluetun. It supports Proton VPN and NordVPN over WireGuard or OpenVPN. The role
also contains NetBird components; the commercial-client settings below do not
configure or disable them.

## Inputs

Supply these as ordinary Ansible variables. The role reads credential values
from those variables; it does not retrieve them from a secret store.

| Variable | Default | Meaning |
| --- | --- | --- |
| `vpn_deploy_client` | `true` | Deploy/start the client; `false` stops and removes its service definitions. |
| `vpn_service_provider` | Required when enabled | `protonvpn` or `nordvpn`. |
| `vpn_client_type` | `wireguard` | `wireguard` or `openvpn`. |
| `vpn_server_countries` | `[Italy]` | List of eligible countries. |
| `vpn_server_hostnames` | `[]` | Optional list of specific server hostnames. |
| `vpn_server_refresh_enabled` | `true` for NordVPN, `false` otherwise | Refresh stale server data before tunnel startup. Currently supports NordVPN only. |
| `vpn_server_refresh_max_age_days` | `15` | Positive integer: maximum age of the last successful refresh. |
| `vpn_server_refresh_force` | `false` | Force a refresh on this run; requires refresh enabled. |
| `vpn_openvpn_protocol` | `udp` | OpenVPN transport: `udp` or `tcp`; not rendered for WireGuard. |
| `vpn_client_version` | `v3.41.1` | Gluetun image tag. |
| `vpn_client_container_user` | `gluetun` | Host account owning the client configuration. |
| `vpn_client_conf_dir` | `/app/gluetun/conf` | Persistent host directory for the generated environment and Gluetun state. |
| `podman_dns` | Required when enabled | List of DNS server addresses for the client bridge network. |

The target must provide Podman with Quadlet support, systemd, and
`/dev/net/tun`. The client receives `NET_ADMIN` to create its tunnel and firewall;
this role does not install Podman. It creates the host account, configuration
directory, network and container service definitions.

Countries and hostnames must be lists of strings without commas or newlines.
Empty lists omit the corresponding filter. No particular server hostname is
required. Explicit country and hostname filters must be compatible with each
other. The role validates their format; Gluetun validates whether matching
servers exist. A hostname that disappears from the provider's server list can
prevent reconnection until the input is updated.

## Credentials

Only the selected provider and protocol require credentials:

| Provider / protocol | Required variables |
| --- | --- |
| Proton / WireGuard | `vpn_protonvpn_wireguard_privatekey` |
| Nord / WireGuard | `vpn_nordvpn_wireguard_privatekey` |
| Proton / OpenVPN | `vpn_protonvpn_openvpn_user`, `vpn_protonvpn_openvpn_password` |
| Nord / OpenVPN | `vpn_nordvpn_openvpn_user`, `vpn_nordvpn_openvpn_password` |

A WireGuard private key must be a 44-character base64-encoded 32-byte key issued
for the selected provider. Keys cannot be reused across providers. OpenVPN
requires the provider's manual-connection/service credentials, which may differ
from the normal account login. Usernames and passwords must be nonempty strings
without carriage returns or newlines. Do not include surrounding literal quotes
in credential values.

The template constructs the variable name from the provider. For example,
`vpn_service_provider: nordvpn` with WireGuard reads
`vpn_nordvpn_wireguard_privatekey`. It renders only that protocol's credentials.
Unused provider credentials do not need to be defined.

Credential validation, environment rendering and container-inspection output
are hidden with `no_log`. Environment-file diffs are disabled, and the generated
`gluetun.env` file has mode `0600`. Keep actual credentials out of committed
configuration files.

## Examples

Proton VPN with WireGuard; supply `vpn_protonvpn_wireguard_privatekey` separately:

```yaml
vpn_deploy_client: true
vpn_service_provider: protonvpn
vpn_client_type: wireguard
vpn_server_countries: [Italy]
podman_dns: [192.168.1.1] # Replace with a reachable DNS server.
```

NordVPN with OpenVPN; supply `vpn_nordvpn_openvpn_user` and
`vpn_nordvpn_openvpn_password` separately:

```yaml
vpn_deploy_client: true
vpn_service_provider: nordvpn
vpn_client_type: openvpn
vpn_openvpn_protocol: udp
vpn_server_countries: [Italy]
podman_dns: [192.168.1.1] # Replace with a reachable DNS server.
```

For NordVPN with WireGuard, use `vpn_client_type: wireguard` and supply
`vpn_nordvpn_wireguard_privatekey` instead of OpenVPN credentials.

## Applications sharing the tunnel

A consumer container can use `network: container:gluetun`. Its systemd unit
should include:

```ini
[Unit]
Requires=gluetun.service
After=gluetun.service
PartOf=gluetun.service
```

These dependencies order startup and propagate VPN service stops/restarts.
They do not wait for VPN health; Gluetun's firewall controls tunnel traffic.
Apply consumer network/unit changes together with changes to the VPN resource
names. Stopping the required VPN service can stop its consumers. The role does
not create, reconfigure or start consumer applications.

## Inbound port forwarding

The environment explicitly sets `VPN_PORT_FORWARDING=off`. The role does not
publish host ports, allocate provider-side inbound mappings or synchronize an
application's listening port with a dynamically allocated port. Changing the
provider does not enable forwarding. A listening application port alone does
not create an inbound mapping through the VPN provider.

Outbound-initiated connections can work without an inbound mapping. Supporting
provider-side forwarding requires additional configuration and application port
synchronization; it is not implemented by this role.

## Server catalogue refresh

For NordVPN, deployment runs the pinned image's `update -enduser -providers
nordvpn` command when `servers.json` or the provider success marker is missing,
when the last successful refresh is at least 15 days old, or when
`vpn_server_refresh_force: true` is supplied. This runs before tunnel startup and
before the client restart handlers. It uses host networking so a broken tunnel cannot
prevent repair. It contacts the provider outside the VPN and requires working
host connectivity/DNS. The temporary container receives no VPN credentials,
capabilities or tunnel device; it runs as the configuration directory owner.

The updater has a five-minute timeout. A failed update stops deployment and does
not advance the success marker. Successful updates restart Gluetun only if the
persisted catalogue checksum changed. A normal run with a fresh marker performs
no update; check mode reports a pending refresh without downloading anything.
There is no timer: the age is evaluated when Ansible runs. Disable this behavior
with `vpn_server_refresh_enabled: false` if the catalogue is managed separately.
Proton refresh is not implemented because its updater additionally requires
account credentials, distinct from the tunnel credentials.

Refreshing cannot guarantee that a hostname offered by NordVPN exists in
Gluetun's catalogue. If startup still rejects a hostname, choose an available
entry or clear `vpn_server_hostnames` to select by country.
