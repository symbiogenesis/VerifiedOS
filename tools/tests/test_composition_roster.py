# SPDX-License-Identifier: Apache-2.0
"""Production projections bind the exact roster snapshot used for their decisions."""

import json
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_composition import (
    _graph_image,
    _rebind_inventory_source,
    _refused,
    _resolve_descriptors,
    _sandbox,
)
from vos import boot
from vos import composition as c


def _rank_substitution(original: bytes) -> bytes:
    substituted = original.replace(b"| `crypto-core` | `image` | 4 |",
                                   b"| `crypto-core` | `image` | 5 |")
    substituted = substituted.replace(b"| `storage` | `image` | 5 |",
                                      b"| `storage` | `image` | 4 |")
    roster = boot.parse_contract_roster(substituted.decode("utf-8"))
    ensure([m.id for m in roster.image_members()][3:5] == ["storage", "crypto-core"],
           "control swaps independently checked startup ranks in a readable roster")
    return substituted


def _roster_reader_snapshot() -> None:
    with _sandbox() as (root, _raw):
        path = root / boot.CONTRACT
        original = path.read_bytes()
        substituted = original.replace(b"| `supervisor` | `image` | 3 | `partial` |",
                                       b"| `supervisor` | `image` | 3 | `executable` |")
        path.write_bytes(substituted)
        ensure(boot.load_roster(root, boot.CONTRACT, snapshot=original).by_id()["supervisor"].status ==
               "partial", "snapshot reader uses exactly the checked bytes despite a different current file")
        ensure(boot.load_roster(root, boot.CONTRACT).by_id()["supervisor"].status == "executable",
               "existing roster callers continue to read the current file")


def _projection_roster_binding() -> None:
    with _sandbox() as (root, raw):
        path = root / boot.CONTRACT
        original = path.read_bytes()
        substituted = _rank_substitution(original)
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
        ensure(reads >= 2, "control reaches roster publication after its validation")
        for data in (original, original + b"\n<!-- independent formatting -->\n"):
            path.write_bytes(data)
            _rebind_inventory_source(root, raw, boot.CONTRACT)
            outputs = c.projections(root)
            recipe = json.loads(outputs["recipe-members.json"])
            ensure([m["id"] for m in recipe["payload"]["members"]] ==
                   ["mmode-firmware", "kernel", "supervisor", "crypto-core", "storage", "copy-service"],
                   "unchanged roster semantics preserve the independently expected image membership")
            for name in ("manifest.json", "graph-input.json", "recipe-members.json", "admission-request.json"):
                ensure(json.loads(outputs[name])["binding"]["roster"] ==
                       {"path": boot.CONTRACT, "sha256": c.digest(data)},
                       "every projection binds exact parsed roster bytes, including formatting")


def _transient_roster_status() -> None:
    with _sandbox() as (root, _raw):
        path = root / boot.CONTRACT
        original = path.read_bytes()
        substituted = original.replace(b"| `supervisor` | `image` | 3 | `partial` |",
                                       b"| `supervisor` | `image` | 3 | `executable` |")
        ensure(boot.parse_contract_roster(substituted.decode("utf-8")).by_id()["supervisor"].status ==
               "executable", "control changes a readable executable status without changing ranks")
        read_bytes = Path.read_bytes
        reads = 0
        def transient_read(candidate: Path) -> bytes:
            nonlocal reads
            if candidate == path:
                reads += 1
                return substituted if reads == 2 else original
            return read_bytes(candidate)
        with patch.object(Path, "read_bytes", transient_read):
            _refused(lambda: c.projections(root), "stale source binding")
        ensure(reads == 2, "status substitution refuses at the first reread of the checked snapshot")


def _build_roster_binding() -> None:
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
        _graph_image(root, "products/image.bin", graph)
        image = c.reference(root, "products/image.bin")
        outputs = c.projections(root)
        record = c.build_record(root, c.EXAMPLE, outputs, artifacts, image, graph)
        c.validate_build_record(root, c.EXAMPLE, record, outputs, graph, image)
        path = root / boot.CONTRACT
        original = path.read_bytes()
        substituted = _rank_substitution(original)
        read_bytes = Path.read_bytes
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
                ensure(reads > stable_reads, "roster drift refuses at projection or final build publication")
        binding = record["binding"]
        ensure(isinstance(binding, dict) and binding["roster"] ==
               {"path": boot.CONTRACT, "sha256": c.digest(original)},
               "unchanged build record retains the roster snapshot used for runtime membership")


def cases() -> list[Case]:
    return [Case("roster-reader-snapshot", _roster_reader_snapshot),
            Case("projection-roster-snapshot", _projection_roster_binding),
            Case("transient-roster-status", _transient_roster_status),
            Case("build-roster-snapshot", _build_roster_binding)]
