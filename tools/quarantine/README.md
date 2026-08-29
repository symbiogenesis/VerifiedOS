# The Quarantine

*Two whole instruments whose decisions are deferred, the two rules that hold them, and the one command that runs all of it. Nothing here is broken, retired, or half-built. Each is what its decision will be taken with, and each is here because the decision is not takeable yet.*

## What is here

| Path | What it is |
| --- | --- |
| [freeze.py](freeze.py) | The profile-freeze measurement instrument: the corpus, the recipe, the ordered act, the region classes and their refusals, the report's two renderings, and the twelve CI predicates of §9 as predicates over the record |
| [freeze-report.py](freeze-report.py) | The instrument, run against [the contract that defines it](../../docs/freeze-measurement-contract.md), in three renderings |
| [banks.py](banks.py) | The second class's bank grant, out of the composition and out of [the exploration contract](../../docs/bank-count-dse-contract.md) |
| [bank-dse.py](bank-dse.py) | Every candidate bank count, scored against the arithmetic that exists without a coefficient, admitting none |
| [checks/](checks/) | K-77 and K-58, the two rules that hold each instrument against the contract it answers |
| [check-rules.md](check-rules.md) | This directory's own rule registry, held against those checks in both directions |
| [tests/](tests/) | The three test modules that moved with the instruments, one seeded defect per CI predicate among them |
| [gate.py](gate.py) | The one command over all of the above |

The two **contracts** stayed in [docs/](../../docs/), and deliberately. They are specifications the register cites and other rules read: the freeze contract is held against the register by the views group and against R-15-014a's closed delta by K-70, and the bank contract is one of the three artifacts K-55 requires to go on booking the per-class bank count as open. What was quarantined is the machinery, never the obligation.

## How it is run

```console
$ python tools/quarantine/gate.py           # everything below, one verdict
$ python tools/quarantine/bank-dse.py       # the second class's bank grant, scored
$ python tools/quarantine/freeze-report.py  # the freeze's ordered act, and what it waits on
$ python tools/quarantine/freeze-report.py --json      # as the record the CI gate reads
$ python tools/quarantine/freeze-report.py --markdown  # as the rendering a curator reads
```

`gate.py` runs the two rules over the live tree, the floors under them, one seeded mutant per rule, this directory's registry against the checks carrying it, and the three test modules, and answers with one exit code. It is **not** a member of [tools/gate.py](../gate.py) and is not run before a landing. It is run when something here or in one of the two contracts is edited, and at the milestone that un-quarantines an instrument.

The tools may be run from anywhere: each finds the repository root from its own location, exactly as every tool in [tools/](../) does.

## Why they are not in the landing loop

[tools/gate.py](../gate.py) is what runs before anything lands, and every second in it is paid by every change whether or not the change is about the thing being checked. These two are paid by every change and are about decisions nobody can take:

- **The freeze's ordered act is behind the M8a gate.** The analyzer joins three inputs (§4 of the contract): the provenance sidecar stream, the link map, and the encoded image. The first is M1.2's backend and the other two are M1.4′'s linker and image composer, and M1.8b, which runs the sweep and publishes the report, is deferred behind the M8a gate with the freeze it serves. So no member of §2's corpus exists, no byte or cycle column is a measurement, eight of the twelve CI predicates defer on a named symbol, and the report says on its own face that it is not a freeze.
- **The bank count's hard constraint has no operands.** M0.17 ran the exploration and its result was that no candidate is admitted: the droop envelope R-15-247p makes a hard admission constraint wants two coefficients, and both are pending on a macro nobody has measured, which is what the composition's own `qualified` flag records (R-15-247m). Six of the contract's seven symbols are pending and one is stated.

## What un-quarantines them, and when

Each instrument leaves separately, and each leaves on a condition a person can check rather than on a judgment.

| Instrument | Milestone | The condition, stated so the reverse act is mechanical |
| --- | --- | --- |
| The freeze analyzer, with K-77 | **M1.8b**, behind the M8a gate and M1.4′ | `freeze-report.py` reports fewer than three of §4's three inputs absent. The sidecar stream, the link map and the encoded image are what M1.2 and M1.4′ produce, and the first of them to land is the first run in which a column is a measurement rather than a symbol. At that point the instrument is on the critical path of a decision being taken, and a rule that holds it against its contract belongs where every landing pays for it. |
| The bank-count instrument, with K-58 | **R4** and **R5** | `bank-dse.py`'s residuals report no pending coefficient for the droop envelope, and the composition's `qualified` flag reads true. R4 specifies the second-class macro architecture and R5 measures it, and the flag is the one artifact that records whether a macro has been measured, which is why K-58 reads it in the direction that bites while the class is unqualified. |

The reverse act is the forward one read backwards, and it is four moves and no design: the instrument and its check go back to `tools/` and `tools/vos/`, the rule's row goes back into [tools/check-rules.md](../check-rules.md), its mutants go back into [tools/check-selftest.py](../check-selftest.py), and the floors its enumerations owe go back into the floors group. K-83 is what makes the list exhaustive: while it is green, nothing outside this directory has come to depend on what is inside it, so there is no fifth move to discover.

## The one rule that makes this a quarantine and not a folder

This directory is an ordinary Python package on `tools/`. `import quarantine.freeze` resolves for any tool that puts its own directory on the path, exactly as `import vos.freeze` did before the move, so moving the files decoupled nothing by itself: the first tool in the landing loop to reach back in would restore the coupling with every gate still green.

**K-83** is what closes that, and it stays in the landing loop because its subject is the landing loop. No source under `tools/` that this directory does not carry may import one of its modules or name its directory as a path, both rosters being read off the git index rather than transcribed, so a module added here is protected the day it is staged and a tool added there is inside the rule the same day. It is registered in [tools/check-rules.md](../check-rules.md) with the rest of the checker's reach and its reasoning lives beside its code in [tools/vos/checks/meta.py](../vos/checks/meta.py).

The direction that is permitted is the other one: this directory reads [vos/](../vos/) for the parses, the corpus and the reporting convention, and [tests/](../tests/) for the case vocabulary its own test modules are written in. A quarantine that could not read the shared machinery would be a fork, which is the failure mode this one is built to avoid.
