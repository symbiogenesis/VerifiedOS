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
| Assurance and review | [Reviewer onramp](assurance/reviewer-onramp.md), [crown jewels](assurance/crown-jewels.md), [coverage matrix](assurance/coverage-matrix.md), [field bindings](assurance/field-bindings.md), [differential corpus](assurance/differential-corpus.md), [findings register](assurance/findings-register.md), [proof reuse inventory](assurance/proof-reuse.md) and its [subject records](assurance/proof-reuse/) |
| Implementation and qualification | [Implementation checklist](implementation/implementation-checklist.md), [completion log](implementation/completion-log.md), [freeze measurements](implementation/freeze-measurement-contract.md), [placement search](implementation/placement-search.md), [product gate](implementation/product-gate-contract.md), [userspace porting](implementation/userspace-porting.md) |
| Performance | [Performance estimates](performance/performance-estimates.md), [inference demand](performance/inference-demand.md) and its [measurement artifacts](performance/inference-demand/) |
| Background and design assessment | [Inspirations and prior art](background/inspirations.md), [architectural alternatives](background/architectural-alternatives.md), [critique](background/critique.md) |

The [tool guide](../tools/README.md) describes the checkers and build commands.
[Working rules](../AGENTS.md) describe document maintenance and review.
