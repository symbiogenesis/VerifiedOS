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
from vos import boot, composer, jsonc
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


def _integer_input_boundary() -> None:
    # Manifest fields are uint32_t values, including the closed policy arrays.
    # Exact integer limits remain valid and unresolved target slots remain null.
    with _sandbox() as (root, raw):
        policy = raw["supervisor"]["policy"]
        policy["threshold"] = [4294967295] * 8
        policy["clear_threshold"] = [0] * 8
        policy["min_dwell"] = 4294967295
        policy["backoff"] = [0, 4294967295]
        policy["ceiling"] = 4294967295
        raw["inst_limit"] = 4294967295
        raw["members"][1]["admission_tier"] = 2
        _write(root, raw)
        output = c.projections(root)["manifest.c"].decode("utf-8")
        ensure("{4294967295, 4294967295" in output and "4294967295.0" not in output,
               "integer manifest limits retain integer C literals")
        ensure(c.load(root)["members"][1]["placement"] is None,
               "unresolved target slots retain null")
    changes: list[Callable[[dict[str, Any]], None]] = [
        lambda raw: raw.update(schema_version=1.0),
        lambda raw: raw["supervisor"]["policy"].update(min_dwell=1.0),
        lambda raw: raw["supervisor"]["policy"].update(threshold=[1.0] * 8),
        lambda raw: raw["supervisor"]["policy"].update(backoff=[0.0]),
        lambda raw: raw["members"][1].update(admission_tier=1.0),
        lambda raw: raw.update(inst_limit=1.0),
        lambda raw: raw.update(graph={"type_count": 1.0, "intent_count": 1, "world_count": 1,
                                      "inventory": [0], "verified_parsers": [0], "ring_depth_ceiling": 1}),
        lambda raw: raw.update(graph={"type_count": 1, "intent_count": 1, "world_count": 1,
                                      "inventory": [0.0], "verified_parsers": [0], "ring_depth_ceiling": 1}),
    ]
    for change in changes:
        with _sandbox() as (root, raw):
            change(raw)
            _write(root, raw)
            _refused(lambda: c.projections(root), "composition schema")
    with _sandbox() as (root, raw):
        memory = boot.regions(root / raw["configuration"]["path"])[0]
        raw["members"][1]["placement"] = {
            "text_base": hex(memory.base), "text_bytes": 16,
            "data_base": hex(memory.base + 32), "data_bytes": 16}
        raw["graph_placement"] = {"base": hex(memory.base + 64), "bytes": 16}
        _write(root, raw)
        c.load(root)
        raw["members"][1]["placement"]["text_bytes"] = 16.0
        _write(root, raw)
        _refused(lambda: c.projections(root), "composition schema")
        raw["members"][1]["placement"]["text_bytes"] = 16
        raw["graph_placement"] = {"base": hex(memory.base + 64), "bytes": 16.0}
        _write(root, raw)
        _refused(lambda: c.projections(root), "composition schema")


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


def _configuration_snapshot_binding() -> None:
    with _sandbox() as (root, raw):
        path = root / str(raw["configuration"]["path"])
        original = path.read_bytes()
        regions = boot.regions(path)
        outside = max(region.base + region.size for region in regions) + 4096
        raw["members"][1]["placement"] = {
            "text_base": hex(outside), "text_bytes": 16,
            "data_base": hex(outside + 32), "data_bytes": 16}
        _write(root, raw)
        _refused(lambda: c.load(root), "misplaced extent")
        changed = json.loads(jsonc.strip_comments(original.decode("utf-8")))
        region = next(region for region in changed["memory"]["regions"]
                      if region["attributes"]["mem_type"] == "MainMemory")
        region["base"]["value"] = hex(outside)
        region["size"]["value"] = "0x10000"
        substituted = composer.canonical_bytes(changed)
        read_bytes, read_text = Path.read_bytes, Path.read_text
        for consume in (c.load, c.projections):
            reads = 0
            def transient_bytes(candidate: Path) -> bytes:
                nonlocal reads
                if candidate == path:
                    reads += 1
                    return original if reads == 1 else substituted
                return read_bytes(candidate)
            def transient_text(candidate: Path, encoding: str | None = None,
                               errors: str | None = None, newline: str | None = None) -> str:
                nonlocal reads
                if candidate == path:
                    reads += 1
                    return substituted.decode("utf-8")
                return read_text(candidate, encoding=encoding, errors=errors, newline=newline)
            with patch.object(Path, "read_bytes", transient_bytes), patch.object(Path, "read_text", transient_text):
                _refused(lambda consume=consume: consume(root), "stale source binding")
            ensure(reads >= 2, "control reaches configuration parsing after digest validation")
        for data in (substituted, ("// reformatted bound configuration\n" +
                                  json.dumps(changed, indent=3)).encode("utf-8")):
            path.write_bytes(data)
            raw["configuration"] = c.reference(root, raw["configuration"]["path"])
            _write(root, raw)
            c.load(root)
            recipe = json.loads(c.projections(root)["recipe-members.json"])
            ensure(recipe["binding"]["configuration"]["sha256"] == c.digest(data),
                   "accepted placements bind exact configuration bytes, including JSONC formatting")
            ensure(boot.regions(path)[0].base == outside, "direct region callers retain JSONC parsing")


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


def _descriptor_snapshot_binding() -> None:
    with _sandbox() as (root, raw):
        _resolve_descriptors(root, raw)
        descriptor = root / "descriptors/storage.json"
        read_bytes = Path.read_bytes
        original = read_bytes(descriptor)
        changed = json.loads(original)
        changed["desc_manifest"] -= 1
        substituted = composer.canonical_bytes(changed)
        ensure(c.digest(original) != c.digest(substituted), "control substitutes descriptor bytes")
        for consume in (c.load, c.projections):
            reads = 0
            def transient_read(path: Path) -> bytes:
                nonlocal reads
                if path == descriptor:
                    reads += 1
                    # The declared binding reads its actual bytes; the parser
                    # subsequently sees a different, otherwise valid descriptor.
                    return original if reads == 1 else substituted
                return read_bytes(path)
            with patch.object(Path, "read_bytes", transient_read):
                _refused(lambda consume=consume: consume(root), "stale source binding")
            ensure(reads >= 2, "control reaches the descriptor parser after binding")
            consume(root)


def _composition_snapshot_binding() -> None:
    with _sandbox() as (root, raw):
        path = root / c.EXAMPLE
        original = path.read_bytes()
        changed = json.loads(original)
        changed["supervisor"]["policy"]["min_dwell"] = 11
        relation = {"member": "copy-service", "requires": "storage"}
        changed["startup"]["dependencies"].append(relation)
        changed["supervisor"]["authority"].append(relation)
        substituted = composer.canonical_bytes(changed)
        read_bytes = Path.read_bytes
        reads = 0
        def transient_read(candidate: Path) -> bytes:
            nonlocal reads
            if candidate == path:
                reads += 1
                return original if reads == 1 else substituted
            return read_bytes(candidate)
        with patch.object(Path, "read_bytes", transient_read):
            _refused(lambda: c.projections(root), "stale source binding")
        ensure(reads >= 2, "control reaches binding after parsing the composition")
        for data, dwell, edges in ((original, 2, [0, 1, 0]),
                                  (substituted, 11, [0, 1, 2]),
                                  (json.dumps(changed, indent=3).encode("utf-8"), 11, [0, 1, 2])):
            path.write_bytes(data)
            outputs = c.projections(root)
            manifest = json.loads(outputs["manifest.json"])
            ensure(manifest["payload"]["policy"]["min_dwell"] == dwell,
                   "manifest follows the actual composition snapshot")
            ensure(manifest["payload"]["edges"] == edges,
                   "authority projection follows independently expected relations")
            for name in ("manifest.json", "graph-input.json", "recipe-members.json", "admission-request.json"):
                ensure(json.loads(outputs[name])["binding"]["input"] ==
                       {"path": c.EXAMPLE, "sha256": c.digest(data)},
                       "all projections bind exact input bytes, including formatting")
        ensure(raw["supervisor"]["policy"]["min_dwell"] == 2, "original fixture policy is unchanged")


def _build_composition_snapshot_binding() -> None:
    with _sandbox() as (root, raw):
        graph = _resolve_descriptors(root, raw)
        directory = root / "products"
        directory.mkdir()
        artifacts = {}
        for member in raw["members"]:
            if member["id"] in ("composer", "admission"):
                continue
            relative = f"products/{member['id']}.bin"
            (root / relative).write_bytes(member["id"].encode("utf-8"))
            artifacts[member["artifact_slot"]] = c.reference(root, relative)
        (directory / "image.bin").write_bytes(b"test-only composed image")
        image = c.reference(root, "products/image.bin")
        outputs = c.projections(root)
        path = root / c.EXAMPLE
        original = path.read_bytes()
        changed = json.loads(original)
        changed["supervisor"]["policy"]["min_dwell"] = 11
        substituted = composer.canonical_bytes(changed)
        read_bytes = Path.read_bytes
        record = c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph)
        for stable_reads in (1, 2):
            for consume in (lambda: c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph),
                            lambda: c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image)):
                reads = 0
                def transient_read(candidate: Path, unchanged_reads: int = stable_reads) -> bytes:
                    nonlocal reads
                    if candidate == path:
                        reads += 1
                        return original if reads <= unchanged_reads else substituted
                    return read_bytes(candidate)
                with patch.object(Path, "read_bytes", transient_read):
                    _refused(consume, "stale source binding")
                ensure(reads > stable_reads, "control reaches the build-record binding boundary")
        for data in (original, json.dumps(raw, indent=3).encode("utf-8")):
            path.write_bytes(data)
            outputs = c.projections(root)
            record = c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph)
            c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image)
            ensure(json.loads(composer.canonical_bytes(record))["binding"]["input"] ==
                   {"path": c.EXAMPLE, "sha256": c.digest(data)},
                   "build record binds the same exact input snapshot as its projections")
        configuration = root / str(raw["configuration"]["path"])
        config_bytes = configuration.read_bytes()
        changed_config = config_bytes + b"\n// substituted configuration identity\n"
        read_text = Path.read_text
        for stable_reads in (1, 2):
            for consume in (lambda: c.projections(root),
                            lambda: c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph),
                            lambda: c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image)):
                reads = 0
                def config_read(candidate: Path, unchanged_reads: int = stable_reads) -> bytes:
                    nonlocal reads
                    if candidate == configuration:
                        reads += 1
                        return config_bytes if reads <= unchanged_reads else changed_config
                    return read_bytes(candidate)
                def config_text(candidate: Path, encoding: str | None = None,
                                errors: str | None = None, newline: str | None = None) -> str:
                    nonlocal reads
                    if candidate == configuration:
                        reads += 1
                        return changed_config.decode("utf-8")
                    return read_text(candidate, encoding=encoding, errors=errors, newline=newline)
                with patch.object(Path, "read_bytes", config_read), patch.object(Path, "read_text", config_text):
                    _refused(consume, "stale source binding")
                ensure(reads > stable_reads, "configuration drift refuses before projection or build publication")
        c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image)


def _declared_source_drift_case(kind: str) -> None:
    with _sandbox() as (root, raw):
        relative = "sources/declared.txt"
        path = root / relative
        path.parent.mkdir()
        original = b"independent declared source bytes\n"
        path.write_bytes(original)
        ref = {"path": relative, "sha256": c.digest(original)}
        member = raw["members"][5]
        if kind == "member":
            member["sources"].append(ref)
        elif kind == "producer":
            raw["producers"].append({"id": "test-producer", "sources": [ref]})
            member["producer"] = "test-producer"
        else:
            member["derivation"]["source"] = ref
        graph = _resolve_descriptors(root, raw)
        directory = root / "products"
        directory.mkdir()
        artifacts = {}
        for runtime in raw["members"]:
            if runtime["id"] in ("composer", "admission"):
                continue
            product = f"products/{runtime['id']}.bin"
            (root / product).write_bytes(runtime["id"].encode("utf-8"))
            artifacts[runtime["artifact_slot"]] = c.reference(root, product)
        (directory / "image.bin").write_bytes(b"test-only composed image")
        image = c.reference(root, "products/image.bin")
        outputs = c.projections(root)
        record = c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph)
        c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image)
        ensure(record["projections"] == {name: c.digest(data) for name, data in outputs.items()},
               "build record binds every projection carrying the declared source")
        recipe = json.loads(outputs["recipe-members.json"])
        storage = next(item for item in recipe["payload"]["members"] if item["id"] == "storage")
        if kind == "member":
            ensure(ref in storage["sources"], "projection retains the independently bound member source")
        elif kind == "producer":
            expected = {"id": "test-producer", "sources": [ref]}
            ensure(expected in recipe["binding"]["member_producers"],
                   "projection retains the independently bound producer source")
            binding = record["binding"]
            ensure(isinstance(binding, dict) and expected in binding["member_producers"],
                   "build record retains the independently bound producer source")
        else:
            request = json.loads(outputs["admission-request.json"])
            admitted = next(item for item in request["payload"]["members"] if item["member"] == "storage")
            ensure(admitted["derivation"]["source"] == ref,
                   "request retains the independently bound derivation source without certifying it")
        read_bytes = Path.read_bytes
        consumers = (lambda: c.projections(root),
                     lambda: c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph),
                     lambda: c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image))
        for position, consume in enumerate(consumers):
            for stable_reads in ((1,) if position == 0 else (1, 2)):
                reads = 0
                def transient_read(candidate: Path, unchanged_reads: int = stable_reads) -> bytes:
                    nonlocal reads
                    if candidate == path:
                        reads += 1
                        return original if reads <= unchanged_reads else original + b"substitution\n"
                    return read_bytes(candidate)
                with patch.object(Path, "read_bytes", transient_read):
                    _refused(consume, "stale source binding")
                ensure(reads > stable_reads, "declared source is rechecked before publication")
            consume()
        graph_builder = c._graph
        graphs = 0
        def substitute_after_graph(checkout: Path, declaration: dict[str, Any]) -> composer.CompositionInput | None:
            nonlocal graphs
            result = graph_builder(checkout, declaration)
            graphs += 1
            if graphs == 2:
                path.write_bytes(original + b"substitution after graph expansion\n")
            return result
        try:
            with patch.object(c, "_graph", substitute_after_graph):
                _refused(lambda: c.projections(root), "stale source binding")
            ensure(graphs == 2, "publication recheck follows the projection's graph expansion")
        finally:
            path.write_bytes(original)
        ensure(c.projections(root) == outputs, "unchanged declarations retain every projection byte")
        c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image)


def _declared_source_drift() -> None:
    for kind in ("member", "producer", "derivation"):
        _declared_source_drift_case(kind)


def _partial_graph_edge_refusals() -> None:
    # An unresolved peer withholds the graph, not checks whose inputs are known.
    with _sandbox() as (root, raw):
        _resolve_descriptors(root, raw)
        raw["members"][2]["descriptor"] = None
        _write(root, raw)
        ensure(json.loads(c.projections(root)["graph-input.json"])["payload"]["document"] is None,
               "a valid present edge cannot fabricate an unresolved peer descriptor")
        descriptor = root / "descriptors/storage.json"
        original = descriptor.read_bytes()
        for field, value in (("edge_target", len(raw["members"])), ("edge_limit", 0),
                             ("edge_intent", 1), ("edge_from", 1), ("edge_to", 1),
                             ("edge_world", 1), ("edge_format", 1), ("edge_bounds", 65),
                             ("edge_ring", 0), ("edge_ring", 2)):
            changed = json.loads(original)
            changed["desc_edges"][0][field] = value
            descriptor.write_bytes(composer.canonical_bytes(changed))
            raw["members"][5]["descriptor"] = c.reference(root, "descriptors/storage.json")
            _write(root, raw)
            _refused(lambda: c.load(root), "declared edge is refused")
        descriptor.write_bytes(original)
        raw["members"][5]["descriptor"] = c.reference(root, "descriptors/storage.json")
        for field in ("inventory", "verified_parsers"):
            raw["graph"][field] = []
            _write(root, raw)
            _refused(lambda: c.load(root), "declared edge is refused")
            raw["graph"][field] = [0]
        raw["graph"] = None
        _write(root, raw)
        ensure(json.loads(c.projections(root)["graph-input.json"])["payload"]["document"] is None,
               "absent graph choices remain unresolved")


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
        malformed_records: list[object] = [None, [], [record], False, True, 0, 1, 1.0,
                                          "production-composition-build-bindings", ""]
        malformed_records.extend({key: value for key, value in record.items() if key != missing}
                                 for missing in record)
        malformed_records.append({**record, "certificate": True})
        for malformed in malformed_records:
            _refused(lambda malformed=malformed:
                     c.validate_build_record(root, c.EXAMPLE, malformed, outputs, graph, image),
                     "malformed record")
        c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image)
        malformed_maps: list[Any] = [None, [], [artifacts], False, 1, "storage-artifact"]
        for malformed in malformed_maps:
            _refused(lambda malformed=malformed:
                     c.build_record(root, c.EXAMPLE, outputs, malformed, image, graph),
                     "malformed artifact map")
            altered = {**record, "artifacts": malformed}
            _refused(lambda altered=altered:
                     c.validate_build_record(root, c.EXAMPLE, altered, outputs, graph, image),
                     "malformed artifact map")
        valid = artifacts["storage-artifact"]
        malformed_refs: list[Any] = [None, [], "products/storage.bin",
                                    {"path": valid["path"]}, {"sha256": valid["sha256"]},
                                    {**valid, "certificate": True},
                                    {**valid, "path": False}, {**valid, "path": 1.0},
                                    {**valid, "sha256": False}, {**valid, "sha256": 1.0}]
        for malformed in malformed_refs:
            substituted = {**artifacts, "storage-artifact": malformed}
            _refused(lambda substituted=substituted:
                     c.build_record(root, c.EXAMPLE, outputs, substituted, image, graph),
                     "malformed source binding")
            altered = {**record, "artifacts": substituted}
            _refused(lambda altered=altered:
                     c.validate_build_record(root, c.EXAMPLE, altered, outputs, graph, image),
                     "malformed source binding")
            _refused(lambda malformed=malformed:
                     c.build_record(root, c.EXAMPLE, outputs, artifacts, malformed, graph),
                     "malformed source binding")
            altered = {**record, "image": malformed}
            _refused(lambda altered=altered, malformed=malformed:
                     c.validate_build_record(root, c.EXAMPLE, altered, outputs, graph, malformed),
                     "malformed source binding")
        for field, value in (("schema_version", True), ("schema_version", 1.0),
                             ("production_admission", 0), ("production_admission", 0.0)):
            altered = {**record, field: value}
            _refused(lambda altered=altered:
                     c.validate_build_record(root, c.EXAMPLE, altered, outputs, graph, image),
                     "substituted binding")
        for value in ({False}, float("nan")):
            altered = {**record, "production_admission": value}
            _refused(lambda altered=altered:
                     c.validate_build_record(root, c.EXAMPLE, altered, outputs, graph, image),
                     "malformed record")
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
            Case("exact-integer-input-boundary", _integer_input_boundary),
            Case("partial-descriptor-refusals", _partial_descriptor_refusals),
            Case("placement-refusals", _placement_refusals),
            Case("stale-inputs-and-projections", _stale_inputs_and_projections),
            Case("configuration-snapshot-binding", _configuration_snapshot_binding),
            Case("typed-handler-owner", _graph_owner_boundary),
            Case("descriptor-snapshot-binding", _descriptor_snapshot_binding),
            Case("composition-snapshot-binding", _composition_snapshot_binding),
            Case("build-composition-snapshot-binding", _build_composition_snapshot_binding),
            Case("declared-source-drift", _declared_source_drift),
            Case("partial-typed-handler-refusals", _partial_graph_edge_refusals),
            Case("post-build-byte-bindings", _build_bindings),
            Case("artifact-path-substitutions", _artifact_path_substitutions),
            Case("production-project-cli", _cli)]
