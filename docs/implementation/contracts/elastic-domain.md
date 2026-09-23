# Elastic-domain contract

This is Q34a's contract: the statement the kernel's elastic dispatch and the pool service are later proved against, which the [crown-jewel inventory](../../assurance/crown-jewels.md) carries as row 31 (`CJ-ELASTIC`). Its Gallina statement is [ElasticDomain.v](../../../proofs/ElasticDomain.v). The [register](../../requirements-register.md) owns every obligation: R-07-037e through R-07-037i, R-08-047a through R-08-047c, R-11-006c and R-15-007k, with R-07-031b's tentative flag on invocation (iii), R-07-027a's placement of the dispatch state in partition-context fields and R-07-032's single runtime choice. This contract adds no obligation. Two things row 31 is constrained by are not stated here: R-08-047d's exhaustion ladder, which the row does not list among its statements, and R-11-006c's focus dispatch bound, which admission derives from constants Q34e composes. Where the register fixes a property the artifact states the property, and where the register leaves a question open or states something a conforming trace refutes, the artifact exhibits the construction and this document records the finding.

The artifact extends the existing vocabularies by `Require` rather than copying them. [PartitionContext.v](../../../proofs/PartitionContext.v)'s `Rotation`, `Action` and `constants_paid` define and price the intra-slot step. [CyclicExecutive.v](../../../proofs/CyclicExecutive.v)'s `Slot`, `Frame` and `slot_index_at` are the envelope's geometry. [MemoryPlan.v](../../../proofs/MemoryPlan.v)'s `MemClass` indexes the pool extents and its `representable_granule` decides whether a size class narrows exactly.

## What is stated and what is proved

A statement is a definition that a later proof must meet. A proved result is a theorem the artifact proves of that definition, at the contract level only: no kernel, pool service, heap library or toolchain pass is proved against the contract here.

| Statement | Register source | Stated as | Proved here | Consumed by |
| --- | --- | --- | --- | --- |
| The envelope | R-07-037e, R-07-037f, R-08-047a | `Domain`, `Manifest`, `envelope_admits`, `EveryMemberCarriesTheLabel`, `NoMemberIsFixedTier` | an admitted envelope has one label and no fixed-tier member | Q34e composes a domain that `envelope_admits` accepts |
| Launch by activation | R-07-037i | `launch_ok`, `ActivatesOnlyPlaced` | `launch_ok` activates only placed dormant contexts | Q34b's launch, close and focus request cell |
| Confinement of the runtime choices | R-07-037e, R-07-037g, R-07-032 | `Global`, `ReadsOnlyItsLabel`, `MovesNothingOutside` | `select` reads only the domain's own state | Q34b's label-internal unwinding case |
| The dispatch rule | R-07-037g, R-07-027a, R-07-031b | `PcFields`, `DState`, `Decl`, `Selects`, `select`, `reply`, `charge`, `Run`, `RunConforms` | `select` chooses exactly the earliest eligible virtual deadline and idles only when nothing is eligible | Q34b refines `select`, `reply` and `charge` over partition-context fields |
| The boundary rule | R-07-037g, R-11-006c | `boundary_need`, `boundary_ok`, `NeverCuts`, `decl_admits` | a conforming dispatch ends, sink and step included, before the slot boundary; the backstop alone bounds an unchecked sink | Q34b's intra-slot step; Q34e's admission |
| The intra-slot step | R-07-037g, R-07-037d, R-07-014c | `ElasticStep`, `elastic_performs` | a step between applications clears the zeroize class, leaves no residue and costs one `vmclear`; a step inside one application is the rotation | Q34b's inter-application `vmclear` |
| The share bound | R-07-037g | `Stint`, `lag`, `LagBounded`, `ShortfallBounded`, `ShareBound`, `register_lag_bound` | the instant half implies the interval half, so Q34b owes the instant half alone | Q34b's share-bound theorem, blocked on finding F1 |
| The yield-bound obligation | R-07-037h | `Cfg`, `Reaction`, `YieldBoundAdmits`, `invocation_gaps` | the counter protocol keeps every path between invocations within the call bound | Q34d's yield-point pass and cost check |
| The pool service's guarantees | R-08-047b, R-08-006, R-08-007a, R-15-007k | `Arena`, `AllocEvent`, `LiveChunksDisjoint`, `BoundedExactly`, `ZeroedAtHandoff`, `ReusedOnlyAfterTheSweep`, `PoolGuarantees`, `class_exact` | each guarantee's meaning over bytes, bounds and positions, and that an exact grant needs no rounding | Q34c's chunk service refinement and size-class table |
| The heap library's narrowing | R-08-047b, R-15-007k | `HeapNarrows` over a member's chunk as the arena | n/a (stated, with witnesses) | Q34c's heap library refinement |
| Capability confinement | R-08-047c, R-12-007 | `EdgeKind`, `carries`, `edges_confine`, `PoolConfined`, `Transfer`, `Reach` | no sequence of transfers along confining edges puts a pool-derived capability outside the domain | Q34c, and the composition's check of its capability distribution |

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

The artifact also refutes a runtime slot-width choice, which moves an instant another tenant owns; a second label, a device-holding member and a shared extent inside one envelope; a launch that creates a member; a rotation that leaves vector state standing between applications and a kernel that saves it; an unpolled back-edge, which no yield bound admits; a reaction above the declared bound; a miscompiled counter; an allocation outside the size-class table; and a table class whose length or alignment would round.

## Readings

The artifact's header states each reading in full. In summary:

- Virtual time uses exact rational EEVDF arithmetic, the published algorithm's own arithmetic. A fixed-point kernel refines this rule only if Q34b's proof covers the rounding.
- The fixed tie order is the member enumeration order, and every fixed order is some enumeration order.
- A request lasts while the service since the dispatch is below the effective request. The kernel answers at the virtual time that service has reached.
- A run is one dispatch: invocations at most one call bound apart, each answered continue until the last, which is either the member's own real yield or a switch-requested reply followed by the sink.
- Lag is service lag over the competing set. A leaving member accrues nothing, a rebalance places a joining member at the eligible time its preserved lag fixes, and a leave moves no other member's accounting.
- The share bound's time base is a parameter, `ServedTime` or `SlotTime`.
- The zeroize class is PartitionContext.v's zeroized CSR class, and a poll site on a back-edge sits at the edge's target.
- The pool guarantees are stated over an observable history of grants, releases, stores, zeroing, barrier completions and sweep passes.

## Findings

Each finding is a register question the owner decides. The artifact exhibits the first three as computed facts and states the fourth as the reading it takes. Where a reading is needed to state the rule at all, the artifact names it as a reading, and `charge` and `rebalance` change with the register's answer to F3.

- **F1. The lag bound omits the sink.** R-07-037g's second acceptance bounds every live member's lag by the largest declared request plus one call bound. After its last continue, a conforming member runs up to one call bound to its next invocation and then up to one yield bound for its sink, which the boundary rule itself budgets. `the_register_s_lag_bound_is_refuted` exhibits a two-member trace in which every step is the rule's. Both members end with a lag of magnitude 22/5 against a bound of 4, so at that declaration `ShareBound` at the register's bound is false and not a theorem Q34b can prove. The same trace stays inside the request plus a call bound plus a yield bound (`sink_inclusive_lag_bound`), which is named and not adopted.
- **F2. The share bound's time base is unstated.** Read over the domain's slot time, the idle tail the boundary rule leaves accrues shortfall in every slot. `the_slot_time_reading_is_refuted` exhibits a single member at lag 8 against a bound of 4 after two slots. Read over served time, the bound holds of that trace, and it cannot see the idling F3 exhibits.
- **F3. Whose lag the published leave and join rules preserve is unstated.** Taken literally, a member leaving with positive lag moves no other member's accounting. `the_literal_leave_rule_is_not_work_conserving` exhibits a member with work pending that never becomes eligible again: the core idles slot after slot while that member's served-time lag stays inside the register's bound. The specification's prose under R-07-037g, that an idle application costs its siblings nothing, fails there. The published remedy adjusts virtual time at a leave, which separates every other member's accounting lag from its service lag, so the choice also decides what the share bound quantifies.
- **F4. Which members are live for the share bound is unstated.** A launched member with nothing pending would accrue entitlement it never uses, which no dispatch can bound. The artifact reads the share bound over the competing set, live members with work pending.

## What each successor consumes

- **Q34b** refines `select`, `reply`, `charge` and `ElasticStep` over PartitionContext.v's contexts and the fields R-07-027a places. It adds the request cell and the label-internal unwinding case, then proves `LagBounded` at the bound the register settles. Until F1 through F4 are settled, the register's own bound is refuted and the kernel's leave accounting is open.
- **Q34c** refines `PoolGuarantees` for the chunk service and `HeapNarrows` for the default heap library. It discharges `class_exact` with the composition's size-class table, states per-island pools and the quarantine's shape, and runs the generated campaigns its Check names over allocation, release and reuse histories of the kind `good_history` shows.
- **Q34d** produces the control-flow graphs and counters `YieldBoundAdmits` and `invocation_gaps` read, and adds the per-function cost triple for a reaction crossing a call.
- **Q34e** composes a domain that `envelope_admits` and `decl_admits` accept, and measures what admission leaves unbounded.

## Evidence and its limits

The lane compiled the artifact with the pinned prover against staged copies of its dependencies. The proof gate's per-source audit reported every native constant closed under the global context, every discharge annotation bound to one compiled declaration, and every quantified record witnessed. `rocqchk` accepted the module with its dependency closure. The integrated `python tools/run.py proofs` receipt supplies the corpus evidence. Nothing here executes, and no witness value is a composition claim. Row 31 moves to `authored` only after independent review under R-05-150, for which the findings above are inputs.
