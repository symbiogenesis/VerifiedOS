# Interior mutability and interference contract

> Non-normative Q25c extension contract. Start with the [primary Vela design and examples](verification-strategy.md) and [first-release boundary](first-release.md#release-boundary). The [requirements register](../../requirements-register.md) governs these proposed cell interfaces and qualification cases; the [delivery plan](../../../PLAN.md#vela-first-release-delivery) owns commissioning. These rules/predicates supply no implemented library, proved calculus, admitted executable or accepted axiom.

## Scope and shared interface

The first supported release uses ordinary ownership, explicit loans and the [initialization and collection libraries](first-release.md#ownership-libraries). Local cells, checked dynamic borrowing and concurrent protocols are later library extensions, each requiring a concrete consumer and its own representation and operation proofs. They are not prerequisites for the first synchronous component or first async service. The [mutability guardrails](verification-strategy.md#interior-mutability-guardrails) constrain any such extension: each sealed state-transition interface grants only its declared operation rights; handle representation or grade alone authorizes no representation access. Preserve explicit snapshots and transitive capture accounting in the core without commissioning all cell mechanisms.

Use Q25a's [resource/computation interface](graded-foundation.md#resource-and-computation-interface): stable `Gamma`, separate computation/type use and dependency rows, and `Delta` for owners, loans and protocols. Outcome-indexed transitions retain captures, effects, event counts, representation and exit duties. This specializes the [synchronous core](core-design.md#judgments-and-interpretations), without a second resource interpretation.

`Capture`, `Dup`, `Dispose`, `Suspend`, `Transfer` and `Share` need semantic evidence. A grade counts invocations only through its trace interpretation; it creates neither ownership, access authority nor release. `Own(r,shape,snapshot)` belongs in `Delta`; stable identity `r` and historical snapshots may index `Gamma`, never unsynchronized current contents.

The retained concurrent qualification candidate uses private packets/tasks and a shared scalar counter within the [atomic profile](../../spec.md#r-15-026) and [exclusive-access constraints](../../spec.md#r-05-096a). It is commissioned only if an actual consumer needs that protocol. It adds no shared mutable capability, CAS, blocking mutex, retry loop, inner scheduler or unwinding. Ordinary libraries and a service using one structured child do not acquire a shared-counter dependency.

### Interpretation commitment

All predicates and transition laws in this dossier apply to the checked elaboration's image in an existing semantic anchor under [R-05-020a](../../spec.md#r-05-020a). The schematic notation specifies proof obligations for the untrusted elaborator and kernel-checked resource derivations; it is not an independent source reduction or a new authoritative memory model. Local operations are interpreted by the selected existing resource logic, while target operations and interference refer to the one pinned Sail subject. Substitution, capture, exit preservation and erasure statements quantify over those interpreted computations and their actual representations, connected to exact source by checked correspondence. No rule can obtain a concrete CHERI instance merely by naming its predicate. The [composition review](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows) retains those implementation prerequisites.

## Representation, authority and open invariants

A cell declaration binds identity, domain, fixed footprint/layout, lifetime/generation, contents type, invariant, transitions, interference, operation rights and concrete memory representation. The latter includes CHERI permissions, tags, provenance, temporal state and initialization; naming an invariant proves none of them.

The proposed proof interface is schematic; its arrows relate assertions about the selected anchor computation and grant no independent operational semantics:

```text
CellDecl(c, domain, generation, footprint, representation, invariant, protocol)
Closed(c, state) * OpRight(c, operation) * Frame
  -- operation --> Exit(result, Closed(c, state') * Returned(result) * Frame)

open:  Closed(c, s) * OpenPermit(c, scope)
       -> Open(c, scope, s) * Representation(c, s) * CloseDebt(c, scope)
close: Open(c, scope, s) * Representation(c, s') * invariant(s')
       * CloseDebt(c, scope) -> Closed(c, s')
```

These proof transitions cannot extract resources from duplicable propositions. Prove exclusive opening permission, a mask preventing reopening, and absence of overlapping representation permissions outside the region. When a record or cell declaration factors its invariant into named conjuncts (`invariant Clause: P`), [`open (ref ...) lifts Clause, ... { ... }`](surface-grammar.md#resource-contracts-and-lexical-handler-capabilities) refines `Open` and `CloseDebt(c, scope, lifted)` to open only the listed conjuncts: unlifted conjuncts remain active without re-proof across writes to disjoint or non-invalidating fields, any write that invalidates an unlifted conjunct must immediately re-establish it at that write, and `close` requires re-proving only the lifted conjuncts at the closing brace while refusing early exits (`return`, `break`, `continue`, `?`), suspension, handler capture or whole-receiver calls while `CloseDebt` is live. Nested openings follow an acyclic order over nonconflicting footprints; the frame rule and interference preserve unborrowed resources.

A local opening permits no interfering activation before close. A concurrent invariant opens only for a proved logically atomic operation or a proved exclusive ownership phase; an indivisible AMO does not make surrounding code atomic. Close consumes its debt once, restores the current representation and ends interior loans before return.

Seal representation primitives against forged handles, casts, exposed fields and untyped bypasses in source and final code. Load/store capability permission alone proves no ownership state. [R-05-096b](../../spec.md#r-05-096b) still requires binary splits and the manifest join. Shared scalar capabilities are privately injected at composition; a received integer identity grants none.

## Local cells

`LocalCell(d,c,T,I)` is confined to domain `d`, with state `Full(v)` satisfying `I(v)` or an explicitly supported `Empty`. Its fixed representation stores authority once. Private storage may hold owners/capabilities only under its representation and lifecycle laws; this grants no concurrent sharing.

| Operation | Entry and result contract |
| --- | --- |
| `snapshot` | Establish a stable mathematical value related to the current representation during one authorized observation. An executable copy additionally requires a duplicable contents representation and declared destination storage. |
| `replace(new)` | Consume the new represented value, prove `I(new)`, install it and return the old value by move. No copy of either owner survives inside the cell. |
| `take` | Available only for a cell whose invariant includes `Empty`. Move the value out, leave `Empty`, and make operations requiring `Full` return a typed empty result. |
| `put` | Consume `Empty` and one owned replacement; return `Full` under its invariant. An occupied-cell result returns the unconsumed replacement. |
| `with_update(f)` | Open the invariant and pass a scoped view to a callback with checked transitive effects and captures. Every callback outcome closes the invariant and returns no interior view. The contract states whether an error preserves the entry value or returns a valid changed value. |

Authority-bearing `T` supports scoped observation, authority-free pure projection or `take` by move, never unrestricted `get : T`. An unretained displaced value from `replace` requires explicit disposal.

A scoped callback cannot suspend, capture control, call unknown/reentrant code, publish its view or retain it transitively in a result, closure, cell, task, continuation or exception-like encoding. Exclude the opening identity and descendant loans from the whole result capture closure; a lifetime marker alone is insufficient. Frame laws permit disjoint resources. The default rule also forbids alias reentry into the open cell.

## Checked dynamic borrows

`BorrowCell(d,c,T,I)` supports same-domain aliases with sealed guard identities and represented states `Idle(v)`, `Readers(v,S)` and `Writer(v,g)`: bounded live-reader identities `S` or unique write guard `g`. A bounded count plus accounted guard slots may implement them only with identity correspondence, overflow exclusion and exact decrement proofs. This ordinary local state word is no concurrent lock.

| Transition | Required result |
| --- | --- |
| `try_read` from `Idle` or `Readers` | Allocate a guard from declared capacity, preserve the same immutable contents, suspend conflicting writes and return a scoped read view. |
| `try_read` from `Writer` | Return `BorrowConflict`; leave cell and caller resources unchanged. |
| `try_write` from `Idle` | Produce one scoped write guard, suspend all overlapping parent access and open the representation under its close debt. |
| `try_write` from `Readers` or `Writer` | Return `BorrowConflict` without a view or partial state change. |
| Reader capacity exhausted | Return the declared capacity verdict, with no counter wrap and no guard created. |
| Release read guard | Consume its identity once, remove exactly that reader, and restore `Idle` only when no reader remains. |
| Release write guard | End descendants, prove the invariant of the final value, consume guard and close debt, and restore `Idle`. |

Public `with_try_read`/`with_try_write` bracket nonescaping library guards. Clients must examine conflict/capacity results. Resource checking rejects missing drop, duplicate guard/release and forged decrement; even an affine guard owes release, with no GC or unwinding fallback.

Reader guards permit compatible reads and forbid footprint mutation; writer guards exclude all overlapping parent, wrapper, device and closure access. Reborrows suspend parents until descendants end. Both scopes forbid suspension/capture, including ready `await`; a future stable read-guard extension needs its own `Suspend`, represented lifetime and cancellation release proof. A conflict branch runs only the sealed state operation, with no callback or second opening.

## Snapshots and dependent indices

`Snapshot(c,e,x)` relates immutable `x` to observation event `e`; `e` is logical unless explicitly represented, not an implicit version counter. It proves neither `current(c) = x` nor current read/length permission. A concurrent scalar observation describes one linearization point, not a separate payload snapshot.

For a packet with capacity `N`, represented length `n` and `length(xs) = n <= N`, snapshot `n0,xs0` remains stable after replacement with length `n1`. `i < n0` still indexes `xs0`; current access needs fresh permission and `i < n1`. A type-changing shape update consumes the old owner and returns a dependent pair with represented `n1` and erased inequality proof.

A multi-field copy needs exclusion throughout or a proved snapshot protocol; separate loads, a sequence counter around a racing non-atomic copy, or atomic payload bytes do not suffice. The selected interface publishes a complete immutable payload. Retained refinements must withstand actual interference, including hidden getters/callback writes.

### Ante as a candidate for static invalidation

[Ante's place-and-mutation design](https://antelang.org/blog/safe_cyclic_mutability/) could infer local-view invalidation. Distinguish address validity from current-content refinements: stable scalar overwrite may preserve a view while invalidating `current(c) = x`. Accept disjoint stable-field updates preserving view/invariant; reject use after invalidating replacement, container mutation or destruction. Hidden callback writes and handler capture need the same analysis.

The proposed proof context records a current fact's dependency footprint
separately from a view's address and lifetime footprint. Dependencies use resolved
places and operation contracts, including transitive call effects. After a
possibly overlapping write, reuse needs checked preservation or re-establishment
of the current fact; an unknown effect leaves that premise unresolved. Historical
snapshot facts remain stable. The [borrow-analysis promotion contract](core-design.md#borrow-analysis-promotion)
connects these obligations to source checking without selecting shared mutation
for the synchronous release.

Selection still needs ownership, open/close and capture laws over all exits, suspension/cancellation, the local-domain boundary and artifact-level exclusivity. The [producer evaluation](../../background/architectural-alternatives.md#ante-place-sensitive-mutation-and-invalidation) retains this candidate without commissioning selection or qualification.

## Transfer, sharing and lifecycle eligibility

Eligibility is transitive through fields, instantiated parameters, environments, tasks and stored continuations. Sealing representation requires a checked theorem exposing its real captures/operations to verification.

| Predicate | Evidence required |
| --- | --- |
| `Capture(v)` | Whole transitive set of retained identities, permissions, loans, close debts and terminal obligations; distinguish temporary evaluation effects from retained state. |
| `Dup(v)` | Duplicating the represented value and its associated resource predicate preserves ownership and all protocol obligations. A duplicable descriptor does not duplicate an access grant. |
| `Dispose(v)` | Exact disposal transition for stored owners, must-erase values, guards and relevant results. An unknown finalizer is no evidence. |
| `Suspend(v)` | Stable represented storage, closed invariants, permitted live loans, preserved obligations and a bounded resume/cancel path at the checkpoint. |
| `Transfer(v,d1,d2)` | Sender loses access before receiver gains it; every retained field is transferable and remains live. Cross-compartment transfer conforms to the fixed grant/manifest protocol. |
| `Share(v,D)` | All participants have separately justified operation rights; the contents representation, permitted interference and observation policy remain sound under simultaneous use. |

Default `LocalCell`/`BorrowCell` have no cross-domain `Share`. Moving a quiescent cell requires no guards, loans or open debt, loss of old-domain handles, and proved domain/storage transfer/rebinding. Wrappers, grades, callbacks and hidden local/thread-local state bypass none of these. [Ambient-state exclusion](../../spec.md#r-05-039) includes caches, registries and lazy initialization behind pure-looking methods.

Shared scalar capabilities stay in private participant environments. Shared mutable memory holds only declared scalars, never capabilities, capability-bearing closures/continuations or task frames. Private stable storage may hold a capability-bearing continuation; transferring it needs a proved fixed-authority-graph protocol, not a pointer serialized into a shared cell.

## Concurrent protocols and the actual memory model

`ConcurrentCell(c,g,S,P)` declares state machine `P`, interference, participant roles, scalar representation `S`, rights and linearization/release points. Each operation proves its functional relation, invariant preservation, published resource transfer and observations. An atomic success is one transition at its proved point; failures establish declared unchanged/partial state, not implicit rollback.

The target is [Ztso](../../spec.md#r-15-004) with [whole-path ordering](../../spec.md#r-15-015a). The [Sail AMO implementation](../../../model/model/extensions/A/zaamo_insts.sail) decodes `AMOADD`, adds a word and writes it; [memory access](../../../model/model/sys/mem.sail) classifies accesses. These are inspected subjects, not checked Vela atomic laws or a concurrent-logic instance.

Lowering names the same pinned Sail term, width/alignment, capability load/store permissions, PMA support, tags, `aq`/`rl` and observations. Distinguish ordinary memory, MMIO and DMA. Forbid widening across neighbors, synthesized CAS/LR-SC, locking `libatomic`, unsupported capability atomics and non-atomic aliases into atomic footprints.

### Immutable publication and reclamation

The [SPSC lifecycle](../../spec.md#r-12-094) permits exclusive initialization, consumes writing at publication, grants immutable reader access and restores writing only after all readers/device holders end or are revoked with quiescence. Shared descriptors contain scalar indices/lengths; receivers resolve private tables and validate generation, extent and rights.

Publication orders payload stores and producer loads before the publication-index store; consumption orders the observing load before subsequent descriptor/payload loads and consumer stores. Prove these store-to-store/load-to-store and load-to-load/load-to-store edges from Ztso, compiler preservation and per-hart fabric ordering. The [fence-free ring contract](../../spec.md#r-12-008) requires that proof; annotations supply none.

Ztso lacks general store-to-later-load ordering. Reclamation needs terminal acknowledgments and ownership transitions; local store-then-load proves no peer stop. A protocol needing that edge must prove a legal drain fence's semantics/bound or use another protocol. Fences cannot repair overlapping non-atomic authority. Guard release, publication, cancel acceptance, terminal completion and reuse remain distinct.

[R-12-099](../../spec.md#r-12-099) changes generation before restart/revocation reuse, invalidating old handles/queued indices. Equal indices/counts prove no freshness: retire all old-generation rights. [R-08-046](../../spec.md#r-08-046) also retains quarantine, revocation and sweep where applicable.

## Concrete scalar service and composed client

This section retains a later concurrent-library experiment. A selected cell consumer first qualifies only the operations it uses, with an independently reviewed functional contract and concrete entry witnesses. A synchronous local-cell client need not implement atomic publication, tasks or handlers. The cross-feature packet/search/counter fixture below is a deferred stress case, not the first useful language or async milestone.

`CountCell(c,g)` is one aligned atomic `u64`, initially zero in generation `g`, summing committed accepted packet lengths. It holds no payload, pointer, request identity or capability. Participants need privately injected capabilities and declared operation rights; the integer handle in `Gamma` grants neither.

`AddOnce(c,g,k,n)` is a unique `Delta` resource for live request `k` and represented stable length `n`, not a copyable grade/proposition. Finite generation allowances conserve `sum(n) <= U64_MAX`; issuing spends that conserved bound, and cancel/commit retires each allowance once. New traffic needs a fresh accounted allowance or quiescent generation, not wraparound or read-then-check. For sequential reference-counted containers, [Evergreen's `starts_owner` reservation and 3-state conservation invariant](verification-strategy.md#rust-and-low-level-verification) (`count = owners + reserved_clones + retiring_owners`) supply an analogous split between pre-increment reservation before a fallible constructor (`reserved_clones`), active owners, and retiring owners during drop; `CountCell`'s concurrent `AddOnce` allowance remains a distinct Ztso `AMOADD` protocol with no shared mutable capabilities or reference-counted heap cells.

```text
commit_add(private_handle, AddOnce(c,g,k,n), represented n)
    -> Added(c,g,k,n,old)

cell transition: value = old  -> value = old + n
resource transition: AddOnce -> one committed receipt
target candidate: one aligned AMOADD.d, aq = false, rl = false
```

The AMO commits/linearizes counter arithmetic only: no payload publication, stable returned current value or cross-client old-value ordering beyond atomic history. The allowance bound makes word addition equal mathematical addition. The proposed lowering must prove its `aq`/`rl` bits; stronger APIs need separate ordering evidence. Callback grades prove neither AMO occurrence nor allowance consumption.

The deferred Q25 research client combines `n <= N`, an immutable-snapshot graded callback, handler and cancellable child. Multi-shot capture retains only `Dup` resources; unique packet/frame owners and `AddOnce` remain outside. Occurrence contract and multiplicity bound callback demand; `commit_add` is one separate child action. Sharing exposes only counter operations. Explicit sequencing evaluates effectful arguments once, unaffected by zero/repeated use grades. The [first async service](handlers-async.md#first-async-service-qualification) instead exercises sequential helper composition and structured ownership without requiring these extra mechanisms.

An entry candidate fixes `N = 4`, `n = 2`, private backing `[1,2,0,0]` with prefix `[1,2]`, a separate immutable callback environment used twice, free declared frame/completion slots, live private grants, zero counter and allowance two. Alternatively two children have lengths/allowances three and two and disjoint packets/frames: either AMO order yields five after joins, with intermediate value three or two. These proposed data witnesses do not construct CHERI resources in Rocq. The [composition review](full-language-review.md#the-representation-the-composed-duties-are-stated-over) constructs no inhabitant of its named carriers; private grants/schedule laws remain in unpriced `GF-resource`/`MUT-ATOMIC`.

### Cancellation, completion and reset

Under [R-12-097](../../spec.md#r-12-097), the final checkpoint, AMO and private committed-receipt store form one bounded region without suspension, capture, reentry or source-fallible operations. Cancellation stays sticky. A request arriving between checkpoint and AMO is decided afterward as postcommit, not accepted preemptively.

| Reachable outcome | Cell and resource result |
| --- | --- |
| Cancel before registered child starts | No AMO occurs; retire the allowance and place the returned input resources in the reserved `cancelled` completion record. Retain the registered frame until terminal collection and its release gate; the collecting owner examines the result. |
| Cancel observed at the pre-commit checkpoint | Close prior scopes, retire the allowance without changing the counter, clean private state and join `cancelled`. |
| Commit succeeds | Consume the allowance at the AMO, retain the receipt until normal terminal completion, and record that the increment cannot be replayed. |
| Cancel after the checkpoint/commit region begins | Resolve at the next decision point; once committed, answer `too_late` and finish normal completion. Do not subtract the increment or repeat the request. |
| Stale or nonexistent request | Answer `not_live` under the declared generation/request-state test, without obtaining an allowance or accessing a stale grant. |
| Frame or completion capacity unavailable | Return the pool's typed capacity result before starting, retaining unstarted input resources and creating no AMO obligation. |
| Parent stops waiting | The scope still owns the child and its packet/frame until terminal join; a wait timeout releases no authority. |
| Generation restart or environmental fault | Follow fail-stop, revocation and quiescence. No source-cleanup execution, normal completion, preserved counter total across generations or implicit replay is assumed. |

This operation has DMA quiescence `n/a`, but reuse still needs task/reader quiescence and pool lifecycle evidence. A DMA extension retains its packet loan through the HAL's completion/quiescence predicate; `too_late`, dropping a handle or seeing the increment proves none.

Completion uses a declared private record or immutable SPSC publication under the ordering/ownership rules above. Final observation/reset requires joining all terminals and retiring all old-generation rights; an expected count alone permits neither reset nor parent reuse. Live observations are historical scalar samples; their exact-width/alignment atomic-load law must prove single-copy atomicity, not a multi-field snapshot.

The [task outcome policy](handlers-async.md#task-completion-and-scope-failure) applies to a cell operation used by a child. A completed `Err(BorrowConflict)` or `Err(CapacityExhausted(...))` is still an ordinary returned value with its examination duty, not an implicit task failure. The owner may handle it, explicitly propagate across the scope, or select an interface-declared failure exit. None of those choices erases the resource state or reverses a committed update.

## Exit closure and bounded progress

Outcome-indexed ordinary exits restore the invariant and end all guards. Release cannot depend on an unproved destructor or its execution.

| Exit or control event | Closure obligation |
| --- | --- |
| Fallthrough, ordinary return, `Result` success/error propagation | End descendants, consume close/release debts and establish the tagged outcome's exact cell state and returned resources. Errors need not roll back unless their contract says so. |
| `break`, `continue`, bounded-loop back edge | Close iteration-local invariants/guards and restore the loop predicate before transferring control. |
| Effect operation, callback or reentrant call | Close first if it can capture, suspend or reenter. A certified local callback may run inside only under the scoped contract excluding those effects and result captures. |
| Ready or pending `await`, cancellation checkpoint | Closed invariants, no default guard scopes, stable frame storage and an explicit `Suspend`/cleanup derivation. Directly awaiting a helper uses the same rule; nesting creates no fresh guard or cancellation allowance. Ready status does not remove the checkpoint. |
| Handler discard or deferred multi-shot resumption | Account for transitive `Dispose` or, when the cloning extension is selected, `Dup`; an open debt, guard or allowance defeats an unsupported discard/duplication premise. |
| Accepted cancellation | Enter bounded cleanup with the invariant closed, retire or return every retained token, and join terminal completion before reuse. |
| Cleanup failure | The default local close/release primitives are total under their premises. An API with fallible external cleanup needs an explicit quarantined terminal state and a proved containment path; it cannot return ordinary reusable ownership. |
| Panic, trap or environmental fail-stop | No language exception/unwinding rule is added. Prove absence of unexpected traps under operation premises; external faults stop the affected domain/session and retain its revocation/quiescence obligations without asserting successful source closing. |

Declare local steps, checkpoint distance, cleanup/publication work, joins and external quiescence. Map them to the [reaction graph](../../spec.md#r-07-037a) and [schedule](../../spec.md#r-11-006). Compose comparable elapsed-time bounds `Lcheckpoint`, `Lcleanup`, `Ljoin`, `Lterminal` for accepted cancellation; prove the composition instead of merely adding them. A directly awaited helper contributes to the same task's state and bound, including cleanup, without an extra child term. Postcommit work has its own remaining bound. The no-checkpoint AMO region must fit locally and cannot defer requests indefinitely.

Progress names admitted activations and service/HAL response bounds, with no hidden fairness, spin or eventual-response premise. Adversarial failure takes the specified fail-stop path. Capacity exhaustion returns an immediate typed result with bounded handling; hardware recovery remains separate from source progress.

## Qualification cases and rejection neighbors

A commissioned extension selects its consumer, supported operations and applicable cases before implementation under the [delivery plan](../../../PLAN.md#vela-first-release-delivery). Local cells, dynamic borrowing and concurrent protocols may qualify separately; async and multi-shot cases apply only when those features are selected. Each negative must parse/elaborate beside its positive, reach a satisfiable entry and fail at the named premise. Missing syntax/parser failure or inconsistent preconditions prove no safety.

| Case | Expected accepted derivation or first rejected premise |
| --- | --- |
| Local replacement returns an owner by move | `replace` changes the invariant and returns exactly the displaced resource; returning a second copy fails resource splitting. |
| Two local readers then an attempted writer | Both read guards preserve one immutable value; writer returns examined `BorrowConflict`; releasing both restores `Idle`. |
| Writer updates then returns `Err` | The declared error predicate contains the valid updated state; guard release precedes propagation. A rollback claim needs its own transition proof. |
| Child completes with an examined borrow/capacity error | In-place handling preserves siblings; explicit propagation across a scope follows its early-exit join. A source or lowering rule that silently treats an error payload as `Failed` violates the task outcome policy. |
| Snapshot length three, replacement length one, access index two | The snapshot remains valid history; current access fails the fresh bound/resource predicate. |
| Hide an owner in a cell inside an unrestricted callback | Transitive capture includes the stored owner; duplicating the callback fails `Dup`, independently of its grade. |
| Return a view in a nested wrapper or retained continuation | The result capture set contains the scoped loan; guard/view escape fails the scope closure rule. |
| Reenter the same cell through an apparently pure getter | Transitive effects expose reopening or conflicting access; the open-invariant callback premise fails. |
| Cancel or await while a write invariant is open | Checkpoint lacks a closed invariant and release proof; both ready and pending awaits fail. A request arriving during a certified bounded region waits for its checkpoint. |
| Read an immutable published packet, then reclaim after all holders end | Publication consumes writing, readers consume only immutable access, and quiescence restores writing once. Reclaiming after only one of several readers fails. |
| Copy a non-atomic payload while its writer remains live | Exclusive-access premise fails before any copy; sequence-number validation or retry cannot repair it. |
| Two counter additions with conserved allowances three and two | Both linearization orders preserve the invariant and give five after terminal joins; a second call with one allowance fails its linear consumption. |
| Check counter below a limit, then add without an allowance | The read is only a historical observation; concurrent additions invalidate the claimed no-overflow premise. |
| Cancel observed at a precommit checkpoint versus after commit | First retires allowance with no add; second produces `too_late` and completes exactly once. Arrival during the bounded checkpoint/commit region is decided afterward. Parent reuse before terminal join fails lifecycle ownership. |
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

The example permits public lengths, scheduling and count while contents stay private; it declassifies no secret length, failure, occupancy, AMO order or completion time. Secret-length instances need a different observation contract and constant-time/policy proof. Atomicity and security grades supply no relational theorem.

The [sharing/disposal survey](verification-strategy.md#effect-handlers-sharing-and-protocol-logics) records mechanized temporary guarding for `MUT-CELL` and a non-leaking resource-accounting adequacy result for `MUT-EXIT`. The [Rust survey](verification-strategy.md#rust-and-low-level-verification) records semantic soundness for a proof tool's cell/invariant/storage subset via guarding plus lifetime logic, and checked Cell/Mutex specifications over a Rust-core model. Each uses another language, trusted base and prover edition, retaining erasure/solver/compiler trust. None constructs this concrete representation, pinned-Sail atomic law or inhabited cell instance.

Q25d records these unproved implementation-law families. The [delivery plan](../../../PLAN.md#vela-first-release-delivery) selects and prices only the slice a consumer needs; the deferred combined fixture assigns no first-release duty. Every theorem below is over the checked interpretation image and its source-correspondence relation. The [foundation map](../../hardware/cheri-foundation-map.md), Q2b/M7.1 target work and Q21 contracts retain their owners; charge shared work once.

| Debt | Concrete acceptance predicate and ownership boundary |
| --- | --- |
| `MUT-CELL` | Interpret sealed cell predicates, invariant masks, unique opening/closing debts and frame preservation over the selected concrete resource logic; prove local replacement/take/put/scoped callback rules. Q25d assigns the cell layer while reusing Q2c's concrete byte/scoped-resource debts. |
| `MUT-BORROW` | Prove represented borrow-state correspondence, bounded guard capacity, alias exclusion, exact release and all source exits, including nested capture checks. Join Q25a substitution and Q25b outcome/exit preservation rather than duplicating them. |
| `MUT-SNAPSHOT` | Prove observation-to-snapshot introduction, stability under interference, invalidation of current predicates and dependent shape transport; connect executable copies to actual initialized memory. |
| `MUT-SHARE` | Prove transitive capture, `Dup`/`Dispose`/`Suspend`/`Transfer`/`Share` composition through sealed representations, task frames and handlers, with a target theorem excluding shared mutable capability storage and bypass paths. |
| `MUT-ATOMIC` | Build the concrete counter invariant/history and one-use allowance interpretation; prove exact AMO linearization, no overflow, width/alignment/permission/PMA conditions and atomic observation against the pinned Sail subject. Reuse the target connection's owner; this dossier creates no parallel memory semantics. |
| `MUT-PUBLISH` | Instantiate the existing SPSC proof with immutable packet/completion publication, actual Ztso/compiler/fabric ordering, reader/DMA quiescence and generation retirement. Reuse the canonical ring/HAL owners rather than inventing a second ring algorithm. |
| `MUT-EXIT` | Join cancellation arbitration, checkpoint masking, sequential helper cleanup, no-replay receipt storage, child terminal records and reset with Q25b; prove each outcome preserves cell/frame resources and terminal bounds. Ordinary completed error values remain distinct from declared task failure, and helper composition neither resets commit phase nor duplicates cleanup. |
| `MUT-OBSERVE` | Prove the chosen counter/packet information-flow contract, including AMO results, occupancy, cancellations and schedules, and preserve it through optimization and final bytes. Coordinate with the existing non-interference/WCET and compiler owners. |
| `MUT-CLIENT` | Construct inhabited concrete entry witnesses for the selected local or concurrent library consumer, replay every supported positive/negative neighbor, independently review the actual behavior/byte contract, and connect the interpreted trace to its exact final representation. A later handler/graded-callback/child combination requires its own commissioned extension and cannot be charged to the first cell client. Q25d records the law boundary; the delivery plan assigns implementation after prerequisites and pricing are reviewed. |

### Requirement disposition owed at Q25d

This dossier changes no platform obligation. The interpretation follows the register's R-05-020a clarification; concrete source correspondence and resource/machine laws remain unimplemented. A selected scalar counter, private frame or immutable-publication consumer retains the following boundaries, including required register/prose co-reads for any later amendment.

| Requirement boundary | Present design and amendment trigger |
| --- | --- |
| R-05-096a and R-05-096b | Preserve exclusive non-atomic access, explicitly atomic shared cells and the binary/manifest join. No weakening is requested. Any proposal permitting a racing copy, mixed atomic/non-atomic alias or source-only exclusion requires an explicit amendment to these entries and their Sail/TAL theorem, and is outside this selected design. |
| R-15-026, with R-15-024/R-15-025/R-15-027 | Preserve scalar `Zaamo`/`Zabha` and the absence of CAS, LR/SC and shared mutable capabilities. An unsupported synchronization library requires a separate profile amendment and renewed consumer justification, not an implementation fallback. |
| R-05-039 and R-05-100 | Preserve injected mutable state and explicit bounded exits. Hidden globals, lazy mutable registries, exceptions or unwinding require amendments; no such feature is used here. |
| R-05-020/R-05-020a and R-05-026 | This dossier adopts the checked-interpretation route under R-05-009/R-05-020a; the [composition review](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows) retains concrete-law and source-correspondence gates. The exact source-to-artifact obligations remain owed at Q2c's `artifact-admission`. An independent source semantics or trusted checker would still require R-05-020's amendment conditions. A cell dossier or emitted Rocq term establishes none of these proofs. |
| R-05-132 through R-05-134 | Keep source grades/protocol laws distinct from the frozen TAL attributes and separately checked CIC evidence. A new on-device attribute requires the existing admissibility demonstration; general grade interpretation or open-term reduction requires a reviewed change rather than silent expansion. |
| R-07-037a and R-11-006 | Retain cooperative reactions and admitted bounds. An inner scheduler, blocking guard acquisition, arbitrary fairness premise or unbounded masking region would require an explicit scheduling amendment. |
| R-08-045 through R-08-047 | Declare all cell/guard/frame/allowance/completion storage and exhaustion behavior. Unplanned allocation or reuse before the applicable lifecycle completes is inadmissible, not a local cell optimization. |
| R-12-094 through R-12-099 | Instantiate publication, capacity, cancellation/commit, terminal and generation rules. A cancellable API with different race outcomes, implicit rollback/replay or early release requires amendments to the affected lifecycle entries before qualification. |

Q25c acceptance covers design review of these interfaces and debts. Execution, metatheory, source-to-Sail correspondence, progress, leakage and production qualification remain unfulfilled, separately evidenced claims.
