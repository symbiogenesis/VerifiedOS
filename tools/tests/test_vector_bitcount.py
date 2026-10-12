# SPDX-License-Identifier: Apache-2.0
"""Independent oracle landmarks, deterministic generation and byte-drift refusals."""

import struct
import subprocess
import tempfile
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import asm, image, vector_bitcount
from vos.cli import vector_bitcount as cli

ROOT = TOOLS.parent


def _oracle() -> None:
    for width in vector_bitcount.WIDTHS:
        mask = (1 << width) - 1
        ensure(vector_bitcount.counts(width, 0) == (width, width, 0), "zero count")
        ensure(vector_bitcount.counts(width, -1) == (0, 0, width), "modulo-width all ones")
        for bit in range(width):
            ensure(vector_bitcount.counts(width, 1 << bit) == (width - bit - 1, bit, 1),
                   "single-bit position")
        for length in range(1, width):
            ensure(vector_bitcount.counts(width, (1 << length) - 1)
                   == (width - length, 0, length), "low run")
            ensure(vector_bitcount.counts(width, mask ^ ((1 << length) - 1))
                   == (0, length, width - length), "high run")
        for value in vector_bitcount.values(width):
            ctz = vector_bitcount.counts(width, value)[1]
            transformed = ((value - 1) & ~value) & mask
            ensure(vector_bitcount.counts(width, transformed)[2] == ctz,
                   "modulo-width CTZ/popcount identity")
    ensure(vector_bitcount.values(8) == tuple(range(256)), "SEW8 must be exhausted")
    ensure(vector_bitcount.geometries(64) == (0, 1, 2, 3), "illegal fractional e64")
    ensure(vector_bitcount.geometries(8) == (-3, -2, -1, 0, 1, 2, 3), "missing fractional e8")
    try:
        vector_bitcount.counts(7, 0)
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported SEW admitted")


def _generated() -> None:
    ensure(not vector_bitcount.check(ROOT), "generated bit-count artifact drift")
    with tempfile.TemporaryDirectory(prefix="vos-bitcount-test-") as temporary:
        root = Path(temporary)
        for artifact, emit in ((vector_bitcount.SAIL, vector_bitcount.emit_sail),
                               (vector_bitcount.CORPUS, vector_bitcount.emit_corpus)):
            path = root / artifact
            path.parent.mkdir(parents=True, exist_ok=True)
            expected = emit(ROOT).encode("utf-8")
            ensure(expected == emit(root).encode("utf-8"), "generator depends on checkout location")
            path.write_bytes(expected)
        ensure(not vector_bitcount.check(root), "fresh artifacts refused")
        for artifact in vector_bitcount.ARTIFACTS:
            path = root / artifact
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            ensure(any(artifact in finding for finding in vector_bitcount.check(root)),
                   "byte drift was accepted")
            path.write_bytes(original)
            path.unlink()
            ensure(any(artifact in finding for finding in vector_bitcount.check(root)),
                   "missing artifact was accepted")
            path.write_bytes(original)
        source = root / vector_bitcount.CORPUS
        ensure(asm.assemble_file(source, root / "vector-bitcount.elf") > 0,
               "generated decoded-instruction corpus did not assemble")


def _disjoint_load_segments(raw: bytes) -> None:
    """Read actual ELF program headers; assembler success alone misses overlap."""
    offset = struct.unpack_from("<Q", raw, 32)[0]
    size, count = struct.unpack_from("<HH", raw, 54)
    extents = []
    for index in range(count):
        header = struct.unpack_from("<IIQQQQQQ", raw, offset + index * size)
        if header[0] == image.PT_LOAD:
            extents.append((header[4], header[4] + header[6]))
    extents.sort()
    ensure(len(extents) == 2, "expected the assembler's text and data load segments")
    ensure(all(left[1] <= right[0] for left, right in pairwise(extents)),
           "loadable ELF segments overlap")


def _layout() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-bitcount-layout-") as temporary:
        root = Path(temporary)
        source = root / "bitcount.s"
        source.write_text(vector_bitcount.emit_corpus(ROOT), encoding="utf-8", newline="\n")
        elf = root / "bitcount.elf"
        asm.assemble_file(source, elf)
        _disjoint_load_segments(elf.read_bytes())
        sections, _, _ = asm.Assembler(source.read_text(encoding="utf-8")).assemble()
        text = next(section for section in sections if section.name == ".text")
        ensure(text.addr + len(text.data) < asm.DATA_BASE,
               "generated text reached the assembler's fixed data base")
        # Reproduce the original failure: a successfully assembled text segment
        # extends through data. The ELF observation must reject it.
        source.write_text(f".text\n_start:\n.space {asm.DATA_BASE - asm.TEXT_BASE + 4}\n"
                          ".data\n.dword 0\n", encoding="utf-8", newline="\n")
        asm.assemble_file(source, elf)
        try:
            _disjoint_load_segments(elf.read_bytes())
        except AssertionError as exc:
            ensure("overlap" in str(exc), f"wrong layout refusal: {exc}")
        else:
            raise AssertionError("the original overlapping ELF layout was accepted")


def _adapter_controls() -> None:
    source, verdicts = vector_bitcount.smoke_source()
    ensure(vector_bitcount.SAIL_SELECTOR in source
           and vector_bitcount.SAIL_SELECTOR in vector_bitcount.emit_sail(ROOT),
           "hosted check and generated model use different selectors")
    ensure(set(verdicts) == {*(f"adapter_e{width}" for width in vector_bitcount.WIDTHS),
                             "original_descending_mismatch"}, "adapter omits a width or original control")
    ensure(verdicts["original_descending_mismatch"] == "sat", "original defect has no counterexample control")
    for mode in ("pass", "missing", "unknown", "positive-sat", "negative-unsat", "compiler-error"):
        with tempfile.TemporaryDirectory(prefix="vos-adapter-test-") as temporary:
            root = Path(temporary)

            def run(argv: list[str], mode: str = mode, **_options: object) -> subprocess.CompletedProcess[str]:
                if argv[0] == "sail":
                    prefix = Path(argv[argv.index("-o") + 1])
                    for name in verdicts:
                        if mode != "missing" or name != "adapter_e16":
                            prefix.with_name(prefix.name + f"_{name}.smt2").write_text("query", encoding="utf-8")
                    return subprocess.CompletedProcess(argv, int(mode == "compiler-error"), "", "")
                name = Path(argv[-1]).stem.removeprefix("adapter_")
                observed = verdicts[name]
                if mode == "unknown":
                    observed = "unknown"
                elif mode == "positive-sat" and name == "adapter_e16":
                    observed = "sat"
                elif mode == "negative-unsat" and name == "original_descending_mismatch":
                    observed = "unsat"
                return subprocess.CompletedProcess(argv, 0, observed + "\n", "")

            with (patch.object(cli.env, "load", return_value=SimpleNamespace(lane_root=root)),
                  patch.object(cli.subprocess, "run", side_effect=run)):
                try:
                    result = cli.smoke()
                except ValueError:
                    ensure(mode not in ("pass", "compiler-error"), f"unexpected {mode} refusal")
                else:
                    ensure(result == (1 if mode == "compiler-error" else 0)
                           and mode in ("pass", "compiler-error"), f"{mode} supplied false passing evidence")


def cases() -> list[Case]:
    return [Case("fixed-width independent oracle and domain", _oracle),
            Case("generated artifacts, drift and decoded words", _generated),
            Case("actual ELF load segments remain disjoint", _layout),
            Case("adapter verdicts and original mismatch fail closed", _adapter_controls)]
