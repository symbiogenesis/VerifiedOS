# The TRNG Source Model: What a Submission Must State, and What Nothing Here Supplies

> A derived view, governed by [R-15-241a and R-15-241ca](../requirements-register.md).
> It decides nothing. It states what a source stochastic model must say for this platform to read it, the schema a submission is checked against, how the start-up sample budget is derived from that model, the review that reads a submission, and every input no artifact in this repository supplies.
> Where this document and [the register](../requirements-register.md) disagree, the register wins and this document is defective.

## How to read this

R-15-241b sizes the noise source's start-up health tests *against the source's stochastic model*, and R-15-241c claims the conditioner's input entropy rate from the same model. Neither entry says what such a model contains, and no artifact in this repository is one. This document is the instrument that reads one when it arrives. It is not the model, and authoring it fills nothing in.

**Every row of the schema below but two is owed, and that is the correct outcome rather than a defect in the instrument.** Nothing in this tree selects a TRNG. The open-RTL substrate list names `lowRISC/opentitan` and Ibex as the RoT's functional reference, but a functional reference for a digital block is not a stochastic model of a physical source, so this document acquires no opinion about which mechanisms a part carries. The schema is therefore published unfilled, the acceptance review has nothing to evaluate, and the start-up sample budget is an expression over symbols rather than a number.

**No standard is adopted here, and none is cited as a ground.** The field list was checked for omissions against two published requirement sets, NIST SP 800-90B, *Recommendation for the Entropy Sources Used for Random Bit Generation* (nvlpubs.nist.gov), and BSI AIS 20/31, *A Proposal for Functionality Classes for Random Number Generators* version 3.0 (bsi.bund.de), both read on 2026-09-14 for the shape of an entropy-source submission and for nothing else. The register cites neither: SP 800-90A is transcribed at [HmacDrbg.v](../../proofs/HmacDrbg.v) because R-15-241d's DRBG needed a construction to be stated against, and no entry in this repository names SP 800-90B or AIS 31 at all. Where this document names a health-test class it takes it from [the prose carrying R-15-241b's own bookmark](../spec.md#r-15-241b), which is this corpus's adopted sentence, and from nowhere else.

## 1. What the root already implements, and what this document does not re-author

The architectural surface of the entropy root is landed, so nothing below adds a mechanism. Four artifacts in three rows carry it, and each refuses a figure by name: three name this document's subject as the owner and the fourth books its figures at R-15-241d.

| Artifact | What it carries | What it refuses |
| --- | --- | --- |
| [sys/rot.sail](../../model/model/sys/rot.sail) | attributed samples into one conditioner, a health verdict per source, one latch with no path out of it, and three refusals at the draw | any claim about a distribution; the file says so at the mixing step, and the budget is read as a configuration constant whose owner it names as this document |
| [postlude/validate_config.sail](../../model/model/postlude/validate_config.sail) | the source-count floor of two and the refusal of a zero budget, both as clauses of `config_is_valid` | a ceiling on either, which is the type's and reaches schema conformance before the validator runs |
| [RotFirmware.v](../../proofs/RotFirmware.v) and [HmacDrbg.v](../../proofs/HmacDrbg.v) | the start-up verdict as a latched boolean ordered before any measured draw, and the seeding discipline as the explicit hypothesis of every DRBG theorem | a sample count, an entropy rate, an estimate, and every figure of the discipline; the first names this document's subject as their owner and the second books them at R-15-241d |

So what is missing is not a mechanism. It is the content of a claim the mechanisms are already shaped around: how much unpredictability one sample of one source carries, and how that is known.

## 2. The shape of a source stochastic model

A submission is five statements. They are the five the register's own obligations consume, and a submission short of any one is read by nothing here.

1. **The physical mechanism of each source**, named as a mechanism rather than as a block: what the noise is, in what device, and what the sampling of it is. R-15-241e mandates at least two mechanisms and not two instances, so this statement is what decides whether the floor is met at all.
2. **The min-entropy per sample of each source**, as a lower bound, with the corner and the service life the bound holds over, and with the method and the dataset that produced it. R-15-241c's criterion wants *a stated number backed by the model, reviewable and disputable as such*, which is a claim about the number's provenance and not only about its value. A per-sample bound is summed over the budget at §4, so this statement also carries what licenses the sum: that the source's samples are independent across the budget, or the bound on what a dependent source accumulates over it. No entry asks for that; §4's derivation does, and this document says so rather than letting the sum read as the register's.
3. **The conditioning assumption**: which vetted non-keyed cryptographic function, at what input and output widths, and the claimed input entropy rate against the full-entropy output rate R-15-241c requires. The conditioner is the one place raw output stops, so the assumption is what carries a per-sample bound across to the DRBG's seed.
4. **The independence claim across the mechanisms**, stated as the common-mode couplings it excludes and not as an assertion of independence. Two sources sharing a supply rail, a clock, a substrate or a thermal environment can fail together, and R-15-241e's whole content is that no single failure silently repairs or silently corrupts the root's output.
5. **The health tests' detection scope**: which tests, at what parameters, detecting which failure at what probability and after how many samples. The class is fixed by the prose carrying R-15-241b's bookmark, the repetition-count and adaptive-proportion class, *sized against the source's stochastic model rather than to a default*. Its parameters are not fixed anywhere, which §8 reports.

## 3. The schema a submission is checked against

One row per statement the submission makes or constraint it is checked against. `stated` means an artifact in this tree already fixes the row and a submission disagreeing with it is refused; `owed` means nothing here supplies it and the owner column says who does.

| Id | What the submission states | Read by | Status | Owner |
| --- | --- | --- | --- | --- |
| TM-1 | how many independent noise sources feed the one conditioner, at least two | R-15-241e, `config_is_valid` | stated | n/a |
| TM-2 | the physical mechanism of each source | R-15-241e, and TM-7's argument | owed | the selected TRNG's silicon supplier |
| TM-3 | each source's sampling rate | the boot delay R-09-006a's ordering imposes | owed | the supplier |
| TM-4 | min-entropy per sample per source, as a lower bound | R-15-241c, and §4's second term | owed | the supplier's characterization on a fabricated part |
| TM-4a | that one source's samples are independent across the budget, or the bound on the entropy a dependent source accumulates over the budget's samples | §4's second term, and the review's clause 7 | owed | the supplier's model |
| TM-5 | the method and the dataset that produced TM-4 | the review's clause 4 | owed | the supplier |
| TM-6 | the corner and the service life TM-4 holds over | the review's clause 4 | owed | the supplier |
| TM-7 | the independence argument across TM-2's mechanisms, as the common-mode couplings it excludes | R-15-241e | owed | the supplier |
| TM-8 | the conditioner's identity and its input and output widths | R-15-241c | owed | a register act at R-15-241c naming the function, or the crypto-core item that implements it |
| TM-9 | the claimed input entropy rate at the conditioner and the full-entropy output rate | R-15-241c | owed | the supplier for the figure, R-15-241c for the obligation to state it |
| TM-10 | the health tests, with each test's window and cutoff | R-15-241b, and the prose carrying its bookmark | owed | the supplier's model for the cutoffs |
| TM-11 | the health tests' false-positive rate | the review's clause 6 | owed | a register act at R-15-241b, which fixes no rate |
| TM-12 | the detection target: which failure, at what probability, after how many samples | R-15-241b, and §4's first term | owed | the supplier's model, against R-15-241b's *sized against* |
| TM-13 | the start-up sample budget | R-15-241b, R-09-006a, `plat_rot_startup_samples` | owed | §4's derivation over TM-4, TM-9, TM-10, TM-11 and TM-12, none of which exists |
| TM-14 | that the budget is at least one sample | `config_is_valid` | stated | n/a |

All but two rows are `owed`, and the two that are `stated` are a floor and a floor. Neither is a value: the model refuses a composition below them and carries no opinion above them, which is exactly the distinction a submission is for.

## 4. The derivation to the start-up sample budget

The budget is the larger of two lower bounds, one from detection and one from seeding, and it has no upper bound in this repository at all.

```
N  >=  max( N_detect(tests, cutoffs, alpha, beta, target) ,  ceil( L_seed / (k * H_min) ) )
```

| Symbol | Meaning | Schema row |
| --- | --- | --- |
| `N` | the start-up sample budget, per source | TM-13 |
| `N_detect` | the least sample count at which the declared tests reach the declared detection probability | TM-10, TM-11, TM-12 |
| `alpha` | the tests' false-positive rate | TM-11 |
| `beta`, `target` | the detection probability and the failure it is claimed against | TM-12 |
| `k` | the number of sources | TM-1 |
| `H_min` | the min-entropy one sample of one source carries; the expression adds it over both | TM-4; TM-7 and TM-4a license the two additions |
| `L_seed` | the DRBG's seed length in bits | R-15-241d, and [HmacDrbg.v](../../proofs/HmacDrbg.v)'s own gap (a) |

**The second term's form rests on three claims, and every one of them is owed.** It adds twice before it maps: `k * H_min` adds across the sources, which is TM-7's cross-source independence and nothing else, and requiring `N` such samples adds across one source's own samples, which is TM-4a and is the claim no register entry asks for. It then carries the sum to seed bits directly, which is the map a conditioner absorbing at its input width and claiming full entropy at its output width admits, and a conditioner with a different absorption discipline changes it, which is TM-8. So what is written here is the form under one conditioning assumption and two independence assumptions, none of the three fixed, and fixing TM-8 alone would not fix it. The case this matters in is not exotic: a memoryful or drifting source can satisfy every other row of §3 and every other clause of §5 and leave clause 7 accepting a budget that under-seeds the DRBG, which is R-15-241a's case exactly, every proof holding and the drawn value predictable.

**No symbol on the right but `k` is available at any candidate today**, so the expression is not evaluable and no budget is admitted. `N_detect`, `alpha`, `beta` and `target` wait on TM-10 through TM-12; `H_min` waits on TM-4, which waits on a fabricated part; `L_seed` waits on R-15-241d, which says *stated* and states none. Only `k` has a value, and what it has is a floor.

**The counterweight is R-09-006b.** The detection term rises with the budget, and what pushes the other way is the composed boot's worst-case latency, a composition constant R-09-006b states with the budget over TM-3's sampling rate as one of its terms, read by the product gate against DP-7, its cold-boot ceiling, which is proposed and binds nothing until ratified; and R-15-198a runs the tests concurrently with the clock-spine lock, the memory-controller bring-up and every image-derived fill, so what the budget adds to that constant is its excess over those steps and not its whole. Inside this repository the only hard ceiling remains `range(0, 65535)` on `plat_rot_startup_samples`, which the schema emission turns into a conformance refusal rather than a decision, so a budget of 65535 and a budget of 65536 are told apart by a representation and not by an argument until DP-7 is ratified. §8 reports what the ceiling's status leaves open.

**The shipped compositions declare `platform.trng.startup_samples`, and the figure is not repeated here.** [config.json.in](../../model/config/config.json.in) says at that key that nothing there is a measurement and that the model holds the shape alone; no rule holds a second copy of it, so this document points at the key and never restates the value. No symbol above is filled from it, no clause of §5 reads it, and a submission arriving at the declared value is one candidate with no standing the others lack. A report that took it for the answer is TS-1's refusal and one that filled `H_min` back out of it is TS-3's.

## 5. The acceptance review

Nine clauses. Each is decidable by reading a submission against an artifact named beside it, or it records its refusal and names what owes it.

1. **Schema conformance.** Every row of §3 carries a statement, and the two `stated` rows agree with the artifacts that state them. Decidable today, against §3.
2. **The source floor is met by mechanisms and not by instances.** TM-2 names at least two distinct physical mechanisms and TM-1 agrees with the composition `config_is_valid` accepts. Decidable today, against R-15-241e and [validate_config.sail](../../model/model/postlude/validate_config.sail).
3. **Independence is argued rather than asserted.** TM-7 names each common-mode coupling it excludes and gives the ground for excluding it. Decidable today as a reading and never by a checker; the review records the reviewer and the couplings read, because a coupling nobody named is the failure mode this clause exists for.
4. **The entropy claim is a measurement with its provenance.** TM-4 is a lower bound taken by the method of TM-5 on the dataset of TM-5, at the corner and the service life of TM-6, on a fabricated part. **Not evaluable today**: no part exists and no TRNG is selected. R-15-247m's refusal of a density figure ahead of a repaired macro is the precedent this clause reads itself under, one axis over.
5. **The conditioner is the one the register names.** **Not writable today.** R-15-241c says *vetted* and names no function, so there is no identity to check TM-8 against. Owed at R-15-241c, or at the crypto-core item that implements the conditioner. The tree holds a Keccak transcription ([Keccak.v](../../proofs/Keccak.v), [keccak_p1600.sail](../../model/model/extensions/keccak/keccak_p1600.sail)) that would be a candidate for such an act; this document does not choose it, choosing it being the act and not the review.
6. **The health tests are the adopted class, sized to this submission.** TM-10 is the repetition-count and adaptive-proportion class and its cutoffs are computed from TM-4 rather than taken from a default. Decidable today against the prose carrying R-15-241b's bookmark. **Its second half is not writable**: TM-11's false-positive rate is the input a cutoff is computed from and nothing in this repository fixes one. Owed at R-15-241b.
7. **The budget satisfies both terms.** §4's expression holds at the submitted `N`, under the premises the second term adds under: TM-4a read at clause 1, TM-7 at clause 3, TM-8 at clause 5, so a submission that passes the arithmetic while failing one of those three fails here rather than passing. **Not evaluable today**: every symbol but `k` is owed.
8. **The budget is representable.** `N` lies in `range(0, 65535)` and is not zero. Decidable today, and it is a schema-conformance check and never an argument that the budget is right.
9. **The budget is affordable.** `N` divided by TM-3's sampling rate, over the sources the composition declares, enters the cold-boot constant R-09-006b states as one term, and that constant fits DP-7 of [the product-gate contract](../implementation/contracts/product-gate.md). **Not evaluable today**: TM-3 is owed to the supplier, and DP-7 is proposed, so a reading against it is a reading and not a verdict. Owed at TM-3 and at DP-7's ratification.

**Verdict, on the day this instrument lands: no source stochastic model has been submitted, and no clause above has been evaluated.** Four of the nine are decidable against artifacts that exist, three are refused for want of a register act, clause 4 waits on a part, and clause 7 waits on all of it at once. That distribution is the review's finding about the register and not about any submission.

## 6. What makes a submission inadmissible

| Id | The refusal |
| --- | --- |
| TS-1 | a budget reported as decided while any symbol of §4 is owed |
| TS-2 | a budget or a health-test cutoff sized to a standard's default rather than to the submitted model, which the prose carrying R-15-241b's bookmark refuses by name |
| TS-3 | an entropy figure filled from an order-of-magnitude estimate, from a simulation of an unfabricated part, or from the composition's placeholder, which §4 points at and never reads |
| TS-4 | an independence claim across mechanisms that names no common-mode coupling, so that what it excludes is unstated and cannot be disputed |
| TS-5 | a budget above 65535, which the model's own type turns into a schema-conformance refusal rather than a decision, and which is therefore a defect in the submission and not an argument against the type |
| TS-6 | a submission on a single physical mechanism, or a second source that is a second instance of the first mechanism, which meets TM-1's count while failing R-15-241e's floor |
| TS-7 | a detection target stated without the probability it is reached at and the sample count it is reached after, which is a scope with no clause 7 behind it |
| TS-8 | a conditioner named only as vetted, the word being R-15-241c's and not an identity |
| TS-9 | an entropy bound stated without the corner and the service life it holds over, which is R-15-247m's discipline read on the noise source |
| TS-10 | a source failure argued away as detected where its own tests do not see it, which is R-17-049a's subversion residual and is inherited rather than narrowed |

## 7. The inputs nothing here supplies, and who owes each

| Input | Owner | Why it is not here |
| --- | --- | --- |
| the identity of the selected TRNG | the programme, at the item that selects it | no artifact in this tree selects one; the RoT's functional-reference RTL is a digital block and not a source |
| TM-2, the physical mechanisms | the supplier | [rot.sail](../../model/model/sys/rot.sail) states outright that which mechanism a source is has no architectural content, so the model holds no opinion and this document acquires none |
| TM-4, TM-5 and TM-6, the entropy bound with its method, dataset, corner and life | the supplier's characterization on a fabricated part | a pre-silicon entropy figure is the same act R-15-247m refuses for density |
| TM-4a, the across-sample independence claim | the supplier's model | no entry asks for it: R-15-241e's independence is across mechanisms, and §4's second term adds over one source's samples without it |
| TM-7, the independence argument | the supplier | R-15-241e's criterion rests on it entirely and no artifact here can supply it |
| TM-8, the conditioner's identity and widths | a register act at R-15-241c, or the crypto-core item implementing it | R-15-241c says *vetted* and names no function |
| TM-9, the input and output entropy rates | the supplier for the figure; R-15-241c for the obligation | the entry requires a stated number backed by the model and there is no model |
| TM-10, the tests' windows and cutoffs | the supplier's model | a cutoff is computed from TM-4 and TM-11, and neither exists |
| TM-11, the false-positive rate | a register act at R-15-241b | nothing in this repository fixes one |
| TM-12, the detection target | the supplier's model, against R-15-241b | the entry states the tests and no parameter |
| TM-3, the sampling rate | the supplier | the review's clause 9 turns a budget into a boot delay through it |
| `L_seed`, the DRBG's seed length | R-15-241d | already booked there by [HmacDrbg.v](../../proofs/HmacDrbg.v)'s gaps (a) and (b); §4 consumes it and this row cites that booking rather than raising it again |
| a bound on cold-boot latency | R-09-006b for the constant; the product's owner for DP-7's ratification in [the product-gate contract](../implementation/contracts/product-gate.md) | the constant is a register obligation and the ceiling a proposed parameter; §4 states how the budget enters the constant |

Every row has an owner and no row has a placeholder. A row whose owner is the supplier is one this repository cannot close by any act of its own, which is what makes the selection of a TRNG the gate on the whole of §5 rather than one clause of it.

## 8. What this document reports rather than settles

**R-15-241b states the tests and not their class, while the prose under its own bookmark states the class.** The entry says *start-up health tests over a fixed sample budget* and *continuous on-line tests thereafter*; the prose adds *the repetition-count and adaptive-proportion class* and the refusal of a default. The review's clause 6 reads the class, so it reads it off the prose, which is the one place in this instrument where an audited obligation is carried by commentary rather than by the entry the gate audits. Owed at R-15-241b.

**No artifact fixes the health tests' false-positive rate.** It is an input to every cutoff and so to `N_detect`, and it is not the supplier's to choose alone: a rate is a statement about how often a good part halts the boot, which is a product decision. Owed at R-15-241b.

**Cold-boot latency is bounded by a constant whose ceiling is proposed.** R-09-006b makes the composed boot's worst case a composition constant with the start-up budget over TM-3 as one term, so the detection term now has the counterweight this section once reported as absent; the ceiling it is read against, DP-7 of the product-gate contract, is proposed, so a submission can still satisfy every clause of §5 with a budget that fails the gate as a reading and not as a verdict until the product's owner ratifies it. Owed at DP-7's ratification.

## 9. Assignment and selection acts for the owed inputs

The following assigns the thirteen input groups in §7 to decisions. Roles name
the accountable owner; the eventual selection record must identify its human
owner, supplier, part revision and evidence revision. No part is selected here,
no source model is submitted, and no acceptance clause is evaluated by assigning
the work. The programme's silicon lead owns obtaining the supplier deliverables;
the independent assurance reviewer owns their acceptance under §5.

| Input group | Accountable owner | Act that supplies or selects it |
| --- | --- | --- |
| Selected TRNG identity | Programme silicon lead | Land a reviewed component-selection record naming supplier, part or macro revision, process, licensing and characterization deliverables. A digital functional reference is insufficient. |
| TM-2 mechanisms | Selected supplier's analog design lead | Supply a circuit-level mechanism and sampling description for each source; the selection review records that at least two physical mechanisms are present. |
| TM-4, TM-5, TM-6 | Supplier characterization lead | Deliver versioned fabricated-part datasets, acquisition method, estimator, corners and lifetime evidence; assurance review accepts a lower bound with that stated scope. |
| TM-4a sample dependence | Supplier stochastic-model owner | Submit either across-sample independence evidence or a conservative dependent-sample accumulation bound; assurance review records which licenses the budget calculation. |
| TM-7 cross-source independence | Supplier analog design lead with programme physical-design lead | Submit coupling analysis for supply, clock, substrate and thermal paths, plus failure evidence; independent review accepts each stated exclusion. |
| TM-8 conditioner | Programme cryptographic architecture owner | Land the conditioner identity and input/output widths through R-15-241c or the crypto-core implementation contract, with its vetted-function evidence. |
| TM-9 rates | Supplier stochastic-model owner | Derive the input entropy and full-entropy output rates under the selected conditioner; the R-15-241c review accepts the figures and their premises. |
| TM-10 tests and cutoffs | Supplier health-test design owner | Derive repetition-count and adaptive-proportion windows and cutoffs from the accepted bound and programme-selected false-positive rate; review the derivation, not a default. |
| TM-11 false-positive rate | Programme product-reliability owner | Land the accepted good-part boot-stop rate at R-15-241b, with operating and service-life scope, before cutoff selection. |
| TM-12 detection target | Programme fault-assurance owner and supplier health-test owner | Select the failures and required detection probabilities and delays at R-15-241b; supplier evidence demonstrates the tests' detection scope against them. |
| TM-3 sampling rate | Supplier characterization lead | Deliver the guaranteed sampling rate across the selected corners; the component-selection review accepts the scope used in the boot-delay calculation. |
| `L_seed` | Programme cryptographic architecture owner | Land DRBG seed length and strength/reseed discipline at R-15-241d and its crypto-core contract before evaluating the seeding term. |
| Cold-boot latency bound | Programme product owner | Ratify DP-7 in the product-gate contract, including corner and operating-point scope; evaluate clause 9 against R-09-006b's constant read against it. |

After these acts and the extraction qualification in §10, the source-model owner computes TM-13 from the accepted inputs,
records the calculation and representation check, and submits all nine clauses
for independent review. Failure of any required premise leaves the budget owed;
the configured emulation budget supplies none of the missing evidence.

## 10. Two-source extraction qualification

R-15-241ca requires a recorded decision before TRNG selection closes: evaluate a
deterministic two-source extractor before the vetted conditioner, with the
conditioner and DRBG-only consumer interface retained. This is a qualification
obligation, not selection of a circuit or credit for an implemented theorem.
Q28b owns the finite theorem and its qualification record; existing entropy-root
implementation and supplier-characterization work retain their own owners.
An unqualified candidate is recorded with its failed premises; the baseline
R-15-241b through R-15-241e obligations remain unchanged. The source count and
mechanism diversity do not supply the missing finite entropy parameters.

There are explicit constructions for much weaker independent sources than the
simple inner-product route. Chattopadhyay and Zuckerman construct a two-source
extractor at polylogarithmic min-entropy; Li's later work reaches asymptotically
optimal `O(log n)` entropy for the stated error regime. These results establish
mathematical possibilities, not this part's block sizes, error target, latency,
side-information security or mechanized implementation. The qualification uses
an exact finite theorem and its constants, not the phrase "polylogarithmic".
[*Explicit two-source extractors and resilient functions*, Annals 2019](https://annals.math.princeton.edu/wp-content/uploads/annals-v189-n3-p01-s.pdf),
[Li, *Two Source Extractors for Asymptotically Optimal Entropy, and (Many) More*](https://eccc.weizmann.ac.il/report/2023/023/)

### Research handoff for alternative extractors

For the unfinished Q28b qualification and S5 source-model join, the [low-error extraction survey](../background/open-math-conjectures.md#explicit-low-error-two-source-extraction) identifies alternative mathematical constructions to compare with the inner-product candidate below. This is research guidance within the existing qualification record, with no source selected or acceptance status changed. Li's logarithmic-entropy constant-error theorem is available as a proof source; simultaneously negligible error at the stated low entropy remains a different target. The surveyed May revision of TR26-011 withdraws its efficient negligible-error DAG-source construction, and TR26-089 is retracted. Their former claims cannot supply the missing efficient two-independent-source theorem.

A candidate comparison should instantiate `n`, both entropy bounds, output length, finite constants and statistical error before comparing sample, buffer and latency costs. Derive the joint law conditioned on the actual observer and history, relate it to the theorem's independence premises, and connect the exact TM-8 conditioner through the existing input-plus-image error budget. A positive witness is a realizing finite distribution pair and a complete seed budget; useful negative witnesses are correlated sources with individually high entropy, repeated blocks without a fresh-history theorem, an impossible `k > n` record and a constant conditioner. The existing local witnesses can exercise those seams, but the physical source evidence, refinement and WCET remain owed. An existence theorem, asymptotic error label or unconditional source model does not discharge these joins, and quantum side information still requires its own applicable theorem.

### A finite first candidate

The initial proof target is the binary inner product of the Chor-Goldreich
construction, rather than an unspecified finite-field variant:

```text
IP(x, y) = XOR over i = 1..n of (x_i AND y_i)

X, Y in {0,1}^n independent
max_x Pr[X=x] <= 2^(-k_X), max_y Pr[Y=y] <= 2^(-k_Y)

Delta(IP(X,Y), U_1) <= (1/2) * 2^((n-k_X-k_Y)/2)
```

Here `Delta` is total variation distance and `U_1` a uniform bit. The target
bound follows from the Walsh-Hadamard matrix's norm and the two distributions'
collision-probability bounds; this paragraph is the mathematical proof route,
and the checked Gallina theorem it describes is the one this section's closing
paragraph records. At entropy exactly `n/2` in each source,
independent distributions on suitable orthogonal subspaces can make the output
constant. Independence without a sufficient **sum** of finite min-entropies
therefore does not entail extraction. [Chor and Goldreich, *Unbiased Bits from
Sources of Weak Randomness and Probabilistic Communication Complexity*, 1988](https://doi.org/10.1137/0217015)

The useful theorem must also name the observer. For a classical side-information
value `e`, a sufficient premise is that `X` and `Y` are independent **conditioned
on every supported `e`**, with the displayed entropy bounds holding for each
conditional distribution. Then the same error bounds the joint output with that
observer's information. Marginal entropy, unconditional independence, average
conditional entropy and passing health tests cannot silently substitute for
those pointwise premises. Health-test success, prior draws, and any observable
rejection or timing transcript belong in the conditioned information where the
claim is made after observing them. Conditioning itself can introduce dependence
or reduce entropy.

For `m` output bits from successive block pairs, the record must prove the
corresponding conditional premises at each invocation, including the prior
history, or supply a separate multi-output theorem. A hybrid argument then gives
total error at most the sum of the `m` individual bounds. Repeating the one-bit
operation on one pair is not such a theorem. A sufficient symbolic target is
`k_X + k_Y >= n + 2s`, giving per-bit error at most `2^(-s-1)` and aggregate
error at most `m * 2^(-s-1)` for qualifying fresh pairs. A concrete witness must
instantiate every symbol from the selected source and seed contract; none is
filled from a nominal entropy rate or the configured startup placeholder.

Quantum side information requires its own theorem and physical scope.
Kasher and Kempe analyze the inner-product family against specifically bounded
quantum-storage adversaries; their premises are not a theorem against arbitrary
quantum leakage. Non-malleable extraction likewise requires a stated tampering
family and entropy premises. Neither label closes R-17-049a's undetectable source
subversion, common-mode control of both sources, or absent entropy.
[*Two-Source Extractors Secure Against Quantum Adversaries*, 2012](https://doi.org/10.4086/toc.2012.v008a021)

### Qualification record and acceptance

The cryptographic architecture owner supplies the finite proof and implementation
contract; the supplier's stochastic-model owner supplies source evidence; the
independent assurance reviewer checks that their premises match. In addition to
TM-1 through TM-14, the record carries:

| Field | Required decision evidence |
| --- | --- |
| Construction | Exact function, source pairing and block boundaries; source attribution preserved; widths and representation fixed |
| Entropy | Per-block lower bounds derived from TM-4/TM-4a with temporal dependence, corners, life and the conditioned transcript explicit |
| Joint model | Independence and leakage premises matched to TM-7; supply, clock, substrate, thermal and injection coupling reviewed; no inference from mechanism count alone |
| Finite theorem | Checked term, declared assumptions, instantiated widths, output length and statistical distance; accepted and failing parameter witnesses |
| Seed accumulation | Invocation count, prior-history premises, exact seed-length relation and aggregate error for startup and every reseed; no reuse of blocks without a theorem |
| Conditioner join | Exact TM-8 map and a theorem or separately declared cryptographic assumption connecting extracted input to conditioned seed; output width and additional error or advantage stated |
| Implementation | Refinement of the actual bit operations to the function, fixed execution and memory bounds, buffering and erasure, health tests before credit and the existing fail-stop latch |
| Cost | Raw-sample counts, representation fit, TM-3 throughput, startup/reseed delay, storage, conditioner work and sustainable DRBG demand |
| Verdict | Qualified candidate with all premises supplied, or unqualified candidate naming each failed or unavailable premise; neither verdict is inferred from a configured emulation value |

For the conditioner join, post-processing preserves distance from the image of
uniform input, not necessarily from uniform **output**. If the extracted block
is `epsilon`-close to `U_m`, then a fixed conditioner `C` produces an output
`epsilon`-close to `C(U_m)`. A statistical seed claim additionally needs a bound
`delta_C` from `C(U_m)` to the target uniform seed, giving total error at most
`epsilon + delta_C`. A cryptographic claim is recorded as such, with its own
advantage and model; hashing cannot silently turn this into a statistical claim.
TM-9 and the §4 seed-budget calculation must be recomputed for the selected chain,
including extraction's output loss. The simple raw-entropy sum in §4 cannot be
used as its output-rate formula.

### Finite composition and parameter proof contract

The [extractor research review](../background/open-math-conjectures.md#explicit-low-error-two-source-extraction)
keeps asymptotic improvements separate from this candidate's finite premises.
The extension to `TwoSourceExtractor.v` preserves every existing definition,
statement and allowed assumption. Its acceptance predicate is an axiom-free
conditioner-to-target bound carrying both the input error and `delta_C`, a
bit-string specialization, and a composed hybrid-plus-conditioner budget in the
existing integer distance scaling. Nonnegative weights with equal positive totals
are required when interpreting those inequalities as normalized statistical distances.
The conditioner still has to map each supported input to exactly one enumerated
output. A constant conditioner must demonstrate that its additional error
cannot be dropped.

The finite-parameter addition must prove that a positive distribution over
`n`-bit strings cannot satisfy the existing min-entropy premise at `k > n`.
For a source pair meeting the candidate's `n + 2s <= kX + kY` target this yields
`2s <= n`. An arithmetically admissible parameter record with an impossible
entropy width must have no realizing source pair; an existing realizable record
must still meet the bound. No source record or admissibility predicate is changed.

Review covers correspondence to R-15-241ca, positive and distinguishing negative
witnesses, and the unchanged physical and invocation premises. Acceptance uses
the exact assumption audit and fresh kernel check through Guest CI with
`cold: true`, together with green Host CI. The run and revision are recorded;
a pending guest verdict supplies no proof acceptance or source qualification.

### Current qualification boundary

Qualification fails when any required premise, correspondence or resource bound
is absent. The finite theorem for this candidate is landed at
[TwoSourceExtractor.v](../../proofs/TwoSourceExtractor.v): over integer weight
functions on `n`-bit strings, with min-entropy stated as `weight * 2^k <= total`
and independence stated as the product of the two weight functions, it proves
`B^2 * 2^(k_X + k_Y) <= W^2 * V^2 * 2^n` for the signed bias numerator `B` and
the totals `W` and `V`, the scaling `2 * Delta = |B| / (W * V)`, the
`k_X + k_Y >= n + 2s` corollary, the observer clause as one distance over the
joint side-information value and output bit, the `m`-invocation hybrid sum, and
post-processing by a fixed conditioner, with an accepted and a failing parameter
witness and a refuting construction at min-entropy exactly `n/2` per source. The
Finite theorem row above reads against it as follows: the checked term, its
declared assumptions and the statistical distance are supplied; the output width
is named as the invocation count of one-bit outputs, which is this
construction's width and not the selected chain's; and the accepted widths are
instantiated by a uniform pair, a mathematical object and not a characterized
source. It supplies none of the other required fields: no source model, selected
extractor, TM-8 conditioner map, seed-accumulation invocation premise or
qualified output-rate claim is present today. This record identifies exactly
what would earn a statistical claim before the conditioner; the landed artifact
supplies no new physical assumption by implication.

The composition extension carries the separately supplied conditioner-image
error into the final target distance, including after an invocation hybrid.
Its integer-scaled budget is `m * per_invocation_budget + image_budget`; each
budget uses the same `2^s` scale. It does not derive the image budget for an
unselected conditioner. The parameter extension makes a different check:
positive `n`-bit sources have min-entropy at most `n`, so a realizing source pair
meeting this construction's target must satisfy `2s <= n`. The arithmetic
admissibility predicate alone is weaker: `n=8, kX=kY=9, s=5` passes it, but no
positive source pair realizes those bounds. This is a limit of the stated
inner-product guarantee, not an impossibility theorem for all extractors.
