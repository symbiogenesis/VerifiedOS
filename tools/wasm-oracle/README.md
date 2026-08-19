# The CertiCoq → Wasm host-side oracle

This is the inner loop of the three-loop discipline ([implementation-checklist §0/§10](../../docs/implementation-checklist.md)): Gallina components run at native-ish speed on a stock Wasm engine with no cross-toolchain, no image, and no machine model in the loop. It is the functional spec-oracle the on-device GC-free lowerings are differentially tested against; capability *enforcement* is never tested here.

## Pinned environment

* **Compiler**: CertiRocq (upstream CertiCoq) at `4f53ca97303847cfb41265ac676e324703f77dcd` plus `metarocq-1.5.1-compat.patch`, built from source because the `coq-certicoq` 0.9 opam release predates the merged CertiCoq-Wasm backend (`theories/CodegenWasm`, mechanized against WasmCert-Coq, CPP 2025). Upstream removed its git submodules (`f27f1473`), so every dependency resolves through opam; its stale `INSTALL.md` submodule instructions are ignored. Main's tip (`45a1950d` as of this pin) tracks the *unreleased* MetaRocq 9.1 branch (`EImplementLazyForce` is not in any released MetaRocq), so the pin is the last pre-drift commit, and the two-site patch follows released MetaRocq 1.5.1 in taking the erasure inlining toggle from `erasure_configuration` into `unsafe_passes`.
* **Prover**: Rocq 9.1.1 (`rocq/rocq-prover:9.1-ocaml-4.14-flambda`). Not the newest Rocq by *constraint*, not oversight: CertiRocq requires `>= 9.1 & < 9.2~`, and SECOMP ([upstream/SECOMP](../../upstream/SECOMP), M1.2) states Rocq 9.1 as well, so one prover version serves both legs.
* **Engine**: Node.js (stock `WebAssembly.instantiate`; the emitted module is import-free). `wasmtime` works equally for modules that need no result pretty-printing.

## Build and run

```console
$ docker build -t wasm-oracle tools/wasm-oracle
$ docker run --rm wasm-oracle bash -lc \
    'rocq c demo.v && node --stack-size=10000000 run_demo.mjs demo.oracle_demo.wasm'
true
```

`demo.v` is the M1.5 smoke program in the oracle's intended shape: a pure Gallina computation checked against a known answer *inside* Gallina (the §4 crypto module's KAT pattern), so only one boolean crosses the Wasm boundary. `run_demo.mjs` decodes it per the upstream value representation (nullary constructors are odd-tagged unboxed scalars). The `--stack-size` flag matches the upstream harness: the generated code recurses deeply and overflows V8's default stack.

## Corporate-network note

On a TLS-intercepting network the opam downloads from GitHub release assets fail certificate verification (here: Cisco Umbrella re-signs `release-assets.githubusercontent.com`). Export the proxy root CA from the Windows store, place it beside the Dockerfile as `proxy-root-ca.crt`, and uncomment the two CA lines in the Dockerfile.
