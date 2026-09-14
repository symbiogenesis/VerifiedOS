(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   MemoryPlannerContracts.v

   Conditional contract extraction and checked-candidate selection for the
   standalone memory planner. The Python implementation lives in
   tools/vos/memory_planner_contracts.py and tools/vos/memory_planner.py.

   A component contract supplies all paths, with each path recording the
   allocated identities at every event boundary. An identity stays allocated
   through lexical release, retained values, outstanding device work and the
   reuse barrier. `conflictb` unions coexistence over every supplied path.
   `extracted_placement_safe` proves that a layout checked against that graph
   separates all simultaneously allocated objects on every supplied path.
   `coexisting_objects_cannot_touch_one_byte` gives its physical-address form.
   Paths may end normally, exceptionally, by cancellation or by timeout: the
   theorem depends on membership in the supplied contract, not the outcome.

   `barrier_sound` proves the separate reuse premise: acceptance of the full
   barrier entails that lexical and retained holders and authority have ended,
   accepted device work is zero, and the post-completion sweep and scrub hold.
   `late_device_blocks_barrier` distinguishes lexical release and revocation
   from device completion. These are modeled completion facts, not measured
   deadlines, and no hypothesis says that timeout implies completion.

   The source-to-contract and implementation boundary is explicit. Theorems
   quantify over contract paths, not Vela source or machine executions. To
   apply them to a program, its frontend must establish that every reachable
   occupancy state is represented in one of those paths and that its barrier
   operations establish these facts. Python parsing, bounded path expansion,
   graph construction and target enforcement have not been proved to refine
   these Gallina definitions. Their negative and generated tests are bounded
   executable evidence. This file does not discharge an admission requirement.

   The checked selector has a second independent theorem. Starting with a
   valid baseline, every accepted candidate passes a sound validity check and
   a sound componentwise baseline bound. Any deterministic preference function
   can choose among those candidates: `selection_nonregression` proves that
   the returned candidate is valid and no pool's selected objective exceeds
   the baseline's. Missing candidates include timeout and search failure. This
   says nothing about planning cost, runtime speed, residency or optimality.

   R-08-014 supplies the interference obligation this graph model addresses;
   R-08-015 keeps that obligation separate from safe reuse, whose containment
   and full sweep prerequisites are stated by R-08-006 and R-08-007a. The
   selector's componentwise bound illustrates R-08-012d's span non-regression
   constraint without proving its locality or timing clauses. All are cited,
   never claimed. R-05-163 audits the compiled assumptions. For R-05-165 and
   R-05-166, each record has a named witness, a safe two-object layout is
   instantiated, an aliased layout is rejected, late completion blocks the
   barrier and a selector example rejects invalid and over-budget candidates.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-165 R-05-166 R-08-006 R-08-007a R-08-012d R-08-014 R-08-015
   SHA256: 1abb15fb1e97a004df1331f7e13d6dbac54e1cac3e266d9fe7c0f91e27a4ddb1
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Import ListNotations.

Record Lease := {
  lexical_holder : bool;
  retained_holder : bool;
  live_authority : bool;
  outstanding_devices : nat;
  sweep_complete : bool;
  scrub_complete : bool
}.

Definition witness_Lease : Lease :=
  {| lexical_holder := false; retained_holder := false;
     live_authority := false; outstanding_devices := 0;
     sweep_complete := true; scrub_complete := true |}.

Definition no_old_users (s : Lease) : Prop :=
  lexical_holder s = false /\ retained_holder s = false /\
  live_authority s = false /\ outstanding_devices s = 0.

Definition barrierb (s : Lease) : bool :=
  negb (lexical_holder s) && negb (retained_holder s) &&
  negb (live_authority s) && (outstanding_devices s =? 0) &&
  sweep_complete s && scrub_complete s.

Theorem barrier_sound : forall s,
  barrierb s = true ->
  no_old_users s /\ sweep_complete s = true /\ scrub_complete s = true.
Proof.
  intros s H. unfold barrierb in H. unfold no_old_users.
  repeat rewrite andb_true_iff in H.
  repeat rewrite negb_true_iff in H.
  rewrite Nat.eqb_eq in H. tauto.
Qed.

Theorem late_device_blocks_barrier : forall s,
  0 < outstanding_devices s -> barrierb s = false.
Proof.
  intros s H. destruct (barrierb s) eqn:HB; auto.
  apply barrier_sound in HB. unfold no_old_users in HB. intuition lia.
Qed.

Definition late_lease : Lease :=
  {| lexical_holder := false; retained_holder := false;
     live_authority := false; outstanding_devices := 1;
     sweep_complete := true; scrub_complete := true |}.

Example drained_barrier_accepted : barrierb witness_Lease = true.
Proof. reflexivity. Qed.

Example late_device_barrier_rejected : barrierb late_lease = false.
Proof. reflexivity. Qed.

Example lexical_release_alone_is_not_reuse :
  lexical_holder late_lease = false /\ live_authority late_lease = false /\
  ~ no_old_users late_lease.
Proof. unfold no_old_users, late_lease; simpl; intuition discriminate. Qed.

Definition Snapshot := list nat.
Definition ContractPath := list Snapshot.
Definition Contract := list ContractPath.

Definition memberb (a : nat) (snapshot : Snapshot) : bool :=
  existsb (Nat.eqb a) snapshot.

Lemma memberb_spec : forall a snapshot,
  memberb a snapshot = true <-> In a snapshot.
Proof.
  intros a snapshot. unfold memberb. rewrite existsb_exists.
  split.
  - intros [b [HB HE]]. apply Nat.eqb_eq in HE. subst b. exact HB.
  - intro HA. exists a. split; [exact HA | apply Nat.eqb_refl].
Qed.

Definition conflicted_in (a b : nat) (snapshot : Snapshot) : bool :=
  memberb a snapshot && memberb b snapshot.

Definition conflictb (contract : Contract) (a b : nat) : bool :=
  existsb (fun path => existsb (conflicted_in a b) path) contract.

Theorem conflict_extraction_exact : forall contract a b,
  conflictb contract a b = true <->
  exists path snapshot, In path contract /\ In snapshot path /\
                        In a snapshot /\ In b snapshot.
Proof.
  intros contract a b. unfold conflictb.
  rewrite existsb_exists. split.
  - intros [path [HP HC]]. apply existsb_exists in HC.
    destruct HC as [snapshot [HS HC]]. unfold conflicted_in in HC.
    apply andb_true_iff in HC. destruct HC as [HA HB].
    apply memberb_spec in HA. apply memberb_spec in HB.
    exists path, snapshot. auto.
  - intros [path [snapshot [HP [HS [HA HB]]]]].
    exists path. split; auto. apply existsb_exists.
    exists snapshot. split; auto. unfold conflicted_in.
    apply andb_true_iff. split; apply memberb_spec; assumption.
Qed.

Record Layout := {
  pool_of : nat -> nat;
  offset_of : nat -> nat;
  size_of : nat -> nat
}.

Definition witness_Layout : Layout :=
  {| pool_of := fun _ => 0;
     offset_of := fun i => if i =? 0 then 0 else 4;
     size_of := fun i => if i =? 0 then 4 else 3 |}.

Definition separated (layout : Layout) (a b : nat) : Prop :=
  pool_of layout a <> pool_of layout b \/ size_of layout a = 0 \/
  size_of layout b = 0 \/
  offset_of layout a + size_of layout a <= offset_of layout b \/
  offset_of layout b + size_of layout b <= offset_of layout a.

Definition valid_graph_layout (contract : Contract) (layout : Layout) : Prop :=
  forall a b, a <> b -> conflictb contract a b = true -> separated layout a b.

Theorem extracted_placement_safe : forall contract layout,
  valid_graph_layout contract layout ->
  forall path snapshot a b, In path contract -> In snapshot path ->
    In a snapshot -> In b snapshot -> a <> b -> separated layout a b.
Proof.
  intros contract layout HV path snapshot a b HP HS HA HB HD.
  apply HV; auto. apply conflict_extraction_exact.
  exists path, snapshot. auto.
Qed.

Definition touches (layout : Layout) (object pool byte : nat) : Prop :=
  pool_of layout object = pool /\ offset_of layout object <= byte /\
  byte < offset_of layout object + size_of layout object.

Theorem coexisting_objects_cannot_touch_one_byte : forall contract layout,
  valid_graph_layout contract layout ->
  forall path snapshot a b pool byte,
    In path contract -> In snapshot path -> In a snapshot -> In b snapshot ->
    a <> b -> touches layout a pool byte -> ~ touches layout b pool byte.
Proof.
  intros contract layout HV path snapshot a b pool byte HP HS HA HB HD TA TB.
  pose proof (extracted_placement_safe contract layout HV path snapshot
              a b HP HS HA HB HD) as HSep.
  unfold separated in HSep. unfold touches in TA, TB.
  destruct TA as [PA [LA UA]]. destruct TB as [PB [LB UB]].
  destruct HSep as [P | [ZA | [ZB | [AB | BA]]]]; (congruence || lia).
Qed.

(* Distinct slots are independently schedulable. Their cross-slot conflicts
   are conservative even where individual paths have different outcomes. *)
Definition slot_object := (nat * nat)%type.
Definition slot_conflict (contract : Contract) (a b : slot_object) : Prop :=
  fst a <> fst b \/ conflictb contract (snd a) (snd b) = true.

Theorem independent_slots_conflict : forall contract slot_a slot_b a b,
  slot_a <> slot_b -> slot_conflict contract (slot_a, a) (slot_b, b).
Proof. intros. left. assumption. Qed.

Definition demo_contract : Contract :=
  [ [[]; [0]; [0; 1]; [1]; []];
    [[]; [0]; []] ].

Example exceptional_path_in_contract : In [[]; [0]; []] demo_contract.
Proof. simpl. auto. Qed.

Example late_overlap_in_graph : conflictb demo_contract 0 1 = true.
Proof. reflexivity. Qed.

Lemma demo_members : forall path snapshot a,
  In path demo_contract -> In snapshot path -> In a snapshot -> a = 0 \/ a = 1.
Proof.
  intros path snapshot a HP HS HA.
  unfold demo_contract in HP. simpl in HP.
  destruct HP as [HP | [HP | HP]]; try contradiction; subst path;
    simpl in HS; repeat destruct HS as [HS | HS]; try contradiction;
    subst snapshot; simpl in HA; intuition.
Qed.

Example safe_layout_checked : valid_graph_layout demo_contract witness_Layout.
Proof.
  intros a b HD HC. apply conflict_extraction_exact in HC.
  destruct HC as [path [snapshot [HP [HS [HA HB]]]]].
  pose proof (demo_members path snapshot a HP HS HA) as DA.
  pose proof (demo_members path snapshot b HP HS HB) as DB.
  destruct DA as [DA | DA], DB as [DB | DB]; subst a; subst b;
    unfold separated, witness_Layout; simpl; intuition.
Qed.

Definition aliased_layout : Layout :=
  {| pool_of := fun _ => 0; offset_of := fun _ => 0; size_of := fun _ => 4 |}.

Example aliased_layout_rejected : ~ valid_graph_layout demo_contract aliased_layout.
Proof.
  intro HV. specialize (HV 0 1 ltac:(lia) late_overlap_in_graph).
  unfold separated, aliased_layout in HV. simpl in HV. intuition lia.
Qed.

(* The checker predicates are parameters, accompanied by explicit soundness
   hypotheses; none is an axiom or an assertion about the Python checker. *)
Fixpoint select_checked {A : Type} (validb withinb : A -> bool)
  (prefer : A -> A -> bool) (candidates : list A) (best : A) : A :=
  match candidates with
  | [] => best
  | candidate :: rest =>
      select_checked validb withinb prefer rest
        (if validb candidate && withinb candidate && prefer candidate best
         then candidate else best)
  end.

Theorem selection_preserves : forall (A : Type) (valid bounded : A -> Prop)
  (validb withinb : A -> bool) (prefer : A -> A -> bool),
  (forall candidate, validb candidate = true -> valid candidate) ->
  (forall candidate, withinb candidate = true -> bounded candidate) ->
  forall candidates best, valid best -> bounded best ->
    valid (select_checked validb withinb prefer candidates best) /\
    bounded (select_checked validb withinb prefer candidates best).
Proof.
  intros A valid bounded validb withinb prefer VS BS candidates.
  induction candidates as [| candidate rest IH]; intros best HV HB.
  - simpl. auto.
  - simpl. destruct (validb candidate && withinb candidate && prefer candidate best)
      eqn:HC.
    + apply andb_true_iff in HC. destruct HC as [HC _].
      apply andb_true_iff in HC. destruct HC as [CV CB].
      apply IH; auto.
    + apply IH; auto.
Qed.

Theorem selection_nonregression : forall (A : Type) (valid : A -> Prop)
  (objective : A -> nat -> nat) (validb withinb : A -> bool)
  (prefer : A -> A -> bool) (baseline : A),
  valid baseline ->
  (forall candidate, validb candidate = true -> valid candidate) ->
  (forall candidate, withinb candidate = true ->
     forall pool, objective candidate pool <= objective baseline pool) ->
  forall candidates,
    valid (select_checked validb withinb prefer candidates baseline) /\
    forall pool, objective (select_checked validb withinb prefer candidates baseline) pool
                 <= objective baseline pool.
Proof.
  intros A valid objective validb withinb prefer baseline HV VS BS candidates.
  apply (selection_preserves A valid
    (fun candidate => forall pool, objective candidate pool <= objective baseline pool)
    validb withinb prefer VS BS candidates baseline); auto.
Qed.

Example selector_rejects_invalid_and_regressions :
  select_checked (fun n => n <=? 8) (fun n => n <=? 6) Nat.ltb [20; 7; 4; 9; 5] 6 = 4.
Proof. reflexivity. Qed.

Example selector_witness_valid_and_nonregressing :
  let selected := select_checked (fun n => n <=? 8) (fun n => n <=? 6)
                                Nat.ltb [20; 7; 4; 9; 5] 6 in
  selected <= 8 /\ selected <= 6.
Proof. simpl. lia. Qed.

Example invalid_baseline_violates_premise : ~ (20 <= 8).
Proof. lia. Qed.

Print Assumptions barrier_sound.
Print Assumptions late_device_blocks_barrier.
Print Assumptions conflict_extraction_exact.
Print Assumptions extracted_placement_safe.
Print Assumptions coexisting_objects_cannot_touch_one_byte.
Print Assumptions selection_nonregression.
