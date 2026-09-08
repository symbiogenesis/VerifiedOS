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

K-108 is the guard on the one thing K-103 above does not read, and it exists because
that exclusion can widen silently. Every artifact opens with prose transcribing the
entries it answers to, hand-maintained and going stale, and the standing proposal is to
replace the transcribed half with a delimited region a repair writes from the cited
entries' normative lines. **The reading above makes that self-feeding, which is a
design defect and not a caveat**: K-103 and `run.py blast` read citations with a
whole-text scan and deliberately no comment stripping, on the ground that a Gallina
identifier cannot carry a hyphen, so an `R-nn-nnn` in a `.v` is inside a comment by
construction; and a register entry line cites other entries. Measured over this tree,
transcribing the cited entries' opening lines introduces 43 ids `DischargeSequence.v`
does not itself cite, 28 in `MemoryPlan.v`, 23 in `ApexTheorem.v` and 22 in
`PartitionContext.v`, and each regeneration widens the set: repeated to a fixed point
those two reach 200 and 77 against the 26 and 38 they genuinely make, at which `blast`
answers a register edit with the artifacts that merely quote the entry.

So [proofcites.derived](../proofcites.py) holds a region out of `ids`, and this is the
rule that stops the hole widening past a transcription. **Three readings and one
floor.** The delimiters balance in every artifact, an imbalance being reported by the
parse rather than swallowed, because a BEGIN nobody closed would hold every citation
below it out of K-103's reading and leave that rule green over nothing. A region
carries only transcribed entry lines: no vernacular, which is either a region that has
swallowed the file it sits in or a definition the next regeneration deletes, and no
line that neither names a requirement nor continues a line that did. And every id a
region names is one the entries the artifact **genuinely** cites, outside every region,
would transcribe, so a citation cannot be moved inside a region to take it out of
K-103's reach. That last is what makes the exclusion unable to widen quietly: the
permitted set is the cited entries' own normative lines, so a writer that transcribed
their criteria too would be reported here and would owe somebody a decision rather than
getting one by default.

**The floor is a probe, and it is stated as one because the tree carries no derived
region at all today.** The other three readings would therefore agree with every one of
no regions, which is exactly the vacuous pass the floors group exists for, and no
member count would help: what has to stay decided is that the exclusion is still an
exclusion. So the rule runs the shared parse over four texts it composes from the
delimiters the module declares, and reports where the answer moved. What the probe does
not decide is the *spelling* of a delimiter, both sides taking it from one declaration;
what covers that is the parse's own fault for a marker that is neither delimiter, which
is how a respelled one arrives in a real artifact. Its own reading is the floor on the
ground K-83, K-97, K-101 and K-103 each state, so it owes the floors group no member.

Reported and never repaired, on K-103's own ground: a region that disagrees with the
entries an artifact cites may be wrong on either side, and the writer that would rewrite
one does not exist yet.
"""

import re
from typing import TYPE_CHECKING

from vos import proofcites

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotations below cost no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from vos.register import Register

    from . import Context

HEADING = "=== citations: what the proof artifacts cite, against the register ==="

MODULE = "tools/vos/proofcites.py"

# The vernaculars a derived region may not open a line with, and the shape one takes.
# `proofcites.DEFINERS` is every sentence that binds a top-level name, and the four
# commands beside it are what a region that has swallowed the file it sits in carries
# first. The shape is what keeps the reading sharp: a definer counts only where a name
# follows it, and the four stand alone before their period, so an ordinary English
# sentence opening with one of these words inside a transcription is not read as code.
_COMMANDS = ("Require", "Import", "Export", "Axiom", "Parameter", "Hypothesis",
             "Ltac", "Notation")
_STANDALONE = ("Proof", "Qed", "Defined", "Admitted")
_MODIFIERS = r"(?:#\[[^\]]*\]\s*)?(?:Local\s+|Global\s+|Program\s+)*"
_VERNACULAR_RE = re.compile(
    rf"^\s*(?:{_MODIFIERS}(?:{'|'.join((*proofcites.DEFINERS, *_COMMANDS))})\s+[\w'(]"
    rf"|(?:{'|'.join(_STANDALONE)})\s*\.)")

# The two ids the probe is written over. They are shaped like requirement ids and are
# deliberately not read against the register: what the probe decides is the exclusion's
# behaviour over a text this rule composes, and a live id here would make it look like a
# reading of the corpus, which it is not.
_OUTSIDE = "R-99-001"
_INSIDE = "R-99-002"


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    rels = [rel for rel in ctx.corpus.tracked if proofcites.is_source(rel)]
    empty = ([f"the git index carries no {proofcites.SUFFIX} file under "
              f"{proofcites.PROOFS}/, so there is no proof artifact for this rule to "
              "read a citation out of"] if not rels else [])
    pairs, faults = proofcites.read(ctx.root, rels)

    _cited(ctx, rels, pairs, empty + faults)
    _regions(ctx, pairs, empty + faults)
    rep.line()


def _cited(ctx: Context, rels: list[str], pairs: list[tuple[str, str]],
           findings: list[str]) -> None:
    """K-103: every citation a shipped proof artifact makes names a live requirement."""
    rep, reg = ctx.rep, ctx.reg
    findings = list(findings)

    total = 0
    distinct: set[str] = set()
    for rel, text in pairs:
        cited = proofcites.ids(text)
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


def _transcribable(reg: Register, cited: set[str]) -> set[str]:
    """Every id a transcription of the entries one artifact cites would name.

    The entries' own ids and whatever their normative lines cite, which is exactly what
    a region written from those lines can carry. The register's line is the source
    because that is what the proposal writes a region from; a writer that transcribed
    the criteria beneath it would name ids outside this set, and being reported for it
    is the point rather than a limitation, an exclusion that widened on its own being
    the defect this rule exists to refuse.
    """
    named = set(cited)
    for ident in cited:
        body = reg.body.get(ident)
        if body:
            named |= set(proofcites.ids(body))
    return named


def _content(rel: str, text: str, span: tuple[int, int]) -> list[str]:
    """What one derived region carries that a transcription of entry lines does not.

    A blank line is admitted, a line naming a requirement is a transcribed entry line,
    and an indented line under one is its continuation, which is how a long normative
    line arrives inside a header wrapped. Anything else is prose a regeneration would
    delete or code it would delete, and the two are told apart because the finding a
    reader gets should say which of the two it is looking at.
    """
    found: list[str] = []
    entry = False
    for n, line in enumerate(text[span[0]:span[1]].splitlines(),
                             start=proofcites.line_at(text, span[0])):
        if not line.strip():
            continue
        if _VERNACULAR_RE.match(line):
            found.append(f"{rel}:{n} opens a vernacular inside a derived region, which "
                         "is either the region swallowing the file it sits in or a "
                         "definition the next regeneration would delete")
            continue
        if proofcites.ids(line):
            entry = True
            continue
        if not (entry and line[:1].isspace()):
            found.append(f"{rel}:{n} is inside a derived region and names no "
                         "requirement, so it is neither a transcribed entry line nor "
                         "the continuation of one")
    return found


def _probe() -> tuple[int, list[str]]:
    """The exclusion held against its own contract, which is this rule's floor.

    No artifact carries a derived region yet, so the three readings above would agree
    with every one of no regions. What stays decidable is whether the exclusion is
    still an exclusion, and that is decided by running the shared parse over texts
    composed here from the delimiters the module declares. Four readings, because the
    exclusion can fail in four directions and only one of them is the obvious one: it
    can stop excluding, it can over-reach past a region, it can reach text no delimiter
    marks, and it can swallow an imbalance instead of reporting it.
    """
    plain = f"an artifact citing {_OUTSIDE} and {_INSIDE}\n"
    region = (f"an artifact citing {_OUTSIDE}\n{proofcites.DERIVED_BEGIN}\n"
              f"**{_INSIDE}** MUST be transcribed here.\n{proofcites.DERIVED_END}\n")
    unclosed = (f"an artifact citing {_OUTSIDE}\n{proofcites.DERIVED_BEGIN}\n"
                f"**{_INSIDE}** MUST be transcribed here.\n")

    readings: list[tuple[str, bool]] = [
        ("text no delimiter marks is read whole",
         proofcites.ids(plain) == [_OUTSIDE, _INSIDE]),
        ("what a region carries is held out of the citation reading",
         proofcites.ids(region) == [_OUTSIDE]),
        ("a well-formed region is one span and no fault",
         len(proofcites.derived(region).spans) == 1
         and not proofcites.derived(region).faults),
        ("an unclosed region is a fault and excludes nothing",
         bool(proofcites.derived(unclosed).faults)
         and proofcites.ids(unclosed) == [_OUTSIDE, _INSIDE]),
    ]
    return len(readings), [f"{MODULE} no longer holds that {what}, so the exclusion "
                           "this rule guards has moved under it"
                           for what, held in readings if not held]


def _regions(ctx: Context, pairs: list[tuple[str, str]],
             findings: list[str]) -> None:
    """K-108: a derived region is a transcription of what its artifact already cites.

    Fail-closed where K-103 is, an index carrying no artifact and an artifact this run
    could not read being handed in as findings already, and floored on the probe rather
    than on a member count: a tree with no derived region at all still decides that the
    exclusion excludes, which is the property that stops it widening while nobody looks.
    """
    rep, reg = ctx.rep, ctx.reg
    findings = list(findings)

    probes, moved = _probe()
    findings += moved

    regions = lines = 0
    for rel, text in pairs:
        region = proofcites.derived(text)
        findings += [f"{rel}: {fault}" for fault in region.faults]
        if not region.spans:
            continue
        allowed = _transcribable(reg, set(proofcites.ids(text)))
        for span in region.spans:
            regions += 1
            lines += sum(1 for line in text[span[0]:span[1]].splitlines() if line.strip())
            findings += _content(rel, text, span)
            findings += [
                f"{rel} transcribes {ident} inside a derived region and cites it "
                "nowhere outside one, and no entry it does cite names it, so the "
                "region is holding a citation out of K-103's reading"
                for ident in sorted(set(proofcites.cited_within(text, span)))
                if ident not in allowed]

    rep.report("K-108", "derived region(s) the citation exclusion cannot be held to:",
               findings,
               f"the {len(pairs)} proof artifacts' derived-region delimiters balance, "
               f"the {lines} lines their {regions} regions carry transcribe only "
               f"entries those artifacts cite, and the exclusion holding a region out "
               f"of K-103's reading answers at each of its {probes} probes")
