# Scalar compiler prerequisite qualification

This contract separates three independently checkable prerequisites from the
unfinished compiler realization in [the checklist](../implementation-checklist.md).
The [purecap ABI](purecap-abi.md), [memory plan](../../../proofs/MemoryPlan.v)
and requirements register retain their existing authority. These tasks neither
amend the ISA nor accept a compiler as purecap. Compiler sources, generated
compiler outputs and their replay scripts remain in the contained repository
identified by [the incorporation record](../../../THIRD-PARTY.md#compcert-and-secomp).

The starting compiler revision is
`cd1d3adbea95b9d7e1a25d335c4dd48e22435a6d`. Its existing capability carrier,
permission helper and representability helper are inputs, not new completion
credit. Initial scouting may inspect them and prepare diagnostics. Acceptance
of the three outputs below requires the focused evidence and separate review
stated here, followed by the integrator's host gate.

## 1. Inhabited capability memory

M1.2g-i qualifies the existing block-memory carrier against concrete inhabited
capability values. A replayable contained proof module must construct such a
value and an allocated memory state, store and reload the value through the
supported capability-sized chunks, and establish equality of the full value.
An empty value type, an assumed successful store or an unrelated integer
round trip does not meet this predicate.

Generate overlap cases from the carrier width and test every overlapping byte
position. Byte writes, an integer overwrite and malformed or incomplete
fragments must not produce the original capability. Nonoverlapping writes must
preserve the capability, and misaligned and wrong-chunk operations must have
explicit results. Record the distinction between the integer-width and
untyped-width chunks rather than treating every equal-width access as the same
operation. Boundary tests must expose an implementation that preserves a
capability after destructive writes.

Compile the proof module against source-identified dependencies, audit its
assumptions and kernel-check its output. Report inherited compiler assumptions
separately from any new ones; add no admitted proposition. A reproducible
receipt binds sources, commands and tool versions. The review must also state
whether capability-valued addresses, pointer arithmetic and source casts are
implemented. Block-memory tests do not substitute for those paths.

M1.2g-ii retains the actual source-value, address-operation and emitted
store/load joins. A successful logical memory qualification supplies no
generated target program or Sail tag-clear refinement theorem.

## 2. Pointer-kind diagnostic and lowering prerequisites

M1.2d-i owns a reproducible diagnosis over the actual contained compiler and a
reviewed account of the interface work the diagnosis requires. Start with
paired pointer and full-width integer source operations, including arithmetic,
memory traffic and a value live across a call. Retain the source, intermediate
dumps and emitted assembly from fresh output directories. Bind them to the
compiler executable, its configuration and matching source revision.

Identify the first intermediate boundary that merges the two value kinds and
follow that loss to the emitted operations. A source grep alone is insufficient:
the campaign must demonstrate the boundary on compiler-produced artifacts.
Preserve positive compilation evidence and state the missing target behavior
separately; a successful ordinary RISC-V compilation is not a purecap pass.

The resulting handoff states the obligations on source casts and authority,
value kinds through intermediate representations, arithmetic, copies and
spills, address materialization, primitive identity and plan-bound narrowing.
Assign the implementation and producer joins to g, d, e and f without creating
a second compiler owner. Distinguish the selected scalar ABI from the still
unresolved switcher protocol in the ABI's section 8. Do not select runtime tag
dispatch, reinterpret integer operations as capability operations, or weaken
the source contract as a diagnostic shortcut.

The diagnostic driver must refuse stale or missing outputs, a mismatched
compiler/source identity and a campaign that no longer exhibits its claimed
kind-loss boundary. Review the actual positive and refusal evidence. This
completes a diagnostic and prerequisite specification; M1.2d-ii retains frame,
call, primitive and cross-compartment realization and its target acceptance.

## 3. Plan-relative narrowing requests

M1.2e-i qualifies a total, composition-time decision over a declared parent
slot and a finite indexed family of child bounds. The request supplies the
parent base and length, byte offset, byte stride, inclusive last index and
child length. The granule is derived from the parent's length using the
existing encoding helper; it is not caller-selected.

Acceptance checks the parent's address domain and exactness, quantization of
its base and length, nonnegative request fields, parent-granule multiples for
offset, stride and child length, containment of the last child, and a child
base strictly below the address-space ceiling even for zero-length children.
Checker arithmetic is mathematical integer arithmetic; no target exponent
calculation or new instruction is introduced.

Prove that the decision is equivalent to its stated clauses. For every index
from zero through the inclusive last index, prove containment, valid address
domain and acceptance by the existing exact-narrowing helper, carrying its
round-trip theorem. Exhibit the correspondence between the byte fields and
MemoryPlan's granule-count fields. Do not claim a universal refinement between
the two developments merely from a matching witness or finite comparison.

Controls include admitted aligned requests, the exclusive 128-byte threshold,
zero-length and address-space endpoints, and generated changes to each checked
field. In particular, reject a child that the isolated bounds helper accepts
but whose offset, stride or length violates its parent's granule. Compile and
kernel-check the new statements, audit assumptions and exercise generated
accepted child bounds against the existing Sail oracle. Preserve evidence of
refusals separately from oracle agreement.

The caller still owes the selected region's membership in the actual plan,
provenance of every request and correspondence to every emitted narrowing.
M1.2e-ii and M1.2f retain that nonvacuous emission coverage. A compiler that
emits no narrowing cannot close them by passing this helper qualification.
