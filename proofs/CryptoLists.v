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

(* Rotation is a cut followed by exchanging the two pieces. Complementary
   cuts restore any list; the cipher supplies only its concrete cut sizes. *)
Definition rotate_at {A : Type} (n : nat) (xs : list A) : list A :=
  app (ProofSupport.drop_of n xs) (ProofSupport.take_of n xs).

Lemma take_prefix_count : forall (A : Type) (front back : list A),
  ProofSupport.take_of (list_length front) (app front back) = front.
Proof.
  intros A front. induction front as [|x front IH]; intros back; simpl.
  - reflexivity.
  - rewrite IH. reflexivity.
Qed.

Lemma drop_prefix_count : forall (A : Type) (front back : list A),
  ProofSupport.drop_of (list_length front) (app front back) = back.
Proof.
  intros A front. induction front as [|x front IH]; intros back; simpl.
  - reflexivity.
  - exact (IH back).
Qed.

Lemma take_drop_reassemble : forall (A : Type) (n : nat) (xs : list A),
  app (ProofSupport.take_of n xs) (ProofSupport.drop_of n xs) = xs.
Proof.
  intros A n. induction n as [|n IH]; intros [|x xs]; simpl; try reflexivity.
  rewrite IH. reflexivity.
Qed.

Lemma count_drop_from_sum : forall (A : Type) (n m : nat) (xs : list A),
  list_length xs = n + m -> list_length (ProofSupport.drop_of n xs) = m.
Proof.
  intros A n. induction n as [|n IH]; intros m xs H.
  - exact H.
  - destruct xs as [|x xs]; [discriminate H |].
    simpl in H. injection H as H. simpl. exact (IH m xs H).
Qed.

Lemma complementary_cuts_inverse : forall (A : Type) (n m : nat) (xs : list A),
  list_length xs = n + m -> rotate_at m (rotate_at n xs) = xs.
Proof.
  intros A n m xs H.
  assert (Hm : m = list_length (ProofSupport.drop_of n xs)).
  { symmetry. exact (count_drop_from_sum A n m xs H). }
  unfold rotate_at. rewrite Hm.
  rewrite drop_prefix_count, take_prefix_count. apply take_drop_reassemble.
Qed.

Lemma map_over_memberwise : forall (A B : Type) (f g : A -> B) (xs : list A),
  (forall x : A, ProofSupport.Member x xs -> f x = g x) ->
  map_over f xs = map_over g xs.
Proof.
  intros A B f g xs. induction xs as [|x xs IH]; intros H; simpl.
  - reflexivity.
  - rewrite (H x (or_introl eq_refl)). rewrite IH; [reflexivity |].
    intros y Hy. apply H. right. exact Hy.
Qed.

Lemma map_over_constant : forall (A B : Type) (f : A -> B) (xs : list A) (b : B),
  (forall x : A, ProofSupport.Member x xs -> f x = b) ->
  map_over f xs = ProofSupport.repeat_of (list_length xs) b.
Proof.
  intros A B f xs. induction xs as [|x xs IH]; intros b H; simpl.
  - reflexivity.
  - rewrite (H x (or_introl eq_refl)). rewrite IH; [reflexivity |].
    intros y Hy. apply H. right. exact Hy.
Qed.

Lemma nth_map_up_from : forall (A : Type) (f : nat -> A) (start n i : nat) (d : A),
  Nat.ltb i n = true ->
  ProofSupport.nth_of i (map_over f (ProofSupport.up_from start n)) d = f (start + i).
Proof.
  intros A f start n. revert start.
  induction n as [|n IH]; intros start i d H.
  - destruct i; discriminate H.
  - destruct i as [|i].
    + simpl. rewrite ProofSupport.nat_add_zero. reflexivity.
    + simpl in H. change
        (ProofSupport.nth_of i (map_over f (ProofSupport.up_from (S start) n)) d
         = f (start + S i)).
      rewrite (IH (S start) i d H), ProofSupport.nat_add_succ. reflexivity.
Qed.

Lemma map_up_from_succ : forall (A : Type) (f : nat -> A) (start n : nat),
  map_over f (ProofSupport.up_from (S start) n) =
  map_over (fun i => f (S i)) (ProofSupport.up_from start n).
Proof.
  intros A f start n. revert start.
  induction n as [|n IH]; intros start; simpl.
  - reflexivity.
  - rewrite (IH (S start)). reflexivity.
Qed.

Lemma gather_identity : forall (A : Type) (xs : list A) (d : A),
  map_over (fun i => ProofSupport.nth_of i xs d)
    (ProofSupport.up_from 0 (list_length xs)) = xs.
Proof.
  intros A xs. induction xs as [|x xs IH]; intros d; simpl.
  - reflexivity.
  - f_equal. rewrite map_up_from_succ.
    change (map_over (fun i => ProofSupport.nth_of i xs d)
      (ProofSupport.up_from 0 (list_length xs)) = xs).
    exact (IH d).
Qed.

(* An inverse index map suffices to invert a gather. Bounds are needed only
   on indices the outer gather actually reads; defaults remain unchanged. *)
Lemma gather_inverse : forall (A : Type) (n : nat) (p q : nat -> nat)
    (xs : list A) (d : A),
  list_length xs = n ->
  (forall i, ProofSupport.Member i (ProofSupport.up_from 0 n) -> Nat.ltb (q i) n = true) ->
  (forall i, ProofSupport.Member i (ProofSupport.up_from 0 n) -> p (q i) = i) ->
  map_over (fun i => ProofSupport.nth_of (q i)
    (map_over (fun j => ProofSupport.nth_of (p j) xs d) (ProofSupport.up_from 0 n)) d)
    (ProofSupport.up_from 0 n) = xs.
Proof.
  intros A n p q xs d Hlength Hbound Hinverse.
  transitivity (map_over (fun i => ProofSupport.nth_of i xs d) (ProofSupport.up_from 0 n)).
  - apply map_over_memberwise. intros i Hi.
    rewrite (nth_map_up_from A (fun j => ProofSupport.nth_of (p j) xs d)
      0 n (q i) d (Hbound i Hi)).
    change (ProofSupport.nth_of (p (q i)) xs d = ProofSupport.nth_of i xs d).
    rewrite (Hinverse i Hi). reflexivity.
  - rewrite <- Hlength. apply gather_identity.
Qed.

Example unequal_lists_still_truncate :
  zip_with xorb (cons true (cons false nil)) (cons true nil) = cons false nil.
Proof. reflexivity. Qed.

Example a_short_key_does_not_restore_a_long_word :
  zip_with xorb
    (zip_with xorb (cons true (cons false nil)) (cons true nil)) (cons true nil)
  <> cons true (cons false nil).
Proof. discriminate. Qed.
