# Optional static-memory candidate generators

The portable planner can consume the real pinned
[idealloc](https://github.com/cappadokes/idealloc/tree/3b7eb67f234905ebccb90e252b220189770c9dcb)
implementation as an untrusted candidate generator. Its original algorithm runs
through an [authored Rust bridge](../../../tools/memory-planner/idealloc/bridge.rs).
The [portable checker](../portable-memory-planner.md) checks every returned identity,
offset and original constraint before selecting a result. Failure, timeout,
unsupported input or a worse candidate preserves the checked baseline. This is
an optional host research integration, with no production admission authority.

## Reproduction and ordinary use

```console
python tools/run.py memory-candidates demo --json
python tools/run.py memory-candidates plan --instance instance.json --baseline baseline.json --timeout 30 --iterations 1 --json
python tools/run.py memory-candidates logs --json
python tools/run.py test --only memory_planner_candidates
```

The runner selects the native guest lane. The build, Rust installation, Cargo
cache and evidence live beneath that lane's `memory-planner-idealloc` directory.
No upstream source is vendored into the tracked tree. The exact revision, source
file hashes and reviewed MIT license are in the
[pin manifest](../../../tools/memory-planner/idealloc.json). The upstream copyright
and permission notice remain in the downloaded workspace. Registry dependency
licenses and source identities are recorded separately in the build receipt.

The bridge is the only added upstream binary target. The upstream algorithms and
dependency lock remain unchanged. Cargo builds only `coreba` and the bridge.
Rust 1.85.1 and its installer are pinned; installation modifies no shell profile
or global toolchain. The build checks every downloaded upstream file, checks
Cargo dependency archives against the pinned lock, and checks unpacked dependency
files against those archives. Archive members are inspected without extraction
by this adapter, with traversal and special-entry refusal. Rustup and Cargo own
their installation and extraction steps. The candidate executable is hashed
before and after each invocation. These identities describe execution inputs;
they are not compiler-correctness or source-to-model theorems.

`plan` accepts the same instance and placement JSON as `memory-planner`. It
validates the baseline before building or invoking optional search. It returns
the selected ordinary placement with the portable evidence, upstream diagnostic
record and build identities. `latest-evidence.json` and `build-evidence.json`
record the latest successful command and build in the guest directory. `logs`
reads bounded tails of setup and compilation logs through the guest command.
Malformed or invalid baselines are refused; an optional generator failure can
still return a successful checked plan by retaining its valid baseline.

## Supported semantics and execution limits

This adapter accepts a single unreserved pool, positive sizes, unit byte
alignment, one nonempty lifetime interval per object, and no aliases, extra
conflict edges or fixed offsets. Other portable-model features are refused,
including richer models that could be approximated conservatively. A refused
field is never discarded to make the upstream call succeed. Object counts and
total size also have explicit reviewed limits in
[the adapter](../../../tools/vos/memory_planner_candidates.py).

The core uses half-open lifetimes. Idealloc's `Job` operations use open discrete
intervals. For all distinct endpoints, the adapter assigns increasing ranks
and maps `[start,end)` to `(2*rank(start),2*rank(end))`. Each positive interval
has an interior point; endpoint ordering and equality are preserved. Thus
adjacent intervals remain disjoint and every original overlapping pair still
overlaps. Logical time is compressed, while byte sizes remain exact. The
conversion tests include adjacent, nested, crossing and large-endpoint cases.

The pinned algorithm is stochastic. Its proposed offsets and time can vary;
the library does not convert a random proposal into a deterministic-result
claim. The iteration parameter and subprocess timeout are explicit. The timeout
limits candidate execution, independently of compilation and downloads. One
Rayon worker limits the upstream's large per-worker virtual stack reservation.
This does not establish a resident-memory bound or a worst-case execution time.
The checker and fallback, rather than upstream diagnostics or its reported
makespan, decide whether the candidate can be used.

## Comparison evidence

`demo` constructs adjacent, equal-size overlapping, mixed crossing, nested,
moving-window and mixed-duration traces. It reports the complete instances,
their hashes, separate-storage spans, a deterministic size-first-fit candidate,
the actual upstream candidate span, and the independently checked selected span.
The local first-fit code applies the existing heuristic family to the portable
interface; it is not idealloc code or a new optimization result.

Small traces also run the portable exact search and independent finite replay.
The report preserves their actual status rather than treating a cutoff as an
optimum. Larger traces carry a separately computed live-load lower bound; that
bound need not be an attainable contiguous span. Every trace additionally
injects a corrupt proposal and verifies rejection with its baseline retained.
If upstream execution fails, the comparison reports that failure even though
ordinary checked fallback remains available.

Elapsed values are measurements from the current run, including the indicated
Python checking work. These synthetic traces are not the paper's benchmark
suite, a composed VerifiedOS roster, target timing evidence, or a demonstration
of the upstream paper's large-instance scaling claims. Repeated execution may
change timings and stochastic candidates. The
[existing scaling and transformation experiments](experiments.md)
remain separate artifacts and predate this adapter.

## Disposition of the allocation literature

| Review entry | Concrete disposition in this integration |
| --- | --- |
| 14, OPT versus LOAD | Preserve the distinction between a live-load lower bound and a legal contiguous optimum; report both without assuming equality. The existing baseline proofs and witnesses already study this distinction. |
| 15, constant-bounded allocation | Its relocating profile is not enabled by offset substitution. This adapter has immutable placements; an explicit movement transformation and its costs belong in the existing transformation program. |
| 16, request fragmentation | Segmentation changes the allocation interface and feasible set. It is not applied to this contiguous-buffer adapter. |
| 17, memory reallocation | Live-object movement, handle updates and outstanding device users require a separate profile and cost proof; this adapter implements none of those mechanisms. |
| 18, idealloc | Adopt the actual pinned implementation as an optional untrusted producer, with strict conversion, a subprocess limit, independent checking and retained fallback. |
| 19, OLLA | Joint lifetime/schedule optimization remains a separate transformation. This integration fixes the supplied lifetimes; the existing transformation experiments are not an OLLA dependency or a general schedule optimizer. |
| 20, TVM USMP | The portable pools/conflicts/alignment boundary already follows this useful architectural precedent. No TVM implementation or ABI is imported by this work. |
| 21, CAMS/checkpointing | Retain recomputation as a separately specified space/time transformation for replayable computations. This candidate adapter does not change execution schedules or claim a checkpointing optimality theorem. |

The [idealloc paper](https://arxiv.org/abs/2504.04874) motivates adopting an
implemented candidate generator. The placement checker supplies the acceptance
boundary. The [static-memory research agenda](../../background/static-memory-research.md)
and its existing experiments own changes to movement, segmentation, scheduling
and recomputation assumptions; naming these donors does not discharge those
separate semantic and physical-cost obligations.
