# SPDX-License-Identifier: Apache-2.0
"""Typed graph filtering, recomposition, canonical binding and source comparisons."""

import json
import tempfile
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import composer as c
from vos.cli import composer as cli

ROOT = Path(__file__).resolve().parents[2]


def _reference() -> None:
    result = c.compare_reference(ROOT)
    ensure(result["passed"] is True, str(result))
    ensure(result["accepted_edges"] == 4 and result["spoiled_edges"] == 12,
           "source witness must exercise acceptance and every refusal conjunct")


def _binding() -> None:
    composition = c.reference_fixture(ROOT)
    data = c.graph_bytes(composition)
    decoded = c.parse_document(json.loads(c.canonical_bytes(c.document(composition))))
    ensure(data == c.graph_bytes(decoded), "round trip must preserve canonical bytes")
    c.validate_graph(composition, data, tuple(f"fixture-{i}" for i in composition.roster))
    for changed, roster in ((data + b" ", None), (data, ("foreign",))):
        try:
            c.validate_graph(composition, changed, roster)
        except c.ComposerError:
            continue
        raise AssertionError("a changed graph or roster must fail its binding")
    changed = replace(composition, ring_depth_ceiling=composition.ring_depth_ceiling + 1)
    ensure(c.graph_sha256(changed) != c.graph_sha256(composition),
           "descriptor changes must alter the graph binding")


def _recomposition() -> None:
    composition = c.reference_fixture(ROOT)
    original = c.compose(composition)
    for count in range(len(composition.roster) + 1):
        current = replace(composition, roster=composition.roster[:count])
        graph = c.compose(current)
        ensure(graph.graph_nodes == current.roster, "node list is exactly the requested roster")
        ensure(all(edge.edge_owner in graph.graph_nodes and edge.edge_target in graph.graph_nodes
                   for edge in graph.graph_edges), "recomposed graph must be closed")
    ensure(c.compose(composition) == original, "successor compositions must leave prior graphs unchanged")
    empty = replace(composition, roster=())
    ensure(c.compose(empty) == c.Graph((), ()), "empty roster composes no ambient or script edges")


def _malformed() -> None:
    document = json.loads(c.canonical_bytes(c.document(c.reference_fixture(ROOT))))
    for key, value in (("schema_version", True), ("type_count", -1), ("intent_count", False),
                       ("roster", [99]), ("roster", [0, 0]), ("inventory", [0, 0]),
                       ("script", "run-me")):
        changed = {**document, key: value}
        try:
            c.parse_document(changed)
        except c.ComposerError:
            continue
        raise AssertionError(f"malformed field accepted: {key}={value}")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "duplicate.json").write_text('{"schema_version":1,"schema_version":1}',
                                              encoding="utf-8")
        try:
            c.load_document(root, "duplicate.json")
        except c.ComposerError:
            return
    raise AssertionError("duplicate JSON keys accepted")


def _spoil_every_field() -> None:
    composition = c.reference_fixture(ROOT)
    graph = c.compose(composition)
    edge = graph.graph_edges[0]
    for key in asdict(edge):
        bad = {**asdict(edge), key: True}
        document = json.loads(c.canonical_bytes(c.document(composition)))
        document["descriptors"][0]["desc_edges"] = [bad]
        try:
            c.parse_document(document)
        except c.ComposerError:
            continue
        raise AssertionError(f"edge natural accepted bool: {key}")


def _source_change_detected() -> None:
    source = (ROOT / c.REFERENCE).read_text(encoding="utf-8")
    source = source.replace("Nat.ltb 0 e.(edge_limit)", "Nat.leb 0 e.(edge_limit)")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "proofs").mkdir()
        (root / c.REFERENCE).write_text(source, encoding="utf-8")
        ensure(c.compare_reference(root)["passed"] is False,
               "a weakened source predicate must disagree with the executable port")


def _cli() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        fixture = c.reference_fixture(ROOT)
        (root / "input.json").write_bytes(c.canonical_bytes(c.document(fixture)))
        output = StringIO()
        with patch.object(cli.corpus, "find_root", return_value=root), redirect_stdout(output):
            ensure(cli.main(["compose", "input.json", "--output", "out/graph.json"]) == 0,
                   "CLI should emit canonical graph")
            ensure(cli.main(["compose", "input.json", "--output", "tracked.json"]) == 1,
                   "CLI generated artifacts belong in out/")
        ensure((root / "out/graph.json").read_bytes() == c.graph_bytes(fixture), "CLI graph bytes")


def _compiled_reference() -> None:
    ensure(c.prove_reference(ROOT)["passed"] is True, "compiled reference disagreement")


def cases() -> list[Case]:
    return [Case("source-reference", _reference), Case("canonical-binding", _binding),
            Case("recomposition-closure", _recomposition), Case("malformed-input", _malformed),
            Case("edge-natural-types", _spoil_every_field), Case("source-change", _source_change_detected),
            Case("compose-cli", _cli),
            Case("compiled-reference", _compiled_reference, slow=True, lane="toolchain")]
