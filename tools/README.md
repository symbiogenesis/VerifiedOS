# The Tools

*Everything in this directory is Python 3.14. This document says why that is the rule, what each tool does, and the conventions every one of them keeps.*

## One language, and what forced it

The tools run in two places. The documents, the proofs metadata, and the checker run on the **Windows host**, where the repository is edited. The Sail model's build loops run inside **WSL**, where the toolchain lives. Three interpreters are in reach across those two lanes, and only one of them runs in both:

| Interpreter | Windows host | WSL guest |
| --- | --- | --- |
| Python | 3.14.7 | 3.14.7 |
| `pwsh` | present | absent |
| `bash` | the guest's | present |

`bash.exe` does resolve on the host, and it is WSL's launcher rather than a shell of its own: what it starts is the guest's bash, in the guest's filesystem, so writing for it is writing for the WSL lane under another name. There is no host bash to target.

Python is the only one that spans both, so it is the only choice that makes the tools one thing rather than two. It also closes the seam a split would open: a fact parsed on one side of it re-parsed by hand on the other, which is the defect [check.py](check.py) exists to catch, running loose in the tools that catch it.

Nothing a shell offers is out of reach. Raising the OCaml stack the Sail emission needs is `resource.setrlimit` in the parent and inheritance in every child; and where a shell measures a stage badly, `/usr/bin/time` reporting the running maximum resident set over every child so far, `os.wait4` reports the child that was actually asked about.

The floor is **3.14**, shared by the host and guest and enforced by the project constraint and checker targets. The system interpreter need not be replaced: uv can select an installed compatible interpreter for the tools' environment. The entry-point bootstrap accepts Python 3.12 or newer; command modules run only after the project environment is ready.

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
own help. CI uses one read-only invocation, `run.py --check --tests`, in
[.github/workflows/host-gates.yml](../.github/workflows/host-gates.yml), on Windows and Ubuntu
runners at every push and pull request to `main`, over a clone with no submodule
checked out; the guest lane's loops run only by hand, on a machine that holds the
toolchain. CI green is a witness that the host gates passed on that commit and never a
substitute for the guest lane's evidence.

**The lane is the front door's business rather than the caller's.** A `[wsl]` command
asked for on the host is re-launched in the guest and says so, so there is no
`wsl -u root -e python3` to remember and no wrong lane to be in. A guest command has
to *drive* the toolchain to need the hop: `model config-keys`,
`model validate-config`, `model asm`, `model freeze-emit`, `rtl provenance`,
`rtl filelist`, `oracle list`, `oracle emit`, `seed list`, `testrig protocol`,
`placement export`, `placement check`, `placement admit`, `placement search`,
`proofs headers` and `proofs status` use this checkout and answer on either lane.
That is a declaration and not a description, so
[tests/test_lanes.py](tests/test_lanes.py) dispatches every member of it on whichever
lane the suite is running on, and holds every subcommand the table declares against
this page: one the table declares and this page nowhere names sends a reader into the
guest for an answer the host already had. Only that direction is held, and only against
the page rather than against this sentence; a name here the table does not declare is
caught by nothing, which is a residue the findings register carries.

| Command | Lane | What it does |
| --- | --- | --- |
| `gate` | host | Validates shared agent instructions and restores a missing import, then runs the three gates below in parallel. `--check` is read-only; `--fix` also repairs derived artifacts before a fresh validation wave; `--tests` adds behavioral tests. A bare `run.py` selects this workflow. |
| `check` | host | Checks every derived fact against the artifact that owns it. `--fix` rewrites the figures that are arithmetic. It is also [check.py](check.py), the one command that is still a path, because the register, the coverage matrix, the crown jewels, the field bindings and the findings register all cite that path for what it decides. |
| `selftest` | host | Seeds each of the checker's rules a defect it must report, and fails on a rule that says nothing. |
| `typecheck` | host | Holds this directory's own Python to the discipline it holds the documents to. |
| `test` | host | Runs the tools' own behavioral tests, one module per subject under [tests/](tests/). |
| `sync-instructions` | host | Validates AGENTS.md and its CLAUDE.md import; creates a missing import. `--check` only validates; `--migrate` converts identical legacy copies without discarding independent edits. |
| `worktree` | host | Lists registered checkouts, creates a fresh branch at an explicit base under the primary checkout's `.worktrees/`, and verifies assigned worktrees, including host-provisioned locations. `--json` produces handoff data. |
| `coread` | host | Prints a register entry against the prose it was extracted from, and records the reading K-61 asks for. |
| `view` | host | Weaves the specification and the register into one generated reading view, each entry rendered beneath the bookmark that cites it, written outside the corpus and never a source. |
| `blast` | host | Answers what an edit to the apex statement re-opens, before the work starts. |
| `provision` | wsl | The lane this repository builds in, as a table of facts a machine can act on: one row per switch, pin, checker and prerequisite, each naming the loop that wants it, the artifact that owns it, and what a probe actually found. The default reports and changes nothing; `--apply` installs what is absent and re-probes; `--only` narrows to the gate's rows or the toolchain's and says which rows it did not decide about. |
| `model` | wsl | Every loop over the curated Sail model: `typecheck`, `bundle`, `emit`, `build`, `wait`, `lane`, `smt`, `oracle`, `sweep`, `corpus`, `asm`, `freeze-emit`, `trace-diff`, `devicetree`, `reference`, `config-keys`, `validate-config`, `keepalive`. `bundle` regenerates the machine-readable view of the model the host lane reads it through, and `bundle --check` holds the tracked one against what Sail writes now, which is the half of K-88 a host with no Sail cannot take. `smt` runs the capability-helper property suite ([model/model/unit_tests/cap_properties.sail](../model/model/unit_tests/cap_properties.sail), a transcription of the pinned `sail-cheri-riscv-verif` properties at the frozen widths) through Sail's SMT target with one verdict and one time per property, proved, counterexample or undecided, the last being its own verdict and never a pass; the suite sits behind the project file's `smt_properties` variable so that no build's ctest waits on a solver, and every verdict is evidence about the Sail functions rather than R-15-007a's proof. |
| `evidence` | wsl | Builds the model, verifies its receipt, and runs the reference, profile sweep, differential corpus, devicetree and proof gate. Proofs overlap the model consumers in a separate process. Each run writes a JSON execution record with input identities, process results and measurements. `--no-build` requires a current successful build receipt; stale logs cannot supply its test evidence. |
| `rtl` | wsl | The RTL lane: `provenance` parses the synthesis record and `filelist` composes the curated arm's elaboration file list, both on either lane; `lint`, `vectors`, `crosscheck`, `elaborate` and `wait` need the guest. `elaborate` elaborates the imported core at the curated configuration and at a baseline and names every structure the disabling parameters remove, and `wait` reports the verdict of a backgrounded one; `vectors` compiles the model's capability format with a generator that prints what its functions return, and `crosscheck` requires the authored SystemVerilog to reproduce every line. **A curation replaces imported sources as well as re-valuing parameters**, so `rtl.py`'s `SUBSTITUTIONS` declares which authored source stands where the imported manifest names imported ones, that declaration reaches the curated arm alone, and the diff is partitioned rather than signed: a kind the curated arm instantiates and the baseline does not is an introduction where an authored source in its file list declares that module and a finding where none does, and a kind the baseline instantiates and the curated arm does not is the parameters' own only where no replaced source declared it. |
| `oracle` | wsl | The model-as-oracle vector generator, which is that Sail generator with the question taken out of it: a spec names the model sources and the domain, and this emits the harness, compiles it against them, and runs it. `list` and `emit` answer on either lane; `vectors` needs Sail. |
| `seed` | wsl | The seeded-defect generator: mutation operators walked over a Sail or Gallina source, pointed at an oracle that must notice. `list` answers on either lane; `sail`, `coq` and `properties` each need their oracle's toolchain. |
| `ring` | host | The ring contract's generated interface artifact, from its two owners: `emit` writes [proofs/RingContract.v](../proofs/RingContract.v) out of [the ring declaration](../interfaces/ring-reference.json) and the register entries it reads, and `check` re-emits and compares byte for byte, which is what K-89 holds the tracked file to. It runs on the host because both owners are already in this checkout, which is why its rule can re-run the generator where K-88's guest row cannot. |
| `placement` | host / wsl | `export`, `check`, `admit` and `search` read the memory plan on either lane. `consistency` asks Z3 to select a jointly admissible candidate from the existing finite island grid, labels constraints with requirement IDs, and replays witnesses and contradiction cores through the exact predicates. A truncated grid can produce a witness but cannot establish unsatisfiability. The proof status remains with the Gallina artifact. |
| `quickchick` | wsl | The Gallina front's input side, which the Wasm oracle has never had: `vectors` runs the enumerative half in the CertiRocq oracle's own switch, `properties` runs the randomized half under QuickChick in a switch of its own, and `check` says which switch holds what. |
| `testrig` | wsl | The RVFI-DII rig: `protocol` reads the wire format off the codec on either lane; `handshake`, `run` and `bridge` drive the emulator over a socket in the guest. `run` generates a DII stream, adjudicates the emulator against itself under a seeded defect, and shrinks the counterexample; `bridge` holds one run's packets against the commit records the same run wrote. |
| `proofs` | wsl / host | Compiles independent proofs in bounded dependency waves, enumerates compiled constants with Rocq, audits their assumptions and claimed theorem types, and rechecks the compiled modules with `rocqchk`. Missing or unsupported enumeration fails. `proofs status` checks the exported evidence against current source and compiled-file hashes on either lane; guest toolchain identity is recorded there, not re-probed by the host. `proofs headers` checks compact requirement references and fingerprints; `--write` refreshes them and `--show FILE` reads the selected register entries as Markdown. |

Each command is one module of [vos/cli/](vos/cli/), which is what those executables
became: each keeps its docstring, its argparse and its `main(argv)`, less its own
preamble and its own `__main__` block. [vos/cli/\_\_init\_\_.py](vos/cli/__init__.py)
is the table `run.py` reads, and it is the only place a command's name, its module and
its lane are written down.

Six directories are inputs rather than commands. [generated/](generated/) is the one this repository does not author: it holds the model's own machine-readable bundle of itself, emitted by Sail and tracked so that the host lane can read the model without one, the encoder table [`run.py check --fix`](check.py) writes from that bundle and the shipped configurations, and the memory plan's placement problem the same repair writes from [the plan's proof file](../proofs/MemoryPlan.v). K-88 holds each against what its generator writes, and they are decided differently: the table's and the plan export's generators run at this gate, so their bytes are compared outright, where the bundle's needs Sail and is held against the git index and the owner record the artifact itself carries until `run.py model bundle --check` runs in the guest. It is under `tools/` rather than under `model/` because `model/` is `-text` in [.gitattributes](../.gitattributes) and vendored byte-identically from its upstream pin, and a generated artifact there would break both properties at once. [oracle-specs/](oracle-specs/) is
one JSON file per oracle: the sources to compile, and per line kind the parameters,
the domain that walks them, the Sail that calls the model, and what to print.
[cheri-equiv/](cheri-equiv/) is the cross-check's two halves, a Sail generator that
calls the model's capability functions and a SystemVerilog testbench that replays what
it printed; neither is a translation of the other and the only thing they share is the
line format each states in its own header. [quickchick/](quickchick/) is the Gallina
harnesses. [wasm-oracle/](wasm-oracle/) is the container the CertiCoq → Wasm oracle is
built and run in, and [its own README](wasm-oracle/README.md) states what it pins.
[bedrock2-lowering/](bedrock2-lowering/) is the Gallina-to-C lowering loop Q2a stood up
in the Rupicola switch M1.6 created: the sources it derives, a hand-run driver, and the
digest of what it emits, with [its own README](bedrock2-lowering/README.md) stating the
recipe and the boundary audit. No `run.py` command reaches it, on the same ground as the
Wasm oracle.

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

The shared machinery is [vos/](vos/), and it holds parses, never decisions: [corpus.py](vos/corpus.py) reads the documents, [register.py](vos/register.py) the register and the tables other documents count, [apex.py](vos/apex.py) the statement's Vocabulary record, [figures.py](vos/figures.py) how a derived figure is spelled and repaired, [trace.py](vos/trace.py) the executors' trace dialects, [jsonc.py](vos/jsonc.py) the model's configuration dialect with [config.py](vos/config.py) the one decoder over it, [coread.py](vos/coread.py) the pairing between a register entry and the prose it cites, [proofcites.py](vos/proofcites.py) what each shipped proof artifact cites and what it defines, read lexically so that the host wave decides it with no prover in reach, and named for the citation half rather than for the evidence it is because `vos/<name>.py` beside `vos/cli/<name>.py` is this directory's word for *the machinery behind that command*, [provenance.py](vos/provenance.py) the synthesis record binding each claimed absence to a build, [pins.py](vos/pins.py) the licence record's table of upstream pins and the shape a restatement of one takes, [fieldbindings.py](vos/fieldbindings.py) the field-bindings table the bindings group and [run.py blast](vos/cli/blast.py) both read, [env.py](vos/env.py) the build environment, [report.py](vos/report.py) the one verdict line every check prints, and [seeded.py](vos/seeded.py) the verdicts a mutation run reports, the exit code they imply and the journal a run that does not finish leaves behind, shared by every loop that seeds a defect so that five accountings cannot drift into five measurements. One more is the *model's own* and is the newest: [sailbundle.py](vos/sailbundle.py) reads the bundle Sail emits about the model it typechecked, every definition indexed by the name the model gives it, and it is the owner the four parses below used to each write a regex for. Three sit on top of it and are read together: [sailexpr.py](vos/sailexpr.py) is the model's own expressions read as expressions rather than matched as text, [encdec.py](vos/encdec.py) joins each `encdec` clause to the `assembly` clause that names it and hands back every form the model spells with the bits it spells it at, and [freezeschema.py](vos/freezeschema.py) owns the freeze contract's §4 record shapes so that the producer writing a stream and the analyzer reading it cannot be two statements of one schema. Four read the *model*, which the document corpus excludes by name: [geometry.py](vos/geometry.py) the welded block size, [capformat.py](vos/capformat.py) the frozen capability format's widths and both packings of it, [coreclass.py](vos/coreclass.py) the core-class table and the extension registry, and [decode.py](vos/decode.py) the assembly clauses the model spells its mnemonics with. **What each of the four takes from the bundle is a *definition* and what it still takes from a file is everything else**, which is the line the emitter itself draws: a `type`, a `let`, a `mapping` or a `function` is indexed by name, so a rename is a lookup that misses instead of a pattern that quietly matches nothing, while a comment, a configuration key, an `assert` inside a test body and a SystemVerilog `localparam` are not definitions at all and keep the patterns that read the artifacts writing them. `--doc-format identity` drops unanchored comments, so a regex whose fact the bundle does not carry is kept rather than deleted. Two of the four read outside the model as well as inside it, and by path in both directions: geometry.py takes the block size the authored capability package writes, and capformat.py takes every site that restates a format width, in `rtl/` and in five documents the corpus does carry. The checks themselves live in [vos/checks/](vos/checks/), one module per rule group, each carrying its group's reasoning beside its code. The `counts` group is the one that outgrew that: [counts.py](vos/checks/counts.py) holds its claim table and the run, and its families sit in the `counts_*.py` modules beside it, one per artifact its rules read. The group is still one heading, one entry in `GROUPS`, and one column of [check-rules.md](check-rules.md), because a rule is registered by its id and its group and never by the file carrying it.

Those four and K-63's citation scan are where the checker reaches past its own corpus, and the reach is declared rather than habitual. It is a good deal narrower than it was: what is left under `model/` is the two comments capformat.py reads, the configurations, the harness assert, the requirement citations, and the three platform files K-94 pairs against each other, the definitions having moved to the bundle. That last reach is the one that is a *pairing* rather than a value: what it takes from each of the three is which call the file makes about a window, and no bundle entry carries that, a call inside a body being what the definition index deliberately does not hold. `model/` is excluded from the document corpus by name, and [run.py selftest](vos/cli/selftest.py) stands the whole tree up as empty files to save copying what no rule opens, so a model path a rule reads has to be admitted by one of two declarations in [corpus.py](vos/corpus.py) or it passes on the host and fails every sandbox's baseline.

**The two declarations are narrow for opposite reasons and are deliberately not one list.** `MODEL_FACTS` names thirteen files by path: it is the *value* window, and a rule reading a number out of the model should name the file it reads, so adding one is a decision somebody makes. `is_model_citation_path` admits by kind instead, because the rule behind it holds a construct that occurs wherever the model argues from the register, and a window sized for the other purpose left it reporting `ok` about a quarter of its subject. Merging them would make the audited list quietly mean two things.

Five are the generators' and none of them holds a question: [run.py oracle](vos/oracle.py) parses a spec and emits the Sail harness a domain description implies, [sailrig.py](vos/sailrig.py) compiles a Sail source set with a harness and runs it, which is the rig M2.1 and R1a each built inside one item, [mutate.py](vos/mutate.py) walks a Sail or Gallina source and produces the mutant population, [proofs.py](vos/proofs.py) reads what a Rocq source Requires and orders a directory by it, and [gallina.py](vos/gallina.py) stages a scratch copy of the proofs, compiles it, and reads back what a harness printed. What decides is the spec, the operator table, and the oracle a run points them at.

Three are compilers rather than generators, and the difference is which way the artifact is held: where the generators above produce evidence a run consumes and throws away, these produce tracked artifacts, so the rule is the point and the emitter is what gives it something to say. [run.py ring](vos/cli/ring.py) emits [proofs/RingContract.v](../proofs/RingContract.v) from two owners, [the ring declaration](../interfaces/ring-reference.json) and the register's own entry lines, and K-89 holds the tracked file against what it writes. It runs on the host because its inputs are a JSON file and the register parse the checker already makes, which is why its rule can re-run the generator where K-88's cannot. K-99 reads the same emission for the other claim about it: the emitter states the wire encoding as well, and what it takes that from is [the typed IDL profile](../docs/languages/idl-profile.md)'s §4, which is not an owner it reads, so agreeing with the declaration says nothing about agreeing with the rows. [socmap.py](vos/socmap.py) emits [rtl/vos_soc_map_pkg.sv](../rtl/vos_soc_map_pkg.sv), the SoC address map in the language the RTL is written in, from the frozen profile's composition; that one is held by **K-88** rather than by a rule of its own, its row of the generated table being a host row whose generator the checker runs. It is worth reading beside the ring's for the one thing it does differently: its subject is an enumeration rather than a fixed set of fields, so it finds the windows it emits by shape rather than by name and a window a composition gains arrives in the package with no edit to the emitter. [memplan.py](vos/memplan.py) is the third, and its owner is a proof file rather than a configuration: it reads the memory plan's lists, literals and register placement out of [proofs/MemoryPlan.v](../proofs/MemoryPlan.v) and emits [tools/generated/memory-plan.json](generated/memory-plan.json), held by **K-88** the same way, and beside the emitter it carries the exact port of that file's checks [run.py placement](vos/cli/placement.py) searches with, which the tests hold to the file's own refutation variants.

Five more modules are the differential corpus's, and they are named for what they are rather than for where they sit: [dialect.py](vos/dialect.py) is one row per mnemonic the curated model decodes, [asm.py](vos/asm.py) the parser and layout over it, [image.py](vos/image.py) the ELF the emulator loads, [compose.py](vos/compose.py) the packer that turns an assembled image into the link map and per-site table the freeze's §4 joins, and [differential.py](vos/differential.py) the corpus manifest. `dialect.py` is the one of them that holds no table of its own any more: [dialectgen.py](vos/dialectgen.py) writes it out of the bundle, which is the one decision in that pair and states it, and `dialect.py` loads what it wrote. The one name that has to be read carefully is `corpus`: [vos/corpus.py](vos/corpus.py) reads the *documents* this repository checks, and [vos/differential.py](vos/differential.py) reads the *programs* the model runs. They share a word and nothing else.

Two more are the RVFI-DII rig's and sit beside them for the same reason: [rvfi.py](vos/rvfi.py) is the wire format TestRIG defines and the projection from one of its packets onto the commit trace's records, and [vengine.py](vos/vengine.py) is the stream generator, the socket, the seeded defects and the shrinker. Neither decides anything about behaviour: what a divergence *is* stays [trace.py](vos/trace.py)'s, so the rig and the corpus adjudicate through one function rather than two.

[check-rules.md](check-rules.md) is the checker's registry: one row per rule, what passing means, and on what ground. It is the reviewable account of the tool's reach, and the checker holds it against the code in both directions on every run.

## Running them

Install Python at the floor above and [uv](https://docs.astral.sh/uv/getting-started/installation/)
at the version declared by [pyproject.toml](pyproject.toml)'s
`tool.uv.required-version`. Both must be available in each OS where commands run;
Windows installations do not supply WSL's prerequisites. No activation, global
package installation, or separate checker installation is needed.

When a compatible Python is absent, install it explicitly with your platform's
installer or `uv python install --no-config 3.14`. That one command bypasses project
configuration for the manual install. The project keeps `python-downloads = "never"`,
and normal commands never download Python. Ensure uv is on the non-interactive PATH
used by WSL as well as your interactive shell.

The first command synchronizes [uv.lock](uv.lock), then runs inside the managed
environment. Windows uses `out/venv-win32`; Linux, including WSL and CI, uses
`out/venv-linux`. Each checkout has its own environments. Only the manifest,
lockfile, and each OS's uv download cache are shared, never Windows and Linux
executables. The runner selects an installed interpreter matching the project.

Every top-level invocation checks the locked resolution; stale or missing lockfiles
stop before dispatch rather than being regenerated. Child commands inherit the
settled environment. Read-only gates may populate ignored environments and caches,
but do not modify tracked dependencies or documents. [check.py](check.py)'s direct
entry point uses the same bootstrap.

From anywhere, and from either lane. Every tool finds the repository root from its own
location rather than from the working directory, and `run.py` sends a guest command
into WSL itself, so there is neither a wrong directory nor a wrong lane to be in.

```console
$ python tools/run.py help                       # every command, and the lane it runs in
$ python tools/run.py --check                    # integrator: the three host gates, read-only
$ python tools/run.py --fix                      # integrator: repair, then all three gates afresh
$ python tools/run.py --check --tests            # final wave including the tools' behavioral tests
$ python tools/check.py                          # checker feedback after a coherent document batch
$ python tools/run.py check --fix                # integrator: arithmetic repair alone
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
$ python tools/run.py rtl install                # verified release in the project toolchain prefix
$ python tools/run.py rtl lint                   # this repository's own RTL, alone
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
$ python tools/run.py quickchick freeze          # the freeze's model, stated twice
$ python tools/run.py seed coq --sample 20
$ python tools/run.py seed sail --spec keccak --sample 14
$ python tools/run.py proofs
```

There is no `-d` on the `wsl` invocation `run.py` makes: it uses WSL's default distribution, expected to be the Ubuntu installation carrying the toolchain. No release number or distribution name is enforced by the tools. `wsl --install` can change that default, so check `wsl -l -v` after installing another distribution; `wsl -s Ubuntu` selects Ubuntu again.

The entry-point spellings differ by OS. Use `python` on Windows, or `py -3.14` when selecting among installed versions; the `python3` app-execution alias may not launch an interpreter. Use `python3` in Ubuntu, where a bare `python` is not guaranteed. [PEP 394](https://peps.python.org/pep-0394/) gives the guest spelling, which the shebangs and WSL launcher retain. After bootstrap, both lanes use the compatible interpreter in their managed environment.

`run.py model build` writes its whole run to a log and prints only where the log is, because a fifteen-minute build is started and left. The last line it writes is `ALL_DONE`, so a caller waits on a marker instead of guessing at a sleep.

`run.py test` leaves the cases marked slow to `--slow`. Concurrent test modules run
in separate spawned processes, isolating their environment overrides, patches and
redirected output. Workers may run later modules, so tests still restore temporary
state. Cases within a module remain sequential, and reports
retain module order, including captured output when a module fails.
`test --jobs N` limits concurrent workers; the default uses
available CPUs up to eight. Imports happen inside each worker, so test callbacks
may be closures without requiring serialization.

`trace-diff` bounds each executor run with `--timeout`, so an emulator that hangs without retiring instructions becomes a SHORT finding instead of a command that never returns.

`model corpus --refresh` rewrites the manifest's own record counts and trace digests, which makes it the one flag that can turn a regression into the baseline: it is for the run where the manifest is what changed, and never for a red run.

`model typecheck` runs `sail --just-check` with its output inherited, and Sail prints nothing on success, so exit 0 with nothing printed is the pass and not a run that failed to start.

`tools/co-read.json`, the ledger `coread --bless` writes, is one line per requirement id, so two lanes blessing disjoint ids merge cleanly and two touching one id conflict loudly, which is the right outcome. A conflict there is resolved by hunk and never by taking a side whole, which discards every blessing the other lane recorded and re-opens the pairs it read; the merged text of a conflicted pair then wants a fresh `coread --show` and `--bless`.

## One toolchain, several checkouts

There is one WSL toolchain and there are as many checkouts as there are git worktrees, so the build trees have to be told apart. Each checkout gets a **lane**, and `run.py model lane` prints which one this is, where it builds, and whether anything is building there right now.

The lane is derived from the checkout rather than declared: a linked worktree's `.git` is a *file* naming its administrative directory under the primary checkout's `.git/worktrees/`, and the lane is git's own name for the worktree, which is unique within the repository by construction. The primary worktree has no lane and keeps the paths it always had; a linked one builds under `/root/build/lane-<name>/`, which is one directory holding the whole of what that lane knows, so a lane is retired by deleting it. The one tree every lane shares is the M0.4 oracle's, because it is stock upstream at a pinned commit and none of this repository's curation reaches it.

**Three things collide when two checkouts share one tree, and only one of them is loud.** cmake refuses outright to point an existing cache at a second source directory, so the second lane's build fails at `configure` with an error that names cmake rather than the collision. A build opens its log with `w`, so the second lane truncates the first's while the first is still writing into it. And every loop downstream of a build reads the simulator back out of the build tree, `sweep`, `corpus`, `trace-diff`, `devicetree` and `reference` all of them, and none can tell whose model generated it: that one is silent, and it is the reason lanes exist.

A build **holds its lane** for exactly as long as it runs, so a second build over a live one is refused and named rather than merged into it. The lock is `flock` rather than a pidfile, so a killed build leaves nothing to break, and `run.py model build --background` hands the lock to the run it detaches rather than dropping it. `run.py model wait` blocks on that lock and then reports the log's verdict: the lock is released by the kernel whether the build finished or died, so a wait ends either way, where a wait on the marker alone would hang on the build that never wrote one.

A build is not the only holder of state, and every holder refuses a concurrent run by naming the one that holds it. `emit` takes the same lock as `build`, because both drive the one cmake tree; `typecheck` holds a lock beside its lane's SMT memo cache, which Sail rewrites whole at exit; and `oracle` holds the one tree every lane shares. `corpus` writes its images into the lane's own directory, so two lanes' runs cannot land one ELF path.

A lane standing up for the first time is seeded from the primary worktree's tree rather than built cold, which is what makes a lane cheap enough to be worth having. What is copied is the downloaded riscv-tests and the two Sail SMT memo caches a lane keeps, the build tree's and the typecheck loop's, and a cache is **copied and never shared**: see `vos/cli/model.py`'s `_seed_smt_cache` for what two writers of one memo cache do to each other. Every command that can stand a tree up seeds it before it configures one, `build`, `emit` and `bundle`, so which command a lane is opened with does not decide what that lane pays.

## The lane as a fact list, and what no provisioner reaches

[run.py provision](vos/cli/provision.py) is that machine written down. Its probes cover four opam switches, a pinned solver ahead of the distribution's, two pinned checkers, an interpreter floor and a handful of distribution packages. The tool is one table: a row per fact, each naming the loop that wants it, the artifact that owns it, a probe that reports what is actually there, and, where this tree states one, the command that would put it there. **Versions and switch names come from their owners**; the interpreter floor is an explicit restatement held by K-75. The count of switches in this sentence is not a copy either: K-24 computes it, and every other figure any document states about that table, over `FACTS` itself. [The opam snapshots](opam/README.md) record complete package resolutions, including the lowering experiment's separate switch, which has its own [installation recipe](bedrock2-lowering/README.md).

It is native rather than containerized: the prover and model toolchains are built on the guest. Python and uv are bootstrap prerequisites. The runner synchronizes the locked Python packages before the provisioner probes them, so those rows have no separate install recipes. `--apply` handles only rows with declared commands. Creating an opam root and the CertiRocq oracle switch remains manual; the latter's recipe is in [wasm-oracle/README.md](wasm-oracle/README.md). The interpreter cannot replace itself, and the cache invariant needs separate copies rather than deletion of a warm cache.

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

**A killed population is a result about the statements and never about the
definitions.** Every mutant killed says some theorem moved when a definition did, which
is that the file's theorems constrain the file's own definitions; it says nothing about
whether those definitions are what the register fixes, and an artifact can kill every
mutant, close under the proof gate and still resolve an open register question by fiat
or state a bar no entry carries. Measured on the proof-authoring fan-out, every artifact
that carried such a decision had a fully killed population, so the reader that resolves
each cited entry against the register and asks which sentence closes each literal and
each definition shape is not a second opinion on the score but the only reader asking
that question. Three tells: a numeric literal no entry closes; a definition whose shape
encodes a choice the register leaves open, a queue where the register fixes only
readiness or a total function where it admits a refusal; and a bound shipped as an
equality, which the statements constrain identically under either reading and no grep
finds.

**Those verdicts are [seeded.py](vos/seeded.py)'s and the oracle is the loop's**, which
is what makes the selftest below a fourth oracle over this vocabulary rather than a
fourth generator. Its population is authored: the subject is a registry, where a rule
and its mutant are two halves of one claim, and there is no source to walk. So its
third verdict is **unseeded** rather than stillborn, and the two are counted apart for
the reason the other pair are. A stillborn mutant is a fact about the subject, and it
decides nothing; an unseeded one is a fact about the *case*, whose seed no longer
applies to a document that moved under it, and it is a finding, because a case that has
stopped applying reports its rule live for as long as nobody looks.

**That coverage is counted over rules, so a rule whose subject is a table wants a case
per row and not only per reading.** The run's own coverage line, *every registered rule
carries a case*, stays true the day a table-driven rule gains a row nothing seeds, and a
row nothing seeds reports green
whether or not it decides anything, which is the shape a check that decides nothing takes
here. K-88 is the rule with that shape and it carries four cases for the reason: the
model bundle at its guest reading, the encoder table at its host reading, the SoC
address map at the second host row and the memory plan's export at the third, those last
two repeating a reading and deciding only that their row is live.

`seed`'s oracles are separate subcommands because they are three prices, not three
kinds: a Gallina mutant costs a prover run, a Sail mutant costs a compile of the spec's
own handful of model files, and a `$[test]` mutant costs a re-emission and a recompile
of the model's one large translation unit. **`run.py seed properties` temporarily replaces live model sources**,
`model/` being where cmake is pointed; it refuses to
start over an edit, the write is byte-for-byte reversible, the restore is verified
before the next mutant is written, and the lane's build tree is rebuilt from the
restored source before the run reports. **Nothing else may read the checkout while it
runs.** For the length of one mutant the tree on disk is wrong, so `git add` stages a
defect, `check.py` reports a capability format that disagrees with itself, and
`run.py selftest` copies a mutated tree into the template every sandbox links
against. The run says so on its first line.

## Worktree isolation during fan-out

**Every subagent in a fan-out performs all repository work inside its own dedicated
Git worktree.** This includes implementation, document work, read-only scouting,
review, repair and nested subagents, including several agents on the same item.
The integration checkout belongs to the integrator; workers return changes and
focused evidence for integration there.

**The repository provisions worktrees under the primary checkout's `.worktrees/`,
independent of OS, model or instruction filename.** The [worktree command](vos/cli/worktree.py)
finds the primary checkout through `git worktree list --porcelain -z`, so invocation
from a linked checkout still creates a sibling lane under the same root. It never
derives that root from the caller's working directory or creates nested lane roots.
Worktrees containing unfinished work survive sessions and are retired explicitly;
the OS temporary directory remains appropriate for disposable test fixtures.

Creation uses Git's `--relative-paths` support, which requires **Git 2.48 or newer**.
Relative links between the checkout and its Git metadata remain usable when the same
Windows directory is accessed through WSL. Git records `extensions.relativeWorktrees`
when creating the first such lane, so every Git installation opening that repository
must support the extension. There is no silent fallback to absolute links. See
[Git's worktree documentation](https://git-scm.com/docs/git-worktree/2.48.0).

Before dispatch, the parent creates each lane serially from the intended committed
input revision. Uncommitted integration changes are not part of that revision; land
the needed input first or explicitly transfer and record the intended changes.

```console
$ python tools/run.py worktree list --json
$ python tools/run.py worktree create review-20260909-a --base HEAD --json
$ python tools/run.py worktree verify <absolute-worktree> --base <revision> --exact --json
```

Use a unique lowercase lane name, for example a task, date and short suffix. Creation
requires a fresh destination and a fresh branch, defaults the branch to `work/<lane>`,
and checks that its initial HEAD is exactly the resolved base commit. Symbolic bases
such as `HEAD` resolve in the invoking checkout. An existing
branch or path is a refusal, never an instruction to reuse old work. The JSON output
provides the actual checkout and revision data for the handoff.

A dedicated worktree already provisioned by a host application may retain its
assigned location and branch or detached HEAD. The parent verifies its Git membership,
expected revision and exclusive assignment before dispatch; directory names alone
establish none of those facts. Use `--exact` for an unchanged starting revision;
without it, verification allows commits descended from the declared base. Review any
uncommitted changes separately. Provider settings and hooks govern native creation;
these instructions do not relocate a checkout or override filesystem permissions.

Every nested checkout must be excluded from corpus scans. Creation and verification
require the target to be ignored and absent from the index of each containing
registered checkout. [.gitignore](../.gitignore) reserves `/.worktrees/`
while retaining narrow exclusions for existing and native provider worktrees. This
keeps duplicate documents and linked checkouts' `.git` pointer files out of the
selftest, which includes untracked non-ignored files as well as indexed files.
The worktree command refuses a `VOS_GIT_DIR` override: verification must discover
each checkout's own Git metadata rather than use one administrative directory for
every lane. Existing Windows absolute paths are translated when verified in WSL;
native host worktrees otherwise retain their existing metadata and lifecycle.

Every brief names the absolute worktree path, branch or detached HEAD, base revision,
owned files, focused checks and integrator. The worker verifies its checkout with
`git -C <worktree> rev-parse --show-toplevel` before starting. All repository reads,
edits, checks, staging and commits target that checkout: set the shell's working
directory on every call, use `git -C <worktree>`, and use absolute paths rooted there
for file tools and scripted writes. A previous `Set-Location` is not a guarantee
about the next tool call's directory. Build and log outputs use that checkout's lane,
which [the build environment](vos/env.py) derives from Git's administrative identity.
Coordinate shared mutable toolchain state separately. Report an accidental write
outside the lane to the integrator, who resolves ownership before integration.
If isolation cannot be established, keep the worker undispatched. Nested fan-outs
follow the same procedure, with a distinct checkout per child.

Retire only lanes owned by this batch. Inspect `git -C <worktree> status --short`,
preserve needed local outputs, and confirm the lane's commits are integrated with
`git merge-base --is-ancestor <lane-branch> <integration-revision>`. Then use
`git worktree remove <absolute-worktree>` and `git branch -d <lane-branch>` from the
integration checkout. A refusal leaves the lane or branch for review; do not force
removal or reset a branch to reuse its name. A squash or cherry-pick may require a
separate equivalence review. Host-managed checkout cleanup belongs to that host;
do not rename or remove another active session's worktree.

## Check scheduling during fan-out

**One integrator schedules validation for each stable integration batch.** A batch
is the set of lane outputs being accepted together on one settled tree. Each brief
names the lane's dedicated worktree, owned files, focused checks and deferred
integration checks, following [worktree isolation](#worktree-isolation-during-fan-out).
Read-only scouts inspect sources in their own worktrees without running gates.
Workers check a coherent change when the result can guide their next edit; they
do not run the complete wave after every file, tool call or handoff. In the
integration checkout, the integrator combines overlapping check requests and
reserves a quiet tree for their readers.

| Changed surface | Feedback during lane work |
| --- | --- |
| Documents and cross-artifact facts | `python tools/run.py check` (or `python tools/check.py`) after a coherent edit batch. It checks the whole corpus; there is no file or rule filter. |
| A checker rule | `python tools/run.py selftest --rule K-110`, substituting the changed rule, once the whole checker baseline is clean. This supplies only the selected rule's mutation evidence. |
| Tool behavior | `python tools/run.py test --only sync_instructions`, substituting a module-name substring for the affected tests. |
| Python sources or checker configuration | `python tools/run.py typecheck` after a coherent batch when feedback is needed before integration. It checks all tools; there is no path filter. |
| Model, RTL or proofs | The changed artifact's required guest checks, against its real inputs and isolated outputs. Coordinate shared builds and proof runs; use `evidence` when its complete sweep is the acceptance check. |

Use the existing verdict for unchanged inputs. If a checker run already reports
arithmetic drift, instruction disagreement or owed co-reads, resolve those findings
before running a selftest: its baseline runs the whole checker even under `--rule`,
and a failed baseline supplies no mutation verdict. Workers report deferred repair
and checks explicitly. They do not run `--fix` or bare `run.py`; the latter also
validates AGENTS.md and restores a missing CLAUDE.md import. A separately justified
full lane gate uses `--check` and a slot agreed with the integrator.

**Budget workers across the machine.** The full runner already parallelizes its
gates; selftest, behavioral tests and typecheck also run internal workers. Keep one
full host wave active across the fan-out by default, including across worktrees.
Schedule costly guest work against the same CPU and memory budget. Focused checks
may overlap on independent stable inputs when capacity permits; `selftest --jobs N`
and `test --jobs N` bound their command's workers, not the whole gate. Default selftest
sandboxes are private; never share an explicit `--sandbox` directory between live runs. Builds,
proofs and oracle runs retain their own output ownership and locking rules.

The integrator closes the batch in this order:

1. Join the lane outputs, resolve shared edits, read the affected prose, and record
   required co-read judgments. Inspect `git status --short --untracked-files=all`
   and each intended diff; track new deliverables by path so the checker sees them.
   Finish instruction maintenance, generated artifacts and other writes before gate readers
   start. Keep the validated checkout stable until its readers finish.
2. Resolve known findings cheaply. Use `python tools/run.py sync-instructions` for
   import validation and `python tools/run.py check --fix` for arithmetic repair
   alone when more editing or co-reading remains. Repair once after the batch's
   authored inputs settle; repeat only if new input changes or findings require it.
   An intermediate merge needs a targeted check only when its answer affects the
   next integration decision.
3. Run one complete host wave: `python tools/run.py --check` on the settled tree,
   or `python tools/run.py --fix` when only repair remains. Append `--tests` for tool
   changes or CI-equivalent host validation. `--fix --tests` already includes a
   fresh checker, selftest, typecheck and default behavioral suite after repair;
   do not follow success with a duplicate `--check --tests` on unchanged inputs.
   The default suite does not replace required slow tests or guest evidence.
4. Record the command, tested revision and any uncommitted input scope, verdict,
   and deferred checks. A lane handoff is provisional until the integrated batch
   passes every required gate and review; a selected-rule selftest cannot establish
   that every mutant was killed. If later edits change a gate's inputs, refresh the
   affected evidence before acceptance. Repeat a complete wave for a new integration
   batch or when the affected scope cannot be established, not as a reassurance run.

These are scheduling rules; the [landing tiers](../docs/implementation/implementation-checklist.md#checklist-conventions)
and item acceptance predicates keep their full gates. `seed properties` still owns
its checkout exclusively against every other reader and writer for the whole run.

## Checking the tools themselves

The documents are checked against each other by [check.py](check.py), and the checker is
checked against its own mutants by [run.py selftest](vos/cli/selftest.py). Neither of
them reads a line of Python as Python, so without a gate of their own the tools are the
one artifact here with no proof, no model, and no reader but their author.
[run.py typecheck](vos/cli/typecheck.py) is that gate for the Python's discipline, and it runs two
checkers because one cannot do the whole job; what a type cannot decide, the behavior, is
[run.py test](vos/cli/test.py)'s to hold.

A bare `run.py` first validates the shared instructions and restores a missing
import, then runs `check`, `selftest` and `typecheck` in parallel. Their reports are collected in a fixed order
and produce one exit code. `--tests` adds the behavioral suite; `--check --tests`
is the same complete validation without tracked writes and is the CI invocation.

`--fix` validates instructions, restores a missing import and repairs derived
artifacts before starting the readers. The checker runs again afterward, so a
repaired finding does not leave a stale failure as the final verdict. An invalid
instruction entry point or crashed repair stops before the validation wave.

The selftest copies the working tree into its sandboxes, so mutations finish before
it starts. Each sandbox runs the generated-artifact checks too: a generator's cost
is multiplied by the mutant population. Keep generators small and measure them
before adding work to every gate run.

| Checker | Pin | What it decides |
| --- | --- | --- |
| [ty](https://github.com/astral-sh/ty) | 0.0.80 | Every expression, against the types it can infer, with `--error all` |
| [ruff](https://github.com/astral-sh/ruff) | 0.16.6 | Every function, against whether it is annotated at all, and the correctness rules [ruff.toml](ruff.toml) admits |

The split is not a preference. ty infers rather than demands, so a function with no
annotations contradicts nothing and is invisible to it; ruff's `ANN` group is what makes
coverage a rule. Both are pinned for the reason Rocq and z3 are pinned, and a version
other than the pinned one is a finding rather than a warning.

The exact checker pins live in [pyproject.toml](pyproject.toml)'s development
group. `jsonschema` is a runtime dependency in the same project, and
[uv.lock](uv.lock) fixes the complete resolution for both operating systems.
The ring emitter uses a cached JSON Schema validator to check declaration shapes
before exposing typed records; fields outside the emitter's scope remain intact.
[run.py typecheck](vos/cli/typecheck.py) reads the pins from the manifest, runs only
the environment's executables, and explicitly gives ty that environment's Python.
K-67 holds this table and the lockfile against the manifest. Global checker shims
and an unrelated activated environment cannot select different tools.

The Python project lives in `tools/`. From the repository root, add a dependency
with `uv add --project tools --no-sync PACKAGE`, or edit the manifest and run
`uv lock --project tools`. Update this checker table when its pins change, and run
the Windows and Linux gates. Review and commit the manifest and lockfile together.
To refresh resolution within the declared constraints, use
`uv lock --project tools --upgrade`. Normal commands synchronize each checkout on
its next invocation, so no manual reinstall window exists across worktrees or OSes.

The optional `model` group pins the pre-commit runner used by the curated model's
hook configuration. On Linux, run it with
`UV_PROJECT_ENVIRONMENT="$PWD/out/venv-linux" uv run --project tools --locked --group model pre-commit --version`;
on Windows, set `UV_PROJECT_ENVIRONMENT` to the checkout's `out/venv-win32` first.
The ordinary host gates synchronize only their default dependency groups.

`--error all` escalates every rule ty carries, including the ones it ships as warnings or
switched off, and that is deliberate: the alternative is a list of opt-ins that silently
stops growing the day ty adds a rule nobody transcribed. What ruff is *not* asked is in
[ruff.toml](ruff.toml): three rules, each named on its own line and each for a reason
that would hold in any project, and no group switched off to spare this code a rewrite. A
single site that has to differ carries a `# noqa` and the sentence saying why.

The settings live in [ty.toml](ty.toml) and [ruff.toml](ruff.toml). In VS Code,
select `out/venv-win32/Scripts/python.exe` on Windows or
`out/venv-linux/bin/python` in Linux/Remote-WSL so editor imports use the same
dependencies as the gate. The Linux typing target is intentional: the guest modules
use POSIX APIs, even when the host checks them. It does not move execution into Linux.

The local `redundant-cast` suppression in [vos/config.py](vos/config.py)
addresses ty's recursive-JSON narrowing behavior, not
package discovery. The negative test in [tests/test_mutate.py](tests/test_mutate.py)
also suppresses `invalid-argument-type`. Unresolved imports remain errors.

## Cleaning local output

`out/` holds disposable output alongside environments and retained evidence. Before
removing an entry, use `run.py worktree list --json` to identify registered work,
check running processes for consumers, and search tracked documents for evidence
paths. Age alone does not establish that an output is unused. Keep each checkout's
active `venv-*` environments, unfinished work's inputs and reproduction recipes,
and evidence that a current completion record explicitly retains.

Completed migration scripts, copied validation checkouts, superseded bootstrap
executables and redundant logs can be removed after their changes are accounted
for in Git and their outputs have no remaining consumer. Review scripts before
discarding them: recurring assertions belong in maintained validation with private
fixtures and inputs discovered from the repository. The [selftest repair
phase](vos/cli/selftest.py) checks stale manifests across the indexed proof corpus,
authored-source preservation and dependent-export convergence. It runs under plain
`run.py`, `run.py --check` and `run.py --fix`; `run.py selftest --rule K-109` is the
focused route. `run.py test --only proofheaders` covers the smaller fixtures,
including missed findings and premature writes, without repeating the corpus sweep.

Keep a cleanup inventory and its retention reasons with the task's local output.
Use explicit paths beneath the inspected `out/` root, recheck them before deletion,
and do not follow links into other directories. Worktree retirement remains the
separate [owned-lane procedure](#worktree-isolation-during-fan-out).

## Current evidence and generated documentation

A model build records the selected source bytes and git revision, tool executable hashes,
build options, output artifacts, stage exits and test-log digest. The evidence sweep
checks that record before and after consuming the model and holds the build lock while
it runs. After all members finish it revalidates and embeds the proof receipt, including
compiled output hashes. It also binds the device-tree compiler's identity. Its JSON
output identifies one execution; a missing result, a failed process
or an input change prevents successful measurements from being published. These records
identify evidence and do not certify a translation or replace the proof kernel.

`proofs status` and `proofs headers` run on the Windows host as well as in WSL.
The proof receipt names the compiled constants, their types and audited assumptions,
the local dependency graph, source identities and compiled output identities. A claim
must resolve to an audited proposition. Matching metadata does not decide whether that
proposition expresses the English requirement; that remains the requirement-to-contract
review. The host checks source and output freshness; the guest records its prover
identity during the proof run.

The requirements register remains the authored normative source. K-109 holds each
non-generated proof's compact reference manifest against the entries selected by its
authored citations. The manifest records the owner, IDs and a SHA-256 fingerprint of
their normative text; it does not copy that text. `check --fix` refreshes the manifest
after arithmetic repairs. K-108 excludes it from citation discovery, so generation
cannot invent new dependencies.

Use `proofs headers --show proofs/PartitionContext.v` to read the selected entries as
Markdown on demand. A current fingerprint records byte agreement, not semantic
agreement between a requirement and a theorem. Authored modeling rationale, criteria
and claim annotations keep their own roles; RingContract keeps its existing generator.

The document parser supports top-level CommonMark fences using backticks or tildes,
with matching delimiter characters and sufficient closing length. Unsupported container
and deeply indented fence forms are refused with a file and line, so an example cannot
silently become a requirement. Ordinary prose, tables and links remain Markdown.

`seed sail`, `seed coq` and QuickChick hold their oracle workspace through staging,
execution, journaling and output publication. Independent oracle workspaces can run
concurrently. `seed properties` mutates the checkout and still requires exclusive access
against every reader of that checkout.
Proof compilation uses bounded workers within dependency waves, preserves report order,
and does not compile a dependent against a failed prerequisite's stale output.
The final `rocqchk` pass uses one shared environment and the pinned tool's default
kernel conversion. Enabling its bytecode compiler would also trust the serialized
bytecode and VM; that option is left disabled. The checker offers no parallel worker
option.

`placement consistency --plan demo_plan --max-candidates 64 --timeout 5` exercises
the finite consistency pilot. It uses the memory plan's candidate domains and existing
predicates, with other islands fixed. Its `sat`, `unsat` and `unknown` results concern
that declared grid, not arbitrary placements or all natural-language requirements.

## Synchronizing agent instructions

[AGENTS.md](../AGENTS.md) is the shared instruction source. [CLAUDE.md](../CLAUDE.md)
contains only `@AGENTS.md` and a final newline, the
[documented import](https://code.claude.com/docs/en/memory#agentsmd) Claude Code loads
at session start. Both files are tracked regular files. LF and CRLF import line endings
are accepted, so checkout normalization on Windows does not change the contract.
Edit shared rules in AGENTS.md; directory placement and lifecycle rules are the same
for every agent. Personal standing preferences defer repository-specific paths and
procedures to this repository instead of repeating them in a global configuration.

`python tools/run.py sync-instructions` validates the nonempty UTF-8 source and its
import, creating CLAUDE.md only when it is missing. It leaves valid files untouched
and refuses unexpected content or unsafe paths. `--check` validates without writes.
The retained command name supports existing callers; it performs no bidirectional
merge, writes no checkpoint and never replaces the shared source from CLAUDE.md.

For a checkout with identical legacy copies, `sync-instructions --migrate` converts
CLAUDE.md to the import. If the copies differ, review and preserve their intended
shared rules in AGENTS.md first; the tool does not discard an independent edit.
The old `--from` options are refused with migration guidance. Existing ignored
instruction-sync checkpoints are no longer read and may be removed when no older
session needs them.

A normal `python tools/run.py` performs validation and missing-import restoration
before starting readers. K-110 checks the tracked source and import inside check.py.
`run.py --check` performs the full read-only gate; CI adds `--tests`. `run.py --fix`
performs the same instruction preparation, repairs derived artifacts, then runs a
fresh validation wave. The tools run on Windows and Linux and install no hooks.
Start a fresh agent session after changing instructions so its loaded guidance
matches the files; existing worktrees retain the instructions at their own revision.

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
- **A rule's cost is the shape of its scan, not the Python around it.** Three shapes each cost tens of milliseconds per pass over the corpus and each has a cheaper equal: `(?m)^` over a document's whole text, which the engine attempts at every line start however few lines match, where walking `doc.lines` with `.match()` behind a substring pre-test gives the line index free; a leading lookbehind such as `(?<![\w-])`, re-decided at every position, where dropping it and checking the boundary in Python on the hits is safe wherever every character inside the token is a word character; and a case-insensitive alternation with no literal prefix, where `str.find` over the lowered text proposes sites and the pattern decides them. The third is where the second's rule reverses, removing the lookbehind making it slower, so a candidate is timed against an equality assertion over the current result rather than applied blind.

## Adding a rule to the checker

Three edits, and the tools refuse to let one be forgotten:

1. The check itself, in the [vos/checks/](vos/checks/) module for its group.
2. Its row in [check-rules.md](check-rules.md). The meta group fails on a rule with no row and a row with no rule.
3. Its mutant in [run.py selftest](vos/cli/selftest.py). The selftest fails on a registered rule with no case, and on a case whose mutation no longer applies.

A rule that reads an enumeration owes the floors group a member count too, so that the day its pattern stops matching anything is the day it says so rather than the day it starts passing vacuously. The exception is a rule whose sites are declared in code and read fail-closed, and each states why: a site that has stopped matching reports at the rule, on the day it stops, rather than as an empty set one group later. The meta group's rules are all of that kind, and five outside it are, K-91 over the two transcriptions of the permutation's known answers, K-97 over the elaborator's version pin, K-99 over what the ring emitter says about the wire encoding, K-101 over the executability of the regions the shipped compositions and the configuration template declare and K-102 over the roster the plan's Current summary states its completed items in. A rule may hold both at once where its readings are not all refusable per member, which K-100 is: its path reading reports at the row and its symbol and command readings carry floors of their own, inside the rule because the meta group has no count to hand the floors group.

A **quarantined** rule keeps all three edits and keeps them together, in [quarantine/](quarantine/): the check under [quarantine/checks/](quarantine/checks/), the row in [quarantine/check-rules.md](quarantine/check-rules.md), and the mutant in [quarantine/gate.py](quarantine/gate.py), which holds the three against each other exactly as the meta group and the selftest hold the landing loop's. What decides which of the two places a rule belongs in is not the rule but its subject: an instrument whose decision is deferred is not worth a second of every landing, and [that directory's README](quarantine/README.md) states the condition that brings each one back.

Before the integrated batch lands, typecheck and the checker must both be green.
The integrator's complete host wave supplies those verdicts; document-only lanes do
not need separate typecheck runs. Use [the check schedule](#check-scheduling-during-fan-out)
for feedback during authoring and for the remaining landing gates.
