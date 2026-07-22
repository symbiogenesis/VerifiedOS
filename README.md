# VerifiedOS

Design for an end-to-end formally verified computer, built around a bespoke in-order RV64IMV+CHERI system-on-chip and a seL4-inspired multikernel operating system. The proof chain is meant to run unbroken from abstract specification through source, binary, and ISA down to the modeled hardware. Engineering effort is treated as free and trust as the scarce resource, so security is placed ahead of performance and ahead of broad hardware or software compatibility; the reference instantiation is a mobile/laptop-class device, and the design is form-factor-agnostic in principle.

> This repository is a living design specification. Nothing here is built or released.

## Design highlights

- **Bespoke seL4-inspired multikernel.** A minimal capability kernel, one instance per core, re-derived from seL4's object model rather than ported, with everything else running as unprivileged, capability-confined compartments.
- **SRAM-only memory architecture with end-to-end ECC.** Memory is bespoke on-die SRAM, error-corrected from the register file through to main memory. Being flat and fast, it removes the L1/L2/L3 cache hierarchy, cache coherence, DRAM channels, refresh and PRAC machinery, and the `Zicbom` cache-management instructions.
- **CHERI in place of the usual protection hardware.** Capabilities carry spatial memory safety in hardware, so there is no virtual memory, MMU, PMP, IOMMU, IOPMP, or supervisor/user privilege modes — and none of the many instructions or control registers those mechanisms require.
- **Temporal safety and no uninitialized reads.** Beyond the spatial bounds CHERI enforces, freed memory is made unreachable: capability revocation (a budgeted sweep plus a per-access check) together with linear and affine capability types, enforced by a mandatory typed assembly language (TAL), rules out use-after-free. A hardware Write-before-Read tag on every memory granule additionally traps any read of a location not written since it was zeroized, so uninitialized data is never observed.
- **No speculative or out-of-order execution.** Cores issue in-order with static-only branch prediction, so the whole transient-execution attack surface (Spectre, Meltdown, and the microarchitectural data-sampling family) is absent by construction rather than mitigated. Instruction-level parallelism comes only from static, exposed mechanisms: wide in-order issue, decoder-stage macro-op fusion, and vector (RVV) execution.
- **No simultaneous multithreading (SMT).** Each core runs a single hardware thread, removing the cross-thread contention and shared-resource timing channels that SMT exposes and keeping execution timing deterministic.
- **Graphics, AI, and signal processing on general-purpose cores.** GPU-, NPU-, and DSP-class work (rendering, machine learning, and radio or sensor signal processing) runs on general-purpose vector (RVV) and matrix cores that share the base ISA, capability model, and proofs with the scalar cores. There is no fixed-function GPU, no discrete accelerator, and no opaque coprocessor; heterogeneity lives in the datapath, never in the trust structure. The accepted price is throughput in the 2010s integrated-GPU and early-NPU class.
- **No firmware coprocessors.** Radios, sensors, and inputs are driven by ordinary verified CPU cores under one ISA and one set of proofs, not opaque baseband or controller firmware.
- **On-die OpenTitan-class root of trust.** Built on a scalar RV64+CHERI core — the platform's only management processor — for measured boot, key custody, and attestation.

## Specification

The normative design lives in [verification-maximal-os.md](verification-maximal-os.md), with non-normative companions covering [prior art](inspirations.md), [evaluated architectural alternatives](architectural-alternatives.md), an [implementation plan](implementation-plan.md), and [performance estimates](performance-estimates.md).
