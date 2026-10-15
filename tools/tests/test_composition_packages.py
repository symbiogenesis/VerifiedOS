# SPDX-License-Identifier: Apache-2.0
"""Real component inventories preserve identities without inventing handler acts."""

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_composition import (
    ROOT,
    _rebind_inventory_source,
    _refused,
    _resolve_descriptors,
    _sandbox,
    _write,
)
from tests.test_composition_build_cli import PROJECT, _build, _check, _products
from vos import composer
from vos import composition as c


def _inventory(root: Path, raw: dict[str, Any], member: str = "supervisor") -> tuple[Path, dict[str, Any]]:
    declaration = next(item for item in raw["members"] if item["id"] == member)
    path = root / declaration["descriptor"]["path"]
    return path, json.loads(path.read_bytes())


def _save(root: Path, raw: dict[str, Any], path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(composer.canonical_bytes(value))
    member = next(item for item in raw["members"] if item["id"] == value["package_id"])
    member["descriptor"] = c.reference(root, path.relative_to(root).as_posix())
    _write(root, raw)


def _real_component_identities() -> None:
    output = json.loads(c.projections(ROOT)["graph-input.json"])
    slots = {item["member"]: item for item in output["payload"]["descriptor_slots"]}
    ensure({name for name, slot in slots.items() if slot["package"] is not None}
           == {"rot-firmware", "mmode-firmware", "kernel", "supervisor", "crypto-core",
               "storage", "copy-service", "composer", "admission"},
           "every real roster member has a source-owned inventory")
    supervisor = slots["supervisor"]["package"]
    copy = slots["copy-service"]["package"]
    ensure(supervisor["package_id"] == "supervisor" and copy["package_id"] == "copy-service",
           "real independently expected package identities")
    ensure({source["path"] for source in supervisor["sources"]} == {
        "supervisor/src/supervisor.c", "supervisor/src/context.c", "supervisor/include/vos_supervisor.h",
        "supervisor/include/vos_supervisor_context.h", "supervisor/include/vos_context_layout.h"},
        "bounded supervisor C and actual context ABI sources")
    ensure({item["id"]: item["source"]["path"] for item in copy["interfaces"]} == {
        "ring-reference": "interfaces/ring-reference.json",
        "copy-service-boundary": "copy-service/README.md"}, "copy boundary owners are existing artifacts")
    ensure(all(slot["package"]["handler_graph"] is None for slot in slots.values()),
           "real package identity does not invent handler intents or manifest bounds")
    ensure(output["payload"]["document"] is None and output["production_admission"] is False,
           "unresolved real roster yields neither a graph nor admission")
    package_sources = {item["member"]: item["sources"] for item in output["binding"]["package_sources"]}
    ensure(package_sources["supervisor"] == c._package_sources(supervisor),
           "transitive sources appear in the common projection binding")


def _roster_inventory_owners() -> None:
    output = json.loads(c.projections(ROOT)["graph-input.json"])
    slots = {item["member"]: item for item in output["payload"]["descriptor_slots"]}
    expected: dict[str, tuple[str, str]] = {
        "rot-firmware": ("firmware/chain/rom.c", "docs/implementation/contracts/boot-handoff.md"),
        "mmode-firmware": ("firmware/chain/mmode.c", "docs/implementation/contracts/purecap-abi.md"),
        "kernel": ("kernel/src/lifecycle.c", "kernel/README.md"),
        "supervisor": ("supervisor/src/context.c", "docs/implementation/contracts/supervisor-context.md"),
        "crypto-core": ("proofs/AesGcm.v", "docs/implementation/contracts/boot-roster.md"),
        "storage": ("proofs/StorageRecovery.v", "docs/implementation/storage-recovery-policy.md"),
        "copy-service": ("copy-service/src/copy_service.c", "interfaces/ring-reference.json"),
        "composer": ("tools/vos/composition.py", "tools/composer/composition.schema.json"),
        "admission": ("tools/vos/admission_production.py", "tools/admission/README.md"),
    }
    bindings = {item["member"]: item["sources"] for item in output["binding"]["package_sources"]}
    for name, (source, interface) in expected.items():
        package = slots[name]["package"]
        ensure(package["package_id"] == name, f"{name}: independent roster identity")
        ensure(source in {ref["path"] for ref in package["sources"]}, f"{name}: actual source owner")
        ensure(interface in {item["source"]["path"] for item in package["interfaces"]},
               f"{name}: actual interface owner")
        ensure(bindings[name] == c._package_sources(package), f"{name}: complete transitive bindings")
        ensure(all(c.reference(ROOT, ref["path"]) == ref for ref in bindings[name]),
               f"{name}: exact source bytes")
    for name in ("crypto-core", "storage"):
        ensure(all(ref["path"].startswith("proofs/") for ref in slots[name]["package"]["sources"]),
               f"{name}: statements do not borrow firmware code as a nonexistent compartment product")
    recipe = json.loads(c.projections(ROOT)["recipe-members.json"])["payload"]["members"]
    ensure(all(member["status"] != "executable" for member in recipe),
           "resolved inventories cannot promote the roster's target status")


def _roster_inventory_source_drift() -> None:
    names = ("rot-firmware", "mmode-firmware", "kernel", "crypto-core", "storage", "composer", "admission")
    for name in names:
        for role in ("sources", "interfaces"):
            with _sandbox() as (root, raw):
                _path, inventory = _inventory(root, raw, name)
                ref = inventory[role][0] if role == "sources" else inventory[role][0]["source"]
                path = root / ref["path"]
                path.write_bytes(path.read_bytes() + b"\n")
                _refused(lambda: c.projections(root), "stale source binding")


def _unresolved_wrapped_graph() -> None:
    with _sandbox() as (root, raw):
        path, inventory = _inventory(root, raw)
        _resolve_descriptors(root, raw)
        _save(root, raw, path, inventory)
        projected = json.loads(c.projections(root)["graph-input.json"])["payload"]
        ensure(projected["document"] is None,
               "one null wrapped handler slot withholds graph despite otherwise complete test descriptors")
        ensure(projected["descriptor_slots"][3]["package"]["handler_graph"] is None,
               "unresolved slot survives normalized projection")


def _wrapped_graph_agreement() -> None:
    with _sandbox() as (root, raw):
        path, inventory = _inventory(root, raw)
        baseline = _resolve_descriptors(root, raw)
        inventory["handler_graph"] = {"desc_manifest": 64, "desc_edges": []}
        _save(root, raw, path, inventory)
        graph = json.loads(c.projections(root)["graph-input.json"])["payload"]["document"]
        ensure(composer.graph_bytes(composer.parse_document(graph)) == baseline,
               "resolved test wrapper and direct reference descriptor produce identical graph bytes")
        edge = {"edge_owner": 3, "edge_target": 6, "edge_intent": 0, "edge_from": 0,
                "edge_to": 0, "edge_limit": 32, "edge_world": 0, "edge_format": 0,
                "edge_bounds": 16, "edge_ring": 1}
        inventory["handler_graph"]["desc_edges"] = [edge]
        _save(root, raw, path, inventory)
        graph = json.loads(c.projections(root)["graph-input.json"])["payload"]["document"]
        ensure(composer.compose(composer.parse_document(graph)).graph_edges[0].edge_owner == 3,
               "wrapper adapter retains real-roster owner index")
        for field, value, phrase in (("edge_owner", 4, "claims another owner"),
                                     ("edge_target", 9, "declared edge is refused"),
                                     ("edge_intent", 1, "declared edge is refused"),
                                     ("edge_bounds", 65, "declared edge is refused")):
            original = edge[field]
            edge[field] = value
            _save(root, raw, path, inventory)
            _refused(lambda: c.projections(root), phrase)
            edge[field] = original
        edge["edge_owner"] = 3.0
        _save(root, raw, path, inventory)
        _refused(lambda: c.projections(root), "malformed descriptor")
        edge["edge_owner"] = 3
        edge["undeclared"] = 0
        _save(root, raw, path, inventory)
        _refused(lambda: c.projections(root), "malformed descriptor")


def _inventory_shape_and_identity() -> None:
    changes = [
        lambda inventory: inventory.update(schema_version=1.0),
        lambda inventory: inventory.update(extra="execute-package"),
        lambda inventory: inventory.update(sources=[]),
        lambda inventory: inventory["interfaces"][0].update(extra="invented-export"),
        lambda inventory: inventory.update(handler_graph={"desc_manifest": 1.0, "desc_edges": []}),
        lambda inventory: inventory.update(handler_graph={"desc_manifest": 0, "desc_edges": [],
                                                          "package_id": "storage"}),
    ]
    for change in changes:
        with _sandbox() as (root, raw):
            path, inventory = _inventory(root, raw)
            change(inventory)
            _save(root, raw, path, inventory)
            _refused(lambda: c.projections(root), "package descriptor schema")
    with _sandbox() as (root, raw):
        path, inventory = _inventory(root, raw)
        inventory["interfaces"].append({**inventory["interfaces"][0], "source": inventory["sources"][0]})
        _save(root, raw, path, inventory)
        _refused(lambda: c.projections(root), "duplicate package interface identity")
    with _sandbox() as (root, raw):
        supervisor = raw["members"][3]
        supervisor["descriptor"] = raw["members"][6]["descriptor"]
        _write(root, raw)
        _refused(lambda: c.projections(root), "descriptor package identity")


def _transitive_source_drift() -> None:
    bind = c._binding
    for package, role in (("supervisor", "sources"), ("supervisor", "interfaces"),
                          ("copy-service", "sources"), ("copy-service", "interfaces")):
        with _sandbox() as (root, raw):
            inventory_path, inventory = _inventory(root, raw, package)
            ref = inventory[role][0] if role == "sources" else inventory[role][0]["source"]
            path = root / ref["path"]
            original = path.read_bytes()
            c.projections(root)
            path.write_bytes(original + b"\n")
            _refused(lambda: c.projections(root), "stale source binding")
            path.write_bytes(original)
            def drift_after_expansion(checkout: Path, declaration: dict[str, Any],
                                      input_binding: dict[str, str],
                                      roster_binding: dict[str, str], target: Path = path,
                                      snapshot: bytes = original) -> dict[str, object]:
                target.write_bytes(snapshot + b"\n")
                return bind(checkout, declaration, input_binding, roster_binding)
            with patch.object(c, "_binding", drift_after_expansion):
                _refused(lambda: c.projections(root), "stale source binding")
            path.write_bytes(original)
            unchanged = c.projections(root)
            path.write_bytes(original + b"\n")
            ref.update(c.reference(root, ref["path"]))
            _save(root, raw, inventory_path, inventory)
            _rebind_inventory_source(root, raw, ref["path"])
            rebound = c.projections(root)
            ensure(unchanged != rebound, "deliberately rebound source changes dependent projection identities")
            ensure(json.loads(rebound["graph-input.json"])["payload"]["document"] is None,
                   "rebound package sources preserve the unresolved graph boundary")


def _transitive_publication_collisions() -> None:
    for role in ("sources", "interfaces"):
        for hardlink in (False, True):
            with _sandbox() as (root, raw):
                path, inventory = _inventory(root, raw)
                ref = inventory[role][0] if role == "sources" else inventory[role][0]["source"]
                original = root / ref["path"]
                destination = root / "out/project"
                destination.mkdir(parents=True)
                for name in c.OUTPUTS:
                    (destination / name).write_bytes(b"retained previous projection")
                alias = destination / c.OUTPUTS[-1]
                if hardlink:
                    alias.unlink()
                    os.link(original, alias)
                else:
                    alias.write_bytes(original.read_bytes())
                    ref.update(c.reference(root, alias.relative_to(root).as_posix()))
                    _save(root, raw, path, inventory)
                before = {file: file.read_bytes() for file in root.rglob("*") if file.is_file()}
                _refused(lambda: c.emit(root, c.EXAMPLE, "out/project"), "overwrite a composition source")
                ensure(before == {file: file.read_bytes() for file in root.rglob("*") if file.is_file()},
                       "transitive alias refuses before any projection or consumed bytes change")


def _transitive_build_record_collisions() -> None:
    for role in ("sources", "interfaces"):
        for hardlink in (False, True):
            with _products() as root:
                raw = json.loads((root / c.EXAMPLE).read_bytes())
                path = root / "tools/composer/packages/supervisor.json"
                inventory = json.loads(path.read_bytes())
                inventory["handler_graph"] = {"desc_manifest": 64, "desc_edges": []}
                ref = inventory[role][0] if role == "sources" else inventory[role][0]["source"]
                source = root / ref["path"]
                alias = root / "out/package-source.bin"
                if hardlink:
                    os.link(source, alias)
                else:
                    alias.write_bytes(source.read_bytes())
                    ref.update(c.reference(root, alias.relative_to(root).as_posix()))
                _save(root, raw, path, inventory)
                c.emit(root, c.EXAMPLE, PROJECT)
                code, output = _build(root)
                ensure(code == 0, output)
                code, output = _check(root)
                ensure(code == 0, output)
                before = {file: file.read_bytes() for file in root.rglob("*") if file.is_file()}
                code, output = _build(root, alias.relative_to(root).as_posix())
                ensure(code == 1 and "overwrite an input or product" in output, output)
                ensure(before == {file: file.read_bytes() for file in root.rglob("*") if file.is_file()},
                       "build record cannot replace a package source through an alias or hardlink")


def cases() -> list[Case]:
    return [Case("real-component-package-identities", _real_component_identities),
            Case("roster-package-source-and-interface-owners", _roster_inventory_owners),
            Case("roster-package-source-drift", _roster_inventory_source_drift),
            Case("unresolved-handler-slot-withholds-graph", _unresolved_wrapped_graph),
            Case("wrapped-direct-graph-agreement", _wrapped_graph_agreement),
            Case("package-schema-and-identity", _inventory_shape_and_identity),
            Case("transitive-source-publication-drift", _transitive_source_drift),
            Case("transitive-source-output-aliases", _transitive_publication_collisions),
            Case("transitive-build-record-output-aliases", _transitive_build_record_collisions)]
