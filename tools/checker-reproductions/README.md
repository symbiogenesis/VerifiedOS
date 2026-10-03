# Checker reproductions

Standalone Rocq sources that reproduce a behaviour of the kernel checker, `rocqchk`,
first met on an upstream library. Each is authored from scratch in the library's module
shape and carries none of its content, so nothing of the upstream enters the checkout.
Each directory holds one behaviour: the trigger, the controls that differ from it by
one construct and check, a `run.sh` that compiles every file with a named switch's
`rocq c` and checks it with that switch's `rocqchk -silent -o`, and a README stating
the expected result per file and release. The record that reads the results lives
under `docs/assurance/`, indexed by [the document index](../../docs/README.md), and
cites the files here.

These files are not proof artifacts. The proof gate compiles only `proofs/`; the
citation, ledger and header rules (K-103, K-105, K-109) read the shipped proof set
under `proofs/` alone; and K-117's instrument table names no directory here, so no
rule holds a file in this tree to the proof set's conventions. Each file carries the
licence mark K-52 requires of every Gallina source. Running one is a short guest probe
in an existing switch, never an install.

| Directory | Behaviour | Record |
| --- | --- | --- |
| [resolver-roots/](resolver-roots/README.md) | `rocqchk` aborts with the anomaly "Incompatible resolver roots" on a functor whose body opaquely ascribes a module holding a submodule, once the functor is applied; VST 2.17's `floyd/SeparationLogicAsLogicSoundness.v` has that shape | [checker-resolver-anomaly.md](../../docs/assurance/checker-resolver-anomaly.md) |
