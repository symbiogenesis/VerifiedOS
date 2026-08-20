"""traces: the register's references against the prose bookmarks they cite.

Bookmarks cannot go stale the way line numbers do, but they can be absent,
misspelled, duplicated or buried, and a dangling Markdown anchor fails silently. The
properties are not hypothetical: they found R-05-022 (no trace) and R-15-159 (a
target inside a mermaid diagram) when the reference first became symbolic. The
mermaid case is why a bookmark inside a fenced block is now a finding on its own:
the fence displays the anchor rather than declaring it, so the trace that cites it
points at nothing while the prose looks like it carries the target. That defect was
repaired by hand once and nothing held it.

The citation itself is now derived rather than written: a trace naming only its
crown jewels cites #r-<id>, the bookmark its own requirement number gives. That
closes the last place the register carried a derived fact by hand, and it is the
counts group's rule applied to a reference instead of a figure, so the third
property below is the one that keeps it closed: a trace written out where the
derived form would do is a restatement, and is reported exactly as an unheld figure.

A written-out target that resolves to nothing at all is a dead link, which the links
group holds over the whole corpus and reports there; reporting it here as well would
book one edit as two findings. What is this group's alone is the target the links
group cannot see as wrong: the derived citation with no bookmark behind it, which is
no link and so reaches no link check, and the written-out citation that lands on a
*heading* rather than a bookmark, which resolves and renders and then moves the next
time the heading is retitled, exactly the drift bookmarks were adopted to end.
"""

import re

from ..corpus import PROSE

HEADING = "=== traces: the register's references against the prose ==="

_TRACE_LINK_RE = re.compile(r"\[§([\d.]+)\]\(spec\.md#([^)]+)\)")
_PROSE_ID_RE = re.compile(r"^r-\d\d-\d", re.IGNORECASE)
_CITATION_SUFFIX_RE = re.compile(r"^(r-\d\d-\d\d\d[a-z]?)-\d+$", re.IGNORECASE)


def run(ctx) -> None:
    rep, reg, corpus = ctx.rep, ctx.reg, ctx.corpus
    rep.line(HEADING)

    spec_targets = corpus.by_name[PROSE].targets
    anchors = corpus.anchor_count

    bad_target: list[str] = []
    wrong_section: list[str] = []
    restated: list[str] = []

    for ident in reg.ids:
        trace = reg.trace_of.get(ident)
        if not trace:
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
            if actual and shown != actual:
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

    # r-ss-nnn, r-ss-nnna (a letter-suffixed requirement) and r-ss-nnn-2 (the nth
    # citation of one requirement) all resolve to the same register id.
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
