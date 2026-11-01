# Host networking

This role configures the homelab's host networking using NetworkManager. It
sets up the LAN bridge and static host address, firewall rules, SSH access
restrictions, and the dedicated Kubernetes network.

Router hosts additionally support the internet connection, DHCP, dynamic DNS,
and a shared gateway address with automatic failover. The role follows the
homelab's network layout; it is not a general-purpose network configuration role.

## Choose the host's role

| Variable | Purpose | Default |
| --- | --- | --- |
| `network_is_router` | Enable internet gateway functionality | `false` |
| `network_gateway_role` | Preferred (`primary`) or backup (`secondary`) gateway | Unset |
| `network_dhcp_role` | DHCP failover role: `primary` or `secondary` | Unset |

All hosts receive the LAN bridge, including hosts that are not routers. Non-router
hosts use `internal_gateway` for outbound traffic. Router hosts establish their
own internet connection.

Set `network_gateway_role` only on routers participating in gateway failover.
A router without this setting does not participate in VRRP. Set
`network_dhcp_role` only on routers that should provide DHCP; otherwise the role
disables the DHCP service.

## LAN and SSH access

The main host and shared-network settings are:

| Variable | Purpose |
| --- | --- |
| `internal_interface` | Physical interface connected to the LAN |
| `bridge_name` | LAN bridge interface name |
| `internal_ip` | Host's static LAN address |
| `internal_gateway` | Shared default gateway address |
| `internal_network` | LAN network address |
| `internal_network_netmask` / `internal_network_netmask_length` | LAN subnet mask and prefix length |
| `network_ssh_allowed_sources` | Non-empty list of addresses or CIDRs permitted to connect over SSH |

For example, a host can restrict SSH access to its management network:

```yaml
network_is_router: false
internal_interface: eth0
internal_ip: 172.16.255.10
network_ssh_allowed_sources:
  - 172.16.0.0/16
```

The example assumes the remaining shared network settings are supplied by
inventory. Reserve static addresses outside the DHCP allocation range and include
the controller's source address in the SSH allowlist.

## Router services

Internet access uses PPPoE with `pppoe_username` and `pppoe_password`. The current
connection layout assumes the homelab's ISP VLAN and bridge arrangement.

DHCP uses `internal_network_dhcp_start` and `internal_network_dhcp_end` for its
allocation range. `dhcp_primary` and `dhcp_failover` identify the paired DHCP
servers. Clients receive the configured `internal_gateway` as their router.

Gateway failover uses `network_vrrp_auth_pass` and `vrrp_virtual_router_id`
(default `90`). Participating routers must share the appropriate failover
configuration. Dynamic DNS is also configured for router hosts using the
homelab's provider credentials.

## Kubernetes networking

Set a unique `network_k8s_ip` on each node. Shared settings including
`k8s_cp_network`, `k8s_cp_netmask`, `k8s_lb_network`, and
`kube_service_addresses` define the node, load-balancer, and service networks.
The role configures the host interfaces and routing needed by that layout;
Kubernetes itself is deployed separately.

## Applying changes

Changing interfaces, addresses, SSH permissions, or firewall rules can interrupt
the current connection. Keep console access available for the initial deployment
or a network layout change. The role reconnects after restarting NetworkManager
and checks that the intended bridge address is present.

See [defaults/main.yaml](defaults/main.yaml) for role defaults. Host addresses,
shared network settings, and provider credentials come from inventory and secret
configuration.
