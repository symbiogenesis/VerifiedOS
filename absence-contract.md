# The Microarchitectural Absence Contract

*Normative as a **view**. This document is the artifact **R-15-100a** mandates and R-15-021, R-15-100, and R-15-107 depend on: the enumerated register of microarchitectural absences with a discharge recorded against each. It is **derived from** [requirements-register.md](requirements-register.md), which remains the audited artifact per R-05-152.*

> **Precedence.** Where this document and the register disagree, **the register wins and this document is defective.** Every row cites the requirement that governs it. This document adds no obligation of its own.

## Why this document exists

R-15-100's acceptance criterion reads *"each appears in the **absence-contract register** with a discharge."* R-15-021 requires that predictor absence *"appears in the absence-contract register, not among the refinement obligations."* R-15-107 requires that *"both entries exist."* No absence-contract register existed. That gap is booked as **[D-14](requirements-register.md#d-14)**.

It is the same defect as [D-13](requirements-register.md#d-13) one layer down, and it lands on the deliverable the specification is most emphatic is available now. R-18-012 calls the absence contract *"buildable on day one and cheap"* and *"the one part of the least-built layer that does not need the layer to exist first"* — the sole part of RTL ⊑ Sail (R-17-039, the least-built layer of the stack) that can be discharged before any RTL of record exists. R-18-003b(ii) makes it day-one deliverable number two. This is the checklist that deliverable runs.

## 1. What the contract is, and why it is a separate register

Sail models **architectural** state. RTL ⊑ Sail therefore cannot state, let alone discharge, *there is no branch predictor* — the proposition is not expressible in the model the refinement is against. The two registers are separated for that reason (R-15-098).

The semantic content of every removal in this document is **one hyperproperty** (R-15-101):

> Cycle-level timing and memory traffic are a function of the instruction stream and architectural state alone, never of prior execution history.

The contract does **not** prove that hyperproperty over a cycle-accurate model. It discharges a **sufficient structural condition** for it: that the enumerated structures and their state elements do not exist (R-15-101). That is what makes it cheap, and it is the whole argument for preferring removal to partitioning — every microarchitectural removal converts a correctness obligation into an absence obligation, moving work out of the least-built arrow. Deletion is preferred to partitioning **even where partitioning would suffice** (R-15-105).

## 2. Scope: what owes this contract and what does not

| Class | Owes | Governing |
| --- | --- | --- |
| **ISA-visible removals** — MMU and its Sv39 walker, PMP, the S/U rings, `C`, `Zifencei`, `Zalrsc`/`Zacas`, scalar `F`/`D`, dynamic `frm` state, asynchronous interrupt delivery | **Nothing further.** These are absences in the frozen Sail model; an RTL implementing any of them fails *ordinary* refinement | R-15-098, R-15-099 |
| **Microarchitectural removals** — the register in §3 | **This contract.** Invisible to a model of architectural state, so no rung of the RTL ⊑ Sail ladder discharges them | R-15-098, R-15-100 |

## 3. The register

Each row is a structure whose **absence** is claimed, with the discharge form that closes it. Discharge form is fixed by who authored the block, not by the structure (§4).

| # | Structure | Ground | Netlist evidence sought | Governing |
| --- | --- | --- | --- | --- |
| **A-01** | Speculative execution / transient state | fails admission tests (1)–(3) | no misspeculation-recovery path, no checkpoint or rollback state, no squash logic | R-15-012, R-15-100 |
| **A-02** | Reorder buffer | out-of-order issue removed | no ROB array | R-15-100, R-15-103 |
| **A-03** | Reservation stations | out-of-order issue removed | no reservation-station array | R-15-100, R-15-103 |
| **A-04** | Dynamic direction predictor (BHT / PHT) | fails test (3); prediction is static-only, a fixed function of encoding and displacement sign with **zero mutable predictor state** | no BHT or PHT array | R-15-012, R-15-019, R-15-021, R-15-100 |
| **A-05** | Dynamic target predictor (BTB) | as A-04 | no BTB array | R-15-019, R-15-021, R-15-100 |
| **A-06** | Return-address stack (RAS) | excluded **despite its IPC value**, being per-core mutable return history; the resulting call/return dispatch penalty is priced into WCET | no RAS or return-address prediction | R-15-019, R-15-023, R-15-100 |
| **A-07** | Prefetch engine | no prefetch request has a software origin; `Zicbop`/`Zihintntl` excluded | no prefetch request generator; every fetch-path state element passes the table-freeness test (§5) | R-15-046, R-15-100, R-15-103, R-15-104 |
| **A-08** | SMT / second hardware thread context | fails test (3) **by construction** | no duplicated architectural register file, no thread-ID field in pipeline state | R-15-012, R-15-100, R-15-103 |
| **A-09** | Instruction cache | flat SRAM at fixed latency; no hierarchy | no cache data, tag, or valid arrays on the fetch path | R-15-100, R-15-103 |
| **A-10** | Data cache | as A-09 | no cache data, tag, or valid arrays on the data path | R-15-100, R-15-103 |
| **A-11** | Tag cache | CHERI tags ride the SRAM word; no separate tag hierarchy | no tag-cache array | R-15-100, R-15-103 |
| **A-12** | DVFS / frequency control | power states are schedule artifacts, never control loops | no PLL or DVFS control path, no frequency-scaling state machine | R-15-100, R-15-103 |

**Absences the `fence.t` completeness argument additionally relies on.** These are discharged elsewhere — each is already absent by an ISA-visible removal or covered by its own named mechanism — but the flush-set claim depends on them, so the audit confirms them rather than assuming them (R-15-215):

| # | Structure | Discharged by | Governing |
| --- | --- | --- | --- |
| **A-13** | LR/SC reservation register | `Zalrsc` excluded — fails tests (3) and (1); ISA-visible, so refinement failure | R-15-012, R-15-025, R-15-215 |
| **A-14** | TLB / walk cache / page-table-walker FSM | MMU excluded; ISA-visible, so refinement failure | R-15-038, R-15-215 |
| **A-15** | Scalar-FP register file (`f0`–`f31`) and dynamic rounding-mode state | scalar `F`/`D` excluded; rounding is static, encoded per-instruction | R-15-039, R-15-083, R-15-215 |
| **A-16** | Second tag plane (initialization-tag plane) | declined hedge under the *verify rather than hedge* clause; one tag bit per granule, not two | R-15-013, R-15-035 |

## 4. The two discharge forms

The contract closes differently depending on who authored the block, and the difference **is** the residual (R-17-040).

| Block origin | Discharge | Strength | Governing |
| --- | --- | --- | --- |
| **Kôika / Kami-authored** — the net-new blocks with no legacy RTL: the capability- and tag-carrying DMA fabric, the TDM NoC, the fixed-function sequencers | A **structural predicate over the Coq term**, checked in the same prover as the refinement | In-prover. Adds **no semantic anchor** — the predicate is over an existing artifact, not a new semantics | R-15-092, R-15-102 |
| **Imported SystemVerilog** — CHERI-CVA6 front end, Ara, Gemmini | A **state-enumeration and structural check over the elaborated netlist**, plus **synthesis-configuration provenance** | A structural **audit, not a theorem**, and stated honestly as such | R-15-090, R-15-103 |

The imported-core check covers, by name: predictor arrays, reorder buffer and reservation stations, prefetch engine, cache data/tag/valid arrays, a second hardware thread context, and PLL/DVFS control paths (R-15-103).

**Honest ceiling.** The strongest microarchitectural claims about imported cores rest on the evidence tier, not the Coq close. The residual is not cost but *where it closes* (R-17-040, R-15-107).

## 5. The decision rule: table-freeness

The one boundary that could otherwise be argued case by case is fixed by rule (R-15-104):

> A state element in the fetch path whose **write data depends on a prior execution** is a **prefetcher** and fails the contract. One whose contents are a **function of the fetched stream** is **fetch pipelining** and passes.

The boundary is decided by table-freeness — **not** by size and **not** by run-ahead depth. The audit is therefore a table search, not a judgment call. The static-path fetch buffer passes on this rule (R-15-022, R-15-104).

## 6. The `fence.t` completeness claim

The contract also carries the flush-set **completeness** classification, because completeness is the claim that *no unenumerated state exists* — which the model cannot see, so the refinement cannot discharge it (R-15-106, R-17-040).

Every stateful structure in the RTL maps to **exactly one of four classes**, and a structure outside the map is a refinement failure (R-15-217):

| Class | Contents | Governing |
| --- | --- | --- |
| Architectural / context-switched | register files, restored in total by the kernel's restore set — residue is impossible rather than cleared, and a register outside the restore set is a failure of the kernel proof | R-15-214, R-15-217 |
| Partition-owned | SRAM banks/macros/tiers, TDM-NoC slots, per-partition interrupt-file state — flushing spatially-owned state would be a category error | R-15-216, R-15-217 |
| `fence.t`-flushed | **a single structure: the store buffer**, drained rather than merely fenced | R-15-213, R-15-217 |
| Stream-determined pipeline state | the static-path fetch buffer and the decode and execute latches, emptied by the fence's pipeline drain; **bounded by the same table-freeness test** as §5 | R-15-217, R-15-104 |

*"Did we flush everything"* is discharged against the RTL state inventory rather than a hand-maintained list (R-15-217). Nothing else joins the flush set, each would-be member being already absent or covered elsewhere — the A-13 through A-16 rows above are that argument's dependencies (R-15-215).

## 7. Disposition

| Property | Value | Governing |
| --- | --- | --- |
| Relation to RTL ⊑ Sail | A **separate gate on** the workstream, not a stage of it — no rung of the ladder discharges it | R-15-089, R-15-098, R-18-012 |
| Availability | **Buildable on day one and cheap**; the one part of the least-built layer that does not need the layer to exist first | R-18-012, R-18-003b |
| §18 status | a distinct bring-up gate | R-15-107 |
| §17 status | a named residual — the one obligation class whose imported-core half closes on audit rather than proof | R-15-107, R-17-040 |
| Why it inverts the difficulty | every removal converts a correctness obligation into an absence obligation, moving work out of the least-built arrow | R-15-105 |

## 8. Running it on day one

The contract needs no RTL of record, no toolchain, and no Sail model — only the imported cores, which exist today (R-18-012). Concretely, for each of the CHERI-CVA6 front end, Ara, and Gemmini (R-15-090):

1. **Elaborate** the core at its intended synthesis configuration.
2. **Enumerate** every state element in the elaborated netlist.
3. **Search** that inventory for the A-01 – A-12 structures by the evidence column of §3; confirm A-13 – A-16.
4. **Record synthesis-configuration provenance** — the parameters that disable each structure — so the absence is bound to a build, not to a reading. CVA6's branch-predictor and cache parameters are the live instance.
5. **Classify** every remaining state element into one of §6's four classes; anything unclassifiable is a finding, not a footnote.
6. Apply **§5's table-freeness rule** to every fetch-path element, mechanically.

Steps 1–3 and 5 are the state-enumeration check R-15-103 requires; step 4 is the provenance half of the same requirement; step 6 is R-15-104. For Kôika/Kami blocks the same six steps become one structural predicate over the Coq term (R-15-102) — but those blocks do not exist yet, so day one is the imported-core half, which is exactly the half that closes on audit.
