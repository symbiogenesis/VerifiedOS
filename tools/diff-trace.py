#!/usr/bin/env python3
"""Adjudicate two normalized traces and report where they stop agreeing.

M0.6e (e5). The rig's adjudicator: it aligns the curated model's record stream
against the M0.4 oracle's on the first program counter they share, walks both
until they disagree, and reports the length of the agreeing prefix and the two
records that ended it. The Sail model is the reference on every divergence, so
the report names what each side produced rather than declaring one right.

The **agreeing prefix** is the figure to read, not the verdict. Over
`riscv-tests` the two machines part company inside the test prologue for a
reason that is a fact about the corpus rather than about the transplant: the
curated model deletes delegation, so `csrwi medeleg` is an illegal instruction
here and retires on the oracle, and the tests guard exactly that by pointing
`mtvec` at the instruction after the group. Both machines then run the test to
the same result by different routes. A corpus both can execute in lockstep is
what M0.12 versions; until it exists the prefix is the regression, and it must
not shorten.

Exit status is 0 when the compared range agreed to its end, 1 otherwise.
"""

import argparse
import sys


def first_retire_pc(records):
    for r in records:
        if r.startswith("I "):
            return int(r.split()[1], 16)
    return None


def align(records, first_pc):
    """Drop the records before the executor reaches `first_pc`.

    The two executors do not start at the same instruction: the oracle enters
    through a reset-vector ROM at 0x1000 that this platform does not have, so
    the streams are aligned on the first program counter the curated model
    retires rather than on the step number, which counts different things on
    each side.
    """
    for i, r in enumerate(records):
        if r.startswith("I ") and int(r.split()[1], 16) == first_pc:
            return records[i:]
    return []


def compare(curated, oracle):
    """Return (prefix, compared, divergence) over the two aligned streams."""
    compared = min(len(curated), len(oracle))
    for i in range(compared):
        if curated[i] != oracle[i]:
            return i, compared, (curated[i], oracle[i])
    # One stream running out is not a divergence: the two machines halt on
    # different conditions, and a shorter range that agrees to its end is what
    # the corpus is asking about until M0.12 fixes the stopping point too.
    return compared, compared, None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("curated", type=argparse.FileType("r"))
    ap.add_argument("oracle", type=argparse.FileType("r"))
    ap.add_argument("--context", type=int, default=4,
                    help="records of agreement to print before a divergence")
    ap.add_argument("--quiet", action="store_true", help="print only the verdict line")
    args = ap.parse_args()

    curated = [line.rstrip("\n") for line in args.curated if line.strip()]
    oracle = [line.rstrip("\n") for line in args.oracle if line.strip()]

    start = first_retire_pc(curated)
    if start is None:
        print("no retire records in the curated trace", file=sys.stderr)
        return 1
    aligned = align(oracle, start)
    if not aligned:
        print("the oracle never reaches the curated model's first PC 0x%016X" % start,
              file=sys.stderr)
        return 1

    prefix, compared, divergence = compare(curated, aligned)
    verdict = ("prefix %d of %d compared" % (prefix, compared) if divergence
               else "agreed over %d records" % compared)
    print(verdict)

    if divergence and not args.quiet:
        lo = max(0, prefix - args.context)
        print()
        for r in curated[lo:prefix]:
            print("  agreed : %s" % r)
        print("  curated: %s" % divergence[0])
        print("  oracle : %s" % divergence[1])
        print()
        print("  the Sail model is the reference: a divergence is a fault in the")
        print("  transplant unless the oracle is shown to be the one at fault.")

    return 1 if divergence else 0


if __name__ == "__main__":
    sys.exit(main())
