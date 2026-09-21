# Optional Isla campaign

Run `python tools/run.py sail-isla provision` once in an isolated worktree, then
`python tools/run.py sail-isla qualify --json`. Windows dispatches these native
commands into WSL; Linux uses `python3`. Provisioning explicitly downloads and
builds optional tools. Qualification performs no downloads. Both operations hold
a lane lock. Native source checkouts, Cargo caches, Rust installation, compiler
prefixes and campaign outputs live in the checkout's assigned native lane;
command and oracle logs use the lane's standard log names.

The prerequisites are the repository's locked baseline Sail opam inventory,
pinned Z3 shared library, Git, a C compiler and binutils. Provisioning checks the
opam package inventory and Z3 version. It reads the baseline switch without
installing into it. A separate development Sail executable and Isla plugin are
built in the lane. The primary compiler is unchanged.

`lock.json` fixes the standalone Isla revision, isla-testgen revision and its
different Isla submodule revision, development Sail archive digest, and Rust
1.90.0 component digests for Linux aarch64 and x86_64. Standalone Isla uses its
tracked upstream Cargo.lock. The authored driver's Cargo.lock fixes the testgen
dependency graph; ordinary builds use `--locked`. The explicit
lalrpop-util lexer feature supplies a feature required by upstream's generated
ACL2 parser without editing upstream source. The build does not request the
optional web or litmus executables, LLVM, or a new opam solution. Cargo still
builds transitive libraries required by the two selected crate graphs.

The report checks the provisioned binaries and build-input digest before use.
Changing a recipe or asset requires provisioning again. The report also records
current curated source hashes, generated IR hash, baseline compiler/runtime
inputs, optional binary hashes, invocation arguments, logs, and control outcomes.
The baseline's dynamic system libraries remain prerequisites; these checks are
input identification, not a hermetic-build or authenticity guarantee.

## What the campaign decides

The source roster comes from the existing capformat oracle spec. The model files
are snapshotted byte-for-byte into the native campaign directory. Authored Sail
wrappers call the actual curated `perms_expand`; they concatenate the input code
with its output so a solver witness identifies both. Isla symbolically executes
a four-bit shape separately for local and global permissions. Each invocation
must yield exactly 16 distinct concrete witnesses, covering all 32 five-bit
permission codes together. Missing, duplicate, malformed or errored results fail
the operation.

The Rust driver uses isla-testgen's public
`execution::run_function` API to replay those generated codes through the same
Sail IR and apply `perms_narrow` to their expanded masks. The existing
`vos.sailrig` separately compiles a fresh harness with the locked primary Sail C
backend. All 32 generated expansion results and testgen's expansion/narrowing
pairs must match that oracle. Python handles orchestration, parsing and
comparison; it does not implement permission semantics.

Three fresh staged-source controls establish what the campaign detects:

- A permission-table semantic mutation must compile and change an observed case:
  `killed`.
- A bounds-exponent mutation outside this campaign must compile and leave its
  cases unchanged: `survived`. This demonstrates the campaign's coverage limit.
- An undefined-name mutation must fail compilation: `build_rejected`. It is
  never counted as a killed mutant.

A successful report requires those three distinct outcomes. Failure before a
complete comparison returns a nonzero exit status without a partial JSON report.
A completed campaign with an unexpected control outcome writes a report with
`passed: false` and exits nonzero. The version 1 report follows
[report.schema.json](report.schema.json).

## Deliberate limits

This integration exercises Isla symbolic execution and isla-testgen helper
execution. It does not implement an RV64 instruction Target or invoke testgen's
architecture-specific instruction/object generator. It generates fresh concrete
function cases from symbolic execution, not instruction programs. There are no
memory, register-state, concurrency, full-ISA, or hardware claims. Narrowing is
tested on the 32 expanded masks, not all 4096 input masks. The PC and memory layout
fields in campaign.toml are required configuration scaffolding; the wrappers do
not use them, and unused external tool slots deliberately point to /bin/false.

The optional plugin supports fewer constructs than Sail and enables its own
SYMBOLIC rewriting settings. Compiler/plugin rejection is a failed build, not
evidence of a model defect. Solver/path success and finite differential agreement
are advisory evidence, never a universal proof or a substitute for normal gates.

No upstream source is vendored here. The optional fetched tools retain their own
license files. See the repository's THIRD-PARTY.md for incorporation and license
details. The local Rust driver, configuration, Sail wrappers and Python recipe are
authored under the repository's Apache-2.0 terms.
