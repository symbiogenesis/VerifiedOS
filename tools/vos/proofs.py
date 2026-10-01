# SPDX-License-Identifier: Apache-2.0
"""What a Rocq source Requires, the order that puts a directory in, and where its
comments end.

Name order is not a dependency order, and a `Require` compiled ahead of its dependency
is satisfied by whatever stale `.vo` a previous run left behind, which is a green run
about a proof nobody rebuilt. [run.py proofs](cli/proofs.py) has always derived the
order rather than assuming it; the parse moved here when [run.py seed](cli/seed.py) needed
the same order for a mutated copy of the same tree, on the convention that a parse two
tools make is written once.

`strip_comments` and `sentences` are here on that same convention and arrived the same
way. They were the proof gate's own, private to [run.py proofs](cli/proofs.py), until
[proofcites.py](proofcites.py) needed the second half of a `.v` the gate already reads: what
the file *defines*, which is a sentence's opening vernacular and so is decided by where
the comments end. Both are lexical and neither knows any Gallina: a comment nests,
separates the tokens beside it and reads a string literal inside it whole, a string
literal outside one is kept whole, and a sentence ends at a full stop outside both, and
that is the whole of what they are for. Nor do they know the tokens a source declares,
which Rocq's lexer reads whole, so the proof gate refuses a declared token they would
read as a string, a comment or a sentence end ([proofaudit.py](proofaudit.py)).

The decoration grammar, what may stand before a command within its sentence, and the
keywords whose sentence states a theorem are here on the same convention. The gate
reads a head after the decorations in its pinned-setting, dynamic-source and witness
readings, and the readers outside it, the apex, memory-plan, mutation, constant-table,
corpus, citation and known-answer readers, each read one too; spelled beside each other
they drifted, one reader missing a form another read, so each composes its anchor,
capture or look-back from the pieces here.
"""

import re
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from types import MappingProxyType

# What a source Requires. `From X Require Import Y` and the bare forms all land here,
# and the names are split on whitespace because one command may Require several.
REQUIRE = re.compile(r"^(?:From\s+(\S+)\s+)?Require(?:\s+(?:Import|Export))?\s+(.+)$")

# A Rocq sentence ends at a full stop followed by whitespace, which is what keeps
# `m.(field)` and `Nat.add` inside their sentence. Rocq's lexer reads `...` as a sentence
# end too, but `..` as a token that ends nothing, so the second of exactly two full stops
# ends nothing here either: a recursive notation's `x .. y` keeps its declaration, and a
# library token ending in `..`, stdpp's telescope binder `∀..` among them, keeps its
# statement. A full stop inside a string literal ends nothing, so the sentence split
# reads each string whole first, an unterminated one to the end as strip_comments reads
# it; a doubled quote inside one is two adjacent strings to this reading and one string
# to Rocq's, which covers the same characters.
SENTENCE_END = re.compile(r"(?<!(?<!\.)\.)\.(?=\s|$)")
_SENTENCE_TOKEN = re.compile(r'"[^"]*(?:"|\Z)|' + SENTENCE_END.pattern)
_COMMENT_TOKEN = re.compile(r'\(\*|\*\)|"')

# Everything that can precede a command within its sentence, each piece with the blank
# after it. Bullets, braces and a focusing goal selector end without a full stop, so the
# sentence split leaves them at the head of the next command, and the pinned Rocq 9.3.0
# accepts a setting, a Timeout or a declaration after them, in effect beyond the proof.
# Then everything Rocq 9.3's vernac_control grammar lets precede a command: control
# flags, quoted attributes and legacy attributes, Program among them, plus the Export
# locality of option commands. Rocq's lexer needs no blank after a word before `#[` or a
# string, nor after a string: the pinned Rocq 9.3.0 compiles `Time#[local]Set` and, once
# its output warning is silenced, `Redirect"out"Load`. So a word prefix ends where its
# word does, and a quoted one where its string does, doubled quotes inside it. An
# attribute's quoted value is read whole, since a bracket inside it closes nothing; an
# unquoted bracket is Rocq's syntax error, and stopping there keeps each read linear.
_QUOTED = r'"(?:[^"]|"")*"\s*'
_ATTRIBUTE_VALUES = r'(?:[^\[\]"]|"[^"]*")*'
BULLETS = r"[-+*{}]\s*|(?:\d+|\[[\w']+\]|!)\s*:\s*\{\s*"
CONTROL_FLAGS = (r"(?:Time|Instructions|Fail|Succeed)(?![\w'])\s*"
                 r"|Profile(?![\w'])\s*(?:" + _QUOTED + r")?|Redirect\s*" + _QUOTED
                 + r"|Timeout\s+\d+\s*|AllocLimit\s+\d+\s*(?:Mw|kw)(?![\w'])\s*")
# An attribute up to its closing bracket, for a reading that looks inside one.
ATTRIBUTE_OPEN = r"#\[" + _ATTRIBUTE_VALUES
LEGACY_ATTRIBUTES = (r"(?:Local|Global|Export|Polymorphic|Monomorphic|Cumulative"
                     r"|NonCumulative|Private|Program)(?![\w'])\s*")
# Any run of them, capturing nothing, for a head pattern to open with. Which of them
# reach the command is `decorations`' to say, since a bullet starts the run again.
CONTROL_PREFIXES = ("(?:" + BULLETS + "|" + CONTROL_FLAGS + "|" + ATTRIBUTE_OPEN + r"\]\s*|"
                    + LEGACY_ATTRIBUTES + ")*")
# One of them, saying which: `bullet` a bullet, brace or goal selector, `word` a control
# flag's or a legacy attribute's word, `attributes` what a quoted attribute holds.
DECORATION = re.compile("(?P<bullet>" + BULLETS + r")|(?=(?P<word>[A-Za-z]+))(?:"
                        + CONTROL_FLAGS + "|" + LEGACY_ATTRIBUTES + r")|#\[(?P<attributes>"
                        + _ATTRIBUTE_VALUES + r")\]\s*")
# The control flags that run their command and keep nothing it states.
VOID = ("Fail", "Succeed")
_BLANK = re.compile(r"\s*")

# The vernaculars whose sentence states a theorem: Rocq 9.3's seven theorem keywords, its
# grammar's `thm_token`, and `Example`, which states and defines.
STATEMENTS = ("Theorem", "Lemma", "Fact", "Remark", "Corollary", "Proposition", "Property",
              "Example")
# The vernaculars whose sentence binds a top-level name a file defines: a definition,
# every statement, an instance, a recursive definition and every inductive type Rocq
# 9.3's `inductive_token` and `finite_token` name but `Class`. It is wider than the
# witness scan's definers (cli/proofs.py), the shape a closed definition typed at a
# record takes, since a record declaration is as much a constant of the file as a lemma.
DECLARATIONS = ("Definition", *STATEMENTS, "Instance", "Fixpoint", "CoFixpoint",
                "Inductive", "CoInductive", "Variant", "Record", "Structure")


def strip_comments(text: str, *, keep_offsets: bool = False) -> str:
    """The source with its comments blanked, where Rocq 9.3's lexer finds them in a source
    declaring no token that holds a quote or a comment opener. Rocq reads such a token
    whole, and the proof gate refuses its declaration (proofaudit.unreadable_tokens).

    Comments nest. A string literal is read whole inside a comment as well as outside
    one, so a `(*` or `*)` quoted in either opens or closes nothing: the lexer reads a
    string in a comment, and the locked compiler under the gate's flags refuses a quoted
    `*)` there outright. A comment is a token separator, so `Set(* c *)Kernel` is two
    words: each complete outer comment becomes its newlines, preserving source line
    numbers, or one space when it holds none. With `keep_offsets` it becomes blank space
    of its own length instead, its line breaks kept, so an offset into the result is one
    into the source, for a reader that reports or cuts at source offsets. The regex engine
    skips ordinary text; Python visits only delimiters.
    """
    blank = _spaces if keep_offsets else _separator
    out: list[str] = []
    depth = start = quoted_until = 0
    for token in _COMMENT_TOKEN.finditer(text):
        if token.start() < quoted_until:
            continue
        if token.group() == '"':
            quoted_until = text.find('"', token.end()) + 1
            if not quoted_until:
                break
        elif token.group() == "(*":
            if not depth:
                out.append(text[start:token.start()])
                start = token.start()
            depth += 1
        elif depth:
            depth -= 1
            if not depth:
                out.append(blank(text, start, token.end()))
                start = token.end()
    out.append(blank(text, start, len(text)) if depth else text[start:])
    return "".join(out)


def _separator(text: str, start: int, end: int) -> str:
    """What one comment leaves behind: its newlines, or one space if it holds none."""
    return "\n" * text.count("\n", start, end) or " "


def _spaces(text: str, start: int, end: int) -> str:
    """What one comment leaves behind at its own offsets: blank space of its length, its
    line breaks kept."""
    return "\n".join(" " * len(line) for line in text[start:end].split("\n"))


def sentences(text: str) -> list[str]:
    """Every sentence the source states, comments gone and whitespace trimmed. Only a
    full stop outside a string literal ends one, so an attribute's quoted note keeps
    its declaration."""
    code = strip_comments(text)
    # Most sources hold no string literal outside their comments, and for them the
    # split in the regex engine is the same reading at a third of the cost.
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
    """Where each sentence of comment-free code ends: the offset of every full stop the
    sentence split ends one at, each string read whole first. Comments blanked to spaces
    of their own length leave the offsets the source's."""
    if '"' not in code:
        return [end.start() for end in SENTENCE_END.finditer(code)]
    return [token.start() for token in _SENTENCE_TOKEN.finditer(code) if token.group() == "."]


def decorations(code: str, at: int = 0) -> tuple[list[re.Match[str]], int]:
    """The decorations standing at `at` in comment-free code that reach the command under
    them, in order, and where that command opens.

    A bullet, a brace or a goal selector is a command of its own in Rocq 9.3's grammar,
    which reads control flags and attributes only before a whole command: the locked
    compiler runs `Fail }` and `Succeed {` as the brace's flag and keeps the declaration
    after it. So the run starts again at each of them, and the last one stands first in
    what is returned, for a reader that asks whether one stood there.
    """
    found: list[re.Match[str]] = []
    while (decoration := DECORATION.match(code, at)) is not None:
        if decoration.group("bullet") is not None:
            found.clear()
        found.append(decoration)
        at = decoration.end()
    return found, at


def void_flag(code: str, opened: int, ends: Sequence[int]) -> str | None:
    """The control flag keeping nothing, `Fail` or `Succeed`, that a command stands under
    in comment-free code, where `opened` is where its line's head opens and `ends` is
    `sentence_ends(code)`.

    A flag may stand on the command's line or on lines of its own above it, so the walk
    starts at the full stop ending the sentence before and reads the decorations from
    there to the command's keyword, a flag before a bullet, a brace or a goal selector
    being that one's (`decorations`). That full stop is found where the sentence split
    finds it, so a string's full stop, an attribute's quoted note among them, ends no
    look-back early. None where there is no such flag, or where something other than
    blank space and decorations stands between that full stop and `opened`, the head then
    opening inside a sentence rather than at one.
    """
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
    """The proofs this source Requires from its own directory, by file stem; what a
    library provides is not this module's to order."""
    return _requires(sentences(source.read_text(encoding="utf-8")), stems)


def _requires(statements: list[str] | tuple[str, ...], stems: set[str]) -> set[str]:
    """Resolve the shared lexical parse against this source set's local names."""
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
    """One immutable source snapshot, with shared parsing and dependency closures.

    This is analysis data, never freshness evidence. A new invocation reads new
    bytes; the proof gate still validates its input and output hashes independently.
    Mapping proxies and immutable values permit workers to share the same snapshot.
    """

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
    """Comment depth before each marker, with quoted strings skipped.

    A discharge is itself a comment, so its opening marker must have depth zero.
    The token walk stays in the regex engine between delimiters rather than walking
    every character in Python. A marker inside a string is absent from the result.
    """
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
    """Read each source once, resolving local names against the supplied directory."""
    by_stem = {source.stem: source for source in sources}
    stems = set(by_stem)
    return {source: {by_stem[stem] for stem in local_requires(source, stems)}
            for source in sources}


def _waves(needs: dict[Path, set[Path]]) -> list[list[Path]]:
    sorter = TopologicalSorter(needs)
    # Drain independent nodes even after a cycle, so the refusal names the same
    # blocked sources as an acyclic prefix would leave, including cycle consumers.
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
    """The sources in dependency order: each wave Requires only what earlier waves
    compiled, and is name-sorted within itself so the order is deterministic."""
    return _waves(_dependencies(sources))


def dependents(sources: list[Path], stem: str) -> list[list[Path]]:
    """One source and every source that reaches it through a `Require`, in that same
    dependency order, with the waves nothing in them dropped.

    What a mutation loop has to recompile, and the argument for why the rest may be
    left alone: a source outside this closure Requires the mutated one nowhere, so
    neither its own text nor any `.vo` it is built against has moved, and compiling it
    again can only reproduce the answer already on disk. The closure therefore holds
    the whole failure set rather than a prefix of it, which is what lets the loop go on
    reporting *which* proofs refused a mutant and not merely that one did.

    A stem no source carries returns nothing, and the caller is the one that decides
    what that means; this function will not guess a closure for a name it cannot find.
    """
    needs = _dependencies(sources)
    reach = {source for source in sources if source.stem == stem}
    out: list[list[Path]] = []
    # Every predecessor is settled before its consumer's wave, so one pass computes
    # the complete closure without reparsing sources or repeatedly scanning the graph.
    for wave in _waves(needs):
        affected = [source for source in wave
                    if source in reach or not needs[source].isdisjoint(reach)]
        if affected:
            reach.update(affected)
            out.append(affected)
    return out
