"""Read DRM sysfs metadata and select one GPU; never modify host state."""

import argparse
import json
import stat
import sys
from pathlib import Path
from typing import Final, Literal, TypedDict

# PCI vendor IDs as exposed by /sys/class/drm/renderD*/device/vendor.
AMD_PCI_VENDOR_ID: Final = "0x1002"
INTEL_PCI_VENDOR_ID: Final = "0x8086"

# Bound Linux DRM drivers: AMD's amdgpu and Intel's legacy/current i915/xe.
# Matching the vendor alone would also admit unsupported virtual renderers.
AMD_DRM_DRIVER: Final = "amdgpu"
INTEL_DRM_DRIVERS: Final = ("i915", "xe")

# Deliberate container-side destination, not an assumed host device. Podman
# maps a colon-free symlink to the discovered host render node here via
# --device HOST:CONTAINER. The symlink follows the stable PCI by-path alias;
# that alias cannot appear directly in --device because PCI paths contain ':'.
# A host renderD129 can therefore appear as
# renderD128 inside Jellyfin. Host numbering is not stable or guaranteed to exist;
# without a supported host render node, auto mode falls back to CPU instead.
# Keep encoding.xml pointed at this same container-side path.
CONTAINER_RENDER_DEVICE: Final = "/dev/dri/renderD128"


class GPUDevice(TypedDict):
    node: str
    host_device: str
    vendor: str
    driver: str
    gid: int


class SelectedGPU(GPUDevice):
    backend: Literal["vaapi", "qsv"]
    container_device: str
    reason: str


class DisabledGPU(TypedDict):
    backend: Literal["none"]
    reason: str


class Arguments(argparse.Namespace):
    def __init__(self) -> None:
        super().__init__()
        self.backend: str = "none"
        self.device: str = "auto"


def discover() -> list[GPUDevice]:
    devices: list[GPUDevice] = []
    aliases = sorted(Path("/dev/dri/by-path").glob("*-render"))

    for entry in sorted(Path("/sys/class/drm").glob("renderD*")):
        node = Path("/dev/dri") / entry.name
        if not node.exists() or not stat.S_ISCHR(node.stat().st_mode):
            continue

        device = entry / "device"
        vendor_file = device / "vendor"
        vendor = vendor_file.read_text().strip().lower() if vendor_file.exists() else ""
        driver = (device / "driver").resolve().name
        stable = next((p for p in aliases if p.resolve() == node), node)
        devices.append(
            {
                "node": str(node),
                "host_device": str(stable),
                "vendor": vendor,
                "driver": driver,
                "gid": node.stat().st_gid,
            }
        )
    return devices


def select(
    devices: list[GPUDevice], backend: str, requested: str
) -> SelectedGPU | DisabledGPU:
    if backend == "none":
        return {"backend": "none", "reason": "GPU acceleration explicitly disabled"}
    # Vendor plus bound kernel driver avoids choosing software/virtual renderers.
    supported = [
        d
        for d in devices
        if (d["vendor"] == AMD_PCI_VENDOR_ID and d["driver"] == AMD_DRM_DRIVER)
        or (d["vendor"] == INTEL_PCI_VENDOR_ID and d["driver"] in INTEL_DRM_DRIVERS)
    ]
    if requested != "auto":
        supported = [
            d
            for d in supported
            if Path(requested).resolve() == Path(d["node"]).resolve()
        ]
        if not supported:
            raise ValueError(
                "Selected render device is missing or has no supported AMD/Intel driver"
            )
    if not supported:
        if backend != "auto":
            raise ValueError(
                "Requested acceleration backend has no supported render device"
            )
        return {
            "backend": "none",
            "reason": "No supported AMD/Intel render device found; using CPU",
        }
    if len(supported) != 1:
        raise ValueError(
            "Multiple supported GPUs found; set media_server_jellyfin_render_device "
            + "to an explicit /dev/dri/by-path/...-render path"
        )
    device = supported[0]
    if backend == "qsv" and device["vendor"] != INTEL_PCI_VENDOR_ID:
        raise ValueError("Quick Sync requires an Intel GPU; use vaapi for AMD")
    # VA-API covers both legacy and modern Intel. QSV runtime/generation support
    # cannot be established reliably from i915 alone, so QSV stays an opt-in.
    selected_backend: Literal["vaapi", "qsv"] = "qsv" if backend == "qsv" else "vaapi"
    return {
        **device,
        "backend": selected_backend,
        "container_device": CONTAINER_RENDER_DEVICE,
        "reason": (
            "Selected supported GPU; codec/runtime capabilities still need verification"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--backend", choices=["auto", "none", "vaapi", "qsv"], required=True
    )
    _ = parser.add_argument("--device", required=True)
    args = parser.parse_args(namespace=Arguments())
    try:
        print(json.dumps(select(discover(), args.backend, args.device)))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
