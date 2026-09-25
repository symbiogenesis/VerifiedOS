# VerifiedOS

Design for an end-to-end formally verified computer, built around a bespoke in-order CHERI-enabled RV64IMV-inspired system-on-chip and a seL4-inspired multikernel operating system. The proof chain is meant to run unbroken from abstract specification through source, binary, and ISA down to the modeled hardware.

Engineering effort is treated as free and trust as the scarce resource, so security comes ahead of performance and ahead of compatibility with existing hardware and software.

The first release targets a [general-purpose laptop](docs/spec.md#r-18-004a). The [release scope](docs/spec.md#r-18-004) defers the browser, handset and server ensemble. The design [prefers open standards wherever its guarantees permit](docs/spec.md#r-04-001a); the [compute and graphics compatibility plan](docs/implementation/compute-compatibility.md) records the proposed OpenCL, SPIR-V, HIP and Vulkan SC surfaces.

> This repository is a living design specification. Nothing here is built or released.

<details>
<summary><strong>Contents</strong></summary>

<details>
<summary>✨ <strong><a href="#design-highlights">Design highlights</a></strong></summary>

- [Bespoke seL4-inspired multikernel](#bespoke-sel4-inspired-multikernel)
- [Deterministic where a guarantee needs it, elastic where the desktop does](#deterministic-where-a-guarantee-needs-it-elastic-where-the-desktop-does)
- [Fixed-latency on-die memory with end-to-end ECC](#fixed-latency-on-die-memory-with-end-to-end-ecc)
- [One die is one machine, and a server is several](#one-die-is-one-machine-and-a-server-is-several)
- [CHERI in place of the usual protection hardware](#cheri-in-place-of-the-usual-protection-hardware)
- [Temporal safety and no uninitialized reads](#temporal-safety-and-no-uninitialized-reads)
- [No speculative or out-of-order execution](#no-speculative-or-out-of-order-execution)
- [No simultaneous multithreading (SMT)](#no-simultaneous-multithreading-smt)
- [Verified cores and qualified devices](#verified-cores-and-qualified-devices)
- [On-die OpenTitan-class root of trust](#on-die-opentitan-class-root-of-trust)
- [The device holder owns the root](#the-device-holder-owns-the-root)
- [The device builds its own software](#the-device-builds-its-own-software)
- [Memory planned before boot, with one elastic pool for the desktop](#memory-planned-before-boot-with-one-elastic-pool-for-the-desktop)

</details>

<details>
<summary>🧱 <strong><a href="#bug-classes-removed-by-construction">Bug classes removed by construction</a></strong></summary>

- [RISC-V and microarchitectural omissions](#risc-v-and-microarchitectural-omissions)
- [CHERI capability tags, bounds, and monotonicity](#cheri-capability-tags-bounds-and-monotonicity)
- [CHERIoT-lineage compartments, sentries, and lifetime](#cheriot-lineage-compartments-sentries-and-lifetime)
- [Static time partitioning](#static-time-partitioning)
- [Mon CHÉRI property, re-homed without a second tag plane](#mon-chéri-property-re-homed-without-a-second-tag-plane)
- [CHERI-TAL and binary admission](#cheri-tal-and-binary-admission)
- [Verified OS, I/O, storage, and supply-chain construction](#verified-os-io-storage-and-supply-chain-construction)
- [Faults the machine detects rather than prevents](#faults-the-machine-detects-rather-than-prevents)
- [Obligations discharged elsewhere](#obligations-discharged-elsewhere)
- [The proof artifacts themselves](#the-proof-artifacts-themselves)
- [What this inventory does not claim](#what-this-inventory-does-not-claim)

</details>

**📐 [Specification](#specification)**

**⚖️ [License](#license)**

</details>

## ✨ Design highlights <a id="design-highlights"></a>

### Bespoke seL4-inspired multikernel

One minimal capability kernel runs per core; other services run in confined compartments. The [kernel design](docs/spec.md#r-07-001) takes seL4's endpoints and non-interference goal, with a static object graph and CHERI capabilities replacing its dynamic object machinery.

### Deterministic where a guarantee needs it, elastic where the desktop does

The [fixed tier](docs/spec.md#r-07-037f) reserves time and memory for trusted services and deadlines. Desktop applications launch, close and share resources inside a fixed [elastic-domain envelope](docs/spec.md#r-07-037e); its contract defines dispatch, bounded yields and the isolation boundary.

### Fixed-latency on-die memory with end-to-end ECC

On-die SRAM and denser gain-cell memory provide two fixed latency classes, with CHERI tags, ECC and revocation checks on both. The [memory profile](docs/hardware/isa-profile.md#7-microarchitectural-mandates-carried-by-the-profile) owns the placement and timing rules; bulk capacity depends on qualifying a physical part.

### One die is one machine, and a server is several

A [machine occupies one die](docs/spec.md#r-15-162). A later [server ensemble](docs/spec.md#r-02-003a) adds whole machines with separate memory and trust roots, connected by scheduled authenticated messages. Its contract states the scaling limits and qualification gates.

### CHERI in place of the usual protection hardware

Pointers carry hardware-checked bounds and permissions. The [ISA profile's exclusions](docs/hardware/isa-profile.md#6-exclusions) record the resulting removal of address translation and parallel protection mechanisms.

### Temporal safety and no uninitialized reads

[CHERI-TAL admission](docs/spec.md#r-05-029) adds lifetime and initialization checks to CHERI's spatial bounds. [Revocation and reclamation](docs/spec.md#r-08-004) prevent stale authority surviving reuse; zeroization prevents prior-tenant disclosure.

### No speculative or out-of-order execution

Cores issue in order with static-only prediction. The [microarchitectural absence contract](docs/hardware/absence-contract.md) specifies how the missing speculative and history-dependent structures are audited.

### No simultaneous multithreading (SMT)

Each core has one hardware thread. The [absence contract](docs/hardware/absence-contract.md#3-the-register) also requires evidence that no second thread context exists.

### Verified cores and qualified devices

Scalar, vector and matrix [core classes](docs/hardware/isa-profile.md#8-core-classes) share one ISA and capability model. Graphics, software inference and device control run on those cores. An optional [immutable inference module](docs/spec.md#r-04-010b) has a separate device contract and remains qualification work.

### On-die OpenTitan-class root of trust

The [root of trust](docs/spec.md#r-09-001) handles measured boot, key custody and attestation on a scalar CHERI core.

### The device holder owns the root

The holder controls the [generation-signing root set](docs/spec.md#r-09-036a), including removal of the vendor's key. That contract distinguishes generation admission from immutable firmware roots, production debug restrictions and the rollback floor.

### The device builds its own software

A [resident certifying toolchain](docs/spec.md#r-13-027) lets the holder build and prove software locally. Its output follows the same admission rules as any producer's: [native code enters a successor generation; Wasm app bundles run as interpreted data in the current session](docs/spec.md#r-02-008).

### Memory planned before boot, with one elastic pool for the desktop

Fixed-tier storage is assigned before boot. Within its fixed envelope, the desktop uses [runtime allocation from reserved pools](docs/spec.md#r-08-047a), with [verified chunk isolation and safe reuse](docs/spec.md#r-08-047b). The pool contract owns exhaustion, fragmentation and quarantine costs.

## 🧱 Bug classes removed by construction <a id="bug-classes-removed-by-construction"></a>

This inventory states the guarantees targeted by the **full specified stack**, not by an existing system: nothing is built, and many crown-jewel specifications and proofs remain unauthored. Each row claims one or more of seven discharge modes. Native binary guarantees apply to native apps and interpreter hosts; an interpreted guest has [arena confinement and the stated guest-semantic limits](docs/spec.md#r-14-013a), so native object-level safety is not implicitly a property of its linear memory.

Four say the bug class cannot occur at all:

- 🕳️ **Absent**: the bug's enabling mechanism is deleted.
- 🛡️ **Enforced**: the CHERI hardware checks every access.
- ✋ **Rejected**: CHERI-TAL admission refuses the binary before installation.
- ✅ **Proved**: what ships carries a machine-checked theorem, subject to the [proof-artifact gates](#the-proof-artifacts-themselves).

Three claim something weaker:

- 🔔 **Detected**: a fault the detector is built for can occur but never silently: it is corrected or contained fail-stop, never claimed absent.
- 🤝 **Transferred**: a real obligation owned by the named party; naming it makes it countable, nothing more.
- 🚩 **Residual**: the row names what it leaves open; the spec's [residual-risks](docs/spec.md#17-residual-risks-the-honest-ceiling) section carries it.

### RISC-V and microarchitectural omissions

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Transient-execution attacks, from Spectre and Meltdown to microarchitectural data sampling | No speculative execution, transient state, reorder buffer, or reservation stations exist | **🕳️&nbsp;Absent** |
| Cross-thread SMT leakage and sibling-thread state corruption | One hardware thread per core; there is no second thread context | **🕳️&nbsp;Absent** |
| Poisoning or aliasing of any dynamic predictor state | Prediction is static-only; BHT/PHT, BTB, and RAS state do not exist | **🕳️&nbsp;Absent** |
| Cache timing and cache-eviction side channels | Two fixed-speed memory classes replace the cache hierarchy, leaving no hit/miss latency or eviction pattern to modulate; which class an address sits in is fixed when the image is composed, not by what ran recently, and the address term that survives, which SRAM bank an access selects, is refused at the address in admitted secret-typed code | **🕳️&nbsp;Absent**<br>**✋&nbsp;Rejected** |
| Cache-coherence protocol and stale-cache bugs | With no cached copies there is no coherence protocol to get wrong and no stale line to serve | **🕳️&nbsp;Absent** |
| Address-translation and paging bugs | Virtual memory, the MMU, page tables, TLBs, walk caches, and the shootdown protocol are deleted | **🕳️&nbsp;Absent** |
| Privilege-ring confusion and S/U transition bugs | Machine mode is the only mode; privileged operations require an unforgeable CHERI permission on PCC | **🕳️&nbsp;Absent**<br>**🛡️&nbsp;Enforced** |
| Configuration gaps and inconsistent views across parallel protection hardware | PMP, IOMMU, and IOPMP are deleted; one capability model governs CPU and DMA access | **🕳️&nbsp;Absent** |
| LR/SC livelock and spurious-failure retry loops | `Zalrsc` is excluded, and admitted code has no such retry loop | **🕳️&nbsp;Absent**<br>**✋&nbsp;Rejected** |
| CAS retry and capability-sized ABA machinery | `Zacas` is excluded, so no compare-and-swap exists to retry or to hand a recycled value | **🕳️&nbsp;Absent** |
| Self-modifying-code and instruction-stream synchronization bugs | Runtime emission into executable memory, writable executable memory, `fence.i`, and writable-to-executable promotion are absent; same-session Wasm apps are interpreted data | **🕳️&nbsp;Absent** |
| DRAM read-disturbance bit flips on the fast class | An SRAM latch gives Rowhammer and RowPress no leaking capacitor or refresh cycle to disturb; SRAM's far weaker disturb modes are detected faults below | **🕳️&nbsp;Absent** |
| Read-disturbance on the bulk class | The bulk gain cell has no capacitor, but its own disturb behaviour is a device property measured before a part qualifies and claimed nowhere ahead of that measurement; whatever it returns is met by cell margin, ECC, and the fixed refresh schedule, an uncorrectable event stopping the machine rather than passing silently, and never by a counter reacting to what was accessed | **🔔&nbsp;Detected**<br>**🚩&nbsp;Residual** |
| Reactive refresh machinery: activation counters, alerts, and back-off | The bulk class is topped up on a schedule fixed when the image is composed, so nothing counts accesses and nothing reacts to them | **🕳️&nbsp;Absent** |
| Memory-bus probing and DIMM or module interposition | On-die memory has no external memory bus, module, or die-to-die link to probe; an ensemble link joins two whole machines and carries scheduled frames, never a load or store, so it is not a memory bus either | **🕳️&nbsp;Absent** |
| Cold-boot remanence | Both memory classes and key storage need construction-specific power-loss qualification. Completed zeroization and authority discharge do not establish erasure after abrupt loss; the [physical residuals](docs/spec.md#r-17-058) remain explicit | **🚩&nbsp;Residual** |
| History-dependent prefetch channels | Prefetchers are absent | **🕳️&nbsp;Absent** |
| DVFS and reactive power-control channels | Frequency control and activity-driven control loops are absent | **🕳️&nbsp;Absent** |
| Refresh-timing channels | DRAM refresh and PRAC activity do not exist to observe | **🕳️&nbsp;Absent** |
| Interconnect and quality-of-service contention channels | The admission proof emits a static time-division fabric schedule; best-effort arbitration does not exist. The NoC model is unauthored, so this absence is structural, not yet proved | **🕳️&nbsp;Absent**<br>**🚩&nbsp;Residual** |
| Contention between high-assurance memory islands | A high-assurance island takes a whole SRAM macro or tier and hosts one domain, sharing no path, arbiter, or revocation array with any peer; the unauthored-model residual above applies | **🕳️&nbsp;Absent**<br>**🚩&nbsp;Residual** |
| Contention between low-sensitivity islands sharing an SRAM macro, or domains sharing an island | Static per-island arbitration, sub-slotted per core inside a shared island, schedules the contention away; the macro's periphery, power delivery, and thermal mass, and inside a shared island the bank ports and the atomic stage, stay shared under a schedule rather than deleted, and the same residual applies | **🚩&nbsp;Residual** |
| Variable latency on a secret operand | Every secret-reachable operation is fixed-latency (integer divide, the vector FPU including subnormals, atomics), and misaligned accesses trap rather than split | **🛡️&nbsp;Enforced** |
| Variable-latency `vfdiv`/`vfsqrt` reached by a secret | The one exception to fixed latency is flow-rejected: no admitted crypto kernel uses either instruction | **✋&nbsp;Rejected** |
| Secret-dependent address timing across SRAM banks | The flow discipline rejects a secret-labeled address, scalar or vector element, in admitted secret-typed code, and the non-work-conserving schedule confines the term to the issuing partition's own slot; no constant-time claim is made outside that code | **✋&nbsp;Rejected** |

The timing rows claim architectural timing only: power and near-field electromagnetic leakage are outside that model, answered by the crypto core's masked datapath, whose row in [CHERI-TAL and binary admission](#cheri-tal-and-binary-admission) carries the probing-model residual.

The auditable list of invisible hardware structures is the [microarchitectural absence contract](docs/hardware/absence-contract.md); the complete architectural profile is the [frozen ISA profile](docs/hardware/isa-profile.md).


### CHERI capability tags, bounds, and monotonicity

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Buffer overflows and out-of-bounds access, down to sub-object fields | Every usable pointer is a tagged capability with hardware-enforced bounds. In the fixed tier the offline memory plan lays each object out so every narrowing is exact, the install check refusing one that would round; in the desktop's elastic pool every allocation comes from a size-class table fixed at composition, so the heap library's narrowing to each allocation is exact as well | **🛡️&nbsp;Enforced**<br>**✋&nbsp;Rejected** |
| Pointer and device-address forgery | Integers and raw bit patterns cannot create a valid tagged capability; authority must derive from an existing capability | **🛡️&nbsp;Enforced** |
| Pointer-provenance violations | Capability validity records derivation in hardware; the admitted ISA exposes no integer-to-capability escape | **🛡️&nbsp;Enforced**<br>**🕳️&nbsp;Absent** |
| Permission escalation and confused derivation | Bounds and permissions only narrow; derivation cannot add authority | **🛡️&nbsp;Enforced** |
| Corruption reaching across any isolation boundary | Each object, compartment, and kernel partition is reachable only through bounded capabilities rooted in the static distribution | **🛡️&nbsp;Enforced** |
| Unsafe-language or compiler-emitted code bypassing spatial checks | Capability checks apply to emitted machine accesses regardless of source language | **🛡️&nbsp;Enforced** |
| DMA bypassing spatial or revocation checks | Device transfers carry explicit capability operands, checked like CPU accesses; a window held by a running transfer is re-authorized against the revocation bitmap at each of its fabric grants, an obligation on the fabric the residual-risk register carries | **🛡️&nbsp;Enforced**<br>**🚩&nbsp;Residual** |
| Writable-code injection and executable-data promotion | No permission encoding holds store together with execute, so a W+X capability is unrepresentable rather than merely underivable, and the only writer of executable memory on either class is the measured-boot loader, ahead of any core's release, so a region written while the machine runs never becomes executable | **🕳️&nbsp;Absent**<br>**🛡️&nbsp;Enforced**<br>**✅&nbsp;Proved** |
| Corrupted pointers accidentally becoming live authority | A modified capability loses its validity tag or fails its bounds and permission checks | **🛡️&nbsp;Enforced** |


### CHERIoT-lineage compartments, sentries, and lifetime

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Ambient authority and authority acquired by name | A compartment can name only capabilities in its manifest; no global namespace or ambient device access exists | **🕳️&nbsp;Absent**<br>**🛡️&nbsp;Enforced** |
| `setuid`-style privilege escalation | There is no uid/gid identity to assume and no `fork()` to inherit it through; authority is only what the manifest delegates | **🕳️&nbsp;Absent** |
| Path traversal and `../` escape | A path is only an app-local alias for a manifest capability; no runtime `mount`/`bind`, global directory, or path-based capability lookup can reach outside the manifest | **🕳️&nbsp;Absent** |
| TOCTOU races through filename and link re-resolution | The capability *is* the object, and no symlink indirection exists, leaving no re-resolution window between check and use | **🕳️&nbsp;Absent** |
| Shell injection and `system()`-style string-to-process execution | There is no text shell, `fork()`/`exec()`, or `PATH` lookup to turn composed text into an action; *run this command* asks the service manager to start a capability-delegated compartment | **🕳️&nbsp;Absent** |
| Environment-variable injection | No environment block exists to inherit or poison | **🕳️&nbsp;Absent** |
| Argument injection between composed commands | The command interpreter pipes typed values between typed-signature commands, never byte streams for each stage to reparse | **🕳️&nbsp;Absent** |
| Dispatch hijack, handler registration to content sniffing | The handler/translator graph is finite, signed, and fixed at composition; no runtime act can add a handler or reroute a format to one | **🕳️&nbsp;Absent** |
| Malicious or compromised dependencies corrupting their caller or reaching unrelated resources | Attacker-facing and over-authorized libraries are separate least-authority compartments in the static graph | **🛡️&nbsp;Enforced**<br>**✅&nbsp;Proved** |
| Escape from an embedded script engine into its host | The platform ships one pure-interpreter Wasm engine with machine-checked soundness and robust guest confinement against the pinned guest semantics: an adversarial module influences host and peers only through its embedding's declared imports and exports; an app that rolls its own engine keeps the transferred row below | **✅&nbsp;Proved**<br>**🤝&nbsp;Transferred** |
| Forged entry points and calls into the middle of a component | Sealed forward-edge sentries constrain entry to declared sites | **🛡️&nbsp;Enforced** |
| Forged or replayed return addresses | Sealed backward-edge sentries constrain return sites | **🛡️&nbsp;Enforced** |
| Unprivileged code accessing system registers or switch machinery | Access-system-register authority is a permission on PCC, held only by the kernel | **🛡️&nbsp;Enforced** |
| Stale capabilities surviving object reuse | Linear lifetime typing, revocation epochs, a budgeted sweep, quarantine, and the per-load filter over the loading island's own revocation array invalidate the old tenant before reuse; a device-held copy dies at its window's next fabric grant, and the desktop pool reuses a chunk only after the same sweep | **🛡️&nbsp;Enforced**<br>**✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |
| Heap-allocator corruption, double allocation, and cross-app heap grooming on the desktop | The desktop pool's service is verified: live chunks are disjoint, exactly bounded and zeroed before handoff, and a released chunk returns only after revocation sweeps it; an app's own heap can damage only chunks it holds, CHERI bounding every access, and no pool capability can be held outside the domain | **✅&nbsp;Proved**<br>**🛡️&nbsp;Enforced** |
| Runtime creation of unreviewed protection domains or authority edges | Compartments, imports, exports, shared windows, and schedule slots are fixed and checked at composition or package admission; launching a desktop app activates a context the composition already placed | **🕳️&nbsp;Absent**<br>**✋&nbsp;Rejected** |
| Kernel memory exhaustion and allocation-failure paths | The kernel neither allocates after boot nor exposes an allocation primitive; the composition-time memory plan places every kernel object | **🕳️&nbsp;Absent** |
| Out-of-memory kills and cross-compartment memory pressure | Fixed-tier compartments can exhaust only their own pre-composed allotments, with no shared kernel heap or reclaim policy. Desktop apps share one fixed pool: its exhaustion walks a declared ladder over that domain's own apps, hibernating a background app and never the focused one, with no global reserve, victim scan or kill daemon, and the pressure apps put on each other inside it is a recorded residual | **🕳️&nbsp;Absent**<br>**🚩&nbsp;Residual** |
| Permission-dialog spoofing and confused consent delegation | Only the trusted powerbox may attenuate and grant device authority, and the prompt's pixels and touches are the trusted-path agent's under one root-of-trust latch that also lights the hardware indicator: neither an app nor the compositor draws the prompt, draws over it, or mints the grant | **🛡️&nbsp;Enforced**<br>**✅&nbsp;Proved** |
| A declassification grant wider than the object it named | The non-interference theorem models a powerbox grant as a delimited release, CHERI-bounded to the object consent named, never a general high-to-low conduit. Whether the user named the right object is transferred below | **✅&nbsp;Proved**<br>**🛡️&nbsp;Enforced** |
| A declassification an attacker can drive | Robust declassification quantifies over every compromised-component strategy: whether, what, and to whom the powerbox releases depends only on the unforgeable consent act and verified powerbox logic | **✅&nbsp;Proved** |
| An inter-level edge that outlives the act that created it | First-class revocation bounds the grant's lifetime, making an overlong edge a revocation failure rather than a policy exception | **✅&nbsp;Proved**<br>**🛡️&nbsp;Enforced** |


### Static time partitioning

A compartment receives a fixed-table slot or whole core at composition; no runtime action can enlarge that share. This bounds interference, not availability under fault, a separately recorded residual. The desktop's elastic domain is one such tenant: inside it, apps share its slots by a proved proportional share rather than by fixed slots, and the rows below say where that changes the claim.

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| CPU starvation and scheduling denial of service by a hostile or runaway compartment | Each core runs a table-driven cyclic executive of fixed, time-triggered slots: no priorities, no run queue, and no runtime decision over the table. Inside the desktop's elastic domain a runaway app receives only its proved proportional share and cannot touch another tenant's slot | **🕳️&nbsp;Absent**<br>**✅&nbsp;Proved** |
| Priority inversion and priority-inheritance chains | There are no priorities to invert, so no inheritance chain can form; the desktop's dispatch uses weights and virtual deadlines rather than priorities, and no call blocks | **🕳️&nbsp;Absent** |
| Kernel lock contention | There is no shared mutable kernel data, no kernel locks, and no kernel threads; the kernel runs on the caller's budget | **🕳️&nbsp;Absent** |
| Interrupt storms and interrupt-driven preemption of an unrelated partition | Interrupt arrival is latched pending state read by ordinary loads in the owner's own slot; the slot-boundary timer is the machine's only asynchronous trap | **🕳️&nbsp;Absent** |
| Termination and progress channels between partitions | The frame is non-work-conserving across labels: a partition that idles, diverges, or faults burns its slot without moving any boundary, so peers observe the schedule, never its progress. A compartment can read its own slot width, and apps inside the desktop's elastic domain share a label and can see one another's progress; both are recorded residuals | **🕳️&nbsp;Absent**<br>**🚩&nbsp;Residual** |
| A desktop app's time or memory spilling into the fixed tier or another tenant | The elastic domain's envelope of slots, cores and pool is fixed at composition; no app's runtime choice moves another tenant's slot or byte, the boundary timer never cuts an app mid-reaction, and no capability derived from the pool can leave the domain | **🕳️&nbsp;Absent**<br>**🛡️&nbsp;Enforced** |
| Slot overruns spilling into another partition's time | An interval-arithmetic admission proof fits every slot budget within the major frame, and overrun restarts the offender | **🕳️&nbsp;Absent**<br>**✅&nbsp;Proved** |
| Forced revocation sweeps spilling into another partition's time | Grant churn sweeps only the granter's footprint, within fixed slots that cannot grow | **🕳️&nbsp;Absent**<br>**✅&nbsp;Proved** |
| Cross-machine back-pressure, flow-control stalls, and contention over an ensemble link | The link's slot tables are an output of the admission artifact beside the fabric schedule: non-work-conserving, no arbitration, no retry, no flow control, so a peer can fill its own slots and never move this machine's frame; the unauthored isolation-model residual applies | **🕳️&nbsp;Absent**<br>**🚩&nbsp;Residual** |


### Mon CHÉRI property, re-homed without a second tag plane

VerifiedOS adopts Mon CHÉRI's **Write-before-Read guarantee** without its runtime metadata plane: CHERI-TAL checks definite initialization statically, while eager zeroization prevents prior-tenant disclosure.

| Potential bug class | Construction | Mode |
| --- | --- | --- |
| Reads of any uninitialized location, representation padding included | A load type-checks only where the slot's initialization attribute is set on every incoming control-flow path | **✋&nbsp;Rejected** |
| Disclosure of a prior tenant's data through unwritten memory | Allocation eagerly zeroizes the slot before it enters its new live range | **🕳️&nbsp;Absent** |
| Treating device-filled memory as initialized before DMA completion | The verified HAL consumes exclusive CPU ownership and returns initialized ownership only on completion | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |
| Partial or ambiguous initialization across an IPC boundary | Typed IDL messages and copy-once parsers write fixed destinations whole and carry initialization state explicitly | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |


### CHERI-TAL and binary admission

| Potential bug class | Construction | Mode |
| --- | --- | --- |
| Use-after-free and dangling pointers | Linear lifetime typing tracks every allocation through the typed binary, so no capability to freed memory survives to be dereferenced | **✋&nbsp;Rejected** |
| Double use or double free of linear authority | Linear and affine capabilities deny duplication, so an authority cannot be spent twice | **✋&nbsp;Rejected** |
| Data races across threads, compartments, or devices | Live writable authority excludes every overlapping alias; shared synchronization cells must have explicit atomic types | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |
| Type confusion and ABI mismatch | Type and ABI conformance are checked on the final binary | **✋&nbsp;Rejected** |
| Malformed control flow and calls to undeclared callees | Both halves of CFI and the manifest callee set are checked on the final binary | **✋&nbsp;Rejected** |
| Implicit integer wrap | An unannotated operation cannot silently trap, because no exception or unwinding path exists, and cannot silently wrap: modular and saturating arithmetic survive only as explicitly named operations | **✋&nbsp;Rejected** |
| Overflow or underflow over static bounds | Range side conditions ride on the arithmetic rules: the on-device checker decides them over closed numerals, and a bound that depends on a runtime value enters as a declared premise the checker reads as given and a release-time proof term discharges | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |
| Overflow in code admitted at Tier 2 | Tier 2 scopes the range obligation out, a recorded residual; in-range but wrong remains functional correctness at every tier | **🚩&nbsp;Residual** |
| Silently dropped security-bearing verdicts | Relevance typing denies weakening an integrity, freshness, admission, or transaction verdict, so a binary cannot eliminate one without examining it | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |
| A wrong response to an examined verdict | The grade bounds the *drop*, never the *response*: proceeding after an examined failure remains functional correctness, a recorded residual | **🚩&nbsp;Residual** |
| Ambient mutable state escaping the authority graph | The image is inspected for hidden mutable state (globals, lazy statics, thread-locals, singletons) and capabilities outside its declared initial set | **✋&nbsp;Rejected** |
| Secret-dependent timing in admitted code | The constant-time type discipline rejects secret taint at branches, addresses, and variable-latency operations; unstructured residuals carry a relational proof over the leakage model | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |
| Nonce and initialization-vector reuse | A linear nonce is consumed by sealing and cannot be duplicated, stored, or reached twice, even across a restored checkpoint or a re-derived key | **✋&nbsp;Rejected** |
| Secret residue in scalar registers and compiler-introduced spill slots | A must-erase grade, checked on the final binary, lets no secret-typed value or spilled copy of one be dropped by anything but an erasing operation | **✋&nbsp;Rejected** |
| Power and near-field electromagnetic analysis of the crypto core | The secret-handling datapath is masked, and its *d*-probing and composition theorems are verified on the artifact against a stated probing model; the model is an axiom about the silicon, its faithfulness the recorded residual | **✅&nbsp;Proved**<br>**🚩&nbsp;Residual** |
| Secret residue in the frames of a compartment that returns | Restart erases the compartment's whole footprint before any reuse | **🕳️&nbsp;Absent** |
| Secret-dependent traps and the restart they cause | Constant-time typing makes trap choice a function of public inputs, and restart consumes only the offender's slots | **✋&nbsp;Rejected**<br>**🕳️&nbsp;Absent** |
| A crash record disclosing more than its labeled fault class | The sentinel receives a labeled fault from a closed enumeration, never verbose logs; that the record's shape bounds the class has no theorem, a recorded residual | **🕳️&nbsp;Absent**<br>**🚩&nbsp;Residual** |
| Unit, dimension, and clock-domain confusion in quantity arithmetic | Quantities carry a phantom dimension decided by type equality and erased before code generation, so cycles cannot stand in for microseconds or bytes for elements | **✋&nbsp;Rejected** |
| Unbounded or slot-overrunning execution | Syntax-directed WCET costs and loop-bound proofs must fit the static cyclic-executive slot; a desktop app instead proves a bounded interval between compiler-inserted yield points, which needs no loop bound | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |
| Stack exhaustion and unbounded recursion | The enumerated callee set proves call-graph acyclicity and recursion depth, so worst-case stack use is static; unbounded depth is refused | **✋&nbsp;Rejected** |
| Stack-clash writes into adjacent objects | A bounds-checked stack capability makes overrun fault rather than reach a neighboring object, with no guard page to bypass | **🛡️&nbsp;Enforced** |
| Compiler-created memory-safety regressions | Safety is checked from the final machine code and its derivation; compiler pedigree is not an admission input | **✋&nbsp;Rejected** |
| Compiler or build-farm output that does not implement its included source | Every package carries its exact content-addressed source closure and a theorem from that closure through assembly, linking, and the final image, which the proof kernel checks on the device at install beside the type check | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |


### Verified OS, I/O, storage, and supply-chain construction

| Potential bug, fault, or attack class | Construction | Mode |
| --- | --- | --- |
| Parser bugs, from unchecked lengths to recursive-input exhaustion | Every attacker-facing format uses a schema-bounded, non-recursive, verified Narcissus parser | **🕳️&nbsp;Absent**<br>**✅&nbsp;Proved** |
| Representation-padding leaks in encoded output | Copy-once serialization emits only bytes the schema defines, so no stale padding reaches the wire | **✅&nbsp;Proved** |
| Non-canonical encodings parting byte identity from value identity | Every descriptor used for signing, hashing, addressing, or equality carries a machine-checked canonicity theorem: decode is injective, and re-encoding a decoded input reproduces its bytes; without the theorem, a format cannot serve an identity role | **✅&nbsp;Proved**<br>**✋&nbsp;Rejected** |
| Query injection, the `SQL`-shaped class | A query supplies a namespace capability and a typed bounded predicate, never command text; even a maximally permissive predicate returns only capabilities derivable from the one supplied | **🕳️&nbsp;Absent**<br>**🛡️&nbsp;Enforced** |
| Configuration injection and text-configuration parsing divergence | Trusted components parse no runtime text configuration; each generation compiles configuration to typed signed objects | **🕳️&nbsp;Absent** |
| Authority smuggling through IPC payloads | Ring payloads cannot store capabilities, on the die or across an ensemble link; they carry only indices into a pre-delegated per-session table, an ensemble-link frame naming the receiving machine's table and nothing on the sending one | **🛡️&nbsp;Enforced**<br>**✅&nbsp;Proved** |
| Ring protocol violations, publication race to peer mutation | One canonical bounded SPSC ring library, linear ownership transfer, explicit atomics, and `Ztso` fences define the only transitions | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |
| DMA time-of-check/time-of-use races over a live buffer | Submission consumes the CPU's exclusive capability and returns it only after device completion | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved** |
| Deadlock and livelock in shared filesystem operations | RefFS-style linearizability and MoLi definite-release proofs are prerequisites to temporal admission | **✅&nbsp;Proved** |
| Torn writes and inconsistent crash recovery | The log and filesystem carry crash-refinement proofs | **✅&nbsp;Proved** |
| Process-resume state corruption | Recovery reconstructs from measured boot rather than resuming execution state, so no saved execution image exists to corrupt | **🕳️&nbsp;Absent** |
| Offline storage tampering and ciphertext substitution | Authenticate-then-return AEAD and the Merkle structure reject unauthenticated data before any byte is returned | **🛡️&nbsp;Enforced**<br>**✅&nbsp;Proved** |
| Silent storage corruption and bit rot | Patrol reads scrub decay and read-disturb, rewriting pages approaching the correction limit; corruption that outruns the scrub fails authentication rather than returning silently | **🔔&nbsp;Detected** |
| Unauthorized rollback of system generations | Signed roots, monotonic counters, and an anti-rollback floor constrain which generation may boot | **🛡️&nbsp;Enforced**<br>**✅&nbsp;Proved** |
| Reopening test, debug, or manufacturing access | A fixed acyclic lifecycle over one-way OTP fuses has no such transition: leaving test disables every debug and manufacturing interface at once, and nothing reopens them | **🕳️&nbsp;Absent**<br>**🛡️&nbsp;Enforced** |
| RMA returning a production device to a debuggable state with its secrets intact | Production's one outgoing edge is an authenticated, terminal RMA transition, preceded by crypto-erase, with no return path | **🛡️&nbsp;Enforced**<br>**🕳️&nbsp;Absent** |
| Engineering-key acceptance outside the factory | Lifecycle state enters the measured chain before ROM verifies any payload, making every transition attested, while state-diversified verification roots leave no engineering key acceptable in production | **🛡️&nbsp;Enforced** |
| Executable-loading and dynamic-linking bugs | There is no on-device ELF loader, dynamic linker, relocation pass, or executable-format parser; a small verified content-addressed image reader and capability-wiring table replace them | **🕳️&nbsp;Absent**<br>**✅&nbsp;Proved** |
| Malicious or compromised supply-chain output bypassing platform safety | Admission re-checks the final artifact's types and proofs with no trust in its build pedigree, the correspondence theorem above ties it to its included source closure, and source-level malicious dependencies remain least-authority contained | **✋&nbsp;Rejected**<br>**✅&nbsp;Proved**<br>**🛡️&nbsp;Enforced** |
| Protocol downgrade and negotiation confusion | Each protocol has one composition-fixed configuration, ciphersuite, and version, with no capability-driven fallback; downgrade generations are absent from silicon | **🕳️&nbsp;Absent** |
| Ensemble-link interposition, peer substitution, or frame replay | A link is an authenticated encrypted session between two mutually attested machines whose unit and composition are fixed when the ensemble is composed, its keys never leaving the crypto core; a peer that fails attestation or attests another composition is refused the link and the machine runs its own generation, an unauthenticated or replayed session frame stops the link at the frame, and the session model is a recorded residual | **✅&nbsp;Proved**<br>**🚩&nbsp;Residual** |
| Link and radio state-machine flaws | A Lustre control plane refines a formal model of the standard's state machine, making unmodeled states, transitions, and timers unreachable | **✅&nbsp;Proved** |
| Model unfaithfulness and composed session security | Each reference model is curated from its protocol's machine-checked symbolic security analysis, so the machine the sequencer provably runs is the one whose session security that analysis checks; what remains recorded is the model's faithfulness to the prose standard, the primitives' symbolic abstraction, and the imported analyses standing as evidence outside the trust base | **🚩&nbsp;Residual** |
| Firmware bugs in auxiliary processors, baseband to management engine | Those programmable foreign computers are absent; fixed-function matter is driven by attested host software | **🕳️&nbsp;Absent** |


### Faults the machine detects rather than prevents

These rows follow a single doctrine: *detect, correct, or contain, never shield*. **Detected** therefore never means absent.

| Potential bug or fault class | Construction | Mode |
| --- | --- | --- |
| Single-event and multi-cell upsets | Every array from the register file to main memory is ECC-corrected, and interleaving separates adjacent-cell strikes | **🔔&nbsp;Detected** |
| A bit flip forging or destroying capability authority | The validity-tag plane carries stronger DECTED (double-error-correct, triple-error-detect) correction, because a flipped tag changes authority rather than data | **🔔&nbsp;Detected** |
| Latent errors accumulating past the correction distance | Background scrubbing finds and repairs errors while they are still correctable | **🔔&nbsp;Detected** |
| An uncorrectable error | The access fails stop rather than returning a value | **🔔&nbsp;Detected** |
| SRAM disturb and half-select upsets | The same end-to-end ECC corrects these operationally induced flips, the far weaker analogs of the deleted DRAM disturbance classes | **🔔&nbsp;Detected** |
| A dead or degraded noise source weakening the one entropy root | Independent sources spanning at least two physical mechanisms are health-tested at startup and continuously after; failure is fail-stop, never a degraded draw. A failure the tests miss remains a recorded residual | **🔔&nbsp;Detected**<br>**🚩&nbsp;Residual** |
| Physical fault injection, glitching to laser to EM | ECC corrects stored-state faults, capability corruption traps on tag and bounds checks, the multikernel confines live-kernel faults for crash-only restart, and layered watchdogs reach wedged cores | **🔔&nbsp;Detected** |
| A fault the layered detectors miss | Coverage beyond the stated single-fault model is evidence rather than theorem, and consumer-grade transient datapath strikes are unclaimed; both are recorded residuals | **🚩&nbsp;Residual** |
| Skipped critical instructions under an injected fault | The certifying compiler maintains control-flow signatures over boot verification, credential comparison, and lifecycle transitions; acceptance requires a comparison-derived token that fall-through or truncation cannot produce, and its absence under every fault in the protected-sequence single-fault model is a theorem | **🔔&nbsp;Detected**<br>**✅&nbsp;Proved** |
| A fault-corrupted detector that cannot report itself | The sentinel is a detection-only lockstepped pair whose divergence latches fail-stop to the root of trust, with no third replicated core and no voting | **🔔&nbsp;Detected** |
| A partition alive but wedged, or a runaway holding its core | Watchdogs occupy failure domains disjoint from the cores, clock tree, and scheduler: the sentinel monitor restarts, revokes, or rolls back first, and the root of trust's always-on timer on an independent slow clock is the last resort. Only its reset responds within a slot, a recorded limit | **🔔&nbsp;Detected**<br>**🚩&nbsp;Residual** |
| Reset loops hardening into permanent denial of service | Boot counting breaks a reset loop into minimal recovery, bounding downtime rather than permitting it | **🔔&nbsp;Detected** |
| An uncorrectable ensemble-link session frame | Fixed-latency forward error correction corrects what it is built for at a constant cost, and a frame whose authentication tag then fails stops the link rather than delivering a guess; the machine keeps running and the link is re-established at a scheduled instant | **🔔&nbsp;Detected** |


### Obligations discharged elsewhere

Each row names the owner of a real obligation met outside the platform; an unnamed transfer would drop the obligation.

| Class the platform does not close | Where the obligation goes, and what the platform still contributes | Mode |
| --- | --- | --- |
| Injection into an app-supplied interpreter, web content in the browser being the standing case | **The compartment author, for the declining set.** The platform offers one verified Wasm interpreter any app may bind, so the transfer narrows to apps that decline it and to the JS standing case, contained rather than verified; an app's own string parser remains injectable within its compartment, and manifest capabilities bound the blast radius to app authority either way | **🤝&nbsp;Transferred** |
| Upset rates and component reliability beyond what the die's own correction covers | **The deployment.** The platform mandates correction at every point; the deployment selects the radiation-hardening grade, the one source-rate lever an enclosure cannot supply | **🤝&nbsp;Transferred** |
| The user granting the authority they meant to grant | **The human.** The attested, unspoofable powerbox makes the grant mechanism trustworthy and CHERI-bounded, but no proof can establish that the user named the right object; the abuse-resistance half of that ceiling is booked open | **🤝&nbsp;Transferred**<br>**🚩&nbsp;Residual** |


### The proof artifacts themselves

**Proved** means a machine-checked theorem, which can verify while establishing too little. The following mechanical checks apply to proof artifacts rather than the machine and are prerequisites for every use of that mode.

| Potential bug class | Construction | Mode |
| --- | --- | --- |
| A shipped theorem resting on more than its declared assumptions | The proof term enumerates each theorem's axioms and assumptions for exact comparison with the requirements-register declaration; any extra or missing member fails the build | **✅&nbsp;Proved** |
| A theorem that is true and empty: a premise nothing satisfies or a quantifier ranging over nothing | The build gate refuses a proof artifact whose theorems quantify over a record the artifact never constructs, and reports each artifact's constructed witnesses beside its constants; because general vacuity is undecidable, that a witness satisfies its theorem's hypotheses stays a per-theorem obligation read at review, and its residue is booked in the [residual-risks section](docs/spec.md#17-residual-risks-the-honest-ceiling) | **✅&nbsp;Proved**<br>**🚩&nbsp;Residual** |
| A specification so weak that anything refines it | Every refinement and policy claim exhibits an instance the specification rejects, a construction the proof artifact carries and the review gate reads; no build check decides that the rejected instance is a telling one, and that judgement is booked in the [residual-risks section](docs/spec.md#17-residual-risks-the-honest-ceiling) | **✅&nbsp;Proved**<br>**🚩&nbsp;Residual** |


### What this inventory does not claim

This inventory does **not** claim to eliminate memory leaks, incorrect app intent, specification errors, cryptographic hardness failures, denial of service, social-engineering mistakes, analog or physical attacks, or every protocol flaw. Canonicity covers this platform's encodings. Agreement with an independent peer additionally requires that peer's grammar, interpretation, and implementation correspondence. A cooperating peer can supply artifacts for a bounded equivalence proof; without them, parser differentials remain untrusted evidence and a [recorded residual](docs/spec.md#r-17-016b).

The transferred rows count limits owned elsewhere. The specification's [residual-risks section](docs/spec.md#17-residual-risks-the-honest-ceiling) and [critique.md](docs/background/critique.md) record those limits and open proof work.

This inventory summarizes named archetypes; it is not the coverage claim, because such a list can never be complete. The register-computed [coverage matrix](docs/assurance/coverage-matrix.md), spanning every boundary and property, makes that claim.

## 📐 Specification <a id="specification"></a>

The [documentation index](docs/README.md) groups the companions by subject: languages, hardware, assurance, implementation, performance, and background.

## ⚖️ License <a id="license"></a>

Original documentation is [CC BY 4.0](LICENSE-docs.md); original code and proofs are [Apache 2.0](LICENSE.md). The modified [Sail model](model/) retains its [BSD two-clause license](model/LICENCE). The [licensing map](COPYRIGHT.md#the-map) owns path-specific terms and exceptions; [THIRD-PARTY.md](THIRD-PARTY.md) records upstream components.
