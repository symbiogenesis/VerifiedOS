# SPDX-License-Identifier: Apache-2.0
"""Production records join the regenerated graph to physical ELF load bytes."""

import json
import struct
from collections.abc import Callable
from pathlib import Path

from tests.harness import Case, ensure
from tests.test_composition import _write
from tests.test_composition_build_cli import IMAGE, PROJECT, RECORD, _build, _check, _products
from vos import composer, image
from vos import composition as c


def _parts(root: Path) -> list[image.Section]:
    raw = c.load(root)
    graph = (root / "products/graph.json").read_bytes()
    base = int(raw["graph_placement"]["base"], 16)
    return [image.Section(".text", base - 4096, bytearray(b"\x13\x00\x00\x00"), executable=True),
            image.Section(".handler_graph", base, bytearray(graph))]


def _emit(root: Path, sections: list[image.Section]) -> None:
    image.write_elf(root / IMAGE, sections, {}, sections[0].addr)


def _refused_image(change: Callable[[Path], object], phrase: str) -> None:
    with _products() as root:
        ensure(_build(root)[0] == 0, "the ordinary emitted ELF binds the graph")
        change(root)
        # Rebind the supplied image digest. The defect is the graph/image join,
        # rather than the older outer byte-identity check.
        record = json.loads((root / RECORD).read_bytes())
        record["image"] = c.reference(root, IMAGE)
        (root / RECORD).write_bytes(composer.canonical_bytes(record))
        before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
        for consume in (_build, _check):
            code, output = consume(root)
            ensure(code == 1 and phrase in output, output)
        ensure(before == {path: path.read_bytes() for path in root.rglob("*") if path.is_file()},
               "a refused graph/image join preserves the record and every input")


def _changed_section(field: str, value: object) -> Callable[[Path], None]:
    def change(root: Path) -> None:
        sections = _parts(root)
        setattr(sections[1], field, value)
        _emit(root, sections)
    return change


def _section_bindings() -> None:
    _refused_image(lambda root: _emit(root, _parts(root)[:1]), "exactly one .handler_graph")
    _refused_image(_changed_section("data", bytearray(b"substituted graph")), "embedded graph bytes differ")
    _refused_image(_changed_section("writable", True), "section must be allocated, read-only")
    _refused_image(_changed_section("executable", True), "section must be allocated, read-only")
    def move(root: Path) -> None:
        sections = _parts(root)
        sections[1].addr += 16
        _emit(root, sections)
    _refused_image(move, "graph address differs from placement")
    def duplicate(root: Path) -> None:
        sections = _parts(root)
        sections.append(image.Section(".handler_graph", sections[1].addr + 2048, bytearray(b"other")))
        _emit(root, sections)
    _refused_image(duplicate, "exactly one .handler_graph")


def _segment_mutation(layout: str, displacement: int, value: int) -> Callable[[Path], None]:
    def change(root: Path) -> None:
        path = root / IMAGE
        blob = bytearray(path.read_bytes())
        # The writer emits the text segment followed by the graph segment.
        struct.pack_into(layout, blob, image.EHDR_SIZE + image.PHDR_SIZE + displacement, value)
        path.write_bytes(blob)
    return change


def _physical_load_binding() -> None:
    _refused_image(_segment_mutation("<I", 0, 0), "not physically loaded")
    _refused_image(_segment_mutation("<I", 4, image.PF_R | image.PF_W), "complete read-only")
    _refused_image(_segment_mutation("<I", 4, image.PF_R | image.PF_X), "complete read-only")
    def move(root: Path) -> None:
        base = _parts(root)[1].addr
        _segment_mutation("<Q", 24, base + 16)(root)
    _refused_image(move, "complete read-only")
    def substitute(root: Path) -> None:
        path = root / IMAGE
        blob = bytearray(path.read_bytes())
        graph = _parts(root)[1].data
        alternate = len(blob)
        blob.extend(b"x" * len(graph))
        struct.pack_into("<Q", blob, image.EHDR_SIZE + image.PHDR_SIZE + 8, alternate)
        path.write_bytes(blob)
    _refused_image(substitute, "substitutes .handler_graph bytes")
    def zero_fill(root: Path) -> None:
        graph = _parts(root)[1].data
        _segment_mutation("<Q", 32, len(graph) - 1)(root)
    _refused_image(zero_fill, "complete read-only")


def _overwriting_segments() -> None:
    for zero_fill in (False, True):
        def overwrite(root: Path, tail: bool = zero_fill) -> None:
            sections = _parts(root)
            graph = sections[1]
            sections.append(image.Section(".other", graph.addr - 16 if tail else graph.addr,
                                          bytearray(b"short!!!" if tail else b"overwriting bytes"), writable=True))
            _emit(root, sections)
            if tail:
                path = root / IMAGE
                blob = bytearray(path.read_bytes())
                # The third segment starts before the graph; its zero-filled
                # memory tail still overwrites the graph's physical address.
                struct.pack_into("<Q", blob, image.EHDR_SIZE + 2 * image.PHDR_SIZE + 40,
                                 16 + len(graph.data))
                path.write_bytes(blob)
        _refused_image(overwrite, "overlap .handler_graph")


def _containing_load_segment() -> None:
    with _products() as root:
        path = root / IMAGE
        blob = bytearray(path.read_bytes())
        graph = _parts(root)[1]
        offset = len(blob)
        blob.extend(b"prefix!!" + graph.data + b"suffix!!")
        struct.pack_into("<IIQQQQQQ", blob, image.EHDR_SIZE + image.PHDR_SIZE,
                         image.PT_LOAD, image.PF_R, offset, graph.addr - 8, graph.addr - 8,
                         len(graph.data) + 16, len(graph.data) + 16, 1)
        path.write_bytes(blob)
        code, output = _build(root)
        ensure(code == 0, output)
        ensure(_check(root)[0] == 0, "a larger ordinary read-only load segment binds its graph subextent")


def _format_and_reservation() -> None:
    _refused_image(lambda root: (root / IMAGE).write_bytes(b"image metadata is insufficient"), "supported ELF64")
    _refused_image(lambda root: (root / IMAGE).write_bytes((root / IMAGE).read_bytes()[:80]),
                   "ELF extent exceeds")
    _refused_image(_segment_mutation("<Q", 24, (1 << 64) - 8), "load segment wraps")
    _refused_image(_changed_section("addr", (1 << 64) - 8), "section wraps")
    with _products() as root:
        raw = c.load(root)
        raw["graph_placement"] = None
        _write(root, raw)
        c.emit(root, c.EXAMPLE, PROJECT)
        code, output = _build(root)
        ensure(code == 1 and "unresolved graph placement" in output, output)
        ensure(not (root / RECORD).exists(), "an unplaced graph cannot publish a build record")


def cases() -> list[Case]:
    return [Case("embedded-section-bindings", _section_bindings),
            Case("physical-loaded-graph", _physical_load_binding),
            Case("graph-load-overwrites", _overwriting_segments),
            Case("containing-read-only-load", _containing_load_segment),
            Case("elf-format-and-placement", _format_and_reservation)]
