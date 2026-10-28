# SPDX-License-Identifier: Apache-2.0
"""Conservative small facts from losslessly compressed audit surfaces.

The original parsers still decide every positive candidate. This pass only proves
that a bounded pin name or a lineage needle is absent, while consuming every gzip
member and its integrity checks. Its cache belongs to one checker context and is
bound to the actual immutable compressed bytes and matcher inputs.
"""

import codecs
import gzip
import io
from dataclasses import dataclass


class UnsupportedScanError(ValueError):
    """Use the existing complete reader rather than approximating its semantics."""


@dataclass(frozen=True)
class Facts:
    pin_name: bool
    lineage: bool


@dataclass(frozen=True)
class _Entry:
    blob: bytes
    names: tuple[str, ...]
    sensitive: tuple[bytes, ...]
    folded: tuple[bytes, ...]
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


def prescan(blob: bytes, names: tuple[str, ...], sensitive: tuple[bytes, ...],
            folded: tuple[bytes, ...], *, chunk_size: int = 256 * 1024) -> Facts:
    """Conservative absence facts; positives retain the complete legacy parser.

    A non-ASCII pin spelling may have context-sensitive lowercase behavior, so
    it retains the old reader. Ordinary Unicode source text is decoded across
    chunk boundaries and participates in the same ``isalnum`` boundaries.
    """
    if chunk_size < 1:
        raise ValueError("archive scan chunk size must be positive")
    if not blob.startswith(b"\x1f\x8b"):
        raise ValueError("missing gzip header")
    if any(not name.isascii() or name != name.lower() or not name for name in names):
        raise UnsupportedScanError("pin spellings require the complete Unicode reader")
    decoder = codecs.getincrementaldecoder("utf-8")()
    text_tail = ""
    byte_tail = b""
    text_overlap = max((len(name) for name in names), default=0) + 1
    byte_overlap = max((len(needle) for needle in (*sensitive, *folded)), default=1) - 1
    pin_name = lineage = False
    decoded_chars = 0
    unsupported: UnicodeDecodeError | UnsupportedScanError | None = None
    with gzip.GzipFile(fileobj=io.BytesIO(blob), mode="rb") as source:
        while True:
            chunk = source.read(chunk_size)
            final = not chunk
            if not lineage:
                window = byte_tail + chunk
                low = window.lower()
                lineage = (any(needle in window for needle in sensitive)
                           or any(needle in low for needle in folded))
                byte_tail = window[-byte_overlap:] if byte_overlap else b""
            if not pin_name and unsupported is None and names:
                try:
                    addition = decoder.decode(chunk, final=final)
                    text = text_tail + addition
                    pin_name = _bounded_name(text, names,
                                             first=decoded_chars == len(text_tail), final=final)
                    decoded_chars += len(addition)
                    text_tail = text[-text_overlap:]
                except (UnicodeDecodeError, UnsupportedScanError) as err:
                    # Still consume the entire stream: a late gzip error must not
                    # disappear behind an earlier unsupported text representation.
                    unsupported = err
            if final:
                break
    if unsupported is not None:
        raise UnsupportedScanError(str(unsupported)) from unsupported
    return Facts(pin_name, lineage)


class Cache:
    """One run's compact facts, never a persistent or path-authorized verdict."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    def scan(self, path: str, blob: bytes, names: tuple[str, ...],
             sensitive: tuple[bytes, ...], folded: tuple[bytes, ...]) -> Facts:
        old = self._entries.get(path)
        if (old is not None and old.blob == blob and old.sensitive == sensitive
                and old.folded == folded and (not names or old.names == names)):
            return old.facts
        facts = prescan(blob, names, sensitive, folded)
        self._entries[path] = _Entry(blob, names, sensitive, folded, facts)
        return facts
