# Workflow profiles, app hibernation and reusable slate slots

This design and qualification contract interprets the [requirements register](../requirements-register.md), which remains authoritative. The lifecycle and transition proofs, executable presets and target measurements are open under Q32 in the [implementation checklist](implementation-checklist.md). A preset recipe is not an implemented application. Literature was checked on 19 September 2026; the source findings below distinguish published results, implementation documentation and preprints. No source or implementation is incorporated by this survey.

## Decisions and scope

Adopt application-level hibernation and finite, composition-checked slate-slot rebinding as the route to larger foreground working sets. Retain bounded capability revocation and its complete reuse barrier. Defer a general variable-size runtime heap allocator: dynamic occupancy and reclamation of preassigned slots already serve the bounded case, while a new allocator needs evidence that those representations cannot serve a required workload.

Statically verified multi-mode scheduling means a finite graph of admitted steady states **and admitted transitions**. It is a local design description, not an ARINC 653 conformance claim or an existing end-to-end theorem. The useful IMA precedent is integration-time resource assignment and selection among known schedules. Removing a partition from a schedule does not itself reclaim its memory or close its capabilities.

The current specification already has population rungs, origin-pool eviction, bounded exhaustion ladders, whole-program placement and revocation completion. Their missing join is an explicit application lifecycle with storage, authority, schedule and capacity evidence at the same boundary. Q22a's [revocation qualification](../assurance/revocation-qualification.md) supplies a reviewed barrier interface and finite host experiment; it supplies neither a running hibernation service nor its machine proof.

## Three separate selections

* A **power mode** selects the admitted operating points, fabric timing, watchdog windows and memory power vector. Its change retains the explicit-authority, RoT-attested global path.
* A **workflow profile** selects a finite admitted app roster, slate bindings, foreground budget, background service roster and checkpoint policy. Selecting it grants no document, network, microphone or other authority. A profile that changes power or fabric settings uses the global path; a local profile keeps those settings and the reserved band fixed.
* **Focus and population** use the existing discretionary slot permutations and rungs. A focus change alone neither hibernates a protected app nor proves its old backing reusable.

Composition checks reachable combinations of all three selections and every permitted edge, rather than assuming their Cartesian product is safe. A compact factorization is acceptable only with a composition theorem. Unknown combinations and edges have no runtime synthesis path. Adding a recipe or changing a budget requires generation admission; ordinary selection among already admitted profiles does not reboot or load executable code.

## Preset recipes

These authored recipes guide composition. Concrete bytes, periods, maxima and latency ceilings come from the selected applications and hardware, with an explicit unavailable result for a missing port or a combination that cannot fit. They are not measurements or promised capacity multipliers. The browser remains deferred under R-18-004; no preset silently enlarges the mobile release floor.

| Recipe | Foreground working set | Explicit continuing work | State to preserve and qualification case |
| --- | --- | --- | --- |
| Everyday | Launcher, selected app and a small admitted live roster | Product-floor services and separately consented communication | Safe default and return destination; open-app records survive while private working sets can be hibernated |
| Writing | Word processor, selected document, bounded layout and undo state | Optional spellcheck and an explicitly selected messaging service | Restore unsaved edits, cursor and bounded undo; an uncheckpointable transaction prevents hibernation |
| Browsing | Shared engine and a bounded set of distinct origin compartments | Explicit audio, download or notification services within their own reservations | Preserve declared page/session state; frozen pages still cost RAM; discard/reload is labeled and cannot promise arbitrary JavaScript heap continuity |
| Image editing | Selected image, tiles, preview and bounded edit history | Explicit export task only if admitted alongside interaction | Commit edit history and tile references; charge restore and export overlap, not just the final image |
| Messaging | Conversation UI and bounded attachment state | A small separately budgeted receive/notification service | Hibernating the UI cannot promise live reception without that service; bound queue growth and declare offline/missed-event behavior |
| Development | Editor, source view and selected build/proof/composition phase | Only explicitly admitted terminals and services | Build pools belong to R-13-027a's composition mode; outputs execute only in a successor generation; checkpoint source/diagnostics, not arbitrary compiler stacks |

Voice, radio, display, storage, revocation, consent and required inference reservations remain present wherever the product contract requires them. The ordinary mode must still meet the simultaneous mobile floor; development builds are scored in their separate composition mode under R-13-027a, with that distinction explicit in every comparison. Each recipe names allowed companion apps; unsupported side-by-side combinations are unavailable instead of silently thinning budgets. A user can select a different admitted profile or compose a new generation.

## Lifecycle and the meaning of zero

The lifecycle distinguishes **active**, **background-service**, **frozen-resident**, **quiescing**, **checkpointed-retiring**, **hibernated**, **restoring**, and **closed**. These are proposed contract states for Q32's formalization, not a claim that a state machine is implemented. A background service is a separately charged live component; calling its UI inactive does not erase its cost. Frozen-resident removes app execution while keeping its backing and authority inventory charged.

For successful hibernation:

1. At a declared boundary, stop new app work, close ingress, and complete or cancel bounded operations. Preserve a protected transaction or refuse the transition; no forced loss of undeclared unsaved work is success.
2. Commit a bounded, authenticated semantic checkpoint under the existing storage transaction and freshness policy. Bind app identity, schema, generation compatibility and confidentiality label. Ordinary document checkpoints retain the bulk-data rollback residual; security-critical state uses the existing declared Fresh class and its endurance budget. Reserve checkpoint space and scratch before starting. A missing commit leaves the prior recovery point intact and grants no successful hibernation claim.
3. Retire app authority through the existing register, saved-context, loan, proxy and device barrier. A checkpoint contains data and logical object references, never a raw tagged heap, register image, executable payload, live grant or reusable session key. Closing an external session has an explicit reconnect or failure result.
4. Complete the post-barrier sweep and required data/tag sanitization. Only the full resource-specific `Reusable` predicate releases backing. A timeout retains quarantine and follows the already admitted failure ladder; it never counts elapsed time as completion.
5. Publish the hibernated record. The app then has zero private volatile working-set bytes and zero app execution slots. Its bounded manager record, durable checkpoint, immutable image/shared engine and continuing services remain charged to their declared owners.

Restore reserves an admitted destination, zeroes and initializes it, authenticates and validates the checkpoint, reconstructs objects using freshly issued bounded capabilities, and re-evaluates current grants. It runs only already admitted code. No revoked grant, expired lease or old device/session authority is revived. A stale schema, incompatible generation, revoked document access or failed restore gives a declared recovery/refusal result. Across reboot, only declared durable state survives; this is not a raw machine resume path.

Functional proof target: restoring a successfully committed checkpoint refines the app's declared resume semantics for document state and permitted external effects, including any explicit reconnect behavior. It does not assert identical network sessions, elapsed time or observations by remote peers. Crash cases after each protocol step must preserve acknowledged durable work and prevent two live owners of one slate slot.

## Slate-slot rebinding and memory accounting

A **slate** is a bounded collection of open-app records; a **slate slot** is a preassigned physical working-set arena that one of a composition-enumerated set of app instances may occupy. Swapping a slate slot means checkpoint, retire, sanitize and rebind at a checked lifecycle boundary. It is not page swapping, demand paging, live capability relocation, executable loading or arbitrary borrowing from another pool.

The plan fixes every allowed app/slot binding, bank/island, memory class, alignment, exact capability bounds, maximum extent and cross-slot interference. Simultaneously permitted apps have distinct backing. App code remains in the immutable admitted image; only private data arenas are candidates for this saving. Restoring data reconstructs references for that slot's fixed layout rather than copying old physical pointers. A successor becomes runnable only after both reuse and transition admission hold.

For a candidate composition, compare actual placed spans under one byte ledger:

```text
capacity needed >= max over reachable steady and transition states of
  (resident image and permanent services + live/frozen private backing
   + checkpoint/restore workspace + quarantined backing
   + lifecycle, capability and allocation metadata)
```

Physical overlap is charged once, and only after a proof that occupants cannot coexist through the complete reuse endpoint. Separate arenas and storage capacity have separate ledgers. The maximum private live payload is only a lower bound on placed span. Checkpoint bytes retained in RAM still count as RAM; durable checkpoints instead consume bounded store capacity, write endurance, encryption work and I/O slots. No saving assumes compression; the existing filesystem-compression exclusion remains in force.

Foreground growth is a precomputed destination binding, not an online extension of an existing object's capability. Serialized switching can reuse a large arena without reserving both complete app heaps simultaneously, but still reserves the scratch, quarantine and uninterrupted services required along the edge. Report both steady-state saving and transition peak. A slow storage write or revoker can make the transition infeasible even if both endpoint profiles fit.

## Transition certificate and failure semantics

Each permitted directed edge supplies its request authority and observation policy, guard, entry phase, carry-in work, retained tasks, bounded queues, checkpoint size, revocation holder set, sweep coverage, zeroization bytes, restore work, memory peak, deadline and failure destination. Frame alignment and the first service after switching are part of the certificate. All reservations for calls, radio and other continuing tasks hold across the edge, including re-phasing; endpoint schedulability alone proves none of this.

The controller serializes transitions, bounds pending requests and enforces a composition-fixed minimum dwell or equivalent request-service bound. Repeated toggling must not starve foreground service, fill checkpoint space, exceed storage endurance or create an unpriced sweep backlog. No request from a compromised app may change another label's allocation using secret activity or pressure. User selection is an explicit observation in the policy, with event timing and rate accounted for; a finite number of profiles alone is not an information-flow proof.

A request that cannot meet its guard leaves the current admitted state running and reports a bounded refusal. After destructive teardown has begun, failure follows a declared recovery state with reserved capacity; it cannot promise to restore the old live instance instantly. Local app failures cannot halt protected services. The edge identifies its commit point and covers power failure before and after it through the existing storage/boot contracts.

## Revocation decision and bounded heap reuse

Keep the CHERIoT-style bitmap/load filter plus scheduled software reclamation. Hibernation makes revocation more relevant: a malicious prior occupant can otherwise keep a pointer into the next foreground app. Zeroing bytes alone leaves stale authority; marking a bitmap alone leaves resident registers; stopping execution alone leaves saved contexts and in-flight transfers. R-08-006 and R-08-007a remain mandatory.

Within a compartment, prefer linear/affine release, regions and fixed pools. A lifetime theorem can establish that a local alias no longer exists, but the compiler must connect it to machine roots and asynchronous completion. It cannot silently delete the existing reuse gate for a revocable slot. An optimization that removes a scan needs its own reviewed equivalence argument and normative amendment. A quota on `malloc` limits occupancy but does not prove safe reuse, bounded fragmentation, bounded allocation latency or a reclamation deadline.

There is no unconditional constant-time heap reclamation claim. The composition bounds holder footprint, retirement burst, queueing, barrier service and sweep service. Quarantine capacity must cover the declared burst and service delay; exhausted capacity refuses new occupancy without borrowing. `free requested`, containment complete and reusable are different events. CHERI-TAL's source-level no-use-after-free discipline and hardware revocation's completion point must be stated separately.

The downgrade is the **general heap allocator proposal**, not temporal safety, grant retraction or compartment teardown. Reopen that proposal only when a required, ported workload fails fixed-pool/region/segmented alternatives under the same useful-function and memory budget. Its comparison must charge worst-case search, metadata, internal/external fragmentation, zeroing, scan traffic, quarantine and refusal behavior. The current no-online-placement rule remains in force until a separate architecture decision changes it.

## Literature findings and transfer limits

The search covered hibernation/checkpoint and browser lifecycle, IMA/ARINC 653 reconfiguration, real-time mode-change protocols and formal separation kernels, then CHERI heap revocation and newer temporal-safety architectures. It found useful pieces, not an artifact proving this entire storage, authority and scheduling composition. The primary ARINC standard text was not available in this review; implementation documentation and research are not a standards audit.

| Source | What it contributes | What this design still owes |
| --- | --- | --- |
| [Phan, Lee and Sokolsky, *A Semantic Framework for Mode Change Protocols*, RTAS 2011](https://repository.upenn.edu/bitstreams/04dbc612-960f-43fe-a3c7-f2078d21c313/download) | Models transitions explicitly, including pending events and buffer state, with decidable feasibility analysis for its model | Instantiate state, timing and buffer semantics; prove capability retirement, storage effects and information flow separately |
| [Nélis and Goossens, *Mode Change Protocol for Multi-Mode Real-Time Systems upon Identical Multiprocessors*, 2008 preprint](https://arxiv.org/abs/0809.5238) | Synchronous transition protocol that separates old work from new releases | Transfer the transition reasoning, not its processor/scheduler assumptions, to the cyclic executive |
| [Chisholm et al., *Supporting Mode Changes while Providing Hardware Isolation in Mixed-Criticality Multicore Systems*, RTNS 2017](https://oscarlab.github.io/papers/rtns17a.pdf) | Studies mode changes together with hardware isolation and shared-resource allocation | Its mixed-criticality platform is not this no-cache, no-MMU design; no direct timing or memory-gain transfer |
| [*Towards fault-tolerance of IMA with safe dynamic reconfiguration*, CEAS Aeronautical Journal, 2024](https://link.springer.com/article/10.1007/s13272-024-00771-5) | Prototype router with statically allocated resources and alternate configurations | The paper expressly leaves safe runtime switching outside its scope; routing or schedule selection is no hibernation/reuse theorem |
| [Zhao et al., ARINC 653 Event-B formalization, 2015](https://arxiv.org/abs/1508.06479) and [refinement/security analysis, 2017](https://arxiv.org/abs/1702.05997) | Formal specification and separation-kernel security analysis; the latter reports information-flow flaws found through verification/review | Specification coverage and mechanized security results do not prove this implementation, its changing ownership map or checkpoint restore |
| [Chrome Page Lifecycle API](https://developer.chrome.com/docs/web-platform/page-lifecycle-api) | Distinguishes freeze from discard; discarded pages reload and have no running callbacks | App-visible resume semantics and protected-state policy must be explicit; freezing is no RAM reclamation guarantee |
| [Linux software suspend documentation](https://docs.kernel.org/power/swsusp.html) | Whole-system memory snapshot/restore with filesystem and device constraints | Raw whole-machine hibernation is a different contract from semantic app checkpoints and the measured-boot-only executable path |
| [Chajed et al., *Verifying concurrent, crash-safe systems with Perennial*, SOSP 2019](https://pdos.csail.mit.edu/papers/perennial:sosp19.pdf) | Machine-checked Iris/Coq crash-safety reasoning, versioned volatile resources and recovery ownership; demonstrated on a concurrent mail server | A useful proof method for checkpoint commit and restore, not a CHERI hibernation theorem. The paper's safety proofs do not supply liveness or this transition's WCET |
| [CRaC project documentation](https://crac.github.io/) | Coordinated application hooks release and reacquire resources that a process snapshot cannot preserve, such as external connections | Use explicit resource lifecycle contracts; cooperative Java callbacks neither prove bounded quiescence nor contain a malicious compartment |
| [Filardo et al., *Cornucopia*, IEEE S&P 2020](https://www.ietfng.org/nwf/_downloads/28d1512e48d653c95bb34be10a925eda/2020-cornucopia.pdf) | Practical sweeping revocation for CHERI heaps | Finite throughput results do not bound this composition's register/device barrier or worst-case quarantine |
| [Filardo et al., *Cornucopia Reloaded*, ASPLOS 2024](https://www.repository.cam.ac.uk/items/16823172-d2b8-426e-944e-ca956fb205f8) and [CheriBSD temporal-safety documentation](https://ctsrd-cheri.github.io/cheribsd-getting-started/features/temporal.html) | Load barriers reduce stop-the-world pauses; allocator quarantine and completed revocation epochs gate reallocation | Morello per-page/VM acceleration is not available here. Protection against stale authority reaching a new allocation is distinct from rejecting every access immediately at a source-language `free` |
| [Amar et al., *CHERIoT: Complete Memory Safety for Embedded Devices*, MICRO 2023](https://www.microsoft.com/en-us/research/uploads/prod/2024/02/cheriot_complete_memory_safety.pdf), [allocator guide](https://cheriot.org/book/memory.html), [core RTOS guide](https://cheriot.org/book/core_rtos.html) | MMU-free temporal-safety co-design, quotas, claims and software/hardware revoker choices | Use the claims/loans and register reasoning; keep this design's software-only sweep, own capability format, fixed service and no unbounded foreign claims |
| [Wang et al., *PoisonCap*, May 2026 preprint](https://arxiv.org/abs/2605.13210) | Proposes hierarchical poisoning, stronger free-time checking and initialization support | Requires changed capability/memory semantics; not evidence to reinstate an initialization plane or autonomous mechanism here |
| [Wang et al., *CHERI-D*, June 2026 preprint](https://arxiv.org/abs/2606.19055) | Inline object IDs for temporal checks and lower revocation cost | Price capability-format, ID exhaustion, metadata access and fixed-latency changes before any replacement decision |
| [Wang, Woodruff and Moore, *CHERI-D Reincarnate*, 10 September 2026 draft](https://arxiv.org/abs/2609.11590) | Quarantines exhausted IDs rather than immediately quarantining the associated memory; adds coherent ID caching | ID supply/reclamation remains finite. Coherence and caching assumptions conflict with this platform; no bounded worst-case or formal-composition claim is imported |

The newer temporal-safety proposals are candidates for a future measured comparison, not grounds to remove bounded revocation today. The main actionable literature finding is to prove mode edges and app resume semantics with the same rigor as steady states, and to charge all retained and retiring state when claiming a foreground-memory gain.

## Qualification sequence

Q32a freezes a finite formal model and its interfaces before implementation. Q32b connects one checkpointable editor-like app and one competing image-workspace app to the actual storage, kernel and schedule paths. Q32c instantiates the preset catalog against available ports and compares frozen residency, semantic hibernation and fixed-pool reuse on the same workload.

Required refuting cases include an endpoint-safe but transition-overloaded schedule; two bindings overlapping during quarantine; a stale register or saved capability; a late DMA or bridge reply; incomplete checkpoint or replay of security-critical state; out-of-space during commit; protected unsaved state; crash at each commit boundary; failed restore after old-state retirement; rapid repeated profile requests; and a profile that drops a standing service to manufacture a saving. Generated finite traces should supply cases where a model oracle exists. Passing host examples supplies no target WCET, physical erasure or universal refinement evidence.
