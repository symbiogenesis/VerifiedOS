# SPDX-License-Identifier: Apache-2.0
"""views: what each derived view carries, in both directions.

A derived view restates requirements that live in the register. That is the shape
which produced D-03 and D-10, the same set stated twice with different membership.
The reverse direction is the one that earns its keep: on first run it found eight
omissions in isa-profile.md, five of them the §15.12 timing contracts.

A view declares what it must carry, either by owning §15 subsections (`secs`) or by a
pattern matched against requirement bodies anywhere in the register (`body`). That
every id a view cites resolves is the names group's business, not this one's: a view
is not a special case of the vocabulary, it is the only place membership is also owed
in the other direction.
"""

import re

from ..register import REQ_TOKEN_RE

HEADING = "=== views: what each derived view carries, both directions ==="

# The declared views. The floors group holds every register citation in this table
# against the register, because these are citations living in a .py and so reaching
# no other rule: renumber a subsection and a view's membership silently narrows to
# nothing while the check over it goes on reporting that everything is carried.
VIEWS = [
    dict(file="docs/isa-profile.md", governing="R-15-001a",
         secs=["15.1", "15.3", "15.4", "15.5", "15.6", "15.7", "15.8",
               "15.9", "15.10", "15.11", "15.12"],
         csr_rows=True),
    dict(file="docs/absence-contract.md", governing="R-15-100a", secs=["15.14"]),
    dict(file="docs/crown-jewels.md", governing="R-17-016a",
         body=r"crown.jewel spec", targets=True),
    dict(file="docs/coverage-matrix.md", governing="R-17-001b", cells=True),
    # the freeze's second act is the one place a requirement defers its own decision
    # to a measurement, so the entries naming that deferral are what the contract must
    # carry: each either puts a choice into the measured act or states the act's
    # gating artifacts
    dict(file="docs/freeze-measurement-contract.md", governing="R-15-014a",
         body=r"R-15-014a|the freeze from measurement|re-derived at the freeze"),
]


def run(ctx) -> None:
    rep, reg, art, corpus = ctx.rep, ctx.reg, ctx.art, ctx.corpus
    ctx.views = VIEWS
    rep.line(HEADING)

    # A view that is not there and a view that is there and short of a member fail
    # differently and are repaired differently, so they are two rules: the first is
    # whether the artifact a requirement obliges exists at all, and it is decided once
    # over the whole table rather than once per view.
    rep.report("K-49", "declared view(s) not in the repository:",
               [f"{v['file']}, which {v['governing']} requires, is not in the repository"
                for v in VIEWS if v["file"] not in corpus],
               f"all {len(VIEWS)} views the register obliges exist")

    for view in VIEWS:
        rep.line(f"{view['file']} (per {view['governing']})")
        doc = corpus.get(view["file"])
        if doc is None:
            continue

        cited = set(REQ_TOKEN_RE.findall(doc.raw))

        # a view declares what it must carry either by owning subsections or by a
        # pattern over the entry bodies; which of the two it is changes only where the
        # members come from, so the membership test itself is stated once
        if view.get("secs") or view.get("body"):
            if view.get("secs"):
                bearing = [i for i in reg.ids if reg.subsection.get(i) in view["secs"]]
            else:
                pattern = re.compile(view["body"], re.IGNORECASE)
                bearing = [i for i in reg.ids if pattern.search(reg.body[i])]
            rep.report("K-14", "bearing requirement(s) not carried:",
                       sorted(i for i in bearing if i not in cited),
                       f"all {len(bearing)} bearing requirements are carried", "  ")

        # a matrix view is bearing over a product rather than a subsection: what it
        # must carry is every pair of its own two enumerations, each resting on a
        # requirement
        if view.get("cells"):
            expected = [f"{b} by {p}" for b in art.cm_bounds for p in art.cm_props]
            gaps = [f"{pair} has no cell" for pair in expected if pair not in art.cm_cells]
            gaps += [f"{pair} names no enumerated boundary or property"
                     for pair in art.cm_cells if pair not in expected]
            gaps += art.cm_twice
            rep.report("K-15", "uncovered or unaccounted cell(s):", gaps,
                       f"all {len(art.cm_bounds)} by {len(art.cm_props)} cells present, exactly once",
                       "  ")
            rep.report("K-16", "cell(s) resting on no requirement:",
                       [pair for pair, row in art.cm_cells.items()
                        if not REQ_TOKEN_RE.search(row)],
                       "every cell cites a requirement", "  ")

        # the profile's CSR bank is the one table in a derived view whose rows are
        # decided one at a time rather than carried wholesale from a subsection, so
        # each row owes the requirement that admits or excludes it, as a cell does
        if view.get("csr_rows"):
            uncited = [f"§{sec}: {row.split('|')[1].strip()} cites no requirement"
                       for sec, rows in art.csr_rows.items() for row in rows
                       if not REQ_TOKEN_RE.search(row)]
            total = sum(len(rows) for rows in art.csr_rows.values())
            rep.report("K-29", "CSR row(s) resting on no requirement:", uncited,
                       f"all {total} rows of the CSR bank cite a governing requirement", "  ")

        # a view standing in for the CJ- vocabulary must account for every target
        if view.get("targets"):
            lowered = doc.raw.lower()
            rep.report("K-17", "CJ- target(s) unaccounted for:",
                       [t for t in reg.cj_targets if t.lower() not in lowered],
                       f"all {len(reg.cj_targets)} CJ- targets accounted for", "  ")
    rep.line()
