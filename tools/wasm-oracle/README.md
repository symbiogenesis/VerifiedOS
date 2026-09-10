# The CertiCoq → Wasm host-side oracle

This is the inner loop of the three-loop discipline ([implementation-checklist §0/§10](../../docs/implementation-checklist.md)): Gallina components run at native-ish speed on a stock Wasm engine with no cross-toolchain, no image, and no machine model in the loop. It is the functional spec-oracle the on-device GC-free lowerings are differentially tested against; capability *enforcement* is never tested here.

## Pinned environment

* **Compiler**: CertiRocq **0.9.1 for Rocq 9.1**, the released `rocq-certirocq.0.9.1+9.1` from the `rocq-released` opam repository, MIT. It is a release rather than a source pin because the release now carries both things a pin used to buy: the merged CertiCoq-Wasm backend (`theories/CodegenWasm`, mechanized against WasmCert-Coq, CPP 2025) that the `coq-certicoq` 0.9 release predated, and `rocq-metarocq-erasure-plugin` and `rocq-metarocq-safechecker-plugin` at `>= 1.5.1`, which is *released* MetaRocq rather than the unreleased 9.1 branch main tracked. There is therefore no clone, no checkout and no compatibility patch; the erasure inlining toggle a patch used to move already sits in `unsafe_passes` here.
* **Prover**: Rocq 9.1.1. CertiRocq requires `rocq-core {>= "9.1" & < "9.2~"}`, and its `coq-wasm` dependency also requires Coq below 9.2. The [proof gate](../vos/cli/proofs.py) independently uses Rocq 9.2.0.
* **OCaml**: 5.1.1 with ocamlfind 1.9.8. CertiRocq's unmodified bootstrap C wrapper fails with OCaml 5.4.1 because its `Hd_val` macro collides with the inline function introduced in OCaml 5.2. The wrapper compiles against 5.1.1, before that header change. The [package snapshot guide](../opam/README.md) records this boundary and the independent 5.4.1 switches. The container recipe selects the same oracle snapshot because its published Rocq 9.1 image still carries OCaml 4.14.2.
* **Engine**: Node.js 26.8.2 through [node.sh](node.sh), which verifies the official archive checksum and installs into a versioned toolchain directory. It uses stock `WebAssembly.instantiate`; the emitted module is import-free. `wasmtime` works equally for modules that need no result pretty-printing.

## Build and run

The CertiRocq bootstrap in the 5.1.1 switch remains incomplete, so `tools/opam/certirocq.lock` is not present. The wrapper compilation and Gallina vectors pass; they do not establish a working Wasm compiler. The recipes below require the snapshot exported after the compiler build, positive smoke checks and seeded negative check pass. Until then, both snapshot imports and the Docker build are unavailable.

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
$ opam switch create verifiedos-certirocq-0.9.1-ocaml-5.1.1 \
    --repos=rocq-released,default --empty --no-switch
$ opam switch import tools/opam/certirocq.lock \
    --switch=verifiedos-certirocq-0.9.1-ocaml-5.1.1 -y
$ eval $(opam env --switch=verifiedos-certirocq-0.9.1-ocaml-5.1.1 --set-switch)
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
$ mkdir -p /root/wasm-stage && cd /root/wasm-stage
$ cp <repo>/proofs/EndpointIPC.v <repo>/tools/wasm-oracle/ipc_oracle.v \
     <repo>/tools/wasm-oracle/run_demo.mjs <repo>/tools/wasm-oracle/node.sh .
$ eval $(opam env --switch=verifiedos-certirocq-0.9.1-ocaml-5.1.1 --set-switch)
$ rocq c EndpointIPC.v && rocq c ipc_oracle.v
     = 84
     : nat
     = true
     : bool
$ sh node.sh --stack-size=10000000 run_demo.mjs ipc_oracle.ipc_oracle.wasm
true
```

The two `Compute` lines are the check count and the answer *inside* the kernel, so a run reports the same verdict twice, once by conversion and once through the compiled pipeline, and a disagreement between them is the finding this staging exists to produce. **A green line is only worth having if a red one is reachable**, so the run is repeated over a source seeded to answer `false`: `sed 's/(upto 31)./(upto 32)./' ipc_oracle.v` widens one mask family past the one mask that is the frozen surface, and the emitted module prints `false` and exits non-zero. No `run.py` command reaches any of this, which is what the [checklist's conventions](../../docs/implementation-checklist.md) mean by the label naming a validator the entry point does not carry.

## Keeping the VM under a long build

WSL2 tears the utility VM down 60 s after its last instance stops, taking `dockerd` and every container with it, so a build left running between two commands dies with it, and the opam install above is long enough to be that build whichever environment runs it. The repository's answer is a bounded keepalive process rather than the global `[wsl2] vmIdleTimeout=-1` in `%USERPROFILE%\.wslconfig`; start it from the repository root before a long build:

```console
$ python tools/run.py model keepalive
KEEPALIVE pid=... hours=8 pidfile=/tmp/vos-keepalive.pid
```

It is idempotent, expires on its own, and stops early with `run.py model keepalive --stop`; see the keepalive section of [tools/vos/env.py](../vos/env.py) for why it is a process and not a setting. Every model loop takes the same lease, so a build started with `run.py model build` needs no separate call. The `certicoq-oracle` container carries `--restart unless-stopped` so it also comes back by itself after a teardown that happens anyway.

## Corporate-network note

On a TLS-intercepting network the opam downloads from GitHub release assets fail certificate verification (here: Cisco Umbrella re-signs `release-assets.githubusercontent.com`). Export the proxy root CA from the Windows store, place it beside the Dockerfile as `proxy-root-ca.crt`, and uncomment the two CA lines in the Dockerfile.
