# Finite workflow lifecycle and admission contract

[WorkflowProfiles.v](../../../proofs/WorkflowProfiles.v) is Q32a's executable Gallina
qualification of the [workflow design](../workflow-profiles.md), under R-08-015a,
R-11-018, R-11-018a, R-14-011a and R-14-011b in the
[requirements register](../../requirements-register.md). It supplies a bounded
source model and consumer interfaces. Q32b owns the actual kernel, storage and
schedule pilot; Q32c owns instantiated recipes and capacity measurements.

## Model boundary

The finite pilot has an editor and an image app, one composition-fixed private
arena, immutable admitted code, a permanent service reservation and a bounded
manager record. The app names denote abstract document state, not application
ports. Each app independently records its arena claim, so simultaneous claims
are representable invalid inputs. `exclusive` rejects that overlap. The model
has no runtime placement, executable payload, growing arena or grant mint in a
profile request. All natural-number state fields have explicit certificate
bounds; the other state components have finite constructors. An admitted
certificate therefore determines a finite state space.

The pilot fixes one power setting and population rung and enumerates its local
profile edges directly. The certificate distinguishes local setting equality
from an explicitly authorized, root-attested global change. It supplies no
multi-power or factored-composition theorem. Generalizing the app roster,
physical arena set, bank interference or selectable powers requires a new
composition and its owner-provided placement and scheduling proofs. The
`fixed_binding` premise connects the pilot's constant arena to exact physical
extent, bounds representability, alignment, memory class and bank/island in that
composition; the Boolean does not prove these physical facts.

`Phase` distinguishes active, background, frozen, quiescing, retiring,
hibernated, restoring and closed. Frozen and background state retains its arena
charge. Hibernated and closed state has no private arena claim or live grant.
Background here describes the private app instance; continuing communication
and product-floor work belongs to the permanent reservation, which no event
removes. A production app with an independently running background component
must include that component in this reservation or enlarge the model.

## Certificate and charged transitions

`Edge` is the composition interface. It carries availability, request authority
and observation policy, local/global setting constraints, fixed binding,
protected-state and bounded-operation guards, RAM, storage and endurance
limits, cross-boundary service gaps, each stage's work, the overall work budget
and deadline, serialization capacity, dwell, and reserved recovery.

`edge_ok` reserves the entire pilot's transition peak before `Request` can
quiesce anything. `complete_transition_peak_fits` proves that every exclusive,
phase-consistent intermediate state fits that admitted RAM and storage
reservation, including retirement quarantine, restore scratch and recovery.
The permanent reservation and metadata always count. An occupied arena remains
charged through quarantine. Each durable checkpoint and the separate commit
scratch count in storage. The immutable checkpoint size and arena size are
abstract units in this finite pilot; they are not measured application bytes.

The RAM/store postcondition in `step` is an additional fail-closed check,
not the only reason the complete edge fits. Endpoint-only RAM and storage
certificates are rejected by `edge_ok` before teardown. Work admission requires
the minimum costs of carry-in, checkpoint, retirement, sanitization, restore
and recovery and charges those same fields in `propose`. Recovery reserves a
complete failure retirement, including cleanup. `admitted_stage_costs_are_reserved`
connects the component sum to the completion deadline.

`continuing_service_bound` includes the old schedule's last-service gap, the
maximum service gap inside the edge and the new schedule's first-service gap.
Those gaps require a real schedule producer. They are neither endpoint
schedulability flags nor a physical latency claim. Event dispatch and completion
must honor their certified service bounds; withholding an event indefinitely
is outside the timing premise. Crash resets the recovery attempt's accounting
under the boot contract and does not promise uninterrupted service while power
is absent.

Requests are serialized in `target`; a second request receives immediate
bounded refusal. The model retains no unbounded pending queue. The dwell
counter saturates at its declared bound. Endurance is a monotonically consumed
generation budget, reserved before a new request, and never wraps or resets
when a profile changes. Exhaustion refuses a new switch rather than borrowing
resources or indefinitely queuing the request.

## Checkpoint, reuse and recovery

`Checkpoint` contains semantic document data and binding metadata. The format
tag admits semantic data and rejects raw heaps, executable content and session
keys. App identity, schema, generation compatibility, confidentiality label,
authentication, durable commit and the declared Fresh class are separate
checks. Ordinary data keeps the storage design's rollback residual. A real
decoder must enforce the semantic format; a claimed format tag is not a proof
about bytes.

`Commit` additionally requires the checkpoint data to equal the app's declared
document state. `commit_preserves_declared_document` proves that relation.
`failed_commit_preserves_acknowledged_data` and
`crash_preserves_acknowledged_data` preserve the previously committed checkpoint.
A failed commit resumes the old live app. Protected or unbounded operations
refuse the edge before that app is stopped.

`Release` requires a successful commit in this retirement attempt and the full
`Roots` receipt. It is the successful hibernation event. The receipt names the
complete holder inventory and derivable bases, closed ingress, live register
and raw saved-state cleanup, minting roots, loans, proxy acknowledgement,
devices, barrier completion, a sweep begun after that barrier, complete sweep
coverage, and data/tag sanitization. These are the
[Q22a reuse interface](../../assurance/revocation-qualification.md), not independent
shortcuts around it. Neither elapsed time nor a set bitmap can construct the
required physical receipt.

`root_correspondence` relates the register, raw saved, ordinary memory, mint,
loan, proxy and device receipt fields to an explicit machine inventory. Ordinary
memory includes capability-bearing locations outside the revoked interval; its
clearance premise requires both the full sweep and data/tag sanitization. The
source constructs a nonempty cleared inventory and a stale-memory counterexample.
The closure premise of
`no_authority_resurrection_under_machine_premise` requires every possible old
authority, including any future reconstruction, to originate in that inventory.
Together with the complete receipt, the theorem excludes resurrection. The
consumer must establish inventory completeness, derivation closure and the
absence of post-barrier writers; the finite proof does not discover these from
a binary. Narrowed capabilities, asynchronous completions and minting roots
cannot be omitted from this premise.

Restore reserves the arena, revalidates the checkpoint, and uses the adapter's
current grant decision. `restore_uses_current_grant` proves that an old session
is never reinstated and that the document grant equals this current decision.
The restored data is the checkpoint document; reconnect behavior is explicitly
no retained session. Production validation must connect this document equality
to the app's declared resume semantics and external effects.

A crash or restore failure marks any occupied arena retiring without claiming
successful checkpointing. `Recover` finds the actual arena owner, requires the
complete reuse receipt and reaches the reserved closed/default state while
retaining durable records and standing services. It cannot substitute for
successful `Release`. A subsequent admitted edge can reconstruct the durable
document; it does not instantly recover lost volatile state. The corpus
exercises a crash before and after every normal switch event, including the
interval when the destination owns the arena while the selected profile still
names the previous app.

## Consumer review and acceptance

| Consumer | Accepted source interface | Required implementation evidence |
| --- | --- | --- |
| Kernel and Q22a/M4.4/R2 | `Roots`, `root_correspondence`, closure premise, arena claim and recovery events | Complete real holder/base inventory, stopped ingress, no-capture and minting-root argument, bounded device/proxy completion, post-barrier sweep and sanitization, and exact fixed binding |
| Storage and Q32b | `Checkpoint`, `cp_ok`, exact document equality, acknowledged-data preservation | Authenticated semantic decoder, durable atomic commit/recovery and Fresh-class policy on actual bytes, bounded space/endurance and app resume relation |
| Scheduler/composer and Q32b | `Edge`, whole-transition peak, component work, service chain, dwell and request refusal | Actual stage WCET and service offsets, continuing product-floor reservation, global-setting/attestation join where used, and failure dispatch within the declared bound |
| All consumers | `ImplementationTrace` and `consumer_refinement_preserves_admitted_invariants` | A forward simulation for every actual accepted event; constructing abstract event receipts supplies no simulation proof |

The integrator's source review accepts these interfaces at the finite pilot
boundary. No new probability theory, third-party source or assumed global axiom
is needed. The production checker and application/kernel/storage/scheduler
simulation remain Q32b and its named existing runtime owners; this source does
not claim those implementations or generalize their budgets.

The source's `generated_reachable` enumerates accepted event words, and
`refuted_neighbors` generates rejected one-event extensions. Both are computed
by the same Gallina operational semantics used by the proofs. The named
qualification examples independently fix expected outcomes for conflicting
ownership, every missing reuse clause, invalid checkpoint fields, lost unsaved
data, endpoint-safe transition overload, cross-boundary service gaps, underpriced
work, failed commits/restores, every crash boundary, grant revocation and repeated
switches through endurance exhaustion. The generated corpus size is a computed
run result, not a maintained document count.

Replay uses Guest CI's proof gate on GitHub Actions, including native
symbol/assumption audit and kernel recheck. Local reproduction for focused
debugging or a CI outage uses an isolated worktree. Bounded mutation
qualification uses `vos.seeded.chosen` to select 24 mutants over `edge_ok`,
`propose`, `reusable`, `cp_ok`, `ram` and `store`, plus targeted memory-inventory
omissions. Compile each mutant's definitions independently in the native proof
environment before checking its proofs: definition failures are stillborn,
not killed, and survivors need individual investigation. The completion evidence
identifies the actual prover and replay helper; the separate `seed coq` vector
harness is not interchangeable evidence. The integrator owns requirement-header
generation, the portable receipt and the final Host CI and Guest CI verdicts
after integration.
