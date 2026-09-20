# Guest CI contract

The guest pipeline validates the current curated model, proof sources and authored
RTL on Linux. It complements [host validation](../../.github/workflows/host-gates.yml).
Its initial triggers are manual dispatch and a weekly schedule; making it a required
pull-request check needs a measured hosted run time and reliability record.

## Running it

[guest-gates.yml](../../.github/workflows/guest-gates.yml) runs on Ubuntu 26.04,
every Monday at 04:23 UTC or through GitHub's **Run workflow** control. A scheduled
run first reads the latest completed run on the same branch. If that run succeeded
at the current revision, it skips the guest job before allocating its runner or
installing tools. New revisions, failed or canceled runs, absent history and failed
history lookups run all gates. Manual dispatch and explicit reruns always execute
them. The history job alone has `actions: read`; the gate job keeps `contents: read`.
It needs no repository secrets or initialized submodules. The public repository's standard
[runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
has 16 GB of RAM; the proof kernel recheck has historically exceeded 8 GiB,
so a smaller runner needs a separate resource measurement.

[bootstrap_guest.py](bootstrap_guest.py) installs only the missing Ubuntu packages
when passed `--install-system`, using root or passwordless sudo. Its `PACKAGES`
tuple owns that list. Python must satisfy [the manifest](../pyproject.toml), and uv
must match its exact pin before bootstrap starts. The script checks the downloaded
opam executable, imports the [package snapshots](../opam/README.md), and calls the
existing pinned Verilator installer. Package repositories provide the archive
checksums for the snapshot imports; distribution package versions follow the runner
image. This records a package resolution, not a bit-for-bit toolchain image.

On native Linux, from the repository root:

```sh
python3 tools/ci/bootstrap_guest.py --root "$HOME/build/guest-ci" --jobs 2 --install-system
. "$HOME/build/guest-ci/environment.sh"
python3 tools/run.py evidence --out "$VOS_LOG_DIR/evidence.json"
python3 tools/run.py model bundle --check
python3 tools/run.py rtl lint
python3 tools/run.py rtl crosscheck
```

For a Windows worktree, run inside WSL and substitute its assigned
`/root/build/lane-<name>/ci` root. Bootstrap refuses a nonempty directory it does not
own. Retrying the same owned root resumes switch imports. Its environment file sets
private opam, build, log, solver, temporary and compiler-cache directories; it does
not edit the user's shell profile or replace existing switches.

The workflow bounds each command and keeps independent checks running after a gate
failure. [report_guest.py](report_guest.py) retains their outcomes in `results.json`,
renders the job summary, and copies the proof receipt only when the evidence record
reports a successful proof member. The `guest-evidence` artifact retains logs and
receipts for 14 days. A canceled run may end before it uploads diagnostics.

uv downloads, opam's source download cache and verified Verilator source archives
are restored between runs; installed toolchains and evidence are rebuilt. The source
cache includes bootstrap's ownership marker so the restored private root can resume.
Its key includes the runner OS and architecture, Sail and Rocq snapshots, bootstrap
and Verilator installer. A prefix fallback reuses older source downloads, with the
installers' checksum verification still required. Cache eviction simply means a cold
installation. The evidence command owns concurrency between proofs and model
consumers; the remaining commands stay sequential within the runner's memory budget.

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

The pipeline runs the existing commands:

- `python3 tools/run.py evidence` builds and tests the model, runs the reference,
  profile, differential-corpus and device-tree checks, and checks the proofs.
- `python3 tools/run.py model bundle --check` compares the emitted model bundle.
- `python3 tools/run.py rtl lint` checks the standalone authored and generated RTL.
- `python3 tools/run.py rtl crosscheck` regenerates model vectors and compares RTL
  answers. Reusing old vectors is not part of this gate.

Each required command has a bounded execution time and retains its exit status.
Independent checks may still run after another fails when their bootstrap succeeded.
The evidence command owns its existing internal concurrency and freshness checks.
Download caches may accelerate installation, but a cache hit never establishes a
validation verdict. A cold run must work without any cache. Avoid caching built
model/proof outputs until their reuse is separately justified and measured.

## Acceptance and handoff

Acceptance requires a cold installation in an isolated Linux environment, followed
by the real commands above, with the tested source revision, platform, tool versions,
durations and results retained. A fixture-only test does not establish that the
upstream packages install or that a hosted runner has sufficient resources. A local
clean toolchain run and a GitHub-hosted run are recorded as distinct evidence.

Focused tests must cover installation planning and failure propagation, including
unavailable dependencies and corrupt downloads where the installer owns download
verification. Workflow syntax is checked with actionlint. The integrator runs
`python tools/run.py --check --tests` over the stable combined changes.

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
