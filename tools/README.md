# The Tools

*Everything in this directory is Python 3.14. This document says why that is the rule, what each tool does, and the conventions every one of them keeps.*

## One language, and what forced it

The tools run in two places. The documents, the proofs metadata, and the checker run on the **Windows host**, where the repository is edited. The Sail model's build loops run inside **WSL**, where the toolchain lives. Three interpreters are in reach across those two lanes, and only one of them runs in both:

| Interpreter | Windows host | WSL guest |
| --- | --- | --- |
| Python | 3.14.7 | 3.14.4 |
| `pwsh` | present | absent |
| `bash` | absent | present |

Python is the only one that spans both, so it is the only choice that makes the tools one thing rather than two. It also closes the seam a split would open: a fact parsed on one side of it re-parsed by hand on the other, which is the defect [check.py](check.py) exists to catch, running loose in the tools that catch it.

Nothing a shell offers is out of reach. Raising the OCaml stack the Sail emission needs is `resource.setrlimit` in the parent and inheritance in every child; and where a shell measures a stage badly, `/usr/bin/time` reporting the running maximum resident set over every child so far, `os.wait4` reports the child that was actually asked about.

The floor is **3.14**, because that is Ubuntu 26.04's system interpreter and the model lane is not going to carry a second one. The host is held at the same version deliberately rather than by coincidence: one interpreter across both lanes is what stops a tool passing on the side it was written on and failing on the side it runs on.

Two things at that floor the tools depend on rather than merely tolerate:

- **Annotations are lazy by default** ([PEP 649](https://peps.python.org/pep-0649/)), so no module here carries `from __future__ import annotations`. Under 3.14 that import is the *opt-out*: it selects the older stringized semantics, which is the reverse of what a file wanting current behaviour should say. This is load-bearing rather than incidental. Every check group annotates its `run` with the `Context` it is handed, and `Context` lives in the package `__init__` that imports the group, so naming it at run time would be a cycle. Deferred evaluation means the annotation is written plainly, imported only under `TYPE_CHECKING`, and never evaluated by anything: no quotes, no cycle, and no import paid for at startup. Nothing here reads `__annotations__` or calls `get_type_hints`, which is what makes that safe.
- **`os.process_cpu_count()`** reports the cores this process may actually run on, honouring an affinity mask wherever one exists. Job sizing in [vos/env.py](vos/env.py) is one call rather than a `sched_getaffinity`-or-`cpu_count` branch that had to name the platform to pick between them.

Two more the floor makes available go unused, because a version floor is a licence to use what pays and not an obligation to use what is new. `pathlib.Path.copy` would replace `shutil.copy2` one call for one call and buy nothing at sites the selftest runs fifty times over. Unparenthesized `except A, B:` ([PEP 758](https://peps.python.org/pep-0758/)) is spelling, and a handler reads the same either way.

## What each tool is

| Tool | Lane | What it does |
| --- | --- | --- |
| [gate.py](gate.py) | host | Runs check.py, check-selftest.py and typecheck.py together, one verdict over the three. `--fix` sends the repair in first, alone. |
| [check.py](check.py) | host | Checks every derived fact against the artifact that owns it. `--fix` rewrites the figures that are arithmetic. |
| [check-selftest.py](check-selftest.py) | host | Seeds each of the checker's rules a defect it must report, and fails on a rule that says nothing. |
| [typecheck.py](typecheck.py) | host | Holds this directory's own Python to the discipline it holds the documents to. |
| [test.py](test.py) | host | Runs the tools' own behavioral tests, one module per subject under [tests/](tests/). |
| [blast-radius.py](blast-radius.py) | host | Answers what an edit to the apex statement re-opens, before the work starts. |
| [bank-dse.py](bank-dse.py) | host | Scores every candidate second-class bank count against the arithmetic the composition fixes, and admits none: the hard constraint's coefficients are pending. |
| [co-read.py](co-read.py) | host | Prints a register entry against the prose it was extracted from, and records the reading K-61 asks for. |
| [read-view.py](read-view.py) | host | Weaves the specification and the register into one generated reading view, each entry rendered beneath the bookmark that cites it, written outside the corpus and never a source. |
| [proof-gate.py](proof-gate.py) | WSL | Compiles every shipped proof in Require-derived dependency waves, accumulates every failure, and holds each assumption set against the declared one; a concurrent run blocks until the holder is done. |
| [model.py](model.py) | WSL | Every loop over the curated Sail model: `typecheck`, `emit`, `build`, `wait`, `lane`, `oracle`, `sweep`, `corpus`, `asm`, `trace-diff`, `devicetree`, `reference`, `config-keys`, `validate-config`, `keepalive`. |

The shared machinery is [vos/](vos/), and it holds parses, never decisions: [corpus.py](vos/corpus.py) reads the documents, [register.py](vos/register.py) the register and the tables other documents count, [apex.py](vos/apex.py) the statement's Vocabulary record, [figures.py](vos/figures.py) how a derived figure is spelled and repaired, [trace.py](vos/trace.py) the executors' trace dialects, [jsonc.py](vos/jsonc.py) the model's configuration dialect with [config.py](vos/config.py) the one decoder over it, [coread.py](vos/coread.py) the pairing between a register entry and the prose it cites, [fieldbindings.py](vos/fieldbindings.py) the field-bindings table the bindings group and [blast-radius.py](blast-radius.py) both read, and [env.py](vos/env.py) the build environment. Two more read a *model* fact a document restates rather than a document: [geometry.py](vos/geometry.py) the welded block size and [banks.py](vos/banks.py) the second class's bank grant. The checks themselves live in [vos/checks/](vos/checks/), one module per rule group, each carrying its group's reasoning beside its code.

Those two are where the checker reaches past its own corpus, and the reach is declared rather than habitual. `model/` is excluded from the document corpus by name, and [check-selftest.py](check-selftest.py) stands the whole tree up as empty files to save copying what no rule opens, so a model path a rule reads has to be admitted by one of two declarations in [corpus.py](vos/corpus.py) or it passes on the host and fails every sandbox's baseline.

**The two declarations are narrow for opposite reasons and are deliberately not one list.** `MODEL_FACTS` names five files by path: it is the *value* window, and a rule reading a number out of the model should name the file it reads, so adding one is a decision somebody makes. `is_model_citation_path` admits by kind instead, because the rule behind it holds a construct that occurs wherever the model argues from the register, and a window sized for the other purpose left it reporting `ok` about a fifth of its subject. Merging them would make the audited list quietly mean two things.

Four more modules are the differential corpus's, and they are named for what they are rather than for where they sit: [dialect.py](vos/dialect.py) is one row per mnemonic the curated model decodes, [asm.py](vos/asm.py) the parser and layout over it, [image.py](vos/image.py) the ELF the emulator loads, and [differential.py](vos/differential.py) the corpus manifest. The one name that has to be read carefully is `corpus`: [vos/corpus.py](vos/corpus.py) reads the *documents* this repository checks, and [vos/differential.py](vos/differential.py) reads the *programs* the model runs. They share a word and nothing else.

[check-rules.md](check-rules.md) is the checker's registry: one row per rule, what passing means, and on what ground. It is the reviewable account of the tool's reach, and the checker holds it against the code in both directions on every run.

## Running them

From anywhere. Every tool finds the repository root from its own location, never from the working directory, so there is no wrong directory to run one from.

```console
$ python tools/gate.py                        # the three gates below, in one run
$ python tools/gate.py --fix                  # the repair first, then the other two
$ python tools/check.py                       # the daily check
$ python tools/check.py --fix                 # and rewrite what is arithmetic
$ python tools/check-selftest.py              # every rule against its own mutant
$ python tools/typecheck.py                   # the tools against their own discipline
$ python tools/test.py                        # the tools against their own tests
$ python tools/blast-radius.py --field spatial_safety
$ python tools/bank-dse.py                    # the second class's bank grant, scored
$ python tools/co-read.py                     # the pairs owed a reading
$ python tools/co-read.py --show R-15-073c    # one pair, side against side
$ python tools/co-read.py --show --all        # every pending pair, in one read
$ python tools/co-read.py --where R-15-073c   # both sides as file:line sites
$ python tools/read-view.py                   # the two documents woven, for reading

$ wsl -u root -e python3 tools/model.py typecheck
$ wsl -u root -e python3 tools/model.py lane           # where this checkout builds
$ wsl -u root -e python3 tools/model.py build --background
$ wsl -u root -e python3 tools/model.py wait           # and its verdict when it lands
$ wsl -u root -e python3 tools/model.py oracle
$ wsl -u root -e python3 tools/model.py corpus
$ wsl -u root -e python3 tools/model.py corpus --refresh
$ wsl -u root -e python3 tools/model.py devicetree
$ wsl -u root -e python3 tools/model.py reference
$ wsl -u root -e python3 tools/model.py trace-diff --corpus --floor 67
$ wsl -u root -e python3 tools/proof-gate.py
```

There is no `-d`, because there is one Ubuntu and it is WSL's default. The name is plain `Ubuntu` and the release is 26.04; nothing in the tools reads the distribution's name, so the only thing holding this together is that default. `wsl --install` sets the newly installed distribution as the default, so installing another one is the single action that quietly redirects every command above. `wsl -s Ubuntu` puts it back.

The two lanes spell the interpreter differently, and that is not an oversight. On the host there is no `python3` to type: the python.org installer ships `python.exe` and `pythonw.exe` and no third spelling, so `python` is the name, with `py -3.14` available when several versions are installed. Inside the guest the reverse holds. Ubuntu ships `python3` and no bare `python` at all; this distribution answers to both only because `python-is-python3` is installed on it, and [PEP 394](https://peps.python.org/pep-0394/) still names `python3` as the one spelling a script may assume. So the shebangs stay `#!/usr/bin/env python3` and so does every WSL command written down here, because both have to work on a stock 26.04 that has never had that metapackage. Treating `python` as portable is the one shortcut this rule exists to refuse.

`model.py build` writes its whole run to a log and prints only where the log is, because a fifteen-minute build is started and left. The last line it writes is `ALL_DONE`, so a caller waits on a marker instead of guessing at a sleep.

`test.py` leaves the cases marked slow to `--slow`, so the default run answers in seconds.

`trace-diff` bounds each executor run with `--timeout`, so an emulator that hangs without retiring instructions becomes a SHORT finding instead of a command that never returns.

## One toolchain, several checkouts

There is one WSL toolchain and there are as many checkouts as there are git worktrees, so the build trees have to be told apart. Each checkout gets a **lane**, and `model.py lane` prints which one this is, where it builds, and whether anything is building there right now.

The lane is derived from the checkout rather than declared: a linked worktree's `.git` is a *file* naming its administrative directory under the primary checkout's `.git/worktrees/`, and the lane is git's own name for the worktree, which is unique within the repository by construction. The primary worktree has no lane and keeps the paths it always had; a linked one builds under `/root/build/lane-<name>/`, which is one directory holding the whole of what that lane knows, so a lane is retired by deleting it. The one tree every lane shares is the M0.4 oracle's, because it is stock upstream at a pinned commit and none of this repository's curation reaches it.

**Three things collide when two checkouts share one tree, and only one of them is loud.** cmake refuses outright to point an existing cache at a second source directory, so the second lane's build fails at `configure` with an error that names cmake rather than the collision. A build opens its log with `w`, so the second lane truncates the first's while the first is still writing into it. And every loop downstream of a build reads the simulator back out of the build tree, `sweep`, `corpus`, `trace-diff`, `devicetree` and `reference` all of them, and none can tell whose model generated it: that one is silent, and it is the reason lanes exist.

A build **holds its lane** for exactly as long as it runs, so a second build over a live one is refused and named rather than merged into it. The lock is `flock` rather than a pidfile, so a killed build leaves nothing to break, and `model.py build --background` hands the lock to the run it detaches rather than dropping it. `model.py wait` blocks on that lock and then reports the log's verdict: the lock is released by the kernel whether the build finished or died, so a wait ends either way, where a wait on the marker alone would hang on the build that never wrote one.

A build is not the only holder of state, and every holder refuses a concurrent run by naming the one that holds it. `emit` takes the same lock as `build`, because both drive the one cmake tree; `typecheck` holds a lock beside its lane's SMT memo cache, which Sail rewrites whole at exit; and `oracle` holds the one tree every lane shares. `corpus` writes its images into the lane's own directory, so two lanes' runs cannot land one ELF path.

A lane standing up for the first time is seeded from the primary worktree's tree rather than built cold, which is what makes a lane cheap enough to be worth having. What is copied is the downloaded riscv-tests and the Sail SMT memo cache, and the cache is **copied and never shared**: see `model.py`'s `_seed_smt_cache` for what two writers of one memo cache do to each other.

## Checking the tools themselves

The documents are checked against each other by [check.py](check.py), and the checker is
checked against its own mutants by [check-selftest.py](check-selftest.py). Neither of
them reads a line of Python as Python, so without a gate of their own the tools are the
one artifact here with no proof, no model, and no reader but their author.
[typecheck.py](typecheck.py) is that gate for the Python's discipline, and it runs two
checkers because one cannot do the whole job; what a type cannot decide, the behavior, is
[test.py](test.py)'s to hold.

Three of those four decide about the tree as it stands, and they contend for nothing:
all three only read the checkout, and the two small ones fit inside the slack of the
large one. So [gate.py](gate.py) runs them as one command and one exit code, each
member's own report printed whole under its own heading in the order the tool declares
rather than the order the three finished in. Measured warm on a twelve-core host over
three alternated runs of each arm, the selftest alone takes a median 22.8 s, the wave
23.9 s, and the same three in sequence 26.0 s: the other two cost about a second inside
the wave where they cost three beside it. The saving is the smaller half of the point
and the single verdict is the larger. `--fix` is the one exception to the wave
and a correctness one, the repair running alone and to completion before the rest,
because the selftest opens by copying the working tree and a document rewritten
mid-copy seeds a torn sandbox that reports as a baseline failure about nothing.
[test.py](test.py) is deliberately not a member: it decides about the tools rather than
about this tree, and it is the one gate that runs the others.

| Checker | Pin | What it decides |
| --- | --- | --- |
| [ty](https://github.com/astral-sh/ty) | 0.0.74 | Every expression, against the types it can infer, with `--error all` |
| [ruff](https://github.com/astral-sh/ruff) | 0.16.4 | Every function, against whether it is annotated at all, and the correctness rules [ruff.toml](ruff.toml) admits |

The split is not a preference. ty infers rather than demands, so a function with no
annotations contradicts nothing and is invisible to it; ruff's `ANN` group is what makes
coverage a rule. Both are pinned for the reason Rocq and z3 are pinned, and a version
other than the pinned one is a finding rather than a warning.

Both install with `uv tool install ty==0.0.74` and `uv tool install ruff==0.16.4`, one
command each because a uv tool install is one environment holding one pinned tool. That
isolation is the point rather than a side effect: neither checker is a dependency of
anything here, so neither belongs in the environment ty resolves this directory's own
imports against, and the pinned checker stays the same one whichever interpreter runs
[typecheck.py](typecheck.py). The shims land in uv's tool bin directory, which
[typecheck.py](typecheck.py) looks in first, ahead of the interpreter's own script
directories and then `PATH`; all three are kept, because reporting absent what is
present is the one failure a pinned-version gate must not have.

`--error all` escalates every rule ty carries, including the ones it ships as warnings or
switched off, and that is deliberate: the alternative is a list of opt-ins that silently
stops growing the day ty adds a rule nobody transcribed. What ruff is *not* asked is in
[ruff.toml](ruff.toml): three rules, each named on its own line and each for a reason
that would hold in any project, and no group switched off to spare this code a rewrite. A
single site that has to differ carries a `# noqa` and the sentence saying why.

The settings live in [ty.toml](ty.toml) and [ruff.toml](ruff.toml) rather than on a
command line, so that an editor's language server decides exactly what this gate decides.

`jsonschema` is the third prerequisite and the one dependency here that is not the
standard library, `uv pip install --system jsonschema` on the host and `apt install
python3-jsonschema` in the guest. It is the one prerequisite that is **not** a uv tool
install, and the reason is the distinction that decides every such choice here: the two
checkers are tools this directory runs, so they get an environment of their own, while
this is a library this directory imports, so it has to be in the environment the
interpreter and ty both resolve against. It is required on **both** lanes although only the
guest validates a configuration, and that is what keeps the gate lane-independent rather
than merely convenient. ty resolves a third-party import against the environment it
finds, so an absent package is an `unresolved-import` and a suppression for it is an
`unused-ignore-comment` the moment the package is present: written for the lane that
lacks it, the directive is a finding on the lane that has it, and the gate's verdict
turns on what happens to be installed instead of on what the code says. ty.toml pins
`python-platform` for the same reason on the other axis, so that the tools are typed
against one declared target and not against whichever machine ran the checker. There is
no `ty: ignore` in this directory at all, which leaves every unresolved import an error
without a carve-out to audit.

## The conventions

Each of these is a rule the next tool added is expected to keep.

- **Exit 0 is clean, 1 is a finding.** argparse answers a usage error with 2, and a crash is a traceback rather than a verdict; nothing else is returned deliberately, and nothing returns 0 while printing a problem.
- **The root is found, not assumed.** `vos.corpus.find_root` walks up from the tool's own file. No tool reads the working directory, and no tool needs `cd` first.
- **A run is one verdict per rule.** `ok <rule>: <what it decided>` or `FAIL <rule>: <n> <what went wrong>` with the findings indented under it. A check prints nothing else.
- **Output is accumulated, not streamed.** A run is data the caller can read back, which is what lets the selftest call the checker and read its verdict instead of parsing stdout.
- **Repairs preserve bytes.** Every write goes through `newline=""` and explicit UTF-8, so a one-token edit to a CRLF document does not silently rewrite the whole file to LF.
- **Arithmetic is repaired, judgment is reported.** A figure that is a sum over an artifact is rewritten under `--fix`. A figure that is somebody's decision is left standing as a finding, because absorbing it would delete the decision.
- **A parse is written once.** If two tools ask the same question of one file, the parse lives in [vos/](vos/) and neither carries a copy. Two copies of one fact is the defect this repository is built to catch.
- **Every function is annotated, and every table is typed.** Not for documentation: a table of callbacks nothing types is a table where a member with the wrong shape is found by running the corpus rather than by reading the module, `dialect.KINDS` and `asm.PSEUDOS` being the two largest here. A dispatch family gets a `Protocol`, a configuration row gets a `TypedDict`, and a `list`, `dict` or `re.Match` written bare gets its parameter.
- **An invariant is stated where it is relied on.** A reader entitled to a value because two branches above ruled out the alternatives says so, rather than leaving a `None` to be subscripted at the point the tool is reporting the finding it exists to report.
- **Assertions that guard an artifact are raised, not asserted.** `python -O` deletes an `assert`, and a check standing between a mis-transcribed row and an image the emulator runs anyway has to outlive a flag. `zip` over two sequences that must correspond takes `strict=True` for the same reason: a silent truncation in a tool whose output is evidence is worse than a stopped run.

## Adding a rule to the checker

Three edits, and the tools refuse to let one be forgotten:

1. The check itself, in the [vos/checks/](vos/checks/) module for its group.
2. Its row in [check-rules.md](check-rules.md). The meta group fails on a rule with no row and a row with no rule.
3. Its mutant in [check-selftest.py](check-selftest.py). The selftest fails on a registered rule with no case, and on a case whose mutation no longer applies.

A rule that reads an enumeration owes the floors group a member count too, so that the day its pattern stops matching anything is the day it says so rather than the day it starts passing vacuously.

And whatever the edit, `python tools/typecheck.py` has to be green before it lands, the same way `python tools/check.py` does.
