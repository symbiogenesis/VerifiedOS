# SPDX-License-Identifier: Apache-2.0
"""Check [docs/assurance/field-bindings.md](../../../docs/assurance/field-bindings.md) against [proofs/ApexTheorem.v](../../../proofs/ApexTheorem.v) (`K-42`..`K-44`).

[proofs/ApexTheorem.v](../../../proofs/ApexTheorem.v) is `R-18-031(a)`'s coverage
checklist: every side-property a seam consumes or concludes is a `Prop` field of the
`Vocabulary` record, and [docs/assurance/field-bindings.md](../../../docs/assurance/field-bindings.md)
carries one row per `Prop` field with its mechanical consumers, its semantic authoring
artifact, and its instantiating proof development.

- `K-42` checks that the parser in [vos/apex.py](../apex.py) left no unread declaration
  residue and that the table rows in [docs/assurance/field-bindings.md](../../../docs/assurance/field-bindings.md)
  match the record's `Prop` fields in declaration order.
- `K-43` checks that every row's consumer cell matches the consumers parsed from the
  statement in [proofs/ApexTheorem.v](../../../proofs/ApexTheorem.v).
- `K-44` checks that every instantiation cell is either `none yet` or a Markdown link.
"""

import re
from typing import TYPE_CHECKING

from vos import apex, fieldbindings
from vos.fieldbindings import BINDINGS

if TYPE_CHECKING:
    from . import Context

HEADING = "=== bindings: the apex statement's fields against the view that binds them ==="

_LINK_RE = re.compile(r"\]\([^)]+\)")


def run(ctx: Context) -> None:
    rep, corpus = ctx.rep, ctx.corpus
    rep.line(HEADING)

    apex_path = ctx.root / apex.APEX
    missing = []
    if not apex_path.exists():
        missing.append(f"{apex.APEX} is not in the repository")
    if BINDINGS not in corpus:
        missing.append(f"{BINDINGS} is not in the repository")
    if missing:
        rep.report("K-42", "missing artifact(s):", missing)
        ctx.shared.update(apex=None, row_order=[])
        rep.line()
        return

    # Shared parse used by both this check and [vos/cli/blast.py](../cli/blast.py).
    record = apex.read(apex_path)

    # Shared table parse from [vos/fieldbindings.py](../fieldbindings.py).
    raw = corpus.by_name[BINDINGS].raw
    table = fieldbindings.rows(raw)
    by_field = {row.field: row for row in table}
    row_order = [row.field for row in table]

    # Report any unparsed declarations from `ApexTheorem.v` before checking row
    # correspondence so a narrowed parse cannot pass silently.
    problems = list(record.unread)
    problems += [f"the row '{line}' is too narrow to carry the view's cells"
                 for line in fieldbindings.malformed(raw)]
    problems += [f"{f} has no row" for f in record.fields if f not in by_field]
    problems += [f"{f} is no Prop field of the record" for f in row_order
                 if f not in record.field_set]
    if not problems and row_order != record.fields:
        problems.append("the rows are not in the record's declaration order")
    rep.report("K-42", "field row(s) disagreeing with the record:", problems,
               f"the view carries the record's {len(record.fields)} Prop fields, in "
               f"declaration order; the record makes {record.declarations} declarations "
               "and this run read them all")

    wrong = []
    for f in row_order:
        if f not in record.field_set:
            continue
        stated = by_field[f].consumers.replace("`", "")
        computed = ", ".join(sorted(record.consumers[f])) or "none"
        if stated != computed:
            wrong.append(f"{f}: the view says '{stated}', the statement gives '{computed}'")
    rep.report("K-43", "consumer cell(s) disagreeing with the statement:", wrong,
               "every consumer cell restates the statement exactly")

    bad = []
    for f in row_order:
        if f not in record.field_set:
            continue
        cell = by_field[f].instantiated_by
        if cell != "none yet" and not _LINK_RE.search(cell):
            bad.append(f"{f}: '{cell}' is neither 'none yet' nor a link to the "
                       "instantiating artifact")
    rep.report("K-44", "instantiation cell(s) in no readable form:", bad,
               "every instantiation cell is 'none yet' or a link the links group resolves")

    ctx.shared.update(apex=record, row_order=row_order)
    rep.line()
