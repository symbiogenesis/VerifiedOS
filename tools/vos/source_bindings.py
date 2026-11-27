# SPDX-License-Identifier: Apache-2.0
"""Declared source identities shared by composition and admission views.

The ordered groups below declare entrypoints and non-Python inputs. Packages,
production-input references and receipt inventories add the current local Python
import closure to their role-specific views without executing those sources.
Generated JSON retains its other authored choices; no generator assigns handlers,
products, admission tiers or proof evidence.
"""

import ast
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from vos import copy_package_sources, python_dependencies
from vos.jsonutil import unique_object
from vos.receipts import atomic_path, digest

OWNER: Final = "tools/vos/source_bindings.py"
COMPOSITION: Final = "tools/composer/m8a-composition.json"
PACKAGE_FILES: Final[dict[str, str]] = {
    name: f"tools/composer/packages/{name}.json" for name in ("composer", "admission", "copy-service")}

# Python helpers derive from imports; other inputs remain explicit. Ordered group
# expansion and sorted Python closures keep source manifests deterministic.
GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "shared": (OWNER, "proofs/ProofSupport.v", "tools/pyproject.toml", "tools/uv.lock"),
    "composer-reference": ("@shared", "tools/vos/composer.py", "proofs/HandlerGraph.v"),
    "admission-reference": ("@shared", "tools/vos/admission.py", "proofs/AdmissionPath.v"),
    "composer-package": ("@projection", "tools/vos/cli/composer.py",
                         "tools/composer/fixed-package.schema.json",
                         "tools/composer/fixed-composition.schema.json"),
    "admission-package": ("@admission-reference", "@projection", "tools/vos/cli/admission.py",
                          "tools/vos/package_admission.py", "tools/composer/fixed-package.schema.json",
                          "tools/admission/production-population.json", "docs/requirements-register.md"),
    "copy-service-package": ("@shared",),
    "projection": ("@composer-reference", "tools/vos/composition.py",
                   "tools/composer/composition.schema.json", "tools/composer/package.schema.json",
                   "tools/generated/dialect-table.json"),
    "admission-comparison": ("@admission-package",),
    "admission-production": ("@admission-package",),
    "boot-composition": ("@composer-reference", "@admission-reference"),
    "math-shapes": ("@composer-reference", "tools/vos/math_evidence.py"),
}

PRODUCER_VIEWS: Final[dict[str, str]] = {
    "offline-reference-composer": "composer-reference",
    "offline-reference-admission": "admission-reference"}


class SourceBindingError(ValueError):
    """A declared inventory cannot be generated or published at its boundary."""


@dataclass
class _Session:
    """Per-call cache so one expansion or render shares AST/digest work without persisting state."""

    root: Path
    root_resolved: Path
    digests: dict[str, str] = field(default_factory=dict)
    parsed: dict[Path, tuple[ast.Module, frozenset[str]]] = field(default_factory=dict)
    regular_cache: dict[Path, bool] = field(default_factory=dict)
    module_cache: dict[str, Path | None] = field(default_factory=dict)
    view_sources: dict[str, tuple[str, ...]] = field(default_factory=dict)
    view_refs: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    rendered_packages: dict[str, str] = field(default_factory=dict)


def _new_session(root: Path) -> _Session:
    return _Session(root=root, root_resolved=root.resolve())


def _sources(view: str, session: _Session) -> tuple[str, ...]:
    cached = session.view_sources.get(view)
    if cached is not None:
        return cached
    root = session.root
    found: dict[str, None] = {}

    def visit(name: str, active: tuple[str, ...]) -> None:
        if name in active:
            raise SourceBindingError(f"recursive source-binding group: {name}")
        if name not in GROUPS:
            raise SourceBindingError(f"unknown source-binding group: {name}")
        members = GROUPS[name]
        if name == "copy-service-package":
            copy_sources = tuple(sorted({
                *(f"copy-service/{item}" for item in
                  (*copy_package_sources.C_FILES, *copy_package_sources.ADAPTERS)),
                *copy_package_sources.DATA_INPUTS,
                *python_dependencies._sources(
                    root, copy_package_sources.ENTRYPOINTS,
                    parsed=session.parsed, regular_cache=session.regular_cache,
                    module_cache=session.module_cache),
            }))
            members = (*members, *copy_sources)
        if not members or len(members) != len(set(members)):
            raise SourceBindingError(f"empty or repeated source-binding group members: {name}")
        for member in members:
            if member.startswith("@"):
                visit(member[1:], (*active, name))
            else:
                found[member] = None

    visit(view, ())
    python = tuple(name for name in found if name.endswith(".py"))
    try:
        imported = python_dependencies._sources(
            root, python, parsed=session.parsed, regular_cache=session.regular_cache,
            module_cache=session.module_cache)
    except ValueError as error:
        raise SourceBindingError(f"{view}: {error}") from error
    result = tuple(dict.fromkeys((*found, *imported)))
    session.view_sources[view] = result
    return result


def sources(view: str, *, root: Path | None = None) -> tuple[str, ...]:
    """Expand current imports and declared inputs in the selected checkout."""
    selected = Path(__file__).resolve().parents[2] if root is None else root
    return _sources(view, _new_session(selected))


def _digest_for(session: _Session, relative: str) -> str:
    cached = session.digests.get(relative)
    if cached is None:
        cached = digest(_path(session.root, relative, root_resolved=session.root_resolved))
        session.digests[relative] = cached
    return cached


def _references(session: _Session, view: str) -> list[dict[str, str]]:
    cached = session.view_refs.get(view)
    if cached is None:
        cached = [{"path": name, "sha256": _digest_for(session, name)}
                  for name in _sources(view, session)]
        session.view_refs[view] = cached
    return [{"path": item["path"], "sha256": item["sha256"]} for item in cached]


def references(root: Path, view: str) -> list[dict[str, str]]:
    """Bind the current bytes of a declared view; missing members are errors."""
    return _references(_new_session(root), view)


def _path(root: Path, relative: str, *, root_resolved: Path | None = None) -> Path:
    selected = (root / relative).resolve()
    resolved_root = root.resolve() if root_resolved is None else root_resolved
    if (Path(relative).is_absolute() or "\\" in relative or ".." in Path(relative).parts
            or not selected.is_relative_to(resolved_root)):
        raise SourceBindingError(f"source-binding path must stay relative to the checkout: {relative}")
    return selected


def _read(root: Path, relative: str, *, root_resolved: Path | None = None) -> dict[str, Any]:
    raw = json.loads(_path(root, relative, root_resolved=root_resolved).read_bytes(),
                     object_pairs_hook=unique_object)
    if not isinstance(raw, dict):
        raise SourceBindingError(f"source-binding input must be an object: {relative}")
    return raw


def _interface_sources(raw: dict[str, Any]) -> list[dict[str, Any]]:
    interfaces = raw.get("interfaces")
    if not isinstance(interfaces, list):
        raise SourceBindingError("source-binding interfaces must be an array")
    sources: list[dict[str, Any]] = []
    for interface in interfaces:
        source = interface.get("source") if isinstance(interface, dict) else None
        if not isinstance(source, dict) or not isinstance(source.get("path"), str):
            raise SourceBindingError("source-binding interface must name a source path")
        sources.append(source)
    return sources


def _render(session: _Session, relative: str) -> str:
    root = session.root
    package = next((name for name, path in PACKAGE_FILES.items() if path == relative), None)
    if package is not None:
        cached = session.rendered_packages.get(relative)
        if cached is not None:
            return cached
        raw = _read(root, relative, root_resolved=session.root_resolved)
        if raw.get("package_id") != package:
            raise SourceBindingError(f"source-binding package identity disagrees: {relative}")
        raw["sources"] = _references(session, f"{package}-package")
        for source in _interface_sources(raw):
            source["sha256"] = _digest_for(session, source["path"])
        rendered = json.dumps(raw, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        session.rendered_packages[relative] = rendered
        return rendered
    if relative == COMPOSITION:
        raw = _read(root, relative, root_resolved=session.root_resolved)
        for kind in ("producers", "members"):
            items = raw.get(kind)
            if not isinstance(items, list) or any(
                    not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in items):
                raise SourceBindingError(f"source-binding {kind} must be an array of identified objects")
        for producer, view in PRODUCER_VIEWS.items():
            matches = [item for item in raw["producers"] if item["id"] == producer]
            if len(matches) != 1:
                raise SourceBindingError(f"source-binding producer must occur once: {producer}")
            matches[0]["sources"] = _references(session, view)
        for package, path in PACKAGE_FILES.items():
            matches = [item for item in raw["members"] if item["id"] == package]
            if len(matches) != 1:
                raise SourceBindingError(f"source-binding member must occur once: {package}")
            # Bind the generated package bytes, including its authored interfaces.
            # Do not repair an independently selected descriptor into another file.
            descriptor = matches[0].get("descriptor")
            if not isinstance(descriptor, dict) or descriptor.get("path") != path:
                raise SourceBindingError(f"source-binding package path disagrees: {package}")
            matches[0]["sources"] = _references(session, f"{package}-package")
            matches[0]["descriptor"]["sha256"] = hashlib.sha256(_render(session, path).encode("utf-8")).hexdigest()
        return json.dumps(raw, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    raise SourceBindingError(f"no declared source-binding artifact: {relative}")


def render(root: Path, relative: str) -> str:
    """Regenerate owned source fields, preserving all other authored choices."""
    return _render(_new_session(root), relative)


def _destinations(session: _Session) -> dict[str, Path]:
    """Preflight every output against containment, peers and bound source inputs."""
    root = session.root
    destinations: dict[str, Path] = {}
    views = [*(f"{package}-package" for package in PACKAGE_FILES), *PRODUCER_VIEWS.values()]
    inputs = {_path(root, name, root_resolved=session.root_resolved)
              for view in views for name in _sources(view, session)}
    inputs.update(_path(root, source["path"], root_resolved=session.root_resolved)
                  for relative in PACKAGE_FILES.values()
                  for source in _interface_sources(_read(root, relative, root_resolved=session.root_resolved)))
    for name in (*PACKAGE_FILES.values(), COMPOSITION):
        selected = _path(root, name, root_resolved=session.root_resolved)
        peers = [*destinations.values(), *inputs]
        if any(selected == peer or (selected.exists() and peer.exists() and selected.samefile(peer))
               for peer in peers):
            raise SourceBindingError(f"source-binding destination aliases another output or bound source: {name}")
        destinations[name] = selected
    return destinations


def emit(root: Path) -> dict[str, str]:
    """Compute every declared view before publishing the fixed inventory paths.

    Each file is replaced atomically; the set is not a filesystem transaction.
    Projection generation follows this command and checks the complete binding.
    """
    session = _new_session(root)
    destinations = _destinations(session)
    outputs = {name: _render(session, name) for name in destinations}
    for name, text in outputs.items():
        with atomic_path(destinations[name]) as pending:
            pending.write_text(text, encoding="utf-8", newline="")
    return {name: digest(path) for name, path in destinations.items()}
