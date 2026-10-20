# SPDX-License-Identifier: Apache-2.0
"""Check core command membership, not semantic completeness or conformance."""

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

REGISTRY_REVISION = "85da0d12c298ffa9eefd2adb1864f2c8193cbe3e"
REGISTRY_SHA256 = "eb5178c428da9e77ede6350bc74ab302890a8e321a44cd84dbf54ea16bdd6946"
REGISTRY_URL = ("https://raw.githubusercontent.com/KhronosGroup/OpenCL-Docs/"
                f"{REGISTRY_REVISION}/xml/cl.xml")
AUDIT_PATH = "docs/implementation/compute-feature-map.md"
VERSIONS = frozenset({"1.0", "1.1", "1.2", "2.0", "2.1", "2.2", "3.0"})
COMMAND = re.compile(r"`(cl[A-Z][A-Za-z0-9]+)`")
START = "## Host API and mandatory baseline"
END = "## Language, environment and optional surface"


@dataclass(frozen=True)
class Inventory:
    """A supplied registry's command membership and audit coverage."""

    commands: tuple[str, ...]
    missing: tuple[str, ...]
    unknown: tuple[str, ...]
    duplicate: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not (self.missing or self.unknown or self.duplicate)


def core_commands(registry: bytes) -> set[str]:
    """Read all core feature blocks; extensions cannot hide absent core names."""
    # The CLI authenticates the exact registry digest before parsing; only tests bypass it.
    root = ET.fromstring(registry)  # noqa: S314
    if root.tag != "registry":
        raise ValueError("expected the OpenCL registry root")
    versions: set[str] = set()
    commands: set[str] = set()
    for feature in root.findall("feature"):
        if feature.get("api") != "opencl":
            continue
        version = feature.get("number", "")
        if version not in VERSIONS or version in versions:
            raise ValueError(f"unexpected or duplicate core version: {version}")
        versions.add(version)
        names: set[str] = set()
        for node in feature.findall("require/command"):
            name = node.get("name", "")
            if not re.fullmatch(r"cl[A-Z][A-Za-z0-9]+", name):
                raise ValueError("missing or malformed core command name")
            names.add(name)
        if not names:
            raise ValueError(f"empty command inventory for core version {version}")
        commands.update(names)
    if versions != VERSIONS:
        raise ValueError(f"missing core versions: {sorted(VERSIONS - versions)}")
    return commands


def audit_commands(document: str) -> list[str]:
    """Only explicit identifiers in host-table subject cells establish coverage."""
    if document.count(START) != 1 or document.count(END) != 1:
        raise ValueError("host audit section boundaries are missing or duplicated")
    begin = document.index(START) + len(START)
    finish = document.index(END)
    if begin >= finish:
        raise ValueError("host audit section boundaries are out of order")
    commands: list[str] = []
    for line in document[begin:finish].splitlines():
        if not line.startswith("| "):
            continue
        cells = line.split("|")
        if len(cells) != 5:
            raise ValueError("expected three host audit table cells")
        names = COMMAND.findall(cells[1])
        if not names:
            continue
        if "U(" not in cells[2] and " C" not in cells[2]:
            raise ValueError(f"missing disposition for {names[0]}")
        if not cells[3].strip():
            raise ValueError(f"missing observable for {names[0]}")
        commands.extend(names)
    if not commands:
        raise ValueError("host audit has no explicit command coverage")
    return commands


def compare(registry: bytes, document: str, *, require_pin: bool = True) -> Inventory:
    """Bind the oracle bytes and compare membership; judgments remain reviewed."""
    if require_pin and hashlib.sha256(registry).hexdigest() != REGISTRY_SHA256:
        raise ValueError("registry bytes do not match the frozen OpenCL-Docs revision")
    expected = core_commands(registry)
    actual = audit_commands(document)
    seen: set[str] = set()
    duplicate: set[str] = set()
    for name in actual:
        if name in seen:
            duplicate.add(name)
        seen.add(name)
    return Inventory(tuple(sorted(expected)), tuple(sorted(expected - seen)),
                     tuple(sorted(seen - expected)), tuple(sorted(duplicate)))
