#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read a register entry against the prose it was extracted from, and record it.

The register is normative and the prose is its rationale, and `check.py`'s traces group
already decides that every reference between them resolves. What it cannot decide is
whether the pair still says the same thing: prose under a bookmark can be rewritten
while the entry extracted from it stays as it was, every reference still resolving and
the run still green. K-61 reports each pair where either side has moved since the two
were last read together; this is where the reading is done.

    tools/co-read.py                     # the pairs a reading is owed on
    tools/co-read.py --show R-15-073c    # the two sides, against each other
    tools/co-read.py --bless R-15-073c   # record that they were read and agree
    tools/co-read.py --bless --all       # record every pending pair at once

**Blessing is a judgment and deliberately not a repair.** tools/README.md's convention
is that arithmetic is repaired and judgment is reported, so `check.py --fix` does not
touch this ledger: there is no artifact to recompute a co-read from, and absorbing it
into `--fix` would delete the decision the rule exists to ask for. `--bless --all` is
the one place that decision can be made in bulk, which is what standing the ledger up
in the first place needs; it prints how many pairs it recorded, because a number nobody
sees is a rubber stamp with a ledger behind it.

This is a worklist and not a gate, so it exits 0 whether or not a reading is owed.
`check.py` is the gate.
"""

import argparse
import sys
from pathlib import Path

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import coread
from vos import corpus as corpus_mod
from vos.register import read_register

RULE = "tools/co-read.py"


def _state(root: Path) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]]]:
    """What the pairs hold today, and what the ledger recorded."""
    corpus = corpus_mod.load(root)
    return coread.current(corpus, read_register(corpus)), coread.read_ledger(root)


def _pending(live: dict[str, tuple[str, str]],
             ledger: dict[str, tuple[str, str]]) -> list[tuple[str, str]]:
    """Every pair owed a reading, each with why it is owed."""
    out: list[tuple[str, str]] = []
    for ident, (prose, entry) in live.items():
        was = ledger.get(ident)
        if was is None:
            out.append((ident, "never recorded"))
        elif (prose, entry) != was:
            moved = [side for side, now, before in
                     (("prose", prose, was[0]), ("entry", entry, was[1]))
                     if now != before]
            out.append((ident, " and ".join(moved) + " changed"))
    return out


def _list(root: Path) -> int:
    live, ledger = _state(root)
    pending = _pending(live, ledger)
    stale = [i for i in sorted(ledger) if i not in live]

    if not pending and not stale:
        print(f"every one of the {len(live)} pairs was last read as it now stands.")
        return 0

    if pending:
        print(f"{len(pending)} pair(s) owed a reading:\n")
        for ident, why in pending:
            print(f"  {ident:<12} {why}")
        print(f"\nread one with `python {RULE} --show <id>`, "
              f"then record it with `--bless <id>`.")
    if stale:
        print(f"\n{len(stale)} ledger row(s) naming no live requirement: "
              f"{', '.join(stale)}")
    return 0


def _show(root: Path, ident: str) -> int:
    corpus = corpus_mod.load(root)
    reg = read_register(corpus)
    if ident not in reg.id_set:
        raise SystemExit(f"no requirement '{ident}' in the register")

    prose, entry = coread.pairs(corpus, reg)[ident]
    ledger = coread.read_ledger(root)
    was = ledger.get(ident)
    now = (coread.digest(prose), coread.digest(entry))

    def state(n: int) -> str:
        if was is None:
            return "never recorded"
        return "unchanged" if now[n] == was[n] else "CHANGED since the last reading"

    print(f"=== {ident} ===\n")
    print(f"--- the prose it cites ({state(0)}) ---\n")
    print(prose or "(no prose reaches this entry)")
    print(f"\n--- the entry ({state(1)}) ---\n")
    print(entry)
    print(f"\nrecord the reading with `python {RULE} --bless {ident}`.")
    return 0


def _bless(root: Path, idents: list[str], everything: bool) -> int:
    live, ledger = _state(root)

    if everything:
        idents = [i for i, _ in _pending(live, ledger)]
        if not idents:
            print("nothing pending; the ledger already stands as the pairs do.")
            return 0
    else:
        unknown = [i for i in idents if i not in live]
        if unknown:
            raise SystemExit(f"no requirement in the register: {', '.join(unknown)}")

    # Rebuilt in the register's order rather than appended to, so the file's order is
    # the register's however the blessings arrived, and a stale row for a retired
    # requirement goes out with the rebuild instead of needing its own command.
    blessed = set(idents)
    rows = {i: (live[i] if i in blessed else ledger[i])
            for i in live if i in blessed or i in ledger}
    coread.write_ledger(root, rows)

    print(f"recorded {len(blessed)} co-read(s); the ledger now holds {len(rows)} "
          f"of {len(live)} pairs.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read a register entry against its prose, and record it.")
    parser.add_argument("--show", metavar="ID",
                        help="print one pair's two sides against each other")
    parser.add_argument("--bless", nargs="*", metavar="ID",
                        help="record that these pairs were read and agree")
    parser.add_argument("--all", action="store_true",
                        help="with --bless, record every pending pair")
    args = parser.parse_args(argv)

    root = corpus_mod.find_root()
    if args.show:
        return _show(root, args.show)
    if args.bless is not None:
        if not args.bless and not args.all:
            raise SystemExit("--bless needs an id, or --all to record every pending pair")
        return _bless(root, args.bless, args.all)
    return _list(root)


if __name__ == "__main__":
    sys.exit(main())
