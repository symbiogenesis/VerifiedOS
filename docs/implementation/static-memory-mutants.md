# Mutating the static-memory oracle: invalid candidates must fail

> Non-normative research companion. The [requirements register](../requirements-register.md)
> remains authoritative. This sweep confers no implementation landing credit and accepts
> no requirement. It exercises one finite research model and touches no admission checker.

The [research agenda](../background/static-memory-research.md) asks for exact
small-instance oracles in which invalid candidates must fail, mutating lifetimes,
alignment, owner assignment, slot overlap and reuse barriers. The
[bounded oracle and independent replay](static-memory-experiments.md) supply the two
things such a sweep needs: a checker that decides one candidate against an unchanged
contract, and a replay that decides one optimality claim.
[static_memory_mutants.py](../../tools/vos/static_memory_mutants.py) supplies the
defects. It applies the vocabulary the repository already uses for generated
validation, which the [tool guide](../../tools/README.md#the-three-generators-and-what-each-answers)
states: a killed mutant moved the oracle's answer, a survivor is the finding, and a
stillborn one decided nothing.

## What a mutant is here

A mutant is a contract paired with a candidate, or a contract paired with an optimality
receipt. An operator moves one side of that pair so that one named constraint is
violated, and it constructs that violation by arithmetic over the declared fields. It
never asks the checker where to put a base, so a verdict is a statement about the
checker rather than about the construction.

Two guarantees make the verdicts mean something. Where an operator cannot guarantee a
violation at a site, it emits no mutant and reports the site as stillborn with its
reason, so an equivalent mutant is never counted as a kill. Where the construction would
break a second constraint as well, it either moves the slot above every extent the arena
already holds, which is disjoint from all of them because they end at or below that
point, or it declines the site. A contract-side operator rebuilds the contract through
the model's own parser, so a lifetime mutant stays a legal contract whose placement is
what became illegal.

## The operators

Placement operators move the candidate or the contract, and the checker's findings name
the constraint before their colon.

| Operator | Constraint targeted | Expected refusal | Where it applies |
| --- | --- | --- | --- |
| `overlap-collide` | slot overlap | `overlap` | an ordered pair of same-arena objects whose lifetimes interfere, where the peer's slot fits at this object's base under the peer's own alignment |
| `alignment-shift` | base alignment | `alignment` | an object whose declared alignment exceeds one, where a misaligned base above the arena's occupied span still fits |
| `capacity-overflow` | arena capacity | `capacity` | every object; the aligned base at or above the occupied span that ends past the capacity always exists |
| `ownership-reassign` | arena ownership | `ownership` | every object of a contract that declares more than one arena |
| `identity-duplicate` | candidate identity | `identity` | every object |
| `identity-drop` | candidate identity | `identity` | every object |
| `lifetime-extend` | slot overlap | `overlap` | an ordered same-arena pair whose predecessor releases its extent at or before the successor's first instant |
| `reuse-before-sweep` | reuse barrier | `overlap` | the same pairs, where the predecessor still charges extent after its `sweep_end` |
| `reuse-before-authority` | reuse barrier | `overlap` | the same pairs, where the predecessor still charges extent after its `authority_end` |

The two reuse-barrier operators follow the contract's own lifecycle fields. They start
the successor inside the window the predecessor still charges, at the boundary the
model calls the completed sweep and at the boundary it calls completed authority, and
the checker must refuse both because the extent is reserved through `reuse`. Their
stillborn reason is itself informative: a contract whose barriers coincide with its
reuse boundary reserves nothing after them, and there is no barrier violation to build.

Certificate operators move an optimality receipt that the unmutated replay verifies, and
the expected refusal is a rejected replay whose finding belongs to the named family.

| Operator | Claim targeted | Expected refusal | Where it applies |
| --- | --- | --- | --- |
| `bound-raise-load` | the independently computed charged load | the arena row's own refusal | every arena of a verified receipt |
| `bound-lower-span` | the span the receipt's own witness attains | the arena row's own refusal | every arena holding at least one slot |
| `witness-refused` | the witness the optimality claim carries | a placement-checker finding | every object of a verified receipt |
| `certificate-argument` | the exhaustion or load-equality argument | a finding naming the certificate | every arena of a verified receipt |

`bound-raise-load` and `bound-lower-span` are the two directions of a false bound, and
`certificate-argument` alters the height the exhaustion argument challenges, or claims
exhaustion where the receipt argued equality with load. A contract whose bounded search
does not complete, or whose unmutated receipt does not replay, yields stillborn
certificate sites rather than mutants: there is no optimality claim there to falsify.

## The four verdicts, and why a miskill is its own

- **Killed.** The oracle refused, and a finding names the constraint the operator
  targeted.
- **Miskilled.** The oracle refused, but no finding names that constraint. The candidate
  is still refused, so this is not a soundness finding; it is a finding about the error
  typing, because a consumer reading the refusal is told the wrong thing about why. It
  is reported apart for the reason the tool guide gives for counting stillborn mutants
  apart: folding it into the kills inflates a score with cases that decided something
  else.
- **Survived.** The oracle accepted a constructed violation. This is the finding.
- **Stillborn.** No mutant was emitted, or the replay reached no verdict within its work
  budget. It decides nothing about the oracle, and each one carries its reason.

## The weakened control

A sweep reporting no survivor is consistent with two very different situations: an
oracle that refuses every constructed violation, and an oracle that refuses nothing that
these operators happen to build. The run separates them. `dropping` returns the checker
with one clause's findings discarded, which is exactly that clause not deciding, and the
receipt requires that removing the alignment clause leaves survivors for the operator
targeting alignment and for no other. The complete sweep beside it is the restored run.
The control therefore measures the sweep against a checker already known to be weak; it
is a check on the instrument, not evidence about the model.

## What a zero-survivor sweep establishes, and what it does not

It establishes that within the declared finite model, the checker refused every
violation these operators constructed, at every site they were applied to, on the
declared witnesses and one generated family. That is a statement about constructed
defects and about this checker.

It establishes nothing about constraints outside that model. CHERI bounds
representability, island and bank assignment, and admission are not modeled here, so no
operator constructs a violation of them and no verdict reports on them. It is not a
theorem: it is bounded executable evidence over the sites sampled by the run's seed, and
a site the sweep did not reach decided nothing. A stillborn population is not coverage,
and the operators are chosen, so a constraint nobody wrote an operator for remains
exactly as unmeasured as it was. The sweep also says nothing about the replay verifier's
own clauses beyond the refusals these mutants provoke.

The sweep is a research tool over the research oracle. It reads no plan, writes no plan
and calls no admission predicate; the
[placement-search admission predicates](placement-search.md) remain the separate
artifact they were.

## Replay

```console
python tools/run.py static-memory mutants --json
python tools/run.py test --only static_memory_mutants
```

The receipt records the seed, the site cap, the work budget and the contracts swept,
then the counts per operator and per site class, every survivor and every miskill in
full with its contract, site and the findings received, and the aggregated stillborn
reasons. It separates the two deliverables the agenda distinguishes: a feasibility
certificate is one candidate against an unchanged contract, and an optimality
certificate additionally carries a bound argument, so a refused witness and a false
bound are different findings with different operators. The command exits nonzero when
any survivor exists.

The focused tests construct every placement operator's mutant on a hand-written contract
and decide it again with a byte-at-a-time and tick-at-a-time oracle that shares no
interval arithmetic with the checker, fix the exact verdict of every operator on a
two-slot contract, run the weakening control in both directions, and hold the sampling
reproducible under its seed.
