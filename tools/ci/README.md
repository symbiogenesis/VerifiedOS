# Guest CI contract

The guest pipeline validates the current curated model, proof sources and authored
RTL on Linux. It complements [host validation](../../.github/workflows/host-gates.yml).
Its initial triggers are manual dispatch and a weekly schedule; making it a required
pull-request check needs a measured hosted run time and reliability record.

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
