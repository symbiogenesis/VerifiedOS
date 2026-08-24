# SPDX-License-Identifier: Apache-2.0
"""floors: the tool's own reach, against the possibility that it is reading nothing.

Every other group decides a property of a set the tool reads out of a document. The
failure none of them can see is the empty set: an anchor that stops matching yields no
members, the property holds over no members, and the run reports the rule green with a
sentence that is true and vacuous. That is not hypothetical and it is not cheap,
because a rule in that state looks exactly like a rule that is working, and the review
gate prices it as one.

Four floors close it, they answer to four different readings, and so they are four
rules rather than one: a registry row is what the review gate prices the tool by, and
a row whose claim is a conjunction of four prices none of them.

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

The fourth is a floor under a figure rather than under a set, and it exists because
the two-class memory plan is the one place where a quantity the tool would like to
compare does not exist yet. The per-class capacity budgets are stated, each owned by
one entry, so the floor under them is the ordinary one: the owner still says it. The
per-class bank count is stated and decided by nothing, which is a different state and
the reason the floor under it is a different instrument. A count is written: the
composition declares one and `vos/banks.py` reads it, the exploration contract holds
that declaration inside a candidate set and admits no candidate, and both disclaim
the figure on their own face while the class's `qualified` flag is false. What is
open is the *frozen* count, item (viii) of R-15-014a's closed delta, and a figure
quoted ahead of the act that decides it is a decision taken by nobody. So the floor
under that one is the booking rather than the figure, three artifacts booking it
open, and it is the reading whose moving is the signal.

M0.17 has landed and supplied no figure to compare against, which is that item's own
result rather than a shortfall in it. Its search admits no candidate because every
coefficient R-15-247p names is pending; the count itself arrives with R5's macro
evidence at the freeze's second act rather than out of the search; and the island
bandwidth ceiling is an *output* of the count under search, times a per-bank width
M0.8 owes and a TDM slot share M1 owes, which R-15-228a forbids the memory plan from
producing. Until those land the comparison has no operands, and inventing them would
be worse than not making it.

No floor decides that the members are the right ones, and none of them sees a reading
that narrows without emptying: a vocabulary that loses one term still catches the rest
and still reports green over them. That residue is named in tools/check-rules.md and
is the same one every enumeration above declares.
"""

import re
from typing import TYPE_CHECKING

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== floors: every enumeration this tool reads has members ==="

# The per-class capacity figures, each with the entry that owns it and the literal that
# entry states. None of them is a sum over anything: they are readings of the roster and
# of R-15-163's materials grading, so the tool never recomputes one. What it holds is
# that the owner still carries it, because a budget quoted in three documents and owned
# by none is the figure nothing owns.
CAPACITY: list[tuple[str, str, str]] = [
    ("R-15-247", "the two classes the plan places against", "two static latency classes"),
    ("R-15-173a", "the first class's single planar tier", "order 1–2 GB"),
    ("R-15-170", "the phone-class first-class budget", "4–8 GB"),
    ("R-15-170", "the laptop and desktop first-class budget", "16–32 GB"),
    ("R-15-247a", "the bulk tier the sidecar is priced against", "40 GB bulk tier"),
]

# The three artifacts that book the per-class bank count as open, and the reading in
# each. While all three hold, no figure exists to compare an island's ceiling against,
# and this rule's second half is the booking rather than the comparison.
BOOKED_OPEN: list[tuple[str, str, str]] = [
    ("register", "R-15-014a",
     "(viii) the per-class bank count (R-15-247p)"),
    ("register", "R-15-247p",
     "the per-class bank count is in R-15-014a's frozen parameter set"),
    ("docs/freeze-measurement-contract.md", "",
     "the per-class bank count (R-15-247p) are re-derived at the final freeze"),
]


def _two_class(ctx: Context) -> tuple[int, list[str]]:
    """The per-class capacity figures still owned, and everything that has moved.

    Read before the floors table is built, so the count of owned figures joins the
    enumerations K-47 requires to be non-empty: this rule catches the table narrowing
    and that one catches it emptying, which are different failures with the same cause.
    """
    reg = ctx.reg
    moved: list[str] = []
    owned = 0
    for ident, what, literal in CAPACITY:
        entry = reg.body.get(ident, "") + reg.accept_text.get(ident, "")
        if not entry:
            moved.append(f"{ident} owns {what} and the register no longer declares it")
        elif literal not in entry:
            moved.append(f"{ident} no longer states {what}, which this floor reads as "
                         f"'{literal}'")
        else:
            owned += 1

    for where, ident, literal in BOOKED_OPEN:
        text = reg.body.get(ident, "") if where == "register" else ctx.text(where)
        if literal not in text:
            names = ident or where
            moved.append(f"{names} no longer books the per-class bank count as open, so "
                         "the figure it withholds may now be stated and this floor is "
                         "the wrong instrument for it")
    return owned, moved


def run(ctx: Context) -> None:
    rep, reg, art, sh = ctx.rep, ctx.reg, ctx.art, ctx.shared
    rep.line(HEADING)

    claimed = {quantity for _, quantity, _, _ in ctx.claims}
    rep.report("K-46", "computed quantity(ies) no claim holds:",
               [f"{q} is computed and no document is required to state it, so nothing "
                "notices when it goes to zero" for q in ctx.q if q not in claimed],
               f"all {len(ctx.q)} computed quantities are held by a claim")

    owned, moved = _two_class(ctx)

    # the sets no figure counts, each named by what it is rather than where it is read,
    # so a floor that fails says which reading has moved
    floors = {
        "prose bookmarks": len(ctx.corpus.anchor_count),
        "entries one document names in another": sh.get("entry_refs", 0),
        "licence texts the third-party page locates": sh.get("licence_texts", 0),
        "tag-plane figures the granule fixes": sh.get("tag_plane", 0),
        "welded block sizes the constraints admit": sh.get("block_candidates", 0),
        "items of the freeze's closed delta": sh.get("delta_items", 0),
        "states the freshness enumeration names": sh.get("rot_states", 0),
        "bank counts the DSE contract declares": sh.get("bank_candidates", 0),
        "core-class table sites the rule can read": sh.get("core_class_sites", 0),
        "VLEN tokens the composition answers": sh.get("vlen_tokens", 0),
        "requirement citations in the model files read": sh.get("model_citations", 0),
        # Five rather than one, because the exclusion rule pairs what the profile writes
        # against what could answer it, and either side of either pairing emptying leaves
        # it reporting green over nothing. The profile writes two kinds of thing, a
        # mnemonic and a Sail constructor, and each is answered by its own reading of the
        # model: a name by the clauses that spell it and by the encoder table, a
        # constructor by the names the decode surface decodes to.
        "names the profile's exclusion rows spell": sh.get("exclusion_names", 0),
        "Sail constructors the profile's exclusion rows mark":
            sh.get("exclusion_markers", 0),
        "mnemonic spellings the model's assembly clauses make":
            sh.get("decode_spellings", 0),
        "names the model's decode surface decodes to": sh.get("decoded_names", 0),
        "rows of the corpus assembler's encoder table": sh.get("encoder_rows", 0),
        "values the shipped configurations state": sh.get("shipped_config_values", 0),
        # The ladder K-78 holds a vectorless composition below. It is the one vector
        # rung reachable without a configuration key, so a registry this rule can no
        # longer read would leave it reporting that every geometry is below no rungs
        # at all.
        "minimum-vector-length rungs the model declares": sh.get("zvl_rungs", 0),
        "per-class capacity figures the register owns": owned,
        "region classes the placement compound reads": sh.get("placement_terms", 0),
        "physical byte classes the composition is charged":
            sh.get("charged_terms", 0),
        # Two rather than one, because K-74 pairs a vocabulary against the cells that
        # spell it: a matrix whose declaring sentence has been rewritten places no mode
        # at all, and one whose cells have stopped booking residuals leaves the §17 half
        # deciding nothing while every mode still places.
        "discharge modes the coverage matrix declares": sh.get("cm_modes", 0),
        "coverage cells booking a residual": sh.get("cm_residual", 0),
        # Two rather than one, because K-76 pairs a contract's enumeration against a
        # record of bindings: a contract whose identifiers have been respelled leaves
        # the rule holding an empty set against a full one and reporting that every
        # absence of none is bound, and a record whose tables this rule can no longer
        # find leaves it reporting the reverse.
        "absences the contract enumerates": sh.get("absence_ids", 0),
        "rows of the synthesis provenance record": sh.get("provenance_rows", 0),
        # Nine rather than one, because K-77 pairs nine of the freeze contract's
        # enumerations against the instrument that implements them and each is a
        # separate table with a separate row shape. The instrument's side is a Python
        # literal and cannot narrow in silence; the contract's is a pattern over a
        # document, so it is the side a renumbering or a reworded header empties, and
        # K-77's own fail-closed reading and this floor catch that from both ends.
        "freeze corpus members": sh.get("freeze corpus members", 0),
        "freeze recipe steps": sh.get("freeze recipe steps", 0),
        "freeze operand classes": sh.get("freeze operand classes", 0),
        "freeze region classes": sh.get("freeze region classes", 0),
        "freeze region-class refusal reasons":
            sh.get("freeze region-class refusal reasons", 0),
        "freeze decisions": sh.get("freeze decisions", 0),
        "freeze report blocks": sh.get("freeze report blocks", 0),
        "freeze declared parameters": sh.get("freeze declared parameters", 0),
        "freeze CI predicates": sh.get("freeze CI predicates", 0),
        # And two more for the two pairs K-77 holds that are relations rather than
        # memberships. These are the floors under the *rule* rather than under the
        # document: a relation dropped out of the comparison narrows K-77 to its nine
        # memberships with every gate still green, which no membership floor can see.
        "freeze corpus feeds edges": sh.get("freeze corpus feeds edges", 0),
        "freeze threshold bindings in §6": sh.get("freeze threshold bindings in §6", 0),
        # Two rather than one, on the same ground the pair above states: K-79 holds a
        # definition against the sites that restate it, so a model whose declarations
        # have moved leaves it reporting that every site agrees with nothing, and a set
        # of sites this rule can no longer find leaves it reporting that nothing
        # disagrees with the definition.
        "capability-format parameters the model declares":
            sh.get("cap_format_params", 0),
        "sites restating a capability-format parameter":
            sh.get("cap_format_sites", 0),
        "CSR rows the profile presents": len(art.csr_rows.get("5.1", [])),
        "CSR rows the profile excludes": len(art.csr_rows.get("5.2", [])),
        "Prop fields of the apex record": len(sh["apex"].fields) if sh.get("apex") else 0,
        "rows of the field-bindings view": len(sh.get("row_order", [])),
        "checklist items": len(sh.get("items", [])),
        "checklist subtotals": len(sh.get("sections", [])),
        "dominant terms read from the big table": len(sh.get("ends", [])),
        "differential corpus members": len(sh.get("corpus_members", [])),
        "files that must carry a license mark": len(sh.get("markable", [])),
        # Two rather than one, on the pair K-76 states above: K-81 holds a record of
        # pins against the index that owns them and then holds every restatement
        # against that record, so a record whose table this rule can no longer read
        # leaves it reporting that every pin of none agrees, and a repository that
        # has stopped restating any leaves the second half deciding nothing while
        # the first still passes.
        "upstream pins the licence record states": sh.get("record_pins", 0),
        "sites restating an upstream pin": sh.get("pin_restatements", 0),
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

    rep.report("K-55", "two-class figure(s) whose owner or booking has moved:", moved,
               f"all {len(CAPACITY)} per-class capacity figures are owned by the entry "
               f"that fixes them, and {len(BOOKED_OPEN)} artifacts still book the "
               "per-class bank count as open")
    rep.line()
