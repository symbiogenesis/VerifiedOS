#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check every derived fact in this repository against the artifact that owns it.

A derived fact is anything one document holds only because another document already
determined it, or because its own parts already do. Restated by hand it drifts
silently, in whichever direction nobody looked, which is the defect the register's
sweep 2 names. The defect takes several granularities, and they are one mistake, so
they are one tool:

    traces        the reference       every bookmark a trace cites, and the section it shows
    coread        the co-currency     every entry against the prose it cites, as last read together
    extraction    the section set     the prose's normative sections against the register's
    names         the vocabulary      every R-, CJ-, A-, B- and P- id used, against its declarer
    links         the pointer         every cross-document link and every §n.m a sentence names
    views         the membership      what a derived view carries, checked in both directions
    confers       the enumeration     every set closed by conferral, and the agenda it misses
    bindings      the instantiation   the apex statement's fields against the view binding them
    counts        the cardinality     every figure any document asserts, against its artifact
    compounds     the synthesis       a statement over rows, against the rows it rests on
    estimates     the arithmetic      every checklist total and share against the item hours
    differential  the twin roster     the corpus manifest against its document, every member assembling
    banks         the restated grant  the second class's bank count, contract against composition
    costated      the joint statement a fact stated in more than one pair, at each site stating it

Three further groups check what a file is rather than what it says: for a document,
the shape and the characters, where a fault survives a rendered read because the
render succeeds, and for every tracked file, the license mark its kind owes:

    tables     the shape         every row against the width its header declares
    glyphs     the characters    punctuation the house style forbids, and encoding damage
    marks      the provenance    every markable file opens with the declared SPDX identifier

Last, the tool checks itself the same way: every check carries a K-nn rule id,
tools/check-rules.md registers each id with its claim and its ground, and the floors
and meta groups hold the reach and the registry in agreement in both directions.

Run with --fix to rewrite the asserted counts, the compounded product, and the
checklist's totals and shares from their artifacts. Every other finding has no
mechanical repair: it is a person's edit, reported not guessed.

Exit 0 clean, 1 on any finding. It may be run from anywhere: the repository root is
found from this file, never from the working directory.
"""

import argparse
import sys
from pathlib import Path

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import corpus as corpus_mod
from vos.checks import GROUPS, Context
from vos.register import read_artifacts, read_register
from vos.report import Reporter


def run(root: Path, fix: bool = False) -> Reporter:
    """One whole run, as data. The caller decides what to do with the verdict, which
    is what lets the mutation selftest read a run back instead of parsing its
    stdout."""
    corpus = corpus_mod.load(root)
    ctx = Context(
        root=root,
        corpus=corpus,
        reg=read_register(corpus),
        art=read_artifacts(corpus),
        rep=Reporter(),
        fix=fix,
    )
    for group in GROUPS:
        group.run(ctx)

    if fix:
        for name, text in ctx.fixed.items():
            # newline='' so the repair writes back exactly the bytes it holds, and a
            # CRLF document does not silently become an LF one under a one-token edit
            (root / name).write_text(text, encoding="utf-8", newline="")
        ctx.rep.line(f"rewrote {len(ctx.fixed)} file(s)." if ctx.fixed
                     else "nothing to rewrite.")

    if ctx.rep.findings:
        ctx.rep.line(f"{ctx.rep.findings} finding(s).")
    else:
        ctx.rep.line("every derived fact agrees with its artifact.")
    return ctx.rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check every derived fact against the artifact that owns it.")
    parser.add_argument("--fix", action="store_true",
                        help="rewrite the figures that are arithmetic over an artifact")
    args = parser.parse_args(argv)

    report = run(corpus_mod.find_root(), fix=args.fix)
    print("\n".join(report.out))
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
