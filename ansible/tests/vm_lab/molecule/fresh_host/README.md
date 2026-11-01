# Fresh host rehearsal

This Molecule scenario provisions a disposable Ubuntu 24.04 ARM VM on an Apple
Silicon Mac and applies the real `setup_homelab.yaml` playbook. Use it to check
fresh-host provisioning and compatibility between host roles.

The guest is defined in [inventory.yml](inventory.yml), separate from production
host definitions. It uses the shared settings, peer information, and credentials
from `ansible/inventory/home.yaml`. Only `fresh-host` is targeted by host setup.
Kubernetes installation is not included. The scenario skips Kubernetes
application roles and ingress certificate automation, as listed in
[molecule.yml](molecule.yml), to avoid changing shared DNS records.

## Prerequisites

Run the following from the repository root:

```bash
brew install qemu python@3.13
python3.13 -m venv .venv-lab
.venv-lab/bin/python -m pip install -r ansible/tests/vm_lab/requirements.txt
```

Install the repository's Ansible collections if they are not already available:

```bash
.venv-lab/bin/ansible-galaxy collection install ansible/collections/ansible_collections/homelab/utils
.venv-lab/bin/ansible-galaxy collection install ansible/collections/ansible_collections/homelab/system
.venv-lab/bin/ansible-galaxy collection install -r ansible/collections/ansible_collections/homelab/system/requirements.yml
.venv-lab/bin/ansible-galaxy collection install ansible/collections/ansible_collections/homelab/apps --upgrade
```

The gateway VM provides DNS, internet access through QEMU NAT, and SSH access to
fresh-host through localhost port `22221`. The target has no physical LAN bridge;
it works over Wi-Fi, Ethernet, or a remote connection without NetBird or sudo.
The private guest addresses live only inside the lab and do not need a home DHCP
reservation. The gateway blocks forwarding to private WAN networks, including
the real home LAN. Public services are still reachable.

Provide the normal homelab controller credentials, including `BWS_ACCESS_TOKEN`,
in the terminal running Molecule. The deployment still loads shared settings and
secrets from the real inventory, so this is a manual integration rehearsal,
not a completely self-contained application environment. It does not prove
physical LAN connectivity or Kubernetes cluster integration.

Router services and scheduled auto-Ansible are disabled on the target. Review
`variables.yml` and the skipped tags in `molecule.yml` before extending coverage.

## Run the scenario

In the terminal with your controller credentials, from the repository root:

```bash
bash ansible/tests/vm_lab/run.sh test -s fresh_host
```

This creates a fresh VM, deploys the host configuration, verifies it (including a
reboot), and stops the VM. Verification checks bridge and node addresses, Podman,
Terraform, DNS, and external HTTPS access.

To leave the VM running after deployment for inspection:

```bash
bash ansible/tests/vm_lab/run.sh converge -s fresh_host
bash ansible/tests/vm_lab/run.sh verify -s fresh_host
```

`converge` creates guests if Molecule has no existing instances; otherwise it
reuses them. The create playbook resets both guest disks when it executes.
Use `test` for a clean installation rehearsal and repeat `converge` to check an
existing installation. `verify` checks the guests without recreating them.

VM disks, keys, and console logs are stored under
`ansible/.ansible/vm-lab/fresh_host/`. The shared downloaded Ubuntu image is kept
under `ansible/.ansible/vm-lab/`.

## Stop and clean up

Stop both guests with:

```bash
bash ansible/tests/vm_lab/run.sh destroy -s fresh_host
```

Destroy stops the target before the gateway and retains files for inspection.
The next create step replaces both guest disks. To reclaim their files, remove
`ansible/.ansible/vm-lab/fresh_host/` only after stopping both guests.

To inspect a running target from the repository root:

```bash
ssh -F ansible/.ansible/vm-lab/fresh_host/ssh_config target
```
