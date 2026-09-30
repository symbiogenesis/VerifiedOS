# SPDX-License-Identifier: Apache-2.0
"""The one Rust toolchain pin the optional native Rust builds install.

[rust-toolchain.json](../rust-toolchain.json) fixes the Rust release and, for each
supported Linux target, the SHA-256 of each component archive the distribution
server publishes. The optional Isla tools and the idealloc candidate build both
read it through `load`, so neither carries a copy that could drift from the other.
rustup does not read this file; each consumer installs the archives into its own
native lane.
"""

import json
import re
from pathlib import Path
from typing import TypedDict

PATH = "tools/rust-toolchain.json"
TARGETS = ("aarch64-unknown-linux-gnu", "x86_64-unknown-linux-gnu")
COMPONENTS = ("rustc", "cargo", "rust-std")
DIST = "https://static.rust-lang.org/dist/"
_RELEASE = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class Pin(TypedDict):
    version: str
    components: dict[str, dict[str, str]]


def load(root: Path) -> Pin:
    """Read the pin, refusing any shape but a plain release and one digest per component."""
    raw = json.loads((root / PATH).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"version", "components"}:
        raise ValueError(f"{PATH} must hold exactly a version and its components")
    version, components = raw["version"], raw["components"]
    if not isinstance(version, str) or _RELEASE.fullmatch(version) is None:
        raise ValueError(f"{PATH} names no plain major.minor.patch Rust release")
    if not isinstance(components, dict) or set(components) != set(TARGETS):
        raise ValueError(f"{PATH} must pin exactly the targets {', '.join(TARGETS)}")
    pinned: dict[str, dict[str, str]] = {}
    for target in TARGETS:
        archives = components[target]
        if (not isinstance(archives, dict) or set(archives) != set(COMPONENTS)
                or not all(isinstance(value, str) and _SHA256.fullmatch(value)
                           for value in archives.values())):
            raise ValueError(f"{PATH} must give {target} one SHA-256 for each of "
                             f"{', '.join(COMPONENTS)}")
        pinned[target] = {component: str(archives[component]) for component in COMPONENTS}
    return {"version": version, "components": pinned}


def archives(pin: Pin, target: str) -> list[tuple[str, str, str]]:
    """Each component's installer directory, HTTPS archive URL and pinned SHA-256."""
    rows: list[tuple[str, str, str]] = []
    for component, digest in pin["components"][target].items():
        name = f"{component}-{pin['version']}-{target}"
        rows.append((name, f"{DIST}{name}.tar.xz", digest))
    return rows
