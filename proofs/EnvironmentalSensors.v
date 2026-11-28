(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   EnvironmentalSensors.v

   Specification, structural invariants, and non-vacuity witnesses for Q41a-i
   environmental fault sensors and the single RoT fail-stop boundary:
   - Four selected sensor families (SupplyWindow, ClockMonitor, TimingReplica,
     OpticalPhotocurrent) with immutable qualified settings and unit-consistent
     inequalities; no `pending` in accepted records; no software-writable
     thresholds, monitor disables, dynamic calibration, added ISA/CSR surface,
     operand sampling, or backside optical occlusion (R-16-008g).
   - Total topology coverage over P (RoT, both physical S-class lockstep
     instances S0/S1, and all composed C/V/M islands): every `rails(P)` and
     `clocks(P)` member from parent to leaf, including the RoT's independent
     slow clock (R-15-195, R-15-196), every datapath, and every logic-tier
     region at declared pitch.
   - Acyclic monitor dependency graph refusing self-justifying monitors,
     RoT slow-clock self-observation, adaptive clock references, and
     guarded-only liveness justifications.
   - Single fail-stop boundary (R-16-005, R-16-008g, R-15-198, R-17-030m):
     - Island-only trips persistently latch the RoT fail-stop latch and freeze
       release of affected islands regardless of software masks or acks;
       transport acknowledgement cannot clear the latch.
     - RoT or RoT-shared trips assert the RoT watchdog bite immediately,
       independent of the RoT CPU, main/spine clock, or firmware mailbox.
     - Disabling, corrupt, open/stuck, stopped-reference, or broken-transducer
       sensor faults latch failure rather than disarming.
     - Table-authorized off/gated intervals require confirmed reset/isolation;
       unexpected deactivation while active or transition overrun trips.
     - Power loss holds reset until the boundary is healthy and reset-table
       recovery completes; attested events expose only closed
       EnvironmentalTripClass and recurrent counts without raw analog
       values or site telemetry.

   Assumptions and non-vacuity (R-05-163, R-05-164, R-05-165, R-05-166):
   - Zero axioms (`Closed under the global context`), prelude + ProofSupport
     only, and every declared Record has a closed `witness_<Record>` inhabitant.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-15-195 R-15-196 R-15-198 R-16-005
      R-16-008g R-17-030m
   SHA256: 7710990c4129776fa82270092b1d27167f7f98c0e7f7aaf6bd4bf582fb385bc4
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport.

Module PS := ProofSupport.

(* =========================================================================
   1. Small prelude helpers
   ========================================================================= *)

Fixpoint sum_nat (l : list nat) : nat :=
  match l with
  | nil => 0
  | cons x xs => Nat.add x (sum_nat xs)
  end.

Fixpoint has_unique_nats (l : list nat) : bool :=
  match l with
  | nil => true
  | cons x xs => andb (negb (PS.mem_nat x xs)) (has_unique_nats xs)
  end.

Definition subset_nats (sub sup : list nat) : bool :=
  PS.all_of (fun x => PS.mem_nat x sup) sub.

Fixpoint union_nats (a b : list nat) : list nat :=
  match a with
  | nil => b
  | cons x xs =>
      if PS.mem_nat x b then union_nats xs b else cons x (union_nats xs b)
  end.

Lemma mem_nat_union_l : forall x a b,
  PS.mem_nat x a = true -> PS.mem_nat x (union_nats a b) = true.
Proof.
  intros x a. induction a as [|y ys IH]; intros b H.
  - discriminate H.
  - unfold PS.mem_nat in H. simpl in H.
    destruct (Nat.eqb x y) eqn:Exy.
    + simpl. destruct (PS.mem_nat y b) eqn:Eyb.
      * rewrite (PS.nat_eqb_true x y Exy).
        clear IH H Exy. induction ys as [|z zs IHzs]; simpl.
        -- exact Eyb.
        -- destruct (PS.mem_nat z b); [exact IHzs | apply PS.mem_nat_cons; exact IHzs].
      * rewrite (PS.nat_eqb_true x y Exy). apply PS.mem_nat_here.
    + simpl. destruct (PS.mem_nat y b).
      * apply IH. exact H.
      * apply PS.mem_nat_cons. apply IH. exact H.
Qed.

Lemma mem_nat_union_r : forall x a b,
  PS.mem_nat x b = true -> PS.mem_nat x (union_nats a b) = true.
Proof.
  intros x a. induction a as [|y ys IH]; intros b H.
  - exact H.
  - simpl. destruct (PS.mem_nat y b).
    + exact (IH b H).
    + apply PS.mem_nat_cons. exact (IH b H).
Qed.

Lemma mem_nat_true_iff : forall x l,
  PS.mem_nat x l = true -> PS.Member x l.
Proof.
  intros x l H. unfold PS.mem_nat in H.
  apply (PS.any_eqb_member nat Nat.eqb PS.nat_eqb_true x l H).
Qed.

Lemma member_mem_nat : forall x l,
  PS.Member x l -> PS.mem_nat x l = true.
Proof.
  intros x l H. unfold PS.mem_nat.
  apply (PS.member_any_eqb nat Nat.eqb PS.nat_eqb_refl x l H).
Qed.

(* =========================================================================
   2. Sensor families, physical blocks, and topology specification
   ========================================================================= *)

Inductive SensorFamily : Type :=
| SupplyWindow
| ClockMonitor
| TimingReplica
| OpticalPhotocurrent.

Definition family_eqb (a b : SensorFamily) : bool :=
  match a, b with
  | SupplyWindow, SupplyWindow => true
  | ClockMonitor, ClockMonitor => true
  | TimingReplica, TimingReplica => true
  | OpticalPhotocurrent, OpticalPhotocurrent => true
  | _, _ => false
  end.

Lemma family_eqb_refl : forall f : SensorFamily, family_eqb f f = true.
Proof. intros [| | |]; reflexivity. Qed.

Lemma family_eqb_true : forall a b : SensorFamily, family_eqb a b = true -> a = b.
Proof. intros [| | |] [| | |] H; try discriminate H; reflexivity. Qed.

Inductive BlockClass : Type :=
| BlkRoT
| BlkSClass0
| BlkSClass1
| BlkCoreC
| BlkCoreV
| BlkCoreM.

Definition block_class_eqb (a b : BlockClass) : bool :=
  match a, b with
  | BlkRoT, BlkRoT => true
  | BlkSClass0, BlkSClass0 => true
  | BlkSClass1, BlkSClass1 => true
  | BlkCoreC, BlkCoreC => true
  | BlkCoreV, BlkCoreV => true
  | BlkCoreM, BlkCoreM => true
  | _, _ => false
  end.

Record RailSpec : Type := {
  rs_id : nat;
  rs_parent : option nat;
  rs_is_leaf : bool;
  rs_reaches_rot : bool;
  rs_sites : list nat;
  rs_islands : list nat
}.

Record ClockSpec : Type := {
  cs_id : nat;
  cs_parent : option nat;
  cs_is_leaf : bool;
  cs_is_rot_slow : bool;
  cs_reaches_rot : bool;
  cs_sites : list nat;
  cs_islands : list nat
}.

Record DatapathSpec : Type := {
  dp_id : nat;
  dp_class : BlockClass;
  dp_island : nat;
  dp_reaches_rot : bool
}.

Record LogicRegionSpec : Type := {
  lr_id : nat;
  lr_reaches_rot : bool;
  lr_islands : list nat;
  lr_declared_pitch_um : nat;
  lr_gap_free : bool;
  lr_occludes_backside : bool
}.

Record Topology : Type := {
  topo_has_rot : bool;
  topo_has_s0 : bool;
  topo_has_s1 : bool;
  topo_islands : list nat;
  topo_rails : list RailSpec;
  topo_clocks : list ClockSpec;
  topo_datapaths : list DatapathSpec;
  topo_regions : list LogicRegionSpec
}.

(* =========================================================================
   3. Sensor entries, immutable fields, and parameter inequalities
   ========================================================================= *)

Record SupplyParams : Type := {
  sp_vmin_uv : nat;
  sp_vmax_uv : nat;
  sp_hyst_uv : nat
}.

Record ClockParams : Type := {
  cp_period_min_ps : nat;
  cp_period_max_ps : nat;
  cp_high_min_ps : nat;
  cp_high_max_ps : nat;
  cp_low_min_ps : nat;
  cp_low_max_ps : nat;
  cp_duty_min_permille : nat;
  cp_duty_max_permille : nat;
  cp_missing_edge_max_ps : nat;
  cp_observer_clock : nat;
  cp_is_rot_slow : bool;
  cp_adaptive_ref : bool
}.

Record TimingParams : Type := {
  tp_slack_min_ps : nat;
  tp_correspondence_qualified : bool;
  tp_fixed_public_excitation : bool;
  tp_samples_operand : bool
}.

Record OpticalParams : Type := {
  op_photocurrent_trip_na : nat;
  op_dark_current_max_na : nat;
  op_site_pitch_um : nat;
  op_max_site_pitch_um : nat;
  op_occludes_backside : bool
}.

Record SensorEntry : Type := {
  se_id : nat;
  se_kind : SensorFamily;
  se_resource_id : nat;
  se_site_id : nat;
  se_affected_islands : list nat;
  se_rot_self_fault : bool;
  se_always_on : bool;
  se_enable_constant : bool;
  se_has_pending : bool;
  se_has_owner : bool;
  se_has_evidence_tuple : bool;
  se_retired_artifact : bool;
  se_sw_writable_threshold : bool;
  se_sw_writable_disable : bool;
  se_dynamic_calibration : bool;
  se_adds_isa_or_csr : bool;
  se_opp_table_bound : bool;
  se_ref_resource : nat;
  se_health_observer : nat;
  se_uses_only_guarded_liveness : bool;
  se_deps : list nat;
  se_supply : SupplyParams;
  se_clock : ClockParams;
  se_timing : TimingParams;
  se_optical : OpticalParams
}.

Definition supply_params_ok (sp : SupplyParams) : bool :=
  andb (Nat.ltb 0 sp.(sp_vmin_uv))
    (andb (Nat.ltb sp.(sp_vmin_uv) sp.(sp_vmax_uv))
      (andb (Nat.ltb 0 sp.(sp_hyst_uv))
            (Nat.ltb sp.(sp_hyst_uv) (Nat.sub sp.(sp_vmax_uv) sp.(sp_vmin_uv))))).

Definition clock_params_ok (cp : ClockParams) : bool :=
  andb (Nat.ltb 0 cp.(cp_period_min_ps))
    (andb (Nat.leb cp.(cp_period_min_ps) cp.(cp_period_max_ps))
      (andb (Nat.ltb 0 cp.(cp_high_min_ps))
        (andb (Nat.leb cp.(cp_high_min_ps) cp.(cp_high_max_ps))
          (andb (Nat.ltb 0 cp.(cp_low_min_ps))
            (andb (Nat.leb cp.(cp_low_min_ps) cp.(cp_low_max_ps))
              (andb (Nat.ltb cp.(cp_high_max_ps) cp.(cp_period_max_ps))
                (andb (Nat.ltb cp.(cp_low_max_ps) cp.(cp_period_max_ps))
                  (andb (Nat.leb (Nat.add cp.(cp_high_min_ps) cp.(cp_low_min_ps)) cp.(cp_period_max_ps))
                    (andb (Nat.leb cp.(cp_period_min_ps) (Nat.add cp.(cp_high_max_ps) cp.(cp_low_max_ps)))
                      (andb (Nat.ltb 0 cp.(cp_duty_min_permille))
                        (andb (Nat.leb cp.(cp_duty_min_permille) cp.(cp_duty_max_permille))
                          (andb (Nat.ltb cp.(cp_duty_max_permille) 1000)
                            (andb (Nat.leb (Nat.mul cp.(cp_duty_min_permille) cp.(cp_period_min_ps))
                                           (Nat.mul cp.(cp_high_max_ps) 1000))
                              (andb (Nat.leb (Nat.mul cp.(cp_high_min_ps) 1000)
                                             (Nat.mul cp.(cp_duty_max_permille) cp.(cp_period_max_ps)))
                                (andb (Nat.ltb 0 cp.(cp_missing_edge_max_ps))
                                  (andb (Nat.ltb 0 cp.(cp_observer_clock))
                                        (negb cp.(cp_adaptive_ref)))))))))))))))))).

Definition timing_params_ok (tp : TimingParams) : bool :=
  andb (Nat.ltb 0 tp.(tp_slack_min_ps))
    (andb tp.(tp_correspondence_qualified)
      (andb tp.(tp_fixed_public_excitation)
            (negb tp.(tp_samples_operand)))).

Definition optical_params_ok (op : OpticalParams) : bool :=
  andb (Nat.ltb 0 op.(op_photocurrent_trip_na))
    (andb (Nat.ltb op.(op_dark_current_max_na) op.(op_photocurrent_trip_na))
      (andb (Nat.ltb 0 op.(op_site_pitch_um))
        (andb (Nat.leb op.(op_site_pitch_um) op.(op_max_site_pitch_um))
              (negb op.(op_occludes_backside))))).

Definition family_params_ok (s : SensorEntry) : bool :=
  match s.(se_kind) with
  | SupplyWindow => supply_params_ok s.(se_supply)
  | ClockMonitor => clock_params_ok s.(se_clock)
  | TimingReplica => timing_params_ok s.(se_timing)
  | OpticalPhotocurrent => optical_params_ok s.(se_optical)
  end.

Definition sensor_immutable_ok (s : SensorEntry) : bool :=
  andb s.(se_enable_constant)
    (andb (negb s.(se_has_pending))
      (andb s.(se_has_owner)
        (andb s.(se_has_evidence_tuple)
          (andb (negb s.(se_retired_artifact))
            (andb (negb s.(se_sw_writable_threshold))
              (andb (negb s.(se_sw_writable_disable))
                (andb (negb s.(se_dynamic_calibration))
                  (andb (negb s.(se_adds_isa_or_csr))
                        (andb s.(se_opp_table_bound)
                              (family_params_ok s)))))))))).

(* =========================================================================
   4. Acyclic monitor dependency graph and anti-self-observation rules
   ========================================================================= *)

Fixpoint find_sensor (sid : nat) (sensors : list SensorEntry) : option SensorEntry :=
  match sensors with
  | nil => None
  | cons s rest => if Nat.eqb sid s.(se_id) then Some s else find_sensor sid rest
  end.

Definition deps_of_id (sid : nat) (sensors : list SensorEntry) : list nat :=
  match find_sensor sid sensors with
  | None => nil
  | Some s => s.(se_deps)
  end.

Fixpoint expand_frontier (sensors : list SensorEntry) (frontier : list nat) : list nat :=
  match frontier with
  | nil => nil
  | cons u rest => union_nats (deps_of_id u sensors) (expand_frontier sensors rest)
  end.

Fixpoint reachable_in (fuel : nat) (sensors : list SensorEntry) (visited frontier : list nat) : list nat :=
  match fuel with
  | 0 => visited
  | S k =>
      let next := expand_frontier sensors frontier in
      reachable_in k sensors (union_nats visited next) next
  end.

Definition has_cycle_from (sensors : list SensorEntry) (sid : nat) : bool :=
  let init := deps_of_id sid sensors in
  let reach := reachable_in (PS.count_of sensors) sensors init init in
  PS.mem_nat sid reach.

Definition no_dependency_cycles (sensors : list SensorEntry) : bool :=
  PS.all_of (fun s => negb (has_cycle_from sensors s.(se_id))) sensors.

Definition sensor_self_dep_free (inv_ids : list nat) (s : SensorEntry) : bool :=
  andb (subset_nats s.(se_deps) inv_ids)
    (andb (negb (Nat.eqb s.(se_health_observer) s.(se_id)))
      (andb (negb (Nat.eqb s.(se_ref_resource) s.(se_resource_id)))
        (andb (negb s.(se_uses_only_guarded_liveness))
              (match s.(se_kind) with
               | ClockMonitor =>
                   if s.(se_clock).(cp_is_rot_slow)
                   then negb (Nat.eqb s.(se_clock).(cp_observer_clock) s.(se_resource_id))
                   else true
               | _ => true
               end)))).

Definition dependency_graph_ok (sensors : list SensorEntry) : bool :=
  let ids := PS.map_over se_id sensors in
  andb (has_unique_nats ids)
    (andb (PS.all_of (sensor_self_dep_free ids) sensors)
          (no_dependency_cycles sensors)).

Lemma reachable_in_preserves_visited :
  forall fuel sensors visited frontier x,
    PS.mem_nat x visited = true ->
    PS.mem_nat x (reachable_in fuel sensors visited frontier) = true.
Proof.
  induction fuel as [|k IH]; intros sensors visited frontier x H.
  - exact H.
  - simpl. apply IH. apply mem_nat_union_l. exact H.
Qed.

Lemma find_sensor_unique_hit :
  forall s rest,
    has_unique_nats (PS.map_over se_id (cons s rest)) = true ->
    find_sensor s.(se_id) (cons s rest) = Some s.
Proof.
  intros s rest _. simpl. rewrite PS.nat_eqb_refl. reflexivity.
Qed.

Lemma mem_nat_expand_frontier :
  forall sensors u rest d,
    PS.mem_nat d (deps_of_id u sensors) = true ->
    PS.mem_nat d (expand_frontier sensors (cons u rest)) = true.
Proof.
  intros sensors u rest d H. simpl. apply mem_nat_union_l. exact H.
Qed.

Lemma member_map_over :
  forall (A B : Type) (f : A -> B) (x : A) (l : list A),
    PS.Member x l -> PS.Member (f x) (PS.map_over f l).
Proof.
  intros A B f x l H. induction l as [|y ys IH].
  - contradiction H.
  - destruct H as [Heq | Htail].
    + rewrite Heq. left. reflexivity.
    + right. exact (IH Htail).
Qed.

(*| discharges: R-15-196, R-16-008g |*)
Theorem self_loop_refused_by_dependency_check :
  forall s sensors,
    PS.Member s sensors ->
    has_unique_nats (PS.map_over se_id sensors) = true ->
    PS.mem_nat s.(se_id) s.(se_deps) = true ->
    dependency_graph_ok sensors = false.
Proof.
  intros s sensors Hin Huniq Hself.
  unfold dependency_graph_ok. rewrite Huniq. simpl.
  assert (Hfind : find_sensor s.(se_id) sensors = Some s).
  { induction sensors as [|x xs IH].
    - contradiction Hin.
    - simpl in Huniq. destruct (PS.andb_split _ _ Huniq) as [Hx Hxs].
      destruct Hin as [Heq | Hin'].
      + rewrite Heq. simpl. rewrite PS.nat_eqb_refl. reflexivity.
      + simpl. destruct (Nat.eqb s.(se_id) x.(se_id)) eqn:E.
        * exfalso.
          assert (Hid : s.(se_id) = x.(se_id)) by (apply PS.nat_eqb_true; exact E).
          assert (Hmem : PS.mem_nat x.(se_id) (PS.map_over se_id xs) = true).
          { apply member_mem_nat. rewrite <- Hid. apply member_map_over. exact Hin'. }
          destruct (negb (PS.mem_nat x.(se_id) (PS.map_over se_id xs))) eqn:En.
          -- rewrite Hmem in En. discriminate En.
          -- discriminate Hx.
        * exact (IH Hin' Hxs). }
  assert (Hcyc : has_cycle_from sensors s.(se_id) = true).
  { unfold has_cycle_from, deps_of_id. rewrite Hfind.
    apply reachable_in_preserves_visited. exact Hself. }
  assert (Hnocyc : no_dependency_cycles sensors = false).
  { unfold no_dependency_cycles.
    destruct (PS.all_of (fun z => negb (has_cycle_from sensors z.(se_id))) sensors) eqn:Eall.
    - pose proof (PS.all_of_member _ _ _ s Eall Hin) as Hneg.
      simpl in Hneg. rewrite Hcyc in Hneg. discriminate Hneg.
    - reflexivity. }
  rewrite Hnocyc. destruct (PS.all_of _ sensors); reflexivity.
Qed.

(*| discharges: R-15-196, R-16-008g |*)
Theorem rot_slow_clock_self_observation_refused :
  forall s sensors,
    PS.Member s sensors ->
    s.(se_kind) = ClockMonitor ->
    s.(se_clock).(cp_is_rot_slow) = true ->
    s.(se_clock).(cp_observer_clock) = s.(se_resource_id) ->
    dependency_graph_ok sensors = false.
Proof.
  intros s sensors Hin Hk Hslow Hobs.
  unfold dependency_graph_ok.
  destruct (has_unique_nats (PS.map_over se_id sensors)); [| reflexivity].
  simpl.
  destruct (PS.all_of (sensor_self_dep_free (PS.map_over se_id sensors)) sensors) eqn:Eall;
    [| reflexivity].
  exfalso.
  pose proof (PS.all_of_member _ _ _ s Eall Hin) as Hs.
  unfold sensor_self_dep_free in Hs.
  repeat match goal with
         | H : andb _ _ = true |- _ =>
             let H1 := fresh in let H2 := fresh in
             destruct (PS.andb_split _ _ H) as [H1 H2]; clear H
         end.
  rewrite Hk, Hslow, Hobs, PS.nat_eqb_refl in *.
  match goal with H : negb true = true |- _ => discriminate H end.
Qed.

(* =========================================================================
   5. Total topology coverage over P (RoT, S0, S1, C/V/M islands)
   ========================================================================= *)

Definition sensor_covers_rail_site (r : RailSpec) (site : nat) (s : SensorEntry) : bool :=
  andb (family_eqb s.(se_kind) SupplyWindow)
    (andb (Nat.eqb s.(se_resource_id) r.(rs_id))
      (andb (Nat.eqb s.(se_site_id) site)
        (andb (subset_nats r.(rs_islands) s.(se_affected_islands))
              (PS.only_if r.(rs_reaches_rot) s.(se_rot_self_fault))))).

Definition rail_covered (sensors : list SensorEntry) (r : RailSpec) : bool :=
  andb (negb (Nat.eqb (PS.count_of r.(rs_sites)) 0))
    (PS.all_of (fun site => PS.any_of (sensor_covers_rail_site r site) sensors) r.(rs_sites)).

Definition sensor_covers_clock_site (c : ClockSpec) (site : nat) (s : SensorEntry) : bool :=
  andb (family_eqb s.(se_kind) ClockMonitor)
    (andb (Nat.eqb s.(se_resource_id) c.(cs_id))
      (andb (Nat.eqb s.(se_site_id) site)
        (andb (subset_nats c.(cs_islands) s.(se_affected_islands))
          (andb (PS.only_if c.(cs_reaches_rot) s.(se_rot_self_fault))
                (PS.only_if c.(cs_is_rot_slow) s.(se_clock).(cp_is_rot_slow)))))).

Definition clock_covered (sensors : list SensorEntry) (c : ClockSpec) : bool :=
  andb (negb (Nat.eqb (PS.count_of c.(cs_sites)) 0))
    (PS.all_of (fun site => PS.any_of (sensor_covers_clock_site c site) sensors) c.(cs_sites)).

Definition sensor_covers_datapath (d : DatapathSpec) (s : SensorEntry) : bool :=
  andb (family_eqb s.(se_kind) TimingReplica)
    (andb (Nat.eqb s.(se_resource_id) d.(dp_id))
      (andb (PS.mem_nat d.(dp_island) s.(se_affected_islands))
            (PS.only_if d.(dp_reaches_rot) s.(se_rot_self_fault)))).

Definition datapath_covered (sensors : list SensorEntry) (d : DatapathSpec) : bool :=
  PS.any_of (sensor_covers_datapath d) sensors.

Definition sensor_covers_region (lr : LogicRegionSpec) (s : SensorEntry) : bool :=
  andb (family_eqb s.(se_kind) OpticalPhotocurrent)
    (andb (Nat.eqb s.(se_resource_id) lr.(lr_id))
      (andb (Nat.leb s.(se_optical).(op_site_pitch_um) lr.(lr_declared_pitch_um))
        (andb (subset_nats lr.(lr_islands) s.(se_affected_islands))
              (PS.only_if lr.(lr_reaches_rot) s.(se_rot_self_fault))))).

Definition region_covered (sensors : list SensorEntry) (lr : LogicRegionSpec) : bool :=
  andb lr.(lr_gap_free)
    (andb (negb lr.(lr_occludes_backside))
      (andb (Nat.ltb 0 lr.(lr_declared_pitch_um))
            (PS.any_of (sensor_covers_region lr) sensors))).

Definition datapath_has_class (cls : BlockClass) (dps : list DatapathSpec) : bool :=
  PS.any_of (fun d => block_class_eqb d.(dp_class) cls) dps.

Definition inventory_valid (t : Topology) (sensors : list SensorEntry) : bool :=
  andb t.(topo_has_rot)
    (andb t.(topo_has_s0)
      (andb t.(topo_has_s1)
        (andb (negb (Nat.eqb (PS.count_of t.(topo_rails)) 0))
          (andb (negb (Nat.eqb (PS.count_of t.(topo_clocks)) 0))
            (andb (negb (Nat.eqb (PS.count_of t.(topo_datapaths)) 0))
              (andb (negb (Nat.eqb (PS.count_of t.(topo_regions)) 0))
                (andb (datapath_has_class BlkRoT t.(topo_datapaths))
                  (andb (datapath_has_class BlkSClass0 t.(topo_datapaths))
                    (andb (datapath_has_class BlkSClass1 t.(topo_datapaths))
                      (andb (PS.all_of sensor_immutable_ok sensors)
                        (andb (dependency_graph_ok sensors)
                          (andb (PS.all_of (rail_covered sensors) t.(topo_rails))
                            (andb (PS.all_of (clock_covered sensors) t.(topo_clocks))
                              (andb (PS.all_of (datapath_covered sensors) t.(topo_datapaths))
                                    (PS.all_of (region_covered sensors) t.(topo_regions)))))))))))))))).

(*| discharges: R-16-008g |*)
Theorem empty_or_incomplete_topology_refused :
  forall t sensors,
    (t.(topo_has_rot) = false \/
     t.(topo_has_s0) = false \/
     t.(topo_has_s1) = false \/
     t.(topo_rails) = nil \/
     t.(topo_clocks) = nil \/
     t.(topo_datapaths) = nil \/
     t.(topo_regions) = nil) ->
    inventory_valid t sensors = false.
Proof.
  intros t sensors H. unfold inventory_valid.
  destruct H as [H | [H | [H | [H | [H | [H | H]]]]]]; rewrite H; simpl.
  - reflexivity.
  - destruct (topo_has_rot t); reflexivity.
  - destruct (topo_has_rot t), (topo_has_s0 t); reflexivity.
  - destruct (topo_has_rot t), (topo_has_s0 t), (topo_has_s1 t); reflexivity.
  - destruct (topo_has_rot t), (topo_has_s0 t), (topo_has_s1 t), (topo_rails t); reflexivity.
  - destruct (topo_has_rot t), (topo_has_s0 t), (topo_has_s1 t), (topo_rails t), (topo_clocks t); reflexivity.
  - destruct (topo_has_rot t), (topo_has_s0 t), (topo_has_s1 t), (topo_rails t), (topo_clocks t), (topo_datapaths t); reflexivity.
Qed.

(*| discharges: R-16-008g, R-15-195, R-15-196 |*)
Theorem valid_inventory_covers_every_member_and_is_immutable :
  forall t sensors,
    inventory_valid t sensors = true ->
    (forall r, PS.Member r t.(topo_rails) -> rail_covered sensors r = true) /\
    (forall c, PS.Member c t.(topo_clocks) -> clock_covered sensors c = true) /\
    (forall d, PS.Member d t.(topo_datapaths) -> datapath_covered sensors d = true) /\
    (forall lr, PS.Member lr t.(topo_regions) -> region_covered sensors lr = true) /\
    (forall s, PS.Member s sensors ->
      s.(se_has_pending) = false /\
      s.(se_sw_writable_threshold) = false /\
      s.(se_sw_writable_disable) = false /\
      s.(se_enable_constant) = true).
Proof.
  intros t sensors Hinv.
  unfold inventory_valid in Hinv.
  repeat match goal with
         | H : andb _ _ = true |- _ =>
             let H1 := fresh in let H2 := fresh in
             destruct (PS.andb_split _ _ H) as [H1 H2]; clear H
         end.
  split; [| split; [| split; [| split]]].
  - intros r Hr. eapply PS.all_of_member; eassumption.
  - intros c Hc. eapply PS.all_of_member; eassumption.
  - intros d Hd. eapply PS.all_of_member; eassumption.
  - intros lr Hlr. eapply PS.all_of_member; eassumption.
  - intros s0 Hs0.
    match goal with
    | Hall : PS.all_of sensor_immutable_ok sensors = true |- _ =>
        pose proof (PS.all_of_member _ _ _ s0 Hall Hs0) as Himm
    end.
    unfold sensor_immutable_ok in Himm.
    repeat match goal with
           | H : andb _ _ = true |- _ =>
               let H1 := fresh in let H2 := fresh in
               destruct (PS.andb_split _ _ H) as [H1 H2]; clear H
           end.
    repeat split.
    + destruct (se_has_pending s0); [discriminate | reflexivity].
    + destruct (se_sw_writable_threshold s0); [discriminate | reflexivity].
    + destruct (se_sw_writable_disable s0); [discriminate | reflexivity].
    + assumption.
Qed.

(* =========================================================================
   6. Runtime single fail-stop boundary, RoT bite, and attested events
   ========================================================================= *)

Inductive EnvironmentalTripClass : Type :=
| TripNone
| TripSupplyExcursion
| TripClockExcursion
| TripTimingMargin
| TripOpticalIllumination
| TripSensorFault
| TripUnexpectedDeactivation
| TripUnknownResetOrPowerLoss.

Record SensorSample : Type := {
  ss_sensor_id : nat;
  ss_disabled : bool;
  ss_corrupt_const : bool;
  ss_open_or_stuck : bool;
  ss_stopped_ref : bool;
  ss_broken_transducer : bool;
  ss_health_timeout : bool;
  ss_table_off_authorized : bool;
  ss_consumer_reset_isolated : bool;
  ss_physically_inactive : bool;
  ss_transition_overrun : bool;
  ss_voltage_uv : nat;
  ss_period_ps : nat;
  ss_high_ps : nat;
  ss_low_ps : nat;
  ss_edge_gap_ps : nat;
  ss_clock_stopped : bool;
  ss_slack_ps : nat;
  ss_photocurrent_na : nat;
  ss_sw_operand_val : nat
}.

Record EnvContext : Type := {
  ec_rot_cpu_alive : bool;
  ec_main_spine_clock_alive : bool;
  ec_firmware_mailbox_ready : bool;
  ec_sw_mask_requested : bool;
  ec_transport_ack_requested : bool
}.

Record AttestedEventRecord : Type := {
  aer_known_trip : bool;
  aer_trip_class : EnvironmentalTripClass;
  aer_recurrent_count : nat;
  aer_lost_interval : bool
}.

Record BoundaryState : Type := {
  bs_rot_latch : bool;
  bs_rot_watchdog_bite : bool;
  bs_reset_hold : bool;
  bs_frozen_islands : list nat;
  bs_last_trip : EnvironmentalTripClass;
  bs_pending_consume : bool;
  bs_lost_interval : bool;
  bs_recurrent_count : nat;
  bs_events : list AttestedEventRecord
}.

Record StepOutcome : Type := {
  so_state : BoundaryState;
  so_tripped : bool;
  so_class : EnvironmentalTripClass;
  so_rot_bite_asserted : bool
}.

Definition initial_boundary_state : BoundaryState :=
  {| bs_rot_latch := false;
     bs_rot_watchdog_bite := false;
     bs_reset_hold := false;
     bs_frozen_islands := nil;
     bs_last_trip := TripNone;
     bs_pending_consume := false;
     bs_lost_interval := false;
     bs_recurrent_count := 0;
     bs_events := nil |}.

Definition sensor_fault_injected (smp : SensorSample) : bool :=
  orb smp.(ss_disabled)
    (orb smp.(ss_corrupt_const)
      (orb smp.(ss_open_or_stuck)
        (orb smp.(ss_stopped_ref)
          (orb smp.(ss_broken_transducer) smp.(ss_health_timeout))))).

Definition family_excursion (s : SensorEntry) (smp : SensorSample) : option EnvironmentalTripClass :=
  match s.(se_kind) with
  | SupplyWindow =>
      if orb (Nat.ltb smp.(ss_voltage_uv) s.(se_supply).(sp_vmin_uv))
             (Nat.ltb s.(se_supply).(sp_vmax_uv) smp.(ss_voltage_uv))
      then Some TripSupplyExcursion else None
  | ClockMonitor =>
      if orb smp.(ss_clock_stopped)
          (orb (Nat.ltb smp.(ss_period_ps) s.(se_clock).(cp_period_min_ps))
            (orb (Nat.ltb s.(se_clock).(cp_period_max_ps) smp.(ss_period_ps))
              (orb (Nat.ltb smp.(ss_high_ps) s.(se_clock).(cp_high_min_ps))
                (orb (Nat.ltb s.(se_clock).(cp_high_max_ps) smp.(ss_high_ps))
                  (orb (Nat.ltb smp.(ss_low_ps) s.(se_clock).(cp_low_min_ps))
                    (orb (Nat.ltb s.(se_clock).(cp_low_max_ps) smp.(ss_low_ps))
                         (Nat.ltb s.(se_clock).(cp_missing_edge_max_ps) smp.(ss_edge_gap_ps))))))))
      then Some TripClockExcursion else None
  | TimingReplica =>
      if Nat.ltb smp.(ss_slack_ps) s.(se_timing).(tp_slack_min_ps)
      then Some TripTimingMargin else None
  | OpticalPhotocurrent =>
      if Nat.ltb s.(se_optical).(op_photocurrent_trip_na) smp.(ss_photocurrent_na)
      then Some TripOpticalIllumination else None
  end.

(* Physical stimulus evaluation ignores ss_sw_operand_val and ec_sw_mask_requested. *)
Definition evaluate_sensor_sample (s : SensorEntry) (smp : SensorSample) : EnvironmentalTripClass :=
  if sensor_fault_injected smp then TripSensorFault
  else if smp.(ss_transition_overrun) then TripUnexpectedDeactivation
  else if smp.(ss_physically_inactive) then
    if andb (negb s.(se_always_on))
            (andb smp.(ss_table_off_authorized) smp.(ss_consumer_reset_isolated))
    then TripNone
    else TripUnexpectedDeactivation
  else
    match family_excursion s smp with
    | Some tc => tc
    | None => TripNone
    end.

Definition trip_class_is_none (tc : EnvironmentalTripClass) : bool :=
  match tc with
  | TripNone => true
  | _ => false
  end.

Definition apply_sample_step
    (s : SensorEntry)
    (smp : SensorSample)
    (env : EnvContext)
    (st : BoundaryState) : StepOutcome :=
  let _unused_env := env in
  let tc := evaluate_sensor_sample s smp in
  if trip_class_is_none tc then
    {| so_state := st;
       so_tripped := false;
       so_class := TripNone;
       so_rot_bite_asserted := st.(bs_rot_watchdog_bite) |}
  else
    let bite := orb st.(bs_rot_watchdog_bite) s.(se_rot_self_fault) in
    let hold := orb st.(bs_reset_hold) bite in
    let frozen := if s.(se_rot_self_fault)
                  then st.(bs_frozen_islands)
                  else union_nats s.(se_affected_islands) st.(bs_frozen_islands) in
    let st' := {| bs_rot_latch := true;
                  bs_rot_watchdog_bite := bite;
                  bs_reset_hold := hold;
                  bs_frozen_islands := frozen;
                  bs_last_trip := tc;
                  bs_pending_consume := true;
                  bs_lost_interval := st.(bs_lost_interval);
                  bs_recurrent_count := st.(bs_recurrent_count);
                  bs_events := st.(bs_events) |} in
    {| so_state := st';
       so_tripped := true;
       so_class := tc;
       so_rot_bite_asserted := bite |}.

(* Transport acknowledgement cannot clear the RoT latch, watchdog bite, or frozen islands. *)
Definition acknowledge_transport (st : BoundaryState) : BoundaryState :=
  st.

(* Power loss forces reset hold and marks lost accounting interval; does not claim retained active latch. *)
Definition power_loss_event (st : BoundaryState) : BoundaryState :=
  {| bs_rot_latch := false;
     bs_rot_watchdog_bite := false;
     bs_reset_hold := true;
     bs_frozen_islands := st.(bs_frozen_islands);
     bs_last_trip := TripUnknownResetOrPowerLoss;
     bs_pending_consume := true;
     bs_lost_interval := true;
     bs_recurrent_count := st.(bs_recurrent_count);
     bs_events := st.(bs_events) |}.

(* Release after power loss requires healthy boundary AND reset-table recovery completion. *)
Definition recover_from_reset
    (st : BoundaryState)
    (boundary_healthy reset_table_done : bool) : BoundaryState :=
  if andb boundary_healthy (andb reset_table_done (negb st.(bs_rot_latch))) then
    {| bs_rot_latch := false;
       bs_rot_watchdog_bite := false;
       bs_reset_hold := false;
       bs_frozen_islands := nil;
       bs_last_trip := st.(bs_last_trip);
       bs_pending_consume := st.(bs_pending_consume);
       bs_lost_interval := st.(bs_lost_interval);
       bs_recurrent_count := st.(bs_recurrent_count);
       bs_events := st.(bs_events) |}
  else
    st.

Definition can_release_island
    (st : BoundaryState)
    (island_id : nat)
    (constants_ok enable_ok health_ok : bool) : bool :=
  andb (negb st.(bs_reset_hold))
    (andb (negb st.(bs_rot_watchdog_bite))
      (andb (negb (PS.mem_nat island_id st.(bs_frozen_islands)))
        (andb constants_ok (andb enable_ok health_ok)))).

(* M3 RoT firmware consumes the latch only after hardware stop/hold is asserted. *)
Definition firmware_consume_event (st : BoundaryState) : option BoundaryState :=
  let hw_stopped := orb st.(bs_rot_latch) (orb st.(bs_rot_watchdog_bite) st.(bs_reset_hold)) in
  if andb st.(bs_pending_consume) hw_stopped then
    let known := match st.(bs_last_trip) with
                 | TripUnknownResetOrPowerLoss => false
                 | TripNone => false
                 | _ => true
                 end in
    let cnt := S st.(bs_recurrent_count) in
    let rec := {| aer_known_trip := known;
                  aer_trip_class := st.(bs_last_trip);
                  aer_recurrent_count := cnt;
                  aer_lost_interval := st.(bs_lost_interval) |} in
    Some {| bs_rot_latch := st.(bs_rot_latch);
            bs_rot_watchdog_bite := st.(bs_rot_watchdog_bite);
            bs_reset_hold := st.(bs_reset_hold);
            bs_frozen_islands := st.(bs_frozen_islands);
            bs_last_trip := st.(bs_last_trip);
            bs_pending_consume := false;
            bs_lost_interval := false;
            bs_recurrent_count := cnt;
            bs_events := cons rec st.(bs_events) |}
  else
    None.

(* =========================================================================
   7. Key theorems on fail-stop boundary, independence, and telemetry hiding
   ========================================================================= *)

(*| discharges: R-16-008g |*)
Theorem island_trip_latches_rot_and_freezes_without_sw_or_ack :
  forall s smp env st isl,
    s.(se_rot_self_fault) = false ->
    PS.Member isl s.(se_affected_islands) ->
    trip_class_is_none (evaluate_sensor_sample s smp) = false ->
    let out := apply_sample_step s smp env st in
    let st_ack := acknowledge_transport out.(so_state) in
    out.(so_tripped) = true /\
    st_ack.(bs_rot_latch) = true /\
    PS.mem_nat isl st_ack.(bs_frozen_islands) = true /\
    forall c e h, can_release_island st_ack isl c e h = false.
Proof.
  intros s smp env st isl Hrot Hisl Htrip.
  unfold apply_sample_step. rewrite Htrip, Hrot.
  simpl.
  assert (Hmem : PS.mem_nat isl (union_nats s.(se_affected_islands) st.(bs_frozen_islands)) = true).
  { apply mem_nat_union_l. apply member_mem_nat. exact Hisl. }
  repeat split.
  - exact Hmem.
  - intros c e h. unfold can_release_island, acknowledge_transport. simpl.
    rewrite Hmem. simpl.
    destruct (bs_reset_hold st), (bs_rot_watchdog_bite st); simpl; reflexivity.
Qed.

(*| discharges: R-16-005, R-16-008g, R-15-196 |*)
Theorem rot_self_fault_bites_independently_of_cpu_clock_mailbox :
  forall s smp st,
    s.(se_rot_self_fault) = true ->
    trip_class_is_none (evaluate_sensor_sample s smp) = false ->
    let dead_env := {| ec_rot_cpu_alive := false;
                       ec_main_spine_clock_alive := false;
                       ec_firmware_mailbox_ready := false;
                       ec_sw_mask_requested := true;
                       ec_transport_ack_requested := true |} in
    let out := apply_sample_step s smp dead_env st in
    out.(so_rot_bite_asserted) = true /\
    out.(so_state).(bs_rot_watchdog_bite) = true /\
    out.(so_state).(bs_reset_hold) = true.
Proof.
  intros s smp st Hrot Htrip dead_env out.
  unfold out, apply_sample_step. rewrite Htrip, Hrot. simpl.
  destruct (bs_reset_hold st), (bs_rot_watchdog_bite st); repeat split; reflexivity.
Qed.

(*| discharges: R-16-008g |*)
Theorem disabling_or_corrupt_sensor_latches_failure :
  forall s smp env st,
    sensor_fault_injected smp = true ->
    let out := apply_sample_step s smp env st in
    out.(so_tripped) = true /\
    out.(so_class) = TripSensorFault /\
    out.(so_state).(bs_rot_latch) = true.
Proof.
  intros s smp env st Hflt.
  assert (Hev : evaluate_sensor_sample s smp = TripSensorFault).
  { unfold evaluate_sensor_sample. rewrite Hflt. reflexivity. }
  unfold apply_sample_step. rewrite Hev. simpl.
  repeat split; reflexivity.
Qed.

(*| discharges: R-15-198, R-16-008g |*)
Theorem unexpected_deactivation_trips_while_authorized_off_requires_reset_isolation :
  forall s smp,
    sensor_fault_injected smp = false ->
    smp.(ss_transition_overrun) = false ->
    smp.(ss_physically_inactive) = true ->
    (s.(se_always_on) = true \/
     smp.(ss_table_off_authorized) = false \/
     smp.(ss_consumer_reset_isolated) = false) ->
    evaluate_sensor_sample s smp = TripUnexpectedDeactivation.
Proof.
  intros s smp Hflt Hovr Hinact Hcond.
  unfold evaluate_sensor_sample. rewrite Hflt, Hovr, Hinact.
  destruct Hcond as [Haon | [Hauth | Hiso]].
  - rewrite Haon. reflexivity.
  - rewrite Hauth. destruct (negb (se_always_on s)); reflexivity.
  - rewrite Hiso. destruct (negb (se_always_on s)), (ss_table_off_authorized smp); reflexivity.
Qed.

(*| discharges: R-15-198, R-16-005, R-16-008g |*)
Theorem power_loss_holds_reset_until_healthy_and_reset_table_complete :
  forall st boundary_healthy reset_table_done isl c e h,
    let st_loss := power_loss_event st in
    st_loss.(bs_reset_hold) = true /\
    st_loss.(bs_lost_interval) = true /\
    st_loss.(bs_last_trip) = TripUnknownResetOrPowerLoss /\
    can_release_island st_loss isl c e h = false /\
    ((boundary_healthy = false \/ reset_table_done = false) ->
     can_release_island (recover_from_reset st_loss boundary_healthy reset_table_done) isl c e h = false).
Proof.
  intros st boundary_healthy reset_table_done isl c e h st_loss.
  split; [reflexivity | split; [reflexivity | split; [reflexivity | split; [reflexivity |]]]].
  intros [Hb | Hr].
  - unfold recover_from_reset, st_loss, power_loss_event. rewrite Hb.
    unfold can_release_island. reflexivity.
  - unfold recover_from_reset, st_loss, power_loss_event. rewrite Hr.
    destruct boundary_healthy; unfold can_release_island; reflexivity.
Qed.

(*| discharges: R-16-008g |*)
Theorem stimulus_independent_of_software_operands :
  forall s smp v1 v2,
    let smp1 := {| ss_sensor_id := smp.(ss_sensor_id);
                   ss_disabled := smp.(ss_disabled);
                   ss_corrupt_const := smp.(ss_corrupt_const);
                   ss_open_or_stuck := smp.(ss_open_or_stuck);
                   ss_stopped_ref := smp.(ss_stopped_ref);
                   ss_broken_transducer := smp.(ss_broken_transducer);
                   ss_health_timeout := smp.(ss_health_timeout);
                   ss_table_off_authorized := smp.(ss_table_off_authorized);
                   ss_consumer_reset_isolated := smp.(ss_consumer_reset_isolated);
                   ss_physically_inactive := smp.(ss_physically_inactive);
                   ss_transition_overrun := smp.(ss_transition_overrun);
                   ss_voltage_uv := smp.(ss_voltage_uv);
                   ss_period_ps := smp.(ss_period_ps);
                   ss_high_ps := smp.(ss_high_ps);
                   ss_low_ps := smp.(ss_low_ps);
                   ss_edge_gap_ps := smp.(ss_edge_gap_ps);
                   ss_clock_stopped := smp.(ss_clock_stopped);
                   ss_slack_ps := smp.(ss_slack_ps);
                   ss_photocurrent_na := smp.(ss_photocurrent_na);
                   ss_sw_operand_val := v1 |} in
    let smp2 := {| ss_sensor_id := smp.(ss_sensor_id);
                   ss_disabled := smp.(ss_disabled);
                   ss_corrupt_const := smp.(ss_corrupt_const);
                   ss_open_or_stuck := smp.(ss_open_or_stuck);
                   ss_stopped_ref := smp.(ss_stopped_ref);
                   ss_broken_transducer := smp.(ss_broken_transducer);
                   ss_health_timeout := smp.(ss_health_timeout);
                   ss_table_off_authorized := smp.(ss_table_off_authorized);
                   ss_consumer_reset_isolated := smp.(ss_consumer_reset_isolated);
                   ss_physically_inactive := smp.(ss_physically_inactive);
                   ss_transition_overrun := smp.(ss_transition_overrun);
                   ss_voltage_uv := smp.(ss_voltage_uv);
                   ss_period_ps := smp.(ss_period_ps);
                   ss_high_ps := smp.(ss_high_ps);
                   ss_low_ps := smp.(ss_low_ps);
                   ss_edge_gap_ps := smp.(ss_edge_gap_ps);
                   ss_clock_stopped := smp.(ss_clock_stopped);
                   ss_slack_ps := smp.(ss_slack_ps);
                   ss_photocurrent_na := smp.(ss_photocurrent_na);
                   ss_sw_operand_val := v2 |} in
    evaluate_sensor_sample s smp1 = evaluate_sensor_sample s smp2.
Proof.
  intros s smp v1 v2. unfold evaluate_sensor_sample, sensor_fault_injected, family_excursion.
  reflexivity.
Qed.

(*| discharges: R-17-030m, R-16-008g |*)
Theorem firmware_consume_requires_hw_stop_and_increments_rate :
  forall st st',
    firmware_consume_event st = Some st' ->
    orb st.(bs_rot_latch) (orb st.(bs_rot_watchdog_bite) st.(bs_reset_hold)) = true /\
    st'.(bs_recurrent_count) = S st.(bs_recurrent_count) /\
    st'.(bs_pending_consume) = false.
Proof.
  intros st st' H. unfold firmware_consume_event in H.
  destruct (orb (bs_rot_latch st) (orb (bs_rot_watchdog_bite st) (bs_reset_hold st))) eqn:Hhw;
    [| destruct (bs_pending_consume st); discriminate H].
  destruct (bs_pending_consume st) eqn:Hp; [| discriminate H].
  inversion H. repeat split; reflexivity.
Qed.

(* =========================================================================
   8. Concrete positive topology, in-band controls, and refutation witnesses
   ========================================================================= *)

(* Scaled canonical units in concrete witnesses (10mV, 100ps, ps-slack, nA/10)
   keep Peano nat evaluation fast while preserving all exact inequalities. *)
Definition default_supply : SupplyParams :=
  {| sp_vmin_uv := 75; sp_vmax_uv := 85; sp_hyst_uv := 2 |}.

Definition default_clock : ClockParams :=
  {| cp_period_min_ps := 9; cp_period_max_ps := 11;
     cp_high_min_ps := 4; cp_high_max_ps := 6;
     cp_low_min_ps := 4; cp_low_max_ps := 6;
     cp_duty_min_permille := 400; cp_duty_max_permille := 600;
     cp_missing_edge_max_ps := 15;
     cp_observer_clock := 20; cp_is_rot_slow := false; cp_adaptive_ref := false |}.

Definition rot_slow_clock_params : ClockParams :=
  {| cp_period_min_ps := 18; cp_period_max_ps := 22;
     cp_high_min_ps := 8; cp_high_max_ps := 12;
     cp_low_min_ps := 8; cp_low_max_ps := 12;
     cp_duty_min_permille := 400; cp_duty_max_permille := 600;
     cp_missing_edge_max_ps := 30;
     cp_observer_clock := 21; cp_is_rot_slow := true; cp_adaptive_ref := false |}.

Definition default_timing : TimingParams :=
  {| tp_slack_min_ps := 12; tp_correspondence_qualified := true;
     tp_fixed_public_excitation := true; tp_samples_operand := false |}.

Definition default_optical : OpticalParams :=
  {| op_photocurrent_trip_na := 50; op_dark_current_max_na := 4;
     op_site_pitch_um := 50; op_max_site_pitch_um := 60; op_occludes_backside := false |}.

Definition mk_sensor
    (sid : nat) (kind : SensorFamily) (res site : nat) (isls : list nat)
    (rot_self : bool) (always_on : bool) (ref_res obs : nat) (deps : list nat)
    (cp : ClockParams) : SensorEntry :=
  {| se_id := sid; se_kind := kind; se_resource_id := res; se_site_id := site;
     se_affected_islands := isls; se_rot_self_fault := rot_self;
     se_always_on := always_on; se_enable_constant := true;
     se_has_pending := false; se_has_owner := true;
     se_has_evidence_tuple := true; se_retired_artifact := false;
     se_sw_writable_threshold := false; se_sw_writable_disable := false;
     se_dynamic_calibration := false; se_adds_isa_or_csr := false;
     se_opp_table_bound := true;
     se_ref_resource := ref_res; se_health_observer := obs;
     se_uses_only_guarded_liveness := false; se_deps := deps;
     se_supply := default_supply; se_clock := cp;
     se_timing := default_timing; se_optical := default_optical |}.

(* Positive composed topology: RoT (island 0), S0/S1 (island 1), C (2), V (3), M (4). *)
Definition demo_topology : Topology :=
  {| topo_has_rot := true;
     topo_has_s0 := true;
     topo_has_s1 := true;
     topo_islands := cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil))));
     topo_rails :=
       cons {| rs_id := 10; rs_parent := None; rs_is_leaf := false;
               rs_reaches_rot := true; rs_sites := cons 100 nil;
               rs_islands := cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil)))) |}
         (cons {| rs_id := 11; rs_parent := Some 10; rs_is_leaf := true;
                  rs_reaches_rot := false; rs_sites := cons 101 nil;
                  rs_islands := cons 2 nil |} nil);
     topo_clocks :=
       cons {| cs_id := 20; cs_parent := None; cs_is_leaf := false;
               cs_is_rot_slow := true; cs_reaches_rot := true;
               cs_sites := cons 200 nil; cs_islands := cons 0 nil |}
         (cons {| cs_id := 21; cs_parent := None; cs_is_leaf := false;
                  cs_is_rot_slow := false; cs_reaches_rot := true;
                  cs_sites := cons 201 nil;
                  cs_islands := cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil)))) |}
           (cons {| cs_id := 22; cs_parent := Some 21; cs_is_leaf := true;
                    cs_is_rot_slow := false; cs_reaches_rot := false;
                    cs_sites := cons 202 nil; cs_islands := cons 2 nil |} nil));
     topo_datapaths :=
       cons {| dp_id := 30; dp_class := BlkRoT; dp_island := 0; dp_reaches_rot := true |}
         (cons {| dp_id := 31; dp_class := BlkSClass0; dp_island := 1; dp_reaches_rot := false |}
           (cons {| dp_id := 32; dp_class := BlkSClass1; dp_island := 1; dp_reaches_rot := false |}
             (cons {| dp_id := 33; dp_class := BlkCoreC; dp_island := 2; dp_reaches_rot := false |}
               (cons {| dp_id := 34; dp_class := BlkCoreV; dp_island := 3; dp_reaches_rot := false |}
                 (cons {| dp_id := 35; dp_class := BlkCoreM; dp_island := 4; dp_reaches_rot := false |} nil)))));
     topo_regions :=
       cons {| lr_id := 40; lr_reaches_rot := true; lr_islands := cons 0 nil;
               lr_declared_pitch_um := 60; lr_gap_free := true; lr_occludes_backside := false |}
         (cons {| lr_id := 41; lr_reaches_rot := false;
                  lr_islands := cons 1 (cons 2 (cons 3 (cons 4 nil)));
                  lr_declared_pitch_um := 60; lr_gap_free := true; lr_occludes_backside := false |} nil) |}.

Definition demo_sensors : list SensorEntry :=
  cons (mk_sensor 1 SupplyWindow 10 100 (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil))))) true true 900 901 nil default_clock)
    (cons (mk_sensor 2 SupplyWindow 11 101 (cons 2 nil) false false 900 1 (cons 1 nil) default_clock)
      (cons (mk_sensor 3 ClockMonitor 20 200 (cons 0 nil) true true 902 1 (cons 1 nil) rot_slow_clock_params)
        (cons (mk_sensor 4 ClockMonitor 21 201 (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil))))) true true 902 1 (cons 1 nil) default_clock)
          (cons (mk_sensor 5 ClockMonitor 22 202 (cons 2 nil) false false 902 4 (cons 4 nil) default_clock)
            (cons (mk_sensor 6 TimingReplica 30 300 (cons 0 nil) true true 903 1 (cons 1 nil) default_clock)
              (cons (mk_sensor 7 TimingReplica 31 301 (cons 1 nil) false false 903 1 (cons 1 nil) default_clock)
                (cons (mk_sensor 8 TimingReplica 32 302 (cons 1 nil) false false 903 1 (cons 1 nil) default_clock)
                  (cons (mk_sensor 9 TimingReplica 33 303 (cons 2 nil) false false 903 2 (cons 2 nil) default_clock)
                    (cons (mk_sensor 10 TimingReplica 34 304 (cons 3 nil) false false 903 1 (cons 1 nil) default_clock)
                      (cons (mk_sensor 11 TimingReplica 35 305 (cons 4 nil) false false 903 1 (cons 1 nil) default_clock)
                        (cons (mk_sensor 12 OpticalPhotocurrent 40 400 (cons 0 nil) true true 904 1 (cons 1 nil) default_clock)
                          (cons (mk_sensor 13 OpticalPhotocurrent 41 401 (cons 1 (cons 2 (cons 3 (cons 4 nil)))) false true 904 1 (cons 1 nil) default_clock) nil)))))))))))).

Definition inband_sample (sid : nat) : SensorSample :=
  {| ss_sensor_id := sid;
     ss_disabled := false; ss_corrupt_const := false; ss_open_or_stuck := false;
     ss_stopped_ref := false; ss_broken_transducer := false; ss_health_timeout := false;
     ss_table_off_authorized := false; ss_consumer_reset_isolated := false;
     ss_physically_inactive := false; ss_transition_overrun := false;
     ss_voltage_uv := 76; ss_period_ps := 10; ss_high_ps := 5; ss_low_ps := 5;
     ss_edge_gap_ps := 11; ss_clock_stopped := false;
     ss_slack_ps := 13; ss_photocurrent_na := 42; ss_sw_operand_val := 0 |}.

Definition sample_supply_droop : SensorSample :=
  {| ss_sensor_id := 2;
     ss_disabled := false; ss_corrupt_const := false; ss_open_or_stuck := false;
     ss_stopped_ref := false; ss_broken_transducer := false; ss_health_timeout := false;
     ss_table_off_authorized := false; ss_consumer_reset_isolated := false;
     ss_physically_inactive := false; ss_transition_overrun := false;
     ss_voltage_uv := 70; ss_period_ps := 10; ss_high_ps := 5; ss_low_ps := 5;
     ss_edge_gap_ps := 10; ss_clock_stopped := false;
     ss_slack_ps := 20; ss_photocurrent_na := 5; ss_sw_operand_val := 99 |}.

Definition sample_rot_slow_stopped : SensorSample :=
  {| ss_sensor_id := 3;
     ss_disabled := false; ss_corrupt_const := false; ss_open_or_stuck := false;
     ss_stopped_ref := false; ss_broken_transducer := false; ss_health_timeout := false;
     ss_table_off_authorized := false; ss_consumer_reset_isolated := false;
     ss_physically_inactive := false; ss_transition_overrun := false;
     ss_voltage_uv := 80; ss_period_ps := 20; ss_high_ps := 10; ss_low_ps := 10;
     ss_edge_gap_ps := 40; ss_clock_stopped := true;
     ss_slack_ps := 20; ss_photocurrent_na := 5; ss_sw_operand_val := 1 |}.

Definition sample_legal_off : SensorSample :=
  {| ss_sensor_id := 9;
     ss_disabled := false; ss_corrupt_const := false; ss_open_or_stuck := false;
     ss_stopped_ref := false; ss_broken_transducer := false; ss_health_timeout := false;
     ss_table_off_authorized := true; ss_consumer_reset_isolated := true;
     ss_physically_inactive := true; ss_transition_overrun := false;
     ss_voltage_uv := 80; ss_period_ps := 10; ss_high_ps := 5; ss_low_ps := 5;
     ss_edge_gap_ps := 10; ss_clock_stopped := false;
     ss_slack_ps := 20; ss_photocurrent_na := 5; ss_sw_operand_val := 0 |}.

Definition sample_illegal_off : SensorSample :=
  {| ss_sensor_id := 9;
     ss_disabled := false; ss_corrupt_const := false; ss_open_or_stuck := false;
     ss_stopped_ref := false; ss_broken_transducer := false; ss_health_timeout := false;
     ss_table_off_authorized := true; ss_consumer_reset_isolated := false;
     ss_physically_inactive := true; ss_transition_overrun := false;
     ss_voltage_uv := 80; ss_period_ps := 10; ss_high_ps := 5; ss_low_ps := 5;
     ss_edge_gap_ps := 10; ss_clock_stopped := false;
     ss_slack_ps := 20; ss_photocurrent_na := 5; ss_sw_operand_val := 0 |}.

Definition sample_disabled_fault : SensorSample :=
  {| ss_sensor_id := 13;
     ss_disabled := true; ss_corrupt_const := false; ss_open_or_stuck := false;
     ss_stopped_ref := false; ss_broken_transducer := false; ss_health_timeout := false;
     ss_table_off_authorized := false; ss_consumer_reset_isolated := false;
     ss_physically_inactive := false; ss_transition_overrun := false;
     ss_voltage_uv := 80; ss_period_ps := 10; ss_high_ps := 5; ss_low_ps := 5;
     ss_edge_gap_ps := 10; ss_clock_stopped := false;
     ss_slack_ps := 20; ss_photocurrent_na := 5; ss_sw_operand_val := 0 |}.

Definition demo_live_env : EnvContext :=
  {| ec_rot_cpu_alive := true; ec_main_spine_clock_alive := true;
     ec_firmware_mailbox_ready := true; ec_sw_mask_requested := false;
     ec_transport_ack_requested := false |}.

Definition demo_dead_env : EnvContext :=
  {| ec_rot_cpu_alive := false; ec_main_spine_clock_alive := false;
     ec_firmware_mailbox_ready := false; ec_sw_mask_requested := true;
     ec_transport_ack_requested := true |}.

(*| discharges: R-15-195, R-15-196, R-15-198, R-16-005, R-16-008g, R-17-030m |*)
Example positive_composed_topology_and_boundary_controls :
  inventory_valid demo_topology demo_sensors = true /\
  evaluate_sensor_sample (mk_sensor 2 SupplyWindow 11 101 (cons 2 nil) false false 900 1 (cons 1 nil) default_clock)
                         (inband_sample 2) = TripNone /\
  evaluate_sensor_sample (mk_sensor 9 TimingReplica 33 303 (cons 2 nil) false false 903 2 (cons 2 nil) default_clock)
                         sample_legal_off = TripNone /\
  let island_out := apply_sample_step
                      (mk_sensor 2 SupplyWindow 11 101 (cons 2 nil) false false 900 1 (cons 1 nil) default_clock)
                      sample_supply_droop demo_live_env initial_boundary_state in
  let rot_out := apply_sample_step
                   (mk_sensor 3 ClockMonitor 20 200 (cons 0 nil) true true 902 1 (cons 1 nil) rot_slow_clock_params)
                   sample_rot_slow_stopped demo_dead_env initial_boundary_state in
  island_out.(so_tripped) = true /\
  island_out.(so_rot_bite_asserted) = false /\
  can_release_island (acknowledge_transport island_out.(so_state)) 2 true true true = false /\
  rot_out.(so_rot_bite_asserted) = true /\
  rot_out.(so_state).(bs_reset_hold) = true /\
  match firmware_consume_event island_out.(so_state) with
  | Some st1 => andb (Nat.eqb st1.(bs_recurrent_count) 1) (negb st1.(bs_pending_consume))
  | None => false
  end = true.
Proof. repeat split; reflexivity. Qed.

(* Negative refutation topologies & configurations. *)
Definition topo_missing_s1 : Topology :=
  {| topo_has_rot := true; topo_has_s0 := true; topo_has_s1 := false;
     topo_islands := demo_topology.(topo_islands);
     topo_rails := demo_topology.(topo_rails);
     topo_clocks := demo_topology.(topo_clocks);
     topo_datapaths := demo_topology.(topo_datapaths);
     topo_regions := demo_topology.(topo_regions) |}.

Definition sensor_with_pending : SensorEntry :=
  {| se_id := 1; se_kind := SupplyWindow; se_resource_id := 10; se_site_id := 100;
     se_affected_islands := cons 0 nil; se_rot_self_fault := true; se_always_on := true;
     se_enable_constant := true; se_has_pending := true; se_has_owner := true;
     se_has_evidence_tuple := true; se_retired_artifact := false;
     se_sw_writable_threshold := false; se_sw_writable_disable := false;
     se_dynamic_calibration := false; se_adds_isa_or_csr := false;
     se_opp_table_bound := true; se_ref_resource := 900; se_health_observer := 901;
     se_uses_only_guarded_liveness := false; se_deps := nil;
     se_supply := default_supply; se_clock := default_clock;
     se_timing := default_timing; se_optical := default_optical |}.

Definition sensor_sw_threshold : SensorEntry :=
  {| se_id := 1; se_kind := SupplyWindow; se_resource_id := 10; se_site_id := 100;
     se_affected_islands := cons 0 nil; se_rot_self_fault := true; se_always_on := true;
     se_enable_constant := true; se_has_pending := false; se_has_owner := true;
     se_has_evidence_tuple := true; se_retired_artifact := false;
     se_sw_writable_threshold := true; se_sw_writable_disable := false;
     se_dynamic_calibration := false; se_adds_isa_or_csr := false;
     se_opp_table_bound := true; se_ref_resource := 900; se_health_observer := 901;
     se_uses_only_guarded_liveness := false; se_deps := nil;
     se_supply := default_supply; se_clock := default_clock;
     se_timing := default_timing; se_optical := default_optical |}.

Definition sensor_slow_self_obs : SensorEntry :=
  mk_sensor 3 ClockMonitor 20 200 (cons 0 nil) true true 902 1 nil
    {| cp_period_min_ps := 18; cp_period_max_ps := 22;
       cp_high_min_ps := 8; cp_high_max_ps := 12;
       cp_low_min_ps := 8; cp_low_max_ps := 12;
       cp_duty_min_permille := 400; cp_duty_max_permille := 600;
       cp_missing_edge_max_ps := 30;
       cp_observer_clock := 20; cp_is_rot_slow := true; cp_adaptive_ref := false |}.

Definition cycle_sensors : list SensorEntry :=
  cons (mk_sensor 1 SupplyWindow 10 100 (cons 0 nil) true true 900 2 (cons 2 nil) default_clock)
    (cons (mk_sensor 2 SupplyWindow 11 101 (cons 2 nil) false false 901 1 (cons 1 nil) default_clock) nil).

Definition bad_clock_duty : ClockParams :=
  {| cp_period_min_ps := 10; cp_period_max_ps := 11;
     cp_high_min_ps := 4; cp_high_max_ps := 5;
     cp_low_min_ps := 4; cp_low_max_ps := 5;
     cp_duty_min_permille := 800; cp_duty_max_permille := 900;
     cp_missing_edge_max_ps := 15;
     cp_observer_clock := 21; cp_is_rot_slow := false; cp_adaptive_ref := false |}.

Definition bad_optical_occlusion : OpticalParams :=
  {| op_photocurrent_trip_na := 50; op_dark_current_max_na := 4;
     op_site_pitch_um := 50; op_max_site_pitch_um := 60; op_occludes_backside := true |}.

(*| discharges: R-15-196, R-15-198, R-16-008g |*)
Example negative_refutations_all_rejected :
  inventory_valid topo_missing_s1 demo_sensors = false /\
  sensor_immutable_ok sensor_with_pending = false /\
  sensor_immutable_ok sensor_sw_threshold = false /\
  dependency_graph_ok (cons sensor_slow_self_obs nil) = false /\
  dependency_graph_ok cycle_sensors = false /\
  clock_params_ok bad_clock_duty = false /\
  optical_params_ok bad_optical_occlusion = false /\
  evaluate_sensor_sample
    (mk_sensor 9 TimingReplica 33 303 (cons 2 nil) false false 903 2 (cons 2 nil) default_clock)
    sample_illegal_off = TripUnexpectedDeactivation /\
  evaluate_sensor_sample
    (mk_sensor 13 OpticalPhotocurrent 41 401 (cons 1 nil) false true 904 1 (cons 1 nil) default_clock)
    sample_disabled_fault = TripSensorFault.
Proof. repeat split; reflexivity. Qed.

(* =========================================================================
   9. R-05-166 inhabitation witnesses (one closed Definition per Record)
   ========================================================================= *)

Definition witness_RailSpec : RailSpec :=
  {| rs_id := 10; rs_parent := None; rs_is_leaf := false;
     rs_reaches_rot := true; rs_sites := cons 100 nil; rs_islands := cons 0 nil |}.

Definition witness_ClockSpec : ClockSpec :=
  {| cs_id := 20; cs_parent := None; cs_is_leaf := false;
     cs_is_rot_slow := true; cs_reaches_rot := true;
     cs_sites := cons 200 nil; cs_islands := cons 0 nil |}.

Definition witness_DatapathSpec : DatapathSpec :=
  {| dp_id := 30; dp_class := BlkRoT; dp_island := 0; dp_reaches_rot := true |}.

Definition witness_LogicRegionSpec : LogicRegionSpec :=
  {| lr_id := 40; lr_reaches_rot := true; lr_islands := cons 0 nil;
     lr_declared_pitch_um := 60; lr_gap_free := true; lr_occludes_backside := false |}.

Definition witness_Topology : Topology := demo_topology.
Definition witness_SupplyParams : SupplyParams := default_supply.
Definition witness_ClockParams : ClockParams := default_clock.
Definition witness_TimingParams : TimingParams := default_timing.
Definition witness_OpticalParams : OpticalParams := default_optical.

Definition witness_SensorEntry : SensorEntry :=
  mk_sensor 1 SupplyWindow 10 100 (cons 0 nil) true true 900 901 nil default_clock.

Definition witness_SensorSample : SensorSample := inband_sample 1.
Definition witness_EnvContext : EnvContext := demo_live_env.

Definition witness_AttestedEventRecord : AttestedEventRecord :=
  {| aer_known_trip := true; aer_trip_class := TripSupplyExcursion;
     aer_recurrent_count := 1; aer_lost_interval := false |}.

Definition witness_BoundaryState : BoundaryState := initial_boundary_state.

Definition witness_StepOutcome : StepOutcome :=
  apply_sample_step witness_SensorEntry witness_SensorSample witness_EnvContext initial_boundary_state.

(* R-05-163, R-05-164, R-05-165, R-05-166: zero axioms, prelude + ProofSupport,
   every Record inhabited, positive & negative controls discharged. *)
