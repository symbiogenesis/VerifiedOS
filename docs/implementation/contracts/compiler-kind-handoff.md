# Scalar compiler kind handoff

This is M1.2d-i's diagnostic and prerequisite handoff under the
[qualification contract](compiler-prerequisites.md#2-pointer-kind-diagnostic-and-lowering-prerequisites).
It identifies the source information the functional backend must retain and
the decisions its owners must review before implementing that path. It does
not implement or accept purecap code. M1.2g-ii, M1.2d-ii, M1.2e-ii and M1.2f
retain their [implementation and target joins](../implementation-checklist.md).
The [scalar ABI](purecap-abi.md) retains its existing authority.

## 1. Measured boundary

The contained compiler campaign in `test/verifiedos-m12d/` binds its source
revision, executable, original and effective configuration, invocation,
source files and generated files by identity. Its source is
`cd1d3adbea95b9d7e1a25d335c4dd48e22435a6d`; its replay record and refusal
results are `evidence/report.json` and `evidence/refusals.json` in that
contained directory. The compiler sources, generated dumps and assembly
remain there under the [containment decision](../../../THIRD-PARTY.md#compcert-and-secomp).

The paired source operations include pointer and full-width integer addition,
loads, stores, copies and values live over calls. The campaign compiles each
input at both unoptimized and optimized settings into fresh directories. It
retains Clight, Cminor, RTL, LTL, Mach and assembly outputs. The unchanged run
satisfies the diagnostic; altered identities, stale or missing output and a
changed claimed boundary are rejected. This says the measured loss is
reproduced, not that ordinary RV64 output is accepted as purecap.

The decisive copy pair takes a destination pointer and a source pointer in
both functions. One copies a pointer-valued object; the other copies a
full-width integer. Clight retains the different pointed-to types. In Cminor,
the two signatures and bodies are identical: both signatures have two pointer
arguments and a void result, and both payload accesses use the integer-width
chunk. Mach also gives them identical operations.

Inspection of the matching source locates the first merging transition in
`Cshmgen.make_load` and `make_store`, which produce Csharpminor accesses from
`Ctypes.access_mode`. A pointer access selects `Mptr`, which is `Mint64` on
RV64; integer-width access selects `Mint64` directly. The access therefore
carries no distinction between these payload kinds before the retained Cminor
dump. Separately, `Ctypes.typ_of_type` maps pointers to `Tptr`, which is
`Tlong` on RV64, and pointer addition through `make_add_ptr_long` shares
`Oaddl` with integer addition.

**Some signature information survives.** `Xptr` remains in extended call
signatures. The pointer-load and integer-load functions retain different
result signatures in Cminor. The copy pair nevertheless has identical
signatures as well as identical bodies, so recovering only that signature
information does not distinguish its accesses. The result is not a claim
that every pointer fact disappears at one phase.

A pointer and an integer live across a call both receive a `long` Mach stack
slot. Their assembly uses scalar `sd` and `ld`, while frame setup uses
integer moves and cursor arithmetic and return uses `jr`. The cast cases
also preserve their input expressions through pointer/integer conversion in
Cminor. Stack-address and global-address cases emit ordinary RV64 forms.
The ninth-argument compilation produces both function bodies in IR, then
fails while printing its first function, which takes an integer ninth
argument. This run does not independently execute the pointer ninth-argument
printer path. No target execution is claimed by these observations.

## 2. Source and intermediate-value decisions

M1.2g-ii and M1.2d-ii must review a value-kind interface that reaches every
relevant intermediate operation, memory access and frame slot. Distinct IR
kinds or a checked sidecar are implementation options; either needs a total
coverage rule and rejection of missing or inconsistent information. Equal
storage width is insufficient to choose authority-preserving operations.
The allocator must retain kind through moves, live-range splits, spill slots,
argument slots and results, including reuse of one physical register by
values of different kinds at different times.

The value relation must also identify the point where abstract block pointers
become concrete capabilities. The existing `Vcap` constructor alone supplies
no execution path: `Memory.loadv` and `storev`, `Values.offset_ptr` and `addl`,
and the pointer-cast case do not currently operate on it. A design may retain
abstract `Vptr` until a defined lowering boundary and relate its blocks to
composition-supplied authority, or carry `Vcap` earlier and define the missing
operations. This handoff selects neither option and treats neither as an
already proved source-to-target relation.

The source contract must distinguish pointer-preserving casts, extraction of
an integer address and any supported rederivation of capability authority.
It must define null conversion and the target's `intptr_t` and `uintptr_t`
behavior. A promised pointer round trip may require a capability-preserving
integer kind distinct from ordinary integer arithmetic. Arbitrary integer
bits cannot silently become authority. The current pointer/intptr-sized cast
case cannot be extended indiscriminately without first settling that policy.

Pointer cursor arithmetic, pointer comparison and difference need explicit
source and target relations; integer arithmetic retains its own behavior.
Likewise, capability loads, stores and copies must be distinguished from
scalar accesses, even when each occupies eight bytes. The interface must
state how overlapping scalar writes, byte copies and aliasing affect tagged
objects. M1.2g-i's inhabited block-memory evidence is an input to that work;
it is not a physical Sail tag-clear refinement.

## 3. Frame, authority and emission joins

The [selected scalar frame](purecap-abi.md#2-the-frame-laid-out-at-composition)
uses typed slots, tagged back links and return sentries, caller preservation,
and no ordinary per-function bounds narrowing. M1.2d-ii must preserve those
choices in emitted instructions and bind the layout to the composition's
stack region and bounded call path. Unsupported signatures, dynamic frame
sizes and call paths exceeding their stack budget require an explicit refusal
policy. A handwritten frame witness cannot establish that the compiler
produces this behavior from the source interface.

Global-address materialization must identify its composition-supplied root or
table entry, symbol extent, permissions and relocation provenance. PCC-derived
code authority cannot manufacture writable-data authority under the split-root
model. Ordinary code pointers and exported sentries retain the separate roles
in [the call contract](purecap-abi.md#4-calls-and-returns).
An integer address alone does not identify the authority that permits an access.

Every emitted narrowing must correspond to a request over a selected plan
region, with source authority, byte fields and provenance bound to its final
instruction. M1.2e-i supplies a plan-relative decision; M1.2e-ii and the emitter
must establish actual plan membership and all-site coverage. Ordinary frames
emit no narrowing under the selected convention, so those frames cannot supply
the nonempty positive control this coverage requires.

Primitive bindings must preserve the exact profile mnemonic, operand form,
operand kinds and effects in [the primitive surface](purecap-abi.md#6-the-primitive-surface).
A legal source spelling is a binding to that identity, not a new instruction
registry. Immediate fields require validation, and barriers retain their
ordering across optimization. Positive emitted encodings and unknown-name,
wrong-kind and wrong-form refusals belong to the compiler acceptance.

The selected scalar convention leaves the [switcher protocol](purecap-abi.md#8-what-the-register-leaves-open)
open: edge-identity transport, scrub masks in each direction, bounded saved
caller state and nesting depth, and switcher authority still need a reviewed
producer/consumer agreement. The one-time firmware handoff is not that
agreement. M1.2d-ii must resolve it before claiming cross-compartment lowering.

## 4. Implementation ownership and decisive evidence

| Owner | Remaining join |
| --- | --- |
| M1.2g-ii | Source-value and address-operation semantics, cast authority, inhabited memory traffic, and the selected abstract/concrete value boundary |
| M1.2d-ii | Kind propagation through backend operations and typed slots, frame and ordinary-call emission, global authority materialization, primitives, and the reviewed cross-compartment protocol |
| M1.2e-ii | Selected-plan provenance and the total narrowing condition at every emitted site |
| M1.2f | Source/component comparisons and nonempty real compiler output through assembler, composer and Sail, with disagreement minimization returned to the relevant owner |

The compiler integrator alone registers shared extraction and build inputs.
No diagnostic creates a second compiler owner. Runtime tag dispatch or a
printer substitution from integer to capability mnemonics does not supply the
missing typed interface.

Decisive target cases pair pointer and integer arithmetic/accesses, preserve
mixed live values across nested direct and indirect calls, exercise stack and
writable-global addresses, and cover stack arguments beyond the register set.
Refusal controls must expose tag loss from scalar or partial overlapping
writes, missing kind/provenance, unsupported authority conversions and invalid
frame or narrowing plans. M1.2f's real target observations must discriminate
those failures; assembly syntax acceptance or this diagnostic alone cannot do so.