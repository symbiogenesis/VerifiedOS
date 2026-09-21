# Scalar compiler implementation checkpoint

M1.2g-ii, M1.2d-ii and M1.2e-ii remain open. Their source-level components
implement parts of the landed [source-value contract](contracts/compiler-source-values.md)
and [kind interface](contracts/compiler-kind-interface.md); the existing
compiler does not yet carry those components through its passes to an accepted
purecap image. The [checklist](implementation-checklist.md) retains the full
implementation and target acceptance predicates.

The compiler code and its replay tools remain in the local contained repository
under the [existing incorporation decision](../../THIRD-PARTY.md#compcert-and-secomp).
No compiler source or generated compiler product is conveyed by this document.

## Source values

`riscV/SourceValues.v` defines a source/concrete representation relation over
composition-supplied authority and explicit derivations. Canonical null,
ordinary scalar data, live data and stack pointers, and sealed handles retain
distinct interpretations. Actual decoded bounds, permissions, roles and
lifetimes constrain supplied roots; matching region names alone is insufficient.
Stack authority must be local, and ordinary data authority cannot carry
store-local permission. Source cursor advance checks its starting offset as
well as its result.

The module includes capability serialization and destructive scalar-write
relations. Its focused checks exercise inhabited values and invalid authority
neighbors. These are local model statements. Source-memory injection, the
connection to the Sail operations, and real compiled memory/call traffic remain
M1.2g-ii's work. Function identities and the entry/return producer joins remain
unimplemented.

## Kinds and source types

`common/ScalarKinds.v` defines mandatory scalar kinds, typed live-value operands,
argument/result signatures, separate scalar and capability accesses, and typed
narrowing declarations. Live-value identifiers are separate from physical
register allocation. Manifest references require independent resolution to
current artifacts and do not authenticate themselves.

`cfrontend/ScalarTypeElaboration.v` derives those declarations from the actual
compiler's source types before the existing `access_mode` mapping erases pointer
payload kinds. It retains explicit integer extensions and truncations, access
alignment and volatility, and named unsupported-signature refusals. It is an
adapter for types and accesses, not an implemented Clight-to-Csharpminor
transformation. M1.2d-ii still owns typed propagation through the actual passes,
allocation, frames, calls, primitives and the switcher.

Boolean memory access refuses until its normalization semantics have a typed
operation. Floating storage retains its kind; floating call signatures require
the qualified ABI before they can be admitted.

## Narrowing provenance

`riscV/NarrowingProvenance.v` checks typed narrowing operations and declared
sites against independently supplied region and request catalogues. It reuses
the existing plan-relative arithmetic decision and checks coverage in both
directions, including duplicate, missing, orphaned and stale identities.
Register-form length transport is checked against the capability address width.

The initial consumer admits one declared site per operation. Transformations
that expand or remove an operation, and immediate-form narrowing, require their
own supported interfaces. Structural acceptance does not prove the runtime
operand's value, resolve authority or enumerate final bytes. The real compiler
producer and final-site enumeration remain M1.2e-ii and M1.2f joins; an empty
site set supplies no positive completion evidence.

## Evidence and continuation

The contained `test/verifiedos-scalar-kinds/`, `test/verifiedos-source-values/`
and `test/verifiedos-narrowing-provenance/` directories own focused replay
instructions and controls. Native compiler and proof products stay in the
assigned guest lanes.

The combined implementation at contained compiler revision
`0c03a2e1e19af29c3bde67207d122082b8e10c45` passes the proof build, extraction,
compiler build and explicit OCaml compilation of the extracted helpers.
The compiler driver does not yet call those helpers. This is an incremental
build over a source-verified retained compiler seed, not a clean rebuild.
Focused controls pass compilation and independent kernel checking; their
assumption audits introduce no new assumptions.

Contained evidence commit `d46034cc374dacd36f7d608c4629d890fda34272` records the
combined receipt and reproduction instructions under
`test/verifiedos-scalar-foundation/`. The source-derived type cases have their
own tested revision in `kind-cases.json`; they do not depend on SourceValues.
The source-value and narrowing receipts remain with their owning test
directories. Each receipt retains its input identities and direct command
verdicts. The local integration branch is
`work/easy-20260921-compiler-integration`; its code and evidence remain contained.

These components create no independently completed checklist item. Completing
the existing items still requires the typed executable pipeline, actual
firmware/kernel producers and the nonempty compiler-to-assembler-to-Sail
campaign. The [handoff](contracts/compiler-kind-handoff.md#4-implementation-ownership-and-decisive-evidence)
retains the allocation of those obligations.
