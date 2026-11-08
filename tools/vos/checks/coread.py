# SPDX-License-Identifier: Apache-2.0
"""coread: check that every requirement entry and its cited prose have been co-read (K-61).

While [`traces`](traces.py#run) checks that trace bookmarks resolve, K-61 checks
[vos/coread.py](../coread.py)'s digest ledger (`tools/coread-ledger.tsv`) to ensure that
every live requirement and the prose span under its trace bookmark match the digests
recorded when they were last read together (R-05-151a).

When either side changes, K-61 reports which side moved (`the prose behind it`, `the
entry`, or both). Use `python tools/run.py coread --show <id>` to inspect both sides and
`python tools/run.py coread --bless <id>` to record agreement. K-61 is never repaired by
`--fix`.
"""

from typing import TYPE_CHECKING

from vos import coread

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
