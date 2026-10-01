# The CertiCoq → Wasm host-side oracle

This is the inner loop of the three-loop discipline ([implementation-checklist §0/§10](../../docs/implementation/implementation-checklist.md)): Gallina components run at native-ish speed on a stock Wasm engine with no cross-toolchain, no image, and no machine model in the loop. It is the functional spec-oracle the on-device GC-free lowerings are differentially tested against; capability *enforcement* is never tested here.

## Pinned environment

* **Compiler**: CertiRocq **0.9.1 for Rocq 9.1**, the released `rocq-certirocq.0.9.1+9.1` from the `rocq-released` opam repository, MIT. It is a release rather than a source pin because the release now carries both things a pin used to buy: the merged CertiCoq-Wasm backend (`theories/CodegenWasm`, mechanized against WasmCert-Coq, CPP 2025) that the `coq-certicoq` 0.9 release predated, and `rocq-metarocq-erasure-plugin` and `rocq-metarocq-safechecker-plugin` at `>= 1.5.1`, which is *released* MetaRocq rather than the unreleased 9.1 branch main tracked. There is therefore no clone, no checkout and no compatibility patch; the erasure inlining toggle a patch used to move already sits in `unsafe_passes` here.
* **Prover**: Rocq 9.1.1. CertiRocq requires `rocq-core {>= "9.1" & < "9.2~"}`, and its `coq-wasm` dependency also requires Coq below 9.2. The [proof gate](../vos/cli/proofs.py) independently uses Rocq 9.3.0.
* **OCaml**: 4.14.4 with ocamlfind 1.9.8. CertiRocq's unmodified native `certirocqc` bootstrap fails with OCaml 5.4.1 because its runtime's `Hd_val` macro collides with the inline function introduced in OCaml 5.2; OCaml 4.14.4 defines `Hd_val` as the same macro, token for token. The [package snapshot guide](../opam/README.md) records this boundary and the independent 5.4.1 switches. The container imports the same snapshot; its published Rocq 9.1 image's OCaml 4.14.2 only runs opam.
* **Engine**: Node.js 26.10.0 through [node.sh](node.sh), which verifies the official archive checksum and installs into a versioned toolchain directory. It uses stock `WebAssembly.instantiate`; the emitted module is import-free. `wasmtime` works equally for modules that need no result pretty-printing.

## Build and run

[tools/opam/certirocq.lock](../opam/certirocq.lock) is the snapshot of the switch in which the unpatched release, its native `certirocqc` bootstrap included, built at OCaml 4.14.4, `demo.v` printed `true` through the compiled Wasm, and `ipc_oracle.v`'s 84 checks answered `true` while its seeded twin answered `false`. The native recipe's create-and-import steps imported it into a fresh opam root on the aarch64 development guest, where those three checks answered the same and emitted the same modules byte for byte, and `run.py provision`'s CertiRocq oracle row held with `OPAMROOT` naming that root. Both recipes below import it. The Docker build is unexercised: the image is published for `linux/amd64` alone, and that guest, where every check here ran, has not built it. The Gallina vector harnesses compile in the proof gate's switch and exercise nothing in this one.

That guest's default opam root holds no switch of the declared name, so `provision`'s oracle row cannot hold there; its `verifiedos-certirocq-0.9.1-ocaml-5.1.1`, which an earlier declaration named, carries no `rocq-certirocq`. `run.py provision --apply` plans nothing for this switch, whose only route is the recipe here, a person's rather than a tool's.

Two environments install the same opam package. The container is the portable one and the opam switch is the one that runs on an arm64 host, because `rocq/rocq-prover` publishes `linux/amd64` alone at every 9.1 tag.

```console
$ docker build -t wasm-oracle -f tools/wasm-oracle/Dockerfile tools
$ docker run --rm wasm-oracle bash -lc \
    'rocq c demo.v && sh node.sh --stack-size=10000000 run_demo.mjs demo.oracle_demo.wasm'
true
```

```console
$ opam repo add rocq-released https://rocq-prover.org/opam/released --dont-select
$ opam update --all
$ opam switch create verifiedos-certirocq-0.9.1-ocaml-4.14.4 \
    --repos=rocq-released,default --empty --no-switch
$ opam switch import tools/opam/certirocq.lock \
    --switch=verifiedos-certirocq-0.9.1-ocaml-4.14.4 -y
$ eval $(opam env --switch=verifiedos-certirocq-0.9.1-ocaml-4.14.4 --set-switch)
$ mkdir -p out/wasm-oracle
$ cp tools/wasm-oracle/demo.v tools/wasm-oracle/run_demo.mjs tools/wasm-oracle/node.sh out/wasm-oracle/
$ cd out/wasm-oracle
$ rocq c demo.v && sh node.sh --stack-size=10000000 run_demo.mjs demo.oracle_demo.wasm
true
```

The switch is separate from the proof gate and from other projects' environments. The round trip is a functional check on one boolean, so nothing it decides turns on the optimizer the emitted OCaml is compiled with.

Run the native setup from the repository root. If an import fails after its switch is created, rerun the import command without repeating creation; it resumes the partial installation.

`demo.v` is the M1.5 smoke program in the oracle's intended shape: a pure Gallina computation checked against a known answer *inside* Gallina (the §4 crypto module's KAT pattern), so only one boolean crosses the Wasm boundary. `run_demo.mjs` decodes it per the upstream value representation (nullary constructors are odd-tagged unboxed scalars). The `--stack-size` flag matches the upstream harness: the generated code recurses deeply and overflows V8's default stack.

## Staging a repository source: `ipc_oracle.v` (M4.3)

`ipc_oracle.v` is the first repository Gallina source put through this loop rather than a smoke program: a battery of checks over [proofs/EndpointIPC.v](../../proofs/EndpointIPC.v)'s decision procedures, folded into one boolean the same way `demo.v` folds one. It needs that file beside it under its own name, because `Require Import EndpointIPC` resolves off the working directory, and the proof gate's `.vo` is built in a different switch and is not reusable here.

```console
$ mkdir -p /root/build/lane-<name>/wasm && cd /root/build/lane-<name>/wasm
$ cp <repo>/proofs/EndpointIPC.v <repo>/tools/wasm-oracle/ipc_oracle.v \
     <repo>/tools/wasm-oracle/run_demo.mjs <repo>/tools/wasm-oracle/node.sh .
$ eval $(opam env --switch=verifiedos-certirocq-0.9.1-ocaml-4.14.4 --set-switch)
$ rocq c EndpointIPC.v && rocq c ipc_oracle.v
     = 84
     : nat
     = true
     : bool
$ sh node.sh --stack-size=10000000 run_demo.mjs ipc_oracle.ipc_oracle.wasm
true
```

The two `Compute` lines are the check count and the answer *inside* the kernel, so a run reports the same verdict twice, once by conversion and once through the compiled pipeline, and a disagreement between them is the finding this staging exists to produce. **A green line is only worth having if a red one is reachable**, so the run is repeated over a source seeded to answer `false`: `sed 's/(upto 31)./(upto 32)./' ipc_oracle.v` widens one mask family past the one mask that is the frozen surface, and the emitted module prints `false` and exits non-zero. No `run.py` command reaches any of this, which is what the [checklist's conventions](../../docs/implementation/implementation-checklist.md) mean by the label naming a validator the entry point does not carry.

## The purecap counterpart: `ipc_oracle.c` (M1.2f)

[ipc_oracle.c](ipc_oracle.c) implements the check battery GC-free in the [selected scalar C profile](../../docs/implementation/contracts/compiler-source-values.md), in `ipc_oracle.v`'s order. Its inductives are integer codes, lists are caller-owned arrays, function-valued arguments are defunctionalized codes, and structural recursion becomes a loop. The [component contract](../../docs/implementation/contracts/compiler-component.md) admits this authored-C reference route and retains the missing extraction and source-refinement proof. `main` returns zero on success or the first failing check's position.

[compare_component.py](compare_component.py) freshly stages and compiles both arms, exposes every existing check through observation wrappers, and compares the complete ordered Boolean vectors and first failures. It runs the semantic mask-boundary mutation on both arms, both crossed comparisons and a corruption at every observation position. The population comes from the Gallina owner. Its receipt binds source closures, wrappers, preprocessed C, compiler, Wasm, final image, emulator, model sources and the installed Wasm producer. Run from the repository root in WSL, with a fresh output directory in the assigned native lane:

```console
$ python3 tools/wasm-oracle/compare_component.py \
    --compiler /native/contained/ccomp \
    --compiler-config /native/compcert.ini \
    --model-snapshot /root/build/lane-<name>/model-snapshot \
    --out /root/build/lane-<name>/component-vector
```

The model snapshot contains `sail_riscv_sim` and its successful `model-build.json` receipt. The Wasm side compiles in the declared switch above unless `--switch` names another, and the command refuses a switch whose prover is not the Rocq release [gallina.py](../vos/gallina.py) states for the oracle. It identifies that environment, including its package export and installed libraries, and its receipt says whether the switch was the declared one. M1.2f's recorded comparison named `--switch certirocq-0.9.1`, the undeclared legacy switch. Missing or changed dependencies invalidate the evidence. Source or tool changes require this experiment to be reissued; Host CI and Guest CI do not execute it. The older `run.py compiler-diff component` aggregate-output mode remains a driver diagnostic and does not satisfy the complete-vector contract. Agreement is finite differential evidence, not a refinement proof.

## Keeping the VM under a long build

WSL2 tears the utility VM down 60 s after its last instance stops, taking `dockerd` and every container with it, so a build left running between two commands dies with it, and the opam install above is long enough to be that build whichever environment runs it. The repository's answer is a bounded keepalive process rather than the global `[wsl2] vmIdleTimeout=-1` in `%USERPROFILE%\.wslconfig`; start it from the repository root before a long build:

```console
$ python tools/run.py model keepalive
KEEPALIVE pid=... hours=8 pidfile=/tmp/vos-keepalive.pid
```

It is idempotent, expires on its own, and stops early with `run.py model keepalive --stop`; see the keepalive section of [tools/vos/env.py](../vos/env.py) for why it is a process and not a setting. Every model loop takes the same lease, so a build started with `run.py model build` needs no separate call. The `certicoq-oracle` container carries `--restart unless-stopped` so it also comes back by itself after a teardown that happens anyway.

## Corporate-network note

On a TLS-intercepting network the opam downloads from GitHub release assets fail certificate verification (here: Cisco Umbrella re-signs `release-assets.githubusercontent.com`). Export the proxy root CA from the Windows store, place it beside the Dockerfile as `proxy-root-ca.crt`, and uncomment the two CA lines in the Dockerfile.
