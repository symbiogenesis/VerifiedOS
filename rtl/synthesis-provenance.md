# The Synthesis-Configuration Provenance Record

*What binds each claimed absence to a build rather than to a reading. R-15-103 requires the imported-core half of [the absence contract](../docs/absence-contract.md) to be discharged by a state enumeration over the elaborated netlist **plus** the synthesis-configuration provenance, and this is that second half: one row per absence, naming the parameters whose values remove it, or stating that no parameter does and why.*

> **Precedence.** [The absence contract](../docs/absence-contract.md) is the register of absences and this record says how each is taken in one build. Where the two disagree the contract wins and this record is defective. Rule K-76 holds the two against each other in both directions, and holds every parameter named here against the configuration package that states it.

## 1. How to read this

Every row names an absence by the contract's own identifier. The **Binding** column is one of two things and never a third:

- a comma-separated list of `` `Name = value` `` settings, each a field of [the curated configuration package](vos_c_class_config_pkg.sv), whose values are what remove the structure; or
- `n/a`, followed by the ground on which no parameter reaches it.

A row whose binding is neither is a finding, because an absence bound to nothing is exactly the state R-15-103 exists to prevent: a claim that reads as discharged and is discharged by no build.

**`n/a` is not a lesser answer, and three different things wear it.** A structure the imported core never had needs no parameter and gets one kind of ground. A structure the core has and no parameter removes gets another, and that one is authoring work rather than configuration. A structure that is not in this netlist at all, sitting in the interconnect or the memory controller instead, gets a third. The column says which.

**Every value here is one this configuration sets, and every one of them removes.** Nothing in this record adds hardware to the stock core, which is the property [the profile](../docs/isa-profile.md) and the contract share and the reason the record can be read as a list of deletions.

## 2. The absences the contract enumerates

| Absence | Structure | Binding | Elaborated result |
| --- | --- | --- | --- |
| A-01 | Speculative execution / transient state | n/a: the imported core issues, executes and commits in order and updates no architectural state ahead of commit, so there is no parameter because there is no structure. What it does have is a fetch-ahead buffer and a redirect on a resolved taken branch, which §5's table-freeness rule places and §6's fourth class holds | no checkpoint, rollback or squash module elaborates |
| A-02 | Reorder buffer | n/a: in-order issue is the imported core's shape rather than a setting on it | no ROB module elaborates. The scoreboard is not one and its §6 class is owed |
| A-03 | Reservation stations | n/a: as A-02 | no reservation-station module elaborates |
| A-04 | Dynamic direction predictor (BHT / PHT) | `BHTEntries = 0` | `bht` absent |
| A-05 | Dynamic target predictor (BTB) | `BTBEntries = 0` | `btb` absent |
| A-06 | Return-address stack | `RASDepth = 0` | `ras` absent |
| A-07 | Prefetch engine | n/a: the imported core issues no fetch a prior execution's data selects, so there is no request generator to disable | no prefetch module elaborates |
| A-08 | SMT / second hardware thread context | n/a: the imported core is single-threaded by construction | no duplicated architectural register file and no thread-identifier field elaborate |
| A-09 | Instruction cache | n/a **and this one is authoring work**: no parameter deletes the fetch-path cache, which elaborates at every configuration the imported core admits | `cva6_icache` present, over its own tag, data and valid arrays |
| A-10 | Data cache | n/a, on the same ground as A-09 | the five write-through modules present, over 84 RAM, 18 cache-SRAM and 18 SRAM instances |
| A-11 | Tag cache | n/a: the structure is in the imported tag controller rather than in the core, so it is outside the netlist this record is taken over and outside any parameter this package carries | no tag-cache module elaborates in the core |
| A-12 | DVFS / frequency control | n/a: the imported core carries no PLL, no frequency-scaling state machine and no rail control | none elaborates |
| A-12a | Activity-driven memory power gating | n/a: the structure would sit in the memory controller, which is not this core and not this package | none elaborates |
| A-13 | LR/SC reservation register | `RVA = 0` | `amo_buffer` absent |
| A-14 | TLB / walk cache / page-table-walker FSM | `MmuPresent = 0`, `RVS = 0`, `RVU = 0`, `InstrTlbEntries = 0`, `DataTlbEntries = 0`, `UseSharedTlb = 0`, `SharedTlbDepth = 0` | `cva6_mmu`, `cva6_ptw`, `cva6_tlb` and `cva6_shared_tlb` all absent |
| A-15 | Scalar-FP register file and dynamic rounding-mode state | `RVF = 0`, `RVD = 0`, `XF16 = 0`, `XF16ALT = 0`, `XF8 = 0`, `XFVec = 0` | no floating-point unit elaborates |
| A-16 | Second tag plane | `CheriCapTagWidth = 1` | one tag bit per granule on the data path, and the parameter that would carry a second is set to one rather than left at a default |
| A-17 | Second-class memory maintenance opcodes | n/a: no such instruction exists in the imported decode surface either, so what the audit looks for is a decoder that has grown a case and not an array a parameter removes | no decode path reaches one |

## 3. The profile's ISA-visible removals, and the parameters that take them

These are not absence-contract rows. An RTL implementing any of them fails ordinary refinement rather than this contract, so they are recorded here because they are set in the same act and by the same package, and a reader auditing the configuration should not have to decide which half a field belongs to.

| Removal | Binding | Elaborated result |
| --- | --- | --- |
| The `C` extension | `RVC = 0`, `RVZCB = 0`, `RVZCMP = 0`, `RVZCMT = 0` | `compressed_decoder` absent |
| PMP | `NrPMPEntries = 0`, `PMPNapotEn = 0` | `pmp_entry` absent; the `pmp` and `pmp_data_if` shells remain, and that residue is authoring work |
| `Zicntr` and `Zihpm` | `RVZicntr = 0`, `RVZihpm = 0`, `PerfCounterEn = 0` | `perf_counters` absent |
| The S and U rings | `RVS = 0`, `RVU = 0` | carried with A-14 above |
| Asynchronous interrupt delivery beyond the machine timer | `SoftwareInterruptEn = 0` | no software-interrupt path elaborates |
| The debug module and the trigger module | `DebugEn = 0`, `SDTRIG = 0`, `Mcontrol6 = 0`, `Icount = 0`, `Etrigger = 0`, `Itrigger = 0` | `trigger_module` absent, and no debug port elaborates |
| The capability-mode flag, the machine being purecap-only | `RVZcherihybrid = 0`, `RVZcheripurecap = 1` | the hybrid decode path is unreachable, though the mode signals remain in the imported source and their deletion is authoring work |
| The vector and hypervisor extensions and the coprocessor interface, none of which is C-class | `RVV = 0`, `RVH = 0`, `CvxifEn = 0` | no accelerator dispatcher and no coprocessor elaborate |

## 4. What no parameter reaches, and what that costs

**Four residues, and they arrive by two different doors.** **Two of the eighteen rows above carry `n/a` on the second of the three grounds §1 separates**, which is the one that is work rather than a fact about the imported core: A-09 and A-10, the two caches, which the first item below takes together. The other three items are rows a parameter *does* take, where the value removes the array and leaves the structure around it standing, so the row is bound and a residue sits beside it. All four are authoring work that no configuration reaches, and the count is over the items below rather than over the rows above.

- **The caches, A-09 and A-10.** They are the largest single item, and no configuration the imported core admits removes them. What replaces them is flat SRAM at fixed latency, which is authored rather than configured.
- **The PMP shells.** Zeroing the entries removes the comparator array and leaves two wrapper modules standing.
- **The capability-mode signals.** Setting the hybrid extension off makes the mode path unreachable, and the signals stay in the imported source until they are curated out.
- **Static-only prediction.** This is the one row where zeroing a parameter and satisfying the requirement are different acts. `BHTEntries = 0`, `BTBEntries = 0` and `RASDepth = 0` discharge A-04, A-05 and A-06, which ask for zero mutable predictor state, and they leave the core predicting not-taken always. R-15-019 asks for prediction that is a fixed function of encoding and displacement sign, which is a different thing and is not a parameter. **No absence-contract row and no coverage cell audits that difference**, which is a register gap reported and not closed here.

## 4a. The tag fabric's route, recorded so it is not derived twice

**The capability- and tag-carrying interconnect is curated here as a functional reference and authored under route (a) afterwards**, and that disposition is written down because both readings are otherwise equally available from the artifacts. R-15-092 requires the net-new blocks authored in a formal-semantics HDL and proven, and names the DMA fabric among them; the pinned `axi-cheri-tagcontroller` is described in [THIRD-PARTY.md](../THIRD-PARTY.md) as the functional reference for exactly that block. Whether elaborating the pinned tree is the act R-15-092 forbids is a question neither artifact answers.

It is not. The three-route ladder exists so a block can stand at evidence tier before it stands at proof tier, and R-15-092's *authored* is a statement about the artifact of record rather than about every artifact that stands where it will stand; the plan's §11 says of route (a) that nothing is owed before it opens, well after the co-simulation gate. So the fabric is elaborated and differentially tested now, and the authored, proven block is the closing act it always was.

**The edition is the one the integration takes, and the name `git describe --all` gives the pin is not a lineage.** The pinned `Capabilities-Limited/axi_cheri_tagcontroller` at `173646d5` is the revision `lowRISC/cva6-cheri` carries at its own `vendor/zero-day/axi_tagcontroller` gitlink and the revision `lowRISC/mocha` vendors at `hw/vendor/tagctrl.lock.hjson`, so the datapath takes that edition unmodified, the bring-up SoC vendors it under two patches of its own, and neither reads a later one. `git describe --all` abbreviates the pin as `remotes/origin/upstream-3-g173646d`, the repository carrying no tag for a plain `git describe` to reach, and that name gives the nearest ancestral ref rather than a side branch: the ref it reaches for, `origin/upstream`, stops three commits below the pin, and the pin is itself an ancestor of the fork's own default branch. Later work on that branch replaces the flat tag store with a root-and-leaf table front-ended by per-stream caches, floated on a branch name rather than a commit in its own dependency manifest, which deepens the structure the A-11 row books as sitting in the imported tag controller rather than in the core, and it deletes `axi_tagctrl_reg_wrap.sv`, which [the delta's §2.4](../docs/rtl-reparameterization-delta.md) reads. So the later edition is a worse functional reference for a design carrying no tag hierarchy rather than a newer one (read 2026-08-31, R-18-001a).

**What that means for an auditor reading this record.** The fabric carries no row in §2 and owes none: those rows bind an absence to the parameters that remove it, and a curated fabric is a structure the build *contains*. What it carries instead is this disposition, and the thing to check against it is that the co-simulation evidence never reads as refinement evidence. No FEV, no Kôika or Kami refinement, and no RTL ⊑ Sail claim covers this block today; what covers it is the corpus agreeing through the capability-widened commit trace, which is agreement with the golden model and not proof against it.

## 5. Where the enumeration is taken

The state enumeration this record is the second half of is taken by [`tools/run.py rtl`](../tools/vos/cli/rtl.py), which elaborates the imported core at this configuration and at the stock CHERI configuration and reports the module set, the instance count and the difference. The record states which parameters cause that difference; the tool states what the difference is. Neither is derived from the other, which is what makes them evidence rather than one fact written twice.
