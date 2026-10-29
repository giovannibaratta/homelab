"""Reconcile an explicit subset of Jellyfin XML settings before server startup.

Ansible installs the JSON manifest and runs ``--check`` against live files; that
mode never writes. systemd ExecStartPre applies it as Jellyfin's UID/GID while
the server is stopped. Do not invoke apply mode against a running server: this
helper does not acquire a Jellyfin lock or merge concurrent application writes.

Only named direct children are owned by code. Other elements, attributes,
comments and processing instructions are retained, although ElementTree can
normalize XML serialization when a real change requires rewriting a file.
Semantically equivalent files are not serialized at all (bytes/mtime unchanged).
String arrays are compared as unordered collections, including multiplicity;
use this helper only for settings whose array order has no meaning.

The manifest and every XML file are validated before the first write. Each file
is replaced atomically, but the collection of files is NOT a transaction: an I/O
failure can leave earlier files updated. Errors intentionally fail startup rather
than reset application configuration. The pinned Jellyfin XML schema remains
the caller's responsibility; unknown/removed fields can cause repeated drift.
"""

import argparse
import json
import os
import stat
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TypedDict, cast

XMLValue = str | int | bool | list[str]
XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"


class ManagedFile(TypedDict):
    path: str
    root: str
    values: dict[str, XMLValue]


class Manifest(TypedDict):
    files: list[ManagedFile]


class Arguments(argparse.Namespace):
    def __init__(self) -> None:
        super().__init__()
        self.manifest: str = ""
        self.check: bool = False


def validate_values(values: dict[str, object]) -> dict[str, XMLValue]:
    """Reject unsupported JSON types instead of writing Python representations."""
    validated: dict[str, XMLValue] = {}
    for name, value in values.items():
        if not name.isidentifier():
            raise ValueError(f"Invalid configuration field: {name}")
        if isinstance(value, (str, bool, int)):
            validated[name] = value
        elif isinstance(value, list) and all(
            isinstance(item, str) for item in cast(list[object], value)
        ):
            validated[name] = cast(list[str], value)
        else:
            raise ValueError(f"Unsupported value type for configuration field: {name}")
    return validated


def load_manifest(path: Path) -> Manifest:
    """Validate the complete manifest, including duplicate destination paths."""
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Manifest must be an object containing files")
    files = cast(dict[str, object], raw).get("files")
    if not isinstance(files, list):
        raise ValueError("Manifest files must be a list")
    validated: list[ManagedFile] = []
    seen: set[Path] = set()
    for entry in cast(list[object], files):
        if not isinstance(entry, dict):
            raise ValueError("Each manifest file must be an object")
        fields = cast(dict[str, object], entry)
        destination, root, values = (
            fields.get("path"),
            fields.get("root"),
            fields.get("values"),
        )
        if not isinstance(destination, str) or not Path(destination).is_absolute():
            raise ValueError("Configuration file paths must be absolute")
        if not isinstance(root, str) or not root.isidentifier():
            raise ValueError(f"Invalid XML root for {destination}")
        if not isinstance(values, dict):
            raise ValueError(f"Configuration values must be an object: {destination}")
        resolved = Path(destination).resolve()
        if resolved in seen:
            raise ValueError(f"Duplicate configuration file: {destination}")
        seen.add(resolved)
        validated.append(
            {
                "path": destination,
                "root": root,
                "values": validate_values(cast(dict[str, object], values)),
            }
        )
    return {"files": validated}


def matches(element: ET.Element | None, desired: XMLValue) -> bool:
    """Compare supported values, ignoring layout and unordered-array order."""
    if element is None:
        return False
    if element.get(XSI_NIL, "false").lower() in ("true", "1"):
        # A null XML value is not the requested empty string/list (or scalar).
        return False
    text = element.text or ""
    if isinstance(desired, list):
        return all(
            child.tag == "string" and not len(child) for child in element
        ) and sorted(child.text or "" for child in element) == sorted(desired)
    if len(element):
        return False
    if isinstance(desired, bool):
        return text.strip().lower() == str(desired).lower()
    if isinstance(desired, int):
        try:
            return int(text) == desired
        except ValueError:
            return False
    return not len(element) and text == desired


def merge(root: ET.Element, values: dict[str, XMLValue]) -> list[str]:
    """Change only explicitly managed direct children; retain all other XML."""
    values = validate_values(cast(dict[str, object], values))
    changed: list[str] = []
    for name, desired in values.items():
        elements = root.findall(name)
        if len(elements) > 1:
            raise ValueError(f"Duplicate configuration field: {name}")
        element = elements[0] if elements else None
        if matches(element, desired):
            continue
        if element is None:
            element = ET.SubElement(root, name)
        # Leaving xsi:nil=true on a replacement makes serializers read null
        # instead of the new value, causing drift or deserialization failures.
        _ = element.attrib.pop(XSI_NIL, None)
        for child in list(element):
            element.remove(child)
        if isinstance(desired, list):
            element.text = None
            for value in desired:
                ET.SubElement(element, "string").text = value
        elif isinstance(desired, bool):
            element.text = str(desired).lower()
        else:
            element.text = str(desired)
        changed.append(name)
    return changed


def reconcile(config: ManagedFile, *, check: bool) -> list[str]:
    """Atomically write only meaningful changes; never replace malformed XML."""
    path = Path(config["path"])
    if path.exists():
        parser = ET.XMLParser(
            target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
        )
        tree = ET.parse(path, parser=parser)
    else:
        tree = ET.ElementTree(ET.Element(config["root"]))
    root = tree.getroot()
    if root is None or root.tag != config["root"]:
        raise ValueError(f"Unexpected XML root in {path}")
    changed = merge(root, config["values"])
    if not changed or check:
        return changed
    # Run as the application UID. This cannot write files privileged to root.
    # Jellyfin must be stopped: ExecStartPre enforces that ordering.
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o660
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            tree.write(output, encoding="utf-8", xml_declaration=True)
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--manifest", required=True)
    _ = parser.add_argument("--check", action="store_true")
    args = parser.parse_args(namespace=Arguments())
    manifest = load_manifest(Path(args.manifest))
    # Preflight every file before apply. A malformed later file must not cause
    # valid earlier files to be rewritten. This is not a multi-file transaction.
    changes = {
        config["path"]: fields
        for config in manifest["files"]
        if (fields := reconcile(config, check=True))
    }
    if not args.check:
        for config in manifest["files"]:
            if config["path"] in changes:
                _ = reconcile(config, check=False)
    # Report field names only; never log complete configs or unmanaged secrets.
    print(json.dumps({"changed": bool(changes), "fields": changes}))


if __name__ == "__main__":
    main()
