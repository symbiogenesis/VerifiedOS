# Native Sail signature type completeness checkpoint

Q35q remains open. The [landed census contract](contracts/sail-support-census.md) requires complete native names and types for abstract signature and functor fields, with separate exact assumption audits for concrete implementations. A focused native check refuses the first signature's type completeness before any adapter implementation.

[Native signature completeness diagnosis](retained-evidence/close3-q35q-20261013/manifest.json), SHA256 `9643ce249720459c89f8ad672cf48f5d10bd3a3a51139b384fb5c4972193d139`, binds the exact query, raw stdout/stderr, command receipt, unchanged frozen switch exports and original source notice. The receipt records the tested contract revision `f3596f70393160fbf6c0ea9f4de3366c2a51dce5`, private native lane and before/after identities of the immutable source archive, both reviewed patches, recipe, project lock, actual compiler, signature source, query and installed prover printer source.

## Focused native result

The source is freshly extracted from the [immutable recipe's](../../tools/opam/sail-support-qualification.json) checksum-bound coq-sail 0.20.3 archive and receives only the existing axiom-removal and strict-source syntax patches. Its actual `MachineWordInterface` module strictly compiles at locked Rocq 9.3.0 with exit 0 and empty diagnostics. Compiler and switch-export processes use an explicitly created absolute native temporary working directory; support and query objects stay in the assigned native build lane.

The query explicitly unsets `Short Module Printing` and sets printing depth and width to 1000000. It prints the enclosing module and its nested module type under default printing, then repeats the module-type query with `Set Printing All`. Both signature responses contain the same `Parameter` labels, starting with `idx`, without their types. The enclosing module's reading identifies the nested module type. These native observations classify its signature boundary, but supply neither the contract's required field types nor a complete census. No inaccessible signature field is queried as a global constant.

The installed locked prover's `vernac/printmod.ml`, bound by before/after digest in the receipt, contains a fallback from rich module printing to names-only printing after a noncritical exception. The observed output is compatible with that behavior; this check does not identify the underlying exception. The printer source is inspected locally and is not copied into the evidence bundle.

The candidate interval is 2026-10-14 03:40:41.598009–03:40:43.504619 UTC, or 2026-10-13 22:40:41.598009–22:40:43.504619 America/Chicago. The receipt records one candidate and its active runtime. Candidate work stops at this unsupported native completeness shape. The hash-bound inputs and the complete frozen project-switch exports remain unchanged.

## Remaining owner act

Rocq [PR 22614](https://github.com/rocq-prover/rocq/pull/22614) is merged into `master` at `01b86fef6a51c6d0e3a9f2e50266f7fa1db3dbce`. It adds `module-printing-fallback` when rich printing falls back to field names. After the [qualified prover adoption](../../tools/opam/README.md#merged-checker-and-printer-improvements), census queries should unset `Short Module Printing` and use `Set Warnings "+module-printing-fallback"` to reject that incomplete output directly. The locked Rocq 9.3.0 lacks this warning. The upstream change supplies an explicit refusal signal; complete typed metadata remains the prerequisite below.

Commission and qualify a native module-body producer that retains each signature and unapplied functor field's elaborated type, enclosing signature and parameters without treating abstract obligations as owned global constants. Its complete enumeration must account for the selected module population, nested fields, inductive families and constructors, aliases, and concrete implementations. It needs the census contract's positive and refusal controls at the locked prover before a support adapter may consume it.

One untested route is a temporary query functor parameter carrying the actual signature, with native type queries inside that parameter's scope. Such a route would still owe complete enumeration and faithful provenance; it could supply no concrete implementation-assumption verdict. It is a future owner hypothesis, not a passing candidate.

This diagnosis performs no adapter qualification, complete declaration census, complete exact assumption audit, recursive kernel check or hosted run. Q35q's hosted acceptance remains open, as do Q35n's independent cold snapshot export/import and Q35b's canonical consumer acceptance. The common inventory guard, strict flags, allowed axiom contexts, package and prover locks, source semantics and project lock are unchanged.
