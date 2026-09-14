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
and admission proofs. `add_0_r`, `add_succ_r`, `add_comm`, `add_assoc`,
`mul_add_distr_l`, `sub_diag`, `sub_0_r`, `mul_0_r`, `leb_refl` and `eqb_refl`
refer directly to the identically named `PeanoNat.Nat` theorems. `eqb_true`
uses the forward implication of `PeanoNat.Nat.eqb_eq`. These are proofs over
the same `nat`, addition, subtraction, multiplication and Boolean comparisons,
so no representation bridge or new premise is required.

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

## Certified search and the register's standing refusals

The constraint-programming and pseudo-Boolean literature carries proof
checkers whose soundness is machine-checked, so a solver's answer can be
re-established without trusting the solver. The register already decides most
of what this repository may do with them, and the decision is not uniform.
The entries F06 through F11 are qualified on 2026-09-13 and are recorded
under that decision, not against it.

**What the pattern admits, and what of it is built.** R-05-066 names the
asymmetric-trust pattern and keeps it: an untrusted producer whose output the
already-existing checkers re-validate is admissible and free to be arbitrarily
aggressive, because the rule it reads targets *minting a checker* rather than
the pattern. Its criterion is narrow in the direction that matters here, an
optimizer being admissible exactly where an existing checker decides its
output and no new checker is introduced. The portable
[LRAT experiment](../../implementation/static-memory-certificates.md) invokes a
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
it does not admit. R-06-011 fixes the admission axioms as the two checkers,
the spec and policy statements, the CHERI-TAL soundness metatheorem and the
Sail model they check against, and R-05-164 reads the declared assumption set
off that inventory, so a third shipped checker is an amendment to R-06-011
decided at the review gate and never an import decided here. R-05-064 is the
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
HOL4; LeanCSP, PBLean and lrat-catcher are Lean, and F05 already records that
this inventory does not introduce Lean as a project trust language; SCIP,
cvc5 and the proof-logging and trimming papers carry no proof assistant at
all. None of them retires an interim.

**The infeasibility question, recorded and not recommended.** A checked
*infeasibility* certificate would move a verdict from "the search found no
placement" to "no legal placement exists", which is a yield other than
tightness, so neither R-05-105 nor its artifact-level generalization R-05-106
disposes of it. Q27a records the remaining conditions. It is a shipped
checker, so R-05-066's no-new-checker clause holds against it and so does
R-06-011's inventory, which names two checkers and not three; R-05-064 has
already deleted the TCB category
it would reintroduce, and R-05-104 refuses whatever ILP machinery its encoding would carry.
R-05-020's three demonstrations are owed on top of all of that. F06 is the
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
R-08-014 is the open infeasibility question stated above and nothing else: an
accepted certificate licenses one run and proves nothing about the search that
produced it, acceptance failure does not imply the model is satisfiable, only
a subset of FlatZinc constraints is expressible in DRCP, and the reported
overheads are measured rather than proved. Promotion past Reference would need
a FlatZinc rendering of the local placement problem, an argument that the
rendering is the problem the register states, the three R-05-020
demonstrations, and, because shipping it is minting a checker, the R-06-011
amendment that section records as decided at the review gate and not here.
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
