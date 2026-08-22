#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Answer, before work starts, what an edit re-opens in the apex statement.

    tools/blast-radius.py --field composed_schedulability
    tools/blast-radius.py --artifact proofs/SomeWorkstream.v
    tools/blast-radius.py                    # every field with its consumers

The mechanical facts come from proofs/ApexTheorem.v alone, through the one parse
vos/apex.py holds, which the checker's bindings group also reads, so the answer here
and the checked view in docs/field-bindings.md cannot disagree. The artifact form
reads that view's Instantiated-by column, through the one row parse
vos/fieldbindings.py holds, to find which fields an artifact discharges. The match
contract: a cell equal to `none yet` is the named absence of an artifact and matches
nothing, and any other cell matches only where the queried name equals a whole token
of it, never a bare substring, so a fragment of a longer word is no hit and the
table's empty state cannot read as full coverage.

The honest scope of the answer: a change to what a field *states* re-opens the
definitions that consume it, and nothing else. The downstream trail printed after is
conditional and labelled as such: a re-proved seam re-opens its consumers only if its
conclusion's statement had to change too. And every seam sits under
composition_meta_lemma, the R-18-031(b) linking theorem, which is always the last
thing re-opened and is listed once rather than per line.
"""

import argparse
import re
import sys
from collections import deque
from pathlib import Path

# The tools import `vos` without being installed, so each puts its own directory on
# the path first. Every import below this line is deliberately not at the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import apex, fieldbindings
from vos.corpus import find_root

# What a cell breaks into: the runs left between whitespace and the punctuation a
# markdown link or code span wraps a path in.
_TOKEN_SPLIT_RE = re.compile(r"[\s\[\]()`,]+")


def _seam_conclusions(record: apex.ApexRecord) -> dict[str, str]:
    """A seam's conclusion is the field after its implication arrow, which body order
    makes the last one read; everything else a seam reads is a premise."""
    return {name: fields[-1] for name, fields in record.def_fields.items()
            if name.startswith("seam_")}


def _matches(cell: str, artifact: str) -> bool:
    """Whether an Instantiated-by cell names the artifact.

    A cell equal to `none yet` matches nothing: it is the named absence of an
    artifact, and a substring match over it once reported every field as
    instantiated. Any other cell matches only where the queried name equals a whole
    token of it, so the answer is an identification and never a coincidence of
    letters.
    """
    cell = cell.strip()
    if cell == "none yet":
        return False
    return artifact in _TOKEN_SPLIT_RE.split(cell)


def field_lines(record: apex.ApexRecord, conclusions: dict[str, str],
                field: str) -> list[str]:
    out = [f"field {field}", "  consumed by:"]
    for consumer in record.consumers[field]:
        if consumer in conclusions:
            role = " (its conclusion)" if conclusions[consumer] == field else " (a premise)"
        else:
            role = ""
        out.append(f"    {consumer}{role}")

    # the conditional trail: premise-consuming seams conclude fields with their own
    # consumers, and so on until nothing new is reached
    trail: list[str] = []
    seen = {field}
    queue = deque([field])
    while queue:
        current = queue.popleft()
        for consumer in record.consumers[current]:
            if consumer not in conclusions or conclusions[consumer] == current:
                continue
            concluded = conclusions[consumer]
            if concluded not in seen:
                seen.add(concluded)
                trail.append(f"    {consumer} concludes {concluded}")
                queue.append(concluded)
    if trail:
        out.append("  downstream, only if a re-proved seam's conclusion statement must change:")
        out.extend(trail)
    out.append("  and last, always: composition_meta_lemma, the R-18-031(b) linking theorem")
    return out


def report(root: Path, field: str | None, artifact: str | None) -> tuple[int, list[str]]:
    """One whole run as data, the exit code and the lines to print, so the caller
    decides what to do with the verdict rather than parsing what was printed."""
    out: list[str] = []

    apex_path = root / apex.APEX
    if not apex_path.is_file():
        out.append(f"FAIL: {apex.APEX} is not in the repository")
        return 1, out
    record = apex.read(apex_path)
    conclusions = _seam_conclusions(record)

    if field:
        if field not in record.field_set:
            out.append(f"no Prop field '{field}' in the Vocabulary record; the fields are:")
            out.extend(f"  {f}" for f in record.fields)
            return 1, out
        out.extend(field_lines(record, conclusions, field))
        return 0, out

    if artifact:
        bindings_path = root / fieldbindings.BINDINGS
        if not bindings_path.is_file():
            out.append(f"FAIL: {fieldbindings.BINDINGS} is not in the repository")
            return 1, out
        rows = fieldbindings.rows(bindings_path.read_text(encoding="utf-8"))
        hits = [row.field for row in rows if _matches(row.instantiated_by, artifact)]
        if not hits:
            out.append(f"{fieldbindings.BINDINGS} binds no field to an artifact "
                       f"matching '{artifact}'")
            return 1, out
        drifted = [f for f in hits if f not in record.field_set]
        if drifted:
            out.append(f"FAIL: {fieldbindings.BINDINGS} row(s) naming no Prop field "
                       f"of the record: {', '.join(drifted)}")
            return 1, out
        out.append(f"artifact {artifact} instantiates: {', '.join(hits)}")
        out.append("")
        for f in hits:
            out.extend(field_lines(record, conclusions, f))
            out.append("")
        return 0, out

    out.append("the Vocabulary record's Prop fields and their consumers:")
    out.extend(f"  {f}  <=  {', '.join(record.consumers[f])}" for f in record.fields)
    out.append("query one with --field <name>, or an instantiating artifact with "
               "--artifact <path>")
    return 0, out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="What an edit re-opens in the apex statement.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--field", help="one Prop field of the Vocabulary record")
    group.add_argument("--artifact",
                       help="a proof development, named by a whole token of its "
                            "Instantiated-by cell")
    args = parser.parse_args(argv)

    code, out = report(find_root(), args.field, args.artifact)
    print("\n".join(out))
    return code


if __name__ == "__main__":
    sys.exit(main())
