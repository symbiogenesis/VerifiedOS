# Static-memory mode families: three models, three checkers

> Non-normative host research. The [requirements register](../requirements-register.md)
> remains authoritative and controls admission. Nothing here is an admission input,
> a requirement, or a change to one; a research output confers no landing credit and
> accepts no requirement. The families below are declared synthetic contracts in
> their own byte and time units, not a measured workload or a product roster.

The [research agenda](../background/static-memory-research.md) states that a
capacity result must say which problem it optimizes: one known trace, a
conservative interference relation over all admitted executions, or a finite
family of checked bindings. The [baseline](static-memory-baseline.md) settles the
single-trace case and records the witness in which one layout across modes costs
more than each mode's own peak. The [experiment contract](static-memory-experiments.md)
already says that two modes solved independently do not give one layout, and that
a global-mode relation or an admitted family of bindings is a separate input and a
separate proof obligation.

This artifact makes those three models executable and comparable on one declared
input. The [mode-family module](../../tools/vos/static_memory_modes.py) owns the
contract, the three computations and their checkers; the
[placement oracle](../../tools/vos/static_memory.py) keeps the single-trace
checker, exact search and optimality replay it already owns.

## Replay and receipt

Run from the host checkout:

```console
python tools/run.py static-memory modes --json
python tools/run.py test --only static_memory_modes
```

The action takes the declared fixtures and refuses `--case`, `--contract` and
`--candidate`, like the other research actions. The outer receipt binds the Git
revision, the working-tree dirty flag and the source bytes of this document and
its module; the inner `static-memory-modes-v1` block carries each contract, its
digest, the three models, their checker findings and the open obligations. Spans,
node counts and certificates live in that receipt and are not restated here.

A contract digest binds every parsed field. Each mode is hashed through the
placement contract's own case hash; the wrapper adds what a single trace cannot
carry, which is the identity set, the switch rule and its transitions.

## The mode-family contract

A mode family declares arenas as the corpus does, one set of object identities,
a finite set of admitted modes, and one binding declaration. Parsing is strict at
every level: exact field sets, no unknown keys, no missing ones. Object, arena and
lifetime rules are not restated here; each mode is handed to the placement
contract's own parser, which owns the lifecycle ordering, the payload bound, the
alignment and the arena membership.

- An **identity** has an arena, a charged extent, a payload subextent and an
  alignment. It has no base: placement chooses bases, and the declaration does not.
- A **mode** lists one lifetime per identity it activates, with the same five
  ordered milestones the baseline states. An identity the mode does not list is
  **dead there**, and contributes no interference to that mode.
- An identity no mode activates is refused rather than carried. The declared mode
  set is the whole admitted set in this model, so such an identity would make the
  family's charge a claim about nothing.
- A **transition** names the mode being left and the mode being entered, the
  instant on each side, and the identities it retains across the switch.
- The **rule** is `dead-at-switch`, which retains nothing and requires that nothing
  is live at either instant, or `retained-bases-equal`, which requires the live set
  at each instant to be exactly the retained set and those identities to keep one
  base on both sides.

The switch instants, the retained set and the lifetimes are supplied assumptions
about a composed schedule, exactly as the single-trace milestones are. Checking
them decides whether the family's own claim is internally consistent. It decides
nothing about a real barrier: R-08-015's temporal-safety discipline at a slot's
reuse points, which composes the containment barrier with the complete reuse gate,
is owed by whatever would implement a switch, and this tool does not discharge it.

## The three models and what each answers

Each model chooses one base per **variable**, and the models differ only in what a
variable is. The conservative model is the fully retained limit, where every
mode's copy of an identity is one base; the per-mode model is the fully dead one,
where no copy binds another; the binding family lies between them, and the
declared transitions decide where.

| Model | The question it answers | The certificate it carries |
| --- | --- | --- |
| Per-mode optimum | What each admitted mode costs when its layout binds nothing else | The existing exact oracle's own receipt per mode, with its independent optimality replay |
| Conservative interference graph | What one immutable layout valid in every admitted mode costs | A pairwise checker over the recomputed all-mode relation, a second reading mode by mode, and a Cartesian replay that refuses every shorter layout |
| Finite binding family | What one checked layout per mode costs, and what makes the family valid | Each mode's layout through the single-trace checker, the switch rule, the retained-base equalities, and the same Cartesian replay |

The per-mode charge is the maximum over modes of that mode's optimal span, taken
inside an arena and never summed across arenas. It is a lower bound no single
layout can beat rather than a cost a single layout attains.

The conservative relation joins two identities that overlap in **any** admitted
mode. It is a union of interval relations and need not be an interval relation
itself, so the search over it is a graph search and not an interval one: no
interval-only ordering, stack or sweep decides it. The receipt carries a bounded
search for an induced cycle of length four or more. Interval graphs are chordal,
a classical characterization used here as a premise and not proved here, so such a
cycle witnesses that the relation has no interval model. Finding none decides
nothing in the other direction, because the search is bounded and a chordal graph
need not be an interval graph either.

The binding family charges the maximum over modes of its per-mode spans. It is
admitted only when the declared rule holds at every declared instant; a family
claiming per-mode layouts while an identity is live at a switch it does not retain
is refused, and the findings name the identity, the mode and the instant.

## What the comparison decides, and what it does not

In every arena the three charges are ordered: the per-mode charge is at most the
binding family's, which is at most one conservative layout's. The reason is
elementary and is the receipt's own check rather than a theorem this artifact
proves: a binding family's layout for one mode is a legal layout for that mode,
and one conservative layout repeated in every mode is a binding family.

What the comparison decides is what each model costs on a declared family, once an
artifact says which model it supplies. What it does not decide is which model an
admitted artifact supplies. That is the compiler's or the composition exporter's,
and it is exactly the question the agenda leaves open. In particular R-08-018a's
rule is unchanged: non-co-occurrence is
admitted only where the admitted frame or the region structure proves it, never
from a measured or assumed correlation, and a declared mode family in this tool is
neither of those premises. A family that parses here is a research input, not an
admission input, and its declared modes are not evidence that the admitted frame
separates anything.

Nor does the comparison bear on R-08-018's pool: that entry's degenerate
interference graph of mutually live cells is one mode's structure, and the models
here concern several modes over fixed identities.
Generic reusable slots with checked binding change the fixed-identity premise the
baseline's witness states, and would need their own binding proof.

## The declared witnesses

Each family is checked against what it is a witness of, so a receipt that stops
exhibiting the separation it was built for is a finding rather than a quiet pass.

- **Pairwise modes.** Three unit identities and three modes, each activating one
  pair and never the third identity. This is the baseline's multi-execution
  witness. Every pair coexists in some mode, so one layout must separate all three
  identities while no mode's own peak requires it; nothing is live at the declared
  switches, so the binding family recovers the per-mode charge.
- **Induced five-cycle.** Five unit identities and five modes activating the
  consecutive pairs of a ring. The conservative relation is a chordless cycle, so
  it has no interval model, and its optimum exceeds every per-mode optimum. This is
  the family an interval-only search would answer wrongly.
- **Retained cycle.** Three identities and three modes, with one identity retained
  across each of three switches, so that the retained bases compose around the
  cycle. Each mode's own optimum is unchanged, and the binding family is forced
  back up to the one-layout charge. Retention is what removes the binding family's
  advantage, not the number of modes.
- **Live identity at a switch.** The pairwise family with its switch instants moved
  inside the lifetimes. The binding family is refused, carries no charge, and names
  the live identities. A refusal is a result here, not an error.

## Checkers, mutations and tests

No search is trusted. The conservative witness is read twice: once by a pairwise
checker that recomputes the all-mode relation from the declared lifetimes and
shares no conflict predicate, ordering or adjacency with the search, and once mode
by mode through the existing single-trace checker. The two readings must return
the same verdict. The binding family's per-mode legality is the single-trace
checker's; the switch rule and the retained equalities are checked separately,
because they are the only part that makes a family of layouts one claim.

An optimality claim additionally carries either equality with the independently
computed charged load or a Cartesian replay that builds every whole layout one
unit shorter and hands it to the independent checker. The replay calls neither the
search's ordering, its pruning nor its conflict test. An exhausted budget reports
`incomplete`: it leaves the claim unchecked and never refutes it, and it is never
infeasibility.

The [focused tests](../../tools/tests/test_static_memory_modes.py) compare the
bounded exact search with an independent enumeration of every legal base tuple
over all small graphs on four vertices, in two size families, and check that the
relation the family induces is exactly the declared edge set. They mutate the
checker's inputs so that a layout overlapping in one mode, which a checker reading
only the first mode accepts, is caught by both readings; they exercise the
switch-rule refusals, a retained identity that moves across a switch, a retained
identity that is dead at its own instant, and the parse refusals; and they check
that the graph search at the per-mode limit agrees with the single-trace oracle
and that a cutoff never becomes a verdict. These are executable checks of finite
instances, not a machine-checked general proof.

## What remains open

The searches enumerate aligned integer bases, which is knowingly pseudopolynomial
in the numerical height and says nothing about parameterized complexity; the
conservative model is a colouring problem and this artifact proves no hardness or
approximation result for it. A declared mode set is not evidence that it is the
admitted set, nor that each mode's reservation intervals cover every execution
that mode admits; that bridge is the compiler's, and the baseline states it. The
switch rule is a premise and not an implemented barrier. Full CHERI
representability, bank, owner and pinning constraints stay outside the model, as
they do for the rest of this corpus.
