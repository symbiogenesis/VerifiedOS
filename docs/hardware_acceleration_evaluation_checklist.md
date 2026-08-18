# Hardware Acceleration Evaluation Checklist

## Purpose

Use this checklist to decide whether a proposed hardware accelerator belongs in VerifiedOS. The objective is to maximize sustainable platform performance and capacity, including before a current workload reaches a proven bottleneck. An accelerator should proactively improve WCET, throughput, capacity, energy efficiency, admission headroom, or security so the platform remains performant as workloads and deployment demands grow, while preserving its small, deterministic, capability-governed state machine.

Normative anchors: `spec.md` §§7, 8, 11, 15, 17–18; `isa-profile.md` §§4–7; `performance-estimates.md`; `architectural-alternatives.md`, especially “Kernel-in-gateware.”

## Performance and safety gate for every candidate

A candidate advances when it demonstrates credible performance value and every mandatory safety and verification box is checked. A currently observed bottleneck is useful evidence, but it is not a prerequisite.

### Performance opportunity and benefit

* [ ] A measured baseline exists for representative current and projected workloads; the proposal may target an existing constraint or create future performance headroom.
* [ ] The benefit is stated in the platform's actual currency: reduced WCET, higher throughput, lower switch-duty ratio, fewer pinned cores, lower SRAM footprint, lower energy, smaller proof surface, greater admission headroom, or improved hard-deadline feasibility.
* [ ] Typical-case speedup, worst-case improvement, and capacity headroom are reported separately; each is credited only for the value it actually provides.
* [ ] The software/compiler/composition alternative is measured as a baseline and evaluated alongside the hardware option; hardware need not wait for software to become inadequate when it provides superior durable performance.
* [ ] The candidate has a continuation threshold: it proceeds only when measured or modeled gains justify its area, energy, complexity, and proof cost.

### Semantic shape

* [ ] The operation is a bounded transform over explicitly supplied operands or a fixed physical geometry.
* [ ] Timing is operand-value-independent, or the information-flow proof explicitly permits the dependence.
* [ ] The operation has no hidden history-dependent state surviving a partition switch.
* [ ] The operation performs no autonomous address traversal, adaptive update, feedback loop, replacement, allocation, or scheduling decision.
* [ ] Every memory access is named by an instruction, a pre-certified fixed schedule, or a capability-bounded streaming window.
* [ ] The operation introduces no authority path outside CHERI.
* [ ] It either preserves authority monotonically or only destroys authority.
* [ ] Partial completion, faults, reset, and replay have simple architectural semantics.

### Verification and lifecycle

* [ ] Sail semantics and fixed-latency cost semantics are small enough to review directly.
* [ ] The RTL state maps cleanly into the architectural/context-switched, partition-owned, `fence.t`-flushed, or stream-determined class.
* [ ] The absence contract remains structural rather than becoming a judgment call.
* [ ] RTL-refinement and non-interference obligations are identified before implementation.
* [ ] The proposal deletes or materially shrinks more proof/WCET surface than it adds.
* [ ] A defect can be patched in software unless the primitive is genuinely frozen and universal.
* [ ] Failure is fail-stop or safely restartable; no partial authority-bearing result can escape.
* [ ] A minimal implementation and an independent software oracle exist for differential testing.

## Priority 0: retain and validate existing hardware primitives

These are architectural mechanisms, not optional performance features. Evaluation should confirm implementation quality and bounds rather than reconsider their existence.

### CHERI enforcement and sealed transfer

* [ ] Measure capability-check latency and critical-path impact by core class.
* [ ] Verify fixed latency for valid, invalid, sealed, bounds-failing, permission-failing, local/global, and revoked cases.
* [ ] Confirm sealed call/return and sentry behavior adds no hidden lookup table.
* [ ] Confirm DMA and core accesses implement the same authority algebra.

Disposition: keep.

### Revocation load filter

* [ ] Validate parallel data/tag/revocation-sidecar access at target frequency.
* [ ] Measure sidecar area, ECC overhead, bank-routing cost, and effect on macro density.
* [ ] Confirm clear and set bits have identical latency and traffic.
* [ ] Confirm in-flight DMA observes the same containment epoch.

Disposition: keep.

### `cbo.zero`, `cclear`, and domain clear

* [ ] Measure fixed latency for line zero, masked register clear, and array-wide transition clear.
* [ ] Confirm data, validity tags, and SECDED/DECTED state update atomically.
* [ ] Confirm latency does not depend on prior contents, mask population, or tag density.
* [ ] Verify reset and power-transition completion signals cannot report early.

Disposition: keep and optimize aggressively; zeroization is bounded, destructive, and universal.

### `fence.t`

* [ ] Measure the padded store-buffer-drain constant for every core class.
* [ ] Confirm the store buffer remains the sole flushed structure.
* [ ] Confirm device-space writes never enter the buffer.
* [ ] Re-run the four-class RTL state inventory after every microarchitectural change.

Disposition: keep while Ztso/store buffering remains.

### Slot-boundary timer

* [ ] Confirm `mtimecmp` is unmaskable at the partition boundary.
* [ ] Verify trap suppression while the handler is live and fail-stop handling of a second trap.
* [ ] Measure timer-to-first-handler-instruction latency and bound its variation.
* [ ] Confirm hardware enforces the boundary but never selects the next tenant.

Disposition: keep the timer; reject a hardware scheduler.

### IMSIC pending array

* [ ] Confirm notification send is an ordinary capability-authorized store.
* [ ] Verify repeated sends coalesce idempotently without counters or queues.
* [ ] Measure fabric round-trip and full-FIFO worst case.
* [ ] Confirm no priority, threshold, top-pending selection, or asynchronous delivery logic remains.

Disposition: keep the pending-bit latch; address cost through batching and placement.

### Capability-checked DMA and fixed streaming engines

* [ ] Verify bounds, permissions, tags, revocation, and granule alignment at each issue point.
* [ ] Confirm autonomous engines hold only a delegated bounded window for a declared lifetime.
* [ ] Confirm no engine discovers addresses through unrestricted descriptors or pointer chasing.
* [ ] Measure capability-fabric area and timing separately from datapath throughput.

Disposition: keep.

## Priority 1: proactively evaluate at the profile freeze

### V/M all-state clear instruction

Candidate: one core-issued `vclearall`/`mclearall`-class operation clearing vector registers, vector CSRs, matrix state, and architecturally defined scratchpad state.

* [ ] Measure current instruction sequence and partition-switch contribution by class.
* [ ] Determine how it improves schedulability, pinning, switch-duty headroom, and average switch time under both current and projected load.
* [ ] Require unconditional, mask-independent, fixed-latency completion.
* [ ] Require no progress CSR, high-water mark, or lazy-state tracking.
* [ ] Compare one architectural clear operation with direct hardware reset wires already present.

Admit if: it materially lowers switch cost, increases switch-duty headroom, or removes a pinned-core requirement, with acceptable Sail/RTL and implementation cost.

### All-or-nothing fixed-list stack save/restore

Candidate: the already-admissible single-check, fixed-count multi-save/multi-restore form discussed in `spec.md` R-15-036n.

* [ ] Measure against the backend after outlining, tail merging, and final dictionary selection.
* [ ] Record both encoded bytes removed and worst-case cycles changed.
* [ ] Require one up-front stack-capability bounds/permission check.
* [ ] Require all-or-nothing architectural completion with no restart state.
* [ ] Reject any form that retains sequencer state across an instruction boundary.

Admit if: the composed image, WCET, throughput, or future capacity improves materially relative to the optimized compiler baseline.

### Partition-switch phase overlap

Candidate: overlap physically independent switch phases, such as zeroization and OPP relock, rather than fusing the switch policy into hardware.

* [ ] Prove the phases are independent under every fault and power state.
* [ ] Confirm overlap cannot expose state before zeroization or allow a store to land after ownership changes.
* [ ] Keep tenant selection and context orchestration in software.
* [ ] Model completion as one fixed padded constant.

Admit if: the switch bound becomes `max(phase costs)` rather than their sum without introducing a policy-bearing switch engine.

### Wider or revised `cloadtags`

Candidate: tune the fixed tag-group width to the physical macro/CBO geometry.

* [ ] Sweep group widths against issue cost, bank activation, encoding cost, and background-slot width.
* [ ] Measure all-clear and all-tagged blocks; latency must be identical.
* [ ] Confirm the instruction reports stored tags rather than filtered tags.
* [ ] Recompute quarantine duration and SRAM reserved for quarantine at each width.

Admit if: it materially shortens reclamation, reduces reserved quarantine or sweep slots, or creates useful capacity headroom for projected allocation rates.

### Core-issued block reclamation

Candidate: one fixed-block instruction that checks stored tags against the revocation sidecar and zeroes only revoked granules, without walking beyond one named block.

* [ ] Evaluate against optimized `cloadtags` and software sweeping, including projected reclamation demand; current inadequacy is not required.
* [ ] Require fixed work over every lane, independent of tag and revocation density.
* [ ] Specify atomicity among data, tags, revocation bits, and ECC.
* [ ] Preserve live granules exactly and return an explicit result bitmap.
* [ ] Prohibit autonomous continuation to the next block.

Admit if: the block operation substantially reduces reclamation cost or creates meaningful capacity/admission headroom for current or projected demand. Otherwise defer or reject based on the projected benefit relative to implementation and proof cost.

### Core-issued block scrub

Candidate: a synchronous fixed-block verify-and-correct operation usable by scheduled software and power-mode exit paths.

* [ ] Keep address progression in the admitted software schedule.
* [ ] Give corrected and uncorrected cases the same latency.
* [ ] Report correction telemetry without exposing data-dependent timing.
* [ ] Fail stop on uncorrectable data or tag-plane errors.
* [ ] Compare with the existing memory-controller RMW/ECC path before adding new semantics.

Admit if: it reuses the existing ECC datapath and meaningfully shrinks scrub software or transition proof surface.

### Static instruction scratchpad

Candidate: explicit, statically placed instruction SRAM—not a cache.

* [ ] Quantify current and projected shared-SRAM port pressure, WCET effects, and admitted-core headroom.
* [ ] Require composition-time contents and placement; no fill, replacement, miss, or coherence state.
* [ ] Include scratchpad ownership and zeroization in the switch proof.
* [ ] Compare capacity consumed with the saved memory ports/banks and tightened WCET.

Admit if: tighter WCET, reduced contention, improved admitted-core headroom, or sustained throughput justifies the modeled region and capacity.

### Fixed-function datapath additions

Candidate class: crypto rounds, FEC geometry, matrix operations, PHY turnaround, fixed sensor conditioning, timestamping, and power sequencing.

* [ ] Quantify the targeted improvement in hard-deadline margin, throughput, latency, energy, key isolation, or core-count capacity for current and projected workloads.
* [ ] Require fixed geometry and bounded state.
* [ ] Keep adaptive policy, parsers, calibration decisions, and protocol state in software.
* [ ] Require capability-bounded data movement and explicit reset behavior.
* [ ] Prefer core-issued operands; permit scheduled streaming only where continuous I/O requires it.

Admit if: the unit materially improves a hard bound, throughput, energy, capacity, or isolation and its durable value exceeds the general-purpose compute and proof burden it adds.

## Priority 2: evaluate selectively for future scale

### Whole partition-switch engine

Evaluation condition: modeling shows software orchestration could materially limit future switch rate, switch-duty margin, or core placement after existing primitives are optimized.

Default disposition: reject. Prefer another small destructive or fixed-latency instruction.

### Hardware endpoint lookup

Evaluation condition: projected endpoint scale or call rate indicates that non-static endpoint operations may materially affect WCET or capacity after singleton-call collapse and composition-assigned indexing.

Default disposition: reject. It risks recreating an object table or CSpace.

### Hardware grant-table operation

Evaluation condition: a specific fixed grant-table sequence materially affects current or projected cross-domain call WCET or throughput.

Default disposition: reject as a general engine. Consider only a single bounded operation that neither allocates nor selects authority.

### Autonomous memory scrub or revocation walker

Evaluation condition: projected retention, reliability, or reclamation demand would consume material scheduled-core capacity or erode operating margin.

Default disposition: reject. First increase block-operation width, dedicate a low-end core, or run the sweep during certified mode transitions.

### Executable-overlay loader

Evaluation condition: projected code growth materially erodes one-tier roster margin after code stripping, dictionary encoding, static placement, and gain-cell/stacked-memory evaluation.

Default disposition: defer. It adds residency, instruction-stream, invalidation, and loader-authority proofs.

## Explicit non-candidates

Do not open a design-space study without a normative amendment changing the relevant architectural goal.

* [ ] No hardware priority scheduler, budget donation, or work-conserving slot mechanism.
* [ ] No endpoint/object TLB, CSpace walker, or capability-name translation table.
* [ ] No autonomous revocation, garbage-collection, paging, prefetch, or relocation walker.
* [ ] No descriptor-following general ring engine.
* [ ] No runtime allocator or placement engine.
* [ ] No programmable parser, protocol processor, embedded controller, or device firmware core.
* [ ] No interrupt priority/threshold/delivery controller beyond the pending array.
* [ ] No high-water tracking, lazy clearing, or history-sensitive zeroization.
* [ ] No cache, victim buffer, return-address stack, dynamic predictor, or adaptive prefetcher.
* [ ] No generic checkpoint, hibernation, or overlay engine.

## Candidate evaluation record

Copy this block for each proposed accelerator.

### Candidate: [name]

* Owner:
* Target release/profile:
* Existing software/compiler mechanism:
* Current constraint or future performance opportunity:
* Workloads and compositions measured:
* Projected workload, scale, and service-life assumptions:
* Baseline WCET:
* Proposed WCET:
* Baseline and proposed throughput/latency:
* Performance headroom gained:
* Baseline area/SRAM/energy:
* Proposed area/SRAM/energy:
* Admission or core-count decisions changed:
* Future admission/core-count margin gained:
* Architectural state added:
* Hidden state added:
* Authority added or destroyed:
* Memory touched and how addresses are supplied:
* Fault and partial-completion semantics:
* Partition-switch state class:
* Sail clauses added/deleted:
* RTL-refinement obligations added/deleted:
* Non-interference obligations added/deleted:
* Absence-contract clauses affected:
* Software oracle:
* FPGA/prototype evidence:
* Sensitivity to workload growth and profile changes:
* Continuation threshold:
* Disposition: admit / defer / reject
* Requirement IDs affected:
* Reviewer rationale:

## Recommended evaluation order

1. Validate the latency, area, and proof cost of existing CHERI, revocation, zeroization, timer, notification, DMA, ECC, and `fence.t` primitives.
2. Measure the complete partition-switch decomposition on each core class.
3. Evaluate V/M all-state clear and safe switch-phase overlap for lower switch cost, greater switch-duty headroom, and future admission capacity.
4. Benchmark software revocation sweep, quarantine footprint, and `cloadtags` group width while evaluating block reclamation against current and projected demand.
5. Run the backend corpus measurement for fixed-list save/restore after outlining and dictionary encoding stabilize.
6. Evaluate the static instruction scratchpad against measured and projected shared-SRAM pressure, WCET, throughput, and admitted-core headroom.
7. Evaluate new fixed-function datapaths against hard-deadline margin, throughput, latency, energy, isolation, and core-count capacity.
8. Open policy-bearing or autonomous engines only after a normative amendment, not as routine optimization.
