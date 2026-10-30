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

## Validation handoff

Review the integrated diff for preserved statements, definitions, assumptions
and non-vacuity evidence. Record focused compilation scope and verdicts; they
are not hosted acceptance. Run the ordinary source and derived-artifact checks
after the inputs settle. Use [fanout](../../../tools/fanout.md#usage) to integrate,
publish only main, require Host CI on Windows and Ubuntu, dispatch every Guest CI
lane with `cold: true`, and retire only the batch-owned worktrees. Record revision
and run identifiers and finish without waiting for Guest CI. Its pending verdict
is not a passing proof result.
