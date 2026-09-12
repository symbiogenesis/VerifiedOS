# Interior mutability and interference contract

> Non-normative Q25c rule dossier. These interfaces specify proposed Vela semantics and qualification cases, not an implemented library, proved calculus or admitted executable. The [requirements register](../requirements-register.md) governs the platform. Missing laws remain obligations for Q25d; schematic predicates below declare no axioms.

## Scope and shared interface

The [full-language commitment](verification-strategy.md#interior-mutability-guardrails) admits local cells, checked dynamic borrowing and proved concurrent protocols. Each cell exposes a sealed state-transition interface. Its client receives the operation rights that its actual grant permits; neither a handle's representation nor its grade permits arbitrary access to the representation.

Q25a's `graded-foundation.md`, under `resource-and-computation-interface`, supplies the common interface. `Gamma` is a stable dependent telescope with computation-use vector `u`, type-use vector `v` and dependency rows. `Delta` interprets owners, loans and protocol obligations in the selected resource logic. Computations transform `Delta` into an outcome-indexed resource predicate, separately carrying captures, effects, event counts, representations and exit obligations. This document specializes that interface and the [synchronous core](core-design.md#judgments-and-interpretations); it does not supply a second resource interpretation.

`Capture`, `Dup`, `Dispose`, `Suspend`, `Transfer` and `Share` require semantic evidence. A numerical use grade can count an invocation only under its trace interpretation; it cannot construct an owner, authorize a hardware access or discharge an outstanding release. `Own(r,shape,snapshot)` lives in `Delta`; the stable identity `r` and a historical snapshot can occur in `Gamma`. No type index reads unsynchronized changing cell contents.

The concrete qualification below uses private packet and task storage plus a shared scalar counter. It introduces no mutable shared capability, compare-and-swap, blocking mutex, retry loop, inner scheduler or new source unwind path. The [current atomic profile](../spec.md#r-15-026) and [exclusive-access theorem](../spec.md#r-05-096a) remain entry constraints, not conclusions supplied by this dossier.

## Representation, authority and open invariants

A library declaration supplies the stable cell identity, execution domain, fixed footprint and layout, lifetime and generation, contents type, invariant, allowed transitions, interference relation, operation rights and the representation linking those objects to memory. Concrete CHERI permissions, tags, provenance, temporal state and initialization remain part of that representation. The invariant is not accepted merely because the author gives it a name.

The proposed proof interface is schematic:

```text
CellDecl(c, domain, generation, footprint, representation, invariant, protocol)
Closed(c, state) * OpRight(c, operation) * Frame
  -- operation --> Exit(result, Closed(c, state') * Returned(result) * Frame)

open:  Closed(c, s) * OpenPermit(c, scope)
       -> Open(c, scope, s) * Representation(c, s) * CloseDebt(c, scope)
close: Open(c, scope, s) * Representation(c, s') * invariant(s')
       * CloseDebt(c, scope) -> Closed(c, s')
```

These expressions describe proof transitions, not instructions that extract a resource from a duplicable proposition. The library must prove that its opening permit is exclusive, its invariant mask excludes reopening the same invariant, and no overlapping representation permission remains outside the opened region. Nested opening follows a declared acyclic order and excludes conflicting footprints. The frame rule and each allowed interference step preserve all resources not borrowed by the operation.

A local opening has one execution domain and no possible interfering activation until closing. A concurrent invariant opens only around a proved logically atomic operation, or within an explicitly proved exclusive ownership phase. An AMO's indivisibility does not make an arbitrary surrounding read/modify/write block atomic. Closing consumes the exact close debt once, restores the current representation rather than an old snapshot, and ends every interior loan before an operation returns.

All raw representation primitives remain sealed. Their source and final-code access rules must exclude forged handles, pointer casts, exposed fields and untyped helpers that bypass the invariant. A CHERI pointer with load/store permissions alone does not establish the matching ownership state. [R-05-096b's binary splits and manifest join](../spec.md#r-05-096b) remain necessary even if every source component accepts independently. Shared scalar addresses resolve through capabilities injected into private participant state at composition; an integer cell identity received in a message never grants a capability.

## Local cells

`LocalCell(d,c,T,I)` is confined to execution domain `d`. Its abstract state is `Full(v)` with `I(v)`, or an explicitly supported `Empty` state. A fixed representation carries any stored authority exactly once. A private cell may hold an owner or capability if its representation and lifecycle support it; that permission does not transfer to concurrently shared storage.

| Operation | Entry and result contract |
| --- | --- |
| `snapshot` | Establish a stable mathematical value related to the current representation during one authorized observation. An executable copy additionally requires a duplicable contents representation and declared destination storage. |
| `replace(new)` | Consume the new represented value, prove `I(new)`, install it and return the old value by move. No copy of either owner survives inside the cell. |
| `take` | Available only for a cell whose invariant includes `Empty`. Move the value out, leave `Empty`, and make operations requiring `Full` return a typed empty result. |
| `put` | Consume `Empty` and one owned replacement; return `Full` under its invariant. An occupied-cell result returns the unconsumed replacement. |
| `with_update(f)` | Open the invariant and pass a scoped view to a callback with checked transitive effects and captures. Every callback outcome closes the invariant and returns no interior view. The contract states whether an error preserves the entry value or returns a valid changed value. |

A read of an authority-bearing `T` does not clone it. Such a cell offers an authorized scoped observation, a pure projection whose proof retains no authority, or a move through `take`; it cannot implement an unrestricted `get : T`. `replace` also needs an explicit disposal path for any displaced value the caller does not retain.

The scoped callback cannot suspend, capture control, invoke an unknown or reentrant callee, publish the view, or capture it in its result, closure, cell, task, continuation or exception-like encoding. A lexical lifetime marker alone is insufficient: the result's whole transitive capture closure must exclude the opening's identity and every descendant loan. Disjoint outside resources remain usable under a checked frame law. The default rule also excludes a call through another alias of the same cell while its invariant is open.

## Checked dynamic borrows

`BorrowCell(d,c,T,I)` supports aliases within one domain using a represented borrow state and sealed guard identities. Its states are `Idle(v)`, `Readers(v,S)` and `Writer(v,g)`, with `S` a bounded finite set of live read guards and `g` the unique write guard. Runtime storage may use a bounded reader count plus statically accounted guard slots; correspondence to the logical identities, count overflow exclusion and every decrement are proof obligations. The state word is ordinary local memory; it is not a concurrent lock.

| Transition | Required result |
| --- | --- |
| `try_read` from `Idle` or `Readers` | Allocate a guard from declared capacity, preserve the same immutable contents, suspend conflicting writes and return a scoped read view. |
| `try_read` from `Writer` | Return `BorrowConflict`; leave cell and caller resources unchanged. |
| `try_write` from `Idle` | Produce one scoped write guard, suspend all overlapping parent access and open the representation under its close debt. |
| `try_write` from `Readers` or `Writer` | Return `BorrowConflict` without a view or partial state change. |
| Reader capacity exhausted | Return the declared capacity verdict, with no counter wrap and no guard created. |
| Release read guard | Consume its identity once, remove exactly that reader, and restore `Idle` only when no reader remains. |
| Release write guard | End descendants, prove the invariant of the final value, consume guard and close debt, and restore `Idle`. |

The public API brackets guards with `with_try_read` and `with_try_write`; library-internal guard values cannot escape that scope. Conflict and capacity are relevant results that clients must examine. A missing drop, duplicated guard, repeated release or forged reader decrement is a rejected resource derivation. A guard that is merely affine in a usage algebra still owes release; there is no garbage collector or implicit unwinding to perform it.

Reader guards permit compatible reads but no mutation of their footprint. Writer guards exclude every overlapping read or write, including one through the parent cell, a second wrapper, a device or a stored closure. Reborrowing suspends the affected parent until descendants end. Both guard scopes use the default no-suspension/no-capture rule, including a ready `await`; a future stable read-guard suspension extension needs a distinct `Suspend` law, represented lifetime and cancellation release proof. The conflict branch itself executes only the sealed borrow-state operation, with no callback and no second opening.

## Snapshots and dependent indices

`Snapshot(c,e,x)` states that observation event `e` justifies immutable value `x`. The event is a logical witness unless the application separately represents it; it is not a silently added runtime version counter. Snapshot evidence does not imply `current(c) = x`, supply a read permission or permit access using `x` as a current length after mutation. Observing a concurrent scalar yields a value at one linearization point, not a coherent snapshot of a separate payload.

For example, take a local packet cell with fixed capacity `N`, represented length `n` and bytes `xs`, with `length(xs) = n <= N`. A snapshot yields stable `n0` and `xs0`. Replacing the packet with length `n1` changes its resource predicate. An index `i < n0` still indexes `xs0`; it indexes the current packet only after fresh permission and a proof of `i < n1`. If a shape change affects the owner's type, the operation consumes the old owner and returns a new dependent pair, with `n1` represented and only the inequality proof erased.

A copied snapshot of several fields requires exclusion throughout the copy or a separately proved snapshot protocol. Loading fields individually, surrounding a racing non-atomic copy with a sequence counter, or making each payload byte atomic does not establish that protocol. Publication of a complete immutable payload is the selected way to expose several fields consistently. Refinements retained across a call must be stable under that call's actual interference relation; a hidden getter or callback that can write invalidates current-content facts exactly like an explicit write.

## Transfer, sharing and lifecycle eligibility

Eligibility follows fields, instantiated type parameters, environments, tasks and stored continuations transitively. A representation boundary can hide implementation details from clients only with a checked theorem exposing its actual captures and operations to the verifier.

| Predicate | Evidence required |
| --- | --- |
| `Capture(v)` | Whole transitive set of retained identities, permissions, loans, close debts and terminal obligations; distinguish temporary evaluation effects from retained state. |
| `Dup(v)` | Duplicating the represented value and its associated resource predicate preserves ownership and all protocol obligations. A duplicable descriptor does not duplicate an access grant. |
| `Dispose(v)` | Exact disposal transition for stored owners, must-erase values, guards and relevant results. An unknown finalizer is no evidence. |
| `Suspend(v)` | Stable represented storage, closed invariants, permitted live loans, preserved obligations and a bounded resume/cancel path at the checkpoint. |
| `Transfer(v,d1,d2)` | Sender loses access before receiver gains it; every retained field is transferable and remains live. Cross-compartment transfer conforms to the fixed grant/manifest protocol. |
| `Share(v,D)` | All participants have separately justified operation rights; the contents representation, permitted interference and observation policy remain sound under simultaneous use. |

The default `LocalCell` and `BorrowCell` interfaces have no cross-domain `Share` law. Moving a quiescent local cell requires no outstanding guards, loans or open debt, loss of all old-domain handles, and a proved transfer/rebinding of its domain and storage. A wrapper, newtype, effect grade, unrestricted callback grade or hidden local/thread-local variable cannot bypass those premises. [Absence of ambient mutable state](../spec.md#r-05-039) includes caches, registries and lazy initialization behind apparently pure methods.

Capabilities used to access a shared scalar cell remain in each participant's private injected environment. Shared mutable memory holds only the declared scalar contents, never those capabilities, a closure containing them, a task frame, or a capability-bearing continuation. A capability-bearing continuation may remain in private stable storage. Any ownership transfer of it must use an independently proved protocol consistent with the platform's fixed authority graph; serializing its pointer into a shared cell is not that protocol.

## Concurrent protocols and the actual memory model

`ConcurrentCell(c,g,S,P)` supplies an abstract state machine `P`, allowed interference steps, participant roles, scalar representation `S`, operation rights and linearization/release points. Each operation states its functional relation, how it preserves the shared invariant, which resources move at publication, and what another participant may observe. A successful atomic operation supplies a single transition only at its proved linearization point. Failure paths must establish their declared unchanged or partial-effect state rather than invent rollback.

The selected target is the [Ztso profile](../spec.md#r-15-004), including its [whole-memory-path ordering obligation](../spec.md#r-15-015a). The [retained Sail AMO implementation](../../model/model/extensions/A/zaamo_insts.sail) decodes `AMOADD`, computes a word addition and writes the result; [memory access](../../model/model/sys/mem.sail) supplies its classified accesses. These are inspected operation subjects, not a checked Vela-to-Sail atomic rule or a proved concurrent logic instance.

Every lowering law must name the same pinned Sail term, exact width and alignment, capability load/store permissions, PMA support, tag behavior, `aq`/`rl` bits, and the allowed observation events. Ordinary memory, MMIO and DMA are not interchangeable. No operation silently widens a sub-word access across neighbors, synthesizes CAS/LR-SC, calls a locking `libatomic`, or depends on unsupported atomic capability access. Atomic types permit only the proved atomic operations; a plain non-atomic alias into their footprint is not an alternative access path.

### Immutable publication and reclamation

The concrete multi-field interface uses the [existing SPSC lifecycle](../spec.md#r-12-094): exclusive writing finishes initialization before submission, publication consumes writable ownership, readers acquire only immutable published access, and reclamation restores writing only after every reader and device holder has ended or been revoked with the required quiescence. Shared descriptors contain indices and scalar lengths; the receiver resolves them against its own privately held table and validates generation, extent and rights before access.

Publication requires payload stores before the publication-index store, plus any producer loads before that store. Consumption requires the load observing publication before later descriptor/payload loads and later consumer stores. These are respectively store-to-store/load-to-store and load-to-load/load-to-store edges. The proof must obtain them from Ztso, the actual compiler preservation theorem and the fabric's per-hart ordering; a source annotation alone provides none. This is the [canonical fence-free ring contract](../spec.md#r-12-008), not permission to omit an ordering premise.

Ztso does not supply general store-to-later-load ordering. Reclamation needs explicit terminal acknowledgments and ownership transitions, not an inference from a local store followed by a load that a peer has stopped. A proposed protocol needing the missing edge must name a legal drain fence and prove its actual semantics and bound, or choose another proved protocol. No fence cures overlapping non-atomic authority. Release of a guard, publication of data, cancellation acceptance, terminal completion and physical reuse are distinct transitions.

Generation changes before reuse across restart or revocation under [R-12-099](../spec.md#r-12-099). Old handles and queued indices become unusable; a same-valued index or count does not establish freshness. Reuse requires retirement of every old-generation operation right, not just observing an empty scalar counter. Pool reuse also retains [R-08-046's lifecycle](../spec.md#r-08-046), including quarantine, revocation and sweeping where applicable.

## Concrete scalar service and composed client

The proposed qualification cell is `CountCell(c,g)`: one aligned atomic `u64`, initially zero for generation `g`, representing the sum of committed accepted packet lengths. It is arithmetic state only. It contains no payload, pointer, request identity or capability. Each participant has a privately injected capability and an operation right for its declared use of this cell. An integer handle in `Gamma` identifies the cell without creating those rights.

`AddOnce(c,g,k,n)` is a unique protocol resource in `Delta`, naming a live request `k` and stable runtime packet length `n`. It is not a grade and not a pure proposition that the program can copy. The generation owns a finite set of allowances whose total `sum(n)` is at most `U64_MAX`. Issuing allowances consumes that conserved bound; cancelling or committing retires each allowance once. New traffic needs a fresh accounted allowance or a new quiescent generation, never a wraparound assumption or a read-then-check race on the counter.

```text
commit_add(private_handle, AddOnce(c,g,k,n), represented n)
    -> Added(c,g,k,n,old)

cell transition: value = old  -> value = old + n
resource transition: AddOnce -> one committed receipt
target candidate: one aligned AMOADD.d, aq = false, rl = false
```

The AMO is the operation's commit and linearization point. Its source contract promises atomic counter arithmetic only. It promises no publication of other memory, no stable current value after return and no ordering between the old values returned to different clients beyond the required atomic history. The conserved allowance bound proves this particular word addition equals mathematical addition. The two ordering bits are part of the proposed lowering law, not an existing proof; a stronger API needs separately justified bits and ordering. A numeric callback grade alone proves neither occurrence of this AMO nor consumption of its allowance.

The combined Q25 client uses runtime packet length `n <= N`, a graded callback over a justified immutable packet snapshot, a handler, and a cancellable child. The handler's multi-shot portion retains only resources with a `Dup` law. The unique packet owner, frame owner and `AddOnce` stay outside that captured delimiter. The callback's occurrence contract and the handler's multiplicity compose into a checked demand bound, while `commit_add` remains a single child action outside the multi-shot portion. The child can share only the counter's authorized operation interface, not its private owner through the counter. Effectful arguments are evaluated once through explicit sequencing; a zero or repeated use grade neither erases nor repeats their cell transitions.

An inhabited entry candidate fixes `N = 4`, `n = 2`, a private initialized packet `[1,2]`, a separate immutable callback environment invoked twice by the pure handler, unused declared frame/completion slots, live private counter grants, counter value zero, and one allowance of two. Two concurrently authorized children may instead have lengths three and two, disjoint private packets/frames, and allowances totalling five. Either AMO order gives a final value of five after both joins; the intermediate observation may be three or two. This is a proposed entry witness for the chosen representation law, not a claim that those concrete CHERI resources are currently constructed in Rocq. Q25d must construct and check them, including the private grants and schedule premises.

### Cancellation, completion and reset

The child performs its final cancellable checkpoint before `commit_add`, following [R-12-097](../spec.md#r-12-097). From that checkpoint through the AMO and recording the committed receipt in its private frame is one bounded region with no suspension, capture, reentry or source-fallible operation. Cancellation remains sticky during that region. A request that arrives after its checkpoint and before the AMO is resolved at the next declared decision point as post-commit; arrival is not itself a preemptive cancellation point.

| Reachable outcome | Cell and resource result |
| --- | --- |
| Cancel before child starts | No AMO occurs; retire the allowance, return the private packet and unused frame resources, and publish an examined `cancelled` terminal result. |
| Cancel observed at the pre-commit checkpoint | Close prior scopes, retire the allowance without changing the counter, clean private state and join `cancelled`. |
| Commit succeeds | Consume the allowance at the AMO, retain the receipt until normal terminal completion, and record that the increment cannot be replayed. |
| Cancel after the checkpoint/commit region begins | Resolve at the next decision point; once committed, answer `too_late` and finish normal completion. Do not subtract the increment or repeat the request. |
| Stale or nonexistent request | Answer `not_live` under the declared generation/request-state test, without obtaining an allowance or accessing a stale grant. |
| Frame or completion capacity unavailable | Return the pool's typed capacity result before starting, retaining unstarted input resources and creating no AMO obligation. |
| Parent stops waiting | The scope still owns the child and its packet/frame until terminal join; a wait timeout releases no authority. |
| Generation restart or environmental fault | Follow fail-stop, revocation and quiescence. No source-cleanup execution, normal completion, preserved counter total across generations or implicit replay is assumed. |

The selected operation has no DMA holder, so its DMA-quiescence field is `n/a`; it still needs task/reader quiescence and pool lifecycle evidence before reuse. An extended operation that lends the packet to DMA must keep the loan until the HAL's declared completion/quiescence predicate holds. Returning `too_late`, dropping a user handle or observing the increment is not such a predicate.

Completion publication is separate from counter arithmetic. It uses a declared private completion record or immutable SPSC publication with the ordering and ownership premises above. Joining all terminal records and retiring every old-generation right permits the final scalar observation and reset protocol; a counter reaching an expected value alone permits neither reset nor parent-storage reuse. A concurrent observation during live traffic is a historical scalar sample. Its atomic-load lowering law must establish single-copy atomicity at the exact width and alignment; a multi-field snapshot theorem is not inferred from it.

## Exit closure and bounded progress

Every operation carries outcome-indexed resource predicates. For ordinary source exits, the default contract admits only paths restoring the cell invariant and ending all scoped guards; it cannot defer release to a destructor whose behavior or execution is unproved.

| Exit or control event | Closure obligation |
| --- | --- |
| Fallthrough, ordinary return, `Result` success/error propagation | End descendants, consume close/release debts and establish the tagged outcome's exact cell state and returned resources. Errors need not roll back unless their contract says so. |
| `break`, `continue`, bounded-loop back edge | Close iteration-local invariants/guards and restore the loop predicate before transferring control. |
| Effect operation, callback or reentrant call | Close first if it can capture, suspend or reenter. A certified local callback may run inside only under the scoped contract excluding those effects and result captures. |
| Ready or pending `await`, cancellation checkpoint | Closed invariants, no default guard scopes, stable frame storage and an explicit `Suspend`/cleanup derivation. Ready status does not remove the checkpoint. |
| Handler discard or multi-shot resumption | Account for transitive `Dispose` or `Dup`; an open debt, guard or allowance defeats an unsupported discard/duplication premise. |
| Accepted cancellation | Enter bounded cleanup with the invariant closed, retire or return every retained token, and join terminal completion before reuse. |
| Cleanup failure | The default local close/release primitives are total under their premises. An API with fallible external cleanup needs an explicit quarantined terminal state and a proved containment path; it cannot return ordinary reusable ownership. |
| Panic, trap or environmental fail-stop | No language exception/unwinding rule is added. Prove absence of unexpected traps under operation premises; external faults stop the affected domain/session and retain its revocation/quiescence obligations without asserting successful source closing. |

An operation declares maximum local steps, distance to the next checkpoint, cleanup work, terminal-publication work, child joins and any external quiescence bound. Admission maps those steps into the [cooperative reaction graph](../spec.md#r-07-037a) and [schedule proof](../spec.md#r-11-006). With `Lcheckpoint` the maximum elapsed scheduled time to observe a request and `Lcleanup`, `Ljoin`, `Lterminal` the corresponding admitted bounds, the proposed accepted-cancellation bound is their proved composition, not their unexplained sum over incomparable units. Post-commit completion has its own remaining-protocol bound. The no-checkpoint AMO region must fit the declared local bound and cannot defer a pending request indefinitely.

No fairness assumption, spin-until-success loop or eventual peer response is hidden in a cell operation. A terminal bound names the admitted activation schedule and, where used, the service/HAL response bound; adversarial failure instead reaches the specified fail-stop outcome. Capacity exhaustion remains an immediate typed result with bounded handling. Hardware-fault recovery is a different guarantee from normal source progress.

## Qualification cases and rejection neighbors

These are semantic derivation and execution targets for future qualification. All negatives must parse and elaborate in the same supported fragment as their positive neighbors, reach a satisfiable entry state, and fail at the named premise. Parser failure, missing syntax or an inconsistent precondition is no safety evidence.

| Case | Expected accepted derivation or first rejected premise |
| --- | --- |
| Local replacement returns an owner by move | `replace` changes the invariant and returns exactly the displaced resource; returning a second copy fails resource splitting. |
| Two local readers then an attempted writer | Both read guards preserve one immutable value; writer returns examined `BorrowConflict`; releasing both restores `Idle`. |
| Writer updates then returns `Err` | The declared error predicate contains the valid updated state; guard release precedes propagation. A rollback claim needs its own transition proof. |
| Snapshot length three, replacement length one, access index two | The snapshot remains valid history; current access fails the fresh bound/resource predicate. |
| Hide an owner in a cell inside an unrestricted callback | Transitive capture includes the stored owner; duplicating the callback fails `Dup`, independently of its grade. |
| Return a view in a nested wrapper or retained continuation | The result capture set contains the scoped loan; guard/view escape fails the scope closure rule. |
| Reenter the same cell through an apparently pure getter | Transitive effects expose reopening or conflicting access; the open-invariant callback premise fails. |
| Cancel or await while a write invariant is open | Checkpoint lacks a closed invariant and release proof; both ready and pending awaits fail. A request arriving during a certified bounded region waits for its checkpoint. |
| Read an immutable published packet, then reclaim after all holders end | Publication consumes writing, readers consume only immutable access, and quiescence restores writing once. Reclaiming after only one of several readers fails. |
| Copy a non-atomic payload while its writer remains live | Exclusive-access premise fails before any copy; sequence-number validation or retry cannot repair it. |
| Two counter additions with conserved allowances three and two | Both linearization orders preserve the invariant and give five after terminal joins; a second call with one allowance fails its linear consumption. |
| Check counter below a limit, then add without an allowance | The read is only a historical observation; concurrent additions invalidate the claimed no-overflow premise. |
| Cancel before commit versus cancel after commit | First retires allowance with no add; second produces `too_late` and completes exactly once. Parent reuse before terminal join fails lifecycle ownership. |
| Capability-bearing task frame in a shared cell | Representation and `Share` fail the prohibition on shared mutable capabilities, even through a sealed source wrapper. |
| Generic CAS counter, LR/SC loop or widened sub-word AMO | No admitted exact-operation lowering law exists; an unsupported instruction or conflicting footprint refuses the target instance. |
| Both components accept but their non-atomic grants overlap | The composed manifest join fails under R-05-096b; local acceptance is insufficient. |
| Observe completion and reuse an old generation's handle | Generation and rights-retirement premises fail even if scalar indices equal their initial values. |
| Ignore a child failure or borrow/capacity result | Relevant verdict elimination is missing; cell restoration alone does not discharge failure handling. |

## Separate theorems and missing-law handoff

| Guarantee | Required theorem subject and premises |
| --- | --- |
| Functional correctness | The interpreted state machine refines each operation's reviewed behavior contract; `commit_add` linearizes once and the generation's count equals committed allowances. Requires actual representation/read/write/atomic laws, conserved bound and no-replay history. Linearizability does not establish the counter's intended meaning by itself. |
| Race freedom | The composed source resource derivation excludes conflicting non-atomic access, and source correspondence/lowering/TAL soundness transport it to every Sail execution admitted by the binary/manifest join. Requires exact footprints, atomic classification, permission and frame laws, and all device participants. |
| Progress and release | Every normal or accepted-cancel trace reaches its declared terminal predicate within its bound; every reusable region is quiescent. Requires bounded reaction activations, local close/release totality, reserved terminal capacity and declared external bounds. Race freedom grants no progress theorem. |
| Leakage and policy | Two related initial states have the required related public observations over the selected architectural leakage model and final artifact. Requires actual security labels, allowed releases, address/branch/AMO-result observations, schedule/resource accounting and relational compiler preservation. The counter exposes lengths and completion information only under an explicit policy. |

The positive counter example uses public packet lengths, public scheduling decisions and a public count. Secret packet contents remain private; nothing in the example declassifies length, failure, occupancy, AMO return order or completion timing. An instance with secret length must supply a different observation contract and constant-time/policy proof before exposing its count. Scalar atomicity and a security grade do not prove this relational statement.

Q25d owns the combined review and assignment of the following missing implementation laws. These keys identify debts, not newly priced checklist cells. Existing [foundation-map obligations](../hardware/cheri-foundation-map.md), Q2b/M7.1 target work and Q21's retained source/compiler contracts keep their owners; shared work is charged once. None is recorded as checked here.

| Debt | Concrete acceptance predicate and ownership boundary |
| --- | --- |
| `MUT-CELL` | Interpret sealed cell predicates, invariant masks, unique opening/closing debts and frame preservation over the selected concrete resource logic; prove local replacement/take/put/scoped callback rules. Q25d assigns the cell layer while reusing Q2c's concrete byte/scoped-resource debts. |
| `MUT-BORROW` | Prove represented borrow-state correspondence, bounded guard capacity, alias exclusion, exact release and all source exits, including nested capture checks. Join Q25a substitution and Q25b outcome/exit preservation rather than duplicating them. |
| `MUT-SNAPSHOT` | Prove observation-to-snapshot introduction, stability under interference, invalidation of current predicates and dependent shape transport; connect executable copies to actual initialized memory. |
| `MUT-SHARE` | Prove transitive capture, `Dup`/`Dispose`/`Suspend`/`Transfer`/`Share` composition through sealed representations, task frames and handlers, with a target theorem excluding shared mutable capability storage and bypass paths. |
| `MUT-ATOMIC` | Build the concrete counter invariant/history and one-use allowance interpretation; prove exact AMO linearization, no overflow, width/alignment/permission/PMA conditions and atomic observation against the pinned Sail subject. Reuse the target connection's owner; this dossier creates no parallel memory semantics. |
| `MUT-PUBLISH` | Instantiate the existing SPSC proof with immutable packet/completion publication, actual Ztso/compiler/fabric ordering, reader/DMA quiescence and generation retirement. Reuse the canonical ring/HAL owners rather than inventing a second ring algorithm. |
| `MUT-EXIT` | Join cancellation arbitration, checkpoint masking, no-replay receipt storage, child terminal records and reset with Q25b; prove each outcome preserves cell/frame resources and terminal bounds. |
| `MUT-OBSERVE` | Prove the chosen counter/packet information-flow contract, including AMO results, occupancy, cancellations and schedules, and preserve it through optimization and final bytes. Coordinate with the existing non-interference/WCET and compiler owners. |
| `MUT-CLIENT` | Construct inhabited concrete entry witnesses, replay every supported positive/negative neighbor, independently review the accepted-byte contract, and connect the composed handler/graded-callback/child trace to its exact final representation. Q25d owns qualification scope and assigns implementation only after prerequisites and pricing are reviewed. |

### Requirement disposition owed at Q25d

No register amendment is applied by this dossier. The chosen scalar counter, private frames and immutable publication are intended to fit the present requirements. Q25d must read the register/prose pair for each proposed change and resolve the following exact duties before dependent implementation opens.

| Requirement boundary | Present design and amendment trigger |
| --- | --- |
| R-05-096a and R-05-096b | Preserve exclusive non-atomic access, explicitly atomic shared cells and the binary/manifest join. No weakening is requested. Any proposal permitting a racing copy, mixed atomic/non-atomic alias or source-only exclusion requires an explicit amendment to these entries and their Sail/TAL theorem, and is outside this selected design. |
| R-15-026, with R-15-024/R-15-025/R-15-027 | Preserve scalar `Zaamo`/`Zabha` and the absence of CAS, LR/SC and shared mutable capabilities. An unsupported synchronization library requires a separate profile amendment and renewed consumer justification, not an implementation fallback. |
| R-05-039 and R-05-100 | Preserve injected mutable state and explicit bounded exits. Hidden globals, lazy mutable registries, exceptions or unwinding require amendments; no such feature is used here. |
| R-05-020 and R-05-026 | The Vela frontend and its source correspondence still need an explicit semantic nonduplication/retirement disposition and exact source-to-artifact obligations. Q25d must either demonstrate the current entry predicates or review an amendment before commissioning; a cell dossier or Rocq output is no disposition. |
| R-05-132 through R-05-134 | Keep source grades/protocol laws distinct from the frozen TAL attributes and separately checked CIC evidence. A new on-device attribute requires the existing admissibility demonstration; general grade interpretation or open-term reduction requires a reviewed change rather than silent expansion. |
| R-07-037a and R-11-006 | Retain cooperative reactions and admitted bounds. An inner scheduler, blocking guard acquisition, arbitrary fairness premise or unbounded masking region would require an explicit scheduling amendment. |
| R-08-045 through R-08-047 | Declare all cell/guard/frame/allowance/completion storage and exhaustion behavior. Unplanned allocation or reuse before the applicable lifecycle completes is inadmissible, not a local cell optimization. |
| R-12-094 through R-12-099 | Instantiate publication, capacity, cancellation/commit, terminal and generation rules. A cancellable API with different race outcomes, implicit rollback/replay or early release requires amendments to the affected lifecycle entries before qualification. |

Acceptance of Q25c means the rule/interface dossier and its explicit debts withstand design review. Source execution, metatheory, source-to-Sail correspondence, progress, leakage and production qualification remain separate unfulfilled evidence claims.
