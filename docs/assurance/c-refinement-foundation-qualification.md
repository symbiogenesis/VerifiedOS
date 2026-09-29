# Source-level C-refinement foundation qualification

This is Q35e's record in [the implementation plan](../implementation/implementation-checklist.md#q-assessment-actions). It applies [U-20's pattern](unassigned-proof-map.md#7-the-next-slices) to the four foundations the specification names for proving trusted C against its Gallina model: VST's non-Iris line, VST's Iris line, RefinedC, and the CN-to-Coq closure. Each was built at the locked prover in a private switch or its failure recorded; a client in each built foundation's own input form was checked; and the kernel checker's whole-environment context summary was read as [the proof gate](../../tools/README.md#current-evidence-and-generated-documentation) reads it. No register entry moves here. The review-gate acts [F-463 and F-464](findings-register.md) name consume this record.

**Result.** No foundation passes the gate's kernel reading unchanged.

- **VST's non-Iris line, 2.17,** builds at the locked prover both through opam, which installs CompCert's non-commercial package, and from its release archive over the CompCert subset it bundles, which is entirely dual-licensed. The client checks over both. The kernel checker then aborts with an anomaly on a module every Verifiable C client loads, so the gate obtains no summary and refuses (F-486). With that one module admitted unchecked, the summary names 380 constants, 17 of them declared axioms or parameters and 363 fields of sealed modules; a fully checked VST closure still names 204 proved fields as axioms (F-487).
- **VST's Iris line, 3.2beta,** does not install beside the prover, and its release archive fails to build at the prover with the Iris release its package names (F-488).
- **RefinedC** at `2e89846b` is refused by the solver at the prover because it pins Coq 9.1.0. With that one bound ignored and no source edited, it builds at the prover, its client checks, and the summary names exactly three constants: one declared axiom and two unused test parameters (F-490, F-492). Its semantics is Caesium rather than any Clight, and the gate's compile settings refuse its client's imports (F-491).
- **CN-to-Coq** is refused by the solver: its closure needs a package no registered repository carries and pins Coq 8.20.1. Its resource-inference relation also accepts every solver-side constraint by a placeholder constructor (F-493).

The record closes with a proposed R-05-164 amendment for RefinedC, which is the only foundation whose summary the gate can read, and with priced repairs for VST, which is the foundation R-06-012, R-10-008 and R-18-026 name. Admitting either also needs the R-05-020 record and C-semantics decision F-464 names, and no bridge from either foundation's C semantics to the contained compiler's Clight exists (F-495).

## Identity, containment and method

Every reading was taken by the Q35e implementer lane from base revision `41fc2086850670eacae03c0f972c1233689ba9ba` in the WSL guest, an `aarch64` Ubuntu with 12 logical CPUs and opam 2.5.0, under the lane root `/root/build/lane-q35e-impl-20260928`. The lane's receipt [`/root/build/lane-q35e-impl-20260928/receipts/q35e-record.json`](../implementation/retained-evidence/root/build/lane-q35e-impl-20260928/receipts/q35e-record.json), SHA-256 `e9950bb45911b979a3546de132bf2d777ecf05f7513e0f9948651df2fc6d3b5a`, binds every source archive, revision, license file, switch export, log and summary cited below by path and SHA-256, carries every solver output whole, lists every name each summary reports with its classification, and carries each build failure's deciding excerpt. Figures below are quoted from it.

- **The locked prover** is [rocq.lock](../../tools/opam/rocq.lock): Rocq 9.2.0 on OCaml 5.4.1. The proof switch `verifiedos-rocq-9.2.0-ocaml-5.4.1` exported byte-identically to that lock, SHA-256 `32da801c0f13fc47f0c8c85aa6d324eb209e789fec6beec14af9ce6e88d718fa` with LF line endings, at the lane's start and at its end; its switch state was last written on 2026-09-28 at 00:15:58 -0500, before the lane began. Nothing was installed into it.
- **Metadata.** Every solver reading ran against the local repositories as last written on 2026-09-27 at 23:09:53 -0500: `default` at stamp `bbc4314c37cbe5902ab659460c440b099fe729a3` and `rocq-released` at stamp `2026-09-26 16:46`. No `opam update` ran. Q35a's simulations were taken against the same metadata; this record re-establishes them rather than quoting them.
- **Switches.** Four new switches, each created empty with `--no-switch`, hold every build and solver reading: `verifiedos-q35e-vst2-20260928`, `verifiedos-q35e-vst3-20260928`, `verifiedos-q35e-refinedc-20260928` and `verifiedos-q35e-cn-20260928`. [The switch recipes](../../tools/opam/c-refinement-qualification-switches.md) record their seeds, pins and installed sets. The first installs `coq-compcert` 3.18 and so carries the INRIA Non-Commercial License Agreement; under M1.1a's containment all four stay private to the guest and out of hosted CI's public proof lane. Upstream source, built libraries and client products stay under the lane root; nothing from CompCert, VST, RefinedC or CN is copied into this repository.
- **The gate's reading** is `rocqchk -silent -o` over the named root with no module admitted, as the gate's fresh run invokes it, parsed by the gate's own `vos.proofaudit.kernel_context` against the gate's declared set, which is empty. A run that writes no summary is refused by that parse. Where the recursive check cannot finish, a second reading admits the one failing module with `-admit`, as the gate admits a root with prior evidence; that reading is supplementary, because no prior evidence for that module can exist.
- **Positive control.** Each summary's control compiles a module that requires the client and declares `Axiom q35e_positive_control_unused : nat.`, and is read the same way. It holds when the control's names are the client's plus exactly that one.
- **Classification.** Each reported name is classified from the library source that defines it: `declared` when that source introduces it with `Axiom`, `Parameter` or `Conjecture` at top level or in an interactive module's body, `module-field` otherwise. The receipt carries each name's class and source path.
- **Clients.** Each client is a function returning whether two slot records are disjoint, one ending at or before the other begins, the shape of `vos_slot_disjoint` against `disjoint` in [CyclicExecutive.v](../../proofs/CyclicExecutive.v); it is authored for this qualification and is not the kernel's C. Each specification's result is a non-constant function of the inputs, and each client carries witnesses that touching slots are disjoint and overlapping ones are not, that the precondition is inhabited, and that a strict comparison would decide the touching case differently. The refusal case for each foundation changes the C's first `<=` to `<` and nothing else; it must fail.

## VST's non-Iris line

**Installation.** At the prover, meaning a request for `rocq-core.9.2.0 rocq-runtime.9.2.0 ocaml-base-compiler.5.4.1 ocaml.5.4.1` beside the foundation from an empty switch, the solver selects `coq-vst` 2.17 with `coq-compcert` 3.18, whose package bounds Coq below 9.3, and `coq-vst` 2.17 bounds Coq below 9.4. Seeded from the lock, the install took 10 min 55 s with a 2.21 GB peak and exit 0.

**The dual-licensed route.** VST's release archive for 2.17, SHA-256 `31574bf1c1f30120dc3b1d2174391a9dce8f3cfffdcd7e2c3ea5fb9fbeddef09`, bundles under `compcert/` a CompCert 3.17 subset: `lib/`, `common/`, `export/`, seven `cfrontend/` files (`Clight.v`, `ClightBigstep.v`, `Cop.v`, `Csem.v`, `Cstrategy.v`, `Csyntax.v`, `Ctypes.v`), `x86/Builtins1.v`, `x86_32/Archi.v`, `x86_64/Archi.v` and `flocq/`. Every one of those CompCert files is on the dual-licensed list of the `compcert/LICENSE` it bundles, SHA-256 `40e8151cb26269a4e051309a958714191a706b5dfc7aaec00a61137cb338a648`, which offers them under the INRIA agreement or `LGPL-2.1-or-later` at the user's choice; Flocq is `LGPL-3.0-or-later`. The 3.2beta archive bundles the same file list under a byte-identical license. The bundled Flocq does not build at the prover (`Zmod` is not found in `Flocq/Core/Zaux.v`), so the vst3 switch installs the platform `coq-flocq` 4.2.2 instead, which is VST's default selection. `make vst COMPCERT=bundled ZLIST=platform BITSIZE=64 IGNORECOQVERSION=true` then built 2.17 in 12 min 0 s with a 2.21 GB peak and exit 0, in a switch holding no CompCert package (F-489).

**The client.** The C, compiled by the vst2 switch's `clightgen -normalize` (which reports version 3.17; F-494):

```c
struct q35e_slot {
  unsigned int offset;
  unsigned int width;
};

int q35e_disjoint(struct q35e_slot *a, struct q35e_slot *b)
{
  unsigned int ao = a->offset;
  unsigned int aw = a->width;
  unsigned int bo = b->offset;
  unsigned int bw = b->width;
  if (ao + aw <= bo)
    return 1;
  if (bo + bw <= ao)
    return 1;
  return 0;
}
```

The Verifiable C proof `body_q35e_disjoint : semax_body Vprog Gprog f_q35e_disjoint disjoint_spec` states that for readable shares of two slot records with non-negative fields and non-wrapping ends, the function returns `Vint (if disjoint ao aw bo bw then Int.one else Int.zero)` and leaves both records unchanged, where `disjoint ao aw bo bw := orb (Z.leb (ao + aw) bo) (Z.leb (bo + bw) ao)`. The file also names VST's `SequentialClight.whole_program_sequential_safety_ext` so that the adequacy theorem a whole-program consumer applies is in the checked closure, and carries the witnesses above. It compiles in 3.06 s in vst2 and 5.33 s over the bundled tree, from the same generated Clight file, SHA-256 `81af8bd6660f50cd765f538238facd8a3ae1a30873818fcb4341d37ad9c9406c`. The refusal case fails: the proof's third branch cannot find the `lia` witness at line 50 of the proof file. The source hashes are in the receipt.

**The gate's reading.** `rocqchk -silent -o` over the client exits 129 after 2 min 28 s in vst2 and 3 min 34 s over the bundled tree, writing no summary:

```
Fatal Error: Anomaly
  "Incompatible resolver roots: VST.floyd.SeparationLogicAsLogicSoundness.DeepEmbeddedSoundness.DeepEmbedded.CConseq.CSHL_Def is not a subpath of VST.floyd.SeparationLogicAsLogic.DeepEmbedded.CConseq.CSHL_Def"
```

The positive control fails the same way. Checked alone, `VST.floyd.SeparationLogicAsLogic` completes and `VST.floyd.SeparationLogicAsLogicSoundness` raises the same anomaly after 44 min 47 s, so the anomaly is in checking the latter, which `VST.floyd.proofauto` loads. The compiler accepted the same module, so this is the checker's refusal of a library the compiler admits. One bounded web search on 2026-09-29 for the anomaly's text found no upstream report; that bounds the search and does not establish that none exists (F-486).

**The closures, by name.** Each summary below was accepted by the gate's parse; the receipt lists every name.

| Closure | Reading | Names | Declared | Module fields |
| --- | --- | --- | --- | --- |
| `compcert.cfrontend.Clight`, opam CompCert 3.18, `aarch64` | recursive | 12 | 12 | 0 |
| `compcert.cfrontend.Clight`, bundled CompCert 3.17, `x86_64` | recursive | 12 | 12 | 0 |
| `VST.veric.SequentialClight`, either route | recursive | 220 | 16 | 204 |
| `VST.floyd.SeparationLogicAsLogic`, vst2 | recursive | 221 | 17 | 204 |
| the client, either route | `SeparationLogicAsLogicSoundness` admitted | 380 | 17 | 363 |
| its positive control, either route | the same | 381 | 18 | 363 |
| the admitted module's own closure, either route | the same, loaded alone | 379 | 17 | 362 |

The client's 17 declared names are the Stdlib axioms `Stdlib.Logic.Classical_Prop.classic`, `Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq`, `Stdlib.Logic.FunctionalExtensionality.functional_extensionality_dep`, `Stdlib.Logic.ProofIrrelevance.proof_irrelevance`, `Stdlib.Logic.PropExtensionality.propositional_extensionality`, `Stdlib.Reals.ClassicalDedekindReals.sig_forall_dec`, `Stdlib.Reals.ClassicalDedekindReals.sig_not_dec` and `Stdlib.Sets.Ensembles.Extensionality_Ensembles`; VST's `VST.msl.Axioms.prop_ext`, `VST.veric.Clight_core.ef_deterministic_fun` and `VST.veric.Clight_core.inline_external_call_mem_events`; and CompCert's `compcert.lib.Axioms.proof_irr`, `compcert.common.Events.external_functions_sem`, `compcert.common.Events.inline_assembly_sem`, `compcert.common.Events.external_functions_properties`, `compcert.common.Events.inline_assembly_properties` and the configuration parameter, `compcert.aarch64.Archi.abi` through opam or `compcert.x86_64.Archi.win64` over the bundled tree. That parameter is the only difference between the two routes' closures. The Clight closure is the same set without `Extensionality_Ensembles`, `propositional_extensionality` and VST's three. The control adds exactly `Q35eVST.q35e_control.q35e_positive_control_unused` on both routes; the client adds to its admitted root exactly the module field `VST.floyd.canon.Conseq.semax_pre_post`.

The 363 module fields are constants of sealed modules that the classification finds no declaration for, and the summary names them as axioms: 174 of `VST.msl.shares.Share`, 30 of `VST.veric.compcert_rmaps.R`, 38 each of `VST.veric.SeparationLogicSoundness.VericMinimumSeparationLogic` and `VST.floyd.SeparationLogicAsLogicSoundness.MainTheorem.CSHL_MinimumLogic`, 17 of `...MainTheorem.CSHL_PracticalLogic`, 3 of `...MainTheorem.CSHL_Def`, 2 of `...MainTheorem.CSHL_Sound`, 2 of `VST.veric.SeparationLogicSoundness.VericSound`, 4 of `VST.msl.predicates_rec.HoRec`, 3 each of `VST.veric.align_mem.LegalAlignasStrictFacts` and `LegalAlignasStrongFacts`, 2 of `VST.veric.align_mem.hardware_alignof_facts`, 1 each of `VST.msl.Extensionality.EqdepElim` and `VST.floyd.canon.Conseq`, and the installed-library fields the gate already covers under an admitted root, 19 of `Stdlib.Arith.PeanoNat.Nat.PrivateImplementsBitwiseSpec`, 17 of `Stdlib.Reals.Rdefinitions.RbaseSymbolsImpl`, 2 of `Stdlib.Reals.Rdefinitions.RinvImpl` and 7 of `Corelib.ssr.ssrunder.Under_rel`. Admission makes the checker list every sealed field of an admitted library. Checking does not clear all of them: in the recursive `SequentialClight` summary the 204 fields of `Share` and `R` remain, `Share` being sealed by the alias `Module Share : SHARE_MODEL := tree_shares.Share.` and `R` being the functor application `Rmaps (CompCert_AV)`, while the interactively sealed Stdlib modules are not listed. The fields read are proved rather than assumed: `VST.msl.shares.Share.ord_antisym`, for one, is a `Lemma` of the module `msl/tree_shares.v` implements `SHARE_MODEL` with, and that implementation, being transparently sealed and checked, contributes no name of its own to the recursive summary. The classification does not establish the same of every field, and some VST files outside this closure carry `Admitted` proofs, so an enumeration of these fields is not by itself evidence that each is proved (F-487).

**What the client's theorems use.** The compiler's `Print Assumptions`, which the gate also runs, names six axioms under `body_q35e_disjoint` (`sig_not_dec`, `sig_forall_dec`, `prop_ext`, `functional_extensionality_dep`, `classic`, `Extensionality_Ensembles`) and nine under the adequacy theorem (those less `Extensionality_Ensembles`, plus `proof_irr`, `inline_external_call_mem_events`, `inline_assembly_sem` and `external_functions_sem`). The gate refuses the loaded set, not only the used one.

**The gate's compile settings.** Under the gate's pinned flags, which make default warnings errors, the generated Clight file fails on `deprecated-from-Coq` (clightgen emits `From Coq Require`) and the proof file fails on `mismatched-hint-db` raised by importing `VST.floyd.proofauto` (F-491). These readings are informational: the gate compiles only files under `proofs/`.

## VST's Iris line

At the prover, the solver refuses `rocq-vst` 3.2beta: it requires `coq-compcert` below 3.18, which requires OCaml below 5 and Coq below 8.17. It refuses `coq-vst` 3.1beta, which requires Coq below 8.21, and `coq-vst-iris` 2.11.1, which requires Coq below 8.17. Unconstrained from an empty switch, `rocq-vst` resolves to Rocq 9.1.1 on OCaml 4.14.4 with `coq-compcert` 3.17. These re-establish Q35a's readings.

The 3.2beta release archive, SHA-256 `4b30ad4bcf522fd8f717102fe0cc234c6a7b99d6853229bdd66a3515fbb64420`, built over its bundled subset in the vst3 switch with `rocq-iris` 4.5.0 and `rocq-vst-ora` 1.2, the versions its package names, stops after 28.67 s with exit 2:

```
File "./shared/resource_map.v", line 611, characters 81-87:
Error: Tactic failure: iStartProof: goal (... !! k = Some (YES dq' rsh' (to_agree ?Goal))) not a BI assertion.
```

The build stops at the first failure, so how many other files fail is unmeasured, and whether the failure is the prover's or the library versions' is not attributed. No client exists for this line (F-488).

## RefinedC

**Installation.** RefinedC at `2e89846baeaa7f65cbe17e3ae7297a8ed5b4feca` names its dependencies by development revision: its README pins Cerberus `f11e6b335a687c1b77539f7e5695607d09dfc3ea`, its `coq-lithium.opam` requires Iris `dev.2026-09-10.3.b3495ef9`, and that package in the Iris development repository at `6d518ba8346641684d9842fe4d1bba4d73293c93` requires stdpp `dev.2026-09-09.1.c3186aad`, so the lock's `rocq-stdpp` 1.13.0 cannot sit beside it. RefinedC's own CI pins Coq 9.1.0. At the prover the solver refuses it: `coq-lithium` requires `coq = 9.1.0`, which requires `rocq-runtime = 9.1.0`. With `--ignore-constraints-on=coq` and no other change the solver plans 76 packages at Rocq 9.2.0 on OCaml 5.4.1, and the install built every one, including `coq-lithium` and `refinedc`, in 17 min 45 s with a 1.53 GB peak and exit 0. No RefinedC, Iris or stdpp source was edited. `refinedc --version` reports `2e89846-dirty`; this record does not attribute the suffix (F-490).

**The client.** RefinedC's input form is annotated C:

```c
#include <refinedc.h>

struct [[rc::refined_by("o : Z", "w : Z")]] q35e_slot {
  [[rc::field("o @ int<u32>")]]
  unsigned int offset;
  [[rc::field("w @ int<u32>")]]
  unsigned int width;
};

[[rc::parameters("pa : loc", "ao : Z", "aw : Z", "pb : loc", "bo : Z", "bw : Z")]]
[[rc::args("pa @ &own<{(ao, aw)} @ q35e_slot>", "pb @ &own<{(bo, bw)} @ q35e_slot>")]]
[[rc::requires("{ao + aw ≤ max_int u32}", "{bo + bw ≤ max_int u32}")]]
[[rc::returns("{bool_to_Z (bool_decide (ao + aw ≤ bo ∨ bo + bw ≤ ao))} @ int<i32>")]]
[[rc::ensures("own pa : {(ao, aw)} @ q35e_slot", "own pb : {(bo, bw)} @ q35e_slot")]]
int q35e_disjoint(struct q35e_slot *a, struct q35e_slot *b)
```

with the same body as VST's client. `refinedc check` generated and checked `type_q35e_disjoint : ⊢ typed_function impl_q35e_disjoint type_of_q35e_disjoint` in 8.72 s. A client module names that lemma and RefinedC's `refinedc_adequacy`, which states that a typed whole program's threads are never stuck under Caesium's `c_lang`, and carries the witnesses. The refusal case fails: in the branch where both mutated tests are false, the generated proof leaves the side condition `¬ (ao + aw ≤ bo ∨ bo + bw ≤ ao)` unsolved, its hypotheses admitting touching slots.

**The gate's reading.** Recursive, nothing admitted, exit 0 in 1 min 8 s with a 1.68 GB peak, the summary names exactly three constants, all declared:

- `refinedc.typing.axioms.Ax.eq_rect_eq`, the `Axiom` in `theories/typing/axioms.v`'s module `Ax : EqdepElimination`, from which the file derives uniqueness of identity proofs;
- `lithium.syntax.li_test.check_wp` and `lithium.syntax.li_test.get_tuple`, `Parameter`s inside the test module `li_test` of Lithium's `syntax.v`.

The positive control adds exactly `Q35eRC.client.q35e_control.q35e_positive_control_unused`. `refinedc.typing.adequacy` checked alone names the same three, so they are the library's and not the client's. `Print Assumptions` reports both the typing lemma and the adequacy theorem closed under the global context: the gate would refuse the loaded names, which no theorem here uses (F-492).

**The gate's compile settings.** Under the gate's flags the generated specification and proof fail on `notation-incompatible-prefix`, a default warning that importing `refinedc.typing.typing` raises and that the generated build file disables explicitly (F-491).

## CN-to-Coq

CN at `10c586baf01f75d0a3209c83d8e622a9d62fb7c8` packages its Coq closure as `cn-coq`, which requires `coq = 8.20.1`, `coq-ext-lib` and `coq-struct-tact`. With Cerberus pinned at `c8c085d4714ae17095b2e1202fa33c5545d98df1`, the revision `cn.opam` names, the solver refuses `cn` with `cn-coq` at the prover, unconstrained, and with the Coq bound ignored alike: `coq-struct-tact` is an unknown package, and `opam search` finds no match in either registered repository. The CN tool alone, which is OCaml and carries no Coq closure, installs at the prover in simulation. Nothing was built and no client exists.

The Coq closure's own statement limits what a build would establish. `coq/Reasoning/ResourceInference.v` defines `provable`, the relation that stands for the solver's discharge of a logical constraint, as an inductive whose one constructor `solvable_SMT` holds of every constraint, with a comment that the actual definition should check a solver witness through SMTCoq. A proof log checked against that closure therefore checks resource inference while accepting every solver-side constraint unchecked. No file under its `coq/` names a soundness theorem relating that inference to an execution of Cerberus's Core (F-493).

## C semantics and bridges

| Foundation | Semantics its soundness is stated over | Producer of the input | Bridge to the contained compiler's Clight |
| --- | --- | --- | --- |
| VST 2.17 through opam | Stock CompCert 3.18 Clight, configured for the build host: `aarch64` in the guest, `x86_64` on hosted runners | `clightgen`, CompCert's unverified front end | None |
| VST 2.17 over its bundled subset | Stock CompCert 3.17 Clight, configured `x86_64` | The same | None |
| VST 3.2beta | Stock CompCert 3.17 Clight | The same | None, and no build |
| RefinedC | Caesium, RefinedC's own C semantics, with no capability model | RefinedC's frontend over Cerberus, unverified | None |
| CN-to-Coq | CN's resource inference over Cerberus Core, with solver constraints assumed | CN over Cerberus, unverified | None |

The contained compiler, `verifiedos-cheri-compcert` at `1cd36c710967e89db21da08f237ffca78843b883`, consumes SECOMP's compartment-annotated Clight: its `cfrontend/Clight.v` gives each function a `fn_comp` compartment (line 138) and allocates each local with `Mem.alloc m cp 0 (sizeof ge ty)` (line 277), and its `common/Values.v` extends `val` with `Vcap : block -> ptrofs -> capmeta -> val` (line 82). Stock Clight has neither. A theorem in any row is therefore about a term that the contained compiler does not consume. Each row's input is also produced by an unverified front end, while the contained compiler parses the C itself, so connecting a foundation's theorem to the compiled bytes needs a proved relation between the two front ends' outputs as well as between the two semantics (F-464, F-495).

Only VST's rows are on R-05-019's anchor: CompCert-C, though not its CHERI variant. RefinedC's Caesium and CN's Core are other C semantics, so admitting either amends R-05-019's anchor list or is refused under R-05-019a.

## Carriage without CompCert's agreement

F-205a records that VST's opam package depends on CompCert's non-commercial package. For the two foundations whose client checks:

- **VST's non-Iris line** is carried without that package by building its release archive over the bundled subset, as the vst3 switch did. The proof switch would gain the platform `coq-flocq` and `coq-vst-zlist` packages and a VST build that no opam package supplies, so the lock would carry a recorded source pin or a project-owned package definition building VST with `COMPCERT=bundled`; the hosted proof lane would build it from the archive's hash as it imports the lock. Every CompCert file taken is then on the dual-licensed list, used under `LGPL-2.1-or-later`, and Flocq under `LGPL-3.0-or-later`; the non-dual-licensed `compcert_new/` is never selected. The built libraries stay in the switch, and distributing them would engage the LGPL's conditions. This route does not reach VST's `sha/`, `hmacdrbg/` or `hmacfcf/`, which F-205a also concerns.
- **RefinedC** installs no CompCert at all. Its closure is BSD-3-Clause (RefinedC, Lithium, Iris, stdpp), BSD-2-Clause with the exceptions its `THIRD_PARTY_FILES.md` lists (Cerberus, used only by the frontend), MIT (`coq-record-update`, which Lithium requires) and the GNU LGPL version 2.1 text (`rocq-elpi` and `elpi`, the plugin Iris's development pin requires), each read at its license file only. [The third-party record](../../THIRD-PARTY.md#source-level-c-refinement-foundations) holds the readings. The proof switch would carry the Rocq libraries at the recorded pins, which replaces the lock's `rocq-stdpp` 1.13.0 with the development pin and is the opam guide's act; the frontend is a producer whose generated Rocq files are the gate's inputs, and it can stay in a separate switch.

Either carriage is also bounded by the proof switch's Rocq 9.3 upgrade, which the opam guide records as motivated: `coq-compcert` 3.18 caps Rocq below 9.3 and `coq-vst` 2.17 below 9.4, and neither the bundled VST route nor RefinedC was read at 9.3.

## Disposition

**Proposed R-05-164 amendment, for RefinedC.** The declared set gains exactly the three names RefinedC's summary reports, `refinedc.typing.axioms.Ax.eq_rect_eq`, `lithium.syntax.li_test.check_wp` and `lithium.syntax.li_test.get_tuple`, through R-06-011's admission-axiom inventory, since R-05-162a's *Ax* classes carry no logical axiom. The last two are unused test scaffolding, so an upstream Lithium release without `li_test` reduces the amendment to the first name. The amendment is only half of the admission. RefinedC also needs its R-05-020 record, whose non-duplication argument fails unless Caesium is added to R-05-019's anchors or bridged to the anchor; a Lithium bound or recorded pin admitting Rocq 9.2; the lock change above; and a resolution of the gate's warning refusal. None of these is taken here.

**Refusal, for VST.** VST's non-Iris line is refused at the gate because the kernel checker aborts on its Floyd closure, and even a fully checked VST closure names hundreds of proved constants as axioms. VST's Iris line is refused because it does not build at the prover. The repairs are proposed as separately priced cells: minimizing the checker anomaly and establishing which checker accepts VST 2.17; deciding the gate's reading of alias- and functor-sealed fields; and, for either VST or RefinedC, stating the bridge to the contained compiler's Clight. A port of VST's Iris line to the prover is not priced, its failure census being unmeasured. CN-to-Coq's axiom-free variant, a `provable` that checks solver witnesses, is upstream research and is not priced.

## Reproducing

The lane root keeps the scripts that took every reading: `vst2-build.sh`, `vst3-build.sh` and `vst3-bundled.sh` for the VST builds, `vst-sims.sh`, `refusals.sh` and `refusals2.sh` for the solver readings, `refinedc-build.sh` for RefinedC, `client-check.sh`, `vst2-diagnose.sh`, `vst2-admit.sh`, `vst2b-check.sh` and `rc-check.sh` for the clients and summaries, `extra.sh` for the compile-setting, assumption and refusal readings, and `analyze.py` with `spec.py` and `record.py` for the receipt. A re-run in a recreated switch is a new measurement, and any change of metadata, pin or source moves it.
