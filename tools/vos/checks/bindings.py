# SPDX-License-Identifier: Apache-2.0
"""bindings: the apex statement's interface fields against the view that binds them.

proofs/ApexTheorem.v is R-18-031(a)'s coverage checklist: every side-property some
seam consumes or concludes is a Prop field of the Vocabulary record, a proof
workstream lands by instantiating its field, and a field nothing instantiates is an
uncovered obligation with exactly one name. docs/field-bindings.md is the view that
makes the checklist readable and queryable: one row per Prop field, carrying what the
statement does with the field (mechanical, recomputed here from the .v), which
artifact authors its meaning (semantic, hand-authored, the register wins), and which
proof development instantiates it (the burn-down, 'none yet' today).

The mechanical half is derived in the one direction this repository allows: the .v is
the source, the view restates it, and this group fails the restatement that drifts.
The semantic half is deliberately not derivable and is only shape-checked here;
whether a row cites the right authoring artifact is the review gate's question.
"""

import re
from typing import TYPE_CHECKING

from vos import apex, fieldbindings
from vos.fieldbindings import BINDINGS

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
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

    # the record's Prop fields, in declaration order, and what consumes each: one
    # parse, held in vos/apex.py, which blast-radius.py reads too, so the answer this
    # group checks the view against and the answer that tool prints are the same fact
    # rather than two readings of one file
    record = apex.read(apex_path)

    # the table through the one parse blast-radius.py shares (vos/fieldbindings.py),
    # so a truncated row is that parse's finding here rather than a crash in either
    raw = corpus.by_name[BINDINGS].raw
    table = fieldbindings.rows(raw)
    by_field = {row.field: row for row in table}
    row_order = [row.field for row in table]

    problems = [f"the row '{line}' is too narrow to carry the view's cells"
                for line in fieldbindings.malformed(raw)]
    problems += [f"{f} has no row" for f in record.fields if f not in by_field]
    problems += [f"{f} is no Prop field of the record" for f in row_order
                 if f not in record.field_set]
    if not problems and row_order != record.fields:
        problems.append("the rows are not in the record's declaration order")
    rep.report("K-42", "field row(s) disagreeing with the record:", problems,
               f"the view carries the record's {len(record.fields)} Prop fields, "
               "in declaration order")

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
