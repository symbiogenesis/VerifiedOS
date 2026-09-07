# SPDX-License-Identifier: Apache-2.0
"""citations: what the proof artifacts argue from, against the register that declares it.

Every shipped proof under [proofs/](../../../proofs/) opens by naming the entries it
answers to, and goes on naming them beside each definition and each judgment, in bulk.
Not one of those citations was checked. `proofs/` carries no Markdown, so K-11 never saw
it; K-63 is the same reading one tree over and its window is `model/` by name. A
mistyped id in a proof header therefore rendered as a citation, survived review,
compiled, passed the assumption gate, and pointed at nothing. How many citations there
are is this rule's own `ok` line's to state and is never written down here.

**What this decides is *live* and not merely *declared*, and the two are different
questions here.** Ids are permanent: a retired requirement keeps its number and is
struck rather than removed or reused, so an id can be one the register once declared and
no longer carries. The set of live requirements is `Register.id_set`, which is the
answer [confers.py](confers.py) already gives to the same question at K-45 and the
answer [the co-read ledger](../cli/coread.py) gives when it purges a row: the register
parse admits an entry from its own unstruck normative line, so a struck entry is out of
that set by construction and this rule reports a citation of one exactly as it reports a
citation of an id nobody ever wrote. There is no second answer to that question in this
tool and this rule does not invent one.

**Reaching into `proofs/` costs no corpus-window change**, on the precedent
[bindings.py](bindings.py) sets by reading the apex statement off `ctx.root` and
[keccak.py](keccak.py) sets by reading a Gallina file and a Sail file: this checker's
corpus is the Markdown the git index carries, and a rule whose subject is outside it
reads that subject itself. The subject here is an enumeration rather than a named pair,
so it is taken from the index by kind, which is what makes an artifact that lands
tomorrow inside the rule the day it is staged and keeps this file free of a list
somebody maintains.

**An untracked `.v` is outside this rule rather than a finding of it**, and that is a
decision rather than an omission. A proof artifact is untracked for as long as it takes
to write one, and a rule that reddened at it would be reporting the act of authoring a
proof; what the corpus boundary means is that nothing here decides about a file the
index does not carry, which is the same thing K-11 means about an untracked document.

Fail-closed in four places on K-67's and K-75's ground. An index carrying no proof
artifact at all is a finding, never a walk over nothing. A listed artifact absent from
the working tree has no bytes, and one that will not decode cannot be decided about;
each is reported rather than dropped out of the comparison. And a scan that finds no
citation at all would leave this rule agreeing with every one of no citations, so that
floor is stated here, in the rule, rather than read off a document or handed to the
floors group: the reading is its own floor, on the ground K-83, K-97 and K-101 each
state, and there is no figure to state because the tree is expected to grow proof
artifacts and a fixed count would turn that growth into a finding.

**`--fix` does not repair it**, on the ground K-89 and K-91 both state and the co-read
ledger states first. A citation is a claim about which entry governs an artifact, so
either side may be the one that moved: rewriting the citation to match the register
would repair a disagreement into agreement with itself and delete the only interesting
fact, which is which of the two the edit landed in.
"""

from typing import TYPE_CHECKING

from vos import evidence

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== citations: what the proof artifacts cite, against the register ==="


def run(ctx: Context) -> None:
    rep, reg = ctx.rep, ctx.reg
    rep.line(HEADING)

    rels = [rel for rel in ctx.corpus.tracked if evidence.is_source(rel)]
    findings: list[str] = []
    if not rels:
        findings.append(f"the git index carries no {evidence.SUFFIX} file under "
                        f"{evidence.PROOFS}/, so there is no proof artifact for this "
                        "rule to read a citation out of")

    pairs, faults = evidence.read(ctx.root, rels)
    findings += faults

    total = 0
    distinct: set[str] = set()
    for rel, text in pairs:
        cited = evidence.ids(text)
        total += len(cited)
        distinct |= set(cited)
        findings += [f"{rel} cites {ident}, which names no live requirement: the "
                     "register declares no such entry, or has struck it"
                     for ident in sorted(set(cited)) if ident not in reg.id_set]

    if rels and not total:
        findings.append(f"the {len(pairs)} proof artifacts make no requirement citation "
                        "at all, so this rule would agree with every one of no citations")

    rep.report("K-103", "proof citation(s) naming no live requirement:", findings,
               f"all {total} requirement citations the {len(pairs)} proof artifacts "
               f"make, {len(distinct)} of them distinct, name a live requirement of the "
               "register")
    rep.line()
