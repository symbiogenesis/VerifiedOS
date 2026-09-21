(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   MModeFirmwareSealing.v

   Sealing-aware refinement of MModeFirmware's installed graph for R-07-028.
   Purecap ABI sections 4 and 7 admit invocation-only kernel sentries.
   The legacy holder/region/permission graph cannot distinguish their sealed
   bits from an unsealed authority. Its original predicates and theorems remain
   unchanged. This module adds exact tag, seal, locality and entry-site identity
   and proves the usable-authority restriction over the actual installed view.

   Regions retain the plan's exact-extent abstraction. Entry cursors below are
   offsets within that named extent. The policy lists are immutable composition
   inputs, not caller claims. Binding them to measured stub/descriptor bytes,
   and proving that a listed backward sentry is hardware-minted and belongs to
   the live protected activation, remain producer obligations. No freshness
   property follows from the seal constructor alone. This is a distribution
   refinement; it is not an implementation or an instruction-level Sail proof.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-07-028
   SHA256: a93666b91149166c77c0f9c9d0224b1fdfc98da0d6b81252784d4ccf058ee780
   (*| END derived |*)
   ========================================================================= *)
Require Import MModeFirmware.

Inductive SealForm : Type := Unsealed | ForwardSentry | BackwardSentry | OtherSeal.

Definition seal_eqb (x y : SealForm) : bool :=
  match x, y with
  | Unsealed, Unsealed | ForwardSentry, ForwardSentry
  | BackwardSentry, BackwardSentry | OtherSeal, OtherSeal => true
  | _, _ => false
  end.
Lemma seal_eqb_refl : forall x, seal_eqb x x = true.
Proof. intros []; reflexivity. Qed.
Lemma seal_eqb_sound : forall x y, seal_eqb x y = true -> x = y.
Proof. intros [] [] H; try discriminate; reflexivity. Qed.

Fixpoint site_eqb (x y : nat) : bool :=
  match x, y with O, O => true | S a, S b => site_eqb a b | _, _ => false end.
Lemma site_eqb_refl : forall x, site_eqb x x = true.
Proof. induction x; simpl; auto. Qed.
Lemma site_eqb_sound : forall x y, site_eqb x y = true -> x = y.
Proof. induction x; intros []; simpl; intros H; try discriminate; auto. Qed.

Record SealedEdge (m : Machine) : Type := {
  raw_edge : Edge m;
  edge_tag : bool;
  edge_seal : SealForm;
  edge_local : bool;
  edge_site : nat
}.
Arguments raw_edge {m} _.
Arguments edge_tag {m} _.
Arguments edge_seal {m} _.
Arguments edge_local {m} _.
Arguments edge_site {m} _.

Definition sealed_edge_eqb (m : Machine) (x y : SealedEdge m) : bool :=
  andb (edge_eqb m (raw_edge x) (raw_edge y))
  (andb (bool_eqb (edge_tag x) (edge_tag y))
  (andb (seal_eqb (edge_seal x) (edge_seal y))
  (andb (bool_eqb (edge_local x) (edge_local y))
        (site_eqb (edge_site x) (edge_site y))))).
Lemma sealed_edge_eqb_refl : forall m (e : SealedEdge m),
  sealed_edge_eqb m e e = true.
Proof.
  intros m [e t s l n]. unfold sealed_edge_eqb; simpl.
  rewrite edge_eqb_refl, bool_eqb_refl, seal_eqb_refl, bool_eqb_refl,
    site_eqb_refl. reflexivity.
Qed.
Lemma sealed_edge_eqb_sound : forall m (x y : SealedEdge m),
  sealed_edge_eqb m x y = true -> x = y.
Proof.
  intros m [e t s l n] [f u q k o] H. unfold sealed_edge_eqb in H; simpl in H.
  destruct (andb_split _ _ H) as [A H1].
  destruct (andb_split _ _ H1) as [B H2].
  destruct (andb_split _ _ H2) as [C H3].
  destruct (andb_split _ _ H3) as [D E].
  rewrite (edge_eqb_sound m e f A), (bool_eqb_sound t u B),
    (seal_eqb_sound s q C), (bool_eqb_sound l k D), (site_eqb_sound n o E).
  reflexivity.
Qed.

Definition SealedGraph (m : Machine) := list (SealedEdge m).
Definition sealed_holds (m : Machine) (e : SealedEdge m) (g : SealedGraph m) :=
  any_of (sealed_edge_eqb m e) g.
Definition erased_graph (m : Machine) (g : SealedGraph m) : Graph m :=
  map_over raw_edge g.

Record SealingPolicy (m : Machine) : Type := {
  kernel_text : m.(Region) -> bool;
  kernel_data : m.(Region) -> bool;
  admitted_entries : SealedGraph m;
  admitted_continuations : SealedGraph m
}.
Arguments kernel_text {m} _ _.
Arguments kernel_data {m} _ _.
Arguments admitted_entries {m} _.
Arguments admitted_continuations {m} _.

Definition invocation_only (m : Machine) (p : SealingPolicy m)
    (e : SealedEdge m) : bool :=
  andb (edge_tag e)
  (andb (kernel_text p (edge_region (raw_edge e)))
  (andb (permit_execute (edge_authority m (raw_edge e)))
  (andb (negb (permit_store (edge_authority m (raw_edge e))))
    (match edge_seal e with
     | ForwardSentry => sealed_holds m e (admitted_entries p)
     | BackwardSentry => andb (edge_local e)
                               (sealed_holds m e (admitted_continuations p))
     | _ => false
     end)))).

Definition sealed_edge_admitted (m : Machine) (p : SealingPolicy m)
    (e : SealedEdge m) : bool :=
  if edge_tag e then
    if m.(node_eqb) (edge_holder (raw_edge e)) m.(kernel) then true
    else andb (negb (kernel_data p (edge_region (raw_edge e))))
      (if orb (access_system_registers (edge_authority m (raw_edge e)))
              (kernel_text p (edge_region (raw_edge e)))
       then invocation_only m p e else true)
  else true.
Definition sealing_graph_check (m : Machine) (p : SealingPolicy m)
    (g : SealedGraph m) : bool := all_of (sealed_edge_admitted m p) g.
Definition SealedInstalled (m : Machine) := SealedEdge m -> bool.
Definition InstalledSealingPolicy (m : Machine) (p : SealingPolicy m)
    (st : SealedInstalled m) : Prop :=
  forall e, st e = true -> sealed_edge_admitted m p e = true.

(* Handoff's resident inventory and partition-bounded roots still apply.
   The new equality compares all fields, not merely the erasure. *)
Definition SealingAwareHandoff (m : Machine) (p : SealingPolicy m)
    (g : SealedGraph m) (legacy : Installed m) (st : SealedInstalled m) : Prop :=
  Handoff m (erased_graph m g) legacy /\
  (forall e, st e = sealed_holds m e g) /\ sealing_graph_check m p g = true.

Theorem sealing_check_reaches_actual_installed_edges : forall m p g legacy st,
  SealingAwareHandoff m p g legacy st -> InstalledSealingPolicy m p st.
Proof.
  intros m p g legacy st [OLD [EXACT CHECK]] e HELD.
  rewrite (EXACT e) in HELD.
  exact (all_of_member (SealedEdge m) (sealed_edge_eqb m)
    (sealed_edge_eqb_sound m) (sealed_edge_admitted m p) g e CHECK HELD).
Qed.
Theorem sealing_handoff_preserves_original_handoff : forall m p g legacy st,
  SealingAwareHandoff m p g legacy st -> Handoff m (erased_graph m g) legacy.
Proof. intros m p g legacy st [H _]. exact H. Qed.
Theorem sealing_handoff_has_bounded_roots : forall m p g legacy st,
  SealingAwareHandoff m p g legacy st -> RootsAreBounded m legacy.
Proof.
  intros m p g legacy st [H _].
  exact (the_handoff_roots_are_bounded m (erased_graph m g) legacy H).
Qed.
Theorem sealing_handoff_remains_quiescent : forall m p g legacy st,
  SealingAwareHandoff m p g legacy st ->
  PlanNamesNoFirmwareEdge m (erased_graph m g) -> Quiescent m legacy.
Proof.
  intros m p g legacy st [H _] PLAN.
  exact (quiescence_follows_from_the_refinement m (erased_graph m g) legacy H PLAN).
Qed.

Lemma unsealed_is_not_invocation_only : forall m p e,
  edge_seal e = Unsealed -> invocation_only m p e = false.
Proof.
  intros m p [e t s l n] H; simpl in H; subst s.
  unfold invocation_only; simpl.
  destruct t; destruct (kernel_text p (edge_region e));
    destruct (permit_execute (edge_authority m e));
    destruct (permit_store (edge_authority m e)); reflexivity.
Qed.
Theorem only_kernel_holds_usable_asr : forall m p st,
  InstalledSealingPolicy m p st -> forall e,
  st e = true -> edge_tag e = true -> edge_seal e = Unsealed ->
  access_system_registers (edge_authority m (raw_edge e)) = true ->
  m.(node_eqb) (edge_holder (raw_edge e)) m.(kernel) = true.
Proof.
  intros m p st SAFE e HELD TAG SEAL ASR.
  pose proof (SAFE e HELD) as CHECK.
  unfold sealed_edge_admitted in CHECK. rewrite TAG in CHECK.
  destruct (m.(node_eqb) (edge_holder (raw_edge e)) m.(kernel)) eqn:OWNER; auto.
  rewrite ASR in CHECK. simpl in CHECK.
  rewrite (unsealed_is_not_invocation_only m p e SEAL) in CHECK.
  destruct (kernel_data p (edge_region (raw_edge e))); discriminate CHECK.
Qed.
Theorem only_kernel_holds_unsealed_kernel_text : forall m p st,
  InstalledSealingPolicy m p st -> forall e,
  st e = true -> edge_tag e = true -> edge_seal e = Unsealed ->
  kernel_text p (edge_region (raw_edge e)) = true ->
  m.(node_eqb) (edge_holder (raw_edge e)) m.(kernel) = true.
Proof.
  intros m p st SAFE e HELD TAG SEAL TEXT.
  pose proof (SAFE e HELD) as CHECK.
  unfold sealed_edge_admitted in CHECK. rewrite TAG in CHECK.
  destruct (m.(node_eqb) (edge_holder (raw_edge e)) m.(kernel)) eqn:OWNER; auto.
  rewrite TEXT in CHECK.
  destruct (access_system_registers (edge_authority m (raw_edge e))); simpl in CHECK;
    rewrite (unsealed_is_not_invocation_only m p e SEAL) in CHECK;
    destruct (kernel_data p (edge_region (raw_edge e))); discriminate CHECK.
Qed.
Theorem only_kernel_holds_kernel_data : forall m p st,
  InstalledSealingPolicy m p st -> forall e,
  st e = true -> edge_tag e = true ->
  kernel_data p (edge_region (raw_edge e)) = true ->
  m.(node_eqb) (edge_holder (raw_edge e)) m.(kernel) = true.
Proof.
  intros m p st SAFE e HELD TAG DATA.
  pose proof (SAFE e HELD) as CHECK.
  unfold sealed_edge_admitted in CHECK. rewrite TAG in CHECK.
  destruct (m.(node_eqb) (edge_holder (raw_edge e)) m.(kernel)) eqn:OWNER; auto.
  rewrite DATA in CHECK. discriminate CHECK.
Qed.
Theorem nonkernel_asr_is_exact_admitted_invocation : forall m p st,
  InstalledSealingPolicy m p st -> forall e,
  st e = true -> edge_tag e = true ->
  m.(node_eqb) (edge_holder (raw_edge e)) m.(kernel) = false ->
  access_system_registers (edge_authority m (raw_edge e)) = true ->
  invocation_only m p e = true.
Proof.
  intros m p st SAFE e HELD TAG OWNER ASR.
  pose proof (SAFE e HELD) as CHECK.
  unfold sealed_edge_admitted in CHECK. rewrite TAG, OWNER, ASR in CHECK.
  simpl in CHECK. exact (proj2 (andb_split _ _ CHECK)).
Qed.
Theorem admitted_continuation_is_local : forall m p e,
  invocation_only m p e = true -> edge_seal e = BackwardSentry ->
  edge_local e = true /\ sealed_holds m e (admitted_continuations p) = true.
Proof.
  intros m p e CHECK SEAL. unfold invocation_only in CHECK. rewrite SEAL in CHECK.
  destruct (andb_split _ _ CHECK) as [_ H1].
  destruct (andb_split _ _ H1) as [_ H2].
  destruct (andb_split _ _ H2) as [_ H3].
  destruct (andb_split _ _ H3) as [_ H4].
  exact (andb_split _ _ H4).
Qed.

Theorem sealing_handoff_is_satisfiable : forall m p g,
  plan_roots_every_core m (erased_graph m g) = true ->
  sealing_graph_check m p g = true ->
  SealingAwareHandoff m p g (canonical m (erased_graph m g))
    (fun e => sealed_holds m e g).
Proof.
  intros m p g ROOTS CHECK. split.
  - apply the_handoff_is_satisfiable. exact ROOTS.
  - split; [intros; reflexivity|exact CHECK].
Qed.

(* Nonempty concrete distribution with private code/data and both admitted
   invocation forms. These are finite witnesses, not measured-image claims. *)
Definition p_asr_execute : Perm := Bits false false true true false.
Definition demo_kernel_code : SealedEdge demo_wx :=
  Build_SealedEdge demo_wx (Build_Edge demo_wx DemoKernel true p_asr_execute)
    true Unsealed false 0.
Definition demo_kernel_data : SealedEdge demo_wx :=
  Build_SealedEdge demo_wx (Build_Edge demo_wx DemoKernel false p_store)
    true Unsealed false 0.
Definition demo_forward_entry : SealedEdge demo_wx :=
  Build_SealedEdge demo_wx (Build_Edge demo_wx DemoApp true p_asr_execute)
    true ForwardSentry false 0.
Definition demo_backward_continuation : SealedEdge demo_wx :=
  Build_SealedEdge demo_wx (Build_Edge demo_wx DemoApp true p_asr_execute)
    true BackwardSentry true 1.
Definition demo_sealing_policy : SealingPolicy demo_wx :=
  Build_SealingPolicy demo_wx (fun r => r) (fun r => negb r)
    (cons demo_forward_entry nil) (cons demo_backward_continuation nil).
Definition demo_sealed_graph : SealedGraph demo_wx :=
  cons demo_kernel_code (cons demo_kernel_data
    (cons demo_forward_entry (cons demo_backward_continuation nil))).
Definition demo_sealed_state : SealedInstalled demo_wx :=
  fun e => sealed_holds demo_wx e demo_sealed_graph.
Definition demo_legacy_state : Installed demo_wx :=
  canonical demo_wx (erased_graph demo_wx demo_sealed_graph).

Example sealed_distribution_is_nonempty : count_of demo_sealed_graph = 4 := eq_refl.
Example sealed_distribution_passes :
  sealing_graph_check demo_wx demo_sealing_policy demo_sealed_graph = true := eq_refl.
Example legacy_asr_check_cannot_qualify_this_distribution :
  system_register_edges_are_the_kernels demo_wx
    (erased_graph demo_wx demo_sealed_graph) = false := eq_refl.
Theorem demo_sealing_handoff_holds :
  SealingAwareHandoff demo_wx demo_sealing_policy demo_sealed_graph
    demo_legacy_state demo_sealed_state.
Proof. apply sealing_handoff_is_satisfiable; reflexivity. Qed.
Theorem demo_installed_sealing_policy_holds :
  InstalledSealingPolicy demo_wx demo_sealing_policy demo_sealed_state.
Proof.
  exact (sealing_check_reaches_actual_installed_edges demo_wx demo_sealing_policy
    demo_sealed_graph demo_legacy_state demo_sealed_state demo_sealing_handoff_holds).
Qed.
Theorem demo_sealing_handoff_is_quiescent : Quiescent demo_wx demo_legacy_state.
Proof.
  eapply sealing_handoff_remains_quiescent; [exact demo_sealing_handoff_holds|].
  apply the_boolean_firmware_check_is_sound. reflexivity.
Qed.
Example nonkernel_sentries_are_actually_installed :
  demo_sealed_state demo_forward_entry = true /\
  demo_sealed_state demo_backward_continuation = true := conj eq_refl eq_refl.

Definition change_seal (m : Machine) (e : SealedEdge m) (seal : SealForm) :=
  Build_SealedEdge m (raw_edge e) (edge_tag e) seal (edge_local e) (edge_site e).
Definition change_site (m : Machine) (e : SealedEdge m) (site : nat) :=
  Build_SealedEdge m (raw_edge e) (edge_tag e) (edge_seal e) (edge_local e) site.
Definition change_local (m : Machine) (e : SealedEdge m) (local : bool) :=
  Build_SealedEdge m (raw_edge e) (edge_tag e) (edge_seal e) local (edge_site e).
Definition change_tag (m : Machine) (e : SealedEdge m) (tag : bool) :=
  Build_SealedEdge m (raw_edge e) tag (edge_seal e) (edge_local e) (edge_site e).
Definition dangerous_unsealed_export := change_seal demo_wx demo_forward_entry Unsealed.
Definition wrong_entry_site := change_site demo_wx demo_forward_entry 2.
Definition global_backward_export := change_local demo_wx demo_backward_continuation false.
Definition wrong_return_site := change_site demo_wx demo_backward_continuation 0.
Definition wrong_seal_export := change_seal demo_wx demo_forward_entry OtherSeal.
Definition backward_entry_export := change_seal demo_wx demo_forward_entry BackwardSentry.
Definition unsealed_text_without_asr : SealedEdge demo_wx :=
  Build_SealedEdge demo_wx (Build_Edge demo_wx DemoApp true p_exec)
    true Unsealed false 0.
Definition kernel_data_export : SealedEdge demo_wx :=
  Build_SealedEdge demo_wx (Build_Edge demo_wx DemoApp false p_store)
    true Unsealed false 0.
Definition sealing_edge_mutations : SealedGraph demo_wx :=
  cons dangerous_unsealed_export (cons wrong_entry_site
  (cons global_backward_export (cons wrong_return_site
  (cons wrong_seal_export (cons backward_entry_export
  (cons unsealed_text_without_asr (cons kernel_data_export nil))))))).
Example every_sealing_edge_mutation_is_refused :
  all_of (fun e => negb (sealed_edge_admitted demo_wx demo_sealing_policy e))
    sealing_edge_mutations = true := eq_refl.
Example sealing_edge_mutation_count : count_of sealing_edge_mutations = 8 := eq_refl.
Example dangerous_export_has_the_same_erased_edge :
  raw_edge dangerous_unsealed_export = raw_edge demo_forward_entry := eq_refl.
Example full_edge_identity_detects_seal_and_tag_changes :
  sealed_edge_eqb demo_wx dangerous_unsealed_export demo_forward_entry = false /\
  sealed_edge_eqb demo_wx (change_tag demo_wx demo_forward_entry false)
    demo_forward_entry = false := conj eq_refl eq_refl.

(* Listing an invalid shape cannot grant an exception to the seal/locality or
   kernel-data rules. These policies intentionally contain malformed entries. *)
Definition malformed_backward_policy : SealingPolicy demo_wx :=
  Build_SealingPolicy demo_wx (fun r => r) (fun r => negb r)
    (cons demo_forward_entry nil) (cons global_backward_export nil).
Example listing_a_global_backward_sentry_does_not_admit_it :
  sealed_edge_admitted demo_wx malformed_backward_policy global_backward_export = false := eq_refl.
Definition malformed_unsealed_policy : SealingPolicy demo_wx :=
  Build_SealingPolicy demo_wx (fun r => r) (fun r => negb r)
    (cons dangerous_unsealed_export nil) nil.
Example listing_unsealed_asr_does_not_admit_it :
  sealed_edge_admitted demo_wx malformed_unsealed_policy dangerous_unsealed_export = false := eq_refl.
Definition sealed_kernel_data_export : SealedEdge demo_wx :=
  Build_SealedEdge demo_wx (Build_Edge demo_wx DemoApp false p_asr_execute)
    true ForwardSentry false 0.
Definition malformed_data_policy : SealingPolicy demo_wx :=
  Build_SealingPolicy demo_wx (fun _ => true) (fun r => negb r)
    (cons sealed_kernel_data_export nil) nil.
Example kernel_data_stays_private_even_if_listed_as_a_sentry :
  invocation_only demo_wx malformed_data_policy sealed_kernel_data_export = true /\
  sealed_edge_admitted demo_wx malformed_data_policy sealed_kernel_data_export = false :=
  conj eq_refl eq_refl.

Definition injected_unsealed_state : SealedInstalled demo_wx := fun e =>
  orb (sealed_edge_eqb demo_wx e dangerous_unsealed_export) (demo_sealed_state e).
Theorem injected_unsealed_authority_refutes_installed_policy :
  ~ InstalledSealingPolicy demo_wx demo_sealing_policy injected_unsealed_state.
Proof. intros BAD. discriminate (BAD dangerous_unsealed_export eq_refl). Qed.
Theorem erased_handoff_does_not_supply_sealing_refinement :
  Handoff demo_wx (erased_graph demo_wx demo_sealed_graph) demo_legacy_state /\
  ~ SealingAwareHandoff demo_wx demo_sealing_policy demo_sealed_graph
      demo_legacy_state injected_unsealed_state.
Proof.
  split.
  - exact (sealing_handoff_preserves_original_handoff demo_wx demo_sealing_policy
      demo_sealed_graph demo_legacy_state demo_sealed_state demo_sealing_handoff_holds).
  - intros BAD. apply injected_unsealed_authority_refutes_installed_policy.
    exact (sealing_check_reaches_actual_installed_edges demo_wx demo_sealing_policy
      demo_sealed_graph demo_legacy_state injected_unsealed_state BAD).
Qed.

(* Inhabited record instances for the repository's domain gate. *)
Definition witness_SealedEdge : SealedEdge demo_wx := demo_forward_entry.
Definition witness_SealingPolicy : SealingPolicy demo_wx := demo_sealing_policy.

Print Assumptions seal_eqb_refl.
Print Assumptions seal_eqb_sound.
Print Assumptions site_eqb_refl.
Print Assumptions site_eqb_sound.
Print Assumptions sealed_edge_eqb_refl.
Print Assumptions sealed_edge_eqb_sound.
Print Assumptions sealing_check_reaches_actual_installed_edges.
Print Assumptions sealing_handoff_preserves_original_handoff.
Print Assumptions sealing_handoff_has_bounded_roots.
Print Assumptions sealing_handoff_remains_quiescent.
Print Assumptions unsealed_is_not_invocation_only.
Print Assumptions only_kernel_holds_usable_asr.
Print Assumptions only_kernel_holds_unsealed_kernel_text.
Print Assumptions only_kernel_holds_kernel_data.
Print Assumptions nonkernel_asr_is_exact_admitted_invocation.
Print Assumptions admitted_continuation_is_local.
Print Assumptions sealing_handoff_is_satisfiable.
Print Assumptions sealed_distribution_is_nonempty.
Print Assumptions sealed_distribution_passes.
Print Assumptions legacy_asr_check_cannot_qualify_this_distribution.
Print Assumptions demo_sealing_handoff_holds.
Print Assumptions demo_installed_sealing_policy_holds.
Print Assumptions demo_sealing_handoff_is_quiescent.
Print Assumptions nonkernel_sentries_are_actually_installed.
Print Assumptions every_sealing_edge_mutation_is_refused.
Print Assumptions sealing_edge_mutation_count.
Print Assumptions dangerous_export_has_the_same_erased_edge.
Print Assumptions full_edge_identity_detects_seal_and_tag_changes.
Print Assumptions listing_a_global_backward_sentry_does_not_admit_it.
Print Assumptions listing_unsealed_asr_does_not_admit_it.
Print Assumptions kernel_data_stays_private_even_if_listed_as_a_sentry.
Print Assumptions injected_unsealed_authority_refutes_installed_policy.
Print Assumptions erased_handoff_does_not_supply_sealing_refinement.
