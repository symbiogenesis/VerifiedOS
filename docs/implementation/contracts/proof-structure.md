# Proof structure maintenance

This contract commissions the proof refactors requested on 2026-10-30. It owns
their interfaces and acceptance predicates; [PLAN.md](../../../PLAN.md#proof-structure-maintenance)
owns their execution state. It introduces no requirement, axiom or security claim.

## Preservation boundary

Retain exported theorem statements and the behavior of executable definitions,
including list ordering, truncation, default values and malformed inputs. Shared
definitions may replace local implementations by convertible aliases or proved
equivalences. New semantic corollaries supplement existing Boolean statements.
Raw values remain available to the existing negative examples. Preserve named
record witnesses, requirement annotations, refusal families and campaign entry
points. Shared modules must have an empty assumption closure under the existing
proof gate. Do not add a package, global hint database or checking exception.

Moving a definition to its owning shared module is an authorized representation
refactor, with its compatibility proved or checked by conversion. It is not a
repair authorized to weaken a frozen theorem. Proof trials follow the portable
[proof assistance workflow](../../assurance/proof-assistance.md#bounded-repair-workflow):
one strategy is reconsidered after three failures and each target has at most
twelve attempts or thirty minutes of active repair. Disposable journals remain
outside the checkout. Focused compilation is debugging evidence; the complete
proof gate runs only on GitHub Actions.

## Deliverables and acceptance

Each numbered slice starts from the committed version of this contract and the
named current sources. Its write boundary is the named proof modules and small
new support modules. Each joins the integrated source review and the hosted
handoff below.

1. **Shared foundation.** Extract compatible prelude collection and Boolean
   helpers used by AdmissionPath, HandlerGraph, EndpointIPC and the crypto
   references. Migrate repeated implementations to shared definitions or local
   compatibility aliases. Retain differing enumeration and fallback policies.
   Check that existing clients still elaborate with their exported types and
   that the shared module uses no additional assumptions.
2. **Semantic checker interfaces.** Give PqArith's polynomial equality a sound
   and complete equality specification and ML-KEM semantic branch corollaries.
   Client reasoning consumes these specifications; the original executable
   checks and branch theorems remain available.
3. **Named conditions.** Replace HandlerGraph's positional extraction, including
   `drop_six_conjuncts`, with named edge conditions and their semantic projections.
   Preserve condition order, composer behavior and dropped-condition campaigns.
4. **Geometry projection.** Factor the geometry-dependent schedule checks through
   a view carrying width, offset, bound and period. Retain SameGeometry and
   existing invariance statements as compatibility interfaces. Derive their
   results from equality of views, including ensemble consumers.
5. **Last-event semantics.** Share the tail-first last-matching-event operation
   behind register, CSR and journal lookups. Supply append and absence laws and
   use them in the clients' replay or frame reasoning. Keep tags, CSR coverage
   and transaction commit conditions in the application-specific projections.
6. **Sequence edits.** Share compatible swap, delete, insert and duplicate
   operations and their universal preservation laws. Migrate existing clients;
   retain each operation's out-of-range policy and order-sensitive refutations.
7. **Scalar lifting.** State scalar cancellation laws separately from their
   equal-length list lifting. Use them for PqArith's scaled butterflies and
   shared AES/Keccak XOR cancellation, preserving unequal-length behavior.
8. **NTT shapes.** Extract balanced-half length and split/reassembly laws from
   PqArith's repeated length and inversion calculations. The recursive inverse
   theorem consumes these laws without strengthening its premises.
9. **Independent updates.** Prove a pointwise law for folds of updates over
   distinct indices, and use it for StaticMemoryService's mapping and XOR
   phases. State frame behavior without functional extensionality.
10. **Dependency order.** Arrange PqArith's general arithmetic, inversion and
    codec laws before concrete examples and alternatives, using support modules
    where that gives an acyclic dependency graph. Preserve existing import paths,
    exported declarations and campaign extraction behavior.

## Further proof interfaces

This tranche commissions the ten remaining improvements selected in the source
review of revision `dfc6812e04b420f3c536e00fbc70590f02b1113d`. Implementation starts
only after this extension is committed. The preservation boundary above applies;
existing executable definitions stay unchanged or definitionally convertible,
and existing theorem declarations remain available with their original types.

1. **B-tree operation cases.** In ExecutableIndex, give leaf and branch
   publication complete success and refusal interfaces, including allocation and
   split cases. Use the interfaces in existing independent invariant proofs;
   do not replace their premises with a stronger bundled invariant.
2. **Named remaining conditions.** In CopyRingService, name the service
   conditions and their projections while preserving the ordered predicate list,
   numeric dropped-condition and spoiling interfaces, including out-of-range
   behavior. In HmacDrbg, replace positional seeding-discipline extraction with
   named projections and transition membership.
3. **Codec composition.** In ModuleFormats, share sequencing and complete-input
   reasoning behind certificate round trips and trailing-byte refusal. Preserve
   every tag, bound, field order, suffix and canonical-encoding theorem.
4. **Complete finite rosters.** Prove universal-check equivalence from an explicit
   enumeration-completeness witness and consume it in EndpointIPC and firmware
   roster proofs. Keep authored enumerations and their refusal evidence intact.
5. **Compositional equality.** Add constructive list, option and pair equality
   specifications using exactly the element laws each direction needs. Derive
   existing comparison lemmas from them without changing comparison functions or
   their exported theorem types.
6. **Support-local probability.** Add finite-support extensionality and
   mass-preserving reindexing laws in ProbingModel. Derive its current global
   interfaces and ArithmeticComposition's membership-restricted counting result
   without adding uniqueness, normalization or probabilistic assumptions.
7. **Crypto permutation laws.** Give SHA rotations and AES row permutations
   general length or inverse-index laws and derive the existing fixed-arity
   declarations as instances. Raw lists, defaults and malformed-input behavior
   remain part of the executable reference.
8. **Ordered admission verdicts.** Give AdmissionPath's certificate checker one
   semantic interface for acceptance and exact refusal rule and site, with earlier
   checks successful in each later-refusal case. Derive existing refusal,
   soundness and completeness results without changing first-failure order.
9. **Remaining shared laws.** Move repeated collection and natural-arithmetic
   laws into their small shared owner and keep client theorem names as wrappers.
   Focus on all-of/map, Boolean membership, append/count, addition, order and
   maximum laws. Retain the prelude-only boundary where a client requires it.
10. **Named service updates.** Replace CopyRingService's positional setters with
    compatible named-field definitions where convertible, and add projection and
    pointwise hit/miss frame laws. Keep function-valued fields pointwise, with no
    functional-extensionality assumption or new package.

Each slice must migrate actual clients rather than add unused abstractions.
Review old exported declaration types, definitions, assumptions and refusal
families against the base. Use the hosted reading comparison with that base;
new helper declarations are expected differences and do not excuse a changed
existing theorem meaning. Frozen readings unavailable locally remain explicitly
outstanding until the hosted comparison is reviewed. The source review and cold
proof gate must establish preservation; a lexical comparison alone cannot.

Runtime algorithms and inputs remain fixed. Proof compilation and kernel-check
costs are measured only on hosted runners using the proof gate's timing evidence;
do not infer a speedup from shorter scripts. A measured regression requires
investigation and correction before claiming performance acceptance. Pending
hosted measurements remain pending evidence under the no-wait Guest CI handoff.

## Validation handoff

Focused native comparison tools and extraction campaigns that stage one of the
refactored modules must also stage and compile its local dependency closure in
dependency order. This includes composer, supervisor, copy-service, Wasm oracle
and crypto campaign consumers. A shared staging helper owns that traversal;
comparison receipts bind every staged proof input and reject changed source or
staged bytes. Existing result fields, toolchain choices and comparison scopes
remain compatible. Focused fixture tests cover dependency order, shared inputs,
cycles, unknown entry points and changed inputs without running a prover. Source
inventories include the staging helper wherever their producer imports it.

Review the integrated diff for preserved statements, definitions, assumptions
and non-vacuity evidence. Record focused compilation scope and verdicts; they
are not hosted acceptance. Run the ordinary source and derived-artifact checks
after the inputs settle. Use [fanout](../../../tools/fanout.md#usage) to integrate,
publish only main, require Host CI on Windows and Ubuntu, dispatch every Guest CI
lane with `cold: true`, and retire only the batch-owned worktrees. Record revision
and run identifiers and finish without waiting for Guest CI. Its pending verdict
is not a passing proof result.
