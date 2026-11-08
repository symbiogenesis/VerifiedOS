# SPDX-License-Identifier: Apache-2.0
"""traces: check requirement traces, acceptance criteria, and prose bookmarks (K-01..K-09).

Checks that:
- **K-01**: Every requirement trace target resolves to an `<a id="...">` bookmark in
  [docs/spec.md](../../../docs/spec.md) rather than a missing anchor or a section heading.
- **K-02**: Traces that match the default `#r-<id>` bookmark without extra citations or
  notes use the derived form rather than spelling `#r-<id>` out by hand.
- **K-03**: Every `<a id="...">` bookmark in a document is unique.
- **K-04**: No `<a id="...">` bookmark appears inside a fenced code or diagram block.
- **K-05**: Every requirement has a `· Trace:` line.
- **K-06**: Every requirement has at least one `· Accept:` line.
- **K-07**: Every `· Accept:` line precedes any conferral (`· Fail-closed:`,
  `· RoT-fresh:`) or `· Trace:` line in its entry.
- **K-08**: Every `r-*` bookmark in [docs/spec.md](../../../docs/spec.md) names a live
  requirement in [docs/requirements-register.md](../../../docs/requirements-register.md).
- **K-09**: Every written-out `[§n.m](spec.md#...)` trace link displays the top-level
  section where its target bookmark is located.
"""

import re
from typing import TYPE_CHECKING

from vos.corpus import PROSE
from vos.register import REQ_ID_PATTERN

if TYPE_CHECKING:
    from . import Context

HEADING = "=== traces: the register's references against the prose ==="

_TRACE_LINK_RE = re.compile(r"\[§([\d.]+)\]\(spec\.md#([^)]+)\)")
_PROSE_ID_RE = re.compile(r"^r-\d\d-\d", re.IGNORECASE)
_CITATION_SUFFIX_RE = re.compile(rf"^({REQ_ID_PATTERN})-\d+$", re.IGNORECASE)


def run(ctx: Context) -> None:
    rep, reg, corpus = ctx.rep, ctx.reg, ctx.corpus
    rep.line(HEADING)

    spec_targets = corpus.by_name[PROSE].targets
    anchors = corpus.anchor_count

    bad_target: list[str] = []
    wrong_section: list[str] = []
    restated: list[str] = []

    for ident in reg.ids:
        trace = reg.trace_of.get(ident)
        if not bool(trace):
            continue
        derived = "r-" + ident[2:].lower()

        links = _TRACE_LINK_RE.findall(trace) if "[§" in trace else []
        if not links:
            # the derived form: one citation, at the bookmark the id names. '[§'
            # present but not this reference's shape is no citation at all, and is
            # judged the same way.
            if derived not in anchors:
                bad_target.append(f"{ident} derives #{derived}, which is no bookmark in the prose")
            continue

        # written out, so it departs from the derived form and must say how
        for shown_section, anchor in links:
            if anchor not in anchors and anchor in spec_targets:
                bad_target.append(
                    f"{ident} cites #{anchor}, which is a heading in the prose and not a bookmark"
                )
            shown = shown_section.split(".")[0]
            actual = corpus.anchor_sec.get(anchor)
            if bool(actual) and shown != actual:
                wrong_section.append(f"{ident} shows §{shown} for #{anchor}, which sits in §{actual}")

        # a second citation, another requirement's bookmark, or a note after the link
        # are the three departures; anything else written out is the derived citation,
        # spelled by hand
        tail = _TRACE_LINK_RE.sub("", trace)
        if len(links) == 1 and links[0][1] == derived and ";" not in tail:
            restated.append(f"{ident} writes out #{derived}, which its id already derives")

    rep.report("K-01", "trace target(s) that are no bookmark:", bad_target,
               "every trace target is a prose bookmark")
    rep.report("K-02", "trace(s) restating the derived citation:", restated,
               "every trace is derived, or departs from the derived form")
    rep.report("K-03", "bookmark(s) declared more than once in one document",
               corpus.declared_twice, "every bookmark id is unique where it is declared")
    rep.report("K-04", "bookmark(s) buried in a fenced block", corpus.buried,
               "every bookmark is addressable where it is written")
    rep.report("K-05", "requirement(s) with no trace",
               [i for i in reg.ids if i not in reg.trace_of],
               "every requirement carries a trace")

    # An entry with no criterion is an obligation nothing decides, which is the one
    # thing this register is for; an entry whose criteria straddle its conferrals reads
    # as though the lines below the first one were something other than the criterion.
    rep.report("K-06", "requirement(s) with no acceptance criterion:",
               [f"{i} carries no · Accept: line" for i in reg.ids if not reg.accepts[i]],
               "every requirement carries at least one acceptance criterion")
    rep.report("K-07", "requirement(s) whose criteria straddle a conferral or the trace:",
               [f"{i} states a criterion below a line that must follow the criteria"
                for i in dict.fromkeys(reg.late_accept)],
               "every entry states its criteria before its conferrals and its trace")

    # Strip only numeric repeated-citation suffixes: r-ss-nnnza-2 belongs to
    # R-ss-nnnza, which remains distinct from R-ss-nnnz and R-ss-nnn.
    orphans = []
    for ident in anchors:
        if not _PROSE_ID_RE.match(ident):
            continue
        base = _CITATION_SUFFIX_RE.sub(r"\1", ident)
        req = "R" + base[1:]
        if req not in reg.id_set:
            orphans.append(f"#{ident}: no requirement {req} in the register")
    rep.report("K-08", "prose bookmark(s) naming no live requirement", sorted(orphans),
               "every prose r-* bookmark names a live requirement")

    rep.report("K-09", "trace(s) whose display section is wrong", wrong_section,
               "every trace displays the section its bookmark sits in")
    rep.line()
