# Deployment threat decision for memory remanence

This contract makes Q7's early deployment choice reviewable. It is governed by R-15-199, R-15-200, R-17-058f and R-17-059a in the [requirements register](../requirements-register.md), and consumes the [topology comparison](memory-topology-comparison.md). It supplies no physical evidence. The current design accepts the uncontrolled-power-loss residual; it does not qualify deployments that require that residual to be closed.

## 1. The decision and its forfeits

The product owner records a deployment identity, which data remains sensitive after abrupt loss, the physical access and cooling capability of the attacker, retained/back-powered supplies, the required confidentiality window and the recovery methods in scope. The decision is over those declared conditions, not the word mobile or the medium's name.

| Arm | Admission condition | Forfeit |
| --- | --- | --- |
| Accept the current residual | The deployment's owner explicitly accepts recovery of live sensitive bulk and any separately unqualified first-class/key state after uncontrolled loss | No claim of powered-off confidentiality for that state or compliance with a deployment requiring it; completed mode-exit discharge does not cover a cut during execution |
| Require a protected window | A concrete protection construction and the complete copy/lifetime record demonstrate the declared window under its stated attacker and power conditions | Additional capacity, circuitry, verification, metadata, power and latency must be priced and any conflicting register clauses amended before implementation |
| Decline that deployment | The required window cannot be supported by the available construction/evidence | The product does not serve that deployment; this is scope control, not hardening |

No user or deployment-specific requirement was supplied to this fan-out, so it cannot select the protected-window arm on behalf of an unnamed deployment. The current product claim remains the register's residual arm; a deployment requiring closure is refused until its evidence exists. This records the boundary rather than assuming an ephemeral key disappears first.

## 2. Retention is not recoverability

An operational minimum retention time bounds how long the implementation can rely on correctly reading written state under its declared operation. Its lower bound supplies the refresh deadline. A confidentiality-relevant maximum recoverability window bounds how long the stated adversary can still extract sensitive information after a named power/erase event, with cold, retained-power, ageing and measurement uncertainty included. Neither bound follows from the other. A last unsuccessful normal read is not an upper bound against a stronger recovery method, and a right-censored experiment supplies no maximum.

R-15-247c prohibits a sanitization or containment guarantee resting on decay. R-15-247q's confirmed mode-exit construction narrows which domains remain live at sudden loss but does not execute when the attacker simply removes power. Invalidating tags removes authority and leaves confidentiality a separate question. The [R5 protocol](macro-qualification-protocol.md) characterizes second-class exposure; [R5a's protocol](sensitive-state-lifetime-protocol.md) separately inventories first-class, register and dedicated key-storage copies, including expanded keys and derivation state.

## 3. Constructions if a window is required

### Protected local storage

Keep sensitive working state only in an identified local storage construction whose abrupt-loss and erase behavior qualifies for the declared window. Public weights may occupy the larger unprotected class. Admission must include all temporary, spill, cache, expanded-key and derivation copies in the protected budget and its destruction proof/evidence. The phrase local or SRAM is insufficient; no qualified construction is supplied here.

This is the protection-construction arm that Q7 says changes R-15-199 and requires a register act before introducing memory-path protection. It is not permission to insert cryptography or to claim a protected storage class today. State exactly which path would change and its key custody, integrity and freshness obligations in that act.

### Reduced retained sensitive bulk

Reduce the admitted sensitive working set, context, concurrency or durable-resume scope until a separately qualified construction can cover every remaining sensitive copy. State which features and capacities are lost and re-evaluate the simultaneous release floor. Zero sensitive bulk in the second class does not qualify first-class state by implication. This arm reduces exposure through product scope and is not a new hardware protection claim.

### Encrypted bulk with independently qualified key destruction

State a standard authenticated construction, actual key custodian, every usable key/expanded-key/derivation copy, key establishment and lifetime, and the destruction event under abrupt loss. Qualification must support the required key-versus-data ordering for the declared adversary; same-die placement and nominal SRAM volatility establish neither equal nor unequal lifetime. R-17-059a's powered-die analysis cannot decide the power-off case.

If the memory interface is adversary-controlled, authenticate data with freshness, address and generation binding and atomic data/metadata updates. State recovery after torn writes and rollback rather than relying on encryption alone. This arm changes R-15-199 and any affected integrity-tree exclusion and requires its own priced implementation and refinement obligations. Existing verified primitives or a masked AES block do not constitute a verified memory-protection subsystem.

For each arm, the result record carries capacity and metadata overhead, masked cryptographic throughput where used, local and external traffic, boot/recovery behavior, abrupt-loss behavior and transition latency. Values are owed to the actual construction and measurements, never borrowed from a host benchmark. Access-pattern, live-probe, power and denial-of-service residuals stay separately named even if ciphertext confidentiality is supported.

## 4. Acceptance and ownership

The early contract is accepted by a Tier A review only if it identifies the decision's input record, the residual/protection/refusal arms and forfeits, separates both lifetime quantities and both power-loss paths, and refuses a protection claim without all-copy evidence. It is falsified by a missing copy class, a tag-clear-as-confidentiality argument, an unsupported key-before-data ordering or a window without an attacker/power/corner scope.

Q7's complete acceptance remains either a concrete protection construction with evidence for its declared window, or a recorded product refusal of deployments needing that property. R5 and R5a own the separate device measurements; M9a owns composition-capacity physical admission. New circuitry, memory cryptography, fabrication and laboratory campaigns require separately priced work and evidence providers. The protocols make the requested measurements concrete and close none of their physical claims.
