# SPDX-License-Identifier: Apache-2.0
"""Compiler navigation, recorded-owner freshness and bounded portable output."""

import hashlib
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from jsonschema import Draft202012Validator
from vos import sailbundle, sailcontext
from vos.cli import sail_context

from tests.harness import TOOLS, Case, ensure, sandbox_tree

FIRST = ("// café\r\n"
         "val shared : int -> int\r\n"
         "function shared(x) = target(x)\r\n"
         "register state : int\r\n"
         "type word = bits(8)\r\n"
         "let initial = target(0)\r\n"
         'ZERO <-> "zero"\r\n')
SECOND = 'function clause shared(y) = target(y)\nONE <-> "one"\n'


def _slot(file: str, text: str, fragment: str) -> dict[str, object]:
    raw = text.encode("utf-8")
    begin = raw.index(fragment.encode("utf-8"))
    end = begin + len(fragment.encode("utf-8"))
    return {"contents": fragment, "file": file,
            "loc": [raw.count(b"\n", 0, begin) + 1, raw.rfind(b"\n", 0, begin) + 1, begin,
                    raw.count(b"\n", 0, end) + 1, raw.rfind(b"\n", 0, end) + 1, end]}


def _link(file: str, text: str, name: str, *, kind: str = "function") -> dict[str, object]:
    begin = text.encode("utf-8").index(name.encode("utf-8"))
    return {"type": kind, "id": name, "file": file, "loc": [begin, begin + len(name.encode("utf-8"))]}


def _fixture() -> tuple[dict[str, str], dict[str, Any]]:
    raw: dict[str, Any] = {
        "version": 1, "embedding": "plain", "anchors": {}, "spans": {},
        "hashes": {file: {"md5": hashlib.md5(text.encode("utf-8"), usedforsecurity=False).hexdigest()}
                   for file, text in (("a.sail", FIRST), ("b.sail", SECOND))},
        "functions": {
            "shared": {"function": [
                {"source": _slot("a.sail", FIRST, "function shared(x) = target(x)")},
                {"source": _slot("b.sail", SECOND, "function clause shared(y) = target(y)")}],
                "links": [_link("a.sail", FIRST, "target"), _link("b.sail", SECOND, "target")]},
            "generated": {"function": {"source": "generated() = 0"},
                          "links": [{"type": "function", "id": "generated_link", "file": "", "loc": [1, 2]}]},
        },
        "vals": {"shared": {"val": {"source": _slot("a.sail", FIRST, "val shared : int -> int")}}},
        "types": {"word": {"type": _slot("a.sail", FIRST, "type word = bits(8)")}},
        "registers": {"state": {"register": {"source": _slot("a.sail", FIRST, "register state : int")}}},
        "lets": {"initial": {"let": {"source": _slot("a.sail", FIRST, "let initial = target(0)")}}},
        "mappings": {"spelling": {"mapping": [
            {"source": _slot("a.sail", FIRST, 'ZERO <-> "zero"')},
            {"source": _slot("b.sail", SECOND, 'ONE <-> "one"')}]}}
    }
    files = {"model/model/a.sail": FIRST, "model/model/b.sail": SECOND}
    files[sailbundle.BUNDLE] = json.dumps(raw)
    return files, raw


def _write_bundle(root: Path, raw: dict[str, Any]) -> None:
    (root / sailbundle.BUNDLE).write_text(json.dumps(raw), encoding="utf-8", newline="")


def _call(root: Path, args: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with (patch.object(sail_context, "find_root", return_value=root),
          redirect_stdout(stdout), redirect_stderr(stderr)):
        try:
            status = sail_context.main(args)
        except SystemExit as exc:
            status = exc.code if isinstance(exc.code, int) else 1
    return status, stdout.getvalue(), stderr.getvalue()


def _shapes_and_exact_symbols() -> None:
    files, raw = _fixture()
    bundle = sailbundle.Bundle(raw)
    ensure({entry.kind for entry in bundle.declarations()} == set(sailcontext.KINDS),
           "all six emitted declaration kinds must remain available")
    with sandbox_tree(files) as root:
        report = sailcontext.context(root, "symbol", "shared")
        ensure(report["known_symbol"] and len(report["matches"]) == 3,
               "exact lookup must preserve the val and both scattered clauses")
        ensure([(hit["kind"], hit["clause"], hit["path"]) for hit in report["matches"]] ==
               [("val", 0, "model/model/a.sail"), ("function", 0, "model/model/a.sail"),
                ("function", 1, "model/model/b.sail")], "source locations determine stable ordering")
        generated = sailcontext.context(root, "symbol", "generated")
        ensure(generated["known_symbol"] and not generated["matches"] and
               generated["omitted_matches"]["unlocated"] == 1,
               "generated names must be distinguished from local source results")
        unknown = sailcontext.context(root, "symbol", "Shared")
        ensure(unknown["known_symbol"] is False and not unknown["matches"],
               "exact lookup must be case-sensitive and distinguish unknown names")
        link = sailcontext.context(root, "references", "generated_link")
        ensure(link["known_symbol"] and link["omitted_matches"]["unlocated"] == 1 and
               link["coverage"]["unlocated_references"] == 1 and not link["matches"],
               "compiler links with empty filenames must remain explicitly unlocated")


def _ranking_filters_and_omissions() -> None:
    files, raw = _fixture()
    ghost = "function target() = 1"
    raw["functions"]["target"] = {"function": {"source": _slot("ghost.sail", ghost, ghost)},
                                    "links": [_link("ghost.sail", ghost, "target")]}
    files["model/model/ghost.sail"] = ghost
    files[sailbundle.BUNDLE] = json.dumps(raw)
    with sandbox_tree(files) as root:
        report = sailcontext.context(root, "search", "shared target", kinds=("function",),
                                     exclude=("model/model/b.sail",))
        ensure([hit["symbol"] for hit in report["matches"]] == ["shared"],
               "kind and exact owner exclusion must constrain ranked examples")
        ensure(report["matches"][0]["score"] == 9, "a name word ranks above a source-text word")
        ensure(report["coverage"]["unrecorded_declarations"] == 1 and
               report["omitted_matches"]["unrecorded"] == 1,
               "unrecorded located examples must be counted but never returned as fresh")
        exact = sailcontext.context(root, "symbol", "target")
        ensure(exact["known_symbol"] and not exact["matches"] and
               exact["omitted_matches"]["unrecorded"] == 1,
               "an exact unrecorded match must not resemble an unknown name")
        refs = sailcontext.context(root, "references", "target")
        ensure(len(refs["matches"]) == 2 and refs["omitted_matches"]["unrecorded"] == 1,
               "compiler references into unrecorded sources have a separate omission count")
        ensure(report == sailcontext.context(root, "search", "shared target", kinds=("function",),
                                            exclude=("model/model/b.sail",)), "ordering must repeat")


def _byte_locations_and_aliases() -> None:
    files, raw = _fixture()
    raw["functions"]["shared"]["links"][0]["id"] = "compiler_alias"
    files[sailbundle.BUNDLE] = json.dumps(raw)
    with sandbox_tree(files) as root:
        report = sailcontext.context(root, "references", "compiler_alias")
        hit = report["matches"][0]
        ensure(hit["line"] == 3 and hit["column"] == 22 and hit["end_column"] == 28,
               f"byte locations after non-ASCII text and CRLF must give correct columns: {hit}")
        ensure(hit["excerpt"] == "function shared(x) = target(x)\r",
               "reference excerpts must show the source line, preserving raw bytes")
        ensure(FIRST.encode("utf-8")[hit["start_byte"]:hit["end_byte"]] == b"target",
               "a compiler alias need not equal the source token spelling")
        ensure(hit["source_sha256"] == hashlib.sha256(FIRST.encode("utf-8")).hexdigest(),
               "source identity must use the exact raw bytes")
        ensure(report["bundle_sha256"] == hashlib.sha256((root / sailbundle.BUNDLE).read_bytes()).hexdigest(),
               "the bundle hash must identify the same read that supplied the result")


def _freshness_all_owners() -> None:
    files, _ = _fixture()
    with sandbox_tree(files) as root:
        path = root / "model/model/b.sail"
        before = path.stat()
        path.write_bytes(SECOND.replace("target", "edited").encode("utf-8"))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        status, stdout, stderr = _call(root, ["search", "shared", "--exclude", "model/model/b.sail", "--json"])
        ensure(status == 1 and not stdout and "digest differs" in stderr,
               "every recorded owner must be hashed, including excluded unchanged-mtime sources")
        path.unlink()
        status, stdout, stderr = _call(root, ["symbol", "shared", "--json"])
        ensure(status == 1 and not stdout and "missing regular source" in stderr,
               "a deleted owner must refuse the complete output")


def _bounds_schema_and_human_output() -> None:
    files, raw = _fixture()
    long_source = "function long() = " + "1 + " * 100 + "0"
    files["model/model/long.sail"] = long_source
    raw["hashes"]["long.sail"] = {"md5": hashlib.md5(long_source.encode(), usedforsecurity=False).hexdigest()}
    raw["functions"]["long"] = {"function": {"source": _slot("long.sail", long_source, long_source)}}
    files[sailbundle.BUNDLE] = json.dumps(raw)
    schema = json.loads((TOOLS / "sail-context.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    with sandbox_tree(files) as root:
        for operation, query in (("search", "shared"), ("symbol", "long"), ("references", "target")):
            status, stdout, stderr = _call(root, [operation, query, "--limit", "1", "--max-chars", "256", "--json"])
            ensure(status == 0 and not stderr, f"valid JSON query failed: {stderr}")
            report = json.loads(stdout)
            validator.validate(report)
            ensure(report["advisory_only"] and len(report["matches"]) == 1,
                   "machine output must retain the boundary and result bound")
            if operation == "symbol":
                hit = report["matches"][0]
                ensure(hit["excerpt_truncated"] and len(hit["excerpt"]) == 256 and
                       hit["excerpt_end_byte"] == 256, "excerpt bounds identify actual returned text")
            else:
                ensure(report["truncated"] and report["total_matches"] > 1,
                       "omitted eligible results must be explicit")
        status, stdout, stderr = _call(root, ["symbol", "long", "--max-chars", "256"])
        ensure(status == 0 and not stderr and sailcontext.NOTICE in stdout and
               "[excerpt truncated]" in stdout, "human output must state scope and bounds")


def _malformed_bundle_and_locations() -> None:
    files, baseline = _fixture()
    with sandbox_tree(files) as root:
        bad_bundles: list[dict[str, Any]] = []
        for field, value in (("embedding", "html"), ("version", True), ("functions", [])):
            raw = json.loads(json.dumps(baseline))
            raw[field] = value
            bad_bundles.append(raw)
        for location in ([3, 0, 0, 3, 0, 99999], [3, 0, 4, 3, 0, 2],
                         [1, 0, 7, 1, 0, 8], [True, 0, 0, 1, 0, 3]):
            raw = json.loads(json.dumps(baseline))
            raw["functions"]["shared"]["function"][0]["source"]["loc"] = location
            bad_bundles.append(raw)
        raw = json.loads(json.dumps(baseline))
        raw["functions"]["shared"]["function"][0]["source"]["contents"] = "forged source"
        bad_bundles.append(raw)
        raw = json.loads(json.dumps(baseline))
        raw["functions"]["shared"]["links"][0]["loc"] = [1, "bad"]
        bad_bundles.append(raw)
        for raw in bad_bundles:
            _write_bundle(root, raw)
            status, stdout, stderr = _call(root, ["symbol", "shared", "--json"])
            ensure(status == 1 and not stdout and stderr, f"malformed bundle must fail: {raw}")
        for text in ('{"version":1,"version":1}', '{"value":NaN}', '{broken'):
            (root / sailbundle.BUNDLE).write_text(text, encoding="utf-8", newline="")
            status, stdout, stderr = _call(root, ["symbol", "shared", "--json"])
            ensure(status == 1 and not stdout and "JSON" in stderr,
                   "duplicate keys, non-JSON numbers and malformed JSON must refuse")


def _unsafe_paths_and_links() -> None:
    files, baseline = _fixture()
    with sandbox_tree(files) as root:
        for unsafe in ("../a.sail", "/outside/a.sail", "C:/a.sail", "a\\b.sail", "./a.sail", "NUL.sail"):
            raw = json.loads(json.dumps(baseline))
            raw["functions"]["shared"]["function"][0]["source"]["file"] = unsafe
            _write_bundle(root, raw)
            status, stdout, stderr = _call(root, ["symbol", "shared", "--json"])
            ensure(status == 1 and not stdout and "unsafe" in stderr,
                   f"unsafe emitted locations must refuse even with valid owners: {unsafe}")
        _write_bundle(root, baseline)

        def linked(path: Path) -> bool:
            return path.name == "a.sail"

        for method in ("is_symlink", "is_junction"):
            with patch.object(Path, method, autospec=True, side_effect=linked):
                status, stdout, stderr = _call(root, ["symbol", "shared", "--json"])
            ensure(status == 1 and not stdout and "links and junctions" in stderr,
                   f"{method} owner must be refused before read")


def _input_errors_and_unreadable_sources() -> None:
    files, _ = _fixture()
    with sandbox_tree(files) as root:
        for args in ([], ["search", ""], ["search", "!"], ["symbol", "x", "--limit", "0"],
                     ["search", "x", "--max-chars", "16001"], ["search", "x", "--kind", "bad"],
                     ["references", "x", "--exclude", "model/model/a.sail"]):
            status, stdout, stderr = _call(root, args)
            ensure(status == 2 and not stdout and stderr, f"invalid selector must be a usage error: {args}")
        status, stdout, stderr = _call(root, ["search", "shared", "--exclude", "model/model/missing.sail", "--json"])
        ensure(status == 1 and not stdout and "not a recorded local owner" in stderr,
               "exclusions must name exact recorded owners")
        (root / "model/model/a.sail").write_bytes(b"\xff")
        status, stdout, stderr = _call(root, ["symbol", "shared", "--json"])
        ensure(status == 1 and not stdout and "UTF-8" in stderr, "undecodable owners must refuse")
        status, stdout, stderr = _call(root, ["--help"])
        ensure(status == 0 and "references" in stdout and not stderr, "help needs no source reads")


def cases() -> list[Case]:
    return [Case("declaration-shapes-and-exact-symbols", _shapes_and_exact_symbols),
            Case("ranking-filters-and-omissions", _ranking_filters_and_omissions),
            Case("byte-locations-and-compiler-aliases", _byte_locations_and_aliases),
            Case("freshness-all-recorded-owners", _freshness_all_owners),
            Case("bounds-json-schema-and-human-output", _bounds_schema_and_human_output),
            Case("malformed-bundle-and-locations", _malformed_bundle_and_locations),
            Case("unsafe-paths-and-links", _unsafe_paths_and_links),
            Case("input-errors-and-unreadable-sources", _input_errors_and_unreadable_sources)]
