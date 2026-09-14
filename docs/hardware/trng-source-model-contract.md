# The TRNG Source Model: What a Submission Must State, and What Nothing Here Supplies

> A derived view, governed by [R-15-241a](../requirements-register.md).
> It decides nothing. It states what a source stochastic model must say for this platform to read it, the schema a submission is checked against, how the start-up sample budget is derived from that model, the review that reads a submission, and every input no artifact in this repository supplies.
> Where this document and [the register](../requirements-register.md) disagree, the register wins and this document is defective.

## How to read this

R-15-241b sizes the noise source's start-up health tests *against the source's stochastic model*, and R-15-241c claims the conditioner's input entropy rate from the same model. Neither entry says what such a model contains, and no artifact in this repository is one. This document is the instrument that reads one when it arrives. It is not the model, and authoring it fills nothing in.

**Every row of the schema below but two is owed, and that is the correct outcome rather than a defect in the instrument.** Nothing in this tree selects a TRNG. The open-RTL substrate list names `lowRISC/opentitan` and Ibex as the RoT's functional reference, but a functional reference for a digital block is not a stochastic model of a physical source, so this document acquires no opinion about which mechanisms a part carries. The schema is therefore published unfilled, the acceptance review has nothing to evaluate, and the start-up sample budget is an expression over symbols rather than a number.

**No standard is adopted here, and none is cited as a ground.** The field list was checked for omissions against two published requirement sets, NIST SP 800-90B, *Recommendation for the Entropy Sources Used for Random Bit Generation* (nvlpubs.nist.gov), and BSI AIS 20/31, *A Proposal for Functionality Classes for Random Number Generators* version 3.0 (bsi.bund.de), both read on 2026-09-14 for the shape of an entropy-source submission and for nothing else. The register cites neither: SP 800-90A is transcribed at [HmacDrbg.v](../../proofs/HmacDrbg.v) because R-15-241d's DRBG needed a construction to be stated against, and no entry in this repository names SP 800-90B or AIS 31 at all. Where this document names a health-test class it takes it from [the prose carrying R-15-241b's own bookmark](../spec.md#r-15-241b), which is this corpus's adopted sentence, and from nowhere else.

## 1. What the root already implements, and what this document does not re-author

The architectural surface of the entropy root is landed, so nothing below adds a mechanism. Three artifacts carry it, and each of the three refuses a figure by name and says this document's subject owns it.

| Artifact | What it carries | What it refuses |
| --- | --- | --- |
| [sys/rot.sail](../../model/model/sys/rot.sail) | attributed samples into one conditioner, a health verdict per source, one latch with no path out of it, and three refusals at the draw | any claim about a distribution; the file says so at the mixing step, and the budget is read as a configuration constant whose owner it names as this document |
| [postlude/validate_config.sail](../../model/model/postlude/validate_config.sail) | the source-count floor of two and the refusal of a zero budget, both as clauses of `config_is_valid` | a ceiling on either, which is the type's and reaches schema conformance before the validator runs |
| [RotFirmware.v](../../proofs/RotFirmware.v) and [HmacDrbg.v](../../proofs/HmacDrbg.v) | the start-up verdict as a latched boolean ordered before any measured draw, and the seeding discipline as the explicit hypothesis of every DRBG theorem | a sample count, an entropy rate, an estimate, and every figure of the discipline; the first names this document's subject as their owner and the second books them at R-15-241d |

So what is missing is not a mechanism. It is the content of a claim the mechanisms are already shaped around: how much unpredictability one sample of one source carries, and how that is known.

## 2. The shape of a source stochastic model

A submission is five statements. They are the five the register's own obligations consume, and a submission short of any one is read by nothing here.

1. **The physical mechanism of each source**, named as a mechanism rather than as a block: what the noise is, in what device, and what the sampling of it is. R-15-241e mandates at least two mechanisms and not two instances, so this statement is what decides whether the floor is met at all.
2. **The min-entropy per sample of each source**, as a lower bound, with the corner and the service life the bound holds over, and with the method and the dataset that produced it. R-15-241c's criterion wants *a stated number backed by the model, reviewable and disputable as such*, which is a claim about the number's provenance and not only about its value.
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

Two rows are `stated` and twelve are `owed`, and the two that are stated are a floor and a floor. Neither is a value: the model refuses a composition below them and carries no opinion above them, which is exactly the distinction a submission is for.

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
| `H_min` | min-entropy per sample per source | TM-4 |
| `L_seed` | the DRBG's seed length in bits | R-15-241d, and [HmacDrbg.v](../../proofs/HmacDrbg.v)'s own gap (a) |

**The second term's form depends on TM-8, which is itself owed.** The expression above maps per-sample min-entropy to seed bits directly, which is the map a conditioner absorbing at its input width and claiming full entropy at its output width admits. A conditioner with a different absorption discipline changes the map, so what is written here is the form under the one conditioning assumption R-15-241c states and not a form that survives the choice. Fixing TM-8 is what fixes it.

**No symbol on the right is available at any candidate today**, so the expression is not evaluable and no budget is admitted. `N_detect`, `alpha`, `beta` and `target` wait on TM-10 through TM-12; `H_min` waits on TM-4, which waits on a fabricated part; `L_seed` waits on R-15-241d, which says *stated* and states none. Only `k` has a value, and what it has is a floor.

**There is no counterweight.** The detection term rises with the budget and nothing in this repository pushes the other way: no entry bounds cold-boot latency, and the product gate's update-turnaround ceiling is a different quantity and is in any case still proposed. The only ceiling anywhere is `range(0, 65535)` on `plat_rot_startup_samples`, which the schema emission turns into a conformance refusal rather than a decision, so a budget of 65535 and a budget of 65536 are told apart by a representation and not by an argument. §8 reports this.

**The shipped compositions declare 1024, and this document restates it once, as the placeholder its own generator calls it.** [config.json.in](../../model/config/config.json.in) says at that key that nothing there is a measurement and that the model holds the shape alone. It is carried here so that a reader arriving at this document from the configuration finds the same reading rather than a second one; no symbol above is filled from it, no clause of §5 reads it, and a submission arriving at 1024 is one candidate with no standing the others lack. A report that took it for the answer is TS-1's refusal and one that filled `H_min` back out of it is TS-3's.

## 5. The acceptance review

Nine clauses. Each is decidable by reading a submission against an artifact named beside it, or it records its refusal and names what owes it.

1. **Schema conformance.** Every row of §3 carries a statement, and the two `stated` rows agree with the artifacts that state them. Decidable today, against §3.
2. **The source floor is met by mechanisms and not by instances.** TM-2 names at least two distinct physical mechanisms and TM-1 agrees with the composition `config_is_valid` accepts. Decidable today, against R-15-241e and [validate_config.sail](../../model/model/postlude/validate_config.sail).
3. **Independence is argued rather than asserted.** TM-7 names each common-mode coupling it excludes and gives the ground for excluding it. Decidable today as a reading and never by a checker; the review records the reviewer and the couplings read, because a coupling nobody named is the failure mode this clause exists for.
4. **The entropy claim is a measurement with its provenance.** TM-4 is a lower bound taken by the method of TM-5 on the dataset of TM-5, at the corner and the service life of TM-6, on a fabricated part. **Not evaluable today**: no part exists and no TRNG is selected. R-15-247m's refusal of a density figure ahead of a repaired macro is the precedent this clause reads itself under, one axis over.
5. **The conditioner is the one the register names.** **Not writable today.** R-15-241c says *vetted* and names no function, so there is no identity to check TM-8 against. Owed at R-15-241c, or at the crypto-core item that implements the conditioner. The tree holds a Keccak transcription ([Keccak.v](../../proofs/Keccak.v), [keccak_p1600.sail](../../model/model/extensions/keccak/keccak_p1600.sail)) that would be a candidate for such an act; this document does not choose it, choosing it being the act and not the review.
6. **The health tests are the adopted class, sized to this submission.** TM-10 is the repetition-count and adaptive-proportion class and its cutoffs are computed from TM-4 rather than taken from a default. Decidable today against the prose carrying R-15-241b's bookmark. **Its second half is not writable**: TM-11's false-positive rate is the input a cutoff is computed from and nothing in this repository fixes one. Owed at R-15-241b.
7. **The budget satisfies both terms.** §4's expression holds at the submitted `N`. **Not evaluable today**: every symbol but `k` is owed.
8. **The budget is representable.** `N` lies in `range(0, 65535)` and is not zero. Decidable today, and it is a schema-conformance check and never an argument that the budget is right.
9. **The budget is affordable.** `N` divided by TM-3's sampling rate, over the sources the composition declares, fits the boot delay R-09-006a's ordering imposes. **Not writable today**: TM-3 is owed to the supplier and no entry states a bound the quotient would be compared against. Owed at R-09-006a, or to a declared parameter in [the product-gate contract](../implementation/product-gate-contract.md).

**Verdict, on the day this instrument lands: no source stochastic model has been submitted, and no clause above has been evaluated.** Four of the nine are decidable against artifacts that exist, three are refused for want of a register act, and two wait on a part. That distribution is the review's finding about the register and not about any submission.

## 6. What makes a submission inadmissible

| Id | The refusal |
| --- | --- |
| TS-1 | a budget reported as decided while any symbol of §4 is owed |
| TS-2 | a budget or a health-test cutoff sized to a standard's default rather than to the submitted model, which the prose carrying R-15-241b's bookmark refuses by name |
| TS-3 | an entropy figure filled from an order-of-magnitude estimate, from a simulation of an unfabricated part, or from the composition's placeholder, which §4 carries as an illustration and not as an input |
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
| TM-7, the independence argument | the supplier | R-15-241e's criterion rests on it entirely and no artifact here can supply it |
| TM-8, the conditioner's identity and widths | a register act at R-15-241c, or the crypto-core item implementing it | R-15-241c says *vetted* and names no function |
| TM-9, the input and output entropy rates | the supplier for the figure; R-15-241c for the obligation | the entry requires a stated number backed by the model and there is no model |
| TM-10, the tests' windows and cutoffs | the supplier's model | a cutoff is computed from TM-4 and TM-11, and neither exists |
| TM-11, the false-positive rate | a register act at R-15-241b | nothing in this repository fixes one |
| TM-12, the detection target | the supplier's model, against R-15-241b | the entry states the tests and no parameter |
| TM-3, the sampling rate | the supplier | the review's clause 9 turns a budget into a boot delay through it |
| `L_seed`, the DRBG's seed length | R-15-241d | already booked there by [HmacDrbg.v](../../proofs/HmacDrbg.v)'s gaps (a) and (b); §4 consumes it and this row cites that booking rather than raising it again |
| a bound on cold-boot latency | a register act at R-09-006a, or a declared parameter in [the product-gate contract](../implementation/product-gate-contract.md) | nothing bounds it; §4 states the consequence |

Every row has an owner and no row has a placeholder. A row whose owner is the supplier is one this repository cannot close by any act of its own, which is what makes the selection of a TRNG the gate on the whole of §5 rather than one clause of it.

## 8. What this document reports rather than settles

**R-15-241b states the tests and not their class, while the prose under its own bookmark states the class.** The entry says *start-up health tests over a fixed sample budget* and *continuous on-line tests thereafter*; the prose adds *the repetition-count and adaptive-proportion class* and the refusal of a default. The review's clause 6 reads the class, so it reads it off the prose, which is the one place in this instrument where an audited obligation is carried by commentary rather than by the entry the gate audits. Owed at R-15-241b.

**No artifact fixes the health tests' false-positive rate.** It is an input to every cutoff and so to `N_detect`, and it is not the supplier's to choose alone: a rate is a statement about how often a good part halts the boot, which is a product decision. Owed at R-15-241b.

**Nothing bounds cold-boot latency, so the budget's only ceiling in this repository is a representation.** The detection term is monotone upward in `N` and the register supplies nothing monotone downward, so a submission can satisfy every clause of §5 with a budget that makes the machine unusable and no clause would say so. The product gate's update-turnaround ceiling is a different quantity and is itself still proposed. Owed at R-09-006a, or to a new declared parameter in the product-gate contract.
