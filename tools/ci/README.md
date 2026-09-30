# Guest CI contract

The guest pipeline validates the curated model, proof sources and authored RTL on
Linux. This document owns its execution and acceptance contract. Follow the
[validation handoff](../../AGENTS.md#tool-execution-and-validation) to publish inputs,
require Host CI and dispatch both guest lanes without waiting for their verdicts.

## Running it

The [`fanout` completion command](../fanout.md) runs from `main`, merges the selected
local worktrees and publishes only `main`,
requires Host CI on Windows and Ubuntu for that commit, then dispatches both guest
lanes with the batch's `cold` policy. It records the dispatch response and returns
without polling Guest CI. The optional `title` workflow input carries the commit
subject into the run title, which also identifies an interrupted dispatch for
recovery. The explicit `revision` input pins checkout
to the settled commit even if `main` advances during dispatch. Work branches and
publication tags are never pushed. A session finishes only after its work is on
local and remote `main`; Guest CI may remain pending.

[guest-gates.yml](../../.github/workflows/guest-gates.yml) runs on Ubuntu 26.04,
every Monday at 04:23 UTC, on the first day of each month at 04:23 UTC, or through
GitHub's **Run workflow** control on `main`. A manual run's optional `revision` input
names a full lowercase commit already on `main`; the workflow refuses any other ref or
revision before installing tools. Each run title follows the workflow name with the
`title` input, or else with its checked-out revision, and runs are not serialized, so a
queued handoff is never replaced. Ordinary runs reuse installed toolchains and
content-validated native proof results. The monthly run and the manual `cold` input
force cold toolchain installation and a fresh full proof check. A weekly scheduled
run first reads the latest completed run on the same branch. It skips the guest
lanes before allocating their runners or installing tools when that run succeeded
on the current revision: a scheduled run's head commit, or for a dispatched run,
which may pin an older revision than its head, the revision named by both lanes'
artifacts. New revisions,
failed or canceled runs, absent history and failed history lookups run all gates. Manual dispatch, monthly cold runs and explicit
reruns always execute them. The history job alone has `actions: read`; the gate lanes keep `contents: read`.
They need no repository secrets or initialized submodules. The public repository's standard
[runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
has 16 GB of RAM; the proof kernel recheck has historically exceeded 8 GiB,
so a smaller runner needs a separate resource measurement.

The gate job is a two-lane matrix, and each lane has its own runner. The `model` lane
installs Z3, Sail and Verilator, then runs the model evidence sweep, bundle comparison,
RTL lint, width check and crosscheck. The `proofs` lane installs Rocq alone and runs the proof gate.
Neither lane consumes the other's toolchain or outputs, so a run lasts as long as its
longer lane. One lane's failure does not cancel the other. Both lanes must pass to
establish complete guest evidence; Host CI supplies no model, RTL or proof verdict.
The workflow retains results and proof receipts when available.

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
python3 tools/run.py rtl widthcheck
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
`guest-<lane>-<revision>-<attempt>` artifact, named for the checked-out revision and
run attempt, retains its logs and receipts for 14 days. A canceled run may
end before it uploads diagnostics.

uv downloads, opam's source download cache and verified Verilator source archives
are restored between runs; model evidence is always rebuilt. The source
cache includes bootstrap's ownership marker so the restored private root can resume.
Each lane has its own source cache. Its key includes the lane, runner OS and architecture,
Sail and Rocq snapshots, bootstrap, the Verilator installer and shared download helper.
A prefix fallback reuses the lane's older source downloads, with the installers' checksum
verification still required. Cache eviction simply means a cold installation. Only the
model lane saves the uv cache; both lanes restore it. Its `guest-gates` key suffix keeps
Host CI's smaller download set, saved under Host CI's own suffix, from claiming the key
when both workflows run on one runner image. Each lane's commands stay
sequential within its runner's memory budget.

Ordinary weekly and manual runs restore a lane's installed
toolchains: its opam root without downloads or logs, the Verilator prefix and the
ownership marker. Bootstrap then runs unchanged: it imports each lock into its restored
switch, installs the uncached solver, skips a Verilator prefix whose receipt matches
and probes every tool. The key includes the lane, runner OS, architecture, the Sail
and Rocq snapshots and bootstrap, with the image version for the model lane and only
the image's release (`ImageOS`) for the proofs lane. Rocq and its checker load only
the C library, whose ABI a release keeps and whose bytes the proof gate binds. A
rebuilt switch reproduces those executables but not every installed library file,
so sharing one switch across a release's images is what lets proof evidence cross
them. Switch names and the Verilator prefix carry their versions, so other tool
edits need no key input. Only exact keys restore. A main-branch run that missed the key saves the lane's toolchains after its
probes pass; a cold run checks the key without restoring it. The reporter records
`cold` or `restored` in `results.json` and the job summary. Only a cold run is
evidence that the toolchains install.

The proof lane also restores the native proof receipt, staged `.v` sources and
compiled `.vo` objects from a successful proof gate. Its cache is separate from
the installed toolchains. Before restoring, the lane runs `proofs identity` in the
gate's explicit environment: the digest of the toolchain and installed-library
context that an earlier receipt must match before any of its evidence is reused.
Keys bind that identity, the runner OS, architecture, proof sources, tools,
requirements register and workflow. A fallback within the same identity supplies
older candidates for incremental checking, so runner images with one identity share
one lineage and no other context's candidates are offered. Without an identity the
gate runs without candidates. Only main saves candidates, and only after the proof
gate succeeds.
The monthly and manual cold modes do not restore them and pass `--fresh`.
Cold results seed the proof cache only when the installed-toolchain key is also
new: a rebuild need not match the bytes of an existing immutable toolchain cache.

Restoring candidates never skips the proof command. The existing
[native cache validator](../README.md#current-evidence-and-generated-documentation)
checks source and object bytes, dependency closures, gate inputs, audited symbols,
assumptions, tool executables, installed libraries and the actual process
environment. Stale or unsupported candidates require compilation, auditing and
kernel checking under that contract. The identity step fixes one explicit
environment, which the cold and ordinary proof commands reuse: tool paths, native
storage, home, locale and Python settings. GitHub's per-run IDs, temporary
file-command paths and credentials never enter the proof process. This preserves the
gate's complete environment comparison without teaching it to ignore CI variables.

The proof log states actual reuse and, when an earlier receipt authorizes none, which
toolchain part, context entries or gate modules differ; the summary states the
selected proof policy.
On an unchanged cache hit the retained receipt identifies the earlier checked
bytes and their original timings, not a new kernel execution. Cold runs retain
periodic installation and full recheck evidence. Model build trees and compiler
caches are not restored, and every run regenerates its RTL vectors.

The model lane restores one file into its fresh build tree before the evidence
sweep: Sail's SMT memo, `model/sail_smt_cache`, which maps each typechecking
obligation's digest to the solver's verdict. A cold memo re-discharges every
obligation and turns the model's C++ emission from seconds into minutes. The build
seeds itself from that copy exactly as a
[new local lane](../vos/cli/model.py) seeds itself from the primary tree's, with
one writer per runner. The memo keys obligations, not the solver that answered
them, so its key binds the runner image, architecture, and the Sail version, Z3
version and Sail snapshot recorded in `bootstrap.json`; a fallback within that
identity supplies an older model's memo, which costs misses and never supplies
another solver's verdict. Only main saves it, after a passing evidence sweep, under
a key that also hashes the model's Sail sources. The monthly and manual cold modes
look the key up without restoring it, so their build discharges every obligation
with the installed solver. The reporter records the memo as `cold` or `restored` in
`results.json` and the job summary; a restored memo's cached verdicts were not
discharged again in that run.

The [boot signature target campaign](../../firmware/crypto/README.md#hosted-target-campaign)
restores the model lane's installed toolchains and Sail memo under these same keys and
path lists and saves neither. A change to either key or path list here must change
that workflow's restore with it, or its runners install and emit cold.

Each command runs under GNU time, whose figures in its retained log end with
`maxrss_kb`: the peak resident memory of the command's largest single process. For
the proof gate this measures the kernel recheck against the planning budget in
[vos/env.py](../vos/env.py)'s `proof_jobs`.

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
  proof gate as excluded. The full corpus command also runs the architectural
  block-image persistence campaign: separate emulator processes write and reopen
  a backing image, with complete-medium comparisons and refusal controls. Its
  failure fails the corpus member. The manifest's trace tally stays separate
  from this generated multi-process campaign.
- `python3 tools/run.py model bundle --check` compares the emitted model bundle.
- `python3 tools/run.py rtl lint` checks the standalone authored and generated RTL.
- `python3 tools/run.py rtl widthcheck` builds the scalar-width testbench from the
  tracked `rtl/` packages and checks the frozen transport widths and every
  store-rotation bit and lane. It reads no gitlink, so the lane still initializes no
  submodule; the checks that read imported cores stay outside this pipeline.
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
Download and installed-toolchain caches accelerate installation, and the Sail memo
accelerates emission; native proof reuse requires the proof gate's validation,
never a cache-action verdict. A cold run must work without any cache. Built model
outputs remain uncached.

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
verification. Host CI's Ubuntu shard 1 analyzes every workflow. zizmor, pinned in
[the manifest](../pyproject.toml)'s `workflows` group and locked outside the gate's
environment, runs its offline security audits, including the one requiring every
action to be pinned by commit. [actionlint.sh](actionlint.sh) runs actionlint from a
release archive verified against its pinned SHA-256, reading
[.github/actionlint.yml](../../.github/actionlint.yml) for hosted runner labels newer
than that release's own table. It checks workflow syntax, expressions and contexts but
not shell bodies, because no pinned shellcheck or pyflakes is provisioned. To run both
in WSL, set `UV_PROJECT_ENVIRONMENT` and `ACTIONLINT_ROOT` to directories under the
lane root, then run
`uv run --project tools --locked --exact --only-group workflows zizmor --offline .github/workflows`
and `sh tools/ci/actionlint.sh -shellcheck= -pyflakes=`. Use the repository's
[validation handoff](../../AGENTS.md#tool-execution-and-validation) for the settled
revision. Select `cold: true` when proof freshness or cold installation is required.
Dispatch alone does not establish proof correctness, cold installation or cache
qualification.

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
