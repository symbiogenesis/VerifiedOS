"""floors: the tool's own reach, against the possibility that it is reading nothing.

Every other group decides a property of a set the tool reads out of a document. The
failure none of them can see is the empty set: an anchor that stops matching yields no
members, the property holds over no members, and the run reports the rule green with a
sentence that is true and vacuous. That is not hypothetical and it is not cheap,
because a rule in that state looks exactly like a rule that is working, and the review
gate prices it as one.

Three floors close it, they answer to three different readings, and so they are three
rules rather than one: a registry row is what the review gate prices the tool by, and
a row whose claim is a conjunction of three prices none of them.

The first is nearly free because the design already almost has it. A quantity the
counts group computes is compared against what the documents say, so an anchor that
breaks drives the count to zero and the prose disagrees with it loudly: being
*claimed* is what makes a quantity self-checking. So every quantity is required to be
claimed, and the counts group becomes total rather than a habit.

The second covers what is read and never counted. There is no prose to disagree with
such a set, so the floor is stated here directly: it has members, or the reading that
produced it has moved and this says so.

The third covers the references the tool makes by hand. A view declares the register
subsections it draws its members from, the pattern that selects them where there is no
subsection to name, and the requirement that governs it. Those are citations of the
register living in a `.py`, so the names group never sees them: renumber a subsection
and the view's membership silently narrows to nothing while the check that reads it
goes on reporting that every bearing requirement is carried. A citation the register
no longer answers is the finding, in whichever of the three forms it takes.

No floor decides that the members are the right ones, and none of them sees a reading
that narrows without emptying: a vocabulary that loses one term still catches the rest
and still reports green over them. That residue is named in tools/check-rules.md and
is the same one every enumeration above declares.
"""

import re

HEADING = "=== floors: every enumeration this tool reads has members ==="


def run(ctx) -> None:
    rep, reg, art, sh = ctx.rep, ctx.reg, ctx.art, ctx.shared
    rep.line(HEADING)

    claimed = {quantity for _, quantity, _, _ in ctx.claims}
    rep.report("K-46", "computed quantity(ies) no claim holds:",
               [f"{q} is computed and no document is required to state it, so nothing "
                "notices when it goes to zero" for q in ctx.q if q not in claimed],
               f"all {len(ctx.q)} computed quantities are held by a claim")

    # the sets no figure counts, each named by what it is rather than where it is read,
    # so a floor that fails says which reading has moved
    floors = {
        "prose bookmarks": len(ctx.corpus.anchor_count),
        "CSR rows the profile presents": len(art.csr_rows.get("5.1", [])),
        "CSR rows the profile excludes": len(art.csr_rows.get("5.2", [])),
        "Prop fields of the apex record": len(sh["apex"].fields) if sh.get("apex") else 0,
        "rows of the field-bindings view": len(sh.get("row_order", [])),
        "checklist items": len(sh.get("items", [])),
        "checklist subtotals": len(sh.get("sections", [])),
        "dominant terms read from the big table": len(sh.get("ends", [])),
    }
    ctx.floors = floors
    rep.report("K-47", "enumeration(s) the tool reads and finds empty:",
               [f"the tool finds no {name}; whatever it reads them from has moved"
                for name, size in floors.items() if not size],
               f"all {len(floors)} uncounted enumerations have members")

    # the register citations the view table carries, which live in a .py and so reach
    # neither the names group nor the links group
    populated = {sub for sub in reg.subsection.values() if sub}
    cited = 0
    unanswered: list[str] = []
    for view in ctx.views:
        cited += 1
        if view["governing"] not in reg.id_set:
            unanswered.append(f"{view['file']} is governed by {view['governing']}, "
                              "which the register does not declare")
        for sub in view.get("secs", []):
            cited += 1
            if sub not in populated:
                unanswered.append(f"{view['file']} draws its members from §{sub}, "
                                  "where the register carries no entries")
        if view.get("body"):
            cited += 1
            pattern = re.compile(view["body"], re.IGNORECASE)
            if not any(pattern.search(body) for body in reg.body.values()):
                unanswered.append(f"{view['file']} selects its members with a pattern "
                                  "no register entry matches")
    rep.report("K-48", "view citation(s) the register no longer answers:", unanswered,
               f"all {cited} register citations in the view table resolve")
    rep.line()
