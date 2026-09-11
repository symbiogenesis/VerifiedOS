# SPDX-License-Identifier: Apache-2.0
"""confers: every enumeration closed by conferral, and the agenda for what it misses.

Three sets here are enumerations of a judgment: the crown-jewel specifications, the
fail-closed refusals, and the state the RoT counter keeps fresh. Each was first
written as a list somebody believed complete on the day they wrote it, which is the
failure R-17-016 was repaired for: a list restated anywhere is a list that silently
stops being the set. The repair was not a better-maintained list but **conferral**,
where membership is asserted by each requirement that has it and collected in exactly
one place, so the two can be checked against each other instead of against a memory.

What conferral closes is the collection's disagreement with the requirements, and
that is all it closes. It cannot decide whether a requirement that *should* confer
does, because *is a crown jewel*, *fails closed* and *needs freshness* are judgments
and no tool holds them. Pretending otherwise would put the defect one level up, in a
checker that certifies a set it cannot see the whole of.

So each set carries a second instrument against that residue, and it is deliberately
a weak one honestly described: the vocabulary of the judgment is over-approximated
across every requirement body, and each entry the vocabulary catches must confer, be
collected, or be dispositioned here by name with a reason. That is lexical and proves
no totality. What it buys is that the totality claim is discharged against an agenda
regenerated on every run rather than against a reading nobody repeats, and it is not
hypothetical: run against the ten-seam fail-closed register it returned the detector
class (R-17-030n), the entropy health test (R-17-030o), the display path (R-17-030p),
and budget admission (R-17-030q), none of which any reading had found.

The crown-jewel side's agenda is the one whose hold is a document rather than a
conferral collection: a candidate is held by conferring the status or by being cited
in an inventory row, since a requirement the inventory names is one the review gate
already reads. Its vocabulary is therefore the vocabulary of **formal discharge**,
and what it reports is a requirement promising a machine-checked artifact that no
row of the inventory carries and no entry confers. The distinction that decides most
of its dispositions is the inventory's own: a crown jewel is a specification, so a
build-time decision procedure over one composition, a workstream that stages an
artifact another entry confers, and a proof over somebody else's specification each
answer the vocabulary without being a member.

The three sets differ in how their collector grows, and that difference is the
register's rather than this file's: R-17-030 and the crown-jewel inventory grow by
addition, a seam or a row written beside the others, and R-10-013 grows by amendment,
because its sentence is a budget over a wearing counter rather than a roll-call. So the
freshness enumeration is the one place a collector gates a conferral, and the rule that
holds it there is the only one here that reads a member's own words rather than an id.

A disposition is a decision, so it is recorded here beside the rule rather than as a
marker in the prose. A marker would tax the vocabulary instead of the judgment, and
an author who has to spend a word to avoid a finding rewords the sentence rather than
making the decision, which is the check defeating its own purpose quietly.
"""

import re
from typing import TYPE_CHECKING, TypedDict

from vos.register import REQ_TOKEN_RE

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== confers: every enumeration closed by conferral, both directions ==="

CJ_VOCAB = re.compile(r"crown.jewel spec", re.IGNORECASE)
_FC_SEAM_RE = re.compile(r"Fail-closed seam \*\*", re.IGNORECASE)
_ROT_ENUM_RE = re.compile(r"R-10-013", re.IGNORECASE)

# The enumeration R-10-013 states, and the state a conferral names before citing it.
# Both are read out of the register rather than listed here, so the rule holds the two
# sides against each other and never either of them against a copy kept in this file.
_ROT_STATES_RE = re.compile(r"that set is enumerated: (.+?), advancing on ")
_ROT_STATE_OF_RE = re.compile(r"^· RoT-fresh: (.+?) \(R-10-013\)")

# Conferral lives in the entry's normative line, never in a criterion: an Accept line
# tests the obligation and states none. But the vocabulary can still appear there, and
# a conferral someone writes only into a criterion would evade both directions without
# this sweep.
CJ_ACCEPT_DISPOSITION = {
    "R-11-015": "references the timing-annotation statement, whose status R-17-041 confers",
    "R-13-009": "references the format-descriptor status R-05-046 confers on every member",
}


class Agenda(TypedDict):
    """One vocabulary sweep and the two ways an entry is held out of it.

    Typed for the reason `views.View` is: written as bare dicts the table read back
    as a union of everything in it, so `re.compile(agenda["vocab"])` was compiling a
    value the checker could only say was a string, a list, or a dict of strings, and
    `held_by_agenda[agenda["name"]]` was a lookup by that same union.
    """

    name: str
    vocab: str
    # the entries that state the set rather than belonging to it
    ruling: list[str]
    # the entries caught by the vocabulary and decided not to belong, each with the
    # reason that decision was taken; the confers group holds every one of them
    # against the register, so a suppression that suppresses nothing is a finding
    disposition: dict[str, str]


AGENDAS: list[Agenda] = [
    Agenda(
        name="fail-closed",
        vocab=(r"fail-stop|fail-closed|fail closed|refuse|refuses|refused|refusal|"
               r"denial of service|permanent DoS"),
        ruling=["R-03-008", "R-03-009", "R-17-030a", "R-17-030l", "R-17-030r", "R-17-030t"],
        disposition={
            "R-03-003": "threat scope, not a refusal: the refusals an EM adversary provokes are composed at R-17-030n",
            "R-05-051c": "a specification-time exclusion: the role is denied to a format when its descriptor is written, and no running unit stops",
            "R-05-118": "an instance of the admission refusal composed at R-17-030e",
            "R-05-125": "the same admission refusal, stated as the contrast with a runtime trap",
            "R-08-008": "a denial priced out structurally, not a refusal the platform performs",
            "R-08-019": "an instance of the budget refusal composed at R-17-030q",
            "R-08-043b": "the revoke-only asymmetry's availability cost, the shape R-08-039 already carries: a compromised submitter subtracts authority the platform then faithfully retires, so nothing refuses; the bound is priced at R-08-043f",
            "R-12-084b": "an instance of the budget admission refusal composed at R-17-030q, taken at the session boundary against the R-15-238c ceiling",
            "R-12-093": "a status vocabulary: its refused arm names the completion a server publishes, the capacity refusal itself conferred at R-12-095",
            "R-12-099": "the teardown half of the ring contract: stale-generation refusal is the R-12-095-conferred discipline seen from restart, and its fail-stop is an instance of the §16 supervision policy",
            "R-13-014": "the policy name for the admission refusal composed at R-17-030e",
            "R-14-010": "a designed non-refusal, kept for the contrast: past the ceiling the browser evicts and the platform does not refuse",
            "R-15-104a": "run-ahead suppression postpones an optional request until architectural demand under its existing checks; no running unit or service stops, and outstanding requests remain timing and drain obligations",
            "R-15-155": "the countermeasure, whose caught-fault path is the refusal composed at R-17-030n",
            "R-15-177a": "an instance of the uncorrectable-ECC fail-stop R-15-179 specifies, composed at R-17-030n",
            "R-15-238b": "a block excluded at specification time under admission test 5; no runtime failure action, nothing stops",
            "R-15-238c": "the ceiling the R-12-084b refusal is taken against, the same budget admission refusal composed at R-17-030q",
            "R-15-238e": "a mechanism excluded at specification time: the path does not exist to be refused at runtime",
            "R-17-013e": "a consent residual: the refusing party is the user on reflection, and the refused mechanisms are declined at specification time; no failure action, nothing stops",
            "R-17-034": "the sharpest instance of the admission refusal composed at R-17-030e",
            "R-17-047": "a tooling choice refused at specification time, with no runtime failure action",
            "R-17-051a": "a first-release service exclusion fixed at specification time; no runtime messaging service stops",
            "R-17-053a": "the residual booking the R-15-238c ceiling and the R-15-238e exclusion; specifies no refusal of its own",
            "R-17-058b": "the residual beyond the R-16-008f fault model behind R-17-030n detectors, not a refusal of its own",
            "R-18-004": "the release roster points at R-17-051a's specification-time messaging exclusion and adds no runtime failure action",
        },
    ),
    Agenda(
        name="RoT-fresh",
        vocab=(r"monotonic counter|monotonic anti-rollback|monotonic attempt counter|"
               r"anti-rollback floor|freshness-protected"),
        ruling=["R-10-013", "R-10-013a"],
        disposition={
            "R-06-005": "enforces the floor R-09-028 confers; places no further state under the counter",
            "R-09-001": "provides the counter; places no state under it",
            "R-09-005": "checks the floor before executing a byte; places no state under it",
            "R-09-008": "provides the counter operations as a functional surface",
            "R-09-013": "a property of the counter, that it is not a clock",
            "R-09-030": "bounds bootability by the floor R-09-028 confers",
            "R-10-011": "the recorded exclusion R-10-013i requires: the mutable volume is deliberately outside the set",
            "R-10-013b": "classifies the state the counter carries; the class it names is placed under the counter by R-10-013c",
            "R-10-013d": "bounds the rate at which R-10-013c may advance the counter; places no state under it",
            "R-10-013f": "names the device fact R-10-011 excludes on; places no state under the counter and changes nothing until R-10-013g is met",
            "R-10-031": "selects a root within the floor; places no state under the counter",
            "R-11-002": "pins a root subject to the floor; places no state under the counter",
            "R-16-008": "the same pinning through the trusted transactor",
        },
    ),
    Agenda(
        name="formal-discharge",
        # The words this register states a machine-checked discharge in. Over-approximating
        # on purpose and demonstrably so: it reaches a residency prohibition, a release
        # manifest, and a declined-alternative essay citing somebody else's prover, none of
        # which discharge anything, and each of those catches is what shows the sweep is
        # not shaped around the answer it returns.
        vocab=(r"machine.checked|mechani[sz]ed|proof obligation|proof[- ]artifacts?|"
               r"formally verified|formal proof|shipped theorem|"
               r"prove[nd] in (?:Coq|Rocq|Gallina|Lean|Isabelle)"),
        # The hygiene gates over the set: each quantifies across every shipped theorem
        # rather than promising one, and R-05-167 says in so many words that the two are
        # preconditions on every claim discharged by a machine-checked theorem.
        ruling=["R-05-163", "R-05-166", "R-05-167"],
        disposition={
            "R-03-004": "the residual enumeration, whose protocol-level member names the upstream analyses R-12-043e curates; the state machines those analyses fix are the rows R-12-043c confers",
            "R-04-006": "nesting authors no artifact: the graph it names is the one R-07-025 fixes at build time, and its criterion tests only that no object class appears",
            "R-05-051a": "a second theorem over the descriptors R-05-046 confers one by one; what it is proved against is the descriptor, and R-05-042's inventory records which descriptors carry it",
            "R-05-080": "locates the residual unsafe rather than stating what is proved of it; the hardware contracts are the specification R-05-082 confers, and this criterion tests an empty set of blocks outside the HAL",
            "R-05-081": "the proof obligation over those same contracts: what it adds is that each primitive is discharged rather than reviewed, the specification the proofs match being R-05-082's",
            "R-06-015d": "its own criterion books CJ-ADMIT-IMPL as a theorem rather than a specification this platform authors, both judgments being fixed elsewhere; the inventory carries specifications and the theorem-target table carries this target",
            "R-07-005": "a build-time decision procedure over one composition, as its criterion states: it decides an instance and establishes no property a specification could be wrong about",
            "R-07-025": "the same build-time decision over one composed topology; the specification a wrong answer would betray is the policy model R-08-028 and R-17-012 confer",
            "R-10-002": "names the prover and the lineage of the four storage layers; each layer's specification is its curated upstream's, and the criterion tests only that no foreign-prover proof enters the trust base",
            "R-10-004": "compares candidate index refinements under R-10-003's existing parametric-index contract; the specifications are the curated upstreams' and the comparison confers no new locally authored specification or completed theorem",
            "R-10-006": "an upstream property consumed as an admission precondition: the proof is RefFS's, and what this entry states is that §11 may not admit a task without it",
            "R-10-007": "the compilation and prover route for those same layers, declining Dafny/Z3 and Rosette as bases; it fixes which artifacts are trusted rather than what any of them says",
            "R-11-006": "the admission proof over one task set, decided per composition against the schedule R-11-017 confers; its Coq artifact is an instance witness and not a specification",
            "R-13-010c": "a residency prohibition: proof artifacts here names bytes kept out of execution SRAM and consumed at admission, not a discharge",
            "R-13-029": "a release-manifest obligation over whatever proofs exist; it names no theorem and its criterion tests presence",
            "R-14-002": "its criterion moves the discharge to the permission encoding R-15-007l fixes, where the machine-checked part is a finite check over 32 codepoints inside the model R-15-005 confers",
            "R-14-004a": "cites a published machine-checked JIT to foreclose a verifiability argument; the artifact is somebody else's and this entry authors nothing against it",
            "R-14-006": "the same graph R-07-025 fixes, read at the intra-app scale, its criterion stating that no new mechanism appears",
            "R-15-011": "proof obligation here names admission test 2's flow-discipline burden, discharged per feature under R-15-010 rather than by a theorem over an artifact",
            "R-15-013": "the clause deciding when a redundant mechanism is admitted; it reads formal verification as a condition on the hedge and confers nothing on the primary",
            "R-15-062": "the adoption entry for fence.t: the flush-set statement and its mechanized classification are the specification R-15-221 confers, and this criterion defers to R-15-186 through R-15-194",
            "R-16-003": "names the mechanism and its owner on the integrity path, as its criterion says; the crash specification is the §10 stack's and its proof is R-18-026's deliverable",
            "R-17-058d": "a reduction over the two axioms already stated, checked beside R-05-004a's theorems against the probing-model statement R-15-053a confers; it selects a countermeasure and fixes no model of its own",
            "R-18-003b": "a §18 workstream: its five day-one deliverables are each stated elsewhere, and a workstream stages what another entry confers",
            "R-18-026": "the workstream staging the storage layers R-10-002 fixes; it orders the proofs and confers no specification of its own",
            "R-18-031": "the workstream staging the apex theorem R-05-156 confers; sub-deliverable (a) authors that statement and this entry orders the work rather than fixing it",
        },
    ),
]


def run(ctx: Context) -> None:
    rep, reg, art = ctx.rep, ctx.reg, ctx.art
    rep.line(HEADING)

    # --- the crown-jewel inventory: rows against the requirements conferring it ------
    #
    # The views group checks that every conferring requirement reaches the inventory,
    # the direction where a row goes missing. This is the other one R-17-016 names, the
    # direction where a row is *added*: a specification the view grants the status and
    # the register never did. Conferral is the whole membership rule, so a row standing
    # behind no conferring requirement is the view legislating, which a derived view
    # may not do. Rows only: the theorem table is targets, not specifications.
    cj_confer = [i for i in reg.ids if CJ_VOCAB.search(reg.body[i])]

    # Each row's citations are read once and asked two questions. K-18 asks whether one
    # of them confers, which is the direction below; the formal-discharge agenda asks
    # whether an entry is among them at all, that being its whole hold, since a
    # requirement the inventory names is one the review gate already reads.
    cj_cited: set[str] = set()
    rowless: list[str] = []
    for row in art.cj_rows:
        tokens = REQ_TOKEN_RE.findall(row)
        cj_cited.update(tokens)
        if not any(c in cj_confer for c in tokens):
            rowless.append(f"row {row.split('|')[1].strip()}: {row.split('|')[2].strip()}")

    rep.report("K-18", "crown-jewel row(s) no requirement confers:", rowless,
               f"every row cites one of the {len(cj_confer)} requirements that confer the status")

    rep.report("K-19", "Accept-line crown-jewel assertion(s) neither conferred nor dispositioned:",
               [f"{i} asserts the status in a criterion and confers on no entry line"
                for i in reg.ids
                if CJ_VOCAB.search(reg.accept_text[i])
                and i not in cj_confer and i not in CJ_ACCEPT_DISPOSITION],
               "every Accept-line use of the status is a conferrer's or dispositioned")

    # --- the fail-closed seam register --------------------------------------------
    #
    # Here the collection is not a separate document but the R-17-030 seam entries,
    # each naming the requirements whose refusal it composes (R-17-030r). Both
    # directions are owed and they fail differently: a conferral no seam collects is a
    # refusal booked correctly in its own section and absent from the composition,
    # which R-03-008 already calls a review-gate finding and nothing enforced until
    # now; a seam collecting no conferral is the register composing a refusal no
    # requirement specifies.
    fc_seams = [i for i in reg.ids if _FC_SEAM_RE.search(reg.body[i])]
    fc_confer = list(reg.confers.get("Fail-closed", {}))
    fc_cited: dict[str, str] = {}
    for seam in fc_seams:
        for token in REQ_TOKEN_RE.findall(reg.body[seam]):
            fc_cited[token] = seam

    rep.report("K-20", "fail-closed conferral(s) no seam collects:",
               [f"{i} confers a refusal no R-17-030 seam names"
                for i in fc_confer if i not in fc_cited],
               f"all {len(fc_confer)} conferred refusals reach the register")

    rep.report("K-21", "fail-closed seam(s) no requirement confers:",
               [f"{s} composes a refusal no requirement confers" for s in fc_seams
                if not any(c in fc_confer for c in REQ_TOKEN_RE.findall(reg.body[s]))],
               f"all {len(fc_seams)} seams stand on a conferred refusal")

    # --- the RoT-fresh enumeration --------------------------------------------------
    #
    # The collection here is one entry's prose enumeration rather than a row or a seam,
    # so the citation and the membership are two readings rather than one: K-22 decides
    # that a conferral names the entry collecting it, and K-73 below decides that the
    # state it names is one that entry carries.
    rot = reg.confers.get("RoT-fresh", {})
    rf_confer = list(rot)
    rep.report("K-22", "RoT-fresh conferral(s) not naming the enumeration:",
               [f"{i} confers freshness without citing R-10-013"
                for i in rf_confer if not _ROT_ENUM_RE.search(rot[i])],
               f"all {len(rf_confer)} conferred states name the enumeration")

    # --- and its states, against the conferrals that name them ----------------------
    #
    # This is the direction R-10-013a states and nothing read. Citation is not
    # membership, so K-22 passes a conferral naming a state R-10-013 does not carry,
    # and the count of conferrals cannot catch one either: the figure is derived, so
    # `--fix` rewrites it as the new member lands and the sentence forbidding the member
    # survives the edit that falsified it. Membership is by the state's own words
    # because that is what both sides are written in, and it is read both ways, a
    # conferral outside the enumeration being counter endurance spent without the budget
    # sentence being reopened and an enumerated state no requirement confers being the
    # collecting entry legislating, which is R-17-016's defect on this register.
    #
    # Fail-closed on the reading itself: an enumeration this rule cannot parse is a
    # finding rather than a comparison quietly made against nothing.
    states: list[str] = []
    disagree: list[str] = []
    enumerated = _ROT_STATES_RE.search(reg.body.get("R-10-013", ""))
    if enumerated is None:
        disagree.append("R-10-013 no longer enumerates its states in a form this rule "
                        "reads")
    else:
        states = [s.removeprefix("and ") for s in enumerated.group(1).split(", ")]
        named: set[str] = set()
        for i in rf_confer:
            state = _ROT_STATE_OF_RE.match(rot[i])
            if state is None:
                disagree.append(f"{i} confers freshness and names no state before the "
                                "entry collecting it")
            elif state.group(1) not in states:
                disagree.append(f"{i} confers freshness on a state R-10-013 does not "
                                "enumerate")
            else:
                named.add(state.group(1))
        disagree += [f"R-10-013 enumerates '{s}' and no requirement confers it"
                     for s in states if s not in named]
    rep.report("K-73", "freshness state(s) the enumeration and its conferrals disagree "
               "on:", disagree,
               f"all {len(states)} states R-10-013 enumerates stand on a conferral, and "
               "every conferral names one")

    # --- the agenda: what the vocabulary catches and the conferral did not -----------
    held_by_agenda = {
        "fail-closed": set(fc_confer) | set(fc_cited) | set(fc_seams),
        "RoT-fresh": set(rf_confer),
        "formal-discharge": set(cj_confer) | cj_cited,
    }
    for agenda in AGENDAS:
        vocab = re.compile(agenda["vocab"], re.IGNORECASE)
        held = held_by_agenda[agenda["name"]] | set(agenda["ruling"]) | set(agenda["disposition"])
        rep.report("K-23", f"{agenda['name']} candidate(s) neither conferred nor dispositioned:",
                   [f"{i} uses the vocabulary of {agenda['name']} and is in no column"
                    for i in reg.ids if vocab.search(reg.body[i]) and i not in held],
                   f"every {agenda['name']} candidate is conferred, collected, or dispositioned")

    # --- the suppressions themselves, against the entries they name -----------------
    #
    # A ruling and a disposition are both decisions not to report an entry, recorded in
    # the tool because the alternative is a marker in the prose that taxes the
    # vocabulary rather than the judgment. They are consulted only when the entry they
    # name is caught, so an entry that is retired, or reworded until the vocabulary no
    # longer reaches it, leaves its suppression standing over nothing: silent,
    # permanent, and counted. The counting is what makes this more than untidiness. The
    # disposition total is a figure the critique states and the counts group holds, so a
    # suppression that suppresses nothing inflates a published claim about how much was
    # actually decided.
    #
    # This is the register's own conferral shape turned on the tool a second time. The
    # meta group holds the rule set against the registry; this holds each rule's
    # carve-outs against the register, so the tables here answer to the documents
    # exactly as the documents answer to each other, and neither drifts unwatched.
    dead: list[str] = []
    for agenda in AGENDAS:
        vocab = re.compile(agenda["vocab"], re.IGNORECASE)
        for i in [*agenda["ruling"], *agenda["disposition"]]:
            if i not in reg.id_set:
                dead.append(f"{i} is held out of the {agenda['name']} agenda and is no live requirement")
            elif not vocab.search(reg.body[i]):
                dead.append(f"{i} is held out of the {agenda['name']} agenda, "
                            "whose vocabulary its entry no longer carries")
    for i in CJ_ACCEPT_DISPOSITION:
        if i not in reg.id_set:
            dead.append(f"{i} is dispositioned for a crown-jewel criterion and is no live requirement")
        elif not CJ_VOCAB.search(reg.accept_text[i]) or i in cj_confer:
            dead.append(f"{i} is dispositioned for a crown-jewel criterion it no longer states")

    dispositions = sum(len(a["disposition"]) for a in AGENDAS)
    rep.report("K-45", "suppression(s) standing over a finding no check would make:", dead,
               f"all {dispositions + len(CJ_ACCEPT_DISPOSITION)} dispositions and every ruling "
               "suppress a live finding")

    # The RoT-fresh agenda's own count, and the critique's claim over it is about that
    # agenda rather than about whichever row sits second. Read by name, so a fourth
    # agenda inserted above it raises here instead of quietly retargeting the claim
    # onto a different set, which `--fix` would then rewrite into a true sentence
    # about the wrong thing.
    by_name = {a["name"]: a for a in AGENDAS}

    ctx.shared.update(
        cj_confer=cj_confer,
        fc_seams=fc_seams,
        fc_confer=fc_confer,
        rf_confer=rf_confer,
        rot_states=len(states),
        dispositions=dispositions,
        rot_cases=len(by_name["RoT-fresh"]["disposition"]),
    )
    rep.line()
