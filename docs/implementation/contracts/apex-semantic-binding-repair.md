# Apex semantic transport repair

This bounded repair implements the execution-binding part of
[R-05-161](../../spec.md#r-05-161) within
[R-18-031](../../spec.md#r-18-031). The existing
[Vocabulary](../../../proofs/ApexTheorem.v#Vocabulary) proposition fields remain a
coverage ledger. A conjunction of those fields supplies no execution relation.
The full composed-system proof and concrete field instantiations remain open.
Implementation begins after this contract is committed.

## Interface and acceptance

- Preserve the exact definitions of `T`, `Ax`, `admissible`, and
  `observation_equal_modulo_D`, the nine seam statements, their allowed assumptions,
  and the current physical/model boundary. Capture and compare the native frozen
  reading of `T` where the locked prover is available; source comparison alone
  supplies no native acceptance verdict.
- Define a semantic transport between separately parameterized source and target
  vocabularies. It carries fixed target-to-source input and adversary-context maps,
  an implication from the target assumption ledger to the source ledger, and
  proofs that target-admissible contexts and target-indistinguishable input pairs
  map into the corresponding source relations.
- Carry fixed source-to-target maps for released value, timing and architectural
  observations. For each complete target execution, prove that all three released
  target observations equal the respective mapped source observations. Maps are
  fixed before selecting an input pair. Declassification is applied on each side
  before this comparison; raw value agreement alone is insufficient. The existing
  total-execution vocabulary keeps termination/progress in whichever observation
  its concrete model declares; the transport may not omit that observation.
- Prove that a source theorem `T source` and this transport imply `T target`.
  No transport field may contain `T target` or a renamed equivalent. The source
  theorem remains an independently required property of its executable source
  semantics. Prove that adjacent transports compose, including context, input,
  assumption-ledger and all observation maps.
- Make `composition_meta_lemma` explicitly require the semantic transport and
  source theorem, retaining the substrate, seams and tower as coverage obligations.
  Keep the old ledger-only implication under a clearly named definition and
  retain its existing leaky counterexample. Do not report the generic transport
  theorem as the concrete machine's capstone proof.
- Construct a nontrivial positive source/target pair with public and secret input
  components, distinct trace representations and public-dependent observations;
  prove source security, the transport and target security. Provide closed
  `witness_<Record>` inhabitants for introduced records. Refuting examples cover
  omission of timing and incompatible context, input or declassification relations.
  In particular, the all-True ledger of the existing leaking target cannot acquire
  a transport from any source satisfying `T` under its actual relations.
- Native compilation and assumption printing of changed modules provide focused
  development feedback only. Existing lexical reader controls must remain green;
  they check field/consumer coverage and grant no semantic proof verdict. The
  integrator regenerates affected views and records a cold Guest CI handoff. The
  user owns all hosted execution; no full local proof gate is permitted.

## Bounded workflow

This is an owner-reviewed interface correction rather than a tactic repair of the
old false ledger-only implication. Follow the
[portable proof workflow](../../assurance/proof-assistance.md#bounded-repair-workflow)
with at most twelve candidate/check attempts and thirty active repair minutes.
Keep the checkpoint in a unique system temporary directory, and native compilation
and query outputs in the assigned guest lane. The frozen target is the existing
`T`; do not change its executable dependencies to make the repair pass.
