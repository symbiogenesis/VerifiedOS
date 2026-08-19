# The Profile-Freeze Measurement Contract

*Normative as a **view** where it restates the register, and **instrument-defining** where it does not. This is the artifact §0 of the [implementation plan](implementation-checklist.md) assigns to M0: the versioned corpus manifest and its generated-source inputs, the composition recipe, the admitted region classes, the acceptance threshold for every choice, the emitter-provenance schema that labels operand classes before assembly, and the one report format that records the realized dictionary, bytes, and Sail-model worst-case cycles. M1.8 builds and wires the instrument this document specifies, and M1.2's backend emits the sidecars §4 defines; neither is a prerequisite of this document, which is a specification act of the R-18-003b class and gates on nothing.*

> **Precedence.** Where this document and [requirements-register.md](requirements-register.md) disagree, **the register wins and this document is defective.** It decides nothing the register decides, and it may not add, remove, or reorder a member of R-15-014a's closed final-freeze delta. What it adds is the *instrumentation*: how a measurement the register already mandates is taken, against what, and which number separates a win from noise. Every such number is either **derived**, with its arithmetic shown where it is stated, or **declared**, and the declared ones are collected in §8 rather than scattered through the text, so every judgment in the contract is findable in one table.

## Why this document exists

The freeze is two acts (R-15-014a). The provisional act fixes everything not conditioned on measurement and is the schedule root R-18-003a names. The final act is the one the proof is taken with, and its delta is closed at six enumerated items whose common property is that each is re-derived from measurement against generated output that does not exist until a backend and a composed image do (R-18-003c).

A measurement is not a fact until three things beside it are fixed: what was measured, what it was measured against, and what number would have changed the answer. None of the three is recoverable after the fact. A freeze report quoting a byte delta without its corpus is a numerator without a denominator; a hit rate quoted whole is R-15-036k's explicitly forbidden aggregate; and **a threshold chosen after the measurement is not a threshold, it is a rationalization.** The whole value of authoring this at M0, before the backend that produces the corpus exists, is that no number in it can have been chosen to make a particular instrument pass. That is also why the schedule places it here rather than beside the analyzer: M1.8 wires an instrument to a contract, and an instrument that arrives with its own acceptance criteria has graded its own homework.

Three consequences follow, and they shape everything below.

- **The measurement is over a composed artifact, not over a component.** Every quantity here is taken against an image built by the recipe in §3, after the §10 and §13 duplication-removal levers, because a dictionary selected against an unmerged image is selected against the wrong histogram (R-13-010e, R-15-036i) and a call-form delta measured over one component counts call sites the composed roster would have merged (R-13-010b).
- **The dictionary is re-selected inside every variant.** Each candidate instrument changes the instruction histogram, so comparing a candidate image against a baseline whose dictionary was chosen for the baseline scores the instrument and the stale dictionary together. §3 makes re-selection a step of the recipe rather than an option, and §9 makes its omission a rejection.
- **Bytes are measured, not modelled.** The encoder is a deterministic composition-time transform (R-15-036g), so the encoded size of an image is an observation. R-15-036h's slot model and R-15-036j's packing term are reported *beside* the observation as a residual check on the model, never in place of it, and a residual outside §8's tolerance is a finding against the model rather than a failed freeze.

---

## 1. The measured act: what is decided, and in what order

The delta is R-15-014a's and is restated here only to attach an instrument to each row. The rightmost column names the decision this contract defines in §6; the ordering column is the sequence R-15-036i and R-15-036p fix, and §9 checks.

| Delta item (R-15-014a) | Governing | Instrument | Order |
| --- | --- | --- | --- |
| (i) realized dictionary size, entry selection, site-varying policy | R-15-036i, R-15-036k | FD-1 | 2, and again as the closing pass |
| (ii) bundle, header, and slot widths | R-15-036a | FD-2 | 2, jointly with FD-1 |
| (iii) call and global-address materialization form, and any absolute form's reachable region | R-15-036l | FD-4 | 3, jointly with FD-3 |
| (iv) the bitfield pair's specifier form, its insert form, and whether the pair is carried | R-15-067d | FD-5 | 4 |
| (iv, continued) the one further code-size candidate weighed in the same act | R-15-067e | FD-6 | 4 |
| (v) the capability indexed load and store's scale immediate | R-15-007g | FD-7 | 4 |
| (vi) frozen fusion-set membership | R-15-031a | FD-8 | 4 |

Two instruments serve rows that are not themselves delta items, and both are in scope because a delta item is measured against their output or against their axis.

| Instrument | Governing | Why it is here | Order |
| --- | --- | --- | --- |
| FD-3, outlining and tail merging on two axes | R-15-036o, R-15-036p | it is measured **first**, every other candidate's corpus being the output of a backend that already outlines; and R-15-036p takes it jointly with FD-4 | 1 |
| FD-9, `rcstep` carriage on worst-case cycles per frame | R-15-067h, R-15-238c | the same single measured act weighs it, on the cycle axis and over a corpus of its own, reported in this report rather than a second one | 4, independent |

**The order is not a convenience.** FD-3 changes the corpus every later row is measured against, so a report that took FD-4 first has measured the call form against an image carrying the stereotyped prologues FD-3 was going to remove (R-15-036p). FD-1 and FD-2 are joint because the selection procedure's output depends on the slot width that bounds the dictionary and on the packing term the slot count fixes. FD-4 through FD-8 are mutually independent given a fixed FD-1/FD-2 configuration and are measured as one-knob variants against the same baseline (§3), and the dictionary is then selected once more at the admitted configuration, which is the realized dictionary the freeze records.

**One row of the freeze's single measured act carries no measurement, and that is a decision rather than an omission.** The single-check multi-register save and restore is **struck ahead of the freeze** (R-15-036n): the candidate is not weighed, its win being halved before any measurement sees it and its residual being substitutive with FD-3's outlining. §0 of the implementation plan lists it in the report's ordered act, and this contract books it as a **nil row**: the report carries the row, names the strike and its governing requirement, and leaves every byte and cycle column `n/a`. A report that carries a *measured* multi-register save row is a report of an amendment (R-18-034), not of a freeze, and §9 rejects it.

**Two rows of R-15-014a's delta are absent from §0's ordered list and present here**, because the delta is closed and the report quantifies over it: FD-6, the further code-size candidate R-15-067e names, and FD-8, the fusion set R-15-031a selects. FD-8 is the one row whose *decision* is not this instrument's to take, membership being a composition-time parameter of the §15 design-space exploration; what this instrument owes it is its measured input, the emitted adjacency histogram, because the exploration cannot invent the mix it selects against. That is booked in §10 as a correction owed to §0 rather than as a difference between the two documents.

---

## 2. The corpus

A corpus member is a named, hashed, reproducibly built artifact that at least one decision is measured against. The manifest is versioned as a whole: its identity is a hash over every member's hash together with the pins and tool versions of §3, so *the corpus* is one object that a report cites and a rebuild reproduces, not a list of files that happened to be present.

| Id | Member | Produced by | Pinned by | Feeds |
| --- | --- | --- | --- | --- |
| `FM-1` | the composed base image, position-fixed, over the first-release roster | M1.4's image composer, after the §10 and §13 levers | roster revision (R-18-004), backend commit, composer commit, provisional profile revision | FD-1, FD-2, FD-3, FD-4, FD-5, FD-6, FD-7, FD-8 |
| `FM-2` | generated UPER RRC codecs, encoder and decoder | the verified ASN.1 (X.691 UPER) to Narcissus front end over the published 3GPP modules (R-05-048, R-18-029) | 3GPP TS 38.331 edition, front-end commit | FD-5 |
| `FM-3` | generated IEI/TLV 5G-NAS codecs | the hand-written NAS grammar's generator (R-05-050, R-18-029) | TS 24.501 edition, grammar revision | FD-5 |
| `FM-4` | generated MMIO register accessors | the verified HAL's accessor generator over the attested devicetree (R-05-083, R-18-018) | devicetree revision, generator commit | FD-5, FD-7 |
| `FM-5` | the emitted call, prologue and epilogue, and global-address materialization sites | derived from `FM-1` by the provenance join of §4, not separately built | `FM-1` | FD-3, FD-4 |
| `FM-6` | the decode conformance streams and their per-frame digests | the formally derived stream corpus of R-15-238d, at the tuples the media server is admitted at (R-15-238c, R-12-084b) | corpus revision, admitted-tuple table revision | FD-9 |

**`FM-2` through `FM-4` are strata of `FM-1` wherever the roster carries them, and standalone builds only where it does not.** R-15-067d fixes those three by name because they are the two largest bodies of generated bitfield code on the machine (R-15-067b), not because they are separate programs. Measuring them standalone changes the answer: a codec compiled alone has its own call sites, its own globals, and no share of the composed roster's merged functions, so its site-invariance profile is not the profile the dictionary will actually see. The rule is therefore:

- if the roster admits the component, the member is measured **in place**, as a provenance-selected stratum of `FM-1`, and the report records the stratum's site count;
- if the roster does not admit it, the member is measured **standalone**, and the report marks the row `standalone` so no reader takes its operand-class distribution for a composed one;
- a member that is neither in the roster nor separately buildable is a **rejection** under §9, not a blank cell. R-18-003c fixes these corpora by name, and a gating artifact absent from the report is a finding against that requirement.

**`FM-5` is derived and not built.** It exists as a named member because §0 lists the generated prologues, epilogues, calls, and global-address materializations as corpus content and because FD-3 and FD-4 are stated over sites rather than over an image; but it is the provenance join of §4 applied to `FM-1`, so it carries `FM-1`'s hash and adds a selector rather than a build.

**`FM-6` is the only member measured on the cycle axis, and it is not an image.** Its unit is a frame of a conformance stream, its instrument is the timing-annotated Sail model (M0.9), and its byte columns are `n/a` throughout.

---

## 3. The composition recipe

The recipe is the definition of "the composed image" that every byte column quantifies over. It is stated as an ordered pipeline because two of its steps are ordered by requirement rather than by convenience, and because a report must be able to say which step produced the artifact it hashed.

| Step | What it does | Governing | Recorded in the report |
| --- | --- | --- | --- |
| S1 | compile the roster to the **provisional** profile, one component at a time, with provenance sidecars on (§4) | R-15-014a, R-18-003a | backend commit, provisional profile revision, per-component source pins |
| S2 | whole-image **dead** elimination over the frozen component graph, typed callee sets, manifest and entry roots, and the capability-wiring table | R-13-010a | retained-closure size, roots count |
| S3 | whole-image **duplication** elimination: identical-function merging, link-time specialization of call sites the frozen graph fixes, and one shared service compartment in place of a per-consumer library | R-13-010b, R-13-010e | merged-function count, specialized-site count |
| S4 | **outlining and tail merging**, intra-compartment, over the admitted region classes of §5 | R-15-036o | per-region-class admissions and refusals with reasons |
| S5 | **link and compose** the position-fixed image; resolve every call and global-address site under the variant's form selection | R-15-036l, main-spec §13 | image layout hash, reachable-region parameter where an absolute form is in force |
| S6 | **select the dictionary** over this variant's histogram, by the variant's selection policy | R-15-036i, R-15-036k | realized size, entries, policy, per-stratum hit rate |
| S7 | **encode** to the bundle format and hash the result | R-15-036a, R-15-036j | encoded bytes, bundles, slots, padding slots, escapes |

Four rules bind the recipe, and each closes a way the measurement could be true and useless.

- **S3 precedes S6, and S4 precedes every decision but its own.** The stripping levers are partly substitutive with the encoding rather than additive, so they are measured composed and never multiplied, and they are ordered first (R-13-010e, R-15-036i). S4 is ordered ahead of FD-4 through FD-8 by R-15-036p.
- **One knob per variant.** A variant is the baseline recipe with exactly one decision's knob moved, recorded as the knob's id and the configuration diff. Two knobs moved in one build make the delta unattributable, and §9 rejects a variant pair whose recorded diff names more than one knob. The two joint pairs the register itself fixes, FD-1 with FD-2 and FD-3 with FD-4, are declared joint in the report and are the only permitted exceptions.
- **S6 runs inside every variant.** A candidate instrument changes the histogram S6 selects against, so a variant that inherits the baseline's dictionary has measured the instrument against a dictionary chosen for its absence. This is the contract's single most consequential methodological rule and the easiest one to skip, since skipping it makes every variant cheaper to build.
- **A closing pass fixes the realized dictionary.** After every decision in §6 is taken, the recipe runs once more at the admitted configuration, and *that* pass's S6 output is the realized dictionary the freeze records and the proof is taken with. The report's frozen-dictionary block cites the closing pass's configuration hash, and §9 checks it equals the admitted configuration.

**Reproducibility is part of the measurement, not part of the build system's hygiene.** Every artifact the report cites is rebuilt from its recorded pins by the CI gate and re-hashed; a hash that does not reproduce invalidates the report rather than the build, because a corpus nobody can rebuild is a corpus nobody can re-measure at the next amendment. This is the same reproducible-build property the checkers' bootstrap-root story already rests on (main-spec §9).

**Images built under the provisional profile are measurement artifacts and are neither deployed nor stored** (R-18-003c). The dictionary is a permanent freeze-time commitment of the same class as the capability format (R-15-036i, R-15-007d), and permanence attaches to the second act alone; the recipe therefore emits into a build tree that no signing or storage path reads.

---

## 4. The emitter-provenance schema

Operand class is a property of the emitter's intent, not of the emitted bits: after encoding, a slot holding a dictionary index is indistinguishable from any other, and after assembly a materialization pair is two instructions with no record of what produced them. The backend therefore **labels operand and region class before assembly** (§0), and the analyzer joins the labels to the link map and the encoded image rather than inferring them.

### The record

One sidecar record per emitted instruction site, emitted by the backend at the same point it emits the instruction, in a stable line-oriented or length-delimited form the analyzer streams.

```
site_id          stable within a compilation unit; the link map carries the same id
unit             compilation unit identity (source pin plus unit path)
compartment      the compartment the site lands in; outlining may not cross it
function         the enclosing function symbol before any merge
opcode           the canonical mnemonic emitted
operand_class    exactly one of OC-1 .. OC-5
producer         the pass and construct that emitted it (see below)
region_id        the outlining region this site belongs to, or none
region_class     exactly one of RC-1 .. RC-5, where region_id is set
ct_arm           set where the site lies on a secret-dependent arm under R-15-036f
knob             the variant knob whose setting caused this form, or none
```

`producer` is free text drawn from a closed enumeration the backend declares and the report reprints, because a site-varying stratum with no producer is a count nobody can act on: knowing that 6% of the stream is site-varying is useless next to knowing which pass emits it.

### Operand classes

R-15-036k's normative split is two-way, site-invariant against site-varying, and the reported split is that one. The five classes below are the strata the sidecar carries, so that a failing hit rate names its cause; every emitted site carries exactly one.

| Id | Class | What is in it | Dictionary behaviour |
| --- | --- | --- | --- |
| `OC-1` | site-invariant, operand-free | register-register forms, `nop`, fences, and every instruction whose whole encoding recurs | hits, by construction |
| `OC-2` | site-invariant, immediate-bearing | recurring constant immediates: the stereotyped `csc cs_i, off(csp)` frame saves at recurring register-and-offset pairs, small constants, fixed field specifiers | hits where the exact instruction recurs, immediate included (R-15-036a) |
| `OC-3` | site-varying, PC-relative code displacement | `cjal` targets, forward and backward branch displacements | misses by construction |
| `OC-4` | site-varying, PC-relative data or global materialization | the `auipcc` plus `cincoffset` pair (R-15-031b) and any other displacement-bearing global reference | misses by construction |
| `OC-5` | site-varying, composition-time absolute | the absolute call and global-address forms, present only in FD-4's absolute variant | site-invariant *per target*: one entry serves every site calling one callee (R-15-036l) |

`OC-5` is the class the whole of FD-4 turns on, and it is why the class is a provenance label rather than a post-hoc classification: an absolute target is a constant that recurs, so its instances become dictionary hits, while the PC-relative displacement they replace could not. The report's stratified hit rate is what makes that visible; an aggregate hides it, which is why R-15-036k forbids quoting one alone and §9 enforces the prohibition mechanically.

### The join

The analyzer consumes three inputs and produces one joined table: the sidecar stream from S1 and S4, the link map from S5, and the encoded image from S7. The join is by `site_id`, and its output is one row per emitted site carrying its class, its final address, its bundle and slot, whether it took an index or an escape, and which dictionary entry it took. **Every site must join.** A sidecar record with no image site, or an image site with no sidecar record, is a rejection under §9 rather than a rounding error: an unjoined site is a stratum count that is silently wrong, and the failure mode this whole schema exists to prevent is a hit rate that is precise and mis-stratified.

---

## 5. Admitted region classes

A region class is the unit FD-3 is measured and decided on, because R-15-036p requires a bytes-and-worst-case-cycles **pair per admitted region class** rather than one figure for the pass. The classes are admitted by construction, not discovered by the pass: outlining is intra-compartment, and only regions needing no frame of their own are profitable, a helper that must save and restore re-incurring the sequence the pass exists to remove (R-15-036o).

| Id | Region class | Why it is a class of its own |
| --- | --- | --- |
| `RC-1` | frameless prologue and epilogue idioms: the stereotyped multi-register save and restore sequences | this is the class that struck the multi-register instrument (R-15-036n), so its measured yield is the evidence for that strike |
| `RC-2` | shared epilogues reached by tail merging | R-13-010b names tail merging beside outlining, and its cycle cost is a branch rather than a call and a return |
| `RC-3` | frameless straight-line sequences, no call, no frame | the general residual R-15-036o assigns to software |
| `RC-4` | capability-derivation idioms: bounds-then-use sequences around `csetbounds` | FD-6's counterfactual is exactly the sequence this class removes, so measuring them apart is what keeps the two from being counted twice |
| `RC-5` | wire-format and accessor inner sequences: the bitfield access loops of `FM-2` through `FM-4` | FD-5's counterfactual sits inside this class for the same reason |

**Four refusal reasons are enumerated, and the report carries a count for each**, because a class whose yield is small because nothing qualified is a different fact from one whose yield is small because the transform did not pay.

- **crosses a compartment**: a helper and every site calling it must lie in one compartment; cross-compartment sharing stays on R-13-010b's own terms (R-15-036o).
- **needs a frame**: the profitability rule above.
- **changes an interface**: the construction is rejected if a merge or an outlining changes a rooted symbol, capability edge, interface, or proof obligation (R-13-010a, R-13-010b).
- **on a balanced arm**: a site whose `ct_arm` label is set is refused unless both arms of the branch are transformed identically, because constant-time balancing is an obligation over **encoded bundle count** (R-15-036f) and outlining one arm moves that count. The §5 constant-time checker re-clears the merged image either way; this refusal keeps the pass from handing it a violation to find.

---

## 6. The decisions

Each decision states its question, its corpus, its unit, its procedure, its threshold, its default when the threshold is not met, and the columns it owes the report. A threshold is **derived** where its number follows from a quantity the register already fixes, and **declared** where this contract chooses it; declared values are listed in §8 with their grounds, and the report reprints the values in force.

### FD-1 · The realized dictionary, its entry selection, and the site-varying policy

**Question** (R-15-036i, R-15-036k). The realized size N, the procedure that selects N entries from the composed image's histogram, and the policy for the site-varying class: selection by instance count alone, which admits single-use entries whenever indices remain, or a marginal-value rule reserving indices for recurring forms.

**Corpus and unit.** `FM-1` after S5. The measured unit is **encoded bits per instruction**, `encoded_text_bytes * 8 / instructions`, taken on the S7 output.

**Procedure.** Run S6 and S7 at each candidate N in the declared candidate set, under each of the two site-varying policies, at the FD-2 configuration under test. Report the full curve, not the chosen point: the freeze records a size, and a size recorded without the curve beside it cannot be re-judged at an amendment.

**Threshold, derived.** The density claim is that the encoding recovers what excluding `C` costs, so acceptance is against the *optimistic* `C` counterfactual: R-15-036 sets it at 70% of the canonical stream, and the canonical stream is 32 bits per instruction, so the bar is **22.4 encoded bits per instruction** measured on `FM-1`. The pessimistic counterfactual, 75% and 24 bits, is reported beside it and is not the bar. A configuration failing the bar fails the density claim R-15-036 rests the `C` exclusion on, which is a finding against the profile and not a number to round.

The register's break-even in *p*, 0.804 against the optimistic figure and 0.728 against the pessimistic one, is the same bar expressed through R-15-036h's slot model and R-15-036j's packing term. It is a **diagnostic here and not the acceptance test**, because the bytes are observed and the model is not: the report carries measured bits per instruction against the bar, and carries modelled bits per instruction beside it as the residual check of §8.

**Selection policy.** Whichever policy is realized, it is recorded with the freeze (R-15-036k). The report carries both policies' curves, because the difference between them is exactly the site-varying class's fate and that class is the density model's dominant risk factor.

**Headroom.** N is frozen with headroom and indices above the realized size trap (R-15-014, R-15-036i). The declared reserve is in §8; the report carries allocated entries, reserved indices, and the trapping range.

**Default.** There is none: the dictionary is the encoding, so FD-1 has no "leave it as it is" arm. A configuration that clears no candidate N is a failure of the freeze's precondition, reported as such.

**Columns.** `N`, `policy`, `entries_allocated`, `indices_reserved`, `instructions`, `bundles`, `slots_used`, `slots_padding`, `escapes`, `p_hit` per `OC-1` to `OC-5`, `p_hit_invariant`, `p_hit_varying`, `encoded_text_bytes`, `canonical_text_bytes`, `bits_per_instruction`, `bits_per_instruction_model`, `model_residual`, `lambda_realized`.

### FD-2 · Bundle, header, and slot widths

**Question** (R-15-036a). The bundle width, the header width *h*, and the slot count *k* at the reference instantiation of 128, 16, and 7, carried as a DSE parameter. This is the one structural item in the delta, and it allocates no opcode and changes no instruction semantics.

**The slot width is not free, and the contract says so rather than sweeping it.** Three constraints pin it. An escape is exactly two slots carrying one canonical 32-bit instruction **verbatim** (R-15-036a), so `2w >= 32` and `w >= 16`; any `w > 16` wastes `2(w - 16)` bits on every escape and buys index space the profile does not use, the dictionary already being bounded at 2^16 entries; and a slot must index the dictionary, so `w >= log2(N)`. The reference `w = 16` is therefore the only non-wasteful width, and the real knob is the pair `(h, k)` with `bundle = h + 16k`, subject to `h >= k` because the header carries one escape-start bit per slot. The declared candidate set in §8 is that pair, and a report sweeping `w` is reporting a wider space than the format admits.

**Corpus, unit, procedure.** `FM-1`; encoded bits per instruction; joint with FD-1, since the packing term λ is a function of *k* and the dictionary bound is a function of *w*. The sweep is the cross product of the declared `(h, k)` candidates with FD-1's N candidates and both policies, and it is run once, before the one-knob variants of FD-4 through FD-8.

**Threshold, derived.** The same 22.4 bits per instruction bar, plus a structural tie-break: among configurations clearing the bar within the declared indifference band, take the one whose realized λ is smallest, since padding is deterministic waste that buys nothing, and break a remaining tie toward the smaller bundle, which is the smaller fetch quantum and the smaller region-end waste.

**Columns.** `bundle`, `h`, `k`, `w`, plus FD-1's columns at that configuration, plus `lambda_bound` = `(2 - p) / (k - 1)` and `lambda_realized`.

### FD-3 · Outlining and tail merging, on two axes

**Question** (R-15-036o, R-15-036p). Which admitted region classes the backend's outlining and tail-merging pass is enabled for. This is not a delta item; it is the transform that produces the corpus every other byte-axis decision is measured against, and it is the one code-size lever that **may not be settled on the byte column alone**.

**Corpus and unit.** `FM-1` and `FM-5`; bytes removed on the byte axis, and **worst-case cycles added** on the cycle axis, per region class.

**Procedure.** Build the baseline with S4 disabled and one variant per region class with only that class enabled. For each, take encoded bytes from S7 and worst-case cycles from the timing-annotated Sail model over every partition containing an outlined site. Cycles come from §1's Sail timing table; **host timing is inadmissible** anywhere in this report (§0), and the report records the model revision the cycles were taken from.

**Threshold, derived and hard.** A region class is admitted iff it removes bytes **and** no partition's admitted slot must widen to hold the new worst case. A partition's capacity is its slot width under the static cyclic executive (R-07-032, R-07-037), so WCET inflation widens a slot or does not fit rather than degrading smoothly (R-15-036p): the acceptance number is therefore **zero slot widenings**, which is derived from the schedule's structure and not a judgment this contract could soften.

**Joint measurement with FD-4.** R-15-036p states the arithmetic and this contract makes it a column set. For a region of *n* instructions at *m* site-invariant sites, the region costs *nm* slots inline, `n + m + 1` outlined under a composition-time absolute call whose one target is one shared dictionary entry, and `n + 2m + 1` outlined under a PC-relative one whose per-site displacement is a site-varying two-slot escape. A two-instruction region therefore pays from four sites under the absolute form and never under the PC-relative one, and the report carries the per-class `n`, `m`, and all three slot counts so that a reader can check the inequality rather than take the verdict.

**Default.** Region classes not clearing the threshold are disabled, and the disabled set is recorded: `FM-1` for every later decision is built with the admitted set and no other.

**Columns.** Per region class: `regions_found`, `regions_admitted`, refusal counts for each of §5's four reasons, `sites_m`, `region_len_n`, `slots_inline`, `slots_outlined_abs`, `slots_outlined_pcrel`, `delta_bytes`, `delta_pct_encoded`, `wc_cycles_delta`, `slot_width_cycles`, `slot_headroom_cycles`, `slots_widened`.

### FD-4 · Call and global-address materialization form

**Question** (R-15-036l). Whether the emitted call and global-address-materialization forms are PC-relative or **composition-time absolute**, and, if absolute, the reachable code region its immediate can name.

**Corpus and unit.** `FM-1` and `FM-5`; encoded bytes, with the site counts of `OC-3`, `OC-4`, and `OC-5` beside them.

**Procedure.** Two variants over the FD-3-admitted baseline, differing in the form knob alone, each with S6 re-run: the absolute form makes one target one shared dictionary entry where every PC-relative displacement was a distinct miss, so the dictionary must be re-selected or the measurement scores the old histogram. Where an absolute form is under test, record the reachable-region parameter and the count of targets outside it that fall back to materialize-then-`cjalr`, since those sites are the form's real cost and are invisible in an aggregate byte figure.

**Threshold, declared: T-form.** An absolute form is admitted iff its byte delta against the PC-relative baseline is at least `T-form` of `FM-1`'s encoded text. The floor is low because the choice consumes no opcode space and adds no instruction: any absolute form admitted remains one canonical 32-bit instruction, and it adds no architectural state, no CSR, no `fence.t` flush-set member, and no target-membership structure (R-15-036l, R-15-036q).

**Default, from the register.** An immaterial measured delta **leaves the PC-relative forms in place** rather than carrying an absolute form on the argument alone (R-15-036l). The default is stated by the requirement, not chosen here.

**Columns.** `form`, `delta_bytes`, `delta_pct_encoded`, `reachable_region_bits`, `fallback_sites`, `oc3_sites`, `oc4_sites`, `oc5_sites`, `p_hit_varying`, plus FD-3's joint slot counts.

### FD-5 · The bitfield pair

**Question** (R-15-067d). Three decisions in one row: the field-specifier form, whether the two 6-bit immediates earn their encoding bits or a register-specified field suffices; whether the insert form `bfins` is carried; and whether the pair is carried at all.

**Corpus and unit.** `FM-1`, with `FM-2`, `FM-3`, and `FM-4` reported as separate strata, per R-15-067d's naming of them. Encoded bytes.

**Procedure.** Four variants over the FD-3-admitted baseline, each with S6 re-run: neither form; extract only; extract and insert with immediate specifiers; extract and insert with a register-specified field. The insert form's decision is **marginal, not joint**: it is admitted on its own delta *given* the extract form's admission, because the extract form collapses a shift-and-mask pair while the insert collapses a four-to-six-instruction sequence, and scoring them together lets the larger carry the smaller (R-15-067b).

**Threshold, declared: T-enc.** Each form is admitted iff its delta is at least `T-enc` of `FM-1`'s encoded text. The floor is the higher of the two because carriage spends custom opcode space, one Sail clause, one instruction-selection rule per production backend, and a review-gate rerun (R-15-067d, R-18-034).

**Default, from the register.** A measured delta immaterial against the §15 capacity budget **drops the instruction at the freeze** rather than carrying it into the frozen profile on the argument alone (R-15-067d).

**A cycle term is recorded and not scored.** The insert form's dependent chain is longer than adjacent-pair fusion collapses; R-15-067b says explicitly that this is not what admits the instruction and is not scored, so the report carries the cycle column for the record and the verdict reads the byte column.

**Columns.** `variant`, `delta_bytes`, `delta_pct_encoded` on `FM-1` and per stratum on `FM-2` through `FM-4`, `sites_extract`, `sites_insert`, `specifier_form`, `wc_cycles_delta` (recorded, not scored), `opcodes_consumed`.

### FD-6 · The further code-size candidate

**Question** (R-15-067e). Whether a `csetbounds` taking a large immediate length, in CHERIoT's form, is carried. It is a candidate and not a commitment, and the recorded expectation is that it is dropped.

**Corpus, unit, procedure, threshold.** As FD-5, with two variants, and measured **against R-15-036p's outlined corpus** as R-15-067e requires: the sequences it would collapse are `RC-4`'s, which FD-3 has already had its chance at, so measuring against an un-outlined baseline would credit this instrument with the outliner's yield. `T-enc` applies, on the same ground.

**Default.** Dropped.

**Columns.** As FD-5, plus `rc4_regions_admitted` from FD-3, so the substitution is visible in the same row.

### FD-7 · The indexed load and store's scale immediate

**Question** (R-15-007g). Whether the shift amount in `cld rd, cs1[rs2 << imm]` and its store form earns its encoding bits, or an unscaled index suffices because element strides are known where the slot plan is decided (R-08-011).

**Corpus and unit.** `FM-1`, with `FM-4` as a named stratum, the accessor surface being where indexed access concentrates. Encoded bytes.

**Procedure.** Two variants over the FD-3-admitted baseline with S6 re-run: scaled and unscaled. Beside the byte delta the report carries the **fraction of indexed accesses whose stride is a slot-plan constant**, because that fraction is the register's stated alternative ground and a byte delta alone cannot distinguish "the scale is unused" from "the scale is used where a constant would have served".

**Threshold, declared: T-form**, the instruction being admitted either way and the choice spending bits inside an existing encoding rather than opcode space.

**Default.** The Sail clause states one form (R-15-007g); where the delta is immaterial the unscaled form is taken, being the smaller encoding and the smaller model.

**Columns.** `form`, `delta_bytes`, `delta_pct_encoded`, `indexed_sites`, `sites_stride_constant`, `immediate_bits`.

### FD-8 · Frozen fusion-set membership

**Question** (R-15-031a). Which pairs are in the frozen fusion set, selected against the instruction mix this profile emits and not inherited from the general RISC-V fusion literature.

**What this instrument owes and what it does not.** Membership is a composition-time parameter of the §15 design-space exploration, which is deferred (main-spec §15, and the plan's §1). The decision is therefore not taken in this report. What is taken here is its **measured input**: the emitted adjacency histogram over `FM-1`, after S5, taken from the provenance join so that a pair's count is a count of what the backend actually emitted adjacently rather than of what a disassembler could pattern-match. The exploration cannot invent the mix it selects against, and the mix does not exist anywhere else.

**Threshold, declared: a candidate floor, not an admission.** A pair enters the reported candidate set at or above the declared adjacency share of §8. Admission is the exploration's, and the only obligation the freeze carries is R-15-034's: the fused set is frozen with the proof and listed in the timing-annotated Sail model, with no certificate, WCET bound, or constant-time statement re-derived on its account.

**Columns.** Per candidate pair: `pair`, `adjacent_sites`, `share_of_static_pairs`, `legal_under_profile`, `admitted` (from the exploration, or `pending`).

### FD-9 · `rcstep` carriage, on the cycle axis

**Question** (R-15-067h). Whether the fixed-latency range-coder step is carried, decided by the same single measured act as the byte instruments but on the cycle axis: the decoder's worst-case cycles per frame over the conformance streams, set against the §11 slot the media server is admitted at and the ceiling that slot declares.

**Corpus and unit.** `FM-6`, the conformance streams at the admitted tuples (R-15-238d, R-15-238c). Worst-case cycles per frame, from the timing-annotated Sail model. Byte columns are `n/a` throughout, and the row is carried in **this** report rather than a second one (§0).

**Procedure.** Two variants of the decoder over the same streams, with and without the instruction, at the same VLEN and the same admitted worker set and frame pool (R-12-084b). Take the worst case per frame per tuple, not the mean: the quantity the slot is admitted against is a bound.

**Threshold, derived and categorical.** Carriage requires that the instrument **moves the admission outcome**: there is at least one tuple in the declared ceiling table that the without-variant refuses and the with-variant admits, its worst case fitting the declared slot. An instrument that does not move that bound is dropped at the freeze rather than carried on the argument alone (R-15-067h), and a percentage improvement that changes no tuple's admission is exactly that case, since decode capacity is a ceiling declared at composition and refused above rather than degraded through (R-15-238c).

**Default.** Dropped. Contention is recorded either way: `rcstep` competes for the same uncontended custom opcode space as R-15-007e, R-15-067a, and R-15-069a, so the opcode ledger of §7 carries it whether it is admitted or not.

**Columns.** Per tuple: `format`, `level`, `resolution`, `frame_rate`, `wc_cycles_frame_without`, `wc_cycles_frame_with`, `slot_width_cycles`, `ceiling_conforms_without`, `ceiling_conforms_with`, `admission_moved`; and `bytes` columns `n/a`.

---

## 7. The report

One report, two renderings, generated together and never authored apart: a machine-readable record the gate of §9 reads, and a Markdown document a curator reads, generated **from** the record so the two cannot drift. It is published with the profile freeze, carrying the corpus manifest, the tool version, the thresholds in force, the per-extension deltas, and the realized choices (§0).

### Blocks

| Block | What it carries |
| --- | --- |
| `manifest` | corpus id and hash, analyzer version, backend and composer commits, Sail model revision the cycles came from, provisional profile revision, thresholds-in-force with their values |
| `corpus` | one entry per `FM-` member: hash, producer, pins, `in_place` or `standalone`, or the roster ground that excludes it |
| `recipe` | one entry per step S1 to S7: tool version, input hash, output hash, and the step's own recorded quantities from §3 |
| `provenance` | site counts for `OC-1` to `OC-5`, the two-way split, the producer enumeration, and the join residue, which must be zero |
| `regions` | one entry per `RC-` class: admissions, the four refusal counts, and the byte-and-cycle pair |
| `decisions` | one entry per `FD-` row: variants, columns as §6 lists them, threshold applied, verdict, and for FD-3 the nil-row treatment of R-15-036n |
| `dictionary` | the frozen block from the closing pass: realized N, allocated entries, reserved and trapping indices, policy, per-stratum hit rate, and the configuration hash it was selected at |
| `opcode_ledger` | custom encodings consumed by each admitted instrument, encodings remaining, and the trapping range (R-15-014) |
| `residuals` | anything measured and not decided, including FD-8's pending admission, with the artifact that will decide it |

### Skeleton

```json
{
  "manifest": {
    "corpus_id": "freeze-corpus-<n>",
    "corpus_hash": "<hash over member hashes, pins, and tool versions>",
    "analyzer_version": "<tools/ analyzer commit>",
    "sail_model_revision": "<revision the cycle columns were taken from>",
    "thresholds": { "T-enc": "<value>", "T-form": "<value>", "...": "..." }
  },
  "corpus":   [ { "id": "FM-1", "hash": "...", "mode": "in_place", "pins": { } } ],
  "recipe":   [ { "step": "S6", "tool": "...", "in": "...", "out": "..." } ],
  "provenance": { "OC-1": 0, "OC-2": 0, "OC-3": 0, "OC-4": 0, "OC-5": 0,
                  "invariant": 0, "varying": 0, "join_residue": 0 },
  "regions":  [ { "id": "RC-1", "admitted": true, "delta_bytes": 0,
                  "wc_cycles_delta": 0, "slots_widened": 0, "refused": { } } ],
  "decisions":[ { "id": "FD-4", "threshold": "T-form", "verdict": "pc_relative",
                  "variants": [ { "knob": "call_form", "columns": { } } ] } ],
  "dictionary": { "N": 0, "policy": "marginal_value", "config_hash": "..." },
  "opcode_ledger": { "consumed": [ ], "remaining": 0 },
  "residuals": [ ]
}
```

### Column conventions

- **A byte column is bytes of encoded text**, `FM-1`'s S7 output, never canonical bytes and never a file size. `canonical_text_bytes` is carried beside it for the `C` counterfactual and is labelled as such.
- **A cycle column is worst-case cycles from the timing-annotated Sail model**, with the model revision in the manifest. There is no host-timing column, and a report carrying one is rejected.
- **A cell where the axis does not apply carries `n/a`**, never a blank and never a dash: the house style spells a not-applicable cell `n/a`, and a blank cell is indistinguishable from an omitted measurement, which is the exact confusion §9 exists to catch.
- **An aggregate hit rate is never carried alone.** `p_hit_aggregate` is present only in a row that also carries the stratified split, per R-15-036k.
- **Every delta is signed from the baseline**, positive meaning the candidate saves, and every percentage is against that row's baseline `encoded_text_bytes`, stated in the row rather than assumed.

---

## 8. Declared parameters

These are the numbers this document chooses. Each has a ground and a stated way to be wrong; each is reprinted in the report's `manifest`; and a freeze taken at a different value is a freeze whose report says so, which is the whole point of collecting them here.

| Parameter | Value | Ground | What would change it |
| --- | --- | --- | --- |
| `T-enc`, materiality floor for a choice consuming custom opcode space or adding an instruction | 0.5% of `FM-1` encoded text | carriage spends opcode space, a Sail clause, a selection rule per backend, and a review-gate rerun, so the win must be visible against the §15 capacity budget rather than against measurement noise | a stated SRAM allocation quantum from the §15 exploration, which would let the floor be one quantum rather than a fraction |
| `T-form`, materiality floor for a choice among forms of already-admitted instructions | 0.1% of `FM-1` encoded text | the choice consumes no opcode space and adds no instruction, so the bar is only that the delta be real | the same quantum, or a demonstrated measurement noise floor above 0.1% |
| dictionary headroom reserve | at least 12.5% of N left unallocated at the freeze | the dictionary is a permanent freeze-time commitment invalidating stored objects wholesale (R-15-036i), and unallocated indices trap (R-15-014), so the reserve is cheap and its absence is not recoverable | a later amendment mechanism that made re-selection affordable, which R-15-036i currently rules out |
| FD-2 candidate set | `(h, k)` in {(16, 3), (16, 7), (16, 15)}, `w = 16`, `bundle = h + 16k` | `w` is pinned by the two-slot verbatim escape and the 2^16 dictionary bound (FD-2); `h >= k` by one escape-start bit per slot; power-of-two bundles keep fetch alignment trivial | a change to the escape rule, which is a structural amendment rather than a second-act decision |
| FD-1 candidate set for N | powers of two from 2^10 to 2^16 | the curve, not the point, is what the freeze records; the top is the slot width's bound | nothing short of a slot-width change |
| indifference band for the FD-2 tie-break | 0.5% of bits per instruction | below it the configurations are indistinguishable on the axis that decides them, so the structural tie-breaks (smaller λ, then smaller bundle) take over | a measured run-to-run variance above the band, which would itself be a finding, the pipeline being deterministic |
| model residual tolerance | 2% of measured bits per instruction | R-15-036h and R-15-036j are a model with a measured input, so a residual outside the band is a defect in the model | a corrected model, at which point the band is re-derived rather than widened |
| FD-8 candidate floor | 0.5% of static emitted adjacent pairs | the candidate set is an input to an exploration, not an admission, so the floor only keeps the histogram's tail out of the report | the exploration's own selection pressure, which supersedes it |

---

## 9. The CI gate

CI rejects a freeze whose report omits a required corpus member, provenance stratum, region class, byte column, or worst-case-cycle column (§0). Stated as predicates over the record of §7, so that the rejection is mechanical and its reason is nameable.

| Id | The gate rejects when | Governing |
| --- | --- | --- |
| `G-1` | a corpus member some decision feeds is absent, and no roster ground is recorded for its absence | R-18-003c |
| `G-2` | a provenance stratum `OC-1` to `OC-5` has no count, a zero being a value and an absence being a rejection, or `join_residue` is nonzero | R-15-036k |
| `G-3` | an admitted region class lacks either half of its bytes-and-worst-case-cycles pair | R-15-036p |
| `G-4` | a delta item of R-15-014a has no decision row, or a decision row carries a blank where §6 requires a column, `n/a` being the only permitted non-value | R-15-014a |
| `G-5` | a decision row names a choice outside R-15-014a's closed delta, including a *measured* multi-register save and restore, which is an amendment and not a freeze | R-15-014a, R-15-036n, R-18-034 |
| `G-6` | the recorded order violates §1: FD-3 not first, or a byte-axis decision whose corpus hash is not the post-S4 image's | R-15-036i, R-15-036p |
| `G-7` | a recorded artifact hash does not reproduce from its recorded pins | main-spec §9 |
| `G-8` | a variant pair's recorded configuration diff names more than one knob, outside the two declared joint pairs | this contract, §3 |
| `G-9` | a cycle column carries no Sail model revision, or the report carries a host-timing column | §0 of the plan, R-15-036p |
| `G-10` | an aggregate hit rate appears in a row carrying no stratified split | R-15-036k |
| `G-11` | the frozen dictionary block's configuration hash is not the admitted configuration's, so the realized dictionary is not the closing pass's | R-15-036i |
| `G-12` | a threshold value in the report differs from §8 without the difference being recorded as such | this contract, §8 |

Two of these are worth their own sentence. `G-5` is what keeps the report honest about the strike: R-15-036n's candidate is struck ahead of the freeze, so a byte column against it is evidence that somebody re-opened a closed decision without the review gate. `G-11` is what keeps the realized dictionary from being an artifact of the sweep rather than of the admitted machine, which is the failure the closing pass of §3 exists to prevent.

---

## 10. What this contract does not decide, and what it owes elsewhere

- **It takes no decision in the delta.** Every verdict in §6 is produced by running the instrument, and this document fixes only the corpus, the procedure, and the number. A freeze report is what decides; this is what makes its decision re-checkable.
- **FD-8's admission is the exploration's.** The instrument supplies the histogram; the frozen fusion set is a composition-time parameter of the §15 design-space exploration, and until that exploration runs, the report carries the row as `pending` in `residuals` rather than as a verdict.
- **FD-9 depends on two milestones this contract does not schedule.** The worst-case cycles per frame are taken from the timing-annotated model (the plan's M0.9) at a class parameterization (M0.8), so the `FM-6` row cannot be filled before both land. That is an ordering fact, not a threshold, and it belongs in the plan rather than here.
- **The bound-directed lowering runs against the emulator-measured table until the WCET cost-annotation pass lands** (R-18-014c, and the plan's scope cut). Where FD-3's cycle column and that table disagree, the Sail model is the reference: the table is a measurement of the same machine, and R-18-014d already forbids a lowering choice that would displace another admitted component from the capacity budget.
- **Three corrections are owed to §0 of the implementation plan**, which is the text this document instantiates. Its ordered report act names the single-check multi-register save and restore, which R-15-036n strikes ahead of the freeze, so the row is a nil row and not a measurement; and it omits two rows R-15-014a's delta carries, the further code-size candidate of R-15-067e and the fusion-set membership of R-15-031a. This contract carries all three in the shape the register fixes, and the plan's §0 is amended to match.
- **`w = 16` is derived, not swept.** R-15-036a carries the slot width as a DSE parameter, and FD-2 shows that the two-slot verbatim escape and the 2^16 dictionary bound leave it no room. The delta item is unchanged, the widths still being decided at the final freeze; what narrows is the search, and the narrowing is stated here so that a report sweeping `w` is recognizable as reporting a space the format does not admit.
