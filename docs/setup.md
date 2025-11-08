# Prepare a new machine

1. Install Ubuntu OS 24 LTS (or a variant)
1. Set a static IP for the machine
   1. Remove all the YAML files in `/etc/netplan`
   1. Create a new file in `/etc/netplan/50-cloud-init.yaml` with the following content (replace the IP and the netmask)
      ```yaml
      network:
      version: 2
      renderer: NetworkManager
      ethernets:
        enp1s0:
          addresses:
            - "<STATIC_IP>/<NETMASK>"
          nameservers:
            addresses:
              - 1.1.1.1
              - 8.8.8.8
            search: []
      ```
   1. Reboot the system
   1. Validate that the system is using the static IP
      ```bash
      ip a | grep enp1s0
      ```
1. Follow [this](../ansible//README.md#manual-setup-to-enable-ansible) steps to setup an Ansible user
1. Install SSH server
1. `apt install openssh-server`
1. `systemctl enable ssh.service`
1. Validate that you can connect to the system using the ansible user
1. Add the new host in `ansible/inventory/home.yaml` with the required variables
1. Define an entry in the DNS solution referenced by the `ddclient`.
1. Run from the `ansible` directory of this repository the following command to complete the basic configuration of the FTTH connection and hardening
   ```bash
   ansible-playbook "setup_homelab.yaml" -i inventory/home.yaml -v --tag="first-setup" --limit "<TARGET_HOST_DEFINED_IN_INVENTORY>" -v
   ```
