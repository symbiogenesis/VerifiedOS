(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   DeviceGeneration.v

   Specification and non-vacuity model for M6.10-i on-device generation
   composition, trusted-path minting, offline scoped inclusion, and
   fixed-package reuse across generations:
   - Trusted-path mint ordering (R-13-027b): the crypto core generates and
     holds the non-exportable local generation signing key; the composer
     compartment holds neither the key nor a mint capability; the trusted-path
     prompt displays the exact roster hash and generation root; a one-use
     credential-gated consent act binds `(roster_hash, gen_root, nonce)` and
     authorizes one crypto-core mint. All three adverse mint cases (no
     consent, altered root after consent, absent credential) are refused.
   - Composition-mode entry/exit state machine (R-11-018): bounded mode
     transition from normal mode gated by an admission-checked edge
     certificate, runtime guard, dwell bound, bounded pending queues, and
     pre-reserved recovery state; clean exit returns to normal mode with zero
     lingering composition privilege on both completion and failure.
   - Offline scoped inclusion (R-13-023b, R-13-027): both a package-change
     generation and a reproducible base-image rebuild (R-13-026) complete with
     no network reachable; locally authored closures carry no publisher,
     whereas any fetched object inside an offline build lacking a logged
     transparency name stops installation rather than passing under cover of
     the local build.
   - Fixed-package reuse across generations (R-13-028, R-06-015a): unchanged
     package objects and HMAC-authenticated checked-set verdicts are reused
     only when every artifact, proof, source, contract, and context binding
     matches the admitted checked set; concrete-layout TAL and generation-wide
     wiring/resource checks always run fresh, and package proof-checking stays
     within the declared R-06-015a step and working-set budget.
   - A/B transactor staging, commit, and health-gated rollback handoff over
     [ObjectTransactor.v](ObjectTransactor.v) and
     [AdmissionPath.v](AdmissionPath.v).

   Assumptions and non-vacuity (R-05-163, R-05-164, R-05-165, R-05-166):
   - Zero axioms (`Closed under the global context`), prelude-only, and every
     declared record carries a closed `witness_<Record>` inhabitant.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-06-015a R-11-018 R-13-023b R-13-026
      R-13-027 R-13-027b R-13-028
   SHA256: f7c2defe0db0231222c42dba278cbb6b97181e0c8f44bf2ef6bb6074d6eb843b
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport AdmissionPath ObjectTransactor.

Module PS := ProofSupport.
Module AP := AdmissionPath.
Module OT := ObjectTransactor.

(* =========================================================================
   1. Small prelude helpers
   ========================================================================= *)

Definition bool_eqb (a b : bool) : bool := PS.bool_eqb a b.

Fixpoint sum_nat (l : list nat) : nat :=
  match l with
  | nil => 0
  | cons x xs => Nat.add x (sum_nat xs)
  end.

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

Lemma nat_eqb_refl_local : forall n : nat, Nat.eqb n n = true.
Proof. exact PS.nat_eqb_refl. Qed.

(* =========================================================================
   2. Trusted-path mint ordering (R-13-027b)
   ========================================================================= *)

Inductive MintRefusal : Type :=
| MintKeyExportable
| MintComposerPrivileged
| MintCoreNotEnrolled
| MintNoConsent
| MintCredentialAbsent
| MintUserDeclined
| MintNonceReused
| MintPromptMismatch
| MintRootOrRosterAltered.

Record CryptoCore : Type := {
  cc_key_id : nat;
  cc_enrolled : bool;
  cc_exportable : bool;
  cc_private_secret : nat;
  cc_used_nonces : list nat
}.

Record ComposerCap : Type := {
  comp_id : nat;
  comp_holds_signing_key : bool;
  comp_has_mint_cap : bool
}.

Record MintPrompt : Type := {
  mp_roster_hash : nat;
  mp_gen_root : nat;
  mp_nonce : nat;
  mp_shows_roster : bool;
  mp_shows_root : bool
}.

Record ConsentAct : Type := {
  ca_credential_ok : bool;
  ca_user_consented : bool;
  ca_prompt : MintPrompt
}.

Inductive MintOutcome : Type :=
| MintOk (sig : nat) (core_after : CryptoCore)
| MintErr (reason : MintRefusal).

Definition compute_mint_sig (key_id secret roster_hash gen_root nonce : nat) : nat :=
  Nat.add (Nat.mul 13 key_id)
    (Nat.add (Nat.mul 7 secret)
      (Nat.add (Nat.mul 5 roster_hash)
        (Nat.add (Nat.mul 3 gen_root) nonce))).

Definition trusted_path_mint
    (core : CryptoCore)
    (comp : ComposerCap)
    (req_roster_hash req_gen_root : nat)
    (consent : option ConsentAct) : MintOutcome :=
  if core.(cc_exportable) then MintErr MintKeyExportable
  else if orb comp.(comp_holds_signing_key) comp.(comp_has_mint_cap) then
    MintErr MintComposerPrivileged
  else if negb core.(cc_enrolled) then MintErr MintCoreNotEnrolled
  else
    match consent with
    | None => MintErr MintNoConsent
    | Some ca =>
        if negb ca.(ca_credential_ok) then MintErr MintCredentialAbsent
        else if negb ca.(ca_user_consented) then MintErr MintUserDeclined
        else
          let pr := ca.(ca_prompt) in
          if orb (negb pr.(mp_shows_roster)) (negb pr.(mp_shows_root)) then
            MintErr MintPromptMismatch
          else if PS.mem_nat pr.(mp_nonce) core.(cc_used_nonces) then
            MintErr MintNonceReused
          else if orb (negb (Nat.eqb pr.(mp_roster_hash) req_roster_hash))
                      (negb (Nat.eqb pr.(mp_gen_root) req_gen_root)) then
            MintErr MintRootOrRosterAltered
          else
            let sig := compute_mint_sig core.(cc_key_id) core.(cc_private_secret)
                         req_roster_hash req_gen_root pr.(mp_nonce) in
            let core' := {| cc_key_id := core.(cc_key_id);
                            cc_enrolled := core.(cc_enrolled);
                            cc_exportable := false;
                            cc_private_secret := core.(cc_private_secret);
                            cc_used_nonces := cons pr.(mp_nonce) core.(cc_used_nonces) |} in
            MintOk sig core'
    end.

Definition mint_succeeded (m : MintOutcome) : bool :=
  match m with
  | MintOk _ _ => true
  | MintErr _ => false
  end.

(*| discharges: R-13-027b |*)
Theorem mint_requires_unexportable_core_and_unprivileged_composer :
  forall core comp r g consent sig core',
    trusted_path_mint core comp r g consent = MintOk sig core' ->
    core.(cc_exportable) = false /\
    comp.(comp_holds_signing_key) = false /\
    comp.(comp_has_mint_cap) = false /\
    core.(cc_enrolled) = true.
Proof.
  intros core comp r g consent sig core' H.
  unfold trusted_path_mint in H.
  destruct (cc_exportable core) eqn:He; [ discriminate H | ].
  destruct (comp_holds_signing_key comp) eqn:Hk;
    destruct (comp_has_mint_cap comp) eqn:Hm; simpl in H; try discriminate H.
  destruct (cc_enrolled core) eqn:Hen; [ | discriminate H ].
  repeat split; reflexivity.
Qed.

(*| discharges: R-13-027b |*)
Theorem mint_refuses_no_consent :
  forall core comp r g,
    core.(cc_exportable) = false ->
    comp.(comp_holds_signing_key) = false ->
    comp.(comp_has_mint_cap) = false ->
    core.(cc_enrolled) = true ->
    trusted_path_mint core comp r g None = MintErr MintNoConsent.
Proof.
  intros core comp r g He Hk Hm Hen.
  unfold trusted_path_mint. rewrite He, Hk, Hm, Hen. reflexivity.
Qed.

(*| discharges: R-13-027b |*)
Theorem mint_refuses_absent_credential :
  forall core comp r g ca,
    core.(cc_exportable) = false ->
    comp.(comp_holds_signing_key) = false ->
    comp.(comp_has_mint_cap) = false ->
    core.(cc_enrolled) = true ->
    ca.(ca_credential_ok) = false ->
    trusted_path_mint core comp r g (Some ca) = MintErr MintCredentialAbsent.
Proof.
  intros core comp r g ca He Hk Hm Hen Hcred.
  unfold trusted_path_mint. rewrite He, Hk, Hm, Hen, Hcred. reflexivity.
Qed.

(*| discharges: R-13-027b |*)
Theorem mint_refuses_altered_root_or_roster :
  forall core comp r g ca,
    core.(cc_exportable) = false ->
    comp.(comp_holds_signing_key) = false ->
    comp.(comp_has_mint_cap) = false ->
    core.(cc_enrolled) = true ->
    ca.(ca_credential_ok) = true ->
    ca.(ca_user_consented) = true ->
    ca.(ca_prompt).(mp_shows_roster) = true ->
    ca.(ca_prompt).(mp_shows_root) = true ->
    PS.mem_nat ca.(ca_prompt).(mp_nonce) core.(cc_used_nonces) = false ->
    orb (negb (Nat.eqb ca.(ca_prompt).(mp_roster_hash) r))
        (negb (Nat.eqb ca.(ca_prompt).(mp_gen_root) g)) = true ->
    trusted_path_mint core comp r g (Some ca) = MintErr MintRootOrRosterAltered.
Proof.
  intros core comp r g ca He Hk Hm Hen Hcred Huser Hsr Hsg Hmem Halt.
  unfold trusted_path_mint.
  rewrite He, Hk, Hm, Hen, Hcred, Huser, Hsr, Hsg, Hmem, Halt.
  reflexivity.
Qed.

(*| discharges: R-13-027b |*)
Theorem mint_consumes_nonce_one_use :
  forall core comp r g ca sig core',
    trusted_path_mint core comp r g (Some ca) = MintOk sig core' ->
    mint_succeeded (trusted_path_mint core' comp r g (Some ca)) = false.
Proof.
  intros core comp r g ca sig core' H.
  unfold trusted_path_mint in H.
  destruct (cc_exportable core) eqn:He; [ discriminate H | ].
  destruct (comp_holds_signing_key comp) eqn:Hk;
    destruct (comp_has_mint_cap comp) eqn:Hm; simpl in H; try discriminate H.
  destruct (cc_enrolled core) eqn:Hen; [ | discriminate H ].
  destruct (ca_credential_ok ca) eqn:Hcred; [ | discriminate H ].
  destruct (ca_user_consented ca) eqn:Huser; [ | discriminate H ].
  destruct (mp_shows_roster (ca_prompt ca)) eqn:Hsr;
    destruct (mp_shows_root (ca_prompt ca)) eqn:Hsg; simpl in H; try discriminate H.
  destruct (PS.mem_nat (mp_nonce (ca_prompt ca)) (cc_used_nonces core)) eqn:Hmem;
    [ discriminate H | ].
  destruct (Nat.eqb (mp_roster_hash (ca_prompt ca)) r) eqn:Hr;
    destruct (Nat.eqb (mp_gen_root (ca_prompt ca)) g) eqn:Hg;
    simpl in H; try discriminate H.
  injection H as _ Hc'. subst core'.
  unfold trusted_path_mint, mint_succeeded.
  cbn [cc_exportable cc_enrolled cc_used_nonces].
  rewrite Hk, Hm, Hcred, Huser, Hsr, Hsg.
  cbn [orb negb PS.mem_nat PS.any_of].
  rewrite (PS.nat_eqb_refl (mp_nonce (ca_prompt ca))).
  reflexivity.
Qed.

(* =========================================================================
   3. Composition-mode entry/exit state machine (R-11-018)
   ========================================================================= *)

Inductive DeviceMode : Type :=
| NormalMode
| CompositionMode.

Record ModeEdge : Type := {
  me_cert_valid : bool;
  me_guard_ok : bool;
  me_dwell_ok : bool;
  me_pending_bounded : bool;
  me_recovery_reserved : bool
}.

Record ModeState : Type := {
  ms_mode : DeviceMode;
  ms_comp_priv : bool;
  ms_running_intact : bool;
  ms_switches : nat
}.

Definition mode_edge_admissible (edge : ModeEdge) : bool :=
  andb edge.(me_cert_valid)
    (andb edge.(me_guard_ok)
      (andb edge.(me_dwell_ok)
        (andb edge.(me_pending_bounded) edge.(me_recovery_reserved)))).

Definition enter_composition_mode (st : ModeState) (edge : ModeEdge) : ModeState :=
  match st.(ms_mode) with
  | NormalMode =>
      if mode_edge_admissible edge then
        {| ms_mode := CompositionMode;
           ms_comp_priv := true;
           ms_running_intact := st.(ms_running_intact);
           ms_switches := S st.(ms_switches) |}
      else
        {| ms_mode := NormalMode;
           ms_comp_priv := false;
           ms_running_intact := st.(ms_running_intact);
           ms_switches := st.(ms_switches) |}
  | CompositionMode =>
      (* Refuse nested entry and force clean exit to normal mode. *)
      {| ms_mode := NormalMode;
         ms_comp_priv := false;
         ms_running_intact := st.(ms_running_intact);
         ms_switches := st.(ms_switches) |}
  end.

Definition exit_composition_mode (st : ModeState) (succeeded : bool) : ModeState :=
  let _ := succeeded in
  {| ms_mode := NormalMode;
     ms_comp_priv := false;
     ms_running_intact := st.(ms_running_intact);
     ms_switches := match st.(ms_mode) with
                    | CompositionMode => S st.(ms_switches)
                    | NormalMode => st.(ms_switches)
                    end |}.

Definition composition_priv_held (st : ModeState) : bool :=
  match st.(ms_mode) with
  | NormalMode => false
  | CompositionMode => st.(ms_comp_priv)
  end.

(*| discharges: R-11-018 |*)
Theorem enter_refuses_invalid_edge_and_preserves_normal_mode :
  forall st edge,
    st.(ms_mode) = NormalMode ->
    mode_edge_admissible edge = false ->
    let st' := enter_composition_mode st edge in
    st'.(ms_mode) = NormalMode /\
    st'.(ms_comp_priv) = false /\
    st'.(ms_running_intact) = st.(ms_running_intact).
Proof.
  intros st edge Hnorm Hbad.
  unfold enter_composition_mode. rewrite Hnorm, Hbad.
  repeat split; reflexivity.
Qed.

(*| discharges: R-11-018 |*)
Theorem exit_always_restores_normal_mode_and_drops_privilege :
  forall st succeeded,
    let st' := exit_composition_mode st succeeded in
    st'.(ms_mode) = NormalMode /\
    st'.(ms_comp_priv) = false /\
    st'.(ms_running_intact) = st.(ms_running_intact).
Proof.
  intros st succeeded.
  unfold exit_composition_mode.
  repeat split; reflexivity.
Qed.

(* =========================================================================
   4. Offline scoped inclusion (R-13-023b, R-13-027)
   ========================================================================= *)

Inductive OriginKind : Type :=
| LocalAuthored
| FetchedFromPublisher.

Record ClosureMember : Type := {
  cm_id : nat;
  cm_origin : OriginKind;
  cm_has_publisher : bool;
  cm_logged_in_checkpoint : bool;
  cm_consistent_with_pin : bool;
  cm_inclusion_ok : bool
}.

Record OfflinePackage : Type := {
  op_id : nat;
  op_locally_composed : bool;
  op_has_publisher : bool;
  op_package_logged : bool;
  op_closure : list ClosureMember
}.

Definition offline_member_admissible (network_reachable : bool) (m : ClosureMember) : bool :=
  let _ := network_reachable in
  match m.(cm_origin) with
  | LocalAuthored => negb m.(cm_has_publisher)
  | FetchedFromPublisher =>
      andb m.(cm_logged_in_checkpoint)
        (andb m.(cm_consistent_with_pin) m.(cm_inclusion_ok))
  end.

Definition offline_package_admissible (network_reachable : bool) (p : OfflinePackage) : bool :=
  let closure_ok := PS.all_of (offline_member_admissible network_reachable) p.(op_closure) in
  let scope_ok :=
    if p.(op_locally_composed)
    then negb p.(op_has_publisher)
    else p.(op_package_logged) in
  andb closure_ok scope_ok.

(*| discharges: R-13-023b, R-13-027 |*)
Theorem offline_local_closure_needs_no_network_and_carries_no_publisher :
  forall p,
    p.(op_locally_composed) = true ->
    p.(op_has_publisher) = false ->
    PS.all_of (offline_member_admissible false) p.(op_closure) = true ->
    offline_package_admissible false p = true.
Proof.
  intros p Hloc Hpub Hclos.
  unfold offline_package_admissible. rewrite Hloc, Hpub, Hclos. reflexivity.
Qed.

(*| discharges: R-13-023b |*)
Theorem fetched_unlogged_member_refuses_even_inside_local_offline_build :
  forall net p,
    PS.any_of (fun x => andb (match x.(cm_origin) with
                               | FetchedFromPublisher => true
                               | LocalAuthored => false
                               end)
                             (negb x.(cm_logged_in_checkpoint)))
              p.(op_closure) = true ->
    offline_package_admissible net p = false.
Proof.
  intros net p Hbad.
  unfold offline_package_admissible.
  assert (Hclos : PS.all_of (offline_member_admissible net) p.(op_closure) = false).
  { induction (op_closure p) as [| x xs IH].
    - simpl in Hbad. discriminate Hbad.
    - simpl in Hbad. simpl.
      destruct (cm_origin x) eqn:Ho; destruct (cm_logged_in_checkpoint x) eqn:Hlog;
        simpl in Hbad; simpl.
      + rewrite (IH Hbad). destruct (offline_member_admissible net x); reflexivity.
      + rewrite (IH Hbad). destruct (offline_member_admissible net x); reflexivity.
      + rewrite (IH Hbad). destruct (offline_member_admissible net x); reflexivity.
      + unfold offline_member_admissible. rewrite Ho, Hlog. reflexivity. }
  rewrite Hclos. reflexivity.
Qed.

(* =========================================================================
   5. Fixed-package reuse across generations & R-06-015a budget (R-13-028, R-13-026)
   ========================================================================= *)

Record CheckedContext : Type := {
  ctx_spec_ver : nat;
  ctx_model_ver : nat;
  ctx_checker_id : nat;
  ctx_tier : nat;
  ctx_policy_ver : nat;
  ctx_resource_ver : nat
}.

Definition context_eqb (a b : CheckedContext) : bool :=
  andb (Nat.eqb a.(ctx_spec_ver) b.(ctx_spec_ver))
  (andb (Nat.eqb a.(ctx_model_ver) b.(ctx_model_ver))
  (andb (Nat.eqb a.(ctx_checker_id) b.(ctx_checker_id))
  (andb (Nat.eqb a.(ctx_tier) b.(ctx_tier))
  (andb (Nat.eqb a.(ctx_policy_ver) b.(ctx_policy_ver))
        (Nat.eqb a.(ctx_resource_ver) b.(ctx_resource_ver)))))).

Record FixedPkg : Type := {
  fp_id : nat;
  fp_artifact_hash : nat;
  fp_expected_hash : nat;
  fp_source_hash : nat;
  fp_contract_hash : nat;
  fp_proof_hash : nat;
  fp_code_rodata : nat;
  fp_initializer : nat;
  fp_context : CheckedContext;
  fp_is_base_image : bool;
  fp_reproducible_match : bool;
  fp_proof_steps : nat;
  fp_proof_workset : nat;
  fp_proof_valid : bool
}.

Record CheckedEntry : Type := {
  ce_id : nat;
  ce_artifact_hash : nat;
  ce_source_hash : nat;
  ce_contract_hash : nat;
  ce_proof_hash : nat;
  ce_context : CheckedContext
}.

Record CheckedSet : Type := {
  cs_root : nat;
  cs_hmac_valid : bool;
  cs_entries : list CheckedEntry
}.

Record GenCheckBudget : Type := {
  gb_max_steps : nat;
  gb_max_workset : nat
}.

Record GenerationCheckInput : Type := {
  gci_tal_layout_fresh_ok : bool;
  gci_wiring_fresh_ok : bool;
  gci_global_resource_ok : bool;
  gci_cic_checker_available : bool
}.

Definition entry_matches_pkg (ctx : CheckedContext) (p : FixedPkg) (e : CheckedEntry) : bool :=
  andb (Nat.eqb e.(ce_id) p.(fp_id))
  (andb (Nat.eqb e.(ce_artifact_hash) p.(fp_artifact_hash))
  (andb (Nat.eqb e.(ce_source_hash) p.(fp_source_hash))
  (andb (Nat.eqb e.(ce_contract_hash) p.(fp_contract_hash))
  (andb (Nat.eqb e.(ce_proof_hash) p.(fp_proof_hash))
  (andb (context_eqb e.(ce_context) ctx)
        (context_eqb p.(fp_context) ctx)))))).

Definition pkg_reusable (cs : CheckedSet) (ctx : CheckedContext) (p : FixedPkg) : bool :=
  andb cs.(cs_hmac_valid) (PS.any_of (entry_matches_pkg ctx p) cs.(cs_entries)).

Definition pkg_object_intact (p : FixedPkg) : bool :=
  andb (Nat.eqb p.(fp_artifact_hash) p.(fp_expected_hash))
       (if p.(fp_is_base_image) then p.(fp_reproducible_match) else true).

Definition check_pkg_under_budget
    (budget : GenCheckBudget)
    (cs : CheckedSet)
    (ctx : CheckedContext)
    (inp : GenerationCheckInput)
    (p : FixedPkg) : bool :=
  if negb (pkg_object_intact p) then false
  else if pkg_reusable cs ctx p then true
  else
    andb inp.(gci_cic_checker_available)
    (andb (Nat.leb p.(fp_proof_steps) budget.(gb_max_steps))
    (andb (Nat.leb p.(fp_proof_workset) budget.(gb_max_workset))
          p.(fp_proof_valid))).

Definition fresh_steps_for (cs : CheckedSet) (ctx : CheckedContext) (p : FixedPkg) : nat :=
  if pkg_reusable cs ctx p then 0 else p.(fp_proof_steps).

Definition fresh_workset_for (cs : CheckedSet) (ctx : CheckedContext) (p : FixedPkg) : nat :=
  if pkg_reusable cs ctx p then 0 else p.(fp_proof_workset).

Definition total_fresh_steps (cs : CheckedSet) (ctx : CheckedContext) (pkgs : list FixedPkg) : nat :=
  sum_nat (PS.map_over (fresh_steps_for cs ctx) pkgs).

Definition max_fresh_workset (cs : CheckedSet) (ctx : CheckedContext) (pkgs : list FixedPkg) : nat :=
  max_nat (PS.map_over (fresh_workset_for cs ctx) pkgs).

Definition admit_generation_checks
    (budget : GenCheckBudget)
    (cs : CheckedSet)
    (ctx : CheckedContext)
    (inp : GenerationCheckInput)
    (pkgs : list FixedPkg) : bool :=
  andb inp.(gci_tal_layout_fresh_ok)
  (andb inp.(gci_wiring_fresh_ok)
  (andb inp.(gci_global_resource_ok)
  (andb (Nat.leb (total_fresh_steps cs ctx pkgs) budget.(gb_max_steps))
  (andb (Nat.leb (max_fresh_workset cs ctx pkgs) budget.(gb_max_workset))
        (PS.all_of (check_pkg_under_budget budget cs ctx inp) pkgs))))).

(*| discharges: R-13-028 |*)
Theorem reused_pkg_requires_authenticated_checked_set :
  forall cs ctx p,
    cs.(cs_hmac_valid) = false ->
    pkg_reusable cs ctx p = false.
Proof.
  intros cs ctx p H. unfold pkg_reusable. rewrite H. reflexivity.
Qed.

(*| discharges: R-13-028 |*)
Theorem stale_tal_or_global_checks_refuse_even_when_all_packages_reused :
  forall budget cs ctx inp pkgs,
    orb (negb inp.(gci_tal_layout_fresh_ok))
        (orb (negb inp.(gci_wiring_fresh_ok))
             (negb inp.(gci_global_resource_ok))) = true ->
    admit_generation_checks budget cs ctx inp pkgs = false.
Proof.
  intros budget cs ctx inp pkgs Hbad.
  unfold admit_generation_checks.
  destruct (gci_tal_layout_fresh_ok inp);
    destruct (gci_wiring_fresh_ok inp);
    destruct (gci_global_resource_ok inp);
    simpl in *; try discriminate Hbad; reflexivity.
Qed.

(*| discharges: R-06-015a |*)
Theorem budget_exhaustion_refuses_generation :
  forall budget cs ctx inp pkgs,
    orb (negb (Nat.leb (total_fresh_steps cs ctx pkgs) budget.(gb_max_steps)))
        (negb (Nat.leb (max_fresh_workset cs ctx pkgs) budget.(gb_max_workset))) = true ->
    admit_generation_checks budget cs ctx inp pkgs = false.
Proof.
  intros budget cs ctx inp pkgs Hbad.
  unfold admit_generation_checks.
  destruct (Nat.leb (total_fresh_steps cs ctx pkgs) (gb_max_steps budget));
    destruct (Nat.leb (max_fresh_workset cs ctx pkgs) (gb_max_workset budget));
    simpl in *; try discriminate Hbad;
    destruct (gci_tal_layout_fresh_ok inp);
    destruct (gci_wiring_fresh_ok inp);
    destruct (gci_global_resource_ok inp);
    reflexivity.
Qed.

(*| discharges: R-13-026 |*)
Theorem base_image_non_reproducible_refuses :
  forall budget cs ctx inp p,
    p.(fp_is_base_image) = true ->
    p.(fp_reproducible_match) = false ->
    check_pkg_under_budget budget cs ctx inp p = false.
Proof.
  intros budget cs ctx inp p Hbase Hnrep.
  unfold check_pkg_under_budget, pkg_object_intact.
  rewrite Hbase, Hnrep.
  destruct (Nat.eqb (fp_artifact_hash p) (fp_expected_hash p)); reflexivity.
Qed.

(* =========================================================================
   6. Combined DeviceGeneration pipeline & A/B transactor handoff
   ========================================================================= *)

Record DeviceState : Type := {
  ds_mode : ModeState;
  ds_core : CryptoCore;
  ds_composer : ComposerCap;
  ds_checked : CheckedSet;
  ds_context : CheckedContext;
  ds_budget : GenCheckBudget;
  ds_ab : OT.Ab;
  ds_occupied_bytes : nat
}.

Record GenRequest : Type := {
  gr_network_reachable : bool;
  gr_roster_hash : nat;
  gr_gen_root : nat;
  gr_version : nat;
  gr_floor : nat;
  gr_edge : ModeEdge;
  gr_offline_pkgs : list OfflinePackage;
  gr_fixed_pkgs : list FixedPkg;
  gr_checks : GenerationCheckInput;
  gr_consent : option ConsentAct;
  gr_tr : OT.Transactor;
  gr_objects : OT.Objects;
  gr_pkg_bytes : nat
}.

Definition build_successor_entries (ctx : CheckedContext) (pkgs : list FixedPkg) : list CheckedEntry :=
  PS.map_over (fun p =>
    {| ce_id := p.(fp_id);
       ce_artifact_hash := p.(fp_artifact_hash);
       ce_source_hash := p.(fp_source_hash);
       ce_contract_hash := p.(fp_contract_hash);
       ce_proof_hash := p.(fp_proof_hash);
       ce_context := ctx |}) pkgs.

Definition build_signed_root (req : GenRequest) (sig : nat) : OT.SignedRoot :=
  let base_sr :=
    {| OT.sr_root := req.(gr_gen_root);
       OT.sr_version := req.(gr_version);
       OT.sr_floor := req.(gr_floor);
       OT.sr_key := 3;
       OT.sr_sig := sig;
       OT.sr_sum := 0 |} in
  {| OT.sr_root := req.(gr_gen_root);
     OT.sr_version := req.(gr_version);
     OT.sr_floor := req.(gr_floor);
     OT.sr_key := 3;
     OT.sr_sig := sig;
     OT.sr_sum := OT.checksum req.(gr_tr) (OT.encode_root req.(gr_tr) base_sr) |}.

Inductive GenRunOutcome : Type :=
| GenAdmitted (dev' : DeviceState)
| GenRefused (dev' : DeviceState).

Definition run_device_generation (dev : DeviceState) (req : GenRequest) : GenRunOutcome :=
  let m1 := enter_composition_mode dev.(ds_mode) req.(gr_edge) in
  if negb (composition_priv_held m1) then
    GenRefused {| ds_mode := exit_composition_mode m1 false;
                  ds_core := dev.(ds_core);
                  ds_composer := dev.(ds_composer);
                  ds_checked := dev.(ds_checked);
                  ds_context := dev.(ds_context);
                  ds_budget := dev.(ds_budget);
                  ds_ab := dev.(ds_ab);
                  ds_occupied_bytes := dev.(ds_occupied_bytes) |}
  else
    let offline_ok :=
      PS.all_of (offline_package_admissible req.(gr_network_reachable)) req.(gr_offline_pkgs) in
    let checks_ok :=
      admit_generation_checks dev.(ds_budget) dev.(ds_checked) dev.(ds_context)
                              req.(gr_checks) req.(gr_fixed_pkgs) in
    if negb (andb offline_ok checks_ok) then
      GenRefused {| ds_mode := exit_composition_mode m1 false;
                    ds_core := dev.(ds_core);
                    ds_composer := dev.(ds_composer);
                    ds_checked := dev.(ds_checked);
                    ds_context := dev.(ds_context);
                    ds_budget := dev.(ds_budget);
                    ds_ab := dev.(ds_ab);
                    ds_occupied_bytes := dev.(ds_occupied_bytes) |}
    else
      match trusted_path_mint dev.(ds_core) dev.(ds_composer)
                              req.(gr_roster_hash) req.(gr_gen_root) req.(gr_consent) with
      | MintErr _ =>
          GenRefused {| ds_mode := exit_composition_mode m1 false;
                        ds_core := dev.(ds_core);
                        ds_composer := dev.(ds_composer);
                        ds_checked := dev.(ds_checked);
                        ds_context := dev.(ds_context);
                        ds_budget := dev.(ds_budget);
                        ds_ab := dev.(ds_ab);
                        ds_occupied_bytes := dev.(ds_occupied_bytes) |}
      | MintOk sig core' =>
          let sr := build_signed_root req sig in
          let ab_staged := OT.stage sr dev.(ds_ab) in
          let ab_verified := OT.verify req.(gr_tr) req.(gr_objects) ab_staged in
          if negb ab_verified.(OT.ab_admitted) then
            GenRefused {| ds_mode := exit_composition_mode m1 false;
                          ds_core := core';
                          ds_composer := dev.(ds_composer);
                          ds_checked := dev.(ds_checked);
                          ds_context := dev.(ds_context);
                          ds_budget := dev.(ds_budget);
                          ds_ab := dev.(ds_ab);
                          ds_occupied_bytes := dev.(ds_occupied_bytes) |}
          else
            let ab_flipped := OT.flip ab_verified in
            let succ_checked :=
              {| cs_root := Nat.add 100 req.(gr_gen_root);
                 cs_hmac_valid := true;
                 cs_entries := build_successor_entries dev.(ds_context) req.(gr_fixed_pkgs) |} in
            let occ := Nat.add req.(gr_pkg_bytes) (max_fresh_workset dev.(ds_checked) dev.(ds_context) req.(gr_fixed_pkgs)) in
            GenAdmitted {| ds_mode := exit_composition_mode m1 true;
                           ds_core := core';
                           ds_composer := dev.(ds_composer);
                           ds_checked := succ_checked;
                           ds_context := dev.(ds_context);
                           ds_budget := dev.(ds_budget);
                           ds_ab := ab_flipped;
                           ds_occupied_bytes := occ |}
      end.

Definition outcome_device (o : GenRunOutcome) : DeviceState :=
  match o with
  | GenAdmitted d => d
  | GenRefused d => d
  end.

Definition outcome_admitted (o : GenRunOutcome) : bool :=
  match o with
  | GenAdmitted _ => true
  | GenRefused _ => false
  end.

(*| discharges: R-11-018, R-13-028 |*)
Theorem every_run_exits_composition_mode_and_drops_privilege :
  forall dev req,
    let d' := outcome_device (run_device_generation dev req) in
    d'.(ds_mode).(ms_mode) = NormalMode /\
    d'.(ds_mode).(ms_comp_priv) = false.
Proof.
  intros dev req.
  unfold run_device_generation, outcome_device.
  destruct (negb (composition_priv_held (enter_composition_mode (ds_mode dev) (gr_edge req))));
    [ repeat split; reflexivity | ].
  destruct (negb (andb (PS.all_of (offline_package_admissible (gr_network_reachable req))
                                  (gr_offline_pkgs req))
                       (admit_generation_checks (ds_budget dev) (ds_checked dev)
                                                (ds_context dev) (gr_checks req)
                                                (gr_fixed_pkgs req))));
    [ repeat split; reflexivity | ].
  destruct (trusted_path_mint (ds_core dev) (ds_composer dev)
                              (gr_roster_hash req) (gr_gen_root req) (gr_consent req));
    [ | repeat split; reflexivity ].
  destruct (negb (OT.ab_admitted (OT.verify (gr_tr req) (gr_objects req)
                                  (OT.stage (build_signed_root req sig) (ds_ab dev)))));
    repeat split; reflexivity.
Qed.

(*| discharges: R-13-028 |*)
Theorem refused_run_preserves_running_ab_and_checked_set :
  forall dev req dev',
    run_device_generation dev req = GenRefused dev' ->
    dev'.(ds_ab) = dev.(ds_ab) /\
    dev'.(ds_checked) = dev.(ds_checked).
Proof.
  intros dev req dev' H.
  unfold run_device_generation in H.
  destruct (negb (composition_priv_held (enter_composition_mode (ds_mode dev) (gr_edge req))));
    [ injection H as <-; split; reflexivity | ].
  destruct (negb (andb (PS.all_of (offline_package_admissible (gr_network_reachable req))
                                  (gr_offline_pkgs req))
                       (admit_generation_checks (ds_budget dev) (ds_checked dev)
                                                (ds_context dev) (gr_checks req)
                                                (gr_fixed_pkgs req))));
    [ injection H as <-; split; reflexivity | ].
  destruct (trusted_path_mint (ds_core dev) (ds_composer dev)
                              (gr_roster_hash req) (gr_gen_root req) (gr_consent req));
    [ | injection H as <-; split; reflexivity ].
  destruct (negb (OT.ab_admitted (OT.verify (gr_tr req) (gr_objects req)
                                  (OT.stage (build_signed_root req sig) (ds_ab dev)))));
    [ injection H as <-; split; reflexivity | discriminate H ].
Qed.

(* =========================================================================
   7. Concrete positive traces and exhaustive adverse refutations
   ========================================================================= *)

Definition demo_ctx : CheckedContext :=
  {| ctx_spec_ver := 1; ctx_model_ver := 1; ctx_checker_id := 1;
     ctx_tier := 2; ctx_policy_ver := 1; ctx_resource_ver := 1 |}.

Definition demo_budget : GenCheckBudget :=
  {| gb_max_steps := 500; gb_max_workset := 4096 |}.

Definition demo_core : CryptoCore :=
  {| cc_key_id := 3; cc_enrolled := true; cc_exportable := false;
     cc_private_secret := 42; cc_used_nonces := nil |}.

Definition demo_composer : ComposerCap :=
  {| comp_id := 9; comp_holds_signing_key := false; comp_has_mint_cap := false |}.

Definition demo_mode_state : ModeState :=
  {| ms_mode := NormalMode; ms_comp_priv := false;
     ms_running_intact := true; ms_switches := 0 |}.

Definition demo_edge : ModeEdge :=
  {| me_cert_valid := true; me_guard_ok := true; me_dwell_ok := true;
     me_pending_bounded := true; me_recovery_reserved := true |}.

(* Build a Transactor whose sig_ok accepts our crypto-core's computed mint sig
   for root 33 under key 3, while keeping OT.demo_transactor's DAG/checksum/floor
   machinery intact. *)
Definition dgen_transactor (expected_sig : nat) (healthy_root_33 : bool) : OT.Transactor :=
  {| OT.encode_obj := OT.encode_obj OT.demo_transactor;
     OT.content_hash := OT.content_hash OT.demo_transactor;
     OT.walk_depth := OT.walk_depth OT.demo_transactor;
     OT.root_copies := OT.root_copies OT.demo_transactor;
     OT.encode_root := OT.encode_root OT.demo_transactor;
     OT.checksum := OT.checksum OT.demo_transactor;
     OT.enrolled_root := OT.enrolled_root OT.demo_transactor;
     OT.sig_ok := fun k bytes s =>
       orb (OT.sig_ok OT.demo_transactor k bytes s)
           (andb (Nat.eqb k 3) (Nat.eqb s expected_sig));
     OT.admits := OT.admits OT.demo_transactor;
     OT.healthy := fun r =>
       if Nat.eqb r 33 then healthy_root_33 else OT.healthy OT.demo_transactor r;
     OT.included := OT.included OT.demo_transactor;
     OT.consistent := OT.consistent OT.demo_transactor;
     OT.checkpoint_accepted := OT.checkpoint_accepted OT.demo_transactor |}.

(* Initial base + pkg A already admitted and present in CheckedSet. *)
Definition pkg_base_unchanged : FixedPkg :=
  {| fp_id := 1; fp_artifact_hash := 101; fp_expected_hash := 101;
     fp_source_hash := 201; fp_contract_hash := 301; fp_proof_hash := 401;
     fp_code_rodata := 1024; fp_initializer := 64; fp_context := demo_ctx;
     fp_is_base_image := true; fp_reproducible_match := true;
     fp_proof_steps := 300; fp_proof_workset := 2048; fp_proof_valid := true |}.

Definition pkg_a_unchanged : FixedPkg :=
  {| fp_id := 2; fp_artifact_hash := 102; fp_expected_hash := 102;
     fp_source_hash := 202; fp_contract_hash := 302; fp_proof_hash := 402;
     fp_code_rodata := 512; fp_initializer := 32; fp_context := demo_ctx;
     fp_is_base_image := false; fp_reproducible_match := true;
     fp_proof_steps := 250; fp_proof_workset := 1024; fp_proof_valid := true |}.

(* Changed package B in generation 1: fresh proof check fits within budget (120 <= 500). *)
Definition pkg_b_changed : FixedPkg :=
  {| fp_id := 3; fp_artifact_hash := 103; fp_expected_hash := 103;
     fp_source_hash := 203; fp_contract_hash := 303; fp_proof_hash := 403;
     fp_code_rodata := 768; fp_initializer := 48; fp_context := demo_ctx;
     fp_is_base_image := false; fp_reproducible_match := true;
     fp_proof_steps := 120; fp_proof_workset := 1024; fp_proof_valid := true |}.

Definition initial_checked_set : CheckedSet :=
  {| cs_root := 900;
     cs_hmac_valid := true;
     cs_entries := build_successor_entries demo_ctx
                     (cons pkg_base_unchanged (cons pkg_a_unchanged nil)) |}.

Definition initial_device : DeviceState :=
  {| ds_mode := demo_mode_state;
     ds_core := demo_core;
     ds_composer := demo_composer;
     ds_checked := initial_checked_set;
     ds_context := demo_ctx;
     ds_budget := demo_budget;
     ds_ab := OT.demo_ab;
     ds_occupied_bytes := 0 |}.

(* Positive Trace 1: Offline package-change generation (network unreachable). *)
Definition local_member_1 : ClosureMember :=
  {| cm_id := 10; cm_origin := LocalAuthored; cm_has_publisher := false;
     cm_logged_in_checkpoint := false; cm_consistent_with_pin := false;
     cm_inclusion_ok := false |}.

Definition fetched_logged_member : ClosureMember :=
  {| cm_id := 11; cm_origin := FetchedFromPublisher; cm_has_publisher := true;
     cm_logged_in_checkpoint := true; cm_consistent_with_pin := true;
     cm_inclusion_ok := true |}.

Definition offline_pkg_local_change : OfflinePackage :=
  {| op_id := 3; op_locally_composed := true; op_has_publisher := false;
     op_package_logged := false;
     op_closure := cons local_member_1 (cons fetched_logged_member nil) |}.

Definition gen1_sig : nat := compute_mint_sig 3 42 777 33 1.

Definition gen1_consent : ConsentAct :=
  {| ca_credential_ok := true;
     ca_user_consented := true;
     ca_prompt := {| mp_roster_hash := 777; mp_gen_root := 33; mp_nonce := 1;
                     mp_shows_roster := true; mp_shows_root := true |} |}.

Definition gen1_checks : GenerationCheckInput :=
  {| gci_tal_layout_fresh_ok := true;
     gci_wiring_fresh_ok := true;
     gci_global_resource_ok := true;
     gci_cic_checker_available := true |}.

Definition gen1_request : GenRequest :=
  {| gr_network_reachable := false;
     gr_roster_hash := 777;
     gr_gen_root := 33;
     gr_version := 6;
     gr_floor := 4;
     gr_edge := demo_edge;
     gr_offline_pkgs := cons offline_pkg_local_change nil;
     gr_fixed_pkgs := cons pkg_base_unchanged (cons pkg_a_unchanged (cons pkg_b_changed nil));
     gr_checks := gen1_checks;
     gr_consent := Some gen1_consent;
     gr_tr := dgen_transactor gen1_sig true;
     gr_objects := OT.whole_view;
     gr_pkg_bytes := 2448 |}.

(* Positive Trace 2: Offline reproducible base-image rebuild (network unreachable, R-13-026). *)
Definition pkg_base_rebuilt : FixedPkg :=
  {| fp_id := 1; fp_artifact_hash := 111; fp_expected_hash := 111;
     fp_source_hash := 211; fp_contract_hash := 311; fp_proof_hash := 411;
     fp_code_rodata := 1024; fp_initializer := 64; fp_context := demo_ctx;
     fp_is_base_image := true; fp_reproducible_match := true;
     fp_proof_steps := 300; fp_proof_workset := 2048; fp_proof_valid := true |}.

Definition offline_base_rebuild_pkg : OfflinePackage :=
  {| op_id := 1; op_locally_composed := true; op_has_publisher := false;
     op_package_logged := false;
     op_closure := cons local_member_1 nil |}.

Definition gen2_sig : nat := compute_mint_sig 3 42 888 33 2.

Definition gen2_consent : ConsentAct :=
  {| ca_credential_ok := true;
     ca_user_consented := true;
     ca_prompt := {| mp_roster_hash := 888; mp_gen_root := 33; mp_nonce := 2;
                     mp_shows_roster := true; mp_shows_root := true |} |}.

Definition gen2_request : GenRequest :=
  {| gr_network_reachable := false;
     gr_roster_hash := 888;
     gr_gen_root := 33;
     gr_version := 6;
     gr_floor := 4;
     gr_edge := demo_edge;
     gr_offline_pkgs := cons offline_base_rebuild_pkg nil;
     gr_fixed_pkgs := cons pkg_base_rebuilt (cons pkg_a_unchanged nil);
     gr_checks := gen1_checks;
     gr_consent := Some gen2_consent;
     gr_tr := dgen_transactor gen2_sig true;
     gr_objects := OT.whole_view;
     gr_pkg_bytes := 1632 |}.

(*| discharges: R-13-027, R-13-026, R-13-028, R-13-027b, R-13-023b, R-11-018, R-06-015a |*)
Example positive_offline_package_change_and_base_rebuild_both_admit_and_boot :
  let out1 := run_device_generation initial_device gen1_request in
  let dev1 := outcome_device out1 in
  let out2 := run_device_generation initial_device gen2_request in
  let dev2 := outcome_device out2 in
  outcome_admitted out1 = true /\
  OT.sr_root (OT.live dev1.(ds_ab)) = 33 /\
  dev1.(ds_mode).(ms_mode) = NormalMode /\
  dev1.(ds_mode).(ms_comp_priv) = false /\
  total_fresh_steps dev1.(ds_checked) demo_ctx
    (cons pkg_base_unchanged (cons pkg_a_unchanged (cons pkg_b_changed nil))) = 0 /\
  total_fresh_steps initial_device.(ds_checked) demo_ctx
    (cons pkg_base_unchanged (cons pkg_a_unchanged (cons pkg_b_changed nil))) = 120 /\
  dev1.(ds_occupied_bytes) = 3472 /\
  outcome_admitted out2 = true /\
  OT.sr_root (OT.live dev2.(ds_ab)) = 33 /\
  dev2.(ds_mode).(ms_mode) = NormalMode /\
  dev2.(ds_mode).(ms_comp_priv) = false /\
  OT.sr_root (OT.live (OT.spec_gate (dgen_transactor gen1_sig false) OT.whole_view dev1.(ds_ab))) = 17.
Proof. repeat split; reflexivity. Qed.

(* Adverse Mint Controls (all three required by R-13-027b). *)
Definition req_no_consent : GenRequest :=
  {| gr_network_reachable := false; gr_roster_hash := 777; gr_gen_root := 33;
     gr_version := 6; gr_floor := 4; gr_edge := demo_edge;
     gr_offline_pkgs := cons offline_pkg_local_change nil;
     gr_fixed_pkgs := cons pkg_base_unchanged (cons pkg_a_unchanged (cons pkg_b_changed nil));
     gr_checks := gen1_checks; gr_consent := None;
     gr_tr := dgen_transactor gen1_sig true; gr_objects := OT.whole_view; gr_pkg_bytes := 2448 |}.

Definition altered_root_consent : ConsentAct :=
  {| ca_credential_ok := true; ca_user_consented := true;
     ca_prompt := {| mp_roster_hash := 777; mp_gen_root := 99; mp_nonce := 1;
                     mp_shows_roster := true; mp_shows_root := true |} |}.

Definition req_altered_root : GenRequest :=
  {| gr_network_reachable := false; gr_roster_hash := 777; gr_gen_root := 33;
     gr_version := 6; gr_floor := 4; gr_edge := demo_edge;
     gr_offline_pkgs := cons offline_pkg_local_change nil;
     gr_fixed_pkgs := cons pkg_base_unchanged (cons pkg_a_unchanged (cons pkg_b_changed nil));
     gr_checks := gen1_checks; gr_consent := Some altered_root_consent;
     gr_tr := dgen_transactor gen1_sig true; gr_objects := OT.whole_view; gr_pkg_bytes := 2448 |}.

Definition absent_cred_consent : ConsentAct :=
  {| ca_credential_ok := false; ca_user_consented := true;
     ca_prompt := {| mp_roster_hash := 777; mp_gen_root := 33; mp_nonce := 1;
                     mp_shows_roster := true; mp_shows_root := true |} |}.

Definition req_absent_cred : GenRequest :=
  {| gr_network_reachable := false; gr_roster_hash := 777; gr_gen_root := 33;
     gr_version := 6; gr_floor := 4; gr_edge := demo_edge;
     gr_offline_pkgs := cons offline_pkg_local_change nil;
     gr_fixed_pkgs := cons pkg_base_unchanged (cons pkg_a_unchanged (cons pkg_b_changed nil));
     gr_checks := gen1_checks; gr_consent := Some absent_cred_consent;
     gr_tr := dgen_transactor gen1_sig true; gr_objects := OT.whole_view; gr_pkg_bytes := 2448 |}.

(*| discharges: R-13-027b |*)
Example adverse_mint_cases_all_refused_and_preserve_running_state :
  trusted_path_mint demo_core demo_composer 777 33 None = MintErr MintNoConsent /\
  trusted_path_mint demo_core demo_composer 777 33 (Some altered_root_consent) = MintErr MintRootOrRosterAltered /\
  trusted_path_mint demo_core demo_composer 777 33 (Some absent_cred_consent) = MintErr MintCredentialAbsent /\
  trusted_path_mint {| cc_key_id := 3; cc_enrolled := true; cc_exportable := true;
                       cc_private_secret := 42; cc_used_nonces := nil |}
                    demo_composer 777 33 (Some gen1_consent) = MintErr MintKeyExportable /\
  trusted_path_mint demo_core
                    {| comp_id := 9; comp_holds_signing_key := true; comp_has_mint_cap := false |}
                    777 33 (Some gen1_consent) = MintErr MintComposerPrivileged /\
  outcome_admitted (run_device_generation initial_device req_no_consent) = false /\
  outcome_admitted (run_device_generation initial_device req_altered_root) = false /\
  outcome_admitted (run_device_generation initial_device req_absent_cred) = false /\
  (outcome_device (run_device_generation initial_device req_no_consent)).(ds_mode).(ms_mode) = NormalMode /\
  (outcome_device (run_device_generation initial_device req_no_consent)).(ds_ab) = OT.demo_ab.
Proof. repeat split; reflexivity. Qed.

(* Adverse Offline Inclusion Control: fetched unlogged member hidden inside local build. *)
Definition fetched_unlogged_member : ClosureMember :=
  {| cm_id := 12; cm_origin := FetchedFromPublisher; cm_has_publisher := true;
     cm_logged_in_checkpoint := false; cm_consistent_with_pin := true;
     cm_inclusion_ok := true |}.

Definition offline_pkg_smuggled : OfflinePackage :=
  {| op_id := 3; op_locally_composed := true; op_has_publisher := false;
     op_package_logged := false;
     op_closure := cons local_member_1 (cons fetched_unlogged_member nil) |}.

Definition req_unlogged_fetched : GenRequest :=
  {| gr_network_reachable := false; gr_roster_hash := 777; gr_gen_root := 33;
     gr_version := 6; gr_floor := 4; gr_edge := demo_edge;
     gr_offline_pkgs := cons offline_pkg_smuggled nil;
     gr_fixed_pkgs := cons pkg_base_unchanged (cons pkg_a_unchanged (cons pkg_b_changed nil));
     gr_checks := gen1_checks; gr_consent := Some gen1_consent;
     gr_tr := dgen_transactor gen1_sig true; gr_objects := OT.whole_view; gr_pkg_bytes := 2448 |}.

(* Adverse Reuse/Budget/Mode/Reproducibility Controls. *)
Definition dev_tampered_checked : DeviceState :=
  {| ds_mode := demo_mode_state; ds_core := demo_core; ds_composer := demo_composer;
     ds_checked := {| cs_root := 900; cs_hmac_valid := false;
                      cs_entries := initial_checked_set.(cs_entries) |};
     ds_context := demo_ctx; ds_budget := demo_budget;
     ds_ab := OT.demo_ab; ds_occupied_bytes := 0 |}.

Definition dev_tiny_budget : DeviceState :=
  {| ds_mode := demo_mode_state; ds_core := demo_core; ds_composer := demo_composer;
     ds_checked := initial_checked_set; ds_context := demo_ctx;
     ds_budget := {| gb_max_steps := 50; gb_max_workset := 4096 |};
     ds_ab := OT.demo_ab; ds_occupied_bytes := 0 |}.

Definition req_stale_tal : GenRequest :=
  {| gr_network_reachable := false; gr_roster_hash := 777; gr_gen_root := 33;
     gr_version := 6; gr_floor := 4; gr_edge := demo_edge;
     gr_offline_pkgs := cons offline_pkg_local_change nil;
     gr_fixed_pkgs := cons pkg_base_unchanged (cons pkg_a_unchanged (cons pkg_b_changed nil));
     gr_checks := {| gci_tal_layout_fresh_ok := false; gci_wiring_fresh_ok := true;
                     gci_global_resource_ok := true; gci_cic_checker_available := true |};
     gr_consent := Some gen1_consent; gr_tr := dgen_transactor gen1_sig true;
     gr_objects := OT.whole_view; gr_pkg_bytes := 2448 |}.

Definition req_bad_mode_cert : GenRequest :=
  {| gr_network_reachable := false; gr_roster_hash := 777; gr_gen_root := 33;
     gr_version := 6; gr_floor := 4;
     gr_edge := {| me_cert_valid := false; me_guard_ok := true; me_dwell_ok := true;
                   me_pending_bounded := true; me_recovery_reserved := true |};
     gr_offline_pkgs := cons offline_pkg_local_change nil;
     gr_fixed_pkgs := cons pkg_base_unchanged (cons pkg_a_unchanged (cons pkg_b_changed nil));
     gr_checks := gen1_checks; gr_consent := Some gen1_consent;
     gr_tr := dgen_transactor gen1_sig true; gr_objects := OT.whole_view; gr_pkg_bytes := 2448 |}.

Definition pkg_base_nonrepro : FixedPkg :=
  {| fp_id := 1; fp_artifact_hash := 111; fp_expected_hash := 111;
     fp_source_hash := 211; fp_contract_hash := 311; fp_proof_hash := 411;
     fp_code_rodata := 1024; fp_initializer := 64; fp_context := demo_ctx;
     fp_is_base_image := true; fp_reproducible_match := false;
     fp_proof_steps := 300; fp_proof_workset := 2048; fp_proof_valid := true |}.

Definition req_nonrepro_base : GenRequest :=
  {| gr_network_reachable := false; gr_roster_hash := 888; gr_gen_root := 33;
     gr_version := 6; gr_floor := 4; gr_edge := demo_edge;
     gr_offline_pkgs := cons offline_base_rebuild_pkg nil;
     gr_fixed_pkgs := cons pkg_base_nonrepro (cons pkg_a_unchanged nil);
     gr_checks := gen1_checks; gr_consent := Some gen2_consent;
     gr_tr := dgen_transactor gen2_sig true; gr_objects := OT.whole_view; gr_pkg_bytes := 1632 |}.

(*| discharges: R-13-023b, R-13-028, R-06-015a, R-11-018, R-13-026 |*)
Example adverse_inclusion_reuse_budget_mode_and_repro_all_refused :
  outcome_admitted (run_device_generation initial_device req_unlogged_fetched) = false /\
  pkg_reusable dev_tampered_checked.(ds_checked) demo_ctx pkg_a_unchanged = false /\
  outcome_admitted (run_device_generation initial_device req_stale_tal) = false /\
  outcome_admitted (run_device_generation dev_tiny_budget gen1_request) = false /\
  outcome_admitted (run_device_generation initial_device req_bad_mode_cert) = false /\
  outcome_admitted (run_device_generation initial_device req_nonrepro_base) = false /\
  (outcome_device (run_device_generation initial_device req_unlogged_fetched)).(ds_mode).(ms_mode) = NormalMode /\
  (outcome_device (run_device_generation dev_tiny_budget gen1_request)).(ds_mode).(ms_comp_priv) = false.
Proof. repeat split; reflexivity. Qed.

(* =========================================================================
   8. R-05-166 inhabitation witnesses (one closed Definition per Record)
   ========================================================================= *)

Definition witness_CryptoCore : CryptoCore := demo_core.
Definition witness_ComposerCap : ComposerCap := demo_composer.
Definition witness_MintPrompt : MintPrompt := gen1_consent.(ca_prompt).
Definition witness_ConsentAct : ConsentAct := gen1_consent.
Definition witness_ModeEdge : ModeEdge := demo_edge.
Definition witness_ModeState : ModeState := demo_mode_state.
Definition witness_ClosureMember : ClosureMember := local_member_1.
Definition witness_OfflinePackage : OfflinePackage := offline_pkg_local_change.
Definition witness_CheckedContext : CheckedContext := demo_ctx.
Definition witness_FixedPkg : FixedPkg := pkg_base_unchanged.
Definition witness_CheckedEntry : CheckedEntry :=
  {| ce_id := 1; ce_artifact_hash := 101; ce_source_hash := 201;
     ce_contract_hash := 301; ce_proof_hash := 401; ce_context := demo_ctx |}.
Definition witness_CheckedSet : CheckedSet := initial_checked_set.
Definition witness_GenCheckBudget : GenCheckBudget := demo_budget.
Definition witness_GenerationCheckInput : GenerationCheckInput := gen1_checks.
Definition witness_DeviceState : DeviceState := initial_device.
Definition witness_GenRequest : GenRequest := gen1_request.

(* R-05-163, R-05-164, R-05-165, R-05-166: zero axioms, prelude-only,
   all records inhabited, positive & negative controls discharged. *)
