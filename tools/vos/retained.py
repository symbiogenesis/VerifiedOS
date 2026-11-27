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
import re
from dataclasses import dataclass

from vos import literalsearch, pins


class UnsupportedScanError(ValueError):
    """Use the existing complete reader rather than approximating its semantics."""


@dataclass(frozen=True)
class Facts:
    pin_name: bool
    lineage: bool
    # Sparse source retains every candidate line at its original line number.
    # None means unrequested or unsupported pin text, never a pin absence verdict.
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


@dataclass(frozen=True)
class _Prepared:
    names: tuple[str, ...]
    sensitive: tuple[bytes, ...]
    folded: tuple[bytes, ...]
    glyphs: tuple[bytes, ...]
    name_matcher: literalsearch.CandidateTrie | None
    name_patterns: tuple[tuple[str, re.Pattern[str]], ...] | None
    ascii_sensitive_groups: tuple[tuple[bytes, tuple[bytes, ...]], ...]
    nonascii_sensitive: tuple[bytes, ...]
    folded_has_empty: bool
    folded_trie: re.Pattern[bytes] | None
    minimal_names_bytes: tuple[bytes, ...]
    names_trie: re.Pattern[bytes] | None
    combined_trie: re.Pattern[bytes] | None
    glyphs_require_nonascii: bool
    name_overlap: int
    byte_overlap: int


def _prepare(names: tuple[str, ...], sensitive: tuple[bytes, ...], folded: tuple[bytes, ...],
             glyphs: tuple[bytes, ...]) -> _Prepared:
    if any(not name.isascii() or name != name.lower() or not name
           or "\n" in name or "\r" in name for name in names):
        raise UnsupportedScanError("pin spellings require the complete Unicode reader")
    name_matcher: literalsearch.CandidateTrie | None
    if names:
        try:
            name_matcher = literalsearch.compile_names(names)
        except literalsearch.LegacyRequiredError:
            name_matcher = None
        name_patterns = pins.name_patterns(names) if name_matcher is None else None
    else:
        name_matcher = None
        name_patterns = None
    ascii_sensitive = tuple(needle for needle in sensitive if needle.isascii())
    nonascii_sensitive = tuple(needle for needle in sensitive if not needle.isascii())
    ascii_sensitive_groups = literalsearch.byte_guard_groups(ascii_sensitive)
    folded_has_empty = any(not needle for needle in folded)
    folded_trie = None if (not folded or folded_has_empty) else literalsearch.compile_bytes_trie(folded)
    minimal_names_bytes = tuple(name.encode("ascii") for name in literalsearch.minimal_substrings(names))
    names_trie = (literalsearch.compile_bytes_trie(minimal_names_bytes)
                  if minimal_names_bytes else None)
    combined_trie = (literalsearch.compile_bytes_trie((*folded, *minimal_names_bytes))
                     if folded and not folded_has_empty and minimal_names_bytes else None)
    name_overlap = max((len(name) for name in names), default=0) + 1
    byte_overlap = max((len(needle) for needle in (*sensitive, *folded, *glyphs)), default=1) - 1
    if names:
        byte_overlap = max(byte_overlap, name_overlap)
    return _Prepared(
        names=names, sensitive=sensitive, folded=folded, glyphs=glyphs,
        name_matcher=name_matcher, name_patterns=name_patterns,
        ascii_sensitive_groups=ascii_sensitive_groups, nonascii_sensitive=nonascii_sensitive,
        folded_has_empty=folded_has_empty, folded_trie=folded_trie,
        minimal_names_bytes=minimal_names_bytes, names_trie=names_trie, combined_trie=combined_trie,
        glyphs_require_nonascii=all(not needle.isascii() for needle in glyphs),
        name_overlap=name_overlap, byte_overlap=byte_overlap,
    )


def _bounded_name(text: str, patterns: tuple[tuple[str, re.Pattern[str]], ...], *, first: bool, final: bool,
                  matcher: literalsearch.CandidateTrie | None = None,
                  names: tuple[str, ...] | None = None) -> bool:
    """A candidate with the original pin parser's asymmetric name boundaries."""
    expected_names = tuple(name for name, _ in patterns) if names is None else names
    if matcher is not None and matcher.names == expected_names:
        try:
            return matcher.present(text, first=first, final=final)
        except literalsearch.LegacyRequiredError as error:
            raise UnsupportedScanError(str(error)) from error
    low = text.lower()
    # The old parser indexes its lowered string with original-string positions.
    # Preserve that behavior through its original implementation when lowering
    # changes length; do not silently reinterpret a Unicode source's offsets.
    if len(low) != len(text):
        raise UnsupportedScanError("Unicode lowercase changes source offsets")
    for name, pattern in patterns:
        if name not in low:
            continue
        match = pattern.search(low)
        while match is not None:
            if (match.start() or first) and (match.end() < len(low) or final):
                return True
            # A rejected window-edge hit must not hide an overlapping later hit.
            match = pattern.search(low, match.start() + 1)
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
            glyphs: tuple[bytes, ...] = (),
            _prepared: _Prepared | None = None) -> Facts:
    """Sparse pin candidates and absence facts for the unchanged exact parsers.

    A non-ASCII pin spelling may have context-sensitive lowercase behavior, so
    it retains the old reader. Ordinary Unicode source text is decoded across
    chunk boundaries and participates in the same ``isalnum`` boundaries.
    """
    if chunk_size < 1:
        raise ValueError("archive scan chunk size must be positive")
    if not blob.startswith(b"\x1f\x8b"):
        raise ValueError("missing gzip header")
    plan = _prepared if _prepared is not None else _prepare(names, sensitive, folded, glyphs)
    decoder = io.IncrementalNewlineDecoder(codecs.getincrementaldecoder("utf-8")(), True)
    text_tail = ""
    name_tail = ""
    name_overlap = plan.name_overlap
    decoded_chars = 0
    sparse_supported = True
    tail_has_candidate = False
    byte_tail = b""
    byte_overlap = plan.byte_overlap
    pin_name = lineage = glyph = False
    line_base = kept_lines = 0
    parts: list[str] = []
    unsupported: UnicodeDecodeError | UnsupportedScanError | None = None
    with gzip.GzipFile(fileobj=io.BytesIO(blob), mode="rb") as source:
        while True:
            chunk = source.read(chunk_size)
            final = not chunk
            need_names = unsupported is None and bool(names) and (not pin_name or sparse_supported)
            if not lineage or (glyphs and not glyph) or need_names:
                window = byte_tail + chunk
                window_isascii = window.isascii()
                if not lineage and plan.ascii_sensitive_groups:
                    lineage = any(
                        (not guard or guard in window) and any(needle in window for needle in group)
                        for guard, group in plan.ascii_sensitive_groups
                    )
                if not lineage and not window_isascii and plan.nonascii_sensitive:
                    lineage = any(needle in window for needle in plan.nonascii_sensitive)
                if glyphs and not glyph and not (plan.glyphs_require_nonascii and window_isascii):
                    glyph = any(needle in window for needle in glyphs)

                need_folded = not lineage and bool(folded)
                need_ascii_names = need_names and window_isascii
                names_hit = False
                if need_folded or need_ascii_names:
                    if need_folded and plan.folded_has_empty:
                        lineage = True
                        need_folded = False
                    if need_folded or need_ascii_names:
                        low_bytes = window.lower()
                        if (need_folded and need_ascii_names and plan.combined_trie is not None
                                and plan.folded_trie is not None and plan.names_trie is not None):
                            if plan.combined_trie.search(low_bytes) is not None:
                                lineage = plan.folded_trie.search(low_bytes) is not None
                                names_hit = plan.names_trie.search(low_bytes) is not None
                        else:
                            if need_folded:
                                if plan.folded_trie is not None:
                                    lineage = plan.folded_trie.search(low_bytes) is not None
                                else:
                                    lineage = any(needle in low_bytes for needle in folded)
                            if need_ascii_names:
                                if plan.names_trie is not None:
                                    names_hit = plan.names_trie.search(low_bytes) is not None
                                else:
                                    names_hit = any(needle in low_bytes for needle in plan.minimal_names_bytes)
                byte_tail = window[-byte_overlap:] if byte_overlap else b""
            else:
                window_isascii = False
                names_hit = False
                byte_tail = b""

            if need_names:
                if (not final and window_isascii and not names_hit and not tail_has_candidate
                        and b"\r" not in chunk and decoder.getstate() == (b"", 0)):
                    decoded_chars += len(chunk)
                    if len(chunk) >= name_overlap:
                        name_tail = chunk[-name_overlap:].decode("ascii")
                    else:
                        name_tail = (name_tail + chunk.decode("ascii"))[-name_overlap:]
                    if sparse_supported:
                        if b"\n" in chunk:
                            line_base += chunk.count(b"\n")
                            text_tail = chunk[chunk.rfind(b"\n") + 1:].decode("ascii")
                        else:
                            text_tail += chunk.decode("ascii")
                        if len(text_tail) > 1024 * 1024:
                            sparse_supported = False
                            parts.clear()
                            text_tail = ""
                else:
                    try:
                        addition = decoder.decode(chunk, final=final)
                        if not pin_name:
                            window_text = name_tail + addition
                            pin_name = _bounded_name(window_text, plan.name_patterns or (),
                                                     first=decoded_chars == len(name_tail), final=final,
                                                     matcher=plan.name_matcher, names=names)
                            name_tail = window_text[-name_overlap:]
                        decoded_chars += len(addition)
                        if sparse_supported:
                            text = text_tail + addition
                            end = len(text) if final else text.rfind("\n") + 1
                            complete, text_tail = text[:end], text[end:]
                            low = ""
                            if not pin_name and complete.isascii():
                                if len(text_tail) > 1024 * 1024:
                                    sparse_supported = False
                                    parts.clear()
                                    text_tail = ""
                                    tail_has_candidate = False
                                low = complete
                            else:
                                try:
                                    low = _streamable(complete, text_tail)
                                except UnsupportedScanError:
                                    # A huge line disables sparse text, not the bounded
                                    # streaming proof that every pin spelling is absent.
                                    sparse_supported = False
                                    parts.clear()
                                    text_tail = ""
                                    tail_has_candidate = False
                            if sparse_supported:
                                # The complete streaming name scan covers every prior
                                # chunk and this one. With no name so far, completed
                                # source cannot carry a pin site; keep its line count
                                # and unfinished tail without searching it again.
                                if pin_name:
                                    for index, start, finish in pins.candidate_lines(
                                        complete, names, lowered=low,
                                        patterns=plan.name_patterns,
                                        matcher=plan.name_matcher,
                                    ):
                                        line = complete[start:finish]
                                        if pins.ID_RE.search(line) is None:
                                            continue
                                        at = line_base + index
                                        parts.extend(("\n" * (at - kept_lines), line, "\n"))
                                        kept_lines = at + 1
                                line_base += complete.count("\n")
                                if not text_tail:
                                    tail_has_candidate = False
                                elif not text_tail.isascii():
                                    tail_has_candidate = True
                                elif plan.names_trie is not None:
                                    tail_has_candidate = (
                                        plan.names_trie.search(text_tail.encode("ascii").lower())
                                        is not None
                                    )
                                else:
                                    low_tail = text_tail.lower()
                                    tail_has_candidate = any(name in low_tail for name in names)
                    except (UnicodeDecodeError, UnsupportedScanError) as err:
                        # Still consume the entire stream: a late gzip error must not
                        # disappear behind an earlier unsupported text representation.
                        unsupported = err
                        parts.clear()
                        text_tail = ""
                        tail_has_candidate = False
            if final:
                break
    # Pin parsing can fall back independently of complete byte-level facts. A huge
    # or unsupported text representation must not cause every consumer to inflate
    # the same archive again, nor may it authorize a cached pin absence.
    return Facts(pin_name or unsupported is not None, lineage,
                 "".join(parts) if names and unsupported is None and sparse_supported else None,
                 glyph if glyphs else None)


class Cache:
    """One run's compact facts, never a persistent or path-authorized verdict."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}
        self._plans: dict[tuple[tuple[str, ...], tuple[bytes, ...], tuple[bytes, ...], tuple[bytes, ...]],
                          _Prepared] = {}

    def scan(self, path: str, blob: bytes, names: tuple[str, ...],
             sensitive: tuple[bytes, ...], folded: tuple[bytes, ...], *,
             glyphs: tuple[bytes, ...] = ()) -> Facts:
        old = self._entries.get(path)
        if (old is not None and old.blob == blob and old.sensitive == sensitive
                and old.folded == folded and (not names or old.names == names)
                and (not glyphs or old.glyphs == glyphs)):
            return old.facts
        key = (names, sensitive, folded, glyphs)
        plan = self._plans.get(key)
        if plan is None:
            plan = _prepare(names, sensitive, folded, glyphs)
            self._plans[key] = plan
        facts = prescan(blob, names, sensitive, folded, glyphs=glyphs, _prepared=plan)
        self._entries[path] = _Entry(blob, names, sensitive, folded, glyphs, facts)
        return facts
