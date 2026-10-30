# SPDX-License-Identifier: Apache-2.0
"""Conservative facts and candidate regions from compressed audit surfaces.

The original parsers still decide every positive candidate. One complete stream
retains pin-name lines and detects glyph/lineage needles while consuming every
gzip member and its integrity checks. Its cache belongs to one checker context
and is bound to the actual immutable compressed bytes and matcher inputs.
"""

import codecs
import gzip
import io
from dataclasses import dataclass

from vos import pins


class UnsupportedScanError(ValueError):
    """Use the existing complete reader rather than approximating its semantics."""


@dataclass(frozen=True)
class Facts:
    pin_name: bool
    lineage: bool
    # Sparse source retains every candidate line at its original line number.
    # None means this scan was not asked to collect pin candidates.
    pin_text: str | None = None
    glyph: bool | None = None


@dataclass(frozen=True)
class _Entry:
    blob: bytes
    names: tuple[str, ...]
    sensitive: tuple[bytes, ...]
    folded: tuple[bytes, ...]
    glyphs: tuple[bytes, ...]
    facts: Facts


def _bounded_name(text: str, names: tuple[str, ...], *, first: bool, final: bool) -> bool:
    """A candidate with the original pin parser's asymmetric name boundaries."""
    low = text.lower()
    # The old parser indexes its lowered string with original-string positions.
    # Preserve that behavior through its original implementation when lowering
    # changes length; do not silently reinterpret a Unicode source's offsets.
    if len(low) != len(text):
        raise UnsupportedScanError("Unicode lowercase changes source offsets")
    for needle in names:
        at = low.find(needle)
        while at >= 0:
            end = at + len(needle)
            if (at or first) and (end < len(low) or final):
                before = low[at - 1] if at else " "
                after = low[end] if end < len(low) else " "
                if (not (before.isalnum() or before in "_-")
                        and not (after.isalnum() or after == "_")):
                    return True
            at = low.find(needle, at + 1)
    return False


def _streamable(text: str, tail: str) -> str:
    """Lower only source representations whose exact offsets remain available."""
    low = text.lower()
    if len(low) != len(text):
        raise UnsupportedScanError("Unicode lowercase changes source offsets")
    # Avoid quadratic concatenation for one enormous line; the complete reader
    # remains authoritative for that representation.
    if len(tail) > 1024 * 1024:
        raise UnsupportedScanError("archive line requires the complete reader")
    return low


def prescan(blob: bytes, names: tuple[str, ...], sensitive: tuple[bytes, ...],
            folded: tuple[bytes, ...], *, chunk_size: int = 256 * 1024,
            glyphs: tuple[bytes, ...] = ()) -> Facts:
    """Sparse pin candidates and absence facts for the unchanged exact parsers.

    A non-ASCII pin spelling may have context-sensitive lowercase behavior, so
    it retains the old reader. Ordinary Unicode source text is decoded across
    chunk boundaries and participates in the same ``isalnum`` boundaries.
    """
    if chunk_size < 1:
        raise ValueError("archive scan chunk size must be positive")
    if not blob.startswith(b"\x1f\x8b"):
        raise ValueError("missing gzip header")
    if any(not name.isascii() or name != name.lower() or not name
           or "\n" in name or "\r" in name for name in names):
        raise UnsupportedScanError("pin spellings require the complete Unicode reader")
    decoder = io.IncrementalNewlineDecoder(codecs.getincrementaldecoder("utf-8")(), True)
    text_tail = ""
    byte_tail = b""
    byte_overlap = max((len(needle) for needle in (*sensitive, *folded, *glyphs)), default=1) - 1
    pin_name = lineage = glyph = False
    line_base = kept_lines = 0
    parts: list[str] = []
    unsupported: UnicodeDecodeError | UnsupportedScanError | None = None
    with gzip.GzipFile(fileobj=io.BytesIO(blob), mode="rb") as source:
        while True:
            chunk = source.read(chunk_size)
            final = not chunk
            if not lineage or (glyphs and not glyph):
                window = byte_tail + chunk
                if not lineage:
                    low = window.lower()
                    lineage = (any(needle in window for needle in sensitive)
                               or any(needle in low for needle in folded))
                if glyphs and not glyph:
                    glyph = any(needle in window for needle in glyphs)
                byte_tail = window[-byte_overlap:] if byte_overlap else b""
            if unsupported is None and names:
                try:
                    addition = decoder.decode(chunk, final=final)
                    text = text_tail + addition
                    end = len(text) if final else text.rfind("\n") + 1
                    complete, text_tail = text[:end], text[end:]
                    low = _streamable(complete, text_tail)
                    for index, start, finish in pins.candidate_lines(complete, names, lowered=low):
                        line = complete[start:finish]
                        if _bounded_name(line, names, first=True, final=True):
                            pin_name = True
                            at = line_base + index
                            parts.extend(("\n" * (at - kept_lines), line, "\n"))
                            kept_lines = at + 1
                    line_base += complete.count("\n")
                except (UnicodeDecodeError, UnsupportedScanError) as err:
                    # Still consume the entire stream: a late gzip error must not
                    # disappear behind an earlier unsupported text representation.
                    unsupported = err
            if final:
                break
    if unsupported is not None:
        raise UnsupportedScanError(str(unsupported)) from unsupported
    return Facts(pin_name, lineage, "".join(parts) if names else None,
                 glyph if glyphs else None)


class Cache:
    """One run's compact facts, never a persistent or path-authorized verdict."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    def scan(self, path: str, blob: bytes, names: tuple[str, ...],
             sensitive: tuple[bytes, ...], folded: tuple[bytes, ...], *,
             glyphs: tuple[bytes, ...] = ()) -> Facts:
        old = self._entries.get(path)
        if (old is not None and old.blob == blob and old.sensitive == sensitive
                and old.folded == folded and (not names or old.names == names)
                and (not glyphs or old.glyphs == glyphs)):
            return old.facts
        facts = prescan(blob, names, sensitive, folded, glyphs=glyphs)
        self._entries[path] = _Entry(blob, names, sensitive, folded, glyphs, facts)
        return facts
