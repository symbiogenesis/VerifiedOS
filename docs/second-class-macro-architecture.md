# The Second-Class Macro Architecture: What the Five Properties Imply, and What R5 Measures at Each Part

> A derived view, governed by [R-15-247m](requirements-register.md).
> It states the macro architecture the second class's five properties imply and the measurand R5 takes at each of its parts; it states no figure. Every physical quantity it names is a symbol R5 returns, every frozen parameter it uses is cited to the register entry that owns it, and every composition placeholder it mentions is named as a placeholder and never as an input.
> Where this document and [the register](requirements-register.md) disagree, the register wins and this document is defective.

## How to read this

Main memory is two static latency classes under one placement discipline (R-15-247), and the second is oxide-semiconductor 2T0C decks stacked above the logic tier on the one die. R-15-247m measures that class's usable density, retention floor, and read, write, refresh and discharge constants on a **repaired megabit-class macro carrying complete tag, ECC, refresh, discharge, and routing overhead**, and admits no density figure as an architectural input ahead of that measurement. No commodity part supplies what the class needs, which the specification states in one sentence ([the memory subsystem](spec.md#r-15-247m)): monolithic integration above a logic die, a native 64+1-bit granule tag plane, SECDED on the data and DECTED on the tags at the frozen codeword width, wordline drivers sized for whole-bank assertion, and fixed-latency random access with no activate/precharge. So the macro is a custom program, and a custom program needs a stated architecture before anything can be measured against it.

This document is that statement. It decides the **shape** of the macro, which is the set of choices a measurement plan has to be written against: what a bank, a deck, a row and a page are here; where the tag bits and the check bits sit; which ports the discharge and the refresh reuse; what the completion indication is a read of; and which constants the controller sees. It decides **no value**: every density, latency, retention, current, energy, dwell and geometry figure is a measurand named in [section 5](#5-the-measurands) with the corner it is taken at and the item that owes it, and the composition's placeholder point is the one [the bank-count contract](bank-count-dse-contract.md) restates as an illustration and [the configuration](../model/config/verifiedos.json) declares behind a `qualified` flag that reads false; it is not repeated here.

Three documents sit beside this one and are not duplicated by it. [The bank-count contract](bank-count-dse-contract.md) states the search the per-class bank count is admitted through and the coefficients it waits on; this document defines three of those coefficients at the macro so that R5 can return them, and takes no candidate. [The block-geometry constraint](block-geometry-constraint.md) states the welded block size's constraint set and leaves its second-class axis empty until a row and a page are measured; this document gives that axis its vocabulary and no value, so the matrix stays as it is and its rows C7 and C8 stay owed to R5. [The alternatives register](architectural-alternatives.md) holds the device evidence and the three-construction reset analysis the adoption rests on; this document consumes none of that evidence as a figure and re-dates in [section 6](#6-dated-device-readings) the readings it relies on for shape.

## 1. What the five properties fix

One row per property, with the entry that owns it and the shape it forces on the macro. The shape column is this document's content; the entry column is where each obligation is normative.

| Property | Owning entries | What it fixes about the macro |
| --- | --- | --- |
| Monolithic integration above a logic die | R-17-063b, R-15-162, R-15-247n | The decks are back-end-of-line layers deposited above a finished logic tier on the one die, reached through on-die vias and no die-to-die link (R-15-176), and the cell is a two-transistor gain cell with no capacitor and no pFET, dynamic by mechanism. The stack is an axiom of the design and an offering of no foundry, so every area figure this macro would have is named against that assumption and none is stated here. |
| A native 64+1-bit granule tag plane | R-15-247a, R-15-203 | One validity tag per 64-bit granule, native to the class's own array, one plane per class, read and written in parallel with the data, with no sidecar in a foreign medium and no tag table. The plane is realized as columns of the same rows the data occupies, so a row access presents its tags with its payload in one operation. |
| SECDED on the data and DECTED on the tags at the frozen codeword | R-15-181a, R-15-175, R-15-178, R-15-178a | The array's unit is the codeword R-15-181a fixes: a 256-bit data payload with its SECDED check bits, and its tag bits, one per granule of the payload, under their own DECTED code, the two codes independent; the 128-bit payload with its own check counts is the fallback where a realized macro will not sense the wider unit in one access. Every row is a whole number of codewords and every access moves whole codewords. |
| Wordline drivers sized for whole-bank assertion | R-15-247e, R-15-247g | Every write wordline of a bank can be asserted at once against grounded write bitlines, so a bank's discharge is one assertion and the driver is sized for the whole bank rather than for one row. The bank is therefore the unit of discharge, of phase membership, and of the simultaneous-activation envelope. |
| Fixed-latency random access with no activate/precharge | R-15-247, R-15-164, R-15-184 | The read is non-destructive through the cell's own read transistor, so there is no row buffer, no open page, no restore, no precharge and no bank state machine: every access to any address of a bank completes in the same constant, and no mechanism on the memory path reads an access pattern. |

The five are stated in the specification as one sentence and are not five independent constraints: the tag plane and the codeword fix what a row holds, the whole-bank driver fixes what a bank is, and fixed latency fixes what the interface may not carry. Sections 2 to 4 are those three consequences in order.

## 2. The macro organisation

### 2.1 The hierarchy

Five levels, from the die inward. The names are the ones the register and [the block-geometry constraint](block-geometry-constraint.md) already use, so that a measured value lands on a symbol that exists.

| Level | What it is | What is fixed about it | What is measured about it |
| --- | --- | --- | --- |
| Deck | One back-end-of-line layer of cells with its own wordlines and bitlines, above the logic tier or above the deck below it | Decks are stacked monolithically on the one die (R-17-063b); a deck withdrawn bends capacity and returns no mechanism (R-15-173) | The deck count a realized stack reaches, and the feature size of a realized cell |
| Bank | The unit of island binding, of the discharge assertion and of the refresh and discharge phase schedule | Whole-bound to one island, never interleaved across an island boundary, never allocated, stolen, donated or resized at run time (R-15-247p); the per-class count is item (viii) of R-15-014a's second act and is searched by the bank-count contract | `I_bank_peak` and the rest of the envelope, on the bank as realized |
| Subarray | A set of rows sharing one sense-amplifier stripe and one write-driver stripe | Fixed at design; the unit the single-access sense width is a property of | The single-access sense width, which decides whether the 256-bit codeword or the 128-bit fallback is realized (R-15-181a) |
| Row | The cells of one subarray sharing one read wordline and one write wordline | A whole number of codewords, tag columns included; the unit of one refresh operation | The deck row width |
| Page | The codewords one row presents to the sense amplifiers in one access | A geometric quantity and never a timing state: with no activate and no precharge there is no open page and no page policy | The page size |

**A bank lies within one deck.** This is the one organisational choice the five properties leave open and this document takes, and it is taken for three reasons that are each a register obligation rather than a preference. The whole-bank assertion's instantaneous current and thermal coupling (R-15-247g) are then one deck's, so the envelope R5 characterizes on a bank is the envelope the schedule admits, with no cross-deck term to add later. Repair and yield are then bank-local to a deck, so the repaired macro R-15-247m names is repaired at the level the schedule addresses. And the fallback R-15-173 states, fewer decks rather than a different mechanism, then removes whole banks and leaves every surviving bank's constants unmoved, which is what keeps the four latency constants constants under a capacity shortfall. What it forfeits is stated with it: a bank cannot amortize its periphery across decks, so the per-bank periphery share is a deck's and the array-efficiency objective of the bank-count search pays for it. Whether the vias and the routing of a deck stack allow a bank of the needed size on one deck is a quantity R5 returns and this document does not assume.

### 2.2 What a row holds

A row is a whole number of codewords laid out so that each codeword's payload, its SECDED check bits, its tag bits and their DECTED check bits are adjacent columns of the same row. Three consequences follow, and each is a register obligation:

- **Tags travel with data.** Validity tags are native to each class's own array at granule alignment (R-15-247a), and here that means the tag columns are in the row, so a read presents the tags with the payload and a write commits both in one row operation, which is what makes data, tag validity and both ECC fields commit atomically at the granule on the second class exactly as on the first (R-15-247b). There is no second write timing for a second medium to be reconciled with.
- **The check travels with the word.** The macro stores and returns check bits as columns and neither generates nor verifies a code: the codeword's check is generated at the controller's read-modify-write stage and verified at the consumer (R-15-176, R-15-181), so the macro is check-transparent and re-encodes nothing at any hop. The stage that verifies the existing codeword before a sub-granule merge is the controller's and not the macro's, and the macro sees whole codewords only.
- **Adjacent cells belong to different codewords.** Physical bit interleaving (R-15-177) is realized in the column order of the row, so a multi-cell upset presents to each codeword as a separable single-bit error.

Spare rows and spare columns are provided per subarray, and the repair map that substitutes them is fixed at part qualification and read from no runtime state, so that a repaired address still completes in the same constant as an unrepaired one. The number of spares, the repair coverage and the usable density after repair are R5's, and the yield model that consumes them is the composition's (R-18-004b).

### 2.3 The two ports

A 2T0C cell has a write port and a read port, and the macro exposes exactly those two and no third:

- **The write port**: a write wordline that opens the cell's write transistor onto a write bitline, landing the bitline's level on the storage node. One row's write is one write wordline against the row's write bitlines. The write drivers are the ones sized for whole-bank assertion.
- **The read port**: a read wordline that enables the cell's read transistor, whose gate is the storage node, onto a read bitline sensed single-ended by the subarray's sense amplifier. The read leaves the storage node's charge where it was; there is no restore.

Discharge and refresh are operations over these two ports and add none. Discharge is the write port, asserted bank-wide against grounded write bitlines (R-15-247e). Refresh is the read port followed by the write port over one row, a read-and-rewrite of every cell of the row (R-17-058e names it as such). Nothing reaches a storage node by any other path: a dedicated per-cell bleed device is refused by R-15-247e on the ground that it is a second leakage contributor, and the macro provides none.

## 3. Refresh and discharge as the macro realizes them

### 3.1 Discharge

Discharge is realized through the cells' existing write devices: every write wordline in the bank asserted against grounded write bitlines, so that each storage node drains through its own write transistor (R-15-247e). At the macro that is one assertion per bank, driven from the sequencer's phase and reaching every row of every subarray of the bank at once; the storage node lands at the grounded level, which is the all-zeros codeword with cleared tags that R-15-182 and R-15-060 already fix as an untagged NULL granule. Both planes land together in the one assertion, so authority invalidation and residue sanitization are one pass and not two (R-15-247d), and no regeneration sweep is owed on the way back in (R-15-189j).

The unit is the bank because the bank is the unit that has a driver sized for it, and the schedule's unit is the phase: bank discharge and refresh phases are fixed and staggered by the composition-time schedule (R-15-247g), a phase being a composition-fixed set of banks asserted together. The macro presents a per-bank assert input and no finer one: a partial-bank discharge is not an operation the macro offers, which is what makes *no path admits a partially sanitized bank* a property of the interface rather than a promise about a sequence.

### 3.2 The completion indication

Discharge completion is a fixed worst-corner dwell followed by a single read of a fail-stop completion indication, with no poll-until-done loop, no retry, and no discharge-speed-dependent timing on either path (R-15-247f). The macro supplies the indication as follows:

- **What is read.** A witness set: a set of row positions fixed at composition, at least one per subarray of every bank in the phase, read through the ordinary read port after the dwell and compared against the landing state. The indication is positive where every witness reads the landing state and negative otherwise.
- **Why the set is fixed.** The witnesses are chosen at composition and depend on nothing observed, which is R-15-247r applied to the read: a witness set chosen by what the bank held, by temperature, or by a prior reading would make the indication a function of a runtime measure.
- **Why the dwell is the macro's worst corner.** The dwell is the time after which a witness's outcome is independent of what the cell held, at the hot corner and at end of life, over every cell of the bank. R5 characterizes that dwell and characterizes the witness as **dwell-invariant**, which is the claim that a witness reading the landing state after the dwell is evidence that every cell of its subarray did. The witness set's size and placement are therefore part of what R5 qualifies, and a macro whose witness cannot be made dwell-invariant is a part that does not qualify.
- **Where the reading lands.** The read is one per phase (R-15-247f) and the latch that holds it sits in the always-on root-of-trust domain, because the discharge is taken on the mode-exit path that collapses the rail the domain sits on (R-15-247q). The macro presents the indication on its interface to the sequencer; the latch is the sequencer's and not the macro's.
- **What a negative reading does.** It stops the transition (R-17-030n). The macro offers no re-assert on that path, so a retry is not a thing the interface can express.

### 3.3 Refresh

Refresh is the same slave's fixed share of each second-class bank's composition-time TDM schedule, taken on ON and RETAINED domains alike (R-15-247h, R-15-247k), at the cadence the hot-corner retention floor R-15-247m measures sets. At the macro one refresh operation is one row: the read port presents the row, the write port rewrites it, both planes and both check fields included because they are columns of the same row. The bank in its refresh slot is granted to no requester, exactly as a bank in another island's slot is, and the row pointer advances with the schedule's own slot counter and with nothing else (R-15-247r). The macro carries no refresh counter of its own and reads no temperature.

A refresh phase covers a composition-fixed set of banks and, within each, every row in turn inside the phase interval; the whole sweep over every bank of the class must complete inside the retention floor, which is the one thing a retention figure is consumed by (R-15-247c). The arithmetic of that comparison is [the bank-count contract](bank-count-dse-contract.md)'s and [the sequencer model](../model/model/sys/memory_sequencer.sail)'s, and neither figure in it is restated here. What the macro contributes is the row count per bank and the per-row refresh constant, both measurands, and the rows-per-phase-interval rate they imply is the cadence R5 qualifies against the floor.

Refresh and the ECC scrub share no engine: `cbo.scrub` is a kernel task issuing one instruction over ON domains at the accumulation cadence and restores no charge (R-15-177a); refresh restores charge and corrects nothing, the macro being check-transparent. The two postconditions [the alternatives register](architectural-alternatives.md) separates are therefore discharged by two mechanisms here rather than by one engine with two proofs, which is the shape R-15-247h fixes.

### 3.4 What the macro does not carry

No instruction is added for discharge, refresh, second-class tag maintenance, or class migration (R-15-247h; [the absence contract](absence-contract.md) A-17): the sequencer is a register slave whose window answers no requester, and the macro's discharge and refresh inputs are the slave's. No activation counter, alert or back-off exists on either class (R-15-184). No rail state, refresh cadence or discharge schedule is a function of any runtime measure (R-15-247r), so the macro has no temperature sensor on the refresh path and no occupancy input anywhere. The requesters held in reset across a discharge are those that can address the domain, read off the same map that fixes the island bindings (R-15-247h, R-15-228), and not the die.

## 4. The interface and timing contract

The controller sees a macro with the following properties, each a constant of the composition and none a property of the access:

- **Whole-codeword access at the frozen width.** No sub-granule write exists at the array (R-15-181): every read and every write moves one codeword with its check bits and tag bits. A sub-granule store is merged at the controller's fixed read-modify-write stage, with the existing codeword's check verified before the merge; the macro is never asked for less than a codeword.
- **Four latency constants and no fifth.** Read, write, refresh and discharge, each entering §11 as one constant per class (R-15-247, R-15-247m). A fetch is a read: with no cache there is no instruction path to amortize, so the fetch constant R-15-247j prices second-class code against is the read constant ([the class record](../model/model/core/memory_class.sail) carries it that way).
- **Address-, data- and history-independent latency.** No open-page state, no bank state machine, no repair-dependent path and no correction-dependent path, so the constant holds at every address of every bank regardless of what was accessed before. Correction, where it happens, is the controller's and is itself a fixed-latency term (R-15-179).
- **The check travels with the word** across the macro boundary, the interconnect and the controller and is verified at the consumer (R-15-176). A detected-but-uncorrectable codeword in either plane is a fail-stop sentinel event and never a returned value (R-15-179).
- **Bank whole-binding.** A bank is granted to one island and no address interleaving crosses an island boundary (R-15-247p); the bank/macro/tier-to-island map is an input to the memory plan and never its output (R-15-228a). The macro offers no bank scheduler, an island's ceiling being fixed by the TDM schedule and the binding (R-15-050).
- **Maintenance windows are not requester windows.** A bank in its refresh slot is granted to no requester; a RETAINED domain is maintenance-accessible and requester-inaccessible, and an access decoding to it is a fail-stop sentinel event and never a stall or a demand power-up (R-15-247k, R-15-189h).
- **The dense map.** Every second-class region sits inside the 36-bit physical space with the rest of main memory and every aperture (R-15-002b), and the macro's address decode is bank, then subarray, then row, then codeword column, with nothing decided by the value stored anywhere.

## 5. The measurands

Per-class usable density, the retention floor, and the read, write, refresh, and discharge latency constants are what R-15-247m measures; this table is one row per quantity R5 returns, each defined at the macro level so that the measurement lands on a symbol this document and its neighbours already use. The **owed to** column names the item and the entry the value enters; the **status** column carries `pending` for every row, and a row that acquired a value while the class's `qualified` flag reads false would be a defect in this document rather than progress. No value cell exists in this table on purpose.

The corner is R-15-247m's for every row it names: the hot corner is the junction temperature at which R-15-193's thermal trip fires, and end of life is after the bias-stress drift the declared service life accumulates, the qualification stating both beside the figure.

| Symbol | Macro-level definition | Measured on | Corner | Owed to | Status |
| --- | --- | --- | --- | --- | --- |
| `rho_usable` | usable bits per unit area after tag columns, both check fields, spares, repair, sense and driver stripes, sequencer inputs and bank routing are counted | the repaired macro, whole | as realized, after repair | R5, R-15-247m | pending |
| `t_read` | one whole-codeword read through the read port, check and tag columns included, from address presented to codeword returned | one bank, every address class | hot corner, end of life | R5, R-15-247m, R-17-041 | pending |
| `t_write` | one whole-codeword write through the write port, both planes committed | the same | the same | R5, R-15-247m, R-17-041 | pending |
| `t_refresh` | one row's read-and-rewrite through both ports | one row of one bank | the same | R5, R-15-247m | pending |
| `t_discharge` | the fixed worst-corner dwell after a whole-bank assertion, after which every witness is dwell-invariant | one phase's bank set, asserted together | hot corner, end of life, over the largest phase | R5, R-15-247f, R-15-247g | pending |
| `T_ret_floor` | the shortest interval after a write at which every cell of the macro still reads its written value, at the corner | the repaired macro, whole | hot corner, end of life | R5, R-15-247m, R-15-247c | pending |
| `T_ret_ceiling` | the longest interval at which any cell still reads its written value, at the cold corner | the same | cold corner | R5, R-15-247m, R-17-058f | pending |
| `w_row` | cells per row of one subarray on one deck, tag and check columns included: the deck row width | one subarray | as realized | R5, [the block-geometry constraint](block-geometry-constraint.md) C8 | pending |
| `w_page` | codewords one row presents to the sense amplifiers in one access: the page size | one subarray | as realized | R5, C8 | pending |
| `w_sense` | bits sensed in one fixed-latency access, deciding whether the codeword R-15-181a fixes or its fallback is realized | one subarray | hot corner | R5, R-15-181a, C9 | pending |
| `n_rows_bank` | rows per bank, over its subarrays, spares excluded | one bank | as realized | R5, [the bank-count contract](bank-count-dse-contract.md) | pending |
| `I_bank_peak` | peak current of one bank's whole-bank write assertion, and of one row's refresh, each stated | one bank | hot corner | R5, [the bank-count contract](bank-count-dse-contract.md) | pending |
| `I_pdn_max` | the delivery network's simultaneous-on ceiling at the macro's rail | the macro's rail as provisioned | hot corner | R-15-189i's provisioning, R5 | pending |
| `C_bl_per_row` | read bitline capacitance per row, which sets read energy per bit | one subarray | as realized | R5, [the bank-count contract](bank-count-dse-contract.md) | pending |
| `theta_couple` | temperature rise in a bank's neighbours per simultaneous assertion of a phase's bank set | one phase's bank set and its neighbours | hot corner | R5, R-15-247g | pending |
| `N_endure` | write cycles, refresh rewrites counted, before any cell of the bank fails the retention floor | one bank | hot corner | R5, R-15-247m | pending |
| `sigma_disturb` | the disturb characterization: the change in a neighbouring cell's stored level per read, per write and per whole-bank assertion, across decks | the stacked array | hot corner | R5, R-15-184 | pending |
| `dV_th` | threshold-voltage drift of the read and write transistors under the composed bias profile over the declared life | the repaired macro | end of life | R5, R-15-247m | pending |
| `V_rail_retained` | the lowest rail at which a refresh write still commits with margin, which sets the RETAINED rail | one bank | hot corner, end of life | R5, R-15-247k | pending |
| `P_refresh` | refresh power at capacity at the cadence the floor sets | the repaired macro, scaled by the composition | hot corner | R5, R-15-247m, R-18-004c | pending |
| `Q_witness` | the witness set's size and placement per bank at which `t_discharge` is dwell-invariant | one bank | hot corner, end of life | R5, R-15-247f | pending |
| `n_spare`, `f_repair` | spare rows and columns per subarray, and the repair coverage the macro carries | the repaired macro | as realized | R5, R-18-004b | pending |

Two consequences of the table are the point of it. **Every row of R5's package has a definition here**: the usable density is `rho_usable`; the four constants are `t_read`, `t_write`, `t_refresh`, `t_discharge`; the retention corner is the interval `T_ret_floor` to `T_ret_ceiling`; the bank-granularity discharge with its worst-corner dwell and dwell-invariant fail-stop indication is `t_discharge` with `Q_witness`; and the simultaneous-activation envelope is `I_bank_peak`, `I_pdn_max`, `theta_couple` and `N_endure` at the bank granularity. **Every one of the seven qualification triggers the alternatives register collects at R-15-247m lands on a row**: usable density, fixed latency across the corner, disturb, drift, the separate scrub-coverage and refresh-deadline postconditions (the deadline is `T_ret_floor` against the sweep, the scrub is `cbo.scrub`'s and not the macro's), the staggered current envelope, and the reset sequence across a short power interruption inside the measured window (`t_discharge` and `Q_witness` taken with `T_ret_ceiling` as the width of the window).

Two symbols of the bank-count contract's table are not here, `W_bank` and `s_island`, because neither is a property of the macro: the per-bank transfer width is the class parameterization's and the slot share is the schedule's. `split_cycle_critical` is a reading of the roster and is likewise not the macro's.

## 6. Dated device readings

R-18-001a makes every maturity claim a reading with a date, taken from the upstream's own page and never inherited from the reading before it. Each reading below carries the page it is taken from and the date it is taken on, and each establishes a **shape** fact this document relies on and no figure this document consumes. None of them is the megabit-class repaired macro R-15-247m names, none carries repair, ECC or a tag plane, and every retention figure a page states is at that page's own corner, room temperature and time zero, which R-15-247m says is not the floor and decides nothing; that is why the table records what each reading shows and not what it measures.

| Reading | Page read | What it establishes for this document | Read on |
| --- | --- | --- | --- |
| imec, first functional 2T0C IGZO DRAM cell at IEDM 2020 | [imec press release](https://www.imec-int.com/en/press/imec-demonstrates-capacitor-less-igzo-based-dram-cell-400s-retention-time) | The cell is two IGZO thin-film transistors and no storage capacitor, fabricated on 300 mm wafers; the page states a retention above four hundred seconds and names no array size | 2026-09-05 |
| imec, 2T0C IGZO DRAM cell at IEDM 2021 | [imec article](https://www.imec-int.com/en/articles/capacitor-less-igzo-based-dram-cell-excellent-retention-endurance-and-gate-length-scaling) | Endurance the page calls unlimited at more than ten to the eleventh cycles, so a refresh that rewrites every cell on a fixed cadence is not endurance-limited at the cell on the page's own statement; a gate length the page states as scalable to 14 nm, with a retention above one hundred seconds stated at that length; no array size named | 2026-09-05 |
| imec, capacitor-less IGZO DRAM roadmap article | [imec article](https://www.imec-int.com/en/articles/disrupting-dram-roadmap-capacitor-less-igzo-dram-technology) | The storage element is the read transistor's own gate node, which is the non-destructive read [section 1](#1-what-the-five-properties-fix)'s fifth property rests on; the page states a retention beyond 4.5 hours at room temperature with the off current it rests on, a write below 10 ns, and 2D and 3D stacking as architectures, and names no cell count; page dated 2025-03-25 | 2026-09-05 |
| Kioxia, OCTRAM at IEDM 2024 | [Kioxia technology topic](https://www.kioxia.com/en-jp/rd/technology/topics/topics-77.html) | OCTRAM is an InGaZnO vertical transistor integrated on top of a capacitor, capacitor-first, at a 4F² architecture with an off current the page states below one attoampere; it is the oxide access transistor for a capacitor cell and not a gain cell, so the commodity roadmap de-risks the channel and the stack and not the cell this class uses | 2026-09-05 |
| Kioxia, 3D OCTRAM at IEDM 2025 | [Kioxia news](https://www.kioxia.com/en-jp/about/news/2025/20251212-1.html) | An eight-layer stack of horizontal oxide-semiconductor channel transistors formed by stacking silicon-oxide and silicon-nitride films and replacing the nitride with InGaZnO, with the operation of transistors in all eight layers verified; the page does not use the word capacitor, and states transistor operation rather than a memory array | 2026-09-05 |

**Readings this document does not carry.** The alternatives register also cites the IEDM 2022 dual-gate cell, the IEDM 2023 stacked two-layer vertical channel-all-around bit-cell, the Science Advances 2025 monolithic multi-deck array, the VLSI 2023 monolithic 3D DRAM over silicon CMOS, and the review article at nature.com. Each of those pages refused an unauthenticated read on 2026-09-05, so none is re-taken here, and no figure from any of them, the largest published 2T0C array count included, is stated in this document; the milestone that spends those readings is R5, which re-takes them under R-18-001a at that time.

What the five readings establish together is narrow and is all this document needs: the device family has the two-port, capacitor-free, non-destructive-read cell that section 2 organizes, its channel and its stacking flow are what the commodity roadmap funds, and nothing on any of the five pages is an array with repair, ECC or a tag plane at any scale. The gap between that and the macro R-15-247m names is R5's to close by measurement and this document's to make measurable.

## 7. What makes a statement of this architecture inadmissible

| Id | The refusal |
| --- | --- |
| MA-1 | a density, latency, retention, current, energy or dwell figure stated as a fact of the macro while the class's `qualified` flag reads false, which is R-15-247m's own gate |
| MA-2 | a deck row width, page size or single-access sense width fed into [the block-geometry constraint](block-geometry-constraint.md)'s matrix or into [the bank-count instrument](../tools/quarantine/bank-dse.py) while that flag reads false, which is BG-3 and BD-3 applied at their source |
| MA-3 | a per-class bank count or a welded block size named, both being items of R-15-014a's closed second act, so that naming either here is an amendment that reruns the review gate under R-18-034 |
| MA-4 | a dedicated per-cell bleed device, or any third path to a storage node beside the two ports (R-15-247e) |
| MA-5 | a tag plane tuned to decay faster than its data, or any guarantee resting on a decay rate or a retention upper bound (R-15-247c) |
| MA-6 | a poll-until-done loop, a retry, or a completion timing that depends on discharge speed on either path (R-15-247f) |
| MA-7 | a completion indication read per bank or per transition rather than per phase, or a witness set chosen from anything observed (R-15-247f, R-15-247r) |
| MA-8 | a die-wide reset hold, where the hold is scoped to the requesters that can address the domain (R-15-247h) |
| MA-9 | more than one bit per cell (the alternatives register's refusal), or an in-macro correction that re-encodes the check at a hop (R-15-176) |
| MA-10 | a disturb-immunity or side-channel-silence claim, both being device properties R5 measures and the register claims nowhere (R-15-184, R-17-058e) |
| MA-11 | a figure stated as if a foundry supplied the stack (R-17-063b), or a maturity claim carried without the page and the date it was read on (R-18-001a) |
| MA-12 | a refresh cadence, discharge schedule or rail state made a function of temperature, occupancy, access counts or any other runtime measure (R-15-247r) |

## 8. What this document is not

It is not R5's evidence: it defines what R5 measures and returns none of it. It is not the per-class bank count, which R-15-247p admits and [its instrument](bank-count-dse-contract.md) searches; it defines three of that search's coefficients at the macro and takes no candidate. It is not the welded block size, which is item (vii) of R-15-014a and whose second-class axis [its constraint](block-geometry-constraint.md) leaves empty until R5 measures a row and a page; it gives that axis its vocabulary and no value. It is not the memory-topology comparison, which the plan places at Q6 with the address-growth act that item raises, and it compares this class with nothing. It is not a register act: no entry states what a macro architecture specification must contain, and this document is written against R-15-247m's measurement obligation and the specification's one sentence rather than against an entry stating its own content, which is a gap reported at its landing and not closed here.
