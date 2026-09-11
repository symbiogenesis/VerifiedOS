# Revocation completion and reuse qualification

The bounded host model in [revocation.py](../../tools/vos/revocation.py) qualifies
the interface [Q22a](../implementation/implementation-checklist.md) supplies to
M4.4 and R2. Bitmap publication prevents a stale capability from becoming usable
on a filtered reload. Completion additionally removes resident and borrowed
authority and establishes the proxy and device barrier. Reuse additionally
requires a full pass started after that barrier which destroys every remaining
stale representation. These are separate events and separate bounds under
R-08-005, R-08-006 and R-08-007a of the
[requirements register](../requirements-register.md).

The assessment accepts this interface for the bounded experiment. It does not
establish a runtime implementation, a Sail refinement, a composition-admission
proof or a universal temporal-safety theorem. In particular, a successful host
run does not provide the physical completion evidence of an unresponsive peer.

## Actual source paths

This is a reviewed inventory of the relevant paths, not a generated call graph.
`python tools/run.py revocation --json` emits the current SHA-256 identities of
the sources below alongside its results. The identities make a run attributable;
they do not automatically requalify an altered source's meaning.

| Path | What the source decides | Barrier consequence |
| --- | --- | --- |
| [cheri_mem.sail](../../model/model/extensions/CHERI/cheri_mem.sail), `cap_load`, `revocation_filter` | The loaded capability's base selects the bit, and a set bit clears the returned tag. `cap_access_checks` checks the authorizing capability's tag, seal, permissions and bounds. | The loaded value is filtered; a resident authorizer is not reloaded by performing a dereference. |
| [cheri_insts.sail](../../model/model/extensions/CHERI/cheri_insts.sail), `LoadCapImm`; [cheri_custom.sail](../../model/model/extensions/CHERI/cheri_custom.sail), `CIndexedLoad` | Both instruction forms call `cap_load`. Stores retain the supplied capability tag through `cap_store`. | Saving a stale capability does not destroy it; a filtered restore prevents use while its bit stays set. |
| [addr_checks.sail](../../model/model/core/addr_checks.sail), `cap_data_checks`, `cap_mode_auth` | Scalar data accesses use the resident capability and apply its architectural checks without reading a revocation bit. | A bitmap mark alone leaves a live register usable. |
| [cheri_insts.sail](../../model/model/extensions/CHERI/cheri_insts.sail), `CMove`, `conditional_cap_move`, `narrow_bounds`, `CSetBounds`, `CSetBoundsImmediate` | Moves preserve capability state; narrowing can change the base while retaining a tag. | The retirement set covers every admitted derived base, or a separate proof excludes its post-barrier use. Marking only an object's initial base is insufficient. |
| [cap_regs.sail](../../model/model/core/cap_regs.sail); `CJALR`, `CSpecialRW` in [cheri_insts.sail](../../model/model/extensions/CHERI/cheri_insts.sail) | PCC, MTCC and MEPCC carry capabilities outside the ordinary merged-register view; transfer and special-register operations do not load-filter them. | The composition's live-root inventory includes executable and sentry roots, not only general registers. |
| [base_insts.sail](../../model/model/extensions/I/base_insts.sail), `MRET`; [sys_exceptions.sail](../../model/model/exceptions/sys_exceptions.sail), `prepare_xret_target` | Return takes MEPCC into `nextPCC`, unsealing a sentry when applicable. There is no revocation-filter call on that path. | A saved return root cannot evade the barrier by moving through a CSR. |
| [cheri_custom.sail](../../model/model/extensions/CHERI/cheri_custom.sail), `CClear` | The selected merged registers become untagged NULL. | This supplies a local clearing operation, not an implementation of the complete root inventory or protocol. |
| [cheri_insts.sail](../../model/model/extensions/CHERI/cheri_insts.sail), `CLoadTags`, `CReclaim` | The former reports stored tags; the latter conditionally clears revoked capability tags in a bounded group. | Reading tags is not reclamation. A sweep owns software progression and only completed groups advance its cursor. |
| [revocation.sail](../../model/model/core/revocation.sail), `revocation_covered`, `revocation_index`, `revocation_revoked`, `revocation_write_word` | The current model has one configured covered interval and a finite bitmap. Bases outside it are live. Epoch, loan and sweep protocol state is absent from this file. | The host experiment's island copies are a protocol abstraction, not evidence that this Sail instance implements the distributed barrier. |
| [PartitionContext.v](../../proofs/PartitionContext.v) | The context relation requires complete value/tag restoration and separately specifies zeroized state. It carries no revocation state. | Total restore alone cannot prove temporal safety. M4.4 must relate a sanitized saved image or the defined filtered load result to that relation. |

The capability instruction paths contain no grant-table invocation validator or
outstanding-loan protocol. The host model's loan cancellation and acknowledgement
operations therefore specify interfaces for M4.4/R2; they are not translations of
existing Sail runtime paths. Device completion is similarly an abstract event
whose R-15-208a ownership postcondition must be established by the RTL consumer.

## Finite state and admission premises

A holder names a live root, a saved context, or a capability-bearing memory
location. Its location may be outside the revocation-covered interval: the load
filter is keyed by the capability's base, not by where its representation sits.
The holder map includes trusted-stack roots, MEPCC, grant storage, a remote
register and proxy slot, loan copies, and an unrelated grant to the same object
as a borrowed capability. The generated fixtures vary the retired object's
granule width and include a representation at each interior granule base.

The finite fixture has one core per island. A capability's `island` annotation
names its address region, not a capability field. Loads take the loading island
explicitly: a foreign base remains live even when its owner's bit is set. The
composition validator rejects a holder whose authority points to another island;
cross-island revocable delegation is represented by a local proxy capability.
Multiple cores in one island and immutable shared windows need a richer address
map and remain outside this fixture's admitted shapes.

The model forgets permissions and seals when asking whether a nonempty tagged
capability could authorize an access. This is conservative at that observation:
it cannot pass a dangerous tagged root by assuming that a seal or permission
blocks it. `retired` is an observer annotation and `loan` identifies the complete
admission-proved borrowed footprint. Neither is an architectural field, generation,
colour, runtime token or load/dereference check.

The finite map and derivable-base closure are premises about TAL-admitted code.
The experiment detects missing and duplicate holders relative to the supplied
map, incomplete sweep coverage, retained narrowed bases and raw saved restores.
It does not discover roots or arbitrary derivations in a binary. In production,
admission must establish that every capability or trusted minting root capable
of recreating retired authority is represented or cannot do so. For object
retirement this includes every admitted base reachable by narrowing. For a
grant-slot retirement, publication blocks invocation of the slot and loan
cancellation clears the borrowed footprint; revoking the slot bit does not
revoke the shared underlying object.

Loan cancellation clears the complete footprint supplied by the no-capture
premise, including a saved borrowed copy. It waits for no untrusted return. The
runtime may instead use a bounded return whose same postcondition is established,
but an unbounded call or unaccounted captured copy rejects admission. The host
model does not prove the no-capture premise. M4.4 must obtain it from the admitted
call convention and TAL ownership proof, not from the ghost annotation.

## Completion and reuse predicates

Publication marks the supplied affected bases, closes new invocations and
advances the monotone epoch. Core cleanup clears the complete live root set on
that core; saved roots remain inaccessible only through mandatory filtered
restore. The completion predicate requires the complete map, all marks, closed
invocation, no usable retired root after direct access or restore/load, no
outstanding loan, each static proxy's acknowledgement and the device completion
boundary. The proxy operation itself refuses to acknowledge a retained local
root, outstanding call or incomplete device boundary.

The modeled remote topology is a rooted star with one proxy per non-root core.
A runtime with a different finite static graph needs R2's bounded traversal and
per-edge ledger; this experiment supplies no general graph theorem. A deadline
expires into an explicit failed attempt, retaining its bitmap marks and
quarantine. Even a late acknowledgement after all cleanup cannot turn that
attempt into successful completion. This is a bounded refusal decision. The
sentinel's physical escalation when a peer cannot supply evidence remains with
the runtime owners; expiry by itself cannot establish containment.

A sweep used for reuse starts strictly after the successful barrier. Every
mapped saved or memory location must participate. Reuse checks raw tags in
addition to today's filtered accessibility: a stale tag protected only by a set
bit would become usable again when that bit clears. A stale saved copy, a copy
outside the covered interval, and a write behind an already visited cursor all
refuse reuse. A pass begun before the barrier refuses even when its cursor claims
full coverage. No live root or loan can repopulate swept storage under the
admitted-code premise; the raw-tag check makes a violation observable in the
bounded state. Quarantine ends only when clearing the affected bits cannot
resurrect any old authority. Epoch exhaustion refuses publication without wrap.

## Schedule bound

The host budget is an illustrative admitted-service ledger, separate from the
logical event-order enumeration. Its units are arbitrary schedule ticks, not
measured chip cycles. Each job supplies period `P`, slot width `W` and complete
work `C`, with `0 < C <= W <= P`. One release is conservatively bounded by
`P + C`. The work includes the finite holder or bitmap footprint assigned to the
job and its dispatch costs. `Budget.bounds` requires the initial composition and
checks one publication job per affected island, one barrier job per core, one
cancellation per named loan, notification plus acknowledgement for each proxy,
the modeled device window's job, and the full sweep-holder count. Missing service
cannot publish a smaller bound. Tuple positions follow each sorted inventory.
A production ledger must be emitted from the admitted composition and charge
shared jobs once; these host values are not that emitter.

Bitmap-mark time is the sum of publication-job bounds across the involved
islands. Semantic-completion time adds the core cleanup, forced loan cancellation,
static-edge notification and acknowledgement, and device jobs. The serial sum
remains a conservative upper bound when independent jobs overlap. Each device
job uses the R-15-208 schedule rotation and granted width: publication plus one
rotation and one granted slot is the device term. Notification and acknowledgement
are separate jobs, so a returned message is not assumed to fit before local
cleanup. All jobs have fixed admitted service; none waits on a principal.

The same finite schedule gives the latest acknowledgement-failure decision.
Successful completion and reuse remain conditional on the required evidence;
there is no finite successful-reclamation bound for a failed peer in this model.

For sweep period `F`, slot width `Q`, complete-group cost `G` and mapped group
count `N`, reserve one lost group per cut. Guaranteed progress per frame is
`q = floor(Q/G) - 1`; `q <= 0` refuses the schedule. A conservative full-pass bound
is `ceil(N/q) * F + Q`, including the first-release wait and final slot. The
fixture charges each mapped storage holder as a separate group, deliberately
taking no packing credit. Set-to-reuse time adds this post-barrier bound to
semantic completion. Changing only the sweep footprint cannot change containment
time. No sweep quantum is charged to a partition switch by this assessment.

## Executable evidence and downstream work

Run `python tools/run.py revocation --json` for deterministic evidence and
`python tools/run.py test --only revocation` for the behavioral tests. The command
enumerates all orders of the finite fixture's independent cleanup operations,
retains refused early acknowledgements as pending, and checks successful reuse
after a permitted acknowledgement. Generated corruptions exercise resident and
special-register retention, unfiltered saved restore, narrowed-base omission,
callee-loan retention, remote acknowledgement/authority, in-flight transfers,
and reuse resurrection. Positive cases also retain the unrelated grant.

The behavioral tests establish telling witnesses separately: a resident
capability still dereferences after marking; a narrowed base survives an
original-base-only mark; a loan survives its slot's bit; and removing marks from
a stale saved copy actually restores usability. This guards against a test that
rejects a label whose alleged authority never existed. Results and source
identities live in command output; measured counts belong in Q22a's completion
note. There is no production timing credit.

M4.4 owns the single-hart implementation and its connection to the actual load,
dereference, special-register and context-restore semantics. Entry must price
the holder/base-map admission connection, sanitized restore, bounded loan
cancellation and invocation check, explicit failure escalation, and targeted
Sail/runtime oracle evidence before any stronger claim lands. R2 owns the
multi-hart/proxy implementation, bounded graph protocol and device completion
join, including acknowledgement failure. The later kernel refinement and
temporal-safety proof retain their obligations. This cell qualifies their
interface; it does not absorb those implementations or proofs into its estimate.
