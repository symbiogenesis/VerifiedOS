# Proof reuse inventory

This inventory identifies established external proofs that can support
VerifiedOS's completed proof artifacts and its remaining proof obligations.
It records the theorem or proof development, authorship, source edition,
language, licence, assumptions and the gap to the local obligation. Source
qualification is dated 2026-09-10. The subject records distinguish published
results from the contents of a particular code edition.

The project's implementation and proof vehicles remain Sail and Rocq/Gallina.
Isabelle/HOL, HOL4, HOL Light, F*, EasyCrypt, Dafny, Why3, Lean and symbolic
protocol proofs can supply strong precedents and independent specifications;
their proof terms cannot simply be loaded into Rocq. Even a Rocq theorem
needs the same semantics, hypotheses and dependency closure before reuse.

## What qualifies as a gold-standard example

A strong candidate has a precise statement, accessible mechanization,
identifiable authors, published technical justification or substantial
maintained-library use, and explicit assumptions. Peer review and artifact
evaluation strengthen this evidence. They do not establish compatibility with
this project's narrower capability encoding, static schedule, crash model,
side-channel observations or admitted axioms.

The records use these dispositions:

- **Integrated by reference:** an existing library theorem is used in a local
  proof, with an exact statement match and native replay evidence.
- **Adaptation candidate:** a relevant mechanized proof exists, but its model,
  implementation, dependencies or prover version require a demonstrated bridge.
- **Reference:** a valuable theorem or method is available in another language,
  under unsuitable terms for copying, or without a usable mechanization.
- **Unqualified lead:** the searched material does not yet establish the code,
  licence, proof completeness or version needed to promote it.

A paper-only metatheorem, an incomplete artifact, a functional test, a solver
run with unchecked assumptions and a complete machine-checked proof are
different kinds of evidence. The subject records say which was found. Except
for the explicitly integrated arithmetic references, this survey does not
claim local replay of the external developments.

## Inventory by obligation family

These are curated source recommendations, not a replacement for the normative
[requirements register](../requirements-register.md), the
[crown-jewel specification inventory](crown-jewels.md), the
[implementation checklist](../implementation/implementation-checklist.md) or the generated
[proof ledger](../../tools/generated/proof-ledger.md). In particular, a completed
statement artifact can prove useful properties of its definitions while its
implementation-refinement obligation remains open. The ledger's distinction
between a citation and a discharge claim applies here too.

| Obligation family and local consumers | Source inventory | Transfer question |
| --- | --- | --- |
| Capability representation, monotonicity, unforgeability, permission lattices, revocation and ISA semantics; the curated Sail model | [Hardware and capability proofs](proof-reuse/hardware.md) | Does the proof cover this 64+1-bit encoding, native tags and exact instruction semantics? |
| RTL refinement, memory/interconnect isolation, ECC, fixed latency and protected-sequence faults | [Hardware](proof-reuse/hardware.md), [foundations](proof-reuse/foundations.md) | Does the refinement relate the actual RTL to this Sail model, including its observations and fault assumptions? |
| Apex composition, noninterference, consent and declassification; [ApexTheorem.v](../../proofs/ApexTheorem.v), [SeamWitnesses.v](../../proofs/SeamWitnesses.v) | [Systems and security](proof-reuse/systems.md), [protocols](proof-reuse/protocols.md) | Are all seam premises instantiated, and are value, timing, compromise and release observations aligned? |
| Kernel authority, IPC, partition switches and M-mode code; [EndpointIPC.v](../../proofs/EndpointIPC.v), [PartitionContext.v](../../proofs/PartitionContext.v), [MModeFirmware.v](../../proofs/MModeFirmware.v) | [Systems](proof-reuse/systems.md), [languages](proof-reuse/languages.md) | Which objects and transitions survive the removal of seL4's capability-space and allocation model? |
| Static scheduling, memory placement, sanitization ordering and supervision; [CyclicExecutive.v](../../proofs/CyclicExecutive.v), [MemoryPlan.v](../../proofs/MemoryPlan.v), [DischargeSequence.v](../../proofs/DischargeSequence.v), [SupervisionTree.v](../../proofs/SupervisionTree.v) | [Foundations](proof-reuse/foundations.md), [systems](proof-reuse/systems.md), [languages](proof-reuse/languages.md) | Do proofs establish the fixed cyclic schedule, whole-program bounds and real device ordering, beyond fair progress or witness examples? |
| Bounded rings, ownership transfer and descriptor validation; [RingContract.v](../../proofs/RingContract.v), [CopyRingService.v](../../proofs/CopyRingService.v) | [Systems](proof-reuse/systems.md), [parsers](proof-reuse/parsers.md), [languages](proof-reuse/languages.md) | Are publication, atomics, wraparound, DMA ownership, bounded capacity and failure behavior represented? |
| Crypto functions, reductions, constant time and masking; [AesGcm.v](../../proofs/AesGcm.v), [Sha256.v](../../proofs/Sha256.v), [HmacDrbg.v](../../proofs/HmacDrbg.v), [Keccak.v](../../proofs/Keccak.v), [RomVerifier.v](../../proofs/RomVerifier.v) | [Cryptography](proof-reuse/crypto.md), [hardware](proof-reuse/hardware.md) | Is the result functional correctness, implementation refinement, computational security or leakage security, and which are still owed? |
| Boot, lifecycle, key custody and credential handles; [RotFirmware.v](../../proofs/RotFirmware.v), [CredentialHandles.v](../../proofs/CredentialHandles.v) | [Protocols and attestation](proof-reuse/protocols.md), [crypto](proof-reuse/crypto.md) | Does the construction bind the measured image, fresh session, authenticated key and authority under the required compromise model? |
| Journal, index, namespaces and storage confidentiality; [JournalIndex.v](../../proofs/JournalIndex.v), [KeyspaceDomains.v](../../proofs/KeyspaceDomains.v) | [Systems](proof-reuse/systems.md), [foundations](proof-reuse/foundations.md), [crypto](proof-reuse/crypto.md) | Can concurrency, crash recovery, bounded progress and AEAD-backed noninterference be composed over the local storage model? |
| Admission, CHERI-TAL soundness, proof checking, extraction and compiler preservation; [AdmissionPath.v](../../proofs/AdmissionPath.v) | [Languages and compilers](proof-reuse/languages.md) | Is the result about the admitted final binary and this machine, including linking, adversarial contexts and source correspondence? |
| Wire-format correctness and canonicity, handler graphs, media and bounded interpretation; [HandlerGraph.v](../../proofs/HandlerGraph.v) | [Parsers and language runtimes](proof-reuse/parsers.md) | Does decoder correctness include injectivity, exact accepted-byte round trips, bounds and the complete selected format? |
| Radio state machines, secure sessions, remote appraisal and persistent witnesses | [Protocols](proof-reuse/protocols.md) | Which procedures, persistence assumptions, compromise cases and composition links are absent from each model? |

## Direct integration

[F01](proof-reuse/foundations.md#f01-rocq-stdlib-arithmetic-integrated-by-reference)
records the Rocq Stdlib arithmetic proof references used by
[MemoryPlan.v](../../proofs/MemoryPlan.v). The local helper statements remain
unchanged. The replacements use the already locked standard library and
remove duplicate elementary proof scripts. Authorship is credited in the
source and the [third-party record](../../THIRD-PARTY.md).

The integration replay of `python tools/run.py proofs --jobs 2` passes. It checks
transitive assumptions and runs the independent kernel rechecker as well as
compiling the local modules. Its untracked `proofs/proof-evidence.json`
receipt is tied to source contents and toolchain identity;
`python tools/run.py proofs status` verifies whether that evidence still
matches. A reference in this inventory alone supplies no such receipt.

## Reuse priorities and gaps

For existing Gallina definitions, start with small exact library lemmas and
concrete finite-map laws. For new machinery, the strongest starting points
are the existing Sail capability proofs, Iris/Cerise foundations, Perennial
crash reasoning, Fiat-Crypto/VST crypto developments, Narcissus codecs,
MetaRocq checking and erasure, and the compiler and protocol artifacts linked
in the subject inventories. Selection still follows each record's licence,
version and semantic restrictions.

Several tempting shortcuts fail qualification. RefFS supplies no crash-safety
proof, and its paper distinguishes Coq proofs using MoLi from a mechanized
soundness theorem for MoLi itself. Fair termination supplies no numerical
deadline. A standard RISC-V compiler theorem supplies no CHERI robust
preservation. A parser round trip supplies no injectivity unless the theorem
actually states it. The crypto and hardware records identify further cases
where a published result exceeds the checked-in artifact's scope.

No retrieved proof closes the project's complete apex theorem, bespoke
capability encoding, final-binary CHERI-TAL chain or silicon qualification
as a drop-in. Physical retention, power/EM leakage, device fault rates,
fabricated macro capacity and the holder's intended consent require the
project's specified assumptions, measurements or residual treatment. A
software proof library cannot discharge those by substitution.

The survey deliberately reaches beyond this repository's pinned upstreams,
using the [library catalogues](proof-reuse/foundations.md#discovery-collections-and-search-limits),
publisher papers, author repositories, artifact deposits and linked source
trees. It covers the proof families and current local artifacts above; it
does not claim an exhaustive census of every publication or a mechanically
complete classification of every register sentence that might entail a
future theorem. New obligations and source editions require renewed matching.
