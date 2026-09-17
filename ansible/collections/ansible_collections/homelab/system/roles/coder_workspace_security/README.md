# Coder workspace node security

This role prepares a node for the non-privileged Coder Pod with Codex/bubblewrap
and rootless Podman. It does not install Kubernetes or deploy the workspace.
The Kubernetes cluster group enables `coder_workspace_security_enabled` on every
node so a workspace can be rescheduled safely.


## What each protection does

Linux capabilities split root privileges into individual operations. The outer
container's bounding set (the maximum it may acquire) contains only SETUID and
SETGID. The normal UID 1001 shell must have zero effective/permitted capabilities.
The root-owned UID helpers acquire only their respective file capability and
keep UID 1001, instead of becoming root through a setuid bit.

`allowPrivilegeEscalation: true` is necessary for those file capabilities. Setting
it false sets `no_new_privs`, disabling the helpers. To contain this exception,
the image removes sudo/setuid programs, Kubernetes fixes UID/GID 1001, drops the
other outer capabilities, and mounts the image read-only. The init container has
only CHOWN/FOWNER to prepare volume roots; it never recursively chowns stored data.

AppArmor enforces access rules in addition to normal Unix permissions:

| Profile | Purpose |
| --- | --- |
| `coder-workspace` | Ordinary commands; no userns, mount or pivot-root permission |
| `coder-workspace//coder-workspace-bwrap` | Create bwrap's sandbox; payloads inherit this profile after bwrap installs the sandbox mounts and drops capabilities |
| `coder-workspace//coder-workspace-podman` | Podman, mapping/networking helpers, OCI runtime and payloads inherit rootless-container confinement |

Child profiles do not inherit parent rules. The template loop repeats common
protections in each: system binaries/configuration, kernel interfaces, runtime
sockets and direct AppArmor relabelling. Only Podman's child permits network
sysctl writes; kernel NET_ADMIN checks still require a network namespace it owns.
There is no outer NET_ADMIN or SYS_ADMIN. AppArmor cannot grant kernel capabilities.

The Podman child necessarily runs user code, including `podman unshare`; it is not
a trusted-code-only boundary. PID/mount/user namespaces and the outer capability
limit remain essential. AppArmor peer names are shared by workspaces using this
profile; normal PID/user isolation still applies. Same-workspace debugging is
allowed, not isolation between mutually hostile users in one workspace.

Seccomp blocks selected kernel APIs even in new user namespaces: BPF, keyrings,
performance events, userfaultfd, io_uring, module/kexec operations and others.
Namespace/mount calls remain available. This is a **denylist**, not a full syscall
allowlist: new kernel APIs remain allowed unless added. The current filter covers
x86_64/x86/x32; the role rejects other architectures. Inner containers cannot undo
the outer seccomp filter, even if their own filter is disabled.

Podman uses native rootless overlay without a host FUSE device/socket. Inner
cgroup management is disabled because Kubernetes owns the outer cgroup.
`apparmor_profile="unconfined"` in the **inner Podman configuration** suppresses
an OCI request to load/switch another profile; the existing outer AppArmor label
is inherited. There is no `Ux` or `change_profile` permission. Verify inheritance
in a real child container after deployment. Inner Podman also sets
`keyring=false`, causing crun to retain the existing session keyring instead of
calling the outer policy's blocked `keyctl` syscall. The outer seccomp denylist
continues to block `add_key`, `request_key`, and `keyctl` for workspace and inner
container processes.

The Podman child permits ordinary writes throughout paths presented as an inner
container's overlay root. Generic images need this for package databases,
application files, writable mappings and file locks. This also gives the Podman
runtime AppArmor permission to write other visible paths, but it does not make
them writable: Kubernetes mounts the outer image read-only, and the only writable
outer filesystems are the intended home, workspace, ephemeral and temporary
volumes. Explicit AppArmor denials still cover `/proc` and `/sys` kernel surfaces,
sensitive devices, container-runtime sockets and Kubernetes credentials. The
workspace and bwrap profiles retain their system-path write restrictions.

The bwrap child likewise permits writes while Bubblewrap constructs its private
mount tree. Bubblewrap creates placeholder files such as `/dev/null` beneath that
staging root before mounting the sandbox filesystems. AppArmor may report these
using staging paths that do not match the final `/dev/**` rule. Bubblewrap sets
`no_new_privs`, installs the read-only/writable bind-mount boundary and drops
capabilities before exec. The payload inherits the bwrap profile; an AppArmor
`Px` transition is rejected under `no_new_privs` because the workspace profile
is not a strict subset. The outer read-only root and explicit sensitive-path
denials remain in force for the payload.

## Limits and compatibility

Rootless Pasta also needs TUN. The Coder application role installs the TUN-only
device plugin on every Kubernetes node and Terraform requests
`devic.es/coder-tun: 1`. This role loads/persists each node's TUN driver. The
plugin adds a trusted kubelet socket consumer; it does not change kubelet
configuration or grant the workspace host networking/NET_ADMIN. Apply the
`k8s-coder-tun` tag as well as
`k8s-coder-security`, then recreate the workspace after updating its template.
No image rebuild is needed. See troubleshooting section 7 for this later fix;
the checks recorded below predate it.

- This shares the node kernel; no AppArmor/seccomp profile guarantees protection
  against unknown kernel exploits. VM-backed isolation is stronger for hostile code.
- Outbound TCP/UDP remains available for development. This does not prevent data
  exfiltration or access to reachable LAN services; that needs a separate Cilium
  egress policy/proxy design. User credentials intentionally in the workspace
  remain accessible, although the Kubernetes API token is no longer mounted.
- Admission sets `hostUsers: false` and developer `procMount: Unmasked`.
  Kubernetes requires the former for the latter. Every node allocates 262144
  outer IDs, sufficient for existing subordinate IDs 100000 through 231071. The
  default 65536 would fail UID mapping. Kubernetes 1.34 accepted this setting but
  ignored it due to kubernetes/kubernetes#133144; use Kubernetes 1.35 or newer.
  PVC idmapped mounts preserve logical file IDs; do not recursively chown them.
  All current workspace volumes are ext4 and node2's runtime advertises
  user-namespace support. Runtime confirmation remains required. Do not bypass a
  volume/idmap error by exposing host paths.
- Rebuild for system/global npm package changes. Install project dependencies in
  home/workspace volumes. Inner images needing writes to `/etc` or `/usr`, FUSE,
  their own cgroups, keyrings, or io_uring without fallback may need adaptation.
- Podman started inside a Codex sandbox with `NoNewPrivs: 1` cannot acquire helper
  file capabilities. Test both separately first. Integration tests may need a
  narrowly approved command outside Codex's inner sandbox, still inside this
  protected Pod. Do not globally disable Codex sandboxing.

