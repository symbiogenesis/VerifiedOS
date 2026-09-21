(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   Finite one-hot encoding in both directions, for optional host LRAT research.

   A row is one finite placement domain or the finite domain of height vectors.
   At-least-one and at-most-one clauses choose a value in every row. Negative
   binary clauses forbid incompatible selections. The Python encoder represents
   alignment, fixed locations, pools and reservations in the row domains; extent
   overlap, aliases and height bounds become forbidden pairs. A distinct DIMACS
   variable names each (row,value) cell.

   `finite_encoding_equivalent` proves equivalence between this finite constraint
   model and the corresponding one-hot Boolean clause semantics. Its constructive
   completeness direction is the one needed to transfer an LRAT refutation back
   to absence of a finite selection. Decoding safety alone does not imply that.

   Scope: this file does not prove Python domain extraction, integer serialization,
   cell-to-DIMACS numbering, physical lifetime extraction, or native checker I/O.
   Those are explicit implementation/refinement obligations. The external checker
   is upstream lrat_isa, whose Isabelle proof reaches its exported LLVM; this Rocq
   file does not import that proof or claim a theorem about the retargeted binary.
   No clause, parser, producer or checker is admitted here. These are optional host
   experiments and do not amend R-05-104 or R-05-105 production optimizer policy.

   R-08-014 supplies the interference obligation represented by forbidden pairs;
   R-08-012d motivates a stated objective, not an unstated physical-memory metric.
   This model does not discharge those admission obligations. R-05-163 audits the
   compiled constants. For R-05-165 and R-05-166, examples construct both a legal
   selection and its one-hot witness, and reject an overlapping Boolean choice.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-104 R-05-105 R-05-163 R-05-165 R-05-166 R-08-012d R-08-014
   SHA256: f51c2dd92503129f1a3602b655d019693282ad96f2e8003b0cdcf6370eb8805a
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Import ListNotations.

Definition Cell := (nat * nat)%type.
Definition Domains := nat -> list nat.
Definition Assignment := nat -> nat -> bool.
Definition Selection := nat -> nat.

Definition well_formed_pairs (rows : nat) (forbidden : list (Cell * Cell)) : Prop :=
  forall a b, In (a, b) forbidden -> fst a < rows /\ fst b < rows.

Definition legal_selection (rows : nat) (domains : Domains)
  (forbidden : list (Cell * Cell)) (selected : Selection) : Prop :=
  (forall row, row < rows -> In (selected row) (domains row)) /\
  (forall a b, In (a, b) forbidden ->
    ~ (selected (fst a) = snd a /\ selected (fst b) = snd b)).

(* These are precisely the three clause families' Boolean satisfaction clauses:
   a positive disjunction; negative pair clauses within a row; forbidden pairs.
   The serialized DIMACS emitter is not identified with this definition by fiat. *)
Definition encoded_sat (rows : nat) (domains : Domains)
  (forbidden : list (Cell * Cell)) (assignment : Assignment) : Prop :=
  (forall row, row < rows -> exists value,
    In value (domains row) /\ assignment row value = true) /\
  (forall row a b, row < rows -> In a (domains row) -> In b (domains row) ->
    a <> b -> assignment row a = false \/ assignment row b = false) /\
  (forall a b, In (a, b) forbidden ->
    assignment (fst a) (snd a) = false \/ assignment (fst b) (snd b) = false).

Definition encode_selection (selected : Selection) : Assignment :=
  fun row value => selected row =? value.

Theorem legal_selection_has_encoded_witness : forall rows domains forbidden selected,
  legal_selection rows domains forbidden selected ->
  encoded_sat rows domains forbidden (encode_selection selected).
Proof.
  intros rows domains forbidden selected [HD HP].
  unfold encoded_sat, encode_selection. split; [| split].
  - intros row HR. exists (selected row). split; [now apply HD | apply Nat.eqb_refl].
  - intros row a b _ _ _ HNE.
    destruct (selected row =? a) eqn:EA; [right | now left].
    apply Nat.eqb_neq. apply Nat.eqb_eq in EA. congruence.
  - intros a b HAB. specialize (HP a b HAB).
    destruct (selected (fst a) =? snd a) eqn:EA; [right | now left].
    apply Nat.eqb_neq. apply Nat.eqb_eq in EA. tauto.
Qed.

Definition decode_row (domain : list nat) (assignment : nat -> bool) : nat :=
  match find assignment domain with Some value => value | None => 0 end.

Lemma decode_row_present : forall domain assignment,
  (exists value, In value domain /\ assignment value = true) ->
  In (decode_row domain assignment) domain /\
  assignment (decode_row domain assignment) = true.
Proof.
  intros domain assignment [value [HD HA]]. unfold decode_row.
  destruct (find assignment domain) as [chosen |] eqn:HF.
  - now apply find_some.
  - rewrite (find_none _ _ HF value HD) in HA. discriminate.
Qed.

Definition decode_assignment (domains : Domains) (assignment : Assignment) : Selection :=
  fun row => decode_row (domains row) (assignment row).

Theorem encoded_witness_decodes_safely : forall rows domains forbidden assignment,
  well_formed_pairs rows forbidden -> encoded_sat rows domains forbidden assignment ->
  legal_selection rows domains forbidden (decode_assignment domains assignment).
Proof.
  intros rows domains forbidden assignment HW [HE [_ HP]].
  assert (HD : forall row, row < rows ->
    In (decode_assignment domains assignment row) (domains row) /\
    assignment row (decode_assignment domains assignment row) = true).
  { intros row HR. apply decode_row_present. apply HE. exact HR. }
  split.
  - intros row HR. apply (HD row HR).
  - intros a b HAB [EA EB]. destruct (HW a b HAB) as [HA HB].
    destruct (HD (fst a) HA) as [_ TA]. destruct (HD (fst b) HB) as [_ TB].
    destruct (HP a b HAB); congruence.
Qed.

Theorem finite_encoding_equivalent : forall rows domains forbidden,
  well_formed_pairs rows forbidden ->
  ((exists selected, legal_selection rows domains forbidden selected) <->
   (exists assignment, encoded_sat rows domains forbidden assignment)).
Proof.
  intros rows domains forbidden HW. split.
  - intros [selected HL]. exists (encode_selection selected).
    apply legal_selection_has_encoded_witness. exact HL.
  - intros [assignment HS]. exists (decode_assignment domains assignment).
    apply encoded_witness_decodes_safely; assumption.
Qed.

Theorem unsat_excludes_every_legal_selection : forall rows domains forbidden,
  ~ (exists assignment, encoded_sat rows domains forbidden assignment) ->
  ~ (exists selected, legal_selection rows domains forbidden selected).
Proof.
  intros rows domains forbidden HU [selected HS]. apply HU.
  exists (encode_selection selected). apply legal_selection_has_encoded_witness. exact HS.
Qed.

(* The upstream-model coverage premise is stated explicitly. A decoder theorem
   cannot replace it: every smaller legal layout must have an encoded witness. *)
Theorem optimum_requires_encoding_completeness :
  forall (Layout : Type) (valid : Layout -> Prop) (cost : Layout -> nat)
         rows domains forbidden (candidate : Layout),
  valid candidate ->
  (forall layout, valid layout -> cost layout < cost candidate ->
    exists selected, legal_selection rows domains forbidden selected) ->
  ~ (exists assignment, encoded_sat rows domains forbidden assignment) ->
  valid candidate /\ forall layout, valid layout -> cost candidate <= cost layout.
Proof.
  intros Layout valid cost rows domains forbidden candidate HC HCOV HU.
  split; [exact HC | intros layout HL]. apply Nat.nlt_ge. intros HLT.
  apply (unsat_excludes_every_legal_selection rows domains forbidden HU).
  exact (HCOV layout HL HLT).
Qed.

Definition demo_domains : Domains := fun _ => [0; 1].
Definition demo_forbidden : list (Cell * Cell) :=
  [((0, 0), (1, 0)); ((0, 1), (1, 1))].
Definition demo_selection : Selection := fun row => if row =? 0 then 0 else 1.

Example demo_selection_legal : legal_selection 2 demo_domains demo_forbidden demo_selection.
Proof.
  split.
  - intros row _. unfold demo_domains, demo_selection.
    destruct (row =? 0); [left | right; left]; reflexivity.
  - intros a b [H | [H | []]]; injection H as <- <-; intros [E0 E1]; discriminate.
Qed.

Example demo_assignment_satisfies :
  encoded_sat 2 demo_domains demo_forbidden (encode_selection demo_selection).
Proof. apply legal_selection_has_encoded_witness. exact demo_selection_legal. Qed.

Example conflicting_assignment_rejected :
  ~ encoded_sat 2 demo_domains demo_forbidden (fun _ value => value =? 0).
Proof.
  intros [_ [_ HP]].
  destruct (HP (0, 0) (1, 0) (in_eq _ _)) as [H | H]; discriminate H.
Qed.

Print Assumptions legal_selection_has_encoded_witness.
Print Assumptions encoded_witness_decodes_safely.
Print Assumptions finite_encoding_equivalent.
Print Assumptions unsat_excludes_every_legal_selection.
Print Assumptions optimum_requires_encoding_completeness.
