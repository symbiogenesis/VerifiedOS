# The Placement Search: What It Exports, What It Enumerates, and What It Admits

> A search contract beside [the memory plan](../proofs/MemoryPlan.v), read against R-08-011's plan, R-08-012c's containment, R-08-014's side condition, R-15-007k's quantization and R-08-012a's ordering.
> It decides nothing. It states the shape the placement problem is exported in, the candidate set the search enumerates, the order its objectives rank in, the constraints every candidate is re-checked against and the entry each decides for, the shape of the report, and what makes a reported placement inadmissible.
> Where this document and [the register](requirements-register.md) disagree, the register wins and this document is defective; where it and [the proof file](../proofs/MemoryPlan.v) disagree, the proof file wins, the checks here being a port of its definitions and never their replacement.

## How to read this

The memory plan is M1.9's, one statement artifact carrying the `Plan` record every composition magnitude is a field of, the boolean checks the register's memory-plan obligations are decided by, and one demo plan instantiating them with witness values. Q5 asks for that problem as data a search can read, a search over a small candidate set, and an independent exact check every proposed placement is admitted by. This document states the three, and it restates no figure the tool computes: the counts, the spans, the paddings and the timing sums are [the report](#5-the-report)'s to print from the plan, and a figure copied into prose here would be the defect this repository is built to catch, on the precedent [the bank-count contract](bank-count-dse-contract.md) sets.

**The plan's figures are witness values.** The proof file says so of every one of them, that each is an arbitrary witness value carrying no composition claim, so what a search over that plan establishes is that the machinery works and nothing about the product. A tighter packing found there is a checked improved assignment over a witness plan and credits nothing, which is the second arm of the item's own completion clause and the only arm open before a composed roster exists.

## 1. The export

[`run.py placement export`](../tools/vos/cli/placement.py) writes [tools/generated/memory-plan.json](../tools/generated/memory-plan.json) from the proof file alone, and **K-88** holds the tracked artifact byte-identical to what the reader writes now, as a host row whose generator runs at the gate. The reader is [vos/memplan.py](../tools/vos/memplan.py), and what it reads is stated so that a reader of the artifact knows what was not invented.

| Section | Read from | Carries |
| --- | --- | --- |
| `header` | the file | its md5, the standing plan's name, every typed list read and every typed list left unread by name, the literal fields read, the count of plans built |
| `plan` | `build_plan`'s literals and the lists the standing plan is built from | per region its kind, cycle-criticality judgment, class, base, length, live range, granule, declared granule counts, island, fetch count, charged slot and placement delta; the islands with base and span; both fetch constants; the placement list, the origin roster, the fixed first-class charge and the first-class budget; the whole roster's worst-case timing |
| `variants` | every other `: Plan := build_plan` definition | the lists each is built from and its second-class constant, by name |
| `absent` | nothing | the four fields the item's export list names and the plan does not carry, each with what would own it |
| `constraints` | nothing | each check the search admits by, and the register entry it decides for |

**The class is read, not chosen.** A region's class is the register's placement of its kind by name, and where the register names none, the criterion over the plan's own cycle-criticality judgment; the reader takes `placed_by_name`'s arms and `criterion_class` out of the file and holds `build_plan`'s `class_of` to that shape, so the artifact carries no class a composition could have chosen.

**The granule is computed, not copied.** R-15-007c's function is ported from the file's `representable_granule`, and the declared granule counts beside each base and length are the plan's own; the check multiplies the count back rather than dividing, so a base that is no whole number of its granule is refused and never rounded (the file's reading 8).

**Four fields are declared absent by name.** Owner, bank, reserved size and the slot's timing bound are on the item's export list and are no field of the plan: R-08-045's charge is read over a list of region indices with no line item named, R-15-228a makes the bank map an input the plan reads only as an island map, a region's reservation is exactly its length, and the slot bound is the frame's in [CyclicExecutive.v](../proofs/CyclicExecutive.v). Each is carried as a stated absence with its ground, and inventing any of them would be an unowned derived fact. Whether the plan should gain an owner or a bank field is a register act this document reports and does not take.

**What the reader refuses.** A list the standing plan is built from that is absent or is no `cons` chain, a kind no constructor spells, a literal field missing, a `placed_by_name` that decides fewer kinds than the inductive carries, a `build_plan` field of a shape the reader does not read, and a standing plan no longer built: each is a raise, which the generated group reports as its finding rather than as a crash. A list the file defines by `app` is left unread and named as such, and matters only where `build_plan` reads it, which is refused there.

## 2. The candidate set

The search is per island, and the set is declared once in the tool and printed at the head of every report:

> per island, every assignment of slot bases to that island's regions in which each base is a multiple of the region's step inside its island, the step being the least common multiple of the region's R-15-007c granule and the island's quantum, and the quantum being the greatest common divisor of the standing plan's bases in that island measured from the island's base; the other islands' regions stay at their standing bases, and islands, classes, kinds, lengths, live ranges, fetch counts and charged slots are fixed.

Two properties follow from the predicate and are what it was chosen for. Every candidate base is granule-aligned, so R-15-007k's quantization is met by construction and re-checked anyway. And the standing plan is a candidate, since every one of its bases is a multiple of the quantum by the quantum's definition and of its granule by the plan's own admission, so the comparison the item wants is between members of one set and not between a set and a point outside it.

**The finer set is counted and not enumerated.** Bases at every multiple of each region's granule alone are the natural predicate and the report prints that set's size beside the enumerated one; it is enumerated nowhere, its size being what makes it not a small candidate set, and a run that claimed it would be claiming what it had not done.

**Completeness over the set is a walk with a sound prune.** Regions are placed in roster order and a prefix is abandoned only where the file's own pairwise test refuses it: two regions whose live ranges overlap and whose slots meet. A pair `colouring_ok` refuses is refused under every completion, since the check is a conjunction over pairs, so the grid points under an abandoned prefix are decided and counted as such. Every prefix that survives to a leaf is a whole plan, the other islands at their standing bases, and it is admitted or refused by the exact check alone.

## 3. The objectives

R-08-012a orders the plan's objectives with the footprint first and locality after it, and a base search reaches only part of that order.

| Term | What it is | Moved by a base |
| --- | --- | --- |
| footprint | the proven simultaneous peak, the most bytes live at once over the live ranges and lengths (R-08-012) | no |
| span used | how far past the island's base the last slot ends | yes |
| unused reservation | span used less the footprint | with the span, one for one |
| padding | bytes under the span no slot covers | yes |
| bank spreading | R-08-012a's locality term over banks | not modellable, the plan carrying no bank |

The search ranks admitted candidates lexicographically on span used and then padding, and the report prints the footprint unmoved on both sides. A report claiming a footprint gain from a base search is wrong on its face, and the tool cannot print one.

## 4. The constraints, and who decides them

Every candidate is decided by the port of the file's own checks, one Python function per Gallina definition, each named for the definition it ports and holding to it under [the tools' own tests](../tools/tests/test_memplan.py), which run the port over the file's admitted plan and every variant plan it builds and require of each the verdict the file's own `Example` lines state.

| Check | Entry | What it decides |
| --- | --- | --- |
| `containment_ok` | R-08-012c | every slot inside its island at both edges |
| `colouring_ok` | R-08-014 | slots disjoint wherever live ranges overlap, the file's reading 7 |
| `slot_bases_quantized` | R-15-007k | every base its declared granule count multiplied back |
| `slot_lengths_quantized` | R-15-007k | every length likewise |
| `plan_ok` | R-08-045 | every region charged once and nothing charged the roster does not carry |
| `places_ok` | R-15-247s | every class the register's placement |
| `slot_indices_held` | R-15-247j | every charged slot one the frame carries, decided against a slot count the plan does not carry and so outside the search |
| `pool_fits` | R-14-010 | the origin population inside the first-class budget, decided against a population that is an argument and so outside the search |

**R-08-014 is taken as the file takes it.** The entry's own word is *disjoint* and the file reads the side condition over *overlapping* live ranges, reporting the inversion to the register as its gap f, because the literal words refuse the mechanism R-08-012 exists to use. The enumerator shares a slot exactly where the file's `live_overlap` is false; the literal reading is carried in the port only so that a test can show it refusing the shared-slot plan the file admits.

**The check admits and the objective never does.** The search's ranking reads scores of candidates the check has already admitted; no candidate reaches the report as feasible without passing the port, and the port reads nothing the ranking computed. The port is development hygiene, as the item's own text puts it: the proof status of every check stays with the file, which decides the demo plan and its variants by conversion, and nothing here is evidence about the machine.

## 5. The report

[`run.py placement search`](../tools/vos/cli/placement.py) prints one block per island and a footer, every figure computed from the plan at run time.

| Line | Carries |
| --- | --- |
| the head | the plan's name and the file's md5; both fetch constants, named as witness values; the candidate-set predicate above; what admits and what prunes; the degrees of freedom not taken |
| per island | the regions, the quantum and the steps; the candidate count with the per-region base counts it is the product of, and the finer set's size beside it; the pruned, leaf and admitted counts; the standing placement's bases, footprint, span used, unused reservation and padding; the best admitted placement's, or that none was admitted; whether the best is bettered on span or padding, with the footprint unmoved; whether the file's own shared-slot plan is the best found |
| worst-case timing | the sum of every region's placement delta, equal on both sides because the class assignment is the register's and a base search moves no class, fetch count or slot |
| status | complete enumeration over the declared set, or cut short and said so; never optimality outside the set; the admitted-workload comparison as not taken, and why |
| residuals | the four absent fields with their grounds; the cost inputs, none read and none rounded |
| verdict | that any gain is over witness values and credits nothing to the product, and that the proof status stays with the file |

## 6. What makes a report inadmissible

| Id | The refusal |
| --- | --- |
| PS-1 | a region moved across an island, or an island's base or span moved; R-15-228a makes the map an input |
| PS-2 | a class, kind, length, live range, fetch count or charged slot moved; the class is the register's placement and the rest are the plan's own fields, and a shared-lifetime assumption is an architecture change taken elsewhere |
| PS-3 | a claim of optimality from one admitted candidate, or from a complete enumeration stated as reaching past its declared set |
| PS-4 | a figure copied from the demo plan and presented as a composition claim, or a gain over it credited to the product |
| PS-5 | a run cut short read as infeasibility, or a candidate refused by the check read as anything but refused |
| PS-6 | a bank-level term in the objective while the plan carries no bank and the bank count is undecided, which is [the bank-count contract](bank-count-dse-contract.md)'s BD-1 met from this side |
| PS-7 | a footprint gain attributed to a base search |
| PS-8 | a placement admitted by the objective, the search tool, or this document rather than by the check, and a check admitted as proof rather than as the port it is |

## 7. What this document records rather than settles

**The comparison on admitted workload is owed and not taken.** The item's fourth bullet compares placements on the admitted workload, and no composed roster exists to compare on: the demo plan's figures are witness values, R-18-004d's demonstration set is unauthored, and the absolute limits Q1 states are Q1's to state. The report says so in its status line, and the half of the item that wants them waits behind those acts.

**Two fields the plan would want for the register's own terms are reported to the register.** R-08-012a's bank-spreading term is stated over banks the plan does not model, and R-08-045's per-line-item charge is read over region indices with no owner named. Whether the plan gains a `bank_of` or an owner field is a register act at R-08-011 and R-08-012a, and this document carries the gap and takes no side.

**No solver is added.** The item admits OR-Tools CP-SAT where a coupled placement or scheduling search justifies it, and nothing here couples one: the enumeration completes over its declared set without one, and a dependency is selected at the milestone that reads its licence and pins it, which is a decision the plan reserves and this document does not take.
