(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ProofSupport.v

   Shared constructive collections and sequence laws. This module imports only
   the Rocq prelude. Clients retain their public names as convertible aliases;
   distinct enumeration and out-of-range policies remain explicit.

   R-05-163's assumption audit covers the shared laws. Concrete boundary
   examples preserve the inhabitation and refusal evidence of R-05-165 and
   R-05-166 without adding a domain-specific assumption.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-165 R-05-166
   SHA256: 4c631348347cb256d8d909843632bc4849e204c51521af8b014dbaabd4d358c9
   (*| END derived |*)
   ========================================================================= *)

Open Scope list_scope.


Fixpoint all_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => true
  | cons x r => andb (p x) (all_of p r)
  end.

Fixpoint any_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => false
  | cons x r => orb (p x) (any_of p r)
  end.

Fixpoint count_of {A : Type} (l : list A) : nat :=
  match l with nil => 0 | cons _ r => S (count_of r) end.

Fixpoint map_over {A B : Type} (f : A -> B) (l : list A) : list B :=
  match l with nil => nil | cons x r => cons (f x) (map_over f r) end.

Fixpoint filter_of {A : Type} (p : A -> bool) (l : list A) : list A :=
  match l with
  | nil => nil
  | cons x r => if p x then cons x (filter_of p r) else filter_of p r
  end.

Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

Fixpoint swap_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons a (cons b r) => cons b (cons a r)
  | 0, _ => l
  | S k, cons a r => cons a (swap_at k r)
  | S _, nil => nil
  end.

Fixpoint drop_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons _ r => r
  | 0, nil => nil
  | S k, cons a r => cons a (drop_at k r)
  | S _, nil => nil
  end.

Fixpoint insert_at {A : Type} (n : nat) (x : A) (l : list A) : list A :=
  match n, l with
  | 0, _ => cons x l
  | S k, cons a r => cons a (insert_at k x r)
  | S _, nil => cons x nil
  end.

Fixpoint dup_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons x r => cons x (cons x r)
  | 0, nil => nil
  | S k, cons x r => cons x (dup_at k r)
  | S _, nil => nil
  end.

Fixpoint patch_at {A : Type} (f : A -> A) (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons x r => cons (f x) r
  | 0, nil => nil
  | S k, cons x r => cons x (patch_at f k r)
  | S _, nil => nil
  end.

Definition before_last (n : nat) : nat :=
  match n with 0 => 0 | S k => k end.

Definition only_if (a b : bool) : bool := orb (negb a) b.

Definition bool_eqb (a b : bool) : bool :=
  match a, b with
  | true, true => true
  | false, false => true
  | _, _ => false
  end.

Definition is_some {A : Type} (o : option A) : bool :=
  match o with None => false | Some _ => true end.

Definition map_option {A B : Type} (f : A -> B) (o : option A) : option B :=
  match o with None => None | Some x => Some (f x) end.

Definition mem_nat (i : nat) (l : list nat) : bool :=
  any_of (fun j => Nat.eqb i j) l.

Fixpoint take_of {A : Type} (n : nat) (l : list A) : list A :=
  match n with
  | 0 => nil
  | S k => match l with nil => nil | x :: r => x :: take_of k r end
  end.

Fixpoint drop_of {A : Type} (n : nat) (l : list A) : list A :=
  match n with
  | 0 => l
  | S k => match l with nil => nil | _ :: r => drop_of k r end
  end.

Fixpoint nth_of {A : Type} (n : nat) (l : list A) (d : A) : A :=
  match l with
  | nil => d
  | x :: r => match n with 0 => x | S k => nth_of k r d end
  end.

Fixpoint rev_onto {A : Type} (l acc : list A) : list A :=
  match l with nil => acc | x :: r => rev_onto r (x :: acc) end.

Fixpoint repeat_of {A : Type} (n : nat) (x : A) : list A :=
  match n with 0 => nil | S k => x :: repeat_of k x end.

Fixpoint up_from (start count : nat) : list nat :=
  match count with 0 => nil | S k => start :: up_from (S start) k end.

Fixpoint fold_over {A B : Type} (f : B -> A -> B) (acc : B) (l : list A) : B :=
  match l with nil => acc | x :: r => fold_over f (f acc x) r end.

Fixpoint concat_of {A : Type} (l : list (list A)) : list A :=
  match l with nil => nil | x :: r => x ++ concat_of r end.

Fixpoint count_where {A : Type} (p : A -> bool) (l : list A) : nat :=
  match l with
  | nil => 0
  | x :: r => if p x then S (count_where p r) else count_where p r
  end.

Definition length_of {A : Type} (l : list A) : nat := count_of l.

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

Lemma andb_join : forall a b : bool, a = true -> b = true -> andb a b = true.
Proof. intros a b Ha Hb. rewrite Ha. rewrite Hb. reflexivity. Qed.

Lemma only_if_elim :
  forall a b : bool, only_if a b = true -> a = true -> b = true.
Proof.
  intros a b H Ha. rewrite Ha in H. exact H.
Qed.

Lemma nat_eqb_refl : forall n : nat, Nat.eqb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma nat_eqb_true : forall a b : nat, Nat.eqb a b = true -> a = b.
Proof.
  intros a. induction a as [ | x IH ]; intros b H.
  - destruct b as [ | y ]; [ reflexivity | discriminate H ].
  - destruct b as [ | y ]; [ discriminate H | ].
    simpl in H. rewrite (IH y H). reflexivity.
Qed.

Lemma nat_leb_refl : forall n : nat, Nat.leb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma nat_leb_succ : forall n : nat, Nat.leb n (S n) = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma nat_leb_trans :
  forall a b c : nat, Nat.leb a b = true -> Nat.leb b c = true -> Nat.leb a c = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b c Hab Hbc.
  - reflexivity.
  - destruct b as [ | y ]; [ discriminate Hab | ].
    destruct c as [ | z ]; [ discriminate Hbc | ].
    simpl in Hab. simpl in Hbc. simpl. exact (IH y z Hab Hbc).
Qed.

Lemma all_of_app :
  forall (A : Type) (p : A -> bool) (l r : list A),
    all_of p (app l r) = true -> all_of p l = true /\ all_of p r = true.
Proof.
  intros A p l r. induction l as [ | x s IH ]; intros H.
  - split; [ reflexivity | exact H ].
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hs ].
    destruct (IH Hs) as [ Hl Hr ]. split; [ | exact Hr ].
    simpl. apply andb_join; [ exact Hx | exact Hl ].
Qed.

Lemma all_of_app_join :
  forall (A : Type) (p : A -> bool) (l r : list A),
    all_of p l = true -> all_of p r = true -> all_of p (app l r) = true.
Proof.
  intros A p l r. induction l as [ | x s IH ]; intros Hl Hr.
  - exact Hr.
  - simpl in Hl. destruct (andb_split _ _ Hl) as [ Hx Hs ].
    simpl. apply andb_join; [ exact Hx | exact (IH Hs Hr) ].
Qed.

Lemma all_of_mono :
  forall (A : Type) (p q : A -> bool) (l : list A),
    (forall x : A, p x = true -> q x = true) ->
    all_of p l = true -> all_of q l = true.
Proof.
  intros A p q l Himp. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    simpl. apply andb_join; [ exact (Himp x Hx) | exact (IH Hr) ].
Qed.

Lemma all_of_filter :
  forall (A : Type) (p : A -> bool) (l : list A), all_of p (filter_of p l) = true.
Proof.
  intros A p l. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. destruct (p x) eqn:E.
    + simpl. rewrite E. exact IH.
    + exact IH.
Qed.

Lemma filter_of_within :
  forall (A : Type) (p q : A -> bool) (l : list A),
    all_of q l = true -> all_of q (filter_of p l) = true.
Proof.
  intros A p q l. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    simpl. destruct (p x).
    + simpl. apply andb_join; [ exact Hx | exact (IH Hr) ].
    + exact (IH Hr).
Qed.

Lemma mem_nat_cons :
  forall (i j : nat) (l : list nat), mem_nat i l = true -> mem_nat i (cons j l) = true.
Proof.
  intros i j l H. unfold mem_nat. simpl. unfold mem_nat in H. rewrite H.
  destruct (Nat.eqb i j); reflexivity.
Qed.

Lemma mem_nat_here : forall (i : nat) (l : list nat), mem_nat i (cons i l) = true.
Proof. intros i l. unfold mem_nat. simpl. rewrite (nat_eqb_refl i). reflexivity. Qed.

Fixpoint Member {A : Type} (x : A) (l : list A) : Prop :=
  match l with nil => False | cons y r => x = y \/ Member x r end.

Lemma all_of_member : forall (A : Type) (p : A -> bool) (l : list A) (x : A),
  all_of p l = true -> Member x l -> p x = true.
Proof.
  intros A p l. induction l as [|y r IH]; intros x Hall Hin.
  - contradiction Hin.
  - simpl in Hall. destruct (andb_split _ _ Hall) as [Hy Hr].
    destruct Hin as [Heq | Hin].
    + rewrite Heq. exact Hy.
    + exact (IH x Hr Hin).
Qed.

Lemma all_of_intro : forall (A : Type) (p : A -> bool) (l : list A),
  (forall x : A, Member x l -> p x = true) -> all_of p l = true.
Proof.
  intros A p l. induction l as [|y r IH]; intro H.
  - reflexivity.
  - simpl. apply andb_join.
    + apply H. left. reflexivity.
    + apply IH. intros x Hin. apply H. right. exact Hin.
Qed.

Lemma all_of_spec : forall (A : Type) (p : A -> bool) (l : list A),
  all_of p l = true <-> forall x : A, Member x l -> p x = true.
Proof.
  intros A p l. split.
  - intros H x Hin. exact (all_of_member A p l x H Hin).
  - exact (all_of_intro A p l).
Qed.

Local Ltac step_by_IH IH s := simpl; rewrite (IH s); reflexivity.
Local Ltac induct_on_the_position n l :=
  revert l; induction n as [|k IH]; intros l;
  [destruct l as [|a s]; [reflexivity|] | ..].


Lemma all_of_insert :
  forall (A : Type) (q : A -> bool) (x : A) (l : list A) (n : nat),
    all_of q (insert_at n x l) = andb (q x) (all_of q l).
Proof.
  intros A q x l n. revert l. induction n as [ | k IH ]; intros l.
  - reflexivity.
  - destruct l as [ | y s ].
    + simpl. destruct (q x); reflexivity.
    + simpl. rewrite (IH s). destruct (q y); destruct (q x); reflexivity.
Qed.

Lemma all_of_drop :
  forall (A : Type) (q : A -> bool) (l : list A) (n : nat),
    all_of q l = true -> all_of q (drop_at n l) = true.
Proof.
  intros A q l n. revert l. induction n as [ | k IH ]; intros l H.
  - destruct l as [ | y s ]; [ reflexivity | ].
    simpl in H. destruct (andb_split _ _ H) as [ _ Hs ]. exact Hs.
  - destruct l as [ | y s ]; [ reflexivity | ].
    simpl in H. destruct (andb_split _ _ H) as [ Hy Hs ].
    simpl. apply andb_join; [ exact Hy | exact (IH s Hs) ].
Qed.

Lemma all_of_swap :
  forall (A : Type) (p : A -> bool) (l : list A) (n : nat),
    all_of p (swap_at n l) = all_of p l.
Proof.
  intros A p l n. induct_on_the_position n l.
  - destruct s as [ | b t ]; [ reflexivity | ].
    simpl. destruct (p a); destruct (p b); reflexivity.
  - destruct l as [ | a s ]; [ reflexivity | ].
    step_by_IH IH s.
Qed.

Lemma all_of_dup :
  forall (A : Type) (p : A -> bool) (l : list A) (n : nat),
    all_of p (dup_at n l) = all_of p l.
Proof.
  intros A p l n. induct_on_the_position n l.
  - simpl. destruct (p a); reflexivity.
  - destruct l as [ | a s ]; [ reflexivity | ].
    step_by_IH IH s.
Qed.

Lemma count_of_insert :
  forall (A : Type) (x : A) (l : list A) (n : nat),
    count_of (insert_at n x l) = S (count_of l).
Proof.
  intros A x l n. revert l. induction n as [ | k IH ]; intros l.
  - reflexivity.
  - destruct l as [ | y s ]; [ reflexivity | ]. step_by_IH IH s.
Qed.

Lemma count_of_swap :
  forall (A : Type) (l : list A) (n : nat), count_of (swap_at n l) = count_of l.
Proof.
  intros A l n. induct_on_the_position n l.
  - destruct s as [ | b t ]; reflexivity.
  - destruct l as [ | a s ]; [ reflexivity | ]. step_by_IH IH s.
Qed.

Lemma count_of_drop :
  forall (A : Type) (l : list A) (n : nat),
    Nat.leb (count_of (drop_at n l)) (count_of l) = true.
Proof.
  intros A l n. induct_on_the_position n l.
  - simpl. exact (nat_leb_succ (count_of s)).
  - destruct l as [ | a s ]; [ reflexivity | ]. simpl. exact (IH s).
Qed.

Example edits_past_the_end :
  swap_at 5 (cons 1 (cons 2 nil)) = cons 1 (cons 2 nil) /\
  drop_at 5 (cons 1 (cons 2 nil)) = cons 1 (cons 2 nil) /\
  insert_at 5 9 (cons 1 (cons 2 nil)) = cons 1 (cons 2 (cons 9 nil)) /\
  dup_at 5 (cons 1 (cons 2 nil)) = cons 1 (cons 2 nil).
Proof. repeat split. Qed.

Example edits_at_the_front :
  swap_at 0 (cons 1 (cons 2 nil)) = cons 2 (cons 1 nil) /\
  drop_at 0 (cons 1 (cons 2 nil)) = cons 2 nil /\
  insert_at 0 9 (cons 1 nil) = cons 9 (cons 1 nil) /\
  dup_at 0 (cons 1 nil) = cons 1 (cons 1 nil).
Proof. repeat split. Qed.

