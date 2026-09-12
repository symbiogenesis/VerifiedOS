# Documentation

Start with the [specification](spec.md) for the design and its rationale. The
[requirements register](requirements-register.md) states the normative obligations
and acceptance criteria; it takes precedence over every companion document.

Companions are grouped by subject. Filenames describe the artifact; the language
strategy, core design and workflow contract share the `languages/` directory.

| Subject | Documents |
| --- | --- |
| Languages and compilation | [Verification strategy](languages/verification-strategy.md), [core design](languages/core-design.md), [workflow contract](languages/workflow-contract.md), [compiler routes](languages/compiler-route-contract.md), [typed assembly language](languages/typed-assembly-language.md), [IDL profile](languages/idl-profile.md) |
| Hardware and ISA | [ISA profile](hardware/isa-profile.md), [absence contract](hardware/absence-contract.md), [CHERI foundations](hardware/cheri-foundation-map.md), [CHERI versions](hardware/cheri-version-matrix.md), [RTL re-parameterization](hardware/rtl-reparameterization-delta.md), [block geometry](hardware/block-geometry-constraint.md), [bank counts](hardware/bank-count-dse-contract.md), [second-class memory macros](hardware/second-class-macro-architecture.md) |
| Assurance and review | [Reviewer onramp](assurance/reviewer-onramp.md), [crown jewels](assurance/crown-jewels.md), [coverage matrix](assurance/coverage-matrix.md), [field bindings](assurance/field-bindings.md), [differential corpus](assurance/differential-corpus.md), [revocation qualification](assurance/revocation-qualification.md), [witness policy](assurance/witness-policy-qualification.md), [session binding](assurance/session-binding-qualification.md), [findings register](assurance/findings-register.md), [proof reuse inventory](assurance/proof-reuse.md) and its [subject records](assurance/proof-reuse/), [unassigned proof map](assurance/unassigned-proof-map.md) |
| Implementation and qualification | [Implementation checklist](implementation/implementation-checklist.md), [completion log](implementation/completion-log.md), [compiler assembly comparison](implementation/compiler-assembly-comparison.md), [purecap ABI contract](implementation/purecap-abi-contract.md), [replay record](implementation/replay-record-contract.md), [freeze measurements](implementation/freeze-measurement-contract.md), [placement search](implementation/placement-search.md), [storage index comparison](implementation/storage-index-comparison.md), [product gate](implementation/product-gate-contract.md), [userspace porting](implementation/userspace-porting.md) |
| Performance | [Performance estimates](performance/performance-estimates.md), [inference demand](performance/inference-demand.md) and its [measurement artifacts](performance/inference-demand/) |
| Background and design assessment | [Inspirations and prior art](background/inspirations.md), [architectural alternatives](background/architectural-alternatives.md), [critique](background/critique.md), [static-memory research agenda](background/static-memory-research.md) |

The [matrix margin contract](implementation/matrix-margin-contract.md) defines
the M-class comparison and its strongest-RVV denominator before instruction admission.

The [static-memory experiments](implementation/static-memory-experiments.md) join
the [mathematical baseline](implementation/static-memory-baseline.md) and
[synthetic capacity corpus](implementation/static-memory-corpus.md) to replayable
byte accounting and bounded placement comparisons.

The [tool guide](../tools/README.md) describes the checkers and build commands.
[Working rules](../AGENTS.md) describe document maintenance and review.

## Specification and companions

The normative design lives in [spec.md](spec.md), with non-normative companions covering [prior art](background/inspirations.md), [evaluated architectural alternatives](background/architectural-alternatives.md), an [implementation plan and execution checklist](implementation/implementation-checklist.md), and [performance estimates](performance/performance-estimates.md).

The [proof reuse inventory](assurance/proof-reuse.md) records established proof sources, their authors and licences, and their fit to the project's completed and remaining proof work.


## The typed assembly language

The [typed assembly language](languages/typed-assembly-language.md), the typed machine-code language and per-install check that binaries are admitted with, is specified as a standalone project rather than a component: it depends on a machine semantics and a type theory and nothing else, so its correctness argument mentions no operating system. This platform pins a version of its `cheri-rv64` instantiation, which the corpus calls CHERI-TAL.


## The atomic-requirements register

The [atomic-requirements register](requirements-register.md) is the artifact that the specification's [independent-review release gate](spec.md#r-05-150) audits: every normative obligation as a numbered requirement with an acceptance criterion, traced to the crown-jewel spec it constrains and to the prose as rationale. It covers all eighteen normative sections as 1449 numbered requirements.

Its standing output is the extraction-defect list: normative claims that resist atomic restatement, which that gate treats as prose defects to repair rather than register omissions to work around. That list is empty, but the register declines to read emptiness as a clean bill: the sweep for such claims has not been asked exhaustively, so further instances are assumed present rather than absent.


## Derived views

Eight **derived views** collect what the register states across many entries but no document held:

- **The [frozen instruction-set profile](hardware/isa-profile.md)**: the single enumeration of the ISA, covering base, adopted extensions, exclusions with their grounds, the CHERI feature set, per-class datapath parameters, and the timing contracts. It carries a third disposition beside adopted and excluded: a **standing adoption** is an extension the profile has already decided it would take, still waiting on the standards body to ratify it, so the decision is on the page while the machine carries none of it. The schedule root and first day-one deliverable of the spec's [realization plan](spec.md#18-realization) consume it.
- **The [microarchitectural absence contract](hardware/absence-contract.md)**: twenty-three enumerated absences with the netlist evidence an auditor searches for, both discharge forms, the table-freeness rule, and the `fence.t` four-class completeness map. It is buildable on day one: the one part of the least-built layer (RTL ⊑ Sail) that does not need that layer to exist first.
- **The [crown-jewel inventory](assurance/crown-jewels.md)**: the twenty-nine specifications the review gate audits, each with its `CJ-` trace target, the requirements constraining it, and whether it has been authored; plus the ten theorem targets and the specification each is proven against. It is the specification workstream's work list, and its status column is the countable form of the as-existing assurance gap.
- **The [coverage matrix](assurance/coverage-matrix.md)**: every boundary of the system against every property it must hold, one row per pair, recording the construction, the discharge mode, and the requirements it rests on. Where the [root README inventory](../README.md#bug-classes-removed-by-construction) names bug classes, this quantifies over the boundaries, so a pair discharged by nothing and booked by nothing is a failing check rather than a gap someone has to notice.
- **The [profile-freeze measurement contract](implementation/freeze-measurement-contract.md)**: the corpus, recipe, provenance schema, region classes, thresholds, report columns, and CI predicates for the freeze's second act, the one place the profile defers its own decisions to a measurement against generated output. It is written before the backend that produces that output exists, which is the point: a threshold chosen after the measurement is not a threshold.

- **The [welded block-size constraint](hardware/block-geometry-constraint.md)**: the one size four instructions share, the closed list of what constrains it, and which of those constraints can be worked out today against which are owed to a chip that does not exist yet. It names no size, on purpose: the point is that the block has to suit the fast memory and the dense memory at once, and picking a size that suits only the fast one would look exactly like picking a size that suits both.

- **The [bank-count exploration contract](hardware/bank-count-dse-contract.md)**: how the dense memory is divided into independently addressed banks, which is a trade between how much data a bank can deliver at once and how much current the chip draws when several wake together. It names the seven quantities the choice turns on and records that six of them have no value yet, three of those waiting on a measured chip and three on artifacts this programme has still to build, so what it publishes today is the shape of the answer and an explicit refusal to pick one.

- **The [second-class macro architecture](hardware/second-class-macro-architecture.md)**: what the dense memory's five stated properties make its memory macro look like, from the stacked decks down to what one row holds, and what one measurement has to return for each part before the chip is real. It states no figure, on purpose: every density, latency, retention and current figure is named as a quantity to be measured on a repaired macro, so the document can be measured against without ever having been able to stand in for the measurement.

Every row cites its governing requirement, and each view is defective, never authoritative, where it disagrees with the register. Traces cite the prose by the `<a id="r-ss-nnn">` bookmark a requirement's own number derives rather than by line number, so editing the prose moves the target with the text, and neither those references nor any figure these documents assert is maintained by hand.
