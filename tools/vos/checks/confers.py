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

A disposition is a decision, so it is recorded here beside the rule rather than as a
marker in the prose. A marker would tax the vocabulary instead of the judgment, and
an author who has to spend a word to avoid a finding rewords the sentence rather than
making the decision, which is the check defeating its own purpose quietly.
"""

import re

from ..register import REQ_TOKEN_RE

HEADING = "=== confers: every enumeration closed by conferral, both directions ==="

CJ_VOCAB = re.compile(r"crown.jewel spec", re.IGNORECASE)
_FC_SEAM_RE = re.compile(r"Fail-closed seam \*\*", re.IGNORECASE)
_ROT_ENUM_RE = re.compile(r"R-10-013", re.IGNORECASE)

# Conferral lives in the entry's normative line, never in a criterion: an Accept line
# tests the obligation and states none. But the vocabulary can still appear there, and
# a conferral someone writes only into a criterion would evade both directions without
# this sweep.
CJ_ACCEPT_DISPOSITION = {
    "R-11-015": "references the timing-annotation statement, whose status R-17-041 confers",
    "R-13-009": "references the format-descriptor status R-05-046 confers on every member",
}

AGENDAS = [
    dict(
        name="fail-closed",
        vocab=(r"fail-stop|fail-closed|fail closed|refuse|refuses|refused|refusal|"
               r"denial of service|permanent DoS"),
        # the entries that state the set rather than belonging to it
        ruling=["R-03-008", "R-03-009", "R-17-030a", "R-17-030l", "R-17-030r", "R-17-030t"],
        disposition={
            "R-03-003": "threat scope, not a refusal: the refusals an EM adversary provokes are composed at R-17-030n",
            "R-05-051c": "a specification-time exclusion: the role is denied to a format when its descriptor is written, and no running unit stops",
            "R-05-118": "an instance of the admission refusal composed at R-17-030e",
            "R-05-125": "the same admission refusal, stated as the contrast with a runtime trap",
            "R-08-008": "a denial priced out structurally, not a refusal the platform performs",
            "R-08-019": "an instance of the budget refusal composed at R-17-030q",
            "R-12-084b": "an instance of the budget admission refusal composed at R-17-030q, taken at the session boundary against the R-15-238c ceiling",
            "R-12-093": "a status vocabulary: its refused arm names the completion a server publishes, the capacity refusal itself conferred at R-12-095",
            "R-12-099": "the teardown half of the ring contract: stale-generation refusal is the R-12-095-conferred discipline seen from restart, and its fail-stop is an instance of the §16 supervision policy",
            "R-13-014": "the policy name for the admission refusal composed at R-17-030e",
            "R-14-010": "a designed non-refusal, kept for the contrast: past the ceiling the browser evicts and the platform does not refuse",
            "R-15-155": "the countermeasure, whose caught-fault path is the refusal composed at R-17-030n",
            "R-15-177a": "an instance of the uncorrectable-ECC fail-stop R-15-179 specifies, composed at R-17-030n",
            "R-15-238b": "a block excluded at specification time under admission test 5; no runtime failure action, nothing stops",
            "R-15-238c": "the ceiling the R-12-084b refusal is taken against, the same budget admission refusal composed at R-17-030q",
            "R-15-238e": "a mechanism excluded at specification time: the path does not exist to be refused at runtime",
            "R-17-013e": "a consent residual: the refusing party is the user on reflection, and the refused mechanisms are declined at specification time; no failure action, nothing stops",
            "R-17-034": "the sharpest instance of the admission refusal composed at R-17-030e",
            "R-17-047": "a tooling choice refused at specification time, with no runtime failure action",
            "R-17-053a": "the residual booking the R-15-238c ceiling and the R-15-238e exclusion; specifies no refusal of its own",
            "R-17-058b": "the residual beyond the R-16-008f fault model behind R-17-030n detectors, not a refusal of its own",
        },
    ),
    dict(
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
]


def run(ctx) -> None:
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
    rep.report("K-18", "crown-jewel row(s) no requirement confers:",
               [f"row {row.split('|')[1].strip()}: {row.split('|')[2].strip()}"
                for row in art.cj_rows
                if not any(c in cj_confer for c in REQ_TOKEN_RE.findall(row))],
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
    # so only the outbound direction is symbolic: every conferral names R-10-013. The
    # inbound direction is the count claim in the counts group, which fails when a
    # conferral is added and the enumeration it must join is not amended.
    rot = reg.confers.get("RoT-fresh", {})
    rf_confer = list(rot)
    rep.report("K-22", "RoT-fresh conferral(s) not naming the enumeration:",
               [f"{i} confers freshness without citing R-10-013"
                for i in rf_confer if not _ROT_ENUM_RE.search(rot[i])],
               f"all {len(rf_confer)} conferred states name the enumeration")

    # --- the agenda: what the vocabulary catches and the conferral did not -----------
    held_by_agenda = {
        "fail-closed": set(fc_confer) | set(fc_cited) | set(fc_seams),
        "RoT-fresh": set(rf_confer),
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

    ctx.shared.update(
        cj_confer=cj_confer,
        fc_seams=fc_seams,
        fc_confer=fc_confer,
        rf_confer=rf_confer,
        dispositions=dispositions,
        rot_cases=len(AGENDAS[1]["disposition"]),
    )
    rep.line()
