# Released OCaml toolchain resolutions

Each `.lock` file records the complete compiler, root-package and installed-package versions of one tested project switch. These are portable `opam switch export` files with no checkout paths or source pins. The package repositories supply release metadata and verify downloaded archives against their checksums. Updating repository metadata does not change the versions an import requests.

| Snapshot | Project switch | Root tool versions |
| --- | --- | --- |
| [sail.lock](sail.lock) | `verifiedos-sail-0.20.2-ocaml-5.4.1` | Sail 0.20.2 |
| [rocq.lock](rocq.lock) | `verifiedos-rocq-9.2.0-ocaml-5.4.1` | Rocq 9.2.0, rocq-sail-stdpp 0.20.2 |
| [certirocq.lock](certirocq.lock) | `verifiedos-certirocq-0.9.1-ocaml-5.4.1` | CertiRocq 0.9.1+9.1, Rocq 9.1.1 |
| [quickchick.lock](quickchick.lock) | `verifiedos-quickchick-9.1.1-ocaml-5.4.1` | QuickChick 2.2.0, Rocq 9.1.1 |
| [rupicola.lock](rupicola.lock) | `verifiedos-rupicola-9.2.0-ocaml-5.4.1` | Rupicola 0.0.11, bedrock2 compiler 0.0.9, Rocq 9.2.0 |

All use OCaml 5.4.1 and ocamlfind 1.9.8. OCaml 5.5.1 is available, but the [released findlib package](https://opam.ocaml.org/packages/ocamlfind/ocamlfind.1.9.8/) requires OCaml below 5.5.0; its 5.5-compatible package is `1.9.9~preview`, marked `avoid-version`. This is the newest compiler that keeps the dependency closure on released packages. CertiRocq and its Wasm library require Rocq below 9.2. QuickChick independently requires `coq-simple-io`, which caps Coq below 9.2 and dune below 3.22. Their Coq 9.1.1 compatibility package fixes the standard library at 9.0.0. Those library constraints do not limit the proof gate or Rupicola switch.

The validation client is [opam 2.5.2](https://github.com/ocaml/opam/releases/tag/2.5.2), installed in `$HOME/build/toolchains/opam-2.5.2/bin`. The release publishes these Linux binary hashes:

| Archive | SHA-256 |
| --- | --- |
| `opam-2.5.2-arm64-linux` | `c4106ece84bcb60c68342573d2d6b4f0d6770ee088015c2216adc83d8854dcf9` |
| `opam-2.5.2-x86_64-linux` | `edfca2630c373b44b7ee1c2f81cd8dcf67468d0db57d6c02158de553ac63dbd4` |

For the arm64 guest, download into the checkout's ignored output directory, verify the hash, install into the versioned prefix and select that client for the shell session:

```console
$ mkdir -p out/deps "$HOME/build/toolchains/opam-2.5.2/bin"
$ curl -fL https://github.com/ocaml/opam/releases/download/2.5.2/opam-2.5.2-arm64-linux \
    -o out/deps/opam-2.5.2-arm64-linux
$ printf '%s  %s\n' c4106ece84bcb60c68342573d2d6b4f0d6770ee088015c2216adc83d8854dcf9 \
    out/deps/opam-2.5.2-arm64-linux | sha256sum -c -
$ install -m 755 out/deps/opam-2.5.2-arm64-linux "$HOME/build/toolchains/opam-2.5.2/bin/opam"
$ export PATH="$HOME/build/toolchains/opam-2.5.2/bin:$PATH"
$ opam --version
2.5.2
```

From the repository root in the guest, register the repositories and import a snapshot into its dedicated switch:

```console
$ opam repository add rocq-released https://rocq-prover.org/opam/released --dont-select
$ opam update --all
$ opam switch create verifiedos-rupicola-9.2.0-ocaml-5.4.1 \
    --repos=rocq-released,default --empty --no-switch -y
$ opam switch import tools/opam/rupicola.lock \
    --switch=verifiedos-rupicola-9.2.0-ocaml-5.4.1 -y
```

Use the corresponding switch and snapshot from the table for the other environments. The Sail switch needs only the default repository. `run.py provision --apply` imports the Sail, proof and QuickChick snapshots through the recipes in [env.py](../vos/env.py) and [quickchick.py](../vos/cli/quickchick.py). The [Wasm oracle](../wasm-oracle/README.md) imports its snapshot in both the native recipe and Dockerfile. Creating these switches preserves existing switches and the user's active switch.

If an import fails after creating its switch, retry the import command directly, omitting creation. The provisioner checks for an existing switch and skips creation automatically, so `run.py provision --apply` can resume a partial installation.

To refresh a resolution, update repository metadata, review `opam upgrade --switch=SWITCH --dry-run`, and apply the compatible upgrade in that project switch. Recheck the compiler and library constraints when newer releases appear. Run the affected model, proof, oracle or lowering checks, then export the tested versions with `opam switch export --switch=SWITCH tools/opam/NAME.lock`. Keep the export and any changed version constants together. An older compatible dependency is retained only when its consuming package's constraints require it.
