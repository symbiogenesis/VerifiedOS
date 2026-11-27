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
   Requirements: R-05-126 R-08-005a R-08-006 R-08-007a R-08-047 R-08-047a R-08-047b R-15-007c
      R-15-007k R-17-045
   SHA256: 4f53920794a1dec57149621e6dc21eb410a902b64359df206619a7bde3e058d1
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Require ProofSupport.
Import ProofSupport.Tactics.
Require Import CyclicExecutive MemoryPlan ElasticDomain.
Import ListNotations.
Local Open Scope nat_scope.

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

(* =========================================================================
   1. Composition-Fixed Size-Class Table & Request-Level Granule Exactness
      (R-15-007c, R-15-007k, R-08-047b, Q34c Finding 1)
   ========================================================================= *)

Definition std_size_classes : list SizeClass :=
  [{| sc_length := 16; sc_align := 16 |};
   {| sc_length := 32; sc_align := 32 |};
   {| sc_length := 64; sc_align := 64 |};
   {| sc_length := 128; sc_align := 128 |};
   {| sc_length := 256; sc_align := 256 |};
   {| sc_length := 512; sc_align := 512 |};
   {| sc_length := 1024; sc_align := 1024 |};
   {| sc_length := 2048; sc_align := 2048 |};
   {| sc_length := 4096; sc_align := 4096 |};
   {| sc_length := 8192; sc_align := 8192 |};
   {| sc_length := 16384; sc_align := 16384 |};
   {| sc_length := 32768; sc_align := 32768 |};
   {| sc_length := 65536; sc_align := 65536 |}].

Lemma granule_exponent_le_step : forall f len,
  granule_exponent f len <= granule_exponent (S f) len.
Proof.
  intros f len. rewrite granule_exponent_step.
  destruct (Nat.leb (64 * (2 * pow2 (granule_exponent f len))) len); lia.
Qed.

Lemma granule_exponent_mono_fuel : forall f1 f2 len,
  f1 <= f2 -> granule_exponent f1 len <= granule_exponent f2 len.
Proof.
  intros f1 f2 len Hle. induction Hle as [|f2 Hle IH]; [lia|].
  pose proof (granule_exponent_le_step f2 len) as Hstep. lia.
Qed.

Lemma pow2_mono : forall e1 e2, e1 <= e2 -> pow2 e1 <= pow2 e2.
Proof.
  intros e1 e2 Hle. induction Hle as [|e2 Hle IH]; [lia|].
  rewrite pow2_step. pose proof (pow2_pos e2) as Hpos. apply Nat.leb_le in Hpos. lia.
Qed.

Lemma granule_exponent_mono_len : forall f len1 len2,
  len1 <= len2 -> granule_exponent f len1 <= granule_exponent f len2.
Proof.
  intros f. induction f as [|f IH]; intros len1 len2 Hle; [simpl; lia|].
  rewrite !granule_exponent_step.
  specialize (IH len1 len2 Hle).
  destruct (Nat.leb (64 * (2 * pow2 (granule_exponent f len1))) len1) eqn:E1;
  destruct (Nat.leb (64 * (2 * pow2 (granule_exponent f len2))) len2) eqn:E2;
    try lia.
  apply Nat.leb_le in E1. apply Nat.leb_gt in E2.
  destruct (Nat.eq_dec (granule_exponent f len1) (granule_exponent f len2)) as [Heq|Hne].
  - rewrite Heq in E1. lia.
  - lia.
Qed.

Lemma granule_exponent_stable : forall f1 f2 len,
  f1 <= f2 ->
  len < 64 * (2 * pow2 (granule_exponent f1 len)) ->
  granule_exponent f2 len = granule_exponent f1 len.
Proof.
  intros f1 f2 len Hle Hlt. induction Hle as [|f2 Hle IH]; [reflexivity|].
  rewrite granule_exponent_step, IH.
  destruct (Nat.leb (64 * (2 * pow2 (granule_exponent f1 len))) len) eqn:E; [|reflexivity].
  apply Nat.leb_le in E. lia.
Qed.

Lemma class_exact_at_12 : forall n,
  Nat.leb 128 n = true ->
  Nat.ltb n (64 * (2 * pow2 (granule_exponent 12 n))) = true ->
  Nat.eqb (n mod pow2 (granule_exponent 12 n)) 0 = true ->
  class_exact {| sc_length := n; sc_align := n |} = true.
Proof.
  intros n Hge Hlt Hmod.
  apply Nat.leb_le in Hge. apply Nat.ltb_lt in Hlt. apply Nat.eqb_eq in Hmod.
  unfold class_exact, representable_granule. simpl.
  replace (n <=? 127) with false by (symmetry; apply Nat.leb_gt; lia).
  rewrite (granule_exponent_stable 12 n n) by lia.
  rewrite Hmod.
  replace (0 <? n) with true by (symmetry; apply Nat.ltb_lt; lia).
  reflexivity.
Qed.

Lemma all_of_cons_true : forall (A : Type) (p : A -> bool) (x : A) (xs : list A),
  p x = true -> all_of p xs = true -> all_of p (x :: xs) = true.
Proof.
  intros A p x xs Hx Hxs. unfold all_of in *. simpl. rewrite Hx, Hxs. reflexivity.
Qed.

Theorem std_size_classes_discharge_r15_007k :
  all_of class_exact std_size_classes = true.
Proof.
  unfold std_size_classes.
  apply all_of_cons_true; [vm_reflexivity|].
  apply all_of_cons_true; [vm_reflexivity|].
  apply all_of_cons_true; [vm_reflexivity|].
  apply all_of_cons_true; [apply class_exact_at_12; vm_reflexivity|].
  apply all_of_cons_true; [apply class_exact_at_12; vm_reflexivity|].
  apply all_of_cons_true; [apply class_exact_at_12; vm_reflexivity|].
  apply all_of_cons_true; [apply class_exact_at_12; vm_reflexivity|].
  apply all_of_cons_true; [apply class_exact_at_12; vm_reflexivity|].
  apply all_of_cons_true; [apply class_exact_at_12; vm_reflexivity|].
  apply all_of_cons_true; [apply class_exact_at_12; vm_reflexivity|].
  apply all_of_cons_true; [apply class_exact_at_12; vm_reflexivity|].
  apply all_of_cons_true; [apply class_exact_at_12; vm_reflexivity|].
  apply all_of_cons_true; [apply class_exact_at_12; vm_reflexivity|].
  reflexivity.
Qed.

Definition round_up_to_granule (req g : nat) : nat :=
  let r := req mod g in
  if Nat.eqb r 0 then req else req + (g - r).

Definition round_request_for_class (sc : SizeClass) (req : nat) : nat :=
  round_up_to_granule req (representable_granule (sc_length sc)).

Definition narrowed_size_class (sc : SizeClass) (req : nat) : SizeClass :=
  {| sc_length := round_request_for_class sc req; sc_align := sc_align sc |}.

Lemma representable_granule_pos : forall len, 0 < representable_granule len.
Proof.
  intro len. unfold representable_granule. destruct (Nat.leb len 127); [lia|].
  pose proof (pow2_pos (granule_exponent len len)) as H. apply Nat.leb_le in H. lia.
Qed.

Lemma pow2_divides_mono : forall e1 e2, e1 <= e2 -> pow2 e2 mod pow2 e1 = 0.
Proof.
  intros e1 e2 Hle. induction Hle as [|e2 Hle IH].
  - pose proof (pow2_pos e1) as Hpos. apply Nat.leb_le in Hpos.
    apply Nat.Div0.mod_same.
  - rewrite pow2_step. apply Nat.Div0.mod_divides in IH.
    destruct IH as [k Hk]. rewrite Hk.
    apply Nat.Div0.mod_divides. exists (2 * k). lia.
Qed.

Lemma representable_granule_mono_divides : forall l1 l2,
  l1 <= l2 ->
  representable_granule l2 mod representable_granule l1 = 0.
Proof.
  intros l1 l2 Hle. unfold representable_granule.
  destruct (Nat.leb l1 127) eqn:E1.
  - apply Nat.mod_1_r.
  - apply Nat.leb_gt in E1.
    replace (l2 <=? 127) with false by (symmetry; apply Nat.leb_gt; lia).
    apply pow2_divides_mono.
    apply Nat.le_trans with (m := granule_exponent l1 l2).
    + apply granule_exponent_mono_len. exact Hle.
    + apply granule_exponent_mono_fuel. exact Hle.
Qed.

Lemma class_exact_props : forall sc,
  class_exact sc = true ->
  0 < sc_length sc /\
  0 < sc_align sc /\
  sc_length sc mod representable_granule (sc_length sc) = 0 /\
  sc_align sc mod representable_granule (sc_length sc) = 0.
Proof.
  intros sc H. unfold class_exact in H. cbv zeta in H.
  apply andb_prop in H. destruct H as [H Hal].
  apply andb_prop in H. destruct H as [H Hlen].
  apply andb_prop in H. destruct H as [Hpl Hpa].
  apply Nat.ltb_lt in Hpl. apply Nat.ltb_lt in Hpa.
  apply Nat.eqb_eq in Hlen. apply Nat.eqb_eq in Hal.
  repeat split; assumption.
Qed.

Lemma round_up_to_granule_props : forall req g len,
  0 < g ->
  0 < req ->
  req <= len ->
  len mod g = 0 ->
  let rounded := round_up_to_granule req g in
  rounded mod g = 0 /\ req <= rounded /\ rounded <= len.
Proof.
  intros req g len Hg Hreq Hle Hlenmod.
  unfold round_up_to_granule. cbv zeta.
  destruct (Nat.eqb (req mod g) 0) eqn:Emod.
  - apply Nat.eqb_eq in Emod. repeat split; try assumption; lia.
  - apply Nat.eqb_neq in Emod.
    pose proof (Nat.mod_upper_bound req g ltac:(lia)) as Hmod_lt.
    pose proof (Nat.div_mod_eq req g) as Hdm.
    assert (Hreq_decomp : req = g * (req / g) + req mod g) by lia.
    assert (Hrounded_eq : req + (g - req mod g) = (req / g + 1) * g) by nia.
    split.
    + rewrite Hrounded_eq. apply Nat.Div0.mod_mul.
    + split; [lia|].
      apply Nat.Div0.mod_divides in Hlenmod. destruct Hlenmod as [q Hq].
      assert (Hq_gt : req / g < q) by nia.
      nia.
Qed.

Theorem requested_length_granule_exact : forall sc req,
  class_exact sc = true ->
  0 < req ->
  req <= sc_length sc ->
  let g := representable_granule (sc_length sc) in
  let rounded := round_request_for_class sc req in
  rounded mod g = 0 /\
  req <= rounded /\
  rounded <= sc_length sc /\
  class_exact (narrowed_size_class sc req) = true /\
  (forall b, b mod sc_align sc = 0 ->
    b mod representable_granule rounded = 0 /\
    rounded mod representable_granule rounded = 0).
Proof.
  intros sc req Hce Hreq Hle.
  destruct (class_exact_props sc Hce) as [Hslen [Hsal [Hsmod Hamod]]].
  pose proof (representable_granule_pos (sc_length sc)) as Hgpos.
  pose proof (round_up_to_granule_props req (representable_granule (sc_length sc))
                (sc_length sc) Hgpos Hreq Hle Hsmod) as [Hrmod [Hreq_r Hr_len]].
  fold (round_request_for_class sc req) in Hrmod, Hreq_r, Hr_len.
  set (rounded := round_request_for_class sc req) in *.
  set (g := representable_granule (sc_length sc)) in *.
  pose proof (representable_granule_mono_divides rounded (sc_length sc) Hr_len) as Hgdiv.
  assert (Hr_own : rounded mod representable_granule rounded = 0).
  { exact (mod_through_a_multiple rounded g (representable_granule rounded) Hrmod Hgdiv). }
  assert (Ha_own : sc_align sc mod representable_granule rounded = 0).
  { exact (mod_through_a_multiple (sc_align sc) g (representable_granule rounded) Hamod Hgdiv). }
  assert (Hce_n : class_exact (narrowed_size_class sc req) = true).
  { unfold class_exact, narrowed_size_class. cbn [sc_length sc_align]. fold rounded.
    replace (0 <? rounded) with true by (symmetry; apply Nat.ltb_lt; lia).
    replace (0 <? sc_align sc) with true by (symmetry; apply Nat.ltb_lt; lia).
    rewrite Hr_own, Ha_own. reflexivity. }
  cbv zeta.
  split; [exact Hrmod|].
  split; [exact Hreq_r|].
  split; [exact Hr_len|].
  split; [exact Hce_n|].
  intros addr Haddr.
  split; [exact (mod_through_a_multiple addr (sc_align sc) _ Haddr Ha_own) | exact Hr_own].
Qed.

Theorem narrowed_grant_preserves_bounded_exactly :
  forall a w cls b sc req,
    nth_error (ar_classes a) cls = Some sc ->
    class_exact sc = true ->
    b mod sc_align sc = 0 ->
    ar_base a <= b ->
    b + sc_length sc <= ar_base a + ar_span a ->
    0 < req ->
    req <= sc_length sc ->
    let rounded := round_request_for_class sc req in
    let a' := {| ar_base := ar_base a;
                 ar_span := ar_span a;
                 ar_classes := [narrowed_size_class sc req];
                 ar_initial := ar_initial a |} in
    BoundedExactly a' [Grant w 0 b (chunk_cap b rounded)] /\
    b mod representable_granule rounded = 0 /\
    rounded mod representable_granule rounded = 0.
Proof.
  intros a w cls b sc req _ Hce Hbal Hbot Htop Hreq Hle.
  destruct (requested_length_granule_exact sc req Hce Hreq Hle)
    as [_ [_ [Hr_len [Hce_n Hbprops]]]].
  destruct (Hbprops b Hbal) as [Hb_own Hr_own].
  repeat split; try assumption.
  intros q Hq. simpl in Hq.
  assert (Hq0 : q = 0) by (apply Nat.ltb_lt in Hq; lia). subst q.
  unfold exact_at, grant_exact, chunk_cap; cbn [nth_error ar_classes].
  rewrite Hce_n.
  unfold narrowed_size_class; cbn [ar_base ar_span cap_base cap_length sc_length sc_align].
  apply andb_true_intro; split; [|apply Nat.leb_le; lia].
  apply andb_true_intro; split; [|apply Nat.leb_le; exact Hbot].
  apply andb_true_intro; split; [|apply Nat.eqb_eq; reflexivity].
  apply andb_true_intro; split; [|apply Nat.eqb_eq; reflexivity].
  apply Nat.eqb_eq. exact Hbal.
Qed.

(* =========================================================================
   2. Eager Zeroing Inside Sub-Allocation Reuse
      (R-05-126, R-08-047b, R-17-045, Q34c Finding 2)
   ========================================================================= *)

Definition HeapZeroedAtHandoff (chunk : Arena) (h : list AllocEvent) : Prop :=
  ZeroedAtHandoff chunk h.

Definition HeapGuarantees (chunk : Arena) (h : list AllocEvent) : Prop :=
  HeapNarrows chunk h /\ HeapZeroedAtHandoff chunk h.

Theorem heap_zeroed_at_handoff_bytes : forall chunk h,
  HeapZeroedAtHandoff chunk h ->
  forall q w c b k x, q < length h ->
    nth_error h q = Some (Grant w c b k) ->
    b <= x < b + class_len chunk c ->
    memory_before chunk h q x = 0.
Proof.
  intros chunk h Hz. exact (every_byte_is_zero_at_handoff chunk h Hz).
Qed.

Theorem meta_init_heap_zeroed : forall chunk slots,
  layout_admitted chunk slots ->
  HeapZeroedAtHandoff chunk (ms_hist (meta_init slots)).
Proof.
  intros chunk slots Hladm.
  destruct (meta_init_inv chunk slots Hladm) as [_ [[_ [_ [Hz _]]] _]].
  exact Hz.
Qed.

Theorem meta_step_preserves_heap_zeroed : forall chunk st op,
  meta_inv chunk st ->
  HeapZeroedAtHandoff chunk (ms_hist (meta_step chunk st op)).
Proof.
  intros chunk st op Hinv.
  destruct (meta_step_preserves_inv chunk st op Hinv) as [_ [[_ [_ [Hz _]]] _]].
  exact Hz.
Qed.

Theorem meta_run_refines_heap_zeroed_at_handoff : forall chunk slots ops,
  layout_admitted chunk slots ->
  HeapZeroedAtHandoff chunk (ms_hist (meta_run chunk (meta_init slots) ops)).
Proof.
  intros chunk slots ops Hladm.
  destruct (meta_run_refines_pool_guarantees chunk slots ops Hladm)
    as [_ [_ [Hz _]]].
  exact Hz.
Qed.

Theorem meta_run_refines_heap_guarantees : forall chunk slots ops,
  layout_admitted chunk slots ->
  HeapGuarantees chunk (ms_hist (meta_run chunk (meta_init slots) ops)).
Proof.
  intros chunk slots ops Hladm.
  split.
  - exact (meta_run_refines_heap_narrows chunk slots ops Hladm).
  - exact (meta_run_refines_heap_zeroed_at_handoff chunk slots ops Hladm).
Qed.

(* Q34c Finding 2 refutation: a reused sub-allocation inside a chunk can
   satisfy `HeapNarrows` while retaining the member's own earlier bytes
   unless `HeapZeroedAtHandoff` is also enforced. *)
Definition unzeroed_suballoc_reuse_history : list AllocEvent :=
  [Zero 2048 16; Grant 1 0 2048 (chunk_cap 2048 16); Write 2048 7;
   Release 2048 0; BarrierDone; SweepBegin; SweepEnd;
   Grant 1 0 2048 (chunk_cap 2048 16)].

Theorem unzeroed_reuse_satisfies_heap_narrows_but_not_zeroed :
  HeapNarrows chunk_arena unzeroed_suballoc_reuse_history /\
  ~ HeapZeroedAtHandoff chunk_arena unzeroed_suballoc_reuse_history /\
  memory_before chunk_arena unzeroed_suballoc_reuse_history 7 2048 = 7.
Proof.
  split; [split; [|split]; intros q Hq; refine (all_of_upto _ _ q _ Hq); reflexivity|].
  split; [|reflexivity].
  intros Hz. specialize (Hz 7 eq_refl). discriminate Hz.
Qed.

(* =========================================================================
   3. Per-Island Pool Disjointness and Revocable Union Containment
      (R-08-047a, R-08-005a)
   ========================================================================= *)

Definition rev_granule : nat := 8.
Definition rot_union_align : nat := 64.

Record IslandPoolEntry : Type := {
  ipe_island : nat;
  ipe_mem_class : MemClass;
  ipe_arena : Arena
}.

Record DomainIslandPools : Type := {
  dip_domain : Domain;
  dip_pools : list IslandPoolEntry;
  dip_core_island : nat -> nat;
  dip_launch_core : nat -> option nat;
  dip_island_revocable : nat -> list (nat * nat)
}.

Definition granule_first (b : nat) : nat := b / rev_granule.

Definition granule_limit (b s : nat) : nat := (b + s + (rev_granule - 1)) / rev_granule.

Definition arena_bytes_disjoint (a1 a2 : Arena) : bool :=
  Nat.leb (ar_base a1 + ar_span a1) (ar_base a2)
  || Nat.leb (ar_base a2 + ar_span a2) (ar_base a1).

Definition arena_granules_disjoint (a1 a2 : Arena) : bool :=
  Nat.leb (granule_limit (ar_base a1) (ar_span a1)) (granule_first (ar_base a2))
  || Nat.leb (granule_limit (ar_base a2) (ar_span a2)) (granule_first (ar_base a1)).

Definition entry_key_eqb (e1 e2 : IslandPoolEntry) : bool :=
  Nat.eqb (ipe_island e1) (ipe_island e2)
  && class_eqb (ipe_mem_class e1) (ipe_mem_class e2).

Definition revocable_interval_ok (iv : nat * nat) : bool :=
  let '(b, s) := iv in
  Nat.ltb 0 s
  && Nat.eqb (b mod rot_union_align) 0
  && Nat.eqb ((b + s) mod rot_union_align) 0.

Definition arena_in_revocable_union (a : Arena) (ivs : list (nat * nat)) : bool :=
  any_of (fun iv =>
    let '(b, s) := iv in
    revocable_interval_ok iv
    && Nat.leb b (ar_base a)
    && Nat.leb (ar_base a + ar_span a) (b + s)) ivs.

Definition entry_ok (dip : DomainIslandPools) (e : IslandPoolEntry) : bool :=
  Nat.ltb 0 (ar_span (ipe_arena e))
  && all_of class_exact (ar_classes (ipe_arena e))
  && arena_in_revocable_union (ipe_arena e) (dip_island_revocable dip (ipe_island e)).

Definition entries_separate (e1 e2 : IslandPoolEntry) : bool :=
  negb (entry_key_eqb e1 e2)
  && arena_bytes_disjoint (ipe_arena e1) (ipe_arena e2)
  && arena_granules_disjoint (ipe_arena e1) (ipe_arena e2).

Fixpoint pairwise_pool_disjoint (pools : list IslandPoolEntry) : bool :=
  match pools with
  | [] => true
  | e :: rest => all_of (entries_separate e) rest && pairwise_pool_disjoint rest
  end.

Definition member_launch_bound (dip : DomainIslandPools) (m : nat) : bool :=
  match dip_launch_core dip m with
  | None => false
  | Some core =>
      launch_ok (dip_domain dip) m core
      && all_of (fun mc =>
           any_of (fun e =>
             Nat.eqb (ipe_island e) (dip_core_island dip core)
             && class_eqb (ipe_mem_class e) mc) (dip_pools dip)) all_classes
  end.

Definition domain_island_pools_admitted (dip : DomainIslandPools) : bool :=
  envelope_admits (dip_domain dip)
  && all_of (entry_ok dip) (dip_pools dip)
  && pairwise_pool_disjoint (dip_pools dip)
  && all_of (member_launch_bound dip) (dom_members (dip_domain dip)).

Definition bind_member_pool
    (dip : DomainIslandPools) (m : nat) (mc : MemClass) : option IslandPoolEntry :=
  if mem_nat m (dom_members (dip_domain dip))
  then match dip_launch_core dip m with
       | None => None
       | Some core =>
           if launch_ok (dip_domain dip) m core
           then find (fun e =>
             Nat.eqb (ipe_island e) (dip_core_island dip core)
             && class_eqb (ipe_mem_class e) mc) (dip_pools dip)
           else None
       end
  else None.

Lemma entries_separate_sym : forall e1 e2,
  entries_separate e1 e2 = true -> entries_separate e2 e1 = true.
Proof.
  intros e1 e2 H. unfold entries_separate in *.
  apply andb_prop in H. destruct H as [H Hgr].
  apply andb_prop in H. destruct H as [Hk Hby].
  apply andb_true_intro. split; [apply andb_true_intro; split|].
  - apply negb_true_iff. apply negb_true_iff in Hk.
    destruct (entry_key_eqb e2 e1) eqn:E21; [|reflexivity].
    unfold entry_key_eqb in E21. apply andb_prop in E21. destruct E21 as [Hi Hc].
    apply Nat.eqb_eq in Hi. apply class_eqb_true in Hc.
    unfold entry_key_eqb in Hk. rewrite <- Hi, <- Hc, Nat.eqb_refl, class_eqb_refl in Hk.
    discriminate Hk.
  - unfold arena_bytes_disjoint in *. apply orb_true_iff in Hby. apply orb_true_iff.
    destruct Hby as [H|H]; [right|left]; exact H.
  - unfold arena_granules_disjoint in *. apply orb_true_iff in Hgr. apply orb_true_iff.
    destruct Hgr as [H|H]; [right|left]; exact H.
Qed.

Lemma pairwise_pool_disjoint_nth : forall pools i j e1 e2,
  pairwise_pool_disjoint pools = true ->
  nth_error pools i = Some e1 ->
  nth_error pools j = Some e2 ->
  i <> j ->
  entries_separate e1 e2 = true.
Proof.
  intro pools. induction pools as [|x rest IH]; intros i j e1 e2 Hpd Hi Hj Hne.
  - destruct i; discriminate Hi.
  - simpl in Hpd. apply andb_prop in Hpd. destruct Hpd as [Hx Hr].
    destruct i as [|i]; destruct j as [|j].
    + exfalso. apply Hne. reflexivity.
    + simpl in Hi, Hj. injection Hi as <-.
      apply all_of_in with (l := rest); [exact Hx|]. eapply nth_error_In. exact Hj.
    + simpl in Hi, Hj. injection Hj as <-.
      apply entries_separate_sym.
      apply all_of_in with (l := rest); [exact Hx|]. eapply nth_error_In. exact Hi.
    + simpl in Hi, Hj. apply (IH i j e1 e2 Hr Hi Hj). lia.
Qed.

Lemma granule_separation_implies_byte_and_granule_distinct : forall b1 s1 b2 s2 x1 x2,
  0 < s1 -> 0 < s2 ->
  arena_granules_disjoint
    {| ar_base := b1; ar_span := s1; ar_classes := []; ar_initial := fun _ => 0 |}
    {| ar_base := b2; ar_span := s2; ar_classes := []; ar_initial := fun _ => 0 |} = true ->
  b1 <= x1 < b1 + s1 ->
  b2 <= x2 < b2 + s2 ->
  x1 <> x2 /\ x1 / rev_granule <> x2 / rev_granule.
Proof.
  intros b1 s1 b2 s2 x1 x2 Hs1 Hs2 Hgr Hx1 Hx2.
  unfold arena_granules_disjoint, granule_first, granule_limit, rev_granule in Hgr.
  simpl in Hgr.
  assert (Hstep : forall a c d y, 0 < d -> a <= y < a + d ->
    (a + d + 7) / 8 <= c / 8 -> y / 8 < c / 8).
  { intros a c d y Hd Hy Hlim.
    assert (Hy_div : y / 8 <= (a + d - 1) / 8) by (apply Nat.Div0.div_le_mono; lia).
    assert (Hnext : (a + d - 1) / 8 + 1 = (a + d + 7) / 8).
    { replace (a + d + 7) with ((a + d - 1) + 1 * 8) by lia.
      rewrite Nat.div_add by lia. lia. }
    lia. }
  apply orb_true_iff in Hgr. destruct Hgr as [H12|H21].
  - apply Nat.leb_le in H12.
    assert (Hx1_lt : x1 / 8 < b2 / 8) by (eapply Hstep; [exact Hs1 | exact Hx1 | exact H12]).
    assert (Hb2_le : b2 / 8 <= x2 / 8) by (apply Nat.Div0.div_le_mono; lia).
    unfold rev_granule. split; [|lia].
    intro Heq. subst x2. lia.
  - apply Nat.leb_le in H21.
    assert (Hx2_lt : x2 / 8 < b1 / 8) by (eapply Hstep; [exact Hs2 | exact Hx2 | exact H21]).
    assert (Hb1_le : b1 / 8 <= x1 / 8) by (apply Nat.Div0.div_le_mono; lia).
    unfold rev_granule. split; [|lia].
    intro Heq. subst x2. lia.
Qed.

Theorem island_pools_disjoint_bytes_and_granules :
  forall dip i j e1 e2,
    domain_island_pools_admitted dip = true ->
    nth_error (dip_pools dip) i = Some e1 ->
    nth_error (dip_pools dip) j = Some e2 ->
    i <> j ->
    (ipe_island e1, ipe_mem_class e1) <> (ipe_island e2, ipe_mem_class e2) /\
    arena_bytes_disjoint (ipe_arena e1) (ipe_arena e2) = true /\
    arena_granules_disjoint (ipe_arena e1) (ipe_arena e2) = true /\
    arena_in_revocable_union (ipe_arena e1) (dip_island_revocable dip (ipe_island e1)) = true /\
    arena_in_revocable_union (ipe_arena e2) (dip_island_revocable dip (ipe_island e2)) = true /\
    (forall x1 x2,
      ar_base (ipe_arena e1) <= x1 < ar_base (ipe_arena e1) + ar_span (ipe_arena e1) ->
      ar_base (ipe_arena e2) <= x2 < ar_base (ipe_arena e2) + ar_span (ipe_arena e2) ->
      x1 <> x2 /\ x1 / rev_granule <> x2 / rev_granule).
Proof.
  intros dip i j e1 e2 Hadm Hi Hj Hne.
  unfold domain_island_pools_admitted in Hadm.
  apply andb_prop in Hadm. destruct Hadm as [Hadm _].
  apply andb_prop in Hadm. destruct Hadm as [Hadm Hpd].
  apply andb_prop in Hadm. destruct Hadm as [_ Hent].
  pose proof (pairwise_pool_disjoint_nth (dip_pools dip) i j e1 e2 Hpd Hi Hj Hne) as Hsep.
  unfold entries_separate in Hsep.
  apply andb_prop in Hsep. destruct Hsep as [Hsep Hgr].
  apply andb_prop in Hsep. destruct Hsep as [Hk Hby].
  pose proof (all_of_in _ _ _ _ Hent (nth_error_In _ _ Hi)) as Hok1.
  pose proof (all_of_in _ _ _ _ Hent (nth_error_In _ _ Hj)) as Hok2.
  unfold entry_ok in Hok1, Hok2.
  apply andb_prop in Hok1. destruct Hok1 as [Hok1 Hun1].
  apply andb_prop in Hok1. destruct Hok1 as [Hs1 _].
  apply andb_prop in Hok2. destruct Hok2 as [Hok2 Hun2].
  apply andb_prop in Hok2. destruct Hok2 as [Hs2 _].
  apply Nat.ltb_lt in Hs1. apply Nat.ltb_lt in Hs2.
  split.
  - intro Heq. injection Heq as Hi_eq Hc_eq.
    unfold entry_key_eqb in Hk. rewrite Hi_eq, Hc_eq, Nat.eqb_refl, class_eqb_refl in Hk.
    discriminate Hk.
  - split; [exact Hby|].
    split; [exact Hgr|].
    split; [exact Hun1|].
    split; [exact Hun2|].
    intros x1 x2 Hx1 Hx2.
    eapply granule_separation_implies_byte_and_granule_distinct;
      [exact Hs1 | exact Hs2 | | exact Hx1 | exact Hx2].
    unfold arena_granules_disjoint in *. exact Hgr.
Qed.

Lemma find_some_in_list : forall (A : Type) (p : A -> bool) (l : list A) (x : A),
  find p l = Some x -> In x l /\ p x = true.
Proof.
  intros A p l x. induction l as [|y rest IH]; intros H; simpl in H; [discriminate H|].
  destruct (p y) eqn:Ey.
  - injection H as <-. split; [left; reflexivity | exact Ey].
  - destruct (IH H) as [Hin Hp]. split; [right; exact Hin | exact Hp].
Qed.

Lemma any_of_implies_find_some : forall (A : Type) (p : A -> bool) (l : list A),
  any_of p l = true -> exists x, find p l = Some x.
Proof.
  intros A p l H. induction l as [|y rest IH]; simpl in H; [discriminate H|].
  simpl. destruct (p y) eqn:Ey; [exists y; reflexivity|].
  simpl in H. exact (IH H).
Qed.

Lemma in_mem_nat : forall m l, In m l -> mem_nat m l = true.
Proof.
  intros m l Hin. induction l as [|y rest IH]; [contradiction|].
  simpl. destruct Hin as [->|Hin].
  - rewrite Nat.eqb_refl. reflexivity.
  - rewrite (IH Hin). apply orb_true_r.
Qed.

Theorem member_binds_launch_island_pool :
  forall dip m mc,
    domain_island_pools_admitted dip = true ->
    (In m (dom_members (dip_domain dip)) ->
      exists core e,
        dip_launch_core dip m = Some core /\
        launch_ok (dip_domain dip) m core = true /\
        bind_member_pool dip m mc = Some e /\
        In e (dip_pools dip) /\
        ipe_island e = dip_core_island dip core /\
        ipe_mem_class e = mc /\
        arena_in_revocable_union (ipe_arena e) (dip_island_revocable dip (ipe_island e)) = true) /\
    (~ In m (dom_members (dip_domain dip)) ->
      bind_member_pool dip m mc = None).
Proof.
  intros dip m mc Hadm. split.
  - intro Hin.
    unfold domain_island_pools_admitted in Hadm.
    apply andb_prop in Hadm. destruct Hadm as [Hadm Hmem].
    apply andb_prop in Hadm. destruct Hadm as [Hadm _].
    apply andb_prop in Hadm. destruct Hadm as [_ Hent].
    pose proof (all_of_in _ _ _ _ Hmem Hin) as Hmb.
    unfold member_launch_bound in Hmb.
    destruct (dip_launch_core dip m) as [core|] eqn:Ecore; [|discriminate Hmb].
    apply andb_prop in Hmb. destruct Hmb as [Hlok Hcls].
    assert (Hmc_in : In mc all_classes) by (destruct mc; simpl; auto).
    pose proof (all_of_in _ _ _ _ Hcls Hmc_in) as Hany.
    destruct (any_of_implies_find_some _ _ _ Hany) as [e He].
    exists core, e.
    destruct (find_some_in_list _ _ _ _ He) as [Hein Hep].
    apply andb_prop in Hep. destruct Hep as [Hisl Hmc].
    apply Nat.eqb_eq in Hisl. apply class_eqb_true in Hmc.
    pose proof (all_of_in _ _ _ _ Hent Hein) as Hok.
    unfold entry_ok in Hok. apply andb_prop in Hok. destruct Hok as [_ Hun].
    repeat split; try assumption.
    unfold bind_member_pool. rewrite (in_mem_nat _ _ Hin), Ecore, Hlok. exact He.
  - intro Hnot. unfold bind_member_pool.
    destruct (mem_nat m (dom_members (dip_domain dip))) eqn:Emem; [|reflexivity].
    exfalso. apply Hnot. exact (mem_nat_in _ _ Emem).
Qed.

Definition witness_IslandPoolEntry : IslandPoolEntry := {|
  ipe_island := 0;
  ipe_mem_class := FirstClass;
  ipe_arena := {| ar_base := 64; ar_span := 64;
                  ar_classes := [{| sc_length := 16; sc_align := 16 |}];
                  ar_initial := fun _ => 0 |}
|}.

Definition witness_SecondClassPoolEntry : IslandPoolEntry := {|
  ipe_island := 0;
  ipe_mem_class := SecondClass;
  ipe_arena := {| ar_base := 128; ar_span := 64;
                  ar_classes := [{| sc_length := 32; sc_align := 32 |}];
                  ar_initial := fun _ => 0 |}
|}.

Definition witness_DomainIslandPools : DomainIslandPools := {|
  dip_domain := demo_domain;
  dip_pools := [witness_IslandPoolEntry; witness_SecondClassPoolEntry];
  dip_core_island := fun _ => 0;
  dip_launch_core := fun m => if Nat.ltb m 2 then Some 0 else None;
  dip_island_revocable := fun isl => if Nat.eqb isl 0 then [(64, 128)] else []
|}.

Example demo_domain_island_pools_admitted :
  domain_island_pools_admitted witness_DomainIslandPools = true.
Proof. vm_reflexivity. Qed.

Definition shared_granule_pools : DomainIslandPools := {|
  dip_domain := demo_domain;
  dip_pools :=
    [{| ipe_island := 0; ipe_mem_class := FirstClass;
        ipe_arena := {| ar_base := 64; ar_span := 4;
                        ar_classes := [{| sc_length := 4; sc_align := 4 |}];
                        ar_initial := fun _ => 0 |} |};
     {| ipe_island := 0; ipe_mem_class := SecondClass;
        ipe_arena := {| ar_base := 68; ar_span := 4;
                        ar_classes := [{| sc_length := 4; sc_align := 4 |}];
                        ar_initial := fun _ => 0 |} |}];
  dip_core_island := fun _ => 0;
  dip_launch_core := fun m => if Nat.ltb m 2 then Some 0 else None;
  dip_island_revocable := fun isl => if Nat.eqb isl 0 then [(64, 64)] else []
|}.

Example shared_granule_pools_refused :
  domain_island_pools_admitted shared_granule_pools = false.
Proof. reflexivity. Qed.

(* =========================================================================
   4. Holder-Map / Revocation-Barrier Linking (R-08-006, R-08-007a)
   ========================================================================= *)

Inductive HolderKind : Type :=
| HReg
| HSavedCtx
| HStoredCell.

Record HolderEntry : Type := {
  he_id : nat;
  he_kind : HolderKind;
  he_cap : option Cap
}.

Record LinkedMetaState : Type := {
  lm_meta : MetaState;
  lm_holders : list HolderEntry
}.

Definition witness_HolderEntry : HolderEntry := {|
  he_id := 0;
  he_kind := HReg;
  he_cap := Some (chunk_cap 64 16)
|}.

Definition witness_LinkedMetaState : LinkedMetaState := {|
  lm_meta := witness_MetaState;
  lm_holders := [witness_HolderEntry]
|}.

Definition holder_touches_slot (h : HolderEntry) (s : MetaSlot) : bool :=
  match he_cap h, ms_phase s with
  | Some k, PPending =>
      overlaps (cap_base k) (cap_length k)
               (sl_base (ms_layout s)) (sl_len (ms_layout s))
  | _, _ => false
  end.

Definition no_holder_for_pending
    (holders : list HolderEntry) (slots : list MetaSlot) : bool :=
  all_of (fun s => negb (any_of (fun h => holder_touches_slot h s) holders)) slots.

Inductive LinkedOp : Type :=
| LMeta (op : MetaOp)
| LClearHolder (holder_idx : nat)
| LAddHolder (h : HolderEntry).

Definition clear_holder_entry (h : HolderEntry) : HolderEntry :=
  {| he_id := he_id h; he_kind := he_kind h; he_cap := None |}.

Fixpoint clear_holder_at (idx : nat) (hs : list HolderEntry) : list HolderEntry :=
  match hs, idx with
  | [], _ => []
  | h :: rest, 0 => clear_holder_entry h :: rest
  | h :: rest, S n => h :: clear_holder_at n rest
  end.

Definition linked_init (slots : list SlotLayout) (holders : list HolderEntry)
  : LinkedMetaState := {|
  lm_meta := meta_init slots;
  lm_holders := holders
|}.

Definition linked_step (a : Arena) (st : LinkedMetaState) (lop : LinkedOp)
  : LinkedMetaState :=
  match lop with
  | LMeta OpBarrier =>
      if no_holder_for_pending (lm_holders st) (ms_slots (lm_meta st))
      then {| lm_meta := meta_step a (lm_meta st) OpBarrier;
              lm_holders := lm_holders st |}
      else st
  | LMeta op =>
      {| lm_meta := meta_step a (lm_meta st) op;
         lm_holders := lm_holders st |}
  | LClearHolder idx =>
      {| lm_meta := lm_meta st;
         lm_holders := clear_holder_at idx (lm_holders st) |}
  | LAddHolder h =>
      {| lm_meta := lm_meta st;
         lm_holders := lm_holders st ++ [h] |}
  end.

Fixpoint linked_run (a : Arena) (st : LinkedMetaState) (lops : list LinkedOp)
  : LinkedMetaState :=
  match lops with
  | [] => st
  | lop :: rest => linked_run a (linked_step a st lop) rest
  end.

Fixpoint effective_meta_ops (a : Arena) (st : LinkedMetaState) (lops : list LinkedOp)
  : list MetaOp :=
  match lops with
  | [] => []
  | lop :: rest =>
      let prefix :=
        match lop with
        | LMeta OpBarrier =>
            if no_holder_for_pending (lm_holders st) (ms_slots (lm_meta st))
            then [OpBarrier] else []
        | LMeta op => [op]
        | LClearHolder _ => []
        | LAddHolder _ => []
        end in
      prefix ++ effective_meta_ops a (linked_step a st lop) rest
  end.

Lemma meta_run_app : forall a st ops1 ops2,
  meta_run a st (ops1 ++ ops2) = meta_run a (meta_run a st ops1) ops2.
Proof.
  intros a st ops1 ops2. revert st.
  induction ops1 as [|op rest IH]; intros st; simpl; [reflexivity|].
  apply IH.
Qed.

Theorem linked_run_refines_meta_run : forall a lops st,
  lm_meta (linked_run a st lops) =
  meta_run a (lm_meta st) (effective_meta_ops a st lops).
Proof.
  intros a lops. induction lops as [|lop rest IH]; intros st; simpl; [reflexivity|].
  rewrite IH. destruct lop as [op|idx|h]; simpl.
  - destruct op; simpl; try reflexivity.
    destruct (no_holder_for_pending (lm_holders st) (ms_slots (lm_meta st))); reflexivity.
  - reflexivity.
  - reflexivity.
Qed.

Theorem linked_run_refines_pool_guarantees : forall a slots holders lops,
  layout_admitted a slots ->
  PoolGuarantees a (ms_hist (lm_meta (linked_run a (linked_init slots holders) lops))).
Proof.
  intros a slots holders lops Hladm.
  rewrite linked_run_refines_meta_run. simpl.
  exact (meta_run_refines_pool_guarantees a slots
           (effective_meta_ops a (linked_init slots holders) lops) Hladm).
Qed.

Theorem linked_run_refines_heap_narrows : forall a slots holders lops,
  layout_admitted a slots ->
  HeapNarrows a (ms_hist (lm_meta (linked_run a (linked_init slots holders) lops))).
Proof.
  intros a slots holders lops Hladm.
  rewrite linked_run_refines_meta_run. simpl.
  exact (meta_run_refines_heap_narrows a slots
           (effective_meta_ops a (linked_init slots holders) lops) Hladm).
Qed.

Theorem linked_run_refines_heap_zeroed_at_handoff : forall a slots holders lops,
  layout_admitted a slots ->
  HeapZeroedAtHandoff a (ms_hist (lm_meta (linked_run a (linked_init slots holders) lops))).
Proof.
  intros a slots holders lops Hladm.
  rewrite linked_run_refines_meta_run. simpl.
  exact (meta_run_refines_heap_zeroed_at_handoff a slots
           (effective_meta_ops a (linked_init slots holders) lops) Hladm).
Qed.

Lemma holder_blocks_no_holder_for_pending : forall holders slots s h k,
  In s slots ->
  ms_phase s = PPending ->
  In h holders ->
  he_cap h = Some k ->
  overlaps (cap_base k) (cap_length k)
           (sl_base (ms_layout s)) (sl_len (ms_layout s)) = true ->
  no_holder_for_pending holders slots = false.
Proof.
  intros holders slots s h k Hs Hph Hh Hcap Hov.
  destruct (no_holder_for_pending holders slots) eqn:E; [|reflexivity].
  unfold no_holder_for_pending in E.
  pose proof (all_of_in _ _ _ _ E Hs) as Hneg.
  apply negb_true_iff in Hneg.
  assert (Htouch : holder_touches_slot h s = true).
  { unfold holder_touches_slot. rewrite Hcap, Hph. exact Hov. }
  assert (Hany : any_of (fun h0 => holder_touches_slot h0 s) holders = true).
  { clear E Hneg. induction holders as [|hd tl IH]; [contradiction|].
    simpl. destruct Hh as [->|Hh].
    - rewrite Htouch. reflexivity.
    - rewrite (IH Hh). apply orb_true_r. }
  rewrite Hany in Hneg. discriminate Hneg.
Qed.

Lemma linked_barrier_blocked_inert : forall a st idx s h k,
  nth_error (ms_slots (lm_meta st)) idx = Some s ->
  ms_phase s = PPending ->
  In h (lm_holders st) ->
  he_cap h = Some k ->
  overlaps (cap_base k) (cap_length k)
           (sl_base (ms_layout s)) (sl_len (ms_layout s)) = true ->
  no_holder_for_pending (lm_holders st) (ms_slots (lm_meta st)) = false /\
  linked_step a st (LMeta OpBarrier) = st.
Proof.
  intros a st idx s h k Es Hph Hh Hcap Hov.
  pose proof (holder_blocks_no_holder_for_pending
                (lm_holders st) (ms_slots (lm_meta st)) s h k
                (nth_error_In _ _ Es) Hph Hh Hcap Hov) as Hblk.
  split; [exact Hblk|].
  simpl. rewrite Hblk. reflexivity.
Qed.

Lemma nth_error_map_slot_phase_pending : forall f slots idx s,
  nth_error slots idx = Some s ->
  ms_phase s = PPending ->
  f PPending = PPending ->
  nth_error (map (map_slot_phase f) slots) idx = Some s.
Proof.
  intros f slots idx s Es Hph Hf.
  rewrite nth_error_map, Es. simpl. f_equal.
  unfold map_slot_phase. destruct s as [l ph z]. simpl in *.
  subst ph. rewrite Hf. reflexivity.
Qed.

Theorem stale_holder_any_kind_blocks_barrier_and_reuse :
  forall a st idx s h k,
    nth_error (ms_slots (lm_meta st)) idx = Some s ->
    ms_phase s = PPending ->
    In h (lm_holders st) ->
    he_cap h = Some k ->
    overlaps (cap_base k) (cap_length k)
             (sl_base (ms_layout s)) (sl_len (ms_layout s)) = true ->
    no_holder_for_pending (lm_holders st) (ms_slots (lm_meta st)) = false /\
    linked_step a st (LMeta OpBarrier) = st /\
    let st' := linked_run a st [LMeta OpBarrier; LMeta OpSweepBegin; LMeta OpSweepEnd] in
    nth_error (ms_slots (lm_meta st')) idx = Some s /\
    linked_step a st' (LMeta (OpAlloc idx)) = st'.
Proof.
  intros a st idx s h k Es Hph Hh Hcap Hov.
  destruct (linked_barrier_blocked_inert a st idx s h k Es Hph Hh Hcap Hov)
    as [Hblk Hbar].
  split; [exact Hblk | split; [exact Hbar|]].
  cbv zeta. simpl. rewrite Hblk.
  assert (Hsb : nth_error (ms_slots (lm_meta (linked_step a st (LMeta OpSweepBegin)))) idx = Some s).
  { simpl. destruct (negb (ms_sweep_active (lm_meta st))); [|exact Es].
    simpl. apply nth_error_map_slot_phase_pending; [exact Es | exact Hph | reflexivity]. }
  assert (Hse : nth_error (ms_slots (lm_meta (linked_run a st [LMeta OpSweepBegin; LMeta OpSweepEnd]))) idx = Some s).
  { simpl. destruct (negb (ms_sweep_active (lm_meta st))) eqn:Esw.
    - simpl. apply nth_error_map_slot_phase_pending; [|exact Hph | reflexivity].
      simpl in Hsb. rewrite Esw in Hsb. exact Hsb.
    - destruct (ms_sweep_active (lm_meta st)) eqn:Esw2; [|exact Es].
      simpl. apply nth_error_map_slot_phase_pending; [exact Es | exact Hph | reflexivity]. }
  split; [exact Hse|].
  simpl in Hse |- *. rewrite Hse, Hph. reflexivity.
Qed.

Theorem stale_register_copy_blocks_barrier_and_reuse :
  forall a st idx s h k,
    nth_error (ms_slots (lm_meta st)) idx = Some s ->
    ms_phase s = PPending ->
    In h (lm_holders st) ->
    he_kind h = HReg ->
    he_cap h = Some k ->
    overlaps (cap_base k) (cap_length k)
             (sl_base (ms_layout s)) (sl_len (ms_layout s)) = true ->
    no_holder_for_pending (lm_holders st) (ms_slots (lm_meta st)) = false /\
    linked_step a st (LMeta OpBarrier) = st /\
    let st' := linked_run a st [LMeta OpBarrier; LMeta OpSweepBegin; LMeta OpSweepEnd] in
    nth_error (ms_slots (lm_meta st')) idx = Some s /\
    linked_step a st' (LMeta (OpAlloc idx)) = st'.
Proof.
  intros a st idx s h k Es Hph Hh _ Hcap Hov.
  exact (stale_holder_any_kind_blocks_barrier_and_reuse a st idx s h k Es Hph Hh Hcap Hov).
Qed.

Definition linked_stale_holders : list HolderEntry :=
  [{| he_id := 0; he_kind := HReg; he_cap := Some (chunk_cap 64 16) |};
   {| he_id := 1; he_kind := HSavedCtx; he_cap := None |};
   {| he_id := 2; he_kind := HStoredCell; he_cap := None |}].

Example linked_clear_register_enables_barrier_and_reuse :
  let init := linked_init meta_ref_slots linked_stale_holders in
  let pending := linked_run pool_reference_arena init
                   [LMeta (OpAlloc 0); LMeta (OpRelease 0)] in
  linked_step pool_reference_arena pending (LMeta OpBarrier) = pending /\
  let reused := linked_run pool_reference_arena pending
                  [LClearHolder 0; LMeta OpBarrier; LMeta OpSweepBegin;
                   LMeta OpSweepEnd; LMeta (OpAlloc 0)] in
  map ms_phase (ms_slots (lm_meta reused)) = [PLive; PFree] /\
  ms_next_id (lm_meta reused) = 2.
Proof. split; [vm_reflexivity | split; vm_reflexivity]. Qed.

(* =========================================================================
   5. Parent/Child Descendant Lifetime Refinement
   ========================================================================= *)

Record NestedHeapState : Type := {
  nh_parent : MetaState;
  nh_parent_gens : list nat;
  nh_bound_slot : nat;
  nh_bound_gen : nat;
  nh_child : MetaState
}.

Definition witness_NestedHeapState : NestedHeapState := {|
  nh_parent := witness_MetaState;
  nh_parent_gens := [0];
  nh_bound_slot := 0;
  nh_bound_gen := 1;
  nh_child := witness_MetaState
|}.

Inductive ChildOp : Type :=
| ChildAlloc (slot_idx : nat)
| ChildWrite (slot_idx off val : nat)
| ChildRelease (slot_idx : nat)
| ChildBarrier
| ChildSweepBegin
| ChildSweepEnd.

Definition child_to_meta_op (cop : ChildOp) : MetaOp :=
  match cop with
  | ChildAlloc idx => OpAlloc idx
  | ChildWrite idx off val => OpWrite idx off val
  | ChildRelease idx => OpRelease idx
  | ChildBarrier => OpBarrier
  | ChildSweepBegin => OpSweepBegin
  | ChildSweepEnd => OpSweepEnd
  end.

Inductive NestedOp : Type :=
| NParent (op : MetaOp)
| NChild (cop : ChildOp).

Fixpoint inc_gen_at (idx : nat) (gens : list nat) : list nat :=
  match gens, idx with
  | [], _ => []
  | g :: rest, 0 => S g :: rest
  | g :: rest, S n => g :: inc_gen_at n rest
  end.

Lemma nth_error_inc_gen_eq : forall idx gens g,
  nth_error gens idx = Some g ->
  nth_error (inc_gen_at idx gens) idx = Some (S g).
Proof.
  intro idx. induction idx as [|idx IH]; intros gens g Hnth.
  - destruct gens; [discriminate Hnth|]. simpl in *. injection Hnth as <-. reflexivity.
  - destruct gens; [discriminate Hnth|]. simpl in *. apply IH. exact Hnth.
Qed.

Lemma nth_error_inc_gen_ne : forall idx j gens,
  j <> idx ->
  nth_error (inc_gen_at idx gens) j = nth_error gens j.
Proof.
  intro idx. induction idx as [|idx IH]; intros j gens Hne.
  - destruct gens; destruct j; simpl; try reflexivity. exfalso. apply Hne. reflexivity.
  - destruct gens; destruct j; simpl; try reflexivity. apply IH. lia.
Qed.

Lemma nth_error_inc_gen_none : forall idx gens,
  nth_error gens idx = None ->
  nth_error (inc_gen_at idx gens) idx = None.
Proof.
  intro idx. induction idx as [|idx IH]; intros gens Hnth.
  - destruct gens; simpl in *; [reflexivity | discriminate Hnth].
  - destruct gens; simpl in *; [reflexivity | apply IH; exact Hnth].
Qed.

Definition parent_binding_live (nh : NestedHeapState) : bool :=
  match nth_error (ms_slots (nh_parent nh)) (nh_bound_slot nh),
        nth_error (nh_parent_gens nh) (nh_bound_slot nh) with
  | Some s, Some g =>
      match ms_phase s with
      | PLive => Nat.eqb g (nh_bound_gen nh)
      | _ => false
      end
  | _, _ => false
  end.

Definition nested_init
    (parent_st : MetaState) (parent_gens : list nat)
    (parent_slot parent_gen : nat) (child_slots : list SlotLayout)
  : NestedHeapState := {|
  nh_parent := parent_st;
  nh_parent_gens := parent_gens;
  nh_bound_slot := parent_slot;
  nh_bound_gen := parent_gen;
  nh_child := meta_init child_slots
|}.

Definition nested_step (pa ca : Arena) (nh : NestedHeapState) (nop : NestedOp)
  : NestedHeapState :=
  match nop with
  | NParent op =>
      let gens' :=
        match op with
        | OpAlloc idx =>
            match nth_error (ms_slots (nh_parent nh)) idx with
            | Some s =>
                match ms_phase s with
                | PFree => inc_gen_at idx (nh_parent_gens nh)
                | _ => nh_parent_gens nh
                end
            | None => nh_parent_gens nh
            end
        | _ => nh_parent_gens nh
        end in
      {| nh_parent := meta_step pa (nh_parent nh) op;
         nh_parent_gens := gens';
         nh_bound_slot := nh_bound_slot nh;
         nh_bound_gen := nh_bound_gen nh;
         nh_child := nh_child nh |}
  | NChild cop =>
      if parent_binding_live nh
      then {| nh_parent := nh_parent nh;
              nh_parent_gens := nh_parent_gens nh;
              nh_bound_slot := nh_bound_slot nh;
              nh_bound_gen := nh_bound_gen nh;
              nh_child := meta_step ca (nh_child nh) (child_to_meta_op cop) |}
      else nh
  end.

Fixpoint nested_run (pa ca : Arena) (nh : NestedHeapState) (nops : list NestedOp)
  : NestedHeapState :=
  match nops with
  | [] => nh
  | nop :: rest => nested_run pa ca (nested_step pa ca nh nop) rest
  end.

Lemma nested_run_preserves_invs : forall pa ca nops nh,
  meta_inv pa (nh_parent nh) ->
  meta_inv ca (nh_child nh) ->
  meta_inv pa (nh_parent (nested_run pa ca nh nops)) /\
  meta_inv ca (nh_child (nested_run pa ca nh nops)).
Proof.
  intros pa ca nops. induction nops as [|nop rest IH]; intros nh Hp Hc; simpl;
    [exact (conj Hp Hc)|].
  apply IH; destruct nop as [op|cop]; simpl.
  - exact (meta_step_preserves_inv pa (nh_parent nh) op Hp).
  - destruct (parent_binding_live nh); [exact Hp | exact Hp].
  - exact Hc.
  - destruct (parent_binding_live nh);
      [exact (meta_step_preserves_inv ca (nh_child nh) (child_to_meta_op cop) Hc) | exact Hc].
Qed.

Theorem nested_run_refines_parent_and_child_guarantees :
  forall pa ca nh nops,
    meta_inv pa (nh_parent nh) ->
    meta_inv ca (nh_child nh) ->
    PoolGuarantees pa (ms_hist (nh_parent (nested_run pa ca nh nops))) /\
    HeapGuarantees ca (ms_hist (nh_child (nested_run pa ca nh nops))).
Proof.
  intros pa ca nh nops Hp Hc.
  destruct (nested_run_preserves_invs pa ca nops nh Hp Hc)
    as [[_ [Hpg _]] [_ [Hcg _]]].
  split; [exact Hpg|].
  destruct Hcg as [Hd [He [Hz Hr]]].
  exact (conj (conj He (conj Hd Hr)) Hz).
Qed.

Definition bound_permanently_dead (nh : NestedHeapState) : Prop :=
  match nth_error (ms_slots (nh_parent nh)) (nh_bound_slot nh),
        nth_error (nh_parent_gens nh) (nh_bound_slot nh) with
  | Some s, Some g =>
      (ms_phase s <> PLive /\ nh_bound_gen nh <= g) \/
      (S (nh_bound_gen nh) <= g)
  | _, _ => True
  end.

Lemma bound_permanently_dead_not_live : forall nh,
  bound_permanently_dead nh -> parent_binding_live nh = false.
Proof.
  intros nh Hdead. unfold bound_permanently_dead, parent_binding_live in *.
  destruct (nth_error (ms_slots (nh_parent nh)) (nh_bound_slot nh)) as [s|]; [|reflexivity].
  destruct (nth_error (nh_parent_gens nh) (nh_bound_slot nh)) as [g|]; [|reflexivity].
  destruct (ms_phase s); try reflexivity.
  destruct Hdead as [[Hne _]|Hgt]; [exfalso; apply Hne; reflexivity|].
  apply Nat.eqb_neq. lia.
Qed.

Lemma bound_permanently_dead_intro : forall nh,
  (forall s g,
    nth_error (ms_slots (nh_parent nh)) (nh_bound_slot nh) = Some s ->
    nth_error (nh_parent_gens nh) (nh_bound_slot nh) = Some g ->
    (ms_phase s <> PLive /\ nh_bound_gen nh <= g) \/ (S (nh_bound_gen nh) <= g)) ->
  bound_permanently_dead nh.
Proof.
  intros nh H. unfold bound_permanently_dead.
  destruct (nth_error (ms_slots (nh_parent nh)) (nh_bound_slot nh)) as [s|] eqn:Es; [|exact I].
  destruct (nth_error (nh_parent_gens nh) (nh_bound_slot nh)) as [g|] eqn:Eg; [|exact I].
  exact (H s g eq_refl eq_refl).
Qed.

Lemma bound_permanently_dead_elim : forall nh s g,
  bound_permanently_dead nh ->
  nth_error (ms_slots (nh_parent nh)) (nh_bound_slot nh) = Some s ->
  nth_error (nh_parent_gens nh) (nh_bound_slot nh) = Some g ->
  (ms_phase s <> PLive /\ nh_bound_gen nh <= g) \/ (S (nh_bound_gen nh) <= g).
Proof.
  intros nh s g Hdead Es Eg. unfold bound_permanently_dead in Hdead.
  rewrite Es, Eg in Hdead. exact Hdead.
Qed.

Lemma map_slot_phase_dead_preserved : forall f s g nh,
  (forall ph, ph <> PLive -> f ph <> PLive) ->
  (ms_phase s <> PLive /\ nh_bound_gen nh <= g \/ S (nh_bound_gen nh) <= g) ->
  ms_phase (map_slot_phase f s) <> PLive /\ nh_bound_gen nh <= g \/ S (nh_bound_gen nh) <= g.
Proof.
  intros f [l ph z] g nh Hf Hprev. unfold map_slot_phase in *. simpl in *.
  destruct Hprev as [[Hne Hle]|Hgt].
  - left. split; [exact (Hf ph Hne) | exact Hle].
  - right. exact Hgt.
Qed.

Lemma nested_step_preserves_dead : forall pa ca nh nop,
  bound_permanently_dead nh ->
  bound_permanently_dead (nested_step pa ca nh nop) /\
  nh_child (nested_step pa ca nh nop) = nh_child nh.
Proof.
  intros pa ca nh nop Hdead.
  pose proof (bound_permanently_dead_not_live nh Hdead) as Hnl.
  destruct nop as [op|cop].
  - split; [|reflexivity].
    destruct op as [idx|idx off val|idx| | |]; simpl.
    + destruct (nth_error (ms_slots (nh_parent nh)) idx) as [s0|] eqn:Es0;
        simpl; [|exact Hdead].
      destruct (ms_phase s0) eqn:Eph0; simpl; try exact Hdead.
      apply bound_permanently_dead_intro. intros s g Hs Hg. simpl in *.
      destruct (Nat.eq_dec idx (nh_bound_slot nh)) as [Heq|Hne].
      * subst idx.
        rewrite (nth_error_replace_slot_eq (nh_bound_slot nh) _ s0 _ Es0) in Hs.
        injection Hs as <-.
        destruct (nth_error (nh_parent_gens nh) (nh_bound_slot nh)) as [g0|] eqn:Eg0.
        -- rewrite (nth_error_inc_gen_eq (nh_bound_slot nh) _ g0 Eg0) in Hg.
           injection Hg as Heqg. rewrite <- Heqg.
           pose proof (bound_permanently_dead_elim nh s0 g0 Hdead Es0 Eg0) as Hprev.
           destruct Hprev as [[_ Hle]|Hgt]; right; lia.
        -- rewrite (nth_error_inc_gen_none (nh_bound_slot nh) _ Eg0) in Hg. discriminate Hg.
      * rewrite (nth_error_replace_slot_ne idx (nh_bound_slot nh) _ _ ltac:(lia)) in Hs.
        rewrite (nth_error_inc_gen_ne idx (nh_bound_slot nh) _ ltac:(lia)) in Hg.
        exact (bound_permanently_dead_elim nh s g Hdead Hs Hg).
    + destruct (nth_error (ms_slots (nh_parent nh)) idx) as [s0|] eqn:Es0;
        simpl; [|exact Hdead].
      destruct (ms_phase s0) eqn:Eph0; simpl; try exact Hdead.
      destruct (Nat.ltb off (sl_len (ms_layout s0))); simpl; [|exact Hdead].
      apply bound_permanently_dead_intro. intros s g Hs Hg. simpl in *.
      destruct (Nat.eq_dec idx (nh_bound_slot nh)) as [Heq|Hne].
      * subst idx.
        rewrite (nth_error_replace_slot_eq (nh_bound_slot nh) _ s0 _ Es0) in Hs.
        injection Hs as <-.
        pose proof (bound_permanently_dead_elim nh s0 g Hdead Es0 Hg) as Hprev.
        rewrite Eph0 in Hprev. exact Hprev.
      * rewrite (nth_error_replace_slot_ne idx (nh_bound_slot nh) _ _ ltac:(lia)) in Hs.
        exact (bound_permanently_dead_elim nh s g Hdead Hs Hg).
    + destruct (nth_error (ms_slots (nh_parent nh)) idx) as [s0|] eqn:Es0;
        simpl; [|exact Hdead].
      destruct (ms_phase s0) eqn:Eph0; simpl; try exact Hdead.
      apply bound_permanently_dead_intro. intros s g Hs Hg. simpl in *.
      destruct (Nat.eq_dec idx (nh_bound_slot nh)) as [Heq|Hne].
      * subst idx.
        rewrite (nth_error_replace_slot_eq (nh_bound_slot nh) _ s0 _ Es0) in Hs.
        injection Hs as <-.
        pose proof (bound_permanently_dead_elim nh s0 g Hdead Es0 Hg) as Hprev.
        destruct Hprev as [[_ Hle]|Hgt]; left; split; try discriminate; lia.
      * rewrite (nth_error_replace_slot_ne idx (nh_bound_slot nh) _ _ ltac:(lia)) in Hs.
        exact (bound_permanently_dead_elim nh s g Hdead Hs Hg).
    + apply bound_permanently_dead_intro. intros s g Hs Hg. simpl in *.
      rewrite nth_error_map in Hs.
      destruct (nth_error (ms_slots (nh_parent nh)) (nh_bound_slot nh)) as [s0|] eqn:Es0;
        [|discriminate Hs].
      simpl in Hs. injection Hs as <-.
      pose proof (bound_permanently_dead_elim nh s0 g Hdead Es0 Hg) as Hprev.
      apply map_slot_phase_dead_preserved; [|exact Hprev].
      intros ph Hne; destruct ph; try discriminate; exfalso; apply Hne; reflexivity.
    + destruct (negb (ms_sweep_active (nh_parent nh))); simpl; [|exact Hdead].
      apply bound_permanently_dead_intro. intros s g Hs Hg. simpl in *.
      rewrite nth_error_map in Hs.
      destruct (nth_error (ms_slots (nh_parent nh)) (nh_bound_slot nh)) as [s0|] eqn:Es0;
        [|discriminate Hs].
      simpl in Hs. injection Hs as <-.
      pose proof (bound_permanently_dead_elim nh s0 g Hdead Es0 Hg) as Hprev.
      apply map_slot_phase_dead_preserved; [|exact Hprev].
      intros ph Hne; destruct ph; try discriminate; exfalso; apply Hne; reflexivity.
    + destruct (ms_sweep_active (nh_parent nh)); simpl; [|exact Hdead].
      apply bound_permanently_dead_intro. intros s g Hs Hg. simpl in *.
      rewrite nth_error_map in Hs.
      destruct (nth_error (ms_slots (nh_parent nh)) (nh_bound_slot nh)) as [s0|] eqn:Es0;
        [|discriminate Hs].
      simpl in Hs. injection Hs as <-.
      pose proof (bound_permanently_dead_elim nh s0 g Hdead Es0 Hg) as Hprev.
      apply map_slot_phase_dead_preserved; [|exact Hprev].
      intros ph Hne; destruct ph; try discriminate; exfalso; apply Hne; reflexivity.
  - simpl. rewrite Hnl. split; [exact Hdead | reflexivity].
Qed.

Lemma nested_run_preserves_dead : forall pa ca nops nh,
  bound_permanently_dead nh ->
  bound_permanently_dead (nested_run pa ca nh nops) /\
  nh_child (nested_run pa ca nh nops) = nh_child nh.
Proof.
  intros pa ca nops. induction nops as [|nop rest IH]; intros nh Hdead; simpl;
    [exact (conj Hdead eq_refl)|].
  destruct (nested_step_preserves_dead pa ca nh nop Hdead) as [Hdead1 Hch1].
  destruct (IH (nested_step pa ca nh nop) Hdead1) as [Hdead2 Hch2].
  split; [exact Hdead2 | congruence].
Qed.

Theorem parent_release_invalidates_descendant_forever :
  forall pa ca nh s,
    nth_error (ms_slots (nh_parent nh)) (nh_bound_slot nh) = Some s ->
    ms_phase s = PLive ->
    nth_error (nh_parent_gens nh) (nh_bound_slot nh) = Some (nh_bound_gen nh) ->
    let nh_rel := nested_step pa ca nh (NParent (OpRelease (nh_bound_slot nh))) in
    forall nops,
      let nh_after := nested_run pa ca nh_rel nops in
      parent_binding_live nh_after = false /\
      nh_child nh_after = nh_child nh /\
      (forall idx, nested_step pa ca nh_after (NChild (ChildAlloc idx)) = nh_after) /\
      (forall idx off val,
        nested_step pa ca nh_after (NChild (ChildWrite idx off val)) = nh_after) /\
      (forall idx, nested_step pa ca nh_after (NChild (ChildRelease idx)) = nh_after).
Proof.
  intros pa ca nh s Es Hph Eg.
  set (nh_rel := nested_step pa ca nh (NParent (OpRelease (nh_bound_slot nh)))).
  assert (Hdead0 : bound_permanently_dead nh_rel).
  { unfold nh_rel, bound_permanently_dead. simpl.
    rewrite Es, Hph. simpl.
    rewrite (nth_error_replace_slot_eq (nh_bound_slot nh) _ s _ Es). simpl. rewrite Eg.
    simpl. left. split; [discriminate | lia]. }
  assert (Hch0 : nh_child nh_rel = nh_child nh) by reflexivity.
  cbv zeta. intro nops.
  destruct (nested_run_preserves_dead pa ca nops nh_rel Hdead0) as [Hdead_a Hch_a].
  pose proof (bound_permanently_dead_not_live _ Hdead_a) as Hnl.
  split; [exact Hnl|].
  split; [congruence|].
  split; [intro idx; simpl; rewrite Hnl; reflexivity|].
  split; [intros idx off val; simpl; rewrite Hnl; reflexivity|].
  intro idx. simpl. rewrite Hnl. reflexivity.
Qed.

Definition nested_child_slots : list SlotLayout :=
  [{| sl_base := 64; sl_class := 0; sl_len := 8 |};
   {| sl_base := 72; sl_class := 0; sl_len := 8 |}].

Definition nested_child_arena : Arena := {|
  ar_base := 64; ar_span := 16;
  ar_classes := [{| sc_length := 8; sc_align := 8 |}];
  ar_initial := fun _ => 19
|}.

Example parent_realloc_at_next_gen_keeps_old_descendant_dead :
  let p0 := meta_step pool_reference_arena (meta_init meta_ref_slots) (OpAlloc 0) in
  let nh0 := nested_init p0 [1; 0] 0 1 nested_child_slots in
  let nh1 := nested_run pool_reference_arena nested_child_arena nh0
               [NChild (ChildAlloc 0);
                NParent (OpRelease 0); NParent OpBarrier;
                NParent OpSweepBegin; NParent OpSweepEnd;
                NParent (OpAlloc 0)] in
  nth_error (nh_parent_gens nh1) 0 = Some 2 /\
  parent_binding_live nh1 = false /\
  nested_step pool_reference_arena nested_child_arena nh1 (NChild (ChildAlloc 1)) = nh1 /\
  nested_step pool_reference_arena nested_child_arena nh1 (NChild (ChildWrite 0 0 99)) = nh1 /\
  nested_step pool_reference_arena nested_child_arena nh1 (NChild (ChildRelease 0)) = nh1.
Proof.
  repeat split; vm_reflexivity.
Qed.

(* =========================================================================
   6. Exhausted-Class Refusal (R-08-047)
   ========================================================================= *)

Fixpoint find_free_slot_in_class (cls idx : nat) (slots : list MetaSlot) : option nat :=
  match slots with
  | [] => None
  | s :: rest =>
      match ms_phase s with
      | PFree => if Nat.eqb (sl_class (ms_layout s)) cls
                 then Some idx
                 else find_free_slot_in_class cls (S idx) rest
      | _ => find_free_slot_in_class cls (S idx) rest
      end
  end.

Definition meta_alloc_class (a : Arena) (st : MetaState) (cls : nat) : MetaState * bool :=
  match find_free_slot_in_class cls 0 (ms_slots st) with
  | Some idx => (meta_step a st (OpAlloc idx), true)
  | None => (st, false)
  end.

Definition class_exhausted (st : MetaState) (cls : nat) : Prop :=
  forall i s,
    nth_error (ms_slots st) i = Some s ->
    sl_class (ms_layout s) = cls ->
    ms_phase s <> PFree.

Lemma find_free_slot_in_class_none : forall cls slots idx,
  (forall i s, nth_error slots i = Some s ->
    sl_class (ms_layout s) = cls -> ms_phase s <> PFree) ->
  find_free_slot_in_class cls idx slots = None.
Proof.
  intros cls slots. induction slots as [|s rest IH]; intros idx Hexh; simpl; [reflexivity|].
  assert (Hrest : forall i s0, nth_error rest i = Some s0 ->
    sl_class (ms_layout s0) = cls -> ms_phase s0 <> PFree).
  { intros i s0 Hi Hc. exact (Hexh (S i) s0 Hi Hc). }
  destruct (ms_phase s) eqn:Eph; try exact (IH (S idx) Hrest).
  destruct (Nat.eqb (sl_class (ms_layout s)) cls) eqn:Ec; [|exact (IH (S idx) Hrest)].
  apply Nat.eqb_eq in Ec.
  exfalso. exact (Hexh 0 s eq_refl Ec Eph).
Qed.

Theorem exhausted_class_refuses_allocation : forall a st cls,
  class_exhausted st cls ->
  meta_alloc_class a st cls = (st, false) /\
  (forall idx s,
    nth_error (ms_slots st) idx = Some s ->
    sl_class (ms_layout s) = cls ->
    meta_step a st (OpAlloc idx) = st) /\
  ms_slots (fst (meta_alloc_class a st cls)) = ms_slots st /\
  ms_hist (fst (meta_alloc_class a st cls)) = ms_hist st /\
  (forall x,
    memory_before a (ms_hist (fst (meta_alloc_class a st cls)))
                    (length (ms_hist (fst (meta_alloc_class a st cls)))) x =
    memory_before a (ms_hist st) (length (ms_hist st)) x).
Proof.
  intros a st cls Hexh.
  assert (Hnone : find_free_slot_in_class cls 0 (ms_slots st) = None).
  { apply find_free_slot_in_class_none. exact Hexh. }
  assert (Halloc : meta_alloc_class a st cls = (st, false)).
  { unfold meta_alloc_class. rewrite Hnone. reflexivity. }
  repeat split.
  - exact Halloc.
  - intros idx s Es Hcls. simpl. rewrite Es.
    pose proof (Hexh idx s Es Hcls) as Hnp.
    destruct (ms_phase s); try reflexivity.
    exfalso. apply Hnp. reflexivity.
  - rewrite Halloc. reflexivity.
  - rewrite Halloc. reflexivity.
  - intro x. rewrite Halloc. reflexivity.
Qed.

Definition mixed_class_slots : list SlotLayout :=
  [{| sl_base := 64; sl_class := 0; sl_len := 16 |};
   {| sl_base := 96; sl_class := 1; sl_len := 32 |}].

Example exhausted_class_cannot_borrow_witness :
  let st := meta_run pool_reference_arena (meta_init mixed_class_slots)
              [OpAlloc 0; OpWrite 0 3 42] in
  meta_alloc_class pool_reference_arena st 0 = (st, false) /\
  map ms_phase (ms_slots st) = [PLive; PFree] /\
  memory_before pool_reference_arena (ms_hist st) (length (ms_hist st)) 67 = 42.
Proof.
  repeat split; vm_reflexivity.
Qed.


