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

The mode column says what the construction claims and nothing about whether anything
discharges it yet, and K-95 is the column that does. A cell's requirements each trace
to the crown-jewel targets they constrain, the inventory gives each of those targets
its rows and each row a status, and the cell's standing is that status lifted over the
rows it reaches: `authored` where every one exists, `not authored` where none does,
`partial` between. It is written into the matrix by `--fix` and never by hand, so a
cell reading `proved` over specifications nobody has authored says so in the next
column, in the inventory's own vocabulary rather than in a fourth mode.
"""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NotRequired, TypedDict

from vos import provenance
from vos.register import COVERAGE_MATRIX, REQ_TOKEN_RE, Artifacts, Register, cj_class

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
        if len(cols) != 6:
            gaps.append(f"{pair} is not the six columns the matrix's header declares, "
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


# A matrix row with its standing as the sixth column. The head is the five columns the
# other rules read and the standing is the one this rule writes; a row short of the
# sixth does not match, and is reported rather than widened, because the column is
# the header's to declare and K-38 already holds a row against its header.
_CM_ROW_RE = re.compile(
    r"^(?P<head>\| `B-\d\d` \| `P-\d` \|(?:[^|\r\n]*\|){3}) (?P<standing>[^|\r\n]*?) "
    r"\|(?P<tail>[ \t]*)$")
_CJ_TOKEN_RE = re.compile(r"CJ-[A-Z][A-Z-]*")
# The inventory's two tables, read by the shape each row opens with: a specification
# row by its number, a theorem row by its target, and a theorem's premises by the
# inventory rows its own last column names.
_CJ_SPEC_ROW_RE = re.compile(r"^\| (\d+) \|")
_CJ_THEOREM_ROW_RE = re.compile(r"^\| `(CJ-[A-Z][A-Z-]*)` \|")
_CJ_PREMISE_RE = re.compile(r"\brows? ((?:\d+(?:, )?)+)")
# The inventory's three classes, spelled as its status column spells them.
_STANDING_OF = {"authored": "authored", "partial": "partial", "unauthored": "not authored"}


@dataclass
class Standing:
    """What K-95 decided about the matrix, and what it rewrote."""

    classes: dict[str, int] = field(default_factory=dict)   # standing class -> cells
    rows_reached: int = 0                                     # inventory rows some cell reaches
    premises: int = 0                                         # theorem targets resolved to rows
    gaps: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)
    text: str | None = None                                   # the matrix, rewritten


def _inventory(art: Artifacts) -> tuple[dict[str, list[int]], dict[int, str | None], int]:
    """Every CJ- target's inventory rows, and every row's status class.

    A specification target reaches its rows through the inventory's own target
    column, and a theorem target through the premises its row names, because a theorem
    is proven against a specification and its standing is that specification's. The
    third value is how many theorem targets resolved to any row at all, which is the
    floor under the second reading: `CJ-ADMIT-IMPL` names no inventory row by design,
    so an empty premise set is not a finding per target, and a theorem table this rule
    can no longer read would leave every theorem-only cell reaching nothing.
    """
    rows_of: dict[str, list[int]] = {}
    status: dict[int, str | None] = {}
    for row in art.cj_rows:
        cols = [c.strip() for c in row.strip().strip("|").split("|")]
        m = _CJ_SPEC_ROW_RE.match(row)
        if m is None or len(cols) < 3:
            continue
        number = int(m.group(1))
        status[number] = cj_class(row)
        for target in _CJ_TOKEN_RE.findall(cols[2]):
            rows_of.setdefault(target, []).append(number)

    premises = 0
    for line in art.cj_lines:
        m = _CJ_THEOREM_ROW_RE.match(line)
        if m is None:
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        named = [int(n) for hit in _CJ_PREMISE_RE.findall(cols[-1])
                 for n in re.findall(r"\d+", hit)] if len(cols) >= 3 else []
        if named:
            premises += 1
        rows_of.setdefault(m.group(1), []).extend(n for n in named if n in status)
    return rows_of, status, premises


def _standing(ctx: Context, reg: Register, art: Artifacts) -> Standing:
    """K-95: every cell's standing is the inventory's, and `--fix` writes it.

    The mode column says how the pair is carried and the citations say by what, and
    neither says whether any of it exists: a cell reading `proved` over a theorem whose
    specification is `not authored` in the inventory is a pair discharged by nothing,
    and the matrix had no column in which to say so. This is that column, and it is
    computed rather than authored, because a standing somebody wrote is a claim that
    stops being true the day a row of the inventory moves.

    The reading is a join of three artifacts, each by name: a cell's citations resolve
    to entries, each entry's trace names the targets it constrains, and the inventory
    gives each target its rows and each row a status. What is lifted from a row to a
    cell is the inventory's own vocabulary: a cell whose rows are all authored stands
    `authored`, one whose rows are none of them authored or partial stands
    `not authored`, and everything between stands `partial`. A cell reaching no row is
    a finding rather than a cell with nothing to say, and a cell reaching a row whose
    status is in no class is left to K-25, which already reports that row, and is not
    written from a class this rule cannot place.

    Repaired rather than reported, on the counts group's ground: the value is
    arithmetic over three enumerations the tool already reads, so a person retyping it
    would be copying a derived fact. The shape is not repaired: a row short of the
    sixth column is reported, the column being the header's to declare.
    """
    result = Standing()
    rows_of, status, result.premises = _inventory(art)
    if not status:
        result.gaps.append("the crown-jewel inventory yields no specification row this "
                           "rule can read, so no cell's standing is decided")
        return result

    counts = {"authored": 0, "partial": 0, "unauthored": 0}
    reached_any: set[int] = set()
    lines = ctx.text(COVERAGE_MATRIX).split("\n")
    for i, line in enumerate(lines):
        m = _CM_ROW_RE.match(line)
        if m is None:
            continue
        cols = [c.strip() for c in m.group("head").strip().strip("|").split("|")]
        pair = f"{cols[0].strip('`')} by {cols[1].strip('`')}"
        reached = {n for ident in REQ_TOKEN_RE.findall(cols[4])
                   for target in _CJ_TOKEN_RE.findall(reg.trace_of.get(ident, ""))
                   for n in rows_of.get(target, [])}
        if not reached:
            result.gaps.append(f"{pair} cites requirements constraining no inventory "
                               "row, so its standing is decided by nothing")
            continue
        reached_any |= reached
        classes = {status[n] for n in reached}
        if None in classes:
            # K-25's finding, at the row; a standing lifted over it would be a class
            # this rule invented
            continue
        if classes == {"authored"}:
            cls = "authored"
        elif "authored" not in classes and "partial" not in classes:
            cls = "unauthored"
        else:
            cls = "partial"
        counts[cls] += 1
        want = _STANDING_OF[cls]
        found = m.group("standing")
        if found == want:
            continue
        if ctx.fix:
            lines[i] = f"{m.group('head')} {want} |{m.group('tail')}"
            result.fixed.append(f"fixed: {COVERAGE_MATRIX}: {pair}'s standing "
                                f"{found} -> {want}")
        else:
            result.gaps.append(f"{pair} stands {found}, and the inventory's rows its "
                               f"requirements constrain make it {want}")

    result.classes = counts
    result.rows_reached = len(reached_any)
    if result.fixed:
        result.text = "\n".join(lines)
    return result


ABSENCE_CONTRACT = "docs/absence-contract.md"
_ABSENCE_ID_RE = re.compile(r"\*\*(A-\d+[a-z]?)\*\*")


def _provenance(ctx: Context) -> list[str]:
    """Every absence bound to a build, and every binding the package states.

    The absence contract enumerates structures whose absence is claimed and
    R-15-103 requires the imported-core half of it to be discharged by a state
    enumeration *plus* the synthesis-configuration provenance, "so the absence is
    bound to a build, not to a reading". Nothing owned that second half. A
    parameter set written into a checklist cell is prose: it reads exactly the
    same the day the configuration moves under it, and the cell goes on saying
    which parameters take which absence long after one of them has stopped.

    Three directions, because the record can fail in three different ways and
    each is a different repair. An absence the record does not carry is claimed
    and bound to nothing. A row naming an identifier the contract does not
    declare is a binding for an absence nobody claims, which is the shape a
    renumbering leaves. And a setting the configuration package does not state at
    that value is a record describing a build that is not this one, which is the
    failure the whole instrument exists to prevent and the only one of the three
    that a reader of either file alone cannot see.

    Fail-closed on the reading. An absent record, an absent configuration package
    and a contract this rule can find no identifiers in are each one finding
    rather than a comparison quietly made against nothing.
    """
    record = provenance.read(ctx.root)
    contract = ctx.text(ABSENCE_CONTRACT)
    declared = dict.fromkeys(_ABSENCE_ID_RE.findall(contract))
    ctx.shared["absence_ids"] = len(declared)
    ctx.shared["provenance_rows"] = len(record.rows)

    if not record.present:
        return [f"{provenance.RECORD} is not in the repository, so no absence is "
                "bound to a build and R-15-103's provenance half is discharged by "
                "nothing"]
    if not declared:
        return [f"{ABSENCE_CONTRACT} declares no absence this rule can find, so the "
                "record is held against nothing"]

    stated = dict.fromkeys(provenance.stated_ids(record))
    gaps = [f"{ident} is claimed by the contract and the record binds it to nothing"
            for ident in declared if ident not in stated]
    gaps += [f"{ident} is bound by the record and the contract declares no such "
             "absence" for ident in stated if ident not in declared]
    gaps += [f"{row.subject} states a binding that is neither a setting nor `n/a` "
             "with a ground, so what removes it is not written down"
             for row in record.rows if not row.is_bound]

    config = ctx.root / provenance.CONFIG
    if not config.is_file():
        return [*gaps, f"{provenance.CONFIG} is not in the repository, so no setting "
                       "the record names is held against the build that takes it"]

    text = config.read_text(encoding="utf-8")
    for subject, name, value in record.settings:
        found = provenance.config_values(text, name)
        if found is None:
            gaps.append(f"{subject} binds `{name}`, which {provenance.CONFIG} does "
                        "not state")
        elif found != (int(value),):
            gaps.append(f"{subject} binds `{name} = {value}` and "
                        f"{provenance.CONFIG} states it as "
                        f"{', '.join(str(v) for v in found) or 'no literal'}")
    return gaps


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

            standing = _standing(ctx, reg, art)
            ctx.shared["cm_standing"] = standing.classes
            ctx.shared["cm_standing_rows"] = standing.rows_reached
            ctx.shared["cm_theorem_premises"] = standing.premises
            if standing.text is not None:
                ctx.fixed[COVERAGE_MATRIX] = standing.text
            for line in standing.fixed:
                rep.line(line)
            n = standing.classes
            rep.report("K-95", "cell(s) whose standing is not the inventory's:",
                       standing.gaps,
                       f"every cell stands as the inventory's rows its requirements "
                       f"constrain make it, {n.get('authored', 0)} authored, "
                       f"{n.get('partial', 0)} partial, {n.get('unauthored', 0)} not "
                       f"authored, over the {standing.rows_reached} rows the cells reach",
                       "  ")

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

    # The absence contract is the one view whose discharge has a second half living
    # outside the document corpus: a configuration that takes each absence in a
    # build. The record binding the two is held here rather than in a group of its
    # own, because what it is held against is this view's own enumeration.
    gaps = _provenance(ctx)
    rep.report("K-76", "absence(s) bound to nothing, or bound to a build that is "
               "not this one:", gaps,
               f"all {ctx.shared.get('absence_ids', 0)} absences the contract "
               f"enumerates are bound by the provenance record's "
               f"{ctx.shared.get('provenance_rows', 0)} rows, and every setting "
               "they name is the one the configuration package states")
    rep.line()
