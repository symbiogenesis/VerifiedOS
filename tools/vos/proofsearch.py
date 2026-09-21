# SPDX-License-Identifier: Apache-2.0
"""Fresh, advisory navigation of local Rocq source, with no prover or index.

This is a limited lexical reader, not Gallina elaboration. It recognizes the named
declarations in proofcites.DEFINERS, optional attributes/locality modifiers, direct
bodies and ordinary Qed/Defined/Admitted/Abort endings. It does not resolve modules,
notation, generated obligations, mutual secondary names or tactic semantics. A
script token can be a variable or term as well as a tactic. In particular, lexical
completion is no evidence that a file compiles or meets its assumption contract.

Offsets survive comment/string masking, so an excerpt, location and raw-byte hash
describe the same read. Files are read separately, not as an atomic tree snapshot.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict

from vos import proofcites
from vos.register import REQ_TOKEN_RE

type Status = Literal["complete", "admitted", "aborted", "incomplete", "definition"]

ADVISORY = "Source navigation only; no proof, assumption or environment validation."
_TOKEN = re.compile(r"[\w']+")
_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")
_HEAD = re.compile(
    r"^(?:#\[[^\]]*\]\s*|(?:Local|Global|Program|Polymorphic|Monomorphic|"
    r"Cumulative|NonCumulative)\s+)*"
    rf"(?P<kind>{'|'.join(proofcites.DEFINERS)})\s+(?P<name>[\w']+)")
_CLOSE = re.compile(r"^[\s{}]*?(Qed|Defined|Admitted|Abort)\s*\.$")


class Match(TypedDict):
    """One source span, with only lexical metadata."""

    path: str
    line: int
    end_line: int
    name: str
    kind: str
    status: Status
    source_sha256: str
    requirements: list[str]
    excerpt: str
    excerpt_truncated: bool
    score: int
    matched_terms: list[str]


class Report(TypedDict):
    """Versioned result described by tools/proof-search.schema.json."""

    version: Literal[1]
    advisory_only: Literal[True]
    notice: str
    query: str
    tactics: list[str]
    requirements: list[str]
    excluded: list[str]
    limit: int
    max_chars: int
    sources_read: int
    total_matches: int
    truncated: bool
    matches: list[Match]


@dataclass(frozen=True)
class _Sentence:
    start: int
    end: int
    code: str
    terminated: bool


@dataclass(frozen=True)
class _Declaration:
    start: int
    statement_end: int
    end: int
    name: str
    kind: str
    status: Status


def _masked(text: str) -> str:
    """Blank nested comments and string contents, preserving offsets and quotes.

    Outer quotes keep an unfinished command's final string in its source span;
    doubled quotes inside a string are masked with the rest of its contents.
    """
    chars = list(text)
    pos, depth = 0, 0
    quoted = False
    while pos < len(text):
        pair = text[pos:pos + 2]
        size = 1
        hidden = depth > 0 or quoted
        if depth:
            if pair == "(*":
                depth += 1
                size = 2
            elif pair == "*)":
                depth -= 1
                size = 2
        elif quoted:
            if pair == '""':
                size = 2
            elif text[pos] == '"':
                quoted, hidden = False, False
        elif pair == "(*":
            depth = 1
            size, hidden = 2, True
        elif pair == "*)":
            raise ValueError(f"line {proofcites.line_at(text, pos)}: unmatched comment ending")
        elif text[pos] == '"':
            quoted, hidden = True, False
        if hidden:
            for index in range(pos, pos + size):
                if chars[index] not in "\r\n":
                    chars[index] = " "
        pos += size
    if depth or quoted:
        raise ValueError("unterminated " + ("comment" if depth else "string"))
    return "".join(chars)


def _sentences(code: str) -> list[_Sentence]:
    """Locate full stops outside masked text, retaining an unfinished last command."""
    result: list[_Sentence] = []
    start = 0
    for pos, char in enumerate(code):
        if (char != "." or (pos and code[pos - 1] == ".")
                or (pos + 1 < len(code) and not code[pos + 1].isspace())):
            continue
        raw = code[start:pos + 1]
        begin = start + len(raw) - len(raw.lstrip())
        if begin < pos + 1:
            result.append(_Sentence(begin, pos + 1, raw.strip(), True))
        start = pos + 1
    raw = code[start:]
    if raw.strip():
        begin = start + len(raw) - len(raw.lstrip())
        result.append(_Sentence(begin, len(code.rstrip()), raw.strip(), False))
    return result


def _direct_body(code: str) -> bool:
    """Distinguish a top-level := body from a binder such as (n := 0)."""
    depth = 0
    for pos, char in enumerate(code):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif depth == 0 and code[pos:pos + 2] == ":=":
            return True
    return False


def _declarations(code: str) -> list[_Declaration]:
    result: list[_Declaration] = []
    pending: tuple[_Sentence, str, str] | None = None
    pending_end = 0
    for sentence in _sentences(code):
        head = _HEAD.match(sentence.code)
        if head:
            if pending:
                first, name, kind = pending
                result.append(_Declaration(first.start, first.end, pending_end,
                                           name, kind, "incomplete"))
            name, kind = head["name"], head["kind"]
            if sentence.terminated and _direct_body(sentence.code[head.end():]):
                result.append(_Declaration(sentence.start, sentence.end, sentence.end,
                                           name, kind, "definition"))
                pending = None
            else:
                pending = (sentence, name, kind)
                pending_end = sentence.end
        elif pending:
            pending_end = sentence.end
            close = _CLOSE.fullmatch(sentence.code) if sentence.terminated else None
            if close:
                first, name, kind = pending
                status: Status = ("admitted" if close[1] == "Admitted" else
                                  "aborted" if close[1] == "Abort" else "complete")
                result.append(_Declaration(first.start, first.end, sentence.end,
                                           name, kind, status))
                pending = None
    if pending:
        first, name, kind = pending
        result.append(_Declaration(first.start, first.end, pending_end,
                                   name, kind, "incomplete"))
    return result


def _words(text: str) -> set[str]:
    """Case-insensitive identifier tokens and their underscore-separated words."""
    lowered = text.casefold()
    return set(_TOKEN.findall(lowered)) | set(_WORD.findall(lowered))


def _walk_error(error: OSError) -> None:
    raise error


def _sources(root: Path) -> list[Path]:
    directory = root / proofcites.PROOFS
    if not directory.is_dir() or directory.is_symlink() or directory.is_junction():
        raise ValueError("proofs must be an ordinary directory in this checkout")
    result: list[Path] = []
    for parent, directories, files in directory.walk(on_error=_walk_error):
        for name in directories + files:
            path = parent / name
            if path.is_symlink() or path.is_junction():
                raise ValueError(f"{path.relative_to(root).as_posix()}: linked paths are unsupported")
            if path.suffix != proofcites.SUFFIX:
                continue
            rel = path.relative_to(root).as_posix()
            if parent != directory or not path.is_file():
                raise ValueError(f"{rel}: proof sources must be regular files directly in proofs/")
            result.append(path)
    return sorted(result)


def validate(query: str, tactics: tuple[str, ...], requirements: tuple[str, ...],
             exclude: tuple[str, ...], limit: int, max_chars: int) -> None:
    """Reject malformed selectors before reading any source."""
    if not 1 <= limit <= 50 or not 256 <= max_chars <= 16000:
        raise ValueError("--limit must be 1..50 and --max-chars must be 256..16000")
    if query and not _WORD.search(query):
        raise ValueError("query must contain a word")
    if not query.strip() and not tactics and not requirements:
        raise ValueError("provide query words, --tactic or --requirement")
    if any(not _TOKEN.fullmatch(word) or not _WORD.search(word) for word in tactics):
        raise ValueError("each --tactic must be one identifier token")
    if any(not REQ_TOKEN_RE.fullmatch(ident) for ident in requirements):
        raise ValueError("each --requirement must be an R-nn-nnn id with an optional letter suffix")
    if any(not re.fullmatch(r"proofs/[^/\\\x00]+\.v", rel) for rel in exclude):
        raise ValueError("each --exclude must be a repository-relative proofs/Name.v path")


def search(root: Path, query: str = "", *, tactics: tuple[str, ...] = (),
           requirements: tuple[str, ...] = (), exclude: tuple[str, ...] = (),
           limit: int = 5, max_chars: int = 1600) -> Report:
    """Read current sources and rank lexical matches; errors never yield partial output.

    Query words are ORed, each contributing its strongest weight: name 8, statement
    4, script 1. Every tactic-token and requirement filter must match, contributing
    2 and 1 respectively. Ties sort by path, line and name. Requirement references
    belong to the whole file and exclude proofcites' derived manifest regions.
    """
    validate(query, tactics, requirements, exclude, limit, max_chars)
    terms = _words(query)
    tactic_terms = {word.casefold() for word in tactics}
    wanted = set(requirements)
    matches: list[Match] = []
    sources = _sources(root)
    read = 0
    for path in sources:
        rel = path.relative_to(root).as_posix()
        if rel in exclude:
            continue
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8-sig")
            code = _masked(text)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError(f"{rel}: {exc}") from exc
        region = proofcites.derived(text)
        if region.faults:
            raise ValueError(f"{rel}: {'; '.join(region.faults)}")
        read += 1
        cited = sorted(set(proofcites.ids(text, region)))
        if not wanted.issubset(cited):
            continue
        digest = hashlib.sha256(raw).hexdigest()
        for declaration in _declarations(code):
            name_words = _words(declaration.name)
            statement_words = _words(code[declaration.start:declaration.statement_end])
            script = code[declaration.statement_end:declaration.end]
            script_tokens = set(_TOKEN.findall(script.casefold()))
            if not tactic_terms.issubset(script_tokens):
                continue
            body_words = _words(script)
            found = terms & (name_words | statement_words | body_words)
            if terms and not found:
                continue
            score = sum(8 if word in name_words else 4 if word in statement_words else 1
                        for word in found) + 2 * len(tactic_terms) + len(wanted)
            excerpt = text[declaration.start:declaration.end]
            matches.append(Match(
                path=rel, line=proofcites.line_at(text, declaration.start),
                end_line=proofcites.line_at(text, declaration.end - 1),
                name=declaration.name, kind=declaration.kind, status=declaration.status,
                source_sha256=digest, requirements=cited, excerpt=excerpt[:max_chars],
                excerpt_truncated=len(excerpt) > max_chars, score=score,
                matched_terms=sorted(found | tactic_terms | wanted)))
    matches.sort(key=lambda hit: (-hit["score"], hit["path"], hit["line"], hit["name"]))
    return Report(version=1, advisory_only=True, notice=ADVISORY, query=query,
                  tactics=sorted(tactic_terms), requirements=sorted(wanted),
                  excluded=sorted(set(exclude)), limit=limit, max_chars=max_chars,
                  sources_read=read, total_matches=len(matches),
                  truncated=len(matches) > limit, matches=matches[:limit])
