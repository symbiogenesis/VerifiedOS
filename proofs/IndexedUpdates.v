(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   IndexedUpdates.v

   Pointwise semantics for a fold of independent indexed updates. The state
   may carry additional data; only the selected memory view is constrained.
   R-05-163 audits these generic laws, which the service equivalence proofs
   instantiate under R-08-011 and R-08-014's reservation and separation scope.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-08-011 R-08-014
   SHA256: bc2379bae58b761b29586b5743242fb28d624d994b0427364bdf579282840dab
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import List Bool PeanoNat Lia.
Import ListNotations.

Lemma existsb_index_spec : forall j indices,
  existsb (Nat.eqb j) indices = true <-> In j indices.
Proof.
  intros j indices. rewrite existsb_exists. split.
  - intros [i [Hin Heq]]. apply Nat.eqb_eq in Heq. subst i. exact Hin.
  - intro Hin. exists j. split; [exact Hin | apply Nat.eqb_refl].
Qed.

Theorem fold_distinct_updates : forall (S A : Type)
    (view : S -> nat -> A) (update : S -> nat -> S)
    (transform : nat -> A -> A),
  (forall st i j,
    view (update st i) j =
      if j =? i then transform i (view st i) else view st j) ->
  forall indices, NoDup indices -> forall initial j,
    view (fold_left update indices initial) j =
      if existsb (Nat.eqb j) indices
      then transform j (view initial j) else view initial j.
Proof.
  intros S A view update transform Hupdate indices Hdistinct.
  induction Hdistinct as [|i rest Habsent Hdistinct IH]; intros initial j.
  - reflexivity.
  - cbn [fold_left existsb]. rewrite IH, !Hupdate.
    destruct (j =? i) eqn:Heq.
    + apply Nat.eqb_eq in Heq. subst j.
      assert (Hmiss : existsb (Nat.eqb i) rest = false).
      { destruct (existsb (Nat.eqb i) rest) eqn:Hin; [|reflexivity].
        apply existsb_index_spec in Hin. contradiction. }
      rewrite Hmiss. reflexivity.
    + destruct (existsb (Nat.eqb j) rest); reflexivity.
Qed.

Lemma existsb_prefix : forall j count,
  existsb (Nat.eqb j) (seq 0 count) = (j <? count).
Proof.
  intros j count. destruct (existsb (Nat.eqb j) (seq 0 count)) eqn:Hin.
  - symmetry. apply Nat.ltb_lt. apply existsb_index_spec in Hin.
    apply in_seq in Hin. lia.
  - symmetry. apply Bool.not_true_is_false. intro Hlt.
    apply Nat.ltb_lt in Hlt.
    assert (Hmember : existsb (Nat.eqb j) (seq 0 count) = true).
    { apply existsb_index_spec. apply in_seq. lia. }
    rewrite Hin in Hmember. discriminate.
Qed.

Corollary fold_prefix_updates : forall (S A : Type)
    (view : S -> nat -> A) (update : S -> nat -> S)
    (transform : nat -> A -> A),
  (forall st i j,
    view (update st i) j =
      if j =? i then transform i (view st i) else view st j) ->
  forall initial count j,
    view (fold_left update (seq 0 count) initial) j =
      if j <? count then transform j (view initial j) else view initial j.
Proof.
  intros S A view update transform Hupdate initial count j.
  assert (Hdistinct : NoDup (seq 0 count)) by apply seq_NoDup.
  rewrite (fold_distinct_updates S A view update transform Hupdate
             (seq 0 count) Hdistinct initial j), existsb_prefix.
  reflexivity.
Qed.
