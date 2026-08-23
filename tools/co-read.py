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
    tools/co-read.py --show --all        # every pending pair's two sides, in one read
    tools/co-read.py --where R-15-073c   # where the two sides live, as file:line
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
from vos.corpus import ANCHOR_RE, PROSE
from vos.register import REGISTER, read_register

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


def _show(root: Path, idents: list[str], everything: bool) -> int:
    corpus = corpus_mod.load(root)
    reg = read_register(corpus)
    pairs = coread.pairs(corpus, reg)
    ledger = coread.read_ledger(root)

    if everything:
        live = {i: (coread.digest(p), coread.digest(e)) for i, (p, e) in pairs.items()}
        idents = [i for i, _ in _pending(live, ledger)]
        if not idents:
            print("nothing pending; the ledger already stands as the pairs do.")
            return 0
    else:
        unknown = [i for i in idents if i not in reg.id_set]
        if unknown:
            raise SystemExit(f"no requirement '{', '.join(unknown)}' in the register")

    for ident in idents:
        prose, entry = pairs[ident]
        was = ledger.get(ident)
        now = (coread.digest(prose), coread.digest(entry))
        state = ["never recorded" if was is None
                 else "unchanged" if now[n] == was[n]
                 else "CHANGED since the last reading" for n in (0, 1)]

        print(f"=== {ident} ===\n")
        print(f"--- the prose it cites ({state[0]}) ---\n")
        print(prose or "(no prose reaches this entry)")
        print(f"\n--- the entry ({state[1]}) ---\n")
        print(entry)
        print()

    if len(idents) == 1:
        print(f"record the reading with `python {RULE} --bless {idents[0]}`.")
    else:
        print(f"record the readings with `python {RULE} --bless {' '.join(idents)}`.")
    return 0


def _where(root: Path, idents: list[str]) -> int:
    """Each pair's sites as file:line, one block per requirement.

    The prose lines are the bookmarks the pairing rule reaches, so what an editor
    opens here is exactly what `--show` digests; the entry line is where the register
    declares the requirement. Presentation only: nothing here decides anything.
    """
    corpus = corpus_mod.load(root)
    reg = read_register(corpus)
    unknown = [i for i in idents if i not in reg.id_set]
    if unknown:
        raise SystemExit(f"no requirement '{', '.join(unknown)}' in the register")

    doc = corpus.by_name[PROSE]
    anchor_at: dict[str, int] = {}
    for m in ANCHOR_RE.finditer(doc.raw):
        i = doc.line_of(m.start())
        if not doc.fenced[i] and m.group(1) not in anchor_at:
            anchor_at[m.group(1)] = i + 1

    regdoc = corpus.by_name[REGISTER]
    entry_at: dict[str, int] = {}
    for i, line in enumerate(regdoc.lines):
        for ident in idents:
            if ident not in entry_at and line.startswith(f"**{ident}** "):
                entry_at[ident] = i + 1

    marks = coread.bookmarks(corpus, reg)
    for ident in idents:
        print(f"{ident}:")
        for mark in marks[ident]:
            if mark in anchor_at:
                print(f"  {PROSE}:{anchor_at[mark]}  #{mark}")
        if ident in entry_at:
            print(f"  {REGISTER}:{entry_at[ident]}")
    return 0


def _bless(root: Path, idents: list[str], everything: bool) -> int:
    live, ledger = _state(root)
    stale = sorted(i for i in ledger if i not in live)

    if everything:
        idents = [i for i, _ in _pending(live, ledger)]
        # A stale row alone still wants the rebuild: with every pair blessed, K-61
        # fails on the row a retired requirement left behind, and this is the one
        # command that purges it.
        if not idents and not stale:
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
    if stale:
        print(f"purged {len(stale)} stale row(s) naming no live requirement: "
              f"{', '.join(stale)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read a register entry against its prose, and record it.")
    parser.add_argument("--show", nargs="*", metavar="ID",
                        help="print these pairs' two sides against each other")
    parser.add_argument("--where", nargs="*", metavar="ID",
                        help="print where each pair's two sides live, as file:line")
    parser.add_argument("--bless", nargs="*", metavar="ID",
                        help="record that these pairs were read and agree")
    parser.add_argument("--all", action="store_true",
                        help="with --show or --bless, cover every pending pair")
    args = parser.parse_args(argv)

    # Each flag names a different act, so a run combining them would have to drop one
    # silently; refusing is the only answer that cannot be misread as the other act.
    acts = [name for name, value in
            (("--show", args.show), ("--where", args.where), ("--bless", args.bless))
            if value is not None]
    if len(acts) > 1:
        raise SystemExit(f"{' and '.join(acts)} are different acts: run one, then the other")
    if args.all and args.show is None and args.bless is None:
        raise SystemExit("--all covers pending pairs and needs --show or --bless")

    root = corpus_mod.find_root()
    if args.show is not None:
        if args.all and args.show:
            raise SystemExit("--show takes explicit ids or --all, not both")
        if not args.all and not [i for i in args.show if i]:
            raise SystemExit("--show needs a requirement id, or --all for every pending pair")
        return _show(root, args.show, args.all)
    if args.where is not None:
        if not [i for i in args.where if i]:
            raise SystemExit("--where needs a requirement id")
        return _where(root, args.where)
    if args.bless is not None:
        if args.all and args.bless:
            raise SystemExit("--bless takes explicit ids or --all, not both")
        if not args.bless and not args.all:
            raise SystemExit("--bless needs an id, or --all to record every pending pair")
        return _bless(root, args.bless, args.all)
    return _list(root)


if __name__ == "__main__":
    sys.exit(main())
