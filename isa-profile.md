# The Frozen Instruction-Set Profile

*Normative as a **view**. This document is the artifact **R-15-001a** mandates and R-15-001, R-15-014, and R-18-003a depend on: the single enumeration of the frozen profile. It is **derived from** [requirements-register.md](requirements-register.md), which remains the audited artifact per R-05-152.*

> **Precedence.** Where this document and the register disagree, **the register wins and this document is defective.** Every row cites the requirement that governs it, so a disagreement is a locatable defect rather than an ambiguity. This document adds no obligation of its own; it collects obligations stated elsewhere.

## Why this document exists

R-15-001's acceptance criterion reads *"the frozen profile enumerates exactly this extension set."* Without this document there is no such enumeration: the profile would be an emergent property of some seventy requirements spread across §15.1–§15.12 and §15.16, and the criterion would name an artifact a reviewer cannot open. Four criteria test membership in the profile this way (R-15-014, R-15-024, R-15-042, R-15-067), so all four are decidable only against this document.

It matters beyond review hygiene. R-18-003a makes the profile freeze the **root of the schedule** — the toolchain, the Sail model, and the CHERI-CompCert backend all target it, so it precedes all three — and R-18-003b(i) makes *"the profile freeze and its Sail curation"* the first day-one deliverable. This is the document that deliverable consumes: what a Sail curator removes from `sail-riscv` ⋈ `sail-cheri-riscv`, and what the backend's target description must match.

## 1. Base

| Property | Value | Governing |
| --- | --- | --- |
| Base ISA | RV64 **IM**_Zicsr | R-15-001 |
| Vector | **V** (RVV), VLEN per core class (§8) | R-15-001, R-15-113 |
| Capabilities | **CHERI**, 128-bit purecap encoding | R-15-001, R-15-007 |
| ABI mode | **purecap only** — no hybrid, no plain-RV64 target anywhere | R-15-001, R-18-002 |
| Atomics | `A` narrowed to **`Zaamo` + `Zabha`** | R-15-001, R-15-024 |
| Scalar FP | **none** — V supplies all floating point, computed at VL=1 | R-15-001, R-15-039 |
| Compressed | **none** — unique 4-byte-aligned decode | R-15-001, R-15-036 |
| Privilege | **Machine mode only**; privilege is the CHERI access-system-registers permission on the PCC, not a ring | R-15-003 |
| Address space | **single physical**; no MMU, `satp` fixed Bare | R-15-002 |
| Memory model | **Ztso** (RVTSO), normatively in place of RVWMO | R-15-004, R-15-015 |
| `misa` | **read-only** — no runtime ISA morphing | R-15-052 |
| Unallocated encodings | **trap**; no encoding is a no-op by default | R-15-014 |
| Model | exactly **one** Sail model, parameterized by core class; exactly **one** capability encoding | R-15-005 |

**Ztso is the specified model, and sequential consistency is not a pending change.** SC was evaluated and rejected on four platform-specific grounds; §18 names it as a question worth revisiting, which is a question and not a deliverable (R-15-018). A curator implements Ztso.

## 2. Adopted extensions

| Extension | Role | Governing |
| --- | --- | --- |
| `Zicsr` | base CSR access | R-15-001 |
| `Zaamo` | unconditional atomic RMW, word + doubleword; dominant consumer is `Arc`'s refcounts | R-15-024, R-15-029 |
| `Zabha` | byte + halfword width cases on the above — width cases, not a new operation class; justified by lowering-admissibility, not traffic | R-15-024, R-15-027, R-15-028 |
| `Zba` / `Zbb` / `Zbs` | fixed-latency bit manipulation | R-15-067 |
| `Zbkb` / `Zbkc` / `Zbkx` | scalar crypto bit-manipulation, retained for software crypto on vectorless cores; **not** an AES/SHA-2 round datapath | R-15-042, R-15-055 |
| `Zicond` | branchless constant-time select (`czero.eqz/nez`); doubly load-bearing under static-only prediction | R-15-054 |
| `Zicboz` | `cbo.zero`; makes eager-zeroize near-free and carries the disclosure half of Write-before-Read | R-15-060 |
| `Zvkned` / `Zvknhb` / `Zvkg` / `Zvbb` / `Zvbc` | table-free vector AES / SHA-2 / GHASH; `Zvbb`/`Zvbc` also carry baseline Keccak, NTT rides plain RVV | R-15-055 |
| `Zvfbfwma` | M-class bf16 | R-15-067 |
| `Zicntr` / `Zihpm` | present but **permission-gated** — unreadable without the counter-read permission on the PCC; hpm events sentinel-only | R-15-077 |
| AIA / IMSIC | interrupt delivery; MSI is a store to an interrupt file, so send authority is a write capability | R-15-064 |
| `mtimecmp` | M-mode timer, programmed directly by the kernel | R-15-063 |

**`Zkt` + `Zvkt`** are adopted as the **leakage contract** rather than as instructions: the architectural statement that a listed instruction set runs in data-independent latency. That list is both the single leakage model constant-time verification is stated against and an RTL ⊑ Sail proof obligation (R-15-053).

**AIA scope.** Only the *machine-level* interrupt files exist, and of those only the **pending array**. The supervisor and guest/VS machinery, and the delivery-enable, threshold, and top-pending-selection machinery, are dead Sail surface and are excluded; software reads pending bits with ordinary loads (R-15-065). The platform is MSI-only — no PLIC, no wired level interrupt on the die; the only non-MSI signals are the RoT's reset and watchdog-bite lines, which sit outside the interrupt model (R-15-066).

## 3. Custom and fork-and-frozen instructions

Each carries full Sail semantics and a recorded **re-pin obligation** where a standards track exists.

| Instruction / unit | Disposition | Re-pin target | Governing |
| --- | --- | --- | --- |
| `fence.t` | platform-custom; specified rather than invoked — enumerated flush set, mechanized completeness classification, padded constant cost | — | R-15-062 |
| Keccak-p[1600] | single vector instruction, fixed-latency permutation, **both 24- and 12-round** modes frozen; **vector-bearing cores only**, not the S-class RoT | `Zvknhk` / `vkeccak.vi` (RISC-V PQC TG, RVG-84) | R-15-056, R-15-056a, R-15-057, R-15-057a, R-15-059, R-15-059a |
| Matrix extension | bespoke, fork-and-frozen; systolic GEMM geometry | ratified AME/IME lineage | R-15-009, R-15-116 |
| FEC units | LDPC and polar decoders only, fixed-geometry, deterministic iteration bounds, core-issued capability operands, no firmware | — | R-15-119 |
| CHERI dialect | frozen with the profile | ratified RVY base, not a private snapshot | R-15-007 |

The Keccak unit has no Coq-native proof to import, so its fixed-permutation invariant is a fresh Sail proof disciplined against FIPS 202 and the NIST ACVP vectors as differential oracle; the `Zvbb`/`Zvbc` software path is retained as the portable route and the differential reference (R-15-058).

**Keccak re-pin target, recorded.** RVG-84 is `Zvknhk`, one instruction `vkeccak.vi`: vector-immediate multi-round Keccak-*p*[1600], **EGW 2048 / EGS 32 / SEW 64 only**, requiring `Zve64x` and mandating `Zvl128b`, with the immediate selecting 24 rounds (SHA-3/SHAKE) or 12 (TurboSHAKE/KangarooTwelve) and all other values illegal (R-15-057a). Three consequences are carried here rather than left to the re-pin. Data-independent execution latency is **mandatory in the extension itself**, so the `Zkt`/`Zvkt` keystone (R-15-053) is discharged architecturally for this instruction rather than imposed by this profile alone. The fork therefore freezes **both** round counts, so the re-pin is a substitution of encoding and not a widening of frozen semantics that would reopen the permutation lemma and the fixed-latency claim at ratification time (R-15-056a). And the 2048-bit element group is LMUL≤1 at the V-class VLEN=4096 but **LMUL=8 at the C-class VLEN=256**, one permutation consuming the whole architectural vector register file, so C-class Keccak figures are stated at that geometry (R-15-059a) — a budget entry, not an admission one.

There is **no scalar Keccak instruction on the RISC-V standards track and none proposed.** RVG-84 is vector-only by construction, so the vectorless S-class and the RoT have nothing to adopt: their SHA-3/SHAKE stays plain 64-bit integer with `Zbb` rotations, which is both the constant-time answer on a fixed-latency core and the standards-aligned one (R-15-041, R-15-059). The matrix unit consumes int8/bf16 only — de-quantization and block-scale application are software on the M-class vector unit, and no block-scale register enters the frozen matrix ISA (R-15-117). Every byte the matrix unit moves is core-issued with explicit capability operands: no independent DMA mastership, no translation context, no firmware (R-15-118).

## 4. CHERI feature set

**Adopted**

| Feature | Note | Governing |
| --- | --- | --- |
| 128-bit purecap encoding | object-type and permission space frozen with the profile | R-15-007 |
| Sealed-entry sentries, forward/backward-edge split | the platform's coarse-grained CFI; a return capability may target only a return site | R-15-008, R-15-071 |
| Capability jump-and-link | unseals a forward-edge sentry into PCC and writes the return address already sealed as a backward-edge sentry — the hardware root of domain entry, so there is no separate call gate | R-15-068, R-15-069 |
| `MTCC` / `MEPCC` / `MTDC` | capability trap registers, reachable only with access-system-registers | R-15-073 |
| Local/global + `store-local` | with `load-global`/`load-mutable` transitivity; only the stack carries `store-local` | R-15-074 |
| access-system-registers permission | *is* the privilege mechanism, replacing the S/U ring | R-15-003 |
| counter-read permission | gates `Zicntr`/`Zihpm` | R-15-077 |

**Excluded**

| Feature | Ground | Governing |
| --- | --- | --- |
| Interrupt-state sentries (`enabled`/`disabled`/`inherit`) | the one CHERIoT capability feature the profile declines: with asynchronous interrupt delivery deleted, the three sentry types collapse to one plain sealed entry | R-15-070 |
| CHERIoT compressed RV32 capability format | no second capability encoding forks the model, the RoT's scalar core included | R-15-005 |
| Landing-pad / target-membership surface | a sentry deliberately does not decide target membership; the residual closes in software as the typed callee set | R-15-072 |

## 5. The CSR bank

*The artifact R-15-001b mandates. The deletions below in §6 are enumerated by name; this is the residue, enumerated the same way, because two obligations quantify over it — the partition switch's restore is total over "every general-purpose register, capability register, and CSR a partition can name" (R-07-015), and the flush-set argument puts that totality in place of flush-set membership (R-15-214).*

**The table is closed.** A CSR address in neither §5.1 nor §5.3 is unallocated, and an unallocated CSR address traps under R-15-014 exactly as an unallocated instruction encoding does. §5.3 is the part the register does not yet decide; those rows are booked as extraction defects and are the review gate's agenda, not an implementer's discretion.

**`mtime` / `mtimecmp` are not in this table.** They are memory-mapped, not CSRs — the kernel programs the machine-timer compare through the fabric, and `Sstc`'s `stimecmp` is excluded with the S-mode bank (R-15-063, R-15-066).

### 5.1 Present

| CSR | Disposition | Governing |
| --- | --- | --- |
| `misa` | **read-only**; writes have no effect, so no runtime ISA morphing | R-15-052 |
| `mstatus` | present for **`VS`/`XS`** — the vector/matrix state gate, set at partition setup and paired with eager zeroize; this is the mechanism `Smstateen` was deleted in favor of. `FS` has no referent with scalar FP deleted | R-07-012, R-15-049, R-15-039 |
| `MTCC` / `MEPCC` / `MTDC` | capability trap registers, **in place of** `mtvec` / `mepc` / trap-scratch, reachable only with access-system-registers. A trap installs `MTCC` as the executing PCC, saves the interrupted PCC as `MEPCC`, and bootstraps the handler's authority from `MTDC` | R-15-073, R-07-022, R-07-023 |
| `vtype` / `vl` / `vlenb` / `vstart` / `vxrm` / `vxsat` / `vcsr` | present with **V**. The partition switch **zeroizes and does not save** them, so no vector CSR context-switches and none joins the `fence.t` flush set — the property R-15-083 deletes `frm` to obtain, obtained here structurally. `vtype`'s reachable configuration space is not itself frozen (see [simplification-candidates.md](simplification-candidates.md) §2) | R-15-001, R-07-014, R-07-014a, R-15-214 |
| `mcycle` / `minstret` / `mhpmcounter3–31` / `mhpmevent3–31` | present but **permission-gated** — unreadable without counter-read on the PCC; hpm events sentinel-only | R-15-077 |
| `dcsr` / `dpc` / `dscratch0–1` | Debug Module state: present in silicon, **unreachable in the production lifecycle state**, where the RoT's OTP fuse holds the DM's clock and reset gated off and its fabric port electrically quiesced | R-15-078, R-15-079 |

### 5.2 Absent

Each row is a `MUST NOT` in the register; the ground is the governing requirement's, restated in one clause.

| CSR | Ground | Governing |
| --- | --- | --- |
| `sstatus` / `stvec` / `sepc` / `scause` / `stval` / `sie` / `sip` / `sscratch` / `senvcfg` / `scounteren` | the S-mode bank: no ring to delegate to, no mode to return to | R-15-003 |
| `medeleg` / `mideleg` | trap delegation with no delegate | R-15-003 |
| `mcounteren` | grants counter access to a less-privileged mode that does not exist; the gate is the CHERI permission | R-15-003, R-15-077 |
| `stimecmp` (`Sstc`) | one privilege mode; the kernel programs the machine-timer compare directly | R-15-063 |
| `satp` | no MMU: the Sail model carries no translation state, and `satp` is Bare rather than present-and-ignored | R-15-002 |
| `fcsr` / `frm` / `fflags` | no scalar FP; rounding is static and encoded per-instruction, so no mutable rounding-mode state context-switches or joins the `fence.t` set | R-15-039, R-15-083 |
| `seed` (`Zkr`) | exactly one entropy root — the RoT TRNG through the verified DRBG | R-15-037 |
| `mstateen0–3` (`Smstateen`) | with no less-privileged mode its bits gate nothing reachable | R-15-049 |
| `srmcfg` (`Ssqosid`) | bandwidth is not a runtime-allocated quantity; per-`MCID` counters would be a cross-partition activity oracle | R-15-050, R-15-051 |
| `pmpcfg0–15` / `pmpaddr0–63` | CHERI is the sole memory-protection mechanism | R-15-075 |
| `hstatus` / `hedeleg` / `hideleg` / `hgatp` / … / `mtinst` / `mtval2` | the platform hosts no guests | R-15-006 |
| `miselect` / `mireg` / `mtopei` / `mtopi` / `mvien` / `mvip` | the AIA **indirect interface**: only the machine-level pending array exists, software reads pending bits with ordinary loads, and the delivery-enable, threshold, and top-pending-selection machinery is dead Sail surface | R-15-064, R-15-065 |

### 5.3 Open — rows the register does not decide

Booked as an extraction defect in the register. Each states what is indicated and why, and **none is settled by this document**: the "indicated" column is a reading of requirements that exist, not a decision this view is entitled to make.

| CSR | What the register does and does not say | Indicated | Bearing |
| --- | --- | --- | --- |
| `mcause` / `mtval` | The trap path is specified in capability terms — `MTCC` installed, `MEPCC` saved, authority from `MTDC` — but no requirement names a cause register, a trap-value register, or the cause encoding for a CHERI capability exception. A handler needs a cause | **present**; this is a hole, not a deletion | R-07-022, R-15-073 |
| `mie` / `mip` | The machine-timer bits have a consumer: the slot-boundary timer is the core's only asynchronous trap. The external- and software-interrupt bits do not — an MSI sets an IMSIC pending bit read by an ordinary load and never vectors the core, and no wired level interrupt exists on the die | **present, narrowed to the timer bits**; the deletion is of fields, not registers | R-07-038, R-07-043, R-15-063, R-15-065, R-15-066 |
| `menvcfg` | Every bit gates a *less-privileged* mode's access to an extension feature. R-15-049's ground against `Smstateen` — with no less-privileged mode its bits gate nothing reachable — applies word for word, and is stated only for `Smstateen`. `Zicboz`'s `CBZE` bit is the case to check: `cbo.zero` is unconditionally permitted in M-mode | **deletion** | R-15-049, R-15-060, R-15-003 |
| `mcountinhibit` | A second gate on counters already gated by a CHERI permission, and writable state a total restore would have to name | **deletion**, under *verify rather than hedge* | R-15-077, R-15-013 |
| `mvendorid` / `marchid` / `mimpid` / `mconfigptr` | Read-only identification. RISC-V permits all four to read zero, and a profile frozen with the proof, carrying exactly one Sail model, has no runtime discovery consumer | **hardwired zero** | R-15-005, R-15-014 |
| `mhartid` | Almost certainly present — one kernel binary runs unmodified on every core class and needs hart identity — but no requirement says so, and its value space is a composition parameter | **present** | R-07-012, R-15-113 |
| `tselect` / `tdata1–3` (trigger module) | The lifecycle fuse is stated for the Debug Module and for trace. The trigger module is not named, and in standard RISC-V its CSRs are **M-mode-accessible** — reachable in the production state. A trigger is mutable hidden state that fires on an address or data match, which is the shape admission test (3) rejects, and it survives a partition switch unless something zeroizes it | **absent**, or fused with the DM | R-15-078, R-15-079, R-15-010, R-15-012 |
| `DDC` | Purecap-only with no hybrid mode leaves the default data capability without a consumer, but no requirement retires it, and it is architectural capability state the total restore would have to name | **absent** | R-15-001, R-07-015 |

---

## 6. Exclusions

Every exclusion below is a `MUST NOT` in the register. Where a feature was excluded by the five-part admission test, the failing test is named (R-15-012).

| Excluded | Ground | Governing |
| --- | --- | --- |
| `C` (compressed) | unique 4-byte decode for binary-level proofs; ~25–30% code size accepted | R-15-036 |
| `F` / `D` scalar FP, `f0`–`f31`, dynamic `frm` | all FP is vector; fixed-latency contract stated once | R-15-039, R-15-083 |
| `Zalrsc` | per-hart reservation register is hidden inter-instruction state (test 3); spurious SC failure (test 1); reservation-granule contention is a cross-hart channel | R-15-025 |
| `Zacas` (incl. `amocas.q`, `amocas.b/.h`) | no consumer: share-nothing multikernel, SPSC rings under Ztso, single-instruction `Zaamo` refcounts, no capability in shared mutable memory | R-15-026, R-15-027 |
| `Zicbom` | no hardware caches, so no consumer; cross-island ring ordering is a plain `fence` | R-15-061 |
| `Zifencei` / `fence.i` | no runtime consumer under W^X with no on-device codegen | R-15-047 |
| `Zkr` | exactly one entropy root — the RoT TRNG through the verified DRBG | R-15-037 |
| `Zkne` / `Zknd` / `Zknh` | vector crypto computes them table-free, so the CT contract is stated once | R-15-041 |
| `Zks*` / `Zvks*` (ShangMi), `Zimop` / `Zcmop` | dead Sail surface on a frozen ISA | R-15-048 |
| `Zicbop` / `Zihintntl` | no prefetch request has a software origin | R-15-046 |
| `Zawrs` | would stall on a reservation set that does not exist | R-15-046 |
| `Ssnpm` / `Smnpm` (pointer masking) | obviated by CHERI; no top-byte-ignore mechanism | R-15-043 |
| `Zicfiss` / `Zicfilp` | CFI is a theorem for verified code and CHERI-enforced for the rest; landing-pad exactness taken as the typed callee set at zero silicon | R-15-044 |
| `Smstateen` | with no less-privileged mode its bits gate nothing reachable | R-15-049 |
| `Ssqosid` / CBQRI | bandwidth is not a runtime-allocated quantity; per-`MCID` counters would be a cross-partition activity oracle | R-15-050, R-15-051 |
| `Sv39` / `Sv48` / `Sv57`, `Svadu` / `Svade`, TLB, walk cache, A/D | the sole autonomous hardware walker is deleted with the MMU rather than exempted from test 5 | R-15-038 |
| `H` (hypervisor) | the platform hosts no guests | R-15-006 |
| `Sstc` / `stimecmp` | one privilege mode; the kernel programs `mtimecmp` directly | R-15-063 |
| S/U modes, `medeleg` / `mideleg`, `sret`, `mcounteren` / `scounteren` | single Machine mode | R-15-003, R-15-077 |
| PMP / `Smepmp` | CHERI is the sole memory-protection mechanism; the three roles a locked-PMP backstop would serve each map onto a named CHERI or crypto-core mechanism | R-15-075 |
| MTE-class memory tagging | ~93% probabilistic detection, blind to intra-granule overflow — a statistic, not a theorem | R-15-045 |
| Initialization-tag plane (Mon CHÉRI-derived) | carried instead by the definite-initialization attribute of [verification-maximal-os.md](verification-maximal-os.md) §5; one tag plane per SRAM word, not two | R-15-035 |
| RVWMO | retained neither in hardware nor in proof reasoning; every ring proof restated under Ztso | R-15-004 |
| Speculation, SMT, dynamic branch prediction | fail admission tests (1)–(3), (3), and (3) respectively | R-15-012, R-15-019 |

**Two exclusions are recorded with their accepted costs rather than as free wins.** Vector-FP-without-scalar-FP is a deliberate, Sail-modeled **fork of standard RVV**, admissible only because the platform curates its own profile and formal model; its cost is a soft-float-register calling convention, accepted (R-15-040). And dropping PMP forgoes the one **CHERI-disjoint failure domain** PMP uniquely offered: the hedge becomes CHERI's own formal verification, and the resulting concentration is booked in §17 as the RTL ⊑ Sail arrow plus a Coq-native restatement of reachable-capability monotonicity over the CHERI-RISC-V Sail model (R-15-076). Neither is a deletion the profile gets for nothing, and a curator reading only the exclusion table would miss both.

## 7. Microarchitectural mandates carried by the profile

R-18-006 makes these part of the platform definition from first FPGA bring-up, not later additions.

| Mandate | Content | Governing |
| --- | --- | --- |
| Static-only prediction | backward-taken / forward-not-taken, a fixed function of encoding and displacement sign, **zero mutable predictor state**; no BHT, BTB, RAS, or dynamic direction/target/return predictor in any RTL | R-15-019 |
| Predictor deletion is structural | discharged by the microarchitectural absence contract, **not** by RTL ⊑ Sail; nothing joins the `fence.t` flush set and no residual completeness obligation exists | R-15-020, R-15-021 |
| Fetch discipline | run-ahead only down the statically determined path; the only run-ahead structure is the static-path fetch buffer | R-15-022 |
| Accepted cost | full pipeline-latency mispredict-equivalent penalties on forward conditional, indirect, and call/return dispatch, priced into WCET; the RAS is excluded despite its IPC value | R-15-023 |
| Ztso realization | in-order issue plus a FIFO store buffer; the only reordering is store→later-load bypass. **TSO is a system property, so the discharge is three-part**: the FIFO (per core), single-copy memory whose bank arbiter is the order-determining point (per location), and the NoC/memory-controller obligation to preserve per-hart request order across banks and macros (across locations) — the last preferentially met by constraining the composition-time TDM schedule. The bring-up gate covers the whole path, not the buffer alone | R-15-015, R-15-015a, R-15-016 |
| `fence` retained | for I/O and device ordering (MMIO, DMA-descriptor visibility) and cross-island ring ordering over shared SRAM; no cache-management instruction accompanies it | R-15-017 |
| Macro-op fusion | decoder may fuse a **frozen, enumerated** set of adjacent pairs (address formation / LEA, compare-and-branch, short dependent-ALU chains); combinational on static encoding, architecturally transparent, so it disturbs no certificate, CT proof, or WCET table. Sole obligation: the set is frozen with the proof and listed in the timing-annotated model | R-15-031, R-15-032, R-15-033, R-15-034 |
| No retry loops in WCET | neither LR/SC spurious-failure retry nor CAS compare-fail retry exists; every atomic is one bounded memory transaction | R-15-030 |

## 8. Core classes

One shared scalar front end (CVA6-class, modified to static-only prediction) across all classes, so kernel-path WCET is a single analysis (R-15-112). Counts are composition parameters, not architecture (R-15-113).

| Class | Datapath | Notes |
| --- | --- | --- |
| **C** | scalar + RVV, **VLEN=256** | control and application |
| **V** | long vector, **VLEN=4096**, 8 lanes | includes a radio-pinned pair; vector, **not** fixed-function graphics and not SIMT — no rasterizer, texture units, ROPs, command processor, or hardware warp scheduler (R-15-115) |
| **M** | systolic GEMM + **VLEN=1024** + software-managed scratchpad | matrix extension admitted only on an 8–10× sustained dense-GEMM margin over the same GEMM as RVV on its own VLEN=1024 unit (R-15-116) |
| **S** | scalar sentinel | vectorless; hashes SHA-3/SHAKE in plain 64-bit integer with `Zbb` rotations (R-15-041) |
| **RoT** | OpenTitan-class scalar RV64+CHERI, own clock/power island | no V/M; main-die purecap capability format, **not** CHERIoT's encoding (R-15-005, R-15-113) |

Capability checks land on scalar-issued vector/matrix memory operations, per-element for gather/scatter; vector data carries no tags, keeping CHERI a single-front-end problem (R-15-115).

## 9. Implementation timing contracts

These are the entries the timing-annotated Sail model carries, and the projection from which the per-instruction latency table is derived (R-18-024).

| Contract | Governing |
| --- | --- |
| Integer DIV/REM completes at fixed worst-case latency always; early-out-on-small-operands dividers forbidden | R-15-080 |
| Vector FPU fixed-latency across all operand classes, **subnormals included**; no subnormal slow path | R-15-081 |
| `vfdiv` / `vfsqrt` either fixed-latency or off the constant-time list — the latter admissible only on a discharged proof that no secret-labeled operand reaches them, never self-declaration | R-15-082, R-15-011 |
| Floating-point rounding static, encoded per-instruction (default RNE); never the dynamic `frm` CSR | R-15-083 |
| Misaligned accesses **trap** and are never split in hardware, so no line-crossing address-dependent latency exists | R-15-084 |
| `Zvkt`-listed vector operations execute in **mask-independent** time: an implementation may not skip memory accesses or cycles for masked-off elements, so the mask is unobservable through timing or memory traffic | R-15-085 |
| Branch-resolution latency is a fixed function of the static rule, so fetch timing depends on architectural state only | R-15-086 |
| `Zaamo` / `Zabha` AMOs complete as single bounded memory transactions with data-independent latency at the SRAM bank's serialization point — which is the whole of what a coherence point would otherwise name | R-15-087 |
| The store buffer's drain at a partition switch is data-independent because it is paid as the `fence.t` padded constant, not as a second budget term beside it | R-15-088 |

## 10. Debug

The RISC-V Debug Module exists in silicon but is **lifecycle-fused at the hardware level**, never merely software-gated: in the production lifecycle state the RoT's OTP fuse holds its clock and reset gated off and its fabric port electrically quiesced. *No DM transaction reaches the fabric in the production state* is a stated RTL ⊑ Sail obligation, so the Sail model carries the gate rather than a model of the debugger (R-15-078). In development and RMA states, DM entry is an RoT challenge-response (ML-DSA-signed, serial-bound), the key hierarchy diversifies by lifecycle state, and moving a fielded device to a debuggable state crypto-erases first; trace rides the same fuse (R-15-079).

## 11. Freeze and re-pin obligations

The profile is frozen **with the proof** (R-15-014). Three components carry standing re-pin obligations, and each re-pins to a ratified base rather than to a private snapshot:

- **CHERI** → the ratified RVY base as 'Y' ratifies (R-15-007)
- **Matrix extension** → a ratified AME/IME-lineage extension when one supersedes it (R-15-009)
- **Keccak** → RVG-84 when the RISC-V PQC Task Group's instruction ratifies (R-15-057)

A re-pin is an amendment to the profile and therefore reruns the review gate (R-18-034).
