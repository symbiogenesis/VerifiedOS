# The Tools

The tools use Python on the Windows host and in the WSL guest. Use
`python tools/run.py <command>` on Windows and `python3 tools/run.py <command>`
on Linux; the dispatcher sends guest commands to WSL when needed.

## One language, and what forced it

Python spans both execution environments. Command modules use the supported version
declared by [pyproject.toml](pyproject.toml) and the checker targets. The bootstrap,
host, guest, CI and standalone scripts require that same Python minor version,
as [the shared rule](../AGENTS.md#tool-execution-and-validation) requires. The
bootstrap selects the locked project environment through uv after checking its
own interpreter against the manifest.

Annotations use Python's lazy evaluation, with cross-module type-only imports under
`TYPE_CHECKING`; do not add `from __future__ import annotations` or evaluate those
annotations at runtime. [vos/proofenv.py](vos/proofenv.py) uses `os.process_cpu_count()`
to size jobs within the process's available CPU allocation.

## One entry point, and the commands under it

[run.py](run.py) dispatches commands by name; `run.py <command> --help` describes
their arguments. A bare `run.py` selects the complete host gate, which runs only
on GitHub Actions. Use the [check schedule](#check-scheduling-during-fan-out) for
local builds and focused checks, and the
[validation handoff](../AGENTS.md#tool-execution-and-validation) for settled inputs.

[Host CI](../.github/workflows/host-gates.yml) runs on Windows and Ubuntu for pushes
and pull requests to `main`, or through manual dispatch from `main`, without
initialized submodules. A manual dispatch's optional `revision` input must name a full
commit SHA already on `main`; the workflow checks out that commit and refuses any other
ref or revision before running checked-out code. When a dispatch is refused, all later
steps—including reporting, workflow analysis and model hooks—are skipped.
The [Guest CI contract](ci/README.md) owns guest triggers, setup, gate commands, proof
reuse, cold runs and evidence limits.
The [failure-prevention contract](ci/failure-prevention.md) owns the preparation
tools and their focused acceptance controls.
[boot-crypto-target.yml](../.github/workflows/boot-crypto-target.yml) runs M7.1f's
boot signature target campaign, defined in [firmware/crypto/README.md](../firmware/crypto/README.md#hosted-target-campaign).
[boot-chain-target.yml](../.github/workflows/boot-chain-target.yml) runs M3.5b's target
chain campaign from its staged inputs under [the boot-handoff contract](../docs/implementation/contracts/boot-handoff.md)'s section 9.
[instrument-switches.yml](../.github/workflows/instrument-switches.yml) builds and
checks the QuickChick switch on manual dispatch from `main` under
[the instrument switch route](ci/README.md#instrument-switch-route); `run.py instrument-ci`
dispatches it and reads its runs back. `run.py provision --apply` must not import
QuickChick in the local guest (F-616).

**Host CI reports each gate member's result.** `--summary` writes per-member
verdicts as JSON outside the checkout. After success or failure, the workflow
renders a job-summary table and annotations for members that did not finish cleanly.
It distinguishes interrupted gates from failing members. Reporting is skipped for
canceled runs and refused dispatches. The summary adds no check; failure to write
it produces a finding and affects the exit code.

Each member's log, JSON `elapsed_seconds` and CI summary include wall time from
process launch. Members run concurrently, so their durations must not be summed.
[vos/timings.py](vos/timings.py) records finer measurements in JSON `units`:

- Behavioral tests record cases and seconds per module, checkpointing queued,
  running and completed modules as results arrive. A completed failure retains
  its diagnostics even while an earlier module is still running; final reports
  and timing records keep discovery order.
- The selftest records phases and individual cases.
- The checker records module imports, corpus/register/artifact loading, rule groups,
  and the generated group's batched staged-blob read and individual artifacts.
  It includes `cpu_seconds` and, except on Windows, waited-for child-process
  `child_cpu_seconds`.

Selftest and checker units also record `start` (seconds since the member's clock
started) and `at` (start time in epoch seconds). These place units on member and
shared-runner timelines; test-module units omit both fields. Unit durations can
overlap and do not enter the member's printed report. The CI summary names the
slowest units. A collapsed log group prints the runner's CPU count and model,
then every unit as a JSON line, grouped by member and sorted slowest first,
with workflow commands disabled.

Members run with unbuffered output. A member timeout retains captured stdout and
stderr and its last readable timing snapshot while remaining a failed gate with no
verdict. The selftest atomically checkpoints completed phases/cases and names spans
still running at its last snapshot; their elapsed times describe that snapshot,
not the final timeout instant. Diagnostic write failure preserves the preceding
snapshot and never changes a gate verdict. Successful final records contain only
completed units in their existing deterministic order.

For a same-runner checker comparison, manually dispatch Host CI with a full
`performance_base` SHA that properly precedes the tested `revision` on `main`.
Ubuntu's unpartitioned job runs the hosted-only
[comparison controller](ci/archive_scan_benchmark.py) after its ordinary checks.
Baseline tool sources and current tools run in fresh interpreters against the same
unchanged indexed checkout, twice each in alternating order. Complete diagnostics
and decisions must agree and be clean. The `archive-scan-comparison` artifact
records source revisions, interpreter, group timings and whole-process durations;
ordinary push runs do not benchmark. This comparison supplies performance evidence
alongside the required Host and Guest handoff, not a replacement for either.

New commits cancel superseded runs of the same pull request. Main push runs share
a concurrency group only for the same event SHA, canceling redundant automatic
work. Each manual dispatch has its own run group, and different revisions of
`main` keep separate runs. The
[workflow's matrix](../.github/workflows/host-gates.yml) fixes each platform's
partition count and runner image. Mutation cases and sorted behavioral test modules are
partitioned by position within each OS, with every item assigned once. A test module
that declares `INDEPENDENT_CASES = True` (meaning its cases share no state and have a
deterministic order) keeps its position so no other module changes shard, while every
shard runs its own stride of that module's cases.
Every mutation runs the checker in a fresh process and private sandbox through the
group that decides its rule (`check.py --through`); a survivor runs the whole checker.
The template compiles checker modules once into checked-hash bytecode outside its
index; each child validates those hashes against its own source and disables cache
writes so source mutants load their modified code. Each shard checks its immutable
template baseline while building case sandboxes, then checks registry coverage.
The repair-only run builds only its private repair sandbox. Alongside the shards, one
unpartitioned job per OS runs the ordinary checker, typecheck, Markdown lint and the
complete repair path; Ubuntu's unpartitioned job also runs
[workflow analysis](#workflow-analysis), and a separate Ubuntu job runs
[the model's hooks](#model-hooks). Members within a job run concurrently under the
platform's native shell (PowerShell on Windows, bash on Ubuntu), reading their shard
selection and verdict path from environment variables. Aggregate checks are named for
each platform rather than its runner image; `HOST_JOBS` in
[vos/fanout_ci.py](vos/fanout_ci.py) owns those names for historical Host CI evidence
validation, and [test_fanout_ci.py](tests/test_fanout_ci.py) checks the workflow
against them. The aggregate checks require every shard, unpartitioned job and
model-hooks job to succeed, rejecting skipped or canceled jobs. The unsharded command
runs the complete suite and is reserved for GitHub Actions.

<a id="workflow-analysis"></a>**Ubuntu's unpartitioned job analyzes workflows and local actions** in a
dedicated step that runs regardless of the gate verdict and fails the job on any
finding. `zizmor`, pinned in [pyproject.toml](pyproject.toml)'s `workflows`
group and locked outside the gate's environment, runs offline security audits,
including commit-SHA pinning for all actions.
[ci/actionlint.sh](ci/actionlint.sh) runs `actionlint` from a release archive verified
against its pinned SHA-256, reading [.github/actionlint.yml](../.github/actionlint.yml)
for hosted runner labels newer than that release's built-in table. It checks workflow
syntax, expressions and contexts without invoking `shellcheck` or `pyflakes`.
Ubuntu's unpartitioned job caches only the release archive keyed by its SHA-256,
verifying its bytes before every extraction and saving the cache only on successful
`main` pushes.
To reproduce the step in WSL, set `UV_CACHE_DIR`,
`UV_PROJECT_ENVIRONMENT` and `ACTIONLINT_ROOT` to directories under the `lane_root`
that `run.py worktree list --json` reports for the checkout, then run
`uv run --project tools --locked --exact --only-group workflows --no-python-downloads zizmor --offline .github`
and `sh tools/ci/actionlint.sh -shellcheck= -pyflakes=` from the checkout.

Host CI jobs cache uv downloads keyed by the manifest and lockfile under Host CI's
key suffix; only each OS's unpartitioned job saves caches on pushes to
`main`, while other jobs restore them. Environments
and gate results are rebuilt on every run. The Windows gate step sets `TMP` and `TEMP`
to `runner.temp` on the checkout's drive, avoiding the image's
[slower default system drive](https://github.com/actions/runner-images/issues/8755).
Per-member timing notices are also available through the public check-run
annotations API.

**The dispatcher selects the execution lane.** On Windows, `[wsl]` commands
relaunch in the guest and report that choice. Commands that read native build
outputs, including `proofs status`, run there. The checked, generated
[lane reference](generated/command-lanes.md) lists operational and help-only
exceptions declared in [vos/commands.py](vos/commands.py).
[tests/test_lanes.py](tests/test_lanes.py) checks operational declarations with
independent handler fixtures and help declarations against their usage output.

| Command | Lane | What it does |
| --- | --- | --- |
| `gate` | host | Runs the host gates below in parallel. `--check` is read-only; `--fix` repairs derived artifacts before a fresh validation wave; `--tests` adds behavioral tests. `--shard INDEX/TOTAL` runs one partition of the selftest cases and (with `--tests`) behavioral tests; `--unpartitioned` runs the ordinary checker, typecheck, Markdown lint and `selftest --repair-only`. `--fix` is incompatible with `--shard` and `--unpartitioned`. `--summary PATH` writes per-member verdicts and exit codes as JSON, failing if the summary cannot be written. A bare `run.py` selects this command. |
| `check` | host | Checks derived facts against their owning artifacts; `--fix` updates deterministic arithmetic and generated views. Also invokable directly as [check.py](check.py), the path cited by the register and derived views. |
| `floor-div` | host | [Constant signed floor-division reference](../docs/implementation/contracts/constant-floor-division.md): plans a known divisor at width 8, 16, 32 or 64, evaluates checked inputs and emits experimental straight-line RV64 arithmetic. Host oracle checks supply no compiler admission or measured target saving. |
| `selftest` | host | Runs mutation testing over the checker, seeding each registered rule with a defect it must report and failing on any surviving or unseeded case. |
| `typecheck` | host | Runs the pinned `ty` (for both `linux` and `win32` targets) and `ruff` checks over all indexed Python sources under `tools/`. |
| `markdown` | host | Checks indexed authored Markdown table syntax with the locked MD055 and MD056 implementation, outside semantic-rule mutation replay. |
| `prepare` | host for `python`; guest for `model` | `python --path FILE` fixes import ordering with the locked Ruff edition; `--check` reports without rewriting. `model --path FILE` runs the pinned model hooks on selected authored files. Repeat `--path` for each file and review the diff. This prepares inputs without builds, shared hooks or acceptance claims. |
| `test` | host | Runs the tools' own behavioral tests, one module per subject under [tests/](tests/). |
| `worktree` | host | Lists registered checkouts, creates a fresh branch at an explicit base under the primary checkout's `.worktrees/`, and verifies assigned worktrees, including host-provisioned locations. `--json` produces handoff data, including each lane's name and `lane_root`, the guest directory its outputs land in. |
| `retain` | host | Publishes explicitly mapped files into a new contained retained bundle and prints its hash-bound citation. See [retained evidence](../docs/implementation/retained-evidence/README.md) for the command and controls. It neither stages files nor edits the owning note. |
| `fanout` | host | Records explicit worker handoffs, merges their commits into local `main`, repairs derived facts, records recommended CI scope and retires integrated batch-owned lanes. Never pushes, contacts remote Git or CI, or waits for hosted validation; the user owns publication and CI. See the [completion contract and usage](fanout.md). |
| `instrument-ci` | host | `dispatch` sends one dispatch of [the instrument switch route](ci/README.md#instrument-switch-route), refusing nothing its plan job refuses, with a nonce in the run title and its intent journalled first; `--resume NONCE` recovers an interrupted dispatch by that nonce without posting again. `read --run ID` follows each artifact's redirect without credentials, extracts it under `out/instrument-ci/<run id>/`, holds its members to the staging allowlist and its inputs to the run, re-joins the run's verdict and says whether the run is closing evidence for a `--closing` commit. `dispatch --revision-from HEAD` resolves and journals a canonical local commit SHA; raw `--revision` remains available for hosted refusal qualification. `fanout` never runs it. |
| `proof-search` | host | Retrieves current local proof examples and named Ltac definitions by query words, body tokens or authored requirement references, with bounded excerpts, source locations and SHA-256 identities. `--json` follows the tracked [JSON Schema](proof-search.schema.json). Results are advisory; the [portable workflow](../docs/assurance/proof-assistance.md) defines bounded tactic reuse, repair and the unchanged fresh proof gate. |
| `rocq-census` | wsl / host help | Runs the [native metadata or census producer](rocq-census/README.md) against an explicit locked switch and copied precompiled inputs in a fresh native lane. Census mode binds native Search requests and emits field classifications and implementation provenance for adapter replay. Hosted exact assumptions, native controls and recursive kernel qualification remain separate acceptance joins. |
| `sail-context` | host | Retrieves compiler-emitted Sail declarations, scattered clauses and recorded incoming references. Checks the bundle's recorded local source hashes before returning bounded context and SHA-256 identities; omitted sources and the freshness boundary remain explicit. `search`, `symbol` and `references` accept `--json` under the tracked [JSON Schema](sail-context.schema.json). The [portable Sail workflow](../docs/assurance/sail-assistance.md) defines repair, validation and upstream adoption decisions. |
| `sail-assist` | guest | `init`, `status`, `typecheck`, `pause`, `resume`, `replan`, `finish` and `recover` manage finite repair journals under the tracked [schema](sail-assist.schema.json). The strict compiler process envelope preserves raw diagnostics, exit status and before/after input identities. Follow the [workflow and recovery contract](../docs/assurance/sail-assistance.md#agent-workflow). Windows launcher notices go to stderr so JSON stdout remains machine-readable. |
| `sail-mcp` | host | Serves the three read-only context operations over local MCP stdio, supporting versions 2026-07-28 and 2025-11-25. Reuses the existing reader and schemas; no network listener, agent SDK or optional native installation. See the [protocol contract](../docs/assurance/sail-assistance.md#optional-standard-protocol-adapter). |
| `sail-lsp` | guest | Explicit `install`, `status`, `serve` and `qualify` for an isolated Sail language server built from the locked compiler's release archive. Qualification includes live dependency refresh, unsaved diagnostics, restart and a strict-batch comparison. The acceptance compiler stays locked; see the [optional integrations](../docs/assurance/sail-assistance.md#optional-native-integrations). |
| `sail-isla` | guest | Explicit `provision` and `qualify` for pinned Isla and isla-testgen execution of curated capability helpers, 32 generated permission cases, baseline replay and killed/survived/build-rejected controls. Scope is finite helper testing, not an RV64 instruction target or universal proof. |
| `sail-modular` | guest | `qualify` derives static libraries from full generated C++ through libclang AST ranges, preserves method bodies and one shared-state owner, and compares clean baseline/partitioned builds on the same suite and corpus. Source, flags, binaries and header dependencies bind reuse; outputs remain in the native lane. See the [paper adaptation](../docs/assurance/sail-assistance.md#the-modular-sail-paper). |
| `coread` | host | Prints a register entry alongside its cited prose and records the co-read blessing required by K-61. |
| `view` | host | Generates a combined reading view of `spec.md` and `requirements-register.md` outside the corpus, rendering each register entry beneath its prose bookmark. |
| `compute-audit` | host | Compares the authored compute feature map with the core API command inventory derived from the hash-checked OpenCL registry snapshot. Missing, unknown or duplicate command coverage refuses the audit. The snapshot is supplied explicitly; this source-coverage check establishes no implementation or standards conformance. |
| `math-evidence` | host | Validates the [research evidence manifest](../docs/background/math-evidence.json), emits/checks its generated decision view and reports finite reference-composer dictionary shapes. Metadata validation supplies no theorem, production workload or target performance verdict. |
| `matrix-identity` | host | Replays [the pinned finite rank-48 identity](../docs/background/rank48-replay.md) from supplied external inputs or an explicit hash-checked temporary fetch. `check-report` checks receipt provenance without rerunning the inputs; no FP32, target or Rocq acceptance is implied. |
| `blast` | host | Reports which definitions, downstream seams and linking theorems are affected by changing a field of the apex statement. |
| `revocation` | host | Qualifies bounded revocation completion and reuse cases against an explicit holder inventory and schedule. The assessment supplies no runtime implementation or universal temporal-safety theorem. |
| `inference-admission` | host | [The decoded-shape host reference](inference-admission/README.md) joins finite expert residency, uniform declared work and exact symbolic grant arithmetic. Its input-bound report distinguishes session opening from checked routing and preserves declared resources. Physical supply, target timing and wire-parser correspondence remain open. |
| `resident-reads` | host | [The finite resident-read reference](resident-reads/README.md) exercises two-holder immutable windows, current authority and authentication, bounded modeled retirement and abstract write classification. Its executed Python controls supply no compiled-control, target or proof qualification. |
| `allocation-churn` | host | Analyzes captured teardown rates, attributed swept bytes, quarantine peaks and per-period background service under the [roster measurement contract](../docs/implementation/contracts/roster-measurement.md). `CAPTURE --expected-identity EXPECTED --json` binds the input bytes; the composed-roster measurement remains open. |
| `ring-measurement` | host | Analyzes captured queue high water, batches, notifications and per-operation charges against the existing ring declaration under the [roster measurement contract](../docs/implementation/contracts/roster-measurement.md). `CAPTURE --expected-identity EXPECTED --json` reports finite observations in explicit units, with target acceptance open. |
| `boot` | wsl; `roster`, `prepare-fixed-fixture` on either lane | M7.1's harness under the [roster and boot-recipe contract](../docs/implementation/contracts/boot-roster.md). `roster` reports missing executable members; `compose RECIPE` assembles and places members in a checked image; `run RECIPE` revalidates and observes it against the recorded image, console, event and trace digests. `prepare-fixed-fixture` constructs one pair of declared fixture packages and two translated layouts under `out/`; `run-fixed RECIPE` observes an existing fixed-package ELF after read-only store, layout, entry and HTIF validation, without invoking a producer. Both run paths refuse process, timeout and digest failures. Fixture and fixed-package observations supply no accepted real-roster identity or production admission. |
| `composer` | wsl; `package-store`, `compose-fixed`, `check-fixed`, `compose`, `fixture`, `compare`, `project`, `check-project`, `promote`, `build-record`, `check-build-record`, `bind-staged-boot-chain` on either lane | [The composer](composer/README.md) stores fixed native artifacts and composes their exact bytes with `package-store` and `compose-fixed`; `check-fixed` validates an existing image against its stored objects, placement, selected entry and declared HTIF export without rebuilding or writing it. It also emits descriptor-only graphs and source-bound production composition projections. `project` emits the immutable manifest, graph input, recipe members and admission skeleton; `check-project` regenerates their bytes; `build-record` binds published projections and produced artifacts, checking the graph's read-only physical ELF placement; `check-build-record` revalidates those bindings; `promote` refuses incomplete production inputs; `bind-staged-boot-chain` checks retained boot products into an explicitly historical candidate without final target acceptance. `prove` compiles finite Gallina comparisons in the native lane. Native checker/transaction joins and production admission remain open. |
| `admission` | wsl; `record`, `emit-reference`, `production-record`, `check-production-record` on either lane | [The offline checker](admission/README.md). `record` binds a metadata-only reference decision to exact image, graph, roster and request bytes; `emit-reference` writes the generated Gallina comparison. `production-record` joins the production request, build record and declared derivation sources into an image-bound refusal record; `check-production-record` replays it. Missing checked derivations and the production checker keep the generation refused. `compare` compiles the reference comparison in the locked native prover. Reference acceptance never supplies real checked derivations or production admission. |
| `supervisor` | wsl | [The bounded supervisor C](../supervisor/README.md). `check` revalidates and consumes the generated production manifest, compares generated C decisions with the Gallina reference in the locked native prover and exercises current-epoch grants, bounded effect sequencing and refusal prefixes. Generated-manifest target integration and full-roster boot/fault order remain open. |
| `boot-crypto` | wsl; `verify`, `join` on either lane | [The boot signature verifiers](../firmware/crypto/README.md). `run` compares bounded C with pinned standard vectors and an independent executable oracle; `--gallina` also compares the ML-DSA reference and SHAKE256. `target` executes the signature interfaces on the scalar RoT profile through the contained compiler or its [staged streams](../firmware/crypto/README.md#staged-target-streams), retaining exact inputs and verdicts. `stage` writes or checks those streams, `boot-crypto verify` holds them to their manifest and sources, and `boot-crypto join` composes interface receipts into one campaign. Firmware composition has a separate predicate. |
| `copy-service` | wsl; `prepare-package` on either lane | [The bounded copy-service C](../copy-service/README.md). `prepare-package --output DIRECTORY` prepares and rechecks a standalone source recipe; `--check` replays an existing snapshot. It supplies no native output or admission verdict. `check` compares generated C decisions with the Gallina reference in the locked native prover. `target` compiles the same scalar stages, executes the reference rows and actual fenced ring operations, and detects altered-reference/lost-publication controls. `notification` joins publication to actual interrupt-file stores and ordinary pending loads. Both target commands require `--ccomp`, optional `--ccomp-arg`, `--simulator` and `--build-receipt`; `target` accepts `--reference` for the existing comparison. Reports preserve the limits: full C/ISA refinement, ownership closure and composed boot remain open. |
| `witness` | host | `qualify` enumerates bounded witness quorums; `test --only witness` exercises durable recovery and policy transitions. Both separate honest intersection from availability and selective delivery. |
| `session-binding` | host | Checks two symbolic attestation/session-binding models, the TLS application binding and the ensemble link session, against replay, parallel-session substitution, unit-substitution, foreign-ensemble-identity and relay cases. Cryptographic and implementation correspondence remain separate obligations. |
| `assembly-compare` | host | Compares stock compiler assembly under the [reviewed annotation-only contract](../docs/implementation/comparisons/compiler-assembly.md). `LEFT RIGHT --json` reports input and tool identities; equal bytes supply no compiler-campaign verdict. |
| `phase-service` | host | Explores synthetic finite phase-service contracts to closure and emits traces reaching the earliest failing cycle for Q22e, per-hart acceptance order over stated fabric paths and the in-flight drain bound included. `--json` binds source identities, contracts and the composition's own `qualified` and `frozen` flags, which are what keep the target comparison open; `--contract FILE` checks a supplied contract. Target arbiter correspondence and cost qualification remain open. |
| `phase-schedule` | host | Resolves named joint arrivals and digest-bound resource declarations into a phase-service contract, retaining grant conflicts and frame-wrap occupancy for checking. It reads `schema` first: a `phase-schedule-v1` table follows the [input schema](../docs/implementation/phase-service/schedule-input.md), and a `phase-schedule-v2` mode set follows the [mode-transition extension](../docs/implementation/phase-service/mode-contract.md), which explores the product of modes, phases, occupancy and flights to closure with each switch carrying boundary state unchanged. `--completion` adds completion order and quiescent drain to either receipt. Both pages include runnable synthetic examples; target schedule correspondence and actual mode changes remain open. |
| `phase-cost` | host | Checks declared per-slot, frame, area and power cost intervals, with the platform boundary and residency charged once per declared switch, the context term a caller-declared part of `other`, and unknown operands preserved. The [input schema](../docs/implementation/phase-service/cost-input.md) states conservative verdicts and synthetic examples; a favorable arithmetic result is not target qualification. |
| `phase-stall` | host | Explores declared per-hart slot programs to closure under a queue-less stall semantics and a nondeterministic maximal arbiter, bounding the issue waiting of a candidate that stalls rather than buffers: per slot `stall_total_max`, `stall_single_max`, boundary-outstanding residency, `drain_max` and the tail an occurrence cuts, with the zero-wait expansion's refutation reported as realizable or not, joined with `--costs` against declared stall, trap-per-switch and drain intervals by `phase-evaluate`'s three-way rule. The [stalled-transition contract](../docs/implementation/phase-service/stall-contract.md) states the program schema, verdicts and hand-computed fixtures; a stall bound over declared programs is not a WCET, and arbiter correspondence and target qualification remain open. |
| `phase-evaluate` | host | Joins schedule extraction, completion and cost arithmetic against the same schedule path, bytes and name, and checks that the declared pipeline drain covers the modeled bound, for a single-mode or a declared mode-product schedule whose bound is the maximum over every mode's boundaries. The [comparison](../docs/implementation/comparisons/store-buffer.md#executable-prerequisite-preparation) states its zero-wait scope and verdicts; the mode-transition budget is a term the join does not carry, and target qualification remains open. |
| `storage-index` | host | Compares a fixed-height buffered index and plain CoW B+ tree under one conditional redo contract. Reports bounded block costs, map equivalence and crash cases; [Q22f's predicate](../docs/implementation/comparisons/storage-index.md) leaves device qualification and target WCET open. `--json` includes source identities and every measured case. |
| `static-memory` | host | Replays capacity ledgers, checked placements, bounded exact oracles, structural and service experiments, reclamation envelopes, mode families, representability, mutations, phases and lending. `manifest --replay --json` inventories and replays the registered actions. [The experiment contract](../docs/implementation/static-memory/experiments.md) states each action's finite scope and remaining target obligations; `--json` binds working-tree sources and inputs. |
| `memory-planner` | host; demo-tflm in wsl | Checks portable pool/offset plans, retains a checked baseline during bounded search, replays finite optimization evidence and extracts bounded component contracts. `plan --two-stack --two-stack-max-objects N` optionally tries the bounded recognized bipartite-crossing construction; `structure-corpus --two-stack-max-objects N --json` reports synthetic eligibility and byte spans without timing. `demo --json` runs the non-ML worker example; `demo-tflm --json` compiles the pinned-interface demonstration in the guest lane. The [portable contract](../docs/implementation/portable-memory-planner.md) distinguishes model, API and deployment evidence. |
| `memory-certificates` | wsl; encode on either lane | Encodes bounded allocation objectives and checks standard LRAT evidence using a pinned native checker. The [certificate contract](../docs/implementation/static-memory/certificates.md) states the encoding, proof endpoint, build identity and replay commands. |
| `memory-candidates` | wsl | Runs a pinned idealloc implementation as an untrusted generator, preserving the independently checked baseline on unsupported input, failure or regression. The [candidate contract](../docs/implementation/static-memory/candidates.md) states the supported model and actual comparison corpus. |
| `matrix-margin` | host | Checks `PLAN REPORT --json` under the [M-class measurement contract](../docs/implementation/contracts/matrix-margin.md). Binds the case and RVV extension sets, checks output identities, and reports exact sustained throughput and per-watt ratios. Supplied measurements do not establish producer truth or admit instructions. |
| `compiler-diff` | host | M1.2f's two acceptance loops over the contained purecap backend. `program --ccomp PATH` feeds C, given or `--generate`d, through a contained `ccomp -S` in a fresh directory, then the in-tree assembler, the image composer and the golden emulator under the corpus's two questions, reporting each mnemonic, directive and section the dialect refuses by name and line; `--interp` adds the compiler's reference interpreter as the source-side reading and `--perturb` the campaign's negative control. `component` holds a Gallina component's Wasm-oracle run against its purecap run under one declared output encoding, lowering the component's C itself with `--c`, and names the first disagreement; `generate` writes the deterministic FP-free campaign. Every report says a run decides no milestone alone. |
| `compiler-build` | wsl; help on either lane | Builds or validates a contained compiler through a reviewed private driver under the [reuse contract](../docs/implementation/contracts/contained-compiler-reuse.md). Normal builds select validated reuse from their lane-local index; a complete audit hit invokes no compilation, queries or checker. `--fresh` requests cold work; phase records preserve original evidence and identify current validation. No compiler source is incorporated into this tree. |
| `compiler-relocation` | host | [Explicit relocated-path verification](../docs/implementation/contained-compiler-port-decisions.md#explicit-relocated-path-verification) binds a trusted retained-catalog digest and its selected compilation seal to an exact historical-helper/lock mapping. It rehashes restored files without executing them or changing receipts. A successful byte connection supplies no compilation reuse, complete kernel qualification or target acceptance. |
| `vector-bitcount` | host for generation; guest for the adapter | `emit` generates the Sail unit tests and decoded vector-count corpus from an independent fixed-width oracle; `check` rejects drift. `test --only vector_bitcount` checks the oracle, generation and assembly. `smoke` checks the actual Sail expectation selector and its negative control before the hosted model build. Full model tests remain hosted; see [the bounded contract](../docs/assurance/vector-bitcount.md). |
| `corpus-images` | host | `check` holds every reviewed member to its source and image identities; `extend` records new members only after every old member still matches. Changes to existing sources or encoding need an independently reviewed baseline update. See [the corpus contract](../docs/assurance/differential-corpus.md). |
| `block-authority` | host | `emit` generates the block-device capability-refusal corpus from composition and profile owners; `check` rejects drift. `test --only block_authority` checks regeneration, while the guest slow case runs HTIF negative controls against the built model. |
| `boot-handoff` | wsl; layout and chain-join on either lane | M3.5's measured release under the [boot-handoff contract](../docs/implementation/contracts/boot-handoff.md). `run` executes the host stage with both sanitizers and either the explicit fixture verifier or `--signature-scheme slh256s`, then boots released bytes on the golden emulator. `release-target` compares compiled RoT preparation and its captured placement with the host stage, then boots the accepted capture; its finite checkpoint leaves the remaining boot-chain joins open. `signature-target` isolates the bounded SLH callback trial. `layout` checks the contract's tables and assembled image against `vos_boot.h`, and its target-chain tables and case table against `firmware/chain/vos_chain.h`, the verdict owners and the model's boot-control door declarations. M3.5b's target chain campaign follows the boot-crypto staged pattern: `chain-stage --ccomp PATH` compiles the ROM, the runtime, its two watchdog mutants and the M-mode stage through the contained compiler, lays the payloads out through the RoT and M-mode composers, signs the images with disposable OpenSSL keys that stay in its output lane, and writes `firmware/chain/target/`; `chain-verify` holds that directory to its manifest, the sources each unit read, the composers' layouts and the contract's verifier identity freeze with M7.1f's manifest; `chain-target --staged` runs one `--case`, the `--group main-die` over `cold-boot`'s outputs (`--cold-boot DIR`) or the `--group watchdog` on the golden emulator against [the host oracle](vos/boot_chain.py) and writes a shard receipt; `boot-handoff chain-join` composes shard receipts into one campaign, refusing shards whose identities differ. [boot-chain-target.yml](../.github/workflows/boot-chain-target.yml) runs the campaign on hosted runners. |
| `provision` | wsl | Probes the guest toolchain and lane layout against `provision.FACTS`: switches, pins, checkers, distribution packages, per-lane caches and native output directories. By default it reports without modifying the system; `--apply` runs declared installation commands and re-probes, installing `opam init` prerequisites, the reviewed `opam` client when none is on `PATH` and no older root would be upgraded, and an `opam` root when absent or resumable. `--only` filters to `gate` or `toolchain` rows. Build or log roots on `/mnt/` or `tmpfs` fail the layout check. |
| `model` | wsl | Runs workflows over the curated Sail model: `typecheck`, `bundle`, `emit`, `rocq`, `simulator`, `build`, `wait`, `lane`, `smt`, `oracle`, `sweep`, `corpus`, `asm`, `freeze-emit`, `trace-diff`, `devicetree`, `reference`, `config-keys`, `validate-config` and `keepalive`. `rocq` cleans prior outputs, emits [the canonical machine term](../docs/assurance/canonical-machine-term.md) through `generated_rocq_rv64d` for the frozen profile, verifies that inputs and toolchain did not change during emission, and writes the generation receipt defined by [vos/rocqterm.py](vos/rocqterm.py). `bundle` regenerates the tracked JSON model bundle for host checks, and `bundle --check` verifies that the tracked bundle matches current Sail output. `smt` runs the capability-helper property suite ([model/model/unit_tests/cap_properties.sail](../model/model/unit_tests/cap_properties.sail)) through Sail's SMT target, reporting `proved`, `counterexample` or `undecided` (never treating `undecided` as a pass) as Sail-level evidence rather than R-15-007a's theorem. `lane` prints this checkout's build and log paths alongside their underlying filesystems. |
| `evidence` | wsl | Builds the model, verifies its receipt, and runs the reference, profile sweep, differential corpus, devicetree and proof gate. Proofs overlap the model consumers in a separate process. Each run writes a JSON execution record with input identities, process results and measurements. `--no-build` requires a current successful build receipt; stale logs cannot supply its test evidence. `--no-proofs` leaves the proof gate to a separate run, as guest CI's proofs lane does; the record lists it as excluded and claims no proof measurement. |
| `rtl` | wsl | Runs RTL checks: `provenance` parses the synthesis record and `filelist` composes the curated elaboration file list on either lane; `lint`, `vectors`, `crosscheck`, `elaborate` and `wait` run in the guest. `elaborate` elaborates the imported core at both the curated and baseline configurations to verify removed structures, and `wait` checks a backgrounded elaboration. `vectors` generates capability-format test vectors from the Sail model, and `crosscheck` verifies that authored SystemVerilog reproduces every output line. Because curation both substitutes authored files (`rtl.py`'s `SUBSTITUTIONS`) and sets parameters, `elaborate` partitions module differences between authored introductions and parameter-driven removals. |
| `oracle` | wsl | Generates and runs model-as-oracle test vectors from a declarative spec in `oracle-specs/`: `list` and `emit` run on either lane; `vectors` compiles and runs the generated Sail harness in the guest. |
| `seed` | wsl | Generates and evaluates source mutants across Sail or Gallina files against a target oracle. `list` runs on either lane; `sail`, `coq` and `properties` require the guest toolchain. |
| `ring` | host | Generates (`emit`) or verifies (`check`) [proofs/RingContract.v](../proofs/RingContract.v) from [the ring declaration](../interfaces/ring-reference.json) and its governing register entries, backing K-89 on the host. |
| `placement` | host / wsl | `export`, `check`, `admit` and `search` read the memory plan on either lane. `consistency` asks Z3 to select a jointly admissible candidate from the existing finite island grid, labels constraints with requirement IDs, and replays witnesses and contradiction cores through the exact predicates. A truncated grid can produce a witness but cannot establish unsatisfiability. The proof status remains with the Gallina artifact. |
| `quickchick` | wsl | Runs property and vector checks over the Gallina specifications: `vectors` runs enumerative checks in the proof switch, `properties` runs randomized QuickChick draws (or exhaustive walks on small domains) in the QuickChick switch, and `check` verifies the switch's QuickChick commit. `--recipe` runs `check` and `properties` in the commit-pinned recipe switch. |
| `kernel` | wsl; `reader` on either lane | M4.4's host-side differential. `vectors` compiles [quickchick/KernelVectors.v](quickchick/KernelVectors.v) against its `Require` closure in the proof gate's switch; `check` holds the [kernel C](../kernel/README.md) and [trace reader](vos/kernelrun.py) against the generated lines and separately reports fixed release/consumer controls. `mutants` attributes executed kills to their deciding oracle. `restore` executes exact scalar restoration; `effects` executes merged-register trap save, scrub, retirement and fresh-entry defects. Both require `--simulator PATH --build-receipt FILE`. `protected` additionally consumes the accepted contained compiler/configuration and boundary runner to observe real nested frames and timer cuts. `target` supplies M4.4a's signed handoff and finite compiled composition. Use each subcommand's `--help` for its private output and compiler arguments. Broader service, restart and ownership joins remain open. |
| `testrig` | wsl | Runs the RVFI-DII differential harness: `protocol` inspects the wire codec on either lane; `handshake`, `run` and `bridge` drive the emulator over a guest socket. `run` generates DII instruction streams, compares the emulator against a defect-seeded build, and shrinks counterexamples; `bridge` compares RVFI packets with commit-trace records from the same run. `adapt FRAME TRACE` decodes an RTL retirement frame ([vos/rtltrace.py](vos/rtltrace.py)) and compares it with the golden commit trace through [trace.py](vos/trace.py). `carry` re-encodes golden corpus traces as retirement frames and verifies that seeded field mutations are detected. `framesim` simulates the SystemVerilog frame writer under [rvfi-harness/](rvfi-harness/) against stimulus (`--controls` and `--corpus`). `bmc` prints the bounded model-checking smoke configuration from [vos/bmc.py](vos/bmc.py). See [the harness contract](../docs/assurance/rtl-cosimulation-harness.md). |
| `proofs` | wsl / host | Stages sources in the native guest lane and compiles each proof under pinned strictness settings once its `Require` dependencies have compiled and passed audit, within a bounded worker limit. It enumerates compiled constants with Rocq, audits their assumptions and claimed theorem types, and rechecks compiled modules with `rocqchk`. Successful runs publish a portable receipt in the checkout. `proofs export` publishes or (`--check`) verifies the portable receipt from a completed native run without invoking Rocq; `proofs status` checks source and compiled-file hashes in the guest without invoking Rocq; `proofs headers` checks, refreshes (`--write`) or displays (`--show FILE`) compact requirement manifests on either OS. |
| `cic-corpus` | wsl | Inspects compiled proof objects in the native lane for M6.2b-0's CIC checker profile: for each enumerated symbol, it records the transitive dependency closure (`Print All Dependencies`), kind/opacity/universe status (`About`), and syntactic term features (`Print` under `Set Printing All`). `report` writes the report and freshness verdict to `out/`; `check` revalidates freshness against the checkout. |
| `proof-reading` | wsl | `record` captures `Check`, location-stripped `About`, and transparent `Print` output (under `Set Printing All` and `Set Printing Universes`) for every inventory constant from the staged proof compile (or `--sources DIR`) as JSON matching [proof-reading.schema.json](proof-reading.schema.json). `compare BASE CANDIDATE` exits 0 only when both readings match and otherwise reports every differing module, constant and field. |

`model simulator --out PATH` builds Q39's focused replay dependency in a fresh
absolute directory beneath this checkout's native lane. It configures the current
model, builds only the explicit `sail_riscv_sim` target and validates the frozen
profile against the generated schema. Its distinct receipt binds the source
population, actual producer tools, commands, logs and simulator; bundled model
tests are recorded as unrun and full model acceptance as pending. Q39's
HELLO and large-argument replay and the bounded
[fixed-package fixture](../docs/implementation/contracts/boot-roster.md#fixed-package-image-observation)
may consume this route. The fixture validates the receipt before and after its
focused execution and supplies no roster or complete model acceptance. Other
target commands retain their complete model-build receipt contracts. The
[compiler port decisions](../docs/implementation/contained-compiler-port-decisions.md#focused-simulator-dependency-for-compiler-replay)
own its narrow scope.

`compiler-build build` applies the [contained compiler reuse contract](../docs/implementation/contracts/contained-compiler-reuse.md).
The normal policy selects a candidate from its lane-local index and asks the
reviewed private validator to recheck its evidence. A complete audit hit uses the
retained compiler without compilation, queries or checker execution. A valid
compilation alone can seed a new qualification; missing or stale default evidence
runs the required phases. `--reuse-from` explicitly adopts a retained candidate,
and `--fresh` bypasses both tiers and the index. Cold acceptance obligations keep
their existing meaning.

Source revision, original producer and execution timings remain bound to their
original receipts. The current operation records validation time, each phase's
executed/reused state and required retention paths separately. `compiler-build status`
validates a named result without rebuilding or rewriting its basis. Native paths
and the reviewed driver/import manifest are supplied explicitly; the command does
not discover other lanes or install packages. Use `build --help` for scheduling
and profiling options. A new profile capture requires a new checker execution.
All current Q39 producers remain independent of this route.

`compiler-build prime --reuse-from RECEIPT` authenticates an explicit retained
compilation through the private status validator, then writes only an owned
controller receipt and a compilation-tier index hint. It runs no qualification
phase. Default builds revalidate that basis before any required audit; `--fresh`
bypasses it. Complete and compilation hints remain separate, with complete
qualification preferred and useful bases retained after later failure. Ordinary
`status` stays read-only. Automatic indexing of new compilation after a failed
fresh audit still needs truthful private partial-result reporting; genuine
Q39-qualified whole-set reuse remains unaccepted.

`supervisor target` compiles separate contained supervisor and trusted consumer
units and checks the timer transport, authority and padded logical release.
It requires `--ccomp`, `--compiler-config`, `--simulator` and `--build-receipt`.
The full service roster and physical timing qualification remain separate joins.

`kernel loan` checks private sealed-slot redemption and complete fixed-borrower
holder cleanup. It takes the accepted `--ccomp`, `--compiler-config`, `--simulator`
and `--build-receipt`, with an optional native `--out` directory.
`copy-service partition` checks confined payload/fault activations and complete
private-span cleanup using the same compiler/model arguments as `copy-service target`.
Each report states the exercised ownership boundary and retains the image and
trace identities; neither command supplies public-client or full-roster acceptance.

`copy-service join` composes the non-ASR supervisor and private copy activation in
one image, using the same compiler/model arguments as `target` and an optional
`--timeout` per image. It checks payload/notification, the context request and
later acknowledgment, fault cleanup, current-epoch restart, stale and incomplete
refusals, and the declared padded logical boundary. The complete boot roster,
external-client transport and physical WCET retain their separate acceptance.

`rtl widthcheck` checks frozen transport widths and every store-rotation bit/lane.
`rtl device-regs` emits the UART constants from their pinned owner and the block
constants from the block contract and the model's bounds, stamping the commit of the
populated `upstream/mocha` checkout (read with the guest's Git) and refusing a Mocha
directory that is not the root of its own repository. `rtl devicescheck` regenerates the
package, fails on any byte difference or commit mismatch, and runs the standalone UART,
block, and route simulation. These guest checks require their declared upstreams; default
host fixtures do not fetch them.

Each command is implemented as a module in [vos/cli/](vos/cli/) with its own docstring,
`argparse` definition, and `main(argv)` entry point. [vos/commands.py](vos/commands.py)
is the single table mapping command names to modules and execution lanes.

`phase-service` models DRAM refresh as fixed per-phase bank reservations (including the
starting cycle). A reservation requires an idle bank, blocks arrivals to that bank, and
carries its residue across frame wrap while leaving other banks usable; refresh consumes
no injection grant in this synthetic contract. A bank's `path` (default `0`) is the number
of cycles a request spends in the fabric before the bank accepts it. An in-flight request
arrives ahead of the phase's own batch; it is refused as `path-blocked` if its bank is
taken, or as `order-inverted` if an earlier request from the same hart (the request's
optional third element) is still in flight. A closed contract reports `drain` (the maximum
cycles any reachable state keeps a request in flight before acceptance); a refuted one
reports none. Shared refresh ports, target refresh timing, and correspondence to an actual
arbiter remain unqualified. An `arrival-blocked` or issue-time `order-inverted` trace
includes the rejected arrival batch; a `refresh-overlap`, `path-blocked`, or arrival-side
`order-inverted` trace contains only the accepted prefix, with `failure` naming the phase,
bank residue, and in-flight requests at the blocked cycle. Quiet-window fixtures state
arrival restrictions as inputs rather than emitted-code certificates. Receipt `inputs` are
read from the composition, and `schedule` is `null` because R-11-017's artifact does not
exist. `--contract FILE` parses a `Contract` JSON structure (refusing unknown fields) and
exits `0` on zero wait, `1` on refutation, or `2` on a malformed/unreadable file. Receipts
record hashes of the composition source and the exact contract bytes. Acceptance order and
the in-flight drain bound do not establish completion/visibility order or bank-completion
drain.

Add `--completion` to a supplied contract run for the separate
[completion analysis](../docs/implementation/phase-service/completion-model.md).
Its `quiescent_drain` includes residual bank occupancy after stopping arrivals;
scheduled refresh continues, and a blocked drain receives no finite bound. It
also checks whether a later operation of one hart completes before an earlier
one. The original acceptance result and `drain` retain their meanings. A
declared mode product is what `phase-schedule --completion` checks; an actual
mode change, physical completion and architectural visibility require separate
evidence. The [preparation contract](../docs/implementation/phase-service/prerequisite-contract.md)
connects this analysis to schedule extraction and workload cost arithmetic.

`compiler-diff` is M1.2f's differential driver. Its shared
[library](vos/compiler_diff.py) owns compilation, assembly, generated programs, and
run comparisons; firmware, kernel, and service instruments import that library, while the
[command adapter](vos/cli/compiler_diff.py) owns CLI arguments, orchestration, and report
publication. Source inventories bind the implementation each caller uses:

- **Program compilation and preprocessing:** Runs the external `--ccomp` binary (kept
  outside every checkout under M1.1a's containment). It preprocesses C sources once with
  `-E` beside the original source to preserve relative transitive includes, then passes
  the exact retained `.i` bytes to `-S` in a fresh directory (incoming `.i` files are used
  verbatim). The report records the preprocessing invocation, working directory, and unit
  digest; `--interp` consumes the same frozen unit. Repeated `--ccomp-arg=ARG` options
  pass flags unchanged (`-fverifiedos-typed` selects the typed purecap backend) and record
  them in each receipt.
- **Generated campaigns and negative controls:** `--generate N` generates seeded programs
  within the [selected scalar source profile](../docs/implementation/contracts/compiler-source-values.md)
  covering stack pointers, struct fields and copies, calls in both directions, stack-passed
  arguments, branch-selected pointers/nulls, pointer spills across calls, and local arrays
  narrowed via the plan-bound `csetbounds` primitive against an independent plan and
  composition emitted as `.i`. `--pattern NAME` filters patterns. `--perturb` is the
  negative control, shifting one expected constant per program off by one and requiring
  failure at that exact check. `--interp` runs each source in CompCert's reference
  interpreter and flags mismatches as `source-disagrees` (except narrowing programs, whose
  `csetbounds` primitive has target-only semantics).
- **Dialect scan and execution harness:** Before assembly, the driver scans emitted
  assembly against [vos/dialect.py](vos/dialect.py) and [vos/asm.py](vos/asm.py) (after
  normalizing mnemonic-to-operand tabs to spaces) and reports refused mnemonics,
  directives, and sections by name and line. Stock `ccomp -S` emits RV64 `lp64d` without
  capability mnemonics (forbidden by R-18-002), which `--expect-refusal` treats as the
  expected outcome. Refused directives mark the seam between CompCert's printer (`.short`,
  `.long`, `.quad`, `.comm`, `.local`, `.option`, `.section .rodata`, numeric local
  labels, `%pcrel_hi`/`%pcrel_lo`) and the assembler's grammar (`.byte`, `.half`, `.word`,
  `.dword`, `.text`, `.data`, named labels, absolute layout). In `.text`, `.align`,
  `.p2align`, and `.balign` pad with canonical 32-bit `nop` instructions included in the
  emitted-site inventory; partial instruction fill and explicit fill arguments are refused,
  and data alignment remains zero-filled. Assembled streams are wrapped in a harness that
  preserves the store-side root in reserved `c4`, derives a bounded local stack with
  store-local permission and `tohost` authority from that root (R-15-001c), installs a
  trap handler, folds `main`'s return into the HTIF exit code, and runs under the
  `model corpus` simulator invocation. A green run requires both the HTIF success line and
  a nonempty commit trace, plus at least one tagged capability store read back tagged
  (M1.7's memory-roundtrip check).
- **Replay and component comparison:** `--against FILE` compares results against a recorded
  run with matching program names, source digests, and preprocessed-unit digests (failing
  on missing/changed identities or comparison mismatches even under `--expect-refusal`).
  Reused `--keep` directories clear stale outputs and typed-route sidecars before running.
  At the component level (`--c SOURCE`), the harness lowers C through `--ccomp`, maps
  `main`'s boolean return to `true`/`false` on the HTIF console and exit code `0`/`1` to
  match [run_demo.mjs](wasm-oracle/run_demo.mjs), and compares exit verdicts and output
  lengths/SHA-256 digests against the Wasm oracle record. The harness supplies the
  [selected scalar ABI](../docs/implementation/contracts/purecap-abi.md) for test
  compositions; every report carries `milestone_acceptance: open` because differential
  agreement does not prove compiler correctness.

The remaining directories under `tools/` hold generated inputs, oracle specifications, and
standalone harnesses:

- [generated/](generated/): Tracked machine-readable artifacts not authored by hand: the
  Sail model bundle (`sail-bundle.json`) and its source identity (`sail-source-id.json`),
  the encoder table (`encoder-table.json`) generated by [`run.py check --fix`](check.py)
  from that bundle and shipped configurations, the memory-plan placement export
  (`memory-plan.json`) generated from [proofs/MemoryPlan.v](../proofs/MemoryPlan.v), and
  the guest-generated [Fiat inclusion headers and manifest](generated/fiat-crypto/)
  (documented in the [emission record](../docs/implementation/fiat-crypto-emission.md)).
  These live under `tools/generated/` rather than `model/` because `model/` is marked
  `-text` in [.gitattributes](../.gitattributes) and tracks its upstream pin cleanly. K-88
  validates each artifact against its generator or indexed source pin.
- [oracle-specs/](oracle-specs/): JSON specifications for `run.py oracle`, declaring the
  Sail sources to compile, parameters, input domains, harness calls, and output format.
- [cheri-equiv/](cheri-equiv/README.md): Authored Sail schedule and independent
  SystemVerilog consumer for the capability equivalence campaign.
- [quickchick/](quickchick/): Gallina harnesses for `run.py quickchick`.
- [wasm-oracle/](wasm-oracle/): Container build and runner for the CertiCoq-to-Wasm
  oracle ([README](wasm-oracle/README.md)).
- [bedrock2-lowering/](bedrock2-lowering/): Standalone Gallina-to-C lowering experiment
  from Q2a/M1.6 ([README](bedrock2-lowering/README.md)), kept outside `run.py` on the same
  basis as the Wasm oracle.
- [checker-reproductions/](checker-reproductions/README.md): Standalone Rocq sources and
  controls reproducing `rocqchk` behaviors on upstream libraries outside the proof set.
- [quarantine/](quarantine/): Deferred instruments and rules gated by
  [quarantine/gate.py](quarantine/gate.py) ([README](quarantine/README.md)). K-83 prevents
  the main landing loop (`run.py` / `check.py`) from importing `quarantine/`, while the
  quarantine gate reuses [vos/seeded.py](vos/seeded.py) to test its rules against seeded
  mutants.

The shared library lives in [vos/](vos/) and separates parsing and data structures from
check verdicts:

- **Document, register, and proof readers:** [corpus.py](vos/corpus.py) loads indexed
  repository documents; [register.py](vos/register.py) parses the requirements register
  and counted tables; [apex.py](vos/apex.py) parses the apex Vocabulary record;
  [figures.py](vos/figures.py) formats and repairs derived counts; [coread.py](vos/coread.py)
  tracks register-to-prose co-read pairs; [proofcites.py](vos/proofcites.py) lexically
  extracts proof citations and declarations on the host without invoking Rocq;
  [provenance.py](vos/provenance.py) parses the RTL synthesis provenance record;
  [pins.py](vos/pins.py) parses upstream pins in `THIRD-PARTY.md`; and
  [fieldbindings.py](vos/fieldbindings.py) parses the field-bindings table for the
  `bindings` check group and [run.py blast](vos/cli/blast.py).
- **Environment, reporting, and configuration:** [env.py](vos/env.py) resolves host/WSL
  lane paths and build environments; [report.py](vos/report.py) formats check verdicts;
  [seeded.py](vos/seeded.py) standardizes mutation verdicts (`killed`, `survived`,
  `stillborn`, `undecided`, `unseeded`), exit codes, and crash journals across all
  mutation loops; [jsonc.py](vos/jsonc.py) and [config.py](vos/config.py) decode the Sail
  model's JSON-with-comments configurations; and [trace.py](vos/trace.py) parses and
  compares executor commit traces.
- **Sail bundle and model readers:** [sailbundle.py](vos/sailbundle.py) indexes the
  typechecked AST bundle emitted by Sail (`tools/generated/sail-bundle.json`);
  [sailexpr.py](vos/sailexpr.py) evaluates AST expressions; [encdec.py](vos/encdec.py)
  joins `encdec` and `assembly` clauses; and [freezeschema.py](vos/freezeschema.py) owns
  the [freeze measurement §4](../docs/implementation/contracts/freeze-measurement.md#4-the-emitter-provenance-schema)
  provenance schemas. Four modules combine bundle definitions with targeted file reads
  across `model/`, `rtl/`, and the document corpus: [geometry.py](vos/geometry.py)
  (welded block size), [capformat.py](vos/capformat.py) (capability format widths and
  packings), [coreclass.py](vos/coreclass.py) (core-class table and extension registry),
  and [decode.py](vos/decode.py) (decoded mnemonics). Named Sail definitions (`type`,
  `let`, `mapping`, `function`) are read from the bundle so renames fail loudly, while
  comments, configuration keys, test assertions, and SystemVerilog `localparam` bindings
  are read from their source files.
- **Model files outside the bundle:** Because `model/` is excluded from the general
  document corpus and stubbed as empty files during [run.py selftest](vos/cli/selftest.py)
  sandboxing, any `model/` file read directly by a check rule must be declared in
  [corpus.py](vos/corpus.py). `MODEL_FACTS` explicitly lists individual files read for
  model values, hooks (K-118), or platform window pairings (K-94), while
  `is_model_citation_path` admits `.sail` sources scanned for requirement citations by
  K-63. Keeping the two declarations separate prevents citation-scan paths from silently
  expanding the value-fact allowlist.
- **Generators and artifact emitters:** [oracle.py](vos/oracle.py) emits Sail harnesses
  from `oracle-specs/`; [sailrig.py](vos/sailrig.py) compiles and runs Sail harnesses;
  [mutate.py](vos/mutate.py) generates Sail and Gallina mutants; [proofs.py](vos/proofs.py)
  orders Rocq modules by `Require` dependencies; and [gallina.py](vos/gallina.py) stages
  and compiles scratch proof copies. Three emitters produce tracked artifacts checked by
  K-88, K-89, and K-99: [run.py ring](vos/cli/ring.py) emits
  [proofs/RingContract.v](../proofs/RingContract.v) from
  [interfaces/ring-reference.json](../interfaces/ring-reference.json) and the register
  (checked against the declaration by K-89 and against
  [the typed IDL profile §4](../docs/languages/idl-profile.md#4-the-wire-format-mapping)
  by K-99); [socmap.py](vos/socmap.py) emits [rtl/vos_soc_map_pkg.sv](../rtl/vos_soc_map_pkg.sv)
  from the frozen composition; and [memplan.py](vos/memplan.py) emits
  [tools/generated/memory-plan.json](generated/memory-plan.json) from
  [proofs/MemoryPlan.v](../proofs/MemoryPlan.v) and ports its placement checks for
  [run.py placement](vos/cli/placement.py).
- **Differential corpus and RVFI modules:** [dialect.py](vos/dialect.py) loads the encoder
  table generated from the Sail bundle by [dialectgen.py](vos/dialectgen.py);
  [asm.py](vos/asm.py) parses and lays out assembly; [image.py](vos/image.py) builds ELF
  images; [compose.py](vos/compose.py) packs assembled images into link maps and per-site
  tables; and [differential.py](vos/differential.py) reads the differential program
  manifest (distinct from [corpus.py](vos/corpus.py), which reads repository documents).
  Alongside them, [rvfi.py](vos/rvfi.py) defines the TestRIG RVFI-DII wire format and its
  projection onto commit-trace records, [vengine.py](vos/vengine.py) drives stream
  generation, socket transport, seeded defects, and shrinking, and
  [rtltrace.py](vos/rtltrace.py) adapts the RTL harness's retirement frames through
  `rvfi.py` into [trace.py](vos/trace.py).
- **Check modules:** Individual check rules live in [vos/checks/](vos/checks/), one module
  per rule group (`counts` splits its per-artifact helpers across `counts_*.py` beside
  [counts.py](vos/checks/counts.py) while remaining a single registered group in
  `GROUPS` and [check-rules.md](check-rules.md)).

[check-registry.json](check-registry.json) owns each rule's required metadata and reach class. [check-rules.md](check-rules.md) presents its generated registry and reach views. The driver binds the definitions to executable groups and requires a clean group to report every declared rule; K-00 checks the definitions, reported coverage and generated bytes. The meaning of a claim and the correctness of its reach classification remain review judgments.

The prerequisite declarations have host-readable checks as well. `device-registers
emit` generates Gallina accessors and SystemVerilog constants from
`interfaces/device-registers.json`; `device-registers check` refuses stale output
and unreviewed model layouts. The wire-format inventory and calibration schema
also generate their review documents. K-88 checks these views and their source
validators; `check --fix` regenerates them. These checks establish declaration
consistency, not parser derivation, device behavior or physical qualification.

## Running them

The root [EditorConfig](../.editorconfig) supplies editor defaults for UTF-8, LF,
final newlines and whitespace, with Python and YAML indentation. Markdown keeps
trailing spaces for hard line breaks, and patches keep context whitespace.
Imported model and upstream trees, retained evidence, build outputs and nested
worktrees keep their own settings. These are editor defaults, not validation:
[Git attributes](../.gitattributes) own checkout normalization and byte-preserving
exceptions, [Git ignore rules](../.gitignore) own untracked-output exclusion, and
the Python generators and acceptance checks still own their output bytes and verdicts.

Install Python within the project's supported range and [uv](https://docs.astral.sh/uv/getting-started/installation/)
at the version declared by [pyproject.toml](pyproject.toml)'s
`tool.uv.required-version`. Both must be available in each OS where commands run;
Windows installations do not supply WSL's prerequisites. No activation, global
package installation, or separate checker installation is needed.

`required-version` is an exact pin, not a floor. A uv patch release can change how
the lockfile is written, CI's `setup-uv` would resolve a range in the manifest to
the highest release it admits, and [guest bootstrap](ci/bootstrap_guest.py)
requires the installed uv to equal the pin. Move the pin when a release fixes
something these tools exercise, or together with other tool refreshes, rather than
for every patch release. A move is one coordinated switch: uv refuses a project
whose `required-version` it does not satisfy, and every checkout on the machine
shares the host's uv and the WSL guest's uv, so both binaries change with the
manifest, and a checkout whose manifest still names the old pin stops until it
takes the move.

The manifest's `exclude-newer = "3 days"` is a release cooldown: a resolution admits
only files uploaded more than three days before it runs, so a release has that long
to be reported or yanked before the lock can take it. [uv.lock](uv.lock)'s
`[options]` records the span as `exclude-newer-span = "P3D"`, beside a placeholder
timestamp uv marks as having no effect, and never a date taken from the clock.
`uv lock --check` and each bootstrap's `uv run --locked` compare that span with the
manifest's and do not hold locked releases against the current date, so the
lockfile does not churn as days pass, and `uv lock` without `--upgrade` leaves it
byte-identical. The cooldown acts when uv resolves again, after an upgrade, a changed
pin or dependency, or a changed cooldown setting: a locked release the cutoff excludes
is then replaced by the newest release it admits, even an older one.

`[tool.uv.exclude-newer-package]` grandfathers the locked releases that were younger
than the cooldown when it was adopted. Its entries exist only to keep that lock valid
under such a resolution, and each also holds its package at the locked release until
the entry is deleted. An entry's cutoff is the first whole second after the upload of
its release's last file: uv compares each file's upload time at the index's
microsecond precision, and a cutoff copied from uv.lock's millisecond `upload-time`
excludes a file uploaded within that millisecond and silently drops it from the lock.
An entry can be deleted once three days have passed since its cutoff, when its
release has aged past the cooldown; the comment on each manifest line gives that
moment, and no rule checks that comment against its cutoff, because the entries are
transient. After deleting one from the manifest, `uv lock --project tools` should remove
only that package's line from uv.lock's `[options.exclude-newer-package]`, and the
table's header with its last line, leaving every `[[package]]` entry byte-identical.
A changed version of the deleted entry's own package means the entry went before its
date, and any other change then follows from it; when that package keeps its version,
any other `[[package]]` change is index drift from the re-resolution and is reviewed
on its own.

The supported interpreter remains Python 3.14. Python 3.15.0 is released, and
replacing `PyYAML` 6.0.3 with the pure-Python `ruamel.yaml` 0.19.1 wheel closes
the all-groups, wheels-only resolution under `no-build = true`; upgrading the
universal `requires-python` floor to 3.15 remains a separate coordinated step
across bootstrap, host, guest, and CI.

When a compatible Python is absent, install it explicitly with your platform's
installer or `uv python install --no-config <supported-minor>`, taking the minor
from [pyproject.toml](pyproject.toml)'s `requires-python`. That command bypasses project
configuration for the manual install. The project keeps `python-downloads = "never"`,
and normal commands never download Python. Ensure uv is on the non-interactive PATH
used by WSL as well as your interactive shell.

The first command synchronizes [uv.lock](uv.lock), then runs inside the managed
environment. Windows uses `out/venv-win32`; native Linux checkouts and CI use
`out/venv-linux`. WSL reading a Windows checkout uses `venv-linux` under the
Git-derived guest lane root. Each checkout has its own environments. Only the manifest,
lockfile, and each OS's uv download cache are shared, never Windows and Linux
executables. The runner selects an installed interpreter matching the project.

Every top-level invocation checks the locked resolution; stale or missing lockfiles
stop before dispatch rather than being regenerated. Child commands inherit the
settled environment. Read-only gates may populate ignored environments and caches,
but do not modify tracked dependencies or documents. [check.py](check.py)'s direct
entry point uses the same bootstrap.

From anywhere, and from either lane. Every tool finds the repository root from its own
location rather than from the working directory, and `run.py` sends a guest command
into WSL itself, so there is neither a wrong directory nor a wrong lane to be in. The
hop carries the checkout as the guest's working directory, and
[where a file lives](#where-a-file-lives-and-which-lane-touches-it) states what the
guest then reads across the OS boundary and what it never writes back across.

```console
$ python tools/run.py help                       # every command, and the lane it runs in
$ python tools/check.py                          # checker feedback after a coherent document batch
$ python tools/run.py check --fix                # integrator: arithmetic repair alone
$ python tools/run.py selftest --rule K-110      # focused mutation feedback for the changed rule
$ python tools/run.py typecheck                  # the tools against their own discipline
$ python tools/run.py test --only test_lanes     # focused behavioral feedback for an affected module
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

The following commands need the toolchain, so asked for on the host they are
re-launched in the guest and say so. Inside the guest they are
`python3 tools/run.py <command>`. Select checks for the issue being investigated;
the examples are not a local acceptance suite. The [Guest CI contract](ci/README.md)
lists the complete hosted campaigns, including the proof gate. `model build` also
runs the full bundled CTest suite, so that command is CI-only. QuickChick switch
checks run only on the [instrument switch route](ci/README.md#instrument-switch-route).

```console
$ python tools/run.py provision                  # is this machine the lane, and what is missing
$ python tools/run.py provision --apply          # and install what this tree states a command for
$ python tools/run.py provision --only gate      # the rows the three host gates alone want
$ python tools/run.py model typecheck
$ python tools/run.py model bundle               # regenerate the model's own bundle
$ python tools/run.py model bundle --check       # and hold the tracked one against it
$ python tools/run.py model rocq                 # the canonical Rocq term and its identity
$ python tools/run.py model lane                 # where this checkout builds
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
$ python tools/run.py quickchick vectors         # the Gallina front's answers
$ python tools/run.py quickchick freeze          # the freeze's model, stated twice
$ python tools/run.py seed coq --sample 20
$ python tools/run.py seed sail --spec keccak --sample 14
```

There is no `-d` on the `wsl` invocation `run.py` makes: it uses WSL's default distribution carrying the toolchain. No release number or distribution name is enforced by the tools. The [current host status](wsl-migration.md#current-host-status) records the migrated host's selection. `wsl --install` can change the default, so check `wsl -l -v` after installing another distribution and use `wsl --set-default <distribution-name>` to select the intended toolchain installation.

The entry-point spellings differ by OS. Use `python` on Windows; the `python3` app-execution alias may not launch an interpreter. Use `python3` in Ubuntu, where a bare `python` is not guaranteed. [PEP 394](https://peps.python.org/pep-0394/) gives the guest spelling, which the shebangs and WSL launcher retain. The [installation guidance](#running-them) supplies a compatible interpreter; after bootstrap, both lanes use it in their managed environment.

`run.py model build` writes its complete hosted run to a log. Its
`--background` form detaches and returns the log location. Use `run.py model wait`
to wait on the lane lock and read the completion verdict; an `ALL_DONE` marker
alone cannot establish that the build and its current receipt passed. Ninja edge
lines give seconds since the build began. When the recorded memory budget permits,
the Sail test `smt_properties_rv64d` starts after configure alongside compilation,
with a private Sail memo. The CTest stage collects that early run and the rest of
the suite, and the evidence sweep sums their tallies.

`run.py test` leaves the cases marked slow to `--slow`. Concurrent test modules run
in separate spawned processes, isolating their environment overrides, patches and
redirected output. Workers may run later modules, so tests still restore temporary
state. Cases within a module remain sequential, and reports
retain module order, including captured output when a module fails. Case and
module-load failures include their tracebacks. Reports count skipped cases by
slow/lane restrictions and explicitly identify modules with no selected cases;
intentional empty shard shares keep their existing successful verdict.
`test --jobs N` limits concurrent workers; the default uses
available CPUs up to eight. Imports happen inside each worker, so test callbacks
may be closures without requiring serialization. `test --native-controls` selects
only slow toolchain cases and refuses an unavailable guest toolchain or an empty
selection. Guest CI runs that selection serially after successful model evidence;
it does not select ordinary cases or host-only recursive full-gate controls.

`trace-diff` bounds each executor run with `--timeout`, so an emulator that hangs without retiring instructions becomes a SHORT finding instead of a command that never returns.

`model corpus --refresh` rewrites the manifest's own record counts and trace digests, which makes it the one flag that can turn a regression into the baseline: it is for the run where the manifest is what changed, and never for a red run.

The full `model corpus` command also runs [the block-image persistence
campaign](vos/block_persistence.py) in a fresh lane output directory. It checks
write/reopen and flush/reopen across separate emulator processes, retaining the
programs, traces, images and event receipts. Either campaign's failure fails the
command; the manifest's member tally describes only its own programs.
`model corpus --persistence-only` selects the persistence campaign for focused
debugging. Named corpus members and `--assemble-only` retain their narrower
scope; `--persistence-only` refuses combinations with those options or `--refresh`.

`model typecheck` runs `sail --just-check` with its output inherited, and Sail prints nothing on success, so exit 0 with nothing printed is the pass and not a run that failed to start.

`tools/co-read.json`, the ledger `coread --bless` writes, is one line per requirement id, so two lanes blessing disjoint ids merge cleanly and two touching one id conflict loudly, which is the right outcome. A conflict there is resolved by hunk and never by taking a side whole, which discards every blessing the other lane recorded and re-opens the pairs it read; the merged text of a conflicted pair then wants a fresh `coread --show` and `--bless`.

### Host tool discovery

On this Windows host, a sandboxed PowerShell session can report `git`, `python`
and `uv` as unrecognized even while their installation directories appear on
`PATH`. Access restrictions can hide the executable or its parent directory;
this result alone does not establish that the tool is absent.

Check `Get-Command git,python,uv` and access to the installation paths. Git is
available through the user's `AppData/Local/Microsoft/WinGet/Links/git.exe`;
Python and uv are in the user's `AppData/Local/Programs/Python/` installation.
When access is denied, use the execution tool's normal escalation mechanism
and repeat command resolution there. Do not reinstall tools or change the
system `PATH` to repair a sandbox restriction. Every command still targets
its assigned checkout and keeps the host/guest placement rules below.

## One toolchain, several checkouts

The [current host migration is complete](wsl-migration.md#current-host-status).
All transferred WSL data and accompanying Windows repository data are restored;
work waiting only for that migration can continue under its existing acceptance
predicates. `VerifiedOS-Restored` is the default WSL distribution.

For a new computer, use the [WSL migration guide](wsl-migration.md) to retain the
old distribution and Windows compiler checkout. Check CPU architecture before
restoring executable toolchains; historical evidence still requires revalidation.

Each checkout has a **lane** with separate build outputs, using the shared WSL toolchain. `run.py model lane` reports its paths, filesystems and active builds.

Git's unique administrative name for a linked worktree determines its lane. Its `.git` file points to that administrative directory under the primary checkout's `.git/worktrees/`. Linked worktrees build under `/root/build/lane-<name>/`; the primary checkout keeps its existing paths. All lanes share only the M0.4 oracle tree, which contains pinned stock upstream sources unaffected by local curation.

The bounded distribution keepalive runs from its native pidfile directory. It
does not inherit a checkout directory whose handle would prevent Windows from
retiring that worktree. The lease still has its existing duration and identity;
the [failure-prevention contract](ci/failure-prevention.md) records this launch
requirement beside the other preparation controls.

Sharing a build tree causes three failures: CMake refuses a cache configured for another source directory; one build can truncate another's log; and consumers can silently read the wrong simulator. `sweep`, `corpus`, `trace-diff`, `devicetree` and `reference` all depend on lane separation.

A build holds a `flock` lock for its lifetime and refuses a concurrent build in the same lane. Background builds inherit the lock; the kernel releases it when the build exits or dies. `run.py model wait` waits for release, then checks the log and, if its stages passed, the build receipt. A missing, malformed, unsuccessful or incomplete receipt fails the wait, with its recorded refusal reason when available. Changes to bound sources, tools, options, artifacts or logs make the receipt stale and also fail the wait.

Other stateful commands also name and refuse conflicting owners. `emit` shares the build lock because it uses the same CMake tree. `typecheck` locks its lane's SMT memo cache, which Sail rewrites at exit. `oracle` locks the shared oracle tree; `trace-diff` holds a shared lock while running its simulator, preventing sync or `--resync` from replacing live inputs. `corpus` writes images into its lane so separate lanes cannot overwrite one ELF path.

On first use, `build`, `emit` and `bundle` seed a lane before configuration. They copy riscv-tests only when it matches the manifest recorded during download verification ([THIRD-PARTY.md](../THIRD-PARTY.md#fetched-at-build-time)). They also copy the build, property-test, typecheck and `smt` memo caches. Caches are **copied, never shared**, because Sail rewrites them; `vos/cli/model.py`'s `_seed_smt_cache` implements this rule.

[vos/model_corpus.py](vos/model_corpus.py) owns the downloaded corpus's release
and digest readers, manifest verification, input selection and verified copying.
The model command selects donors and records build evidence using that library.

## Where a file lives, and which lane touches it

**A file sits on the side of the OS boundary whose tools read it most; explicit evidence exports and tracked generated artifacts may land in the checkout.** WSL mounts Windows drives under `/mnt/<drive>` and exposes the guest filesystem to Windows at `\\wsl.localhost\<distribution>`. Crossing that boundary pays a high per-file cost ([Microsoft's WSL filesystem guidance](https://learn.microsoft.com/en-us/windows/wsl/filesystems#file-storage-and-performance-across-file-systems)). Because the host edits and checks documents while the guest builds the model, elaborates RTL, and runs provers, the layout splits files across both filesystems; `run.py model lane` prints each lane path alongside its underlying filesystem.

| What | Where it sits | Who touches it, and from which side |
| --- | --- | --- |
| The checkout, and every lane under `.worktrees/` | The Windows filesystem, at the path the editor opens | The editor and the host gates, natively; the guest reads it across `/mnt/<drive>`, once per build, which is the one crossing the layout keeps |
| The Python environment | Windows: `out/venv-win32`; native Linux checkout: `out/venv-linux`; WSL reading a Windows checkout: `<lane_root>/venv-linux` | That checkout's `run.py` bootstrap, on the filesystem native to its interpreter |
| Build trees, fast trees, SMT memo caches, and the work directories of the bundle, oracle, seed, QuickChick, RTL and evidence loops | `/root/build`, in a `lane-<name>` directory per linked worktree | Guest loops only; no host tool opens them |
| Logs | `/root/logs`, the lane in the file name | Guest loops write them; a person reads them through `run.py model wait`, `run.py rtl wait` or `wsl -e cat`, never through a host tool pointed at the share |
| The opam switches, the pinned solver, ccache | `/root/.opam`, `/root/z3-<version>`, `/root/.ccache` | The guest toolchain |
| Proof staging, compiled `.vo`, audit scratch, lock and full `proofs/proof-evidence.json` | `<lane_root>/proof-gate/` | The proof gate, `proofs status` and `proofs export`, reached through the guest hop; source identities still bind the original checkout |
| Portable [proof receipt](../proofs/proof-evidence.json) | `proofs/proof-evidence.json` in the checkout, tracked by Git | Successful proof runs and `proofs export` publish it atomically; `proofs export --check` compares it with the native run |
| Exported evidence in `out/evidence/` and tracked generated artifacts | Inside the checkout | The evidence exporter and artifact generators; host readers consume their explicit outputs |
| Disposable agent scripts, probes, notes, captures and commit messages | A unique session directory under the system temporary directory, outside repositories and worktrees | The agent's host tools; native diagnostics use an explicit absolute temporary working directory |

On Windows, obtain the temporary root with `[System.IO.Path]::GetTempPath()`.
Preserve inherited system and profile environment variables; isolate only child
`TEMP` and `TMP` when needed. For COM activation, set both the PowerShell location
and `[Environment]::CurrentDirectory` to the temporary directory and restore both
in `finally`. Resolve output paths before launching and reject relative paths or
unexpanded `%NAME%` tokens. A literal `%SystemDrive%` or `ProgramData/Microsoft/Windows/Caches`
tree in a checkout is a launch error to correct, not an artifact to ignore.

The per-file crossing costs recorded in [vos/env.py](vos/env.py) explain the split: CMake configure over `/mnt/c` takes ~17 s versus ~1 s on ext4; `git status` from the guest takes ~3.2 s versus ~0.14 s on the host; and `tools/check.py` on the host takes ~1 s over NTFS versus 11–18 s over `\\wsl.localhost` (which is why I1 declined moving the checkout to ext4). Only a developer working entirely inside the guest (`Remote-WSL`) would place the checkout on ext4 as well.

Operational rules that follow from the placement table:

- **Create lanes from the host.** `run.py worktree create` uses Windows Git on the Windows filesystem. Never place a checkout on `\\wsl.localhost` (host Git rejects it without `safe.directory`, and `check.py` pays the 9P mount penalty on every run).
- **Dispatch guest work through `run.py`.** `python tools/run.py <command>` on the host hops into WSL with the checkout as the working directory, reading sources across `/mnt/` and writing outputs under the lane's native `lane_root` (printed by `run.py worktree create --json`). Inside the guest, run `python3 tools/run.py <command>`.
- **Keep guest build products on native ext4, never on `/mnt/` or `/tmp`.** Pointing `VOS_BUILD_ROOT` or `VOS_LOG_DIR` under `/mnt/` forces every write across the 9P mount, and `/tmp` is wiped when WSL idle-terminates. `run.py provision` probes both roots and fails if either sits on `/mnt/` or tmpfs.
- **Run repository queries on the host.** `git status`, recursive searches, and directory walks over `/mnt/c` take seconds from WSL; guest tools invoke `git` only where a build requires it (`git describe` at configure and `git ls-files` for receipts).
- **Only designated commands write into the checkout.** `seed properties` mutates `model/` in place under exclusive checkout ownership; `model bundle` writes the tracked bundle; and successful proof runs or `proofs export` publish the portable receipt.
- **Respect case sensitivity across filesystems.** NTFS is case-insensitive while ext4 is case-sensitive, so lane names are lowercased on creation and [.gitignore](../.gitignore) excludes `.Codex` and `.codex` separately.

## The lane as a fact list, and what no provisioner reaches

[run.py provision](vos/cli/provision.py) checks the toolchain and lane layout. Its `FACTS` table declares each dependency's consumer, source of truth, probe and optional installation command. It covers opam switches, the pinned solver and checkers, Python, distribution packages, per-lane memo caches and native guest output placement. **Versions and switch names come from their defining artifacts**, and [pyproject.toml](pyproject.toml)'s `requires-python` owns the supported Python minor. Historical completion records retain their original measurements. The [opam snapshots](opam/README.md) record complete package resolutions, including the lowering experiment's separate switch and [installation recipe](bedrock2-lowering/README.md).

The prover and model toolchains build natively in the guest. WSL Containers (`wslc`) are declined without a revisit condition: they retain the Windows-filesystem crossing described in the [placement table](#where-a-file-lives-and-which-lane-touches-it), and would introduce an environment absent from Guest CI. The [M1.5 completion record](../docs/implementation/completion-log.md#m15-run-the-certicoq-to-wasm-oracle) records that decision.

Python and uv must already be installed. The runner synchronizes locked Python packages before provisioning, so those rows need no separate recipes. `--apply` executes only declared commands. It cannot replace its own interpreter; cache isolation requires separate copies, not deletion of a warm cache.

`run.py provision --install-opam` uses the verified installation and root-creation routes in [vos/opam_client.py](vos/opam_client.py). It installs the reviewed client only when none is on `PATH` and doing so cannot upgrade an older root. It creates a missing root before switch recipes run. Earlier rows install the required distribution packages; if any prerequisite remains missing, root creation names it and refuses before installation.

The command never replaces an installed client. It modifies an existing root only when it matches a partially completed creation route: the root must use the reviewed format, contain exactly an initial sequence of the route's repositories at their declared URLs, retain the first repository's metadata stamp, and leave at least one required repository unfetched. Completion runs only the remaining steps; it skips `opam init`, which would rewrite shell setup.

Other client/root problems are reported without a repair plan: a different client release; a missing client over an older root; or a root with no format, a newer format, a required repository missing or at the wrong URL, or missing repository metadata. Switch installation is also blocked by a different client release or an older root format. The reviewed client can irreversibly upgrade an older root on its first write, or even its first read when an in-memory upgrade is insufficient, so that migration requires a deliberate step.

[Guest CI bootstrap](ci/README.md) uses the same route to create an isolated opam root and install the Sail and proof snapshots with native prerequisites. The experimental CertiRocq oracle switch has a separate manual [recipe](wasm-oracle/README.md).

The report lists two external settings as **not reached**: WSL2 memory reclamation, configured per user across distributions, and whether editing happens on the host or in the guest. Neither affects the verdict. [vos/env.py](vos/env.py) uses the same boundary for the idle timer.

## The three generators, and what each answers

Validation is generated wherever an oracle exists. The three standing instruments
below cover model inputs, mutation sensitivity and Gallina inputs; their owning
findings explain the blind spots each addresses.

| Generator | The finding it answers | What it does |
| --- | --- | --- |
| [run.py oracle](vos/cli/oracle.py) | **M0.12**: its corpus found an encoding defect that `$[test]` harnesses cannot reach because `$[test]` calls `execute` on an already-decoded AST and never decodes raw instruction words | Reads a JSON spec naming model sources and an input domain, emits and compiles a Sail harness, and runs it over the domain |
| [run.py seed](vos/cli/seed.py) | **M0.8d**: a hand-written property never ran because the test harness executed alphabetically and an earlier failure aborted the binary first | Applies systematic mutation operators across Sail or Gallina sources and checks that an oracle detects each live mutant |
| [run.py quickchick](vos/cli/quickchick.py) | **M0.8d** (in Gallina): known-answer vectors caught two transcription defects that had no corresponding structural property | Exercises Gallina definitions via exhaustive enumeration in the proof switch and seeded QuickChick random testing in the QuickChick switch |

Every mutant run classifies each mutant into one of four disjoint verdicts via [seeded.py](vos/seeded.py):

- **Stillborn:** Failed to compile; the oracle never ran, so nothing is decided about oracle sensitivity. Stillborn mutants are excluded from the live denominator so they cannot inflate mutation scores.
- **Killed:** Compiled and changed the oracle's verdict (or raised an uncaught runtime exception in a QuickChick set that passed at baseline).
- **Survived:** Compiled and left the oracle's verdict unchanged. This is a finding: the oracle does not cover the mutated site.
- **Undecided:** A Gallina compile or QuickChick execution hit a per-file timeout, died on a signal (such as OOM), or terminated with an unclassifiable runner status. Undecided mutants are journaled with their cause and fail the run because the population was not fully decided.

**A killed population tests the theorem statements, not whether definitions match the register.** Killing every mutant shows that the file's theorems constrain its definitions, but an artifact can achieve a 100% mutation score and pass the proof gate while still resolving an open register question by fiat or encoding a stronger assumption than the register warrants. During proof review, check each cited entry against the register for three common defects: numeric literals not fixed by any requirement, definition shapes that over-constrain open choices (such as a queue where the register specifies only readiness, or a total function where the register admits refusal), and bounds stated as equalities.

**[run.py selftest](vos/cli/selftest.py) reuses [seeded.py](vos/seeded.py)'s vocabulary for authored checker mutants.** Because checker mutants are authored per rule in `check-registry.json` rather than generated from source syntax, a mutation whose target text no longer exists in the corpus is reported as **unseeded** (a failing verdict) rather than stillborn. Table-driven rules such as K-88 should carry a mutant case for each distinct reader row so newly added rows cannot pass unexercised.

`seed`'s three subcommands reflect their compilation cost: `seed coq` runs the prover on a Gallina file, `seed sail` compiles a small subset of Sail files for an oracle spec, and `seed properties` re-emits and recompiles the full C simulator. **`run.py seed properties` temporarily mutates `model/` in place**, verifying byte-for-byte restoration after each mutant and rebuilding the lane's build tree before exiting. **Nothing else may read or write the checkout while `seed properties` runs**, or concurrent `git add`, `check.py`, or `selftest` invocations will observe a mutated `model/` tree.

## Model build inputs

The upstream-derived model keeps CMake and Ninja. The supported CMake floor lives
in [the model project](../model/CMakeLists.txt); provisioning reads that owner.
The shared [configure recipe](vos/cli/model.py) selects the native lane, build
profile, Sail executable and dependency inputs, and disables CMake package
registries. The optional static-library experiment uses the same recipe.

```console
python tools/run.py model dependencies
python tools/run.py model build --offline
python tools/run.py model dependencies --offline
```

`model dependencies` acquires missing pinned inputs and materializes them on the
guest's native filesystem without configuring or compiling the model. `--fast`
selects the iterate tree. Ordinary configure-based model commands perform the
same preparation automatically. `--offline` on `build`, `emit`, `rocq`, `simulator`
or `dependencies`, or `VOS_MODEL_OFFLINE=1`, requires inputs already available;
`VOS_MODEL_OFFLINE=0` permits acquisition and any other value refuses.
Build profiles and fresh focused outputs share the lane's authenticated archive
cache. Offline preparation can materialize absent derived trees from those archives;
it refuses a missing archive or an existing tree whose contents changed.

[The acquisition helper](vos/model_dependencies.py) reads URLs and archive hashes
from the existing model declarations, verifies archive bytes and compares each
materialized source population with the authenticated archive. Corrupt or
substituted inputs refuse rather than being silently repaired. Archive extraction
rejects escaping paths and special files. Safe archive-internal directory aliases
are materialized as ordinary directory copies; no filesystem links are installed.
Preparation supplies verified source overrides and disconnected settings to CMake.
Configuration refuses a missing or invalid offline suite before deleting or
fetching anything. Acquisition is the network-using phase; these settings do not
enforce OS-level network isolation on arbitrary upstream build code.

[The generation graph](../model/cmake/sail_toolchain.cmake) hashes the selected
Sail executable, installed library and plugin population and selected solver at
build time. A changed identity invalidates generated outputs even when input
timestamps are preserved; an unchanged identity preserves incremental reuse.
The Python configure recipe also binds the native plugin enumeration order into
that identity and rechecks installed generator inputs when consuming receipts.
Standalone CMake checks the sorted file population; accepted model evidence uses
the Python recipe's stronger loader binding.
Completion stamps are published only after successful generation. The canonical
Rocq command additionally forces a new emission for its run-specific receipt.

[Native input evidence](vos/native_build.py) records CMake's actual compiler and
tool selections, compiler support files, used native source/header population and
linked runtime libraries. A previous native population that changed, or existing
objects without that evidence, requires cleaning before reuse. Successful model
receipts bind this closure and later consumption revalidates its membership and
bytes. Missing inputs or changes during the observed build interval refuse the
receipt. These checks improve freshness and provenance; they do not establish an
independent bit-for-bit rebuild, constrain every OS input or discharge the checker
bootstrap's diverse-compilation obligation.

Model receipts derive their local Python implementation from the launcher's and
selected model command's transitive imports through
[the shared dependency reader](vos/python_dependencies.py). The
[model receipt owner](vos/cli/model.py) separately declares consumed data,
toolchain locks and gitlinks. Unrelated tool modules and generated proof views
do not join that identity. A later unrelated commit does not invalidate unchanged
build inputs: the observed build revision remains provenance beside the reuse
identity, and artifact hashes retain the actual built bytes and version stamp.

## Worktree isolation during fan-out

Apply the [shared isolation and ownership rules](../AGENTS.md#worktree-isolation-and-ownership)
to every worker. The procedure below owns provisioning, verification and handoff
of those dedicated worktrees.

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
input revision, and from the host, where Windows git writes the Windows filesystem the
lane sits on: see [where a file lives](#where-a-file-lives-and-which-lane-touches-it).
Uncommitted integration changes are not part of that revision; land the needed input
first or explicitly transfer and record the intended changes.

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

For the contained compiler, pass `--repo <absolute-checkout>` to `worktree create`,
`list` or `verify`. The same isolation checks apply inside that repository: its
primary checkout must ignore `/.worktrees/`, its symbolic base resolves there,
and its lane stays under its own `.worktrees/`. This keeps compiler sources inside
their licensed repository. Omitting `--repo` selects the invoking VerifiedOS
checkout; an invalid explicit path refuses rather than falling back to it.

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
owned files, focused checks and integrator, and for guest work the lane's guest output
directory as `worktree create --json` reports it in `lane_root`. The worker verifies its checkout with
`git -C <worktree> rev-parse --show-toplevel` before starting. All repository reads,
edits, checks, staging and commits target that checkout: set the shell's working
directory on every call, use `git -C <worktree>`, and use absolute paths rooted there
for file tools and scripted writes. A previous `Set-Location` is not a guarantee
about the next tool call's directory. Build and log outputs use that checkout's lane,
which [the lane derivation](vos/proofenv.py) derives from Git's administrative identity,
and sit on the guest's own filesystem under `/root/build/lane-<name>` and `/root/logs`,
never in the checkout.
Coordinate shared mutable toolchain state separately. Report an accidental write
outside the lane to the integrator, who resolves ownership before integration.
If isolation cannot be established, keep the worker undispatched. Nested fan-outs
follow the same procedure, with a distinct checkout per child.

After the workers stop, complete local integration and retirement through
[`run.py fanout`](fanout.md#usage). Its [completion contract](fanout.md#required-behavior)
owns handoff freezing, revision-bound recommendations, output retention, retirement checks
and resumable refusals. Follow the [shared validation handoff](../AGENTS.md#tool-execution-and-validation)
for the settled batch.

## Check scheduling during fan-out

**One integrator schedules validation for each stable integration batch.** A batch
is the set of lane outputs being accepted together on one settled tree. Prepare
each brief under [the worktree handoff procedure](#worktree-isolation-during-fan-out),
including its focused and deferred integration checks.
Read-only scouts inspect sources in their own worktrees without running gates.
Workers check a coherent change when the result can guide their next edit; they
do not run the complete wave after every file, tool call or handoff. In the
integration checkout, the integrator combines overlapping check requests and
reserves a quiet tree for their readers.

| Changed surface | Feedback during lane work |
| --- | --- |
| Documents and cross-artifact facts | `python tools/run.py check` (or `python tools/check.py`) after a coherent edit batch. It checks the whole corpus; there is no file or rule filter. |
| A checker rule | `python tools/run.py selftest --rule K-110`, substituting the changed rule, once the whole checker baseline is clean. This supplies only the selected rule's mutation evidence. |
| Tool behavior | `python tools/run.py test --only gate`, substituting a module-name substring for the affected tests. |
| Python sources or checker configuration | `python tools/run.py typecheck` after a coherent batch when feedback is needed before integration. It checks all tools; there is no path filter. |
| Model, RTL or proofs | Use focused candidate checks when needed for debugging. Record the affected Guest CI lanes for the user under the [change-selection policy](ci/README.md#change-selection); retain separate checks for requirements outside its contract. |

Before the readers start, `python tools/run.py prepare python --path FILE` applies
locked import ordering to explicitly selected Python files; repeat `--path` as needed.
`prepare model --path FILE` runs the pinned hooks on selected authored model files
through the guest. Both commands use the same settings as CI, require no model or
proof build, and leave their selected diffs for review. Preparation supplies no gate
verdict; the existing typecheck and hosted validation remain required.

Use the existing verdict for unchanged inputs. If a checker run already reports
arithmetic drift, invalid instructions or owed co-reads, resolve those findings
before running a selftest: its baseline runs the whole checker even under `--rule`,
and a failed baseline supplies no mutation verdict. Workers report deferred repair
and checks explicitly. They do not run `--fix` or bare `run.py`. Local builds and
focused checks are allowed; record their reason, scope and verdict. Complete host
and guest/proof suites and all benchmarks run only on GitHub Actions, including
during a hosted-service outage. Use focused selections to investigate a specific
issue; do not reconstruct a full suite by batching selections.

**Budget workers across the machine.** The full runner already parallelizes its
gates; selftest, behavioral tests and typecheck also run internal workers. Reserve
complete host and guest/proof suites for GitHub Actions, which supplies both final
verdicts. Budget any necessary local debugging or checks outside the workflows
against the same CPU and memory limits. Focused checks
may overlap on independent stable inputs when capacity permits; `selftest --jobs N`
and `test --jobs N` bound their command's workers, not the whole gate. Default selftest
sandboxes are private; never share an explicit `--sandbox` directory between live runs. Builds,
proofs and oracle runs retain their own output ownership and locking rules.

The integrator closes the batch in this order:

1. Join the lane outputs, resolve shared edits, read the affected prose, and record
   required co-read judgments. Inspect `git status --short --untracked-files=all`
   and each intended diff; track new deliverables by path so the checker sees them.
   Finish generated artifacts and other writes before gate readers start. Keep the
   validated checkout stable until its readers finish.
2. Resolve known findings cheaply. Use `python tools/run.py check --fix` for
   arithmetic repair alone when more editing or co-reading remains. Repair once
   after the batch's authored inputs settle; repeat only if new input changes or
   findings require it. An intermediate merge needs a targeted check only when its
   answer affects the next integration decision.
3. Complete the [validation handoff](../AGENTS.md#tool-execution-and-validation).
   Required experiments and measurements outside the [Guest CI contract](ci/README.md)
   retain their separate acceptance checks.
4. Reuse evidence for unchanged inputs. Refresh affected evidence when later edits
   invalidate it; record the need for user-managed hosted validation for a new batch
   or when the affected scope cannot be established. A selected-rule selftest establishes only its
   selected mutants' results.

These scheduling rules do not replace the [landing tiers](../PLAN.md#checklist-conventions)
or item acceptance predicates. `seed properties` owns its checkout exclusively
against every other reader and writer for the whole run.

## Checking the tools themselves

Performance changes follow the [tool performance acceptance](performance.md):
measure equivalent work, preserve failure behavior, and share parsed owner facts
within an explicit input snapshot rather than caching decisions by path.

[check.py](check.py) validates the repository documents, and [run.py selftest](vos/cli/selftest.py)
tests the checker against seeded mutants. To validate the Python tooling itself,
[run.py typecheck](vos/cli/typecheck.py) enforces static typing and lint rules across
both platforms, and [run.py test](vos/cli/test.py) runs the behavioral test suite.

A bare `run.py` first validates the shared instructions and restores a missing
import, then runs `check`, `selftest`, `typecheck` and `markdown` in parallel. Their reports are collected in a fixed order
and produce one exit code. `--tests` adds the behavioral suite; `--check --tests`
is the same complete validation without tracked writes. CI partitions that work
with `--shard INDEX/TOTAL` using the workflow's platform-specific counts, runs the rest
with `--unpartitioned` in a job of its own on each OS, and requires every selected
job. For prose-only changes, [change selection](ci/README.md#change-selection)
instead runs `check` and `markdown` on both operating systems without allocating
mutation or behavioral shards or running typecheck. Model hooks run only when
their inputs are affected. Both platform aggregates remain mandatory and reject
unexpected skips as well as failures. `--rule` and `--only` cannot narrow a shard, and a
partition count larger than its mutation or module population is refused.

`--fix` validates instructions, restores a missing import and repairs derived
artifacts before starting the readers. The checker runs again afterward, so a
repaired finding does not leave a stale failure as the final verdict. An invalid
instruction entry point or crashed repair stops before the validation wave.

The selftest copies the working tree into its sandboxes, so mutations finish before
it starts. Each sandbox runs the generated-artifact checks too: a generator's cost
is multiplied by the mutant population. Keep generators small and measure them
before adding work to every gate run.

Tooling consolidation preserves each consumer's complete input population and
acceptance decisions. The [retirement plan](../PLAN.md#coverage-preserving-tooling-retirement)
tracks qualified replacements and conditional workarounds. Shared generation and
parsing belong in libraries; the independent model/RTL comparison, assumption
audit, recursive kernel check and checker mutation controls retain their own
verdicts. Optional integrations earn a change of default through their existing
qualification and equivalent-work measurements.

Holder-citation and landing-declaration mutants select their targets by document
structure, so completion prose can change without maintaining test literals.
After changing those declarations, `python tools/run.py selftest --rule K-84`
checks the affected controls; a missing seed remains a failure. See the
[CI failure-prevention contract](ci/failure-prevention.md#generated-behavioral-checks).

| Checker | What it decides |
| --- | --- |
| [ty](https://github.com/astral-sh/ty) | Type-checks every expression reachable under `--python-platform linux` and `--python-platform win32` with all rules at error severity |
| [ruff](https://github.com/astral-sh/ruff) | Enforces complete function type annotations (`ANN`) and the lint rules enabled in [ruff.toml](ruff.toml) |

Both tools are required because `ty` infers types without requiring function signatures
to be annotated, whereas Ruff's `ANN` rules enforce annotation coverage. Both are pinned
to exact versions in [pyproject.toml](pyproject.toml)'s `dev` dependency group; version
mismatches fail the gate.

Runtime dependencies (JSON Schema validation, CommonMark parsing, file locking) and
development tools share a single cross-platform resolution in [uv.lock](uv.lock).
Workflow and hook pin readers use [vos/yamlutil.py](vos/yamlutil.py) (backed by locked
`ruamel.yaml`) to parse YAML AST nodes with source locations while rejecting duplicate keys,
aliases, merge keys, and nonstandard tags. Structured entries in
[development-tools.json](development-tools.json) (validated by
[development-tools.schema.json](development-tools.schema.json)) own development-tool
license editions, owner references, and generated rows in
[THIRD-PARTY.md](../THIRD-PARTY.md). K-118 verifies workflow and hook membership,
source-literal tool versions (including Verilator's `assign` binding), and generated
display bytes; if an upstream pin moves past its recorded license review, `--fix`
refuses repair until the new license reading is recorded.

The ring emitter uses a cached JSON Schema validator to check declaration shapes
before exposing typed records; fields outside the emitter's scope remain intact.
[run.py typecheck](vos/cli/typecheck.py) reads the pins from the manifest, runs only
the environment's executables, and explicitly gives ty that environment's Python.
The launcher's `uv run --locked --exact` refuses stale resolution before dispatch.
Global checker shims and an unrelated activated environment cannot select different tools.

The [checker registry](check-registry.schema.json),
[work-order data](../docs/implementation/work-order.schema.json) and calibration
[owner](../interfaces/calibration-owner.schema.json) and
[field declarations](../interfaces/calibration-field.schema.json),
[device-register declarations](../interfaces/device-registers.schema.json) and
[wire-format inventory](../interfaces/wire-formats.schema.json) also have authored
schemas. Their readers validate structure through [vos/schema.py](vos/schema.py),
then decide semantic relationships against live owners. VS Code's
[schema associations](../.vscode/settings.json) use those same files. Duplicate
JSON keys remain errors. Calibration digest lengths require actual integers;
integral floats and booleans cannot stand in for byte counts. Generated views
remain products of their existing owners.

Ordinary local links and fragments use the pinned offline
[Lychee adapter](vos/lychee.py). It reads the indexed corpus explicitly, validates
headings and declared anchors, and accepts a tracked submodule root without fetching
its contents. Its archive and executable hashes are verified in the managed Python
environment, shared by mutation subprocesses. Cold installation has one process
owner through archive extraction and executable publication; waiting consumers
recheck the pinned executable after acquiring the installation lock.
The lock path stays present, and unsupported native locking refuses, preserving
the retirement tool's ability to exclude a live producer.
Corrupt cached bytes remain a finding.
It does not contact external links.

The Python project lives in `tools/`. From the repository root, add a dependency
with `uv add --project tools --no-sync PACKAGE`, or edit the manifest and run
`uv lock --project tools`. After changing pins, run
the Windows and Linux gates. Review and commit the manifest and lockfile together.
To refresh resolution within the declared constraints and the
[release cooldown](#running-them), use `uv lock --project tools --upgrade`. The
cooldown binds the dependency groups' exact `==` pins too: a pin to a release
uploaded within the cooldown does not resolve, and uv reports the requirement
unsatisfiable because the release was published after the cutoff. Move such a pin
once its release has aged past the cooldown, and never by adding an
`exclude-newer-package` entry, which is reserved for the releases grandfathered when
the cooldown was adopted. Normal commands synchronize each checkout on its next
invocation, so no manual reinstall window exists across worktrees or OSes.

The manifest sets `no-build = true`, so uv installs published wheels only and
refuses a package that would need a source build instead of running its build
backend or requiring a compiler. The project itself is virtual and is never
built. Each locked package therefore needs a wheel CPython 3.14 can install
(pure-Python, `py3-none` for the platform, or `cp314`) on every platform that
synchronizes it: Windows ARM64 on the development host, Linux aarch64 in its WSL
guest, and Windows x64 and Linux x86_64 on the CI runners.
The x64 runners cannot reveal a missing ARM64 wheel, Windows or Linux, so read a new
dependency's wheel list in [uv.lock](uv.lock) before committing it. Only requested
groups are installed, so a non-default group without one platform's wheel is
refused on that platform alone and the default synchronization is unaffected.

The optional `model` group pins the `prek` runner used by the curated model's
hook configuration. Set `UV_PROJECT_ENVIRONMENT` to the environment in the placement
table above, then run `uv run --project tools --locked --group model prek --version`.
For a WSL-mounted checkout, `run.py model lane` supplies the guest lane root.
The gate step itself synchronizes only the default dependency groups, and
[uv.lock](uv.lock) is one resolution covering every group, so each `run.py`
bootstrap's `uv run --locked` refuses a lockfile the manifest would change. Host CI's
model-hooks job synchronizes the group alone and runs it, as
[the model's hooks](#model-hooks) describe, which checks that it installs and runs on
Linux x86_64; no gate installs it on Windows or on either ARM64 platform.
`uv sync --project tools --locked --group model --dry-run` lists what a
synchronization would install without installing it.

The optional `workflows` group pins zizmor, which Host CI syncs alone into an
environment of its own; [workflow analysis](#workflow-analysis) gives the command.
PyPI publishes no Windows ARM64 wheel for it, so run it on Linux.

<a id="model-hooks"></a>**Host CI runs the curated model's pre-commit hooks with `prek`, except the external link check.** Because `prek` runs from the repository root, [model/.pre-commit-config.yaml](../model/.pre-commit-config.yaml) scopes all hooks to `files: "^model/"`, excludes `model/dependencies/`, and passes `model/.typos.toml` and `model/.markdown-link-check.config`. Each remote hook repository is pinned to a full commit SHA with a `# frozen:` tag comment and a matching development-tools entry in [THIRD-PARTY.md](../THIRD-PARTY.md) checked by K-118 (`git ls-remote` verifies tag-to-commit correspondence during review). `prek` executes all six hooks in `pre-commit/pre-commit-hooks` (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `check-executables-have-shebangs`, `check-shebang-scripts-are-executable`) and `forbid-tabs` (`repo: builtin`, `id: deny-pattern`) in-process on its built-in Rust fast path without creating a Python hook environment. The `model-hooks` job in [Host CI](../.github/workflows/host-gates.yml) runs `--all-files --show-diff-on-failure` with `SKIP=markdown-link-check` (avoiding network fetches for external URLs) and pins hook dependencies as described [below](#model-hook-dependencies). To run the hooks locally from the checkout root, set `SKIP=markdown-link-check`, `PREK_HOME`, `PREK_UV_SOURCE=none`, `UV_PYTHON_DOWNLOADS=never`, and the `uv` constraint variables (using absolute paths), then run `uv run --project tools --locked --group model prek run --config model/.pre-commit-config.yaml --all-files` (or use `python tools/run.py prepare model --path <path>` for selected files). Because fixing hooks (`trailing-whitespace`, `end-of-file-fixer`, `clang-format`, `prettier`) modify files in place, inspect `git diff -- model` afterward. Never run `prek install` or `pre-commit install` (despite upstream's [model/CONTRIBUTING.md](../model/CONTRIBUTING.md)): it installs a shared Git hook across all worktrees that binds one OS's runner, fails commits when fixing hooks rewrite staged files, and fetches external links on every staged Markdown file.

<a id="model-hook-dependencies"></a>**Model hook Python dependencies are pinned via `uv` constraint files.** With `PREK_UV_SOURCE=none`, `prek` installs each Python hook with the locked `uv` on `PATH` inside an isolated environment:

- **Runtime constraints ([model-hooks-constraints.txt](ci/model-hooks-constraints.txt), `UV_CONSTRAINT`):** Pins runtime dependencies installed alongside Python hooks (`clang-format`, `typos`) with wheel `--hash=sha256:` digests for Linux `x86_64` and `aarch64`, which `uv pip install` verifies while still building each hook's local clone.
- **Build constraints ([model-hooks-build-constraints.txt](ci/model-hooks-build-constraints.txt), `UV_BUILD_CONSTRAINT`):** Pins the isolated PEP 517 build backend (`setuptools`) with its wheel `--hash=sha256:` digest.
- **Cooldown and review:** Host CI passes both files by absolute path along with `UV_EXCLUDE_NEWER="3 days"` (enforcing the [3-day release cooldown](#running-them)), `PREK_UV_SOURCE=none`, and `UV_PYTHON_DOWNLOADS=never`. `prettier` is fetched by npm using the version and registry integrity hash from its hook mirror. Review both constraint files whenever a hook revision or the locked `uv` version changes. K-118 parses both files using pip's line-continuation and comment rules, requires every line to be a strict `<name>==<release>` pin (with optional `--hash=sha256:` digests and no pip flags, markers, extras, or URLs), and verifies that each pinned version matches its license entry in [THIRD-PARTY.md](../THIRD-PARTY.md).

[ty.toml](ty.toml) enables every ty rule at error. Its admitted tables, exact
values and keys are declared in [the configuration schema](ty-config.schema.json);
[Ruff's schema](ruff-config.schema.json) declares its admitted settings. The
[typecheck command](vos/cli/typecheck.py) decodes TOML and delegates structural
policy to [the shared strict JSON Schema validator](vos/schema.py). Missing,
malformed or policy-violating configuration and schema files are findings. The
schemas refuse per-file suppression settings and changes to ty's required
coverage and import-resolution tables, including unreviewed top-level ty keys
and diagnostic baselines. Schema findings
carry configuration paths and remain visible beside each tool's verdict.

Both TOML files carry a local schema directive for editors supporting
[Taplo's schema directives](https://taplo.tamasfe.dev/configuration/directives.html).
To prevent ambient environment overrides, `run.py typecheck` fails if a user-level `ty.toml` (`%APPDATA%\ty\ty.toml` on Windows or `$XDG_CONFIG_HOME/ty/ty.toml` / `~/.config/ty/ty.toml` on Linux/macOS) or `PYTHONPATH` is present, and clears `TY_LOG` and `TY_LOG_PROFILE` before invoking `ty`. Excluded Ruff rules must be documented in [ruff.toml](ruff.toml). Line-specific suppressions must name a specific rule and rationale; blanket `# noqa` and `# type: ignore` comments are rejected by Ruff's `PGH` rules, and `typecheck` additionally rejects file-wide or multi-line suppressions (`# ruff: noqa` except for `N999`, `# flake8: noqa`, `# ruff: file-ignore[...]`, `# ruff: disable[...]` / `enable[...]`, and `isort` action comments). Single-line `# ruff: ignore[...]` and trailing `# noqa: <RULE>` comments remain allowed.

The gate passes every indexed Python source under `tools/` directly to both ty
platform runs and to Ruff. Bounded filename batches respect Windows command-line
limits, and missing source files refuse before dispatch. Ruff receives
`--no-force-exclude`; explicit targets bypass the tools' directory and ignore-file
discovery. No diagnostic debug log supplies coverage evidence.

[pyproject.toml](pyproject.toml)'s `requires-python` owns the supported minor.
Workflow setup reads that file, provisioning and guest bootstrap use the shared
[manifest reader](vos/pyversion.py), and explicit-config checker and preparation
commands receive targets derived from it. Editors infer their targets from the same
manifest. A malformed or multi-minor constraint refuses instead of selecting a default.

`python tools/run.py markdown` checks table syntax with the pinned
[rumdl adapter](vos/markdownlint.py) implementation of MD055 and MD056 using
[.rumdl.toml](../.rumdl.toml). Its archive and executable hashes are verified in
the managed Python environment under a serialized installation lock, and its
NUL-framed `--stdin-batch` input lints the indexed Markdown population without
temporary document trees. Only MD055 and MD056 run, and inline document comments
cannot disable them. This mandatory
host-wave member runs once in each unpartitioned CI job, outside semantic-rule
mutation replay. K-39 retains the separate check for pipe-led text with no table
separator, which a standard Markdown table rule does not recognize.

Because `ty` discovers configuration upward from its working directory and the repository root has no `ty.toml`, open `tools/` as a workspace folder in VS Code and select the checkout's managed interpreter (`out/venv-win32/Scripts/python.exe` on Windows or `<lane_root>/venv-linux/bin/python` in WSL) so editor diagnostics match the gate. `run.py typecheck` runs `ty` twice—once with `--python-platform linux` and once with `--python-platform win32`—so platform-guarded branches on both OSes are typechecked. Because typeshed stubs OS-specific standard-library modules (such as `fcntl` and `msvcrt`) on all platforms, `ruff.toml`'s `banned-module-level-imports` (`TID253`) and `typecheck`'s AST guard ban all imports of OS-specific standard-library modules outside function bodies; [tests/test_typecheck.py](tests/test_typecheck.py) verifies that ban list against the running interpreter's importable standard library on both Windows and Linux. OS-specific modules must be imported inside the functions that use them, behind a `sys.platform` check.

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

Keep a cleanup inventory and its retention reasons in the session's temporary directory.
Use explicit paths beneath the inspected `out/` root, recheck them before deletion,
and do not follow links into other directories. Worktree retirement remains the
separate [owned-lane procedure](#worktree-isolation-during-fan-out).

## Current evidence and generated documentation

A model build records the selected source bytes and git revision, tool executable hashes,
build options, output artifacts, stage exits and test-log digest. The revision excludes
Git's repository-wide dirty flag; the input manifest binds working bytes, so publishing
the proof receipt does not invalidate the model build. The evidence sweep
checks that record before and after consuming the model and holds the build lock while
it runs. After all members finish it revalidates and embeds the proof receipt, including
compiled output hashes. It also binds the device-tree compiler's identity. Its JSON
output identifies one execution; a missing result, a failed process
or an input change prevents successful measurements from being published. These records
identify evidence and do not certify a translation or replace the proof kernel.

`model bundle` relocates the selected Sail switch's absolute library hash keys to
the canonical prefix in [vos/sailbundle.py](vos/sailbundle.py), then writes compact
UTF-8 JSON. Source text, locations and digests remain intact. Regeneration and
`model bundle --check` use the same transformation; an unrelated library root is
refused, and changed library bytes still fail comparison. Regeneration publishes
atomically after successful emission and validation.

`proofs headers` reads the sources on either OS. `proofs status` takes the guest hop
on Windows, holds the proof workspace lock, and hashes staged sources and compiled
outputs in the native lane against the current original source inputs.
The proof receipt names the compiled constants, their types and audited assumptions,
the local dependency graph, source identities and compiled output identities. A claim
must resolve to an audited proposition. Matching metadata does not decide whether that
proposition expresses the English requirement; that remains the requirement-to-contract
review. Status checks freshness without invoking Rocq; the receipt records the prover
identity measured during the proof run.

The tracked [portable proof receipt](../proofs/proof-evidence.json) records the last
successful run's source, gate-input and compiled-object hashes, prover version and
executable hashes, module constant counts, dependencies, witnesses and timings.
It includes the SHA-256 of the complete native receipt and digests of each symbol
inventory and the cache context. Schema 2 also records the modules kernel-checked
in this run, the modules whose checked results were reused, and the prior native
receipt's SHA-256 when reuse contributed. Those JSON-value digests use UTF-8, sorted keys,
literal Unicode and comma/colon separators without whitespace. Guest executable and
library paths stay in the full native receipt, alongside the complete symbol types
and assumptions. The portable record is historical evidence, not a cache authority
or a claim that today's checkout has been rechecked.

`python tools/run.py proofs export` validates the recorded staged sources and compiled
objects, then publishes the portable receipt without compiling or invoking Rocq.
It retains the original input hashes even after gate or source edits. The full native
receipt is never rewritten by export. `proofs export --check` checks agreement with
that native run without writing; `proofs status` separately checks current inputs.
New successful runs, including cache hits, automatically publish the portable receipt.
Publication failure fails the command but preserves the native evidence, allowing an
export retry without a proof recheck. A failed proof run leaves the previous portable
receipt intact; its recorded input hashes still identify only the earlier run.

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
Proof compilation starts each module, within a bounded worker limit, once every module
it Requires has compiled and been audited, preserves report order, and does not compile
a dependent against a failed prerequisite's stale output.

Every source compiles under the gate's [pinned settings](vos/cli/proofs.py), and a
successful compile prints no diagnostic. Default-enabled warnings are errors, except
the notice for a `nat` literal above the unary threshold, whose only fix would change a
statement's type. The `!` goal selector refuses a tactic that would act on the first of
several unfocused goals. SProp is refused, which holds the
[checker profile's](../docs/assurance/cic-checker-qualification.md#the-published-profile-and-metatheory-decision)
exclusion of definitional proof irrelevance. A source that configures warnings, resets
a pinned setting or a kernel checking flag, sets `Indices Matter`, enables definitional
UIP or sets a wall-clock timeout or allocation limit is refused before compilation,
whatever control flags or attributes precede the command. The gate's own generated
queries open every interactive proof with `Proof`, whose absence Rocq 9.3 reports by
default as `missing-proof-command`.

The kernel recheck runs `rocqchk -o` and parses its stderr context summary:

- **Context summary audit:** The summary covers the entire loaded environment (including admitted modules) and must report no axiom outside the declared set and no `type-in-type`, unsafe `(co)fixpoint`, or assumed-positivity entries. Any axiom declared by a checked library (such as Stdlib's `Program` or `FunctionalExtensionality` closures) is refused even if unused. The summary ends with inductives that rely on `indices_matter=false` (including Corelib's `eq`), which the gate requires with qualified names and accepts under the checker profile.
- **Sealed modules under `-admit`:** `rocqchk` records which axioms a sealed module's hidden proofs use only while checking that module (`mod_checking.ml`: `check_structure_field`, `check_constant_declaration`, and `constants_of_opaques`). When an installed library is loaded under `-admit`, the fields of structure bodies sealed by a module type (such as in Stdlib's `PeanoNat` or Corelib's `ssrunder`) appear as body-less axioms. When a worker with admitted roots reports an undeclared installed-library axiom, the gate runs a shared load-only pass over those admitted roots alone; any name also reported by the load-only pass is covered by the peer worker or prior accepted run that recursively checked those roots. Proof-module axioms are never covered.
- **Algebraic and functor-sealed module fields:** Fields of algebraic module ascriptions (`Module M : T := N` or `Module M : T := F X`) and functor results sealed by their result signature have no body in `rocqchk` (and module aliases retain the aliased module's canonical names), so `rocqchk` lists them as axioms even when it checks the library. For any such installed-library name not explained by the load-only pass, the gate queries the compiler with `Print Assumptions` in the environment that `Require`s the worker's roots. The name is covered only when `Print Assumptions` reports `Closed under the global context` or lists only declared axioms; an admitted proof, `Axiom`, or `Parameter` under the seal—or a failed/missing query—fails the gate. Combining `rocqchk -o` with `Print Assumptions` also catches definitional UIP, which `rocqchk`'s summary omits.

The default run reuses compiled objects, native assumption audits and kernel verdicts
only from a successful native receipt with matching source bytes, compiled-object
hashes, dependency resolution, gate inputs and toolchain context. A changed source
or object invalidates its transitive dependents. Adding or removing a source retains
unaffected components; any change to a module's local dependency resolution invalidates
that module. A change to the gate's implementation invalidates all objects. That
implementation is every checkout module Python runs to import
[the gate](vos/cli/proofs.py), derived from their import statements, including imports
inside functions and parent packages. The launcher, the [command table](vos/commands.py)
and the Python lockfile choose and start the process without deciding anything in it;
the environment identity below covers the process they start, including the token the
tool environment derives from its manifest and lockfile. Register prose is
recorded in each receipt but does not invalidate native checks: annotations still
bind the exact proof source, K-109 holds its reference manifest, and semantic
agreement with a requirement remains a review obligation. Timestamps do not establish
freshness. Portable receipts alone never authorize reuse.

When the entire proof set is unchanged, the gate validates and reuses its previous
kernel evidence without rewriting the native receipt, and republishes the portable
receipt. The cache also hashes installed
library and runtime files discovered through the compiler configuration and actual
load paths, the checker library, the system libraries that `ldd` resolves for both
executables and every loadable plugin, and the environment (each variable's value
is recorded only as a digest; shell launch bookkeeping and WSL's per-launch interop
socket are excluded). Unknown load-path formats, directory symlinks, dynamic source/ML
loading, unsupported wrapped Require commands or an unresolved system library disable
reuse and parallel kernel checking. The first run after upgrading the gate needs a
full check to establish this identity. When an earlier receipt authorizes no reuse at
all, the gate prints why, naming the differing toolchain part, context entries or gate
modules but never their values. `proofs identity` prints the digest of the toolchain
and context that reuse requires, so a cache keyed by it offers only candidates with
an acceptable context; it authorizes nothing.
`proofs --fresh` forces all work; `--jobs N` bounds compilation, auditing and kernel
workers. Per-phase wall times and reused-object/audit counts are recorded in the
receipt and printed.

A module's compile and audit start once every module it Requires has finished both,
beside any other ready module within the worker limit. Among ready modules, the one
heading the longest chain of dependents starts first, then dependency-wave and name
order. A module whose prerequisite failed is reported blocked and never compiled. The
log gives each compiled module's start and end in seconds from the phase's start.
Beside the phase's wall seconds it gives the makespan of a wave schedule, in which
each dependency wave finishes before the next starts, replayed over those seconds at
the same worker limit, so a run is read against that schedule on its own machine.
A wrapped Require, which the dependency parse does not read, may name a module in
any wave, so a source holding one runs the phase as that wave schedule.

Without `--jobs`, each phase selects as many workers as the available logical CPUs
and its memory planning budget permit. The guest samples `MemAvailable` immediately
before compilation/auditing and again before kernel checking, after acquiring the
workspace lock. [The resource policy](vos/proofenv.py) owns the headroom, per-worker budgets
and conservative fallbacks when memory cannot be read. The compile/audit budget is an
estimate from the [recorded prover measurements](../docs/performance/toolchain-residency.md#the-prover-and-which-of-its-two-acts-the-device-performs).
The kernel budget is set at or above the peak resident memory of the one kernel worker
that checks every module on Guest CI's proofs runner, whose recorded runs and margin
`proof_jobs` states, so that 16 GB runner runs one kernel worker. Guest CI's
proof log records each run's peak single-process resident memory
([Guest CI contract](ci/README.md)). The selected limits are printed, each automatic one
beside the usable CPU count and the `MemAvailable` reading it was sized from. An explicit
`--jobs N` overrides automatic CPU/memory sizing for both phases; the single-process
fallback for an unknown library identity still applies.
Help, status, export and whole-set cache hits do not sample worker capacity.

Changed runs use Rocq's documented
[`-admit` incremental checking](https://rocq-prover.org/doc/V9.3.0/refman/practical-tools/coq-commands.html):
byte-validated, previously kernel-checked modules and their unchanged dependency
closures may skip repeated type checking. Every changed module must be an explicit
check target in one worker, which overrides admission in that worker. A target
overrides only its own admission: a library that an admitted root reaches stays
admitted inside a target's closure, so a component's changed modules are targets
together. A freshly
compiled empty joining module requires every current module, including disconnected
reused ones, so the checker still loads one joint environment and checks dependency
consistency. New external dependencies
are covered by recursive worker checks or a reused module's checked closure.
Cached object hashes are verified after staging, after compilation/auditing and after
the kernel pass; source and toolchain identities are verified again before publishing.
A failed run cannot publish new success evidence. When rebuilding with reusable modules,
the prior successful native receipt is retained only as private cache input. Unchanged
staged objects can be recovered on retry; no current receipt is published until the
whole run succeeds.
This follows the pinned checker's
[selection algorithm](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/checkLibrary.ml);
the native regressions exercise incremental success, incompatible objects,
contradictory universe constraints across separately valid libraries, an admitted
root that loads a sealed installed module, and a checked library whose alias-sealed
and functor-sealed fields the compiler's reading covers or, over an admitted
implementation or a genuine axiom, refuses.

The launcher groups changed modules by connected local dependency components and
distributes them within the selected kernel-worker limit. Components stay
together so their shared changed prerequisites are checked once. Compiled-object sizes
balance the batches and select the lightest batch to carry the complete joint
environment; sizes never authorize reuse. That worker type-checks its own targets
while also checking dependency identities and combined universe constraints for all
roots. It provisionally admits peer targets and their dependencies. Every peer
recursively checks its targets, admitting only previously validated reusable roots.
External dependencies can be checked by more than one worker.

The launcher verifies complete, disjoint target coverage before any worker starts.
A provisional admission supplies no reusable evidence: acceptance requires every
worker's context summary to pass the audit above plus unchanged object, source,
toolchain and library hashes.
The joint worker may finish first, but a peer failure still refuses the entire run.
The pinned checker's admission path still checks dependency identities and inserts
universe constraints through
[`Safe_typing.import`](https://github.com/rocq-prover/rocq/blob/V9.3.0/kernel/safe_typing.ml).
The launcher composes these verdicts over identical bytes; there is no separate
consistency pass after the workers finish.

`--fresh` checks all proof modules during the current run. `--jobs 1`, a single changed
component or an unavailable installed-library identity keeps the single-process path.
Whole-set cache hits still avoid invoking the kernel. The pinned tool's default kernel
conversion remains in use: enabling its bytecode compiler would also trust the
bytecode it compiles from the checked declarations and the VM that runs it, so that
option is left disabled. The pinned checker never reads the bytecode a `.vo` carries. The launcher supplies
parallelism; the checker itself offers no parallel worker option.

`placement consistency --plan demo_plan --max-candidates 64 --timeout 5` exercises
the finite consistency pilot. It uses the memory plan's candidate domains and existing
predicates, with other islands fixed. Its `sat`, `unsat` and `unknown` results concern
that declared grid, not arbitrary placements or all natural-language requirements.

## Agent instructions

[AGENTS.md](../AGENTS.md) owns shared agent rules; K-110 requires it to be a tracked,
nonempty UTF-8 regular file. Edit shared rules there. Personal preferences should
link to repository procedures instead of copying them. Existing worktrees retain
the instructions at their own revision; a new session loads changed instructions.

## Checked references in source comments

Write a local cross-reference as a Markdown link in a comment or Python docstring.
K-12 checks these alongside ordinary document links during `run.py check`.
The source scan covers Python, Gallina, Sail, C, C++ and SystemVerilog.
Paths are relative to the source file carrying the link and must name an indexed
file or a directory with indexed descendants; directory links have no fragment.
Use forward slashes and the exact filename case. Use a fragment when the
comment depends on a particular section or declaration:

```python
# In tools/vos/checks/links.py:
# [source reference validation](../source_refs.py#findings)
# [validation handoff](../../../AGENTS.md#tool-execution-and-validation)
```

```coq
(* In proofs/KernelInstance.v:
   [register restoration](PartitionContext.v#RestoresRegisters) *)
```

```systemverilog
// In rtl/vos_scalar_width_pkg.sv:
// [register conversion](../model/model/core/reg_type.sail#regval_into_reg)
```

Markdown fragments name headings or explicit anchors. Source fragments name a
Python declaration (including qualified class/member names), a Gallina declaration
supported by the shared source-name reader, or a Sail declaration recorded for
that file in the current compiler bundle. Python targets are parsed without
importing or executing them. Sail references require the existing bundle's
source identity to agree with current sources. Other target kinds support file
references without a fragment. C and RTL comments can link to declarations in
these supported languages; their own declarations do not yet have a resolver.

Inline and reference-style Markdown links are supported in source comments;
Python docstrings also participate. Ordinary strings and fenced examples do not
introduce references. Retained source snapshots are historical evidence and stay
outside this live-source check. External URLs remain outside offline validation.
Keep generated references in their generator and preserve frozen campaign bytes.
Existing requirement-ID checks remain responsible for requirement citations.

Renaming or deleting a referenced file, section or supported declaration makes
the corpus check fail at the referring source and line. Resolution establishes
that the target exists; review still decides whether it supports the comment.
Prefer these links over bare filenames, line numbers or symbol names when
directing readers to an owner. The host gate runs the corpus check even for
prose-only changes, so moving a document heading also checks source backlinks.

## The conventions

All tools must follow these rules:

- **Exit 0 is clean, 1 is a finding.** `argparse` exits `2` on usage errors, and unhandled exceptions produce tracebacks; no command exits `0` after reporting a finding.
- **Discover the repository root from `__file__`.** `vos.corpus.find_root` walks up from the tool's own file path; tools do not depend on the caller's working directory.
- **Print one verdict line per rule.** Checks emit `ok <rule>: <summary>` or `FAIL <rule>: <n> <summary>` with findings indented beneath it.
- **Accumulate verdicts in memory.** Check runners return structured verdict records so callers such as `selftest` can inspect results directly without parsing stdout.
- **Preserve line endings on repair.** Write files with `newline=""` and explicit UTF-8 so token edits do not rewrite line endings across a file.
- **Repair derived arithmetic; report judgment mismatches.** `--fix` updates computed sums and generated views, but leaves judgment-dependent mismatches as findings.
- **Share parsers in [vos/](vos/).** When two tools read the same artifact, the parser lives in `vos/` rather than being duplicated.
  JSON object readers use [vos/jsonutil.py](vos/jsonutil.py)'s ordered duplicate-key
  hook while keeping domain-specific numeric, encoding, and shape checks in each reader
  ([consolidation acceptance](../PLAN.md#shared-json-duplicate-key-rejection)).
  Memory-planner commands share duplicate-field diagnostics in
  [vos/memory_planner_json.py](vos/memory_planner_json.py).
- **Use atomic publication.**
  [vos/atomic.py](vos/atomic.py) handles sibling temporary files, atomic replacement, and
  cleanup on failure, while callers supply containment, serialization, and locking.
  Whole-file SHA-256 digests use [vos/receipts.py](vos/receipts.py)'s `digest`.
- **Declare source-binding owners in one place.**
  [vos/source_bindings.py](vos/source_bindings.py) declares the composer and
  admission entry points and non-Python inputs used by package inventories,
  composition inputs, and receipt manifests, while
  [vos/python_dependencies.py](vos/python_dependencies.py) statically resolves local
  transitive Python imports. The copy-service recipe supplies its complete source
  closure; authored interface paths retain their choices while their digests regenerate.
  Regenerate owned fields with `composer bind-sources` before
  `composer project`; K-88 checks those views.
- **Annotate all functions and type all dispatch tables.** Use `Protocol` for dispatch families, `TypedDict` for configuration rows, and explicit type parameters for containers and `re.Match`.
- **Admit letter suffixes in ID regexes.** Inserted requirement and artifact IDs use letter suffixes (e.g., `R-15-073c`) rather than renumbering. Patterns such as `A-\d+` or `A-\d+(?![\w-])` silently miss or skip suffixed IDs; audit both enumeration and citation patterns.
- **Raise explicit exceptions instead of `assert` for validation.** `python -O` strips `assert` statements, so checks guarding artifacts must raise exceptions explicitly and pass `strict=True` to `zip` over parallel sequences.
- **Avoid expensive full-document regex scans.** Prefer line-by-line `.match()` with a substring precheck over `(?m)^` across full document text, check word boundaries in Python on matches instead of using leading lookbehinds (`(?<![\w-])`), and prefilter case-insensitive alternations with `str.find` on lowered text (benchmarking candidates against an equality check).

## Adding a rule to the checker

The [document-count maintenance contract](../docs/implementation/contracts/document-counts.md) keeps narrative counts optional while retaining checks on their owners.

Adding a check rule requires three edits:

1. Implement the check in the [vos/checks/](vos/checks/) module for its group (binding a new group in [vos/checks/__init__.py](vos/checks/__init__.py) if needed).
2. Register its metadata and reach class in [check-registry.json](check-registry.json). K-00 verifies that every registered rule is implemented, reported by a clean group run, and reflected in the generated views.
3. Add a mutant case in [run.py selftest](vos/cli/selftest.py), which fails if any registered rule lacks a case or has an unseeded mutation.

Regenerate [check-rules.md](check-rules.md)'s marked table and reach memberships
through `python tools/run.py check --fix`; never hand-edit those regions. Retire an
ID into the owner's inactive records instead of deleting or reusing it.

A rule that reads an enumeration supplies a member count to the floors group, unless it reports unreadable or missing sites itself. State that treatment in its authored metadata. A rule with several readers accounts for each separately; a fail-closed path lookup does not protect an unrelated symbol or command enumeration.

A **quarantined** rule keeps the same three parts inside [quarantine/](quarantine/): the check under [quarantine/checks/](quarantine/checks/), the row in [quarantine/check-rules.md](quarantine/check-rules.md), and the mutant in [quarantine/gate.py](quarantine/gate.py). See [quarantine/README.md](quarantine/README.md) for the deferral criteria and un-quarantine conditions.

Before the integrated batch lands, typecheck and the checker must both be green.
Host CI supplies those verdicts; document-only lanes do not need separate typecheck
runs. Use [the check schedule](#check-scheduling-during-fan-out) for feedback during
authoring and for the remaining landing gates.
