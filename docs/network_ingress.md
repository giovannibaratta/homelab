# Homelab Network & Ingress Architecture

This document outlines the architecture of the homelab networking setup and how external traffic is routed to both standalone Podman containers and Kubernetes workflows.

## 1. Firewall and NAT (nftables)
The primary firewall and NAT layer is managed by `nftables` running directly on the router nodes.
- **External Traffic (`ftth` interface)**: All traffic arriving from the WAN interface on ports `80` (HTTP) and `443` (HTTPS) is explicitly DNAT'ed to internal ports `9080` and `9443` on the host (`internal_ip_address`). 
- No firewall rules route traffic directly to the Kubernetes virtual network. All external traffic must pass through the host ingress layer first.

## 2. External Gateway (Traefik on Podman)
A primary Traefik instance runs as a Podman quadlet directly on the host using host networking (`network: host`). This serves as the single entry point for all external web traffic.
- **Listeners**: It listens on the internal DNAT ports (`:9080` for `public-insecure` and `:9443` for `public-secure`).
- **TLS Termination**: It acts as the TLS terminator for the entire network, automatically handling Let's Encrypt SSL certificates
- **Security & WAF**: All public entrypoints have a strict 3-layer security middleware chain configured: 
  1. Rate Limiting
  2. In-flight request limiting
  3. OWASP ModSecurity WAF (via an experimental Traefik plugin)
- **Podman Workload Discovery**: It connects to a secure, read-only Docker Socket Proxy to automatically discover and route to existing Podman/Docker workloads running on the host.

## 3. Kubernetes Networking
Kubernetes is deployed via Kubespray, utilizing Cilium as the primary CNI.
- **Kube-Proxy**: Removed (`kube_proxy_remove: true`) to prevent iptables/nftables interference with the host's Podman setup.
- **Load Balancer**: MetalLB and Kubespray's NGINX ingress are disabled. Instead, Cilium's native L2 Announcement Policy (`CiliumL2AnnouncementPolicy`) is used to broadcast LoadBalancer IPs.
- **IP Allocation**: Cilium provisions IP addresses for `LoadBalancer` type services from the `172.16.184.0/24` network pool (`k8s_lb_network`).

## 4. Hybrid Routing (External Traefik to Kubernetes)
To expose Kubernetes workflows to the internet without duplicating TLS configurations or bypassing the WAF, a hybrid routing model is used:
1. **Internal Ingress**: A lightweight Ingress Controller runs inside the Kubernetes cluster, exposed via a `LoadBalancer` service with a statically assigned IP from the Cilium pool (e.g., `172.16.184.10`).
2. **Bridge Configuration**: The External Traefik gateway uses a static File Provider configuration to define `routers` for specific Kubernetes-hosted domains.
3. **Traffic Flow**: 
   - External Traefik receives the HTTPS request, performs WAF inspection, and decrypts the TLS payload.
   - It forwards the request as plain HTTP to the internal Kubernetes Ingress Controller (`http://172.16.184.10:80`).
   - The internal Ingress Controller reads the `Host` header and routes the traffic to the corresponding Kubernetes pod natively.
