# Guest CI contract

The guest pipeline validates the curated model, proof sources and authored RTL on
Linux. This document owns its execution and acceptance contract. Follow the
[validation handoff](../../AGENTS.md#tool-execution-and-validation) to publish inputs,
require Host CI and dispatch every guest lane without waiting for their verdicts.

## Running it

The [`fanout` completion command](../fanout.md) runs from `main`, merges the selected
local worktrees and publishes only `main`,
requires Host CI on Windows and Ubuntu for that commit, then dispatches every guest
lane with the batch's `cold` policy and, for a batch initialized with
`--reading-base`, its reading base. It records the dispatch response and returns
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
revision before installing tools. Its optional `reading_base` input, empty by default,
names a full lowercase commit that is a proper ancestor of that revision; when it is
nonempty, the same check refuses any other value before checked-out code runs. A
refused dispatch runs no checked-out code afterwards either: each later step that runs
commands after a failure, the reporter included, also requires that check not to have
failed, so such a run records no `results.json` and its upload finds no logs. The
input reaches each step that reads it only through that step's environment, never
through text written into a script. Each run title follows the workflow name with the
`title` input, or else with its checked-out revision, and runs are not serialized, so a
queued handoff is never replaced. Ordinary runs reuse installed toolchains and
content-validated native proof results. The monthly run and the manual `cold` input
force cold toolchain installation and a fresh full proof check. A weekly scheduled
run first reads the latest completed run on the same branch. It skips the guest
lanes before allocating their runners or installing tools when that run succeeded
on the current revision: a scheduled run's head commit, or for a dispatched run,
which may pin an older revision than its head, the revision named by every lane's
artifact. New revisions,
failed or canceled runs, absent history and failed history lookups run all gates. Manual dispatch, monthly cold runs and explicit
reruns always execute them. The history job alone has `actions: read`; the gate lanes keep `contents: read`.
They need no repository secrets or initialized submodules. The public repository's standard
[runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
has 16 GB of RAM; the proof gate's one kernel worker peaks just under its 10 GiB
budget there, as the runs [vos/proofenv.py](../vos/proofenv.py)'s `proof_jobs` records
measured, so a smaller runner needs a separate resource measurement.

The gate job is a matrix of lanes, and each lane has its own runner. The `model` lane
installs Z3, Sail and Verilator, then runs the model evidence sweep. The `rtl` lane
installs the same toolchains, restoring the model lane's download, toolchain and Sail
memo caches and saving none, then runs the bundle comparison, RTL lint, width check
and crosscheck. The `proofs` lane
installs Rocq alone, runs the proof gate and, in a run given a `reading_base`, reads
the proofs against that base. No lane consumes another's outputs, so a run lasts as
long as its longest lane. One lane's failure does not cancel another. Every lane must
pass to establish complete guest evidence; Host CI supplies no model, RTL or proof
verdict. The workflow retains results and proof receipts when available.

[bootstrap_guest.py](bootstrap_guest.py) installs only the missing Ubuntu packages
when passed `--install-system`, using root or passwordless sudo. Its `BASE_PACKAGES`
and per-toolchain `PACKAGES` own that list: every selection installs the base, which
takes the packages `opam init` needs from
[the opam client's owner](../vos/opam_client.py), and each selected toolchain adds its
installation's and gates' own, so the Rocq-only proofs lane installs none of the model
build's or Verilator's. One package-database query checks all of a selection's
prerequisites; a fatal query error stops installation. Python must satisfy
[the manifest](../pyproject.toml), and uv must match its exact pin before bootstrap starts. The script checks the downloaded
opam executable, imports the [package snapshots](../opam/README.md), and calls the
existing pinned Verilator installer. It installs Z3 first, only from the wheels whose SHA-256
values [the solver's requirements](../z3-requirements.txt) record and never from source,
and probes it, prepending its private binary directory to `PATH` before Sail starts: Sail initializes its solver
even for `--version`. Each tool is probed immediately after installation, so a failed
Sail probe stops before building Rocq or Verilator. A repeatable `--toolchain` option
selects `sail` (with its solver), `rocq` or `rtl`. The default installs all three in
that order. Bootstrap creates its opam root by the owner's root-creation route where
none stands, and finishes one in the shape the route's leading steps leave by running
the route's remaining steps, never `opam init` over it. That shape includes a root
whose `repository add` was stopped during its fetch, which leaves the repository
configured but unfetched; the same step run again fetches it. It keeps a root that stands
complete, in the reviewed client's format with exactly the owner's repositories at
their URLs and every metadata stamp read, without running the route over it, because
the reviewed client's `repository add`
fetches a repository the root already carries again and removes it where that fetch
fails. It refuses any other standing root, naming each gap it reads there, and leaves
it as it is. `bootstrap.json`
records the selection, whether the root was created, finished or kept, each opam
repository's URL and metadata stamp, and the root's format. Bootstrap fails when the
root is not configured with exactly the owner's repositories, a stamp cannot be read,
or the format is not the reviewed client's. Bootstrap failures print the last
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

This runs every lane's commands on one machine; the complete `evidence` sweep
includes the proof gate.

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
that lane's command outcomes in `results.json` and renders the job summary. The proofs
lane's outcomes include the reading step's, `skipped` in a run given no reading base,
and a run given one also records that base. The reporter refuses a base in any other
lane or in any form but a full lowercase commit SHA. It copies
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
The model and proofs lanes each have their own source cache, and the rtl lane restores
the model lane's without saving it. Its key includes the lane that saves it, runner OS
and architecture, Sail and Rocq snapshots, bootstrap,
[the opam client's owner](../vos/opam_client.py), the Verilator installer and shared
download helper.
A prefix fallback reuses the lane's older source downloads, with the installers' checksum
verification still required. Cache eviction simply means a cold installation. Only the
model lane saves the uv cache; every lane restores it. Its `guest-gates` key suffix keeps
Host CI's smaller download set, saved under Host CI's own suffix, from claiming the key
when both workflows run on one runner image. Each lane's commands stay
sequential within its runner's memory budget.

Ordinary weekly and manual runs restore a lane's installed
toolchains: its opam root without downloads or logs, the Verilator prefix and the
ownership marker. The rtl lane restores the model lane's, under that lane's key, and
never saves them. Bootstrap then runs unchanged: it keeps the restored root, which
stands complete, and records the repository stamps its switches were resolved against,
imports each lock into its restored switch, installs the uncached solver, skips a
Verilator prefix whose receipt matches and probes every tool. The key includes the
lane whose installation it holds, runner OS, architecture and that lane's toolchain
recipe identity, with the image
version for the model lane and only the image's release (`ImageOS`) for the proofs
lane. `bootstrap_guest.py --print-recipe-identity`, given the lane's `--toolchain`
selection, prints that identity: the SHA-256 of the owner data that decides the
installed bytes, which bootstrap's `recipe` states. That data is the selection's Ubuntu
packages; the opam client's release, per-architecture SHA-256 values, root format,
repositories and root-creation route from
[the opam client's owner](../vos/opam_client.py); each selected switch's steps from
[its owner](../vos/env.py) with the bytes of the snapshot it imports, so the proofs
lane's key reads `rocq.lock` alone and the model lane's `sail.lock` alone; and for
`rtl` the Verilator release, archive URL and SHA-256. Other edits to bootstrap or the
client's owner keep the key. No constant summarizes that data: the key's
`guest-toolchains-v1` version is the one a reviewer raises by hand for an
installation-procedure change none of it captures, such as another step in the
Verilator installer's build or in how bootstrap finishes a root. Rocq and its checker
load only the C library, whose ABI a release keeps and whose bytes the proof gate
binds. A rebuilt switch reproduces those executables but not every installed library
file, so sharing one switch across a release's images is what lets proof evidence
cross them. Only exact keys restore. A main-branch run of the model or proofs lane that
missed the key saves that lane's toolchains after its probes pass; a cold run checks
the key without restoring it. The reporter records
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
periodic installation and full recheck evidence. Model build trees are not restored,
and every run regenerates its RTL vectors.

The model and rtl lanes each restore one file into their fresh build tree before
running Sail, the model lane before its evidence sweep and the rtl lane before its
bundle comparison: Sail's SMT memo, `model/sail_smt_cache`, which maps each
typechecking obligation's digest to the solver's verdict. A cold memo re-discharges
every obligation and turns the model's C++ emission from seconds into minutes. Each
lane's Sail run seeds itself from that copy exactly as a
[new local lane](../vos/cli/model.py) seeds itself from the primary tree's, with
one writer per runner. The memo keys obligations, not the solver that answered
them, so its key binds the runner image, architecture, and the Sail version, Z3
version and Sail snapshot recorded in `bootstrap.json`; a fallback within that
identity supplies an older model's memo, which costs misses and never supplies
another solver's verdict. Only main's model lane saves it, after a passing evidence
sweep, under a key that also hashes the model's Sail sources; the rtl lane, whose
bundle rewrites its own copy in a tree it does not build, never saves it. The monthly
and manual cold modes look the key up without restoring it, so their Sail runs
discharge every obligation with the installed solver. In the model and rtl lanes the
reporter records the memo as `cold` or `restored` in `results.json` and the job
summary; a restored memo's cached verdicts were not discharged again in that run.

The [boot signature target campaign](../../firmware/crypto/README.md#hosted-target-campaign)
restores the model lane's installed toolchains and Sail memo under these same keys and
path lists and saves neither. It computes the recipe identity for the model lane's
selection, `--toolchain sail --toolchain rtl`, though it bootstraps Sail alone,
because the cache it restores holds that lane's installation. A change to either key,
path list or the model lane's selection here must change that workflow's restore with
it, or its runners install and emit cold;
[the guest report tests](../tests/test_guest_report.py) hold the two workflows' keys,
fallbacks, paths and identity computations equal.

The model lane also restores ccache's directory, the `CCACHE_DIR` bootstrap exports,
less its scratch `tmp`, before its evidence sweep, so a compile an earlier main run
already made, the generated model unit's included, returns that run's object instead
of compiling again. Under the default configuration [vos/env.py](../vos/env.py) keeps,
with no sloppiness and no base directory, ccache keys each object on the preprocessed
source, the full command line and the compiler's size and modification time, and every
runner builds from the same checkout path into the same `~/verifiedos-guest/build`
tree. The build compiles with the image's preinstalled clang, which bootstrap's
`--no-upgrade` installation leaves in place, so the key's image version binds the
compiler itself, and a hit is the object that compile produces, debug information
included. The key binds the runner OS, architecture, image version and the model lane's
toolchain recipe identity, so an entry never crosses an image or toolchain recipe, and
hashes `model/**`; a fallback within that lineage supplies an older model's objects,
which hit only where a unit's inputs are unchanged. A configure option changed outside
`model/` costs misses, never a wrong object, until the model next changes. Before the
sweep the lane zeroes ccache's statistics and notes the time; after it, the lane prints
them, this run's hits and misses, to the log and evicts every entry older than that
time, which a hit renews, so only the objects this build used remain. Only main's model
lane saves the cache, when the key missed, after a passing sweep and a successful trim.
The statistics and the trim decide no verdict: printing the statistics never fails
the step, and a failure to zero them, note the time or trim skips the save alone. The
monthly and manual cold modes look the key up without restoring it, so their builds
compile every unit. The rtl lane restores none of it, because every compile it runs
builds other sources, Verilator's generated C++ and the vector generator's C, under
paths the model build never uses. The guest report tests hold these steps' order,
conditions, key and paths.

Each command runs under GNU time, whose figures in its retained log end with
`maxrss_kb`: the peak resident memory of the command's largest single process. The
reading comparison's log holds the comparison alone, so its figures stand beside it in
`proof-reading-compare.time`. For
the proof gate this measures the kernel recheck against the planning budget in
[vos/proofenv.py](../vos/proofenv.py)'s `proof_jobs`, beside the usable CPU count and
`MemAvailable` reading the gate's log states for each automatic worker limit.

## Inputs and execution

The checked-out revision owns the Sail and Rocq package snapshots, solver and
Verilator pins, Python lockfile, generated model bundle and gate commands. Bootstrap
starts from a supported Ubuntu runner with Python and uv installed and initializes
its own opam root without borrowing the developer's switches. Install only the
toolchains consumed by this pipeline. QuickChick's switch is built and checked only on
the [instrument switch route](#instrument-switch-route), the incomplete CertiRocq oracle
is built only locally, and compiler experiments and imported-core elaboration remain
separate loops.

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

In the rtl lane:

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
- In a run given a `reading_base`, once the proof gate has passed,
  [`python3 tools/run.py proof-reading`](../vos/cli/proof_reading.py) `record` reads
  the gate's compile, `record --sources` compiles and reads the base's `proofs/`,
  which `git archive` extracts from that commit into the runner's temporary
  directory, and `compare` compares the base's reading with the gate's. All three run
  in the gate's explicit environment. The step passes once both readings are recorded
  and compared, whatever differences the comparison names: it logs every one, its
  summary line states their count, and it then prints both readings' SHA-256 to its
  log and the summary, which outlast the artifact. A refused reading, a comparison
  that refuses its readings rather than comparing them, and a base whose sources
  cannot be extracted each fail it. Both readings, as `proof-reading-base.json` and
  `proof-reading-candidate.json`, their console logs and the comparison's log,
  `proof-reading-compare.log`, stay in the lane's artifact. A reading accepts no proof.

Each required command has a bounded execution time and retains its exit status.
Each lane's step limits stay a stated margin under the job's, which the steps without
a limit of their own share, so a lane that reaches every limit still reports and
uploads its diagnostics.
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
outputs remain uncached but for the compiler cache's objects, which ccache returns
only for an identical compile.

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
verification. Host CI analyzes this workflow with the others, as the tools guide's
[workflow analysis](../README.md#workflow-analysis) describes. Use the repository's
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

## Instrument switch route

[instrument-switches.yml](../../.github/workflows/instrument-switches.yml) builds and
checks QuickChick's switch on GitHub-hosted runners, and this section owns its contract.
QuickChick's switch is built and checked only on this route: no QuickChick switch is
built or checked in the local guest, and no QuickChick lock is tracked from a guest
build. The user's ruling of 2026-09-30 keeps `run.py provision --apply`'s QuickChick
import, which [the lock guide](../opam/README.md) names, out of the local guest (F-616).
No CertiRocq switch is built, checked or dispatched
on this route, the user's ruling of 2026-09-30 keeping CertiRocq's builds local. No
switch or download cache is used, so every switch a run reports was built in that run
from its recipe or lock in a fresh root; the uv cache Guest CI saves is read and never
saved.

**Dispatch and plan.** `run.py instrument-ci dispatch` sends one dispatch with the
inputs `revision`, `base_revision`, `build` (`install` or `recipe`), `sample` (a whole
number from 1 to 20, default 20) and `title`, at a `--ref` that defaults to `main`, and
refuses nothing the plan refuses. It puts a per-dispatch nonce in the run title,
journals its intent under `out/instrument-ci/dispatches/` before its one POST, and
recovers an interrupted dispatch with `--resume NONCE` by the run whose title carries
the nonce, never by posting again. `fanout` never runs it. The plan job runs
[instrument_route.py](instrument_route.py) from the dispatching commit before any
requested revision is checked out and uploads `plan.json`, each check's verdict and
reason, under `always()`. It refuses a plan whose checkout is not the dispatching
commit; a ref other than `main`; an empty `revision`, or one that is not a full
lowercase commit on `main`; a `base_revision` that is not a full lowercase commit, or
not a proper ancestor of `revision`; a `sample` outside 1 to 20 or written with a sign
or a leading zero; a `build` other than `install` or `recipe`; a revision whose
quickchick.py declares no `RECIPE` where `build` is `recipe`, or no `INSTALL` where it
is `install`; and a `base_revision` whose quickchick.py declares no `INSTALL`, each
declaration a non-empty tuple or list of steps, read from that revision's source
without running it. A refused plan starts no later job. Inputs reach a step only
through its environment, and later jobs read only the values the plan validated.

**Jobs.** Every job runs the route's own files, the workflow,
[bootstrap_instrument.py](bootstrap_instrument.py), instrument_route.py and
[the opam client's owner](../vos/opam_client.py), from the dispatching commit's
checkout, takes only the owner's declarations, the instruments, the harnesses and
`proofs/` from its side's revision, and holds each checkout to `main` before any of its
code runs. bootstrap_instrument.py installs its own distribution prerequisites,
`PACKAGES`, the root's from the client's owner and the QuickChick build's, then the
reviewed client and a fresh private root by the owner's route, and builds the side's
switch: by `quickchick.RECIPE` into `gallina.QUICKCHICK_RECIPE_SWITCH` where `build` is
`recipe`, by `quickchick.INSTALL` into `gallina.QUICKCHICK_SWITCH` where it is
`install`, and on the base side always by its revision's `INSTALL`. It refuses a build
after which the switch its recipe names does not stand, and the checks on a switch a
`RECIPE` built run with `--recipe`.

- The build job builds the candidate's switch, runs `quickchick check` and
  `quickchick properties` and exports the switch, uploading the export only when every
  check on its switch passed.
- The import job, on another runner, takes that export only from the same run, at the
  SHA-256 the build job recorded, imports it into a fresh root and the switch the
  build's recipe names by [the lock guide's](../opam/README.md) create-and-import form,
  runs `quickchick check` with the build's flag, and decides by its exit 0, the
  installed closure and each pin's URL and commit. The byte difference of its re-export
  is recorded as an observation.
- Where `base_revision` is given, three seed jobs, the base run and two candidate runs,
  each build their side's switch in a fresh root, list the sampled population with
  `seed list`, the operator of each mutant the journal names, and run
  `seed coq --quickchick --sample N` over seed's default subject. The route reads the
  journal as [seed's `Journal`](../vos/seeded.py) writes it: the scope its head states,
  one line per verdict, any reason running on over the lines after its verdict, and a
  closing line counting the decided verdicts and, where there is one, the undecided
  ones apart. A note, a line opening `-- `, is no verdict and no part of one's reason,
  and the route reads nothing from it. `seed coq` journals a mutant whose compile
  reaches gallina's per-file timeout as undecided and goes on to the next. A seed run is
  complete when its journal's closing line counts every mutant its head picked, decided
  and undecided together, at seed's exit 0 or 1; a journal that closes on fewer, as one
  whose baseline did not stand closes on none, fails the step. `--jobs` stays at 1 until
  the build job's recorded `quickchick properties` peak is the basis for more; after a
  seed step reaches its limit, the next dispatch raises `--jobs` on that peak or records
  the runner decision as owed to the user, and the sample stays 20.
- The join job runs when the plan job passed and the run was not cancelled. It takes
  one artifact per job, records a job its prerequisite's failure skipped as not run,
  records as failed a job whose result is failure though none of its wrapped steps
  failed or was undecided, a seed run only where a step of its own never ran, since a
  seed run's result is its matrix's, passes over and records an artifact an earlier
  attempt of the run left for a job this attempt did not run, refuses an artifact
  missing from a job that ran, a duplicate, any other artifact from a job that did not
  run, an artifact the route does not name or one not named for its side's revision, a
  `plan.json` missing, unreadable or naming another run, and a receipt that cannot be
  read, that names another job, seed run, run or dispatching commit, that records inputs
  other than the plan's, or that records no tested revision once its provisioning ran or
  another revision than its side's, and writes `report.json` and a job summary naming
  each step's verdict, each sampled mutant's verdict in every seed run by its identity,
  operator, site and rewrite, each mutant whose verdict differs between the two
  candidate runs or between base and candidate, or whose journalled verdict is other
  than killed, survived, stillborn or unseeded, an undecided one among them, with the
  verdicts and reasons the journal records, and every pair of sides whose opam client
  version or runner image differs.

**Receipts and limits.** Each job's receipt records its effective inputs, side,
revision, base revision, build, sample and subject, the subject being the one the plan
read from the side's seed.py and provisioning refusing a side that names another,
beside its `source_revision`, recorded before provisioning reads anything else, the
dispatching commit and `GITHUB_RUN_ATTEMPT`; the recipe built, the switch and the flag
its checks ran with, and that switch's installed closure with each pin's URL and
commit; the runner image, `uname -m`, the opam client's version and the prerequisites
installed; free disk before and after; and each step's limit, exit, GNU time figures
and the sampler's peaks. Each step runs under coreutils `timeout --kill-after` at the
limit instrument_route.py states with its basis: the build's from Q38f's 4,402 s
import, `quickchick properties`' from Q38e's 378 s, and each seed step's its job's
limit, GitHub's 360-minute hosted maximum less a 5-minute margin, the build step's
limit, the population listing's and the staging margin, marked unmeasured. A sampler
appends the largest resident set, its process tree's total, free disk and load average
to the job's progress log every minute, so a step cut at its limit leaves its peak.
`report.json`, the job summary and `instrument-ci read` give a step's peak as the
larger of GNU time's `maxrss_kb` and the sampler's largest resident set, each the
step's largest single process, name which gave it, and give both figures and the
sampler's tree total beside it. A step for which neither recorded a figure, as one GNU
time did not wrap that ended before the first sample, is said to have none, never a
peak of 0. An exit of 124, or of 137 where the receipt holds no kernel OOM record for
the step, once the step has run for its limit, is the limit reached; either exit
sooner is recorded undecided, its cause unread. A step that reaches its limit; that
exits for want of disk or memory, as the sampler's free-disk figure, a line of its
output reporting `No space left on device` or the kernel's OOM record shows; or that
exits with a line of its output naming `TimeoutExpired` decides nothing and is
recorded undecided, never as a failure. That line is read as a compile that reached
gallina's per-file timeout and raised out of the step, as one does from
`quickchick properties`; `seed coq` instead journals such a compile's mutant
undecided and goes on to the next. Each step's `timeout-minutes` is a backstop above
its limit, and each job's is the sum of its step limits plus a 15-minute
staging-and-upload margin.

**Staging.** Each job's staging and upload run under `always()`. As in Guest CI, a
refused check runs no requested revision's code afterwards: each later step that runs a
command after a failure also requires the plan, or its job's side guard, not to have
failed, staging alone excepted, and a failed route guard skips the side checkout.
Staging runs after a refused plan or side revision too, so a refused plan still uploads
`plan.json` and a refused side its job's receipt, and it runs no requested revision's
code: its one command runs the dispatching commit's instrument_route.py, which imports
only the standard library and that checkout's `vos.receipts` and `vos.env`, reads the
job's private root as data, and reads no file of the side's checkout, whose code no
step before a refused guard has run.
The upload runs its pinned action alone. Staging copies an allowlist of `.json`, `.log`,
`.txt`, `.lock` and `.journal` files into an upload directory and leaves out any file
that is not a regular file, holds more than 64 MiB, would take the artifact past 256 MiB
or carries Wasm or ELF magic or a NUL byte, naming each in the receipt with its reason,
so that no switch, build tree, `.vo`, executable, image or opam cache is uploaded. Each
artifact is named for its job and revision with no attempt suffix, replaced on a rerun
and retained 30 days.

**Reading.** `run.py instrument-ci read --run ID` follows each artifact's redirect
without credentials, saves it under `out/instrument-ci/<run id>/` and extracts it only
there, refusing an archive with a member whose path is absolute or climbs out of its
directory, two members that would land on one another, a member that cannot be read,
or whose members total more than 256 MiB, and moving an extraction into place only
whole. It holds each member to the allowlist and each recorded input to the run, reads
the jobs' conclusions and the `plan.json` of a run the plan refused, re-joins the
artifacts against the run's `report.json`, and prints the verdict with the run's URL,
tested revisions, runner images and step durations and peaks. It prints whether
`git diff --quiet R <closing parent> -- <route inputs>` holds for the candidate's
`source_revision` R, and whether the same holds over the route's own files and their
`vos` import closure for the dispatching commit; given the closing commit by
`--closing` and the paths its owning item's closing landing names by `--closing-path`,
it reads that commit's own diff over the route inputs at R and at the closing commit,
so a module a named path newly imports is one, and prints those paths. It refuses as
closing evidence a run whose verdict is not passed or where a comparison does not
hold, a build artifact holding no export, a closing parent given beside the closing
commit that is not that commit's first parent, a closing commit that touches a route
input other than the tracked lock, its SHA-256 equal to the artifact's export, and the
named paths, and a run with a `base_revision` whose sample is not 20 or whose subject
is not seed's default. The route inputs are the workflow, bootstrap_instrument.py,
instrument_route.py, opam_client.py, gallina.py, quickchick.py, seed.py, provision.py,
env.py, proofs.py, seeded.py and mutate.py, the transitive `vos` import closure at R of
every module the route runs, which the reader computes from R's sources, tools/run.py,
tools/pyproject.toml, tools/uv.lock, `tools/quickchick/`, `tools/opam/quickchick.lock`
and `proofs/`.

**Landing.** QuickChick's lock is tracked only in its owning item's closing landing,
from a passing run's artifact, its SHA-256 equal to the artifact's. That landing copies
`report.json` and any failing step's text log, at their `out/instrument-ci/` paths,
under `docs/implementation/retained-evidence/`, each cited with its SHA-256.
