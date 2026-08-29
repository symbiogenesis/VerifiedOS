# SPDX-License-Identifier: Apache-2.0
"""coread: every entry and the prose it cites, last read together as they now stand.

The traces group decides that the register's references *resolve*: the bookmark exists,
it is unique, it is not buried, it names a live requirement, and it is derived rather
than spelled by hand. R-05-151a says in as many words what that leaves open: the check
is one of *reference*, not *fidelity*, and a trace landing on prose that does not
support its requirement is a review-gate finding rather than a tool's.

This group takes the mechanical half of that residue. It cannot decide whether prose
supports an entry, which is a reading. It can decide whether anybody has done the
reading since either side last moved, and that is the half that goes wrong silently:
the prose under a bookmark is rewritten, every reference still resolves, the run stays
green, and the entry extracted from that paragraph now answers a paragraph that is no
longer there. Nothing else in the tool looks at a pair's *contents* at all.

So the ledger records, per requirement, what the two sides held when they were last
read together, and this rule reports each pair where either side has moved since. The
report names which side moved, because that is the difference between *the design
changed and the obligation has not caught up* and *the obligation was sharpened and the
rationale still argues the old one*, and they are different readings to do.

`tools/run.py coread` is where a person does the reading: it prints the two sides against
each other and records the pair once they agree. That is deliberately not `--fix`.
tools/README.md's convention is that arithmetic is repaired and judgment reported, and
a co-read has no artifact to recompute it from; a `--fix` that blessed these pairs
would delete the only decision the rule exists to ask for.

What this cannot decide is whether the reading was any good, which is the residue every
conferral in this tool declares and this one declares too. A blessed pair asserts that
somebody looked, and nothing more.
"""

from typing import TYPE_CHECKING

from vos import coread

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== coread: every entry and its prose, read together as they now stand ==="


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    live = coread.current(ctx.corpus, ctx.reg)
    ledger = coread.read_ledger(ctx.root)
    empty = coread.digest("")

    findings: list[str] = []
    for ident, (prose, entry) in live.items():
        # A pair whose prose side is empty would agree with every other empty one
        # forever, so the rule would read a populated ledger and have stopped deciding
        # anything about these entries. Reported instead, as the absence it is.
        if prose == empty:
            findings.append(
                f"{ident} reaches no prose: its trace resolves, and there is no text "
                f"under the bookmark for the entry to be read against"
            )
            continue

        was = ledger.get(ident)
        if was is None:
            findings.append(
                f"{ident} is in no ledger row: the entry and the prose it cites have "
                f"not been recorded as read together"
            )
            continue

        moved = [side for side, now, before in
                 (("the prose behind it", prose, was[0]), ("the entry", entry, was[1]))
                 if now != before]
        if moved:
            findings.append(
                f"{ident}: {' and '.join(moved)} changed since the pair was last read; "
                f"read the two against each other and record it with "
                f"`python tools/run.py coread --bless {ident}`"
            )

    findings += [
        f"{ident} has a ledger row and is no requirement the register declares; a "
        f"recorded co-read of a retired entry is a reading nothing is owed"
        for ident in sorted(ledger)
        if ident not in live
    ]

    rep.report("K-61", "requirement(s) owed a reading against their prose:", findings,
               f"all {len(live)} entries and the prose they cite were last read "
               f"together as they now stand")
    rep.line()
