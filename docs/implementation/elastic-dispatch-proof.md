# Elastic Dispatch Proof (Q34b)

## Scope and artifacts

[ElasticDispatch.v](../../proofs/ElasticDispatch.v) extends the Q34a contract module [ElasticDomain.v](../../proofs/ElasticDomain.v) together with [PartitionContext.v](../../proofs/PartitionContext.v), [CyclicExecutive.v](../../proofs/CyclicExecutive.v), and [EndpointIPC.v](../../proofs/EndpointIPC.v) to discharge the kernel elastic-dispatch obligations (`Q34b`) and close findings `F-428`, `F-430`, `F-431`, and `F-432` from [the findings register](../assurance/findings-register.md) against [the requirements register](../requirements-register.md).

Cited requirements in the module header: `R-05-163`, `R-05-164`, `R-05-165`, `R-05-166`, `R-07-014`, `R-07-014a`, `R-07-014c`, `R-07-027a`, `R-07-031b`, `R-07-032`, `R-07-037b`, `R-07-037c`, `R-07-037d`, `R-07-037e`, `R-07-037g`, `R-07-037h`, `R-07-037i`, `R-11-006c`, and `R-17-007b`.

## Proved properties

1. **Tentative-yield ABI extension (`R-07-031b`, `R-07-014a`)**:
   `ElasticInvocation` maps the five kernel entries (`EpSend`, `EpReceive`, `PcYield (tentative : bool)`, `RevRedeem`, `RevRevoke`) directly to `EndpointIPC.Invocation` (`abi_invocation_count_remains_five`), keeping the empty notification group and no named-successor invocation (`R-07-037b`). `invoke_pc_yield` proves that `tentative = true` returns `YContinue` or `YSwitchRequested` without switching (`tentative_yield_does_not_switch`), `tentative = false` charges and switches (`real_yield_enacts_switch`), and a second `PcYield true` after an unanswered `YSwitchRequested` enacts a real switch (`repeated_tentative_backstop_switches`), with no kernel vector-save path.
2. **Partition-context-only state and request cell (`R-07-027a`, `R-07-037i`)**:
   Per-member dispatch fields (`MemberDispatchFields`: `mdf_active`, `mdf_pending`, `mdf_weight`, `mdf_request`, `mdf_eligible`, `mdf_deadline`, `mdf_switch_requested_pending`) and session-manager fields (`SessionManagerFields`: `smf_vtime`, `smf_focus`, `smf_request_cell` carrying `Launch | Close | Focus`) live inside `PlacedPartitionContext` records, introducing zero new kernel tables or object classes (`no_new_kernel_table_or_class`), and `enact_session_request` only activates placed members (`request_cell_launch_activates_only_placed`).
3. **Inter-application `vmclear` and static-schedule elision (`R-07-014`, `R-07-014c`, `R-07-037c`, `R-07-037g`, `F-428`)**:
   `ElasticStep` executes `vmclear` whenever outgoing and incoming domain members belong to distinct applications (`cross_app_step_executes_vmclear`), allows `vmclear` elision within the same application (`same_app_step_elides_vmclear`), and permits static-schedule elision (`StaticSlotSwitch`) only when the outgoing partition slot's `StaticSlotManifest` fixes both `mstatus.VS = Off` and `mstatus.XS = Off` (`static_elision_requires_vs_xs_off`).
4. **Cooperative boundary rule and label-internal non-interference (`R-07-032`, `R-07-037e`, `R-07-037g`, `R-07-037h`)**:
   `cooperative_boundary_never_cuts` preserves `NeverCuts` under `boundary_need d = call_bound d + dc_yield_bound d + dc_step d`. `elastic_dispatch_label_internal_unwinding` establishes `LabelInternalUnwinding` for `select`, `reply`, and `kernel_dispatch_step`: global states agreeing on domain `d`'s state produce identical dispatch choices, replies, and next domain states without altering any slot boundary observable by another label.
5. **Universal cooperative EEVDF share-bound theorem (`R-07-037g`, `R-11-006c`, `R-17-007b`, `F-430`, `F-431`, `F-432`)**:
   With `eff_coop_request d s i := eff_request d s i + call_bound d + dc_yield_bound d`, `coop_deadline_at d s i ve := ve + qn (eff_coop_request d s i) / qn (eff_weight d s i)`, and `sink_inclusive_lag_bound d = qn (max_request d + call_bound d + dc_yield_bound d)`:
   - Zero-sum accounting lag (`sum_competing_lag d s == 0`) holds initially (`coop_fresh_zero_sum`) and is preserved by cooperative service charging (`coop_charge_preserves_zero_sum`), zero-lag joins (`coop_join_preserves_zero_sum`), lag-preserving reweighting (`coop_reweight_preserves_zero_sum`), published leaves (`coop_published_leave_preserves_zero_sum`), and zero-lag leaves (`coop_zero_lag_leave_preserves_zero_sum`), guaranteeing an eligible member whenever any member competes (`zero_sum_implies_eligible_exists`).
   - `cooperative_eevdf_lag_bounded` proves `Qabs (accounting_lag d sn i) <= sink_inclusive_lag_bound d` universally across all `AdmissibleCoopDecl` declarations and all conforming served-time traces (`CoopConforming` with runs `0 <= u <= eff_coop_request`, slots, idles, zero-lag joins, and zero-lag/passive leaves).
   - `cooperative_eevdf_shortfall_bounded` proves served-time shortfall `lag ServedTime i post - lag ServedTime i pre <= 2 * sink_inclusive_lag_bound d` over every interval where `i` stays continuously competing (`member_continuously_competing`).

## Refutations and witnesses

- **Mutant refutations (`R-05-165`, `R-05-166`)**:
  - `mutant_leaky_dispatch_is_refuted`: refutes cross-label inspection (`~ LabelInternalUnwinding`).
  - `mutant_no_boundary_is_refuted`: refutes dropping the boundary rule (`~ NeverCuts`).
  - `mutant_vector_save_is_refuted`: refutes saving kernel vector state instead of clearing it.
  - `mutant_vmclear_elision_is_refuted`: refutes eliding `vmclear` across applications or when an outgoing static slot has `mstatus.VS <> Off` or `mstatus.XS <> Off`.
  - `mutant_omitted_coop_padding_exceeds_lag_bound`: exhibits a concrete 3-member admissible declaration (`omitted_vd_decl`, `sink_inclusive_lag_bound = 10`) and conforming trace (`omitted_vd_steps`) omitting `call_bound + dc_yield_bound` from deadlines where member `2` reaches `accounting_lag = 101 # 10 > 10`.
- **Constructive witnesses (`R-05-166`)**:
  All six `Record` declarations (`MemberDispatchFields`, `SessionManagerFields`, `PlacedPartitionContext`, `DomainPlacedState`, `StaticSlotManifest`, `CoopConfig`) have closed top-level `witness_<Record>` definitions (`witness_MemberDispatchFields`, `witness_SessionManagerFields`, `witness_PlacedPartitionContext`, `witness_DomainPlacedState`, `witness_StaticSlotManifest`, `witness_CoopConfig`), with no `Axiom`, `Parameter`, `Admitted`, `CoInductive`, `CoFixpoint`, `Module Type`, `Functor`, or `SProp`.

## Local verification

Verified in the isolated WSL lane (`verifiedos-rocq-9.3.0-ocaml-5.4.1`) with `-w +default,-abstract-large-number -set "Default Goal Selector=!" -disallow-sprop`:

- Native compilation of `ElasticDispatch.v` (142 top-level declared symbols) exited `0` with no warnings.
- `Print Assumptions` across all 142 declared symbols returned `Closed under the global context` for all 142 symbols (`0` non-closed).
- `rocqchk -silent -o` on `ElasticDispatch` exited `0` (`Axioms: <none>`, predicative `Set`, no rewrite rules, no unsafe cofixpoints or type-in-type).
- Host header derivation (`python tools/run.py proofs headers --write`) updated the derived SHA256 block on `proofs/ElasticDispatch.v` (`14` `(*| discharges: ... |*)` claims, `0` lexical audit faults).

Full repository host checks, proof receipt export, and Guest CI remain for integrator/user execution.
