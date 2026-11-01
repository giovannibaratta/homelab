#!/usr/bin/env python3
"""Two ARM VMs on macOS. Usage: lab.py {up,down,reset,status}.

up resumes existing disks; reset stops both VMs and discards their changes.
Only the gateway has an uplink. The target's only NIC uses a Unix socket.

Network layout (static addresses are configured in cloud-init/*-network.yaml):
  gateway WAN: QEMU user-mode NAT, DHCP on its private 10.0.2.0/24 network
  gateway LAN: 172.16.255.254 for routing, .252 and .253 for DNS
  target LAN:  172.16.0.10/16, later moved from eth0 to br0 by the network role
  target K8s:  172.20.0.10/16, configured by the role, not cloud-init

The LAN addresses deliberately match the role's existing hardcoded DNS subnet.
The Unix socket is a virtual Ethernet cable between these two VMs: it adds no
interface, bridge or route to macOS. Matching physical LAN addresses therefore
do not cause an address conflict. Do not attach this lab LAN to a physical bridge.
The gateway firewall blocks forwarding to private WAN destinations. This does
not guarantee isolation from production services exposed at public addresses.
Only one lab can run at a time: it owns fixed socket paths and SSH port 22220.
"""

import argparse
import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import time
import urllib.request
from typing import Any, Literal, NotRequired, TypeAlias, TypedDict, cast

import yaml
from qemu.qmp import ConnectError, QMPClient

LAB = Path(__file__).resolve().parents[1]
STATE = LAB.parents[1] / ".ansible/vm-lab"
# Canonical's dated image and SHA256SUMS; do not follow the moving release alias.
IMAGE_URL = "https://cloud-images.ubuntu.com/releases/noble/release-20261017/ubuntu-24.04-server-cloudimg-arm64.img"
IMAGE_SHA256 = "50e24e1fb79e89116e939d90aa7738f7af48c442fa1bc2510131e0b39c50348e"

SSH_PORT = 22220
TARGET_IP = "172.16.0.10"  # Also set in cloud-init/target-network.yaml and inventory/hosts.yml.
VMName = Literal["gateway", "target"]


@dataclass(frozen=True)
class VirtualMachine:
    """Fixed VM resources and NIC identities; no running process state is stored."""

    name: VMName
    memory_mib: int
    lan_mac: str
    wan_mac: str | None = None
    cpus: int = 2


# Deterministic, locally administered unicast MACs, unique within this lab.
# Netplan matches these exact values to rename NICs to wan0/lan0/eth0; random
# MACs would break those matches. Keep cloud-init/*-network.yaml in sync.
GATEWAY = VirtualMachine("gateway", 1024, "52:54:00:00:00:02", "52:54:00:00:00:01")
TARGET = VirtualMachine("target", 2048, "52:54:00:00:00:03")
VMS = (GATEWAY, TARGET)  # Start the socket server (gateway) before its client.


# Network configuration is nested YAML; values remain flexible without using Any.
YamlValue: TypeAlias = str | int | float | bool | None | list["YamlValue"] | dict[str, "YamlValue"]
YamlMapping: TypeAlias = dict[str, YamlValue]


class CloudInitUser(TypedDict):
    """User fields consumed or emitted by the lab bootstrap."""

    name: str
    groups: NotRequired[list[str]]
    shell: NotRequired[str]
    lock_passwd: NotRequired[bool]
    ssh_authorized_keys: NotRequired[list[str]]


class CloudInitConfig(TypedDict):
    """Cloud-init options used by the gateway and target seed files."""

    users: list[CloudInitUser]
    hostname: NotRequired[str]
    groups: NotRequired[list[str]]
    ssh_pwauth: NotRequired[bool]
    disable_root: NotRequired[bool]
    package_update: NotRequired[bool]
    packages: NotRequired[list[str]]
    write_files: NotRequired[list[YamlMapping]]
    runcmd: NotRequired[list[YamlValue]]


class VMStatus(TypedDict):
    """Fields consumed from QMP's query-status response (not guest health)."""

    status: str
    running: bool


# OpenSSH aliases let Ansible reach the target through the gateway without a
# second management NIC. Quotes preserve paths containing spaces.
SSH_CONFIG_TEMPLATE = '''Host gateway target
  User ansible
  IdentityFile "{state_dir}/id_ed25519"
  IdentitiesOnly yes
  UserKnownHostsFile "{state_dir}/known_hosts"
  StrictHostKeyChecking accept-new
  ControlMaster no
Host gateway
  HostName 127.0.0.1
  Port {ssh_port}
Host target
  HostName {target_ip}
  ProxyJump gateway
'''


def run(*args: str | Path) -> None:
    """Run an executable directly, without shell interpolation; fail on error."""
    subprocess.run([str(arg) for arg in args], check=True)


async def qmp(name: VMName, command: str, state: Path) -> Any:
    """Let the official client handle negotiation, replies and async events."""
    async with asyncio.timeout(5):
        client = QMPClient(name)
        await client.connect(str(state / f"{name}.qmp"))

        try:
            return await client.execute(command)
        finally:
            await client.disconnect()


def vm_status(name: VMName, state: Path) -> VMStatus | None:
    """Only missing/refused sockets mean absent; other QMP failures propagate."""
    try:
        return cast(VMStatus, asyncio.run(qmp(name, "query-status", state)))
    except ConnectError as error:
        if not isinstance(error.exc, (FileNotFoundError, ConnectionRefusedError)):
            raise
        (state / f"{name}.qmp").unlink(missing_ok=True)
        return None


def stop() -> None:
    """Quit guests before the gateway, retaining their disks and console logs."""
    for vm in reversed(VMS):
        stop_vm(vm.name, STATE)


def stop_vm(name: VMName, state: Path) -> None:
    """Stop one QEMU instance before its caller replaces or deletes its disks."""
    monitor = state / f"{name}.qmp"
    if vm_status(name, state) is not None:
        asyncio.run(qmp(name, "quit", state))
        for _ in range(50):
            if not monitor.exists():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f"{name} has not stopped; disks were preserved")


def download_ubuntu() -> Path:
    """Return the checksum-verified base image, downloading it only if absent.

    Download to a temporary file so an interruption cannot leave a partial
    ubuntu.img. Verify cached images too, before using them as backing disks.
    """
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    image = STATE / "ubuntu.img"
    if not image.exists():
        temporary = image.with_suffix(".download")
        print(f"Downloading {IMAGE_URL}", flush=True)
        with urllib.request.urlopen(IMAGE_URL, timeout=60) as source, temporary.open("wb") as output:
            shutil.copyfileobj(source, output)

        with temporary.open("rb") as downloaded:
            if hashlib.file_digest(downloaded, "sha256").hexdigest() != IMAGE_SHA256:
                temporary.unlink()
                raise RuntimeError("Ubuntu image checksum mismatch")

        temporary.rename(image)

    with image.open("rb") as downloaded:
        if hashlib.file_digest(downloaded, "sha256").hexdigest() != IMAGE_SHA256:
            raise RuntimeError("Cached Ubuntu image checksum mismatch")

    return image


def find_firmware() -> Path:
    """Find Homebrew's firmware beside the resolved QEMU installation."""
    executable = shutil.which("qemu-system-aarch64")
    if executable is None:
        raise RuntimeError("qemu-system-aarch64 is not installed or is not on PATH")
    return Path(executable).resolve().parent.parent / "share/qemu"


def prepare_vm(
    vm: VirtualMachine,
    image: Path,
    firmware: Path,
    config: CloudInitConfig,
    network: YamlMapping,
    state: Path,
    disk_size: str = "20G",
) -> None:
    """Seed a missing VM disk; existing disks retain their guest configuration.

    The caller supplies cloud-init data and a state directory, allowing isolated
    and bridged scenarios to reuse the same image without sharing writable disks.
    The SSH public key must already exist in that state directory.
    """
    name = vm.name
    disk = state / f"{name}.qcow2"

    if disk.exists():
        return

    seed = state / f"{name}-seed"
    seed.mkdir(exist_ok=True)
    config["users"][0]["ssh_authorized_keys"] = [(state / "id_ed25519.pub").read_text().strip()]
    (seed / "user-data").write_text("#cloud-config\n" + yaml.safe_dump(config))
    hostname = config.get("hostname", f"lab-{name}")
    (seed / "meta-data").write_text(f"instance-id: lab-{name}\nlocal-hostname: {hostname}\n")
    (seed / "network-config").write_text(yaml.safe_dump(network))
    iso = state / f"{name}-seed.iso"
    iso.unlink(missing_ok=True)
    # cidata identifies this virtual CD as a cloud-init NoCloud datasource.
    run("hdiutil", "makehybrid", "-iso", "-joliet", "-default-volume-name", "cidata", "-o", iso, seed)
    # Per-VM writable UEFI settings; the firmware code remains read-only.
    shutil.copyfile(firmware / "edk2-arm-vars.fd", state / f"{name}-vars.fd")
    run("qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", image, disk, disk_size)


def prepare() -> Path:
    """Verify the base image, seed missing disks, and return the firmware folder.

    Existing VM disks are resumed untouched. Each new disk is a writable qcow2
    overlay backed by the unchanged Ubuntu image. The cidata ISO supplies SSH
    access and initial networking through cloud-init's NoCloud datasource.
    """
    image = download_ubuntu()

    if not (STATE / "id_ed25519").exists():
        run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", STATE / "id_ed25519")

    firmware = find_firmware()

    for vm in VMS:
        name = vm.name
        config = cast(CloudInitConfig, yaml.safe_load((LAB / f"cloud-init/{name}.yaml").read_text()))
        network = cast(YamlMapping, yaml.safe_load((LAB / f"cloud-init/{name}-network.yaml").read_text()))
        prepare_vm(vm, image, firmware, config, network, STATE)

    (STATE / "ssh_config").write_text(SSH_CONFIG_TEMPLATE.format(
        state_dir=STATE, ssh_port=SSH_PORT, target_ip=TARGET_IP,
    ))
    return firmware


def gateway_network_arguments(vm: VirtualMachine, lan_socket: Path) -> list[str]:
    """Give the gateway a NAT uplink and the listening end of the lab LAN.

    A QEMU netdev is the host-side connection; a device is the emulated guest
    NIC attached to it. Only the gateway has a WAN NIC. Its SSH forward binds
    to macOS loopback so the controller can reach it without exposing it to LAN.
    """
    if vm.wan_mac is None:
        raise ValueError("The gateway requires a WAN MAC address")
    return [
        "-netdev", f"user,id=wan,ipv6=off,hostfwd=tcp:127.0.0.1:{SSH_PORT}-:22",
        "-device", f"virtio-net-pci,netdev=wan,mac={vm.wan_mac}",
        "-netdev", f"stream,id=lan,server=on,addr.type=unix,addr.path={lan_socket}",
        "-device", f"virtio-net-pci,netdev=lan,mac={vm.lan_mac}",
    ]


def target_network_arguments(vm: VirtualMachine, lan_socket: Path) -> list[str]:
    """Connect the target's only NIC to the gateway's LAN socket.

    Reconnect every second if that socket connection drops. There is no direct
    NAT or management NIC: SSH, DNS and Internet traffic all use the gateway.
    """
    return [
        "-netdev", f"stream,id=lan,server=off,addr.type=unix,addr.path={lan_socket},reconnect-ms=1000",
        "-device", f"virtio-net-pci,netdev=lan,mac={vm.lan_mac}",
    ]


def network_arguments(vm: VirtualMachine, lan_socket: Path) -> list[str]:
    """Select the network topology explicitly by VM role."""
    if vm.name == "gateway":
        return gateway_network_arguments(vm, lan_socket)
    return target_network_arguments(vm, lan_socket)


def qemu_base_command(vm: VirtualMachine, firmware: Path, state: Path) -> list[str]:
    """Build the QEMU CLI in groups: hardware, firmware, storage and management.

    HVF runs ARM instructions using Apple's hypervisor. UEFI code is shared
    read-only, but each VM gets its own writable firmware variables file.
    The seed CD carries configuration, not an OS installer. There is no GUI:
    serial output goes to a log, while the QMP socket controls the process.
    """
    name = vm.name
    args = [
        "qemu-system-aarch64",
        # Virtual ARM machine with native hardware acceleration.
        "-name", f"homelab-{name}",
        "-machine", "virt,accel=hvf",
        "-cpu", "host",
        "-smp", str(vm.cpus),
        "-m", str(vm.memory_mib),
        # Read-only UEFI firmware and per-VM persistent boot variables.
        "-drive", f"if=pflash,format=raw,readonly=on,file={firmware}/edk2-aarch64-code.fd",
        "-drive", f"if=pflash,format=raw,file={state}/{name}-vars.fd",
        # Writable OS overlay and read-only cloud-init CD.
        "-drive", f"if=virtio,format=qcow2,file={state}/{name}.qcow2",
        "-drive", f"if=none,id=seed,format=raw,readonly=on,file={state}/{name}-seed.iso",
        "-device", "virtio-scsi-pci",
        "-device", "scsi-cd,drive=seed",
        # Headless background process, separate console log and control socket.
        "-display", "none",
        "-serial", f"file:{state}/{name}-console.log",
        "-monitor", "none",
        "-qmp", f"unix:{state}/{name}.qmp,server=on,wait=off",
        "-daemonize",
    ]
    return args


def qemu_command(vm: VirtualMachine, firmware: Path, lan_socket: Path) -> list[str]:
    """Attach the isolated lab topology to the common QEMU machine settings."""
    return qemu_base_command(vm, firmware, STATE) + network_arguments(vm, lan_socket)


def start() -> None:
    """Resume or create both VMs, refusing to start a second lab instance."""
    for vm in VMS:
        name = vm.name
        status = vm_status(name, STATE)
        if status is not None:
            raise RuntimeError(f"{name} already exists (state: {status['status']}); run down first")

    firmware = prepare()
    lan = STATE / "lan.sock"
    lan.unlink(missing_ok=True)
    # Refuse to attach to another service if our forwarded SSH port is occupied.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", SSH_PORT))
    for vm in VMS:
        run(*qemu_command(vm, firmware, lan))
    print(f"VMs started. Logs: {STATE}\nSSH: ssh -F {STATE}/ssh_config target")


def main() -> None:
    """Dispatch explicit lifecycle actions; status never restarts a guest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("up", "down", "reset", "status"))
    args = parser.parse_args()

    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("This lab requires an Apple Silicon Mac")

    if args.action == "status":
        for vm in VMS:
            name = vm.name
            status = vm_status(name, STATE)
            print(f"{name}: {status['status'] if status is not None else 'absent'}")

    if args.action in ("down", "reset"):
        stop()

    if args.action == "reset":
        # Deliberately retain the image, SSH key and console logs for diagnostics.
        for vm in VMS:
            name = vm.name
            for suffix in (".qcow2", "-vars.fd"):
                (STATE / f"{name}{suffix}").unlink(missing_ok=True)

        (STATE / "known_hosts").unlink(missing_ok=True)

    if args.action in ("up", "reset"):
        start()


if __name__ == "__main__":
    main()
