(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   CryptoLists.v

   Equal-length lifting for the executable crypto references. The functions
   remain total on unequal lists: zip_with stops at the shorter input.
   R-05-163 audits the shared laws; the concrete unequal-length examples
   retain the boundary evidence required by R-05-165 and R-05-166.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-165 R-05-166
   SHA256: 4c631348347cb256d8d909843632bc4849e204c51521af8b014dbaabd4d358c9
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport.

Definition list_length {A : Type} : list A -> nat := @ProofSupport.count_of A.

Definition map_over {A B : Type} : (A -> B) -> list A -> list B := @ProofSupport.map_over A B.

Fixpoint zip_with {A B C : Type} (f : A -> B -> C)
    (xs : list A) (ys : list B) : list C :=
  match xs with
  | nil => nil
  | cons x rest =>
      match ys with
      | nil => nil
      | cons y tail => cons (f x y) (zip_with f rest tail)
      end
  end.

(* A list operation inherits a scalar law when its cons equation has that
   law at the head. Clients supply the scalar equation, not another list
   induction. The length premise is essential for operations that truncate. *)
Lemma lift_map_left : forall (A B C : Type)
    (F : list A -> list B -> list C) (f : A -> C),
  F nil nil = nil ->
  (forall x xs y ys, F (cons x xs) (cons y ys) = cons (f x) (F xs ys)) ->
  forall xs ys, list_length xs = list_length ys -> F xs ys = map_over f xs.
Proof.
  intros A B C F f Hnil Hcons xs. induction xs as [|x xs IH];
    intros [|y ys] H; try discriminate H.
  - exact Hnil.
  - simpl in H. injection H as H. rewrite Hcons, (IH ys H). reflexivity.
Qed.

Lemma lift_map_right : forall (A B C : Type)
    (F : list A -> list B -> list C) (f : B -> C),
  F nil nil = nil ->
  (forall x xs y ys, F (cons x xs) (cons y ys) = cons (f y) (F xs ys)) ->
  forall xs ys, list_length xs = list_length ys -> F xs ys = map_over f ys.
Proof.
  intros A B C F f Hnil Hcons xs ys H.
  apply (lift_map_left B A C (fun ys xs => F xs ys) f Hnil).
  - intros y tail x rest. apply Hcons.
  - symmetry. exact H.
Qed.

Lemma map_over_id : forall (A : Type) (xs : list A), map_over (fun x => x) xs = xs.
Proof.
  intros A xs. induction xs as [|x xs IH]; [reflexivity|]. simpl. rewrite IH. reflexivity.
Qed.

Lemma zip_involution : forall (A B : Type) (f : A -> B -> A),
  (forall x y, f (f x y) y = x) ->
  forall xs ys, list_length xs = list_length ys -> zip_with f (zip_with f xs ys) ys = xs.
Proof.
  intros A B f Hscalar xs ys H.
  transitivity (map_over (fun x => x) xs).
  - apply (lift_map_left A B A (fun xs ys => zip_with f (zip_with f xs ys) ys)
             (fun x => x)).
    + reflexivity.
    + intros x rest y tail. simpl. rewrite Hscalar. reflexivity.
    + exact H.
  - apply map_over_id.
Qed.

Lemma xorb_cancels : forall x y : bool, xorb (xorb x y) y = x.
Proof. destruct x, y; reflexivity. Qed.

Lemma xor_involution : forall xs ys : list bool,
  list_length xs = list_length ys ->
  zip_with xorb (zip_with xorb xs ys) ys = xs.
Proof. exact (zip_involution bool bool xorb xorb_cancels). Qed.

Example unequal_lists_still_truncate :
  zip_with xorb (cons true (cons false nil)) (cons true nil) = cons false nil.
Proof. reflexivity. Qed.

Example a_short_key_does_not_restore_a_long_word :
  zip_with xorb
    (zip_with xorb (cons true (cons false nil)) (cons true nil)) (cons true nil)
  <> cons true (cons false nil).
Proof. discriminate. Qed.
