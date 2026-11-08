# SPDX-License-Identifier: Apache-2.0
"""Requirement citations, discharge annotations, and source declaration names in `proofs/*.v`.

Extracts requirement tokens outside derived header blocks (`(*| BEGIN derived ... |*)`),
parses `(*| discharges: R-... |*)` annotations above theorem statements (`STATEMENTS`),
and lists top-level defined names (`DEFINERS`) for host-side checks and navigation.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from vos.proofs import (
    CONTROL_PREFIXES,
    DECLARATIONS,
    STATEMENTS,
    VERNAC_CONTROL,
    VOID,
    decorations,
    marker_depths,
    sentence_ends,
    sentences,
    strip_comments,
    void_flag,
)
from vos.register import REQ_TOKEN_RE

PROOFS = "proofs"
SUFFIX = ".v"

# Derived header region delimiters (`checks/citations.py` K-108).
DERIVED_BEGIN = "(*| BEGIN derived: cited entries |*)"
DERIVED_END = "(*| END derived |*)"
DERIVED_MARK = "(*|"

_DERIVED_RE = re.compile(r"\(\*\|\s*(BEGIN|END)\s+derived\s*(?::[^|\r\n]*)?\|\*\)")
_ANNOTATION_RE = re.compile(r"\(\*\|\s*discharges:[^|\r\n]*\|\*\)")

DEFINERS = DECLARATIONS
MODIFIERS = VERNAC_CONTROL
_DEFINED_RE = re.compile(rf"^({CONTROL_PREFIXES})(?:{'|'.join(DEFINERS)})\s+([\w']+)")

DISCHARGE_OPEN = "(*|"
DISCHARGE_WORD = "discharges"

# Match a `(*| discharges: ... |*)` line and the immediately following vernacular head.
_DISCHARGE_RE = re.compile(
    rf"\(\*\|[^\S\r\n]*{DISCHARGE_WORD}:(?P<ids>[^|\r\n]*)\|\*\)[^\S\r\n]*\r?\n")
_CLAIMED_RE = re.compile(
    rf"[^\S\r\n]*{CONTROL_PREFIXES}(?P<vernac>[A-Za-z]+)[^\S\r\n]+(?P<name>[\w']+)")

type Claim = tuple[str, list[str]]


def is_source(rel: str) -> bool:
    """Return True if `rel` is a `.v` file under `proofs/`."""
    return rel.startswith(f"{PROOFS}/") and rel.endswith(SUFFIX)


def on_disk(root: Path) -> list[str]:
    """Return sorted relative paths of `proofs/*.v` files in the working tree."""
    directory = root / PROOFS
    if not directory.is_dir():
        return []
    return sorted(f"{PROOFS}/{path.name}" for path in directory.glob(f"*{SUFFIX}"))


def read(root: Path, rels: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """Read `(rel, text)` pairs for `rels`, returning any missing/decode faults separately."""
    pairs: list[tuple[str, str]] = []
    faults: list[str] = []
    for rel in rels:
        path = root / rel
        if not path.is_file():
            faults.append(f"{rel} is listed and not in the working tree, so there are "
                          "no bytes here to read")
            continue
        try:
            pairs.append((rel, path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError) as exc:
            faults.append(f"{rel} is unreadable, so its citations cannot be decided "
                          f"({exc})")
    return pairs, faults


@dataclass(frozen=True)
class Derived:
    """Balanced derived-header character spans `(start, end)` or delimiter faults.

    `spans` is empty whenever `faults` is non-empty so malformed delimiters never
    silently exclude citations.
    """

    spans: tuple[tuple[int, int], ...] = ()
    faults: tuple[str, ...] = ()


def line_at(text: str, offset: int) -> int:
    """Return the 1-based line number of `offset` in `text`."""
    return text.count("\n", 0, offset) + 1


def derived(text: str) -> Derived:
    """Parse `(*| BEGIN/END derived |*)` spans in `text` and report any delimiter faults."""
    if DERIVED_MARK not in text:
        return Derived()

    spans: list[tuple[int, int]] = []
    faults: list[str] = []
    opened_at: int | None = None
    content_from = 0
    read = 0
    for m in _DERIVED_RE.finditer(text):
        read += 1
        if m.group(1) == "BEGIN":
            if opened_at is not None:
                faults.append(f"line {line_at(text, m.start())} opens a derived region "
                              f"inside the one line {line_at(text, opened_at)} opened, "
                              "and a region does not nest")
            else:
                opened_at, content_from = m.start(), m.end()
        elif opened_at is None:
            faults.append(f"line {line_at(text, m.start())} closes a derived region no "
                          "line above it opened")
        else:
            spans.append((content_from, m.start()))
            opened_at = None

    if opened_at is not None:
        faults.append(f"line {line_at(text, opened_at)} opens a derived region the file "
                      "never closes, which is the delimiter that would hold every "
                      "citation below it out of the reading")
    stray = text.count(DERIVED_MARK) - read - len(_ANNOTATION_RE.findall(text))
    if stray:
        faults.append(f"{stray} occurrence(s) of `{DERIVED_MARK}` are neither a BEGIN "
                      "nor an END this parse reads, nor a discharge annotation, so a "
                      "region may be delimited by a marker nothing excludes")

    return Derived((), tuple(faults)) if faults else Derived(tuple(spans), ())


def ids(text: str, region: Derived | None = None) -> list[str]:
    """Return all requirement IDs cited in `text` outside balanced `Derived` spans."""
    if region is None:
        region = derived(text)
    if not region.spans:
        return cast("list[str]", REQ_TOKEN_RE.findall(text))
    return [m.group() for m in REQ_TOKEN_RE.finditer(text)
            if not any(start <= m.start() < end for start, end in region.spans)]


def cited_within(text: str, span: tuple[int, int]) -> list[str]:
    """Return all requirement IDs cited within `span` of `text`."""
    return cast("list[str]", REQ_TOKEN_RE.findall(text, span[0], span[1]))


class ParseCache:
    """Per-invocation cache of `Derived` spans and cited requirement IDs keyed by source text."""

    def __init__(self) -> None:
        self._regions: dict[str, Derived] = {}
        self._ids: dict[str, tuple[str, ...]] = {}

    def region(self, text: str) -> Derived:
        if text not in self._regions:
            self._regions[text] = derived(text)
        return self._regions[text]

    def ids(self, text: str) -> tuple[str, ...]:
        if text not in self._ids:
            self._ids[text] = tuple(ids(text, self.region(text)))
        return self._ids[text]


def _void(decorated: str) -> str | None:
    """Return `'Fail'` or `'Succeed'` if present in `decorated`."""
    found, _ = decorations(decorated)
    return next((str(decoration.group("word")) for decoration in found
                 if decoration.group("word") in VOID), None)


def names(text: str) -> list[str]:
    """Return top-level constant names defined in `text` (excluding `Fail`/`Succeed`)."""
    found: list[str] = []
    for sentence in sentences(text):
        m = _DEFINED_RE.match(sentence)
        if m and _void(m.group(1)) is None:
            found.append(m.group(2))
    return found


def _listed(body: str) -> tuple[list[str], str | None]:
    """Parse a comma-separated list of distinct requirement IDs, or return a fault message."""
    found: list[str] = []
    for token in body.split(","):
        word = token.strip()
        if not word:
            return [], ("an empty entry in its id list, so the list is not a "
                        "comma-separated one" if body.strip() else
                        "no requirement id at all, so it claims nothing")
        if not REQ_TOKEN_RE.fullmatch(word):
            return [], (f"{word!r} in its id list, which is not a requirement id; the "
                        "form is comma-separated R-nn-nnn with an optional letter "
                        "suffix and nothing else")
        if word in found:
            return [], (f"{word} twice in one id list, so how many entries the "
                        "annotation claims depends on which of the two is read")
        found.append(word)
    return found, None


def discharges(text: str) -> tuple[list[Claim], list[str]]:
    """Parse `(symbol_name, requirement_ids)` discharge claims and syntax faults from `text`."""
    claims: list[Claim] = []
    faults: list[str] = []
    depths = marker_depths(text, DISCHARGE_OPEN) if DISCHARGE_OPEN in text else {}
    blanked: tuple[str, list[int]] | None = None
    at, line = 0, 1
    while (mark := text.find(DISCHARGE_OPEN, at)) >= 0:
        line += text.count("\n", at, mark)
        at = mark + len(DISCHARGE_OPEN)
        if _DERIVED_RE.match(text, mark):
            continue
        if depths.get(mark) != 0:
            faults.append(f"line {line} places a discharge inside an enclosing "
                          "comment or string, where it binds no compiled statement")
            continue
        head = text.rfind("\n", 0, mark) + 1
        if text[head:mark].strip():
            faults.append(f"line {line} opens {DISCHARGE_OPEN} with code before it on "
                          "the same line; a discharge annotation sits alone on the line "
                          "above the statement it claims")
            continue
        hit = _DISCHARGE_RE.match(text, mark)
        if hit is not None and blanked is None:
            code = strip_comments(text, keep_offsets=True)
            blanked = (code, sentence_ends(code))
        claimed = _CLAIMED_RE.match(blanked[0], hit.end()) if hit and blanked else None
        if hit is None or blanked is None or claimed is None:
            faults.append(f"line {line} opens {DISCHARGE_OPEN} and no discharge "
                          f"annotation follows it; the form is `{DISCHARGE_OPEN} "
                          f"{DISCHARGE_WORD}: R-nn-nnn |*)` alone on its line, with a "
                          "statement on the next line and no blank line between")
            continue
        listed, fault = _listed(hit.group("ids"))
        if fault is not None:
            faults.append(f"line {line} states {fault}")
            continue
        vernac, name = claimed.group("vernac"), claimed.group("name")
        if vernac not in STATEMENTS:
            faults.append(f"line {line} claims {', '.join(listed)} above "
                          f"`{vernac} {name}`, which states nothing; a discharge sits "
                          f"above one of {', '.join(STATEMENTS)}")
            continue
        if (flag := void_flag(blanked[0], claimed.start(), blanked[1])) is not None:
            faults.append(f"line {line} claims {', '.join(listed)} above `{vernac} {name}` "
                          f"under `{flag}`, which keeps nothing it states")
            continue
        claims.append((name, listed))
    return claims, faults


def citations(pairs: list[tuple[str, str]]) -> dict[str, set[str]]:
    """Map each `(rel, text)` pair to the set of requirement IDs it cites."""
    return {rel: set(ids(text)) for rel, text in pairs}


def claims(pairs: list[tuple[str, str]]) -> tuple[dict[str, list[Claim]], list[str]]:
    """Map each `(rel, text)` pair to its deduplicated discharge `Claim` list and collect faults."""
    index: dict[str, list[Claim]] = {}
    faults: list[str] = []
    for rel, text in pairs:
        found, problems = discharges(text)
        faults += [f"{rel}: {problem}" for problem in problems]
        seen: set[str] = set()
        kept: list[Claim] = []
        for name, listed in found:
            if name in seen:
                faults.append(f"{rel}: `{name}` carries more than one discharge "
                              "annotation, so what that constant claims is stated twice")
                continue
            seen.add(name)
            kept.append((name, listed))
        index[rel] = kept
    return index, faults


def constants(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Map each `(rel, text)` pair to the list of top-level constants it defines."""
    return {rel: names(text) for rel, text in pairs}


def citing(index: dict[str, set[str]], ident: str) -> list[str]:
    """Return the artifact paths in `index` that cite requirement `ident`."""
    return [rel for rel, cited in index.items() if ident in cited]
