# Native Sail support module census

Q35q owns this prerequisite to its [native declaration inventory](../../../tools/opam/sail-compatibility.md#native-support-inventory-prerequisite). The [retained diagnosis](../q35q-native-inventory.md) identifies module-type fields that are not global constants and a sealed concrete functor result. Implementation starts after this contract is committed. Its scope is the exact selected support population in [the immutable recipe](../../../tools/opam/sail-support-qualification.json), at the existing locked prover, dependencies, strict flags and source patches.

## Census and provenance

Retain the complete native `Print Module` reading for each selected module and recursively read every nested module, module type and functor that reading names. Retain `Print Module Type` readings for signatures. Every native field receives one classification: an owned instantiated kernel declaration, an abstract interface obligation, or a proven abbreviation/alias. Every `Search` row is accounted for by native resolution and the corresponding field; source spelling alone establishes neither ownership nor completeness. Unsupported, incomplete or ambiguous readings refuse the census.

Module-type fields and the formal and result fields of unapplied functors remain explicit interface obligations. They are not ordinary global constants and must not be passed to `Print Assumptions` as though they were. Their complete names, types, enclosing signatures and functor parameters remain in the census. This classification permits no additional global assumption.

For concrete modules, including sealed functor results, use native canonical resolution to connect every exported field to its actual instantiated implementation. Audit that resolved declaration's exact assumptions. A printed signature or functor application without the implementation connection supplies no assumption verdict. Aliases retain both the printed spelling and native target; two spellings of one declaration need explicit alias provenance rather than duplicate acceptance. Foreign, missing, duplicate or ambiguous declarations refuse. An empty or alias-only module needs its complete native body and abbreviation/alias readings; an empty `Search` result alone is insufficient.

## Acceptance and controls

The adapter passes only when the complete selected population and every printed row are accounted for, every owned instantiated declaration has its exact assumption audit, and native input identities remain unchanged. Keep the common inventory guard unchanged. The support-specific adapter supplies only independently established canonical declarations to that guard and preserves all original rows and provenance in its evidence. No prefix insertion, discarded row or unexplained empty result may turn a refusal into success.

Positive controls cover a signature-only module, an unapplied functor, a sealed concrete functor result and a proven empty/alias-only module. Refusal controls cover an omitted nested field, a signature field treated as a global constant, a missing concrete implementation connection, a foreign declaration, ambiguous resolution, a duplicate, an unsupported native module form and an unproved empty module. Controls run at the locked prover where native classification is claimed; Python fixtures alone qualify no native census.

Q35q still requires its complete real hosted census, exact assumption audit and recursive kernel check. Q35n's independent cold snapshot export/import campaign and Q35b's canonical consumer acceptance retain their separate predicates. This contract accepts no support carriage, proof, changed source semantics or project-lock update.

## Bounded execution and estimate

Run at most three candidate checks or twenty active minutes, whichever comes first. At the first unsupported native shape, retain the exact reading and refusal, stop candidate work and return the missing act to the owner. Focused local checks are permitted; complete gates and benchmarks remain on GitHub Actions. Native processes use an absolute temporary working directory, and compiled objects remain in the assigned native lane.

The census extension adds 6 h, range 3–9, to Q35q's existing allowance: native grammar/classification 1–3 h, canonical implementation connections 1–3 h, and controls/evidence 1–3 h. The combined item is 10 h, range 5–15. This is a planning estimate for the commissioned scope; unattended hosted runtime and a further unsupported form are excluded. A retained refusal does not close Q35q.
