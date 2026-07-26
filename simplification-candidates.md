# Simplification Candidates (non-normative)

> Companion to [verification-maximal-os.md](verification-maximal-os.md) and [isa-profile.md](isa-profile.md).
> Where [performance-recovery-todo.md](performance-recovery-todo.md) enumerates levers that buy **performance** at no cost on the scarce axis, this doc enumerates levers that buy **the scarce axis itself** — specification and proof surface — at no cost in performance.
> Both lists exist because the design's premise ("engineering is free; trust is the scarce resource") makes the two currencies non-interchangeable: a deletion that shrinks the Sail model and the proof burden is worth pursuing even when it recovers not one cycle, and *especially* when it recovers cycles too.
> Nothing here is normative. Each item is a proposal against the frozen profile, and adopting one is a profile amendment that reruns the review gate (R-18-034).
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
  *Touches:* R-15-017 (which currently retains `fence` generically), R-12-008's acceptance criterion, R-15-061.

  **Two adjacent claims to re-derive rather than inherit.** Both are stated in the register as though `fence` were load-bearing, and under TSO on single-copy memory neither obviously is:
  - **R-12-008's "under Ztso *with fences included*."** A bounded SPSC ring needs release-store and acquire-load semantics (R-15-026), and on this machine both are **free**: release needs load→store and store→store, acquire needs load→load and load→store, and all four are given. The producer's *check tail → write data → write head* and the consumer's *read head → read data → write tail* contain no store→load edge. If that holds, the ring proof needs no fence at all, and its acceptance criterion is over-specifying the hardware.
  - **R-15-061's "cross-island ring ordering is a plain `fence`."** Cross-island rings live in shared SRAM (R-15-223), and shared SRAM is the same single-copy memory under the same TSO. The fence there is either unnecessary for the same reason, or it is standing in for the fabric-ordering property that R-15-015a now makes an explicit obligation — in which case it is a fence papering over an interconnect guarantee, which is the wrong place to pay for it.

  If both re-derive as fence-free, `fence`'s sole surviving consumer is MMIO and DMA-descriptor visibility, and the cut becomes the same *no consumer* deletion that took `Zacas`. A stronger version then opens: make device-space stores architecturally non-bufferable, which retires the last consumer and deletes the instruction. That version is **not** perf-neutral — device stores become synchronous — so it is a separate trade, recorded here and not proposed.

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

## 4. Enumerate the surviving CSR set

- [ ] **State the CSRs that remain, as a frozen table in the profile view.**
  Not a simplification in itself — the enabling artifact for several. §15 enumerates the **deleted** CSR banks exhaustively and admirably (the S-mode bank by name, `medeleg`/`mideleg`, `frm`, `mstateen`, `srmcfg`, `Zkr`'s entropy CSR, `scounteren`), but nowhere states the set that **survives**. `misa` is read-only (R-15-052), the trap registers are capability-typed (R-15-073), `mtimecmp` is present (R-15-063), the counters are gated (R-15-077), and `vtype`/`vl`/`vstart`/`vxrm`/`vcsr` are implied by RVV — but there is no table, so no reviewer can decide membership.
  *Grounds (gate 4):* this is precisely the defect R-15-001a diagnosed for the extension set, in a space the derived views do not cover. The same fix applies: a table, in the profile view, with a governing requirement per row.
  *Perf:* neutral by construction.
  *Why it belongs on this list:* a `Zicsr` surface nobody has enumerated is a surface nobody has minimized. Expect the table itself to expose deletions — `vstart` in particular is mutable per-instruction state that survives a trap and therefore has a `fence.t` and partition-switch story that should be written down whether or not it is deletable, and `vxrm`'s dynamic rounding mode is the vector sibling of the `frm` CSR that R-15-083 already deleted for being dynamic.
  *That last observation is the strongest reason to write the table.* R-15-083 mandates static, per-instruction floating-point rounding and deletes `frm` so that *"no mutable rounding-mode state context-switches or joins the fence.t set."* If `vxrm` (fixed-point rounding) is in the profile unexamined, that requirement has a live counterexample sitting next to it.

---

## Not a simplification, but adjacent

- [ ] **Add the invariance clause to R-15-018's SC rejection.**
  The four grounds against sequential consistency are sound, but they do not say what they are invariant under, and the first challenge a reviewer will bring is the natural one: *does this change at low core counts, or with fewer and beefier cores?* It does not, and the reason is already in the register — R-15-087's single-copy memory makes the deviation from SC **local** (each hart's own store buffer) rather than coherence-borne, so there is no traffic term for hart count to scale, and wider issue makes SC's per-load stall *worse* rather than better by deepening the buffer it must drain.
  One clause naming that closes the challenge. Ground (4) can be sharpened with the same citation: on single-copy memory the model contains exactly one relaxation, so what SC deletes is smaller than (4) currently claims — which strengthens the rejection rather than weakening it.
  *Not on the numbered list because it deletes nothing;* it makes an existing argument survive its first review.

---

## Considered and rejected

Recorded so they are not re-proposed. Each fails a specific gate.

| Proposal | Fails | Why |
|---|---|---|
| **Sequential consistency** (at any core count or width) | 2, 4 | Grounds (1)–(4) of R-15-018, none of which has a hart-count term. Ground (3) is decisive and invariant: it trades a *structural* obligation (a FIFO cannot expose ordering weaker than TSO, bookable in the absence contract) for an *interlock-correctness* obligation (no load bypasses the drain, on any path, proven present and complete), which runs *delete rather than defend* backwards. Wider cores make it worse, not better. |
| **Delete hardware integer DIV/REM**, do it in software | 2 | [performance-estimates.md](performance-estimates.md) already books −1% to −6% for the always-worst-case fixed-latency divider (R-15-080). Shift-subtract or Newton–Raphson in software is several times that latency; the deletion buys one datapath unit and one timing-contract row for a real cycle loss. |
| **Delete vector masking** | 2 | Tempting because R-15-085 mandates mask-*independent* timing, so masking buys no cycles — but if-converted vector code then needs explicit merges, which need masks to generate. The surface returns as instructions and the cycles go negative. |
| **Collapse the three VLENs to one** | 2 | VLEN is where the vector performance argument lives (R-15-113, R-15-115). Real surface win, real perf loss; belongs in the DSE trade (already `[x]` in [performance-recovery-todo.md](performance-recovery-todo.md) §2), not here. |
| **Delete indexed gather/scatter and segment load/store** | 2 | Large surface with per-element capability checks (R-15-115), but segment load/store is the AoS↔SoA path the radio and codec kernels on the V-class need most. Deleting it moves the cost into every kernel's inner loop. |
| **A hardware store-buffer bypass predictor**, or any dynamic ordering optimization | 3, 4 | Hidden state that survives a partition switch; fails admission test 3 outright (R-15-011). Already out of scope in [performance-recovery-todo.md](performance-recovery-todo.md). |
