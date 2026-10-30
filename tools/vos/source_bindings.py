# SPDX-License-Identifier: Apache-2.0
"""Declared source identities shared by composition and admission views.

The ordered groups below own membership. Packages, production-input references
and receipt inventories derive their role-specific views from these declarations.
Generated JSON retains its other authored choices; no generator assigns handlers,
products, admission tiers or proof evidence.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Final

from vos.jsonutil import unique_object
from vos.receipts import atomic_path, digest

OWNER: Final = "tools/vos/source_bindings.py"
COMPOSITION: Final = "tools/composer/m8a-composition.json"
PACKAGE_FILES: Final[dict[str, str]] = {
    name: f"tools/composer/packages/{name}.json" for name in ("composer", "admission")}

# A dependency is declared once, at the narrowest common group. Ordered expansion
# keeps source manifests deterministic while removing repeated members at joins.
GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "shared": (OWNER, "tools/vos/jsonutil.py", "tools/vos/receipts.py",
               "tools/vos/proofenv.py", "tools/vos/atomic.py"),
    "composer-reference": ("@shared", "tools/vos/composer.py", "proofs/HandlerGraph.v"),
    "admission-reference": ("@shared", "tools/vos/admission.py", "proofs/AdmissionPath.v"),
    "composer-package": ("@composer-reference", "tools/vos/composition.py",
                         "tools/vos/cli/composer.py", "tools/vos/composition_staged.py"),
    "admission-package": ("@admission-reference", "tools/vos/admission_production.py",
                          "tools/vos/cli/admission.py"),
    "projection": ("@composer-reference", "tools/vos/composition.py", "tools/vos/boot.py",
                   "tools/vos/image.py", "tools/composer/composition.schema.json",
                   "tools/composer/package.schema.json"),
    "admission-comparison": ("@admission-reference", "tools/vos/cli/admission.py"),
    "admission-production": ("@admission-package", "@projection"),
    "boot-composition": ("@composer-reference", "@admission-reference"),
    "math-shapes": ("@composer-reference", "tools/vos/math_evidence.py"),
}

PRODUCER_VIEWS: Final[dict[str, str]] = {
    "offline-reference-composer": "composer-reference",
    "offline-reference-admission": "admission-reference"}


def sources(view: str) -> tuple[str, ...]:
    """Expand one declared view, refusing unknown or recursive declarations."""
    found: dict[str, None] = {}

    def visit(name: str, active: tuple[str, ...]) -> None:
        if name in active:
            raise ValueError(f"recursive source-binding group: {name}")
        if name not in GROUPS:
            raise ValueError(f"unknown source-binding group: {name}")
        members = GROUPS[name]
        if not members or len(members) != len(set(members)):
            raise ValueError(f"empty or repeated source-binding group members: {name}")
        for member in members:
            if member.startswith("@"):
                visit(member[1:], (*active, name))
            else:
                found[member] = None

    visit(view, ())
    return tuple(found)


def references(root: Path, view: str) -> list[dict[str, str]]:
    """Bind the current bytes of a declared view; missing members are errors."""
    return [{"path": name, "sha256": digest(_path(root, name))} for name in sources(view)]


def _path(root: Path, relative: str) -> Path:
    selected = (root / relative).resolve()
    if (Path(relative).is_absolute() or "\\" in relative or ".." in Path(relative).parts
            or not selected.is_relative_to(root.resolve())):
        raise ValueError(f"source-binding path must stay relative to the checkout: {relative}")
    return selected


def _read(root: Path, relative: str) -> dict[str, Any]:
    raw = json.loads(_path(root, relative).read_bytes(), object_pairs_hook=unique_object)
    if not isinstance(raw, dict):
        raise ValueError(f"source-binding input must be an object: {relative}")
    return raw


def render(root: Path, relative: str) -> str:
    """Regenerate owned source fields, preserving all other authored choices."""
    raw = _read(root, relative)
    package = next((name for name, path in PACKAGE_FILES.items() if path == relative), None)
    if package is not None:
        if raw.get("package_id") != package:
            raise ValueError(f"source-binding package identity disagrees: {relative}")
        raw["sources"] = references(root, f"{package}-package")
    elif relative == COMPOSITION:
        for field in ("producers", "members"):
            items = raw.get(field)
            if not isinstance(items, list) or any(
                    not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in items):
                raise ValueError(f"source-binding {field} must be an array of identified objects")
        for producer, view in PRODUCER_VIEWS.items():
            matches = [item for item in raw["producers"] if item["id"] == producer]
            if len(matches) != 1:
                raise ValueError(f"source-binding producer must occur once: {producer}")
            matches[0]["sources"] = references(root, view)
        for package, path in PACKAGE_FILES.items():
            matches = [item for item in raw["members"] if item["id"] == package]
            if len(matches) != 1:
                raise ValueError(f"source-binding member must occur once: {package}")
            # Bind the generated package bytes, including its authored interfaces.
            # Do not repair an independently selected descriptor into another file.
            descriptor = matches[0].get("descriptor")
            if not isinstance(descriptor, dict) or descriptor.get("path") != path:
                raise ValueError(f"source-binding package path disagrees: {package}")
            matches[0]["sources"] = references(root, f"{package}-package")
            matches[0]["descriptor"]["sha256"] = hashlib.sha256(render(root, path).encode("utf-8")).hexdigest()
    else:
        raise ValueError(f"no declared source-binding artifact: {relative}")
    return json.dumps(raw, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _destinations(root: Path) -> dict[str, Path]:
    """Preflight every output against containment, peers and bound source inputs."""
    destinations: dict[str, Path] = {}
    views = [*(f"{package}-package" for package in PACKAGE_FILES), *PRODUCER_VIEWS.values()]
    inputs = {_path(root, name) for view in views for name in sources(view)}
    for name in (*PACKAGE_FILES.values(), COMPOSITION):
        selected = _path(root, name)
        peers = [*destinations.values(), *inputs]
        if any(selected == peer or (selected.exists() and peer.exists() and selected.samefile(peer))
               for peer in peers):
            raise ValueError(f"source-binding destination aliases another output or bound source: {name}")
        destinations[name] = selected
    return destinations


def emit(root: Path) -> dict[str, str]:
    """Compute every declared view before publishing the fixed inventory paths.

    Each file is replaced atomically; the set is not a filesystem transaction.
    Projection generation follows this command and checks the complete binding.
    """
    destinations = _destinations(root)
    outputs = {name: render(root, name) for name in destinations}
    for name, text in outputs.items():
        with atomic_path(destinations[name]) as pending:
            pending.write_text(text, encoding="utf-8", newline="")
    return {name: digest(path) for name, path in destinations.items()}
