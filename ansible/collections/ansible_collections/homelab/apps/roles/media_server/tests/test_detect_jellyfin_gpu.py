"""Selection safety tests; no real GPUs or host modifications required."""

import unittest
from pathlib import Path
from unittest.mock import patch

from ..files import detect_jellyfin_gpu as gpu


def device(
    vendor: str = "0x1002", driver: str = "amdgpu", number: int = 128, gid: int = 993
) -> gpu.GPUDevice:
    return {
        "node": f"/dev/dri/renderD{number}",
        "host_device": f"/dev/dri/by-path/pci-0000:0{number - 128}:00.0-render",
        "vendor": vendor,
        "driver": driver,
        "gid": gid,
    }


class SelectionTests(unittest.TestCase):
    def test_amd_auto_uses_stable_host_path_and_fixed_container_path(self) -> None:
        d = device(number=129)
        result = gpu.select([d], "auto", "auto")
        if result["backend"] == "none":
            self.fail("Expected an AMD GPU selection")
        self.assertEqual(result["backend"], "vaapi")
        self.assertEqual(result["host_device"], d["host_device"])
        self.assertEqual(result["container_device"], "/dev/dri/renderD128")
        self.assertEqual(result["gid"], 993)

    def test_intel_auto_is_conservative_but_qsv_can_be_requested(self) -> None:
        for driver in ["i915", "xe"]:
            d = device("0x8086", driver, gid=992)
            self.assertEqual(gpu.select([d], "auto", "auto")["backend"], "vaapi")
            self.assertEqual(gpu.select([d], "qsv", "auto")["backend"], "qsv")

    def test_missing_or_unsupported_gpu_falls_back_only_in_auto(self) -> None:
        cases: list[list[gpu.GPUDevice]] = [
            [],
            [device("0x10de", "nouveau")],
            [device("0x8086", "virtio_gpu")],
        ]
        for devices in cases:
            self.assertEqual(gpu.select(devices, "auto", "auto")["backend"], "none")
            with self.assertRaises(ValueError):
                gpu.select(devices, "vaapi", "auto")

    def test_multiple_gpus_require_explicit_selection(self) -> None:
        devices = [device(), device("0x8086", "i915", number=129)]
        with self.assertRaises(ValueError):
            gpu.select(devices, "auto", "auto")
        result = gpu.select(devices, "auto", "/dev/dri/renderD129")
        if result["backend"] == "none":
            self.fail("Expected explicit Intel GPU selection")
        self.assertEqual(result["vendor"], "0x8086")

    def test_explicit_stable_alias_resolves_to_selected_node(self) -> None:
        d = device()
        with patch.object(gpu.Path, "resolve", return_value=Path(d["node"])):
            result = gpu.select([d], "auto", d["host_device"])
        if result["backend"] == "none":
            self.fail("Expected stable GPU alias selection")
        self.assertEqual(result["gid"], 993)

    def test_wrong_vendor_and_missing_override_fail(self) -> None:
        with self.assertRaises(ValueError):
            gpu.select([device()], "qsv", "auto")
        with self.assertRaises(ValueError):
            gpu.select([device()], "auto", "/dev/dri/renderD999")

    def test_disabled_gpu_ignores_discovered_devices(self) -> None:
        self.assertEqual(
            gpu.select([device(), device(number=129)], "none", "auto")["backend"],
            "none",
        )


if __name__ == "__main__":
    unittest.main()
