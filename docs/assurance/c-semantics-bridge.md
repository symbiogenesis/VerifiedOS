# Stock Clight to compartment Clight: statement and premise

Q35j states the bridge that a VST client would need between stock Clight 3.17 and
the contained compiler's Clight at `1cd36c710967e89db21da08f237ffca78843b883`.
The authored [statement](../../tools/c-semantics-bridge/Bridge.v) is held outside
`proofs/` and compiled in a private switch. It does not prove the simulation,
admit VST, establish source correspondence, or supply a compiler certificate.
The [foundation qualification](c-refinement-foundation-qualification.md) and
F-464, F-489 and F-495 retain those decisions.

## Artifacts and fragment

The source semantics is the exact `compcert/cfrontend/Clight.v` in VST 2.17's
bundled subset, whose `VERSION` states 3.17. The target semantics is the exact
contained `cfrontend/Clight.v`, with `common/Values.v` carrying `Vcap`. Both
are imported, under distinct logical load paths, rather than transcribed into
the statement. Syntax translation functions describe the relation between the
two ASTs; they define no execution relation.

The fragment includes the constructs in the kernel's
[cold executive C](../../kernel/src/executive.c): integer and long constants,
plain structs and arrays, ordinary pointers, temporary and local variables,
address-taking, dereference and member access, casts, integer operations,
assignments, sequences, branches, loops, break/continue, returns and internal
calls. Types retain their signedness, width, bounds, attributes and names.
The stock x86_64 configuration defines 64-bit source pointers. The contained
`riscV/Archi.v` leaves `ptr64 : bool` a parameter even though the extracted RV64
compiler selects `true`. `program_pair` therefore requires exactly
`Contained.riscV.Archi.ptr64 = true` when the program uses pointers, memory,
layout queries or calls. Its register-only subfragment needs no such equality.
This is an explicit architecture binding to establish for an executive client,
not a replacement definition or an added global axiom. The proof plan must
prove the remaining integer and composite layout agreement; another target's
host client supplies no agreement.

The syntax predicate refuses floating-point and volatile types, unions,
bitfields, variadic or unprototyped calls, builtins, switch, labels and goto.
The global-definition relation contains internal functions. Before a real
front-end output can inhabit it, any unused predefined external declarations
must be removed by the separately checked normalization described below.
External calls, inline assembly, capability primitives and objects containing
capability values are outside this increment.

The executive source defines functions and no global objects. The relation
admits those functions but excludes global object definitions; a consumer must
link them with a corresponding harness using local storage for its table and
cursor. `program_pair` preserves the complete definition list, composite
declarations, public names and main identifier. It does not assert that an
arbitrary identifier is a valid entry point. Whole-program use must supply a
well-formed `int main(void)` harness and establish inhabited initial states
under the two imported rules. The non-vacuity witness uses that exact signature.

The compartment is one fixed argument to `map_function` for the whole executive
fragment. Each corresponding target function receives that `fn_comp`; the
target semantics itself still supplies that compartment to allocation, loads,
stores and returns and checks its program policy. The proof must construct the
memory ownership and program-policy correspondence. Ignoring the argument or
assuming the existing compartment proofs apply to stock memory is insufficient.

An ordinary source pointer stays `Vptr(block, offset)` at the target Clight
layer. `Vcap` has no inverse image in this bridge, and `state_cap_free` refuses
it in temporary values, call arguments, returned results and readable memory.
Thus `vos_slot_disjoint`'s pointer arguments and
`vos_frame_pairwise_disjoint`'s array indexing remain in scope. The contained
backend's source-kind elaboration converts ordinary C pointer roles to purecap
machine roles later; this statement makes no assertion about that later
representation, capability bounds or the emitted bytes.

## Simulation obligation

`bridge_statement` universally quantifies a `FrontendCorrespondence` input
and asks for `silent_forward_simulation` of its two programs, using each
implementation's `semantics2` transition rules. A proof must construct a state
relation, match every stock initial state with a target initial state, keep
related target states capability-free, preserve terminal integer results, and
match each stock step by a nonempty finite target execution. Source and target
traces are exactly their respective empty traces: the fragment exposes no
external or volatile event. There is no zero-step escape or assumed simulation
lemma in the premise. Using an existential state relation leaves its
construction to the proof while fixing the observable conclusion.

The forward direction preserves stock executions of defined C. Extending it to
VST's particular safety/correctness judgment requires the appropriate safety
transport and trace/determinism argument for that judgment. A forward diagram
alone is not a blanket claim that target undefined behavior is impossible.

## Front-end correspondence and producer

The premise names the source closure, both complete ASTs, the producer and the
target compartment. It carries two independently supplied producer relations,
`stock_produces` and `contained_parses`, and structural `program_pair` evidence.
Neither producer relation may be defined as execution agreement or as the
desired simulation. A production consumer fixes them to its pinned producer
results, exact preprocessing closure and command options; arbitrary relations
chosen by a client supply no evidence about an actual C build.

For VST the producer is explicit: `HandAuthored` for the witness here, or
`LicensedClightgen` for a real `clightgen` output. The latter requires the
license and output provenance F-489 records. VST libraries built from the
dual-licensed subset do not supply `clightgen`. A hand-authored AST for the
executive requires its own source-to-AST correctness evidence; resemblance
to the C is not that evidence.

The required front-end correspondence has these stages:

| Stage | Required comparison |
| --- | --- |
| Source and preprocessing closure | The same content-addressed C, headers, include resolution, macros and selected integer/pointer declarations enter both producers. Target options are bound; a prior aarch64-generated client checked under x86_64 supplies no agreement. |
| Parsing and elaboration | The stock input and the contained compiler's parsed source represent the same declarations, types, expressions and name bindings. The actual producer's unverified front end remains an explicit premise until this relation is proved. |
| Expression and local normalization | `clightgen`'s selected `SimplExpr`/`SimplLocals` configuration and the contained compiler's passes are related under the selected temporary-parameter semantics. Their ASTs need not be assumed byte-identical. |
| Unused predefined declarations | Remove only unreachable external declarations, preserving name resolution and executions, so both programs inhabit the internal-function fragment. A compiler-added builtin reached by the executive defeats this premise. |
| Compartment annotation and policy | Insert the one executive compartment and construct the contained policy obligations, without changing an operation or granting additional cross-compartment authority. |
| Complete AST relation | `program_pair` relates every global definition and composite, and preserves public identifiers and the entry identifier. Source bytes, producer outputs and the normalization evidence belong in the same artifact binding. |

`FrontendCorrespondence` is not an axiom or a verified parser. Its concrete
witness uses the exact source string `int main(void) { return 0; }`, a
hand-authored stock program and a corresponding target program constructed
through the target's own `make_program`. The witness producer relations are
equalities to those concrete values. Separate evaluation witnesses inhabit
both implementations' constant-return semantics. This proves the premise is
inhabited and the execution domains used here are nonempty; it does not certify
the real parser or the executive's source closure.

The refutation's actual target function declares a pointer parameter and a
distinct pointer temporary; its body copies the argument and then returns
zero. A capability-bearing caller supplies that declared parameter.
`capability_call_entry_step` and `capability_body_entry_step` establish
reachability of the assignment from that function's call state in its own
program. `capability_producing_step` constructs the assignment step;
`capability_instance_refuted` shows its result violates `state_cap_free`.
It distinguishes the fragment from a program execution producing a capability
value. It claims no creation of tagged authority from an integer.

## Proof plan and anchor decision

| Increment | Exact obligation | Price |
| --- | --- | --- |
| Producer binding and normalization | Establish the stages above over the selected actual stock input producer and contained parser; retain each pass's intermediate AST and source identity. | unpriced: the admissible production input producer and its exact output pair have not been selected or measured. |
| Type, composite and layout correspondence | Prove signedness/width, parameter types, field offsets, `sizeof`/`alignof`, access modes and cast/classification agreement for the fragment. | unpriced: the primitive-operation proof census and the actual normalized executive AST pair are not available. |
| Values and compartment memory | Relate integer values by their represented bits and ordinary pointers by a common block/offset mapping; show source memory operations correspond to target operations for the executive-owned blocks, preserving permissions and capability exclusion. | unpriced: no preservation proof has been trialed and compartment ownership introduces obligations absent from stock memory. |
| Expressions, lvalues and lists | Prove simultaneous evaluation correspondence over the preceding laws, including array/struct pointer arithmetic and defined-operation side conditions. | unpriced: depends on the preceding unmeasured laws; no reuse percentage is defensible. |
| Calls, allocation, continuations and returns | Relate temporary-parameter function entry, allocation/free, internal calls and the target's return type/compartment fields. Construct corresponding initial global memories and policies. | unpriced: depends on the concrete front-end/program policy and memory relation. |
| Small-step diagram and observation transport | Prove every admitted statement case, lift to nonempty finite target runs and terminal results, prove the capability-free invariant, then connect the particular VST client judgment. | unpriced: the state relation and required client judgment are not yet measured. |

No compiler-backend pass is proved by this bridge. R-05-024's contained backend
preservation and the post-CompCert correspondence obligations keep their owners.
No time estimate for establishing this simulation is inferred from compiling
the statement or from another foundation's successful build.

For R-05-020, the proposed bridge is Coq-native proof transport between imported
semantics. Its statement shows what must be mechanically bridged; only its
completed, checked proof would demonstrate that condition. For non-duplication,
all admitted target claims must quantify the contained anchor's exact artifact;
stock Clight may be used to discharge clients through the bridge, but cannot be
silently counted as that artifact. For retirement, a completed bridge would
retire the unproved stock-Clight-to-contained-Clight correspondence premise for
the consumers in its fragment. It retires neither the unverified front end nor
any other interim by assertion. An admission record must name the actual
consumers and the evidence that the replaced premise is gone.

R-05-019a therefore remains a refusal against treating the two Clights as one
artifact today. This statement supplies a precise proposed route to the anchor;
F-464's review act still must decide the program logic, the demonstrated bridge,
retired premise and accepted assumptions under R-05-164. An unproved definition
of `bridge_statement` supplies no eighth-anchor exception or admission evidence.

## Private checking and incorporation

The contained snapshot is the parent's private archive of the accepted revision,
SHA-256 `cc790f82d126cdecd4b74bde8182946dfb329b42a4df059f7abf9baa399838f5`.
The contained `Clight.v` is SHA-256
`208e9adce9a24b90320cc686d5b0539e8b3e0588a7b6a4ebd90c7a01cd5a7f15`,
`Values.v` is `34f0fb03e0444178b1870ea7758a155cc952e60693780ef5f2edecc5b868fa1a`,
and the selected stock `Clight.v` is
`53cef4b5c923084999949229c3fdb065a25833d7f3761a1285adbaeebaaf79d0`.

The actual two CompCert `LICENSE` files have the same SHA-256,
`40e8151cb26269a4e051309a958714191a706b5dfc7aaec00a61137cb338a648`.
They expressly dual-license `Clight.v`, `common/` and `lib/` under
LGPL-2.1-or-later or the INRIA Non-Commercial agreement; the compiler contains
other files covered by the latter. The existing M1.1a containment is maintained.
VST 2.17's `LICENSE`, SHA-256
`1681071efc9cb22a656dbbe7130327359b2f2e72ee0bb622ae24ff08522fcaed`,
states BSD-2-Clause for its distribution with the CompCert exceptions named.
Flocq 4.2.2's source headers elect LGPL-3.0-or-later; its `COPYING`, SHA-256
`da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768`,
contains the LGPL version 3 text. These are private evaluation dependencies.
Only authored source, the record and small receipts/logs are offered here;
no upstream source, compiled library or switch is conveyed.

At Rocq 9.3.0 and 9.2.0, the unchanged accepted contained `common/Memory.v` refuses its
`drop_perm`/`loadbytes` proof at the existing `perm_order` goal. That compiler
port belongs to Q39. The instrument selects the already installed Flocq 4.2.2
source dependency without rewriting it. Neither compiler refusal is a
successful proof repair.

The accepted source still declares the F-522 axiom `ec_public_first_order` in
`common/Events.v`. Its presence prohibits claiming an accepted whole-environment
closure from this instrument. Statement elaboration, and the per-constant
assumption readings of the authored witness/refusal, have a narrower scope than
kernel admission of the imported environment. Q39 retains the source/prover
qualification and exact environmental audit.

The unchanged stock and contained Clight dependency closures, followed by
the authored statement and witness/refutation constants, compile with the
existing distribution Coq 8.20.1, compiled with OCaml 5.4.0. The command selects
`verifiedos-q35e-vst3-20260928` only as a private execution environment and invokes
`/usr/bin/coqc` and `/usr/bin/coqdep` explicitly; it does not use that switch's
Rocq 9.2.0 binary or mutate its packages. The statement uses `-w @all`; imported
legacy sources use the recorded `-w -all`. Q39's known legacy-kernel limitations
remain. This is the item's private statement-compilation predicate, not
shared-lock qualification, axiom-free proof acceptance or a whole-environment
kernel result.

The native `About` and `Print Assumptions` readings identify the statement as
a transparent `Prop` definition and show the following dependencies. Here
`C` abbreviates precisely `ClassicalDedekindReals.sig_not_dec`,
`ClassicalDedekindReals.sig_forall_dec`,
`FunctionalExtensionality.functional_extensionality_dep` and
`Classical_Prop.classic`; `E` names both `external_functions_sem` and
`inline_assembly_sem` in the stated implementation. The bare `Archi.ptr64`
in the diagnostic is the contained parameter, not an equality to `true`.

| Reading | Native assumption names |
| --- | --- |
| `bridge_statement` | `C`, contained `Archi.ptr64`, stock `E` and contained `E` |
| `witness_FrontendCorrespondence` | contained `Archi.ptr64` |
| Each capability execution step | `C`, contained `Archi.ptr64` and contained `E` |
| `capability_instance_refuted` | `C` and contained `Archi.ptr64` |
| `witness_source_return_step` | `C` |
| `witness_target_return_value` | `C` and contained `Archi.ptr64` |

These are exact per-constant elaboration readings. They do not substitute for
Q39's environmental audit or decide their R-05-164 admission. No simulation
proof search occurred. The narrow statement and refutation qualification does
not change a frozen admitted theorem or claim that F-522 is discharged.

The full authoring interval was not captured, including the early reading and
provisioning work. Q35j keeps its 16-hour estimate and reports actual `n/a`,
excluded from calibration. Receipt `compile_seconds` values measure only
imported compilation subprocesses; they are not item authoring time or prices
for the future simulation proof.

The following records are verbatim retained copies at their cited native paths.
The instrument receipt binds the exact invocation, explicit compiler binaries,
private execution prefix, contained archive identity and authored source hashes.
The closure receipts bind every selected imported source and object; those
objects and upstream sources remain in native private storage. The successful
authored statement is frozen at SHA-256
`2bf2354e81f3178113bbca901fc09b1d1fa94753c4edb86fa97b233891a3ed0e`.

| Record | Retained native path and SHA-256 |
| --- | --- |
| Exact invocation and instrument | [`/root/build/lane-solve-20261010-b/c-semantics/check820/instrument-receipt.json`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check820/instrument-receipt.json), SHA256 `8b5091e35d78a1062d2590b9bb3abe86d68786e410144de54f792198fe9f30ab` |
| Successful statement receipt | [`/root/build/lane-solve-20261010-b/c-semantics/check820/report.json`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check820/report.json), SHA256 `c9a6a9cfdf9f16d4a4788f9906fc19ada31d3757a85b6ebc2be3649c0afddee3` |
| Imported source/object closure | [`/root/build/lane-solve-20261010-b/c-semantics/check820/upstream-report.json`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check820/upstream-report.json), SHA256 `827b0e534a733b589c0172df4b3b9201e7df7b6bb000483c36a490ea1d954cc0` |
| Compatible prover version | [`/root/build/lane-solve-20261010-b/c-semantics/check820/prover.log`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check820/prover.log), SHA256 `627ca2d6330687c61eb17426f18683ab82fc2e71ca503967c1e4a2fd187b03c3` |
| Raw elaboration and assumptions | [`/root/build/lane-solve-20261010-b/c-semantics/check820/statement.log`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check820/statement.log), SHA256 `ad879f51ecc6aa9803e344ce415424a65bd7e5f431c74fb350b50069950d2f92` |
| Checked authored Gallina | [`/root/build/lane-solve-20261010-b/c-semantics/check820/statement/Bridge.v`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check820/statement/Bridge.v), SHA256 `2bf2354e81f3178113bbca901fc09b1d1fa94753c4edb86fa97b233891a3ed0e` |
| Checked authored instrument | [`/root/build/lane-solve-20261010-b/c-semantics/check820/statement/check.py`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check820/statement/check.py), SHA256 `ef6bc28eb9582b9936456875ddf0042f8c0a7985a9116c285b3c00929e802ed0` |
| Rocq 9.3.0 version | [`/root/build/lane-solve-20261010-b/c-semantics/check/prover.log`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check/prover.log), SHA256 `4fc6711c2d07dd908fd6ab23af8fa41f7d0b950b18373fe2b6fe21451c416761` |
| Rocq 9.3.0 contained refusal | [`/root/build/lane-solve-20261010-b/c-semantics/check/Contained-Memory.log`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check/Contained-Memory.log), SHA256 `c1f9ac5037bfdf3e6e1374baf0c70c2346a6ed8f35619662085baf7bce1c0365` |
| Rocq 9.2.0 version | [`/root/build/lane-solve-20261010-b/c-semantics/check92/prover.log`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check92/prover.log), SHA256 `07e8b997f9238997ddba485030523c4c56de1ccb96945af9ffff5311e8e988f4` |
| Rocq 9.2.0 contained refusal | [`/root/build/lane-solve-20261010-b/c-semantics/check92/Contained-Memory.log`](../implementation/retained-evidence/root/build/lane-solve-20261010-b/c-semantics/check92/Contained-Memory.log), SHA256 `6e54dfa0f763948dd003afdf41307ed5a2628d39a17acb41912e9ac50fa931a8` |
