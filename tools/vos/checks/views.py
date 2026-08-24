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

The matrix is the one view whose rows say something a citation check cannot read. A
cell states how a pair is carried in one column and by what in the next, and whether
the cited entry carries what the column claims is a reading. One mode is the exception
and K-74 takes it: R-17-001a fixes the answer for `residual` by naming the section that
books it, so that column's claim has a membership question behind it.
"""

import re
from typing import TYPE_CHECKING, NotRequired, TypedDict

from vos.register import REQ_TOKEN_RE

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== views: what each derived view carries, both directions ==="


class View(TypedDict):
    """One row of `VIEWS`, declared so that the table is read as what it is.

    Written as a `dict` per row this was `dict[str, str | list[str] | bool]`, and
    every read of it came back as that union: `re.compile(v["body"])` was compiling
    a value that might be a list, and nothing objected. A typo in a key was not a
    finding either, it was a view that quietly declared nothing and passed.
    """

    file: str
    governing: str
    secs: NotRequired[list[str]]
    body: NotRequired[str]
    csr_rows: NotRequired[bool]
    targets: NotRequired[bool]
    cells: NotRequired[bool]


# The declared views. The floors group holds every register citation in this table
# against the register, because these are citations living in a .py and so reaching
# no other rule: renumber a subsection and a view's membership silently narrows to
# nothing while the check over it goes on reporting that everything is carried.
VIEWS: list[View] = [
    View(file="docs/isa-profile.md", governing="R-15-001a",
         secs=["15.1", "15.3", "15.4", "15.5", "15.6", "15.7", "15.8",
               "15.9", "15.10", "15.11", "15.12"],
         csr_rows=True),
    View(file="docs/absence-contract.md", governing="R-15-100a", secs=["15.14"]),
    View(file="docs/crown-jewels.md", governing="R-17-016a",
         body=r"crown.jewel spec", targets=True),
    View(file="docs/coverage-matrix.md", governing="R-17-001b", cells=True),
    # the freeze's second act is the one place a requirement defers its own decision
    # to a measurement, so the entries naming that deferral are what the contract must
    # carry: each either puts a choice into the measured act or states the act's
    # gating artifacts
    View(file="docs/freeze-measurement-contract.md", governing="R-15-014a",
         body=r"R-15-014a|the freeze from measurement|re-derived at the freeze"),
    # the welded block size is one parameter four instructions share, so what the
    # constraint document must carry is the entries that decide any of them: the
    # instructions themselves, the granule and codeword they are quantized against,
    # and the two classes the geometry has to satisfy at once
    View(file="docs/block-geometry-constraint.md", governing="R-15-014a",
         body=r"welded CBO block|CBO block of R-15-007q|allocates whole lines|"
              r"one validity tag per|atomic write unit is the ECC codeword"),
    # the bank count is admitted against three quantities and constrained by the
    # schedule wrapped around it, so what the contract must carry is the entry that
    # names the three, the envelope one of them is, the cadence rules the schedule
    # answers to, and the measurement every coefficient waits on
    View(file="docs/bank-count-dse-contract.md", governing="R-15-247p",
         body=r"Bank granularity on the second class|"
              r"Bank discharge and refresh phases are fixed and staggered|"
              r"Retention figures are lower bounds|"
              r"repaired megabit-class macro|"
              r"whole-bound to islands"),
]


# The discharge vocabulary, read from the one sentence of §3 that declares it, and the
# section a residual is booked in. Both are located by pattern, so the sets they yield
# are members of the floors group's enumerations.
_CM_VOCAB_LEAD = "The modes are "
_CM_MODE_RE = re.compile(r"\*\*([a-z][a-z-]*)\*\* where")
_SEC17_RE = re.compile(r"R-17-\d")


def _discharge(lines: list[str], cells: dict[str, str]) -> tuple[list[str], int, list[str]]:
    """The modes the matrix declares, how many cells book a residual, and every cell
    whose mode its own citations do not answer.

    A cell says how the pair is carried and then by what, and nothing held the two
    columns against each other: K-16 asks only that some requirement be cited, so
    `residual` standing over nothing but discharging entries reads exactly like a booked
    remainder. R-17-001a fixes the answer for that one mode, a pair carrying *either a
    requirement that discharges it or a §17 residual that books it*, and which section
    an entry sits in is a membership question. That is the substitution this rule is:
    whether a cited entry carries what the cell claims is a reading no rule reaches, and
    whether a cell claiming §17 books its remainder cites §17 is not.

    Only that direction. A cell citing a §17 entry need not be a residual, because §17
    carries seams and compositions as well as bookings, and `B-06` by `P-5` is one:
    proved and detected over two seam entries, with nothing booked away.

    Fail-closed on the reading rather than on the claim. The mode column is placed
    against the vocabulary its own document declares, so a mode this rule cannot place
    stops the comparison for that cell instead of passing over it as a cell carrying no
    residual, and a matrix declaring no vocabulary this rule can read is one finding
    rather than sixty-three silent passes.
    """
    vocab: list[str] = []
    for line in lines:
        if _CM_VOCAB_LEAD in line:
            vocab = [str(mode) for mode in _CM_MODE_RE.findall(line)]
            break
    if not vocab:
        return [], 0, ["the matrix declares no discharge vocabulary this rule can read, "
                       "so no cell's mode is placed against one"]

    residual = 0
    gaps: list[str] = []
    for pair, row in cells.items():
        cols = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cols) != 5:
            gaps.append(f"{pair} is not the five columns the matrix's header declares, "
                        "so its mode and its citations are not read")
            continue
        modes = [m.strip() for m in cols[3].split("/")]
        stray = [m for m in modes if m not in vocab]
        if stray:
            gaps.append(f"{pair} is discharged {', '.join(stray)}, which the matrix's "
                        "own vocabulary does not declare")
        elif "residual" in modes:
            residual += 1
            if not _SEC17_RE.search(cols[4]):
                gaps.append(f"{pair} declares a residual and cites no §17 entry booking "
                            "it, so what the mode names as booked is booked nowhere")
    return vocab, residual, gaps


def run(ctx: Context) -> None:
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

            modes, residual, unanswered = _discharge(doc.lines, art.cm_cells)
            ctx.shared["cm_modes"] = len(modes)
            ctx.shared["cm_residual"] = residual
            rep.report("K-74", "cell(s) whose mode its own citations do not answer:",
                       unanswered,
                       f"every cell's discharge mode names one of the {len(modes)} the "
                       f"matrix declares, and each of the {residual} booking a residual "
                       "cites the §17 entry that books it", "  ")

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
