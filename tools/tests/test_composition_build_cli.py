# SPDX-License-Identifier: Apache-2.0
"""File-backed build records bind published outputs without admitting fixtures."""

import json
from collections.abc import Generator
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from tests.test_composition import _graph_image, _resolve_descriptors, _sandbox, _write
from vos import composer
from vos import composition as c
from vos.cli import composer as cli

PROJECT = "out/project"
RECORD = "out/build-record.json"
ARTIFACTS = "products/artifact-paths.json"
GRAPH = "products/graph.json"
IMAGE = "products/image.bin"


@contextmanager
def _products() -> Generator[Path]:
    with _sandbox() as (root, raw):
        graph = _resolve_descriptors(root, raw)
        directory = root / "products"
        directory.mkdir()
        paths = {}
        for member in raw["members"]:
            if member["id"] in ("composer", "admission"):
                continue
            relative = f"products/{member['id']}.bin"
            (root / relative).write_bytes(f"test-only bytes for {member['id']}".encode())
            paths[member["artifact_slot"]] = relative
        (root / ARTIFACTS).write_bytes(composer.canonical_bytes(paths))
        (root / GRAPH).write_bytes(graph)
        _graph_image(root, IMAGE, graph)
        c.emit(root, c.EXAMPLE, PROJECT)
        yield root


def _invoke(root: Path, command: str, *options: str) -> tuple[int, str]:
    output = StringIO()
    args = [command, c.EXAMPLE, "--projections", PROJECT, "--graph", GRAPH, "--image", IMAGE]
    with patch.object(cli.corpus, "find_root", return_value=root), redirect_stdout(output):
        result = cli.main([*args, *options])
    return result, output.getvalue()


def _build(root: Path, output: str = RECORD) -> tuple[int, str]:
    return _invoke(root, "build-record", "--artifacts", ARTIFACTS, "--output", output)


def _check(root: Path) -> tuple[int, str]:
    return _invoke(root, "check-build-record", "--record", RECORD)


def _roundtrip() -> None:
    with _products() as root:
        code, output = _build(root)
        ensure(code == 0, output)
        record_bytes = (root / RECORD).read_bytes()
        record = json.loads(record_bytes)
        ensure(record_bytes == composer.canonical_bytes(record), "record publication must be canonical")
        ensure(record["production_admission"] is False, "test products never acquire admission")
        ensure(record["image"] == c.reference(root, IMAGE), "final image identity")
        ensure(record["graph_sha256"] == c.digest((root / GRAPH).read_bytes()), "actual graph identity")
        paths = json.loads((root / ARTIFACTS).read_bytes())
        ensure(record["artifacts"] == {slot: c.reference(root, path) for slot, path in paths.items()},
               "resolve every runtime slot to actual produced bytes")
        before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
        code, output = _check(root)
        ensure(code == 0 and "admission remains open" in output, output)
        ensure(before == {path: path.read_bytes() for path in root.rglob("*") if path.is_file()},
               "checking a saved record must write no files")


def _published_drift() -> None:
    for relative, phrase in ((f"{PROJECT}/manifest.c", "stale projection bindings"),
                             ("products/storage.bin", "stale source binding"),
                             (GRAPH, "graph binding"), (IMAGE, "image binding")):
        with _products() as root:
            ensure(_build(root)[0] == 0, "passing control")
            path = root / relative
            path.write_bytes(path.read_bytes() + b"changed")
            before = (root / RECORD).read_bytes()
            code, output = _check(root)
            ensure(code == 1 and phrase in output, output)
            ensure((root / RECORD).read_bytes() == before, "a refused check preserves the record")
            if relative == f"{PROJECT}/manifest.c":
                code, output = _build(root)
                ensure(code == 1 and phrase in output, output)
                ensure((root / RECORD).read_bytes() == before, "stale projections cannot publish a record")
    with _products() as root:
        ensure(_build(root)[0] == 0, "passing control")
        record = json.loads((root / RECORD).read_bytes())
        record["production_admission"] = True
        (root / RECORD).write_bytes(composer.canonical_bytes(record))
        code, output = _check(root)
        ensure(code == 1 and "substituted binding" in output, output)


def _artifact_paths() -> None:
    for content, phrase in ((b"[]", "artifact paths"), (b'{"slot":1}', "string slots and paths"),
                            (b'{"slot":"missing.bin","slot":"missing.bin"}', "duplicate JSON key"),
                            (b'{"slot":"../escape.bin"}', "relative to the checkout"),
                            (b"{}", "artifact slots differ")):
        with _products() as root:
            (root / ARTIFACTS).write_bytes(content)
            code, output = _build(root)
            ensure(code == 1 and phrase in output, output)
            ensure(not (root / RECORD).exists(), "malformed slot paths must not publish a record")


def _output_containment() -> None:
    for relative in (IMAGE, GRAPH, ARTIFACTS, f"{PROJECT}/manifest.c", "products/storage.bin"):
        with _products() as root:
            before = (root / relative).read_bytes()
            code, output = _build(root, relative)
            ensure(code == 1 and "overwrite an input or product" in output, output)
            ensure((root / relative).read_bytes() == before, "bound input bytes must survive output refusal")
    for relative in ("tracked.json", "../escape.json"):
        with _products() as root:
            code, output = _build(root, relative)
            ensure(code == 1, output)
            ensure(not (root / "tracked.json").exists(), "records belong under out/")
    with _products() as root:
        code, output = _invoke(root, "check-build-record", "--record", "../escape.json")
        ensure(code == 1 and "relative to the checkout" in output, output)


def _bound_source_outputs() -> None:
    for kind in ("configuration", "member", "producer", "descriptor", "derivation"):
        with _products() as root:
            raw = c.load(root)
            member = raw["members"][0]
            if kind == "configuration":
                original = raw["configuration"]
            elif kind == "producer":
                original = raw["producers"][0]["sources"][0]
            elif kind == "descriptor":
                original = member["descriptor"]
            else:
                original = member["sources"][0]
            relative = "out/bound-source.json"
            before = (root / original["path"]).read_bytes()
            (root / relative).write_bytes(before)
            ref = c.reference(root, relative)
            if kind == "configuration":
                raw["configuration"] = ref
            elif kind == "producer":
                raw["producers"][0]["sources"][0] = ref
            elif kind == "descriptor":
                member["descriptor"] = ref
            elif kind == "derivation":
                member["derivation"]["source"] = ref
            else:
                member["sources"][0] = ref
            _write(root, raw)
            c.emit(root, c.EXAMPLE, PROJECT)
            code, output = _build(root, relative)
            ensure(code == 1 and "overwrite an input or product" in output, f"{kind}: {output}")
            ensure((root / relative).read_bytes() == before, f"bound {kind} source must survive refusal")


def _unresolved_real_input() -> None:
    with _sandbox() as (root, _raw):
        (root / "products").mkdir()
        (root / GRAPH).write_bytes(b"{}\n")
        (root / IMAGE).write_bytes(b"test-only image")
        (root / ARTIFACTS).write_bytes(b"{}\n")
        c.emit(root, c.EXAMPLE, PROJECT)
        code, output = _build(root)
        ensure(code == 1 and "missing graph binding" in output, output)
        ensure(not (root / RECORD).exists(), "unresolved real descriptors cannot acquire a build record")


def cases() -> list[Case]:
    return [Case("file-backed-roundtrip", _roundtrip),
            Case("published-byte-drift", _published_drift),
            Case("artifact-slot-path-map", _artifact_paths),
            Case("record-output-containment", _output_containment),
            Case("transitive-source-output-aliases", _bound_source_outputs),
            Case("unresolved-real-composition", _unresolved_real_input)]
