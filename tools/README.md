# The Tools

*Everything in this directory is Python 3.12. This document says why that is the rule, what each tool does, and the conventions every one of them keeps.*

## One language, and what forced it

The tools run in two places. The documents, the proofs metadata, and the checker run on the **Windows host**, where the repository is edited. The Sail model's build loops run inside **WSL**, where the toolchain lives. Those two lanes used to be written in three languages, one of which could not run in either place the other could:

| Interpreter | Windows host | WSL guest |
| --- | --- | --- |
| `python3` | 3.12.10 | 3.12.3 |
| `pwsh` | present | absent |
| `bash` | absent | present |

Python is the only one that spans both, so it is the only choice that makes the tools one thing rather than two. It also removes the seam that made them drift: a fact parsed on one side of it was re-parsed by hand on the other, which is the defect [check.py](check.py) exists to catch, running loose in the tools that catch it.

Nothing was lost in the move. The one thing a shell could do that looked out of reach, raising the OCaml stack the Sail emission needs, is `resource.setrlimit` in the parent and inheritance in every child; and the one thing the shell did badly, `/usr/bin/time` reporting the running maximum resident set over every child so far, is `os.wait4` reporting the child that was actually asked about.

The floor is **3.12**, because that is Ubuntu 24.04's system interpreter and the model lane is not going to carry a second one. Nothing here uses syntax or a standard-library call newer than that, and everything runs unchanged on later versions.

## What each tool is

| Tool | Lane | What it does |
| --- | --- | --- |
| [check.py](check.py) | host | Checks every derived fact against the artifact that owns it. `--fix` rewrites the figures that are arithmetic. |
| [check-selftest.py](check-selftest.py) | host | Seeds each of the checker's rules a defect it must report, and fails on a rule that says nothing. |
| [blast-radius.py](blast-radius.py) | host | Answers what an edit to the apex statement re-opens, before the work starts. |
| [proof-gate.py](proof-gate.py) | WSL | Compiles every shipped proof and holds its assumption set against the declared one. |
| [model.py](model.py) | WSL | Every loop over the curated Sail model: `typecheck`, `emit`, `build`, `sweep`, `trace-diff`, `config-keys`, `validate-config`, `keepalive`. |

The shared machinery is [vos/](vos/), and it holds parses, never decisions: [corpus.py](vos/corpus.py) reads the documents, [register.py](vos/register.py) the register and the tables other documents count, [apex.py](vos/apex.py) the statement's Vocabulary record, [figures.py](vos/figures.py) how a derived figure is spelled and repaired, [trace.py](vos/trace.py) the two executors' trace dialects, [jsonc.py](vos/jsonc.py) the model's configuration dialect, and [env.py](vos/env.py) the build environment. The checks themselves live in [vos/checks/](vos/checks/), one module per rule group, each carrying its group's reasoning beside its code.

[check-rules.md](check-rules.md) is the checker's registry: one row per rule, what passing means, and on what ground. It is the reviewable account of the tool's reach, and the checker holds it against the code in both directions on every run.

## Running them

From anywhere. Every tool finds the repository root from its own location, never from the working directory, so there is no wrong directory to run one from.

```console
$ python tools/check.py                       # the daily check
$ python tools/check.py --fix                 # and rewrite what is arithmetic
$ python tools/check-selftest.py              # every rule against its own mutant
$ python tools/blast-radius.py --field spatial_safety

$ wsl -d Ubuntu -u root -e python3 tools/model.py typecheck
$ wsl -d Ubuntu -u root -e python3 tools/model.py build
$ wsl -d Ubuntu -u root -e python3 tools/model.py trace-diff --corpus --floor 97
$ wsl -d Ubuntu -u root -e python3 tools/proof-gate.py
```

`model.py build` writes its whole run to a log and prints only where the log is, because a fifteen-minute build is started and left. The last line it writes is `ALL_DONE`, so a caller waits on a marker instead of guessing at a sleep.

## The conventions

Each of these is a rule the next tool added is expected to keep.

- **Exit 0 is clean, 1 is a finding.** Nothing else is returned, and nothing returns 0 while printing a problem.
- **The root is found, not assumed.** `vos.corpus.find_root` walks up from the tool's own file. No tool reads the working directory, and no tool needs `cd` first.
- **A run is one verdict per rule.** `ok <rule>: <what it decided>` or `FAIL <rule>: <n> <what went wrong>` with the findings indented under it. A check prints nothing else.
- **Output is accumulated, not streamed.** A run is data the caller can read back, which is what lets the selftest call the checker and read its verdict instead of parsing stdout.
- **Repairs preserve bytes.** Every write goes through `newline=""` and explicit UTF-8, so a one-token edit to a CRLF document does not silently rewrite the whole file to LF.
- **Arithmetic is repaired, judgment is reported.** A figure that is a sum over an artifact is rewritten under `--fix`. A figure that is somebody's decision is left standing as a finding, because absorbing it would delete the decision.
- **A parse is written once.** If two tools ask the same question of one file, the parse lives in [vos/](vos/) and neither carries a copy. Two copies of one fact is the defect this repository is built to catch.

## Adding a rule to the checker

Three edits, and the tools refuse to let one be forgotten:

1. The check itself, in the [vos/checks/](vos/checks/) module for its group.
2. Its row in [check-rules.md](check-rules.md). The meta group fails on a rule with no row and a row with no rule.
3. Its mutant in [check-selftest.py](check-selftest.py). The selftest fails on a registered rule with no case, and on a case whose mutation no longer applies.

A rule that reads an enumeration owes the floors group a member count too, so that the day its pattern stops matching anything is the day it says so rather than the day it starts passing vacuously.
