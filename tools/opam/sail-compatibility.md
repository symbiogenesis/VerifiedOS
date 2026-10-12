# Sail support compatibility qualification

The first bounded compatibility route selects the Sail 0.20.3 paired
`rocq-sail-stdpp` 0.20.3 source at
`e7b914cddc032e3676eebd87a808229828013e9c`, keeping Rocq 9.3.0,
Stdlib 9.2.0, stdpp/bitvector 1.13.0, OCaml 5.4.1 and Dune 3.24.2.
Its purpose is to remove artificial release waiting without downgrading the
prover or reducing the canonical machine term's guarantees. The
[canonical-term record](../../docs/assurance/canonical-machine-term.md#routes-that-take-the-five-out)
owns the distinct five-axiom removal and model emission obligations.

## Bounded contract and acceptance

This contract must be committed before the trial starts. Use only a private
source/build prefix in the assigned native lane. Do not install into, pin in,
or otherwise mutate a shared project switch. Record its before/after exports.
Read the exact source's licence and bind the release archive, upstream tree,
package metadata and every patch by SHA-256. Use the release paired with the
locked Sail, not a moving upstream branch.

The first stage runs the package's real Dune build with the locked dependency
versions and existing settings. It may repair package metadata or build syntax
only. It must record whether each patch changes a Gallina source, definition,
statement or compile flag. Preserve every existing flag. The package's own
build result is distinct from the consumer's strict compiler, exact-assumption
and kernel acceptance. Stop at the first source-level semantic incompatibility
rather than expand into an unpriced framework port. Do not downgrade a library,
suppress a diagnostic, add an admission or change an allowed assumption.

A successful package trial must reproduce the support library imports with the
locked compiler and recursive checker, including the positive `Eqdep` control.
The unchanged release is expected to retain the five previously measured Stdlib
axioms; a successful build does not authorize those axioms. Q35g's separately
reviewed axiom-removal patch may be qualified only with its frozen elaborated
comparison, complete strict closure, exact assumptions and unchanged consumer
semantics. The term's `Real` import and all term-side floating-point axioms
remain independently owned obligations.

Production carriage requires a deterministic recipe, immutable source/patch
identities, complete dependency resolution, hosted cold build and fresh
acceptance under the consumer's existing contracts, and a portable snapshot
exported and re-imported from that qualified hosted build. Keep `rocq.lock`
unchanged until that evidence exists. A released package that admits the locked
prover and satisfies the same consumer acceptance retires the local metadata
or source patch after repeating qualification.

The endpoint is either those checks with exact scope and evidence, or a recorded
refusal naming the first incompatibility and its separately scoped next action.
Neither endpoint claims the canonical term, machine logic or binary theorem
complete.

## Trial result

The implementation lane records the package build and import probes here after
running the bounded trial. No result is implied by the contract.
