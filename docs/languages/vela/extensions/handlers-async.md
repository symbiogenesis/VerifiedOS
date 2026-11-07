# Handlers and structured async lifecycle rules

> Non-normative Q25b extension contract. Start with the [primary Vela design and examples](../verification-strategy.md) and the [first-release boundary](../first-release.md#release-boundary). The [requirements register](../../../requirements-register.md) governs, and the [delivery plan](../../../../PLAN.md#vela-first-release-delivery) owns commissioning. These rules and missing laws supply no implemented language, checked metatheory, accepted axiom or admitted binary.

## Boundary and shared resource interface

The first supported release is synchronous. Structured async is a later extension commissioned for a named service after the synchronous component and independent-client gates. Its first qualification uses sequential helper calls and one structured child; it does not require a handler or shared mutable cell. A separately justified handler extension starts with deep, one-shot continuations, including explicit zero-resumption disposal. Runtime multi-shot continuations and shallow rehandling remain optional research directions. Their retained rules below apply only to a separately commissioned extension; they impose no first-release implementation or proof requirement. A consumer must demonstrate a material benefit over ordinary bounded control flow before either extension is selected.

Async computations own dormant state and may compose sequentially or create structured children. VerifiedOS realizes the selected extension as a finite represented reaction graph with ordinary control transfers, explicit cleanup and syntactic poll sites. Lowering must prove R-05-100's absence of exceptions, unwinding and `longjmp`, R-07-037a's absence of blocking, internal threads and an inner scheduler, and R-11-006's schedule obligation. Effects confer no ambient service authority or change to the composition-fixed graph.

### Interpretation commitment

Every judgment, transition and equation in this dossier denotes an obligation about the checked elaboration's image in an existing semantic anchor under [R-05-020a](../../../spec.md#r-05-020a). `Interpret(e)` is the selected anchor computation together with its checked source correspondence; ownership and frame predicates are interpreted by the existing resource logic. The syntax below specifies what an untrusted elaborator must construct and the kernel must check. It supplies no independent source reduction, accepted source typechecker, new memory semantics or eighth anchor. Capture, substitution, return, erasure and progress laws must quantify over those interpreted computations and their actual representations. A checked CIC term alone establishes neither source correspondence nor a concrete CHERI law. The [composition review](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows) retains the implementation and evidence gates.

The [graded foundation](graded-foundation.md#resource-and-computation-interface) owns the stable telescope `Gamma`, use vectors `u` and `v`, binder dependency rows and resource context `Delta`. Its `Capture`, `Dup`, `Dispose`, `Suspend`, `Transfer` and `Share` require concrete resource-logic laws; grade constraints alone supply no memory predicate or ownership token.

```text
Gamma ; u ; v ; Delta_in |- e : Exit(A, Delta_out)
  [captures C, loans L, effects E, source trace bound B, representation rho]

Capture(e, Delta_k, C, L, rho_k)
  records every transitively retained resource and its exit duties
Dup(Delta_k, rho_k)
  permits a represented clone and a separating resource interpretation
Dispose(Delta_k, reason, Delta_disposed)
  accounts for cleanup, erasure, terminal protocols and examined verdicts
Suspend(Delta_k, frame, lifetime, Delta_resumed)
  preserves stable storage, closed invariants and restoration at activation
```

`Delta_in = Delta_run * Delta_k * Delta_frame` is a proved separating split, including suspended parent permissions and restoration debts. Naming a loan in `Gamma` grants no access without its permission in `Delta`. `Dup` checks nested closures, handlers and stored continuations transitively; repeated invocations need fresh separated inputs `Delta_i` where their contracts require them. Idempotent grades cannot duplicate owners. Operation contracts supply source event counts, separately from use grades and target WCET.

Effectful arguments use explicit call-by-value sequencing: `bind x <- c; call f(x)` evaluates `c` once, with its trace and resource transition. Zero use does not erase effects; repeated use does not reevaluate the argument. The foundation's pure scaling rules and open call-by-value bridge govern this distinction. Multiple resumption repeats only the captured continuation under its contract.

The [synchronous core](../core-design.md#loans-and-control-flow) embeds without handler capture or suspended frames, retaining ordinary returns, resource-indexed errors and loan restoration. Fallible cleanup and suspended loans require additional laws. Relevant precedents are:

| Source | Result and transfer limit |
| --- | --- |
| [Soundly Handling Linearity](https://arxiv.org/abs/2307.09383v2), POPL 2024 | Relates continuation use to retained linear resources and exposes the motivating soundness bug. Pen-and-paper proofs; Links-fork artifact under GPL-3.0-or-later; no checked development. |
| [Affect](https://iris-project.org/pdfs/2025-popl-affect.pdf), POPL 2025 | Iris/Rocq semantic type soundness over Hazel, separating one-shot/multi-shot continuations, including storage in mutable references. No verified checker or inference algorithm. |

The [strategy](../verification-strategy.md#effect-handlers-sharing-and-protocol-logics) surveys relational, stack-switching, sharing and disposal logics. None proves this graded dependent CHERI combination or models its preassigned immovable frames.

## Handler lookup, capture and return

An effect signature declares represented arguments and represented dependent reply types, effect permission, input/output resources and resumption allowance. A selected one-shot handler supplies a finite deep operation table, environment representation, operation/return/disposal clauses and a result/resource transformation. Shallow mode and multiple-resumption allowances belong only to the deferred research extension. Binding introduces a capability for that instance. Effect contracts enumerate usable capabilities; effect polymorphism quantifies over them. Specialization fixes tables, layouts and bounds. Every residual operation needs a caller-supplied capability or injected primitive; an unhandled composed-entry operation is an unresolved obligation, never a default service or runtime trap.

A handler capability resolves to its frame's preassigned slot and incarnation under the [frame representation](#frames-child-ownership-and-reaction-execution); the deferred cloning/rehandling candidate additionally stores body-internal references frame-relatively. An operation names it explicitly or takes the lexically nearest binding, following [Zhang and Myers](https://doi.org/10.1145/3290318), POPL 2019; effect-contract parameters count as lexical bindings. Lookup never searches a dynamic chain. `E` contains the evaluated hole and all frames up to the named handler, including intervening handlers regardless of their tables. Their clauses and cleanup do not run at capture; resumption restores them. The chosen clause runs outside those frames and its handler, using capabilities from its lexical context/environment unless it installs another handler.

A handler capability is a shared duplicable loan on its frame, authorizing only perform; the running context supplies capture authority over intervening frames. Lexical scope bounds use, following Effekt and [System C](https://doi.org/10.1145/3527320), OOPSLA 2022:

- Type a handler's operation, return and disposal clauses without its capability or capabilities bound inside its body.
- Type a spawn's dormant computation with no handler capability in scope. Children install their own handlers; their frames cannot form a continuation segment to an outer handler.
- Track retained capabilities transitively. A use site requires every capture in scope, including a closure read through a cell. Operation argument/reply types cannot carry a capability bound inside the body. Effekt's [capture discipline](https://effekt-lang.org/tour/captures) likewise requires captures in scope when unboxing.
- An operation argument may lend the clause part of the body's frames, resolved against `k`'s current invocation frame. End that loan before resume, clone, rehandle or dispose; neither `Dup`, rehandle nor the reply retains it.

A handler installed by an effect-polymorphic function cannot intercept operations through its capability parameters. This excludes Zhang and Myers' accidental handling and preserves parametric reasoning. It applies the [object-capability rule](../../../spec.md#r-04-003) to effects and permits constant-time lookup by slot, independent of nesting.

Proof reuse still needs a simulation: Affect/Hazel selects the first enclosing matching handler and captures non-matching ones, unlike capability-directed lookup. The checked named/lexical-instance precedents establish different results:

| Source | Checked result |
| --- | --- |
| Zhang and Myers | Coq parametricity and logical-relation soundness for contextual refinement; label types/effects must be closed. |
| [Biernacki, Piróg, Polesiuk and Sieczkowski](https://doi.org/10.1145/3371116), POPL 2020 | Coq lexically scoped instances, open/generative semantics and logical relations. |
| System C | Coq progress and preservation for second-class capabilities and boxes. |
| [De Vilhena and Pottier](https://doi.org/10.1007/978-3-031-30044-8_9), ESOP 2023 | Coq type soundness by encoding into Iris separation logic; supports lexical handlers without requiring them. |

None supplies Affect's one-shot/multi-shot retained-resource separation for this lookup rule; the combination remains an open law.

```text
Interpret(handle_deep E[perform op(a)] with H)
  ~= Interpret(H.op(a, k)), with resume k(b) interpreted as handle_deep E[b] with H

Deferred shallow extension:
Interpret(handle_shallow E[perform op(a)] with H)
  ~= Interpret(H.op(a, k)), with rehandle k(b) with H' interpreted as E[b]
     handled by H' at k's invocation frame, for H' of H's effect signature
```

Here `~=` requires the appropriate checked behavior/resource relation in the selected anchor; it is not a source reduction axiom. Deep resumption reinstalls `H` and its return transformation; each completed resumption evaluates that clause once. In the deferred shallow extension, capture moves the handler environment into its clause and leaves a delimiter hole. Resume is allowed only inside a rehandle of the same effect signature, bound at `k`'s invocation frame under a fresh incarnation (or the clone's frame). The segment's retained delimiter capability resolves to that handler. Specialization fixes a finite rehandler declaration set and sizes the slot for every member; performs dispatch on its recorded declaration in constant time. The rehandler's return clause receives raw body results/resources, and the operation clause explicitly transforms its result. Ordinary body completion evaluates `H.return` once. Effekt, [Lexa](https://doi.org/10.1145/3689770), OOPSLA 2024, and System C supply only deep handlers, so no cited design transfers this shallow rule.

| Rule | Required state and resulting obligation |
| --- | --- |
| Enter handler | Split exclusive environment resources from the body; bind a declared frame and its shared perform capability, scoped to the body. Establish stable reference/lifetime laws; the deferred cloning/rehandling candidate additionally stores body-internal references relative to the delimiter from entry. Type clauses under the lexical restrictions above and check every exit against the result transformation. Sharing an immutable descriptor still needs its permission. |
| Capture | Transfer `Delta_k`, its complete transitive loan/authority graph and exit duties into the continuation's ownership, including all intervening frames and their capabilities. The running clause loses those resources. Extents and lifetimes must be represented; no reference to unaccounted or retiring stack storage crosses the delimiter. One-shot capture preserves the existing stable frames. Deferred cloning/rehandling additionally preserves frame-relative references and rejects an absolute reference into the copied segment. `Suspend` maintains the selected premises across gaps. |
| Perform past intervening handlers | Reach the named outer frame directly; capture intervening frames in `E` regardless of their tables. Run none of their operation, return or disposal clauses; restore them on resumption. |
| Explicit forward from a clause | Move `k` once into an adapter that composes outer replies with its resumption and performs through a supplied outer capability. Retain no alias or reset use allowance; compose both continuations' capture/disposal duties. |
| Resume once | Consume one-shot authority, transfer `Delta_k` and reply resources to the resumed graph, and return its indexed result. Even an error consumes the descriptor. |
| Resume multiple times (deferred) | Require transitive `Dup`, including reinstated handler environments. Give simultaneously live clones distinct preassigned invocation frames and fresh incarnations; copy templates and resolve relative references without rewriting. Check fresh inputs `Delta_i`, every exit and a finite resumption bound. Sequential reuse waits for release. Shared mutable handles need [interference laws](interior-mutability.md); descriptor copies grant no mutable access. |
| Rehandle a shallow continuation (deferred) | Fill `k`'s delimiter hole at its invocation frame with a same-signature handler from its specialized finite rehandler set, using a fresh incarnation of the vacated slot or the clone's frame. Apply the one-shot/multi-shot premises. Refuse shallow resume outside rehandle. |
| Dispose without resumption | Consume the declared disposal graph: end descendant loans first, erase must-erase contents and eliminate mandatory verdicts by outcome. Request cancellation where available and join in-flight operations. Disposal may suspend under `Suspend`; waiting cannot free its frame. |
| Leave handler | Consume, dispose or explicitly transfer every continuation with its lifetime/exit contract; retain any environment it still needs. No result outside a transferred segment retains the handler capability. Inside that segment, the selected representation reaches only the still-live handler reinstated by resumption. |

A handler may change result types/resources, but alternatives must entail a common predicate or retain a represented indexed sum. A disposed packet and a resumed result holding its loan cannot join as freely writable ownership. Disposal follows its separately checked bounded graph, not the abandoned user continuation; its effects, waits and failures use the same judgment.

Specialization or bounded-loop derivations bound nesting, forwarding and resumptions; recursive forwarding needs a decreasing bound. Capture either binds complete capacity or returns uncaptured resources to a declared branch that examines `CapacityExhausted(pool)`. Without that branch, reserved available capacity must be proved. Partial moves are forbidden.

## Frames, child ownership and reaction execution

Each live frame has a preassigned immovable slot containing finite PC state, incarnation, represented environment, handler links, child membership, cancellation latch, bounded mask state and indexed result slot. Validity permits access only to initialized variant fields. Erasure may remove loan/ownership proofs, never executable bases, extents, tags or identities. Checked incarnation exhaustion/no-wrap distinguishes old handles before reuse without adding a kernel epoch mechanism.

Continuations/scopes own frames; handles supply only declared operations, and dropping one does not remove scope membership. Outside continuation segments, references name slot plus live incarnation under `Suspend` and cannot survive moving/retiring storage. Handler links are perform capabilities, not search positions. Returning a frame view transfers a pin/loan preventing reuse until it ends; APIs may instead return owners or copies. Inter-core transport needs `Transfer`/`Share`, composition grants and a separate publication theorem.

For one-shot control, capture transfers the existing frame ownership once and `Suspend` preserves its stable locations. It needs no clone template or shallow delimiter hole. The following frame-relative construction is a representation candidate for the deferred cloning/rehandling extension, not an extra first-async requirement: a handled body's delimiter-to-running frames form its capture segment. Every internal reference uses its delimiter's invocation-frame base from entry, including nested handler capabilities and a deep delimiter. Capture moves no reference; `Dup` copies the template into a fresh clone frame without rewriting. Activation resolves references to slot plus incarnation through that frame's capability. A shallow delimiter is the rehandler-filled hole. For nested segments, specialization fixes each reference's enclosing invocation-frame base and nesting bound; the inner activation retains those base capabilities. Absolute references may name only storage outside all enclosing segments, shared under its actual permission. An absolute capability into a copied segment would still authorize the template and fails `Capture`, `Suspend` and, for multi-shot use, `Dup`.

Stack-address designs need different copying machinery: Lexa aborts multi-shot resumption containing a handler and permits only one stack segment with no simultaneous copies because stale-reference scanning is costly ([Virtualizing Continuations](https://cs.uwaterloo.ca/~yizhou/papers/multilexa-pldi2026.pdf)). The [strategy](../verification-strategy.md#general-handlers-with-resource-safe-resumptions) records Effekt's active-copy global pointer and Virtualizing Continuations' software memory-management unit.

Task PC states refine R-08-046's frame-pool lifecycle. The [IDL profile](../../idl-profile.md#43-the-ring-schema-and-its-lifecycle) and [RingContract.v](../../../../proofs/RingContract.v) separately own request-slot states and terminal statuses. Task completion, ring reclamation and reader release remain distinct.

| Source event | Frame and scope transition |
| --- | --- |
| Construct async computation | Move captures into a dormant owned value in existing declared storage; execute no body effect. Disposing an unspawned value requires its `Dispose` contract. Construction storage itself must fit the plan. |
| Directly await a dormant computation | Consume it once into a bounded sequential subgraph of the current task, under the [sequential composition rules](#sequential-async-composition). Use declared nested state storage; create no child registration or child completion record solely for this call. |
| Scoped spawn | Bind a frame and completion capacity, then transfer the dormant value to the scope's child slot. Registration reads the scope's latched cancellation bit; a child registered while it is set is registered already marked. Body execution starts only at its graph's admitted activation. Failure returns the unchanged dormant value and examined capacity verdict, with no child registered. Only the scope owner's own graph has a registration edge into the scope, since a scope handle does not transfer to a child, and a cleanup graph has none. |
| Run activation | Execute the declared finite control-flow branch for this frame's state within the compartment reaction. All internal choice is ordinary program control flow with a proved bound; no ready queue selects a task. |
| Await checkpoint | Require already-closed invariants and released default dynamic guards, then validate suspension/restoration premises and observe the sticky cancellation state and any declared deadline decision. Elaboration may insert only a separately proved close/release operation before this edge. This step occurs even when the awaited result is ready. It records a semantic checkpoint, not a mandatory OS dispatch. |
| Await ready | Match the current result at the checkpoint and continue only along the graph's declared successor. It may continue in the same bounded reaction if that path is admitted. Cancellation of the enclosing task routes through its cleanup edge while still accounting for an already-produced result. |
| Await pending | Store the continuation PC and retained resources, then return at a syntactic poll site. Later activations inspect authoritative state in the declared order. Coalesced notifications are hints; the existing ring index/recheck discipline remains required. |
| Child reaches terminal | Store its result/resources in its reserved completion record; retain scope membership until collection. A local result cannot hide an unexamined service completion. Service terminal publication obeys R-12-093 and R-12-100. |
| Join child | Consume its mandatory result by named outcome and transfer/restore returned resources. Reclaim the child frame only after loans, readers, erasure and the pool release gate permit it. |
| Finish scope | Normal exit joins every child. Early return, explicit failure propagation across the scope, declared task failure or scoped timeout first marks descendants for cancellation and then joins them; marking covers a child registered after the latch, and cleanup registers none. An ordinary completed error value alone does not cause early exit. The scope releases captured parent storage only after those obligations finish. Detached children are outside this profile. |

Composition fixes activation edges and order. Pending children cause no unplanned activation, poll-spin or work donation; R-07-037b's platform rotation supplies no task scheduler. Collect completed, cancelled and failed children by declared index under the [completion policy](#task-completion-and-scope-failure). Retain or explicitly eliminate every outcome, including failures discovered after another child caused cancellation.

Every variable occupancy needs its R-08-046 classification and manifest contract for authority, lifecycle, capacity, derivation source, exhaustion, confidentiality, recovery and generation: pool-backed dormant environments, task/continuation frames, scope membership and completions. Bind frame/completion slots transactionally or return all inputs. Reserve cleanup resources before the child becomes live. R-08-045 charges metadata and unused reservations; R-08-047 forbids borrowing another pool on exhaustion.

### Sequential async composition

The static operand type distinguishes `await dormant` from `await child`. The former executes an owned computation sequentially in the current task; the latter observes and joins an already registered child. Both retain checkpoint and resource obligations. A helper call does not create concurrency, extend the task's lifetime or obtain a fresh cancellation budget.

A directly awaited helper may use a caller-supplied handler capability only while its lexical scope and frame remain live, under the same transitive capture and suspension laws as the caller. This does not relax the prohibition on a spawned child retaining an outer handler capability. Invariants and default dynamic guards close before direct await, including an immediately ready helper.

```text
async Result<Data, Error> Load()
{
    return await ReadAndValidate();
}
```

This illustrates the proposed rule, not currently supported elaboration. Construction of `ReadAndValidate()` moves its captures without running body effects. The direct await first takes the enclosing task's checkpoint. For an ordinary-work helper, cancellation accepted before entry selects its unstarted disposal contract, which returns or retires those captures without a body step. Otherwise control enters its admitted subgraph. A pending helper stores its local PC and retained resources and returns at the same task's poll site; the next activation resumes that subgraph before the caller. A ready helper still takes the checkpoint. Returning transfers the declared value and resources to the caller without publishing a child terminal record. A helper has no independently observable task outcome: any control exit selecting the enclosing task's declared failure must be explicit in the helper's contract.

Specialization accounts for the complete bounded call nesting, local PC/result storage, captures, loans and cleanup state in the task's reserved representation. Inlining is an optional proved lowering, not a source requirement. An out-of-line state-machine call has the same contract. Recursive helper calls require a static depth bound and proved storage/cost composition; an unbounded call chain is unsupported. A returned view must name still-live caller backing or a declared pinned region, and cannot outlive the helper storage that represents it. No child-pool capacity request is introduced just by extracting a sequential helper; any resource request the helper itself performs remains explicit and fallible.

The caller and helper share the task's latched cancellation state and declared commit phase. A precommit helper cannot silently commit an independent enclosing operation: a commit-capable signature explicitly consumes the enclosing operation's unique commit permission and returns the corresponding phase/receipt. Following that commit, both caller and helper follow the declared bounded postcommit continuation; another cancellation request cannot undo the committed action or restart precommit cleanup. Independent service requests retain their own declared commit/cancellation contracts and quiescence, and composition does not turn them into one transaction.

An accepted cancellation closes the active helper's local loans and runs its declared cleanup before the caller's cleanup, passing the exact returned resource state outward. Dormant values and already produced results are disposed or transferred once. Cleanup may directly await a cleanup-compatible helper whose effects, state storage and terminal bound were reserved before the task became live. It executes in the existing cleanup phase: checkpoints preserve the sticky request, cannot abandon or restart cleanup, and permit only the declared bounded service waits/reoffers. The latched request does not select the ordinary helper's unstarted-disposal edge; the cleanup helper must finish its declared cleanup graph. It may neither spawn, register children, enter ordinary application work, introduce a new commit of the cancelled operation, recurse through cleanup nor acquire resources or capacity not reserved for cleanup. A helper failure follows the existing bounded recovery or fail-stop contract and never manufactures reusable ownership. Masks remain finite and their delay belongs to the same task's cancellation bound.

### Task completion and scope failure

Use the following semantic outcome algebra with resources indexed by the case. These names describe the source contract, not new IDL wire tags or implemented syntax. The concrete source API exposes named elimination or explicit propagation of every outcome and retains any stricter must-examine obligation of its payload.

| Outcome | Meaning and scope effect |
| --- | --- |
| `Completed(value)` | The task returned its declared `T` and associated resources. If `T` is `Result<A,E>`, `Completed(Err(e))` is an ordinary completed value; observing it does not cancel siblings. |
| `Cancelled(resources)` | The task accepted cancellation and completed its declared cancellation path. It remains in the scope until collected and its separate release gate is met. Collection does not turn it into a task failure. |
| `Failed(reason, resources)` | The task explicitly selected a failure exit from the finite failure set declared in its interface, after establishing that exit's resource predicate. The initial scope policy marks sibling cancellation when this outcome is observed at an admitted site. An operation with no such exit declares the empty failure set. |

A checked failure return cannot hide a panic, illegal access or missed quiescence bound; environmental fail-stop retains its separate platform recovery meaning. A task's declared postcommit contract determines any allowed failure outcome after commitment and must preserve its committed effects. A service mapping preserves the existing terminal statuses and their ownership rules.

The first scope policy is fixed: observing a declared `Failed` outcome triggers early exit and cancellation/join of remaining children. A caller may instead match `Completed(Err(e))`, handle it normally, or explicitly choose an early return/error-propagation edge crossing the scope; that edge performs the existing cancellation/join protocol. It never rewrites the child's recorded outcome to `Failed`. There is no implicit promotion based on a type name, field name, enum case spelling or library change. A `Cancelled` outcome may likewise be examined and explicitly propagated by the owner.

Observe simultaneous terminal records in the composition-declared child order, preserve every outcome, and latch early exit once. A later failure cannot erase an earlier result or restart cleanup; a postcommit sibling still joins normally under its actual outcome. A collect-all or supervisor policy needs a separately reviewed library contract and bound before selection. Neither task failure nor a stopped wait proves storage reusable.

## Cancellation, commit and all exits

A cancellable child declares frame-incarnation identity, checkpoints, commit, bounded masks, cleanup/join graph, quiescence and terminal bound. Service cancellation additionally uses R-12-097's generation/request ID and existing control plane, with no new wire field or ring. A local `Task` does not restore the deleted IDL `future` constructor.

Cancellation delivery latches a persistent bit and marks descendants in bounded graph order; terminal completion is separate. Registration reads the bit, so every child registered after cancellation starts marked and takes the unstarted path. Spawn retains registration/capacity outcomes. Only the owner's graph registers into its scope: scope handles do not transfer to children, and cleanup registers none. Cleanup may run synchronous steps, directly await a [cleanup-compatible sequential helper](#sequential-async-composition), join registered children and perform declared service/control requests. Each helper's state and bounded cleanup were reserved in the current task; helper composition requires no child registration. Later grandchildren belong to their live parent's scope and `B_terminal`.

Service delivery may wait for a scheduled control-plane visit; examine transfer refusal and reoffer only under the bounded policy. Receipt proves neither loan release nor quiescence. `cancel_answer` differs from terminal status: `too_late`/`not_live` are control replies. `cancel_cancelled` commits to the cancelled-completion path, whose storage stays owned through release.

| Target state when its cancellation decision runs | Required continuation |
| --- | --- |
| Dormant, not registered | The owner may dispose locally under `Dispose`; no nonexistent service request is cancelled. |
| Registered but not started, including a child registered already marked; service request still Submitted | Cancel before body effects; consume/restore its input resources through the unstarted cleanup path and record one `cancelled` terminal result. |
| Live before commit | At the declared checkpoint, accept cancellation and enter cleanup. Between checkpoints the bit persists; only the bounded declared segment may run before the next decision. The decision point's operation contract supplies the precommit cancellation semantics. |
| Commit already linearized | Answer `too_late` and finish the committed protocol normally. The scope may remain cancelled, but cannot undo the operation or retire an already-consumed commit token. |
| Target no longer live, stale generation, or non-cancellable operation | Use R-12-097's `not_live` control answer where applicable. Examine it and inspect the already-owned terminal/generation state; it is not permission to invent successful cancellation or free the frame. A non-cancellable child requires a bounded normal join contract. |
| Accepted cancellation during cleanup | Keep cancellation latched and continue the same cleanup; do not restart it, publish another terminal record or reenter ordinary work. Repeated requests have the declared idempotent observation of the same live cleanup decision. |

The final checkpoint arbitrates cancellation before a bounded no-capture/no-suspend commit segment. An observed request wins and skips commit. Arrival afterward is not acceptance, even before the instruction: decide after commit as `too_late`, with committed state represented before the next checkpoint. An already-terminal target answers `not_live`; its original result remains authoritative. Service lowering must refine its existing R-12-097 serialization points.

At await, validate generation, select the parent's cancellation/finite-deadline outcome, then collect ready child results in declared order before cleanup or ordinary continuation. Cancellation does not discard a ready result or execute ordinary work. Existing commits/terminal records cannot be reclassified by deadlines. The interface must choose whether precommit expiry yields `deadline_expired` directly or requests cancellation then yields `cancelled`.

Existing runtimes illustrate distinct spawn/cleanup choices:

| Runtime | Cancelled-scope behavior |
| --- | --- |
| [Kotlin default start](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/-coroutine-start/-d-e-f-a-u-l-t/) | Does not execute a coroutine cancelled before start; considers it cancelled. |
| [Java JDK 27 `fork`](https://docs.oracle.com/en/java/javase/27/docs/api/java.base/java/util/concurrent/StructuredTaskScope.html) | Returns `UNAVAILABLE` without a thread on a cancelled scope; throws `IllegalStateException` after owner join/closure. |
| [Python `TaskGroup.create_task`](https://docs.python.org/3/library/asyncio-task.html) | Closes the coroutine and raises `RuntimeError` during shutdown. |
| [Trio](https://trio.readthedocs.io/en/stable/reference-core.html) | Child inherits nursery cancellation scopes and runs to its first cancellable checkpoint, which raises `Cancelled`. |
| [Swift SE-0504](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0504-task-cancellation-shields.md) | Outside a shield, `addTask` creates an immediately cancelled child; `addTaskUnlessCancelled` starts none. A shield starts children uncancelled. |

Kotlin's [`NonCancellable`](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/-non-cancellable/) recommends wrapping cleanup children in `coroutineScope`. Vela instead gives marked registration one `cancelled` result without body effects and writes cleanup sequentially. [R-05-065](../../../spec.md#r-05-065) prefers sequential cleanup over a speed-only concurrency mechanism; its longer `B_cleanup` must fit the terminal bound. Declared service requests may still overlap waits by submission before await.

| Exit | Resource and control duty |
| --- | --- |
| Fallthrough, return, `break`, `continue`, propagated `Result` | Close local loans and establish the specific return/loop invariant. Crossing a scope boundary elaborates to its explicit join or early-exit graph. Handling a returned `Err` inside the scope without such an exit does not cancel siblings. All branches retain their reason and resource predicate. |
| Handler abort by zero resumption | Run the continuation's `Dispose` graph, including child joins and must-examine verdicts; return only its declared disposed resources. It is an explicit typed branch, with no stack walk or unwinding. |
| Precommit cancellation or scoped timeout | Stop ordinary work after the declared decision, cancel/join the children already registered while registering none, quiesce device-held references, run cleanup, then publish the chosen terminal result and release according to the pool contract. |
| Client wait timeout | Stop that wait only. The enclosing scope retains the task, authority and completion obligation; a later join or explicit scope cancellation remains required. It cannot return a loan as if the operation had stopped. |
| Declared child `Failed` outcome | Preserve its typed outcome, mark the owning scope once under the fixed failure policy, cancel/join affected siblings and keep all resources indexed by actual outcomes. A `too_late` sibling completes normally and is still joined. An ordinary `Completed(Err(e))` remains a returned value. |
| Postcommit normal completion | Preserve the committed effect, complete its bounded remaining work, quiesce and return the actual outcome. No cancellation acknowledgement grants earlier storage reuse. |
| Fallible cleanup | Its declared result graph either reaches a bounded recovery cleanup with the retained resources or takes the existing fail-stop path. A cleanup error is not a returned writable owner. No unbounded retry, cleanup recursion or new cleanup resource request is permitted. |
| Compartment fault, overrun, session teardown or restart | Source cleanup is not assumed to execute. Existing containment/revocation and generation change govern recovery; an old service request has the R-12-093 logical `peer_restarted` result. Storage remains unavailable until the platform reuse gate, including outstanding device authority, completes. |

R-12-100 terminal completion retains no DMA capability. Reclamation also needs every R-12-094 reader consumed and the pool release-to-Reusable gate; revocable storage retains R-08-007a's barrier/sweep. A deleted handle, error or absent completion proves no quiescence. Missing the DMA bound invokes R-12-099 fail-stop.

## Compositional handler summaries

This section is retained for the deferred multi-shot search extension. Its nested-choice, clone and complete-search bounds are not prerequisites for the first async service or a one-shot handler client. A selected one-shot handler still needs its actual work, frame and disposal bounds through the common resource derivation.

A public higher-order handler contract states the source-work and live-frame
bounds needed by its callers. Ordinary ghost parameters and `requires`/`ensures`
carry these summaries; the [BestScore example](../verification-strategy.md#handlers-with-accountable-continuations)
uses an illustrative `SearchBudget` library record with natural-number `Work` and
`Frames` fields. The summary binds the callback model, captures, selected handler
clauses and resumption strategy. It covers every permitted reply history, including
nested choices, forwarding and all reachable exits. A callback or handler change
invalidates that evidence through its semantic dependencies.

`Search.ExpansionFits(body.Model, budget)` denotes checked compositional evidence
under this fixed handler strategy. Its derivation combines callback contracts and
handler rules to establish the advertised limits; it is not an assumed Boolean or
a renamed assertion of the desired postconditions. Inference may reconstruct a
summary, but a missing bound or failed reconstruction remains an obligation.

The source observation model defines the counted work events and frame lifecycle.
Work includes the callback and handler steps, resumptions, cloning and disposal;
sequential work adds and alternatives take their permitted worst case. A multi-shot
handler charges every explored resumption. Along `d` successive binary choices,
exploring both replies at each choice can reach `2^d` leaves even though each
operation resumes at most twice. A local resumption allowance alone supplies no
bound on complete exploration. `PeakFrames` counts the maximum simultaneously live
source frames, including retained continuations and handler environments under the
declared representation; it is not the total number of resumptions.

These source summaries grant no pool authority or physical capacity. Lowering
connects them to frame layouts, reserved slots and bytes, including unused
reservations and metadata under [R-08-045](../../../spec.md#r-08-045), with exhaustion
handled under [R-08-047](../../../spec.md#r-08-047). Target cost and storage still come
from [R-05-102](../../../spec.md#r-05-102) and
[R-08-017](../../../spec.md#r-08-017)'s shared derivation; a source step is not a target
cycle. The bounds below retain scheduled gaps, external waits and cleanup costs.

Qualification under `HA-resume-dispose`, `HA-suspend-scope` and
`HA-lowering-erasure` includes a
nested-choice client, sequential frame reuse and simultaneously retained clones.
Refuse a summary charging only the largest branch when both are explored, one
omitting callback or disposal work, a stale callback/handler summary, and a
live-frame bound presented as reserved-byte or target-time evidence. Positive and
negative cases retain the same declared source measures and representation.

## Bounds and progress premises

Specialization bounds frame nesting, children, resumptions, checkpoint distance, masks, cleanup, control delivery, device quiescence and publication. Each segment has a decreasing measure or acyclic bound. Service repetition may be indefinite across requests; each accepted request/cancellation cleanup still has a finite terminal contract. Join/resource dependencies must be acyclic: no descendant waits for a parent release that depends on its own join.

For finite path `p`, `L(p) = sum(C(v)) + sum(G(e)) + sum(D(e))` counts work, scheduled activation gaps and external waiting not already charged, with occurrences counted. Bound admitted paths by their maximum or conservative loop/visit sums. Coefficients come from named artifacts, not grade arithmetic. R-05-102/R-08-017/R-11-006 cost/storage evidence includes ready continuations, polls, cancellation checks and unsuccessful visits.

```text
B_decide(t) = B_deliver(t) + B_checkpoint(t)
B_tail(t) = sum(B_terminal(child)) + B_collect(t) + B_cleanup(t)
            + B_quiesce(t) + B_publish(t)
B_cancel_suffix(t) = B_tail(t)
B_commit_suffix(t) = B_normal_remaining(t) + B_tail(t)
B_cancel_request(t) = B_decide(t)
                     + max(B_cancel_suffix(t), B_commit_suffix(t),
                           B_unstarted_suffix(t))
B_terminal(t) >= max(B_normal_from_start(t), B_cancel_request(t))
```

Use one elapsed scheduled-time unit. `B_decide` runs from the declared request/expiry origin to the authoritative cancel/commit decision; delivery includes propagation/reoffers and checkpoint distance includes masking. Suffixes start there, including postcommit work when a precommit arrival is decided after commit. Example delay five, committed work ten and tail one require sixteen, not `max(6,11)`; these are illustrative units, not measurements.

The sums conservatively serialize children and include activation gaps; overlap proof is optional. Sum the bounded child set fixed at cleanup entry, including already-marked registrations. Each child's maximum covers cancellation, normal/unstarted paths and later grandchildren in its own scopes; `B_collect` charges parent result handling. Path derivations charge disjoint work/wait occurrences in comparable units. `B_unstarted_suffix` includes cleanup/publication, and `B_normal_from_start` includes registration-to-first-activation delay. A request already at its decision uses the applicable remaining suffix. Generation teardown/faults retain separate outcomes/bounds. Release additionally includes collecting this task's completion, readers, erasure, revocation and sweep; a terminal bound cannot replace it.

A directly awaited helper contributes its work, waiting and checkpoint distance to the enclosing task's path once, either expanded into `C/G/D` or through a proved subgraph summary. It is not another child term. Its cleanup contributes to the enclosing `B_cleanup`; nested masks and the depth-bounded cleanup sequence enter the same decision and tail bounds. Refuse an accounting that omits helper storage/work, resets the caller's mask allowance, or counts an inlined helper and its summary twice.

A witness states units and fits these sums to the interface terminal declaration and composition slot/cadence/capacity checks. [RingContract.v](../../../../proofs/RingContract.v) supplies service `cancellation_interval`/`op_max_to_terminal` arithmetic; [CopyRingService.v](../../../../proofs/CopyRingService.v) supplies cleanup/held-reference declarations. Neither connects Vela frames, waits or execution to that arithmetic; no target constants are measured here.

The [timing/progress survey](../verification-strategy.md#research-that-changes-the-experiments) records donors whose response-time WCET parameters or liveness fairness are premises. This profile grants neither those coefficients nor general scheduler fairness.

Progress assumes admitted WCET, activation cadence, live generations, bounded device service/quiescence and control delivery. An unbounded/unavailable peer requires a bounded failure/teardown branch or refusal of hard progress. Hardware faults have separate recovery bounds. Missed progress assumptions never establish completion or release ownership.

<a id="qualification"></a>

## First async service qualification

The [first-release qualification](../first-release.md#qualification) and [delivery plan](../../../../PLAN.md#vela-first-release-delivery) must first establish the synchronous component, its concrete representation and a separate library client. The first async extension then selects a real bounded request service over those proved primitives. Before implementation, freeze its actual packet/operation format, represented capacities and cleanup reserve, independent valid/invalid byte fixtures, complete result/resource contract, service generation/commit interface and target evidence endpoint. A storage pattern alone is no valid-message witness. Neither a shared counter nor general handlers are prerequisites unless that service uses them.

The service exercises a reusable sequential async helper and one structured child. A second child is introduced only for the scope-failure/ordering fixture, with all outcomes fixed before implementation. Every accepted input has an inhabited concrete entry state, and all resource claims are checked over the elaboration image. The initial acceptance set is:

| Case | Required behavior and evidence |
| --- | --- |
| Sequential helper, ready and pending | The same declared value/resource result as its synchronous contract where applicable; one task, bounded nested state, checkpoint even on ready, and no child registration introduced by helper extraction. Compare factored and inline versions without requiring inlining. |
| Error value versus task failure | `Completed(Err(e))` handled in place leaves siblings active; explicit propagation across the scope closes it; declared `Failed` triggers the fixed cancellation/join policy. Interface changes cannot silently promote an error payload. |
| Capacity exhaustion and cancellation before start | Spawn returns the unchanged dormant computation on exhaustion; a marked child or cancelled direct helper runs no body effect and returns/disposes its actual captures once. |
| Commit race and reusable cleanup helper | Cancellation accepted before commit runs helper then caller cleanup once; after commit, preserve the effect and complete the bounded suffix. Repeated cancellation during a directly awaited cleanup helper neither restarts cleanup nor creates a child. |
| Ready result beside cancellation or failure | Preserve and eliminate every produced result/resource by named outcome, including simultaneous terminal records in declared order and a committed sibling that answers `too_late`. |
| Cleanup failure, late completion and stale handle | Follow bounded recovery/fail-stop, retain unavailable backing, reject stale generation/incarnation use, and prove the complete quiescence and release-to-Reusable gate before reuse. |
| Cost, storage and source maintenance | Charge nested frames, masks, results, children and cleanup once; source edits invalidate affected evidence; factor/unfactor a helper and change its resource contract with diagnosed dependent rechecking. |

Retain matching negative neighbors that skip a ready checkpoint, omit helper state, double-consume a returned resource, promote `Err` implicitly, reset a commit phase, spawn during cleanup or reclaim on cancellation acknowledgement. They must reach and fail the intended semantic premise; an unsupported syntax error is no safety verdict. Source proofs, final-byte correspondence and production progress/resources remain separate acceptance subjects.

## Positive derivations and invalid neighbors

These symbolic, conditionally inhabited paper derivations are retained design fixtures, not executable checker results. Multi-shot and shallow cases belong only to their deferred extension. They do not replace the [first async service](#first-async-service-qualification). Fix positive frame capacities, initialized representations, injected authority and live generation (`emp` for empty resources); fix expected branches/resources before implementation. Concrete laws remain open below.

| Case | Trace and resource derivation |
| --- | --- |
| Zero resumption with disposal | `Own(packet) * EraseRequired(packet)` is moved into `k` at a handled choice. The clause selects rejection and `dispose(k)` runs a finite byte-erasure graph, consumes the erasure obligation and returns the cleared owner to the caller. Trace is capture, named reject, erase, disposed return; no resumed body event occurs. This needs capture/disposal and erasure laws; no external operation or verdict is silently omitted. |
| One resumption with a loan | A pinned outer packet owner lends a shared prefix into `k`; the parent access stays suspended. `resume k(reply)` uses the view, ends the loan and returns its restoration evidence, reconstituting the enclosing parent's access exactly once under the loan-end law. The clause consumes the returned result. A deep handler's return transformation runs once; the shallow variant resumes `k` inside a rehandle whose handler of the same signature has an identity return clause, so the clause receives the raw result and explicitly applies its transformation. |
| Multiple resumptions | A handler around `let b = perform choose(); callback(snapshot,b)` captures only a stable immutable snapshot and a proved repeatable effect-free callback. Its owning packet/frame stays outside the delimiter. Clone with `Dup`, resume with `false`, resume with `true`, collect both scalar results, dispose the template. Each invocation calls the callback once by its contract, so the source callback-event bound is two; each clone has independent local storage, resolves its reinstalled handler relative to its own invocation frame and has its own result elimination, while the snapshot outside the delimiter is shared under its immutable permission. No unique owner or protocol token is cloned. |
| Nested lookup and forwarding | An outer handler binds `c` for `choose` and an inner handler binds `t` for `trace`; the inner body performs through both. Performing through `c` reaches the outer frame directly and captures the intervening inner frame without running its clause. Deep resumption reinstalls the outer handler and restores the inner `trace` handler. A second `choose` handler installed between them, whose capability the body does not name, joins `k` in the same way and does not intercept the operation. An explicit forwarding clause instead moves `k` into an adapter that performs through a further outer `choose` capability the clause was given; disposal of the adapter must dispose `k` too. Neither trace environment is lost at forwarding. |
| Shallow rehandle | A shallow handler `S(0)` binds `s` for `tick` and carries the count `0` in its environment; its body performs `tick` through `s` twice and returns a scalar, with `emp` resources. The first `tick` captures `k1`, whose segment retains `s` with its delimiter reference as the hole. `S(0)`'s clause resumes `k1` inside a rehandle installing `S(1)`, of the same effect signature, at `k1`'s invocation frame, so the hole resolves there and the second `tick` through `s` reaches `S(1)`, not `S(0)`. `S(1)`'s clause captures `k2` and rehandles it with `S(2)`, whose return clause pairs the body's raw scalar with `2`. Each rehandle binds a fresh incarnation of the slot the previous shallow handler vacated when its environment moved to its clause, and the rehandler set specialization fixes is the one declaration `S`; the trace is two ticks and one return, and each clause returns what its rehandle returns. |
| Ready await | Spawn child at its assigned activation; it records `Completed(value)` and returned resources. Parent reaches await with cancel bit clear, performs the checkpoint, matches `Completed` and continues along its admitted ready edge. With parent cancellation already latched, the same ready result is collected and parent cleanup runs; it is not discarded and ordinary work does not run. |
| Pending await | Spawn, parent checkpoint, pending PC store, poll-site return; child completes at its admitted activation; parent is revisited, rechecks authoritative completion state, checkpoints and matches the result. All retained loans name pinned live storage and closed invariants across the gap. |
| Cancellation race | Request observed at the final checkpoint gives cancelled cleanup with commit token unspent; a request after that checkpoint's bounded commit segment gives `too_late`, then the single normal terminal completion. A cancellation arriving after terminal gives `not_live`; collection still consumes the original result. |
| Child failure and cleanup | Child at lower index selects its declared `Failed` exit before commit; the scope observes that outcome, marks its sibling, receives sibling `too_late`, joins that sibling's normal completion and returns the indexed pair of outcomes after cleanup. Parent storage stays pinned throughout. A declared cleanup failure keeps ownership unavailable and takes bounded recovery or fail-stop. |
| Spawn after the latch | Within one parent activation, the parent's bounded segment reaches an admitted observation site that is not a checkpoint, discovers child 1's recorded `Failed` outcome and latches the scope's bit; the same segment then reaches a `spawn`. Activations are cooperative under R-07-037a, so nothing else can latch the bit mid-segment. Registration binds child 2's frame and completion record and marks it; its first activation takes the unstarted path, restores its inputs and records one `Cancelled` result with no body event. The parent's next checkpoint enters cleanup, which joins both children, registers none and returns the indexed failed and cancelled outcomes. |
| Capacity and timeout | Full frame capacity gives `CapacityExhausted(pool)` and the unchanged dormant computation. A client wait timeout leaves an already-spawned task in its scope. A scoped timeout requests cancellation and joins under `B_terminal`, including a committed child's normal-completion branch. |

The combined Q25d client is a deferred cross-feature research fixture. It prepares an initialized private packet and an immutable snapshot under the [synchronous core's copy-once contract](../core-design.md#composed-qualification-fixture), then registers a bounded child. Its pure choice handler runs the repeatable graded callback on that snapshot; the packet owner and frame permission stay outside the multi-shot delimiter. The child accesses the guarded scalar `CountCell(c,g)` only through the [mutability dossier](interior-mutability.md)'s `commit_add(handle, AddOnce(c,g,k,n), n)`. The linear `AddOnce` authorization is outside every repeatable capture. Its conserved allowance proves the aggregate count representable. This optional fixture supplies no critical-path requirement for the synchronous release or the first async service.

One concrete data witness has capacity `N = 4`, admitted length `n = 2`, source bytes `[1,2]` and the initialized private destination `[1,2,0,0]`. The pure repeatable callback receives the immutable prefix snapshot and a represented Boolean, returning a scalar without touching the packet owner. The handler resumes on `false` and `true`, giving two source callback events by that contract. A `Ready` parser result additionally needs an actual valid-header witness for the selected encoding; the byte pattern here witnesses storage, ownership and the local counter path, not unspecified parser validity. This retained fixture supplies neither a selected packet format nor branch expectations, so its combined parser case is not inhabited. Its concrete resource inhabitant remains a `GF-resource` prerequisite under the [foundation and pricing review](full-language-review.md#reviewed-implementation-pricing); no assumed inhabitant can open implementation.

The child's final checkpoint and `commit_add` form a bounded no-capture/no-suspend segment. Precommit cancellation retires `AddOnce` once without addition and disposes the packet under its resource contract. The single aligned scalar AMOADD is the committed effect; the frame records `Added(c,g,k,n,old)` before the next checkpoint. A later cancellation is `too_late`, and normal cleanup returns the packet owner and the actual result. The counter is arithmetic state, not publication of packet contents; any service completion uses its separate release/acquire proof. A second child supplies the simultaneous failure and sibling-join case. This is a proposed local child operation; mapping it to any service interface must explicitly supply that interface's cancellation/commit declaration and current generation, not alter the ring schema.

| Well-formed change to a positive case | First refusing premise |
| --- | --- |
| Clone the one-shot `k`, or hide it in a shared cell and invoke both aliases | `Dup` for its transitive owner/loan or one-shot consumption; a duplicable cell descriptor does not duplicate contents. |
| Keep `AddOnce` inside the multiple-resumption delimiter | `Dup` for the unique commit authorization; callback repeatability is insufficient. |
| Dispose `k` without erasing its packet or without examining an already-produced child failure | `Dispose`'s erasure or mandatory-verdict elimination obligation, respectively. |
| Resume after the captured parent frame expires, move a frame retaining a self-reference, or store an absolute reference into a captured segment's own frames | `Suspend`'s live incarnation, stable address and parent-lifetime premise; for the segment, the frame-relative representation premise of `Capture` and `Suspend`, and of `Dup` for a multi-shot segment. |
| Perform through a handler capability outside its handler's scope, from a closure retaining it | The lexical-scope premise: a use site names a captured capability only where every capture is in scope, and the closure's capture set records it. |
| Pass a closure retaining `c` to the `choose` clause of `c`'s own handler, as the operation argument or through a cell | The lexical-scope premise: operation argument types carry no capability bound inside the handled body, and the clause, typed without `c`, cannot use a closure whose captures include it. |
| Spawn a child whose dormant value captures a handler capability | The lexical-scope premise: a dormant computation constructed for a spawn is typed with no handler capability in scope. |
| Resume, clone, rehandle or dispose `k` while the clause still holds a loan an operation argument lent it into `k`'s frames | The argument-loan premise: the loan ends before the clause acts on `k`, so neither `Dup` nor a rehandle sees it. |
| Resume a shallow `k` whose segment retains its handler's capability outside a rehandling expression | The shallow rehandle premise: the segment's reference to its delimiter is a hole that only a rehandling handler's invocation frame fills. |
| Rehandle a shallow `k` with a handler declaration outside the set specialization fixed for its segment | The finite rehandler set: the slot is sized for, and performs dispatch over, only that set. |
| Perform through a handler capability missing from the enclosing function's effect contract | Effect-contract membership: the contract is the capability set the computation may use. |
| Return a parent writable owner while a pending child or returned view retains its loan | Indexed exit restoration and structured-scope extent. |
| Skip the ready-await checkpoint when the cancel bit is set | Checkpoint trace and cancellation-priority simulation; immediate readiness cannot authorize ordinary continuation. |
| Clear cancellation in a mask region or resume ordinary work after accepted cancellation | Sticky cancellation invariant and cleanup-only transition graph. |
| Spawn a child from a cleanup graph | Cleanup-only transition graph: cleanup has no registration edge. |
| Register into a scope from a child holding its handle | Owner-only registration: only the scope owner's own graph has a registration edge into the scope, and a scope handle does not transfer to a child. |
| Spawn after the latch and claim the child's body events or an `ok` result | Registration-time marking: the child's trace is the unstarted path, with no body event and one `cancelled` result. |
| Reuse a terminal slot under a reader, DMA holder or pending required sweep | Request reclamation and pool release-to-Reusable premise; terminal status alone proves none of them. |
| Ignore sibling failure after another child has failed; overwrite a full completion record | Mandatory outcome elimination or pre-reserved completion capacity. |
| Free the task on `too_late`, `not_live` or wait timeout | Missing terminal ownership transfer and quiescence/reclamation evidence. |
| Add an unbounded cleanup retry, forwarding cycle or ready-task selection queue | Finite path/ranking proof or the R-07-037a lowering obligation. |
| Perform packet mutation after counter-only AMO as if it published the packet | The distinct publication/ownership theorem; counter arithmetic grants no payload access. |

Each selected extension's negative preserves supported parsing/resolution, unrelated entry resources and operation identities, and fails at its named premise. Missing implementation/syntax, timeout or an unrelated theorem failure supplies no rejection evidence. A commissioned extension must instantiate its concrete representation, expected outcomes and relevant failing goals; deferred cases are not first-release acceptance duties.

## Open laws and amendment duties for Q25d

Every row below is a theorem obligation over `Interpret` and the selected existing anchor, including the relation from exact source to that interpreted computation. Shared rows apply only to the selected feature subset. Deep one-shot and sequential-async laws are qualified without cloning, shallow rehandling or arbitrary grade domains; the extra clauses remain deferred until those extensions are commissioned.

| Open obligation | Required statement and evidence |
| --- | --- |
| `HA-capture-substitution` | Prove context moves preserve selected usage dependencies, separation, capabilities and loans, and reply substitution preserves deep/forwarded result contracts. Capability selection reaches the named handler frame and captures intervening handlers unexecuted; an effect-polymorphic callee's handlers cannot intercept operations through its capability parameters. Prove lexical scope through arguments, replies, selected cells and children: clauses lack their own or body-bound handler capabilities, spawned values capture no handler capability, and use requires every retained capture in scope. Argument loans resolve against `k`'s invocation frame and end before resume/dispose. Include nested environments and forwarding adapters. The deferred clone/shallow extension additionally proves argument-loan closure before clone/rehandle and that a shallow delimiter hole resolves only to its same-signature rehandler, with no shallow resume outside rehandle. |
| `HA-resume-dispose` | Prove one-shot transfer once and zero-shot disposal closing erasure, restoration, mandatory verdicts and protocols on every selected exit. A duplicated handler loan authorizes perform only; capture authority comes from the running context. The deferred multi-shot extension additionally proves transitive `Dup` for separated represented invocations, fresh inputs and compositional traces: clones' internal references/reinstalled handlers denote their own frames and only external storage is shared under permission. Continuations stored in selected mutable interfaces retain the corresponding disposal duties. |
| `HA-suspend-scope` | Every interpreted activation preserves the frame's typed representation, stable addresses and loan tree; no parent owner or frame is released before every child's actual indexed terminal resources and returning views are discharged. Direct await composes bounded nested state in the same task without hidden child registration, preserves active lexical capabilities, and restores helper resources before the caller continues or cleans up. |
| `HA-cancel-progress` | Relate the interpreted sticky-bit/commit machine to the declared R-12-097 service decisions where used, with exactly one task terminal result, finite masked distance and explicit delivery/child/quiescence bounds. Prove direct-helper checkpoint/commit inheritance and cleanup composition without a fresh mask budget or duplicate cleanup. Distinguish ordinary `Completed(Err(e))` from declared `Failed`; fixed-order observation triggers scope failure only under the explicit policy or source early-exit edge. Cover owner-only registration, children registered already marked after the latch and cleanup graphs that register none, so `B_tail` sums over the scope's child set, fixed once cleanup begins, and each child's `B_terminal` bounds the grandchildren its own scopes register. Prove cleanup failure preserves safety without assuming source cleanup on fail-stop. |
| `HA-lowering-erasure` | Prove PC-graph simulation of checkpoints, slot-directed capability selection, return transformations and indexed exits; erasure preserves executable tags/effects. One-shot capture preserves stable frames. For the deferred cloning/rehandling representation, establish delimiter-relative references from handler entry, including nested segments and handler links/capabilities, so capture moves none and `Dup` rewrites none. Resolve them against each invocation frame and fresh incarnation, including shallow delimiter holes and finite-set rehandler dispatch. Moving or, when supported, cloning effects across checkpoint, commit or handler boundaries needs preservation laws. Connect actual graph cost/storage, TAL derivation and pinned Sail. |
| `HA-combined-embedding` | First instantiate the resource interface with the real bounded async service, its direct helper, structured child and intended outcome/cleanup negatives. Prove that the no-suspension restriction retains the synchronous core's interpreted behavior and exit predicates. A later cell or multi-shot extension additionally instantiates its own selected protocol and combined client; the retained Q25d counter/graded-search fixture is deferred until those features are commissioned. |

Q25d reviews and assigns these missing laws once. Existing concrete/target debts remain with the [foundation map](../../../hardware/cheri-foundation-map.md) and [compiler contract](../compiler-route-contract.md); naming a law supplies no evidence, estimate or implementation gate.

| Requirement boundary | Exact disposition owed before dependent implementation |
| --- | --- |
| R-08-046 pool inventory | Its current explicit inventory does not name general task, scope, continuation and completion-frame pools. [Q25d's classification](full-language-review.md#r-08-046-and-what-the-languages-runtime-varying-storage-is) reads them against that inventory and every manifest field; no existing named class covers them. The required amendment to the entry and cited prose remains a gate before dependent runtime implementation and is not taken here. R-08-045's charge and R-08-047's exhaustion semantics remain obligations; a hidden frame allocator cannot qualify. |
| R-05-020/R-05-020a translator admission | This dossier adopts the [interpretation commitment](#interpretation-commitment): all laws concern the checked image in an existing anchor, under R-05-009 and R-05-020a. The [composition review](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows) governs source correspondence and concrete-law prerequisites. This design choice supplies no proved elaborator, source correspondence or concrete handler/async laws; an independent source semantics or trust-base addition would still require R-05-020's amendment conditions. |
| R-05-100 and R-07-037a | Preserve the typed absence and cooperative-reaction shape by the PC-graph proof. No amendment is requested by this proposal. An implementation needing unwinding, an internal thread, dynamic task scheduling or a blocking join fails this design; choosing it would require an explicit amendment to these exact requirements before implementation. |
| R-12-097, R-12-093 through R-12-095 and R-12-100 | Reuse the declared control replies, terminal ownership, completion capacity and device-quiescence protocol. Local task syntax changes none of them. Any requested new reply/status, cancellation transport or earlier release rule requires amendment of its owning entry and the IDL/generated contract; none is proposed here. |
| R-05-132 through R-05-134; R-11-006 | Project source reasoning into existing TAL attributes and separately checked CIC obligations, with actual schedule evidence. A new on-device grade or checkpoint interpreter cannot be presumed admitted; the exact attribute criterion would need its own demonstration or amendment. |

R-18-034 amendments require register/prose co-reading and integration validation. Corpus checking proves none of these laws. Design acceptance is an attended review of choices, shared interfaces and limits; mechanization, frontend admission, execution and timing keep separate predicates.
