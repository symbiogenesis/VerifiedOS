# Foundational proof reuse

This is a source-qualified part of the [proof reuse inventory](../proof-reuse.md).
The [opam lock](../../../tools/opam/rocq.lock) fixes the local prover and library
versions. A library's statements and its licence are separate checks; a theorem
about mathematical integers does not establish a bounded machine operation.

## F01: Rocq Stdlib arithmetic, integrated by reference

**Source and authors.** The Rocq Development Team, INRIA, CNRS and contributors;
`PeanoNat.v` credits Evgeny Makarov, INRIA, 2007. The reviewed edition is
[Stdlib V9.2.0](https://github.com/rocq-prover/stdlib/tree/V9.2.0), revision
`8dd155bc10529814202f8f4c643e5ae6c2c88fa6`. Its
[PeanoNat source](https://github.com/rocq-prover/stdlib/blob/8dd155bc10529814202f8f4c643e5ae6c2c88fa6/theories/Arith/PeanoNat.v)
instantiates natural-number property modules, including the generic addition
and multiplication facts. The [library documentation](https://rocq-prover.org/doc/V9.1.0/stdlib/index.html)
is a discovery aid; the installed V9.2.0 source and kernel are the integration
evidence.

**Exact use.** [MemoryPlan.v](../../../proofs/MemoryPlan.v) requires
`Stdlib.Arith.PeanoNat` without importing its namespace. Its existing helper
names and propositions remain the interface to the slot-placement, alignment
and admission proofs. `add_0_r`, `add_succ_r`, `add_comm`, `add_assoc`,
`mul_add_distr_l`, `sub_diag`, `sub_0_r`, `mul_0_r`, `leb_refl` and `eqb_refl`
refer directly to the identically named `PeanoNat.Nat` theorems. `eqb_true`
uses the forward implication of `PeanoNat.Nat.eqb_eq`. These are proofs over
the same `nat`, addition, subtraction, multiplication and Boolean comparisons,
so no representation bridge or new premise is required.

**Scope.** This supports the existing memory-plan arithmetic behind R-08-011,
R-08-018 and R-15-060. It changes no discharge claim. In particular it does
not turn the statement artifact into a proof of a shipped composition,
machine-word overflow, allocator optimality or the compiler's emitted plan.
The native `run.py proofs` gate compiles the clients, inventories their
constants, follows `Print Assumptions` through the imported proof terms and
kernel-rechecks the modules. An import is never an exemption from that audit.

**Licence and conveyance.** The actual
[V9.2.0 LICENSE](https://github.com/rocq-prover/stdlib/blob/8dd155bc10529814202f8f4c643e5ae6c2c88fa6/LICENSE)
and the source header state LGPL version 2.1. No upstream source or compiled
library is vendored. The original Apache-2.0 adapters use the separately
installed library, whose compiled outputs stay untracked. Redistribution of
the library or combined compiled artifacts carries its own LGPL obligations;
the [third-party record](../../../THIRD-PARTY.md#used-by-the-build-not-conveyed)
records that boundary. This is reuse by a library reference, not relicensing
the upstream proofs as Apache-2.0.

## F02: stdpp finite maps, sets and sequences

**Source and authors.** The std++ developers and contributors, in the
[Iris stdpp repository](https://gitlab.mpi-sws.org/iris/stdpp). Its
[gmap development](https://gitlab.mpi-sws.org/iris/stdpp/-/blob/master/stdpp/gmap.v)
implements finite maps over countable keys with extensional equality; the
source credits the canonical binary-trie work of Andrew Appel and Xavier
Leroy. The map laws and concrete implementation are more useful starting
points than a fresh abstract map interface alone. The actual
[LICENSE](https://gitlab.mpi-sws.org/iris/stdpp/-/blob/master/LICENSE)
grants BSD-3-Clause and names the std++ developers and contributors.

**Fit and disposition.** Rocq-native adaptation candidate for
[JournalIndex.v](../../../proofs/JournalIndex.v),
[KeyspaceDomains.v](../../../proofs/KeyspaceDomains.v),
[CredentialHandles.v](../../../proofs/CredentialHandles.v) and the future Iris
program logic. The project's proof switch already fixes `rocq-stdpp` in its
lock, but the local modules do not thereby acquire map correctness. A selected
replacement needs a relation to the existing list/record representations,
finite-capacity and iteration-order proofs, and an assumption audit. A
logarithmic map in Rocq is not a proved WCET bound on CHERI. No change is made
to these data structures here. The branch link is a discovery location,
not a pinned integration input.

## F03: coqutil maps and machine words

**Source and authors.** Massachusetts Institute of Technology and the coqutil
authors, as identified by [AUTHORS](https://github.com/mit-plv/coqutil/blob/master/AUTHORS)
and the [MIT LICENSE](https://github.com/mit-plv/coqutil/blob/master/LICENSE).
The [map interface](https://github.com/mit-plv/coqutil/blob/master/src/coqutil/Map/Interface.v)
and [word developments](https://github.com/mit-plv/coqutil/tree/master/src/coqutil/Word)
are shared foundations for Bedrock2. The local lowering switch's version is
recorded in [THIRD-PARTY.md](../../../THIRD-PARTY.md).

**Fit and disposition.** Adaptation candidate for the bounded words and maps
of ring descriptors, firmware, crypto and the journal, especially at the
Gallina-to-Bedrock boundary. `map.ok` and word-law interfaces are premises
until a concrete implementation supplies their proofs. The existing
natural-number specifications do not become machine-word-correct merely by
importing these interfaces. Match signedness, width, overflow, byte order and
finite storage, then replay the chosen implementation at the pinned version.
MIT permits incorporation with retained notices; no source is copied here.

## F04: Mathematical Components

**Source and authors.** Georges Gonthier and the Mathematical Components
contributors, with attribution in
[INITIAL_AUTHORS.md](https://github.com/math-comp/math-comp/blob/master/INITIAL_AUTHORS.md)
and [AUTHORS](https://github.com/math-comp/math-comp/blob/master/AUTHORS).
The [project](https://github.com/math-comp/math-comp) publishes Rocq/SSReflect
developments for finite types, graphs, algebra, matrices and fields, used in
the formal Four Colour and Odd Order theorem developments. Its actual
[LICENCE](https://github.com/math-comp/math-comp/blob/master/LICENCE) states
CeCILL-B, which includes attribution conditions requiring a separate
incorporation reading; it is not an MIT election.

**Fit and disposition.** Strong Rocq-native foundations for finite permission
lattices, live-range colouring, linear ECC and finite-field crypto. See the
Infotheo ECC entry in [hardware](hardware.md) and the arithmetic entries in
[crypto](crypto.md). Algebraic or graph theorems need an encoding relation to
the local permissions, intervals and bit layout. The Four Colour theorem is
about planar graphs and gives no general allocator-colouring theorem.
No MathComp dependency or global automation is added to the current proofs.

## F05: Lean mathlib as a cross-language reference

**Source and authors.** The mathlib contributors, with per-file authorship in
the [Lean 4 library](https://github.com/leanprover-community/mathlib4).
The actual [LICENSE](https://github.com/leanprover-community/mathlib4/blob/master/LICENSE)
is Apache-2.0. Its
[simple-graph colouring developments](https://github.com/leanprover-community/mathlib4/tree/master/Mathlib/Combinatorics/SimpleGraph/Coloring)
are a concrete lead for mathematical colouring arguments; its algebra and
finite-set library supplies alternative statements against which to review
Rocq models.

**Fit and disposition.** Reference only for R-08-011's live-range colouring
and proof-aware design-space mathematics. Lean proof terms are not Rocq
terms. An actual reuse requires a proved translation or a Rocq reconstruction,
including the relevant classical, choice and extensionality assumptions.
Neither an Apache licence nor a theorem-name match establishes that bridge.
This inventory does not introduce Lean as a project trust language.

## Discovery collections and search limits

The [Rocq package catalogue](https://rocq-prover.org/packages) and
[Corelib catalogue](https://rocq-prover.org/corelib), the
[Archive of Formal Proofs topic index](https://isa-afp.org/topics/), the
[Iris research index](https://iris-project.org/), and the
[Toccata verified-program gallery](https://toccata.gitlabpages.inria.fr/toccata/gallery/)
provide broader discovery surfaces. They lead respectively to Rocq packages,
Isabelle/HOL developments, separation-logic artifacts and Why3/Frama-C case
studies. Entries found there are qualified in the subject inventories; a
catalogue's membership alone supplies neither project compatibility nor a
successful local replay. The survey does not assert that every entry in
every library, or unpublished academic work, has been examined.

SMTCoq is a further [source-backed certificate-checker candidate](https://github.com/smtcoq/smtcoq)
for arithmetic obligations: the project describes Rocq checking of external
SAT/SMT witnesses and publishes a CeCILL-C licence. It is a discovery lead
requiring a concrete supported certificate, selected-version licence reading
and assumption audit, rather than an integrated replacement for the project's
existing admission checks or kernel.
