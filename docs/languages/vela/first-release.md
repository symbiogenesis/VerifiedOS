# Vela first supported release

This contract owns the first supported Vela software release's scope, primitive
semantics, module boundary and required library behavior. The
[primary design](verification-strategy.md) supplies rationale and examples;
[PLAN.md](../../../PLAN.md#vela-first-release-delivery) owns commissioning,
budgets and delivery order. The [requirements register](../../requirements-register.md)
remains normative for VerifiedOS. These are design decisions and acceptance
predicates, not a claim that the current prototypes implement them.

## Release boundary

The first product is a synchronous, bounded systems-language subset connected to
one retained compiler route. It supports explicit machine representations,
records and finite tagged sums, generics, stable dependent lengths and states,
exhaustive matching, `Option`/`Result`, bounded loops, shared and exclusive loans,
ownership transfer, resource-aware exits, closed effects and checked contracts.
Its resource discipline has fixed unrestricted, affine, relevant-verdict and
linear-obligation cases. Their permissions and disposal rules come from the
actual resource interpretation; an erased token or numeric annotation supplies
no authority by itself. Public interfaces fix representations, required-static
inputs, effects and resource contracts; ordinary local inference hides routine
derivations without weakening them.

Specifications and proofs may use the admitted mathematical definitions and
libraries in the existing kernel. A mathematical definition's expressiveness
does not imply a runtime representation or admission to executable type
conversion. The [mathematical prototype](elaboration-prototype.md) retains its
own supported subset; the [pure prototype](vela-prototype.md) and
[surface parser](surface-grammar.md) retain theirs. Parsing a larger feature does
not make it part of this release.

All language laws concern the elaborated image in an existing semantic anchor
under [the untrusted-elaboration boundary](../../spec.md#r-05-020a). Located source
syntax, binding and resource derivations are inputs to checked interpretation
and source correspondence, not an independently authoritative operational
semantics. The kernel must check the interpretation and requested laws for the
actual source closure. A well-typed generated term alone proves neither intended
source meaning nor concrete memory safety. Concrete CHERI laws, representation,
lowering, final bytes and applicable admission remain separate obligations.

The first end-to-end client uses caller-supplied storage and the
[synchronous core](core-design.md). Bounded pool allocation is a later library
increment within this software product, requiring its actual allocator, manifest,
exhaustion and reuse proofs; there is no implicit heap or boxing. The release
does not require arbitrary grade domains, runtime multi-shot or shallow handlers,
general reflection/generation, concurrent interior mutation, native self-hosting,
ISA replacement or hardware authorship. Async and one-shot control capture need
a separately accepted consumer and their own resource/lowering slice.

The [extended grade dossier](graded-foundation.md),
[control dossier](handlers-async.md), [mutation dossier](interior-mutability.md),
[metaprogramming design](metaprogramming.md) and
[whole-system contract](unified-source-contract.md) retain their extension
obligations. Selecting an extension requires a named client, a comparison with
the supported subset, a bounded implementation/qualification budget and a
decision predicate. A proposal's syntax or a demonstration assembled to exercise
the proposal is insufficient evidence of product need. Its omission changes no
VerifiedOS guarantee or mandatory compiler obligation.

## Primitive semantics

Every operation below has the same meaning in constant evaluation and runtime
code and under every assurance preset. Runtime representations come from the
selected target, never the build host. The
[existing integer policy](../../spec.md#r-05-144) requires explicit conversions,
total ordinary arithmetic and named modular/saturating operations. The language
binds that policy as follows; the target bridge must prove the binding.

| Surface or operation | First-release meaning |
| --- | --- |
| `bool`, `Unit` | Exactly `false`/`true`, and the single unit value `()`. Integers have no truthiness conversion. |
| `u8`, `u16`, `u32`, `u64`; `i8`, `i16`, `i32`, `i64` | Unsigned values range from zero to `2^w - 1`; signed values range from `-2^(w-1)` to `2^(w-1) - 1`. Bitwise signed representation is two's complement. `byte` is an alias for `u8`. |
| `usize` | Unsigned index/count arithmetic at the target's declared XLEN width. This is not a capability's representation, permission to address all values of that width, or a pointer/integer conversion. Target specialization fixes the width and its representability obligations. |
| Mathematical `Nat` and integers | Specification/static values with their mathematical operations. Runtime use needs a selected finite representation and a proved range relation; there is no implicit arbitrary-precision runtime. |
| Integer literals | Decimal, binary and hexadecimal digits with the [separator rules](authoring-tools.md#numeric-separators) denote exact mathematical magnitudes. A suffix or expected type determines the representation; an unconstrained runtime literal needs an annotation. No machine-default integer type is guessed. A syntactic negative integer literal is checked as one signed value, admitting the signed minimum; negation of an already typed expression obeys the ordinary range rule. An out-of-range literal is a compile-time error. |
| Ordinary `+`, `-`, `*` and unary `-` | Exact mathematical result with a proof that it is representable in the result type. Failure to discharge the premise is an unresolved obligation, not wrapping, trapping or a debug/release distinction. Operands have one explicitly determined type. |
| Ordinary `/` and `%` | Division truncates toward zero. For the mathematical quotient `q`, `a = q*b + r`, with `r` zero or of the dividend's sign and `abs(r) < abs(b)`. Both operations require a nonzero divisor; division additionally requires a representable quotient, excluding signed `MIN / -1`. Signed `MIN % -1` is exactly zero. A pair of runtime quotient/remainder results satisfies the equation only when the quotient is representable; the mathematical equation also describes the exceptional division input. |
| Checked arithmetic | Named `CheckedAdd`, `CheckedSub`, `CheckedMul`, `CheckedNeg`, `CheckedDiv` and `CheckedRem` return `Result<T, ArithmeticError>` with the ordinary value on `Ok`, otherwise the named `Overflow` or `ZeroDivisor` case. Division checks zero before signed quotient overflow; `CheckedRem(MIN, -1)` returns `Ok(0)`. They do not mutate their inputs or expose a partial result. |
| Modular and saturating arithmetic | Named `WrappingAdd`, `WrappingSub`, `WrappingMul` and `WrappingNeg` reduce modulo `2^w`, interpreting the resulting bits as the selected signed/unsigned type. `SaturatingAdd`, `SaturatingSub`, `SaturatingMul` and `SaturatingNeg` clamp the exact result to that type's minimum/maximum. There is no implicit modular conversion and no wrapping division/remainder in this initial vocabulary. |
| Bitwise operations and shifts | Bitwise operations use the selected `w` bits. Named `ShiftLeft` and `ShiftRight` take a `usize` count and require `count < w`; no implicit masking of excessive counts. Numeric left shift additionally requires the mathematical result to fit. Explicit `WrappingShiftLeft` discards high bits but retains the count bound. Right shift is zero-filling for unsigned and sign-extending for signed values, equivalent to floor division by `2^count`. `CheckedShiftLeft` and `CheckedShiftRight` return `InvalidShift` for an excessive count; the former returns `Overflow` for numeric left-shift range failure. |
| Conversions and comparisons | Checked conversion returns a named range failure; a proved conversion requires its range premise. Explicit truncation/reinterpretation uses a separately named bit operation. Ordering compares mathematical values within one type. Executable equality is Boolean through a selected decidable operation; proposition equality and transport stay in proof/contract interpretation. |
| Layout and encoding | Scalar representation/alignment is fixed by the target/ABI. Integer-to-byte encoding uses explicitly named little- or big-endian library operations; native record layout and padding never define a wire format. Capability fabrication and implicit pointer/integer conversion remain excluded. |
| Floating point | Not in this initial runtime release. A future consumer must select formats, NaN/signed-zero/rounding and exception behavior, equality/ordering, constant evaluation and target correspondence together. Parser recognition or existing hardware floating-point instructions supply no Vela support claim. |

Named operations are library interface commitments. The surface parser may need
no new productions for them, but implementations and operation laws remain to be
qualified. No generic operator overload can change these primitive meanings or
silently insert a conversion. Bounds failures use explicit checked APIs or proof
premises under the same rule; there is no unchecked indexing shortcut.

### Bytes and text

Source files are strict UTF-8. First-release identifiers retain the prototype's
ASCII identifier alphabet; string contents may contain Unicode. A `char` denotes
one Unicode scalar value (`U+0000` through `U+10FFFF`, excluding surrogates), with
a checked finite representation. A string literal denotes its exact UTF-8 bytes
without normalization, a terminator or implicit allocation. Embedded `U+0000`
is an ordinary scalar. Literal escapes are `\\`, `\"`, `\'`, `\n`, `\r`, `\t`,
`\0`, and `\u{H...}` with one through six hexadecimal digits denoting a scalar;
malformed/unknown escapes, invalid UTF-8 and non-scalar escapes are rejected.
Character literals decode to exactly one scalar. Raw byte data uses byte buffers
and explicit encoders rather than malformed text literals.

The initial text library uses an immutable validated UTF-8 view with represented
byte extent and the ordinary loan/lifetime contract. Decoding untrusted bytes
returns either that view with its validity proof or a typed encoding error;
neither path invents ownership or extends the input's lifetime. A mutable byte
alias cannot survive beside a validity-dependent immutable text view.

`ByteLength` counts encoded bytes. `ScalarCount` is an explicitly bounded
traversal; neither claims to count grapheme clusters or display cells. Text has
no ambiguous integer indexing operation: access its byte view, iterate scalars,
or use a checked byte-range slice whose endpoints are UTF-8 boundaries. Text
equality compares exact encoded bytes; canonically equivalent but differently
encoded scalar sequences remain distinct. Normalization, locale collation and
grapheme segmentation require separately specified libraries. Runtime-built
text uses explicit bounded storage, capacity outcomes and validation; literals'
read-only backing is charged to the composed image.

## Modules and packages

The module boundary must support two independently authored libraries before
public generic APIs qualify. A package manifest names its canonical package,
language edition, module roots, direct dependencies, explicit build inputs and
target/profile. A lock records each resolved package's exact source digest,
selected version/revision, transitive closure, generator/tool identities and
configuration. Locked builds neither resolve a different version nor read
undeclared ambient inputs. Fetching dependencies is an explicit preparation
operation; missing locked inputs produce an incomplete-build result.

The initial import graph is acyclic and imports are explicit. Cycles report the
cycle rather than depending on traversal order. Modules have no runtime
initializers; required-static initialization uses the
[bounded staging rules](metaprogramming.md#evaluation-and-phase-boundaries).
Qualified names resolve independently of import order. Duplicate local/imported
bindings are errors unless an explicit alias distinguishes them. A public nominal
identity comprises the resolved package instance, module path and declaration
identity. Two package revisions with the same printed type name are distinct;
neither structural similarity nor reflection can equate their private types.

The first trait/interface implementation model uses explicit nonoverlapping
instances. The defining package must own the trait/interface or the outer
nominal implementing type. A bare type parameter does not establish ownership;
foreign traits on foreign primitive types require a local nominal wrapper.
Instance heads use nominal type constructors, rigid constants and type
parameters, with structural unification deciding possible overlap. Arbitrary
computed type families and proof search are unavailable in instance selection.
Potentially overlapping instances are rejected without specialization, priority,
negative bounds or import-dependent choice. An interface fixes its qualified
instances or explicit dictionary parameters; adding an unrelated dependency
cannot change a selected implementation. Required laws are checked fields of
that dictionary, not facts obtained by finding its name.

Public signatures specify generic and required-static parameters, result types,
effects, call modes, transitive capture constraints, pre/postconditions and
resource exits. Private representations stay abstract except through explicit
published views or derivation interfaces. Implementation changes must re-establish
the exported contract. An interface fingerprint binds these semantic declarations,
the nominal identities and any exposed representation/ABI; source maps have a
separate exact-byte identity. Dependency records also include implementation and
proof bodies actually consumed, accepted assumptions, target and tools. An equal
interface fingerprint alone cannot reuse stale compilation or proof evidence.
Until finer dependency tracking is qualified, a semantic dependency change
invalidates the reachable component closure conservatively.

## Ownership libraries

The initial client needs a small, proved library of buffers, immutable/mutable
spans, bounded iteration, records/sums, initialization and typed errors. Public
operations state capacity, bounds, overlap, initialization, retained loans and
resource states on every exit. Iterators carry their bounds and loan contracts;
they do not require ordinary users to reconstruct a separation-logic proof at
each element. Codecs retain the platform's required format-description and
[boundary initialization obligations](../../spec.md#r-05-124).

`out T` retains its simple rule: no reads before initialization and a fully
initialized `T` on every normal return, including an error return. Fallible
construction instead consumes an owned storage/builder state and returns an
outcome-indexed state: a completed value, an explicitly retained initialized
prefix, or restored empty storage after total rollback. These are library types
and resource contracts, not an unchecked `MaybeUninit` escape. The initialization
map names exactly the fields/elements that may be read or disposed; dropping a
partially built object visits only those entries, accounts for their resources,
and restores the promised storage state. Failure must return storage and
unconsumed inputs or discharge them through an explicit proved operation.
Boundary-mandated whole-buffer initialization and zeroization are unchanged.

Construction, replacement and bounded collection growth must demonstrate failure
before the first write, partial failure, successful completion and rollback with
a live unrelated frame. No allocation, emergency capacity or cleanup retry is
implicit. A later explicit bounded-pool library additionally satisfies the
[pool declaration and exhaustion contracts](../../spec.md#r-08-046), with
reuse/quiescence proof before returned backing is lent again.

The receiver loan starts before explicit argument evaluation, using its declared
whole-object or named-view footprint. Preserve this simple first-release rule.
For a whole-buffer receiver, `buffer.Append(buffer.Length)` conflicts when the
argument reads the borrowed footprint. A diagnostic names both accesses and
offers a preceding immutable snapshot only when its evaluation and lifetime
preserve the program's meaning. Named disjoint views can avoid the conflict.
Two-phase receiver borrowing remains a separately priced option, triggered by
measured client friction rather than made a prerequisite for ordinary ownership.
No diagnostic may silently reorder effectful arguments or insert hidden loans.

## Qualification

The [delivery plan](../../../PLAN.md#vela-first-release-delivery) selects a real
bounded byte-buffer consumer and an independently chosen second client before
implementation. Their contracts must identify actual formats, entry states and
independently expected success/failure results. A candidate that only parses,
emits a term or returns an unconstrained theorem has not met this predicate.

| Subject | Acceptance evidence |
| --- | --- |
| Interpretation and concrete resources | Checked elaboration-image laws, an inhabited carrier state, read/write/initialization/frame and loan restoration, with wrong-offset, alias, premature-restoration and partial-initialization neighbors rejected at the intended obligations. Missing laws remain missing; no axiom or source judgment substitutes for them. |
| Scalar and text behavior | Independent boundary fixtures for every supported type and operation, signed division/remainder signs, zero and minimum/-1, shift zero/width-1/width, exact/wrapping/saturating arithmetic, target versus host width, invalid conversions, embedded NUL, malformed UTF-8/escapes, scalar boundaries and byte slicing. Static and runtime meanings agree under the same target. Generate finite boundary classes from an independently reviewed oracle; a shared implementation is not an independent expectation. |
| Package composition | Two independently authored packages compose with fixed instances; reordered imports preserve meaning; overlap, cycles and conflicting nominal identities are diagnosed. Locked builds reproduce their source/input closure. Contract, representation, proof assumption and tool changes invalidate affected evidence before reuse. |
| Everyday ownership | Bounded collection/iterator, receiver-snapshot, fallible-builder and error-propagation clients compile under their actual representations and the [borrow-analysis promotion contract](core-design.md#borrow-analysis-promotion); escaped views, duplicated tokens, reads of unwritten fields, stale current-content facts and lost mandatory outcomes fail at the responsible resource rule. |
| Complete software path | Authored source and independent contract reach one retained backend with checked correspondence, representation and lowering; applicable final-byte, resource, observation and admission duties meet their existing owners. Report source, artifact and production evidence separately. |
| Developer usefulness | Record annotation burden, first useful diagnostic, checking latency, code/stack/storage consequences and repair after a semantic-preserving refactor, a representation change and a real contract change on both clients. A held-out client cannot be redesigned to fit the candidate unnoticed. |

Hard safety, resource and admission limits are mandatory. Technical feasibility,
recurring authoring/maintenance benefit and eventual economic adoption are
separate decisions. Charge setup and shared maintenance fully, without requiring
the first two small clients to repay the entire language foundation. Any accepted
size/speed trade has a declared target envelope and per-case evidence; no average
hides a missed hard bound. The canceled [workflow comparison](workflow-contract.md)
retains its frozen experiment's identity and verdict, and supplies no current
product acceptance by implication.
