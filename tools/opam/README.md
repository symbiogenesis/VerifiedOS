# OCaml toolchain resolutions

Each `.lock` file records the complete compiler, root-package and installed-package versions of one tested project switch. These are portable `opam switch export` files with no checkout paths, and each source pin or compatibility patch follows the qualification rule below. The current snapshots carry pins only in QuickChick; an authorized candidate does not enter another snapshot before its own hosted acceptance. The package repositories supply release metadata and verify downloaded archives against their checksums. Updating repository metadata does not change the versions an import requests.

| Snapshot | Project switch | Key tool versions |
| --- | --- | --- |
| [sail.lock](sail.lock) | `verifiedos-sail-0.20.3-ocaml-5.4.1` | Sail 0.20.3 |
| [rocq.lock](rocq.lock) | `verifiedos-rocq-9.3.0-ocaml-5.4.1` | Rocq 9.3.0, Stdlib 9.2.0, stdpp 1.13.0 |
| [certirocq.lock](certirocq.lock) | `verifiedos-certirocq-0.9.1-ocaml-4.14.4` | CertiRocq 0.9.1+9.1, Rocq 9.1.1, CompCert 3.18 |
| [quickchick.lock](quickchick.lock) | `verifiedos-quickchick-9.3.0-ocaml-5.4.1` | QuickChick and `coq-simple-io` at pinned commits, ExtLib 0.13.2, Rocq 9.3.0, Stdlib 9.2.0, dune 3.23.1 |
| [rupicola.lock](rupicola.lock) | `verifiedos-rupicola-9.2.0-ocaml-5.4.1` | Rupicola 0.0.11, bedrock2 compiler 0.0.9, Rocq 9.2.0 |
| [contained-compiler.lock](contained-compiler.lock) | `verifiedos-contained-compiler-9.3.0-ocaml-4.14.4` | Rocq 9.3.0, Stdlib 9.2.0, OCaml 4.14.4, dune 3.24.2, Menhir 20260209 |

The package metadata was rechecked on 2026-10-19 with opam 2.6.1 in a private
root. Constraining the qualified root versions leaves the Sail, proof and
Rupicola snapshots current. The latest stable findlib remains 1.9.8; its OCaml
bound still prevents a stable 5.5 compiler in those switches. CertiRocq stays
on Rocq 9.1.1 because its compiler and Wasm library require Rocq below 9.2;
its OCaml 4.14 closure also cannot take the newer Jane Street PPX packages
that require OCaml 5.1. Rupicola's Rocq 9.2 runtime and QuickChick's Rocq-Elpi
closure retain dune below 3.24. QuickChick resolution and qualification use only
the hosted instrument route; no local QuickChick switch was imported or built.

The current QuickChick lock is the byte-exact export from the
[2026-10-19 hosted recipe run](https://github.com/symbiogenesis/VerifiedOS/actions/runs/39348906266),
tested at `b9b451560f1f551ee8dae37f8828fcac60978d0b`. Its fresh build, property
checks, independent clean import and export comparison passed. Only ppxlib moves,
from 0.38.0 to 0.39.0. The separate lock-adoption commit
`4550a7da9c6db9c13d26546a471639b424d75c5d` preserves the tested route inputs;
`instrument-ci read --closing` confirms that binding. This qualification does not
state a Host CI or Guest CI verdict for later integration commits.

The Sail, proof, QuickChick and Rupicola switches use OCaml 5.4.1 and ocamlfind 1.9.8. OCaml 5.5.1 is available, but the [released findlib package](https://opam.ocaml.org/packages/ocamlfind/ocamlfind.1.9.8/) requires OCaml below 5.5.0; its 5.5-compatible package is `1.9.9~preview`, marked `avoid-version`.

The Sail switch locks Sail 0.20.3, and [Q37's note](../../docs/implementation/completion-log.md#q37-upgrade-the-sail-switch-to-sail-0203) compares its outputs over the model with 0.20.2's. Its [release notes](https://github.com/rems-project/sail/releases/tag/0.20.3) list reduced memory use in the Lean and Rocq conversion, colon-separated `SAIL_PLUGIN_DIR` lists, a `--tool` subcommand mechanism carrying a JSON comment stripper and moving `--fmt`'s arguments after it, and `where` reserved as a keyword. No project tool passes `--fmt`, `SAIL_PLUGIN_DIR` or `strip_json`, and the model's Sail sources use `where` only in comments and one string literal. The release's library declares in an implicit `corelib` project what 0.20.2 declared in `flow.sail` or built into the compiler: the integer comparisons, `__id`, `__size`, `__deref`, `internal_pick` and the `undefined_*` builtins. It also spells the Rocq externs of Euclidean division `e_div` and `e_modulo`. Sail is the model's acceptance compiler. Its paired Rocq support library, `rocq-sail-stdpp`, is published as 0.20.2 and 0.20.3, the latter tagged on 2026-09-24 and published in `rocq-released` on 2026-09-28 by [rocq-prover/opam#3872](https://github.com/rocq-prover/opam/pull/3872), each conflicting with every Sail version but its own and requiring `rocq-core` below 9.3, so the locked Sail's Rocq output pairs with 0.20.3. That bound is the published package's: the 0.20.3 source's own opam file requires `rocq-core` 9.0 or later with no upper bound. The proof switch takes dune 3.24.2, the Sail switch's edition: `rocq-runtime` 9.3.0 requires dune 3.21 or later with no upper bound, and `rocq-stdlib` 9.2.0 and `rocq-stdpp` 1.13.0 build against Rocq 9.3.0 unchanged.

The proof switch carries no Sail support library: no proof or tool loads one. `rocq-sail-stdpp` 0.20.2 requires `rocq-core` below 9.3, and built against Rocq 9.3.0 with that bound ignored it fails, because 9.3 rejects a `Proof` command that follows a tactic. The 0.20.3 release archive's 30 `src-stdpp` modules compile at Rocq 9.3.0 unchanged: on 2026-10-03 the locked `rocq c` compiled each with exit 0, after `rocq-stdpp-bitvector` 1.13.0's three, nothing installed. The [paired-release trial](sail-compatibility.md#trial-result) now passes the package's real Dune build and package tests at the locked versions without a source patch. Its published bound prevents ordinary installation; strict-source diagnostics and the five undeclared axioms remain independent carriage obligations. The [bounded compatibility trial](sail-compatibility.md) may qualify the paired release with reviewed metadata and source patches without waiting for another release. Add it back as a root of the proof switch and export the lock again only after that route or a compatible release has passed its complete acceptance predicate. Until then no project switch builds the model's Rocq output, whose [`riscv_extras.v`](../../model/handwritten_support/riscv_extras.v) requires `SailStdpp.Base`. Both releases load five Stdlib axioms into that output. [The canonical-term record](../../docs/assurance/canonical-machine-term.md#routes-that-take-the-five-out) states what carrying Q35g's change to the library, which removes them, would take of this guide.

The proof switch keeps `rocq-stdpp` 1.13.0 as a root although no tracked proof requires it. [The specification](../../docs/spec.md#r-05-018b) makes selective stdlib, stdpp and coqutil imports the first choice before new list, map, word or arithmetic helpers; [the language strategy](../../docs/languages/verification-strategy.md#existing-tooling-and-implementation-owners) lists selective stdpp imports as a reuse candidate not yet trialed, and its [estimation basis](../../docs/languages/verification-strategy.md#estimation-basis) lets selected stdpp laws support the bounded-component library's representation proofs. Q35e seeded two of its [private qualification switches](c-refinement-qualification-switches.md) by importing this lock at its Rocq 9.2.0 edition. `rocq-sail-stdpp` 0.20.3, the release paired with the locked Sail, requires `rocq-stdpp-bitvector` 1.13, which requires `rocq-stdpp` at its own version, so a return at that release's published bounds needs a 1.13 stdpp in the switch; 0.20.3 itself cannot install beside Rocq 9.3, its published bound being `rocq-core` below 9.3~.

The proof switch locks Rocq 9.3.0 because Rocq 9.2.0's kernel accepts proofs of `False` in ordinary fixpoint code. Rocq 9.3.0 fixes kernel inconsistencies present in 9.2.0, including two guard-checker defects, [#21839](https://github.com/rocq-prover/rocq/issues/21839) and [#22382](https://github.com/rocq-prover/rocq/issues/22382), each labelled upstream as a proof of `False` accepted by the kernel or checker. Rocq 9.2.0's compiler accepts all three upstream counterexamples, the first of #22382's two reporting itself closed under the global context, and its `rocqchk -o` gives each an all-`<none>` context summary; the locked compiler refuses all three as ill-formed recursive definitions. The upstream [critical-bug list](https://github.com/rocq-prover/rocq/blob/master/dev/doc/critical-bugs.md) records `rocqchk` as affected in the same versions, and the 9.2.1 milestone that targeted these fixes has no release. `rocq-core` and `rocq-runtime` 9.3.0 come from the default repository, which [ocaml/opam-repository#30776](https://github.com/ocaml/opam-repository/pull/30776) extended on 2026-09-29 with `rocq-runtime`, `rocq-core`, `rocq-devtools` and `rocqide` 9.3.0, their `coq`, `coq-core` and `coqide-server` compatibility packages and `rocq-native` 3, and with `rocq-stdlib` and `coq-stdlib` 9.2.0, the Stdlib release the proof switch takes from `rocq-released`. Rocq 9.3.0 makes `Print Assumptions` report axioms reached through a definition's type ([changelog](https://github.com/rocq-prover/rocq/blob/V9.3.0/doc/sphinx/changes.rst)), and `Print All Dependencies` traverses types the same way, so the CIC corpus exporter's dependency closures also name what a type alone reaches. Every proof compiles with the gate's settings and no diagnostic, and the exact assumption audit reports no assumption. The gate's generated queries open each interactive proof with `Proof`, whose absence 9.3 reports by default as `missing-proof-command`, and its [kernel recheck](../README.md#current-evidence-and-generated-documentation) requires the section 9.3's `rocqchk -o` adds for inductives relying on indices not mattering. For every query shape the exporter's tests transcribe, Rocq 9.3.0 prints `Print All Dependencies`, `About` and `Print` output byte for byte as 9.2.0 does. 9.3 reserves `is` and `of` as keywords and deprecates `if` over a two-constructor guard other than `bool`, `sumbool` or `sumor`, such as an `option`. Its record-update and `if ... is` syntax replace existing text only where the elaborated terms stay unchanged. A third inconsistency has no fixed release: [#22287](https://github.com/rocq-prover/rocq/issues/22287), recorded as [CVE-2026-72714](https://api.osv.dev/v1/vulns/CVE-2026-72714) with versions through 9.2.0 affected and no fixed version, leaves the universe graph's check disabled after a module that ran `Local Unset Universe Checking` closes, so a Hurkens-paradox proof of `False` is reported closed under the global context. The locked compiler still reports the upstream reproducer closed; `rocqchk` 9.2.0 and 9.3.0 each refuse its compiled object with a type error, a reading of that one reproducer rather than of the defect. The proof audit refuses setting or unsetting `Universe Checking` under any locality prefix in authored sources, which covers that form; dependency sources are outside that lexical check. A fourth, [#22510](https://github.com/rocq-prover/rocq/issues/22510), labelled upstream an inconsistency, is fixed by [#22494](https://github.com/rocq-prover/rocq/pull/22494) for the 9.3.1 milestone, which has no release: module subtyping accepts an inductive whose uniform parameters disagree with its signature's, and the upstream proof of `False` also needs a functor and propositional extensionality. The exact assumption audit refuses that axiom, and the audit refuses functors and module signatures in authored sources, so either check covers that form; dependency sources are outside both. Two cofixpoint guard-checker inconsistencies, [#22386](https://github.com/rocq-prover/rocq/issues/22386) and [#22389](https://github.com/rocq-prover/rocq/issues/22389), remain in Rocq 9.3.0 although the critical-bug list reports them fixed in V9.3: their fixes, [#22388](https://github.com/rocq-prover/rocq/pull/22388) and [#22392](https://github.com/rocq-prover/rocq/pull/22392), are milestoned 9.2.1 and entered `master` after the 9.3 branch was cut (F-565). So the proof audit refuses, before compiling, every sentence of every source the gate compiles that holds `CoInductive`, `CoFixpoint`, `cofix`, Ltac2's `cofix_` tactic or its `CoFix` constructor as a whole word outside comments and strings, whatever precedes it, a numeral, a quote or a token the source declares among them, and every sentence declaring a notation token that could hide such a word from that reading. Its residue is dependency sources, whose own cofixpoints a `rocqchk` carrying the same defects rechecks; any cofixpoint a proof takes from one through its definitions, notations, abbreviations, tactics or hints, Ltac2's `Constr.Unsafe.map` among them, which no lexical reading of the source sees; and a word joined to a token a dependency declares ending in a letter, or in digits, quotes or underscores after one, such as `+c1cofix` after Stdlib's `+c`, which Rocq lexes as three tokens and the audit reads as one identifier. The refusal retires only with a move of the proof switch's lock to a Rocq release whose `kernel/inductive.ml`, whitespace aside, holds `let check_one_cofix ?evars env nbfix def vlra =`, which #22388 writes in place of V9.3.0's `let check_one_cofix ?evars env nbfix def deftype =`, and `raise (CoFixGuardError (env, RecCallInNonMainMutual c))`, which #22392 adds, and whose source carries both fixes' regression tests, `test-suite/bugs/bug_22386.v` and `test-suite/bugs/bug_22389.v`. [#22387](https://github.com/rocq-prover/rocq/issues/22387), module subtyping that accepts inductives whose constructor types differ in let-ins, remains for the same reason, its fix [#22394](https://github.com/rocq-prover/rocq/pull/22394) missing from the tag (F-525); exploiting it needs module subtyping, which the audit's refusal of functors and module signatures in authored sources covers.

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

**Existing QuickChick pins.** Where no release of a package in QuickChick's closure installs beside Rocq 9.3.0, [quickchick.py](../vos/cli/quickchick.py)'s `RECIPE` pins it to the recorded upstream commit, and the hosted-qualified snapshot carries that pin. opam records each pin as an entry of a snapshot's `pinned:` list and a package block whose `url` names the upstream repository and the full commit, `git+URL#COMMIT`, and an import fetches that commit. No archive checksum covers such a source: it is verified by its commit, a git object id, so a build takes that commit or fails, and an upstream that rewrites or deletes it breaks the build rather than changing what it builds. A snapshot of the recipe is tracked only from a hosted run that built the switch from the recipe and passed the randomized half's checks on it, the snapshot tracked being that run's export; [quickchick.lock](quickchick.lock) is such an export. Each pin is listed below with its upstream, its commit, why no release serves, and the condition that retires it, that project's first release admitting Rocq 9.3.0: a release whose published bounds admit `rocq-core` 9.3.0 and which builds in the recipe's closure. When that release arrives, the recipe takes it in the pin's place, a hosted run exports the snapshot again, the row here leaves, and the licence is read again at the release. Moving a pin to another commit is a refresh like any other, with this table, [THIRD-PARTY.md](../../THIRD-PARTY.md)'s licence reading and the recipe moved together.

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

The Rupicola switch stays on Rocq 9.2.0, the kernel the proof switch left, because the released `coq-bedrock2` 0.0.9, which the bedrock2 compiler and Rupicola packages require, does not build against Rocq 9.3.0. The released lowering packages, `coq-coqutil` 0.0.7, `coq-riscv` 0.0.6, `coq-bedrock2` and `coq-bedrock2-compiler` 0.0.9 and `coq-rupicola` 0.0.11, set no upper bound on the prover; their tagged commits date from 2025-09-05 to 2025-10-02, and their GitHub releases were published on 2025-10-06. The `master` branches of mit-plv's bedrock2 and coqutil later adapted sources those packages build to three changes milestoned for Rocq 9.3+rc1, [rocq#21849](https://github.com/rocq-prover/rocq/pull/21849), [#21987](https://github.com/rocq-prover/rocq/pull/21987) and [#21478](https://github.com/rocq-prover/rocq/pull/21478): bedrock2's for #21849 and #21987, coqutil's for #21987 and #21478. No tagged release carries those adaptations. Measured on 2026-09-30 in a private opam root on the guest, in a switch created with `--repos=rocq-released,default --packages=ocaml-base-compiler.5.4.1`, `opam install -j2 ocamlfind.1.9.8 rocq-core.9.3.0 coq.9.3.0 coq-coqutil.0.0.7 coq-riscv.0.0.6 coq-bedrock2.0.0.9 coq-bedrock2-compiler.0.0.9 coq-rupicola.0.0.11` installs coqutil and riscv-coq beside `rocq-stdlib` 9.2.0 and fails first at `coq-bedrock2` 0.0.9: Rocq 9.3.0 refuses line 3 of `bedrock2/src/bedrock2/SuppressibleWarnings.v`, `Arguments warning_marker {T} msg%message_scope.`, because #21849 makes the `argument-scope-delimiter` deprecation an error by default, and the build passes no warning flag. The bedrock2 compiler and Rupicola packages were not reached.

[The opam client's owner](../vos/opam_client.py) fixes the reviewed client release, its
architecture-specific SHA-256 hashes, the package repositories and the one route that
creates a root on them. The
[guest bootstrap](../ci/bootstrap_guest.py) downloads that client, creates an isolated
root by that route, records each repository's URL and metadata stamp in
`bootstrap.json`, and imports the Sail and proof snapshots without changing the developer's
active switch. `run.py provision` holds a developer's client to the same release and their
root to one stating a format no newer than that client writes and carrying each of those
repositories at its URL with its metadata stamp read. It installs
the client where no client is on `PATH` and no root stands in a format older than that client writes, creates a root by the same route where none stands
or completes one in the shape that route leaves after its leading steps by the route's remaining steps, without
running `opam init` over it, which would rewrite that root's shell setup, and reports the root's format and
repository stamps; it replaces no client and alters no other standing root. A client
rewrites a root older than its own format one way, and the owner records the reviewed
client's format as `OPAM_ROOT_FORMAT`, so moving an existing root is a deliberate, recorded step,
and `run.py provision --apply` plans no switch over a root in an older format. See [the CI guide](../ci/README.md)
for invocation, placement and environment setup. QuickChick's switch is built and checked only on
[the instrument switch route](../ci/README.md#instrument-switch-route), on GitHub-hosted runners in
a fresh root, and CertiRocq's only locally; the remaining experimental switches are installed
separately into an initialized root.

From the repository root in the guest, register the repositories and import a snapshot into its dedicated switch:

```console
$ opam repository add rocq-released https://rocq-prover.org/opam/released --dont-select
$ opam update --all
$ opam switch create verifiedos-rupicola-9.2.0-ocaml-5.4.1 \
    --repos=rocq-released,default --empty --no-switch -y
$ opam switch import tools/opam/rupicola.lock \
    --switch=verifiedos-rupicola-9.2.0-ocaml-5.4.1 -y
```

Use the corresponding switch and snapshot from the table for the other environments. The Sail switch needs only the default repository. `run.py provision --apply` imports the Sail, proof and QuickChick snapshots through the recipes in [env.py](../vos/env.py), [proofenv.py](../vos/proofenv.py) and [quickchick.py](../vos/cli/quickchick.py); the user's ruling of 2026-09-30 keeps its QuickChick import out of the local guest, QuickChick's switch being built and checked only on [the instrument switch route](../ci/README.md#instrument-switch-route) (F-616). The [Wasm oracle](../wasm-oracle/README.md) specifies the CertiRocq snapshot's import in both the native recipe and Dockerfile. Creating these switches preserves existing switches and the user's active switch.

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
