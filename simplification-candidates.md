# Simplification Candidates (non-normative)

> Companion to [verification-maximal-os.md](verification-maximal-os.md) and [isa-profile.md](isa-profile.md).
> Where [performance-recovery-todo.md](performance-recovery-todo.md) enumerates levers that buy **performance** at no cost on the scarce axis, this doc enumerates levers that buy **the scarce axis itself** — specification and proof surface — at no cost in performance.
> Both lists exist because the design's premise ("engineering is free; trust is the scarce resource") makes the two currencies non-interchangeable: a deletion that shrinks the Sail model and the proof burden is worth pursuing even when it recovers not one cycle, and *especially* when it recovers cycles too.
> An item can sit on both lists; where one does, this doc holds the deletion argument and the other holds the row.
> Nothing here is normative. Each item is a proposal against the frozen profile, and adopting one is a profile amendment that reruns the review gate (R-18-034).
> This list records **open** proposals only: an item that lands in the spec leaves it, the spec thereafter being the record.
> The list is deliberately short. This spec has already run the deletion argument to a fixed point across eighteen sections; what remains are places the argument was **not run**, not places it was run and got the wrong answer.

## The simplification gate

An item earns a place on this list iff it clears all five:

1. **Deletes specification or proof surface** — Sail semantics, a proof obligation, a state inventory entry, a `fence.t` flush-set member, or a hedge — measurably, not rhetorically.
2. **Costs nothing in performance, or gains.** A deletion that trades cycles for surface belongs in [performance-estimates.md](performance-estimates.md) as an accepted cost, not here. This is the gate that rejects most candidates.
3. **Sheds no security property.** Every theorem the spec claims still holds, unchanged.
4. **Follows the spec's own stated grounds** — *delete rather than defend* (R-15-012), *verify rather than hedge* (R-15-013), or the *no consumer* parsimony that cut `Zacas` (R-15-026) and `Zifencei` (R-15-047) — rather than inventing a new principle to justify itself.
5. **Reduces, never relocates.** A deletion that reappears as a software obligation, a new checker, or a hand-waved assumption has moved the cost, not paid it.

**Why gate 4 matters.** Every item below is an application of a rule the spec already states to a case the spec did not reach. That is the difference between a simplification and a redesign: none of these asks §15 to change its mind, and each can be argued from a requirement already in the register.

---

## 1. Collapse the `fence` encoding space

- [ ] **Reduce `fence` from 256 encodings to the two (at most four) behaviors the machine can actually exhibit.**
  RISC-V `fence` carries `fm[3:0]`, `pred[3:0]`, `succ[3:0]`, with predecessor and successor sets each drawn from `{PI, PO, PR, PW}` — 256 pred/succ pairs, plus `fence.tso` as a distinguished `fm`.
  This machine's ordering set is fully determined by three facts already in the register: in-order issue gives load→load and load→store, the FIFO store buffer gives store→store (R-15-015), and single-copy memory with the bank arbiter as the order-determining point gives store atomicity (R-15-087). The **only** relaxation is store→later-load bypass.
  So a `fence` is observable iff its predecessor set includes a write and its successor set includes a read; every other encoding — all of `r,r`, `w,w`, `r,w`, and their I/O variants — is architecturally a **no-op on this platform**, and `fence.tso` is indistinguishable from the machine's steady state.
  Two behaviors exist (drain, nop), or four if device stores travel a path distinct from SRAM stores and the `PI`/`PO` axis therefore separates. Not 256.
  *Grounds (gate 4):* this is verbatim the argument §15 already makes for dropping RVWMO — *"keeping RVWMO would only impose its heavier reasoning burden on every proof for behaviors the hardware cannot produce"* (R-15-004). The pred/succ set lattice is that burden's remaining half: it is RVWMO's vocabulary, retained on a machine that cannot make the distinctions it expresses.
  *Perf:* neutral. Every collapsed encoding is already a no-op; the drain case keeps the cost it has.
  *Deletes:* the pred/succ lattice from the Sail memory-ordering rules, the `fm` field's semantics, and the fence-set case analysis from every ring proof (R-12-008) and from the §17 litmus obligations.
  *Touches:* R-15-017 (which currently retains `fence` generically), R-12-008's acceptance criterion, R-15-061, R-15-015a (whose coverage the device case turns on, below).

  **Two adjacent claims to re-derive rather than inherit.** Both are stated in the register as though `fence` were load-bearing, and under TSO on single-copy memory neither obviously is:
  - **R-12-008's "under Ztso *with fences included*."** A bounded SPSC ring needs release-store and acquire-load semantics (R-15-026), and on this machine both are **free**: release needs load→store and store→store, acquire needs load→load and load→store, and all four are given. The producer's *check tail → write data → write head* and the consumer's *read head → read data → write tail* contain no store→load edge. If that holds, the ring proof needs no fence at all, and its acceptance criterion is over-specifying the hardware.
  - **R-15-061's "cross-island ring ordering is a plain `fence`."** Cross-island rings live in shared SRAM (R-15-223), and shared SRAM is the same single-copy memory under the same TSO. The fence there is either unnecessary for the same reason, or it is standing in for the fabric-ordering property R-15-015a makes an explicit obligation — in which case it is a fence papering over an interconnect guarantee, which is the wrong place to pay for it.

  **The last consumer, and where it actually lives.** If both re-derive as fence-free, `fence`'s sole surviving consumer is device ordering — MMIO and DMA-descriptor visibility (R-15-017) — and the cut becomes the same *no consumer* deletion that took `Zacas`. But that consumer is misdescribed by its own name, and the misdescription is what makes it look expensive to retire.

  DMA-descriptor visibility is not a *device-store* ordering problem. The descriptors are ordinary SRAM writes; only the doorbell is a device write. The edge that must hold is therefore **SRAM store → device store**, and TSO gives store→store architecturally. What does not obviously follow is the implementation side: R-15-015a states the fabric obligation over "banks, macros, and shared cross-island ring windows" — **device endpoints are not in that list**. That omission, not buffering, is the whole of why the `PI`/`PO` axis survives into the four-behavior count above.

  *Preferred discharge — extend R-15-015a to device endpoints.* Per-hart program order preserved to a device endpoint exactly as to a bank makes descriptor-before-doorbell structural, retiring the consumer outright.
  - *Perf:* neutral. It constrains a TDM schedule at composition time, which is where R-15-015a already says the property is preferentially discharged — not a term paid per store at runtime.
  - *Deletes:* more than the non-bufferable route does. The `PI`/`PO` axis goes with it, collapsing this section's "two, or four" back to an unqualified **two**, and folding I/O ordering into the one memory model rather than leaving it in the sidecar RISC-V keeps it in.
  - *Residual:* device store → device load — the MMIO read-back — is the one genuine store→load edge left, and it is closed by a local store-buffer rule (device-space stores do not forward to loads), not by an architectural change to when a store completes.
  - *Grounds (gate 4):* this is R-15-015a's own move, applied to the endpoint class it did not reach — naming a fabric obligation instead of buying the ordering with an instruction. Same shape as R-15-061's diagnosis one bullet up: a fence papering over an interconnect guarantee is paying in the wrong currency.

  *The non-bufferable variant, rejected.* Making device-space stores architecturally non-bufferable is the stronger-looking alternative, and it is **worse on both gates that matter**:
  - It **does not retire the descriptor consumer** it was proposed for. Non-bufferable device stores leave the *SRAM* stores in the buffer, so the descriptor→doorbell edge is exactly as unordered as before. It closes the read-back hazard and nothing else — which the forwarding rule above closes for free.
  - It **fails gate 2**, where the fabric route does not. Cost is concentrated, not diffuse: MMIO configuration is cold-path by construction (R-15-140), and doorbells are already per-batch under R-11-010's ring-depth amortization rather than per-item. The one class that pays is **MSI sends**, which R-15-064 and R-08-032 make device-space stores on the cross-core notification path — and the mitigation there is the batching-at-the-source that [performance-recovery-todo.md](performance-recovery-todo.md) §1's ring-window lever already prescribes for the same traffic. Bounded and largely recoverable, but a cycle cost bought for a guarantee the composition-time route supplies at none.

  Recorded as **considered and rejected in favor of the fabric obligation**, not as a live trade.

---

## 2. Freeze `vtype`

- [ ] **Enumerate the admissible vector configurations and freeze them with the profile, as the profile already freezes the extension set.**
  `vtype` is the one configuration space the freeze did not reach. `SEW ∈ {8,16,32,64}` × `LMUL ∈ {1/8,1/4,1/2,1,2,4,8}` × `vta` × `vma` is 112 reachable configurations plus `vill`, and unlike an extension it does not *add* to the instruction count — it **multiplies into the semantics of every vector instruction in the profile**. On a machine whose vector unit carries graphics, ML, DSP, and crypto (R-15-115), that is plausibly the largest single block of Sail surface left anywhere in the ISA.
  The register reaches it exactly once, incidentally, and only through Keccak element-group geometry (R-15-059a). No requirement constrains it.
  The proposal: enumerate the configurations the named kernels actually use, freeze that set, and trap the rest — dropping **fractional LMUL** outright, fixing **one tail policy and one mask policy**, and making `vill` unreachable by construction rather than a state the model must carry.
  *Grounds (gate 4):* R-15-014 already mandates that reserved and unused encodings trap rather than silently executing, and R-15-001a's complaint about the extension set — that without an enumeration the criterion *"names an artifact a reviewer cannot open"* — applies word for word to `vtype`. This is that requirement's own logic, applied to the space it did not cover.
  *Perf:* neutral for every workload the spec names. GEMM, table-free vector crypto, the NTT, and codec kernels each fix SEW and LMUL per kernel; none needs runtime agility across the full space. `vill` is unreachable on a machine that traps illegal encodings anyway.
  *Costs, honestly:* fractional LMUL is the convenience path for mixed-width arithmetic (widening and narrowing chains), so dropping it costs some register pressure and a few extra moves in mixed-precision code. That is a code-generation cost paid off-device by the untrusted optimizer, not a cycle cost on a hot loop — but it is a real cost, and the enumeration should be chosen from measured kernels rather than from taste.
  *Deletes:* the tail/mask policy cross-product, the fractional-LMUL register-addressing rules, and `vill` from the Sail model, and collapses the per-class geometry claims (R-15-059a's LMUL=8-at-VLEN=256 sharp edge becomes a frozen case rather than a discovered one).
  *Blocks on:* choosing the set, which needs the kernels. Sequence it after the first vector kernels exist, not on day one.

---

## 3. Delete `Zicntr` / `Zihpm` instead of permission-gating them

- [ ] **Replace the counter-read permission with the lifecycle fuse the Debug Module already uses.**
  R-15-077 keeps `Zicntr` and `Zihpm` in the profile, unreadable without the counter-read permission on the PCC, with hpm events sentinel-only. That is a **hedge**: a mechanism retained and then gated, whose gating must be modeled, whose permission bit consumes capability encoding space, and whose "sentinel-only" event restriction is an argument that has to be made and audited rather than a structure that can be checked.
  *Grounds (gate 4):* *verify rather than hedge* (R-15-013) declines exactly this shape — a second modeled mechanism spending the scarce axis to buy down a risk. And the timing-oracle risk the gate exists to manage is the one this platform is otherwise structurally free of: cycle counters are the last general-purpose measurement instrument on a machine that deleted every other one.
  *The substitute already exists.* R-15-078 lifecycle-fuses the Debug Module at the hardware level — clock and reset gated off, fabric port electrically quiesced in the production state, with *no DM transaction reaches the fabric* as a stated RTL ⊑ Sail obligation. Cycle measurement wants exactly that treatment: present and readable in development states where WCET-table validation happens, electrically absent in production. Reusing a mechanism the spec already builds and already proves is strictly cheaper than maintaining a second, softer gate beside it.
  *Perf:* neutral. Neither counter is on any hot path, in the kernel or out of it.
  *The obvious objection, answered:* `rdtime` lives in `Zicntr`, so deleting the extension appears to delete timekeeping. It does not — the platform's clock is `mtime`/`mtimecmp`, programmed directly by the kernel (R-15-063), and the time-service compartment (§9) reads it there. Nothing in the scheduling or timeout path needs `rdcycle`.
  *Deletes:* the counter CSRs, one CHERI permission bit, the hpm sentinel-event argument, and the counter-read branch of the §8 *clock read-out is authority* reasoning.
  *Touches:* R-15-077, and the CHERI permission table in [isa-profile.md](isa-profile.md) §4.

---

## Not a simplification, but adjacent

- [ ] **Add the invariance clause to R-15-018's SC rejection.**
  The four grounds against sequential consistency are sound, but they do not say what they are invariant under, and the first challenge a reviewer will bring is the natural one: *does this change at low core counts, or with fewer and beefier cores?* It does not, and the reason is already in the register — R-15-087's single-copy memory makes the deviation from SC **local** (each hart's own store buffer) rather than coherence-borne, so there is no traffic term for hart count to scale, and wider issue makes SC's per-load stall *worse* rather than better by deepening the buffer it must drain.
  One clause naming that closes the challenge. Ground (4) can be sharpened with the same citation: on single-copy memory the model contains exactly one relaxation, so what SC deletes is smaller than (4) currently claims — which strengthens the rejection rather than weakening it.
  *Not on the numbered list because it deletes nothing;* it makes an existing argument survive its first review.

- [ ] **Settle whether a device store can sit in the store buffer across a `fence.t`.**
  R-15-218 states the padded constant's worst case as "the store buffer's drain latency at the class's depth **and memory bandwidth**." That phrasing assumes every buffered store is bound for SRAM. If device-space stores are bufferable — and nothing in the register says they are not — then a partition holding an MMIO write to a slow endpoint makes the drain's worst case that endpoint's accept latency instead, and the eUICC's ISO7816 block, clocked off a divided card clock (R-12-046), is an existence proof that such an endpoint is on the die.
  Either device stores are already implicitly excluded from the buffer and no requirement says so, or **R-15-218's constant is understated and R-15-220's three-term switch cost inherits the error** — which would put a device's response time inside a bound the design needs to be a function of the *class*, not of what the outgoing partition was talking to.
  *Not on the numbered list because it deletes nothing either;* it is a question about a stated bound, and it wants an answer whether or not §1 is ever adopted. The answer may also close §1's read-back residual for free: if device stores never enter the buffer, the no-forwarding rule is vacuous.

---

## Considered and rejected

Recorded so they are not re-proposed. Each fails a specific gate.

| Proposal | Fails | Why |
|---|---|---|
| **Sequential consistency** (at any core count or width) | 2, 4 | Grounds (1)–(4) of R-15-018, none of which has a hart-count term. Ground (3) is decisive and invariant: it trades a *structural* obligation (a FIFO cannot expose ordering weaker than TSO, bookable in the absence contract) for an *interlock-correctness* obligation (no load bypasses the drain, on any path, proven present and complete), which runs *delete rather than defend* backwards. Wider cores make it worse, not better. |
| **Delete hardware integer DIV/REM**, do it in software | 2 | [performance-estimates.md](performance-estimates.md) already books −1% to −6% for the always-worst-case fixed-latency divider (R-15-080). Shift-subtract or Newton–Raphson in software is several times that latency; the deletion buys one datapath unit and one timing-contract row for a real cycle loss. |
| **Delete vector masking** | 2 | Tempting because R-15-085 mandates mask-*independent* timing, so masking buys no cycles — but if-converted vector code then needs explicit merges, which need masks to generate. The surface returns as instructions and the cycles go negative. |
| **Collapse the three VLENs to one** | 2 | VLEN is where the vector performance argument lives (R-15-113, R-15-115). Real surface win, real perf loss; belongs in the multi-objective DSE trade the spec already specifies (§15, [implementation-plan.md](implementation-plan.md) §1), not here. |
| **Delete indexed gather/scatter and segment load/store** | 2 | Large surface with per-element capability checks (R-15-115), but segment load/store is the AoS↔SoA path the radio and codec kernels on the V-class need most. Deleting it moves the cost into every kernel's inner loop. |
| **A hardware store-buffer bypass predictor**, or any dynamic ordering optimization | 3, 4 | Hidden state that survives a partition switch; fails admission test 3 outright (R-15-011). Already out of scope in [performance-recovery-todo.md](performance-recovery-todo.md). |
| **Architecturally non-bufferable device stores**, as the route to deleting `fence` | 2 | Superseded by §1's fabric-obligation route, which retires the same consumer at composition time. Two defects: it does not order the SRAM-store→doorbell edge it was proposed for (those stores stay buffered), and it puts a NoC round-trip in every MSI send (R-15-064, R-08-032). Kept only as the fallback if extending R-15-015a to device endpoints proves infeasible in the NoC schedule. |
