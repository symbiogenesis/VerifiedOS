# SPDX-License-Identifier: Apache-2.0
"""Advisory navigation of the compiler bundle against its recorded local owners.

Only the emitter's declarations and links are read. No Sail grammar, inferred call
graph, compiler invocation or persistent index lives here. Every invocation reads
the bundle and all recorded local owners once. MD5 detects accidental staleness;
SHA-256 identifies those individual reads, not an atomic snapshot or authenticity.
"""

import hashlib
import re
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict

from vos import sailbundle

type Operation = Literal["search", "symbol", "references"]
KINDS = tuple(kind for _, kind in sailbundle.DECLARATION_KINDS)
NOTICE = ("Advisory context only. Freshness covers recorded local owners, not project "
          "selection, unrecorded files, compiler options or installed libraries. "
          "References are compiler-recorded links, not a complete call graph. "
          "Unlocated and unrecorded declarations and links are omitted; no result establishes "
          "compilation or behavioral correctness.")
_TOKEN = re.compile(r"[\w']+")
_WORD = re.compile(r"[^\W_]+")
_RESERVED = frozenset(("CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                       *(f"{prefix}{digit}" for prefix in ("COM", "LPT")
                         for digit in "123456789¹²³")))


class Match(TypedDict):
    """A declaration span or compiler link in a checked local source."""

    kind: str
    symbol: str
    clause: int | None
    target: str | None
    reference_kind: str | None
    path: str
    line: int
    column: int
    end_line: int
    end_column: int
    start_byte: int
    end_byte: int
    source_sha256: str
    excerpt: str
    excerpt_start_byte: int
    excerpt_end_byte: int
    excerpt_truncated: bool
    score: int
    matched_terms: list[str]


class Coverage(TypedDict):
    local_declarations: int
    unlocated_declarations: int
    unrecorded_declarations: int
    local_references: int
    unlocated_references: int
    unrecorded_references: int


class Omitted(TypedDict):
    unlocated: int
    unrecorded: int


class Report(TypedDict):
    version: Literal[1]
    advisory_only: Literal[True]
    notice: str
    operation: Operation
    query: str
    kinds: list[str]
    excluded: list[str]
    known_symbol: bool | None
    bundle_path: str
    bundle_sha256: str
    sources_checked: int
    coverage: Coverage
    omitted_matches: Omitted
    limit: int
    max_chars: int
    total_matches: int
    truncated: bool
    matches: list[Match]


@dataclass(frozen=True)
class _Owner:
    raw: bytes
    sha256: str
    lines: tuple[int, ...]


def _parts(rel: str) -> list[str]:
    parts = rel.split("/")
    if (not rel or any(part in ("", ".", "..") for part in parts)
            or any(char in rel for char in '\\:<>"|?*') or any(ord(char) < 32 or ord(char) == 127 for char in rel)
            or any(part.endswith((" ", ".")) or part.split(".", 1)[0].upper() in _RESERVED
                   for part in parts)):
        raise ValueError(f"unsafe repository-relative path {rel!r}")
    return parts


def _safe_path(root: Path, rel: str) -> Path:
    path = root
    for part in _parts(rel):
        path /= part
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"{rel}: symbolic links and junctions are not source owners")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"{rel}: path escapes the checkout")
    return path


def _source_path(file: str) -> str:
    _parts(file)
    return f"{sailbundle.SOURCE_ROOT}/{file}"


def _read(root: Path) -> tuple[sailbundle.Bundle, str, dict[str, _Owner]]:
    path = _safe_path(root, sailbundle.BUNDLE)
    if not path.is_file():
        raise ValueError(f"{sailbundle.BUNDLE}: missing regular bundle file")
    raw = path.read_bytes()
    bundle = sailbundle.parse(raw)
    # Validate canonical external names without reading an installed library.
    for key in bundle.library_owners():
        _parts(key.removeprefix(sailbundle.LIBRARY_PREFIX))
    for key, digest in bundle.hashes.items():
        if not re.fullmatch(r"[0-9a-f]{32}", digest):
            raise ValueError(f"{key}: malformed recorded MD5")
    owners: dict[str, _Owner] = {}
    for rel, expected in sorted(bundle.owners().items()):
        path = _safe_path(root, rel)
        if not path.is_file():
            raise ValueError(f"{rel}: missing regular source owner")
        try:
            data = path.read_bytes()
            data.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise ValueError(f"{rel}: cannot read UTF-8 source: {exc}") from exc
        if hashlib.md5(data, usedforsecurity=False).hexdigest() != expected:
            raise ValueError(f"{rel}: recorded owner digest differs from current bytes; "
                             "regenerate and compare the bundle before using its context")
        owners[rel] = _Owner(data, hashlib.sha256(data).hexdigest(),
                             tuple([0] + [pos + 1 for pos, byte in enumerate(data) if byte == 10]))
    return bundle, hashlib.sha256(raw).hexdigest(), owners


def _position(owner: _Owner, offset: int) -> tuple[int, int, int]:
    if not 0 <= offset <= len(owner.raw):
        raise ValueError(f"byte location {offset} is outside its source")
    line = bisect_right(owner.lines, offset)
    bol = owner.lines[line - 1]
    try:
        column = len(owner.raw[bol:offset].decode("utf-8")) + 1
    except UnicodeError as exc:
        raise ValueError(f"byte location {offset} splits a UTF-8 character") from exc
    return line, column, bol


def _span(owner: _Owner, start: int, end: int) -> tuple[int, int, int, int]:
    if end < start:
        raise ValueError("source byte span is reversed")
    line, column, _ = _position(owner, start)
    end_line, end_column, _ = _position(owner, end)
    return line, column, end_line, end_column


def _declaration_valid(declaration: sailbundle.Declaration, owner: _Owner) -> None:
    loc = declaration.source.loc
    if loc is None:
        raise ValueError("a local declaration has no source location")
    start_line, _, start_bol = _position(owner, loc[2])
    end_line, _, end_bol = _position(owner, loc[5])
    if (start_line, start_bol, end_line, end_bol) != (loc[0], loc[1], loc[3], loc[4]):
        raise ValueError(f"{declaration.name}: source line metadata disagrees with byte locations")
    if owner.raw[loc[2]:loc[5]].decode("utf-8") != declaration.source.contents:
        raise ValueError(f"{declaration.name}: embedded source differs from its recorded byte span")


def _words(text: str) -> set[str]:
    lowered = text.casefold()
    return {match.group(0) for pattern in (_TOKEN, _WORD) for match in pattern.finditer(lowered)}


def validate(operation: str, query: str, kinds: tuple[str, ...], exclude: tuple[str, ...],
             limit: int, max_chars: int) -> None:
    """Validate selectors before source reads; exclusion membership is checked later."""
    if operation not in ("search", "symbol", "references") or not query.strip():
        raise ValueError("provide search words or an exact symbol name")
    if operation == "search" and not _WORD.search(query):
        raise ValueError("search requires at least one word")
    if not 1 <= limit <= 50 or not 256 <= max_chars <= 16000:
        raise ValueError("--limit must be 1..50 and --max-chars must be 256..16000")
    if any(kind not in KINDS for kind in kinds):
        raise ValueError("unsupported declaration kind")
    if operation != "search" and (kinds or exclude):
        raise ValueError("--kind and --exclude apply only to search")
    for rel in exclude:
        _parts(rel)
        if not rel.startswith(sailbundle.SOURCE_ROOT + "/"):
            raise ValueError("--exclude requires an exact model/model/... owner path")


def _match(kind: str, symbol: str, clause: int | None, target: str | None,
           reference_kind: str | None, path: str, owner: _Owner,
           start: int, end: int, excerpt_start: int, excerpt_end: int,
           max_chars: int, score: int, terms: list[str]) -> Match:
    line, column, end_line, end_column = _span(owner, start, end)
    text = owner.raw[excerpt_start:excerpt_end].decode("utf-8")
    excerpt = text[:max_chars]
    return Match(kind=kind, symbol=symbol, clause=clause, target=target,
                 reference_kind=reference_kind, path=path, line=line, column=column,
                 end_line=end_line, end_column=end_column, start_byte=start, end_byte=end,
                 source_sha256=owner.sha256, excerpt=excerpt,
                 excerpt_start_byte=excerpt_start,
                 excerpt_end_byte=excerpt_start + len(excerpt.encode("utf-8")),
                 excerpt_truncated=len(text) > max_chars, score=score, matched_terms=terms)


def context(root: Path, operation: Operation, query: str, *, kinds: tuple[str, ...] = (),
            exclude: tuple[str, ...] = (), limit: int = 5, max_chars: int = 1600) -> Report:
    """Validate every recorded local owner, then return bounded compiler context.

    Search words are ORed, each scoring 8 in the name or 1 in emitted source text.
    Exact lookup remains case-sensitive. A result is one declaration/clause or one
    link; scattered clauses are never collapsed by symbol. Unlocated declarations
    and located entries with no recorded owner are counted, never presented as fresh.
    """
    validate(operation, query, kinds, exclude, limit, max_chars)
    bundle, bundle_hash, owners = _read(root)
    missing = set(exclude) - owners.keys()
    if missing:
        raise ValueError("--exclude is not a recorded local owner: " + ", ".join(sorted(missing)))
    declarations, references = bundle.declarations(), bundle.references()
    coverage = Coverage(local_declarations=0, unlocated_declarations=0,
                        unrecorded_declarations=0, local_references=0,
                        unlocated_references=0, unrecorded_references=0)
    checked_paths = set(owners)
    for declaration in declarations:
        source = declaration.source
        if source.file is None:
            coverage["unlocated_declarations"] += 1
            continue
        rel = _source_path(source.file)
        if rel not in checked_paths:
            _safe_path(root, rel)
            checked_paths.add(rel)
        if rel not in owners:
            coverage["unrecorded_declarations"] += 1
            continue
        _declaration_valid(declaration, owners[rel])
        coverage["local_declarations"] += 1
    for reference in references:
        if reference.file is None:
            coverage["unlocated_references"] += 1
            continue
        rel = _source_path(reference.file)
        if rel not in checked_paths:
            _safe_path(root, rel)
            checked_paths.add(rel)
        if rel not in owners:
            coverage["unrecorded_references"] += 1
            continue
        _span(owners[rel], reference.start, reference.end)
        coverage["local_references"] += 1
    omitted = Omitted(unlocated=0, unrecorded=0)
    matches: list[Match] = []
    query_words = _words(query)
    if operation == "references":
        for reference in references:
            if reference.target != query:
                continue
            if reference.file is None:
                omitted["unlocated"] += 1
                continue
            rel = _source_path(reference.file)
            if rel not in owners:
                omitted["unrecorded"] += 1
                continue
            owner = owners[rel]
            _, _, begin = _position(owner, reference.start)
            line_start = begin
            prefix = owner.raw[begin:reference.start].decode("utf-8")
            target_chars = len(owner.raw[reference.start:reference.end].decode("utf-8"))
            if len(prefix) + target_chars > max_chars:
                # Keep the queried occurrence visible on long lines. The source
                # offsets still identify the exact returned window.
                before = min(80, max(0, max_chars - target_chars))
                kept = prefix[-before:] if before else ""
                begin = reference.start - len(kept.encode("utf-8"))
            newline = owner.raw.find(b"\n", reference.end)
            finish = len(owner.raw) if newline < 0 else newline
            hit = _match(reference.kind, reference.name, None, reference.target,
                         reference.target_kind, rel, owner, reference.start,
                         reference.end, begin, finish, max_chars, 0, [])
            hit["excerpt_truncated"] |= begin != line_start
            matches.append(hit)
    else:
        for declaration in declarations:
            if kinds and declaration.kind not in kinds:
                continue
            source = declaration.source
            rel = _source_path(source.file) if source.file is not None else None
            if rel in exclude:
                continue
            name_words = _words(declaration.name)
            found = query_words & (name_words | _words(source.contents))
            if ((operation == "symbol" and declaration.name != query)
                    or (operation == "search" and not found)):
                continue
            if rel is None:
                omitted["unlocated"] += 1
                continue
            if rel not in owners:
                omitted["unrecorded"] += 1
                continue
            loc = source.loc
            if loc is None:
                raise ValueError(f"{declaration.name}: local source has no location")
            score = sum(8 if term in name_words else 1 for term in found) if operation == "search" else 0
            matches.append(_match(declaration.kind, declaration.name, declaration.clause,
                                  None, None, rel, owners[rel], loc[2], loc[5], loc[2], loc[5],
                                  max_chars, score, sorted(found) if operation == "search" else []))
    matches.sort(key=lambda hit: (-hit["score"], hit["path"], hit["start_byte"], hit["end_byte"],
                                  hit["kind"], hit["symbol"], hit["clause"] or 0,
                                  hit["reference_kind"] or ""))
    return Report(version=1, advisory_only=True, notice=NOTICE, operation=operation, query=query,
                  kinds=sorted(set(kinds)), excluded=sorted(set(exclude)),
                  known_symbol=(None if operation == "search" else
                                any(declaration.name == query for declaration in declarations)
                                or any(reference.target == query for reference in references)),
                  bundle_path=sailbundle.BUNDLE, bundle_sha256=bundle_hash,
                  sources_checked=len(owners), coverage=coverage, omitted_matches=omitted,
                  limit=limit, max_chars=max_chars, total_matches=len(matches),
                  truncated=len(matches) > limit, matches=matches[:limit])
