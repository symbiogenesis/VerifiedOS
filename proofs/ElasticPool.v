(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ElasticPool.v

   Executable history-indexed pool reference for R-08-047b and R-15-007k.
   Each step checks the new event only, and the prefix lemma proves that earlier
   grants retain their guarantees. This reference models the history-indexed
   producer specification; the finite-metadata host implementation in
   [elastic_pool.py](../tools/vos/elastic_pool.py) and the physical R-08-006
   reuse barrier are verified separately.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-08-006 R-08-047b R-15-007k
   SHA256: 626b50df8799150a7a87c3a4e85fab3d74e148629016b0f5f8f583fa4513df22
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Require Import CyclicExecutive MemoryPlan ElasticDomain.
Import ListNotations.
Local Open Scope nat_scope.

(* Defer evaluation of the equality to the kernel's VM cast check at Qed. *)
Local Ltac vm_reflexivity :=
  intros; lazymatch goal with |- _ = ?b => vm_cast_no_check (@eq_refl _ b) end.

Lemma pool_upto_in : forall n k, In k (upto n) -> k < n.
Proof.
  induction n as [|n IHn]; intros k H; simpl in H; [contradiction|].
  apply in_app_or in H. destruct H as [H|[H|H]].
  - specialize (IHn k H). lia.
  - subst. lia.
  - contradiction.
Qed.

Lemma pool_all_ext : forall (A : Type) (l : list A) f g,
  (forall x, In x l -> f x = g x) -> all_of f l = all_of g l.
Proof.
  intros A l; induction l as [|a l IHl]; intros f g H; simpl; auto.
  rewrite (H a (or_introl eq_refl)). f_equal. apply IHl.
  intros x Hx. apply H. now right.
Qed.

Lemma pool_any_ext : forall (A : Type) (l : list A) f g,
  (forall x, In x l -> f x = g x) -> any_of f l = any_of g l.
Proof.
  intros A l; induction l as [|a l IHl]; intros f g H; simpl; auto.
  rewrite (H a (or_introl eq_refl)). f_equal. apply IHl.
  intros x Hx. apply H. now right.
Qed.

Lemma pool_release_prefix : forall h tail b p q,
  q <= length h ->
  released_between (h ++ tail) b p q = released_between h b p q.
Proof.
  intros. unfold released_between. apply pool_any_ext. intros k Hk.
  apply pool_upto_in in Hk. rewrite nth_error_app1 by lia. reflexivity.
Qed.

Lemma pool_begun_prefix : forall h tail sp ep,
  ep <= length h -> begun_between (h ++ tail) sp ep = begun_between h sp ep.
Proof.
  intros. unfold begun_between. apply pool_any_ext. intros k Hk.
  apply pool_upto_in in Hk. rewrite nth_error_app1 by lia. reflexivity.
Qed.

Lemma pool_gate_prefix : forall h tail p q,
  q <= length h -> gate_passed (h ++ tail) p q = gate_passed h p q.
Proof.
  intros h tail p q Hq. unfold gate_passed.
  apply pool_any_ext. intros bp Hb. apply pool_upto_in in Hb.
  rewrite nth_error_app1 by lia. f_equal.
  apply pool_any_ext. intros sp Hs. apply pool_upto_in in Hs.
  rewrite nth_error_app1 by lia. f_equal.
  apply pool_any_ext. intros ep He. apply pool_upto_in in He.
  rewrite nth_error_app1 by lia. rewrite pool_begun_prefix by lia. reflexivity.
Qed.

Definition pool_point (a : Arena) (h : list AllocEvent) (q : nat) : bool :=
  disjoint_at a h q && exact_at a h q && zeroed_at a h q && reuse_ok_at a h q.

Lemma pool_point_prefix : forall a h tail q,
  q < length h -> pool_point a (h ++ tail) q = pool_point a h q.
Proof.
  intros a h tail q Hq. unfold pool_point.
  assert (Hd : disjoint_at a (h ++ tail) q = disjoint_at a h q).
  { unfold disjoint_at. rewrite nth_error_app1 by lia.
    destruct (nth_error h q) as [event|]; try reflexivity.
    destruct event; try reflexivity. apply pool_all_ext. intros p Hp.
    apply pool_upto_in in Hp. rewrite nth_error_app1 by lia.
    destruct (nth_error h p) as [old|]; try reflexivity.
    destruct old; try reflexivity. rewrite pool_release_prefix by lia. reflexivity. }
  assert (He : exact_at a (h ++ tail) q = exact_at a h q).
  { unfold exact_at. rewrite nth_error_app1 by lia. reflexivity. }
  assert (Hz : zeroed_at a (h ++ tail) q = zeroed_at a h q).
  { unfold zeroed_at. rewrite nth_error_app1 by lia.
    destruct (nth_error h q) as [event|]; try reflexivity.
    destruct event; try reflexivity. unfold memory_before.
    rewrite firstn_app. replace (q - length h) with 0 by lia.
    simpl. rewrite app_nil_r. reflexivity. }
  assert (Hr : reuse_ok_at a (h ++ tail) q = reuse_ok_at a h q).
  { unfold reuse_ok_at. rewrite nth_error_app1 by lia.
    destruct (nth_error h q) as [event|]; try reflexivity.
    destruct event; try reflexivity. apply pool_all_ext. intros p Hp.
    apply pool_upto_in in Hp. rewrite nth_error_app1 by lia.
    destruct (nth_error h p) as [old|]; try reflexivity.
    destruct old; try reflexivity. rewrite pool_gate_prefix by lia. reflexivity. }
  now rewrite Hd, He, Hz, Hr.
Qed.

Definition pool_event (a : Arena) (h : list AllocEvent) (e : AllocEvent)
  : list AllocEvent :=
  let candidate := h ++ [e] in
  if pool_point a candidate (length h) then candidate else h.

Fixpoint pool_run (a : Arena) (h : list AllocEvent) (events : list AllocEvent)
  : list AllocEvent :=
  match events with
  | [] => h
  | e :: rest => pool_run a (pool_event a h e) rest
  end.

Lemma pool_guarantees_points : forall a h,
  PoolGuarantees a h <->
  (forall q, q < length h -> pool_point a h q = true).
Proof.
  intros a h. unfold PoolGuarantees, LiveChunksDisjoint, BoundedExactly,
    ZeroedAtHandoff, ReusedOnlyAfterTheSweep, pool_point.
  split.
  - intros [Hd [He [Hz Hr]]] q Hq.
    assert (H : (q <? length h) = true) by now apply Nat.ltb_lt.
    now rewrite (Hd q H), (He q H), (Hz q H), (Hr q H).
  - intros H. repeat split; intros q Hq; apply Nat.ltb_lt in Hq;
      specialize (H q Hq); repeat rewrite andb_true_iff in H; tauto.
Qed.

Theorem pool_event_preserves_guarantees : forall a h e,
  PoolGuarantees a h -> PoolGuarantees a (pool_event a h e).
Proof.
  intros a h e Hsafe.
  pose proof ((proj1 (pool_guarantees_points a h)) Hsafe) as H.
  apply (proj2 (pool_guarantees_points a (pool_event a h e))). unfold pool_event.
  destruct (pool_point a (h ++ [e]) (length h)) eqn:E; [|exact H].
  intros q Hq. rewrite length_app in Hq. simpl in Hq.
  destruct (Nat.eq_dec q (length h)) as [->|Hne]; [exact E|].
  rewrite pool_point_prefix by lia. apply H. lia.
Qed.

(* This theorem quantifies every requested sequence, including malicious grants,
   writes and premature reuse. Rejected new events leave the old state intact. *)
Theorem pool_run_refines_four_guarantees : forall a events,
  PoolGuarantees a (pool_run a [] events).
Proof.
  intros a events.
  assert (H : forall events h, PoolGuarantees a h ->
      PoolGuarantees a (pool_run a h events)).
  { intro events0. induction events0 as [|e rest IH]; intros h Hh; simpl; auto.
    apply IH. now apply pool_event_preserves_guarantees. }
  apply H. apply (proj2 (pool_guarantees_points a [])).
  intros q Hq. simpl in Hq. lia.
Qed.

Theorem heap_run_narrows : forall chunk events,
  HeapNarrows chunk (pool_run chunk [] events).
Proof.
  intros chunk events. destruct (pool_run_refines_four_guarantees chunk events)
    as [Hd [He [Hz Hr]]]. exact (conj He (conj Hd Hr)).
Qed.

Theorem pool_checked_history : forall a h,
  all_of (pool_point a h) (upto (length h)) = true -> PoolGuarantees a h.
Proof.
  intros a h H. apply (proj2 (pool_guarantees_points a h)).
  intros q Hq. apply Nat.ltb_lt in Hq.
  exact (all_of_upto _ _ q H Hq).
Qed.

Definition pool_reference_arena : Arena := {|
  ar_base := 64; ar_span := 64;
  ar_classes := [{|sc_length := 16; sc_align := 16|};
                 {|sc_length := 32; sc_align := 32|}];
  ar_initial := fun _ => 19
|}.

Definition pool_reference_cycle : list AllocEvent :=
  [Zero 64 16; Grant 1 0 64 (chunk_cap 64 16); Write 64 7;
   Release 64 0; BarrierDone; SweepBegin; SweepEnd;
   Zero 64 16; Grant 2 0 64 (chunk_cap 64 16)].

Example pool_cycle_is_executable :
  pool_run pool_reference_arena [] pool_reference_cycle = pool_reference_cycle.
Proof. vm_reflexivity. Qed.

Example pool_classes_are_exact :
  all_of class_exact (ar_classes pool_reference_arena) = true.
Proof. reflexivity. Qed.

Example pool_rejects_overlap :
  pool_event pool_reference_arena
    [Zero 64 16; Grant 1 0 64 (chunk_cap 64 16)]
    (Grant 2 0 64 (chunk_cap 64 16)) =
    [Zero 64 16; Grant 1 0 64 (chunk_cap 64 16)].
Proof. reflexivity. Qed.

Example pool_rejects_wide_bounds :
  pool_event pool_reference_arena [Zero 64 16]
    (Grant 1 0 64 (chunk_cap 64 32)) = [Zero 64 16].
Proof. reflexivity. Qed.

Example pool_rejects_unzeroed_handoff :
  pool_event pool_reference_arena [] (Grant 1 0 64 (chunk_cap 64 16)) = [].
Proof. reflexivity. Qed.

Definition pool_early_prefix : list AllocEvent :=
  [Zero 64 16; Grant 1 0 64 (chunk_cap 64 16); Release 64 0;
   BarrierDone; SweepBegin; Zero 64 16].

Example pool_rejects_early_reuse :
  pool_event pool_reference_arena pool_early_prefix
    (Grant 2 0 64 (chunk_cap 64 16)) = pool_early_prefix.
Proof. reflexivity. Qed.

Definition pool_presweep_prefix : list AllocEvent :=
  [Zero 64 16; Grant 1 0 64 (chunk_cap 64 16); Release 64 0;
   SweepBegin; BarrierDone; SweepEnd; Zero 64 16].

Example pool_rejects_presweep_reuse :
  pool_event pool_reference_arena pool_presweep_prefix
    (Grant 2 0 64 (chunk_cap 64 16)) = pool_presweep_prefix.
Proof. reflexivity. Qed.

(* =========================================================================
   Finite Metadata Allocator and Universal Refinement (Q34c)

   Models the 5-phase, two-generation quarantine metadata state machine of
   [elastic_pool.py](../tools/vos/elastic_pool.py) over a composition-admitted
   fixed slot layout, and proves universally that every reachable history
   satisfies `PoolGuarantees` and `HeapNarrows`.
   ========================================================================= *)

Inductive SlotPhase : Type :=
| PFree
| PLive
| PPending
| PBarrier
| PSweeping.

Record SlotLayout : Type := {
  sl_base : nat;
  sl_class : nat;
  sl_len : nat
}.

Record MetaSlot : Type := {
  ms_layout : SlotLayout;
  ms_phase : SlotPhase;
  ms_zeroed : bool
}.

Record MetaState : Type := {
  ms_slots : list MetaSlot;
  ms_sweep_active : bool;
  ms_next_id : nat;
  ms_hist : list AllocEvent
}.

Definition witness_SlotLayout : SlotLayout := {|
  sl_base := 64; sl_class := 0; sl_len := 16
|}.

Definition witness_MetaSlot : MetaSlot := {|
  ms_layout := witness_SlotLayout; ms_phase := PFree; ms_zeroed := false
|}.

Definition witness_MetaState : MetaState := {|
  ms_slots := [witness_MetaSlot];
  ms_sweep_active := false;
  ms_next_id := 0;
  ms_hist := []
|}.

Definition slot_ok (a : Arena) (s : SlotLayout) : bool :=
  match nth_error (ar_classes a) (sl_class s) with
  | None => false
  | Some c =>
      class_exact c
      && Nat.eqb (sl_len s) (sc_length c)
      && Nat.eqb (sl_base s mod sc_align c) 0
      && Nat.leb (ar_base a) (sl_base s)
      && Nat.leb (sl_base s + sl_len s) (ar_base a + ar_span a)
  end.

(* Byte-level pairwise separation matching `extents_separate` geometry;
   8-byte revocation-granule separation in the Python reference is stronger
   and implies this byte-disjointness bound. *)
Definition slot_disjoint (s1 s2 : SlotLayout) : bool :=
  Nat.leb (sl_base s1 + sl_len s1) (sl_base s2)
  || Nat.leb (sl_base s2 + sl_len s2) (sl_base s1).

Fixpoint pairwise_disjoint (slots : list SlotLayout) : bool :=
  match slots with
  | [] => true
  | s :: rest => all_of (slot_disjoint s) rest && pairwise_disjoint rest
  end.

Definition layout_admitted (a : Arena) (slots : list SlotLayout) : Prop :=
  all_of (slot_ok a) slots = true /\ pairwise_disjoint slots = true.

Inductive MetaOp : Type :=
| OpAlloc (slot_idx : nat)
| OpWrite (slot_idx off val : nat)
| OpRelease (slot_idx : nat)
| OpBarrier
| OpSweepBegin
| OpSweepEnd.

Fixpoint replace_slot (idx : nat) (s : MetaSlot) (slots : list MetaSlot)
  : list MetaSlot :=
  match slots, idx with
  | [], _ => []
  | _ :: rest, 0 => s :: rest
  | hd :: rest, S n => hd :: replace_slot n s rest
  end.

Definition map_slot_phase (f : SlotPhase -> SlotPhase) (s : MetaSlot) : MetaSlot :=
  {| ms_layout := ms_layout s;
     ms_phase := f (ms_phase s);
     ms_zeroed := ms_zeroed s |}.

Definition barrier_phase (p : SlotPhase) : SlotPhase :=
  match p with
  | PPending => PBarrier
  | _ => p
  end.

Definition sweep_begin_phase (p : SlotPhase) : SlotPhase :=
  match p with
  | PBarrier => PSweeping
  | _ => p
  end.

Definition sweep_end_phase (p : SlotPhase) : SlotPhase :=
  match p with
  | PSweeping => PFree
  | _ => p
  end.

Definition meta_init (slots : list SlotLayout) : MetaState := {|
  ms_slots := map (fun l => {| ms_layout := l; ms_phase := PFree; ms_zeroed := false |}) slots;
  ms_sweep_active := false;
  ms_next_id := 0;
  ms_hist := []
|}.

Definition meta_step (_ : Arena) (st : MetaState) (op : MetaOp) : MetaState :=
  match op with
  | OpAlloc idx =>
      match nth_error (ms_slots st) idx with
      | Some s =>
          match ms_phase s with
          | PFree =>
              let l := ms_layout s in
              let s' := {| ms_layout := l; ms_phase := PLive; ms_zeroed := true |} in
              {| ms_slots := replace_slot idx s' (ms_slots st);
                 ms_sweep_active := ms_sweep_active st;
                 ms_next_id := S (ms_next_id st);
                 ms_hist := ms_hist st ++
                   [Zero (sl_base l) (sl_len l);
                    Grant (ms_next_id st) (sl_class l) (sl_base l)
                          (chunk_cap (sl_base l) (sl_len l))] |}
          | _ => st
          end
      | None => st
      end
  | OpWrite idx off val =>
      match nth_error (ms_slots st) idx with
      | Some s =>
          match ms_phase s with
          | PLive =>
              let l := ms_layout s in
              if Nat.ltb off (sl_len l)
              then let s' := {| ms_layout := l; ms_phase := PLive; ms_zeroed := false |} in
                   {| ms_slots := replace_slot idx s' (ms_slots st);
                      ms_sweep_active := ms_sweep_active st;
                      ms_next_id := ms_next_id st;
                      ms_hist := ms_hist st ++ [Write (sl_base l + off) val] |}
              else st
          | _ => st
          end
      | None => st
      end
  | OpRelease idx =>
      match nth_error (ms_slots st) idx with
      | Some s =>
          match ms_phase s with
          | PLive =>
              let l := ms_layout s in
              let s' := {| ms_layout := l; ms_phase := PPending; ms_zeroed := false |} in
              {| ms_slots := replace_slot idx s' (ms_slots st);
                 ms_sweep_active := ms_sweep_active st;
                 ms_next_id := ms_next_id st;
                 ms_hist := ms_hist st ++ [Release (sl_base l) (sl_class l)] |}
          | _ => st
          end
      | None => st
      end
  | OpBarrier =>
      {| ms_slots := map (map_slot_phase barrier_phase) (ms_slots st);
         ms_sweep_active := ms_sweep_active st;
         ms_next_id := ms_next_id st;
         ms_hist := ms_hist st ++ [BarrierDone] |}
  | OpSweepBegin =>
      if negb (ms_sweep_active st)
      then {| ms_slots := map (map_slot_phase sweep_begin_phase) (ms_slots st);
              ms_sweep_active := true;
              ms_next_id := ms_next_id st;
              ms_hist := ms_hist st ++ [SweepBegin] |}
      else st
  | OpSweepEnd =>
      if ms_sweep_active st
      then {| ms_slots := map (map_slot_phase sweep_end_phase) (ms_slots st);
              ms_sweep_active := false;
              ms_next_id := ms_next_id st;
              ms_hist := ms_hist st ++ [SweepEnd] |}
      else st
  end.

Fixpoint meta_run (a : Arena) (st : MetaState) (ops : list MetaOp) : MetaState :=
  match ops with
  | [] => st
  | op :: rest => meta_run a (meta_step a st op) rest
  end.

Definition slot_quarantine_inv
    (h : list AllocEvent) (sp_opt : option nat) (s : MetaSlot) : Prop :=
  let b := sl_base (ms_layout s) in
  match ms_phase s with
  | PFree =>
      (forall p w c k, p < length h ->
        nth_error h p = Some (Grant w c b k) ->
        released_between h b p (length h) = true) /\
      (forall p c, p < length h ->
        nth_error h p = Some (Release b c) ->
        gate_passed h p (length h) = true)
  | PLive =>
      forall p c, p < length h ->
        nth_error h p = Some (Release b c) ->
        gate_passed h p (length h) = true
  | PPending =>
      forall p w c k, p < length h ->
        nth_error h p = Some (Grant w c b k) ->
        released_between h b p (length h) = true
  | PBarrier =>
      (forall p w c k, p < length h ->
        nth_error h p = Some (Grant w c b k) ->
        released_between h b p (length h) = true) /\
      (exists bp, bp < length h /\ nth_error h bp = Some BarrierDone /\
        forall p c, p < length h -> nth_error h p = Some (Release b c) -> p < bp)
  | PSweeping =>
      (forall p w c k, p < length h ->
        nth_error h p = Some (Grant w c b k) ->
        released_between h b p (length h) = true) /\
      (exists sp bp, sp_opt = Some sp /\ bp < sp /\ sp < length h /\
        nth_error h bp = Some BarrierDone /\
        nth_error h sp = Some SweepBegin /\
        forall p c, p < length h -> nth_error h p = Some (Release b c) -> p < bp)
  end.

Definition meta_inv (a : Arena) (st : MetaState) : Prop :=
  let h := ms_hist st in
  layout_admitted a (map ms_layout (ms_slots st)) /\
  PoolGuarantees a h /\
  (forall p w c b k, p < length h ->
    nth_error h p = Some (Grant w c b k) ->
    exists i s, nth_error (ms_slots st) i = Some s /\
      sl_base (ms_layout s) = b /\ sl_class (ms_layout s) = c) /\
  (forall p b c, p < length h ->
    nth_error h p = Some (Release b c) ->
    exists i s, nth_error (ms_slots st) i = Some s /\
      sl_base (ms_layout s) = b /\ sl_class (ms_layout s) = c) /\
  (if ms_sweep_active st then
     exists sp,
       sp < length h /\
       nth_error h sp = Some SweepBegin /\
       (forall k, sp < k < length h -> nth_error h k <> Some SweepBegin) /\
       (forall j s, nth_error (ms_slots st) j = Some s ->
         slot_quarantine_inv h (Some sp) s)
   else
     forall j s, nth_error (ms_slots st) j = Some s ->
       slot_quarantine_inv h None s).

(* --- Helpers for layout, slots, and history prefixes --- *)

Lemma slot_disjoint_sym : forall s1 s2,
  slot_disjoint s1 s2 = true -> slot_disjoint s2 s1 = true.
Proof.
  intros s1 s2 H. unfold slot_disjoint in *.
  apply orb_true_iff in H. apply orb_true_iff.
  destruct H as [H|H]; [right|left]; exact H.
Qed.

Lemma pairwise_disjoint_nth : forall slots i j l1 l2,
  pairwise_disjoint slots = true ->
  nth_error slots i = Some l1 ->
  nth_error slots j = Some l2 ->
  i <> j ->
  slot_disjoint l1 l2 = true.
Proof.
  intro slots. induction slots as [|x rest IH]; intros i j l1 l2 Hpd Hi Hj Hne.
  - destruct i; discriminate Hi.
  - simpl in Hpd. apply andb_prop in Hpd. destruct Hpd as [Hx Hr].
    destruct i as [|i]; destruct j as [|j].
    + exfalso. apply Hne. reflexivity.
    + simpl in Hi, Hj. injection Hi as <-.
      apply all_of_in with (l := rest); [exact Hx|].
      eapply nth_error_In. exact Hj.
    + simpl in Hi, Hj. injection Hj as <-.
      apply slot_disjoint_sym.
      apply all_of_in with (l := rest); [exact Hx|].
      eapply nth_error_In. exact Hi.
    + simpl in Hi, Hj. apply (IH i j l1 l2 Hr Hi Hj). lia.
Qed.

Lemma slot_ok_props : forall a l,
  slot_ok a l = true ->
  exists c,
    nth_error (ar_classes a) (sl_class l) = Some c /\
    class_exact c = true /\
    sl_len l = sc_length c /\
    0 < sl_len l /\
    sl_base l mod sc_align c = 0 /\
    ar_base a <= sl_base l /\
    sl_base l + sl_len l <= ar_base a + ar_span a.
Proof.
  intros a l H. unfold slot_ok in H.
  destruct (nth_error (ar_classes a) (sl_class l)) as [c|] eqn:Ec; [|discriminate H].
  apply andb_prop in H. destruct H as [H Htop].
  apply andb_prop in H. destruct H as [H Hbot].
  apply andb_prop in H. destruct H as [H Hal].
  apply andb_prop in H. destruct H as [Hce Hlen].
  assert (Hpos : 0 < sc_length c).
  { unfold class_exact in Hce. cbv zeta in Hce.
    apply andb_prop in Hce. destruct Hce as [Hce _].
    apply andb_prop in Hce. destruct Hce as [Hce _].
    apply andb_prop in Hce. destruct Hce as [Hlt _].
    apply Nat.ltb_lt. exact Hlt. }
  apply Nat.eqb_eq in Hlen. apply Nat.eqb_eq in Hal.
  apply Nat.leb_le in Hbot. apply Nat.leb_le in Htop.
  exists c. repeat split; try assumption; lia.
Qed.

Lemma slot_ok_class_len : forall a l,
  slot_ok a l = true ->
  class_len a (sl_class l) = sl_len l.
Proof.
  intros a l H. apply slot_ok_props in H.
  destruct H as [c [Ec [_ [Hlen _]]]].
  unfold class_len. rewrite Ec. symmetry. exact Hlen.
Qed.

Lemma slot_disjoint_no_overlap : forall a l1 l2,
  slot_ok a l1 = true ->
  slot_ok a l2 = true ->
  slot_disjoint l1 l2 = true ->
  overlaps (sl_base l1) (class_len a (sl_class l1))
           (sl_base l2) (class_len a (sl_class l2)) = false.
Proof.
  intros a l1 l2 Hok1 Hok2 Hdis.
  rewrite (slot_ok_class_len a l1 Hok1), (slot_ok_class_len a l2 Hok2).
  unfold slot_disjoint, overlaps in *.
  apply orb_true_iff in Hdis. apply andb_false_iff.
  destruct Hdis as [H|H]; apply Nat.leb_le in H; [right|left]; apply Nat.ltb_ge; exact H.
Qed.

Lemma slot_disjoint_distinct_base : forall a l1 l2,
  slot_ok a l1 = true ->
  slot_ok a l2 = true ->
  slot_disjoint l1 l2 = true ->
  sl_base l1 <> sl_base l2.
Proof.
  intros a l1 l2 Hok1 Hok2 Hdis.
  apply slot_ok_props in Hok1. destruct Hok1 as [_ [_ [_ [_ [Hp1 _]]]]].
  apply slot_ok_props in Hok2. destruct Hok2 as [_ [_ [_ [_ [Hp2 _]]]]].
  unfold slot_disjoint in Hdis. apply orb_true_iff in Hdis.
  destruct Hdis as [H|H]; apply Nat.leb_le in H; lia.
Qed.

Lemma layout_admitted_slot_ok : forall a slots i l,
  layout_admitted a slots ->
  nth_error slots i = Some l ->
  slot_ok a l = true.
Proof.
  intros a slots i l [Hok _] Hi.
  eapply all_of_in; [exact Hok|]. eapply nth_error_In. exact Hi.
Qed.

Lemma layout_admitted_disjoint : forall a slots i j l1 l2,
  layout_admitted a slots ->
  nth_error slots i = Some l1 ->
  nth_error slots j = Some l2 ->
  i <> j ->
  slot_disjoint l1 l2 = true.
Proof.
  intros a slots i j l1 l2 [_ Hpd] Hi Hj Hne.
  exact (pairwise_disjoint_nth slots i j l1 l2 Hpd Hi Hj Hne).
Qed.

Lemma replace_slot_map_layout : forall idx s old slots,
  nth_error slots idx = Some old ->
  ms_layout s = ms_layout old ->
  map ms_layout (replace_slot idx s slots) = map ms_layout slots.
Proof.
  intro idx. induction idx as [|idx IH]; intros s old slots Hnth Hlay.
  - destruct slots as [|hd tl]; [discriminate Hnth|].
    simpl in Hnth. injection Hnth as <-. simpl. rewrite Hlay. reflexivity.
  - destruct slots as [|hd tl]; [discriminate Hnth|].
    simpl in Hnth. simpl. f_equal. eapply IH; [exact Hnth|exact Hlay].
Qed.

Lemma nth_error_replace_slot_eq : forall idx s old slots,
  nth_error slots idx = Some old ->
  nth_error (replace_slot idx s slots) idx = Some s.
Proof.
  intro idx. induction idx as [|idx IH]; intros s old slots Hnth.
  - destruct slots; [discriminate Hnth|]. reflexivity.
  - destruct slots; [discriminate Hnth|]. simpl in *. eapply IH. exact Hnth.
Qed.

Lemma nth_error_replace_slot_ne : forall idx j s slots,
  j <> idx ->
  nth_error (replace_slot idx s slots) j = nth_error slots j.
Proof.
  intro idx. induction idx as [|idx IH]; intros j s slots Hne.
  - destruct slots; destruct j; simpl; try reflexivity.
    exfalso. apply Hne. reflexivity.
  - destruct slots; destruct j; simpl; try reflexivity.
    apply IH. lia.
Qed.

Lemma map_slot_phase_layout : forall f slots,
  map ms_layout (map (map_slot_phase f) slots) = map ms_layout slots.
Proof.
  intros f slots. induction slots as [|s rest IH]; simpl; [reflexivity|].
  unfold map_slot_phase at 1. simpl. f_equal. exact IH.
Qed.

Lemma released_between_app : forall h tail b p q,
  q <= length h ->
  released_between h b p q = true ->
  released_between (h ++ tail) b p (q + length tail) = true.
Proof.
  intros h tail b p q Hq H.
  unfold released_between in *.
  apply any_of_in in H. destruct H as [k [Hk Hcond]].
  apply upto_in in Hk.
  apply andb_prop in Hcond. destruct Hcond as [Hbounds Hrel].
  apply andb_prop in Hbounds. destruct Hbounds as [Hpk Hkq].
  apply any_of_upto_intro with (v := k).
  - apply Nat.ltb_lt. lia.
  - rewrite nth_error_app1 by lia.
    apply andb_true_intro. split; [|exact Hrel].
    apply andb_true_intro. split; [exact Hpk|].
    apply Nat.ltb_lt. lia.
Qed.

Lemma gate_passed_app : forall h tail p q,
  q <= length h ->
  gate_passed h p q = true ->
  gate_passed (h ++ tail) p (q + length tail) = true.
Proof.
  intros h tail p q Hq H.
  assert (Hext : q + length tail <= length (h ++ tail)).
  { rewrite length_app. lia. }
  unfold gate_passed in H.
  apply any_of_in in H. destruct H as [bp [Hbp Hb]].
  apply upto_in in Hbp.
  apply andb_prop in Hb. destruct Hb as [Hb Hs].
  apply andb_prop in Hb. destruct Hb as [Hpb Hbar].
  apply any_of_in in Hs. destruct Hs as [sp [Hsp Hs2]].
  apply upto_in in Hsp.
  apply andb_prop in Hs2. destruct Hs2 as [Hs2 He].
  apply andb_prop in Hs2. destruct Hs2 as [Hbs Hbeg].
  apply any_of_in in He. destruct He as [ep [Hep He2]].
  apply upto_in in Hep.
  apply andb_prop in He2. destruct He2 as [He2 Hnb].
  apply andb_prop in He2. destruct He2 as [Hse Hend].
  apply any_of_upto_intro with (v := bp).
  - apply Nat.ltb_lt. lia.
  - apply andb_true_intro. split.
    + apply andb_true_intro. split; [exact Hpb|].
      rewrite nth_error_app1 by lia. exact Hbar.
    + apply any_of_upto_intro with (v := sp).
      * apply Nat.ltb_lt. lia.
      * apply andb_true_intro. split.
        -- apply andb_true_intro. split; [exact Hbs|].
           rewrite nth_error_app1 by lia. exact Hbeg.
        -- apply any_of_upto_intro with (v := ep).
           ++ apply Nat.ltb_lt. lia.
           ++ apply andb_true_intro. split.
              ** apply andb_true_intro. split; [exact Hse|].
                 rewrite nth_error_app1 by lia. exact Hend.
              ** rewrite pool_begun_prefix by lia. exact Hnb.
Qed.

Lemma gate_passed_intro : forall h p bp sp ep q,
  p < bp -> bp < sp -> sp < ep -> ep < q ->
  nth_error h bp = Some BarrierDone ->
  nth_error h sp = Some SweepBegin ->
  nth_error h ep = Some SweepEnd ->
  (forall k, sp < k < ep -> nth_error h k <> Some SweepBegin) ->
  gate_passed h p q = true.
Proof.
  intros h p bp sp ep q Hpb Hbs Hse Heq Hbar Hbeg Hend Hnobeg.
  unfold gate_passed.
  apply any_of_upto_intro with (v := bp); [apply Nat.ltb_lt; lia|].
  apply andb_true_intro. split.
  - apply andb_true_intro. split; [apply Nat.ltb_lt; exact Hpb|].
    unfold is_barrier. rewrite Hbar. reflexivity.
  - apply any_of_upto_intro with (v := sp); [apply Nat.ltb_lt; lia|].
    apply andb_true_intro. split.
    + apply andb_true_intro. split; [apply Nat.ltb_lt; exact Hbs|].
      unfold is_sweep_begin. rewrite Hbeg. reflexivity.
    + apply any_of_upto_intro with (v := ep); [apply Nat.ltb_lt; lia|].
      apply andb_true_intro. split.
      * apply andb_true_intro. split; [apply Nat.ltb_lt; exact Hse|].
        unfold is_sweep_end. rewrite Hend. reflexivity.
      * apply negb_true_iff.
        destruct (begun_between h sp ep) eqn:Ebeg; [|reflexivity].
        unfold begun_between in Ebeg. apply any_of_in in Ebeg.
        destruct Ebeg as [k [Hk Hcond]]. apply upto_in in Hk.
        apply andb_prop in Hcond. destruct Hcond as [Hbounds Hsb].
        apply andb_prop in Hbounds. destruct Hbounds as [Hsk Hke].
        apply Nat.ltb_lt in Hsk. apply Nat.ltb_lt in Hke.
        exfalso. apply (Hnobeg k (conj Hsk Hke)).
        unfold is_sweep_begin in Hsb.
        destruct (nth_error h k) as [ev|]; [|discriminate Hsb].
        destruct ev; try discriminate Hsb. reflexivity.
Qed.

Lemma pool_guarantees_step : forall a h e,
  PoolGuarantees a h ->
  pool_point a (h ++ [e]) (length h) = true ->
  PoolGuarantees a (h ++ [e]).
Proof.
  intros a h e Hsafe Hpt.
  pose proof ((proj1 (pool_guarantees_points a h)) Hsafe) as Hpts.
  apply (proj2 (pool_guarantees_points a (h ++ [e]))).
  intros q Hq. rewrite length_app in Hq. simpl in Hq.
  destruct (Nat.eq_dec q (length h)) as [->|Hne]; [exact Hpt|].
  rewrite pool_point_prefix by lia. apply Hpts. lia.
Qed.

Lemma pool_point_non_grant : forall a h e,
  match e with Grant _ _ _ _ => False | _ => True end ->
  pool_point a (h ++ [e]) (length h) = true.
Proof.
  intros a h e Hng.
  assert (Hnth : nth_error (h ++ [e]) (length h) = Some e).
  { rewrite nth_error_app2 by lia. replace (length h - length h) with 0 by lia. reflexivity. }
  unfold pool_point, disjoint_at, exact_at, zeroed_at, reuse_ok_at.
  rewrite Hnth. destruct e; try contradiction; reflexivity.
Qed.

Lemma meta_quarantine_app_inert : forall h tail sp_opt s,
  (forall p w c k, length h <= p < length (h ++ tail) ->
    nth_error (h ++ tail) p = Some (Grant w c (sl_base (ms_layout s)) k) -> False) ->
  (forall p c, length h <= p < length (h ++ tail) ->
    nth_error (h ++ tail) p = Some (Release (sl_base (ms_layout s)) c) -> False) ->
  slot_quarantine_inv h sp_opt s ->
  slot_quarantine_inv (h ++ tail) sp_opt s.
Proof.
  intros h tail sp_opt s Hng Hnr Hinv.
  unfold slot_quarantine_inv in *.
  destruct (ms_phase s) eqn:Ephase; simpl in *.
  - destruct Hinv as [Hg Hr]. split.
    + intros p w c k Hp Hnth.
      destruct (le_lt_dec (length h) p) as [Hge|Hlt].
      * exfalso. eapply Hng; [split; [exact Hge|exact Hp]|exact Hnth].
      * rewrite nth_error_app1 in Hnth by exact Hlt.
        rewrite length_app. apply released_between_app; [lia|].
        exact (Hg p w c k Hlt Hnth).
    + intros p c Hp Hnth.
      destruct (le_lt_dec (length h) p) as [Hge|Hlt].
      * exfalso. eapply Hnr; [split; [exact Hge|exact Hp]|exact Hnth].
      * rewrite nth_error_app1 in Hnth by exact Hlt.
        rewrite length_app. apply gate_passed_app; [lia|].
        exact (Hr p c Hlt Hnth).
  - intros p c Hp Hnth.
    destruct (le_lt_dec (length h) p) as [Hge|Hlt].
    + exfalso. eapply Hnr; [split; [exact Hge|exact Hp]|exact Hnth].
    + rewrite nth_error_app1 in Hnth by exact Hlt.
      rewrite length_app. apply gate_passed_app; [lia|].
      exact (Hinv p c Hlt Hnth).
  - intros p w c k Hp Hnth.
    destruct (le_lt_dec (length h) p) as [Hge|Hlt].
    + exfalso. eapply Hng; [split; [exact Hge|exact Hp]|exact Hnth].
    + rewrite nth_error_app1 in Hnth by exact Hlt.
      rewrite length_app. apply released_between_app; [lia|].
      exact (Hinv p w c k Hlt Hnth).
  - destruct Hinv as [Hg [bp [Hbp [Hbar Hrel]]]]. split.
    + intros p w c k Hp Hnth.
      destruct (le_lt_dec (length h) p) as [Hge|Hlt].
      * exfalso. eapply Hng; [split; [exact Hge|exact Hp]|exact Hnth].
      * rewrite nth_error_app1 in Hnth by exact Hlt.
        rewrite length_app. apply released_between_app; [lia|].
        exact (Hg p w c k Hlt Hnth).
    + exists bp. split; [rewrite length_app; lia|].
      split; [rewrite nth_error_app1 by exact Hbp; exact Hbar|].
      intros p c Hp Hnth.
      destruct (le_lt_dec (length h) p) as [Hge|Hlt].
      * exfalso. eapply Hnr; [split; [exact Hge|exact Hp]|exact Hnth].
      * rewrite nth_error_app1 in Hnth by exact Hlt.
        exact (Hrel p c Hlt Hnth).
  - destruct Hinv as [Hg [sp [bp [Hsp [Hbs [Hsl [Hbar [Hbeg Hrel]]]]]]]]. split.
    + intros p w c k Hp Hnth.
      destruct (le_lt_dec (length h) p) as [Hge|Hlt].
      * exfalso. eapply Hng; [split; [exact Hge|exact Hp]|exact Hnth].
      * rewrite nth_error_app1 in Hnth by exact Hlt.
        rewrite length_app. apply released_between_app; [lia|].
        exact (Hg p w c k Hlt Hnth).
    + exists sp, bp. repeat split; try assumption.
      * rewrite length_app. lia.
      * rewrite nth_error_app1 by lia. exact Hbar.
      * rewrite nth_error_app1 by exact Hsl. exact Hbeg.
      * intros p c Hp Hnth.
        destruct (le_lt_dec (length h) p) as [Hge|Hlt].
        -- exfalso. eapply Hnr; [split; [exact Hge|exact Hp]|exact Hnth].
        -- rewrite nth_error_app1 in Hnth by exact Hlt.
           exact (Hrel p c Hlt Hnth).
Qed.

Lemma meta_quarantine_app_single_inert : forall h e sp_opt s,
  (match e with Grant _ _ b _ => b <> sl_base (ms_layout s) | _ => True end) ->
  (match e with Release b _ => b <> sl_base (ms_layout s) | _ => True end) ->
  slot_quarantine_inv h sp_opt s ->
  slot_quarantine_inv (h ++ [e]) sp_opt s.
Proof.
  intros h e sp_opt s Hng Hnr Hinv.
  apply meta_quarantine_app_inert; [| |exact Hinv].
  - intros p w c k Hp Hnth. rewrite length_app in Hp. simpl in Hp.
    assert (Hp_eq : p = length h) by lia. subst p.
    rewrite nth_error_app2 in Hnth by lia.
    replace (length h - length h) with 0 in Hnth by lia. simpl in Hnth.
    injection Hnth as He. destruct e; try discriminate He.
    injection He as _ _ Hb _. apply Hng. exact Hb.
  - intros p c Hp Hnth. rewrite length_app in Hp. simpl in Hp.
    assert (Hp_eq : p = length h) by lia. subst p.
    rewrite nth_error_app2 in Hnth by lia.
    replace (length h - length h) with 0 in Hnth by lia. simpl in Hnth.
    injection Hnth as He. destruct e; try discriminate He.
    injection He as Hb _. apply Hnr. exact Hb.
Qed.

Lemma meta_init_map_layout : forall slots,
  map ms_layout
    (map (fun l => {| ms_layout := l; ms_phase := PFree; ms_zeroed := false |}) slots)
  = slots.
Proof.
  intro slots. induction slots as [|l rest IH]; simpl; [reflexivity|].
  f_equal. exact IH.
Qed.

Theorem meta_init_inv : forall a slots,
  layout_admitted a slots -> meta_inv a (meta_init slots).
Proof.
  intros a slots Hladm. unfold meta_inv, meta_init. simpl.
  rewrite meta_init_map_layout.
  split; [exact Hladm|].
  split; [apply (proj2 (pool_guarantees_points a [])); intros q Hq; simpl in Hq; lia|].
  split; [intros p w c b k Hp; simpl in Hp; lia|].
  split; [intros p b c Hp; simpl in Hp; lia|].
  intros j s Hnth. rewrite nth_error_map in Hnth.
  destruct (nth_error slots j) as [l|]; [|discriminate Hnth].
  injection Hnth as <-. simpl. split; intros p; simpl; lia.
Qed.

Theorem meta_step_preserves_inv : forall a st op,
  meta_inv a st -> meta_inv a (meta_step a st op).
Proof.
  intros a st op Hinv.
  destruct Hinv as [Hladm [Hguar [HprovG [HprovR Hquar]]]].
  destruct op as [idx | idx off val | idx | | |]; simpl.
  - (* OpAlloc idx *)
    destruct (nth_error (ms_slots st) idx) as [s|] eqn:Eslot;
      [|exact (conj Hladm (conj Hguar (conj HprovG (conj HprovR Hquar))))].
    destruct (ms_phase s) eqn:Ephase;
      try exact (conj Hladm (conj Hguar (conj HprovG (conj HprovR Hquar)))).
    set (l := ms_layout s).
    set (s' := {| ms_layout := l; ms_phase := PLive; ms_zeroed := true |}).
    set (slots' := replace_slot idx s' (ms_slots st)).
    set (h := ms_hist st).
    set (h1 := h ++ [Zero (sl_base l) (sl_len l)]).
    set (evG := Grant (ms_next_id st) (sl_class l) (sl_base l)
                      (chunk_cap (sl_base l) (sl_len l))).
    set (h2 := h ++ [Zero (sl_base l) (sl_len l); evG]).
    assert (Hh2_eq : h2 = h1 ++ [evG]).
    { unfold h2, h1. rewrite <- app_assoc. reflexivity. }
    assert (Hlay_nth : nth_error (map ms_layout (ms_slots st)) idx = Some l).
    { rewrite nth_error_map, Eslot. reflexivity. }
    assert (Hok_s : slot_ok a l = true).
    { eapply layout_admitted_slot_ok; [exact Hladm|exact Hlay_nth]. }
    assert (Hlen_c : class_len a (sl_class l) = sl_len l).
    { exact (slot_ok_class_len a l Hok_s). }
    assert (Hguar1 : PoolGuarantees a h1).
    { apply pool_guarantees_step; [exact Hguar|].
      apply pool_point_non_grant. exact I. }
    assert (Hs_quar :
      (forall p w c k, p < length h ->
        nth_error h p = Some (Grant w c (sl_base l) k) ->
        released_between h (sl_base l) p (length h) = true) /\
      (forall p c, p < length h ->
        nth_error h p = Some (Release (sl_base l) c) ->
        gate_passed h p (length h) = true)).
    { destruct (ms_sweep_active st) eqn:Esw.
      - destruct Hquar as [sp [_ [_ [_ Hfor]]]].
        pose proof (Hfor idx s Eslot) as Hq. unfold slot_quarantine_inv in Hq. rewrite Ephase in Hq.
        exact Hq.
      - pose proof (Hquar idx s Eslot) as Hq. unfold slot_quarantine_inv in Hq. rewrite Ephase in Hq.
        exact Hq. }
    destruct Hs_quar as [Hs_rel Hs_gate].
    assert (Hpt2 : pool_point a (h1 ++ [evG]) (length h1) = true).
    { assert (Hnth_evG : nth_error (h1 ++ [evG]) (length h1) = Some evG).
      { rewrite nth_error_app2 by lia. replace (length h1 - length h1) with 0 by lia. reflexivity. }
      assert (Hdis : disjoint_at a (h1 ++ [evG]) (length h1) = true).
      { unfold disjoint_at. rewrite Hnth_evG.
        apply all_of_upto_intro. intros p Hp. apply Nat.ltb_lt in Hp.
        destruct (nth_error (h1 ++ [evG]) p) as [old|] eqn:Eold; [|reflexivity].
        destruct old as [w1 c1 b1 k1| | | | | |]; try reflexivity.
        assert (Hp_h : p < length h).
        { assert (Hp_h1 : p < length h1) by exact Hp.
          unfold h1 in Hp_h1. rewrite length_app in Hp_h1. simpl in Hp_h1.
          destruct (Nat.eq_dec p (length h)) as [->|Hne]; [|lia].
          rewrite nth_error_app1 in Eold by (unfold h1; rewrite length_app; simpl; lia).
          unfold h1 in Eold. rewrite nth_error_app2 in Eold by lia.
          replace (length h - length h) with 0 in Eold by lia. simpl in Eold.
          discriminate Eold. }
        rewrite nth_error_app1 in Eold by (unfold h1; rewrite length_app; simpl; lia).
        unfold h1 in Eold. rewrite nth_error_app1 in Eold by exact Hp_h.
        destruct (HprovG p w1 c1 b1 k1 Hp_h Eold) as [i [s1 [Es1 [Hb1 Hc1]]]].
        apply orb_true_intro. destruct (Nat.eq_dec i idx) as [->|Hne].
        - left. rewrite Eslot in Es1. injection Es1 as <-.
          rewrite pool_release_prefix by lia.
          unfold h1. rewrite length_app. apply released_between_app; [lia|].
          rewrite <- Hb1. exact (Hs_rel p w1 c1 k1 Hp_h (eq_ind_r (fun x => nth_error h p = Some (Grant w1 c1 x k1)) Eold Hb1)).
        - right. apply negb_true_iff.
          assert (Hl1 : nth_error (map ms_layout (ms_slots st)) i = Some (ms_layout s1)).
          { rewrite nth_error_map, Es1. reflexivity. }
          assert (Hok1 : slot_ok a (ms_layout s1) = true).
          { eapply layout_admitted_slot_ok; [exact Hladm|exact Hl1]. }
          assert (Hdis1 : slot_disjoint (ms_layout s1) l = true).
          { eapply layout_admitted_disjoint; [exact Hladm|exact Hl1|exact Hlay_nth|exact Hne]. }
          rewrite <- Hb1, <- Hc1.
          exact (slot_disjoint_no_overlap a (ms_layout s1) l Hok1 Hok_s Hdis1). }
      assert (Hex : exact_at a (h1 ++ [evG]) (length h1) = true).
      { unfold exact_at. rewrite Hnth_evG. unfold evG, grant_exact.
        apply slot_ok_props in Hok_s.
        destruct Hok_s as [c [Ec [Hce [Hlen [_ [Hal [Hbot Htop]]]]]]].
        rewrite Ec. unfold chunk_cap. simpl.
        apply andb_true_intro; split; [|apply Nat.leb_le; rewrite <- Hlen; exact Htop].
        apply andb_true_intro; split; [|apply Nat.leb_le; exact Hbot].
        apply andb_true_intro; split; [|apply Nat.eqb_eq; exact Hlen].
        apply andb_true_intro; split; [|apply Nat.eqb_eq; reflexivity].
        apply andb_true_intro; split; [exact Hce|apply Nat.eqb_eq; exact Hal]. }
      assert (Hzero : zeroed_at a (h1 ++ [evG]) (length h1) = true).
      { unfold zeroed_at. rewrite Hnth_evG.
        apply all_of_upto_intro. intros off Hoff. apply Nat.ltb_lt in Hoff.
        rewrite Hlen_c in Hoff. apply Nat.eqb_eq.
        unfold memory_before.
        rewrite firstn_app. replace (length h1 - length h1) with 0 by lia.
        simpl. rewrite app_nil_r, firstn_all.
        unfold h1. rewrite fold_left_app. simpl.
        replace ((sl_base l <=? sl_base l + off) && (sl_base l + off <? sl_base l + sl_len l))
          with true; [reflexivity|].
        symmetry. apply andb_true_intro; split; [apply Nat.leb_le; lia|apply Nat.ltb_lt; lia]. }
      assert (Hreuse : reuse_ok_at a (h1 ++ [evG]) (length h1) = true).
      { unfold reuse_ok_at. rewrite Hnth_evG.
        apply all_of_upto_intro. intros p Hp. apply Nat.ltb_lt in Hp.
        destruct (nth_error (h1 ++ [evG]) p) as [old|] eqn:Eold; [|reflexivity].
        destruct old as [ |b1 c1| | | | |]; try reflexivity.
        assert (Hp_h : p < length h).
        { unfold h1 in Hp. rewrite length_app in Hp. simpl in Hp.
          destruct (Nat.eq_dec p (length h)) as [->|Hne]; [|lia].
          rewrite nth_error_app1 in Eold by (unfold h1; rewrite length_app; simpl; lia).
          unfold h1 in Eold. rewrite nth_error_app2 in Eold by lia.
          replace (length h - length h) with 0 in Eold by lia. simpl in Eold.
          discriminate Eold. }
        rewrite nth_error_app1 in Eold by (unfold h1; rewrite length_app; simpl; lia).
        unfold h1 in Eold. rewrite nth_error_app1 in Eold by exact Hp_h.
        destruct (HprovR p b1 c1 Hp_h Eold) as [i [s1 [Es1 [Hb1 Hc1]]]].
        apply orb_true_intro. destruct (Nat.eq_dec i idx) as [->|Hne].
        - right. rewrite Eslot in Es1. injection Es1 as <-.
          rewrite pool_gate_prefix by lia.
          unfold h1. rewrite length_app. apply gate_passed_app; [lia|].
          exact (Hs_gate p c1 Hp_h (eq_ind_r (fun x => nth_error h p = Some (Release x c1)) Eold Hb1)).
        - left. apply negb_true_iff.
          assert (Hl1 : nth_error (map ms_layout (ms_slots st)) i = Some (ms_layout s1)).
          { rewrite nth_error_map, Es1. reflexivity. }
          assert (Hok1 : slot_ok a (ms_layout s1) = true).
          { eapply layout_admitted_slot_ok; [exact Hladm|exact Hl1]. }
          assert (Hdis1 : slot_disjoint (ms_layout s1) l = true).
          { eapply layout_admitted_disjoint; [exact Hladm|exact Hl1|exact Hlay_nth|exact Hne]. }
          rewrite <- Hb1, <- Hc1.
          exact (slot_disjoint_no_overlap a (ms_layout s1) l Hok1 Hok_s Hdis1). }
      unfold pool_point. rewrite Hdis, Hex, Hzero, Hreuse. reflexivity. }
    assert (Hguar2 : PoolGuarantees a h2).
    { rewrite Hh2_eq. exact (pool_guarantees_step a h1 evG Hguar1 Hpt2). }
    assert (Hladm' : layout_admitted a (map ms_layout slots')).
    { unfold slots'. rewrite (replace_slot_map_layout idx s' s _ Eslot eq_refl). exact Hladm. }
    assert (HprovG' : forall p w c b k, p < length h2 ->
      nth_error h2 p = Some (Grant w c b k) ->
      exists i s0, nth_error slots' i = Some s0 /\
        sl_base (ms_layout s0) = b /\ sl_class (ms_layout s0) = c).
    { intros p w c b k Hp Hnth. unfold h2 in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (le_lt_dec (length h) p) as [Hge|Hlt].
      - destruct (Nat.eq_dec p (length h)) as [->|Hne].
        + rewrite nth_error_app2 in Hnth by lia.
          replace (length h - length h) with 0 in Hnth by lia. simpl in Hnth.
          discriminate Hnth.
        + assert (Hp_eq : p = S (length h)) by lia. subst p.
          rewrite nth_error_app2 in Hnth by lia.
          replace (S (length h) - length h) with 1 in Hnth by lia. simpl in Hnth.
          injection Hnth as _ <- <- _.
          exists idx, s'. split; [exact (nth_error_replace_slot_eq idx s' s _ Eslot)|].
          split; reflexivity.
      - rewrite nth_error_app1 in Hnth by exact Hlt.
        destruct (HprovG p w c b k Hlt Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        destruct (Nat.eq_dec i idx) as [->|Hne].
        + rewrite Eslot in Es0. injection Es0 as <-.
          exists idx, s'. split; [exact (nth_error_replace_slot_eq idx s' s _ Eslot)|].
          split; assumption.
        + exists i, s0. split; [unfold slots'; rewrite (nth_error_replace_slot_ne idx i s' _ Hne); exact Es0|].
          split; assumption. }
    assert (HprovR' : forall p b c, p < length h2 ->
      nth_error h2 p = Some (Release b c) ->
      exists i s0, nth_error slots' i = Some s0 /\
        sl_base (ms_layout s0) = b /\ sl_class (ms_layout s0) = c).
    { intros p b c Hp Hnth. unfold h2 in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (le_lt_dec (length h) p) as [Hge|Hlt].
      - rewrite nth_error_app2 in Hnth by exact Hge.
        destruct (p - length h) as [|[|n]] eqn:Ediff;
          [simpl in Hnth; discriminate Hnth | simpl in Hnth; discriminate Hnth | lia].
      - rewrite nth_error_app1 in Hnth by exact Hlt.
        destruct (HprovR p b c Hlt Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        destruct (Nat.eq_dec i idx) as [->|Hne].
        + rewrite Eslot in Es0. injection Es0 as <-.
          exists idx, s'. split; [exact (nth_error_replace_slot_eq idx s' s _ Eslot)|].
          split; assumption.
        + exists i, s0. split; [unfold slots'; rewrite (nth_error_replace_slot_ne idx i s' _ Hne); exact Es0|].
          split; assumption. }
    split; [exact Hladm'|].
    split; [exact Hguar2|].
    split; [exact HprovG'|].
    split; [exact HprovR'|].
    simpl.
    change (ms_hist st ++ [Zero (sl_base l) (sl_len l);
      Grant (ms_next_id st) (sl_class l) (sl_base l) (chunk_cap (sl_base l) (sl_len l))]) with h2.
    change (replace_slot idx s' (ms_slots st)) with slots'.
    destruct (ms_sweep_active st) eqn:Esw.
      * destruct Hquar as [sp [Hsp [Hsb [Hnosb Hfor]]]].
        exists sp. split; [unfold h2, h; rewrite length_app; simpl; lia|].
        split; [unfold h2, h; rewrite nth_error_app1 by exact Hsp; exact Hsb|].
        split.
        -- intros k [Hsk Hkl] Hk. unfold h2, h in Hkl, Hk.
           rewrite length_app in Hkl. simpl in Hkl.
           destruct (le_lt_dec (length (ms_hist st)) k) as [Hge|Hlt].
           ++ rewrite nth_error_app2 in Hk by exact Hge.
              destruct (k - length (ms_hist st)) as [|[|n]] eqn:Ediff;
                [simpl in Hk; discriminate Hk | simpl in Hk; discriminate Hk | lia].
           ++ rewrite nth_error_app1 in Hk by exact Hlt.
              exact (Hnosb k (conj Hsk Hlt) Hk).
        -- intros j sj Hnth. unfold slots' in Hnth. destruct (Nat.eq_dec j idx) as [->|Hne].
           ++ rewrite (nth_error_replace_slot_eq idx s' s _ Eslot) in Hnth.
              injection Hnth as <-. simpl.
              intros p c Hp Hrel. unfold h2, h in Hp, Hrel.
              rewrite length_app in Hp. simpl in Hp.
              destruct (le_lt_dec (length (ms_hist st)) p) as [Hge|Hlt].
              ** rewrite nth_error_app2 in Hrel by exact Hge.
                 destruct (p - length (ms_hist st)) as [|[|n]] eqn:Ediff;
                   [simpl in Hrel; discriminate Hrel | simpl in Hrel; discriminate Hrel | lia].
              ** rewrite nth_error_app1 in Hrel by exact Hlt.
                 unfold h2, h. rewrite length_app.
                 apply gate_passed_app; [lia|].
                 exact (Hs_gate p c Hlt Hrel).
           ++ rewrite (nth_error_replace_slot_ne idx j s' _ Hne) in Hnth.
              assert (Hlayj : nth_error (map ms_layout (ms_slots st)) j = Some (ms_layout sj)).
              { rewrite nth_error_map, Hnth. reflexivity. }
              assert (Hokj : slot_ok a (ms_layout sj) = true).
              { eapply layout_admitted_slot_ok; [exact Hladm|exact Hlayj]. }
              assert (Hdisj : slot_disjoint (ms_layout sj) l = true).
              { eapply layout_admitted_disjoint; [exact Hladm|exact Hlayj|exact Hlay_nth|exact Hne]. }
              assert (Hdiff : sl_base (ms_layout sj) <> sl_base l).
              { exact (slot_disjoint_distinct_base a (ms_layout sj) l Hokj Hok_s Hdisj). }
              apply meta_quarantine_app_inert; [| |exact (Hfor j sj Hnth)].
              ** intros p w c k [Hge Hp] Hnp. rewrite nth_error_app2 in Hnp by exact Hge.
                 rewrite length_app in Hp. simpl in Hp.
                 destruct (p - length h) as [|[|n]] eqn:Ediff;
                   [simpl in Hnp; discriminate Hnp | | lia].
                 simpl in Hnp. injection Hnp as _ _ Hb _. apply Hdiff. symmetry. exact Hb.
              ** intros p c [Hge Hp] Hnp. rewrite nth_error_app2 in Hnp by exact Hge.
                 rewrite length_app in Hp. simpl in Hp.
                 destruct (p - length h) as [|[|n]] eqn:Ediff;
                   [simpl in Hnp; discriminate Hnp | simpl in Hnp; discriminate Hnp | lia].
      * intros j sj Hnth. unfold slots' in Hnth. destruct (Nat.eq_dec j idx) as [->|Hne].
        -- rewrite (nth_error_replace_slot_eq idx s' s _ Eslot) in Hnth.
           injection Hnth as <-. simpl.
           intros p c Hp Hrel. unfold h2, h in Hp, Hrel.
           rewrite length_app in Hp. simpl in Hp.
           destruct (le_lt_dec (length (ms_hist st)) p) as [Hge|Hlt].
           ++ rewrite nth_error_app2 in Hrel by exact Hge.
              destruct (p - length (ms_hist st)) as [|[|n]] eqn:Ediff;
                [simpl in Hrel; discriminate Hrel | simpl in Hrel; discriminate Hrel | lia].
           ++ rewrite nth_error_app1 in Hrel by exact Hlt.
              unfold h2, h. rewrite length_app.
              apply gate_passed_app; [lia|].
              exact (Hs_gate p c Hlt Hrel).
        -- rewrite (nth_error_replace_slot_ne idx j s' _ Hne) in Hnth.
           assert (Hlayj : nth_error (map ms_layout (ms_slots st)) j = Some (ms_layout sj)).
           { rewrite nth_error_map, Hnth. reflexivity. }
           assert (Hokj : slot_ok a (ms_layout sj) = true).
           { eapply layout_admitted_slot_ok; [exact Hladm|exact Hlayj]. }
           assert (Hdisj : slot_disjoint (ms_layout sj) l = true).
           { eapply layout_admitted_disjoint; [exact Hladm|exact Hlayj|exact Hlay_nth|exact Hne]. }
           assert (Hdiff : sl_base (ms_layout sj) <> sl_base l).
           { exact (slot_disjoint_distinct_base a (ms_layout sj) l Hokj Hok_s Hdisj). }
           apply meta_quarantine_app_inert; [| |exact (Hquar j sj Hnth)].
           ++ intros p w c k [Hge Hp] Hnp. rewrite nth_error_app2 in Hnp by exact Hge.
              rewrite length_app in Hp. simpl in Hp.
              destruct (p - length h) as [|[|n]] eqn:Ediff;
                [simpl in Hnp; discriminate Hnp | | lia].
              simpl in Hnp. injection Hnp as _ _ Hb _. apply Hdiff. symmetry. exact Hb.
           ++ intros p c [Hge Hp] Hnp. rewrite nth_error_app2 in Hnp by exact Hge.
              rewrite length_app in Hp. simpl in Hp.
              destruct (p - length h) as [|[|n]] eqn:Ediff;
                [simpl in Hnp; discriminate Hnp | simpl in Hnp; discriminate Hnp | lia].
  - (* OpWrite idx off val *)
    destruct (nth_error (ms_slots st) idx) as [s|] eqn:Eslot;
      [|exact (conj Hladm (conj Hguar (conj HprovG (conj HprovR Hquar))))].
    destruct (ms_phase s) eqn:Ephase;
      try exact (conj Hladm (conj Hguar (conj HprovG (conj HprovR Hquar)))).
    destruct (Nat.ltb off (sl_len (ms_layout s))) eqn:Eoff;
      [|exact (conj Hladm (conj Hguar (conj HprovG (conj HprovR Hquar))))].
    set (l := ms_layout s).
    set (s' := {| ms_layout := l; ms_phase := PLive; ms_zeroed := false |}).
    set (slots' := replace_slot idx s' (ms_slots st)).
    set (ev := Write (sl_base l + off) val).
    set (h' := ms_hist st ++ [ev]).
    assert (Hladm' : layout_admitted a (map ms_layout slots')).
    { unfold slots'. rewrite (replace_slot_map_layout idx s' s _ Eslot eq_refl). exact Hladm. }
    assert (Hguar' : PoolGuarantees a h').
    { apply pool_guarantees_step; [exact Hguar|]. apply pool_point_non_grant. exact I. }
    unfold meta_inv. simpl.
    change (ms_hist st ++ [Write (sl_base l + off) val]) with h'.
    change (replace_slot idx s' (ms_slots st)) with slots'.
    split; [exact Hladm'|].
    split; [exact Hguar'|].
    split.
    { intros p w c b k Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
      - rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        discriminate Hnth.
      - assert (Hp0 : p < length (ms_hist st)) by lia.
        rewrite nth_error_app1 in Hnth by exact Hp0.
        destruct (HprovG p w c b k Hp0 Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        destruct (Nat.eq_dec i idx) as [->|Hne_i].
        + rewrite Eslot in Es0. injection Es0 as <-.
          exists idx, s'. split; [exact (nth_error_replace_slot_eq idx s' s _ Eslot)|].
          split; assumption.
        + exists i, s0. split; [unfold slots'; rewrite (nth_error_replace_slot_ne idx i s' _ Hne_i); exact Es0|].
          split; assumption. }
    split.
    { intros p b c Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
      - rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        discriminate Hnth.
      - assert (Hp0 : p < length (ms_hist st)) by lia.
        rewrite nth_error_app1 in Hnth by exact Hp0.
        destruct (HprovR p b c Hp0 Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        destruct (Nat.eq_dec i idx) as [->|Hne_i].
        + rewrite Eslot in Es0. injection Es0 as <-.
          exists idx, s'. split; [exact (nth_error_replace_slot_eq idx s' s _ Eslot)|].
          split; assumption.
        + exists i, s0. split; [unfold slots'; rewrite (nth_error_replace_slot_ne idx i s' _ Hne_i); exact Es0|].
          split; assumption. }
    destruct (ms_sweep_active st) eqn:Esw.
      * destruct Hquar as [sp [Hsp [Hsb [Hnosb Hfor]]]].
        exists sp. split; [unfold h'; rewrite length_app; simpl; lia|].
        split; [unfold h'; rewrite nth_error_app1 by exact Hsp; exact Hsb|].
        split.
        -- intros k [Hsk Hkl] Hk. unfold h' in Hkl, Hk.
           rewrite length_app in Hkl. simpl in Hkl.
           destruct (Nat.eq_dec k (length (ms_hist st))) as [->|Hne].
           ++ rewrite nth_error_app2 in Hk by lia.
              replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hk by lia.
              discriminate Hk.
           ++ assert (Hk0 : k < length (ms_hist st)) by lia.
              rewrite nth_error_app1 in Hk by exact Hk0.
              exact (Hnosb k (conj Hsk Hk0) Hk).
        -- intros j sj Hnth. unfold slots' in Hnth. destruct (Nat.eq_dec j idx) as [->|Hne].
           ++ rewrite (nth_error_replace_slot_eq idx s' s _ Eslot) in Hnth.
              injection Hnth as <-.
              pose proof (Hfor idx s Eslot) as Hs_q.
              unfold slot_quarantine_inv in Hs_q. rewrite Ephase in Hs_q.
              simpl. intros p c Hp Hrel. unfold h' in Hp, Hrel.
              rewrite length_app in Hp. simpl in Hp.
              destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hnep].
              ** rewrite nth_error_app2 in Hrel by lia.
                 replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hrel by lia.
                 discriminate Hrel.
              ** assert (Hp0 : p < length (ms_hist st)) by lia.
                 rewrite nth_error_app1 in Hrel by exact Hp0.
                 unfold h'. rewrite length_app. apply gate_passed_app; [lia|].
                 exact (Hs_q p c Hp0 Hrel).
           ++ rewrite (nth_error_replace_slot_ne idx j s' _ Hne) in Hnth.
              apply meta_quarantine_app_single_inert; [exact I|exact I|exact (Hfor j sj Hnth)].
      * intros j sj Hnth. unfold slots' in Hnth. destruct (Nat.eq_dec j idx) as [->|Hne].
        -- rewrite (nth_error_replace_slot_eq idx s' s _ Eslot) in Hnth.
           injection Hnth as <-.
           pose proof (Hquar idx s Eslot) as Hs_q.
           unfold slot_quarantine_inv in Hs_q. rewrite Ephase in Hs_q.
           simpl. intros p c Hp Hrel. unfold h' in Hp, Hrel.
           rewrite length_app in Hp. simpl in Hp.
           destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hnep].
           ++ rewrite nth_error_app2 in Hrel by lia.
              replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hrel by lia.
              discriminate Hrel.
           ++ assert (Hp0 : p < length (ms_hist st)) by lia.
              rewrite nth_error_app1 in Hrel by exact Hp0.
              unfold h'. rewrite length_app. apply gate_passed_app; [lia|].
              exact (Hs_q p c Hp0 Hrel).
        -- rewrite (nth_error_replace_slot_ne idx j s' _ Hne) in Hnth.
           apply meta_quarantine_app_single_inert; [exact I|exact I|exact (Hquar j sj Hnth)].
  - (* OpRelease idx *)
    destruct (nth_error (ms_slots st) idx) as [s|] eqn:Eslot;
      [|exact (conj Hladm (conj Hguar (conj HprovG (conj HprovR Hquar))))].
    destruct (ms_phase s) eqn:Ephase;
      try exact (conj Hladm (conj Hguar (conj HprovG (conj HprovR Hquar)))).
    set (l := ms_layout s).
    set (s' := {| ms_layout := l; ms_phase := PPending; ms_zeroed := false |}).
    set (slots' := replace_slot idx s' (ms_slots st)).
    set (ev := Release (sl_base l) (sl_class l)).
    set (h' := ms_hist st ++ [ev]).
    assert (Hlay_nth : nth_error (map ms_layout (ms_slots st)) idx = Some l).
    { rewrite nth_error_map, Eslot. reflexivity. }
    assert (Hok_s : slot_ok a l = true).
    { eapply layout_admitted_slot_ok; [exact Hladm|exact Hlay_nth]. }
    assert (Hladm' : layout_admitted a (map ms_layout slots')).
    { unfold slots'. rewrite (replace_slot_map_layout idx s' s _ Eslot eq_refl). exact Hladm. }
    assert (Hguar' : PoolGuarantees a h').
    { apply pool_guarantees_step; [exact Hguar|]. apply pool_point_non_grant. exact I. }
    unfold meta_inv. simpl.
    change (ms_hist st ++ [Release (sl_base l) (sl_class l)]) with h'.
    change (replace_slot idx s' (ms_slots st)) with slots'.
    assert (Hpend_s' : forall p w c k, p < length h' ->
      nth_error h' p = Some (Grant w c (sl_base l) k) ->
      released_between h' (sl_base l) p (length h') = true).
    { intros p w c k Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      assert (Hp0 : p < length (ms_hist st)).
      { destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne]; [|lia].
        rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        discriminate Hnth. }
      unfold h'. rewrite length_app. simpl.
      apply any_of_upto_intro with (v := length (ms_hist st)).
      - apply Nat.ltb_lt. lia.
      - apply andb_true_intro. split.
        + apply andb_true_intro. split; apply Nat.ltb_lt; lia.
        + rewrite nth_error_app2 by lia.
          replace (length (ms_hist st) - length (ms_hist st)) with 0 by lia.
          simpl. apply Nat.eqb_eq. reflexivity. }
    split; [exact Hladm'|].
    split; [exact Hguar'|].
    split.
    { intros p w c b k Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
      - rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        discriminate Hnth.
      - assert (Hp0 : p < length (ms_hist st)) by lia.
        rewrite nth_error_app1 in Hnth by exact Hp0.
        destruct (HprovG p w c b k Hp0 Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        destruct (Nat.eq_dec i idx) as [->|Hne_i].
        + rewrite Eslot in Es0. injection Es0 as <-.
          exists idx, s'. split; [exact (nth_error_replace_slot_eq idx s' s _ Eslot)|].
          split; assumption.
        + exists i, s0. split; [unfold slots'; rewrite (nth_error_replace_slot_ne idx i s' _ Hne_i); exact Es0|].
          split; assumption. }
    split.
    { intros p b c Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
      - rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        simpl in Hnth. injection Hnth as <- <-.
        exists idx, s'. split; [exact (nth_error_replace_slot_eq idx s' s _ Eslot)|].
        split; reflexivity.
      - assert (Hp0 : p < length (ms_hist st)) by lia.
        rewrite nth_error_app1 in Hnth by exact Hp0.
        destruct (HprovR p b c Hp0 Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        destruct (Nat.eq_dec i idx) as [->|Hne_i].
        + rewrite Eslot in Es0. injection Es0 as <-.
          exists idx, s'. split; [exact (nth_error_replace_slot_eq idx s' s _ Eslot)|].
          split; assumption.
        + exists i, s0. split; [unfold slots'; rewrite (nth_error_replace_slot_ne idx i s' _ Hne_i); exact Es0|].
          split; assumption. }
    destruct (ms_sweep_active st) eqn:Esw.
      * destruct Hquar as [sp [Hsp [Hsb [Hnosb Hfor]]]].
        exists sp. split; [unfold h'; rewrite length_app; simpl; lia|].
        split; [unfold h'; rewrite nth_error_app1 by exact Hsp; exact Hsb|].
        split.
        -- intros k [Hsk Hkl] Hk. unfold h' in Hkl, Hk.
           rewrite length_app in Hkl. simpl in Hkl.
           destruct (Nat.eq_dec k (length (ms_hist st))) as [->|Hne].
           ++ rewrite nth_error_app2 in Hk by lia.
              replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hk by lia.
              discriminate Hk.
           ++ assert (Hk0 : k < length (ms_hist st)) by lia.
              rewrite nth_error_app1 in Hk by exact Hk0.
              exact (Hnosb k (conj Hsk Hk0) Hk).
        -- intros j sj Hnth. unfold slots' in Hnth. destruct (Nat.eq_dec j idx) as [->|Hne].
           ++ rewrite (nth_error_replace_slot_eq idx s' s _ Eslot) in Hnth.
              injection Hnth as <-. exact Hpend_s'.
           ++ rewrite (nth_error_replace_slot_ne idx j s' _ Hne) in Hnth.
              assert (Hlayj : nth_error (map ms_layout (ms_slots st)) j = Some (ms_layout sj)).
              { rewrite nth_error_map, Hnth. reflexivity. }
              assert (Hokj : slot_ok a (ms_layout sj) = true).
              { eapply layout_admitted_slot_ok; [exact Hladm|exact Hlayj]. }
              assert (Hdisj : slot_disjoint (ms_layout sj) l = true).
              { eapply layout_admitted_disjoint; [exact Hladm|exact Hlayj|exact Hlay_nth|exact Hne]. }
              assert (Hdiff : sl_base (ms_layout sj) <> sl_base l).
              { exact (slot_disjoint_distinct_base a (ms_layout sj) l Hokj Hok_s Hdisj). }
              apply meta_quarantine_app_single_inert; [exact I| |exact (Hfor j sj Hnth)].
              congruence.
      * intros j sj Hnth. unfold slots' in Hnth. destruct (Nat.eq_dec j idx) as [->|Hne].
        -- rewrite (nth_error_replace_slot_eq idx s' s _ Eslot) in Hnth.
           injection Hnth as <-. exact Hpend_s'.
        -- rewrite (nth_error_replace_slot_ne idx j s' _ Hne) in Hnth.
           assert (Hlayj : nth_error (map ms_layout (ms_slots st)) j = Some (ms_layout sj)).
           { rewrite nth_error_map, Hnth. reflexivity. }
           assert (Hokj : slot_ok a (ms_layout sj) = true).
           { eapply layout_admitted_slot_ok; [exact Hladm|exact Hlayj]. }
           assert (Hdisj : slot_disjoint (ms_layout sj) l = true).
           { eapply layout_admitted_disjoint; [exact Hladm|exact Hlayj|exact Hlay_nth|exact Hne]. }
           assert (Hdiff : sl_base (ms_layout sj) <> sl_base l).
           { exact (slot_disjoint_distinct_base a (ms_layout sj) l Hokj Hok_s Hdisj). }
           apply meta_quarantine_app_single_inert; [exact I| |exact (Hquar j sj Hnth)].
           congruence.
  - (* OpBarrier *)
    set (slots' := map (map_slot_phase barrier_phase) (ms_slots st)).
    set (h' := ms_hist st ++ [BarrierDone]).
    assert (Hladm' : layout_admitted a (map ms_layout slots')).
    { unfold slots'. rewrite map_slot_phase_layout. exact Hladm. }
    assert (Hguar' : PoolGuarantees a h').
    { apply pool_guarantees_step; [exact Hguar|]. apply pool_point_non_grant. exact I. }
    assert (Hstep_q : forall sp_opt s,
      slot_quarantine_inv (ms_hist st) sp_opt s ->
      slot_quarantine_inv h' sp_opt (map_slot_phase barrier_phase s)).
    { intros sp_opt [l0 ph0 z0] Hs.
      destruct ph0 eqn:Ephase.
      - (* PFree *)
        exact (meta_quarantine_app_single_inert (ms_hist st) BarrierDone sp_opt
                 {| ms_layout := l0; ms_phase := PFree; ms_zeroed := z0 |} I I Hs).
      - (* PLive *)
        exact (meta_quarantine_app_single_inert (ms_hist st) BarrierDone sp_opt
                 {| ms_layout := l0; ms_phase := PLive; ms_zeroed := z0 |} I I Hs).
      - (* PPending -> PBarrier *)
        unfold slot_quarantine_inv in Hs. simpl in Hs.
        unfold map_slot_phase, slot_quarantine_inv. simpl. split.
        + intros p w c k Hp Hnth. unfold h' in Hp, Hnth.
          rewrite length_app in Hp. simpl in Hp.
          destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
          * rewrite nth_error_app2 in Hnth by lia.
            replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
            discriminate Hnth.
          * assert (Hp0 : p < length (ms_hist st)) by lia.
            rewrite nth_error_app1 in Hnth by exact Hp0.
            unfold h'. rewrite length_app. apply released_between_app; [lia|].
            exact (Hs p w c k Hp0 Hnth).
        + exists (length (ms_hist st)).
          split; [unfold h'; rewrite length_app; simpl; lia|].
          split.
          * unfold h'. rewrite nth_error_app2 by lia.
            replace (length (ms_hist st) - length (ms_hist st)) with 0 by lia. reflexivity.
          * intros p c Hp Hrel. unfold h' in Hp, Hrel.
            rewrite length_app in Hp. simpl in Hp.
            destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne]; [|lia].
            rewrite nth_error_app2 in Hrel by lia.
            replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hrel by lia.
            discriminate Hrel.
      - (* PBarrier *)
        exact (meta_quarantine_app_single_inert (ms_hist st) BarrierDone sp_opt
                 {| ms_layout := l0; ms_phase := PBarrier; ms_zeroed := z0 |} I I Hs).
      - (* PSweeping *)
        exact (meta_quarantine_app_single_inert (ms_hist st) BarrierDone sp_opt
                 {| ms_layout := l0; ms_phase := PSweeping; ms_zeroed := z0 |} I I Hs). }
    split; [exact Hladm'|].
    split; [exact Hguar'|].
    simpl.
    change (ms_hist st ++ [BarrierDone]) with h'.
    change (map (map_slot_phase barrier_phase) (ms_slots st)) with slots'.
    split.
    { intros p w c b k Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
      - rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        discriminate Hnth.
      - assert (Hp0 : p < length (ms_hist st)) by lia.
        rewrite nth_error_app1 in Hnth by exact Hp0.
        destruct (HprovG p w c b k Hp0 Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        exists i, (map_slot_phase barrier_phase s0).
        split; [unfold slots'; rewrite nth_error_map, Es0; reflexivity|].
        split; assumption. }
    split.
    { intros p b c Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
      - rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        discriminate Hnth.
      - assert (Hp0 : p < length (ms_hist st)) by lia.
        rewrite nth_error_app1 in Hnth by exact Hp0.
        destruct (HprovR p b c Hp0 Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        exists i, (map_slot_phase barrier_phase s0).
        split; [unfold slots'; rewrite nth_error_map, Es0; reflexivity|].
        split; assumption. }
    destruct (ms_sweep_active st) eqn:Esw.
      * destruct Hquar as [sp [Hsp [Hsb [Hnosb Hfor]]]].
        exists sp. split; [unfold h'; rewrite length_app; simpl; lia|].
        split; [unfold h'; rewrite nth_error_app1 by exact Hsp; exact Hsb|].
        split.
        -- intros k [Hsk Hkl] Hk. unfold h' in Hkl, Hk.
           rewrite length_app in Hkl. simpl in Hkl.
           destruct (Nat.eq_dec k (length (ms_hist st))) as [->|Hne].
           ++ rewrite nth_error_app2 in Hk by lia.
              replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hk by lia.
              discriminate Hk.
           ++ assert (Hk0 : k < length (ms_hist st)) by lia.
              rewrite nth_error_app1 in Hk by exact Hk0.
              exact (Hnosb k (conj Hsk Hk0) Hk).
        -- intros j sj Hnth. unfold slots' in Hnth. rewrite nth_error_map in Hnth.
           destruct (nth_error (ms_slots st) j) as [s0|] eqn:Es0; [|discriminate Hnth].
           injection Hnth as <-. exact (Hstep_q (Some sp) s0 (Hfor j s0 Es0)).
      * intros j sj Hnth. unfold slots' in Hnth. rewrite nth_error_map in Hnth.
        destruct (nth_error (ms_slots st) j) as [s0|] eqn:Es0; [|discriminate Hnth].
        injection Hnth as <-. exact (Hstep_q None s0 (Hquar j s0 Es0)).
  - (* OpSweepBegin *)
    destruct (ms_sweep_active st) eqn:Esw;
      [simpl; unfold meta_inv; rewrite Esw;
       exact (conj Hladm (conj Hguar (conj HprovG (conj HprovR Hquar))))|].
    simpl.
    set (slots' := map (map_slot_phase sweep_begin_phase) (ms_slots st)).
    set (h' := ms_hist st ++ [SweepBegin]).
    assert (Hladm' : layout_admitted a (map ms_layout slots')).
    { unfold slots'. rewrite map_slot_phase_layout. exact Hladm. }
    assert (Hguar' : PoolGuarantees a h').
    { apply pool_guarantees_step; [exact Hguar|]. apply pool_point_non_grant. exact I. }
    unfold meta_inv. simpl.
    change (ms_hist st ++ [SweepBegin]) with h'.
    change (map (map_slot_phase sweep_begin_phase) (ms_slots st)) with slots'.
    split; [exact Hladm'|].
    split; [exact Hguar'|].
    split.
    { intros p w c b k Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
      - rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        discriminate Hnth.
      - assert (Hp0 : p < length (ms_hist st)) by lia.
        rewrite nth_error_app1 in Hnth by exact Hp0.
        destruct (HprovG p w c b k Hp0 Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        exists i, (map_slot_phase sweep_begin_phase s0).
        split; [unfold slots'; rewrite nth_error_map, Es0; reflexivity|].
        split; assumption. }
    split.
    { intros p b c Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
      - rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        discriminate Hnth.
      - assert (Hp0 : p < length (ms_hist st)) by lia.
        rewrite nth_error_app1 in Hnth by exact Hp0.
        destruct (HprovR p b c Hp0 Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        exists i, (map_slot_phase sweep_begin_phase s0).
        split; [unfold slots'; rewrite nth_error_map, Es0; reflexivity|].
        split; assumption. }
    exists (length (ms_hist st)).
      split; [unfold h'; rewrite length_app; simpl; lia|].
      split.
      * unfold h'. rewrite nth_error_app2 by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 by lia. reflexivity.
      * split.
        -- intros k [Hk1 Hk2]. unfold h' in Hk2. rewrite length_app in Hk2. simpl in Hk2. lia.
        -- intros j sj Hnth. unfold slots' in Hnth. rewrite nth_error_map in Hnth.
           destruct (nth_error (ms_slots st) j) as [s0|] eqn:Es0; [|discriminate Hnth].
           injection Hnth as <-.
           pose proof (Hquar j s0 Es0) as Hs0.
           destruct (ms_phase s0) eqn:Ephase.
           ++ (* PFree *)
              unfold slot_quarantine_inv in *. rewrite Ephase in Hs0.
              unfold map_slot_phase. simpl. rewrite Ephase. simpl.
              destruct Hs0 as [Hg Hr]. split.
              ** intros p w c k Hp Hnp. unfold h' in Hp, Hnp.
                 rewrite length_app in Hp. simpl in Hp.
                 destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
                 --- rewrite nth_error_app2 in Hnp by lia.
                     replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
                     discriminate Hnp.
                 --- assert (Hp0 : p < length (ms_hist st)) by lia.
                     rewrite nth_error_app1 in Hnp by exact Hp0.
                     unfold h'. rewrite length_app. apply released_between_app; [lia|].
                     exact (Hg p w c k Hp0 Hnp).
              ** intros p c Hp Hnp. unfold h' in Hp, Hnp.
                 rewrite length_app in Hp. simpl in Hp.
                 destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
                 --- rewrite nth_error_app2 in Hnp by lia.
                     replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
                     discriminate Hnp.
                 --- assert (Hp0 : p < length (ms_hist st)) by lia.
                     rewrite nth_error_app1 in Hnp by exact Hp0.
                     unfold h'. rewrite length_app. apply gate_passed_app; [lia|].
                     exact (Hr p c Hp0 Hnp).
           ++ (* PLive *)
              unfold slot_quarantine_inv in *. rewrite Ephase in Hs0.
              unfold map_slot_phase. simpl. rewrite Ephase. simpl.
              intros p c Hp Hnp. unfold h' in Hp, Hnp.
              rewrite length_app in Hp. simpl in Hp.
              destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
              ** rewrite nth_error_app2 in Hnp by lia.
                 replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
                 discriminate Hnp.
              ** assert (Hp0 : p < length (ms_hist st)) by lia.
                 rewrite nth_error_app1 in Hnp by exact Hp0.
                 unfold h'. rewrite length_app. apply gate_passed_app; [lia|].
                 exact (Hs0 p c Hp0 Hnp).
           ++ (* PPending *)
              unfold slot_quarantine_inv in *. rewrite Ephase in Hs0.
              unfold map_slot_phase. simpl. rewrite Ephase. simpl.
              intros p w c k Hp Hnp. unfold h' in Hp, Hnp.
              rewrite length_app in Hp. simpl in Hp.
              destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
              ** rewrite nth_error_app2 in Hnp by lia.
                 replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
                 discriminate Hnp.
              ** assert (Hp0 : p < length (ms_hist st)) by lia.
                 rewrite nth_error_app1 in Hnp by exact Hp0.
                 unfold h'. rewrite length_app. apply released_between_app; [lia|].
                 exact (Hs0 p w c k Hp0 Hnp).
           ++ (* PBarrier -> PSweeping *)
              unfold slot_quarantine_inv in *. rewrite Ephase in Hs0.
              unfold map_slot_phase. simpl. rewrite Ephase. simpl.
              destruct Hs0 as [Hg [bp [Hbp [Hbar Hrel]]]]. split.
              ** intros p w c k Hp Hnp. unfold h' in Hp, Hnp.
                 rewrite length_app in Hp. simpl in Hp.
                 destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
                 --- rewrite nth_error_app2 in Hnp by lia.
                     replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
                     discriminate Hnp.
                 --- assert (Hp0 : p < length (ms_hist st)) by lia.
                     rewrite nth_error_app1 in Hnp by exact Hp0.
                     unfold h'. rewrite length_app. apply released_between_app; [lia|].
                     exact (Hg p w c k Hp0 Hnp).
              ** exists (length (ms_hist st)), bp. repeat split.
                 --- exact Hbp.
                 --- unfold h'. rewrite length_app. simpl. lia.
                 --- unfold h'. rewrite nth_error_app1 by exact Hbp. exact Hbar.
                 --- unfold h'. rewrite nth_error_app2 by lia.
                     replace (length (ms_hist st) - length (ms_hist st)) with 0 by lia. reflexivity.
                 --- intros p c Hp Hnp. unfold h' in Hp, Hnp.
                     rewrite length_app in Hp. simpl in Hp.
                     destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
                     +++ rewrite nth_error_app2 in Hnp by lia.
                         replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
                         discriminate Hnp.
                     +++ assert (Hp0 : p < length (ms_hist st)) by lia.
                         rewrite nth_error_app1 in Hnp by exact Hp0.
                         exact (Hrel p c Hp0 Hnp).
           ++ (* PSweeping impossible when ms_sweep_active = false *)
              unfold slot_quarantine_inv in Hs0. rewrite Ephase in Hs0.
              destruct Hs0 as [_ [sp [_ [Hcontra _]]]]. discriminate Hcontra.
  - (* OpSweepEnd *)
    destruct (ms_sweep_active st) eqn:Esw;
      [|simpl; unfold meta_inv; rewrite Esw;
        exact (conj Hladm (conj Hguar (conj HprovG (conj HprovR Hquar))))].
    destruct Hquar as [sp [Hsp [Hsb [Hnosb Hfor]]]].
    set (slots' := map (map_slot_phase sweep_end_phase) (ms_slots st)).
    set (h' := ms_hist st ++ [SweepEnd]).
    assert (Hladm' : layout_admitted a (map ms_layout slots')).
    { unfold slots'. rewrite map_slot_phase_layout. exact Hladm. }
    assert (Hguar' : PoolGuarantees a h').
    { apply pool_guarantees_step; [exact Hguar|]. apply pool_point_non_grant. exact I. }
    unfold meta_inv. simpl.
    change (ms_hist st ++ [SweepEnd]) with h'.
    change (map (map_slot_phase sweep_end_phase) (ms_slots st)) with slots'.
    split; [exact Hladm'|].
    split; [exact Hguar'|].
    split.
    { intros p w c b k Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
      - rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        discriminate Hnth.
      - assert (Hp0 : p < length (ms_hist st)) by lia.
        rewrite nth_error_app1 in Hnth by exact Hp0.
        destruct (HprovG p w c b k Hp0 Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        exists i, (map_slot_phase sweep_end_phase s0).
        split; [unfold slots'; rewrite nth_error_map, Es0; reflexivity|].
        split; assumption. }
    split.
    { intros p b c Hp Hnth. unfold h' in Hp, Hnth.
      rewrite length_app in Hp. simpl in Hp.
      destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
      - rewrite nth_error_app2 in Hnth by lia.
        replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnth by lia.
        discriminate Hnth.
      - assert (Hp0 : p < length (ms_hist st)) by lia.
        rewrite nth_error_app1 in Hnth by exact Hp0.
        destruct (HprovR p b c Hp0 Hnth) as [i [s0 [Es0 [Hb Hc]]]].
        exists i, (map_slot_phase sweep_end_phase s0).
        split; [unfold slots'; rewrite nth_error_map, Es0; reflexivity|].
        split; assumption. }
    intros j sj Hnth. unfold slots' in Hnth. rewrite nth_error_map in Hnth.
      destruct (nth_error (ms_slots st) j) as [s0|] eqn:Es0; [|discriminate Hnth].
      injection Hnth as <-.
      pose proof (Hfor j s0 Es0) as Hs0.
      destruct (ms_phase s0) eqn:Ephase.
      * (* PFree *)
        unfold slot_quarantine_inv in *. rewrite Ephase in Hs0.
        unfold map_slot_phase. simpl. rewrite Ephase. simpl.
        destruct Hs0 as [Hg Hr]. split.
        -- intros p w c k Hp Hnp. unfold h' in Hp, Hnp.
           rewrite length_app in Hp. simpl in Hp.
           destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
           ++ rewrite nth_error_app2 in Hnp by lia.
              replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
              discriminate Hnp.
           ++ assert (Hp0 : p < length (ms_hist st)) by lia.
              rewrite nth_error_app1 in Hnp by exact Hp0.
              unfold h'. rewrite length_app. apply released_between_app; [lia|].
              exact (Hg p w c k Hp0 Hnp).
        -- intros p c Hp Hnp. unfold h' in Hp, Hnp.
           rewrite length_app in Hp. simpl in Hp.
           destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
           ++ rewrite nth_error_app2 in Hnp by lia.
              replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
              discriminate Hnp.
           ++ assert (Hp0 : p < length (ms_hist st)) by lia.
              rewrite nth_error_app1 in Hnp by exact Hp0.
              unfold h'. rewrite length_app. apply gate_passed_app; [lia|].
              exact (Hr p c Hp0 Hnp).
      * (* PLive *)
        unfold slot_quarantine_inv in *. rewrite Ephase in Hs0.
        unfold map_slot_phase. simpl. rewrite Ephase. simpl.
        intros p c Hp Hnp. unfold h' in Hp, Hnp.
        rewrite length_app in Hp. simpl in Hp.
        destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
        -- rewrite nth_error_app2 in Hnp by lia.
           replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
           discriminate Hnp.
        -- assert (Hp0 : p < length (ms_hist st)) by lia.
           rewrite nth_error_app1 in Hnp by exact Hp0.
           unfold h'. rewrite length_app. apply gate_passed_app; [lia|].
           exact (Hs0 p c Hp0 Hnp).
      * (* PPending *)
        unfold slot_quarantine_inv in *. rewrite Ephase in Hs0.
        unfold map_slot_phase. simpl. rewrite Ephase. simpl.
        intros p w c k Hp Hnp. unfold h' in Hp, Hnp.
        rewrite length_app in Hp. simpl in Hp.
        destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
        -- rewrite nth_error_app2 in Hnp by lia.
           replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
           discriminate Hnp.
        -- assert (Hp0 : p < length (ms_hist st)) by lia.
           rewrite nth_error_app1 in Hnp by exact Hp0.
           unfold h'. rewrite length_app. apply released_between_app; [lia|].
           exact (Hs0 p w c k Hp0 Hnp).
      * (* PBarrier *)
        unfold slot_quarantine_inv in *. rewrite Ephase in Hs0.
        unfold map_slot_phase. simpl. rewrite Ephase. simpl.
        destruct Hs0 as [Hg [bp [Hbp [Hbar Hrel]]]]. split.
        -- intros p w c k Hp Hnp. unfold h' in Hp, Hnp.
           rewrite length_app in Hp. simpl in Hp.
           destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
           ++ rewrite nth_error_app2 in Hnp by lia.
              replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
              discriminate Hnp.
           ++ assert (Hp0 : p < length (ms_hist st)) by lia.
              rewrite nth_error_app1 in Hnp by exact Hp0.
              unfold h'. rewrite length_app. apply released_between_app; [lia|].
              exact (Hg p w c k Hp0 Hnp).
        -- exists bp. split; [unfold h'; rewrite length_app; simpl; lia|].
           split; [unfold h'; rewrite nth_error_app1 by exact Hbp; exact Hbar|].
           intros p c Hp Hnp. unfold h' in Hp, Hnp.
           rewrite length_app in Hp. simpl in Hp.
           destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
           ++ rewrite nth_error_app2 in Hnp by lia.
              replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
              discriminate Hnp.
           ++ assert (Hp0 : p < length (ms_hist st)) by lia.
              rewrite nth_error_app1 in Hnp by exact Hp0.
              exact (Hrel p c Hp0 Hnp).
      * (* PSweeping -> PFree *)
        unfold slot_quarantine_inv in *. rewrite Ephase in Hs0.
        unfold map_slot_phase. simpl. rewrite Ephase. simpl.
        destruct Hs0 as [Hg [sp0 [bp [Heqsp [Hbs [Hsl [Hbar [Hbeg Hrel]]]]]]]].
        injection Heqsp as <-. split.
        -- intros p w c k Hp Hnp. unfold h' in Hp, Hnp.
           rewrite length_app in Hp. simpl in Hp.
           destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne].
           ++ rewrite nth_error_app2 in Hnp by lia.
              replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
              discriminate Hnp.
           ++ assert (Hp0 : p < length (ms_hist st)) by lia.
              rewrite nth_error_app1 in Hnp by exact Hp0.
              unfold h'. rewrite length_app. apply released_between_app; [lia|].
              exact (Hg p w c k Hp0 Hnp).
        -- intros p c Hp Hnp. unfold h' in Hp, Hnp.
           rewrite length_app in Hp. simpl in Hp.
           assert (Hp0 : p < length (ms_hist st)).
           { destruct (Nat.eq_dec p (length (ms_hist st))) as [->|Hne]; [|lia].
             rewrite nth_error_app2 in Hnp by lia.
             replace (length (ms_hist st) - length (ms_hist st)) with 0 in Hnp by lia.
             discriminate Hnp. }
           rewrite nth_error_app1 in Hnp by exact Hp0.
           pose proof (Hrel p c Hp0 Hnp) as Hpbp.
           eapply gate_passed_intro with (bp := bp) (sp := sp) (ep := length (ms_hist st)).
           ++ exact Hpbp.
           ++ exact Hbs.
           ++ exact Hsp.
           ++ unfold h'. rewrite length_app. simpl. lia.
           ++ unfold h'. rewrite nth_error_app1 by lia. exact Hbar.
           ++ unfold h'. rewrite nth_error_app1 by exact Hsp. exact Hsb.
           ++ unfold h'. rewrite nth_error_app2 by lia.
              replace (length (ms_hist st) - length (ms_hist st)) with 0 by lia. reflexivity.
           ++ intros k [Hk1 Hk2] Hk.
              unfold h' in Hk. rewrite nth_error_app1 in Hk by exact Hk2.
              exact (Hnosb k (conj Hk1 Hk2) Hk).
Qed.

Lemma meta_run_preserves_inv : forall a ops st,
  meta_inv a st -> meta_inv a (meta_run a st ops).
Proof.
  intros a ops. induction ops as [|op rest IH]; intros st Hinv; simpl; [exact Hinv|].
  apply IH. exact (meta_step_preserves_inv a st op Hinv).
Qed.

Theorem meta_run_refines_pool_guarantees : forall a slots ops,
  layout_admitted a slots ->
  PoolGuarantees a (ms_hist (meta_run a (meta_init slots) ops)).
Proof.
  intros a slots ops Hladm.
  pose proof (meta_run_preserves_inv a ops (meta_init slots) (meta_init_inv a slots Hladm))
    as [_ [Hguar _]].
  exact Hguar.
Qed.

Theorem meta_run_refines_heap_narrows : forall a slots ops,
  layout_admitted a slots ->
  HeapNarrows a (ms_hist (meta_run a (meta_init slots) ops)).
Proof.
  intros a slots ops Hladm.
  destruct (meta_run_refines_pool_guarantees a slots ops Hladm)
    as [Hd [He [_ Hr]]].
  exact (conj He (conj Hd Hr)).
Qed.

(* --- Executable witnesses for two-generation quarantine --- *)

Definition meta_ref_slots : list SlotLayout :=
  [{| sl_base := 64; sl_class := 0; sl_len := 16 |};
   {| sl_base := 80; sl_class := 0; sl_len := 16 |}].

Example meta_ref_layout_is_admitted :
  layout_admitted pool_reference_arena meta_ref_slots.
Proof. split; reflexivity. Qed.

Definition meta_two_gen_prefix_ops : list MetaOp :=
  [OpAlloc 0; OpAlloc 1;
   OpRelease 0; OpBarrier; OpSweepBegin;
   OpRelease 1; OpBarrier; OpSweepEnd].

Definition meta_two_gen_mid : MetaState :=
  meta_run pool_reference_arena (meta_init meta_ref_slots) meta_two_gen_prefix_ops.

(* A slot released during an active sweep stays quarantined in `PBarrier` after
   `OpBarrier` and `OpSweepEnd`, and `OpAlloc` refuses it until a second sweep
   completes. *)
Example meta_two_gen_quarantine_refuses_early_alloc :
  map ms_phase (ms_slots meta_two_gen_mid) = [PFree; PBarrier] /\
  ms_sweep_active meta_two_gen_mid = false /\
  meta_step pool_reference_arena meta_two_gen_mid (OpAlloc 1) = meta_two_gen_mid.
Proof. split; [vm_reflexivity | split; vm_reflexivity]. Qed.

Definition meta_two_gen_full_ops : list MetaOp :=
  meta_two_gen_prefix_ops ++ [OpAlloc 1; OpSweepBegin; OpSweepEnd; OpAlloc 1].

Definition meta_two_gen_final : MetaState :=
  meta_run pool_reference_arena (meta_init meta_ref_slots) meta_two_gen_full_ops.

Example meta_two_gen_quarantine_reuses_after_second_sweep :
  map ms_phase (ms_slots meta_two_gen_final) = [PFree; PLive] /\
  ms_next_id meta_two_gen_final = 3 /\
  ms_hist meta_two_gen_final =
    [Zero 64 16; Grant 0 0 64 (chunk_cap 64 16);
     Zero 80 16; Grant 1 0 80 (chunk_cap 80 16);
     Release 64 0; BarrierDone; SweepBegin;
     Release 80 0; BarrierDone; SweepEnd;
     SweepBegin; SweepEnd;
     Zero 80 16; Grant 2 0 80 (chunk_cap 80 16)].
Proof. split; [vm_reflexivity | split; vm_reflexivity]. Qed.

