# The Tools

*Everything in this directory is Python 3.14. This document says why that is the rule, what each tool does, and the conventions every one of them keeps.*

## One language, and what forced it

The tools run in two places. The documents, the proofs metadata, and the checker run on the **Windows host**, where the repository is edited. The Sail model's build loops run inside **WSL**, where the toolchain lives. Those two lanes used to be written in three languages, one of which could not run in either place the other could:

| Interpreter | Windows host | WSL guest |
| --- | --- | --- |
| Python | 3.14.7 | 3.14.4 |
| `pwsh` | present | absent |
| `bash` | absent | present |

Python is the only one that spans both, so it is the only choice that makes the tools one thing rather than two. It also removes the seam that made them drift: a fact parsed on one side of it was re-parsed by hand on the other, which is the defect [check.py](check.py) exists to catch, running loose in the tools that catch it.

Nothing was lost in the move. The one thing a shell could do that looked out of reach, raising the OCaml stack the Sail emission needs, is `resource.setrlimit` in the parent and inheritance in every child; and the one thing the shell did badly, `/usr/bin/time` reporting the running maximum resident set over every child so far, is `os.wait4` reporting the child that was actually asked about.

The floor is **3.14**, because that is Ubuntu 26.04's system interpreter and the model lane is not going to carry a second one. The host is held at the same version deliberately rather than by coincidence: one interpreter across both lanes is what stops a tool passing on the side it was written on and failing on the side it runs on.

Two things at that floor the tools depend on rather than merely tolerate:

- **Annotations are lazy by default** ([PEP 649](https://peps.python.org/pep-0649/)), so no module here carries `from __future__ import annotations`. Under 3.14 that import is the *opt-out*: it selects the older stringized semantics, which is the reverse of what a file wanting current behaviour should say. Nothing in these tools reads `__annotations__` or calls `get_type_hints`, so the change is invisible at every use site and the line is simply gone.
- **`os.process_cpu_count()`** reports the cores this process may actually run on, honouring an affinity mask wherever one exists. Job sizing in [vos/env.py](vos/env.py) is one call rather than a `sched_getaffinity`-or-`cpu_count` branch that had to name the platform to pick between them.

Two more were considered and refused, because a version floor is a licence to use what pays and not an obligation to use what is new. `pathlib.Path.copy` would replace `shutil.copy2` one call for one call and buy nothing at sites the selftest runs fifty times over. Unparenthesized `except A, B:` ([PEP 758](https://peps.python.org/pep-0758/)) is spelling, and a handler reads the same either way.

## What each tool is

| Tool | Lane | What it does |
| --- | --- | --- |
| [check.py](check.py) | host | Checks every derived fact against the artifact that owns it. `--fix` rewrites the figures that are arithmetic. |
| [check-selftest.py](check-selftest.py) | host | Seeds each of the checker's rules a defect it must report, and fails on a rule that says nothing. |
| [blast-radius.py](blast-radius.py) | host | Answers what an edit to the apex statement re-opens, before the work starts. |
| [proof-gate.py](proof-gate.py) | WSL | Compiles every shipped proof and holds its assumption set against the declared one. |
| [model.py](model.py) | WSL | Every loop over the curated Sail model: `typecheck`, `emit`, `build`, `oracle`, `sweep`, `corpus`, `asm`, `trace-diff`, `config-keys`, `validate-config`, `keepalive`. |

The shared machinery is [vos/](vos/), and it holds parses, never decisions: [corpus.py](vos/corpus.py) reads the documents, [register.py](vos/register.py) the register and the tables other documents count, [apex.py](vos/apex.py) the statement's Vocabulary record, [figures.py](vos/figures.py) how a derived figure is spelled and repaired, [trace.py](vos/trace.py) the executors' trace dialects, [jsonc.py](vos/jsonc.py) the model's configuration dialect, and [env.py](vos/env.py) the build environment. The checks themselves live in [vos/checks/](vos/checks/), one module per rule group, each carrying its group's reasoning beside its code.

Four more modules are the differential corpus's, and they are named for what they are rather than for where they sit: [dialect.py](vos/dialect.py) is one row per mnemonic the curated model decodes, [asm.py](vos/asm.py) the parser and layout over it, [image.py](vos/image.py) the ELF the emulator loads, and [differential.py](vos/differential.py) the corpus manifest. The one name that has to be read carefully is `corpus`: [vos/corpus.py](vos/corpus.py) reads the *documents* this repository checks, and [vos/differential.py](vos/differential.py) reads the *programs* the model runs. They share a word and nothing else.

[check-rules.md](check-rules.md) is the checker's registry: one row per rule, what passing means, and on what ground. It is the reviewable account of the tool's reach, and the checker holds it against the code in both directions on every run.

## Running them

From anywhere. Every tool finds the repository root from its own location, never from the working directory, so there is no wrong directory to run one from.

```console
$ python tools/check.py                       # the daily check
$ python tools/check.py --fix                 # and rewrite what is arithmetic
$ python tools/check-selftest.py              # every rule against its own mutant
$ python tools/blast-radius.py --field spatial_safety

$ wsl -u root -e python3 tools/model.py typecheck
$ wsl -u root -e python3 tools/model.py build
$ wsl -u root -e python3 tools/model.py oracle
$ wsl -u root -e python3 tools/model.py corpus
$ wsl -u root -e python3 tools/model.py corpus --refresh
$ wsl -u root -e python3 tools/model.py trace-diff --corpus --floor 67
$ wsl -u root -e python3 tools/proof-gate.py
```

There is no `-d`, because there is one Ubuntu and it is WSL's default. The name is plain `Ubuntu` and the release is 26.04; nothing in the tools reads the distribution's name, so the only thing holding this together is that default. `wsl --install` sets the newly installed distribution as the default, so installing another one is the single action that quietly redirects every command above. `wsl -s Ubuntu` puts it back.

The two lanes spell the interpreter differently, and that is not an oversight. On the host there is no `python3` to type: the python.org installer ships `python.exe` and `pythonw.exe` and no third spelling, so `python` is the name, with `py -3.14` available when several versions are installed. Inside the guest the reverse holds. Ubuntu ships `python3` and no bare `python` at all; this distribution answers to both only because `python-is-python3` is installed on it, and [PEP 394](https://peps.python.org/pep-0394/) still names `python3` as the one spelling a script may assume. So the shebangs stay `#!/usr/bin/env python3` and so does every WSL command written down here, because both have to work on a stock 26.04 that has never had that metapackage. Treating `python` as portable is the one shortcut this rule exists to refuse.

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
