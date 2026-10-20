# CertiRocq compatibility qualification

The Wasm oracle's next prover candidate is Rocq 9.3.0, the proof switch's
current release. The production oracle stays at its qualified snapshot until
the acceptance below holds. CertiRocq builds and checks remain local under
the [instrument-route contract](../ci/README.md#instrument-switch-route).

## Upstream assessment

The 2026-10-19 reading of PR 166 at
`ea16ec556ebc509a5c7fd42c60591b6eb3fdf30b` finds useful Wasm memory proofs,
but its package still requires Coq below 9.2 and the old Equations edition.
WasmCert's own replacement release excludes 9.3. The PR's passing Nix checks
exercise 9.1; they establish no 9.3 result. PR 160 adapts a development switch
and leaves package-bound changes to PR 159. Applying both PR heads would also
adopt a newer compiler pipeline needing unreleased MetaRocq erasure work.

The release-based candidate below avoids that unrelated pipeline change and
targets the latest stable prover directly. Its metadata solution and actual
source compatibility are separate questions. Neither open PR is by itself a
qualified replacement for the current oracle.

## Bounded candidate contract

Commit this contract before building or repairing the candidate. Use a private
native root, source trees and build directories; never install or pin into a
shared switch. Preserve exports of any existing switch read by the trial.
Scratch scripts and research captures live in a unique OS temporary directory.

The initial source selection is:

| Component | Immutable source | Reason |
| --- | --- | --- |
| CertiRocq | `49cd1c23b74678d36f7f37412a5c1ce6d00f41d2`, release `v0.9.1+9.1` | Preserve the qualified compiler's pipeline rather than adopt unrelated development work. |
| MetaRocq | `9242c14bc377611a56d45283977ea754fd499c47` | Rocq `V9.3.0` selects this source in `dev/ci/ci-basic-overlay.sh`. Its selection is compatibility evidence, not acceptance of this oracle. |
| WasmCert-Coq | `58a3d3f8b7af4dc8aa9351f254a9e672643b21f8`, release `v2.2.1` | The release selected by [CertiRocq PR 166](https://github.com/CertiRocq/certirocq/pull/166). Its published prover bound still excludes 9.3. |
| Equations | `d562d8c413f4b0d2a837ef742d08fa59d14107e6` | Rocq `V9.3.0`'s CI selection; the newest released Equations package still excludes 9.3. |

Keep OCaml 4.14.4, ocamlfind 1.9.8, CompCert 3.18 and ExtLib 0.13.2.
Use Rocq 9.3.0 and Stdlib 9.2.0. Keep Dune 3.23.1 and Menhir/MenhirLib
20260209 from the oracle snapshot. Mathematical Components selects 2.6.0,
whose published bounds admit the prover; 2.4.0 and 2.5.0 exclude it.
WasmCert's new
`rocq-parseque` dependency selects release 0.3.1, replacing `coq-parseque` 0.2.2.
MenhirLib's published bound also needs a target-only metadata trial.
Record the complete resolved closure before building; no implicit
dependency downgrade is permitted. Read each selected source's actual licence
and applicable file notices before building it, and bind archives, metadata,
source revisions and patches by digest. Native outputs are not distributed.

The first five commits of PR 166 supply the Wasm memory/int64 adaptations:
`1ac483d0f9264723ed76e5ed96e0ab22d120d65a`,
`f805712f4c555528b52cf9d2348d38c2d797a622`,
`77ca66298c5f5c53dd90b20f916f1cf6b8e82af7`,
`769c72b4ed18915e3d4aedf2becaf3baadeb9126` and
`f452cd11d3fa50f44dd492e48d3611cc1df38780`.
Exclude its subsequent renames and correctness-proof restructuring.
[PR 160](https://github.com/CertiRocq/certirocq/pull/160), reviewed at head
`35b87650bac0d01470ab7e41581b3697f9ef3da0`, supplies candidate
orphan end-tactic, `Monomorphic_entry` and Ltac-value API adaptations, transplanted
to the release's file layout only where the selected APIs require them.
Its development pipeline changes are outside this candidate.

Metadata may admit exactly the target prover and selected dependency versions.
Compatibility repairs may change grammar, proof scripts or plugin API calls
while preserving executable behavior and theorem statements. Record each
patch's affected declarations and compare their frozen elaborated readings
where meanings could change. Preserve package build flags; add no admission,
diagnostic suppression or allowed assumption. Stop at the first incompatible
statement, executable definition, unaccounted assumption or dependency framework
port. The repair budget is twelve candidate source checks or two attended hours,
whichever comes first; finish the current build and retain its diagnostics at
the limit. A refused candidate records its first failure and the separately
scoped next action instead of receiving a production snapshot.

## Acceptance and adoption

The candidate's complete package closure must build, including CertiRocq's
plugins and both native bootstraps. Compile the unchanged `demo.v`,
`EndpointIPC.v` and `ipc_oracle.v` under their existing consumer settings.
Require the original in-kernel IPC population and verdict, the demo and all IPC
checks to answer `true` through Wasm, and the
existing mask-boundary negative to answer `false` with a nonzero runner exit.
For the compiled `demo`, `EndpointIPC` and `ipc_oracle` consumer roots, require
recursive kernel rechecks to exit zero and exact-assumption comparisons to pass
against the same named roots in the qualified baseline switch, recording each
constant's assumption set and any difference. An unexplained new or missing
assumption refuses adoption. An upstream build or a metadata solution supplies
neither verdict.

Export with an explicit compiler invariant, import into another empty private
root, repeat the functional, kernel and exact-assumption checks and require a
byte-identical re-export. Before adoption,
reissue the [complete-vector C/Wasm comparison](../wasm-oracle/README.md#the-purecap-counterpart-ipc_oraclec-m12f),
including both mutants, crossed comparisons and every observation-position
control, against the qualified contained compiler and source-bound emulator.
Qualify any candidate-version/snapshot input that comparison needs before using
it; its production-version check is not waived.

Only then update the oracle owner, snapshot, recipes and third-party readings
together. Host CI must pass for the settled publication and every Guest CI lane
must be dispatched; neither workflow performs these oracle checks. Retire each
compatibility patch after a released source admits the target prover and passes
the same acceptance. Rocq 9.2 is not a fallback candidate: the target is the
kernel already selected for the project's proofs.

## Same-prover grammar continuation

The cross-version Menhir reading is a stopped comparison: the original
Rocq 9.1.1 reading and the candidate's 9.3.0 reading differ in the parentheses
printed around `parse`'s match return type. Retain that difference and its
diagnostics; it is not a passing frozen reading.

A separate bounded diagnostic reference may compile the original Menhir source
at the target prover with only its three late `Proof` commands deleted. Preserve
every original term, statement and tactic, the package build flags and the
target environment. Keep the reference in its own native build tree, retain
its missing-`Proof` warnings, and grant that reference no package acceptance.
It is a reference for the grammar edit, not a replacement production source.

Compare that reference's frozen public types, universes, executable bodies and
assumptions for `pop`, `reduce_step` and `parse` byte for byte with the candidate
that moves those commands before `refine`. Bind the complete source inventory,
loaded library environment, logical mappings and compile settings; other
source differences or a different same-prover reading stop this continuation.
The existing total repair budget still applies. This separate target-version
qualification does not change the authored-proof repair workflow or erase the
failed cross-version comparison. All consumer, re-import and vector acceptance
above remains due.

## Native trial verdict

[Native Rocq 9.3 compatibility trial](../../docs/implementation/retained-evidence/certirocq-compat-20261019/manifest.json), SHA256 `b40b542a17f28533921c39960b8bd4f6f8bc9d15931e2d57c60e2b8ac517832d`,
records a stopped candidate on 2026-10-19. No replacement snapshot is qualified.
The private resolver found a complete solution; its dry-run action records are
simulations, not build results. Actual builds installed Rocq 9.3.0, Stdlib 9.2.0,
MathComp 2.6.0, parseque 0.3.1 and CompCert 3.18. An initial metadata-only path pin
omitted package sources; the corrected retry used the verified complete archives.
That setup failure supplies no compatibility verdict.

MenhirLib 20260209 first refused three late `Proof` commands. Moving those
commands before `refine` built the library in two candidate checks. The original
cross-prover frozen comparison remains failed. The separately scoped target-version
reference built with its missing-`Proof` warnings retained, and its readings for
`pop`, `reduce_step` and `parse` match the candidate byte for byte, SHA256
`887d1a21bd7271624ef753f2fcfbf0fd86bf06498c09f7e121816ca7ef514a29`.
This establishes that grammar comparison only. Upstream already carries the exact
three-command relocation in [Menhir `6dedce5`](https://gitlab.inria.fr/fpottier/menhir/-/commit/6dedce5de5df8f139c42326f3bd95e7a1c878674).
A future source pin must also preserve Menhir's generated-parser version check:
the development source defines `require_unreleased`, whereas the selected generator
requires `require_20260209`. Upstream's release stamping owns that adjustment.

The next actual build stopped in WasmCert `theories/numerics.v`, line 1585,
at `BofZ_normalise`: `Cannot apply lemma Eqdep_dec.eq_proofs_unicity_on`.
[WasmCert `72c33dcb`](https://github.com/WasmCert/WasmCert-Coq/commit/72c33dcb6b629bbd744f5b6b4a6ebf6f2d9fa0c6)
contains an adaptation, but it changes the executable `normalise` definition from
`ltac:(abstract exact false)` to explicit `false` as well as simplifying the proof.
It was not applied: an executable-definition/transparency change exceeds this
candidate's repair boundary. This is an unresolved port, not a refutation of the
theorem or evidence that Rocq 9.3 cannot support the oracle.

Equations, MetaRocq, CertiRocq's plugins and bootstraps, all consumer and exact
assumption checks, fresh snapshot import and the complete-vector comparison were
not reached. The existing qualified switch's ordinary and full exports are each
byte-identical before and after the trial; its ordinary export still matches the
tracked production lock. Native sources, complete frozen readings and build outputs
remain in `/root/build/certirocq-compat-20261019`; the portable bundle retains their
identities, commands, diagnostics and comparison results.

The next candidate needs an explicit contract for the upstream WasmCert
`normalise` adaptation: freeze its public types, executable meaning and assumptions,
review the intended transparency change, and qualify that source before resuming
the remaining closure and all acceptance above. Neither raising the package bounds
nor combining the two CertiRocq PR heads discharges that work. The production
oracle remains at Rocq 9.1.1.
