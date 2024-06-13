# Ansible

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
