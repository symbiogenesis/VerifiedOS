(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ElasticDispatch.v

   Kernel elastic-dispatch specification and universal cooperative EEVDF
   share-bound proof extending [PartitionContext.v](PartitionContext.v),
   [CyclicExecutive.v](CyclicExecutive.v), [EndpointIPC.v](EndpointIPC.v),
   and [ElasticDomain.v](ElasticDomain.v):

   - Invocation (iii) tentative-yield ABI extension with no sixth ABI entry,
     no named-successor invocation, and no kernel vector-save path, plus the
     repeated-tentative backstop (R-07-031b, R-07-014a).
   - Partition-context-only EEVDF state and session-manager request cell
     (`Launch | Close | Focus`) inside placed partition contexts with zero new
     kernel tables or object classes (R-07-027a, R-07-037i).
   - Intra-slot step extending [PartitionContext.v](PartitionContext.v#Rotation)
     with inter-application `vmclear` and R-07-037c's pending swap, while
     preserving static-schedule `vmclear` elision only when the outgoing
     partition slot's manifest fixes `mstatus.VS`/`XS = Off`
     (R-07-014, R-07-014c, R-07-037b, R-07-037c, R-07-037d, R-07-037g).
   - Cooperative boundary rule (`NeverCuts`) and label-internal
     non-interference unwinding (R-07-032, R-07-037e, R-07-037g, R-07-037h).
   - Universal cooperative EEVDF share-bound theorem over served time
     (`eff_coop_request = eff_request + call_bound + yield_bound`), zero-sum
     accounting lag invariant, work conservation (`zero_sum_implies_eligible_exists`),
     instant lag bound (`|accounting_lag| <= sink_inclusive_lag_bound`), and
     interval shortfall bound (`<= 2 * sink_inclusive_lag_bound`)
     (R-07-037g, R-11-006c, R-17-007b).
   - Constructive inhabitation witnesses (`witness_<Record>`) and refutations
     for leaky dispatch, missing boundary rule, vector saving, missing
     `vmclear`, and omitted cooperative deadline padding
     (R-05-163, R-05-165, R-05-166).
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-07-014 R-07-014a R-07-014c R-07-027a
      R-07-031b R-07-032 R-07-037b R-07-037c R-07-037d R-07-037e R-07-037g R-07-037h R-07-037i
      R-11-006c R-17-007b
   SHA256: 12e69a3dca3704e2ee043796cd7aa6f7811200393d1d1e9a71910b384df5f45a
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia QArith Qabs Lqa.
Require Import ProofSupport.
Require Import EndpointIPC.
Require Import PartitionContext.
Require Import CyclicExecutive.
Require Import MemoryPlan.
Require Import ElasticDomain.

Local Open Scope nat_scope.

(* =========================================================================
   S1. Rational and summation helpers.
   ========================================================================= *)

Lemma qn_pos : forall n : nat, 1 <= n -> (0 < qn n)%Q.
Proof.
  intros n H. unfold qn, Qlt. simpl. lia.
Qed.

Lemma qn_nonzero : forall n : nat, 1 <= n -> ~ (qn n == 0)%Q.
Proof.
  intros n H Heq. pose proof (qn_pos n H) as Hlt. lra.
Qed.

Lemma qn_add : forall a b : nat, (qn (a + b) == qn a + qn b)%Q.
Proof.
  intros a b. unfold qn, Qeq. simpl. lia.
Qed.

Lemma qn_le : forall a b : nat, a <= b -> (qn a <= qn b)%Q.
Proof.
  intros a b H. unfold qn, Qle. simpl. lia.
Qed.

Lemma qn_nonneg : forall n : nat, (0 <= qn n)%Q.
Proof.
  intros n. unfold qn, Qle. simpl. lia.
Qed.

Lemma qmult_pos_neg : forall a b : Q, (0 < a)%Q -> (b < 0)%Q -> (a * b < 0)%Q.
Proof.
  intros a b Ha Hb.
  assert (Hpos : (0 < a * (- b))%Q) by (apply Qmult_lt_0_compat; lra).
  assert (Heq : (a * b == - (a * (- b)))%Q) by ring.
  lra.
Qed.

Fixpoint sum_Q (f : nat -> Q) (l : list nat) : Q :=
  match l with
  | nil => 0%Q
  | cons x r => Qplus (f x) (sum_Q f r)
  end.

Lemma sum_Q_ext : forall f g l,
  (forall x, In x l -> (f x == g x)%Q) ->
  (sum_Q f l == sum_Q g l)%Q.
Proof.
  intros f g l. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl. rewrite (H x (or_introl eq_refl)).
    rewrite IH; [ reflexivity | ].
    intros y Hy. exact (H y (or_intror Hy)).
Qed.

Lemma sum_Q_app : forall f l1 l2,
  (sum_Q f (l1 ++ l2) == sum_Q f l1 + sum_Q f l2)%Q.
Proof.
  intros f l1 l2. induction l1 as [ | x r IH ].
  - simpl. lra.
  - simpl. rewrite IH. lra.
Qed.

Lemma sum_Q_add : forall f g l,
  (sum_Q (fun x => (f x + g x)%Q) l == sum_Q f l + sum_Q g l)%Q.
Proof.
  intros f g l. induction l as [ | x r IH ].
  - simpl. lra.
  - simpl. rewrite IH. lra.
Qed.

Lemma sum_Q_scale : forall c f l,
  (sum_Q (fun x => (c * f x)%Q) l == c * sum_Q f l)%Q.
Proof.
  intros c f l. induction l as [ | x r IH ].
  - simpl. lra.
  - simpl. rewrite IH. ring.
Qed.

Lemma sum_Q_zero : forall f l,
  (forall x, In x l -> (f x == 0)%Q) ->
  (sum_Q f l == 0)%Q.
Proof.
  intros f l. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl. rewrite (H x (or_introl eq_refl)), IH; [ lra | ].
    intros y Hy. exact (H y (or_intror Hy)).
Qed.

Lemma sum_Q_le : forall f g l,
  (forall x, In x l -> (f x <= g x)%Q) ->
  (sum_Q f l <= sum_Q g l)%Q.
Proof.
  intros f g l. induction l as [ | x r IH ]; intros H.
  - simpl. lra.
  - simpl.
    pose proof (H x (or_introl eq_refl)) as Hx.
    assert (Hr : (sum_Q f r <= sum_Q g r)%Q).
    { apply IH. intros y Hy. exact (H y (or_intror Hy)). }
    lra.
Qed.

Lemma sum_Q_nonneg : forall f l,
  (forall x, In x l -> (0 <= f x)%Q) ->
  (0 <= sum_Q f l)%Q.
Proof.
  intros f l H.
  assert (Hz : (sum_Q (fun _ => 0%Q) l == 0)%Q).
  { apply sum_Q_zero. intros _ _. reflexivity. }
  rewrite <- Hz. apply sum_Q_le. exact H.
Qed.

Lemma sum_Q_nonneg_member_le : forall f l k,
  (forall x, In x l -> (0 <= f x)%Q) ->
  In k l ->
  (f k <= sum_Q f l)%Q.
Proof.
  intros f l k Hpos Hin. induction l as [ | x r IH ].
  - destruct Hin.
  - simpl in *. destruct Hin as [ Heq | Hin ].
    + subst x.
      assert (Hr : (0 <= sum_Q f r)%Q).
      { apply sum_Q_nonneg. intros y Hy. exact (Hpos y (or_intror Hy)). }
      lra.
    + pose proof (Hpos x (or_introl eq_refl)) as Hx.
      assert (Hk : (f k <= sum_Q f r)%Q).
      { apply IH; [ | exact Hin ]. intros y Hy. exact (Hpos y (or_intror Hy)). }
      lra.
Qed.

Lemma sum_Q_nonneg_zero : forall f l,
  (forall x, In x l -> (0 <= f x)%Q) ->
  (sum_Q f l == 0)%Q ->
  forall x, In x l -> (f x == 0)%Q.
Proof.
  intros f l Hpos Hsum x Hin.
  pose proof (Hpos x Hin) as Hge.
  pose proof (sum_Q_nonneg_member_le f l x Hpos Hin) as Hle.
  lra.
Qed.

Lemma sum_Q_nonpos_lt : forall f l k,
  (forall x, In x l -> (f x <= 0)%Q) ->
  In k l ->
  (f k < 0)%Q ->
  (sum_Q f l < 0)%Q.
Proof.
  intros f l k Hle Hin Hlt. induction l as [ | x r IH ].
  - destruct Hin.
  - simpl in *. destruct Hin as [ Heq | Hin ].
    + subst x.
      assert (Hr : (sum_Q f r <= 0)%Q).
      { rewrite <- (sum_Q_zero (fun _ => 0%Q) r (fun _ _ => Qeq_refl _)).
        apply sum_Q_le. intros y Hy. exact (Hle y (or_intror Hy)). }
      lra.
    + pose proof (Hle x (or_introl eq_refl)) as Hx.
      assert (Hr : (sum_Q f r < 0)%Q).
      { apply IH; [ | exact Hin ]. intros y Hy. exact (Hle y (or_intror Hy)). }
      lra.
Qed.

Lemma sum_Q_replace_one : forall f l k (v : Q),
  NoDup l -> In k l ->
  (sum_Q (fun j => if Nat.eqb j k then v else f j) l ==
   sum_Q f l - f k + v)%Q.
Proof.
  intros f l k v Hnd Hin. induction l as [ | x r IH ].
  - destruct Hin.
  - inversion Hnd as [ | ? ? Hninx Hndr ]; subst.
    simpl. destruct Hin as [ Heq | Hin ].
    + subst x. rewrite Nat.eqb_refl.
      assert (Hrest : (sum_Q (fun j => if Nat.eqb j k then v else f j) r == sum_Q f r)%Q).
      { apply sum_Q_ext. intros y Hy.
        destruct (Nat.eqb_spec y k) as [ Heqy | _ ]; [ subst y; contradiction | reflexivity ]. }
      rewrite Hrest. lra.
    + destruct (Nat.eqb_spec x k) as [ Heqx | Hnek ].
      * subst x. contradiction.
      * rewrite (IH Hndr Hin). lra.
Qed.

Lemma upto_NoDup : forall n : nat, NoDup (upto n).
Proof.
  induction n as [ | k IH ].
  - simpl. constructor.
  - simpl.
    assert (Hnot : ~ In k (upto k)).
    { intros Hin. apply upto_in in Hin. lia. }
    clear -IH Hnot. induction (upto k) as [ | x r IHr ].
    + simpl. constructor; [ intros [] | constructor ].
    + simpl. inversion IH as [ | ? ? Hnx Hnr ]; subst.
      constructor.
      * intros Hin. apply in_app_or in Hin. destruct Hin as [ Hin | [ Heq | [] ] ].
        -- exact (Hnx Hin).
        -- subst x. apply Hnot. left. reflexivity.
      * apply IHr; [ exact Hnr | intros Hk; apply Hnot; right; exact Hk ].
Qed.

Lemma sum_nat_qn : forall f l,
  (qn (sum_nat f l) == sum_Q (fun j => qn (f j)) l)%Q.
Proof.
  intros f l. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. rewrite qn_add, IH. reflexivity.
Qed.

Lemma max_over_ge : forall f l x, In x l -> f x <= max_over f l.
Proof.
  intros f l x. induction l as [ | y r IH ]; intros Hin.
  - destruct Hin.
  - simpl in *. destruct Hin as [ Heq | Hin ].
    + subst y. lia.
    + specialize (IH Hin). lia.
Qed.

(* =========================================================================
   S2. Invocation (iii) tentative-yield ABI extension (R-07-031b).
   ========================================================================= *)

(* The five-invocation frozen ABI with invocation (iii)'s tentative flag.
   No sixth invocation, no named successor, and no vector-save path exists. *)
Inductive ElasticInvocation : Type :=
| EpSend
| EpReceive
| PcYield (tentative : bool)
| RevRedeem
| RevRevoke.

Definition abi_base_invocation (inv : ElasticInvocation) : EndpointIPC.Invocation :=
  match inv with
  | EpSend => EndpointIPC.Send
  | EpReceive => EndpointIPC.Receive
  | PcYield _ => EndpointIPC.PollSiteYield
  | RevRedeem => EndpointIPC.GrantRedeem
  | RevRevoke => EndpointIPC.Revoke
  end.

Definition abi_number (inv : ElasticInvocation) : nat :=
  match inv with
  | EpSend => 0
  | EpReceive => 1
  | PcYield _ => 2
  | RevRedeem => 3
  | RevRevoke => 4
  end.

Definition elastic_abi_group (inv : ElasticInvocation) : EndpointIPC.AbiGroup :=
  EndpointIPC.group_of (abi_base_invocation inv).

(*| discharges: R-07-031b |*)
Theorem abi_invocation_count_remains_five :
  EndpointIPC.count_of EndpointIPC.all_invocations = 5
  /\ EndpointIPC.count_of EndpointIPC.all_groups = 4
  /\ EndpointIPC.TheNotificationGroupIsEmpty EndpointIPC.group_of
  /\ (forall inv : ElasticInvocation,
        In (abi_base_invocation inv) EndpointIPC.all_invocations
        /\ abi_number inv < 5)
  /\ abi_number (PcYield true) = abi_number (PcYield false)
  /\ elastic_abi_group (PcYield true) = EndpointIPC.PartitionContextGroup
  /\ elastic_abi_group (PcYield false) = EndpointIPC.PartitionContextGroup.
Proof.
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  split; [ exact EndpointIPC.the_specification_grouping_leaves_the_notification_group_empty | ].
  split.
  - intros inv. destruct inv; simpl; split; try lia;
      repeat (try (left; reflexivity); right).
  - repeat split; reflexivity.
Qed.

(* =========================================================================
   S3. Partition-context-only state and session-manager request cell
   (R-07-027a, R-07-037e, R-07-037i).
   ========================================================================= *)

Inductive SessionRequest : Type :=
| ReqLaunch (member core : nat)
| ReqClose (member : nat)
| ReqFocus (member : option nat).

(* Per-member EEVDF fields stored inside each member's placed PartitionContext. *)
Record MemberDispatchFields : Type := {
  mdf_active : bool;
  mdf_pending : bool;
  mdf_weight : nat;
  mdf_request : nat;
  mdf_eligible : Q;
  mdf_deadline : Q;
  mdf_switch_requested_pending : bool
}.

(* Domain-wide dispatch fields and the Launch/Close/Focus request cell, stored
   inside the domain's session manager's placed PartitionContext. *)
Record SessionManagerFields : Type := {
  smf_vtime : Q;
  smf_focus : option nat;
  smf_request_cell : option SessionRequest
}.

Record PlacedPartitionContext (m : Machine) : Type := {
  ppc_arch : Context m;
  ppc_dispatch : MemberDispatchFields;
  ppc_session_mgr : option SessionManagerFields
}.

Arguments ppc_arch {m} _.
Arguments ppc_dispatch {m} _.
Arguments ppc_session_mgr {m} _.

Record DomainPlacedState (m : Machine) : Type := {
  dps_sm_idx : nat;
  dps_contexts : nat -> PlacedPartitionContext m;
  dps_current : option nat
}.

Arguments dps_sm_idx {m} _.
Arguments dps_contexts {m} _.
Arguments dps_current {m} _.

Definition default_sm_fields : SessionManagerFields :=
  {| smf_vtime := 0%Q; smf_focus := None; smf_request_cell := None |}.

Definition sm_fields {m : Machine} (st : DomainPlacedState m) : SessionManagerFields :=
  match ppc_session_mgr (dps_contexts st (dps_sm_idx st)) with
  | Some sm => sm
  | None => default_sm_fields
  end.

Definition to_pc_fields (df : MemberDispatchFields) : PcFields :=
  {| pc_active := mdf_active df;
     pc_pending := mdf_pending df;
     pc_eligible := mdf_eligible df;
     pc_deadline := mdf_deadline df |}.

Definition to_dstate {m : Machine} (st : DomainPlacedState m) : DState :=
  let sm := sm_fields st in
  {| ds_vtime := smf_vtime sm;
     ds_focus := smf_focus sm;
     ds_member := fun i => to_pc_fields (ppc_dispatch (dps_contexts st i)) |}.

Inductive ElasticStateComponent : Type :=
| CompArchContext
| CompMemberFields
| CompSessionManagerFields
| CompMemberDeclarations
| CompDomainSlots.

Definition component_carrier (c : ElasticStateComponent) : EndpointIPC.Nameable :=
  match c with
  | CompArchContext => EndpointIPC.NPartitionContext
  | CompMemberFields => EndpointIPC.NPartitionContext
  | CompSessionManagerFields => EndpointIPC.NPartitionContext
  | CompMemberDeclarations => EndpointIPC.NScheduleTable
  | CompDomainSlots => EndpointIPC.NScheduleTable
  end.

Definition live_kernel_inventory : list EndpointIPC.Nameable :=
  EndpointIPC.filter_of
    (fun n => negb (EndpointIPC.nameable_eqb n EndpointIPC.NReplyObject))
    EndpointIPC.all_nameable.

(*| discharges: R-07-027a |*)
Theorem no_new_kernel_table_or_class :
  EndpointIPC.count_of live_kernel_inventory = 5
  /\ live_kernel_inventory =
       cons EndpointIPC.NEndpoint
         (cons EndpointIPC.NNotification
           (cons EndpointIPC.NPartitionContext
             (cons EndpointIPC.NGrantTable
               (cons EndpointIPC.NScheduleTable nil))))
  /\ (forall c : ElasticStateComponent,
        In (component_carrier c) live_kernel_inventory
        /\ component_carrier c <> EndpointIPC.NReplyObject)
  /\ component_carrier CompMemberFields = EndpointIPC.NPartitionContext
  /\ component_carrier CompSessionManagerFields = EndpointIPC.NPartitionContext
  /\ component_carrier CompMemberDeclarations = EndpointIPC.NScheduleTable.
Proof.
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  split.
  - intros c. destruct c; simpl; split; try discriminate;
      repeat (try (left; reflexivity); right).
  - split; [ reflexivity | split; reflexivity ].
Qed.

Definition eff_coop_request (d : Decl) (s : DState) (i : nat) : nat :=
  eff_request d s i + call_bound d + dc_yield_bound d.

Definition coop_deadline_at (d : Decl) (s : DState) (i : nat) (ve : Q) : Q :=
  Qplus ve (Qdiv (qn (eff_coop_request d s i)) (qn (eff_weight d s i))).

Definition set_placed_dispatch {m : Machine} (st : DomainPlacedState m) (i : nat)
    (df : MemberDispatchFields) : DomainPlacedState m :=
  {| dps_sm_idx := dps_sm_idx st;
     dps_contexts := fun j =>
       if Nat.eqb j i
       then {| ppc_arch := ppc_arch (dps_contexts st j);
               ppc_dispatch := df;
               ppc_session_mgr := ppc_session_mgr (dps_contexts st j) |}
       else dps_contexts st j;
     dps_current := dps_current st |}.

Definition set_placed_sm {m : Machine} (st : DomainPlacedState m)
    (sm : SessionManagerFields) : DomainPlacedState m :=
  {| dps_sm_idx := dps_sm_idx st;
     dps_contexts := fun j =>
       if Nat.eqb j (dps_sm_idx st)
       then {| ppc_arch := ppc_arch (dps_contexts st j);
               ppc_dispatch := ppc_dispatch (dps_contexts st j);
               ppc_session_mgr := Some sm |}
       else dps_contexts st j;
     dps_current := dps_current st |}.

Definition enact_session_request (dom : Domain) (d : Decl) {m : Machine}
    (st : DomainPlacedState m) : DomainPlacedState m :=
  let sm := sm_fields st in
  match smf_request_cell sm with
  | None => st
  | Some req =>
      let cleared := set_placed_sm st {| smf_vtime := smf_vtime sm;
                                          smf_focus := smf_focus sm;
                                          smf_request_cell := None |} in
      match req with
      | ReqLaunch mem core =>
          if launch_ok dom mem core
          then
            let df := ppc_dispatch (dps_contexts cleared mem) in
            let s := to_dstate cleared in
            let ve := smf_vtime sm in
            set_placed_dispatch cleared mem
              {| mdf_active := true;
                 mdf_pending := true;
                 mdf_weight := dc_weight d mem;
                 mdf_request := dc_request d mem;
                 mdf_eligible := ve;
                 mdf_deadline := coop_deadline_at d s mem ve;
                 mdf_switch_requested_pending := false |}
          else cleared
      | ReqClose mem =>
          let df := ppc_dispatch (dps_contexts cleared mem) in
          set_placed_dispatch cleared mem
            {| mdf_active := false;
               mdf_pending := false;
               mdf_weight := mdf_weight df;
               mdf_request := mdf_request df;
               mdf_eligible := mdf_eligible df;
               mdf_deadline := mdf_deadline df;
               mdf_switch_requested_pending := false |}
      | ReqFocus f =>
          let valid := match f with None => true | Some idx => Nat.ltb idx (dc_count d) end in
          if valid
          then set_placed_sm cleared {| smf_vtime := smf_vtime sm;
                                        smf_focus := f;
                                        smf_request_cell := None |}
          else cleared
      end
  end.

(*| discharges: R-07-037i |*)
Theorem request_cell_launch_activates_only_placed :
  forall (dom : Domain) (d : Decl) (m : Machine) (st : DomainPlacedState m) (mem core : nat),
    smf_request_cell (sm_fields st) = Some (ReqLaunch mem core) ->
    launch_ok dom mem core = true ->
    In mem (dom_members dom) /\ In core (dom_cores dom) /\ dom_dormant dom mem core = true
    /\ dps_sm_idx (enact_session_request dom d st) = dps_sm_idx st
    /\ mdf_active (ppc_dispatch (dps_contexts (enact_session_request dom d st) mem)) = true
    /\ smf_request_cell (sm_fields (enact_session_request dom d st)) = None.
Proof.
  intros dom d m st mem core Hcell Hok.
  destruct (launch_activates_only_placed_contexts dom mem core Hok) as [ Hm [ Hc Hd ] ].
  split; [ exact Hm | split; [ exact Hc | split; [ exact Hd | ] ] ].
  unfold enact_session_request. rewrite Hcell, Hok.
  split; [ reflexivity | ].
  split.
  - unfold set_placed_dispatch. simpl. rewrite Nat.eqb_refl. reflexivity.
  - unfold set_placed_dispatch, sm_fields, set_placed_sm. simpl.
    destruct (Nat.eqb (dps_sm_idx st) mem) eqn:E.
    + apply Nat.eqb_eq in E. subst mem. rewrite Nat.eqb_refl. reflexivity.
    + rewrite Nat.eqb_refl. reflexivity.
Qed.

(* =========================================================================
   S4. Tentative-yield kernel semantics and repeated-tentative backstop
   (R-07-031b, R-07-037g, R-07-014a).
   ========================================================================= *)

Inductive YieldOutcome : Type :=
| YContinue
| YSwitchRequested
| YSwitched (next : option nat).

Definition coop_charge (d : Decl) (s : DState) (i u : nat) (pending : bool) : DState :=
  let w := qn (eff_weight d s i) in
  let ve := Qplus (pc_eligible (ds_member s i)) (Qdiv (qn u) w) in
  set_member (advance d s u) i
    {| (ds_member s i) with
       pc_pending := pending;
       pc_eligible := ve;
       pc_deadline := Qplus ve (Qdiv (qn (eff_coop_request d s i)) w) |}.

Definition invoke_pc_yield (d : Decl) {m : Machine} (st : DomainPlacedState m)
    (tentative : bool) (used rem : nat) : YieldOutcome * DomainPlacedState m :=
  match dps_current st with
  | None =>
      let next := select d (to_dstate st) in
      (YSwitched next,
       {| dps_sm_idx := dps_sm_idx st;
          dps_contexts := dps_contexts st;
          dps_current := next |})
  | Some i =>
      let df := ppc_dispatch (dps_contexts st i) in
      let s := to_dstate st in
      if negb tentative || mdf_switch_requested_pending df
      then
        let s' := coop_charge d s i used (mdf_pending df) in
        let next := select d s' in
        let sm := sm_fields st in
        let st1 := set_placed_sm st {| smf_vtime := ds_vtime s';
                                       smf_focus := ds_focus s';
                                       smf_request_cell := smf_request_cell sm |} in
        let pc_i := ds_member s' i in
        let st2 := set_placed_dispatch st1 i
                     {| mdf_active := pc_active pc_i;
                        mdf_pending := pc_pending pc_i;
                        mdf_weight := mdf_weight df;
                        mdf_request := mdf_request df;
                        mdf_eligible := pc_eligible pc_i;
                        mdf_deadline := pc_deadline pc_i;
                        mdf_switch_requested_pending := false |} in
        (YSwitched next,
         {| dps_sm_idx := dps_sm_idx st2;
            dps_contexts := dps_contexts st2;
            dps_current := next |})
      else
        match reply d s i used rem with
        | Continue => (YContinue, st)
        | SwitchRequested =>
            (YSwitchRequested,
             set_placed_dispatch st i
               {| mdf_active := mdf_active df;
                  mdf_pending := mdf_pending df;
                  mdf_weight := mdf_weight df;
                  mdf_request := mdf_request df;
                  mdf_eligible := mdf_eligible df;
                  mdf_deadline := mdf_deadline df;
                  mdf_switch_requested_pending := true |})
        end
  end.

(*| discharges: R-07-031b |*)
Theorem tentative_yield_does_not_switch :
  forall (d : Decl) (m : Machine) (st : DomainPlacedState m) (i used rem : nat),
    dps_current st = Some i ->
    mdf_switch_requested_pending (ppc_dispatch (dps_contexts st i)) = false ->
    (fst (invoke_pc_yield d st true used rem) = YContinue
     \/ fst (invoke_pc_yield d st true used rem) = YSwitchRequested)
    /\ dps_current (snd (invoke_pc_yield d st true used rem)) = Some i.
Proof.
  intros d m st i used rem Hcur Hpend.
  unfold invoke_pc_yield. rewrite Hcur, Hpend. simpl.
  destruct (reply d (to_dstate st) i used rem); split; try (left; reflexivity);
    try (right; reflexivity); simpl; exact Hcur.
Qed.

Theorem real_yield_enacts_switch :
  forall (d : Decl) (m : Machine) (st : DomainPlacedState m) (used rem : nat),
    fst (invoke_pc_yield d st false used rem)
    = YSwitched (dps_current (snd (invoke_pc_yield d st false used rem))).
Proof.
  intros d m st used rem. unfold invoke_pc_yield.
  destruct (dps_current st) as [ i | ]; simpl; reflexivity.
Qed.

(*| discharges: R-07-031b, R-07-037g |*)
Theorem repeated_tentative_backstop_switches :
  forall (d : Decl) (m : Machine) (st : DomainPlacedState m) (i used1 rem1 used2 rem2 : nat),
    dps_current st = Some i ->
    mdf_switch_requested_pending (ppc_dispatch (dps_contexts st i)) = false ->
    reply d (to_dstate st) i used1 rem1 = SwitchRequested ->
    let res1 := invoke_pc_yield d st true used1 rem1 in
    let res2 := invoke_pc_yield d (snd res1) true used2 rem2 in
    fst res1 = YSwitchRequested
    /\ dps_current (snd res1) = Some i
    /\ fst res2 = YSwitched (dps_current (snd res2))
    /\ mdf_switch_requested_pending (ppc_dispatch (dps_contexts (snd res2) i)) = false.
Proof.
  intros d m st i used1 rem1 used2 rem2 Hcur Hpend Hrep.
  cbv zeta.
  unfold invoke_pc_yield. rewrite Hcur, Hpend, Hrep. simpl.
  split; [ reflexivity | ].
  split; [ unfold set_placed_dispatch; simpl; exact Hcur | ].
  unfold set_placed_dispatch at 1 2 3. simpl.
  rewrite Hcur, Nat.eqb_refl. simpl.
  split; [ reflexivity | ].
  unfold set_placed_dispatch. simpl. rewrite Nat.eqb_refl. reflexivity.
Qed.

(* =========================================================================
   S5. Inter-application vmclear and static-schedule elision
   (R-07-014, R-07-014a, R-07-014c, R-07-037b, R-07-037c, R-07-037d,
   R-07-037g; closes F-428).
   ========================================================================= *)

Record StaticSlotManifest : Type := {
  ssm_vs_off : bool;
  ssm_xs_off : bool
}.

Definition vs_xs_fixed_off (ssm : StaticSlotManifest) : bool :=
  ssm_vs_off ssm && ssm_xs_off ssm.

Definition static_switch_performs (ssm : StaticSlotManifest) (a : Action) : bool :=
  match a with
  | Restore => true
  | FenceT => true
  | Vmclear => negb (vs_xs_fixed_off ssm)
  | OppRelock => true
  end.

Definition StaticSlotSwitch (m : Machine) (ssm : StaticSlotManifest) : Step m :=
  fun succ pre post =>
    (forall r, Nat.ltb r register_count = true -> ctx_reg post r = ctx_reg succ r)
    /\ (forall c, csr_nameable m c = true -> csr_zeroized m c = false ->
          ctx_csr post c = ctx_csr succ c)
    /\ (if vs_xs_fixed_off ssm
        then True
        else forall c, csr_nameable m c = true -> csr_zeroized m c = true ->
               ctx_csr post c = zero_word m)
    /\ ctx_pending post = pending_written m succ.

(*| discharges: R-07-014c, R-07-037g |*)
Theorem cross_app_step_executes_vmclear :
  forall (d : Decl) (out_m in_m : nat),
    dc_app d out_m <> dc_app d in_m ->
    performs_between d out_m in_m Vmclear = true
    /\ constants_paid (dc_machine d) (performs_between d out_m in_m) = vmclear_cost (dc_machine d)
    /\ RestoresNameableCsrs (dc_machine d) (step_between d out_m in_m)
    /\ (rotation_swaps_pending (dc_machine d) = true ->
        NoResidue (dc_machine d) (step_between d out_m in_m)).
Proof.
  intros d out_m in_m Hdiff.
  unfold performs_between, same_application.
  rewrite (proj2 (Nat.eqb_neq _ _) Hdiff).
  split; [ reflexivity | ].
  split; [ exact (proj1 (the_clear_costs_one_vmclear_and_nothing_else _)) | ].
  split; [ exact (a_step_between_applications_clears_the_zeroize_class d out_m in_m Hdiff) | ].
  intro Hswap. exact (a_step_between_applications_leaves_no_residue d out_m in_m Hdiff Hswap).
Qed.

(*| discharges: R-07-037b, R-07-037c, R-07-037d |*)
Theorem same_app_step_elides_vmclear :
  forall (d : Decl) (out_m in_m : nat),
    dc_app d out_m = dc_app d in_m ->
    performs_between d out_m in_m Vmclear = false
    /\ constants_paid (dc_machine d) (performs_between d out_m in_m) = 0
    /\ (forall succ pre post,
          step_between d out_m in_m succ pre post <-> Rotation (dc_machine d) succ pre post).
Proof.
  intros d out_m in_m Heq.
  unfold performs_between, same_application.
  rewrite Heq, Nat.eqb_refl.
  split; [ reflexivity | ].
  split; [ exact (proj2 (the_clear_costs_one_vmclear_and_nothing_else _)) | ].
  intros succ pre post. exact (a_step_inside_one_application_is_the_rotation d out_m in_m succ pre post Heq).
Qed.

(*| discharges: R-07-014, R-07-014c |*)
Theorem static_elision_requires_vs_xs_off :
  forall (m : Machine) (ssm : StaticSlotManifest),
    (static_switch_performs ssm Vmclear = false <->
       (ssm_vs_off ssm = true /\ ssm_xs_off ssm = true))
    /\ ((ssm_vs_off ssm = false \/ ssm_xs_off ssm = false) ->
        static_switch_performs ssm Vmclear = true
        /\ constants_paid m (static_switch_performs ssm) = switch_cost m
        /\ RestoresNameableCsrs m (StaticSlotSwitch m ssm)
        /\ (forall succ pre post, StaticSlotSwitch m ssm succ pre post <-> Switch m succ pre post))
    /\ (ssm_vs_off ssm = true /\ ssm_xs_off ssm = true ->
        constants_paid m (static_switch_performs ssm) = fence_t_cost m + opp_relock_cost m).
Proof.
  intros m ssm. split; [ | split ].
  - unfold static_switch_performs, vs_xs_fixed_off.
    destruct (ssm_vs_off ssm), (ssm_xs_off ssm); simpl; split; intro H;
      try discriminate H; try (split; reflexivity); destruct H as [ H1 H2 ];
      try discriminate H1; try discriminate H2; reflexivity.
  - intros Hactive.
    assert (Hoff : vs_xs_fixed_off ssm = false).
    { unfold vs_xs_fixed_off. destruct Hactive as [ H | H ]; rewrite H;
        [ reflexivity | apply andb_false_r ]. }
    unfold static_switch_performs, constants_paid, switch_cost.
    rewrite Hoff. simpl.
    split; [ reflexivity | ].
    split; [ lia | ].
    split.
    + intros succ pre post [ _ [ Hrest [ Hzero _ ] ] ] c Hn.
      rewrite Hoff in Hzero.
      destruct (csr_zeroized m c) eqn:Ez.
      * exact (Hzero c Hn Ez).
      * exact (Hrest c Hn Ez).
    + intros succ pre post. unfold StaticSlotSwitch, Switch. rewrite Hoff.
      split; [ intros [ Hreg [ Hrest [ Hzero Hp ] ] ] | intros [ Hreg [ Hrest Hp ] ] ].
      * split; [ exact Hreg | split; [ | exact Hp ] ].
        intros c Hn. destruct (csr_zeroized m c) eqn:Ez;
          [ exact (Hzero c Hn Ez) | exact (Hrest c Hn Ez) ].
      * split; [ exact Hreg | split ].
        -- intros c Hn Ez. rewrite (Hrest c Hn), Ez. reflexivity.
        -- split; [ | exact Hp ].
           intros c Hn Ez. rewrite (Hrest c Hn), Ez. reflexivity.
  - intros [ Hvs Hxs ]. unfold static_switch_performs, constants_paid, vs_xs_fixed_off.
    rewrite Hvs, Hxs. simpl. lia.
Qed.

(* =========================================================================
   S6. Cooperative boundary rule and label-internal non-interference
   unwinding (R-07-032, R-07-037g, R-07-037h).
   ========================================================================= *)

Definition LabelInternalUnwinding {X : Type}
    (choice : Global -> X) (step : DomainStep) : Prop :=
  ReadsOnlyItsLabel choice /\ MovesNothingOutside step.

Definition kernel_dispatch_choice (d : Decl) (used rem : nat) (g : Global) : Reply * option nat :=
  let s := g_domain g in
  match select d s with
  | None => (SwitchRequested, None)
  | Some i => (reply d s i used rem, Some i)
  end.

Definition kernel_dispatch_step (d : Decl) (used : nat) (pending : bool) : DomainStep :=
  within_the_envelope (fun s s' =>
    exists i, Selects d s i /\ s' = coop_charge d s i used pending).

(*| discharges: R-07-037g, R-07-037h |*)
Theorem cooperative_boundary_never_cuts :
  forall d : Decl, NeverCuts (boundary_ok d) (dc_yield_bound d) d.
Proof.
  exact the_boundary_rule_leaves_no_member_cut.
Qed.

(*| discharges: R-07-032, R-07-037g |*)
Theorem elastic_dispatch_label_internal_unwinding :
  forall (d : Decl) (used rem : nat) (pending : bool),
    LabelInternalUnwinding (kernel_dispatch_choice d used rem)
                           (kernel_dispatch_step d used pending)
    /\ (forall g g' ph t,
          kernel_dispatch_step d used pending g g' ->
          slot_index_at (frame_slots (g_frame g')) ph t
          = slot_index_at (frame_slots (g_frame g)) ph t).
Proof.
  intros d used rem pending. split.
  - split.
    + intros g1 g2 Hg. unfold kernel_dispatch_choice. rewrite Hg. reflexivity.
    + apply every_domain_transition_stays_inside.
  - intros g g' ph t Hstep.
    destruct (every_domain_transition_stays_inside _ g g' Hstep) as [ Hf _ ].
    rewrite Hf. reflexivity.
Qed.

(* =========================================================================
   S7. Universal Cooperative EEVDF Share-Bound Theorem
   (R-07-037g, R-11-006c, R-17-007b; closes F-430, F-431, F-432).
   ========================================================================= *)

Definition AdmissibleCoopDecl (d : Decl) : Prop :=
  0 < dc_count d
  /\ (forall i, i < dc_count d -> 1 <= dc_weight d i /\ 1 <= dc_request d i)
  /\ 1 <= dc_focus_weight d
  /\ 1 <= dc_focus_request d.

Lemma admissible_eff_bounds : forall d s i,
  AdmissibleCoopDecl d -> i < dc_count d ->
  1 <= eff_weight d s i
  /\ 1 <= eff_request d s i
  /\ eff_coop_request d s i <= max_request d + call_bound d + dc_yield_bound d.
Proof.
  intros d s i [ _ [ Hmem [ Hfw Hfr ] ] ] Hi.
  destruct (Hmem i Hi) as [ Hwi Hri ].
  unfold eff_coop_request, eff_weight, max_request. unfold eff_request.
  pose proof (max_over_ge (dc_request d) _ i (in_upto _ _ Hi)) as Hmax.
  destruct (is_focus s i); repeat split; lia.
Qed.

Lemma admissible_competing_total_weight : forall d s i,
  AdmissibleCoopDecl d -> competing d s i = true ->
  eff_weight d s i <= total_weight d s /\ 1 <= total_weight d s.
Proof.
  intros d s i Hadm Hcomp.
  pose proof (competing_lt d s i Hcomp) as Hlt.
  pose proof (admissible_eff_bounds d s i Hadm Hlt) as [ Hwi _ ].
  unfold total_weight.
  assert (Hsum : forall l, In i l ->
    eff_weight d s i <= sum_nat (fun j => if competing d s j then eff_weight d s j else 0) l).
  { intros l. induction l as [ | x r IH ]; intros Hin.
    - destruct Hin.
    - simpl in *. destruct Hin as [ Heq | Hin ].
      + subst x. rewrite Hcomp. lia.
      + specialize (IH Hin). destruct (competing d s x); lia. }
  pose proof (Hsum (upto (dc_count d)) (in_upto _ _ Hlt)) as Hle.
  lia.
Qed.

Definition sum_competing_lag (d : Decl) (s : DState) : Q :=
  sum_Q (fun j => if competing d s j then accounting_lag d s j else 0%Q) (upto (dc_count d)).

Definition coop_fresh (d : Decl) (s : DState) : bool :=
  Qeq_bool (ds_vtime s) 0
  && all_of (fun i => implb (competing d s i)
                        (Qeq_bool (pc_eligible (ds_member s i)) 0
                         && Qeq_bool (pc_deadline (ds_member s i))
                              (Qdiv (qn (eff_coop_request d s i)) (qn (eff_weight d s i)))))
            (upto (dc_count d)).

Definition coop_join (d : Decl) (s : DState) (j : nat) : DState :=
  let v := ds_vtime s in
  set_member s j
    {| pc_active := true;
       pc_pending := true;
       pc_eligible := v;
       pc_deadline := coop_deadline_at d s j v |}.

Definition coop_reweight (d d' : Decl) (s : DState) (f' : option nat) : DState :=
  let s1 := {| s with ds_focus := f' |} in
  {| s1 with
     ds_member := fun j =>
       let w' := qn (eff_weight d' s1 j) in
       let ve' := Qminus (ds_vtime s) (Qdiv (accounting_lag d s j) w') in
       {| (ds_member s j) with
          pc_eligible := ve';
          pc_deadline := coop_deadline_at d' s1 j ve' |} |}.

Definition coop_published_leave (d : Decl) (s : DState) (j : nat) : DState :=
  let l_j := accounting_lag d s j in
  let s_left := set_member s j {| (ds_member s j) with pc_pending := false |} in
  let w_rem := total_weight d s_left in
  if Nat.eqb w_rem 0
  then s_left
  else {| s_left with ds_vtime := Qplus (ds_vtime s_left) (Qdiv l_j (qn w_rem)) |}.

Definition coop_zero_lag_leave (s : DState) (j : nat) : DState :=
  set_member s j {| (ds_member s j) with pc_pending := false |}.

(* --- Zero-sum accounting lag & work conservation --- *)

Lemma coop_fresh_zero_sum : forall d s,
  coop_fresh d s = true -> (sum_competing_lag d s == 0)%Q.
Proof.
  intros d s Hf. unfold coop_fresh in Hf.
  apply andb_prop in Hf. destruct Hf as [ Hv Hall ].
  apply Qeq_bool_iff in Hv.
  unfold sum_competing_lag. apply sum_Q_zero.
  intros x Hx. destruct (competing d s x) eqn:Ec; [ | reflexivity ].
  pose proof (all_of_in _ _ _ _ Hall Hx) as Hi. cbv beta in Hi.
  rewrite Ec in Hi. simpl in Hi. apply andb_prop in Hi. destruct Hi as [ He _ ].
  apply Qeq_bool_iff in He. unfold accounting_lag. rewrite Hv, He. lra.
Qed.

Lemma competing_set_member_same : forall d s i f j,
  pc_active f = pc_active (ds_member s i) ->
  pc_pending f = pc_pending (ds_member s i) ->
  competing d (set_member s i f) j = competing d s j.
Proof.
  intros d s i f j Ha Hp. unfold competing, set_member. simpl.
  destruct (Nat.eqb_spec j i) as [ Heq | _ ]; [ subst j; rewrite Ha, Hp; reflexivity | reflexivity ].
Qed.

Lemma eff_weight_set_member : forall d s i f j,
  eff_weight d (set_member s i f) j = eff_weight d s j.
Proof.
  intros d s i f j. unfold eff_weight, is_focus, set_member. simpl. reflexivity.
Qed.

Lemma total_weight_set_member_same : forall d s i f,
  pc_active f = pc_active (ds_member s i) ->
  pc_pending f = pc_pending (ds_member s i) ->
  total_weight d (set_member s i f) = total_weight d s.
Proof.
  intros d s i f Ha Hp. unfold total_weight.
  induction (upto (dc_count d)) as [ | x r IH ].
  - reflexivity.
  - simpl. rewrite (competing_set_member_same d s i f x Ha Hp), eff_weight_set_member, IH.
    reflexivity.
Qed.

Lemma coop_charge_preserves_zero_sum : forall d s i u,
  AdmissibleCoopDecl d ->
  competing d s i = true ->
  (sum_competing_lag d s == 0)%Q ->
  (sum_competing_lag d (coop_charge d s i u true) == 0)%Q.
Proof.
  intros d s i u Hadm Hcomp Hsum.
  pose proof (competing_lt d s i Hcomp) as Hlt.
  pose proof (admissible_eff_bounds d s i Hadm Hlt) as [ Hwi _ ].
  pose proof (admissible_competing_total_weight d s i Hadm Hcomp) as [ _ HW ].
  assert (Hpend : pc_pending (ds_member s i) = true).
  { unfold competing in Hcomp. apply andb_prop in Hcomp. exact (proj2 Hcomp). }
  unfold sum_competing_lag, coop_charge.
  assert (Hext :
    (sum_Q (fun j =>
       if competing d (set_member (advance d s u) i
            {| pc_active := pc_active (ds_member s i);
               pc_pending := true;
               pc_eligible := Qplus (pc_eligible (ds_member s i))
                                    (Qdiv (qn u) (qn (eff_weight d s i)));
               pc_deadline := Qplus (Qplus (pc_eligible (ds_member s i))
                                           (Qdiv (qn u) (qn (eff_weight d s i))))
                                    (Qdiv (qn (eff_coop_request d s i))
                                          (qn (eff_weight d s i))) |}) j
       then accounting_lag d (set_member (advance d s u) i
            {| pc_active := pc_active (ds_member s i);
               pc_pending := true;
               pc_eligible := Qplus (pc_eligible (ds_member s i))
                                    (Qdiv (qn u) (qn (eff_weight d s i)));
               pc_deadline := Qplus (Qplus (pc_eligible (ds_member s i))
                                           (Qdiv (qn u) (qn (eff_weight d s i))))
                                    (Qdiv (qn (eff_coop_request d s i))
                                          (qn (eff_weight d s i))) |}) j
       else 0%Q) (upto (dc_count d))
     ==
     sum_Q (fun j =>
       (if competing d s j then accounting_lag d s j else 0%Q)
       + (if competing d s j
          then (qn (eff_weight d s j) * (qn u / qn (total_weight d s)))%Q
          else 0%Q)
       - (if Nat.eqb j i then qn u else 0%Q)) (upto (dc_count d)))%Q).
  { apply sum_Q_ext. intros j Hj.
    rewrite competing_set_member_same; [ | reflexivity | simpl; symmetry; exact Hpend ].
    assert (Hcomp_adv : competing d (advance d s u) j = competing d s j) by reflexivity.
    rewrite Hcomp_adv.
    destruct (competing d s j) eqn:Ej.
    - unfold accounting_lag, eff_weight, is_focus, set_member, advance. simpl.
      destruct (Nat.eqb_spec j i) as [ Heq | Hne ].
      + subst j. simpl.
        field. split; [ apply qn_nonzero; exact HW | apply qn_nonzero; exact Hwi ].
      + ring.
    - destruct (Nat.eqb_spec j i) as [ Heq | _ ].
      + subst j. rewrite Ej in Hcomp. discriminate Hcomp.
      + ring. }
  rewrite Hext.
  assert (Hsplit :
    (sum_Q (fun j =>
       (if competing d s j then accounting_lag d s j else 0%Q)
       + (if competing d s j
          then (qn (eff_weight d s j) * (qn u / qn (total_weight d s)))%Q
          else 0%Q)
       - (if Nat.eqb j i then qn u else 0%Q)) (upto (dc_count d))
     ==
     sum_competing_lag d s
     + sum_Q (fun j => (qn u / qn (total_weight d s)) *
                         qn (if competing d s j then eff_weight d s j else 0))
             (upto (dc_count d))
     - sum_Q (fun j => if Nat.eqb j i then qn u else 0%Q) (upto (dc_count d)))%Q).
  { unfold sum_competing_lag.
    assert (H1 :
      (sum_Q (fun j =>
         (if competing d s j then accounting_lag d s j else 0%Q)
         + (if competing d s j
            then (qn (eff_weight d s j) * (qn u / qn (total_weight d s)))%Q
            else 0%Q)
         - (if Nat.eqb j i then qn u else 0%Q)) (upto (dc_count d))
       ==
       sum_Q (fun j =>
         (if competing d s j then accounting_lag d s j else 0%Q)
         + ((if competing d s j
             then (qn (eff_weight d s j) * (qn u / qn (total_weight d s)))%Q
             else 0%Q)
            + (- (if Nat.eqb j i then qn u else 0%Q)))) (upto (dc_count d)))%Q).
    { apply sum_Q_ext. intros j _. ring. }
    rewrite H1. rewrite sum_Q_add.
    rewrite (sum_Q_add (fun j => if competing d s j
                                 then (qn (eff_weight d s j) * (qn u / qn (total_weight d s)))%Q
                                 else 0%Q)
                       (fun j => (- (if Nat.eqb j i then qn u else 0%Q))%Q)).
    assert (H2 :
      (sum_Q (fun j => if competing d s j
                       then (qn (eff_weight d s j) * (qn u / qn (total_weight d s)))%Q
                       else 0%Q) (upto (dc_count d))
       == sum_Q (fun j => (qn u / qn (total_weight d s)) *
                            qn (if competing d s j then eff_weight d s j else 0))
                (upto (dc_count d)))%Q).
    { apply sum_Q_ext. intros j _. destruct (competing d s j); [ ring | change (qn 0) with 0%Q; ring ]. }
    assert (H3 :
      (sum_Q (fun j => (- (if Nat.eqb j i then qn u else 0%Q))%Q) (upto (dc_count d))
       == - sum_Q (fun j => if Nat.eqb j i then qn u else 0%Q) (upto (dc_count d)))%Q).
    { rewrite <- (sum_Q_scale (-1%Q) (fun j => if Nat.eqb j i then qn u else 0%Q)).
      apply sum_Q_ext. intros j _. ring. }
    rewrite H2, H3. lra. }
  rewrite Hsplit, Hsum.
  rewrite sum_Q_scale.
  fold (total_weight d s).
  rewrite <- sum_nat_qn.
  change (sum_nat (fun j => if competing d s j then eff_weight d s j else 0) (upto (dc_count d)))
    with (total_weight d s).
  assert (Hone : (sum_Q (fun j => if Nat.eqb j i then qn u else 0%Q) (upto (dc_count d)) == qn u)%Q).
  { pose proof (sum_Q_replace_one (fun _ => 0%Q) (upto (dc_count d)) i (qn u)
                  (upto_NoDup _) (in_upto _ _ Hlt)) as Hr.
    rewrite (sum_Q_zero (fun _ => 0%Q) (upto (dc_count d)) (fun _ _ => Qeq_refl _)) in Hr.
    rewrite Hr. lra. }
  rewrite Hone.
  assert (HWnz : ~ (qn (total_weight d s) == 0)%Q) by (apply qn_nonzero; exact HW).
  field. exact HWnz.
Qed.

Lemma coop_join_preserves_zero_sum : forall d s j,
  j < dc_count d ->
  competing d s j = false ->
  (sum_competing_lag d s == 0)%Q ->
  (sum_competing_lag d (coop_join d s j) == 0)%Q.
Proof.
  intros d s j Hlt Hnc Hsum.
  unfold sum_competing_lag, coop_join in *.
  rewrite <- Hsum. apply sum_Q_ext. intros x _.
  unfold competing, set_member. simpl.
  destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
  - subst x.
    assert (Hltb : Nat.ltb j (dc_count d) = true) by (apply Nat.ltb_lt; exact Hlt).
    rewrite Hltb. simpl.
    unfold competing in Hnc. rewrite Hltb in Hnc. simpl in Hnc. rewrite Hnc.
    unfold accounting_lag. simpl. rewrite Nat.eqb_refl. simpl. lra.
  - unfold accounting_lag, eff_weight, is_focus. simpl.
    destruct (Nat.eqb_spec x j); [ contradiction | ].
    destruct (Nat.ltb x (dc_count d) && pc_active (ds_member s x) && pc_pending (ds_member s x));
      reflexivity.
Qed.

Lemma coop_reweight_preserves_zero_sum : forall d d' s f',
  dc_count d' = dc_count d ->
  (forall k, k < dc_count d -> 1 <= eff_weight d' {| s with ds_focus := f' |} k) ->
  (sum_competing_lag d s == 0)%Q ->
  (sum_competing_lag d' (coop_reweight d d' s f') == 0)%Q.
Proof.
  intros d d' s f' Hcnt Hw Hsum.
  unfold sum_competing_lag, coop_reweight. rewrite Hcnt.
  rewrite <- Hsum. apply sum_Q_ext. intros j Hj.
  apply upto_in in Hj.
  unfold competing, accounting_lag, eff_weight, is_focus. simpl.
  rewrite Hcnt.
  destruct (Nat.ltb j (dc_count d) && pc_active (ds_member s j) && pc_pending (ds_member s j));
    [ | reflexivity ].
  assert (Hnz : ~ (qn (if (if f' is Some f then Nat.eqb f j else false)
                        then dc_focus_weight d' else dc_weight d' j) == 0)%Q).
  { apply qn_nonzero. exact (Hw j Hj). }
  field. exact Hnz.
Qed.

Lemma coop_published_leave_preserves_zero_sum : forall d s j,
  AdmissibleCoopDecl d ->
  competing d s j = true ->
  (sum_competing_lag d s == 0)%Q ->
  (sum_competing_lag d (coop_published_leave d s j) == 0)%Q.
Proof.
  intros d s j Hadm Hcomp Hsum.
  pose proof (competing_lt d s j Hcomp) as Hlt.
  unfold coop_published_leave.
  set (s_left := set_member s j {| (ds_member s j) with pc_pending := false |}).
  set (w_rem := total_weight d s_left).
  assert (Hcomp_left : forall x, competing d s_left x = if Nat.eqb x j then false else competing d s x).
  { intros x. unfold competing, s_left, set_member. simpl.
    destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
    - subst x. rewrite andb_false_r. reflexivity.
    - reflexivity. }
  destruct (Nat.eqb_spec w_rem 0) as [ Hw0 | Hwnz ].
  - unfold sum_competing_lag. apply sum_Q_zero. intros x Hx.
    destruct (competing d s_left x) eqn:Ex; [ | reflexivity ].
    exfalso.
    assert (Hpos : 1 <= eff_weight d s_left x).
    { apply (proj1 (admissible_eff_bounds d s_left x Hadm (upto_in _ _ Hx))). }
    assert (Hge : eff_weight d s_left x <= total_weight d s_left).
    { clear -Ex Hx. unfold total_weight.
      assert (Hmem : forall l, In x l ->
        (if competing d s_left x then eff_weight d s_left x else 0)
        <= sum_nat (fun k => if competing d s_left k then eff_weight d s_left k else 0) l).
      { induction l as [ | y r IH ]; intros Hin.
        - destruct Hin.
        - simpl in *. destruct Hin as [ Heq | Hin ];
            [ subst y; lia | specialize (IH Hin); destruct (competing d s_left y); lia ]. }
      pose proof (Hmem (upto (dc_count d)) Hx) as Hm. rewrite Ex in Hm. exact Hm. }
    change (total_weight d s_left) with w_rem in Hge. lia.
  - assert (Hwpos : 1 <= w_rem) by lia.
    assert (HwnzQ : ~ (qn w_rem == 0)%Q) by (apply qn_nonzero; exact Hwpos).
    unfold sum_competing_lag.
    assert (Hext :
      (sum_Q (fun x =>
         if competing d {| s_left with ds_vtime := Qplus (ds_vtime s_left)
                                                        (Qdiv (accounting_lag d s j) (qn w_rem)) |} x
         then accounting_lag d {| s_left with ds_vtime := Qplus (ds_vtime s_left)
                                                                (Qdiv (accounting_lag d s j) (qn w_rem)) |} x
         else 0%Q) (upto (dc_count d))
       ==
       sum_Q (fun x =>
         (if Nat.eqb x j then 0%Q
          else if competing d s x then accounting_lag d s x else 0%Q)
         + (accounting_lag d s j / qn w_rem)
           * qn (if competing d s_left x then eff_weight d s_left x else 0))
       (upto (dc_count d)))%Q).
    { apply sum_Q_ext. intros x _.
      change (competing d {| s_left with ds_vtime := Qplus (ds_vtime s_left)
                                                          (Qdiv (accounting_lag d s j) (qn w_rem)) |} x)
        with (competing d s_left x).
      rewrite Hcomp_left.
      destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
      - subst x. simpl. change (qn 0) with 0%Q. ring.
      - destruct (Nat.eqb_spec x j); [ contradiction | ].
        destruct (competing d s x) eqn:Ex.
        + unfold accounting_lag, s_left, set_member, eff_weight, is_focus. simpl.
          destruct (Nat.eqb_spec x j); [ contradiction | ].
          ring.
        + change (qn 0) with 0%Q. ring. }
    rewrite Hext, sum_Q_add, sum_Q_scale, <- sum_nat_qn.
    fold (total_weight d s_left).
    change (total_weight d s_left) with w_rem.
    pose proof (sum_Q_replace_one
                  (fun x => if competing d s x then accounting_lag d s x else 0%Q)
                  (upto (dc_count d)) j 0%Q (upto_NoDup _) (in_upto _ _ Hlt)) as Hrep.
    assert (Hrep_eq :
      (sum_Q (fun x => if Nat.eqb x j then 0%Q else if competing d s x then accounting_lag d s x else 0%Q)
             (upto (dc_count d))
       == sum_competing_lag d s - accounting_lag d s j)%Q).
    { unfold sum_competing_lag. rewrite Hrep, Hcomp. lra. }
    rewrite Hrep_eq, Hsum.
    field. exact HwnzQ.
Qed.

Lemma coop_zero_lag_leave_preserves_zero_sum : forall d s j,
  competing d s j = true ->
  (accounting_lag d s j == 0)%Q ->
  (sum_competing_lag d s == 0)%Q ->
  (sum_competing_lag d (coop_zero_lag_leave s j) == 0)%Q.
Proof.
  intros d s j Hcomp Hlag Hsum.
  pose proof (competing_lt d s j Hcomp) as Hlt.
  unfold sum_competing_lag, coop_zero_lag_leave.
  pose proof (sum_Q_replace_one
                (fun x => if competing d s x then accounting_lag d s x else 0%Q)
                (upto (dc_count d)) j 0%Q (upto_NoDup _) (in_upto _ _ Hlt)) as Hrep.
  assert (Hext :
    (sum_Q (fun x => if competing d (set_member s j {| (ds_member s j) with pc_pending := false |}) x
                     then accounting_lag d (set_member s j {| (ds_member s j) with pc_pending := false |}) x
                     else 0%Q) (upto (dc_count d))
     == sum_Q (fun x => if Nat.eqb x j then 0%Q
                        else if competing d s x then accounting_lag d s x else 0%Q)
              (upto (dc_count d)))%Q).
  { apply sum_Q_ext. intros x _.
    unfold competing, set_member, accounting_lag, eff_weight, is_focus. simpl.
    destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
    - subst x. rewrite andb_false_r. reflexivity.
    - destruct (Nat.eqb_spec x j); [ contradiction | ].
      destruct (Nat.ltb x (dc_count d) && pc_active (ds_member s x) && pc_pending (ds_member s x));
        reflexivity. }
  rewrite Hext, Hrep. unfold sum_competing_lag in Hsum.
  rewrite Hsum, Hcomp, Hlag. lra.
Qed.

(*| discharges: R-07-037g |*)
Theorem zero_sum_implies_eligible_exists : forall d s,
  AdmissibleCoopDecl d ->
  (exists k, competing d s k = true) ->
  (sum_competing_lag d s == 0)%Q ->
  (exists i, competing d s i = true /\ eligible d s i = true)
  /\ select d s <> None.
Proof.
  intros d s Hadm [ k Hk ] Hsum.
  assert (Hex : exists i, competing d s i = true /\ eligible d s i = true).
  { destruct (any_of (eligible d s) (upto (dc_count d))) eqn:Eany.
    - destruct (any_of_in _ _ _ Eany) as [ i [ _ Hi ] ].
      exists i. split; [ exact (eligible_competing d s i Hi) | exact Hi ].
    - exfalso.
      assert (Hnone : forall j, competing d s j = true -> eligible d s j = false).
      { intros j Hj. destruct (eligible d s j) eqn:Ej; [ | reflexivity ].
        pose proof (competing_lt d s j Hj) as Hlt.
        assert (Htrue : any_of (eligible d s) (upto (dc_count d)) = true).
        { clear -Ej Hlt. generalize (in_upto _ _ Hlt).
          induction (upto (dc_count d)) as [ | x r IH ]; intros Hin.
          - destruct Hin.
          - simpl in *. destruct Hin as [ Heq | Hin ].
            + subst x. rewrite Ej. reflexivity.
            + rewrite (IH Hin). apply orb_true_r. }
        rewrite Htrue in Eany. discriminate Eany. }
      assert (Hle : forall j, In j (upto (dc_count d)) ->
        ((if competing d s j then accounting_lag d s j else 0%Q) <= 0)%Q).
      { intros j Hj. destruct (competing d s j) eqn:Ej; [ | lra ].
        pose proof (Hnone j Ej) as Hne. unfold eligible in Hne.
        rewrite Ej in Hne. simpl in Hne.
        assert (Hltv : (ds_vtime s < pc_eligible (ds_member s j))%Q).
        { apply Qnot_le_lt. intros Hle. apply Qle_bool_iff in Hle.
          rewrite Hle in Hne. discriminate Hne. }
        pose proof (qn_pos _ (proj1 (admissible_eff_bounds d s j Hadm (upto_in _ _ Hj)))) as Hw.
        unfold accounting_lag. apply Qlt_le_weak.
        apply qmult_pos_neg; [ exact Hw | lra ]. }
      assert (Hklt : (accounting_lag d s k < 0)%Q).
      { pose proof (Hnone k Hk) as Hne. unfold eligible in Hne.
        rewrite Hk in Hne. simpl in Hne.
        assert (Hltv : (ds_vtime s < pc_eligible (ds_member s k))%Q).
        { apply Qnot_le_lt. intros Hlek. apply Qle_bool_iff in Hlek.
          rewrite Hlek in Hne. discriminate Hne. }
        pose proof (qn_pos _ (proj1 (admissible_eff_bounds d s k Hadm (competing_lt _ _ _ Hk)))) as Hw.
        unfold accounting_lag.
        apply qmult_pos_neg; [ exact Hw | lra ]. }
      assert (Hkneg : ((if competing d s k then accounting_lag d s k else 0%Q) < 0)%Q).
      { rewrite Hk. exact Hklt. }
      pose proof (sum_Q_nonpos_lt _ (upto (dc_count d)) k Hle
                    (in_upto _ _ (competing_lt _ _ _ Hk)) Hkneg) as Hneg.
      unfold sum_competing_lag in Hsum. lra. }
  split; [ exact Hex | ].
  destruct Hex as [ i [ _ Hi ] ].
  destruct (a_selection_exists_whenever_a_member_is_eligible d s i Hi) as [ w Hsel ].
  intro Hnone. pose proof (select_idles_only_when_nothing_is_eligible d s Hnone i) as Hf.
  rewrite Hi in Hf. discriminate Hf.
Qed.

(* --- Cooperative served-time trace model and Stoica-Abdel-Wahab lag bound --- *)

Inductive CoopStep : Type :=
| CSlot (w : nat)
| CIdle
| CRun (r : Run)
| CJoin (j : nat)
| CLeave (j : nat).

Record CoopConfig : Type := {
  ccf_state : DState;
  ccf_rem : nat;
  ccf_past : list Stint
}.

Definition coop_start (s : DState) : CoopConfig :=
  {| ccf_state := s; ccf_rem := 0; ccf_past := nil |}.

Definition coop_exec (d : Decl) (c : CoopConfig) (st : CoopStep) : CoopConfig :=
  match st with
  | CSlot w => {| ccf_state := ccf_state c; ccf_rem := w; ccf_past := ccf_past c |}
  | CIdle =>
      {| ccf_state := ccf_state c;
         ccf_rem := 0;
         ccf_past := ccf_past c ++ cons (idle_stint d (ccf_state c) (ccf_rem c)) nil |}
  | CRun r =>
      {| ccf_state := coop_charge d (ccf_state c) (run_member r) (run_service r) (run_pending r);
         ccf_rem := ccf_rem c - (run_service r + dc_step d);
         ccf_past := ccf_past c ++ cons (stint_of_run d (ccf_state c) r)
                                      (cons (step_stint d (ccf_state c)) nil) |}
  | CJoin j =>
      {| ccf_state := coop_join d (ccf_state c) j;
         ccf_rem := ccf_rem c;
         ccf_past := ccf_past c |}
  | CLeave j =>
      {| ccf_state := coop_zero_lag_leave (ccf_state c) j;
         ccf_rem := ccf_rem c;
         ccf_past := ccf_past c |}
  end.

Definition coop_step_ok (d : Decl) (c : CoopConfig) (st : CoopStep) : Prop :=
  match st with
  | CSlot w => ccf_rem c = 0 /\ mem_nat w (dc_widths d) = true
  | CIdle => idle_permitted d (ccf_state c) (ccf_rem c) = true
  | CRun r =>
      RunConforms d (ccf_state c) (ccf_rem c) r
      /\ (run_pending r = true
          \/ (accounting_lag d (coop_charge d (ccf_state c) (run_member r) (run_service r) true)
                             (run_member r) == 0)%Q)
  | CJoin j => j < dc_count d /\ competing d (ccf_state c) j = false
  | CLeave j => competing d (ccf_state c) j = true
                /\ (accounting_lag d (ccf_state c) j == 0)%Q
  end.

Fixpoint CoopConforming (d : Decl) (c : CoopConfig) (steps : list CoopStep) : Prop :=
  match steps with
  | nil => True
  | cons st rest => coop_step_ok d c st /\ CoopConforming d (coop_exec d c st) rest
  end.

Fixpoint coop_exec_all (d : Decl) (c : CoopConfig) (steps : list CoopStep) : CoopConfig :=
  match steps with
  | nil => c
  | cons st rest => coop_exec_all d (coop_exec d c st) rest
  end.

Lemma coop_exec_all_app : forall d c l1 l2,
  coop_exec_all d c (l1 ++ l2) = coop_exec_all d (coop_exec_all d c l1) l2.
Proof.
  intros d c l1. revert c. induction l1 as [ | st r IH ]; intros c l2.
  - reflexivity.
  - simpl. exact (IH (coop_exec d c st) l2).
Qed.

Lemma coop_conforming_app : forall d c l1 l2,
  CoopConforming d c (l1 ++ l2) ->
  CoopConforming d c l1 /\ CoopConforming d (coop_exec_all d c l1) l2.
Proof.
  intros d c l1. revert c. induction l1 as [ | st r IH ]; intros c l2 H.
  - split; [ exact I | exact H ].
  - simpl in H. destruct H as [ Hs Hr ].
    destruct (IH (coop_exec d c st) l2 Hr) as [ H1 H2 ].
    split; [ split; [ exact Hs | exact H1 ] | exact H2 ].
Qed.

Lemma calls_with_service_bound : forall d s i rem gaps used sink,
  used < eff_request d s i ->
  calls_with (boundary_ok d) (dc_yield_bound d) d s i rem used gaps sink ->
  used + sum_list gaps + (match sink with None => 0 | Some k => k end)
  <= eff_coop_request d s i.
Proof.
  intros d s i rem gaps. induction gaps as [ | g rest IH ]; intros used sink Hu H.
  - destruct H.
  - destruct H as [ Hg Hrest ]. destruct rest as [ | g2 rest2 ].
    + unfold eff_coop_request. simpl. destruct sink as [ k | ].
      * destruct Hrest as [ _ Hk ]. lia.
      * lia.
    + destruct Hrest as [ Hc Hcall ].
      assert (Hlt : used + g < eff_request d s i).
      { unfold reply_with in Hc.
        destruct (Nat.ltb (used + g) (eff_request d s i)) eqn:Elt.
        - apply Nat.ltb_lt. exact Elt.
        - simpl in Hc. discriminate Hc. }
      specialize (IH (used + g) sink Hlt Hcall).
      simpl sum_list in IH |- *. lia.
Qed.

Lemma conforming_run_service_le_coop_request : forall d s rem r,
  AdmissibleCoopDecl d ->
  RunConforms d s rem r ->
  run_service r <= eff_coop_request d s (run_member r).
Proof.
  intros d s rem r Hadm [ Hsel [ _ Hc ] ].
  destruct Hsel as [ Hel _ ].
  pose proof (competing_lt d s (run_member r) (eligible_competing _ _ _ Hel)) as Hlt.
  pose proof (proj1 (proj2 (admissible_eff_bounds d s (run_member r) Hadm Hlt))) as Hreq.
  unfold run_service, sink_len.
  exact (calls_with_service_bound d s (run_member r) rem (run_gaps r) 0 (run_sink r) Hreq Hc).
Qed.

(* Trace invariants preserved across every CoopStep:
   (1) deadlines match eff_coop_request / eff_weight,
   (2) sum_competing_lag == 0,
   (3) -eff_coop_request <= accounting_lag (equivalently V <= vd_i). *)

Definition DeadlinesCoop (d : Decl) (s : DState) : Prop :=
  forall i, competing d s i = true ->
    (pc_deadline (ds_member s i) == coop_deadline_at d s i (pc_eligible (ds_member s i)))%Q.

Definition LagLowerBounded (d : Decl) (s : DState) : Prop :=
  forall i, competing d s i = true ->
    (- qn (eff_coop_request d s i) <= accounting_lag d s i)%Q.

Definition CoopInv (d : Decl) (s : DState) : Prop :=
  DeadlinesCoop d s /\ (sum_competing_lag d s == 0)%Q /\ LagLowerBounded d s.

Lemma coop_fresh_inv : forall d s,
  coop_fresh d s = true -> CoopInv d s.
Proof.
  intros d s Hf.
  pose proof Hf as Hf0.
  unfold coop_fresh in Hf. apply andb_prop in Hf. destruct Hf as [ Hv Hall ].
  apply Qeq_bool_iff in Hv.
  split; [ | split ].
  - intros i Hi. pose proof (all_of_in _ _ _ _ Hall (in_upto _ _ (competing_lt _ _ _ Hi))) as H1.
    cbv beta in H1. rewrite Hi in H1. simpl in H1. apply andb_prop in H1. destruct H1 as [ He Hd ].
    apply Qeq_bool_iff in He. apply Qeq_bool_iff in Hd.
    unfold coop_deadline_at. rewrite He, Hd. lra.
  - exact (coop_fresh_zero_sum d s Hf0).
  - intros i Hi. pose proof (all_of_in _ _ _ _ Hall (in_upto _ _ (competing_lt _ _ _ Hi))) as H1.
    cbv beta in H1. rewrite Hi in H1. simpl in H1. apply andb_prop in H1. destruct H1 as [ He _ ].
    apply Qeq_bool_iff in He. unfold accounting_lag. rewrite Hv, He.
    pose proof (qn_nonneg (eff_coop_request d s i)) as Hnn. lra.
Qed.

Lemma coop_charge_leave_preserves_zero_sum : forall d s i u,
  AdmissibleCoopDecl d ->
  competing d s i = true ->
  (sum_competing_lag d s == 0)%Q ->
  (accounting_lag d (coop_charge d s i u true) i == 0)%Q ->
  (sum_competing_lag d (coop_charge d s i u false) == 0)%Q.
Proof.
  intros d s i u Hadm Hcomp Hsum Hlag0.
  pose proof (coop_charge_preserves_zero_sum d s i u Hadm Hcomp Hsum) as Hsum1.
  set (s1 := coop_charge d s i u true) in *.
  assert (Hc1 : competing d s1 i = true).
  { unfold s1, coop_charge. rewrite competing_set_member_same; [ exact Hcomp | reflexivity | ].
    unfold competing in Hcomp. apply andb_prop in Hcomp. symmetry. exact (proj2 Hcomp). }
  pose proof (coop_zero_lag_leave_preserves_zero_sum d s1 i Hc1 Hlag0 Hsum1) as Hsum2.
  unfold sum_competing_lag in *. rewrite <- Hsum2.
  apply sum_Q_ext. intros j _.
  unfold coop_zero_lag_leave, s1, coop_charge, competing, set_member, accounting_lag, eff_weight, is_focus.
  simpl.
  destruct (Nat.eqb_spec j i) as [ Heq | Hne ].
  - subst j. rewrite Nat.eqb_refl. simpl. rewrite andb_false_r. reflexivity.
  - destruct (Nat.eqb_spec j i); [ contradiction | ].
    destruct (Nat.ltb j (dc_count d) && pc_active (ds_member s j) && pc_pending (ds_member s j));
      reflexivity.
Qed.

Lemma coop_step_preserves_inv : forall d c st,
  AdmissibleCoopDecl d ->
  CoopInv d (ccf_state c) ->
  coop_step_ok d c st ->
  CoopInv d (ccf_state (coop_exec d c st)).
Proof.
  intros d c st Hadm [ Hdl [ Hsum Hlb ] ] Hok.
  destruct st as [ w | | r | j | j ].
  - split; [ exact Hdl | split; [ exact Hsum | exact Hlb ] ].
  - split; [ exact Hdl | split; [ exact Hsum | exact Hlb ] ].
  - destruct Hok as [ Hrc Hpend ].
    set (s := ccf_state c) in *.
    set (k := run_member r) in *.
    set (u := run_service r) in *.
    pose proof (conforming_run_service_le_coop_request d s (ccf_rem c) r Hadm Hrc) as Hu.
    destruct Hrc as [ Hsel [ _ _ ] ].
    pose proof Hsel as [ Hel _ ].
    pose proof (eligible_competing _ _ _ Hel) as Hcomp.
    assert (Hcomp' : forall j,
      competing d (coop_charge d s k u (run_pending r)) j =
      if Nat.eqb j k then competing d s j && run_pending r else competing d s j).
    { intros j. unfold coop_charge, competing, set_member. simpl.
      destruct (Nat.eqb_spec j k) as [ Heq | Hne ].
      - subst j. simpl.
        unfold competing in Hcomp. apply andb_prop in Hcomp. destruct Hcomp as [ Hca Hcp ].
        fold k in Hca, Hcp. rewrite Hca, Hcp. destruct (run_pending r); reflexivity.
      - destruct (Nat.eqb_spec j k); [ contradiction | reflexivity ]. }
    split; [ | split ].
    + intros j Hj. rewrite Hcomp' in Hj.
      destruct (Nat.eqb_spec j k) as [ Heq | Hne ].
      * subst j. apply andb_prop in Hj. destruct Hj as [ _ Hrp ].
        unfold coop_charge, coop_deadline_at, set_member, advance, eff_coop_request, eff_request,
          eff_weight, is_focus. simpl. rewrite Nat.eqb_refl. reflexivity.
      * unfold coop_charge, set_member, advance, coop_deadline_at, eff_coop_request, eff_request,
          eff_weight, is_focus. simpl.
        destruct (Nat.eqb_spec j (run_member r)); [ contradiction | ].
        exact (Hdl j Hj).
    + simpl. destruct (run_pending r) eqn:Erp.
      * exact (coop_charge_preserves_zero_sum d s k u Hadm Hcomp Hsum).
      * destruct Hpend as [ Hd | Hlag0 ]; [ discriminate Hd | ].
        exact (coop_charge_leave_preserves_zero_sum d s k u Hadm Hcomp Hsum Hlag0).
    + intros j Hj. rewrite Hcomp' in Hj.
      pose proof (admissible_competing_total_weight d s k Hadm Hcomp) as [ _ HW ].
      pose proof (qn_pos _ HW) as HWpos.
      pose proof (qn_nonneg u) as Hu0.
      destruct (Nat.eqb_spec j k) as [ Heq | Hne ].
      * subst j. apply andb_prop in Hj. destruct Hj as [ _ Hrp ].
        pose proof (competing_lt d s k Hcomp) as Hlt.
        pose proof (proj1 (admissible_eff_bounds d s k Hadm Hlt)) as Hwk.
        pose proof (qn_pos _ Hwk) as Hwkpos.
        pose proof (qn_nonzero _ Hwk) as Hwknz.
        assert (Helv : (pc_eligible (ds_member s k) <= ds_vtime s)%Q).
        { unfold eligible in Hel. apply andb_prop in Hel.
          apply Qle_bool_iff. exact (proj2 Hel). }
        assert (HLpos : (0 <= accounting_lag d s k)%Q).
        { unfold accounting_lag. apply Qmult_le_0_compat; [ apply qn_nonneg | lra ]. }
        unfold accounting_lag, coop_charge, set_member, advance, eff_coop_request, eff_request,
          eff_weight. unfold is_focus. simpl.
        destruct (Nat.eqb_spec k (run_member r)) as [ _ | Hne ]; [ | exfalso; exact (Hne eq_refl) ].
        assert (Hadv : (0 <= qn (if is_focus s k then dc_focus_weight d else dc_weight d k)
                             * (qn u / qn (total_weight d s)))%Q).
        { apply Qmult_le_0_compat; [ apply qn_nonneg | ].
          unfold Qdiv. apply Qmult_le_0_compat; [ exact Hu0 | ].
          apply Qlt_le_weak. apply Qinv_lt_0_compat. exact HWpos. }
        assert (Heq_lag :
          (qn (if is_focus s k then dc_focus_weight d else dc_weight d k)
           * (ds_vtime s + qn u / qn (total_weight d s)
              - (pc_eligible (ds_member s k)
                 + qn u / qn (if is_focus s k then dc_focus_weight d else dc_weight d k)))
           == accounting_lag d s k
              + qn (if is_focus s k then dc_focus_weight d else dc_weight d k)
                * (qn u / qn (total_weight d s))
              - qn u)%Q).
        { unfold accounting_lag, eff_weight, is_focus.
          field. split; [ apply qn_nonzero; exact HW | exact Hwknz ]. }
        unfold s, k, u, is_focus in *. rewrite Heq_lag.
        pose proof (qn_le _ _ Hu) as Huq. unfold eff_coop_request, eff_request, is_focus in Huq.
        lra.
      * specialize (Hlb j Hj).
        unfold accounting_lag, coop_charge, set_member, advance, eff_coop_request, eff_request,
          eff_weight in *. unfold is_focus in *. simpl.
        destruct (Nat.eqb_spec j (run_member r)); [ contradiction | ].
        assert (Hadv : (0 <= qn (if is_focus s j then dc_focus_weight d else dc_weight d j)
                             * (qn u / qn (total_weight d s)))%Q).
        { apply Qmult_le_0_compat; [ apply qn_nonneg | ].
          unfold Qdiv. apply Qmult_le_0_compat; [ exact Hu0 | ].
          apply Qlt_le_weak. apply Qinv_lt_0_compat. exact HWpos. }
        assert (Heq_lag :
          (qn (if is_focus s j then dc_focus_weight d else dc_weight d j)
           * (ds_vtime s + qn u / qn (total_weight d s) - pc_eligible (ds_member s j))
           == qn (if is_focus s j then dc_focus_weight d else dc_weight d j)
              * (ds_vtime s - pc_eligible (ds_member s j))
              + qn (if is_focus s j then dc_focus_weight d else dc_weight d j)
                * (qn u / qn (total_weight d s)))%Q).
        { ring. }
        unfold s, k, u, is_focus in Hadv, Heq_lag, Hlb. rewrite Heq_lag. lra.
  - destruct Hok as [ Hj Hnc ].
    assert (Hcomp' : forall x,
      competing d (coop_join d (ccf_state c) j) x =
      if Nat.eqb x j then true else competing d (ccf_state c) x).
    { intros x. unfold coop_join, competing, set_member. simpl.
      destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
      - subst x. rewrite (proj2 (Nat.ltb_lt _ _) Hj). reflexivity.
      - reflexivity. }
    split; [ | split ].
    + intros x Hx. rewrite Hcomp' in Hx.
      destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
      * subst x. unfold coop_join, set_member, coop_deadline_at, eff_coop_request, eff_request,
          eff_weight, is_focus. simpl. rewrite Nat.eqb_refl. reflexivity.
      * unfold coop_join, set_member, coop_deadline_at, eff_coop_request, eff_request,
          eff_weight, is_focus. simpl.
        destruct (Nat.eqb_spec x j); [ contradiction | ].
        exact (Hdl x Hx).
    + exact (coop_join_preserves_zero_sum d (ccf_state c) j Hj Hnc Hsum).
    + intros x Hx. rewrite Hcomp' in Hx.
      destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
      * subst x. unfold accounting_lag, coop_join, set_member, eff_coop_request, eff_request,
          eff_weight. unfold is_focus. simpl. rewrite Nat.eqb_refl.
        pose proof (qn_nonneg (eff_coop_request d (ccf_state c) j)) as Hnn.
        unfold eff_coop_request, eff_request, is_focus in Hnn.
        assert (Hz : (ds_vtime (ccf_state c) - ds_vtime (ccf_state c) == 0)%Q) by ring.
        rewrite Hz, Qmult_0_r. lra.
      * specialize (Hlb x Hx).
        unfold accounting_lag, coop_join, set_member, eff_coop_request, eff_request,
          eff_weight in *. unfold is_focus in *. simpl.
        destruct (Nat.eqb_spec x j); [ contradiction | exact Hlb ].
  - destruct Hok as [ Hcj Hlj ].
    assert (Hcomp' : forall x,
      competing d (coop_zero_lag_leave (ccf_state c) j) x =
      if Nat.eqb x j then false else competing d (ccf_state c) x).
    { intros x. unfold coop_zero_lag_leave, competing, set_member. simpl.
      destruct (Nat.eqb_spec x j) as [ Heq | Hne ];
        [ subst x; simpl; rewrite andb_false_r; reflexivity
        | destruct (Nat.eqb_spec x j); [ contradiction | reflexivity ] ]. }
    split; [ | split ].
    + intros x Hx. rewrite Hcomp' in Hx.
      destruct (Nat.eqb_spec x j) as [ Heq | Hne ]; [ discriminate Hx | ].
      unfold coop_zero_lag_leave, set_member, coop_deadline_at, eff_coop_request, eff_request,
        eff_weight, is_focus. simpl.
      destruct (Nat.eqb_spec x j); [ contradiction | exact (Hdl x Hx) ].
    + exact (coop_zero_lag_leave_preserves_zero_sum d (ccf_state c) j Hcj Hlj Hsum).
    + intros x Hx. rewrite Hcomp' in Hx.
      destruct (Nat.eqb_spec x j) as [ Heq | Hne ]; [ discriminate Hx | ].
      specialize (Hlb x Hx).
      unfold accounting_lag, coop_zero_lag_leave, set_member, eff_coop_request, eff_request,
        eff_weight, is_focus in *. simpl.
      destruct (Nat.eqb_spec x j); [ contradiction | exact Hlb ].
Qed.

Lemma coop_exec_all_preserves_inv : forall d steps c,
  AdmissibleCoopDecl d ->
  CoopInv d (ccf_state c) ->
  CoopConforming d c steps ->
  CoopInv d (ccf_state (coop_exec_all d c steps)).
Proof.
  intros d steps. induction steps as [ | st rest IH ]; intros c Hadm Hinv Hconf.
  - exact Hinv.
  - simpl in Hconf. destruct Hconf as [ Hok Hrest ].
    apply IH; [ exact Hadm | exact (coop_step_preserves_inv d c st Hadm Hinv Hok) | exact Hrest ].
Qed.

Lemma coop_step_vtime_mono : forall d c st,
  AdmissibleCoopDecl d ->
  coop_step_ok d c st ->
  (ds_vtime (ccf_state c) <= ds_vtime (ccf_state (coop_exec d c st)))%Q.
Proof.
  intros d c st Hadm Hok. destruct st as [ w | | r | j | j ]; simpl; try lra.
  destruct Hok as [ [ [ Hel _ ] _ ] _ ].
  pose proof (admissible_competing_total_weight d (ccf_state c) (run_member r)
                Hadm (eligible_competing _ _ _ Hel)) as [ _ HW ].
  pose proof (qn_pos _ HW) as HWpos.
  unfold coop_charge, set_member, advance. simpl.
  assert (Hadd : (0 <= qn (run_service r) / qn (total_weight d (ccf_state c)))%Q).
  { unfold Qdiv. apply Qmult_le_0_compat; [ apply qn_nonneg | ].
    apply Qlt_le_weak, Qinv_lt_0_compat. exact HWpos. }
  lra.
Qed.

Lemma coop_exec_all_vtime_mono : forall d steps c,
  AdmissibleCoopDecl d ->
  CoopConforming d c steps ->
  (ds_vtime (ccf_state c) <= ds_vtime (ccf_state (coop_exec_all d c steps)))%Q.
Proof.
  intros d steps. induction steps as [ | st rest IH ]; intros c Hadm Hconf.
  - simpl. lra.
  - simpl in Hconf. destruct Hconf as [ Hok Hrest ].
    eapply Qle_trans; [ exact (coop_step_vtime_mono d c st Hadm Hok) | ].
    exact (IH _ Hadm Hrest).
Qed.

(* Trace splitting for the Stoica-Abdel-Wahab upper bound:
   find the last CRun step with deadline > V_final. *)
Fixpoint split_last_above (d : Decl) (c : CoopConfig) (v_final : Q) (steps : list CoopStep)
  : option (list CoopStep * CoopConfig * Run * list CoopStep) :=
  match steps with
  | nil => None
  | cons st rest =>
      match split_last_above d (coop_exec d c st) v_final rest with
      | Some (pre, c0, r0, tail) => Some (cons st pre, c0, r0, tail)
      | None =>
          match st with
          | CRun r =>
              if qltb v_final (deadline_of (ccf_state c) (run_member r))
              then Some (nil, c, r, rest)
              else None
          | _ => None
          end
      end
  end.

Lemma split_last_above_none_run : forall d steps c v_final,
  split_last_above d c v_final steps = None ->
  AdmissibleCoopDecl d ->
  CoopInv d (ccf_state c) ->
  CoopConforming d c steps ->
  (ds_vtime (ccf_state (coop_exec_all d c steps)) <= v_final)%Q ->
  (forall j, competing d (ccf_state c) j = true -> (pc_eligible (ds_member (ccf_state c) j) <= v_final)%Q) ->
  forall j, competing d (ccf_state (coop_exec_all d c steps)) j = true ->
    (pc_eligible (ds_member (ccf_state (coop_exec_all d c steps)) j) <= v_final)%Q.
Proof.
  intros d steps. induction steps as [ | st rest IH ]; intros c v_final Hnone Hadm Hinv Hconf Hvf Hbase j Hj.
  - exact (Hbase j Hj).
  - simpl in Hnone, Hconf. destruct Hconf as [ Hok Hrest ].
    destruct (split_last_above d (coop_exec d c st) v_final rest) as [ [[[pre c0] r0] tail] | ] eqn:Esub;
      [ discriminate Hnone | ].
    apply (IH (coop_exec d c st) v_final Esub Hadm (coop_step_preserves_inv d c st Hadm Hinv Hok) Hrest Hvf);
      [ | exact Hj ].
    intros x Hx.
    destruct st as [ w | | r | k | k ]; simpl in *.
    + exact (Hbase x Hx).
    + exact (Hbase x Hx).
    + destruct (qltb v_final (deadline_of (ccf_state c) (run_member r))) eqn:Elt;
        [ discriminate Hnone | ].
      assert (Hdle : (deadline_of (ccf_state c) (run_member r) <= v_final)%Q).
      { unfold qltb in Elt. apply negb_false_iff, Qle_bool_iff in Elt. exact Elt. }
      destruct Hok as [ Hrc _ ].
      pose proof (conforming_run_service_le_coop_request d (ccf_state c) (ccf_rem c) r Hadm Hrc) as Hu.
      unfold coop_charge, competing, set_member, advance in *. simpl in *.
      destruct (Nat.eqb_spec x (run_member r)) as [ Heq | Hne ].
      * subst x. simpl.
        destruct Hrc as [ [ Hel _ ] _ ].
        pose proof (eligible_competing _ _ _ Hel) as Hcr.
        destruct Hinv as [ Hdl _ ].
        pose proof (Hdl _ Hcr) as Hdlr.
        unfold coop_deadline_at, deadline_of in *.
        pose proof (qn_pos _ (proj1 (admissible_eff_bounds d (ccf_state c) (run_member r)
                                        Hadm (competing_lt _ _ _ Hcr)))) as Hwpos.
        assert (Hstep_le : (qn (run_service r) / qn (eff_weight d (ccf_state c) (run_member r))
                            <= qn (eff_coop_request d (ccf_state c) (run_member r))
                               / qn (eff_weight d (ccf_state c) (run_member r)))%Q).
        { unfold Qdiv. apply Qmult_le_compat_r; [ apply qn_le; exact Hu | ].
          apply Qlt_le_weak, Qinv_lt_0_compat. exact Hwpos. }
        lra.
      * destruct (Nat.eqb_spec x (run_member r)); [ contradiction | ].
        exact (Hbase x Hx).
    + unfold coop_join, competing, set_member in *. simpl in *.
      destruct (Nat.eqb_spec x k) as [ Heq | Hne ].
      * subst x. simpl.
        pose proof (coop_exec_all_vtime_mono d rest (coop_exec d c (CJoin k)) Hadm Hrest) as Hvm.
        simpl in Hvm, Hvf. unfold coop_join in Hvm, Hvf. simpl in Hvm, Hvf.
        eapply Qle_trans; [ exact Hvm | exact Hvf ].
      * destruct (Nat.eqb_spec x k); [ contradiction | ].
        exact (Hbase x Hx).
    + unfold coop_zero_lag_leave, competing, set_member in *. simpl in *.
      destruct (Nat.eqb_spec x k) as [ Heq | Hne ];
        [ subst x; simpl in Hx; rewrite andb_false_r in Hx; discriminate Hx | ].
      destruct (Nat.eqb_spec x k); [ contradiction | ].
      exact (Hbase x Hx).
Qed.

Lemma split_last_above_some_spec : forall d steps c v_final pre c0 r0 tail,
  split_last_above d c v_final steps = Some (pre, c0, r0, tail) ->
  steps = pre ++ cons (CRun r0) tail
  /\ c0 = coop_exec_all d c pre
  /\ (v_final < deadline_of (ccf_state c0) (run_member r0))%Q
  /\ split_last_above d (coop_exec d c0 (CRun r0)) v_final tail = None.
Proof.
  intros d steps. induction steps as [ | st rest IH ]; intros c v_final pre c0 r0 tail H.
  - discriminate H.
  - simpl in H.
    destruct (split_last_above d (coop_exec d c st) v_final rest)
      as [ [[[pre' c0'] r0'] tail'] | ] eqn:Esub.
    + injection H as Hp Hc Hr Ht. subst pre c0 r0 tail.
      destruct (IH _ _ _ _ _ _ Esub) as [ H1 [ H2 [ H3 H4 ] ] ].
      split; [ simpl; rewrite H1; reflexivity | ].
      split; [ simpl; exact H2 | ].
      split; [ exact H3 | exact H4 ].
    + destruct st as [ w | | r | j | j ]; try discriminate H.
      destruct (qltb v_final (deadline_of (ccf_state c) (run_member r))) eqn:Elt;
        [ | discriminate H ].
      injection H as Hp Hc Hr Ht. subst pre c0 r0 tail.
      split; [ reflexivity | ].
      split; [ reflexivity | ].
      split; [ apply qltb_lt; exact Elt | exact Esub ].
Qed.

Fixpoint runs_before_leave (j : nat) (tail : list CoopStep) : bool :=
  match tail with
  | nil => false
  | cons st rest =>
      match st with
      | CRun r => if Nat.eqb (run_member r) j then true else runs_before_leave j rest
      | CLeave x => if Nat.eqb x j then false else runs_before_leave j rest
      | CJoin x => if Nat.eqb x j then false else runs_before_leave j rest
      | _ => runs_before_leave j rest
      end
  end.

Fixpoint stays_competing (j : nat) (tail : list CoopStep) : bool :=
  match tail with
  | nil => true
  | cons st rest =>
      match st with
      | CRun r => if Nat.eqb (run_member r) j
                  then run_pending r && stays_competing j rest
                  else stays_competing j rest
      | CLeave x => if Nat.eqb x j then false else stays_competing j rest
      | CJoin x => if Nat.eqb x j then false else stays_competing j rest
      | _ => stays_competing j rest
      end
  end.

Lemma high_deadline_never_runs_before_leave : forall d tail c v_final j,
  split_last_above d c v_final tail = None ->
  AdmissibleCoopDecl d ->
  CoopInv d (ccf_state c) ->
  CoopConforming d c tail ->
  competing d (ccf_state c) j = true ->
  (v_final < deadline_of (ccf_state c) j)%Q ->
  runs_before_leave j tail = false
  /\ (stays_competing j tail = true ->
      competing d (ccf_state (coop_exec_all d c tail)) j = true
      /\ (v_final < deadline_of (ccf_state (coop_exec_all d c tail)) j)%Q).
Proof.
  intros d tail. induction tail as [ | st rest IH ];
    intros c v_final j Hnone Hadm Hinv Hconf Hcomp Hdl.
  - simpl. split; [ reflexivity | intros _; split; assumption ].
  - simpl in Hnone, Hconf. destruct Hconf as [ Hok Hrest ].
    destruct (split_last_above d (coop_exec d c st) v_final rest)
      as [ [[[pre c0] r0] t0] | ] eqn:Esub; [ discriminate Hnone | ].
    pose proof (coop_step_preserves_inv d c st Hadm Hinv Hok) as Hinv'.
    destruct st as [ w | | r | x | x ]; simpl.
    + exact (IH _ v_final j Esub Hadm Hinv' Hrest Hcomp Hdl).
    + exact (IH _ v_final j Esub Hadm Hinv' Hrest Hcomp Hdl).
    + destruct (qltb v_final (deadline_of (ccf_state c) (run_member r))) eqn:Elt;
        [ discriminate Hnone | ].
      assert (Hdle : (deadline_of (ccf_state c) (run_member r) <= v_final)%Q).
      { unfold qltb in Elt. apply negb_false_iff, Qle_bool_iff in Elt. exact Elt. }
      destruct (Nat.eqb_spec (run_member r) j) as [ Heq | Hne ].
      * subst j. exfalso. lra.
      * assert (Hcomp' : competing d (ccf_state (coop_exec d c (CRun r))) j = true).
        { simpl. unfold coop_charge, competing, set_member. simpl.
          destruct (Nat.eqb_spec j (run_member r)); [ symmetry in e; contradiction | exact Hcomp ]. }
        assert (Hdl' : (v_final < deadline_of (ccf_state (coop_exec d c (CRun r))) j)%Q).
        { simpl. unfold deadline_of, coop_charge, set_member. simpl.
          destruct (Nat.eqb_spec j (run_member r)); [ symmetry in e; contradiction | exact Hdl ]. }
        exact (IH _ v_final j Esub Hadm Hinv' Hrest Hcomp' Hdl').
    + destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
      * subst x. simpl in Hok. destruct Hok as [ _ Hnc ]. rewrite Hnc in Hcomp. discriminate Hcomp.
      * assert (Hcomp' : competing d (ccf_state (coop_exec d c (CJoin x))) j = true).
        { simpl. unfold coop_join, competing, set_member. simpl.
          destruct (Nat.eqb_spec j x); [ symmetry in e; contradiction | exact Hcomp ]. }
        assert (Hdl' : (v_final < deadline_of (ccf_state (coop_exec d c (CJoin x))) j)%Q).
        { simpl. unfold deadline_of, coop_join, set_member. simpl.
          destruct (Nat.eqb_spec j x); [ symmetry in e; contradiction | exact Hdl ]. }
        exact (IH _ v_final j Esub Hadm Hinv' Hrest Hcomp' Hdl').
    + destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
      * subst x. split; [ reflexivity | intro Hd; discriminate Hd ].
      * assert (Hcomp' : competing d (ccf_state (coop_exec d c (CLeave x))) j = true).
        { simpl. unfold coop_zero_lag_leave, competing, set_member. simpl.
          destruct (Nat.eqb_spec j x); [ symmetry in e; contradiction | exact Hcomp ]. }
        assert (Hdl' : (v_final < deadline_of (ccf_state (coop_exec d c (CLeave x))) j)%Q).
        { simpl. unfold deadline_of, coop_zero_lag_leave, set_member. simpl.
          destruct (Nat.eqb_spec j x); [ symmetry in e; contradiction | exact Hdl ]. }
        exact (IH _ v_final j Esub Hadm Hinv' Hrest Hcomp' Hdl').
Qed.

Definition step_U (U : nat -> bool) (st : CoopStep) : nat -> bool :=
  match st with
  | CSlot _ => U
  | CIdle => U
  | CRun r => if run_pending r then U else fun x => if Nat.eqb x (run_member r) then false else U x
  | CJoin j => fun x => if Nat.eqb x j then true else U x
  | CLeave j => fun x => if Nat.eqb x j then false else U x
  end.

Definition sum_U (d : Decl) (s : DState) (U : nat -> bool) : Q :=
  sum_Q (fun j => if U j && competing d s j then accounting_lag d s j else 0%Q) (upto (dc_count d)).

Lemma sum_U_step : forall d c st U,
  AdmissibleCoopDecl d ->
  CoopInv d (ccf_state c) ->
  coop_step_ok d c st ->
  (match st with CRun r => U (run_member r) = true | _ => True end) ->
  (sum_U d (ccf_state (coop_exec d c st)) (step_U U st) <= sum_U d (ccf_state c) U)%Q.
Proof.
  intros d c st U Hadm Hinv Hok HUk.
  destruct st as [ w | | r | j | j ]; simpl.
  - simpl. lra.
  - simpl. lra.
  - destruct Hok as [ Hrc Hpend ].
    destruct Hrc as [ [ Hel _ ] _ ].
    pose proof (eligible_competing _ _ _ Hel) as Hcomp.
    set (s := ccf_state c) in *.
    set (k := run_member r) in *.
    set (u := run_service r) in *.
    pose proof (competing_lt d s k Hcomp) as Hlt.
    pose proof (admissible_competing_total_weight d s k Hadm Hcomp) as [ _ HW ].
    pose proof (qn_pos _ HW) as HWpos.
    pose proof (qn_nonneg u) as Hu0.
    assert (Hbound :
      (sum_U d (coop_charge d s k u (run_pending r))
             (if run_pending r then U else fun x => if Nat.eqb x k then false else U x)
       <= sum_U d s U
          + sum_Q (fun x => if U x && competing d s x
                            then (qn (eff_weight d s x) * (qn u / qn (total_weight d s)))%Q
                            else 0%Q) (upto (dc_count d))
          - qn u)%Q).
    { unfold sum_U.
      destruct (run_pending r) eqn:Erp.
      - assert (Hext :
          (sum_Q (fun j => if U j && competing d (coop_charge d s k u true) j
                           then accounting_lag d (coop_charge d s k u true) j else 0%Q)
                 (upto (dc_count d))
           == sum_Q (fun j =>
                (if U j && competing d s j then accounting_lag d s j else 0%Q)
                + (if U j && competing d s j
                   then (qn (eff_weight d s j) * (qn u / qn (total_weight d s)))%Q else 0%Q)
                + (- (if Nat.eqb j k then qn u else 0%Q))) (upto (dc_count d)))%Q).
        { apply sum_Q_ext. intros x _.
          assert (Hcx : competing d (coop_charge d s k u true) x = competing d s x).
          { unfold coop_charge.
            transitivity (competing d (advance d s u) x); [ | reflexivity ].
            apply competing_set_member_same; [ reflexivity | ].
            unfold competing in Hcomp. apply andb_prop in Hcomp. symmetry. exact (proj2 Hcomp). }
          rewrite Hcx.
          destruct (Nat.eqb_spec x k) as [ Heq | Hne ].
          - subst x. rewrite HUk, Hcomp. simpl.
            unfold accounting_lag, coop_charge, set_member, advance, eff_weight, is_focus. simpl.
            rewrite Nat.eqb_refl. simpl.
            pose proof (qn_nonzero _ (proj1 (admissible_eff_bounds d s k Hadm Hlt))) as Hwknz.
            unfold eff_weight, is_focus in Hwknz.
            field. split; [ apply qn_nonzero; exact HW | exact Hwknz ].
          - destruct (U x && competing d s x) eqn:Ex.
            + unfold accounting_lag, coop_charge, set_member, advance, eff_weight, is_focus. simpl.
              destruct (Nat.eqb_spec x k); [ contradiction | simpl; ring ].
            + ring. }
        rewrite Hext.
        rewrite (sum_Q_add (fun j =>
                   ((if U j && competing d s j then accounting_lag d s j else 0%Q)
                    + (if U j && competing d s j
                       then (qn (eff_weight d s j) * (qn u / qn (total_weight d s)))%Q else 0%Q))%Q)
                           (fun j => (- (if Nat.eqb j k then qn u else 0%Q))%Q)).
        rewrite (sum_Q_add (fun j => if U j && competing d s j then accounting_lag d s j else 0%Q)).
        assert (Hk_sum :
          (sum_Q (fun j => (- (if Nat.eqb j k then qn u else 0%Q))%Q) (upto (dc_count d))
           == - qn u)%Q).
        { assert (Hneg :
            (sum_Q (fun j => (- (if Nat.eqb j k then qn u else 0%Q))%Q) (upto (dc_count d))
             == - sum_Q (fun j => if Nat.eqb j k then qn u else 0%Q) (upto (dc_count d)))%Q).
          { rewrite <- (sum_Q_scale (-(1#1)) (fun j => if Nat.eqb j k then qn u else 0%Q)).
            apply sum_Q_ext. intros j _. ring. }
          rewrite Hneg.
          pose proof (sum_Q_replace_one (fun _ => 0%Q) (upto (dc_count d)) k (qn u)
                        (upto_NoDup _) (in_upto _ _ Hlt)) as Hrep.
          rewrite (sum_Q_zero (fun _ => 0%Q) (upto (dc_count d)) (fun _ _ => Qeq_refl _)) in Hrep.
          rewrite Hrep. lra. }
        rewrite Hk_sum. lra.
      - destruct Hpend as [ Hd | Hlag0 ]; [ discriminate Hd | ].
        assert (Hext :
          (sum_Q (fun j =>
             if (if Nat.eqb j k then false else U j)
                && competing d (coop_charge d s k u false) j
             then accounting_lag d (coop_charge d s k u false) j else 0%Q) (upto (dc_count d))
           == sum_Q (fun j =>
                (if U j && competing d s j then accounting_lag d s j else 0%Q)
                + (if U j && competing d s j
                   then (qn (eff_weight d s j) * (qn u / qn (total_weight d s)))%Q else 0%Q)
                + (- (if Nat.eqb j k then qn u else 0%Q))) (upto (dc_count d)))%Q).
        { apply sum_Q_ext. intros x _.
          destruct (Nat.eqb_spec x k) as [ Heq | Hne ].
          - subst x. simpl. rewrite HUk, Hcomp. simpl.
            assert (Heq_lag :
              (accounting_lag d s k
               + qn (eff_weight d s k) * (qn u / qn (total_weight d s)) - qn u
               == accounting_lag d (coop_charge d s k u true) k)%Q).
            { unfold accounting_lag, coop_charge, set_member, advance, eff_weight, is_focus. simpl.
              rewrite Nat.eqb_refl. simpl.
              pose proof (qn_nonzero _ (proj1 (admissible_eff_bounds d s k Hadm Hlt))) as Hwknz.
              unfold eff_weight, is_focus in Hwknz.
              field. split; [ exact Hwknz | apply qn_nonzero; exact HW ]. }
            lra.
          - assert (Hcx : competing d (coop_charge d s k u false) x = competing d s x).
            { unfold coop_charge, competing, set_member. simpl.
              destruct (Nat.eqb_spec x k); [ contradiction | reflexivity ]. }
            rewrite Hcx. destruct (U x && competing d s x) eqn:Ex.
            + unfold accounting_lag, coop_charge, set_member, advance, eff_weight, is_focus. simpl.
              destruct (Nat.eqb_spec x k); [ contradiction | simpl; ring ].
            + ring. }
        rewrite Hext.
        rewrite (sum_Q_add (fun j =>
                   ((if U j && competing d s j then accounting_lag d s j else 0%Q)
                    + (if U j && competing d s j
                       then (qn (eff_weight d s j) * (qn u / qn (total_weight d s)))%Q else 0%Q))%Q)
                           (fun j => (- (if Nat.eqb j k then qn u else 0%Q))%Q)).
        rewrite (sum_Q_add (fun j => if U j && competing d s j then accounting_lag d s j else 0%Q)).
        assert (Hk_sum :
          (sum_Q (fun j => (- (if Nat.eqb j k then qn u else 0%Q))%Q) (upto (dc_count d))
           == - qn u)%Q).
        { assert (Hneg :
            (sum_Q (fun j => (- (if Nat.eqb j k then qn u else 0%Q))%Q) (upto (dc_count d))
             == - sum_Q (fun j => if Nat.eqb j k then qn u else 0%Q) (upto (dc_count d)))%Q).
          { rewrite <- (sum_Q_scale (-(1#1)) (fun j => if Nat.eqb j k then qn u else 0%Q)).
            apply sum_Q_ext. intros j _. ring. }
          rewrite Hneg.
          pose proof (sum_Q_replace_one (fun _ => 0%Q) (upto (dc_count d)) k (qn u)
                        (upto_NoDup _) (in_upto _ _ Hlt)) as Hrep.
          rewrite (sum_Q_zero (fun _ => 0%Q) (upto (dc_count d)) (fun _ _ => Qeq_refl _)) in Hrep.
          rewrite Hrep. lra. }
        rewrite Hk_sum. lra. }
    assert (Hshare_le :
      (sum_Q (fun x => if U x && competing d s x
                       then (qn (eff_weight d s x) * (qn u / qn (total_weight d s)))%Q
                       else 0%Q) (upto (dc_count d))
       <= qn u)%Q).
    { assert (Hle_terms :
        (sum_Q (fun x => if U x && competing d s x
                         then (qn (eff_weight d s x) * (qn u / qn (total_weight d s)))%Q
                         else 0%Q) (upto (dc_count d))
         <= sum_Q (fun x => (qn u / qn (total_weight d s))
                            * qn (if competing d s x then eff_weight d s x else 0))
                  (upto (dc_count d)))%Q).
      { apply sum_Q_le. intros x _.
        destruct (U x), (competing d s x).
        - simpl.
          assert (Heqm : (qn (eff_weight d s x) * (qn u / qn (total_weight d s))
                          == (qn u / qn (total_weight d s)) * qn (eff_weight d s x))%Q) by ring.
          lra.
        - change (qn 0) with 0%Q. simpl. lra.
        - simpl. apply Qmult_le_0_compat;
            [ unfold Qdiv; apply Qmult_le_0_compat;
              [ exact Hu0 | apply Qlt_le_weak, Qinv_lt_0_compat; exact HWpos ]
            | apply qn_nonneg ].
        - change (qn 0) with 0%Q. simpl. lra. }
      rewrite sum_Q_scale, <- sum_nat_qn in Hle_terms.
      change (sum_nat (fun x => if competing d s x then eff_weight d s x else 0) (upto (dc_count d)))
        with (total_weight d s) in Hle_terms.
      assert (Hequ : (qn u / qn (total_weight d s) * qn (total_weight d s) == qn u)%Q).
      { field. apply qn_nonzero. exact HW. }
      lra. }
    lra.
  - destruct Hok as [ Hj Hnc ].
    unfold sum_U.
    assert (Hext :
      (sum_Q (fun x =>
         if (if Nat.eqb x j then true else U x) && competing d (coop_join d (ccf_state c) j) x
         then accounting_lag d (coop_join d (ccf_state c) j) x else 0%Q) (upto (dc_count d))
       == sum_Q (fun x => if U x && competing d (ccf_state c) x
                          then accounting_lag d (ccf_state c) x else 0%Q) (upto (dc_count d)))%Q).
    { apply sum_Q_ext. intros x _.
      destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
      - subst x. rewrite Hnc, andb_false_r. simpl.
        destruct (competing d (coop_join d (ccf_state c) j) j);
          [ unfold accounting_lag, coop_join, set_member, eff_weight, is_focus; simpl;
            try rewrite Nat.eqb_refl; simpl; ring
          | reflexivity ].
      - unfold coop_join, competing, set_member, accounting_lag, eff_weight, is_focus. simpl.
        destruct (Nat.eqb_spec x j); [ contradiction | simpl; reflexivity ]. }
    rewrite Hext. lra.
  - destruct Hok as [ Hcj Hlj ].
    unfold sum_U.
    assert (Hext :
      (sum_Q (fun x =>
         if (if Nat.eqb x j then false else U x) && competing d (coop_zero_lag_leave (ccf_state c) j) x
         then accounting_lag d (coop_zero_lag_leave (ccf_state c) j) x else 0%Q) (upto (dc_count d))
       == sum_Q (fun x => if U x && competing d (ccf_state c) x
                          then accounting_lag d (ccf_state c) x else 0%Q) (upto (dc_count d)))%Q).
    { apply sum_Q_ext. intros x _.
      destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
      - subst x. simpl. rewrite Hcj.
        destruct (U j); simpl; [ rewrite Hlj; reflexivity | reflexivity ].
      - unfold coop_zero_lag_leave, competing, set_member, accounting_lag, eff_weight, is_focus. simpl.
        destruct (Nat.eqb_spec x j); [ contradiction | simpl; reflexivity ]. }
    rewrite Hext. lra.
Qed.

Lemma tail_U_invariant : forall d tail c v_final i U,
  split_last_above d c v_final tail = None ->
  AdmissibleCoopDecl d ->
  CoopInv d (ccf_state c) ->
  CoopConforming d c tail ->
  (ds_vtime (ccf_state (coop_exec_all d c tail)) == v_final)%Q ->
  (forall j, competing d (ccf_state c) j = true ->
     (runs_before_leave j tail = true \/ (j = i /\ stays_competing i tail = true)) ->
     U j = true) ->
  (forall j, U j = true -> competing d (ccf_state c) j = true ->
     (pc_eligible (ds_member (ccf_state c) j) <= v_final)%Q
     \/ runs_before_leave j tail = true
     \/ (j = i /\ stays_competing i tail = true)) ->
  exists U_end,
    (sum_U d (ccf_state (coop_exec_all d c tail)) U_end <= sum_U d (ccf_state c) U)%Q
    /\ (competing d (ccf_state (coop_exec_all d c tail)) i = true -> U_end i = true)
    /\ (forall j, U_end j = true -> competing d (ccf_state (coop_exec_all d c tail)) j = true ->
          j = i \/ (0 <= accounting_lag d (ccf_state (coop_exec_all d c tail)) j)%Q).
Proof.
  intros d tail. induction tail as [ | st rest IH ];
    intros c v_final i U Hnone Hadm Hinv Hconf Hvf HUreq HUok.
  - simpl in Hvf. exists U. split; [ simpl; apply Qle_refl | split ].
    + intros Hci. apply (HUreq i Hci). right. split; reflexivity.
    + intros j HUj Hcj. destruct (Nat.eqb_spec j i) as [ Heq | Hne ]; [ left; exact Heq | ].
      right. destruct (HUok j HUj Hcj) as [ Hle | [ Hrun | [ Heq _ ] ] ].
      * unfold accounting_lag. simpl. apply Qmult_le_0_compat; [ apply qn_nonneg | lra ].
      * discriminate Hrun.
      * contradiction.
  - simpl in Hnone, Hconf. destruct Hconf as [ Hok Hrest ].
    destruct (split_last_above d (coop_exec d c st) v_final rest)
      as [ [[[pre c0] r0] t0] | ] eqn:Esub; [ discriminate Hnone | ].
    pose proof (coop_step_preserves_inv d c st Hadm Hinv Hok) as Hinv'.
    assert (HUk : match st with CRun r => U (run_member r) = true | _ => True end).
    { destruct st as [ w | | r | x | x ]; try exact I.
      destruct Hok as [ [ [ Hel _ ] _ ] _ ].
      apply (HUreq (run_member r) (eligible_competing _ _ _ Hel)).
      left. simpl. rewrite Nat.eqb_refl. reflexivity. }
    pose proof (sum_U_step d c st U Hadm Hinv Hok HUk) as Hstep_le.
    assert (HUreq' : forall j, competing d (ccf_state (coop_exec d c st)) j = true ->
      (runs_before_leave j rest = true \/ (j = i /\ stays_competing i rest = true)) ->
      step_U U st j = true).
    { intros j Hj Hcond. destruct st as [ w | | r | x | x ]; simpl in *.
      - exact (HUreq j Hj Hcond).
      - exact (HUreq j Hj Hcond).
      - destruct (qltb v_final (deadline_of (ccf_state c) (run_member r))) eqn:Elt;
          [ discriminate Hnone | ].
        destruct (Nat.eqb_spec j (run_member r)) as [ Heq | Hne ].
        + subst j. destruct (run_pending r) eqn:Erp.
          * exact HUk.
          * unfold coop_charge, competing, set_member in Hj. simpl in Hj.
            rewrite Nat.eqb_refl, andb_false_r in Hj. discriminate Hj.
        + assert (HUj_eq : (if run_pending r then U else fun x => if Nat.eqb x (run_member r) then false else U x) j = U j).
          { destruct (run_pending r); [ reflexivity | ].
            destruct (Nat.eqb_spec j (run_member r)); [ contradiction | reflexivity ]. }
          rewrite HUj_eq. apply (HUreq j).
          * unfold coop_charge, competing, set_member in Hj; simpl in Hj.
            destruct (Nat.eqb_spec j (run_member r)); [ contradiction | exact Hj ].
          * destruct Hcond as [ Hr | [ Hji Hs ] ].
            -- left. destruct (Nat.eqb_spec (run_member r) j); [ symmetry in e; contradiction | exact Hr ].
            -- right. split; [ exact Hji | ].
               destruct (Nat.eqb_spec (run_member r) i);
                 [ subst j; rewrite e in Hne; contradiction | exact Hs ].
      - destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
        + subst x. try rewrite Nat.eqb_refl. reflexivity.
        + unfold coop_join, competing, set_member in Hj. simpl in Hj.
          destruct (Nat.eqb_spec j x); [ symmetry in e; contradiction | ].
          apply (HUreq j Hj).
          destruct Hcond as [ Hr | [ Hji Hs ] ];
            [ left; destruct (Nat.eqb_spec x j); [ contradiction | exact Hr ] | ].
          right. split; [ exact Hji | ].
          destruct (Nat.eqb_spec x i); [ subst x; contradiction | exact Hs ].
      - destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
        + subst x. unfold coop_zero_lag_leave, competing, set_member in Hj. simpl in Hj.
          try rewrite Nat.eqb_refl in Hj. simpl in Hj. rewrite andb_false_r in Hj. discriminate Hj.
        + unfold coop_zero_lag_leave, competing, set_member in Hj. simpl in Hj.
          destruct (Nat.eqb_spec j x); [ symmetry in e; contradiction | ].
          apply (HUreq j Hj).
          destruct Hcond as [ Hr | [ Hji Hs ] ];
            [ left; destruct (Nat.eqb_spec x j); [ contradiction | exact Hr ] | ].
          right. split; [ exact Hji | ].
          destruct (Nat.eqb_spec x i); [ subst x; contradiction | exact Hs ]. }
    assert (HUok' : forall j, step_U U st j = true ->
      competing d (ccf_state (coop_exec d c st)) j = true ->
      (pc_eligible (ds_member (ccf_state (coop_exec d c st)) j) <= v_final)%Q
      \/ runs_before_leave j rest = true
      \/ (j = i /\ stays_competing i rest = true)).
    { intros j HUj Hj. destruct st as [ w | | r | x | x ]; simpl in *.
      - exact (HUok j HUj Hj).
      - exact (HUok j HUj Hj).
      - destruct (qltb v_final (deadline_of (ccf_state c) (run_member r))) eqn:Elt;
          [ discriminate Hnone | ].
        assert (Hdle : (deadline_of (ccf_state c) (run_member r) <= v_final)%Q).
        { unfold qltb in Elt. apply negb_false_iff, Qle_bool_iff in Elt. exact Elt. }
        destruct (Nat.eqb_spec j (run_member r)) as [ Heq | Hne ].
        + subst j. left.
          destruct Hok as [ Hrc _ ].
          pose proof (conforming_run_service_le_coop_request d (ccf_state c) (ccf_rem c) r Hadm Hrc) as Hu.
          destruct Hrc as [ [ Hel _ ] _ ].
          pose proof (eligible_competing _ _ _ Hel) as Hcr.
          destruct Hinv as [ Hdl _ ].
          pose proof (Hdl _ Hcr) as Hdlr.
          unfold coop_charge, set_member, advance, coop_deadline_at, deadline_of in *. simpl in *.
          try rewrite Nat.eqb_refl. simpl.
          pose proof (qn_pos _ (proj1 (admissible_eff_bounds d (ccf_state c) (run_member r)
                                          Hadm (competing_lt _ _ _ Hcr)))) as Hwpos.
          assert (Hstep_le' : (qn (run_service r) / qn (eff_weight d (ccf_state c) (run_member r))
                               <= qn (eff_coop_request d (ccf_state c) (run_member r))
                                  / qn (eff_weight d (ccf_state c) (run_member r)))%Q).
          { unfold Qdiv. apply Qmult_le_compat_r; [ apply qn_le; exact Hu | ].
            apply Qlt_le_weak, Qinv_lt_0_compat. exact Hwpos. }
          lra.
        + assert (HUj0 : U j = true).
          { destruct (run_pending r); [ exact HUj | ].
            destruct (Nat.eqb_spec j (run_member r)); [ contradiction | exact HUj ]. }
          assert (Hj0 : competing d (ccf_state c) j = true).
          { unfold coop_charge, competing, set_member in Hj. simpl in Hj.
            destruct (Nat.eqb_spec j (run_member r)); [ contradiction | exact Hj ]. }
          unfold coop_charge, set_member, advance. simpl.
          destruct (Nat.eqb_spec j (run_member r)); [ contradiction | ].
          destruct (HUok j HUj0 Hj0) as [ Hle | [ Hrun | [ Hji Hs ] ] ].
          * left. exact Hle.
          * right. left. destruct (Nat.eqb_spec (run_member r) j) in Hrun;
              [ symmetry in e; contradiction | exact Hrun ].
          * right. right. split; [ exact Hji | ].
            destruct (Nat.eqb_spec (run_member r) i) in Hs;
              [ subst j; rewrite e in Hne; contradiction | exact Hs ].
      - destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
        + subst x. left.
          unfold coop_join, set_member. simpl. try rewrite Nat.eqb_refl. simpl.
          pose proof (coop_exec_all_vtime_mono d rest (coop_exec d c (CJoin j)) Hadm Hrest) as Hvm.
          simpl in Hvm, Hvf. unfold coop_join in Hvm, Hvf. simpl in Hvm, Hvf. lra.
        + unfold coop_join, competing, set_member in *. simpl in *.
          destruct (Nat.eqb_spec j x); [ symmetry in e; contradiction | ].
          destruct (Nat.eqb_spec x j); [ contradiction | ].
          destruct (HUok j HUj Hj) as [ Hle | [ Hrun | [ Hji Hs ] ] ].
          * left. exact Hle.
          * right. left. simpl in Hrun.
            destruct (Nat.eqb_spec x j) in Hrun; [ contradiction | exact Hrun ].
          * right. right. split; [ exact Hji | ].
            simpl in Hs. destruct (Nat.eqb_spec x i) in Hs; [ subst x; contradiction | exact Hs ].
      - destruct (Nat.eqb_spec x j) as [ Heq | Hne ].
        + subst x. try rewrite Nat.eqb_refl in HUj. discriminate HUj.
        + unfold coop_zero_lag_leave, competing, set_member in *. simpl in *.
          destruct (Nat.eqb_spec j x); [ symmetry in e; contradiction | ].
          destruct (HUok j HUj Hj) as [ Hle | [ Hrun | [ Hji Hs ] ] ].
          * left. exact Hle.
          * right. left. simpl in Hrun.
            destruct (Nat.eqb_spec x j) in Hrun; [ contradiction | exact Hrun ].
          * right. right. split; [ exact Hji | ].
            simpl in Hs. destruct (Nat.eqb_spec x i) in Hs; [ subst x; contradiction | exact Hs ]. }
    destruct (IH (coop_exec d c st) v_final i (step_U U st) Esub Hadm Hinv' Hrest Hvf HUreq' HUok')
      as [ U_end [ Hsum_end [ Hi_end Hrest_end ] ] ].
    exists U_end. split; [ simpl in *; lra | split; [ exact Hi_end | exact Hrest_end ] ].
Qed.

Lemma coop_fresh_eligible_zero : forall d s j,
  coop_fresh d s = true ->
  competing d s j = true ->
  (pc_eligible (ds_member s j) <= 0)%Q.
Proof.
  intros d s j Hf Hj. unfold coop_fresh in Hf. apply andb_prop in Hf. destruct Hf as [ _ Hall ].
  pose proof (all_of_in _ _ _ _ Hall (in_upto _ _ (competing_lt _ _ _ Hj))) as H1.
  cbv beta in H1. rewrite Hj in H1. simpl in H1. apply andb_prop in H1. destruct H1 as [ He _ ].
  apply Qeq_bool_iff in He. lra.
Qed.

(*| discharges: R-07-037g, R-11-006c |*)
Theorem cooperative_eevdf_lag_bounded :
  forall (d : Decl) (s0 : DState) (steps : list CoopStep),
    AdmissibleCoopDecl d ->
    coop_fresh d s0 = true ->
    CoopConforming d (coop_start s0) steps ->
    forall i, competing d (ccf_state (coop_exec_all d (coop_start s0) steps)) i = true ->
      (Qabs (accounting_lag d (ccf_state (coop_exec_all d (coop_start s0) steps)) i)
       <= sink_inclusive_lag_bound d)%Q.
Proof.
  intros d s0 steps Hadm Hf Hconf i Hci.
  set (c_end := coop_exec_all d (coop_start s0) steps) in *.
  set (sn := ccf_state c_end) in *.
  set (v_final := ds_vtime sn) in *.
  pose proof (coop_fresh_inv d s0 Hf) as Hinv0.
  pose proof (coop_exec_all_preserves_inv d steps (coop_start s0) Hadm Hinv0 Hconf) as Hinv_n.
  fold c_end in Hinv_n. fold sn in Hinv_n.
  destruct Hinv_n as [ Hdl_n [ Hsum_n Hlb_n ] ].
  apply Qabs_Qle_condition. split.
  - pose proof (Hlb_n i Hci) as Hlow.
    pose proof (proj2 (proj2 (admissible_eff_bounds d sn i Hadm (competing_lt _ _ _ Hci)))) as Hreq.
    apply qn_le in Hreq. unfold sink_inclusive_lag_bound. lra.
  - destruct (Qle_bool (accounting_lag d sn i) 0%Q) eqn:Eneg.
    { apply Qle_bool_iff in Eneg. unfold sink_inclusive_lag_bound.
      pose proof (qn_nonneg (max_request d + call_bound d + dc_yield_bound d)) as Hnn. lra. }
    assert (Hi_pos : (0 < accounting_lag d sn i)%Q).
    { apply Qnot_le_lt. intro Hle. apply Qle_bool_iff in Hle. rewrite Hle in Eneg. discriminate Eneg. }
    destruct (split_last_above d (coop_start s0) v_final steps)
      as [ [[[pre c0] r0] tail] | ] eqn:Esplit.
    + destruct (split_last_above_some_spec d steps (coop_start s0) v_final pre c0 r0 tail Esplit)
        as [ Happ [ Hc0 [ Hdl0 Htail_none ] ] ].
      rewrite Happ in Hconf.
      destruct (coop_conforming_app d (coop_start s0) pre (cons (CRun r0) tail) Hconf)
        as [ Hconf_pre Hconf_rest ].
      simpl in Hconf_rest. destruct Hconf_rest as [ Hokr0 Hconf_tail ].
      set (s_t0 := ccf_state c0) in *.
      set (c1 := coop_exec d c0 (CRun r0)) in *.
      rewrite <- Hc0 in Hokr0, Hconf_tail.
      change (coop_step_ok d c0 (CRun r0)) in Hokr0.
      change {| ccf_state := coop_charge d (ccf_state c0) (run_member r0) (run_service r0) (run_pending r0);
                ccf_rem := ccf_rem c0 - (run_service r0 + dc_step d);
                ccf_past := ccf_past c0 ++ cons (stint_of_run d (ccf_state c0) r0)
                                                (cons (step_stint d (ccf_state c0)) nil) |}
        with c1 in Hconf_tail.
      assert (Hinv_t0 : CoopInv d s_t0).
      { unfold s_t0. rewrite Hc0. exact (coop_exec_all_preserves_inv d pre (coop_start s0) Hadm Hinv0 Hconf_pre). }
      assert (Hinv_1 : CoopInv d (ccf_state c1)).
      { exact (coop_step_preserves_inv d c0 (CRun r0) Hadm Hinv_t0 Hokr0). }
      assert (Hc_end_eq : c_end = coop_exec_all d c1 tail).
      { unfold c_end. rewrite Happ, coop_exec_all_app, <- Hc0. reflexivity. }
      assert (Hvf_eq : (ds_vtime (ccf_state (coop_exec_all d c1 tail)) == v_final)%Q).
      { unfold v_final, sn. rewrite <- Hc_end_eq. reflexivity. }
      (* Case 2a: i was eligible at s_t0 and stayed competing through tail *)
      destruct (competing d s_t0 i && eligible d s_t0 i && stays_competing i tail) eqn:Ecase2a.
      * apply andb_prop in Ecase2a. destruct Ecase2a as [ Ece Hstays ].
        apply andb_prop in Ece. destruct Ece as [ Hci0 Heli0 ].
        destruct Hokr0 as [ Hrc0 _ ].
        destruct Hrc0 as [ [ Hel_k0 Hpref ] _ ].
        pose proof (Hpref i Heli0) as Hpk0i.
        change (ccf_state c0) with s_t0 in Hpk0i.
        assert (Hdle_k0_i : (deadline_of s_t0 (run_member r0) <= deadline_of s_t0 i)%Q).
        { unfold preferred in Hpk0i. apply orb_true_iff in Hpk0i.
          destruct Hpk0i as [ Hlt | Heq ].
          - apply Qlt_le_weak, qltb_lt. exact Hlt.
          - apply andb_prop in Heq. destruct Heq as [ Hdeq _ ]. apply Qeq_bool_iff in Hdeq. lra. }
        assert (Hdl_i0 : (v_final < deadline_of s_t0 i)%Q) by lra.
        assert (Hafter_i : competing d (ccf_state c1) i = true /\ (v_final < deadline_of (ccf_state c1) i)%Q).
        { unfold c1. simpl. unfold coop_charge, competing, deadline_of, set_member. simpl.
          destruct (Nat.eqb_spec i (run_member r0)) as [ Heq | Hne ].
          - subst i. try rewrite Nat.eqb_refl. simpl.
            destruct (run_pending r0) eqn:Erp.
            + assert (Hcomp_after : competing d s_t0 (run_member r0) && true = true).
              { rewrite Hci0. reflexivity. }
              split.
              * unfold competing in Hci0. apply andb_prop in Hci0. destruct Hci0 as [ Hca _ ].
                rewrite andb_true_r. exact Hca.
              * destruct Hinv_t0 as [ Hdl_t0 _ ].
                pose proof (Hdl_t0 (run_member r0) Hci0) as Hdlk0.
                unfold coop_deadline_at, deadline_of in *.
                assert (Hu_nn : (0 <= qn (run_service r0) / qn (eff_weight d s_t0 (run_member r0)))%Q).
                { unfold Qdiv. apply Qmult_le_0_compat; [ apply qn_nonneg | ].
                  apply Qlt_le_weak, Qinv_lt_0_compat, qn_pos.
                  exact (proj1 (admissible_eff_bounds d s_t0 (run_member r0) Hadm
                                  (competing_lt _ _ _ Hci0))). }
                unfold eff_coop_request, eff_request, eff_weight, is_focus in *.
                change (ccf_state c0) with s_t0. lra.
            + exfalso.
              assert (Hnot_comp : competing d (ccf_state c1) (run_member r0) = false).
              { unfold c1. simpl. unfold coop_charge, competing, set_member. simpl.
                try rewrite Nat.eqb_refl. simpl.
                rewrite Erp, andb_false_r. reflexivity. }
              clear -Hstays Hci Hc_end_eq Hnot_comp Hconf_tail.
              assert (Hstays_abs : forall t c_x,
                CoopConforming d c_x t ->
                stays_competing (run_member r0) t = true ->
                competing d (ccf_state c_x) (run_member r0) = false ->
                competing d (ccf_state (coop_exec_all d c_x t)) (run_member r0) = false).
              { induction t as [ | sx rx IHx ]; intros cx Hcx Hs Hnc.
                - exact Hnc.
                - simpl in Hcx, Hs. destruct Hcx as [ Hsx Hrx ].
                  destruct sx as [ w | | rx' | jx | jx ]; simpl.
                  + apply (IHx _ Hrx Hs). exact Hnc.
                  + apply (IHx _ Hrx Hs). exact Hnc.
                  + destruct (Nat.eqb_spec (run_member rx') (run_member r0)) as [ Heqx | Hnex ].
                    * exfalso. destruct Hsx as [ [ [ Hel _ ] _ ] _ ].
                      rewrite <- Heqx, (eligible_competing _ _ _ Hel) in Hnc. discriminate Hnc.
                    * apply (IHx _ Hrx Hs). unfold coop_charge, competing, set_member in *. simpl.
                      destruct (Nat.eqb_spec (run_member r0) (run_member rx')); [ symmetry in e; contradiction | simpl; exact Hnc ].
                  + destruct (Nat.eqb_spec jx (run_member r0)); [ discriminate Hs | ].
                    apply (IHx _ Hrx Hs). unfold coop_join, competing, set_member in *. simpl.
                    destruct (Nat.eqb_spec (run_member r0) jx); [ symmetry in e; contradiction | simpl; exact Hnc ].
                  + destruct (Nat.eqb_spec jx (run_member r0)); [ discriminate Hs | ].
                    apply (IHx _ Hrx Hs). unfold coop_zero_lag_leave, competing, set_member in *. simpl.
                    destruct (Nat.eqb_spec (run_member r0) jx); [ symmetry in e; contradiction | simpl; exact Hnc ]. }
              pose proof (Hstays_abs tail c1 Hconf_tail Hstays Hnot_comp) as Hfc.
              rewrite <- Hc_end_eq in Hfc. fold sn in Hfc. rewrite Hfc in Hci. discriminate Hci.
          - simpl. split; [ exact Hci0 | exact Hdl_i0 ]. }
        destruct (high_deadline_never_runs_before_leave d tail c1 v_final i Htail_none Hadm Hinv_1
                    Hconf_tail (proj1 Hafter_i) (proj2 Hafter_i)) as [ _ Hstay_res ].
        destruct (Hstay_res Hstays) as [ _ Hdl_end ].
        rewrite <- Hc_end_eq in Hdl_end. fold sn in Hdl_end.
        pose proof (Hdl_n i Hci) as Hcoop_i.
        unfold deadline_of in Hdl_end. rewrite Hcoop_i in Hdl_end.
        unfold coop_deadline_at in Hdl_end.
        pose proof (proj1 (admissible_eff_bounds d sn i Hadm (competing_lt _ _ _ Hci))) as Hwi.
        pose proof (qn_pos _ Hwi) as Hwipos.
        assert (Hlag_lt : (accounting_lag d sn i < qn (eff_coop_request d sn i))%Q).
        { unfold accounting_lag.
          assert (Heq : (qn (eff_weight d sn i) * (ds_vtime sn - pc_eligible (ds_member sn i))
                         == qn (eff_weight d sn i) * (v_final - pc_eligible (ds_member sn i)))%Q) by reflexivity.
          rewrite Heq.
          assert (Hdiff : (v_final - pc_eligible (ds_member sn i)
                           < qn (eff_coop_request d sn i) / qn (eff_weight d sn i))%Q) by lra.
          apply (Qlt_le_trans _ (qn (eff_weight d sn i)
                                 * (qn (eff_coop_request d sn i) / qn (eff_weight d sn i)))).
          - apply Qmult_lt_l; [ exact Hwipos | exact Hdiff ].
          - assert (Hcancel : (qn (eff_weight d sn i)
                               * (qn (eff_coop_request d sn i) / qn (eff_weight d sn i))
                               == qn (eff_coop_request d sn i))%Q).
            { field. apply qn_nonzero. exact Hwi. }
            lra. }
        pose proof (proj2 (proj2 (admissible_eff_bounds d sn i Hadm (competing_lt _ _ _ Hci)))) as Hreq.
        apply qn_le in Hreq. unfold sink_inclusive_lag_bound. lra.
      * (* Case 2b: U tracking over tail *)
        set (U0 := fun j => competing d s_t0 j && negb (eligible d s_t0 j)
                            && ((Nat.eqb j i && stays_competing i tail) || runs_before_leave j tail)).
        assert (HU0_le : (sum_U d s_t0 U0 <= 0)%Q).
        { unfold sum_U. rewrite <- (sum_Q_zero (fun _ => 0%Q) (upto (dc_count d)) (fun _ _ => Qeq_refl _)).
          apply sum_Q_le. intros j Hj.
          destruct (U0 j && competing d s_t0 j) eqn:Ej; [ | lra ].
          apply andb_prop in Ej. destruct Ej as [ HU0j Hcj ].
          unfold U0 in HU0j. apply andb_prop in HU0j. destruct HU0j as [ Hce _ ].
          apply andb_prop in Hce. destruct Hce as [ _ Hnel ].
          apply negb_true_iff in Hnel. unfold eligible in Hnel. rewrite Hcj in Hnel. simpl in Hnel.
          assert (Hltv : (ds_vtime s_t0 < pc_eligible (ds_member s_t0 j))%Q).
          { apply Qnot_le_lt. intro Hle. apply Qle_bool_iff in Hle. rewrite Hle in Hnel. discriminate Hnel. }
          unfold accounting_lag. apply Qlt_le_weak.
          apply qmult_pos_neg; [ apply qn_pos, (proj1 (admissible_eff_bounds d s_t0 j Hadm (upto_in _ _ Hj))) | lra ]. }
        assert (HU0_k0 : U0 (run_member r0) = false).
        { unfold U0. destruct Hokr0 as [ [ [ Helk0 _ ] _ ] _ ].
          change (ccf_state c0) with s_t0 in Helk0. rewrite Helk0. simpl.
          rewrite andb_false_r. reflexivity. }
        assert (HU1_bound : (sum_U d (ccf_state c1) U0 <= sink_inclusive_lag_bound d)%Q).
        { destruct Hokr0 as [ Hrc0 _ ].
          pose proof (conforming_run_service_le_coop_request d s_t0 (ccf_rem c0) r0 Hadm Hrc0) as Hu0.
          destruct Hrc0 as [ [ Helk0 _ ] _ ].
          pose proof (eligible_competing _ _ _ Helk0) as Hck0.
          pose proof (admissible_competing_total_weight d s_t0 (run_member r0) Hadm Hck0) as [ _ HW0 ].
          pose proof (qn_pos _ HW0) as HW0pos.
          unfold sum_U, c1. simpl.
          assert (Hstep0 :
            (sum_Q (fun j => if U0 j && competing d (coop_charge d s_t0 (run_member r0) (run_service r0) (run_pending r0)) j
                             then accounting_lag d (coop_charge d s_t0 (run_member r0) (run_service r0) (run_pending r0)) j
                             else 0%Q) (upto (dc_count d))
             <= sum_U d s_t0 U0
                + sum_Q (fun j => if U0 j && competing d s_t0 j
                                  then (qn (eff_weight d s_t0 j) * (qn (run_service r0) / qn (total_weight d s_t0)))%Q
                                  else 0%Q) (upto (dc_count d)))%Q).
          { unfold sum_U.
            rewrite <- (sum_Q_add (fun j => if U0 j && competing d s_t0 j then accounting_lag d s_t0 j else 0%Q)).
            apply sum_Q_le. intros j _.
            destruct (Nat.eqb_spec j (run_member r0)) as [ Heq | Hne ].
            - subst j. rewrite HU0_k0. simpl. lra.
            - assert (Hcj : competing d (coop_charge d s_t0 (run_member r0) (run_service r0) (run_pending r0)) j
                            = competing d s_t0 j).
              { unfold coop_charge, competing, set_member. simpl.
                destruct (Nat.eqb_spec j (run_member r0)); [ contradiction | reflexivity ]. }
              rewrite Hcj. destruct (U0 j && competing d s_t0 j); [ | lra ].
              unfold accounting_lag, coop_charge, set_member, advance, eff_weight, is_focus. simpl.
              destruct (Nat.eqb_spec j (run_member r0)); [ contradiction | ].
              simpl. assert (Heq : (qn (if is_focus s_t0 j then dc_focus_weight d else dc_weight d j)
                                     * (ds_vtime s_t0 + qn (run_service r0) / qn (total_weight d s_t0)
                                        - pc_eligible (ds_member s_t0 j))
                                    == qn (if is_focus s_t0 j then dc_focus_weight d else dc_weight d j)
                                       * (ds_vtime s_t0 - pc_eligible (ds_member s_t0 j))
                                       + qn (if is_focus s_t0 j then dc_focus_weight d else dc_weight d j)
                                         * (qn (run_service r0) / qn (total_weight d s_t0)))%Q).
              { unfold is_focus. ring. }
              unfold is_focus in Heq. lra. }
          assert (Hshare0 :
            (sum_Q (fun j => if U0 j && competing d s_t0 j
                             then (qn (eff_weight d s_t0 j) * (qn (run_service r0) / qn (total_weight d s_t0)))%Q
                             else 0%Q) (upto (dc_count d))
             <= qn (run_service r0))%Q).
          { assert (Hle_t :
              (sum_Q (fun j => if U0 j && competing d s_t0 j
                               then (qn (eff_weight d s_t0 j) * (qn (run_service r0) / qn (total_weight d s_t0)))%Q
                               else 0%Q) (upto (dc_count d))
               <= sum_Q (fun j => (qn (run_service r0) / qn (total_weight d s_t0))
                                  * qn (if competing d s_t0 j then eff_weight d s_t0 j else 0))
                        (upto (dc_count d)))%Q).
            { apply sum_Q_le. intros j _.
              destruct (U0 j), (competing d s_t0 j).
              - simpl.
                assert (Heqm : (qn (eff_weight d s_t0 j) * (qn (run_service r0) / qn (total_weight d s_t0))
                                == (qn (run_service r0) / qn (total_weight d s_t0)) * qn (eff_weight d s_t0 j))%Q) by ring.
                lra.
              - change (qn 0) with 0%Q. simpl. lra.
              - simpl. apply Qmult_le_0_compat;
                  [ unfold Qdiv; apply Qmult_le_0_compat;
                    [ apply qn_nonneg | apply Qlt_le_weak, Qinv_lt_0_compat; exact HW0pos ]
                  | apply qn_nonneg ].
              - change (qn 0) with 0%Q. simpl. lra. }
            rewrite sum_Q_scale, <- sum_nat_qn in Hle_t.
            change (sum_nat (fun j => if competing d s_t0 j then eff_weight d s_t0 j else 0) (upto (dc_count d)))
              with (total_weight d s_t0) in Hle_t.
            assert (Hequ : (qn (run_service r0) / qn (total_weight d s_t0) * qn (total_weight d s_t0)
                            == qn (run_service r0))%Q).
            { field. apply qn_nonzero. exact HW0. }
            lra. }
          pose proof (proj2 (proj2 (admissible_eff_bounds d s_t0 (run_member r0) Hadm (competing_lt _ _ _ Hck0))))
            as Hreq0.
          pose proof (qn_le _ _ (Nat.le_trans _ _ _ Hu0 Hreq0)) as Hqbound.
          unfold sink_inclusive_lag_bound. change (ccf_state c0) with s_t0. lra. }
        assert (HUreq1 : forall j, competing d (ccf_state c1) j = true ->
          (runs_before_leave j tail = true \/ (j = i /\ stays_competing i tail = true)) ->
          U0 j = true).
        { intros j Hj1 Hcond.
          assert (Hj0 : competing d s_t0 j = true).
          { unfold c1, coop_charge, competing, set_member in Hj1. simpl in Hj1.
            destruct (Nat.eqb_spec j (run_member r0)) as [ Heq | Hne ].
            - subst j. unfold competing in Hj1. apply andb_prop in Hj1. destruct Hj1 as [ Hca _ ].
              destruct Hokr0 as [ [ [ Helk0 _ ] _ ] _ ].
              change (ccf_state c0) with s_t0 in Helk0. exact (eligible_competing _ _ _ Helk0).
            - exact Hj1. }
          assert (Hnel0 : eligible d s_t0 j = false).
          { destruct (eligible d s_t0 j) eqn:Eej; [ | reflexivity ].
            exfalso.
            destruct Hokr0 as [ [ [ Helk0 Hpref ] _ ] _ ].
            pose proof (Hpref j Eej) as Hpk0j.
            change (ccf_state c0) with s_t0 in Hpk0j.
            assert (Hdle_k0_j : (deadline_of s_t0 (run_member r0) <= deadline_of s_t0 j)%Q).
            { unfold preferred in Hpk0j. apply orb_true_iff in Hpk0j.
              destruct Hpk0j as [ Hlt | Heq ].
              - apply Qlt_le_weak, qltb_lt. exact Hlt.
              - apply andb_prop in Heq. destruct Heq as [ Hdeq _ ]. apply Qeq_bool_iff in Hdeq. lra. }
            assert (Hdl_j1 : (v_final < deadline_of (ccf_state c1) j)%Q).
            { unfold c1. simpl. unfold coop_charge, deadline_of, set_member. simpl.
              destruct (Nat.eqb_spec j (run_member r0)) as [ Heq | Hne ].
              - subst j. try rewrite Nat.eqb_refl. simpl.
                destruct Hinv_t0 as [ Hdl_t0 _ ].
                pose proof (Hdl_t0 (run_member r0) Hj0) as Hdlk0.
                unfold coop_deadline_at, deadline_of in *.
                assert (Hu_nn : (0 <= qn (run_service r0) / qn (eff_weight d s_t0 (run_member r0)))%Q).
                { unfold Qdiv. apply Qmult_le_0_compat; [ apply qn_nonneg | ].
                  apply Qlt_le_weak, Qinv_lt_0_compat, qn_pos.
                  exact (proj1 (admissible_eff_bounds d s_t0 (run_member r0) Hadm
                                  (competing_lt _ _ _ Hj0))). }
                unfold eff_coop_request, eff_request, eff_weight, is_focus in *.
                change (ccf_state c0) with s_t0. lra.
              - simpl. unfold deadline_of in *. change (ccf_state c0) with s_t0. lra. }
            destruct (high_deadline_never_runs_before_leave d tail c1 v_final j Htail_none Hadm
                        Hinv_1 Hconf_tail Hj1 Hdl_j1) as [ Hnrun _ ].
            destruct Hcond as [ Hr | [ Hji Hstays ] ].
            - rewrite Hr in Hnrun. discriminate Hnrun.
            - subst j. rewrite Hj0, Eej, Hstays in Ecase2a. discriminate Ecase2a. }
          unfold U0. rewrite Hj0, Hnel0. simpl.
          destruct Hcond as [ Hr | [ Hji Hstays ] ].
          - rewrite Hr. apply orb_true_r.
          - subst j. rewrite Nat.eqb_refl, Hstays. reflexivity. }
        assert (HUok1 : forall j, U0 j = true -> competing d (ccf_state c1) j = true ->
          (pc_eligible (ds_member (ccf_state c1) j) <= v_final)%Q
          \/ runs_before_leave j tail = true
          \/ (j = i /\ stays_competing i tail = true)).
        { intros j HUj _. unfold U0 in HUj. apply andb_prop in HUj. destruct HUj as [ _ Htailj ].
          apply orb_true_iff in Htailj. destruct Htailj as [ His | Hrun ].
          - apply andb_prop in His. destruct His as [ Hji Hstays ].
            apply Nat.eqb_eq in Hji. right. right. split; assumption.
          - right. left. exact Hrun. }
        destruct (tail_U_invariant d tail c1 v_final i U0 Htail_none Hadm Hinv_1 Hconf_tail Hvf_eq
                    HUreq1 HUok1) as [ U_end [ Hsum_end [ Hi_end Hrest_end ] ] ].
        rewrite <- Hc_end_eq in Hsum_end, Hi_end, Hrest_end.
        fold sn in Hsum_end, Hi_end, Hrest_end.
        assert (Hpos_all : forall j, In j (upto (dc_count d)) ->
          (0 <= (if U_end j && competing d sn j then accounting_lag d sn j else 0%Q))%Q).
        { intros j Hj. destruct (U_end j) eqn:EUj; [ | simpl; lra ].
          destruct (competing d sn j) eqn:Ecj; [ | rewrite andb_false_r; simpl; lra ].
          simpl. destruct (Hrest_end j EUj Ecj) as [ Heq | Hge ].
          - subst j. lra.
          - exact Hge. }
        pose proof (sum_Q_nonneg_member_le
                      (fun j => if U_end j && competing d sn j then accounting_lag d sn j else 0%Q)
                      (upto (dc_count d)) i Hpos_all (in_upto _ _ (competing_lt _ _ _ Hci))) as Hle_sum.
        cbv beta in Hle_sum.
        rewrite (Hi_end Hci), Hci in Hle_sum. simpl in Hle_sum.
        fold (sum_U d sn U_end) in Hle_sum. lra.
    + (* Case 1: no step in steps has deadline > v_final *)
      assert (Hbase : forall j, competing d (ccf_state (coop_start s0)) j = true ->
        (pc_eligible (ds_member (ccf_state (coop_start s0)) j) <= v_final)%Q).
      { intros j Hj. simpl in *.
        pose proof (coop_fresh_eligible_zero d s0 j Hf Hj) as Hel0.
        pose proof (coop_exec_all_vtime_mono d steps (coop_start s0) Hadm Hconf) as Hvm.
        simpl in Hvm. unfold coop_fresh in Hf. apply andb_prop in Hf.
        destruct Hf as [ Hv0 _ ]. apply Qeq_bool_iff in Hv0.
        fold c_end in Hvm. fold sn in Hvm. fold v_final in Hvm. lra. }
      assert (Hvf_le : (ds_vtime sn <= v_final)%Q) by (unfold v_final; lra).
      pose proof (split_last_above_none_run d steps (coop_start s0) v_final Esplit Hadm Hinv0
                    Hconf Hvf_le Hbase) as Hall_le.
      fold c_end in Hall_le. fold sn in Hall_le.
      assert (Hnonneg : forall j, In j (upto (dc_count d)) ->
        (0 <= (if competing d sn j then accounting_lag d sn j else 0%Q))%Q).
      { intros j _. destruct (competing d sn j) eqn:Ej; [ | lra ].
        pose proof (Hall_le j Ej) as Hve. unfold accounting_lag.
        apply Qmult_le_0_compat; [ apply qn_nonneg | unfold v_final in Hve; lra ]. }
      pose proof (sum_Q_nonneg_zero _ _ Hnonneg Hsum_n i (in_upto _ _ (competing_lt _ _ _ Hci))) as Hiz.
      cbv beta in Hiz. rewrite Hci in Hiz.
      unfold sink_inclusive_lag_bound.
      pose proof (qn_nonneg (max_request d + call_bound d + dc_yield_bound d)) as Hnn. lra.
Qed.

(* Served-time shortfall over an interval [steps1, steps1 ++ steps2] where
   member i remains competing throughout steps2. *)
Fixpoint member_continuously_competing (i : nat) (steps : list CoopStep) : bool :=
  match steps with
  | nil => true
  | cons st rest =>
      match st with
      | CRun r => if Nat.eqb (run_member r) i
                  then run_pending r && member_continuously_competing i rest
                  else member_continuously_competing i rest
      | CLeave j => if Nat.eqb j i then false else member_continuously_competing i rest
      | CJoin j => if Nat.eqb j i then false else member_continuously_competing i rest
      | _ => member_continuously_competing i rest
      end
  end.

Lemma stint_lag_app : forall tb i l1 l2,
  (lag tb i (l1 ++ l2) == lag tb i l1 + lag tb i l2)%Q.
Proof.
  intros tb i l1 l2. induction l1 as [ | st r IH ].
  - simpl. lra.
  - simpl. rewrite IH. lra.
Qed.

Lemma coop_step_served_lag_eq_accounting : forall d c st i,
  AdmissibleCoopDecl d ->
  coop_step_ok d c st ->
  competing d (ccf_state c) i = true ->
  member_continuously_competing i (cons st nil) = true ->
  competing d (ccf_state (coop_exec d c st)) i = true
  /\ (lag ServedTime i (ccf_past (coop_exec d c st)) - lag ServedTime i (ccf_past c)
      == accounting_lag d (ccf_state (coop_exec d c st)) i
         - accounting_lag d (ccf_state c) i)%Q.
Proof.
  intros d c st i Hadm Hok Hci Hcont.
  destruct st as [ w | | r | j | j ]; simpl in *.
  - split; [ exact Hci | lra ].
  - split; [ exact Hci | rewrite stint_lag_app; simpl; unfold stint_lag; simpl; lra ].
  - destruct Hok as [ [ [ Hel _ ] _ ] _ ].
    pose proof (eligible_competing _ _ _ Hel) as Hcr.
    pose proof (admissible_competing_total_weight d (ccf_state c) (run_member r) Hadm Hcr) as [ _ HW ].
    pose proof (competing_lt d (ccf_state c) i Hci) as Hlti.
    pose proof (proj1 (admissible_eff_bounds d (ccf_state c) i Hadm Hlti)) as Hwi.
    destruct (Nat.eqb_spec (run_member r) i) as [ Heq | Hne ].
    + subst i. apply andb_prop in Hcont. destruct Hcont as [ Hrp _ ].
      assert (Hci' : competing d (coop_charge d (ccf_state c) (run_member r) (run_service r) (run_pending r)) (run_member r) = true).
      { unfold coop_charge, competing, set_member. simpl. try rewrite Nat.eqb_refl. simpl.
        rewrite Hrp. unfold competing in Hci. apply andb_prop in Hci.
        rewrite (proj1 Hci). reflexivity. }
      split; [ exact Hci' | ].
      rewrite stint_lag_app. simpl. unfold stint_lag, stint_of_run, step_stint, share_of. simpl.
      rewrite Hci. try rewrite Nat.eqb_refl. simpl.
      unfold accounting_lag, coop_charge, set_member, advance, eff_weight, is_focus. simpl.
      try rewrite Nat.eqb_refl. simpl.
      pose proof (qn_nonzero _ Hwi) as Hwnz. unfold eff_weight, is_focus in Hwnz.
      field. split; [ exact Hwnz | apply qn_nonzero; exact HW ].
    + assert (Hci' : competing d (coop_charge d (ccf_state c) (run_member r) (run_service r) (run_pending r)) i = true).
      { unfold coop_charge, competing, set_member. simpl.
        destruct (Nat.eqb_spec i (run_member r)); [ symmetry in e; contradiction | simpl; exact Hci ]. }
      split; [ exact Hci' | ].
      rewrite stint_lag_app. simpl. unfold stint_lag, stint_of_run, step_stint, share_of. simpl.
      rewrite Hci.
      destruct (Nat.eqb_spec (run_member r) i); [ contradiction | ].
      unfold accounting_lag, coop_charge, set_member, advance, eff_weight, is_focus. simpl.
      destruct (Nat.eqb_spec i (run_member r)); [ symmetry in e; contradiction | simpl; field; apply qn_nonzero; exact HW ].
  - destruct (Nat.eqb_spec j i) as [ Heq | Hne ]; [ discriminate Hcont | ].
    assert (Hci' : competing d (coop_join d (ccf_state c) j) i = true).
    { unfold coop_join, competing, set_member. simpl.
      destruct (Nat.eqb_spec i j); [ symmetry in e; contradiction | simpl; exact Hci ]. }
    split; [ exact Hci' | ].
    unfold coop_join, accounting_lag, set_member, eff_weight, is_focus. simpl.
    destruct (Nat.eqb_spec i j); [ symmetry in e; contradiction | simpl; lra ].
  - destruct (Nat.eqb_spec j i) as [ Heq | Hne ]; [ discriminate Hcont | ].
    assert (Hci' : competing d (coop_zero_lag_leave (ccf_state c) j) i = true).
    { unfold coop_zero_lag_leave, competing, set_member. simpl.
      destruct (Nat.eqb_spec i j); [ symmetry in e; contradiction | simpl; exact Hci ]. }
    split; [ exact Hci' | ].
    unfold coop_zero_lag_leave, accounting_lag, set_member, eff_weight, is_focus. simpl.
    destruct (Nat.eqb_spec i j); [ symmetry in e; contradiction | simpl; lra ].
Qed.

Lemma coop_steps_served_lag_eq_accounting : forall d steps2 c i,
  AdmissibleCoopDecl d ->
  CoopConforming d c steps2 ->
  competing d (ccf_state c) i = true ->
  member_continuously_competing i steps2 = true ->
  competing d (ccf_state (coop_exec_all d c steps2)) i = true
  /\ (lag ServedTime i (ccf_past (coop_exec_all d c steps2)) - lag ServedTime i (ccf_past c)
      == accounting_lag d (ccf_state (coop_exec_all d c steps2)) i
         - accounting_lag d (ccf_state c) i)%Q.
Proof.
  intros d steps2. induction steps2 as [ | st rest IH ]; intros c i Hadm Hconf Hci Hcont.
  - split; [ exact Hci | simpl; lra ].
  - simpl in Hconf, Hcont. destruct Hconf as [ Hok Hrest ].
    assert (Hone : member_continuously_competing i (cons st nil) = true).
    { destruct st as [ w | | r | j | j ]; simpl in *; try reflexivity.
      - destruct (Nat.eqb_spec (run_member r) i); [ | reflexivity ].
        apply andb_prop in Hcont. rewrite (proj1 Hcont). reflexivity.
      - destruct (Nat.eqb_spec j i); [ discriminate Hcont | reflexivity ].
      - destruct (Nat.eqb_spec j i); [ discriminate Hcont | reflexivity ]. }
    assert (Hrest_cont : member_continuously_competing i rest = true).
    { destruct st as [ w | | r | j | j ]; simpl in *; try exact Hcont.
      - destruct (Nat.eqb_spec (run_member r) i); [ apply andb_prop in Hcont; exact (proj2 Hcont) | exact Hcont ].
      - destruct (Nat.eqb_spec j i); [ discriminate Hcont | exact Hcont ].
      - destruct (Nat.eqb_spec j i); [ discriminate Hcont | exact Hcont ]. }
    destruct (coop_step_served_lag_eq_accounting d c st i Hadm Hok Hci Hone) as [ Hci' Hdiff1 ].
    destruct (IH (coop_exec d c st) i Hadm Hrest Hci' Hrest_cont) as [ Hci'' Hdiff2 ].
    split; [ exact Hci'' | simpl in *; lra ].
Qed.

(*| discharges: R-07-037g, R-11-006c, R-17-007b |*)
Theorem cooperative_eevdf_shortfall_bounded :
  forall (d : Decl) (s0 : DState) (steps1 steps2 : list CoopStep) (i : nat),
    AdmissibleCoopDecl d ->
    coop_fresh d s0 = true ->
    CoopConforming d (coop_start s0) (steps1 ++ steps2) ->
    competing d (ccf_state (coop_exec_all d (coop_start s0) steps1)) i = true ->
    member_continuously_competing i steps2 = true ->
    (lag ServedTime i (ccf_past (coop_exec_all d (coop_start s0) (steps1 ++ steps2)))
     - lag ServedTime i (ccf_past (coop_exec_all d (coop_start s0) steps1))
     <= 2 * sink_inclusive_lag_bound d)%Q.
Proof.
  intros d s0 steps1 steps2 i Hadm Hf Hconf Hci1 Hcont.
  destruct (coop_conforming_app d (coop_start s0) steps1 steps2 Hconf) as [ Hc1 Hc2 ].
  rewrite coop_exec_all_app.
  destruct (coop_steps_served_lag_eq_accounting d steps2 (coop_exec_all d (coop_start s0) steps1)
              i Hadm Hc2 Hci1 Hcont) as [ Hci2 Hdiff ].
  rewrite Hdiff.
  pose proof (cooperative_eevdf_lag_bounded d s0 steps1 Hadm Hf Hc1 i Hci1) as Hb1.
  pose proof (cooperative_eevdf_lag_bounded d s0 (steps1 ++ steps2) Hadm Hf Hconf i) as Hb2.
  rewrite coop_exec_all_app in Hb2. specialize (Hb2 Hci2).
  apply Qabs_Qle_condition in Hb1. apply Qabs_Qle_condition in Hb2.
  lra.
Qed.

(* =========================================================================
   S8. Required refutations (R-05-165, R-05-166) and record witnesses.
   ========================================================================= *)

(* 1. Mutant consulting another label's state refuted (~ LabelInternalUnwinding). *)
Theorem mutant_leaky_dispatch_is_refuted :
  ~ LabelInternalUnwinding (leaky_choice cx_decl) (kernel_dispatch_step cx_decl 1 true).
Proof.
  intros [ Hreads _ ].
  pose proof (Hreads leak_calm leak_busy eq_refl) as Heq.
  assert (E1 : leaky_choice cx_decl leak_calm = Some 1) by reflexivity.
  assert (E2 : leaky_choice cx_decl leak_busy = None) by reflexivity.
  rewrite E1, E2 in Heq. discriminate Heq.
Qed.

(* 2. Mutant dropping the boundary rule refuted (~ NeverCuts). *)
Theorem mutant_no_boundary_is_refuted :
  ~ NeverCuts no_boundary (dc_yield_bound cut_decl) cut_decl.
Proof.
  exact (proj2 dropping_the_boundary_rule_cuts_a_member).
Qed.

(* 3. Mutant saving vector state refuted. *)
Theorem mutant_vector_save_is_refuted :
  saving_step demo_rotation_swaps demo_succ demo_succ unzeroed_post
  /\ ~ ElasticStep demo_rotation_swaps false demo_succ demo_succ unzeroed_post
  /\ ~ RestoresNameableCsrs demo_rotation_swaps (saving_step demo_rotation_swaps).
Proof.
  exact a_kernel_saving_vector_state_is_refuted.
Qed.

(* 4. Mutants eliding vmclear across applications or on an active V/M outgoing slot refuted. *)
Definition vm_active_eliding_switch (m : Machine) : Step m :=
  StaticSlotSwitch m {| ssm_vs_off := true; ssm_xs_off := true |}.

Theorem mutant_vmclear_elision_is_refuted :
  Rotation demo_rotation_swaps demo_succ demo_succ unzeroed_post
  /\ ~ ElasticStep demo_rotation_swaps false demo_succ demo_succ unzeroed_post
  /\ vm_active_eliding_switch demo_rotation_swaps demo_succ demo_succ unzeroed_post
  /\ ~ StaticSlotSwitch demo_rotation_swaps {| ssm_vs_off := false; ssm_xs_off := true |}
         demo_succ demo_succ unzeroed_post
  /\ ~ StaticSlotSwitch demo_rotation_swaps {| ssm_vs_off := true; ssm_xs_off := false |}
         demo_succ demo_succ unzeroed_post
  /\ ~ RestoresNameableCsrs demo_rotation_swaps (vm_active_eliding_switch demo_rotation_swaps).
Proof.
  assert (Hrot : Rotation demo_rotation_swaps demo_succ demo_succ unzeroed_post)
    by exact (proj1 rotation_omits_the_zeroize_at_state_level).
  assert (Helide : vm_active_eliding_switch demo_rotation_swaps demo_succ demo_succ unzeroed_post).
  { split; [ intros r _; reflexivity | split ].
    - intros c _ Hz. destruct c; [ discriminate Hz | reflexivity ].
    - split; [ exact I | reflexivity ]. }
  split; [ exact Hrot | ].
  split; [ exact (proj2 a_rotation_across_applications_leaves_vector_state_standing) | ].
  split; [ exact Helide | ].
  split.
  - intros [ _ [ _ [ Hz _ ] ] ].
    specialize (Hz true eq_refl eq_refl). cbv in Hz. discriminate Hz.
  - split.
    + intros [ _ [ _ [ Hz _ ] ] ].
      specialize (Hz true eq_refl eq_refl). cbv in Hz. discriminate Hz.
    + intros Htot.
      specialize (Htot demo_succ demo_succ unzeroed_post Helide true eq_refl).
      cbv in Htot. discriminate Htot.
Qed.

(* 5. Mutant omitting call_bound + yield_bound from virtual deadlines refuted
      on a concrete 3-member conforming trace exceeding sink_inclusive_lag_bound. *)
Definition omitted_vd_decl : Decl := {|
  dc_count := 3;
  dc_weight := fun i => match i with 0 => 1 | 1 => 9 | _ => 90 end;
  dc_request := fun i => match i with 0 => 4 | 1 => 1 | _ => 4 end;
  dc_focus_weight := 1;
  dc_focus_request := 4;
  dc_call_interval := 2;
  dc_yield_bound := 2;
  dc_step := 5;
  dc_widths := cons 100 nil;
  dc_app := fun i => i;
  dc_machine := demo_rotation_swaps
|}.

Definition omitted_vd_start : DState := {|
  ds_vtime := 0%Q;
  ds_focus := None;
  ds_member := fun i =>
    match i with
    | 0 => fields true true 0 4
    | 1 => fields true true 0 (1 # 9)
    | _ => fields true true 0 (4 # 90)
    end
|}.

Definition omitted_run_1 : Run :=
  {| run_member := 2; run_gaps := cons 3 (cons 4 nil); run_sink := Some 2; run_pending := true |}.

Definition omitted_run_2 : Run :=
  {| run_member := 1; run_gaps := cons 1 nil; run_sink := None; run_pending := true |}.

Definition omitted_run_3 : Run :=
  {| run_member := 2; run_gaps := cons 1 nil; run_sink := None; run_pending := true |}.

Definition omitted_run_4 : Run :=
  {| run_member := 0; run_gaps := cons 4 nil; run_sink := Some 2; run_pending := true |}.

Definition omitted_run_5 : Run :=
  {| run_member := 2; run_gaps := cons 4 nil; run_sink := Some 2; run_pending := true |}.

Definition omitted_run_6 : Run :=
  {| run_member := 1; run_gaps := cons 4 nil; run_sink := Some 2; run_pending := true |}.

Definition omitted_vd_steps : list DStep :=
  cons (DSlot 100)
    (cons (DRun omitted_run_1)
      (cons (DRun omitted_run_2)
        (cons (DRun omitted_run_3)
          (cons (DRun omitted_run_4)
            (cons (DRun omitted_run_5)
              (cons (DRun omitted_run_6) nil)))))).

Lemma omitted_vd_is_admissible : AdmissibleCoopDecl omitted_vd_decl.
Proof.
  split; [ simpl; lia | ].
  split; [ | split; simpl; lia ].
  intros i Hi. destruct i as [ | [ | [ | i ] ] ]; simpl; try lia.
Qed.

Lemma omitted_vd_conforms : Conforming omitted_vd_decl (start omitted_vd_start) omitted_vd_steps.
Proof.
  split; [ split; reflexivity | ].
  split.
  - split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
    simpl. unfold call_bound. simpl.
    split; [ lia | split; [ reflexivity | split; [ lia | split; [ reflexivity | lia ] ] ] ].
  - split.
    + split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
      simpl. unfold call_bound. simpl. split; [ lia | exact I ].
    + split.
      * split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
        simpl. unfold call_bound. simpl. split; [ lia | exact I ].
      * split.
        -- split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
           simpl. unfold call_bound. simpl. split; [ lia | split; [ reflexivity | lia ] ].
        -- split.
           ++ split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
              simpl. unfold call_bound. simpl. split; [ lia | split; [ reflexivity | lia ] ].
           ++ split; [ | exact I ].
              split; [ apply select_is_the_eevdf_choice; reflexivity | split; [ reflexivity | ] ].
              simpl. unfold call_bound. simpl. split; [ lia | split; [ reflexivity | lia ] ].
Qed.

(*| discharges: R-05-165, R-05-166 |*)
Theorem mutant_omitted_coop_padding_exceeds_lag_bound :
  AdmissibleCoopDecl omitted_vd_decl
  /\ fresh omitted_vd_decl omitted_vd_start = true
  /\ Conforming omitted_vd_decl (start omitted_vd_start) omitted_vd_steps
  /\ Qeq_bool (sink_inclusive_lag_bound omitted_vd_decl) 10 = true
  /\ Qeq_bool (accounting_lag omitted_vd_decl
                 (cf_state (exec_all omitted_vd_decl (start omitted_vd_start) omitted_vd_steps)) 2)
              (101 # 10) = true
  /\ (sink_inclusive_lag_bound omitted_vd_decl
      < Qabs (accounting_lag omitted_vd_decl
                (cf_state (exec_all omitted_vd_decl (start omitted_vd_start) omitted_vd_steps)) 2))%Q.
Proof.
  split; [ exact omitted_vd_is_admissible | ].
  split; [ reflexivity | ].
  split; [ exact omitted_vd_conforms | ].
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  apply qltb_lt. reflexivity.
Qed.

(* =========================================================================
   R-05-166 record witnesses for every Record declared in ElasticDispatch.v.
   ========================================================================= *)

Definition witness_MemberDispatchFields : MemberDispatchFields :=
  {| mdf_active := true;
     mdf_pending := true;
     mdf_weight := 1;
     mdf_request := 5;
     mdf_eligible := 0%Q;
     mdf_deadline := 11%Q;
     mdf_switch_requested_pending := false |}.

Definition witness_SessionManagerFields : SessionManagerFields :=
  {| smf_vtime := 0%Q;
     smf_focus := None;
     smf_request_cell := None |}.

Definition witness_PlacedPartitionContext : PlacedPartitionContext demo_rotation_swaps :=
  {| ppc_arch := demo_succ;
     ppc_dispatch := witness_MemberDispatchFields;
     ppc_session_mgr := Some witness_SessionManagerFields |}.

Definition witness_DomainPlacedState : DomainPlacedState demo_rotation_swaps :=
  {| dps_sm_idx := 0;
     dps_contexts := fun _ => witness_PlacedPartitionContext;
     dps_current := Some 0 |}.

Definition witness_StaticSlotManifest : StaticSlotManifest :=
  {| ssm_vs_off := true;
     ssm_xs_off := true |}.

Definition witness_CoopConfig : CoopConfig :=
  coop_start omitted_vd_start.

(* R-05-163, R-05-164: closed under the global context and audited natively. *)

