# The Ensemble Link Contract: Its Frames, Its Endpoint, and What Each Is Waiting On

> A gating artifact, governed by [R-15-228b through R-15-228e, R-12-007a, R-12-015d, R-11-017a and R-15-196a](../requirements-register.md).
> It states the frame grammar as a Narcissus descriptor, the link's code and its selection predicate, the endpoint's register description with every register's owner, the per-link composition constants with the artifact that carries each, R-04-010a's three conditions decided against the block clause by clause, the netlist evidence an auditor searches for, and the link server's IDL interface.
> Where this document and [the register](../requirements-register.md) disagree, the register wins and this document is defective.

## How to read this

R-02-003a admits an ensemble only when five artifacts exist, and this is the first of them: *the ensemble link contract stating the endpoint and the frame descriptor under R-15-228b through R-15-228e*. Three entries delegate to it by name rather than by description. R-15-228e sends the frame's code here, *this design's own and stated in the link contract*; R-15-119 repeats the delegation from the decoder's side and adds that the code owes no table to any standard, being between two copies of one design; and R-12-015d sends the handshake's *grammar, cryptographic checks and public fields* here. So the sections below are where those three sentences land, and nowhere else in this repository are they answered.

**What this document adds over the register is layout, field-level statement, and decision.** The register already fixes the frame's four forms, the code's discipline, the endpoint's absences, the two window contracts, the arrival-phase reading and the slot table's field set, and it fixes them in prose the review gate audits. A paragraph here that only re-says one of those is a defect under the corpus rule that a fact has one owner (R-05-152), so this document cites instead, and what it authors is the field order, the admissible length forms, the per-register ownership, the clause-by-clause sorting, the refusals, and the arithmetic three sibling items read.

**What this document refuses is every magnitude.** R-15-228d makes the frame count and frame size per-link composition constants of the attested schedule artifact; R-11-017a makes the slot instants, guard bands and leap cadence entries of that same artifact; R-17-041 owns the latency magnitudes, at [crown-jewel](../assurance/crown-jewels.md) row 15, which reads `not authored`; and R-15-196a has the skew bound measured on a two-member pair at qualification. No composition in this tree fixes any of them. §4 therefore carries one row per constant with its unit, its admissibility predicate and its owner, and carries no number. A reader of §4 who wants a figure is reading the wrong artifact, and §8's EL-2 is the refusal that says so.

**The code's family is owed rather than chosen.** R-15-228e admits either of R-15-119's two families and requires this document to state which. The operand that decides it is the wire's raw error rate at the declared reach and frame length, which nothing in this tree supplies, and Q23g's two-member pair is the first measurement named. §2 therefore states the selection predicate in full and records the family as owed with its operand named, so that the measurement decides it mechanically rather than confirming a choice already written. Stating one of the two families here would be a design decision resting on no measurement, and would be EL-2 against this document's own refusal table.

## 1. The frame grammar

### 1.1 The two layers, and which one the descriptor is over

A frame on the wire is one codeword of the link's code (R-15-228e). **The descriptor's language is the decoded message block and never the wire symbols.** The encoder produces the parity symbols and the decoder strips them, neither reads a field, and no parser sees a symbol. What that separation buys is exact and no more: the code's output is bits, the grammar's input is bits, and no decode outcome reaches a field, so the verdict register R-15-228e refuses would have no consumer in this grammar even if a candidate block carried one. **The absence of the register itself is R-15-228e's rule and not this structure's consequence**, and EL-5 is where this document refuses it.

Every frame form occupies exactly `M` bytes of message block, `M` being the code's message length and a composition constant of §4. There is therefore no frame-length field in any form, no length to bound, and one admissible length form at the frame level by construction, which is the first of R-05-051b's no-slack conditions met without a clause.

### 1.2 The four forms, and what selects between them

| Id | Form | Regime | Carried in |
| --- | --- | --- | --- |
| `FF-1` | established-session payload frame | established | any established-session slot the table grants, where the link server has payload |
| `FF-2` | authenticated idle frame | established | every other established-session slot (R-15-228d) |
| `FF-3` | scheduled handshake frame | unestablished | the composition-reserved establishment slots (R-12-015d) |
| `FF-4` | unestablished-slot public padding | unestablished | every other enabled slot before establishment (R-15-228d) |

**The wire selects nothing.** Which regime applies is the receiving member's own session state; which slot a frame arrived in is the receiving member's own table read against its own origin; which handshake step is expected is the reserved slot's, at the composition-fixed cadence R-12-015d names. Every discriminant a frame carries is therefore **checked against what the schedule and the session state already say**, and never read to select a handler, a key, or a regime. A mismatch is an eligibility refusal taken after the parse, not a decode failure taken during it, which keeps the descriptor a total function of the bytes alone and keeps canonicity a property of one language rather than of a language indexed by the receiver's state.

That split is the whole of *separating bounded handshake parsing from application-payload eligibility*. The parse is a fixed walk over fixed-width fields into a fixed destination buffer (R-05-124), so its cost is a function of `M` and of nothing in the bytes; eligibility is decided afterward, in the established regime only, and by the receiving link server against its own per-link session table (R-12-007a). Nothing a handshake frame parses to can make a payload eligible, because the eligibility decision is not reachable from the unestablished regime at all.

### 1.3 `FF-1` and `FF-2`, the established-session message block

The two forms share their public shape exactly, which is R-15-228d's requirement that an idle frame be indistinguishable on the wire from a payload frame except by a type field read after the crypto core has decrypted and authenticated it. The type field is accordingly **inside** the sealed body and there is no public discriminant in this regime at all.

| Order | Field | Kind | Length | Public before the tag verifies | Read by |
| --- | --- | --- | --- | --- | --- |
| 1 | `sealed_body` | opaque bytes | `M - L_tag` | no | the crypto core, which decrypts it (R-05-070, R-15-202) |
| 2 | `tag` | opaque bytes | `L_tag` | as bytes, and it names nothing | the crypto core, which verifies it before any field below is read |

The associated data the tag covers is **not on the wire**: it is the link, the session epoch, and the schedule's own count of that link's slots since the epoch began, a value R-12-015d has both ends derive from the schedule and neither from the wire. So this form carries no sequence number, no epoch field, no session identifier and no sender field, and R-15-132 stays unmoved as R-12-015d reads it. An adversary cannot supply any of the three, and a frame displaced into another slot fails its tag rather than being detected by a counter.

The plaintext body, which the verified copy-once parser reads only after the tag verifies:

| Order | Field | Kind | Length | Read by |
| --- | --- | --- | --- | --- |
| 1 | `body_kind` | `WF-7` enum over exactly two cases, `payload` and `idle` | the discriminant width `IDL-023` fixes for two cases | the receiving link server |
| 2 | `descriptor_count` | `WF-5` count, admissible values `0` through `N_desc_max` | `w_count`, the width `IDL-023` fixes for that bound | the receiving link server |
| 3 | `descriptors[i]` | R-12-092's descriptor, each member encoded by the row of [the IDL profile](../languages/idl-profile.md)'s encoding table that `IDL-053` names for its kind | `S_desc` each, `N_desc_max * S_desc` in all | the receiving link server, which validates every one against its own per-link table before any becomes eligible |
| 4 | `payload_region` | opaque bytes, indexed by the descriptors' offsets and lengths | `P_bytes` | the receiving compartment, after validation and after the link server's copy |

**The four rows exhaust `M - L_tag` exactly**, and §4's arithmetic is what makes that true rather than a trailing fill rule. A `descriptor` slot above `descriptor_count`, and every byte of `payload_region` no admitted descriptor's offset and length covers, is a **declared zero fill** on `IDL-024`'s terms: a fill byte that is not zero is a decode failure, so the fill carries no value and is not the free padding R-05-051b forbids. The `idle` case of `body_kind` admits `descriptor_count` zero alone, which makes rows 3 and 4 entirely fill, so `FF-2` is `FF-1` with an empty descriptor list and a zero payload region, encoded to the same length by the same rule.

### 1.4 `FF-3`, the scheduled handshake frame

No session exists, so no session tag covers this form. Its integrity is the construction's own, inside `step_payload`, and **this document authors none of it**: R-12-015a's sealing service brokers the credential operations as schema-bounded requests returning only the protocol result, and R-12-015d's reference model, owed at Q23c, states the relation. What is authored here is the grammar, which is what R-12-015d delegates.

| Order | Field | Kind | Length | Public before the tag verifies | Read by |
| --- | --- | --- | --- | --- | --- |
| 1 | `form` | `WF-7` enum over exactly two cases, `handshake` and `padding` | the discriminant width `IDL-023` fixes for two cases | n/a, no tag exists in this regime | the bounded parse |
| 2 | `step` | `WF-7` enum over R-12-015d's finite step set | the discriminant width `IDL-023` fixes for that set | yes | checked against the reserved slot's step, then R-12-015d's bounded establishment handler |
| 3 | `step_payload` | opaque bytes, the construction's | `H_step(s)` for the decoded step `s`, the remainder of the block a declared zero fill on `IDL-024`'s terms | yes | R-12-015d's bounded establishment handler alone |

**The one consumer this form reaches is that handler.** Nothing else is on the path: not the receiving compartment, not the payload-eligibility decision, not the leap. That is R-15-228b's *establishment traffic reaches only R-12-015d's bounded handler* read as a reachability property of this grammar rather than as a policy, and EL-4 is the refusal that holds it.

Every field of this form is public, which is stated rather than conceded: the hybrid key establishment's shares, the two fresh challenges, the attestation evidence and the slot-table digest each end binds are public by construction, so no field of `FF-3` carries a value whose disclosure the design depends on. What the form does not carry is equally exact: no address, no capability encoding, no persistent link-layer address and no sender field, the peer's identity being attestation evidence the session construction processes and never a header field (R-15-132, R-12-015d).

### 1.5 `FF-4`, unestablished-slot public padding

| Order | Field | Kind | Length | Public before the tag verifies | Read by |
| --- | --- | --- | --- | --- | --- |
| 1 | `form` | `WF-7` enum, the `padding` case | the discriminant width `IDL-023` fixes for two cases | n/a, no tag exists in this regime | the bounded parse |
| 2 | `fill` | the declared constant `F_pad`, repeated | the remainder of the block | yes | nothing |

**`fill` is checked and then discarded, and the check is the point.** A byte that is not `F_pad` is a decode failure. An unchecked fill would be exactly the accept-and-ignore field R-05-051b forbids, and it would let a wire adversary place chosen bytes into an unestablished slot and have them retained somewhere on this member. Checking costs one fixed comparison over a fixed length and closes that reading; nothing downstream of the check reads this form at all, which is what makes *neither eligible as application traffic or a leap input* structural here rather than enforced.

### 1.6 The no-slack conditions, as this descriptor's own

R-05-051b's conditions are stated here as properties of the four forms rather than cited, because the register states them of descriptors in general and this is the place they are decided of this one.

| Condition | How this descriptor meets it |
| --- | --- |
| one admissible length form | every form is `M` bytes, and no field of the frame format bounds another field's extent except `descriptor_count`, whose width `IDL-023`'s ladder fixes from `N_desc_max` alone. A buffer reference inside a descriptor does carry an offset and a length (`WF-11`, R-12-092), each a fixed-width scalar inside the descriptor's own fixed size, and neither selects an extent on this member: nothing a reference names becomes eligible until the receiving link server has validated it against its own per-link table (`IDL-054`, R-12-007a) |
| one presence encoding per optional field | the only optional member is R-12-092's deadline, encoded by `WF-8` inside the descriptor; no second presence encoding exists in any form |
| fixed field order | the order is the `Order` column of §1.3 through §1.5, and it is a property of the form and not of the values |
| no free padding, no reserved bits | every fill byte is declared and checked, `FF-1` and `FF-2` to zero on `IDL-024`'s terms and `FF-4` to `F_pad`, which is what keeps none of them the free padding this condition forbids; the descriptor's flag set is `WF-10`, where a set bit above the declared count is a decode failure |
| no accept-and-ignore field | every field above names a reader, and the two that name none, the fills, are decode failures when they differ from their declared value |
| a non-canonical input fails rather than normalizing | the parse is total over the bytes and produces a value or a failure; no path rewrites an input into the canonical encoding of the same value |

**The canonicity theorem R-05-051a requires is OWED.** It is owed and not deferred: the tag is computed over the frame's encoding, and each end binds the digest of its slot table into the session context, so this descriptor's encoding is an input to a signature and to an equality test and R-05-051a reaches it squarely. What owes it is [crown-jewel](../assurance/crown-jewels.md) row 10, the wire-format inventory and its Narcissus descriptors, whose status is `not authored`: no Narcissus descriptor is authored anywhere in this repository, so there is no artifact for a Coq-checked injectivity theorem to be stated against. §1 enters this descriptor in that row's specification cell as a member under R-05-046; the theorem lands when the row does. A claim that this descriptor carries its canonicity theorem while that row reads `not authored` is EL-10.

## 2. The link's code

### 2.1 The selection predicate

A candidate code is admissible for a link exactly when every clause holds. The clauses are what R-15-228e, R-15-119, R-15-119c and R-12-043a decide between them, collected here because the selection is made against all of them at once or not at all.

| # | Clause | Why it is here |
| --- | --- | --- |
| 1 | fixed geometry: one message length `M`, one codeword length `N`, one rate, no puncturing or rate matching chosen at run time | R-15-228e's *fixed-geometry block code* |
| 2 | one codeword is one frame, and one frame is one codeword | R-15-228e; it is what makes §1.1's two layers separable |
| 3 | a deterministic iteration bound `I_max`, run to the bound and never stopped early | R-15-119's bound and R-15-119c's discipline, read at this device rather than at the ISA unit |
| 4 | decode latency independent of the symbols and of whether the frame was correctable | R-15-119c; an early-terminating decoder reports correctability in its latency |
| 5 | no verdict register, no syndrome and no CRC decides a frame; the decoder reports the decoded bits and nothing else | R-15-228e, on R-15-119b's ground for declining the verdict register at the ISA surface |
| 6 | no re-encode at any hop | R-15-228e, R-15-176's chain ending at each member's edge |
| 7 | no rate adaptation, no feedback from the peer, no hybrid retransmission | each is a retry or a credit, which A-18 and A-19 already exclude from the endpoint |
| 8 | exactly one admissible code per link, fixed at composition | R-12-043a's one-configuration discipline read at the code |
| 9 | the family is one of R-15-119's two, and the link's code is this design's own | R-15-228e, R-15-119, which adds that it owes no table to any standard |

Clause 8 is the one that is easiest to lose, because a code family naturally carries a parameter set. **A link declares one code and no control plane holds a variable selecting a second**, exactly as no control plane holds a variable selecting a ciphersuite. Two links of one ensemble may declare different codes, each fixed at its own composition; one link may not.

### 2.2 The two latency rows

The encoder and the decoder are stages of a device datapath, so each is an entry in **the endpoint's own device row** of the timing-annotated model and neither is a third entry of R-15-119c's two ISA rows. R-15-119 states that division from the other side and this document records the consequence: the member's admission check charges `T_enc` in the transmitting endpoint's slot and `T_dec` in the receiving endpoint's. What enters the member's R-11-006 interval arithmetic as ordinary tasks and grants is R-11-017a's own list, the link server's slots, the endpoint's encode and decode latencies, the crypto core's per-frame operations, and the endpoint's window grants, the last of those being the two window contracts §3.3 states.

`T_enc` and `T_dec` are magnitudes, so they are R-17-041's and not this document's, exactly as every other row's are. Both appear in §4 with no number.

### 2.3 What the family is waiting on

The selection predicate above admits both of R-15-119's families. Nothing in it separates them, because the clauses are all structural and both families satisfy every one at a suitable geometry. **What separates them is a measurement nobody has taken**: the decode latency each family needs, at the link's declared frame length and at a target residual frame error rate, given the wire's raw error rate at the declared reach. The frame length is itself an unfixed composition constant, the reach is a cable and connector question none of the five artifacts R-02-003a gates on buys, and the raw error rate is a physical measurement of a medium this tree does not name.

The first measurement named anywhere is Q23g's, a two-member pair on two FPGA instances of the R-18-005 scalar class carrying the endpoint block. **The family is therefore recorded as owed, with its operand named and its owner named**, and §4's `code_family` row carries it. What this document fixes today is that the choice is made once per link at composition against the predicate of §2.1 and against nothing else, so whichever family the measurement selects changes no clause above and no field of §1.

### Research handoff for the unselected code

Q23g's future selection can consult the [code and decoder proof handoff](../assurance/proof-reuse/hardware.md#research-handoff-for-future-code-and-decoder-proofs), which routes the survey's binary rate-distance bounds, folded/ordinary Reed-Solomon decoding and scratch-space advances to concrete finite proof obligations. The inspected formal improvement to the asymptotic binary-code upper bound is a constraint on a rate-distance frontier, not a finite code or decoder. Those results do not select one of the admitted families, establish the wire's error model or implement the decoded-bits-only interface. A list decoder with several candidates and authenticated selection is a different interface until a reviewed construction proves it satisfies every clause of §2.1. VT deletion correction and the seven-cycle zero-error construction have no identified matching channel here.

The [communication proof handoff](../assurance/proof-reuse/protocols.md#research-handoff-for-future-communication-proofs) separately routes log-rank and Li-Li to possible future Q23d/Q23h comparisons. Neither licenses shorter unpadded transcripts, network coding, new forwarding behavior or lower reserved traffic in this point-to-point contract. These research notes supply no missing magnitude, new acceptance clause or completion evidence.

## 3. The endpoint's register description

### 3.1 What is a register of this endpoint and what is not

Three structures a reader expects to find here are owned elsewhere, and naming them is the first half of *every register with its ownership*.

| Structure | Whose it is | Why it is not the endpoint's |
| --- | --- | --- |
| the two delegated window capabilities | the owning island's memory controller, in the fabric-side window registers R-15-208 places there | R-15-208 puts the delegated capability in a fabric-side register re-authorized at the start of each TDM grant against the island's R-08-005a revocation bit; the endpoint carries no capability-bearing register, so R-12-007's *mapped without capability-store permission* is structural at this block and what the endpoint lands is untagged bytes (R-12-007a) |
| the frame-origin register | the clock spine (R-15-195, R-15-196a) | it is the platform-wide origin every core's boundary handler, the memory controller's TDM arbiter and each window's grant read as a common zero, stepped by exactly one kernel instance, the boot core's, under a capability the composition grants to it alone; **the endpoint has no write path to it at all**, which is what A-21's search reads |
| the session keys, the cipher, and the tag | the crypto core (R-05-070, R-15-202) | R-15-228c has the endpoint hold no key and no cipher, so no key register, no nonce register and no tag-verify result register exists here |

**The engines hold their windows in the sense R-15-228c states and the register mechanism is R-15-208's.** The endpoint's configuration carries a window index naming which fabric-side window each engine issues against, and that index is neither an address nor a capability. This is a reading taken here rather than a sentence read out of either entry, because R-15-228c says the engine holds the capability and R-15-208 says the capability is held fabric-side; the reconciliation is that R-15-208 is the specific mechanism and R-15-228c the ownership, and a reviewer who reads it the other way should say so against this paragraph.

### 3.2 The registers

**The `Owner` column names the party whose direction the `Access` column states**, `RW` and `RO` being that party's own direction, and any access a second party holds is stated in the description cell rather than in either column; a direction no party holds faults, and so does every offset this table does not admit. The offsets themselves are composition constants and are not stated here: an MMIO aperture's placement is a stated constraint on the attested devicetree (R-15-002b, R-09-007), and no entry of the register assigns an offset inside that aperture to any register of this table, which is a declaration owed on the same ground §4.2 reports for the link's other constants.

| Name | Owner | Access | What it is, and what it is not |
| --- | --- | --- | --- |
| `SLOT[i]` | the link server compartment, as configuration MMIO | `RW` while the grant is live | one entry of R-11-017a's link slot table for this endpoint: the slot's instant against the member's own origin, its direction, and its guard band. Core-issued software loads it from the admission artifact's fourth output; no runtime exchange establishes or amends it |
| `TX_WINDOW_BIND` | the link server compartment, as configuration MMIO | `RW` while the grant is live | the index of the fabric-side window register the transmit engine issues against. Carries no address and no capability; cleared when the grant is revoked |
| `RX_WINDOW_BIND` | the link server compartment, as configuration MMIO | `RW` while the grant is live | the same for the receive engine |
| `EQ_READY` | the endpoint's line interface | write, at link-up and at link-down and at no other instant | whether the current link epoch's equalization training has completed, which is the frozen store's own validity and nothing else. The link server reads it `RO` and no software writes it. **It holds no epoch number**: which link epoch is in force is the link server's own state, read through §7.3's `session_state`, and the endpoint holds no epoch counter |
| `EQ_COEF[j]` | the RoT | write, cleared on link-down | the equalization coefficients, trained at link-up and frozen for the epoch on R-15-137's terms (R-15-228c). The link server neither reads nor writes it |
| `ARRIVAL_PHASE` | the endpoint | write, on the landing in the slot named for the leap | the one-sided arrival-phase reading of the most recent landing in the slot this endpoint's table names for the leap (R-15-196a). Holds one reading and no history, no accumulator and no estimator. It is `RO` to all software, and the boot core kernel's leap path is its one reader |

**That is the whole set**, and the absences are as much of the description as the rows. There is no receive status register and no landed flag, because R-15-228c admits no state a received frame writes except the landing itself and the arrival-phase reading; **the schedule and not a flag tells the link server when to read a receive entry**, which is the same non-work-conserving discipline the table already keeps (R-15-228d). `EQ_READY` is not such a flag: the link's training phase writes it and nothing a frame does reaches it. There is no FIFO level register, a level being state the wire's timing writes. There is no enable bit, the endpoint being electronically enabled by the liveness of the link server's delegated window grant and by no software claim (R-15-146, R-15-228c). There is no software-writable equalization path, and no coefficient is retrained inside an epoch.

The code's geometry is not a register either, and its absence from the table is a statement rather than an omission. `M`, `N`, `I_max` and the family are **synthesis-time parameters of the block**, so R-15-228c's *declared configuration the composition supplies* is read at synthesis for them and at `SLOT[i]` and the two window binds for the schedule. What binds such a parameter to a build is the form [the synthesis provenance record](../../rtl/synthesis-provenance.md) already keeps, one row per absence naming the parameter values that remove it; that record carries A-18 through A-21 as `n/a` today because the endpoint is net-new authored RTL rather than a configuration of an imported core, so the endpoint's own provenance rows are owed with the block and not with this contract.

There is also **no slot counter**. The slot a launch or a landing belongs to is a function of the spine's origin and of `SLOT[i]`, computed rather than accumulated, which is precisely what R-04-010a's third condition asks of the block and what §5.3 decides against it. The monotone count of slots since the epoch began, which R-12-015d makes the frame's associated data, is the link server's and the crypto core's to derive from the same two inputs; putting it in the endpoint would be the sequence counter EL-1 refuses.

`EQ_COEF[j]` sits in the RoT's aperture and not in the link server's, so R-15-143's indivisible ownership is over the configuration MMIO and the two windows, and the coefficient store is neither. **That placement is this contract's decision and not a deduction from the two entries.** The other placement is compatible with both: R-15-137 has the coefficients trained at link-up and then frozen for the epoch, and a store frozen for the epoch cannot be moved by whoever holds the aperture while traffic is in flight, so a coefficient store inside the ownership R-15-143 binds would satisfy R-15-137 as well. The separation is taken as the stronger of the two readings because it removes the control rather than timing it: a reviewer checking the weaker reading has to check that the freeze holds against every path that could write the store, and a reviewer checking this one has to check an ownership boundary. A reviewer who prefers the weaker reading should say so against this paragraph.

### 3.3 The two window contracts

The engines are R-15-206's second shape, autonomous streaming engines holding delegated, bounds-checked, revocable window capabilities for the lifetime of their windows, into ring regions of the endpoint's island (R-15-223, R-15-228c). Both windows carry every clause below, and only the last differs.

| Clause | Transmit window | Receive window |
| --- | --- | --- |
| the capability | delegated, bounds-checked, revocable, held fabric-side (§3.1) | the same |
| store permission | absent, so what the engine reads is untagged bytes (R-12-007) | absent, so what the engine lands is untagged bytes (R-12-007a) |
| revocation | the bit at the window capability's base is read from the island's R-08-005a array at the start of each TDM grant of that window, and no request of that grant issues when it is set (R-15-208) | the same |
| teardown | R-15-208a's completion boundary, so a torn-down link leaves no engine authorized past the next grant (R-15-228c) | the same |
| ownership | indivisible with the configuration MMIO, granted and revoked together, held by the link server compartment alone (R-15-143) | the same |
| occupancy | one frame per slot, the slot's own entry, placed by the link server before the launch instant | **at most one frame per slot** (R-12-015d), landed in the entry the slot names |

The receive side's clause is the one that differs because it is the one an adversary reaches. R-12-015d admits at most one frame per slot, so a peer or a wire cannot land two, and a link server that does not drain a receive entry before the schedule lands on it again is that partition's overrun, restarted by R-07-040 and reaching no other partition's slot (R-15-228c). **Neither window's extent is a function of anything a peer does**: both are composition constants of §4, and a window that grew or shrank with traffic would be the peer-varying depth EL-1 refuses.

### 3.4 The FIFO, the line rate, and why the link adds no asynchronous boundary

The recovered line clock is one of R-15-196's three external interface clocks and terminates in the endpoint's bounded FIFO of depth `D_fifo`, with the fabric side on the island clock (R-15-196a). **R-15-196's count of three is unmoved by class membership and by nothing else**: its Accept clause reads an ensemble link's recovered line clock as one of the external interface clocks, terminating as they do, so the link adds one more member to a class already counted and no new class. Nothing about where the FIFO sits enters that.

**The FIFO is on the receive path alone**, the transmit serializer running off the member's own clock. That is this document's own statement in the voice §3.2 uses for the readings it takes, no entry fixing the transmit path's clock domain; what it decides is which path carries a FIFO, and not the count above.

`D_fifo` is admissible exactly when it absorbs the declared frequency difference between the recovered line clock and the island clock across one frame at `M` and `N`, and no deeper. **It is not a queue in A-20's sense**, and the distinction is what makes the row decidable: its depth is a function of two declared oscillator tolerances and one frame length, all three composition constants, and of no peer's activity, no credit, no retry and no sequence. A FIFO sized to hold more than one frame, or sized against a peer's behaviour, is the structure A-20's search would find.

`R_line` carries two predicates at once and both bind: R-15-196 lets an external interface clock contribute a line-rate bound to the member's bandwidth reservation and nothing else, and R-12-015d's second Accept clause caps it at the crypto core's authenticated-encryption throughput. What this document decides is the consequence for a candidate composition: a declared `R_line` above that ceiling is inadmissible at composition and not a degraded mode, there being no rate to fall back to on a link that declares one code and one schedule.

### 3.5 The arrival-phase reading

`ARRIVAL_PHASE` is updated by the landing of the leader link's frame in the slot the table names for the leap. It is **one-sided**: it is a reading of when a landing occurred against the member's own origin, not a two-sided estimate of the peer's offset, and the endpoint holds no loop that would close over it (A-21).

**The endpoint cannot gate the reading on verification and does not try to.** It holds no key and no cipher, so it cannot know whether the frame that produced a reading will verify. What gates the leap is the consumer: the boot core kernel reads `ARRIVAL_PHASE` only after the crypto core has verified that frame's tag in its own slot, and a slot whose frame failed its tag yields no leap (R-15-196a). So the reading is updated by landings the crypto core later rejects, and the leap is not, and the register description must say which of the two the verification gates, or a reader will look for the gate in the wrong block.

What this leaves an adversary is exactly what R-17-025a books and no more: a wire adversary delaying a genuine frame within its accepted slot, or a compromised leader, can walk a follower's origin by at most the skew bound per cadence inside the guard band. A frame displaced outside its accepted slot fails its tag and stops the link (R-17-030z). The tag does not authenticate the arrival instant within a slot, which R-17-025a states and this register's one-sidedness is the structural half of.

### 3.6 The slot-table register format

`SLOT[i]` carries R-11-017a's own field set for one slot and carries nothing else.

| Field | Kind | What decides it |
| --- | --- | --- |
| instant | the slot's start in the member's own spine cycles against the member's own origin (R-11-014a) | the ensemble schedule, emitted by the one composition act |
| direction | transmit or receive | the same |
| guard band | the slot's guard band, admissible only at or above the composition's skew bound plus this link's latency bound (R-11-017a) | the same |

Every slot of a link carries the link's one frame length, so **no per-slot length field exists**, which is R-15-228d's fixed frame size read as an absence in the table rather than as a constraint on its values. The leap slot is not an entry of this table: it is a kernel-owned idle window the executive reserves on every core of the member at the same absolute instant, which R-11-017a places in the member's artifact and not in an endpoint's register. The digest of this table is what each end binds into the session's context at establishment (R-12-015d, R-11-017a), so a table one end does not hold refuses the session rather than corrupting a slot.

## 4. The per-link composition constants

One row per quantity, with the predicate that makes a value admissible and the artifact that carries and emits it. **Every row is pending and carries no number**, for the reason the reading note above states: no composition in this tree fixes any of them, and a figure written here would be the placeholder EL-2 refuses.

**Three carriers appear in the last column and they do not rest on equal authority**, which §4.2 is where the difference is reported. *The attested schedule artifact* carries the rows R-11-017a and R-15-228d put there by name: the slot tables, every slot's instant, direction and guard band, the leap cadence, and the link's one frame length. *The attested devicetree* carries the skew bound and the link's latency constants by name (R-15-196a) and the ensemble's membership, endpoints, leader ends and expected identities by name (R-02-003a); every other row marked with it rests on R-02-003a's general clause that every constant of an ensemble is carried in every member's attested devicetree, a clause that names none of these constants and whose enumeration R-09-007's own list does not carry. *§7's declaration* carries what the generated interface artifact fixes.

| Symbol | Quantity | Unit | Admissibility predicate | Decided by | Carried and emitted by |
| --- | --- | --- | --- | --- | --- |
| `M` | code message length, one frame's message block | bytes | equals `L_tag` plus the sum of §1.3's plaintext body; the same for all four forms | the composition (R-15-228d) | the attested schedule artifact, every slot of a link carrying the link's one frame length (R-15-228d, R-11-017a); Q23d |
| `N` | codeword length | symbols | fixed geometry at the declared rate; `M` maps to it under one code (R-15-228e) | the composition | the attested devicetree; Q23d |
| `code_family` | LDPC or polar | n/a | every clause of §2.1, then the lower decode latency at the target residual frame error rate | **owed**; operand is the wire's raw error rate at the declared reach and `M` | first measured at Q23g |
| `I_max` | decoder iteration bound | iterations | deterministic, run to the bound, never stopped early (R-15-119c) | the composition | the attested devicetree; Q23d |
| `L_tag` | authentication tag | bytes | the one admissible configuration R-12-043a fixes for the session's construction | R-12-015d's construction | the attested devicetree |
| `S_desc` | descriptor size of the link interface | bytes | one size for every variant of the closed descriptor variant (`IDL-024`, R-12-091) | the generated interface artifact | §7's declaration |
| `N_desc_max` | descriptors per payload frame | count | `L_tag + d_kind + w_count + N_desc_max * S_desc` does not exceed `M`, leaving `P_bytes` at or above the link's declared minimum payload | the composition | §7's declaration |
| `P_bytes` | payload region of a payload frame | bytes | `M - L_tag` less §1.3's discriminant, count and descriptor array | derived, see §4.1 | derived |
| `H_step(s)` | handshake step payload, per step | bytes | at most `M` less §1.4's two discriminants; the remainder is declared zero fill | R-12-015d's construction | Q23c's reference model |
| `F_pad` | the padding fill value | byte | one value; any other byte is a decode failure | the composition | the attested devicetree |
| `D_fifo` | receive FIFO depth | entries | absorbs the two declared oscillator tolerances across one frame, and no deeper (§3.4) | the composition | the attested devicetree; Q23g measures the tolerance it is derived from |
| `R_line` | line rate | bits per second | at or below the crypto core's authenticated-encryption throughput (R-12-015d); contributes the line-rate bound to the member's reservation (R-15-196) | the composition | the attested devicetree |
| `T_enc` | encode latency | cycles | fixed, independent of the symbols (§2.2) | **owed**; R-17-041's magnitudes, [crown-jewel](../assurance/crown-jewels.md) row 15 | measured at Q23g; entered in the attested devicetree by name as one of the link's latency constants (R-15-196a) |
| `T_dec` | decode latency | cycles | fixed, independent of the symbols and of correctability (§2.2) | **owed**; the same | the same |
| `T_slot` | slot period of this link | spine cycles | the table's own, one frame per slot (R-15-228d) | the ensemble schedule | the attested schedule artifact (R-11-017a); Q23d |
| `G_band` | guard band, per slot | spine cycles | at or above `B_skew` plus this link's latency bound (R-11-017a) | the ensemble schedule | the attested schedule artifact (R-11-017a); Q23d |
| `C_leap` | re-alignment cadence on the leader link | slots | `C_leap` times both members' declared oscillator tolerance lies inside `G_band` (R-11-017a) | the ensemble schedule | the attested schedule artifact (R-11-017a); Q23d |
| `B_skew` | skew bound between two members' origins | spine cycles | **owed**; measured on a two-member pair at qualification, a pair exceeding it failing to qualify rather than leaping more often (R-15-196a) | measured at Q23g | the attested devicetree, beside the link's latency constants and by name (R-15-196a) |
| `C_epoch` | re-establishment cadence | slots | composition-fixed, never on demand (R-12-015d, R-15-228e) | the composition | the attested devicetree |
| `W_tx`, `W_rx` | the two window extents | bytes | a ring region of the endpoint's island (R-15-223); one frame per slot in `W_rx` (R-12-015d) | the composition | the attested devicetree |
| `N_eq` | equalization coefficient count | count | frozen for the epoch, cleared on link-down (R-15-137) | the composition | the attested devicetree |

### 4.1 The arithmetic, which is what a sibling item can read

Q23e's Start line asks for *Q23b's frame size*. **What this document can hand it is the size's arithmetic and these parameter names, and not a figure**, because R-15-228d makes the frame size a per-link composition constant and no composition fixes one. Reading a placeholder out of §4 would be worse than reading nothing, so §4 has none.

The arithmetic, over §1.3's field list:

- `P_bytes = M - L_tag - d_kind - w_count - N_desc_max * S_desc`, where `d_kind` and `w_count` are the widths `IDL-023`'s ladder fixes for two cases and for `N_desc_max`.
- The useful bytes a payload frame moves are `P_bytes`, and not `M`: the tag, the discriminant, the count and the unused descriptor slots are carried in every frame whether or not they are used, which is the same non-work-conserving price R-15-228d already charges for the idle frame.
- Frames per step on one link are the bytes that step exchanges over that link divided by `P_bytes`, rounded up, and the slot tables must grant at least that many transmit slots per step or the sharding is refused at composition (R-15-171a).
- Wire symbols per step are that frame count times `N`, which is what `R_line` is checked against.
- The per-frame charge on the member's admission is `T_enc` or `T_dec` in the endpoint's slot, the crypto core's authenticated-encryption operation over `M` in its slot, and the link server's validation and copy in its own (R-11-017a).

Every term above but the two discriminant widths is a row of §4, and every one of those rows is pending, so the arithmetic evaluates to nothing today. Of the two widths, `d_kind` is one byte, `IDL-023`'s ladder fixing the smallest of one, two or four bytes that holds a two-case count, and `w_count` follows `N_desc_max` and is pending with it. That is the honest state and it is the useful one: a consumer cites a row rather than a sentence, and a row that acquires a value moves every figure derived from it.

### 4.2 One declaration this contract cannot make, and who owes it

R-09-007's list of what the static devicetree declares names core classes, islands, the NoC schedule, OPP tables and radio calibration, and it gained one explicit Accept clause for the inference socket's declared constants under R-15-228h. **The ensemble link's per-link constants are not named in that list**, and §4's carrier column is the place a reader meets the consequence.

Three entries name a carrier for part of the table and the rest rests on a general clause. R-11-017a makes the slot tables entries of the attested schedule artifact and public constants of the generation, which is `T_slot`, `G_band`, `C_leap` and, with R-15-228d, `M`. R-15-196a has the skew bound and the link's latency constants entered in the attested devicetree at qualification, which is `B_skew`, `T_enc` and `T_dec`. R-02-003a carries the membership, each link's endpoints, each link's leader end and each peer's expected unit and ensemble identity in every member's attested devicetree, and it opens with a general clause that **every** constant of an ensemble is carried there. **The remaining rows rest on that general clause alone.** `N`, `I_max`, `L_tag`, `F_pad`, `D_fifo`, `R_line`, `C_epoch`, `W_tx`, `W_rx` and `N_eq` are carried in the attested devicetree because they are constants of an ensemble and for no more specific reason, no entry naming any of them and R-09-007's own enumeration of what that tree declares reaching none of them. That the general clause is not read as exhaustive is visible inside the register: `M` is a constant of an ensemble too, and R-15-228d puts it in a different artifact by name.

Whether R-09-007 owes an Accept clause naming this second class of declared constants, on the precedent of the one R-15-228h already earned there, is **a register act this document reports and does not take**. Until it is taken, a reader comparing R-09-007's list against §4's table finds the rows named above carrying an artifact read off a general clause rather than declared, and that, and not a settled answer, is what this section records.

## 5. R-04-010a, decided clause by clause

R-15-228c sorts the endpoint as matter under R-04-010a's three conditions and R-04-010a's own criterion lists it among the standing matter dispositions. Neither decides the conditions **against this block's parts**, which is what a review gate and a netlist audit each need, so that is what §5 does: one table per condition, one row per clause of it, with the structure that satisfies the clause and the structure whose presence in the Coq term or in the netlist would falsify it. The falsifying column is written so that a reader can search for the thing rather than judge the claim.

### 5.1 Condition one: the transition relation is welded in RTL over no writable program store

| Clause | Satisfied by | Falsified by |
| --- | --- | --- |
| the encoder | a fixed linear map at one geometry, `M` to `N` under the one code §2.1 admits | a code-set index the block selects from at run time; a generator matrix read from a store the block writes |
| the decoder | a fixed graph run to `I_max`, reporting decoded bits and nothing else | a message schedule read from a writable store; an instruction fetch; a microcode ROM; a decode verdict register |
| the slot timer | a comparator of the spine's origin plus `SLOT[i]`'s instant against the member's own cycle count (R-15-122's kind) | a sequencer whose next state is read from memory the block writes; a program store of any width |
| the line interface | a fixed filter whose coefficients are frozen for the epoch and loaded only by the RoT (§3.2) | a coefficient store the datapath's own control rewrites within an epoch, which is a third-condition breach as well as this one |

**Reacting is not deciding**, which R-04-010a states and which sorts this block: a codeword the wire delivers is reacted to under a relation this composition welded, exactly as the PD sequencer steps on a message a foreign device sent. The condition is over the program store and never over input dependence, so a frame's contents reaching the decoder's arithmetic falsifies nothing here.

### 5.2 Condition two: every operand and every schedule is core-issued under explicit capability operands

| Clause | Satisfied by | Falsified by |
| --- | --- | --- |
| the schedule | `SLOT[i]` loaded by core-issued software from the admission artifact's fourth output, with no runtime exchange amending it (R-11-017a) | a slot the block derives from a frame; a table entry a peer's frame writes; any path from the wire to `SLOT[i]` |
| the operands | the two delegated windows, bounds-checked and re-authorized against the revocation bit at each TDM grant (R-15-208) | a DMA descriptor the endpoint builds; a request issued under a window whose revocation bit is set at that grant; a window the endpoint widens |
| the configuration | the code and every schedule parameter declared configuration the composition supplies (R-15-228c) | a parameter the block negotiates, adapts, or latches from a frame |
| the origin | read from the frame-origin register in the clock spine, which the boot core kernel alone writes (R-15-196a) | **any write path from the endpoint to the frame-origin register**, to a launch instant, or to a guard band |
| the enable | the liveness of the link server's delegated window grant (R-15-146) | a software-writable enable bit; an enable the block asserts for itself |

The grammar closes one of these rows at the field level rather than at the fabric: R-12-007a admits no capability, no address of either member, and no authority of any kind in a frame, so there is no field for a peer-supplied address to arrive in, and an endpoint that mastered a transfer would have to have invented the address rather than received it. That is why §1's *no field admits an address* and this condition's *masters nothing of its own* are two readings of one structure.

### 5.3 Condition three: it runs to a stated bound and accumulates no state across operations

| Clause | Satisfied by | Falsified by |
| --- | --- | --- |
| the bound | one slot's bound is the whole of what the block runs to (R-15-228c) | an operation spanning two slots; a launch that waits on a landing |
| fixed latency | `T_enc` and `T_dec` fixed, the decoder run to `I_max` and never stopped early | an early-terminating decoder, whose latency carries the frame's correctability across the slot boundary into the schedule |
| no accumulated slot state | the slot index is a **function** of the spine's origin and `SLOT[i]`, computed each slot | a slot counter; a sequence counter; an epoch counter in the endpoint |
| no peer-derived state | nothing a received frame writes except the landing and `ARRIVAL_PHASE` (R-15-228c) | a retry buffer (A-18); a credit or acknowledgement tracker (A-19); a per-flow queue or arbiter (A-20); a FIFO level register; a landed flag |
| no loop | `ARRIVAL_PHASE` one-sided, read by software (§3.5) | a phase accumulator; a latency estimator; any closed loop from a landing to a launch instant (A-21) |
| the one admitted carry | the equalization frozen per link epoch, which R-15-137's canceller already takes of this condition per epoch (R-15-228c); `EQ_READY` is that freeze's own validity and carries nothing else across a slot (§3.2) | equalization retrained inside an epoch, or adapted while traffic is in flight |

**The sorting is by these conditions and by nothing else.** The endpoint is not admitted here because it resembles the FEC decoders or the PD sequencer; it is admitted because each row above holds, and the resemblance is what makes the rows recognizable rather than what makes them true. R-04-010b is a separate admission category and the endpoint is not in it, holding neither a fixed model nor declared private retained state.

## 6. The netlist evidence an auditor searches for

Rows A-18 through A-21 are [the absence contract](absence-contract.md)'s, with their grounds, their evidence columns and their governing entries there and their provenance bindings in [the synthesis provenance record](../../rtl/synthesis-provenance.md). This section restates none of that. What it adds is the correspondence the rows cannot carry, because they are written over one block and this document is where that block's structures are named: **for each row, the structure of §3 or §5 whose presence in the netlist or in the Coq term is the finding.**

| Row | The structure whose presence falsifies it | Where a candidate would show it |
| --- | --- | --- |
| A-18 | a copy of a launched frame outliving its slot; a timeout counter; any register the launch path writes and a later slot reads | the transmit engine's window path, and any state between `TX_WINDOW_BIND` and the serializer |
| A-19 | a credit register; a ready, stall or back-pressure signal from the wire reaching the launch path; a landing that gates a launch | the path from the receive engine to the slot timer, which in an admissible block does not exist |
| A-20 | an arbiter; virtual-channel state; a per-flow queue; a FIFO deeper than §3.4's predicate admits, or one sized against a peer | the receive FIFO and everything between it and the receive window |
| A-21 | a phase accumulator; a latency estimator; a write path from the endpoint to the frame-origin register or to any launch instant; a leap path from an unverified landing; endpoint state a received frame updates beyond the landing and `ARRIVAL_PHASE` | `ARRIVAL_PHASE` and its fan-out, and the clock-data recovery, which is analog line-interface matter reaching no launch instant |

Every row above is discharged as authored RTL under R-15-092 by R-15-102's structural predicate over the block's Coq term, checked in the same prover as the refinement, which is R-15-228c's own acceptance and Q23g's to run. **This document states what the predicate must exclude and states no predicate**, that being the block's artifact and not this one's.

## 7. The link server's IDL interface

### 7.1 Where this declaration lives, and what it is waiting on

The link server is contained non-TCB software on cores (R-15-228b), and its clients are the sharded-function compartments on the same member. This section states its world in prose rather than as a world of [the ring reference](../../interfaces/ring-reference.json), and the reason is what a declaration fixes rather than where one may be written: `run.py ring emit` reads that declaration's worlds and K-89 binds the emitted Gallina artifact byte for byte, so a world added there fixes every composition-time constant R-12-091 and R-12-101 name and its generated campaign refuses a set of them that does not hold together. This section fixes no value of any of them, which is `IDL-050`'s own rule, so what is missing is the measured roster those constants are chosen from and not a place to write them down. **The declaration and its generated interface artifact are owed**, with `IDL-064`'s three parts and R-18-037's conformance campaign, and they are owed to the item that stands the link server up rather than to this contract.

### 7.2 The rings

Two ring instances, each declaring the composition-time constants R-12-091 enumerates as `IDL-050` requires, with **no value fixed here**: a request ring from the client compartment to the link server, and a completion ring back. The header is exactly the words R-12-091 names and carries nothing else, the count being that entry's and not this document's (`IDL-051`); indices are interpreted modulo the declared capacity with sequence information distinguishing full from empty, and no implementation infers validity from descriptor contents (`IDL-052`).

**The request ring's capacity is a composition-fixed local constant and is not a credit.** It is declared in the generated interface artifact, it is a property of this member alone, and no frame, no peer and no wire changes it. The distinction matters because A-19 and A-20 exclude credit registers and peer-varying queues from the **endpoint**, and a reader who carried that exclusion up into the link server would conclude that the server may hold no ring at all. EL-1 is where the distinction is recorded.

### 7.3 The operations

| Operation | What it carries | What its terminal completion means |
| --- | --- | --- |
| `send` | buffer references in the client's own session table, direction to the server, with R-12-092's bounded scalars and closed flag set | the bytes were placed in a transmit slot's frame and launched. **Never that a peer received them**: there is no acknowledgement to read, A-18 having deleted the structure that would carry one |
| `recv` | a pre-posted buffer reference, direction to the client, the extent validated before the transfer starts | a landed frame decoded, its tag verified by the crypto core, its descriptors validated against the per-link table, and its bytes copied into the posted buffer |
| `session_state` | no buffer reference; one bounded scalar selecting what is read | the link server's own view of the session epoch and whether the link is established, read from its own state and never from a peer |

`recv` is pre-posted rather than allocated on arrival, which is what keeps the receive path free of a queue that grows with a peer's traffic: a landing with no posted buffer is the overrun §3.3 states and not a backlog. Cancellation is `IDL-061`'s typed control-plane request and not a further operation of this interface. Zero-copy transfers execute only through a session-table capability whose permissions match the declared direction, with the complete extent validated before the transfer starts and never reinterpreted after (`IDL-063`).

### 7.4 The statuses, and how a link stop is represented

Statuses are drawn from R-12-093's closed common set and this document restates neither the set nor its lifecycle meaning (`IDL-028`). What it decides is the mapping, and one row of it is the interesting one.

| Event | How it is represented |
| --- | --- |
| a descriptor whose index, offset, length, direction, content type or generation fails validation against the per-link table | one of R-12-093's defined refusal completions, never a fallback interpretation (R-12-092, `IDL-054`) |
| submission against a full request ring | the sole typed result R-12-095 names, with no partial enqueue (`IDL-058`) |
| **a frame that fails its tag, an uncorrectable frame included** | **not a status.** The link fail-stops (R-15-228e), the session is torn down, and teardown is represented out of band by revocation plus a generation change, after which every formerly live request has R-12-093's own logical result for that case |
| re-establishment | a fresh session at `C_epoch`, never a resumption and never on demand (R-15-228e, R-12-015d); the new generation is live before any index is reused (`IDL-062`) |

The third row is the one a reader is most likely to get wrong, because a status is the natural place to put a failure. Putting it there would make a tag failure a per-request outcome a client could retry against, which is the reactive element R-15-228d deletes and which R-17-030z already decided to spend availability rather than admit.

### 7.5 The two session tables, which are not one table

R-12-006 has descriptors name only indices into a per-session table of pre-delegated capabilities, and R-12-007a reads that table at the link as the **receiving** member's own per-link session table, delegated at composition to the receiving link server alone and revoked as any compartment's authority is.

**An index in a frame and an index in a descriptor of §7.3 are indices into different tables.** The per-link table is the one a peer's descriptors select from, and it is the receiving link server's; the interface's session table is per client session, and it is the client's. An index carries no meaning on the member that sent it (R-12-007a), and it carries no meaning in the other table on the member that received it either. Conflating them would let a local client's index name a peer's entry, which is EL-3's refusal. A peer compromised inside an accepted session therefore reaches exactly what a compromised local ring peer behind the same table reaches, which is the ring proof's Byzantine peer (R-12-008) and no more.

## 8. What makes a candidate, a report, or an implementation inadmissible

| Id | The refusal |
| --- | --- |
| EL-1 | an endpoint holding a queue whose depth varies with a peer's activity, a retry, a credit or a sequence counter, **refused at review and never at RTL** (A-18 through A-20, R-15-228c). The link server's own ring capacity is not such a queue: it is a composition-fixed constant of the generated interface artifact (R-12-091), local to this member, and no frame changes it (§7.2) |
| EL-2 | a magnitude of §4 quoted as decided, or a pending row filled from an estimate, from a sibling document's illustration, or from a placeholder composition |
| EL-3 | a frame field admitting an address of either member, a capability encoding, a path, an executable name, a recursive value, an unbounded collection, or an index read against the wrong table (R-12-006, R-12-007a, R-12-092, `IDL-025`, §7.5) |
| EL-4 | an application payload or an origin leap enabled before establishment: a handshake or padding frame reaching any consumer but R-12-015d's bounded establishment handler, or a leap consuming a landing whose tag the crypto core has not verified |
| EL-5 | a frame delivered on the decoder's verdict, a syndrome or a CRC rather than on the tag, or a decoder that reports anything but decoded bits (R-15-228e) |
| EL-6 | an early-terminating decoder, or any encode or decode path whose latency is a function of the symbols or of whether the frame was correctable (R-15-119c, §2.1) |
| EL-7 | a second admissible code, ciphersuite, protocol version or configuration on one link, or a control plane holding a variable that selects among them (R-12-043a) |
| EL-8 | a public wire field selecting a regime, a handler or a key rather than being checked against the schedule and the session state; and any sender, address or persistent link-layer identifier field in any form (R-15-132, §1.2) |
| EL-9 | a re-encode at a hop, a member forwarding a frame, or a header carrying a route (R-15-228e, R-02-003a) |
| EL-10 | a claim that this descriptor carries its R-05-051a canonicity theorem while [crown-jewel](../assurance/crown-jewels.md) row 10 records the wire-format inventory as not authored (§1.6) |
| EL-11 | an accept-and-ignore field, a reserved bit, a fill byte accepted without its check, or any value with a second admissible encoding (R-05-051b, §1.6) |
| EL-12 | a `send` completion read as peer delivery, or any client behaviour conditioned on an acknowledgement this interface does not carry (§7.3) |
| EL-13 | an endpoint register outside §3.2's table, a receive status or landed flag, a FIFO level register, a software-writable enable, or a write path from the endpoint to the frame-origin register (§3.2, A-21) |

## 9. What this document leaves open, and to whom

| Owed | Who owes it |
| --- | --- |
| the descriptor's canonicity theorem and its Narcissus correctness pair | [crown-jewel](../assurance/crown-jewels.md) row 10, which reads `not authored`; no Narcissus descriptor exists in this repository for either to be stated against |
| the code's family, with its operand the wire's raw error rate at the declared reach and `M` | first measured at Q23g's two-member pair; §2.3 |
| `T_enc` and `T_dec` | R-17-041's magnitudes at [crown-jewel](../assurance/crown-jewels.md) row 15, measured at Q23g and entered in the devicetree fixture |
| `B_skew`, and the oscillator tolerances `D_fifo` and `C_leap` are derived from | measured on a two-member pair at qualification (R-15-196a); Q23g |
| every other row of §4 | the composition, emitted by Q23d with the ensemble schedule |
| §7's world declaration and its generated interface artifact with R-18-037's campaign | the item that stands the link server up; §7.1 says why it is not a second `interfaces/` world today |
| the session's reference model, its endpoint and key-compromise assumptions, and the binding between the quote's signing identity and the device-identity secret | Q23c, under R-12-015d and R-12-015c; R-17-049d records it open |
| the composed non-interference statement the §5 dispositions are eventually decided against | Q23f, under R-17-014a and R-17-003d |
| an R-09-007 Accept clause naming this class of declared per-link constants | **reported, not taken**; §4.2 names which rows an entry places by name and which rest on R-02-003a's general clause alone |

**One thing is deliberately not moved.** Entering this descriptor in [crown-jewel](../assurance/crown-jewels.md) row 10's specification cell adds a member to an inventory row whose status stays `not authored`, because no descriptor of that row is authored, this one included: what §1 states is the grammar a descriptor would be generated from, and the descriptor, its parser proof and its canonicity theorem are all still owed. Whether one stated grammar promotes that row's status is a coverage-matrix question, K-95 lifting a cell's standing from the inventory row's status class, and it belongs to whoever runs that repair rather than to this document.
