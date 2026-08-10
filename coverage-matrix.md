# The Coverage Matrix

*Normative as a **view**. This document is the artifact **R-17-001b** mandates and **R-17-001a** quantifies over: the enumerated boundaries of the system, the properties each must hold, and one row per pair of them recording the construction that carries it, its discharge mode, and the requirements it rests on. It is **derived from** [requirements-register.md](requirements-register.md), which remains the audited artifact per R-05-152.*

> **Precedence.** Where this document and the register disagree, **the register wins and this document is defective.** Every row cites the requirements that govern it. This document adds no obligation of its own.

## Why this document exists

R-17-001a claims coverage top down rather than by enumerated attack archetype: every boundary against every property, discharged by a requirement or booked as a residual. That claim is only decidable against an artifact holding the two enumerations, because a pair nobody wrote down is a pair nobody can find missing. This document is that artifact, and the enumerations live here rather than in the prose that quantifies over them, for the same reason crown-jewel membership does under R-17-016: a set restated in two places is a set free to stop being the set.

The two enumerations below are nine boundaries and seven properties, and the matrix carries all sixty-three of their pairs.

The point of the shape is what it makes mechanical. `tools/check.ps1` decides that both enumerations are stated once, that every pair appears exactly once, and that no cell rests on nothing. An uncovered boundary is therefore a failing check rather than a critique somebody had to write, which is the whole difference between a coverage argument and a long list.

## 1. The boundaries

A boundary is a place where something crosses between parties that do not fully trust each other. Each is already named across the specification; this table fixes the set and the identifier, and nothing else in the repository restates it.

| Id | Boundary | Where the specification names it |
| --- | --- | --- |
| `B-01` | The instruction set and its microarchitectural absences | §15 |
| `B-02` | Binary admission | §5, §13 |
| `B-03` | The inter-process interface | §12 |
| `B-04` | The device edge | §12, §15 |
| `B-05` | Storage at rest | §10 |
| `B-06` | The radio and network wire | §12 |
| `B-07` | The human consent path | §6, §8, §12 |
| `B-08` | Time and freshness | §9, §11 |
| `B-09` | The supply chain from source through binary to mask | §13, §17, §18 |

## 2. The properties

A property is what a boundary must hold, stated as a property and never as an attack, so that a cell can be completed rather than merely lengthened.

| Id | Property | What it asserts of a boundary |
| --- | --- | --- |
| `P-1` | Confidentiality | Nothing crosses that the policy does not permit to cross |
| `P-2` | Integrity | Nothing crosses altered without detection |
| `P-3` | Authority | Nothing crosses carrying more authority than was granted |
| `P-4` | Freshness | Nothing crosses that is a replay of a superseded state |
| `P-5` | Availability and progress | The boundary cannot be made to stop, or to block without bound |
| `P-6` | Timing and leakage | What is observable at the boundary does not vary with a secret |
| `P-7` | Identity and uniqueness | What crosses is named unambiguously, and by exactly one name |

## 3. The matrix

Each row records the construction in this design's own mechanisms, its discharge mode, and the requirements that carry it. The modes are the inventory's: **absent** where the class has no vehicle to exist in, **hardware-enforced** where matter decides it, **admission-rejected** where a gate refuses what would violate it, **proved** where a machine-checked theorem carries it, **detected** where the fault is not prevented but cannot pass silently and its consequence is bounded, **transferred** where the obligation is real and is met by a named party other than the platform, and **residual** where §17 books the remainder rather than a construction closing it.

| Boundary | Property | Construction | Mode | Requirements |
| --- | --- | --- | --- | --- |
| `B-01` | `P-1` | No speculative, out-of-order, or predictor state exists to carry history across a domain; islands are confidentiality domains and `fence.t` clears what is time-shared | absent | R-15-100, R-15-211, R-15-222 |
| `B-01` | `P-2` | Every SRAM array is ECC-protected and corrected, the validity tag bits take the stronger code, and no sub-granule write reaches the array; interleaving and scrubbing keep a latent error from accumulating and an uncorrectable one is a fail-stop rather than a returned value | detected | R-15-175, R-15-177, R-15-178, R-15-181 |
| `B-01` | `P-3` | CHERI is the sole spatial mechanism, privilege is a permission on the program-counter capability, and domain entry is a sealed capability jump; the debug module, the one master that would sit outside that model, is fused absent in production under a lifecycle that never re-enters a state it has left | hardware-enforced | R-07-018, R-09-033, R-15-068, R-15-073, R-15-078 |
| `B-01` | `P-4` | Neither memory encryption nor an anti-replay tree is on the die, the off-die surface they answer being absent and the tags never leaving it | absent | R-15-199, R-15-203, R-15-204 |
| `B-01` | `P-5` | Divide, vector floating point, and atomics complete at a fixed worst-case latency, and the partition fence completes at a padded constant rather than early | hardware-enforced | R-15-080, R-15-081, R-15-087, R-15-218 |
| `B-01` | `P-6` | `Zkt` and `Zvkt` are the architectural data-independent-timing contract, and bare self-exclusion from that list is not a pass | hardware-enforced | R-15-011, R-15-053, R-15-085 |
| `B-01` | `P-7` | Exactly one Sail model and one capability encoding exist, and a second entropy root is refused rather than reconciled | admission-rejected | R-15-005, R-15-037, R-15-241 |
| `B-02` | `P-1` | Any binary receiving secret-labeled material carries the binary-level constant-time obligation, and secret taint is a type-level attribute the checker decides | proved | R-05-062, R-05-069, R-13-020 |
| `B-02` | `P-2` | Admission binds the installed bytes to their exact content-addressed source closure, and the pack is read by a verified copy-once reader | proved | R-06-010, R-13-001, R-13-009 |
| `B-02` | `P-3` | Execute authority is wired only over the immutable image through the capability-wiring table, and the manifest declares the internal compartment graph | admission-rejected | R-13-004, R-13-006, R-13-024 |
| `B-02` | `P-4` | A binary enters only through a signed generation, the anti-rollback floor bounds which generations may boot, and no system component fetches code at runtime | hardware-enforced | R-09-028, R-11-005, R-13-002 |
| `B-02` | `P-5` | Worst-case execution time is derived syntax-directed over the typed control-flow graph, and a task set without a schedulability proof does not admit | admission-rejected | R-05-102, R-11-006, R-11-015 |
| `B-02` | `P-6` | Constant time is typed where a type system reaches it and proved on the binary where it does not, and is never inherited from a compiler theorem | proved | R-05-063, R-05-071, R-17-042 |
| `B-02` | `P-7` | Content addressing names a binary by its closure, so identity is computed rather than asserted and transfer is a set difference, over pack and manifest descriptors whose canonicity theorem leaves an object one encoding to be hashed | proved | R-05-051a, R-13-001, R-13-007, R-13-008 |
| `B-03` | `P-1` | Flow annotations are a first-class concern of the interface language for every cross-domain channel, over the static capability topology the theorem quantifies over | proved | R-08-021, R-12-011 |
| `B-03` | `P-2` | Both sides parse with verified copy-once parsers, over one canonical ring library proven once | proved | R-12-005, R-12-008 |
| `B-03` | `P-3` | Ring pages are mapped without capability-store permission, so authority physically cannot cross the data plane, and descriptors name only indices into a pre-delegated table | hardware-enforced | R-12-006, R-12-007 |
| `B-03` | `P-4` | Every payload slot follows a checked ownership transition, so no reader observes a slot its producer still owns | proved | R-12-008a |
| `B-03` | `P-5` | Service is metered on the session's own schedule slot, and the switch-duty ratio is counted explicitly at admission | admission-rejected | R-11-009, R-12-009 |
| `B-03` | `P-6` | The interface profile is restricted to closed variants, no recursion, and an explicit bound on every length, so decode cost is a function of declared bounds | proved | R-12-012, R-12-013 |
| `B-03` | `P-7` | One typed interface profile is fork-and-frozen, and an object reference is an out-of-band capability rather than a forgeable name | proved | R-12-010, R-12-013a |
| `B-04` | `P-1` | A front-end's capability-bounded DMA window and its configuration registers are one indivisible ownership unit, and a peripheral is electronically enabled only while a consented grant holds it | hardware-enforced | R-15-143, R-15-146 |
| `B-04` | `P-2` | Device DMA is granule-aligned by construction, and completion is an ownership boundary the fabric enforces rather than a convention the driver keeps | hardware-enforced | R-15-183, R-15-208a |
| `B-04` | `P-3` | Device DMA is capability-checked by the fabric in exactly two shapes, with neither an IOMMU nor an IOPMP on the die | hardware-enforced | R-15-205, R-15-206, R-15-209 |
| `B-04` | `P-4` | Honoring the revocation epoch for a transfer already in flight is an obligation on the fabric rather than a discharged theorem | residual | R-08-006, R-15-208, R-17-037 |
| `B-04` | `P-5` | Fixed-function sequencers complete within a bounded turnaround, and a device server's polling cadence is admitted rather than assumed | admission-rejected | R-11-011, R-15-122 |
| `B-04` | `P-6` | Readout is fixed-cadence, or event-driven with the event timing confined to the owning island's static partition | proved | R-12-070, R-12-071 |
| `B-04` | `P-7` | A wired peripheral and its cable authenticate before a data role is granted, which attests identity and not behavior | proved | R-12-060, R-12-061, R-17-056 |
| `B-05` | `P-1` | Per-extent authenticated encryption with volume keys resident only in the crypto core, and a deduplication digest keyed per confidentiality domain | proved | R-10-012, R-10-015, R-10-016 |
| `B-05` | `P-2` | The base image is a content-addressed Merkle DAG verified on every read against the signed root, and the authentication tag is the integrity checksum | proved | R-10-001, R-10-022, R-10-023 |
| `B-05` | `P-3` | Volume keys are sealed to the root of trust and to measured state, and are resident only after first unlock | hardware-enforced | R-09-017, R-10-032 |
| `B-05` | `P-4` | The monotonic counter is spent only on low-rate security-critical state, so the mutable volume is deliberately not freshness-protected | residual | R-10-011, R-10-013, R-17-043 |
| `B-05` | `P-5` | Deadlock and livelock freedom are machine-checked over a journal that carries crash refinement | proved | R-10-002, R-10-006 |
| `B-05` | `P-6` | Filesystem compression is out of scope, deleting the compression oracle, and deduplication never crosses a confidentiality domain | absent | R-10-016, R-10-018 |
| `B-05` | `P-7` | The content address is a per-domain keyed digest, deterministic within a domain and incomparable across domains, taken over an encoding a canonicity theorem makes unique | proved | R-05-051c, R-10-015, R-10-017 |
| `B-06` | `P-1` | Session keys live in crypto-core-backed compartments, and a null or broken cipher is rejected rather than negotiated | proved | R-12-042, R-12-044 |
| `B-06` | `P-2` | Every attacker-facing wire format is parsed by a verified copy-once parser stated against a descriptor that is itself a reviewed specification | proved | R-05-042, R-05-046, R-12-040 |
| `B-06` | `P-3` | The whole radio stack is contained compartments in no trusted set, and the one tolerated foreign computer is a zero-authority register slave | hardware-enforced | R-06-021, R-12-045 |
| `B-06` | `P-4` | Mutual authentication is required with no silent downgrade, the legacy generations a downgrade would reach are absent from the silicon, and each protocol has one admissible configuration with nothing to negotiate, its sequencer proved to refine a formal model of the standard's own state machine so that a transition the model does not carry is unreachable | absent / proved | R-12-041, R-12-042, R-12-043a, R-12-043b |
| `B-06` | `P-5` | Radio deadlines ship as admitted hard tasks, and a stack crash costs connectivity rather than platform integrity | proved | R-11-007, R-16-002 |
| `B-06` | `P-6` | The plane split keeps wire parsing in the data plane and protocol state in synchronous control planes whose reaction time is structural | proved | R-05-054, R-12-043 |
| `B-06` | `P-7` | A value crosses under exactly one admissible encoding, canonicity being proved from the descriptor rather than tested, though agreement with a peer's implementation of the same format stays evidence; no persistent link-layer identifier exists in hardware, every address being a draw from the one entropy root, which is necessary and not sufficient for unlinkability | proved / hardware-enforced / residual | R-05-051a, R-15-132, R-15-133, R-17-016b, R-17-055 |
| `B-07` | `P-1` | Non-interference holds modulo robust delimited declassification, and the powerbox is the sole runtime declassifier; what the modulo releases is decided by the consent act, so the mechanism is proved and the judgment is the user's | proved / transferred | R-06-016, R-08-024, R-08-026, R-17-013 |
| `B-07` | `P-2` | A grant is an authenticated user act over a path whose front-end ownership the root of trust latches for the prompt's duration | hardware-enforced | R-08-036, R-12-078, R-12-081 |
| `B-07` | `P-3` | The powerbox holds only the authority grants are attenuated from, and a supervised restart re-grant mints nothing new | proved | R-08-035, R-12-074 |
| `B-07` | `P-4` | A grant carries a temporal scope enforced by the same revocation, and the unconditional cuts dominate any lease | proved | R-08-037, R-08-041 |
| `B-07` | `P-5` | The compositor may deny service but cannot forge consent, and touch being unavailable to applications while a prompt is up is an accepted cost | residual | R-12-076, R-12-080, R-17-010 |
| `B-07` | `P-6` | There is no ambient observation of input or of surfaces, and the touch driver is not trusted between the front end and the agent | hardware-enforced | R-12-075, R-12-077 |
| `B-07` | `P-7` | The on-die path is the platform's own authenticator, and an external roaming authenticator is declined rather than admitted | admission-rejected | R-12-020 |
| `B-08` | `P-1` | Clock read-out is authority, coarse by default, and statistical degradation of a counter read is inadmissible | proved | R-08-031, R-08-031a |
| `B-08` | `P-2` | Every time source is authenticated, and the precision protocol runs in the most defensive profile the standard allows | proved | R-12-035, R-12-037 |
| `B-08` | `P-3` | Precision beyond the default is granted through the one time-service interface rather than read ambiently from a counter | proved | R-08-031, R-12-036 |
| `B-08` | `P-4` | The platform carries no persistent real-time clock: the device boots time-unknown, re-acquires from an authenticated source, and holds a persisted monotonic floor | absent | R-09-012, R-09-014, R-09-016 |
| `B-08` | `P-5` | A network adversary can deny or stall fresh absolute time, which is booked as an availability limit rather than an integrity one | residual | R-17-057 |
| `B-08` | `P-6` | The schedule is time-triggered and non-work-conserving, so an idle slot is burned rather than donated | absent | R-07-032, R-07-036 |
| `B-08` | `P-7` | Nothing security-critical depends on wall-clock time, the monotonic counters being counters rather than clocks | absent | R-09-013 |
| `B-09` | `P-1` | There are no maintainer scripts, no post-install execution, and no runtime code fetching by system components | absent | R-13-002 |
| `B-09` | `P-2` | The base image is bit-for-bit reproducible, so a relying party reproduces the reference values instead of being told them | proved | R-09-027, R-13-026 |
| `B-09` | `P-3` | The toolchain is untrusted evidence-producing machinery: a compromised compiler cannot mint a valid certificate for a property its output lacks | proved | R-06-015, R-13-021 |
| `B-09` | `P-4` | Each signed generation emits a reference integrity manifest, and the monotonic anti-rollback floor bounds which generations remain bootable | hardware-enforced | R-09-026, R-09-030 |
| `B-09` | `P-5` | There is no trusted-toolchain fallback, so the certifying compiler is a delivery prerequisite and its preservation theorem an availability property | residual | R-13-022, R-17-033 |
| `B-09` | `P-6` | A subverted but memory-safe upstream is answered by compose-time compartmentalization, which the source-correspondence theorem cannot reach | proved | R-13-023, R-13-024 |
| `B-09` | `P-7` | Correspondence between the reviewed design and the fabricated die is evidence rather than proof, claimed for the logic tier at a stated resolution | residual | R-17-060, R-17-061, R-17-063 |

## 4. How to read a cell, and how to change one

A cell says how this design carries one property at one boundary, and points at the register for the obligation itself. It is not a summary of everything the requirements say; it is the shortest statement that makes the pair decidable.

A **residual** cell is not an empty cell. It records that the remainder is booked in §17 with an owner and a scope, which is the honest discharge for a pair no construction closes. What the matrix forbids is the third case, a pair with neither.

A **detected** cell and a **transferred** cell are the two ways a pair is carried without being closed here, and both are read wrong if read as the first four modes. Detected says the fault reaches the boundary and cannot cross it silently, so what the cell bounds is the consequence and not the fault. Transferred says the obligation crosses to the party the cell names, so what the cell states is where it went; a transferred cell whose text names no party is defective on its face.

To change a cell, change the register first. Adding a boundary or a property adds a row to one of the two enumerations above and thereby a whole line or column of cells, every one of which must be filled before the checker passes: that is the intended cost, and it is what keeps the enumerations honest rather than convenient.
