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
stated here. The integrator requires Host CI to pass and dispatches Guest CI on
GitHub Actions for the settled revision, then records the run and pending status
and finishes without waiting for its verdict. The user monitors Guest CI and will
report any issues; pending is not passing evidence. Contained compiler checks
remain separate acceptance evidence.

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
a second compiler owner. Distinguish the selected scalar ABI from the switcher
protocol that was unresolved at the diagnostic boundary; section 4 below owns
the review needed to select that protocol. Do not select runtime tag
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

## 4. Reviewed source, kind and switcher agreement

The next prerequisite is an implementable producer/consumer agreement for the
decisions identified by the [kind handoff](compiler-kind-handoff.md). It is
contract work within M1.2g-ii and M1.2d-ii, with no separate completion credit
and no change to their estimates. Contract review can proceed before the
compiler implementation and target joins.

The agreement has three owners. The source-value contract chooses the
abstract/concrete value boundary and specifies casts, arithmetic and memory
behavior. The kind interface chooses how each compiler stage retains the
information needed by its consumer. The scalar ABI chooses the switcher's
edge transport, protected state, scrub sequence and authority. Each owner
states the unsupported cases and the evidence its implementation must supply.

Acceptance is a full Tier-A read of those contracts and their governing
register, model and route clauses. Review must decide all of the following:

* Every source operation has a value representation and a kind-preserving
  path, or an explicit compile-time refusal. A refusal identifies an unsupported
  implementation case; it cannot redefine source behavior or satisfy a
  production-completeness obligation.
* Every lowering boundary has a named producer and consumer. Same-width
  pointer/integer pairs, joins, spills, stack arguments and optimization-created
  operations remain distinguishable. Missing coverage refuses compilation.
* The value relation identifies composition-supplied authority, including
  writable globals, and exposes its unproved obligations. A kind annotation,
  source hash or accepted bounds helper is not a refinement theorem.
* The switcher can obtain its own authority using the actual ISA, transport
  every admitted argument, preserve protected caller state, and clear its
  transient authority before either boundary transfer. Nested calls, refusal,
  return and interrupted execution have explicit state obligations. No step
  may assume that a sentry also installs a data capability.
* Source, kind and ABI choices agree on scalar signatures, null and tag state,
  call effects, local capability lifetime and unsupported forms. A cross-review
  by a lane other than the author reads these joins, and the integrator resolves
  every finding before landing the agreement.
* The implementation campaign has nonempty positive cases and a discriminating
  refusal or fault for each boundary. Tests of a handwritten sequence cannot
  be reported as compiler emission, and a green document gate cannot be
  reported as a source-to-Sail proof.

The integrator owns the shared handoff and checklist updates, the settled Host CI
verdict and Guest CI dispatch with pending status on GitHub Actions, under the
handoff above. This agreement changes no compiler
implementation, extraction manifest or proof statement; generated requirement-reference
fingerprints follow their owner. M1.2g-ii, M1.2d-ii, M1.2e-ii and M1.2f remain open
until their existing implementation and target predicates hold.
