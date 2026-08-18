# VerifiedOS Capacity-Exhaustion Additions

## Scope

This document reviews the Linux BPF OOM patch series being developed for Linux 7.3 and Meta's oomd, then identifies the pieces VerifiedOS should add to its specification.

The conclusion is not to import an OOM killer. VerifiedOS deletes the conditions that create a Linux global OOM event: there is no online heap allocator, overcommit, paging, swap, reclaim, movable working set, or dynamically competing memory hierarchy. Its remaining issue is narrower and more general: finite precomposed pools can fill at runtime even though their storage is statically reserved.

The missing specification is therefore a deterministic capacity-exhaustion contract for bounded pools, not an out-of-memory subsystem.

## Source mechanisms reviewed

### Linux BPF OOM patches

The patch series separates two questions:

* When should an exhaustion intervention be invoked?
* What workload-specific policy should run when it is invoked?

It adds a generic BPF hook ahead of the existing kernel OOM killer and a PSI-triggered path. A policy may select a task or memory cgroup, or free memory by another mechanism, while the ordinary kernel killer remains the final fallback. The motivating argument is that victim selection depends heavily on workload organization and cgroup structure, while userspace daemons are difficult to keep reliable under severe pressure and require a separate deployment and telemetry pipeline. See [mm: BPF OOM](https://lwn.net/Articles/1019129/) and the [v3 patch summary](https://www.phoronix.com/news/Linux-OOM-BPF-2026).

The useful abstractions are:

* detection separated from action;
* workload-aware policy;
* group-level action rather than accidental process selection;
* intervention before terminal deadlock or livelock;
* a reliable execution context that cannot itself be starved;
* verification that an action made sufficient progress;
* a final bounded fallback when customized policy does not resolve the condition.

The BPF mechanism itself is unsuitable for VerifiedOS. Runtime-loaded policy, dynamic iteration over workload hierarchies, sleepable hooks, generic victim selection, and fallback into a second policy engine conflict with its finite admitted state space and static proof posture.

### Meta oomd

Meta's oomd uses cgroup v2 and Pressure Stall Information to observe the system holistically and act before the kernel OOM killer. PSI measures lost wall-clock time caused by resource shortages rather than merely counting allocated bytes. Oomd separates detectors from actions through a plugin system and commonly terminates an entire offending workload group. See the [oomd overview](https://facebookmicrosites.github.io/oomd/docs/overview.html), [Meta's design explanation](https://engineering.fb.com/2018/07/19/production-engineering/oomd/), and the [oomd source overview](https://github.com/facebookincubator/oomd).

The useful abstractions are:

* progress degradation is a better trigger than raw utilization alone;
* the recovery unit should coincide with an ownership and restart boundary;
* protected workloads need explicit policy rather than an inferred badness score;
* detector and action policy should be independently testable;
* repeated pressure and ineffective interventions require observability.

PSI itself has no direct VerifiedOS consumer. There are no reclaim, refault, compaction, paging, or swap stalls to measure. A dynamic plugin system is also the opposite of the platform's admitted finite policy.

## Existing VerifiedOS coverage

The current specification already provides most low-level mechanisms needed for deterministic exhaustion handling:

* `R-08-010` through `R-08-020` delete the online allocator and produce a checked static slot plan.
* `R-08-018` admits runtime-count-dependent fan-out as a fixed pool of precolored equal-size slots.
* `R-08-008` bounds quarantine and prices forced reclamation to the requesting principal.
* `R-11-021` through `R-11-026` provide finite population rungs and a hard tenant ceiling.
* `R-12-073` and `R-12-074` provide a deterministic supervision tree, restart backoff, and manifest-bounded authority re-grant.
* `R-14-009` through `R-14-011` define a fixed origin pool and browser-owned victim selection beyond its live ceiling.
* `R-16-001` through `R-16-005` define crash-only restart and layered recovery.
* `R-17-030m` requires repeated degraded-subset entries to be counted rather than hiding a durable denial behind successful per-incident containment.

The gap is that these mechanisms are stated separately. There is no uniform contract saying what every finite runtime-occupancy pool must expose, how exhaustion is detected, which action owns it, how completion is proved, and what happens when the first action does not restore usable capacity.

## Missing pieces to add

The identifiers below are provisional. They are intended to become ordinary atomic requirements in `spec.md` and `requirements-register.md`.

## 1. State explicitly that global OOM is unreachable

Suggested placement: §8, immediately after the static memory plan.

### Proposed requirement `R-08-CAP-001`

The admitted machine has no global out-of-memory execution state. Every physical byte, kernel object, stack, register-save area, DMA window, ring, grant slot, quarantine slot, interpreter object slot, and recovery workspace is charged to the signed composition. Aggregate physical insufficiency rejects the generation at admission and never invokes runtime victim selection.

### Proposed acceptance condition

For every admitted generation, the checker derives a closed capacity equation covering application payloads and all platform metadata. No runtime path requests unplanned physical storage from a global pool.

### Why this is missing

The specification strongly implies this result but does not name global OOM as an unreachable state. Naming it prevents a later “safety” daemon, emergency allocator, or global victim selector from entering as an apparently harmless fallback.

## 2. Define a generic bounded-pool object

Suggested placement: §8 after `R-08-018`.

### Proposed requirement `R-08-CAP-002`

Every resource whose backing storage is static but whose occupancy varies at runtime is a declared bounded pool. Its manifest entry states:

* owning compartment;
* element type and fixed capacity;
* authority needed to bind and release an element;
* binding and release state machine;
* low and exhausted thresholds;
* maximum time from release request to reusable state;
* exhaustion action;
* recovery reserve, if any;
* confidentiality label of occupancy and telemetry;
* restart and generation-migration semantics.

Candidate pools include origin compartments, connection/session slots, grant slots, quarantine entries, protocol control blocks, fixed interpreter-object arenas, device descriptors, ring entries, checkpoint transaction slots, storage epochs, and sentinel event records.

### Proposed acceptance condition

The requirements register contains an inventory of every runtime-varying pool. No unclassified counter, bitmap, free list, object arena, queue, or table can influence admission or forward progress.

### Why this is missing

`R-08-018` explains how a zero-fragmentation pool is laid out but not the generic semantics of selecting, exhausting, releasing, and recovering its members.

## 3. Add a relevant capacity-exhausted verdict

Suggested placement: §5 relevant-verdict rules and §8 bounded pools.

### Proposed requirement `R-08-CAP-003`

A request to bind an element from a full pool returns a typed, relevant `CapacityExhausted(pool_id)` verdict. The verdict cannot be ignored, converted to an implicit wait, or replaced by borrowing from another pool.

### Proposed acceptance condition

The TAL derivation proves that every capacity-producing operation handles the exhausted arm through one of the manifest-declared actions. No capacity request can block indefinitely or fall through to an ambient supervisor decision.

### Why this is missing

VerifiedOS has no `malloc` failure, but it still has pool-binding failure. That failure needs the same must-examine discipline already applied to malformed inputs and security verdicts.

## 4. Separate detection from action, but close both sets

Suggested placement: §12 control plane.

### Proposed requirement `R-12-CAP-001`

Capacity handling is expressed as a finite composition-time mapping from an enumerated detector to an enumerated action. The mapping is compiled into the existing synchronous Lustre control plane. No runtime-loaded policy, plugin, BPF program, script, rule parser, or generic callback may participate.

Permitted detectors should initially be limited to:

* `pool_low`;
* `pool_exhausted`;
* `oldest_wait_exceeds_bound`;
* `quarantine_backlog_exceeds_bound`;
* `release_did_not_complete_by_deadline`;
* `restart_rate_exceeds_bound`;
* `population_ceiling_reached`;
* `checkpoint_space_unavailable`.

Permitted actions should initially be limited to:

* refuse the new request;
* shed optional owner-local state;
* suspend a manifest-named tenant;
* checkpoint and terminate a manifest-named tenant;
* terminate an ownership-closed group;
* advance to a lower pre-certified population rung;
* disable a nonessential service;
* restart the owning subtree;
* fail stop the owning subsystem;
* escalate to RoT reset where already authorized.

### Proposed acceptance condition

Every detector/action pair is visible in the signed composition and has a finite transition proof. No detector searches the component graph and no action computes a victim score at runtime.

### Linux/oomd lesson retained

Retain policy separation and workload specificity; reject dynamic policy injection.

## 5. Replace PSI with typed forward-progress signals

Suggested placement: §§11, 12, and 16.

### Proposed requirement `R-12-CAP-002`

Capacity intervention is triggered by resource-specific progress signals, not aggregate physical-memory utilization. Each signal has a fixed sampling cadence, public threshold, bounded reaction time, and declared observer label.

Useful signals include:

* remaining entries in a bounded pool;
* age of the oldest waiter or queued request;
* number of quarantined but not reusable entries;
* number of failed binding attempts in a fixed window;
* completion age of teardown, zeroization, checkpoint, or sweep work;
* ring occupancy only where the occupancy label permits observation;
* repeated restart or eviction count.

### Proposed acceptance condition

The detector's latency and reaction slot are admitted under §11. Signal collection performs no scanning proportional to the number of compartments and cannot alter another partition's schedule.

### Why this differs from PSI

PSI measures lost execution time caused by dynamic reclaim and other shortage stalls. VerifiedOS should instead measure whether a declared finite protocol is approaching or violating its progress bound.

## 6. Reserve the recovery path completely

Suggested placement: §§11, 12, and 16.

### Proposed requirement `R-16-CAP-001`

Every capacity-recovery path is pre-funded in memory, schedule, NoC bandwidth, storage transaction space, grant slots, and telemetry capacity. Recovery performs no operation whose own success depends on the exhausted pool.

The reserve must include:

* supervisor and sentinel execution slots;
* restart and teardown metadata;
* revocation and quarantine bookkeeping;
* zeroization and sweep progress state;
* checkpoint transaction capacity where checkpoint is an allowed action;
* one terminal fault record even when the ordinary telemetry ring is full;
* authority needed to quiesce DMA and revoke grants.

### Proposed acceptance condition

Fault injection that fills the target pool and all nonreserved adjacent queues cannot prevent the declared recovery transition from completing within its bound.

### Linux/oomd lesson retained

This captures the patch series' reason for moving policy into a context that remains reliable under pressure, without adding a daemon or kernel hook.

## 7. Make the recovery unit ownership-closed

Suggested placement: §§8, 12, and 16.

### Proposed requirement `R-16-CAP-002`

A capacity victim is never an arbitrary thread or internal process. It is a manifest-declared ownership-closed unit: a compartment, same-label compartment group, browser origin, application tenant, or complete supervised subtree.

Termination of the unit includes:

1. Stop future scheduled entry.
2. Quiesce or cancel bounded DMA.
3. Revoke exported grants and session handles.
4. Advance the relevant containment epoch.
5. Commit or discard durable state according to the declared action.
6. Zeroize private state.
7. Enter quarantine until the existing sweep establishes reusability.
8. Re-grant only manifest-fixed authority on restart.

### Proposed acceptance condition

The compositor proves that every object and grant owned exclusively by the unit appears in the teardown closure, while shared services and other labels are excluded.

### oomd lesson retained

The workload group, not a guessed individual process, is the correct unit of sacrifice.

## 8. Define criticality and sacrifice classes statically

Suggested placement: §§11 and 12 manifests.

### Proposed requirement `R-12-CAP-003`

Every dynamically occupiable tenant or pool member has one composition-fixed criticality class:

* non-sacrificable;
* suspendable;
* checkpoint-and-terminable;
* restartable without checkpoint;
* discardable.

The manifest also names any all-or-nothing dependency group and the ordered action ladder permitted for that group. Runtime focus may select among candidates only inside an equivalence class whose sacrifice policy is identical and whose selection observation is already permitted.

### Proposed acceptance condition

No lower-criticality principal can cause termination of a higher-criticality unit by consuming a shared pool. Critical capacity is physically or logically reserved rather than protected by a score adjustment.

### Linux/oomd lesson retained

This is the static equivalent of cgroup protection and workload-specific victim policy, without `oom_score_adj`, hierarchy traversal, or runtime scoring.

## 9. Require proof of effective reclamation

Suggested placement: §16.

### Proposed requirement `R-16-CAP-003`

An exhaustion action is not successful when a victim is merely marked dead. It succeeds only when the resource-specific completion predicate is true and the promised capacity is reusable.

For memory-backed pools, completion may require:

* execution stopped;
* DMA quiesced;
* authority revoked;
* zeroization complete;
* required checkpoint committed or intentionally discarded;
* quarantine sweep complete;
* at least the declared number of entries returned to `Reusable`.

### Proposed acceptance condition

Every action declares `reclaim_min` and `complete_by`. The monitor verifies both. If either fails, it executes the next pre-certified action in the finite ladder.

### Linux patch lesson retained

Customized policy must demonstrate actual progress; invoking a handler or killing a nominal victim is not itself proof that the shortage was resolved.

## 10. Make teardown idempotent and suppress duplicate victims

Suggested placement: §§8 and 16.

### Proposed requirement `R-16-CAP-004`

Each pool member follows an explicit monotone lifecycle such as:

`Free → Bound → Quiescing → Revoked → Sweeping → Reusable`

A repeated capacity trigger against a member already beyond `Bound` coalesces with the existing teardown. It cannot select a second victim merely because the first victim's storage has not yet become reusable.

### Proposed acceptance condition

Model checking covers repeated detector events, supervisor restart during each transition, duplicate release requests, and reset at every lifecycle state. At most one teardown owns a member and no member is rebound before `Reusable`.

### Linux lesson retained

Linux has historically needed explicit protection against selecting an additional innocent victim while the first OOM victim is still being reaped. VerifiedOS can remove that race structurally with a small monotone state machine.

## 11. Specify bounded owner-local shedding

Suggested placement: §12.

### Proposed requirement `R-12-CAP-004`

A pool owner may declare one optional owner-local shedding action before suspension or termination. The action runs only at an admitted quiescent point, consumes a fixed slot, touches only the owner's manifest-bounded state, and returns a relevant result naming the entries made reusable.

The system does not trust the result. It verifies the pool's completion predicate before considering pressure resolved.

### Proposed acceptance condition

The shedding action cannot receive extra time, allocate from a reserve, scan another owner, or delay the mandatory action ladder beyond a fixed bound.

### Why this is useful

This captures oomd's ability to take a workload-aware corrective action other than killing, while preventing cooperative cleanup from becoming an unbounded callback or a new source of scheduling feedback.

## 12. Generalize browser eviction into a platform contract

Suggested placement: §14 and the generic pool requirements.

### Proposed requirement `R-14-CAP-001`

The browser's origin-pool policy must declare:

* the exact victim equivalence class;
* whether focused, consent-bearing, audio-active, fresh-transaction, or non-checkpointable origins are protected;
* deterministic tie-breaking where multiple candidates are equivalent;
* whether the action is suspension, checkpoint-and-termination, or discard;
* the maximum time until the pool member is reusable;
* behavior when every origin is protected;
* repeated-eviction rate telemetry.

### Proposed acceptance condition

The browser may choose user-experience policy only within a statically bounded candidate set. It cannot alter slot width, borrow memory, evade quarantine, or terminate a different confidentiality label.

### Why this is missing

`R-14-010` currently delegates victim choice to the browser among its own origins. That contains authority, but it leaves progress, tie-breaking, protected states, and effective-reclamation semantics underspecified.

## 13. Clarify dynamic interpreter-object storage

Suggested placement: §§8 and 14.

### Proposed requirement `R-14-CAP-002`

Every interpreter whose guest can create a runtime-dependent number of objects uses a composition-sized fixed object arena conforming to the bounded-pool contract. The specification must distinguish this pool binding from the general online allocator deleted by `R-08-010`.

The arena must define:

* fixed object-size classes or a statically proved bounded representation;
* maximum live object count by class;
* selection and release algorithm;
* handling of cyclic guest graphs, if admitted;
* behavior when no object slot is available;
* whether guest-level collection exists and, if so, its complete WCET and non-interference model;
* host behavior after guest exhaustion.

### Proposed acceptance condition

No browser or Wasm/JS interpreter relies on an unspecified malloc, tracing collector, compactor, or variable-time emergency collection path. Guest exhaustion cannot consume host-reserved state or another origin's arena.

### Why this is high priority

The generic static-memory argument covers typed region lifetimes and bounded fan-out, while web JavaScript has input-dependent object creation and graph structure. The current browser text contains the failure boundary but does not fully state the object-arena mechanism that reaches it.

## 14. Add hysteresis, backoff, and escalation bounds

Suggested placement: §16 and `R-17-030m`.

### Proposed requirement `R-16-CAP-005`

Each detector/action pair declares:

* assertion threshold;
* clear threshold;
* minimum dwell time;
* maximum interventions per time window;
* restart or eviction backoff;
* escalation action after the rate limit is exceeded.

### Proposed acceptance condition

A workload oscillating at a threshold cannot create an unbounded restart, checkpoint, sweep, or eviction loop. The rate is included in the existing attested degraded-subset event accounting.

### oomd lesson retained

Sustained pressure, not a single noisy sample, should trigger disruptive action. VerifiedOS expresses this as a finite synchronous state machine rather than a tuned userspace daemon.

## 15. Add closed telemetry for capacity events

Suggested placement: §§12, 16, and 17.

### Proposed requirement `R-16-CAP-006`

Capacity events use a closed typed record containing:

* pool identifier;
* detector class;
* threshold and observed bounded value;
* selected ownership group;
* action taken;
* promised and actual reclaimed capacity;
* lifecycle state reached;
* completion latency bucket;
* escalation count;
* generation and population rung;
* terminal failure class, if any.

The record carries the pool's confidentiality label and is emitted through the existing sentinel telemetry path. No process list, pointer, free-form string, stack dump, or ambient log is generated.

### Proposed acceptance condition

The telemetry path retains one preallocated terminal record even when its ordinary ring is full, and logging failure cannot delay the recovery action.

### Linux/oomd lesson retained

A unified event pipeline is valuable; generic diagnostic dumps and separate daemon/kernel reporting paths are not.

## 16. Add capacity-exhaustion verification campaigns

Suggested placement: §§16 and 18.

### Proposed requirement `R-18-CAP-001`

The conformance suite generates exhaustion tests for every bounded pool and every action ladder. Tests include:

* fill to exactly capacity;
* one request beyond capacity;
* repeated concurrent-looking requests under the static schedule;
* crash during each teardown state;
* duplicate detector events;
* action that releases less than `reclaim_min`;
* action that misses `complete_by`;
* full telemetry ring;
* unavailable checkpoint space;
* stalled DMA quiescence;
* repeated threshold oscillation;
* reset during quarantine;
* protected-only candidate set;
* adversarial owner refusing to shed state.

### Proposed acceptance condition

Model checking proves the finite state machines; FPGA fault campaigns validate timing and reset behavior; the replay harness reproduces the detector and action sequence from the closed event record.

## Required fallback order

VerifiedOS should not have a universal OOM fallback. Each pool instead has a finite owner-local ladder. The default ladder should be:

1. Refuse the new request if refusal preserves the service's stated contract.
2. Run one optional bounded owner-local shedding action.
3. Suspend, checkpoint, or terminate one manifest-permitted ownership group.
4. Verify effective reclamation by the declared deadline.
5. Escalate to the next pre-certified group or lower population rung.
6. Restart the owning subtree if its pool protocol is inconsistent.
7. Fail stop the owning subsystem.
8. Reset only where the existing watchdog policy already authorizes it.

No action may borrow another partition's memory or schedule, weaken capability enforcement, skip quarantine, or dynamically invent a new victim class.

## Explicit non-additions

The following should be recorded as deliberate non-consumers rather than omissions:

* No PSI subsystem: reclaim/refault/swap pressure does not exist.
* No OOM daemon: the existing sentinel and supervisors already have reserved execution.
* No BPF or runtime policy hook.
* No global process or compartment scan.
* No badness score or usage-proportional victim heuristic.
* No cgroup-like dynamic hierarchy.
* No emergency allocator or hidden reserve reachable by applications.
* No global reclaim, compaction, paging, swapping, or cache dropping.
* No waiting for an application to voluntarily return capacity.
* No default kernel killer after custom policy fails.

## Suggested integration order

1. Add the explicit global-OOM absence theorem and bounded-pool definition to §8.
2. Inventory every runtime-varying pool in the requirements register.
3. Add the relevant `CapacityExhausted` verdict and pool lifecycle.
4. Extend the existing Lustre service-manager model with closed detector/action tables.
5. Add reserved recovery budgets to §11 admission.
6. Add effective-reclamation, duplicate-trigger, rate, and escalation rules to §16.
7. Tighten browser origin eviction and interpreter-object-arena requirements in §14.
8. Add typed telemetry and exhaustion fault campaigns to §§16–18.
9. Add the Linux mechanisms to `architectural-alternatives.md` as inspiration whose policy separation is retained while BPF, PSI, global victim selection, and daemon infrastructure are declined.

## Bottom line

The Linux patches and oomd do not reveal a missing memory-management subsystem in VerifiedOS. They reveal a missing specification layer around finite runtime occupancy.

The key addition is:

> Every runtime-varying resource is a statically funded bounded pool with a typed exhaustion verdict, a closed detector/action policy, an ownership-closed recovery unit, a reserved recovery path, a verified completion predicate, and a finite escalation ladder.

That imports the mature operational lessons of oomd and the BPF OOM work while preserving the architecture's stronger claim: physical memory never becomes globally overcommitted, and the machine never has to improvise who dies.

## Sources

* [Linux BPF OOM patch-series overview](https://lwn.net/Articles/1019129/)
* [Linux BPF OOM v3 summary](https://www.phoronix.com/news/Linux-OOM-BPF-2026)
* [Meta oomd overview](https://facebookmicrosites.github.io/oomd/docs/overview.html)
* [Meta engineering: Open-sourcing oomd](https://engineering.fb.com/2018/07/19/production-engineering/oomd/)
* [Meta oomd repository](https://github.com/facebookincubator/oomd)
* `spec.md`, especially §§5, 8, 11, 12, 14, 16, and 17
* `requirements-register.md`, corresponding atomic requirements
