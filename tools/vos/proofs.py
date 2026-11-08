# SPDX-License-Identifier: Apache-2.0
"""Lexical comment stripping, sentence splitting, decorations, and `Require` ordering for `.v` sources."""

import re
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from types import MappingProxyType

from vos import prooflex

# Match `From X Require [Import|Export] Y...` and bare `Require` sentences.
REQUIRE = re.compile(r"^(?:From\s+(\S+)\s+)?Require(?:\s+(?:Import|Export))?\s+(.+)$")

# Sentence terminator: a `.` (or `...`, but not the second `.` of `..`) followed by
# whitespace or EOF outside comments and string literals.
SENTENCE_END = re.compile(r"(?<!(?<!\.)\.)\.(?=\s|$)")
_SENTENCE_TOKEN = re.compile(r'"[^"]*(?:"|\Z)|' + SENTENCE_END.pattern)

# Tokens that can precede a Rocq 9.3 vernacular command within a sentence:
# proof bullets/braces/goal selectors (`BULLETS`), `vernac_control` flags (`CONTROL_FLAGS`),
# quoted attributes (`#[...]`), and legacy attributes (`LEGACY_ATTRIBUTES`).
_QUOTED = r'"(?:[^"]|"")*"\s*'
_ATTRIBUTE_VALUES = r'(?:[^\[\]"]|"[^"]*")*'
BULLETS = r"[-+*{}]\s*|(?:\d+|\[[\w']+\]|!)\s*:\s*\{\s*"
CONTROL_FLAGS = (r"(?:Time|Instructions|Fail|Succeed)(?![\w'])\s*"
                 r"|Profile(?![\w'])\s*(?:" + _QUOTED + r")?|Redirect\s*" + _QUOTED
                 + r"|Timeout\s+\d+\s*|AllocLimit\s+\d+\s*(?:Mw|kw)(?![\w'])\s*")
ATTRIBUTE_OPEN = r"#\[" + _ATTRIBUTE_VALUES
LEGACY_ATTRIBUTES = (r"(?:Local|Global|Export|Polymorphic|Monomorphic|Cumulative"
                     r"|NonCumulative|Private|Program)(?![\w'])\s*")
CONTROL_PREFIXES = ("(?:" + BULLETS + "|" + CONTROL_FLAGS + "|" + ATTRIBUTE_OPEN + r"\]\s*|"
                    + LEGACY_ATTRIBUTES + ")*")
VERNAC_CONTROL = ("(?:" + CONTROL_FLAGS + "|" + ATTRIBUTE_OPEN + r"\]\s*|" + LEGACY_ATTRIBUTES
                  + ")*")
DECORATION = re.compile("(?P<bullet>" + BULLETS + r")|(?=(?P<word>[A-Za-z]+))(?:"
                        + CONTROL_FLAGS + "|" + LEGACY_ATTRIBUTES + r")|#\[(?P<attributes>"
                        + _ATTRIBUTE_VALUES + r")\]\s*")
# Control flags that execute a command without retaining its effect.
VOID = ("Fail", "Succeed")
_BLANK = re.compile(r"\s*")

# Vernacular keywords that state a proposition (`thm_token` plus `Example`).
STATEMENTS = ("Theorem", "Lemma", "Fact", "Remark", "Corollary", "Proposition", "Property",
              "Example")
# Vernacular keywords that bind a top-level constant, inductive, or record.
DECLARATIONS = ("Definition", *STATEMENTS, "Instance", "Fixpoint", "CoFixpoint",
                "Inductive", "CoInductive", "Variant", "Record", "Structure")


def strip_comments(text: str, *, keep_offsets: bool = False) -> str:
    """Replace nested Rocq `(* ... *)` comments with whitespace while preserving strings.

    By default, each top-level comment is replaced by its newline count (or a single space
    if single-line). With `keep_offsets=True`, every non-newline character in a comment is
    replaced with a space so character offsets match `text`.
    """
    blank = _spaces if keep_offsets else _separator
    out: list[str] = []
    start = 0
    for region in prooflex.regions(text, strings_in_comments=True):
        if region.kind == "comment":
            out.append(text[start:region.start])
            out.append(blank(text, region.start, region.end))
            start = region.end
    out.append(text[start:])
    return "".join(out)


def _separator(text: str, start: int, end: int) -> str:
    return "\n" * text.count("\n", start, end) or " "


def _spaces(text: str, start: int, end: int) -> str:
    return "\n".join(" " * len(line) for line in text[start:end].split("\n"))


def sentences(text: str) -> list[str]:
    """Strip comments from `text` and return trimmed Rocq sentences."""
    code = strip_comments(text)
    if '"' not in code:
        return [trimmed for s in SENTENCE_END.split(code) if (trimmed := s.strip())]
    found: list[str] = []
    start = 0
    for end in sentence_ends(code):
        found.append(code[start:end])
        start = end + 1
    found.append(code[start:])
    return [trimmed for s in found if (trimmed := s.strip())]


def sentence_ends(code: str) -> list[int]:
    """Return the character offsets of sentence-terminating `.` tokens in comment-free `code`."""
    if '"' not in code:
        return [end.start() for end in SENTENCE_END.finditer(code)]
    return [token.start() for token in _SENTENCE_TOKEN.finditer(code) if token.group() == "."]


def decorations(code: str, at: int = 0) -> tuple[list[re.Match[str]], int]:
    """Parse leading decorations at `at` in comment-free `code`.

    Bullets, braces, and goal selectors reset prior control flags/attributes so only the
    last bullet and subsequent decorations apply to the following command. Returns
    `(decorations, command_start_offset)`.
    """
    found: list[re.Match[str]] = []
    while (decoration := DECORATION.match(code, at)) is not None:
        if decoration.group("bullet") is not None:
            found.clear()
        found.append(decoration)
        at = decoration.end()
    return found, at


def void_flag(code: str, opened: int, ends: Sequence[int]) -> str | None:
    """Return `'Fail'` or `'Succeed'` if the command at `opened` is governed by a void flag."""
    before = bisect_left(ends, opened)
    start = ends[before - 1] + 1 if before else 0
    blank = _BLANK.match(code, start)
    found, at = decorations(code, blank.end() if blank else start)
    if at < opened:
        return None
    for decoration in found:
        if decoration.group("word") in VOID:
            return str(decoration.group("word"))
    return None


def local_requires(source: Path, stems: set[str]) -> set[str]:
    """Return the subset of `stems` that `source` imports via `Require`."""
    return _requires(sentences(source.read_text(encoding="utf-8")), stems)


def _requires(statements: list[str] | tuple[str, ...], stems: set[str]) -> set[str]:
    named: set[str] = set()
    for sentence in statements:
        found = REQUIRE.fullmatch(sentence)
        if found:
            prefix = found.group(1)
            named.update(f"{prefix}.{name}" if prefix else name
                         for name in found.group(2).split())
    return named & stems


@dataclass(frozen=True)
class SourceIndex:
    """Immutable snapshot of `.v` source texts, sentences, and `Require` dependency waves."""

    texts: Mapping[Path, str]
    statements: Mapping[Path, tuple[str, ...]]
    needs: Mapping[Path, frozenset[Path]]
    ordered: tuple[tuple[Path, ...], ...]
    imports: Mapping[Path, tuple[Path, ...]]

    @classmethod
    def read(cls, sources: list[Path]) -> SourceIndex:
        texts = {source: source.read_text(encoding="utf-8") for source in sources}
        statements = {source: tuple(sentences(text)) for source, text in texts.items()}
        by_stem = {source.stem: source for source in sources}
        stems = set(by_stem)
        needs = {source: frozenset(by_stem[stem] for stem in _requires(parsed, stems))
                 for source, parsed in statements.items()}
        ordered = tuple(tuple(wave) for wave in _waves(
            {source: set(required) for source, required in needs.items()}))
        closures: dict[Path, frozenset[Path]] = {}
        for wave in ordered:
            for source in wave:
                closures[source] = needs[source].union(
                    *(closures[required] for required in needs[source]))
        imports = {source: tuple(sorted(reached, key=lambda path: path.stem))
                   for source, reached in closures.items()}
        return cls(MappingProxyType(texts), MappingProxyType(statements),
                   MappingProxyType(needs), ordered, MappingProxyType(imports))


def marker_depths(text: str, marker: str) -> dict[int, int]:
    """Map each `marker` offset outside string literals to its enclosing comment nesting depth."""
    depth = 0
    found: dict[int, int] = {}
    for token in re.finditer(r'\(\*|\*\)|"(?:[^"]|"")*"', text):
        if token.group() == "(*":
            if text.startswith(marker, token.start()):
                found[token.start()] = depth
            depth += 1
        elif token.group() == "*)":
            depth -= 1
    return found


def _dependencies(sources: list[Path]) -> dict[Path, set[Path]]:
    """Map each file in `sources` to the files in `sources` it `Require`s."""
    by_stem = {source.stem: source for source in sources}
    stems = set(by_stem)
    return {source: {by_stem[stem] for stem in local_requires(source, stems)}
            for source in sources}


def _waves(needs: dict[Path, set[Path]]) -> list[list[Path]]:
    sorter = TopologicalSorter(needs)
    with suppress(CycleError):
        sorter.prepare()
    out: list[list[Path]] = []
    remaining = set(needs)
    while sorter.is_active():
        ready = sorted(sorter.get_ready())
        out.append(ready)
        sorter.done(*ready)
        remaining.difference_update(ready)
    if remaining:
        stuck = ", ".join(source.name for source in sorted(remaining))
        raise SystemExit(f"FAIL: a Require cycle among {stuck}; "
                         f"no compile order satisfies it")
    return out


def waves(sources: list[Path]) -> list[list[Path]]:
    """Return `sources` partitioned into topologically sorted compilation waves."""
    return _waves(_dependencies(sources))


def dependents(sources: list[Path], stem: str) -> list[list[Path]]:
    """Return the compilation waves of `stem` and all files in `sources` that transitively `Require` it."""
    needs = _dependencies(sources)
    reach = {source for source in sources if source.stem == stem}
    out: list[list[Path]] = []
    for wave in _waves(needs):
        affected = [source for source in wave
                    if source in reach or not needs[source].isdisjoint(reach)]
        if affected:
            reach.update(affected)
            out.append(affected)
    return out
