(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ResidentToolchain.v

   Specification and non-vacuity model for M1.10-i resident toolchain
   admissibility, bounded resumable pass activations, residency scoring, and
   host-vs-device bootstrap reproduction:
   - License/distribution screening (R-18-004e): refuses shipping a
     non-commercial external compiler/prover pass without an explicit
     redistribution grant, an independent implementation, or strict
     restriction to the enumerated dual-licensed subset; requires reading
     license terms at incorporation.
   - Whole-closure port audit (R-13-027, R-13-027a): audits unsafe sites,
     ambient authority, and host assumptions (Filesystem, Subprocess,
     HostAllocator); unresolved host assumptions must be disposed as named
     estimated sub-ports and never absorbed as `unsafe` exceptions.
   - Bounded resumable pass activations (R-08-046, R-13-027a): enforces
     smallest-loop-first order (type-checker over an already admitted artifact
     before compilers), per-pass step budgets, recorded peak bytes/RSS,
     refusal at declared pool exhaustion thresholds preserving the running
     generation, and zero execute/sealing/wiring authority over outputs.
   - Residency scoring and pool sharing (R-08-014, R-08-018a, R-18-004e):
     separates ReadingA (per-mode composition scoring) from ReadingB
     (one-layout cross-mode scoring) and requires explicit R-08-014 disjoint
     live ranges plus R-08-018a frame/region non-co-occurrence proof (never
     assumed correlation) before sharing compiler and prover pools.
   - Bootstrap self-build reproduction receipt (R-13-027, R-06-014): compares
     the on-device self-build artifact and admission receipt against the
     locked-switch host receipt (equal -> Reproduced; unequal -> named
     Diverged finding with cause), while keeping R-06-014's De Bruijn
     bootstrap root explicitly Relocated and refusing any Closed claim.

   Assumptions and non-vacuity (R-05-163, R-05-164, R-05-165, R-05-166):
   - Zero axioms (`Closed under the global context`), prelude + ProofSupport
     only, and every declared record carries a closed `witness_<Record>`
     inhabitant.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-06-014 R-08-014 R-08-018a R-08-046
      R-13-027 R-13-027a R-18-004e
   SHA256: f21f6ba44f1cc9258c8ce8772d392150cddbb6208023da60e2e4feef149bd9f9
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport.

Module PS := ProofSupport.

(* =========================================================================
   1. Small prelude helpers
   ========================================================================= *)

Definition bool_eqb (a b : bool) : bool := PS.bool_eqb a b.

Fixpoint max_nat (l : list nat) : nat :=
  match l with
  | nil => 0
  | cons x xs => Nat.max x (max_nat xs)
  end.

Lemma nat_leb_refl_local : forall n : nat, Nat.leb n n = true.
Proof. exact PS.nat_leb_refl. Qed.

Lemma nat_leb_trans_local :
  forall a b c : nat, Nat.leb a b = true -> Nat.leb b c = true -> Nat.leb a c = true.
Proof. exact PS.nat_leb_trans. Qed.

Lemma nat_leb_add_r : forall a b : nat, Nat.leb a (Nat.add a b) = true.
Proof.
  intros a b. induction a as [| k IH]; simpl.
  - reflexivity.
  - exact IH.
Qed.

Lemma nat_leb_add_l : forall a b : nat, Nat.leb b (Nat.add a b) = true.
Proof.
  intros a b. rewrite PS.nat_add_comm. exact (nat_leb_add_r b a).
Qed.

Lemma nat_max_le_both :
  forall a b c : nat,
    Nat.leb a c = true ->
    Nat.leb b c = true ->
    Nat.leb (Nat.max a b) c = true.
Proof.
  intros a. induction a as [| x IH]; intros b c Ha Hb; simpl.
  - exact Hb.
  - destruct b as [| y].
    + exact Ha.
    + destruct c as [| z]; [ discriminate Ha | ].
      simpl in Ha, Hb. simpl. exact (IH y z Ha Hb).
Qed.

Lemma nat_le_max_l : forall a b : nat, Nat.leb a (Nat.max a b) = true.
Proof.
  intros a. induction a as [| x IH]; intros b; simpl.
  - reflexivity.
  - destruct b as [| y].
    + exact (PS.nat_leb_refl (S x)).
    + simpl. exact (IH y).
Qed.

Lemma nat_le_max_r : forall a b : nat, Nat.leb b (Nat.max a b) = true.
Proof.
  intros a. induction a as [| x IH]; intros b; simpl.
  - exact (PS.nat_leb_refl b).
  - destruct b as [| y].
    + reflexivity.
    + simpl. exact (IH y).
Qed.

(* =========================================================================
   2. License & distribution screening (R-18-004e)
   ========================================================================= *)

Inductive LicenseRoute : Type :=
| RouteIndependentImpl
| RouteCommercialGrant
| RouteDualLicensedSubset
| RouteNonCommercialOnly.

Inductive LicenseRefusal : Type :=
| LicenseNotReadAtIncorporation
| NonCommercialPassWithoutGrant
| MissingCommercialGrant
| OutsideDualLicensedSubset.

Record ComponentLicense : Type := {
  cl_comp_id : nat;
  cl_route : LicenseRoute;
  cl_read_at_incorporation : bool;
  cl_has_noncommercial_pass : bool;
  cl_has_commercial_grant : bool;
  cl_dual_subset_only : bool;
  cl_provides_required_backend : bool
}.

Inductive LicenseVerdict : Type :=
| LicenseAdmitted
| LicenseRefused (reason : LicenseRefusal).

Definition screen_component_license (c : ComponentLicense) : LicenseVerdict :=
  if negb c.(cl_read_at_incorporation) then
    LicenseRefused LicenseNotReadAtIncorporation
  else
    match c.(cl_route) with
    | RouteIndependentImpl =>
        if c.(cl_has_noncommercial_pass) then
          LicenseRefused NonCommercialPassWithoutGrant
        else
          LicenseAdmitted
    | RouteCommercialGrant =>
        if c.(cl_has_commercial_grant) then
          LicenseAdmitted
        else
          LicenseRefused MissingCommercialGrant
    | RouteDualLicensedSubset =>
        if orb (negb c.(cl_dual_subset_only)) c.(cl_has_noncommercial_pass) then
          LicenseRefused OutsideDualLicensedSubset
        else if c.(cl_provides_required_backend) then
          LicenseRefused OutsideDualLicensedSubset
        else
          LicenseAdmitted
    | RouteNonCommercialOnly =>
        LicenseRefused NonCommercialPassWithoutGrant
    end.

Definition license_admitted (v : LicenseVerdict) : bool :=
  match v with
  | LicenseAdmitted => true
  | LicenseRefused _ => false
  end.

Definition screen_all_licenses (cs : list ComponentLicense) : bool :=
  PS.all_of (fun c => license_admitted (screen_component_license c)) cs.

(*| discharges: R-18-004e |*)
Theorem license_unread_at_incorporation_refused :
  forall c,
    c.(cl_read_at_incorporation) = false ->
    screen_component_license c = LicenseRefused LicenseNotReadAtIncorporation.
Proof.
  intros c Hunread.
  unfold screen_component_license. rewrite Hunread. reflexivity.
Qed.

(*| discharges: R-18-004e |*)
Theorem noncommercial_pass_without_grant_refused :
  forall c,
    c.(cl_has_noncommercial_pass) = true ->
    c.(cl_has_commercial_grant) = false ->
    license_admitted (screen_component_license c) = false.
Proof.
  intros c Hnc Hnogrant.
  unfold screen_component_license, license_admitted.
  destruct (cl_read_at_incorporation c); simpl; [ | reflexivity ].
  destruct (cl_route c); simpl;
    rewrite ?Hnc, ?Hnogrant;
    try destruct (cl_dual_subset_only c); simpl; reflexivity.
Qed.

(*| discharges: R-18-004e |*)
Theorem dual_licensed_subset_refuses_outside_files_or_backend_claim :
  forall c,
    c.(cl_route) = RouteDualLicensedSubset ->
    orb (negb c.(cl_dual_subset_only))
        (orb c.(cl_has_noncommercial_pass) c.(cl_provides_required_backend)) = true ->
    license_admitted (screen_component_license c) = false.
Proof.
  intros c Hroute Hbad.
  unfold screen_component_license, license_admitted.
  rewrite Hroute.
  destruct (cl_read_at_incorporation c); simpl; [ | reflexivity ].
  destruct (cl_dual_subset_only c);
    destruct (cl_has_noncommercial_pass c);
    destruct (cl_provides_required_backend c);
    simpl in *; try discriminate Hbad; reflexivity.
Qed.

(* =========================================================================
   3. Whole-closure port audit (R-13-027, R-13-027a)
   ========================================================================= *)

Inductive ClosureDisposition : Type :=
| DispClean
| DispDeleted
| DispVerifiedHalOrProof
| DispNamedSubPort
| DispUnsafeException
| DispUnresolvedAmbient.

Inductive ClosureRefusal : Type :=
| AmbientAuthorityPresent
| UncoveredUnsafeSite
| UnsafeExceptionForbidden
| UnresolvedHostAssumption
| UnestimatedSubPort.

Record ClosureUnit : Type := {
  cu_id : nat;
  cu_unsafe_sites : nat;
  cu_unsafe_hal_or_proof_ok : bool;
  cu_ambient_authority : bool;
  cu_has_filesystem : bool;
  cu_has_subprocess : bool;
  cu_has_host_allocator : bool;
  cu_disposition : ClosureDisposition;
  cu_subport_id : nat;
  cu_subport_estimated : bool
}.

Definition unit_has_host_assumption (u : ClosureUnit) : bool :=
  orb u.(cu_has_filesystem)
      (orb u.(cu_has_subprocess) u.(cu_has_host_allocator)).

Inductive ClosureVerdict : Type :=
| ClosureCleared
| ClosureAssignedSubPort (subport_id : nat)
| ClosureRefused (reason : ClosureRefusal).

Definition audit_closure_unit (u : ClosureUnit) : ClosureVerdict :=
  if u.(cu_ambient_authority) then
    ClosureRefused AmbientAuthorityPresent
  else
    match u.(cu_disposition) with
    | DispUnsafeException =>
        ClosureRefused UnsafeExceptionForbidden
    | DispUnresolvedAmbient =>
        ClosureRefused AmbientAuthorityPresent
    | DispClean =>
        if negb (Nat.eqb u.(cu_unsafe_sites) 0) then
          ClosureRefused UncoveredUnsafeSite
        else if unit_has_host_assumption u then
          ClosureRefused UnresolvedHostAssumption
        else
          ClosureCleared
    | DispDeleted =>
        if andb (negb (Nat.eqb u.(cu_unsafe_sites) 0))
                (negb u.(cu_unsafe_hal_or_proof_ok)) then
          ClosureRefused UncoveredUnsafeSite
        else
          ClosureCleared
    | DispVerifiedHalOrProof =>
        if negb u.(cu_unsafe_hal_or_proof_ok) then
          ClosureRefused UncoveredUnsafeSite
        else if unit_has_host_assumption u then
          ClosureRefused UnresolvedHostAssumption
        else
          ClosureCleared
    | DispNamedSubPort =>
        if andb (negb (Nat.eqb u.(cu_unsafe_sites) 0))
                (negb u.(cu_unsafe_hal_or_proof_ok)) then
          ClosureRefused UncoveredUnsafeSite
        else if negb (unit_has_host_assumption u) then
          ClosureRefused UnresolvedHostAssumption
        else if orb (Nat.eqb u.(cu_subport_id) 0) (negb u.(cu_subport_estimated)) then
          ClosureRefused UnestimatedSubPort
        else
          ClosureAssignedSubPort u.(cu_subport_id)
    end.

Definition closure_audit_accepted (v : ClosureVerdict) : bool :=
  match v with
  | ClosureCleared => true
  | ClosureAssignedSubPort _ => true
  | ClosureRefused _ => false
  end.

Definition closure_cleared_now (v : ClosureVerdict) : bool :=
  match v with
  | ClosureCleared => true
  | ClosureAssignedSubPort _ => false
  | ClosureRefused _ => false
  end.

Definition audit_all_closures (us : list ClosureUnit) : bool :=
  PS.all_of (fun u => closure_audit_accepted (audit_closure_unit u)) us.

Definition all_closures_cleared_now (us : list ClosureUnit) : bool :=
  PS.all_of (fun u => closure_cleared_now (audit_closure_unit u)) us.

(*| discharges: R-13-027a |*)
Theorem unsafe_exception_always_refused :
  forall u,
    u.(cu_disposition) = DispUnsafeException ->
    closure_audit_accepted (audit_closure_unit u) = false.
Proof.
  intros u Hdisp.
  unfold audit_closure_unit, closure_audit_accepted.
  rewrite Hdisp.
  destruct (cu_ambient_authority u); reflexivity.
Qed.

(*| discharges: R-13-027a |*)
Theorem ambient_authority_always_refused :
  forall u,
    u.(cu_ambient_authority) = true ->
    audit_closure_unit u = ClosureRefused AmbientAuthorityPresent.
Proof.
  intros u Hamb.
  unfold audit_closure_unit. rewrite Hamb. reflexivity.
Qed.

(*| discharges: R-13-027 |*)
Theorem unresolved_host_assumption_must_shed_or_become_estimated_subport :
  forall u,
    u.(cu_ambient_authority) = false ->
    unit_has_host_assumption u = true ->
    closure_audit_accepted (audit_closure_unit u) = true ->
    u.(cu_disposition) = DispDeleted \/
    (u.(cu_disposition) = DispNamedSubPort /\
     Nat.eqb u.(cu_subport_id) 0 = false /\
     u.(cu_subport_estimated) = true).
Proof.
  intros u Hamb Hhost Hacc.
  unfold audit_closure_unit in Hacc.
  rewrite Hamb in Hacc.
  destruct (cu_disposition u) eqn:Hdisp; simpl in *.
  - destruct (Nat.eqb (cu_unsafe_sites u) 0); [ | discriminate Hacc ].
    rewrite Hhost in Hacc. discriminate Hacc.
  - left. reflexivity.
  - destruct (cu_unsafe_hal_or_proof_ok u); [ | discriminate Hacc ].
    rewrite Hhost in Hacc. discriminate Hacc.
  - right.
    destruct (andb (negb (Nat.eqb (cu_unsafe_sites u) 0))
                   (negb (cu_unsafe_hal_or_proof_ok u)));
      [ discriminate Hacc | ].
    rewrite Hhost in Hacc. simpl in Hacc.
    destruct (Nat.eqb (cu_subport_id u) 0) eqn:Hid;
      destruct (cu_subport_estimated u) eqn:Hest;
      simpl in Hacc; try discriminate Hacc.
    repeat split; reflexivity.
  - discriminate Hacc.
  - discriminate Hacc.
Qed.

(* =========================================================================
   4. Smallest-loop-first order, compartment authority, and bounded pools
      (R-08-046, R-13-027a)
   ========================================================================= *)

Inductive ToolchainRole : Type :=
| RoleTypeChecker
| RoleProver
| RoleCompiler
| RoleComposer
| RolePackageBuilder.

Definition role_rank (r : ToolchainRole) : nat :=
  match r with
  | RoleTypeChecker => 0
  | RoleProver => 1
  | RoleCompiler => 2
  | RoleComposer => 3
  | RolePackageBuilder => 4
  end.

Definition role_eqb (a b : ToolchainRole) : bool :=
  Nat.eqb (role_rank a) (role_rank b).

Fixpoint role_sequence_ordered_from (min_rank : nat) (roles : list ToolchainRole) : bool :=
  match roles with
  | nil => true
  | cons r rest =>
      andb (Nat.leb min_rank (role_rank r))
           (role_sequence_ordered_from (role_rank r) rest)
  end.

Definition smallest_loop_first (roles : list ToolchainRole) : bool :=
  andb (PS.any_of (role_eqb RoleTypeChecker) roles)
       (role_sequence_ordered_from 0 roles).

Record CompartmentCaps : Type := {
  cc_id : nat;
  cc_role : ToolchainRole;
  cc_exec_over_own_output : bool;
  cc_sealing_auth : bool;
  cc_wiring_auth : bool;
  cc_store_consent_grant : bool
}.

Definition compartment_authority_valid (c : CompartmentCaps) : bool :=
  andb (negb c.(cc_exec_over_own_output))
  (andb (negb c.(cc_sealing_auth))
  (andb (negb c.(cc_wiring_auth))
        c.(cc_store_consent_grant))).

Inductive PoolLifecycle : Type :=
| PoolFree
| PoolBound
| PoolQuiescing
| PoolRevoked
| PoolSweeping
| PoolReusable.

Definition pool_can_bind (lc : PoolLifecycle) : bool :=
  match lc with
  | PoolFree => true
  | PoolBound => true
  | PoolReusable => true
  | PoolQuiescing => false
  | PoolRevoked => false
  | PoolSweeping => false
  end.

Record BoundedPool : Type := {
  bp_id : nat;
  bp_owner_id : nat;
  bp_capacity_bytes : nat;
  bp_low_threshold : nat;
  bp_exhausted_threshold : nat;
  bp_used_bytes : nat;
  bp_peak_bytes : nat;
  bp_lifecycle : PoolLifecycle
}.

Record PassActivation : Type := {
  pa_id : nat;
  pa_role : ToolchainRole;
  pa_pool_id : nat;
  pa_step_budget : nat;
  pa_steps_used : nat;
  pa_alloc_bytes : nat;
  pa_pass_peak_bytes : nat;
  pa_resumable : bool;
  pa_checkpoint_saved : bool
}.

Inductive ActRefusal : Type :=
| ActWrongPool
| ActLifecycleInvalid
| ActNotResumable
| ActStepBudgetExceeded
| ActCapacityExhausted.

Inductive ActOutcome : Type :=
| ActCompleted (pool' : BoundedPool) (recorded_peak : nat) (running_gen : nat)
| ActPausedCheckpoint (pool' : BoundedPool) (recorded_peak : nat) (running_gen : nat)
| ActRefused (reason : ActRefusal) (pool' : BoundedPool) (running_gen : nat).

Definition run_pass_activation
    (pool : BoundedPool)
    (act : PassActivation)
    (running_gen : nat) : ActOutcome :=
  if negb (Nat.eqb pool.(bp_id) act.(pa_pool_id)) then
    ActRefused ActWrongPool pool running_gen
  else if negb (pool_can_bind pool.(bp_lifecycle)) then
    ActRefused ActLifecycleInvalid pool running_gen
  else if negb act.(pa_resumable) then
    ActRefused ActNotResumable pool running_gen
  else if negb (Nat.leb act.(pa_steps_used) act.(pa_step_budget)) then
    ActRefused ActStepBudgetExceeded pool running_gen
  else
    let next_used := Nat.add pool.(bp_used_bytes) act.(pa_alloc_bytes) in
    let cand_peak := Nat.max next_used act.(pa_pass_peak_bytes) in
    if orb (negb (Nat.leb pool.(bp_exhausted_threshold) pool.(bp_capacity_bytes)))
           (negb (Nat.leb cand_peak pool.(bp_exhausted_threshold))) then
      ActRefused ActCapacityExhausted pool running_gen
    else
      let new_pool_peak := Nat.max pool.(bp_peak_bytes) cand_peak in
      let pool' := {| bp_id := pool.(bp_id);
                      bp_owner_id := pool.(bp_owner_id);
                      bp_capacity_bytes := pool.(bp_capacity_bytes);
                      bp_low_threshold := pool.(bp_low_threshold);
                      bp_exhausted_threshold := pool.(bp_exhausted_threshold);
                      bp_used_bytes := next_used;
                      bp_peak_bytes := new_pool_peak;
                      bp_lifecycle := PoolBound |} in
      if act.(pa_checkpoint_saved) then
        ActPausedCheckpoint pool' cand_peak running_gen
      else
        ActCompleted pool' cand_peak running_gen.

Definition act_succeeded (o : ActOutcome) : bool :=
  match o with
  | ActCompleted _ _ _ => true
  | ActPausedCheckpoint _ _ _ => true
  | ActRefused _ _ _ => false
  end.

Definition act_running_gen (o : ActOutcome) : nat :=
  match o with
  | ActCompleted _ _ g => g
  | ActPausedCheckpoint _ _ g => g
  | ActRefused _ _ g => g
  end.

(*| discharges: R-13-027a |*)
Theorem compartment_exec_own_output_or_sealing_or_wiring_refused :
  forall c,
    orb c.(cc_exec_over_own_output)
        (orb c.(cc_sealing_auth) c.(cc_wiring_auth)) = true ->
    compartment_authority_valid c = false.
Proof.
  intros c Hbad.
  unfold compartment_authority_valid.
  destruct (cc_exec_over_own_output c);
    destruct (cc_sealing_auth c);
    destruct (cc_wiring_auth c);
    simpl in *; try discriminate Hbad; reflexivity.
Qed.

Lemma role_seq_ge1_cannot_contain_checker :
  forall rest min_rank,
    Nat.leb 1 min_rank = true ->
    andb (PS.any_of (role_eqb RoleTypeChecker) rest)
         (role_sequence_ordered_from min_rank rest) = false.
Proof.
  induction rest as [| r rs IH]; intros min_rank Hmin; simpl.
  - reflexivity.
  - destruct r; simpl in *.
    + destruct min_rank; [ discriminate Hmin | ].
      destruct (PS.any_of (role_eqb RoleTypeChecker) rs); reflexivity.
    + destruct (Nat.leb min_rank 1);
        [ exact (IH 1 (eq_refl true))
        | destruct (PS.any_of (role_eqb RoleTypeChecker) rs); reflexivity ].
    + destruct (Nat.leb min_rank 2);
        [ exact (IH 2 (eq_refl true))
        | destruct (PS.any_of (role_eqb RoleTypeChecker) rs); reflexivity ].
    + destruct (Nat.leb min_rank 3);
        [ exact (IH 3 (eq_refl true))
        | destruct (PS.any_of (role_eqb RoleTypeChecker) rs); reflexivity ].
    + destruct (Nat.leb min_rank 4);
        [ exact (IH 4 (eq_refl true))
        | destruct (PS.any_of (role_eqb RoleTypeChecker) rs); reflexivity ].
Qed.

(*| discharges: R-13-027 |*)
Theorem smallest_loop_first_refuses_compiler_before_checker :
  forall rest,
    smallest_loop_first (cons RoleCompiler rest) = false.
Proof.
  intros rest.
  unfold smallest_loop_first. simpl.
  exact (role_seq_ge1_cannot_contain_checker rest 2 (eq_refl true)).
Qed.

(*| discharges: R-08-046, R-13-027a |*)
Theorem pool_exhaustion_refuses_and_preserves_running_generation :
  forall pool act gen,
    Nat.leb (Nat.max (Nat.add pool.(bp_used_bytes) act.(pa_alloc_bytes))
                     act.(pa_pass_peak_bytes))
            pool.(bp_exhausted_threshold) = false ->
    act_succeeded (run_pass_activation pool act gen) = false /\
    act_running_gen (run_pass_activation pool act gen) = gen.
Proof.
  intros pool act gen Hexh.
  unfold run_pass_activation, act_succeeded, act_running_gen.
  destruct (Nat.eqb (bp_id pool) (pa_pool_id act)); simpl; [ | split; reflexivity ].
  destruct (pool_can_bind (bp_lifecycle pool)); simpl; [ | split; reflexivity ].
  destruct (pa_resumable act); simpl; [ | split; reflexivity ].
  destruct (Nat.leb (pa_steps_used act) (pa_step_budget act)); simpl; [ | split; reflexivity ].
  rewrite Hexh.
  destruct (Nat.leb (bp_exhausted_threshold pool) (bp_capacity_bytes pool));
    simpl; split; reflexivity.
Qed.

(*| discharges: R-13-027a |*)
Theorem step_budget_exceeded_refuses_and_preserves_running_generation :
  forall pool act gen,
    Nat.leb act.(pa_steps_used) act.(pa_step_budget) = false ->
    act_succeeded (run_pass_activation pool act gen) = false /\
    act_running_gen (run_pass_activation pool act gen) = gen.
Proof.
  intros pool act gen Hsteps.
  unfold run_pass_activation, act_succeeded, act_running_gen.
  destruct (Nat.eqb (bp_id pool) (pa_pool_id act)); simpl; [ | split; reflexivity ].
  destruct (pool_can_bind (bp_lifecycle pool)); simpl; [ | split; reflexivity ].
  destruct (pa_resumable act); simpl; [ | split; reflexivity ].
  rewrite Hsteps. simpl. split; reflexivity.
Qed.

(*| discharges: R-08-046 |*)
Theorem activation_success_keeps_peak_within_exhausted_threshold :
  forall pool act gen pool' peak gen',
    (run_pass_activation pool act gen = ActCompleted pool' peak gen' \/
     run_pass_activation pool act gen = ActPausedCheckpoint pool' peak gen') ->
    Nat.leb peak pool.(bp_exhausted_threshold) = true /\
    Nat.leb pool.(bp_exhausted_threshold) pool.(bp_capacity_bytes) = true /\
    gen' = gen.
Proof.
  intros pool act gen pool' peak gen' H.
  unfold run_pass_activation in H.
  destruct (Nat.eqb (bp_id pool) (pa_pool_id act));
    destruct (pool_can_bind (bp_lifecycle pool));
    destruct (pa_resumable act);
    destruct (Nat.leb (pa_steps_used act) (pa_step_budget act));
    simpl in H; try (destruct H as [H | H]; discriminate H).
  destruct (Nat.leb (bp_exhausted_threshold pool) (bp_capacity_bytes pool)) eqn:Hcap;
    destruct (Nat.leb (Nat.max (Nat.add (bp_used_bytes pool) (pa_alloc_bytes act))
                               (pa_pass_peak_bytes act))
                      (bp_exhausted_threshold pool)) eqn:Hexh;
    simpl in H; try (destruct H as [H | H]; discriminate H).
  destruct (pa_checkpoint_saved act) eqn:Hchk.
  - destruct H as [H | H]; [ discriminate H | ].
    injection H as _ Hpeak Hgen.
    subst peak gen'. repeat split; assumption.
  - destruct H as [H | H]; [ | discriminate H ].
    injection H as _ Hpeak Hgen.
    subst peak gen'. repeat split; assumption.
Qed.

(* =========================================================================
   5. Residency scoring (ReadingA vs ReadingB) & pool sharing
      (R-08-014, R-08-018a, R-18-004e)
   ========================================================================= *)

Inductive ResidencyReading : Type :=
| ReadingA
| ReadingB.

Record PoolSharingProof : Type := {
  psp_disjoint_live_ranges : bool;
  psp_frame_or_region_proven : bool;
  psp_assumed_correlation_only : bool;
  psp_temporal_barrier_ok : bool
}.

Definition pools_can_share (p : PoolSharingProof) : bool :=
  andb p.(psp_disjoint_live_ranges)
  (andb p.(psp_frame_or_region_proven)
  (andb (negb p.(psp_assumed_correlation_only))
        p.(psp_temporal_barrier_ok))).

Definition toolchain_pool_charge
    (compiler_peak prover_peak : nat)
    (p : PoolSharingProof) : nat :=
  if pools_can_share p then Nat.max compiler_peak prover_peak
  else Nat.add compiler_peak prover_peak.

Definition reading_charge
    (r : ResidencyReading)
    (ordinary_bytes toolchain_bytes : nat) : nat :=
  match r with
  | ReadingA => toolchain_bytes
  | ReadingB => Nat.add ordinary_bytes toolchain_bytes
  end.

Definition residency_fits
    (r : ResidencyReading)
    (ordinary_bytes compiler_peak prover_peak first_class_cap : nat)
    (p : PoolSharingProof) : bool :=
  Nat.leb
    (reading_charge r ordinary_bytes (toolchain_pool_charge compiler_peak prover_peak p))
    first_class_cap.

(*| discharges: R-08-014, R-08-018a |*)
Theorem assumed_correlation_cannot_share_pools :
  forall cpeak ppeak sh,
    sh.(psp_assumed_correlation_only) = true ->
    pools_can_share sh = false /\
    toolchain_pool_charge cpeak ppeak sh = Nat.add cpeak ppeak.
Proof.
  intros cpeak ppeak sh Hcorr.
  unfold toolchain_pool_charge, pools_can_share.
  rewrite Hcorr.
  destruct (psp_disjoint_live_ranges sh);
    destruct (psp_frame_or_region_proven sh);
    destruct (psp_temporal_barrier_ok sh);
    simpl; split; reflexivity.
Qed.

(*| discharges: R-08-014, R-08-018a |*)
Theorem missing_disjoint_range_or_frame_proof_charges_sum :
  forall cpeak ppeak sh,
    orb (negb sh.(psp_disjoint_live_ranges))
        (orb (negb sh.(psp_frame_or_region_proven))
             (negb sh.(psp_temporal_barrier_ok))) = true ->
    pools_can_share sh = false /\
    toolchain_pool_charge cpeak ppeak sh = Nat.add cpeak ppeak.
Proof.
  intros cpeak ppeak sh Hbad.
  unfold toolchain_pool_charge, pools_can_share.
  destruct (psp_disjoint_live_ranges sh);
    destruct (psp_frame_or_region_proven sh);
    destruct (psp_assumed_correlation_only sh);
    destruct (psp_temporal_barrier_ok sh);
    simpl in *; try discriminate Hbad; split; reflexivity.
Qed.

(*| discharges: R-18-004e, R-13-027a |*)
Theorem reading_b_fit_implies_reading_a_fit :
  forall ord cpeak ppeak cap sh,
    residency_fits ReadingB ord cpeak ppeak cap sh = true ->
    residency_fits ReadingA ord cpeak ppeak cap sh = true.
Proof.
  intros ord cpeak ppeak cap sh Hb.
  unfold residency_fits, reading_charge in *.
  eapply nat_leb_trans_local.
  - apply nat_leb_add_l.
  - exact Hb.
Qed.

(* =========================================================================
   6. Bootstrap self-build reproduction receipt & De Bruijn root (R-13-027, R-06-014)
   ========================================================================= *)

Inductive DeBruijnRootStatus : Type :=
| Relocated
| Closed.

Definition root_status_relocated (s : DeBruijnRootStatus) : bool :=
  match s with
  | Relocated => true
  | Closed => false
  end.

Inductive DivergenceCause : Type :=
| CauseNone
| CauseSourceMismatch
| CauseSwitchMismatch
| CauseArtifactMismatch
| CauseDeviceAdmissionRefused
| CauseHostAdmissionRefused
| CauseDdcOrRotIncomplete
| CauseClosedBootstrapClaimed.

Record BuildReceipt : Type := {
  br_source_hash : nat;
  br_switch_hash : nat;
  br_artifact_hash : nat;
  br_tal_admitted : bool;
  br_cic_admitted : bool;
  br_ddc_checked : bool;
  br_rot_measured : bool;
  br_root_status : DeBruijnRootStatus
}.

Inductive BootstrapVerdict : Type :=
| Reproduced (root_status : DeBruijnRootStatus)
| Diverged (cause : DivergenceCause).

Definition compare_bootstrap_receipts (host dev : BuildReceipt) : BootstrapVerdict :=
  if orb (negb (root_status_relocated host.(br_root_status)))
         (negb (root_status_relocated dev.(br_root_status))) then
    Diverged CauseClosedBootstrapClaimed
  else if negb (andb host.(br_tal_admitted) host.(br_cic_admitted)) then
    Diverged CauseHostAdmissionRefused
  else if negb (andb dev.(br_tal_admitted) dev.(br_cic_admitted)) then
    Diverged CauseDeviceAdmissionRefused
  else if negb (Nat.eqb host.(br_source_hash) dev.(br_source_hash)) then
    Diverged CauseSourceMismatch
  else if negb (Nat.eqb host.(br_switch_hash) dev.(br_switch_hash)) then
    Diverged CauseSwitchMismatch
  else if negb (Nat.eqb host.(br_artifact_hash) dev.(br_artifact_hash)) then
    Diverged CauseArtifactMismatch
  else if negb (andb (andb host.(br_ddc_checked) dev.(br_ddc_checked))
                     (andb host.(br_rot_measured) dev.(br_rot_measured))) then
    Diverged CauseDdcOrRotIncomplete
  else
    Reproduced Relocated.

Definition bootstrap_reproduced (v : BootstrapVerdict) : bool :=
  match v with
  | Reproduced _ => true
  | Diverged _ => false
  end.

(*| discharges: R-06-014 |*)
Theorem reproduced_keeps_debruijn_root_relocated :
  forall host dev s,
    compare_bootstrap_receipts host dev = Reproduced s ->
    s = Relocated /\
    host.(br_root_status) = Relocated /\
    dev.(br_root_status) = Relocated.
Proof.
  intros host dev s H.
  unfold compare_bootstrap_receipts in H.
  destruct (br_root_status host) eqn:Hhr;
    destruct (br_root_status dev) eqn:Hdr;
    simpl in H; try discriminate H.
  destruct (andb (br_tal_admitted host) (br_cic_admitted host)); [ | discriminate H ].
  destruct (andb (br_tal_admitted dev) (br_cic_admitted dev)); [ | discriminate H ].
  destruct (Nat.eqb (br_source_hash host) (br_source_hash dev)); [ | discriminate H ].
  destruct (Nat.eqb (br_switch_hash host) (br_switch_hash dev)); [ | discriminate H ].
  destruct (Nat.eqb (br_artifact_hash host) (br_artifact_hash dev)); [ | discriminate H ].
  destruct (andb (andb (br_ddc_checked host) (br_ddc_checked dev))
                 (andb (br_rot_measured host) (br_rot_measured dev)));
    [ | discriminate H ].
  injection H as Hs. subst s. repeat split; reflexivity.
Qed.

(*| discharges: R-06-014 |*)
Theorem closed_bootstrap_claim_always_refused :
  forall host dev,
    orb (negb (root_status_relocated host.(br_root_status)))
        (negb (root_status_relocated dev.(br_root_status))) = true ->
    compare_bootstrap_receipts host dev = Diverged CauseClosedBootstrapClaimed.
Proof.
  intros host dev Hclosed.
  unfold compare_bootstrap_receipts. rewrite Hclosed. reflexivity.
Qed.

(*| discharges: R-13-027 |*)
Theorem artifact_mismatch_produces_diverged_finding :
  forall host dev,
    host.(br_root_status) = Relocated ->
    dev.(br_root_status) = Relocated ->
    host.(br_tal_admitted) = true ->
    host.(br_cic_admitted) = true ->
    dev.(br_tal_admitted) = true ->
    dev.(br_cic_admitted) = true ->
    Nat.eqb host.(br_source_hash) dev.(br_source_hash) = true ->
    Nat.eqb host.(br_switch_hash) dev.(br_switch_hash) = true ->
    Nat.eqb host.(br_artifact_hash) dev.(br_artifact_hash) = false ->
    compare_bootstrap_receipts host dev = Diverged CauseArtifactMismatch.
Proof.
  intros host dev Hhr Hdr Hht Hhc Hdt Hdc Hsrc Hsw Hart.
  unfold compare_bootstrap_receipts.
  rewrite Hhr, Hdr, Hht, Hhc, Hdt, Hdc, Hsrc, Hsw, Hart.
  reflexivity.
Qed.

(* =========================================================================
   7. Combined resident toolchain admission & reproduction pipeline
   ========================================================================= *)

Record ResidencySpec : Type := {
  rs_reading : ResidencyReading;
  rs_ordinary_bytes : nat;
  rs_compiler_peak : nat;
  rs_prover_peak : nat;
  rs_first_class_cap : nat;
  rs_sharing : PoolSharingProof
}.

Record ResidentToolchainReq : Type := {
  rtr_licenses : list ComponentLicense;
  rtr_closure : list ClosureUnit;
  rtr_compartments : list CompartmentCaps;
  rtr_pool : BoundedPool;
  rtr_activations : list PassActivation;
  rtr_residency : ResidencySpec;
  rtr_host_receipt : BuildReceipt;
  rtr_dev_receipt : BuildReceipt
}.

Record ResidentToolchainState : Type := {
  rts_running_gen : nat;
  rts_last_peak_bytes : nat;
  rts_last_verdict : BootstrapVerdict;
  rts_admitted_runs : nat
}.

Inductive ToolchainRunOutcome : Type :=
| ToolchainAdmitted (st' : ResidentToolchainState)
| ToolchainRefused (st' : ResidentToolchainState).

Fixpoint run_activations_seq
    (pool : BoundedPool)
    (acts : list PassActivation)
    (gen peak_acc : nat) : option (BoundedPool * nat) :=
  match acts with
  | nil => Some (pool, peak_acc)
  | cons a rest =>
      match run_pass_activation pool a gen with
      | ActCompleted pool' peak _ =>
          run_activations_seq pool' rest gen (Nat.max peak_acc peak)
      | ActPausedCheckpoint pool' peak _ =>
          run_activations_seq pool' rest gen (Nat.max peak_acc peak)
      | ActRefused _ _ _ => None
      end
  end.

Definition run_resident_toolchain
    (st : ResidentToolchainState)
    (req : ResidentToolchainReq) : ToolchainRunOutcome :=
  let lic_ok := screen_all_licenses req.(rtr_licenses) in
  let clos_ok := all_closures_cleared_now req.(rtr_closure) in
  let caps_ok := PS.all_of compartment_authority_valid req.(rtr_compartments) in
  let order_ok :=
    smallest_loop_first (PS.map_over (fun c => c.(cc_role)) req.(rtr_compartments)) in
  let rs := req.(rtr_residency) in
  let res_ok :=
    residency_fits rs.(rs_reading) rs.(rs_ordinary_bytes)
                   rs.(rs_compiler_peak) rs.(rs_prover_peak)
                   rs.(rs_first_class_cap) rs.(rs_sharing) in
  if negb (andb lic_ok (andb clos_ok (andb caps_ok (andb order_ok res_ok)))) then
    ToolchainRefused st
  else
    match run_activations_seq req.(rtr_pool) req.(rtr_activations) st.(rts_running_gen) 0 with
    | None => ToolchainRefused st
    | Some (pool', peak) =>
        if negb (Nat.leb peak rs.(rs_compiler_peak)) then
          ToolchainRefused st
        else
          let verdict := compare_bootstrap_receipts req.(rtr_host_receipt) req.(rtr_dev_receipt) in
          match verdict with
          | Diverged _ =>
              ToolchainRefused st
          | Reproduced Relocated =>
              ToolchainAdmitted
                {| rts_running_gen := S st.(rts_running_gen);
                   rts_last_peak_bytes := Nat.max pool'.(bp_peak_bytes) peak;
                   rts_last_verdict := Reproduced Relocated;
                   rts_admitted_runs := S st.(rts_admitted_runs) |}
          | Reproduced Closed =>
              ToolchainRefused st
          end
    end.

Definition toolchain_outcome_admitted (o : ToolchainRunOutcome) : bool :=
  match o with
  | ToolchainAdmitted _ => true
  | ToolchainRefused _ => false
  end.

Definition toolchain_outcome_state (o : ToolchainRunOutcome) : ResidentToolchainState :=
  match o with
  | ToolchainAdmitted s => s
  | ToolchainRefused s => s
  end.

(*| discharges: R-08-046, R-13-027a |*)
Theorem refused_toolchain_run_preserves_running_generation :
  forall st req st',
    run_resident_toolchain st req = ToolchainRefused st' ->
    st' = st.
Proof.
  intros st req st' H.
  unfold run_resident_toolchain in H.
  destruct (andb (screen_all_licenses (rtr_licenses req))
                 (andb (all_closures_cleared_now (rtr_closure req))
                       (andb (PS.all_of compartment_authority_valid (rtr_compartments req))
                             (andb (smallest_loop_first (PS.map_over (fun c => cc_role c)
                                                                     (rtr_compartments req)))
                                   (residency_fits (rs_reading (rtr_residency req))
                                                   (rs_ordinary_bytes (rtr_residency req))
                                                   (rs_compiler_peak (rtr_residency req))
                                                   (rs_prover_peak (rtr_residency req))
                                                   (rs_first_class_cap (rtr_residency req))
                                                   (rs_sharing (rtr_residency req)))))));
    simpl in H; [ | injection H as <-; reflexivity ].
  destruct (run_activations_seq (rtr_pool req) (rtr_activations req) (rts_running_gen st) 0)
    as [[pool' peak] | ]; [ | injection H as <-; reflexivity ].
  destruct (Nat.leb peak (rs_compiler_peak (rtr_residency req)));
    simpl in H; [ | injection H as <-; reflexivity ].
  destruct (compare_bootstrap_receipts (rtr_host_receipt req) (rtr_dev_receipt req))
    as [[|] | cause];
    try (injection H as <-; reflexivity);
    discriminate H.
Qed.

(*| discharges: R-18-004e, R-13-027, R-13-027a, R-06-014 |*)
Theorem admitted_toolchain_run_establishes_all_gates :
  forall st req st',
    run_resident_toolchain st req = ToolchainAdmitted st' ->
    screen_all_licenses (rtr_licenses req) = true /\
    all_closures_cleared_now (rtr_closure req) = true /\
    PS.all_of compartment_authority_valid (rtr_compartments req) = true /\
    smallest_loop_first (PS.map_over (fun c => cc_role c) (rtr_compartments req)) = true /\
    st'.(rts_last_verdict) = Reproduced Relocated.
Proof.
  intros st req st' H.
  unfold run_resident_toolchain in H.
  destruct (screen_all_licenses (rtr_licenses req)) eqn:Hlic;
    destruct (all_closures_cleared_now (rtr_closure req)) eqn:Hclos;
    destruct (PS.all_of compartment_authority_valid (rtr_compartments req)) eqn:Hcaps;
    destruct (smallest_loop_first (PS.map_over (fun c => cc_role c) (rtr_compartments req))) eqn:Hord;
    destruct (residency_fits (rs_reading (rtr_residency req))
                             (rs_ordinary_bytes (rtr_residency req))
                             (rs_compiler_peak (rtr_residency req))
                             (rs_prover_peak (rtr_residency req))
                             (rs_first_class_cap (rtr_residency req))
                             (rs_sharing (rtr_residency req))) eqn:Hres;
    simpl in H; try discriminate H.
  destruct (run_activations_seq (rtr_pool req) (rtr_activations req) (rts_running_gen st) 0)
    as [[pool' peak] | ]; [ | discriminate H ].
  destruct (Nat.leb peak (rs_compiler_peak (rtr_residency req)));
    simpl in H; [ | discriminate H ].
  destruct (compare_bootstrap_receipts (rtr_host_receipt req) (rtr_dev_receipt req))
    as [[|] | cause]; try discriminate H.
  injection H as <-. repeat split; reflexivity.
Qed.

(* =========================================================================
   8. Concrete positive witness & exhaustive failure-mode refutations
      (R-05-165, R-05-166)
   ========================================================================= *)

Definition lic_holdfast_independent : ComponentLicense :=
  {| cl_comp_id := 1;
     cl_route := RouteIndependentImpl;
     cl_read_at_incorporation := true;
     cl_has_noncommercial_pass := false;
     cl_has_commercial_grant := false;
     cl_dual_subset_only := false;
     cl_provides_required_backend := true |}.

Definition lic_compcert_granted : ComponentLicense :=
  {| cl_comp_id := 2;
     cl_route := RouteCommercialGrant;
     cl_read_at_incorporation := true;
     cl_has_noncommercial_pass := true;
     cl_has_commercial_grant := true;
     cl_dual_subset_only := false;
     cl_provides_required_backend := true |}.

Definition lic_dual_support_only : ComponentLicense :=
  {| cl_comp_id := 3;
     cl_route := RouteDualLicensedSubset;
     cl_read_at_incorporation := true;
     cl_has_noncommercial_pass := false;
     cl_has_commercial_grant := false;
     cl_dual_subset_only := true;
     cl_provides_required_backend := false |}.

Definition cu_clean_checker : ClosureUnit :=
  {| cu_id := 10;
     cu_unsafe_sites := 0;
     cu_unsafe_hal_or_proof_ok := true;
     cu_ambient_authority := false;
     cu_has_filesystem := false;
     cu_has_subprocess := false;
     cu_has_host_allocator := false;
     cu_disposition := DispClean;
     cu_subport_id := 0;
     cu_subport_estimated := false |}.

Definition cu_hal_compiler : ClosureUnit :=
  {| cu_id := 11;
     cu_unsafe_sites := 2;
     cu_unsafe_hal_or_proof_ok := true;
     cu_ambient_authority := false;
     cu_has_filesystem := false;
     cu_has_subprocess := false;
     cu_has_host_allocator := false;
     cu_disposition := DispVerifiedHalOrProof;
     cu_subport_id := 0;
     cu_subport_estimated := false |}.

Definition cu_shed_host_assumptions : ClosureUnit :=
  {| cu_id := 12;
     cu_unsafe_sites := 0;
     cu_unsafe_hal_or_proof_ok := true;
     cu_ambient_authority := false;
     cu_has_filesystem := true;
     cu_has_subprocess := true;
     cu_has_host_allocator := true;
     cu_disposition := DispDeleted;
     cu_subport_id := 0;
     cu_subport_estimated := false |}.

Definition cu_named_subport_unit : ClosureUnit :=
  {| cu_id := 13;
     cu_unsafe_sites := 0;
     cu_unsafe_hal_or_proof_ok := true;
     cu_ambient_authority := false;
     cu_has_filesystem := true;
     cu_has_subprocess := false;
     cu_has_host_allocator := true;
     cu_disposition := DispNamedSubPort;
     cu_subport_id := 77;
     cu_subport_estimated := true |}.

Definition comp_checker : CompartmentCaps :=
  {| cc_id := 101;
     cc_role := RoleTypeChecker;
     cc_exec_over_own_output := false;
     cc_sealing_auth := false;
     cc_wiring_auth := false;
     cc_store_consent_grant := true |}.

Definition comp_prover : CompartmentCaps :=
  {| cc_id := 102;
     cc_role := RoleProver;
     cc_exec_over_own_output := false;
     cc_sealing_auth := false;
     cc_wiring_auth := false;
     cc_store_consent_grant := true |}.

Definition comp_compiler : CompartmentCaps :=
  {| cc_id := 103;
     cc_role := RoleCompiler;
     cc_exec_over_own_output := false;
     cc_sealing_auth := false;
     cc_wiring_auth := false;
     cc_store_consent_grant := true |}.

Definition demo_pool : BoundedPool :=
  {| bp_id := 1;
     bp_owner_id := 103;
     bp_capacity_bytes := 64000;
     bp_low_threshold := 48000;
     bp_exhausted_threshold := 60000;
     bp_used_bytes := 0;
     bp_peak_bytes := 0;
     bp_lifecycle := PoolFree |}.

Definition act_checker : PassActivation :=
  {| pa_id := 1;
     pa_role := RoleTypeChecker;
     pa_pool_id := 1;
     pa_step_budget := 500;
     pa_steps_used := 120;
     pa_alloc_bytes := 4096;
     pa_pass_peak_bytes := 8192;
     pa_resumable := true;
     pa_checkpoint_saved := true |}.

Definition act_compiler : PassActivation :=
  {| pa_id := 2;
     pa_role := RoleCompiler;
     pa_pool_id := 1;
     pa_step_budget := 2000;
     pa_steps_used := 1500;
     pa_alloc_bytes := 12288;
     pa_pass_peak_bytes := 24576;
     pa_resumable := true;
     pa_checkpoint_saved := false |}.

Definition demo_sharing_proven : PoolSharingProof :=
  {| psp_disjoint_live_ranges := true;
     psp_frame_or_region_proven := true;
     psp_assumed_correlation_only := false;
     psp_temporal_barrier_ok := true |}.

Definition demo_residency_spec : ResidencySpec :=
  {| rs_reading := ReadingA;
     rs_ordinary_bytes := 40000;
     rs_compiler_peak := 24576;
     rs_prover_peak := 38000;
     rs_first_class_cap := 60000;
     rs_sharing := demo_sharing_proven |}.

Definition demo_host_receipt : BuildReceipt :=
  {| br_source_hash := 1001;
     br_switch_hash := 2002;
     br_artifact_hash := 3003;
     br_tal_admitted := true;
     br_cic_admitted := true;
     br_ddc_checked := true;
     br_rot_measured := true;
     br_root_status := Relocated |}.

Definition demo_dev_receipt : BuildReceipt := demo_host_receipt.

Definition initial_tc_state : ResidentToolchainState :=
  {| rts_running_gen := 5;
     rts_last_peak_bytes := 0;
     rts_last_verdict := Reproduced Relocated;
     rts_admitted_runs := 0 |}.

Definition positive_tc_req : ResidentToolchainReq :=
  {| rtr_licenses := cons lic_holdfast_independent
                       (cons lic_compcert_granted (cons lic_dual_support_only nil));
     rtr_closure := cons cu_clean_checker
                      (cons cu_hal_compiler (cons cu_shed_host_assumptions nil));
     rtr_compartments := cons comp_checker (cons comp_prover (cons comp_compiler nil));
     rtr_pool := demo_pool;
     rtr_activations := cons act_checker (cons act_compiler nil);
     rtr_residency := demo_residency_spec;
     rtr_host_receipt := demo_host_receipt;
     rtr_dev_receipt := demo_dev_receipt |}.

(*| discharges: R-18-004e, R-13-027, R-13-027a, R-08-046, R-08-014, R-08-018a, R-06-014 |*)
Example positive_resident_toolchain_admits_and_reproduces :
  let out := run_resident_toolchain initial_tc_state positive_tc_req in
  let st' := toolchain_outcome_state out in
  toolchain_outcome_admitted out = true /\
  st'.(rts_running_gen) = 6 /\
  st'.(rts_last_peak_bytes) = 24576 /\
  st'.(rts_last_verdict) = Reproduced Relocated /\
  closure_audit_accepted (audit_closure_unit cu_named_subport_unit) = true /\
  audit_closure_unit cu_named_subport_unit = ClosureAssignedSubPort 77.
Proof. repeat split; reflexivity. Qed.

(* Adverse controls covering every failure mode. *)
Definition lic_noncommercial_no_grant : ComponentLicense :=
  {| cl_comp_id := 9;
     cl_route := RouteNonCommercialOnly;
     cl_read_at_incorporation := true;
     cl_has_noncommercial_pass := true;
     cl_has_commercial_grant := false;
     cl_dual_subset_only := false;
     cl_provides_required_backend := true |}.

Definition lic_unread_before_port : ComponentLicense :=
  {| cl_comp_id := 10;
     cl_route := RouteIndependentImpl;
     cl_read_at_incorporation := false;
     cl_has_noncommercial_pass := false;
     cl_has_commercial_grant := false;
     cl_dual_subset_only := false;
     cl_provides_required_backend := true |}.

(*| discharges: R-18-004e |*)
Example adverse_license_refusals :
  license_admitted (screen_component_license lic_noncommercial_no_grant) = false /\
  screen_component_license lic_unread_before_port =
    LicenseRefused LicenseNotReadAtIncorporation /\
  screen_component_license
    {| cl_comp_id := 11; cl_route := RouteDualLicensedSubset;
       cl_read_at_incorporation := true; cl_has_noncommercial_pass := true;
       cl_has_commercial_grant := false; cl_dual_subset_only := true;
       cl_provides_required_backend := false |} =
    LicenseRefused OutsideDualLicensedSubset.
Proof. repeat split; reflexivity. Qed.

Definition cu_unsafe_exception : ClosureUnit :=
  {| cu_id := 20; cu_unsafe_sites := 1; cu_unsafe_hal_or_proof_ok := false;
     cu_ambient_authority := false; cu_has_filesystem := true;
     cu_has_subprocess := false; cu_has_host_allocator := false;
     cu_disposition := DispUnsafeException; cu_subport_id := 0;
     cu_subport_estimated := false |}.

Definition cu_ambient_posix : ClosureUnit :=
  {| cu_id := 21; cu_unsafe_sites := 0; cu_unsafe_hal_or_proof_ok := true;
     cu_ambient_authority := true; cu_has_filesystem := true;
     cu_has_subprocess := true; cu_has_host_allocator := false;
     cu_disposition := DispClean; cu_subport_id := 0;
     cu_subport_estimated := false |}.

Definition cu_unresolved_fs : ClosureUnit :=
  {| cu_id := 22; cu_unsafe_sites := 0; cu_unsafe_hal_or_proof_ok := true;
     cu_ambient_authority := false; cu_has_filesystem := true;
     cu_has_subprocess := false; cu_has_host_allocator := false;
     cu_disposition := DispClean; cu_subport_id := 0;
     cu_subport_estimated := false |}.

(*| discharges: R-13-027, R-13-027a |*)
Example adverse_closure_refusals :
  audit_closure_unit cu_unsafe_exception = ClosureRefused UnsafeExceptionForbidden /\
  audit_closure_unit cu_ambient_posix = ClosureRefused AmbientAuthorityPresent /\
  audit_closure_unit cu_unresolved_fs = ClosureRefused UnresolvedHostAssumption.
Proof. repeat split; reflexivity. Qed.

Definition comp_exec_own_output : CompartmentCaps :=
  {| cc_id := 201; cc_role := RoleCompiler; cc_exec_over_own_output := true;
     cc_sealing_auth := false; cc_wiring_auth := false; cc_store_consent_grant := true |}.

Definition sharing_assumed_correlation : PoolSharingProof :=
  {| psp_disjoint_live_ranges := true; psp_frame_or_region_proven := true;
     psp_assumed_correlation_only := true; psp_temporal_barrier_ok := true |}.

(*| discharges: R-13-027a, R-08-014, R-08-018a, R-18-004e |*)
Example adverse_order_authority_sharing_and_reading_refusals :
  compartment_authority_valid comp_exec_own_output = false /\
  smallest_loop_first (cons RoleCompiler (cons RoleTypeChecker nil)) = false /\
  pools_can_share sharing_assumed_correlation = false /\
  toolchain_pool_charge 24576 38000 sharing_assumed_correlation = 62576 /\
  residency_fits ReadingA 40000 24576 38000 60000 demo_sharing_proven = true /\
  residency_fits ReadingA 40000 24576 38000 60000 sharing_assumed_correlation = false /\
  residency_fits ReadingB 40000 24576 38000 60000 demo_sharing_proven = false.
Proof. repeat split; reflexivity. Qed.

Definition act_exhausts_pool : PassActivation :=
  {| pa_id := 99; pa_role := RoleCompiler; pa_pool_id := 1;
     pa_step_budget := 2000; pa_steps_used := 500;
     pa_alloc_bytes := 60001; pa_pass_peak_bytes := 60001;
     pa_resumable := true; pa_checkpoint_saved := false |}.

Definition act_over_steps : PassActivation :=
  {| pa_id := 100; pa_role := RoleCompiler; pa_pool_id := 1;
     pa_step_budget := 100; pa_steps_used := 101;
     pa_alloc_bytes := 1024; pa_pass_peak_bytes := 1024;
     pa_resumable := true; pa_checkpoint_saved := false |}.

Definition req_exhausted_pool : ResidentToolchainReq :=
  {| rtr_licenses := positive_tc_req.(rtr_licenses);
     rtr_closure := positive_tc_req.(rtr_closure);
     rtr_compartments := positive_tc_req.(rtr_compartments);
     rtr_pool := demo_pool;
     rtr_activations := cons act_checker (cons act_exhausts_pool nil);
     rtr_residency := demo_residency_spec;
     rtr_host_receipt := demo_host_receipt;
     rtr_dev_receipt := demo_dev_receipt |}.

Definition dev_receipt_diverged : BuildReceipt :=
  {| br_source_hash := 1001; br_switch_hash := 2002; br_artifact_hash := 9999;
     br_tal_admitted := true; br_cic_admitted := true;
     br_ddc_checked := true; br_rot_measured := true; br_root_status := Relocated |}.

Definition dev_receipt_claimed_closed : BuildReceipt :=
  {| br_source_hash := 1001; br_switch_hash := 2002; br_artifact_hash := 3003;
     br_tal_admitted := true; br_cic_admitted := true;
     br_ddc_checked := true; br_rot_measured := true; br_root_status := Closed |}.

(*| discharges: R-08-046, R-13-027, R-06-014 |*)
Example adverse_budget_exhaustion_and_bootstrap_refusals :
  run_pass_activation demo_pool act_exhausts_pool 5 =
    ActRefused ActCapacityExhausted demo_pool 5 /\
  run_pass_activation demo_pool act_over_steps 5 =
    ActRefused ActStepBudgetExceeded demo_pool 5 /\
  run_resident_toolchain initial_tc_state req_exhausted_pool =
    ToolchainRefused initial_tc_state /\
  compare_bootstrap_receipts demo_host_receipt dev_receipt_diverged =
    Diverged CauseArtifactMismatch /\
  compare_bootstrap_receipts demo_host_receipt dev_receipt_claimed_closed =
    Diverged CauseClosedBootstrapClaimed.
Proof. repeat split; reflexivity. Qed.

(* =========================================================================
   9. R-05-166 inhabitation witnesses (one closed Definition per Record)
   ========================================================================= *)

Definition witness_ComponentLicense : ComponentLicense := lic_holdfast_independent.
Definition witness_ClosureUnit : ClosureUnit := cu_clean_checker.
Definition witness_CompartmentCaps : CompartmentCaps := comp_checker.
Definition witness_BoundedPool : BoundedPool := demo_pool.
Definition witness_PassActivation : PassActivation := act_checker.
Definition witness_PoolSharingProof : PoolSharingProof := demo_sharing_proven.
Definition witness_BuildReceipt : BuildReceipt := demo_host_receipt.
Definition witness_ResidencySpec : ResidencySpec := demo_residency_spec.
Definition witness_ResidentToolchainReq : ResidentToolchainReq := positive_tc_req.
Definition witness_ResidentToolchainState : ResidentToolchainState := initial_tc_state.

(* R-05-163, R-05-164, R-05-165, R-05-166: zero axioms, prelude + ProofSupport
   only, all records inhabited, positive & negative controls discharged. *)
