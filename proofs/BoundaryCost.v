(* SPDX-License-Identifier: Apache-2.0 *)
(* Boundary admission arithmetic for R-07-040 and R-11-009. R-15-220's
   platform cost remains owned by PartitionContext; R-15-220a's context
   bound is a separate composition input. These are declared cycle bounds,
   not measured timing evidence. A residency case covers one complete
   timer-to-handler prefix: remaining irrevocable operation followed by its
   consequent handler, or the remainder of an already live kernel path.
   The two fields cover non-overlapping execution, so they add.

   Refinement must establish coverage of every reachable successful prefix,
   soundness of its costs and continued service after timer delivery. The
   arithmetic below establishes none of those physical premises. Faults
   requiring fail-stop have no successful-release obligation. *)

Require Import PartitionContext.

Record ResidencyCase : Type := {
  remaining_operation : nat;
  remaining_handler : nat
}.

Record BoundaryInputs : Type := {
  context_cost : nat;
  residency_cases : list ResidencyCase
}.

Definition prefix_cost (p : ResidencyCase) : nat :=
  remaining_operation p + remaining_handler p.

Fixpoint residency_max (ps : list ResidencyCase) : nat :=
  match ps with
  | nil => 0
  | cons p rest => Nat.max (prefix_cost p) (residency_max rest)
  end.

Definition boundary_nonempty (b : BoundaryInputs) : bool :=
  match residency_cases b with nil => false | cons _ _ => true end.

Definition full_switch_cost (m : Machine) (b : BoundaryInputs) : nat :=
  switch_cost m + context_cost b.

Definition boundary_cost (m : Machine) (b : BoundaryInputs) : nat :=
  residency_max (residency_cases b) + full_switch_cost m b.

Fixpoint DeclaredCase (p : ResidencyCase) (ps : list ResidencyCase) : Prop :=
  match ps with nil => False | cons q rest => p = q \/ DeclaredCase p rest end.

(* An explicit refinement obligation, never a field automatically discharged
   by a nonempty declaration. It allows conservative case bounds, and requires
   operation and handler soundness separately before their sum is consumed. *)
Definition ResidencyRefines (b : BoundaryInputs)
    (reachable : ResidencyCase -> Prop) : Prop :=
  forall actual : ResidencyCase, reachable actual ->
    exists declared : ResidencyCase,
      DeclaredCase declared (residency_cases b) /\
      Nat.leb (remaining_operation actual) (remaining_operation declared) = true /\
      Nat.leb (remaining_handler actual) (remaining_handler declared) = true.

(* Prelude-only arithmetic, with a prefix to avoid shadowing consumers. *)
Lemma bc_leb_refl : forall n : nat, Nat.leb n n = true.
Proof. induction n; simpl; [reflexivity | exact IHn]. Qed.

Lemma bc_leb_trans : forall a b c : nat,
  Nat.leb a b = true -> Nat.leb b c = true -> Nat.leb a c = true.
Proof.
  induction a; intros b c Hab Hbc; [reflexivity |].
  destruct b; [discriminate Hab |]. destruct c; [discriminate Hbc |].
  simpl in *. exact (IHa b c Hab Hbc).
Qed.

Lemma bc_add_zero : forall a : nat, a + 0 = a.
Proof. induction a; simpl; [reflexivity | rewrite IHa; reflexivity]. Qed.

Lemma bc_add_succ : forall a b : nat, a + S b = S (a + b).
Proof. induction a; intros b; simpl; [reflexivity | rewrite IHa; reflexivity]. Qed.

Lemma bc_add_comm : forall a b : nat, a + b = b + a.
Proof.
  induction a; intros b; simpl.
  - rewrite bc_add_zero. reflexivity.
  - rewrite IHa, bc_add_succ. reflexivity.
Qed.

Lemma bc_add_left : forall k a b : nat,
  Nat.leb a b = true -> Nat.leb (k + a) (k + b) = true.
Proof. induction k; intros a b H; simpl; [exact H | apply IHk; exact H]. Qed.

Lemma bc_add_mono : forall a b c d : nat,
  Nat.leb a b = true -> Nat.leb c d = true ->
  Nat.leb (a + c) (b + d) = true.
Proof.
  intros a b c d Hab Hcd.
  apply (bc_leb_trans (a + c) (a + d) (b + d)).
  - apply bc_add_left. exact Hcd.
  - rewrite (bc_add_comm a d), (bc_add_comm b d).
    apply bc_add_left. exact Hab.
Qed.

Lemma bc_max_left : forall a b : nat, Nat.leb a (Nat.max a b) = true.
Proof.
  induction a; intros b; [reflexivity |].
  destruct b; simpl; [apply bc_leb_refl | apply IHa].
Qed.

Lemma bc_max_right : forall a b : nat, Nat.leb b (Nat.max a b) = true.
Proof.
  induction a; intros b; simpl; [apply bc_leb_refl |].
  destruct b; simpl; [reflexivity | apply IHa].
Qed.

Lemma bc_max_upper : forall a b c : nat,
  Nat.leb a c = true -> Nat.leb b c = true ->
  Nat.leb (Nat.max a b) c = true.
Proof.
  induction a; intros b c Ha Hb; simpl; [exact Hb |].
  destruct c; [discriminate Ha |]. destruct b; simpl; [exact Ha |].
  apply IHa; assumption.
Qed.

Lemma bc_sub_padding : forall elapsed bound : nat,
  Nat.leb elapsed bound = true -> elapsed + (bound - elapsed) = bound.
Proof.
  induction elapsed; intros bound H.
  - destruct bound; reflexivity.
  - destruct bound; [discriminate H |]. simpl in *.
    rewrite (IHelapsed bound H). reflexivity.
Qed.

Theorem residency_bounds_declared_case : forall ps p,
  DeclaredCase p ps -> Nat.leb (prefix_cost p) (residency_max ps) = true.
Proof.
  induction ps as [|q rest IH]; intros p H; simpl in H; [contradiction |].
  simpl. destruct H as [H | H].
  - rewrite H. apply bc_max_left.
  - apply (bc_leb_trans _ (residency_max rest) _).
    + exact (IH p H).
    + apply bc_max_right.
Qed.

Theorem boundary_bounds_declared_prefix : forall m b p,
  DeclaredCase p (residency_cases b) ->
  Nat.leb (prefix_cost p + full_switch_cost m b) (boundary_cost m b) = true.
Proof.
  intros m b p H. unfold boundary_cost. apply bc_add_mono.
  - apply residency_bounds_declared_case. exact H.
  - apply bc_leb_refl.
Qed.

Theorem boundary_bounds_refined_prefix : forall m b reachable actual,
  ResidencyRefines b reachable -> reachable actual ->
  Nat.leb (prefix_cost actual + full_switch_cost m b) (boundary_cost m b) = true.
Proof.
  intros m b reachable actual Href Hactual.
  destruct (Href actual Hactual) as [declared [Hin [Hop Hhandler]]].
  apply (bc_leb_trans _ (prefix_cost declared + full_switch_cost m b) _).
  - apply bc_add_mono; [unfold prefix_cost; apply bc_add_mono; assumption |].
    apply bc_leb_refl.
  - apply boundary_bounds_declared_prefix. exact Hin.
Qed.

Definition padded_release (m : Machine) (b : BoundaryInputs)
    (table_instant elapsed : nat) : nat :=
  table_instant + (elapsed + (boundary_cost m b - elapsed)).

Theorem padding_fixes_successful_release : forall m b table_instant elapsed,
  Nat.leb elapsed (boundary_cost m b) = true ->
  padded_release m b table_instant elapsed = table_instant + boundary_cost m b.
Proof.
  intros m b table_instant elapsed H. unfold padded_release.
  rewrite (bc_sub_padding elapsed (boundary_cost m b) H). reflexivity.
Qed.

Theorem successful_release_is_prefix_independent : forall m b t p q,
  DeclaredCase p (residency_cases b) -> DeclaredCase q (residency_cases b) ->
  padded_release m b t (prefix_cost p + full_switch_cost m b) =
  padded_release m b t (prefix_cost q + full_switch_cost m b).
Proof.
  intros m b t p q Hp Hq.
  rewrite (padding_fixes_successful_release m b t _
    (boundary_bounds_declared_prefix m b p Hp)).
  rewrite (padding_fixes_successful_release m b t _
    (boundary_bounds_declared_prefix m b q Hq)). reflexivity.
Qed.

(* Pointwise domination also permits adding cases: each old declared case
   must have a new case covering both its sequential components. *)
Definition CasesDominated (old newer : list ResidencyCase) : Prop :=
  forall p, DeclaredCase p old -> exists q,
    DeclaredCase q newer /\
    Nat.leb (remaining_operation p) (remaining_operation q) = true /\
    Nat.leb (remaining_handler p) (remaining_handler q) = true.

Theorem residency_max_monotone : forall old newer,
  CasesDominated old newer -> Nat.leb (residency_max old) (residency_max newer) = true.
Proof.
  induction old as [|p rest IH]; intros newer Hdom; [reflexivity |].
  simpl. apply bc_max_upper.
  - destruct (Hdom p (or_introl eq_refl)) as [q [Hq [Hop Hhandler]]].
    apply (bc_leb_trans _ (prefix_cost q) _).
    + unfold prefix_cost. apply bc_add_mono; assumption.
    + apply residency_bounds_declared_case. exact Hq.
  - apply IH. intros q Hq. apply Hdom. right. exact Hq.
Qed.

Theorem boundary_components_monotone : forall m n b c,
  Nat.leb (fence_t_cost m) (fence_t_cost n) = true ->
  Nat.leb (vmclear_cost m) (vmclear_cost n) = true ->
  Nat.leb (opp_relock_cost m) (opp_relock_cost n) = true ->
  Nat.leb (context_cost b) (context_cost c) = true ->
  CasesDominated (residency_cases b) (residency_cases c) ->
  Nat.leb (boundary_cost m b) (boundary_cost n c) = true.
Proof.
  intros m n b c Hf Hv Ho Hctx Hcases.
  unfold boundary_cost, full_switch_cost, switch_cost.
  apply bc_add_mono; [apply residency_max_monotone; exact Hcases |].
  apply bc_add_mono; [|exact Hctx].
  apply bc_add_mono; [apply bc_add_mono; assumption |exact Ho].
Qed.

(* Arbitrary inhabited demonstrations: idle, live kernel, unbuffered
   operation, and operation followed by a synchronous handler. *)
Definition idle_prefix : ResidencyCase := Build_ResidencyCase 0 0.
Definition live_kernel_prefix : ResidencyCase := Build_ResidencyCase 0 2.
Definition unbuffered_prefix : ResidencyCase := Build_ResidencyCase 2 0.
Definition operation_fault_prefix : ResidencyCase := Build_ResidencyCase 2 1.
Definition demo_boundary_inputs : BoundaryInputs :=
  Build_BoundaryInputs 2 (cons idle_prefix (cons live_kernel_prefix
    (cons unbuffered_prefix (cons operation_fault_prefix nil)))).
Definition empty_boundary_inputs : BoundaryInputs := Build_BoundaryInputs 0 nil.

Example idle_is_explicitly_nonempty :
  boundary_nonempty (Build_BoundaryInputs 0 (cons idle_prefix nil)) = true := eq_refl.
Example missing_cases_are_not_idle : boundary_nonempty empty_boundary_inputs = false := eq_refl.
Example the_four_prefix_cases_have_bound_three :
  residency_max (residency_cases demo_boundary_inputs) = 3 := eq_refl.
Example the_full_boundary_is_twenty :
  boundary_cost demo_rotation_swaps demo_boundary_inputs = 20 := eq_refl.

(* Each alternative underprices an actual member followed by its switch.
   The counterexamples use the same declared cases and machine throughout. *)
Example omitted_context_is_refuted :
  Nat.leb (prefix_cost operation_fault_prefix + full_switch_cost demo_rotation_swaps demo_boundary_inputs)
    (residency_max (residency_cases demo_boundary_inputs) + switch_cost demo_rotation_swaps) = false := eq_refl.
Example omitted_operation_is_refuted :
  Nat.leb (prefix_cost unbuffered_prefix + full_switch_cost demo_rotation_swaps demo_boundary_inputs)
    (remaining_handler unbuffered_prefix + full_switch_cost demo_rotation_swaps demo_boundary_inputs) = false := eq_refl.
Example max_instead_of_sequential_sum_is_refuted :
  Nat.leb (prefix_cost operation_fault_prefix + full_switch_cost demo_rotation_swaps demo_boundary_inputs)
    (Nat.max (remaining_operation operation_fault_prefix) (remaining_handler operation_fault_prefix)
       + full_switch_cost demo_rotation_swaps demo_boundary_inputs) = false := eq_refl.

Definition witness_ResidencyCase : ResidencyCase := operation_fault_prefix.
Definition witness_BoundaryInputs : BoundaryInputs := demo_boundary_inputs.

Print Assumptions residency_bounds_declared_case.
Print Assumptions boundary_bounds_declared_prefix.
Print Assumptions boundary_bounds_refined_prefix.
Print Assumptions padding_fixes_successful_release.
Print Assumptions successful_release_is_prefix_independent.
Print Assumptions residency_max_monotone.
Print Assumptions boundary_components_monotone.
Print Assumptions omitted_context_is_refuted.
Print Assumptions omitted_operation_is_refuted.
Print Assumptions max_instead_of_sequential_sum_is_refuted.
