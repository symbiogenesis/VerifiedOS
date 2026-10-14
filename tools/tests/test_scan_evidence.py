# SPDX-License-Identifier: Apache-2.0
"""Lossless storage keeps retained text visible to repository-wide scanners."""

import gzip
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import corpus
from vos.checks import Context, glyphs
from vos.register import Artifacts, Register
from vos.report import Reporter

INDEPENDENT_CASES = True


def _ctx(root: Path, rel: str) -> Context:
    return Context(root, corpus.Corpus(root, [], {}, [rel]), Register(), Artifacts(), Reporter())


def _expanded_reads_keep_scope_and_refresh() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-scan-evidence-") as td:
        root = Path(td)
        rel = corpus.COMPRESSED_EVIDENCE + "reading.txt.gz"
        path = root / rel
        path.parent.mkdir(parents=True)
        first = b"before\r\n\x00\xff"
        second = b"after!\r\n\x00\xff"
        path.write_bytes(gzip.compress(first, mtime=0))
        ensure(corpus.scan_bytes(root, rel) == first, "expansion must preserve exact bytes")
        path.write_bytes(gzip.compress(second, mtime=0))
        ensure(corpus.scan_bytes(root, rel) == second, "another read must observe new bytes")
        other = root / "outside.gz"
        other.write_bytes(path.read_bytes())
        ensure(corpus.scan_bytes(root, "outside.gz") == other.read_bytes(),
               "compression has a declared evidence scope, not a suffix-only expansion")
        for bad in (b"", b"plaintext", gzip.compress(first)[:-3]):
            path.write_bytes(bad)
            try:
                corpus.scan_bytes(root, rel)
            except (OSError, EOFError, ValueError):
                pass
            else:
                raise AssertionError("malformed compressed evidence must not become an empty reading")


def _glyph_decisions_survive_compression() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-scan-glyphs-") as td:
        root = Path(td)
        plain = corpus.COMPRESSED_EVIDENCE + "reading.txt"
        packed = plain + ".gz"
        path = root / plain
        path.parent.mkdir(parents=True)
        for text in ("ASCII\r\nclean\rthird", "Unicode λ is clean\n",
                     "first\rsecond\r\n" + glyphs.REPLACEMENT + "\n",
                     "bad " + chr(0xC2) + chr(0xA0) + "\n"):
            blob = text.encode("utf-8")
            path.write_bytes(blob)
            (root / packed).write_bytes(gzip.compress(blob, mtime=0))
            original, compressed = _ctx(root, plain), _ctx(root, packed)
            glyphs.run(original)
            glyphs.run(compressed)
            ensure([line.replace(plain, packed) for line in original.rep.out] == compressed.rep.out,
                   "gzip must keep the original encoding-damage decision and line numbers")


def cases() -> list[Case]:
    return [Case("expanded-evidence-scope-and-refresh", _expanded_reads_keep_scope_and_refresh),
            Case("glyph-decisions-survive-compression", _glyph_decisions_survive_compression)]
