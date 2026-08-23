# SPDX-License-Identifier: Apache-2.0
"""costated: every fact stated in more than one pair, at each site that states it.

K-61 holds one entry against the prose its trace cites. What it cannot see, by
construction, is the fact stated in *two* pairs: each pair blesses on its own two
sides, so an edit that moves the fact in one pair leaves the other pair's copy
standing, internally consistent and silently wrong. The register's own discipline is
to cite rather than restate, and where the prose obeys it there is nothing here to
hold; these are the residue, the facts a survey of both documents found stated at
sites no single pair covers, each confirmed to be held by no other rule.

The hold is the K-55 shape one size up: each fact names its sites, each site is a
literal the artifact still states, and a site that stops stating it is the finding,
which names the sibling sites so the fact is revisited jointly rather than repaired
at the one site that moved. Nothing here is repaired: which side is right when they
part is a judgment, exactly the judgment K-61 asks for inside one pair, so a K-68
finding is settled by editing the sites back into agreement and re-reading the pairs
the edits dirty.

What this cannot decide is that the sites still *mean* the same thing when every
literal matches, nor that the table below is complete: a new restatement joins it by
being found, which is the same residue every enumeration in this tool declares.
"""

from typing import TYPE_CHECKING

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== costated: every fact stated across pairs, at each site stating it ==="

SPEC = "docs/spec.md"
REGISTER = "docs/requirements-register.md"

# One row per fact: what it is, and the sites that state it. A site names a register
# entry (held against that entry's own lines: body, criteria, conferrals) or a
# document (held against its text), and the literal is the site's own spelling, which
# the sites deliberately do not share: pinning each spelling separately is what lets
# one site move alone and be named for it.
COSTATED: list[tuple[str, list[tuple[str, str]]]] = [
    ("the sub-compartmentalization population", [
        ("R-14-007", "parsing attacker-controlled input, and any third-party library "
                     "handed capabilities beyond pure compute"),
        (SPEC, "parses attacker-controlled input or is handed authority beyond pure "
               "compute"),
    ]),
    ("the goal-ordering axiom", [
        ("R-01-006", "pessimism is free by axiom"),
        (SPEC, "performance is subordinate to security"),
        (SPEC, "the pessimism is free by axiom"),
    ]),
    ("the legacy radio generations' absence", [
        ("R-15-129", "5G and 6G only"),
        ("R-15-129", "cannot be received at all"),
        (SPEC, "2G/3G/4G are absent from the silicon"),
    ]),
    ("the foreign-computer exception count", [
        ("R-12-045", "the one tolerated foreign computer"),
        ("R-04-011", "the exception count is one"),
        (SPEC, "The single tolerated exception is the eUICC"),
    ]),
    # three spellings coexist on purpose: the owner's "wired data port", the threat
    # model's "USB data lanes", and R-15-150's "USB-data"; a normalizer that "fixes"
    # them apart is exactly the edit this row reports
    ("the sealed-cutoff device trio", [
        ("R-15-145", "the microphone, the radios, and the wired data port"),
        ("R-15-150", "The microphone, radio, and USB-data cutoffs"),
        (SPEC, "the microphone, the radios, and the USB data lanes"),
    ]),
    # the two heads state one relationship: the register's line-3 banner and the
    # banner spec.md opens with; editing either names the other for a joint revisit
    ("the precedence relationship, stated at both documents' heads", [
        (REGISTER, "This register, not the prose, is the artifact"),
        (SPEC, "where the two disagree the register wins (R-05-152)"),
        (SPEC, "which rule K-61 reports and `tools/co-read.py` records"),
    ]),
    ("the admission rule's non-duplication clause, cited by ordinal", [
        ("R-05-132", "(2) duplicates no existing grade or label axis"),
    ]),
    ("the frozen theory's absence (2), cited by ordinal", [
        ("R-05-129", "Absence (2): no type-level computation"),
    ]),
    ("the consent TCB's two proof clauses", [
        ("R-06-017", "exactly two clauses: mint only on witnessed consent, and bound "
                     "the mint to the named object"),
        ("R-08-036", "R-06-017's two clauses are mint-on-witness and "
                     "bound-to-the-named-object"),
    ]),
    # the terminal period encodes the list's tail: a reorder that stops the ninth
    # seam being ninth breaks this literal while every id still resolves
    ("the seam-lemma list's tail, which 'the ninth seam' resolves against", [
        ("R-05-160", "attestation ⋈ capability safety."),
    ]),
    ("the fence.t completeness map's four classes, cited by letter elsewhere", [
        ("R-15-217", "four classes: architectural or context-switched; "
                     "partition-owned; `fence.t`-flushed; or stream-determined "
                     "pipeline state"),
    ]),
    ("the background origin's floor share", [
        ("R-17-005", "one percent of one core"),
        (SPEC, "receives roughly one percent of one core"),
    ]),
    ("the recorded-nondeterminism enumeration", [
        ("R-16-015", "enumerated as exactly four sources"),
        ("R-16-015", "and the physical event stream the sentinel consumes"),
        (SPEC, "(entropy draws, link-layer address draws, counter reads, the "
               "sentinel's physical-event stream)"),
    ]),
    ("the RTL ⊑ Sail ladder's staging", [
        ("R-18-010", "rvfi first, then Sail-generated SystemVerilog plus commercial "
                     "FEV, then Isla-generated obligations, then the Kami/Kôika "
                     "Coq refinement"),
        ("R-01-002a", "the rungs R-18-010 stages split at the unbounded one"),
        (SPEC, "**Kami/Kôika** (Coq) is the closing vehicle"),
        (SPEC, "**riscv-formal/rvfi** (SVA + BMC) is the cheapest bring-up gate"),
        (SPEC, "**Isla** (symbolic Sail) generates the obligations"),
    ]),
    # the ruling R-05-022 states and the prose used to contradict: three interims on
    # the books, aiT and Binsec/Rel on none
    ("the interim-anchor books", [
        ("R-05-022", "The three entries (F\\*/Z3 for libcrux/HACL\\*, EasyCrypt's "
                     "Why3/SMT, Cranelift/Crocus's SMT)"),
        ("R-05-022", "aiT and Binsec/Rel are not interim anchors and carry no "
                     "retirement rule"),
        (SPEC, "aiT and Binsec/Rel are on no book at all"),
        (SPEC, "aiT and Binsec/Rel are bring-up gates and cross-checks that carry "
               "no claim"),
    ]),
    ("the WCET tooling disposition", [
        ("R-18-024", "retired as a workstream"),
        ("R-18-025", "never the bound"),
        (SPEC, "the standalone Coq-verified estimator is retired rather than built"),
        (SPEC, "**aiT (AbsInt) stays the unverified commercial cross-check**, never "
               "the axiom"),
    ]),
    ("the capacity-recovery field names", [
        ("R-16-025", "`reclaim_min` and `complete_by`"),
        ("R-18-036", "an action returning less than `reclaim_min`, an action missing "
                     "`complete_by`"),
    ]),
    ("the control-flow-signature protected sequences", [
        ("R-16-008c", "the measured-boot chain's per-stage verify-then-transfer, the "
                      "credential comparison at the RoT gate, and the lifecycle "
                      "transition over one-way fuse state"),
        ("R-16-008e", "instrumentation in three named regions"),
        ("R-16-008f", "The three R-16-008c sequences"),
        ("R-17-058c", "the three R-16-008c sequences"),
        (SPEC, "the three protected sequences carry their detection as a theorem"),
        (SPEC, "The three §16 protected sequences"),
    ]),
    ("the admission test's numbered discharges, cited by test ordinal elsewhere", [
        ("R-15-010", "(1) deterministic architectural semantics"),
        ("R-15-010", "(2) data-independent timing"),
        ("R-15-010", "(3) no new hidden shared microarchitectural state"),
        ("R-15-010", "(5) no autonomous behaviour"),
    ]),
    ("the admissible power mechanisms, cited by ordinal elsewhere", [
        ("R-15-186", "race-to-idle with in-slot gating; static per-partition "
                     "operating points; pre-proved global mode schedules; deep sleep "
                     "as a boot-chain variant; and composition-time gating of "
                     "unallocated SRAM"),
    ]),
]


def _site_text(ctx: Context, where: str) -> str:
    """What a site is held against: an entry's own lines, or a document's text."""
    if where.startswith("R-"):
        reg = ctx.reg
        parts = [reg.body.get(where, ""), reg.accept_text.get(where, "")]
        parts += [lines.get(where, "") for lines in reg.confers.values()]
        return " ".join(p for p in parts if p)
    return ctx.text(where)


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    findings: list[str] = []
    sites = 0
    for fact, stated in COSTATED:
        moved: list[str] = []
        for where, literal in stated:
            sites += 1
            if literal not in _site_text(ctx, where):
                moved.append(f"{where} no longer states it as '{literal}'")
        if moved:
            siblings = ", ".join(where for where, _ in stated)
            findings.append(f"{fact}: " + "; ".join(moved) +
                            f" (the sites stating it together: {siblings})")

    rep.report("K-68", "co-stated fact(s) with a moved site:", findings,
               f"all {len(COSTATED)} co-stated facts stand at every one of their "
               f"{sites} sites")
    rep.line()
