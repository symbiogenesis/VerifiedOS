# SPDX-License-Identifier: Apache-2.0
"""What a Rocq source Requires, and the order that puts a directory in.

Name order is not a dependency order, and a `Require` compiled ahead of its dependency
is satisfied by whatever stale `.vo` a previous run left behind, which is a green run
about a proof nobody rebuilt. [run.py proofs](cli/proofs.py) has always derived the
order rather than assuming it; the parse moved here when [run.py seed](cli/seed.py) needed
the same order for a mutated copy of the same tree, on the convention that a parse two
tools make is written once.
"""

import re
from pathlib import Path

# What a source Requires. `From X Require Import Y` and the bare forms all land here,
# and the names are split on whitespace because one command may Require several.
REQUIRE = re.compile(r"^\s*(?:From\s+\S+\s+)?Require(?:\s+(?:Import|Export))?\s+([^.]+)\.",
                     re.MULTILINE)


def local_requires(source: Path, stems: set[str]) -> set[str]:
    """The proofs this source Requires from its own directory, by file stem; what a
    library provides is not this module's to order."""
    text = source.read_text(encoding="utf-8")
    named = (name for found in REQUIRE.finditer(text) for name in found.group(1).split())
    return {name for name in named if name in stems}


def waves(sources: list[Path]) -> list[list[Path]]:
    """The sources in dependency order: each wave Requires only what earlier waves
    compiled, and is name-sorted within itself so the order is deterministic."""
    stems = {source.stem for source in sources}
    needs = {source: local_requires(source, stems) for source in sources}
    out: list[list[Path]] = []
    done: set[str] = set()
    remaining = sorted(sources)
    while remaining:
        ready = [source for source in remaining if needs[source] <= done]
        if not ready:
            stuck = ", ".join(source.name for source in remaining)
            raise SystemExit(f"FAIL: a Require cycle among {stuck}; "
                             f"no compile order satisfies it")
        out.append(ready)
        done |= {source.stem for source in ready}
        remaining = [source for source in remaining if source not in ready]
    return out


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
    stems = {source.stem for source in sources}
    needs = {source: local_requires(source, stems) for source in sources}
    reach = {stem}
    while True:
        grown = reach | {source.stem for source in sources if needs[source] & reach}
        if grown == reach:
            break
        reach = grown
    narrowed = ([source for source in wave if source.stem in reach]
                for wave in waves(sources))
    return [wave for wave in narrowed if wave]
