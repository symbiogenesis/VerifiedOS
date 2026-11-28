(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   CompatibilityWorkflow.v

   Specification and non-vacuity model for Q9-i editor-driven native
   successor-generation workflow (`docs/implementation/contracts/compatibility.md`):
   - Explicit-authority 9-operation interface (ReadSourceSlice, StageEditedSource,
     SubmitBuild, AdvanceBuild, ReadDiagnostics, CancelBuild,
     SubmitSuccessorAdmission, RequestGenerationConsent, ReadSuccessorTestResult)
     with strict separation between editor, builder, admission, trusted-path,
     and next-generation test roles (R-13-027, R-13-027a, R-18-004e).
   - Same-generation native execution refusal (R-02-008, R-13-001a, R-14-013e):
     no operation executes staged native bytes, rewrites the running roster,
     installs a runtime native plugin, loads an external helper by path, or
     bypasses checking; Wasm and browser paths remain bounded and non-native.
   - All 8 R-08-046 bounded data pools (SourceIndex, EditedStaging, BuildJobs,
     PassArenas, DiagnosticsBuffer, ProofCache, CandidateClosure,
     ConsentTransfer), mandatory R-08-046 profile manifest declarations, and
     the 6-state member lifecycle (Free, Bound, Quiescing, Revoked, Sweeping,
     Reusable) where interruption never skips quiescence/sweep to Reusable.
   - Complete dependency, imported lemma, semantics, configuration, and
     assumption identity keying for ProofCache: any change invalidates reuse,
     and cache hits never bypass admission or layout/correspondence checks.
   - Epoch exhaustion without wrap, reserved diagnostics truncation marker on
     overflow, and successor test result binding to `(candidate_root, test_id,
     boot_epoch)`.
   - External roaming hardware authenticator decline (R-12-020): no CTAP
     client or foreign USB exception; only the on-die credential path is valid.

   Assumptions and non-vacuity (R-05-163, R-05-164, R-05-165, R-05-166):
   - Zero axioms (`Closed under the global context`), prelude + ProofSupport
     only, and every declared Record carries a closed `witness_<Record>`.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-02-008 R-05-163 R-05-164 R-05-165 R-05-166 R-08-046 R-12-020 R-13-001a
      R-13-027 R-13-027a R-14-013e R-18-004e
   SHA256: 3c8607bc6690ed1e73ff4a4f5017f26bd62ea55a8adf9755a6455bfd079e5260
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport.

Module PS := ProofSupport.

(* =========================================================================
   1. Small prelude helpers
   ========================================================================= *)

Definition bool_eqb (a b : bool) : bool := PS.bool_eqb a b.

Lemma andb_true_iff_local : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof. exact PS.andb_split. Qed.

Lemma nat_eqb_refl_local : forall n : nat, Nat.eqb n n = true.
Proof. exact PS.nat_eqb_refl. Qed.

Lemma nat_eqb_true_local : forall a b : nat, Nat.eqb a b = true -> a = b.
Proof. exact PS.nat_eqb_true. Qed.

Lemma nat_leb_refl_local : forall n : nat, Nat.leb n n = true.
Proof. exact PS.nat_leb_refl. Qed.

(* =========================================================================
   2. Roles, authority separation, and R-02-008 forbidden operations
   ========================================================================= *)

Record EditorAuthority : Type := {
  ea_private_source_ep : bool;
  ea_private_result_ep : bool;
  ea_holds_exec_staged : bool;
  ea_holds_signing_key : bool;
  ea_holds_mint_cap : bool;
  ea_holds_sealing_cap : bool;
  ea_holds_wiring_cap : bool;
  ea_holds_boot_select_cap : bool
}.

Record BuilderAuthority : Type := {
  ba_immutable_closure_ok : bool;
  ba_output_reservation_ok : bool;
  ba_diagnostics_ep_ok : bool;
  ba_holds_exec_staged : bool;
  ba_holds_sealing_cap : bool;
  ba_holds_wiring_cap : bool;
  ba_holds_signing_key : bool
}.

Definition valid_editor_authority (ea : EditorAuthority) : bool :=
  andb ea.(ea_private_source_ep)
    (andb ea.(ea_private_result_ep)
      (andb (negb ea.(ea_holds_exec_staged))
        (andb (negb ea.(ea_holds_signing_key))
          (andb (negb ea.(ea_holds_mint_cap))
            (andb (negb ea.(ea_holds_sealing_cap))
              (andb (negb ea.(ea_holds_wiring_cap))
                    (negb ea.(ea_holds_boot_select_cap)))))))).

Definition valid_builder_authority (ba : BuilderAuthority) : bool :=
  andb ba.(ba_immutable_closure_ok)
    (andb ba.(ba_output_reservation_ok)
      (andb ba.(ba_diagnostics_ep_ok)
        (andb (negb ba.(ba_holds_exec_staged))
          (andb (negb ba.(ba_holds_sealing_cap))
            (andb (negb ba.(ba_holds_wiring_cap))
                  (negb ba.(ba_holds_signing_key))))))).

Inductive ForbiddenNativeOp : Type :=
| ForbiddenExecStagedNative
| ForbiddenRewriteRunningRoster
| ForbiddenInstallRuntimePlugin
| ForbiddenLoadExternalByPath
| ForbiddenBypassChecking
| ForbiddenWasmNativeEscape.

(* =========================================================================
   3. Bounded data pools and 6-state member lifecycle (R-08-046)
   ========================================================================= *)

Inductive PoolKind : Type :=
| PoolSourceIndex
| PoolEditedStaging
| PoolBuildJobs
| PoolPassArenas
| PoolDiagnosticsBuffer
| PoolProofCache
| PoolCandidateClosure
| PoolConsentTransfer.

Inductive MemberLifecycle : Type :=
| Free
| Bound
| Quiescing
| Revoked
| Sweeping
| Reusable.

Definition lifecycle_eqb (a b : MemberLifecycle) : bool :=
  match a, b with
  | Free, Free => true
  | Bound, Bound => true
  | Quiescing, Quiescing => true
  | Revoked, Revoked => true
  | Sweeping, Sweeping => true
  | Reusable, Reusable => true
  | _, _ => false
  end.

Inductive LifecycleAction : Type :=
| ActBind
| ActQuiesce
| ActRevoke
| ActSweep
| ActRelease
| ActInterrupt.

Definition lifecycle_step (st : MemberLifecycle) (act : LifecycleAction)
    : option MemberLifecycle :=
  match st, act with
  | Free, ActBind => Some Bound
  | Reusable, ActBind => Some Bound
  | Bound, ActQuiesce => Some Quiescing
  | Bound, ActRevoke => Some Revoked
  | Quiescing, ActRevoke => Some Revoked
  | Revoked, ActSweep => Some Sweeping
  | Sweeping, ActRelease => Some Reusable
  | Quiescing, ActInterrupt => Some Quiescing
  | Revoked, ActInterrupt => Some Revoked
  | Sweeping, ActInterrupt => Some Sweeping
  | _, _ => None
  end.

Record PoolDecl : Type := {
  pd_kind : PoolKind;
  pd_max_capacity : nat;
  pd_has_owning_compartment : bool;
  pd_has_derivation_source : bool;
  pd_has_bind_release_caps : bool;
  pd_has_thresholds : bool;
  pd_has_release_bound : bool;
  pd_has_lifecycle : bool;
  pd_has_recovery_reserve : bool;
  pd_has_confidentiality : bool;
  pd_has_telemetry : bool;
  pd_has_restart_semantics : bool
}.

Definition pool_decl_valid (expected_kind : PoolKind) (pd : PoolDecl) : bool :=
  let kind_ok :=
    match expected_kind, pd.(pd_kind) with
    | PoolSourceIndex, PoolSourceIndex => true
    | PoolEditedStaging, PoolEditedStaging => true
    | PoolBuildJobs, PoolBuildJobs => true
    | PoolPassArenas, PoolPassArenas => true
    | PoolDiagnosticsBuffer, PoolDiagnosticsBuffer => true
    | PoolProofCache, PoolProofCache => true
    | PoolCandidateClosure, PoolCandidateClosure => true
    | PoolConsentTransfer, PoolConsentTransfer => true
    | _, _ => false
    end in
  andb kind_ok
    (andb (Nat.ltb 0 pd.(pd_max_capacity))
      (andb pd.(pd_has_owning_compartment)
        (andb pd.(pd_has_derivation_source)
          (andb pd.(pd_has_bind_release_caps)
            (andb pd.(pd_has_thresholds)
              (andb pd.(pd_has_release_bound)
                (andb pd.(pd_has_lifecycle)
                  (andb pd.(pd_has_recovery_reserve)
                    (andb pd.(pd_has_confidentiality)
                      (andb pd.(pd_has_telemetry)
                            pd.(pd_has_restart_semantics))))))))))).

Record ProfilePools : Type := {
  pp_source_index : PoolDecl;
  pp_edited_staging : PoolDecl;
  pp_build_jobs : PoolDecl;
  pp_pass_arenas : PoolDecl;
  pp_diagnostics_buffer : PoolDecl;
  pp_proof_cache : PoolDecl;
  pp_candidate_closure : PoolDecl;
  pp_consent_transfer : PoolDecl;
  pp_max_source_edges : nat;
  pp_max_source_depth : nat;
  pp_max_chunk_bytes : nat;
  pp_max_partial_objects : nat;
  pp_epoch_limit : nat;
  pp_max_diag_bytes : nat;
  pp_max_checking_steps : nat;
  pp_max_result_bytes : nat;
  pp_ordinary_borrows_comp : bool
}.

Record BuildProfile : Type := {
  bp_id : nat;
  bp_predeclared : bool;
  bp_toolchain_id : nat;
  bp_config_id : nat;
  bp_step_budget : nat;
  bp_pools : ProfilePools
}.

Definition profile_valid (bp : BuildProfile) : bool :=
  let p := bp.(bp_pools) in
  andb bp.(bp_predeclared)
    (andb (Nat.ltb 0 bp.(bp_step_budget))
      (andb (negb p.(pp_ordinary_borrows_comp))
        (andb (pool_decl_valid PoolSourceIndex p.(pp_source_index))
          (andb (pool_decl_valid PoolEditedStaging p.(pp_edited_staging))
            (andb (pool_decl_valid PoolBuildJobs p.(pp_build_jobs))
              (andb (pool_decl_valid PoolPassArenas p.(pp_pass_arenas))
                (andb (pool_decl_valid PoolDiagnosticsBuffer p.(pp_diagnostics_buffer))
                  (andb (pool_decl_valid PoolProofCache p.(pp_proof_cache))
                    (andb (pool_decl_valid PoolCandidateClosure p.(pp_candidate_closure))
                      (andb (pool_decl_valid PoolConsentTransfer p.(pp_consent_transfer))
                        (andb (Nat.ltb 0 p.(pp_max_source_edges))
                          (andb (Nat.ltb 0 p.(pp_max_source_depth))
                            (andb (Nat.ltb 0 p.(pp_max_chunk_bytes))
                              (andb (Nat.ltb 0 p.(pp_max_partial_objects))
                                (andb (Nat.ltb 0 p.(pp_epoch_limit))
                                  (andb (Nat.ltb 0 p.(pp_max_diag_bytes))
                                    (andb (Nat.ltb 0 p.(pp_max_checking_steps))
                                          (Nat.ltb 0 p.(pp_max_result_bytes))))))))))))))))))).

(* =========================================================================
   4. Complete ProofCache identity and lookup semantics
   ========================================================================= *)

Record CacheIdentity : Type := {
  ci_source_hash : nat;
  ci_dep_closure_hash : nat;
  ci_imported_lemma_hash : nat;
  ci_semantics_hash : nat;
  ci_config_hash : nat;
  ci_assumption_set_hash : nat;
  ci_profile_id : nat
}.

Definition cache_identity_eqb (a b : CacheIdentity) : bool :=
  andb (Nat.eqb a.(ci_source_hash) b.(ci_source_hash))
    (andb (Nat.eqb a.(ci_dep_closure_hash) b.(ci_dep_closure_hash))
      (andb (Nat.eqb a.(ci_imported_lemma_hash) b.(ci_imported_lemma_hash))
        (andb (Nat.eqb a.(ci_semantics_hash) b.(ci_semantics_hash))
          (andb (Nat.eqb a.(ci_config_hash) b.(ci_config_hash))
            (andb (Nat.eqb a.(ci_assumption_set_hash) b.(ci_assumption_set_hash))
                  (Nat.eqb a.(ci_profile_id) b.(ci_profile_id))))))).

Record ProofCacheEntry : Type := {
  pce_identity : CacheIdentity;
  pce_proof_digest : nat;
  pce_verified : bool
}.

Fixpoint lookup_proof_cache (id : CacheIdentity) (entries : list ProofCacheEntry)
    : option ProofCacheEntry :=
  match entries with
  | nil => None
  | cons e rest =>
      if andb e.(pce_verified) (cache_identity_eqb id e.(pce_identity))
      then Some e
      else lookup_proof_cache id rest
  end.

(* =========================================================================
   5. Workflow objects, diagnostics truncation, jobs, and state
   ========================================================================= *)

Record SourceObject : Type := {
  so_obj_id : nat;
  so_version : nat;
  so_total_bytes : nat;
  so_grant_ok : bool
}.

Record PartialStage : Type := {
  ps_slot_id : nat;
  ps_active : bool;
  ps_next_seq : nat;
  ps_declared_total : nat;
  ps_accum_bytes : nat;
  ps_running_digest : nat
}.

Record StagedObject : Type := {
  st_obj_id : nat;
  st_content_digest : nat;
  st_total_bytes : nat;
  st_executable : bool
}.

Inductive JobStage : Type :=
| JobRunning
| JobCompleted
| JobFailed
| JobCancelled.

Record BuildJob : Type := {
  jb_handle_slot : nat;
  jb_epoch : nat;
  jb_lifecycle : MemberLifecycle;
  jb_stage : JobStage;
  jb_closure_digest : nat;
  jb_profile_id : nat;
  jb_step_budget : nat;
  jb_steps_used : nat;
  jb_output_digest : nat;
  jb_output_executable : bool;
  jb_diag_records : nat;
  jb_diag_bytes : nat;
  jb_diag_truncated : bool
}.

Definition TRUNCATED_DIAG_MARKER : nat := 999999.

Record DiagRecord : Type := {
  dr_seq : nat;
  dr_bytes : nat;
  dr_is_truncation_marker : bool
}.

Record DiagnosticsView : Type := {
  dv_records : list DiagRecord;
  dv_total_bytes : nat;
  dv_truncated : bool;
  dv_marker_code : nat
}.

Record AdmissionPackage : Type := {
  ap_job_slot : nat;
  ap_job_epoch : nat;
  ap_proof_complete : bool;
  ap_checking_arena_ok : bool;
  ap_checking_steps : nat;
  ap_roster_entries : nat;
  ap_roster_valid : bool;
  ap_tal_ok : bool;
  ap_source_corr_ok : bool;
  ap_cache_hit_used : bool;
  ap_cache_id : CacheIdentity;
  ap_candidate_root : nat;
  ap_candidate_roster_hash : nat
}.

Record ConsentRequest : Type := {
  cr_candidate_root : nat;
  cr_roster_hash : nat;
  cr_user_consented : bool;
  cr_on_die_cred_ok : bool;
  cr_external_roaming_key : bool
}.

Record SuccessorTestResult : Type := {
  tr_grant_ok : bool;
  tr_candidate_root : nat;
  tr_test_id : nat;
  tr_boot_epoch : nat;
  tr_result_bytes : nat;
  tr_passed : bool
}.

Record WorkflowState : Type := {
  ws_editor_auth : EditorAuthority;
  ws_builder_auth : BuilderAuthority;
  ws_profile : BuildProfile;
  ws_running_gen_root : nat;
  ws_running_roster_hash : nat;
  ws_boot_epoch : nat;
  ws_next_job_epoch : nat;
  ws_epoch_retired : bool;
  ws_partials : list PartialStage;
  ws_staged : list StagedObject;
  ws_jobs : list BuildJob;
  ws_proof_cache : list ProofCacheEntry;
  ws_admitted_root : option nat;
  ws_admitted_roster : option nat;
  ws_consent_granted : bool;
  ws_consent_outstanding : nat;
  ws_successor_booted : bool;
  ws_last_diag_view : option DiagnosticsView;
  ws_last_test_result : option SuccessorTestResult
}.

(* =========================================================================
   6. Error taxonomy and 9 explicit-authority operations
   ========================================================================= *)

Inductive WorkflowError : Type :=
| ErrAuthorityViolation
| ErrInvalidProfile
| ErrMissingGrant
| ErrWrongObjectOrVersion
| ErrOutOfRange
| ErrIndexPoolExhausted
| ErrStagingOverBudget
| ErrStagingSequenceOrRepeat
| ErrStagingIncomplete
| ErrStagingDigestMismatch
| ErrMissingClosure
| ErrCompServiceUnavailable
| ErrJobPoolExhausted
| ErrEpochExhausted
| ErrStaleHandle
| ErrBudgetExpansion
| ErrPassArenaExhausted
| ErrJobNotActive
| ErrLifecycleInterrupted
| ErrProofIncomplete
| ErrCheckingArenaExhausted
| ErrCheckingStepsExceeded
| ErrInadmissibleRoster
| ErrTalOrCorrespondenceFailed
| ErrCacheIdentityMismatch
| ErrNoAdmittedCandidate
| ErrConsentMismatch
| ErrConsentPoolExhausted
| ErrOnDieCredentialAbsent
| ErrExternalAuthenticatorDeclined
| ErrSuccessorNotBooted
| ErrTestResultStaleOrUnbound
| ErrResultOverBudget
| ErrSameGenNativeExecution
| ErrRewriteRunningRoster
| ErrRuntimeNativePlugin
| ErrExternalPathLoad
| ErrCheckingBypass.

Inductive OpOutcome : Type :=
| OpOk (st : WorkflowState)
| OpErr (err : WorkflowError) (st : WorkflowState).

Definition outcome_ok (o : OpOutcome) : bool :=
  match o with
  | OpOk _ => true
  | OpErr _ _ => false
  end.

Definition outcome_state (o : OpOutcome) : WorkflowState :=
  match o with
  | OpOk s => s
  | OpErr _ s => s
  end.

Definition outcome_err (o : OpOutcome) : option WorkflowError :=
  match o with
  | OpOk _ => None
  | OpErr e _ => Some e
  end.

Definition check_authorities (st : WorkflowState) : bool :=
  andb (valid_editor_authority st.(ws_editor_auth))
       (valid_builder_authority st.(ws_builder_auth)).

(* Op 1: ReadSourceSlice *)
Definition op_read_source_slice
    (st : WorkflowState)
    (src : SourceObject)
    (req_obj_id req_version offset len index_objs index_edges index_depth : nat)
    : OpOutcome :=
  if negb (check_authorities st) then OpErr ErrAuthorityViolation st
  else if negb (profile_valid st.(ws_profile)) then OpErr ErrInvalidProfile st
  else if negb src.(so_grant_ok) then OpErr ErrMissingGrant st
  else if orb (negb (Nat.eqb req_obj_id src.(so_obj_id)))
              (negb (Nat.eqb req_version src.(so_version))) then
    OpErr ErrWrongObjectOrVersion st
  else if negb (Nat.leb (Nat.add offset len) src.(so_total_bytes)) then
    OpErr ErrOutOfRange st
  else
    let p := st.(ws_profile).(bp_pools) in
    if orb (negb (Nat.leb index_objs p.(pp_source_index).(pd_max_capacity)))
           (orb (negb (Nat.leb index_edges p.(pp_max_source_edges)))
                (negb (Nat.leb index_depth p.(pp_max_source_depth)))) then
      OpErr ErrIndexPoolExhausted st
    else OpOk st.

(* Op 2: StageEditedSource *)
Definition abort_partial_slot (slot : nat) (partials : list PartialStage)
    : list PartialStage :=
  PS.filter_of (fun ps => negb (Nat.eqb ps.(ps_slot_id) slot)) partials.

Definition find_partial_slot (slot : nat) (partials : list PartialStage)
    : option PartialStage :=
  match PS.filter_of (fun ps => Nat.eqb ps.(ps_slot_id) slot) partials with
  | nil => None
  | cons x _ => Some x
  end.

Definition op_stage_edited_source
    (st : WorkflowState)
    (reservation_ok : bool)
    (slot seq declared_total chunk_len chunk_digest expected_digest actual_digest : nat)
    (is_final : bool) : OpOutcome :=
  if negb (check_authorities st) then OpErr ErrAuthorityViolation st
  else if negb (profile_valid st.(ws_profile)) then OpErr ErrInvalidProfile st
  else if negb reservation_ok then OpErr ErrMissingGrant st
  else
    let p := st.(ws_profile).(bp_pools) in
    let max_bytes := p.(pp_edited_staging).(pd_max_capacity) in
    let max_chunk := p.(pp_max_chunk_bytes) in
    let max_partial := p.(pp_max_partial_objects) in
    let clean_partials := abort_partial_slot slot st.(ws_partials) in
    let aborted_st :=
      {| ws_editor_auth := st.(ws_editor_auth);
         ws_builder_auth := st.(ws_builder_auth);
         ws_profile := st.(ws_profile);
         ws_running_gen_root := st.(ws_running_gen_root);
         ws_running_roster_hash := st.(ws_running_roster_hash);
         ws_boot_epoch := st.(ws_boot_epoch);
         ws_next_job_epoch := st.(ws_next_job_epoch);
         ws_epoch_retired := st.(ws_epoch_retired);
         ws_partials := clean_partials;
         ws_staged := st.(ws_staged);
         ws_jobs := st.(ws_jobs);
         ws_proof_cache := st.(ws_proof_cache);
         ws_admitted_root := st.(ws_admitted_root);
         ws_admitted_roster := st.(ws_admitted_roster);
         ws_consent_granted := st.(ws_consent_granted);
         ws_consent_outstanding := st.(ws_consent_outstanding);
         ws_successor_booted := st.(ws_successor_booted);
         ws_last_diag_view := st.(ws_last_diag_view);
         ws_last_test_result := st.(ws_last_test_result) |} in
    if orb (negb (Nat.leb declared_total max_bytes))
           (negb (Nat.leb chunk_len max_chunk)) then
      OpErr ErrStagingOverBudget aborted_st
    else
      match find_partial_slot slot st.(ws_partials) with
      | None =>
          if negb (Nat.ltb (PS.count_of st.(ws_partials)) max_partial) then
            OpErr ErrStagingOverBudget aborted_st
          else if orb (negb (Nat.eqb seq 0))
                      (negb (Nat.leb chunk_len declared_total)) then
            OpErr ErrStagingSequenceOrRepeat aborted_st
          else
            let next_digest := Nat.add chunk_digest declared_total in
            if is_final then
              if negb (Nat.eqb chunk_len declared_total) then
                OpErr ErrStagingIncomplete aborted_st
              else if negb (Nat.eqb actual_digest expected_digest) then
                OpErr ErrStagingDigestMismatch aborted_st
              else
                let obj := {| st_obj_id := slot;
                              st_content_digest := actual_digest;
                              st_total_bytes := declared_total;
                              st_executable := false |} in
                OpOk {| ws_editor_auth := st.(ws_editor_auth);
                        ws_builder_auth := st.(ws_builder_auth);
                        ws_profile := st.(ws_profile);
                        ws_running_gen_root := st.(ws_running_gen_root);
                        ws_running_roster_hash := st.(ws_running_roster_hash);
                        ws_boot_epoch := st.(ws_boot_epoch);
                        ws_next_job_epoch := st.(ws_next_job_epoch);
                        ws_epoch_retired := st.(ws_epoch_retired);
                        ws_partials := clean_partials;
                        ws_staged := cons obj st.(ws_staged);
                        ws_jobs := st.(ws_jobs);
                        ws_proof_cache := st.(ws_proof_cache);
                        ws_admitted_root := st.(ws_admitted_root);
                        ws_admitted_roster := st.(ws_admitted_roster);
                        ws_consent_granted := st.(ws_consent_granted);
                        ws_consent_outstanding := st.(ws_consent_outstanding);
                        ws_successor_booted := st.(ws_successor_booted);
                        ws_last_diag_view := st.(ws_last_diag_view);
                        ws_last_test_result := st.(ws_last_test_result) |}
            else
              let ps := {| ps_slot_id := slot;
                           ps_active := true;
                           ps_next_seq := 1;
                           ps_declared_total := declared_total;
                           ps_accum_bytes := chunk_len;
                           ps_running_digest := next_digest |} in
              OpOk {| ws_editor_auth := st.(ws_editor_auth);
                      ws_builder_auth := st.(ws_builder_auth);
                      ws_profile := st.(ws_profile);
                      ws_running_gen_root := st.(ws_running_gen_root);
                      ws_running_roster_hash := st.(ws_running_roster_hash);
                      ws_boot_epoch := st.(ws_boot_epoch);
                      ws_next_job_epoch := st.(ws_next_job_epoch);
                      ws_epoch_retired := st.(ws_epoch_retired);
                      ws_partials := cons ps clean_partials;
                      ws_staged := st.(ws_staged);
                      ws_jobs := st.(ws_jobs);
                      ws_proof_cache := st.(ws_proof_cache);
                      ws_admitted_root := st.(ws_admitted_root);
                      ws_admitted_roster := st.(ws_admitted_roster);
                      ws_consent_granted := st.(ws_consent_granted);
                      ws_consent_outstanding := st.(ws_consent_outstanding);
                      ws_successor_booted := st.(ws_successor_booted);
                      ws_last_diag_view := st.(ws_last_diag_view);
                      ws_last_test_result := st.(ws_last_test_result) |}
      | Some cur =>
          let new_accum := Nat.add cur.(ps_accum_bytes) chunk_len in
          if orb (negb (Nat.eqb seq cur.(ps_next_seq)))
                 (orb (negb (Nat.eqb declared_total cur.(ps_declared_total)))
                      (negb (Nat.leb new_accum cur.(ps_declared_total)))) then
            OpErr ErrStagingSequenceOrRepeat aborted_st
          else if is_final then
            if negb (Nat.eqb new_accum cur.(ps_declared_total)) then
              OpErr ErrStagingIncomplete aborted_st
            else if negb (Nat.eqb actual_digest expected_digest) then
              OpErr ErrStagingDigestMismatch aborted_st
            else
              let obj := {| st_obj_id := slot;
                            st_content_digest := actual_digest;
                            st_total_bytes := cur.(ps_declared_total);
                            st_executable := false |} in
              OpOk {| ws_editor_auth := st.(ws_editor_auth);
                      ws_builder_auth := st.(ws_builder_auth);
                      ws_profile := st.(ws_profile);
                      ws_running_gen_root := st.(ws_running_gen_root);
                      ws_running_roster_hash := st.(ws_running_roster_hash);
                      ws_boot_epoch := st.(ws_boot_epoch);
                      ws_next_job_epoch := st.(ws_next_job_epoch);
                      ws_epoch_retired := st.(ws_epoch_retired);
                      ws_partials := clean_partials;
                      ws_staged := cons obj st.(ws_staged);
                      ws_jobs := st.(ws_jobs);
                      ws_proof_cache := st.(ws_proof_cache);
                      ws_admitted_root := st.(ws_admitted_root);
                      ws_admitted_roster := st.(ws_admitted_roster);
                      ws_consent_granted := st.(ws_consent_granted);
                      ws_consent_outstanding := st.(ws_consent_outstanding);
                      ws_successor_booted := st.(ws_successor_booted);
                      ws_last_diag_view := st.(ws_last_diag_view);
                      ws_last_test_result := st.(ws_last_test_result) |}
          else
            let ps := {| ps_slot_id := slot;
                         ps_active := true;
                         ps_next_seq := S cur.(ps_next_seq);
                         ps_declared_total := cur.(ps_declared_total);
                         ps_accum_bytes := new_accum;
                         ps_running_digest := Nat.add cur.(ps_running_digest) chunk_digest |} in
            OpOk {| ws_editor_auth := st.(ws_editor_auth);
                    ws_builder_auth := st.(ws_builder_auth);
                    ws_profile := st.(ws_profile);
                    ws_running_gen_root := st.(ws_running_gen_root);
                    ws_running_roster_hash := st.(ws_running_roster_hash);
                    ws_boot_epoch := st.(ws_boot_epoch);
                    ws_next_job_epoch := st.(ws_next_job_epoch);
                    ws_epoch_retired := st.(ws_epoch_retired);
                    ws_partials := cons ps clean_partials;
                    ws_staged := st.(ws_staged);
                    ws_jobs := st.(ws_jobs);
                    ws_proof_cache := st.(ws_proof_cache);
                    ws_admitted_root := st.(ws_admitted_root);
                    ws_admitted_roster := st.(ws_admitted_roster);
                    ws_consent_granted := st.(ws_consent_granted);
                    ws_consent_outstanding := st.(ws_consent_outstanding);
                    ws_successor_booted := st.(ws_successor_booted);
                    ws_last_diag_view := st.(ws_last_diag_view);
                    ws_last_test_result := st.(ws_last_test_result) |}
      end.

(* Op 3: SubmitBuild *)
Definition live_job_count (jobs : list BuildJob) : nat :=
  PS.count_where (fun j => negb (lifecycle_eqb j.(jb_lifecycle) Reusable)) jobs.

Definition op_submit_build
    (st : WorkflowState)
    (closure_ok comp_service_ep_ok : bool)
    (closure_digest closure_objs closure_edges closure_depth toolchain_id config_id : nat)
    (req_profile : BuildProfile) : OpOutcome :=
  if negb (check_authorities st) then OpErr ErrAuthorityViolation st
  else if negb closure_ok then OpErr ErrMissingClosure st
  else if negb comp_service_ep_ok then OpErr ErrCompServiceUnavailable st
  else if orb (negb (profile_valid req_profile))
              (orb (negb (Nat.eqb req_profile.(bp_id) st.(ws_profile).(bp_id)))
                   (orb (negb (Nat.eqb toolchain_id req_profile.(bp_toolchain_id)))
                        (negb (Nat.eqb config_id req_profile.(bp_config_id))))) then
    OpErr ErrInvalidProfile st
  else
    let p := req_profile.(bp_pools) in
    if orb (negb (Nat.leb closure_objs p.(pp_source_index).(pd_max_capacity)))
           (orb (negb (Nat.leb closure_edges p.(pp_max_source_edges)))
                (negb (Nat.leb closure_depth p.(pp_max_source_depth)))) then
      OpErr ErrIndexPoolExhausted st
    else if orb st.(ws_epoch_retired)
                (negb (Nat.ltb st.(ws_next_job_epoch) p.(pp_epoch_limit))) then
      let retired_st :=
        {| ws_editor_auth := st.(ws_editor_auth);
           ws_builder_auth := st.(ws_builder_auth);
           ws_profile := st.(ws_profile);
           ws_running_gen_root := st.(ws_running_gen_root);
           ws_running_roster_hash := st.(ws_running_roster_hash);
           ws_boot_epoch := st.(ws_boot_epoch);
           ws_next_job_epoch := st.(ws_next_job_epoch);
           ws_epoch_retired := true;
           ws_partials := st.(ws_partials);
           ws_staged := st.(ws_staged);
           ws_jobs := st.(ws_jobs);
           ws_proof_cache := st.(ws_proof_cache);
           ws_admitted_root := st.(ws_admitted_root);
           ws_admitted_roster := st.(ws_admitted_roster);
           ws_consent_granted := st.(ws_consent_granted);
           ws_consent_outstanding := st.(ws_consent_outstanding);
           ws_successor_booted := st.(ws_successor_booted);
           ws_last_diag_view := st.(ws_last_diag_view);
           ws_last_test_result := st.(ws_last_test_result) |} in
      OpErr ErrEpochExhausted retired_st
    else if negb (Nat.ltb (live_job_count st.(ws_jobs))
                          p.(pp_build_jobs).(pd_max_capacity)) then
      OpErr ErrJobPoolExhausted st
    else
      let slot := PS.count_of st.(ws_jobs) in
      let job := {| jb_handle_slot := slot;
                    jb_epoch := st.(ws_next_job_epoch);
                    jb_lifecycle := Bound;
                    jb_stage := JobRunning;
                    jb_closure_digest := closure_digest;
                    jb_profile_id := req_profile.(bp_id);
                    jb_step_budget := req_profile.(bp_step_budget);
                    jb_steps_used := 0;
                    jb_output_digest := 0;
                    jb_output_executable := false;
                    jb_diag_records := 0;
                    jb_diag_bytes := 0;
                    jb_diag_truncated := false |} in
      OpOk {| ws_editor_auth := st.(ws_editor_auth);
              ws_builder_auth := st.(ws_builder_auth);
              ws_profile := st.(ws_profile);
              ws_running_gen_root := st.(ws_running_gen_root);
              ws_running_roster_hash := st.(ws_running_roster_hash);
              ws_boot_epoch := st.(ws_boot_epoch);
              ws_next_job_epoch := S st.(ws_next_job_epoch);
              ws_epoch_retired := false;
              ws_partials := st.(ws_partials);
              ws_staged := st.(ws_staged);
              ws_jobs := app st.(ws_jobs) (cons job nil);
              ws_proof_cache := st.(ws_proof_cache);
              ws_admitted_root := st.(ws_admitted_root);
              ws_admitted_roster := st.(ws_admitted_roster);
              ws_consent_granted := st.(ws_consent_granted);
              ws_consent_outstanding := st.(ws_consent_outstanding);
              ws_successor_booted := st.(ws_successor_booted);
              ws_last_diag_view := st.(ws_last_diag_view);
              ws_last_test_result := st.(ws_last_test_result) |}.

(* Helpers for job lookup & replacement *)
Fixpoint find_job_by_slot (slot : nat) (jobs : list BuildJob) : option BuildJob :=
  match jobs with
  | nil => None
  | cons j rest => if Nat.eqb j.(jb_handle_slot) slot then Some j else find_job_by_slot slot rest
  end.

Fixpoint replace_job_by_slot (slot : nat) (nj : BuildJob) (jobs : list BuildJob)
    : list BuildJob :=
  match jobs with
  | nil => nil
  | cons j rest =>
      if Nat.eqb j.(jb_handle_slot) slot then cons nj rest
      else cons j (replace_job_by_slot slot nj rest)
  end.

(* Op 4: AdvanceBuild *)
Definition op_advance_build
    (st : WorkflowState)
    (slot epoch steps_req workset_bytes output_digest diag_recs diag_bytes : nat)
    (finish_build : bool) : OpOutcome :=
  if negb (check_authorities st) then OpErr ErrAuthorityViolation st
  else
    match find_job_by_slot slot st.(ws_jobs) with
    | None => OpErr ErrStaleHandle st
    | Some j =>
        if negb (Nat.eqb j.(jb_epoch) epoch) then OpErr ErrStaleHandle st
        else if negb (lifecycle_eqb j.(jb_lifecycle) Bound) then OpErr ErrJobNotActive st
        else
          let running := match j.(jb_stage) with JobRunning => true | _ => false end in
          if negb running then OpErr ErrJobNotActive st
          else if negb (Nat.leb (Nat.add j.(jb_steps_used) steps_req) j.(jb_step_budget)) then
            OpErr ErrBudgetExpansion st
          else
            let p := st.(ws_profile).(bp_pools) in
            if negb (Nat.leb workset_bytes p.(pp_pass_arenas).(pd_max_capacity)) then
              let failed_j :=
                {| jb_handle_slot := j.(jb_handle_slot);
                   jb_epoch := j.(jb_epoch);
                   jb_lifecycle := Bound;
                   jb_stage := JobFailed;
                   jb_closure_digest := j.(jb_closure_digest);
                   jb_profile_id := j.(jb_profile_id);
                   jb_step_budget := j.(jb_step_budget);
                   jb_steps_used := j.(jb_steps_used);
                   jb_output_digest := 0;
                   jb_output_executable := false;
                   jb_diag_records := j.(jb_diag_records);
                   jb_diag_bytes := j.(jb_diag_bytes);
                   jb_diag_truncated := j.(jb_diag_truncated) |} in
              OpErr ErrPassArenaExhausted
                {| ws_editor_auth := st.(ws_editor_auth);
                   ws_builder_auth := st.(ws_builder_auth);
                   ws_profile := st.(ws_profile);
                   ws_running_gen_root := st.(ws_running_gen_root);
                   ws_running_roster_hash := st.(ws_running_roster_hash);
                   ws_boot_epoch := st.(ws_boot_epoch);
                   ws_next_job_epoch := st.(ws_next_job_epoch);
                   ws_epoch_retired := st.(ws_epoch_retired);
                   ws_partials := st.(ws_partials);
                   ws_staged := st.(ws_staged);
                   ws_jobs := replace_job_by_slot slot failed_j st.(ws_jobs);
                   ws_proof_cache := st.(ws_proof_cache);
                   ws_admitted_root := st.(ws_admitted_root);
                   ws_admitted_roster := st.(ws_admitted_roster);
                   ws_consent_granted := st.(ws_consent_granted);
                   ws_consent_outstanding := st.(ws_consent_outstanding);
                   ws_successor_booted := st.(ws_successor_booted);
                   ws_last_diag_view := st.(ws_last_diag_view);
                   ws_last_test_result := st.(ws_last_test_result) |}
            else
              let new_recs := Nat.add j.(jb_diag_records) diag_recs in
              let new_bytes := Nat.add j.(jb_diag_bytes) diag_bytes in
              let max_recs := p.(pp_diagnostics_buffer).(pd_max_capacity) in
              let max_dbytes := p.(pp_max_diag_bytes) in
              let over := orb (negb (Nat.leb new_recs max_recs))
                              (negb (Nat.leb new_bytes max_dbytes)) in
              let capped_recs := Nat.min new_recs max_recs in
              let capped_bytes := Nat.min new_bytes max_dbytes in
              let next_j :=
                {| jb_handle_slot := j.(jb_handle_slot);
                   jb_epoch := j.(jb_epoch);
                   jb_lifecycle := Bound;
                   jb_stage := if finish_build then JobCompleted else JobRunning;
                   jb_closure_digest := j.(jb_closure_digest);
                   jb_profile_id := j.(jb_profile_id);
                   jb_step_budget := j.(jb_step_budget);
                   jb_steps_used := Nat.add j.(jb_steps_used) steps_req;
                   jb_output_digest := if finish_build then output_digest else 0;
                   jb_output_executable := false;
                   jb_diag_records := capped_recs;
                   jb_diag_bytes := capped_bytes;
                   jb_diag_truncated := orb j.(jb_diag_truncated) over |} in
              OpOk {| ws_editor_auth := st.(ws_editor_auth);
                      ws_builder_auth := st.(ws_builder_auth);
                      ws_profile := st.(ws_profile);
                      ws_running_gen_root := st.(ws_running_gen_root);
                      ws_running_roster_hash := st.(ws_running_roster_hash);
                      ws_boot_epoch := st.(ws_boot_epoch);
                      ws_next_job_epoch := st.(ws_next_job_epoch);
                      ws_epoch_retired := st.(ws_epoch_retired);
                      ws_partials := st.(ws_partials);
                      ws_staged := st.(ws_staged);
                      ws_jobs := replace_job_by_slot slot next_j st.(ws_jobs);
                      ws_proof_cache := st.(ws_proof_cache);
                      ws_admitted_root := st.(ws_admitted_root);
                      ws_admitted_roster := st.(ws_admitted_roster);
                      ws_consent_granted := st.(ws_consent_granted);
                      ws_consent_outstanding := st.(ws_consent_outstanding);
                      ws_successor_booted := st.(ws_successor_booted);
                      ws_last_diag_view := st.(ws_last_diag_view);
                      ws_last_test_result := st.(ws_last_test_result) |}
    end.

(* Op 5: ReadDiagnostics *)
Definition op_read_diagnostics
    (st : WorkflowState)
    (slot epoch : nat)
    (result_ep_ok : bool)
    (req_records req_bytes : nat) : OpOutcome :=
  if negb (check_authorities st) then OpErr ErrAuthorityViolation st
  else if negb result_ep_ok then OpErr ErrMissingGrant st
  else
    match find_job_by_slot slot st.(ws_jobs) with
    | None => OpErr ErrStaleHandle st
    | Some j =>
        if negb (Nat.eqb j.(jb_epoch) epoch) then OpErr ErrStaleHandle st
        else
          let p := st.(ws_profile).(bp_pools) in
          let cap_recs := p.(pp_diagnostics_buffer).(pd_max_capacity) in
          let cap_bytes := p.(pp_max_diag_bytes) in
          let over_req := orb (negb (Nat.leb req_records cap_recs))
                              (negb (Nat.leb req_bytes cap_bytes)) in
          let trunc := orb j.(jb_diag_truncated) over_req in
          let ret_recs := Nat.min j.(jb_diag_records) (Nat.min req_records cap_recs) in
          let ret_bytes := Nat.min j.(jb_diag_bytes) (Nat.min req_bytes cap_bytes) in
          let marker := if trunc then TRUNCATED_DIAG_MARKER else 0 in
          let rec_list :=
            if trunc
            then cons {| dr_seq := ret_recs; dr_bytes := 0; dr_is_truncation_marker := true |} nil
            else cons {| dr_seq := 0; dr_bytes := ret_bytes; dr_is_truncation_marker := false |} nil in
          let view := {| dv_records := rec_list;
                         dv_total_bytes := ret_bytes;
                         dv_truncated := trunc;
                         dv_marker_code := marker |} in
          OpOk {| ws_editor_auth := st.(ws_editor_auth);
                  ws_builder_auth := st.(ws_builder_auth);
                  ws_profile := st.(ws_profile);
                  ws_running_gen_root := st.(ws_running_gen_root);
                  ws_running_roster_hash := st.(ws_running_roster_hash);
                  ws_boot_epoch := st.(ws_boot_epoch);
                  ws_next_job_epoch := st.(ws_next_job_epoch);
                  ws_epoch_retired := st.(ws_epoch_retired);
                  ws_partials := st.(ws_partials);
                  ws_staged := st.(ws_staged);
                  ws_jobs := st.(ws_jobs);
                  ws_proof_cache := st.(ws_proof_cache);
                  ws_admitted_root := st.(ws_admitted_root);
                  ws_admitted_roster := st.(ws_admitted_roster);
                  ws_consent_granted := st.(ws_consent_granted);
                  ws_consent_outstanding := st.(ws_consent_outstanding);
                  ws_successor_booted := st.(ws_successor_booted);
                  ws_last_diag_view := Some view;
                  ws_last_test_result := st.(ws_last_test_result) |}
    end.

(* Op 6: CancelBuild *)
Definition op_cancel_build
    (st : WorkflowState)
    (slot epoch : nat)
    (cancel_cap_ok interrupt_mid_sweep : bool) : OpOutcome :=
  if negb (check_authorities st) then OpErr ErrAuthorityViolation st
  else if negb cancel_cap_ok then OpErr ErrMissingGrant st
  else
    match find_job_by_slot slot st.(ws_jobs) with
    | None => OpErr ErrStaleHandle st
    | Some j =>
        if negb (Nat.eqb j.(jb_epoch) epoch) then OpErr ErrStaleHandle st
        else
          let s1 := lifecycle_step j.(jb_lifecycle) ActQuiesce in
          let s2 := match s1 with Some x => lifecycle_step x ActRevoke | None => None end in
          let s3 := match s2 with Some x => lifecycle_step x ActSweep | None => None end in
          match s3 with
          | None => OpErr ErrJobNotActive st
          | Some sweeping =>
              if interrupt_mid_sweep then
                let interrupted := match lifecycle_step sweeping ActInterrupt with
                                   | Some x => x
                                   | None => Sweeping
                                   end in
                let nj := {| jb_handle_slot := j.(jb_handle_slot);
                             jb_epoch := j.(jb_epoch);
                             jb_lifecycle := interrupted;
                             jb_stage := JobCancelled;
                             jb_closure_digest := j.(jb_closure_digest);
                             jb_profile_id := j.(jb_profile_id);
                             jb_step_budget := j.(jb_step_budget);
                             jb_steps_used := j.(jb_steps_used);
                             jb_output_digest := 0;
                             jb_output_executable := false;
                             jb_diag_records := j.(jb_diag_records);
                             jb_diag_bytes := j.(jb_diag_bytes);
                             jb_diag_truncated := j.(jb_diag_truncated) |} in
                OpErr ErrLifecycleInterrupted
                  {| ws_editor_auth := st.(ws_editor_auth);
                     ws_builder_auth := st.(ws_builder_auth);
                     ws_profile := st.(ws_profile);
                     ws_running_gen_root := st.(ws_running_gen_root);
                     ws_running_roster_hash := st.(ws_running_roster_hash);
                     ws_boot_epoch := st.(ws_boot_epoch);
                     ws_next_job_epoch := st.(ws_next_job_epoch);
                     ws_epoch_retired := st.(ws_epoch_retired);
                     ws_partials := st.(ws_partials);
                     ws_staged := st.(ws_staged);
                     ws_jobs := replace_job_by_slot slot nj st.(ws_jobs);
                     ws_proof_cache := st.(ws_proof_cache);
                     ws_admitted_root := st.(ws_admitted_root);
                     ws_admitted_roster := st.(ws_admitted_roster);
                     ws_consent_granted := st.(ws_consent_granted);
                     ws_consent_outstanding := st.(ws_consent_outstanding);
                     ws_successor_booted := st.(ws_successor_booted);
                     ws_last_diag_view := st.(ws_last_diag_view);
                     ws_last_test_result := st.(ws_last_test_result) |}
              else
                let final_lc := match lifecycle_step sweeping ActRelease with
                                | Some x => x
                                | None => Sweeping
                                end in
                let nj := {| jb_handle_slot := j.(jb_handle_slot);
                             jb_epoch := j.(jb_epoch);
                             jb_lifecycle := final_lc;
                             jb_stage := JobCancelled;
                             jb_closure_digest := j.(jb_closure_digest);
                             jb_profile_id := j.(jb_profile_id);
                             jb_step_budget := j.(jb_step_budget);
                             jb_steps_used := j.(jb_steps_used);
                             jb_output_digest := 0;
                             jb_output_executable := false;
                             jb_diag_records := j.(jb_diag_records);
                             jb_diag_bytes := j.(jb_diag_bytes);
                             jb_diag_truncated := j.(jb_diag_truncated) |} in
                OpOk {| ws_editor_auth := st.(ws_editor_auth);
                        ws_builder_auth := st.(ws_builder_auth);
                        ws_profile := st.(ws_profile);
                        ws_running_gen_root := st.(ws_running_gen_root);
                        ws_running_roster_hash := st.(ws_running_roster_hash);
                        ws_boot_epoch := st.(ws_boot_epoch);
                        ws_next_job_epoch := st.(ws_next_job_epoch);
                        ws_epoch_retired := st.(ws_epoch_retired);
                        ws_partials := st.(ws_partials);
                        ws_staged := st.(ws_staged);
                        ws_jobs := replace_job_by_slot slot nj st.(ws_jobs);
                        ws_proof_cache := st.(ws_proof_cache);
                        ws_admitted_root := st.(ws_admitted_root);
                        ws_admitted_roster := st.(ws_admitted_roster);
                        ws_consent_granted := st.(ws_consent_granted);
                        ws_consent_outstanding := st.(ws_consent_outstanding);
                        ws_successor_booted := st.(ws_successor_booted);
                        ws_last_diag_view := st.(ws_last_diag_view);
                        ws_last_test_result := st.(ws_last_test_result) |}
          end
    end.

(* Op 7: SubmitSuccessorAdmission *)
Definition op_submit_successor_admission
    (st : WorkflowState)
    (pkg : AdmissionPackage) : OpOutcome :=
  if negb (check_authorities st) then OpErr ErrAuthorityViolation st
  else
    match find_job_by_slot pkg.(ap_job_slot) st.(ws_jobs) with
    | None => OpErr ErrStaleHandle st
    | Some j =>
        if negb (Nat.eqb j.(jb_epoch) pkg.(ap_job_epoch)) then OpErr ErrStaleHandle st
        else
          let completed := match j.(jb_stage) with JobCompleted => true | _ => false end in
          if negb completed then OpErr ErrJobNotActive st
          else if negb pkg.(ap_proof_complete) then OpErr ErrProofIncomplete st
          else if negb pkg.(ap_checking_arena_ok) then OpErr ErrCheckingArenaExhausted st
          else
            let p := st.(ws_profile).(bp_pools) in
            if orb (negb (Nat.leb pkg.(ap_roster_entries)
                                   p.(pp_candidate_closure).(pd_max_capacity)))
                   (negb (Nat.leb pkg.(ap_checking_steps) p.(pp_max_checking_steps))) then
              OpErr ErrCheckingStepsExceeded st
            else if negb pkg.(ap_roster_valid) then OpErr ErrInadmissibleRoster st
            else if orb (negb pkg.(ap_tal_ok)) (negb pkg.(ap_source_corr_ok)) then
              OpErr ErrTalOrCorrespondenceFailed st
            else
              let cache_ok :=
                if pkg.(ap_cache_hit_used)
                then PS.is_some (lookup_proof_cache pkg.(ap_cache_id) st.(ws_proof_cache))
                else true in
              if negb cache_ok then OpErr ErrCacheIdentityMismatch st
              else
                let new_entry := {| pce_identity := pkg.(ap_cache_id);
                                    pce_proof_digest := pkg.(ap_candidate_root);
                                    pce_verified := true |} in
                let max_cache := p.(pp_proof_cache).(pd_max_capacity) in
                let next_cache :=
                  PS.take_of max_cache (cons new_entry st.(ws_proof_cache)) in
                OpOk {| ws_editor_auth := st.(ws_editor_auth);
                        ws_builder_auth := st.(ws_builder_auth);
                        ws_profile := st.(ws_profile);
                        ws_running_gen_root := st.(ws_running_gen_root);
                        ws_running_roster_hash := st.(ws_running_roster_hash);
                        ws_boot_epoch := st.(ws_boot_epoch);
                        ws_next_job_epoch := st.(ws_next_job_epoch);
                        ws_epoch_retired := st.(ws_epoch_retired);
                        ws_partials := st.(ws_partials);
                        ws_staged := st.(ws_staged);
                        ws_jobs := st.(ws_jobs);
                        ws_proof_cache := next_cache;
                        ws_admitted_root := Some pkg.(ap_candidate_root);
                        ws_admitted_roster := Some pkg.(ap_candidate_roster_hash);
                        ws_consent_granted := false;
                        ws_consent_outstanding := st.(ws_consent_outstanding);
                        ws_successor_booted := false;
                        ws_last_diag_view := st.(ws_last_diag_view);
                        ws_last_test_result := st.(ws_last_test_result) |}
    end.

(* Op 8: RequestGenerationConsent (with R-12-020 external authenticator decline) *)
Definition op_request_generation_consent
    (st : WorkflowState)
    (cr : ConsentRequest) : OpOutcome :=
  if cr.(cr_external_roaming_key) then
    OpErr ErrExternalAuthenticatorDeclined st
  else if negb (check_authorities st) then
    OpErr ErrAuthorityViolation st
  else
    let max_consent := st.(ws_profile).(bp_pools).(pp_consent_transfer).(pd_max_capacity) in
    if negb (Nat.ltb st.(ws_consent_outstanding) max_consent) then
      OpErr ErrConsentPoolExhausted st
    else
      match st.(ws_admitted_root), st.(ws_admitted_roster) with
      | Some adm_root, Some adm_roster =>
          if orb (negb (Nat.eqb cr.(cr_candidate_root) adm_root))
                 (negb (Nat.eqb cr.(cr_roster_hash) adm_roster)) then
            OpErr ErrConsentMismatch st
          else if negb cr.(cr_on_die_cred_ok) then
            OpErr ErrOnDieCredentialAbsent st
          else if negb cr.(cr_user_consented) then
            OpErr ErrConsentMismatch st
          else
            OpOk {| ws_editor_auth := st.(ws_editor_auth);
                    ws_builder_auth := st.(ws_builder_auth);
                    ws_profile := st.(ws_profile);
                    ws_running_gen_root := st.(ws_running_gen_root);
                    ws_running_roster_hash := st.(ws_running_roster_hash);
                    ws_boot_epoch := st.(ws_boot_epoch);
                    ws_next_job_epoch := st.(ws_next_job_epoch);
                    ws_epoch_retired := st.(ws_epoch_retired);
                    ws_partials := st.(ws_partials);
                    ws_staged := st.(ws_staged);
                    ws_jobs := st.(ws_jobs);
                    ws_proof_cache := st.(ws_proof_cache);
                    ws_admitted_root := st.(ws_admitted_root);
                    ws_admitted_roster := st.(ws_admitted_roster);
                    ws_consent_granted := true;
                    ws_consent_outstanding := S st.(ws_consent_outstanding);
                    ws_successor_booted := st.(ws_successor_booted);
                    ws_last_diag_view := st.(ws_last_diag_view);
                    ws_last_test_result := st.(ws_last_test_result) |}
      | _, _ => OpErr ErrNoAdmittedCandidate st
      end.

(* Trusted-path boot transition from consented admitted candidate into next generation *)
Definition op_boot_successor (st : WorkflowState) : OpOutcome :=
  if negb (check_authorities st) then OpErr ErrAuthorityViolation st
  else if negb st.(ws_consent_granted) then OpErr ErrNoAdmittedCandidate st
  else
    match st.(ws_admitted_root), st.(ws_admitted_roster) with
    | Some adm_root, Some adm_roster =>
        OpOk {| ws_editor_auth := st.(ws_editor_auth);
                ws_builder_auth := st.(ws_builder_auth);
                ws_profile := st.(ws_profile);
                ws_running_gen_root := adm_root;
                ws_running_roster_hash := adm_roster;
                ws_boot_epoch := S st.(ws_boot_epoch);
                ws_next_job_epoch := st.(ws_next_job_epoch);
                ws_epoch_retired := st.(ws_epoch_retired);
                ws_partials := st.(ws_partials);
                ws_staged := st.(ws_staged);
                ws_jobs := st.(ws_jobs);
                ws_proof_cache := st.(ws_proof_cache);
                ws_admitted_root := st.(ws_admitted_root);
                ws_admitted_roster := st.(ws_admitted_roster);
                ws_consent_granted := false;
                ws_consent_outstanding := 0;
                ws_successor_booted := true;
                ws_last_diag_view := st.(ws_last_diag_view);
                ws_last_test_result := st.(ws_last_test_result) |}
    | _, _ => OpErr ErrNoAdmittedCandidate st
    end.

(* Op 9: ReadSuccessorTestResult *)
Definition op_read_successor_test_result
    (st : WorkflowState)
    (res : SuccessorTestResult)
    (expected_root expected_test_id : nat) : OpOutcome :=
  if negb (check_authorities st) then OpErr ErrAuthorityViolation st
  else if negb st.(ws_successor_booted) then OpErr ErrSuccessorNotBooted st
  else if negb res.(tr_grant_ok) then OpErr ErrMissingGrant st
  else
    let max_res := st.(ws_profile).(bp_pools).(pp_max_result_bytes) in
    if negb (Nat.leb res.(tr_result_bytes) max_res) then OpErr ErrResultOverBudget st
    else if orb (negb (Nat.eqb res.(tr_candidate_root) expected_root))
                (orb (negb (Nat.eqb res.(tr_candidate_root) st.(ws_running_gen_root)))
                     (orb (negb (Nat.eqb res.(tr_test_id) expected_test_id))
                          (negb (Nat.eqb res.(tr_boot_epoch) st.(ws_boot_epoch))))) then
      OpErr ErrTestResultStaleOrUnbound st
    else
      OpOk {| ws_editor_auth := st.(ws_editor_auth);
              ws_builder_auth := st.(ws_builder_auth);
              ws_profile := st.(ws_profile);
              ws_running_gen_root := st.(ws_running_gen_root);
              ws_running_roster_hash := st.(ws_running_roster_hash);
              ws_boot_epoch := st.(ws_boot_epoch);
              ws_next_job_epoch := st.(ws_next_job_epoch);
              ws_epoch_retired := st.(ws_epoch_retired);
              ws_partials := st.(ws_partials);
              ws_staged := st.(ws_staged);
              ws_jobs := st.(ws_jobs);
              ws_proof_cache := st.(ws_proof_cache);
              ws_admitted_root := st.(ws_admitted_root);
              ws_admitted_roster := st.(ws_admitted_roster);
              ws_consent_granted := st.(ws_consent_granted);
              ws_consent_outstanding := st.(ws_consent_outstanding);
              ws_successor_booted := st.(ws_successor_booted);
              ws_last_diag_view := st.(ws_last_diag_view);
              ws_last_test_result := Some res |}.

(* R-02-008 forbidden same-generation operations *)
Definition attempt_forbidden_native_op
    (st : WorkflowState) (fop : ForbiddenNativeOp) : OpOutcome :=
  match fop with
  | ForbiddenExecStagedNative => OpErr ErrSameGenNativeExecution st
  | ForbiddenRewriteRunningRoster => OpErr ErrRewriteRunningRoster st
  | ForbiddenInstallRuntimePlugin => OpErr ErrRuntimeNativePlugin st
  | ForbiddenLoadExternalByPath => OpErr ErrExternalPathLoad st
  | ForbiddenBypassChecking => OpErr ErrCheckingBypass st
  | ForbiddenWasmNativeEscape => OpErr ErrSameGenNativeExecution st
  end.

(* =========================================================================
   7. Key theorems (authority separation, R-02-008, R-08-046, R-12-020, cache)
   ========================================================================= *)

(*| discharges: R-13-027, R-13-027a, R-18-004e |*)
Theorem authority_separation_no_exec_sign_wire :
  forall st src req_id req_ver off len io ie idp next_st,
    op_read_source_slice st src req_id req_ver off len io ie idp = OpOk next_st ->
    st.(ws_editor_auth).(ea_holds_exec_staged) = false /\
    st.(ws_editor_auth).(ea_holds_signing_key) = false /\
    st.(ws_editor_auth).(ea_holds_mint_cap) = false /\
    st.(ws_editor_auth).(ea_holds_sealing_cap) = false /\
    st.(ws_editor_auth).(ea_holds_wiring_cap) = false /\
    st.(ws_editor_auth).(ea_holds_boot_select_cap) = false /\
    st.(ws_builder_auth).(ba_holds_exec_staged) = false /\
    st.(ws_builder_auth).(ba_holds_sealing_cap) = false /\
    st.(ws_builder_auth).(ba_holds_wiring_cap) = false /\
    st.(ws_builder_auth).(ba_holds_signing_key) = false.
Proof.
  intros st src req_id req_ver off len io ie idp next_st H.
  unfold op_read_source_slice in H.
  destruct (check_authorities st) eqn:Hauth; [ | discriminate H ].
  unfold check_authorities, valid_editor_authority, valid_builder_authority in Hauth.
  apply andb_true_iff_local in Hauth. destruct Hauth as [Hea Hba].
  destruct (ws_editor_auth st); destruct (ws_builder_auth st); simpl in *.
  destruct ea_private_source_ep0; destruct ea_private_result_ep0;
    destruct ea_holds_exec_staged0; destruct ea_holds_signing_key0;
    destruct ea_holds_mint_cap0; destruct ea_holds_sealing_cap0;
    destruct ea_holds_wiring_cap0; destruct ea_holds_boot_select_cap0;
    simpl in Hea; try discriminate Hea.
  destruct ba_immutable_closure_ok0; destruct ba_output_reservation_ok0;
    destruct ba_diagnostics_ep_ok0; destruct ba_holds_exec_staged0;
    destruct ba_holds_sealing_cap0; destruct ba_holds_wiring_cap0;
    destruct ba_holds_signing_key0; simpl in Hba; try discriminate Hba.
  repeat split; reflexivity.
Qed.

(*| discharges: R-02-008, R-13-001a, R-14-013e |*)
Theorem same_gen_native_exec_always_refused :
  forall st fop,
    outcome_ok (attempt_forbidden_native_op st fop) = false /\
    outcome_state (attempt_forbidden_native_op st fop) = st.
Proof.
  intros st fop. destruct fop; simpl; split; reflexivity.
Qed.

(*| discharges: R-02-008 |*)
Theorem staged_list_all_non_executable :
  forall st res_ok slot seq decl clen cdig exp_d act_d is_fin next_st,
    PS.all_of (fun o => negb o.(st_executable)) st.(ws_staged) = true ->
    op_stage_edited_source st res_ok slot seq decl clen cdig exp_d act_d is_fin = OpOk next_st ->
    PS.all_of (fun o => negb o.(st_executable)) next_st.(ws_staged) = true.
Proof.
  intros st res_ok slot seq decl clen cdig exp_d act_d is_fin next_st Hprev H.
  unfold op_stage_edited_source in H.
  destruct (check_authorities st); [ | discriminate H ].
  destruct (profile_valid (ws_profile st)); [ | discriminate H ].
  destruct res_ok; [ | discriminate H ].
  destruct (_ || _)%bool; [ discriminate H | ].
  destruct (find_partial_slot slot (ws_partials st)).
  - destruct (_ || _)%bool; [ discriminate H | ].
    destruct is_fin.
    + destruct (Nat.eqb _ _); [ | discriminate H ].
      destruct (Nat.eqb act_d exp_d); [ | discriminate H ].
      inversion H; subst; clear H. simpl. exact Hprev.
    + inversion H; subst; clear H. simpl. exact Hprev.
  - destruct (negb (Nat.ltb _ _)); [ discriminate H | ].
    destruct (_ || _)%bool; [ discriminate H | ].
    destruct is_fin.
    + destruct (Nat.eqb _ _); [ | discriminate H ].
      destruct (Nat.eqb act_d exp_d); [ | discriminate H ].
      inversion H; subst; clear H. simpl. exact Hprev.
    + inversion H; subst; clear H. simpl. exact Hprev.
Qed.

Fixpoint list_In {A : Type} (x : A) (l : list A) : Prop :=
  match l with
  | nil => False
  | cons y ys => y = x \/ list_In x ys
  end.

(*| discharges: R-02-008 |*)
Theorem staged_object_never_executable :
  forall st res_ok slot seq decl clen cdig exp_d act_d is_fin next_st obj,
    PS.all_of (fun o => negb o.(st_executable)) st.(ws_staged) = true ->
    op_stage_edited_source st res_ok slot seq decl clen cdig exp_d act_d is_fin = OpOk next_st ->
    list_In obj next_st.(ws_staged) ->
    obj.(st_executable) = false.
Proof.
  intros st res_ok slot seq decl clen cdig exp_d act_d is_fin next_st obj Hprev H Hin.
  assert (Hall : PS.all_of (fun o => negb o.(st_executable)) next_st.(ws_staged) = true).
  { exact (staged_list_all_non_executable st res_ok slot seq decl clen cdig exp_d act_d is_fin next_st Hprev H). }
  induction (ws_staged next_st) as [ | x xs IH ].
  - contradiction Hin.
  - simpl in Hall. apply andb_true_iff_local in Hall. destruct Hall as [Hx Hxs].
    simpl in Hin. destruct Hin as [Heq | Hrest].
    + subst x. destruct (st_executable obj); [ discriminate Hx | reflexivity ].
    + exact (IH Hrest Hxs).
Qed.

(*| discharges: R-12-020 |*)
Theorem external_roaming_auth_always_declined :
  forall st cr,
    cr.(cr_external_roaming_key) = true ->
    op_request_generation_consent st cr = OpErr ErrExternalAuthenticatorDeclined st.
Proof.
  intros st cr Hext. unfold op_request_generation_consent. rewrite Hext. reflexivity.
Qed.

(*| discharges: R-08-046 |*)
Theorem lifecycle_interruption_never_reusable :
  forall st,
    st <> Reusable ->
    lifecycle_step st ActInterrupt <> Some Reusable /\
    lifecycle_step Revoked ActRelease = None.
Proof.
  intros st Hnr. split.
  - destruct st; simpl; try discriminate; contradiction Hnr; reflexivity.
  - reflexivity.
Qed.

(*| discharges: R-08-046 |*)
Theorem profile_rejects_ordinary_borrowing :
  forall bp,
    bp.(bp_pools).(pp_ordinary_borrows_comp) = true ->
    profile_valid bp = false.
Proof.
  intros bp Hb. unfold profile_valid. rewrite Hb.
  destruct (bp_predeclared bp); destruct (Nat.ltb 0 (bp_step_budget bp)); reflexivity.
Qed.

Lemma nat_ltb_irrefl_local : forall n : nat, Nat.ltb n n = false.
Proof.
  intros n. induction n as [ | k IH ].
  - reflexivity.
  - exact IH.
Qed.

(*| discharges: R-08-046 |*)
Theorem epoch_exhaustion_retires_without_wrap :
  forall st cok eok cd co ce cdp tid cid rp next_st,
    st.(ws_next_job_epoch) = rp.(bp_pools).(pp_epoch_limit) ->
    check_authorities st = true ->
    cok = true ->
    eok = true ->
    profile_valid rp = true ->
    Nat.eqb rp.(bp_id) st.(ws_profile).(bp_id) = true ->
    Nat.eqb tid rp.(bp_toolchain_id) = true ->
    Nat.eqb cid rp.(bp_config_id) = true ->
    Nat.leb co rp.(bp_pools).(pp_source_index).(pd_max_capacity) = true ->
    Nat.leb ce rp.(bp_pools).(pp_max_source_edges) = true ->
    Nat.leb cdp rp.(bp_pools).(pp_max_source_depth) = true ->
    op_submit_build st cok eok cd co ce cdp tid cid rp = OpErr ErrEpochExhausted next_st ->
    next_st.(ws_epoch_retired) = true /\
    next_st.(ws_next_job_epoch) = st.(ws_next_job_epoch).
Proof.
  intros st cok eok cd co ce cdp tid cid rp next_st Hep Hauth Hcok Heok Hprof Hid Htid Hcid Hco Hce Hcdp H.
  unfold op_submit_build in H.
  rewrite Hauth, Hcok, Heok, Hprof, Hid, Htid, Hcid, Hco, Hce, Hcdp in H.
  simpl in H. rewrite Hep in H.
  rewrite nat_ltb_irrefl_local in H.
  destruct (ws_epoch_retired st); simpl in H; inversion H; subst;
    split; try reflexivity; symmetry; exact Hep.
Qed.

(*| discharges: R-13-027 |*)
Theorem cache_identity_sensitive_to_every_field :
  forall a b,
    cache_identity_eqb a b = true -> a = b.
Proof.
  intros [s1 d1 l1 m1 c1 a1 p1] [s2 d2 l2 m2 c2 a2 p2] H.
  unfold cache_identity_eqb in H. simpl in H.
  repeat match goal with
  | H0 : andb _ _ = true |- _ => apply andb_true_iff_local in H0; destruct H0
  end.
  repeat match goal with
  | H0 : Nat.eqb _ _ = true |- _ => apply nat_eqb_true_local in H0
  end.
  subst. reflexivity.
Qed.

(*| discharges: R-13-027, R-13-027a |*)
Theorem cache_hit_never_bypasses_admission :
  forall st pkg,
    pkg.(ap_cache_hit_used) = true ->
    (pkg.(ap_tal_ok) = false \/ pkg.(ap_source_corr_ok) = false) ->
    outcome_ok (op_submit_successor_admission st pkg) = false /\
    (outcome_state (op_submit_successor_admission st pkg)).(ws_running_gen_root) = st.(ws_running_gen_root) /\
    (outcome_state (op_submit_successor_admission st pkg)).(ws_running_roster_hash) = st.(ws_running_roster_hash).
Proof.
  intros st pkg _ Hfail.
  unfold op_submit_successor_admission.
  destruct (check_authorities st); [ | repeat split; reflexivity ].
  destruct (find_job_by_slot (ap_job_slot pkg) (ws_jobs st)); [ | repeat split; reflexivity ].
  destruct (Nat.eqb _ _); [ | repeat split; reflexivity ].
  destruct (jb_stage b); try (repeat split; reflexivity).
  destruct (ap_proof_complete pkg); [ | repeat split; reflexivity ].
  destruct (ap_checking_arena_ok pkg); [ | repeat split; reflexivity ].
  destruct (_ || _)%bool; [ repeat split; reflexivity | ].
  destruct (ap_roster_valid pkg); [ | repeat split; reflexivity ].
  destruct Hfail as [Htal | Hcorr].
  - rewrite Htal. simpl. repeat split; reflexivity.
  - rewrite Hcorr. destruct (ap_tal_ok pkg); simpl; repeat split; reflexivity.
Qed.

(*| discharges: R-02-008, R-13-027a |*)
Theorem refused_admission_preserves_running_generation :
  forall st pkg err next_st,
    op_submit_successor_admission st pkg = OpErr err next_st ->
    next_st.(ws_running_gen_root) = st.(ws_running_gen_root) /\
    next_st.(ws_running_roster_hash) = st.(ws_running_roster_hash).
Proof.
  intros st pkg err next_st H.
  unfold op_submit_successor_admission in H.
  repeat match goal with
  | H0 : (if ?c then _ else _) = OpErr _ _ |- _ => destruct c
  | H0 : match ?m with _ => _ end = OpErr _ _ |- _ => destruct m
  end; inversion H; subst; split; reflexivity.
Qed.

(*| discharges: R-08-046 |*)
Theorem diagnostics_overflow_emits_truncation_marker :
  forall st slot epoch req_recs req_bytes j view next_st,
    check_authorities st = true ->
    find_job_by_slot slot st.(ws_jobs) = Some j ->
    Nat.eqb j.(jb_epoch) epoch = true ->
    j.(jb_diag_truncated) = true ->
    op_read_diagnostics st slot epoch true req_recs req_bytes = OpOk next_st ->
    next_st.(ws_last_diag_view) = Some view ->
    view.(dv_truncated) = true /\
    view.(dv_marker_code) = TRUNCATED_DIAG_MARKER.
Proof.
  intros st slot epoch req_recs req_bytes j view next_st Hauth Hfind Hep Htr H Hview.
  unfold op_read_diagnostics in H.
  rewrite Hauth, Hfind, Hep in H. simpl in H.
  rewrite Htr in H. simpl in H.
  inversion H; subst; clear H.
  simpl in Hview. inversion Hview; subst; clear Hview.
  split; reflexivity.
Qed.

(*| discharges: R-02-008, R-13-001a |*)
Theorem successor_test_result_bound_to_root_test_and_epoch :
  forall st res exp_root exp_tid next_st,
    op_read_successor_test_result st res exp_root exp_tid = OpOk next_st ->
    res.(tr_candidate_root) = exp_root /\
    res.(tr_candidate_root) = st.(ws_running_gen_root) /\
    res.(tr_test_id) = exp_tid /\
    res.(tr_boot_epoch) = st.(ws_boot_epoch).
Proof.
  intros st res exp_root exp_tid next_st H.
  unfold op_read_successor_test_result in H.
  destruct (check_authorities st); [ | discriminate H ].
  destruct (ws_successor_booted st); [ | discriminate H ].
  destruct (tr_grant_ok res); [ | discriminate H ].
  destruct (Nat.leb _ _); [ | discriminate H ].
  destruct (Nat.eqb (tr_candidate_root res) exp_root) eqn:H1;
    destruct (Nat.eqb (tr_candidate_root res) (ws_running_gen_root st)) eqn:H2;
    destruct (Nat.eqb (tr_test_id res) exp_tid) eqn:H3;
    destruct (Nat.eqb (tr_boot_epoch res) (ws_boot_epoch st)) eqn:H4;
    simpl in H; try discriminate H.
  apply nat_eqb_true_local in H1.
  apply nat_eqb_true_local in H2.
  apply nat_eqb_true_local in H3.
  apply nat_eqb_true_local in H4.
  repeat split; assumption.
Qed.

(* =========================================================================
   8. Constructive reference state, end-to-end trace, and negative controls
   ========================================================================= *)

Definition mk_pool (k : PoolKind) (cap : nat) : PoolDecl :=
  {| pd_kind := k;
     pd_max_capacity := cap;
     pd_has_owning_compartment := true;
     pd_has_derivation_source := true;
     pd_has_bind_release_caps := true;
     pd_has_thresholds := true;
     pd_has_release_bound := true;
     pd_has_lifecycle := true;
     pd_has_recovery_reserve := true;
     pd_has_confidentiality := true;
     pd_has_telemetry := true;
     pd_has_restart_semantics := true |}.

Definition demo_profile : BuildProfile :=
  {| bp_id := 1;
     bp_predeclared := true;
     bp_toolchain_id := 10;
     bp_config_id := 20;
     bp_step_budget := 1000;
     bp_pools :=
       {| pp_source_index := mk_pool PoolSourceIndex 16;
          pp_edited_staging := mk_pool PoolEditedStaging 4096;
          pp_build_jobs := mk_pool PoolBuildJobs 4;
          pp_pass_arenas := mk_pool PoolPassArenas 8192;
          pp_diagnostics_buffer := mk_pool PoolDiagnosticsBuffer 8;
          pp_proof_cache := mk_pool PoolProofCache 8;
          pp_candidate_closure := mk_pool PoolCandidateClosure 16;
          pp_consent_transfer := mk_pool PoolConsentTransfer 4;
          pp_max_source_edges := 32;
          pp_max_source_depth := 8;
          pp_max_chunk_bytes := 1024;
          pp_max_partial_objects := 4;
          pp_epoch_limit := 4;
          pp_max_diag_bytes := 512;
          pp_max_checking_steps := 2000;
          pp_max_result_bytes := 256;
          pp_ordinary_borrows_comp := false |} |}.

Definition demo_editor_auth : EditorAuthority :=
  {| ea_private_source_ep := true;
     ea_private_result_ep := true;
     ea_holds_exec_staged := false;
     ea_holds_signing_key := false;
     ea_holds_mint_cap := false;
     ea_holds_sealing_cap := false;
     ea_holds_wiring_cap := false;
     ea_holds_boot_select_cap := false |}.

Definition demo_builder_auth : BuilderAuthority :=
  {| ba_immutable_closure_ok := true;
     ba_output_reservation_ok := true;
     ba_diagnostics_ep_ok := true;
     ba_holds_exec_staged := false;
     ba_holds_sealing_cap := false;
     ba_holds_wiring_cap := false;
     ba_holds_signing_key := false |}.

Definition demo_source : SourceObject :=
  {| so_obj_id := 101; so_version := 3; so_total_bytes := 512; so_grant_ok := true |}.

Definition demo_cache_id : CacheIdentity :=
  {| ci_source_hash := 111;
     ci_dep_closure_hash := 222;
     ci_imported_lemma_hash := 333;
     ci_semantics_hash := 444;
     ci_config_hash := 20;
     ci_assumption_set_hash := 555;
     ci_profile_id := 1 |}.

Definition initial_state : WorkflowState :=
  {| ws_editor_auth := demo_editor_auth;
     ws_builder_auth := demo_builder_auth;
     ws_profile := demo_profile;
     ws_running_gen_root := 1000;
     ws_running_roster_hash := 2000;
     ws_boot_epoch := 1;
     ws_next_job_epoch := 1;
     ws_epoch_retired := false;
     ws_partials := nil;
     ws_staged := nil;
     ws_jobs := nil;
     ws_proof_cache := nil;
     ws_admitted_root := None;
     ws_admitted_roster := None;
     ws_consent_granted := false;
     ws_consent_outstanding := 0;
     ws_successor_booted := false;
     ws_last_diag_view := None;
     ws_last_test_result := None |}.

(*| discharges: R-02-008, R-05-165, R-05-166, R-13-001a, R-13-027, R-13-027a, R-18-004e |*)
Example positive_end_to_end_successor_generation_trace :
  let o1 := op_read_source_slice initial_state demo_source 101 3 0 256 4 6 3 in
  let s1 := outcome_state o1 in
  let o2 := op_stage_edited_source s1 true 1 0 300 200 71 777 777 false in
  let s2 := outcome_state o2 in
  let o3 := op_stage_edited_source s2 true 1 1 300 100 72 777 777 true in
  let s3 := outcome_state o3 in
  let o4 := op_submit_build s3 true true 777 4 6 3 10 20 demo_profile in
  let s4 := outcome_state o4 in
  let o5 := op_advance_build s4 0 1 400 4096 888 2 128 true in
  let s5 := outcome_state o5 in
  let o6 := op_read_diagnostics s5 0 1 true 4 256 in
  let s6 := outcome_state o6 in
  let pkg := {| ap_job_slot := 0;
                ap_job_epoch := 1;
                ap_proof_complete := true;
                ap_checking_arena_ok := true;
                ap_checking_steps := 500;
                ap_roster_entries := 4;
                ap_roster_valid := true;
                ap_tal_ok := true;
                ap_source_corr_ok := true;
                ap_cache_hit_used := false;
                ap_cache_id := demo_cache_id;
                ap_candidate_root := 3000;
                ap_candidate_roster_hash := 4000 |} in
  let o7 := op_submit_successor_admission s6 pkg in
  let s7 := outcome_state o7 in
  let cr := {| cr_candidate_root := 3000;
               cr_roster_hash := 4000;
               cr_user_consented := true;
               cr_on_die_cred_ok := true;
               cr_external_roaming_key := false |} in
  let o8 := op_request_generation_consent s7 cr in
  let s8 := outcome_state o8 in
  let o9 := op_boot_successor s8 in
  let s9 := outcome_state o9 in
  let tr := {| tr_grant_ok := true;
               tr_candidate_root := 3000;
               tr_test_id := 42;
               tr_boot_epoch := 2;
               tr_result_bytes := 64;
               tr_passed := true |} in
  let o10 := op_read_successor_test_result s9 tr 3000 42 in
  let s10 := outcome_state o10 in
  outcome_ok o1 = true /\
  outcome_ok o2 = true /\
  outcome_ok o3 = true /\
  outcome_ok o4 = true /\
  outcome_ok o5 = true /\
  outcome_ok o6 = true /\
  outcome_ok o7 = true /\
  outcome_ok o8 = true /\
  outcome_ok o9 = true /\
  outcome_ok o10 = true /\
  s10.(ws_running_gen_root) = 3000 /\
  s10.(ws_boot_epoch) = 2 /\
  s10.(ws_last_test_result) = Some tr /\
  PS.all_of (fun o => negb o.(st_executable)) s10.(ws_staged) = true.
Proof. repeat split; reflexivity. Qed.

(*| discharges: R-02-008, R-08-046, R-12-020, R-13-027, R-13-027a, R-14-013e |*)
Example negative_controls_all_refused :
  (* 1. Wrong object/version or out-of-range slice read *)
  outcome_err (op_read_source_slice initial_state demo_source 999 3 0 64 1 1 1) = Some ErrWrongObjectOrVersion /\
  outcome_err (op_read_source_slice initial_state demo_source 101 3 500 64 1 1 1) = Some ErrOutOfRange /\
  (* 2. Staging repeated/over-budget/mismatched aborts and publishes nothing *)
  let s_p1 := outcome_state (op_stage_edited_source initial_state true 2 0 100 50 1 900 900 false) in
  let o_rep := op_stage_edited_source s_p1 true 2 0 100 50 1 900 900 false in
  let o_bad_dig := op_stage_edited_source s_p1 true 2 1 100 50 2 900 901 true in
  outcome_err o_rep = Some ErrStagingSequenceOrRepeat /\
  (outcome_state o_rep).(ws_staged) = nil /\
  outcome_err o_bad_dig = Some ErrStagingDigestMismatch /\
  (outcome_state o_bad_dig).(ws_staged) = nil /\
  (* 3. SubmitBuild missing closure / missing comp service / epoch exhaustion *)
  outcome_err (op_submit_build initial_state false true 1 1 1 1 10 20 demo_profile) = Some ErrMissingClosure /\
  outcome_err (op_submit_build initial_state true false 1 1 1 1 10 20 demo_profile) = Some ErrCompServiceUnavailable /\
  let st_epoch_full :=
    {| ws_editor_auth := demo_editor_auth; ws_builder_auth := demo_builder_auth;
       ws_profile := demo_profile; ws_running_gen_root := 1000; ws_running_roster_hash := 2000;
       ws_boot_epoch := 1; ws_next_job_epoch := 4; ws_epoch_retired := false;
       ws_partials := nil; ws_staged := nil; ws_jobs := nil; ws_proof_cache := nil;
       ws_admitted_root := None; ws_admitted_roster := None; ws_consent_granted := false;
       ws_consent_outstanding := 0; ws_successor_booted := false;
       ws_last_diag_view := None; ws_last_test_result := None |} in
  let o_ep := op_submit_build st_epoch_full true true 1 1 1 1 10 20 demo_profile in
  outcome_err o_ep = Some ErrEpochExhausted /\
  (outcome_state o_ep).(ws_epoch_retired) = true /\
  (outcome_state o_ep).(ws_next_job_epoch) = 4 /\
  (* 4. AdvanceBuild budget expansion & pass-arena exhaustion *)
  let s_job := outcome_state (op_submit_build initial_state true true 777 4 6 3 10 20 demo_profile) in
  outcome_err (op_advance_build s_job 0 1 1001 1024 888 1 32 true) = Some ErrBudgetExpansion /\
  outcome_err (op_advance_build s_job 0 1 100 9000 888 1 32 true) = Some ErrPassArenaExhausted /\
  (* 5. Diagnostics overflow emits truncation marker *)
  let s_diag := outcome_state (op_advance_build s_job 0 1 100 1024 888 20 1024 true) in
  let o_dv := op_read_diagnostics s_diag 0 1 true 4 128 in
  outcome_ok o_dv = true /\
  match (outcome_state o_dv).(ws_last_diag_view) with
  | Some v => andb v.(dv_truncated) (Nat.eqb v.(dv_marker_code) TRUNCATED_DIAG_MARKER)
  | None => false
  end = true /\
  (* 6. CancelBuild stale epoch & mid-sweep interruption never Reusable *)
  outcome_err (op_cancel_build s_job 0 99 true false) = Some ErrStaleHandle /\
  let o_int := op_cancel_build s_job 0 1 true true in
  outcome_err o_int = Some ErrLifecycleInterrupted /\
  match find_job_by_slot 0 (outcome_state o_int).(ws_jobs) with
  | Some jb => negb (lifecycle_eqb jb.(jb_lifecycle) Reusable)
  | None => false
  end = true /\
  (* 7. ProofCache invalidation on lemma/semantics/assumption change & no bypass *)
  let shifted_id := {| ci_source_hash := 111; ci_dep_closure_hash := 222;
                       ci_imported_lemma_hash := 999; ci_semantics_hash := 444;
                       ci_config_hash := 20; ci_assumption_set_hash := 555; ci_profile_id := 1 |} in
  cache_identity_eqb demo_cache_id shifted_id = false /\
  (* 8. Admission failure leaves running gen unchanged *)
  let s_done := outcome_state (op_advance_build s_job 0 1 100 1024 888 1 32 true) in
  let bad_pkg := {| ap_job_slot := 0; ap_job_epoch := 1; ap_proof_complete := false;
                    ap_checking_arena_ok := true; ap_checking_steps := 100;
                    ap_roster_entries := 2; ap_roster_valid := true; ap_tal_ok := true;
                    ap_source_corr_ok := true; ap_cache_hit_used := false;
                    ap_cache_id := demo_cache_id; ap_candidate_root := 3000;
                    ap_candidate_roster_hash := 4000 |} in
  let o_adm_fail := op_submit_successor_admission s_done bad_pkg in
  outcome_err o_adm_fail = Some ErrProofIncomplete /\
  (outcome_state o_adm_fail).(ws_running_gen_root) = 1000 /\
  (* 9. R-12-020 external roaming key declined *)
  let ext_cr := {| cr_candidate_root := 3000; cr_roster_hash := 4000;
                   cr_user_consented := true; cr_on_die_cred_ok := true;
                   cr_external_roaming_key := true |} in
  outcome_err (op_request_generation_consent initial_state ext_cr) = Some ErrExternalAuthenticatorDeclined /\
  (* 10. R-02-008 same-gen native exec / rewrite / plugin / path / bypass refused *)
  outcome_err (attempt_forbidden_native_op initial_state ForbiddenExecStagedNative) = Some ErrSameGenNativeExecution /\
  outcome_err (attempt_forbidden_native_op initial_state ForbiddenRewriteRunningRoster) = Some ErrRewriteRunningRoster /\
  outcome_err (attempt_forbidden_native_op initial_state ForbiddenWasmNativeEscape) = Some ErrSameGenNativeExecution /\
  (* 11. Old boot epoch successor test result refused *)
  let s_booted :=
    {| ws_editor_auth := demo_editor_auth; ws_builder_auth := demo_builder_auth;
       ws_profile := demo_profile; ws_running_gen_root := 3000; ws_running_roster_hash := 4000;
       ws_boot_epoch := 2; ws_next_job_epoch := 2; ws_epoch_retired := false;
       ws_partials := nil; ws_staged := nil; ws_jobs := nil; ws_proof_cache := nil;
       ws_admitted_root := Some 3000; ws_admitted_roster := Some 4000; ws_consent_granted := false;
       ws_consent_outstanding := 0; ws_successor_booted := true;
       ws_last_diag_view := None; ws_last_test_result := None |} in
  let old_tr := {| tr_grant_ok := true; tr_candidate_root := 3000; tr_test_id := 42;
                   tr_boot_epoch := 1; tr_result_bytes := 64; tr_passed := true |} in
  outcome_err (op_read_successor_test_result s_booted old_tr 3000 42) = Some ErrTestResultStaleOrUnbound.
Proof. repeat split; reflexivity. Qed.

(* =========================================================================
   9. R-05-166 inhabitation witnesses (one closed Definition per Record)
   ========================================================================= *)

Definition witness_EditorAuthority : EditorAuthority := demo_editor_auth.
Definition witness_BuilderAuthority : BuilderAuthority := demo_builder_auth.
Definition witness_PoolDecl : PoolDecl := mk_pool PoolSourceIndex 16.
Definition witness_ProfilePools : ProfilePools := demo_profile.(bp_pools).
Definition witness_BuildProfile : BuildProfile := demo_profile.
Definition witness_CacheIdentity : CacheIdentity := demo_cache_id.
Definition witness_ProofCacheEntry : ProofCacheEntry :=
  {| pce_identity := demo_cache_id; pce_proof_digest := 3000; pce_verified := true |}.
Definition witness_SourceObject : SourceObject := demo_source.
Definition witness_PartialStage : PartialStage :=
  {| ps_slot_id := 1; ps_active := true; ps_next_seq := 1;
     ps_declared_total := 300; ps_accum_bytes := 200; ps_running_digest := 371 |}.
Definition witness_StagedObject : StagedObject :=
  {| st_obj_id := 1; st_content_digest := 777; st_total_bytes := 300; st_executable := false |}.
Definition witness_BuildJob : BuildJob :=
  {| jb_handle_slot := 0; jb_epoch := 1; jb_lifecycle := Bound; jb_stage := JobRunning;
     jb_closure_digest := 777; jb_profile_id := 1; jb_step_budget := 1000; jb_steps_used := 0;
     jb_output_digest := 0; jb_output_executable := false;
     jb_diag_records := 0; jb_diag_bytes := 0; jb_diag_truncated := false |}.
Definition witness_DiagRecord : DiagRecord :=
  {| dr_seq := 0; dr_bytes := 32; dr_is_truncation_marker := false |}.
Definition witness_DiagnosticsView : DiagnosticsView :=
  {| dv_records := cons witness_DiagRecord nil; dv_total_bytes := 32;
     dv_truncated := false; dv_marker_code := 0 |}.
Definition witness_AdmissionPackage : AdmissionPackage :=
  {| ap_job_slot := 0; ap_job_epoch := 1; ap_proof_complete := true;
     ap_checking_arena_ok := true; ap_checking_steps := 500; ap_roster_entries := 4;
     ap_roster_valid := true; ap_tal_ok := true; ap_source_corr_ok := true;
     ap_cache_hit_used := false; ap_cache_id := demo_cache_id;
     ap_candidate_root := 3000; ap_candidate_roster_hash := 4000 |}.
Definition witness_ConsentRequest : ConsentRequest :=
  {| cr_candidate_root := 3000; cr_roster_hash := 4000;
     cr_user_consented := true; cr_on_die_cred_ok := true;
     cr_external_roaming_key := false |}.
Definition witness_SuccessorTestResult : SuccessorTestResult :=
  {| tr_grant_ok := true; tr_candidate_root := 3000; tr_test_id := 42;
     tr_boot_epoch := 2; tr_result_bytes := 64; tr_passed := true |}.
Definition witness_WorkflowState : WorkflowState := initial_state.

(* R-05-163, R-05-164, R-05-165, R-05-166: zero axioms, ProofSupport + prelude
   only, all records inhabited, positive & negative controls discharged. *)
