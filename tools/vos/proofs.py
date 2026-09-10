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
the comments end. Both are lexical and neither knows any Gallina: a comment nests and a
string literal outside one is kept whole, and that is the whole of what they are for.
"""

import re
from contextlib import suppress
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

# What a source Requires. `From X Require Import Y` and the bare forms all land here,
# and the names are split on whitespace because one command may Require several.
REQUIRE = re.compile(r"^(?:From\s+(\S+)\s+)?Require(?:\s+(?:Import|Export))?\s+(.+)$")

# A Rocq sentence ends at a full stop followed by whitespace, which is what keeps
# `m.(field)` and `Nat.add` inside their sentence.
SENTENCE_END = re.compile(r"\.(?=\s|$)")
_COMMENT_TOKEN = re.compile(r'\(\*|\*\)|"')


def strip_comments(text: str) -> str:
    """The source with its comments blanked. Rocq comments nest, and a string literal
    outside one is kept whole so a `(*` inside it does not open one.

    The regex engine skips ordinary text; Python visits only delimiters. Each complete
    outer comment contributes its newlines in one count, preserving source line numbers.
    """
    out: list[str] = []
    depth = start = quoted_until = 0
    for token in _COMMENT_TOKEN.finditer(text):
        if token.start() < quoted_until:
            continue
        if depth:
            if token.group() == "(*":
                depth += 1
            elif token.group() == "*)":
                depth -= 1
                if not depth:
                    out.append("\n" * text.count("\n", start, token.end()))
                    start = token.end()
        elif token.group() == '"':
            quoted_until = text.find('"', token.end()) + 1
            if not quoted_until:
                break
        elif token.group() == "(*":
            out.append(text[start:token.start()])
            start = token.start()
            depth = 1
    out.append("\n" * text.count("\n", start) if depth else text[start:])
    return "".join(out)


def sentences(text: str) -> list[str]:
    """Every sentence the source states, comments gone and whitespace trimmed."""
    return [trimmed for s in SENTENCE_END.split(strip_comments(text)) if (trimmed := s.strip())]


def local_requires(source: Path, stems: set[str]) -> set[str]:
    """The proofs this source Requires from its own directory, by file stem; what a
    library provides is not this module's to order."""
    text = source.read_text(encoding="utf-8")
    named: set[str] = set()
    for sentence in sentences(text):
        found = REQUIRE.fullmatch(sentence)
        if found:
            prefix = found.group(1)
            named.update(f"{prefix}.{name}" if prefix else name
                         for name in found.group(2).split())
    return named & stems


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
