# VerifiedOS — action list from the 2026-09-06/07 review

Repo state: `symbiogenesis/VerifiedOS` @ **`94a6e27`** (2026-09-07, "Stop the spec calling the no-C code-size cost accepted, and re-anchor the rule that pinned it by that word").

Scope: NFC/Tap-to-Pay, Wayland, RCS, recent GrapheneOS, MesaOS, Wasmi 2.0, ASIC-like acceleration, OpenAI Jalapeño, plus a literature pass (RISC-V matrix TGs, ternary-weight LLMs, gain-cell CIM) and the NX-bit / speculative-fetch post.

**Convention:** each item names the artifact it lands in and the requirement it touches. `NEW` = nothing in the register covers it. `AMEND` = an entry exists and this changes or prices it. `NO-ACTION` = adjudicated; recorded so the question does not get re-asked.

---

## Changes in this revision

Pulled forward from `0df746e` (5 commits: M1.2b backend partial, a six-claim audit repair, findings recount, the laptop/desktop first-class budget correction, and the "accepted" re-anchor). Two of them touch this list, and one thing I had missed in the first pass turns out to govern T-04.

| Change | Effect |
| --- | --- |
| **`0df746e` §15 already retires the RVY re-pin** — "the dialect is permanently bespoke, no standards-track re-pin target is recorded for it… it spends oracles, not a badge" | **T-04 reframed.** I missed this in the first pass. The argument for tracking the matrix TGs cannot be standards-conformance-as-virtue; it has to be made on the oracles axis, which is the axis §15 itself names. Scope check below: that retirement is bound to the capability *encoding*, not to the profile generally. |
| **NX-bit post (2026-09-04)** | **T-18 new** (three sub-items), **T-19 new**, **T-03 amended** with an explicit boundary. |
| `726e4ba` laptop/desktop first class **16–32 GB → 8–16 GB** | Context for T-01 only. The inference floor sits on the *second* class (region 4 at `0x100000000`, 8 GB) and R-18-004b's ≥4 GB payload floor is untouched. |
| `1e32d7f`, `3f8107a`, `7680d98` — M1.2b backend partial (merged register file, scalar FP deleted, capability encoding closed), 627 findings across 98 items | No effect on this list. Noted so the pin is legible. |

---

## Priority ordering

| # | Item | Why first |
| --- | --- | --- |
| 1 | [T-18] Wrong-path fetch reach as an absence-contract obligation | Free to state (already true in every composition), closes a class the model structurally cannot see, and gets cheaper the earlier it lands — every new aperture is a chance to forget it. |
| 2 | [T-01] Ternary weights against the R-18-004a(vii) inference floor | Touches a first-release floor, the R-18-004b bandwidth floor, and the R-15-116 margin denominator at once. Cheapest measurement, largest consequence. |
| 3 | [T-02] Prefill/decode as two composed assignments | Closes an unmodelled term in R-12-085's ceiling using a mechanism (R-15-188) that already exists. No new surface. |
| 4 | [T-03] Wasmi 2.0 port with the branch-site inversion | Bring-up interim is on the path to M6; the inversion is a correctness-of-measurement issue, not just a speed one. |
| 5 | [T-04] RISC-V matrix extension standards track (AME/IME/VME) | Bears on the profile's largest block of net-new Sail surface. Now argued on oracles, per §15's own retirement language. |
| 6 | [T-05] SMS/MMS and the messaging gap | First release ships cellular and has no messaging story at all. |
| 7 | Everything else | Documentation and scoping, not critical path. |

---

## 0. Fetch reach *(new this revision)*

### [T-18] `NEW` Wrong-path fetch reach belongs in the absence contract, not among the refinement obligations
**Lands in:** `docs/absence-contract.md` §3/§5, `docs/requirements-register.md` (R-15-022, R-15-104, A-07), `model/config/*.json`

**The mechanism from the NX post cannot happen here; the lesson reaches by a different route.** Sonya's hang needs a mispredicted *indirect* branch — `blr x0` speculating to an invented target that happened to be a locked-out bootrom at `0x0`. With no BTB and no RAS (A-05, A-06) an indirect jump has nothing to predict from and the fetch buffer stalls, so that exact bug is structurally unreachable. But R-15-022 reads *"fetch runs ahead only down the statically determined path, so wrong-path fetch is a deterministic function of the instruction stream and never of prior execution history"* — it **names wrong-path fetch and bounds its determinism, not its reach**. R-15-104 then decides the prefetcher boundary by table-freeness, "not by size **or run-ahead depth**." Sequential run-ahead past the end of a code region is therefore admitted, unbounded in depth, and nothing says which addresses it may touch.

**Determinism cuts the wrong way here.** The post's bug was intermittent because prediction is history-dependent. The equivalent here would fire on every run, on every die, precisely *because* R-15-022 guarantees the wrong path is a fixed function of the instruction stream. R-15-022 currently frames that determinism as a security property (no history channel); determinism of reach and safety of reach are orthogonal, and the requirement should say so.

- [ ] **(a) Add the row.** The property is not expressible in an architectural model — the Sail model has no fetch buffer and no run-ahead, so `pmaCheck` is only ever reached by an *architectural* fetch. That is R-15-098's own situation verbatim: not expressible in the model the refinement is against, therefore an absence obligation rather than a refinement obligation. Add a row (or extend §5's decision rule) covering **which addresses a fetch-path structure may emit a transaction to**, alongside A-07's existing coverage of *which structures may exist*. §5's rule as written admits a structure that passes every table-freeness test and still emits an off-path bus read.
- [ ] **(b) Make the invariant normative — it is already true, so it is free.** You already carry both halves of the ARM pair, and better placed than ARM does: `read_idempotent: false` is the Device-memory analog (no speculative *data* access) and `pmaCheck`'s `InstructionFetch() => attributes.executable` (`model/model/sys/mem.sail:102`) is the NX analog (no speculative *instruction* access). The post's punchline is that you need both. **All three compositions already satisfy `mem_type == IOMemory ⟺ executable == false`, with zero exceptions:**

  | base | `mem_type` | `executable` | `read_idempotent` |
  | --- | --- | --- | --- |
  | `0x1000` | IOMemory | false | true |
  | `0x2000000` | IOMemory | false | **false** |
  | `0x80000000` | MainMemory | true | true |
  | `0x100000000` | MainMemory | true | true |

  Identical in `verifiedos.json`, `verifiedos-v.json` and `verifiedos-rot.json`. Turn the repeated judgment into a rule: **no `IOMemory` region is executable, and no composition may grant executability to one.** A schema constraint plus a `run.py` rule; costs nothing today, and makes the whole failure class unrepresentable for every aperture the map gains later — concretely including the NFC front end at [T-06], which is exactly the kind of new region where a per-region judgment gets forgotten. F-229g is already open on a window with no stated extent; a total rule is cheaper than getting each one right.

  Note it is stronger than ARM's situation in one further way: `matching_pma_region` returning `None()` is an access fault, so an address in no declared region faults rather than reaching a bus. The post's `0x0` had a 1:1 mapping underneath it; you have no such thing.
- [ ] **(c) Give the boot ROM's disposition its second, non-contingent ground.** M0's decode landing already decided this correctly — the region "stays readable and not executable, and the attested devicetree sharing it stays non-executable with it" — but the ground recorded is that R-09-006 puts the verified M-mode image in main SRAM, so *nothing on this die fetches from `platform.boot_rom`*. That is a fact about the current boot flow. Defeat the flow and you defeat the ground: someone proposing a bring-up path that does fetch from ROM gets the executable bit back and silently loses a protection nobody wrote down. The post's ground does not depend on the boot flow: **non-executable is the only control over what a fetch-path structure may reach at all.** Two independent grounds is a materially stronger disposition than one.
- [ ] **(d) Check the `fence.t` interaction.** The absence contract classifies the static-path fetch buffer as stream-determined pipeline state, "emptied by the fence's pipeline drain." That covers the *state*; it does not obviously cover a bus transaction the run-ahead already emitted. The store-side reasoning is already written — a compartment's bound is set by the slowest endpoint its capabilities can *reach*, with the eUICC's divided-clock ISO7816 block as the on-die existence proof that such an endpoint exists. The same argument transfers to reads: if run-ahead can emit a fetch toward a slow endpoint, that endpoint's read latency lands in the `fence.t` bound. Item (b) disposes of this too, which is a second reason to prefer the rule over case-by-case.

### [T-19] `NEW` Discharge a removal against every property the structure carried, not only the one it is named for
**Lands in:** `docs/absence-contract.md` §3 (ground-column convention), or the *verify rather than hedge* clause in `docs/spec.md`

The post's actual punchline is methodological: NX was filed as a security mechanism and turned out to be load-bearing for **correctness**, because on ARM it is the only control over speculative fetch reach. Your governing maxim is *verify rather than hedge* — PMP, the IOMMU and MTE are declined precisely because they are defence-in-depth. This is a clean case study in that maxim's failure mode: **a mechanism declined because its stated purpose is redundant may be carrying a second, unstated, non-security purpose.**

- [ ] Add the discipline as a convention: when a removal is discharged, discharge it against **every** property the structure carried in its origin architecture, not only the property it is named for. A sentence in §3's ground-column convention, not a workstream.
- [ ] The design already knows how to do this in the other direction — the physical cutoffs (R-15-145) are admitted under the same clause exactly because they cover a domain the gates' own verification does not reach. What is missing is the symmetric rule for removals.

---

## 1. Inference and acceleration

### [T-01] `AMEND` Re-open the inference floor's quantization choice against ternary weights
**Lands in:** `docs/inference-demand.md`, `docs/requirements-register.md` (R-18-004a(vii), R-18-004b, R-12-085, R-15-247p)

The register already cites BitNet b1.58 — but only inside `architectural-alternatives.md` §"Ternary and multi-valued logic", as a *rebuttal to ternary logic* ("the win has nothing to do with a ternary transistor"). The citation was never followed through to the inference floor, and it should be.

- [ ] Re-derive static demand for a natively-trained ternary model against the same predicates §5 already uses (weight bytes, bytes read per generated token, KV footprint, resident buffers at 8,192 context).
- [ ] Score against R-18-004b: ≥4 GB usable second-class payload, ≥8 GB/s sustained second-class read to the M-class island, ≥20 GB/s aggregate. Decode is bandwidth-bound and bytes-per-token is this document's own load-bearing figure, so ~1.58 bits/weight against the current 4-bit row is a direct ~2.5× move on the binding term.
- [ ] State the consequence explicitly: either the R-18-004b read floor drops, or the R-15-247p bank grant buys a higher admitted token rate. Both are register-visible outcomes.
- [ ] Record the honest constraints beside it: ternary requires quantization-aware training from scratch (no post-hoc conversion), the official BitNet b1.58 model is 2.4B and therefore *below* the 3B floor, and the licence and publisher-conversion discipline §3 applies to Qwen3-4B must be re-run on any candidate.
- [ ] Note the second-order effect on R-15-117: with ternary weights, de-quantization collapses to sign-select and the multiply collapses to add/sign/zero-skip, which changes what the software front end is actually doing.
- [ ] *(context, `726e4ba`)* The first-class budget moved to 8–16 GB for laptop/desktop. The inference floor sits on the second class, so nothing here changes — but if a future composition rebalances the classes, this measurement is the one that reprices.

### [T-02] `NEW` Prefill and decode are two modes, not one composed assignment
**Lands in:** `docs/spec.md` §12 (R-12-085), §15 power architecture (R-15-188), `docs/requirements-register.md`

R-12-085 names the ceiling's terms and R-15-247p makes the token rate a composition-time constant of the bank grant — a *single* constant. But prefill is compute-bound and decode is memory-bandwidth-bound, so a grant sized for decode over-provisions bandwidth for prefill and one sized for prefill misses the decode floor.

Two independent 2026 sources land on this asymmetry as the defining feature: Jalapeño is architected around activating different combinations of compute, memory and networking per phase, and the edge-FPGA ternary-LLM literature reports prefill dominated by matmul throughput and attention compute while decode is dominated by weight and KV-cache memory traffic — with at least one design swapping the logic itself between the two phases.

- [ ] Make the inference server's composed assignment **two-valued** (prefill, decode), with the transition an ordinary R-15-188 partition-boundary OPP change: divider ratio and rail set-point reprogrammed from the composed assignment, no control loop, no new mechanism.
- [ ] Extend R-12-085's declared ceiling terms so the bank grant and admitted rate are stated per phase.
- [ ] Confirm the transition is priced in the §11 switch-duty accounting and does not push the inference server toward pinning.
- [ ] `inference-demand.md` §1 disowns its depth-8192 rows and states the two deciding passes run at depth 0 in one cache format — the controlled `-d 0,8192` invocation in both cache formats is exactly the measurement this item needs. Fold the asks together rather than running the host twice.

### [T-03] `AMEND` Port Wasmi 2.0 into the R-14-013a bring-up interim
**Lands in:** `docs/userspace-porting.md` (line ~322), `docs/requirements-register.md` (R-14-013a/b/c)

**Adopt outright — hardware-agnostic wins:**
- [ ] **Accumulator registers** (`ireg` / `freg32` / `freg64`). Operands and results in real hardware registers, no decode/load/store per instruction. Reduces stack traffic, which helps both the R-14-013 bounded pool and the WCET max-path sum.
- [ ] **Flattened `InstanceEntity`** — one contiguous handles buffer, instance *addresses* rather than Wasm indices, so an object access is one pointer offset instead of a three-deep dependent chain. **Worth more here than upstream measured:** with no I-cache or D-cache (A-09/A-10), flat SRAM at fixed latency, in-order issue and no prefetcher (A-07), every link in the old chain was fully exposed. Treat upstream's figure as a lower bound.
- [ ] **Append-only function buckets that never reallocate or move**, letting body pointers be baked into the bytecode. Stable addresses are what a static memory plan yields; fits R-08-010's no-online-allocator rule and R-14-013's declared bounded pool.
- [ ] **Fixed 64-bit cells** with `v128` as two adjacent cells. Cleans up pool sizing and removes the width penalty widening imposed on non-vector values.
- [ ] **The `validate` feature and binary-size knobs.** Relevant to the executable SRAM budget (R-13-010a/b/c) and therefore to the `Zifencei` / static-code-overlay trigger the absence contract holds.
- [ ] **The WebAssembly deterministic profile.** The sleeper item: it narrows R-14-013b's version-frozen pinned semantics and shrinks what §16's replay nondeterminism record has to carry. File it as a pinned-semantics amendment, not a config flag.

**Price rather than assume:**
- [ ] **Direct-threaded dispatch.** It embeds handler function pointers into the IR, so under purecap the IR buffer becomes tag-carrying memory and every dispatch is an indirect jump through a capability loaded from data. Sentries are no longer optional upstream — `Zysentry` folded into the RVY base at v0.9.9 per `cheri-version-matrix.md` — so the mechanism exists, and the target set being exactly the sealed sentry set is arguably *cleaner* than a jump table. But typing the IR's capability fields in the CHERI-TAL derivation is net-new admission surface and must be booked.
- [ ] It also needs guaranteed tail calls. Rust's `become` is still unstable; upstream works around it with a dispatch macro. The certifying Rust→RV64+CHERI toolchain has to provide the guarantee and the TAL has to type it. **Default to indirect-threaded** (≈10–15% slower, significantly smaller IR, *no code pointers in data at all*) until the sentry typing is priced.
- [ ] **`AMEND` State the boundary explicitly, because it is one instruction wide.** *(new this revision)* The NX post's *first* bug was sorting a table of executable machine code at runtime on an I/D-incoherent machine. That class is already deleted here: `Zifencei` is excluded (R-15-047, for want of a runtime write-then-execute consumer) and W^X forbids on-device codegen. Direct threading is the near-miss: it builds a table of code *pointers* at translation time, which on this machine is sentry **capabilities in tagged data**, not instructions — so it is not a `Zifencei` consumer and the class stays deleted. Write that into the disposition. A threading scheme that inlines handler *bodies* into the buffer rather than pointers to them has rebuilt the post's first bug and tripped the static-code-overlay trigger the absence contract holds against `Zifencei`, and the difference between the two is not visible in a benchmark.

**The inversion — do this before any upstream number informs `performance-estimates.md`:**
- [ ] Wasmi 2.0's single largest win (~2800 → ~4200 CoreMark, ~50%) came from *un*-collapsing a `csel` back into two branch sites, because one unified branch site gives a dynamic predictor a single entry with mixed history. **You have no BHT, no PHT, no BTB and no RAS** (A-04, A-05, A-06); prediction is static-only with zero mutable predictor state. On this die the branch-free `csel` form has no conditional branch to statically mispredict *and* is data-independent in timing — what R-15-101's hyperproperty and the CT taint discipline both want. Measure, then expect to **revert the upstream fix on port**.
- [ ] Generalize into a porting note: any interpreter result that improves by feeding a branch predictor is measuring hardware this machine does not have. The whole `wasmi-benchmarks` ranking needs re-reading under A-04/A-05/A-06 before it informs a figure anywhere in the tree.

**Roadmap:**
- [ ] Wasmi 3.0 targets `function-references`, `exception-handling` and `gc`. Wasm GC as specified is not a declared bounded pool with fixed size classes, a maximum live object count per class, a declared selection and release algorithm, and a complete WCET and non-interference model — which is what R-14-013 requires. R-14-013b already pins a version; **write down that 3.0 is the version the pin declines**, not the one it has yet to reach.

### [T-04] `NEW` Track the RISC-V matrix extension TGs — argued on oracles, not on conformance
**Lands in:** `docs/architectural-alternatives.md`, `docs/isa-profile.md`, `docs/cheri-version-matrix.md`

> **Reframed this revision.** §15 already retires the RVY re-pin outright: *"the dialect is permanently bespoke, no standards-track re-pin target is recorded for it, and what that retirement spends is booked in §17 (it spends oracles, not a badge)."* I missed that in the first pass and it changes how this item must be argued. **Scope check first:** that retirement is bound to R-15-007c/d, the narrowed 64-bit capability encoding, and its ground is a *permanent format commitment* — every capability in the immutable image and every sealed blob is stored in that format, so a width change invalidates stored authority wholesale. The matrix extension carries no such commitment: matrix data lives in vector registers and the scratchpad, never in the immutable image, and R-15-116 already contemplates deleting the extension by its own terms. So the retirement does **not** transfer, and the item survives — but it cannot be argued as standards-conformance-as-virtue, because §15 has already priced that as a badge. It has to be argued on the same axis §15 names: **oracles.**

RISC-V is pursuing three complementary matrix approaches — AME (attached, free to introduce its own architectural state), IME (integrated, matrix data in the existing V registers, control registers "in moderation"), and VME (a fast-track vector-based option). **VME is close to what you already built:** it stays coupled to the hart and its RVV implementation, reads vector registers for source operands, adds an accumulator register file, and is primarily outer-product matmul instructions with **no new 2D load/store instructions and no major new CSRs**. That is nearly a description of the M-class — VLEN=1024 RVV beside the array, an outer-product interface, and a deliberate refusal of per-format architectural state.

- [ ] Write the alternatives entry evaluating AME / IME / VME against the frozen bespoke extension.
- [ ] **Argue it on oracles.** A bespoke matrix extension has no conformance suite, no second implementation to differential-test against, no upstream toolchain lowering, and no independent Sail model — the same currency §15 says the capability retirement spends. A ratified matrix surface buys all four back for the profile's *largest* block of net-new Sail surface, and unlike the capability encoding there is no permanent-format commitment standing against it. That is the whole case; make it in that currency or not at all.
- [ ] Record the disqualifiers if they hold: AME introduces its own architectural state by design, which is what R-15-117 refuses; and any extension carrying a block-scale field reopens R-15-117 rather than fitting inside it.
- [ ] Add ratification-tracking rows so this is a dated reading like every other upstream, per R-18-001. Note the asymmetry explicitly in the entry, so a later reader does not read §15's retirement as covering the whole profile: **the capability dialect is permanently bespoke by commitment; the matrix extension is bespoke by default and re-pinnable in principle.**

### [T-05] `NEW` Record the declination of analog in-array compute in the adopted gain-cell tier
**Lands in:** `docs/architectural-alternatives.md`

You adopted on-die IGZO 2T0C as the normative bulk tier. The most-cited application of that exact cell is analog compute-in-memory: imec has demonstrated multilevel MAC on 2T1C and capacitor-less 2T0C gain cells, and 3D-stacked 2T0C arrays with multibit storage have been fabricated for CIM. A reviewer who knows the medium will ask why you store in it and do not compute in it, and the register has no answer.

- [ ] Write the entry. The answer is short: analog in-array MAC fails admission test (1), deterministic architectural semantics, and has no Sail surface to refine against; and §12's excluded-foreign-computers table already bans processing-in-memory as *autonomous in-array compute*.
- [ ] Draw the line precisely, since it is not the same line: §12's ban is on **autonomy**, and the disqualifier here is **analog**. State both, so a future core-issued, capability-operand *digital* near-memory proposal is judged on its own terms rather than by an argument that does not reach it.

### `NO-ACTION` Already adjudicated — recorded so they are not re-asked
- **PQ NTT / full PQC coprocessor.** Declined in `architectural-alternatives.md` §"Bespoke full-PQC and NTT instruction sets": adds Sail semantics, `Zvkt` timing clauses and refinement cases without deleting a hard proof. This was the candidate I would otherwise have raised, given hybrid PQ on every TLS connection.
- **Block-scale / MX registers.** Declined by R-15-117, priced by R-15-117a. **Jalapeño's native MXFP4 is not the proposal that reopens it** — a 700 W datacenter part with no partition-switch zeroize obligation and no Sail model. What it establishes is that MX is now the industry default rather than a bet, which strengthens R-15-117a's own Amdahl argument that the software front end sits on the binding term.
  - [ ] The one derived action: R-15-117a admits it quotes an external 7.0× / 4.8× figure "as an order rather than as this machine's own." **Take that measurement on your own VLEN=1024 unit.** It decides whether the clean line is cheap or expensive, and it is currently borrowed.
- **Fixed-function graphics.** Declined on grammar and warp-scheduler timing nondeterminism (R-15-115).
- **LDPC/polar, link-layer turnaround timer, flash ECC, scanout, the 1000BASE-T frozen-coefficient canceller.** Already admitted as grammar-free geometry under the five-part test.

---

## 2. NFC / Tap to Pay

`NFC`, `EMV`, and `secure element` appear **zero times** across the docs tree. Unconsidered, not declined.

### [T-06] `NEW` Dissolve NFC as an RF path plus a timing-sequencer event
**Lands in:** `docs/spec.md` §15 radio subsystem, `docs/requirements-register.md`

- [ ] Add 13.56 MHz to the switched bank of pre-certified fixed analog paths (R-15-124) with its own passband and power ceiling.
- [ ] Add Miller / Manchester coding and the ASK envelope to the digital front end alongside the existing filtering and decimation.
- [ ] Add the ISO 14443 frame-delay-time turnaround as one more event schedule on the R-15-122 link-layer timing sequencer. Same deadline class as BLE `T_IFS` (150 µs) and the 802.15.4 turnaround — a new entry in an existing mechanism, not a new mechanism.
- [ ] State why dissolution is the only route rather than a preference: every commodity NFC controller runs its stack as firmware on a hidden core, which is the §4 "no foreign computers" line — the argument that deletes the Wi-Fi/BT controller.
- [ ] Book the MMIO-pricing consequence. The eUICC's ISO7816 block, clocked off a divided card clock, is already named as the on-die existence proof that a slow endpoint is reachable, and a compartment's `fence.t` bound is set by the slowest endpoint its capabilities can *reach*. An NFC front end is a second such endpoint; the attested devicetree must carry it so the bound is derived rather than discovered.
- [ ] **Its PMA region is `IOMemory` and therefore non-executable** under [T-18(b)]. This is the first new aperture that rule protects; land T-18(b) before this item, not after.

### [T-07] `NEW` Card emulation as an APDU compartment
**Lands in:** `docs/spec.md` §12

- [ ] ISO 7816-4 APDUs over ISO 14443-4, as a Narcissus-derived parser over the APDU grammar — ordinary §5 work on the containment footing §12 takes for the media decode server.
- [ ] Note the precedent: the die already carries an ISO7816 interface block for the eUICC (R-12-045). Same vocabulary, opposite direction — the block moves bytes and interprets nothing.

### [T-08] `NEW` Book EMV Tap-to-Pay in §17 as a declined coverage trade
**Lands in:** `docs/spec.md` §17, `docs/architectural-alternatives.md`

There is no open standard at the credential layer. EMV Contactless Books A–D are published but require per-device EMVCo L1/L2 type approval; a live Visa/Mastercard token requires a TSP relationship and network wallet-provider approval. HCE removes the secure element, not the tokenization gate — it is "open" only relative to carrier-controlled SEs.

- [ ] Write the alternatives entry. **A payment secure element is declined**, and the argument is already written elsewhere: §4 states the eUICC exception is *an exception and not a pass*, with a second exception being an act taken against the criterion with its own containment stated. A payment SE is strictly worse than the eUICC — power-reserve card emulation means it answers the RF field while the host is off, breaking R-15-146's grant-liveness enable rule and R-15-147's lockout cut outright.
- [ ] Record that **HCE fits this platform better than any commodity phone would allow**: token in the crypto core, cryptogram computed there, the tap a powerbox-mediated consent act under the RoT latch on the trusted-path agent. The blocker is commercial, not architectural, and the entry should say so plainly rather than dressing it as a security decision.
- [ ] Book it in §17 in the shape of the 5G-SA emergency-calling trade: a stated coverage-for-security cost, not an unimplemented gap.

### [T-09] `NEW` Name the NFC use cases that *are* open
**Lands in:** `docs/spec.md` §12, `docs/architectural-alternatives.md`

- [ ] **ISO 18013-5 mobile driving licence** — device retrieval over NFC, a genuine ISO standard, no network membership required.
- [ ] **EU Digital Identity Wallet (EUDI ARF)** and the W3C Digital Credentials API as the adjacent credential-presentation surface.
- [ ] **FIDO2/CTAP over NFC**, with the on-die platform authenticator answering a foreign reader. This is the YubiKey entry's own distilled atom moved one domain over: that entry declines the *roaming external* key, not the authenticator function, and NFC is how the platform authenticator reaches a machine that is not this platform. It partially recovers the portability cost that entry books as its honest cost.
- [ ] **NFC Forum tag read/write (NDEF)** — trivially open, cheapest thing to bring up first.
- [ ] One line on the other reading of "Tap to Pay" (phone as terminal): PCI MPoC, also a certification gate, but attestation-driven — the one gate this architecture is unusually well placed for. A sentence, not a workstream.

---

## 3. Display / Wayland

### [T-10] `AMEND` Sharpen what "Wayland" means here
**Lands in:** `docs/userspace-porting.md` §"COSMIC Desktop"

The existing disposition is right — adopt `cosmic-comp` as the reference §12 display server, keep the Wayland surface model as *vocabulary*, move enforcement to per-surface and per-input capabilities. What it does not say sharply enough is that wire compatibility is **not on the table and should not be pursued**.

- [ ] State the three reasons: libwayland is C (closure disposition 3); the wire protocol is Unix-domain sockets with `SCM_RIGHTS` fd passing and this platform has rings, not sockets; and `wl_registry` is ambient by construction, exactly what R-12-075 makes unexpressible.
- [ ] Draw the roster consequence: anything speaking raw libwayland (GTK, Qt, Firefox, Chromium) does not port. Consistent with the no-Linux decision, but currently left for the reader to infer.

### [T-11] `NEW` Decline `security-context-v1` explicitly
**Lands in:** `docs/architectural-alternatives.md`

`wp_security_context_manager_v1` lets a sandbox engine attach a context to a *connection* by handing the compositor a listening socket FD plus a close FD; the compositor then restricts which globals that connection may bind.

- [ ] Write the entry. That is a **policy filter over an ambient registry, not a capability**: authority is still enumerable from the registry and is withheld by compositor discretion rather than by not being held. Adopting it re-admits the ambient global §12 deletes.
- [ ] Note the mechanism dependency as a second, independent disqualifier: the protocol is defined in terms of socket FDs and hangup semantics, neither of which exists here.

### [T-12] `NEW` (low) Import Wayland's frame-callback / presentation-time semantics into the IDL profile
**Lands in:** `docs/idl-profile.md`

- [ ] The compositor's slot is composition-declared against a line-period scanout deadline, so presentation-time feedback is the one piece of Wayland's timing model with a reason to exist here. The object model (surface / buffer / xdg roles, damage-and-commit) is already the intended vocabulary; presentation timing should join it rather than being reinvented.

---

## 4. Messaging

### [T-13] `NEW` SMS/MMS — the more urgent half of the gap
**Lands in:** `docs/spec.md` §12, `docs/requirements-register.md`, R-18-004

`RCS`, `SMS`, and `messaging` appear essentially nowhere. The first release carries cellular, an IMS voice call and an emergency call — and no way to send a text.

- [ ] Decide and record whether the first release ships messaging at all. If yes, it is a §12 compartment and a §18 workload member and both need entries. If no, it is a §17 booking.

### [T-14] `NEW` MLS as the platform's messaging primitive, RCS as a transport over it
**Lands in:** `docs/spec.md` §12 network, `docs/architectural-alternatives.md`

The structural news is favourable: the 5G-SA floor means no CS fallback, so voice is VoNR over IMS, and the first release already names an IMS voice call as a workload member. **RCS rides the same SIP/IMS stack that is already on the critical path.**

GSMA published Universal Profile 3.0 in March 2025 — the first version to formally define end-to-end encryption, using IETF MLS (RFC 9420). UP 3.1 followed in July 2025 and UP 4.0 added video. The RCS E2EE specification reached v2.0 with improved certificate handling and encrypted file transfer. Cross-platform E2EE went to beta in May 2026.

- [ ] Add an alternatives entry evaluating **MLS as a §12 compartment in its own right**. It fits: the primitives are ones the crypto core already holds, the group state machine is the shape the Lustre control plane handles, and it is an IETF RFC rather than a vendor protocol.
- [ ] Evaluate RCS **on top of** that compartment rather than as a monolith, and book its four honest costs:
  - SIP/MSRP/HTTP is a large attacker-facing grammar (Narcissus-derivable, but large).
  - Provisioning is carrier-driven autoconfiguration, so the platform inherits a **carrier PKI trust anchor for identity certificates** it does not otherwise have. The item most worth arguing about.
  - A2P / business messaging is not covered by E2EE.
  - UP 3.0 moves spam detection client-side as a direct consequence of encryption — a classifier in a compartment, i.e. a new policy surface.
- [ ] Record the effort calibration: GrapheneOS, with an existing Messaging app and a full AOSP base, has called building an RCS alternative to Google Messages "extremely hard" while stating it plans to do it; RCS there still routes through Google Messages.

---

## 5. GrapheneOS

### [T-15] `NEW` Clipboard as a powerbox object class
**Lands in:** `docs/spec.md` §12, `docs/requirements-register.md`

The linked post is the Messaging app converted to a modern app with an overhauled Compose UI — the pullable item is not the UI, it is the accompanying **secure clipboard**, gating app clipboard access behind permission.

- [ ] `clipboard` appears exactly once in the tree, inside R-14-008's browser bullet ("powerbox-only file/clipboard access"). There is no §12 clipboard server and no clipboard object class in the powerbox.
- [ ] Name it as a first-class powerbox object: a clipboard is a cross-compartment data channel with a consent act attached, which is the definition. Inheriting it from the browser bullet leaves every non-browser compartment's clipboard behaviour unstated.
- [ ] Check whether the copy direction needs the trusted-path agent or only the paste direction. (Paste is the grant; copy is the caller's own data. Worth stating rather than assuming.)
- [ ] Credit the pattern in `inspirations.md` under the existing GrapheneOS entry.

### `NO-ACTION` Everything else from GrapheneOS is already banked
Auto-reboot to Before First Unlock, MAC randomization tied to the entropy root (taken further here as a hardware invariant — no factory-burned MAC exists), and the 2G toggle taken further to a silicon generation floor. `inspirations.md` §"GrapheneOS" is current.

---

## 6. MesaOS

### `NO-ACTION` Nothing to import
A from-scratch x86_64 Rust hybrid kernel that recently cold-booted on a retail HP 15s laptop, with a shell, text editor, early USB storage, a Linux syscall shim, Ring 0 / Ring 3 and an ELF loader. Every one of those is something this design deliberately does not have. Its author is a 14-year-old who used AI for code generation.

- [ ] *(optional, one line)* The only extractable datapoint is about method and it argues **for** the admission discipline: LLM-assisted from-scratch kernel bring-up is now fast, so code volume is cheap and proof obligations are not. If it belongs anywhere it is §18's framing, not `inspirations.md`.

---

## 7. Method

### [T-16] `NEW` Mechanize the absence contract's §8 day-one procedure
**Lands in:** `docs/absence-contract.md` §8, `docs/implementation-checklist.md` (M0)

Jalapeño reached tape-out in nine months with AI in the loop on architecture, arithmetic circuits and kernels, with AI-written block implementations reported at 1.5–1.8× over human-expert code. **For this project the lesson inverts:** RTL authoring is not the bottleneck; RTL ⊑ Sail is, and it is the least-built layer (R-17-039). Generating RTL faster without generating proof faster only widens the gap.

- [ ] Automate the six-step procedure over CHERI-CVA6, Ara and Gemmini: elaborate at the intended synthesis configuration → enumerate every state element → search for A-01 through A-12a by the evidence column → record synthesis-configuration provenance → classify every remaining element into one of §6's four `fence.t` classes → apply §5's table-freeness rule mechanically to the fetch path.
- [ ] It needs no RTL of record, no Sail model and no prover — only an elaborator and cores that exist today. It is a table search, not a judgment call, which is what mechanizes cleanly.
- [ ] Output is an auditable artifact per build, which is what R-15-103's provenance half requires ("the absence is bound to a build, not to a reading").
- [ ] **Blocked today, and the blocker is named:** F-229e records that `run.py rtl elaborate` refuses while `upstream/opentitan` is uninitialized, and that a whole-SoC elaboration additionally wants `upstream/mocha`. Unblocking the elaboration is the prerequisite act; do it before writing the automation, not after.
- [ ] Extend the search to cover [T-18(a)] once that row exists — the reach obligation is a netlist question of exactly the same kind.

### [T-17] `NEW` (low) Cite the independent convergence on static placement
**Lands in:** `docs/spec.md` §1, `docs/performance-estimates.md`

Jalapeño's headline architecture — model state and KV cache explicitly placed and kept local rather than demand-cached, a NUMA-style spatial layout, and deliberate design as a *predictable programming target* so mapping, placement, scheduling and coordination can be optimized offline — is your static memory plan, your absent caches, your composition-time bank grants and your composed schedules, arrived at for performance rather than verification.

- [ ] Worth one paragraph: the largest inference deployment in the industry converged on static placement and predictability as the **performance** answer, not merely a verification tax. §1's value function defends predictability as a cost willingly paid; this is evidence it is sometimes not a cost at all.
- [ ] Keep the scale disclaimer in the same breath: 216 GB HBM4 at 15.4 TB/s and 700 W against a phone SoC and an 8 GB/s second-class grant. The principle transfers; nothing else does.

---

## Summary

| Category | Count |
| --- | --- |
| `NEW` register entries | 13 |
| `AMEND` existing entries | 3 |
| `NO-ACTION` determinations recorded | 6 |
| Measurements owed | 3 (T-01 ternary demand, T-02 depth-0/8192 controlled run, R-15-117a on this machine's own unit) |
| Rules that are free to state (already true in every composition) | 1 (T-18(b)) |

**Genuine gaps in the register:** wrong-path fetch *reach* (as distinct from fetch-path *structures*), NFC entirely, messaging/SMS/RCS entirely, clipboard as a powerbox class, prefill/decode as distinct modes, the RISC-V matrix standards track on the numerator side, and the ternary-weight question the register already cites but never follows through.

**Already answered, correctly:** every ASIC-acceleration candidate I would have raised. The five-part admission test plus R-15-116's margin rule is doing its job; the framework did not need extending, only exercising.

**The one thing the framework does not currently reach:** the absence contract enumerates *structures that must not exist* and R-15-104 decides membership by table-freeness, explicitly not by run-ahead depth. Nothing enumerates *addresses a permitted structure may reach*. The NX post is a demonstration that those are different questions and that the second one hangs machines. T-18 is that gap.
