# Performance Estimates — What the Security Choices Cost (and Buy) (non-normative)

> Externalized companion to [verification-maximal-os.md](verification-maximal-os.md). This is a **non-normative estimate**, not part of the specification: an engineering-judgment accounting of the performance-relevant features the spec removes, adds, or substitutes, and the resulting net delta. Cross-references of the form §N point to sections of that specification. Every figure is a **coarse range with wide error bars**, not a benchmark; performance was deliberately subordinated to security (§1), so this document quantifies the accepted price rather than defending it.

## How to read this

- **Baseline.** Unless noted, the reference is a **conventional 2026 application-class RISC-V SoC**: out-of-order (OoO) superscalar, TAGE-class dynamic branch prediction, MMU + multi-level TLB, multi-level caches with hardware coherence, aggressive DVFS + turbo, fixed-function GPU and video codecs, RVA23-class ISA *including* the C extension, conventional (non-CHERI) 64-bit pointers, plain (unencrypted, no-integrity-tree) DRAM. This is "what you would otherwise buy" for the phone/desktop targets the spec addresses. A **secondary baseline** — a plain *in-order* RV64GC core — is treated in the totals, because against it several of the largest losses vanish.
- **The percentages are per-workload multipliers, NOT additive.** Each row is the approximate change *on the workload it applies to*, holding everything else equal. They compound **multiplicatively** and are **gated by workload** (a vector gain and an in-order loss rarely touch the same cycle). The totals section is therefore a reasoned synthesis, not a column sum.
- **Sign convention:** negative = slower than baseline; positive = faster. `×` denotes a multiple (e.g. `+900%` = `10×`).

## The big table

| Group | Feature (spec §) | Change | Est. Δ perf | Applies to | Notes |
|---|---|---|---|---|---|
| Core µarch | In-order issue, no speculation/OoO (§2, §15) | Removed | **−35% to −60%** | general scalar / latency-bound | Dominant single factor vs an OoO baseline. |
| Core µarch | Static-only branch prediction, no BHT/BTB/RAS (§15) | Removed | **−10% to −30%** | branchy control code | Compounds with in-order; per-mispredict penalty is *smaller* due to the short pipeline. |
| Core µarch | No SMT (§15) | Removed | **0%; −15% to −30%** | multithreaded throughput only | No single-thread effect. |
| Core µarch | Fixed modest clocks, no turbo/DVFS (§15 power) | Substituted | **−15% to −40% burst; −0% to −15% sustained** | burst/interactive latency | Frequency effect, not IPC; turbo never helps thermally-bound sustained load. |
| Core µarch | No JIT — interpret-only dynamic languages (§2, §14) | Removed | **−60% to −90%** | JS / Wasm / dynamic-language code only | Native AOT code unaffected; hits the browser hardest. |
| ISA removed | No C / compressed extension (§15) | Removed | **−2% to −12%** | fetch / I-cache-bound | +25–30% code size → I-cache & bandwidth pressure. |
| ISA removed | Fixed-latency integer DIV and vector FPU, no early-out, subnormal-safe (§15) | Substituted | **−1% to −6%** | divide / sqrt / FP-heavy | Price of the constant-time mandate. |
| ISA removed | No scalar `F`/`D` — scalar float folded onto the vector FPU (§15) | Substituted | **−2% to −15%** | scalar-float-bound code | VL=1 vector ops + soft-float-register ABI setup; well-vectorized FP is unaffected (runs on RVV). |
| ISA removed | No prefetch / non-temporal hints — Zicbop/Zihintntl (§15) | Removed | **−3% to −15%** | memory-bound streaming | Explicit loads only. |
| ISA removed | Misaligned accesses trap (§15) | Substituted | **−0% to −5%** | code with unaligned access | Well-aligned code ≈ 0. |
| ISA removed | `Zaamo`-only — no LR/SC, no CAS (§15) | Removed | **−0% to −3%** | lock-free / atomic-heavy | Spec argues no consumer exists above a share-nothing kernel; near-zero in practice. |
| Mem / security | CHERI purecap, 128-bit capabilities (§7, §8, §15) | Added | **−3% to −15%** | pointer-heavy | Footprint/bandwidth from doubled pointer width; many workloads <5%. |
| Mem / security | Transparent memory encryption — TME (§15) | Added | **−1% to −5%** | memory-bound | Added controller latency. |
| Mem / security | DRAM-wide integrity + anti-replay Merkle tree (§15) | Added | **−5% to −30%** | memory-bandwidth-bound | Largest memory-side tax; address- not data-dependent (no timing channel). |
| Mem / security | End-to-end ECC, 3 layers (§15, §16) | Added | **−1% to −3%** | memory-bound | User-flagged "a little." |
| Mem / security | Deterministic RFM refresh at worst-case cadence — replaces reactive PRAC back-off (§15) | Added | **−2% to −10%** | activation-heavy / memory-bound | Fixed worst-case cadence spends bandwidth a reactive back-off would reclaim; address- not data-dependent, so no timing channel. |
| Mem / security | Mandatory IOMMU-confined DMA (§15) | Added | **−1% to −5%** | DMA / I/O-heavy | Translation overhead on the device path. |
| Isolation | Non-work-conserving static cyclic scheduler (§7) | Added | **−10% to −35%** | mixed-load throughput | Idle slots stay idle; no slack donation (that would be a timing channel). |
| Isolation | Cache partitioning / way-coloring (§15) | Added | **−5% to −25%** | cache-sensitive, shared island | Reduced effective cache per partition. |
| Isolation | DRAM (sub-)channel partitioning, no interleave (§15) | Added | **−5% to −20%** | bandwidth-bound per island | Bandwidth quantizes to assigned (sub-)channels. |
| Isolation | TDM NoC arbitration, no best-effort QoS (§15) | Added | **−5% to −15%** | communication-heavy | Deterministic but lower fabric utilization. |
| Isolation | `fence.t` flush + eager V/M zeroize at switch (§7, §15) | Added | **−2% to −10%** | context-switch-heavy | Cheaper than usual — no predictor/speculative state to flush (`cbo.zero` helps). |
| Isolation | No cross-island hardware coherence (§15) | Substituted | **−5% to −20%** | cross-island sharing | Explicit cache management replaces the protocol; within-island unaffected. |
| Accel removed | No fixed-function GPU — software render (§12, §15) | Substituted | **−70% to −95%** vs a real GPU | 3D / graphics | Runs on V-cores instead; 2D/UI compositing is fine. |
| Accel removed | No fixed-function video codecs (§15) | Substituted | **−80% to −95%** vs a HW codec | video encode/decode | Software codecs on V-cores; throughput/power hit. |
| **Gain — removed** | No MMU / single address space, no TLB, no page walks (§7, §15) | Removed | **+5% to +25%** (up to ~+30%) | large-footprint / pointer-chasing | User-flagged "a lot." Eliminates TLB misses & walk latency. |
| **Gain — removed** | No ASLR (§14, §15) | Removed | **+0% to +3%** | PIC-heavy | User-flagged "a little." |
| **Gain — removed** | No shadow stacks / CFI / landing pads — Zicfiss/Zicfilp (§15) | Removed | **+1% to +5%** | call/return-heavy | CHERI + proofs give CFI without the runtime tax. |
| **Gain — removed** | No MTE memory tagging (§15) | Removed | **+2% to +5%** | vs an MTE-enabled baseline | Replaced by CHERI (whose cost is booked above). |
| **Gain — removed** | No pointer masking — Ssnpm/Smnpm (§15) | Removed | **~0% to +1%** | — | Negligible. |
| **Gain — added** | RVV vector, VLEN 256 (C-class) / 4096 (V-class) (§15) | Added | **+100% to +1500% (2–16×+)** | data-parallel | User-flagged. The dominant gain lever; huge VLEN on V-class. |
| **Gain — added** | Matrix / systolic GEMM units — M-class (§15) | Added | **+900% to +9900% (10–100×)** | dense GEMM / AI inference | Vs scalar; "early-NPU-class" per the spec's own honesty. Admitted over the M-class's own VLEN=1024 RVV GEMM by the order-of-magnitude margin that is its §15 admission threshold. |
| **Gain — added** | Scalar + vector crypto — Zkne/Zknd/Zknh, Zvkned/Zvknhb/Zvkg/Zvbb/Zvbc (§15) | Added | **+400% to +2000% (5–20×)** | AES / SHA-2 / GHASH | Table-free; *also* deletes the cache-timing side channel. |
| **Gain — added** | Bit-manip Zba/Zbb/Zbs, fixed-latency (§15) | Added | **+2% to +12%** | bit / integer-heavy | Broad integer uplift. |
| **Gain — added** | Macro-op fusion — decoder-stage, architecturally transparent (§2, §15) | Added | **+3% to +10%** | dependent scalar-integer / address-gen / compare-branch | Recovers issue efficiency lost to no-C and static-only prediction; a fused pair is one fixed-latency entry (tightens WCET), architecturally transparent so it costs no proof. |
| **Gain — added** | `Zicond` branchless select (§15) | Added | **+0% to +4%** | data-dependent branches | "Doubly load-bearing": also dodges the static-predictor mispredict. |
| **Gain — added** | `Zicboz` (cbo.zero) (§15) | Added | **+0% to +3%** | zeroing / context-switch | Makes eager-zeroize nearly free. |
| **Gain — added** | bf16 (Zvfbfwma), `Zaamo` fixed-latency AMO (§15) | Added | **small, workload-specific** | ML / atomic paths | — |
| Neutral | `Ztso` memory model vs RVWMO (§15) | Substituted | **~0%** | all | Free on an in-order FIFO-store-buffer core; buys proof simplicity, not speed. |

## Net change by workload archetype (vs the OoO baseline)

The single-number answer depends entirely on the workload mix, so the honest total is a small matrix. Figures are the compounded synthesis of the applicable rows above.

| Workload archetype | Net Δ vs conventional OoO core | Reading |
|---|---|---|
| General scalar / interactive / branchy (compilers, OS logic, business logic) | **−50% to −70%** | Runs at ~**30–50%** of a conventional core. In-order + static prediction + lower clocks dominate; single-address-space and bit-manip only partly offset. |
| Memory-bound streaming | **−30% to −55%** | Integrity tree + no-prefetch + channel partitioning, softened by no-MMU. |
| JS / Wasm / dynamic-language (browser) | **−60% to −90%** | The worst case; no-JIT dominates. |
| Vectorizable data-parallel (render, DSP, codecs, ML pre/post) | **+200% to +1400% (3–15×)** vs scalar; **≈ −20% to +100%** vs a vector-equipped baseline | RVV VLEN=4096 dominates; this is the class the design optimizes. |
| Crypto (AES / SHA / GHASH) | **+400% to +1900% (5–20×)** | Table-free crypto extensions, constant-time. |
| Dense GEMM / AI inference (M-class) | **+900% to +9900% (10–100×)** vs scalar | Systolic units; competitive with early-NPU-class parts. |

## Headline total

- **General-purpose scalar / interactive code: ≈ −50%, range −40% to −70%** vs a conventional out-of-order RISC-V application core. In plain terms, ordinary software *feels like* it runs at roughly **one-third to one-half** the speed of what you would otherwise buy — the deliberate, spec-wide price of deleting speculation, dynamic prediction, and reactive clocking, and of paying the CHERI/encryption/integrity/isolation taxes.
- **The workloads the machine is actually built for — vector graphics/DSP, crypto, and matrix/AI — run at parity-to-many-times the baseline** (roughly **+3× to +100×** over a scalar baseline, depending on class), because RVV, the systolic units, and table-free crypto more than repay the scalar overheads whenever the work vectorizes.
- **Blended "typical desktop/phone" experience:** dominated by the scalar/interactive figure for responsiveness (**−40% to −65%**), with the accelerated paths pulling media, crypto, radio/DSP, and AI inference back to parity-or-better. Net: a machine that is **materially slower for general use and faster for the parallel workloads it targets** — exactly the trade §1–§2 declare.

### Sensitivity to the baseline

If "bog-standard" is read literally as a **plain in-order RV64GC core** (the common shipping RISC-V application profile — dynamic prediction, MMU, DVFS, C extension, non-CHERI, no vector) rather than an OoO part, then the two biggest losses (in-order vs OoO, and much of the turbo gap) **disappear or shrink**, while the no-MMU, bit-manip, and CFI/ASLR gains and the vector/crypto/matrix gains remain. Against that baseline:

- **General scalar: ≈ −15% to −45%** (static prediction + CHERI + partitioning + no-C, minus the single-address-space and bit-manip gains).
- **Vector / crypto / matrix: unchanged — still large net positives**, and larger still because a plain RV64GC baseline has no vector unit to compare against.

So the design's general-purpose penalty is **"roughly half"** against a premium OoO core and **"a modest fraction"** against an ordinary in-order core — and in both cases it *wins* on the parallel and cryptographic workloads it was built to run.
