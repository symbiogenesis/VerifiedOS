# Portable static-memory planning

This is an optional host research interface for bounded components. It implements
the placement and adapter work proposed in the desktop integration assessment.
The [requirements register](../requirements-register.md) governs VerifiedOS
admission; this library supplies no new production admission path. Q5b owns the
comparison on an actual composed workload, and Q22 owns qualified reuse evidence.

## Scope and planning horizon

A fixed memory plan can serve unpredictable requests when the number of concurrent
requests, their sizes and retention are bounded. The request contents and pool
occupancy can vary while the backing remains fixed. The planner therefore accepts
an allocation instance rather than requiring a tensor graph, Vela source or CHERI
capabilities. Its placement guarantee is conditional on the supplied instance
describing every permitted use.

Compile-time planning assigns backing from program structure and bounds.
Configuration-time planning specializes a bounded component before activation.
Repeatedly planning a new graph immediately before execution is another possible
desktop use, but does not satisfy VerifiedOS's prohibition on runtime placement.
The same algorithm must run at the horizon its deployment permits.

Useful non-ML boundaries include bounded service workspaces, parser and codec
scratch, packet queues, task frames, audio processing chains and render resources.
LLVM's [stack coloring](https://llvm.org/doxygen/StackColoring_8cpp_source.html),
Unreal's [render graph](https://dev.epicgames.com/documentation/en-us/unreal-engine/render-dependency-graph-in-unreal-engine),
JACK's [callback restrictions](https://jackaudio.org/api/group__ClientCallbacks.html)
and Linux's [memory allocation interfaces](https://docs.kernel.org/core-api/memory-allocation.html)
identify relevant existing boundaries. These are motivation, not implemented
adapters or evidence that every object in those systems can share storage. GPU
completion, escaped stack pointers and kernel allocation guarantees each require
their own integration argument.

The executable service example reserves independent worker slots and overlays
scratch only between exclusive phases of the same worker. Explicit conflicts
allow different workers to progress independently. Its reported reduction is
constructed arithmetic, not a measured application result. A late device user or
retained alias invalidates that overlay until the reuse contract permits it.

Arbitrary process growth, unconstrained browser state and variable file caches
remain online allocation problems on conventional desktops. Permanently
coexisting objects cannot overlap, and a private idle reservation cannot be lent
merely by improving placement. A virtual arena's span, committed pages, physical
residency and whole-system memory use are different quantities.

## Portable model and checked selection

The command uses the repository's ordinary tool environment:

```console
python tools/run.py memory-planner demo --json
python tools/run.py memory-planner contracts --json
python tools/run.py memory-planner resources --json
python tools/run.py memory-planner resources --resource-budget resources.json --json
python tools/run.py memory-planner resource-proof --resource-budget resources.json --json
python tools/run.py memory-planner plan --instance instance.json --baseline baseline.json --candidate candidate.json --work-budget 10000 --json
python tools/run.py memory-planner check --instance instance.json --candidate candidate.json --json
python tools/run.py memory-planner solve --instance instance.json --work-budget 10000 --certify --json
python tools/run.py memory-planner verify --instance instance.json --evidence result.json --json
python tools/run.py memory-planner demo-tflm --json
```

`--instance` names a JSON object with `name`, `pools` and `buffers`. Each pool has
an `id`, `capacity` and optional `reserved` half-open byte ranges. Each buffer has
an `id`, `size`, `allowed_pools` and optional `alignment`, `intervals`,
`fixed_pool`, `fixed_offset`, `alias_of` and `alias_offset`. Optional `conflicts`
adds object-id pairs; `assumptions` records the caller's premises. Unknown fields
are rejected. Placement files contain an array of `{id, pool, offset}` objects.
`demo --json` supplies a complete constructed instance and baseline to inspect.
The result's `placement` array is the ordinary return value; preserve the complete
result separately when replaying its evidence with `verify`.

The [core](../../tools/vos/memory_planner.py) models fixed-size objects, explicit
active intervals and conflicts, alignment, permitted pools, reserved ranges,
fixed locations and declared views. Instances and results preserve object
identity. Unsupported inputs fail explicitly; callers must not erase a field
to obtain acceptance. An inclusive lifetime adapter must check endpoint overflow
before converting to half-open intervals. Zero-size objects, integer ranges,
alignment and alias bounds belong to the contract rather than to solver guesses.
A conservative interval conversion can preserve safety while losing packing
opportunities from a richer branch or asynchronous conflict relation. Its
optimum applies to the converted instance, not automatically to that richer
behavior.

The ordinary result is a list of pool/offset assignments. A separate evidence
record binds the instance, checker, selected objective, assumptions and proof
endpoint. Evidence distinguishes checked feasible, checked optimal, checked
infeasible and unknown/unsupported. A timeout supplies no infeasibility or
optimality conclusion. A legacy adapter can expose fewer ordinary statuses only
while retaining the richer diagnostic record separately.

The planner first checks and retains the supplied baseline. It checks every
candidate independently and accepts only an improvement within the baseline's
componentwise pool limits. The selected objective and stable tie-break are
explicit. Search uses a deterministic work budget; a wall-clock race is not an
input to placement. Failure or exhaustion leaves the checked incumbent available.
An invalid baseline is refused, since it cannot establish the non-regression
premise.

The deterministic work limit covers the library's finite search and replay.
Optional synchronous candidate callbacks are caller code and must impose their
own resource limit; the library isolates their input data and catches failures,
but cannot preempt arbitrary Python computation. Production integrations should
run heavyweight generators off-device with their own bounded execution policy.

For unchanged instance `I`, valid baseline `P0` and declared objective `J`, this
selection rule establishes `Valid(I, result)` and `J(result) <= J(P0)`. It does not
establish shorter compilation, lower host memory, better cache behavior, fewer
bank conflicts or faster target execution. A smaller sum of pool heights can
worsen a scarce pool, hence the componentwise guard. Alignment, metadata,
representability and runtime evidence storage must be charged in any deployment
that requires them.

Scheduling changes, recomputation, splitting, movement and changed revocation
rules alter the feasible instance. They remain separate opt-in transformations
in the [existing research experiments](static-memory-experiments.md), rather than
transparent offset substitutions.

## Compatibility boundaries

The [adapters](../../tools/vos/memory_planner_adapters.py) and their
[pinned demonstration sources](../../tools/memory-planner/) identify exact upstream
interfaces. Model compatibility preserves the feasible instance. API/file
compatibility additionally preserves names, ordering, types and errors.
Operational compatibility additionally covers initialization resources,
execution cost and deployment behavior. An adapter demonstration establishes
only the boundary its tests exercise.

MiniMalloc is the standalone interchange target. Its rich representation includes
inactive gaps, fixed offsets, alignment and advisory hints; its simple CSV does
not express the whole model. A feasible solution below a supplied capacity is
not itself a global minimum. The adapter keeps placement checking separate from
the untrusted candidate generator.

ExecuTorch's algorithm suite already selects among planners. The additional work
here is candidate validation, retained fallback and scoped evidence. The adapter
must preserve the pinned callback's result structure, pool sizes, aliases/views,
bounded shapes and graph input/output policies. It cannot infer those conventions
from an older tutorial.

TFLite Micro supplies a replaceable planner interface. The demonstration exercises
its initialization, statuses, buffer identity, maximum extent and fixed-offset
conventions. Heavy search belongs on the development host; a small runtime plan
consumer does not eliminate persistent objects, weights or temporary allocations.
Tensor preservation and alignment are part of its caller contract.

The [idealloc candidate integration](static-memory-candidates.md) supplies an
optional research comparator behind the original checker and retained baseline.
TVM v0.18.0 USMP supplies useful pool/conflict prior art. XLA heap simulation and IREE Stream layout have additional
compiler-specific semantics. None is represented as a shipped universal allocator
ABI or as a current-main compatibility promise.

## Optimization evidence and extraction

Small finite instances can be exhaustively checked against their entire declared
address domain. The result must identify whether optimality is global for that
domain or restricted by the retained baseline's pool limits. Incomplete replay
cannot certify an optimum. Independent candidate feasibility and exclusion of
every better placement are separate obligations.

The [LRAT certificate experiment](static-memory-certificates.md) uses a pinned external
checker for a bounded Boolean encoding. Its verdict is portable research evidence
under R-05-011b and grounds no admitted placement or infeasibility claim. It does
not produce the instance-specific Rocq term R-05-015 requires, and it does not
complete Q27a or override that item's refusal of an imported admission checker.
DRCP and CakePB are comparison ecosystems with their own encoding and execution boundaries. Decoding
solver solutions to legal placements establishes only one direction: excluding
all better layouts additionally requires every legal better layout to have an
encoded witness. No external certificate dependency is admitted merely by naming
one of these systems. The [literature adoption map](static-memory-literature.md)
states each relevant donor's disposition and the evidence for adopted techniques.

The [contract extractor](../../tools/vos/memory_planner_contracts.py) models bounded
control flow, exceptional outcomes, retained authority and device completion.
Its conflicts cover the permitted paths and independent request slots. Its proof
states the relation between those modeled hazards, the reuse gate and a legal
placement. The remaining compiler obligation is to show that an actual program
refines this contract; a caller-supplied completion time does not prove that a
physical device has finished. [MemoryPlannerContracts.v](../../proofs/MemoryPlannerContracts.v)
proves conflict-graph separation, the conjunction required by the reuse barrier,
and checked-selection non-regression. Temporal ordering of interpreter events is
an executable check; its refinement to that mathematical model is not proved.

The [resource-aware contract layer](static-memory-resource-contracts.md) ties
bounded credits and release obligations to independently checked fixed backing.
Free-byte totals alone do not establish a suitably shaped allocation. Its finite
proofs and executable evidence preserve the source and target refinement boundary.
`resources` preserves the replayable report under `resource_contract`, alongside
the command's input-file and source hashes. `resource-proof` additionally emits
`rocq_source` for the finite credit and deadline facts; emitting that text does
not certify it until Rocq checks it. `--replay-budget` bounds resource analysis.

R-05-104 excludes ILP machinery from the required toolchain; R-05-105 restricts
admitted verified analyses whose only yield is bound tightening. This optional
host library uses bounded finite search and introduces no ILP dependency. It does
not reconcile those rules by silently expanding their exceptions. A future
production solver or verified optimizer requires an explicit register decision.
R-08-012b continues to exclude sampled profiles and runtime feedback from
production placement inputs.

Q5b still needs measured savings and planning cost on the real roster, and the
product gate needs target timing, physical capacity and service qualification.
The fast checked baseline remains available while an expensive offline mode is
evaluated. Those measurements address costs the non-regression argument does
not establish; they are not a vote on the argument itself.
