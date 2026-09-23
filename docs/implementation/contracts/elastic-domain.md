# Elastic-domain contract

This is Q34a's contract: the statement the kernel's elastic dispatch and the pool service are later proved against, which the [crown-jewel inventory](../../assurance/crown-jewels.md) carries as row 31 (`CJ-ELASTIC`). Its Gallina statement is [ElasticDomain.v](../../../proofs/ElasticDomain.v). The [register](../../requirements-register.md) owns every obligation: R-07-037e through R-07-037i, R-08-047a through R-08-047c, R-11-006c and R-15-007k, with R-07-031b's tentative flag on invocation (iii), R-07-027a's placement of the dispatch state in partition-context fields and R-07-032's single runtime choice. This contract adds no obligation. Three things row 31 is constrained by are not stated here: R-08-047d's exhaustion ladder, which the row does not list among its statements; R-11-006c's focus dispatch bound; and the minimum-share admission that R-07-037g's second acceptance and R-11-006c both state. The bound and the minimum share are admission arithmetic over R-11-006c's admissible load and the constants Q34e composes. Where the register fixes a property the artifact states the property, and where the register leaves a question open or states something a conforming trace refutes, the artifact exhibits the construction and this document records the finding.

The artifact extends the existing vocabularies by `Require` rather than copying them. [PartitionContext.v](../../../proofs/PartitionContext.v)'s `Rotation`, `Action` and `constants_paid` define and price the intra-slot step. [CyclicExecutive.v](../../../proofs/CyclicExecutive.v)'s `Slot`, `Frame` and `slot_index_at` are the envelope's geometry. [MemoryPlan.v](../../../proofs/MemoryPlan.v)'s `MemClass` indexes the pool extents and its `representable_granule` decides whether a size class narrows exactly.

## What is stated and what is proved

A statement is a definition that a later proof must meet. A proved result is a theorem the artifact proves of that definition, at the contract level only: no kernel, pool service, heap library or toolchain pass is proved against the contract here.

| Statement | Register source | Stated as | Proved here | Consumed by |
| --- | --- | --- | --- | --- |
| The envelope | R-07-037e, R-07-037f, R-08-047a | `Domain`, `Manifest`, `envelope_admits`, `EveryMemberCarriesTheLabel`, `NoMemberIsFixedTier`, for one island | an admitted envelope has one label and no fixed-tier member | Q34e composes a domain that `envelope_admits` accepts |
| Launch by activation | R-07-037i | `launch_ok`, `ActivatesOnlyPlaced` | `launch_ok` activates only placed dormant contexts | Q34b's launch, close and focus request cell |
| Confinement of the runtime choices | R-07-037e, R-07-037g, R-07-032 | `Global`, `ReadsOnlyItsLabel`, `MovesNothingOutside` | `select` reads only the domain's own state | Q34b's label-internal unwinding case |
| The dispatch rule | R-07-037g, R-07-027a, R-07-031b | `PcFields`, `DState`, `Decl`, `Selects`, `select`, `reply`, `charge`, `rebalance`, `Run`, `RunConforms` | `select` chooses exactly the earliest eligible virtual deadline and idles only when nothing is eligible | Q34b refines `select` and `reply` over partition-context fields, and `charge` and `rebalance` once the register answers F3 |
| The boundary rule | R-07-037g, R-11-006c | `boundary_need`, `boundary_ok`, `NeverCuts`, `decl_admits` | a conforming dispatch ends, sink and step included, before the slot boundary; the backstop alone bounds an unchecked sink | Q34b's intra-slot step; Q34e's admission |
| The intra-slot step | R-07-037g, R-07-037d, R-07-014c | `ElasticStep`, `elastic_performs`, `step_between`, `decl_enumerates` | a step between members of different applications clears the zeroize class, leaves no residue and costs one `vmclear`; a step inside one application is the rotation; the clearing step is satisfiable at every machine | Q34b's inter-application `vmclear` |
| The share bound | R-07-037g | `Stint` (served, step and idle), `lag`, `LagBounded`, `ShortfallBounded`, `ShareBound`, `register_lag_bound` | the instant half implies the interval half, so Q34b owes the instant half alone | Q34b's share-bound theorem, blocked on finding F1 |
| The yield-bound obligation | R-07-037h | `Cfg`, `Reaction`, `ExitReaction`, `ReactionsWithin`, `SinksYieldWithinOneReaction`, `YieldBoundAdmits`, `invocation_gaps` | the counter protocol keeps every path between invocations within the call bound | Q34d's yield-point pass, sink lowering and cost check |
| The pool service's guarantees | R-08-047b, R-08-006, R-08-007a, R-15-007k | `Arena`, `AllocEvent`, `LiveChunksDisjoint`, `BoundedExactly`, `ZeroedAtHandoff`, `ReusedOnlyAfterTheSweep`, `PoolGuarantees`, `class_exact` | each guarantee's meaning over bytes, bounds and positions, and that an exact grant needs no rounding | Q34c's chunk service refinement and size-class table |
| The heap library's narrowing | R-08-047b, R-15-007k | `HeapNarrows` over a member's chunk as the arena | n/a (stated, with witnesses) | Q34c's heap library refinement |
| Capability confinement | R-08-047c, R-12-007 | `EdgeKind`, `carries`, `leaves`, `edges_confine`, `PoolConfined`, `Transfer`, `Reach` | no sequence of transfers along the declared edges puts a pool-derived capability outside the domain when no edge leaving it carries one | Q34c, and the composition's check of its capability distribution |

The generated proof ledger binds R-07-037g to the selection, the confinement of the choice, the boundary rule and the clearing step between applications. None of those constants answers the share-bound acceptance, which F1 refutes as stated, and no discharge claim is bound to the share bound.

## Refutations

Each refutation is a concrete construction the statement rejects. The pool refutations break exactly one guarantee each, and the artifact proves the other guarantees of the same history.

| Refutation the item names | Construction | Rejected by |
| --- | --- | --- |
| A dispatch reading outside state | `leaky_choice` defers to another label's activity | `ReadsOnlyItsLabel` |
| A member cut by the boundary | a call-bound-only test (`thin_boundary`), no test (`no_boundary`), and the backstop standing in for the checked sink | `NeverCuts` |
| Two live chunks sharing a byte | `shared_history` | `LiveChunksDisjoint` |
| A chunk wider than its allocation | `wide_history`, and at the heap level `wider_allocation` and `chunk_wide_allocation` | `BoundedExactly`, `HeapNarrows` |
| A chunk handed out unzeroed | `unzeroed_history` | `ZeroedAtHandoff` |
| A chunk reused ahead of the sweep | `early_history`, and `presweep_history` with a sweep begun before the barrier | `ReusedOnlyAfterTheSweep` |
| A pool capability held outside the domain | `slotted_distribution` with a capability-slot endpoint and `storable_surface` with a store-permitted window | `edges_confine`, `PoolConfined` |

The artifact also refutes:

- a runtime slot-width choice, which moves an instant another tenant owns;
- a second label, a device-holding member and a shared extent inside one envelope;
- a launch that creates a member;
- a rotation that leaves vector state standing between applications, and a kernel that saves it;
- an unpolled back-edge, which no yield bound admits;
- a reaction above the declared bound;
- an exit block whose cost puts its reaction above every smaller bound;
- a sink that returns to a tentative poll site without yielding, which passes every other conjunct of `YieldBoundAdmits`;
- a miscompiled counter;
- an allocation outside the size-class table;
- a table class whose length or alignment would round.

The positive instances are:

- an admitted envelope and a placed launch;
- a step between two members of different applications;
- the conforming traces;
- a polled loop with its sink and real yield;
- a counter at a declaration;
- the pool and heap histories;
- a sealed distribution with an inbound capability-carrying edge.

## Readings

The artifact's header states each reading in full. In summary:

- Virtual time uses exact rational EEVDF arithmetic, the published algorithm's own arithmetic. A fixed-point kernel refines this rule only if Q34b's proof covers the rounding.
- The fixed tie order is the member enumeration order, and every fixed order is some enumeration order.
- A request lasts while the service since the dispatch is below the effective request. The kernel answers at the virtual time that service has reached. "An earlier virtual deadline" is strictly earlier, so a tie does not end the running member's request.
- A run is one dispatch: invocations at most one call bound apart, each answered continue until the last, which is either the member's own real yield or a switch-requested reply followed by the sink.
- Lag is service lag. A member accrues entitlement only while it competes, and the bound is taken over every enumerated member. `charge` and `rebalance` apply no virtual-time adjustment at a leave, join or reweight. This departs from EEVDF's published leave rule, which R-07-037g names. It is taken so that a competing member's accounting lag stays its service lag; F3 records the question.
- The share bound's time base is a parameter. `ServedTime` counts only served stretches. `SlotTime` counts all of the domain's slot time: served stretches, intra-slot steps and idle tails.
- The zeroize class is PartitionContext.v's zeroized CSR class.
- A poll site on a back-edge sits at the edge's target. A reaction ending at a poll site excludes that block, and one ending at an exit includes the exit block. A real yield is a marked poll site, and a switch-requested return enters a marked sink block along an edge from the invoking poll site.
- The pool guarantees are stated over an observable history of grants, releases, stores, zeroing, barrier completions and sweep passes.
- An edge is listed in the direction a capability can travel, and R-08-047c constrains the edges leaving the domain.

## Findings

Each finding is a register question the owner decides. The artifact exhibits the first three as computed facts and states the fourth as the reading it takes.

- **F1. The lag bound omits the sink.** R-07-037g's second acceptance bounds every live member's lag by the largest declared request plus one call bound. After its last continue, a conforming member runs up to one call bound to its next invocation and then up to one yield bound for its sink, which the boundary rule itself budgets. `the_register_s_lag_bound_is_refuted` exhibits a two-member trace in which every step is the rule's. Both members end with a served-time lag of magnitude 22/5 against a bound of 4, so at that declaration `ShareBound` at the register's bound is false and not a theorem Q34b can prove. The same trace stays inside the request plus a call bound plus a yield bound (`sink_inclusive_lag_bound`), which is named and not adopted.
- **F2. The share bound's time base is unstated.** Read over the domain's slot time, the intra-slot steps and the idle tails the boundary rule leaves accrue shortfall in every slot. `the_slot_time_reading_is_refuted` exhibits a single member at lag 18 against a bound of 4 after two slots of 12, of which it was served 6. Read over served time, the bound holds of that trace, and it cannot see the idling F3 exhibits. R-11-006c's third acceptance charges the idle tail to the domain and books it at R-17-007b. That places the tail in the domain's time without saying whether a member's share is measured over it.
- **F3. Which lag the share bound quantifies is unstated, and with it whether the dispatch applies EEVDF's published leave rule.** The published rule advances virtual time by the leaving member's lag over the remaining weight. Without that adjustment, `a_leave_without_the_published_adjustment_is_not_work_conserving` exhibits a member with work pending that never becomes eligible again: the core idles slot after slot while that member's served-time lag stays inside the register's bound. With the adjustment, `the_published_leave_separates_accounting_from_service_lag` shows the same member selected at once, its accounting lag at 0 while its service lag is -13/2. The register must say whether the bound quantifies the accounting lag the published rules preserve or the service shortfall its interval half is worded in; `charge` and `rebalance` follow its answer.
- **F4. Which members are live for the share bound is unstated.** A launched member with nothing pending would accrue entitlement it never uses, which no dispatch can bound. The artifact takes the bound over every enumerated member, each accruing entitlement only while it competes: live with work pending.

## What each successor consumes

- **Q34b** refines `select`, `reply` and `step_between` over PartitionContext.v's contexts and the fields R-07-027a places, and adds the request cell and the label-internal unwinding case. It refines `charge` and `rebalance` and proves `LagBounded` once the register settles F1 and F3, and preferably F2 and F4. Until then the register's own bound is refuted and the leave accounting is open.
- **Q34c** refines `PoolGuarantees` for the chunk service and `HeapNarrows` for the default heap library. It discharges `class_exact` with the composition's size-class table, states per-island pools and the quarantine's shape, and runs the generated campaigns its Check names over allocation, release and reuse histories of the kind `good_history` shows.
- **Q34d** produces the control-flow graphs, sink and yield markings and counters that `YieldBoundAdmits` and `invocation_gaps` read. It lowers the sink before the real yield on *switch-requested*, and adds the per-function cost triple for a reaction crossing a call.
- **Q34e** composes a domain that `envelope_admits` and `decl_admits` accept. It derives the focus dispatch bound and the minimum-share check over the admissible load, and measures what admission leaves unbounded.

## Evidence and its limits

The artifact's decisions are held by the proof gate: its compile, its exact assumption audit, its witness scan and the kernel recheck. Every record the file declares has a named `witness_<Record>` definition. The gate's witness scan detects only the records that type-ascribed binders quantify, a subset of them, so its count is a floor. Nothing here executes, and no witness value is a composition claim. Row 31 moves to `authored` only after independent review under R-05-150, for which the findings above are inputs.
