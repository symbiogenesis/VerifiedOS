# Scalar compiler kind handoff

This is M1.2d-i's diagnostic and prerequisite handoff under the
[qualification contract](compiler-prerequisites.md#2-pointer-kind-diagnostic-and-lowering-prerequisites).
It identifies the source information the functional backend must retain and
links the selected source, kind and call interfaces for implementing that path.
It does not implement or accept purecap code. M1.2g-ii, M1.2d-ii, M1.2e-ii and M1.2f
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

The [source-value contract](compiler-source-values.md) owns the selected
abstract values, source operations, authority witnesses and the point where
symbolic lowering meets concrete composition. Its explicit profile and
unsupported-lowering refusals preserve the distinction between a missing
implementation and source undefined behavior. The platform's existing ban on
integer-to-capability provenance governs the cast policy; a pointer-width
integer alias cannot bypass it.

The [kind interface](compiler-kind-interface.md) selects explicit typed IRs
through the whole scalar pipeline. It owns payload versus address typing,
transformation and allocator obligations, typed frame locations, and total
coverage through the decoded final image. Kind checking and authority
correspondence are separate obligations. No runtime tag dispatch or
integer-to-capability printer substitution supplies either one.

These contracts resolve the diagnostic's design alternatives under
[the reviewed-agreement predicate](compiler-prerequisites.md#4-reviewed-source-kind-and-switcher-agreement).
They supply no new source execution, pass simulation or target result. The
existing `Vcap` constructor and M1.2g-i's inhabited memory evidence remain
inputs to M1.2g-ii's implementation; they do not establish the source relation
or physical tag-clear refinement. Shared compiler type definitions land under
one owner before dependent pass changes, and the compiler integrator alone
registers shared extraction and build inputs.

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

The [selected switcher protocol](purecap-abi.md#4-calls-and-returns) owns
edge identity, protected saved state, bounded nesting, scrubbing and authority
transfer. It also identifies the sealing-aware firmware refinement and
crash-only timer-cut cleanup the real producer must establish, including the
explicitly missing timer/trap model behavior needed by its target campaign.
The one-time firmware handoff is not that producer. M1.2d-ii consumes the reviewed agreement;
its cross-compartment implementation and proof joins remain open.

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