# Storage recovery policy decision

This is M5.3's decision input and contract for its policy-independent recovery work. It recommends a discipline and does not select it. The [register](../requirements-register.md), [JournalIndex.v](../../proofs/JournalIndex.v), [block-device contract](../../interfaces/block-device-contract.md), and [Q22f comparison](storage-index-comparison.md) retain their existing authority. M5.3's target execution and M5.4's policy-dependent transactor behavior remain open.

## The observable choice

JournalIndex.v's header states: "The recovery discipline is a parameter and not a choice made here." Its `scan` stops at the first record for which `intact` is false. Its `sieve` discards that record and continues. `recover_under` computes the committed transaction set from the selected records and replays those records in order; `spec_recover` instantiates `scan`, and `sieve_recover` instantiates `sieve`. The word `spec` in the first name does not confer a register decision.

Both satisfy `AdmitsOnlyIntactRecords`, `IsIdempotent`, `LeavesUntouchedBlocks`, `LandsEveryCommittedWrite`, `ReadsOnlyWhatTheDisciplineAdmits`, and `ReplayIsIdempotent`. The first two concern the record filter; the next four concern replay under that filter. None establishes that the selected records contain every payload of an originally acknowledged transaction.

The source's `what_each_recovery_reading_reaches` evaluates the same `tear_at 2 0 demo_journal` and initial store. In block-index order, stopping reaches `[0; 11; 12; 3; 4; 5]`; skipping reaches `[0; 22; 12; 3; 4; 5]`. Block 1 therefore changes observably. This is not two representations of one recovered store. The stop arm's selected log is `take 2 demo_journal`; the skip arm retains the intact suffix, including a closing record whose earlier payload may be missing.

The policy-independent companion `proofs/StorageRecovery.v` reuses these definitions and examples rather than defining another journal. Its agreement theorem covers an entirely intact log. Its refinement theorem states when two filters select the same records and therefore replay to the same store. Neither theorem equates the disagreeing torn-log stores.

## Costs and forfeits

Let `L` be the composition's bounded record count and `P` the bound on changed node images per transaction. These are parameters, not a selected layout or measured capacity.

| Question | Stop at first invalid record | Skip invalid records |
| --- | --- | --- |
| Scan work | Inspects at most `L` records and may stop earlier | Inspects every declared record before deciding what can be recovered |
| Successful replay bound | Bounded by the admitted prefix and its committed writes | Bounded by all surviving records and their committed writes; suffix salvage receives no extra unbounded budget |
| Unprotected missing payload | Can lose a later closing record and mistake damaged committed work for uncommitted work | Can retain a closing record after losing a payload and apply a partial transaction |
| Journal size | Requires the bounded redo images, transaction manifest and commit evidence | Requires the same complete transaction evidence; safe salvage may additionally need independent authenticated record framing/indexing |
| Write amplification | Inherits Q22f's full-block redo, home-copy and checkpoint-publication accounting only if its complete transaction protocol is also selected | Gets no endurance discount for skipping; authentication, repair or salvage writes must be charged separately |
| Worst-case execution time | Needs target coefficients for record parsing, authentication, block service and bounded replay | Needs the same coefficients plus the complete scan; neither a Python operation count nor early stopping is a WCET certificate |
| Failure tradeoff | Refuses or abandons an unauthenticated suffix; simple sequential framing | Can recover independently complete later transactions only after proving they are complete and eligible; raw `sieve` does not prove that |

The replay choice acts at L0. L1 must publish only a complete authenticated CoW root and preserve retained roots under either arm. L2's object, metadata and secondary-index effects stay in the same transaction, and post-commit notifications must follow that transaction's validated publication. L3's domain authentication and `Fresh` epoch acknowledgement remain separate: a recovered mutable-volume root does not become rollback-fresh, and no recovery arm authorizes cross-domain deduplication or bypasses the sealed epoch. [KeyspaceDomains.v](../../proofs/KeyspaceDomains.v) owns those statements.

Q22f's measured redo experiment uses an authenticated commit that binds payload count, order, addresses and content identities; durable acknowledgement follows checkpoint publication, and a complete commit with a bad payload refuses recovery. That is stronger than bare `scan` or `sieve`. Its write, barrier and reservation formulas remain owned by the [comparison's shared contract](storage-index-comparison.md#shared-journal-recovery-and-integrity-contract); copying its preferred scan into an implementation without its commit and acknowledgement contract cannot inherit its measurements.

## Recommendation and decision criteria

Recommend bounded prefix redo with authenticated complete-transaction manifests, checkpoint-before-acknowledgement ordering and explicit refusal when a known committed transaction cannot be reconstructed. This preserves Q22f's comparison contract and avoids making independent suffix salvage a new protocol. It does not claim raw `scan` alone satisfies durable acknowledgement preservation.

The decision must settle record framing and authentication, commit representation and binding, acknowledgement ordering, journal reuse, the durable evidence that distinguishes an incomplete uncommitted suffix from corruption of acknowledged work, the refusal/recovery escalation, and the finite resource bounds. It must preserve R-10-036's multi-object atomicity and R-16-005's committed-work guarantee under the selected fault class. A measured whole-system configuration, not this recommendation, supplies service and crypto costs. The alternative is separately qualified complete-transaction salvage, never unqualified skipping.

The block-device contract remains unchanged. It permits non-prefix bit tears, misdirected reads and arbitrary recorded corruption. `rec_landed = rec_len` is a symbolic predicate and cannot decode or authenticate those bytes. A decoder/verifier and transaction-completeness bridge must be reviewed before any device trace is presented as one of JournalIndex.v's record traces. Missing, invalid or over-limit evidence is a refusal, not an invented intact record.

## Acceptance fixed before companion authoring

This decision document passes when it names both existing arms and their computed store difference; separates their shared obligations from full-transaction completeness; accounts for L0 through L3 and Q22f's conditional costs; states a recommendation and exact proposed register text; and identifies every producer the final crash predicate needs. It does not pass by marking M5.3 complete or choosing an arm in source code.

The policy-independent companion passes a focused Rocq compilation, native assumption/type audit and kernel recheck; carries constructed accepted and rejected instances; reuses JournalIndex.v's `Rec`, `Discipline`, `Store` and `recover_under`; proves intact-input and equal-selection agreement, bounds recovery output to selected records, and exhibits the torn-log disagreement. It must also distinguish symbolic record completeness from byte authentication and reject a closing record whose required payload is absent. These checks apply before any policy-dependent lowering starts.

The writable crash-half predicate feeds one recorded device-produced image through a separately qualified bytes-to-record decoder, runs both admitted filters over identical decoded inputs, and reports their observable stores separately. Decoder or authentication refusal returns no reconstructed store. It records image identity, fault trace, decoder identity, selected policy and final root identity. Policy-independent properties are preservation of untouched blocks, replay of every selected committed write, idempotent replay, complete required payload before publication, and retained-root integrity.

The final success predicate cannot yet name one normative post-crash store. It requires the register's recovery/acknowledgement decision, the persistent host-image adapter and reopen boundary, the bytes-to-record/authentication bridge, M5.3's real storage/crypto execution and one-index-body evidence, and M3.5's boot/counter join. A run of `python tools/run.py model corpus` must then show the policy-selected root after each declared crash cut, corruption refusal before returned object bytes, and no acknowledged partial transaction. `python tools/run.py storage-index --json` and `python tools/run.py test --only storage_index` exercise Q22f's bounded experiment; they do not supply those missing producers.

## proposedIntegratorEdits

Proposed new entry immediately after R-10-002, with the final ID assigned in prose order by the integrator:

> **R-10-002a** MUST: L0 recovery uses a bounded prefix redo journal whose independently authenticated commit evidence binds the complete ordered payload, target addresses and content identities of each transaction. An incomplete uncommitted suffix is not published. A transaction known to have committed whose required payload does not authenticate is refused rather than replayed partially or silently treated as uncommitted.
> · Accept: every accepted transaction contains its complete bound payload; a missing, torn, reordered, duplicated or misdirected payload is rejected; replay is idempotent; current and retained roots remain authenticated; acknowledgement follows durable publication of the complete checkpoint, and journal reuse follows that same boundary. Recovery over the declared fault cases preserves acknowledged work or enters the declared refusal path, never returns a partially updated object/metadata/index transaction. The bounded scan, redo, retained-root and recovery resources are declared before admission and satisfy the composition's measured worst-case budget.
> · Fail-closed: missing evidence needed to distinguish uncommitted work from corruption of an acknowledged transaction stops recovery of that affected store; it does not lower the anti-rollback floor, erase other stores or authorize unverified object reads.

This is proposed decision text, not an amendment made by this document. Its matching specification prose, trace targets, affected coverage and co-read review belong to the integrator's register act. Until that act, both arms remain explicit inputs to the companion and the transactor.
