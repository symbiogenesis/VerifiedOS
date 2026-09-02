# The Welded Block Size: Its Constraint Set and the Shape of an Answer

> A derived view, governed by [R-15-014a (vii)](requirements-register.md).
> It decides nothing. It states what constrains the one parameter four instructions share, which of those constraints can be evaluated today and which are owed to a measurement, and what an admissible answer looks like when the freeze's second act takes it.
> Where this document and [the register](requirements-register.md) disagree, the register wins and this document is defective.

## How to read this

The **welded block size** is the naturally aligned granule group that `cbo.zero` allocates, `cloadtags` reports the tags of, `creclaim` sweeps, and `cbo.scrub` verifies. R-15-007q welds the tag group to the CBO block rather than leaving it the implementation-defined cache line upstream ties it to, so the four are one parameter and not four. R-15-014a puts it in the closed delta of the final freeze, item (vii), and says in the same clause what an answer must be: *scored against a first-class SRAM macro geometry and a second-class deck row and page geometry together, whose answer is the interval satisfying both and not a value satisfying one*.

That sentence is the whole reason this document exists rather than a number. A value satisfying only the SRAM macro forecloses the second class **silently**: nothing in the model, the configuration, or any report would say that the deck geometry had never been consulted, because the parameter would be sitting there looking decided. So the instrument's output is a matrix of intervals, and its refusals are aimed at the ways an answer can look complete while resting on one geometry.

This is not a second freeze-measurement instrument. [The freeze-measurement contract](freeze-measurement-contract.md) records in its own §10 that this item and the per-class bank count are re-derived from realized macro geometry rather than from a composed image, so no corpus, no composition recipe, and no byte threshold reaches them, and a freeze report quoting either from that instrument is a finding against it. This document therefore carries none of that machinery, and acquiring any of it would make it the thing that contract already refuses.

## 1. Where the parameter lives

**Five artifacts write the number, one declares the key it arrives on, and this document states the set it must lie in.** The model's declaration and the composition's are two independent statements of one fact, asserted equal at each of the four instructions rather than merged, and the assertion is what keeps them from drifting once something executes. The harness, the generated configurations and the authored capability package are transcriptions with no assertion behind them at all, which is what the rule below is for.

| Site | What it writes | Role |
| --- | --- | --- |
| [`core/cap_format.sail`](../model/model/core/cap_format.sail) | `log2_cap_block_size`, and `caps_per_block` derived from it and the granule | the model's declaration, beside the granule it is a multiple of |
| [`config/verifiedos.json`](../model/config/verifiedos.json) | `platform.cache_block_size_exp` | the frozen profile's own composition |
| [`config/config.json.in`](../model/config/config.json.in) | the same key | the generated test-matrix configurations |
| [`unit_tests/test_cheri_insts.sail`](../model/model/unit_tests/test_cheri_insts.sail) | `caps_per_block` as a literal | the harness's transcription of the group width |
| [`vos_cheri_pkg.sv`](../rtl/vos_cheri_pkg.sv) | `Log2CapBlockSize` | the authored RTL's transcription, and the one site outside the model |
| [`core/platform_config.sail`](../model/model/core/platform_config.sail) | the key itself, at `range(0, 12)` | the bound a composition is read under, not a value |
| this document | the candidate set the number must lie in | the constraint statement |

The four consumers, each reading one of the two declarations and asserting the other agrees: `cbo.zero` ([`Zicboz/zicboz_insts.sail`](../model/model/extensions/Zicboz/zicboz_insts.sail)) allocates the block in one write; `cloadtags` and `creclaim` ([`CHERI/cheri_insts.sail`](../model/model/extensions/CHERI/cheri_insts.sail)) walk it a granule at a time and return `bits(caps_per_block)`; `cbo.scrub` ([`platform/cbo_scrub.sail`](../model/model/extensions/platform/cbo_scrub.sail)) reads every codeword in it through the ECC check. Two further readers take the parameter without deciding it: the attested devicetree emits the block size as a property, and the configuration validator refuses a `Zic64b` composition at any exponent but six.

## 2. The candidate space

Both declarations spell the parameter as an exponent, so every candidate is a power of two and the space is the exponent's range rather than an arbitrary byte count. The model bounds that range at `range(0, 12)`, which is `max_mem_access`, because `cbo.zero` performs the whole block in a single write.

## 3. The constraints

One row per constraint, each citing the entry that owns it. The **status** column has two admitted values and no third: `derivable` means the constraint can be evaluated against artifacts that exist, and `owed` means it cannot and names what supplies it.

| Id | Constraint | Ground | Status |
| --- | --- | --- | --- |
| C1 | the block is a power of two | both declarations are exponents | derivable |
| C2 | the block is a whole number of 8-byte granules | R-15-203, R-15-247a | derivable |
| C3 | the group fits an integer register: `caps_per_block` at most XLEN, so the block is at most 512 bytes | R-15-007q, R-15-002a | derivable |
| C4 | the block is at most `max_mem_access`, 4096 bytes | the single-write allocation; subsumed by C3 | derivable |
| C5 | the block is a whole number of ECC codewords, 32 bytes at the payload R-15-181a fixes or 16 at its fallback | R-15-181, R-15-181a, R-15-182 | derivable |
| C6 | the block does not straddle a revocable interval, which the bitmap aligns at 64 bytes | R-08-005a, R-15-007s | derivable, and not binding |
| C7 | the block is a whole number of first-class SRAM macro rows, and does not straddle one | R-15-014a (vii) | owed to R4, R5 |
| C8 | the block is a whole number of second-class deck rows, and lies within one page | R-15-014a (vii), R-15-247 | owed to R4, R5 |
| C9 | the block's single-access sense width is realizable on the second class | R-15-181a's fallback clause, R-15-247m | owed to R5 |
| C10 | the per-block latency of each of the four instructions is inside its slot | R-15-182, R-15-177a | owed to R-17-041's magnitudes, the M1 schedule |
| C11 | the sweep's preemption granularity survives the block width | R-08-007, R-08-007b | owed to R-17-041's magnitudes, the M1 schedule |
| C12 | the block is consistent with the frozen per-class bank count | R-15-247p | owed to R5, the freeze's second act |

**C3 is the one architectural fact this view derives rather than collects, and the register records it.** `cloadtags` and `creclaim` both end by zero-extending `bits(caps_per_block)` into an integer destination register, and an integer register is 64 bits (R-15-002a, R-15-007i). A group wider than 64 granules therefore has no destination to be returned in, and the model refuses it at typecheck rather than at run time. At the 8-byte granule R-15-203 fixes, that is a ceiling of **512 bytes**, and R-15-007q's criterion states it beside the two parameters the pin left open, which is where a criterion about an already-admitted instruction belongs. So the bound is the entry's, the refusal is the model's, and this table is the third statement of one fact rather than its only one.

**Two of the derivable rows bind and the rest are implied by them.** The floor is C5's codeword and the ceiling is C3's integer destination, so **the block is 32, 64, 128, 256, or 512 bytes**, which is 4, 8, 16, 32, or 64 granules. C2 is implied by C5, a codeword being a whole number of granules; C4 is implied by C3; and C6 binds nothing on that set, because every candidate at or above 64 bytes is already a multiple of the interval's alignment and every candidate below one fits inside a single interval. Under R-15-181a's 128-bit fallback codeword the floor halves and the set gains 16 bytes at two granules.

The declared 64 bytes is interior to that set, which is the useful shape of the result: the value the tree carries is at neither end, so no derivable constraint is what is holding it there, and what decides it is one of the owed rows.

**Three of the owed rows have their instrument and not their figure, which is why a landed instrument does not close them.** The timing-annotated model carries a row for each of the four instructions ([core/timing.sail](../model/model/core/timing.sail)), and R-17-041 makes the magnitudes in those rows the crown-jewel specification, not one of which is measured, so C10 and C11 have a table to be evaluated in and nothing to evaluate in it; the slot the latency is held against is the schedule's, which arrives with M1. C12 is the same shape one artifact over: [the bank-count instrument](bank-count-dse-contract.md) states that search and its pruning predicate has no operands, so no candidate is admitted there either, and the count arrives with R5's macro evidence at the freeze's second act rather than out of the search alone.

## 4. Why one parameter answers to two geometries

The block is a first-class unit and a second-class unit at once, and the coupling is not a symmetry anybody chose. `cbo.zero` and `cbo.scrub` are the first class's allocation and verify units, sized against an SRAM macro row. But `cbo.zero`, `cbo.scrub`, `cloadtags` and `creclaim` reach the second class on the same terms as the first (R-15-247s), which makes the allocation and verify units second-class units too. So the same block that must be a whole number of SRAM macro rows must also be a whole number of oxide-deck rows inside one page, and the two geometries have no reason to admit a common multiple that is also a power of two inside the C1 to C6 set.

That is the failure R-15-014a (vii) is written against, and it is why C7 and C8 are separate rows rather than one. A search that evaluated C7 alone would return a healthy-looking interval; the point at which C8 turned out to admit nothing inside it would be R5, long after the freeze.

## 5. The shape of an answer

One row per first-class macro geometry candidate, one column per second-class deck row-and-page candidate, each cell the interval over the C1 to C6 set intersected with that pair's own C7 to C9 constraints.

| First-class macro geometry | Second-class deck row and page geometry | Feasible interval |
| --- | --- | --- |
| not authored | not authored | n/a |

**The matrix ships with both axes empty, and that is this item's result rather than its failure.** No deck row width, page size, or single-access sense width exists anywhere in this repository, and R-15-247m forbids one being asserted ahead of the macro measurement: *no density figure is an architectural input ahead of that measurement*. The macro architecture that would state a row and a page is R4's to author and R5's to measure. What M0.13 can do before them is fix the candidate space, close the derivable constraints over it, and state what an inadmissible answer looks like, which is what M0.11 did for the freeze report before a backend existed.

## 6. What makes an answer inadmissible

| Id | The refusal |
| --- | --- |
| BG-1 | a report naming a point rather than an interval, the freeze taking the value and the interval being what this instrument owes it |
| BG-2 | an interval whose binding constraint is a first-class row alone, which is the silent foreclosure R-15-014a (vii) exists to prevent |
| BG-3 | a second-class geometry or density figure used as an input while its qualification state is false, which is M0.14's own finding applied to this axis |
| BG-4 | a candidate outside the C1 to C6 set, which is a search defect rather than a choice |
| BG-5 | a freeze report reaching this item from the freeze-measurement instrument, which that contract's §10 already makes a finding against itself |

## 7. What this document is not

It is not the macro architecture, which R4 authors. It is not the per-class bank count, which R-15-247p owns and [its own instrument](bank-count-dse-contract.md) constrains the way this one constrains the block. It does not name a value, and neither does that one: the block size is item (vii) of R-15-014a's closed final-freeze delta and the bank count is item (viii) of the same closed delta, so a document naming either would be taking a freeze decision early, which is an amendment that reruns the review gate under R-18-034 rather than a second-act decision.
