# Documentation

Start with the [specification](spec.md) for the design and its rationale. The
[requirements register](requirements-register.md) states the normative obligations
and acceptance criteria; it takes precedence over every companion document.

Companions are grouped by subject. Filenames describe the artifact; the language
strategy, core design and workflow contract share the `languages/` directory.

| Subject | Documents |
| --- | --- |
| Languages and compilation | [Verification strategy](languages/verification-strategy.md), [core design](languages/core-design.md), [assurance presets](languages/assurance-profiles.md), [workflow contract](languages/workflow-contract.md), [compiler routes](languages/compiler-route-contract.md), [typed assembly language](languages/typed-assembly-language.md), [IDL profile](languages/idl-profile.md) |
| Hardware and ISA | [ISA profile](hardware/isa-profile.md), [absence contract](hardware/absence-contract.md), [CHERI foundations](hardware/cheri-foundation-map.md), [CHERI versions](hardware/cheri-version-matrix.md), [RTL re-parameterization](hardware/rtl-reparameterization-delta.md), [block geometry](hardware/block-geometry-constraint.md), [bank counts](hardware/bank-count-dse-contract.md), [second-class memory macros](hardware/second-class-macro-architecture.md), [immutable module contract](hardware/immutable-module-contract.md), [ensemble link](hardware/ensemble-link-contract.md), [TRNG source model](hardware/trng-source-model-contract.md), [protected-sequence fault model](hardware/protected-sequence-fault-model.md) |
| Assurance and review | [Reviewer onramp](assurance/reviewer-onramp.md), [crown jewels](assurance/crown-jewels.md), [coverage matrix](assurance/coverage-matrix.md), [field bindings](assurance/field-bindings.md), [differential corpus](assurance/differential-corpus.md), [RTL co-simulation harness](assurance/rtl-cosimulation-harness.md), [revocation qualification](assurance/revocation-qualification.md), [witness policy](assurance/witness-policy-qualification.md), [session binding](assurance/session-binding-qualification.md), [RTL correspondence boundary](assurance/rtl-correspondence-boundary.md), [findings register](assurance/findings-register.md), [proof reuse inventory](assurance/proof-reuse.md) and its [subject records](assurance/proof-reuse/), [bearing record](assurance/proof-reuse-bearing.md), [unassigned proof map](assurance/unassigned-proof-map.md) |
| Implementation and qualification | [Implementation checklist](implementation/implementation-checklist.md), [completion log](implementation/completion-log.md), [compiler assembly comparison](implementation/comparisons/compiler-assembly.md), [purecap ABI contract](implementation/contracts/purecap-abi.md), [compiler prerequisite qualification](implementation/contracts/compiler-prerequisites.md), [compiler kind handoff](implementation/contracts/compiler-kind-handoff.md), [source-value contract](implementation/contracts/compiler-source-values.md), [preserved-kind interface](implementation/contracts/compiler-kind-interface.md), [replay record](implementation/contracts/replay-record.md), [freeze measurements](implementation/contracts/freeze-measurement.md), [placement search](implementation/placement-search.md), [storage index comparison](implementation/comparisons/storage-index.md), [package-layer comparison](implementation/comparisons/package-layer.md), [product gate](implementation/contracts/product-gate.md), [userspace porting](implementation/userspace-porting.md) |
| Performance | [Performance estimates](performance/performance-estimates.md), [inference demand](performance/inference-demand.md) and its [measurement artifacts](performance/inference-demand/), [ensemble sharding traffic](performance/ensemble-sharding-traffic.md) and its [derived artifacts](performance/ensemble-sharding-traffic/), [toolchain residency](performance/toolchain-residency.md) and its [measurement artifacts](performance/toolchain-residency/) |
| Background and design assessment | [Inspirations and prior art](background/inspirations.md), [architectural alternatives](background/architectural-alternatives.md), [critique](background/critique.md), [static-memory research agenda](background/static-memory-research.md), [mathematical open problems and recent results](background/open-math-conjectures.md) |

The [web application pilot contract](implementation/contracts/web-application-profile.md)
freezes the hosted/packaged subset, bridge lifecycle, budgets and qualification
thresholds before the deferred browser pilots are implemented.

The [workflow profile and hibernation contract](implementation/workflow-profiles.md)
records preset recipes, slate-slot reuse, transition admission and the source-backed
revocation decision; Q32 owns its formalization and qualification.
The [finite workflow formal contract](implementation/contracts/workflow-formal.md)
states the lifecycle model's machine, storage and timing premises and the
interfaces its runtime consumers must discharge.

The first release is a general-purpose laptop ([R-18-004a](spec.md#r-18-004a)).
Its desktop applications run in an elastic domain: a composition-fixed envelope
inside which apps launch at runtime, share time by a verified proportional-share
dispatch and grow their heaps from a revocation-gated pool, while the fixed tier
keeps the static discipline ([§7](spec.md#r-07-037e), [§8](spec.md#r-08-047a)).
The [elastic-domain contract](implementation/contracts/elastic-domain.md) is crown-jewel
row 31 and Q34 in the
[implementation checklist](implementation/implementation-checklist.md) owns it; the
[architectural alternatives](background/architectural-alternatives.md#a-general-purpose-desktop-on-a-static-machine-an-elastic-domain-inside-a-fixed-envelope-adopted-for-the-laptop)
record what the variant trades and what it declines.

The [compute compatibility contract](implementation/compute-compatibility.md) records
the OpenCL/SPIR-V and HIP source/API path, the Vulkan SC-shaped graphics
surface that path can carry with its start-froms, standards and prior-art
evidence, unchanged admission guarantees and Q30 qualification predicates.
Its [feature map](implementation/compute-feature-map.md),
[semantic contract](implementation/contracts/compute-semantic.md) and
[upstream review](implementation/compute-upstream-review.md) freeze the pilot
subset, numerical references, resource boundaries and candidate source readings.

The [host replay envelope](implementation/contracts/host-replay-envelope.md)
authenticates bounded development artifacts under an independent host key;
operational machine recording, production sealing and replay remain separate work.

The [matrix margin contract](implementation/contracts/matrix-margin.md) defines
the M-class comparison and its strongest-RVV denominator before instruction admission.

The full-language design has dossiers for the [graded foundation](languages/graded-foundation.md),
[handlers and async lifecycles](languages/handlers-async.md), and
[interior mutability](languages/interior-mutability.md). Their
[composition review](languages/full-language-review.md) records the combined
client and the implementation and admission decisions still owed at Q25d, while
the [assurance presets](languages/assurance-profiles.md) state the policy those
rules are selected under: which claims a build must establish, what an
unestablished claim may be used for, and what the build reports about each.

The [static-memory experiments](implementation/static-memory/experiments.md) join
the [mathematical baseline](implementation/static-memory/baseline.md) and
[synthetic capacity corpus](implementation/static-memory/corpus.md) to replayable
byte accounting and bounded placement comparisons, the corpus recording which
research families its witnesses cover and which composed-roster input is still
absent. The [artifact inventory](implementation/static-memory/artifact.md) indexes the
experiments, classifications and replay commands, including service transformations,
reclamation, modes, representability, structural algorithms, phases and lending.
The [compiled census](implementation/static-memory/census.md) supplies a plain-RV64
proxy, while the [laminar theorem](implementation/static-memory/baseline.md#mechanized-statement)
and [functional service equivalence](implementation/static-memory/transformations.md#mechanized-equivalence)
have separate Rocq proofs with their implementation bridges stated as remaining work.

The [portable memory planner](implementation/portable-memory-planner.md) exposes
checked fixed-instance placement, retained baselines, pinned framework adapters
and bounded contract extraction for desktop and embedded components.
The [static-memory literature adoption map](implementation/static-memory/literature.md)
connects allocation and reusable-capacity research to the pinned candidate and
certificate integrations, finite resource contracts and remaining proof obligations.

The implementation interfaces are recorded in the
[service authoring contracts](implementation/contracts/service-authoring.md),
[object transactor contract](implementation/contracts/object-transactor.md),
[recovery policy input](implementation/storage-recovery-policy.md),
[attested TLS protocol](implementation/attested-tls-protocol.md),
[compatibility workflow](implementation/contracts/compatibility.md),
[application-host contract](implementation/contracts/application-host.md) for
Wasm bundle validation, binding, replacement and performance qualification,
[Wasm execution contract](implementation/contracts/wasm-execution.md) for
the researched execution profile, proof obligations and optimization comparisons,
[entropy observer](implementation/contracts/entropy-observer.md), and
[store-buffer comparison](implementation/comparisons/store-buffer.md).
Its [executable prerequisite contract](implementation/phase-service/prerequisite-contract.md)
covers schedule extraction, completion and quiescent drain, and workload cost
arithmetic while target qualification remains open.
The [boundary admission contract](implementation/phase-service/boundary-contract.md)
resolves the second-class baseline and the complete timer residency that the
cyclic executive must charge alongside platform and context costs.
The [stalled-transition contract](implementation/phase-service/stall-contract.md)
specifies the instrument that bounds a candidate waiting at issue over declared
per-hart programs, and the [mode-transition extension](implementation/phase-service/mode-contract.md)
extends the finite phase model to declared global modes and their transitions;
both leave target qualification open.
The [roster measurement contract](implementation/contracts/roster-measurement.md)
fixes the allocation-churn and ring-accounting analyzers' inputs and limits;
the accepted composed roster supplies the eventual target measurements.
The [roster and boot-recipe contract](implementation/contracts/boot-roster.md)
names that roster's members, owners and handoffs, and fixes the image recipe and the
console and event digests M7.1's boot harness computes.
The [boot-handoff contract](implementation/contracts/boot-handoff.md) fixes the measured
release, the boot image header, and the kernel-entry state and handoff record the
[kernel instance](../kernel/README.md) consumes.

Hardware qualification preparation includes the
[memory topology comparison](hardware/memory-topology-comparison.md),
[remanence decision](hardware/remanence-threat-decision.md),
[macro protocol](hardware/macro-qualification-protocol.md),
[sensitive-state lifetime protocol](hardware/sensitive-state-lifetime-protocol.md),
[scalar staging contract](hardware/scalar-width-transform-contract.md),
[scalar core port contract](hardware/core-port-contract.md),
[platform device contracts](hardware/platform-device-contracts.md), and
[module admission candidate](hardware/immutable-module-admission.md).
The [post-quantum reference contract](assurance/pq-reference-contract.md) fixes
the shared arithmetic and scheme campaign boundaries; the
[probing model contract](assurance/probing-model-contract.md) separates finite
algebra and circuit-model results from probability-library and physical qualification.
The [AES-GCM premise dossier](assurance/aes-gcm-premise-dossier.md) binds one
storage-authentication claim to its game, model and key/nonce assumptions,
with a finite oracle counterexample and a stored-secret horizon review.
The [security policy candidate](assurance/security-policy-model.md) and
[opening hardening obligations](assurance/hardening-opening-obligations.md)
state their remaining implementation and proof premises. The
[ternary static demand](performance/ternary-static-demand.md) and
[prompt-processing term](performance/prompt-processing-term.md) keep measured
bytes distinct from the target rate still owed.
The [BITCOS assessment](performance/bitcos-assessment.md) proposes RVV unpacking
and a comparison against the existing ternary baseline, with representation
overhead, aligned sign reads and fixed-grant target evidence included.
The [Bonsai 2 assessment](performance/bonsai2-assessment.md) adds the newer
27B candidate and a conditional post-training experiment, with rotation,
hybrid-state, licensing and useful-answer quality requirements.

The [tool guide](../tools/README.md) describes the checkers and build commands.
[Working rules](../AGENTS.md) describe document maintenance and review.
The [portable proof workflow](assurance/proof-assistance.md) documents local example
retrieval, bounded repair checkpoints and the unchanged proof-acceptance boundary.
The [portable Sail workflow](assurance/sail-assistance.md) exposes compiler-produced
context, a bounded edit loop, and the upstream LSP and modular-emulator decisions.

The independent prerequisite batch adds a [schedule record](implementation/contracts/schedule-record.md),
[device-register declarations](implementation/contracts/device-registers.md),
[wire-format inventory](assurance/wire-format-inventory.md) and
[calibration field classes](hardware/calibration-manifest.md). Their acceptance and remaining
consumer dependencies are recorded under S31 in the [implementation checklist](implementation/implementation-checklist.md).

## Specification and companions

The normative design lives in [spec.md](spec.md), with non-normative companions covering [prior art](background/inspirations.md), [evaluated architectural alternatives](background/architectural-alternatives.md), an [implementation plan and execution checklist](implementation/implementation-checklist.md), and [performance estimates](performance/performance-estimates.md).

The [proof reuse inventory](assurance/proof-reuse.md) records established proof sources, their authors and licences, and their fit to the project's completed and remaining proof work.


## The typed assembly language

The [typed assembly language](languages/typed-assembly-language.md), the typed machine-code language and per-install check that binaries are admitted with, is specified as a standalone project rather than a component: it depends on a machine semantics and a type theory and nothing else, so its correctness argument mentions no operating system. This platform pins a version of its `cheri-rv64` instantiation, which the corpus calls CHERI-TAL.


## The atomic-requirements register

The [atomic-requirements register](requirements-register.md) is the artifact that the specification's [independent-review release gate](spec.md#r-05-150) audits: every normative obligation as a numbered requirement with an acceptance criterion, traced to the crown-jewel spec it constrains and to the prose as rationale. It covers all eighteen normative sections as 1499 numbered requirements.

Its standing output is the extraction-defect list: normative claims that resist atomic restatement, which that gate treats as prose defects to repair rather than register omissions to work around. That list is empty, but the register declines to read emptiness as a clean bill: the sweep for such claims has not been asked exhaustively, so further instances are assumed present rather than absent.


## Derived views

Nine **derived views** collect what the register states across many entries but no document held:

- **The [frozen instruction-set profile](hardware/isa-profile.md)**: the single enumeration of the ISA, covering base, adopted extensions, exclusions with their grounds, the CHERI feature set, per-class datapath parameters, and the timing contracts. It carries a third disposition beside adopted and excluded: a **standing adoption** is an extension the profile has already decided it would take, still waiting on the standards body to ratify it, so the decision is on the page while the machine carries none of it. The schedule root and first day-one deliverable of the spec's [realization plan](spec.md#18-realization) consume it.
- **The [microarchitectural absence contract](hardware/absence-contract.md)**: twenty-three enumerated absences with the netlist evidence an auditor searches for, both discharge forms, the table-freeness rule, and the `fence.t` four-class completeness map. It is buildable on day one: the one part of the least-built layer (RTL ⊑ Sail) that does not need that layer to exist first.
- **The [crown-jewel inventory](assurance/crown-jewels.md)**: the thirty-one specifications the review gate audits, each with its `CJ-` trace target, the requirements constraining it, and whether it has been authored; plus the ten theorem targets and the specification each is proven against. It is the specification workstream's work list, and its status column is the countable form of the as-existing assurance gap.
- **The [coverage matrix](assurance/coverage-matrix.md)**: every boundary of the system against every property it must hold, one row per pair, recording the construction, the discharge mode, and the requirements it rests on. Where the [root README inventory](../README.md#bug-classes-removed-by-construction) names bug classes, this quantifies over the boundaries, so a pair discharged by nothing and booked by nothing is a failing check rather than a gap someone has to notice.
- **The [profile-freeze measurement contract](implementation/contracts/freeze-measurement.md)**: the corpus, recipe, provenance schema, region classes, thresholds, report columns, and CI predicates for the freeze's second act, the one place the profile defers its own decisions to a measurement against generated output. It is written before the backend that produces that output exists, which is the point: a threshold chosen after the measurement is not a threshold.

- **The [welded block-size constraint](hardware/block-geometry-constraint.md)**: the one size four instructions share, the closed list of what constrains it, and which of those constraints can be worked out today against which are owed to a chip that does not exist yet. It names no size, on purpose: the point is that the block has to suit the fast memory and the dense memory at once, and picking a size that suits only the fast one would look exactly like picking a size that suits both.

- **The [bank-count exploration contract](hardware/bank-count-dse-contract.md)**: how the dense memory is divided into independently addressed banks, which is a trade between how much data a bank can deliver at once and how much current the chip draws when several wake together. It names the seven quantities the choice turns on and records that six of them have no value yet, three of those waiting on a measured chip and three on artifacts this programme has still to build, so what it publishes today is the shape of the answer and an explicit refusal to pick one.

- **The [second-class macro architecture](hardware/second-class-macro-architecture.md)**: what the dense memory's five stated properties make its memory macro look like, from the stacked decks down to what one row holds, and what one measurement has to return for each part before the chip is real. It states no figure, on purpose: every density, latency, retention and current figure is named as a quantity to be measured on a repaired macro, so the document can be measured against without ever having been able to stand in for the measurement.

- **The [TRNG source-model contract](hardware/trng-source-model-contract.md)**: what a supplier has to say about a random-number source before this machine will trust it, the schema that submission is checked against, the review that reads it, and how the number of samples the boot tests run over would be worked out from it. It states no figure either: all but two rows of its schema are unfilled, and what holds them is a TRNG nobody has selected rather than a part nobody has fabricated, with two rows owed instead to decisions the register can still take on its own. What it publishes is the question and a refusal to answer it early.

Every row cites its governing requirement, and each view is defective, never authoritative, where it disagrees with the register. Traces cite the prose by the `<a id="r-ss-nnn">` bookmark a requirement's own number derives rather than by line number, so editing the prose moves the target with the text, and neither those references nor any figure these documents assert is maintained by hand.

Proof tooling has a [qualification contract](assurance/proof-qualification-contract.md)
and an [executed comparison](assurance/proof-tooling-qualification.md).
The [CIC checker qualification](assurance/cic-checker-qualification.md) records its
missing premises, [staged bounded foundation route](assurance/cic-checker-qualification.md#bounded-foundation-execution-route)
and bounded refinement endpoint, with [literature starting points](assurance/proof-reuse/languages.md#bounded-cic-starting-points)
for conversion soundness, partial checking and guarded recursion. The
[Fiat emission record](implementation/fiat-crypto-emission.md) binds the incorporated
field headers to their actual generator run and replay checks.
