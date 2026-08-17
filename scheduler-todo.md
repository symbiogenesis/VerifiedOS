# Scheduler TODO

*Non-normative. The work list distilled from a reading of the OS-kernel scheduling literature against [§7.7](requirements-register.md), [§11](verification-maximal-os.md#r-11-006), and [§17.2](requirements-register.md) as they stand. Where this document and [requirements-register.md](requirements-register.md) disagree, **the register wins and this document is defective**. Nothing here amends the schedule model: this is the agenda a review of it works through, not a set of decisions already taken.*

*Every item carries the requirements that govern it and the place in [verification-maximal-os.md](verification-maximal-os.md) where the change lands. Items are ordered by class, not by size: one clause that closes a named hole outranks a design question that would take a quarter to settle.*

**Convention.** When an item lands normatively, delete the bullet and its row in the landing table. No departure notes, no strikethroughs: git history is the narrative.

---

## The classes

| Class | Meaning | Count |
| --- | --- | --- |
| **§0 The mechanism** | Why the list does not collapse into "adopt a conventional scheduler". | 0 |
| **§1 Defects** | A quantity the register claims to bound and does not. | 0 |
| **§2 Corrections** | Arguments that need restating; the conclusions stand. | 0 |
| **§3 Statements** | Clauses the schedule model should add because something it depends on is inferable rather than stated. | 0 |
| **§4 Decisions** | Genuine open questions. | 0 |
| **§5 Records** | Two free confirmations, recorded so a later reader does not mistake either for drift. | 2 |
| **§6 Watch** | External lines with no obligation attached, tracked because each aims at what §0 settles. | 2 |

---

## 0. Why this is a list and not a different scheduler

*The first question at any review of the schedule model is whether the whole list collapses into "the real-time literature settled this against cyclic executives in 1992, so adopt fixed-priority or a reservation server." It does not, and the reason is worth writing down once rather than re-deriving.*

**The received conclusion is real and is about a different objective.** Locke's *Cyclic executives vs. fixed priority executives* (Real-Time Systems 4(1), 1992) concludes that fixed priority under rate-monotonic assignment generally dominates the cyclic executive, and the multi-core cyclic-executive line that followed still reports the two costs he named: strongly NP-hard schedule construction, and idle time when execution times vary. Both costs land here in full: construction is the [R-11-015b](verification-maximal-os.md#r-11-015b) search duty, and the idle time is the §17.2 population wall, whose division [R-07-037b](verification-maximal-os.md#r-07-037b) stops at the label boundary and no finer. **What that literature does not weigh is the timing channel**, because it is not measuring one.

**On the objective this platform states, the mechanism class is forced, and there is a proof of it.** Ge, Yarom, Chothia and Heiser (*Time Protection*, EuroSys 2019) separate two channels a shared scheduler exposes: **online time**, what a domain observes of its own uninterrupted execution, and **offline time**, the gap between its executions. Partitioning and flushing (the `fence.t` lineage the profile already adopts, later mechanized by Buckley, Sison, Wistoff, Millar, Murray, Klein and Heiser) closes the online half and leaves the offline half open. Only a schedule whose instants are independent of every domain's behaviour closes the offline half, which is exactly what [R-07-032](verification-maximal-os.md#r-07-032) and [R-07-036](verification-maximal-os.md#r-07-036) are. Gong and Kiyavash close the other direction information-theoretically: leakage is unavoidable within the deterministic *work-conserving* class, where work-conserving TDMA is privacy-optimal and still leaks. **Elimination requires surrendering work conservation**, so [R-07-036](verification-maximal-os.md#r-07-036) is a consequence rather than a preference, and [R-17-006](verification-maximal-os.md#r-17-006)'s refusal to add a donation mechanism later is the same statement seen from the cost side.

**The proof-cost half is measured, not asserted.** Connecting Prosa's mechanized response-time analysis to RT-CertiKOS (single-core, sequential, fixed-priority) took roughly 4,100 lines of Rocq for the connection alone, 1,900 of them interface translation (Liu et al., CAV 2019). seL4's MCS branch, the mechanism [R-07-035](verification-maximal-os.md#r-07-035) deletes, reached functional correctness on RISC-V in June 2026, roughly eight years after the mechanism was published, and its integrity and confidentiality proofs are outstanding still. An interval-arithmetic check over a harmonic task set ([R-11-006](verification-maximal-os.md#r-11-006)) is close to the cheapest schedulability obligation on offer, and on an objective that treats trust as the scarce resource that is the whole argument.

**So the list is by construction the residue the mechanism choice does not reach.** Every item below leaves [R-07-032](verification-maximal-os.md#r-07-032), [R-07-036](verification-maximal-os.md#r-07-036), and [R-07-038](verification-maximal-os.md#r-07-038) exactly as they are, and none spends trust.

---

## 1. Defects

*None. The class is a quantity the register claims to bound and does not: a finding, never a preference.*

---

## 2. Corrections

*None. In particular, [R-11-022](verification-maximal-os.md#r-11-022)'s claim survives inspection: with the discretionary band subdivided rather than the frame lengthened, a focus compartment is visited once per major frame at every rung, so interactive latency genuinely does not divide by* n *even though aggregate share does. The constant it does not divide is the focus visit period, which [R-11-022a](verification-maximal-os.md#r-11-022a) sizes against input-event cadence.*

---

## 3. Statements to add

*None. The class is a clause the schedule model should add because something it depends on is inferable rather than stated, and silence about a load-bearing dependency is not neutral.*

---

## 4. Decisions

*None. The class is a genuine open question; the boundary question the last cluster asked is answered normatively at [R-07-037b](verification-maximal-os.md#r-07-037b) and [R-11-006b](verification-maximal-os.md#r-11-006b), with the declined stronger forms recorded in [architectural-alternatives.md](architectural-alternatives.md).*

---

## 5. Records

### 5B. Free confirmations to collect

- [ ] **The literature contains the impossibility result that [R-07-036](verification-maximal-os.md#r-07-036) currently argues from first principles.** *[R-07-036](verification-maximal-os.md#r-07-036), [R-17-006](verification-maximal-os.md#r-17-006) · §7.7, §17.2.*
  Gong and Kiyavash quantify leakage through deterministic work-conserving schedulers and show it is unavoidable within that class, work-conserving TDMA being privacy-optimal and still leaking. The requirement's rationale, that donated time is a timing channel, is presently stated as a design judgement. It is a published result, and citing it converts a judgement into a confirmation at the cost of one clause.
- [ ] **The online/offline-time split names what [R-07-036](verification-maximal-os.md#r-07-036) buys that flushing alone does not.** *[R-07-036](verification-maximal-os.md#r-07-036), [R-07-040](verification-maximal-os.md#r-07-040) · §7.7.*
  Time protection's two channels are separable: `fence.t` and eager zeroize close the online half, and only a behaviour-independent schedule closes the offline half. The model does both and nowhere says so, which understates it: a reader who knows the time-protection line will otherwise read the switch cost as buying what flushing already bought.

---

## 6. Watch

*No obligation attached. Each aims at what §0 settles, so a movement on either would rerun that argument rather than open an item here.*

- [ ] **The time-protection proof line.** Buckley, Sison, Wistoff, Millar, Murray, Klein and Heiser mechanize time protection against seL4. It is the nearest external work to this model's own obligation, and its residuals are the ones §17.2 should expect to inherit.
- [ ] **Any published work-conserving scheduler carrying an offline-time leakage proof.** This is the one result that would reopen §0 and with it the whole reservation-based family. Gong and Kiyavash argue it cannot exist for deterministic schedulers, but their model is a shared queueing server rather than a partitioned CPU, so the impossibility is narrower than a casual reading makes it.

---

## Where the work lands

*Several items collapse into one edit. This is the grouping to work in, not the order above.*

| Section | Items | Class |
| --- | --- | --- |
| §7.7 Scheduling | both confirmations | 5B |
