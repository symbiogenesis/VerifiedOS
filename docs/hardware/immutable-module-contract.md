# The Immutable Module Contract

> The crown-jewel specification [the inventory](../assurance/crown-jewels.md) names as the immutable inference device contract, conferred by R-12-085h.
> It fixes the socket's boundary, its grammar, its lifecycle and its private-state ownership, and separates the arbitrary-card host-containment theorem from the honest-card guarantees.
> It supplies no theorem, no descriptor, no magnitude and no measurement. Every one of those is owed below, with an owner.
> Where this document and [the register](../requirements-register.md) disagree, the register wins and this document is defective.

## Why this document exists

R-12-085h makes this contract a crown jewel and says in its own criterion that the contract is not authored until its artifact exists. R-12-085f refuses to enable any module for inference before its complete design, implementation and physical qualification artifacts are admitted, and Q24b through Q24h are the items that produce them. None of those items can state its own acceptance predicate against a boundary that has not been drawn, which is the whole of this document's job: to be exact about what crosses the socket, what may never cross it, and which claim is made over which scope, so that its consumers inherit one boundary rather than a reading each.

What this document is not is a price or a schedule for that work. It names owners and it names no figure, no estimate and no date.

**What is a composition choice here and what is deduced.** R-15-228f through R-15-228k fix the socket's kind, its traffic discipline, its seven states, its electrical control, its on-die model constants and its structural evidence, and R-12-085f through R-12-085n fix the broker, the manifest, the session binding, the grant, the state inventory and the arithmetic scoping. None of them enumerates the operations. The operation set, the register set, the slot classes, the socket state that admits each operation and the pre-establishment padding below are therefore this contract's composition choices in the sense [the modeled block-device contract](../../interfaces/block-device-contract.md) declares for its own command set: reviewed proposals bounded by the entries above, not deductions from them. Changing one is a device review and invalidates the evidence that read it. Everything stated as a refusal, a state or an ownership is the register's and is cited to it.

## 1. What the socket is, and what it is not

A module socket is a point-to-point message device edge from one host-owned endpoint to one R-04-010b module (R-15-228f). It is a **new external confidentiality boundary**: the material crossing it is a client's, it leaves the host die, and it enters a separately manufactured part in the holder's physical custody. Three resemblances are close enough to mislead, and each is told apart by what the register already decides rather than by how the traffic looks.

**It is not host memory, and not a shape of host DMA.** R-15-206 admits exactly two DMA-capable shapes, a core-issued capability-operand mover and an autonomous streaming engine holding a delegated bounds-checked window. The module is neither: it holds no host address, no capability, no DMA mastership, no coherence traffic, no interrupt authority and no route to another module (R-15-228f). The two shapes appear on the socket only on the host side of it, where the broker's mover carries bytes between host memory and the endpoint's windows under the ordinary capability check, and the endpoint's windows are one revocable ownership with its configuration MMIO on R-15-143's terms. **Every host destination is chosen by the endpoint from its own outstanding-operation state, never from a field the card supplied** (R-15-228f), which is the single sentence the containment theorem's DMA half rests on.

**It is not an ensemble member.** R-15-228c's ensemble-link endpoint reaches another copy of this same computer, attested under R-12-015d to be running the same discipline, and R-04-010's criterion says in as many words that such a peer is not a foreign computer. A module is not that peer: it runs no kernel, holds no generation, carries no address space of this machine's kind, and is admitted by R-04-010b as a separate device category rather than by R-04-010a's three conditions. R-15-228b's link and this socket therefore share a frame discipline and share no trust relation.

**It is not ordinary matter.** R-04-010a's third condition forbids state across the operations a block is handed, and a module retains an activation's private state by design. R-04-010b's second criterion says so directly: the module's retention is admitted only by R-12-085k's explicit ownership and erasure contract and is not ordinary matter. A reader who sorts the module with the FEC decoders or the PD sequencer has used the wrong instrument.

**What the module is.** A qualified peripheral whose complete execution relation is fixed digital logic, holding its own private state for the length of one activation under a declared scrub, reached only across this message edge, and carrying no authority on this machine at all.

## 2. Immutability

**The model graph, the weight constants and the sequencer are immutable, and the module admits no path that would change them.** There is no writable program store, no instruction fetch, no executable ROM, no microcode, no downloadable or in-field firmware, no mutable weights, no adapter, no LoRA or other low-rank update, no fine-tuning path, no runtime driver loaded at insertion, and no proof plugin (R-04-010b, R-15-228h, R-12-085h). The manifest and proof bytes the module carries are held in non-executable immutable storage and **are data rather than an option ROM** (R-04-010b); a digest identifies bytes and confers no theorem (R-12-085g).

This is not a property the socket enforces, and stating it here does not discharge it. It is a structural claim about the board and the inference die, and A-22 in [the absence contract](absence-contract.md) is the search that decides it: instruction, program, microcode and firmware stores and processors, writable weights and adapters, user-data nonvolatile stores, accessible debug, scan and test overrides, foreign bus mastership and undeclared private state, across the whole board and die, with the host endpoint searched separately for card-supplied address paths, independent interrupt authority, retry or credit state and arbitration state. A board carrying a programmable controller fails the classification even where its weights are immutable (R-04-010b). Q24f owns the evidence; this contract owns only the statement that the socket admits no operation whose effect would be to write any of it.

Replacement is therefore not an update. R-15-228h admits only a unit and design pair already in the generation's finite admitted replacement set, and adding a pair or changing this contract requires ordinary generation admission and boot.

## 3. The endpoint's register set

The endpoint is reached from the root device capability the attested devicetree hands the broker at construction, never from a hard-coded address (R-05-138), and its configuration MMIO and its two windows are one indivisible ownership granted and revoked together (R-15-143). The table declares each register's owner and direction and **no bit layout**: R-05-083 requires field layouts to be declared once in a register-description language with generated Coq-checked accessors, that language does not exist, and inventing a layout here would create a second owner for it. The layout is owed to U-10 in [the unassigned proof map](../assurance/unassigned-proof-map.md).

| Register | Written by | Read by | What it holds |
| --- | --- | --- | --- |
| `SOCKET_STATE` | the RoT alone | the broker | the current lifecycle state, one of the seven in section 6 |
| `ISOLATE` | the RoT alone | nothing | the declared isolation transition; re-enable is a host transition and never an autonomous recovery (R-15-228i) |
| `SLOT_PHASE` | the schedule | the broker | the current slot index within the rotation, from the attested schedule and from no peer's activity |
| `TX_WINDOW`, `RX_WINDOW` | the broker, under its grant | the fabric | the delegated bounds-checked window capabilities, re-authorized per grant against the revocation bitmap (R-15-208) |
| `EPOCH` | the broker | the broker | the activation epoch a result is matched against |
| `OUTSTANDING` | the endpoint | the broker | the outstanding-operation state from which every host destination is chosen (R-15-228f) |

Four absences are part of the declaration, and A-22 searches the endpoint for each: **no retry buffer, no credit or flow-control state, no arbiter, and no register a card-supplied field reaches.** No register names a host address, a DMA descriptor, an interrupt destination or a domain selector, on the same ground [the modeled block-device contract](../../interfaces/block-device-contract.md) states for its slave. The endpoint raises no interrupt of its own and initiates no fabric access outside its granted windows.

## 4. The request and result grammar

Every frame is one fixed-size unit of the composition-fixed frame size, carries authenticated encryption once a session is established, and is verified by the host crypto core before the copy-once parser accepts any field (R-15-228g). Every length field in the grammar is bounded by a **composition constant**, and this contract names the constants and no magnitude, for the reason section 10 states: R-15-228g makes frame size, slot counts, context and output ceilings and management budgets composition-fixed, and no artifact in this repository fixes any of their values.

The constants a length is bounded by are `F` the frame size, `N_in` the input elements one input frame carries, `N_out` the output elements one output frame carries, `C_ctx` the context ceiling of an activation, `C_out` its output ceiling, and `B_mgmt` the management budget per attachment, charged by each insertion and failed-authentication event (R-15-228h) and by each management operation of section 4.1, and by nothing on the transfer path.

### 4.1 The grammar

`slot class` is one of `reserved` (the identification and handshake slots that exist before authorization), `transfer` and `management`. Every operation not in this table is undeclared, and an undeclared opcode is refused at `N-opcode`.

| Operation | Direction | Slot class | Payload fields, each bounded by |
| --- | --- | --- | --- |
| `ID-RECORD` | module to host | reserved | the fixed public identification record R-12-085g's bounded format fixes: protocol version, design-manifest digest, endorsement reference. Total bounded by `F`; it confers no payload authority |
| `HS-INIT` | host to module | reserved | the challenge and authenticated context of the R-12-015c construction R-12-085i selects: host endpoint, unit and design identity, session epoch, schedule digest, slot count. Bounded by `F` |
| `HS-REPLY` | module to host | reserved | that construction's response. Bounded by `F` |
| `INF-OPEN` | host to module | transfer | activation id, request epoch, declared context length bounded by `C_ctx`, declared output ceiling bounded by `C_out` |
| `INF-INPUT` | host to module | transfer | activation id, request epoch, sequence index, element count bounded by `N_in`, and the elements: token IDs or one declared bounded tensor block and nothing else (R-15-228f) |
| `INF-DRAW` | host to module | transfer | activation id, request epoch, element count requested, bounded by `N_out` |
| `INF-ABORT` | host to module | transfer | activation id, request epoch |
| `INF-OUTPUT` | module to host | transfer | activation id, request epoch, sequence index, element count bounded by `N_out`, and the elements |
| `INF-END` | module to host | transfer | activation id, request epoch, disposition: completed, aborted, or refused with its declared reason code |
| `MGMT-QUIESCE` | host to module | management | session epoch |
| `MGMT-QUIESCE-END` | module to host | management | session epoch, disposition: drained or aborted |
| `MGMT-SCRUB` | host to module | management | session epoch |
| `MGMT-SCRUB-END` | module to host | management | session epoch, authenticated bounded completion |
| `IDLE` | either | any granted | the authenticated idle frame, fixed content, one per unfilled slot from `authenticated` onward. Before establishment an unfilled slot carries section 5's fixed public padding, which is a constant and not an operation of this table |

No field of any operation carries a host address, a capability, a length that another field does not already bound, a retry count, a credit, a deadline or a reschedule request. **A result never names its own destination**: the endpoint matches `activation id` and `request epoch` against `OUTSTANDING` and chooses the destination from there (R-15-228f).

Tokenization, text parsing, tool interpretation and grant handling stay on admitted host cores (R-15-228f). The elements an `INF-INPUT` carries are data with the client's confidentiality label and no secret label (R-15-228f, R-12-085j), and an `INF-OUTPUT` element is an untrusted proposal that reaches no object without a capability already granted for it (R-12-085b, R-12-085d).

### 4.2 The decision

Every row names the socket states that admit the operation, the success predicate inside those states, and the disjunction that refuses it. **A declared operation arriving in a state outside its Admitted-in cell is refused at `N-state`**; that disjunct belongs to every row and is not repeated in any of them. Inside the admitting states the disjuncts are drawn to be the complement of the success predicate, so **no frame of the declared grammar is unclassified**: a frame either satisfies its operation's success predicate or matches at least one disjunct. A frame outside the declared grammar is refused before this table is reached, at `N-tag` if its tag does not verify, at `N-length-frame` if its lengths do not fit the frame, and at `N-opcode` if its opcode is undeclared. That the two sides are complementary is a drafting property of this table and not a theorem; Q24d's generated frames are what would falsify it.

An operation whose cell names `quiescing` is admitted there only for **an activation already open when `T5` fired**, which is the drain R-15-228h's ordered path permits between ordered stop and scrub. No new activation opens in `quiescing`.

| Operation | Admitted in | Success predicate | Refusal disjuncts |
| --- | --- | --- | --- |
| `ID-RECORD` | `reset` | the frame arrives in a reserved slot, every field parses under R-12-085g's bounded format, and the record asserts no authority beyond identification | not a reserved slot (`N-slot`); a field outside its format (`N-length-bound`); an identification record asserting any authority beyond identification (`N-idpayload`) |
| `HS-INIT` | `reset` | the slot is reserved and the construction's precondition holds | not a reserved slot (`N-slot`); the construction's precondition fails, which includes a freshness premise the reset seam has not discharged (`N-hs-freshness`) |
| `HS-REPLY` | `reset` | the slot is reserved, an `HS-INIT` is outstanding at the current session epoch, the tag and the authenticated context verify, the unit and design pair is in the generation's finite admitted set, and the appraisal succeeds under holder-admitted roots | not a reserved slot (`N-slot`); no `HS-INIT` outstanding (`N-unsolicited`); a reply naming a superseded session epoch (`N-stale-epoch`); tag or context fails (`N-tag`); unit or design outside the admitted set (`N-unadmitted`); appraisal fails (`N-appraisal`) |
| `INF-OPEN` | `active` | a live grant names this agent, unit and design, the request asks for no authority the grant does not carry, no activation is open, the declared lengths are within `C_ctx` and `C_out`, and the lengths are consistent with the frame | no live grant or a mismatched one (`N-grant`); a request for authority the grant does not carry (`N-grant-widen`); an activation already open (`N-state`); a declared length above its ceiling (`N-length-bound`); lengths inconsistent with the frame (`N-length-frame`) |
| `INF-INPUT` | `active` | an activation is open at this epoch, the sequence index is the next one, the element count is at most `N_in`, the lengths are consistent with the frame, and the cumulative element count stays within `C_ctx` | no open activation (`N-state`); a superseded epoch (`N-stale-epoch`); a sequence index that is not the next (`N-sequence`); element count above `N_in` (`N-length-bound`); cumulative count above `C_ctx` (`N-length-bound`); lengths inconsistent with the frame (`N-length-frame`) |
| `INF-DRAW` | `active`, `quiescing` | an activation is open at this epoch, the requested count is at most `N_out`, and the cumulative drawn count stays within `C_out` | no open activation (`N-state`); a superseded epoch (`N-stale-epoch`); count above `N_out` (`N-length-bound`); cumulative count above `C_out` (`N-length-bound`) |
| `INF-ABORT` | `active`, `quiescing` | an activation is open at this epoch | no open activation (`N-state`); a superseded epoch (`N-stale-epoch`) |
| `INF-OUTPUT` | `active`, `quiescing` | an `INF-DRAW` is outstanding at this epoch, the sequence index is the next one, the element count is at most the count drawn and at most `N_out`, and no destination field is present | no outstanding draw (`N-unsolicited`); superseded epoch (`N-stale-epoch`); wrong sequence index (`N-sequence`); count above the count drawn or above `N_out` (`N-length-bound`); a destination field present at all (`N-destination`) |
| `INF-END` | `active`, `quiescing` | an activation is open at this epoch and the disposition is one of the three declared | no open activation (`N-unsolicited`); superseded epoch (`N-stale-epoch`); an undeclared disposition (`N-opcode`) |
| `MGMT-QUIESCE` | `authenticated`, `active` | the slot is a management slot and `B_mgmt` is not exhausted | not a management slot (`N-slot`); budget exhausted (`N-budget`) |
| `MGMT-QUIESCE-END` | `quiescing` | the slot is a management slot and a `MGMT-QUIESCE` is outstanding at this session epoch | not a management slot (`N-slot`); none outstanding (`N-unsolicited`); superseded epoch (`N-stale-epoch`) |
| `MGMT-SCRUB` | `quiescing` | the slot is a management slot, `B_mgmt` is not exhausted, and every activation of the session is closed, drained or aborted | not a management slot (`N-slot`); budget exhausted (`N-budget`); an activation still draining (`N-state`) |
| `MGMT-SCRUB-END` | `quiescing` | the slot is a management slot, a `MGMT-SCRUB` is outstanding at this session epoch, and its authenticated bounded completion verifies | not a management slot (`N-slot`); none outstanding (`N-unsolicited`); superseded epoch (`N-stale-epoch`); completion does not verify (`N-tag`) |
| `IDLE` | `authenticated`, `active`, `quiescing` | the slot is granted to this socket and the frame's tag verifies at the current session epoch | a slot not granted to this socket (`N-slot`); tag fails (`N-tag`); a tag at a superseded session epoch (`N-stale-epoch`) |

**An application record refused at the wire ends its session without delivery**, and the host and unrelated work retain their schedules: that is R-15-228g's fail-closed clause over malformed, unsolicited, stale or unauthenticated application traffic, and it is what `N-tag`, `N-opcode`, `N-length-bound`, `N-length-frame`, `N-sequence`, `N-unsolicited`, `N-stale-epoch`, `N-destination`, `N-grant-widen` and `N-state` carry. **`N-grant` is not one of them**: a missing, expired, revoked or mismatched grant is refused by the broker before any frame is emitted, and R-12-085j disposes of it as grant failure disabling application delivery through that route, leaving the established session standing until an ordered stop or a wire refusal closes it. A reserved-slot record refused at `N-idpayload`, `N-length-bound`, `N-unadmitted`, `N-appraisal` or `N-hs-freshness` has no session to end and takes `T8` or `T10` into `isolated`. A refusal of a management record consumes its budget and takes no other host effect. Refusals are collected by the fail-closed seam R-17-030za; there is no weaker mode, no fallback destination and no automatic retry anywhere in this table (R-12-085f, R-15-228g).

## 5. Slots, idle behaviour, and the socket before a session exists

Socket traffic follows composition-fixed slots (R-15-228g) on R-07-036's non-work-conserving discipline. **Every slot granted to the socket carries exactly one frame of size `F`**, so the wire carries the same frame count and the same frame size whatever the traffic. An unused slot is **burned**: it is not reassigned, donated, skipped or rescheduled, and a silent or absent module cannot stall the host or borrow another partition's slot (R-15-228g). There is no transport retry, no adaptive flow control, no credit and no on-demand rescheduling; a new request is an explicit broker operation and never a replay of an old one.

**Before a session is established, the only records that cross are the fixed public identification and handshake records in reserved slots** (R-15-228g), under R-12-085g's verified bounded formats. They confer no payload authority: an identification record is a claim about a design, it is checked against the generation's admitted set, and it authorizes nothing by being well formed. A card that sends only these records forever consumes `B_mgmt` and nothing else.

**What fills a slot that has nothing in it is decided in two pieces, and the split is this contract's composition choice on R-15-228d's precedent for the ensemble link.** Transfer and management slots are granted to the socket only from `authenticated` onward; before that the socket holds reserved slots alone. An unfilled reserved slot carries the **declared fixed public padding pattern** of size `F`: a constant, carrying no opcode, reaching no parser, and eligible as neither application traffic nor a handshake input. A pre-establishment reserved slot holding neither that constant nor a declared reserved-slot record is refused at `N-opcode`. From `authenticated` onward an unfilled granted slot carries the authenticated `IDLE` frame, whose tag the crypto core verifies like any other.

Two things follow that are worth stating because a reader expects the opposite. First, **an idle established session and a loaded one are indistinguishable in slot occupancy**, because both produce the same frame count at the same size, and the type of an established-session frame is read only after the crypto core has decrypted and authenticated it (R-15-228d's reading of the same discipline). This is a statement about the traffic of a live session and not about presence: an absent module sends no frame at all, and its absence is what `T1`'s declared detection reports into `SOCKET_STATE`. Second, **the module's own internal routing, KV addressing and token selection may depend on its client's content** within the admitted private budget, and only the observable link timing and size follow the schedule (R-15-228g). No general claim of constant power or electromagnetic leakage follows from either, and R-17-058i books those observations as a residual.

The admitted rate of the socket includes the broker's cost, the cryptography, the endpoint and the erasure work at the declared contexts, and is not an arithmetic peak (R-15-228g). This contract states that the rate is that composition constant and states no value for it.

## 6. The lifecycle

R-15-228h fixes the state set at composition and names it: **absent, isolated, detected, reset, authenticated, active and quiescing**. Two words a reader may arrive with are glosses rather than states. *Present* is the condition a card is in from `detected` onward and is not a state of its own. *Admitted* describes a unit and design pair that is in the generation's finite admitted replacement set, which is a property of the pair rather than of the socket, and the socket state it produces is `authenticated`.

### 6.1 The admitted transitions

| Id | From | To | Trigger | Precondition |
| --- | --- | --- | --- | --- |
| `T1` | absent | detected | the RoT's declared presence detection asserts, within its bounded detection delay (R-15-228i) | the socket is electrically isolated and unpowered |
| `T2` | detected | reset | the RoT runs the declared power, clock and reset sequence | the sequence's step gating is satisfied; the electrical steps are [the reset and power sequence table](../assurance/crown-jewels.md)'s and are cited here, never copied |
| `T3` | reset | authenticated | the R-12-015c construction R-12-085i selects completes with `HS-REPLY` accepted | the unit and design pair is in the generation's finite admitted set, the appraisal succeeds under holder-admitted roots, and the reset seam has discharged the construction's freshness premises |
| `T4` | authenticated | active | the broker opens the route on a live R-12-085j grant | the grant names this agent or application, this authenticated unit key and this design and model, the permitted inputs, the result destination and the activation epoch; at most one unit and design pair is active on the socket (R-15-228h) |
| `T5` | active | quiescing | ordered stop: grant revoked or expired, ordered replacement requested, or the session epoch closed | none beyond the trigger; new work stops and application grants close at the transition, and an activation already open drains or aborts inside `quiescing` before `MGMT-SCRUB` is admitted (R-15-228h) |
| `T13` | authenticated | quiescing | the same ordered stop, before any activation opened | the private volatile inventory is empty, so the scrub's inference part is vacuous and its key and epoch part is not |
| `T6` | quiescing | isolated | the qualified scrub completes with authenticated bounded completion, **or** its bounded deadline expires, **or** the card is removed | on completion, session keys are destroyed and epochs invalidated before isolation; on deadline expiry or removal, isolation and power-down proceed **with no completed-erasure claim** (R-15-228h) |
| `T7` | active | isolated | failure, timeout, protocol failure, a refused application record, or surprise removal | none; the host can always isolate without a card acknowledgement (R-12-085k) |
| `T8` | detected | isolated | detection of an unmatched or unadmitted unit, or a failed detection step | an unmatched replacement remains isolated (R-15-228h) |
| `T9` | reset | isolated | the reset sequence fails or times out | n/a |
| `T10` | authenticated | isolated | authentication revoked, appraisal withdrawn, protocol failure or timeout before a grant opens | n/a |
| `T11` | isolated | absent | the declared detection step confirms removal | n/a |
| `T12` | isolated | reset | the declared host re-enable transition (R-15-228i) | `B_mgmt` is not exhausted; non-programmable protection may cut the slot off and may never raise its envelope or recover it autonomously |

**Surprise removal and a missed scrub deadline land in the same place and carry the same silence**: `T6` or `T7` into `isolated`, with no drain, no erase acknowledgement and no erasure claim of any kind (R-12-085h's fail-closed seam, R-12-085k, R-15-228h). An acknowledgement alone proves no erasure, and removal or power loss before completion establishes none.

Across every transition into `isolated` and `absent`: outstanding request epochs are invalidated, old replies never populate a new owner's buffers, no request is implicitly replayed, and **host buffers are reclaimed only after the host mover's own bounded completion and revocation barrier** (R-15-228h, R-15-208a). Reconnection establishes a fresh session and re-evaluates permission; no live conversation continuity is promised, and migrating a conversation would need a separately admitted bounded state transfer that this contract does not define.

### 6.2 The transition matrix

Rows are the state left, columns the state entered. A cell naming a `T` id is that admitted transition. A cell naming an `N-` id is refused, and that id is a rejected instance in section 9. The diagonal is `n/a`: holding a state is not a transition, and a self-transition is not in the relation.

| from \ to | absent | isolated | detected | reset | authenticated | active | quiescing |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **absent** | n/a | `N-trans-absent` | `T1` | `N-trans-power` | `N-trans-skip` | `N-trans-skip` | `N-trans-skip` |
| **isolated** | `T11` | n/a | `N-trans-redetect` | `T12` | `N-trans-skip` | `N-trans-skip` | `N-trans-skip` |
| **detected** | `N-trans-surprise` | `T8` | n/a | `T2` | `N-trans-skip` | `N-trans-skip` | `N-trans-skip` |
| **reset** | `N-trans-surprise` | `T9` | `N-trans-back` | n/a | `T3` | `N-trans-skip` | `N-trans-skip` |
| **authenticated** | `N-trans-surprise` | `T10` | `N-trans-back` | `N-trans-back` | n/a | `T4` | `T13` |
| **active** | `N-trans-surprise` | `T7` | `N-trans-back` | `N-trans-back` | `N-trans-reauth` | n/a | `T5` |
| **quiescing** | `N-trans-surprise` | `T6` | `N-trans-back` | `N-trans-back` | `N-trans-reauth` | `N-trans-resume` | n/a |

## 7. Private state, and what clears it

### 7.1 The inventory

R-12-085k gives module state four dispositions and requires every mutable store to be inventoried, bounded and owned. The rows below cover every store this contract declares: R-12-085k's four dispositions on the module side, and every register of section 3 on the host side. A retained element neither section declares is what A-22 searches the board, the die and the endpoint for, and finding one is a finding against the part rather than a row missing here. Module rows carry one of the four dispositions by name; host rows carry `host endpoint`, which is not one of R-12-085k's four because R-12-085k scopes the module. **No magnitude appears in this table**: the module's private footprint is Q24b's and Q24e's to fix against a qualified closure, and R-15-228j requires the context, KV, activation and work ceilings to be declared independently of the model constants.

| Store | Confidentiality domain | Disposition | Cleared by | State after | Owned by |
| --- | --- | --- | --- | --- | --- |
| model graph, weight constants, tokenizer and vocabulary tables | public | immutable public | nothing; no admitted operation writes them | unchanged for the life of the die | R-04-010b, R-12-085g, R-15-228j |
| manifest and proof bytes | public | immutable public | nothing; non-executable immutable storage | unchanged | R-12-085g |
| unit private key, local derivation and masking seed | protected persistent | protected persistent | nothing in any transition of section 6; it is the unit's identity | retained through scrub, reset and power cycle | R-12-085i |
| module-side session keys | protected ephemeral | ephemeral crypto | session-key destruction on `T6`'s completing arm | destroyed; the epoch is invalid | R-12-085i, R-15-228h |
| module-side DRBG and masking randomness | protected ephemeral | ephemeral crypto | the declared reset sequence and the qualified scrub | refreshed from the protected seed under the construction's freshness premise; repeated power cycles and repeated or adversarial handshakes may not silently reuse a nonce, ephemeral key or mask (R-12-085i) | R-12-085i |
| prompts, context buffers and token IDs | the activation | private volatile | the qualified scrub | the scrub's declared post-state | R-12-085k |
| KV tensors | the activation | private volatile | the qualified scrub | the same | R-12-085k |
| activations and scratch | the activation | private volatile | the qualified scrub | the same | R-12-085k |
| queues, counters and sequencer state | the activation | private volatile | the qualified scrub | the same | R-12-085k |
| sampling state and partial outputs | the activation | private volatile | the qualified scrub | the same | R-12-085k |
| endpoint outstanding-operation state, and the `EPOCH` a result is matched against | the host | host endpoint | epoch invalidation at every transition into `isolated` | emptied and invalid; no late result matches | R-15-228f, R-15-228h |
| endpoint receive and transmit window contents, and the `TX_WINDOW` and `RX_WINDOW` capabilities that reach them | the host | host endpoint | the contents by the host mover's bounded completion and revocation barrier; the capabilities by revocation, re-authorized per grant against the revocation bitmap | reclaimed, and not before; no engine authorized past the next grant | R-15-208, R-15-208a, R-15-228h |
| host-side session keys, held in the crypto core | the host | host endpoint | epoch invalidation | destroyed | R-12-085i |
| `SOCKET_STATE` and `ISOLATE`, the endpoint's lifecycle and isolation control | public | host endpoint | the RoT's declared power, clock and reset sequence at `T2`, the RoT being the only writer of either | the sequence's declared post-state; re-enable is `T12` and never an autonomous recovery | R-15-228h, R-15-228i |
| `SLOT_PHASE`, the index within the rotation | public | host endpoint | nothing: it is a function of the attested schedule and of no peer's activity, and it carries no client or session material | advancing with the rotation | R-15-228g, R-07-036 |

**No private user data persists in nonvolatile storage or through an adapter, and no simultaneous cross-domain tenancy is admitted** (R-12-085k). Reassignment of the module to a new owner follows completed qualified erasure and nothing weaker.

### 7.2 Abort

`INF-ABORT` succeeds against an open activation at the current epoch. Its postcondition, in full: the activation's private volatile rows above are placed in the scrub's declared post-state; the request epoch is invalidated; no `INF-OUTPUT` of that activation is delivered afterwards, and one that arrives is refused at `N-stale-epoch`; `INF-END` reports the disposition `aborted`. **Abort clears no protected persistent store, destroys no unit key, and ends no session.** It travels the transfer slots its activation already holds and is charged to no management budget; its completion is an authenticated bounded result, which is evidence that the module answered and is not evidence that anything was erased (`I-ack-not-erasure`).

### 7.3 The scrub

R-12-085k fixes the scrub's postcondition, what that postcondition does not demand, and the corners at which the physical record establishes the reset and erase construction. This contract adds nothing to those terms and does not restate them; a consumer reads them at the entry.

Three boundaries around it are stated here because a consumer will otherwise assume them. **The scrub is what `MGMT-SCRUB` starts and `MGMT-SCRUB-END` reports, both inside `quiescing` and both charged to `B_mgmt`.** **Scrub completion precedes management-key destruction**, so the ordering in `T6` is not an implementation detail. And **the host never waits on the card to isolate**: the deadline is the host's, it can isolate without an acknowledgement, and expiry takes `T6`'s non-completing arm.

## 8. What is claimed, and over what

Every row below but the last is a theorem target. None of those is proved, and the Owner column names the item that owes each. The last row is a residual no theorem discharges, which is why its Quantified-over cell is `n/a`. The Scope column is the point of the table: R-12-085h requires the certificate to cover the minimum guarantees **across the whole circuit**, and says that a certificate covering selected blocks while leaving other relevant paths unexamined does not satisfy the requirement.

| Claim | Quantified over | Scope | Owner |
| --- | --- | --- | --- |
| host containment against an arbitrary card | every module behaviour, including silence, malformed frames and dishonest answers within the current session, inside the declared electrical fault model | the whole relevant host path: endpoint, broker, mover, windows and epochs | Q24d |
| module interface conformance | the qualified implementation's framing, authentication and sequencing against the existing crypto specifications | whole circuit | Q24e, admitted by Q24c |
| cryptographic identity and session binding | the qualified implementation and the selected R-12-015c construction, over replay, concurrent attachment, wrong unit with the same model, wrong design with the same label, relay, key compromise and the reset seam | whole circuit | Q24c |
| resource bounds | the declared contexts, ceilings and budgets | whole circuit | Q24e |
| state separation and clearing | the declared scrub, including KV, activations, scratch, queues, crypto and session state and reset or abort | whole circuit | Q24e |
| exact arithmetic over named operators | the named operators over their legal dimensions and constants | **selected blocks, and stated as such** | Q24e |
| whole-model functional correctness | the exact finite graph and weight bytes R-12-085g identifies, with checked correspondence through the declared lowering artifacts | the whole graph | Q24e, over Q24b's closure |
| structural absence | the complete board and inference die, and the host endpoint | whole board and die | Q24f, against A-22 |
| fabrication and physical correspondence | n/a | residual; no design proof, key possession or endorsement establishes it | Q24f, booked by R-17-058i |

**The first row is quantified differently from the rest and the difference is the whole separation.** Host containment holds against a card that is arbitrary. Rows two through five hold over the qualified implementation and assume an honest card, and R-12-085h says they are never inferred from the containment theorem. A reader who has row one and reads rows two through five as consequences of it has made the mistake this table exists to prevent (`I-honest-vs-arbitrary`).

**Row six is scoped and is not a down payment on rows two through five.** An arithmetic result over selected blocks is admitted under R-12-085l, records its actual scope in the manifest and the admission receipt, and never promotes into a whole-graph proof on the strength of model performance. The complete minimum security contract, rows two through five, does not by itself confer row seven either.

**Trust assumptions, stated together because they are read together.** The certificate is checked by the same CIC kernel, or by reflection of a soundness-proved certificate checker inside it, and may introduce neither a trusted axiom nor replacement semantics, an executable tactic, a checker plugin or a driver (R-12-085h). Byte size, checking fuel, scratch space and verdict latency obey R-06-015a's predeclared bounds. Proof production and circuit synthesis are off-device. Authentication proves key possession and makes no physical-locality claim. Sail supplies executable device semantics joined to its generated Rocq definitions and is not itself a proof of RTL conformance (R-12-085l). The electrical fault model bounding row one is R-15-228i's and its values are Q24f's; **arbitrary physical sabotage is outside it** and no row above covers it.

**Outside every row above**, and outside this contract entirely: factual accuracy, prompt injection, learned backdoors, and the intent of any output (R-12-085l, and R-12-085b's reading that model output is an untrusted proposal). Approximation error and model quality are separate evidence. A theorem over a circuit does not certify a manufactured die.

## 9. Named cases

These are decisive cases for the consumers, in the form [the modeled block-device contract](../../interfaces/block-device-contract.md) uses. They are acceptance predicates and not a record that anything passes; nothing here has been executed. Q24d generates adversarial frames and a malicious endpoint model against the `N-` and `C-` rows, and Q24e against the `I-` rows.

| Case | Stimulus | Required observation |
| --- | --- | --- |
| `P-idle` | an established session with no traffic for a full rotation | one `IDLE` frame per granted slot, same count and same size as a loaded rotation; no slot reassigned or skipped |
| `P-preauth` | a socket in `reset` with no reserved-slot record to send for a full rotation | the fixed public padding constant in every unfilled reserved slot, same count and same size; no transfer or management slot granted to the socket; no parser reached and no `B_mgmt` charged |
| `P-open` | a live grant, `INF-OPEN` at the declared ceilings, inputs in sequence, draws to the output ceiling, `INF-END` completed | delivery only to the destination `OUTSTANDING` names; no host buffer reclaimed before the mover's barrier |
| `P-scrub` | ordered removal from `active`: `MGMT-QUIESCE`, `MGMT-SCRUB`, completion inside the deadline | `T5` then `T6`'s completing arm; scrub completion precedes key destruction; epochs invalid before isolation |
| `P-cold-swap` | power-down replacement by another pair in the admitted set | fresh session, fresh epoch, re-evaluated grant; no inherited grant and no conversation continuity |
| `N-opcode` | a frame whose opcode is not in the section 4.1 table, a disposition code `INF-END` does not declare, and a pre-establishment reserved slot holding neither the padding constant nor a declared reserved-slot record | refused before any field is interpreted; an established session ends without delivery; no host state change beyond the refusal |
| `N-length-bound` | an element count above `N_in`, a declared context above `C_ctx`, a cumulative draw above `C_out`, each otherwise well formed | refused at the bound, not at the frame; the refusal names the constant |
| `N-length-frame` | lengths mutually consistent but summing past `F`, and lengths consistent with `F` but inconsistent with each other | refused before the copy-once parser accepts a field |
| `N-tag` | a frame whose authentication tag does not verify, including a correctly shaped one | delivered to nothing; the session ends; the crypto core's verdict precedes every parse |
| `N-state` | each operation of section 4.2 issued in every socket state outside its **Admitted in** cell, each activation operation issued with no activation open, `INF-OPEN` with one already open, and `MGMT-SCRUB` with an activation still draining | refused by state; `B_mgmt` charged where the operation is a management one; no other host effect |
| `N-slot` | a frame in a slot not granted to this socket, and a card attempting a second frame in one slot | refused; no other partition's slot is reachable and no stall reaches the host schedule |
| `N-unsolicited` | `INF-OUTPUT`, `INF-END`, `MGMT-SCRUB-END` and `HS-REPLY` with nothing outstanding | refused against `OUTSTANDING`; no host buffer is written |
| `N-stale-epoch` | a result naming a superseded activation or session epoch, delivered after abort, after revocation and after replacement | refused; old replies never populate a new owner's buffers |
| `N-sequence` | an input or output frame whose sequence index is not the next one, including a repeat of the previous one | refused; no implicit replay and no reordering |
| `N-destination` | a frame carrying a host address, a capability, a descriptor or any field that would select where a result lands | refused; the field is not in the grammar and its presence is itself the defect |
| `N-grant` | `INF-OPEN` with no grant, an expired one, a revoked one, or one naming another agent, unit or design | refused by the broker with no frame emitted; delivery through the route is disabled and the established session stands; a replacement inherits no grant |
| `N-grant-widen` | a module frame requesting wider authority, a different destination, or a consent response | refused; no module message manufactures a consent response and the capability stays with the host principal and broker (R-12-085j) |
| `N-idpayload` | an identification or handshake record carrying application bytes or asserting authority | refused; reserved-slot records confer no payload authority |
| `N-budget` | repeated insertion, repeated failed authentication and repeated management requests past `B_mgmt` | isolation; only the fixed management budget is consumed and unrelated host work is unmoved |
| `N-appraisal`, `N-unadmitted` | a unit outside the admitted set, a design outside it, a copied identifier without its key, a foreign unit, and a valid unit with a withdrawn appraisal | `T8` or `T10` into `isolated`; an unmatched replacement remains isolated |
| `N-hs-freshness` | repeated power cycles and identical or adversarial handshake traces | no silent reuse of a nonce, ephemeral key or mask where the construction forbids it; the handshake refuses rather than proceeding |
| `N-trans-skip` | every transition that would enter `reset`, `authenticated`, `active` or `quiescing` without its admitted predecessor | refused; the matrix cell is the specification |
| `N-trans-back` | every backward transition out of `reset`, `authenticated`, `active` or `quiescing` toward `detected` or `reset` | refused; re-entry is through `isolated` and `T12`, or through `absent` |
| `N-trans-power` | entering `reset` from `absent`, bypassing detection and the declared sequence | refused; the RoT's sequence is the only path to a powered socket |
| `N-trans-absent` | entering `isolated` from `absent` | refused; `isolated` describes a present module |
| `N-trans-redetect` | re-entering `detected` from `isolated` without removal | refused; `T12` is the declared re-enable and `T11` the declared removal |
| `N-trans-reauth` | re-entering `authenticated` from `active` or `quiescing` | refused; a session is never re-entered, and reconnection starts at `T2` |
| `N-trans-resume` | re-entering `active` from `quiescing` | refused; quiescence is not a pause and there is no resumption |
| `N-trans-surprise` | removal at every state from `detected` onward | `isolated` first and `absent` only after `T11`; **no erasure claim on any of these paths** |
| `C-removal-ordered` | ordered removal interrupted at each step of `T5` then `T6` | completion or the deadline arm; unrelated host authority and the host schedule unchanged |
| `C-removal-surprise` | removal, stuck pins, contact bounce, brownout and a partial frame at every transition | `T7` or `T6`'s non-completing arm within the declared electrical bounds; the host continues in its composed schedule |
| `C-scrub-deadline` | scrub started and the bounded deadline allowed to expire, with and without a later card acknowledgement | isolation and power-down; the late acknowledgement changes nothing and confers no erasure |
| `I-ack-not-erasure` | a card that reports every completion promptly and erases nothing | the protocol is satisfied and no erasure claim is earned; only Q24e's state-lifetime proof and Q24f's physical record decide it |
| `I-honest-vs-arbitrary` | the containment theorem of section 8 row one, offered as evidence for rows two through five | refused as a category error; the honest-card guarantees are over the qualified implementation and are never inferred from the wrapper |

## 10. What is owed, and who owes it

Nothing in this list carries a figure, an estimate or a date.

| Owed | Owner |
| --- | --- |
| the magnitudes of `F`, the transfer, management and reserved slot counts, `N_in`, `N_out`, `C_ctx` and `C_out`, the budget `B_mgmt`, and the bit pattern of section 5's fixed public padding: R-15-228g makes them composition-fixed and no artifact in this repository fixes any of them | the composition act that admits a module, reading Q24b's closure, Q24e's footprint and Q24f's envelope |
| the Narcissus descriptors for the manifest, certificate transport, endorsement and the protocol records of section 4.1, with their bounded non-recursive formats and explicit byte, field and depth limits (R-12-085g, R-05-046) | U-12's wire-format inventory, whose row in the crown-jewel inventory already names these as member classes |
| the R-05-051a canonicity theorem over each descriptor whose encoding is an input to a signature, a hash used as a name or an equality test | U-14, over one descriptor end to end, then per descriptor |
| the endpoint's register field layouts and their generated Coq-checked accessors (R-05-083) | U-10's register-description language |
| the electrical steps of `T1`, `T2`, `T6` and `T12`: the dependency-ordered sequence, its ready indications, timeouts and re-entry points | U-06's reset and power sequence table, which this contract cites rather than copies |
| the values of R-15-228i's envelope: connector sequencing, bounded detection and isolation delay, inrush and backfeed limits, short, overvoltage and thermal limits, and rail and reset independence | Q24f |
| the host-side wrapper, its Sail-visible operations, its device-window refinement and the containment theorem of section 8 row one | Q24d |
| the bounded read-only manifest and proof-certificate format, the checked design-admission path, and the R-06-015a budget instance | Q24c |
| a qualified model closure fixing the identity the manifest must pin: weights, graph, tokenizer, quantization, rounding, overflow and sampling rules | Q24b |
| the operator proofs, their composition over the graph, and the state-lifetime proof section 7 states the postcondition of | Q24e |
| the orderly host-live replacement path and its surprise-removal containment evidence; this contract's `T5`, `T6` and `T12` are protocol transitions and carry no electrical qualification | Q24g |
| the integration verdict for an exact model, circuit, unit set, socket, host generation and replacement mode | Q24h |

## 11. What this contract does not decide

It authors no theorem and proves nothing. It selects no model, no candidate and no vendor; naming none is deliberate, because R-12-085m fixes selection at incorporation and a name written here would read as a shortlist. It states no byte count, no rate, no latency and no power figure, and a figure quoted from this document is a defect in the quoting artifact. It does not qualify the socket electrically, does not admit any unit, and confers no status on any module.

It also decides nothing about the routes it sits beside. R-12-085n keeps the software inference server and the remote endpoint as separately authorized choices, neither retired by a module's admission, and R-18-004a's first-release local inference floor stays on its software mechanism with no dependency on this peripheral. The comparison that would weigh the three is Q24h's, and an immutable model establishes no pure improvement over the confined software path without it.
