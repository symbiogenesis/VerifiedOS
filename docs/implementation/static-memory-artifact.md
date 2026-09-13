# The static-memory research artifact

> Non-normative research inventory for the [static-memory agenda](../background/static-memory-research.md).
> The [requirements register](../requirements-register.md) remains authoritative. Research
> outputs confer no implementation landing credit and accept no requirement. Nothing here
> qualifies a hardware service rate, a product roster or a target measurement.

The artifact is the set of definitions, proofs, generators, witnesses, checker inputs,
search settings and replayable receipts this repository already carries for the
static-memory research. It is local: every part is a tracked file, every action runs on
the host, and no part of it has been published, reviewed outside this repository or
measured on a product.

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

The agenda names four classes: a peer-reviewed result cited, a preprint cited, a new
conjecture, and a measured outcome. This table adds two. **Bounded executable evidence**
separates a replayed finite check from both a proof and a measurement: a finite
enumeration that refuses a candidate decides that instance and nothing beyond the
declared model. **An elementary argument in prose** is what the baseline's laminar
theorem is, a hand proof that is neither published nor machine-checked, and without its
own name it would have to borrow one of the other five.

The classes are assigned by reading each document, not by parsing its prose. The manifest
checks only that the join is complete in both directions, so a document a sibling
experiment adds is a finding here until somebody reads it and gives it a row.

| Document | Result classes | Where each class sits |
| --- | --- | --- |
| [Research agenda](../background/static-memory-research.md) | peer-reviewed result cited; preprint cited; new conjecture | The offline-placement separation, the region calculus, the region and resource-type language results, the rematerialization formulation and the two reallocation comparators are published papers, cited for their own models. The joint tensor optimizer, the large-instance planner and the request-fragmentation submission are preprints, each named as such at its citation. The hypotheses, the open proof problem and the open tradeoff are this repository's conjectures and are not claims made by any cited author. No percentage from any cited paper is transferred |
| [Mathematical baseline](static-memory-baseline.md) | elementary argument in prose; bounded executable evidence | The laminar special case, its construction, feasibility and span arguments, and the lower-bound inequalities are hand proofs stated in prose. The replayed constructor, the independent byte oracle, the alignment counterexample and the bounded deletion witnesses are executable evidence over finite declared instances |
| [Capacity corpus and byte ledger](static-memory-corpus.md) | bounded executable evidence | The synthetic contracts, the event timeline, the disjoint byte partition and the request diagnoses are replayed on declared witness premises. The bridge to the existing exporter reports the fields that artifact omits rather than supplying them |
| [Replay guide and exact oracle](static-memory-experiments.md) | bounded executable evidence; measured outcome | The bounded exact search, its lower bounds and the independent optimality replay are executable evidence inside the declared integer model. Search elapsed time is a host measurement, and the receipt marks it as a varying one rather than as solver evidence |
| [Service transformations](static-memory-transformations.md) | bounded executable evidence | The emitted bounded service, its independent output check and the reported reservations are replayed. Executed operation and traffic counts are synthetic units of the interpreter's own model, not target cycles, bytes moved on a bus or energy |
| [Reclamation scheduling](static-memory-reclamation.md) | bounded executable evidence | The fixed synthetic calendars, the byte timelines, the comparison across schedules and the authority-barrier refusals are replayed under explicit premises. No sweep rate, holder map or service guarantee here is qualified for a target |
| [Planning scale](static-memory-scaling.md) | bounded executable evidence; measured outcome | The generated families, the checked heuristics, the bounded exact search and the preserved witness comparison are executable evidence. Host build and search times are measurements of this machine and of nothing else |
| [This artifact inventory](static-memory-artifact.md) | bounded executable evidence | The manifest receipt is a computed inventory of tracked files and registered actions, replayable from the tree it reads. The classification above is a reading, and the manifest holds only its completeness |

## What publication would additionally need

The agenda's publication item is not closed by a complete local inventory. What remains
is stated here so that a green manifest is never read as the item's answer:

| Owed | Why the artifact cannot supply it |
| --- | --- |
| External review of the definitions, the prose proofs and the generators | Every argument here is this repository's own reading; no result in the artifact has been refereed |
| A mechanized theorem for each argument stated in prose | The laminar case, the lower bounds and the deletion argument are hand proofs; the executable checks are finite instances of them, not proofs of the general statement |
| Incorporation of any new dependency with its licence read at that milestone | The experiments deliberately depend on nothing new. A solver, a planner or a corpus taken from a cited work is an incorporation, and its terms are read from its own licence file at the milestone that would take it, never at release |
| A measured product comparison | The roster, the compiled service contracts and the qualified resource inputs the composition comparison needs are absent, so no admitted-workload gain is claimed. Synthetic units and host times are not a product measurement |
| A disposition for each register claim the research touches | A register change is proposed only with the precise theorem or measured contract that replaces the current claim, through the register's own gate. An inconclusive experiment leaves its item open |
