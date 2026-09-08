# SPDX-License-Identifier: Apache-2.0
"""ledger: what each proof constant claims to answer, and the ledger that joins it.

[The citations group](citations.py) holds every requirement id a shipped proof *names*
against the register that declares it. That is a bibliography: it says the entry
informed the artifact and nothing about which sentence in the artifact answers it. The
whole of a proof file's evidence therefore arrived at the register as one undivided
lump, and the question a reviewer actually asks, *which constant claims this entry*,
was answered by reading the file.

A discharge annotation answers it. `(*| discharges: R-07-015, R-15-007i |*)` on the
line above a statement says that this constant claims those entries, and the two words
are kept apart everywhere here for the reason [proofcites](../proofcites.py) states at
length: a **citation** is a bibliography and a **claim** is a debt.

**A claim is a claim and never a proof that the theorem states the obligation.** A
constant can be annotated with an entry it has nothing to do with, and both this group
and the ledger it holds will report it as claimed, because deciding otherwise means
reading the entry's sentence against the theorem's and judging whether one is the
other. That reading is the review gate R-05-150 fixes, the residue R-17-016 declares,
and a person's. Nothing here narrows it, and the ledger's own preamble says so in its
first paragraph so that a reader who meets the table before this file is not misled by
it.

## K-105, and why it is reported rather than repaired

The rule holds four things about every annotation the tree carries and each is a
different edit. It parses in the form the contract fixes. Its ids are ids, comma
separated and nothing else. It sits above a *statement* rather than above a
`Definition`, a `Fixpoint` or a `Record`, which is the failure that renders perfectly
and reads as correct. And every id it names is a **live** requirement of the register,
which is `Register.id_set` exactly as K-103 and K-45 read it: there is no second answer
to that question in this tool and this rule does not invent one.

**Reported and never repaired**, on the ground K-89, K-91 and K-103 each state. A
discharge is a claim about which entry an artifact answers. Either side may be the one
that moved, the entry retired or the annotation mistyped, and rewriting the annotation
to match the register would repair a disagreement into agreement with itself and delete
the only fact worth having, which is which of the two the edit landed in.

**Fail-closed on the marker rather than on the population.** Every `(*|` a proof
artifact carries is taken as an attempt at an annotation, so one that will not parse is
a finding instead of a comment the scan walks past, and an annotation above no statement
is a finding rather than a claim dropped out of the comparison. A register that yields
no live requirement at all is a finding too, that being a comparison made against an
empty set.

What this rule deliberately does **not** carry is a floor over the annotation
population, and that is a decision rather than an omission. The annotations are an
authoring act in progress: the tree carries none today, so a rule that reddened at zero
would be reporting that nobody has annotated a theorem yet, which is the decision K-103
already takes in the other direction when it puts an untracked `.v` outside its rule
rather than inside it. What is floored instead is the *ledger*, at K-106, whose rows are
the join of both halves and are not empty; so neither rule can pass over an empty
subject, and the half that is unfloored is the claimed half alone. The day the
annotations land is the day a population floor here becomes a floor over something, and
it belongs to that landing.

## K-106, and why the ledger is not a row of the generated table

[tools/generated/proof-ledger.md](../../generated/proof-ledger.md) is that join written
down: one row per requirement, artifact and constant, saying whether the pair is cited
only or claimed. It is arithmetic over an enumeration this group already reads, so
unlike K-105 it **is** repaired: `--fix` writes what the generator writes, because there
is no disagreement between two artifacts to preserve, only a file that is or is not the
function of its owners.

[The generated group](generated.py) already holds three artifacts that way, and its
table was the obvious home for a fourth. It was measured and refused, on two grounds.

The first is the `Emitter` protocol, which is `(root, bundle) -> str`. This artifact's
owners are the **register** and the shipped proofs, and the register reaches an emitter
of that shape only by being parsed again inside it: measured on the host this landed on,
`corpus.load` is 347 to 606 ms and `read_register` 8 ms, against the 11 ms this whole
reading spends on I/O and the 7 ms it spends scanning. [The tools' own
README](../../README.md) prices a host row at its generator's runtime times the sandbox
count and records the measurement that fixes the relation, the first host row's 0.15 s
generator taking the mutation wave from 35.6 s to 52 s; at that relation a re-parse per
emission is tens of seconds on a wave whose whole run-to-run spread is under six.

The second is what the alternative costs. Widening the protocol to carry the `Context`
would put a whole-corpus dependency inside the group that runs **first**, and it runs
first for a stated reason that is the opposite of this one: its artifact is an *input*
to four rules downstream, so it settles bytes others read. This artifact is an output
that nothing downstream reads, and its subject is the same twenty-one files
[the citations group](citations.py) opens one group later, so reading it here shares
that read instead of paying for it twice.

So the row was not taken and the rule is written here. What is kept from that table is
its reading, which is the part worth reusing: the index is asked whether the artifact is
tracked at all, because a generated file the index does not carry is one every claim
about is vacuous, and the working tree is what the bytes are compared against, because
the index says what is *tracked* and the file says what it *says*.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vos import corpus as corpus_mod
from vos import proofcites

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== ledger: every discharge claim, and the ledger that joins it ==="

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
        return f"| {self.requirement} | {self.artifact} | {self.constant} | {self.claims} |"


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

**This file sits under `tools/generated/` and it is not a derived view.** A derived view
here is an artifact the register *obliges*, declared by a governing requirement that
names it and fixes what it must carry; that obligation is what the checker's view rules
hold, in both directions, and what lets a bearing entry a view has stopped carrying be
reported at all. No register entry obliges a proof ledger. Declaring one anyway, under a
governing id invented to fill the column, would be the view legislating its own
obligation, which is the defect R-17-016 forecloses; and R-07-031b has already refused a
derived view outright on the ground that its bearing set would ship mostly empty, which
is this ledger's own position for as long as the claim column below reads `cited`
throughout. So it is a generated artifact, which needs no register obligation, and it
carries no normative status at all.

Rows are in the register's own order, which is the prose's rather than the numeric one,
then by artifact, then in the order each artifact makes its claims. The claim column
reads `claimed` where a constant of that artifact claims the entry and `cited` where the
artifact names the entry and no constant in it claims it; the constant cell is `n/a` on
a cited row, there being no constant to name. An entry the register does not carry has
no row here at all, a ledger row being a join and a citation or a claim that joins
nothing being a finding of the rules that read them rather than a row of this table.

| Requirement | Artifact | Constant | Claims |
| --- | --- | --- | --- |
"""


def order_of(ids: list[str]) -> dict[str, int]:
    """Each requirement id against its place in the register's own order.

    The first declaration wins where an id is declared twice, which K-10 reports: this
    is a sort key and it must be total whatever that rule finds, so a duplicate cannot
    make the ledger's order depend on which of the two the loop saw last.
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
    """
    found: list[Row] = []
    for artifact in sorted(set(cites) | set(claimed)):
        # the file's own order for the constants, so that a ledger read down an
        # artifact's rows reads down the artifact
        rank = {name: i for i, (name, _) in enumerate(claimed.get(artifact, []))}
        by_id: dict[str, list[str]] = {}
        for name, listed in claimed.get(artifact, []):
            for ident in listed:
                by_id.setdefault(ident, []).append(name)
        for ident in sorted(set(cites.get(artifact, set())) | set(by_id),
                            key=lambda i: (place.get(i, len(place)), i)):
            if ident not in place:
                continue
            names = sorted(by_id.get(ident, []), key=lambda n: rank[n])
            found += ([Row(ident, artifact, name, CLAIMED) for name in names] if names
                      else [Row(ident, artifact, NONE, CITED)])
    return sorted(found, key=lambda r: (place[r.requirement], r.artifact,
                                        _rank(claimed, r)))


def _rank(claimed: dict[str, list[proofcites.Claim]], row: Row) -> int:
    """A row's place among its artifact's rows: the constant's declaration order, and
    -1 for the cited row, which carries no constant and sorts ahead of the claims."""
    for i, (name, _) in enumerate(claimed.get(row.artifact, [])):
        if name == row.constant:
            return i
    return -1


def emit(place: dict[str, int], cites: dict[str, set[str]],
         claimed: dict[str, list[proofcites.Claim]]) -> str:
    """The ledger's whole text, which is the preamble and one line per row."""
    return PREAMBLE + "".join(f"{row.rendered()}\n"
                              for row in rows(place, cites, claimed))


def run(ctx: Context) -> None:
    rep, reg = ctx.rep, ctx.reg
    rep.line(HEADING)

    rels = [rel for rel in ctx.corpus.tracked if proofcites.is_source(rel)]
    pairs, faults = proofcites.read(ctx.root, rels)
    claimed, problems = proofcites.claims(pairs)
    cites = proofcites.citations(pairs)

    findings: list[str] = list(faults) + list(problems)
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
               f"carry are well formed, sit above a statement, and name only live "
               "requirements; whether each theorem states the obligation it claims is "
               "the review gate's")

    _ledger(ctx, order_of(reg.ids), cites, claimed)
    rep.line()


def _ledger(ctx: Context, place: dict[str, int], cites: dict[str, set[str]],
            claimed: dict[str, list[proofcites.Claim]]) -> None:
    """K-106: the generated ledger is the join, and `--fix` writes it.

    Fail-closed in three places, on K-67's and K-75's ground and on the generated
    group's. An artifact the git index does not carry is one nothing decided about it
    means anything, so it is a finding before its bytes are read. A join yielding no row
    at all is a comparison made against an empty set, and it is the floor the claimed
    half of K-105 does not carry. And a file this checker cannot read is not a file that
    agrees.
    """
    rep = ctx.rep
    findings: list[str] = []
    joined = rows(place, cites, claimed)
    if not joined:
        findings.append(f"the register and the shipped proofs join at no pair at all, so "
                        f"{ARTIFACT} would be a table with no row and this rule would "
                        "hold a generated file against nothing")

    if corpus_mod.staged_bytes(ctx.root, ARTIFACT) is None:
        findings.append(f"{ARTIFACT} is generated by `{GENERATOR}` and the git index "
                        "does not carry it, so nothing this checker decides about it "
                        "means anything")
    else:
        expected = emit(place, cites, claimed)
        held = ctx.text(ARTIFACT) if ARTIFACT in ctx.corpus else _read(ctx)
        if held != expected:
            findings.append(
                f"{ARTIFACT} is generated by `{GENERATOR}` and the working tree differs "
                f"from what its generator writes at line {_diverges(expected, held)} of "
                f"{expected.count(chr(10))}: a generated artifact is not edited by hand")
            if ctx.fix:
                ctx.fixed[ARTIFACT] = expected
                rep.line(f"fixed: {ARTIFACT} rewritten by its generator, "
                         f"{len(joined)} ledger row(s)")

    claims = sum(1 for row in joined if row.claims == CLAIMED)
    rep.report("K-106", "generated proof ledger that is not the join it states:",
               findings,
               f"{ARTIFACT} is the {len(joined)} pairs the register and the "
               f"{len(cites)} proof artifacts join at, {claims} of them claimed by a "
               "constant and the rest cited, in the register's own order")


def _read(ctx: Context) -> str:
    """The artifact off disk, for the run in which it is not a corpus document yet.

    A file the index carries and the working tree does not, or one that will not decode,
    comes back as text that cannot equal the emission, so the comparison above reports it
    instead of raising here. The corpus is preferred where it has the file because
    `--fix` may already have rewritten it in this same run, and reading disk would then
    hold the run against bytes it has just replaced.
    """
    try:
        return (ctx.root / ARTIFACT).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"unreadable: {exc}"


_LINE_RE = re.compile(r"[^\n]*\n?")


def _diverges(expected: str, held: str) -> int:
    """The 1-based line the two texts first disagree on, for a person to go and look at.

    A line rather than a byte offset, because the repair is to run the generator and the
    figure's whole job is to say *what changed*: a table row is a line here, so the line
    number names the pair whose row moved.
    """
    for i, (a, b) in enumerate(zip(_LINE_RE.findall(expected), _LINE_RE.findall(held),
                                   strict=False), start=1):
        if a != b:
            return i
    return min(expected.count("\n"), held.count("\n")) + 1
