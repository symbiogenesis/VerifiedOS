#!/usr/bin/env python3
"""Answer, before work starts, what an edit re-opens in the apex statement.

    tools/blast-radius.py --field composed_schedulability
    tools/blast-radius.py --artifact proofs/SomeWorkstream.v
    tools/blast-radius.py                    # every field with its consumers

The mechanical facts come from proofs/ApexTheorem.v alone, through the one parse
vos/apex.py holds, which the checker's bindings group also reads, so the answer here
and the checked view in docs/field-bindings.md cannot disagree. The artifact form
reads that view's Instantiated-by column to find which fields an artifact discharges.

The honest scope of the answer: a change to what a field *states* re-opens the
definitions that consume it, and nothing else. The downstream trail printed after is
conditional and labelled as such: a re-proved seam re-opens its consumers only if its
conclusion's statement had to change too. And every seam sits under
composition_meta_lemma, the R-18-031(b) linking theorem, which is always the last
thing re-opened and is listed once rather than per line.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import apex                          # noqa: E402
from vos.corpus import find_root              # noqa: E402

BINDINGS = "docs/field-bindings.md"
_ROW_RE = re.compile(r"^\| ``?(\w+)``? \|")


def _seam_conclusions(record: apex.ApexRecord) -> dict[str, str]:
    """A seam's conclusion is the field after its implication arrow, which body order
    makes the last one read; everything else a seam reads is a premise."""
    return {name: fields[-1] for name, fields in record.def_fields.items()
            if name.startswith("seam_")}


def show_field(record: apex.ApexRecord, conclusions: dict[str, str], field: str) -> None:
    print(f"field {field}")
    print("  consumed by:")
    for consumer in record.consumers[field]:
        if consumer in conclusions:
            role = " (its conclusion)" if conclusions[consumer] == field else " (a premise)"
        else:
            role = ""
        print(f"    {consumer}{role}")

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
        print("  downstream, only if a re-proved seam's conclusion statement must change:")
        for line in trail:
            print(line)
    print("  and last, always: composition_meta_lemma, the R-18-031(b) linking theorem")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="What an edit re-opens in the apex statement.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--field", help="one Prop field of the Vocabulary record")
    group.add_argument("--artifact", help="a proof development, by path or fragment of one")
    args = parser.parse_args(argv)

    root = find_root()
    record = apex.read(root / apex.APEX)
    conclusions = _seam_conclusions(record)

    if args.field:
        if args.field not in record.field_set:
            print(f"no Prop field '{args.field}' in the Vocabulary record; the fields are:")
            for f in record.fields:
                print(f"  {f}")
            return 1
        show_field(record, conclusions, args.field)
        return 0

    if args.artifact:
        hits = []
        for line in (root / BINDINGS).read_text(encoding="utf-8").splitlines():
            m = _ROW_RE.match(line)
            if m and args.artifact in line.split("|")[4]:
                hits.append(m.group(1))
        if not hits:
            print(f"{BINDINGS} binds no field to an artifact matching '{args.artifact}'")
            return 1
        print(f"artifact {args.artifact} instantiates: {', '.join(hits)}")
        print()
        for field in hits:
            show_field(record, conclusions, field)
            print()
        return 0

    print("the Vocabulary record's Prop fields and their consumers:")
    for field in record.fields:
        print(f"  {field}  <=  {', '.join(record.consumers[field])}")
    print("query one with --field <name>, or an instantiating artifact with --artifact <path>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
