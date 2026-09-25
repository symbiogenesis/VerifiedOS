# Toolchain residency: the working set, the store side, and the turnaround

*The report Q26 owes. R-13-027 makes the certifying compilers, the prover, the composer and the package-construction passes admitted compartments the device runs, and R-18-004e puts them in the first release. Three quantities decide whether that is affordable on the machine R-18-004b prices, and they have three different owners: what the toolchain occupies while it runs, what its closures occupy in the authenticated store, and how long one generation takes. None is invented here. Each is stated with the act it was taken over, the instrument, the lane and the revision, and each is scored against the artifact that owns its supply or is declared unscorable with the act that owes the supply named.*

**Why this sits in `performance/` and not in `implementation/`.** Its consumers are [the inference demand](inference-demand.md)'s consumers: R-18-004b's per-class capacity comparison, the [product-gate contract](../implementation/contracts/product-gate.md)'s PL-7 and DP-3 row, and Q9's turnaround. `docs/implementation/` holds contracts and act records, what a gate does and how a result is written down; this is a measured demand read against the register's supply floors, which is what `docs/performance/` already holds, and [the inference demand](inference-demand.md) is the precedent this follows in form as well as in place.

## 1. What is measured, and what is not

Measured here:

- **The certifying compiler's peak resident bytes per translation unit**, over a size ladder and over the real units the contained fork's own runtime carries, with the growth answered by measurement rather than asserted, and with the optional optimization passes separated from the mandatory chain by running the same act with them off.
- **The prover's peak resident bytes**, per module for the per-artifact check that is the device's act and R-06-015a's declared budget, and once over a whole module set for what one kernel re-check in one invocation costs.
- **The store side**: actual bytes of the source closures and of the proof objects that exist on this machine, each named by the revision it was read at, with the deduplication R-13-008 performs credited once at each level and never twice at any.
- **The turnaround**, as a range over the stages that have an executable, with the power state and the concurrent load per row.

Not measured here, each with the reason and the act that owes it:

- **The composer and the package-construction passes**, two of the four component classes R-13-027 names. M6.3a landed the package composer and the typed graph as a statement artifact and M6.10 is open after the M8a gate, so no executable performs the act. Their working set and their store side are owed by M6.3a's lowering owner and by M6.10.
- **The device's certifying purecap compiler.** M1.2's purecap backend is open, so the compiler the device will run does not exist. The measurable arm is a *related* compiler, the contained fork configured `rv64-linux`, and section 2 names it as such: it is a CompCert of the same lineage compiled for a plain RV64 target, and no figure here is a purecap figure.
- **Vélus.** M1.10 names it among the components it would admit and [THIRD-PARTY.md](../../THIRD-PARTY.md) carries `INRIA/velus` as a contained external producer under the Inria Non-Commercial License Agreement. There is no gitlink, no local clone and nothing in the guest, so both its working set and its store side are owed in full and are not bounded here.
- **The roster size and the per-component memory extents.** Q26 asks for a roster of the size M7.1 composes; M7.1 states no size, and [the synthetic capacity corpus](../implementation/static-memory/corpus.md#the-absent-extents-by-inspection) records by inspection that the admission path's `golden_roster` names the golden model's seven components while no tracked artifact carries a memory extent against one. The size ladder of section 4 is a ladder and not a roster; it answers the growth question and stands in for no composition.
- **Energy, and any figure at a device operating point.** No energy instrument reaches this host's guest, and R-11-017's operating point does not exist, which is why section 7 states the conversion terms and refuses the conversion.

## 2. The instruments and their identity

**The certifying compiler.** `/root/build/m12b-clean-20260912-closeout/ccomp` in the guest, 14,378,056 bytes, SHA-256 `d5ab6764ba5833e49c4a76b81c46f3cc3640d178cd65c67b34310645109f1cc4`. Its build directory's own `evidence.json` records the revision it was built from as `a826d5f17bb09742940cb66f7c986c55ccfbf6de` of the contained fork, configured `sh ./configure rv64-linux -ignore-ocaml-version`, whose `Makefile.config` reads `ARCH=riscV`, `BITSIZE=64`, `MODEL=64`, `ABI=standard`. **That revision is not the fork's head**, which is `13b7ff72d486858021f0fc4fc9fbed98daf9c10f`, and the store-side reading of section 6 is taken at the head while this binary is not: the two revisions are named apart wherever both appear.

**The contained fork is read and never copied.** It is a local repository with no remote at `C:\Users\symbi\source\repos\verifiedos-cheri-compcert`, outside every checkout, under the INRIA Non-Commercial License Agreement that M1.1a's containment answers. It is not built in that tree: it carries no `Makefile.config`, no `ccomp` and no compiled proof object. Nothing of its source enters this repository, and no measurement here required that it do so: the size ladder is generated by [gen.py](toolchain-residency/gen.py), and the nine real units of section 4 were preprocessed in a guest lane directory and compiled there.

**The prover.** `rocq` 9.2.0 from the pinned switch `/root/.opam/verifiedos-rocq-9.2.0-ocaml-5.4.1`, which is the switch [tools/vos/env.py](../../tools/vos/env.py) resolves for the proof gate, with its own kernel re-checker `rocqchk` beside it in the same switch.

**The peak-resident instrument.** [peak.py](toolchain-residency/peak.py), whose predicate is `ru_maxrss` from `os.wait4` on the child that invocation forked, in kibibytes times 1024. It is deliberately not `/usr/bin/time -v`, whose figure is the running maximum over every child the timed process has waited for: a compiler driver that forks a preprocessor and an assembler reports the largest of the three under that instrument and the compiler proper under this one. Every ccomp act below is handed an already-preprocessed unit with `-S`, so the measured process forks nothing and the figure is the compiler's own.

**The store-side instruments.** Two, because the two things measured are held two ways. [store.py](toolchain-residency/store.py) walks a directory tree, sizes every regular non-symlink file by `st_size` and names it by the SHA-256 of its bytes; it is what reads the built objects in the guest. Tracked source is read instead with `git ls-tree -r -l <revision>`, sized by the blob's own length and named by its object id, which is checkout-independent and counts no build residue; a gitlink is counted as neither a file nor a byte. Both credit one object per distinct content name exactly once in the union figure, and section 6 states where that credit is taken.

**The lanes.** Host lane: Windows 11, the worktree at `9e2b56ab54745958bf2d287bad66ba2798cead5e`, which is where every tracked-byte figure was taken. Guest lane: WSL 2, kernel 6.18.33.2-microsoft-standard-WSL2, 12 cores, 16,504,463,360 bytes of guest memory and a 4,294,967,296-byte swap, where every peak-resident and wall-clock figure was taken, with every output under `/root/build/lane-q26-toolchain-20260914/q26` and nothing written into the checkout.

## 3. The machine, the power state and the contention

The host is the same Snapdragon X Elite class machine [the inference demand](inference-demand.md#4-the-machine-the-power-state-and-the-contention) records, and the two conditions it books hold here for the same reason. **Power**: the guest reported `Discharging` at `/sys/class/power_supply/*/status` at the first and last stamp of every run below, so no timed row here spans a power transition, and the state is stated once rather than per row for that reason. **Contention, which differed by run and is therefore stated per run and not once**: thirteen sibling agent lanes ran on the same twelve cores while the compiler ladder was taken, at a guest load average of 2.49 at its first stamp and 2.72 at its last, and while the proof gate of section 7 ran, when a second lane's kernel re-check was resident beside this one's over the same module set and the guest's 16.5 GB was full; the prover measurements of section 4 were taken after those lanes had largely quiesced, at a load average of 0.10 at the first stamp and 1.00 at the last.

**The byte figures are the load-bearing evidence here, and the spread this lane's load puts on one of them is measured rather than assumed.** Section 4's three repeat rows re-take the compiler's 1,024-function row, a 74 MB figure, under the same thirteen-lane load, and the whole spread is 2.5% of it. That bound is measured on that row and on no other: no repeat was taken on a multi-gigabyte prover figure, which is why the two prover rows state their own condition rather than inherit this one. Every timed figure below is a lower bound taken under a load that was neither constant nor measured, and none is offered as a characterization of this host, let alone of any other.

## 4. Quantity 1: the working set

### The certifying compiler, over a size ladder

One act per row: compile one preprocessed translation unit to assembly, `ccomp -S -o <out>.s <unit>.i`, which is the per-object act the device's certifying compiler performs and the one whose peak a declared pool (R-08-046) has to hold. The unit is [gen.py](toolchain-residency/gen.py)'s output at the stated function count: a header-free unit of equally shaped functions in a call chain, so that the only free variable across the ladder is the unit's size.

| Functions | Unit bytes | Peak resident bytes | Wall s | User s | Minor faults |
| --- | --- | --- | --- | --- | --- |
| 1 | 106 | 17,297,408 | 0.010 | 0.003 | 1,580 |
| 4 | 934 | 17,788,928 | 0.014 | 0.004 | 2,184 |
| 16 | 4,306 | 20,668,416 | 0.024 | 0.015 | 2,901 |
| 64 | 18,034 | 23,162,880 | 0.074 | 0.048 | 3,515 |
| 256 | 73,098 | 33,579,008 | 0.254 | 0.233 | 5,538 |
| 1,024 | 293,690 | 74,878,976 | 1.081 | 1.016 | 13,572 |
| 4,096 | 1,182,010 | 233,525,248 | 4.468 | 4.286 | 46,463 |

**The peak is affine in the unit's size over the four decades the ladder spans**, 106 bytes to 1,182,010. A least-squares line over the seven rows is 181.75 bytes of peak per byte of preprocessed source above an intercept of 19,307,790 bytes, and the secant from the first row to the last is 182.95 bytes per byte. **The product a port can be sized against is therefore two numbers and not one**: a fixed part of about 17 MB, which the 106-byte unit measures directly at 17,297,408 bytes, and a growing part of about 182 bytes of peak per byte of unit.

### The nine real units, which measure the fixed part independently

Nine translation units of the contained fork's own `runtime/c`, preprocessed with the preprocessor that fork's `Makefile.config` names and compiled by the same act:

| Unit | Unit bytes | Peak resident bytes | Wall s |
| --- | --- | --- | --- |
| `i64_udiv` | 1,191 | 16,494,592 | 0.010 |
| `i64_umod` | 1,203 | 16,596,992 | 0.011 |
| `i64_smod` | 1,309 | 17,567,744 | 0.014 |
| `i64_sdiv` | 1,318 | 17,457,152 | 0.011 |
| `i64_smulh` | 1,335 | 16,990,208 | 0.011 |
| `i64_umulh` | 1,441 | 17,743,872 | 0.012 |
| `i64_sar` | 1,444 | 18,411,520 | 0.016 |
| `i64_shr` | 1,451 | 17,473,536 | 0.012 |
| `i64_shl` | 1,459 | 17,289,216 | 0.011 |

Nine real units of 1.2 to 1.5 kilobytes land between 16,494,592 and 18,411,520 bytes, which brackets the ladder's own 106-byte row from both sides. **So the fixed part is a property of the compiler and not of the ladder's synthetic text.**

One further real unit compiled and is out of the table because it measures something else: `test/c/simplefib.c`, whose preprocessed form is 39,160 bytes, peaks at 21,622,784 against the ladder's fit of 26,425,120 for a unit that size. **The fit's independent variable is preprocessed bytes, and a unit that is mostly `stdio.h` declarations emits nothing for most of them**, so the 181.75 slope is an upper bound taken over code-dense text and a declaration-heavy unit costs less. A port sizing a pool from a roster's byte count should read it that way.

**Eight units did not compile, and the reason separates into two kinds that are reported rather than dropped.** `i64_udivmod.c` and `test_int64.c` fail at the host's own `stddef.h`, which uses `__typeof__` after the `-U__GNUC__` the fork's `Makefile.config` prescribes; that is the host's headers not being the device's, a property of the arm and not of the compiler. The other six, `i64_dtos`, `i64_dtou`, `i64_stod`, `i64_stof`, `i64_utod` and `i64_utof`, are refused by the backend itself with `Asmgen: scalar floating point is excluded (R-15-039)`. **That is the absence contract answering correctly**, and it is the one place in this report where the measured compiler and the platform's own register meet: the units the device would have no instruction for are the units this compiler will not emit.

### Which passes' peak grows, and which do not

The instrument reaches the process and not the pass, so this is answered by the differences between acts rather than by attribution inside one.

- **The optional optimization passes are not where the peak is.** At 1,024 functions, `-O0` peaks at 73,703,424 bytes against the default's 74,878,976, which is 1.57% lower, and `-fno-inline` at 74,649,600, which is 0.31% lower. Constant propagation, CSE, redundancy elimination, inlining and tail calls together therefore move the peak by under two percent of it.
- **The growth is in the mandatory representation chain.** What is left when the optional passes are off is the elaboration and lowering sequence the compiler's own `-timings` enumerates: parsing, elaboration, emulations, CompCert C, Clight, simplification of locals, C#minor, Cminor, instruction selection, RTL, renumbering, unused globals, register allocation, branch tunneling, CFG linearization, label cleanup, Mach and Asm. Each of those representations is built whole for the whole unit before the next is, which is what an affine peak in the unit's size looks like from outside.
- **The time profile, which is not the memory profile, says register allocation is the largest pass.** At 1,024 functions `-timings` reports 0.26 s of a 1.04 s total in register allocation, then 0.17 s parsing, 0.09 s CSE, 0.08 s redundancy elimination; at 4,096 functions, 1.02 s of 4.35 s in register allocation, then 0.71 s parsing, 0.38 s CSE. **This is quoted as a time profile and is not evidence about any pass's peak.**
- **The per-pass peak is not produced here and is M1.10's.** That item's own text says so in as many words: the port owns a resumable pass structure and *a recorded peak per pass* rather than a measurement of a host run. This report yields one peak per process per translation unit, and it synthesizes no per-pass figure from it.

### Repeatability of the byte figure under this lane's load

Three consecutive invocations of the 1,024-function row, taken after the ladder and under the same thirteen-lane load: 73,195,520, 73,449,472 and 73,035,776 bytes, against 74,878,976 in the ladder itself. The whole spread is 2.5% of the figure, which is the ground for treating the byte figures as the load-bearing evidence and the timed figures as a range.

### The prover, and which of its two acts the device performs

**The two acts are not the same act and the register separates them.** R-13-028 says deep proofs are not per-device: Tier-0 functional refinement and non-interference are validated by the CIC kernel *at release time* over the base-image TCB, while a composition re-emits every object in the package closure outside the base image with its derivation and its correspondence theorem, and R-13-027 makes the on-device act *CIC-check the artifact-local source-correspondence theorem*. **So the per-artifact check is the act the device performs and the act R-06-015a's declared working-set budget covers**, that entry budgeting every proof the CIC kernel checks on the install path. **What R-13-028 separates is subject matter and not invocation shape**: its Accept puts on the install path *the CIC correspondence check over the closure the composition re-lowered, which is the roster's package closure*, so an install does re-check a whole closure, and the one-invocation shape decides nothing about which act is which. Both are measured; each is labelled for the closure it was taken over.

**Per-module check, which is the device's act.** `rocq c -q -Q proofs "" <module>.v`, one invocation per module, over this repository's 27 tracked proof modules at `9e2b56ab`, in dependency order, each peak taken on the child that invocation forked. Ordered by peak:

| Module | Source bytes | `.vo` bytes | Peak resident bytes | Wall s |
| --- | --- | --- | --- | --- |
| `MemoryPlan` | 244,656 | 414,203 | 725,676,032 | 84.58 |
| `StaticMemoryLaminar` | 51,086 | 205,875 | 483,774,464 | 5.83 |
| `StaticMemoryService` | 35,984 | 76,813 | 473,268,224 | 4.28 |
| `RomVerifier` | 67,748 | 362,689 | 467,439,616 | 2.29 |
| `AesGcm` | 108,487 | 111,249 | 456,216,576 | 23.74 |
| `MemoryPlannerResources` | 8,957 | 29,319 | 434,802,688 | 1.48 |
| `MemoryPlannerContracts` | 14,777 | 49,978 | 429,146,112 | 1.34 |
| `MemoryPlannerCertificates` | 9,405 | 20,562 | 414,531,584 | 0.64 |
| `CopyRingService` | 170,126 | 239,027 | 396,935,168 | 35.11 |
| `Keccak` | 91,978 | 118,301 | 377,663,488 | 4.63 |
| `Sha256` | 92,013 | 175,075 | 368,427,008 | 16.72 |
| `AdmissionPath` | 313,611 | 426,811 | 354,328,576 | 2.00 |
| `HmacDrbg` | 71,766 | 86,075 | 352,681,984 | 39.03 |
| `RotFirmware` | 232,232 | 265,711 | 342,708,224 | 1.02 |
| `KeyspaceDomains` | 198,782 | 230,489 | 340,463,616 | 1.08 |
| `JournalIndex` | 196,589 | 239,965 | 338,604,032 | 1.23 |
| `HandlerGraph` | 223,150 | 257,143 | 337,817,600 | 1.11 |
| `EndpointIPC` | 207,997 | 229,779 | 335,106,048 | 0.81 |
| `DischargeSequence` | 103,640 | 146,186 | 330,764,288 | 0.60 |
| `MModeFirmware` | 81,785 | 105,213 | 326,049,792 | 0.58 |
| `RingContract` | 26,690 | 90,311 | 325,197,824 | 0.49 |
| `CyclicExecutive` | 49,094 | 81,378 | 324,300,800 | 0.41 |
| `SupervisionTree` | 89,662 | 108,500 | 323,952,640 | 0.50 |
| `CredentialHandles` | 26,774 | 69,730 | 321,679,360 | 0.42 |
| `PartitionContext` | 48,634 | 49,653 | 283,840,512 | 0.31 |
| `ApexTheorem` | 28,189 | 37,300 | 125,927,424 | 0.13 |
| `SeamWitnesses` | 12,539 | 9,982 | 104,275,968 | 0.11 |

**The prover's peak does not track the input's size, and that is the opposite of the compiler's answer.** Source sizes span a factor of 35 across these 27 modules, 8,957 bytes to 313,611. The peaks of 25 of them span a factor of 2.6, 283,840,512 to 725,676,032, with no ordering by source size inside that band: the largest source, `AdmissionPath`, peaks below eleven smaller ones, and the smallest, `MemoryPlannerResources`, peaks above it. Only the two lightest modules fall out of the band, `SeamWitnesses` at 104,275,968 and `ApexTheorem` at 125,927,424. **What drives the peak inside the band is not identified here**: the instrument reaches the process and not the cause, and no property this report measured, not the source size, not the `.vo` size, not the constant count the gate enumerates, orders the band. Naming it is M1.10's, the item that owns the recorded peak per pass.

**So the two components answer the growth question in opposite directions**, which is the part of quantity 1 the item asks for by name. The compiler's peak is affine in the unit's size, so it grows with a roster and a port can trade it against how much a unit holds. The prover's is a band between 0.28 and 0.73 gigabytes for 25 of this corpus's 27 modules, the two lightest sitting below it at 0.10 and 0.13, and inside the band it is independent of the module's byte count, so it does not grow with a roster and cannot be traded that way; what a roster changes is how many times it is paid. **A pool sized from a roster's byte count would be sized correctly for the first and wrongly for the second.**

**Whole-set re-check, over a corpus that is neither of R-13-028's two closures.** `rocqchk -silent -Q proofs "" <all 27 modules>` in one invocation: **peak 8,836,591,616 bytes**, 750.108 s wall, exit 0. The set is this repository's design corpus, which is neither the base-image TCB R-13-028 validates at release time nor a roster's package closure an install re-checks, and the row is reported for what one kernel check over 27 modules of this size costs rather than as either act.

**Conditions for these two rows.** `Discharging` at both stamps; guest load average 0.10 at the first stamp and 1.00 at the last, the sibling lanes having largely quiesced by then, which is a looser condition than the compiler ladder's 2.49 to 2.72 and is stated per act rather than once. An earlier run of the same re-check, taken while a second lane's re-check was resident beside it and the guest's 16.5 GB was full, is not quoted here in any form: what was observed of it came from a current-resident sampler this report declares no predicate for, and no figure of it enters this report or any record beside it. **The 8,836,591,616-byte figure above was taken with that second re-check gone, and it is the only whole-set figure this report carries.**

## 5. Quantity 1 scored, twice, with neither reading chosen here

### What the supply floors are

R-18-004b's first-class comparison is *the composed roster's resident bytes on the first class, summed over R-15-247s's first list as the whole-program static memory plan places them (R-08-010, R-08-012a), at most (1 − τ) of that class's usable capacity, τ being its own declared exclusivity fraction, and that capacity being at least the pessimistic end of R-15-173a's ungraded-branch budget stated as payload*, with the same entry's separate exclusivity clause putting each class's declared τ at most 20%. R-15-173a puts that budget at order 0.5 to 1 GB and states why it stops at one, so **the first-class payload a demand is scored against is 0.4 GB at the minimum declarable capacity and the maximum exclusivity fraction, and 0.8 GB at that budget's optimistic end**. The second class's floor on the same convention is [the inference demand](inference-demand.md#8-the-target-traffic-budget)'s 3.2 GB and is cited from there rather than recomputed.

**Which class the toolchain's working set sits on is decided by no artifact, and the first class is the reading taken here.** R-15-247s's boundary is *latency-criticality*, and that entry places by criterion rather than by membership: *ownership is no part of a latency criterion, so the boundary places application payloads by criterion and not by name*, and *a term of that charge appearing in neither list nor in this clause is a placement nobody has taken*. Neither list names a compiler's or a proof checker's working set. By form the first list is where they belong, since it opens with the scalar working set and names the servers' scalar working sets explicitly, while the second holds bulk by volume, framebuffers, extents, interpreter arenas, media buffers, cold code and model weights, and a compiler's or a checker's live data is none of those. By the stated criterion they do not belong there, a proof check not being latency-critical, which is the concession arm 2 of section 8 makes explicit. Form and criterion therefore point opposite ways and neither settles it. **The placement is the whole-program memory plan's (R-08-012a)**, exactly as [the inference demand](inference-demand.md#8-the-target-traffic-budget) records the KV cache's placement to be, and **every figure scored in this section is conditional on the plan putting the toolchain on the first class.** Section 8 says what the other placement costs, and arm 2 there is the other side of this same undecided question rather than a widening of anything.

**A host high-water mark is an upper bound on a declared pool and not the pool**, and the direction of that bound is worth one clause: a garbage-collected runtime's peak resident set exceeds its live bytes by whatever the collector had not yet returned, but those pages were held, and R-08-045 charges every physical byte to the signed composition while R-08-046 fixes each pool's capacity, both stated over resident bytes and not over live bytes. So the gap between peak and live bounds what a *different* collector configuration or a differently represented port would need, and not what this implementation of the act needs; deflating any multiple below by an unmeasured live-to-peak ratio is not a move the register admits. That is the sense in which section 4's numbers size a declaration rather than enter a comparison.

### The scoring separation the register fixes, and the layout question it leaves open

**Charging R-18-004a's floor zero in the composition mode is the register's own reading.** R-13-027a's Accept states it: *the ordinary mode's budgets are what they were without the toolchain, so R-18-004a's floor is scored in the ordinary mode and a configuration that met that floor only by borrowing this mode's grants fails R-18-004a rather than this entry*. R-18-004e's Accept states it again from the other side: it is *deliberately not a ninth member of R-18-004a's floor*, because *a composition runs in R-13-027a's composition mode*, so *what this entry obliges is that the mode exists and both acts complete inside it, while R-18-004a stays scored in the ordinary mode with its budgets untouched*.

**Taking R-18-004b's per-class capacity comparison per mode is this item's direction and not a second register reading.** Neither Accept above indexes that comparison by mode, and R-18-004b states its first-class demand side once, over the composed roster as the whole-program static memory plan places it, with no mode index. Q26's own cell supplies the index, directing that the composition mode's occupancy is scored against R-18-004b's per-class capacity in that mode and not in the ordinary one. **Reading A below is the two together**, the register's zero-charging and the item's per-mode comparison, and neither half is a model invented here.

**Modes touch the plan in three places.** R-13-027a fixes the composition mode's *slot table and per-mode gating-domain occupancy (R-08-012a, R-08-012e)* at composition; R-08-012e's fourth lexicographic term emits the per-mode gating-domain occupancy map for the power vector; and R-11-018 makes each global mode schedule an independently admission-proved schedule. **Whether a mode's slot table is a capacity object is not settled by the register's own usage**, whose other slot tables are the time-domain tables of R-11-017a and of R-15-228d, cited at R-17-003d, and which calls the memory object the slot plan (R-08-011, R-13-028); section 7 reads the same R-13-027a clause for the mode's own slot share, which is a time quantity. The layout question below is open under either reading and is not decided by this one.

**What no entry decides is whether one physical layout must serve both modes.** A mode's own slot table being fixed at composition does not say whether the composition mode's slots are the ordinary mode's reused or slots beside them. Sharing one slot between a composition-mode-only compartment and an ordinary-mode object is admitted by R-08-014 only where the two regions' R-08-011 live ranges do not intersect, and by R-08-018a only where the admitted frame or the region structure proves the non-co-occurrence and never from assumed correlation; **no entry says a global mode boundary is such a proof**, and R-08-020 leaves nothing to relocate at runtime to reclaim a slot the other mode holds. So the register separates the two modes' **scoring** and leaves their **layout** relation to the whole-program static memory plan (R-08-012a), which this tree does not carry.

**That open relation is why a second reading is worth scoring, and this tree's own research states its arithmetic.** [The mode families](../implementation/static-memory/modes.md), whose own header declares it non-normative host research that is no admission input and changes no requirement, record that the per-mode charge is the maximum over modes of that mode's optimal span and is *a lower bound no single layout can beat rather than a cost a single layout attains*, that the baseline carries the witness in which one layout across modes costs more than each mode's own peak, and that two modes solved independently do not give one layout, a global-mode relation being a separate input and a separate proof obligation. **So the per-mode scoring is a lower bound on what the first class must physically hold, and a one-layout figure is an upper bound on it**; which the plan will produce is owed by that plan and by nothing here. Both are scored below, and the verdict does not turn on which.

### The two readings

Under **reading A, the per-mode scoring of section 5**, the composition mode is scored alone and the ordinary mode's roster is charged zero. What the first class must then hold is at least the composition mode's own peak, which is at least the largest single toolchain activation resident at once in that mode. Every multiple in the table is a reading-A multiple, and reading A is a lower bound on the class's physical charge.

Under **reading B, one layout across modes**, the same slots must also hold whatever the ordinary mode places there, because no runtime relocation exists to reclaim them; the toolchain's demand is then *added* to R-18-004a's eight members' first-class demand rather than substituted for it. R-18-004a's own first-class demand is measured by nothing in this tree, so reading B is scored as an inequality and not as a number.

Both readings are taken in decimal gigabytes, on the ground [the inference demand](inference-demand.md#8-the-target-traffic-budget) states for its own comparison: R-18-004b fixes no base for its unit, and decimal is the conservative choice, a binary floor being the larger number.

| Act, one activation | Peak resident bytes | Reading A against 0.4 GB | Reading A against 0.8 GB |
| --- | --- | --- | --- |
| Compiler, one 1.2 kB real unit | 16,494,592 | 0.04 | 0.02 |
| Compiler, the 293,690-byte unit | 74,878,976 | 0.19 | 0.09 |
| Compiler, the 1,182,010-byte unit | 233,525,248 | 0.58 | 0.29 |
| Prover, the lightest module | 104,275,968 | 0.26 | 0.13 |
| Prover, the median of the 27 modules | 342,708,224 | 0.86 | 0.43 |
| Prover, the heaviest module | 725,676,032 | **1.81** | 0.91 |
| Prover, the whole-set re-check in one invocation | 8,836,591,616 | **22.09** | **11.05** |

**Under reading A, the heaviest single proof check this repository contains already fails the pessimistic floor on its own**, at 1.81 of it, and reaches 0.91 of the optimistic one, and that is one activation of one component of a four-component toolchain with no roster, no composer, no package-construction passes and no Vélus beside it. **That is reported as a demand and not as a reason to move a floor.**

Reading B adds to every figure above whatever R-18-004a's eight members place in the same first-class slots, because R-08-020 leaves nothing to relocate at runtime and R-15-247 admits no promotion between classes. **That addend is measured by no artifact in this tree**, so reading B is an inequality: every row's multiple under reading B is strictly greater than its reading A multiple, and the row that fails under A fails under B.

**One further charge is undecided and is not counted twice here.** Whether the compiler's declared pool and the prover's declared pool are two charges or one turns on R-08-018a, which colours a compartment's pools against each other in one interference structure and admits non-co-occurrence only where the admitted frame or the region structure proves it, and on R-08-014, under which two regions whose live ranges do not intersect may share one slot. Nothing states that a toolchain's compiler phase and its proof phase have disjoint live ranges. The rows above are therefore per activation, and a composition that ran two at once would charge their sum.

## 6. Quantity 2: the store side

R-13-027 obliges the device to hold the source closure every generation it runs it can also produce, and R-13-010c keeps source closures, derivations and proof artifacts out of execution SRAM: they are resident in the authenticated store and consumed at admission rather than at run time. **So this quantity is bytes of storage and is not charged against either memory class.** R-13-027's own text makes the proof objects closure members by putting the source closure and the artifact-local correspondence theorem on the same admission path, and R-13-028 re-emits every object outside the base image with its derivation and its correspondence theorem per roster, so a proof object is counted here as a closure member and never as a separate category.

**What exists to be measured, and what does not.** There is no base image, so the base image's own source closure is absent and is owed by M6.10 and by R-13-026's reproducible object. What exists is one toolchain component's source closure, that component's proof objects, the prover's own installation, and this repository's tracked corpus, and each is labelled for what it is.

| Closure | What it is | Revision | Files | Bytes | Unique bytes |
| --- | --- | --- | --- | --- | --- |
| `compiler-source` | the certifying compiler's own source closure, as tracked | `13b7ff7` | 1,050 | 16,185,647 | 16,112,077 |
| `compiler-proof-objects` | that compiler's compiled proof objects | `a826d5f1` | 204 | 120,335,937 | 120,335,937 |
| `compiler-native-objects` | that compiler's compiled native objects and interfaces | `a826d5f1` | 699 | 18,509,818 | 18,509,818 |
| `prover-runtime` | the prover's own installed runtime libraries | rocq-core 9.2.0 | 3,666 | 395,687,841 | 395,682,751 |
| `prover-stdlib` | the prover's compiled standard library | rocq-core 9.2.0 | 2,328 | 97,986,966 | 97,986,966 |
| `verifiedos-tracked` | this repository's tracked corpus | `9e2b56ab` | 1,233 | 25,358,105 | 25,249,605 |
| `verifiedos-proof-objects` | this repository's compiled proof objects | `9e2b56ab` | 27 | 4,235,970 | 4,235,970 |

**Total unique bytes measured: 678,113,124.** Two figures beside it, each with its own predicate and neither summed into it. The prover switch as a whole, by `du -sb` over `/root/.opam/verifiedos-rocq-9.2.0-ocaml-5.4.1`, is 1,035,251,658 bytes, of which 264,264,283 is its `bin/`; that tree is a build environment, carrying an OCaml toolchain the device would not hold, so its parts are reported and the `prover-runtime` and `prover-stdlib` rows are what enters the total. And **204 compiled proof objects at `a826d5f1` stand against that same revision's 301 tracked `.v` files**, the head `13b7ff7` the `compiler-source` row is read at carrying 305 of them, the configured target compiling one architecture's subset rather than every architecture that tree carries, so a device holding the purecap target's objects would hold a different count and not this one.

**The `verifiedos-proof-objects` row and section 4's `.vo bytes` column are two acts and not one.** The row sizes the 27 objects the proof gate emitted into its own build root, 4,235,970 bytes; the column sizes the 27 this report's own per-module `rocq c` invocations emitted into the prover directory of the guest lane, 4,237,317 bytes. Each record names the root its act wrote to, [store.json](toolchain-residency/store.json) per row and [prover.json](toolchain-residency/prover.json) in each invocation's argv, the difference is 1,347 bytes, and neither figure is corrected against the other or summed with it.

**What the total is not.** It is the closure of *one* toolchain component plus a prover installation plus this repository's design corpus. **R-13-027's obligation is over the base image's source closure and the toolchain's, and the base image does not exist**, so the largest term of the real figure is absent and is owed by M6.10 and by R-13-026's reproducible object. `verifiedos-tracked` is this repository's design corpus and is in the table because it is measurable and because a reader would otherwise assume it stood for the base image; **it does not**, and its 22 gitlinks carry no bytes here, so no upstream's contents are inside any figure above.

**Where the deduplication is credited, and which credits were computed rather than argued.** R-13-008 makes a transfer a set difference: a content-addressed store holds one object per distinct content name. The credit is taken at three levels and only the first two of them are computed. Inside a row it is computed, which is what each row's unique figure is. Across the rows one instrument measured it is computed for the two `git ls-tree` closures, which were read together: their union is 41,361,682 bytes over 1,929 distinct object ids against the rows' own 752 and 1,177, so no object repeats across them. It is argued rather than computed across the three `store.py` runs, whose own unions are each exact and whose roots are disjoint trees, giving 636,751,442 bytes. **Across the two instruments it is argued and not computed**, on the ground [store.json](toolchain-residency/store.json) states: the instruments name objects by different digests, and the kinds they measure are disjoint, source blobs of two repositories against suffix-filtered built objects of a compiler and of a prover. **The total is those two instrument figures added**, and because no credit was found or claimed above the row it equals the seven rows' unique bytes summed, which is what a reader adding the column will find. A reader who wants the cross-instrument overlap computed rather than argued should read that as owed.

**The comparison this report cannot make.** Quantity 2 is to be scored against a declared device capacity and **no artifact declares one**. R-18-004b prices two memory classes, bandwidth, area, yield and unit cost, and names no storage capacity; the product-gate contract's declared parameters are DP-1 power, DP-2 temperature, DP-3 turnaround, DP-4 and DP-5 inference quality, with no storage row, and every one of them is `proposed` and binds nothing. The demand side above is measured; **the supply side is owed by a register act or by a product act, and the comparison is therefore stated as owed rather than made.**

## 7. Quantity 3: the turnaround

**The act R-18-004e names is a generation composed, signed, admitted and booted with nothing reachable, and no part of it runs anywhere.** What exists to be timed are the stages that have an executable, which is compilation and proof; signing, admission and boot have none, and the composer and the package-construction passes have none. The range below is over what runs and says so. **It is not a generation's turnaround and is not offered as one.**

| Stage | Act | Instrument | Power | Guest load, start and end | Wall s |
| --- | --- | --- | --- | --- | --- |
| Compile, one small unit | `ccomp -S` over a 1,191-byte unit | `peak.py` | Discharging | 2.49 to 2.72 | 0.010 |
| Compile, one large unit | `ccomp -S` over a 1,182,010-byte unit | `peak.py` | Discharging | 2.49 to 2.72 | 4.468 |
| Proof, one module | `rocq c` over the lightest of 27 modules | `peak.py` | Discharging | 0.10 to 1.00 | 0.11 |
| Proof, one module | `rocq c` over the heaviest of 27 modules | `peak.py` | Discharging | 0.10 to 1.00 | 84.58 |
| Proof, 27 modules | `rocq c` over the whole set, serially | `peak.py`, summed | Discharging | 0.10 to 1.00 | 230.483 |
| Kernel re-check, 27 modules | `rocqchk` over the whole set, one invocation | `peak.py` | Discharging | 0.10 to 1.00 | 750.108 |
| The whole proof gate | `python tools/run.py proofs` | the command's own wall clock | Discharging | thirteen sibling lanes, one of them a second proof gate over the same set | 1,003.394 |

**Two wall clocks measure the 27-module row and the table carries the instrument's.** Summing the 27 per-invocation figures `peak.py` recorded gives 230.483 s, which is the row above. The driver's own monotonic clock around the same 27 invocations reads 231.12 s, carrying each invocation's interpreter start and the driver's own bookkeeping beside the prover's work; [prover.json](toolchain-residency/prover.json) records both under names that say which is which, and the 0.64 s between them is that overhead and nothing the prover spent.

**The range, then, is 0.01 s for one small compilation and 1,003 s for one gate run over 27 proof modules, on a host, at a contention that differed by stage and is stated per row.** One figure beside them, recorded by a build rather than by this report and quoted with its own predicate: the guest build directory's `evidence.json` records that same fork's `make -j6 proof` at 308.501 s and its `make extraction` at 8.592 s at revision `a826d5f1`, which is what building the compiler itself cost on this machine once.

**Nothing here scales.** The largest single stage, the whole-set re-check at 750 s, is one kernel check over a corpus no roster fixes; the device's own per-artifact check is the 0.11 s to 84.58 s column, over modules whose count and content a roster would fix and no roster does.

**The ratio a device figure would need, stated term by term and not applied.** Converting any wall-clock figure above into a device figure needs, in order: R-11-017's selected operating point and slot share, which does not exist; R-17-041's latency magnitudes, which do not exist; the composition mode's own slot share for the toolchain compartments, which R-13-027a makes a composition-time constant and no composition has declared; and the step budget R-13-027a bounds one activation's work by, which makes a build many bounded activations rather than one task, so that a device turnaround is a count of activations times a period and not a scaled host second. **Not one of the four terms has a value, so the ratio has no value and none is applied here.** The product-gate contract's own PG-3 refuses a verdict taken this way and R-18-004c states the same rule from the register's side; a figure in `host_elapsed` stays in `host_elapsed`.

**Read against DP-3, with DP-3's own predicate quoted.** DP-3 is *15 min from the device naming a roster to the new generation running at the rung it left, over M-ii's declared 802.11 rate*, and PL-7 reads it the same way. **This act fetches nothing**, being the offline local composition R-18-004e obliges, so DP-3's predicate does not hold over it: PL-8 is the row R-13-027 and R-18-004e actually feed, and PL-8 carries no timed condition and says the turnaround is PL-7's. R-18-004e's own acceptance states no wall-clock threshold. **So there is no device-side ceiling this quantity fails or meets**, and that absence is a named gap rather than a pass.

## 8. The verdict

**Does R-18-004e close on credible resources? Not on the resources R-18-004b declares as floors.** The single heaviest proof check this repository contains peaks at 725,676,032 bytes, which is 1.81 of the first-class payload floor at the pessimistic end of R-15-173a's ungraded-branch budget and 0.91 of it at the optimistic end, and the median of the 27 is 0.86 and 0.43 of the same two. That is one activation of one of the four component classes R-13-027 names, measured on a host, with no roster, no composer, no package-construction passes and no Vélus beside it, and with R-18-004a's own eight members charged nothing. **The conclusion does not depend on which of the two readings of section 5 is taken**, because reading B only adds.

**Which class carries the shortfall is undecided, and the shortfall survives either answer.** Section 5 states why no artifact places a compiler's or a prover's working set: R-15-247s places by latency-criticality, neither list names them, and the placement is R-08-012a's. On the first class, which is where this report scores, the heaviest activation is at 1.81 of a payload floor whose budget stops at one gigabyte for the reason R-15-173a states, that the whole logic tier needs the rest of the die. On the second class it is 0.23 of the 3.2 GB floor, which does not fit either, because that floor is already at 0.88 to 1.06 for R-18-004a(vii)'s own three-billion-parameter four-bit model alone before any toolchain arrives. **So what the placement decides is which class fails and not whether one does.**

**Which of the three is binding: the working set, and inside it the prover.** The store side is 678,113,124 measured bytes with its largest term absent, against a capacity nobody has declared, so it cannot bind until that declaration exists and it is not close to any plausible storage figure in any case. The turnaround is a host range with no device-side ceiling to fail, DP-3's predicate not holding over an act that fetches nothing and PL-8 carrying no timed condition. **The working set binds, and the compiler is not what binds it**: the compiler's peak is affine and modest, 233,525,248 bytes on a 1.18-megabyte unit, and a port can trade it against unit size because it grows with unit size. The prover's does not track size, so it cannot be traded that way, and its band starts at 283,840,512 bytes for the lightest module of this corpus outside the two smallest, which is 0.71 of the pessimistic floor before any roster exists.

**What would have to move, as arms for the product's owner, none taken here.** Each is stated with what it forfeits, and **none of them is a silent widening of the composition mode**, which R-13-027a's Accept already forecloses: a configuration that met R-18-004a's floor only by borrowing this mode's grants fails R-18-004a rather than R-13-027a.

1. **Raise the first class.** R-15-173a's budget stops at one gigabyte because at two the whole logic tier has nothing left at the pessimistic end of R-15-170's density band, which is the fit R-18-004b demands at both ends. Raising it forfeits that fit, and it is a register act on R-15-173a and R-18-004b together, not a composition's choice.
2. **Place the toolchain's working set on the second class.** R-15-247s's boundary is latency-criticality, and a proof check is not latency-critical, so this arm is arguable on the register's own criterion rather than against it, and it is the other side of the undecided placement section 5 states rather than an amendment to anything. It forfeits second-class payload against R-18-004a(vii)'s resident model, which [the inference demand](inference-demand.md#8-the-target-traffic-budget) scores at 0.88 of the same 3.2 GB floor under a `q8_0` cache and 1.06 under an f16 one, so the two demands do not both fit there either: the heaviest prover activation is 0.23 of that floor, which carries the `q8_0` reading to 1.11 and the f16 reading to 1.29. **Taking the arm as settled rather than as arguable would be a register act on R-15-247s's second list**, which today names neither a compiler's nor a prover's working set.
3. **Shrink the act rather than the machine.** R-13-027a already bounds one activation's work by a declared step budget and makes a build many bounded activations; R-06-015a already makes the working set a declared budget whose exhaustion ends the install unadmitted. What neither states is that a proof check is *resumable* across activations, and a CIC kernel check that cannot be suspended and resumed is one activation whatever the step budget says. **This arm is M1.10's**, whose own text already owns the resumable pass structure and the recorded peak per pass, and it is the only arm that does not move a floor.
4. **Ship a smaller first release.** R-18-004e puts the whole toolchain in the first release; a release carrying the checkers and not the prover, or carrying the prover for a bounded artifact class, is a different product. **That is Q10's arm**, where R-18-004a's fixed-capacity secure appliance is already weighed, and it forfeits the local autonomy R-13-027 states.

**What this verdict is not.** It is not a measurement of the device's compiler, which does not exist; not a measurement of a roster, which does not exist; and not a per-pass figure, which M1.10 owns. It is a demand, taken on a host, at the revisions named, against supply floors the register states. **Its one load-bearing claim is that the demand exceeds the supply by a margin no measurement error at this size closes**, the repeatability spread of section 4 being 2.5% against a 1.81 multiple, and that claim survives the two questions this report leaves open, the class the plan places the toolchain on and the layout relation between the two modes, because it fails on either answer to each.

### Research leads for bounded resident passes

M1.10's unfinished bounded-activation and pool proofs, together with the M6.10
producer joins, are the consumers of the following
[survey leads](../background/open-math-conjectures.md). These are prospective
comparisons, not new measurements or savings credited to the tables above.
Select a real pass and its input/output relation before developing a candidate.
The [proof-production handoff](../assurance/proof-assistance.md#research-handoff-for-future-proof-producers)
owns the distinct proof-search and certificate-cost questions.

| Lead | Missing implementation/proof bridge and useful comparison |
| --- | --- |
| [Parallel matching and explicit-tree planning](../background/open-math-conjectures.md#p-versus-uniform-nc) | Reduce a concrete assignment pass to the stated matching/matroid problem with its weight bounds and field representation, or expose the actual expression tree. Prove returned assignments legal and the transformed pass equivalent. Compare against the sequential baseline with finite processor, memory and communication budgets. The general P/NC question and harder succinct representations remain separate. |
| [Directed reachability](../background/open-math-conjectures.md#l-versus-nl-directed-reachability-in-logarithmic-workspace) | Preserve the explicit graph and reachability meaning, counting read-only graph storage and input accesses as well as writable workspace. Exercise cycles, unreachable vertices and the largest admitted graph. An O(log n) clean-space target supplies neither the missing classical algorithm nor its activation bound. |
| [Square-root-space simulation](../background/open-math-conjectures.md#square-root-space-simulation-and-circuit-evaluation) | A chosen circuit/tree evaluator needs a simulation and output-equivalence proof, recomputation counts, intermediate representation sizes and resumable polling bounds. Compare total memory and turnaround; the Turing-machine theorem is not an arbitrary-RAM pass rewrite. The withdrawn O(sqrt(t)) claim supplies no bound. |
| [Catalytic graph, sequence and streaming algorithms](../background/open-math-conjectures.md#catalytic-graph-and-sequence-algorithms) | Inside one authorized quiescent region, prove both the result and exact restoration of the original payload, tags, initialization and typed invariants. State supported interruptions and restoration behavior. Charge input replay, catalyst capacity and all restoration work; test arbitrary catalyst contents and interruption points. The multi-pass, passive-output and characteristic restrictions must match the chosen algorithm. The withdrawn almost-logarithmic-total-space claim is unusable. |

For catalytic candidates the [computational model](../background/open-math-conjectures.md#the-power-of-catalytic-memory)
does not authorize borrowing another compartment's memory or restore state after
a fault by itself. For every candidate, a lower host peak is exploratory evidence;
M1.10 still owes bounded target activations, declared-pool exhaustion and the
accepted artifact. An unavailable pass or missing restoration/refinement theorem
leaves the candidate unevaluated and the existing demand unchanged.

## 9. The reproducible invocation

Every command ran in the guest lane at `/root/build/lane-q26-toolchain-20260914/q26`, with `$CC` the ccomp binary section 2 identifies, `$ROCQ` and `$ROCQCHK` the pinned switch's own binaries it identifies beside them, and `$F` the contained fork's working tree; the host-side tracked-byte reading ran on the host at the worktree. No output was written into the checkout.

```console
$ python3 gen.py <n> > c/gen-<n>.c && cp c/gen-<n>.c i/gen-<n>.i
$ python3 peak.py ccomp-S-gen-<n> -- $CC -S -o asm/gen-<n>.s i/gen-<n>.i
$ python3 peak.py ccomp-S-O0-gen-1024 -- $CC -O0 -S -o asm/gen-1024-O0.s i/gen-1024.i
$ python3 peak.py ccomp-S-fno-inline-gen-1024 -- $CC -fno-inline -S -o asm/gen-1024-ni.s i/gen-1024.i
$ gcc -U__GNUC__ -nostdinc -I $F/runtime -E $F/runtime/c/<u>.c -o i/rt-<u>.i
$ python3 peak.py ccomp-S-runtime-<u> -- $CC -S -o asm/rt-<u>.s i/rt-<u>.i
$ $CC -timings -S -o /dev/null i/gen-<n>.i
$ python3 peak.py rocq-c-<module> -- $ROCQ c -q -Q proofs "" prover/proofs/<module>.v
$ python3 peak.py rocqchk-all -- $ROCQCHK -silent -Q proofs "" <the 27 modules>
$ python3 store.py "<name>=<root>:<suffixes>"
$ git ls-tree -r -l <revision>          # the tracked-source predicate of section 2
$ python tools/run.py proofs            # the gate row of section 7, and no row of section 4
```

A size ladder and a peak reading are one experiment, so none of it enters [tools/run.py](../../tools/run.py): the plan's rule is that an experiment enters the runner when it becomes recurring work.

## 10. The files

[toolchain-residency/](toolchain-residency/) carries the machine-readable output and the two instruments, every file ASCII and LF:

- [peak.py](toolchain-residency/peak.py), the peak-resident instrument, and [store.py](toolchain-residency/store.py), the directory-tree store instrument, each stating its own predicate in its docstring.
- [gen.py](toolchain-residency/gen.py), which emits the size ladder's units deterministically.
- [manifest.json](toolchain-residency/manifest.json), the instruments, the binaries and their digests, the lanes, the machine and the conditions.
- [ccomp.json](toolchain-residency/ccomp.json), every compiler row with its unit size and the fit over the ladder.
- [prover.json](toolchain-residency/prover.json), the 27 per-module rows, the whole-set re-check row and the two wall clocks over those 27 invocations. The proof gate's own 1,003.394 s of section 7 is not in it: that figure stands in section 7's table and in no machine-readable record here.
- [store.json](toolchain-residency/store.json), every closure measured, per-row and union, with the predicate each was taken under.
