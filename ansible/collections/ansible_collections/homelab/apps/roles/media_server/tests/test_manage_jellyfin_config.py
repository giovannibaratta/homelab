"""Verify semantic idempotence, offline checks, and application-data preservation."""

import json
import stat
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from ..files import manage_jellyfin_config as config


class ConfigurationTests(unittest.TestCase):
    def test_unmanaged_state_and_xml_comments_are_preserved(self) -> None:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        root = ET.fromstring(
            "<ServerConfiguration><!--app-owned--><IsStartupWizardCompleted>true"
            "</IsStartupWizardCompleted><Unknown><Nested>keep</Nested></Unknown>"
            "<ServerName>Old</ServerName></ServerConfiguration>",
            parser=parser,
        )
        self.assertEqual(config.merge(root, {"ServerName": "TV"}), ["ServerName"])
        self.assertEqual(root.findtext("IsStartupWizardCompleted"), "true")
        self.assertEqual(root.findtext("Unknown/Nested"), "keep")
        self.assertIn("<!--app-owned-->", ET.tostring(root, encoding="unicode"))

    def test_equivalent_values_do_not_produce_permanent_diffs(self) -> None:
        root = ET.fromstring(
            "<NetworkConfiguration>\n<BaseUrl/>\n<EnableHttps>False</EnableHttps>"
            "<InternalHttpPort>08096</InternalHttpPort><KnownProxies>"
            "<string>172.16.0.2</string><string>172.16.0.1</string>"
            "</KnownProxies></NetworkConfiguration>"
        )
        values: dict[str, config.XMLValue] = {
            "BaseUrl": "",
            "EnableHttps": False,
            "InternalHttpPort": 8096,
            "KnownProxies": ["172.16.0.1", "172.16.0.2"],
        }
        self.assertEqual(config.merge(root, values), [])

    def test_array_replacement_and_empty_arrays_are_idempotent(self) -> None:
        root = ET.fromstring(
            "<NetworkConfiguration><KnownProxies/></NetworkConfiguration>"
        )
        values: dict[str, config.XMLValue] = {"KnownProxies": ["10.89.0.1"]}
        self.assertEqual(config.merge(root, values), ["KnownProxies"])
        self.assertEqual(config.merge(root, values), [])
        self.assertEqual(config.merge(root, {"KnownProxies": []}), ["KnownProxies"])
        reloaded = ET.fromstring(ET.tostring(root))
        self.assertEqual(config.merge(reloaded, {"KnownProxies": []}), [])

    def test_check_only_does_not_create_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "network.xml"
            desired: config.ManagedFile = {
                "path": str(path),
                "root": "NetworkConfiguration",
                "values": {"EnableRemoteAccess": False},
            }
            self.assertEqual(
                config.reconcile(desired, check=True), ["EnableRemoteAccess"]
            )
            self.assertFalse(path.exists())

    def test_second_apply_does_not_rewrite_file_and_preserves_permissions(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "system.xml"
            path.write_text(
                "<ServerConfiguration><IsStartupWizardCompleted>true"
                "</IsStartupWizardCompleted></ServerConfiguration>"
            )
            path.chmod(0o640)
            desired: config.ManagedFile = {
                "path": str(path),
                "root": "ServerConfiguration",
                "values": {"ServerName": "TV"},
            }
            self.assertEqual(config.reconcile(desired, check=False), ["ServerName"])
            written = path.read_bytes()
            timestamp = path.stat().st_mtime_ns
            self.assertEqual(config.reconcile(desired, check=False), [])
            self.assertEqual(path.read_bytes(), written)
            self.assertEqual(path.stat().st_mtime_ns, timestamp)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            self.assertEqual(
                ET.parse(path).findtext("IsStartupWizardCompleted"), "true"
            )

    def test_malformed_or_wrong_xml_is_never_replaced(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "system.xml"
            desired: config.ManagedFile = {
                "path": str(path),
                "root": "ServerConfiguration",
                "values": {"ServerName": "TV"},
            }
            for original in ["<broken", "<WrongRoot/>"]:
                path.write_text(original)
                with self.assertRaises((ET.ParseError, ValueError)):
                    config.reconcile(desired, check=False)
                self.assertEqual(path.read_text(), original)

    def test_duplicate_managed_fields_are_rejected(self) -> None:
        root = ET.fromstring(
            "<Root><ServerName>A</ServerName><ServerName>B</ServerName></Root>"
        )
        with self.assertRaises(ValueError):
            config.merge(root, {"ServerName": "TV"})

    def test_nested_content_is_not_a_valid_scalar(self) -> None:
        root = ET.fromstring(
            "<Root><Enabled>true<Nested/></Enabled><Port>8096<Nested/></Port></Root>"
        )
        self.assertEqual(
            config.merge(root, {"Enabled": True, "Port": 8096}), ["Enabled", "Port"]
        )
        self.assertEqual(config.merge(root, {"Enabled": True, "Port": 8096}), [])

    def test_replacing_nil_values_is_idempotent(self) -> None:
        root = ET.fromstring(
            '<Root xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<Name xsi:nil="true"/><Values xsi:nil="true"/></Root>'
        )
        values: dict[str, config.XMLValue] = {"Name": "TV", "Values": ["one"]}
        self.assertEqual(config.merge(root, values), ["Name", "Values"])
        reloaded = ET.fromstring(ET.tostring(root))
        self.assertEqual(config.merge(reloaded, values), [])
        for element in reloaded:
            self.assertNotIn(config.XSI_NIL, element.attrib)

    def test_manifest_rejects_unsupported_values_before_writing(self) -> None:
        invalid_values: list[object] = [None, 1.5, {"Nested": True}, ["one", 2]]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            manifest = Path(directory) / "settings.json"
            for value in invalid_values:
                manifest.write_text(
                    json.dumps(
                        {
                            "files": [
                                {
                                    "path": str(Path(directory) / "system.xml"),
                                    "root": "ServerConfiguration",
                                    "values": {"ServerName": value},
                                }
                            ]
                        }
                    )
                )
                with self.subTest(value=value), self.assertRaises(ValueError):
                    _ = config.load_manifest(manifest)

    def test_duplicate_manifest_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            manifest = Path(directory) / "settings.json"
            entry: config.ManagedFile = {
                "path": str(Path(directory) / "system.xml"),
                "root": "Root",
                "values": {},
            }
            manifest.write_text(json.dumps({"files": [entry, entry]}))
            with self.assertRaises(ValueError):
                _ = config.load_manifest(manifest)

    def test_later_invalid_xml_does_not_modify_earlier_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            first, second = (
                Path(directory) / "first.xml",
                Path(directory) / "second.xml",
            )
            first.write_text("<Root><Name>Old</Name></Root>")
            second.write_text("<broken")
            manifest = Path(directory) / "settings.json"
            manifest.write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": str(path),
                                "root": "Root",
                                "values": {"Name": "TV"},
                            }
                            for path in (first, second)
                        ]
                    }
                )
            )
            original = first.read_bytes()
            with (
                mock.patch("sys.argv", ["helper", "--manifest", str(manifest)]),
                self.assertRaises(ET.ParseError),
            ):
                config.main()
            self.assertEqual(first.read_bytes(), original)

    def test_failed_write_keeps_original_and_removes_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path = Path(directory) / "system.xml"
            path.write_text("<Root><Name>Old</Name></Root>")
            desired: config.ManagedFile = {
                "path": str(path),
                "root": "Root",
                "values": {"Name": "TV"},
            }
            original = path.read_bytes()
            with (
                mock.patch.object(
                    ET.ElementTree, "write", side_effect=OSError("disk full")
                ),
                self.assertRaises(OSError),
            ):
                _ = config.reconcile(desired, check=False)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
