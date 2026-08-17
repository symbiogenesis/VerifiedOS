# VerifiedOS

Design for an end-to-end formally verified computer, built around a bespoke in-order CHERI-enabled RV64IMV-inspired system-on-chip and a seL4-inspired multikernel operating system. The proof chain is meant to run unbroken from abstract specification through source, binary, and ISA down to the modeled hardware.

Engineering effort is treated as free and trust as the scarce resource, so security comes ahead of performance and ahead of compatibility with existing hardware and software. The reference design is a mobile/laptop-class device, though nothing ties the design to that form factor.

> This repository is a living design specification. Nothing here is built or released.

<details>
<summary><strong>Contents</strong></summary>

- [Design highlights](#design-highlights)
  - [Bespoke seL4-inspired multikernel](#bespoke-sel4-inspired-multikernel)
  - [SRAM-only memory with end-to-end ECC](#sram-only-memory-with-end-to-end-ecc)
  - [CHERI in place of the usual protection hardware](#cheri-in-place-of-the-usual-protection-hardware)
  - [Temporal safety and no uninitialized reads](#temporal-safety-and-no-uninitialized-reads)
  - [No speculative or out-of-order execution](#no-speculative-or-out-of-order-execution)
  - [No simultaneous multithreading (SMT)](#no-simultaneous-multithreading-smt)
  - [Everything on general-purpose verified cores](#everything-on-general-purpose-verified-cores)
  - [On-die OpenTitan-class root of trust](#on-die-opentitan-class-root-of-trust)
- [Bug classes removed by construction](#bug-classes-removed-by-construction)
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
- [Specification](#specification)
  - [The typed assembly language](#the-typed-assembly-language)
  - [The atomic-requirements register](#the-atomic-requirements-register)
  - [Derived views](#derived-views)
  - [The consistency checker](#the-consistency-checker)

</details>

## Design highlights

### Bespoke seL4-inspired multikernel

A minimal capability kernel, one instance per core; everything else runs as unprivileged, capability-confined compartments. From seL4 it takes two ideas, not code: message-passing endpoints, and the non-interference statement that one partition cannot influence what another observes. The rest of seL4's object model (untyped memory and retype, the capability space, the derivation tree) is deleted: with the object graph fixed at composition and capabilities held in CHERI's hardware tags, each piece either has no user or duplicates the hardware. Deleting the derivation tree retires its revocation proof, the plan's hardest scheduled subproof.

### SRAM-only memory with end-to-end ECC

All memory is bespoke on-die SRAM, error-corrected from the register file to main memory. Uniformly fast, it needs no L1/L2/L3 cache hierarchy, no coherence protocol to keep cached copies in sync, no DRAM channels, no refresh or Rowhammer-counting (PRAC) machinery, no `Zicbom` cache-management instructions; Rowhammer and RowPress themselves vanish with the DRAM capacitors they disturb. On-die, it leaves no external memory bus to probe, no memory module to interpose, and no data in powered-down chips for a cold-boot attack, so the memory encryption and anti-replay tree a DRAM design needs are deleted rather than added to the proof workload.

### CHERI in place of the usual protection hardware

Every pointer is a CHERI capability (a tagged, hardware-checked value carrying its own bounds and permissions), so there is no virtual memory, MMU, PMP, IOMMU, IOPMP, or supervisor/user privilege modes, and none of their many instructions and control registers.

### Temporal safety and no uninitialized reads

CHERI's bounds are spatial; a mandatory typed assembly language (TAL) checks two more guarantees at install time. Use-after-free: freed memory is made unreachable by capability revocation (a budgeted sweep plus a per-access check) and by linear and affine capabilities, which cannot be duplicated. Uninitialized reads: the TAL rejects any binary that could read a location before writing it, and allocation zeroes memory so no earlier tenant's data survives. Neither costs dedicated hardware.

### No speculative or out-of-order execution

Cores issue in order with static-only branch prediction, so the entire transient-execution attack surface (Spectre, Meltdown, and the microarchitectural data-sampling family) is absent by construction rather than mitigated. Instruction-level parallelism comes only from static, software-visible mechanisms: wide in-order issue, decoder-stage macro-op fusion, and vector (RVV) execution.

### No simultaneous multithreading (SMT)

Each core runs a single hardware thread, so SMT's cross-thread contention and shared-resource timing channels do not exist, and execution timing stays deterministic.

### Everything on general-purpose verified cores

No firmware coprocessors. Graphics, machine learning, signal processing, and every radio, sensor, and input device run on general-purpose scalar, vector (RVV), and matrix cores that share one base ISA, one capability model, and one set of proofs. There is no fixed-function GPU, discrete accelerator, or opaque baseband or controller firmware: no processor on the chip runs code the proofs do not cover. Heterogeneity lives in the datapath, never in the trust structure. The accepted price is compute throughput in the class of a 2010s integrated GPU or early NPU.

### On-die OpenTitan-class root of trust

A scalar CHERI-enabled RV64 core under the same ISA, capability model, and proofs, the platform's only management processor, handles measured boot, key custody, and attestation.

## Bug classes removed by construction

This inventory states the guarantees targeted by the **full specified stack**, not by an existing system: nothing is built, and many crown-jewel specifications and proofs remain unauthored. Each row claims one or more of seven discharge modes.

Four say the bug class cannot occur at all:

- 🕳️ **Absent**: the bug's enabling mechanism is deleted.
- 🛡️ **Enforced**: the CHERI hardware checks every access.
- ✋ **Rejected**: CHERI-TAL admission refuses the binary before installation.
- ✅ **Proved**: what ships carries a machine-checked theorem, subject to the [proof-artifact gates](#the-proof-artifacts-themselves).

Three claim something weaker:

- 🔔 **Detected**: the fault can occur but never silently: it is corrected or contained fail-stop, never claimed absent.
- 🤝 **Transferred**: a real obligation owned by the named party; naming it makes it countable, nothing more.
- 🚩 **Residual**: the row names what it leaves open; the spec's [residual-risks](verification-maximal-os.md#17-residual-risks-the-honest-ceiling) section carries it.

All seven are stronger and narrower claims than “written in a safe language.”


### RISC-V and microarchitectural omissions

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Transient-execution attacks, from Spectre and Meltdown to microarchitectural data sampling | No speculative execution, transient state, reorder buffer, or reservation stations exist | **🕳️ Absent** |
| Cross-thread SMT leakage and sibling-thread state corruption | One hardware thread per core; there is no second thread context | **🕳️ Absent** |
| Poisoning or aliasing of any dynamic predictor state | Prediction is static-only; BHT/PHT, BTB, and RAS state do not exist | **🕳️ Absent** |
| Cache timing and cache-eviction side channels | Flat SRAM replaces the cache hierarchy, leaving no hit/miss latency or eviction pattern to modulate | **🕳️ Absent** |
| Cache-coherence protocol and stale-cache bugs | With no cached copies there is no coherence protocol to get wrong and no stale line to serve | **🕳️ Absent** |
| Address-translation and paging bugs | Virtual memory, the MMU, page tables, TLBs, walk caches, and the shootdown protocol are deleted | **🕳️ Absent** |
| Privilege-ring confusion and S/U transition bugs | Machine mode is the only mode; privileged operations require an unforgeable CHERI permission on PCC | **🕳️ Absent**<br>**🛡️ Enforced** |
| Configuration gaps and inconsistent views across parallel protection hardware | PMP, IOMMU, and IOPMP are deleted; one capability model governs CPU and DMA access | **🕳️ Absent** |
| LR/SC livelock and spurious-failure retry loops | `Zalrsc` is excluded, and admitted code has no such retry loop | **🕳️ Absent**<br>**✋ Rejected** |
| CAS retry and capability-sized ABA machinery | `Zacas` is excluded, so no compare-and-swap exists to retry or to hand a recycled value | **🕳️ Absent** |
| Self-modifying-code and instruction-stream synchronization bugs | Runtime code generation, writable executable memory, `fence.i`, and writable-to-executable promotion are absent | **🕳️ Absent** |
| Rowhammer, RowPress, and DRAM read-disturbance bit flips | An SRAM latch has no leaking capacitor or refresh cycle to disturb; SRAM's far weaker disturb modes are detected faults below | **🕳️ Absent** |
| Memory-bus probing and DIMM or module interposition | On-die SRAM has no external memory bus, module, or die-to-die link to probe | **🕳️ Absent** |
| Cold-boot remanence | Near-zero volatile remanence plus zeroization leaves no powered-down data to recover | **🕳️ Absent** |
| History-dependent prefetch channels | Prefetchers are absent | **🕳️ Absent** |
| DVFS and reactive power-control channels | Frequency control and activity-driven control loops are absent | **🕳️ Absent** |
| Refresh-timing channels | DRAM refresh and PRAC activity do not exist to observe | **🕳️ Absent** |
| Interconnect and quality-of-service contention channels | The admission proof emits a static time-division fabric schedule; best-effort arbitration does not exist. The NoC model is unauthored, so this absence is structural, not yet proved | **🕳️ Absent**<br>**🚩 Residual** |
| Contention between high-assurance memory islands | A high-assurance island takes a whole SRAM macro or tier, sharing no path or arbiter with any peer; the unauthored-model residual above applies | **🕳️ Absent**<br>**🚩 Residual** |
| Contention between low-sensitivity islands sharing an SRAM macro | Static per-island arbitration schedules the contention away, leaving only periphery, power delivery, and thermal mass shared; the same residual applies | **🕳️ Absent**<br>**🚩 Residual** |
| Variable latency on a secret operand | Every secret-reachable operation is fixed-latency (integer divide, the vector FPU including subnormals, atomics), and misaligned accesses trap rather than split | **🛡️ Enforced** |
| Variable-latency `vfdiv`/`vfsqrt` reached by a secret | The one exception to fixed latency is flow-rejected: no admitted crypto kernel uses either instruction | **✋ Rejected** |
| Secret-dependent address timing across SRAM banks | The flow discipline rejects secret-labeled element addresses, and the non-work-conserving schedule confines what remains to the issuing partition's slot | **✋ Rejected** |

The timing rows claim architectural timing only: power and near-field electromagnetic leakage are outside the model, and the crypto core is unmasked, a recorded residual.

The auditable list of invisible hardware structures is the [microarchitectural absence contract](absence-contract.md); the complete architectural profile is the [frozen ISA profile](isa-profile.md).


### CHERI capability tags, bounds, and monotonicity

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Buffer overflows and out-of-bounds access at any granularity, down to sub-object fields | Every usable pointer is a tagged capability with hardware-enforced bounds | **🛡️ Enforced** |
| Pointer and device-address forgery | Integers and raw bit patterns cannot create a valid tagged capability; authority must derive from an existing capability | **🛡️ Enforced** |
| Pointer-provenance violations | Capability validity records derivation in hardware; the admitted ISA exposes no integer-to-capability escape | **🛡️ Enforced**<br>**🕳️ Absent** |
| Permission escalation and confused derivation | Bounds and permissions only narrow; derivation cannot add authority | **🛡️ Enforced** |
| Corruption reaching across any isolation boundary | Each object, compartment, and kernel partition is reachable only through bounded capabilities rooted in the static distribution | **🛡️ Enforced** |
| C/C++, assembly, unsafe-Rust, or compiler-emitted code bypassing spatial checks | Capability checks apply to emitted machine accesses regardless of source language | **🛡️ Enforced** |
| DMA bypassing spatial checks | Device transfers carry explicit capability operands, checked like CPU accesses | **🛡️ Enforced** |
| Writable-code injection and executable-data promotion | The initial capability forest contains no Store-and-Execute authority, and monotonicity preserves that W^X invariant | **🛡️ Enforced**<br>**✅ Proved** |
| Corrupted pointers accidentally becoming live authority | A modified capability loses its validity tag or fails its bounds and permission checks | **🛡️ Enforced** |


### CHERIoT-lineage compartments, sentries, and lifetime

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| Ambient authority and authority acquired by name | A compartment can name only capabilities in its manifest; no global namespace or ambient device access exists | **🕳️ Absent**<br>**🛡️ Enforced** |
| `setuid`-style privilege escalation | There is no uid/gid identity to assume and no `fork()` to inherit it through; authority is only what the manifest delegates | **🕳️ Absent** |
| Path traversal and `../` escape | A path is only an app-local alias for a manifest capability; no runtime `mount`/`bind`, global directory, or path-based capability lookup can reach outside the manifest | **🕳️ Absent** |
| TOCTOU races through filename and link re-resolution | The capability *is* the object, and no symlink indirection exists, leaving no re-resolution window between check and use | **🕳️ Absent** |
| Shell injection and `system()`-style string-to-process execution | There is no shell, `fork()`/`exec()`, or `PATH` lookup to turn composed text into an action; *run this command* asks the service manager to start a capability-delegated compartment | **🕳️ Absent** |
| Environment-variable injection | No environment block exists to inherit or poison | **🕳️ Absent** |
| Argument injection between composed commands | The command interpreter pipes typed values between typed-signature commands, never byte streams for each stage to reparse | **🕳️ Absent** |
| Dispatch hijack through runtime handler registration, plugin load, or content sniffing | The handler/translator graph is finite, signed, and fixed at composition; no runtime act can add a handler or reroute a format to one | **🕳️ Absent** |
| Malicious or compromised dependencies corrupting their caller or reaching unrelated resources | Attacker-facing and over-authorized libraries are separate least-authority compartments in the static graph | **🛡️ Enforced**<br>**✅ Proved** |
| Forged entry points and calls into the middle of a component | Sealed forward-edge sentries constrain entry to declared sites | **🛡️ Enforced** |
| Forged or replayed return addresses | Sealed backward-edge sentries constrain return sites | **🛡️ Enforced** |
| Unprivileged code accessing system registers or switch machinery | Access-system-register authority is a permission on PCC, held only by the kernel | **🛡️ Enforced** |
| Stale capabilities surviving object reuse | Linear lifetime typing, revocation epochs, a budgeted sweep, quarantine, and the per-access load filter invalidate the old tenant before reuse | **🛡️ Enforced**<br>**✋ Rejected**<br>**✅ Proved** |
| Runtime creation of unreviewed protection domains or authority edges | Compartments, imports, exports, shared windows, and schedule slots are fixed and checked at composition or package admission | **🕳️ Absent**<br>**✋ Rejected** |
| Kernel memory exhaustion and allocation-failure paths | The kernel neither allocates after boot nor exposes an allocation primitive; the composition-time memory plan places every kernel object | **🕳️ Absent** |
| Out-of-memory kills and cross-compartment memory pressure | Compartments can exhaust only their own pre-composed allotments; there is no shared kernel heap or reclaim policy | **🕳️ Absent** |
| Permission-dialog spoofing and confused consent delegation | Only the trusted powerbox may attenuate and grant device authority; apps neither draw the prompt nor mint the grant | **🛡️ Enforced**<br>**✅ Proved** |
| A declassification grant wider than the object it named | The non-interference theorem models a powerbox grant as a delimited release, CHERI-bounded to the object consent named, never a general high-to-low conduit. Whether the user named the right object is transferred below | **✅ Proved**<br>**🛡️ Enforced** |
| A declassification an attacker can drive | Robust declassification quantifies over every compromised-component strategy: whether, what, and to whom the powerbox releases depends only on the unforgeable consent act and verified powerbox logic | **✅ Proved** |
| An inter-level edge that outlives the act that created it | First-class revocation bounds the grant's lifetime, making an overlong edge a revocation failure rather than a policy exception | **✅ Proved**<br>**🛡️ Enforced** |


### Static time partitioning

A compartment receives a fixed-table slot or whole core at composition; no runtime action can enlarge that share. This bounds interference, not availability under fault, a separately recorded residual.

| Potential bug or attack class | Construction | Mode |
| --- | --- | --- |
| CPU starvation and scheduling denial of service by a hostile or runaway compartment | Each core runs a table-driven cyclic executive of fixed, time-triggered slots: no priorities, no run queue, and no runtime scheduling decision | **🕳️ Absent** |
| Priority inversion and priority-inheritance chains | There are no priorities to invert, so no inheritance chain can form | **🕳️ Absent** |
| Kernel lock contention | There is no shared mutable kernel data, no kernel locks, and no kernel threads; the kernel runs on the caller's budget | **🕳️ Absent** |
| Interrupt storms and interrupt-driven preemption of an unrelated partition | Interrupt arrival is latched pending state read by ordinary loads in the owner's own slot; the slot-boundary timer is the machine's only asynchronous trap | **🕳️ Absent** |
| Termination and progress channels: one partition observing another's completion, progress, or fault | The frame is non-work-conserving: a partition that idles, diverges, or faults burns its slot without moving any boundary, so peers observe the schedule, never its progress. A compartment can read its own slot width, a recorded residual | **🕳️ Absent**<br>**🚩 Residual** |
| Slot overruns spilling into another partition's time | An interval-arithmetic admission proof fits every slot budget within the major frame, and overrun restarts the offender | **🕳️ Absent**<br>**✅ Proved** |
| Forced revocation sweeps spilling into another partition's time | Grant churn sweeps only the granter's footprint, within fixed slots that cannot grow | **🕳️ Absent**<br>**✅ Proved** |


### Mon CHÉRI property, re-homed without a second tag plane

VerifiedOS adopts Mon CHÉRI's **Write-before-Read guarantee** without its runtime metadata plane: CHERI-TAL checks definite initialization statically, while eager zeroization prevents prior-tenant disclosure.

| Potential bug class | Construction | Mode |
| --- | --- | --- |
| Reads of any uninitialized location, representation padding included | A load type-checks only where the slot's initialization attribute is set on every incoming control-flow path | **✋ Rejected** |
| Disclosure of a prior tenant's data through unwritten memory | Allocation eagerly zeroizes the slot before it enters its new live range | **🕳️ Absent** |
| Treating device-filled memory as initialized before DMA completion | The verified HAL consumes exclusive CPU ownership and returns initialized ownership only on completion | **✋ Rejected**<br>**✅ Proved** |
| Partial or ambiguous initialization across an IPC boundary | Typed IDL messages and copy-once parsers write fixed destinations whole and carry initialization state explicitly | **✋ Rejected**<br>**✅ Proved** |


### CHERI-TAL and binary admission

| Potential bug class | Construction | Mode |
| --- | --- | --- |
| Use-after-free and dangling pointers | Linear lifetime typing tracks every allocation through the typed binary, so no capability to freed memory survives to be dereferenced | **✋ Rejected** |
| Double use or double free of linear authority | Linear and affine capabilities deny duplication, so an authority cannot be spent twice | **✋ Rejected** |
| Data races across threads, compartments, or devices | Live writable authority excludes every overlapping alias; shared synchronization cells must have explicit atomic types | **✋ Rejected**<br>**✅ Proved** |
| Type confusion and ABI mismatch | Type and ABI conformance are checked on the final binary | **✋ Rejected** |
| Malformed control flow and calls to undeclared callees | Both halves of CFI and the manifest callee set are checked on the final binary | **✋ Rejected** |
| Implicit integer wrap | An unannotated operation cannot silently trap, because no exception or unwinding path exists, and cannot silently wrap: modular and saturating arithmetic survive only as explicitly named operations | **✋ Rejected** |
| Overflow or underflow over static bounds | Range side conditions ride on the arithmetic rules: the on-device checker decides them where operand bounds are closed numerals, and a release-time proof term covers bounds that depend on runtime values | **✋ Rejected**<br>**✅ Proved** |
| Overflow in code admitted at Tier 2 | Tier 2 scopes the range obligation out, a recorded residual; in-range but wrong remains functional correctness at every tier | **🚩 Residual** |
| Silently dropped security-bearing verdicts: integrity, freshness, admission, transaction | Relevance typing denies weakening a security-bearing result, so a binary cannot eliminate a verdict without examining it | **✋ Rejected**<br>**✅ Proved** |
| A wrong response to an examined verdict | The grade bounds the *drop*, never the *response*: proceeding after an examined failure remains functional correctness, a recorded residual | **🚩 Residual** |
| Ambient mutable state escaping the authority graph | The image is inspected for hidden mutable state (globals, lazy statics, thread-locals, singletons) and capabilities outside its declared initial set | **✋ Rejected** |
| Secret-dependent branches, addresses, or variable-latency operations | Secret taint is checked by the constant-time type discipline; unstructured residuals carry a relational proof over the leakage model | **✋ Rejected**<br>**✅ Proved** |
| Nonce and initialization-vector reuse | A linear nonce is consumed by sealing and cannot be duplicated, stored, or reached twice, even across a restored checkpoint or a re-derived key | **✋ Rejected** |
| Secret residue in scalar registers and compiler-introduced spill slots | Final-binary checking requires every secret-typed value, including unseen spills, to reach an erasing operation | **✋ Rejected** |
| Secret residue in the frames of a compartment that returns | Restart erases the compartment's whole footprint before any reuse | **🕳️ Absent** |
| Secret-dependent traps and the restart they cause | Constant-time typing makes trap choice a function of public inputs, and restart consumes only the offender's slots | **✋ Rejected**<br>**🕳️ Absent** |
| A crash record disclosing more than its labeled fault class | The sentinel receives a labeled fault from a closed enumeration, never verbose logs; that the record's shape bounds the class has no theorem, a recorded residual | **🕳️ Absent**<br>**🚩 Residual** |
| Unit, dimension, and clock-domain confusion in quantity arithmetic | Quantities carry a phantom dimension decided by type equality and erased before code generation, so cycles cannot stand in for microseconds or bytes for elements | **✋ Rejected** |
| Unbounded or slot-overrunning execution | Syntax-directed WCET costs and loop-bound proofs must fit the static cyclic-executive slot | **✋ Rejected**<br>**✅ Proved** |
| Stack exhaustion and unbounded recursion | The enumerated callee set proves call-graph acyclicity and recursion depth, so worst-case stack use is static; unbounded depth is refused | **✋ Rejected** |
| Stack-clash writes into adjacent objects | A bounds-checked stack capability makes overrun fault rather than reach a neighboring object, with no guard page to bypass | **🛡️ Enforced** |
| Compiler-created memory-safety regressions | Safety is checked from the final machine code and its derivation; compiler pedigree is not an admission input | **✋ Rejected** |
| Compiler or build-farm output that does not implement its included source | Every package carries its exact content-addressed source closure and a kernel-checked theorem from that closure through assembly, linking, and the final image | **✋ Rejected**<br>**✅ Proved** |


### Verified OS, I/O, storage, and supply-chain construction

| Potential bug, fault, or attack class | Construction | Mode |
| --- | --- | --- |
| Parser buffer errors, unchecked lengths, and recursive-input exhaustion | Every attacker-facing format uses a schema-bounded, non-recursive, verified Narcissus parser | **🕳️ Absent**<br>**✅ Proved** |
| Representation-padding leaks in encoded output | Copy-once serialization emits only bytes the schema defines, so no stale padding reaches the wire | **✅ Proved** |
| A value carrying more than one admissible encoding, parting byte identity from value identity | Every descriptor used for signing, hashing, addressing, or equality carries a machine-checked canonicity theorem: decode is injective, and re-encoding a decoded input reproduces its bytes. Without the theorem, a format cannot serve an identity role | **✅ Proved**<br>**✋ Rejected** |
| Query injection, the `SQL`-shaped class | A query supplies a namespace capability and a typed bounded predicate, never command text; even a maximally permissive predicate returns only capabilities derivable from the one supplied | **🕳️ Absent**<br>**🛡️ Enforced** |
| Configuration injection and text-configuration parsing divergence | Trusted components parse no runtime text configuration; each generation compiles configuration to typed signed objects | **🕳️ Absent** |
| Authority smuggling through IPC payloads | Ring payloads cannot store capabilities; they carry only indices into a pre-delegated per-session table | **🛡️ Enforced**<br>**✅ Proved** |
| Ring publication races, torn ownership, and peer mutation of published slots | One canonical bounded SPSC ring library, linear ownership transfer, explicit atomics, and `Ztso` fences define the only transitions | **✋ Rejected**<br>**✅ Proved** |
| DMA time-of-check/time-of-use races over a live buffer | Submission consumes the CPU's exclusive capability and returns it only after device completion | **✋ Rejected**<br>**✅ Proved** |
| Deadlock and livelock in shared filesystem operations | RefFS-style linearizability and MoLi definite-release proofs are prerequisites to temporal admission | **✅ Proved** |
| Torn writes and inconsistent crash recovery | The log and filesystem carry crash-refinement proofs | **✅ Proved** |
| Process-resume state corruption | Recovery reconstructs from measured boot rather than resuming execution state, so no saved execution image exists to corrupt | **🕳️ Absent** |
| Offline storage tampering and ciphertext substitution | Authenticate-then-return AEAD and the Merkle structure reject unauthenticated data before any byte is returned | **🛡️ Enforced**<br>**✅ Proved** |
| Silent storage corruption and bit rot | Patrol reads scrub decay and read-disturb, rewriting pages approaching the correction limit; corruption that outruns the scrub fails authentication rather than returning silently | **🔔 Detected** |
| Unauthorized rollback of system generations | Signed roots, monotonic counters, and an anti-rollback floor constrain which generation may boot | **🛡️ Enforced**<br>**✅ Proved** |
| Test-mode re-entry, TAP unlock, and factory-mode escape | A fixed acyclic lifecycle over one-way OTP fuses omits these transitions: leaving test disables every debug and manufacturing interface at once, and nothing reopens them | **🕳️ Absent**<br>**🛡️ Enforced** |
| RMA returning a production device to a debuggable state with its secrets intact | Production's one outgoing edge is an authenticated, terminal RMA transition, preceded by crypto-erase, with no return path | **🛡️ Enforced**<br>**🕳️ Absent** |
| Engineering-key acceptance outside the factory | Lifecycle state enters the measured chain before ROM verifies any payload, making every transition attested, while state-diversified verification roots leave no engineering key acceptable in production | **🛡️ Enforced** |
| Executable-loading and dynamic-linking bugs | There is no on-device ELF loader, dynamic linker, relocation pass, or executable-format parser; a small verified content-addressed image reader and capability-wiring table replace them | **🕳️ Absent**<br>**✅ Proved** |
| Malicious or compromised supply-chain output bypassing platform safety | Admission re-checks the final artifact's types and proofs with no trust in its build pedigree, the correspondence theorem above ties it to its included source closure, and source-level malicious dependencies remain least-authority contained | **✋ Rejected**<br>**✅ Proved**<br>**🛡️ Enforced** |
| Protocol downgrade and negotiation confusion | Each protocol has one composition-fixed configuration, ciphersuite, and version, with no capability-driven fallback; downgrade generations are absent from silicon | **🕳️ Absent** |
| Link and radio state-machine flaws | A Lustre control plane refines a formal model of the standard's state machine, making unmodeled states, transitions, and timers unreachable | **✅ Proved** |
| Model unfaithfulness and composed session security | The state-machine claim is conformance, not protocol security: model faithfulness is review-gated, and composed session security a recorded residual | **🚩 Residual** |
| Firmware bugs in auxiliary processors, baseband to management engine | Those programmable foreign computers are absent; fixed-function matter is driven by verified host software | **🕳️ Absent** |


### Faults the machine detects rather than prevents

Unlike the rows above, these allow the fault to occur but prevent it from passing *silently* and bound its consequence. They follow a single doctrine: *detect, correct, or contain, never shield*. **Detected** therefore never means absent.

| Potential bug or fault class | Construction | Mode |
| --- | --- | --- |
| Single-event and multi-cell upsets | Every array from the register file to main memory is ECC-corrected, and interleaving separates adjacent-cell strikes | **🔔 Detected** |
| A bit flip forging or destroying capability authority | The validity-tag plane carries stronger DECTED (double-error-correct, triple-error-detect) correction, because a flipped tag changes authority rather than data | **🔔 Detected** |
| Latent errors accumulating past the correction distance | Background scrubbing finds and repairs errors while they are still correctable | **🔔 Detected** |
| An uncorrectable error | The access fails stop rather than returning a value | **🔔 Detected** |
| SRAM read-disturb, write-disturb, and half-select upsets | The same end-to-end ECC corrects these operationally induced flips, the far weaker analogs of the deleted DRAM disturbance classes | **🔔 Detected** |
| A dead, stuck, or narrowly trimmed noise source weakening the one entropy root | Independent sources spanning at least two physical mechanisms are health-tested at startup and continuously after; failure is fail-stop, never a degraded draw. A failure the tests miss remains a recorded residual | **🔔 Detected**<br>**🚩 Residual** |
| Voltage or clock glitching, laser, and electromagnetic fault injection | ECC corrects stored-state faults, capability corruption traps on tag and bounds checks, the multikernel confines live-kernel faults for crash-only restart, and layered watchdogs reach wedged cores | **🔔 Detected** |
| A fault the layered detectors miss | Coverage is evidence rather than theorem, and consumer-grade transient datapath strikes are unclaimed; both are recorded residuals | **🚩 Residual** |
| Skipped critical instructions under an injected fault | The certifying compiler maintains control-flow signatures over boot verification, credential comparison, and lifecycle transitions; acceptance requires a comparison-derived token that fall-through or truncation cannot produce | **🔔 Detected** |
| A fault-corrupted detector that cannot report itself | The sentinel is a detection-only lockstepped pair whose divergence latches fail-stop to the root of trust, with no third replicated core and no voting | **🔔 Detected** |
| A partition alive but wedged, or a runaway holding its core | Watchdogs occupy failure domains disjoint from the cores, clock tree, and scheduler: the sentinel monitor restarts, revokes, or rolls back first, and the root of trust's always-on timer on an independent slow clock is the last resort. Only its reset responds within a slot, a recorded limit | **🔔 Detected**<br>**🚩 Residual** |
| Reset loops hardening into permanent denial of service | Boot counting breaks a reset loop into minimal recovery, bounding downtime rather than permitting it | **🔔 Detected** |


### Obligations discharged elsewhere

These three limits are real obligations met outside the platform. Rows make each transfer countable and name its owner; an unnamed transfer would drop the obligation.

| Class the platform does not close | Where the obligation goes, and what the platform still contributes | Mode |
| --- | --- | --- |
| Injection into an interpreter an application brings with it, web content in the browser being the standing case | **The compartment author.** An app's own string parser remains injectable within its compartment; manifest capabilities bound the blast radius to app authority | **🤝 Transferred** |
| Upset rates and component reliability beyond what the die's own correction covers | **The deployment.** The platform mandates correction at every point; the deployment selects the radiation-hardening grade, the one source-rate lever an enclosure cannot supply | **🤝 Transferred** |
| The user granting the authority they meant to grant | **The human.** The attested, unspoofable powerbox makes the grant mechanism trustworthy and CHERI-bounded, but no proof can establish that the user named the right object; the abuse-resistance half of that ceiling is booked open | **🤝 Transferred**<br>**🚩 Residual** |


### The proof artifacts themselves

**Proved** means a machine-checked theorem, which can verify while establishing too little. The following mechanical checks apply to proof artifacts rather than the machine and are prerequisites for every use of that mode.

| Potential bug class | Construction | Mode |
| --- | --- | --- |
| A shipped theorem resting on an admitted lemma, an unresolved obligation, or an axiom nobody declared | The proof term enumerates each theorem's axioms and assumptions for exact comparison with the requirements-register declaration; any extra or missing member fails the build | **✅ Proved** |
| A theorem that is true and empty: a premise nothing satisfies or a quantifier ranging over nothing | Each theorem carries a machine-checked satisfiability witness; because general vacuity is undecidable, this is a per-theorem obligation | **✅ Proved** |
| A specification so weak that anything refines it | Every refinement and policy claim must exhibit an instance the specification rejects | **✅ Proved** |


### What this inventory does not claim

This inventory does **not** claim to eliminate memory leaks, incorrect app intent, specification errors, cryptographic hardness failures, denial of service, social-engineering mistakes, analog or physical attacks, or every protocol flaw. Canonicity covers this platform's encodings, not whether an independent peer accepts the same language; no single-party proof can establish that, so parser differentials remain untrusted evidence and a recorded residual.

The transferred rows count limits owned elsewhere. The specification's [residual-risks section](verification-maximal-os.md#17-residual-risks-the-honest-ceiling) and [critique.md](critique.md) record those limits and open proof work.

This inventory summarizes named archetypes; it is not the coverage claim, because such a list can never be complete. The register-computed [coverage matrix](coverage-matrix.md), spanning every boundary and property, makes that claim.

## Specification

The normative design lives in [verification-maximal-os.md](verification-maximal-os.md), with non-normative companions covering [prior art](inspirations.md), [evaluated architectural alternatives](architectural-alternatives.md), an [implementation plan](implementation-plan.md), and [performance estimates](performance-estimates.md).


### The typed assembly language

The [typed assembly language](typed-assembly-language.md), the typed machine-code language and per-install check that binaries are admitted with, is specified as a standalone project rather than a component: it depends on a machine semantics and a type theory and nothing else, so its correctness argument mentions no operating system. This platform pins a version of its `cheri-rv64` instantiation, which the corpus calls CHERI-TAL.


### The atomic-requirements register

The [atomic-requirements register](requirements-register.md) is the artifact §5's independent-specification-review release gate audits: every normative obligation as a numbered requirement with an acceptance criterion, traced to the crown-jewel spec it constrains and to the prose as rationale. It covers all eighteen normative sections as 1203 numbered requirements.

Its standing output is the extraction-defect list: normative claims that resist atomic restatement, which §5 treats as prose defects to repair rather than register omissions to work around. That list is empty, but the register declines to read emptiness as a clean bill: the sweep for such claims has not been asked exhaustively, so further instances are assumed present rather than absent.


### Derived views

Four **derived views** collect what the register states across many entries but no document held:

- **The [frozen instruction-set profile](isa-profile.md)**: the single enumeration of the ISA, covering base, adopted extensions, exclusions with their grounds, the CHERI feature set, per-class datapath parameters, and the timing contracts. §18's schedule root and first day-one deliverable consume it.
- **The [microarchitectural absence contract](absence-contract.md)**: sixteen enumerated absences with the netlist evidence an auditor searches for, both discharge forms, the table-freeness rule, and the `fence.t` four-class completeness map. Per §18 it is buildable on day one: the one part of the least-built layer (RTL ⊑ Sail) that does not need that layer to exist first.
- **The [crown-jewel inventory](crown-jewels.md)**: the twenty-two specifications the §5 review gate audits, each with its `CJ-` trace target, the requirements constraining it, and whether it has been authored; plus the seven theorem targets and the specification each is proven against. It is the specification workstream's work list, and its status column is the countable form of the as-existing assurance gap.
- **The [coverage matrix](coverage-matrix.md)**: every boundary of the system against every property it must hold, one row per pair, recording the construction, the discharge mode, and the requirements it rests on. Where the inventory above names bug classes, this quantifies over the boundaries, so a pair discharged by nothing and booked by nothing is a failing check rather than a gap someone has to notice.

Every row cites its governing requirement, and each view is defective, never authoritative, where it disagrees with the register. Traces cite the prose by the `<a id="r-ss-nnn">` bookmark a requirement's own number derives rather than by line number, so editing the prose moves the target with the text, and neither those references nor any figure these documents assert is maintained by hand.


### The consistency checker

`tools/check.ps1` enforces all of it and exits non-zero on any finding: every citation resolves to something live, no view drops a requirement in the subsections it bears, and every asserted count matches the artifact that owns it (rewritten in place under `-Fix`). It is one tool because a line number, a membership list, and a count are the same mistake at three granularities: a derived fact restated where nothing checks it.

It also holds the sets that enumerate a *judgment*, the same mistake one granularity coarser: the crown-jewel specifications, the fail-closed refusals (R-17-030r), and the state the RoT counter keeps fresh (R-10-013a). Each closes by **conferral**: membership is asserted by each requirement that has it and collected in exactly one place, so the collection and the requirements are checked against each other rather than against a memory.

Conferral closes their disagreement, not their completeness, which no tool decides. Against completeness the checker over-approximates each judgment's vocabulary and requires every requirement it catches to confer, be collected, or be dispositioned by name, so the totality claim is an agenda regenerated on every run. Run against a fail-closed register believed complete, that agenda returned four members it did not carry.
