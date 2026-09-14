# The security policy model

This is the authored model and review candidate for crown-jewel inventory row 2 (R-08-028, R-17-012). Its Gallina artifact is [SecurityPolicyModel.v](../../proofs/SecurityPolicyModel.v). The [requirements register](../requirements-register.md) remains normative: a disagreement with it is a defect in this specification. The [crown-jewel inventory](crown-jewels.md) owns review status.

The artifact constructs the policy interfaces of [ApexTheorem.v](../../proofs/ApexTheorem.v), proves properties of reference examples, and rejects counterexamples. It does not prove the kernel, compiler, composed image, consent implementation or fabricated machine secure. R-08-022's fresh non-interference proof and `CJ-SECOMP`'s robust compiler preservation remain separate work.

## 1. Composition and labels

A `PolicyModel` carries a finite level count, a Boolean flow order, a compartment count, compartment clearances and trusted membership, an observation-site count, separate content and arrival labels, drive authority, manifest channels and consent-site membership. These fields are composition inputs. R-08-021 and R-08-024 require their eventual derivation from the admitted capability graph; this file does not implement that derivation.

`wellformed` decides the following conditions by enumerating the supplied finite counts:

- The level set is nonempty; the order is reflexive, transitive and antisymmetric.
- Every pair has a least upper bound and a greatest lower bound. A partial order without these bounds is refused.
- Every carried compartment's clearance and every checked site's two labels belong to the level set.
- Only trusted compartments drive consent sites.

The first conditions implement R-08-024's lattice, the label bounds implement R-08-021's checked labelling, and the last condition represents the consent-path ownership required by R-08-035 and R-08-036. The check is not a proof that a physical trusted path enforces that ownership.

A domain is a predicate over compartment indices. `apex_vocabulary.graph_permits` admits every subset of the carried indices. `ApexTheorem.admissible` separately excludes trusted members, so the permitted domain includes a single victim compartment as required by R-01-002 and R-05-156b.

The label and input functions are total on natural indices. Well-formedness checks only the finite declared region, while the observation relation covers every index. Composition refinement must connect the declared region and these total functions to the actual device events and objects; no claim that the Boolean check validates an infinite tail is made.

## 2. Inputs and observations

An ordinary external observation site carries both content and a cycle-level arrival instant. R-05-156a requires both because T treats execution as a function of whole-system input, including device events. Site indexing must eventually represent each external occurrence, including repeated arrivals; the present artifact supplies the carrier rather than a device-trace translation.

`may_read` permits content when the flow order permits its label to reach the compartment clearance, or a manifest channel names that site and compartment. `may_time` permits arrival timing only through the arrival label. A domain may read or time a site when one member may do so.

`indistinguishable` equates the content of every site the domain may read and the arrival instant of every site it may time. It places no equality requirement on other sites. Its equivalence laws are proved. Drive authority is a separate relation: the artifact exhibits input pairs showing that agreement on controlled inputs and agreement on observable inputs are incomparable. These definitions and the admissible singleton victim discharge the two model provisos of R-05-156b for this instance, not an implementation proof of T.

`arrival_quantified_out` decides whether every carried compartment may time a site. For any nonempty carried domain, such an arrival is equated across its related inputs and is outside that instance of T's protection against variation. `arrival_inside_T` negates that aggregate predicate: it means some carried compartment lacks that permission, not that every adversary set is protected for that site. The actual per-domain decision is `set_times`. The empty domain observes nothing.

`SystemInput` also carries typed authenticated-consent evidence and trusted lifecycle snapshots. These are abstract trusted inputs used by the powerbox contract. They are not equated by the ordinary content/arrival indistinguishability clause. Connecting these typed inputs to external stimuli and deciding any observations of them is a trace-refinement obligation; their omission is not an assertion that their contents are public. The example executions do not return them as observations.

`SystemTrace` records received values, read instants, slot instants and widths, a progress measure, termination, fault class and restart count. Its apex observations are predicate-valued views restricted to domain members. The value view contains every received site, including an unauthorized read; masking such a read by `may_read` would conceal the violation. Timing contains the slot instant, progress, slot width, termination bit and per-site read instants. The architectural view is the pair of fault class and restart count.

R-08-027a requires termination and progress, R-08-027b requires schedule-controlled observable progress, and R-08-027c also names exceptions and restarts. The artifact carries all these snapshot observations and separately rejects leaks through termination and restart. Refinement must still bind the snapshot cuts to complete execution histories and actual scheduler, exception and restart transitions. The presence of fields does not establish those mappings.

## 3. Non-interference target

`explicit_flow_target m x` conjoins three named propositions:

| Target | Required agreement across indistinguishable inputs |
| --- | --- |
| `flow_noninterference` | Every received value and read instant of every domain member, with no permission precondition on the output |
| `progress_noninterference` | Each member's slot instant, progress measure, slot width and termination |
| `fault_noninterference` | Each member's fault class and restart count |

The reference `confining` execution returns only permitted input content and arrival timing, a fixed slot, progress computed from visible inputs, fixed slot width and termination, and fixed fault and restart observations. It satisfies this target. Separate executions leak through value, arrival, progress, fault class, termination or restart and are refused. These are specification witnesses under R-05-165 and R-05-166.

The progress witness does not satisfy R-08-027b's stronger requirement that observable progress be determined by the schedule alone. The artifact's theorem is equality under policy-indistinguishable inputs. Binding that target to the schedule-only property and to the separate timing-isolation proof of R-08-027 remains open.

## 4. Consent and exact release

R-08-029 identifies compose-time channels and powerbox grants as the two forms of declassification. A manifest channel changes the base input relation: the artifact demonstrates that a pair related before the channel is added is separated afterward. Runtime grants instead enter T's release quotient.

A `Grant` names a grantee, exactly one object/site, its authenticated witness site, issue instant, scope and ceiling. A `Release` contains candidate grants, trusted lifecycle snapshots and the instant at which they are checked. A candidate grants authority through the quotient only when `licensed` finds the exact grantee/object pair and `live` accepts its scope.

`witnessed m i rel` checks every candidate against a typed act at its named consent site: the act must match the grantee, object, witness site, issue instant, scope and ceiling, and the release's relevant lifecycle state must equal the input snapshot. A trusted site name alone does not witness anything. The artifact rejects both an absent act and an object substituted after consent (R-06-017, R-08-036).

These typed acts abstract authenticated live consent and authenticated recorded consent. Producing them from the trusted path, proving record freshness, deriving physical CHERI bounds and rights, and proving that the powerbox holds the authority it attenuates are implementation obligations. A natural-number object identity in this model is not a capability representation or a proof of byte bounds.

`delimited` requires every released pair to have a grant naming that exact recipient and object. `scoped` additionally requires the same grant to be live at the release instant. `licensed` satisfies both propositions. A rule releasing every object at the named object's level is rejected by `delimited`; a rule ignoring the scope is rejected by `scoped`. This distinguishes the R-08-026 and R-17-012 bound from a general high-to-low channel.

## 5. Temporal scope and freshness

`GrantState` is a trusted snapshot, keyed by witness-site index. The live check first requires that the act has been issued, remains unrevoked and has been requested. Its scope then selects the following condition:

| Scope | Additional live condition | Owner |
| --- | --- | --- |
| `OneShot` | Unconsumed and no later than its ceiling | R-08-037 |
| `WhileActive` | No later than its trusted ceiling | R-08-038, R-08-040 |
| `Persistent` | Fresh record, unlocked profile and compatible record | R-08-025, R-08-037b, R-08-037d, R-08-037e, R-08-037g |
| `EmergencyCall` | The call remains active | R-08-040's R-12-052 exception |

Issued and ceiling instants are inclusive in the reference cycle model. A composition must map these instants to the real expiry transition consistently. The emergency branch is a modelling carrier for the single registered exception; admission must prove that only the emergency-call microphone receives it.

The unrevoked input summarizes revoke-only focus loss, unconditional cuts, retraction and teardown. The unconsumed input summarizes the single mediated use. The persistent freshness input is the explicit additional premise in R-08-025, not ordinary replayable consent content. The implementation must prove these snapshots faithful to the existing revocation, consent store and request discipline; this artifact creates no permission subsystem.

The reference examples reject a used one-shot grant, a stale persistent record, a revoked lease, an ended emergency call and a lease beyond its ceiling. They also accept live examples and both boundaries of leases and one-shot grants. They do not prove the underlying lifecycle transition systems, irreversibility of revocation, package/rights binding or physical cutoff behavior. Witness-site indices must identify distinct live act instances when multiple grants coexist; that allocation and generation binding is another refinement obligation.

## 6. Robust declassification

A `Powerbox` maps the whole input and the observation instant to a release. `consent_agrees` requires equality of content, arrival, typed consent and lifecycle snapshots at each consent site. `robust` quantifies over all input pairs satisfying that relation and requires equal releases at every instant. All off-consent input variation is unrestricted.

The shipped reference powerbox copies exactly the authenticated grant at its designated consent site and takes lifecycle state only there. It is robust. Equal release sets fix the named `whether`, `what` and `to_whom` observations; the theorem proves that implication. Three powerboxes whose respective choices depend on an attacker-controlled ordinary input are rejected (R-08-025).

This is an input-pair formulation with the trusted context fixed. An implementation proof must relate every interactive compromised-component strategy to those input pairs, account for permitted revoke-only subtraction, and establish freshness of persistent context. That strategy-to-input correspondence is not proved by the reference example and is not replaced by calling any input difference a strategy.

`authorized_release_target` requires witnessed output for every input, the true requested observation instant, a delimited and scoped release rule, and robust behavior. A backdating powerbox is rejected: it cannot make expired authority appear live by returning an earlier observation cut. In `apex_vocabulary`, `declassified_flows_authorized` additionally requires that the actual `D` used by T equals a powerbox result at D's own instant. A release unrelated to the supplied powerbox is therefore refused. Linking this existential output witness to the particular executions compared by a composed theorem remains part of the apex instantiation review.

## 7. The apex instance and its limits

`apex_vocabulary` supplies `Policy`, `policy`, `indist`, `Declass`, `D`, the observation types and the release quotients expected by ApexTheorem. Its first and seventh seam fields have the concrete targets described above. Other theorem and axiom fields are `True` in these examples. They are placeholders for other workstreams, not proofs of their obligations, and no field-binding inventory row is closed by these examples.

The value quotient erases exactly the licensed recipient/object observations. Timing and architectural quotients are identities. `a_named_release_is_inside_T` admits a reference execution that actually returns a secret named object to its recipient. `the_same_release_after_expiry_is_outside_T` rejects the same execution at T itself after expiry. `the_leaking_composition_is_rejected_by_T` separately refuses a wider value leak. Thus permitted release has a positive witness as well as refusals.

The positive T theorems have explicit `FunExt2`, `FunExt3` and `PropExt` premises. They concern functional extensionality at two arities and propositional extensionality for this predicate-valued encoding. All are theorem premises; the artifact declares no global axioms. Consequently an empty `Print Assumptions` result is not an unconditional proof of T. Resolving or explicitly admitting these premises, or choosing an encoding that avoids them, remains open. No change to ApexTheorem or the register's declared assumption set is made or claimed necessary by a proved impossibility result.

## 8. Arrival timing under release

The register has not explicitly settled whether an object release also releases that object's arrival timing. R-08-026 names the object bound; R-05-156a requires an explicit arrival label. The present instance releases content only. `may_time_wide` and `indistinguishable_wide` represent the alternative for manifest channels, and `the_two_arrival_arms_are_different_policies` proves that the choice changes the policy.

The alternative runtime timing quotient is not implemented here. An owner decision in the register must state which timing observations, if any, follow a runtime grant and with which scope. Until then, the content-only instance is a review candidate and a proof against it does not establish the other reading.

## 9. Evidence index

The following is an authored traceability map, not a generated enumeration of the proof file. Each listed theorem can be inspected in its compiled type; independent review must judge the strength of the statement.

| Obligation | Register owner | Constants and refutations |
| --- | --- | --- |
| Finite lattice and labelling | R-08-021, R-08-024, R-08-035 | `wellformed`, `wellformed_requires_each_lattice_law`, `the_model_rejects_a_labelling`, `a_partial_order_without_bounds_is_not_a_lattice` |
| Device content and arrival relation | R-05-156a | `indistinguishable`, `a_quantified_out_arrival_is_equated`, `the_device_clause_decides_something`, `indistinguishability_has_classes` |
| Victim-shaped domains and observation/control distinction | R-05-156b | `the_domain_admits_victim_shaped_sets`, `observation_and_control_are_incomparable` |
| Explicit flow and observed progress/fault | R-08-021, R-08-027a, R-08-027c | `explicit_flow_target`, `the_confining_execution_is_noninterferent`, `a_leaked_value_is_refused`, `a_leaked_arrival_is_refused`, `a_leaked_progress_is_refused`, `a_leaked_fault_class_is_refused`, `a_leaked_termination_is_refused`, `a_leaked_restart_is_refused` |
| Manifest declassification | R-08-024, R-08-029 | `a_compose_time_channel_is_inside_the_policy` |
| Exact object and scope | R-08-026, R-08-037, R-17-012 | `the_shipped_rule_is_delimited`, `the_shipped_rule_is_scoped`, `a_release_wider_than_the_named_object_is_refused`, `an_edge_outliving_its_act_is_refused` |
| Typed witness and freshness | R-06-017, R-08-025, R-08-036, R-08-040 | `a_site_name_is_not_a_consent_witness`, `scope_state_decides_authority`, `both_lease_boundaries_are_live`, `both_one_shot_boundaries_are_live` |
| Robustness and exact D | R-08-025, R-05-160 | `the_shipped_powerbox_is_robust`, `robustness_fixes_whether_what_and_to_whom`, `an_attacker_driven_powerbox_is_refused`, `an_unrelated_D_is_not_authorized`, `a_backdated_release_is_not_authorized` |
| Apex positive and rejected instances | R-05-156, R-05-165, R-05-166 | `a_named_release_is_inside_T`, `the_same_release_after_expiry_is_outside_T`, `the_leaking_composition_is_rejected_by_T` |
| Unresolved arrival-release choice | R-05-156a, R-08-026 | `the_two_arrival_arms_are_different_policies` |

## 10. Acceptance predicate and remaining work

This predicate is proposed with the specification. It has not received the independent review required by R-05-150 and R-08-028. A later reviewer can reject either its coverage or its thresholds.

1. With the intended files tracked, `python tools/run.py proofs --jobs 2` compiles the artifact, enumerates its constants and claimed theorem types, audits assumptions and record witnesses, and completes kernel rechecking. Every explicit theorem premise remains visible in the compiled type; global axiom freedom alone does not discharge it.
2. `python tools/run.py proofs headers --file proofs/SecurityPolicyModel.v` and `python tools/run.py check` pass. Any shared-baseline disagreement is resolved before integration is accepted.
3. `python tools/run.py seed coq --file proofs/SecurityPolicyModel.v --region live --region licensed --region witnessed --region wellformed --jobs 2` runs the complete generated population for those contract regions. Its report names killed, stillborn and surviving mutants separately. Each survivor must be repaired or individually explained with a semantic equivalence or a stated missing obligation; a compilation failure is never reported as a live kill. This focused population does not claim exhaustive mutation coverage of the whole artifact.
4. A reviewer checks the evidence index against the actual propositions, reads each negative example and its positive counterpart, and verifies that the three requested refusals are present: invalid labelling, wider-than-consented release and an expired edge.
5. Independent specification review resolves or explicitly retains each open item below, with inventory status reflecting the retained work. Passing tools does not satisfy this clause.

| Remaining work | Owner and required result |
| --- | --- |
| Graph and object realization | Composition/kernel work: derive labels and channels from the admitted graph, bind object identities and rights to CHERI bounds, and bind the total site space to repeated external events |
| Complete observations | R-08-027a through R-08-027c: bind the snapshot observation fields to full histories and the actual scheduler, termination and restart transitions; establish schedule-only observable progress |
| Consent and lifecycle realization | Powerbox, trusted path and storage work: authenticated live/recorded witness production, freshness, request gating, one-shot consumption, revocation, cuts, record compatibility and unique act-instance indexing |
| Full robust-strategy theorem | R-08-025 and R-08-022: prove the strategy/input correspondence, including permitted revoke-only actions, over the kernel and multikernel semantics |
| Runtime arrival release | Register owner: decide the timing scope, then implement and review the selected runtime quotient |
| Unconditional apex use | Apex integration: discharge or replace extensionality premises and bind actual D to the compared executions, without `True` placeholders for other workstreams |
| Compiler preservation | `CJ-SECOMP`: state and prove robust preservation against the reviewed isolation model |
| Independent review | R-05-150 and R-08-028: review both artifacts at the same edition and set crown-jewel row 2's status |

This artifact supplies a model to review and executable reference evidence. It leaves all listed implementation and review obligations visible.
