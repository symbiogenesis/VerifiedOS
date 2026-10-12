# SPDX-License-Identifier: Apache-2.0
"""Independent oracle landmarks, deterministic generation and byte-drift refusals."""

import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import asm, vector_bitcount

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


def cases() -> list[Case]:
    return [Case("fixed-width independent oracle and domain", _oracle),
            Case("generated artifacts, drift and decoded words", _generated)]
