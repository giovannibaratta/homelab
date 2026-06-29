# Ansible

## Prerequisites

- Install Python packages
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  python3 -m pip install -r requirements.txt
  ```
- (optional) If you use Bitwarden Secret Manager to store variables, you have to install the SDK (see [here](https://github.com/bitwarden/sdk-sm)) and configure an access token.
  ```bash
  export BWS_ACCESS_TOKEN=""
  ```
- Terraform

## Run playbook

1. Install the collections

   ```bash
   ansible-galaxy collection install collections/ansible_collections/homelab/utils
   ansible-galaxy collection install collections/ansible_collections/homelab/system
   ansible-galaxy collection install -r collections/ansible_collections/homelab/system/requirements.yml
   ansible-galaxy collection install collections/ansible_collections/homelab/apps
   ```

1. Run the playbook
   ```bash
   ansible-playbook "setup_homelab.yaml" -i inventory/home.yaml -v
   ```

## Emergency Outbound Fallback (Cloudflare Tunnel)

The `cloudflared` daemon can be deployed to provide fallback access when Zitadel, Traefik, or the VPN mesh are offline. Since it is an emergency fallback, it is kept separate from the main playbook to avoid unexpected service interruptions during regular deployments.

### Prerequisites

Define the Cloudflare tunnel tokens inside the Bitwarden Secrets Manager bundle as host-specific keys:
- `cloudflare_tunnel_token_node1`
- `cloudflare_tunnel_token_node2`
- `cloudflare_tunnel_token_node3`

#### Generating Tunnel Tokens
Create a separate tunnel for each node in the Cloudflare Zero Trust Dashboard:
1. Navigate to **Cloudflare Zero Trust Dashboard** -> **Networks** -> **Connectors**.
2. Click **Add a tunnel**, select **Cloudflare (Recommended)**, and click **Next**.
3. Name your tunnel (e.g., `homelab-node1`), and click **Save tunnel**.
4. On the **Install and run a connector** page, choose **Debian** or **Ubuntu**.
5. Locate the commands shown under **Install and run connector**.
6. Copy the long base64 string directly following the `--token` parameter (e.g., `eyJhIjoiZT...`).
7. Store this token under the key `cloudflare_tunnel_token_nodeX` in your Bitwarden Secrets Manager bundle.
8. Repeat for other nodes.

Enable the deployment for targeted hosts in `inventory/home.yaml` by setting:
```yaml
deploy_cloudflare_tunnel: true
```

### Deploy

Run the dedicated playbook:
```bash
ansible-playbook "deploy_cloudflare_tunnel.yaml" -i inventory/home.yaml
```

## Manual setup to enable Ansible

1. Create a group for passwordless sudo

```bash
groupadd wheel
```

1. Allow passwordless sudo for the group

```bash
echo "%wheel ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/wheel
```

1. Create ansible user

```bash
useradd -s /bin/bash ansible
```

1. Add the user to the group

```bash
usermod -aG wheel ansible
```

1. Copy the public key in the ansible home directory

```bash
SSH_PUB_KEY=""
mkdir -p /home/ansible/.ssh
echo "$SSH_PUB_KEY" >> /home/ansible/.ssh/authorized_keys
chmod -R 600 /home/ansible/.ssh/*
chmod 755 /home/ansible/.ssh/*
chown -R ansible:ansible /home/ansible
```

## Kubernetes

### Deploy

```bash
ansible-playbook --become "install_kubernetes.yaml" -i inventory/home.yaml
```

### Clean up

````bash
ansible-playbook --become -i inventory/home.yaml ~/.ansible/collections/ansible_collections/kubernetes_sigs/kubespray/playbooks/reset.yml --extra-vars "reset_confirmation=yes"
```bash

### Manual testing

```bash
kubectl run test-net --rm -ti --image=alpine -- ping -c 4 8.8.8.8
kubectl run test-dns --rm -ti --image=alpine -- nslookup google.com
````

### FAQ

#### Python requirements installation fails

If the installation of the Python requirements fails due to a maturin error, it might related to this issue [here](https://github.com/bitwarden/sdk-sm/issues/1222). Manually install the Bitwarden SDK python package by cloning it from GitHub.
