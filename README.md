# VerifiedOS

Design for an end-to-end formally verified computer, built around a bespoke in-order RV64IMV+CHERI system-on-chip and a seL4-inspired multikernel operating system. The proof chain is meant to run unbroken from abstract specification through source, binary, and ISA down to the modeled hardware. Engineering effort is treated as free and trust as the scarce resource, so security is placed ahead of performance and broad compatibility with other hardware or software; the reference instantiation is a mobile/laptop-class device, form-factor-agnostic in principle.

> This repository is a living design specification. Nothing here is built or released.

## Design highlights

- **Bespoke seL4-inspired multikernel.** A minimal capability kernel, one instance per core, re-derived from seL4's object model rather than ported, with everything else running as unprivileged, capability-confined compartments.
- **SRAM-only memory architecture with end-to-end ECC.** Memory is bespoke on-die SRAM, error-corrected from the register file through to main memory. Being flat and fast, it removes the L1/L2/L3 cache hierarchy, cache coherence, DRAM channels, refresh and PRAC machinery, and the `Zicbom` cache-management instructions; the Rowhammer and RowPress charge-disturbance primitives go with the capacitors. Being on-die, it also removes the external memory bus, the socketed module, and the cold-boot remanence window, so the memory encryption and anti-replay tree a DRAM design needs are deleted rather than scoped.
- **CHERI in place of the usual protection hardware.** Capabilities carry spatial memory safety in hardware, so there is no virtual memory, MMU, PMP, IOMMU, IOPMP, or supervisor/user privilege modes, and none of the many instructions or control registers those mechanisms require.
- **Temporal safety and no uninitialized reads.** Beyond the spatial bounds CHERI enforces, freed memory is made unreachable: capability revocation (a budgeted sweep plus a per-access check) together with linear and affine capability types, enforced by a mandatory typed assembly language (TAL), rules out use-after-free. The same TAL tracks which memory a program has written, so a program that could read a location before writing it is rejected when it is installed rather than caught while it runs, and memory is zeroed when it is allocated, so old data is never left behind for it to find. Neither guarantee costs any dedicated hardware.
- **No speculative or out-of-order execution.** Cores issue in-order with static-only branch prediction, so the whole transient-execution attack surface (Spectre, Meltdown, and the microarchitectural data-sampling family) is absent by construction rather than mitigated. Instruction-level parallelism comes only from static, exposed mechanisms: wide in-order issue, decoder-stage macro-op fusion, and vector (RVV) execution.
- **No simultaneous multithreading (SMT).** Each core runs a single hardware thread, removing the cross-thread contention and shared-resource timing channels that SMT exposes and keeping execution timing deterministic.
- **Graphics, AI, and signal processing on general-purpose cores.** GPU-, NPU-, and DSP-class work (rendering, machine learning, and radio or sensor signal processing) runs on general-purpose vector (RVV) and matrix cores that share the base ISA, capability model, and proofs with the scalar cores. There is no fixed-function GPU, no discrete accelerator, and no opaque coprocessor; heterogeneity lives in the datapath, never in the trust structure. The accepted price is throughput in the 2010s integrated-GPU and early-NPU class.
- **No firmware coprocessors.** Radios, sensors, and inputs are driven by ordinary verified CPU cores under one ISA and one set of proofs, not opaque baseband or controller firmware.
- **On-die OpenTitan-class root of trust.** Built on a scalar RV64+CHERI core, the platform's only management processor, for measured boot, key custody, and attestation.

## Bug classes removed by construction

This is an inventory of the guarantees targeted by the **full specified stack**, not a claim about a system that exists today. Nothing is built yet, and many of the crown-jewel specifications and proofs are explicitly unauthored. The construction uses four different discharge modes: **absent** means the mechanism needed to express the bug is deleted; **hardware-enforced** means every access is checked by the CHERI machine; **admission-rejected** means the CHERI-TAL checker refuses the binary before installation; **proved** means the shipped artifact or composed system must carry a machine-checked theorem. These are stronger and narrower claims than “written in a safe language.”

### RISC-V and microarchitectural omissions

| Potential bug or attack class | Why it cannot arise in the specified machine | Mode |
| --- | --- | --- |
| Spectre, Meltdown, transient execution, and microarchitectural data sampling | No speculative execution, transient state, reorder buffer, or reservation stations exist | **Absent** |
| Cross-thread SMT leakage and sibling-thread state corruption | One hardware thread per core; there is no second thread context | **Absent** |
| Branch-predictor poisoning, BTB aliasing, and return-stack poisoning | Prediction is static-only; BHT/PHT, BTB, and RAS state do not exist | **Absent** |
| Cache timing, cache eviction, cache coherence, and stale-cache bugs | Flat SRAM replaces the I-cache, D-cache, L2/LLC hierarchy, tag cache, and coherence protocol | **Absent** |
| TLB, page-table-walk, A/D-bit, alias-mapping, and TLB-shootdown bugs | Virtual memory, the MMU, page tables, TLBs, and walk caches are deleted | **Absent** |
| Privilege-ring confusion and S/U transition bugs | Machine mode is the only mode; privileged operations require an unforgeable CHERI permission on PCC | **Absent / hardware-enforced** |
| PMP, IOMMU, and IOPMP configuration gaps or inconsistent protection views | Those parallel protection mechanisms are deleted; one capability model governs CPU and DMA access | **Absent** |
| LR/SC livelock, spurious-failure retry, CAS retry, and capability-sized ABA machinery | `Zalrsc` and `Zacas` are excluded, and admitted code has no such retry loop | **Absent** |
| Self-modifying-code and instruction-stream synchronization bugs | Runtime code generation, writable executable memory, `fence.i`, and writable-to-executable promotion are absent | **Absent / admission-rejected** |
| Rowhammer, RowPress, and DRAM read-disturbance bit flips | Main memory is SRAM: a bistable latch has no leaking capacitor and no refresh cycle, so neither the repeated-activation nor the row-open-time disturbance primitive has an analog, and the counting-and-back-off machinery (RFM, PRAC) is deleted rather than re-tuned per variant. SRAM's own far weaker read/write-disturb and half-select modes remain, corrected by the end-to-end ECC, with an uncorrectable event a fail-stop | **Absent** |
| Memory-bus probing, DIMM and module interposers, and cold-boot remanence | Main memory is bespoke SRAM on the same die as the cores: there is no external memory bus to probe, no socketed or soldered module to interpose on, and no die-to-die link, so the interface these attacks need does not exist. The array is volatile with near-zero remanence and is zeroized anyway, leaving nothing to recover from a powered-down machine. This is why the design carries no memory encryption and no integrity or anti-replay tree: what remains is an adversary already inside the package, which is invasive physical attack, out of scope by name | **Absent** |
| History-dependent prefetch, DVFS, refresh, and reactive power-control channels | Prefetchers, frequency control, DRAM refresh/PRAC, and activity-driven control loops are absent | **Absent** |
| Variable-latency secret operations | Secret-reachable operations are fixed-latency or rejected by the information-flow discipline | **Hardware-enforced / admission-rejected** |

The auditable list of invisible hardware structures is the [microarchitectural absence contract](absence-contract.md); the complete architectural profile is the [frozen ISA profile](isa-profile.md).

### CHERI capability tags, bounds, and monotonicity

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Stack, heap, object, and sub-object buffer overflows or out-of-bounds reads | Every usable pointer is a tagged capability with hardware-enforced bounds | **Hardware-enforced** |
| Pointer forgery, integer-to-pointer confusion, and fabricated device addresses | Integers and raw bit patterns cannot create a valid tagged capability; authority must derive from an existing capability | **Hardware-enforced** |
| Pointer-provenance violations | Capability validity records derivation in hardware; the admitted ISA exposes no integer-to-capability escape | **Hardware-enforced / admission-rejected** |
| Permission escalation and confused derivation | Bounds and permissions only narrow; derivation cannot add authority | **Hardware-enforced** |
| Cross-object, cross-compartment, and cross-kernel-partition corruption | Each object and partition is reachable only through bounded capabilities rooted in the static distribution | **Hardware-enforced** |
| C/C++, assembly, unsafe-Rust, compiler, or DMA code bypassing spatial checks | Capability checks apply to emitted machine accesses regardless of source language; DMA carries explicit capability operands | **Hardware-enforced** |
| Writable-code injection and executable-data promotion | The initial capability forest contains no Store-and-Execute authority, and monotonicity preserves that W^X invariant | **Hardware-enforced / proved** |
| Corrupted pointers accidentally becoming live authority | A modified capability loses its validity tag or fails its bounds and permission checks | **Hardware-enforced** |

### CHERIoT-lineage compartments, sentries, and lifetime

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Ambient authority, global namespace privilege, `setuid`-style escalation, and authority acquired by name | A compartment can name only capabilities in its manifest; no uid/gid, global namespace, `fork()`, or ambient device access exists | **Absent / hardware-enforced** |
| Path traversal and `../` escape, symlink and hardlink races, and `/tmp`-style filename TOCTOU | The whole "resolve a string to an object" class is unexpressible: there is no ambient namespace to resolve against, a path is only an app-local alias for a capability already in the manifest, and no runtime `mount`/`bind`, global directory, path-based capability lookup, or symlink indirection exists to redirect one. The resolved capability *is* the object, so no re-resolution window separates check from use | **Absent** |
| Malicious or compromised dependencies corrupting their caller or reaching unrelated resources | Attacker-facing and over-authorized libraries are separate least-authority compartments in the static graph | **Hardware-enforced / proved** |
| Forged entry points, calls into the middle of a component, and forged or replayed return addresses | Sealed forward- and backward-edge sentries constrain entry and return sites | **Hardware-enforced** |
| Unprivileged code accessing system registers or switch machinery | Access-system-register authority is a permission on PCC, held only by the kernel | **Hardware-enforced** |
| Stale capabilities surviving object reuse | Linear lifetime typing, revocation epochs, a budgeted sweep, quarantine, and the per-access load filter invalidate the old tenant before reuse | **Hardware-enforced / admission-rejected / proved** |
| Runtime creation of unreviewed protection domains or authority edges | Compartments, imports, exports, shared windows, and schedule slots are fixed and checked at composition or package admission | **Absent / admission-rejected** |
| Kernel memory exhaustion, allocation-failure paths, and out-of-memory kills | The kernel allocates nothing after boot: every kernel object is carved from untyped memory delegated from userland, each core's instance owns a disjoint pool, and IPC rings are bounded and pre-composed. A compartment can exhaust only what it was itself given, so there is no shared kernel heap to drain, no allocation that can fail, and no reclaim policy to attack | **Absent** |
| Permission-dialog spoofing and confused consent delegation | Only the trusted powerbox may attenuate and grant device authority; apps neither draw the prompt nor mint the grant | **Hardware-enforced / proved** |

### Static time partitioning

A compartment's share of the processor is decided at composition, as a slot in a fixed table or a core of its own, so scheduling is a static artifact rather than a runtime policy and nothing a compartment does can enlarge its share. That bounds what one compartment can take from another; it does not make availability under fault a guarantee, which §17 books separately.

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| CPU starvation and scheduling denial of service by a hostile or runaway compartment | Each core runs a table-driven cyclic executive of fixed, time-triggered slots: no priorities, no run queue to enqueue on, no runtime scheduling decision, and no budget donation | **Absent** |
| Priority inversion, priority-inheritance chains, and kernel lock contention | There are no priorities to invert, no shared mutable kernel data, and no kernel locks or kernel threads; the kernel is entered only by a synchronous trap or the slot-boundary timer, and runs on the caller's budget | **Absent** |
| Interrupt storms and interrupt-driven preemption of an unrelated partition | Asynchronous interrupt delivery does not exist: arrival is latched pending state read by ordinary loads in the owner's own slot, and the slot-boundary timer is the machine's only asynchronous trap | **Absent** |
| Slot overruns and forced revocation sweeps spilling into another partition's time | Admission is an interval-arithmetic proof that the slot budgets fit the major frame, and the schedule is non-work-conserving; an overrun is a fault that restarts the offending partition, and a compartment that churns grants forces sweeps only of its own footprint, paid from fixed slots that cannot grow | **Absent / proved** |

### Mon CHÉRI property, re-homed without a second tag plane

VerifiedOS adopts Mon CHÉRI's **Write-before-Read guarantee**, but not its additional runtime metadata plane. The same property is checked statically as CHERI-TAL definite initialization, while eager zeroization also prevents prior-tenant disclosure.

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Reads of uninitialized locals, heap slots, fields, or representation padding | A load type-checks only where the slot's initialization attribute is set on every incoming control-flow path | **Admission-rejected** |
| Disclosure of a prior tenant's data through unwritten memory | Allocation eagerly zeroizes the slot before it enters its new live range | **Absent** |
| Treating device-filled memory as initialized before DMA completion | The verified HAL consumes exclusive CPU ownership and returns initialized ownership only on completion | **Admission-rejected / proved** |
| Partial or ambiguous initialization across an IPC boundary | Typed IDL messages and copy-once parsers write fixed destinations whole and carry initialization state explicitly | **Admission-rejected / proved** |

### CHERI-TAL and binary admission

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Use-after-free, dangling pointers, and double use or double free of linear authority | Linear and affine capabilities deny duplication and track lifetime through the typed binary | **Admission-rejected** |
| Data races across threads, compartments, or devices | Live writable authority excludes every overlapping alias; shared synchronization cells must have explicit atomic types | **Admission-rejected / proved** |
| Type confusion, ABI mismatch, malformed control flow, and calls to undeclared callees | Type/ABI conformance, both halves of CFI, and the manifest callee set are checked on the final binary | **Admission-rejected** |
| Integer overflow and underflow | Arithmetic is total by typing; range side conditions reject trapping and wrapping executions | **Admission-rejected / proved** |
| Ignored security, integrity, freshness, admission, or transaction verdicts | Relevance typing requires each security-bearing result to be examined before its authority-bearing effect can continue | **Admission-rejected** |
| Hidden mutable globals, lazy statics, thread-locals, and singleton state escaping the authority graph | The image is inspected for ambient mutable state and capabilities outside its declared initial set | **Admission-rejected** |
| Secret-dependent branches, addresses, or variable-latency operations | Secret taint is checked by the constant-time type discipline; unstructured residuals carry a relational proof over the leakage model | **Admission-rejected / proved** |
| Unbounded loops, handlers that outlive a slot, and timing-budget overruns | Syntax-directed WCET costs and loop-bound proofs must fit the static cyclic-executive slot | **Admission-rejected / proved** |
| Stack exhaustion, unbounded recursion, and stack-clash writes into adjacent objects | The same static facts bound space as bound time: an enumerated callee set makes call-graph acyclicity and recursion depth provable, and a binary whose depth is unbounded is refused rather than run out of memory. The stack is reached only through a bounds-checked capability, so an overrun faults rather than landing in a neighboring object, and there is no guard page to jump over | **Admission-rejected / hardware-enforced** |
| Compiler-created memory-safety regressions | Safety is checked from the final machine code and its derivation; compiler pedigree is not an admission input | **Admission-rejected** |
| Compiler or build-farm output that does not implement its included source | Every package carries its exact content-addressed source closure and a kernel-checked theorem from that closure through assembly, linking, and the final image | **Admission-rejected / proved** |

### Verified OS, I/O, storage, and supply-chain construction

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Parser buffer errors, unchecked lengths, recursive-input exhaustion, and representation-padding leaks | Every attacker-facing format uses a schema-bounded, non-recursive, verified copy-once Narcissus parser | **Absent / proved** |
| Authority smuggling through IPC payloads | Ring payloads cannot store capabilities; they carry only indices into a pre-delegated per-session table | **Hardware-enforced / proved** |
| Ring publication races, torn ownership, and peer mutation of published slots | One canonical bounded SPSC ring library, linear ownership transfer, explicit atomics, and `Ztso` fences define the only transitions | **Admission-rejected / proved** |
| DMA time-of-check/time-of-use races over a live buffer | Submission consumes the CPU's exclusive capability and returns it only after device completion | **Admission-rejected / proved** |
| Deadlock and livelock in shared filesystem operations | RefFS-style linearizability and MoLi definite-release proofs are prerequisites to temporal admission | **Proved** |
| Torn writes, inconsistent recovery, and process-resume state corruption | The log and filesystem carry crash-refinement proofs; recovery reconstructs from measured boot rather than resuming execution state | **Proved** |
| Offline storage tampering, ciphertext substitution, and silent corruption | Authenticate-then-return AEAD plus the Merkle structure rejects unauthenticated data | **Hardware-enforced / proved** |
| Unauthorized rollback of system generations | Signed roots, monotonic counters, and an anti-rollback floor constrain which generation may boot | **Hardware-enforced / proved** |
| Loader, dynamic-linker, relocation, and executable-format parser bugs | There is no on-device ELF loader or dynamic linker; a small verified content-addressed image reader and capability-wiring table replace them | **Absent / proved** |
| Malicious compiler, package, dependency, or build-farm output bypassing platform safety | The final artifact is independently type- or proof-checked and proved to correspond to its included source closure; source-level malicious dependencies remain least-authority contained | **Admission-rejected / proved** |
| Firmware bugs in basebands, SSD controllers, GPUs, NPUs, sensor hubs, and management engines | Those programmable foreign computers are absent; fixed-function matter is driven by verified host software | **Absent** |

This inventory deliberately does **not** claim to eliminate memory leaks, incorrect app intent, specification errors, cryptographic hardness failures, denial of service, social-engineering mistakes, analog or physical attacks, or every protocol-level flaw. Functional correctness is mandatory for the TCB, not for arbitrary apps. Those limits and the still-open proof work are recorded in the normative specification's §17 and in [critique.md](critique.md).

## Specification

The normative design lives in [verification-maximal-os.md](verification-maximal-os.md), with non-normative companions covering [prior art](inspirations.md), [evaluated architectural alternatives](architectural-alternatives.md), an [implementation plan](implementation-plan.md), and [performance estimates](performance-estimates.md).

Per §5, the artifact the independent-specification-review release gate audits is the [atomic-requirements register](requirements-register.md) — each normative obligation as a numbered requirement with an acceptance criterion, traced to the crown-jewel spec it constrains and to the prose as rationale. It covers all eighteen normative sections as 954 numbered requirements. Its standing output is the extraction-defect list — normative claims that resist atomic restatement, which §5 treats as spec defects to repair in the prose rather than register omissions to work around. That list carries one open defect, `D-CSR`, whose seven rows are surviving CSRs that the frozen profile had to enumerate and that no requirement decides.

Three **derived views** collect what the register states across many entries but no document held:

- The [frozen instruction-set profile](isa-profile.md) — the single enumeration of the ISA: base, adopted extensions, exclusions with their grounds, the CHERI feature set, per-class datapath parameters, and the timing contracts. This is what §18's schedule root and first day-one deliverable consume.
- The [microarchitectural absence contract](absence-contract.md) — sixteen enumerated absences with the netlist evidence an auditor searches for, both discharge forms, the table-freeness rule, and the `fence.t` four-class completeness map. Per §18 it is buildable on day one and is the one part of the least-built layer (RTL ⊑ Sail) that does not need that layer to exist first.
- The [crown-jewel inventory](crown-jewels.md) — the twenty-two specifications the §5 review gate audits, each with its `CJ-` trace target, the requirements constraining it, and whether it has been authored; plus the seven theorem targets and the specification each is proven against. It is the specification workstream's work list, and its status column is the countable form of the as-existing assurance gap.

Each cites the governing requirement for every row and is defective, never authoritative, where it disagrees with the register. Traces cite the prose by `<a id="r-ss-nnn">` bookmark rather than by line number, so editing the prose moves the target with the text, and no figure any of these documents asserts is maintained by hand.

`tools/check.ps1` holds all of it and exits non-zero on any finding: every citation resolves to something live, no view drops a requirement in the subsections it bears, and every asserted count matches the artifact that owns it, rewritten in place under `-Fix`. It is one tool because a derived fact restated where nothing checks it is one defect: a line number, a membership list, and a count are the same mistake at three granularities.
