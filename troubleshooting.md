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

## 3. UPS Monitor `Data stale` / USB `Overflow (-8)` on Cypress 0665:5161

### Symptom
`upsc <ups-name>` fails with `Init SSL without certificate database: Error: Data stale`, `nut-monitor` logs `Poll UPS failed - Data stale`, and Prometheus `nut_ups_load` shows gaps/blanks. Manually testing `nutdrv_qx` reports `read: Overflow (-8)` and `Device not supported!`.

### Root Cause
Tecnoware / Cypress `0665:5161` is a USB 1.1 Low-Speed (1.5 Mbps) controller. When host systems reboot or when the USB device is hot-plugged across xHCI (USB 3.x) ports, the internal FIFO buffer on the Cypress chip or xHCI transaction translator can lock up in a persistent overflow state, causing `libusb` reads to fail with `LIBUSB_ERROR_OVERFLOW (-8)`.

### Resolution
1. **Remote USB Reset via Sysfs (without physical access)**:
   ```bash
   echo 0 | sudo tee /sys/bus/usb/devices/1-5/authorized
   sleep 2
   echo 1 | sudo tee /sys/bus/usb/devices/1-5/authorized
   ```
   Or using `usbreset`:
   ```bash
   sudo usbreset 0665:5161
   ```
2. **Restart NUT services**:
   ```bash
   sudo systemctl restart nut-driver@tecnoware nut-server nut-monitor
   ```
3. **Verify**:
   ```bash
   upsc tecnoware
   cat /var/lib/node_exporter/textfile_collector/nut.prom
   ```

## 4. Diagnosing commands blocked in a Coder/Codex sandbox

Use this process before changing AppArmor, seccomp, capabilities, mounts or the
Pod security context. `EPERM` and `EACCES` only describe the result; several
independent layers can return them.

### Reproduce without a model request

Run the smallest equivalent command directly in the workspace and then through
Codex's sandbox subcommand. `codex sandbox` does not call a model or consume
model tokens.

```bash
cd /workspace/approvio
sed -n '1p' docs/ADR/003-auditing-system.md
codex sandbox -P workspace-write -C "$PWD" -- \
  sed -n '1p' docs/ADR/003-auditing-system.md
```

- If only the second command fails, inspect bwrap setup, the bwrap AppArmor
  child and Codex's mount policy.
- If both fail, inspect the outer workspace profile, Kubernetes mounts,
  ownership, capabilities and seccomp.
- If sandbox creation succeeds but a particular program fails, reduce it to the
  failing syscall or file path. Keep the complete error and exit status.

`/bin/true` is the quickest sandbox-construction and exec smoke test:

```bash
codex sandbox -P workspace-write -C "$PWD" -- /bin/true
```

### Record the process and filesystem context

These read-only checks identify the active policy and common kernel boundaries:

```bash
cat /proc/self/attr/current
grep -E 'NoNewPrivs|Seccomp|Cap(Inh|Prm|Eff|Bnd|Amb)' /proc/self/status
cat /proc/self/uid_map /proc/self/gid_map
id
findmnt -T /path/that/failed -o TARGET,SOURCE,FSTYPE,OPTIONS
namei -l /path/that/failed
stat -Lc '%F %a %u:%g %t:%T %n' /path/that/failed
```

When the sandbox can execute commands, run the relevant checks both directly and
under `codex sandbox`. A sandbox payload should report
`coder-workspace//coder-workspace-bwrap (enforce)`; an inner Podman payload should
report `coder-workspace//coder-workspace-podman (enforce)`.

### Read the node audit evidence

AppArmor decisions are made by the node kernel, not inside the container. Query
the node through the repository's read-only Ansible workflow immediately after a
reproduction:

```bash
cd ansible
.venv/bin/ansible node2 -i inventory/home.yaml -b \
  -m ansible.builtin.shell \
  -a "journalctl -k --since '-5 minutes' --no-pager | \
      grep 'apparmor=\"DENIED\"' | tail -n 100"
```

Correlate the timestamp, `pid`, `comm`, profile and failed program. The useful
fields are:

- `profile`: which template branch needs examination: workspace, bwrap or
  Podman.
- `operation` and `class`: file access, exec, capability, mount, signal or
  ptrace.
- `name` and `requested_mask`: the mediated path and requested permissions.
- `info="no new privs"`: an AppArmor domain transition was rejected after
  `no_new_privs`; adding file permissions will not fix it.
- `capname`: AppArmor rejected a capability operation. An AppArmor allow cannot
  add a capability missing from the process or outer bounding set.

An explicit AppArmor `deny` can suppress its own audit message. If evidence
strongly identifies a candidate deny rule, temporarily make only that rule
auditable, reproduce once, and restore quiet enforcement after diagnosis. Do not
put the complete workspace profile into complain mode.

### Distinguish the enforcing layer

| Evidence | Likely layer | Direction |
| --- | --- | --- |
| Matching `apparmor="DENIED"` record | AppArmor | Change the exact profile, operation and path; retain explicit sensitive-path denials. |
| `info="no new privs"` on `operation="exec"` | AppArmor transition | Use an inheriting or demonstrably more restrictive transition; do not disable `no_new_privs`. |
| `EPERM` on a syscall named in `coder-workspace-seccomp.json`, with no AppArmor record | Seccomp | Prefer configuring the program not to use it; remove a syscall from the denylist only after assessing its use inside new user namespaces. |
| `EROFS`, or `findmnt` reports `ro` | Kubernetes/bwrap VFS mount | Change the intended mount layout or writable volume. AppArmor and capabilities cannot override a read-only mount. |
| `EACCES` with restrictive ownership or mode from `namei`/`stat` | Unix DAC or user mapping | Correct ownership at the mount root or the UID/GID mapping; do not recursively chown persisted Podman storage. |
| Capability absent from `CapBnd` | Kubernetes capability bounding set | First verify the operation is necessary. AppArmor cannot restore a capability removed by Kubernetes. |
| UID/GID range missing from `uid_map` or `gid_map` | Kubernetes user namespace allocation | Fix kubelet `idsPerPod` and recreate user-namespaced Pods; AppArmor is unrelated. |
| Device exists but open/ioctl fails without AppArmor evidence | Device cgroup, device plugin or ioctl policy | Verify the Pod resource allocation and device major/minor; do not replace it with a broad hostPath or privileged mode. |
| Binary/configuration missing, incompatible or on a `noexec` mount | Image or mount construction | Fix the image or mount. A security-policy allow cannot supply a missing executable. |

The seccomp profile uses `SCMP_ACT_ERRNO`, so its expected denials usually return
`EPERM` without a kernel audit entry. When the failing syscall is unknown, use a
minimal `strace` if it is already available:

```bash
strace -f -e trace=process,file,mount,network,ipc,ioctl <minimal-command>
```

Trace the smallest reproducer and compare its failing syscall with
`ansible/collections/ansible_collections/homelab/system/roles/coder_workspace_security/files/coder-workspace-seccomp.json`.
Absence of an AppArmor message alone is not proof of a seccomp failure.

### Choose the smallest fix and rollout

Prefer a program configuration that avoids an unnecessary privileged operation,
such as disabling per-container keyrings, over weakening an outer policy. When a
policy change is required, limit it to the affected child profile and preserve
the existing user namespace, read-only outer root, capability bounding set,
sensitive-path denials and lack of host mounts.

| Changed layer | Repository owner | Required rollout |
| --- | --- | --- |
| AppArmor | `coder_workspace_security/templates/coder-workspace.apparmor.j2` | Apply `k8s-coder-security` to every Kubernetes node. The role validates then replaces the live profile; normally no Pod recreation is needed. |
| Seccomp | `coder_workspace_security/files/coder-workspace-seccomp.json` | Apply `k8s-coder-security`, then recreate the workspace Pod because seccomp filters attach at container creation. |
| Pod security context, volumes or devices | Coder Terraform and `homelab.apps.k8s_coder` | Apply the owning Kubernetes/Coder configuration and recreate the workspace Pod. |
| Image package or global configuration | `coder/templates/k8s-dev-env/build/Dockerfile` | Bump the image tag, build/publish it and recreate the workspace. |
| Kubelet user-namespace allocation | Kubespray inventory | Stop user-namespaced Pods, apply the cluster change to every node, verify kubelet `/configz`, then recreate the Pods. |

After the positive reproducer succeeds, rerun a negative check proving that the
boundary still blocks an adjacent forbidden operation. Record the exact error,
audit evidence, minimal fix, security tradeoff and deployment requirement in this
file. A successful application command alone does not validate the sandbox.
