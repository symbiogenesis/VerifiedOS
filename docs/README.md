# Documentation

Use this index to find each topic's owner. The linked contracts hold the details;
implementation state and landing evidence belong in the checklist and completion log.

## Specification and companions

| Start here | Purpose |
| --- | --- |
| [Specification](spec.md) | Design and rationale |
| [Reviewer onramp](assurance/reviewer-onramp.md) | How to review the requirements and their evidence |
| [Implementation checklist](implementation/implementation-checklist.md) | Build order, acceptance predicates, estimates and execution state |
| [Completion log](implementation/completion-log.md) | Recorded landing evidence |
| [Construction inventory](../README.md#bug-classes-removed-by-construction) | Overview by bug class |

Design entry points: [release scope](spec.md#r-18-004a),
[elastic domain](spec.md#r-07-037e), [elastic memory pool](spec.md#r-08-047a),
[independent review gate](spec.md#r-05-150), and [realization plan](spec.md#18-realization).

### The atomic-requirements register

The [requirements register](requirements-register.md) owns VerifiedOS's normative
obligations, acceptance criteria, extraction coverage and extraction defects.

## Languages and compilation

| Topic | Documents |
| --- | --- |
| Language design | [Verification strategy](languages/verification-strategy.md), [core design](languages/core-design.md), [assurance presets](languages/assurance-profiles.md) |
| Workflow and routes | [Workflow contract](languages/workflow-contract.md), [compiler routes](languages/compiler-route-contract.md) |
| Language features | [Graded foundation](languages/graded-foundation.md), [handlers and async lifecycles](languages/handlers-async.md), [interior mutability](languages/interior-mutability.md), [composition review](languages/full-language-review.md) |
| Interfaces | [IDL profile](languages/idl-profile.md) |

### The typed assembly language

The [typed assembly language](languages/typed-assembly-language.md) owns the
standalone language specification and its relationship to VerifiedOS's CHERI-TAL instantiation.

## Derived views

| Document | Topic |
| --- | --- |
| [ISA profile](hardware/isa-profile.md) | Instructions, extensions and timing contracts |
| [Absence contract](hardware/absence-contract.md) | Absent hardware structures and audit evidence |
| [Crown-jewel inventory](assurance/crown-jewels.md) | Specifications, theorem targets and review status |
| [Coverage matrix](assurance/coverage-matrix.md) | Property-boundary coverage |
| [Profile-freeze measurements](implementation/contracts/freeze-measurement.md) | Measurement recipe and acceptance thresholds |
| [Block geometry](hardware/block-geometry-constraint.md) | Shared block-size constraints |
| [Bank-count exploration](hardware/bank-count-dse-contract.md) | Candidate banks, constraints and objectives |
| [Second-class macro architecture](hardware/second-class-macro-architecture.md) | Dense-memory architecture and measurands |
| [TRNG source model](hardware/trng-source-model-contract.md) | Source submission and qualification inputs |

## Hardware and ISA

| Topic | Documents |
| --- | --- |
| CHERI lineage | [Foundation map](hardware/cheri-foundation-map.md), [version matrix](hardware/cheri-version-matrix.md) |
| Scalar RTL | [Re-parameterization delta](hardware/rtl-reparameterization-delta.md), [width staging](hardware/scalar-width-transform-contract.md), [core port](hardware/core-port-contract.md), [platform devices](hardware/platform-device-contracts.md) |
| Memory qualification | [Topology comparison](hardware/memory-topology-comparison.md), [remanence decision](hardware/remanence-threat-decision.md), [macro protocol](hardware/macro-qualification-protocol.md), [sensitive-state lifetime protocol](hardware/sensitive-state-lifetime-protocol.md) |
| External devices and links | [Immutable module contract](hardware/immutable-module-contract.md), [module admission](hardware/immutable-module-admission.md), [ensemble link](hardware/ensemble-link-contract.md) |
| Faults and calibration | [Protected-sequence fault model](hardware/protected-sequence-fault-model.md), [calibration field classes](hardware/calibration-manifest.md) |

## Assurance and review

| Topic | Documents |
| --- | --- |
| Proof coverage and findings | [Field bindings](assurance/field-bindings.md), [findings register](assurance/findings-register.md), [unassigned proof map](assurance/unassigned-proof-map.md) |
| Proof sources | [Reuse inventory](assurance/proof-reuse.md), [subject records](assurance/proof-reuse/), [bearing record](assurance/proof-reuse-bearing.md) |
| Model and RTL correspondence | [Differential corpus](assurance/differential-corpus.md), [RTL co-simulation harness](assurance/rtl-cosimulation-harness.md), [RTL correspondence boundary](assurance/rtl-correspondence-boundary.md) |
| Security models and qualification | [Revocation](assurance/revocation-qualification.md), [witness policy](assurance/witness-policy-qualification.md), [session binding](assurance/session-binding-qualification.md), [security policy](assurance/security-policy-model.md), [hardening obligations](assurance/hardening-opening-obligations.md) |
| Cryptographic premises | [Post-quantum reference](assurance/pq-reference-contract.md), [probing model](assurance/probing-model-contract.md), [AES-GCM dossier](assurance/aes-gcm-premise-dossier.md) |
| Formats | [Wire-format inventory](assurance/wire-format-inventory.md) |
| Proof tools | [Qualification contract](assurance/proof-qualification-contract.md), [executed comparison](assurance/proof-tooling-qualification.md), [CIC checker qualification](assurance/cic-checker-qualification.md), [bounded foundation route](assurance/cic-checker-qualification.md#bounded-foundation-execution-route), [CIC literature starting points](assurance/proof-reuse/languages.md#bounded-cic-starting-points) |

## Implementation and qualification

| Topic | Documents |
| --- | --- |
| Scalar compiler | [Assembly comparison](implementation/comparisons/compiler-assembly.md), [purecap ABI](implementation/contracts/purecap-abi.md), [prerequisite qualification](implementation/contracts/compiler-prerequisites.md), [kind handoff](implementation/contracts/compiler-kind-handoff.md), [source values](implementation/contracts/compiler-source-values.md), [preserved-kind interface](implementation/contracts/compiler-kind-interface.md) |
| Application execution | [Elastic domain](implementation/contracts/elastic-domain.md), [application host](implementation/contracts/application-host.md), [Wasm execution](implementation/contracts/wasm-execution.md), [web application pilot](implementation/contracts/web-application-profile.md), [userspace porting](implementation/userspace-porting.md) |
| Workflow and compatibility | [Workflow profiles and hibernation](implementation/workflow-profiles.md), [finite workflow model](implementation/contracts/workflow-formal.md), [editor-driven native test cycle](implementation/contracts/compatibility.md) |
| Compute compatibility | [Compute contract](implementation/compute-compatibility.md), [feature map](implementation/compute-feature-map.md), [semantic contract](implementation/contracts/compute-semantic.md), [upstream review](implementation/compute-upstream-review.md), [matrix margin](implementation/contracts/matrix-margin.md) |
| Services, storage and packages | [Service authoring](implementation/contracts/service-authoring.md), [object transactor](implementation/contracts/object-transactor.md), [storage recovery](implementation/storage-recovery-policy.md), [storage index comparison](implementation/comparisons/storage-index.md), [package-layer comparison](implementation/comparisons/package-layer.md), [attested TLS](implementation/attested-tls-protocol.md) |
| Boot and composition | [Roster and boot recipe](implementation/contracts/boot-roster.md), [boot handoff](implementation/contracts/boot-handoff.md), [kernel instance](../kernel/README.md), [roster measurements](implementation/contracts/roster-measurement.md), [schedule record](implementation/contracts/schedule-record.md), [device registers](implementation/contracts/device-registers.md) |
| Phase-service comparison | [Store-buffer comparison](implementation/comparisons/store-buffer.md), [executable prerequisites](implementation/phase-service/prerequisite-contract.md), [boundary admission](implementation/phase-service/boundary-contract.md), [stalled transitions](implementation/phase-service/stall-contract.md), [mode transitions](implementation/phase-service/mode-contract.md) |
| Replay and entropy | [Replay record](implementation/contracts/replay-record.md), [host replay envelope](implementation/contracts/host-replay-envelope.md), [entropy observer](implementation/contracts/entropy-observer.md) |
| Qualification and generation | [Product gate](implementation/contracts/product-gate.md), [Fiat-Crypto emission](implementation/fiat-crypto-emission.md) |

### Static-memory research

| Topic | Documents |
| --- | --- |
| Research and artifacts | [Research agenda](background/static-memory-research.md), [artifact inventory](implementation/static-memory/artifact.md), [literature adoption](implementation/static-memory/literature.md) |
| Experiments | [Replay guide](implementation/static-memory/experiments.md), [baseline](implementation/static-memory/baseline.md), [capacity corpus](implementation/static-memory/corpus.md), [compiled census](implementation/static-memory/census.md) |
| Mechanized results | [Laminar placement](implementation/static-memory/baseline.md#mechanized-statement), [service equivalence](implementation/static-memory/transformations.md#mechanized-equivalence) |
| Planning interfaces | [Placement search](implementation/placement-search.md), [portable memory planner](implementation/portable-memory-planner.md) |

## Performance

| Topic | Documents |
| --- | --- |
| System estimates | [Performance estimates](performance/performance-estimates.md) |
| Inference | [Demand record](performance/inference-demand.md) and [measurement artifacts](performance/inference-demand/), [ternary static demand](performance/ternary-static-demand.md), [prompt-processing term](performance/prompt-processing-term.md), [BITCOS assessment](performance/bitcos-assessment.md), [Bonsai 2 assessment](performance/bonsai2-assessment.md) |
| Ensemble traffic | [Sharding traffic](performance/ensemble-sharding-traffic.md) and [derived artifacts](performance/ensemble-sharding-traffic/) |
| Self-hosting | [Toolchain residency](performance/toolchain-residency.md) and [measurement artifacts](performance/toolchain-residency/) |

## Background and design assessment

- [Inspirations and prior art](background/inspirations.md)
- [Architectural alternatives](background/architectural-alternatives.md), including the [desktop elastic-domain decision](background/architectural-alternatives.md#a-general-purpose-desktop-on-a-static-machine-an-elastic-domain-inside-a-fixed-envelope-adopted-for-the-laptop)
- [Critique](background/critique.md)
- [Mathematical open problems and recent results](background/open-math-conjectures.md)

## Working on the repository

- [Working rules](../AGENTS.md)
- [Tool guide](../tools/README.md)
- [Portable proof assistance](assurance/proof-assistance.md)
- [Portable Sail assistance](assurance/sail-assistance.md)
