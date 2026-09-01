# The Typed IDL Profile

> **What this is.**
> This document is the one typed interface-definition profile R-12-010 fixes: the type constructors every §12 server protocol and capability manifest is stated in, the wire-format mapping those types are carried by, the obligations each definition declares, and the subset a generated Coq interface skeleton is stated over.
> It is the artifact row 3 of [the crown-jewel inventory](crown-jewels.md) names, `CJ-IDL`, conferred by R-12-013.
>
> **Normative for the profile; not a derived view.**
> [The frozen instruction-set profile](isa-profile.md), [the absence contract](absence-contract.md), [the crown-jewel inventory](crown-jewels.md), and [the coverage matrix](coverage-matrix.md) are derived views of [requirements-register.md](requirements-register.md) and state no obligation of their own.
> This document states obligations of its own, as numbered requirements carrying acceptance criteria, in the shape [the typed assembly language](typed-assembly-language.md) already uses one artifact over.
> Where this document and the register disagree about a VerifiedOS obligation, **the register governs and this document is defective**; where they disagree about the profile's own language, this document governs.
> It decides nothing the register decides. Where the register is silent on a question the profile cannot avoid answering, the answer is a **declared parameter** collected in §8 with its ground and what would change it, rather than a sentence buried in §2 or §4.
>
> **Normative form.**
> Every obligation is a numbered requirement of the form `**IDL-nnn** MUST | MUST NOT | IS:` carrying one `· Accept:` line and one `· Trace:` line. Prose around them is rationale and binds nothing. Identifiers are permanent: a retired requirement is struck in place and its identifier is never reused.
>
> **Section references.** A bare `§n` in this document names a section **of this document**. Where a sentence names the register's section or the specification's, it says so. That is [the differential corpus](differential-corpus.md)'s device and it is needed here because §12 of the register, §12 of the specification, and this document's own sections meet on the same page.
>
> **The wire-format mapping is the crown jewel, and its row is not flipped here.**
> §4 is the mapping R-12-013 confers crown-jewel status on. Flipping row 3's status is an edit to [the crown-jewel inventory](crown-jewels.md), which is an act R-05-150's review gate reads; this document reports the row as ready and does not take it.
>
> **Nothing here is built.**
> No generator, no parser, no marshalling code, no Coq skeleton, and no interface declaration exists in this repository. This document is the specification those artifacts are written against, and authoring it relocates that work rather than reducing it.

---

## 1. The start-from, and what survives the read

R-12-010 says **fork-and-frozen** and names no artifact. The register is silent on what the fork is a fork of; the specification's §12 prose says *WIT-derived* and [inspirations.md](inspirations.md) splits the intent in two, a WIT-derived type layer over a FIDL/Zircon-channel wire layer. Neither is the artifact the review gate audits, so naming a start-from is a maturity claim under R-18-001a with no register owner, and it is taken here as a declared parameter (§8) rather than as a reading of the register.

**IDL-001** IS: The type layer of this profile is a fork of **WIT**, the interface-definition syntax of `WebAssembly/component-model`, taken at its own `design/mvp/WIT.md`. The wire layer of this profile is **authored fresh** over the §12 ring data plane and is a fork of nothing.
· Accept: every constructor row of §2 names WIT's own spelling or is marked as this profile's own; no row of §4 is attributed to an upstream.
· Trace: §2, §4, §8

### 1.1 The terms, read at each upstream's own licence file

**A licence is read at the milestone that would incorporate the upstream, at that upstream's own licence file, and never inferred from its lineage** (R-18-001a). Both readings are dated **2026-08-31** and are recorded in [THIRD-PARTY.md](../THIRD-PARTY.md), which is where their terms live; this section states only what the readings decided for the profile.

Both instruments are permissive, non-reciprocal, and carry no field-of-use restriction, so **the arm this repository has taken three times does not engage.** That arm refuses a term reaching a shipped artifact and contains a term reaching a build-time producer; a wire-format mapping is the first kind, and neither read produced a term to refuse or to contain. Nothing is incorporated in either direction: this repository tracks no file, no URL, no integrity hash, and no gitlink of either upstream.

**IDL-002** MUST: No text, grammar file, schema, or generated artifact of either upstream is copied, vendored, or transcribed into this repository. What the type layer takes from WIT is a **vocabulary of constructor names and their intended meanings**, which is a discipline rather than an artifact.
· Accept: no tracked file of this repository is derived from an upstream interface-definition source, and [THIRD-PARTY.md](../THIRD-PARTY.md) carries neither upstream in its vendored, fetched, or submodule tables.
· Trace: §1, §2

### 1.2 Why the wire layer is authored rather than forked, and the ground is technical

WIT's own wire format is the Component Model's **Canonical ABI**, which is stated over Core WebAssembly linear memory: values flatten to `i32`, `i64`, `f32` and `f64`, and lifting and lowering run through a module's own memory with a realloc callback. This platform declines Wasm as an execution target anywhere (R-05-084 and the specification's §14), carries no linear-memory sandbox, and moves authority out of band as session-table indices rather than through memory (R-12-006, R-12-007). The Canonical ABI therefore has **no machine here to be stated over**, and forking it would carry a mapping whose every term names a substrate this design does not have.

That is also why `CJ-IDL` confers on the mapping and not on the type layer: the layer that is a fork is the one with an upstream to be read against, and the layer that must be authored is the one the review gate must read.

### 1.3 What the freeze is, as an act

**IDL-003** IS: The fork is a **subset-and-delete** of the vocabulary §2 names, and the freeze is **this document's own version**. A change to §2's constructor set, to §3's declaration obligations, or to §4's mapping is an amendment carrying a review-gate event, in the shape R-18-034 fixes for the register and R-05-135b fixes for a pinned language version, and never a transparent upgrade from an upstream's later edition.
· Accept: this document declares one version; a generated artifact records the version it was generated against; no artifact is admitted against an unversioned profile.
· Trace: §8

**IDL-004** MUST NOT: No later edition of the upstream reaches this profile by inheritance. A constructor the upstream adds is absent here until an amendment adds it, and a constructor the upstream removes stays here until an amendment removes it.
· Accept: no row of §2 cites an upstream edition as its ground; every row cites a requirement of the register or a parameter of §8.
· Trace: §2, §8

**The version is this document's own and nothing in the register pins it.** R-05-135a pins [the typed assembly language](typed-assembly-language.md) by name and R-05-135b makes a version bump a review-gate event carrying a fresh reading; R-12-010 pins no artifact at all. So the amendment discipline IDL-003 declares of this document binds this document and nothing else until a register act names it. That is the headline finding of this item and it is reported rather than closed.

---

## 2. The type constructors

R-12-012 restricts the profile to closed variants, no recursion, and an explicit bound on every list and string. It does not enumerate what constructors exist, so **the table below is closed by this document and by nothing the review gate audits** (§8). Every row is decided by a requirement or by a declared parameter; nothing is deleted on taste.

**Standing** is `admitted` where the constructor is carried as the upstream states it, `narrowed` where it is carried under a restriction this table names, and `deleted` where no declaration may use it.

| Id | Constructor | Standing | Decided by |
| --- | --- | --- | --- |
| `TC-1` | `u8`, `u16`, `u32`, `u64`, `s8`, `s16`, `s32`, `s64` | admitted | fixed width, so no bound is owed (R-12-012) |
| `TC-2` | `bool` | narrowed: exactly two admissible encodings, one per value | R-05-051b |
| `TC-3` | `char` | narrowed: a Unicode scalar value, surrogates excluded | R-05-051b |
| `TC-4` | `string` | narrowed: an explicit bound and one declared encoding | R-12-012, R-05-143, §8 |
| `TC-5` | `list<T>` | narrowed: an explicit bound on the element count | R-12-012, R-05-143 |
| `TC-6` | `tuple<T, ...>` | narrowed: fixed arity, fixed member order | R-12-012 |
| `TC-7` | `record` | narrowed: a fixed field set in a fixed order, no optional field beyond `TC-11` | R-05-051b |
| `TC-8` | `variant` | narrowed: closed, every case enumerated at the definition | R-12-012 |
| `TC-9` | `enum` | narrowed: closed, no open-ended value space | R-12-012 |
| `TC-10` | `flags` | narrowed: a closed flag set of declared width, no reserved bit | R-12-012, R-05-051b |
| `TC-11` | `option<T>` | narrowed: one presence encoding | R-05-051b |
| `TC-12` | `result<T, E>` | narrowed: relevance-graded at its definition | R-18-016, R-05-097 |
| `TC-13` | `resource` | narrowed: two declared readings, control-plane and data-plane | R-12-010, R-12-006, R-12-007, §8 |
| `TC-14` | `borrow<T>` and the owned handle | narrowed: a borrow is valid for one operation and never outlives it | R-12-006, R-12-099 |
| `TC-15` | `future<T>` | deleted | unbounded in time, and no admitted transport carries it (R-12-093, R-12-098) |
| `TC-16` | `stream<T>` | deleted | unbounded in length (R-12-012, R-05-143) |
| `TC-17` | `map<K, V>` | deleted | unbounded, and no declared key order, so no canonical encoding (R-12-012, R-05-051b) |
| `TC-18` | any type naming itself through any chain of definitions | deleted | R-12-012, R-05-143 |
| `TC-19` | an open or extensible variant, and any accept-and-ignore case | deleted | R-12-012, R-05-051b |
| `TC-20` | `f32`, `f64` | deleted | §8, on R-05-051b's one-encoding-per-value rule |
| `TC-21` | the `@since`, `@unstable` and `@deprecated` gates | deleted | a frozen profile has one version and R-18-034 owns its motion |

**IDL-005** MUST: A declaration uses only the constructors §2 marks `admitted` or `narrowed`, under the narrowing its row states.
· Accept: an admission checker reading a declaration that uses a deleted constructor rejects it; the empty use of a deleted constructor is decidable syntactically, no constructor here being introduced by inference.
· Trace: §2, §6

**IDL-006** MUST: Every `list` and every `string` declares a bound at its own definition, and the bound is a **sound existence condition** rather than a claim of tightness (R-05-105): a value shorter than the bound is not a defect and the bound is not sharpened by measurement.
· Accept: no declaration carries an unbounded former; no proof over a declaration reads a bound as an equality.
· Trace: §2, §3.5

**IDL-007** MUST NOT: No type admits an unbounded value, and no type is recursive.
· Accept: the constructor graph over a declaration's type definitions is acyclic, and every former of `TC-4` and `TC-5` carries its bound; this is R-12-012's own acceptance criterion decided over §2's closed set.
· Trace: §2

**Three deletions are worth a sentence each, because each removes something an interface author will reach for.** `TC-17`'s map has no declared key order, so one association carries several admissible byte strings and there is nothing for a canonicity theorem to be stated over; a declaration that wants one uses a bounded `list` of a two-field `record` and states the order it is sorted in. `TC-15` and `TC-16` are the concurrency formers, and what replaces them is the ring's own lifecycle: a request receives exactly one terminal completion (R-12-093), and a repeated result is a repeated request rather than a stream inside one. `TC-20` is the one deletion whose ground is a parameter rather than a requirement, and §8 carries both arms.

---

## 3. What every definition carries

Five obligations attach **at a type's or an operation's definition** rather than at a call site, and that placement is what R-18-016 buys: the net-new work sits at the interface definitions rather than at every call site, and the front end propagates from there.

### 3.1 The flow labels

**IDL-008** MUST: Every type definition carries a **confidentiality label** and an **integrity label**. The labels are declared at the definition and are not restated per operation or per call.
· Accept: no type definition is admitted without both labels; the IDL-to-Coq generator emits the matching flow predicates and a cross-domain server's Tier-1 proof carries flow theorems against them (R-12-011).
· Trace: §3.1, §6

**The lattice the labels are drawn from is stated nowhere.** R-12-011 requires the labels and names no label set, no order, no join, and no answer to whether a label is a wire field or a composition-time attribute; the security policy model that would own such a lattice is row 2 of the crown-jewel inventory, `CJ-NI`, and reads `not authored`. This profile therefore declares the **place** the labels sit and states the obligations over an arbitrary lattice, and it invents no label set (§8).

**IDL-009** MUST NOT: No label of this profile is carried on the wire. A label is a property of the declaration and of the generated typing.
· Accept: no row of §4 encodes a label; the labeling is what defines secret-labeled material for IDL-borne material and is one source of the label rather than the definition of the population (R-12-011).
· Trace: §3.1, §4

### 3.2 The relevance grade

**IDL-010** MUST: Every **fallible result type** declares itself relevance-graded **at its own definition**, and nowhere else.
· Accept: the declaration carries the grade; no call site re-declares it; the front end propagates from the definition (R-18-016).
· Trace: §3.2, §6

**IDL-011** IS: The content of the grade is R-05-097's: weakening denied, contraction allowed, so every error verdict is consumed at least once and a derivation that drops a graded value fails to type-check.
· Accept: this profile states the placement of the grade and never a second definition of what the grade is.
· Trace: §3.2

**IDL-012** MUST NOT: The generated bindings and the generated Coq skeleton admit **no wildcard elimination** at a relevance-graded result. Discarding a verdict requires an explicit elimination that names the outcome.
· Accept: a generated binding contains no `_`-bind at graded type, and the typed discard form the generator emits is auditable (R-05-099).
· Trace: §3.2, §6

**IDL-013** MUST NOT: This profile adds no member to R-05-098's closed list of relevance-graded result kinds. The IDL call outcome is that list's member; the list is closed by amendment to the register.
· Accept: no requirement of this document asserts the grade of a result kind outside that list.
· Trace: §3.2

**Which result types carry the grade is a parameter.** R-05-098's list names *IDL call outcomes* as one member, and R-12-093 admits a per-operation closed refinement variant beside the common status set; whether each refinement is separately graded at its own definition in R-18-016's sense, or inherits the grade of the common set, is undecided by the register. §8 carries the value this profile takes.

### 3.3 The receiver-validation obligation

R-12-012a is the entry that keeps a declared type from being read as a statement about meaning: a declared type bounds what a value *is* and never what it *means to the receiver*, and capability bounds do not close the difference. The register requires the IDL to declare which received values carry the obligation and says nothing about the form that declaration takes, so the vocabulary below is this document's (§8).

**IDL-014** MUST: Every field of every received type carries a **validated-at-use marker**, set where the receiver uses the value as an index, a length, an offset, or a selector into its own state.
· Accept: the marker is per field rather than per operation, which is the granularity R-12-012a's own wording carries; the Tier-1 proof discharges the obligation at the receiver and never inherits it from a sender's compliance.
· Trace: §3.3, §6

**IDL-015** MUST: An operation whose received values carry **no** marker declares that emptiness as an explicit claim.
· Accept: the empty case is a claim the checker reads rather than a default it assumes, so an interface marking nothing is admitted only where no received value is used as an index, length, offset, or selector (R-12-012a); an operation with neither markers nor the claim is rejected rather than read as empty.
· Trace: §3.3

### 3.4 The initialization state of a delegated buffer

**IDL-016** MUST: Every delegated buffer type declares its **initialization state**, and the state rides the message type and the manifest's import and export tables.
· Accept: no delegated buffer arrives without a declared initialization state, and a copy-once parser writes its fixed destination buffer whole (R-05-124).
· Trace: §3.4, §5

### 3.5 The bounds, and what a magnitude is

**IDL-017** IS: Every composition magnitude of a declaration is a **field rather than a figure**: the number of operations an interface carries, the number of types, the number of fields of a record, the number of cases of a variant, the number of imports and exports of a world, and every declared bound of `TC-4` and `TC-5`.
· Accept: no figure of this kind is written in this document; each is a field of the declaration and of the generated artifact.
· Trace: §2, §8

**Nothing in the register bounds the size of a declaration.** R-05-143 bounds every recursive former and R-12-012 bounds every list and string, and both are bounds on **values**; the number of operations, types, fields, or worlds a declaration carries is not a runtime value and no entry bounds it. IDL-017 is the idiom the landed Gallina items already use, stated here so the absence reads as a boundary rather than a gap.

### 3.6 The per-operation records

**IDL-018** MUST: Every operation variant of a declaration carries the per-variant record R-12-101 requires, as a **declaration form with one field per member of that entry's list and no values**.
· Accept: R-12-101 states the list and this document states only the form; a generated interface artifact carries the record with its composition-time values, and the composition proves the joint bound that entry requires.
· Trace: §3.6, §4, §6

**IDL-019** MUST: Every cancellable operation declares the cancellation points, commit point, cleanup bound, DMA-quiescence rule, and maximum time to terminal completion R-12-097 requires, and an operation carrying no such declaration is **non-cancellable**.
· Accept: the declaration form exists in the profile and its absence is a property of the operation rather than an omission the generator repairs; deadlines are drawn from the interface's finite deadline classes.
· Trace: §3.6, §4

---

## 4. The wire-format mapping

*This is the mapping R-12-013 confers crown-jewel status on, and row 3 of [the crown-jewel inventory](crown-jewels.md) names. It is a specification that must be authored rather than a proof to be discharged: a wrong mapping yields a correct proof of the wrong property, which is R-17-016's residual and the reason this section is what the review gate reads.*

Three things the register already fixes position this section, and it cites them rather than restating them.

- **Parsing.** Every attacker-facing wire format is parsed by a verified copy-once Narcissus parser and the parser proof is against the descriptor rather than against any prose (R-05-042, R-05-046). A descriptor arriving from another compartment is attacker-facing by R-12-008a's Byzantine-peer posture, which assumes no protocol compliance beyond admission of the typed binary.
- **Canonicity.** A descriptor whose encoding is ever an input to a signature, a hash used as a name, a content address, a cache key, or an equality test carries a machine-checked canonicity theorem and admits no encoding slack (R-05-051a, R-05-051b), and a format that cannot carry one is refused that role rather than used with a caveat (R-05-051c).
- **Transport.** The transport is the §12 ring data plane, handles travel out of band, and ring pages are mapped without capability-store permission (R-12-005 through R-12-009, R-12-091, R-12-092).

### 4.1 The standing position

**IDL-020** MUST: The mapping is authored to R-05-051b's no-slack rule **whole**, whether or not a given encoding sits on an identity-bearing path: one admissible length form, one presence encoding per optional field, fixed field order, no free padding, no reserved bits, and no accept-and-ignore field.
· Accept: no value of any type §2 admits has a second admissible encoding under §4; a non-canonical input is a decode failure and is never normalized into the canonical encoding of the same value.
· Trace: §4.2, §8

**IDL-021** MUST: Every descriptor generated from this mapping carries an R-05-051a **canonicity theorem** beside its Narcissus correctness pair.
· Accept: the theorem quantifies over the whole admissible language rather than a corpus, and the correctness pair alone is never cited for it, the two directions being separate theorems.
· Trace: §4.1, §6

**Whether the mapping is on an identity-bearing path is undecided by the register**, and IDL-020 takes the stronger reading rather than waiting for the answer. R-13-003 puts the capability manifest's §12 interface descriptor inside the content-addressed admitted artifact, which makes that descriptor's own encoding look identity-bearing; R-05-051c's enumerated site list names the pack reader, the typed manifest, the content address and the deterministic-reuse key and does not name a live IDL call. §8 carries the reading and what taking the weaker one would have bought.

**IDL-022** MUST: Every descriptor of this mapping is parsed by a verified copy-once Narcissus parser generated from the type source, and no parser for it is hand-written.
· Accept: the descriptor is an output of §6's generator rather than an artifact authored beside it; the set of hand-written attacker-facing parsers over this mapping is empty.
· Trace: §4.1, §6

### 4.2 The encoding, per constructor

**The encoding is packed and alignment is the destination buffer's rather than the wire's.** A copy-once parser writes its fixed destination buffer whole (R-05-124), so interior padding buys nothing on the wire and would be exactly the free padding R-05-051b forbids. Multi-byte scalars are little-endian, which is the machine's own order.

| Id | Constructor | Encoding |
| --- | --- | --- |
| `WF-1` | `TC-1` fixed-width integers | the declared width in bytes, little-endian, two's complement for the signed forms, no padding before or after |
| `WF-2` | `TC-2` `bool` | one byte, `0` or `1`; any other byte is a decode failure |
| `WF-3` | `TC-3` `char` | four bytes, little-endian, an unsigned Unicode scalar value; a surrogate code point or a value above the scalar range is a decode failure |
| `WF-4` | `TC-4` `string` | a length in the declared bound's width, then exactly that many bytes of the declared encoding; a length above the bound, and any sequence the declared encoding does not admit, is a decode failure |
| `WF-5` | `TC-5` `list<T>` | a count in the declared bound's width, then exactly that many `T` encodings back to back; a count above the bound is a decode failure |
| `WF-6` | `TC-6` `tuple`, `TC-7` `record` | the members in declaration order, no tag, no count, no interior padding |
| `WF-7` | `TC-8` `variant`, `TC-9` `enum` | a case index in the declared discriminant width, first, then the case's payload where it has one; an index at or above the declared case count is a decode failure |
| `WF-8` | `TC-11` `option<T>` | discriminant `0` and no payload bytes, or discriminant `1` and `T`'s encoding; there is no second presence encoding |
| `WF-9` | `TC-12` `result<T, E>` | discriminant `0` and `T`'s encoding, or discriminant `1` and `E`'s encoding |
| `WF-10` | `TC-10` `flags` | a bit field of the declared width, bits in declaration order; every bit above the declared flag count is zero and a set one is a decode failure |
| `WF-11` | `TC-13` `resource`, data-plane reading | a session-table index of the declared index width, plus offset, length, direction, and declared content type (R-12-092) |
| `WF-12` | `TC-13` `resource`, control-plane reading | no wire bytes: the capability travels out of band and the encoding carries nothing that names it (R-12-006, R-12-007) |
| `WF-13` | `TC-14` `borrow<T>` | the data-plane reading of `WF-11`, valid for one operation, revoked with the session generation (R-12-099) |

**IDL-023** MUST: A **length form is one form.** The width of every length and count field is the smallest of one, two, or four bytes that holds the declared bound, and the width of every discriminant is the smallest of one, two, or four bytes that holds the declared case count.
· Accept: no declaration admits two spellings of one length; the width is a function of the declared bound alone and is recorded in the generated artifact.
· Trace: §4.2

**IDL-024** MUST: Every descriptor variant of one interface encodes to **exactly** that interface's declared descriptor size, a variant shorter than the slot being followed by a declared zero fill.
· Accept: a fill byte that is not zero is a decode failure, so the fill is not free padding and carries no value; the descriptor size and alignment are composition-time constants of the generated interface artifact (R-12-091).
· Trace: §4.2, §4.3

**IDL-025** MUST NOT: No field of any encoding under §4 is a path, a raw address, a capability encoding, an executable name, a recursive value, or an unbounded collection.
· Accept: no descriptor field is dereferenceable as an address (R-12-006), and rings carry indices and never capabilities (R-12-007); this is R-12-092's own refusal decided over §2's closed constructor set.
· Trace: §4.2, §2

**IDL-026** MUST NOT: There are **no reserved bits and no reserved fields**. A field a later interface version adds is an amendment under IDL-003 producing a new declared version, never a reserved bit spent.
· Accept: an unknown tag or a reserved flag produces one of R-12-093's defined refusal completions rather than a fallback interpretation (R-12-092).
· Trace: §4.2, §1.3

### 4.3 The ring schema and its lifecycle

**IDL-027** IS: The common ring schema and lifecycle R-12-091 through R-12-101 state are **content of this mapping** and not a second normative ring-semantics artifact beside it. §4.3 is where that schema lands.
· Accept: this is R-12-091's own acceptance criterion; no artifact of this repository states ring semantics normatively outside this document.
· Trace: §4.3

**IDL-028** MUST: A descriptor is a member of its interface's closed variant under `TC-8`, and a completion carries a status from R-12-093's closed common set, which that entry states and this document cites.
· Accept: an interface refines the statuses with a closed operation-specific result variant under `TC-8` and cannot alter their lifecycle meaning; no requirement here restates the status set, the figure being one entry's to state and every other site's to cite (R-05-152).
· Trace: §4.3, §3.2

**The register owns the membership of every enumeration below and this section owns the encoding and the declaration form.** Where a requirement here says *the members that entry enumerates*, that is deliberate: a list written twice is a list free to drift, and §9's closing paragraph states the rule this section keeps.

#### 4.3.1 What a ring declaration declares

**IDL-050** MUST: Every ring instance declares the composition-time constants R-12-091 enumerates, as fields of the declaration with no value fixed here.
· Accept: the constants appear in the generated interface artifact; capacity is an admission parameter rather than a runtime negotiation (R-12-095), and no figure of this document states one.
· Trace: §4.3.1, §3.5

**IDL-051** MUST: A ring header is exactly the four words R-12-091 names, in a fixed order, and carries nothing else. The first three are R-12-008a atomics and the generation word is immutable between reinitializations.
· Accept: a header carrying a fifth word, a counter, or a flags cell is not this schema's header; §4.2's packed rule does not apply to the header, whose cells are separately addressed atomics rather than fields of one encoding.
· Trace: §4.3.1

**IDL-052** MUST: Indices are interpreted modulo the declared capacity, with sequence information distinguishing full from empty, and **no implementation infers validity from descriptor contents**.
· Accept: this is R-12-091's own criterion; a reader that decides occupancy by inspecting a slot rather than by reading the indices is refused.
· Trace: §4.3.1

#### 4.3.2 The descriptor and the completion

**IDL-053** MUST: A descriptor carries exactly the members R-12-092 enumerates, each encoded by the row of §4.2 its kind names: the operation tag and the flag set by `WF-7` and `WF-10`, the request identifier and the operation-specific scalars by `WF-1`, each buffer reference by `WF-11`, and the deadline by `WF-8` over the interface's finite deadline classes.
· Accept: no member is encoded by a row §4.2 does not carry, and IDL-025's refusal decides every field kind R-12-092 forbids.
· Trace: §4.3.2, §4.2

**IDL-054** MUST: The server validates bounds, permissions, direction, content type, and generation against the pre-delegated session table **before** the operation becomes eligible to execute, and a validation failure produces one of R-12-093's defined refusal completions rather than a fallback interpretation.
· Accept: the obligation is the receiver's under §3.3 and is never inherited from a sender's compliance; the generated artifact carries the marked fields as the obligations IDL-042 states.
· Trace: §4.3.2, §3.3

**IDL-055** MUST: Every accepted request receives exactly one terminal completion carrying the members R-12-093 enumerates.
· Accept: teardown is represented out of band by revocation plus a generation change and not by a status; no separate server-unavailable status exists.
· Trace: §4.3.2

#### 4.3.3 The lifecycle

**IDL-056** MUST: A request slot advances the monotone lifecycle R-12-094 states, in that entry's own order, and the successor relation is a **function**: each state has at most one successor and the last has none.
· Accept: the generated artifact carries the states and the successor relation emitted from R-12-094's own sentence rather than transcribed beside it, so a state added or reordered there moves the artifact.
· Trace: §4.3.3, §4.3.6

**IDL-057** MUST: A malformed request moves from the submitted state directly to the terminal one without acquiring device authority or beginning payload mutation, which is the one admitted step past a successor.
· Accept: R-12-094 states that step; the generated artifact carries it as a second relation beside the successor function rather than as an exception inside it, so the successor function stays total in its own terms.
· Trace: §4.3.3

#### 4.3.4 Capacity, notification, and batching

**IDL-058** MUST: Exhaustion is fail-closed on both sides. Submission against a full request ring has the sole typed result R-12-095 names, with no partial enqueue, and a server accepts a request only against completion capacity at least its maximum number of simultaneously accepted requests, established at composition.
· Accept: no terminal completion is dropped or overwritten to recover space; the typed result is relevance-graded under §3.2 like every other fallible result.
· Trace: §4.3.4, §3.2

**IDL-059** MUST: The notification word is a **binary armed state with a defined reset** and no counter exists. The consumer drains within its admitted budget, arms the word, re-reads the producer index, and sleeps only if the recheck still shows no work.
· Accept: spurious and coalesced notifications are admitted and cost one bounded empty drain; the indices are the source of truth and the notification is a hint (R-12-096).
· Trace: §4.3.4

**IDL-060** MUST: A batch is an amortization unit and never a transaction: every member validates, accepts, cancels, completes, and accounts independently, and **no descriptor names a predecessor or encodes cross-request control flow**.
· Accept: no field of §4.2 admits a reference to another request, so the refusal is a property of the encoding rather than a rule a server enforces; publication and drain are bounded by the declared maximum batch size (R-12-098).
· Trace: §4.3.4, §4.2

#### 4.3.5 Cancellation, generation, and DMA

**IDL-061** MUST: Cancellation is a typed control-plane request naming its target by generation and request identifier, and its race semantics are the four deterministic answers R-12-097 fixes, decided by where the target stands against its declared cancellation and commit points.
· Accept: the four answers are that entry's and are generated into the artifact from it; an operation carrying no cancellation declaration under IDL-019 is non-cancellable and the request answers accordingly rather than being refused as malformed.
· Trace: §4.3.5, §3.6

**IDL-062** MUST: Every ring and descriptor is bound to a session generation that changes before any reuse across peer restart, device reset, or revocation, and no operation is replayed implicitly.
· Accept: no old-generation descriptor is accepted, indices and the notification word are reinitialized before the new generation is live, and an interface claiming idempotence names the operation subset, the stable request identity, the deduplication retention bound, and the duplicate-effect proof (R-12-099).
· Trace: §4.3.5

**IDL-063** MUST: Zero-copy DMA executes only through a session-table capability whose permissions match the descriptor's declared direction, with the complete extent validated before the transfer starts and never reinterpreted after; scatter and gather exist only as a bounded list under `TC-5` with a declared maximum segment count.
· Accept: no capability is retained past terminal completion, and the maximum segment count is a declared field of IDL-018's record rather than a figure of this document (R-12-100, R-12-101).
· Trace: §4.3.5, §3.6

#### 4.3.6 The generated interface artifact

**IDL-064** IS: The **generated interface artifact** is what a ring-bearing declaration is compiled to. It carries three parts: §6.2's skeleton, the composition-time constants R-12-091 and R-12-101 name, and the conformance campaign R-18-037 requires.
· Accept: IDL-045's refusal of a proof is a property of the skeleton part and not of the artifact, whose campaign part is exactly the generated obligations that entry's criterion names.
· Trace: §4.3.6, §6.2

**IDL-065** MUST: The two closed enumerations the artifact carries from the register, R-12-093's status set and R-12-094's lifecycle states, are **emitted from those entries** rather than transcribed into the generator or into the declaration.
· Accept: the register is the enumeration's one owner and the artifact is its second statement, generated; a member added at either entry moves the artifact's bytes, and a generator carrying its own copy of either list is a defect rather than a convenience.
· Trace: §4.3.6, §9

**IDL-066** MUST: The conformance campaign is generated **from the artifact's own constants**, and every obligation it carries is decided by computation over those constants rather than by an authored proof.
· Accept: the campaign covers the cases R-18-037's criterion enumerates; a declaration whose constants do not satisfy an obligation fails to compile the artifact, which is the fail-closed reading of *no interface world declaring rings is admitted before its campaign runs*.
· Trace: §4.3.6

**IDL-067** MUST: The declaration is the **one authored owner** of everything a composition fixes, and the artifact is a function of the declaration and of the register alone.
· Accept: no hand edit of the artifact survives, the artifact being regenerated and compared byte for byte; a fact stated in both the declaration and the artifact is stated once and generated once.
· Trace: §4.3.6, §9

**IDL-068** IS: Two things this schema names cannot be emitted in this repository today, and each is a limit of a milestone rather than of the schema.
· Accept: the reference bindings are Gallina rather than systems-language, the specification's §0 putting base components assigned to safe Rust in Gallina for the reference and no purecap backend existing yet; and the admission checker R-12-010 and R-18-037 both name is a separate milestone, of which only the composition-time half is landed, so a generated artifact has nothing to be admitted by. Neither limit is repaired by narrowing the schema.
· Trace: §4.3.6, §7

---

## 5. Worlds, manifests, and resources

**IDL-029** MUST: A `world` maps to a **capability manifest**, and its home in the admitted artifact is R-13-003's capability manifest with its §12 interface descriptor.
· Accept: the manifest is generated from the world declaration; no manifest is authored beside the world it is the image of.
· Trace: §5, §6

**IDL-030** MUST: A world declares **import and export tables**, and those tables carry the cross-compartment edges the typed set leaves out.
· Accept: scope is per compartment, cross-compartment sentry edges stay outside the typed set, and the system call graph is the composition of per-compartment graphs with manifest edges (R-05-117); initialization state crosses on those tables (R-05-124).
· Trace: §5, §3.4

**IDL-031** MUST: A `resource` maps to a **capability**. The declaration states which of `TC-13`'s two readings a given occurrence carries, control-plane or data-plane, and the reading is a property of the field rather than of the constructor.
· Accept: a control-plane occurrence carries no wire bytes and a data-plane occurrence carries a session-table index (§4.2); new authority arrives via control-plane IPC only (R-12-006).
· Trace: §5, §4.2, §8

**IDL-032** MUST: An **object reference** is an out-of-band capability plus a typed metadata identity; an **intent** is a closed variant under `TC-8`; a **transformation** declares bounded input and output types, its resource limits, and its interface world.
· Accept: no desktop-specific wire protocol, open-ended intent string, or authority-bearing path is introduced, and all three ride this profile rather than a second one (R-12-013a).
· Trace: §5, §2

**IDL-033** MUST: A `package` is a name and a declaration set. Version ranges, feature gates, and conditional inclusion are absent: a world's import and export tables are literal.
· Accept: `TC-21`'s gates are deleted and no world declaration admits a union operator, so a world's edge set is decidable by reading the declaration rather than by resolving a set of conditions.
· Trace: §5, §2

**IDL-034** MUST: A type shared between interfaces is referenced rather than copied, and the reference names a declaration inside the same package.
· Accept: one type has one definition and every other statement of it is generated; a cross-package reference is an amendment rather than a resolution step.
· Trace: §5, §6

---

## 6. The generated artifacts, and the subset a Coq interface is stated over

**IDL-035** MUST: Marshalling, the verified parsers, and the Coq interface skeletons are **all generated from the same type source**.
· Accept: no artifact of the three is hand-written; a hand-written restatement held equal to a generated one by a rule is a finding rather than a repair, the fact having one owner.
· Trace: §6, §4

**IDL-036** MUST: Every generated artifact records the profile version it was generated against and the declaration it was generated from.
· Accept: an artifact carrying neither is refused by the admission checker; a version bump is an amendment under IDL-003 rather than a transparent regeneration.
· Trace: §6, §1.3

### 6.1 What has a Gallina image and what does not

| Constructor | Gallina image |
| --- | --- |
| `TC-1` fixed-width integers | one bounded numeric type per declared width |
| `TC-2` `bool` | the prover's own two-case inductive |
| `TC-3` `char` | a bounded numeric type carrying the scalar-value restriction as a proposition |
| `TC-4` `string`, `TC-5` `list<T>` | a list paired with a proof its length is at or below the declared bound |
| `TC-6` `tuple`, `TC-7` `record` | one record type, fields in declaration order |
| `TC-8` `variant`, `TC-9` `enum` | one closed inductive, one constructor per declared case |
| `TC-10` `flags` | one record of booleans, one field per declared flag |
| `TC-11` `option<T>`, `TC-12` `result<T, E>` | the two-case inductives, the second carrying its grade as a typing obligation on the generated elimination |
| `TC-13` `resource`, `TC-14` `borrow<T>` | an abstract index type with no elimination, so no proof reads a handle's representation |
| `TC-15` through `TC-21` | none: the constructors are deleted, so the image is empty by construction |

**IDL-037** MUST: The image is **total over §2's admitted and narrowed set**, so no declaration this profile admits has a part the generator cannot state.
· Accept: every row of §2 not marked `deleted` has a row above; a constructor added by amendment adds a row to both tables in the same act.
· Trace: §6.1, §2

### 6.2 What a skeleton contains

**IDL-038** IS: A **Coq interface skeleton** is the generated Gallina artifact a Tier-1 proof is stated against. It contains exactly six things.
· Accept: the six are enumerated in IDL-039 through IDL-044 and a skeleton carrying a seventh, or missing one, is not this profile's skeleton.
· Trace: §6.2

**IDL-039** MUST: The skeleton contains the **type images** of §6.1 for every type the declaration defines and every type it references.
· Accept: no image is authored beside the skeleton; the closure is over the declaration's own type graph, which `TC-18`'s deletion makes finite and acyclic.
· Trace: §6.1

**IDL-040** MUST: The skeleton contains one **signature per operation**, over those images, with the operation's result type in its graded form.
· Accept: a signature names the operation's declared parameter and result types and nothing else; it carries no implementation and no proof.
· Trace: §6.2, §3.2

**IDL-041** MUST: The skeleton contains the **flow predicates** matching §3.1's labels, emitted by the generator rather than authored.
· Accept: a cross-domain server's Tier-1 proof includes flow theorems against those predicates (R-12-011); the predicates are stated over an arbitrary lattice until one is fixed (§8).
· Trace: §3.1, §8

**IDL-042** MUST: The skeleton contains the **receiver-validation obligations** §3.3 declares, as hypotheses the Tier-1 proof discharges at the receiver.
· Accept: a marked field yields an obligation and an operation carrying IDL-015's empty claim yields the claim as a proposition rather than as nothing (R-12-012a).
· Trace: §3.3

**IDL-043** MUST: The skeleton contains the **per-variant record** IDL-018 declares, as a record of the composition-time constants R-12-101 names, so a conformance campaign generates its tests from the artifact's own constants.
· Accept: the record carries the values the composition fixed and the skeleton restates none of R-12-101's list as prose (R-18-037).
· Trace: §3.6, §6.3

**IDL-044** MUST: The skeleton contains the **lifecycle statuses** as R-12-093's closed set cited rather than restated, and the interface's own refinement variant beside it.
· Accept: one closed inductive per set, generated from the register's enumeration through the declaration rather than transcribed into the skeleton.
· Trace: §4.3

**IDL-045** MUST NOT: A skeleton contains no proof, no proof obligation of the implementation, no wire bytes, no ring buffer, no scheduling term, and no axiom.
· Accept: the skeleton is what a Tier-1 proof is stated *against* and never part of that proof; a skeleton carrying a `Parameter` or an `Axiom` is refused.
· Trace: §6.2

### 6.3 The two consumers the subset must be adequate for

**IDL-046** MUST: The subset is adequate for the **admission checker's** criterion, which verifies each Tier-1 proof is stated against the matching skeleton (R-12-010).
· Accept: matching is decided on the recorded declaration and profile version of IDL-036 rather than on a structural comparison of two Gallina terms.
· Trace: §6, §1.3

**IDL-047** MUST: The subset is adequate for **conformance among the generated client, server, parsers, and Coq interface skeleton**, which is R-18-037's campaign.
· Accept: the suite generates each interface world's tests from the artifact's own constants, and no interface world declaring rings is admitted before its campaign runs.
· Trace: §6.3, §3.6

**What the subset's boundary is, is undecided by the register**, and §6.2 decides it. That is the largest single act this document takes: R-12-010's criterion requires a Tier-1 proof to be stated against *the matching skeleton* and R-18-037 requires conformance among four generated artifacts, and no entry says what a skeleton contains. The decision is recorded in §8 rather than presented as a reading.

---

## 7. What this profile does not carry

**IDL-048** MUST NOT: This profile carries **no kernel ABI**. The kernel is not an IDL endpoint.
· Accept: R-07-031b closes the invocation list and states the figure, R-07-031a fixes the surface, and R-07-031 puts rich interfaces one layer up in §12; this document cites those entries and restates neither the list nor the figure, an interface profile authored for servers being the wrong home for a syscall surface (R-12-013).
· Trace: §7

**IDL-049** IS: The types of this profile are **documentation of the contract and never the contract**. Enforcement remains kernel capabilities plus CHERI plus the Coq specifications.
· Accept: no requirement of this document claims that a declared type enforces anything at run time; the wire-format mapping's obligations are discharged by the generated parser's proofs and by the Tier-1 proofs stated against §6's skeleton, not by the declaration.
· Trace: §7, §4

**Four further absences, each named so it reads as a boundary.**

- **No value of any composition magnitude.** IDL-017 makes every one a field, so no figure here is a number a later composition could contradict.
- **No ring schema.** §4.3 is where it lands and M6.4 is what authors it.
- **No admission-checker behaviour.** IDL-046 states what the checker's criterion needs of this profile and nothing about how the checker decides it; that is M6.2's, of which the composition-time half is landed.
- **No generator.** IDL-035 states what is generated and from what; no generator exists in this repository, so every generated artifact named above is an obligation rather than a file.

---

## 8. Declared parameters

*These are the judgments this document takes that the register does not fix. Each has a value, a ground, and a stated way to be wrong. A parameter is here rather than inside a sentence of §2 or §4 precisely because taking one by fiat would put a decision in an artifact the review gate does not audit, and collecting them is what makes each findable in one place.*

| Parameter | Value | Ground | What would change it |
| --- | --- | --- | --- |
| this document's version and amendment rule | version 1; a change to §2, §3 or §4 is an amendment carrying a review-gate event | R-12-010 says fork-and-frozen and names no artifact, where R-05-135a pins the language document by name and R-05-135b makes its bump a gate event | a register act pinning this document by name, which is what would make IDL-003 bind anything but this document |
| the start-from's name | WIT, at `design/mvp/WIT.md` of `WebAssembly/component-model` | the specification's §12 prose and [inspirations.md](inspirations.md) say WIT-derived; neither is the audited artifact, so naming it is a maturity claim under R-18-001a with no register owner | a register act naming the start-from, or a reading that finds the fork is of something else |
| the edition the fork is cut from | the reading of 2026-08-31; the upstream publishes no release and the document states no version of itself | measured at the upstream rather than characterized: the release list is empty and the specification carries no version line | pinning the upstream as a submodule, which would fix the edition as an object id a rule could hold, at the cost of a gitlink and its pin row |
| the constructor set of §2 | closed at `TC-1` through `TC-21` | R-12-012 restricts without enumerating, so nothing the gate audits closes the set | a register act enumerating it, in the shape R-07-027a used to close the object inventory before M4.2b could author against it |
| floating point | `TC-20` deleted | IEEE-754 gives NaN a payload field and zero a sign, so one value has many encodings, which is exactly the slack R-05-051b forbids of any descriptor on an identity-bearing path; IDL-020 takes that rule whole | a register act admitting a float type together with the canonical subset it is restricted to, or a decision that bit-pattern equality is the equality on the identity-bearing path, at which point each encoding is a distinct value. The arm not taken forfeits a direct declaration of a measured quantity: an interface that needs one declares a scaled integer pair and states the scale |
| the `string` encoding, and what its bound counts | UTF-8; the bound counts bytes of the encoded form; an over-long, ill-formed, surrogate-encoding or out-of-range sequence is a decode failure and is never replaced | R-12-012 requires an explicit bound and says nothing about the encoding, and UTF-8 admits over-long encodings of the same scalar, which R-05-051b's one-admissible-form rule reaches | a register act fixing the encoding, or a declaration that the bound counts scalar values, which would make the encoded length a computed rather than a declared quantity |
| which result type carries the grade | every result type at its own definition, the common status set and each operation-specific refinement variant alike; a refinement inherits nothing | R-18-016 places the declaration at the definition and R-12-093 makes a refinement its own closed variant, hence its own definition | a register act stating that a refinement inherits the common set's grade, which would remove the declaration from every refinement and put it on one |
| the grade's wire consequence | none: no field of §4 encodes the grade | R-18-016 places the grade at the definition and R-05-097 makes it a typing property; a grade on the wire would be a field IDL-020 then has to admit no slack in, bought for no decided reader | a register act making the grade observable to a peer, which is the only reading that would need it encoded |
| the flow-label lattice | not invented here: the labels are declared per type and the obligations are stated over an arbitrary lattice | R-12-011 names no label set, no order and no join, and the security policy model that would own one is `CJ-NI`, row 2 of the crown-jewel inventory, reading `not authored` | authoring `CJ-NI`, or a register act naming the lattice; either would let IDL-041's predicates be stated over a fixed set rather than a parameter |
| the mapping's membership in the R-05-042 wire-format inventory | stated here as attacker-facing and owing a Narcissus descriptor; the inventory row is not written | R-12-024f puts translator content formats in that inventory and R-05-046 makes each descriptor its own crown jewel; the mapping is crown-jewel row 3 under `CJ-IDL` rather than row 10 under `CJ-FORMAT` | a crown-jewels and register act adding the descriptor to row 10, which would confer separately on it |
| whether the mapping is identity-bearing | the stronger reading: IDL-020 admits no slack anywhere, whether or not a given encoding feeds an identity | R-13-003 puts the interface descriptor inside the content-addressed manifest, which makes that descriptor look identity-bearing; R-05-051c's enumerated site list does not name a live IDL call | a register act deciding the reading. Taking the weaker one would have bought encoding slack on the call path and a second audit at every site that later became identity-bearing |
| the receiver-validation vocabulary | a per-field marker, plus a per-operation claim where an operation marks none | R-12-012a says the IDL declares *which received values* carry the obligation, which is per value, and requires the empty case to be a claim the checker reads | a register act fixing the form as a per-operation clause or as a type of its own, either of which would move IDL-014's granularity |
| `resource`'s two readings | one constructor, two declared readings, the reading a property of the field | R-12-010 maps resources to capabilities and R-12-006 with R-12-007 admit only session-table indices on the data plane, and no entry says whether that is one constructor or two | a register act splitting it, which would make `TC-13` two rows and `WF-11` and `WF-12` two constructors rather than two readings |
| declaration magnitudes | every one a field, no figure stated | R-05-143 and R-12-012 bound values and nothing bounds a declaration, so a declaration's size is a composition magnitude with no owner | a register act bounding a declaration, in the shape R-15-014a uses for a frozen-but-unvalued parameter |
| the Coq subset's boundary | §6.2's six contents, and no seventh | R-12-010's criterion requires a Tier-1 proof to be stated against the matching skeleton and R-18-037 requires conformance among four generated artifacts, and no entry says what a skeleton contains | a register act stating the skeleton's content, which is the act that would make §6.2 a reading rather than a decision |

---

## 9. What holds this document, and what nothing holds

`tools/check.py` reaches this document as it reaches every tracked Markdown file, and the rules that bear on it are named here so the reach is legible rather than assumed. Each is written plain: none of them is cited as the holder of a fact this document creates.

| Predicate | Rule |
| --- | --- |
| every register, crown-jewel, absence and coverage id used names one its declarer holds | K-11 |
| every link resolves to a file, and every fragment to a bookmark or heading | K-12 |
| every section number a sentence names is carried by some heading | K-13 |
| every table row is the width its header declares, in a table with a header rule | K-38, K-39 |
| no em-dash, no mojibake, no replacement character | K-40, K-41 |
| every entry this document names in another document is carried by a heading there | K-59 |
| every finding the completion note counts has exactly one entry in the findings register | K-82 |

**No rule holds §2's constructor table against anything, and none holds §4's encoding table.** That is not an omission in the tool: nothing else in this repository states a constructor set or a wire encoding for the IDL, so there is no second statement for a rule to hold the first against, and a rule invented to hold one artifact against itself would be the older discipline the plan's own conventions call a finding. What §2 and §4 are held by is R-05-150's independent review, which is what a crown jewel is for.

**Three enumerations this document depends on are cited rather than restated**, and that is deliberate: R-12-093's status set, R-07-031b's closed invocation list, and R-12-101's per-variant field list are each one entry's to state and every other site's to cite. A figure written here would be an unheld restatement free to drift from the entry that owns it.
