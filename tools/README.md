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
| `gate` | host | Synchronizes agent instructions, then runs the three gates below in parallel. `--check` is read-only; `--fix` also repairs derived artifacts before a fresh validation wave; `--tests` adds behavioral tests. A bare `run.py` selects this workflow. |
| `check` | host | Checks every derived fact against the artifact that owns it. `--fix` rewrites the figures that are arithmetic. It is also [check.py](check.py), the one command that is still a path, because the register, the coverage matrix, the crown jewels, the field bindings and the findings register all cite that path for what it decides. |
| `selftest` | host | Seeds each of the checker's rules a defect it must report, and fails on a rule that says nothing. |
| `typecheck` | host | Holds this directory's own Python to the discipline it holds the documents to. |
| `test` | host | Runs the tools' own behavioral tests, one module per subject under [tests/](tests/). |
| `sync-instructions` | host | Synchronizes root AGENTS.md and CLAUDE.md from either side. `--check` verifies equality without writing; `--from AGENTS.md` or `--from CLAUDE.md` explicitly selects a source when edits conflict. |
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

Three are compilers rather than generators, and the difference is which way the artifact is held: where the generators above produce evidence a run consumes and throws away, these produce tracked artifacts, so the rule is the point and the emitter is what gives it something to say. [run.py ring](vos/cli/ring.py) emits [proofs/RingContract.v](../proofs/RingContract.v) from two owners, [the ring declaration](../interfaces/ring-reference.json) and the register's own entry lines, and K-89 holds the tracked file against what it writes. It runs on the host because its inputs are a JSON file and the register parse the checker already makes, which is why its rule can re-run the generator where K-88's cannot. K-99 reads the same emission for the other claim about it: the emitter states the wire encoding as well, and what it takes that from is [the typed IDL profile](../docs/idl-profile.md)'s §4, which is not an owner it reads, so agreeing with the declaration says nothing about agreeing with the rows. [socmap.py](vos/socmap.py) emits [rtl/vos_soc_map_pkg.sv](../rtl/vos_soc_map_pkg.sv), the SoC address map in the language the RTL is written in, from the frozen profile's composition; that one is held by **K-88** rather than by a rule of its own, its row of the generated table being a host row whose generator the checker runs. It is worth reading beside the ring's for the one thing it does differently: its subject is an enumeration rather than a fixed set of fields, so it finds the windows it emits by shape rather than by name and a window a composition gains arrives in the package with no edit to the emitter. [memplan.py](vos/memplan.py) is the third, and its owner is a proof file rather than a configuration: it reads the memory plan's lists, literals and register placement out of [proofs/MemoryPlan.v](../proofs/MemoryPlan.v) and emits [tools/generated/memory-plan.json](generated/memory-plan.json), held by **K-88** the same way, and beside the emitter it carries the exact port of that file's checks [run.py placement](vos/cli/placement.py) searches with, which the tests hold to the file's own refutation variants.

Five more modules are the differential corpus's, and they are named for what they are rather than for where they sit: [dialect.py](vos/dialect.py) is one row per mnemonic the curated model decodes, [asm.py](vos/asm.py) the parser and layout over it, [image.py](vos/image.py) the ELF the emulator loads, [compose.py](vos/compose.py) the packer that turns an assembled image into the link map and per-site table the freeze's §4 joins, and [differential.py](vos/differential.py) the corpus manifest. `dialect.py` is the one of them that holds no table of its own any more: [dialectgen.py](vos/dialectgen.py) writes it out of the bundle, which is the one decision in that pair and states it, and `dialect.py` loads what it wrote. The one name that has to be read carefully is `corpus`: [vos/corpus.py](vos/corpus.py) reads the *documents* this repository checks, and [vos/differential.py](vos/differential.py) reads the *programs* the model runs. They share a word and nothing else.

Two more are the RVFI-DII rig's and sit beside them for the same reason: [rvfi.py](vos/rvfi.py) is the wire format TestRIG defines and the projection from one of its packets onto the commit trace's records, and [vengine.py](vos/vengine.py) is the stream generator, the socket, the seeded defects and the shrinker. Neither decides anything about behaviour: what a divergence *is* stays [trace.py](vos/trace.py)'s, so the rig and the corpus adjudicate through one function rather than two.

[check-rules.md](check-rules.md) is the checker's registry: one row per rule, what passing means, and on what ground. It is the reviewable account of the tool's reach, and the checker holds it against the code in both directions on every run.

## Running them

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

There is no `-d` on the `wsl` invocation `run.py` makes, because `Ubuntu` is WSL's default and the default is what every guest command wants. The name is plain `Ubuntu` and the release is 26.04; it is not the only distribution registered on this machine, and nothing in the tools reads the distribution's name, so the only thing holding this together is that default. `wsl --install` sets the newly installed distribution as the default, so installing another one is the single action that quietly redirects every guest command. `wsl -l -v` says which one holds the default today and `wsl -s Ubuntu` puts it back.

The two lanes spell the interpreter differently, and that is not an oversight. On the host `python3` is worse than absent: the python.org installer ships `python.exe` and `pythonw.exe` and no third spelling, and what answers to `python3` is Windows' own app execution alias, a stub that resolves, prints *Python was not found*, and exits 9009. A tool invoked through it fails as though the tool were broken. So `python` is the name, with `py -3.14` available when several versions are installed. Inside the guest the reverse holds. Ubuntu ships `python3` and no bare `python` at all; this distribution answers to both only because `python-is-python3` is installed on it, and [PEP 394](https://peps.python.org/pep-0394/) still names `python3` as the one spelling a script may assume. So the shebangs stay `#!/usr/bin/env python3` and so does every WSL command written down here, because both have to work on a stock 26.04 that has never had that metapackage. Treating `python` as portable is the one shortcut this rule exists to refuse.

`run.py model build` writes its whole run to a log and prints only where the log is, because a fifteen-minute build is started and left. The last line it writes is `ALL_DONE`, so a caller waits on a marker instead of guessing at a sleep.

`run.py test` leaves the cases marked slow to `--slow`, so the default run answers in seconds.

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
review, repair and any nested subagents. Each agent gets its own checkout even when
several agents work on the same item. The integration checkout belongs to the
integrator; subagents return their changes and evidence for integration there.

Before dispatch, the parent creates each worktree serially under
`.Codex/worktrees/<lane>` on a fresh branch from the intended input revision. Inspect
`git worktree list` before choosing names, use
`git worktree add -b <fresh-branch> .Codex/worktrees/<lane> <base>`, and prove the base
with `git merge-base --is-ancestor <base> <fresh-branch>`. Follow
[the worktree lifecycle rules](../AGENTS.md#before-standing-up-a-worktree) when
retiring a lane. If a worktree cannot be created, keep that subagent undispatched
until it can be isolated. A reviewer receives the revision under review in its own
worktree, and a parent assigning nested work provisions a separate worktree for
each child before it starts.

Every brief names the absolute worktree path, branch, base revision, owned files,
focused checks and integrator. The agent verifies its checkout with
`git -C <worktree> rev-parse --show-toplevel` before starting. All repository reads,
edits, checks, staging and commits target that checkout: set the shell's working
directory on every call, use `git -C <worktree>`, and use absolute paths rooted in
that worktree for file tools and scripted writes. A previous `Set-Location` is not
a guarantee about the next tool call's directory. Build and log outputs use that
worktree's own lane; coordinate any shared mutable toolchain state separately.
Report an accidental write outside the lane to the integrator, who resolves its
ownership before integration.

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
synchronizes AGENTS.md and CLAUDE.md. A separately justified full lane gate uses
`--check` and a slot agreed with the integrator.

**Budget workers across the machine.** The full runner already parallelizes its
gates; selftest, behavioral tests and typecheck also run internal workers. Keep one
full host wave active across the fan-out by default, including across worktrees.
Schedule costly guest work against the same CPU and memory budget. Focused checks
may overlap on independent stable inputs when capacity permits; `selftest --jobs N`
bounds that command's workers, not the whole gate. Default selftest sandboxes are
private; never share an explicit `--sandbox` directory between live runs. Builds,
proofs and oracle runs retain their own output ownership and locking rules.

The integrator closes the batch in this order:

1. Join the lane outputs, resolve shared edits, read the affected prose, and record
   required co-read judgments. Inspect `git status --short --untracked-files=all`
   and each intended diff; track new deliverables by path so the checker sees them.
   Finish instruction sync, generated artifacts and other writes before gate readers
   start. Keep the validated checkout stable until its readers finish.
2. Resolve known findings cheaply. Use `python tools/run.py sync-instructions` for
   instruction sync and `python tools/run.py check --fix` for arithmetic repair
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

These are scheduling rules; the [landing tiers](../docs/implementation-checklist.md#checklist-conventions)
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

A bare `run.py` first synchronizes the root instruction files, then runs `check`,
`selftest` and `typecheck` in parallel. Their reports are collected in a fixed order
and produce one exit code. `--tests` adds the behavioral suite; `--check --tests`
is the same complete validation without any writes and is the CI invocation.

`--fix` synchronizes instructions and repairs derived artifacts before starting
the readers. The checker runs again afterward, so a repaired finding does not leave
a stale failure as the final verdict. A sync conflict or crashed repair stops before the validation wave.

The selftest copies the working tree into its sandboxes, so mutations finish before
it starts. Each sandbox runs the generated-artifact checks too: a generator's cost
is multiplied by the mutant population. Keep generators small and measure them
before adding work to every gate run.

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

The checkers are installed once per lane and not once per machine: uv's tool bin
directory on the host and the guest's are different filesystems, so an install is shared
by every worktree on its lane and by nothing on the other. A bump is therefore both
installs and the pin edit, and the gate is red on one lane between the first install and
the pin landing and on the other between the pin landing and the second install, the
finding reversing direction between the two, so which lane reported is read before a
version finding is read as drift. The window is not a mistake, the install having to
precede the edit; landing the pin commit promptly is what shortens it.

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
against one declared target and not against whichever machine ran the checker. The
`ty: ignore` directives in this directory are the same narrowing cast in
[vos/config.py](vos/config.py) and [vos/socmap.py](vos/socmap.py), where ty calls the code
unsound without the cast and the cast redundant with it, each naming `redundant-cast`, and
one in [tests/test_mutate.py](tests/test_mutate.py) naming `invalid-argument-type`; no
import suppression exists here, which leaves every unresolved
import an error without a carve-out to audit.

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

A normal `python tools/run.py` synchronizes the root instruction files before any
readers start. The same operation is available as `python tools/run.py sync-instructions`.
It copies a one-sided edit and merges independent edits against their last agreed
text. An ignored checkpoint in `out/` preserves that baseline between edits before a
commit; it is tied to the current HEAD. Without a usable checkpoint, the tool uses
identical committed copies. Equal files are not rewritten; one missing file is restored from
its companion. Overlapping changes, unsafe paths and a missing common baseline are
reported without guessing which file wins.

For an intentional conflict resolution, use `sync-instructions --from AGENTS.md` or
`sync-instructions --from CLAUDE.md`, or reconcile both files by hand. `run.py --check`
performs the full read-only gate; CI adds `--tests` to that invocation. K-110 also checks
equality inside `check.py`. `run.py --fix` synchronizes first, repairs derived artifacts
next, then runs fresh checks in parallel. The tool runs on Windows and in WSL and
installs no hooks.

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
