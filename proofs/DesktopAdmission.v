(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   DesktopAdmission.v

   Q34e-i formalization of desktop elastic-domain admission, pool exhaustion,
   focus dispatch bounds, minimum-share preservation, and offline
   slot-geometry comparison:
   - Pool exhaustion ladder (`R-08-047d`, `R-07-037e`): guaranteed floor
     reservation at launch, unconditional protection of the focused member,
     LRU hibernation of eligible permitted background members respecting
     protected/uncheckpointable flags and the reuse barrier, and clean
     refusal at ceiling without touching fixed-tier or other-domain pools.
   - Focus dispatch bound and minimum-share admission (`R-07-037g`,
     `R-11-006c`, `R-18-004a`, `R-18-004c`): exact natural and rational
     accounting over a desktop roster with at least eight concurrently live
     members including a toolchain build member, charging weights, effective
     cooperative requests, call/yield/sink bounds, intra-slot clearing
     steps, and unusable slot tails.
   - Offline slot-geometry comparison (`R-11-022a`): holds roster, operating
     point, total domain share, reserved band, peer grants, and EEVDF weights
     and requests fixed while varying offline slot geometry; accepts a
     candidate iff focus dispatch bound and input-to-response improve
     without weakening any member or peer service bound or increasing
     admitted peak memory.

   All composition quantities are record fields (`R-05-163`, `R-05-164`),
   every declared record carries a closed `witness_<Record>` inhabitant, and
   each obligation pairs positive admission with explicit refutations
   (`R-05-165`, `R-05-166`).
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-07-037e R-07-037g R-08-047d R-11-006c
      R-11-022a R-18-004a R-18-004c
   SHA256: 883e157df17d10076978c92eb01f50c785e969d9504580898133d56632fbb5aa
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia ZArith QArith Lqa.
Require ProofSupport.
Import ProofSupport.
Import ProofSupport.Tactics.
Import ListNotations.

Local Open Scope nat_scope.

(* =========================================================================
   Helpers.
   ========================================================================= *)

Definition qn (n : nat) : Q := inject_Z (Z.of_nat n).

Definition qpos (n d : nat) : Q := Qdiv (qn n) (qn d).

Definition qlt_bool (x y : Q) : bool := negb (Qle_bool y x).

Lemma qlt_bool_lt : forall x y : Q, qlt_bool x y = true <-> (x < y)%Q.
Proof.
  intros x y. unfold qlt_bool. split; intros H.
  - apply Qnot_le_lt. intros Hle. apply Qle_bool_iff in Hle.
    rewrite Hle in H. discriminate H.
  - destruct (Qle_bool y x) eqn:E; [| reflexivity].
    apply Qle_bool_iff in E. exfalso. exact (Qlt_not_le x y H E).
Qed.

Lemma qn_inj_le : forall a b : nat, a <= b -> (qn a <= qn b)%Q.
Proof.
  intros a b H. unfold qn, Qle. simpl. lia.
Qed.

Lemma qn_inj_lt : forall a b : nat, a < b -> (qn a < qn b)%Q.
Proof.
  intros a b H. unfold qn, Qlt. simpl. lia.
Qed.

Lemma qn_pos : forall a : nat, 0 < a -> (0 < qn a)%Q.
Proof.
  intros a H. change 0%Q with (qn 0). apply qn_inj_lt. exact H.
Qed.

Lemma qdiv_pos_lt : forall a b c : nat,
  0 < c -> a < b -> (Qdiv (qn a) (qn c) < Qdiv (qn b) (qn c))%Q.
Proof.
  intros a b c Hc Hab.
  pose proof (qn_pos c Hc) as Hcp.
  pose proof (qn_inj_lt a b Hab) as Hlt.
  unfold Qdiv. apply Qmult_lt_r; [| exact Hlt].
  apply Qinv_lt_0_compat. exact Hcp.
Qed.

Lemma qdiv_pos_le : forall a b c : nat,
  0 < c -> a <= b -> (Qdiv (qn a) (qn c) <= Qdiv (qn b) (qn c))%Q.
Proof.
  intros a b c Hc Hab.
  pose proof (qn_pos c Hc) as Hcp.
  pose proof (qn_inj_le a b Hab) as Hle.
  unfold Qdiv. apply Qmult_le_compat_r; [exact Hle |].
  apply Qlt_le_weak. apply Qinv_lt_0_compat. exact Hcp.
Qed.

Lemma qdiv_denom_anti : forall a b c : nat,
  0 < b -> b <= c -> (Qdiv (qn a) (qn c) <= Qdiv (qn a) (qn b))%Q.
Proof.
  intros a b c Hb Hbc.
  pose proof (qn_pos b Hb) as Hbp.
  assert (Hc : 0 < c) by lia.
  pose proof (qn_pos c Hc) as Hcp.
  pose proof (qn_inj_le b c Hbc) as Hle.
  apply Qle_shift_div_l; [exact Hbp |].
  unfold Qdiv. rewrite <- Qmult_assoc.
  rewrite (Qmult_comm (/ qn c) (qn b)). rewrite Qmult_assoc.
  apply Qle_shift_div_r; [exact Hcp |].
  rewrite (Qmult_comm (qn a) (qn b)), (Qmult_comm (qn a) (qn c)).
  apply Qmult_le_compat_r; [exact Hle |].
  change 0%Q with (qn 0). apply qn_inj_le. lia.
Qed.

Definition ceil_div (a b : nat) : nat :=
  if Nat.eqb b 0 then 0 else (a + b - 1) / b.

Lemma ceil_div_pos : forall a b : nat, 0 < a -> 0 < b -> 1 <= ceil_div a b.
Proof.
  intros a b Ha Hb. unfold ceil_div.
  destruct (Nat.eqb b 0) eqn:Eb.
  - apply Nat.eqb_eq in Eb. lia.
  - apply Nat.div_le_lower_bound; lia.
Qed.

Lemma in_member : forall (A : Type) (x : A) (l : list A), In x l -> Member x l.
Proof.
  intros A x l. induction l as [| y r IH]; intros H; [destruct H | destruct H as [H | H]].
  - left. symmetry. exact H.
  - right. exact (IH H).
Qed.

Lemma all_of_in : forall (A : Type) (p : A -> bool) (l : list A) (x : A),
  all_of p l = true -> In x l -> p x = true.
Proof.
  intros A p l x Hall Hin. exact (all_of_member A p l x Hall (in_member A x l Hin)).
Qed.

Lemma any_of_in : forall (A : Type) (p : A -> bool) (l : list A),
  any_of p l = true -> exists x, In x l /\ p x = true.
Proof.
  intros A p l. induction l as [| y r IH]; intros H; [discriminate H |].
  simpl in H. apply orb_true_iff in H. destruct H as [H | H].
  - exists y. split; [left; reflexivity | exact H].
  - destruct (IH H) as [x [Hin Hp]]. exists x. split; [right; exact Hin | exact Hp].
Qed.

(* =========================================================================
   S1. Pool exhaustion ladder, floor reservation, focused protection,
       LRU hibernation, reuse barrier, and external-domain confinement
       (`R-08-047d`, `R-07-037e`).
   ========================================================================= *)

Record PoolMember : Type := {
  pm_id : nat;
  pm_floor : nat;
  pm_extra : nat;
  pm_sheddable : nat;
  pm_live : bool;
  pm_hibernated : bool;
  pm_consent_bearing : bool;
  pm_mid_transaction : bool;
  pm_sacrificable : bool;
  pm_checkpointable : bool;
  pm_last_focus : nat
}.

Record PoolState : Type := {
  ps_capacity : nat;
  ps_quarantined : nat;
  ps_focused : option nat;
  ps_fixed_tier : nat;
  ps_other_domain : nat;
  ps_members : list PoolMember
}.

Inductive LadderOutcome : Type :=
| OutcomeGranted
| OutcomeRefuseRequest
| OutcomeShedLocal
| OutcomeHibernated (victim_id : nat)
| OutcomeRefuseAtCeiling
| OutcomeRefuseLaunch.

Record LadderResult : Type := {
  lr_outcome : LadderOutcome;
  lr_state : PoolState
}.

Definition member_held (m : PoolMember) : nat :=
  if pm_live m then pm_floor m + pm_extra m else 0.

Definition pool_used_list (ms : list PoolMember) : nat :=
  fold_over (fun acc m => acc + member_held m) 0 ms.

Definition pool_used (ps : PoolState) : nat :=
  pool_used_list (ps_members ps).

Definition pool_committed (ps : PoolState) : nat :=
  pool_used ps + ps_quarantined ps.

Definition pool_free (ps : PoolState) : nat :=
  ps_capacity ps - pool_committed ps.

Definition pool_sheddable_list (ms : list PoolMember) : nat :=
  fold_over (fun acc m => acc + (if pm_live m then pm_sheddable m else 0)) 0 ms.

Definition pool_well_formed (ps : PoolState) : Prop :=
  pool_committed ps <= ps_capacity ps
  /\ NoDup (map pm_id (ps_members ps))
  /\ forall m, In m (ps_members ps) -> pm_sheddable m <= pm_extra m.

Fixpoint find_member (mid : nat) (ms : list PoolMember) : option PoolMember :=
  match ms with
  | nil => None
  | m :: rest => if Nat.eqb (pm_id m) mid then Some m else find_member mid rest
  end.

Fixpoint update_member_by_id
    (mid : nat) (f : PoolMember -> PoolMember) (ms : list PoolMember) : list PoolMember :=
  match ms with
  | nil => nil
  | m :: rest =>
      if Nat.eqb (pm_id m) mid
      then f m :: rest
      else m :: update_member_by_id mid f rest
  end.

Definition launch_member_fn (x : PoolMember) : PoolMember := {|
  pm_id := pm_id x;
  pm_floor := pm_floor x;
  pm_extra := 0;
  pm_sheddable := 0;
  pm_live := true;
  pm_hibernated := false;
  pm_consent_bearing := pm_consent_bearing x;
  pm_mid_transaction := pm_mid_transaction x;
  pm_sacrificable := pm_sacrificable x;
  pm_checkpointable := pm_checkpointable x;
  pm_last_focus := pm_last_focus x
|}.

Definition launch_member (ps : PoolState) (mid : nat) : LadderResult :=
  match find_member mid (ps_members ps) with
  | None => {| lr_outcome := OutcomeRefuseLaunch; lr_state := ps |}
  | Some m =>
      if negb (pm_live m) && Nat.leb (pm_floor m) (pool_free ps)
      then
        let ms' := update_member_by_id mid launch_member_fn (ps_members ps) in
        {| lr_outcome := OutcomeGranted;
           lr_state := {| ps_capacity := ps_capacity ps;
                          ps_quarantined := ps_quarantined ps;
                          ps_focused := ps_focused ps;
                          ps_fixed_tier := ps_fixed_tier ps;
                          ps_other_domain := ps_other_domain ps;
                          ps_members := ms' |} |}
      else {| lr_outcome := OutcomeRefuseLaunch; lr_state := ps |}
  end.

Definition alloc_chunk (ps : PoolState) (mid req : nat) : LadderResult :=
  match find_member mid (ps_members ps) with
  | None => {| lr_outcome := OutcomeRefuseRequest; lr_state := ps |}
  | Some m =>
      if pm_live m && Nat.leb req (pool_free ps)
      then
        let ms' := update_member_by_id mid
                     (fun x => {| pm_id := pm_id x;
                                  pm_floor := pm_floor x;
                                  pm_extra := pm_extra x + req;
                                  pm_sheddable := pm_sheddable x;
                                  pm_live := true;
                                  pm_hibernated := pm_hibernated x;
                                  pm_consent_bearing := pm_consent_bearing x;
                                  pm_mid_transaction := pm_mid_transaction x;
                                  pm_sacrificable := pm_sacrificable x;
                                  pm_checkpointable := pm_checkpointable x;
                                  pm_last_focus := pm_last_focus x |})
                     (ps_members ps) in
        {| lr_outcome := OutcomeGranted;
           lr_state := {| ps_capacity := ps_capacity ps;
                          ps_quarantined := ps_quarantined ps;
                          ps_focused := ps_focused ps;
                          ps_fixed_tier := ps_fixed_tier ps;
                          ps_other_domain := ps_other_domain ps;
                          ps_members := ms' |} |}
      else {| lr_outcome := OutcomeRefuseRequest; lr_state := ps |}
  end.

Definition shed_member (m : PoolMember) : PoolMember :=
  if pm_live m
  then {| pm_id := pm_id m;
          pm_floor := pm_floor m;
          pm_extra := pm_extra m - pm_sheddable m;
          pm_sheddable := 0;
          pm_live := true;
          pm_hibernated := pm_hibernated m;
          pm_consent_bearing := pm_consent_bearing m;
          pm_mid_transaction := pm_mid_transaction m;
          pm_sacrificable := pm_sacrificable m;
          pm_checkpointable := pm_checkpointable m;
          pm_last_focus := pm_last_focus m |}
  else m.

Definition shed_owner_local (ps : PoolState) : LadderResult :=
  let shed_amt := pool_sheddable_list (ps_members ps) in
  if Nat.eqb shed_amt 0
  then {| lr_outcome := OutcomeRefuseAtCeiling; lr_state := ps |}
  else
    let ms' := map shed_member (ps_members ps) in
    {| lr_outcome := OutcomeShedLocal;
       lr_state := {| ps_capacity := ps_capacity ps;
                      ps_quarantined := ps_quarantined ps + shed_amt;
                      ps_focused := ps_focused ps;
                      ps_fixed_tier := ps_fixed_tier ps;
                      ps_other_domain := ps_other_domain ps;
                      ps_members := ms' |} |}.

Definition is_focused_id (focused : option nat) (mid : nat) : bool :=
  match focused with
  | Some f => Nat.eqb f mid
  | None => false
  end.

Definition hibernation_eligible (focused : option nat) (m : PoolMember) : bool :=
  pm_live m
  && negb (is_focused_id focused (pm_id m))
  && negb (pm_consent_bearing m)
  && negb (pm_mid_transaction m)
  && pm_sacrificable m
  && pm_checkpointable m.

Fixpoint pick_lru_aux
    (focused : option nat) (best : option PoolMember) (ms : list PoolMember) : option PoolMember :=
  match ms with
  | nil => best
  | m :: rest =>
      if hibernation_eligible focused m
      then match best with
           | None => pick_lru_aux focused (Some m) rest
           | Some b =>
               if Nat.ltb (pm_last_focus m) (pm_last_focus b)
               then pick_lru_aux focused (Some m) rest
               else pick_lru_aux focused (Some b) rest
           end
      else pick_lru_aux focused best rest
  end.

Definition pick_lru_victim (focused : option nat) (ms : list PoolMember) : option PoolMember :=
  pick_lru_aux focused None ms.

Definition hibernate_member (m : PoolMember) : PoolMember :=
  {| pm_id := pm_id m;
     pm_floor := pm_floor m;
     pm_extra := 0;
     pm_sheddable := 0;
     pm_live := false;
     pm_hibernated := true;
     pm_consent_bearing := pm_consent_bearing m;
     pm_mid_transaction := pm_mid_transaction m;
     pm_sacrificable := pm_sacrificable m;
     pm_checkpointable := pm_checkpointable m;
     pm_last_focus := pm_last_focus m |}.

Definition hibernate_lru (ps : PoolState) : LadderResult :=
  match pick_lru_victim (ps_focused ps) (ps_members ps) with
  | None => {| lr_outcome := OutcomeRefuseAtCeiling; lr_state := ps |}
  | Some v =>
      let reclaimed := pm_floor v + pm_extra v in
      let ms' := update_member_by_id (pm_id v) hibernate_member (ps_members ps) in
      {| lr_outcome := OutcomeHibernated (pm_id v);
         lr_state := {| ps_capacity := ps_capacity ps;
                        ps_quarantined := ps_quarantined ps + reclaimed;
                        ps_focused := ps_focused ps;
                        ps_fixed_tier := ps_fixed_tier ps;
                        ps_other_domain := ps_other_domain ps;
                        ps_members := ms' |} |}
  end.

Definition complete_reuse_barrier (ps : PoolState) : PoolState :=
  {| ps_capacity := ps_capacity ps;
     ps_quarantined := 0;
     ps_focused := ps_focused ps;
     ps_fixed_tier := ps_fixed_tier ps;
     ps_other_domain := ps_other_domain ps;
     ps_members := ps_members ps |}.

Definition exhaustion_step (ps : PoolState) (mid req : nat) : LadderResult :=
  let r_alloc := alloc_chunk ps mid req in
  match lr_outcome r_alloc with
  | OutcomeGranted => r_alloc
  | _ =>
      if Nat.ltb 0 (pool_sheddable_list (ps_members ps))
      then shed_owner_local ps
      else hibernate_lru ps
  end.

Lemma fold_over_add_shift : forall (A : Type) (f : A -> nat) (l : list A) (acc : nat),
  fold_over (fun a x => a + f x) acc l = acc + fold_over (fun a x => a + f x) 0 l.
Proof.
  intros A f l. induction l as [| x rest IH]; intros acc.
  - simpl. lia.
  - simpl. rewrite (IH (acc + f x)). rewrite (IH (f x)). lia.
Qed.

Lemma pool_used_list_cons : forall m rest,
  pool_used_list (m :: rest) = member_held m + pool_used_list rest.
Proof.
  intros m rest. unfold pool_used_list. simpl.
  rewrite (fold_over_add_shift PoolMember member_held rest (member_held m)).
  lia.
Qed.

Lemma update_member_used_delta :
  forall mid f ms m,
    NoDup (map pm_id ms) ->
    find_member mid ms = Some m ->
    pool_used_list (update_member_by_id mid f ms) + member_held m =
    pool_used_list ms + member_held (f m).
Proof.
  intros mid f ms. induction ms as [| x rest IH]; intros m Hnd Hfind.
  - discriminate Hfind.
  - simpl in Hnd. inversion Hnd as [| ? ? Hnot Hin_nd]; subst.
    simpl in Hfind |- *.
    destruct (Nat.eqb (pm_id x) mid) eqn:Eq.
    + injection Hfind as Hx. subst x.
      rewrite !pool_used_list_cons. lia.
    + rewrite !pool_used_list_cons.
      pose proof (IH m Hin_nd Hfind) as Hrec. lia.
Qed.

(*| discharges: R-08-047d |*)
Theorem launch_reserves_floor :
  forall ps mid m res,
    pool_well_formed ps ->
    find_member mid (ps_members ps) = Some m ->
    pm_live m = false ->
    pm_floor m <= pool_free ps ->
    res = launch_member ps mid ->
    lr_outcome res = OutcomeGranted
    /\ pool_used (lr_state res) = pool_used ps + pm_floor m
    /\ pool_free (lr_state res) + pm_floor m = pool_free ps
    /\ pool_committed (lr_state res) <= ps_capacity (lr_state res).
Proof.
  intros ps mid m res [Hcap [Hnd Hsh]] Hfind Hdead Hfl Hres.
  unfold launch_member in Hres. rewrite Hfind, Hdead in Hres.
  assert (Hleb : Nat.leb (pm_floor m) (pool_free ps) = true) by (apply Nat.leb_le; exact Hfl).
  rewrite Hleb in Hres. simpl in Hres. subst res.
  pose proof (update_member_used_delta mid launch_member_fn (ps_members ps) m Hnd Hfind) as Hdelta.
  assert (Hhm : member_held m = 0) by (unfold member_held; rewrite Hdead; reflexivity).
  assert (Hhf : member_held (launch_member_fn m) = pm_floor m + 0) by reflexivity.
  rewrite Hhm, Hhf in Hdelta.
  unfold pool_free in *; unfold pool_committed in *; unfold pool_used in *.
  simpl in *. repeat split; try reflexivity; lia.
Qed.

(*| discharges: R-08-047d |*)
Theorem exhausted_floor_launch_refused :
  forall ps mid m,
    find_member mid (ps_members ps) = Some m ->
    pool_free ps < pm_floor m ->
    launch_member ps mid = {| lr_outcome := OutcomeRefuseLaunch; lr_state := ps |}.
Proof.
  intros ps mid m Hfind Hlt. unfold launch_member. rewrite Hfind.
  assert (Hleb : Nat.leb (pm_floor m) (pool_free ps) = false) by (apply Nat.leb_gt; exact Hlt).
  rewrite Hleb, andb_false_r. reflexivity.
Qed.

Lemma pick_lru_aux_props :
  forall focused best ms v,
    (forall b, best = Some b -> hibernation_eligible focused b = true) ->
    pick_lru_aux focused best ms = Some v ->
    hibernation_eligible focused v = true
    /\ (forall b, best = Some b -> pm_last_focus v <= pm_last_focus b)
    /\ (forall m, In m ms -> hibernation_eligible focused m = true -> pm_last_focus v <= pm_last_focus m)
    /\ ((exists b, best = Some b /\ v = b) \/ In v ms).
Proof.
  intros focused best ms. revert best.
  induction ms as [| x rest IH]; intros best v Hbest Hpick.
  - simpl in Hpick. subst best. split; [exact (Hbest v eq_refl) | split; [| split]].
    + intros b Hb. injection Hb as Hb. subst b. lia.
    + intros m [].
    + left. exists v. split; reflexivity.
  - simpl in Hpick. destruct (hibernation_eligible focused x) eqn:Ex.
    + destruct best as [b |].
      * destruct (Nat.ltb (pm_last_focus x) (pm_last_focus b)) eqn:Elt.
        -- assert (Hx : forall b', Some x = Some b' -> hibernation_eligible focused b' = true)
             by (intros b' Hb'; injection Hb' as Hb'; subst b'; exact Ex).
           destruct (IH (Some x) v Hx Hpick) as [Hv [Hxle [Hrest Hwhere]]].
           apply Nat.ltb_lt in Elt.
           split; [exact Hv | split; [| split]].
           ++ intros b' Hb'. injection Hb' as Hb'. subst b'.
              pose proof (Hxle x eq_refl) as Hvx. lia.
           ++ intros m [Hm | Hm] Em.
              ** subst m. exact (Hxle x eq_refl).
              ** exact (Hrest m Hm Em).
           ++ destruct Hwhere as [[b' [Hb' Hvb']] | Hin].
              ** injection Hb' as Hb'. subst b' v. right. left. reflexivity.
              ** right. right. exact Hin.
        -- destruct (IH (Some b) v Hbest Hpick) as [Hv [Hble [Hrest Hwhere]]].
           apply Nat.ltb_ge in Elt.
           split; [exact Hv | split; [exact Hble | split]].
           ++ intros m [Hm | Hm] Em.
              ** subst m. pose proof (Hble b eq_refl) as Hvb. lia.
              ** exact (Hrest m Hm Em).
           ++ destruct Hwhere as [[b' [Hb' Hvb']] | Hin].
              ** left. exists b'. split; assumption.
              ** right. right. exact Hin.
      * assert (Hx : forall b', Some x = Some b' -> hibernation_eligible focused b' = true)
          by (intros b' Hb'; injection Hb' as Hb'; subst b'; exact Ex).
        destruct (IH (Some x) v Hx Hpick) as [Hv [Hxle [Hrest Hwhere]]].
        split; [exact Hv | split; [intros b Hb; discriminate Hb | split]].
        -- intros m [Hm | Hm] Em.
           ++ subst m. exact (Hxle x eq_refl).
           ++ exact (Hrest m Hm Em).
        -- destruct Hwhere as [[b' [Hb' Hvb']] | Hin].
           ++ injection Hb' as Hb'. subst b' v. right. left. reflexivity.
           ++ right. right. exact Hin.
    + destruct (IH best v Hbest Hpick) as [Hv [Hble [Hrest Hwhere]]].
      split; [exact Hv | split; [exact Hble | split]].
      * intros m [Hm | Hm] Em.
        -- subst m. rewrite Ex in Em. discriminate Em.
        -- exact (Hrest m Hm Em).
      * destruct Hwhere as [Hb | Hin]; [left; exact Hb | right; right; exact Hin].
Qed.

Lemma pick_lru_victim_spec :
  forall focused ms v,
    pick_lru_victim focused ms = Some v ->
    In v ms
    /\ hibernation_eligible focused v = true
    /\ (forall m, In m ms -> hibernation_eligible focused m = true -> pm_last_focus v <= pm_last_focus m).
Proof.
  intros focused ms v H.
  assert (Hn : forall b, (None : option PoolMember) = Some b -> hibernation_eligible focused b = true)
    by (intros b Hb; discriminate Hb).
  destruct (pick_lru_aux_props focused None ms v Hn H) as [Hv [_ [Hmin Hwhere]]].
  split; [| split; assumption].
  destruct Hwhere as [[b [Hb _]] | Hin]; [discriminate Hb | exact Hin].
Qed.

(*| discharges: R-08-047d |*)
Theorem focused_and_protected_flags_prevent_hibernation :
  forall focused ms v,
    pick_lru_victim focused ms = Some v ->
    focused <> Some (pm_id v)
    /\ pm_live v = true
    /\ pm_consent_bearing v = false
    /\ pm_mid_transaction v = false
    /\ pm_sacrificable v = true
    /\ pm_checkpointable v = true.
Proof.
  intros focused ms v H.
  destruct (pick_lru_victim_spec focused ms v H) as [_ [Hel _]].
  unfold hibernation_eligible in Hel.
  rewrite !andb_true_iff in Hel.
  destruct Hel as [[[[[Hlive Hnf] Hnc] Hnt] Hsac] Hchk].
  apply negb_true_iff in Hnf.
  apply negb_true_iff in Hnc.
  apply negb_true_iff in Hnt.
  repeat split; try assumption.
  intro Heq. rewrite Heq in Hnf. simpl in Hnf.
  rewrite Nat.eqb_refl in Hnf. discriminate Hnf.
Qed.

Theorem pick_lru_victim_selects_least_recently_focused :
  forall focused ms v m,
    pick_lru_victim focused ms = Some v ->
    In m ms ->
    hibernation_eligible focused m = true ->
    pm_last_focus v <= pm_last_focus m.
Proof.
  intros focused ms v m Hpick Hin Hm.
  destruct (pick_lru_victim_spec focused ms v Hpick) as [_ [_ Hmin]].
  exact (Hmin m Hin Hm).
Qed.

Lemma find_member_unique_in : forall ms v,
  NoDup (map pm_id ms) ->
  In v ms ->
  find_member (pm_id v) ms = Some v.
Proof.
  intros ms v Hnd Hin. induction ms as [| x rest IH].
  - destruct Hin.
  - simpl in Hnd. inversion Hnd as [| ? ? Hnot Hnd_rest]; subst.
    simpl. destruct Hin as [Heq | Hin].
    + subst x. rewrite Nat.eqb_refl. reflexivity.
    + destruct (Nat.eqb (pm_id x) (pm_id v)) eqn:Eq.
      * apply Nat.eqb_eq in Eq. exfalso. apply Hnot.
        rewrite Eq. apply in_map. exact Hin.
      * exact (IH Hnd_rest Hin).
Qed.

(*| discharges: R-08-047d |*)
Theorem reuse_barrier_blocks_premature_reuse_and_restores_on_clear :
  forall ps v res,
    pool_well_formed ps ->
    pick_lru_victim (ps_focused ps) (ps_members ps) = Some v ->
    res = hibernate_lru ps ->
    lr_outcome res = OutcomeHibernated (pm_id v)
    /\ ps_quarantined (lr_state res) = ps_quarantined ps + (pm_floor v + pm_extra v)
    /\ pool_free (lr_state res) = pool_free ps
    /\ pool_free (complete_reuse_barrier (lr_state res)) =
         pool_free ps + ps_quarantined ps + (pm_floor v + pm_extra v).
Proof.
  intros ps v res [Hcap [Hnd Hsh]] Hpick Hres.
  unfold hibernate_lru in Hres. rewrite Hpick in Hres.
  subst res. simpl.
  destruct (pick_lru_victim_spec (ps_focused ps) (ps_members ps) v Hpick) as [Hin [Hel _]].
  assert (Hlive : pm_live v = true).
  { unfold hibernation_eligible in Hel. rewrite !andb_true_iff in Hel. tauto. }
  assert (Hfind : find_member (pm_id v) (ps_members ps) = Some v)
    by exact (find_member_unique_in (ps_members ps) v Hnd Hin).
  pose proof (update_member_used_delta (pm_id v) hibernate_member (ps_members ps) v Hnd Hfind)
    as Hdelta.
  assert (Hhv : member_held v = pm_floor v + pm_extra v)
    by (unfold member_held; rewrite Hlive; reflexivity).
  assert (Hhh : member_held (hibernate_member v) = 0) by reflexivity.
  rewrite Hhv, Hhh in Hdelta.
  unfold pool_free in *; unfold pool_committed in *; unfold pool_used in *.
  simpl in *. repeat split; try reflexivity; lia.
Qed.

Theorem ceiling_refuses_cleanly :
  forall ps,
    pick_lru_victim (ps_focused ps) (ps_members ps) = None ->
    hibernate_lru ps = {| lr_outcome := OutcomeRefuseAtCeiling; lr_state := ps |}.
Proof.
  intros ps Hnone. unfold hibernate_lru. rewrite Hnone. reflexivity.
Qed.

(*| discharges: R-07-037e |*)
Theorem ladder_preserves_external_domains :
  forall ps mid req,
    ps_fixed_tier (lr_state (launch_member ps mid)) = ps_fixed_tier ps
    /\ ps_other_domain (lr_state (launch_member ps mid)) = ps_other_domain ps
    /\ ps_fixed_tier (lr_state (alloc_chunk ps mid req)) = ps_fixed_tier ps
    /\ ps_other_domain (lr_state (alloc_chunk ps mid req)) = ps_other_domain ps
    /\ ps_fixed_tier (lr_state (shed_owner_local ps)) = ps_fixed_tier ps
    /\ ps_other_domain (lr_state (shed_owner_local ps)) = ps_other_domain ps
    /\ ps_fixed_tier (lr_state (hibernate_lru ps)) = ps_fixed_tier ps
    /\ ps_other_domain (lr_state (hibernate_lru ps)) = ps_other_domain ps
    /\ ps_fixed_tier (lr_state (exhaustion_step ps mid req)) = ps_fixed_tier ps
    /\ ps_other_domain (lr_state (exhaustion_step ps mid req)) = ps_other_domain ps
    /\ ps_fixed_tier (complete_reuse_barrier ps) = ps_fixed_tier ps
    /\ ps_other_domain (complete_reuse_barrier ps) = ps_other_domain ps.
Proof.
  intros ps mid req.
  unfold exhaustion_step, launch_member, alloc_chunk, shed_owner_local,
         hibernate_lru, complete_reuse_barrier.
  repeat split;
    try reflexivity;
    try (destruct (find_member mid (ps_members ps)) as [m|];
         [destruct (negb (pm_live m) && Nat.leb (pm_floor m) (pool_free ps)) |];
         reflexivity);
    try (destruct (find_member mid (ps_members ps)) as [m|];
         [destruct (pm_live m && Nat.leb req (pool_free ps)) |];
         reflexivity);
    try (destruct (Nat.eqb (pool_sheddable_list (ps_members ps)) 0); reflexivity);
    try (destruct (pick_lru_victim (ps_focused ps) (ps_members ps)); reflexivity);
    try (destruct (find_member mid (ps_members ps)) as [m|];
         [destruct (pm_live m && Nat.leb req (pool_free ps));
          [reflexivity |
           destruct (Nat.ltb 0 (pool_sheddable_list (ps_members ps)));
           [destruct (Nat.eqb (pool_sheddable_list (ps_members ps)) 0) |
            destruct (pick_lru_victim (ps_focused ps) (ps_members ps))];
           reflexivity] |
          destruct (Nat.ltb 0 (pool_sheddable_list (ps_members ps)));
          [destruct (Nat.eqb (pool_sheddable_list (ps_members ps)) 0) |
           destruct (pick_lru_victim (ps_focused ps) (ps_members ps))];
          reflexivity]).
Qed.

(* =========================================================================
   S2. Desktop roster (>=8 live members with build member), focus dispatch
       bound, and minimum-share admission (`R-07-037g`, `R-11-006c`,
       `R-18-004a`, `R-18-004c`).
   ========================================================================= *)

Record MemberSpec : Type := {
  ms_id : nat;
  ms_app : nat;
  ms_is_build : bool;
  ms_weight : nat;
  ms_request : nat;
  ms_min_share_num : nat;
  ms_min_share_den : nat;
  ms_floor_bytes : nat
}.

Record DomainSpec : Type := {
  ds_label : nat;
  ds_members : list MemberSpec;
  ds_focus_weight : nat;
  ds_focus_request : nat;
  ds_call_interval : nat;
  ds_yield_bound : nat;
  ds_rotation_cost : nat;
  ds_vmclear_cost : nat;
  ds_poll_cost : nat;
  ds_switch_cost : nat;
  ds_opp_cycles_per_ms : nat;
  ds_focus_exec_cycles : nat;
  ds_scanout_period : nat;
  ds_dispatch_deadline_ms : Q;
  ds_response_deadline_ms : Q;
  ds_peak_memory_bytes : nat
}.

Record SlotWindow : Type := {
  sw_start : nat;
  sw_width : nat
}.

Record SlotGeometry : Type := {
  sg_frame_period : nat;
  sg_reserved_band : nat;
  sg_peer_width : nat;
  sg_peer_service_floor : nat;
  sg_domain_slots : list SlotWindow;
  sg_admitted_member_service_floor : nat;
  sg_peak_memory_bytes : nat
}.

Record GeometryComparison : Type := {
  gc_accepted : bool;
  gc_base_dispatch_ms : Q;
  gc_cand_dispatch_ms : Q;
  gc_base_response_ms : Q;
  gc_cand_response_ms : Q;
  gc_base_usable : nat;
  gc_cand_usable : nat
}.

Definition call_bound (dom : DomainSpec) : nat :=
  ds_call_interval dom + ds_yield_bound dom.

Definition intra_step_cost (dom : DomainSpec) : nat :=
  ds_rotation_cost dom + ds_vmclear_cost dom.

Definition boundary_need (dom : DomainSpec) : nat :=
  call_bound dom + ds_yield_bound dom + intra_step_cost dom.

Definition slot_entry_overhead (dom : DomainSpec) : nat :=
  ds_switch_cost dom + ds_vmclear_cost dom + ds_poll_cost dom.

Definition unusable_tail_bound (dom : DomainSpec) : nat :=
  boundary_need dom - 1.

Definition min_usable_slot_width (dom : DomainSpec) : nat :=
  slot_entry_overhead dom + boundary_need dom.

Definition slot_usable_cycles (dom : DomainSpec) (w : nat) : nat :=
  if Nat.leb (min_usable_slot_width dom) w
  then w - slot_entry_overhead dom - unusable_tail_bound dom
  else 0.

Definition total_domain_width (sg : SlotGeometry) : nat :=
  fold_over (fun acc s => acc + sw_width s) 0 (sg_domain_slots sg).

Definition total_usable_cycles (dom : DomainSpec) (sg : SlotGeometry) : nat :=
  fold_over (fun acc s => acc + slot_usable_cycles dom (sw_width s)) 0 (sg_domain_slots sg).

Fixpoint min_slot_usable_aux (dom : DomainSpec) (cur : nat) (slots : list SlotWindow) : nat :=
  match slots with
  | nil => cur
  | s :: rest => min_slot_usable_aux dom (Nat.min cur (slot_usable_cycles dom (sw_width s))) rest
  end.

Definition min_slot_usable (dom : DomainSpec) (sg : SlotGeometry) : nat :=
  match sg_domain_slots sg with
  | nil => 0
  | s :: rest => min_slot_usable_aux dom (slot_usable_cycles dom (sw_width s)) rest
  end.

Fixpoint slots_ordered_from (pos limit : nat) (slots : list SlotWindow) : bool :=
  match slots with
  | nil => Nat.leb pos limit
  | s :: rest =>
      Nat.ltb 0 (sw_width s)
      && Nat.leb pos (sw_start s)
      && slots_ordered_from (sw_start s + sw_width s) limit rest
  end.

Definition slots_ordered_nonoverlapping (P : nat) (slots : list SlotWindow) : bool :=
  slots_ordered_from 0 P slots.

Fixpoint slot_gaps_aux (prev_end first_start P : nat) (slots : list SlotWindow) : list nat :=
  match slots with
  | nil => ((P - prev_end) + first_start) :: nil
  | s :: rest => (sw_start s - prev_end) :: slot_gaps_aux (sw_start s + sw_width s) first_start P rest
  end.

Definition slot_gaps (P : nat) (slots : list SlotWindow) : list nat :=
  match slots with
  | nil => P :: nil
  | s :: rest => slot_gaps_aux (sw_start s + sw_width s) (sw_start s) P rest
  end.

Definition max_slot_gap (sg : SlotGeometry) : nat :=
  fold_over Nat.max 0 (slot_gaps (sg_frame_period sg) (sg_domain_slots sg)).

Definition eff_request_member (dom : DomainSpec) (m : MemberSpec) : nat :=
  ms_request m + call_bound dom + ds_yield_bound dom.

Definition eff_request_focus (dom : DomainSpec) : nat :=
  ds_focus_request dom + call_bound dom + ds_yield_bound dom.

Definition dispatches_ahead (dom : DomainSpec) (m : MemberSpec) : nat :=
  1 + (ms_weight m * eff_request_focus dom) / (ds_focus_weight dom * eff_request_member dom m).

Definition member_eevdf_cost (dom : DomainSpec) (m : MemberSpec) : nat :=
  dispatches_ahead dom m * (eff_request_member dom m + intra_step_cost dom).

Definition eevdf_interference_for_focus (dom : DomainSpec) (focus_id : nat) (live : list MemberSpec) : nat :=
  fold_over (fun acc m =>
    if Nat.eqb (ms_id m) focus_id then acc else acc + member_eevdf_cost dom m)
    0 live.

Definition worst_eevdf_interference (dom : DomainSpec) : nat :=
  fold_over (fun acc f =>
    Nat.max acc (eevdf_interference_for_focus dom (ms_id f) (ds_members dom)))
    0 (ds_members dom).

Definition focus_work_cycles (dom : DomainSpec) : nat :=
  boundary_need dom + worst_eevdf_interference dom.

Definition focus_dispatch_cycles (dom : DomainSpec) (sg : SlotGeometry) : nat :=
  let u := min_slot_usable dom sg in
  if Nat.eqb u 0 then 0
  else
    let k := Nat.max 1 (ceil_div (focus_work_cycles dom) u) in
    unusable_tail_bound dom
    + k * (max_slot_gap sg + slot_entry_overhead dom)
    + (k - 1) * unusable_tail_bound dom
    + focus_work_cycles dom.

Definition exec_extra_cycles (dom : DomainSpec) (sg : SlotGeometry) : nat :=
  let u := min_slot_usable dom sg in
  if Nat.eqb u 0 then 0
  else if Nat.eqb (ds_focus_exec_cycles dom) 0 then 0
  else
    let k_disp := Nat.max 1 (ceil_div (focus_work_cycles dom) u) in
    let k_tot := Nat.max 1 (ceil_div (focus_work_cycles dom + ds_focus_exec_cycles dom) u) in
    (k_tot - k_disp) * (max_slot_gap sg + slot_entry_overhead dom + unusable_tail_bound dom)
    + ds_focus_exec_cycles dom.

Definition input_to_response_cycles (dom : DomainSpec) (sg : SlotGeometry) : nat :=
  focus_dispatch_cycles dom sg + exec_extra_cycles dom sg + ds_scanout_period dom.

Definition cycles_to_ms (dom : DomainSpec) (c : nat) : Q :=
  Qdiv (qn c) (qn (ds_opp_cycles_per_ms dom)).

Definition focus_dispatch_ms (dom : DomainSpec) (sg : SlotGeometry) : Q :=
  cycles_to_ms dom (focus_dispatch_cycles dom sg).

Definition input_to_response_ms (dom : DomainSpec) (sg : SlotGeometry) : Q :=
  cycles_to_ms dom (input_to_response_cycles dom sg).

Definition focus_weight_for (dom : DomainSpec) (focus_id : option nat) (m : MemberSpec) : nat :=
  match focus_id with
  | Some f => if Nat.eqb (ms_id m) f then ds_focus_weight dom else ms_weight m
  | None => ms_weight m
  end.

Definition total_weight_subset (dom : DomainSpec) (focus_id : option nat) (live : list MemberSpec) : nat :=
  fold_over (fun acc m => acc + focus_weight_for dom focus_id m) 0 live.

Definition worst_total_weight_against (dom : DomainSpec) (mid : nat) : nat :=
  let base_w := total_weight_subset dom None (ds_members dom) in
  fold_over (fun acc f =>
    if Nat.eqb (ms_id f) mid then acc
    else Nat.max acc (total_weight_subset dom (Some (ms_id f)) (ds_members dom)))
    base_w (ds_members dom).

Definition member_min_share (m : MemberSpec) : Q :=
  qpos (ms_min_share_num m) (ms_min_share_den m).

Definition member_eevdf_share (dom : DomainSpec) (m : MemberSpec) : Q :=
  qpos (ms_weight m) (worst_total_weight_against dom (ms_id m)).

Definition domain_net_share (dom : DomainSpec) (sg : SlotGeometry) : Q :=
  qpos (total_usable_cycles dom sg) (sg_frame_period sg).

Definition member_step_efficiency (dom : DomainSpec) (m : MemberSpec) : Q :=
  qpos (eff_request_member dom m) (eff_request_member dom m + intra_step_cost dom).

Definition member_net_share (dom : DomainSpec) (sg : SlotGeometry) (m : MemberSpec) : Q :=
  Qmult (member_eevdf_share dom m)
        (Qmult (domain_net_share dom sg) (member_step_efficiency dom m)).

Definition member_spec_valid (m : MemberSpec) : bool :=
  Nat.ltb 0 (ms_weight m)
  && Nat.ltb 0 (ms_request m)
  && Nat.ltb 0 (ms_min_share_den m).

Fixpoint distinct_member_ids (ms : list MemberSpec) : bool :=
  match ms with
  | nil => true
  | m :: rest =>
      negb (any_of (fun x => Nat.eqb (ms_id x) (ms_id m)) rest)
      && distinct_member_ids rest
  end.

Definition domain_admits (dom : DomainSpec) (sg : SlotGeometry) : bool :=
  Nat.leb 8 (length (ds_members dom))
  && any_of ms_is_build (ds_members dom)
  && all_of member_spec_valid (ds_members dom)
  && distinct_member_ids (ds_members dom)
  && Nat.ltb 0 (ds_focus_weight dom)
  && Nat.ltb 0 (ds_focus_request dom)
  && Nat.ltb 0 (ds_opp_cycles_per_ms dom)
  && Nat.ltb 0 (sg_frame_period sg)
  && negb (match sg_domain_slots sg with nil => true | _ => false end)
  && slots_ordered_nonoverlapping (sg_frame_period sg) (sg_domain_slots sg)
  && Nat.leb (total_domain_width sg + sg_reserved_band sg + sg_peer_width sg) (sg_frame_period sg)
  && all_of (fun s => Nat.leb (min_usable_slot_width dom) (sw_width s)) (sg_domain_slots sg)
  && all_of (fun m => Qle_bool (member_min_share m) (member_net_share dom sg m)) (ds_members dom)
  && Nat.leb (sg_admitted_member_service_floor sg) (total_usable_cycles dom sg)
  && Nat.ltb 0 (min_slot_usable dom sg)
  && Qle_bool (focus_dispatch_ms dom sg) (ds_dispatch_deadline_ms dom)
  && Qle_bool (input_to_response_ms dom sg) (ds_response_deadline_ms dom).

(* Subset / admissible-load monotonicity theorems. *)
Definition AdmissibleLiveSet (dom : DomainSpec) (live : list MemberSpec) : Prop :=
  NoDup (map ms_id live) /\ forall m, In m live -> In m (ds_members dom).

Fixpoint remove_member_by_id (mid : nat) (ms : list MemberSpec) : list MemberSpec :=
  match ms with
  | nil => nil
  | m :: rest => if Nat.eqb (ms_id m) mid then rest else m :: remove_member_by_id mid rest
  end.

Lemma distinct_member_ids_nodup : forall ms,
  distinct_member_ids ms = true -> NoDup (map ms_id ms).
Proof.
  induction ms as [| m rest IH]; intros H.
  - constructor.
  - simpl in H. apply andb_prop in H. destruct H as [Hnot Hrest].
    apply negb_true_iff in Hnot. constructor.
    + intro Hin. apply in_map_iff in Hin. destruct Hin as [x [Heq Hxin]].
      assert (Hany : any_of (fun y => Nat.eqb (ms_id y) (ms_id m)) rest = true).
      { clear - Heq Hxin. induction rest as [| y r IHr]; [destruct Hxin |].
        simpl. destruct Hxin as [Hy | Hxin].
        - subst y. rewrite Heq, Nat.eqb_refl. reflexivity.
        - rewrite (IHr Hxin). apply orb_true_r. }
      rewrite Hany in Hnot. discriminate Hnot.
    + exact (IH Hrest).
Qed.

Lemma nodup_remove_member : forall mid ms,
  NoDup (map ms_id ms) -> NoDup (map ms_id (remove_member_by_id mid ms)).
Proof.
  intros mid ms. induction ms as [| x rest IH]; intros Hnd; [constructor |].
  simpl in *. inversion Hnd as [| ? ? Hnot Hnd_rest]; subst.
  destruct (Nat.eqb (ms_id x) mid); [exact Hnd_rest |].
  simpl. constructor; [| exact (IH Hnd_rest)].
  intro Hin. apply Hnot. apply in_map_iff in Hin. destruct Hin as [y [Hy Hyin]].
  apply in_map_iff. exists y. split; [exact Hy |].
  clear - Hyin. induction rest as [| z r IHr]; [destruct Hyin |].
  simpl in Hyin. destruct (Nat.eqb (ms_id z) mid).
  - right. exact Hyin.
  - destruct Hyin as [Hz | Hyin]; [left; exact Hz | right; exact (IHr Hyin)].
Qed.

Lemma in_remove_member : forall mid m ms,
  In m ms -> ms_id m <> mid -> In m (remove_member_by_id mid ms).
Proof.
  intros mid m ms. induction ms as [| x rest IH]; intros Hin Hne; [destruct Hin |].
  simpl. destruct Hin as [Hx | Hin].
  - subst x. destruct (Nat.eqb (ms_id m) mid) eqn:Eq.
    + apply Nat.eqb_eq in Eq. contradiction.
    + left. reflexivity.
  - destruct (Nat.eqb (ms_id x) mid) eqn:Eq.
    + exact Hin.
    + right. exact (IH Hin Hne).
Qed.

Lemma fold_add_cons : forall (f : MemberSpec -> nat) (m : MemberSpec) (rest : list MemberSpec),
  fold_over (fun acc x => acc + f x) 0 (m :: rest) =
  f m + fold_over (fun acc x => acc + f x) 0 rest.
Proof.
  intros f m rest. simpl.
  rewrite (fold_over_add_shift MemberSpec f rest (f m)). lia.
Qed.

Lemma fold_add_remove_eq : forall (f : MemberSpec -> nat) (x : MemberSpec) (full : list MemberSpec),
  NoDup (map ms_id full) ->
  In x full ->
  fold_over (fun acc y => acc + f y) 0 full =
  f x + fold_over (fun acc y => acc + f y) 0 (remove_member_by_id (ms_id x) full).
Proof.
  intros f x full. induction full as [| y rest IH]; intros Hnd Hin.
  - destruct Hin.
  - simpl in Hnd. inversion Hnd as [| ? ? Hnot Hnd_rest]; subst.
    rewrite fold_add_cons. simpl. destruct Hin as [Hy | Hin].
    + subst y. rewrite Nat.eqb_refl. reflexivity.
    + destruct (Nat.eqb (ms_id y) (ms_id x)) eqn:Eq.
      * apply Nat.eqb_eq in Eq. exfalso. apply Hnot. rewrite Eq. apply in_map. exact Hin.
      * rewrite fold_add_cons. rewrite (IH Hnd_rest Hin). lia.
Qed.

Lemma fold_add_subset_le : forall (f : MemberSpec -> nat) (live full : list MemberSpec),
  NoDup (map ms_id live) ->
  NoDup (map ms_id full) ->
  (forall m, In m live -> In m full) ->
  fold_over (fun acc y => acc + f y) 0 live <=
  fold_over (fun acc y => acc + f y) 0 full.
Proof.
  intros f live. induction live as [| x rest IH]; intros full Hndl Hndf Hsub.
  - simpl. lia.
  - simpl in Hndl. inversion Hndl as [| ? ? Hnot Hnd_rest]; subst.
    rewrite fold_add_cons.
    assert (Hx : In x full) by (apply Hsub; left; reflexivity).
    rewrite (fold_add_remove_eq f x full Hndf Hx).
    assert (Hsub_rest : forall m, In m rest -> In m (remove_member_by_id (ms_id x) full)).
    { intros m Hm. apply in_remove_member; [apply Hsub; right; exact Hm |].
      intro Heq. apply Hnot. rewrite <- Heq. apply in_map. exact Hm. }
    pose proof (IH _ Hnd_rest (nodup_remove_member (ms_id x) full Hndf) Hsub_rest) as Hrec.
    lia.
Qed.

Lemma eevdf_as_fold_add : forall dom fid l a,
  fold_over (fun acc m => if Nat.eqb (ms_id m) fid then acc else acc + member_eevdf_cost dom m) a l =
  fold_over (fun acc m => acc + (if Nat.eqb (ms_id m) fid then 0 else member_eevdf_cost dom m)) a l.
Proof.
  intros dom fid l. induction l as [| x rest IH]; intros a; [reflexivity |].
  simpl. destruct (Nat.eqb (ms_id x) fid); [replace (a + 0) with a by lia; apply IH | apply IH].
Qed.

Lemma fold_max_ge_init : forall (A : Type) (f : A -> nat) (l : list A) (acc : nat),
  acc <= fold_over (fun a x => Nat.max a (f x)) acc l.
Proof.
  intros A f l. induction l as [| x rest IH]; intros acc; simpl; [lia |].
  pose proof (IH (Nat.max acc (f x))) as H. lia.
Qed.

Lemma fold_max_in_ge : forall (A : Type) (f : A -> nat) (l : list A) (acc : nat) (x : A),
  In x l -> f x <= fold_over (fun a y => Nat.max a (f y)) acc l.
Proof.
  intros A f l. induction l as [| y rest IH]; intros acc x Hin; [destruct Hin |].
  simpl. destruct Hin as [Hy | Hin].
  - subst y. pose proof (fold_max_ge_init A f rest (Nat.max acc (f x))) as H. lia.
  - exact (IH (Nat.max acc (f y)) x Hin).
Qed.

(*| discharges: R-11-006c |*)
Theorem eevdf_interference_monotone_in_live_set :
  forall dom f live,
    distinct_member_ids (ds_members dom) = true ->
    In f (ds_members dom) ->
    AdmissibleLiveSet dom live ->
    eevdf_interference_for_focus dom (ms_id f) live <= worst_eevdf_interference dom.
Proof.
  intros dom f live Hdist Hf [Hndl Hsub].
  unfold worst_eevdf_interference, eevdf_interference_for_focus.
  rewrite eevdf_as_fold_add.
  pose proof (distinct_member_ids_nodup _ Hdist) as Hndf.
  pose proof (fold_add_subset_le
    (fun m => if Nat.eqb (ms_id m) (ms_id f) then 0 else member_eevdf_cost dom m)
    live (ds_members dom) Hndl Hndf Hsub) as Hle.
  cbv beta in Hle.
  pose proof (fold_max_in_ge MemberSpec
    (fun g => eevdf_interference_for_focus dom (ms_id g) (ds_members dom))
    (ds_members dom) 0 f Hf) as Hmax.
  unfold eevdf_interference_for_focus in Hmax.
  rewrite (eevdf_as_fold_add dom (ms_id f) (ds_members dom) 0) in Hmax.
  lia.
Qed.

Lemma worst_total_weight_bounds_subset :
  forall dom mid focus_id live,
    distinct_member_ids (ds_members dom) = true ->
    AdmissibleLiveSet dom live ->
    (forall f, focus_id = Some f -> In f (map ms_id (ds_members dom)) /\ f <> mid) ->
    total_weight_subset dom focus_id live <= worst_total_weight_against dom mid.
Proof.
  intros dom mid focus_id live Hdist [Hndl Hsub] Hfoc.
  pose proof (distinct_member_ids_nodup _ Hdist) as Hndf.
  pose proof (fold_add_subset_le (focus_weight_for dom focus_id) live (ds_members dom) Hndl Hndf Hsub) as Hle.
  cbv beta in Hle.
  change (fold_over (fun acc y => acc + focus_weight_for dom focus_id y) 0 live)
    with (total_weight_subset dom focus_id live) in Hle.
  change (fold_over (fun acc y => acc + focus_weight_for dom focus_id y) 0 (ds_members dom))
    with (total_weight_subset dom focus_id (ds_members dom)) in Hle.
  unfold worst_total_weight_against.
  destruct focus_id as [fid |].
  - destruct (Hfoc fid eq_refl) as [Hfin Hne].
    apply in_map_iff in Hfin. destruct Hfin as [f [Hfid Hfin]].
    assert (Hne' : Nat.eqb (ms_id f) mid = false).
    { apply Nat.eqb_neq. rewrite Hfid. exact Hne. }
    set (g := fun x : MemberSpec =>
      if Nat.eqb (ms_id x) mid then 0 else total_weight_subset dom (Some (ms_id x)) (ds_members dom)).
    assert (Hfold : forall l acc,
      fold_over (fun a x => if Nat.eqb (ms_id x) mid then a else Nat.max a (total_weight_subset dom (Some (ms_id x)) (ds_members dom))) acc l =
      fold_over (fun a x => Nat.max a (g x)) acc l).
    { intros l. induction l as [| y r IH]; intros acc; [reflexivity |].
      simpl. unfold g at 2. destruct (Nat.eqb (ms_id y) mid) eqn:E.
      - replace (Nat.max acc 0) with acc by lia. apply IH.
      - apply IH. }
    rewrite Hfold.
    pose proof (fold_max_in_ge MemberSpec g (ds_members dom) (total_weight_subset dom None (ds_members dom)) f Hfin) as Hmax.
    unfold g in Hmax at 1. rewrite Hne', Hfid in Hmax. lia.
  - pose proof (fold_max_ge_init MemberSpec
      (fun f => if Nat.eqb (ms_id f) mid then 0 else total_weight_subset dom (Some (ms_id f)) (ds_members dom))
      (ds_members dom) (total_weight_subset dom None (ds_members dom))) as Hge.
    assert (Hfold : forall l acc,
      fold_over (fun a x => if Nat.eqb (ms_id x) mid then a else Nat.max a (total_weight_subset dom (Some (ms_id x)) (ds_members dom))) acc l =
      fold_over (fun a x => Nat.max a (if Nat.eqb (ms_id x) mid then 0 else total_weight_subset dom (Some (ms_id x)) (ds_members dom))) acc l).
    { intros l. induction l as [| y r IH]; intros acc; [reflexivity |].
      simpl. destruct (Nat.eqb (ms_id y) mid).
      - replace (Nat.max acc 0) with acc by lia. apply IH.
      - apply IH. }
    rewrite Hfold. lia.
Qed.

(*| discharges: R-07-037g, R-11-006c |*)
Theorem minimum_share_preserved_under_all_admissible_loads :
  forall dom sg m live focus_id,
    domain_admits dom sg = true ->
    In m (ds_members dom) ->
    AdmissibleLiveSet dom live ->
    In m live ->
    (forall f, focus_id = Some f -> In f (map ms_id (ds_members dom)) /\ f <> ms_id m) ->
    (member_min_share m <=
     Qmult (qpos (ms_weight m) (total_weight_subset dom focus_id live))
           (Qmult (domain_net_share dom sg) (member_step_efficiency dom m)))%Q.
Proof.
  intros dom sg m live focus_id Hadm Hm Hlive Hmlive Hfoc.
  unfold domain_admits in Hadm.
  rewrite !andb_true_iff in Hadm.
  destruct Hadm as [[[[[[[[[[[[[[[[_ _] Hval] Hdist] Hfw] Hfr] Hopp] Hfp] _] _] _] _] Hmin_all] _] _] _] _].
  pose proof (all_of_in _ _ _ _ Hmin_all Hm) as Hmin_m.
  apply Qle_bool_iff in Hmin_m.
  pose proof (all_of_in _ _ _ _ Hval Hm) as Hvm.
  unfold member_spec_valid in Hvm. rewrite !andb_true_iff in Hvm.
  destruct Hvm as [[Hwm Hrm] _]. apply Nat.ltb_lt in Hwm. apply Nat.ltb_lt in Hrm.
  apply Nat.ltb_lt in Hfp.
  assert (Htw_pos : 0 < total_weight_subset dom focus_id live).
  { clear - Hmlive Hwm Hfoc.
    assert (Hfw_pos : 0 < focus_weight_for dom focus_id m).
    { unfold focus_weight_for. destruct focus_id as [fid |].
      - destruct (Hfoc fid eq_refl) as [_ Hne].
        destruct (Nat.eqb (ms_id m) fid) eqn:E.
        + apply Nat.eqb_eq in E. exfalso. apply Hne. symmetry. exact E.
        + exact Hwm.
      - exact Hwm. }
    induction live as [| x rest IH]; [destruct Hmlive |].
    unfold total_weight_subset. rewrite fold_add_cons.
    destruct Hmlive as [Hx | Hmlive].
    - subst x. lia.
    - pose proof (IH Hmlive) as Hr. unfold total_weight_subset in Hr. lia. }
  pose proof (worst_total_weight_bounds_subset dom (ms_id m) focus_id live Hdist Hlive Hfoc) as Hwle.
  assert (Heevdf_le : (member_eevdf_share dom m <= qpos (ms_weight m) (total_weight_subset dom focus_id live))%Q).
  { unfold member_eevdf_share, qpos. apply qdiv_denom_anti; assumption. }
  assert (Hnonneg : (0 <= Qmult (domain_net_share dom sg) (member_step_efficiency dom m))%Q).
  { unfold domain_net_share, member_step_efficiency, eff_request_member, qpos, Qdiv.
    apply Qmult_le_0_compat;
      apply Qmult_le_0_compat;
      try (change 0%Q with (qn 0); apply qn_inj_le; lia);
      apply Qlt_le_weak; apply Qinv_lt_0_compat; apply qn_pos; lia. }
  apply (Qle_trans _ (member_net_share dom sg m) _ Hmin_m).
  unfold member_net_share.
  apply Qmult_le_compat_r; assumption.
Qed.

(*| discharges: R-18-004a, R-18-004c |*)
Theorem admitted_desktop_meets_16_7ms_and_66_7ms_with_8_members_and_build :
  forall dom sg,
    domain_admits dom sg = true ->
    8 <= length (ds_members dom)
    /\ (exists b, In b (ds_members dom) /\ ms_is_build b = true)
    /\ min_usable_slot_width dom <= sg_frame_period sg
    /\ (focus_dispatch_ms dom sg <= ds_dispatch_deadline_ms dom)%Q
    /\ (input_to_response_ms dom sg <= ds_response_deadline_ms dom)%Q.
Proof.
  intros dom sg Hadm.
  unfold domain_admits in Hadm. rewrite !andb_true_iff in Hadm.
  destruct Hadm as [[[[[[[[[[[[[[[[Hlen Hbuild] _] _] _] _] _] _] Hnonnil] _] Hsum] Hminw] _] _] _] Hdisp] Hresp].
  apply Nat.leb_le in Hlen.
  apply Nat.leb_le in Hsum.
  apply Qle_bool_iff in Hdisp.
  apply Qle_bool_iff in Hresp.
  destruct (any_of_in _ _ _ Hbuild) as [b [Hbin Hbis]].
  assert (Hslot : min_usable_slot_width dom <= sg_frame_period sg).
  { destruct (sg_domain_slots sg) as [| s rest] eqn:Es; [discriminate Hnonnil |].
    assert (Hsin : In s (s :: rest)) by (left; reflexivity).
    pose proof (all_of_in _ _ _ _ Hminw Hsin) as Hsw. apply Nat.leb_le in Hsw.
    assert (Hle_tot : sw_width s <= total_domain_width sg).
    { unfold total_domain_width. rewrite Es. simpl.
      rewrite (fold_over_add_shift SlotWindow sw_width rest (sw_width s)). lia. }
    lia. }
  repeat split; try assumption.
  exists b. split; assumption.
Qed.

(* =========================================================================
   S3. Offline slot-geometry comparison (`R-11-022a`).
   ========================================================================= *)

Definition slot_geometry_comparison_accepts
    (dom : DomainSpec) (base cand : SlotGeometry) : bool :=
  domain_admits dom base
  && domain_admits dom cand
  && Nat.eqb (sg_frame_period cand) (sg_frame_period base)
  && Nat.eqb (sg_reserved_band cand) (sg_reserved_band base)
  && Nat.eqb (sg_peer_width cand) (sg_peer_width base)
  && Nat.eqb (total_domain_width cand) (total_domain_width base)
  && Nat.leb (sg_peer_service_floor base) (sg_peer_service_floor cand)
  && Nat.leb (sg_admitted_member_service_floor base) (total_usable_cycles dom cand)
  && Nat.leb (sg_peak_memory_bytes cand) (sg_peak_memory_bytes base)
  && qlt_bool (focus_dispatch_ms dom cand) (focus_dispatch_ms dom base)
  && qlt_bool (input_to_response_ms dom cand) (input_to_response_ms dom base).

Definition SlotGeometryAccepted (dom : DomainSpec) (base cand : SlotGeometry) : Prop :=
  domain_admits dom base = true
  /\ domain_admits dom cand = true
  /\ sg_frame_period cand = sg_frame_period base
  /\ sg_reserved_band cand = sg_reserved_band base
  /\ sg_peer_width cand = sg_peer_width base
  /\ total_domain_width cand = total_domain_width base
  /\ sg_peer_service_floor base <= sg_peer_service_floor cand
  /\ sg_admitted_member_service_floor base <= total_usable_cycles dom cand
  /\ sg_peak_memory_bytes cand <= sg_peak_memory_bytes base
  /\ (focus_dispatch_ms dom cand < focus_dispatch_ms dom base)%Q
  /\ (input_to_response_ms dom cand < input_to_response_ms dom base)%Q.

(*| discharges: R-11-022a |*)
Theorem slot_geometry_comparison_iff :
  forall dom base cand,
    slot_geometry_comparison_accepts dom base cand = true <->
    SlotGeometryAccepted dom base cand.
Proof.
  intros dom base cand.
  unfold slot_geometry_comparison_accepts, SlotGeometryAccepted.
  rewrite !andb_true_iff, !Nat.eqb_eq, !Nat.leb_le, !qlt_bool_lt.
  tauto.
Qed.

Definition compare_geometries (dom : DomainSpec) (base cand : SlotGeometry) : GeometryComparison :=
  {| gc_accepted := slot_geometry_comparison_accepts dom base cand;
     gc_base_dispatch_ms := focus_dispatch_ms dom base;
     gc_cand_dispatch_ms := focus_dispatch_ms dom cand;
     gc_base_response_ms := input_to_response_ms dom base;
     gc_cand_response_ms := input_to_response_ms dom cand;
     gc_base_usable := total_usable_cycles dom base;
     gc_cand_usable := total_usable_cycles dom cand |}.

(* =========================================================================
   S4. Concrete >=8-member desktop roster, positive admissions,
       non-vacuity witnesses (`R-05-166`), and distinguishing refutations.
   ========================================================================= *)

Definition mk_member (id app : nat) (is_build : bool) (w req min_n min_d fl : nat) : MemberSpec :=
  {| ms_id := id; ms_app := app; ms_is_build := is_build;
     ms_weight := w; ms_request := req;
     ms_min_share_num := min_n; ms_min_share_den := min_d; ms_floor_bytes := fl |}.

Definition demo_roster : list MemberSpec :=
  [ mk_member 0 1 false 4 1 1 25 128;
    mk_member 1 2 true  2 1 1 50 256;
    mk_member 2 3 false 1 1 1 50 64;
    mk_member 3 4 false 1 1 1 50 64;
    mk_member 4 5 false 1 1 1 50 64;
    mk_member 5 6 false 1 1 1 50 64;
    mk_member 6 7 false 1 1 1 50 64;
    mk_member 7 8 false 1 1 1 50 64 ].

Definition demo_domain_spec : DomainSpec := {|
  ds_label := 3;
  ds_members := demo_roster;
  ds_focus_weight := 8;
  ds_focus_request := 1;
  ds_call_interval := 1;
  ds_yield_bound := 1;
  ds_rotation_cost := 0;
  ds_vmclear_cost := 1;
  ds_poll_cost := 1;
  ds_switch_cost := 0;
  ds_opp_cycles_per_ms := 10;
  ds_focus_exec_cycles := 16;
  ds_scanout_period := 160;
  ds_dispatch_deadline_ms := (167 # 10)%Q;
  ds_response_deadline_ms := (667 # 10)%Q;
  ds_peak_memory_bytes := 1024
|}.

Definition base_slot_geometry : SlotGeometry := {|
  sg_frame_period := 200;
  sg_reserved_band := 20;
  sg_peer_width := 60;
  sg_peer_service_floor := 55;
  sg_domain_slots := [{| sw_start := 0; sw_width := 120 |}];
  sg_admitted_member_service_floor := 100;
  sg_peak_memory_bytes := 1024
|}.

(* Two shorter focus slots halving max slot gap (80 -> 40) at identical 120-tick share. *)
Definition two_slot_geometry : SlotGeometry := {|
  sg_frame_period := 200;
  sg_reserved_band := 20;
  sg_peer_width := 60;
  sg_peer_service_floor := 55;
  sg_domain_slots := [{| sw_start := 0; sw_width := 60 |};
                      {| sw_start := 100; sw_width := 60 |}];
  sg_admitted_member_service_floor := 100;
  sg_peak_memory_bytes := 1024
|}.

(* Shorter visit period (15 slots of width 8, identical 120-tick share) whose
   added switch/clear/poll/tail overhead destroys usable service and worsens
   focus dispatch latency beyond the 16.7 ms deadline. *)
Definition fragmented_15slot_geometry : SlotGeometry := {|
  sg_frame_period := 200;
  sg_reserved_band := 20;
  sg_peer_width := 60;
  sg_peer_service_floor := 55;
  sg_domain_slots :=
    [{| sw_start := 0;   sw_width := 8 |}; {| sw_start := 13;  sw_width := 8 |};
     {| sw_start := 26;  sw_width := 8 |}; {| sw_start := 39;  sw_width := 8 |};
     {| sw_start := 52;  sw_width := 8 |}; {| sw_start := 65;  sw_width := 8 |};
     {| sw_start := 78;  sw_width := 8 |}; {| sw_start := 91;  sw_width := 8 |};
     {| sw_start := 104; sw_width := 8 |}; {| sw_start := 117; sw_width := 8 |};
     {| sw_start := 130; sw_width := 8 |}; {| sw_start := 143; sw_width := 8 |};
     {| sw_start := 156; sw_width := 8 |}; {| sw_start := 169; sw_width := 8 |};
     {| sw_start := 182; sw_width := 8 |}];
  sg_admitted_member_service_floor := 100;
  sg_peak_memory_bytes := 1024
|}.

Definition peer_weakened_geometry : SlotGeometry := {|
  sg_frame_period := 200;
  sg_reserved_band := 20;
  sg_peer_width := 60;
  sg_peer_service_floor := 50;
  sg_domain_slots := [{| sw_start := 0; sw_width := 60 |};
                      {| sw_start := 100; sw_width := 60 |}];
  sg_admitted_member_service_floor := 100;
  sg_peak_memory_bytes := 1024
|}.

Definition memory_bloated_geometry : SlotGeometry := {|
  sg_frame_period := 200;
  sg_reserved_band := 20;
  sg_peer_width := 60;
  sg_peer_service_floor := 55;
  sg_domain_slots := [{| sw_start := 0; sw_width := 60 |};
                      {| sw_start := 100; sw_width := 60 |}];
  sg_admitted_member_service_floor := 100;
  sg_peak_memory_bytes := 1280
|}.

Theorem demo_baseline_and_two_slot_admitted :
  domain_admits demo_domain_spec base_slot_geometry = true
  /\ domain_admits demo_domain_spec two_slot_geometry = true
  /\ slot_geometry_comparison_accepts demo_domain_spec base_slot_geometry two_slot_geometry = true
  /\ SlotGeometryAccepted demo_domain_spec base_slot_geometry two_slot_geometry.
Proof.
  split; [vm_reflexivity | split; [vm_reflexivity | split; [vm_reflexivity |]]].
  apply slot_geometry_comparison_iff. vm_reflexivity.
Qed.

Theorem refute_shorter_visit_period_candidate :
  total_domain_width fragmented_15slot_geometry = total_domain_width base_slot_geometry
  /\ total_usable_cycles demo_domain_spec fragmented_15slot_geometry <
       sg_admitted_member_service_floor base_slot_geometry
  /\ (focus_dispatch_ms demo_domain_spec base_slot_geometry <
      focus_dispatch_ms demo_domain_spec fragmented_15slot_geometry)%Q
  /\ domain_admits demo_domain_spec fragmented_15slot_geometry = false
  /\ slot_geometry_comparison_accepts demo_domain_spec base_slot_geometry fragmented_15slot_geometry = false
  /\ ~ SlotGeometryAccepted demo_domain_spec base_slot_geometry fragmented_15slot_geometry.
Proof.
  split; [vm_reflexivity |].
  split; [unfold total_usable_cycles, sg_admitted_member_service_floor; cbn; lia |].
  split; [apply qlt_bool_lt; vm_reflexivity |].
  split; [vm_reflexivity |].
  split; [vm_reflexivity |].
  intro H. apply slot_geometry_comparison_iff in H.
  assert (Hf : slot_geometry_comparison_accepts demo_domain_spec base_slot_geometry fragmented_15slot_geometry = false)
    by vm_reflexivity.
  rewrite H in Hf. discriminate Hf.
Qed.

Theorem refute_peer_weakened_and_memory_bloated_candidates :
  slot_geometry_comparison_accepts demo_domain_spec base_slot_geometry peer_weakened_geometry = false
  /\ slot_geometry_comparison_accepts demo_domain_spec base_slot_geometry memory_bloated_geometry = false.
Proof.
  split; vm_reflexivity.
Qed.

(* Pool witnesses and refutations. *)
Definition mk_pool_member
    (id fl ex sh : nat) (live hib con mtx sac chk : bool) (lf : nat) : PoolMember := {|
  pm_id := id; pm_floor := fl; pm_extra := ex; pm_sheddable := sh;
  pm_live := live; pm_hibernated := hib;
  pm_consent_bearing := con; pm_mid_transaction := mtx;
  pm_sacrificable := sac; pm_checkpointable := chk; pm_last_focus := lf
|}.

Definition demo_pool_members : list PoolMember :=
  [ mk_pool_member 0 128 32 16 true  false false false true  true  0;
    mk_pool_member 1 256 64 16 true  false false false false true  1;
    mk_pool_member 2  64 32  8 true  false true  false true  true  2;
    mk_pool_member 3  64 32  8 true  false false true  true  true  3;
    mk_pool_member 4  64 32  8 true  false false false true  false 4;
    mk_pool_member 5  64 32  8 true  false false false true  true  5;
    mk_pool_member 6  64 32  8 true  false false false true  true  8;
    mk_pool_member 7  64 32  8 false false false false true  true  9 ].

Definition demo_pool_state : PoolState := {|
  ps_capacity := 1024;
  ps_quarantined := 64;
  ps_focused := Some 0;
  ps_fixed_tier := 2048;
  ps_other_domain := 512;
  ps_members := demo_pool_members
|}.

(* Notice: member 0 is focused with oldest pm_last_focus = 0; member 1 is non-sacrificable;
   member 2 is consent-bearing; member 3 is mid-transaction; member 4 is uncheckpointable;
   member 5 (tick 5) and member 6 (tick 8) are eligible, so LRU picks member 5! *)
Theorem refute_focused_member_eviction_picks_lru_eligible_background :
  ps_focused demo_pool_state = Some 0
  /\ lr_outcome (hibernate_lru demo_pool_state) = OutcomeHibernated 5
  /\ lr_outcome (hibernate_lru demo_pool_state) <> OutcomeHibernated 0
  /\ ps_fixed_tier (lr_state (hibernate_lru demo_pool_state)) = 2048
  /\ ps_other_domain (lr_state (hibernate_lru demo_pool_state)) = 512.
Proof.
  split; [vm_reflexivity | split; [vm_reflexivity | split; [| split; vm_reflexivity]]].
  vm_compute. discriminate.
Qed.

(* Pool free is 0, quarantined is 64 (behind reuse barrier), and dormant member 7 needs floor 64:
   launch MUST be refused until the reuse barrier completes! *)
Theorem refute_exhausted_floor_launch :
  pool_free demo_pool_state = 0
  /\ ps_quarantined demo_pool_state = 64
  /\ launch_member demo_pool_state 7 =
       {| lr_outcome := OutcomeRefuseLaunch; lr_state := demo_pool_state |}
  /\ lr_outcome (launch_member (complete_reuse_barrier demo_pool_state) 7) = OutcomeGranted.
Proof.
  repeat split; vm_reflexivity.
Qed.

Definition demo_ceiling_pool_state : PoolState := {|
  ps_capacity := 1024;
  ps_quarantined := 0;
  ps_focused := Some 0;
  ps_fixed_tier := 2048;
  ps_other_domain := 512;
  ps_members :=
    [ mk_pool_member 0 512 0 0 true false false false true  true  0;
      mk_pool_member 1 256 0 0 true false false false false true  1;
      mk_pool_member 2 256 0 0 true false true  false true  true  2 ]
|}.

Theorem demo_ceiling_refusal :
  hibernate_lru demo_ceiling_pool_state =
  {| lr_outcome := OutcomeRefuseAtCeiling; lr_state := demo_ceiling_pool_state |}.
Proof.
  vm_reflexivity.
Qed.

(* Closed top-level record inhabitation witnesses (`R-05-166`). *)
Definition witness_PoolMember : PoolMember :=
  mk_pool_member 0 128 32 16 true false false false true true 0.

Definition witness_PoolState : PoolState :=
  demo_pool_state.

Definition witness_LadderResult : LadderResult :=
  hibernate_lru demo_pool_state.

Definition witness_MemberSpec : MemberSpec :=
  mk_member 0 1 false 4 1 1 25 128.

Definition witness_DomainSpec : DomainSpec :=
  demo_domain_spec.

Definition witness_SlotWindow : SlotWindow :=
  {| sw_start := 0; sw_width := 120 |}.

Definition witness_SlotGeometry : SlotGeometry :=
  base_slot_geometry.

Definition witness_GeometryComparison : GeometryComparison :=
  compare_geometries demo_domain_spec base_slot_geometry two_slot_geometry.
