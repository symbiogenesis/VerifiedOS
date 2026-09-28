# Released OCaml toolchain resolutions

Each `.lock` file records the complete compiler, root-package and installed-package versions of one tested project switch. These are portable `opam switch export` files with no checkout paths or source pins. The package repositories supply release metadata and verify downloaded archives against their checksums. Updating repository metadata does not change the versions an import requests.

| Snapshot | Project switch | Key tool versions |
| --- | --- | --- |
| [sail.lock](sail.lock) | `verifiedos-sail-0.20.2-ocaml-5.4.1` | Sail 0.20.2 |
| [rocq.lock](rocq.lock) | `verifiedos-rocq-9.2.0-ocaml-5.4.1` | Rocq 9.2.0, Stdlib 9.2.0, stdpp 1.13.0 |
| `certirocq.lock` (export pending the compiler build) | `verifiedos-certirocq-0.9.1-ocaml-5.1.1` | CertiRocq 0.9.1+9.1, Rocq 9.1.1, CompCert 3.18 |
| [quickchick.lock](quickchick.lock) | `verifiedos-quickchick-9.1.1-ocaml-5.4.1` | QuickChick 2.2.0, Rocq 9.1.1 |
| [rupicola.lock](rupicola.lock) | `verifiedos-rupicola-9.2.0-ocaml-5.4.1` | Rupicola 0.0.11, bedrock2 compiler 0.0.9, Rocq 9.2.0 |

The Sail, proof, QuickChick and Rupicola switches use OCaml 5.4.1 and ocamlfind 1.9.8. OCaml 5.5.1 is available, but the [released findlib package](https://opam.ocaml.org/packages/ocamlfind/ocamlfind.1.9.8/) requires OCaml below 5.5.0; its 5.5-compatible package is `1.9.9~preview`, marked `avoid-version`.

Sail 0.20.3 and Rocq 9.3.0 are released upstream but not locked. Sail is the model's acceptance compiler, and its paired Rocq support library is unpublished: the latest `rocq-sail-stdpp` release, 0.20.2, conflicts with every other Sail version. The opam repositories carry no `rocq-core` 9.3.0. The proof switch keeps dune 3.23.1 because `rocq-runtime` 9.2.0 requires dune below 3.24; Rocq 9.3.0 installs with dune 3.24.2, and `rocq-stdlib` 9.2.0 and `rocq-stdpp` 1.13.0 build against it unchanged.

The proof switch carries no Sail support library, because no proof or tool loads one. `rocq-sail-stdpp` 0.20.2 requires `rocq-core` below 9.3, and built against Rocq 9.3.0 with that bound ignored it fails, because 9.3 rejects a `Proof` command that follows a tactic. Add it back as a root of the proof switch, at a release whose `rocq-core` range admits the locked prover, when a proof or a build of the model's Rocq output needs it, and export the lock again.

The missing `rocq-core` package blocks a proof-switch upgrade that the locked kernel itself motivates. Rocq 9.3.0 fixes kernel inconsistencies present in 9.2.0, including two guard-checker defects in ordinary fixpoint code, [#21839](https://github.com/rocq-prover/rocq/issues/21839) and [#22382](https://github.com/rocq-prover/rocq/issues/22382), each labelled upstream as a proof of `False` accepted by the kernel or checker. The locked compiler reports both upstream counterexamples closed under the global context and `rocqchk -o` gives them an all-`<none>` context summary; Rocq 9.3.0 built from its release tag rejects both. The upstream [critical-bug list](https://github.com/rocq-prover/rocq/blob/master/dev/doc/critical-bugs.md) records `rocqchk` as affected in the same versions, and the 9.2.1 milestone that targeted these fixes has no release. Rocq 9.3.0 also makes `Print Assumptions` report axioms reached through a definition's type ([changelog](https://github.com/rocq-prover/rocq/blob/V9.3.0/doc/sphinx/changes.rst)), so the upgrade reruns the exact assumption audit and reviews any assumption it newly reports. Under 9.3.0 every proof compiles with the gate's settings and no diagnostic, and the audit reports no assumption. The gate's generated queries open each interactive proof with `Proof`, which 9.3 otherwise reports by default, and its [kernel recheck](../README.md#current-evidence-and-generated-documentation) accepts the section 9.3's `rocqchk -o` adds for inductives relying on indices not mattering. The CIC corpus exporter reads `Print All Dependencies` and `About` output in the form Rocq 9.2.0 prints, so the upgrade compares its parsers with 9.3.0's output. 9.3 reserves `is` and `of` as keywords and deprecates `if` over a two-constructor guard other than `bool`, `sumbool` or `sumor`, such as an `option`. Its record-update and `if ... is` syntax replace existing text only where the elaborated terms stay unchanged.

The CertiRocq oracle switch selects OCaml 5.1.1 and ocamlfind 1.9.8. The unmodified CertiRocq 0.9.1+9.1 release fails its native bootstrap with OCaml 5.4.1: its runtime's `Hd_val` macro collides with the inline function in OCaml's runtime header. OCaml [5.1.1 still defines that name as a macro](https://github.com/ocaml/ocaml/blob/5.1.1/runtime/caml/mlvalues.h), while [5.2.0 defines an inline function](https://github.com/ocaml/ocaml/blob/5.2.0/runtime/caml/mlvalues.h). This compatibility boundary keeps the oracle on 5.1.1 without patching its release. The installed dependencies retain `ocaml-compiler-libs` v0.12.4.

The 5.1.1 wrapper compilation and Gallina vector checks pass, but the full CertiRocq bootstrap and Wasm smoke checks remain incomplete. No `certirocq.lock` is exported until that compiler build and the positive and negative Wasm checks pass. The Docker and native import recipes require that pending snapshot.

CertiRocq and its Wasm library require Rocq below 9.2. QuickChick independently requires `coq-simple-io`, which caps Coq below 9.2 and dune below 3.22. Their Coq 9.1.1 compatibility package fixes the standard library at 9.0.0. Those library constraints do not limit the proof gate or Rupicola switch.

The [guest bootstrap](../ci/bootstrap_guest.py) owns the reviewed opam client release
and architecture-specific SHA-256 hashes. It initializes an isolated root, registers
the package repositories and imports the Sail and proof snapshots without changing
the developer's active switch. See [the CI guide](../ci/README.md) for invocation,
placement and environment setup. The remaining experimental switches are installed
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

Use the corresponding switch and snapshot from the table for the other environments. The Sail switch needs only the default repository. `run.py provision --apply` imports the Sail, proof and QuickChick snapshots through the recipes in [env.py](../vos/env.py) and [quickchick.py](../vos/cli/quickchick.py). The [Wasm oracle](../wasm-oracle/README.md) specifies the pending snapshot import in both the native recipe and Dockerfile. Creating these switches preserves existing switches and the user's active switch.

If an import fails after creating its switch, retry the import command directly, omitting creation. The provisioner checks for an existing switch and skips creation automatically, so `run.py provision --apply` can resume a partial installation.

To refresh a resolution, update repository metadata, review `opam upgrade --switch=SWITCH --dry-run`, and apply the compatible upgrade in that project switch. Recheck the compiler and library constraints when newer releases appear. Run the affected model, proof, oracle or lowering checks, then export the tested versions with `opam switch export --switch=SWITCH tools/opam/NAME.lock`. Keep the export and any changed version constants together. Record the package constraint or demonstrated build incompatibility whenever an older dependency is retained.
