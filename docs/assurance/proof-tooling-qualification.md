# Proof tooling and selective-library qualification

Q19a rejects adoption of the tested cached presentation workflow because changing an imported proof did not invalidate its rendered result. The editor server itself ran and gave useful source diagnostics. Q19b retains the handwritten helpers and dependent match: the selective Stdlib and Equations candidates replayed without additional assumptions, but this small client does not justify their integration and maintenance cost. Neither decision changes the locked prover or the acceptance gates.

This is the result under the [qualification contract](proof-qualification-contract.md), R-05-017, R-05-018a, R-05-018b and R-05-163. The baseline is revision `7ad95cb6830805fcd9e015d931f96eac5db997f5`, with the qualification contract committed before the experiments. `CopyRingService.v` had SHA-256 `1f4bfe599fd49e0b70adbbc719cf5bc5c9bde7091b7c158c98232787a45bb06c`; `RingContract.v` had `de0f337da91e247d60a15edf91d42f8e58be2fa3314546aad20beea697f092ee`. Both source files remain byte-identical to their pre-trial contents. Repository-wide proof and host gates belong to the integrator; the checks here use only these two modules and the named experimental dependent module.

## Environment and evidence identity

The acceptance switch is `verifiedos-rocq-9.2.0-ocaml-5.4.1`. Its `opam switch export` before and after the trials is byte-identical. All candidate packages were installed into the separate switch `verifiedos-q19-recovery-20260914`, explicitly using `--no-switch` when creating it. No package was installed into, removed from or downgraded in the locked switch. No solver result, rendered output or editor admission was imported as a theorem.

| Candidate | Exact selected source and disposition |
| --- | --- |
| Editor | [rocq-lsp `f49d7b391c8dc6599a00d126d7bfedc9efbdc2e7`](https://github.com/rocq-community/rocq-lsp/tree/f49d7b391c8dc6599a00d126d7bfedc9efbdc2e7), the v9.2 branch's selected immutable revision. Binary `coq-lsp` reports 0.2.5. Its own LICENSE is LGPL-2.1; the package declares LGPL-2.1-or-later. It is an external trial tool, not redistributed. |
| Rendering | [Alectryon `a6f19454a4a8756c51c6c4413544ad09d188e006`](https://github.com/cpitclaudel/alectryon/tree/a6f19454a4a8756c51c6c4413544ad09d188e006), its own MIT license read, with [VsRocq 2.5.0 at `ed2355f45cf2417d32251ec645a2bff7a9ece95c`](https://github.com/rocq-prover/vsrocq/tree/ed2355f45cf2417d32251ec645a2bff7a9ece95c), whose own root LICENSE is MIT. The VsRocq release archive is pinned by SHA-512 `b5ab3eea5bb6af643d635781e741a7a7b217fcc33e84c2c9e3448962118a63e174569ef6069c50af2ab57508d5cef476a8cfade14957a9654b1fea16c29a08b9`. This backend was tested independently from the editor session. |
| Arithmetic library | Existing F-01 Stdlib 9.2.0 at revision `8dd155bc10529814202f8f4c643e5ae6c2c88fa6`, whose own license and arithmetic scope F-01 records. The trial imports the already-qualified arithmetic and Boolean library selectively; no library source is copied. |
| Dependent definitions | Equations 1.3.2+9.2 at [revision `80195d4db7de6544dddde9d03f583b42497cc846`](https://github.com/mattam82/Coq-Equations/tree/80195d4db7de6544dddde9d03f583b42497cc846), with its own LGPL-2.1 LICENSE. Its archive SHA-512 is `04fb7a776b5ef6c3e34d8bdb9fe5e8873b03bff5616ae563eccba4121ad92bb2f49c9a8e2f178cb168ba71426c6ee1ac9f8dee72107dad62923c9006f03fbb9e`. External trial only; no generated dependent definition is shipped. |

The original source reads, exact package metadata, candidate switch export, Python package freeze, tool identities, commands, response payloads and trial programs are preserved in the recovery lane's `out/qualification-evidence/`, with a SHA-256 manifest. Native results remain under `/root/build/lane-recover-qualification-20260914`. Those receipts identify the actual tested inputs, including provisional and failed runs; a receipt from another source or dependency tuple is stale. Neither directory is a release artifact.

## Q19a: actual source diagnostics and batch refusals

The pinned batch compiler, native symbol/assumption audit and joint `rocqchk` accepted `RingContract` and `CopyRingService`: 0.82 s for the former audit, 28.38 s for the latter, and 66.98 s for the joint kernel recheck. The reported helper and client constants have empty transitive assumption sets.

Three actual source trials distinguish the gates:

| Trial | Exact change and observed refusal |
| --- | --- |
| Broken bound | In the lane's actual `CopyRingService.v`, changed the publisher's `Nat.ltb (rv_occupancy v) ring_capacity` guard to `Nat.leb`, including the matching case split. Compilation refused `publish_keeps_the_invariant` at line 873, characters 77â€“79: `Hg` proves `<=` while `leb_sub_succ` requires `<`. Elapsed 1.71 s. |
| Unfinished interactive proof | Replaced the file's suffix at `publish_keeps_the_invariant` with `Proof. intros v H.` and no closing proof. The compiler named that pending proof and exited 1 in 1.74 s. Exact original bytes were restored in `finally`. |
| Provisional admission | The separate native candidate uses `Admitted` for that same lemma. Compilation can produce a module, but the real native assumption audit refused the new axiom in the lemma, the interleaving theorem and its other dependent client. Elapsed 29.18 s. Kernel checking by itself would not reject a declared axiom; all three acceptance components are necessary. |

The editor is launched as `coq-lsp` in an isolated native project with `_RocqProject` containing `-Q proofs ""`. Its dependency is rebuilt by that candidate switch's `rocq c -q -Q proofs "" proofs/RingContract.v` before opening the source. Standard LSP `initialize`, `initialized`, `textDocument/didOpen` and `textDocument/didChange` messages supply the root URI and complete source text with versions 1, 2 and 3. The documented `proof/goals` request supplies the same versioned URI, source position and `pp_format: "Str"`. The preserved `lsp-trial.py` launcher and `lsp-trial.json` hold the exact messages and source hashes.

At the baseline publisher goal the server returned the actual `v`, `H`, `Hord` and `Hbd` context and goal `rv_ok (rv_publish v) = true` in 1.92 s. After the bound edit it returned the version-2 goal with the offending inclusive `Hg`, and a diagnostic on the same two source characters as the batch compiler, in 0.019 s. The unfinished version returned the remaining goal in 0.006 s. These responses are **provisional**, including a response with no diagnostic: an open interactive goal is not a batch acceptance. The source URI, version and recorded input digest distinguish the three responses.

An initial attempt to reuse a `.vo` from the acceptance switch was refused as making inconsistent assumptions over `Corelib.Init.Prelude`, even though both installations reported Rocq 9.2. Rebuilding the dependency in the candidate switch corrected the trial. This is direct evidence that a version label is insufficient environment identity. The candidate's executable and installed dependency identity must travel with a diagnostic; a source hash alone cannot validate an imported module.

## Q19a: independent rendering and the failed cache condition

Alectryon used its `vsrocq` backend, not the editor server. The input was the authoritative `CopyRingService` prefix through both named invariant lemmas and `the_invariant_survives_every_interleaving`; the cut ends after that theorem's `Qed`. No proof statement in that prefix was rewritten for display. The invocation shape was:

```
opam exec --switch=verifiedos-q19-recovery-20260914 -- <render-env>/bin/alectryon --frontend coq --coq-driver vsrocq --backend webpage --cache-directory <native>/render-cache -Q <native>/q19-editor/proofs "" <native>/q19-editor/Review.v -o <native>/render-cold.html
```

The cold page took 5.51 s; replay from cache took 0.31 s. Both had SHA-256 `9d486e6d27fb99402f5ad93fc25f34c22e1fa4adc6eefcfcaad326d0b6733d2f`. The dependency trial replaced `RingContract.eqb_reflexive` with `Admitted` in the isolated native project and successfully recompiled that changed import in the candidate switch. The import source digest changed to `68e0600464a80bb9631e9da457f876a6de79b9c91d30b3c576a088d51dda47ea`. With the same render source and cache, Alectryon returned exit 0 in 0.30 s and the **identical old page digest**. It did not invalidate feedback after that imported lemma changed.

The separate stale-page batch test copied that old HTML beside the changed dependency and called the repository's native assumption audit using the locked prover. It refused both `RingContract.eqb_reflexive` and `RingContract.a_fresh_unique_request_is_accepted` for the undeclared axiom, in 0.72 s. The page's presence and apparent success could not make the batch predicate pass; the gate stopped before a success receipt or kernel-acceptance claim. The dependency's original bytes were restored after the rendering trial.

Changing the render configuration to `--rocq-arg=-noinit` produced an explicit outdated-cache-metadata message and exit 1. Changing the source to the broken publisher bound also regenerated diagnostics and exited 1. Configuration and source invalidation worked in these trials; imported-lemma invalidation did not. Therefore the tested cached rendering integration is **rejected under R-05-018a**, even though its positive display and its other invalidations worked. Neither it nor the editor session is installed as a repository acceptance dependency. A later integration must supply and negatively test source, transitive dependency, executable and configuration identities before calling a page or diagnostic current; this result does not preapprove such a wrapper.

These are machine latency measurements, not a human usability study. Source diagnostics localized the failed bound and exposed its context; batch diagnostics already named the same failing range. Rendering made both proof paths inspectable in one page, but no measured reduction in human review time is claimed. Setup, semantic inspection and human review effort were not timed as person-hours. A fresh `python3 -m venv` lacked ensurepip; `uv venv` and installation of the immutable Alectryon source in the native lane succeeded in 4.95 s without a system-package change.

Thus the positive predicate's measured review-effort clause is also unsatisfied. The observed freshness failure independently rejects this candidate integration; recording that rejection does not silently waive the missing measurement or qualify a human-review workflow. A later retained presentation candidate must perform that comparison as well as passing all invalidation cases.

## Q19b: unchanged native statements and assumptions

The named client set is `andb_split`, `andb_join`, `nat_leb_refl`, `nat_leb_succ_r`, `nat_leb_from_succ`, `nat_leb_pred`, `publish_keeps_the_invariant`, `take_keeps_the_invariant` and `the_invariant_survives_every_interleaving`. The selective candidate replaced only the six helper proof scripts, using `Bool.andb_true_iff` and the qualified `PeanoNat.Nat.leb_refl`, `leb_le`, `le_trans`, `le_succ_diag_r` and `le_pred_l` lemmas. The candidate uses `From Stdlib Require Bool.Bool Arith.PeanoNat.` without opening the arithmetic namespace in client statements.

That distinction was checked rather than assumed: the initial `Require Import` candidate changed printed constant names in statement types. The repaired selective `Require` candidate preserves the native types and exact assumption sets of **all 526 inventoried `CopyRingService` constants**, not just the nine named clients. Every assumption set remains empty. Its native compile/audit took 34.13 s and joint kernel recheck with `RingContract` took 105.24 s. The unchanged handwritten baseline is the retained positive artifact.

A representative client edit asks for preservation after an initial publication. Directly specializing the induction's state loses the arbitrary-state induction hypothesis and the unrepaired proof failed in 2.01 s. The repaired client is a separate wrapper, with exactly the same statement and proof over either helper implementation:

```coq
Theorem after_initial_publish : forall sched v,
  rv_ok v = true -> rv_ok (rv_run sched (rv_publish v)) = true.
Proof.
  intros sched v H. apply the_invariant_survives_every_interleaving.
  apply publish_keeps_the_invariant. exact H.
Qed.
```

Both wrappers compile and print empty assumption sets. The helper bodies and original client statements remain unchanged during this repair. The script change is small in either version, so this trial provides no maintenance advantage that justifies rewriting the retained source.

## Q19b: dependent computation, equations and equality principles

The chosen dependent experiment uses `Payload b := if b then nat else bool`, with a handwritten dependent match and an Equations function having the same two clauses: true returns its natural-number payload, false returns its Boolean payload. The generated function computes concretely at `true, 7` and `false, false` by `eq_refl`. Its generated `generated_equation_1` and `generated_equation_2` prove the corresponding general equations. A theorem compares the generated and handwritten implementations for every tag and payload.

The transport theorem uses `Eqdep_dec.eq_rect_eq_dec` with decidable Boolean equality. Its concrete reduction and proof replay succeed without global UIP. A separate comparison queries `Eqdep.Eq_rect_eq.eq_rect_eq`; `Print Assumptions` exposes its global axiom. That principle is not used to prove the candidate functions or their equations. Native inventory and assumption auditing of the complete experimental module found **19 constants, all with empty transitive assumption sets**; kernel rechecking also passed. The presence of the separate global-principle query is not evidence that the candidate depends on it.

The candidate compilation and explicit equation/computation checks took 0.32 s, its full native audit 0.71 s and its kernel recheck 6.48 s. No stuck concrete computation, additional assumption or admitted obligation was accepted. This small dependent match is retained handwritten; installing Equations into the locked switch or exporting a new generated-definition interface would add maintenance with no demonstrated client gain. CoqHammer dependent mode, global UIP and assumption-adding solver modes are outside this retained result.

## Cost accounting and scope of the verdict

| Cost category | Observed work |
| --- | --- |
| Setup | Candidate editor, renderer backend and Equations switch installation: 703.48 s, two jobs. Alectryon Python environment: 4.95 s. Exact solver attempts and package receipts are retained separately from proof replay. |
| Repair | Rebuilt the editor dependency after the Prelude digest mismatch; changed the selective library use from namespace-opening `Require Import` to qualified `Require`; repaired the specialized client by composing the existing arbitrary-schedule theorem with publication preservation. The unrepaired client was refused in 2.01 s; the repaired full library audit is the separately measured 34.13 s run. Human editing time is unmeasured. |
| Replay | Baseline two-module audit and kernel recheck, candidate two-module audit and kernel recheck, the two repaired wrapper checks, editor goal latencies, render cold/cache trials, and dependent computation/audit/kernel checks are separately identified above and in their receipts. No search seed or external proof search is involved. |
| Review | Semantic comparison of native statements and assumptions, the precise bound diagnostic, cache counterexample and equality-principle distinction. No human review-effort improvement or person-hour saving is inferred from machine timings. |

Q19a's candidate integration is rejected on the observed imported-proof freshness failure. Q19b's candidates pass the bounded replay experiments but are not adopted; the existing handwritten source and locked batch workflow are retained. These are qualification dispositions, not claims of new target semantics, a full human-factors benchmark or a completed integration proof wave. Any later source change requires renewed evidence for the affected clients, and integration owns the final complete repository gates.
