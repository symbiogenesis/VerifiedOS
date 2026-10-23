# Proof reuse inventory

This inventory identifies established external proofs that can support
VerifiedOS's completed proof artifacts and its remaining proof obligations.
It records the theorem or proof development, authorship, source edition,
language, licence, assumptions and the gap to the local obligation. Source
editions and qualification limits live in the subject records. The latest
source qualification is dated 2026-10-23. The subject records
distinguish published results from the contents of a particular code edition,
and a paper, an archived deposit, a maintained tree and a pen-and-paper
metatheory beside an unverified implementation are four different findings.

Which plan cell or proof-map slice each source actually
bears on, and the ground where a source bears on none, is resolved once in
[the bearing record](proof-reuse-bearing.md). The subject records stay keyed by
obligation family and state each source's theorem, terms and distance; that
record is keyed by source and names a consumer or names none.

The project's implementation and proof vehicles remain Sail and Rocq/Gallina.
Isabelle/HOL, HOL4, HOL Light, F*, EasyCrypt, Dafny, Why3, Lean and symbolic
protocol proofs can supply strong precedents and independent specifications;
their proof terms cannot simply be loaded into Rocq. Even a Rocq theorem
needs the same semantics, hypotheses and dependency closure before reuse.

<a id="the-2026-10-10-literature-reading"></a>

## Literature scope

The inventory includes recent formal proofs and substantive corrections, along
with older results selected for their local relevance. The records distinguish
an artifact's proof or release date from a paper's posting date.

The [bearing rows](proof-reuse-bearing.md#sources-the-2026-10-10-reading-added)
link the references to their local consumers or explain why none is
selected. Their subject records hold immutable source identities, theorem
scope, hypotheses, licenses and transfer limits. This is a bounded literature
search, not an exhaustive census or an external-proof replay. No result
changes the local acceptance route or discharges a requirement by citation.

<a id="the-2026-10-23-online-reuse-review"></a>

## Implementation reuse priorities

Source selections and implementation references are qualified against the open proof boundaries. Exact editions, license readings, theorem scope and dependency limits live in the subject records. The [bearing rows](proof-reuse-bearing.md#sources-the-2026-10-23-reading-added-or-requalified) assign each result to its existing consumer. Source qualification adds no upstream code, dependency, accepted assumption or completed proof.

The [pinned source binding handoff](../implementation/reuse-source-bindings.md) connects the selected Rocq crash interface, crypto routine proofs and PER reference to their existing consumers. The [authored native metadata control](../../tools/rocq-census/README.md), reached through `python tools/run.py rocq-census`, uses the locked prover's module API for Q35q. Its output remains metadata evidence until complete enumeration, implementation connections and exact audits qualify. Q35p's preserving tag interface and that census serve the canonical machine term and the real cold-path proof client already prioritized by the plan. The remaining recommendations retain their consumers' readiness conditions.

| Candidate | Recommended use | Qualification that remains |
| --- | --- | --- |
| [Native Rocq module metadata](proof-reuse/foundations.md#f16-native-rocq-module-metadata-for-the-sail-support-census) | Use the authored `rocq-census` metadata control as the typed producer starting point for Q35q. | Complete binder/universe/name handling, concrete implementation connections, refusal controls and exact assumption/kernel evidence. An opaque LSP serializer does not supply those fields. |
| [Sail V2 and ArchSem's interpreter](proof-reuse/languages.md#canonical-sail-effects-existing-interpreters-and-their-tag-boundary) | Compare existing effect interpreters before designing Q35p's adapter. | Neither supplies the missing qualified standalone tag operation; preserved observations and actual canonical consumer acceptance remain owed. |
| [Capability and hardware sources](proof-reuse/hardware.md) | Adapt Griotte's switcher proof structure and qualify the hardware-refinement sources. | Griotte requires permissions the local lattice forbids. Kami's selected shipped example uses `cheat : forall t, t`; its restored scripts and full loaded assumption context require qualification. |
| [Rocq crash logic and PoWER](proof-reuse/systems.md) | Retain exact Rocq source editions for the storage crash-proof interface. | Current default Perennial development is Lean and lacks crash/recovery logic; native persistence/authentication correspondence remains local work. |
| [s2n-bignum and libcrux](proof-reuse/crypto.md) | Use concrete routine proofs and explicit verification-status maps for crypto refinement and leakage review. | Foreign ISA/prover proofs and source-level secret independence do not establish constant time for the emitted CHERI binary. |
| [Corrected WasmCert](proof-reuse/parsers.md#wasmcert-coq-type-safety-and-interpreter-refinement-with-concrete-boundaries) | Qualify the edition with repaired array-interface assumptions for Q34g. | Rocq 9.3 compatibility, concrete array/numeric/SIMD implementations, binary parsing and full Core 3.0/host refinement remain open. |
| [vasn](proof-reuse/parsers.md#vasn-licensed-per-proof-and-differential-oracle-candidate) | Compare PER fragmentation/alignment and extension cases for the required ASN.1-to-Narcissus front end. | Verus proofs, trusted helper contracts and version-dependent injectivity supply an independent reference/oracle, not the required Rocq/native proof. |

Use immutable editions that retain the required proof system, corrected assumption interfaces and precise producer APIs. Every adoption still consumes its owner's semantic correspondence and acceptance checks; no porting saving is measured here.

## What qualifies as a gold-standard example

Concrete donors are selected at their consumers: the capability-aware CHERIoT Rust compiler for the future functional
Rust producer, GarageDoor's whole-image integration recipe for Q35d, PoWER's
write-permission/crash correspondence for storage hardening, and a bounded Sailor
adapter for uncovered context-state analysis. The subject records own immutable
editions, terms and transfer gaps; [the bearing record](proof-reuse-bearing.md#sources-the-2026-10-12-implementation-reading-added)
assigns their consumers. [The architectural alternatives](../background/architectural-alternatives.md#functional-cheri-rust-compiler-starting-point)
retain displaced fresh-port and interface-design starting points and their
reopening conditions. These selections replace work strategies rather than
commissioning parallel implementations. Granite remains a leakage-composition
reference pending its exact dependency closure, and archived MachCSL remains
blocked on first-party terms. No source-only selection closes a local proof or
removes its representation, assumption, fault-model or target obligations.

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

Four families the local obligations reach for most directly now have a
qualified precedent rather than a literature mention: resource-aware
allocation, where a specification makes a successful allocation a proved
consequence of available resources and a separate heap-space logic bounds
what a program can hold; a response-time analysis joined to the C
implementation of the scheduler that earns it; certified refinement from an
abstract type to a declared concrete data layout; and foundational ownership
reasoning over unsafe abstractions inside ordinary code. Their records say
what each leaves local, and two of the four are mechanized in provers this
project does not use. Qualification is the weaker half of reuse: it records
terms, theorem and distance, and it discharges nothing.

Certificate-checking machinery is qualified in
[foundations](proof-reuse/foundations.md) as reference material and not as a
route, because the register decides its admission before any candidate's
merits are weighed. An untrusted producer whose output the existing checkers
re-validate is admissible and free to be aggressive; importing a checker to
decide those candidates is a different act, and the entries that refuse it,
together with the one question they leave open, are read there and taken at
the plan's Q27a rather than re-argued per record.

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
