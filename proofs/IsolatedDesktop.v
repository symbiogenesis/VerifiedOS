(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   Q34i's two-domain instantiation of the elastic-domain contract.
   R-14-011c gives the general and isolated domains distinct labels and pools;
   R-17-007b confines runtime observations to each label. R-07-037e's
   envelope and R-08-047c's pool-capability confinement remain unchanged.
   This is a contract-level composition witness, not a kernel refinement,
   a pool-service refinement or a first-release resident-memory measurement.
   The state projection reads the complete other pool as outside observation;
   the two-domain relation separately preserves the other's complete DState.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-07-037e R-08-047c R-14-011c R-17-007b
   SHA256: d7e3948a4419ef73af88f61f08d1f0c7457c9b8c0a4b61ea0e5508694b00a995
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith.
Require Import CyclicExecutive MemoryPlan PartitionContext ElasticDomain.
Import ListNotations.
Local Open Scope nat_scope.

Definition isolated_envelope : Domain := {|
  dom_label := 4;
  dom_members := [5];
  dom_manifest := fun m => plain_manifest 5 4;
  dom_cores := [0];
  dom_dormant := fun m c => Nat.eqb m 5 && Nat.eqb c 0;
  dom_extent := fun c => if c is FirstClass then (3072, 1024) else (4096, 2048)
|}.

Definition desktop_frame : Frame nat :=
  Build_Frame nat 100 0 []
    (Build_Band nat (Build_Slot nat 60 0 0 100 3)
      [Build_Slot nat 40 60 0 100 4]).

Definition isolated_decl : Decl := {|
  dc_count := 1; dc_weight := fun _ => 1; dc_request := fun _ => 1;
  dc_focus_weight := 1; dc_focus_request := 1;
  dc_call_interval := 1; dc_yield_bound := 2; dc_step := 5;
  dc_widths := [40]; dc_app := fun _ => 5;
  dc_machine := demo_rotation_swaps
|}.

Theorem the_isolated_declaration_enumerates_its_single_application :
  decl_enumerates isolated_envelope isolated_decl = true
  /\ decl_admits isolated_decl = true.
Proof. split; reflexivity. Qed.

Theorem two_labels_have_envelopes_on_one_core :
  envelope_admits demo_domain = true /\ envelope_admits isolated_envelope = true
  /\ dom_label demo_domain <> dom_label isolated_envelope
  /\ dom_cores demo_domain = [0] /\ dom_cores isolated_envelope = [0]
  /\ slot_tenant (nth 0 (frame_slots desktop_frame) (Build_Slot nat 0 0 0 0 0)) = 3
  /\ slot_tenant (nth 1 (frame_slots desktop_frame) (Build_Slot nat 0 0 0 0 0)) = 4.
Proof. repeat split; try reflexivity; discriminate. Qed.

Record DesktopState : Type := {
  dt_general : DState;
  dt_isolated : DState;
  dt_general_pool : nat -> nat;
  dt_isolated_pool : nat -> nat
}.

Definition own_dispatch (isolated : bool) (s : DesktopState) : DState :=
  if isolated then dt_isolated s else dt_general s.

Definition own_pool (isolated : bool) (s : DesktopState) : nat -> nat :=
  if isolated then dt_isolated_pool s else dt_general_pool s.

Definition domain_projection (isolated : bool) (s : DesktopState) : Global := {|
  g_frame := desktop_frame;
  g_domain := own_dispatch isolated s;
  g_others := own_pool (negb isolated) s
|}.

Definition ReadsOwnDesktop {X : Type} (isolated : bool)
    (read : DesktopState -> X) : Prop :=
  forall s s', own_dispatch isolated s = own_dispatch isolated s' ->
    own_pool isolated s = own_pool isolated s' -> read s = read s'.

Definition desktop_dispatch (isolated : bool) (d : Decl) (s : DesktopState) : option nat :=
  spec_choice d (domain_projection isolated s).

Definition desktop_pool_read (isolated : bool) (address : nat) (s : DesktopState) : nat :=
  own_pool isolated s address.

Theorem each_dispatch_instantiates_the_existing_confinement :
  forall isolated d, ReadsOwnDesktop isolated (desktop_dispatch isolated d).
Proof.
  intros isolated d s s' Hd _.
  exact (the_dispatch_reads_only_its_label d
    (domain_projection isolated s) (domain_projection isolated s') Hd).
Qed.

Theorem each_pool_reads_its_own_label :
  forall isolated address, ReadsOwnDesktop isolated (desktop_pool_read isolated address).
Proof. intros isolated address s s' _ Hp. unfold desktop_pool_read. rewrite Hp. reflexivity. Qed.

(* No mutable frame lives in this state. A domain step may change its own
   dispatch and pool, but preserves the other's entire state, not a digest. *)
Definition desktop_step (isolated : bool) (t : DState -> DState -> Prop)
    (s s' : DesktopState) : Prop :=
  t (own_dispatch isolated s) (own_dispatch isolated s')
  /\ own_dispatch (negb isolated) s' = own_dispatch (negb isolated) s
  /\ own_pool (negb isolated) s' = own_pool (negb isolated) s.

Theorem each_step_instantiates_the_existing_envelope :
  forall isolated t s s', desktop_step isolated t s s' ->
    within_the_envelope t (domain_projection isolated s) (domain_projection isolated s')
  /\ own_dispatch (negb isolated) s' = own_dispatch (negb isolated) s.
Proof.
  intros isolated t s s' [Ht [Hd Hp]]. split; [|exact Hd].
  split; [exact Ht|]. split; [reflexivity|exact Hp].
Qed.

Theorem each_projected_transition_moves_nothing_outside :
  forall t, MovesNothingOutside (within_the_envelope t).
Proof. exact every_domain_transition_stays_inside. Qed.

Definition quiet_desktop : DesktopState := {|
  dt_general := cx_start; dt_isolated := cx_start;
  dt_general_pool := fun _ => 0; dt_isolated_pool := fun _ => 0
|}.

Definition other_pool_busy (isolated : bool) : DesktopState := {|
  dt_general := cx_start; dt_isolated := cx_start;
  dt_general_pool := fun _ => if isolated then 1 else 0;
  dt_isolated_pool := fun _ => if isolated then 0 else 1
|}.

Definition cross_dispatch (isolated : bool) (s : DesktopState) : option nat :=
  leaky_choice (if isolated then isolated_decl else cx_decl)
    (domain_projection isolated s).

Definition cross_pool_read (isolated : bool) (s : DesktopState) : nat :=
  own_pool isolated s 0 + own_pool (negb isolated) s 0.

Theorem reading_the_other_domain_refutes_either_dispatch :
  forall isolated, ~ ReadsOwnDesktop isolated (cross_dispatch isolated).
Proof.
  intros isolated H.
  assert (Hd : own_dispatch isolated quiet_desktop =
               own_dispatch isolated (other_pool_busy isolated)) by
    (destruct isolated; reflexivity).
  assert (Hp : own_pool isolated quiet_desktop =
               own_pool isolated (other_pool_busy isolated)) by
    (destruct isolated; reflexivity).
  specialize (H quiet_desktop (other_pool_busy isolated) Hd Hp).
  destruct isolated; cbn in H; discriminate H.
Qed.

Theorem reading_the_other_domain_refutes_either_pool :
  forall isolated, ~ ReadsOwnDesktop isolated (cross_pool_read isolated).
Proof.
  intros isolated H.
  assert (Hd : own_dispatch isolated quiet_desktop =
               own_dispatch isolated (other_pool_busy isolated)) by
    (destruct isolated; reflexivity).
  assert (Hp : own_pool isolated quiet_desktop =
               own_pool isolated (other_pool_busy isolated)) by
    (destruct isolated; reflexivity).
  specialize (H quiet_desktop (other_pool_busy isolated) Hd Hp).
  destruct isolated; cbn in H; discriminate H.
Qed.

(* A concrete changing step witnesses that the relation is inhabited. *)
Definition general_pool_busy : DesktopState := {|
  dt_general := quiet_state; dt_isolated := cx_start;
  dt_general_pool := fun _ => 1; dt_isolated_pool := fun _ => 0
|}.

Example a_real_general_change_preserves_the_isolated_domain :
  desktop_step false (fun _ _ => True) quiet_desktop general_pool_busy
  /\ dt_general_pool quiet_desktop 0 <> dt_general_pool general_pool_busy 0
  /\ dt_isolated general_pool_busy = dt_isolated quiet_desktop
  /\ dt_isolated_pool general_pool_busy = dt_isolated_pool quiet_desktop.
Proof. repeat split; try exact I; try reflexivity; discriminate. Qed.

Definition isolated_distribution : Distribution := {|
  cd_in_domain := fun p => Nat.eqb p 5;
  cd_edges := [{| e_from := 0; e_to := 5; e_kind := RegisterEndpoint false false |}];
  cd_pool_base := 4096; cd_pool_span := 2048
|}.

Definition isolated_holdings : Holdings := [(5, chunk_cap 4096 64)].

Theorem the_one_way_request_endpoint_does_not_export_the_isolated_pool :
  edges_confine isolated_distribution = true
  /\ forall hs, Reach isolated_distribution isolated_holdings hs ->
      PoolConfined isolated_distribution hs.
Proof.
  split; [reflexivity|]. intros hs Hr.
  apply (confinement_survives_every_transfer isolated_distribution isolated_holdings hs).
  - reflexivity.
  - intros h k Hin _. destruct Hin as [Hin|[]]. injection Hin as Hh _. subst h. reflexivity.
  - exact Hr.
Qed.

Definition witness_DesktopState : DesktopState := quiet_desktop.
