# OCaml toolchain resolutions

Each `.lock` file records the complete compiler, root-package and installed-package versions of one tested project switch. These are portable `opam switch export` files with no checkout paths, and each source pin or compatibility patch follows the qualification rule below. The current snapshots carry pins only in QuickChick; candidate recipes may advance ahead of their qualified snapshots under the refresh contract below. The package repositories supply release metadata and verify downloaded archives against their checksums. Updating repository metadata does not change the versions an import requests.

| Snapshot | Project switch | Key tool versions |
| --- | --- | --- |
| [sail.lock](sail.lock) | `verifiedos-sail-0.20.3-ocaml-5.4.1` | Sail 0.20.3 |
| [rocq.lock](rocq.lock) | `verifiedos-rocq-9.3.0-ocaml-5.4.1` | Rocq 9.3.0, Stdlib 9.2.0, stdpp 1.13.0 |
| [certirocq.lock](certirocq.lock) | `verifiedos-certirocq-0.9.1-ocaml-4.14.4` | CertiRocq 0.9.1+9.1, Rocq 9.1.1, CompCert 3.18 |
| [quickchick.lock](quickchick.lock) | `verifiedos-quickchick-9.3.0-ocaml-5.4.1` | QuickChick and `coq-simple-io` at pinned commits, ExtLib 0.13.2, Rocq 9.3.0, Stdlib 9.2.0, dune 3.23.1 |
| [rupicola.lock](rupicola.lock) | `verifiedos-rupicola-9.2.0-ocaml-5.4.1` | Rupicola 0.0.11, bedrock2 compiler 0.0.9, Rocq 9.2.0 |
| [contained-compiler.lock](contained-compiler.lock) | `verifiedos-contained-compiler-9.3.0-ocaml-4.14.4` | Rocq 9.3.0, Stdlib 9.2.0, OCaml 4.14.4, dune 3.24.2, Menhir 20260209 |

The package-resolution snapshot is dated 2026-10-19 and uses opam 2.6.1 in a private
root. Constraining the qualified root versions leaves the Sail, proof and
Rupicola snapshots current. The latest stable findlib remains 1.9.8; its OCaml
bound still prevents a stable 5.5 compiler in those switches. CertiRocq stays
on Rocq 9.1.1 under the qualified release's bounds; the
[bounded 9.3 qualification](certirocq-compatibility.md#native-trial-verdict)
builds CompCert but stops at a WasmCert executable-definition adaptation;
its OCaml 4.14 closure also cannot take the newer Jane Street PPX packages
that require OCaml 5.1. Rupicola's Rocq 9.2 runtime and QuickChick's Rocq-Elpi
closure retain dune below 3.24. QuickChick resolution and qualification use only
the hosted instrument route; no local QuickChick switch was imported or built.

The current QuickChick lock is the byte-exact export from the
[2026-10-19 hosted recipe run](https://github.com/symbiogenesis/VerifiedOS/actions/runs/39348906266),
tested at `b9b451560f1f551ee8dae37f8828fcac60978d0b`. Its fresh build, property
checks, independent clean import and export comparison passed. The lock selects
ppxlib 0.39.0. The separate lock-adoption commit
`4550a7da9c6db9c13d26546a471639b424d75c5d` preserves the tested route inputs;
`instrument-ci read --closing` confirms that binding. This qualification does not
state a Host CI or Guest CI verdict for later integration commits.

The Sail, proof, QuickChick and Rupicola switches use OCaml 5.4.1 and ocamlfind 1.9.8. OCaml 5.5.2 is available, but the [released findlib package](https://opam.ocaml.org/packages/ocamlfind/ocamlfind.1.9.8/) requires OCaml below 5.5.0; its 5.5-compatible package is `1.9.9~preview`, marked `avoid-version`.

The Sail switch locks Sail 0.20.3, and [Q37's note](../../docs/implementation/completion-log.md#q37-upgrade-the-sail-switch-to-sail-0203) compares its outputs over the model with 0.20.2's. Its [release notes](https://github.com/rems-project/sail/releases/tag/0.20.3) list reduced memory use in the Lean and Rocq conversion, colon-separated `SAIL_PLUGIN_DIR` lists, a `--tool` subcommand mechanism carrying a JSON comment stripper and moving `--fmt`'s arguments after it, and `where` reserved as a keyword. No project tool passes `--fmt`, `SAIL_PLUGIN_DIR` or `strip_json`, and the model's Sail sources use `where` only in comments and one string literal. The release's library declares in an implicit `corelib` project what 0.20.2 declared in `flow.sail` or built into the compiler: the integer comparisons, `__id`, `__size`, `__deref`, `internal_pick` and the `undefined_*` builtins. It also spells the Rocq externs of Euclidean division `e_div` and `e_modulo`. Sail is the model's acceptance compiler. Its paired Rocq support library, `rocq-sail-stdpp`, is published as 0.20.2 and 0.20.3, the latter tagged on 2026-09-24 and published in `rocq-released` on 2026-09-28 by [rocq-prover/opam#3872](https://github.com/rocq-prover/opam/pull/3872), each conflicting with every Sail version but its own and requiring `rocq-core` below 9.3, so the locked Sail's Rocq output pairs with 0.20.3. That bound is the published package's: the 0.20.3 source's own opam file requires `rocq-core` 9.0 or later with no upper bound. The proof switch takes dune 3.24.2, the Sail switch's edition: `rocq-runtime` 9.3.0 requires dune 3.21 or later with no upper bound, and `rocq-stdlib` 9.2.0 and `rocq-stdpp` 1.13.0 build against Rocq 9.3.0 unchanged.

The proof switch carries no Sail support library: no proof or tool loads one. `rocq-sail-stdpp` 0.20.2 requires `rocq-core` below 9.3, and built against Rocq 9.3.0 with that bound ignored it fails, because 9.3 rejects a `Proof` command that follows a tactic. The 0.20.3 release archive's 30 `src-stdpp` modules compile at Rocq 9.3.0 unchanged: on 2026-10-03 the locked `rocq c` compiled each with exit 0, after `rocq-stdpp-bitvector` 1.13.0's three, nothing installed. The [paired-release trial](sail-compatibility.md#trial-result) now passes the package's real Dune build and package tests at the locked versions without a source patch. Its published bound prevents ordinary installation; strict-source diagnostics and the five undeclared axioms remain independent carriage obligations. The [bounded compatibility trial](sail-compatibility.md) may qualify the paired release with reviewed metadata and source patches without waiting for another release. Add it back as a root of the proof switch and export the lock again only after that route or a compatible release has passed its complete acceptance predicate. Until then no project switch builds the model's Rocq output, whose [`riscv_extras.v`](../../model/handwritten_support/riscv_extras.v) requires `SailStdpp.Base`. Both releases load five Stdlib axioms into that output. [The canonical-term record](../../docs/assurance/canonical-machine-term.md#routes-that-take-the-five-out) states what carrying Q35g's change to the library, which removes them, would take of this guide.

The proof switch keeps `rocq-stdpp` 1.13.0 as a root although no tracked proof requires it. [The specification](../../docs/spec.md#r-05-018b) makes selective stdlib, stdpp and coqutil imports the first choice before new list, map, word or arithmetic helpers; [the Vela language strategy](https://github.com/symbiogenesis/VelaLang/blob/main/docs/verification-strategy.md#existing-tooling-and-implementation-owners) lists selective stdpp imports as a reuse candidate not yet trialed, and its [estimation basis](https://github.com/symbiogenesis/VelaLang/blob/main/docs/verification-strategy.md#estimation-basis) lets selected stdpp laws support the bounded-component library's representation proofs. Q35e seeded two of its [private qualification switches](c-refinement-qualification-switches.md) by importing this lock at its Rocq 9.2.0 edition. `rocq-sail-stdpp` 0.20.3, the release paired with the locked Sail, requires `rocq-stdpp-bitvector` 1.13, which requires `rocq-stdpp` at its own version, so a return at that release's published bounds needs a 1.13 stdpp in the switch; 0.20.3 itself cannot install beside Rocq 9.3, its published bound being `rocq-core` below 9.3~.

The proof switch locks Rocq 9.3.0 (`rocq-core` and `rocq-runtime` 9.3.0 from the default opam repository via [ocaml/opam-repository#30776](https://github.com/ocaml/opam-repository/pull/30776), with `rocq-stdlib` 9.2.0 from `rocq-released`) and pairs it with source and kernel audits for upstream issues:

- **Fixed in Rocq 9.3.0 ([#21839](https://github.com/rocq-prover/rocq/issues/21839), [#22382](https://github.com/rocq-prover/rocq/issues/22382), and `Print Assumptions` type traversal):** Rocq 9.2.0's kernel and `rocqchk -o` accepted proofs of `False` in ordinary fixpoint code (listed on the upstream [critical-bug list](https://github.com/rocq-prover/rocq/blob/master/dev/doc/critical-bugs.md) with no 9.2.1 release); Rocq 9.3.0 rejects all three upstream counterexamples as ill-formed recursive definitions. Rocq 9.3.0 also makes `Print Assumptions` and `Print All Dependencies` traverse definition types ([changelog](https://github.com/rocq-prover/rocq/blob/V9.3.0/doc/sphinx/changes.rst)), adds the `indices_matter=false` section required by the [kernel recheck](../README.md#current-evidence-and-generated-documentation), reserves `is` and `of` as keywords, and defaults `missing-proof-command` to a warning.
- **`Local Unset Universe Checking` leak ([#22287](https://github.com/rocq-prover/rocq/issues/22287), [CVE-2026-72714](https://api.osv.dev/v1/vulns/CVE-2026-72714)):** Leaves universe checking disabled after a module running `Local Unset Universe Checking` closes, allowing a Hurkens-paradox proof of `False` to report `Closed under the global context` in `rocq c` (though `rocqchk` 9.2.0 and 9.3.0 reject the upstream reproducer). The proof gate's source audit rejects setting or unsetting `Universe Checking` under any locality prefix in authored sources.
- **Module-subtyping inductive mismatches ([#22510](https://github.com/rocq-prover/rocq/issues/22510) / [#22494](https://github.com/rocq-prover/rocq/pull/22494) and [#22387](https://github.com/rocq-prover/rocq/issues/22387) / [#22394](https://github.com/rocq-prover/rocq/pull/22394), F-525):** Unreleased in 9.3.0; exploiting either requires module subtyping (functors or module signatures, plus propositional extensionality for #22510), which the proof gate's source and assumption audits reject in authored sources.
- **Cofixpoint guard-checker defects ([#22386](https://github.com/rocq-prover/rocq/issues/22386) / [#22388](https://github.com/rocq-prover/rocq/pull/22388) and [#22389](https://github.com/rocq-prover/rocq/issues/22389) / [#22392](https://github.com/rocq-prover/rocq/pull/22392), F-565):** Both fixes landed on `master` after the 9.3 branch cut and remain absent from Rocq 9.3.0. Before compilation, the proof gate rejects any sentence in an authored proof source containing `CoInductive`, `CoFixpoint`, `cofix`, Ltac2's `cofix_` tactic, or `CoFix` outside comments and strings, as well as custom notation declarations that could disguise those tokens. This lexical guard retires only when the proof switch upgrades to a Rocq release whose `kernel/inductive.ml` carries both `let check_one_cofix ?evars env nbfix def vlra =` (#22388) and `raise (CoFixGuardError (env, RecCallInNonMainMutual c))` (#22392) alongside `test-suite/bugs/bug_22386.v` and `test-suite/bugs/bug_22389.v`.

The resolver-roots defect found during VerifiedOS's VST qualification, [rocq#22555](https://github.com/rocq-prover/rocq/issues/22555#event-32794329058), is resolved upstream by [#22556](https://github.com/rocq-prover/rocq/pull/22556), merged 2026-10-08 and milestoned 9.2.1. As of 2026-10-10 no release carrying it is published, and this snapshot still locks the affected Rocq 9.3.0. [The qualification record](../../docs/assurance/checker-resolver-anomaly.md) keeps the pre-fix measurements and the pending release adoption and VST requalification; an upstream merge supplies no passing evidence for the pinned checker.

The CertiRocq oracle switch selects OCaml 4.14.4 and ocamlfind 1.9.8. The unmodified CertiRocq 0.9.1+9.1 release fails its native `certirocqc` bootstrap with OCaml 5.4.1: the bootstrap's C wrapper includes its runtime's `Hd_val` macro beside OCaml's runtime header, and [5.2.0 defines that name as an inline function](https://github.com/ocaml/ocaml/blob/5.2.0/runtime/caml/mlvalues.h) the macro collides with. [OCaml 4.14.4 defines it as a macro](https://github.com/ocaml/ocaml/blob/4.14.4/runtime/caml/mlvalues.h) token for token identical to CertiRocq's, so the release bootstraps there without a patch. CertiRocq admits OCaml 4.13 or later and Rocq 9.1.1 requires 4.14 or later. The installed dependencies retain `ocaml-compiler-libs` v0.12.4.

In that switch the unpatched release and both native bootstraps build, and
the [recorded Wasm oracle checks](../wasm-oracle/README.md#build-and-run) answer
`true` for the demo and all 84 IPC cases and `false` for the seeded negative.
The current lock is the actual fresh-root export with its OCaml 4.14.4 compiler
invariant. The create-and-import form below is the reproduction route. Before
exporting an imported switch, explicitly set its compiler invariant with
`opam switch set-invariant --switch=SWITCH ocaml-base-compiler.4.14.4 -y` so
the export carries its `compiler:` section (F-496). The Gallina vector harnesses
load Stdlib alone and compile in the proof switch, so they exercise nothing in
this one. The Docker and native import recipes select this snapshot.

The merged bootstrap header fix has a [bounded backport qualification](certirocq-hdval-adoption.md#deferred-qualification).
Its initial complete build passes, but production adoption is deferred pending
the remaining consumer and reproducibility checks. This snapshot still selects
the qualified, unpatched release.

CertiRocq and its Wasm library require Rocq below 9.2, and the oracle switch's Coq 9.1.1 compatibility package fixes the standard library at 9.0.0. Those library constraints do not limit the proof gate, QuickChick or Rupicola switch.

The contained-compiler snapshot is an actual fresh export with an explicit
OCaml 4.14.4 compiler invariant. The
[native compiler and OpenSSL refresh evidence](../../docs/implementation/retained-evidence/dependencies-20261019/native-toolchains/manifest.json),
SHA-256 `123319f4a3241d7c916fa6f9e6374bd0743844055de530ae3dfeea69dd10a8eb`,
binds the isolated build and unchanged-source consumer comparison: 216 expected
proof objects, 334 identical extracted files and byte-identical assembly under
the same Clang preprocessing configuration. Only OCaml 4.14.2 to 4.14.4 and
dune 3.23.1 to 3.24.2 change in this closure. This local consumer check leaves
Q39's separate whole-environment kernel acceptance open.

**Qualified compatibility sources.** A reviewed recipe may select an immutable upstream commit or a checksummed release archive with bounded compatibility patches when no released package serves the locked toolchain. This applies beyond QuickChick. Its contract must name the affected consumer, unchanged semantic guarantees, exact package versions, source and patch digests, actual licence readings, stopping condition and retirement condition. A mutable branch, unrecorded patch or resolver-selected downgrade is refused. Preserve the locked prover and every dependency version unless the owner separately approves and qualifies a change; a library downgrade is not a shortcut around a compatibility failure. Keep trials in the assigned native lane and preserve shared switches byte for byte. Compile the complete selected closure under the consumer's existing settings, compare frozen elaborated readings where source semantics change, audit exact assumptions and run recursive kernel checks. A changed statement, definition or assumption returns to its owner. The affected hosted acceptance, fresh when required, must pass before exporting a production snapshot. A metadata-only build supplies no semantic or assumption acceptance. The [Sail support trial](sail-compatibility.md) is the first bounded non-QuickChick route.

**Existing QuickChick pins.** Where no release of a package in QuickChick's closure installs beside Rocq 9.3.0, [quickchick.py](../vos/cli/quickchick.py) records the qualified source in `PINS` and the candidate source in `RECIPE_PINS`. The table below describes the hosted-qualified snapshot; the [refresh contract](#rocq-dependency-refresh) describes the newer candidate. opam records each pin as an entry of a snapshot's `pinned:` list and a package block whose `url` names the upstream repository and the full commit, `git+URL#COMMIT`, and an import fetches that commit. No archive checksum covers such a source: it is verified by its commit, a git object id, so a build takes that commit or fails, and an upstream that rewrites or deletes it breaks the build rather than changing what it builds. A snapshot of the recipe is tracked only from a hosted run that built the switch from the recipe and passed the randomized half's checks on it, the snapshot tracked being that run's export; [quickchick.lock](quickchick.lock) is such an export. Each pin is listed below with its upstream, its commit, why no release serves, and the condition that retires it, that project's first release admitting Rocq 9.3.0: a release whose published bounds admit `rocq-core` 9.3.0 and which builds in the recipe's closure. When that release arrives, the recipe takes it in the pin's place, a hosted run exports the snapshot again, the row here leaves, and the licence is read again at the release. Refreshing a candidate moves the recipe and [THIRD-PARTY.md](../../THIRD-PARTY.md)'s licence reading together. The qualified-pin table and `PINS` move only when the hosted export is adopted.

The recipe and snapshot take released `coq-ext-lib` 0.13.2, whose compiled
sources match the former pin and whose published bounds admit Rocq 9.3.0. The
[hosted qualification](https://github.com/symbiogenesis/VerifiedOS/actions/runs/37571154640)
passes the clean recipe build, randomized property checks and import into a second
fresh root at revision `1f11f2be8a5c44fb3600675bd03e620ef0102f81`. Its
[retained report](../../docs/implementation/retained-evidence/out/instrument-ci/37571154640/artifacts/instrument-join-1f11f2be8a5c44fb3600675bd03e620ef0102f81/report.json),
SHA-256 `9eceede2ed458b4ce5a2ea7a5906a9103d27a5b026fbfc825b5f3b129eada89f`, records the
snapshot export, SHA-256 `91bf54af8abad50f2809f7a1797e4e8f84cd36653cc77c073681c6036e7cd7d0`,
and the byte-identical re-export. The remaining commit pins are listed below.

| Package | Upstream | Commit | Why no release serves | Retired by |
| --- | --- | --- | --- | --- |
| `coq-quickchick` | [QuickChick/QuickChick](https://github.com/QuickChick/QuickChick) | `3d4d6c0e9f72172a9f0b26db61c5496ec8e0f568` | 2.2.0, the latest release, cannot install: the latest release of its `coq-simple-io` dependency, 1.11.0, caps Coq below 9.2. The commit, one past 2.2.0, is the one Rocq V9.3.0's own CI overlay builds, and adapts the plugin to [rocq#22207](https://github.com/rocq-prover/rocq/pull/22207)'s record syntax | the first `coq-quickchick` release admitting Rocq 9.3.0 |
| `coq-simple-io` | [Lysxia/rocq-simple-io](https://github.com/Lysxia/rocq-simple-io) | `d035c0a85f0bde4ad56c31a9fa9ef3cb5e8d0f18` | 1.11.0, the latest release, caps Coq below 9.2 and dune below 3.22. The commit, the overlay's, states neither cap | the first `coq-simple-io` release admitting Rocq 9.3.0 |

The recipe takes dune 3.23.1, below the proof switch's 3.24.2, because `rocq-elpi` 3.5.1, which QuickChick's `coq-mathcomp-ssreflect` dependency reaches through `rocq-mathcomp-ssreflect`, `rocq-mathcomp-boot` and `rocq-hierarchy-builder`, requires dune 3.13 or later and below 3.24.

The Rupicola switch uses Rocq 9.2.0 because the released `coq-bedrock2` 0.0.9, which the bedrock2 compiler and Rupicola packages require, does not build against Rocq 9.3.0. The released lowering packages, `coq-coqutil` 0.0.7, `coq-riscv` 0.0.6, `coq-bedrock2` and `coq-bedrock2-compiler` 0.0.9 and `coq-rupicola` 0.0.11, set no upper bound on the prover; their tagged commits date from 2025-09-05 to 2025-10-02, and their GitHub releases were published on 2025-10-06. The `master` branches of mit-plv's bedrock2 and coqutil later adapted sources those packages build to three changes milestoned for Rocq 9.3+rc1, [rocq#21849](https://github.com/rocq-prover/rocq/pull/21849), [#21987](https://github.com/rocq-prover/rocq/pull/21987) and [#21478](https://github.com/rocq-prover/rocq/pull/21478): bedrock2's for #21849 and #21987, coqutil's for #21987 and #21478. No tagged release carries those adaptations. Measured on 2026-09-30 in a private opam root on the guest, in a switch created with `--repos=rocq-released,default --packages=ocaml-base-compiler.5.4.1`, `opam install -j2 ocamlfind.1.9.8 rocq-core.9.3.0 coq.9.3.0 coq-coqutil.0.0.7 coq-riscv.0.0.6 coq-bedrock2.0.0.9 coq-bedrock2-compiler.0.0.9 coq-rupicola.0.0.11` installs coqutil and riscv-coq beside `rocq-stdlib` 9.2.0 and fails first at `coq-bedrock2` 0.0.9: Rocq 9.3.0 refuses line 3 of `bedrock2/src/bedrock2/SuppressibleWarnings.v`, `Arguments warning_marker {T} msg%message_scope.`, because #21849 makes the `argument-scope-delimiter` deprecation an error by default, and the build passes no warning flag. The bedrock2 compiler and Rupicola packages were not reached.

[vos/opam_client.py](../vos/opam_client.py) defines the reviewed opam client release,
per-architecture SHA-256 digests, package repositories, root format (`OPAM_ROOT_FORMAT`),
and root-creation route. [bootstrap_guest.py](../ci/bootstrap_guest.py) downloads that
client, initializes an isolated root, records each repository's URL and metadata stamp in
`bootstrap.json`, and imports the Sail and proof snapshots without altering the
developer's active switch. `run.py provision` verifies the client version, root format,
and repository stamps, and can install a missing client or complete a partially
initialized root without running `opam init` (which would modify shell profiles) or
upgrading an older root format automatically. See [the CI guide](../ci/README.md) for
invocation, placement, and environment setup. QuickChick's switch is built and checked
only on [the instrument switch route](../ci/README.md#instrument-switch-route), and
CertiRocq's only locally; the remaining experimental switches are imported manually into
an initialized root.

From the repository root in the guest, register the repositories and import a snapshot into its dedicated switch:

```console
$ opam repository add rocq-released https://rocq-prover.org/opam/released --dont-select
$ opam update --all
$ opam switch create verifiedos-rupicola-9.2.0-ocaml-5.4.1 \
    --repos=rocq-released,default --empty --no-switch -y
$ opam switch import tools/opam/rupicola.lock \
    --switch=verifiedos-rupicola-9.2.0-ocaml-5.4.1 -y
```

Use the corresponding switch and snapshot from the table for the other environments. The Sail switch needs only the default repository. `run.py provision --apply` imports the Sail, proof and QuickChick snapshots through the recipes in [env.py](../vos/env.py), [proofenv.py](../vos/proofenv.py) and [quickchick.py](../vos/cli/quickchick.py); QuickChick's switch is built and checked only on [the instrument switch route](../ci/README.md#instrument-switch-route) (F-616). The [Wasm oracle](../wasm-oracle/README.md) specifies the CertiRocq snapshot's import in both the native recipe and Dockerfile. Creating these switches preserves existing switches and the user's active switch.

The contained compiler has its own switch and source-containment boundary. Import
`contained-compiler.lock` by the same create-and-import route, using the switch
name in the table. The qualifying native switches are named `q39-port` and
`q39-replay` in the private root
`/root/build/lane-checklist-20261010-c/q39/opam-root`; the table gives the portable
project name for a fresh import. The export records released packages only and
contains no compiler source. The [port decisions](../../docs/implementation/contained-compiler-port-decisions.md)
record the rejected Rocq 9.1 pairing, bounded compatibility work, frozen comparison
and separate acceptance requirements. Preserve the compiler's original build
flags and record any `configure` version override when building its contained
source through this lock.

If an import fails after creating its switch, retry the import command directly, omitting creation. The provisioner checks for an existing switch and skips creation automatically, so `run.py provision --apply` can resume a partial installation.

To refresh a resolution, update repository metadata, review `opam upgrade --switch=SWITCH --dry-run`, and apply the compatible upgrade in that project switch. Recheck the compiler and library constraints when newer releases appear. Run the affected model, proof, oracle or lowering checks, then export the tested versions with `opam switch export --switch=SWITCH tools/opam/NAME.lock`. Keep the export and any changed version constants together. Record the package constraint or demonstrated build incompatibility whenever an older dependency is retained.

## Rocq dependency refresh

The current upstream review is dated 2026-11-08. Released metadata was read at
opam-repository revision
[`76e3d586`](https://github.com/ocaml/opam-repository/tree/76e3d58643dea3b2867c8811b8aacf30a4417c05/packages)
and rocq-released revision
[`06733fd8`](https://github.com/rocq-prover/opam/tree/06733fd8dcbd7ca2e61bc38c72d6062a52f20d57/released/packages).
Rocq, Stdlib, stdpp, ExtLib, CertiRocq and the released lowering packages remain
at the versions above. The qualified snapshots retain their 2026-10-19 evidence.
The [package enumeration](../../docs/implementation/evidence/dependency-refresh-20261108.json)
records every installed lock entry against those metadata revisions. It is a
source review, with availability and consumer constraints still applicable, and
supplies no new resolver, build or kernel verdict. The QuickChick candidate moves
to the latest `master` commit below; Q45 retains qualification and production-lock
adoption.

The next QuickChick recipe selects QuickChick commit
`2b625770f22a7c0bfd1d5d812593eccfd6ef2034`, simple-io commit
`5c70625af00af6182817e490d93247cdefbed2e1` and
`ocaml_intrinsics_kernel.v0.17.3`. Keep Rocq 9.3.0, OCaml 5.4.1, findlib 1.9.8,
Stdlib 9.2.0, dune 3.23.1 and ExtLib 0.13.2. The source comparisons for
[QuickChick](https://github.com/QuickChick/QuickChick/compare/3d4d6c0e9f72172a9f0b26db61c5496ec8e0f568...2b625770f22a7c0bfd1d5d812593eccfd6ef2034)
and [simple-io](https://github.com/Lysxia/rocq-simple-io/compare/d035c0a85f0bde4ad56c31a9fa9ef3cb5e8d0f18...5c70625af00af6182817e490d93247cdefbed2e1)
retain the old APIs below Rocq 9.4 through version guards. Simple-io also
propagates the universe state returned by `interp_constr`; qualification must
exercise polymorphic extraction as well as the existing property harness.
Static review supplies no build verdict. Selected license readings belong to
[the third-party ledger](../../THIRD-PARTY.md#development-tools-contained-by-use).

Before moving recipe pins, ordinary checks and provisioning must recognize
the qualified lock's source, while `--recipe` recognizes only the candidate's
source. Focused controls must accept each source in its own mode and reject
crossed sources before staging. The recipe remains a candidate until the
[hosted instrument route](../ci/README.md#instrument-switch-route) passes its
fresh build, property checks, independent import and seeded comparison against
the qualified lock. Only that passing run's export replaces the lock. Stop on
a changed statement, assumption, unsupported API or failed property. Compatible
released packages retire the source pins under the existing rule.

CertiRocq's compatible transitive candidate is `ocaml-version.4.1.5`. Trial it
in a private native switch imported from `certirocq.lock`, preserving the
compiler invariant and every other version, using
`opam upgrade --switch=SWITCH ocaml-version.4.1.5`. Require an actual successful
export, unchanged demo and IPC kernel/Wasm answers, the negative IPC control,
exact consumer assumptions, recursive kernel checks, an independent clean
import and the [complete-vector comparison](../wasm-oracle/README.md#the-purecap-counterpart-ipc_oraclec-m12f)
before replacing that snapshot. This does not resume the deferred bootstrap
backport or the Rocq 9.3 compatibility trial.

Retained versions have concrete constraints: CertiRocq's
[published metadata](https://github.com/rocq-prover/opam/blob/06733fd8dcbd7ca2e61bc38c72d6062a52f20d57/released/packages/rocq-certirocq/rocq-certirocq.0.9.1%2B9.1/opam)
requires WasmCert exactly 2.2.0 and Rocq below 9.2; MetaRocq and Equations must
match that prover. Rocq-Elpi 3.5.1 requires Elpi below 3.8 and dune below 3.24,
excluding Elpi 4.0.1 and dune-configurator 3.24.2 from those closures. Stable
findlib excludes OCaml 5.5 and later. The Sail-support and lowering refusals
above remain applicable.

Q45 in [the plan](../../PLAN.md) owns remaining qualification. The user's
local-commit-only instruction defers publication, Host CI, Guest CI and the
instrument dispatch. Pending checks supply no passing evidence; production
snapshots retain their previously qualified versions.

## Merged checker and printer improvements

Rocq [PR 22609](https://github.com/rocq-prover/rocq/pull/22609),
[PR 22611](https://github.com/rocq-prover/rocq/pull/22611) and
[PR 22614](https://github.com/rocq-prover/rocq/pull/22614) are merged into `master`
for milestone `9.4+rc1`. The proof switch still locks Rocq 9.3.0, which contains
none of these changes. Their [tracker entries](../../docs/implementation/upstream-prs.md)
record the merge revisions and public checks. A qualified prover-lock move must
precede relying on these improvements in production.

The [conditional context-pass retirement](../../PLAN.md#coverage-preserving-tooling-retirement)
is tracked in the project plan. The current lock and extra pass remain required
until the comparison and hosted acceptance below pass.

PR 22611 records sealed implementation dependencies while collecting context
output from admitted libraries under `-norec` or `-admit`; admitted terms remain
unchecked. At adoption, compare those native contexts against the proof gate's
existing extra admitted-root cover pass, retaining genuine hidden axioms and
admission accounting. Once the comparison and hosted proof acceptance pass, retire
that redundant context pass. Checked alias/functor sealed-field assumption queries
retain their independent purpose and remain required. Merged
[`-axiom-free` PR 22609](https://github.com/rocq-prover/rocq/pull/22609) and
companion [PR 22710](https://github.com/rocq-prover/rocq/pull/22710) enable the
assumption-collection path without `-o`; qualify the combined recursive, `-norec`,
`-admit`, sealed, primitive and rewrite-permission cases (alongside open
[`-allow-axiom` PR 22668](https://github.com/rocq-prover/rocq/pull/22668) if selected)
before replacing context-summary parsing.

PR 22614 adds the default warning `module-printing-fallback` when rich module or
module-type printing returns names without types. After adoption, Q35q's rich-print
queries should unset `Short Module Printing` and use
`Set Warnings "+module-printing-fallback"` to reject incomplete output directly.
Explicit short printing emits no warning. This removes silent fallback from those
queries; Q35q still needs its [complete native type producer](../../docs/assurance/sail-support-inventory.md#remaining-owner-act),
census, exact concrete-implementation assumption audit and hosted recursive check.
The current strict flags, inventory guards, proof handling and lock stay in force
until their respective replacements qualify.
