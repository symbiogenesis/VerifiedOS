(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ScheduleRecord.v

   R-11-006, R-11-017 and R-11-018: the shared schedule statement.
   This extends CyclicExecutive's Frame without changing its consumers.
   Every duration is in the composition's common spine-time unit. Bounds,
   the finite operating-point catalog and its speed order are inputs, not
   measured facts. Memory terms distinguish M0.14's two latency classes.
   The input derivation and physical qualification remain outside U-05.

   A point is admissible for a partition only if it fits ALL that partition's
   declared visits in this mode. The selected point is the slowest such
   point in the declared class catalog. There is one selection function per
   tenant, so repeated visits cannot silently select different points.

   Re-entry reserves a bounded idle window in every core's target frame.
   This is the target-side statement seam. It does not discharge R-11-018's
   directed-edge certificates, cross-boundary service chains, memory and
   queue invariants, attestation implementation or arbitrary sequences.
   Neither the choice function below nor endpoint feasibility authorizes a
   mode transition. No theorem here claims that full requirement discharged.

   R-05-165 and R-05-166: closed record witnesses and executable accepted
   and rejected instances follow. No timing measurement is asserted.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-165 R-05-166 R-11-006 R-11-017 R-11-018
   SHA256: f9f034c1b7e50ef72f9a62e13fb6bb15fbcdbdbf125cf1753c8f481bca1240e5
   (*| END derived |*)
   ========================================================================= *)

Require Import CyclicExecutive.
Require Import EnsembleSchedule.
Require Import BoundaryCost.

Record OperatingPoint : Type := {
  operating_class : nat;
  speed_order : nat;
  first_read_time : nat;
  first_write_time : nat;
  second_read_time : nat;
  second_write_time : nat
}.

Record WorkBound : Type := {
  execution_time : nat;
  first_reads : nat;
  first_writes : nat;
  second_reads : nat;
  second_writes : nat
}.

Definition work_time (p : OperatingPoint) (b : WorkBound) : nat :=
  execution_time b + first_reads b * first_read_time p +
  first_writes b * first_write_time p + second_reads b * second_read_time p +
  second_writes b * second_write_time p.

(* A visit points into the existing frame; there is no second slot geometry.
   Its bounds list is indexed by the mode's complete point catalog. *)
Record Visit : Type := {
  visit_core : nat;
  visit_slot : nat;
  visit_class : nat;
  visit_deadline : nat;
  visit_bounds : list WorkBound;
  visit_noc_demand : nat
}.

Record NocGrant : Type := {
  grant_visit : nat;
  grant_resource : nat;
  grant_offset : nat;
  grant_width : nat;
  grant_bound : nat
}.

Record WatchdogWindow : Type := {
  watched_visit : nat;
  watchdog_open : nat;
  watchdog_close : nat
}.

Record ReentryWindow : Type := {
  entry_offset : nat;
  entry_width : nat;
  entry_work : nat
}.

Record ModeSchedule (T : Type) : Type := {
  schedule_frames : list (Frame T);
  schedule_points : list OperatingPoint;
  schedule_tenant_eq : forall x y : T, {x = y} + {x <> y};
  schedule_visits : list Visit;
  opp_assignment : T -> nat;
  schedule_noc : list NocGrant;
  schedule_watchdogs : list WatchdogWindow;
  schedule_reentry : ReentryWindow
}.

Arguments schedule_frames {T} _.
Arguments schedule_points {T} _.
Arguments schedule_visits {T} _.
Arguments schedule_tenant_eq {T} _ _ _.
Arguments opp_assignment {T} _ _.
Arguments schedule_noc {T} _.
Arguments schedule_watchdogs {T} _.
Arguments schedule_reentry {T} _.

Definition visit_frame {T} (m : ModeSchedule T) (v : Visit) : option (Frame T) :=
  nth_of (schedule_frames m) (visit_core v).

Definition visit_geometry {T} (m : ModeSchedule T) (v : Visit) : option (Slot T) :=
  match visit_frame m v with
  | None => None
  | Some f => nth_of (frame_slots f) (visit_slot v)
  end.

Definition visit_at_point (c : Composition) (m : ModeSchedule (Tenant c))
    (v : Visit) (i : nat) : bool :=
  match nth_of (schedule_points m) i, nth_of (visit_bounds v) i,
        visit_geometry m v with
  | Some p, Some b, Some s =>
      andb (Nat.eqb (operating_class p) (visit_class v))
        (andb (Nat.leb (work_time p b + boundary_cost (machine c) (boundary_inputs c))
                       (slot_width s))
          (Nat.leb (slot_offset s + work_time p b +
                    boundary_cost (machine c) (boundary_inputs c)) (visit_deadline v)))
  | _, _, _ => false
  end.

Definition partition_at_point (c : Composition) (m : ModeSchedule (Tenant c))
    (tenant : Tenant c) (i : nat) : bool :=
  all_of (fun v =>
    match visit_geometry m v with
    | None => false
    | Some s => if schedule_tenant_eq m tenant (slot_tenant s)
                then visit_at_point c m v i else true
    end) (schedule_visits m).
Fixpoint no_slower_visit_point (c : Composition) (m : ModeSchedule (Tenant c))
    (tenant : Tenant c) (selected_speed i : nat) (ps : list OperatingPoint) : bool :=
  match ps with
  | nil => true
  | cons p rest =>
      andb (orb (negb (partition_at_point c m tenant i))
                (Nat.leb selected_speed (speed_order p)))
           (no_slower_visit_point c m tenant selected_speed (S i) rest)
  end.

Definition visit_admits (c : Composition) (m : ModeSchedule (Tenant c))
    (v : Visit) : bool :=
  match visit_geometry m v with
  | None => false
  | Some s =>
      let selected := opp_assignment m (slot_tenant s) in
      match nth_of (schedule_points m) selected, nth_of (visit_bounds v) selected with
      | Some p, Some b =>
          andb (Nat.eqb (count_of (visit_bounds v)) (count_of (schedule_points m)))
            (andb (Nat.eqb (slot_bound s) (work_time p b))
              (andb (visit_at_point c m v selected)
                (no_slower_visit_point c m (slot_tenant s) (speed_order p) 0 (schedule_points m))))
      | _, _ => false
      end
  end.

Lemma slowest_scan_sound : forall c m tenant ps base rank index p,
  no_slower_visit_point c m tenant rank base ps = true ->
  nth_of ps index = Some p ->
  partition_at_point c m tenant (index + base) = true ->
  Nat.leb rank (speed_order p) = true.
Proof.
  intros c m tenant ps. induction ps as [|q rest IH]; intros base rank index p H Hnth Hfits.
  - discriminate Hnth.
  - simpl in H. destruct (andb_split _ _ H) as [Hhead Htail].
    destruct index as [|index].
    + simpl in Hnth. injection Hnth as Hnth. subst p.
      simpl in Hfits. rewrite Hfits in Hhead. exact Hhead.
    + simpl in Hnth. apply (IH (S base) rank index p Htail Hnth).
      rewrite plus_succ_r. exact Hfits.
Qed.

Theorem admitted_visit_selects_slowest_partition_point : forall c m v s p index q,
  visit_admits c m v = true ->
  visit_geometry m v = Some s ->
  nth_of (schedule_points m) (opp_assignment m (slot_tenant s)) = Some p ->
  nth_of (schedule_points m) index = Some q ->
  partition_at_point c m (slot_tenant s) index = true ->
  Nat.leb (speed_order p) (speed_order q) = true.
Proof.
  intros c m v s p index q H Hslot Hselected Hcandidate Hfits.
  unfold visit_admits in H. rewrite Hslot, Hselected in H.
  destruct (nth_of (visit_bounds v) (opp_assignment m (slot_tenant s))) as [b|];
    [|discriminate H].
  destruct (andb_split _ _ H) as [_ H1].
  destruct (andb_split _ _ H1) as [_ H2].
  destruct (andb_split _ _ H2) as [_ Hscan].
  apply (slowest_scan_sound c m (slot_tenant s) (schedule_points m) 0
           (speed_order p) index q Hscan Hcandidate).
  rewrite plus_zero_r. exact Hfits.
Qed.

Fixpoint visit_count (core slot : nat) (vs : list Visit) : nat :=
  match vs with
  | nil => 0
  | cons v rest =>
      (if andb (Nat.eqb core (visit_core v)) (Nat.eqb slot (visit_slot v)) then 1 else 0)
      + visit_count core slot rest
  end.

Fixpoint slots_covered {T} (vs : list Visit) (core index : nat)
    (ss : list (Slot T)) : bool :=
  match ss with
  | nil => true
  | cons _ rest => andb (Nat.eqb (visit_count core index vs) 1)
      (slots_covered vs core (S index) rest)
  end.

Fixpoint cores_covered {T} (vs : list Visit) (index : nat)
    (fs : list (Frame T)) : bool :=
  match fs with
  | nil => true
  | cons f rest => andb (slots_covered vs index 0 (frame_slots f))
      (cores_covered vs (S index) rest)
  end.

Definition grant_admits {T} (m : ModeSchedule T) (g : NocGrant) : bool :=
  match nth_of (schedule_visits m) (grant_visit g) with
  | None => false
  | Some v =>
      match visit_frame m v, visit_geometry m v with
      | Some f, Some s =>
          andb (Nat.leb (grant_offset g + grant_width g) (major_frame f))
          (andb (Nat.ltb 0 (grant_width g))
            (andb (Nat.leb (grant_bound g) (grant_width g))
              (andb (Nat.leb (phase_offset f + slot_offset s) (grant_offset g))
                (Nat.leb (grant_offset g + grant_width g)
                         (phase_offset f + slot_offset s + slot_width s)))))
      | _, _ => false
      end
  end.

Definition grants_disjoint (g h : NocGrant) : bool :=
  orb (negb (Nat.eqb (grant_resource g) (grant_resource h)))
    (orb (Nat.leb (grant_offset g + grant_width g) (grant_offset h))
         (Nat.leb (grant_offset h + grant_width h) (grant_offset g))).

Fixpoint noc_disjoint (gs : list NocGrant) : bool :=
  match gs with
  | nil => true
  | cons g rest => andb (all_of (grants_disjoint g) rest) (noc_disjoint rest)
  end.

Fixpoint granted_service (index : nat) (gs : list NocGrant) : nat :=
  match gs with
  | nil => 0
  | cons g rest =>
      (if Nat.eqb index (grant_visit g) then grant_bound g else 0) +
      granted_service index rest
  end.

Fixpoint noc_demand_covered (gs : list NocGrant) (index : nat) (vs : list Visit) : bool :=
  match vs with
  | nil => true
  | cons v rest => andb (Nat.leb (visit_noc_demand v) (granted_service index gs))
      (noc_demand_covered gs (S index) rest)
  end.

Definition watchdog_admits {T} (m : ModeSchedule T) (w : WatchdogWindow) : bool :=
  match nth_of (schedule_visits m) (watched_visit w) with
  | None => false
  | Some v =>
      match visit_frame m v, visit_geometry m v with
      | Some f, Some s =>
          andb (Nat.leb (watchdog_open w) (phase_offset f + slot_offset s))
            (andb (Nat.leb (phase_offset f + slot_offset s + slot_width s) (watchdog_close w))
              (Nat.leb (watchdog_close w) (phase_offset f + visit_deadline v)))
      | _, _ => false
      end
  end.

Fixpoint watchdog_count (index : nat) (ws : list WatchdogWindow) : nat :=
  match ws with
  | nil => 0
  | cons w rest => (if Nat.eqb index (watched_visit w) then 1 else 0) +
      watchdog_count index rest
  end.

Fixpoint watchdogs_cover (ws : list WatchdogWindow) (index : nat) (vs : list Visit) : bool :=
  match vs with
  | nil => true
  | cons _ rest => andb (Nat.eqb (watchdog_count index ws) 1)
      (watchdogs_cover ws (S index) rest)
  end.

Definition reentry_admits {T} (m : ModeSchedule T) : bool :=
  let e := schedule_reentry m in
  andb (Nat.ltb 0 (entry_width e))
    (andb (Nat.leb (entry_work e) (entry_width e))
      (all_of (core_admits_the_leap (Build_Leap 0 (entry_offset e) (entry_width e)))
              (schedule_frames m))).

Definition frame_periods_agree {T} (fs : list (Frame T)) : bool :=
  match fs with
  | nil => false
  | cons first rest =>
      andb (Nat.ltb 0 (major_frame first))
        (all_of (fun f => andb (Nat.eqb (major_frame first) (major_frame f))
                              (Nat.ltb (phase_offset f) (major_frame f))) fs)
  end.

Definition mode_admits (c : Composition) (m : ModeSchedule (Tenant c)) : bool :=
  andb (frame_periods_agree (schedule_frames m))
    (andb (all_of (admits c) (schedule_frames m))
      (andb (cores_covered (schedule_visits m) 0 (schedule_frames m))
        (andb (all_of (visit_admits c m) (schedule_visits m))
          (andb (all_of (grant_admits m) (schedule_noc m))
            (andb (noc_disjoint (schedule_noc m))
              (andb (noc_demand_covered (schedule_noc m) 0 (schedule_visits m))
                (andb (all_of (watchdog_admits m) (schedule_watchdogs m))
                  (andb (watchdogs_cover (schedule_watchdogs m) 0 (schedule_visits m))
                        (reentry_admits m))))))))).

Record ModeCatalog (T : Type) : Type := { global_modes : list (ModeSchedule T) }.
Arguments global_modes {T} _.

Definition catalog_admits (c : Composition) (k : ModeCatalog (Tenant c)) : bool :=
  andb (Nat.ltb 0 (count_of (global_modes k))) (all_of (mode_admits c) (global_modes k)).

Theorem every_catalog_mode_is_admitted : forall c k m,
  catalog_admits c k = true -> InList m (global_modes k) -> mode_admits c m = true.
Proof.
  intros c k m H Hin. unfold catalog_admits in H.
  destruct (andb_split _ _ H) as [_ Hall].
  exact (all_of_member _ _ _ _ Hall Hin).
Qed.

Theorem admitted_mode_preserves_frame_admission : forall c m f,
  mode_admits c m = true -> InList f (schedule_frames m) -> admits c f = true.
Proof.
  intros c m f H Hin. unfold mode_admits in H.
  destruct (andb_split _ _ H) as [_ Hnext]. clear H. rename Hnext into H.
  destruct (andb_split _ _ H) as [Hall _].
  exact (all_of_member _ _ _ _ Hall Hin).
Qed.

Theorem admitted_mode_checks_each_visit : forall c m v,
  mode_admits c m = true -> InList v (schedule_visits m) -> visit_admits c m v = true.
Proof.
  intros c m v H Hin. unfold mode_admits in H.
  destruct (andb_split _ _ H) as [_ Hnext]. clear H. rename Hnext into H.
  destruct (andb_split _ _ H) as [_ Hnext]. clear H. rename Hnext into H.
  destruct (andb_split _ _ H) as [_ Hnext]. clear H. rename Hnext into H.
  destruct (andb_split _ _ H) as [Hall _].
  exact (all_of_member _ _ _ _ Hall Hin).
Qed.

Theorem admitted_mode_has_checked_reentry : forall c m,
  mode_admits c m = true -> reentry_admits m = true.
Proof.
  intros c m H. unfold mode_admits in H.
  do 9 (destruct (andb_split _ _ H) as [_ Hnext]; clear H; rename Hnext into H). exact H.
Qed.

Theorem schedule_decidable : forall c m, {mode_admits c m = true} + {mode_admits c m = false}.
Proof. intros c m. destruct (mode_admits c m); [left | right]; reflexivity. Qed.

(* Q23d's fourth output is a further field. The compatibility projection
   takes the existing frames directly; no copied frame table can drift. *)
Record FourOutputSchedule (T : Type) : Type := {
  three_outputs : ModeSchedule T;
  ensemble_link_tables : list LinkTable;
  ensemble_crypto_core : nat;
  ensemble_verify_slot : nat;
  ensemble_tolerance : nat;
  ensemble_role : LeaderRole
}.

Definition ensemble_projection {T} (a : FourOutputSchedule T) : MemberSchedule T :=
  Build_MemberSchedule T (schedule_frames (three_outputs T a))
    (ensemble_crypto_core T a) (ensemble_verify_slot T a)
    (ensemble_tolerance T a) (ensemble_role T a).

Theorem fourth_output_preserves_frames : forall T (a : FourOutputSchedule T),
  ms_cores (ensemble_projection a) = schedule_frames (three_outputs T a).
Proof. intros T a. reflexivity. Qed.

(* Symbolic witness inputs. No literal below is a platform measurement. *)
Definition witness_OperatingPoint : OperatingPoint := Build_OperatingPoint 0 1 1 1 2 2.
Definition fast_point : OperatingPoint := Build_OperatingPoint 0 2 1 1 2 2.
Definition witness_WorkBound : WorkBound := Build_WorkBound 6 1 1 1 0.
Definition fast_bound : WorkBound := Build_WorkBound 1 1 1 1 0.
Definition witness_Visit : Visit := Build_Visit 0 0 0 50
  (cons witness_WorkBound (cons fast_bound nil)) 3.
Definition witness_NocGrant : NocGrant := Build_NocGrant 0 0 20 5 3.
Definition witness_WatchdogWindow : WatchdogWindow := Build_WatchdogWindow 0 20 50.
Definition witness_ReentryWindow : ReentryWindow := Build_ReentryWindow 0 10 8.
Definition schedule_frame (bound : nat) : Frame bool :=
  Build_Frame bool 100 0 nil (Build_Band bool (Build_Slot bool 30 20 bound 100 true) nil).

Definition bool_tenant_eq : forall x y : bool, {x = y} + {x <> y}.
Proof. decide equality. Defined.

Definition make_mode (selected bound : nat) (vs : list Visit) (gs : list NocGrant)
    (ws : list WatchdogWindow) (e : ReentryWindow) : ModeSchedule bool :=
  Build_ModeSchedule bool (cons (schedule_frame bound) nil)
    (cons witness_OperatingPoint (cons fast_point nil)) bool_tenant_eq vs (fun _ => selected) gs ws e.

Definition witness_ModeSchedule : ModeSchedule bool := make_mode 0 10
  (cons witness_Visit nil) (cons witness_NocGrant nil)
  (cons witness_WatchdogWindow nil) witness_ReentryWindow.

Example complete_mode_admits : mode_admits demo_composition witness_ModeSchedule = true := eq_refl.

Definition faster_mode : ModeSchedule bool := make_mode 1 5
  (cons witness_Visit nil) (cons witness_NocGrant nil)
  (cons witness_WatchdogWindow nil) witness_ReentryWindow.

Example non_slowest_point_is_refused :
  visit_at_point demo_composition faster_mode witness_Visit 1 = true /\
  visit_at_point demo_composition faster_mode witness_Visit 0 = true /\
  mode_admits demo_composition faster_mode = false := conj eq_refl (conj eq_refl eq_refl).

Definition overrun_visit : Visit := Build_Visit 0 0 0 50
  (cons (Build_WorkBound 31 0 0 0 0) (cons fast_bound nil)) 3.
Definition overrun_mode : ModeSchedule bool := make_mode 0 31
  (cons overrun_visit nil) (cons witness_NocGrant nil)
  (cons witness_WatchdogWindow nil) witness_ReentryWindow.
Example slot_overrun_is_refused : mode_admits demo_composition overrun_mode = false := eq_refl.

Definition fast_required_visit : Visit := Build_Visit 0 0 0 50
  (cons (Build_WorkBound 31 0 0 0 0) (cons fast_bound nil)) 3.
Definition second_mode : ModeSchedule bool := make_mode 1 5
  (cons fast_required_visit nil) (cons witness_NocGrant nil)
  (cons witness_WatchdogWindow nil) witness_ReentryWindow.
Example faster_point_admits_when_required : mode_admits demo_composition second_mode = true := eq_refl.

Definition two_visit_mode : ModeSchedule bool :=
  Build_ModeSchedule bool
    (cons (Build_Frame bool 100 0 nil
      (Build_Band bool (Build_Slot bool 30 20 5 100 true)
        (cons (Build_Slot bool 30 60 5 100 true) nil))) nil)
    (cons witness_OperatingPoint (cons fast_point nil)) bool_tenant_eq
    (cons (Build_Visit 0 0 0 50 (cons witness_WorkBound (cons fast_bound nil)) 0)
      (cons (Build_Visit 0 1 0 90
        (cons (Build_WorkBound 31 0 0 0 0) (cons fast_bound nil)) 0) nil))
    (fun _ => 1) nil
    (cons (Build_WatchdogWindow 0 20 50) (cons (Build_WatchdogWindow 1 60 90) nil))
    witness_ReentryWindow.

Example slowest_point_is_joint_across_a_partitions_visits :
  mode_admits demo_composition two_visit_mode = true := eq_refl.

Definition witness_ModeCatalog : ModeCatalog bool :=
  Build_ModeCatalog bool (cons witness_ModeSchedule (cons second_mode nil)).
Example each_global_mode_admits : catalog_admits demo_composition witness_ModeCatalog = true := eq_refl.

Example missing_watchdog_is_refused : mode_admits demo_composition
  (make_mode 0 10 (cons witness_Visit nil) (cons witness_NocGrant nil) nil witness_ReentryWindow)
  = false := eq_refl.
Example overlapping_noc_is_refused : mode_admits demo_composition
  (make_mode 0 10 (cons witness_Visit nil) (cons witness_NocGrant (cons witness_NocGrant nil))
    (cons witness_WatchdogWindow nil) witness_ReentryWindow) = false := eq_refl.
Example unserved_noc_demand_is_refused : mode_admits demo_composition
  (make_mode 0 10 (cons witness_Visit nil) nil (cons witness_WatchdogWindow nil)
    witness_ReentryWindow) = false := eq_refl.
Example occupied_reentry_is_refused : mode_admits demo_composition
  (make_mode 0 10 (cons witness_Visit nil) (cons witness_NocGrant nil)
    (cons witness_WatchdogWindow nil) (Build_ReentryWindow 20 10 8)) = false := eq_refl.
Example overrun_reentry_is_refused : mode_admits demo_composition
  (make_mode 0 10 (cons witness_Visit nil) (cons witness_NocGrant nil)
    (cons witness_WatchdogWindow nil) (Build_ReentryWindow 0 10 11)) = false := eq_refl.
Example uncovered_slot_is_refused : mode_admits demo_composition
  (make_mode 0 10 nil nil nil witness_ReentryWindow) = false := eq_refl.
Example duplicate_visit_is_refused : mode_admits demo_composition
  (make_mode 0 10 (cons witness_Visit (cons witness_Visit nil))
    (cons witness_NocGrant nil) (cons witness_WatchdogWindow nil) witness_ReentryWindow)
  = false := eq_refl.
Example missing_point_bound_is_refused : mode_admits demo_composition
  (make_mode 0 10 (cons (Build_Visit 0 0 0 50 (cons witness_WorkBound nil) 3) nil)
    (cons witness_NocGrant nil) (cons witness_WatchdogWindow nil) witness_ReentryWindow)
  = false := eq_refl.
Example wrong_class_is_refused : mode_admits demo_composition
  (make_mode 0 10 (cons (Build_Visit 0 0 1 50
      (cons witness_WorkBound (cons fast_bound nil)) 3) nil)
    (cons witness_NocGrant nil) (cons witness_WatchdogWindow nil) witness_ReentryWindow)
  = false := eq_refl.
Example early_watchdog_is_refused : mode_admits demo_composition
  (make_mode 0 10 (cons witness_Visit nil) (cons witness_NocGrant nil)
    (cons (Build_WatchdogWindow 0 20 49) nil) witness_ReentryWindow) = false := eq_refl.
Example bad_mode_refuses_catalog : catalog_admits demo_composition
  (Build_ModeCatalog bool (cons witness_ModeSchedule (cons faster_mode nil))) = false := eq_refl.
Example empty_catalog_is_refused : catalog_admits demo_composition
  (Build_ModeCatalog bool nil) = false := eq_refl.

Definition witness_FourOutputSchedule : FourOutputSchedule bool :=
  Build_FourOutputSchedule bool witness_ModeSchedule (cons demo_link nil) 0 0 1 Root.
Example fourth_output_compiles_against_q23d :
  all_of (admits demo_composition) (ms_cores (ensemble_projection witness_FourOutputSchedule))
  = true := eq_refl.

Print Assumptions every_catalog_mode_is_admitted.
Print Assumptions admitted_visit_selects_slowest_partition_point.
Print Assumptions admitted_mode_preserves_frame_admission.
Print Assumptions admitted_mode_checks_each_visit.
Print Assumptions admitted_mode_has_checked_reentry.
Print Assumptions schedule_decidable.
Print Assumptions fourth_output_preserves_frames.
Print Assumptions complete_mode_admits.
Print Assumptions non_slowest_point_is_refused.
Print Assumptions slot_overrun_is_refused.
Print Assumptions each_global_mode_admits.
