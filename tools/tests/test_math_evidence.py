# SPDX-License-Identifier: Apache-2.0
"""Fail-closed metadata and finite map semantics, without a timing benchmark."""

import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from vos import composer
from vos import math_evidence as evidence

from tests.harness import Case, ensure

ROOT = Path(__file__).resolve().parents[2]


def _reject(raw: object, message: str) -> None:
    try:
        evidence.validate(ROOT, raw)
    except evidence.EvidenceError:
        return
    raise AssertionError(message)


def _metadata_refusals() -> None:
    original = evidence.load(ROOT)
    changes: list[tuple[str, object]] = [
        ("id", "unknown"), ("inspected", "2026-02-30"), ("inspected", "20261020"),
        ("stage", "proved"), ("disposition", "adopt"), ("claim", ""),
        ("sources", []), ("assumptions", []), ("evidence", []),
        ("consumer", {"artifact": "README.md#missing-evidence-fragment", "owner": "Q26"}),
        ("consumer", {"artifact": "../README.md", "owner": "Q26"}),
        ("consumer", {"artifact": "https://example.com", "owner": "Q26"}),
        ("consumer", {"artifact": "README.md", "owner": ""}),
    ]
    for key, value in changes:
        changed = copy.deepcopy(original)
        changed["entries"][0][key] = value
        _reject(changed, f"accepted malformed {key}: {value}")
    for changed in (
        {**original, "extra": False}, {"schema_version": True, "entries": original["entries"]},
        {"schema_version": 1, "entries": []},
        {"schema_version": 1, "entries": original["entries"][:-1]},
        {"schema_version": 1, "entries": [*original["entries"], original["entries"][0]]},
    ):
        _reject(changed, "accepted missing, unknown or duplicate collection member")
    changed = copy.deepcopy(original)
    changed["entries"][0]["extra"] = 1
    _reject(changed, "accepted unknown entry field")
    with tempfile.TemporaryDirectory(prefix="vos-math-duplicate-") as temporary:
        root = Path(temporary)
        manifest = root / evidence.MANIFEST
        manifest.parent.mkdir(parents=True)
        for text in ('{"schema_version":1,"schema_version":1,"entries":[]}',
                     '{"schema_version":1,"entries":[{"id":"a","id":"b"}]}'):
            manifest.write_text(text, encoding="utf-8")
            try:
                evidence.load(root)
            except evidence.EvidenceError as error:
                ensure("duplicate JSON key" in str(error), "duplicate must fail before semantic parsing")
            else:
                raise AssertionError("duplicate JSON key accepted")


def _source_refusals() -> None:
    original = evidence.load(ROOT)
    malformed = [
        {"url": "https://arxiv.org/abs/2609.12027", "kind": "arxiv", "identity": "2609.12027"},
        {"url": "https://github.com/openai/math/tree/main", "kind": "git", "identity": "main"},
        {"url": "https://example.com", "kind": "latest", "identity": "latest"},
        {"url": "README.md", "kind": "local-sha256", "identity": "0" * 64},
        {"url": "https://eprint.iacr.org/2026/1591", "kind": "eprint", "identity": "2026/1591@2026-02-30T00:30:09Z"},
    ]
    for source in malformed:
        changed = copy.deepcopy(original)
        changed["entries"][0]["sources"] = [source]
        _reject(changed, f"accepted unversioned or stale source: {source}")


def _generated_missing_and_drift() -> None:
    original = evidence.load(ROOT)
    names = {evidence.MANIFEST, *evidence.SHAPE_SOURCES}
    for row in original["entries"]:
        names.add(row["consumer"]["artifact"].split("#")[0])
        names.update(item.split("#")[0] for item in row["evidence"])
        names.update(source["url"] for source in row["sources"] if source["kind"] == "local-sha256")
    with tempfile.TemporaryDirectory(prefix="vos-math-view-") as temporary:
        root = Path(temporary)
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, path)
        ensure(bool(evidence.check(root)), "missing generated output must fail")
        evidence.emit(root)
        first = (root / evidence.ARTIFACT).read_bytes()
        ensure(not evidence.check(root), "emitted view must reproduce")
        evidence.emit(root)
        ensure((root / evidence.ARTIFACT).read_bytes() == first, "emission must be deterministic")
        (root / evidence.ARTIFACT).write_bytes(first + b"drift\n")
        ensure(bool(evidence.check(root)), "changed generated view must fail")
        changed = copy.deepcopy(original)
        changed["entries"][0]["next_action"] += " Refreshed action."
        (root / evidence.MANIFEST).write_text(json.dumps(changed), encoding="utf-8")
        ensure(evidence.render(root).encode("utf-8") != first, "manifest updates must change the view")
        (root / evidence.MANIFEST).unlink()
        ensure(bool(evidence.check(root)), "missing manifest must fail")


def _dictionary_semantics() -> None:
    # Deliberately unsorted roster order and descriptor value zero distinguish a
    # real hit from a falsey miss and exercise an internal binary-search branch.
    fixture = composer.CompositionInput(
        (composer.Descriptor("b", 0, ()), composer.Descriptor("a", 0, ()),
         composer.Descriptor("c", 0, ())), (0, 1, 2), 0, 0, 0, frozenset(), frozenset(), 0)
    result = evidence.dictionary_report(fixture)
    ensure(result["entries"] == 3 and result["key_bytes"] == 3, "fixture table shape changed")
    ensure(result["linear_payload_bytes"] == result["sorted_payload_bytes"] == 33,
           "specified records require 2 length + 1 key + 8 value bytes")
    independent = b"".join(b"\x01\x00" + key + index.to_bytes(8, "little")
                           for key, index in ((b"a", 1), (b"b", 0), (b"c", 2)))
    ensure(result["sorted_payload_sha256"] == hashlib.sha256(independent).hexdigest(),
           "payload must bind the exact length/key/value representation")
    queries = result["queries"]
    ensure([query["value"] for query in queries] == [0, 1, 2, None, None, None],
           "hits preserve descriptor index and every explicit absent key misses")
    ensure([query["sorted_comparisons"] for query in queries[:3]] == [1, 2, 2],
           "binary counts must examine the actual sorted rows")
    for key in (b"", b"a", b"aa", b"b", b"c", b"d", b"\xff"):
        expected = {b"a": 1, b"b": 0, b"c": 2}.get(key)
        for binary, rows in ((False, ((b"b", 0), (b"a", 1), (b"c", 2))),
                             (True, ((b"a", 1), (b"b", 0), (b"c", 2)))):
            value, count = evidence.lookup(rows, key, binary=binary)
            ensure(value == expected and 0 < count <= 3, "lookup disagrees with independent map")
    empty = composer.CompositionInput((), (), 0, 0, 0, frozenset(), frozenset(), 0)
    zero = evidence.dictionary_report(empty)
    ensure(zero["sorted_payload_bytes"] == 0 and len(zero["queries"]) == 2,
           "empty map has empty payload and explicit absent-key queries")
    ensure(all(row["value"] is None and row["sorted_comparisons"] == 0 for row in zero["queries"]),
           "empty lookup must not fabricate a value or examine a row")


def _real_shape_binding() -> None:
    result = evidence.shape_report(ROOT)
    fixture = composer.reference_fixture(ROOT)
    graph = composer.compose(fixture)
    ensure(result["roster_components"] == len(fixture.roster)
           and result["accepted_edges"] == len(graph.graph_edges), "report must follow the actual fixture")
    ensure(result["fixture_sha256"] == hashlib.sha256(composer.canonical_bytes(
        composer.document(fixture))).hexdigest(), "fixture identity must bind parsed descriptor semantics")
    for name, digest in result["sources_sha256"].items():
        ensure(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest,
               "implementation binding must follow exact file bytes")


def cases() -> list[Case]:
    return [Case("metadata-refusals", _metadata_refusals),
            Case("source-refusals", _source_refusals),
            Case("generated-missing-and-drift", _generated_missing_and_drift),
            Case("dictionary-semantics", _dictionary_semantics),
            Case("real-shape-binding", _real_shape_binding)]
