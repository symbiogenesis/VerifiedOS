# The Tools

*Everything in this directory is Python 3.14. This document says why that is the rule, what each tool does, and the conventions every one of them keeps.*

## One language, and what forced it

The tools run in two places. The documents, the proofs metadata, and the checker run on the **Windows host**, where the repository is edited. The Sail model's build loops run inside **WSL**, where the toolchain lives. Three interpreters are in reach across those two lanes, and only one of them runs in both:

| Interpreter | Windows host | WSL guest |
| --- | --- | --- |
| Python | 3.14.7 | 3.14.4 |
| `pwsh` | present | absent |
| `bash` | the guest's | present |

`bash.exe` does resolve on the host, and it is WSL's launcher rather than a shell of its own: what it starts is the guest's bash, in the guest's filesystem, so writing for it is writing for the WSL lane under another name. There is no host bash to target.

Python is the only one that spans both, so it is the only choice that makes the tools one thing rather than two. It also closes the seam a split would open: a fact parsed on one side of it re-parsed by hand on the other, which is the defect [check.py](check.py) exists to catch, running loose in the tools that catch it.

Nothing a shell offers is out of reach. Raising the OCaml stack the Sail emission needs is `resource.setrlimit` in the parent and inheritance in every child; and where a shell measures a stage badly, `/usr/bin/time` reporting the running maximum resident set over every child so far, `os.wait4` reports the child that was actually asked about.

The floor is **3.14**, because that is Ubuntu 26.04's system interpreter and the model lane is not going to carry a second one. The host is held at the same version deliberately rather than by coincidence: one interpreter across both lanes is what stops a tool passing on the side it was written on and failing on the side it runs on.

Two things at that floor the tools depend on rather than merely tolerate:

- **Annotations are lazy by default** ([PEP 649](https://peps.python.org/pep-0649/)), so no module here carries `from __future__ import annotations`. Under 3.14 that import is the *opt-out*: it selects the older stringized semantics, which is the reverse of what a file wanting current behaviour should say. This is load-bearing rather than incidental. Every check group annotates its `run` with the `Context` it is handed, and `Context` lives in the package `__init__` that imports the group, so naming it at run time would be a cycle. Deferred evaluation means the annotation is written plainly, imported only under `TYPE_CHECKING`, and never evaluated by anything: no quotes, no cycle, and no import paid for at startup. Nothing here reads `__annotations__` or calls `get_type_hints`, which is what makes that safe.
- **`os.process_cpu_count()`** reports the cores this process may actually run on, honouring an affinity mask wherever one exists. Job sizing in [vos/env.py](vos/env.py) is one call rather than a `sched_getaffinity`-or-`cpu_count` branch that had to name the platform to pick between them.

Two more the floor makes available go unused, because a version floor is a licence to use what pays and not an obligation to use what is new. `pathlib.Path.copy` would replace `shutil.copy2` one call for one call and buy nothing at sites the selftest runs fifty times over. Unparenthesized `except A, B:` ([PEP 758](https://peps.python.org/pep-0758/)) is spelling, and a handler reads the same either way.

## One entry point, and the commands under it

There is one executable here, [run.py](run.py), and a command is a name rather than a
path. It was seventeen executables, and using them meant knowing which file answered
which question and which of the two lanes it ran in; both of those are now the tool's
to know. `python tools/run.py` with no command runs the host gate wave, which is what
has to be green before anything lands, and `run.py <command> --help` is that command's
own help. The wave and `run.py test` also run in CI, in
[.github/workflows/host-gates.yml](../.github/workflows/host-gates.yml), on an Ubuntu
runner at every push and pull request to `main`, over a clone with no submodule
checked out; the guest lane's loops run only by hand, on a machine that holds the
toolchain. CI green is a witness that the host gates passed on that commit and never a
substitute for the guest lane's evidence.

**The lane is the front door's business rather than the caller's.** A `[wsl]` command
asked for on the host is re-launched in the guest and says so, so there is no
`wsl -u root -e python3` to remember and no wrong lane to be in. A guest command has
to *drive* the toolchain to need the hop: `model config-keys`,
`model validate-config`, `model asm`, `model freeze-emit`, `rtl provenance`,
`rtl filelist`, `oracle list`, `oracle emit`, `seed list` and `testrig protocol` read
this checkout and answer on either lane. That is a declaration and not a description, so
[tests/test_lanes.py](tests/test_lanes.py) dispatches every member of it on whichever
lane the suite is running on, and holds every subcommand the table declares against
this page: one the table declares and this page nowhere names sends a reader into the
guest for an answer the host already had. Only that direction is held, and only against
the page rather than against this sentence; a name here the table does not declare is
caught by nothing, which is a residue the findings register carries.

| Command | Lane | What it does |
| --- | --- | --- |
| `gate` | host | The three gates below together, one verdict over them. `--fix` sends the repair in first, alone; `--tests` adds the fourth. This is what a bare `run.py` runs. |
| `check` | host | Checks every derived fact against the artifact that owns it. `--fix` rewrites the figures that are arithmetic. It is also [check.py](check.py), the one command that is still a path, because the register, the coverage matrix, the crown jewels, the field bindings and the findings register all cite that path for what it decides. |
| `selftest` | host | Seeds each of the checker's rules a defect it must report, and fails on a rule that says nothing. |
| `typecheck` | host | Holds this directory's own Python to the discipline it holds the documents to. |
| `test` | host | Runs the tools' own behavioral tests, one module per subject under [tests/](tests/). |
| `coread` | host | Prints a register entry against the prose it was extracted from, and records the reading K-61 asks for. |
| `view` | host | Weaves the specification and the register into one generated reading view, each entry rendered beneath the bookmark that cites it, written outside the corpus and never a source. |
| `blast` | host | Answers what an edit to the apex statement re-opens, before the work starts. |
| `provision` | wsl | The lane this repository builds in, as a table of facts a machine can act on: one row per switch, pin, checker and prerequisite, each naming the loop that wants it, the artifact that owns it, and what a probe actually found. The default reports and changes nothing; `--apply` installs what is absent and re-probes; `--only` narrows to the gate's rows or the toolchain's and says which rows it did not decide about. |
| `model` | wsl | Every loop over the curated Sail model: `typecheck`, `bundle`, `emit`, `build`, `wait`, `lane`, `oracle`, `sweep`, `corpus`, `asm`, `freeze-emit`, `trace-diff`, `devicetree`, `reference`, `config-keys`, `validate-config`, `keepalive`. `bundle` regenerates the machine-readable view of the model the host lane reads it through, and `bundle --check` holds the tracked one against what Sail writes now, which is the half of K-88 a host with no Sail cannot take. |
| `evidence` | wsl | The exit-evidence sweep as one run, six members in the order it runs them: the build and its bundled suite, the reference, the profile sweep, the differential corpus, the devicetree and the proof gate, with the block of figures a completion note quotes. The `$[test]` property harness is one of those figures rather than a seventh member, read back out of what `reference` printed. |
| `rtl` | wsl | The RTL lane: `provenance` parses the synthesis record and `filelist` composes the curated arm's elaboration file list, both on either lane; `lint`, `vectors`, `crosscheck`, `elaborate` and `wait` need the guest. `elaborate` elaborates the imported core at the curated configuration and at a baseline and names every structure the disabling parameters remove, and `wait` reports the verdict of a backgrounded one; `vectors` compiles the model's capability format with a generator that prints what its functions return, and `crosscheck` requires the authored SystemVerilog to reproduce every line. **A curation replaces imported sources as well as re-valuing parameters**, so `rtl.py`'s `SUBSTITUTIONS` declares which authored source stands where the imported manifest names imported ones, that declaration reaches the curated arm alone, and the diff is partitioned rather than signed: a kind the curated arm instantiates and the baseline does not is an introduction where an authored source in its file list declares that module and a finding where none does, and a kind the baseline instantiates and the curated arm does not is the parameters' own only where no replaced source declared it. |
| `oracle` | wsl | The model-as-oracle vector generator, which is that Sail generator with the question taken out of it: a spec names the model sources and the domain, and this emits the harness, compiles it against them, and runs it. `list` and `emit` answer on either lane; `vectors` needs Sail. |
| `seed` | wsl | The seeded-defect generator: mutation operators walked over a Sail or Gallina source, pointed at an oracle that must notice. `list` answers on either lane; `sail`, `coq` and `properties` each need their oracle's toolchain. |
| `quickchick` | wsl | The Gallina front's input side, which the Wasm oracle has never had: `vectors` runs the enumerative half in the CertiRocq oracle's own switch, `properties` runs the randomized half under QuickChick in a switch of its own, and `check` says which switch holds what. |
| `testrig` | wsl | The RVFI-DII rig: `protocol` reads the wire format off the codec on either lane; `handshake`, `run` and `bridge` drive the emulator over a socket in the guest. `run` generates a DII stream, adjudicates the emulator against itself under a seeded defect, and shrinks the counterexample; `bridge` holds one run's packets against the commit records the same run wrote. |
| `proofs` | wsl | Compiles every shipped proof in Require-derived dependency waves, accumulates every failure, and holds each assumption set against the declared one; a concurrent run blocks until the holder is done. The same run holds R-05-166's decidable half: every record a file's theorems quantify over must be constructed in that file or one it Requires, by a closed definition typed at it (the `demo` convention), by its `Build_` constructor or by a record literal, and the closed definitions are reported as each file's witness count beside its constant count. Whether a witness is non-trivial is a judgement the gate does not make. |

Each command is one module of [vos/cli/](vos/cli/), which is what those executables
became: each keeps its docstring, its argparse and its `main(argv)`, less its own
preamble and its own `__main__` block. [vos/cli/\_\_init\_\_.py](vos/cli/__init__.py)
is the table `run.py` reads, and it is the only place a command's name, its module and
its lane are written down.

Five directories are inputs rather than commands. [generated/](generated/) is the one this repository does not author: it holds the model's own machine-readable bundle of itself, emitted by Sail and tracked so that the host lane can read the model without one, and K-88 holds it byte-for-byte against what the emitter writes. It is under `tools/` rather than under `model/` because `model/` is `-text` in [.gitattributes](../.gitattributes) and vendored byte-identically from its upstream pin, and a generated artifact there would break both properties at once. [oracle-specs/](oracle-specs/) is
one JSON file per oracle: the sources to compile, and per line kind the parameters,
the domain that walks them, the Sail that calls the model, and what to print.
[cheri-equiv/](cheri-equiv/) is the cross-check's two halves, a Sail generator that
calls the model's capability functions and a SystemVerilog testbench that replays what
it printed; neither is a translation of the other and the only thing they share is the
line format each states in its own header. [quickchick/](quickchick/) is the Gallina
harnesses. [wasm-oracle/](wasm-oracle/) is the container the CertiCoq → Wasm oracle is
built and run in, and [its own README](wasm-oracle/README.md) states what it pins.

[quarantine/](quarantine/) is the exception to the one entry point, and deliberately:
it holds the two instruments whose decisions are deferred, the two rules that hold
them, and [its own gate](quarantine/gate.py), the one command over all of it. K-83 is
what makes it a quarantine rather than a folder, and it forbids exactly the coupling a
`run.py` command would be. What that rule holds out is the *landing loop* reaching in,
so the reverse is open and is taken: that gate seeds at least one defect per rule and
reports the result through [vos/seeded.py](vos/seeded.py) like every other loop that
seeds one, which is what keeps a mutation whose seed no longer applies and a mutant the
rule said nothing about from arriving as one undifferentiated failure. [Its README](quarantine/README.md) states what each
instrument waits on and what un-quarantines it.

The shared machinery is [vos/](vos/), and it holds parses, never decisions: [corpus.py](vos/corpus.py) reads the documents, [register.py](vos/register.py) the register and the tables other documents count, [apex.py](vos/apex.py) the statement's Vocabulary record, [figures.py](vos/figures.py) how a derived figure is spelled and repaired, [trace.py](vos/trace.py) the executors' trace dialects, [jsonc.py](vos/jsonc.py) the model's configuration dialect with [config.py](vos/config.py) the one decoder over it, [coread.py](vos/coread.py) the pairing between a register entry and the prose it cites, [provenance.py](vos/provenance.py) the synthesis record binding each claimed absence to a build, [pins.py](vos/pins.py) the licence record's table of upstream pins and the shape a restatement of one takes, [fieldbindings.py](vos/fieldbindings.py) the field-bindings table the bindings group and [run.py blast](vos/cli/blast.py) both read, [env.py](vos/env.py) the build environment, [report.py](vos/report.py) the one verdict line every check prints, and [seeded.py](vos/seeded.py) the verdicts a mutation run reports, the exit code they imply and the journal a run that does not finish leaves behind, shared by every loop that seeds a defect so that five accountings cannot drift into five measurements. One more is the *model's own* and is the newest: [sailbundle.py](vos/sailbundle.py) reads the bundle Sail emits about the model it typechecked, every definition indexed by the name the model gives it, and it is the owner the four parses below used to each write a regex for. Three sit on top of it and are read together: [sailexpr.py](vos/sailexpr.py) is the model's own expressions read as expressions rather than matched as text, [encdec.py](vos/encdec.py) joins each `encdec` clause to the `assembly` clause that names it and hands back every form the model spells with the bits it spells it at, and [freezeschema.py](vos/freezeschema.py) owns the freeze contract's §4 record shapes so that the producer writing a stream and the analyzer reading it cannot be two statements of one schema. Four read the *model*, which the document corpus excludes by name: [geometry.py](vos/geometry.py) the welded block size, [capformat.py](vos/capformat.py) the frozen capability format's widths and both packings of it, [coreclass.py](vos/coreclass.py) the core-class table and the extension registry, and [decode.py](vos/decode.py) the assembly clauses the model spells its mnemonics with. **What each of the four takes from the bundle is a *definition* and what it still takes from a file is everything else**, which is the line the emitter itself draws: a `type`, a `let`, a `mapping` or a `function` is indexed by name, so a rename is a lookup that misses instead of a pattern that quietly matches nothing, while a comment, a configuration key, an `assert` inside a test body and a SystemVerilog `localparam` are not definitions at all and keep the patterns that read the artifacts writing them. `--doc-format identity` drops unanchored comments, so a regex whose fact the bundle does not carry is kept rather than deleted. Two of the four read outside the model as well as inside it, and by path in both directions: geometry.py takes the block size the authored capability package writes, and capformat.py takes every site that restates a format width, in `rtl/` and in four documents the corpus does carry. The checks themselves live in [vos/checks/](vos/checks/), one module per rule group, each carrying its group's reasoning beside its code. The `counts` group is the one that outgrew that: [counts.py](vos/checks/counts.py) holds its claim table and the run, and its families sit in the `counts_*.py` modules beside it, one per artifact its rules read. The group is still one heading, one entry in `GROUPS`, and one column of [check-rules.md](check-rules.md), because a rule is registered by its id and its group and never by the file carrying it.

Those four and K-63's citation scan are where the checker reaches past its own corpus, and the reach is declared rather than habitual. It is a good deal narrower than it was: what is left under `model/` is the two comments capformat.py reads, the configurations, the harness assert, the requirement citations, and the three platform files K-94 pairs against each other, the definitions having moved to the bundle. That last reach is the one that is a *pairing* rather than a value: what it takes from each of the three is which call the file makes about a window, and no bundle entry carries that, a call inside a body being what the definition index deliberately does not hold. `model/` is excluded from the document corpus by name, and [run.py selftest](vos/cli/selftest.py) stands the whole tree up as empty files to save copying what no rule opens, so a model path a rule reads has to be admitted by one of two declarations in [corpus.py](vos/corpus.py) or it passes on the host and fails every sandbox's baseline.

**The two declarations are narrow for opposite reasons and are deliberately not one list.** `MODEL_FACTS` names thirteen files by path: it is the *value* window, and a rule reading a number out of the model should name the file it reads, so adding one is a decision somebody makes. `is_model_citation_path` admits by kind instead, because the rule behind it holds a construct that occurs wherever the model argues from the register, and a window sized for the other purpose left it reporting `ok` about a quarter of its subject. Merging them would make the audited list quietly mean two things.

Five are the generators' and none of them holds a question: [run.py oracle](vos/oracle.py) parses a spec and emits the Sail harness a domain description implies, [sailrig.py](vos/sailrig.py) compiles a Sail source set with a harness and runs it, which is the rig M2.1 and R1a each built inside one item, [mutate.py](vos/mutate.py) walks a Sail or Gallina source and produces the mutant population, [proofs.py](vos/proofs.py) reads what a Rocq source Requires and orders a directory by it, and [gallina.py](vos/gallina.py) stages a scratch copy of the proofs, compiles it, and reads back what a harness printed. What decides is the spec, the operator table, and the oracle a run points them at.

One is a compiler rather than a generator, and the difference is which way the artifact is held. [run.py ring](vos/cli/ring.py) emits [proofs/RingContract.v](../proofs/RingContract.v) from two owners, [the ring declaration](../interfaces/ring-reference.json) and the register's own entry lines, and K-89 holds the tracked file against what it writes; where the generators above produce evidence a run consumes and throws away, this produces a tracked artifact, so the rule is the point and the emitter is what gives it something to say. It runs on the host because its inputs are a JSON file and the register parse the checker already makes, which is why its rule can re-run the generator where K-88's cannot.

Five more modules are the differential corpus's, and they are named for what they are rather than for where they sit: [dialect.py](vos/dialect.py) is one row per mnemonic the curated model decodes, [asm.py](vos/asm.py) the parser and layout over it, [image.py](vos/image.py) the ELF the emulator loads, [compose.py](vos/compose.py) the packer that turns an assembled image into the link map and per-site table the freeze's §4 joins, and [differential.py](vos/differential.py) the corpus manifest. `dialect.py` is the one of them that holds no table of its own any more: [dialectgen.py](vos/dialectgen.py) writes it out of the bundle, which is the one decision in that pair and states it, and `dialect.py` loads what it wrote. The one name that has to be read carefully is `corpus`: [vos/corpus.py](vos/corpus.py) reads the *documents* this repository checks, and [vos/differential.py](vos/differential.py) reads the *programs* the model runs. They share a word and nothing else.

Two more are the RVFI-DII rig's and sit beside them for the same reason: [rvfi.py](vos/rvfi.py) is the wire format TestRIG defines and the projection from one of its packets onto the commit trace's records, and [vengine.py](vos/vengine.py) is the stream generator, the socket, the seeded defects and the shrinker. Neither decides anything about behaviour: what a divergence *is* stays [trace.py](vos/trace.py)'s, so the rig and the corpus adjudicate through one function rather than two.

[check-rules.md](check-rules.md) is the checker's registry: one row per rule, what passing means, and on what ground. It is the reviewable account of the tool's reach, and the checker holds it against the code in both directions on every run.

## Running them

From anywhere, and from either lane. Every tool finds the repository root from its own
location rather than from the working directory, and `run.py` sends a guest command
into WSL itself, so there is neither a wrong directory nor a wrong lane to be in.

```console
$ python tools/run.py help                       # every command, and the lane it runs in
$ python tools/run.py                            # the three host gates, in one run
$ python tools/run.py --fix                      # the repair first, then the other two
$ python tools/run.py --tests                    # and the tools' own tests beside them
$ python tools/check.py                          # the daily check, at the path the register cites
$ python tools/run.py check --fix                # and rewrite what is arithmetic
$ python tools/run.py selftest                   # every rule against its own mutant
$ python tools/run.py typecheck                  # the tools against their own discipline
$ python tools/run.py test                       # the tools against their own tests
$ python tools/run.py blast --field spatial_safety
$ python tools/quarantine/gate.py                # the deferred instruments, off the wave
$ python tools/run.py coread                     # the pairs owed a reading
$ python tools/run.py coread --show R-15-073c    # one pair, side against side
$ python tools/run.py coread --show --all        # every pending pair, in one read
$ python tools/run.py coread --where R-15-073c   # both sides as file:line sites
$ python tools/run.py coread --bless R-15-073c   # the reading recorded
$ python tools/run.py view                       # the two documents woven, for reading
$ python tools/run.py rtl provenance             # the absences, and what binds each
$ python tools/run.py rtl filelist               # the curated arm's file list, and its substitutions
$ python tools/run.py testrig protocol           # the RVFI-DII wire, against the commit trace
$ python tools/run.py oracle list                # the oracle specs, and how large each is
$ python tools/run.py oracle emit --spec keccak  # the Sail harness one spec implies
$ python tools/run.py seed list --file model/model/core/cap_common.sail
$ python tools/run.py ring emit                  # the ring contract's generated artifact
$ python tools/run.py ring check                 # and the tracked one held against it
```

The rest need the toolchain, so asked for on the host they are re-launched in the
guest and say so. Inside the guest they are `python3 tools/run.py <command>` and
nothing else changes.

```console
$ python tools/run.py provision                  # is this machine the lane, and what is missing
$ python tools/run.py provision --apply          # and install what this tree states a command for
$ python tools/run.py provision --only gate      # the rows the three host gates alone want
$ python tools/run.py evidence                   # the whole exit-evidence sweep, one block
$ python tools/run.py evidence --no-build        # and without rebuilding first
$ python tools/run.py model typecheck
$ python tools/run.py model bundle               # regenerate the model's own bundle
$ python tools/run.py model bundle --check       # and hold the tracked one against it
$ python tools/run.py model lane                 # where this checkout builds
$ python tools/run.py model build --background
$ python tools/run.py model wait                 # and its verdict when it lands
$ python tools/run.py model oracle
$ python tools/run.py model corpus
$ python tools/run.py model corpus --refresh
$ python tools/run.py model devicetree
$ python tools/run.py model reference
$ python tools/run.py model trace-diff --corpus --floor 67
$ python tools/run.py rtl lint                   # the authored RTL, alone
$ python tools/run.py rtl vectors                # the model's own answers, as text
$ python tools/run.py rtl crosscheck             # and the RTL reproducing them
$ python tools/run.py rtl elaborate --background
$ python tools/run.py rtl wait                   # and the structures it removed
$ python tools/run.py testrig handshake          # the emulator, over RVFI-DII
$ python tools/run.py testrig run --seeds 100 --defect none
$ python tools/run.py testrig run --defect tag-dropped --shrink
$ python tools/run.py testrig bridge             # both dialects, one run
$ python tools/run.py oracle vectors --spec capformat
$ python tools/run.py quickchick check           # and what the install costs
$ python tools/run.py quickchick vectors         # the Gallina front's answers
$ python tools/run.py seed coq --sample 20
$ python tools/run.py seed sail --spec keccak --sample 14
$ python tools/run.py proofs
```

There is no `-d` on the `wsl` invocation `run.py` makes, because `Ubuntu` is WSL's default and the default is what every guest command wants. The name is plain `Ubuntu` and the release is 26.04; it is not the only distribution registered on this machine, and nothing in the tools reads the distribution's name, so the only thing holding this together is that default. `wsl --install` sets the newly installed distribution as the default, so installing another one is the single action that quietly redirects every guest command. `wsl -l -v` says which one holds the default today and `wsl -s Ubuntu` puts it back.

The two lanes spell the interpreter differently, and that is not an oversight. On the host `python3` is worse than absent: the python.org installer ships `python.exe` and `pythonw.exe` and no third spelling, and what answers to `python3` is Windows' own app execution alias, a stub that resolves, prints *Python was not found*, and exits 9009. A tool invoked through it fails as though the tool were broken. So `python` is the name, with `py -3.14` available when several versions are installed. Inside the guest the reverse holds. Ubuntu ships `python3` and no bare `python` at all; this distribution answers to both only because `python-is-python3` is installed on it, and [PEP 394](https://peps.python.org/pep-0394/) still names `python3` as the one spelling a script may assume. So the shebangs stay `#!/usr/bin/env python3` and so does every WSL command written down here, because both have to work on a stock 26.04 that has never had that metapackage. Treating `python` as portable is the one shortcut this rule exists to refuse.

`run.py model build` writes its whole run to a log and prints only where the log is, because a fifteen-minute build is started and left. The last line it writes is `ALL_DONE`, so a caller waits on a marker instead of guessing at a sleep.

`run.py test` leaves the cases marked slow to `--slow`, so the default run answers in seconds.

`trace-diff` bounds each executor run with `--timeout`, so an emulator that hangs without retiring instructions becomes a SHORT finding instead of a command that never returns.

## One toolchain, several checkouts

There is one WSL toolchain and there are as many checkouts as there are git worktrees, so the build trees have to be told apart. Each checkout gets a **lane**, and `run.py model lane` prints which one this is, where it builds, and whether anything is building there right now.

The lane is derived from the checkout rather than declared: a linked worktree's `.git` is a *file* naming its administrative directory under the primary checkout's `.git/worktrees/`, and the lane is git's own name for the worktree, which is unique within the repository by construction. The primary worktree has no lane and keeps the paths it always had; a linked one builds under `/root/build/lane-<name>/`, which is one directory holding the whole of what that lane knows, so a lane is retired by deleting it. The one tree every lane shares is the M0.4 oracle's, because it is stock upstream at a pinned commit and none of this repository's curation reaches it.

**Three things collide when two checkouts share one tree, and only one of them is loud.** cmake refuses outright to point an existing cache at a second source directory, so the second lane's build fails at `configure` with an error that names cmake rather than the collision. A build opens its log with `w`, so the second lane truncates the first's while the first is still writing into it. And every loop downstream of a build reads the simulator back out of the build tree, `sweep`, `corpus`, `trace-diff`, `devicetree` and `reference` all of them, and none can tell whose model generated it: that one is silent, and it is the reason lanes exist.

A build **holds its lane** for exactly as long as it runs, so a second build over a live one is refused and named rather than merged into it. The lock is `flock` rather than a pidfile, so a killed build leaves nothing to break, and `run.py model build --background` hands the lock to the run it detaches rather than dropping it. `run.py model wait` blocks on that lock and then reports the log's verdict: the lock is released by the kernel whether the build finished or died, so a wait ends either way, where a wait on the marker alone would hang on the build that never wrote one.

A build is not the only holder of state, and every holder refuses a concurrent run by naming the one that holds it. `emit` takes the same lock as `build`, because both drive the one cmake tree; `typecheck` holds a lock beside its lane's SMT memo cache, which Sail rewrites whole at exit; and `oracle` holds the one tree every lane shares. `corpus` writes its images into the lane's own directory, so two lanes' runs cannot land one ELF path.

A lane standing up for the first time is seeded from the primary worktree's tree rather than built cold, which is what makes a lane cheap enough to be worth having. What is copied is the downloaded riscv-tests and the two Sail SMT memo caches a lane keeps, the build tree's and the typecheck loop's, and a cache is **copied and never shared**: see `vos/cli/model.py`'s `_seed_smt_cache` for what two writers of one memo cache do to each other. Every command that can stand a tree up seeds it before it configures one, `build`, `emit` and `bundle`, so which command a lane is opened with does not decide what that lane pays.

## The lane as a fact list, and what no provisioner reaches

[run.py provision](vos/cli/provision.py) is that machine written down. The guest is a particular thing, four opam switches, a pinned solver ahead of the distribution's, two pinned checkers, an interpreter floor and a handful of distribution packages. The tool is one table: a row per fact, each naming the loop that wants it, the artifact that owns it, a probe that reports what is actually there, and, where this tree states one, the command that would put it there. **Every version and switch name in it is imported from the module that fixes it**, so the table is rows and not a second copy of the pins; the one figure written as a literal is the interpreter floor, because a TOML setting is not importable, and K-75 holds that restatement like the others. The count of switches in this sentence is not a copy either: K-24 computes it, and every other figure any document states about that table, over `FACTS` itself.

It is native rather than containerized, and that is what makes it architecture-agnostic: the prover's published image is amd64-only, an opam build from source is not, and the pinned solver arrives as a wheel built for both. **A row installs only what an artifact here states as a command.** Three routes have owners this file cannot import as an argument vector, uv's own installation, the creation of an opam root, and the CertiRocq oracle switch whose recipe is prose in [wasm-oracle/README.md](wasm-oracle/README.md), and inventing a command for one of them would be exactly the unowned derived fact the working rules refuse. Two of the three are rows and the third is a route no row probes; two further rows plan nothing for reasons of their own, the interpreter floor being the interpreter taking the probe and the cache invariant's repair being to give a lane a copy rather than to delete a warm cache.

**What it does not reach it prints rather than absorbs.** Two settings decide how this lane behaves and neither is in this tree: WSL2's memory reclamation, which lives in a per-user file global to every distribution, and whether a person edits from the host or from inside the guest. Both are printed at the end of a run as not reached and neither is counted into the verdict, which is the same boundary [vos/env.py](vos/env.py) draws around the idle timer.

## The three generators, and what each answers

Validation here is generated rather than authored wherever an oracle exists, and until
these landed the technique had been proved twice and used nowhere else: M2.1 emitted
21,546 vectors from the model itself and R1a emitted 658,659 over thirteen kinds,
killing twelve seeded defects on between 4 and 61,579 lines. Both rigs were built
inside one item and thrown away. These three are the standing instruments, and each
answers one of the two findings that say why generation pays.

| Generator | The finding it answers | What it does |
| --- | --- | --- |
| [run.py oracle](vos/cli/oracle.py) | **M0.12**: its corpus found an encoding defect the `$[test]` harness structurally cannot, a `$[test]` calling `execute` on an already-decoded instruction and so never seeing a mis-encoded word | A spec names model sources and a domain; the harness is emitted, compiled against them, and run, and what it reaches is decided by the domain rather than by what a property happens to be about |
| [run.py seed](vos/cli/seed.py) | **M0.8d**: the property that named a defect was written before the vectors and never ran, the harness running alphabetically so the symptom aborted the executable ahead of the cause | Mutation operators walked over a Sail or Gallina source, each mutant pointed at an oracle that must notice; a written property inherits the blind spots of the choice to write it and a generated mutant is not chosen at all |
| [run.py quickchick](vos/cli/quickchick.py) | **M0.8d**, one language over: both defects its known-answer vectors found were transcriptions no structural property was written about | The Gallina front's inputs, which the Wasm oracle has never had any generator for: an enumerative half in the oracle's own switch, and a randomized half under QuickChick 2.2.0 in a switch of its own, with automatic counterexample shrinking |

Three verdicts and never two, wherever a mutant is run. **Stillborn** is a mutant that
did not compile, and nothing was decided about the oracle because the oracle never ran.
**Killed** is one that compiled and moved the oracle's answer. **Survived** is one that
compiled and did not, and it is the finding: the oracle does not reach that site.
Counting stillborn mutants as kills is the standard way a mutation score is inflated,
so a run scores over the live population and reports the three apart.

**Those verdicts are [seeded.py](vos/seeded.py)'s and the oracle is the loop's**, which
is what makes the selftest below a fourth oracle over this vocabulary rather than a
fourth generator. Its population is authored: the subject is a registry, where a rule
and its mutant are two halves of one claim, and there is no source to walk. So its
third verdict is **unseeded** rather than stillborn, and the two are counted apart for
the reason the other pair are. A stillborn mutant is a fact about the subject, and it
decides nothing; an unseeded one is a fact about the *case*, whose seed no longer
applies to a document that moved under it, and it is a finding, because a case that has
stopped applying reports its rule live for as long as nobody looks.

`seed`'s oracles are separate subcommands because they are three prices, not three
kinds: a Gallina mutant costs a prover run, a Sail mutant costs a compile of the spec's
own handful of model files, and a `$[test]` mutant costs a re-emission and a recompile
of the model's one large translation unit. **`run.py seed properties` is the only loop here
that writes into the checkout**, `model/` being where cmake is pointed; it refuses to
start over an edit, the write is byte-for-byte reversible, the restore is verified
before the next mutant is written, and the lane's build tree is rebuilt from the
restored source before the run reports. **Nothing else may read the checkout while it
runs.** For the length of one mutant the tree on disk is wrong, so `git add` stages a
defect, `check.py` reports a capability format that disagrees with itself, and
`run.py selftest` copies a mutated tree into the template every sandbox links
against. The run says so on its first line.

## Checking the tools themselves

The documents are checked against each other by [check.py](check.py), and the checker is
checked against its own mutants by [run.py selftest](vos/cli/selftest.py). Neither of
them reads a line of Python as Python, so without a gate of their own the tools are the
one artifact here with no proof, no model, and no reader but their author.
[run.py typecheck](vos/cli/typecheck.py) is that gate for the Python's discipline, and it runs two
checkers because one cannot do the whole job; what a type cannot decide, the behavior, is
[run.py test](vos/cli/test.py)'s to hold.

Three of those four decide about the tree as it stands, and they contend for nothing:
all three only read the checkout, and the two small ones fit inside the slack of the
large one. So [a bare `run.py`](run.py) runs them as one command and one exit code, each
member's own report printed whole under its own heading in the order the tool declares
rather than the order the three finished in. What the wave buys in wall time is that the
two small members fit inside the selftest's slack rather than adding their own, and
**no figure is quoted for it here**: a median is a property of the checker it was taken
at, the rule count and the mutant population both move on every rule landed, and the
only timings in this repository with a revision beside them are the ones
[the plan](../docs/implementation-checklist.md)'s I8 recorded at its own gate. The saving is the smaller half of the point
and the single verdict is the larger.

**The wave's cost is the selftest's, multiplied**, and what multiplies it is a host row
of the generated table: a sandbox runs the checker whole, and every host row's generator
runs with it, so a generator that takes a fraction of a second costs that fraction about
a hundred times over. Measured warm on this twelve-core host with one such row, the wave
takes 52 s against the 35.6 s it took with none, and the generator's own run is 0.15 s.
That is a price worth naming twice over: it is what buys K-88 deciding byte identity
outright rather than against the last commit, and it is the number a second host row
would move again. `--fix` is the one exception to the wave
and a correctness one, the repair running alone and to completion before the rest,
because the selftest opens by copying the working tree and a document rewritten
mid-copy seeds a torn sandbox that reports as a baseline failure about nothing.
[run.py test](vos/cli/test.py) is a member only when `--tests` asks for it, and for two
reasons: it decides about the tools rather than about this tree, so a document edit has
no reason to pay for it, and one of its own cases launches the wave as a subprocess to
hold its verdict, which a default that ran the tests would make a recursion rather than
a case.

| Checker | Pin | What it decides |
| --- | --- | --- |
| [ty](https://github.com/astral-sh/ty) | 0.0.75 | Every expression, against the types it can infer, with `--error all` |
| [ruff](https://github.com/astral-sh/ruff) | 0.16.5 | Every function, against whether it is annotated at all, and the correctness rules [ruff.toml](ruff.toml) admits |

The split is not a preference. ty infers rather than demands, so a function with no
annotations contradicts nothing and is invisible to it; ruff's `ANN` group is what makes
coverage a rule. Both are pinned for the reason Rocq and z3 are pinned, and a version
other than the pinned one is a finding rather than a warning.

Both install with `uv tool install ty==0.0.75` and `uv tool install ruff==0.16.5`, one
command each because a uv tool install is one environment holding one pinned tool. That
isolation is the point rather than a side effect: neither checker is a dependency of
anything here, so neither belongs in the environment ty resolves this directory's own
imports against, and the pinned checker stays the same one whichever interpreter runs
[run.py typecheck](vos/cli/typecheck.py). The shims land in uv's tool bin directory, which
[run.py typecheck](vos/cli/typecheck.py) looks in first, ahead of the interpreter's own script
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
against one declared target and not against whichever machine ran the checker. The one
`ty: ignore` in this directory is [vos/config.py](vos/config.py)'s, on a cast where ty
calls the code unsound without it and the cast redundant with it, and it names
`redundant-cast` alone; no import suppression exists here, which leaves every unresolved
import an error without a carve-out to audit.

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
- **An id pattern admits the letter suffix.** Every id family here can take one, because a thing inserted between two others is suffixed rather than renumbered, so `A-\d+` does not merely read imprecisely, it narrows its input silently and in two directions that mask each other: the parse side undercounts, and a claim repaired from that parse is then *written* wrong under `--fix`, which is worse than a copied figure because the rule vouches for it; while on the name side a token under a trailing `(?![\w-])` boundary does not match the suffixed id at all, so a citation of one that does not exist is skipped rather than reported unknown. Audit the parse side and the name side together, since fixing either alone leaves the other blind.
- **An invariant is stated where it is relied on.** A reader entitled to a value because two branches above ruled out the alternatives says so, rather than leaving a `None` to be subscripted at the point the tool is reporting the finding it exists to report.
- **Assertions that guard an artifact are raised, not asserted.** `python -O` deletes an `assert`, and a check standing between a mis-transcribed row and an image the emulator runs anyway has to outlive a flag. `zip` over two sequences that must correspond takes `strict=True` for the same reason: a silent truncation in a tool whose output is evidence is worse than a stopped run.

## Adding a rule to the checker

Three edits, and the tools refuse to let one be forgotten:

1. The check itself, in the [vos/checks/](vos/checks/) module for its group.
2. Its row in [check-rules.md](check-rules.md). The meta group fails on a rule with no row and a row with no rule.
3. Its mutant in [run.py selftest](vos/cli/selftest.py). The selftest fails on a registered rule with no case, and on a case whose mutation no longer applies.

A rule that reads an enumeration owes the floors group a member count too, so that the day its pattern stops matching anything is the day it says so rather than the day it starts passing vacuously. The meta group's own rules are the exception and state why: their sites are declared in code and read fail-closed, so a reading that has emptied reports there rather than one group later.

A **quarantined** rule keeps all three edits and keeps them together, in [quarantine/](quarantine/): the check under [quarantine/checks/](quarantine/checks/), the row in [quarantine/check-rules.md](quarantine/check-rules.md), and the mutant in [quarantine/gate.py](quarantine/gate.py), which holds the three against each other exactly as the meta group and the selftest hold the landing loop's. What decides which of the two places a rule belongs in is not the rule but its subject: an instrument whose decision is deferred is not worth a second of every landing, and [that directory's README](quarantine/README.md) states the condition that brings each one back.

And whatever the edit, `python tools/run.py typecheck` has to be green before it lands, the same way `python tools/check.py` does.
