# Homelab Troubleshooting & Known Issues

## 1. SSH `No route to host` from IDE Terminal on macOS Sequoia

### Symptom
Running `ssh ansible@<node-ip>` from Antigravity IDE terminal fails with `ssh: connect to host <node-ip> port 22: No route to host`, while `ssh` from standalone iTerm2 succeeds. `ping <node-ip>` from CLI task runner fails with `ping: sendto: No route to host`.

### Root Cause
macOS Sequoia (15.x+) introduced **Local Network Privacy**. If the parent IDE / CLI process is not granted Local Network permission, macOS silently drops ARP queries and outbound socket connections to local subnet IPs for child processes, returning `EHOSTUNREACH`.

### Resolution
1. Open **System Settings** → **Privacy & Security** → **Local Network**.
2. Enable access for **Antigravity** / **Antigravity IDE** / **node**.
3. If not listed, reset Local Network privacy rules to trigger prompt:
   ```bash
   tccutil reset LocalNetwork
   ```
4. Restart the IDE.

## 2. Rootless Podman Compose Bridge WAN Data Stall (Outdated Pasta)

### Symptom
When running `podman-compose` in a rootless development workspace, child containers on custom Netavark bridge networks (`driver: bridge`) can resolve DNS and establish TCP 3-way handshakes, but outbound WAN data transfer stalls (e.g. HTTPS requests hang indefinitely immediately after sending the TLS `ClientHello`). In contrast, containers on the default rootless network or running with `network_mode: host` work fine.

### Root Cause
Ubuntu 24.04 LTS (Noble) universe repositories ship an outdated version of `passt`/`pasta` (`0.0~git20240220.1e6f92b-1`). Podman 5.8+ and Netavark 1.17+ route rootless forwarded/NATed bridge traffic through `pasta`, but the old `pasta` version mishandles inbound return packets on forwarded bridge networks.

### Resolution
Upgrade `passt`/`pasta` to the latest upstream release (`0.0+20260728.f8df3f1b` or newer) by compiling from source in the container image:
```bash
git clone --depth 1 git://passt.top/passt /tmp/passt
make -C /tmp/passt prefix=/usr install
rm -rf /tmp/passt
```
Restart rootless Podman processes to spawn the new `pasta` binary.

