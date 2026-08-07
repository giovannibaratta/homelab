---
name: ansible-nodes
description: Access remote nodes and execute read-only diagnostic or query commands via Ansible.
---

# Ansible Nodes Skill

Use this skill when you need to inspect, query, or run read-only diagnostic commands on remote nodes (e.g., `node2`, `node3`) in the homelab cluster.

## Prerequisites and Paths

- **Working Directory**: `<repo_root>/ansible`
- **Ansible Executable**: `.venv/bin/ansible` (or `<repo_root>/ansible/.venv/bin/ansible`)
- **Inventory File**: `inventory/home.yaml`

## Core Guidelines

1. **Strictly Read-Only**: You MUST only execute commands that do not alter the state of the target system (e.g., `ip`, `sysctl`, `kubectl`, `cat`, `grep`, `systemctl status`, `journalctl`). Never execute modifying commands (e.g., `systemctl restart`, `iptables -A`, writing files).
2. **Execution Method**: Always run the Ansible commands from the `<repo_root>/ansible` directory.

## Command Templates

### 1. Run a Standard Diagnostic Command
Run a command as the default `ansible` user:
```bash
<repo_root>/ansible/.venv/bin/ansible <node_name> -i inventory/home.yaml -m shell -a "<command>"
```

### 2. Run a Command with Sudo Privileges
If the command requires root/sudo access (e.g., reading syslog or system configs), append the `-b` (become) flag:
```bash
<repo_root>/ansible/.venv/bin/ansible <node_name> -i inventory/home.yaml -m shell -a "<command>" -b
```

## Common Diagnostic Recipes

### Inspect Interfaces
```bash
<repo_root>/ansible/.venv/bin/ansible node2 -i inventory/home.yaml -m shell -a "ip -o link show"
```

### Inspect IP Addresses
```bash
<repo_root>/ansible/.venv/bin/ansible node2 -i inventory/home.yaml -m shell -a "ip -o addr show | grep -E 'inet '"
```

### Inspect Sysctl Settings
```bash
<repo_root>/ansible/.venv/bin/ansible node2 -i inventory/home.yaml -m shell -a "sysctl net.ipv4.conf.all.rp_filter"
```

### Inspect Journal Logs
```bash
<repo_root>/ansible/.venv/bin/ansible node2 -i inventory/home.yaml -m shell -a "journalctl -u nftables --since '1 hour ago'" -b
```

### Run kubectl as Admin
```bash
<repo_root>/ansible/.venv/bin/ansible node2 -i inventory/home.yaml -m shell -a "sudo KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes"
```
