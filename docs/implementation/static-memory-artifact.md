# The static-memory research artifact

> Non-normative research inventory for the [static-memory agenda](../background/static-memory-research.md).
> The [requirements register](../requirements-register.md) remains authoritative. Research
> outputs confer no implementation landing credit and accept no requirement. Nothing here
> qualifies a hardware service rate, a product roster or a target measurement.

The artifact is the set of definitions, proofs, generators, witnesses, checker inputs,
search settings and replayable receipts this repository already carries for the
static-memory research. Every part is a tracked file. Registered research actions
run on the host; proof and lowering checks run in their guest lanes. No part has
been published, reviewed outside this repository or measured on a product.

The inventory of those parts is computed rather than written down.
[static_memory_manifest.py](../../tools/vos/static_memory_manifest.py) globs the modules,
tests, documents and proofs, reads the accepted actions and their declared source sets
from the command's own parser, hashes each file through the same `identity` function the
experiment receipts use, and reports each file's membership in the git index. A module,
document or proof a later experiment adds is inventoried the day it lands, without an
edit to this document or to that module.

## Replaying the artifact end to end

```console
python tools/run.py static-memory manifest --json
python tools/run.py static-memory manifest --replay --json
python tools/run.py test --only static_memory
```

The default run is an inventory and a completeness check; it executes no experiment. The
`--replay` run additionally runs every other accepted action at the smallest budget the
command's own tests use, and records each receipt's schema, scope sentence, reported
errors and a digest of the receipt it produced. A budget is a setting and not a result:
these replays decide whether each action still runs and what it says about its own
scope. They are not the research runs whose figures the experiment documents describe,
which use the budgets [the replay guide](static-memory-experiments.md) states.

The receipt is a `static-memory-experiment-v1` envelope, like the other research
actions, with a `static-memory-manifest-v1` body. The envelope binds the Git revision,
the working-tree dirty flag and the source hashes; the body carries the inventory, the
classification rows, any replay verdicts and the findings. A digest binds the receipt
one replay produced, and an action that records host elapsed time does not repeat that
digest between runs.

## What the completeness check decides

The command exits nonzero on any finding, and each finding names a path and the rule it
violates:

| Finding | Rule |
| --- | --- |
| An inventoried file is absent, or the git index does not carry it | Corpus membership comes from the index, as [the checker](../../tools/check.py) reads it; nothing decided about an untracked file means anything |
| A `static_memory_<topic>` module has no registered action of its topic and no document outside this index naming it | A module nobody can reach and nobody describes is not part of a replayable artifact |
| A document under `docs/implementation/static-memory-*.md` carries no Markdown link from another static-memory document and none from the research agenda | An unreachable document leaves its results outside the artifact a reader follows. A mention of the basename is not a link: a name inside a fenced command line, or in a sentence a reader cannot follow, gives nobody a way to arrive |
| A declared source of an action does not exist, or the index does not carry it | An action binds the bytes it names, so a source it cannot hash decides nothing |
| A test module has no module of its own topic | A test naming a subject the artifact does not ship is evidence about nothing |
| A proof under `proofs/StaticMemory*.v` has no row in [the proof ledger](../../tools/generated/proof-ledger.md) | The ledger is the join of the register with what the shipped proofs cite; a proof no row reaches cites no live requirement, or the ledger is owed its regeneration by `run.py check --fix` |
| A static-memory document has no classification row or more than one, a row names a document the artifact does not carry, or a row names a class outside the declared vocabulary | The table below is a completeness statement and not a derived count, so both directions of the join are held. Exactly one row and not at least one, because two rows for one document can claim class sets that contradict each other |
| A replayed action refused, or reported its own errors | An action that no longer runs is a part of the artifact that no longer replays |

The link graph has one root, and it is this document. This document is the subject of no
reachability rule, and it is the witness for none either: it is written beside the rules
and names the artifact's own parts, so the classification table below would satisfy the
document rule over anything, and one sentence of the prose above would satisfy the module
rule for a module whose action nobody registered. Every reachability finding is therefore
decided by the other documents and by the command's own registration, never by this page.

**A green manifest is inventory completeness and nothing else.** It says the parts are
present, tracked, registered, reachable and classified. It does not say that a laminar
argument is correct, that a bounded search found an optimum, that a synthetic unit
corresponds to a cycle or a byte on any machine, or that any hypothesis in the agenda
holds. Those readings belong to the documents themselves, to the register's own review
gate, and to the external review this artifact has not had.

## Result classes and where each carries them

The agenda distinguishes cited peer-reviewed results, cited preprints, new
conjectures and measured outcomes. **Bounded executable evidence** identifies finite
checks within declared inputs. **An elementary argument in prose** identifies a
human-readable proof. **A mechanized theorem** identifies a statement checked by
the guest Rocq proof gate under its explicit premises; it supplies no correspondence
to a Python implementation or emitted program unless that relation is proved too.

The classes are assigned by reading each document, not by parsing its prose. The manifest
checks only that the join is complete in both directions, so a document a sibling
experiment adds is a finding here until somebody reads it and gives it a row.

| Document | Result classes | Where each class sits |
| --- | --- | --- |
| [Research agenda](../background/static-memory-research.md) | peer-reviewed result cited; preprint cited; new conjecture | Literature is cited for its own models; the open hypotheses and product tradeoffs remain research questions |
| [Mathematical baseline](static-memory-baseline.md) | elementary argument in prose; bounded executable evidence; mechanized theorem | The prose states inequalities and a forest construction; finite witnesses test assumptions; StaticMemoryLaminar.v proves the scoped closed-form construction and a crossing-family gap |
| [Capacity corpus and byte ledger](static-memory-corpus.md) | bounded executable evidence | Synthetic contracts, event accounting and declared family coverage; absent roster inputs are reported |
| [Replay guide and exact oracle](static-memory-experiments.md) | bounded executable evidence; measured outcome | Bounded search and independent replay apply to the declared model; elapsed search time is a host measurement |
| [Service transformations](static-memory-transformations.md) | bounded executable evidence; mechanized theorem | The interpreter counts abstract work and storage; StaticMemoryService.v proves list-functional variant equivalence, with implementation refinement still open |
| [Reclamation scheduling](static-memory-reclamation.md) | bounded executable evidence | Holder signatures, fixed calendars, barrier witnesses and schedule comparisons use synthetic service inputs |
| [Planning scale](static-memory-scaling.md) | elementary argument in prose; bounded executable evidence; measured outcome | Prose establishes span lower bounds, bounded algorithms compare candidates, and host times measure the local search |
| [Mode families](static-memory-modes.md) | bounded executable evidence | Per-mode, common-layout and binding-family results hold over declared synthetic modes and switch premises |
| [Representable placement](static-memory-representability.md) | bounded executable evidence | The frozen granule rule and exported-plan predicates are cross-checked without establishing complete capability-format admission |
| [Deletion-parameter structure](static-memory-structure.md) | peer-reviewed result cited; elementary argument in prose; bounded executable evidence; mechanized theorem | Parameter, bipartite, triangle-free threshold and extent-gcd arguments are proved in prose; the gap inequality also has a mechanized proof in StaticMemoryLaminar.v; finite replay establishes the named witness's inclusion-minimality |
| [Capacity lending](static-memory-lending.md) | elementary argument in prose; bounded executable evidence | Public-policy independence arguments accompany finite two-run distinctions and counterexample calendars; no target transition is implemented |
| [Public phases](static-memory-phases.md) | bounded executable evidence; new conjecture | Finite certificate checks and minimized counterexamples motivate the stated compositional conjecture |
| [Oracle mutations](static-memory-mutants.md) | bounded executable evidence | Constructed violations and weakened-clause controls distinguish killed, miskilled, surviving and stillborn cases |
| [Retirement envelopes](static-memory-envelope.md) | elementary argument in prose; bounded executable evidence | Calendar bounds have explicit finite-adversary premises and bounded exhaustive comparisons |
| [Compiled census](static-memory-census.md) | bounded executable evidence; measured outcome | Reproducible lowering checks and emitted C and instruction counts concern a plain-RV64 proxy, with no target timing or image qualification |
| [Artifact inventory](static-memory-artifact.md) | bounded executable evidence | The manifest computes tracked files, registered actions and completeness; classification is a review judgment |

## What publication would additionally need

The agenda's publication item is not closed by a complete local inventory. What remains
is stated here so that a green manifest is never read as the item's answer:

| Owed | Why the artifact cannot supply it |
| --- | --- |
| External review of the definitions, the prose proofs and the generators | Every argument here is this repository's own reading; no result in the artifact has been refereed |
| Remaining mechanized proofs and implementation refinements | The laminar and list-functional service statements are mechanized; lower-bound and deletion arguments, source extraction and correspondence to emitted implementations still need their own proofs |
| Incorporation of any new dependency with its licence read at that milestone | The experiments deliberately depend on nothing new. A solver, a planner or a corpus taken from a cited work is an incorporation, and its terms are read from its own licence file at the milestone that would take it, never at release |
| A measured product comparison | The roster, the compiled service contracts and the qualified resource inputs the composition comparison needs are absent, so no admitted-workload gain is claimed. Synthetic units and host times are not a product measurement |
| A disposition for each further register claim the research touches | The reservation, span and interference requirements state the reconciled scope. Further changes need the precise theorem or measured contract that supports them; an inconclusive experiment leaves its item open |
