# SPDX-License-Identifier: Apache-2.0
"""ledger: what each proof constant claims to answer, and the ledger that joins it.

[The citations group](citations.py) holds every requirement id a shipped proof *names*
against the register that declares it. That is a bibliography: it says the entry
informed the artifact and nothing about which sentence in the artifact answers it. The
whole of a proof file's evidence therefore arrived at the register as one undivided
lump, and the question a reviewer actually asks, *which constant claims this entry*, was
answered by reading the file.

A discharge annotation answers it. `(*| discharges: R-07-015, R-15-007i |*)` on the line
above a statement says that this constant claims those entries, and the two words are
kept apart everywhere here for the reason [proofcites](../proofcites.py) states at
length: a **citation** is a bibliography and a **claim** is a debt.

**A claim is a claim and never a proof that the theorem states the obligation.** A
constant can be annotated with an entry it has nothing to do with, and both this group
and the ledger it holds will report it as claimed, because deciding otherwise means
reading the entry's sentence against the theorem's and judging whether one is the other.
That reading is the review gate R-05-150 fixes, the residue R-17-016 declares, and a
person's. Nothing here narrows it, and the ledger's own preamble says so in its first
paragraph, so that a reader who meets the table before this file is not misled by it.

## K-105, and why it is reported rather than repaired

The rule holds four things about every annotation the tree carries and each is a
different edit. It parses in the form the contract fixes. Its ids are ids, comma
separated, distinct, and nothing else. It sits above a *statement* rather than above a
`Definition`, a `Fixpoint` or a `Record`, which is the failure that renders perfectly
and reads as correct. And every id it names is a **live** requirement of the register,
which is `Register.id_set` exactly as K-103 and K-45 read it: there is no second answer
to that question in this tool and this rule does not invent one.

**Reported and never repaired**, on the ground K-89, K-91 and K-103 each state. A
discharge is a claim about which entry an artifact answers. Either side may be the one
that moved, the entry retired or the annotation mistyped, and rewriting the annotation
to match the register would repair a disagreement into agreement with itself and delete
the only fact worth having, which is which of the two the edit landed in.

**A dead id inside an annotation is reported here and by K-103, and that is intended.**
An annotation is text in the artifact, so the ids in it are citations as well as claims
and the citation rule sees them one group earlier. What this rule adds is the half the
repair needs and the coarser reading structurally cannot reach, *which constant made the
claim*; a rule that fell silent because a neighbour had already spoken would have its
reach depend on the order of `GROUPS` rather than on its own subject. What is **not**
restated is the artifact this tool could not open at all: the per-file reason for that is
K-103's finding and is not written twice, and what stands here in its place is one line
saying how many of the index's proof artifacts this rule's subject is missing, so a
narrowed reading is never a silent one.

**Fail-closed on the marker rather than on the population.** Every `(*|` a proof artifact
carries is taken as an attempt at an annotation, so one that will not parse is a finding
instead of a comment the scan walks past, and an annotation above no statement is a
finding rather than a claim dropped out of the comparison. A register that yields no live
requirement at all is a finding too, that being a comparison made against an empty set.

What this rule deliberately does **not** carry is a floor over the annotation
population, and that is a decision rather than an omission. The annotations are an
authoring act in progress: a tree that carries none would fail such a floor for the
reason that nobody has annotated a theorem yet, which is the decision K-103 already
takes in the other direction when it puts an untracked `.v` outside its rule rather than
inside it. What is floored instead is the *ledger*, at K-106, whose rows are the join of
both halves and are not empty; so the group cannot pass over an empty subject, and the
half left unfloored is the claimed half alone. The day a population floor here would
floor something is the day the annotations are no longer being authored, and it belongs
to that landing.

## K-106, and why the ledger is not a row of the generated table

[tools/generated/proof-ledger.md](../../generated/proof-ledger.md) is that join written
down: one row per requirement, artifact and constant, saying whether the pair is cited
only or claimed. It is arithmetic over an enumeration this group already reads, so unlike
K-105 it **is** repaired: `--fix` writes what the generator writes, because there is no
disagreement between two artifacts to preserve, only a file that is or is not the
function of its owners.

[The generated group](generated.py) already holds three artifacts that way, and its
table was the obvious home for a fourth. It is refused, and the first reason is the one
that decides it. `generated.paths()` is read by the pins group, where it **exempts** a
generated artifact from the transcription rule K-81 holds over every other tracked file:
a machine-written file restates nothing, so an object-id-shaped token inside one is not a
transcription and there is no edit a finding could ask for. That exemption is right for
four megabytes of emitted Sail bit literals and wrong here. This artifact is a burn-down
a person reads row by row, its cells are requirement ids and Gallina names rather than
emitted literals, and taking a carve-out out of a hygiene rule for a table under human
review is buying nothing and giving up a window. The second reason is the `Emitter`
protocol's shape, `(root, bundle) -> str`: this artifact's owners are the **register**
and the shipped proofs, and neither reaches an emitter of that signature. Widening the
protocol to carry the `Context` would put a whole-corpus dependency inside the group that
runs **first**, and it runs first for the opposite reason to this one, its artifact being
an *input* four rules downstream read. This artifact is an output nothing downstream
reads, and its subject is the same proof artifacts [the citations group](citations.py)
opens one group earlier.

So the row was not taken and the rule is written here. What is kept from that table is
half its reading and deliberately not the other half. Kept: a generated artifact this
checkout does not carry as a tracked document is one every claim about is vacuous, so
that is asked before its bytes are read. Not kept: `corpus.staged_bytes`, which is how
the generated group asks it. That helper shells out to `git cat-file`, and one call
measured 98 to 192 ms on the host this landed on, where the whole of the reading below
is 8 ms and `check.py` is about 2 s. The generated group pays it because it compares the
working tree against the *index* and needs those bytes; this rule compares the working
tree against its **generator** and needs no blob at all, so the question it does have is
put to the corpus, which answered it once for the whole run out of the `ls-files` the
load already made.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vos import proofcites

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== ledger: what each proof constant claims, and the ledger that joins it ==="

# The generated artifact and the command that writes it, stated once so that a finding
# and the file's own header cannot come to name different repairs.
ARTIFACT = "tools/generated/proof-ledger.md"
GENERATOR = "run.py check --fix"

# The two values the claim column takes. `claimed` is the stronger reading and `cited`
# the weaker, and the column is named for the stronger one because a reader scanning it
# is looking for the debts rather than for the bibliography.
CLAIMED = "claimed"
CITED = "cited"

# What a cell says where there is nothing to name, which the working rules fix: a
# not-applicable cell is `n/a`, never a blank and never a bare dash.
NONE = "n/a"

# Where a cited row sorts among its artifact's rows for one entry. Negative because the
# claims sort by the order their annotations appear in the file, and a row naming no
# constant belongs ahead of all of them; it is never beside one, a claimed entry having
# no cited row.
CITED_RANK = -1


@dataclass(frozen=True)
class Row:
    """One joined pair: an entry, the artifact that reaches it, and how.

    `constant` is `n/a` on a cited row rather than empty, because the ledger is a
    Markdown table and an empty cell reads as a cell somebody forgot to fill.
    """

    requirement: str
    artifact: str
    constant: str
    claims: str

    def rendered(self) -> str:
        return (f"| {self.requirement} | {self.artifact} | {self.constant} "
                f"| {self.claims} |")


# The file's whole prose, which is a function of nothing and so is written here rather
# than composed. It states what a row means and why the file sits where it does, in that
# order, because a reader meets the ruling after the reading and not before it.
PREAMBLE = """\
# The proof ledger

*Generated by `run.py check --fix` from the register and the shipped proofs under
`proofs/`. Do not edit it: rule K-106 holds every byte against what its generator
writes, and a hand edit here is repaired rather than kept.*

A **citation** is a proof artifact naming a register entry, and it says only that the
entry informed the artifact. A **claim** is a constant inside that artifact carrying a
discharge annotation naming the entry, and it says that this constant answers it. The
second is much the stronger of the two, and it is still only a claim: neither this file
nor any rule over it decides whether the sentence a constant proves is the sentence its
entry demands. That reading is the review gate R-05-150 fixes and the residue R-17-016
declares, and it is a person's to make.

**This file sits under `tools/generated/` and it is not a derived view, and the reason is
worth stating because the promotion is the obvious next thought.** A derived view owes
its membership in **both** directions: rule K-14 reads a governing entry and a body
pattern, collects every register entry the pattern bears on, and reports any of them the
view has stopped carrying. That second direction is the whole value of a view and it is
what this table cannot supply today. The only bearing set available is one of two, and
neither will do. Taking *every entry some proof cites* is circular, because the ledger
carries exactly those by construction, so the rule would run, pass, and decide nothing.
Taking the entries that oblige a formal discharge means a discharge vocabulary in the
register itself, marking which obligations are owed a machine-checked answer at all;
nobody has yet shown what that costs to write or to keep. So this is a generated artifact
rather than a view. It carries no normative status, nothing cites it as authority, and
promotion to `docs/` is a later act gated on that measurement rather than a tidying.

Rows are in the register's own order, which is the prose's rather than the numeric one,
then by artifact, then in the order each artifact makes its claims. The claim column
reads `claimed` where a constant of that artifact claims the entry and `cited` where the
artifact names the entry and no constant in it claims it; the constant cell is `n/a` on a
cited row, there being no constant to name. An entry the register does not carry has no
row here at all, a ledger row being a join, and a citation or a claim that joins nothing
being a finding of the rules that read them rather than a row of this table.

| Requirement | Artifact | Constant | Claims |
| --- | --- | --- | --- |
"""


def order_of(ids: list[str]) -> dict[str, int]:
    """Each requirement id against its place in the register's own order.

    The first declaration wins where an id is declared twice, which K-10 reports: this is
    a sort key and it must be total whatever that rule finds, so a duplicate cannot make
    the ledger's order depend on which of the two the loop saw last.
    """
    place: dict[str, int] = {}
    for ident in ids:
        place.setdefault(ident, len(place))
    return place


def rows(place: dict[str, int], cites: dict[str, set[str]],
         claimed: dict[str, list[proofcites.Claim]]) -> list[Row]:
    """Every joined pair, in the ledger's order.

    An id outside `place` is one the register does not declare or has struck, and it
    yields no row: the ledger joins the two artifacts, and a citation or a claim that
    names nothing joins nothing. Which rule reports it is not this function's business
    and is deliberately not decided twice.

    Each row is built beside the key it sorts on rather than sorted by a function that
    goes looking for its constant afterwards, which is what keeps the ordering one
    `sorted` over the rows instead of a scan of the claim list per row.
    """
    keyed: list[tuple[tuple[int, str, int], Row]] = []
    for artifact in set(cites) | set(claimed):
        by_id: dict[str, set[tuple[int, str]]] = {}
        for order, (name, listed) in enumerate(claimed.get(artifact, [])):
            for ident in listed:
                by_id.setdefault(ident, set()).add((order, name))
        for ident in set(cites.get(artifact, set())) | set(by_id):
            if ident not in place:
                continue
            found = sorted(by_id.get(ident, set()))
            if not found:
                keyed.append(((place[ident], artifact, CITED_RANK),
                              Row(ident, artifact, NONE, CITED)))
                continue
            keyed += [((place[ident], artifact, order),
                       Row(ident, artifact, name, CLAIMED)) for order, name in found]
    return [row for _, row in sorted(keyed, key=lambda pair: pair[0])]


def emit(joined: list[Row]) -> str:
    """The ledger's whole text, which is the preamble and one line per row.

    It takes the rows rather than computing them, because its one caller counts them for
    its own verdict and the join is not worth walking twice in a run.
    """
    return PREAMBLE + "".join(f"{row.rendered()}\n" for row in joined)


def run(ctx: Context) -> None:
    rep, reg = ctx.rep, ctx.reg
    rep.line(HEADING)

    rels = [rel for rel in ctx.corpus.tracked if proofcites.is_source(rel)]
    pairs, _ = proofcites.read(ctx.root, rels)
    claimed, findings = proofcites.claims(pairs)
    cites = proofcites.citations(pairs)

    if len(pairs) < len(rels):
        # the per-file reason is K-103's, and repeating it here would price one
        # unreadable artifact as two findings; what this says is only that this rule's
        # subject is short of the index's, so a narrowed reading is not a silent one
        findings.append(f"{len(rels) - len(pairs)} of the {len(rels)} proof artifacts "
                        "the index carries could not be read here, so what their "
                        "constants claim is undecided")
    if not reg.id_set:
        findings.append("the register yields no live requirement at all, so every "
                        "discharge claim would be held against an empty set")

    total = 0
    for rel in sorted(claimed):
        for name, listed in claimed[rel]:
            total += 1
            findings += [f"{rel}: `{name}` claims to discharge {ident}, which names no "
                         "live requirement: the register declares no such entry, or has "
                         "struck it" for ident in listed if ident not in reg.id_set]

    rep.report("K-105", "discharge annotation(s) that do not decide what they claim:",
               findings,
               f"all {total} discharge annotations the {len(pairs)} proof artifacts "
               "carry are well formed, sit above a statement, and name only live "
               "requirements; whether each theorem states the obligation it claims is "
               "the review gate's")

    _ledger(ctx, order_of(reg.ids), cites, claimed)
    rep.line()


def _ledger(ctx: Context, place: dict[str, int], cites: dict[str, set[str]],
            claimed: dict[str, list[proofcites.Claim]]) -> None:
    """K-106: the generated ledger is the join, and `--fix` writes it.

    Fail-closed in two places, on K-67's and K-75's ground and on the generated group's.
    An artifact this checkout does not carry as a tracked document is one nothing decided
    about it means anything, so it is a finding before its bytes are read; the corpus is
    what answers that, and it answers the same way for a file the index never carried, one
    a peer session deleted out from under the run, and one whose path this corpus does not
    read, because the repair is the same act in all three. And a join yielding no row at
    all is a comparison made against an empty set, which is the floor the claimed half of
    K-105 does not carry.
    """
    rep = ctx.rep
    findings: list[str] = []
    joined = rows(place, cites, claimed)
    if not joined:
        findings.append("the register and the shipped proofs join at no pair at all, so "
                        f"{ARTIFACT} would be a table with no row and this rule would "
                        "hold a generated file against nothing")

    if ARTIFACT not in ctx.corpus:
        findings.append(f"{ARTIFACT} is generated by `{GENERATOR}` and this checkout "
                        "does not carry it as a tracked document, so nothing this "
                        "checker decides about it means anything")
    else:
        expected = emit(joined)
        # the corpus's copy rather than the file's, so that a `--fix` earlier in this
        # same run is what the comparison sees instead of the bytes it has just replaced
        held = ctx.text(ARTIFACT)
        if held != expected:
            findings.append(
                f"{ARTIFACT} is generated by `{GENERATOR}` and the working tree differs "
                f"from what its generator writes at line {_diverges(expected, held)}: a "
                "generated artifact is not edited by hand")
            if ctx.fix:
                ctx.fixed[ARTIFACT] = expected
                rep.line(f"fixed: {ARTIFACT} rewritten by its generator, "
                         f"{len(joined)} ledger row(s)")

    claims = sum(1 for row in joined if row.claims == CLAIMED)
    rep.report("K-106", "generated proof ledger that is not the join it states:",
               findings,
               f"{ARTIFACT} is the {len(joined)} pairs the register and the {len(cites)} "
               f"proof artifacts join at, {claims} of them claimed by a constant and the "
               "rest cited, in the register's own order")


def _diverges(expected: str, held: str) -> int:
    """The 1-based line the two texts first disagree on, for a person to go and look at.

    A line rather than a byte offset, because the repair is to run the generator and the
    figure's whole job is to say *where* it moved: a table row is a line here, so the
    number names the pair whose row changed, arrived or left.
    """
    mine, theirs = expected.splitlines(), held.splitlines()
    for i, (a, b) in enumerate(zip(mine, theirs, strict=False), start=1):
        if a != b:
            return i
    return min(len(mine), len(theirs)) + 1
