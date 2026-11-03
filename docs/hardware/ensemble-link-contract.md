# The Ensemble Link Contract: Its Frames, Its Endpoint, and What Each Is Waiting On

> A gating artifact, governed by [R-15-228b through R-15-228e, R-12-007a, R-12-015d, R-11-017a and R-15-196a](../requirements-register.md).
> It states the frame grammar as a Narcissus descriptor, the link's code and its selection predicate, the endpoint's register description with every register's owner, the per-link composition constants with the artifact that carries each, R-04-010a's three conditions decided against the block clause by clause, the netlist evidence an auditor searches for, and the link server's IDL interface.
> Where this document and [the register](../requirements-register.md) disagree, the register wins and this document is defective.

## How to read this

This is the first of R-02-003a's five ensemble admission artifacts. It supplies the endpoint and frame contract delegated by R-15-228b through R-15-228e, the design-specific code delegated by R-15-119, and the handshake grammar, cryptographic checks and public fields delegated by R-12-015d.

The register owns the frame forms, code discipline, endpoint absences, window contracts, arrival-phase rule and slot-table fields. Under R-05-152's single-owner rule, this contract adds their field layout, length forms, register ownership, classification decisions, refusals and consumer arithmetic.

**Composition and qualification values remain pending.** R-15-228d and R-11-017a assign frame geometry, slot instants, guard bands and leap cadence to the attested schedule artifact. R-17-041 owns the latency magnitudes at [crown-jewel](../assurance/crown-jewels.md) row 15 (`not authored`); R-15-196a requires a measured two-member skew bound. No composition fixes these values. [§4](#4-the-per-link-composition-constants) records their units, admissibility predicates and owners; quoting a pending value as decided is EL-2 in [§8](#8-what-makes-a-candidate-a-report-or-an-implementation-inadmissible).

**The code family remains unselected.** R-15-228e requires a choice between R-15-119's two families. [§2](#2-the-links-code) states the selection predicate; Q23g's two-member measurement must supply the wire's raw error rate at the declared reach and frame length. Selecting a family without that operand would also violate EL-2.

## 1. The frame grammar

### 1.1 The two layers, and which one the descriptor is over

A wire frame is one codeword of the link's code (R-15-228e). **The descriptor parses the decoded message block.** The encoder adds parity symbols and the decoder removes them; neither reads fields, and no parser sees symbols or a decode verdict. This separation leaves a verdict register without a grammar consumer; R-15-228e independently prohibits the register itself, enforced here by EL-5.

Every form occupies exactly `M` message-block bytes, the composition-fixed code message length in [§4](#4-the-per-link-composition-constants). No form has a frame-length field. This supplies R-05-051b's single admissible frame-length form.

### 1.2 The four forms, and what selects between them

| Id | Form | Regime | Carried in |
| --- | --- | --- | --- |
| `FF-1` | established-session payload frame | established | any established-session slot the table grants, where the link server has payload |
| `FF-2` | authenticated idle frame | established | every other established-session slot (R-15-228d) |
| `FF-3` | scheduled handshake frame | unestablished | the composition-reserved establishment slots (R-12-015d) |
| `FF-4` | unestablished-slot public padding | unestablished | every other enabled slot before establishment (R-15-228d) |

The receiver's own session state selects the regime; its table and origin identify the slot and expected handshake step at R-12-015d's composition-fixed cadence. A frame's discriminants are checked against that state and schedule; they select no handler, key or regime. A mismatch is a post-parse eligibility refusal. Parsing remains a total function of bytes alone, and canonicity remains a property of one state-independent language.

Parsing walks fixed-width fields into a fixed destination buffer (R-05-124), with cost determined solely by `M`. The receiving link server then checks payload eligibility against its own per-link session table (R-12-007a). That decision is reachable only in the established regime, so no parsed handshake can authorize payload delivery.

### 1.3 `FF-1` and `FF-2`, the established-session message block

`FF-1` and `FF-2` have the same public shape. R-15-228d's distinguishing type field is inside the sealed body and read only after decryption and authentication; this regime has no public discriminant.

| Order | Field | Kind | Length | Public before the tag verifies | Read by |
| --- | --- | --- | --- | --- | --- |
| 1 | `sealed_body` | opaque bytes | `M - L_tag` | no | the crypto core, which decrypts it (R-05-070, R-15-202) |
| 2 | `tag` | opaque bytes | `L_tag` | as bytes, and it names nothing | the crypto core, which verifies it before any field below is read |

The tag's associated data is derived locally: the link, session epoch and schedule-derived count of link slots since that epoch (R-12-015d). None is supplied on the wire. The frame carries no sequence number, epoch, session identifier or sender field (R-15-132); displacement to another slot fails the tag.

The plaintext body, which the verified copy-once parser reads only after the tag verifies:

| Order | Field | Kind | Length | Read by |
| --- | --- | --- | --- | --- |
| 1 | `body_kind` | `WF-7` enum over exactly two cases, `payload` and `idle` | the discriminant width `IDL-023` fixes for two cases | the receiving link server |
| 2 | `descriptor_count` | `WF-5` count, admissible values `0` through `N_desc_max` | `w_count`, the width `IDL-023` fixes for that bound | the receiving link server |
| 3 | `descriptors[i]` | R-12-092's descriptor, each member encoded by the row of [the IDL profile](../languages/idl-profile.md)'s encoding table that `IDL-053` names for its kind | `S_desc` each, `N_desc_max * S_desc` in all | the receiving link server, which validates every one against its own per-link table before any becomes eligible |
| 4 | `payload_region` | opaque bytes, indexed by the descriptors' offsets and lengths | `P_bytes` | the receiving compartment, after validation and after the link server's copy |

The four rows exactly fill `M - L_tag` by [§4](#4-the-per-link-composition-constants)'s arithmetic. Descriptor slots above `descriptor_count` and payload bytes outside admitted descriptor extents are declared zero fill under `IDL-024`; any nonzero fill byte fails decoding, as R-05-051b requires. For `idle`, `descriptor_count` must be zero, making both the descriptor array and payload region entirely fill. `FF-2` therefore uses `FF-1`'s encoding and length with an empty descriptor list and zero payload.

### 1.4 `FF-3`, the scheduled handshake frame

`FF-3` has no session tag. Its integrity checks are inside the construction's `step_payload`: R-12-015a's sealing service brokers schema-bounded credential requests returning only protocol results, and Q23c owes R-12-015d's reference model of that relation. This contract specifies the delegated grammar.

| Order | Field | Kind | Length | Public before the tag verifies | Read by |
| --- | --- | --- | --- | --- | --- |
| 1 | `form` | `WF-7` enum over exactly two cases, `handshake` and `padding` | the discriminant width `IDL-023` fixes for two cases | n/a, no tag exists in this regime | the bounded parse |
| 2 | `step` | `WF-7` enum over R-12-015d's finite step set | the discriminant width `IDL-023` fixes for that set | yes | checked against the reserved slot's step, then R-12-015d's bounded establishment handler |
| 3 | `step_payload` | opaque bytes, the construction's | `H_step(s)` for the decoded step `s`, the remainder of the block a declared zero fill on `IDL-024`'s terms | yes | R-12-015d's bounded establishment handler alone |

This form reaches only R-12-015d's bounded establishment handler, with no path to the receiving compartment, payload eligibility or an origin leap (R-15-228b, EL-4).

All `FF-3` fields are public: hybrid key-establishment shares, two fresh challenges, attestation evidence and the bound slot-table digest. Confidentiality depends on none of them. The form carries no address, capability encoding, persistent link-layer address or sender field; peer identity appears only as attestation evidence processed by the session construction (R-15-132, R-12-015d).

### 1.5 `FF-4`, unestablished-slot public padding

| Order | Field | Kind | Length | Public before the tag verifies | Read by |
| --- | --- | --- | --- | --- | --- |
| 1 | `form` | `WF-7` enum, the `padding` case | the discriminant width `IDL-023` fixes for two cases | n/a, no tag exists in this regime | the bounded parse |
| 2 | `fill` | the declared constant `F_pad`, repeated | the remainder of the block | yes | nothing |

Every `fill` byte must equal `F_pad` or decoding fails. The fixed-length comparison precedes discarding the form; nothing downstream reads it. This meets R-05-051b's prohibition on unchecked fill and gives padding no path to application delivery or an origin leap.

### 1.6 The no-slack conditions, as this descriptor's own

The following table applies R-05-051b's general descriptor conditions to these four forms.

| Condition | How this descriptor meets it |
| --- | --- |
| one admissible length form | every form is `M` bytes, and no field of the frame format bounds another field's extent except `descriptor_count`, whose width `IDL-023`'s ladder fixes from `N_desc_max` alone. A buffer reference inside a descriptor does carry an offset and a length (`WF-11`, R-12-092), each a fixed-width scalar inside the descriptor's own fixed size, and neither selects an extent on this member: nothing a reference names becomes eligible until the receiving link server has validated it against its own per-link table (`IDL-054`, R-12-007a) |
| one presence encoding per optional field | the only optional member is R-12-092's deadline, encoded by `WF-8` inside the descriptor; no second presence encoding exists in any form |
| fixed field order | the order is the `Order` column of [§1.3](#13-ff-1-and-ff-2-the-established-session-message-block) through [§1.5](#15-ff-4-unestablished-slot-public-padding), and it is a property of the form and not of the values |
| no free padding, no reserved bits | every fill byte is declared and checked, `FF-1` and `FF-2` to zero on `IDL-024`'s terms and `FF-4` to `F_pad`, which is what keeps none of them the free padding this condition forbids; the descriptor's flag set is `WF-10`, where a set bit above the declared count is a decode failure |
| no accept-and-ignore field | every field above names a reader, and the two that name none, the fills, are decode failures when they differ from their declared value |
| a non-canonical input fails rather than normalizing | the parse is total over the bytes and produces a value or a failure; no path rewrites an input into the canonical encoding of the same value |

**R-05-051a's canonicity theorem is OWED.** The frame encoding feeds authentication, and both ends bind the slot-table digest into the session context, so its signature/equality-input rule applies. [Crown-jewel](../assurance/crown-jewels.md) row 10 is `partial`: the wire-format inventory exists, while Narcissus descriptors and their checked derivations remain absent. No descriptor exists for a Coq-checked injectivity theorem. [§1](#1-the-frame-grammar) supplies this member's grammar under R-05-046; the theorem must land with its descriptor. Claiming it already exists is EL-10.

## 2. The link's code

### 2.1 The selection predicate

A candidate code is admissible only if every clause below holds, jointly applying R-15-228e, R-15-119, R-15-119c and R-12-043a.

| # | Clause | Why it is here |
| --- | --- | --- |
| 1 | fixed geometry: one message length `M`, one codeword length `N`, one rate, no puncturing or rate matching chosen at run time | R-15-228e's *fixed-geometry block code* |
| 2 | one codeword is one frame, and one frame is one codeword | R-15-228e; it is what makes [§1.1](#11-the-two-layers-and-which-one-the-descriptor-is-over)'s two layers separable |
| 3 | a deterministic iteration bound `I_max`, run to the bound and never stopped early | R-15-119's bound and R-15-119c's discipline, read at this device rather than at the ISA unit |
| 4 | decode latency independent of the symbols and of whether the frame was correctable | R-15-119c; an early-terminating decoder reports correctability in its latency |
| 5 | no verdict register, no syndrome and no CRC decides a frame; the decoder reports the decoded bits and nothing else | R-15-228e, on R-15-119b's ground for declining the verdict register at the ISA surface |
| 6 | no re-encode at any hop | R-15-228e, R-15-176's chain ending at each member's edge |
| 7 | no rate adaptation, no feedback from the peer, no hybrid retransmission | each is a retry or a credit, which A-18 and A-19 already exclude from the endpoint |
| 8 | exactly one admissible code per link, fixed at composition | R-12-043a's one-configuration discipline read at the code |
| 9 | the family is one of R-15-119's two, and the link's code is this design's own | R-15-228e, R-15-119, which adds that it owes no table to any standard |

Clause 8 fixes one code per link, with no control-plane variable selecting another, just as no variable selects a ciphersuite. Different links may use different composition-fixed codes.

### 2.2 The two latency rows

Encoding and decoding belong to the endpoint's device timing row, separate from R-15-119c's two ISA rows. Admission charges `T_enc` to the transmitting endpoint's slot and `T_dec` to the receiving endpoint's. R-11-017a also charges the link server, per-frame crypto operations and [§3.3](#33-the-two-window-contracts)'s window grants as ordinary R-11-006 tasks and grants.

R-17-041 owns both latency magnitudes; [§4](#4-the-per-link-composition-constants) records them without values.

### 2.3 What the family is waiting on

Both R-15-119 families can satisfy [§2.1](#21-the-selection-predicate)'s structural clauses at a suitable geometry. The choice requires comparing decode latency at a target residual frame error rate, using the declared frame length and the wire's raw error rate at the declared reach. Frame length is unfixed, the cable and connector are unspecified, and none of R-02-003a's five artifacts supplies that reach or error-rate measurement.

Q23g owns the first planned measurement: two FPGA instances of R-18-005's scalar class carrying the endpoint. The `code_family` row in [§4](#4-the-per-link-composition-constants) records the missing operand and owner. Selection occurs once per link at composition under [§2.1](#21-the-selection-predicate), changing neither its clauses nor [§1](#1-the-frame-grammar)'s fields.

### Research handoff for the unselected code

Q23g's future selection can consult the [code and decoder proof handoff](../assurance/proof-reuse/hardware.md#research-handoff-for-future-code-and-decoder-proofs), which routes the survey's binary rate-distance bounds, folded/ordinary Reed-Solomon decoding and scratch-space advances to concrete finite proof obligations. The inspected formal improvement to the asymptotic binary-code upper bound is a constraint on a rate-distance frontier, not a finite code or decoder. Those results do not select one of the admitted families, establish the wire's error model or implement the decoded-bits-only interface. A list decoder with several candidates and authenticated selection is a different interface until a reviewed construction proves it satisfies every clause of [§2.1](#21-the-selection-predicate). VT deletion correction and the seven-cycle zero-error construction have no identified matching channel here.

The [communication proof handoff](../assurance/proof-reuse/protocols.md#research-handoff-for-future-communication-proofs) separately routes log-rank and Li-Li to possible future Q23d/Q23h comparisons. Neither licenses shorter unpadded transcripts, network coding, new forwarding behavior or lower reserved traffic in this point-to-point contract. These research notes supply no missing magnitude, new acceptance clause or completion evidence.

## 3. The endpoint's register description

### 3.1 What is a register of this endpoint and what is not

Three relevant structures are owned outside the endpoint:

| Structure | Whose it is | Why it is not the endpoint's |
| --- | --- | --- |
| the two delegated window capabilities | the owning island's memory controller, in the fabric-side window registers R-15-208 places there | R-15-208 puts the delegated capability in a fabric-side register re-authorized at the start of each TDM grant against the island's R-08-005a revocation bit; the endpoint carries no capability-bearing register, so R-12-007's *mapped without capability-store permission* is structural at this block and what the endpoint lands is untagged bytes (R-12-007a) |
| the frame-origin register | the clock spine (R-15-195, R-15-196a) | it is the platform-wide origin every core's boundary handler, the memory controller's TDM arbiter and each window's grant read as a common zero, stepped by exactly one kernel instance, the boot core's, under a capability the composition grants to it alone; **the endpoint has no write path to it at all**, which is what A-21's search reads |
| the session keys, the cipher, and the tag | the crypto core (R-05-070, R-15-202) | R-15-228c has the endpoint hold no key and no cipher, so no key register, no nonce register and no tag-verify result register exists here |

R-15-228c assigns each engine a window; R-15-208 places the capability in fabric-side registers. This contract reconciles them by assigning each engine a configuration index naming its fabric-side window. The index is neither an address nor a capability. This is an explicit interpretation of ownership and mechanism, subject to review.

### 3.2 The registers

`Access` is relative to the named `Owner`; additional parties' rights appear in the description. All unlisted accesses and offsets fault. Offsets remain pending composition constants: R-15-002b and R-09-007 constrain the attested devicetree's MMIO aperture, but no register entry assigns offsets within it. [§4.2](#42-one-declaration-this-contract-cannot-make-and-who-owes-it) records the corresponding declaration gap.

| Name | Owner | Access | What it is, and what it is not |
| --- | --- | --- | --- |
| `SLOT[i]` | the link server compartment, as configuration MMIO | `RW` while the grant is live | one entry of R-11-017a's link slot table for this endpoint: the slot's instant against the member's own origin, its direction, and its guard band. Core-issued software loads it from the admission artifact's fourth output; no runtime exchange establishes or amends it |
| `TX_WINDOW_BIND` | the link server compartment, as configuration MMIO | `RW` while the grant is live | the index of the fabric-side window register the transmit engine issues against. Carries no address and no capability; cleared when the grant is revoked |
| `RX_WINDOW_BIND` | the link server compartment, as configuration MMIO | `RW` while the grant is live | the same for the receive engine |
| `EQ_READY` | the endpoint's line interface | write, at link-up and at link-down and at no other instant | whether the current link epoch's equalization training has completed, which is the frozen store's own validity and nothing else. The link server reads it `RO` and no software writes it. **It holds no epoch number**: which link epoch is in force is the link server's own state, read through [§7.3](#73-the-operations)'s `session_state`, and the endpoint holds no epoch counter |
| `EQ_COEF[j]` | the RoT | write, cleared on link-down | the equalization coefficients, trained at link-up and frozen for the epoch on R-15-137's terms (R-15-228c). The link server neither reads nor writes it |
| `ARRIVAL_PHASE` | the endpoint | write, on the landing in the slot named for the leap | the one-sided arrival-phase reading of the most recent landing in the slot this endpoint's table names for the leap (R-15-196a). Holds one reading and no history, no accumulator and no estimator. It is `RO` to all software, and the boot core kernel's leap path is its one reader |

The table is exhaustive. R-15-228c permits no frame-written state beyond the landing and arrival-phase reading, so no receive status, landed flag or FIFO-level register exists. The schedule tells software when to read a receive entry (R-15-228d); `EQ_READY` records training validity and is unreachable from frames. Enablement depends solely on the live delegated-window grant (R-15-146, R-15-228c). The link server has no equalization write path, and coefficients remain frozen within an epoch.

`M`, `N`, `I_max` and the code family are synthesis-time block parameters. R-15-228c's composition-supplied configuration therefore reaches them at synthesis, while `SLOT[i]` and the window binds carry schedule configuration. Their build binding follows [synthesis provenance](../../rtl/synthesis-provenance.md)'s parameter-recording form. Its A-18 through A-21 rows are currently `n/a` because the endpoint is net-new authored RTL; endpoint provenance is owed with the block.

There is no slot counter: the slot index is computed from the spine origin and `SLOT[i]`, meeting the third condition examined in [§5.3](#53-condition-three-it-runs-to-a-stated-bound-and-accumulates-no-state-across-operations). The link server and crypto core derive R-12-015d's epoch-relative slot count from the same inputs. An endpoint-held count would violate EL-1.

This contract places `EQ_COEF[j]` in the RoT's aperture, outside R-15-143's indivisible configuration-MMIO/window ownership. R-15-137 also permits a store within that ownership if it remains frozen throughout the epoch. The chosen placement removes the link server's control altogether: review checks an ownership boundary rather than every possible write path through a freeze. This is a contract decision, open to review, rather than a deduction from those entries.

### 3.3 The two window contracts

The engines are R-15-206's second shape, autonomous streaming engines holding delegated, bounds-checked, revocable window capabilities for the lifetime of their windows, into ring regions of the endpoint's island (R-15-223, R-15-228c). Both windows carry every clause below, and only the last differs.

| Clause | Transmit window | Receive window |
| --- | --- | --- |
| the capability | delegated, bounds-checked, revocable, held fabric-side ([§3.1](#31-what-is-a-register-of-this-endpoint-and-what-is-not)) | the same |
| store permission | absent, so what the engine reads is untagged bytes (R-12-007) | absent, so what the engine lands is untagged bytes (R-12-007a) |
| revocation | the bit at the window capability's base is read from the island's R-08-005a array at the start of each TDM grant of that window, and no request of that grant issues when it is set (R-15-208) | the same |
| teardown | R-15-208a's completion boundary, so a torn-down link leaves no engine authorized past the next grant (R-15-228c) | the same |
| ownership | indivisible with the configuration MMIO, granted and revoked together, held by the link server compartment alone (R-15-143) | the same |
| occupancy | one frame per slot, the slot's own entry, placed by the link server before the launch instant | **at most one frame per slot** (R-12-015d), landed in the entry the slot names |

The receive occupancy limit prevents a peer or wire from landing two frames in a slot (R-12-015d). Failure to drain an entry before its next scheduled landing is the partition's overrun, restarted under R-07-040 without reaching another partition's slot (R-15-228c). Both window extents are composition constants in [§4](#4-the-per-link-composition-constants); peer-dependent resizing would violate EL-1.

### 3.4 The FIFO, the line rate, and why the link adds no asynchronous boundary

The recovered line clock terminates in a bounded receive FIFO of depth `D_fifo`; the fabric side uses the island clock (R-15-196a). It belongs to R-15-196's existing external-interface-clock class, adding no class to that entry's count of three. FIFO placement does not determine that count.

This contract places the FIFO only on the receive path and runs the transmit serializer from the member's own clock. No register entry fixes the transmit clock domain; this is an explicit design decision, independent of the class count.

`D_fifo` must absorb the two declared oscillator tolerances across one frame at `M` and `N`, and be no deeper. Its depth depends only on those composition constants, never on peer activity, credits, retries or sequence. A depth sized for more than one frame or for peer behavior would be an A-20 queue.

`R_line` contributes only a line-rate bound to bandwidth reservation (R-15-196) and must not exceed crypto-core authenticated-encryption throughput (R-12-015d). A higher rate refuses composition; the single-code, single-schedule link has no fallback rate.

### 3.5 The arrival-phase reading

`ARRIVAL_PHASE` is updated by the landing of the leader link's frame in the slot the table names for the leap. It is **one-sided**: it is a reading of when a landing occurred against the member's own origin, not a two-sided estimate of the peer's offset, and the endpoint holds no loop that would close over it (A-21).

The endpoint has no key or cipher, so it updates `ARRIVAL_PHASE` before verification. The boot core kernel consumes the reading only after the crypto core verifies that frame's tag in its own slot; tag failure permits no leap (R-15-196a). Verification therefore gates the leap, not the reading's update.

A compromised leader or wire adversary delaying a genuine frame within its accepted slot can walk a follower's origin by at most the skew bound per cadence inside the guard band (R-17-025a). The tag authenticates no within-slot arrival instant. Displacement outside the accepted slot fails the tag and stops the link (R-17-030z).

### 3.6 The slot-table register format

`SLOT[i]` carries R-11-017a's own field set for one slot and carries nothing else.

| Field | Kind | What decides it |
| --- | --- | --- |
| instant | the slot's start in the member's own spine cycles against the member's own origin (R-11-014a) | the ensemble schedule, emitted by the one composition act |
| direction | transmit or receive | the same |
| guard band | the slot's guard band, admissible only at or above the composition's skew bound plus this link's latency bound (R-11-017a) | the same |

All slots carry the link's one frame length, so `SLOT[i]` has no length field (R-15-228d). The leap slot belongs to the member's artifact, not this table: it is a kernel-owned idle window reserved on every core at the same absolute instant (R-11-017a). Each end binds the table digest into session establishment; different tables refuse the session (R-12-015d, R-11-017a).

## 4. The per-link composition constants

Each row names a quantity, its admissibility predicate and its deciding and carrying artifacts. **All values remain pending** because no composition fixes them. EL-2 prohibits substituting placeholders.

The carrier column distinguishes the attested schedule artifact, attested devicetree and [§7](#7-the-link-servers-idl-interface)'s generated-interface declaration. Some assignments are explicit in the register; others rely on R-02-003a's general clause for ensemble constants. [§4.2](#42-one-declaration-this-contract-cannot-make-and-who-owes-it) records that declaration gap.

| Symbol | Quantity | Unit | Admissibility predicate | Decided by | Carried and emitted by |
| --- | --- | --- | --- | --- | --- |
| `M` | code message length, one frame's message block | bytes | equals `L_tag` plus the sum of [§1.3](#13-ff-1-and-ff-2-the-established-session-message-block)'s plaintext body; the same for all four forms | the composition (R-15-228d) | the attested schedule artifact, every slot of a link carrying the link's one frame length (R-15-228d, R-11-017a); Q23d |
| `N` | codeword length | symbols | fixed geometry at the declared rate; `M` maps to it under one code (R-15-228e) | the composition | the attested devicetree; Q23d |
| `code_family` | LDPC or polar | n/a | every clause of [§2.1](#21-the-selection-predicate), then the lower decode latency at the target residual frame error rate | **owed**; operand is the wire's raw error rate at the declared reach and `M` | first measured at Q23g |
| `I_max` | decoder iteration bound | iterations | deterministic, run to the bound, never stopped early (R-15-119c) | the composition | the attested devicetree; Q23d |
| `L_tag` | authentication tag | bytes | the one admissible configuration R-12-043a fixes for the session's construction | R-12-015d's construction | the attested devicetree |
| `S_desc` | descriptor size of the link interface | bytes | one size for every variant of the closed descriptor variant (`IDL-024`, R-12-091) | the generated interface artifact | [§7](#7-the-link-servers-idl-interface)'s declaration |
| `N_desc_max` | descriptors per payload frame | count | `L_tag + d_kind + w_count + N_desc_max * S_desc` does not exceed `M`, leaving `P_bytes` at or above the link's declared minimum payload | the composition | [§7](#7-the-link-servers-idl-interface)'s declaration |
| `P_bytes` | payload region of a payload frame | bytes | `M - L_tag` less [§1.3](#13-ff-1-and-ff-2-the-established-session-message-block)'s discriminant, count and descriptor array | derived, see [§4.1](#41-the-arithmetic-which-is-what-a-sibling-item-can-read) | derived |
| `H_step(s)` | handshake step payload, per step | bytes | at most `M` less [§1.4](#14-ff-3-the-scheduled-handshake-frame)'s two discriminants; the remainder is declared zero fill | R-12-015d's construction | Q23c's reference model |
| `F_pad` | the padding fill value | byte | one value; any other byte is a decode failure | the composition | the attested devicetree |
| `D_fifo` | receive FIFO depth | entries | absorbs the two declared oscillator tolerances across one frame, and no deeper ([§3.4](#34-the-fifo-the-line-rate-and-why-the-link-adds-no-asynchronous-boundary)) | the composition | the attested devicetree; Q23g measures the tolerance it is derived from |
| `R_line` | line rate | bits per second | at or below the crypto core's authenticated-encryption throughput (R-12-015d); contributes the line-rate bound to the member's reservation (R-15-196) | the composition | the attested devicetree |
| `T_enc` | encode latency | cycles | fixed, independent of the symbols ([§2.2](#22-the-two-latency-rows)) | **owed**; R-17-041's magnitudes, [crown-jewel](../assurance/crown-jewels.md) row 15 | measured at Q23g; entered in the attested devicetree by name as one of the link's latency constants (R-15-196a) |
| `T_dec` | decode latency | cycles | fixed, independent of the symbols and of correctability ([§2.2](#22-the-two-latency-rows)) | **owed**; the same | the same |
| `T_slot` | slot period of this link | spine cycles | the table's own, one frame per slot (R-15-228d) | the ensemble schedule | the attested schedule artifact (R-11-017a); Q23d |
| `G_band` | guard band, per slot | spine cycles | at or above `B_skew` plus this link's latency bound (R-11-017a) | the ensemble schedule | the attested schedule artifact (R-11-017a); Q23d |
| `C_leap` | re-alignment cadence on the leader link | slots | `C_leap` times both members' declared oscillator tolerance lies inside `G_band` (R-11-017a) | the ensemble schedule | the attested schedule artifact (R-11-017a); Q23d |
| `B_skew` | skew bound between two members' origins | spine cycles | **owed**; measured on a two-member pair at qualification, a pair exceeding it failing to qualify rather than leaping more often (R-15-196a) | measured at Q23g | the attested devicetree, beside the link's latency constants and by name (R-15-196a) |
| `C_epoch` | re-establishment cadence | slots | composition-fixed, never on demand (R-12-015d, R-15-228e) | the composition | the attested devicetree |
| `W_tx`, `W_rx` | the two window extents | bytes | a ring region of the endpoint's island (R-15-223); one frame per slot in `W_rx` (R-12-015d) | the composition | the attested devicetree |
| `N_eq` | equalization coefficient count | count | frozen for the epoch, cleared on link-down (R-15-137) | the composition | the attested devicetree |

### 4.1 The arithmetic, which is what a sibling item can read

Q23e's Start requires Q23b's frame size. This contract supplies its arithmetic and parameter names; no composition fixes the per-link value R-15-228d requires. [§4](#4-the-per-link-composition-constants) therefore supplies no placeholder.

The arithmetic, over [§1.3](#13-ff-1-and-ff-2-the-established-session-message-block)'s field list:

- `P_bytes = M - L_tag - d_kind - w_count - N_desc_max * S_desc`, where `d_kind` and `w_count` are the widths `IDL-023`'s ladder fixes for two cases and for `N_desc_max`.
- The useful bytes a payload frame moves are `P_bytes`, and not `M`: the tag, the discriminant, the count and the unused descriptor slots are carried in every frame whether or not they are used, which is the same non-work-conserving price R-15-228d already charges for the idle frame.
- Frames per step on one link are the bytes that step exchanges over that link divided by `P_bytes`, rounded up, and the slot tables must grant at least that many transmit slots per step or the sharding is refused at composition (R-15-171a).
- Wire symbols per step are that frame count times `N`, which is what `R_line` is checked against.
- The per-frame charge on the member's admission is `T_enc` or `T_dec` in the endpoint's slot, the crypto core's authenticated-encryption operation over `M` in its slot, and the link server's validation and copy in its own (R-11-017a).

Every term except `d_kind` and `w_count` has a pending [§4](#4-the-per-link-composition-constants) row, so no numeric result follows today. `IDL-023` fixes `d_kind` at one byte, the smallest of one, two or four bytes holding two cases. `w_count` remains pending with `N_desc_max`. Consumers cite those owning rows for values.

### 4.2 One declaration this contract cannot make, and who owes it

R-09-007 explicitly lists core classes, islands, NoC schedule, OPP tables and radio calibration, and its added Accept clause names R-15-228h's inference-socket constants. It does not enumerate ensemble-link constants.

R-11-017a and R-15-228d explicitly place `T_slot`, `G_band`, `C_leap` and `M` in the attested schedule artifact. R-15-196a explicitly places `B_skew`, `T_enc` and `T_dec` in the attested devicetree. R-02-003a names ensemble membership, link endpoints, leader ends and expected peer identities there, plus a general clause covering every ensemble constant. Only that general clause places `N`, `I_max`, `L_tag`, `F_pad`, `D_fifo`, `R_line`, `C_epoch`, `W_tx`, `W_rx` and `N_eq` there; R-09-007 names none of them. The clause cannot be the sole carrier rule for all constants, since `M` is explicitly assigned to the schedule artifact.

Whether R-09-007 needs an explicit Accept clause for this second class of constants remains a register decision. This contract records the reliance on a general clause and leaves that decision open.

## 5. R-04-010a, decided clause by clause

R-15-228c and R-04-010a classify the endpoint as matter. The tables below apply the three conditions to its parts, pairing each satisfying structure with a searchable falsifier in the Coq term or netlist.

### 5.1 Condition one: the transition relation is welded in RTL over no writable program store

| Clause | Satisfied by | Falsified by |
| --- | --- | --- |
| the encoder | a fixed linear map at one geometry, `M` to `N` under the one code [§2.1](#21-the-selection-predicate) admits | a code-set index the block selects from at run time; a generator matrix read from a store the block writes |
| the decoder | a fixed graph run to `I_max`, reporting decoded bits and nothing else | a message schedule read from a writable store; an instruction fetch; a microcode ROM; a decode verdict register |
| the slot timer | a comparator of the spine's origin plus `SLOT[i]`'s instant against the member's own cycle count (R-15-122's kind) | a sequencer whose next state is read from memory the block writes; a program store of any width |
| the line interface | a fixed filter whose coefficients are frozen for the epoch and loaded only by the RoT ([§3.2](#32-the-registers)) | a coefficient store the datapath's own control rewrites within an epoch, which is a third-condition breach as well as this one |

The first condition governs the program store, not input dependence (R-04-010a). Decoder arithmetic may depend on received symbols while its transition relation remains composition-fixed, as in the PD sequencer.

### 5.2 Condition two: every operand and every schedule is core-issued under explicit capability operands

| Clause | Satisfied by | Falsified by |
| --- | --- | --- |
| the schedule | `SLOT[i]` loaded by core-issued software from the admission artifact's fourth output, with no runtime exchange amending it (R-11-017a) | a slot the block derives from a frame; a table entry a peer's frame writes; any path from the wire to `SLOT[i]` |
| the operands | the two delegated windows, bounds-checked and re-authorized against the revocation bit at each TDM grant (R-15-208) | a DMA descriptor the endpoint builds; a request issued under a window whose revocation bit is set at that grant; a window the endpoint widens |
| the configuration | the code and every schedule parameter declared configuration the composition supplies (R-15-228c) | a parameter the block negotiates, adapts, or latches from a frame |
| the origin | read from the frame-origin register in the clock spine, which the boot core kernel alone writes (R-15-196a) | **any write path from the endpoint to the frame-origin register**, to a launch instant, or to a guard band |
| the enable | the liveness of the link server's delegated window grant (R-15-146) | a software-writable enable bit; an enable the block asserts for itself |

R-12-007a permits no frame field containing a capability, either member's address or other authority. [§1](#1-the-frame-grammar) thus rules out peer-supplied transfer addresses at the field level; an endpoint mastering its own transfer would have to invent one.

### 5.3 Condition three: it runs to a stated bound and accumulates no state across operations

| Clause | Satisfied by | Falsified by |
| --- | --- | --- |
| the bound | one slot's bound is the whole of what the block runs to (R-15-228c) | an operation spanning two slots; a launch that waits on a landing |
| fixed latency | `T_enc` and `T_dec` fixed, the decoder run to `I_max` and never stopped early | an early-terminating decoder, whose latency carries the frame's correctability across the slot boundary into the schedule |
| no accumulated slot state | the slot index is a **function** of the spine's origin and `SLOT[i]`, computed each slot | a slot counter; a sequence counter; an epoch counter in the endpoint |
| no peer-derived state | nothing a received frame writes except the landing and `ARRIVAL_PHASE` (R-15-228c) | a retry buffer (A-18); a credit or acknowledgement tracker (A-19); a per-flow queue or arbiter (A-20); a FIFO level register; a landed flag |
| no loop | `ARRIVAL_PHASE` one-sided, read by software ([§3.5](#35-the-arrival-phase-reading)) | a phase accumulator; a latency estimator; any closed loop from a landing to a launch instant (A-21) |
| the one admitted carry | the equalization frozen per link epoch, which R-15-137's canceller already takes of this condition per epoch (R-15-228c); `EQ_READY` is that freeze's own validity and carries nothing else across a slot ([§3.2](#32-the-registers)) | equalization retrained inside an epoch, or adapted while traffic is in flight |

Every row must hold for R-04-010a classification; resemblance to an FEC decoder or PD sequencer is insufficient. The endpoint is outside R-04-010b's separate category: it holds neither a fixed model nor declared private retained state.

## 6. The netlist evidence an auditor searches for

The [absence contract](absence-contract.md) owns A-18 through A-21's grounds and evidence, with bindings in [synthesis provenance](../../rtl/synthesis-provenance.md). This table maps each row to the named [§3](#3-the-endpoints-register-description) and [§5](#5-r-04-010a-decided-clause-by-clause) structures whose presence falsifies it.

| Row | The structure whose presence falsifies it | Where a candidate would show it |
| --- | --- | --- |
| A-18 | a copy of a launched frame outliving its slot; a timeout counter; any register the launch path writes and a later slot reads | the transmit engine's window path, and any state between `TX_WINDOW_BIND` and the serializer |
| A-19 | a credit register; a ready, stall or back-pressure signal from the wire reaching the launch path; a landing that gates a launch | the path from the receive engine to the slot timer, which in an admissible block does not exist |
| A-20 | an arbiter; virtual-channel state; a per-flow queue; a FIFO deeper than [§3.4](#34-the-fifo-the-line-rate-and-why-the-link-adds-no-asynchronous-boundary)'s predicate admits, or one sized against a peer | the receive FIFO and everything between it and the receive window |
| A-21 | a phase accumulator; a latency estimator; a write path from the endpoint to the frame-origin register or to any launch instant; a leap path from an unverified landing; endpoint state a received frame updates beyond the landing and `ARRIVAL_PHASE` | `ARRIVAL_PHASE` and its fan-out, and the clock-data recovery, which is analog line-interface matter reaching no launch instant |

Q23g must discharge each row as authored RTL under R-15-092, using R-15-102's structural predicate over the block's Coq term in the refinement prover (R-15-228c). This contract specifies exclusions; the block must supply the predicate.

## 7. The link server's IDL interface

### 7.1 Where this declaration lives, and what it is waiting on

The link server is contained non-TCB software serving this member's sharded-function compartments (R-15-228b). Its world is specified here in prose because adding one to [the ring reference](../../interfaces/ring-reference.json) would fix R-12-091 and R-12-101's composition constants: `run.py ring emit` generates the Gallina artifact, K-89 binds its bytes, and the generated campaign checks consistency. Under `IDL-050`, this contract fixes no values before a measured roster exists. The item implementing the server owes the declaration, generated artifact, `IDL-064`'s three parts and R-18-037's conformance campaign.

### 7.2 The rings

Two ring instances, each declaring the composition-time constants R-12-091 enumerates as `IDL-050` requires, with **no value fixed here**: a request ring from the client compartment to the link server, and a completion ring back. The header is exactly the words R-12-091 names and carries nothing else, the count being that entry's and not this document's (`IDL-051`); indices are interpreted modulo the declared capacity with sequence information distinguishing full from empty, and no implementation infers validity from descriptor contents (`IDL-052`).

The request-ring capacity is a composition-fixed local constant in the generated interface artifact, unaffected by any frame, peer or wire. It is no credit or peer-varying endpoint queue under A-19/A-20; those exclusions do not forbid the software link server's rings (EL-1).

### 7.3 The operations

| Operation | What it carries | What its terminal completion means |
| --- | --- | --- |
| `send` | buffer references in the client's own session table, direction to the server, with R-12-092's bounded scalars and closed flag set | the bytes were placed in a transmit slot's frame and launched. **Never that a peer received them**: there is no acknowledgement to read, A-18 having deleted the structure that would carry one |
| `recv` | a pre-posted buffer reference, direction to the client, the extent validated before the transfer starts | a landed frame decoded, its tag verified by the crypto core, its descriptors validated against the per-link table, and its bytes copied into the posted buffer |
| `session_state` | no buffer reference; one bounded scalar selecting what is read | the link server's own view of the session epoch and whether the link is established, read from its own state and never from a peer |

`recv` is pre-posted rather than allocated on arrival, which is what keeps the receive path free of a queue that grows with a peer's traffic: a landing with no posted buffer is the overrun [§3.3](#33-the-two-window-contracts) states and not a backlog. Cancellation is `IDL-061`'s typed control-plane request and not a further operation of this interface. Zero-copy transfers execute only through a session-table capability whose permissions match the declared direction, with the complete extent validated before the transfer starts and never reinterpreted after (`IDL-063`).

### 7.4 The statuses, and how a link stop is represented

Statuses use R-12-093's closed common set and lifecycle meanings (`IDL-028`), with these event mappings:

| Event | How it is represented |
| --- | --- |
| a descriptor whose index, offset, length, direction, content type or generation fails validation against the per-link table | one of R-12-093's defined refusal completions, never a fallback interpretation (R-12-092, `IDL-054`) |
| submission against a full request ring | the sole typed result R-12-095 names, with no partial enqueue (`IDL-058`) |
| **a frame that fails its tag, an uncorrectable frame included** | **not a status.** The link fail-stops (R-15-228e), the session is torn down, and teardown is represented out of band by revocation plus a generation change, after which every formerly live request has R-12-093's own logical result for that case |
| re-establishment | a fresh session at `C_epoch`, never a resumption and never on demand (R-15-228e, R-12-015d); the new generation is live before any index is reused (`IDL-062`) |

Representing tag failure as a per-request status would permit client retries, contrary to R-15-228d's fixed schedule. R-17-030z instead requires the availability cost of stopping the link.

### 7.5 The two session tables, which are not one table

R-12-006 has descriptors name only indices into a per-session table of pre-delegated capabilities, and R-12-007a reads that table at the link as the **receiving** member's own per-link session table, delegated at composition to the receiving link server alone and revoked as any compartment's authority is.

A peer's frame indices select the receiving link server's per-link table. [§7.3](#73-the-operations)'s local interface indices select the client's per-session table. A frame index has no meaning on the sending member or in the receiving client-session table (R-12-007a); conflating the tables violates EL-3. A compromised authenticated peer is therefore bounded by the same table authority as the ring proof's Byzantine local peer (R-12-008).

## 8. What makes a candidate, a report, or an implementation inadmissible

| Id | The refusal |
| --- | --- |
| EL-1 | an endpoint holding a queue whose depth varies with a peer's activity, a retry, a credit or a sequence counter, **refused at review and never at RTL** (A-18 through A-20, R-15-228c). The link server's own ring capacity is not such a queue: it is a composition-fixed constant of the generated interface artifact (R-12-091), local to this member, and no frame changes it ([§7.2](#72-the-rings)) |
| EL-2 | a magnitude of [§4](#4-the-per-link-composition-constants) quoted as decided, or a pending row filled from an estimate, from a sibling document's illustration, or from a placeholder composition |
| EL-3 | a frame field admitting an address of either member, a capability encoding, a path, an executable name, a recursive value, an unbounded collection, or an index read against the wrong table (R-12-006, R-12-007a, R-12-092, `IDL-025`, [§7.5](#75-the-two-session-tables-which-are-not-one-table)) |
| EL-4 | an application payload or an origin leap enabled before establishment: a handshake or padding frame reaching any consumer but R-12-015d's bounded establishment handler, or a leap consuming a landing whose tag the crypto core has not verified |
| EL-5 | a frame delivered on the decoder's verdict, a syndrome or a CRC rather than on the tag, or a decoder that reports anything but decoded bits (R-15-228e) |
| EL-6 | an early-terminating decoder, or any encode or decode path whose latency is a function of the symbols or of whether the frame was correctable (R-15-119c, [§2.1](#21-the-selection-predicate)) |
| EL-7 | a second admissible code, ciphersuite, protocol version or configuration on one link, or a control plane holding a variable that selects among them (R-12-043a) |
| EL-8 | a public wire field selecting a regime, a handler or a key rather than being checked against the schedule and the session state; and any sender, address or persistent link-layer identifier field in any form (R-15-132, [§1.2](#12-the-four-forms-and-what-selects-between-them)) |
| EL-9 | a re-encode at a hop, a member forwarding a frame, or a header carrying a route (R-15-228e, R-02-003a) |
| EL-10 | a claim that this descriptor carries its R-05-051a canonicity theorem while [crown-jewel](../assurance/crown-jewels.md) row 10 records Narcissus descriptors and their checked derivations as absent ([§1.6](#16-the-no-slack-conditions-as-this-descriptors-own)) |
| EL-11 | an accept-and-ignore field, a reserved bit, a fill byte accepted without its check, or any value with a second admissible encoding (R-05-051b, [§1.6](#16-the-no-slack-conditions-as-this-descriptors-own)) |
| EL-12 | a `send` completion read as peer delivery, or any client behaviour conditioned on an acknowledgement this interface does not carry ([§7.3](#73-the-operations)) |
| EL-13 | an endpoint register outside [§3.2](#32-the-registers)'s table, a receive status or landed flag, a FIFO level register, a software-writable enable, or a write path from the endpoint to the frame-origin register ([§3.2](#32-the-registers), A-21) |

## 9. What this document leaves open, and to whom

| Owed | Who owes it |
| --- | --- |
| the descriptor's canonicity theorem and its Narcissus correctness pair | [crown-jewel](../assurance/crown-jewels.md) row 10, whose `partial` status records the inventory but no Narcissus descriptors; no descriptor exists in this repository for either to be stated against |
| the code's family, with its operand the wire's raw error rate at the declared reach and `M` | first measured at Q23g's two-member pair; [§2.3](#23-what-the-family-is-waiting-on) |
| `T_enc` and `T_dec` | R-17-041's magnitudes at [crown-jewel](../assurance/crown-jewels.md) row 15, measured at Q23g and entered in the devicetree fixture |
| `B_skew`, and the oscillator tolerances `D_fifo` and `C_leap` are derived from | measured on a two-member pair at qualification (R-15-196a); Q23g |
| every other row of [§4](#4-the-per-link-composition-constants) | the composition, emitted by Q23d with the ensemble schedule |
| [§7](#7-the-link-servers-idl-interface)'s world declaration and its generated interface artifact with R-18-037's campaign | the item that stands the link server up; [§7.1](#71-where-this-declaration-lives-and-what-it-is-waiting-on) says why it is not a second `interfaces/` world today |
| the session's reference model, its endpoint and key-compromise assumptions, and the binding between the quote's signing identity and the device-identity secret | Q23c, under R-12-015d and R-12-015c; R-17-049d records it open |
| the composed non-interference statement the [§5](#5-r-04-010a-decided-clause-by-clause) dispositions are eventually decided against | Q23f, under R-17-014a and R-17-003d |
| an R-09-007 Accept clause naming this class of declared per-link constants | **reported, not taken**; [§4.2](#42-one-declaration-this-contract-cannot-make-and-who-owes-it) names which rows an entry places by name and which rest on R-02-003a's general clause alone |

[Crown-jewel](../assurance/crown-jewels.md) row 10 remains `partial`: the inventory exists, while descriptors and checked derivations are absent. Adding this grammar to its specification cell supplies no Narcissus descriptor, parser proof or canonicity theorem. Any inventory-status change and resulting K-95 coverage repair belong to their owners.
