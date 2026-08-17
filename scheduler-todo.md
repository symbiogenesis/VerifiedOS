# Scheduler TODO

*Non-normative. The work list distilled from a reading of the OS-kernel scheduling literature against [§7.7](requirements-register.md), [§11](verification-maximal-os.md#r-11-006), and [§17.2](requirements-register.md) as they stand. Where this document and [requirements-register.md](requirements-register.md) disagree, **the register wins and this document is defective**. Nothing here amends the schedule model: this is the agenda a review of it works through, not a set of decisions already taken.*

*Every item carries the requirements that govern it and the place in [verification-maximal-os.md](verification-maximal-os.md) where the change lands. Items are ordered by class, not by size: one clause that closes a named hole outranks a design question that would take a quarter to settle.*

**Convention.** When an item lands normatively, delete the bullet and its row in the landing table. No departure notes, no strikethroughs: git history is the narrative.

---

## The classes

| Class | Meaning | Count |
| --- | --- | --- |
| **§0 The mechanism** | Why the list does not collapse into "adopt a conventional scheduler". | 0 |
| **§1 Defects** | A quantity the register claims to bound and does not. | 1 |
| **§2 Corrections** | Arguments that need restating; the conclusions stand. | 0 |
| **§3 Statements** | Clauses the schedule model should add because something it depends on is inferable rather than stated. | 4 |
| **§4 Decisions** | Genuine open questions. One cluster, two questions that stand or fall together. | 1 in 1 cluster |
| **§5 Records** | A deliberate divergence and two free confirmations, recorded so a later reader does not mistake either for drift. | 1 + 2 |
| **§6 Watch** | External lines with no obligation attached, tracked because each aims at what §0 settles. | 3 |

---

## 0. Why this is a list and not a different scheduler

*The first question at any review of the schedule model is whether the whole list collapses into "the real-time literature settled this against cyclic executives in 1992, so adopt fixed-priority or a reservation server." It does not, and the reason is worth writing down once rather than re-deriving.*

**The received conclusion is real and is about a different objective.** Locke's *Cyclic executives vs. fixed priority executives* (Real-Time Systems 4(1), 1992) concludes that fixed priority under rate-monotonic assignment generally dominates the cyclic executive, and the multi-core cyclic-executive line that followed still reports the two costs he named: strongly NP-hard schedule construction, and idle time when execution times vary. Both costs land here in full, and §4 and §17.2 are where they are booked. **What that literature does not weigh is the timing channel**, because it is not measuring one.

**On the objective this platform states, the mechanism class is forced, and there is a proof of it.** Ge, Yarom, Chothia and Heiser (*Time Protection*, EuroSys 2019) separate two channels a shared scheduler exposes: **online time**, what a domain observes of its own uninterrupted execution, and **offline time**, the gap between its executions. Partitioning and flushing (the `fence.t` lineage the profile already adopts, later mechanized by Buckley, Sison, Wistoff, Millar, Murray, Klein and Heiser) closes the online half and leaves the offline half open. Only a schedule whose instants are independent of every domain's behaviour closes the offline half, which is exactly what [R-07-032](verification-maximal-os.md#r-07-032) and [R-07-036](verification-maximal-os.md#r-07-036) are. Gong and Kiyavash close the other direction information-theoretically: leakage is unavoidable within the deterministic *work-conserving* class, where work-conserving TDMA is privacy-optimal and still leaks. **Elimination requires surrendering work conservation**, so [R-07-036](verification-maximal-os.md#r-07-036) is a consequence rather than a preference, and [R-17-006](verification-maximal-os.md#r-17-006)'s refusal to add a donation mechanism later is the same statement seen from the cost side.

**The proof-cost half is measured, not asserted.** Connecting Prosa's mechanized response-time analysis to RT-CertiKOS (single-core, sequential, fixed-priority) took roughly 4,100 lines of Rocq for the connection alone, 1,900 of them interface translation (Liu et al., CAV 2019). seL4's MCS branch, the mechanism [R-07-035](verification-maximal-os.md#r-07-035) deletes, remains under active verification years after it shipped. An interval-arithmetic check over a harmonic task set ([R-11-006](verification-maximal-os.md#r-11-006)) is close to the cheapest schedulability obligation on offer, and on an objective that treats trust as the scarce resource that is the whole argument.

**So the list is by construction the residue the mechanism choice does not reach.** Every item below leaves [R-07-032](verification-maximal-os.md#r-07-032), [R-07-036](verification-maximal-os.md#r-07-036), and [R-07-038](verification-maximal-os.md#r-07-038) exactly as they are. Three of the five spend no trust at all; the fourth (§4) is the one that would, and it is stated as a question rather than a proposal for that reason.

---

## 1. Defects

*The register claims to bound a quantity and does not. This is not a preference.*

- [ ] **The phase relation between per-core frames is unbound, so cross-core response time has no derivation.** *[R-11-014](verification-maximal-os.md#r-11-014), [R-07-042](verification-maximal-os.md#r-07-042), [R-11-006](verification-maximal-os.md#r-11-006) · lands in §11.*
  [R-11-014](verification-maximal-os.md#r-11-014) reduces the heterogeneous-multiprocessor problem to independent per-core uniprocessor analyses, which is sound for *schedulability*: each core's slot WCETs fit its own major frame whatever the neighbouring core is doing. It is not sufficient for *latency*. Slot widths and offsets are fixed per core; **the offset of one core's frame against another's is named nowhere**, so a request crossing a core boundary waits for the callee partition's next slot: worst case a full major frame per hop, and a client → server → driver chain multiplies it. Nothing in §11 admits that quantity, and [R-07-042](verification-maximal-os.md#r-07-042) states that worst-case service latency is a schedule corollary **without exception**, which under an unbound phase has exactly one.
  **This is not the NoC question already treated.** [performance-recovery-todo.md](performance-recovery-todo.md) sizes ring windows so a logical exchange lands inside one TDM slot and batches IPI round-trips at the source; that governs when the *message* moves. This governs when the *peer partition next runs to consume it*, which is a partition-schedule parameter and a different term.
  **The fix costs nothing on the scarce axis.** Frame offsets are static, public, composition-fixed constants exactly as widths are, so no channel opens and no runtime decision appears; [R-11-023](verification-maximal-os.md#r-11-023) already records that the interval arithmetic quantifies over widths **and offsets**, so the admission machinery reads the parameter it needs today. What is missing is that anything *binds* it, and that the synthesis pass has a cross-core chain-latency objective to bind it against. The same clause covers data-parallel work spanning several V-class cores, which serializes across unaligned wheels for the same reason and by the same amount.

---

## 2. Corrections

*None. In particular, [R-11-022](verification-maximal-os.md#r-11-022)'s claim survives inspection: with the discretionary band subdivided rather than the frame lengthened, a focus compartment is visited once per major frame at every rung, so interactive latency genuinely does not divide by* n *even though aggregate share does. What no requirement fixes is the constant it does not divide, which is [§3](#3-statements-to-add) below and not a correction to this one.*

---

## 3. Statements to add

*Each is one or two clauses. Each is needed because something the model already depends on is inferable rather than stated, and silence about a load-bearing dependency is not neutral.*

- [ ] **The discretionary frame period is sized against input-event cadence, and the resulting input-to-response bound is admitted.** *[R-11-008](verification-maximal-os.md#r-11-008), [R-11-022](verification-maximal-os.md#r-11-022) · lands in §11.*
  [R-11-008](verification-maximal-os.md#r-11-008) sizes every *device's* poll cadence or sporadic slot to its deadline and admits the result. The discretionary band has no equivalent: its period falls out of composition rather than being sized against the deadline that governs it, which for the focus compartment is a human-perceptual one set by touch sampling and display refresh. The quantity that decides whether the machine feels responsive is therefore the one quantity in §11 that no requirement bounds. State it the way device latency is stated, and the useful corollary follows for free: two shorter focus slots per frame halve focus latency at identical share, which is a schedule-shape choice admission can make once it is written down as a choice.
- [ ] **Harmonization is a composition-tool duty that reports the capacity it spends.** *[R-11-006](verification-maximal-os.md#r-11-006), [R-11-015a](verification-maximal-os.md#r-11-015a) · lands in §11.*
  [R-11-006](verification-maximal-os.md#r-11-006) requires each task's period to be harmonic with the major frame, stated as a property the admitted task set *has*. Real cadences do not have it: display refresh, radio frame timings, touch sampling and audio buffer periods are not mutually harmonic, so something must make them so, and the only two instruments are period distortion (running a task faster than its deadline needs, which spends capacity) and hyperperiod growth (which spends frame length). Optimal harmonic period assignment is itself NP-hard with known approximation algorithms, so this is tool work, not authoring guidance. **The clause to add is that the tool owns it and declares the cost**, because [R-11-015a](verification-maximal-os.md#r-11-015a) already makes frame capacity a quantity the toolchain chooses rather than merely reports, and harmonization spends it silently today.
- [ ] **The intra-compartment concurrency model is run-to-completion over syntactic poll sites, and is stated rather than inferred.** *[R-07-039](verification-maximal-os.md#r-07-039), [R-07-043](verification-maximal-os.md#r-07-043) · lands in §7.7.*
  The model deletes the second scheduling level that ARINC 653 keeps and does not say what stands in its place. The rest of the design answers the question, since [R-07-043](verification-maximal-os.md#r-07-043) loses the preemption term precisely *because* the remaining trap points are syntactic poll sites already in the typed control-flow graph, which presumes a compartment structured as a cooperative reaction rather than as blocking threads; but the answer is load-bearing and unstated. It constrains every server and application author (no blocking call, no internal thread, cooperative structure throughout), and an author cannot conform to a rule that is only a consequence of someone else's WCET argument.
- [ ] **Static schedule synthesis is a composition-tool duty, not an optional lever.** *[R-15-110](verification-maximal-os.md#r-15-110), [R-18-014c](verification-maximal-os.md#r-18-014c), [R-11-015a](verification-maximal-os.md#r-11-015a) · lands in §11 or §18; delete the corresponding `[U]` item and its table row from [performance-recovery-todo.md](performance-recovery-todo.md) when it does.*
  Frame construction is strongly NP-hard, and the cyclic-executive literature from Baker and Shaw onward treats packing quality as the thing that decides whether a task set fits at all. Utilization loss is this model's headline cost, and better packing is the only lever that attacks it while changing no mechanism, no boundary, and no theorem. **The synthesizer spends no trust:** its output is validated by the interval-arithmetic admission check, the same untrusted-evidence-producing-machinery shape [R-15-110](verification-maximal-os.md#r-15-110) already applies to the design-space explorer, where a poor proxy costs search quality and never soundness. On an objective where engineering effort is free and trust is scarce, an *optional* marker on a zero-trust lever against the headline cost is the one place the schedule model's bookkeeping disagrees with the platform's own cost model.

---

## 4. Decisions

*One cluster. Both questions rest on the same claim about where the boundary that matters actually is, so they are answered together or not at all.*

### 4A. The decomposition tax: is the slot per compartment, or per confidentiality label?

**The observation.** A compartment receives a fixed-table slot or a whole core at composition, and [R-11-021](verification-maximal-os.md#r-11-021) sets the discretionary ladder at 4 / 8 / 16 / 32 slots per C-class core. Decomposing one application into *n* least-authority compartments therefore spends *n* slots against a ceiling as low as four, each at roughly 1/*n* of the discretionary band. **The mechanism prices the practice the rest of the design is built on**, and the incentive it creates runs toward coarser compartments.

**Where the register already answers, and where it stops.** [R-17-004](verification-maximal-os.md#r-17-004) through [R-17-008](verification-maximal-os.md#r-17-008) book the population wall for the *browser* case honestly and in numbers, and there the division is genuinely forced: per-origin isolation makes each tab its own confidentiality class, so no slack may cross between them and no mechanism could recover the difference. What §17.2 does not treat is several compartments **inside one confidentiality label**, where the division is not forced by the flow policy at all and is charged anyway.

**The claim the decision turns on.** The boundary the timing channel cares about is the **label** boundary, not the compartment boundary. Compartments sharing a label are mutually distrusting for *authority*, which is what CHERI and the manifest enforce, and not for *timing secrecy*, because a flow between them is permitted by the lattice by definition. If that holds, then giving such a group one slot subdivided by a second-level budgeted scheme leaks nothing across any label boundary: every decision the inner level makes is a function of state inside one label, and [R-07-036](verification-maximal-os.md#r-07-036)'s prohibition, which is written *across confidentiality boundaries* and not universally, is untouched. [R-17-006](verification-maximal-os.md#r-17-006) currently hardens it to a universal refusal, and that hardening is the sentence the decision would have to revisit.

**The two questions.**
1. **Second-level scheduling inside a slot.** Shin and Lee's periodic resource model gives the exact schedulability condition for scheduling a component set inside a budget, so the outer check of [R-11-006](verification-maximal-os.md#r-11-006) is untouched and the inner obligation is a known one. A CBS-style budget at the inner level keeps one compartment from starving a sibling, so least authority survives as an availability property and not only as an authority one.
2. **Intra-label slack reclamation.** The same boundary argument licenses returning an idle inner budget to a sibling under the same label, which is what GRUB does inside `SCHED_DEADLINE` and what QNX's adaptive partitioning ships industrially. Its value is exactly the case in (1) and close to nil for the browser, so it is not a route around the population wall and must not be argued as one.

**What it costs, stated rather than absorbed.** A second scheduling level is proof surface, and it is where the six information-leakage flaws that the Isabelle/HOL work found in ARINC 653 and in VxWorks 653, XtratuM and POK actually lived. That history is a real argument for the current answer and is why this is a decision rather than a statement. Against it: the current answer sets a hard ceiling of four to thirty-two compartments per core on a machine whose thesis is fine-grained compartmentalization, and [R-11-026](verification-maximal-os.md#r-11-026) makes that ceiling absolute by design. **Both horns are expensive; neither is obviously right; the register currently takes one without recording that the other was available.**

---

## 5. Records

### 5A. A deliberate divergence, so a later reader does not read it as drift

- [ ] **The second scheduling level is deleted, where every separation kernel in the field keeps it.** *[R-07-032](verification-maximal-os.md#r-07-032), [R-07-043](verification-maximal-os.md#r-07-043) · §7.7.*
  ARINC 653 pairs a static major-frame partition window schedule with priority-preemptive processes *inside* each window, and PikeOS, VxWorks 653 and the static-partitioning hypervisor line all follow it. This model keeps the first level and deletes the second. Record the ground with the divergence: that inner level is where the found leaks were, and deleting it is what lets [R-07-043](verification-maximal-os.md#r-07-043) lose the preemption term rather than bound it. §4A is the question of whether the deletion is drawn at the right boundary; the divergence itself is deliberate either way.

### 5B. Free confirmations to collect

- [ ] **The literature contains the impossibility result that [R-07-036](verification-maximal-os.md#r-07-036) currently argues from first principles.** *[R-07-036](verification-maximal-os.md#r-07-036), [R-17-006](verification-maximal-os.md#r-17-006) · §7.7, §17.2.*
  Gong and Kiyavash quantify leakage through deterministic work-conserving schedulers and show it is unavoidable within that class, work-conserving TDMA being privacy-optimal and still leaking. The requirement's rationale, that donated time is a timing channel, is presently stated as a design judgement. It is a published result, and citing it converts a judgement into a confirmation at the cost of one clause.
- [ ] **The online/offline-time split names what [R-07-036](verification-maximal-os.md#r-07-036) buys that flushing alone does not.** *[R-07-036](verification-maximal-os.md#r-07-036), [R-07-040](verification-maximal-os.md#r-07-040) · §7.7.*
  Time protection's two channels are separable: `fence.t` and eager zeroize close the online half, and only a behaviour-independent schedule closes the offline half. The model does both and nowhere says so, which understates it: a reader who knows the time-protection line will otherwise read the switch cost as buying what flushing already bought.

---

## 6. Watch

*No obligation attached. Each aims at what §0 settles, so a movement on any of the three would rerun that argument rather than open an item here.*

- [ ] **seL4 MCS verification.** The branch is still under active verification. Completion narrows [R-07-035](verification-maximal-os.md#r-07-035)'s ground to the timing-channel argument alone, which still carries the decision, but would then be carrying it unaided: worth knowing before the ground is needed rather than after.
- [ ] **The time-protection proof line.** Buckley, Sison, Wistoff, Millar, Murray, Klein and Heiser mechanize time protection against seL4. It is the nearest external work to this model's own obligation, and its residuals are the ones §17.2 should expect to inherit.
- [ ] **Any published work-conserving scheduler carrying an offline-time leakage proof.** This is the one result that would reopen §0 and with it the whole reservation-based family. Gong and Kiyavash argue it cannot exist for deterministic schedulers, but their model is a shared queueing server rather than a partitioned CPU, so the impossibility is narrower than a casual reading makes it.

---

## Where the work lands

*Several items collapse into one edit. This is the grouping to work in, not the order above.*

| Section | Items | Class |
| --- | --- | --- |
| §7.7 Scheduling | intra-compartment concurrency model; second-level divergence record; both confirmations | 3, 5A, 5B |
| §11 Timing and scheduling | frame offsets and cross-core response; discretionary frame period; harmonization as tool duty; schedule synthesis | 1, 3 |
| §17.2 Timing and scheduling | the intra-label half of the population wall, if 4A is answered that way | 4A |
