# The Quarantine

*Two instruments whose decisions are deferred, the two rules that hold them, and the command that runs them.*

## What is here

| Path | What it is |
| --- | --- |
| [freeze.py](freeze.py) | The profile-freeze measurement instrument: corpus, recipe, region classes, refusal reasons, report renderings, and the thirteen CI predicates of [§9](../../docs/implementation/contracts/freeze-measurement.md#9-the-freeze-gate) |
| [freeze-report.py](freeze-report.py) | CLI entry point running [freeze.py](freeze.py) against [the freeze measurement contract](../../docs/implementation/contracts/freeze-measurement.md) |
| [banks.py](banks.py) | Second-class bank-grant reader over the shipped composition and [the exploration contract](../../docs/hardware/bank-count-dse-contract.md) |
| [bank-dse.py](bank-dse.py) | CLI entry point scoring candidate bank counts against the currently available arithmetic |
| [checks/](checks/) | K-77 and K-58, holding each instrument against its contract |
| [check-rules.md](check-rules.md) | This directory's rule registry, checked in both directions against [checks/](checks/) |
| [tests/](tests/) | Unit tests discovered by `gate.py`, including one seeded defect per freeze CI predicate |
| [gate.py](gate.py) | Single entry point running the rules, floors, registry check, mutants, and tests |

The two **contracts** remain in [docs/](../../docs/) as normative derived views: [freeze-measurement.md](../../docs/implementation/contracts/freeze-measurement.md) is checked against the register by the views group and against R-15-014a's closed delta by K-70, and [bank-count-dse-contract.md](../../docs/hardware/bank-count-dse-contract.md) is checked by K-55. Only the deferred measurement instruments and their two checker rules live here.

## How it is run

```console
$ python tools/quarantine/gate.py           # rules, floors, registry, mutants, and tests
$ python tools/quarantine/bank-dse.py       # score candidate second-class bank counts
$ python tools/quarantine/freeze-report.py  # human-readable freeze report
$ python tools/quarantine/freeze-report.py --json      # JSON record for the CI gate
$ python tools/quarantine/freeze-report.py --markdown  # Markdown report for review
```

`gate.py` runs K-58 and K-77, their enumeration floors, one seeded mutant per rule, the local registry check, and every test module under [tests/](tests/). It is not invoked by [tools/run.py](../run.py) during ordinary landings; run it when editing files in this directory or the two contracts, and when un-quarantining an instrument.

Every script resolves the repository root from its own file location and can be run from any working directory.

## Why they are not in the landing loop

- **The profile-freeze sweep is gated behind M8a.** `freeze.py` joins three inputs ([§4](../../docs/implementation/contracts/freeze-measurement.md#4-the-emitter-provenance-schema) of the contract): the provenance sidecar stream, the link map, and the encoded image. `run.py model freeze-emit` produces the link map and encoded image, while the provenance sidecar stream awaits M1.2's compiler backend and M1.8b's sweep. Until then, nine of the thirteen CI predicates defer on unproduced symbols.
- **The bank-count hard constraint awaits R5 measurements.** The droop envelope (R-15-247p) requires two macro-characterization coefficients that remain pending until R5 measures a physical macro, recorded by `qualified: false` in the composition (R-15-247m).

## What un-quarantines them, and when

| Instrument | Milestone | Un-quarantine condition |
| --- | --- | --- |
| The freeze analyzer, with K-77 | **M1.8b**, after the M8a gate and M1.4′ | `freeze-report.py` reports fewer than three of [§4](../../docs/implementation/contracts/freeze-measurement.md#4-the-emitter-provenance-schema)'s three inputs absent when **run after `run.py model freeze-emit`**. Running `freeze-emit` first makes the check independent of whether a fresh checkout has built the streams yet. Once the compiler backend emits the sidecar stream, the report produces real measurements and K-77 returns to the main checker. |
| The bank-count instrument, with K-58 | **R4** and **R5** | `bank-dse.py` reports no pending coefficient for the droop envelope, and the composition's `qualified` flag is `true` after R4 and R5 complete. |

To un-quarantine an instrument, move the module and its check back to `tools/` and `tools/vos/`, move its rule row back into [tools/check-rules.md](../check-rules.md) (via `tools/check-registry.json`), move its mutants back into [tools/run.py selftest](../vos/cli/selftest.py), and move its enumeration floors back into the `floors` group.

## The one rule that makes this a quarantine and not a folder

Because `tools/quarantine/` sits under `tools/`, an ordinary `import quarantine.freeze` would resolve for any tool on `tools/`. **K-83** in [tools/vos/checks/meta.py](../vos/checks/meta.py) prevents the landing loop from coupling to this directory: no tracked Python file under `tools/` outside `tools/quarantine/` may import `quarantine` or reference the directory as a path.

The reverse direction is allowed: modules in `tools/quarantine/` import shared parsers, corpus readers, and reporting helpers from [vos/](../vos/) and test helpers from [tests/](../tests/).
