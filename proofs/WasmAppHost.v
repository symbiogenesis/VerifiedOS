(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   WasmAppHost.v

   Specification and non-vacuity model for Q34f-i same-session Wasm
   application host lifecycle and security boundaries:
   - Canonical bundle descriptor and immutable closure validation
     (R-14-013e, R-14-013g, R-14-013h): Prepare authenticates closure,
     descriptor, Core 3.0 validity, host/import ABI compatibility, and
     bounded resource reservations without executing guest start functions
     or spending new grants; malformed, forged, incompatible, or oversized
     inputs fail closed while leaving any live app running.
   - Distinct clear-group Launch and digest-bound consent (R-14-013e,
     R-14-013f, R-08-047b): every Launch allocates a distinct clear-group
     host instance (`group_id`) with fresh activation binding (`act_id`,
     `epoch`), refuses filesystem-path authority, and binds trusted consent
     to the exact bundle digest rather than the guest-controlled UI label.
   - Binding-scoped InvokeImport and tag-free transport (R-14-013f,
     R-08-047c): refuses cross-instance or stale handles, pool-capability
     exports to fixed-tier services, tagged transport, calls from non-active
     or retiring hosts, and replies whose epoch disagrees with the active
     requesting epoch.
   - Transactional Replace (R-14-013f): pre-commit failure preserves the
     old binding live and usable; post-commit failure closes the host with
     the candidate's acknowledged durable work without automatic rollback or
     mixing bundle A's grants with bundle B's execution or durable state.
   - Cancel/Close lifecycle and sweep-before-reuse barrier (R-08-046,
     R-08-047b, R-14-013f, R-14-013g): Free -> Prepared -> Active ->
     Cancelling -> Sweeping -> Sanitized -> Reusable stops execution and
     ingress, drains/cancels outstanding imports, completes holder-map sweep
     and zeroization before Reusable, and retires exhausted epochs without
     wraparound.
   - Semantic checkpoint Restore (R-14-013f): validates checkpoint
     authentication, bundle digest, profile, ABI, schema, and generation,
     and activates using current grants only without resurrecting old grants,
     tagged memory, or session keys.

   Assumptions and non-vacuity (R-05-163, R-05-164, R-05-165, R-05-166):
   - Zero axioms (`Closed under the global context`), prelude + `ProofSupport`
     only, and every declared record carries a closed `witness_<Record>`
     inhabitant.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-08-046 R-08-047b R-08-047c R-14-013e
      R-14-013f R-14-013g R-14-013h
   SHA256: 600459a64a8c9e25c439d81572f15135ce5c1cdf55d4b501b9654a0e44068ee8
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport.

Module PS := ProofSupport.

(* =========================================================================
   1. Host lifecycle phases, errors, and policies (R-08-046, R-14-013e)
   ========================================================================= *)

Inductive HostPhase : Type :=
| PhaseFree
| PhasePrepared
| PhaseActive
| PhaseCancelling
| PhaseSweeping
| PhaseSanitized
| PhaseReusable.

Definition host_phase_eqb (a b : HostPhase) : bool :=
  match a, b with
  | PhaseFree, PhaseFree => true
  | PhasePrepared, PhasePrepared => true
  | PhaseActive, PhaseActive => true
  | PhaseCancelling, PhaseCancelling => true
  | PhaseSweeping, PhaseSweeping => true
  | PhaseSanitized, PhaseSanitized => true
  | PhaseReusable, PhaseReusable => true
  | _, _ => false
  end.

Inductive HostErr : Type :=
| ErrBadPhase
| ErrFsPathAuthority
| ErrForgedClosure
| ErrForgedDescriptor
| ErrIncompatibleAbi
| ErrOversizedReservation
| ErrOverScopedGrant
| ErrNoStaging
| ErrNoCapacity
| ErrNoConsent
| ErrConsentDigestMismatch
| ErrEpochExhausted
| ErrGroupCollision
| ErrHandleScope
| ErrEpochMismatch
| ErrPoolCapExport
| ErrTaggedTransport
| ErrYieldBound
| ErrPendingImports
| ErrNotSanitized
| ErrUnauthCheckpoint
| ErrStaleSchema
| ErrIncompatibleGen
| ErrCommitUnauthorized
| ErrPostCommitClosed.

Record HostPolicy : Type := {
  hp_abi_version : nat;
  hp_profile_id : nat;
  hp_generation : nat;
  hp_mem_page_ceiling : nat;
  hp_table_ceiling : nat;
  hp_stack_ceiling : nat;
  hp_import_ceiling : list nat;
  hp_max_epoch : nat
}.

Record BundleDescriptor : Type := {
  bd_bundle_digest : nat;
  bd_closure_digest : nat;
  bd_module_digest : nat;
  bd_assets_digest : nat;
  bd_ui_label : nat;
  bd_abi_version : nat;
  bd_core30_valid : bool;
  bd_closure_valid : bool;
  bd_descriptor_valid : bool;
  bd_init_mem_pages : nat;
  bd_max_mem_pages : nat;
  bd_table_limit : nat;
  bd_stack_limit : nat;
  bd_schema_id : nat;
  bd_requested_imports : list nat;
  bd_has_start_fn : bool;
  bd_uses_fs_path_authority : bool
}.

Record TrustedConsent : Type := {
  tc_user_consented : bool;
  tc_credential_ok : bool;
  tc_trusted_digest : nat;
  tc_ui_label_shown : nat;
  tc_nonce : nat
}.

Record ImportHandle : Type := {
  ih_act_id : nat;
  ih_epoch : nat;
  ih_group_id : nat;
  ih_import_id : nat;
  ih_scope_ok : bool
}.

Record ImportCall : Type := {
  ic_handle : ImportHandle;
  ic_op_id : nat;
  ic_exports_pool_cap : bool;
  ic_tagged_transport : bool;
  ic_reply_epoch : nat;
  ic_yield_bounded : bool
}.

Record DurableState : Type := {
  ds_bundle_digest : nat;
  ds_schema_id : nat;
  ds_state_digest : nat;
  ds_acked : bool
}.

Record SemanticCheckpoint : Type := {
  sc_bundle_digest : nat;
  sc_abi_version : nat;
  sc_profile_id : nat;
  sc_schema_id : nat;
  sc_generation : nat;
  sc_hmac_valid : bool;
  sc_durable_digest : nat;
  sc_embedded_old_grants : list nat;
  sc_embedded_tagged_mem : bool;
  sc_embedded_session_key : nat
}.

Record PoolResources : Type := {
  pr_avail_pages : nat;
  pr_staging_avail : bool;
  pr_quarantine_pages : nat;
  pr_next_act_id : nat
}.

Record HostSlot : Type := {
  hs_slot_id : nat;
  hs_group_id : nat;
  hs_phase : HostPhase;
  hs_act_id : nat;
  hs_epoch : nat;
  hs_epoch_retired : bool;
  hs_prepared : option BundleDescriptor;
  hs_active_bundle : option BundleDescriptor;
  hs_active_grants : list nat;
  hs_session_key : nat;
  hs_tagged_mem : bool;
  hs_start_executed : bool;
  hs_new_grants_spent : bool;
  hs_exec_stopped : bool;
  hs_ingress_stopped : bool;
  hs_pending_imports : nat;
  hs_sweep_done : bool;
  hs_zeroized : bool;
  hs_durable : option DurableState
}.

Record ReplaceRequest : Type := {
  rr_candidate : BundleDescriptor;
  rr_consent : option TrustedConsent;
  rr_new_grants : list nat;
  rr_transition_reserved : bool;
  rr_commit_authorized : bool;
  rr_durable_policy_ok : bool;
  rr_post_commit_ok : bool;
  rr_acked_durable_digest : nat;
  rr_uses_fs_path_authority : bool
}.

Record HostOutcome : Type := {
  ho_ok : bool;
  ho_err : option HostErr;
  ho_slot : HostSlot;
  ho_res : PoolResources
}.

Inductive InvokeOutcome : Type :=
| InvokeOk (reply_epoch : nat) (op_id : nat)
| InvokeErr (err : HostErr).

(* =========================================================================
   2. Validation and prepare (R-14-013e, R-14-013g, R-14-013h)
   ========================================================================= *)

Definition expected_closure_digest (bd : BundleDescriptor) : nat :=
  Nat.add (Nat.mul 7 bd.(bd_module_digest))
    (Nat.add (Nat.mul 3 bd.(bd_assets_digest)) 1).

Definition expected_bundle_digest (bd : BundleDescriptor) : nat :=
  Nat.add (Nat.mul 11 bd.(bd_closure_digest))
    (Nat.add (Nat.mul 5 bd.(bd_abi_version))
      (Nat.add bd.(bd_schema_id) bd.(bd_max_mem_pages))).

Definition grants_subset (req allowed : list nat) : bool :=
  PS.all_of (fun g => PS.mem_nat g allowed) req.

Definition validate_bundle (pol : HostPolicy) (res : PoolResources)
    (bd : BundleDescriptor) : option HostErr :=
  if bd.(bd_uses_fs_path_authority) then Some ErrFsPathAuthority
  else if negb bd.(bd_closure_valid) then Some ErrForgedClosure
  else if negb (Nat.eqb bd.(bd_closure_digest) (expected_closure_digest bd)) then
    Some ErrForgedClosure
  else if negb bd.(bd_descriptor_valid) then Some ErrForgedDescriptor
  else if negb bd.(bd_core30_valid) then Some ErrForgedDescriptor
  else if negb (Nat.eqb bd.(bd_bundle_digest) (expected_bundle_digest bd)) then
    Some ErrForgedDescriptor
  else if negb (Nat.eqb bd.(bd_abi_version) pol.(hp_abi_version)) then
    Some ErrIncompatibleAbi
  else if negb (Nat.leb bd.(bd_init_mem_pages) bd.(bd_max_mem_pages)) then
    Some ErrOversizedReservation
  else if negb (Nat.leb bd.(bd_max_mem_pages) pol.(hp_mem_page_ceiling)) then
    Some ErrOversizedReservation
  else if negb (Nat.leb bd.(bd_init_mem_pages) res.(pr_avail_pages)) then
    Some ErrOversizedReservation
  else if negb (Nat.leb bd.(bd_table_limit) pol.(hp_table_ceiling)) then
    Some ErrOversizedReservation
  else if negb (Nat.leb bd.(bd_stack_limit) pol.(hp_stack_ceiling)) then
    Some ErrOversizedReservation
  else if negb (grants_subset bd.(bd_requested_imports) pol.(hp_import_ceiling)) then
    Some ErrOverScopedGrant
  else None.

Lemma validate_bundle_ne_postcommit :
  forall pol res bd, validate_bundle pol res bd <> Some ErrPostCommitClosed.
Proof.
  intros pol res bd H.
  unfold validate_bundle in H.
  destruct (bd_uses_fs_path_authority bd); [ discriminate H | ].
  destruct (bd_closure_valid bd); simpl in H; [ | discriminate H ].
  destruct (Nat.eqb (bd_closure_digest bd) (expected_closure_digest bd));
    simpl in H; [ | discriminate H ].
  destruct (bd_descriptor_valid bd); simpl in H; [ | discriminate H ].
  destruct (bd_core30_valid bd); simpl in H; [ | discriminate H ].
  destruct (Nat.eqb (bd_bundle_digest bd) (expected_bundle_digest bd));
    simpl in H; [ | discriminate H ].
  destruct (Nat.eqb (bd_abi_version bd) (hp_abi_version pol));
    simpl in H; [ | discriminate H ].
  destruct (Nat.leb (bd_init_mem_pages bd) (bd_max_mem_pages bd));
    simpl in H; [ | discriminate H ].
  destruct (Nat.leb (bd_max_mem_pages bd) (hp_mem_page_ceiling pol));
    simpl in H; [ | discriminate H ].
  destruct (Nat.leb (bd_init_mem_pages bd) (pr_avail_pages res));
    simpl in H; [ | discriminate H ].
  destruct (Nat.leb (bd_table_limit bd) (hp_table_ceiling pol));
    simpl in H; [ | discriminate H ].
  destruct (Nat.leb (bd_stack_limit bd) (hp_stack_ceiling pol));
    simpl in H; [ | discriminate H ].
  destruct (grants_subset (bd_requested_imports bd) (hp_import_ceiling pol));
    simpl in H; discriminate H.
Qed.

Definition slot_accepts_prepare (ph : HostPhase) : bool :=
  match ph with
  | PhaseFree => true
  | PhaseReusable => true
  | _ => false
  end.

Definition fail_outcome (err : HostErr) (slot : HostSlot) (res : PoolResources)
    : HostOutcome :=
  {| ho_ok := false; ho_err := Some err; ho_slot := slot; ho_res := res |}.

Definition ok_outcome (slot : HostSlot) (res : PoolResources) : HostOutcome :=
  {| ho_ok := true; ho_err := None; ho_slot := slot; ho_res := res |}.

Definition prepare_host (pol : HostPolicy) (res : PoolResources)
    (slot : HostSlot) (bd : BundleDescriptor) : HostOutcome :=
  if negb (slot_accepts_prepare slot.(hs_phase)) then
    fail_outcome ErrBadPhase slot res
  else if negb res.(pr_staging_avail) then
    fail_outcome ErrNoStaging slot res
  else
    match validate_bundle pol res bd with
    | Some err => fail_outcome err slot res
    | None =>
        let slot' := {|
          hs_slot_id := slot.(hs_slot_id);
          hs_group_id := slot.(hs_group_id);
          hs_phase := PhasePrepared;
          hs_act_id := slot.(hs_act_id);
          hs_epoch := slot.(hs_epoch);
          hs_epoch_retired := slot.(hs_epoch_retired);
          hs_prepared := Some bd;
          hs_active_bundle := None;
          hs_active_grants := nil;
          hs_session_key := 0;
          hs_tagged_mem := false;
          hs_start_executed := false;
          hs_new_grants_spent := false;
          hs_exec_stopped := true;
          hs_ingress_stopped := true;
          hs_pending_imports := 0;
          hs_sweep_done := slot.(hs_sweep_done);
          hs_zeroized := slot.(hs_zeroized);
          hs_durable := slot.(hs_durable)
        |} in
        ok_outcome slot' res
    end.

(*| discharges: R-14-013e, R-14-013g, R-14-013h |*)
Theorem prepare_executes_no_start_and_spends_no_grants :
  forall pol res slot bd out,
    prepare_host pol res slot bd = out ->
    out.(ho_ok) = true ->
    out.(ho_slot).(hs_phase) = PhasePrepared /\
    out.(ho_slot).(hs_start_executed) = false /\
    out.(ho_slot).(hs_new_grants_spent) = false /\
    out.(ho_slot).(hs_active_grants) = nil /\
    out.(ho_slot).(hs_active_bundle) = None.
Proof.
  intros pol res slot bd out Hstep Hok.
  unfold prepare_host in Hstep.
  destruct (slot_accepts_prepare (hs_phase slot)) eqn:Hph;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (pr_staging_avail res) eqn:Hstg;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (validate_bundle pol res bd) as [err | ] eqn:Hval;
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  rewrite <- Hstep.
  repeat split; reflexivity.
Qed.

(*| discharges: R-14-013e |*)
Theorem prepare_failure_preserves_slot_and_live_binding :
  forall pol res slot bd out,
    prepare_host pol res slot bd = out ->
    out.(ho_ok) = false ->
    out.(ho_slot) = slot /\ out.(ho_res) = res.
Proof.
  intros pol res slot bd out Hstep Hfail.
  unfold prepare_host in Hstep.
  destruct (slot_accepts_prepare (hs_phase slot)) eqn:Hph.
  - destruct (pr_staging_avail res) eqn:Hstg.
    + destruct (validate_bundle pol res bd) as [err | ] eqn:Hval.
      * rewrite <- Hstep. split; reflexivity.
      * rewrite <- Hstep in Hfail. discriminate Hfail.
    + rewrite <- Hstep. split; reflexivity.
  - rewrite <- Hstep. split; reflexivity.
Qed.

(* =========================================================================
   3. Launch into distinct clear-group with fresh epoch and digest consent
      (R-14-013e, R-14-013f, R-08-047b)
   ========================================================================= *)

Definition check_consent (bd : BundleDescriptor)
    (consent : option TrustedConsent) : option HostErr :=
  match consent with
  | None => Some ErrNoConsent
  | Some tc =>
      if negb tc.(tc_user_consented) then Some ErrNoConsent
      else if negb tc.(tc_credential_ok) then Some ErrNoConsent
      else if negb (Nat.eqb tc.(tc_trusted_digest) bd.(bd_bundle_digest)) then
        Some ErrConsentDigestMismatch
      else None
  end.

Lemma check_consent_ne_postcommit :
  forall bd consent, check_consent bd consent <> Some ErrPostCommitClosed.
Proof.
  intros bd [tc | ] H; unfold check_consent in H; [ | discriminate H ].
  destruct (tc_user_consented tc); simpl in H; [ | discriminate H ].
  destruct (tc_credential_ok tc); simpl in H; [ | discriminate H ].
  destruct (Nat.eqb (tc_trusted_digest tc) (bd_bundle_digest bd));
    simpl in H; discriminate H.
Qed.

Definition launch_host (pol : HostPolicy) (res : PoolResources)
    (slot : HostSlot) (consent : option TrustedConsent)
    (initial_grants : list nat) (uses_fs_path : bool)
    (new_session_key : nat) (used_groups : list nat) : HostOutcome :=
  if uses_fs_path then fail_outcome ErrFsPathAuthority slot res
  else if negb (host_phase_eqb slot.(hs_phase) PhasePrepared) then
    fail_outcome ErrBadPhase slot res
  else
    match slot.(hs_prepared) with
    | None => fail_outcome ErrBadPhase slot res
    | Some bd =>
        if orb slot.(hs_epoch_retired)
               (negb (Nat.ltb slot.(hs_epoch) pol.(hp_max_epoch))) then
          let retired := {|
            hs_slot_id := slot.(hs_slot_id);
            hs_group_id := slot.(hs_group_id);
            hs_phase := slot.(hs_phase);
            hs_act_id := slot.(hs_act_id);
            hs_epoch := slot.(hs_epoch);
            hs_epoch_retired := true;
            hs_prepared := slot.(hs_prepared);
            hs_active_bundle := slot.(hs_active_bundle);
            hs_active_grants := slot.(hs_active_grants);
            hs_session_key := slot.(hs_session_key);
            hs_tagged_mem := slot.(hs_tagged_mem);
            hs_start_executed := slot.(hs_start_executed);
            hs_new_grants_spent := slot.(hs_new_grants_spent);
            hs_exec_stopped := slot.(hs_exec_stopped);
            hs_ingress_stopped := slot.(hs_ingress_stopped);
            hs_pending_imports := slot.(hs_pending_imports);
            hs_sweep_done := slot.(hs_sweep_done);
            hs_zeroized := slot.(hs_zeroized);
            hs_durable := slot.(hs_durable)
          |} in
          fail_outcome ErrEpochExhausted retired res
        else if PS.mem_nat slot.(hs_group_id) used_groups then
          fail_outcome ErrGroupCollision slot res
        else
          match check_consent bd consent with
          | Some err => fail_outcome err slot res
          | None =>
              if negb (andb (grants_subset initial_grants bd.(bd_requested_imports))
                            (grants_subset initial_grants pol.(hp_import_ceiling))) then
                fail_outcome ErrOverScopedGrant slot res
              else if negb (Nat.leb bd.(bd_init_mem_pages) res.(pr_avail_pages)) then
                fail_outcome ErrNoCapacity slot res
              else
                let slot' := {|
                  hs_slot_id := slot.(hs_slot_id);
                  hs_group_id := slot.(hs_group_id);
                  hs_phase := PhaseActive;
                  hs_act_id := res.(pr_next_act_id);
                  hs_epoch := S slot.(hs_epoch);
                  hs_epoch_retired := false;
                  hs_prepared := None;
                  hs_active_bundle := Some bd;
                  hs_active_grants := initial_grants;
                  hs_session_key := new_session_key;
                  hs_tagged_mem := false;
                  hs_start_executed := bd.(bd_has_start_fn);
                  hs_new_grants_spent := true;
                  hs_exec_stopped := false;
                  hs_ingress_stopped := false;
                  hs_pending_imports := 0;
                  hs_sweep_done := false;
                  hs_zeroized := false;
                  hs_durable := slot.(hs_durable)
                |} in
                let res' := {|
                  pr_avail_pages := Nat.sub res.(pr_avail_pages) bd.(bd_init_mem_pages);
                  pr_staging_avail := res.(pr_staging_avail);
                  pr_quarantine_pages := res.(pr_quarantine_pages);
                  pr_next_act_id := S res.(pr_next_act_id)
                |} in
                ok_outcome slot' res'
          end
    end.

(*| discharges: R-14-013f |*)
Theorem launch_refuses_ui_label_spoof_when_digest_differs :
  forall pol res slot bd tc grants skey groups,
    slot.(hs_phase) = PhasePrepared ->
    slot.(hs_prepared) = Some bd ->
    slot.(hs_epoch_retired) = false ->
    Nat.ltb slot.(hs_epoch) pol.(hp_max_epoch) = true ->
    PS.mem_nat slot.(hs_group_id) groups = false ->
    tc.(tc_user_consented) = true ->
    tc.(tc_credential_ok) = true ->
    tc.(tc_ui_label_shown) = bd.(bd_ui_label) ->
    Nat.eqb tc.(tc_trusted_digest) bd.(bd_bundle_digest) = false ->
    let out := launch_host pol res slot (Some tc) grants false skey groups in
    out.(ho_ok) = false /\ out.(ho_err) = Some ErrConsentDigestMismatch.
Proof.
  intros pol res slot bd tc grants skey groups Hph Hprep Hret Hlt Hgrp Huc Hcr _ Hdig.
  unfold launch_host.
  rewrite Hph. simpl.
  rewrite Hprep, Hret, Hlt, Hgrp. simpl.
  unfold check_consent.
  rewrite Huc, Hcr, Hdig. simpl.
  split; reflexivity.
Qed.

(*| discharges: R-14-013f |*)
Theorem launch_refuses_exhausted_epoch_without_wraparound :
  forall pol res slot bd consent grants skey groups,
    slot.(hs_phase) = PhasePrepared ->
    slot.(hs_prepared) = Some bd ->
    Nat.ltb slot.(hs_epoch) pol.(hp_max_epoch) = false ->
    let out := launch_host pol res slot consent grants false skey groups in
    out.(ho_ok) = false /\
    out.(ho_err) = Some ErrEpochExhausted /\
    out.(ho_slot).(hs_epoch) = slot.(hs_epoch) /\
    out.(ho_slot).(hs_epoch_retired) = true.
Proof.
  intros pol res slot bd consent grants skey groups Hph Hprep Hge.
  unfold launch_host.
  rewrite Hph. simpl.
  rewrite Hprep, Hge.
  destruct (hs_epoch_retired slot); simpl; repeat split; reflexivity.
Qed.

(*| discharges: R-14-013e, R-14-013f, R-08-047b |*)
Theorem launch_succeeds_with_fresh_epoch_distinct_group_and_exact_digest :
  forall pol res slot consent grants skey groups out,
    launch_host pol res slot consent grants false skey groups = out ->
    out.(ho_ok) = true ->
    exists bd tc,
      slot.(hs_prepared) = Some bd /\
      consent = Some tc /\
      tc.(tc_trusted_digest) = bd.(bd_bundle_digest) /\
      PS.mem_nat slot.(hs_group_id) groups = false /\
      out.(ho_slot).(hs_phase) = PhaseActive /\
      out.(ho_slot).(hs_epoch) = S slot.(hs_epoch) /\
      out.(ho_slot).(hs_act_id) = res.(pr_next_act_id) /\
      out.(ho_slot).(hs_tagged_mem) = false.
Proof.
  intros pol res slot consent grants skey groups out Hstep Hok.
  unfold launch_host in Hstep.
  destruct (host_phase_eqb (hs_phase slot) PhasePrepared) eqn:Hph;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (hs_prepared slot) as [bd | ] eqn:Hprep;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (orb (hs_epoch_retired slot) (negb (Nat.ltb (hs_epoch slot) (hp_max_epoch pol)))) eqn:Hep;
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  destruct (PS.mem_nat (hs_group_id slot) groups) eqn:Hgrp;
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  destruct (check_consent bd consent) as [err | ] eqn:Hcon;
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  destruct (andb (grants_subset grants (bd_requested_imports bd))
                 (grants_subset grants (hp_import_ceiling pol))) eqn:Hgr;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (Nat.leb (bd_init_mem_pages bd) (pr_avail_pages res)) eqn:Hmem;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct consent as [tc | ]; [ | discriminate Hcon ].
  unfold check_consent in Hcon.
  destruct (tc_user_consented tc) eqn:Huc; [ | discriminate Hcon ].
  destruct (tc_credential_ok tc) eqn:Hcr; [ | discriminate Hcon ].
  destruct (Nat.eqb (tc_trusted_digest tc) (bd_bundle_digest bd)) eqn:Heq;
    [ | discriminate Hcon ].
  exists bd, tc.
  rewrite <- Hstep.
  repeat split; try reflexivity.
  exact (PS.nat_eqb_true (tc_trusted_digest tc) (bd_bundle_digest bd) Heq).
Qed.

(* =========================================================================
   4. Binding-scoped InvokeImport and tag-free transport
      (R-14-013f, R-08-047c, R-14-013g)
   ========================================================================= *)

Definition invoke_import (slot : HostSlot) (call : ImportCall) : InvokeOutcome :=
  if negb (host_phase_eqb slot.(hs_phase) PhaseActive) then
    InvokeErr ErrBadPhase
  else if orb slot.(hs_exec_stopped) slot.(hs_ingress_stopped) then
    InvokeErr ErrBadPhase
  else if orb (negb (Nat.eqb call.(ic_handle).(ih_act_id) slot.(hs_act_id)))
              (orb (negb (Nat.eqb call.(ic_handle).(ih_epoch) slot.(hs_epoch)))
                   (negb (Nat.eqb call.(ic_handle).(ih_group_id) slot.(hs_group_id)))) then
    InvokeErr ErrHandleScope
  else if negb call.(ic_handle).(ih_scope_ok) then
    InvokeErr ErrHandleScope
  else if negb (PS.mem_nat call.(ic_handle).(ih_import_id) slot.(hs_active_grants)) then
    InvokeErr ErrOverScopedGrant
  else if call.(ic_exports_pool_cap) then
    InvokeErr ErrPoolCapExport
  else if call.(ic_tagged_transport) then
    InvokeErr ErrTaggedTransport
  else if negb (Nat.eqb call.(ic_reply_epoch) slot.(hs_epoch)) then
    InvokeErr ErrEpochMismatch
  else if negb call.(ic_yield_bounded) then
    InvokeErr ErrYieldBound
  else
    InvokeOk slot.(hs_epoch) call.(ic_op_id).

(*| discharges: R-14-013f, R-08-047c, R-14-013g |*)
Theorem invoke_requires_active_matching_binding_epoch_and_tagfree_transport :
  forall slot call r_epoch op_id,
    invoke_import slot call = InvokeOk r_epoch op_id ->
    slot.(hs_phase) = PhaseActive /\
    slot.(hs_exec_stopped) = false /\
    slot.(hs_ingress_stopped) = false /\
    call.(ic_handle).(ih_act_id) = slot.(hs_act_id) /\
    call.(ic_handle).(ih_epoch) = slot.(hs_epoch) /\
    call.(ic_handle).(ih_group_id) = slot.(hs_group_id) /\
    PS.mem_nat call.(ic_handle).(ih_import_id) slot.(hs_active_grants) = true /\
    call.(ic_exports_pool_cap) = false /\
    call.(ic_tagged_transport) = false /\
    call.(ic_reply_epoch) = slot.(hs_epoch) /\
    r_epoch = slot.(hs_epoch) /\
    call.(ic_yield_bounded) = true.
Proof.
  intros slot call r_epoch op_id H.
  unfold invoke_import in H.
  destruct (hs_phase slot) eqn:Hph; simpl in H; try discriminate H.
  destruct (hs_exec_stopped slot) eqn:Hes;
    destruct (hs_ingress_stopped slot) eqn:His; simpl in H; try discriminate H.
  destruct (Nat.eqb (ih_act_id (ic_handle call)) (hs_act_id slot)) eqn:Hact;
    destruct (Nat.eqb (ih_epoch (ic_handle call)) (hs_epoch slot)) eqn:Hep;
    destruct (Nat.eqb (ih_group_id (ic_handle call)) (hs_group_id slot)) eqn:Hgrp;
    simpl in H; try discriminate H.
  destruct (ih_scope_ok (ic_handle call)) eqn:Hsc; [ | discriminate H ].
  destruct (PS.mem_nat (ih_import_id (ic_handle call)) (hs_active_grants slot)) eqn:Hmem;
    [ | discriminate H ].
  destruct (ic_exports_pool_cap call) eqn:Hpool; [ discriminate H | ].
  destruct (ic_tagged_transport call) eqn:Htag; [ discriminate H | ].
  destruct (Nat.eqb (ic_reply_epoch call) (hs_epoch slot)) eqn:Hrep;
    [ | discriminate H ].
  destruct (ic_yield_bounded call) eqn:Hyld; [ | discriminate H ].
  injection H as Heq_ep Heq_op.
  repeat split; try reflexivity; try assumption.
  - exact (PS.nat_eqb_true _ _ Hact).
  - exact (PS.nat_eqb_true _ _ Hep).
  - exact (PS.nat_eqb_true _ _ Hgrp).
  - exact (PS.nat_eqb_true _ _ Hrep).
  - symmetry. exact Heq_ep.
Qed.

(*| discharges: R-08-047c |*)
Theorem invoke_refuses_pool_cap_export :
  forall slot call,
    slot.(hs_phase) = PhaseActive ->
    slot.(hs_exec_stopped) = false ->
    slot.(hs_ingress_stopped) = false ->
    call.(ic_handle).(ih_act_id) = slot.(hs_act_id) ->
    call.(ic_handle).(ih_epoch) = slot.(hs_epoch) ->
    call.(ic_handle).(ih_group_id) = slot.(hs_group_id) ->
    call.(ic_handle).(ih_scope_ok) = true ->
    PS.mem_nat call.(ic_handle).(ih_import_id) slot.(hs_active_grants) = true ->
    call.(ic_exports_pool_cap) = true ->
    invoke_import slot call = InvokeErr ErrPoolCapExport.
Proof.
  intros slot call Hph Hes His Hact Hep Hgrp Hsc Hmem Hpool.
  unfold invoke_import.
  rewrite Hph, Hes, His, Hact, Hep, Hgrp, Hsc, Hmem, Hpool.
  rewrite (PS.nat_eqb_refl (hs_act_id slot)).
  rewrite (PS.nat_eqb_refl (hs_epoch slot)).
  rewrite (PS.nat_eqb_refl (hs_group_id slot)).
  reflexivity.
Qed.

(* =========================================================================
   5. Cancel / Close lifecycle and sweep-before-reuse barrier
      (R-08-046, R-08-047b, R-14-013f, R-14-013g)
   ========================================================================= *)

Definition cancel_begin (slot : HostSlot) (res : PoolResources) : HostOutcome :=
  if negb (host_phase_eqb slot.(hs_phase) PhaseActive) then
    fail_outcome ErrBadPhase slot res
  else
    let slot' := {|
      hs_slot_id := slot.(hs_slot_id);
      hs_group_id := slot.(hs_group_id);
      hs_phase := PhaseCancelling;
      hs_act_id := slot.(hs_act_id);
      hs_epoch := slot.(hs_epoch);
      hs_epoch_retired := slot.(hs_epoch_retired);
      hs_prepared := slot.(hs_prepared);
      hs_active_bundle := slot.(hs_active_bundle);
      hs_active_grants := slot.(hs_active_grants);
      hs_session_key := slot.(hs_session_key);
      hs_tagged_mem := slot.(hs_tagged_mem);
      hs_start_executed := slot.(hs_start_executed);
      hs_new_grants_spent := slot.(hs_new_grants_spent);
      hs_exec_stopped := true;
      hs_ingress_stopped := true;
      hs_pending_imports := slot.(hs_pending_imports);
      hs_sweep_done := false;
      hs_zeroized := false;
      hs_durable := slot.(hs_durable)
    |} in
    ok_outcome slot' res.

Definition cancel_drain_step (slot : HostSlot) (res : PoolResources) : HostOutcome :=
  if negb (host_phase_eqb slot.(hs_phase) PhaseCancelling) then
    fail_outcome ErrBadPhase slot res
  else
    let slot' := {|
      hs_slot_id := slot.(hs_slot_id);
      hs_group_id := slot.(hs_group_id);
      hs_phase := PhaseCancelling;
      hs_act_id := slot.(hs_act_id);
      hs_epoch := slot.(hs_epoch);
      hs_epoch_retired := slot.(hs_epoch_retired);
      hs_prepared := slot.(hs_prepared);
      hs_active_bundle := slot.(hs_active_bundle);
      hs_active_grants := slot.(hs_active_grants);
      hs_session_key := slot.(hs_session_key);
      hs_tagged_mem := slot.(hs_tagged_mem);
      hs_start_executed := slot.(hs_start_executed);
      hs_new_grants_spent := slot.(hs_new_grants_spent);
      hs_exec_stopped := slot.(hs_exec_stopped);
      hs_ingress_stopped := slot.(hs_ingress_stopped);
      hs_pending_imports := 0;
      hs_sweep_done := slot.(hs_sweep_done);
      hs_zeroized := slot.(hs_zeroized);
      hs_durable := slot.(hs_durable)
    |} in
    ok_outcome slot' res.

Definition enter_sweeping (slot : HostSlot) (res : PoolResources) : HostOutcome :=
  if negb (host_phase_eqb slot.(hs_phase) PhaseCancelling) then
    fail_outcome ErrBadPhase slot res
  else if orb (negb slot.(hs_exec_stopped)) (negb slot.(hs_ingress_stopped)) then
    fail_outcome ErrBadPhase slot res
  else if negb (Nat.eqb slot.(hs_pending_imports) 0) then
    fail_outcome ErrPendingImports slot res
  else
    let slot' := {|
      hs_slot_id := slot.(hs_slot_id);
      hs_group_id := slot.(hs_group_id);
      hs_phase := PhaseSweeping;
      hs_act_id := slot.(hs_act_id);
      hs_epoch := slot.(hs_epoch);
      hs_epoch_retired := slot.(hs_epoch_retired);
      hs_prepared := slot.(hs_prepared);
      hs_active_bundle := slot.(hs_active_bundle);
      hs_active_grants := slot.(hs_active_grants);
      hs_session_key := slot.(hs_session_key);
      hs_tagged_mem := slot.(hs_tagged_mem);
      hs_start_executed := slot.(hs_start_executed);
      hs_new_grants_spent := slot.(hs_new_grants_spent);
      hs_exec_stopped := true;
      hs_ingress_stopped := true;
      hs_pending_imports := 0;
      hs_sweep_done := false;
      hs_zeroized := false;
      hs_durable := slot.(hs_durable)
    |} in
    ok_outcome slot' res.

Definition sweep_and_zeroize (slot : HostSlot) (res : PoolResources) : HostOutcome :=
  if negb (host_phase_eqb slot.(hs_phase) PhaseSweeping) then
    fail_outcome ErrBadPhase slot res
  else
    let reclaimed :=
      match slot.(hs_active_bundle) with
      | None => 0
      | Some bd => bd.(bd_init_mem_pages)
      end in
    let slot' := {|
      hs_slot_id := slot.(hs_slot_id);
      hs_group_id := slot.(hs_group_id);
      hs_phase := PhaseSanitized;
      hs_act_id := slot.(hs_act_id);
      hs_epoch := slot.(hs_epoch);
      hs_epoch_retired := slot.(hs_epoch_retired);
      hs_prepared := None;
      hs_active_bundle := None;
      hs_active_grants := nil;
      hs_session_key := 0;
      hs_tagged_mem := false;
      hs_start_executed := false;
      hs_new_grants_spent := false;
      hs_exec_stopped := true;
      hs_ingress_stopped := true;
      hs_pending_imports := 0;
      hs_sweep_done := true;
      hs_zeroized := true;
      hs_durable := slot.(hs_durable)
    |} in
    let res' := {|
      pr_avail_pages := Nat.add res.(pr_avail_pages) reclaimed;
      pr_staging_avail := res.(pr_staging_avail);
      pr_quarantine_pages := res.(pr_quarantine_pages);
      pr_next_act_id := res.(pr_next_act_id)
    |} in
    ok_outcome slot' res'.

Definition complete_reuse (slot : HostSlot) (res : PoolResources) : HostOutcome :=
  if negb (host_phase_eqb slot.(hs_phase) PhaseSanitized) then
    fail_outcome ErrNotSanitized slot res
  else if orb (negb slot.(hs_sweep_done)) (negb slot.(hs_zeroized)) then
    fail_outcome ErrNotSanitized slot res
  else if negb (Nat.eqb slot.(hs_pending_imports) 0) then
    fail_outcome ErrPendingImports slot res
  else
    let slot' := {|
      hs_slot_id := slot.(hs_slot_id);
      hs_group_id := slot.(hs_group_id);
      hs_phase := PhaseReusable;
      hs_act_id := slot.(hs_act_id);
      hs_epoch := slot.(hs_epoch);
      hs_epoch_retired := slot.(hs_epoch_retired);
      hs_prepared := None;
      hs_active_bundle := None;
      hs_active_grants := nil;
      hs_session_key := 0;
      hs_tagged_mem := false;
      hs_start_executed := false;
      hs_new_grants_spent := false;
      hs_exec_stopped := true;
      hs_ingress_stopped := true;
      hs_pending_imports := 0;
      hs_sweep_done := true;
      hs_zeroized := true;
      hs_durable := slot.(hs_durable)
    |} in
    ok_outcome slot' res.

(*| discharges: R-08-046, R-08-047b, R-14-013f |*)
Theorem reusable_requires_sanitized_sweep_and_zeroization :
  forall slot res out,
    complete_reuse slot res = out ->
    out.(ho_ok) = true ->
    slot.(hs_phase) = PhaseSanitized /\
    slot.(hs_sweep_done) = true /\
    slot.(hs_zeroized) = true /\
    slot.(hs_pending_imports) = 0 /\
    out.(ho_slot).(hs_phase) = PhaseReusable /\
    out.(ho_slot).(hs_active_grants) = nil /\
    out.(ho_slot).(hs_session_key) = 0 /\
    out.(ho_slot).(hs_tagged_mem) = false /\
    out.(ho_slot).(hs_epoch) = slot.(hs_epoch).
Proof.
  intros slot res out Hstep Hok.
  unfold complete_reuse in Hstep.
  destruct (hs_phase slot) eqn:Hph; simpl in Hstep;
    try (rewrite <- Hstep in Hok; discriminate Hok).
  destruct (hs_sweep_done slot) eqn:Hsw;
    destruct (hs_zeroized slot) eqn:Hz; simpl in Hstep;
    try (rewrite <- Hstep in Hok; discriminate Hok).
  destruct (Nat.eqb (hs_pending_imports slot) 0) eqn:Hpend;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  rewrite <- Hstep.
  repeat split; try reflexivity.
  exact (PS.nat_eqb_true _ _ Hpend).
Qed.

(*| discharges: R-14-013f, R-14-013g |*)
Theorem invoke_refused_once_cancelling_or_beyond :
  forall slot call,
    slot.(hs_phase) <> PhaseActive ->
    exists err, invoke_import slot call = InvokeErr err.
Proof.
  intros slot call Hnact.
  unfold invoke_import.
  destruct (hs_phase slot) eqn:Hph; simpl;
    try (eexists; reflexivity).
  exfalso. apply Hnact. reflexivity.
Qed.

(* =========================================================================
   6. Transactional Replace (R-14-013f)
   ========================================================================= *)

Definition replace_host (pol : HostPolicy) (res : PoolResources)
    (slot : HostSlot) (req : ReplaceRequest) (new_session_key : nat)
    : HostOutcome :=
  if negb (host_phase_eqb slot.(hs_phase) PhaseActive) then
    fail_outcome ErrBadPhase slot res
  else if req.(rr_uses_fs_path_authority) then
    fail_outcome ErrFsPathAuthority slot res
  else if negb req.(rr_transition_reserved) then
    fail_outcome ErrNoCapacity slot res
  else if negb req.(rr_durable_policy_ok) then
    fail_outcome ErrCommitUnauthorized slot res
  else
    match validate_bundle pol res req.(rr_candidate) with
    | Some err => fail_outcome err slot res
    | None =>
        if orb slot.(hs_epoch_retired)
               (negb (Nat.ltb slot.(hs_epoch) pol.(hp_max_epoch))) then
          fail_outcome ErrEpochExhausted slot res
        else
          match check_consent req.(rr_candidate) req.(rr_consent) with
          | Some err => fail_outcome err slot res
          | None =>
              if negb (andb (grants_subset req.(rr_new_grants)
                                           req.(rr_candidate).(bd_requested_imports))
                            (grants_subset req.(rr_new_grants) pol.(hp_import_ceiling))) then
                fail_outcome ErrOverScopedGrant slot res
              else if negb req.(rr_commit_authorized) then
                fail_outcome ErrCommitUnauthorized slot res
              else
                (* Commit point: old binding is retired before candidate activation;
                   acknowledged durable state belongs strictly to candidate bundle. *)
                let acked := {|
                  ds_bundle_digest := req.(rr_candidate).(bd_bundle_digest);
                  ds_schema_id := req.(rr_candidate).(bd_schema_id);
                  ds_state_digest := req.(rr_acked_durable_digest);
                  ds_acked := true
                |} in
                let old_pages :=
                  match slot.(hs_active_bundle) with
                  | None => 0
                  | Some old_bd => old_bd.(bd_init_mem_pages)
                  end in
                if req.(rr_post_commit_ok) then
                  let slot' := {|
                    hs_slot_id := slot.(hs_slot_id);
                    hs_group_id := slot.(hs_group_id);
                    hs_phase := PhaseActive;
                    hs_act_id := res.(pr_next_act_id);
                    hs_epoch := S slot.(hs_epoch);
                    hs_epoch_retired := false;
                    hs_prepared := None;
                    hs_active_bundle := Some req.(rr_candidate);
                    hs_active_grants := req.(rr_new_grants);
                    hs_session_key := new_session_key;
                    hs_tagged_mem := false;
                    hs_start_executed := req.(rr_candidate).(bd_has_start_fn);
                    hs_new_grants_spent := true;
                    hs_exec_stopped := false;
                    hs_ingress_stopped := false;
                    hs_pending_imports := 0;
                    hs_sweep_done := false;
                    hs_zeroized := false;
                    hs_durable := Some acked
                  |} in
                  let res' := {|
                    pr_avail_pages :=
                      Nat.sub (Nat.add res.(pr_avail_pages) old_pages)
                              req.(rr_candidate).(bd_init_mem_pages);
                    pr_staging_avail := res.(pr_staging_avail);
                    pr_quarantine_pages := res.(pr_quarantine_pages);
                    pr_next_act_id := S res.(pr_next_act_id)
                  |} in
                  ok_outcome slot' res'
                else
                  (* Post-commit failure: closed and sanitized with acknowledged durable state,
                     no automatic rollback to old binding and no partial candidate activation. *)
                  let slot' := {|
                    hs_slot_id := slot.(hs_slot_id);
                    hs_group_id := slot.(hs_group_id);
                    hs_phase := PhaseSanitized;
                    hs_act_id := res.(pr_next_act_id);
                    hs_epoch := S slot.(hs_epoch);
                    hs_epoch_retired := false;
                    hs_prepared := None;
                    hs_active_bundle := None;
                    hs_active_grants := nil;
                    hs_session_key := 0;
                    hs_tagged_mem := false;
                    hs_start_executed := false;
                    hs_new_grants_spent := false;
                    hs_exec_stopped := true;
                    hs_ingress_stopped := true;
                    hs_pending_imports := 0;
                    hs_sweep_done := true;
                    hs_zeroized := true;
                    hs_durable := Some acked
                  |} in
                  let res' := {|
                    pr_avail_pages := Nat.add res.(pr_avail_pages) old_pages;
                    pr_staging_avail := res.(pr_staging_avail);
                    pr_quarantine_pages := res.(pr_quarantine_pages);
                    pr_next_act_id := S res.(pr_next_act_id)
                  |} in
                  fail_outcome ErrPostCommitClosed slot' res'
          end
    end.

(*| discharges: R-14-013f |*)
Theorem replace_precommit_failure_preserves_old_binding :
  forall pol res slot req skey out,
    replace_host pol res slot req skey = out ->
    out.(ho_ok) = false ->
    out.(ho_err) <> Some ErrPostCommitClosed ->
    out.(ho_slot) = slot /\ out.(ho_res) = res.
Proof.
  intros pol res slot req skey out Hstep Hfail Hnpost.
  unfold replace_host in Hstep.
  destruct (host_phase_eqb (hs_phase slot) PhaseActive) eqn:Hph;
    [ | rewrite <- Hstep; split; reflexivity ].
  destruct (rr_uses_fs_path_authority req) eqn:Hfs;
    [ rewrite <- Hstep; split; reflexivity | ].
  destruct (rr_transition_reserved req) eqn:Htr;
    [ | rewrite <- Hstep; split; reflexivity ].
  destruct (rr_durable_policy_ok req) eqn:Hdp;
    [ | rewrite <- Hstep; split; reflexivity ].
  destruct (validate_bundle pol res (rr_candidate req)) as [err | ] eqn:Hval;
    [ rewrite <- Hstep; split; reflexivity | ].
  destruct (orb (hs_epoch_retired slot) (negb (Nat.ltb (hs_epoch slot) (hp_max_epoch pol)))) eqn:Hep;
    [ rewrite <- Hstep; split; reflexivity | ].
  destruct (check_consent (rr_candidate req) (rr_consent req)) as [cerr | ] eqn:Hcon;
    [ rewrite <- Hstep; split; reflexivity | ].
  destruct (andb (grants_subset (rr_new_grants req) (bd_requested_imports (rr_candidate req)))
                 (grants_subset (rr_new_grants req) (hp_import_ceiling pol))) eqn:Hgr;
    [ | rewrite <- Hstep; split; reflexivity ].
  destruct (rr_commit_authorized req) eqn:Hca;
    [ | rewrite <- Hstep; split; reflexivity ].
  destruct (rr_post_commit_ok req) eqn:Hpost.
  - rewrite <- Hstep in Hfail. discriminate Hfail.
  - rewrite <- Hstep in Hnpost. exfalso. apply Hnpost. reflexivity.
Qed.

(*| discharges: R-14-013f |*)
Theorem replace_postcommit_failure_closes_with_acked_durable_and_no_old_grants :
  forall pol res slot req skey out,
    replace_host pol res slot req skey = out ->
    out.(ho_err) = Some ErrPostCommitClosed ->
    out.(ho_slot).(hs_phase) = PhaseSanitized /\
    out.(ho_slot).(hs_active_bundle) = None /\
    out.(ho_slot).(hs_active_grants) = nil /\
    out.(ho_slot).(hs_epoch) = S slot.(hs_epoch) /\
    out.(ho_slot).(hs_zeroized) = true /\
    exists d,
      out.(ho_slot).(hs_durable) = Some d /\
      d.(ds_bundle_digest) = req.(rr_candidate).(bd_bundle_digest) /\
      d.(ds_acked) = true.
Proof.
  intros pol res slot req skey out Hstep Hpost_err.
  unfold replace_host in Hstep.
  destruct (host_phase_eqb (hs_phase slot) PhaseActive);
    [ | rewrite <- Hstep in Hpost_err; discriminate Hpost_err ].
  destruct (rr_uses_fs_path_authority req);
    [ rewrite <- Hstep in Hpost_err; discriminate Hpost_err | ].
  destruct (rr_transition_reserved req);
    [ | rewrite <- Hstep in Hpost_err; discriminate Hpost_err ].
  destruct (rr_durable_policy_ok req);
    [ | rewrite <- Hstep in Hpost_err; discriminate Hpost_err ].
  destruct (validate_bundle pol res (rr_candidate req)) as [ve | ] eqn:Hval;
    [ rewrite <- Hstep in Hpost_err; cbn [ho_err fail_outcome] in Hpost_err;
      injection Hpost_err as Hve; rewrite Hve in Hval;
      exact (False_ind _ (validate_bundle_ne_postcommit pol res (rr_candidate req) Hval)) | ].
  destruct (orb (hs_epoch_retired slot) (negb (Nat.ltb (hs_epoch slot) (hp_max_epoch pol))));
    [ rewrite <- Hstep in Hpost_err; discriminate Hpost_err | ].
  destruct (check_consent (rr_candidate req) (rr_consent req)) as [ce | ] eqn:Hcon;
    [ rewrite <- Hstep in Hpost_err; cbn [ho_err fail_outcome] in Hpost_err;
      injection Hpost_err as Hce; rewrite Hce in Hcon;
      exact (False_ind _ (check_consent_ne_postcommit (rr_candidate req) (rr_consent req) Hcon)) | ].
  destruct (andb (grants_subset (rr_new_grants req) (bd_requested_imports (rr_candidate req)))
                 (grants_subset (rr_new_grants req) (hp_import_ceiling pol)));
    [ | rewrite <- Hstep in Hpost_err; discriminate Hpost_err ].
  destruct (rr_commit_authorized req);
    [ | rewrite <- Hstep in Hpost_err; discriminate Hpost_err ].
  destruct (rr_post_commit_ok req);
    [ rewrite <- Hstep in Hpost_err; discriminate Hpost_err | ].
  rewrite <- Hstep.
  repeat split; try reflexivity.
  eexists. repeat split; reflexivity.
Qed.

(*| discharges: R-14-013f |*)
Theorem replace_commit_never_mixes_old_grants_with_candidate_execution :
  forall pol res slot req skey out,
    replace_host pol res slot req skey = out ->
    out.(ho_ok) = true ->
    out.(ho_slot).(hs_active_bundle) = Some req.(rr_candidate) /\
    out.(ho_slot).(hs_active_grants) = req.(rr_new_grants) /\
    grants_subset req.(rr_new_grants) req.(rr_candidate).(bd_requested_imports) = true /\
    out.(ho_slot).(hs_epoch) = S slot.(hs_epoch) /\
    exists d,
      out.(ho_slot).(hs_durable) = Some d /\
      d.(ds_bundle_digest) = req.(rr_candidate).(bd_bundle_digest).
Proof.
  intros pol res slot req skey out Hstep Hok.
  unfold replace_host in Hstep.
  destruct (host_phase_eqb (hs_phase slot) PhaseActive);
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (rr_uses_fs_path_authority req);
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  destruct (rr_transition_reserved req);
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (rr_durable_policy_ok req);
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (validate_bundle pol res (rr_candidate req));
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  destruct (orb (hs_epoch_retired slot) (negb (Nat.ltb (hs_epoch slot) (hp_max_epoch pol))));
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  destruct (check_consent (rr_candidate req) (rr_consent req));
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  destruct (andb (grants_subset (rr_new_grants req) (bd_requested_imports (rr_candidate req)))
                 (grants_subset (rr_new_grants req) (hp_import_ceiling pol))) eqn:Hgr;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (PS.andb_split _ _ Hgr) as [Hsub _].
  destruct (rr_commit_authorized req);
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (rr_post_commit_ok req);
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  rewrite <- Hstep.
  repeat split; try reflexivity.
  - exact Hsub.
  - eexists. split; reflexivity.
Qed.

(* =========================================================================
   7. Semantic checkpoint Restore (R-14-013f)
   ========================================================================= *)

Definition restore_checkpoint (pol : HostPolicy) (res : PoolResources)
    (slot : HostSlot) (bd : BundleDescriptor) (ckpt : SemanticCheckpoint)
    (current_grants : list nat) (new_session_key : nat)
    (used_groups : list nat) : HostOutcome :=
  if negb (slot_accepts_prepare slot.(hs_phase)) then
    fail_outcome ErrBadPhase slot res
  else if negb ckpt.(sc_hmac_valid) then
    fail_outcome ErrUnauthCheckpoint slot res
  else
    match validate_bundle pol res bd with
    | Some err => fail_outcome err slot res
    | None =>
        if negb (Nat.eqb ckpt.(sc_bundle_digest) bd.(bd_bundle_digest)) then
          fail_outcome ErrForgedDescriptor slot res
        else if negb (Nat.eqb ckpt.(sc_abi_version) pol.(hp_abi_version)) then
          fail_outcome ErrIncompatibleAbi slot res
        else if negb (Nat.eqb ckpt.(sc_profile_id) pol.(hp_profile_id)) then
          fail_outcome ErrIncompatibleGen slot res
        else if negb (Nat.eqb ckpt.(sc_schema_id) bd.(bd_schema_id)) then
          fail_outcome ErrStaleSchema slot res
        else if negb (Nat.eqb ckpt.(sc_generation) pol.(hp_generation)) then
          fail_outcome ErrIncompatibleGen slot res
        else if orb slot.(hs_epoch_retired)
                    (negb (Nat.ltb slot.(hs_epoch) pol.(hp_max_epoch))) then
          fail_outcome ErrEpochExhausted slot res
        else if PS.mem_nat slot.(hs_group_id) used_groups then
          fail_outcome ErrGroupCollision slot res
        else if negb (andb (grants_subset current_grants bd.(bd_requested_imports))
                           (grants_subset current_grants pol.(hp_import_ceiling))) then
          fail_outcome ErrOverScopedGrant slot res
        else
          let durable := {|
            ds_bundle_digest := bd.(bd_bundle_digest);
            ds_schema_id := ckpt.(sc_schema_id);
            ds_state_digest := ckpt.(sc_durable_digest);
            ds_acked := true
          |} in
          let slot' := {|
            hs_slot_id := slot.(hs_slot_id);
            hs_group_id := slot.(hs_group_id);
            hs_phase := PhaseActive;
            hs_act_id := res.(pr_next_act_id);
            hs_epoch := S slot.(hs_epoch);
            hs_epoch_retired := false;
            hs_prepared := None;
            hs_active_bundle := Some bd;
            hs_active_grants := current_grants;
            hs_session_key := new_session_key;
            hs_tagged_mem := false;
            hs_start_executed := bd.(bd_has_start_fn);
            hs_new_grants_spent := true;
            hs_exec_stopped := false;
            hs_ingress_stopped := false;
            hs_pending_imports := 0;
            hs_sweep_done := false;
            hs_zeroized := false;
            hs_durable := Some durable
          |} in
          let res' := {|
            pr_avail_pages := Nat.sub res.(pr_avail_pages) bd.(bd_init_mem_pages);
            pr_staging_avail := res.(pr_staging_avail);
            pr_quarantine_pages := res.(pr_quarantine_pages);
            pr_next_act_id := S res.(pr_next_act_id)
          |} in
          ok_outcome slot' res'
    end.

(*| discharges: R-14-013f |*)
Theorem restore_requires_auth_schema_abi_gen_and_uses_current_grants_only :
  forall pol res slot bd ckpt cur_grants skey groups out,
    restore_checkpoint pol res slot bd ckpt cur_grants skey groups = out ->
    out.(ho_ok) = true ->
    ckpt.(sc_hmac_valid) = true /\
    ckpt.(sc_schema_id) = bd.(bd_schema_id) /\
    ckpt.(sc_abi_version) = pol.(hp_abi_version) /\
    ckpt.(sc_generation) = pol.(hp_generation) /\
    out.(ho_slot).(hs_active_grants) = cur_grants /\
    out.(ho_slot).(hs_session_key) = skey /\
    out.(ho_slot).(hs_tagged_mem) = false /\
    out.(ho_slot).(hs_epoch) = S slot.(hs_epoch).
Proof.
  intros pol res slot bd ckpt cur_grants skey groups out Hstep Hok.
  unfold restore_checkpoint in Hstep.
  destruct (slot_accepts_prepare (hs_phase slot));
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (sc_hmac_valid ckpt) eqn:Hhmac;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (validate_bundle pol res bd);
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  destruct (Nat.eqb (sc_bundle_digest ckpt) (bd_bundle_digest bd));
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (Nat.eqb (sc_abi_version ckpt) (hp_abi_version pol)) eqn:Habi;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (Nat.eqb (sc_profile_id ckpt) (hp_profile_id pol));
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (Nat.eqb (sc_schema_id ckpt) (bd_schema_id bd)) eqn:Hsch;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (Nat.eqb (sc_generation ckpt) (hp_generation pol)) eqn:Hgen;
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  destruct (orb (hs_epoch_retired slot) (negb (Nat.ltb (hs_epoch slot) (hp_max_epoch pol))));
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  destruct (PS.mem_nat (hs_group_id slot) groups);
    [ rewrite <- Hstep in Hok; discriminate Hok | ].
  destruct (andb (grants_subset cur_grants (bd_requested_imports bd))
                 (grants_subset cur_grants (hp_import_ceiling pol)));
    [ | rewrite <- Hstep in Hok; discriminate Hok ].
  rewrite <- Hstep.
  repeat split; try reflexivity.
  - exact (PS.nat_eqb_true _ _ Hsch).
  - exact (PS.nat_eqb_true _ _ Habi).
  - exact (PS.nat_eqb_true _ _ Hgen).
Qed.

(* =========================================================================
   8. Concrete positive traces and refusal controls (R-05-165, R-05-166)
   ========================================================================= *)

Definition demo_policy : HostPolicy := {|
  hp_abi_version := 1;
  hp_profile_id := 10;
  hp_generation := 4;
  hp_mem_page_ceiling := 64;
  hp_table_ceiling := 256;
  hp_stack_ceiling := 128;
  hp_import_ceiling := cons 1 (cons 2 (cons 3 nil));
  hp_max_epoch := 3
|}.

Definition demo_res : PoolResources := {|
  pr_avail_pages := 64;
  pr_staging_avail := true;
  pr_quarantine_pages := 0;
  pr_next_act_id := 100
|}.

Definition demo_slot : HostSlot := {|
  hs_slot_id := 0;
  hs_group_id := 7001;
  hs_phase := PhaseFree;
  hs_act_id := 0;
  hs_epoch := 0;
  hs_epoch_retired := false;
  hs_prepared := None;
  hs_active_bundle := None;
  hs_active_grants := nil;
  hs_session_key := 0;
  hs_tagged_mem := false;
  hs_start_executed := false;
  hs_new_grants_spent := false;
  hs_exec_stopped := true;
  hs_ingress_stopped := true;
  hs_pending_imports := 0;
  hs_sweep_done := true;
  hs_zeroized := true;
  hs_durable := None
|}.

Definition mk_bundle (mod_d ast_d lbl abi init_p max_p tbl stk sch : nat)
    (grants : list nat) : BundleDescriptor :=
  let cl := Nat.add (Nat.mul 7 mod_d) (Nat.add (Nat.mul 3 ast_d) 1) in
  let bd := Nat.add (Nat.mul 11 cl)
              (Nat.add (Nat.mul 5 abi) (Nat.add sch max_p)) in
  {|
    bd_bundle_digest := bd;
    bd_closure_digest := cl;
    bd_module_digest := mod_d;
    bd_assets_digest := ast_d;
    bd_ui_label := lbl;
    bd_abi_version := abi;
    bd_core30_valid := true;
    bd_closure_valid := true;
    bd_descriptor_valid := true;
    bd_init_mem_pages := init_p;
    bd_max_mem_pages := max_p;
    bd_table_limit := tbl;
    bd_stack_limit := stk;
    bd_schema_id := sch;
    bd_requested_imports := grants;
    bd_has_start_fn := true;
    bd_uses_fs_path_authority := false
  |}.

Definition bundle_a : BundleDescriptor :=
  mk_bundle 10 20 9001 1 8 32 64 32 1 (cons 1 (cons 2 nil)).

Definition bundle_b : BundleDescriptor :=
  mk_bundle 30 40 9001 1 12 48 64 32 2 (cons 2 (cons 3 nil)).

Definition consent_a : TrustedConsent := {|
  tc_user_consented := true;
  tc_credential_ok := true;
  tc_trusted_digest := bundle_a.(bd_bundle_digest);
  tc_ui_label_shown := 9001;
  tc_nonce := 1
|}.

Definition consent_b : TrustedConsent := {|
  tc_user_consented := true;
  tc_credential_ok := true;
  tc_trusted_digest := bundle_b.(bd_bundle_digest);
  tc_ui_label_shown := 9001;
  tc_nonce := 2
|}.

(*| discharges: R-08-046, R-14-013e, R-14-013f, R-14-013g |*)
Example positive_full_lifecycle_prepare_launch_invoke_cancel_sweep_reuse :
  let p_out := prepare_host demo_policy demo_res demo_slot bundle_a in
  let l_out := launch_host demo_policy p_out.(ho_res) p_out.(ho_slot)
                 (Some consent_a) (cons 1 nil) false 555 nil in
  let call_ok := {|
    ic_handle := {| ih_act_id := l_out.(ho_slot).(hs_act_id);
                    ih_epoch := l_out.(ho_slot).(hs_epoch);
                    ih_group_id := l_out.(ho_slot).(hs_group_id);
                    ih_import_id := 1;
                    ih_scope_ok := true |};
    ic_op_id := 42;
    ic_exports_pool_cap := false;
    ic_tagged_transport := false;
    ic_reply_epoch := l_out.(ho_slot).(hs_epoch);
    ic_yield_bounded := true
  |} in
  let inv := invoke_import l_out.(ho_slot) call_ok in
  let c_out := cancel_begin l_out.(ho_slot) l_out.(ho_res) in
  let d_out := cancel_drain_step c_out.(ho_slot) c_out.(ho_res) in
  let e_out := enter_sweeping d_out.(ho_slot) d_out.(ho_res) in
  let s_out := sweep_and_zeroize e_out.(ho_slot) e_out.(ho_res) in
  let r_out := complete_reuse s_out.(ho_slot) s_out.(ho_res) in
  p_out.(ho_ok) = true /\
  p_out.(ho_slot).(hs_phase) = PhasePrepared /\
  p_out.(ho_slot).(hs_start_executed) = false /\
  p_out.(ho_slot).(hs_new_grants_spent) = false /\
  l_out.(ho_ok) = true /\
  l_out.(ho_slot).(hs_phase) = PhaseActive /\
  l_out.(ho_slot).(hs_epoch) = 1 /\
  inv = InvokeOk 1 42 /\
  r_out.(ho_ok) = true /\
  r_out.(ho_slot).(hs_phase) = PhaseReusable /\
  r_out.(ho_slot).(hs_active_grants) = nil /\
  r_out.(ho_slot).(hs_session_key) = 0 /\
  r_out.(ho_slot).(hs_zeroized) = true /\
  r_out.(ho_res).(pr_avail_pages) = 64.
Proof. repeat split; reflexivity. Qed.

(*| discharges: R-14-013f |*)
Example positive_transactional_replace_and_checkpoint_restore :
  let p_out := prepare_host demo_policy demo_res demo_slot bundle_a in
  let l_out := launch_host demo_policy p_out.(ho_res) p_out.(ho_slot)
                 (Some consent_a) (cons 1 nil) false 555 nil in
  let req_ok := {|
    rr_candidate := bundle_b;
    rr_consent := Some consent_b;
    rr_new_grants := cons 3 nil;
    rr_transition_reserved := true;
    rr_commit_authorized := true;
    rr_durable_policy_ok := true;
    rr_post_commit_ok := true;
    rr_acked_durable_digest := 777;
    rr_uses_fs_path_authority := false
  |} in
  let rep_out := replace_host demo_policy l_out.(ho_res) l_out.(ho_slot) req_ok 888 in
  let ckpt := {|
    sc_bundle_digest := bundle_b.(bd_bundle_digest);
    sc_abi_version := 1;
    sc_profile_id := 10;
    sc_schema_id := 2;
    sc_generation := 4;
    sc_hmac_valid := true;
    sc_durable_digest := 777;
    sc_embedded_old_grants := cons 1 (cons 2 nil);
    sc_embedded_tagged_mem := true;
    sc_embedded_session_key := 999
  |} in
  let rst_slot := {|
    hs_slot_id := 1; hs_group_id := 7002; hs_phase := PhaseFree;
    hs_act_id := 0; hs_epoch := 0; hs_epoch_retired := false;
    hs_prepared := None; hs_active_bundle := None; hs_active_grants := nil;
    hs_session_key := 0; hs_tagged_mem := false; hs_start_executed := false;
    hs_new_grants_spent := false; hs_exec_stopped := true;
    hs_ingress_stopped := true; hs_pending_imports := 0;
    hs_sweep_done := true; hs_zeroized := true; hs_durable := None
  |} in
  let rst_out := restore_checkpoint demo_policy demo_res rst_slot bundle_b
                   ckpt (cons 3 nil) 444 nil in
  rep_out.(ho_ok) = true /\
  rep_out.(ho_slot).(hs_active_grants) = cons 3 nil /\
  rep_out.(ho_slot).(hs_epoch) = 2 /\
  rst_out.(ho_ok) = true /\
  rst_out.(ho_slot).(hs_active_grants) = cons 3 nil /\
  rst_out.(ho_slot).(hs_session_key) = 444 /\
  rst_out.(ho_slot).(hs_tagged_mem) = false.
Proof. repeat split; reflexivity. Qed.

Definition bundle_forged_closure : BundleDescriptor := {|
  bd_bundle_digest := bundle_a.(bd_bundle_digest);
  bd_closure_digest := 999999;
  bd_module_digest := bundle_a.(bd_module_digest);
  bd_assets_digest := bundle_a.(bd_assets_digest);
  bd_ui_label := 9001; bd_abi_version := 1;
  bd_core30_valid := true; bd_closure_valid := true; bd_descriptor_valid := true;
  bd_init_mem_pages := 8; bd_max_mem_pages := 32; bd_table_limit := 64;
  bd_stack_limit := 32; bd_schema_id := 1;
  bd_requested_imports := cons 1 nil; bd_has_start_fn := true;
  bd_uses_fs_path_authority := false
|}.

Definition bundle_bad_abi : BundleDescriptor :=
  mk_bundle 10 20 9001 99 8 32 64 32 1 (cons 1 nil).

Definition bundle_oversized : BundleDescriptor :=
  mk_bundle 10 20 9001 1 8 128 64 32 1 (cons 1 nil).

Definition consent_spoof_label : TrustedConsent := {|
  tc_user_consented := true;
  tc_credential_ok := true;
  tc_trusted_digest := bundle_a.(bd_bundle_digest);
  tc_ui_label_shown := 9001;
  tc_nonce := 9
|}.

(*| discharges: R-08-047b, R-08-047c, R-14-013e, R-14-013f, R-14-013g |*)
Example negative_prepare_launch_invoke_replace_reuse_and_restore_controls :
  let p_live := prepare_host demo_policy demo_res demo_slot bundle_a in
  let l_live := launch_host demo_policy p_live.(ho_res) p_live.(ho_slot)
                  (Some consent_a) (cons 1 nil) false 555 nil in
  let live_slot := l_live.(ho_slot) in
  let live_res := l_live.(ho_res) in
  let prep_forged := prepare_host demo_policy demo_res demo_slot bundle_forged_closure in
  let prep_abi := prepare_host demo_policy demo_res demo_slot bundle_bad_abi in
  let prep_big := prepare_host demo_policy demo_res demo_slot bundle_oversized in
  let launch_spoof := launch_host demo_policy demo_res
                        (prepare_host demo_policy demo_res demo_slot bundle_b).(ho_slot)
                        (Some consent_spoof_label) (cons 2 nil) false 666 nil in
  let launch_fs := launch_host demo_policy demo_res p_live.(ho_slot)
                     (Some consent_a) (cons 1 nil) true 555 nil in
  let launch_grp := launch_host demo_policy demo_res p_live.(ho_slot)
                      (Some consent_a) (cons 1 nil) false 555 (cons 7001 nil) in
  let exhausted_slot := {|
    hs_slot_id := 0; hs_group_id := 7001; hs_phase := PhasePrepared;
    hs_act_id := 102; hs_epoch := 3; hs_epoch_retired := false;
    hs_prepared := Some bundle_a; hs_active_bundle := None; hs_active_grants := nil;
    hs_session_key := 0; hs_tagged_mem := false; hs_start_executed := false;
    hs_new_grants_spent := false; hs_exec_stopped := true;
    hs_ingress_stopped := true; hs_pending_imports := 0;
    hs_sweep_done := true; hs_zeroized := true; hs_durable := None
  |} in
  let launch_exh := launch_host demo_policy demo_res exhausted_slot
                      (Some consent_a) (cons 1 nil) false 555 nil in
  let inv_cross := invoke_import live_slot {|
    ic_handle := {| ih_act_id := live_slot.(hs_act_id);
                    ih_epoch := live_slot.(hs_epoch);
                    ih_group_id := 7999;
                    ih_import_id := 1; ih_scope_ok := true |};
    ic_op_id := 1; ic_exports_pool_cap := false; ic_tagged_transport := false;
    ic_reply_epoch := live_slot.(hs_epoch); ic_yield_bounded := true
  |} in
  let inv_stale_ep := invoke_import live_slot {|
    ic_handle := {| ih_act_id := live_slot.(hs_act_id);
                    ih_epoch := live_slot.(hs_epoch);
                    ih_group_id := live_slot.(hs_group_id);
                    ih_import_id := 1; ih_scope_ok := true |};
    ic_op_id := 1; ic_exports_pool_cap := false; ic_tagged_transport := false;
    ic_reply_epoch := 0; ic_yield_bounded := true
  |} in
  let inv_pool := invoke_import live_slot {|
    ic_handle := {| ih_act_id := live_slot.(hs_act_id);
                    ih_epoch := live_slot.(hs_epoch);
                    ih_group_id := live_slot.(hs_group_id);
                    ih_import_id := 1; ih_scope_ok := true |};
    ic_op_id := 1; ic_exports_pool_cap := true; ic_tagged_transport := false;
    ic_reply_epoch := live_slot.(hs_epoch); ic_yield_bounded := true
  |} in
  let inv_tagged := invoke_import live_slot {|
    ic_handle := {| ih_act_id := live_slot.(hs_act_id);
                    ih_epoch := live_slot.(hs_epoch);
                    ih_group_id := live_slot.(hs_group_id);
                    ih_import_id := 1; ih_scope_ok := true |};
    ic_op_id := 1; ic_exports_pool_cap := false; ic_tagged_transport := true;
    ic_reply_epoch := live_slot.(hs_epoch); ic_yield_bounded := true
  |} in
  let req_pre_fail := {|
    rr_candidate := bundle_b; rr_consent := None; rr_new_grants := cons 3 nil;
    rr_transition_reserved := true; rr_commit_authorized := true;
    rr_durable_policy_ok := true; rr_post_commit_ok := true;
    rr_acked_durable_digest := 777; rr_uses_fs_path_authority := false
  |} in
  let rep_pre := replace_host demo_policy live_res live_slot req_pre_fail 888 in
  let req_post_fail := {|
    rr_candidate := bundle_b; rr_consent := Some consent_b; rr_new_grants := cons 3 nil;
    rr_transition_reserved := true; rr_commit_authorized := true;
    rr_durable_policy_ok := true; rr_post_commit_ok := false;
    rr_acked_durable_digest := 778; rr_uses_fs_path_authority := false
  |} in
  let rep_post := replace_host demo_policy live_res live_slot req_post_fail 888 in
  let sweeping_unsanitized := {|
    hs_slot_id := 0; hs_group_id := 7001; hs_phase := PhaseSweeping;
    hs_act_id := 100; hs_epoch := 1; hs_epoch_retired := false;
    hs_prepared := None; hs_active_bundle := None; hs_active_grants := nil;
    hs_session_key := 0; hs_tagged_mem := false; hs_start_executed := false;
    hs_new_grants_spent := false; hs_exec_stopped := true;
    hs_ingress_stopped := true; hs_pending_imports := 0;
    hs_sweep_done := false; hs_zeroized := false; hs_durable := None
  |} in
  let reuse_early := complete_reuse sweeping_unsanitized demo_res in
  let bad_ckpt := {|
    sc_bundle_digest := bundle_b.(bd_bundle_digest);
    sc_abi_version := 1; sc_profile_id := 10; sc_schema_id := 99;
    sc_generation := 4; sc_hmac_valid := true; sc_durable_digest := 777;
    sc_embedded_old_grants := cons 1 nil; sc_embedded_tagged_mem := true;
    sc_embedded_session_key := 999
  |} in
  let unauth_ckpt := {|
    sc_bundle_digest := bundle_b.(bd_bundle_digest);
    sc_abi_version := 1; sc_profile_id := 10; sc_schema_id := 2;
    sc_generation := 4; sc_hmac_valid := false; sc_durable_digest := 777;
    sc_embedded_old_grants := cons 1 nil; sc_embedded_tagged_mem := true;
    sc_embedded_session_key := 999
  |} in
  let rst_stale := restore_checkpoint demo_policy demo_res demo_slot bundle_b
                     bad_ckpt (cons 3 nil) 444 nil in
  let rst_unauth := restore_checkpoint demo_policy demo_res demo_slot bundle_b
                      unauth_ckpt (cons 3 nil) 444 nil in
  prep_forged.(ho_err) = Some ErrForgedClosure /\
  prep_abi.(ho_err) = Some ErrIncompatibleAbi /\
  prep_big.(ho_err) = Some ErrOversizedReservation /\
  launch_spoof.(ho_err) = Some ErrConsentDigestMismatch /\
  launch_fs.(ho_err) = Some ErrFsPathAuthority /\
  launch_grp.(ho_err) = Some ErrGroupCollision /\
  launch_exh.(ho_err) = Some ErrEpochExhausted /\
  launch_exh.(ho_slot).(hs_epoch) = 3 /\
  launch_exh.(ho_slot).(hs_epoch_retired) = true /\
  inv_cross = InvokeErr ErrHandleScope /\
  inv_stale_ep = InvokeErr ErrEpochMismatch /\
  inv_pool = InvokeErr ErrPoolCapExport /\
  inv_tagged = InvokeErr ErrTaggedTransport /\
  rep_pre.(ho_err) = Some ErrNoConsent /\
  rep_pre.(ho_slot) = live_slot /\
  rep_post.(ho_err) = Some ErrPostCommitClosed /\
  rep_post.(ho_slot).(hs_phase) = PhaseSanitized /\
  rep_post.(ho_slot).(hs_active_grants) = nil /\
  reuse_early.(ho_err) = Some ErrNotSanitized /\
  rst_stale.(ho_err) = Some ErrStaleSchema /\
  rst_unauth.(ho_err) = Some ErrUnauthCheckpoint.
Proof. repeat split; reflexivity. Qed.

(* =========================================================================
   9. R-05-166 inhabitation witnesses (one closed Definition per Record)
   ========================================================================= *)

Definition witness_HostPolicy : HostPolicy := demo_policy.
Definition witness_BundleDescriptor : BundleDescriptor := bundle_a.
Definition witness_TrustedConsent : TrustedConsent := consent_a.
Definition witness_ImportHandle : ImportHandle := {|
  ih_act_id := 100; ih_epoch := 1; ih_group_id := 7001;
  ih_import_id := 1; ih_scope_ok := true
|}.
Definition witness_ImportCall : ImportCall := {|
  ic_handle := witness_ImportHandle;
  ic_op_id := 42;
  ic_exports_pool_cap := false;
  ic_tagged_transport := false;
  ic_reply_epoch := 1;
  ic_yield_bounded := true
|}.
Definition witness_DurableState : DurableState := {|
  ds_bundle_digest := bundle_a.(bd_bundle_digest);
  ds_schema_id := 1;
  ds_state_digest := 777;
  ds_acked := true
|}.
Definition witness_SemanticCheckpoint : SemanticCheckpoint := {|
  sc_bundle_digest := bundle_a.(bd_bundle_digest);
  sc_abi_version := 1;
  sc_profile_id := 10;
  sc_schema_id := 1;
  sc_generation := 4;
  sc_hmac_valid := true;
  sc_durable_digest := 777;
  sc_embedded_old_grants := nil;
  sc_embedded_tagged_mem := false;
  sc_embedded_session_key := 0
|}.
Definition witness_PoolResources : PoolResources := demo_res.
Definition witness_HostSlot : HostSlot := demo_slot.
Definition witness_ReplaceRequest : ReplaceRequest := {|
  rr_candidate := bundle_b;
  rr_consent := Some consent_b;
  rr_new_grants := cons 3 nil;
  rr_transition_reserved := true;
  rr_commit_authorized := true;
  rr_durable_policy_ok := true;
  rr_post_commit_ok := true;
  rr_acked_durable_digest := 777;
  rr_uses_fs_path_authority := false
|}.
Definition witness_HostOutcome : HostOutcome := ok_outcome demo_slot demo_res.

(* R-05-163, R-05-164, R-05-165, R-05-166: zero axioms, ProofSupport-only,
   all records inhabited, positive & negative controls discharged. *)
