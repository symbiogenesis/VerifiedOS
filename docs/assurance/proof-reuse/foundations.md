# Foundational proof reuse

This is a source-qualified part of the [proof reuse inventory](../proof-reuse.md).
The [opam lock](../../../tools/opam/rocq.lock) fixes the local prover and library
versions. A library's statements and its licence are separate checks; a theorem
about mathematical integers does not establish a bounded machine operation.

## F01: Rocq Stdlib arithmetic, integrated by reference

**Source and authors.** The Rocq Development Team, INRIA, CNRS and contributors;
`PeanoNat.v` credits Evgeny Makarov, INRIA, 2007. The reviewed edition is
[Stdlib V9.2.0](https://github.com/rocq-prover/stdlib/tree/V9.2.0), revision
`8dd155bc10529814202f8f4c643e5ae6c2c88fa6`. Its
[PeanoNat source](https://github.com/rocq-prover/stdlib/blob/8dd155bc10529814202f8f4c643e5ae6c2c88fa6/theories/Arith/PeanoNat.v)
instantiates natural-number property modules, including the generic addition
and multiplication facts. The [library documentation](https://rocq-prover.org/doc/V9.1.0/stdlib/index.html)
is a discovery aid; the installed V9.2.0 source and kernel are the integration
evidence.

**Exact use.** [MemoryPlan.v](../../../proofs/MemoryPlan.v) requires
`Stdlib.Arith.PeanoNat` without importing its namespace. Its existing helper
names and propositions remain the interface to the slot-placement, alignment
and admission proofs. Arithmetic identities, monotonicity, strict-order and
subtraction adapters use qualified `PeanoNat.Nat` facts. The Boolean adapters
cross to propositional order through `leb_le`, `ltb_lt` and `leb_gt`, and
`eqb_true` uses the forward implication of `eqb_eq`. These are proofs over the
same `nat`, arithmetic and Boolean comparisons, so no representation bridge,
new import or new premise is required. The adapter bodies own the exact lemma
references.

**Scope.** This supports the existing memory-plan arithmetic behind R-08-011,
R-08-018 and R-15-060. It changes no discharge claim. In particular it does
not turn the statement artifact into a proof of a shipped composition,
machine-word overflow, allocator optimality or the compiler's emitted plan.
The native `run.py proofs` gate compiles the clients, inventories their
constants, follows `Print Assumptions` through the imported proof terms and
kernel-rechecks the modules. An import is never an exemption from that audit.

**Licence and conveyance.** The actual
[V9.2.0 LICENSE](https://github.com/rocq-prover/stdlib/blob/8dd155bc10529814202f8f4c643e5ae6c2c88fa6/LICENSE)
and the source header state LGPL version 2.1. No upstream source or compiled
library is vendored. The original Apache-2.0 adapters use the separately
installed library, whose compiled outputs stay untracked. Redistribution of
the library or combined compiled artifacts carries its own LGPL obligations;
the [third-party record](../../../THIRD-PARTY.md#used-by-the-build-not-conveyed)
records that boundary. This is reuse by a library reference, not relicensing
the upstream proofs as Apache-2.0.

## F02: stdpp finite maps, sets and sequences

**Source and authors.** The std++ developers and contributors, in the
[Iris stdpp repository](https://gitlab.mpi-sws.org/iris/stdpp). Its
[gmap development](https://gitlab.mpi-sws.org/iris/stdpp/-/blob/master/stdpp/gmap.v)
implements finite maps over countable keys with extensional equality; the
source credits the canonical binary-trie work of Andrew Appel and Xavier
Leroy. The map laws and concrete implementation are more useful starting
points than a fresh abstract map interface alone. The actual
[LICENSE](https://gitlab.mpi-sws.org/iris/stdpp/-/blob/master/LICENSE)
grants BSD-3-Clause and names the std++ developers and contributors.

**Fit and disposition.** Rocq-native adaptation candidate for
[JournalIndex.v](../../../proofs/JournalIndex.v),
[KeyspaceDomains.v](../../../proofs/KeyspaceDomains.v),
[CredentialHandles.v](../../../proofs/CredentialHandles.v) and the future Iris
program logic. The project's proof switch already fixes `rocq-stdpp` in its
lock, but the local modules do not thereby acquire map correctness. A selected
replacement needs a relation to the existing list/record representations,
finite-capacity and iteration-order proofs, and an assumption audit. A
logarithmic map in Rocq is not a proved WCET bound on CHERI. No change is made
to these data structures here. The branch link is a discovery location,
not a pinned integration input.

## F03: coqutil maps and machine words

**Source and authors.** Massachusetts Institute of Technology and the coqutil
authors, as identified by [AUTHORS](https://github.com/mit-plv/coqutil/blob/master/AUTHORS)
and the [MIT LICENSE](https://github.com/mit-plv/coqutil/blob/master/LICENSE).
The [map interface](https://github.com/mit-plv/coqutil/blob/master/src/coqutil/Map/Interface.v)
and [word developments](https://github.com/mit-plv/coqutil/tree/master/src/coqutil/Word)
are shared foundations for Bedrock2. The local lowering switch's version is
recorded in [THIRD-PARTY.md](../../../THIRD-PARTY.md).

**Fit and disposition.** Adaptation candidate for the bounded words and maps
of ring descriptors, firmware, crypto and the journal, especially at the
Gallina-to-Bedrock boundary. `map.ok` and word-law interfaces are premises
until a concrete implementation supplies their proofs. The existing
natural-number specifications do not become machine-word-correct merely by
importing these interfaces. Match signedness, width, overflow, byte order and
finite storage, then replay the chosen implementation at the pinned version.
MIT permits incorporation with retained notices; no source is copied here.

## F04: Mathematical Components

**Source and authors.** Georges Gonthier and the Mathematical Components
contributors, with attribution in
[INITIAL_AUTHORS.md](https://github.com/math-comp/math-comp/blob/master/INITIAL_AUTHORS.md)
and [AUTHORS](https://github.com/math-comp/math-comp/blob/master/AUTHORS).
The [project](https://github.com/math-comp/math-comp) publishes Rocq/SSReflect
developments for finite types, graphs, algebra, matrices and fields, used in
the formal Four Colour and Odd Order theorem developments. Its actual
[LICENCE](https://github.com/math-comp/math-comp/blob/master/LICENCE) states
CeCILL-B, which includes attribution conditions requiring a separate
incorporation reading; it is not an MIT election.

**Fit and disposition.** Strong Rocq-native foundations for finite permission
lattices, live-range colouring, linear ECC and finite-field crypto. See the
Infotheo ECC entry in [hardware](hardware.md) and the arithmetic entries in
[crypto](crypto.md). Algebraic or graph theorems need an encoding relation to
the local permissions, intervals and bit layout. The Four Colour theorem is
about planar graphs and gives no general allocator-colouring theorem.
No MathComp dependency or global automation is added to the current proofs.

## F05: Lean mathlib as a cross-language reference

**Source and authors.** The mathlib contributors, with per-file authorship in
the [Lean 4 library](https://github.com/leanprover-community/mathlib4).
The actual [LICENSE](https://github.com/leanprover-community/mathlib4/blob/master/LICENSE)
is Apache-2.0. Its
[simple-graph colouring developments](https://github.com/leanprover-community/mathlib4/tree/master/Mathlib/Combinatorics/SimpleGraph/Coloring)
are a concrete lead for mathematical colouring arguments; its algebra and
finite-set library supplies alternative statements against which to review
Rocq models.

**Fit and disposition.** Reference only for R-08-011's live-range colouring
and proof-aware design-space mathematics. Lean proof terms are not Rocq
terms. An actual reuse requires a proved translation or a Rocq reconstruction,
including the relevant classical, choice and extensionality assumptions.
Neither an Apache licence nor a theorem-name match establishes that bridge.
This inventory does not introduce Lean as a project trust language.

## Research-scale formalization as planning evidence

These completed projects demonstrate that coordinated formalization can reach substantial research mathematics. They are evidence for feasibility and work organization, not a conversion from published calendar time to VerifiedOS engineering hours or a proof that its outstanding statements are true.

| Project and primary account | Evidence and local limit |
| --- | --- |
| Gowers, Green, Manners and Tao's Marton/PFR result over characteristic two; [the authors' formalization project](https://teorth.github.io/pfr/) and [Tao's November 2023 workflow account](https://terrytao.wordpress.com/2023/11/18/formalizing-the-proof-of-pfr-in-lean4-using-blueprint-a-short-tour/) | The completed Lean formalization uses a proof blueprint and develops Shannon entropy infrastructure. A modular proof graph and explicit prerequisite library are useful planning patterns. It does not certify CIC normalization, compiler preservation or hardware observations; the mathematics and the available library determine the amount of new work. |
| Busy Beaver Challenge, [July 2024 completion announcement](https://discuss.bbchallenge.org/t/july-2nd-2024-we-have-proved-bb-5-47-176-870/237) | The Coq proof of BB(5) = 47,176,870 combines finite enumeration, proved deciders and specialized arguments, with independent review of the theorem statement. The project reports two years of collaboration and roughly ten hours to compile on a standard laptop. These are different costs, neither a measured port of this project's proofs. |
| [Liquid Tensor Experiment completion](https://leanprover-community.github.io/blog/posts/lte-final/), July 2022 | The Lean project completed its main theorem about liquid vector spaces about a year and a half after the challenge. Its linked blueprint and library development demonstrate the value of explicit dependencies and staged milestones. They do not establish the metatheoretic premises or resource behavior of an on-device Rocq checker. |

Use these cases in the [estimate basis](../../implementation/implementation-checklist.md#estimate-and-schedule-basis) as external existence evidence alongside this repository's own calibration. Before repricing a research-heavy item, obtain a representative local checked result, its assumption audit, dependency closure and measured authoring/checking costs; record unsupported features and replan at that boundary. M6.2b-0's first recursive corpus example and U-25's instantiated compiler criterion are local checkpoints of that kind. No theorem source is imported here, no local replay is claimed and no estimated hours are removed by this evidence.

### FormalFlow's low individual-degree test: a statement-review reference

**Read 2026-10-10; older proof, recent report.** Sirui Lu, Ruixuan Deng,
David Zhu and Zhengfeng Ji's
[September 17 paper, revised September 24](https://arxiv.org/abs/2609.19814v2)
reports a proof completed on June 24. The inspected
[`b39705bfd36b8f7208f58d8c75e6c42a1624e06c` theorem](https://github.com/LionSR/MIPStarRE/blob/b39705bfd36b8f7208f58d8c75e6c42a1624e06c/MIPStarRE/LDT/Test/MainTheorem/MainFormal.lean)
is quantum soundness of the classical low individual-degree test, not all
of MIP*=RE. For a passing normalized finite-dimensional strategy it supplies
polynomial measurements with stated consistency-error bounds, under
`400 * m * d <= k` and `0 < k`. The report identifies those sampling
conditions as corrections and reports the Lean closure `propext`,
`Classical.choice`, `Quot.sound`.

The useful transfer is to [proof review](../proof-assistance.md#research-handoff-for-future-proof-producers):
the [documented failures](https://arxiv.org/html/2609.19814v2#A3)
include intermediate records assuming their desired conclusions. Review the
actual definitions and joint satisfiability of premises alongside axiom
closure. This supplies no quantum-security premise for VerifiedOS or local
proof. No license file was found in the inspected snapshot; source adaptation
remains unqualified. No code is copied, no replay is claimed and no estimate
changes.

## Certified search and the register's standing refusals

The constraint-programming and pseudo-Boolean literature carries proof
checkers whose soundness is machine-checked, so a solver's answer can be
re-established without trusting the solver. The register already decides most
of what this repository may do with them, and the decision is not uniform.
The entries F06 through F11 are qualified on 2026-09-13 and F12 on 2026-10-02,
and all are recorded under that decision, not against it.

**What the pattern admits, and what of it is built.** R-05-066 names the
asymmetric-trust pattern and keeps it: an untrusted producer whose output the
already-existing checkers re-validate is admissible and free to be arbitrarily
aggressive, because the rule it reads targets *minting a checker* rather than
the pattern. Its criterion is narrow in the direction that matters here, an
optimizer being admissible exactly where an existing checker decides its
output and no new checker is introduced. The portable
[LRAT experiment](../../implementation/static-memory/certificates.md) invokes a
separately licensed Isabelle-LLVM checker as evidence-producing machinery under
R-05-011b. Its verdict grounds no admitted claim and supplies no instance-specific
Rocq term; Q27a's disposition is unchanged. Only the producer half of the
production arrangement exists locally:
[the placement search](../../implementation/placement-search.md) is a
host-side search over the witness values in
[the memory plan](../../../proofs/MemoryPlan.v), exporting the problem as data
and admitting every candidate by a port of that file's own checks, and it
decides nothing, a gain found there being a gain over witness values that
credits nothing to the product. The checker R-08-014 states its side condition
for is the on-device TAL type-check, and that checker is owed rather than
built: R-18-020 books it and the derivation producer as hard prerequisites
with no trusted-toolchain fallback. Nothing in this family is needed for either
half, and no entry below is proposed as part of it.

**What the register refuses.** What these entries would be is a *shipped*
certificate checker, and the register refuses that from several directions at
once. R-05-066's own criterion is the first: a new checker is precisely what
it does not admit. R-06-011 fixes the admission axioms, and R-05-164 reads the
declared assumption set off that inventory. A new ground of admission requires
an amendment; program count alone does not, as R-05-011c expressly states.
R-05-016 and R-05-016a exclude reliance on a second logic's acceptance, while
R-05-015 admits proof terms re-checked by the existing kernel. R-05-064 is the
canonical statement of what the CryptOpt-style route's deletion took with it,
the checker-admitted-artifacts TCB category among it, and every section
observing that absence cites it rather than restating it. R-05-104 deletes the
Implicit Path Enumeration Technique and its LP solver rather than retargeting
them, its criterion being that no ILP machinery exists in the toolchain, which
reaches F10's mixed-integer route directly and holds any constraint or
pseudo-Boolean encoding to introducing none. R-05-105 is the standing
no-tightening rule: a verified tool whose only yield is a tighter
already-sound bound is inadmissible and the trivial sound bound is taken, and
R-05-106 reads that same rule on artifacts rather than estimates, naming
R-05-064's deletion as its instance. A checker imported so that a planner can
return a certified-optimal layout yields a smaller span over a plan the
existing checks already admit, which is the yield those rules were written to
refuse.

**What R-05-020 asks of any of them besides.** It admits a new semantics,
program logic or translator only on a shown demonstration of three conditions:
Rocq-native or mechanically bridged, non-duplicating of an existing anchor,
and retiring an interim it replaces. Two members are Rocq-side, FznDrcpCheck
at F06 and the Rocq LRAT checker at F08, and only the first addresses the
constraint and optimization problems at issue, the second being a SAT proof
checker. CakePB and the colouring and enumeration results built over it are
HOL4; LeanCSP, PBLean, lrat-catcher and Ordeal's checker are Lean, and F05
already records that this inventory does not introduce Lean as a project
trust language; SCIP, cvc5 and the proof-logging and trimming papers carry no
proof assistant at all. None of them retires an interim.

**The infeasibility proposal is declined on present evidence.** A checked
*infeasibility* certificate would move a verdict from "the search found no
placement" to "no legal placement exists", which is a yield other than
tightness, so neither R-05-105 nor its artifact-level generalization R-05-106
disposes of it. The [placement disposition](../../background/architectural-alternatives.md#certified-placement-and-infeasibility-no-new-certificate-machinery)
accepts the inconclusive diagnostic result and commissions no new machinery.
An imported verdict cannot ground admission under R-05-016; an instance-specific
kernel-checked proof can take R-05-015's route, but the local experiment supplies
none. R-05-066 supplies no permission for a new optimizer checker, R-05-104
refuses any ILP machinery, and a new semantics, logic or translator owes all
three R-05-020 demonstrations. Reopening requires the concrete composition
decision and reviewed contract the disposition states. F06 is the
only member whose prover matches the project's while addressing a constraint
problem, and its own trusted base carries the FlatZinc grammar, the extraction
and the OCaml compiler; nothing here proposes it, or any other entry, as a
thing to start from.

## F06: FznDrcpCheck and the DRCP proof system, reference

**Source and authors.** Maarten Flippo, Konstantin Sidorov, Tip ten Brink,
Clément Pit-Claudel and Emir Demirović, *Formally Verified Certification of
Constraint Programming Proofs*, CP 2026, LIPIcs volume 379, pages 24:1-24:23,
at [the publisher record](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2026.24).
DRCP is a proof system for constraint programming over integer domains,
covering conflict analysis and heterogeneous propagation, and
[fzn-drcp-check](https://github.com/ConSol-Lab/fzn-drcp-check) is a checker
whose soundness is proved in Rocq: if it accepts a DRCP proof against a
FlatZinc model, the model is unsatisfiable or the claimed bound holds. Its
actual [LICENSE](https://github.com/ConSol-Lab/fzn-drcp-check/blob/main/LICENSE)
is MIT, copyright 2024 ConSoL Lab, and the `dune-project` declares the same.
The paper puts the DRCP parser deliberately outside the trusted base, since
the certificate is an opaque object in the soundness statement; what the
paper places inside it is a specification of roughly two hundred lines of
Rocq carrying the CSP formulation, the correctness property and the FlatZinc
grammar, together with the Rocq toolchain, the extraction and the OCaml
compiler. The opam dependencies are still spelled `coq-menhirlib` and
`coq-mmaps`.

**Fit and disposition.** Reference, and the only Rocq-native member of this
family addressing a constraint problem, F08's Rocq checker being the other
Rocq-side artifact here and a SAT checker. Its relevance to R-08-011 and
R-08-014 is the declined infeasibility proposal stated above: an
accepted certificate licenses one run and proves nothing about the search that
produced it, acceptance failure does not imply the model is satisfiable, only
a subset of FlatZinc constraints is expressible in DRCP, and the reported
overheads are measured rather than proved. Promotion past Reference would need
a FlatZinc rendering of the local placement problem, an argument that the
rendering is the problem the register states, the applicable R-05-020
demonstrations, and the placement disposition's reopening review. An external
verdict used as an admission ground also needs the explicit rule and inventory
amendments that review names; a kernel-checked producer is not excluded by
program count alone.
None of those is attempted here, and this survey claims no local build or
replay of the checker.

## F07: VeriPB and CakePB, reference

**Source and authors.** Wietze Koops, Daniel Le Berre, Magnus O. Myreen,
Jakob Nordström, Andy Oertel, Yong Kiam Tan and Marc Vinyals, *Practically
Feasible Proof Logging for Pseudo-Boolean Optimization*, CP 2025, LIPIcs
volume 340, pages 21:1-21:27, at
[the publisher record](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2025.21).
The two names are two artifacts and the verified claim attaches to one of
them. [CakePB](https://gitlab.com/MIAOresearch/software/cakepb) is a checker
specified and proved sound in HOL4 and compiled to machine code by the
verified CakeML compiler; its actual
[COPYING](https://gitlab.com/MIAOresearch/software/cakepb/-/blob/main/COPYING)
is the CakeML BSD-3-Clause notice.
[VeriPB](https://gitlab.com/MIAOresearch/software/VeriPB) is the proof format
and its fast elaborating checker, is not itself formally verified, and is
dual-licensed MIT or Apache-2.0 at the user's option.

**Fit and disposition.** Reference. What CakePB establishes is that an
accepted elaborated kernel-format proof entails the claimed unsatisfiability
or optimality bound for the pseudo-Boolean formula as given; the solvers that
produced it, RoundingSat and Sat4j, are unverified and certified only per
run, and the encoding of a real problem into pseudo-Boolean form is trusted,
which is where a placement obligation would actually have to be argued. The
prover is HOL4, so R-05-020's first condition fails outright and no bridge is
proposed. "Practically feasible" is a measured benchmark claim.

## F08: LRAT and its two certified checkers, reference

**Source and authors.** Luís Cruz-Filipe, Marijn J. H. Heule, Warren A. Hunt
Jr., Matt Kaufmann and Peter Schneider-Kamp, *Efficient Certified RAT
Verification*, CADE-26, LNCS volume 10395, pages 220-236,
[DOI 10.1007/978-3-319-63046-5_14](https://doi.org/10.1007/978-3-319-63046-5_14),
with the open-access copy at [arXiv:1612.02353](https://arxiv.org/abs/1612.02353).
LRAT is a proof format and not a tool: it extends DRAT with hints that make
checking a single linear pass, and the paper supplies two certified checkers
for it. The
[ACL2 checker](https://github.com/acl2/acl2/tree/master/books/projects/sat/lrat)
proves `main-theorem`, and its own source headers and the repository
[LICENSE](https://github.com/acl2/acl2/blob/master/LICENSE) state BSD-3-Clause.
The Rocq checker proves `refute_correct`, that acceptance implies the parsed
formula is unsatisfiable, and is distributed as a bare `rat-checker.tar.gz`
from [the authors' distribution page](https://imada.sdu.dk/u/petersk/lrat/),
which states no terms; its licence is therefore unread, and reading it means
opening a licence file inside that archive or asking the authors.

**Fit and disposition.** Reference. The Rocq checker is one of the two members
of this family whose prover matches the project's, F06 being the other, so
R-05-020's first condition is the only one a demonstration could begin from;
neither of its other two is argued here, and shipping the checker would meet
the same no-new-checker refusals the section above states, so the entry stays
a reference. Outside the theorem sit the CNF and LRAT parsers, extraction and
the OCaml and Lisp runtimes, the SAT solver, and `drat-trim`, the unverified
converter that generates the hints a checker consumes. Soundness is one
direction only: a rejected proof establishes nothing, and nothing connects
the parsed formula to the problem a caller meant to state.

## F09: the Lean certificate checkers, unqualified lead

**Source and authors.** Three separate preprints, all Lean 4, none with an
established venue. Pablo Manrique and Stefan Szeider, *LeanCSP: A Framework
for Certifying Constraint Reformulation and Solving in Lean*,
[arXiv:2607.28459](https://arxiv.org/abs/2607.28459) of 30 July 2026, proves
reformulation properties parametrically over problem families and re-checks
solver certificates per instance through MiniZinc, SMT-LIB and OPB backends;
its [LICENSE](https://github.com/leansolving/leancsp/blob/main/LICENSE) is
Apache-2.0, and the repository is a handful of commits with no tag or
release. Stefan Szeider, *PBLean: Pseudo-Boolean Proof Certificates for Lean
4*, [arXiv:2602.08692](https://arxiv.org/abs/2602.08692), was accepted at the
Pragmatics of SAT 2026 workshop whose proceedings have not appeared, so it is
cited as a preprint; its
[LICENSE](https://github.com/leansolving/pblean/blob/main/LICENSE) is
Apache-2.0. Stefan Szeider,
[arXiv:2607.00815](https://arxiv.org/abs/2607.00815), carries the v2 title
*Streaming LRAT Certificates into Lean Theorems* over a v1 titled
*LRAT-Catcher: Importing SAT Solver Certificates into Lean4 by Reflection*;
its [LICENSE](https://github.com/leansolving/lrat-catcher/blob/main/LICENSE)
is MIT, and the checker it makes resumable is Lean core's own.

**Fit and disposition.** Unqualified lead, on the prover before anything
else: these are Lean developments, R-05-020's first condition fails, and F05
already states that this inventory does not introduce Lean as a project trust
language. Their trusted bases also differ from a kernel-only reading in the
same way and should not be quoted as if they did not. PBLean's scalable path
runs its checker as compiled native code and so adds `Lean.trustCompiler` to
the trusted base, with an explicit proof-term path that avoids the axiom and
does not scale; lrat-catcher's default import mode is reflective and carries
the same native-evaluation axiom, with a slower kernel mode that drops it.
Two of the three are unreleased preprints, which is a second reason the lead
is unqualified and not a candidate.

## F10: SCIP's exact mode and VIPR certificates, unqualified lead

**Source and authors.** Christopher Hojny and thirty-three coauthors, *The
SCIP Optimization Suite 10.0*,
[arXiv:2511.18580](https://arxiv.org/abs/2511.18580) of 23 November 2025, a
technical report that is not peer reviewed. The exact solving mode solves
rational mixed-integer linear programs without floating-point tolerances and
can write a VIPR certificate recording the LP-based branch-and-bound
reasoning, which an independent checker verifies afterwards; the checker that
ships with the suite is C++. [SCIP](https://github.com/scipopt/scip) itself is
Apache-2.0, read from its own
[LICENSE](https://github.com/scipopt/scip/blob/master/LICENSE), which is the
verbatim Apache 2.0 text. The report states SoPlex, PaPILO and GCG also under
Apache 2.0 and ZIMPL and UG under the GNU LGPL; no component's own licence
file was opened here, so all five are reported terms rather than read ones,
and each is read from its own repository at the milestone that would
incorporate it.

**Fit and disposition.** Unqualified lead. Nothing here is machine-checked:
no proof assistant is involved, SCIP's own implementation is unverified, and
a certificate attests to one solve. The mode is restricted to mixed-integer
linear programs, the certificate does not cover presolving, and the report
prices exact mode at roughly three to four times a comparable floating-point
configuration. Claims circulating in secondary summaries that a HOL4/CakeML
VIPR checker ships alongside the C++ one are not substantiated by the report
or by the VIPR repository, and are not carried here.

## F11: pseudo-Boolean proof logging in solvers, reference

**Source and authors.** Four results, two of which have a machine-checked
checker behind them and two of which have none. Emir Demirović, Ciaran
McCreesh, Matthew J. McIlree, Jakob Nordström, Andy Oertel and Konstantin
Sidorov, *Pseudo-Boolean Reasoning About States and Transitions to Certify
Dynamic Programming and Decision Diagram Algorithms*, CP 2024, LIPIcs volume
307, pages 9:1-9:21, emits VeriPB-format certificates from algorithms that
reason over states and transitions; no proof assistant is involved, its
[supplement deposit](https://doi.org/10.5281/zenodo.12574620) is CC BY 4.0,
and the third-party code bundled inside that archive carries its own unread
terms. Simon Dold, George Katsirelos, Wietze Koops, Magnus O. Myreen, Jakob
Nordström, Andy Oertel and Yong Kiam Tan, *End-to-End Certified Graph
Colouring*, CP 2026, LIPIcs volume 379, pages 21:1-21:27, checks
ZykovColor's logs with CakePB, so the verified component is HOL4's and the
solver is unverified. Ciaran McCreesh, Jakob Nordström, Andy Oertel and Yong
Kiam Tan, *Proof Logging for Projected Enumeration (and Counting?) Problems
in VeriPB*, CP 2026, LIPIcs volume 379, pages 43:1-43:21, obtains formally
verified enumerations through the same CakePB backend. Twelve authors led by
Berhan Oumer Adame and Bart Bogaerts, *Trimming Pseudo-Boolean Proofs*,
FMCAD 2026, pages 743-756, shrinks proof logs. All four papers are CC BY 4.0
at their publishers.

**Fit and disposition.** Reference, for the shape of the certificates the two
checkers above consume rather than for any theorem. The question mark the
enumeration paper's title carries over counting is a scope fact and is carried
with it: enumerations are certified there, while counting is treated in the
design and is not shown certified. Trimming is proof compression with
no formally verified component, the trimmer being untrusted and soundness in
practice coming from re-checking the trimmed proof, so it is an engineering
result about proof size and not evidence of anything a checker holds.

## F12: Ordeal, a certificate-checked bit-vector solver, reference

**Source and authors.** PulseEngine's
[ordeal](https://github.com/pulseengine/ordeal/tree/97d314fc3cbf1868969fe3617bb7df4555cc4e29)
at its `v0.27.0` tag, read on 2026-10-02. It is a tool repository, not a paper.
It decides a closed QF_BV fragment at widths 1 to 128 by bit-blasting to CNF
for its own SAT solver. An `unsat` answer carries an LRAT certificate and a
`sat` answer an assignment. The trusted part is the `ordeal-lrat` crate. Charon
and Aeneas translate it from Rust to Lean 4 at pinned revisions, and the
soundness theorems are about that Lean model. `lrat_check_sound` makes an
accepted certificate refute the CNF, and `check_sat_sound` makes an accepted
assignment satisfy it. A certificate in the second format carries the term DAG,
which `check_query_sound` re-encodes inside the trusted crate, so an accepted
bundle refutes that DAG rather than a CNF taken on faith. The repository's
`AxiomCheck.lean` holds those theorems to Lean's three classical axioms.
Building the DAG from the input terms, rewriting, the derived operations and
the SMT-LIB front end stay outside the proof. Tests and a differential against
Z3 defend them, and the upstream cites an earlier translation bug, its issue
182, that produced a wrong answer under a valid certificate. Its own
trusted-base statement adds the Charon and Aeneas translation, which is not
verified end to end. The terms are `Apache-2.0`, as
[the third-party record](../../../THIRD-PARTY.md#webassembly-toolchain-and-rocq-extraction-readings)
reads them.

**Fit and disposition.** Reference. The checker's soundness is a Lean theorem
about an Aeneas model, so R-05-020's first condition fails as it does for
[F09](#f09-the-lean-certificate-checkers-unqualified-lead). Shipping it as an
admission checker meets the no-new-checker refusals above, and an imported
verdict would be a second checker R-05-016 excludes. As an untrusted producer
under R-05-066 it would need an existing checker to decide its output, and none
here decides a bit-vector equivalence.
[The LRAT experiment](../../implementation/static-memory/certificates.md)'s
Isabelle-LLVM checker would check a CNF alone, and it is evidence-producing
machinery under R-05-011b that grounds no admitted claim. Searching for a
rewrite candidate needs no certificate at all, and accepting one needs the
kernel-checked proof term R-05-015 names, which a Lean verdict does not supply.
Upstream, Ordeal validates a Wasm optimizer's and an Arm lowering's rewrites, a
role with no counterpart here: R-05-085 makes Wasm no native execution target.
No local build or replay is claimed.

## F13: Fair Repetitive Interval Scheduling, a restricted coloring reference

**Read 2026-10-10; formalization published 2026-10-02.** Yuval Itzhaki,
with Claude, formalizes results of Heeger, Hermelin, Itzhaki, Molter and
Shabtay (Algorithmica 2025). The
[archive record](https://laxarchive.org/lax-117284/index.html) identifies
[`b4de5da23cb7666dbeb3b1b332b35eefa090a330`](https://github.com/yuvalyitz/fairris-lax/tree/b4de5da23cb7666dbeb3b1b332b35eefa090a330).
The inspected
[proof wrappers](https://github.com/yuvalyitz/fairris-lax/blob/b4de5da23cb7666dbeb3b1b332b35eefa090a330/proofs/Lax117284Proofs/Tractable.lean)
include `chromaticNumber_dayGraph` and
`hasKFairSchedule_iff_mul_chromaticNumber_le`. The first proves that the
finite interval conflict graph's chromatic and clique numbers agree. When
processing times and due dates are both independent of day, the second
characterizes serving each client at least `k` times by
`k * chromaticNumber <= days`; its `i₀ : Fin I.days` requires a nonempty
day set. Concept-file axioms are statement interfaces, not these proofs.

**Fit and qualification.** Reference for Q5b's restricted equal-size
interval-coloring comparison. Source intervals are `(d-p,d]`; a reduction
must establish agreement with local `[start,end)` lifetimes. Variable sizes,
contiguity, alignment, capability representability and island/bank constraints
remain local. The statement proves neither cyclic-executive admission nor a
CHERI memory layout. The edition uses Lean 4.33.0 and mathlib
`db584cd6d46c92f209a44c0f1c829460d327499d`; its
[LICENSE](https://github.com/yuvalyitz/fairris-lax/blob/b4de5da23cb7666dbeb3b1b332b35eefa090a330/LICENSE)
is Apache-2.0. The proof/statement interface and dependency assumptions need
independent replay before adaptation. No Rocq bridge, local replay or
obligation reduction is claimed.

## F14: Eligible-machine interval scheduling with an explicit work bound

**Read 2026-10-10.** Yuval Itzhaki, with Claude, formalizes Hermelin,
Itzhaki, Molter and Shabtay's JCSS 2024 result. The
[archive history](https://laxarchive.org/lax-888481/index.html) dates the first
version to 2026-09-22 and the reviewed successor to 2026-10-01, at
[`3cdde85ce7b7eed2938def9b9be0b5434f615c0f`](https://github.com/yuvalyitz/isem-lax/tree/3cdde85ce7b7eed2938def9b9be0b5434f615c0f).
The proof
[`fptTime_byMachinesAndPmax`](https://github.com/yuvalyitz/isem-lax/blob/3cdde85ce7b7eed2938def9b9be0b5434f615c0f/proofs/Lax888481Proofs/Theorem3.lean)
gives a word-RAM decision procedure for an eligible-machine schedule meeting
a weight threshold, with instruction bound
`c * (m*pmax+1)^(2*m) * (m+1) * (|x|+1)`.
Its [statement](https://github.com/yuvalyitz/isem-lax/blob/3cdde85ce7b7eed2938def9b9be0b5434f615c0f/concepts/Lax888481/Theorem3.lean)
requires valid input, `Fits c w x`, and configuration-table addressability
`c*(m*pmax+1)^(2*m) <= 2^w`. The separate qualitative FPT theorem uses
exhaustive fallback when that table cannot fit; it does not erase this
bound's premise.

**Fit and qualification.** Q5b comparison reference for finite assignments
with resource eligibility. No reduction from the actual placement problem
is supplied, and abstract instruction counts are not target WCET. Keep Q5's
existing enumeration and Q27a's no-new-checker disposition. The inspected
edition uses Lean 4.33.0 and mathlib
`db584cd6d46c92f209a44c0f1c829460d327499d`, with an Apache-2.0
[LICENSE](https://github.com/yuvalyitz/isem-lax/blob/3cdde85ce7b7eed2938def9b9be0b5434f615c0f/LICENSE).
The README's reported standard-axiom closure is not a local audit; other
hardness results have separate dependencies. No code is incorporated, no
external proof is replayed and no admission or implementation obligation is
removed.

## F15: HOL Light to Rocq alignment, with regeneration required

**Read 2026-10-10; older proof development.** Frédéric Blanqui and Antoine
Gontard's [September 21 paper](https://arxiv.org/abs/2609.24598) describes
proved representation alignments and translations of the Logic and
Multivariate libraries. The [author's chronology](https://blanqui.gitlabpages.inria.fr/)
already records aligned-real translation in January 2025; the September
edition is not a new completion date for those proofs.

The inspected
[`rocq-hollight` edition](https://github.com/Deducteam/rocq-hollight/tree/d325e1c912d824556a7e06d1c10e9266190e75a6)
has a CeCILL-2.1 [LICENSE.txt](https://github.com/Deducteam/rocq-hollight/blob/d325e1c912d824556a7e06d1c10e9266190e75a6/LICENSE.txt).
Crucially, the packaged
[`Logic/theorems.v`](https://github.com/Deducteam/rocq-hollight/blob/d325e1c912d824556a7e06d1c10e9266190e75a6/Logic/theorems.v)
declares translated results as axioms. The
[`reproduce` route](https://github.com/Deducteam/rocq-hollight/blob/d325e1c912d824556a7e06d1c10e9266190e75a6/reproduce)
regenerates proofs using HOL Light 3.1.0, hol2dk 2.1.0, Lambdapi 3.0.0 and
Rocq 9.0.0; package compatibility with Rocq 9.2 is not a replay of that
route. Functional extensionality, propositional extensionality and
constructive indefinite description remain foundational premises.

**Disposition.** Proof-transport reference; importing the distributed
axiomatic theorems is refused under the local assumption audit. An untrusted
translator can in principle emit terms for the existing Rocq kernel, but
reuse still needs regenerated proof closure, permitted assumptions, exact
local definition alignment and an incorporation-time license decision.
No concrete local theorem replacement is selected, no reciprocal source is
copied, and no local replay or removed obligation is claimed.

## Discovery collections and search limits

The [Rocq package catalogue](https://rocq-prover.org/packages) and
[Corelib catalogue](https://rocq-prover.org/corelib), the
[Archive of Formal Proofs topic index](https://isa-afp.org/topics/), the
[Iris research index](https://iris-project.org/), and the
[Toccata verified-program gallery](https://toccata.gitlabpages.inria.fr/toccata/gallery/)
provide broader discovery surfaces. They lead respectively to Rocq packages,
Isabelle/HOL developments, separation-logic artifacts and Why3/Frama-C case
studies. Entries found there are qualified in the subject inventories; a
catalogue's membership alone supplies neither project compatibility nor a
successful local replay. The survey does not assert that every entry in
every library, or unpublished academic work, has been examined.

SMTCoq is a further [source-backed certificate-checker candidate](https://github.com/smtcoq/smtcoq)
for arithmetic obligations, and the same family read on SAT and SMT witnesses
rather than on the constraint and pseudo-Boolean ones above. Its Rocq-proved
checkers accept witnesses from ZChaff, veriT and CVC4, and an accepted
witness makes the corresponding proposition a theorem in the kernel, so a
solver answer is imported without trusting the solver. cvc5 appears on the
default branch as the backend of the `abduce` tactic and is not a fourth
certificate checker; the project site lags that branch and is not the place
to read the solver list. cvc5's own Alethe output is no substitute either:
the solver is unverified and the documented output can carry `hole` steps
standing for rewrites the translation cannot express. The actual
[LICENSE](https://github.com/smtcoq/smtcoq/blob/master/LICENSE) is CeCILL-C
version 1.0, a weak copyleft the FSF describes as somewhat like the LGPL and
records as GPL-incompatible, so it is neither permissive nor LGPL-compatible;
its reciprocity attaches to a modified module rather than to a caller that
only links. It is a discovery lead requiring a concrete supported
certificate, a licence reading at the selected version and an assumption
audit, rather than an integrated replacement for the project's existing
admission checks or kernel. A reflective importer whose result the Rocq kernel
re-checks has R-05-015's shape and is the route R-05-017 names; it is not admitted
on an external verdict and is not a second logic under R-05-016a. Q27a distinguishes
that route from the extracted checkers above. Q3b still owes the exact supported
solver, witness, plugin and Rocq replay, and Q27c records the terms that govern it.
