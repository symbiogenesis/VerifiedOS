# The Per-Class Bank Count: What Decides It, and What It Is Waiting On

> A derived view, governed by [R-15-247p](requirements-register.md).
> It decides nothing. It states the candidate set the second class's bank count is searched over, the one constraint that prunes it and the two objectives that rank it, which coefficient each of the three is waiting on and who owes it, and what makes a reported answer inadmissible.
> Where this document and [the register](requirements-register.md) disagree, the register wins and this document is defective.

## How to read this

Bank granularity on the second class is admitted against three quantities jointly: the island bandwidth ceiling §11 consumes, the read energy per bit that bitline capacitance sets, and the R-15-247g simultaneous-activation envelope. **The droop envelope is a hard admission constraint and the other two are objectives**, which is the asymmetry the whole search turns on: a point outside the envelope is pruned exactly as every candidate failing the five-part admission test is, and is never traded against bandwidth or energy however well it scores on them.

The count is item (viii) of R-15-014a's closed final-freeze delta, so this document is an instrument for an act that has not happened. [The freeze-measurement contract](freeze-measurement-contract.md)'s own §10 says why the instrument is separate: the bank count is re-derived from realized macro geometry rather than from a composed image, so no corpus, no composition recipe, and no byte delta there reaches it, and *a freeze report quoting either from this instrument is a finding against this bullet*. This document therefore carries no corpus and no byte threshold, and acquiring either would make it the thing that contract refuses.

## 1. The knob

The second class is divided into banks whole-bound to islands: no address interleaving crosses an island boundary, no bank is dynamically allocated, stolen, or donated, and no bank count varies with occupancy or load (R-15-247p). So the count is a composition-time constant with three consumers and no runtime reader at all, which is what makes it searchable off-model.

The configuration declares **4096 banks** over an 8 GiB second-class region, and it says on its own face that this and every figure beside it is a placeholder: `qualified` is `false` on both classes, and R-15-247m admits no density figure as an architectural input ahead of the measurement it names. The candidate set is **64 through 65536** banks, the range the model's own `memory_class_banks` type admits intersected with the powers of two an island binding can divide a region into.

## 2. What prunes, and what ranks

| Symbol | Quantity | Role | Owed to | Status |
| --- | --- | --- | --- | --- |
| `I_bank_peak` | peak activation current of one bank | prunes | R-15-189i's power vectors, R5 | pending |
| `I_pdn_max` | the delivery network's simultaneous-on ceiling | prunes | R-15-189i's provisioning, R5 | pending |
| `W_bank` | per-bank transfer width | ranks | M0.8's class parameterization | pending |
| `s_island` | an island's TDM slot share | ranks | the M1 schedule | pending |
| `C_bl_per_row` | bitline capacitance per row | ranks | R-15-247m, R5 | pending |
| `split_cycle_critical` | how much of the roster's working set is cycle-critical | ranks | a recorded product decision | pending |
| `tag_ecc_share` | the tag plane and its DECTED code as a share of the array | ranks | R-15-247a | stated |

**Six of the seven are pending and one is stated**, and the one that is stated is the smallest of them. That ratio is this document's main content: the search cannot be run, and what it is missing is not detail but every coefficient that would make it a search rather than an enumeration.

**The pruning predicate.** A candidate is admissible only where the largest set of banks the composition-fixed schedule ever activates at once draws no more than the delivery network is provisioned for, at the worst corner and with thermal coupling and the power signature admitted on the same footing (R-15-247g). Finer banking lowers peak activation current at the same average throughput, so the predicate is monotone in the count and the search's feasible region is a tail rather than an interval. Both of its coefficients are pending, so **the predicate cannot be evaluated at any candidate**, and no candidate is admitted.

**Objective A, island bandwidth.** An island's ceiling is fixed by the TDM schedule and the bank binding rather than regulated at run time (R-15-247p, R-15-050), so it rises with the banks an island is granted and with each bank's own width. Both terms are pending. What the register does state without a coefficient is the shape: *each island's bandwidth ceiling quantizes to its assigned banks or macros and feeds §11 admission* (R-15-228), and a bandwidth-bound island therefore claims several banks rather than a faster one.

**Objective B, read energy per bit, against array efficiency.** Bank size sets bitline capacitance and so read energy per bit, while more periphery per bit costs array efficiency and so capacity. That is two objectives on one knob and a real optimum rather than a monotone preference, which is the reason the count is searched at all rather than pushed to one end. The energy coefficient is pending; the efficiency side has one figure that is not, the tag plane at one bit per 64-bit granule costing 1.5625% of the array plus its own DECTED code, some 2.5 to 3.5% of the bulk array once that code is counted (R-15-247a, R-15-203).

## 3. What the arithmetic can decide today

Four figures fall out of the composition with no coefficient at all, and [tools/bank-dse.py](../tools/bank-dse.py) computes them per candidate: the bank's own size, the refresh sweep against the deadline the retention floor sets, the mode-exit discharge dwell, and whether the region divides the count exactly. None of them is an objective and none of them admits anything; they are the shape constraints a candidate must satisfy before the pruning predicate would even be asked.

They are not restated here as numbers, because the tool computes them from the configuration and a figure copied into prose is the defect this repository is built to catch. What is worth stating is which of them binds: the refresh sweep is the only one that can fail, and it fails by the count rising until the phases the cadence needs no longer fit inside the retention floor.

That deadline is the **only** thing a retention figure may be consumed by. R-15-247c admits no reset, sanitization, or containment guarantee resting on a characterized decay rate, on an upper bound on retention, or on any timing derived from leakage, and states retention figures as lower bounds with the refresh deadline as their one consumer. So the sweep comparison is a use of the floor and never of the ceiling, and a candidate is not "safer" for having margin against it: it either fits or it does not.

## 4. The report

One row per candidate, and every column that wants a coefficient prints the symbol it is waiting on rather than a number or a blank.

| Column | Source |
| --- | --- |
| banks | the candidate |
| bank bytes | the region divided by the candidate |
| refresh phases, sweep cycles, deadline cycles | the cadence and the retention floor, from the configuration |
| discharge phases, dwell cycles | the same |
| droop headroom | `I_bank_peak`, `I_pdn_max` |
| island bandwidth | `W_bank`, `s_island` |
| read energy per bit | `C_bl_per_row` |
| admitted | n/a while the pruning predicate has no operands |

The report carries a residuals block naming every pending symbol and what owes it, and its verdict line states how many candidates cleared the arithmetic that exists and that **none is admitted**, with the reason.

## 5. What makes a report inadmissible

| Id | The refusal |
| --- | --- |
| BD-1 | a bank count reported as decided while any symbol above is pending |
| BD-2 | a bank count reported as decided while the second class's `qualified` flag is false, which is R-15-247m's own gate applied to this axis |
| BD-3 | a pending coefficient filled from an order-of-magnitude estimate, the estimate document's own closing sentence disclaiming its figures as freeze inputs |
| BD-4 | droop traded against bandwidth or energy, which inverts R-15-247p's stated asymmetry and admits a point the envelope excludes |
| BD-5 | a candidate outside the declared set, which is a search defect rather than a choice |
| BD-6 | a freeze report reaching this item from the freeze-measurement instrument, which that contract's §10 already makes a finding against itself |

## 6. Two things this document records rather than settles

**The per-class capacity split is a precondition nobody has taken.** How much of the roster's working set is genuinely cycle-critical decides how the budget divides between the two classes (R-15-247, R-15-247s), and until it is stated the second class has no bandwidth target its bank grant is scored against. It is a reading of the roster rather than a search output, and it is carried above as `split_cycle_critical` so that the freeze does not settle it by whatever the memory plan happened to place.

**R-15-108's own parameter list does not name the bank count.** Its criterion enumerates the frozen microarchitectural set as VLEN per class, core count per class, issue width and pipeline depth, the SRAM bank/macro/tier-to-island assignment, scratchpad sizes, the CBO block size, and the TDM-NoC schedule. R-15-247p and R-15-014a (viii) both put the per-class bank count in the frozen set, and the tier-to-island assignment is the nearest thing R-15-108 has to it. Whether that is the same parameter under another name or an omission is a register question rather than this instrument's, and repairing it is an amendment that reruns the review gate, so it is reported here and not absorbed.
