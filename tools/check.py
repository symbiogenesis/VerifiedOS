#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check every derived fact in this repository against the artifact that owns it.

A derived fact is anything one document holds only because another document already
determined it, or because its own parts already do. Restated by hand it drifts
silently, in whichever direction nobody looked, which is the defect the register's
sweep 2 names. The defect takes several granularities, and they are one mistake, so
they are one tool:

    generated     the emitted file    every generated artifact against its generator and its owner
    ring          the compiled file   the interface artifact against the two owners it is emitted from
    traces        the reference       every bookmark a trace cites, and the section it shows
    coread        the co-currency     every entry against the prose it cites, as last read together
    extraction    the section set     the prose's normative sections against the register's
    names         the vocabulary      every R-, CJ-, A-, B- and P- id used, against its declarer
    links         the pointer         every cross-document link and every §n.m a sentence names
    views         the membership      what a derived view carries, checked in both directions
    confers       the enumeration     every set closed by conferral, and the agenda it misses
    bindings      the instantiation   the apex statement's fields against the view binding them
    keccak        the shared answer   one permutation state, through both transcriptions of it
    counts        the cardinality     every figure any document asserts, against its artifact
    compounds     the synthesis       a statement over rows, against the rows it rests on
    estimates     the arithmetic      every checklist total and share against the item hours
    differential  the twin roster     the corpus manifest against its document, every member assembling
    findings      the index           every finding a completion note counts, against its entry,
                                      and every landed item's one summary line and its link
    costated      the joint statement a fact stated in more than one pair, at each site stating it
    pins          the edition         every upstream pin against the gitlink the index carries

Three further groups check what a file is rather than what it says: for a document,
the shape and the characters, where a fault survives a rendered read because the
render succeeds, and for every tracked file, the license mark its kind owes:

    tables     the shape         every row against the width its header declares
    glyphs     the characters    encoding damage, in every tracked file
    marks      the provenance    every markable file opens with the declared SPDX identifier

Last, the tool checks itself the same way: every check carries a K-nn rule id,
tools/check-rules.md registers each id with its claim and its ground, and the floors
and meta groups hold the reach and the registry in agreement in both directions.

Run with --fix to rewrite the asserted counts, the compounded product, the coverage
matrix's standing column, and the checklist's totals and shares from their artifacts.
Every other finding has no mechanical repair: it is a person's edit, reported not
guessed.

`--through K-nn` stops after the group that decides that rule. A group reads only
what earlier groups computed, so the rule's verdict is the one a whole run reaches;
the mutation selftest uses it because each case needs its own rule's verdict alone.
A stopped run decides nothing about the later groups and says so.

Under the gate's `--summary`, the seconds of each fixed phase before the first group, of
each group and of each generated artifact's row go to the file
[vos/timings.py](vos/timings.py) names, with this process's CPU seconds and, except on
Windows, those of the processes it started and waited for beside them, never into the
printed report.

Exit 0 clean, 1 on any finding. It may be run from anywhere: the repository root is
found from this file, never from the working directory.
"""

import argparse
import io
import re
import sys
from pathlib import Path

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import corpus as corpus_mod
from vos import timings, toolenv

if __name__ == "__main__":
    code = toolenv.bootstrap(corpus_mod.find_root(), ["check", *sys.argv[1:]])
    if code is not None:
        sys.exit(code)

# The clocks' readings on either side of importing every group's module, which a run's
# timings record as its first fixed phase.
_IMPORTING = timings.reading()

from vos.checks import GROUPS, Context  # noqa: E402  (timed by the readings either side)
from vos.register import read_artifacts, read_register  # noqa: E402
from vos.report import Reporter  # noqa: E402

_IMPORTED = timings.reading()


def _utf8_output() -> None:
    """Make redirected output obey the corpus's UTF-8 encoding, on either lane.

    `reconfigure` belongs to `io.TextIOWrapper` and not to the `TextIO` protocol the
    streams are typed as, so the guard is the type checker's, and a stream that is not
    a wrapper (a harness's capture, say) keeps the encoding its owner gave it."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


def run(root: Path, fix: bool = False, through: str | None = None,
        clock: timings.Clock | None = None) -> Reporter:
    """One whole run, as data. The caller decides what to do with the verdict, which
    is what lets the mutation selftest read a run back instead of parsing its
    stdout. `through` stops the run after the group that reports that rule. `clock`
    receives the fixed phases before the first group and each group that ran, by the
    last part of its module's name, and whatever parts a group measures inside itself."""
    measured = clock or timings.Clock()
    with measured.timing("phase", "corpus load"):
        corpus = corpus_mod.load(root)
    with measured.timing("phase", "register read"):
        reg = read_register(corpus)
    with measured.timing("phase", "artifacts read"):
        art = read_artifacts(corpus)
    ctx = Context(root=root, corpus=corpus, reg=reg, art=art, rep=Reporter(), fix=fix,
                  clock=measured)
    decided = re.compile(rf"\s*(?:ok|FAIL) {re.escape(through)}:") if through else None
    skipped = 0
    for index, group in enumerate(GROUPS):
        start = len(ctx.rep.out)
        with measured.timing("group", group.__name__.rpartition(".")[2]):
            group.run(ctx)
        if decided is not None and any(decided.match(line) for line in ctx.rep.out[start:]):
            skipped = len(GROUPS) - index - 1
            break

    if fix:
        for name, text in ctx.fixed.items():
            # newline='' so the repair writes back exactly the bytes it holds, and a
            # CRLF document does not silently become an LF one under a one-token edit
            (root / name).write_text(text, encoding="utf-8", newline="")
        ctx.rep.line(f"rewrote {len(ctx.fixed)} file(s)." if ctx.fixed
                     else "nothing to rewrite.")

    if skipped:
        ctx.rep.line(f"stopped after the group deciding {through}; "
                     f"the {skipped} later group(s) decided nothing.")
    if ctx.rep.findings:
        ctx.rep.line(f"{ctx.rep.findings} finding(s).")
    elif not skipped:
        ctx.rep.line("every derived fact agrees with its artifact.")
    return ctx.rep


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    parser = argparse.ArgumentParser(
        description="Check every derived fact against the artifact that owns it.")
    parser.add_argument("--fix", action="store_true",
                        help="rewrite the figures that are arithmetic over an artifact")
    parser.add_argument("--through", metavar="RULE",
                        help="stop after the group that decides RULE (a K- id)")
    args = parser.parse_args(argv)
    if args.fix and args.through:
        parser.error("--fix repairs the whole run; it cannot stop at one rule's group")

    # The fixed phases' and groups' seconds for the gate's summary, never printed;
    # claimed before any group runs, so nothing a group starts inherits the file.
    record = timings.claim()
    clock = timings.Clock(cpu=True, origin=_IMPORTING.wall)
    clock.span("phase", "imports", _IMPORTING, _IMPORTED)
    report = run(corpus_mod.find_root(), fix=args.fix, through=args.through, clock=clock)
    print("\n".join(report.out))
    timings.write(record, clock.units())
    return 1 if report.findings else 0


if __name__ == "__main__":
    sys.exit(main())
