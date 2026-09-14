(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   MemoryPlannerResources.v

   Logical credit and elapsed-bound arithmetic for preallocated component
   request slots. The host contract checker additionally requires checked fixed
   offsets and accounts for overhead: scalar free bytes alone do not guarantee
   a contiguous, aligned extent. Neither an online allocator nor a collector
   is implemented by these definitions. No donor implementation or proof is
   imported. The specification pattern is discussed in
   docs/implementation/static-memory-resource-contracts.md.

   required_credit is the exact initial credit required for a finite sequence
   of Take and Return actions. Returns are protocol facts, supplied only at
   validated reuse barriers by the host extractor. run_credit independently
   executes forward. required_credit_exact proves success precisely at or
   above the inferred requirement; below_requirement_fails exhibits failure
   below it. credit_conservation accounts for every issued and returned byte.
   balanced_trace_restores_credit states the reusable-slot postcondition, and
   repeated_balanced_traces_fit extends it to any finite number of invocations.

   These credit theorems do not prove that a Return names its own outstanding
   allocation or that holders and device users drained. Those independent
   identity and barrier checks belong to the bounded component interpreter and
   MemoryPlannerContracts.v. The host checks each pool/slot separately and
   checks fixed placement before presenting success. Its certificate emitter
   produces concrete run_credit and deadline examples for independent kernel
   replay; no theorem equates its Python code to this Gallina implementation.

   release_deadline_sound transports pointwise admitted elapsed upper bounds
   through their sum. The bounds must already include preemption, blocking,
   device completion and cleanup. It neither derives hardware timing nor
   turns fairness, wait-freedom or an event count into a wall-clock deadline.

   R-08-046 supplies bounded structure admission; R-08-014 still owns physical
   interference, and R-08-015 keeps safe reuse separate. R-08-006 and R-08-007a
   supply containment and the subsequent full pass; credit returns before
   those facts are outside this contract. R-11-015 owns actual placed-image
   timing. These entries are cited, never discharged. R-05-163 audits every
   compiled assumption. R-05-165 and R-05-166 are witnessed by a concrete
   balanced nonlexical trace, failure one byte below its required credit, a
   lost return that fails restoration, and a delayed cleanup refutation.
   ========================================================================= *)

From Stdlib Require Import List Arith Lia.
Import ListNotations.

Inductive CreditEvent := Take (bytes : nat) | Return (bytes : nat).

Fixpoint required_credit (events : list CreditEvent) : nat :=
  match events with
  | [] => 0
  | Take n :: rest => n + required_credit rest
  | Return n :: rest => required_credit rest - n
  end.

Fixpoint run_credit (events : list CreditEvent) (credit : nat) : option nat :=
  match events with
  | [] => Some credit
  | Take n :: rest =>
      if n <=? credit then run_credit rest (credit - n) else None
  | Return n :: rest => run_credit rest (credit + n)
  end.

Theorem required_credit_exact : forall events credit,
  (exists final, run_credit events credit = Some final) <-> required_credit events <= credit.
Proof.
  induction events as [| event rest IH]; intro credit.
  - simpl. split; [lia | intro H; eexists; reflexivity].
  - destruct event as [n | n]; cbn [run_credit required_credit].
    + destruct (n <=? credit) eqn:HC.
      * apply Nat.leb_le in HC. rewrite IH. lia.
      * apply Nat.leb_gt in HC. split.
        -- intros [final H]. discriminate.
        -- lia.
    + rewrite IH. lia.
Qed.

Theorem below_requirement_fails : forall events credit,
  credit < required_credit events -> run_credit events credit = None.
Proof.
  intros events credit H. destruct (run_credit events credit) as [final |] eqn:HR; auto.
  assert (required_credit events <= credit).
  { apply required_credit_exact. exists final. exact HR. }
  lia.
Qed.

Fixpoint taken (events : list CreditEvent) : nat :=
  match events with
  | [] => 0
  | Take n :: rest => n + taken rest
  | Return _ :: rest => taken rest
  end.

Fixpoint returned (events : list CreditEvent) : nat :=
  match events with
  | [] => 0
  | Take _ :: rest => returned rest
  | Return n :: rest => n + returned rest
  end.

Theorem credit_conservation : forall events initial final,
  run_credit events initial = Some final ->
  final + taken events = initial + returned events.
Proof.
  induction events as [| event rest IH]; intros initial final HR.
  - simpl in HR. inversion HR. simpl. lia.
  - destruct event as [n | n]; cbn [run_credit] in HR.
    + destruct (n <=? initial) eqn:HC; try discriminate.
      apply Nat.leb_le in HC. apply IH in HR. cbn [taken returned]. lia.
    + apply IH in HR. cbn [taken returned]. lia.
Qed.

Theorem balanced_trace_restores_credit : forall events initial,
  taken events = returned events -> required_credit events <= initial ->
  run_credit events initial = Some initial.
Proof.
  intros events initial HB HC.
  apply required_credit_exact in HC. destruct HC as [final HR].
  pose proof (credit_conservation events initial final HR). replace final with initial in HR by lia.
  exact HR.
Qed.

Lemma run_credit_app : forall first second initial intermediate,
  run_credit first initial = Some intermediate ->
  run_credit (first ++ second) initial = run_credit second intermediate.
Proof.
  induction first as [| event rest IH]; intros second initial intermediate HR.
  - simpl in HR. inversion HR. reflexivity.
  - destruct event as [n | n]; cbn [run_credit] in HR; cbn [app run_credit].
    + destruct (n <=? initial) eqn:HC; try discriminate. apply IH. exact HR.
    + apply IH. exact HR.
Qed.

Theorem repeated_balanced_traces_fit : forall events initial repetitions,
  taken events = returned events -> required_credit events <= initial ->
  run_credit (concat (repeat events repetitions)) initial = Some initial.
Proof.
  intros events initial repetitions HB HC. induction repetitions as [| count IH].
  - reflexivity.
  - simpl. rewrite (run_credit_app events (concat (repeat events count)) initial initial)
      by (apply balanced_trace_restores_credit; assumption).
    exact IH.
Qed.

Definition partial_credit_spec (events : list CreditEvent) (initial : nat)
  (result : option nat) : Prop :=
  result = None \/ exists final, result = Some final /\
                                final + taken events = initial + returned events.

Theorem resource_aware_refines_partial : forall events initial,
  required_credit events <= initial ->
  partial_credit_spec events initial (run_credit events initial) /\
  run_credit events initial <> None.
Proof.
  intros events initial HC. apply required_credit_exact in HC.
  destruct HC as [final HR]. split.
  - right. exists final. split; [exact HR | eapply credit_conservation; exact HR].
  - rewrite HR. discriminate.
Qed.

Theorem elapsed_bounds_sum : forall actual bounds,
  Forall2 le actual bounds -> list_sum actual <= list_sum bounds.
Proof.
  intros actual bounds H. induction H; simpl; lia.
Qed.

Theorem release_deadline_sound : forall actual bounds deadline,
  Forall2 le actual bounds -> list_sum bounds <= deadline ->
  list_sum actual <= deadline.
Proof. intros. pose proof (elapsed_bounds_sum actual bounds H). lia. Qed.

Definition nonlexical_trace : list CreditEvent :=
  [Take 4; Take 3; Return 4; Take 2; Return 3; Return 2].

Example crossing_credit_requirement : required_credit nonlexical_trace = 7.
Proof. reflexivity. Qed.

Example enough_credit_guarantees_success : run_credit nonlexical_trace 7 = Some 7.
Proof. reflexivity. Qed.

Example insufficient_credit_rejected : run_credit nonlexical_trace 6 = None.
Proof. reflexivity. Qed.

Example lost_obligation_is_not_restored : run_credit [Take 4; Take 3; Return 3] 7 = Some 3.
Proof. reflexivity. Qed.

Example cleanup_bound_satisfied : Forall2 le [1; 3; 1; 2; 1] [1; 4; 2; 2; 1] /\
                                  list_sum [1; 4; 2; 2; 1] <= 10.
Proof. repeat constructor; lia. Qed.

Example delayed_cleanup_refuted : ~ (list_sum [1; 5; 2; 2; 1] <= 10).
Proof. simpl. lia. Qed.

Print Assumptions required_credit_exact.
Print Assumptions credit_conservation.
Print Assumptions repeated_balanced_traces_fit.
Print Assumptions resource_aware_refines_partial.
Print Assumptions release_deadline_sound.
