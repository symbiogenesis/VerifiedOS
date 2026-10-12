# SPDX-License-Identifier: Apache-2.0
"""Independent roster expectations and production projection substitution controls."""

import json
import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import boot, composer
from vos import composition as c
from vos.cli import composer as cli

ROOT = Path(__file__).resolve().parents[2]
IMAGES = ["mmode-firmware", "kernel", "supervisor", "crypto-core", "storage", "copy-service"]
SERVICES = ["crypto-core", "storage", "copy-service"]


def _write(root: Path, raw: dict[str, Any]) -> None:
    (root / c.EXAMPLE).write_bytes(composer.canonical_bytes(raw))


@contextmanager
def _sandbox() -> Iterator[tuple[Path, dict[str, Any]]]:
    raw = json.loads((ROOT / c.EXAMPLE).read_bytes())
    paths = {c.EXAMPLE, boot.CONTRACT, raw["configuration"]["path"], *c.PRODUCERS}
    for member in raw["members"]:
        paths.update(ref["path"] for ref in member["sources"])
    for producer in raw["producers"]:
        paths.update(ref["path"] for ref in producer["sources"])
    with tempfile.TemporaryDirectory(prefix="vos-composition-") as temporary:
        root = Path(temporary)
        for relative in paths:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        yield root, raw


def _refused(fn: Callable[[], object], phrase: str) -> None:
    try:
        fn()
    except (c.CompositionError, boot.RecipeError) as error:
        ensure(phrase in str(error), f"wrong refusal: {error}")
        return
    raise AssertionError(f"expected refusal: {phrase}")


def _real_roster() -> None:
    outputs = c.projections(ROOT)
    recipe = json.loads(outputs["recipe-members.json"])
    ensure([m["id"] for m in recipe["payload"]["members"]] == IMAGES,
           "six independently expected main-die members")
    manifest = json.loads(outputs["manifest.json"])
    ensure(manifest["payload"]["units"] == SERVICES, "independently expected service startup order")
    ensure(manifest["payload"]["order"] == [0, 1, 2], "immutable local-unit order")
    ensure(manifest["payload"]["edges"] == [0, 1, 0], "storage holds only crypto-core entry")
    ensure("const struct vos_supervisor_manifest vos_m8a_supervisor_manifest" in
           outputs["manifest.c"].decode("utf-8"), "manifest is immutable C source")
    graph = json.loads(outputs["graph-input.json"])["payload"]
    ensure(graph["document"] is None, "absent descriptors must not become a fabricated graph")
    request = json.loads(outputs["admission-request.json"])
    ensure(request["payload"]["image_sha256"] is None and request["payload"]["build_record"] is None,
           "artifact digests resolve only after the build")
    ensure(all(m["certificate"] is None for m in request["payload"]["members"]),
           "generated derivation references never become certificates")
    for name in ("manifest.json", "graph-input.json", "recipe-members.json", "admission-request.json"):
        ensure(json.loads(outputs[name])["binding"] == manifest["binding"], "one input/producer binding")
    _refused(lambda: c.require_production(ROOT), "production promotion refused")
    c.check(ROOT)


def _schema_and_membership() -> None:
    changes: list[tuple[Callable[[dict[str, Any]], None], str]] = [
        (lambda raw: raw.update(script="execute-me"), "composition schema"),
        (lambda raw: raw.update(schema_version=True), "composition schema"),
        (lambda raw: raw["members"].pop(), "real roster"),
        (lambda raw: raw["members"].append(raw["members"][0]), "real roster"),
        (lambda raw: raw["members"][4].update(package_id="storage"), "package identity"),
        (lambda raw: raw["members"][4].update(producer="nonexistent-producer"), "unknown producer"),
        (lambda raw: raw["members"][4].update(artifact_slot=raw["members"][5]["artifact_slot"]),
         "duplicate symbolic slot"),
        (lambda raw: raw["members"][7].update(admission_tier=0), "cannot certify themselves"),
    ]
    for change, message in changes:
        with _sandbox() as (root, raw):
            change(raw)
            _write(root, raw)
            _refused(lambda: c.load(root), message)
    with _sandbox() as (root, _raw):
        path = root / c.EXAMPLE
        path.write_bytes(b'{"schema_version":1,"schema_version":1}')
        _refused(lambda: c.load(root), "duplicate JSON key")


def _independent_relations() -> None:
    changes: list[tuple[Callable[[dict[str, Any]], None], str]] = [
        (lambda raw: raw["startup"].update(order=["storage", "crypto-core", "copy-service"]), "startup order"),
        (lambda raw: raw["startup"].update(dependencies=[]), "storage must depend"),
        (lambda raw: raw["supervisor"].update(authority=[]), "storage must depend"),
        (lambda raw: raw["startup"]["dependencies"].append({"member": "crypto-core", "requires": "storage"}),
         "conflicts with supervisor"),
        (lambda raw: raw["members"][5].update(imports={"tohost": "crypto-core"}), "invalid image import"),
        (lambda raw: raw["members"][5].update(imports={"entry": "storage"}), "invalid image import"),
        (lambda raw: raw["supervisor"]["policy"].update(restart_members=8), "manifest bounds"),
        (lambda raw: raw["supervisor"]["policy"].update(backoff=[6]), "manifest bounds"),
    ]
    for change, message in changes:
        with _sandbox() as (root, raw):
            change(raw)
            _write(root, raw)
            _refused(lambda: c.load(root), message)


def _partial_descriptor_refusals() -> None:
    for descriptor, phrase in (({"package_id": "storage", "desc_manifest": 0, "desc_edges": []},
                                "descriptor package identity"),
                               ({"package_id": "crypto-core", "desc_manifest": True, "desc_edges": []},
                                "malformed descriptor")):
        with _sandbox() as (root, raw):
            relative = "tools/composer/present-descriptor.json"
            (root / relative).write_bytes(composer.canonical_bytes(descriptor))
            raw["members"][4]["descriptor"] = c.reference(root, relative)
            _write(root, raw)
            _refused(lambda: c.load(root), phrase)


def _placement_refusals() -> None:
    with _sandbox() as (root, raw):
        memory = boot.regions(root / raw["configuration"]["path"])[0]
        placement = {"text_base": hex(memory.base), "text_bytes": 16,
                     "data_base": hex(memory.base + 32), "data_bytes": 16}
        raw["members"][1]["placement"] = placement
        raw["tohost"] = hex(memory.base + 64)
        _write(root, raw)
        c.load(root)
        raw["members"][2]["placement"] = dict(placement)
        _write(root, raw)
        _refused(lambda: c.load(root), "overlaps")
        raw["members"][2]["placement"] = None
        end = max(region.base + region.size for region in
                  boot.regions(root / raw["configuration"]["path"]))
        raw["members"][1]["placement"]["text_base"] = hex(end + 4096)
        _write(root, raw)
        _refused(lambda: c.load(root), "misplaced extent")
        raw["members"][1]["placement"] = None
        raw["tohost"] = hex(memory.base + 1)
        _write(root, raw)
        _refused(lambda: c.load(root), "misplaced extent")


def _stale_inputs_and_projections() -> None:
    with _sandbox() as (root, raw):
        c.emit(root, c.EXAMPLE, "out/project")
        c.check(root, c.EXAMPLE, "out/project")
        path = root / "out/project/manifest.c"
        path.write_bytes(path.read_bytes() + b"// substituted\n")
        _refused(lambda: c.check(root, c.EXAMPLE, "out/project"), "stale generated projection")
        c.emit(root, c.EXAMPLE, "out/project")
        raw["members"][5]["derivation"]["source"] = c.reference(root, "proofs/Sha256.v")
        _write(root, raw)
        _refused(lambda: c.check(root, c.EXAMPLE, "out/project"), "stale generated projection")
    with _sandbox() as (root, raw):
        path = root / raw["members"][0]["sources"][0]["path"]
        path.write_bytes(path.read_bytes() + b"\n")
        _refused(lambda: c.load(root), "stale source binding")
    with _sandbox() as (root, _raw):
        c.emit(root, c.EXAMPLE, "out/project")
        path = root / "tools/vos/composition.py"
        path.write_bytes(path.read_bytes() + b"\n")
        _refused(lambda: c.check(root, c.EXAMPLE, "out/project"), "stale generated projection")


def _resolve_descriptors(root: Path, raw: dict[str, Any]) -> bytes:
    raw["graph"] = {"type_count": 1, "intent_count": 1, "world_count": 1,
                    "inventory": [0], "verified_parsers": [0], "ring_depth_ceiling": 1}
    directory = root / "descriptors"
    directory.mkdir()
    for member in raw["members"]:
        relative = f"descriptors/{member['id']}.json"
        edges = []
        if member["id"] == "storage":
            edges = [{"edge_owner": 5, "edge_target": 4, "edge_intent": 0,
                      "edge_from": 0, "edge_to": 0, "edge_limit": 32, "edge_world": 0,
                      "edge_format": 0, "edge_bounds": 16, "edge_ring": 1}]
        (root / relative).write_bytes(composer.canonical_bytes(
            {"package_id": member["package_id"], "desc_manifest": 64, "desc_edges": edges}))
        member["descriptor"] = c.reference(root, relative)
    _write(root, raw)
    projected = json.loads(c.projections(root)["graph-input.json"])["payload"]["document"]
    return composer.graph_bytes(composer.parse_document(projected))


def _graph_owner_boundary() -> None:
    with _sandbox() as (root, raw):
        graph = json.loads(_resolve_descriptors(root, raw))
        ensure(graph["graph"]["graph_edges"][0]["edge_owner"] == 5, "storage is the typed handler owner")
        ensure(graph["graph"]["graph_edges"][0]["edge_target"] == 4, "separate typed handler targets crypto")
        raw["startup"]["dependencies"] = []
        _write(root, raw)
        _refused(lambda: c.load(root), "storage must depend")
        raw["startup"]["dependencies"] = [{"member": "storage", "requires": "crypto-core"}]
        descriptor = root / "descriptors/storage.json"
        value = json.loads(descriptor.read_bytes())
        value["desc_edges"][0]["edge_owner"] = 4
        descriptor.write_bytes(composer.canonical_bytes(value))
        raw["members"][5]["descriptor"] = c.reference(root, "descriptors/storage.json")
        _write(root, raw)
        _refused(lambda: c.load(root), "claims another owner")


def _build_bindings() -> None:
    with _sandbox() as (root, raw):
        graph = _resolve_descriptors(root, raw)
        directory = root / "products"
        directory.mkdir()
        artifacts = {}
        for member in raw["members"]:
            if member["id"] in ("composer", "admission"):
                continue
            relative = f"products/{member['id']}.bin"
            (root / relative).write_bytes(f"test-only bytes for {member['id']}".encode())
            artifacts[member["artifact_slot"]] = c.reference(root, relative)
        (directory / "image.bin").write_bytes(b"test-only composed image")
        image = c.reference(root, "products/image.bin")
        outputs = c.projections(root)
        record = c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph)
        c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image)
        ensure(record["production_admission"] is False, "build bindings cannot promote incomplete members")
        _refused(lambda: c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph + b" "),
                 "graph binding")
        changed_image = {**image, "sha256": "0" * 64}
        _refused(lambda: c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, changed_image),
                 "image binding")
        altered = {**record, "production_admission": True}
        _refused(lambda: c.validate_build_record(root, c.EXAMPLE, altered, outputs, graph, image),
                 "substituted binding")
        substituted = {**artifacts, "storage-artifact": artifacts["crypto-core-artifact"]}
        _refused(lambda: c.build_record(root, c.EXAMPLE, outputs, substituted, image, graph),
                 "substituted artifact")
        artifact = root / "products/storage.bin"
        original = artifact.read_bytes()
        artifact.write_bytes(original + b"changed")
        _refused(lambda: c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image),
                 "stale source binding")
        artifact.write_bytes(original)
        raw["members"][5]["derivation"]["source"] = c.reference(root, "proofs/Sha256.v")
        _write(root, raw)
        _refused(lambda: c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image),
                 "stale projection bindings")
        _write(root, json.loads((ROOT / c.EXAMPLE).read_bytes()))
        _refused(lambda: c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph),
                 "stale projection bindings")


def _artifact_path_substitutions() -> None:
    with _sandbox() as (root, raw):
        graph = _resolve_descriptors(root, raw)
        directory = root / "products"
        directory.mkdir()
        artifacts = {}
        for member in raw["members"]:
            if member["id"] in ("composer", "admission"):
                continue
            relative = f"products/{member['id']}.bin"
            (root / relative).write_bytes(b"identical test-only payload")
            artifacts[member["artifact_slot"]] = c.reference(root, relative)
        (directory / "image.bin").write_bytes(b"test-only composed image")
        image = c.reference(root, "products/image.bin")
        outputs = c.projections(root)
        record = c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph)
        c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image)
        ensure(len({ref["sha256"] for ref in artifacts.values()}) == 1,
               "distinct artifact files remain valid even when their bytes match")
        aliases = ["products/./crypto-core.bin", "products//crypto-core.bin"]
        if os.name == "nt":
            aliases.append("products/CRYPTO-CORE.bin")
        for alias in aliases:
            substituted = {**artifacts, "storage-artifact": c.reference(root, alias)}
            _refused(lambda substituted=substituted:
                     c.build_record(root, c.EXAMPLE, outputs, substituted, image, graph),
                     "substituted artifact")
            altered = {**record, "artifacts": substituted}
            _refused(lambda altered=altered:
                     c.validate_build_record(root, c.EXAMPLE, altered, outputs, graph, image),
                     "substituted artifact")


def _cli() -> None:
    with _sandbox() as (root, _raw), patch.object(cli.corpus, "find_root", return_value=root), redirect_stdout(StringIO()):
        ensure(cli.main(["project", c.EXAMPLE, "--output", "out/project"]) == 0, "projection CLI")
        ensure(cli.main(["check-project", c.EXAMPLE, "--output", "out/project"]) == 0, "check CLI")
        ensure(cli.main(["promote", c.EXAMPLE]) == 1, "incomplete production promotion CLI must refuse")
        ensure(cli.main(["project", c.EXAMPLE, "--output", "tools/other"]) == 1, "output containment")
        ensure(cli.main(["project", c.EXAMPLE, "--output", "../escape"]) == 1, "output cannot escape")


def cases() -> list[Case]:
    return [Case("real-roster-projections", _real_roster),
            Case("schema-and-membership", _schema_and_membership),
            Case("separate-startup-authority-imports", _independent_relations),
            Case("partial-descriptor-refusals", _partial_descriptor_refusals),
            Case("placement-refusals", _placement_refusals),
            Case("stale-inputs-and-projections", _stale_inputs_and_projections),
            Case("typed-handler-owner", _graph_owner_boundary),
            Case("post-build-byte-bindings", _build_bindings),
            Case("artifact-path-substitutions", _artifact_path_substitutions),
            Case("production-project-cli", _cli)]
