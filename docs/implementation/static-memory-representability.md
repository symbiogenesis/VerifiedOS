# Representable placement in the static-memory research oracle

> Non-normative host research. The [requirements register](../requirements-register.md)
> remains authoritative and decides admission; this document confers no landing credit,
> accepts no requirement, and admits nothing. It states one constraint of the frozen
> capability format, the part of the research placement model that now carries it, and
> the parts that still do not.

[The research agenda](../background/static-memory-research.md)'s exact small-instance
oracle records that full CHERI placement constraints stay outside its declared finite
integer model, and [the experiment contract](static-memory-experiments.md) names
arbitrary CHERI representability among the quantities that model does not decide. The
[legal-position layer](../../tools/vos/static_memory_repr.py) closes the
representability part of that residue for the format this repository fixes. The rest of
the residue stands unchanged, and the last section of this document names each piece of
it.

## 1. The model

**A granule is derived from a charged extent, and from nothing else.** R-15-007c fixes
the precision the narrowing buys: bounds are byte-exact for objects below a stated
threshold, and from that threshold the representable region rounds outward at a
power-of-two granularity the entry bounds as a fraction of the length. The function is
R-15-007c's, ported once from [the memory plan's statement artifact](../../proofs/MemoryPlan.v)
into [memplan](../../tools/vos/memplan.py) as `representable_granule`, and this layer
calls that port rather than restating it: a change to the function moves the layer with
it, and the tests mutate the port to watch a placement that stood become refused.

**A base is a legal position exactly where the object's granule divides it.** This is
the question `base_is_quantized` asks of a region, asked of a research object: the plan
multiplies a declared granule count back, and a research contract states a base and
declares no count, so the layer divides instead. The two agree wherever the declared
count is the base's own, which the cross-check below is what establishes.

**A length its own granule does not divide has no exact bounds at any base.** That is a
different refusal, and it is reported per object rather than repaired: the layer names
the object, its granule, and the extent a quantized plan would have to charge in its
place, and leaves the contract's charged size where it stands. R-15-007k is what decides
that disposition. The entry puts the obligation on the static memory plan rather than on
an instruction, requires each object a derivation may narrow to be laid at its
representable alignment and at a granule-quantized length, and declines `CRAM`, `CRRL`,
`CSetBoundsExact` and `YAMASK`, so an outward round is a defect in the slot plan and
never a runtime event. A research oracle that silently rounded an inexact extent would
be manufacturing exactly the plan the entry says must be authored deliberately.

**The quantized extent is a fixed point rather than one division.** Rounding an extent
up can coarsen its own granule, so the layer re-derives the granule of the extent it
just produced and stops where that extent is a whole number of it. One step always
suffices at the ported granule: an extent lies in a half-open interval its granule's
threshold defines, rounding up moves it by less than one granule, and the only value
that reaches the next interval is the interval's own endpoint, which the coarser granule
divides. The loop is bounded anyway, so a mutated granule is a refusal and not a hang.

**A base-quantized placement is not yet a representable plan, so a third model is
solved beside the other two.** Quantizing the bases alone leaves an inexact extent
charged at the length its contract states, which is a length the format cannot express
as exact bounds, so the span that model reports is below what a compliant plan would
charge. The third model is the same contract with every extent grown to its own
granule, solved under the same legal-base layer, and its span is the one a plan meeting
R-15-007k has to pay. It is an artifact beside the supplied contract and never a
rewrite of it: the charged sizes stay where the contract puts them, the exact-length
refusals still name each object the growth applies to, and the receipt reports the
middle model's span and the third separately rather than merging them.

**The format's parameters are named here and read where they are declared.**
[capformat](../../tools/vos/capformat.py) resolves `cap_mantissa_width`,
`stored_mantissa_width`, `cap_E_width`, `cap_addr_width`, `cap_otype_width`,
`cap_perms_code_width`, `cap_perms_width`, `reserved_otypes`, `cap_size`,
`log2_cap_size` and `xlen` out of [the model's own declarations](../../model/model/core/cap_format.sail)
and holds every other artifact that restates one against them. Two of those parameters
are what the granule spends, the base and stored top mantissas, and the exponent field
beside them is why the quantum above the threshold is coarser than the mantissa width
alone suggests, which R-15-007c states. No figure is written down here: a width this
document spelled would be a site nothing holds.

## 2. What is now inside the oracle

[The placement oracle](../../tools/vos/static_memory.py) takes an optional legal-base
layer as a keyword, and the default asks nothing. Under the default every finding, every
node count and every receipt is the alignment-only one that stood, which is the property
the focused tests pin; the layer is a restriction that adds refusals and removes none.

| Entry point | What a supplied layer changes |
| --- | --- |
| `check_placement` | one refusal per object whose base the layer rejects, in the layer's own words, beside the alignment and capacity findings |
| `solve_exact` | the candidate bases the bounded depth-first search enumerates, counted and abandoned exactly where an overlapping base is |
| `compare_heuristics` | each first-fit endpoint walks up to the first base the layer admits, before the scan that decides overlap |
| `verify_optimality` | the independent Cartesian replay of the preceding height runs over legal bases alone |

Two of those are the ones a restriction most easily gets wrong. First fit advances its
endpoints in a separate pass rather than in place, because the scan that follows reads
one blocker cursor that only moves forward: an endpoint advanced where it stands could
fall behind the endpoint after it, and the cursor would then skip a blocker that still
ends above the smaller base. The replay is restricted for the opposite reason: its
refutation asks whether a smaller *legal* placement exists, so replaying an unrestricted
grid would refute an optimum the restriction itself forced. The replay filters only
after the work budget has admitted the grid's size, so no unbounded range is walked.

Neither claim is left to the reading. A layer that refuses nothing never advances an
endpoint, so the walk is unexercised until something is refused, and
[the focused tests](../../tools/tests/test_static_memory_repr.py) drive it with the
layer that does: an endpoint advances to the least legal base at or above it, an
endpoint whose walk leaves the arena is dropped rather than rounded into it, a budget
spent inside the walk is reported as incomplete and never as a failure to fit, and
every contract's own first-fit candidate is handed back to the independent checker
under the layer, which is what a skipped blocker would fail. The replay's half is held
by the declared fixtures whose bases move: each of their optima is replayed under the
same layer and comes back verified, where a replay over the unrestricted grid would
find the alignment-only placement one height below and refute an optimum the
restriction itself forced.

The charged live load stays the bound it was. A restriction of the legal positions
cannot lower the bytes that are simultaneously live, so a span that still attains the
load is still optimal, and the load-equality certificate keeps its meaning on both
sides.

## 3. The lower bound under quantization, and why it is sound

The charged load is sound and weak: it ignores the positions entirely. The layer
computes a second bound that reads them, and the report prints both beside each span.

**The bound.** For one arena, for each instant, take the objects live at that instant.
Give each object a step, the spacing every legal base of it is a multiple of: its
alignment under the alignment-only model, and the least common multiple of that
alignment and its granule under this layer. Stack the live set from the arena's origin
in some order, each object at the first multiple of its own step at or above the end of
the one below it, and take the least end any order reaches. The arena's bound is the
largest such value over the instants, and never less than the charged load.

**Soundness.** Let a placement be admitted by the checker under the layer, and fix an
instant. The objects live at that instant pairwise interfere, so the checker's own
overlap rule makes their extents pairwise disjoint; order them by base. The first base
is at or above zero, and every base after it is at or above the end of its predecessor
and is a multiple of its own step, so it is at or above that end rounded up to the next
multiple of that step. Rounding up to a multiple and adding a fixed extent is
non-decreasing in its argument, so induction along the order gives that the last object's
end is at or above the end the same order reaches in the stack, which is at or above the
least end over all orders. The arena's span is at or above that last end. The instant was
arbitrary, so the maximum over instants is a lower bound too.

**Why the least end over orders is computed by a subset walk.** Among the orders ending
with a given object, the end is that object's extent above its predecessors' end rounded
up to its step, and that map is non-decreasing, so the best such order is the best order
of the remaining set followed by that object. The recurrence over subsets is therefore
exact for the minimum over orders, and the exponential work is in the size of one live
set rather than in the arena.

**Why only start times are examined.** Every live set is contained in the live set at
the latest start among its members, and deleting a member from a stack never raises the
end it reaches, so the value at that start is at or above the value at the instant in
question. Where a live set is larger than the walk will take, that instant contributes
the charged load instead, which is a lower bound on its own; leaving an instant out
weakens the bound and cannot make it unsound.

**What it buys, and what it is not.** A span equal to the bound is optimal for that
arena under that layer, needing no exhaustive search and no enumeration certificate.
That is a statement about the arithmetic and not a description of the tool: **the search
does not read the bound**. Every certificate the receipt carries is the one that stood,
load equality or exhaustion at the height below, and no arena is settled by the bound.
What the bound does in the receipt is stand beside each span, so a reader sees which
spans it would settle, and be compared against it, so an unsound bound fails the run:
a bound above a span an exhaustive search reached is a defect in the bound and not a
result about the layout, and [the report](../../tools/vos/static_memory_repr.py) makes
that comparison for every arena it finishes.

The bound is not an algorithm for the optimum and not a theorem about placement: it is
a lower bound whose argument is stated above and whose soundness is tested rather than
proved mechanically. [The focused tests](../../tools/tests/test_static_memory_repr.py)
look for an unsound one against an independent exhaustive grid over a coarsened granule,
small instances being the only ones a grid can exhaust. That the bound is genuinely
weaker than an optimum is itself pinned rather than assumed: one declared fixture holds
it strictly below, an object living across two instants having to take a base that
serves the later instant's aligned neighbour, so the earlier instant's tightest stack is
unreachable and the arena pays for an interaction between instants that a bound reading
one instant at a time cannot see. On every other row of the receipt the two are equal,
which is an observation about instances that small and not a claim that they coincide.

## 4. The cross-check against the exported plan

Q5's own reader exports [the memory plan](placement-search.md) from the statement
artifact, and the same two questions are already decided there by
`base_is_quantized` and `length_is_quantized` over declared granule counts. For every
region of the exported standing plan the layer decides both questions its own way, and
the two verdicts must agree region by region; a disagreement is a finding about the plan
or about the layer and is reported as one, never absorbed. An export carrying no region
is a reader that has stopped reading rather than a plan that agrees about nothing, so
the cross-check refuses it outright, and refuses a region whose length is not positive
for the same reason.

Every region of the standing plan answers yes to all four questions, so agreement over
it alone would read the same way if neither side ever refused anything. What binds the
verdict to its inputs is mutation, in both directions. The focused tests replace the
granule counts the plan's own predicates multiply back, once for each predicate and
region by region, and require a disagreement naming every region; and they move one
region's base off its own granule, where both sides refuse and the cross-check has to
stay silent, which is the reading a layer that admitted every base would fail.

## 5. What stays outside

The layer reaches one rule of the format. Each of the following is untouched, and none
of them is made easier by what is here.

| Outside | Where it sits |
| --- | --- |
| island containment and the island map | `containment_ok` for R-08-012c, over a map R-15-228a makes an input to the plan; the research arenas are relative address spaces with no island structure |
| bank selection and any locality term | no field of the plan names a bank, which is [the placement search](placement-search.md)'s own recorded gap |
| the encoding's exponent range and every check derived from the mantissas | R-15-007a's representation-correctness proof and its characterization of the malformed set, over the widths `capformat` reads |
| the containment domain above the representable address space | R-15-007a's own stated domain, which is a property of the bounds algorithm and not of a slot plan |
| sealing and the permission lattice | R-15-007b's enumerated lattice, inside which R-15-007o separates `Permit_Seal` from `Permit_Unseal` and R-15-007l admits no set holding both `Permit_Store` and `Permit_Execute`, none of which a base decides anything about |
| the object-type space | frozen with the profile by R-15-007, at the width `capformat` reads as `cap_otype_width`; R-15-007n declines software-defined permission bits and leaves a software class of capability to that composition-fixed set |
| dynamic subobject narrowing under the language's own rule | R-15-007k's side condition, discharged against a real slot plan and not against a research contract |
| admission | the register and its gates; no research receipt performs one |

Two further limits are the model's rather than the format's. The research contract
charges an object's entire extent through safe reuse and supplies its milestones as
assumptions, so a placement the layer admits is not evidence about a barrier or a sweep,
and the synthetic families carry synthetic units. The bounded search reports an exhausted
budget as incomplete, which is unfinished research and never infeasibility.

## 6. Replay

Run from the host checkout:

```console
python tools/run.py static-memory repr --json
python tools/run.py test --only static_memory_repr
```

The action replays the declared witness corpus and the fixtures the layer's own
generator states, each under all three models, and emits the cross-check with them. Per
arena the receipt carries the charged load, each model's best span with its status,
certificate and independent replay verdict, the stacked bound beside each span, the part
of the difference between the alignment-only and base-quantized spans that both models
having finished makes attributable to representability, the further difference the
quantized-length model charges above the base-quantized one, and the exact-length
refusals with the extent a quantized plan would charge. A pair of models that did not
both finish reports no difference and says so, two cutoffs not being subtractable.
Figures live in the receipt; none is copied here. The receipt's own identity hashes the
revision it was run at, so it is a figure about a commit rather than about the module
and is quoted with that revision beside it or not at all.

The declared fixtures are the only cases that reach past the exactness threshold, and
the last of them stays below it deliberately, being about the lower bound rather than
about the format. Every extent in the witness corpus is below the threshold, where the
granule is one byte and the layer refuses nothing, so the receipt says of those cases
that representability costs them nothing, which is a result about that corpus and not
about a product roster.

## 7. What kind of claim each result is

- R-15-007c's granule and R-15-007k's disposition are **normative**, and the register
  owns them. Nothing here revises either, and where this document and the register
  disagree, the register wins and this document is defective.
- The port of the granule function and the memory plan's checks are **development
  hygiene** whose proof status stays with the statement artifact, exactly as
  [the placement search](placement-search.md) states for its own port.
- The soundness argument above is a **stated argument over this model**, not a machine
  checked theorem, and the exchange argument it rests on is textbook rather than novel.
- Every span, gap and refusal a run prints is a **measured outcome of a bounded search
  over declared synthetic contracts**. A feasible placement is not an optimal one, an
  optimum over a declared model is not a fact about a product, and an exhausted budget
  is not infeasibility.
- The quantized-length span is a **counterfactual over a derived contract**, stating what
  a plan that grew every extent to its granule would have to charge. It is not a plan,
  not an admission that such growth is the right disposition for any particular object,
  and not a rewrite of the contract it is derived from.
- That two models can be compared at all rests on both of them finishing. Where either
  is incomplete the receipt says so and the difference between the spans is reported as
  bounded rather than as a cost.
