# SPDX-License-Identifier: Apache-2.0
"""Offline research metadata and finite host composer dictionary evidence.

Metadata validation does not verify a theorem or fetch a newer source. The
dictionary is a deliberately specified reference encoding, not a target layout.
"""

import hashlib
import json
import posixpath
import re
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from vos import composer, corpus

MANIFEST = "docs/background/math-evidence.json"
ARTIFACT = "docs/background/math-evidence.md"
REQUIRED_IDS = frozenset({"dcp", "rank48", "type-fpt", "logspace103", "comparator",
                          "integer109", "shortest-path", "two-stack", "composer-dictionaries"})
STAGES = ("source inspection", "supplied replay", "independent replay", "production acceptance")
DISPOSITIONS = ("evaluate now", "await workload", "monitor security")
SHAPE_SOURCES = (composer.REFERENCE, "tools/vos/composer.py", "tools/vos/math_evidence.py")


class EvidenceError(ValueError):
    """Missing, malformed or stale evidence metadata."""


def _object(raw: object, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != keys:
        raise EvidenceError(f"{where}: expected exactly {sorted(keys)}")
    return raw


def _text(raw: object, where: str) -> str:
    if (not isinstance(raw, str) or not raw.strip() or raw != raw.strip()
            or any(ord(char) < 32 for char in raw)):
        raise EvidenceError(f"{where}: expected nonempty single-line text")
    return raw


def _array(raw: object, where: str) -> list[Any]:
    if not isinstance(raw, list) or not raw:
        raise EvidenceError(f"{where}: expected a nonempty array")
    return raw


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _local(root: Path, target: object, where: str) -> str:
    value = _text(target, where)
    parts = urlsplit(value)
    path = PurePosixPath(parts.path)
    if (parts.scheme or parts.netloc or parts.query or "\\" in value
            or path.is_absolute() or ".." in path.parts or ":" in parts.path
            or not parts.path or path.as_posix() != parts.path):
        raise EvidenceError(f"{where}: expected a repository-relative file and optional fragment")
    resolved = (root / parts.path).resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise EvidenceError(f"{where}: missing or escaped local file {value}")
    if parts.fragment:
        text = resolved.read_text(encoding="utf-8")
        lines = text.splitlines()
        fenced = corpus.fence_lines(lines)
        targets: set[str] = set()
        for line, hidden in zip(lines, fenced, strict=True):
            if hidden:
                continue
            targets.update(corpus.ANCHOR_RE.findall(line))
            heading = corpus.HEADING_RE.fullmatch(line)
            if heading:
                targets.add(corpus.slug(heading[1]))
        if parts.fragment not in targets:
            raise EvidenceError(f"{where}: missing fragment {value}")
    return value


def _source(root: Path, raw: object, where: str) -> dict[str, str]:
    row = _object(raw, {"url", "kind", "identity"}, where)
    url = _text(row["url"], where + ".url")
    kind = _text(row["kind"], where + ".kind")
    identity = _text(row["identity"], where + ".identity")
    parsed = urlsplit(url)
    if kind == "local-sha256":
        _local(root, url, where)
        if parsed.fragment or re.fullmatch(r"[0-9a-f]{64}", identity) is None:
            raise EvidenceError(f"{where}: local source requires a SHA-256 file identity")
        if hashlib.sha256((root / url).read_bytes()).hexdigest() != identity:
            raise EvidenceError(f"{where}: stale local source identity {url}")
    elif kind == "git":
        if (parsed.scheme != "https" or parsed.hostname != "github.com"
                or re.fullmatch(r"[0-9a-f]{40}", identity) is None
                or identity not in PurePosixPath(parsed.path).parts):
            raise EvidenceError(f"{where}: Git source URL must contain its full immutable revision")
    elif kind == "arxiv":
        if (parsed.scheme != "https" or parsed.hostname != "arxiv.org"
                or re.fullmatch(r"\d{4}\.\d{4,5}v[1-9]\d*", identity) is None
                or parsed.path not in (f"/abs/{identity}", f"/html/{identity}", f"/pdf/{identity}")):
            raise EvidenceError(f"{where}: arXiv source requires an explicit numbered version")
    elif kind == "eprint":
        match = re.fullmatch(r"(\d{4}/\d+)@(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", identity)
        if (match is None or parsed.scheme != "https" or parsed.hostname != "eprint.iacr.org"
                or parsed.path != "/" + match[1]):
            raise EvidenceError(f"{where}: ePrint source requires its exact revision timestamp")
        try:
            datetime.strptime(match[2], "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise EvidenceError(f"{where}: invalid ePrint revision timestamp") from error
    else:
        raise EvidenceError(f"{where}: unsupported or unversioned source identity")
    if (parsed.query or parsed.fragment or parsed.username is not None
            or parsed.password is not None):
        raise EvidenceError(f"{where}: source URL cannot carry query, fragment or credentials")
    return {"url": url, "kind": kind, "identity": identity}


def validate(root: Path, raw: object) -> dict[str, Any]:
    """Validate exact schema, immutable identities and local evidence consumers."""
    document = _object(raw, {"schema_version", "entries"}, "manifest")
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise EvidenceError("manifest: unsupported schema_version")
    seen: set[str] = set()
    for index, item in enumerate(_array(document["entries"], "entries")):
        where = f"entries[{index}]"
        row = _object(item, {"id", "title", "claim", "sources", "inspected", "stage",
                             "assumptions", "consumer", "disposition", "next_action", "evidence"}, where)
        ident = _text(row["id"], where + ".id")
        if re.fullmatch(r"[a-z][a-z0-9-]*", ident) is None or ident in seen:
            raise EvidenceError(f"{where}: malformed or duplicate identifier {ident}")
        seen.add(ident)
        for key in ("title", "claim", "next_action"):
            _text(row[key], where + "." + key)
        inspected = _text(row["inspected"], where + ".inspected")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", inspected) is None:
            raise EvidenceError(f"{where}: invalid inspection date")
        try:
            date.fromisoformat(inspected)
        except ValueError as error:
            raise EvidenceError(f"{where}: invalid inspection date") from error
        if row["stage"] not in STAGES or row["disposition"] not in DISPOSITIONS:
            raise EvidenceError(f"{where}: unknown evidence stage or disposition")
        sources = [_source(root, source, where + ".sources")
                   for source in _array(row["sources"], where + ".sources")]
        if len({(source["url"], source["identity"]) for source in sources}) != len(sources):
            raise EvidenceError(f"{where}: duplicate source")
        for assumption in _array(row["assumptions"], where + ".assumptions"):
            _text(assumption, where + ".assumptions")
        consumer = _object(row["consumer"], {"artifact", "owner"}, where + ".consumer")
        _local(root, consumer["artifact"], where + ".consumer.artifact")
        _text(consumer["owner"], where + ".consumer.owner")
        for evidence in _array(row["evidence"], where + ".evidence"):
            _local(root, evidence, where + ".evidence")
    if seen != REQUIRED_IDS:
        raise EvidenceError(f"manifest: selected entry set differs; missing={sorted(REQUIRED_IDS - seen)}, "
                            f"unknown={sorted(seen - REQUIRED_IDS)}")
    return document


def load(root: Path) -> dict[str, Any]:
    """Read the manifest with duplicate-key refusal at every nesting level."""
    try:
        raw = json.loads((root / MANIFEST).read_text(encoding="utf-8"),
                         object_pairs_hook=_unique_object)
        return validate(root, raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError(f"cannot read math evidence: {error}") from error


def lookup(rows: tuple[tuple[bytes, int], ...], key: bytes, *, binary: bool) -> tuple[int | None, int]:
    """One lexicographic key comparison per examined row; misses return None."""
    comparisons = 0
    if binary:
        lo, hi = 0, len(rows)
        while lo < hi:
            mid = (lo + hi) // 2
            comparisons += 1
            candidate, value = rows[mid]
            if key == candidate:
                return value, comparisons
            if key < candidate:
                hi = mid
            else:
                lo = mid + 1
    else:
        for candidate, value in rows:
            comparisons += 1
            if candidate == key:
                return value, comparisons
    return None, comparisons


def dictionary_report(composition: composer.CompositionInput) -> dict[str, Any]:
    """Finite reference shape, storage arithmetic and all-hit/explicit-miss queries."""
    declaration = tuple((composition.descriptors[index].package_id.encode("utf-8"), index)
                        for index in composition.roster)
    if len({key for key, _ in declaration}) != len(declaration):
        raise EvidenceError("dictionary: duplicate package key")
    if any(len(key) > 65535 or value >= 1 << 64 for key, value in declaration):
        raise EvidenceError("dictionary: key or value exceeds the declared reference encoding")
    ordered = tuple(sorted(declaration))
    # Empty and 0xff cannot encode an admitted package_id. An internal gap, when
    # available, tests binary search between neighboring entries as well.
    missing = [b"", b"\xff"]
    if ordered:
        missing.append(ordered[0][0] + b"\x00")
    queries = [key for key, _ in declaration] + missing
    rows: list[dict[str, Any]] = []
    for key in queries:
        expected = next((value for candidate, value in declaration if candidate == key), None)
        linear_value, linear_count = lookup(declaration, key, binary=False)
        sorted_value, sorted_count = lookup(ordered, key, binary=True)
        if linear_value != expected or sorted_value != expected:
            raise EvidenceError("dictionary: lookup disagrees with the declared finite map")
        rows.append({"key_hex": key.hex(), "value": expected,
                     "linear_comparisons": linear_count, "sorted_comparisons": sorted_count})
    wire = b"".join(len(key).to_bytes(2, "little") + key + value.to_bytes(8, "little")
                    for key, value in ordered)
    graph = composer.compose(composition)
    return {"components": len(composition.descriptors), "roster_components": len(declaration),
            "declared_edges": sum(len(item.desc_edges) for item in composition.descriptors),
            "accepted_edges": len(graph.graph_edges), "refused_roster_edges": len(composer.refused_edges(composition)),
            "entries": len(declaration), "key_bytes": sum(len(key) for key, _ in declaration),
            "key_lengths": sorted({len(key) for key, _ in declaration}),
            "value_width_bytes": 8, "key_length_width_bytes": 2,
            "sorted_payload_bytes": len(wire), "linear_payload_bytes": len(wire),
            "sorted_payload_sha256": hashlib.sha256(wire).hexdigest(), "queries": rows}


def shape_report(root: Path) -> dict[str, Any]:
    """Source-bound host reference, without timing or a production frequency claim."""
    comparison = composer.compare_reference(root)
    if not comparison["passed"]:
        raise EvidenceError(f"composer source comparison failed: {comparison['failures']}")
    result = dictionary_report(composer.reference_fixture(root))
    result["sources_sha256"] = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SHAPE_SOURCES}
    result["fixture_sha256"] = hashlib.sha256(composer.canonical_bytes(
        composer.document(composer.reference_fixture(root)))).hexdigest()
    return result


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|")


def _link(target: str) -> str:
    file, marker, fragment = target.partition("#")
    relative = posixpath.relpath(file, posixpath.dirname(ARTIFACT))
    return f"[{_escape(target)}]({relative}{marker}{fragment})"


def render(root: Path) -> str:
    """Emit the complete deterministic view; read no network or moving clock."""
    try:
        document = load(root)
        shape = shape_report(root)
        lines = ["# Mathematical research evidence", "",
                 "Generated by `python tools/run.py math-evidence emit` from "
                 "[the manifest](math-evidence.json) under [the contract](math-evidence-contract.md). "
                 "Edit the manifest or producer, then regenerate this entire file.", "",
                 "This validates metadata and finite host/reference behavior. It supplies no theorem "
                 "verification, source-truth verdict, accepted security premise or production adoption. "
                 "An inspection date names the selected evidence, not a claim that no newer source exists.", "",
                 "| Topic | Evidence stage | Disposition | Inspected |", "| --- | --- | --- | --- |"]
        entries = sorted(document["entries"], key=lambda row: row["id"])
        lines.extend(f"| [{_escape(row['title'])}](#{row['id']}) | {row['stage']} | "
                     f"{row['disposition']} | {row['inspected']} |" for row in entries)
        for row in entries:
            lines += ["", f"## {row['title']} <a id=\"{row['id']}\"></a>", "", row["claim"], "",
                      f"Evidence stage: **{row['stage']}**. Disposition: **{row['disposition']}**. "
                      f"Inspected: {row['inspected']}.", "", "Selected sources:", ""]
            for source in row["sources"]:
                target = (_link(source["url"]) if source["kind"] == "local-sha256"
                          else f"[{source['kind']}]({source['url']})")
                lines.append(f"- {target}; identity `{source['identity']}`.")
            lines += ["", "Assumptions and exclusions:", ""]
            lines += [f"- {item}" for item in row["assumptions"]]
            lines += ["", f"Consumer: {_link(row['consumer']['artifact'])}. Owner: {row['consumer']['owner']}.", "",
                      "Local evidence: " + "; ".join(_link(item) for item in row["evidence"]) + ".", "",
                      "Next action: " + row["next_action"]]
        lines += ["", "## Finite composer dictionary workload", "",
                  "The existing host/reference composer reads the synthetic `demo` witness in "
                  "[HandlerGraph.v](../../proofs/HandlerGraph.v). These are fixture shapes, not an actual "
                  "device roster, resident producer measurement or observed production access frequency. "
                  "The source-reader comparison passes; no Gallina proof is replayed by this command.", "",
                  "| Quantity | Value |", "| --- | --- |"]
        for name in ("components", "roster_components", "declared_edges", "accepted_edges", "refused_roster_edges",
                     "entries", "key_bytes", "key_lengths", "key_length_width_bytes", "value_width_bytes",
                     "linear_payload_bytes", "sorted_payload_bytes"):
            lines.append(f"| `{name}` | {shape[name]} |")
        lines += ["", "The immutable map sends each roster package ID's UTF-8 bytes to its descriptor index. "
                  "The specified packed reference record is `u16le(key byte length) || key bytes || "
                  "u64le(descriptor index)`, with no terminator, padding or pointer. The sorted baseline "
                  "orders records lexicographically by unsigned key bytes; the linear baseline keeps "
                  "roster order with the same record widths and payload bytes. This reference serialization "
                  "does not exist as a production target representation. Host object overhead, search-offset "
                  "indexes, construction workspace, authenticated storage and CHERI capability metadata are "
                  "excluded and must be charged for any target implementation.", "",
                  "Every existing key is queried once. Additional misses are empty bytes, `ff`, and the "
                  "least existing key followed by `00` (the last query is omitted for an empty map). "
                  "A miss returns `None`; no descriptor index is a default. Counts below are examined rows "
                  "under one abstract three-way key comparison per row, not byte comparisons, instructions, "
                  "timings, target WCET or a probability-weighted workload.", "",
                  "| Query key (hex) | Result | Linear comparisons | Sorted binary comparisons |",
                  "| --- | --- | --- | --- |"]
        for query in shape["queries"]:
            result = "None (absent)" if query["value"] is None else str(query["value"])
            key = query["key_hex"] or "(empty)"
            lines.append(f"| `{key}` | {result} | {query['linear_comparisons']} | {query['sorted_comparisons']} |")
        lines += ["", f"Canonical parsed fixture SHA-256: `{shape['fixture_sha256']}`.", "",
                  f"Sorted reference payload SHA-256: `{shape['sorted_payload_sha256']}`.", "",
                  "| Bound input or implementation | SHA-256 |", "| --- | --- |"]
        lines += [f"| {_link(name)} | `{digest}` |" for name, digest in shape["sources_sha256"].items()]
        lines += ["", "Before adopting a compact dictionary, name a real consumer, record its table shapes "
                  "and access trace or justified query distribution, compare sorted arrays and generated "
                  "perfect hashing, and declare finite byte/work thresholds. Construction and any randomized "
                  "seed need their own bounds. Timing comparisons and benchmarks run on CI. Dynamic service "
                  "indexes separately owe update, exhaustion and recovery behavior.", ""]
        return "\n".join(lines)
    except (OSError, UnicodeError, composer.ComposerError) as error:
        raise EvidenceError(f"cannot render math evidence: {error}") from error


def emit(root: Path) -> None:
    """Repair only the derived view after all input checks succeed."""
    text = render(root)
    (root / ARTIFACT).write_text(text, encoding="utf-8", newline="\n")


def check(root: Path) -> list[str]:
    """Missing and stale output are failures; metadata exceptions remain named."""
    try:
        expected = render(root).encode("utf-8")
        actual = (root / ARTIFACT).read_bytes()
    except (EvidenceError, OSError) as error:
        return [str(error)]
    return [] if actual == expected else [f"stale {ARTIFACT}; run math-evidence emit"]
