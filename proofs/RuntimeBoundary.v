(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   RuntimeBoundary.v

   Q47 callback-safety and runtime-teardown qualification model.

   Part 1 formalizes the callback-safety boundary over explicit `ObjectId`,
   slice bounds (`init_prefix <= len <= cap`), UTF-8/ASCII range validation
   bound to exact `ObjectId`, synchronous reentrancy locking, and ownership /
   drop linearity. Safety preservation is proved under adversarial callbacks
   (changing borrows, inconsistent comparators, lying iterator lengths,
   foreign-string ranges, and reentrant calls or drops).

   Part 2 formalizes native abandonment and multi-class holder retirement
   (`RunningHart`, `SavedContext`, `RegisteredHandle`, `PeerCap`,
   `QueuedReply`, `OutstandingDma`), proving that native abandonment runs
   zero user cleanup frames and never invokes destructors to reclaim chunks
   or DMA loans, that disabling a caller registration leaves other contexts'
   holders intact, that backing zeroization and reuse are refused until all
   holder classes complete, and that guest trap, cancel, or memory growth
   never unwinds native frames and invalidates stale guest views.

   Closed `witness_<R>` terms inhabit every declared record (R-05-166), and
   computed refutations distinguish guarded checks from single-defect
   weakenings (R-05-163, R-05-164, R-05-165). Governing obligations:
   R-05-031, R-05-080, R-05-100, R-08-004, R-13-012, R-13-013, R-14-013a,
   R-16-001.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-031 R-05-080 R-05-100 R-05-163 R-05-164 R-05-165 R-05-166 R-08-004
      R-13-012 R-13-013 R-14-013a R-16-001
   SHA256: d24d8f123fa8210318b71d0951516ac0b783041e5bc6f428df9b9b9c7244ecc0
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Require ProofSupport.
Import ListNotations.
Local Open Scope nat_scope.

(* =========================================================================
   Part 1: Callback-Safety Model (ObjectId, Bounds, UTF-8, Reentrancy, Drop)
   ========================================================================= *)

Record ObjectId : Type := {
  oid_gen : nat;
  oid_slot : nat
}.

Definition witness_ObjectId : ObjectId := {|
  oid_gen := 1;
  oid_slot := 0
|}.

Definition object_id_eqb (a b : ObjectId) : bool :=
  Nat.eqb (oid_gen a) (oid_gen b) && Nat.eqb (oid_slot a) (oid_slot b).

Lemma object_id_eqb_eq : forall a b,
  object_id_eqb a b = true <-> a = b.
Proof.
  intros [ga sa] [gb sb]. unfold object_id_eqb. simpl.
  rewrite andb_true_iff, !Nat.eqb_eq. split.
  - intros [Hg Hs]. subst. reflexivity.
  - intro H. inversion H. split; reflexivity.
Qed.

Record SliceView : Type := {
  sv_obj : ObjectId;
  sv_bytes : list nat;
  sv_cap : nat;
  sv_len : nat;
  sv_init : nat
}.

Definition witness_SliceView : SliceView := {|
  sv_obj := witness_ObjectId;
  sv_bytes := [65; 66; 67; 68];
  sv_cap := 4;
  sv_len := 4;
  sv_init := 4
|}.

Definition slice_bytes_bounded (bs : list nat) (n : nat) : bool :=
  forallb (fun b => b <? 256) (firstn n bs).

Definition slice_ok (v : SliceView) : bool :=
  (sv_init v <=? sv_len v)
  && (sv_len v <=? sv_cap v)
  && (sv_cap v <=? length (sv_bytes v))
  && slice_bytes_bounded (sv_bytes v) (sv_init v).

Definition slice_inv (v : SliceView) : Prop :=
  sv_init v <= sv_len v
  /\ sv_len v <= sv_cap v
  /\ sv_cap v <= length (sv_bytes v)
  /\ slice_bytes_bounded (sv_bytes v) (sv_init v) = true.

Lemma slice_ok_inv : forall v,
  slice_ok v = true <-> slice_inv v.
Proof.
  intro v. unfold slice_ok, slice_inv.
  rewrite !andb_true_iff, !Nat.leb_le. tauto.
Qed.

(* Constructive UTF-8 validator over byte lists (RFC 3629 scalar ranges). *)
Definition is_ascii_byte (b : nat) : bool := b <? 128.

Definition is_cont_byte (b : nat) : bool :=
  (128 <=? b) && (b <=? 191).

Fixpoint utf8_valid_bytes (bs : list nat) : bool :=
  match bs with
  | [] => true
  | b0 :: rest =>
      if b0 <? 128 then
        utf8_valid_bytes rest
      else if (194 <=? b0) && (b0 <=? 223) then
        match rest with
        | b1 :: r1 => is_cont_byte b1 && utf8_valid_bytes r1
        | [] => false
        end
      else if (224 <=? b0) && (b0 <=? 239) then
        match rest with
        | b1 :: b2 :: r2 =>
            let lead_ok :=
              if Nat.eqb b0 224 then (160 <=? b1) && (b1 <=? 191)
              else if Nat.eqb b0 237 then (128 <=? b1) && (b1 <=? 159)
              else is_cont_byte b1 in
            lead_ok && is_cont_byte b2 && utf8_valid_bytes r2
        | _ => false
        end
      else if (240 <=? b0) && (b0 <=? 244) then
        match rest with
        | b1 :: b2 :: b3 :: r3 =>
            let lead_ok :=
              if Nat.eqb b0 240 then (144 <=? b1) && (b1 <=? 191)
              else if Nat.eqb b0 244 then (128 <=? b1) && (b1 <=? 143)
              else is_cont_byte b1 in
            lead_ok && is_cont_byte b2 && is_cont_byte b3 && utf8_valid_bytes r3
        | _ => false
        end
      else
        false
  end.

Definition subslice (bs : list nat) (s e : nat) : list nat :=
  firstn (e - s) (skipn s bs).

Lemma subslice_length : forall bs s e,
  s <= e -> e <= length bs ->
  length (subslice bs s e) = e - s.
Proof.
  intros bs s e Hse He. unfold subslice.
  rewrite length_firstn, length_skipn. lia.
Qed.

Record ValidatedRange : Type := {
  vr_obj : ObjectId;
  vr_start : nat;
  vr_end : nat;
  vr_require_utf8 : bool
}.

Definition witness_ValidatedRange : ValidatedRange := {|
  vr_obj := witness_ObjectId;
  vr_start := 0;
  vr_end := 2;
  vr_require_utf8 := true
|}.

Definition range_valid_for (v : SliceView) (r : ValidatedRange) : bool :=
  object_id_eqb (vr_obj r) (sv_obj v)
  && (vr_start r <=? vr_end r)
  && (vr_end r <=? sv_init v)
  && (if vr_require_utf8 r
      then utf8_valid_bytes (subslice (sv_bytes v) (vr_start r) (vr_end r))
      else true).

Definition checked_slice_substr (v : SliceView) (r : ValidatedRange)
  : option (list nat) :=
  if slice_ok v && range_valid_for v r
  then Some (subslice (sv_bytes v) (vr_start r) (vr_end r))
  else None.

Theorem checked_slice_substr_safe : forall v r out,
  checked_slice_substr v r = Some out ->
  slice_inv v
  /\ vr_obj r = sv_obj v
  /\ vr_start r <= vr_end r
  /\ vr_end r <= sv_init v
  /\ length out = vr_end r - vr_start r
  /\ (vr_require_utf8 r = true -> utf8_valid_bytes out = true).
Proof.
  intros v r out H. unfold checked_slice_substr in H.
  destruct (slice_ok v) eqn:Hs; [|discriminate].
  destruct (range_valid_for v r) eqn:Hr; [|discriminate].
  simpl in H. inversion H. subst out.
  apply slice_ok_inv in Hs.
  unfold range_valid_for in Hr.
  rewrite !andb_true_iff in Hr.
  destruct Hr as [[[Hobj Hse] Hend] Hutf].
  apply object_id_eqb_eq in Hobj.
  apply Nat.leb_le in Hse. apply Nat.leb_le in Hend.
  destruct Hs as [Hi [Hl [Hc Hbs]]].
  repeat split; try assumption.
  - apply subslice_length; [exact Hse|lia].
  - intro Hreq. rewrite Hreq in Hutf. exact Hutf.
Qed.

(* Two-pass callback safety: pass 1 validates an initial view; pass 2 may
   mutate bytes, shrink init_prefix, or switch ObjectId. Re-validation binds
   the copied prefix to the remaining destination capacity and live ObjectId. *)
Definition two_pass_extract
    (cb_src : nat -> SliceView) (expected_id : ObjectId) (dst_cap : nat)
    : option (list nat) :=
  let v1 := cb_src 0 in
  if slice_ok v1 && object_id_eqb (sv_obj v1) expected_id
     && (sv_init v1 <=? dst_cap)
  then
    let v2 := cb_src 1 in
    if slice_ok v2 && object_id_eqb (sv_obj v2) expected_id
       && (sv_init v2 <=? dst_cap)
       && (sv_init v1 <=? sv_init v2)
    then Some (firstn (sv_init v1) (sv_bytes v2))
    else None
  else None.

Theorem two_pass_extract_safe : forall cb_src expected_id dst_cap out,
  two_pass_extract cb_src expected_id dst_cap = Some out ->
  length out <= dst_cap
  /\ object_id_eqb (sv_obj (cb_src 0)) expected_id = true
  /\ object_id_eqb (sv_obj (cb_src 1)) expected_id = true
  /\ length out <= sv_init (cb_src 1)
  /\ sv_init (cb_src 1) <= length (sv_bytes (cb_src 1)).
Proof.
  intros cb_src expected_id dst_cap out H.
  unfold two_pass_extract in H.
  destruct (slice_ok (cb_src 0) && object_id_eqb (sv_obj (cb_src 0)) expected_id
            && (sv_init (cb_src 0) <=? dst_cap)) eqn:E1; [|discriminate].
  destruct (slice_ok (cb_src 1) && object_id_eqb (sv_obj (cb_src 1)) expected_id
            && (sv_init (cb_src 1) <=? dst_cap)
            && (sv_init (cb_src 0) <=? sv_init (cb_src 1))) eqn:E2; [|discriminate].
  inversion H. subst out.
  rewrite !andb_true_iff in E1.
  rewrite !andb_true_iff in E2.
  destruct E1 as [[Hs1 Hid1] Hcap1].
  destruct E2 as [[[Hs2 Hid2] Hcap2] Hmono].
  apply slice_ok_inv in Hs2.
  apply Nat.leb_le in Hcap1.
  apply Nat.leb_le in Hmono.
  destruct Hs2 as [Hi2 [Hl2 [Hc2 _]]].
  rewrite length_firstn.
  repeat split; try assumption; lia.
Qed.

(* Collection state with synchronous reentrancy lock and linear drop tracking. *)
Record CollectionState : Type := {
  cs_id : ObjectId;
  cs_buf : list nat;
  cs_cap : nat;
  cs_len : nat;
  cs_init : nat;
  cs_reentry_locked : bool;
  cs_owned : bool;
  cs_dropped : bool;
  cs_drop_count : nat
}.

Definition witness_CollectionState : CollectionState := {|
  cs_id := witness_ObjectId;
  cs_buf := [65; 66; 0; 0];
  cs_cap := 4;
  cs_len := 2;
  cs_init := 2;
  cs_reentry_locked := false;
  cs_owned := true;
  cs_dropped := false;
  cs_drop_count := 0
|}.

Definition collection_inv (st : CollectionState) : Prop :=
  cs_init st <= cs_len st
  /\ cs_len st <= cs_cap st
  /\ cs_cap st <= length (cs_buf st)
  /\ cs_drop_count st <= 1
  /\ (cs_dropped st = true ->
      cs_owned st = false /\ cs_init st = 0 /\ cs_len st = 0 /\ cs_drop_count st = 1)
  /\ (cs_dropped st = false -> cs_drop_count st = 0).

Definition collection_ok (st : CollectionState) : bool :=
  (cs_init st <=? cs_len st)
  && (cs_len st <=? cs_cap st)
  && (cs_cap st <=? length (cs_buf st))
  && (cs_drop_count st <=? 1)
  && (if cs_dropped st
      then negb (cs_owned st) && Nat.eqb (cs_init st) 0
           && Nat.eqb (cs_len st) 0 && Nat.eqb (cs_drop_count st) 1
      else Nat.eqb (cs_drop_count st) 0).

Lemma collection_ok_inv : forall st,
  collection_ok st = true <-> collection_inv st.
Proof.
  intro st. unfold collection_ok, collection_inv.
  rewrite !andb_true_iff, !Nat.leb_le.
  destruct (cs_dropped st) eqn:Edrop; simpl.
  - rewrite !andb_true_iff, negb_true_iff, !Nat.eqb_eq.
    split.
    + intros [[[[Hi Hl] Hc] Hd] [[[Ho H0] Hl0] Hdc]].
      split; [exact Hi|]. split; [exact Hl|]. split; [exact Hc|]. split; [exact Hd|].
      split; intro E; [|discriminate E].
      split; [exact Ho|]. split; [exact H0|]. split; [exact Hl0|exact Hdc].
    + intros [Hi [Hl [Hc [Hd [Ht _]]]]].
      destruct (Ht eq_refl) as [Ho [H0 [Hl0 Hdc]]].
      repeat split; assumption.
  - rewrite Nat.eqb_eq. split.
    + intros [[[[Hi Hl] Hc] Hd] Hdc].
      split; [exact Hi|]. split; [exact Hl|]. split; [exact Hc|]. split; [exact Hd|].
      split; intro E; [discriminate E|exact Hdc].
    + intros [Hi [Hl [Hc [Hd [_ Hf]]]]].
      specialize (Hf eq_refl).
      repeat split; assumption.
Qed.

(* Bounded iterator push: ignores lying `reported_len` beyond `max_reserve`
   and advances `cs_init`/`cs_len` only per actually materialized element. *)
Fixpoint push_bounded (buf : list nat) (cap cur : nat) (items : list nat)
  : list nat * nat :=
  match items with
  | [] => (buf, cur)
  | x :: rest =>
      if cur <? cap then
        push_bounded (firstn cur buf ++ x :: skipn (S cur) buf) cap (S cur) rest
      else
        (buf, cur)
  end.

Lemma push_bounded_bounds : forall items buf cap cur,
  cur <= cap -> cap <= length buf ->
  cur <= snd (push_bounded buf cap cur items)
  /\ snd (push_bounded buf cap cur items) <= cap
  /\ length (fst (push_bounded buf cap cur items)) = length buf.
Proof.
  induction items as [|x rest IH]; intros buf cap cur Hcur Hcap; cbn [push_bounded].
  - simpl. repeat split; lia.
  - destruct (cur <? cap) eqn:Elt.
    + apply Nat.ltb_lt in Elt.
      assert (Hlen' : length (firstn cur buf ++ x :: skipn (S cur) buf) = length buf).
      { rewrite length_app, length_firstn.
        change (length (x :: skipn (S cur) buf)) with (S (length (skipn (S cur) buf))).
        rewrite length_skipn. lia. }
      assert (Hcap' : cap <= length (firstn cur buf ++ x :: skipn (S cur) buf)) by lia.
      assert (Hcur' : S cur <= cap) by lia.
      destruct (IH (firstn cur buf ++ x :: skipn (S cur) buf) cap (S cur) Hcur' Hcap')
        as [Ha [Hb Hc]].
      cbv iota. repeat split; [lia|lia|rewrite Hc; exact Hlen'].
    + simpl. repeat split; lia.
Qed.

Definition iter_collect
    (st : CollectionState) (reported_len : nat) (items : list nat)
    : CollectionState :=
  if cs_reentry_locked st || negb (cs_owned st) || cs_dropped st then
    st
  else
    (* Allocation hint is capped; actual `cs_init` and `cs_len` only grow for
       concrete yielded items, never trusting `reported_len`. *)
    let _hint := Nat.min reported_len (cs_cap st - cs_len st) in
    let pushed := push_bounded (cs_buf st) (cs_cap st) (cs_len st) items in
    {| cs_id := cs_id st;
       cs_buf := fst pushed;
       cs_cap := cs_cap st;
       cs_len := snd pushed;
       cs_init := cs_init st + (snd pushed - cs_len st);
       cs_reentry_locked := cs_reentry_locked st;
       cs_owned := cs_owned st;
       cs_dropped := cs_dropped st;
       cs_drop_count := cs_drop_count st |}.

Theorem iter_collect_preserves_inv : forall st reported_len items,
  collection_inv st ->
  collection_inv (iter_collect st reported_len items).
Proof.
  intros st reported_len items Hinv.
  unfold iter_collect.
  destruct (cs_reentry_locked st || negb (cs_owned st) || cs_dropped st) eqn:E;
    [exact Hinv|].
  destruct Hinv as [Hi [Hl [Hc [Hd [Ht Hf]]]]].
  pose proof (push_bounded_bounds items (cs_buf st) (cs_cap st) (cs_len st) Hl Hc)
    as [H1 [H2 Hlen]].
  unfold collection_inv. cbv zeta. simpl.
  split; [lia|].
  split; [lia|].
  split; [lia|].
  split; [exact Hd|].
  split.
  - intro Hdrop. rewrite Hdrop in E. rewrite orb_true_r in E. discriminate E.
  - intro Hnd. apply Hf. exact Hnd.
Qed.

(* Adversarial comparator binary search: never trusts comparator transitivity
   or antisymmetry; any returned index is strictly below `sv_init v`. *)
Fixpoint bounded_bsearch
    (cmp : nat -> nat -> comparison) (bs : list nat) (lo span fuel : nat)
    : option nat :=
  match fuel with
  | 0 => None
  | S f =>
      match span with
      | 0 => None
      | S k =>
          let mid := lo + k / 2 in
          match nth_error bs mid with
          | None => None
          | Some val =>
              match cmp val 0 with
              | Eq => Some mid
              | Lt => bounded_bsearch cmp bs (S mid) (lo + span - S mid) f
              | Gt => bounded_bsearch cmp bs lo (mid - lo) f
              end
          end
      end
  end.

Lemma bounded_bsearch_in_range : forall fuel cmp bs lo span idx,
  bounded_bsearch cmp bs lo span fuel = Some idx ->
  lo <= idx /\ idx < lo + span.
Proof.
  induction fuel as [|f IH]; intros cmp bs lo span idx H; [discriminate H|].
  destruct span as [|k]; [discriminate H|].
  cbn [bounded_bsearch] in H. cbv zeta in H.
  set (mid := lo + k / 2) in *.
  destruct (nth_error bs mid) eqn:Enth; [|discriminate H].
  assert (Hk2 : k / 2 <= k) by (pose proof (Nat.div_mod_eq k 2); lia).
  destruct (cmp n 0).
  - inversion H. subst. unfold mid. lia.
  - apply IH in H. unfold mid in *. lia.
  - apply IH in H. unfold mid in *. lia.
Qed.

Definition safe_binary_search
    (cmp : nat -> nat -> comparison) (v : SliceView) : option nat :=
  if slice_ok v then bounded_bsearch cmp (sv_bytes v) 0 (sv_init v) (sv_init v) else None.

Theorem safe_binary_search_in_bounds : forall cmp v idx,
  safe_binary_search cmp v = Some idx ->
  idx < sv_init v /\ sv_init v <= sv_len v /\ sv_len v <= sv_cap v /\
  sv_cap v <= length (sv_bytes v).
Proof.
  intros cmp v idx H. unfold safe_binary_search in H.
  destruct (slice_ok v) eqn:Hs; [|discriminate].
  apply bounded_bsearch_in_range in H.
  apply slice_ok_inv in Hs.
  destruct Hs as [Hi [Hl [Hc _]]]. lia.
Qed.

(* Synchronous callback lock and linear drop discipline. *)
Definition begin_callback (st : CollectionState) : option CollectionState :=
  if cs_reentry_locked st || negb (cs_owned st) || cs_dropped st then
    None
  else
    Some {| cs_id := cs_id st;
            cs_buf := cs_buf st;
            cs_cap := cs_cap st;
            cs_len := cs_len st;
            cs_init := cs_init st;
            cs_reentry_locked := true;
            cs_owned := cs_owned st;
            cs_dropped := cs_dropped st;
            cs_drop_count := cs_drop_count st |}.

Definition end_callback (st : CollectionState) : CollectionState :=
  {| cs_id := cs_id st;
     cs_buf := cs_buf st;
     cs_cap := cs_cap st;
     cs_len := cs_len st;
     cs_init := cs_init st;
     cs_reentry_locked := false;
     cs_owned := cs_owned st;
     cs_dropped := cs_dropped st;
     cs_drop_count := cs_drop_count st |}.

Inductive CallbackAction : Type :=
| CbMutateLen (n : nat)
| CbReentrantCall
| CbReentrantDrop
| CbReturnNormal.

Definition run_adversarial_callback
    (st : CollectionState) (act : CallbackAction) : CollectionState :=
  match begin_callback st with
  | None => st
  | Some locked =>
      let after_cb :=
        match act with
        | CbMutateLen _ => locked
        | CbReentrantCall =>
            match begin_callback locked with
            | None => locked
            | Some s => s
            end
        | CbReentrantDrop =>
            if cs_reentry_locked locked then locked else locked
        | CbReturnNormal => locked
        end in
      end_callback after_cb
  end.

Definition drop_collection (st : CollectionState) : CollectionState * list nat :=
  if cs_reentry_locked st || negb (cs_owned st) || cs_dropped st then
    (st, [])
  else
    let dropped_elems := firstn (cs_init st) (cs_buf st) in
    ({| cs_id := cs_id st;
        cs_buf := cs_buf st;
        cs_cap := cs_cap st;
        cs_len := 0;
        cs_init := 0;
        cs_reentry_locked := false;
        cs_owned := false;
        cs_dropped := true;
        cs_drop_count := S (cs_drop_count st) |},
     dropped_elems).

Theorem adversarial_callback_preserves_inv : forall st act,
  collection_inv st ->
  collection_inv (run_adversarial_callback st act).
Proof.
  intros st act Hinv. unfold run_adversarial_callback, begin_callback.
  destruct (cs_reentry_locked st || negb (cs_owned st) || cs_dropped st) eqn:E;
    [exact Hinv|].
  destruct act; simpl; unfold end_callback, collection_inv in *; simpl in *;
    exact Hinv.
Qed.

Theorem drop_collection_linear_and_initialized : forall st,
  collection_inv st ->
  let res := drop_collection st in
  collection_inv (fst res)
  /\ cs_drop_count (fst res) <= 1
  /\ (length (snd res) = cs_init st \/ snd res = []).
Proof.
  intros st Hinv. unfold drop_collection.
  destruct (cs_reentry_locked st || negb (cs_owned st) || cs_dropped st) eqn:E;
    simpl.
  - split; [exact Hinv|].
    split; [destruct Hinv as [_ [_ [_ [Hd _]]]]; exact Hd|right; reflexivity].
  - destruct Hinv as [Hi [Hl [Hc [Hd [Ht Hf]]]]].
    assert (Hnd : cs_dropped st = false).
    { destruct (cs_dropped st); [rewrite orb_true_r in E; discriminate E|reflexivity]. }
    specialize (Hf Hnd).
    split; [|split; [lia|left; rewrite length_firstn; lia]].
    unfold collection_inv. simpl.
    split; [lia|]. split; [lia|]. split; [lia|]. split; [lia|].
    split.
    + intro. split; [reflexivity|]. split; [reflexivity|]. split; [reflexivity|lia].
    + intro Hbad. discriminate Hbad.
Qed.

Theorem double_drop_is_noop : forall st,
  collection_inv st ->
  let st1 := fst (drop_collection st) in
  drop_collection st1 = (st1, []).
Proof.
  intros st Hinv. unfold drop_collection. cbv zeta.
  destruct (cs_reentry_locked st || negb (cs_owned st) || cs_dropped st) eqn:E;
    simpl.
  - unfold drop_collection. rewrite E. reflexivity.
  - unfold drop_collection. simpl. reflexivity.
Qed.

(* =========================================================================
   Part 2: Native Abandonment, Multi-Class Holder Retirement, Guest Boundaries
   ========================================================================= *)

Inductive HolderClass : Type :=
| RunningHart
| SavedContext
| RegisteredHandle
| PeerCap
| QueuedReply
| OutstandingDma.

Definition holder_class_eqb (a b : HolderClass) : bool :=
  match a, b with
  | RunningHart, RunningHart => true
  | SavedContext, SavedContext => true
  | RegisteredHandle, RegisteredHandle => true
  | PeerCap, PeerCap => true
  | QueuedReply, QueuedReply => true
  | OutstandingDma, OutstandingDma => true
  | _, _ => false
  end.

Lemma holder_class_eqb_eq : forall a b,
  holder_class_eqb a b = true <-> a = b.
Proof.
  intros [] []; simpl; split; intro H; try reflexivity; try discriminate H.
Qed.

Record HolderEntry : Type := {
  he_class : HolderClass;
  he_ctx : nat;
  he_backing_id : ObjectId;
  he_active : bool
}.

Definition witness_HolderEntry : HolderEntry := {|
  he_class := OutstandingDma;
  he_ctx := 1;
  he_backing_id := witness_ObjectId;
  he_active := true
|}.

Inductive BackingPhase : Type :=
| BPLive
| BPQuarantined
| BPReusable.

Record GuestView : Type := {
  gv_epoch : nat;
  gv_obj : ObjectId;
  gv_base : nat;
  gv_len : nat;
  gv_live : bool
}.

Definition witness_GuestView : GuestView := {|
  gv_epoch := 0;
  gv_obj := witness_ObjectId;
  gv_base := 0;
  gv_len := 4;
  gv_live := true
|}.

Record RuntimeTeardownState : Type := {
  rts_backing : ObjectId;
  rts_phase : BackingPhase;
  rts_zeroized : bool;
  rts_holders : list HolderEntry;
  rts_abandoned : bool;
  rts_cleanup_frames_run : nat;
  rts_dtor_reclaims_run : nat;
  rts_native_frames_unwound : nat;
  rts_guest_views : list GuestView;
  rts_mem_epoch : nat
}.

Definition witness_RuntimeTeardownState : RuntimeTeardownState := {|
  rts_backing := witness_ObjectId;
  rts_phase := BPQuarantined;
  rts_zeroized := false;
  rts_holders := [
    {| he_class := RunningHart; he_ctx := 0; he_backing_id := witness_ObjectId; he_active := false |};
    {| he_class := SavedContext; he_ctx := 0; he_backing_id := witness_ObjectId; he_active := false |};
    {| he_class := RegisteredHandle; he_ctx := 1; he_backing_id := witness_ObjectId; he_active := true |};
    {| he_class := PeerCap; he_ctx := 2; he_backing_id := witness_ObjectId; he_active := false |};
    {| he_class := QueuedReply; he_ctx := 3; he_backing_id := witness_ObjectId; he_active := false |};
    {| he_class := OutstandingDma; he_ctx := 4; he_backing_id := witness_ObjectId; he_active := true |}
  ];
  rts_abandoned := false;
  rts_cleanup_frames_run := 0;
  rts_dtor_reclaims_run := 0;
  rts_native_frames_unwound := 0;
  rts_guest_views := [witness_GuestView];
  rts_mem_epoch := 0
|}.

(* Native abandonment: transitions backing to quarantine without running any user
   cleanup frames, without invoking destructors to return chunks/DMA loans, and
   without unwinding native frames. *)
Definition native_abandon (st : RuntimeTeardownState) : RuntimeTeardownState :=
  let next_phase :=
    match rts_phase st with
    | BPLive => BPQuarantined
    | BPQuarantined => BPQuarantined
    | BPReusable => BPReusable
    end in
  {| rts_backing := rts_backing st;
     rts_phase := next_phase;
     rts_zeroized := rts_zeroized st;
     rts_holders := rts_holders st;
     rts_abandoned := true;
     rts_cleanup_frames_run := rts_cleanup_frames_run st;
     rts_dtor_reclaims_run := rts_dtor_reclaims_run st;
     rts_native_frames_unwound := rts_native_frames_unwound st;
     rts_guest_views := rts_guest_views st;
     rts_mem_epoch := rts_mem_epoch st |}.

Theorem native_abandon_zero_cleanup_and_dtor : forall st,
  rts_cleanup_frames_run (native_abandon st) = rts_cleanup_frames_run st
  /\ rts_dtor_reclaims_run (native_abandon st) = rts_dtor_reclaims_run st
  /\ rts_native_frames_unwound (native_abandon st) = rts_native_frames_unwound st
  /\ rts_holders (native_abandon st) = rts_holders st
  /\ rts_abandoned (native_abandon st) = true.
Proof.
  intro st. unfold native_abandon. simpl.
  repeat split; reflexivity.
Qed.

(* Disabling a caller registration clears ONLY `RegisteredHandle` owned by
   `caller_ctx`; all other contexts' registrations and all other holder
   classes remain untouched. *)
Definition disable_caller_registration
    (st : RuntimeTeardownState) (caller_ctx : nat) : RuntimeTeardownState :=
  let updated :=
    map (fun h =>
      if holder_class_eqb (he_class h) RegisteredHandle
         && Nat.eqb (he_ctx h) caller_ctx
         && object_id_eqb (he_backing_id h) (rts_backing st)
      then {| he_class := he_class h;
              he_ctx := he_ctx h;
              he_backing_id := he_backing_id h;
              he_active := false |}
      else h) (rts_holders st) in
  {| rts_backing := rts_backing st;
     rts_phase := rts_phase st;
     rts_zeroized := rts_zeroized st;
     rts_holders := updated;
     rts_abandoned := rts_abandoned st;
     rts_cleanup_frames_run := rts_cleanup_frames_run st;
     rts_dtor_reclaims_run := rts_dtor_reclaims_run st;
     rts_native_frames_unwound := rts_native_frames_unwound st;
     rts_guest_views := rts_guest_views st;
     rts_mem_epoch := rts_mem_epoch st |}.

Theorem disable_caller_reg_preserves_other_holders : forall st caller_ctx h,
  In h (rts_holders st) ->
  (he_class h <> RegisteredHandle \/ he_ctx h <> caller_ctx) ->
  In h (rts_holders (disable_caller_registration st caller_ctx)).
Proof.
  intros st caller_ctx h Hin Hother.
  unfold disable_caller_registration. simpl.
  apply in_map_iff. exists h. split; [|exact Hin].
  destruct Hother as [Hcls | Hctx].
  - destruct (holder_class_eqb (he_class h) RegisteredHandle) eqn:E.
    + apply holder_class_eqb_eq in E. contradiction.
    + simpl. reflexivity.
  - destruct (Nat.eqb (he_ctx h) caller_ctx) eqn:E.
    + apply Nat.eqb_eq in E. contradiction.
    + rewrite andb_false_r. simpl. reflexivity.
Qed.

Definition retire_holder
    (st : RuntimeTeardownState) (cls : HolderClass) (ctx : nat)
    : RuntimeTeardownState :=
  let updated :=
    map (fun h =>
      if holder_class_eqb (he_class h) cls && Nat.eqb (he_ctx h) ctx
      then {| he_class := he_class h;
              he_ctx := he_ctx h;
              he_backing_id := he_backing_id h;
              he_active := false |}
      else h) (rts_holders st) in
  {| rts_backing := rts_backing st;
     rts_phase := rts_phase st;
     rts_zeroized := rts_zeroized st;
     rts_holders := updated;
     rts_abandoned := rts_abandoned st;
     rts_cleanup_frames_run := rts_cleanup_frames_run st;
     rts_dtor_reclaims_run := rts_dtor_reclaims_run st;
     rts_native_frames_unwound := rts_native_frames_unwound st;
     rts_guest_views := rts_guest_views st;
     rts_mem_epoch := rts_mem_epoch st |}.

Definition all_holders_retired (st : RuntimeTeardownState) : bool :=
  forallb (fun h => negb (he_active h)) (rts_holders st).

Definition phase_quarantined (p : BackingPhase) : bool :=
  match p with
  | BPQuarantined => true
  | BPLive | BPReusable => false
  end.

Definition try_zeroize_and_reuse
    (st : RuntimeTeardownState) (new_id : ObjectId)
    : RuntimeTeardownState * bool :=
  if phase_quarantined (rts_phase st) && all_holders_retired st then
    ({| rts_backing := new_id;
        rts_phase := BPReusable;
        rts_zeroized := true;
        rts_holders := rts_holders st;
        rts_abandoned := rts_abandoned st;
        rts_cleanup_frames_run := rts_cleanup_frames_run st;
        rts_dtor_reclaims_run := rts_dtor_reclaims_run st;
        rts_native_frames_unwound := rts_native_frames_unwound st;
        rts_guest_views := rts_guest_views st;
        rts_mem_epoch := rts_mem_epoch st |}, true)
  else
    (st, false).

Theorem reuse_refused_while_any_holder_active : forall st new_id h,
  In h (rts_holders st) ->
  he_active h = true ->
  try_zeroize_and_reuse st new_id = (st, false).
Proof.
  intros st new_id h Hin Hact.
  unfold try_zeroize_and_reuse, all_holders_retired.
  assert (Hforall : forallb (fun x => negb (he_active x)) (rts_holders st) = false).
  { destruct (forallb (fun x => negb (he_active x)) (rts_holders st)) eqn:E;
      [|reflexivity].
    rewrite forallb_forall in E. specialize (E h Hin).
    rewrite Hact in E. discriminate E. }
  rewrite Hforall, andb_false_r. reflexivity.
Qed.

Theorem quarantine_retained_until_all_retired : forall st new_id,
  rts_phase st = BPQuarantined ->
  rts_zeroized st = false ->
  all_holders_retired st = false ->
  let res := try_zeroize_and_reuse st new_id in
  snd res = false
  /\ rts_phase (fst res) = BPQuarantined
  /\ rts_zeroized (fst res) = false
  /\ rts_backing (fst res) = rts_backing st.
Proof.
  intros st new_id Hph Hzero Hnot.
  unfold try_zeroize_and_reuse. rewrite Hph, Hnot. simpl.
  repeat split; try assumption; reflexivity.
Qed.

Theorem reuse_succeeds_when_quarantined_and_all_retired : forall st new_id,
  rts_phase st = BPQuarantined ->
  all_holders_retired st = true ->
  let res := try_zeroize_and_reuse st new_id in
  snd res = true
  /\ rts_phase (fst res) = BPReusable
  /\ rts_zeroized (fst res) = true
  /\ rts_backing (fst res) = new_id.
Proof.
  intros st new_id Hph Hall.
  unfold try_zeroize_and_reuse. rewrite Hph, Hall. simpl.
  repeat split; reflexivity.
Qed.

(* Guest trap, cancel, or memory growth: never unwinds native frames, never runs
   user cleanup, and invalidates stale guest views on memory growth or trap. *)
Definition guest_trap_cancel_or_grow
    (st : RuntimeTeardownState) (grow_mem : bool) : RuntimeTeardownState :=
  let new_epoch := if grow_mem then S (rts_mem_epoch st) else rts_mem_epoch st in
  let views' :=
    map (fun gv =>
      {| gv_epoch := gv_epoch gv;
         gv_obj := gv_obj gv;
         gv_base := gv_base gv;
         gv_len := gv_len gv;
         gv_live := false |}) (rts_guest_views st) in
  {| rts_backing := rts_backing st;
     rts_phase := rts_phase st;
     rts_zeroized := rts_zeroized st;
     rts_holders := rts_holders st;
     rts_abandoned := rts_abandoned st;
     rts_cleanup_frames_run := rts_cleanup_frames_run st;
     rts_dtor_reclaims_run := rts_dtor_reclaims_run st;
     rts_native_frames_unwound := rts_native_frames_unwound st;
     rts_guest_views := views';
     rts_mem_epoch := new_epoch |}.

Theorem guest_event_never_unwinds_native_and_invalidates_stale : forall st grow_mem gv,
  let st' := guest_trap_cancel_or_grow st grow_mem in
  rts_native_frames_unwound st' = rts_native_frames_unwound st
  /\ rts_cleanup_frames_run st' = rts_cleanup_frames_run st
  /\ (In gv (rts_guest_views st') -> gv_live gv = false)
  /\ (grow_mem = true -> rts_mem_epoch st < rts_mem_epoch st').
Proof.
  intros st grow_mem gv. simpl.
  repeat split.
  - intro Hin. unfold guest_trap_cancel_or_grow in Hin. simpl in Hin.
    apply in_map_iff in Hin. destruct Hin as [orig [Heq _]].
    subst gv. reflexivity.
  - intro Hgrow. unfold guest_trap_cancel_or_grow. rewrite Hgrow. simpl. lia.
Qed.

(* =========================================================================
   Part 3: Concrete Refuting Constructions (R-05-165, R-05-166)
   ========================================================================= *)

(* 1. Foreign-string range splice: a range minted for oid1 (len 8) applied to
   oid2 (len 3) passes a defective object-ID-blind check of oid1's length,
   whereas `checked_slice_substr` rejects it. *)
Definition oid_1 : ObjectId := {| oid_gen := 1; oid_slot := 1 |}.
Definition oid_2 : ObjectId := {| oid_gen := 1; oid_slot := 2 |}.

Definition slice_short : SliceView := {|
  sv_obj := oid_2;
  sv_bytes := [65; 66; 67];
  sv_cap := 3;
  sv_len := 3;
  sv_init := 3
|}.

Definition foreign_range : ValidatedRange := {|
  vr_obj := oid_1;
  vr_start := 0;
  vr_end := 2;
  vr_require_utf8 := true
|}.

Example refute_foreign_range_splice :
  checked_slice_substr slice_short foreign_range = None.
Proof. reflexivity. Qed.

(* 2. Two-pass borrow mutation: callback shrinks `sv_init` from 4 to 1 between
   pass 1 and pass 2; `two_pass_extract` detects the shrinkage and refuses. *)
Definition shrinking_borrow_cb (pass : nat) : SliceView :=
  match pass with
  | 0 => {| sv_obj := witness_ObjectId; sv_bytes := [65; 66; 67; 68];
            sv_cap := 4; sv_len := 4; sv_init := 4 |}
  | _ => {| sv_obj := witness_ObjectId; sv_bytes := [65; 0; 0; 0];
            sv_cap := 4; sv_len := 1; sv_init := 1 |}
  end.

Example refute_two_pass_borrow_mutation :
  two_pass_extract shrinking_borrow_cb witness_ObjectId 4 = None.
Proof. reflexivity. Qed.

(* 3. Reentrant double-drop: reentrant callback is blocked while locked, and
   a second drop after the first drop returns an empty list with drop_count = 1. *)
Example refute_reentrant_double_drop :
  let st0 := witness_CollectionState in
  let st1 := fst (drop_collection st0) in
  let st2 := fst (drop_collection st1) in
  cs_drop_count st1 = 1
  /\ cs_drop_count st2 = 1
  /\ snd (drop_collection st1) = []
  /\ begin_callback (end_callback st0) <> None
  /\ begin_callback st1 = None.
Proof.
  simpl. repeat split; try reflexivity; discriminate.
Qed.

(* 4. Premature reuse with outstanding DMA / queued reply: even after
   disabling caller registration, active `OutstandingDma` or `QueuedReply`
   keeps backing quarantined and refuses reuse. *)
Example refute_premature_reuse_pending_dma_and_reply :
  let st_dma := disable_caller_registration witness_RuntimeTeardownState 1 in
  snd (try_zeroize_and_reuse st_dma oid_2) = false
  /\ rts_zeroized (fst (try_zeroize_and_reuse st_dma oid_2)) = false
  /\ let st_reply_only := retire_holder st_dma OutstandingDma 4 in
     snd (try_zeroize_and_reuse st_reply_only oid_2) = true.
Proof.
  simpl. repeat split; reflexivity.
Qed.

(* 5. Native abandonment runs zero cleanup frames and zero destructor reclaims,
   and leaves active DMA / queued reply intact for explicit barrier retirement. *)
Example refute_unwind_into_cleanup :
  let abandoned := native_abandon witness_RuntimeTeardownState in
  rts_cleanup_frames_run abandoned = 0
  /\ rts_dtor_reclaims_run abandoned = 0
  /\ rts_native_frames_unwound abandoned = 0
  /\ rts_phase abandoned = BPQuarantined.
Proof.
  simpl. repeat split; reflexivity.
Qed.

(* 6. Lying iterator length: `reported_len = 1000` with 1 item only grows
   `cs_init` and `cs_len` by 1, preserving `collection_inv`. *)
Example refute_lying_iterator_length :
  let st1 := iter_collect witness_CollectionState 1000 [67] in
  cs_init st1 = 3 /\ cs_len st1 = 3 /\ cs_cap st1 = 4.
Proof.
  simpl. repeat split; reflexivity.
Qed.

(* 7. Non-ASCII invalid UTF-8 byte sequence inside an otherwise in-bounds
   range is rejected by `checked_slice_substr`. *)
Definition slice_invalid_utf8 : SliceView := {|
  sv_obj := witness_ObjectId;
  sv_bytes := [255; 128; 65; 66];
  sv_cap := 4;
  sv_len := 4;
  sv_init := 4
|}.

Example refute_non_ascii_utf8_claim :
  checked_slice_substr slice_invalid_utf8 witness_ValidatedRange = None.
Proof. reflexivity. Qed.
