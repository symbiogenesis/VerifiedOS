# Scalar compiler kind interface

This contract resolves the preserved-kind decision returned by the
[compiler handoff](compiler-kind-handoff.md). It selects explicit typed
intermediate representations for the scalar backend owned by M1.2g-ii and
M1.2d-ii. It supplies an implementation interface and acceptance cases, not an
implemented pass, a compiler theorem or a target result. The
[source-value contract](compiler-source-values.md) owns source operations and
their definedness; the [purecap ABI](purecap-abi.md) owns register roles, frames
and calls. The requirements register and the pinned Sail definitions retain
precedence. The [route contract](../../languages/compiler-route-contract.md)
retains the separate production evidence and arbitrary-context obligations.

## 1. Selection and representation boundary

Every intermediate value, operand, result, memory access, formal parameter,
return and frame slot has an explicit kind in the IR. The kind is part of the
constructor or its mandatory typed operand/function declaration, serialized
with that IR and checked against every use. An auxiliary compiler analysis may
compute it, but an unchecked table alongside an untyped program is not this
interface. There is no default kind for an omitted declaration. A consumer
refuses an untyped input even when a dump, signature or inferred bit width
would let it guess the intended operation.

Source pointers remain abstract `Vptr` block-and-offset values through the
typed Mach representation. The representation-lowering boundary is Asmgen's
translation from that typed Mach program to the capability-aware target Asm
program. It introduces symbolic capability references and typed capability
operations, not physical addresses. Its relation is parameterized by the
composition map described in section 6. The assembler/composer resolves that
map and fixes concrete layout and derivation parameters at the final-image
boundary; target execution derives capabilities from its installed roots. An
unresolved symbol or authority obligation prevents final-image acceptance.
The resulting relation connects source pointers to complete capability values,
including tag and metadata. Merely adding `Vcap` to the value datatype, using
it as a concrete address without defining its operations, or printing a
capability mnemonic for an integer operation does not establish this boundary.
M1.2g-ii owns the relation and its source-memory side; M1.2d-ii implements the
typed target operations that consume it.

The kind is a static interpretation, not a test of the runtime tag. A null or
otherwise untagged capability representation still has capability kind. Its
permitted observations, failure and access behavior come from the source
contract and Sail relation. No pass chooses a scalar or capability operation
by branching on that tag.
An arbitrary invalid target capability does not thereby represent source
null; that correspondence is the source-value relation's obligation.

## 2. Kinds, operation forms and authority

The selected scalar value kinds are the following semantic categories. These
names describe the required IR constructors; they do not assert that the
contained compiler already declares them.

| Kind | Meaning and storage interpretation |
| --- | --- |
| `I32` | An ordinary 32-bit integer value. Narrow C integer objects use an explicit source-authorized extension or truncation and access width; signedness belongs to the operation. |
| `I64` | An ordinary 64-bit integer value. It carries no authority even when its bits equal a capability cursor. |
| `Cap` | A pointer representation preserved as authority-bearing data, including a null pointer. Its source block/offset relation and concrete tag/metadata are preserved together. |
| `F32` and `F64` | Floating-point values whose moves, arguments and spills use untagged scalar storage under the ABI. Their arithmetic remains floating-point arithmetic, never integer arithmetic selected by storage width. |

`Void` describes absence of a result and never a stored value. Uninitialized
or undefined values are states of the source semantics and initialization
analysis, not a kind that unifies `Cap` and `I64`. Aggregate layout contains
typed fields and padding; an aggregate is not a new untyped register kind.
The selected scalar ABI's unsupported aggregate, variadic, vector and
floating-point-computation signatures are refused at their existing boundary.
Recording `F32` or `F64` makes passthrough and refusal distinguishable; it
does not qualify the open vector-FP lowering or preservation convention.

Pointer role and authority evidence are distinct from these kinds. A `Cap`
operand may be data, stack, ordinary executable code, an exported forward
sentry, a return sentry or a sealed handle. Those roles, its required
permissions, locality, source object and bounds are facts in the existing
source/ABI/plan proof interfaces, not subtypes inferred from its bits. A kind
check proves neither dereferenceability nor the right to call. The concrete
value relation may carry different admissible authorities on different paths;
it does not replace them with a union capability having greater authority.
Linear/affine resource annotations retain their existing owner and travel
with the value relation. A same-kind copy is not permission to duplicate
writable authority, and a kind-correct use does not discharge ownership or
restoration. The interface references these obligations rather than keeping
another independent authority inventory.

Each instruction constructor specifies its operand kinds, result kind or
absence, addressed-memory effects and control effects. The finite typing
decision compares those requirements with its typed operands and declarations.
In particular:

- Integer arithmetic, shifts and bitwise operations consume and produce their
  declared integer kinds. Pointer advance consumes `Cap` and an explicitly
  extended integer displacement, producing `Cap` through the source contract's
  pointer operation. They are different IR operations even where the old
  backend used `Oaddl` for both. Explicit width/signedness operations and
  overflow side conditions remain required by R-05-144 through R-05-147;
  integer kind alone does not authorize implicit conversion or wraparound.
- Pointer comparison and difference use distinct operations whose source
  premises and result kinds are supplied by the source contract. They cannot
  be rewritten as integer comparisons solely because cursors agree.
- Every conversion is explicit. Source pointer-preserving casts retain
  `Cap`; the named `cgetaddr` source operation produces an ordinary cursor
  integer. Raw pointer/integer casts and capability-preserving integer
  typedefs are outside the selected source profile. R-05-136 and R-05-137
  forbid integer-to-capability reconstruction and exposed-address provenance;
  there is no reverse coercion or `CapInt` kind to repair a mismatch.
- A move, select or parallel-copy edge names one result kind and same-kind
  inputs. A recognized source null pointer constant is elaborated to the
  authority-free null constructor before this interface; a runtime integer
  zero and an unconverted `I64` constant are not `Cap`.
- A memory access names both its `Cap` address operand and its payload kind,
  size, alignment, volatility and extension/truncation behavior. A capability
  payload access is an explicit capability-access constructor. A scalar
  access through a pointer does not acquire capability payload kind. Its
  object/field access contract connects the payload kind to the selected
  typed layout under R-05-139; internal operand consistency cannot replace
  that source-to-access correspondence.
- A call names its complete argument/result signature, direct symbol or
  `Cap` indirect target, call role and declared clobber/effect contract.
  Primitive operations retain their exact profile identity and typed operand
  form under section 7. Barriers remain effectful through all passes.

The capability payload constructor may reuse the qualified block-memory
serialization machinery behind M1.2g-i. It may not collapse to the scalar
constructor because both use the same number of bytes. The physical width and
alignment remain the profile and ABI's facts. The implementation derives them
from those owners rather than introducing another width registry here.

## 3. Producer and consumer obligations through the IRs

Each pass consumes a kind-checked predecessor and produces a kind-checked
successor with a source/site correspondence. A pass cannot repair an invalid
predecessor by silently dropping a use. Unknown constructors, unresolved kind
variables, inconsistent declarations and unsupported operation forms are
named refusals. Optimizations may remove unreachable code only after checking
that its input is a valid member of the admitted IR.

| Boundary | Producer obligation | Consumer refusal |
| --- | --- | --- |
| Clight to Csharpminor | Derive value and payload kinds from elaborated source types before `typ_of_type` or `access_mode` can merge them. Emit separate pointer arithmetic, pointer conversions and capability payload accesses. Carry the same complete kind signature at definitions and call sites. | Pointer payload becomes a scalar access because `Mptr` aliases `Mint64`; a source cast has no selected interpretation; a source type has no supported lowering. |
| Csharpminor to Cminor | Preserve the distinction in expressions, temporaries, local/global object layout, accesses and function signatures. Lower structured expressions with explicitly typed introduced temporaries. | A source type annotation disappears before its last required operation has been expressed in a typed constructor. |
| Cminor through instruction selection and RTL | Preserve typed operations through every intervening representation, including CminorSel and RTL instruction selection. Declare kinds for pseudo-registers and all definitions and uses; selected address modes keep their base authority and integer index separate. | Address and payload kinds are conflated; an addressing-mode rewrite uses integer addition on its capability base; a selected opcode has no typed rule. |
| RTL optimization and allocation to LTL | Preserve kinds at all program points and across edges. Coalescing, splitting and allocation return a typed location assignment, liveness correspondence and typed inserted copies/spills. | A location assignment loses a live capability, a merge has inconsistent incoming kinds, or an inserted move/spill uses a storage-width default. |
| LTL through Linear and stacking to Mach | Preserve kinds after linearization and scheduling. Materialize typed frame slots and arguments under the existing frame convention, with complete lifetime and overlap evidence. | A slot's kind or lifetime is missing; a parent argument is loaded by offset alone; a reused live slot overlaps an incompatible payload. |
| Typed Mach to target Asm | Lower each typed operation under the selected source/concrete relation and composition map. Expand frame, call and primitive sequences with typed temporaries and effects; retain expansion provenance. | A target operation, temporary, relocation or expansion step lacks a rule, or its assigned register destroys authority still required by the expansion. |
| Asm through final composition | Preserve each rule's obligations through encoding, relocation, relaxation and any introduced stub. Check coverage against the decoded final bytes and typed linkage. | A final site has no admitted origin/rule, a stale identity is supplied, or a transformation changes an obligation without renewed evidence. |

This table covers the named pass boundaries, not just the dumps retained by
the diagnostic. A newly enabled pass or helper is part of the same traversal
and cannot bypass it because that stage was absent from the original dump
campaign. The implementation generates its constructor census from the
actual enabled compiler and refuses any constructor outside its typing and
emission rules. The census and diagnostics are derived views, not separately
maintained inventories.

For finite functions the structural checks are decidable: declarations are
unique, every operand resolves, every instruction has an admitted rule, and
every edge supplies the successor's declared live-value kinds. Loop headers
use declared invariants and the same edge check. A disagreement at a join is
a refusal, not a widening to a common eight-byte kind. Where the source
permits different pointer objects to join, `Cap` agrees but the authority
relation retains the path distinction and proves each subsequent use for
each predecessor. These checks do not themselves decide a semantic
preservation theorem or discharge its hypotheses.

## 4. Transformations, memory and copies

A transformation preserves both kind and the operation's source meaning.
For common-subexpression elimination the key includes the typed operation,
operands, applicable memory/effect version and authority-sensitive
obligations. Two pointers with the same cursor and different roots, bounds,
permissions, tags or sentry roles cannot be substituted using cursor equality.
Value numbering, constant folding and address simplification have the same
restriction. A derivation may be removed only when the retained value supplies
the required complete authority under the pass's relation.

Load/store forwarding and dead-store elimination consider payload kind,
access extent, possible aliasing and tag effects. An overlapping scalar or
partial write invalidates the earlier capability observation for forwarding.
A bytewise reconstruction cannot be promoted to a tagged capability merely
because its data bytes match. A disjoint access may preserve the earlier
value only with the required no-alias and effect evidence. Hoisting across a
guard must retain its definedness and failure behavior.

Typed pointer assignment, aggregate copying and the source contract's
capability-preserving object-copy operation retain complete capability
fragments. Byte-copy operations retain their distinct source meaning and
tag-destruction behavior. Copy expansion is checked against the selected
layout, alignment, extent and overlap semantics; it cannot convert a typed
capability copy into a sequence of scalar loads/stores. Uncertain layout or
overlap does not license such expansion: preserve a contracted operation or
refuse that lowering. The source contract owns which source spellings select
each operation and the defined result after partial writes.

Moves introduced by scheduling, parallel-copy resolution, inlining, outlining
and tail merging obey the same rules as source moves. A parallel-copy cycle
uses a temporary of the moved kind; its scratch allocation cannot overwrite
another live capability. Select/if-conversion chooses the capability-preserving
operation when the selected values have kind `Cap`. It cannot replace a
capability select with an integer operation over identical-width data.

## 5. Mixed allocation, calls and slot reuse

The merged architectural register file has one interference problem. Integer
and capability names for a physical register alias; they are not two
allocatable resources. The location kind is attached to a live range at a
program point, not permanently to the physical register. A register can hold
`I64` and later `Cap` only when the first lifetime has ended and a complete
definition of the second precedes every use. An integer definition clears
the previous tag under Sail; no later use may recover the prior capability
from the remaining bits.

Every split edge and spill/reload preserves its live value's kind. Capability
spills use the ABI's capability store and load, including return sentries and
back links. Integer and floating-point spills use their scalar forms.
Physical slot reuse requires disjoint lifetimes, the receiving kind's size
and alignment, and the initialization/lifetime transitions required by the
source and plan. No scalar byte occupying part of a dead capability slot
establishes a new initialized capability. No live scalar slot may overlap a
live capability slot. A local capability's permitted spill destination is
the stack authority the ABI names; matching slot width is insufficient.

Call-site and callee declarations agree on argument/result kinds and roles,
including stack arguments beyond the register set. At indirect calls the
typed callee set supplies that agreement. The caller preserves every live
value that the selected ABI clobbers, without treating an `s` register alias
as callee-saved. Argument setup, target setup and result placement are checked
as one parallel assignment with liveness; the indirect target cannot be lost
while filling arguments. Ordinary calls, exported entry calls and returns
retain distinct authority roles even when their values all have kind `Cap`.

The existing ABI owns frame layout, bounded call paths, parent-frame access,
scratch reservations and the absence of ordinary per-function narrowing.
The kind contract consumes that convention. A tail-call or outlined-helper
rule must separately satisfy its frame teardown, argument and return-authority
obligations. Cross-compartment lowering additionally consumes the reviewed
switcher protocol; an ordinary-call typing success supplies none of its scrub,
delegation, saved-state or nesting evidence.

## 6. Address materialization and root provenance

The source/concrete relation consumes a composition map from abstract blocks,
objects and frame instances to concrete regions, offsets, extents and admitted
authority. The composer supplies object/symbol identity, address and layout;
the ABI and installed-state producer supply the root or bounded table entry
from which that authority is available. The map is tied to the exact profile,
source closure, composition and emitted artifact. The backend does not invent
a root from a numerical address. Relocations resolve layout and instruction
parameters; they do not fabricate tagged capabilities from address bits.

Each materialization carries the selected object's identity, requested role,
source root/table-entry identity, derivation path, permissions and bounds,
plus the relocation expression and checked addend. The consumer verifies the
map lookup, root availability at that program point, permitted attenuation,
address representability and the emitted sequence's correspondence. Symbol
addition cannot change the referenced authority while retaining an old proof.
For a stack object the frame instance and typed layout supply the analogous
connection to `csp`; an absolute address is not a substitute for that link.

Writable data uses the composed data authority. PCC-relative materialization
can supply only authority derived from that executable root and cannot
manufacture writable-data permission under the split-root model. Code
materialization distinguishes ordinary executable pointers from exported
sentries. Link-time relaxation preserves the full selected derivation and
call role, not just its numerical destination. An unavailable root, mismatched
symbol/region, overbroad permission request or unresolved relocation refuses
final emission or composition at the boundary that owns the missing input.

## 7. Narrowing, primitives and final coverage

Every emitted narrowing carries M1.2e-ii's selected-plan region membership and
the source authority, byte request and provenance consumed by M1.2e-i's
decision. The emitter identifies its input operation and all target sites in
its expansion; optimization and relaxation renew or preserve that connection
under their checked rule. Coverage runs in both directions: each actual
narrowing site has an accepted request, and each requested operation is
implemented or removed by a recorded semantics-preserving transformation.
Unexpected, duplicated and orphan sites fail. The ABI's ordinary frames
provide no narrowing site and cannot supply the required nonempty positive
control for this acceptance.

Primitive membership and meanings remain the profile rows and their Sail
clauses, with the ABI's source binding to exact mnemonic and operand form.
The implementation derives typing and emission coverage from those owners;
this contract creates no primitive list. Unknown names, a legal mnemonic in
the wrong form, out-of-range immediates, wrong operand kinds and unsupported
privilege/effect premises are explicit refusals. A source binding keeps its
identity through elaboration and emission. Barrier effects constrain motion
and elimination; a call-shaped builtin cannot erase them.

The final artifact coverage includes compiler expansions, assembler expansions,
relocations, relaxations and linker-created code. The emitted record is
content-bound to the exact sources, options, IRs, selected profile, plan and
image. Reusing a record after any dependency changes is refused. The existing
assembler/composer and R-05-023a validation own the final-byte evidence; the
kind checker is neither a replacement admission checker nor a new proof
foundation. M1.2f owns the real compiler-to-Sail functional comparison and its
independent reproduction.

## 8. Acceptance and adversarial controls

Implementations of this interface must supply a nonempty, kind-correct
positive program beside each applicable refusal. Generated cases use the
source/type/layout owners where an oracle exists. A malformed fixture that
never reaches its intended checker is reported separately from a rejected
well-formed transformation. The following pairs decide the interface's
coverage; they are requirements on future evidence, not results recorded here.

| Positive case | Adversarial change and required rejecting boundary |
| --- | --- |
| Equal-width pointer and integer payload copies remain distinct from Clight through final instructions. | Change the pointer payload access to scalar while retaining the signature: the source-to-access correspondence fails even if the mutated IR is internally kind-correct. Signature-only recovery must fail this test. |
| Null and non-null pointers join through explicit `Cap` values. | Replace the source-elaborated null constructor with an `I64` constant or omit one edge kind: the join checker refuses it. |
| Two pointers share a cursor while retaining different authority. | CSE substitutes the wider, differently rooted or differently permissioned value without a relation: the transformation evidence fails despite equal cursor bits. |
| A capability store/reload survives a disjoint scalar write. | Move that write to each overlapping byte or forward through it: the memory/tag relation rejects preservation of the original capability. |
| A capability copy and an ordinary byte copy follow their source contracts. | Scalarize the capability copy or assert tag reconstruction from bytes: the copy lowering/refinement fails at that operation. |
| Mixed integer and capability values remain live through nested direct and indirect calls, including stack arguments. | Spill a capability as an integer, use an `s` alias as preserved, clobber the indirect target during argument setup or mis-type the ninth argument: allocation/call checking refuses the specific defect. |
| One physical register or slot is reused after the previous lifetime ends. | Keep the previous capability live, overlap another live slot or read the reused location before complete initialization: liveness/slot checking refuses it. |
| A writable global is reached from its declared data root. | Replace it with PCC-derived authority or change the relocation's symbol/region: materialization checking refuses the mismatch. |
| A nonempty plan-admitted narrowing maps to its actual emitted sites. | Remove plan membership, substitute a locally exact but plan-invalid request or insert an unrecorded site: narrowing coverage refuses it. |
| A primitive binding retains its exact identity, operands and effects. | Rename its profile key, alter its operand form, overflow an immediate or move a memory effect across a barrier: primitive typing or the pass's effect relation refuses it. |
| The decoded linked image is covered by current typed emission evidence. | Add a stub, change a relaxed instruction or reuse evidence from an earlier image: final coverage or identity checking refuses it. |

M1.2g-ii supplies source-value and memory relations; M1.2d-ii supplies typed
passes, allocation, ABI and primitive emission; M1.2e-ii supplies selected-plan
narrowing; M1.2f joins real outputs to the assembler, composer and Sail. Each
owner records implemented constructor coverage, focused proof/test receipts,
unsupported cases and failed controls at the tested revision. Source
compilation, an unchanged assumption count or the contract's review supplies
no claim that these implementation obligations are complete.
