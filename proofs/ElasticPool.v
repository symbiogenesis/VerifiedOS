(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   Executable history-indexed pool reference for R-08-047b and R-15-007k.
   The step checks the new event only; the prefix lemma proves that earlier
   grants keep their guarantees. This reference is not a bounded native service.
   The finite metadata implementation in vos/elastic_pool.py needs its own
   refinement to this producer before Q34c can close. No accepted assumption
   stands in for that missing theorem or the physical R-08-006 barrier.
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Require Import CyclicExecutive MemoryPlan ElasticDomain.
Import ListNotations.
Local Open Scope nat_scope.

Lemma pool_upto_in : forall n k, In k (upto n) -> k < n.
Proof.
  induction n; intros k H; simpl in H; [contradiction|].
  apply in_app_or in H. destruct H as [H|[H|H]].
  - specialize (IHn k H). lia.
  - subst. lia.
  - contradiction.
Qed.

Lemma pool_all_ext : forall (A : Type) (l : list A) f g,
  (forall x, In x l -> f x = g x) -> all_of f l = all_of g l.
Proof.
  intros A l; induction l; intros f g H; simpl; auto.
  rewrite (H a (or_introl eq_refl)). f_equal. apply IHl.
  intros x Hx. apply H. now right.
Qed.

Lemma pool_any_ext : forall (A : Type) (l : list A) f g,
  (forall x, In x l -> f x = g x) -> any_of f l = any_of g l.
Proof.
  intros A l; induction l; intros f g H; simpl; auto.
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
  { induction events0 as [|e rest IH]; intros h Hh; simpl; auto.
    apply IH. now apply pool_event_preserves_guarantees. }
  apply H. apply (proj2 (pool_guarantees_points a [])).
  intros q Hq. simpl in Hq. lia.
Qed.

Theorem heap_run_narrows : forall chunk events,
  HeapNarrows chunk (pool_run chunk [] events).
Proof.
  intros. destruct (pool_run_refines_four_guarantees chunk events)
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
Proof. vm_compute. reflexivity. Qed.

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

Print Assumptions pool_run_refines_four_guarantees.
Print Assumptions heap_run_narrows.
