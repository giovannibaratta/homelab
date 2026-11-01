#!/usr/bin/env python3
"""Manage an isolated gateway and fresh Ubuntu ARM host on Apple Silicon.

Usage: fresh_host.py {up,down,reset,status}

The gateway provides NAT internet access, DNS and SSH forwarding on localhost
port 22221. The target has only a private socket-network connection to it.
No physical LAN bridge, NetBird connection or privileged helper is required.
The gateway blocks private WAN destinations; public services remain reachable.

up resumes disks; down stops both guests and retains their files. reset stops
both guests and recreates their disks. status only queries QEMU. Run Molecule's
fresh_host scenario separately to deploy and verify host roles.
"""

import argparse
from ipaddress import IPv4Address, IPv4Interface
from pathlib import Path
import platform
import socket
from typing import cast

import yaml

import lab

STATE = lab.STATE / "fresh_host"
SSH_PORT = 22221
LAN_SOCKET = STATE / "lan.sock"
GATEWAY = lab.GATEWAY
VM = lab.VirtualMachine("target", 4096, "52:54:00:00:00:13")
INVENTORY = lab.LAB / "molecule/fresh_host/inventory.yml"


def start() -> None:
    """Start both unprivileged guests on a scenario-specific socket network."""
    for vm in (GATEWAY, VM):
        if lab.vm_status(vm.name, STATE) is not None:
            raise RuntimeError("fresh_host is already running; use down or reset first")

    if (STATE / "target.qcow2").exists() and not (STATE / "isolated-network").exists():
        raise RuntimeError("Existing disk predates isolated networking; run reset to recreate it")

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", SSH_PORT))

    # Parse the scenario inventory as data: this does not evaluate secret lookups.
    home = yaml.safe_load(INVENTORY.read_text())["home"]
    host = home["hosts"]["fresh-host"]
    if host["internal_interface"] != "eth0":
        raise ValueError("The fresh_host VM bootstrap requires internal_interface: eth0")

    if host.get("network_is_router") is not False or host.get("auto_ansible_enabled") is not False:
        raise ValueError("fresh_host requires network_is_router and auto_ansible_enabled to be false")

    address = IPv4Interface(f"{host['internal_ip']}/{host['internal_network_netmask_length']}")
    gateway = IPv4Address(host["internal_gateway"])
    if address.ip in (address.network.network_address, address.network.broadcast_address):
        raise ValueError("The guest address must not be a network or broadcast address")

    if gateway not in address.network or gateway == address.ip:
        raise ValueError("The gateway must be a different address in the guest's subnet")

    dns_servers = host["fresh_host_dns_servers"]
    if not isinstance(dns_servers, list) or not dns_servers:
        raise ValueError("fresh_host_dns_servers must be a non-empty list of IPv4 addresses")
    for server in dns_servers:
        IPv4Address(server)

    IPv4Address(host["network_k8s_ip"])

    image = lab.download_ubuntu()  # Reuse the pinned, verified base image.
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)

    if not (STATE / "id_ed25519").exists():
        lab.run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", STATE / "id_ed25519")

    config = cast(lab.CloudInitConfig, yaml.safe_load((lab.LAB / "cloud-init/target.yaml").read_text()))
    config["hostname"] = "fresh-host"
    network: lab.YamlMapping = {
        "version": 2,
        "ethernets": {
            "lan": {
                "match": {"macaddress": VM.lan_mac},
                "set-name": "eth0",
                "addresses": [f"{host['internal_ip']}/{host['internal_network_netmask_length']}"],
                "routes": [{"to": "default", "via": host["internal_gateway"]}],
                "nameservers": {"addresses": host["fresh_host_dns_servers"]},
            }
        },
    }
    firmware = lab.find_firmware()
    lab.prepare_vm(VM, image, firmware, config, network, STATE, disk_size="60G")

    gateway_config = cast(lab.CloudInitConfig, yaml.safe_load((lab.LAB / "cloud-init/gateway.yaml").read_text()))
    gateway_config["hostname"] = "fresh-gateway"

    for entry in gateway_config.get("write_files", []):
        if entry.get("path") == "/etc/dnsmasq.d/lab.conf":
            entry["content"] = str(entry["content"]).replace(lab.TARGET_IP, host["internal_ip"])

    gateway_network = cast(lab.YamlMapping, yaml.safe_load((lab.LAB / "cloud-init/gateway-network.yaml").read_text()))
    lab.prepare_vm(GATEWAY, image, firmware, gateway_config, gateway_network, STATE)

    (STATE / "ssh_config").write_text(lab.SSH_CONFIG_TEMPLATE.format(
        state_dir=STATE, ssh_port=SSH_PORT, target_ip=host["internal_ip"],
    ))
    (STATE / "isolated-network").touch()
    LAN_SOCKET.unlink(missing_ok=True)

    try:
        lab.run(*(lab.qemu_base_command(GATEWAY, firmware, STATE)
                  + lab.gateway_network_arguments(GATEWAY, LAN_SOCKET, SSH_PORT)))
        lab.run(*(lab.qemu_base_command(VM, firmware, STATE)
                  + lab.target_network_arguments(VM, LAN_SOCKET)))
    except Exception:
        stop()
        raise

    print(f"fresh-host started at {host['internal_ip']} on the private lab network")
    print(f"SSH: ssh -F {STATE}/ssh_config target")


def stop() -> None:
    """Stop the target before its gateway, preserving guest disks and logs."""
    for vm in (VM, GATEWAY):
        lab.stop_vm(vm.name, STATE)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("action", choices=("up", "down", "reset", "status"))
    args = parser.parse_args()

    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("This VM requires an Apple Silicon Mac")

    if args.action == "status":
        for vm in (GATEWAY, VM):
            status = lab.vm_status(vm.name, STATE)
            print(f"{vm.name}: {status['status'] if status else 'absent'}")

    if args.action in ("down", "reset"):
        stop()

    if args.action == "reset":
        for vm in (VM, GATEWAY):
            for suffix in (".qcow2", "-vars.fd"):
                (STATE / f"{vm.name}{suffix}").unlink(missing_ok=True)
        (STATE / "known_hosts").unlink(missing_ok=True)

    if args.action in ("up", "reset"):
        start()


if __name__ == "__main__":
    main()
