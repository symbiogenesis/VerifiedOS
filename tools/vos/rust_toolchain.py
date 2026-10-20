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
import tomllib
from pathlib import Path
from typing import TypedDict, cast

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


def _release(version: object, what: str) -> tuple[int, int, int]:
    """A plain major.minor.patch release; pre-release and build suffixes are refused."""
    match = _RELEASE.fullmatch(version) if isinstance(version, str) else None
    if match is None:
        raise ValueError(f"{what} is not a plain major.minor.patch release: {version!r}")
    return int(match[1]), int(match[2]), int(match[3])


def check_lock_override(upstream: str, override: str, versions: dict[str, str],
                        *, consumer: str) -> None:
    """Refuse an override differing from upstream's lock beyond the declared versions.

    A declared package keeps every other field, including its source and
    dependencies, and changes only its version and checksum, to a release later
    than upstream's. Every other package entry and top-level key must be identical.
    """
    try:
        before, after = tomllib.loads(upstream), tomllib.loads(override)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"a {consumer} Cargo.lock is not TOML") from exc
    if ({key: value for key, value in before.items() if key != "package"}
            != {key: value for key, value in after.items() if key != "package"}):
        raise ValueError(f"the {consumer} lock override changes the lock format")

    def split(lock: dict[str, object]) -> tuple[list[str], dict[str, dict[str, object]]]:
        raw = lock.get("package")
        if (not isinstance(raw, list) or any(not isinstance(row, dict)
                or not isinstance(row.get("name"), str) for row in raw)):
            raise ValueError(f"the {consumer} lock has malformed package entries")
        rows = cast(list[dict[str, object]], raw)
        kept = sorted(json.dumps(row, sort_keys=True) for row in rows if row["name"] not in versions)
        moved: dict[str, dict[str, object]] = {}
        for row in rows:
            name = cast(str, row["name"])
            if name in versions:
                if name in moved:
                    raise ValueError(f"overridden {consumer} lock package is not unique: {name}")
                moved[name] = row
        return kept, moved

    kept_before, moved_before = split(before)
    kept_after, moved_after = split(after)
    if kept_before != kept_after:
        raise ValueError(f"the {consumer} lock override changes an undeclared package")
    if set(moved_before) != set(versions) or set(moved_after) != set(versions):
        raise ValueError(f"a declared {consumer} lock override names no locked package")
    for name, version in versions.items():
        old, new = moved_before[name], moved_after[name]
        changing = ("version", "checksum")
        if (new["version"] != version or set(old) != set(new)
                or {k: v for k, v in old.items() if k not in changing}
                != {k: v for k, v in new.items() if k not in changing}):
            raise ValueError(f"the {consumer} lock override for {name} is not the declared version alone")
        source = old.get("source")
        if (not isinstance(source, str) or not source.startswith("registry+")
                or not all(isinstance(checksum, str) and _SHA256.fullmatch(checksum) is not None
                           for checksum in (old.get("checksum"), new.get("checksum")))):
            raise ValueError(f"the {consumer} override for {name} needs a registry source and SHA-256 checksums")
        if _release(old["version"], f"upstream's {name}") >= _release(version, f"the declared {name}"):
            raise ValueError(f"upstream already carries {name} {old['version']}; "
                            "retire or regenerate the override")
