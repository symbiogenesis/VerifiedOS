# The CertiCoq → Wasm host-side oracle

This is the inner loop of the three-loop discipline ([implementation-checklist §0/§10](../../docs/implementation-checklist.md)): Gallina components run at native-ish speed on a stock Wasm engine with no cross-toolchain, no image, and no machine model in the loop. It is the functional spec-oracle the on-device GC-free lowerings are differentially tested against; capability *enforcement* is never tested here.

## Pinned environment

* **Compiler**: CertiRocq **0.9.1 for Rocq 9.1**, the released `rocq-certirocq.0.9.1+9.1` from the `rocq-released` opam repository, MIT. It is a release rather than a source pin because the release now carries both things a pin used to buy: the merged CertiCoq-Wasm backend (`theories/CodegenWasm`, mechanized against WasmCert-Coq, CPP 2025) that the `coq-certicoq` 0.9 release predated, and `rocq-metarocq-erasure-plugin` and `rocq-metarocq-safechecker-plugin` at `>= 1.5.1`, which is *released* MetaRocq rather than the unreleased 9.1 branch main tracked. There is therefore no clone, no checkout and no compatibility patch; the erasure inlining toggle a patch used to move already sits in `unsafe_passes` here.
* **Prover**: Rocq 9.1.1. Not the newest Rocq by *constraint*, not oversight: the release's own `depends` field reads `rocq-core {>= "9.1" & < "9.2~"}`, and SECOMP ([upstream/SECOMP](../../upstream/SECOMP), M1.2) states Rocq 9.1 as well, so one prover version serves both legs.
* **Engine**: Node.js (stock `WebAssembly.instantiate`; the emitted module is import-free). `wasmtime` works equally for modules that need no result pretty-printing.

## Build and run

Two environments install the same opam package. The container is the portable one and the opam switch is the one that runs on an arm64 host, because `rocq/rocq-prover` publishes `linux/amd64` alone at every 9.1 tag.

```console
$ docker build -t wasm-oracle tools/wasm-oracle
$ docker run --rm wasm-oracle bash -lc \
    'rocq c demo.v && node --stack-size=10000000 run_demo.mjs demo.oracle_demo.wasm'
true
```

```console
$ opam repo add rocq-released https://rocq-prover.org/opam/released --dont-select
$ opam switch create certirocq-0.9.1 --repos=rocq-released,default \
    --packages=ocaml-base-compiler.4.14.2
$ eval $(opam env --switch=certirocq-0.9.1 --set-switch)
$ opam install -y rocq-certirocq.0.9.1+9.1
$ rocq c demo.v && node --stack-size=10000000 run_demo.mjs demo.oracle_demo.wasm
true
```

The switch is its own rather than the [proof gate](../vos/cli/proofs.py)'s `rocq-9.1.1`, which the gate reads while this installs, and it takes the distribution's OCaml 4.14.2 without flambda: the round trip is a functional check on one boolean, so nothing it decides turns on the optimizer the emitted OCaml is compiled with.

`demo.v` is the M1.5 smoke program in the oracle's intended shape: a pure Gallina computation checked against a known answer *inside* Gallina (the §4 crypto module's KAT pattern), so only one boolean crosses the Wasm boundary. `run_demo.mjs` decodes it per the upstream value representation (nullary constructors are odd-tagged unboxed scalars). The `--stack-size` flag matches the upstream harness: the generated code recurses deeply and overflows V8's default stack.

## Keeping the VM under a long build

WSL2 tears the utility VM down 60 s after its last instance stops, taking `dockerd` and every container with it, so a build left running between two commands dies with it, and the opam install above is long enough to be that build whichever environment runs it. The repository's answer is a bounded keepalive process rather than the global `[wsl2] vmIdleTimeout=-1` in `%USERPROFILE%\.wslconfig`; start it from the repository root before a long build:

```console
$ python tools/run.py model keepalive
KEEPALIVE pid=... hours=8 pidfile=/tmp/vos-keepalive.pid
```

It is idempotent, expires on its own, and stops early with `model.py keepalive --stop`; see the keepalive section of [tools/vos/env.py](../vos/env.py) for why it is a process and not a setting. Every model loop takes the same lease, so a build started with `model.py build` needs no separate call. The `certicoq-oracle` container carries `--restart unless-stopped` so it also comes back by itself after a teardown that happens anyway.

## Corporate-network note

On a TLS-intercepting network the opam downloads from GitHub release assets fail certificate verification (here: Cisco Umbrella re-signs `release-assets.githubusercontent.com`). Export the proxy root CA from the Windows store, place it beside the Dockerfile as `proxy-root-ca.crt`, and uncomment the two CA lines in the Dockerfile.
