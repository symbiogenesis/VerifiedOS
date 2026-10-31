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

(* These comparisons expose their element laws separately: soundness needs
   sound elements, and reflexivity needs only reflexive elements. *)
Fixpoint list_eqb {A : Type} (eqb : A -> A -> bool) (l r : list A) : bool :=
  match l, r with
  | nil, nil => true
  | cons x xs, cons y ys => andb (eqb x y) (list_eqb eqb xs ys)
  | _, _ => false
  end.

Definition option_eqb {A : Type} (eqb : A -> A -> bool) (a b : option A) : bool :=
  match a, b with
  | None, None => true
  | Some x, Some y => eqb x y
  | _, _ => false
  end.

Definition pair_eqb {A B : Type} (eq_a : A -> A -> bool) (eq_b : B -> B -> bool)
    (a b : prod A B) : bool :=
  andb (eq_a (fst a) (fst b)) (eq_b (snd a) (snd b)).

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

Lemma nat_add_zero : forall a : nat, a + 0 = a.
Proof. induction a as [|a IH]; simpl; [reflexivity | rewrite IH; reflexivity]. Qed.

Lemma nat_add_succ : forall a b : nat, a + S b = S (a + b).
Proof. induction a as [|a IH]; intros b; simpl; [reflexivity | rewrite IH; reflexivity]. Qed.

Lemma nat_add_comm : forall a b : nat, a + b = b + a.
Proof.
  induction a as [|a IH]; intros b; simpl.
  - rewrite nat_add_zero. reflexivity.
  - rewrite IH, nat_add_succ. reflexivity.
Qed.

Lemma nat_leb_add_left : forall k a b : nat,
  Nat.leb a b = true -> Nat.leb (k + a) (k + b) = true.
Proof. induction k as [|k IH]; intros a b H; simpl; [exact H | apply IH; exact H]. Qed.

Lemma nat_leb_add_mono : forall a b c d : nat,
  Nat.leb a b = true -> Nat.leb c d = true -> Nat.leb (a + c) (b + d) = true.
Proof.
  intros a b c d Hab Hcd. apply (nat_leb_trans (a + c) (a + d) (b + d)).
  - apply nat_leb_add_left. exact Hcd.
  - rewrite (nat_add_comm a d), (nat_add_comm b d).
    apply nat_leb_add_left. exact Hab.
Qed.

Lemma nat_leb_add_r : forall a b : nat, Nat.leb a (a + b) = true.
Proof. induction a as [|a IH]; intros b; [reflexivity | simpl; apply IH]. Qed.

Lemma nat_max_left : forall a b : nat, Nat.leb a (Nat.max a b) = true.
Proof.
  induction a as [|a IH]; intros b; [reflexivity |].
  destruct b; simpl; [apply nat_leb_refl | apply IH].
Qed.

Lemma nat_max_right : forall a b : nat, Nat.leb b (Nat.max a b) = true.
Proof.
  induction a as [|a IH]; intros b; simpl; [apply nat_leb_refl |].
  destruct b; simpl; [reflexivity | apply IH].
Qed.

Lemma nat_max_upper : forall a b c : nat,
  Nat.leb a c = true -> Nat.leb b c = true -> Nat.leb (Nat.max a b) c = true.
Proof.
  induction a as [|a IH]; intros b c Ha Hb; simpl; [exact Hb |].
  destruct c; [discriminate Ha |]. destruct b; simpl; [exact Ha |].
  apply IH; assumption.
Qed.

Lemma nat_sub_padding : forall elapsed bound : nat,
  Nat.leb elapsed bound = true -> elapsed + (bound - elapsed) = bound.
Proof.
  induction elapsed as [|elapsed IH]; intros bound H.
  - destruct bound; reflexivity.
  - destruct bound as [|bound]; [discriminate H |]. simpl in *.
    rewrite (IH bound H). reflexivity.
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

(* A roster's completeness is distinct from its length and from its order. *)
Definition CompleteRoster {A : Type} (l : list A) : Prop :=
  forall x : A, Member x l.

Lemma all_of_complete_roster : forall (A : Type) (l : list A),
  CompleteRoster l -> forall p : A -> bool,
    all_of p l = true <-> forall x : A, p x = true.
Proof.
  intros A l complete p. split.
  - intros H x. exact (all_of_member A p l x H (complete x)).
  - intros H. apply all_of_intro. intros x _. exact (H x).
Qed.

Lemma any_eqb_member : forall (A : Type) (eqb : A -> A -> bool),
  (forall x y : A, eqb x y = true -> x = y) ->
  forall (x : A) (l : list A), any_of (eqb x) l = true -> Member x l.
Proof.
  intros A eqb sound x l. induction l as [|y r IH]; intros H.
  - discriminate H.
  - simpl in H. destruct (eqb x y) eqn:E.
    + left. exact (sound x y E).
    + right. exact (IH H).
Qed.

Lemma member_any_eqb : forall (A : Type) (eqb : A -> A -> bool),
  (forall x : A, eqb x x = true) ->
  forall (x : A) (l : list A), Member x l -> any_of (eqb x) l = true.
Proof.
  intros A eqb refl x l. induction l as [|y r IH]; intros H.
  - contradiction H.
  - simpl. destruct H as [E | H].
    + rewrite E, refl. reflexivity.
    + rewrite (IH H). destruct (eqb x y); reflexivity.
Qed.

Lemma all_of_eqb_member : forall (A : Type) (eqb : A -> A -> bool),
  (forall x y : A, eqb x y = true -> x = y) ->
  forall (p : A -> bool) (l : list A) (x : A),
    all_of p l = true -> any_of (eqb x) l = true -> p x = true.
Proof.
  intros A eqb sound p l x Hall Hmem.
  exact (all_of_member A p l x Hall (any_eqb_member A eqb sound x l Hmem)).
Qed.

Lemma all_of_complete_roster_eqb : forall (A : Type) (eqb : A -> A -> bool),
  (forall x y : A, eqb x y = true -> x = y) ->
  forall l : list A, (forall x : A, any_of (eqb x) l = true) ->
  forall p : A -> bool, all_of p l = true <-> forall x : A, p x = true.
Proof.
  intros A eqb sound l complete p. apply all_of_complete_roster.
  intros x. exact (any_eqb_member A eqb sound x l (complete x)).
Qed.

Lemma all_of_app_eq : forall (A : Type) (p : A -> bool) (l r : list A),
  all_of p (app l r) = andb (all_of p l) (all_of p r).
Proof.
  intros A p l. induction l as [|x s IH]; intros r.
  - reflexivity.
  - simpl. rewrite IH. destruct (p x); reflexivity.
Qed.

Lemma all_of_map : forall (A B : Type) (p : B -> bool) (f : A -> B) (l : list A),
  all_of p (map_over f l) = all_of (fun x => p (f x)) l.
Proof.
  intros A B p f l. induction l as [|x r IH];
    [reflexivity | simpl; rewrite IH; reflexivity].
Qed.

Lemma count_of_app : forall (A : Type) (l r : list A),
  count_of (app l r) = Nat.add (count_of l) (count_of r).
Proof.
  intros A l r. induction l as [|x s IH];
    [reflexivity | simpl; rewrite IH; reflexivity].
Qed.

Lemma count_of_map : forall (A B : Type) (f : A -> B) (l : list A),
  count_of (map_over f l) = count_of l.
Proof.
  intros A B f l. induction l as [|x r IH];
    [reflexivity | simpl; rewrite IH; reflexivity].
Qed.

Lemma map_over_app : forall (A B : Type) (f : A -> B) (l r : list A),
  map_over f (app l r) = app (map_over f l) (map_over f r).
Proof.
  intros A B f l. induction l as [|x s IH]; intros r;
    [reflexivity | simpl; rewrite IH; reflexivity].
Qed.

Lemma filter_of_app : forall (A : Type) (p : A -> bool) (l r : list A),
  filter_of p (app l r) = app (filter_of p l) (filter_of p r).
Proof.
  intros A p l. induction l as [|x s IH]; intros r.
  - reflexivity.
  - simpl. destruct (p x); rewrite IH; reflexivity.
Qed.

Lemma list_eqb_refl : forall (A : Type) (eqb : A -> A -> bool),
  (forall x : A, eqb x x = true) -> forall l : list A, list_eqb eqb l l = true.
Proof.
  intros A eqb refl l. induction l as [|x r IH]; [reflexivity |].
  simpl. rewrite (refl x), IH. reflexivity.
Qed.

Lemma list_eqb_sound : forall (A : Type) (eqb : A -> A -> bool),
  (forall x y : A, eqb x y = true -> x = y) ->
  forall l r : list A, list_eqb eqb l r = true -> l = r.
Proof.
  intros A eqb sound l. induction l as [|x xs IH]; intros r H.
  - destruct r; [reflexivity | discriminate H].
  - destruct r as [|y ys]; [discriminate H |].
    simpl in H. destruct (andb_split _ _ H) as [Hxy Hrest].
    rewrite (sound x y Hxy), (IH ys Hrest). reflexivity.
Qed.

Lemma list_eqb_spec : forall (A : Type) (eqb : A -> A -> bool),
  (forall x y : A, eqb x y = true -> x = y) ->
  (forall x : A, eqb x x = true) ->
  forall l r : list A, list_eqb eqb l r = true <-> l = r.
Proof.
  intros A eqb sound refl l r. split.
  - exact (list_eqb_sound A eqb sound l r).
  - intros E. rewrite E. exact (list_eqb_refl A eqb refl r).
Qed.

Lemma option_eqb_refl : forall (A : Type) (eqb : A -> A -> bool),
  (forall x : A, eqb x x = true) -> forall a : option A, option_eqb eqb a a = true.
Proof. intros A eqb refl [x|]; [exact (refl x) | reflexivity]. Qed.

Lemma option_eqb_sound : forall (A : Type) (eqb : A -> A -> bool),
  (forall x y : A, eqb x y = true -> x = y) ->
  forall a b : option A, option_eqb eqb a b = true -> a = b.
Proof.
  intros A eqb sound [x|] [y|] H; try discriminate H; [|reflexivity].
  simpl in H. rewrite (sound x y H). reflexivity.
Qed.

Lemma option_eqb_spec : forall (A : Type) (eqb : A -> A -> bool),
  (forall x y : A, eqb x y = true -> x = y) ->
  (forall x : A, eqb x x = true) ->
  forall a b : option A, option_eqb eqb a b = true <-> a = b.
Proof.
  intros A eqb sound refl a b. split.
  - exact (option_eqb_sound A eqb sound a b).
  - intros E. rewrite E. exact (option_eqb_refl A eqb refl b).
Qed.

Lemma pair_eqb_refl : forall (A B : Type)
    (eq_a : A -> A -> bool) (eq_b : B -> B -> bool),
  (forall x : A, eq_a x x = true) -> (forall y : B, eq_b y y = true) ->
  forall p : prod A B, pair_eqb eq_a eq_b p p = true.
Proof.
  intros A B eq_a eq_b refl_a refl_b [x y]. unfold pair_eqb. simpl.
  rewrite (refl_a x), (refl_b y). reflexivity.
Qed.

Lemma pair_eqb_sound : forall (A B : Type)
    (eq_a : A -> A -> bool) (eq_b : B -> B -> bool),
  (forall x y : A, eq_a x y = true -> x = y) ->
  (forall x y : B, eq_b x y = true -> x = y) ->
  forall p q : prod A B, pair_eqb eq_a eq_b p q = true -> p = q.
Proof.
  intros A B eq_a eq_b sound_a sound_b [x y] [u v] H.
  unfold pair_eqb in H. simpl in H.
  destruct (andb_split _ _ H) as [Ha Hb].
  rewrite (sound_a x u Ha), (sound_b y v Hb). reflexivity.
Qed.

Lemma pair_eqb_spec : forall (A B : Type)
    (eq_a : A -> A -> bool) (eq_b : B -> B -> bool),
  (forall x y : A, eq_a x y = true -> x = y) ->
  (forall x y : B, eq_b x y = true -> x = y) ->
  (forall x : A, eq_a x x = true) -> (forall y : B, eq_b y y = true) ->
  forall p q : prod A B, pair_eqb eq_a eq_b p q = true <-> p = q.
Proof.
  intros A B eq_a eq_b sound_a sound_b refl_a refl_b p q. split.
  - exact (pair_eqb_sound A B eq_a eq_b sound_a sound_b p q).
  - intros E. rewrite E. exact (pair_eqb_refl A B eq_a eq_b refl_a refl_b q).
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

Example equality_comparisons_refuse_different_shapes_and_fields :
  list_eqb Nat.eqb (cons 1 nil) nil = false /\
  option_eqb Nat.eqb (Some 1) None = false /\
  pair_eqb Nat.eqb Nat.eqb (pair 1 2) (pair 1 3) = false.
Proof. repeat split. Qed.

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

