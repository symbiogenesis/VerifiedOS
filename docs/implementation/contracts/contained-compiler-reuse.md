# Contained compiler build reuse

## Delivery contract

Q43 implements the user's 12 October 2026 request to make validated reuse the
normal build policy while preserving the four running Q39 producers. The private
compiler repository owns compilation and qualification semantics. VerifiedOS owns
the `compiler-build` front door, request framing and its lane-local cache index.
No compiler source, proof object or executable is incorporated into this public
repository. The existing containment and licensing rules remain applicable.

The first delivery implements whole-set audit reuse, authenticated compilation
reuse, explicit cold operation, bounded scheduling controls and future profiling.
It does not implement checker checkpoints, dependency-frontier sharding, a prover
change or a proof repair. The [source investigation](../contained-compiler-port-decisions.md#investigate-future-audit-reuse-without-interrupting-current-runs)
explains why incremental compilation cannot recover an interrupted checker.
No first-cold-run finish time or speed factor is an acceptance claim.

## Ownership and isolation

The new private worktree is based on integrated private revision `4173140f`.
Workers may change only its Q39 build helpers and new reuse validator/tests.
The original `ec5b825` and `6409d0ed` worktrees, their raw and qualification
outputs, archives, seals, logs, public lock, switches, packages, installed
libraries and tools remain unchanged. No signal, restart, installed-package
operation, producer reinterpretation or read from a live audit tree is part of
this implementation. Static Git objects and already exported helper copies may
be read. New execution and outputs belong to the new assigned lane.

The public worker owns `tools/vos/compiler_build.py`,
`tools/vos/cli/compiler_build.py` and their focused tests. The integrator owns
command registration, shared documentation, estimates, integration and final
gates. Before dispatch the integrator provides each dedicated worktree's absolute
path, branch, exact revision, files, checks and integrator.

## Request and driver boundary

`python tools/run.py compiler-build build|status` runs on the guest. Help may run
on either OS. The controller invokes the reviewed private `build.py` through a
versioned JSON request using protocol `verifiedos-contained-compiler-build/1`.
It supplies absolute native source/output/cache paths, an explicit immutable
source revision, the recorded lock, private opam root and switch, compilation
configuration, kernel profile, scheduling/profile requests, cold policy and an
optional resolved reuse candidate. It does not install anything.

A reviewed manifest binds the private driver and its complete project-local
import closure. Resolve each entry beneath the declared helper root, reject
escaping or unsupported entries and verify its bytes before and after the
operation. Bind the manifest digest in request/result records. The compiled
source revision and original producer identity are distinct from the current
controller/driver identity; changing a driver never relabels an old compilation.
Malformed framing, driver drift or an unsupported protocol refuses the operation.

Output and cache roots must lie in the explicitly assigned native lane. Hold an
exclusive operation lock, refuse output collisions and escaping/symlink paths,
and publish records atomically. Read-only status does not build, audit, repair or
rewrite prior evidence. Disposable requests and process working directories use
unique absolute Temp paths; preserve inherited system/profile variables.

## Default reuse policy

Normal builds consult a versioned lane-local index of this controller's earlier
validated outputs. The index is a lookup hint, never acceptance evidence. Lookup
binds source revision, lock, compilation settings, kernel profile and reviewed
driver/context identity. The private validator always rechecks the selected
candidate. No native-root scan or discovery of current C outputs is permitted.
Missing or stale default evidence records its reason and executes the necessary
phases. `--reuse-from` supplies an explicit bootstrap/override candidate; malformed
or unauthenticated explicit evidence refuses reuse rather than being ignored.

`--fresh` bypasses both reuse tiers and the index. Q39's two independent complete
qualifications continue to require their original fresh evidence. Cold Guest CI
and other existing fresh-check obligations remain unchanged. A requested new
profile output requires a new kernel execution; compilation may still be reused.

The index records only authenticated completed compilation or successful complete
qualification produced or validated by this controller. Pending audit state
cannot enter the complete tier. Atomic index updates retain the last useful
successful basis after a later failure. Referenced native artifacts and receipts
remain at their bound retained paths until their cache entries are retired; do
not relocate them or leave a lookup pointing at deleted inputs.

## Reuse predicates

Compilation reuse requires the seven successful export, configure, clean,
dependency, proof, extraction and compiler stages, authenticated pre-query seal,
stage logs, source archive and source/object/compiler/configuration populations,
exact lock closure, tools and installed-library inputs. Recheck bytes before
copying, after staging and after the operation. Preserve every stage's original
argv, producer identity, source revision and timings. Copy into a new owned
qualification tree and execute the complete qualification when kernel evidence
is unavailable. A separately pending or failed audit supplies no kernel credit.

Complete qualification reuse additionally requires a genuinely successful full
kernel exit, exact whole-environment classification and stable final input
verdict; complete Make-derived roots and recursive dependency scope; bound query,
matcher and original producer identities; exact checker argv and matching kernel
profile; original seals/logs/receipts and current unchanged source/object/tool,
library, lock and configuration identities. Unsupported producer schemas or
missing, failed, changed or partial evidence cannot authorize this tier. The
validator explicitly supports each admitted historical producer format; it never
passes an old seal through a new producer or fabricates a fresh execution.

The complete tier may reference the validated existing compiler and receipts
without recompilation, queries or kernel execution. Current validation is a new
operation; original proof/build execution remains historical. No progress-log
prefix, timestamp, existing `.vo` or portable summary alone authorizes reuse.
The private validator is the single semantic owner; the public controller checks
its framing and phase relationships without maintaining a competing classifier.

## Reporting and controls

Every result identifies its protocol, requested/effective policy, source revision,
current driver manifest, compiler and receipt paths, original basis digests and
retention paths. Compilation, queries, kernel and classification each state
`executed`, `reused` or `not_run`. Reused phases name complete basis evidence and
original timings separately from current validation time. Failure and pending
status are distinct from success. Never report compilation reuse as kernel PASS
or earlier elapsed time as this operation's execution time.

Scheduling uses an explicit positive job limit, records actual commands and does
not increase concurrency on a cache hit. Profiling uses the locked checker's
supported option in the new owned output tree, with actual argv/output binding;
it changes no current producer. No benchmark is run locally and no measured
throughput claim is required for this delivery.

Focused controls must cover default whole-set reuse after priming, compilation
reuse followed by a fresh complete audit, cold bypass of both tiers, pending
kernel exclusion, profile mismatch/new-profile execution, source/object/compiler,
tool/library/lock/configuration drift, damaged receipts, unsuccessful
classification, original identity/timing retention, import-closure drift,
protocol/result inconsistencies, index poisoning/escaping paths, output collision
and locking. Fake drivers/fixture receipts in Temp establish controller and
validator behavior; they are not production compiler acceptance.

After a Q39 pair genuinely qualifies, perform one actual unchanged whole-set
reuse through the new front door and default index, showing no compilation,
query or checker execution and retained genuine basis digests. Preserve original
receipts. Do not start an additional full cold compiler audit merely to test this
cache. If real evidence reveals an unsupported prerequisite or new failure, stop
that path for a scoped replan; keep all original producers running.

The private implementation is initially bounded to three candidates or forty-five
active minutes; the public controller to three candidates or thirty active
minutes. Editing and focused-check waits count. At the limit finish the current
check and return evidence for integrator replanning. Neither budget authorizes
new proof search, installations or terminating any job.

Completion requires reviewed implementation, the focused controls and genuine
default-reuse case, settled public `main`, Host CI passing and every cold Guest CI
lane dispatched under the repository handoff. Guest verdicts remain pending until
the user reports them. Finer incremental scheduling and cold-check performance
changes need separately scoped qualification; they are not silently included in
this first reuse delivery.

## Implementation checkpoint

The public controller, command registration and default index are integrated on
public `main`. Focused controller validation at `f3d51ca9` passed sixteen controls,
strict Linux/Windows typing, Ruff and import discipline. The private primary
integrates worker `151a7919` at `e604e260`; its final focused fixture run passed
87 controls in 39.586 seconds. `audit.py` retains digest
`61c8f0f67c1975b3f4a1b73828dd40b9e2562c1ac8656f066fb692b5e1502138`.
The complete development interval is unmeasured; these check durations are not
implementation time or benchmarks.

Independent static review closes two malformed-receipt findings. Present stage
durations require finite, nonnegative numbers excluding Booleans; absent historical
measurements remain unknown. Successful compilation and kernel exits require exact
integer zero. The refusal controls update the captured receipt hashes before
asserting the semantic diagnostic. Retention follows the recursively authenticated
compilation ancestry, including original helper and artifact paths; serialized
retention lists alone supply no authority. The older direct source/output driver
requires explicit `--fresh`, so its cold route cannot silently become the normal
policy.

The integrator's bounded replans cover only diagnosed implementation defects:
one additional public fixture-refusal candidate with five active minutes; one
private retention/legacy-cold candidate with ten active minutes; and one private
timing/exit candidate with ten active minutes. A slow mocked test wrapper on the
Windows mount was interrupted with the integrator's authorization and retained as
incomplete evidence. Its replacement uses unique native Temp fixtures. No original
compiler producer was interrupted, restarted or changed. These decisions retain
completed work while refusing malformed evidence, and authorize no new proof search,
installation or cold compiler audit.

The actual guest front door and durable private driver agree on an empty-index
`status` operation: expected exit 1, outcome `unavailable`, every phase `not_run`,
no compiler or basis, and no output lane created. Its retained summary digest is
`f5fb86229d523b6c4459ee0a11bfec79d5f167c87f8d36b31da68dd186ab1fa9`.
The private development handoff digest is
`0eebda3f0207f704d64014a0e9a2974d5a165fd8e872aed93287027d360e48f3`.
Neither check establishes a genuine cache hit or compiler correctness. Q43 remains
open until an original Q39 qualification passes, its unchanged result primes the
index, and the following normal build reuses that exact complete evidence without
compilation, queries or checker execution. The required public validation handoff
remains pending with the shared batch.
