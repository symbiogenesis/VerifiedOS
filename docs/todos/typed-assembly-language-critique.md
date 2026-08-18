# Critique of the Typed Assembly Language Specification

## Executive assessment

The design makes sense as an architectural proposal. Its central idea is clear and strong: final machine code carries a typing derivation; a small checker validates local constraints; machine-enforced facts are cited; deeper properties remain release-time proofs. The separation between producer effort and consumer checking is especially coherent.

The document is not yet a complete language specification, however. It is currently a high-level design contract and rationale. Several normative statements disagree about routing granularity, guarantee scope, and how inserted checks fit the three-move checker. Those issues should be resolved before the grammar, checker, or soundness theorem is implemented, because each resolution changes the theorem that must be proved.

This critique compares the document with the [requirements register](../requirements-register.md), the [VerifiedOS specification](../spec.md), the [crown-jewel inventory](../crown-jewels.md), and the [prior-art survey](../inspirations.md).

## What already works well

* The certificate-consumption boundary is crisp: producers may perform arbitrary analysis, while the consumer validates producer-supplied join states without finding a fixpoint.
* The frozen-theory argument ties checker size to the decisions the checker must make, rather than treating line count as an independent target.
* The profile abstraction correctly separates machine-dependent facts from the language core.
* The document states important CHERI qualifications instead of treating bounds, monotonicity, sealing, and W^X as unconditional.
* The split between type-level obligations and deep proof obligations is principled and consistent with the wider VerifiedOS architecture.
* The status section is unusually candid about unbuilt components and first-of-kind work.

## Confusing, contradictory, or underspecified points

### 1. The unit of routing is inconsistent

Section 2 says that every obligation has exactly one route. Section 4 counts memory safety as one obligation while explicitly combining spatial and temporal safety; it likewise counts control-flow integrity once while combining its run-time and callee-set halves. Yet `cheri-rv64` routes the halves differently: spatial safety is cited while temporal safety is attributed, and run-time CFI is cited while the callee set is attributed.

This is a direct normative mismatch. The likely intended unit is an atomic obligation facet, not one of the eleven menu rows, but adopting that interpretation changes the route rule and should be explicit.

### 2. The `cheri-rv64` guarantee is not wholly open-world

The document says the guarantee is open-world under `cheri-rv64`. Only cited invariants have that scope. Temporal safety, exclusive access, typed control flow, initialization, taint, cost, and the other attributed properties still depend on well-typed code and controlled interfaces. Arbitrary co-resident code can invalidate at least some of them if it shares relevant authority.

The open-world/closed-world distinction should therefore be stated per routed facet, or as a mixed guarantee for `cheri-rv64`, rather than as one profile-wide classification.

### 3. Inserted checks do not fit the “exactly three moves” account

The route table includes `Inserted`, but the checker section lists only citation, attribute evaluation, and deletion. An inserted bounds check appears to require an attribute that proves placement and dominance, followed by a run-time operation. That may fit move II, but the specification never says so. Section 6 separately assigns inserted checks a domination argument, which further blurs whether that argument belongs to the profile proof, the derivation, or the checker.

The normative model should say whether `Inserted` is a route implemented through move II, and specify the exact certificate evidence required.

### 4. The cited-route cost row contradicts its own description

The original table says a cited route has no check-time cost, while the same row requires the checker to inspect the citation. The intended claim appears to be “no static enforcement beyond citation validation” or “no additional run-time software check,” not literally zero admission work.

### 5. The document calls itself a language specification but does not yet specify a language

The document fixes a design envelope but does not define:

* concrete or abstract syntax;
* the type grammar and well-formedness judgments;
* instruction typing rules;
* control-flow-graph and join-state encoding;
* certificate format and canonicalization;
* decoder-to-instruction binding;
* profile schema;
* checker acceptance and rejection rules;
* the exact soundness theorem;
* malformed-input behavior and resource bounds.

This matters because the [crown-jewel inventory](../crown-jewels.md) treats the TAL soundness theorem as depending on the ISA profile and Sail semantics, while the [requirements register](../requirements-register.md) expects this document to own the theory, menu, profile rule, and soundness statement. A prose architecture cannot yet serve as the complete premise of that theorem.

### 6. “One syntax-directed pass” is stronger than the rest of the document supports

The checker includes a derivation reader, CFG attribute evaluation, and an image scan. Cost analysis also consumes loop bounds, recursion bounds, and path facts. It is unclear whether “one pass” means one traversal of the certificate, one traversal per attribute, one traversal of each artifact, or linear total complexity. A cyclic CFG with supplied join states avoids fixpoint discovery, but it does not automatically establish a single physical pass or bounded memory.

Specify the complexity claim directly: for example, linear in decoded instructions plus certificate size, with bounded work per edge and explicit bounds on set operations.

### 7. The amendment rule and current attributes do not obviously match

The rule requires a finite semilattice or monoid domain. Callee sets are finite per image but may have image-dependent size; linear contexts can grow with program state; literal naturals are bounded-width but not described as a fixed attribute domain; and cost uses max-plus arithmetic rather than a plainly finite semilattice unless saturation or rejection is specified.

The rule should distinguish a finite carrier fixed by the profile from a finitely represented, certificate-bounded carrier whose operations have explicit complexity limits.

### 8. WCET checking relies on proof-like inputs whose status is unclear

The cost rule depends on loop and recursion bounds and “path facts that exclude infeasible worst cases.” Elsewhere, non-structural loop bounds are Coq obligations against source. The TAL document does not state how those discharged facts reach the final-code derivation, how the checker authenticates them without becoming a proof checker, or whether infeasible-path facts are optional tightening evidence prohibited by the no-tightening rule.

A normative design should either limit the TAL to conservative structural bounds or define an explicit interface from release-time proofs to closed certificate constants.

### 9. The ambient-state check is described too narrowly

Inspecting static data for a set capability tag can establish that the image embeds no tagged authority. It does not by itself establish the broader property named in the register: no module-level mutable state, lazy statics, thread-locals, hidden singletons, or writable object reachable except through handed authority. Untagged mutable globals are also ambient state.

The image-level predicate needs a complete semantic statement, not only the tagged-data test.

### 10. Producer option 3 is incomplete

A source-level proof elaborated into a reviewed source semantics does not by itself create a final-machine-code TAL derivation. The document needs to state that the producer must also transport the proved fact to final code or emit a derivation whose local premises the checker validates. Otherwise option 3 bypasses the artifact-level admission rule.

### 11. The “trusted replayer” wording conflicts with revalidation

If the on-device checker fully revalidates the reconstructed derivation, the replayer need not be trusted for safety; it is evidence-producing machinery. Calling it trusted enlarges the trusted base unnecessarily and conflicts with the artifact-not-pedigree principle.

### 12. Binary identity and certificate binding are missing

The document says it checks final machine code but does not specify how the derivation binds to exact bytes, decoder version, profile version, relocation state, image layout, or entry-point set. This is the seam at which annotated assembly can silently differ from installed bytes.

### 13. Profile assumptions mix theorems and environmental premises

The profile includes execution-mode, loader, privilege, initial-distribution, and memory-permission assumptions, then says the soundness instantiation discharges rather than assumes them. Some can be theorems of an initialization model; others may remain premises supplied by the consumer. The exact assumption ledger should be explicit.

### 14. The normative surface and rationale are interleaved

Sections 9 and 10 contain valuable research context, but they dominate the document and include time-sensitive empirical claims. That makes it harder to identify the actual language contract and creates unnecessary amendment pressure when literature status changes.

Move prior art and artifact-landscape material to [inspirations.md](../inspirations.md), leaving stable normative requirements and a short rationale here.

## Redundancy and suboptimal presentation

* The phrases “category claim,” “not a proof checker,” “frozen theory,” “artifact not pedigree,” and “factoring relocates rather than reduces work” recur more often than needed.
* Sections 1, 3, 5, 9, and 10 repeatedly justify the checker-size claim. One normative complexity statement and one rationale section would be clearer.
* The profile descriptions should be a complete obligation-by-route matrix. Prose makes omissions and mixed routes difficult to detect.
* The eleven obligations should remain an explicit numbered list. Their current prose enumeration is easy to miscount.
* Literature references need a bibliography with stable identifiers. Parenthetical author/venue/year strings are not enough for auditability.
* Volatile claims such as “maintained,” “current state,” “planetary-scale,” and project activity belong in a dated evidence note, not the normative specification.
* “Safe,” “memory safety,” “control-flow integrity,” “constant-time,” “local,” “structured,” and “open-world” require definitions. Their intuitive meanings are not precise enough for a soundness theorem.

## Proposed normative improvements

The following changes intentionally alter or complete the normative design; they belong in a future amendment, not in the wording-only revision.

### 1. Route atomic facets, not menu rows

Define atomic facets such as `memory.spatial`, `memory.temporal`, `cfi.entry`, and `cfi.callee-set`. Retain the eleven menu rows as user-facing groupings, but require exactly one route per atomic facet.

### 2. Replace prose profile descriptions with a complete matrix

For every facet and profile, record:

* route;
* checker move;
* certificate evidence;
* machine theorem or inserted instruction pattern;
* guarantee scope;
* soundness lemma;
* failure behavior.

Generate the narrative profile descriptions from that matrix.

### 3. Make guarantee scope route-specific

Specify that cited facets may be open-world subject to their machine premises, while attributed and inserted facets are closed under an explicit linking or address-space assumption. State the composed profile guarantee as mixed-scope rather than globally open- or closed-world.

### 4. Define inserted checks as move-II evidence

Require the derivation to identify each guarded operation, the inserted check, and a certificate-supplied dominance fact validated locally. Define the run-time failure state and include it in the soundness theorem.

### 5. Publish the formal language core

Add normative artifacts for:

* type and certificate grammar;
* decoded instruction and CFG representation;
* typing and transfer rules;
* join validation;
* profile schema;
* canonical serialization;
* checker algorithm;
* resource limits;
* acceptance theorem;
* malformed-certificate behavior.

The prose document should become the readable index to those artifacts.

### 6. State an exact checker complexity contract

Replace “one pass” and line-count implications with a checkable bound, such as linear work in image plus certificate size, bounded memory per block, no iteration to convergence, and explicit complexity for callee-set and context operations. Keep line count as a secondary audit budget.

### 7. Strengthen the amendment criterion

Permit finitely represented, certificate-bounded domains only when their representation size and every operation have a stated bound. Require an amendment to provide termination, complexity, soundness, and negative tests, not only algebraic shape and locality.

### 8. Define the WCET evidence boundary

Choose one of two designs:

* conservative structural WCET only, with no infeasible-path facts; or
* release-time proofs that produce signed closed constants and path certificates in a small, separately defined certificate language.

Do not leave “path facts” as an unspecified input to a non-proof checker.

### 9. Define ambient-state absence semantically

Require that every mutable root and every initial capability be enumerated in the manifest or derivation, then prove that all mutable reachability begins at those roots. Keep the static-tag scan as one implementation check, not the whole property.

### 10. Bind certificates to installed bytes

Hash or otherwise commit the certificate to the exact decoded image, decoder/profile versions, layout, entry points, and immutable tables. State admission over the post-link, post-layout, post-encoding installed artifact.

### 11. Make the assumption ledger part of each profile

Classify every dependency as a proved machine theorem, proved loader/initialization theorem, consumer premise, silicon-correspondence assumption, or operational assumption. The soundness theorem should expose the exact ledger it consumes.

### 12. Add conformance and adversarial test suites

Provide positive and negative examples for every rule, including malformed joins, hidden capability data, inexact bounds, privileged transitions, stale grants, callee-set under-declaration, missing dominance, secret-dependent addresses, cost overflow, and decoder ambiguity.

### 13. Give this document atomic requirement IDs

The wider project treats atomic, testable requirements as the audited normative form. Apply the same discipline here: stable IDs, acceptance criteria, and trace links to formal rules. That will prevent the language prose from becoming a second requirements register that can drift.

## Recommended amendment order

1. Resolve routing granularity and guarantee scope.
2. Define how inserted checks map to the three moves.
3. Freeze the profile matrix and assumption ledger.
4. Specify certificate-to-byte binding and the formal checker input.
5. State the exact checker algorithm and complexity bound.
6. Define the typing rules and soundness theorem.
7. Add conformance tests and only then begin implementation.
