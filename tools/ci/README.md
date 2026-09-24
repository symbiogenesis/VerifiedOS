# Guest CI contract

The guest pipeline validates the current curated model, proof sources and authored
RTL on Linux. Run it together with [host validation](../../.github/workflows/host-gates.yml)
on GitHub Actions for each settled integration batch. Both workflows supply required
acceptance evidence; routine local execution of either complete suite is unnecessary.
Guest CI currently triggers through manual dispatch and scheduled runs. Dispatch
it for the published revision before acceptance; this procedure does not configure
an automatic pull-request trigger or a branch-protection requirement.

## Running it

[guest-gates.yml](../../.github/workflows/guest-gates.yml) runs on Ubuntu 26.04,
every Monday at 04:23 UTC, on the first day of each month at 04:23 UTC, or through
GitHub's **Run workflow** control. Ordinary runs reuse installed toolchains and
content-validated native proof results. The monthly run and the manual `cold` input
force cold toolchain installation and a fresh full proof check. A weekly scheduled
run first reads the latest completed run on the same branch. If that run succeeded
at the current revision, it skips the guest lanes before allocating their runners or
installing tools. New revisions, failed or canceled runs, absent history and failed
history lookups run all gates. Manual dispatch, monthly cold runs and explicit
reruns always execute them. The history job alone has `actions: read`; the gate lanes keep `contents: read`.
They need no repository secrets or initialized submodules. The public repository's standard
[runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
has 16 GB of RAM; the proof kernel recheck has historically exceeded 8 GiB,
so a smaller runner needs a separate resource measurement.

The gate job is a two-lane matrix, and each lane has its own runner. The `model` lane
installs Z3, Sail and Verilator, then runs the model evidence sweep, bundle comparison,
RTL lint and crosscheck. The `proofs` lane installs Rocq alone and runs the proof gate.
Neither lane consumes the other's toolchain or outputs, so a run lasts as long as its
longer lane. One lane's failure does not cancel the other. Require both lanes to pass,
and retain the run URL, tested revision, results and proof receipt. A green Host CI
run alone supplies no model, RTL or proof-gate verdict.

[bootstrap_guest.py](bootstrap_guest.py) installs only the missing Ubuntu packages
when passed `--install-system`, using root or passwordless sudo. Its `PACKAGES`
tuple owns that list. One package-database query checks all prerequisites; a fatal
query error stops installation. Python must satisfy [the manifest](../pyproject.toml),
and uv must match its exact pin before bootstrap starts. The script checks the downloaded
opam executable, imports the [package snapshots](../opam/README.md), and calls the
existing pinned Verilator installer. It installs and probes Z3 first, prepending its
private binary directory to `PATH` before Sail starts: Sail initializes its solver
even for `--version`. Each tool is probed immediately after installation, so a failed
Sail probe stops before building Rocq or Verilator. A repeatable `--toolchain` option
selects `sail` (with its solver), `rocq` or `rtl`. The default installs all three in
that order, and `bootstrap.json` records the selection. Bootstrap failures print the last
40 log lines in the Actions console as well as retaining the complete log.
Bootstrap and the Verilator installer share verified-download and atomic-publication
helpers in [vos/receipts.py](../vos/receipts.py); the reporter and JSON writers use
the same publication helper. Cached bytes are checked again before use, and corrupt
or interrupted downloads never become the cached archive. These helpers need only
the standard library, including when reporting a failed bootstrap.
Package repositories provide the archive
checksums for the snapshot imports; distribution package versions follow the runner
image. This records a package resolution, not a bit-for-bit toolchain image.

For local reproduction during focused debugging or a hosted-service outage, run
the affected commands on native Linux from the repository root. To reproduce the
complete guest suite when needed:

```sh
python3 tools/ci/bootstrap_guest.py --root "$HOME/build/guest-ci" --install-system
. "$HOME/build/guest-ci/environment.sh"
python3 tools/run.py evidence --out "$VOS_LOG_DIR/evidence.json"
python3 tools/run.py model bundle --check
python3 tools/run.py rtl lint
python3 tools/run.py rtl crosscheck
```

This runs both lanes' commands on one machine; the complete `evidence` sweep includes
the proof gate.

Bootstrap and standalone `rtl install` select workers through [vos/env.py](../vos/env.py).
`os.process_cpu_count()` supplies usable logical CPUs, including Linux affinity limits;
`/proc/meminfo` supplies available memory. Automatic toolchain sizing reserves 2 GiB
and budgets 2 GiB per worker, with at least one worker and at most the CPU count.
Unknown memory falls back to one worker with a warning. These are planning budgets,
not measured bounds on every upstream build. `--jobs N` overrides automatic sizing;
zero and negative counts are refused. Bootstrap records the selected count and exports
it to opam, the model build and its tests. Proof compilation and kernel checking keep
their separate memory budgets and resample before each phase. This sizing targets the
native runner or WSL VM; it does not interpret container cgroup CPU or memory quotas.

For a Windows worktree, run inside WSL and substitute its assigned
`/root/build/lane-<name>/ci` root. Bootstrap refuses a nonempty directory it does not
own. Retrying the same owned root resumes switch imports. Its environment file sets
private opam, build, log, solver, temporary and compiler-cache directories; it does
not edit the user's shell profile or replace existing switches. Shell activation and
GitHub's exported `PATH` both include the private solver and opam directories.
Bootstrap validates its ownership marker and holds the root's lock before changing
run state. A retry discards old gate records and activation, then writes an initial
failure record before installation. JSON records are replaced atomically, and a log
retention error is recorded separately without hiding the original installation error.

The workflow bounds each command and keeps independent checks running after a gate
failure. [report_guest.py](report_guest.py) reads its lane from `GUEST_LANE`, retains
that lane's command outcomes in `results.json` and renders the job summary. It copies
the checkout's proof receipt only when the proofs lane's proof gate step succeeded; the
tracked receipt otherwise predates the run. In the model lane it validates all member
names, exit codes and durations before rendering the evidence table. Skipped, failed or
canceled proof gates and evidence records cannot authorize retaining an old proof
receipt. Diagnostic copies are atomic;
copy failures appear in the summary without discarding command outcomes or other
diagnostics. The reporter uses `VOS_LOG_DIR`, with the workflow's default log directory
as its fallback when bootstrap did not export an environment. Each lane's
`guest-<lane>` artifact retains its logs and receipts for 14 days. A canceled run may
end before it uploads diagnostics.

uv downloads, opam's source download cache and verified Verilator source archives
are restored between runs; model evidence is always rebuilt. The source
cache includes bootstrap's ownership marker so the restored private root can resume.
Each lane has its own source cache. Its key includes the lane, runner OS and architecture,
Sail and Rocq snapshots, bootstrap, the Verilator installer and shared download helper.
A prefix fallback reuses the lane's older source downloads, with the installers' checksum
verification still required. Cache eviction simply means a cold installation. Only the
model lane saves the uv cache; both lanes restore it. Each lane's commands stay
sequential within its runner's memory budget.

Ordinary weekly and manual runs restore a lane's installed
toolchains: its opam root without downloads or logs, the Verilator prefix and the
ownership marker. Bootstrap then runs unchanged: it imports each lock into its restored
switch, installs the uncached solver, skips a Verilator prefix whose receipt matches
and probes every tool. The key includes the lane, runner OS, architecture and image
version, the Sail and Rocq snapshots and bootstrap. Switch names and the Verilator
prefix carry their versions, so other tool edits need no key input. Only exact keys
restore. A main-branch run that missed the key saves the lane's toolchains after its
probes pass; a cold run checks the key without restoring it. The reporter records
`cold` or `restored` in `results.json` and the job summary. Only a cold run is
evidence that the toolchains install.

The proof lane also restores the native proof receipt, staged `.v` sources and
compiled `.vo` objects from a successful proof gate. Its cache is separate from
the installed toolchains. Keys bind the runner image, architecture, Rocq snapshot,
bootstrap, proof sources, tools, requirements register and workflow. A fallback
within the same image and toolchain supplies older candidates for incremental
checking. Only main saves candidates, and only after the proof gate succeeds.
The monthly and manual cold modes do not restore them and pass `--fresh`.
Cold results seed the proof cache only when the installed-toolchain key is also
new: a rebuild need not match the bytes of an existing immutable toolchain cache.

Restoring candidates never skips the proof command. The existing
[native cache validator](../README.md#current-evidence-and-generated-documentation)
checks source and object bytes, dependency closures, gate inputs, audited symbols,
assumptions, tool executables, installed libraries and the actual process
environment. Stale or unsupported candidates require compilation, auditing and
kernel checking under that contract. The workflow starts both cold and ordinary
proof commands with the same explicit environment: tool paths, native storage,
home, locale and Python settings. GitHub's per-run IDs, temporary file-command
paths and credentials never enter the proof process. This preserves the gate's
complete environment comparison without teaching it to ignore CI variables.

The proof log states actual reuse; the summary states the selected proof policy.
On an unchanged cache hit the retained receipt identifies the earlier checked
bytes and their original timings, not a new kernel execution. Cold runs retain
periodic installation and full recheck evidence. Model build trees and compiler
caches are not restored, and every run regenerates its RTL vectors.

## Inputs and execution

The checked-out revision owns the Sail and Rocq package snapshots, solver and
Verilator pins, Python lockfile, generated model bundle and gate commands. Bootstrap
starts from a supported Ubuntu runner with Python and uv installed and initializes
its own opam root without borrowing the developer's switches. Install only the
toolchains consumed by this pipeline. The incomplete CertiRocq oracle, QuickChick
campaigns, compiler experiments and imported-core elaboration remain separate loops.

Builds, toolchains and logs use explicit native Linux directories outside the source
checkout. Local Windows runs keep them in their assigned guest lane. Bootstrap must
support a normal Linux user, state its distribution prerequisites, verify downloaded
tool archives and preserve the package versions requested by the snapshots.

The pipeline runs the existing commands. In the model lane:

- `python3 tools/run.py evidence --no-proofs` builds and tests the model, runs the
  reference, profile, differential-corpus and device-tree checks, and records the
  proof gate as excluded.
- `python3 tools/run.py model bundle --check` compares the emitted model bundle.
- `python3 tools/run.py rtl lint` checks the standalone authored and generated RTL.
- `python3 tools/run.py rtl crosscheck` regenerates model vectors and compares RTL
  answers. Reusing old vectors is not part of this gate.

In the proofs lane:

- `python3 tools/run.py proofs` validates native cache candidates and compiles,
  audits and kernel-checks proofs whose evidence cannot be reused. With no valid
  candidates it checks every proof. Cold runs add `--fresh` to force all work.

Each required command has a bounded execution time and retains its exit status.
Independent checks may still run after another fails when their bootstrap succeeded.
The evidence command owns its existing internal concurrency and freshness checks.
Proof receipt publication changes an output rather than the model's input identity;
working model bytes remain bound by the build manifest. Bundle comparison relocates
only the selected switch's absolute library hash keys to the canonical locations
used by the tracked artifact. A private opam root therefore does not change the
comparison, while changed library digests and model contents still fail it.
Download and installed-toolchain caches accelerate installation; native proof
reuse requires the proof gate's validation, never a cache-action verdict. A cold
run must work without any cache. Built model outputs remain uncached.

## Acceptance and handoff

Acceptance requires a cold installation in an isolated Linux environment, followed
by the real commands above, with the tested source revision, platform, tool versions,
durations and results retained. A fixture-only test does not establish that the
upstream packages install or that a hosted runner has sufficient resources. A local
clean toolchain run and a GitHub-hosted run are recorded as distinct evidence.
Proof-cache acceptance additionally needs a successful hosted cold run and an
ordinary run on the same revision that reports actual native reuse. Retain both
run identifiers and timings; installation-cache hits alone do not establish that
proof caching works. Existing proof-cache regressions cover changed sources,
objects, dependencies, toolchain context and failed runs.

Focused tests must cover installation planning and failure propagation, including
unavailable dependencies and corrupt downloads where the installer owns download
verification. Workflow syntax is checked with actionlint. After publishing the stable
combined changes, the integrator requires green Host CI on Windows and Ubuntu and
both Guest CI lanes on GitHub Actions. Host CI runs the sharded
`python tools/run.py --check --tests` suite; Guest CI runs the commands above,
including `python3 tools/run.py proofs`. Select `cold: true` when the applicable
acceptance contract requires `proofs --fresh` or cold installation evidence.
Record each workflow's run URL,
tested revision and verdict, and verify that both cover the settled inputs.
Use manual dispatch when no automatic event starts the required workflow.

Failure reporting and artifact upload run after failed checks without turning a
failed or skipped required command into success. Preserve textual logs, structured
evidence, the generated proof receipt and source/tool identities. Upload no compiled
emulators, opam switches, third-party source trees or executable caches as evidence.
Read and record the selected licenses of newly consumed actions and tools in
[THIRD-PARTY.md](../../THIRD-PARTY.md).

The bootstrap lane owns unattended installation and any necessary environment
portability fixes; the workflow lane owns orchestration and diagnostics. Independent
review checks their joined behavior and hidden machine assumptions. The integrator
owns shared documentation, license records, merging and final validation. The
[worktree and check procedures](../README.md#worktree-isolation-during-fan-out)
apply to every lane.
