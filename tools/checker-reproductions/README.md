# Checker reproductions

Standalone Rocq sources that reproduce `rocqchk` kernel-checker behaviors first
encountered on upstream libraries. Each reproduction is authored from scratch in the
upstream library's module shape and contains no upstream code. Each directory includes the
trigger, single-construct negative controls, a `run.sh` script that compiles and checks
every file in a named opam switch (`rocq c` and `rocqchk -silent -o`), and a README
recording the expected outcome per file and release (`run.sh` exits `1` if any result
differs). The corresponding analysis records live under `docs/assurance/`.

These files sit outside the shipped proof set: `run.py proofs` and the proof citation,
ledger,header, and instrument rules (K-103, K-105, K-109, K-117) scan only `proofs/` and
registered instruments. Each `.v` file carries the `Apache-2.0` license header required
by K-52. Running a reproduction is a read-only probe in an existing switch.

| Directory | Behaviour | Record |
| --- | --- | --- |
| [resolver-roots/](resolver-roots/README.md) | `rocqchk` aborts with the anomaly "Incompatible resolver roots" on a functor whose body opaquely ascribes a module holding a submodule, once the functor is applied; VST 2.17's `floyd/SeparationLogicAsLogicSoundness.v` has that shape. Upstream fixed the reported defect in [#22556](https://github.com/rocq-prover/rocq/pull/22556) on 2026-10-08; no fixed release is published as of 2026-10-10, and the locked 9.3.0 checker remains affected | [checker-resolver-anomaly.md](../../docs/assurance/checker-resolver-anomaly.md) |
