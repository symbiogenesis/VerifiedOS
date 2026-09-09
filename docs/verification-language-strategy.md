# A Verification-First Systems Language: Strategy and Research

> Non-normative research and design proposal. Scheduled experiments belong to the implementation checklist; this document supplies no admission rule, semantic anchor, or accepted trust assumption.
> The [requirements register](requirements-register.md) governs VerifiedOS; the [typed assembly language](typed-assembly-language.md) governs the certificate language.
> Research snapshot: 2026-09-08. Upstream capabilities below are distinguished from proposed integration work; a language sketch is not an implemented compiler.

## Recommendation

The bounded tooling qualification is scheduled as Q19 in [the implementation checklist](implementation-checklist.md#q-assessment-actions), with acceptance owned by [interactive-evidence discipline](spec.md#r-05-018a), [audited reuse](spec.md#r-05-018b) and [SMT reconstruction](spec.md#r-05-017). Q20 schedules the combined language acceptance experiment: a comparison contract, a conditional integrated authoring trial, and a conditional optimized-artifact promotion trial. General grading, a new frontend and external portability remain exploratory beyond those cells.

Build toward one developer-facing systems language, starting with a target-parametric Rocq library and an integrated source/proof workflow over its supported components.
Separate the reusable framework from its first concrete instance, VerifiedOS's CHERI target.
The useful synthesis is an Idris-like specification layer, Rust-like explicit ownership and representation, and C#-like discoverability and diagnostics, elaborated into Rocq through explicit semantic interfaces.
It does not require a new proof kernel or a dependently typed on-device checker.

Substantial parts of this workflow already exist, including combinations that reach beyond a source-only component theorem.
The [closest prior art](#closest-matches-to-the-complete-workflow) is DeepSEA for a Rocq-oriented systems language and certified representation/lowering, Isabelle's Sepref/LLVM framework for reusable imperative refinement, and the verified Dafny subset through CakeML for familiar contracts connected to machine code.
For the capability boundary, [memory-model-parametric symbolic execution and Morello-Cerise](#capability-aware-and-parametric-verification) supply particularly relevant mechanized results.
The local experiment should identify what can be reused from those results before implementing equivalent machinery; its remaining uncertainty is compatibility with the selected semantics, assumptions and clients, as well as maintenance cost.

The local hypothesis is that executable specifications and proof-producing construction combinators, parameterized by proved operation and representation laws, can remove repeated specification-to-implementation work while leaving the project's semantic-anchor budget unchanged.
The discriminating experiment is a bounded buffer operation: prove its contract using only the declared interface laws, instantiate those laws over the selected CHERI-aware program semantics, and show that changing the store or its bound breaks the proof.
A library that only proves a second hand-transcribed model, without relating the implementation to it, fails that experiment.

The hypothesis carries a precondition this repository does not currently meet, and it belongs in the recommendation rather than in a caveat further down.
Removing *repeated* specification-to-implementation work presupposes enough authored specifications for there to be a repetition, and [the crown-jewel inventory](crown-jewels.md) books all but a handful of its rows as not authored while [the critique](critique.md) reads exactly that as the project's binding constraint.
The library's value therefore lands on the second and third client rather than the first, and while that constraint holds the cheaper move is to author specifications and let the repetition appear before building the thing that removes it.

The register already separates the two halves this proposal needs: [semantic anchors are frozen and exhaustively enumerated](spec.md#r-05-019), while [a verified compiler is proof transport between two existing anchors rather than an anchor, and is admitted freely](spec.md#r-05-021).
The generic library and its construction combinators are transport in that sense, which is what makes them cheap to admit.
A surface language's elaborator is not: it is a translator, and [a new semantics, program logic or translator is admitted only on three conditions](spec.md#r-05-020), Coq-native or mechanically bridged, non-duplicating of an existing anchor, and retiring an interim it replaces.
This proposal meets the first two and names no interim for the third, so the frontend has a gate to clear that the library does not, and nothing below should be read as having cleared it.
The VerifiedOS instance adds definitions and theorems over those anchors, not a parallel operational semantics or a non-CHERI deployment path.
Other projects could supply different proved instances without changing the generic library or acquiring VerifiedOS's security claims by implication.
Its first usable result can be a verified source-level component; an admitted optimized binary remains a later result dependent on the existing compiler and artifact-verification work.

## Language Product Contract

The full combination is a research objective, not a demonstrated property of this proposal. Its foundations draw on strong existing work, but library qualification alone cannot establish C# productivity, Rust performance or a production binary with a complete proof chain. Q20 makes their conjunction an explicit experiment. No finite survey can establish that it includes every latest idea; a new result earns integration by closing a measured gap with compatible semantics and evidence.

**One language means one authoring surface for executable definitions, contracts and proofs.** A component package contains its operational definition, independently reviewed intended behavior, explicit representation choices and supporting lemmas. Ordinary callers use typed APIs and inferred routine obligations; library authors prove the representation and ownership rules those APIs expose. Rich dependent mathematics remains available for difficult properties. This organization permits generated intermediate languages and target code underneath the surface; it must not require the pilot's author to maintain a second handwritten optimized implementation to make the first execute.

That last condition is deliberately stronger than the current bring-up plan's manual Gallina-to-C refinement path. It applies first to the bounded family Q20 tests. Existing kernel and storage refinements retain their owners; their replacement requires an equivalent demonstrated path, not an assumption that every abstract Gallina algorithm can be lowered efficiently. If successful clients can express their code only by dropping into a separately maintained implementation language, the unified-language trial fails even when both programs have valid proofs.

| Desired quality | Design commitment to test | Evidence needed before claiming it |
| --- | --- | --- |
| C#-like productivity | Discoverable APIs, local inference, concise contracts, actionable diagnostics, navigation, reproducible package builds and stable interfaces | Time to implement, diagnose, review and change representative tasks, including a client not used to design the library. Syntax resemblance and proof-search success rates alone do not decide this. |
| Rust-like safety and control | Ownership, temporary borrowing, explicit layouts, predictable failure and bounded resource use, with reusable safe interfaces to proved primitives | Checked ownership and functional contracts, negative alias/escape/failure cases, and the required transport to the actual machine. A new systems subset need not accept every Rust program, but records its restrictions. |
| Idris/Gerty-style verification | Dependent specifications, erased proofs, indexed protocols and explicitly interpreted resource grades in the same workflow | Kernel-checked terms with the accepted assumptions, totality or progress where claimed, and sound resource interpretation. Routine code must not require authors to understand every underlying calculus. |
| Production performance | Specialization, in-place representations and the selected backend's existing optimization duties | Comparable final code size, stack, allocation, memory traffic and target execution measurements. A cost proof is separate from a claim of competitive throughput. |
| Maintainability | Abstract public contracts, generated representation glue where proved, deterministic builds and dependency-aware proof replay | A semantics-preserving refactor, an internal representation change and a genuine contract change, with review and repair effort reported separately. Unrelated clients should not need representation facts. |

C#'s [language strategy](https://learn.microsoft.com/en-gb/dotnet/csharp/tour-of-csharp/strategy) treats tooling, learning resources and compatibility as part of feature development. Matching that experience therefore also takes maintained libraries, documentation, package compatibility and debugging support. The proposed resource discipline excludes parts of ordinary .NET programming; the pilot tests a bounded systems workflow, not parity with C#'s application ecosystem.

**The optimized executable is the software golden artifact.** For a selected source closure and target, call the final image `B`. Q20's promotion trial uses those exact bytes on the Sail emulator and on every available compatible target execution environment; production admission and resource evidence refer to `B` as well. No later manual rewrite or unchecked optimization produces the shipped implementation. If optimization, linking, a dependency or configuration changes the image, the new image needs its own evidence. Hashes identify the subject; the source-correspondence and artifact proofs establish what it means.

The independently reviewed contract remains a mathematical description of intended behavior. It can have an extracted host oracle, and the machine retains its independently authored Sail semantics. Neither needs to be textually identical to machine code. The saving is eliminating an independently maintained production implementation for the supported family, while preserving independent ways to detect a wrong contract. This software claim does not turn the host simulator into the fabricated processor.

The experiment distinguishes **source-verified**, **artifact-connected** and **production-qualified** results. The first has a checked component theorem; the second connects the authored subject through representation and lowering to exact bytes; the third also meets the applicable admission, resource, security and target-evidence obligations. Bring-up can stop at an earlier result, but its success cannot be reported as the last one. Q20c consumes the existing compiler and assurance milestones rather than paying for their unfinished proofs inside a small integration estimate.

The everyday automation policy follows the same split. Infer routine ownership, bounds and effect obligations where reliable; expose unresolved goals and counterexamples with their source context; allow explicit lemmas for harder mathematics. Timeouts and unsupported constructs stay distinct from disproved contracts. Proof search and optional AI assistance may propose code or lemmas, but they cannot weaken the reviewed contract or grant acceptance. Expressiveness is available when needed without promising automatic inference or proof of arbitrary dependent programs.

## Research Landscape

This is a broad, decision-oriented survey of primary papers, project documentation, and implementation repositories, not a claim to enumerate every language or establish the absence of a newer preprint.
It emphasizes developments from 2024 onward, retaining earlier systems where they supply a missing part of the proposed design.
Links in each entry are its evidence; moving documentation describes the snapshot, not a pinned dependency or a reproduced benchmark.
No surveyed toolchain is demonstrated by these sources to deliver the entire requested combination on VerifiedOS's CHERI target.
The project-fit columns assess that initial instance, not the general usefulness of these systems on other architectures.
Architecture independence is also distinct from prover independence: the proposed reusable framework still checks proofs in Rocq.

### Rust and Low-Level Verification

| System | First-class verification and useful idea | Evidence boundary and project fit |
| --- | --- | --- |
| [Verus](https://verus-lang.github.io/verus/guide/) | Rust executable, specification, and proof modes; contracts, ghost state, inductive lemmas, and SMT automation. Strong reference for an integrated systems-programming workflow. | Its guide explicitly excludes verifying the verifier and Rust/LLVM compilers. A solver verdict is not a Rocq certificate. Borrow its UX and proof/library organization; do not equate source verification with certified bytes. |
| [RefinedRust](https://plv.mpi-sws.org/refinedrust/) | Refined ownership types for safe and unsafe Rust, interpreted in Iris; generated proofs checked in Rocq. Particularly relevant to verified implementations behind safe APIs. | The foundational theorem concerns the embedded Rust model. Translation from actual Rust and subsequent compilation remain distinct boundaries. Best-aligned Rust proof infrastructure for the existing Radium anchor, not proof of all Rust or rustc. |
| [Aeneas](https://github.com/AeneasVerif/aeneas) | Charon MIR/LLBC translation to functional definitions lets ordinary Rust programs be verified with functional reasoning. | The current README names Lean and HOL4 as its most mature backends, despite also providing Coq and F*. Unsafe and concurrency support are ongoing work. The [2024 symbolic borrow-checking result](https://arxiv.org/abs/2404.02680) is not a verified rustc backend. Pilot the actual Rocq subset before choosing it. |
| [hax](https://hax.cryspen.com/) and [hacspec lineage](https://hax.cryspen.com/publications/) | Rust-to-prover translation and specification-oriented Rust, especially for cryptography. The 2025 hax paper and protocol applications demonstrate multi-prover workflows. | The homepage names Lean, F*, and Rocq; current tutorials emphasize Lean and F*. A listed backend is not feature parity or proof of final machine code. Useful for executable specifications; Rocq integration needs an example-specific check. |
| [Creusot](https://github.com/creusot-rs/creusot) | Rust contracts and logical models, including reasoning about mutation; translates to Coma within Why3. | Active implementation, but its ordinary Why3/solver route is not a foundational Rocq proof of Rust lowering or compilation. An interactive prover backend alone does not validate the frontend. A useful donor for model views and post-borrow specifications. |
| [Flux](https://github.com/flux-rs/flux) | Refinement types integrated into Rust; lightweight value invariants can make bounds and API constraints part of signatures. | A practical refinement-checking candidate, not a general dependent proof assistant or established Rocq-to-binary chain. Borrow predictable inference and concise refinement diagnostics, while measuring the supported fragment. |
| [Prusti](https://github.com/viperproject/prusti-dev) | Contract-annotated Rust through Viper, with panic/overflow checking and an editor workflow. | A useful established comparator, not assumed to track current Rust: the inspected repository retains an older pinned nightly. Viper verification does not itself produce the project's admitted proof evidence. |
| [Kani](https://github.com/model-checking/kani) | Bit-precise model checking, proof harnesses, nondeterministic inputs, and checks for unsafe-code defects. | Excellent complementary counterexample search. Results depend on harness assumptions, supported operations, and sufficient unwinding; they are not automatically unbounded inductive theorems or Rocq certificates. |
| [RefinedC](https://plv.mpi-sws.org/refinedc/) | C ownership/refinement annotations and predictable Lithium automation with foundational Iris/Rocq proofs. | Strong proof-engineering precedent, but its C model is not interchangeable with CHERI-C. Reuse reasoning patterns or proved transport, not a second authoritative memory semantics. |
| [CN](https://doi.org/10.1145/3571194), [VST-A](https://doi.org/10.1145/3632911), and [Iris for CompCert C](https://doi.org/10.1145/3632848) | Respectively separation-logic refinement types for systems C, foundational annotation verification, and integration of CompCert C reasoning with Iris. | Distinct routes, not one toolchain: CN's Cerberus/solver boundary differs from VST-A's Coq proof construction. The CompCert/Iris work is the closest semantic fit for the C path; none establishes the project's CHERI port merely by using C. |
| [C*](https://arxiv.org/abs/2504.02246) | Programmable proofs and symbolic states in the same C development surface. | An important 2025 language-design experiment; the detailed assessment below separates its prototype from its intended interaction model. |

For existing Rust components, evaluate RefinedRust first when foundational ownership reasoning is decisive, and Aeneas when the actual supported safe fragment makes functional translation simpler.
Verus is a strong ergonomics comparator, not a drop-in replacement for the repository's proof authority.
RustBelt supplies semantic foundations for Rust safety; it is not itself a push-button functional verifier for arbitrary crates.

### What the Rust Verifiers Contribute

**Verus: proof resources need ownership too.** Its [variable modes](https://verus-lang.github.io/verus/guide/reference-var-modes.html) separate runtime values from `ghost` mathematical values and `tracked` proof resources.
Both ghost and tracked data are erased, but tracked resources retain ownership discipline during verification.
This is a better design reference than treating every erased value as freely duplicable: an immutable sequence snapshot may be copied in reasoning, while permission to mutate a cell must not be duplicated.
Its [interior-mutability libraries](https://verus-lang.github.io/verus/guide/interior_mutability.html) distinguish a cell's identity from its changing contents; an invariant-based cell can expose a predicate on every observed value without promising an immutable snapshot of shared mutable storage.
For `VerifiedComponents`, borrow this separation in the library interface, with resource ownership interpreted in the chosen separation logic, not a new trusted Rust-like checker.

Verus's `spec`/`proof`/`exec` function modes are not merely comments: they separate mathematical computation, reasoning, and deployed execution.
Contracts plus small lemma calls are the everyday surface; quantified reasoning still needs attention to triggers, unfolding, and solver behavior.
Its [assumptions guide](https://verus-lang.github.io/verus/guide/tcb.html) explicitly names `assume`, external proof bodies, and external executable specifications as ways to introduce assumptions.
The proposed equivalent is an inspectable transitive assumptions report, with no silent conversion of an external-body contract into an accepted component theorem.
Ergonomics and mature examples make Verus a serious comparator, but translating arbitrary Verus verification conditions into Rocq would be a separate verification project, not a library wrapper.

**Creusot: specify the end of a borrow.** The current [guide](https://guide.creusot.rs/) describes Rust-to-Coma translation followed by Why3find proof search.
Its [architecture](https://github.com/creusot-rs/creusot/blob/master/ARCHITECTURE.md) explains the RustHorn-inspired representation of a mutable borrow through its current and final values, using a prophecy resolved when the borrow ends.
Pearlite's `*` and `^` notation exposes those values; pure logical values are not subject to the runtime ownership checker.
This makes a container operation returning a mutable element reference specifiable without exposing the whole heap: say what the element initially contains and how its eventual value determines the restored container.
Borrow-end specifications, model views, and a reusable specified standard library are the transferable ideas; adopting Coma or trusting its solver encoding is not required to reproduce that API discipline in Rocq.

**Prusti: make restoration obligations visible at the call site.** Its [pledges](https://viperproject.github.io/prusti-dev/user-guide/verify/pledge.html), including `after_expiry` and `before_expiry`, express what holds after a returned mutable reference expires.
The vector example preserves length, replaces the selected element with the final borrowed value, and preserves the other elements.
That example's wrappers are marked `trusted`: it demonstrates useful contract vocabulary, not foundational verification of those wrappers.
The [verification guide](https://viperproject.github.io/prusti-dev/user-guide/verify/summary.html) also explicitly limits its general guarantee to partial correctness; a terminating result satisfies the contract, but termination is not thereby established.
For this project, implement the restoration lemma itself and discharge termination separately where required.

The practical choice is therefore not a contest between interchangeable Rust verifiers.
Use Verus to evaluate proof authoring and erased permissions, Creusot and Prusti to evaluate borrow contracts, and RefinedRust for a foundational ownership route already aligned with the architecture.
A verifier's convenient annotation syntax does not remove the cost of specifying a primitive, proving its implementation, or connecting its source model to the deployed artifact.

### Dependent Types, Effects, and Ergonomics

| System | Contribution to the ideal language | Boundary to retain |
| --- | --- | --- |
| [Idris 2](https://idris2.readthedocs.io/en/latest/tutorial/multiplicities.html) | Full dependent programming, type-directed holes, resource protocols, and explicit erased/linear/reusable arguments through quantitative type theory. | Its compiler and totality implementation are not the Rocq kernel. Its default Scheme and alternative reference-counted C backends do not imply a GC-free, allocation-free, CHERI-verified runtime. |
| [F*, Low*, and Pulse](https://fstar-lang.org/) | Dependent types, indexed effects, ghost computation, SMT/tactics, and low-level programming. Pulse adds an imperative separation-logic surface; [PulseCore](https://fstar-lang.org/papers/pulsecore-indirection-2025.pdf) is a PLDI 2025 foundational result. | The logic is F*, not CIC. Foundational PulseCore does not make every F* verification or extraction step Rocq-checkable. [Pulse is now integrated into F*](https://github.com/FStarLang/pulse); treating the old separate repository as the current tool would misjudge maturity. |
| [Lean 4: mvcgen](https://lean-lang.org/doc/reference/latest/The--mvcgen--tactic/) and [grind](https://lean-lang.org/doc/reference/latest/The--grind--tactic/) | Dependent executable programming with monadic verification-condition generation and proof-producing, SMT-style automation in the same environment. A particularly relevant current convergence of programming and proving. | Ordinary Lean proof terms are checked by Lean, not Rocq. Native compilation and runtime behavior are separate from proving a Lean function's theorem. Borrow the interaction and automation architecture, not a second admission kernel. |
| [Dafny](https://dafny.org/) | Readable contracts, ghost methods, calculational proofs, datatype patterns, and a mature language-server experience. Closest direct syntax/interaction comparator to the requested C# ergonomics. | Distinguish ordinary Dafny's solver/compiler pipeline from the [CPP 2026 verified subset through CakeML](#closest-matches-to-the-complete-workflow), which proves substantially more of the verification/compilation chain in HOL4. Neither supplies this project's Rocq/purecap backend or runtime discipline. |
| [SPARK](https://www.adacore.com/about-spark) | Language-level contracts, explicit data flow, proof of runtime-error freedom, and ownership for pointers in an industrial systems setting. | Serious practical comparator, but Ada/GNAT and its proof tooling are not the chosen Rocq/CHERI path. Source-level proof and tool qualification do not establish the final artifact theorem. |
| [LiquidHaskell](https://ucsd-progsys.github.io/liquidhaskell/) | Refinements and equational proofs expressed as code; useful models for lightweight contracts and reflection. | Haskell's runtime and the solver/compiler trust chain do not satisfy this target merely because the types are precise. |
| [Granule and Gerty](https://granule-project.github.io/) | Graded, linear, and dependent types for resource use, effects, and permissions. The project lists 2024 fractional-uniqueness work and 2026 work relating graded-type designs. | Research foundations, not an off-the-shelf systems compiler. General grades belong in source proofs until justified by an existing admission obligation; they do not authorize new TAL grade axes. |

Agda and ATS are useful background precedents for dependent programming and, in ATS, erasing proofs while retaining low-level code.
Stainless/Scala and the Spec#/Dafny lineage are additional contract-and-ergonomics comparators.
They are not evaluated here as current deployment candidates; their present backend coverage and integration costs remain unassessed.
Likewise, an effect system such as Koka's or a linear extension to Haskell addresses resource/effect structure, not by itself functional correctness against a specification.

Koka's relevance extends beyond effects: its [fully in-place programming work](#embedded-verification-and-certified-synthesis) supplies a resource-disciplined functional fragment, while AddressC supplies an implemented imperative proof surface. Those are separate contributions and neither requires adopting Koka's runtime.

The most directly relevant recent advances are therefore not a single new universal language: they are foundational Rust verification, live proof-state interaction, imperative dependent verification in Pulse and Lean, and more trustworthy extraction in Rocq.
AI proof synthesis can help in all these workflows, but contributes candidate programs, contracts, and proof scripts only. A generated contract still needs independent review and a generated proof still needs kernel checking.

### Compilation and Executable Models

| System | What it establishes or enables | Consequence for this project |
| --- | --- | --- |
| [Live Verification in an Interactive Proof Assistant](https://doi.org/10.1145/3656439), PLDI 2024 | Incremental construction of low-level programs and their proofs inside Coq, with symbolic state at the cursor. | Closest precedent for the proposed Rocq-library-first UX. Reproducing the interaction is smaller than designing a new language and runtime. |
| [Rupicola](https://github.com/mit-plv/rupicola) and [Bedrock2](https://github.com/mit-plv/bedrock2) | Relational compilation from functional descriptions to imperative code, plus a low-level verified compiler and end-to-end examples. | Directly useful construction techniques, and the one row here this repository has already measured rather than surveyed: M1.6 stood the stack up whole and found its verified exit emitting base-integer RISC-V with no capability instruction anywhere, which is the non-capability compilation target [purecap-only](spec.md#r-18-002) forbids, while the C-printer exit that does reach a usable target carries no theorem at all. Reuse the construction technique and treat the target as unbuilt; the planned Clight transport needs its own demonstrated connection. |
| [MetaRocq](https://metarocq.github.io/) | Quotation, verified type checking, and erasure; its bibliography includes verified extraction to OCaml/Malfunction in 2024 and the consolidated typechecking/erasure account in 2025. | Useful metaprogramming and proof infrastructure. Erasure is not native compilation; the documented safe checker also states a strong-normalization assumption. Inspect each theorem's assumptions rather than inferring them from the project name. |
| [CertiRocq, formerly CertiCoq](https://github.com/CertiRocq/certirocq) | Gallina compilation to Clight and WebAssembly. | The current README says large parts are verified and others remain in progress. General Gallina compilation includes representation/runtime issues; it is not an automatic static-memory CHERI backend. Monitor or use for host tools, not the first on-device route. |
| [CakeML](https://cakeml.org/) and [Pancake](https://cakeml.org/pancake.html) | CakeML demonstrates proof-producing translation and compilation to machine code. Pancake pursues explicit-memory systems programming using lower compiler layers without a GC. | Closest architectural evidence that the executable-reference goal is feasible. Their HOL foundation and target models are different; adopting them would not be a small Rocq library change. |
| [Cogent](https://github.com/NICTA/cogent) | Systems-oriented code/proof co-generation and refinement to C, with Isabelle proofs and file-system case studies. | A valuable precedent for functional views of imperative storage and an intentionally restricted language. Not an Idris-like general dependent language or a Rocq-native pipeline. |
| [Jasmin](https://jasmin-lang.readthedocs.io/en/latest/) | Executable formal semantics, precise low-level control, and a Rocq-verified compiler to assembly for cryptographic code. | Distinguish compiler correctness from its trusted safety analyzer and EasyCrypt proof route. Its result is not automatically a proof about linked CHERI bytes or the project's leakage model. Borrow explicit representation and instruction-level accountability. |

F*/Low* with KaRaMeL, HACL*, Vale, and EverParse provide particularly strong evidence that high-level verified descriptions can yield useful high-performance native components.
Their production use supports feasibility, not equivalence between their trust assumptions and this repository's.
The comparison is about theorem endpoints and runtime obligations, not whether a project uses the word "verified."

### Closest Matches to the Complete Workflow

Several systems already combine executable models, implementation construction and foundational proofs; some also connect them to machine execution. The useful comparison is the supported component and the theorem's subject, rather than a score for how many language features a project lists. The following assessments are readings of upstream results, not locally reproduced integrations.

**DeepSEA: the closest systems-language precedent.** The [OOPSLA 2019 systems paper](https://flint.cs.yale.edu/certikos/publications/deepsea19.pdf) integrates imperative implementations, pure Coq views, explicit data representation and certified abstraction layers. It generates representation relations and proofs connecting functional views to Clight, then uses CompCertX for compilation to assembly. Its examples include SHA-256 and part of CertiKOS's memory manager. This directly addresses the repeated specification/implementation/refinement work motivating `VerifiedComponents`, with an implemented language rather than proposed notation.

The restrictions matter: objects are statically allocated, loops have selected forms, and the source type system is deliberately simple. Rich correctness properties are proved in Coq; a generated functional view describes the program and still needs an independently chosen correctness theorem. Bottom-layer primitive specifications have separate implementation obligations. Neither the demonstrated representation nor its assembly endpoint is the selected CHERI/Sail instance. Read its representation generator and layered composition before designing equivalents; reproducing its entire compiler would be separately scoped work.

DeepSEA's [2024 smart-contract work](https://arxiv.org/html/2405.08348v1) develops a different backend, through MiniC to an EVM formalization, with gas-sensitive simulation. This reaches further on that target, but it is not an update establishing a CHERI systems backend. The paper explicitly assumes injectivity of concrete Keccak hashes at the final connection, which is false as an unrestricted mathematical statement; its eWasm route lacks a correctness proof. Those assumptions cannot enter this project's component theorem. Keep the systems and EVM editions distinct when selecting an artifact, and audit the exact source-to-generated-view subject as well as the generated proof.

**Sepref and Isabelle-LLVM: much of the proposed library already has an analogue.** [Generating Verified LLVM from Isabelle/HOL](https://drops.dagstuhl.de/storage/00lipics/lipics-vol141-itp2019/LIPIcs.ITP.2019.22/LIPIcs.ITP.2019.22.pdf) combines abstract functional algorithms, concrete imperative data structures, separation logic and automated refinement to a shallow embedding of an LLVM fragment. This is a close comparator for `Models`, `Representation` and `Build`, with generated code and checked refinement rather than annotations alone. Its trusted boundary includes the shallow embedding's interpretation as LLVM, code generation and subsequent LLVM compilation; its model also assumes an unbounded supply of memory. Verification of the embedded fragment is not a theorem about all LLVM optimizations, allocation failure or final bytes.

The [parallel-refinement development](https://www21.in.tum.de/~lammich/isabelle_llvm/) goes beyond the initial sequential pilot: it exposes generic separation-logic rules parameterized over a memory model, array implementations of scoped splitting/index combinators, and verified sorting algorithms. Compare those combinators with the proposed scoped borrow-restoration interface. Reusing their design is immediately possible; transferring their Isabelle/HOL proofs, concurrency model and LLVM memory interpretation into the admitted Rocq/CHERI chain is separate work. They demonstrate that this library architecture is practical, without establishing its local instance or a portable timing guarantee.

**Verified Dafny through CakeML: familiar contracts with a foundational compiler path.** [Verified VCG and Verified Compiler for Dafny](https://arxiv.org/abs/2512.05262), CPP 2026, formalizes an imperative subset with arrays, loops and mutually recursive methods in HOL4. It proves a verification-condition generator and compilation to CakeML, whose verified backend supplies the machine-code path. This is a stronger comparator than ordinary Dafny verification followed by an unverified native compiler.

The [paper's composed example and boundary](https://research.chalmers.se/publication/550353/file/550353_Fulltext.pdf) are precise: the McCarthy 91 example combines proof of the generated verification condition with the verified rules and compiler. Source parsing/elaboration begins with an untrusted Dafny frontend exporting an S-expression, so source correspondence still needs attention. The formal subset does not cover all Dafny, and its CakeML references, arrays and exceptions do not establish the static-memory runtime required here. Compare its separation of frontend, VCG, discharged conditions and compiler theorem when specifying evidence packages. Its [published mechanization](https://github.com/CakeML/cakeml/tree/751ecd45c16b11ee0c3fd1280be7a6d798b5c457/compiler/dafny) is an artifact to inspect, not a new acceptance kernel or scheduled dependency.

**Pancake: a practical systems result with a split proof boundary.** The [Ethernet-driver study](https://arxiv.org/html/2501.08249v1) combines explicit-memory systems programming, a HOL4-verified compiler using CakeML's backend, and automated Viper verification, with measured performance close to its C comparator. This is useful evidence that a restricted imperative language can support real driver work. The study also explicitly leaves the Pancake-to-Viper translator, Viper/SMT infrastructure and linker trusted, and does not compose the driver's reentry properties and compiler result into one theorem. Its sound HOL4 Hoare logic provides a route toward a smaller boundary. Retain the distinction between practical automated verification and the fully composed foundational result; neither supplies CHERI lowering here.

**Fiat-Crypto and Bedrock2/Kami: stronger examples in lineages already selected.** [Fiat-Crypto](https://github.com/mit-plv/fiat-crypto) generates specialized arithmetic through proved transformations and supplies a proved translation to the Bedrock2 AST. Its README explicitly separates that from its unproved language printers, including the C printer. Reuse the generator pattern and existing field-arithmetic work under [its current owner](../THIRD-PARTY.md#the-cryptography-upstreams); the survey does not create another arithmetic generator or claim its printed C has acquired a compiler theorem.

The [Bedrock2 umbrella development](https://github.com/mit-plv/bedrock2) connects a verified program and compiler to a pipelined Kami processor for an IoT-lightbulb example, including a proof connecting its software-facing and hardware-facing RISC-V specifications. That is stronger than a source theorem or even an isolated compiler theorem. It demonstrates that a composed software/hardware result can exist in Coq. Its ordinary RISC-V specifications and processor are different from the pinned Sail term and CHERI target here; M1.6's local backend finding still stands. Q2b can inspect how the interfaces compose without inheriting that example's theorem or replacing this project's machine model.

**seL4: a delivered artifact comparator.** Its [proof overview](https://sel4.org/Verification/proofs.html) documents functional correctness, binary correctness and security properties, with availability depending on configuration. Its [assumptions](https://sel4.org/Verification/assumptions.html) retain hardware, boot/assembly and device obligations, and distinguish modeled information flow from timing channels. This is an established comparison for an executable artifact with substantial assurance, rather than a proposal for a new proof language. The register already records the different proof-authority boundary at [proof diversity](spec.md#r-05-016a); seL4's configuration-specific results do not supply this platform's purecap target, source workflow or TAL evidence.

### Capability-Aware and Parametric Verification

**Memory-model-parametric symbolic execution has a Rocq foundation.** [Compositional Symbolic Execution for the Next 700 Memory Models](https://arxiv.org/abs/2508.15576), OOPSLA 2025, mechanizes a generic compositional symbolic-execution theory and instantiates it with multiple memory models. This is particularly close to the proposed separation between generic reasoning and instance-specific memory laws.

The [CHERI instance and scope limitations](https://arxiv.org/html/2508.15576v2) prevent overreading that result. The language is a sequential demonstrator; the CHERI instance is an idealized architecture-independent assembly memory model with a proved over-approximation soundness result for verification. Its under-approximation result for bug finding and implementation in Gillian are future work in this version. The work does not supply a compiled CHERI-C component or a connection to this checkout's Sail term. Inspect its memory-action, resource-production/consumption and framing premises under Q2b before inventing equivalent interfaces. Adopting its separate semantics directly would still face the semantic-anchor gate; a reusable proof pattern or proved connection is the useful output of that comparison.

**Morello-Cerise reaches adversarial-code encapsulation on a full-scale ISA.** [Morello-Cerise](https://www.cl.cam.ac.uk/~pes20/pldi25-paper646-camera-ready.pdf), PLDI 2025, combines Cerise's Iris logical relation, Islaris reasoning about known code, and T-CHERI properties of arbitrary code. It proves strong encapsulation for an example component above the full-scale sequential Arm Morello ISA model in the presence of arbitrary untrusted code. This is directly relevant to the stronger guarantee interfaces proposed here, and goes beyond a bounded-buffer functional theorem. Its subject is a particular Morello component and ISA, not a generic CHERI-RISC-V compiler, all Morello software, concurrent hardware or a theorem about this processor. Q2b's machine comparison should read the actual encapsulation argument; Q3b still owns the selected slice's evidence.

**Gillian's language instances are different results.** The [TACAS 2023 CHERI-C work](https://arxiv.org/abs/2211.07511) formalizes a memory model in Isabelle/HOL and uses extracted code for concrete execution in Gillian. It must not be conflated with the later Rocq symbolic-execution foundation. [Gillian-Rust](https://giltho.github.io/publications/Gillian-Rust.pdf), PLDI 2025, combines semi-automated unsafe-Rust reasoning with Creusot's safe-Rust workflow through translated contracts. Its lifetime and prophecy reasoning makes it a useful borrow-contract comparator. The hybrid tool's Rust source verification does not become a Rocq certificate or a compiler-to-bytes theorem merely because some of its logical foundations have mechanizations. Keep it as a design comparison alongside RefinedRust, not a replacement for the selected Radium route.

### Further Reuse and Emerging Compiler Work

| Project | Demonstrated contribution | Disposition for this proposal |
| --- | --- | --- |
| [Heapster](https://paulhe.com/assets/spec-extraction-oopsla.pdf), within [SAW](https://github.com/GaloisInc/saw-script) | Extracts functional specifications from memory-safe imperative LLVM code using a permission type system; the Coq/interaction-tree soundness result concerns a simplified assembly formalization. | Useful reverse-direction comparator for deriving a model from implementation. A generated model still needs an independently reviewed contract; LLVM ingestion, source correspondence, native compilation and the new logic/effect interface need their own justification. No SAW verdict is admitted automatically. |
| [Rocqet](https://github.com/rocqetry/rocqet), PLDI 2025 | Nested family polymorphism supports extensible definitions and proofs, with an extensible certified-C-compiler case study. | Directly relevant to refactoring semantic families together. Its documented Rocq/OCaml tuple needs local qualification; it is compiler-proof infrastructure rather than a CHERI backend or a reason to replace ordinary modules before reuse demands it. |
| [Pyrosome](https://github.com/DIJamner/pyrosome), [2026 thesis work](https://www.csail.mit.edu/event/framework-modular-metatheory-and-verified-compilation) | A Rocq framework for modular language metatheory and composable verified translation; examples include System F with references, imperative and linear calculi. | Research reference for language extension, linking and pass composition. The examples do not establish a production systems language, native optimizer or this project's source-correspondence theorem. |
| [Crane](https://bloomberg.github.io/crane/), [RocqPL 2026](https://bloomberg.github.io/crane/papers/crane-rocqpl26.pdf) | Extracts Rocq programs to readable modern C++, with configurable data mappings and a library-oriented adoption model. | Strong integration/ergonomics reference. The authors explicitly prioritize an unverified extractor, and the mappings and runtime support do not imply static-memory CHERI execution. Read it as an alternative for other host integration needs, not a new device exit. |
| [Verity](https://github.com/lfglabs-dev/verity) and powdr's [Yul-to-EVM compiler](https://github.com/powdr-labs/yul-compiler) | Lean-based contract/proof construction and verified lowering are active developments. Powdr's [July 2026 theorem](https://powdr.org/blog/yul-compiler) relates successfully compiled Yul and assembled EVM execution under matching-state and sufficient-gas premises. | Verity's [boundary record](https://github.com/lfglabs-dev/verity/blob/main/TRUST_ASSUMPTIONS.md) retains an explicit IR-to-Yul bridge hypothesis and trusted `solc`. These are separate toolchains: a proposed connection needs matching Yul semantics and a composed theorem over the supported fragments. An EVM result or passing execution tests establishes neither that composition nor Rocq/CHERI admission. |

The practical ordering is to inspect the existing construction and representation solutions first, then the actual capability-law interfaces, and only then consider infrastructure for a larger family of languages. These results strengthen the case for qualified reuse. They do not justify importing every listed tool or treating a missing local connection as a missing result everywhere.

### Embedded Verification and Certified Synthesis

Small embedded languages and proof-producing tools provide implemented pieces of the proposed workflow, even when they do not provide its machine connection. Evaluate their notation, proof rules and certificate construction before designing a new surface; distinguish an upstream demonstration from an integration this repository has reproduced.

**AddressC: imperative syntax over an existing proof language.** [AddressC](https://github.com/koka-lang/AddressC) defines functions, mutable locals, loops and structure-access notation that yield ordinary Iris HeapLang programs, with Diaframe automation. Its [functional/imperative tree correspondence](https://www.microsoft.com/en-us/research/publication/fiptree-tr/) accompanies the PLDI 2024 work on move-to-root, splay and zip trees: simple functional arguments support proofs about imperative algorithms. This is a concrete Rocq-native authoring reference alongside LiveVerif, not just a syntax sketch. It is neither a C compiler nor a verified Koka backend. The README's reversal specification is partial correctness, conditional on termination; the documented build uses Coq 8.19.1 and older Iris/Diaframe revisions. HeapLang representation, primitive rules and compiled CHERI behavior are distinct obligations, so its frontend cannot be relabeled as a target-independent instance.

Its cited predecessor [MiniC](https://gitlab.mpi-sws.org/iris/c) provides a monadic embedding into HeapLang, with proved symbolic execution and verification-condition generation. The repository explicitly says it is unmaintained and will not track current Iris. Read its construction as a reference, not as a preferred new dependency.

**SuSLik: synthesize the program and reconstruct its proof.** [SuSLik](https://github.com/TyGuS/suslik) synthesizes heap-manipulating programs from separation-logic specifications. Its [certification component](https://github.com/TyGuS/suslik/blob/master/certification.md), accompanying ICFP 2021, emits correctness certificates for HTT, Iris or VST. This is directly relevant to the proposed proof-producing builders: the search procedure need not be trusted when the emitted program's certificate is checked. Coverage differs by backend, and the HTT path defaults to leaving pure lemmas `Admitted` unless its proof option is enabled; advanced examples still require manual pure proofs. A generated certificate is therefore a candidate, not evidence of a closed proof. Qualify an actual certificate and its assumptions, preserving the intended contract; neither the existing allocation primitives nor an ordinary VST/HeapLang certificate establishes a CHERI connection.

**CFML and Sisyphus: reusable reasoning and proof repair.** [CFML](https://github.com/charguer/cfml) translates OCaml source to a Rocq AST and supplies characteristic formulas, higher-order separation logic and tactics for imperative proofs, including ownership and time-credit examples. Its documented environment uses Coq 8.20 and OCaml before version 5. The frontend/source connection and subsequent compilation remain separate from the proof over the AST. [Sisyphus](https://verse-lab.org/sisyphus/) uses an existing CFML proof to repair verification after a program change, including changes in algorithm structure; its published evaluation covers 14 OCaml programs. It is a focused maintenance experiment, not a general Rocq proof-repair service. Read these for representation and repair patterns; an OCaml runtime, CFML's logic and its dependencies do not become admitted by that reading. Incorporation would also require its own licence review, with Sisyphus advertising AGPLv3+ terms.

**Perennial/Goose: reuse the crash-recovery work already selected.** [Perennial](https://github.com/mit-pdos/perennial) builds concurrency, crash weakest preconditions, recovery and crash-refinement reasoning on Iris; its Grove extension handles distributed systems. The implementation checklist already selects the Perennial/GoJournal journal design for Gallina, so this is an existing source to consult at that work, not a new proposal to ship Go. [Goose](https://github.com/goose-lang/goose) explicitly trusts its Go-to-model translation and semantics, and Perennial documents a backwards-incompatible migration to new Goose. A selected edition, its crash model and the connection to this project's semantics must be explicit. Reusable Iris lemmas are not an automatic transfer of a Goose program theorem.

**Fully in-place programming: functional descriptions with a resource theorem.** [FP2](https://www.microsoft.com/en-us/research/publication/fp2-fully-in-place-functional-programming/) identifies a linear functional calculus whose programs can execute without allocation or deallocation and with constant stack space, under its restrictions. It discusses static uniqueness and dynamic reference-counting embeddings; the implemented Koka route uses the latter. This is a stronger resource-design reference than an effect annotation alone, but it does not make arbitrary Koka programs allocation-free or supply a verified CHERI compiler. Investigate static reuse laws for bounded components without importing a reference-counting runtime. [creditmonad](https://github.com/anfelor/creditmonad) is a separate Haskell DSL for testing amortized costs in persistent data structures. Its executable tests can falsify a proposed accounting argument; they neither prove a universal client bound nor connect that bound to target WCET.

**Velvet/Loom and LeetProof: an implemented integrated workflow.** [Velvet](https://github.com/verse-lab/velvet), built on [Loom](https://github.com/verse-lab/loom), combines a Dafny-like imperative surface, specification and invariant annotations, property testing, automated proof discharge and interactive fallback in Lean. Partial correctness and termination can be proved separately and combined. It is a close design comparator for Vela's desired interaction, not a Rocq library or a CHERI deployment route. [LeetProof](https://arxiv.org/abs/2604.16584) stages specification validation, program/invariant synthesis and final proof construction around that verifier. Its most transferable step tests that intended outputs satisfy a contract and that deliberately wrong outputs do not, before spending effort on implementation proofs. Output uniqueness is appropriate only for a deterministic contract; a nondeterministic contract must permit its whole intended result set. Property tests and LLM reviews cannot establish correspondence to informal intent. The paper explicitly separates testing guards that may contain `sorry` from final correctness certificates; this project's analogous guards remain outside accepted proof dependencies.

**Priority:** read AddressC and SuSLik first for proof-surface and construction reuse, compare Velvet/Loom/LeetProof for workflow and specification testing, and consult Perennial within the journal work already selected. CFML/Sisyphus and FP2 are focused design references; creditmonad and MiniC are testing and historical references respectively. None removes the missing CHERI primitive rules, and none warrants a new compiler or semantic anchor merely to reproduce its demonstration.

### Research That Changes the Experiments

**Optimization reuse: CompCert Chamois.** Its [current development](https://certicompil.gricad-pages.univ-grenoble-alpes.fr/Chamois-CompCert/) and [authors' overview](https://www.pepr-cyber-arsene.fr/publications/jfla24.pdf) provide verified or validated transformations, including loop and block optimizations and scheduling. Its BTL approach validates proposals from untrusted optimization machinery. M1.3 compares an applicable mechanism before authoring equivalent passes; Q20c measures the resulting image. Ordinary CompCert memory and target premises do not establish capability-tag preservation, trapping behavior, isolation, constant-time behavior or this platform's cost bounds. This is reuse within the already required backend, not a new speed-only checker. The selected fork's actual licence and dependency terms still need reading before incorporation; a forge classifier is insufficient.

The performance gap cannot be settled by compiler lineage: [CompCert's own description](https://compcert.org/compcert-C.html) reports approximately 90% of GCC `-O1` performance on ARMv8. That upstream measurement neither establishes parity with Rust/LLVM nor predicts this custom target. Compare the selected backend on actual clients, retain valid transformations that help under the platform's constraints, and state the remaining gap.

**Representation and primitive contracts: VeriFFI.** [A Verified Foreign Function Interface between Coq and C](https://www.cs.princeton.edu/~appel/papers/VeriFFI.pdf), POPL 2025, generates VST function specifications from Gallina types and functional models, connecting high-level clients to proved C primitives with concrete representations. The checklist already names VeriFFI in its host-side checker fallback; Q2b and Q19c additionally inspect its contract-generation mechanism alongside DeepSEA before inventing representation glue. The paper does not demonstrate the complete CertiCoq end-to-end theorem. More immediately, [the existing third-party audit](../THIRD-PARTY.md) records a VST version and transitive-assumption mismatch with this repository. A design comparison is useful now; direct incorporation requires resolving those concrete blockers and reading the selected artifact's licence, not weakening the assumption audit.

**Borrowing precision: Polonius Alpha.** The Rust project's [August 2026 announcement](https://blog.rust-lang.org/2026/08/04/enabling-polonius-alpha-on-nightly/) enables a flow-sensitive borrow analysis on nightly. A loan returned on one branch need not prevent mutation on the branch where it is absent. This is an appropriate ownership-UX comparator for returned loans and reborrowing, with a pinned version and the announcement's unsupported cases recorded. The first library's lexical scoped combinators remain a bounded pilot, not the eventual expressiveness ceiling. Q20b records awkward rewrites its restrictions cause; importing rustc's analysis would still require a sound interpretation over the admitted semantics.

**Resource inference: RaRust.** [Automatic Linear Resource Bound Analysis for Rust via Prophecy Potentials](https://arxiv.org/html/2502.19810v1), a 2025 preprint, infers symbolic linear bounds for a safe Rust fragment using shared and prophecy potentials for borrowing. Its soundness is against its resource-aware borrow calculus, with costs assigned by explicit `tick` events. The stated limitations include unsafe code, generics, closures, trait objects and nonlinear bounds. This is a closer inference reference for a future named resource obligation than inventing a general grade engine first. An untrusted analyzer may suggest potentials and bounds for Rocq to prove; its printed answer supplies neither a certificate nor a target WCET bound. Source events, peak memory and machine time retain distinct interpretations. No analyzer port is scheduled by this reading.

**Specification coverage: check what the theorem constrains.** [Static Coverage in Deductive Software Verification](https://www.amazon.science/publications/static-coverage-in-deductive-software-verification), FMCAD 2025, uses unsatisfiable cores in the Boogie/Dafny setting to help expose vacuity, unconstrained behavior and redundant specifications. This complements the register's existing inhabitation witnesses and Q19c's implementation mutants. Q20 checks observable outputs, state changes and failure branches, then deliberately removes a selected postcondition or output constraint to see whether independent specification checks expose the loss. A non-vacuous theorem may still ignore the field that matters. Reuse that testing idea with existing instruments; a general Boogie-to-Rocq coverage tool is not implied, and even complete formal coverage would not prove the informal intent correct.

**Proof stability: measure development rather than successful proof counts.** [On the Impact of Formal Verification on Software Development](https://cseweb.ucsd.edu/~mcoblenz/assets/pdf/OOPSLA_2025_Dafny.pdf), OOPSLA 2025, reports interviews with experienced Dafny users identifying debugging, proof hardening and review as important costs. This is qualitative evidence, not a productivity multiplier. Dafny's [verification-optimization guide](https://dafny.org/dafny/VerificationOptimization/VerificationOptimization) gives transferable methods: isolate obligations, inspect resource use and vary search seeds to find fragile automation. Q20b measures actionable-diagnostic latency, review effort and proof discovery after semantics-preserving edits, separately from replay of already checked terms. The relevant practice can be reused without importing Dafny as an acceptance tool.

These additions qualify mechanisms against existing owners. Pinning another repository alone closes no integration gap. The current tuple, client theorem, generated-code boundary, transitive assumptions, actual licence and measured benefit decide adoption. A blocked package can still inform a design; it cannot be described as an installed or proved part of the stack.

## What a Golden Binary Can Mean

A binary is executable, but being executable does not make it a correctness oracle for itself.
The target is a **proof-carrying executable reference implementation**: exact bytes, interpreted by a named target semantics, proved to refine an independently reviewed contract.
For VerifiedOS that semantics is the pinned Sail term. A different target needs its own interpretation and artifact theorem.
An optimized implementation can then serve as a fast oracle for other implementations of that contract.
The portable object is the contract and its reusable proof structure, not a universal binary or a target-independent timing theorem.
Independent specification review and differential tests remain necessary because agreement with itself cannot reveal a wrong specification.

The evidence chain separates the following judgments:

- Source elaboration preserves the meaning of the authored program and its contract.
- The concrete representation implements the abstract values and state transitions.
- Compilation, assembly, linking, and image construction preserve the required behavior.
- Final bytes satisfy the required admission properties under the pinned Sail model.
- Hardware implements that model at the tier the platform actually claims.

Different target binaries may implement the same abstract contract through different representations, provided their input/output encodings and permitted observations are related explicitly.
For a nondeterministic or underspecified contract, correct implementations need not produce identical traces; differential comparison must respect the contract rather than assume byte-for-byte output agreement.

Functional refinement alone does not prove constant-time behavior, worst-case execution time, absence of hidden allocation, or robust isolation against adversarial linked code.
Those remain the separately scoped obligations of the [specification](spec.md) and [admission language](typed-assembly-language.md).
Neither an optimizing compiler nor an SMT success verdict closes them by implication.

## C*: The Useful Idea and the Actual Boundary

[C*: Unifying Programming and Verification in C](https://arxiv.org/html/2504.02246v1), April 2025, integrates executable C, assertions, and programmable proof blocks using familiar C syntax.
Its valuable idea is a single development surface: inspect a symbolic program state, transform it with a proved lemma, and continue writing implementation code.
Proof libraries become ordinary reusable programming tools instead of a separate after-the-fact activity.

The paper's implementation and evaluation impose important limits:

- The proof kernel is HOL Light, exposed through a C interface. It is not Coq/Rocq.
- The symbolic execution engine is trusted. A small LCF kernel does not by itself validate the engine's interpretation of C.
- Separation logic is axiomatized, with integers and pointers treated alike in the logical memory model. This is not the project's purecap provenance model.
- The prototype manually interleaves runs of the symbolic executor; the live IDE is future work in this version of the paper.
- The evaluation includes small examples and the buddy allocator's attach operation, not verification of an entire allocator or a compiler-to-binary theorem.
- The authors explicitly retain a weaker allocator specification that does not establish that every free block occurs in the free list. This is a concrete warning about specification adequacy.

**Disposition:** borrow the integrated proof-block workflow and reusable state-transformation libraries.
Do not import HOL Light as an additional admission authority, treat its symbolic executor as foundational, or infer a CHERI-aware verified compilation path from its use of C.
The closest project-compatible implementation of that interaction is a Rocq-native workflow over the program logics already selected here.

## Idris Flexibility Without an Idris Runtime

Idris 2's [quantities](https://idris2.readthedocs.io/en/latest/tutorial/multiplicities.html) distinguish erased values, values used exactly once, and unrestricted values.
This is more useful than simply adding dependent array lengths: ownership protocols can evolve in types, and the type signature can state which indices are unavailable at runtime.
However, linear use of a parameter is not the same as unique ownership of all reachable storage, and neither guarantees stack allocation or eliminates garbage collection.
Rust borrowing also permits temporary aliases with lifetime constraints; an exact-use multiplicity is not a substitute for that discipline.

The [Idris theorem-proving guide](https://idris2.readthedocs.io/en/latest/tutorial/theorems.html) distinguishes total proofs from partial programs and warns about its totality checker's implementation.
The [backend documentation](https://idris2.readthedocs.io/en/latest/backends/index.html) describes Scheme and reference-counted C among its execution routes.
Neither document supplies a verified optimizing CHERI compilation theorem.
Thus Idris 2 is a design reference here, not an assurance shortcut.

The proposed split is deliberate:

- **Specification/proof world:** dependent functions, indexed families, existential packages, induction, rich mathematical structures, and reusable verified algorithms. Elaborate into CIC; use only its accepted assumptions and reject unresolved proof holes.
- **Runtime world:** explicit finite representations, machine integers, bounded arrays, regions and resource handles, ownership/borrowing, and statically accounted effects. The VerifiedOS instance represents applicable handles with CHERI capabilities. Rich types may describe these values without becoming runtime objects.
- **Proof automation:** arbitrary off-device search may time out or fail. Successful search produces a checked term; nontermination of a tactic never produces a theorem or permission to ship.

This is not a promise to embed all of Idris 2 unchanged in Rocq.
Universe rules, conversion, positivity, equality elimination, and quantitative resource judgments need a specified mapping.
In particular, CIC does not acquire a linear context because a frontend spells `owned`; the ownership discipline needs a semantic soundness proof in the existing program logic.
For the initial library, that discipline is exposed through predicates and proved combinators rather than a new type theory.

Erasure has a concrete test: two terms differing only in proof data must have the same relevant behavior under the erasure relation.
A runtime loop cannot read an erased length. It can read a stored length proved equal to the erased index, or use a compile-time specialized constant.
An existential packet length discovered while parsing therefore remains a runtime integer with an erased proof, not magically compile-time knowledge.

### Reading the Graded-Type Claims

The fixed quantity set in Idris 2 is a language implementation choice, not a definition of every quantitative type theory.
[Idris 2: Quantitative Type Theory in Practice](https://arxiv.org/abs/2104.00480) describes erasure and resource protocols in Idris 2; it is not evidence that Idris lets a program replace its grading algebra.
Comparisons below distinguish a calculus parameterized by an algebra, a prototype implementing particular grades, and an extensible production language.
These are different levels of evidence.

**Idris 2 offers useful libraries without arbitrary grades.** Its actual [linear IO library](https://github.com/idris-lang/Idris2/blob/main/libs/linear/Control/Linear/LIO.idr) indexes `L` by result usage and supplies `Pure0`, `Pure1`, `PureW`, and corresponding continuation types.
It can require an action's result to be used linearly, which is useful for state-changing resource APIs.
The implementation explicitly repeats definitions because multiplicity polymorphism is absent; its `Usage` datatype does not change the compiler's core quantity algebra.
The immediate lesson is to build state-indexed operations and proved combinators now, not wait for a fully general graded compiler.

**Granule is a working graded-language laboratory, with indexed rather than full dependent types.** Its [language guide](https://granule-project.github.io/granule.html) demonstrates exact-use modalities, security labels, and IO effects.
For example, the essential shape of its vector map signature is `(a -> b) [n] -> Vec n a -> Vec n b`: the callback is available for the vector's number of elements.
Its `twice` example composes usage through multiplication, while security examples reject a private-to-public flow and permit ignoring an unused private input.
These are different interpretations of grading, not interchangeable meanings of the same numeric annotation.
Its [implementation](https://github.com/granule-project/granule) provides an interpreter/checker and a compiler to Haskell with a runtime library; the separate LLVM compiler is described as experimental.
The language guide describes programmer-customizable modalities as a goal. Built-in grades and theoretical parameterization should not be presented as a finished general plugin system.
Exact callback accounting also does not specify map's element order; a functional contract is still needed.

**Gerty implements GrTT's distinction between computation use and type use.** In [Graded Modal Dependent Type Theory](https://arxiv.org/html/2010.13163v2), a dependent function binder carries a pair of grades, with further bookkeeping for dependencies in the typing context.
The [Gerty implementation](https://github.com/granule-project/gerty) illustrates this with the binder `(a : (.0, .2) Type 0)`: no computational use of `a`, but two uses in the remaining type.
That is more precise than tracking runtime erasure alone and can recover restricted parametric reasoning inside a dependent setting.
It is not unrestricted dependence without constraints: elimination rules must respect resource usage, and graded modalities are needed to use parts of compound values differently.
The paper's strong-normalization result is explicitly for a restricted two-universe fragment, not every conceivable extension of the language.

Gerty's typechecker optimization is concrete and narrow: for a suitable quantitative semiring, a zero type-use grade lets application checking omit a substitution into a codomain that does not semantically depend on the argument.
It does not erase arbitrary proof obligations or skip checking whether a program is valid.
The paper evaluates small fanout examples, with benefits dependent on whether grade equality uses normalization or SMT; extra solver calls can make the optimization slower.
The implementation exposes `--tyc-optimise`, but this is not evidence of a production-scale or self-optimizing verification compiler.
First-class grade terms and internally defined semiring instances are explicitly future work in the paper. The inspected README does not establish that these extensions are completed.

**GraD supplies a semantic test for what grades actually guarantee.** [A Graded Dependent Type System with a Usage-Aware Semantics](https://arxiv.org/html/2011.04070v2) uses a partially ordered semiring and a heap-based, usage-aware operational semantics.
It tracks runtime demand, checking but discarding irrelevant type-use counts when computing that demand; it does not retain GrTT's separate type-use vector.
Its key point is that ordinary progress and preservation do not prove correct resource accounting: a separate usage-aware soundness theorem is necessary.
The paper derives irrelevance noninterference and a single-pointer property under additional algebraic conditions, and reports Coq mechanization of selected syntactic metatheory, not a fully mechanized native compiler.
Its simplified dependent calculus uses `Type : Type`; it must not be adopted as this project's consistent proof logic.
Use it to guide a resource interpretation inside CIC, retaining Rocq's universes and logic.

Even the meaning of `0` and `1` needs proof: in a Boolean semiring, `1 + 1 = 1`, so grade `1` does not establish single use.
GraD distinguishes the conditions needed for unusability of zero from those needed for linearity and its stronger single-pointer result.
Its single-pointer property concerns the paper's heap graph, not CHERI capabilities, arbitrary imperative aliasing, DMA, or revocation.
The connection from such a grade to a concrete operation must be proved in the existing program semantics.
Likewise, a security lattice needs an observation model and noninterference theorem; a privacy budget needs probabilistic semantics and a sensitivity/composition theorem; an operation count needs an instruction/cost connection before it says anything about WCET.

**Proto-Quipper is a useful boundary case, not a systems backend.** [Linear dependent type theory for quantum programming languages](https://arxiv.org/abs/2004.13472), by Fu, Kishida, and Selinger, is the work corresponding to the [LICS 2020 DOI](https://doi.org/10.1145/3373718.3394765), with an extended LMCS version in 2022.
It combines linear quantum resources with classical parameters indexing circuit families and includes a prototype.
The transferable idea is to distinguish a resource from the duplicable description or shape used to index it.
No-cloning does not mean physical quantum systems can never be discarded; a language's explicit disposal or uncomputation discipline is a separate rule.
Quantum semantics add no direct implementation advantage to the bounded classical components proposed here.

**Design consequence:** keep runtime representation, erasure, permission ownership, protocol state, effects, and quantitative bounds as distinct questions.
Start with library-level proofs of the particular relationships needed by real clients.
General grading becomes worthwhile when it eliminates repeated resource derivations across those clients, not merely because many analyses can be described by an algebra.

## Target Abstraction and Tooling Evolution

The framework can hide architecture from ordinary component authors, but cannot remove architecture from the proof chain.
Separate source portability, generic proof reuse, concrete representation correctness, and artifact security.
A component qualifies for a target only when that target supplies the laws and guarantees it requires.
Making the interface small does not make the target's compiler, memory model, or hardware proofs small.

### Portable Interfaces and Concrete Instances

| Layer | Reusable content | Instance-specific evidence |
| --- | --- | --- |
| Language and editor | Syntax, dependent contracts, proof interaction, source locations, diagnostic protocol | Interpretation of target-sensitive features and profile compatibility |
| Pure specifications | Abstract sequences, algorithm results, format meaning, protocol transitions | Encodings and relationships to represented input/output values |
| Operation and resource interfaces | Ownership, scoped borrows, framing, explicit effects, primitive contracts | Sound implementation of each operation and law in the chosen program logic |
| Program construction | Generic induction and composition over proved primitive rules | Concrete program terms, numeric limits, layout, ABI, and compilation preservation |
| Artifact evidence | Dependency tracking, proof orchestration, explicit theorem subjects | Binary semantics, permitted contexts, linking, observation/leakage model, hardware assumptions |

For the bounded-buffer example, the interface can have this schematic shape:

```text
interface BufferStorage {
	type Handle;
	type Index;
	predicate Owns(Handle handle, Seq<byte> contents);
	predicate ValidIndex(Index index, Nat length);

	operation Read(...);
	operation Write(...);
	operation WithElement(...);

	proof ReadReturnsSelectedElement;
	proof WriteUpdatesSelectedElementAndPreservesFrame;
	proof ScopedBorrowRestoresOwnership;
	proof OperationsTerminateUnderTheirPreconditions;
}
```

This is an interface sketch, not a new memory semantics or a complete declaration of these proof rules.
The concrete rules must bind the operation's program term, entry and exit representation, arithmetic premises, effects, frame, and permitted interference.
Index conversion and iteration expose a representability bound and proved increment rule; the generic algorithm cannot assume an unbounded machine index.
The generic fill theorem quantifies over these laws. The VerifiedOS instance discharges them over its selected CHERI-aware semantics and transport, rather than asserting a flat-address memory model that CHERI must emulate.
Keep handles opaque: pointer width, integer casts, address equality, provenance, capability tags, bounds compression, endianness, and alignment are not implicit generic facts.
An operation that genuinely needs one of them states that dependency in a narrower interface.

**The interface is a proof-side abstraction and never a second way to reach the machine, which is a register constraint rather than a design preference.**
[A verified component reaches an instruction through exactly one surface](spec.md#r-05-023b), a backend primitive named by that instruction's own profile mnemonic and operand form and taking its meaning from the pinned Sail clause for it, and that surface is a duty of [the two required certifying compilers](spec.md#r-18-014) rather than a deliverable standing beside them.
An operation law here is therefore discharged over that primitive and inherits its meaning; a law that introduced a machine operation of its own would be the second surface the register says does not exist.
The constraint binds the instance and not the generic modules, and it is what keeps a target interface from quietly becoming a competing backend.

Use static module instantiation and specialization, not runtime virtual dispatch, for this abstraction.
Logical parameters and law proofs are erased; actual storage handles and required runtime metadata remain.
Inlining, layout, and generated code still need inspection and the selected compilation evidence: a module boundary alone promises neither zero overhead nor good code generation.
The high-level loop invariant can be reused even when the concrete representation and primitive proofs differ.

The first instance is CHERI-specific; the generic modules are not.
In a separate reuse project, an ordinary-architecture implementation could discharge a bounded buffer contract through verified ownership and access operations.
That example would demonstrate portability of this contract, not equivalence to VerifiedOS's isolation model or authorization for a non-CHERI VerifiedOS target.
Do not build a second implementation here merely to fill an adapter roster.

### Required Guarantees, Not Feature Flags

A target profile identifies the semantic instance, representation and ABI choices, accepted assumptions, and available guarantee theorems.
A component declares required guarantees; acceptance needs checked evidence that the profile supplies them, not a Boolean claiming that the target supports a feature.
Keep useful guarantees independent instead of making every target implement a universal interface:

| Requirement | What can be shared | What the target must justify |
| --- | --- | --- |
| Bounded storage access | Contents, bounds, and frame contracts | Representation, primitive safety, arithmetic limits, and relevant execution contexts |
| Exclusive mutation | Ownership and borrow-restoration rules | Sound resource interpretation, including any unsafe or external code |
| Isolation from adversarial code | Statement of authority confinement and allowed observations | Hardware enforcement, verified software enforcement, or sufficient restrictions on linked contexts |
| Revocation or freshness | Protocol interfaces and abstract transition requirements | The actual invalidation mechanism, epoch rules, and interference assumptions; CHERI alone is not a blanket temporal-safety proof |
| Information flow and constant time | Relational specification and some compositional proof rules | Target observations, instruction behavior, compiler preservation, and applicable hardware leakage model |
| Resource bounds | Abstract accounting and bounded-loop arguments | Mapping to allocation, instruction costs, or timing under the chosen environment |

A target may implement a guarantee differently, with additional runtime cost and proof obligations.
It may also be unable to implement it under the requested threat model.
In that case the tooling rejects the component/profile pairing or the author explicitly selects a different contract; it never silently weakens the guarantee.
Source-level ownership on conventional hardware does not protect against arbitrary unverified code with unrestricted memory access.
Conversely, a CHERI backend does not automatically establish functional correctness, liveness, or every form of revocation.
This preserves stronger optional guarantees without reducing every component to the weakest common target.

### Refactoring Without Expanding Trust

The iteration boundary is a reviewed semantic interface, not a permanent surface-language design:

```text
Editable language, inference, automation, and editor tools
	-> explicit program terms and proof obligations with source correspondence
	-> reusable Rocq component interfaces and generic theorems
	-> concrete semantic instance and proved target laws
	-> target compiler and final-artifact evidence
```

Frontend elaborators, tactics, solvers, and AI assistants may change frequently because their proposed proofs are rechecked.
Their output must still identify the intended source program and contract; proof-producing does not excuse an incorrect source translation.
Initially these outputs are ordinary Rocq terms over the existing backend, not a newly invented universal intermediate language or trusted checker.
Adding a new meaning for a language construct needs explicit semantics and corresponding proof work, even if its syntax looks like a small edit.

| Change | Reuse opportunity | Required revalidation |
| --- | --- | --- |
| Editor presentation or lemma search | Same statements, program terms, and target laws | Tool behavior; replay of new proof output, if any |
| New syntax or inference strategy with unchanged meaning | Same generic component and backend theorems | Elaboration and exact source-subject correspondence; invalidate changed source bindings |
| Refactored algorithm preserving a contract | Same client-facing contract and target primitive laws | The changed implementation's proof, termination/effects, and affected binary evidence |
| New storage representation | Same abstract algorithm contract and generic theorem | Representation and primitive laws, layout/ABI, compilation and affected artifacts |
| Changed interface law or observation model | Only results independent of the change | Dependent generic and instance proofs; no reuse based solely on unchanged names |
| Different target or emitted bytes | Applicable abstract contracts and generic lemmas | Target law instantiation and all affected final-artifact bindings and judgments |

Use dependency identities covering semantic definitions, theorem statements, representations, assumptions, source closure, and the relevant toolchain/artifact inputs.
Incremental checking can avoid rebuilding unaffected results, but a source change can invalidate its binding even when it emits identical machine code.
Retaining an exact existing binary theorem is distinct from establishing that it corresponds to the newly authored source.
Caching must follow the existing evidence discipline and cannot turn a stale success flag into authority.
No new on-device solving, grade interpretation, or open-term reduction is introduced into VerifiedOS's TAL checker.

This design supports rapid tooling iteration without requiring compatibility with a released language: this is a proposal, not a frozen public API.
The aim is to localize the proof consequences of a change, not prohibit necessary changes to the semantic interface.

## An Ideal Surface

Call the illustrative language **Vela** in this document; the name denotes a thought experiment, not a package, reserved name, or existing implementation.
Its surface borrows C#'s readable declarations and tool discoverability, Rust's ownership and representation control, and Idris's type-directed specification and proof construction.
The examples use portable buffer contracts. A build selects a concrete semantic instance and required target profile separately; CHERI does not appear in an ordinary buffer function's signature.
`byte` denotes an eight-bit value, while `usize` and represented lengths obey the selected target's explicit limits, never the build host's inferred word size.

### A Small Example

The following is original, unimplemented pseudocode, not valid C#, Rust, Idris, or a checked Rocq example.
`Span<byte, count>` describes already initialized storage with an explicit runtime length; its model is an erased logical sequence.

```text
module Buffers;

public void Fill<ghost count: Nat>(mut target: Span<byte, count>, byte value)
	effects writes(target), allocates(none)
	ensures target.Model == Seq.Repeat(value, count)
{
	var index: usize = 0;
	while (index < target.Length)
		invariant index <= target.Length
		invariant target.Model.Take(index) == Seq.Repeat(value, index)
		decreases target.Length - index
	{
		target[index] = value;
		index = index + 1;
	}
}
```

The mutable borrow supplies exclusive access for the call and returns that access on exit; its representation invariant relates runtime length to `count` and the concrete memory to `Model`.
The inferred frame states that memory outside the borrow is unchanged.
The loop guard establishes bounds and increment safety using the instance's representable-length and index laws; the natural-valued variant establishes termination.
`Take` and `Repeat` compute in specifications, not on the deployed target.
Ordinary filling of initialized public data is the example: it does not establish secure secret erasure, device-memory semantics, or resistance to dead-store elimination.

At a failed proof, the editor displays the local store, available ownership, arithmetic facts, and remaining postcondition.
An optional block such as `proof { apply Seq.repeat_extend; }` invokes a checked lemma through proof-producing automation; it cannot assert a fact without evidence.
The same module/package system resolves executable definitions, specifications, lemmas, and source locations.

A parser interface illustrates the more dependent case:

```text
public Result<PacketView<'input>, ParseError> Parse(ReadSpan<'input, byte> input)
	effects reads(input), allocates(none)
	ensures result matches PacketFormat(input.Model);
```

Here `PacketFormat` is an independently authored executable format specification.
A successful `PacketView` packages a measured payload length, a borrowed subslice tied to `'input`, and erased proofs of its bounds and format invariants.
An error carries no valid packet view. Completeness, malformed-input rejection, and treatment of trailing bytes are explicit parts of the format contract, not implications of bounds safety.
This interface is a candidate surface over the existing [descriptor-to-implementation route](spec.md#r-05-043), not a new handwritten parser specification.

### Borrowing With a Restoration Contract

The following additional examples are original design sketches, not accepted syntax or checked programs.
A container's mutable element accessor should state both its immediate result and the container state after the borrow ends:

```text
public mut byte<'loan> Element<ghost count: Nat>(
	mut target: Span<'loan, byte, count>, usize index)
	requires index < target.Length
	ensures result.Value == old(target.Model)[index]
	after_borrow target.Model == old(target.Model).Update(index, final(result.Value))
	after_borrow target.Length == old(target.Length);

public void SetFirst(mut target: Span<byte>, byte value)
	requires target.Length > 0
	ensures target.Model == old(target.Model).Update(0, value)
{
	borrow mut selected = target.Element(0);
	selected = value;
	end borrow;
}
```

`old` captures the entry model; `final` is a specification of the value when the loan is returned, not a runtime prediction.
The owner cannot inspect or independently mutate the borrowed storage while the exclusive loan is active.
Lifetime checking prevents the reference escaping its owner, and a proved restoration rule recovers the updated whole-buffer predicate.
The first library version should expose a scoped `with_element` combinator instead of implementing general returned borrows, nested reborrows, or prophecy inference.
This restriction preserves the useful contract while making its proof substantially smaller.

### Indexed Protocols and Erased Permissions

An initialization operation should return a different state, not invite callers to assert that uninitialized memory is readable:

```text
public owned Buffer<byte, count, Initialized> Initialize<ghost count: Nat>(
	owned storage: Buffer<byte, count, Uninitialized>, byte value)
	effects writes(storage), allocates(none)
	ensures result.Model == Seq.Repeat(value, count);

public owned Buffer<byte, count, Initialized> Prepare<ghost count: Nat>(
	owned storage: Buffer<byte, count, Uninitialized>)
{
	return Initialize(move storage, 0);
}
```

The runtime length and storage handle remain real data; the state index and initialization proof are erased.
For VerifiedOS the handle includes the applicable CHERI capability.
The generic invariant relates initialized storage to readable values; the instance proves the concrete layout, alignment, and applicable capability-tag rules.
Initializing byte storage is intentionally narrower than initializing arbitrary capability-bearing records.
Every exit path must return or explicitly dispose of ownership according to a proved operation; an affine move rule alone does not guarantee completion of a resource protocol.

Verus's distinction suggests a separate spelling for mathematical facts and permission evidence:

```text
ghost before: Seq<byte> = target.Model;
tracked access: WritePermit<target.Identity> = proof AcquireFromOwner(target);
Store(target, index, value, mut access);
proof ReturnToOwner(target, move access);
assert target.Model == before.Update(index, value);
```

Here `Store` has a checked contract and returns the updated permission through its mutable argument.
`AcquireFromOwner` must consume or suspend the owner's existing permission; it cannot manufacture write authority from an address or identifier.
The snapshot is duplicable, the write permission is not, and neither is emitted as runtime data.
This does not make a hardware capability erasable: in the CHERI instance, the capability used for the actual store remains in the generated code.
The library can initially hide these explicit permission steps inside the scoped borrowing combinator.

### Optional Grades With Explicit Meaning

A higher-order operation can combine a functional specification with a use count:

```text
public void MapInto<ghost count: Nat>(
	ReadSpan<byte, count> input,
	mut output: Span<byte, count>,
	uses(count) transform: PureFn<byte, byte>)
	requires Disjoint(input, output)
	effects reads(input), writes(output), allocates(none)
	ensures output.Model == input.Model.Map(transform.Model);
```

`uses(count)` is a proposed source-level callback-invocation contract on every completed execution, with termination required for this bounded operation.
It is not a promise that optimized assembly contains that many calls, nor a claim that every graded calculus interprets function-variable usage as exactly this trace count.
A library proof must connect the chosen accounting to the operation's semantics.
The contents contract rules out permutation or repetition of the wrong element, which a count alone cannot do.
Effects of captured state must be accounted for; `PureFn` cannot hide device access, allocation, or secret-dependent external calls.
For a runtime-discovered length, the descriptor supplies the loop bound; the erased index only proves its relationship to the contract.

The ideal extension permits a library to supply an algebra, its laws, and a proved interpretation, for example `CallBudget`, not just register a solver plugin that declares programs safe.
Keep erasure decisions fixed at specialization/ABI boundaries: a generic grade must not ambiguously decide whether an argument exists in a register.
Known grades may be specialized off-device; general grade polymorphism needs an explicit representation strategy.
Use separate annotations such as `effects calls(endpoint)` and `requires Public(index)` where appropriate, rather than pretending usage counts, capability permissions, and security labels are the same analysis.
An IFC checker must track control dependence as well as data dependence; a public return type alone does not exclude secret-dependent branches or addresses.

### Feature Decisions

| Area | Proposed behavior |
| --- | --- |
| Everyday data | Value records, tagged unions, exhaustive patterns, generics, traits/interfaces, local inference, immutable bindings by default. No implicit object allocation. |
| Ownership | Move-only resource owners, scoped mutable/shared borrows, explicit region parameters, and typestate backed by representation predicates. Copying requires an appropriate duplicability rule. |
| Numeric behavior | Distinguish mathematical specification integers from fixed-width runtime integers. Overflow is proved absent or represented by explicit checked/wrapping operations under the platform's existing rules. |
| Dependent contracts | Lengths, initialization states, protocol states, and abstract contents can index types. Unresolved equalities become visible proof goals rather than silent coercions. |
| Effects and authority | Reads, writes, allocation, device access, and permitted calls are explicit and compositional. FFI and assembly require contracts over the actual operation, not an unchecked `extern` promise. |
| Error handling | Exhaustive `Result`/`Option` patterns and explicit failure paths. No hidden exception unwinding or ambient service access. |
| Code generation | Static target/module instantiation and ahead-of-time specialization with explicit layout and ABI. Closures need a known environment representation; generic specialization is checked for code-size growth. |
| Target requirements | Select semantic instances and required guarantee theorems separately from ordinary source syntax. Reject unsupported requirements; never silently downgrade the contract. |
| Proof interaction | Type-directed holes, inline goals, calculational steps, lemma search, reproducible automation, and one diagnostic that distinguishes disproved, unresolved, timed out, and unsupported. |
| Encapsulation | Clients use abstract contracts; representation proofs stay with the defining module. Changing layout invalidates its proof dependencies without requiring clients to inspect the heap. |

The C# contribution is **ergonomics**, not the CLR: namespaces, precise completion, useful diagnostics, readable generic APIs, and direct navigation between code and proof.
Properties cannot conceal unaccounted effects; query syntax needs a known allocation-free lowering before it belongs in the runtime subset.
Open-ended reflection, dynamic loading, general managed objects, and an implicit async scheduler are outside that subset.
These restrictions define the initial systems-language subset and preserve VerifiedOS's deployment constraints while leaving host-side proof tooling expressive.
The framework's target parameters do not authorize a backend to add hidden allocation or a managed runtime to that subset.

### Performance Is an Artifact Claim

Erasing a proof does not erase a boxed value, an allocation, a virtual call, or a costly representation conversion.
Rust-like performance therefore needs layout control, specialization, efficient concrete data structures, and an inspected optimizing compilation path.
Compare native size, stack, memory traffic, allocation behavior, and execution time against the equivalent hand-authored baseline on the same target and inputs.
Report proof construction time and kernel replay time separately from runtime performance.

Q20a fixes the comparison workloads and acceptance thresholds before optimization, and Q20c consumes the existing backend work to run them on the exact promoted image. The same-target hand-authored baseline isolates representation and generation costs. A Rust comparison uses a matching target, ABI, checks and optimization settings where available; a commodity-machine Rust benchmark is an explicitly separate design experiment and cannot establish CHERI performance parity. Report typical execution measurements separately from worst-case bounds, emulator throughput separately from modeled target cycles, and absent hardware measurements as unavailable.

The design does not add a new verified speed-only optimizer or checker.
It uses the selected compiler's optimizations and the existing representation/refinement route; any proposed extension remains subject to the standing specification.
Source annotations for secrecy or cost express proof obligations. Constant-time and timing conclusions still come from the appropriate final-artifact judgments.

## From the Library to Bytes

The reusable part of the path is a generic contract and construction theorem, instantiated with proved target operations and representation laws.
Its preferred VerifiedOS route for an initial on-device component is:

```text
Reviewed executable Gallina contract + generic component theorem
	-> CHERI instance: proved operation laws + explicit representation
	-> Rocq proof-guided construction of an imperative implementation
	-> proved transport to the selected CHERI-C / CompCert representation
	-> CHERI-CompCert and required secure-compilation evidence
	-> final assembly, link, layout, and image validation
	-> exact installed bytes + TAL evidence + deeper CIC proofs
						 |
				the same pinned Sail term
						 |
				 hardware refinement
```

These arrows are obligations, not claims that the route is implemented end to end.
**The weakest arrow is named rather than left to be discovered, and the plan already owns it.**
Q2b chooses the device path and closes the relation to the Sail model, and the plan's own reading of that fork is that the Clight intermediate R-05-043 names is emitted by neither exit the route currently has, so the route is a second front end until that bridge exists.
Nothing in this document shortens that item, and a library built above the bridge does not build the bridge.
Another project's backend replaces the target-specific portion, not the independently reviewed contract; it must prove its own transport and artifact claims.
Within VerifiedOS, all machine-level connections still use the same pinned Sail term and the reviewed source anchors.
For a Rust-origin component, the existing Radium/source-correspondence route replaces the Gallina-to-C construction portion; no new source language displaces contained Rust by this proposal.
TCB components retain the required verified-C path.
That a component's source language is free at the admission boundary is the register's position and not this document's: [admission never gates on the source language or producer identity of a binary](spec.md#r-05-008), which is what makes a new surface language a question about proof-authoring cost rather than about admission.
It is also what leaves [source correspondence](spec.md#r-05-026) as the binding obligation instead, a proof about the wrong source subject being one the kernel accepts and that entry rejects.

For a contract `Contract`, implementation `Program`, final bytes `Binary`, and pinned machine semantics `Sail`, the central functional goal has the shape

```text
PlatformAssumptions /\ ValidEntryState /\ Represents(inputs, memory)
	-> every permitted execution of Binary under Sail
	   satisfies Contract, with outputs related by Represents.
```

Termination or reactive progress is stated separately as appropriate; a terminating postcondition is not enough to exclude divergence.
For adversarial contexts, a whole-program functional theorem is not the required robust preservation theorem.
The [source correspondence rule](spec.md#r-05-026) also requires binding the evidence to the authored source closure, not merely proving something about a convenient intermediate term.
An untrusted parser/elaborator can produce a perfectly valid proof about the wrong program; kernel checking alone does not prevent this subject mismatch.
Use a reviewed elaboration meaning and checked correspondence to the exact source subject, not just a hash attached to unrelated proof output.

The reviewed Sail model remains upstream of artifact validation and hardware refinement.
Do not regenerate ISA meaning from the new compiler or the binary it is meant to check.
Host reference execution may use extraction for testing, but that executable's trust boundary is recorded independently; its test results are not automatically proofs about the Gallina definition.

## First Deliverable

The proposed first deliverable is a small off-device Rocq package, provisionally `VerifiedComponents`, for proving bounded components through target-parametric interfaces interpreted over existing semantic anchors.
It exposes executable pure specifications, operation and representation interfaces, reusable refinement lemmas, and proof automation that produces terms checked by Rocq.
The package is useful independently of any new surface syntax.

**Its stop condition is reached before its first line, and saying so is the most useful thing this proposal currently does.**
The pilot's stated starting point is an accessible CHERI-aware imperative semantics with usable primitive rules.
The Iris-over-Sail program logic those rules would be stated in is an anchor the register enumerates and this development does not yet carry, which is why the machine-boundary connection is described as planned throughout this document; the specifications such rules would quantify over are booked as not authored across all but a handful of [the crown-jewel inventory](crown-jewels.md)'s rows; and M1.6 measured the one relational-compilation stack that might have supplied the primitives as carrying no capability awareness at all.
So the prerequisite is the work, and the library is what becomes worth building once the semantics it abstracts exists.
An earlier version would be abstracting an interface nothing can yet instantiate, which is the failure mode the interface-adequacy experiment below is designed to detect and would detect in its own first week.

This is a statement about the local instance. The [upstream capability results](#capability-aware-and-parametric-verification) already provide mechanized memory and encapsulation arguments with different subjects. Q2b's useful question is which existing rules can be connected to the pinned semantics and at what cost; the local absence is not evidence that those rules must all be invented from scratch.

### Library Contents and Reuse

The interfaces are target-parametric, but the first concrete backend is deliberately singular: instantiate them over the existing Gallina contract and selected CHERI-C transport, with the planned Iris-over-Sail connection at the machine boundary.
Use ordinary Rocq modules with explicit laws, introducing only the parameters needed by these clients.
Do not implement a universal adapter layer across every surveyed language or require a second target before a concrete client works.

| Proposed library surface | Small useful result | Existing machinery to reuse or evaluate |
| --- | --- | --- |
| Model views | A buffer's contents, length, initialized region, and frame condition share one representation predicate. | Existing Rocq lists/finite indices and the chosen memory logic; no parallel byte-address semantics. |
| Target interfaces | Generic algorithms require only named operation, representation, and composition laws. | Rocq modules and functors, informed by the [parametric symbolic-execution premises](#capability-aware-and-parametric-verification); prove one CHERI instance over the existing anchors. |
| Construction combinators | Sequence, branch, bounded iteration, and local update produce the concrete program and its refinement proof together. | Fiat/Bedrock/Rupicola-style relational compilation and SuSLik-style certifying synthesis, compared with [DeepSEA's representation generation and Sepref's refinement combinators](#closest-matches-to-the-complete-workflow). M1.6 measured the former route locally; the other systems' endpoints and compatibility remain separate questions. |
| Proof support | Normalize bounds, apply array-update lemmas, preserve frames, and expose the first unsolved goal. | Rocq tactics; Equations for dependent definitions; Iris automation where the instantiated logic supports it. |
| Source-oriented interaction | A user alternates between writing a statement and applying a proof step while inspecting current symbolic state. | Live Verification and AddressC as implemented Rocq proof surfaces; Velvet as a Lean-based workflow comparator. Use the existing Rocq editor rather than a new LSP implementation. |
| Certificate packaging | Keep the actual program term, its contract, representation relation, checked theorem, and declared assumptions together. | Existing artifact/proof infrastructure; no opaque success flag and no replacement admission format. |

The key dependent package is conceptually a concrete program paired with a proof of `Refines(program, contract)` under a named representation and entry condition.
`Refines` is the selected semantics' existing judgment or a definition over it, not a new uninterpreted relation.
The first implementation can use ordinary records, modules, notation, and tactics; MetaRocq or Coq-Elpi becomes useful only when generating repetitive terms demonstrably saves work.

SMTCoq-style certificate replay is a candidate for supported pure arithmetic goals, not a universal converter for Verus, Why3, F*, or separation-logic proofs.
Where no checked solver bridge exists, use existing Rocq lemmas or expose the goal.
Raw solver acceptance and a frontend's axiomatized library model cannot become hidden assumptions of the component theorem.

Start with a public-data, bounded buffer-fill example, then a second operation that reuses its array and initialization lemmas.
Publish the source-level theorem and its assumptions before attempting native artifact integration.
No claim of constant time, CHERI admission, or native performance accompanies a source-only result.

The first experiment succeeds only if the generated or refined implementation is the term named in the theorem, an incorrect implementation is rejected, and the second client reuses the first client's proof infrastructure without introducing another memory semantics.
The generic proof must depend only on the advertised interface, with CHERI representation facts confined to its instance.
Audit that dependency boundary and reject an instance with an undischarged required law; one working instance alone is not empirical evidence of broad target portability.
The native follow-on additionally binds the theorem and admission evidence to the final bytes and checks them against the same Sail term the hardware refinement consumes.

### Concrete Package Shape

The following are proposed module names within one package, not existing files or a request to create independent frameworks:

| Module | Public surface | Proof responsibility |
| --- | --- | --- |
| `Models` | Pure sequence updates, bounded indices, initialized-prefix views, protocol transition functions | Target-independent functional facts; no new memory model |
| `Interfaces` | Coherent program/logic signatures, primitive laws, representability and required guarantee judgments | State all generic theorem premises without treating them as discharged axioms |
| `Representation` | Buffer ownership, readable initialized cells, disjoint slices, model snapshots | Parameterized views and laws connected to concrete predicates by each instance |
| `Build` | `sequence`, `branch`, `bounded_loop`, `store`, `with_element` | Construct the instance's program terms while composing its proved rules |
| `Buffers` | `fill`, `initialize`, `update`, disjoint `copy`, then `map_into` | Generic contents, bounds, frame, termination, and effect proofs under explicit interface laws |
| `Protocols` | Indexed transitions and scoped acquisition/return | Preserve an independently specified protocol and its ownership invariant on success and failure |
| `Grades` | Optional fixed-domain accounting and checked arithmetic evidence | Interpret the chosen grade in an actual trace or resource predicate; no universal grade engine initially |
| `Instances.Cheri` | Selected CHERI program/logic interpretation, primitive implementations, concrete representations | Discharge the generic laws and connect to existing source/transport anchors; no second ISA semantics |
| `Evidence` | Theorem subject, semantic instance, required guarantees, representation, assumptions, source/build bindings | Integrate with existing artifact evidence; a metadata wrapper cannot establish correspondence |
| `Automation` | Bounds, sequence updates, frame reconstruction, named lemma hints | Produce ordinary Rocq terms and preserve useful unresolved goals |

The public component package can have this schematic Rocq module shape:

```text
Module Components (Backend : COMPONENT_BACKEND).
	Record Component (contract : Backend.Contract) := {
		implementation : Backend.Program;
		representation : Backend.Representation;
		functional : Backend.Refines implementation representation contract;
		terminates : Backend.TerminatesUnder implementation contract.entry;
		effects : Backend.RespectsEffects implementation contract.effects
	}.
End Components.
```

These qualified names stand for definitions and judgments supplied by a backend, not new axioms, actual APIs, or a claim that these declarations compile.
The module signature also requires the primitive and composition laws used by the builders; a concrete instance proves them in its existing semantics.
An abstract signature is a conditional proof interface, not permission to admit its unproved parameters as global axioms.
Pure algorithm contracts live outside this module; each backend connects their input/output models to its contract and representation judgments.
The program type, representations, logic judgments, and law proofs belong to one coherent instance; they cannot be selected independently from incompatible source semantics or memory models.
The terminating bounded-component interface is intentional; a reactive service needs a different progress contract.
The representation is shared between the entry condition, refinement theorem, and exit condition, not chosen independently to make a theorem vacuous.
Accepted assumptions are inspected transitively from the proof environment, not trusted because a record contains an empty list called `assumptions`.
The package initially stores the selected imperative term and its theorem; it does not pretend that a source-level `Component` already contains an admitted binary.

For buffer fill, the component author supplies a pure result function and an entry requirement expressed through the buffer interface; the instance provides the concrete representation.
`Build.bounded_loop` asks for an invariant, a decreasing measure, and a proved body step; `Build.store` produces the updated initialized-cell predicate and the corresponding sequence-update fact.
The library proves the induction and reconstructs the frame.
The caller still supplies meaningful functional intent, aliasing premises, and exceptional-case policy; the library saves repeated derivation, not specification judgment.

For scoped element borrowing, the core resource law has the schematic separation-logic shape:

```text
BufferOwn(target, values)
	|- CellOwn(target, index, values[index]) *
	   (forall replacement,
	      CellOwn(target, index, replacement) -*
	      BufferOwn(target, Update(values, index, replacement)))
```

The law requires a valid index and the actual layout/disjointness premises of the selected memory logic.
The generic client uses the proved rule; the instance owns its concrete layout proof. Concurrency or fractional sharing is not inferred from this sequential interface.
`*` separates resources; `-*` is the restoring implication, not ordinary reusable implication.
The continuation retains the rest of the buffer and reconstructs the whole after the cell is returned.
An ordinary Rocq record containing a permission proposition does not enforce linearity: validity comes from the separation-logic derivation, including its frame and update rules.
Start with byte buffers and lexical scope; general shared interior mutation and concurrent invariants require additional rules and are not hidden inside this small interface.

### Other Useful Libraries and Tools

**Descriptor-backed codecs.** Extend the existing format route with reusable bounds, consumed-length, failure, and round-trip lemmas.
Generate implementation and proof obligations from the same reviewed descriptor, while keeping independent malformed-input examples and semantic review.
Keep format bytes, endianness, and rejection behavior explicit in the descriptor rather than inheriting a target's native layout; instantiate storage access separately.
This is potentially more valuable than another frontend because an attacker-facing parser repeatedly needs the same representation and rejection arguments.
Do not add a competing descriptor language or independently retype the format in Vela.

**Protocol combinators.** Reuse an existing transition specification to expose operations indexed by state, such as reserved, populated, and published.
An operation returning `Result` must identify the resource state on both branches; a failed publish cannot lose ownership or invent a published token.
Start with a sequential bounded protocol.
Ring concurrency, crash recovery, freshness, and cancellation are separate semantic obligations and can make superficially similar APIs much more expensive.
Idris's linear IO demonstrates the library technique; a reusable transition theorem is conditional on the instance's actual operation laws.
For VerifiedOS, publication ordering and capability authority are discharged by its instance, not hidden behind a portable state name.

**Small graded accounting library.** Start with a fixed natural-valued event count or upper bound, proved by loop induction, plus its interpretation over the selected execution trace.
Composition, branching, and loops need explicitly different rules: sequential counts add; alternatives must agree for an exact count or use a sound upper bound; iteration needs a proved bound.
Later generalization can package semiring/order laws and an interpretation theorem, with additional premises for erasure or linearity where needed.
Keep permission fractions in the existing separation algebra rather than forcing them into a total numeric semiring.
This is a library of checked judgments, not an extension to CIC conversion or a new on-device grade solver.
An abstract event count can survive a target change; its interpretation as target cost cannot survive without the corresponding new proof.
Resource-budget exhaustion and protocol misuse are useful correctness targets; a new verified tool whose only purpose is tightening an already-sound bound remains outside the standing design.

**Proof authoring and evidence diagnostics.** Extend the existing Rocq editor and build entry point to show the active model view, available permissions, unresolved obligation, theorem subject, and transitive assumptions.
Distinguish unsupported translation, missing target guarantee, solver timeout, failed instance law, failed client proof, and stale subject binding.
Expose which obligations are generic and which come from the selected profile, so a backend failure does not appear as an unexplained source-level type error.
Record proof-edit effort and maintenance across clients, not just proof-script line count.
An external solver or AI assistant may suggest terms or lemmas; successful replay is the condition for using them.
This tooling must use current artifact identity and gate records, not create another cache whose success flag can bypass admission.

**Restricted frontend.** Only after these APIs work, parse a small subset of the Vela examples into calls to proved combinators, retaining source locations and an explicit source-correspondence story.
Keep target selection and guarantee requirements separate from ordinary buffer syntax, with explicit diagnostics when source arithmetic or effects exceed the profile.
Refactor surface syntax against the same elaborated contracts before introducing new semantic constructs; an elaboration snapshot is a useful regression test, not a substitute for correspondence evidence.
A syntax demo is cheap compared with checked elaboration, dependent inference, borrowing diagnostics, and proof preservation.
An alternative Rust-facing annotation layer should target the existing RefinedRust/Radium route; it is not a reason to build a universal Verus/Prusti/Creusot proof translator.
No new optimizer, code generator, or language runtime is necessary for the initial library.

### Existing Tooling and Implementation Owners

The [current spec](spec.md#r-05-018a) selects bounded qualification, not blanket adoption. The [checklist's Q19](implementation-checklist.md#q-assessment-actions) owns the diagnostics and selective-reuse trials and a conditional source-level component pilot; Q2b and Q3b own the existing device and assurance work. Upstream capability is not compatibility with this checkout's exact Rocq/plugin tuple, and a package installed in a switch is not a library imported by a shipped proof. No candidate below is incorporated by this table.

| Candidate and upstream | Owner and disposition | Useful capability and qualification boundary |
| --- | --- | --- |
| [Rocq LSP](https://github.com/rocq-community/rocq-lsp) and [Pytanque](https://github.com/LLM4Rocq/pytanque) | Q19a: first interaction trial | Incremental source state and Python access to goals, premises and commands through Petanque. Qualify a Rocq-compatible revision and WSL invocation; editor recovery can provisionally admit goals, so only the batch gate accepts a proof. |
| [Alectryon](https://github.com/cpitclaudel/alectryon) | Q19a: rendered-review comparison | Annotated source with actual goals and messages, usable without changing the documentation format. Its Rocq 9 path uses VsRocq; the Rocq LSP driver is not assumed stable. Qualify the backend separately and bind rendered output to its source/environment. |
| Selective Rocq stdlib, [stdpp](https://gitlab.mpi-sws.org/iris/stdpp) and [coqutil](https://github.com/mit-plv/coqutil) | Q19b: reuse before new helpers | Lists, finite maps/sets, word and arithmetic lemmas. stdpp describes an axiom-free foundation; the acceptance question is still the actual client term's transitive assumptions. Audit changed hints, notation and obligation behavior; do not upgrade the installed stdpp merely to match latest upstream. |
| [Equations](https://github.com/mattam82/Coq-Equations) and [Rocq-Elpi Derive](https://github.com/LPCIC/coq-elpi/tree/master/apps/derive) | Q19b: dependent definitions and boilerplate | Checked dependent eliminators, equality/reflection, maps and lenses with laws where supported. Experimental derivations and unsupported dependent records need their own trial; generated field laws do not prove ownership or concrete representation. |
| [CoqHammer](https://coqhammer.github.io/) | Q19b: standalone `sauto` first | Try the tactics-only package before external ATP setup. Retain explicit replay scripts and lemma sets; dependent mode can introduce UIP-equivalent assumptions, and neither search nor reconstruction supplies induction automatically. |
| [Iris/MoSeL](https://iris-project.org/mosel/) and [Diaframe](https://gitlab.mpi-sws.org/iris/diaframe) | Q19c: gated on CHERI primitive rules | Reuse BI proof contexts and symbolic-execution/abduction automation over the one admitted logic. Diaframe's language-independent core is useful; installing its HeapLang instance supplies no CHERI semantics. |
| [Hierarchy Builder](https://github.com/math-comp/hierarchy-builder) | Q19c: only if concrete reuse needs a hierarchy | Lawful mixins, structures and instances elaborate to ordinary Rocq machinery. First prove the small interface's laws; do not invent a universal target hierarchy in anticipation of clients. |
| [Actris](https://gitlab.mpi-sws.org/iris/actris) | Deferred protocol extension, not a Q19c deliverable | Dependent protocols can carry state, message constraints and transferred ownership. Separate its protocol model and Iris rules from its HeapLang channels; an actual bounded IPC connection and any liveness claim remain separate proofs. |
| [LiveVerif](https://github.com/mit-plv/bedrock2/tree/master/LiveVerif) with Rupicola/Bedrock2 | Q2b: read existing construction machinery | Joint imperative AST and correctness construction is a better starting point than a new frontend. The word-and-byte memory model, ordinary RISC-V backend and unproved C printer do not close the capability or Clight boundary. |
| [DeepSEA and Sepref/Isabelle-LLVM](#closest-matches-to-the-complete-workflow) | Q2b: representation/lowering comparison; Q19c: builder design comparison | Inspect existing generated representation relations, refinement rules and scoped combinators before authoring equivalents. Comparing those mechanisms fits the existing items; reproducing a compiler, transferring a HOL library or importing another semantics requires separate scope. |
| [Rocq memory-model-parametric symbolic execution](#capability-aware-and-parametric-verification) | Q2b: memory-law comparison; Q19c: interface design reference | Inspect concrete/symbolic memory laws and the idealized CHERI verification instance. Its soundness result does not connect it to the selected Sail term or make Gillian a checked CHERI backend. |
| [Verified Dafny/CakeML, Pancake and seL4](#closest-matches-to-the-complete-workflow) | Evidence-endpoint comparisons, no new implementation cell | Compare authored contracts, verifier soundness, compilation, linking and runtime assumptions separately; none is selected as an additional proof authority. |
| [Rocqet and Pyrosome](#further-reuse-and-emerging-compiler-work) | Deferred modularity references | Reconsider only when concrete interfaces need more than ordinary modules. Their metatheory and compiler case studies do not warrant a proof-switch change or a general frontend in Q19. |
| [AddressC](https://github.com/koka-lang/AddressC) | Q19 design comparison; Q19c surface reference | Implemented imperative notation and Diaframe proofs over HeapLang. Reuse patterns, not an unproved CHERI instance; see [the detailed assessment](#embedded-verification-and-certified-synthesis). |
| [SuSLik](https://github.com/TyGuS/suslik) | Q19c builder/certificate comparison, not a booked backend port | Synthesis with Iris, VST or HTT certificates. Check actual backend coverage and reject admitted obligations; its existing semantics are not this target's. |
| [CFML](https://github.com/charguer/cfml) and [Sisyphus](https://verse-lab.org/sisyphus/) | Q19 maintenance-design references, not scheduled installations | Characteristic-formula proof libraries and specialized OCaml proof repair. A general repair service or a new source logic requires separate scope and qualification. |
| [Perennial/Goose](https://github.com/mit-pdos/perennial) | Existing filesystem/journal work | Reuse crash-recovery reasoning where it fits the selected model. The journal design is already selected; trusted Go translation and a Goose theorem do not prove the target implementation. |
| [FP2](https://www.microsoft.com/en-us/research/publication/fp2-fully-in-place-functional-programming/) and [creditmonad](https://github.com/anfelor/creditmonad) | Resource-design references, no new implementation cell | Restricted in-place functional execution and amortized-cost testing respectively. Neither licenses a reference-counting runtime nor supplies target WCET evidence. |
| [Velvet/Loom](https://github.com/verse-lab/velvet) and [LeetProof](https://arxiv.org/abs/2604.16584) | Q19 workflow comparison; specification-testing pattern in Q19c | Lean-based execution, automated/interactive proof and staged specification validation. Borrow the workflow through existing Rocq instruments, not another acceptance kernel. |
| [MiniC](https://gitlab.mpi-sws.org/iris/c) | Historical reference only | Proved VC generation over a HeapLang embedding; explicitly unmaintained. |
| [Katamaran](https://github.com/katamaran-project/katamaran), [Islaris](https://github.com/rems-project/islaris) and [Morello-Cerise](#capability-aware-and-parametric-verification) | Q2b: machine-connection comparison; Q3b: accepted slice evidence | Compare primitive contracts, instruction reasoning and the demonstrated adversarial-code encapsulation proof. Pinned Sail meaning, translation/trace soundness and compatibility must be established; the Morello theorem is not a CHERI-RISC-V library instance. |
| [SMTCoq](https://github.com/smtcoq/smtcoq) | Q3b when SMT facts enter a proof | Qualify the exact solver, certificate format, reconstruction plugin and Rocq revisions under R-05-017. Upstream documentation of CVC4/veriT/ZChaff paths is not evidence for arbitrary current Z3/cvc5 combinations. Host solver checks remain evidence unless reconstructed. |
| [Interaction Trees](https://github.com/DeepSpec/InteractionTrees) | Deferred until a named effect-modeling need clears R-05-020 | Reusable effectful descriptions and coinductive reasoning may help, but introduce another semantic interface. Audit selected modules: optional results use UIP, functional extensionality or classical principles; no blanket assumption-free admission follows from the core library. |
| [AutoRocq](https://github.com/NUS-Program-Verification/AutoRocq) | Optional later search comparison, not a scheduled dependency | Retrieval and tactic exploration can emit replayable scripts. Qualify its Rocq/backend tuple and GPL/commercial terms first; compare with the existing workflow and tactics-only baseline without making a service a proof-gate dependency. |
| [Fiat2](https://github.com/mit-plv/fiat2) and [Trakt](https://github.com/ecranceMERCE/trakt) | Research watch, no implementation cell | Data-oriented verified transformations and goal preprocessing respectively. Neither has demonstrated the local compatibility and bounded CHERI benefit needed to displace existing machinery; this does not undo the project's existing Narcissus use. |

The first experiment retains the existing theorem statements and compares setup, manual proof edits, replay time and repair after a representative change. A candidate with no demonstrated maintenance benefit may be rejected. Additional protocol libraries, proof agents and semantic frameworks need a separately scoped item before incorporation; listing them here does not spend the Q19 pilot budgets on them. Licences and transitive notices are read from the selected upstream artifacts at incorporation, not inferred from a project's lineage or this survey.

### Experiments and Stop Conditions

Q19a and Q19b book the bounded workflow and reuse trials; Q19c books the conditional library-feasibility pilot and its interface, specification and reuse checks. Q20 books the combined authoring and optimized-artifact comparison under the [language product contract](#language-product-contract). Its integration cells consume existing implementations and proofs; they do not price building missing backends or admission machinery. The remaining rows are research proposals, and the effort ranges below remain separate research-planning judgments. Promotion beyond those bounded cells requires the repository's normal milestone and review process.
**The lowering experiment is already booked and half landed, and its boundary remains explicit.**
The plan's Q2 demonstrates one single-source lowering route on a wire parser; its host-only half, Q2a, landed with a boundary audit finding the checked relation stopping at the first of its four boundaries, and its device half, Q2b, is open.
Q19c consumes Q2b's usable primitive rules and tests generic source-level reuse; it does not charge again for Q2b's lowering or Q3b's target and fault evidence. If those rules do not exist, Q19c does not open by treating assumptions as an instance.

| Experiment | Evidence to produce | What disconfirms the approach |
| --- | --- | --- |
| Library feasibility | Generic fill plus bounded update or copy, a proved initial CHERI-aware instance, Rocq replay, and an explicit assumptions report. | Proofs concern only a separate model, require fresh axioms, or cannot express the actual ownership/representation boundary. |
| Interface adequacy | Inspect generic theorem dependencies; require every primitive/representation law and reject a deliberately missing or false one. | Clients import CHERI representation facts directly, or an instance is accepted through an unchecked law declaration. |
| Specification adequacy | Independent examples and generated checks against the executable contract, including empty/full buffers, boundary indices, overflow limits and a deliberately weakened output or failure postcondition. | A wrong store value or off-by-one variant still satisfies the purported full contract, or independent checks cannot expose the selected omitted behavior. Mutation construction failure decides nothing. |
| Proof reuse | Change a client bound within its declared limits; separately change representation and reprove instance laws while replaying unchanged generic theorems. Record manual proof edits. | Each client needs its own byte semantics or repeated low-level proof script. A shorter notation without less proof maintenance is not enough. |
| Profile enforcement | Require an isolation or observation guarantee absent from a test profile and confirm rejection; bind supported guarantees to their actual theorems. | A feature flag or static ownership alone is accepted as proof of adversarial-context isolation. |
| Tooling refactor | Change syntax or proof search while preserving meaning; measure rediscovery stability separately from replay and refresh source correspondence. Change a semantic law and confirm dependent results become invalid. | A changed source subject or law inherits cached success, or routine equivalent edits make search and diagnostic costs exceed the declared usability budget. |
| Format integration | Use an existing Narcissus-style descriptor and account for successful parsing, malformed input, and consumed bytes. | Safety proves while interpretation, rejection policy, or encoder/decoder agreement remains unspecified. |
| Native integration | Bind actual source, compiler inputs, link layout, final bytes, Sail version, and replayable evidence; reject a changed byte or stale certificate. | A source theorem is presented as the binary theorem, or a non-CHERI upstream backend is treated as the deployed target. |
| Performance and resources | Equivalent target/compiler settings, functional cross-checks, code and stack measurements, and no undeclared runtime support. | Performance relies on unproved representation changes, hidden allocation, or omitted failure/overflow behavior. |
| Surface-language value | Implement only syntax already represented by successful library clients and compare proof-editing effort. | A new parser/typechecker becomes prerequisite to the useful component, or source meaning cannot be tied to the elaborated theorem. |
| Optional external portability probe | In a separately scoped reuse project with an existing verified backend, instantiate the same bounded-buffer theorem on a non-CHERI target and report all changed proofs and weaker guarantees. | The generic proof needs target-specific rewrites, or a source-only port is reported as equivalent binary isolation. This is not a VerifiedOS deployment milestone. |

For executable contract checks, use the repository's [oracle, mutation, and QuickChick instruments](../tools/README.md) where applicable; keep negative proof tests alongside positive replay.
A release-quality component also needs a transitive assumption audit: no unresolved holes, no `Admitted`, no new unchecked axioms, and no unsafe proof-evaluation shortcut outside the accepted base.
Assumptions about primitives, FFI, the memory model, and platform behavior are named rather than erased from the report.

The lowest-hanging fruit is the shared specification/representation library with narrow target interfaces and a live proof workflow.
The initial value comes from reuse within the CHERI instance; broad portability remains a hypothesis until another instance is actually proved.
A restricted surface parser is a later usability project.
A general quantitative dependent typechecker, a Rust-equivalent ecosystem, and a verified optimizing CHERI compiler are substantial separate undertakings, not features obtained by adding notation to Rocq.

## Effort and Expected Return

### Estimation Basis

These are engineering judgments for deciding which experiment to fund, not measured productivity results, upstream delivery promises, or estimates copied into the implementation checklist.
A person-week or person-month means focused engineering effort, including local proof work, tests, documentation, and review preparation; it is not elapsed time for an intermittently staffed project.

**They are also in a different unit from the plan's, and the two are not convertible.**
[The implementation checklist](implementation-checklist.md) prices every item in attended agent-session hours, keeps a separate clock for items that ran under fan-out, fits a calibration over each clock separately on the ground that no item has been measured on both, and derives every total, range and progress figure from those cells arithmetically.
A person-month here is neither of those clocks.
Read the ranges below as relative costs *among the experiments in this document*, and read the plan's own cells for what any of this would cost this project.
A reader who converts at forty hours to the person-week will find that the smallest deliverable below exceeds the plan's entire remaining balance, and that result is an artefact of the unit rather than a finding about the work.
The estimates assume engineers already productive in Rocq and the selected program logic, stable primitive specifications, and reuse of existing libraries.
A small team needs both proof-engineering and systems/compiler expertise; dividing person-months by headcount is not a reliable calendar forecast because semantic design and review are serial dependencies.
An unfamiliar team, missing transport theorem, changing ISA/ABI, or unexpectedly weak upstream library can exceed these bands substantially.
No AI productivity multiplier is assumed. The plan's measurements of completed agent-assisted items do not calibrate these unimplemented language and compiler research projects; their task mix, review obligations and uncertainty differ.

Each row is scoped from its stated starting point. Rows overlap and are alternatives or extensions, so they must not be added as a project total.
Source-level deliverables exclude CHERI compiler construction, whole-system proofs, hardware refinement, production certification, and on-device admission unless explicitly stated.
The initial library bands include narrowly factoring already usable primitive rules into interfaces and proving the corresponding initial instance wrappers.
They do not include discovering a new memory logic, establishing missing primitive soundness, or engineering a universal backend API.
If that foundation is unavailable, the pilot reports the blocking obligation rather than consuming its budget under a claim of target independence.

| Deliverable | Effort judgment | Starting point and exit evidence |
| --- | --- | --- |
| `VerifiedComponents` feasibility pilot | 4-8 person-weeks | An accessible CHERI-aware imperative semantics and usable primitive rules. Generic fill and bounded update, narrow interface laws and initial instance wrappers; replay, mutation rejection, and assumption audit. Stop if those prerequisites cannot be demonstrated. |
| Reusable bounded-component library | 4-9 person-months, including the pilot | Start from the same primitive foundation. Parameterized initialization, disjoint copy, scoped update, documented combinators, independent client reuse, and instance/refactoring tests. One concrete instance; source assurance only. |
| Scoped borrow-restoration extension | 1-3 person-months | Working buffer predicates and frame rules. Lexical element/slice borrowing with negative alias/escape tests; excludes general Rust borrow inference and concurrent interior mutation. |
| Indexed protocol library | 1-3 person-months | A reviewed sequential transition specification and primitive implementations. One bounded protocol, with success/failure ownership and reuse by another client; excludes crash/concurrency/freshness proofs. |
| Descriptor-backed codec integration | 2-4 person-months | Existing descriptor and synthesis path already usable. One bounded format, concrete representation, parse/reject/consumed-length proofs, and reusable support; excludes inventing or porting the synthesis backend. |
| Fixed-domain graded accounting | 2-4 person-months | Existing component traces and loop rules. One event-count or budget domain, a semantic interpretation theorem, composition lemmas, and misuse tests; no generic grading inference. |
| Extensible graded proof library | 9-18 person-months | Successful fixed-domain prototype. Lawful algebra interfaces, more than one independently interpreted analysis, and checked evidence; excludes a new dependent typechecker and arbitrary privacy/timing analyses. |
| Existing-editor proof/evidence diagnostics | 3-6 person-weeks | Existing Rocq interaction and build evidence are available. Focus on local obligations, subject identity, and assumptions; excludes a new language server. |
| Restricted Vela syntax prototype | 2-4 person-months | Successful library clients. Parse their bounded subset, preserve source locations, and generate inspectable terms/proofs. A prototype is not accepted source-correspondence evidence by itself. |
| Reviewed restricted frontend | 9-18 person-months, including its syntax prototype | Working library and a fixed small source semantics. Checked elaboration/correspondence for that subset, useful diagnostics, negative tests, reproducible builds; reuse the existing backend and runtime discipline. |
| Native integration of one library family | 2-6 person-months | Starts only once the required CHERI compilation, source-correspondence and final-artifact checking routes work, and none of them does today: the device half of the lowering route is open in the plan and gated on its backend. Connect representations and obligations, bind exact bytes, and measure resources. The starting point is a condition on the row and not a description of the present tree. |
| Optional second-target bounded-buffer probe outside VerifiedOS | 1-3 person-months | Working generic library and a second backend with already proved compatible primitive/logic rules. Instantiate one family and audit proof reuse and missing guarantees. Source-level experiment only; excludes backend porting, compiler construction, and equivalent isolation. |
| General graded dependent systems-language implementation | 4-10 person-years for a limited usable research tool | Language design, elaboration, resource analysis, layout, one backend, core libraries, and editor support. Does not include a Rust-sized ecosystem or a fully verified end-to-end compiler. High uncertainty. |
| New verified optimizing CHERI compiler route | 10-30 or more person-years | A fixed source/target subset and substantial reuse of verified compiler infrastructure. Include representation, erasure/lowering, optimization preservation, ABI/link integration, and the required security-property transport. Excludes hardware proofs and a full general-language ecosystem; feasibility may require narrowing the scope. |

The final two rows are order-of-magnitude research budgets, not confidence intervals or estimates of the repository's existing compiler work.
They explain why a general language or fresh compiler is not low-hanging fruit.
There is no responsible architecture-independent estimate for a complete new target port without its ISA, memory/concurrency model, ABI, compiler evidence, and required security profile.
The optional probe budget assumes those source-level foundations already exist; it is not a budget for adding an arbitrary processor.
An existing target-parametric verified compiler can offer reusable passes and simulation structure, but target lowering, calling convention, linking, and security preservation still need separate evidence.
The framework does not reduce the repository's unfinished CHERI compiler obligations by relabeling them as an instance.
The existing [implementation checklist](implementation-checklist.md) remains the owner of scheduled work and its measured/calibrated estimates; these ranges neither replace it nor subtract claimed savings from it.
Gerty-style typechecking optimization is not separately recommended: its toy-program result establishes a technique, not a bottleneck here or a justification for new speed-only verified machinery.

### Where Time Might Be Saved

There is no measured productivity percentage for this approach. Q20 compares recurring representation, framing, bounds and proof-repair work separately from the full implementation-and-proof task, including independent review and initial integration. Its acceptance thresholds are experiment decisions fixed before measurement, not forecasts of the savings it will find.
The first clients can take longer because they pay for abstraction, primitive lemmas, tooling integration, and independent review.
Novel algorithms, concurrency, cryptographic reductions, compiler preservation, and hardware refinement should receive no assumed savings from a buffer library.

Within one target, the strongest savings mechanism is reuse of a proved representation and frame/restoration theorem across changing clients.
Across targets, reuse primarily covers abstract specifications, algorithm proofs, and authoring tools; representation and target-security proofs are separate work.
Rapid syntax and proof-search iteration can preserve these investments when the semantic contract stays fixed, while a new observation model or interface law can invalidate substantial downstream work.
The next is generation from an existing format or protocol specification, avoiding repeated implementation/proof synchronization.
Earlier ownership diagnostics may shorten debugging, but changing syntax alone is unlikely to dominate the proof budget.
General grading can reduce repeated resource accounting only if clients actually share that analysis; otherwise it adds algebra, inference, and maintenance work.

Use a break-even model instead of quoting an OS-wide percentage.
Let $L$ be upfront library and interface effort, $M$ shared maintenance, $P_j$ the attributable establishment and maintenance cost of target instance $j$, $B_i$ the comparable baseline effort for client $i$, and $A_i$ its effort with the library, including learning and integration:

$$
\operatorname{NetSaved} = \sum_{i=1}^{N}(B_i - A_i) - L - M - \sum_{j=1}^{T} P_j.
$$

Adoption pays back only when this is positive, with equivalent contract strength and evidence endpoints.
Do not count both a shared lemma and every client using it as separate upfront costs, or compare a source-only library theorem with a baseline that includes final-byte proofs.
Charge initial instance work to either its inclusive deliverable budget or $P_j$, never both. Apply the same accounting boundary to the baseline, including any existing backend prerequisites.
Measure author time, review time, proof repair after a representation change, and kernel replay separately.
For a second target, report unchanged generic theorems, changed instance proofs, unsupported guarantees, and port maintenance rather than quoting a portability percentage.
Use clients not used to design the combinators, and preserve a hand-authored baseline on the same semantics.
If realistic reuse does not repay library costs, retain the useful component proofs and stop generalizing.

### Security Gains and Their Limits

The proposal initially makes existing required guarantees easier to establish; it does not strengthen the platform merely by adding types or annotations.
A genuinely additional guarantee needs a stronger named contract and a proof over the implementation, followed by the required transport to bytes.
Target abstraction adds a useful enforcement boundary when tools reject missing semantic laws and unsupported security requirements.
It does not itself add hardware isolation: each accepted guarantee is conditional on the selected instance's proved interpretation and stated environment assumptions.

| Checked library property | Defects it can exclude within its semantics | What remains outside that result |
| --- | --- | --- |
| Initialization and bounds refinement | Reads of uninitialized cells, out-of-range accesses, incorrectly initialized output contents | Secret scrubbing, stale DMA access, and properties not preserved to the final artifact |
| Ownership plus borrow restoration | Conflicting mutation, use after the modeled loan ends, accidental changes to framed storage | Hardware capability revocation, unsafe/FFI primitives without proofs, general concurrent interference |
| Functional codec contract | Wrong interpretation, omitted validation required by the descriptor, inconsistent consumed length | A wrong descriptor, unspecified rejection policy, denial of service without termination/resource proofs |
| Indexed protocol refinement | Illegal modeled transitions, duplicated exclusive permission, lost ownership on specified failure paths | Global liveness, crash recovery, cancellation, or freshness unless those behaviors are included |
| Semantically interpreted usage budget | Excess modeled calls or events, or incorrect exact-use accounting | WCET, allocation volume, physical energy, or call ordering without their separate models/contracts |
| Information-flow proof with explicit observations | Prohibited modeled explicit and implicit flows | Final-artifact timing/leakage, physical side channels, and declassification rules not included in the proof |
| Subject binding and assumption auditing | Stale evidence and unaccepted assumptions when the existing checker enforces the bindings | Specification adequacy, a mismatched source interpretation, or compiler/hardware correctness by metadata alone |

For a single-use publication permission, for example, an ownership theorem can rule out publishing twice through the verified API.
Proving that publication eventually occurs also needs termination/progress and failure semantics; move-only syntax cannot establish it.
A grade that merely renames an existing permission contributes no stronger guarantee, although it may improve error locality.
Shared libraries also concentrate risk: a weak contract or wrong representation can affect every client, so independent contract review and negative specification tests remain essential even when the implementation theorem checks.
Audit generic laws for vacuous premises and instance representations for satisfiable entry states; a sound implication with an impossible precondition is not a usable component.
For deployment, the stronger VerifiedOS profile remains mandatory even if the same framework serves less demanding projects elsewhere.

## Decision

Adopt **target-parametric, Rocq-native proof-carrying components** as the unit of experimentation, with a rich specification world and a tightly represented executable world.
Prove one concrete CHERI instance first. Hide its architecture from ordinary component contracts while retaining its exact representation, compilation, and security obligations in the instance and artifact evidence.
Use Idris 2 for state-indexed APIs and erasure, Verus for erased ownership evidence and proof ergonomics, Creusot/Prusti for borrow-end contracts, RefinedRust for foundational ownership, and Live Verification/Rupicola for construction and proof reuse.
Compare DeepSEA and Sepref before authoring representation generators or refinement combinators, and the Rocq memory-model-parametric symbolic-execution work and Morello-Cerise before specifying the capability instance's laws. Use the verified Dafny/CakeML subset and the Bedrock2/Kami example to assess the strength of a composed result, with their source and machine boundaries explicit.
Read AddressC and SuSLik before inventing an imperative proof surface or certifying builder; compare Velvet/Loom/LeetProof for integrated interaction and specification testing. Reuse Perennial's relevant recovery reasoning within the journal work already selected, and use CFML/Sisyphus and FP2 as focused maintenance and resource-design references rather than new deployment routes.
Use Granule, Gerty, and GraD to distinguish what a resource annotation means and what theorem justifies it, not as ready-made CHERI compilation paths.
Keep F*/Pulse and Lean's program-verification tooling as active comparisons, and CakeML/Pancake as references for honest end-to-end compiler claims.

Prioritize the small proof and evidence diagnostics, which are the one deliverable here whose stated starting point already holds, and hold the bounded-component pilot behind the semantics it abstracts rather than in front of it.
Take scoped restoration and the existing descriptor and protocol clients when they demonstrate reuse.
Test generic theorem dependencies, missing-law rejection, required-profile enforcement, and selective invalidation as part of that pilot rather than building a universal target layer first.
Add a fixed-domain resource library only for a named obligation that existing combinators do not already handle well.
Defer general grading, a new language server, and a frontend until measured authoring problems justify them; a fresh optimizing compiler is not part of this library proposal.
This ordering can deliver useful source proofs without waiting for a universal language, while leaving native admission dependent on the existing compiler and artifact work.
Keep syntax, automation, and editor iteration above explicit semantic interfaces, and reserve any non-CHERI portability experiment for a separately scoped reuse project.

The desired golden artifact is achievable in principle as a binary proved against an independently reviewed model. Q20 tests one authoring surface and promotes its exact optimized output only when the existing evidence chain is available and the comparison succeeds.
This strategy's immediate contribution is to make that proof path easier to author and reuse, without claiming that a new language has already closed the project's compiler, source-correspondence, timing, or hardware obligations.
The reusable result is a framework for producing such artifacts under explicit target interpretations, not one binary, memory model, or security promise that applies to every architecture.

No upstream code is incorporated by this proposal.
Any implementation milestone that incorporates a dependency first reads that upstream's actual license and records the chosen artifact and its terms under the repository's [third-party discipline](../THIRD-PARTY.md).

## Expected Developer Experience

The intended experience is to write a component and the promises it must keep together, receive useful explanations when a change breaks a promise, and ship the optimized executable that those promises cover. Most callers would use ordinary records, collections and operations; specialists would build the deeper proofs into reusable libraries. There would be less need to keep a prototype and a separately rewritten production implementation synchronized for the supported components.

Productivity should benefit most from repeated work: parsers, bounded buffers, protocol steps and changes to already verified libraries. The first examples pay the cost of specifying behavior and building the reusable proofs. Difficult algorithms and concurrency can still need substantial expert work. A familiar syntax alone cannot supply C#'s ecosystem or make arbitrary verification automatic.

Maintenance can improve because contracts describe what callers may rely on, and the build detects when an implementation change breaks that agreement. Internal changes can reuse client proofs when their public promises stay the same. Incorrect shared contracts remain a common failure source, so independent examples and review remain part of the workflow.

Performance can approach carefully written native systems code where the compiler can erase proofs, specialize abstractions and use efficient in-place representations. Proof checking happens during development and admission; intended erased proofs need no runtime execution. Runtime checks, representation costs and security mechanisms still cost what the measured binary says they cost. Rust-equivalent throughput and predictable resource bounds are separate results to demonstrate, and neither is established by this proposal today.
