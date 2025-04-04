# Ansible

## Prerequisites

- Install Python packages
    ```bash
    pip install -r requirements.txt
    ```
- (optional) If you use Bitwarden Secret Manager to store variables, you have to install the SDK and configure an access token.
    ```bash
    export BWS_ACCESS_TOKEN=""
    ```
- Terraform

## Run playbook

1. Install the requirements

    ```bash
    ansible-galaxy install -r "requirements.yaml"
    ```

1. Install the collections

    ```bash
    ansible-galaxy collection install collections/ansible_collections/homelab/system
    ansible-galaxy collection install collections/ansible_collections/homelab/apps
    ```

1. Run the playbook
    ```bash
    ansible-playbook "setup_homelab.yaml" -i inventory/home.yaml -v
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
chmod -R 600 /home/ansible/.ssh
chown -R ansible:ansible /home/ansible
```
