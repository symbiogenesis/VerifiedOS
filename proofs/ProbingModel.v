(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ProbingModel.v

   Gate-level functional probing model with stable, glitch, transition-pair,
   and difference-only observations (R-05-004a, R-15-053a, R-15-108,
   R-17-058a, R-17-058d; see
   [probing-model-contract.md](../docs/assurance/probing-model-contract.md)):
   - Robust expansion following transitive combinational dependencies and
     both sides of a register boundary, with physical probe locations counted
     before expansion and `ProbeStrategy` modeling adaptive value-dependent
     choices.
   - Finite weighted-mass probability interface (`Probability`) and normalized
     qualification (`FiniteMassQualification`) instantiated by uniform
     counting over Cartesian mask enumerations.
   - General additive `(n+1)`-share encoding security for up to `n` probes over
     an arbitrary enumerated finite abelian group (`Sharing`), plus local
     simulation predicates (`NI`, `SNI`, `PINI`) and separating witnesses
     (R-05-163, R-05-164, R-05-165, R-05-166).
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-004a R-05-163 R-05-164 R-05-165 R-05-166 R-15-053a R-15-108 R-17-058a
      R-17-058d
   SHA256: d5cee754487cff1dce8f7dbea7859259d762d96570ab1134f826bbc65f91a0ad
   (*| END derived |*)
   ========================================================================= *)

(* -------------------------------------------------------------------------
   Local list, boolean and arithmetic helpers. The general enumeration
   proofs below also use the standard List, Arith and Lia modules.
   ------------------------------------------------------------------------- *)

Require ProofSupport.

Definition all_of {A : Type} (p : A -> bool) (l : list A) : bool := @ProofSupport.all_of A p l.

Definition any_of {A : Type} (p : A -> bool) (l : list A) : bool := @ProofSupport.any_of A p l.

Definition count_of {A : Type} (l : list A) : nat := @ProofSupport.count_of A l.

Definition map_over {A B : Type} (f : A -> B) (l : list A) : list B := @ProofSupport.map_over A B f l.

Definition filter_of {A : Type} (p : A -> bool) (l : list A) : list A := @ProofSupport.filter_of A p l.

Fixpoint flat_map_over {A B : Type} (f : A -> list B) (l : list A) : list B :=
  match l with nil => nil | cons x r => app (f x) (flat_map_over f r) end.

(* 0 through n-1, in that order. *)
Definition upto (n : nat) : list nat := @ProofSupport.upto n.

(* Out-of-range lookup returns dflt. The wires_exist condition separately
   rejects references to wires outside the circuit. *)
Fixpoint at_member {A : Type} (l : list A) (n : nat) (dflt : A) : A :=
  match l with
  | nil => dflt
  | cons x r => match n with 0 => x | S k => at_member r k dflt end
  end.

Fixpoint mem_nat (x : nat) (l : list nat) : bool :=
  match l with
  | nil => false
  | cons y r => orb (Nat.eqb x y) (mem_nat x r)
  end.

Definition bool_eqb (a b : bool) : bool := ProofSupport.bool_eqb a b.

Definition list_eqb {A : Type} (eqb : A -> A -> bool) (l1 l2 : list A) : bool :=
  @ProofSupport.list_eqb A eqb l1 l2.

Definition prev_cycle (t : nat) : nat := match t with 0 => 0 | S k => k end.

(* -------------------------------------------------------------------------
   Arithmetic lemmas for finite mass and sharing proofs.
   ------------------------------------------------------------------------- *)

Lemma eqb_refl_nat : forall n : nat, Nat.eqb n n = true.
Proof. exact ProofSupport.nat_eqb_refl. Qed.

Lemma eqb_sound_nat : forall a b : nat, Nat.eqb a b = true -> a = b.
Proof. exact ProofSupport.nat_eqb_true. Qed.

Lemma add_zero_r_nat : forall n : nat, Nat.add n 0 = n.
Proof. exact ProofSupport.nat_add_zero. Qed.

Lemma add_zero_l_nat : forall n : nat, Nat.add 0 n = n.
Proof. intros n. reflexivity. Qed.

Lemma add_succ_r_nat : forall n k : nat, Nat.add n (S k) = S (Nat.add n k).
Proof. exact ProofSupport.nat_add_succ. Qed.

Lemma add_comm_nat : forall a b : nat, Nat.add a b = Nat.add b a.
Proof. exact ProofSupport.nat_add_comm. Qed.

Lemma add_assoc_nat :
  forall a b c : nat, Nat.add a (Nat.add b c) = Nat.add (Nat.add a b) c.
Proof.
  induction a as [ | a IH ]; intros b c; simpl;
    [ reflexivity | rewrite IH; reflexivity ].
Qed.

Lemma leb_refl_nat : forall n : nat, Nat.leb n n = true.
Proof. exact ProofSupport.nat_leb_refl. Qed.

Lemma leb_trans_nat :
  forall a b c : nat, Nat.leb a b = true -> Nat.leb b c = true ->
    Nat.leb a c = true.
Proof. exact ProofSupport.nat_leb_trans. Qed.

Lemma leb_succ_r_nat :
  forall a b : nat, Nat.leb a b = true -> Nat.leb a (S b) = true.
Proof. exact ProofSupport.nat_leb_succ_r. Qed.

Lemma leb_add_r_nat : forall a b : nat, Nat.leb a (Nat.add a b) = true.
Proof. exact ProofSupport.nat_leb_add_r. Qed.

Lemma leb_drop_left : forall a b, Nat.leb (S a) b = true -> Nat.leb a b = true.
Proof. exact ProofSupport.nat_leb_pred. Qed.

Lemma leb_add_mono_r_nat :
  forall a b c : nat, Nat.leb a b = true ->
    Nat.leb (Nat.add a c) (Nat.add b c) = true.
Proof.
  intros a b c H. induction c as [ | c IH ].
  - rewrite add_zero_r_nat. rewrite add_zero_r_nat. exact H.
  - rewrite add_succ_r_nat. rewrite add_succ_r_nat. simpl. exact IH.
Qed.

Lemma all_of_mono :
  forall {A : Type} (p q : A -> bool) (l : list A),
    (forall x : A, p x = true -> q x = true) ->
    all_of p l = true -> all_of q l = true.
Proof. exact ProofSupport.all_of_mono. Qed.

Lemma map_over_compose :
  forall {A B C : Type} (f : B -> C) (g : A -> B) (l : list A),
    map_over f (map_over g l) = map_over (fun a => f (g a)) l.
Proof.
  intros A B C f g l. induction l as [ | x r IH ]; simpl;
    [ reflexivity | rewrite IH; reflexivity ].
Qed.

Lemma map_over_ext :
  forall {A B : Type} (f g : A -> B) (l : list A),
    (forall a : A, f a = g a) -> map_over f l = map_over g l.
Proof.
  intros A B f g l H. induction l as [ | x r IH ]; simpl;
    [ reflexivity | rewrite (H x); rewrite IH; reflexivity ].
Qed.

Lemma map_over_ext_nat :
  forall {B : Type} (f g : nat -> B) (l : list nat),
    (forall a : nat, mem_nat a l = true -> f a = g a) ->
    map_over f l = map_over g l.
Proof.
  intros B f g l. induction l as [ | x r IH ]; simpl; intros H.
  - reflexivity.
  - rewrite (H x).
    + rewrite IH; [ reflexivity | ].
      intros b Hb. apply H. simpl. rewrite Hb.
      destruct (Nat.eqb b x); reflexivity.
    + simpl. rewrite eqb_refl_nat. reflexivity.
Qed.

Lemma filter_of_ext :
  forall {A : Type} (p q : A -> bool) (l : list A),
    (forall a : A, p a = q a) -> filter_of p l = filter_of q l.
Proof.
  intros A p q l H. induction l as [ | x r IH ]; simpl.
  - reflexivity.
  - rewrite (H x). rewrite IH. reflexivity.
Qed.

Lemma map_filter_comm :
  forall {A B : Type} (sigma : A -> B) (q : B -> bool) (l : list A),
    map_over sigma (filter_of (fun a => q (sigma a)) l)
    = filter_of q (map_over sigma l).
Proof.
  intros A B sigma q l. induction l as [ | x r IH ]; simpl.
  - reflexivity.
  - destruct (q (sigma x)); simpl; rewrite IH; reflexivity.
Qed.

Lemma mem_nat_app :
  forall (s : nat) (l1 l2 : list nat),
    mem_nat s (app l1 l2) = orb (mem_nat s l1) (mem_nat s l2).
Proof.
  intros s l1 l2. induction l1 as [ | x r IH ]; simpl.
  - reflexivity.
  - rewrite IH. destruct (Nat.eqb s x); reflexivity.
Qed.

Lemma mem_flat_map_over :
  forall (f : nat -> list nat) (l : list nat) (a s : nat),
    mem_nat a l = true -> mem_nat s (f a) = true ->
    mem_nat s (flat_map_over f l) = true.
Proof.
  intros f l. induction l as [ | x r IH ]; intros a s Ha Hs; simpl.
  - discriminate Ha.
  - rewrite mem_nat_app. simpl in Ha.
    destruct (Nat.eqb a x) eqn:Eax.
    + rewrite <- (eqb_sound_nat a x Eax). rewrite Hs. reflexivity.
    + simpl in Ha. rewrite (IH a s Ha Hs).
      destruct (mem_nat s (f x)); reflexivity.
Qed.

Lemma all_of_mem_nat :
  forall (p : nat -> bool) (l : list nat) (a : nat),
    all_of p l = true -> mem_nat a l = true -> p a = true.
Proof.
  intros p l. induction l as [ | x r IH ]; intros a Hall Ha.
  - discriminate Ha.
  - simpl in Hall. simpl in Ha.
    destruct (p x) eqn:Ex; [ | discriminate Hall ].
    simpl in Hall.
    destruct (Nat.eqb a x) eqn:Eax.
    + rewrite (eqb_sound_nat a x Eax). exact Ex.
    + simpl in Ha. exact (IH a Hall Ha).
Qed.

Lemma app_nil_r_eq : forall {A : Type} (l : list A), app l nil = l.
Proof.
  intros A l. induction l as [ | x r IH ]; simpl;
    [ reflexivity | rewrite IH; reflexivity ].
Qed.

(* =========================================================================
   Permutations, defined locally for the same reason the list helpers are.
   The one lemma the whole probabilistic half runs on is that a sum of
   masses does not depend on the order of the sample space, which is what
   makes a re-randomization argument available at all.
   ========================================================================= *)

Inductive Perm {A : Type} : list A -> list A -> Prop :=
  | perm_nil : Perm nil nil
  | perm_skip : forall (x : A) (l l' : list A),
      Perm l l' -> Perm (cons x l) (cons x l')
  | perm_swap : forall (x y : A) (l : list A),
      Perm (cons y (cons x l)) (cons x (cons y l))
  | perm_trans : forall l l' l'' : list A,
      Perm l l' -> Perm l' l'' -> Perm l l''.

Lemma perm_refl : forall {A : Type} (l : list A), Perm l l.
Proof.
  intros A l. induction l as [ | x r IH ];
    [ apply perm_nil | apply perm_skip; exact IH ].
Qed.

Lemma perm_map :
  forall {A B : Type} (f : A -> B) (l1 l2 : list A),
    Perm l1 l2 -> Perm (map_over f l1) (map_over f l2).
Proof.
  intros A B f l1 l2 H.
  induction H as [ | x l l' H IH | x y l | l l' l'' H1 IH1 H2 IH2 ].
  - simpl. apply perm_nil.
  - simpl. apply perm_skip. exact IH.
  - simpl. apply perm_swap.
  - exact (perm_trans _ _ _ IH1 IH2).
Qed.

Lemma perm_filter :
  forall {A : Type} (p : A -> bool) (l1 l2 : list A),
    Perm l1 l2 -> Perm (filter_of p l1) (filter_of p l2).
Proof.
  intros A p l1 l2 H.
  induction H as [ | x l l' H IH | x y l | l l' l'' H1 IH1 H2 IH2 ].
  - simpl. apply perm_nil.
  - simpl. destruct (p x); [ apply perm_skip; exact IH | exact IH ].
  - simpl. destruct (p y); destruct (p x);
      [ apply perm_swap | apply perm_refl | apply perm_refl | apply perm_refl ].
  - exact (perm_trans _ _ _ IH1 IH2).
Qed.

Lemma count_of_perm :
  forall {A : Type} (l1 l2 : list A), Perm l1 l2 -> count_of l1 = count_of l2.
Proof.
  intros A l1 l2 H.
  induction H as [ | x l l' H IH | x y l | l l' l'' H1 IH1 H2 IH2 ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
  - simpl. reflexivity.
  - rewrite IH1. exact IH2.
Qed.

Lemma perm_cons_app :
  forall {A : Type} (x : A) (l1 l2 : list A),
    Perm (app l1 (cons x l2)) (cons x (app l1 l2)).
Proof.
  intros A x l1. induction l1 as [ | y r IH ]; intros l2; simpl.
  - apply perm_refl.
  - apply (perm_trans (cons y (app r (cons x l2)))
                      (cons y (cons x (app r l2)))).
    + apply perm_skip. exact (IH l2).
    + apply perm_swap.
Qed.

Lemma perm_app_comm :
  forall {A : Type} (l1 l2 : list A), Perm (app l1 l2) (app l2 l1).
Proof.
  intros A l1 l2. generalize dependent l1.
  induction l2 as [ | x r IH ]; intros l1; simpl.
  - rewrite app_nil_r_eq. apply perm_refl.
  - apply (perm_trans (app l1 (cons x r)) (cons x (app l1 r))).
    + apply perm_cons_app.
    + apply perm_skip. exact (IH l1).
Qed.

(* =========================================================================
   The probabilistic interface, stated as a record of hypotheses rather than
   axiomatized: a sample space with a finite enumeration, a mass on each
   point, and a commutative monoid to add masses in.
   ========================================================================= *)

Record Probability : Type := {
  Tape : Type;
  tape_enum : list Tape;
  Mass : Type;
  mass : Tape -> Mass;
  m_zero : Mass;
  m_add : Mass -> Mass -> Mass;
  m_add_comm : forall a b : Mass, m_add a b = m_add b a;
  m_add_assoc : forall a b c : Mass,
    m_add a (m_add b c) = m_add (m_add a b) c;
  m_add_zero_l : forall a : Mass, m_add m_zero a = a
}.

Fixpoint fold_mass (p : Probability) (l : list (Mass p)) : Mass p :=
  match l with
  | nil => m_zero p
  | cons x r => m_add p x (fold_mass p r)
  end.

Definition pr (p : Probability) (q : Tape p -> bool) : Mass p :=
  fold_mass p (map_over (mass p) (filter_of q (tape_enum p))).

Lemma fold_mass_perm :
  forall (p : Probability) (l1 l2 : list (Mass p)),
    Perm l1 l2 -> fold_mass p l1 = fold_mass p l2.
Proof.
  intros p l1 l2 H.
  induction H as [ | x l l' H IH | x y l | l l' l'' H1 IH1 H2 IH2 ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
  - simpl. rewrite (m_add_assoc p). rewrite (m_add_assoc p).
    rewrite (m_add_comm p y x). reflexivity.
  - rewrite IH1. exact IH2.
Qed.

(* Probability reads only the enumerated support, including repeated entries.
   These laws need neither uniqueness nor a normalization of its masses. *)
Lemma support_filter_member : forall (A : Type) (q : A -> bool) (l : list A) (x : A),
  ProofSupport.Member x (filter_of q l) -> ProofSupport.Member x l.
Proof.
  intros A q l. induction l as [|a r IH]; intros x H; simpl in *.
  - exact H.
  - destruct (q a).
    + destruct H as [H | H]; [left; exact H | right; exact (IH x H)].
    + right. exact (IH x H).
Qed.

Lemma support_filter_ext : forall (A : Type) (q1 q2 : A -> bool) (l : list A),
  (forall x : A, ProofSupport.Member x l -> q1 x = q2 x) ->
  filter_of q1 l = filter_of q2 l.
Proof.
  intros A q1 q2 l. induction l as [|a r IH]; intros H; simpl.
  - reflexivity.
  - rewrite (H a (or_introl eq_refl)). rewrite IH; [reflexivity |].
    intros x Hx. apply H. right. exact Hx.
Qed.

Lemma support_map_ext : forall (A B : Type) (f g : A -> B) (l : list A),
  (forall x : A, ProofSupport.Member x l -> f x = g x) ->
  map_over f l = map_over g l.
Proof.
  intros A B f g l. induction l as [|a r IH]; intros H; simpl.
  - reflexivity.
  - rewrite (H a (or_introl eq_refl)). rewrite IH; [reflexivity |].
    intros x Hx. apply H. right. exact Hx.
Qed.

Lemma pr_ext_on_members :
  forall (p : Probability) (q1 q2 : Tape p -> bool),
    (forall t : Tape p, ProofSupport.Member t (tape_enum p) -> q1 t = q2 t) ->
    pr p q1 = pr p q2.
Proof.
  intros p q1 q2 H. unfold pr.
  rewrite (support_filter_ext (Tape p) q1 q2 (tape_enum p) H). reflexivity.
Qed.

Lemma pr_ext :
  forall (p : Probability) (q1 q2 : Tape p -> bool),
    (forall t : Tape p, q1 t = q2 t) -> pr p q1 = pr p q2.
Proof.
  intros p q1 q2 H. apply pr_ext_on_members. intros t _. exact (H t).
Qed.

Theorem reindexing_preserves_probability_on_members :
  forall (p : Probability) (sigma : Tape p -> Tape p) (q : Tape p -> bool),
    (forall t : Tape p, ProofSupport.Member t (tape_enum p) ->
       mass p (sigma t) = mass p t) ->
    Perm (map_over sigma (tape_enum p)) (tape_enum p) ->
    pr p (fun t => q (sigma t)) = pr p q.
Proof.
  intros p sigma q Hmass Hperm. unfold pr.
  assert (Hmap :
    map_over (mass p) (filter_of (fun t => q (sigma t)) (tape_enum p)) =
    map_over (fun t => mass p (sigma t))
      (filter_of (fun t => q (sigma t)) (tape_enum p))).
  { apply support_map_ext. intros t Ht. symmetry. apply Hmass.
    exact (support_filter_member (Tape p) (fun t => q (sigma t)) (tape_enum p) t Ht). }
  rewrite Hmap.
  rewrite <- (map_over_compose (mass p) sigma
                (filter_of (fun t => q (sigma t)) (tape_enum p))).
  rewrite (map_filter_comm sigma q (tape_enum p)).
  apply fold_mass_perm. apply perm_map. apply perm_filter. exact Hperm.
Qed.

(* A mass-preserving permutation of the finite sample space leaves each
   event's mass unchanged, using the commutative-monoid laws. *)
(*| discharges: R-15-053a |*)
Theorem reindexing_preserves_probability :
  forall (p : Probability) (sigma : Tape p -> Tape p) (q : Tape p -> bool),
    (forall t : Tape p, mass p (sigma t) = mass p t) ->
    Perm (map_over sigma (tape_enum p)) (tape_enum p) ->
    pr p (fun t => q (sigma t)) = pr p q.
Proof.
  intros p sigma q Hmass Hperm.
  apply reindexing_preserves_probability_on_members; [|exact Hperm].
  intros t _. exact (Hmass t).
Qed.

(* Two random variables over one sample space are identically distributed
   when every value carries the same mass under each. The equality test is
   a parameter and it carries weight: a degenerate one makes the predicate
   hold of everything, which `a_degenerate_equality_test_hides_every_
   difference` exhibits, and which is why every security statement below
   fixes the test to the sharing's own and keeps its soundness law. *)
Definition SameDistribution (p : Probability) (O : Type)
    (oeqb : O -> O -> bool) (f g : Tape p -> O) : Prop :=
  forall o : O, pr p (fun t => oeqb (f t) o) = pr p (fun t => oeqb (g t) o).

(*| discharges: R-05-165 |*)
Theorem a_degenerate_equality_test_hides_every_difference :
  forall (p : Probability) (O : Type) (f g : Tape p -> O),
    SameDistribution p O (fun _ _ => true) f g.
Proof.
  intros p O f g o. apply pr_ext. intros t. reflexivity.
Qed.

Theorem identical_views_are_identically_distributed :
  forall (p : Probability) (O : Type) (oeqb : O -> O -> bool)
         (f g : Tape p -> O),
    (forall t : Tape p, f t = g t) -> SameDistribution p O oeqb f g.
Proof.
  intros p O oeqb f g H o. apply pr_ext. intros t. rewrite (H t). reflexivity.
Qed.

Theorem rerandomization_hides_on_members :
  forall (p : Probability) (O : Type) (oeqb : O -> O -> bool)
         (f g : Tape p -> O) (sigma : Tape p -> Tape p),
    (forall t : Tape p, ProofSupport.Member t (tape_enum p) ->
       mass p (sigma t) = mass p t) ->
    Perm (map_over sigma (tape_enum p)) (tape_enum p) ->
    (forall t : Tape p, ProofSupport.Member t (tape_enum p) -> g (sigma t) = f t) ->
    SameDistribution p O oeqb f g.
Proof.
  intros p O oeqb f g sigma Hmass Hperm Hg o.
  rewrite <- (reindexing_preserves_probability_on_members p sigma
                (fun t => oeqb (g t) o) Hmass Hperm).
  apply pr_ext_on_members. intros t Ht. rewrite (Hg t Ht). reflexivity.
Qed.

(*| discharges: R-15-053a |*)
Theorem rerandomization_hides :
  forall (p : Probability) (O : Type) (oeqb : O -> O -> bool)
         (f g : Tape p -> O) (sigma : Tape p -> Tape p),
    (forall t : Tape p, mass p (sigma t) = mass p t) ->
    Perm (map_over sigma (tape_enum p)) (tape_enum p) ->
    (forall t : Tape p, g (sigma t) = f t) ->
    SameDistribution p O oeqb f g.
Proof.
  intros p O oeqb f g sigma Hmass Hperm Hg.
  apply (rerandomization_hides_on_members p O oeqb f g sigma).
  - intros t _. exact (Hmass t).
  - exact Hperm.
  - intros t _. exact (Hg t).
Qed.

(* -------------------------------------------------------------------------
   The uniform counting measure over a finite enumerated sample space: an
   inhabitant of the interface, and the premise R-05-004a's masking
   theorems take.
   ------------------------------------------------------------------------- *)

Definition counting (T : Type) (enum : list T) : Probability := {|
  Tape := T;
  tape_enum := enum;
  Mass := nat;
  mass := fun _ => 1;
  m_zero := 0;
  m_add := Nat.add;
  m_add_comm := add_comm_nat;
  m_add_assoc := add_assoc_nat;
  m_add_zero_l := add_zero_l_nat
|}.

Lemma counting_pr :
  forall (T : Type) (enum : list T) (q : T -> bool),
    pr (counting T enum) q = count_of (filter_of q enum).
Proof.
  intros T enum q. unfold pr. simpl.
  generalize (filter_of q enum). intros l.
  induction l as [ | x r IH ]; simpl; [ reflexivity | rewrite IH; reflexivity ].
Qed.

Lemma count_filter_image :
  forall {A B : Type} (f : A -> B) (q : B -> bool) (l : list A),
    count_of (filter_of (fun a => q (f a)) l)
    = count_of (filter_of q (map_over f l)).
Proof.
  intros A B f q l. induction l as [ | x r IH ]; simpl.
  - reflexivity.
  - destruct (q (f x)); simpl; rewrite IH; reflexivity.
Qed.

(* Under the counting measure, two random variables are identically
   distributed as soon as their images over the enumeration agree up to
   order. This is what makes a concrete non-vacuity witness decidable. *)
(*| discharges: R-05-166 |*)
Theorem equal_image_multisets_are_identically_distributed :
  forall (T : Type) (enum : list T) (O : Type) (oeqb : O -> O -> bool)
         (f g : T -> O),
    Perm (map_over f enum) (map_over g enum) ->
    SameDistribution (counting T enum) O oeqb f g.
Proof.
  intros T enum O oeqb f g Hperm o.
  rewrite counting_pr. rewrite counting_pr.
  apply (eq_trans (count_filter_image f (fun v => oeqb v o) enum)).
  symmetry.
  apply (eq_trans (count_filter_image g (fun v => oeqb v o) enum)).
  symmetry.
  apply count_of_perm. apply perm_filter. exact Hperm.
Qed.

(* =========================================================================
   An enumerated finite abelian group with translation-invariant enumeration,
   used for uniform masks. GF(2) supplies the Boolean examples; arithmetic
   gadget composition needs a prime-field instance.
   ========================================================================= *)

Record Sharing : Type := {
  Val : Type;
  v_eqb : Val -> Val -> bool;
  v_zero : Val;
  v_add : Val -> Val -> Val;
  v_sub : Val -> Val -> Val;
  v_enum : list Val;

  v_eqb_sound : forall a b : Val, v_eqb a b = true -> a = b;
  v_eqb_refl : forall a : Val, v_eqb a a = true;
  v_add_comm : forall a b : Val, v_add a b = v_add b a;
  v_add_assoc : forall a b c : Val,
    v_add a (v_add b c) = v_add (v_add a b) c;
  v_add_zero_l : forall a : Val, v_add v_zero a = a;
  v_sub_add : forall a b : Val, v_add (v_sub a b) b = a;
  v_add_sub : forall a b : Val, v_sub (v_add a b) b = a;
  v_enum_total : forall a : Val, any_of (v_eqb a) v_enum = true;
  v_enum_shift : forall k : Val, Perm (map_over (v_add k) v_enum) v_enum
}.

Lemma v_add_cancel_r :
  forall (m : Sharing) (a b c : Val m),
    v_add m a c = v_add m b c -> a = b.
Proof.
  intros m a b c H.
  rewrite <- (v_add_sub m a c). rewrite <- (v_add_sub m b c).
  rewrite H. reflexivity.
Qed.

Lemma v_sub_shift :
  forall (m : Sharing) (s1 s2 r : Val m),
    v_sub m s2 (v_add m (v_sub m s2 s1) r) = v_sub m s1 r.
Proof.
  intros m s1 s2 r.
  apply (v_add_cancel_r m _ _ (v_add m (v_sub m s2 s1) r)).
  rewrite (v_sub_add m s2 (v_add m (v_sub m s2 s1) r)).
  rewrite (v_add_assoc m (v_sub m s1 r) (v_sub m s2 s1) r).
  rewrite (v_add_comm m (v_sub m s1 r) (v_sub m s2 s1)).
  rewrite <- (v_add_assoc m (v_sub m s2 s1) (v_sub m s1 r) r).
  rewrite (v_sub_add m s1 r).
  rewrite (v_sub_add m s2 s1).
  reflexivity.
Qed.

Lemma list_eqb_sound :
  forall (m : Sharing) (l1 l2 : list (Val m)),
    list_eqb (v_eqb m) l1 l2 = true -> l1 = l2.
Proof.
  intros m l1. induction l1 as [ | x r IH ]; intros l2 H.
  - destruct l2 as [ | y s ]; [ reflexivity | discriminate H ].
  - destruct l2 as [ | y s ]; [ discriminate H | ].
    simpl in H. destruct (v_eqb m x y) eqn:Exy; [ | discriminate H ].
    simpl in H. rewrite (v_eqb_sound m x y Exy). rewrite (IH s H). reflexivity.
Qed.

(* The soundness law is what excludes the degenerate test above: a constant
   test is refuted by the very law `Sharing` carries. *)
(*| discharges: R-05-166 |*)
Theorem the_soundness_law_refuses_a_degenerate_equality_test :
  ~ (forall a b : bool, (fun _ _ : bool => true) a b = true -> a = b).
Proof.
  intros H. specialize (H false true eq_refl). discriminate H.
Qed.

(* =========================================================================
   Gate-level circuits and trace semantics. A wire index identifies its
   driving gate in the gate list.
   ========================================================================= *)

Inductive Gate : Type :=
  | g_in (i : nat)                        (* a primary input: a share, a
                                             randomness wire, or a public
                                             input; which is which is the
                                             experiment's to say           *)
  | g_reg (src : nat)                     (* a register sampling `src` at
                                             the end of each cycle         *)
  | g_op (o : nat) (args : list nat).     (* a combinational gate over the
                                             argument wires, under the
                                             experiment's operation
                                             alphabet                      *)

Definition Circuit : Type := list Gate.

Definition wire_count (c : Circuit) : nat := count_of c.

Definition gate_at (c : Circuit) (w : nat) : Gate := at_member c w (g_in 0).

Definition gate_args (g : Gate) : list nat :=
  match g with
  | g_in _ => nil
  | g_reg s => cons s nil
  | g_op _ a => a
  end.

Definition wires_exist (c : Circuit) (ps : list nat) : bool :=
  all_of (fun w => Nat.ltb w (wire_count c)) ps.

(* Combinational inputs must precede their gate. A register is a cycle
   boundary: its sampled source may occur anywhere in the circuit, including
   itself, but must exist. This admits synchronous feedback without admitting
   a combinational cycle or a dangling register source. *)
Definition gate_well_formed (total i : nat) (g : Gate) : bool :=
  match g with
  | g_in _ => true
  | g_reg src => Nat.ltb src total
  | g_op _ args => all_of (fun a => Nat.ltb a i) args
  end.

Fixpoint wf_from (total i : nat) (rest : list Gate) : bool :=
  match rest with
  | nil => true
  | cons g r => andb (gate_well_formed total i g) (wf_from total (S i) r)
  end.

Definition well_formed (c : Circuit) : bool := wf_from (wire_count c) 0 c.

Lemma wf_from_lookup :
  forall (rest : list Gate) (total i w : nat),
    wf_from total i rest = true -> Nat.ltb w (count_of rest) = true ->
    gate_well_formed total (Nat.add i w) (at_member rest w (g_in 0)) = true.
Proof.
  intros rest. induction rest as [ | g r IH ]; intros total i w Hwf Hw.
  - discriminate Hw.
  - simpl in Hwf.
    destruct (gate_well_formed total i g) eqn:Eg;
      [ | discriminate Hwf ].
    simpl in Hwf.
    destruct w as [ | k ]; simpl.
    + rewrite add_zero_r_nat. exact Eg.
    + simpl in Hw.
      rewrite add_succ_r_nat.
      exact (IH total (S i) k Hwf Hw).
Qed.

(*| discharges: R-15-053a |*)
Theorem well_formed_gate_reads_earlier_wires :
  forall (c : Circuit) (w o : nat) (args : list nat),
    well_formed c = true -> Nat.ltb w (wire_count c) = true ->
    gate_at c w = g_op o args ->
    all_of (fun a => Nat.ltb a w) args = true.
Proof.
  intros c w o args Hwf Hw Eg.
  pose proof (wf_from_lookup c (wire_count c) 0 w Hwf Hw) as H.
  change (gate_well_formed (wire_count c) w (gate_at c w) = true) in H.
  rewrite Eg in H. exact H.
Qed.

Theorem well_formed_register_source_exists :
  forall (c : Circuit) (w src : nat),
    well_formed c = true -> Nat.ltb w (wire_count c) = true ->
    gate_at c w = g_reg src -> Nat.ltb src (wire_count c) = true.
Proof.
  intros c w src Hwf Hw Eg.
  pose proof (wf_from_lookup c (wire_count c) 0 w Hwf Hw) as H.
  change (gate_well_formed (wire_count c) w (gate_at c w) = true) in H.
  rewrite Eg in H. exact H.
Qed.

(* -------------------------------------------------------------------------
   Evaluation. The combinational recursion is bounded by a fuel rather than
   by a well-foundedness argument, and `eval_fuel_irrelevant` below is what
   says the fuel is a proof device and not part of the model: over a
   well-formed circuit any two fuels past the probed wire agree.
   ------------------------------------------------------------------------- *)

Fixpoint eval_wire (m : Sharing) (ops : nat -> list (Val m) -> Val m)
    (c : Circuit) (regs : nat -> Val m) (ins : nat -> Val m)
    (fuel w : nat) : Val m :=
  match fuel with
  | 0 => v_zero m
  | S f =>
      match gate_at c w with
      | g_in i => ins i
      | g_reg _ => regs w
      | g_op o args => ops o (map_over (eval_wire m ops c regs ins f) args)
      end
  end.

Definition step_regs (m : Sharing) (ops : nat -> list (Val m) -> Val m)
    (c : Circuit) (regs : nat -> Val m) (ins : nat -> Val m) : nat -> Val m :=
  fun w => if gate_at c w is g_reg s then eval_wire m ops c regs ins (wire_count c) s
           else regs w.

Fixpoint regs_at (m : Sharing) (ops : nat -> list (Val m) -> Val m)
    (c : Circuit) (init : nat -> Val m) (ins : nat -> nat -> Val m)
    (t : nat) : nat -> Val m :=
  match t with
  | 0 => init
  | S k => step_regs m ops c (regs_at m ops c init ins k) (ins k)
  end.

Definition value_at (m : Sharing) (ops : nat -> list (Val m) -> Val m)
    (c : Circuit) (init : nat -> Val m) (ins : nat -> nat -> Val m)
    (t w : nat) : Val m :=
  eval_wire m ops c (regs_at m ops c init ins t) (ins t) (wire_count c) w.

Lemma eval_fuel_irrelevant_upto :
  forall (n : nat) (m : Sharing) (ops : nat -> list (Val m) -> Val m)
         (c : Circuit) (regs : nat -> Val m) (ins : nat -> Val m)
         (w f1 f2 : nat),
    well_formed c = true ->
    Nat.ltb w (wire_count c) = true ->
    Nat.ltb w n = true ->
    Nat.ltb w f1 = true -> Nat.ltb w f2 = true ->
    eval_wire m ops c regs ins f1 w = eval_wire m ops c regs ins f2 w.
Proof.
  intros n. induction n as [ | k IH ];
    intros m ops c regs ins w f1 f2 Hwf Hc Hn H1 H2.
  - discriminate Hn.
  - destruct f1 as [ | g1 ]; [ discriminate H1 | ].
    destruct f2 as [ | g2 ]; [ discriminate H2 | ].
    simpl. destruct (gate_at c w) as [ i | s | o args ] eqn:Eg.
    + reflexivity.
    + reflexivity.
    + f_equal. apply map_over_ext_nat. intros a Ha.
      pose proof (well_formed_gate_reads_earlier_wires c w o args Hwf Hc Eg)
        as Hargs.
      pose proof (all_of_mem_nat (fun b => Nat.ltb b w) args a Hargs Ha)
        as Haw.
      apply (IH m ops c regs ins a g1 g2 Hwf).
      * unfold Nat.ltb in *.
        exact (leb_trans_nat _ _ _ Haw (leb_drop_left _ _ Hc)).
      * unfold Nat.ltb in *. simpl in Hn.
        exact (leb_trans_nat _ _ _ Haw Hn).
      * unfold Nat.ltb in *. simpl in H1.
        exact (leb_trans_nat _ _ _ Haw H1).
      * unfold Nat.ltb in *. simpl in H2.
        exact (leb_trans_nat _ _ _ Haw H2).
Qed.

(*| discharges: R-15-053a |*)
Theorem eval_fuel_irrelevant :
  forall (m : Sharing) (ops : nat -> list (Val m) -> Val m) (c : Circuit)
         (regs : nat -> Val m) (ins : nat -> Val m) (w f1 f2 : nat),
    well_formed c = true ->
    Nat.ltb w (wire_count c) = true ->
    Nat.ltb w f1 = true -> Nat.ltb w f2 = true ->
    eval_wire m ops c regs ins f1 w = eval_wire m ops c regs ins f2 w.
Proof.
  intros m ops c regs ins w f1 f2 Hwf Hc H1 H2.
  exact (eval_fuel_irrelevant_upto (S w) m ops c regs ins w f1 f2
           Hwf Hc (leb_refl_nat (S w)) H1 H2).
Qed.

(* =========================================================================
   Probe observations and expansion functions.
   ========================================================================= *)

Inductive Obs : Type :=
  | obs_at (w : nat) (t : nat)      (* the stable value of wire w at cycle t *)
  | obs_delta (w : nat) (t : nat).  (* the difference across one cycle
                                       boundary at wire w *)

Definition obs_eqb (a b : Obs) : bool :=
  match a, b with
  | obs_at w1 t1, obs_at w2 t2 => andb (Nat.eqb w1 w2) (Nat.eqb t1 t2)
  | obs_delta w1 t1, obs_delta w2 t2 => andb (Nat.eqb w1 w2) (Nat.eqb t1 t2)
  | _, _ => false
  end.

Fixpoint mem_obs (o : Obs) (l : list Obs) : bool :=
  match l with
  | nil => false
  | cons x r => orb (obs_eqb o x) (mem_obs o r)
  end.

Definition obs_value (m : Sharing) (ops : nat -> list (Val m) -> Val m)
    (c : Circuit) (init : nat -> Val m) (ins : nat -> nat -> Val m)
    (o : Obs) : Val m :=
  match o with
  | obs_at w t => value_at m ops c init ins t w
  | obs_delta w t =>
      v_sub m (value_at m ops c init ins t w)
              (value_at m ops c init ins (prev_cycle t) w)
  end.

(* Follow combinational dependencies back to registers and primary inputs.
   Constant gates have no stable sources. *)
Fixpoint stable_sources (c : Circuit) (fuel w : nat) : list nat :=
  match fuel with
  | 0 => cons w nil
  | S f =>
      match gate_at c w with
      | g_in _ => cons w nil
      | g_reg _ => cons w nil
      | g_op _ args => flat_map_over (stable_sources c f) args
      end
  end.

Record Probe : Type := { p_wire : nat; p_cycle : nat }.

Definition Expansion : Type := Circuit -> Probe -> list Obs.

(* The classical d-probing model: the probe observes the settled value on
   the wire it sits on and nothing else. *)
Definition ex_stable : Expansion :=
  fun _ p => cons (obs_at (p_wire p) (p_cycle p)) nil.

(* Glitch observations. *)
Definition ex_glitch : Expansion :=
  fun c p => map_over (fun s => obs_at s (p_cycle p))
                      (stable_sources c (wire_count c) (p_wire p)).

(* Observe both values across a cycle boundary. *)
Definition ex_transition : Expansion :=
  fun _ p => cons (obs_at (p_wire p) (p_cycle p))
                  (cons (obs_at (p_wire p) (prev_cycle (p_cycle p))) nil).

(* Observe only the difference across a cycle boundary. *)
Definition ex_transition_delta : Expansion :=
  fun _ p => cons (obs_delta (p_wire p) (p_cycle p)) nil.

(* The combined R-15-053a expansion observes each stable source at the probed
   cycle and the preceding cycle. *)
Definition ex_robust : Expansion :=
  fun c p =>
    flat_map_over
      (fun s => cons (obs_at s (p_cycle p))
                     (cons (obs_at s (prev_cycle (p_cycle p))) nil))
      (stable_sources c (wire_count c) (p_wire p)).

Lemma robust_contains_glitch_list :
  forall (l : list nat) (t : nat),
    all_of (fun o => mem_obs o
              (flat_map_over
                 (fun s => cons (obs_at s t)
                                (cons (obs_at s (prev_cycle t)) nil)) l))
           (map_over (fun s => obs_at s t) l) = true.
Proof.
  intros l t. induction l as [ | s r IH ]; simpl.
  - reflexivity.
  - repeat rewrite eqb_refl_nat. simpl.
    apply (all_of_mono
             (fun o => mem_obs o
                (flat_map_over
                   (fun s0 => cons (obs_at s0 t)
                                   (cons (obs_at s0 (prev_cycle t)) nil)) r))).
    + intros o Ho. cbn [mem_obs]. rewrite Ho.
      destruct (obs_eqb o (obs_at s t));
        destruct (obs_eqb o (obs_at s (prev_cycle t))); reflexivity.
    + exact IH.
Qed.

(* The composed extension observes everything the glitch extension does,
   which is R-15-053a's "both extensions are in the statement" read at the
   observation set rather than asserted in prose. *)
(*| discharges: R-15-053a |*)
Theorem robust_expansion_contains_the_glitch_expansion :
  forall (c : Circuit) (p : Probe),
    all_of (fun o => mem_obs o (ex_robust c p)) (ex_glitch c p) = true.
Proof.
  intros c p. unfold ex_robust. unfold ex_glitch.
  apply robust_contains_glitch_list.
Qed.

(* -------------------------------------------------------------------------
   The glitch extension observes at least as much as the stable-value probe
   on the same wire: the values of a wire's stable sources determine its
   own. This is the general half of sanity result three; the concrete half,
   that the containment is STRICT at a wire where it matters, is
   `glitch_probe_sees_strictly_more_than_the_stable_probe` below.
   ------------------------------------------------------------------------- *)

Definition stable_value (m : Sharing) (c : Circuit)
    (regs : nat -> Val m) (ins : nat -> Val m) (s : nat) : Val m :=
  if gate_at c s is g_in i then ins i else regs s.

(*| discharges: R-15-053a |*)
Theorem stable_sources_determine_the_probed_value :
  forall (fuel : nat) (m : Sharing) (ops : nat -> list (Val m) -> Val m)
         (c : Circuit) (regs regs' : nat -> Val m) (ins ins' : nat -> Val m)
         (w : nat),
    (forall s : nat, mem_nat s (stable_sources c fuel w) = true ->
       stable_value m c regs ins s = stable_value m c regs' ins' s) ->
    eval_wire m ops c regs ins fuel w = eval_wire m ops c regs' ins' fuel w.
Proof.
  intros fuel. induction fuel as [ | f IH ];
    intros m ops c regs regs' ins ins' w H.
  - reflexivity.
  - simpl. destruct (gate_at c w) as [ i | s | o args ] eqn:Eg.
    (* A primary input or register output is its own only stable source. *)
    1-2: assert (Hw : stable_value m c regs ins w
                      = stable_value m c regs' ins' w)
           by (apply H; simpl; rewrite Eg; simpl; rewrite eqb_refl_nat;
               reflexivity);
         unfold stable_value in Hw; rewrite Eg in Hw; exact Hw.
    f_equal. apply map_over_ext_nat. intros a Ha.
    apply (IH m ops c regs regs' ins ins' a).
    intros s Hs. apply H. simpl. rewrite Eg.
    exact (mem_flat_map_over (stable_sources c f) args a s Ha Hs).
Qed.

(* =========================================================================
   The probe set, the view and the d-probe adversary.
   ========================================================================= *)

Definition probe_set (E : Expansion) (c : Circuit) (ps : list Probe)
    : list Obs := flat_map_over (E c) ps.

Definition admissible_probes (c : Circuit) (d : nat) (ps : list Probe)
    : bool :=
  andb (Nat.leb (count_of ps) d)
       (wires_exist c (map_over p_wire ps)).

(* -------------------------------------------------------------------------
   An experiment supplies a circuit, secret/randomness input assignment and
   probe budget. x_order counts physical probes, not shares.
   ------------------------------------------------------------------------- *)

Record Experiment : Type := {
  x_share : Sharing;
  x_prob : Probability;
  x_circuit : Circuit;
  x_ops : nat -> list (Val x_share) -> Val x_share;
  x_secret : Type;
  x_in : x_secret -> Tape x_prob -> nat -> nat -> Val x_share;
  x_init : x_secret -> Tape x_prob -> nat -> Val x_share;
  x_order : nat
}.

Definition x_view (x : Experiment) (E : Expansion) (ps : list Probe)
    (s : x_secret x) (t : Tape (x_prob x)) : list (Val (x_share x)) :=
  map_over (obs_value (x_share x) (x_ops x) (x_circuit x)
                      (x_init x s t) (x_in x s t))
           (probe_set E (x_circuit x) ps).

(* Perfect d-probing security for R-15-053a and R-05-004a: under the chosen
   expansion, every admissible probe list of length at most d has the same
   distribution for any two secrets. *)
Definition ProbingSecure (x : Experiment) (E : Expansion) : Prop :=
  forall ps : list Probe,
    admissible_probes (x_circuit x) (x_order x) ps = true ->
    forall s1 s2 : x_secret x,
      SameDistribution (x_prob x) (list (Val (x_share x)))
        (list_eqb (v_eqb (x_share x))) (x_view x E ps s1) (x_view x E ps s2).

(* A leak is the refusal, and it is what every sanity refutation below
   establishes. *)
Definition Leaks (x : Experiment) (E : Expansion) : Prop :=
  ~ ProbingSecure x E.

(* =========================================================================
   The d-share encoding and its two cases (sanity result one). The encoding
   is stated for an arbitrary order over an arbitrary group; the field is
   R-15-108's to select and is a variable here.
   ========================================================================= *)

Fixpoint sum_of (m : Sharing) (l : list (Val m)) : Val m :=
  match l with
  | nil => v_zero m
  | cons x r => v_add m x (sum_of m r)
  end.

(* d shares out of d-1 uniform masks: the completing share is what the
   secret enters through. *)
Definition encode (m : Sharing) (s : Val m) (masks : list (Val m))
    : list (Val m) := app masks (cons (v_sub m s (sum_of m masks)) nil).

Definition share_view (m : Sharing) (idxs : list nat) (shares : list (Val m))
    : list (Val m) :=
  map_over (fun i => at_member shares i (v_zero m)) idxs.

Lemma sum_of_app_one :
  forall (m : Sharing) (l : list (Val m)) (x : Val m),
    sum_of m (app l (cons x nil)) = v_add m (sum_of m l) x.
Proof.
  intros m l x. induction l as [ | y r IH ]; simpl.
  - rewrite (v_add_comm m x (v_zero m)). rewrite (v_add_zero_l m x).
    reflexivity.
  - rewrite IH. rewrite (v_add_assoc m y (sum_of m r) x). reflexivity.
Qed.

Lemma at_member_app_l :
  forall {A : Type} (l1 l2 : list A) (i : nat) (d : A),
    Nat.ltb i (count_of l1) = true ->
    at_member (app l1 l2) i d = at_member l1 i d.
Proof.
  intros A l1. induction l1 as [ | x r IH ]; intros l2 i d Hi.
  - discriminate Hi.
  - destruct i as [ | k ]; simpl; [ reflexivity | ].
    simpl in Hi. exact (IH l2 k d Hi).
Qed.

(* The whole sharing recovers the secret: the encoding is correct, and the
   probe bound is tight at the top because a probe set reaching every share
   reads the secret off them. *)
(*| discharges: R-15-053a |*)
Theorem the_whole_sharing_recovers_the_secret :
  forall (m : Sharing) (s : Val m) (masks : list (Val m)),
    sum_of m (encode m s masks) = s.
Proof.
  intros m s masks. unfold encode.
  rewrite (sum_of_app_one m masks (v_sub m s (sum_of m masks))).
  rewrite (v_add_comm m (sum_of m masks) (v_sub m s (sum_of m masks))).
  exact (v_sub_add m s (sum_of m masks)).
Qed.

(* CASE A, general in the order: a probe set that stays inside the masks
   observes a value the secret does not enter, so its distribution is the
   same for every two secrets at every instance of the interface. *)
(*| discharges: R-15-053a |*)
Theorem masks_alone_carry_no_secret :
  forall (m : Sharing) (s1 s2 : Val m) (idxs : list nat)
         (masks : list (Val m)),
    all_of (fun i => Nat.ltb i (count_of masks)) idxs = true ->
    share_view m idxs (encode m s1 masks)
    = share_view m idxs (encode m s2 masks).
Proof.
  intros m s1 s2 idxs masks H. unfold share_view. unfold encode.
  induction idxs as [ | i r IH ]; simpl.
  - reflexivity.
  - simpl in H. destruct (Nat.ltb i (count_of masks)) eqn:Ei;
      [ | discriminate H ].
    simpl in H.
    rewrite (at_member_app_l masks _ i (v_zero m) Ei).
    rewrite (at_member_app_l masks _ i (v_zero m) Ei).
    rewrite (IH H). reflexivity.
Qed.

(* CASE B at two shares, general in the group: the probe set reaches the
   completing share and misses the one mask, and re-randomizing that mask
   carries one secret's view onto the other's. This is the shape the
   arbitrary-order case takes; the generalization is proved below by Cartesian-mask reindexing. *)
Definition value_tapes (m : Sharing) : Probability :=
  counting (Val m) (v_enum m).

Definition two_share (m : Sharing) (s r : Val m) (k : nat) : Val m :=
  if k is 0 then r else v_sub m s r.

(*| discharges: R-15-053a |*)
Theorem two_share_encoding_hides_the_secret :
  forall (m : Sharing) (s1 s2 : Val m) (k : nat),
    SameDistribution (value_tapes m) (Val m) (v_eqb m)
      (fun r => two_share m s1 r k) (fun r => two_share m s2 r k).
Proof.
  intros m s1 s2 k. destruct k as [ | k ].
  - apply identical_views_are_identically_distributed. intros r. reflexivity.
  - apply (rerandomization_hides (value_tapes m) (Val m) (v_eqb m)
             (fun r => two_share m s1 r (S k))
             (fun r => two_share m s2 r (S k))
             (v_add m (v_sub m s2 s1))).
    + intros t. reflexivity.
    + simpl. exact (v_enum_shift m (v_sub m s2 s1)).
    + intros r. simpl. exact (v_sub_shift m s1 s2 r).
Qed.

(* =========================================================================
   NI, SNI and PINI use the same view: internal observations followed by
   selected output shares. Their bounds differ, not their observation format.
   ========================================================================= *)

Record Gadget : Type := {
  gd_share : Sharing;
  gd_prob : Probability;
  gd_circuit : Circuit;
  gd_ops : nat -> list (Val gd_share) -> Val gd_share;
  gd_inputs : nat;                 (* how many shared inputs the gadget takes *)
  gd_shares : nat;                 (* shares per input and per output          *)
  gd_out : nat -> nat;             (* output share index to wire               *)
  gd_read : nat;                   (* the cycle the output shares are read at  *)
  gd_assign : (nat -> nat -> Val gd_share) -> Tape gd_prob ->
              nat -> nat -> Val gd_share;
  gd_start : (nat -> nat -> Val gd_share) -> Tape gd_prob ->
             nat -> Val gd_share
}.

Definition ShareMatrix (g : Gadget) : Type := nat -> nat -> Val (gd_share g).
Definition ShareSet : Type := nat -> nat -> bool.

(* The local R-05-004a convention uses d+1 shares for probe order d. *)
Definition OrderMatchesShares (g : Gadget) (d : nat) : Prop :=
  gd_shares g = S d.

Definition gd_value (g : Gadget) (a : ShareMatrix g) (tape : Tape (gd_prob g))
    (t w : nat) : Val (gd_share g) :=
  value_at (gd_share g) (gd_ops g) (gd_circuit g)
           (gd_start g a tape) (gd_assign g a tape) t w.

Definition internal_view (g : Gadget) (E : Expansion) (ps : list Probe)
    (a : ShareMatrix g) (tape : Tape (gd_prob g)) : list (Val (gd_share g)) :=
  map_over (obs_value (gd_share g) (gd_ops g) (gd_circuit g)
                      (gd_start g a tape) (gd_assign g a tape))
           (probe_set E (gd_circuit g) ps).

Definition selected_outputs (g : Gadget) (B : nat -> bool)
    : list nat := filter_of B (upto (gd_shares g)).

Definition output_view (g : Gadget) (B : nat -> bool) (a : ShareMatrix g)
    (tape : Tape (gd_prob g)) : list (Val (gd_share g)) :=
  map_over (fun k => gd_value g a tape (gd_read g) (gd_out g k))
           (selected_outputs g B).

Definition split_view (g : Gadget) (E : Expansion) (ps : list Probe)
    (B : nat -> bool) (a : ShareMatrix g) (tape : Tape (gd_prob g))
    : list (Val (gd_share g)) :=
  app (internal_view g E ps a tape) (output_view g B a tape).

Definition card_in (g : Gadget) (I : ShareSet) (j : nat) : nat :=
  count_of (filter_of (I j) (upto (gd_shares g))).

Definition BoundedBy (g : Gadget) (I : ShareSet) (n : nat) : Prop :=
  forall j : nat, Nat.ltb j (gd_inputs g) = true ->
    Nat.leb (card_in g I j) n = true.

Definition agree_on (g : Gadget) (I : ShareSet) (a b : ShareMatrix g) : Prop :=
  forall j k : nat,
    Nat.ltb j (gd_inputs g) = true -> Nat.ltb k (gd_shares g) = true ->
    I j k = true -> a j k = b j k.

(* The view distribution depends only on the selected input shares. *)
Definition SimulableFrom (g : Gadget) (I : ShareSet)
    (f : ShareMatrix g -> Tape (gd_prob g) -> list (Val (gd_share g)))
    : Prop :=
  forall a b : ShareMatrix g, agree_on g I a b ->
    SameDistribution (gd_prob g) (list (Val (gd_share g)))
      (list_eqb (v_eqb (gd_share g))) (f a) (f b).

(* A simulator retains input shares in I and replaces all others with zero.
   SimulableFrom ensures this preserves the view distribution. *)
Definition restrict_to (g : Gadget) (I : ShareSet) (a : ShareMatrix g)
    : ShareMatrix g :=
  fun j k => if I j k then a j k else v_zero (gd_share g).

(*| discharges: R-05-166 |*)
Theorem dependence_yields_a_simulator :
  forall (g : Gadget) (I : ShareSet)
         (f : ShareMatrix g -> Tape (gd_prob g) -> list (Val (gd_share g))),
    SimulableFrom g I f ->
    forall a : ShareMatrix g,
      SameDistribution (gd_prob g) (list (Val (gd_share g)))
        (list_eqb (v_eqb (gd_share g))) (f a) (f (restrict_to g I a)).
Proof.
  intros g I f Hsim a. apply Hsim.
  intros j k _ _ HI. unfold restrict_to. rewrite HI. reflexivity.
Qed.

Definition union_shares (I : ShareSet) (B : nat -> bool) : ShareSet :=
  fun j k => orb (I j k) (B k).

Definition split_size (g : Gadget) (ps : list Probe) (B : nat -> bool) : nat :=
  Nat.add (count_of ps) (count_of (selected_outputs g B)).

(* NON-INTERFERENCE at order d. *)
Definition NI (g : Gadget) (E : Expansion) (d : nat) : Prop :=
  forall (ps : list Probe) (B : nat -> bool),
    wires_exist (gd_circuit g) (map_over p_wire ps) = true ->
    Nat.leb (split_size g ps B) d = true ->
    exists I : ShareSet,
      BoundedBy g I (split_size g ps B)
      /\ SimulableFrom g I (split_view g E ps B).

(* STRONG NON-INTERFERENCE at order d: the output probes buy no input
   shares, which is what makes an SNI gadget a refresh barrier. *)
Definition SNI (g : Gadget) (E : Expansion) (d : nat) : Prop :=
  forall (ps : list Probe) (B : nat -> bool),
    wires_exist (gd_circuit g) (map_over p_wire ps) = true ->
    Nat.leb (split_size g ps B) d = true ->
    exists I : ShareSet,
      BoundedBy g I (count_of ps)
      /\ SimulableFrom g I (split_view g E ps B).

(* PROBE-ISOLATING NON-INTERFERENCE at order d: an output share at index k
   is simulated from input share k of every input, plus the internal
   probes' own set. This local simulation budget does not bound output-share
   selections. A theorem composing gadgets under this predicate remains open. *)
Definition PINI (g : Gadget) (E : Expansion) (d : nat) : Prop :=
  forall (ps : list Probe) (B : nat -> bool),
    wires_exist (gd_circuit g) (map_over p_wire ps) = true ->
    Nat.leb (count_of ps) d = true ->
    exists I : ShareSet,
      BoundedBy g I (count_of ps)
      /\ SimulableFrom g (union_shares I B) (split_view g E ps B).

Lemma count_filter_or :
  forall {A : Type} (p q : A -> bool) (l : list A),
    Nat.leb (count_of (filter_of (fun a => orb (p a) (q a)) l))
            (Nat.add (count_of (filter_of p l)) (count_of (filter_of q l)))
    = true.
Proof.
  intros A p q l. induction l as [ | x r IH ]; simpl; [ reflexivity | ].
  destruct (p x) eqn:Ep; destruct (q x) eqn:Eq; simpl.
  - rewrite add_succ_r_nat. simpl. exact (leb_succ_r_nat _ _ IH).
  - exact IH.
  - rewrite add_succ_r_nat. simpl. exact IH.
  - exact IH.
Qed.

Lemma card_in_union :
  forall (g : Gadget) (I : ShareSet) (B : nat -> bool) (j : nat),
    Nat.leb (card_in g (union_shares I B) j)
            (Nat.add (card_in g I j) (count_of (selected_outputs g B)))
    = true.
Proof.
  intros g I B j. unfold card_in. unfold union_shares.
  unfold selected_outputs.
  exact (count_filter_or (I j) B (upto (gd_shares g))).
Qed.

(*| discharges: R-05-004a |*)
Theorem sni_implies_ni :
  forall (g : Gadget) (E : Expansion) (d : nat), SNI g E d -> NI g E d.
Proof.
  intros g E d H ps B Hw Hs.
  destruct (H ps B Hw Hs) as [ I [ Hb Hsim ] ].
  exists I. split; [ | exact Hsim ].
  intros j Hj. unfold split_size.
  exact (leb_trans_nat _ _ _ (Hb j Hj)
           (leb_add_r_nat (count_of ps)
              (count_of (selected_outputs g B)))).
Qed.

(*| discharges: R-05-004a |*)
Theorem pini_implies_ni :
  forall (g : Gadget) (E : Expansion) (d : nat), PINI g E d -> NI g E d.
Proof.
  intros g E d H ps B Hw Hs.
  assert (Hps : Nat.leb (count_of ps) d = true).
  { unfold split_size in Hs.
    exact (leb_trans_nat _ _ _
             (leb_add_r_nat (count_of ps)
                (count_of (selected_outputs g B))) Hs). }
  destruct (H ps B Hw Hps) as [ I [ Hb Hsim ] ].
  exists (union_shares I B). split; [ | exact Hsim ].
  intros j Hj. unfold split_size.
  apply (leb_trans_nat _
           (Nat.add (card_in g I j) (count_of (selected_outputs g B)))).
  - exact (card_in_union g I B j).
  - exact (leb_add_mono_r_nat _ _ _ (Hb j Hj)).
Qed.

(* =========================================================================
   The value algebra this file's witnesses run over: GF(2), the Boolean
   composition half's field. The arithmetic half instantiates the same
   record at a prime field.
   ========================================================================= *)

Definition gf2 : Sharing.
Proof.
  refine {|
    Val := bool;
    v_eqb := bool_eqb;
    v_zero := false;
    v_add := xorb;
    v_sub := xorb;
    v_enum := cons false (cons true nil)
  |}.
  - intros a b H. destruct a; destruct b;
      solve [ reflexivity | discriminate H ].
  - intros a. destruct a; reflexivity.
  - intros a b. destruct a; destruct b; reflexivity.
  - intros a b c. destruct a; destruct b; destruct c; reflexivity.
  - intros a. destruct a; reflexivity.
  - intros a b. destruct a; destruct b; reflexivity.
  - intros a b. destruct a; destruct b; reflexivity.
  - intros a. destruct a; reflexivity.
  - intros k. destruct k; simpl.
    + apply perm_swap.
    + apply perm_refl.
Defined.

Fixpoint xor_fold (l : list bool) : bool :=
  match l with nil => false | cons x r => xorb x (xor_fold r) end.

(* For these witnesses, operation 0 is constant zero; other indices XOR
   their arguments. General models parameterize the operation alphabet. *)
Definition gf2_ops (o : nat) (args : list bool) : bool :=
  if o is 0 then false else xor_fold args.

(* Tapes as bit vectors, so a demo's randomness is enumerated and every
   distribution below is decided by conversion. *)
Fixpoint bitvectors (n : nat) : list (list bool) :=
  match n with
  | 0 => cons nil nil
  | S k => flat_map_over
             (fun v => cons (cons false v) (cons (cons true v) nil))
             (bitvectors k)
  end.

Definition bit_at (v : list bool) (i : nat) : bool := at_member v i false.

Definition bit_tapes (n : nat) : Probability :=
  counting (list bool) (bitvectors n).

(* =========================================================================
   SANITY RESULT TWO: an unmasked wire carrying the secret IS a leak the
   model detects, and its one-share counterpart is not. Both witnesses are
   decided by conversion.
   ========================================================================= *)

Definition one_wire_circuit : Circuit := cons (g_in 0) nil.

Definition unmasked_experiment : Experiment := {|
  x_share := gf2;
  x_prob := bit_tapes 1;
  x_circuit := one_wire_circuit;
  x_ops := gf2_ops;
  x_secret := bool;
  x_in := fun s _ _ _ => s;
  x_init := fun _ _ _ => false;
  x_order := 1
|}.

Definition shared_experiment : Experiment := {|
  x_share := gf2;
  x_prob := bit_tapes 1;
  x_circuit := one_wire_circuit;
  x_ops := gf2_ops;
  x_secret := bool;
  x_in := fun s tape _ _ => xorb s (bit_at tape 0);
  x_init := fun _ _ _ => false;
  x_order := 1
|}.

Definition probe_of (w t : nat) : Probe := {| p_wire := w; p_cycle := t |}.

(*| discharges: R-15-053a |*)
Theorem an_unmasked_wire_is_a_leak :
  Leaks unmasked_experiment ex_stable.
Proof.
  intros H.
  specialize (H (cons (probe_of 0 0) nil) eq_refl false true).
  specialize (H (cons false nil)).
  vm_compute in H. discriminate H.
Qed.

(*| discharges: R-15-053a |*)
Theorem one_share_of_a_secret_is_not_a_leak :
  forall (ps : list Probe) (s1 s2 : bool),
    SameDistribution (x_prob shared_experiment)
      (list (Val (x_share shared_experiment)))
      (list_eqb (v_eqb (x_share shared_experiment)))
      (x_view shared_experiment ex_stable ps s1)
      (x_view shared_experiment ex_stable ps s2).
Proof.
  intros ps s1 s2.
  apply (equal_image_multisets_are_identically_distributed
           (list bool) (bitvectors 1)).
  destruct s1; destruct s2; simpl.
  - apply perm_refl.
  - apply perm_swap.
  - apply perm_swap.
  - apply perm_refl.
Qed.

(* =========================================================================
   SANITY RESULT THREE: the glitch extension is not vacuous. One circuit,
   one wire, one cycle, two expansions: the stable-value probe on the
   gadget output is secure and the glitch-extended probe on the same wire
   is a leak, so the extension observes STRICTLY more where it matters.
   The general containment is
   `stable_sources_determine_the_probed_value` above.

   The circuit is the textbook one: two shares and one fresh mask, with the
   recombination performed in a single combinational cone, so the settled
   value is uniform and the cone's stable sources are the two shares and
   the mask separately.
   ========================================================================= *)

Definition glitch_circuit : Circuit :=
  cons (g_in 0)                              (* 0: x1, the first share    *)
  (cons (g_in 1)                             (* 1: x2, the second share   *)
  (cons (g_in 2)                             (* 2: r, the fresh mask      *)
  (cons (g_op 1 (cons 0 (cons 2 nil)))       (* 3: a = x1 xor r           *)
  (cons (g_op 1 (cons 1 (cons 3 nil)))       (* 4: b = x2 xor a           *)
  (cons (g_reg 4) nil))))).                  (* 5: the output register    *)

Definition glitch_experiment : Experiment := {|
  x_share := gf2;
  x_prob := bit_tapes 2;
  x_circuit := glitch_circuit;
  x_ops := gf2_ops;
  x_secret := bool;
  x_in := fun s tape _ i =>
            match i with
            | 0 => bit_at tape 0
            | 1 => xorb s (bit_at tape 0)
            | _ => bit_at tape 1
            end;
  x_init := fun _ _ _ => false;
  x_order := 1
|}.

Example glitch_circuit_is_well_formed : well_formed glitch_circuit = true.
Proof. reflexivity. Qed.

(*| discharges: R-15-053a |*)
Theorem a_glitch_extended_probe_is_a_leak :
  Leaks glitch_experiment ex_glitch.
Proof.
  intros H.
  specialize (H (cons (probe_of 4 0) nil) eq_refl false true).
  specialize (H (cons false (cons false (cons false nil)))).
  vm_compute in H. discriminate H.
Qed.

(*| discharges: R-15-053a |*)
Theorem the_stable_probe_on_that_wire_is_not_a_leak :
  forall s1 s2 : bool,
    SameDistribution (x_prob glitch_experiment)
      (list (Val (x_share glitch_experiment)))
      (list_eqb (v_eqb (x_share glitch_experiment)))
      (x_view glitch_experiment ex_stable (cons (probe_of 4 0) nil) s1)
      (x_view glitch_experiment ex_stable (cons (probe_of 4 0) nil) s2).
Proof.
  intros s1 s2.
  apply (equal_image_multisets_are_identically_distributed
           (list bool) (bitvectors 2)).
  destruct s1; destruct s2; vm_compute.
  - apply perm_refl.
  - apply (perm_app_comm
             (cons (cons true nil) (cons (cons true nil) nil))
             (cons (cons false nil) (cons (cons false nil) nil))).
  - apply (perm_app_comm
             (cons (cons false nil) (cons (cons false nil) nil))
             (cons (cons true nil) (cons (cons true nil) nil))).
  - apply perm_refl.
Qed.

(* The two results together, at one wire and one cycle: the extension is
   not a re-spelling of the classical model. *)
(*| discharges: R-15-053a |*)
Theorem glitch_probe_sees_strictly_more_than_the_stable_probe :
  Leaks glitch_experiment ex_glitch
  /\ (forall s1 s2 : bool,
        SameDistribution (x_prob glitch_experiment)
          (list (Val (x_share glitch_experiment)))
          (list_eqb (v_eqb (x_share glitch_experiment)))
          (x_view glitch_experiment ex_stable (cons (probe_of 4 0) nil) s1)
          (x_view glitch_experiment ex_stable (cons (probe_of 4 0) nil) s2)).
Proof.
  split.
  - exact a_glitch_extended_probe_is_a_leak.
  - exact the_stable_probe_on_that_wire_is_not_a_leak.
Qed.

(* The combined extension also detects the glitch leak. *)
(*| discharges: R-15-053a |*)
Theorem the_robust_expansion_inherits_the_glitch_leak :
  Leaks glitch_experiment ex_robust.
Proof.
  intros H.
  specialize (H (cons (probe_of 4 0) nil) eq_refl false true).
  specialize (H (cons false (cons false (cons false
                  (cons false (cons false (cons false nil))))))).
  vm_compute in H. discriminate H.
Qed.

(* =========================================================================
   SANITY RESULT FOUR: a transition probe on a register reused across two
   shares IS a leak, and the same register holding one share twice is not.
   ========================================================================= *)

Definition register_circuit : Circuit :=
  cons (g_in 0) (cons (g_reg 0) nil).

Definition self_holding_register : Circuit := cons (g_reg 0) nil.
Definition toggling_register : Circuit :=
  cons (g_reg 1) (cons (g_op 0 (cons 0 nil)) nil).

Example synchronous_feedback_is_well_formed :
  (well_formed self_holding_register, well_formed toggling_register) = (true, true).
Proof. reflexivity. Qed.

Example register_feedback_holds_its_initial_value :
  forall initial : bool,
  value_at gf2 gf2_ops self_holding_register (fun _ => initial)
    (fun _ _ => false) 4 0 = initial.
Proof. reflexivity. Qed.

Definition toggle_ops (_ : nat) (args : list bool) : bool :=
  negb (at_member args 0 false).

Example register_combinational_feedback_toggles :
  (value_at gf2 toggle_ops toggling_register (fun _ => false)
     (fun _ _ => false) 1 0,
   value_at gf2 toggle_ops toggling_register (fun _ => false)
     (fun _ _ => false) 2 0) = (true, false).
Proof. reflexivity. Qed.

Example dangling_register_source_is_refused :
  well_formed (cons (g_reg 1) nil) = false.
Proof. reflexivity. Qed.

Example combinational_self_feedback_is_refused :
  well_formed (cons (g_op 0 (cons 0 nil)) nil) = false.
Proof. reflexivity. Qed.

(* The register carries the first share in the first cycle and the second
   in the next, which is the reuse a transition probe reads across. *)
Definition reused_register_experiment : Experiment := {|
  x_share := gf2;
  x_prob := bit_tapes 1;
  x_circuit := register_circuit;
  x_ops := gf2_ops;
  x_secret := bool;
  x_in := fun s tape t _ =>
            if t is 0 then bit_at tape 0 else xorb s (bit_at tape 0);
  x_init := fun _ _ _ => false;
  x_order := 1
|}.

(* The same register holding the same share in both cycles. *)
Definition held_register_experiment : Experiment := {|
  x_share := gf2;
  x_prob := bit_tapes 1;
  x_circuit := register_circuit;
  x_ops := gf2_ops;
  x_secret := bool;
  x_in := fun _ tape _ _ => bit_at tape 0;
  x_init := fun _ _ _ => false;
  x_order := 1
|}.

Example register_circuit_is_well_formed : well_formed register_circuit = true.
Proof. reflexivity. Qed.

(*| discharges: R-15-053a |*)
Theorem a_transition_probe_on_a_reused_register_is_a_leak :
  Leaks reused_register_experiment ex_transition.
Proof.
  intros H.
  specialize (H (cons (probe_of 1 2) nil) eq_refl false true).
  specialize (H (cons false (cons false nil))).
  vm_compute in H. discriminate H.
Qed.

(*| discharges: R-15-053a |*)
Theorem the_stable_probe_on_that_register_is_not_a_leak :
  forall s1 s2 : bool,
    SameDistribution (x_prob reused_register_experiment)
      (list (Val (x_share reused_register_experiment)))
      (list_eqb (v_eqb (x_share reused_register_experiment)))
      (x_view reused_register_experiment ex_stable
              (cons (probe_of 1 2) nil) s1)
      (x_view reused_register_experiment ex_stable
              (cons (probe_of 1 2) nil) s2).
Proof.
  intros s1 s2.
  apply (equal_image_multisets_are_identically_distributed
           (list bool) (bitvectors 1)).
  destruct s1; destruct s2; vm_compute.
  - apply perm_refl.
  - apply (perm_app_comm
             (cons (cons true nil) nil) (cons (cons false nil) nil)).
  - apply (perm_app_comm
             (cons (cons false nil) nil) (cons (cons true nil) nil)).
  - apply perm_refl.
Qed.

(* The admitted witness: reuse is what the transition probe reads, not the
   register. A register holding one share across the boundary carries the
   same view for every secret. *)
(*| discharges: R-15-053a |*)
Theorem a_transition_probe_on_a_held_register_is_not_a_leak :
  forall (ps : list Probe) (s1 s2 : bool),
    SameDistribution (x_prob held_register_experiment)
      (list (Val (x_share held_register_experiment)))
      (list_eqb (v_eqb (x_share held_register_experiment)))
      (x_view held_register_experiment ex_transition ps s1)
      (x_view held_register_experiment ex_transition ps s2).
Proof.
  intros ps s1 s2.
  apply identical_views_are_identically_distributed.
  intros t. reflexivity.
Qed.

(* =========================================================================
   Pair and difference-only transition observations differ: a register that
   holds the secret unchanged leaks under the pair model but has zero
   difference. The initial state here already contains the secret.
   ========================================================================= *)

Definition static_secret_experiment : Experiment := {|
  x_share := gf2;
  x_prob := bit_tapes 1;
  x_circuit := register_circuit;
  x_ops := gf2_ops;
  x_secret := bool;
  x_in := fun s _ _ _ => s;
  x_init := fun s _ _ => s;
  x_order := 1
|}.

Lemma static_secret_value : forall s t w,
  value_at gf2 gf2_ops register_circuit (fun _ => s) (fun _ _ => s) t w = s.
Proof.
  intros s t [|[|w]]; unfold value_at; simpl; try reflexivity.
  destruct t; reflexivity.
Qed.

(*| discharges: R-15-053a |*)
Theorem the_two_transition_readings_disagree :
  Leaks static_secret_experiment ex_transition
  /\ (forall (ps : list Probe) (s1 s2 : bool),
        SameDistribution (x_prob static_secret_experiment)
          (list (Val (x_share static_secret_experiment)))
          (list_eqb (v_eqb (x_share static_secret_experiment)))
          (x_view static_secret_experiment ex_transition_delta ps s1)
          (x_view static_secret_experiment ex_transition_delta ps s2)).
Proof.
  split.
  - intros H.
    specialize (H (cons (probe_of 1 2) nil) eq_refl false true).
    specialize (H (cons false (cons false nil))).
    vm_compute in H. discriminate H.
  - intros ps s1 s2.
    apply identical_views_are_identically_distributed.
    intros t. induction ps as [ | p r IH ]; [ reflexivity | ].
    unfold x_view. unfold probe_set. simpl.
    unfold x_view in IH. unfold probe_set in IH. simpl in IH.
    destruct p as [ w cyc ]. simpl.
    rewrite IH. repeat rewrite static_secret_value.
    destruct s1; destruct s2; reflexivity.
Qed.

(* =========================================================================
   The constant gadget satisfies NI, SNI and PINI at every order (R-05-165).
   The copy gadget separates PINI from SNI at the output boundary.
   ========================================================================= *)

Definition constant_circuit : Circuit := cons (g_op 0 nil) nil.

Definition constant_gadget : Gadget := {|
  gd_share := gf2;
  gd_prob := bit_tapes 0;
  gd_circuit := constant_circuit;
  gd_ops := gf2_ops;
  gd_inputs := 1;
  gd_shares := 1;
  gd_out := fun _ => 0;
  gd_read := 0;
  gd_assign := fun _ _ _ _ => false;
  gd_start := fun _ _ _ => false
|}.

Lemma constant_gadget_view_ignores_its_inputs :
  forall (E : Expansion) (ps : list Probe) (B : nat -> bool)
         (a b : ShareMatrix constant_gadget)
         (tape : Tape (gd_prob constant_gadget)),
    split_view constant_gadget E ps B a tape
    = split_view constant_gadget E ps B b tape.
Proof. intros E ps B a b tape. reflexivity. Qed.

Definition empty_shares : ShareSet := fun _ _ => false.

Lemma empty_shares_are_bounded :
  forall (g : Gadget) (n : nat), BoundedBy g empty_shares n.
Proof.
  intros g n j _. unfold card_in. unfold empty_shares.
  generalize (upto (gd_shares g)). intros l.
  induction l as [ | x r IH ]; simpl; [ reflexivity | exact IH ].
Qed.

(*| discharges: R-05-165 |*)
Theorem the_constant_gadget_satisfies_all_three_notions :
  forall (E : Expansion) (d : nat),
    NI constant_gadget E d /\ SNI constant_gadget E d
    /\ PINI constant_gadget E d.
Proof.
  (* The empty input-share set meets all three bounds. *)
  intros E d. split; [ | split ];
    (intros ps B _ _; exists empty_shares; split;
       [ apply empty_shares_are_bounded
       | intros a b _; apply identical_views_are_identically_distributed;
         intros tape; apply constant_gadget_view_ignores_its_inputs ]).
Qed.

(* The copy gadget: two shares of one input, carried to two output wires
   with nothing between them. *)
Definition copy_circuit : Circuit := cons (g_in 0) (cons (g_in 1) nil).

Definition copy_gadget : Gadget := {|
  gd_share := gf2;
  gd_prob := bit_tapes 0;
  gd_circuit := copy_circuit;
  gd_ops := gf2_ops;
  gd_inputs := 1;
  gd_shares := 2;
  gd_out := fun k => k;
  gd_read := 0;
  gd_assign := fun a _ _ i => a 0 i;
  gd_start := fun _ _ _ => false
|}.

Definition first_output : nat -> bool := fun k => Nat.eqb k 0.

(*| discharges: R-05-166 |*)
Theorem copy_gadget_refutes_sni :
  ~ SNI copy_gadget ex_stable 1.
Proof.
  intros H.
  destruct (H nil first_output eq_refl eq_refl) as [ I [ Hb Hsim ] ].
  specialize (Hb 0 eq_refl). unfold card_in in Hb. simpl in Hb.
  destruct (I 0 0) eqn:E0; [ simpl in Hb; discriminate Hb | ].
  destruct (I 0 1) eqn:E1; [ simpl in Hb; discriminate Hb | ].
  assert (Hagree : agree_on copy_gadget I
                     (fun _ _ => false) (fun _ _ => true)).
  { intros j k Hj Hk HI.
    destruct j as [ | j ]; [ | discriminate Hj ].
    destruct k as [ | k ]; [ rewrite E0 in HI; discriminate HI | ].
    destruct k as [ | k ]; [ rewrite E1 in HI; discriminate HI | ].
    discriminate Hk. }
  specialize (Hsim (fun _ _ => false) (fun _ _ => true) Hagree).
  specialize (Hsim (cons false nil)).
  vm_compute in Hsim. discriminate Hsim.
Qed.

(* PINI can simulate output share 0 from input share 0; SNI grants no
   input share for an output probe, so the same split fails SNI. *)
(*| discharges: R-05-004a |*)
Theorem copy_gadget_meets_the_pini_obligation_where_sni_fails :
  exists I : ShareSet,
    BoundedBy copy_gadget I (count_of (nil : list Probe))
    /\ SimulableFrom copy_gadget (union_shares I first_output)
         (split_view copy_gadget ex_stable nil first_output).
Proof.
  exists empty_shares. split.
  - apply empty_shares_are_bounded.
  - intros a b Hagree.
    apply identical_views_are_identically_distributed. intros tape.
    unfold split_view. unfold internal_view. unfold output_view. simpl.
    change (cons (a 0 0) nil = cons (b 0 0) nil).
    rewrite (Hagree 0 0 eq_refl eq_refl eq_refl). reflexivity.
Qed.

(* =========================================================================
   Three shares over GF(2), the case the general two-share theorem does not
   reach by itself: every probe set short of the whole sharing is hidden, and
   the whole sharing recovers the secret. Decided by conversion over the
   four tapes the two masks enumerate.
   ========================================================================= *)

Definition three_share_view (s : bool) (idxs : list nat) (tape : list bool)
    : list bool :=
  share_view gf2 idxs
    (encode gf2 s (cons (bit_at tape 0) (cons (bit_at tape 1) nil))).

Definition three_share_experiment_tapes : Probability := bit_tapes 2.

(* The two masks alone, both of them, hide the secret. *)
(*| discharges: R-15-053a |*)
Theorem three_shares_hide_the_secret_from_the_two_masks :
  forall s1 s2 : bool,
    SameDistribution three_share_experiment_tapes (list bool)
      (list_eqb bool_eqb)
      (three_share_view s1 (cons 0 (cons 1 nil)))
      (three_share_view s2 (cons 0 (cons 1 nil))).
Proof.
  intros s1 s2. apply identical_views_are_identically_distributed.
  intros tape. unfold three_share_view.
  apply (masks_alone_carry_no_secret gf2 s1 s2 (cons 0 (cons 1 nil))).
  reflexivity.
Qed.

(* A mask and the completing share, which is the case the re-randomization
   argument covers and the two-share theorem proves in general. *)
(*| discharges: R-15-053a |*)
Theorem three_shares_hide_the_secret_from_a_mask_and_the_last_share :
  forall s1 s2 : bool,
    SameDistribution three_share_experiment_tapes (list bool)
      (list_eqb bool_eqb)
      (three_share_view s1 (cons 0 (cons 2 nil)))
      (three_share_view s2 (cons 0 (cons 2 nil))).
Proof.
  intros [] [] obs; destruct obs as [|a [|b [|c r]]]; try reflexivity;
    destruct a; destruct b; reflexivity.
Qed.

(* And the bound is tight: the whole sharing is the secret. *)
(*| discharges: R-15-053a |*)
Theorem three_shares_are_recovered_by_the_whole_sharing :
  forall (s : bool) (tape : list bool),
    xor_fold (encode gf2 s (cons (bit_at tape 0) (cons (bit_at tape 1) nil)))
    = s.
Proof.
  intros s tape. destruct s; destruct (bit_at tape 0); destruct (bit_at tape 1);
    reflexivity.
Qed.

(* =========================================================================
   Order vs. share-count conventions: the two conventions are different
   arithmetic, so one letter cannot carry both without an entry saying which.
   ========================================================================= *)

(*| discharges: R-05-004a |*)
Theorem the_two_order_conventions_are_not_the_same_number :
  OrderMatchesShares copy_gadget 1
  /\ ~ OrderMatchesShares copy_gadget 2.
Proof.
  split; [ reflexivity | intros H; discriminate H ].
Qed.

(* -------------------------------------------------------------------------
   R-05-166's inhabitation witnesses: one closed definition per record this
   file's statements quantify over, named for that record and ascribed at
   it. The prover decides inhabitation by type-checking the ascription, so
   `run.py proofs` reads a name rather than approximating a type judgement.
   ------------------------------------------------------------------------- *)

Definition witness_Sharing : Sharing := gf2.
Definition witness_Probability : Probability := bit_tapes 1.
Definition witness_Probe : Probe := probe_of 0 0.
Definition witness_Experiment : Experiment := glitch_experiment.
Definition witness_Gadget : Gadget := copy_gadget.

(* The probability laws are record fields rather than undeclared global
   axioms, so the native gate can enforce R-05-164's declared assumption set. *)
(* R-05-163: `run.py proofs` audits the complete native inventory. *)


(* Arbitrary-order finite counting. These standard-library list and natural
   arithmetic lemmas introduce no probability or classical-choice axiom. *)
From Stdlib Require Import List Arith Lia.

Lemma map_over_is_map : forall {A B} (f : A -> B) xs, map_over f xs = map f xs.
Proof. intros A B f xs. induction xs; simpl; congruence. Qed.

Lemma count_of_is_length : forall {A} (xs : list A), count_of xs = length xs.
Proof. intros A xs. induction xs; simpl; congruence. Qed.

Lemma at_member_is_nth : forall {A} (xs : list A) i d, at_member xs i d = nth i xs d.
Proof. intros A xs. induction xs; intros [|i] d; simpl; auto. Qed.

Lemma all_of_is_forallb : forall {A} (f : A -> bool) xs, all_of f xs = forallb f xs.
Proof. intros A f xs. induction xs; simpl; congruence. Qed.

Lemma perm_map_std : forall {A B} (f : A -> B) xs ys,
  Perm xs ys -> Perm (map f xs) (map f ys).
Proof. intros. repeat rewrite <- map_over_is_map. apply perm_map. assumption. Qed.

Lemma perm_append_left : forall {A} (p a b : list A),
  Perm a b -> Perm (p ++ a) (p ++ b).
Proof. intros A p. induction p; intros; simpl; auto using perm_skip. Qed.

Lemma perm_append_right : forall {A} (a b r : list A),
  Perm a b -> Perm (a ++ r) (b ++ r).
Proof.
  intros A a b r H. induction H; simpl; auto using perm_refl, perm_skip, perm_swap.
  eapply perm_trans; eauto.
Qed.

Lemma perm_flat_map_std : forall {A B} (f : A -> list B) a b,
  Perm a b -> Perm (flat_map f a) (flat_map f b).
Proof.
  intros A B f a b H. induction H as [ | x l l' H IHPerm | | ]; simpl.
  - apply perm_refl.
  - apply perm_append_left. exact IHPerm.
  - repeat rewrite app_assoc. apply perm_append_right. apply perm_app_comm.
  - eapply perm_trans; eauto.
Qed.

Lemma perm_flat_map_pointwise : forall {A B} (f g : A -> list B) a,
  (forall x, In x a -> Perm (f x) (g x)) ->
  Perm (flat_map f a) (flat_map g a).
Proof.
  intros A B f g a. induction a as [ | x r IHa ]; intros H; simpl.
  - apply perm_refl.
  - eapply perm_trans.
    + apply perm_append_right. apply H. left. reflexivity.
    + apply perm_append_left. apply IHa. intros. apply H. right. assumption.
Qed.

Lemma map_flatten : forall {A B C} (f : B -> C) (g : A -> list B) a,
  map f (flat_map g a) = flat_map (fun x => map f (g x)) a.
Proof. intros A B C f g a. induction a as [ | x r IHa ]; simpl; auto. rewrite map_app, IHa. reflexivity. Qed.

Lemma flat_map_mapped : forall {A B C} (f : B -> list C) (g : A -> B) a,
  flat_map f (map g a) = flat_map (fun x => f (g x)) a.
Proof. intros A B C f g a. induction a; simpl; congruence. Qed.

Fixpoint mask_tuples (m : Sharing) (n : nat) : list (list (Val m)) :=
  match n with
  | O => nil :: nil
  | S k => flat_map (fun x => map (cons x) (mask_tuples m k)) (v_enum m)
  end.

Fixpoint shift_mask (m : Sharing) (i : nat) (delta : Val m)
    (xs : list (Val m)) : list (Val m) :=
  match xs, i with
  | nil, _ => nil
  | x :: r, O => v_add m delta x :: r
  | x :: r, S k => x :: shift_mask m k delta r
  end.

Lemma shift_mask_length : forall m i delta xs,
  length (shift_mask m i delta xs) = length xs.
Proof.
  intros m i delta xs. revert i. induction xs; intros [|i]; simpl; auto.
Qed.

Lemma shift_mask_sum : forall m i delta xs,
  i < length xs ->
  sum_of m (shift_mask m i delta xs) = v_add m delta (sum_of m xs).
Proof.
  intros m i delta xs. revert i. induction xs as [ | a xs IHxs ]; intros [|i] H; simpl in *; try lia.
  - symmetry. apply v_add_assoc.
  - rewrite IHxs by lia. rewrite (v_add_assoc m a delta (sum_of m xs)).
    rewrite (v_add_comm m a delta). symmetry. apply v_add_assoc.
Qed.

Lemma shift_mask_other : forall m i j delta xs,
  i <> j -> nth j (shift_mask m i delta xs) (v_zero m) = nth j xs (v_zero m).
Proof.
  intros m i j delta xs. revert i j.
  induction xs as [ | a xs IHxs ]; intros [|i] [|j] H; simpl; try reflexivity; try congruence.
  apply IHxs. congruence.
Qed.

Lemma mask_tuples_length : forall m n xs,
  In xs (mask_tuples m n) -> length xs = n.
Proof.
  intros m n. induction n as [ | n IHn ]; intros xs H.
  - simpl in H. destruct H as [<-|H]; [reflexivity|contradiction].
  - apply in_flat_map in H. destruct H as [x [Hx H]].
    apply in_map_iff in H. destruct H as [r [<- Hr]]. simpl. f_equal. apply IHn. exact Hr.
Qed.

Lemma shift_mask_permutation : forall m n i delta,
  i < n -> Perm (map (shift_mask m i delta) (mask_tuples m n)) (mask_tuples m n).
Proof.
  intros m n. induction n as [ | n IHn ]; intros [|i] delta H; try lia;
    cbn [mask_tuples]; rewrite map_flatten.
  - replace (flat_map
      (fun x => map (shift_mask m 0 delta) (map (cons x) (mask_tuples m n))) (v_enum m))
      with (flat_map (fun x => map (cons x) (mask_tuples m n))
              (map (v_add m delta) (v_enum m))).
    + apply perm_flat_map_std. rewrite <- map_over_is_map. exact (v_enum_shift m delta).
    + rewrite flat_map_mapped. apply flat_map_ext. intros x. rewrite map_map. reflexivity.
  - apply perm_flat_map_pointwise. intros x Hx. rewrite map_map.
    change (Perm (map (fun r => cons x (shift_mask m i delta r)) (mask_tuples m n))
                 (map (cons x) (mask_tuples m n))).
    rewrite <- map_map. apply perm_map_std. apply IHn. lia.
Qed.

Lemma share_view_shift : forall m s1 s2 n xs i idxs,
  length xs = n -> i < n -> ~ In i idxs ->
  (forall j, In j idxs -> j <= n) ->
  share_view m idxs (encode m s2 (shift_mask m i (v_sub m s2 s1) xs)) =
  share_view m idxs (encode m s1 xs).
Proof.
  intros m s1 s2 n xs i idxs Hlen Hi Hmiss Hbound.
  unfold share_view. repeat rewrite map_over_is_map. apply map_ext_in.
  intros j Hj. repeat rewrite at_member_is_nth.
  unfold encode. destruct (Nat.lt_ge_cases j n) as [Hjlt|Hjge].
  - repeat rewrite app_nth1; try (rewrite shift_mask_length, Hlen; lia); try lia.
    apply shift_mask_other. intro E. apply Hmiss. rewrite E. exact Hj.
  - assert (E : j = n) by (specialize (Hbound j Hj); lia). subst j.
    rewrite app_nth2, app_nth2; try (rewrite shift_mask_length, Hlen; lia); try lia.
    rewrite shift_mask_length, Hlen, Nat.sub_diag. cbn [nth].
    rewrite shift_mask_sum by lia. apply v_sub_shift.
Qed.

Lemma a_short_probe_list_misses_a_share : forall n idxs,
  length idxs < n -> exists i, i < n /\ ~ In i idxs.
Proof.
  intros n idxs Hlen.
  destruct (find (fun i => if in_dec Nat.eq_dec i idxs then false else true) (seq 0 n))
    as [i|] eqn:Hfind.
  - apply find_some in Hfind. destruct Hfind as [Hi Hmissing].
    apply in_seq in Hi. exists i. split; [lia|].
    destruct (in_dec Nat.eq_dec i idxs); [discriminate Hmissing|assumption].
  - assert (Hincl : incl (seq 0 n) idxs).
    { intros i Hi. pose proof (find_none _ _ Hfind i Hi) as He.
      cbn in He.
      destruct (in_dec Nat.eq_dec i idxs); [assumption|discriminate He]. }
    pose proof (NoDup_incl_length (seq_NoDup n 0) Hincl) as Hle.
    rewrite length_seq in Hle. lia.
Qed.

Theorem d_share_encoding_hides_from_d_minus_one_probes :
  forall (m : Sharing) (n : nat) (idxs : list nat) (s1 s2 : Val m),
  length idxs <= n -> (forall j, In j idxs -> j <= n) ->
  SameDistribution (counting (list (Val m)) (mask_tuples m n))
    (list (Val m)) (list_eqb (v_eqb m))
    (fun xs => share_view m idxs (encode m s1 xs))
    (fun xs => share_view m idxs (encode m s2 xs)).
Proof.
  intros m n idxs s1 s2 Hlen Hbound.
  apply equal_image_multisets_are_identically_distributed.
  repeat rewrite map_over_is_map.
  change (Perm (map (fun xs => share_view m idxs (encode m s1 xs)) (mask_tuples m n))
               (map (fun xs => share_view m idxs (encode m s2 xs)) (mask_tuples m n))).
  destruct (a_short_probe_list_misses_a_share (S n) idxs) as [i [Hi Hmiss]]; [lia|].
  destruct (Nat.lt_ge_cases i n) as [Hin|Hin].
  - set (sigma := shift_mask m i (v_sub m s2 s1)).
    replace (map (fun xs => share_view m idxs (encode m s1 xs)) (mask_tuples m n))
      with (map (fun xs => share_view m idxs (encode m s2 (sigma xs))) (mask_tuples m n)).
    + rewrite <- (map_map sigma (fun xs => share_view m idxs (encode m s2 xs)) (mask_tuples m n)).
      apply perm_map_std. apply shift_mask_permutation. exact Hin.
    + apply map_ext_in. intros xs Hxs. unfold sigma.
      apply (share_view_shift m s1 s2 n xs i idxs);
        auto using mask_tuples_length.
  - assert (Ei : i = n) by lia. subst i.
    assert (Heq : map (fun xs => share_view m idxs (encode m s1 xs)) (mask_tuples m n)
                = map (fun xs => share_view m idxs (encode m s2 xs)) (mask_tuples m n)).
    { apply map_ext_in. intros xs Hxs. apply masks_alone_carry_no_secret.
      rewrite all_of_is_forallb, count_of_is_length.
      apply forallb_forall. intros j Hj. apply Nat.ltb_lt.
      rewrite (mask_tuples_length m n xs Hxs). specialize (Hbound j Hj).
      assert (j <> n) by (intro E; apply Hmiss; rewrite <- E; exact Hj). lia. }
    rewrite Heq. apply perm_refl.
Qed.

Lemma sharing_enumeration_nonempty : forall m, v_enum m <> nil.
Proof.
  intros m E. pose proof (v_enum_total m (v_zero m)) as H.
  rewrite E in H. discriminate H.
Qed.

Lemma mask_tuples_nonempty : forall m n, exists xs, In xs (mask_tuples m n).
Proof.
  intros m n. induction n as [|n [xs Hxs]].
  - exists nil. left. reflexivity.
  - destruct (v_enum m) as [|x r] eqn:He.
    + exfalso. exact (sharing_enumeration_nonempty m He).
    + exists (x :: xs). cbn [mask_tuples]. apply in_flat_map.
      exists x. split; [rewrite He; left; reflexivity|].
      apply in_map. exact Hxs.
Qed.

(* A finite mass algebra has a nonzero normalizing denominator only under
   these extra laws. The base Probability record alone does not assert
   them. *)
Record FiniteMassQualification (p : Probability) : Type := {
  mass_unit : Mass p;
  mass_le : Mass p -> Mass p -> Prop;
  mass_le_refl : forall x, mass_le x x;
  mass_le_trans : forall x y z, mass_le x y -> mass_le y z -> mass_le x z;
  mass_le_antisym : forall x y, mass_le x y -> mass_le y x -> x = y;
  mass_add_monotone : forall a b c, mass_le a b ->
      mass_le (m_add p a c) (m_add p b c);
  mass_nonnegative : forall t, mass_le (m_zero p) (mass p t);
  mass_normalization : pr p (fun _ => true) = mass_unit;
  mass_unit_nonzero : mass_unit <> m_zero p
}.

Lemma counting_total : forall T enum,
  pr (counting T enum) (fun _ => true) = length enum.
Proof.
  intros T enum. rewrite counting_pr. induction enum; simpl; auto.
Qed.

Definition qualify_counting (T : Type) (enum : list T) (H : enum <> nil)
  : FiniteMassQualification (counting T enum).
Proof.
  refine (@Build_FiniteMassQualification (counting T enum) (length enum) le _ _ _ _ _ _ _); simpl.
  - auto.
  - intros. lia.
  - intros. lia.
  - intros. lia.
  - intros. lia.
  - apply counting_total.
  - destruct enum; [contradiction|discriminate].
Defined.

Definition qualified_mask_counting (m : Sharing) (n : nat)
  : FiniteMassQualification (counting (list (Val m)) (mask_tuples m n)).
Proof.
  apply qualify_counting. intro E.
  destruct (mask_tuples_nonempty m n) as [xs Hxs]. rewrite E in Hxs. contradiction.
Defined.

Theorem empty_counting_is_not_a_qualified_probability : forall T,
  FiniteMassQualification (counting T nil) -> False.
Proof.
  intros T q. pose proof (mass_normalization _ q) as H.
  apply (mass_unit_nonzero _ q). symmetry. exact H.
Qed.

Definition normalized_counting_observation {T O}
    (enum : list T) (eqb : O -> O -> bool) (f : T -> O) (o : O) : nat * nat :=
  (pr (counting T enum) (fun t => eqb (f t) o), length enum).

Theorem d_share_normalized_observations_agree :
  forall m n idxs s1 s2 o,
  length idxs <= n -> (forall j, In j idxs -> j <= n) ->
  normalized_counting_observation (mask_tuples m n) (list_eqb (v_eqb m))
      (fun xs => share_view m idxs (encode m s1 xs)) o =
  normalized_counting_observation (mask_tuples m n) (list_eqb (v_eqb m))
      (fun xs => share_view m idxs (encode m s2 xs)) o /\
  0 < length (mask_tuples m n).
Proof.
  intros m n idxs s1 s2 o H H0. split.
  - unfold normalized_counting_observation. f_equal.
    apply d_share_encoding_hides_from_d_minus_one_probes; assumption.
  - destruct (mask_tuples_nonempty m n) as [xs Hxs].
    destruct (mask_tuples m n); simpl in *; [contradiction|lia].
Qed.

Definition witness_FiniteMassQualification :
  FiniteMassQualification (counting (list (Val gf2)) (mask_tuples gf2 3)) :=
  qualified_mask_counting gf2 3.

(* An adaptive strategy can choose the next physical probe from the values
   already observed. Its interpreter exposes this interface without claiming
   the fixed-list security theorems above prove adaptive security. *)
Inductive ProbeStrategy (V : Type) : Type :=
  | strategy_stop : ProbeStrategy V
  | strategy_query : Probe -> (list V -> ProbeStrategy V) -> ProbeStrategy V.

Fixpoint adaptive_view (fuel : nat) (x : Experiment) (E : Expansion)
    (strategy : ProbeStrategy (Val (x_share x))) (s : x_secret x)
    (tape : Tape (x_prob x)) : list (Probe * list (Val (x_share x))) :=
  match fuel, strategy with
  | S f, strategy_query _ p next =>
      let values := x_view x E (p :: nil) s tape in
      (p, values) :: adaptive_view f x E (next values) s tape
  | _, _ => nil
  end.

Theorem adaptive_view_respects_its_physical_probe_budget :
  forall fuel x E strategy s tape,
  length (adaptive_view fuel x E strategy s tape) <= fuel.
Proof.
  induction fuel as [ | fuel IHfuel ]; intros x E strategy s tape; [reflexivity|].
  destruct strategy as [|p next]; cbn [adaptive_view length]; [lia|].
  specialize (IHfuel x E (next (x_view x E (p :: nil) s tape)) s tape). lia.
Qed.

Definition witness_ProbeStrategy : ProbeStrategy bool :=
  strategy_query bool (probe_of 0 0)
    (fun seen => strategy_query bool
       (probe_of (if at_member seen 0 false then 1 else 2) 1)
       (fun _ => strategy_stop bool)).

Definition zero_weight_probability : Probability :=
  {| Tape := unit; tape_enum := tt :: nil; Mass := nat;
     mass := fun _ => 0; m_zero := 0; m_add := Nat.add;
     m_add_comm := Nat.add_comm; m_add_assoc := Nat.add_assoc;
     m_add_zero_l := Nat.add_0_l |}.

Theorem zero_weight_probability_is_unqualified :
  FiniteMassQualification zero_weight_probability -> False.
Proof.
  intros q. apply (mass_unit_nonzero _ q).
  symmetry. exact (mass_normalization _ q).
Qed.

Definition QualifiedProbingSecure (x : Experiment) (E : Expansion) : Prop :=
  well_formed (x_circuit x) = true /\
  (exists q : FiniteMassQualification (x_prob x), True) /\ ProbingSecure x E.

Theorem the_shared_wire_has_qualified_stable_security :
  QualifiedProbingSecure shared_experiment ex_stable.
Proof.
  split; [reflexivity|]. split.
  - exists (qualify_counting (list bool) (bitvectors 1) (ltac:(discriminate))). exact I.
  - intros ps _ s1 s2. apply one_share_of_a_secret_is_not_a_leak.
Qed.

Example four_shares_and_three_probes_have_a_positive_normalizer :
  normalized_counting_observation (mask_tuples gf2 3) (list_eqb bool_eqb)
    (fun xs => share_view gf2 (0 :: 2 :: 3 :: nil) (encode gf2 true xs))
    (false :: true :: false :: nil) = (1, 8).
Proof. reflexivity. Qed.

(* =========================================================================
   Adaptive probing equivalence over ProbeStrategy, and instantiation for
   the general (n+1)-share additive encoding (R-15-053a, R-05-004a).
   ========================================================================= *)

Definition probe_eqb (p1 p2 : Probe) : bool :=
  andb (Nat.eqb (p_wire p1) (p_wire p2)) (Nat.eqb (p_cycle p1) (p_cycle p2)).

Lemma probe_eqb_refl : forall p : Probe, probe_eqb p p = true.
Proof.
  intros [w t]. unfold probe_eqb. simpl.
  rewrite Nat.eqb_refl, Nat.eqb_refl. reflexivity.
Qed.

Lemma probe_eqb_sound : forall p1 p2 : Probe, probe_eqb p1 p2 = true -> p1 = p2.
Proof.
  intros [w1 t1] [w2 t2] H. unfold probe_eqb in H. simpl in H.
  apply andb_prop in H. destruct H as [Hw Ht].
  apply Nat.eqb_eq in Hw. apply Nat.eqb_eq in Ht. subst. reflexivity.
Qed.

Definition trace_entry_eqb (m : Sharing)
    (e1 e2 : Probe * list (Val m)) : bool :=
  andb (probe_eqb (fst e1) (fst e2))
       (list_eqb (v_eqb m) (snd e1) (snd e2)).

Definition trace_eqb (m : Sharing)
    (tr1 tr2 : list (Probe * list (Val m))) : bool :=
  list_eqb (trace_entry_eqb m) tr1 tr2.

Lemma trace_entry_eqb_refl :
  forall (m : Sharing) (e : Probe * list (Val m)),
    trace_entry_eqb m e e = true.
Proof.
  intros m [p vs]. unfold trace_entry_eqb. simpl.
  rewrite probe_eqb_refl. induction vs as [|v r IH]; simpl; [reflexivity|].
  rewrite (v_eqb_refl m v). exact IH.
Qed.

Lemma trace_eqb_refl :
  forall (m : Sharing) (tr : list (Probe * list (Val m))),
    trace_eqb m tr tr = true.
Proof.
  intros m tr. unfold trace_eqb. induction tr as [|e r IH]; simpl; [reflexivity|].
  rewrite trace_entry_eqb_refl. exact IH.
Qed.

Lemma trace_eqb_sound :
  forall (m : Sharing) (tr1 tr2 : list (Probe * list (Val m))),
    trace_eqb m tr1 tr2 = true -> tr1 = tr2.
Proof.
  intros m tr1. unfold trace_eqb.
  induction tr1 as [|[p1 vs1] r1 IH]; intros [|[p2 vs2] r2] H;
    try reflexivity; try discriminate H.
  simpl in H. apply andb_prop in H. destruct H as [He Hr].
  unfold trace_entry_eqb in He. simpl in He.
  apply andb_prop in He. destruct He as [Hp Hvs].
  apply probe_eqb_sound in Hp. apply list_eqb_sound in Hvs.
  subst. f_equal. apply IH. exact Hr.
Qed.

Fixpoint strategy_admissible {V : Type} (c : Circuit) (fuel : nat)
    (st : ProbeStrategy V) : Prop :=
  match fuel, st with
  | O, _ => True
  | S f, strategy_stop _ => True
  | S f, strategy_query _ p next =>
      Nat.ltb (p_wire p) (wire_count c) = true /\
      forall seen : list V, strategy_admissible c f (next seen)
  end.

Definition AdaptiveProbingSecure (x : Experiment) (E : Expansion) : Prop :=
  forall (fuel : nat) (st : ProbeStrategy (Val (x_share x))),
    Nat.leb fuel (x_order x) = true ->
    strategy_admissible (x_circuit x) fuel st ->
    forall s1 s2 : x_secret x,
      SameDistribution (x_prob x)
        (list (Probe * list (Val (x_share x))))
        (trace_eqb (x_share x))
        (adaptive_view fuel x E st s1)
        (adaptive_view fuel x E st s2).

(* Extract the fixed probe list and flat observation vector determined by a
   strategy and a candidate trace, together with whether the trace matches
   the strategy's query structure and expansion lengths. *)
Fixpoint trace_accepts (fuel : nat) (x : Experiment) (E : Expansion)
    (st : ProbeStrategy (Val (x_share x)))
    (tr : list (Probe * list (Val (x_share x)))) : bool :=
  match fuel, st, tr with
  | O, _, nil => true
  | S _, strategy_stop _, nil => true
  | S f, strategy_query _ p next, (p', vs) :: rest =>
      andb (probe_eqb p' p)
           (andb (Nat.eqb (count_of vs) (count_of (E (x_circuit x) p)))
                 (trace_accepts f x E (next vs) rest))
  | _, _, _ => false
  end.

Fixpoint trace_probes (fuel : nat) (x : Experiment)
    (st : ProbeStrategy (Val (x_share x)))
    (tr : list (Probe * list (Val (x_share x)))) : list Probe :=
  match fuel, st, tr with
  | S f, strategy_query _ p next, (_, vs) :: rest =>
      p :: trace_probes f x (next vs) rest
  | _, _, _ => nil
  end.

Fixpoint trace_values {V : Type}
    (tr : list (Probe * list V)) : list V :=
  match tr with
  | nil => nil
  | (_, vs) :: rest => app vs (trace_values rest)
  end.

Lemma list_eqb_refl_sharing :
  forall (m : Sharing) (l : list (Val m)),
    list_eqb (v_eqb m) l l = true.
Proof.
  intros m l. induction l as [|x r IH]; simpl; [reflexivity|].
  rewrite (v_eqb_refl m x). exact IH.
Qed.

Lemma list_eqb_app_eq_len :
  forall (m : Sharing) (a1 a2 b1 b2 : list (Val m)),
    count_of a1 = count_of a2 ->
    list_eqb (v_eqb m) (app a1 b1) (app a2 b2) =
    andb (list_eqb (v_eqb m) a1 a2) (list_eqb (v_eqb m) b1 b2).
Proof.
  intros m a1. induction a1 as [|x r1 IH]; intros [|y r2] b1 b2 Hlen;
    simpl in *; try discriminate Hlen.
  - reflexivity.
  - rewrite <- Bool.andb_assoc. f_equal. apply IH. lia.
Qed.

Lemma x_view_cons :
  forall (x : Experiment) (E : Expansion) (p : Probe) (ps : list Probe)
         (s : x_secret x) (tape : Tape (x_prob x)),
    x_view x E (p :: ps) s tape =
    app (x_view x E (p :: nil) s tape) (x_view x E ps s tape).
Proof.
  intros x E p ps s tape. unfold x_view, probe_set. simpl.
  rewrite app_nil_r_eq.
  generalize (E (x_circuit x) p) as l1.
  generalize (flat_map_over (E (x_circuit x)) ps) as l2.
  intros l2 l1. induction l1 as [|o r IH]; simpl; [reflexivity|].
  rewrite IH. reflexivity.
Qed.

Lemma x_view_single_length :
  forall (x : Experiment) (E : Expansion) (p : Probe)
         (s : x_secret x) (tape : Tape (x_prob x)),
    count_of (x_view x E (p :: nil) s tape) =
    count_of (E (x_circuit x) p).
Proof.
  intros x E p s tape. unfold x_view, probe_set. simpl.
  rewrite app_nil_r_eq.
  induction (E (x_circuit x) p) as [|o r IH]; simpl; [reflexivity|].
  rewrite IH. reflexivity.
Qed.

Lemma trace_probes_length :
  forall (fuel : nat) (x : Experiment)
         (st : ProbeStrategy (Val (x_share x)))
         (tr : list (Probe * list (Val (x_share x)))),
    count_of (trace_probes fuel x st tr) <= fuel.
Proof.
  induction fuel as [|f IH]; intros x st tr;
    destruct st as [|p next], tr as [|[p' vs] rest];
    simpl; try lia.
  specialize (IH x (next vs) rest). lia.
Qed.

Lemma trace_probes_wires_exist :
  forall (fuel : nat) (x : Experiment)
         (st : ProbeStrategy (Val (x_share x)))
         (tr : list (Probe * list (Val (x_share x)))),
    strategy_admissible (x_circuit x) fuel st ->
    wires_exist (x_circuit x) (map_over p_wire (trace_probes fuel x st tr)) = true.
Proof.
  induction fuel as [|f IH]; intros x st tr Hadm;
    destruct st as [|p next], tr as [|[p' vs] rest];
    try reflexivity.
  cbn [strategy_admissible] in Hadm. destruct Hadm as [Hp Hnext].
  unfold wires_exist. cbn [trace_probes].
  change (map_over p_wire (p :: trace_probes f x (next vs) rest))
    with (p_wire p :: map_over p_wire (trace_probes f x (next vs) rest)).
  change (all_of (fun w => Nat.ltb w (wire_count (x_circuit x)))
                 (p_wire p :: map_over p_wire (trace_probes f x (next vs) rest)))
    with (andb (Nat.ltb (p_wire p) (wire_count (x_circuit x)))
               (all_of (fun w => Nat.ltb w (wire_count (x_circuit x)))
                       (map_over p_wire (trace_probes f x (next vs) rest)))).
  rewrite Hp. simpl. exact (IH x (next vs) rest (Hnext vs)).
Qed.

Lemma adaptive_trace_reduces_to_fixed_view :
  forall (fuel : nat) (x : Experiment) (E : Expansion)
         (st : ProbeStrategy (Val (x_share x)))
         (tr : list (Probe * list (Val (x_share x))))
         (s : x_secret x) (tape : Tape (x_prob x)),
    trace_eqb (x_share x) (adaptive_view fuel x E st s tape) tr =
    andb (trace_accepts fuel x E st tr)
         (list_eqb (v_eqb (x_share x))
            (x_view x E (trace_probes fuel x st tr) s tape)
            (trace_values tr)).
Proof.
  induction fuel as [|f IH]; intros x E st tr s tape.
  - destruct st, tr as [|[p' vs] rest]; reflexivity.
  - destruct st as [|p next]; destruct tr as [|[p' vs] rest]; try reflexivity.
    unfold trace_eqb.
    change (list_eqb (trace_entry_eqb (x_share x))
              (adaptive_view (S f) x E (strategy_query _ p next) s tape)
              ((p', vs) :: rest))
      with (andb (trace_entry_eqb (x_share x)
                    (p, x_view x E (p :: nil) s tape) (p', vs))
                 (trace_eqb (x_share x)
                    (adaptive_view f x E (next (x_view x E (p :: nil) s tape)) s tape)
                    rest)).
    cbn [trace_accepts trace_probes trace_values].
    rewrite (x_view_cons x E p (trace_probes f x (next vs) rest) s tape).
    unfold trace_entry_eqb. cbn [fst snd].
    destruct (probe_eqb p p') eqn:Epp'.
    + apply probe_eqb_sound in Epp'. subst p'. rewrite probe_eqb_refl.
      destruct (Nat.eqb (count_of vs) (count_of (E (x_circuit x) p))) eqn:Elen.
      * apply Nat.eqb_eq in Elen.
        rewrite list_eqb_app_eq_len by (rewrite x_view_single_length; symmetry; exact Elen).
        cbn [andb].
        destruct (list_eqb (v_eqb (x_share x))
                    (x_view x E (p :: nil) s tape) vs) eqn:Evs.
        -- apply list_eqb_sound in Evs. rewrite Evs. simpl.
           exact (IH x E (next vs) rest s tape).
        -- simpl. rewrite Bool.andb_false_r. reflexivity.
      * destruct (list_eqb (v_eqb (x_share x))
                    (x_view x E (p :: nil) s tape) vs) eqn:Evs; simpl.
        -- apply list_eqb_sound in Evs. rewrite <- Evs in Elen.
           rewrite x_view_single_length, Nat.eqb_refl in Elen. discriminate Elen.
        -- reflexivity.
    + assert (Hne : probe_eqb p' p = false).
      { destruct (probe_eqb p' p) eqn:E2; [|reflexivity].
        apply probe_eqb_sound in E2. subst. rewrite probe_eqb_refl in Epp'. discriminate. }
      rewrite Hne. reflexivity.
Qed.

(*| discharges: R-15-053a |*)
Theorem fixed_implies_adaptive_probing_secure :
  forall (x : Experiment) (E : Expansion),
    FiniteMassQualification (x_prob x) ->
    ProbingSecure x E ->
    AdaptiveProbingSecure x E.
Proof.
  intros x E _ Hfixed fuel st Hle Hadm s1 s2 tr.
  apply Nat.leb_le in Hle.
  apply eq_trans with
    (pr (x_prob x) (fun t =>
       andb (trace_accepts fuel x E st tr)
            (list_eqb (v_eqb (x_share x))
               (x_view x E (trace_probes fuel x st tr) s1 t)
               (trace_values tr)))).
  - apply pr_ext. intros t. apply adaptive_trace_reduces_to_fixed_view.
  - apply eq_trans with
      (pr (x_prob x) (fun t =>
         andb (trace_accepts fuel x E st tr)
              (list_eqb (v_eqb (x_share x))
                 (x_view x E (trace_probes fuel x st tr) s2 t)
                 (trace_values tr)))).
    + destruct (trace_accepts fuel x E st tr) eqn:Hacc.
      * apply Hfixed. unfold admissible_probes. apply andb_true_intro. split.
        -- apply Nat.leb_le.
           pose proof (trace_probes_length fuel x st tr). lia.
        -- exact (trace_probes_wires_exist fuel x st tr Hadm).
      * reflexivity.
    + apply pr_ext. intros t. symmetry. apply adaptive_trace_reduces_to_fixed_view.
Qed.

Fixpoint strategy_of_probes {V : Type} (ps : list Probe) : ProbeStrategy V :=
  match ps with
  | nil => strategy_stop V
  | p :: rest => strategy_query V p (fun _ => strategy_of_probes rest)
  end.

Lemma strategy_of_probes_admissible :
  forall (V : Type) (c : Circuit) (ps : list Probe),
    wires_exist c (map_over p_wire ps) = true ->
    strategy_admissible c (count_of ps) (strategy_of_probes ps : ProbeStrategy V).
Proof.
  intros V c ps. induction ps as [|p rest IH]; intros Hw; simpl in *; [exact I|].
  apply andb_prop in Hw. destruct Hw as [Hp Hrest].
  split; [exact Hp | intros _; exact (IH Hrest)].
Qed.

Lemma adaptive_view_strategy_of_probes :
  forall (x : Experiment) (E : Expansion) (ps : list Probe)
         (s : x_secret x) (tape : Tape (x_prob x)),
    trace_values (adaptive_view (count_of ps) x E (strategy_of_probes ps) s tape) =
    x_view x E ps s tape.
Proof.
  intros x E ps s tape. induction ps as [|p rest IH]; simpl.
  - reflexivity.
  - rewrite IH. symmetry. apply x_view_cons.
Qed.

(* Helper for Perm symmetry. *)
Lemma perm_sym_local : forall {A : Type} (l1 l2 : list A), Perm l1 l2 -> Perm l2 l1.
Proof.
  intros A l1 l2 H. induction H.
  - apply perm_nil.
  - apply perm_skip. exact IHPerm.
  - apply perm_swap.
  - eapply perm_trans; eauto.
Qed.

Lemma perm_from_eqb_counts :
  forall {A : Type} (eqA : A -> A -> bool) (l1 l2 : list A),
    (forall u v, eqA u v = true -> u = v) ->
    (forall u, eqA u u = true) ->
    (forall a : A, count_of (filter_of (fun z => eqA z a) l1) =
                   count_of (filter_of (fun z => eqA z a) l2)) ->
    Perm l1 l2.
Proof.
  intros A eqA l1. induction l1 as [|x r1 IH]; intros l2 Hsound Hrefl Hocc.
  - destruct l2 as [|y r2]; [apply perm_nil|].
    specialize (Hocc y). simpl in Hocc. rewrite Hrefl in Hocc. discriminate Hocc.
  - assert (Hin : ProofSupport.Member x l2).
    { specialize (Hocc x). simpl in Hocc. rewrite Hrefl in Hocc.
      clear -Hocc Hsound. induction l2 as [|y r2 IH2]; simpl in *; [discriminate|].
      destruct (eqA y x) eqn:Eyx.
      - left. symmetry. apply Hsound. exact Eyx.
      - right. apply IH2. exact Hocc. }
    assert (Hsplit : exists l2', Perm l2 (x :: l2')).
    { clear -Hin. induction l2 as [|y r2 IH2]; simpl in *; [contradiction|].
      destruct Hin as [Hy | Hr].
      - subst y. exists r2. apply perm_refl.
      - destruct (IH2 Hr) as [r2' Hr2']. exists (y :: r2').
        eapply perm_trans; [apply perm_skip; exact Hr2' | apply perm_swap]. }
    destruct Hsplit as [l2' Hl2'].
    apply perm_sym_local in Hl2'.
    eapply perm_trans; [|exact Hl2'].
    apply perm_skip. apply IH.
    + exact Hsound.
    + exact Hrefl.
    + intros a.
      pose proof (Hocc a) as Ha.
      pose proof (count_of_perm _ _ (perm_filter (fun z => eqA z a) _ _ Hl2')) as Hp.
      cbn [filter_of ProofSupport.filter_of] in Ha, Hp.
      rewrite count_of_is_length in Ha, Hp.
      rewrite <- Hp in Ha.
      destruct (eqA x a); simpl in Ha; repeat rewrite count_of_is_length; unfold filter_of; lia.
Qed.

Lemma counting_pushforward :
  forall (T : Type) (enum : list T) (A B : Type) (eqA : A -> A -> bool)
         (eqB : B -> B -> bool) (f g : T -> A) (h : A -> B),
    (forall a1 a2, eqA a1 a2 = true -> a1 = a2) ->
    (forall a, eqA a a = true) ->
    SameDistribution (counting T enum) A eqA f g ->
    SameDistribution (counting T enum) B eqB (fun t => h (f t)) (fun t => h (g t)).
Proof.
  intros T enum A B eqA eqB f g h Hsound Hrefl Hsame.
  apply (equal_image_multisets_are_identically_distributed T enum B eqB
           (fun t => h (f t)) (fun t => h (g t))).
  rewrite <- (map_over_compose h f enum), <- (map_over_compose h g enum).
  apply (perm_map h). apply (perm_from_eqb_counts eqA); [exact Hsound|exact Hrefl|].
  intros a. rewrite <- count_filter_image, <- count_filter_image.
  rewrite <- counting_pr, <- counting_pr. exact (Hsame a).
Qed.

Fixpoint chunk_trace (c : Circuit) (E : Expansion) (ps : list Probe)
    {V : Type} (vals : list V) : list (Probe * list V) :=
  match ps with
  | nil => nil
  | p :: rest =>
      let k := count_of (E c p) in
      (p, ProofSupport.take_of k vals) ::
        chunk_trace c E rest (ProofSupport.drop_of k vals)
  end.

Lemma take_drop_exact :
  forall {A : Type} (k : nat) (l1 l2 : list A),
    count_of l1 = k ->
    ProofSupport.take_of k (app l1 l2) = l1 /\
    ProofSupport.drop_of k (app l1 l2) = l2.
Proof.
  intros A k l1. revert k. induction l1 as [|x r IH]; intros [|k] l2 Hk;
    simpl in *; try discriminate Hk.
  - split; reflexivity.
  - destruct (IH k l2 ltac:(lia)) as [Ht Hd]. split; [f_equal; exact Ht | exact Hd].
Qed.

Lemma count_of_take_le :
  forall {A : Type} (k : nat) (l : list A),
    k <= count_of l -> count_of (ProofSupport.take_of k l) = k.
Proof.
  intros A k. induction k as [|k IH]; intros [|x r] H; simpl in *; try lia.
  f_equal. apply IH. lia.
Qed.

Lemma trace_eqb_chunk_iff :
  forall (x : Experiment) (E : Expansion) (ps : list Probe)
         (s : x_secret x) (tape : Tape (x_prob x))
         (o : list (Val (x_share x))),
    count_of o = count_of (probe_set E (x_circuit x) ps) ->
    trace_eqb (x_share x)
      (adaptive_view (count_of ps) x E (strategy_of_probes ps) s tape)
      (chunk_trace (x_circuit x) E ps o) =
    list_eqb (v_eqb (x_share x)) (x_view x E ps s tape) o.
Proof.
  intros x E ps s tape. induction ps as [|p rest IH]; intros o Hlen.
  - unfold probe_set in Hlen. simpl in Hlen.
    destruct o; [reflexivity | discriminate Hlen].
  - unfold trace_eqb.
    change (list_eqb (trace_entry_eqb (x_share x))
              (adaptive_view (count_of (p :: rest)) x E (strategy_of_probes (p :: rest)) s tape)
              (chunk_trace (x_circuit x) E (p :: rest) o))
      with (andb (trace_entry_eqb (x_share x)
                    (p, x_view x E (p :: nil) s tape)
                    (p, ProofSupport.take_of (count_of (E (x_circuit x) p)) o))
                 (trace_eqb (x_share x)
                    (adaptive_view (count_of rest) x E (strategy_of_probes rest) s tape)
                    (chunk_trace (x_circuit x) E rest
                       (ProofSupport.drop_of (count_of (E (x_circuit x) p)) o)))).
    rewrite (x_view_cons x E p rest s tape).
    assert (Hlen1 : count_of (x_view x E (p :: nil) s tape) = count_of (E (x_circuit x) p))
      by apply x_view_single_length.
    assert (Hlen_app : count_of (E (x_circuit x) p) <= count_of o).
    { unfold probe_set in Hlen. simpl in Hlen. rewrite Hlen.
      clear. induction (E (x_circuit x) p) as [|? ? IHl]; simpl; lia. }
    assert (Htake_len : count_of (ProofSupport.take_of (count_of (E (x_circuit x) p)) o)
                        = count_of (E (x_circuit x) p))
      by (apply count_of_take_le; exact Hlen_app).
    assert (Ho_split : o = app (ProofSupport.take_of (count_of (E (x_circuit x) p)) o)
                               (ProofSupport.drop_of (count_of (E (x_circuit x) p)) o)).
    { clear. generalize (count_of (E (x_circuit x) p)) o.
      induction n as [|n IH]; intros [|y r]; simpl; try reflexivity.
      f_equal. apply IH. }
    rewrite Ho_split at 3.
    rewrite list_eqb_app_eq_len by (rewrite Hlen1, Htake_len; reflexivity).
    unfold trace_entry_eqb. cbn [fst snd]. rewrite probe_eqb_refl. cbn [andb].
    f_equal. apply IH.
    unfold probe_set in *. simpl in Hlen.
    rewrite Ho_split in Hlen at 1.
    repeat rewrite count_of_is_length in *.
    repeat rewrite length_app in Hlen.
    lia.
Qed.

Lemma x_view_length :
  forall (x : Experiment) (E : Expansion) (ps : list Probe)
         (s : x_secret x) (tape : Tape (x_prob x)),
    count_of (x_view x E ps s tape) = count_of (probe_set E (x_circuit x) ps).
Proof.
  intros x E ps s tape. unfold x_view.
  induction (probe_set E (x_circuit x) ps); simpl; auto.
Qed.

(*| discharges: R-15-053a |*)
Theorem adaptive_implies_fixed_probing_secure :
  forall (x : Experiment) (E : Expansion),
    AdaptiveProbingSecure x E ->
    ProbingSecure x E.
Proof.
  intros x E Hadapt ps Hadm s1 s2 o.
  unfold admissible_probes in Hadm. apply andb_prop in Hadm.
  destruct Hadm as [Hord Hw].
  destruct (Nat.eq_dec (count_of o) (count_of (probe_set E (x_circuit x) ps))) as [Hlen|Hne].
  - specialize (Hadapt (count_of ps) (strategy_of_probes ps) Hord
                 (strategy_of_probes_admissible _ (x_circuit x) ps Hw)
                 s1 s2 (chunk_trace (x_circuit x) E ps o)).
    eapply eq_trans; [|eapply eq_trans; [exact Hadapt|]].
    + apply pr_ext. intros t. symmetry. apply trace_eqb_chunk_iff. exact Hlen.
    + apply pr_ext. intros t. apply trace_eqb_chunk_iff. exact Hlen.
  - apply eq_trans with (pr (x_prob x) (fun _ => false)).
    + apply pr_ext. intros t.
      destruct (list_eqb (v_eqb (x_share x)) (x_view x E ps s1 t) o) eqn:E1; [|reflexivity].
      apply list_eqb_sound in E1. exfalso. apply Hne. rewrite <- E1.
      apply x_view_length.
    + apply pr_ext. intros t.
      destruct (list_eqb (v_eqb (x_share x)) (x_view x E ps s2 t) o) eqn:E2; [|reflexivity].
      apply list_eqb_sound in E2. exfalso. apply Hne. rewrite <- E2.
      apply x_view_length.
Qed.

(*| discharges: R-15-053a |*)
Theorem adaptive_probing_equivalence :
  forall (x : Experiment) (E : Expansion),
    FiniteMassQualification (x_prob x) ->
    (ProbingSecure x E <-> AdaptiveProbingSecure x E).
Proof.
  intros x E Hq. split.
  - apply fixed_implies_adaptive_probing_secure. exact Hq.
  - apply adaptive_implies_fixed_probing_secure.
Qed.

(* General (n+1)-share additive encoding experiment and adaptive theorem. *)
Fixpoint input_wires_circuit (k : nat) : Circuit :=
  match k with
  | O => nil
  | S m => app (input_wires_circuit m) (cons (g_in m) nil)
  end.

Lemma input_wires_count :
  forall k : nat, wire_count (input_wires_circuit k) = k.
Proof.
  induction k as [|k IH]; simpl; [reflexivity|].
  unfold wire_count in *.
  rewrite count_of_is_length, length_app. simpl.
  rewrite <- count_of_is_length. lia.
Qed.

Lemma at_member_app_last :
  forall {A : Type} (l : list A) (x d : A),
    at_member (app l (cons x nil)) (count_of l) d = x.
Proof.
  intros A l x d. induction l as [|y r IH]; simpl; [reflexivity | exact IH].
Qed.

Lemma input_wires_gate_at :
  forall k w : nat,
    w < k -> gate_at (input_wires_circuit k) w = g_in w.
Proof.
  induction k as [|k IH]; intros w Hw; [lia|].
  unfold gate_at. simpl.
  destruct (Nat.lt_ge_cases w k) as [Hlt | Hge].
  - rewrite at_member_app_l; [apply IH; exact Hlt|].
    rewrite <- (input_wires_count k) in Hlt.
    unfold wire_count in Hlt. apply Nat.ltb_lt. exact Hlt.
  - assert (E : w = k) by lia. subst w.
    assert (Hk : k = count_of (input_wires_circuit k))
      by (symmetry; apply input_wires_count).
    rewrite Hk at 3. apply at_member_app_last.
Qed.

Lemma wf_from_input_wires :
  forall total k i : nat, wf_from total i (input_wires_circuit k) = true.
Proof.
  intros total k. induction k as [|k IH]; intros i; simpl; [reflexivity|].
  assert (Happ : forall l1 l2 j,
    wf_from total j (app l1 l2) =
    andb (wf_from total j l1) (wf_from total (Nat.add j (count_of l1)) l2)).
  { clear. induction l1 as [|x r1 IHl]; intros l2 j; simpl.
    - rewrite add_zero_r_nat. reflexivity.
    - rewrite IHl, add_succ_r_nat. destruct (gate_well_formed total j x); reflexivity. }
  rewrite Happ. rewrite IH. reflexivity.
Qed.

Lemma input_wires_well_formed :
  forall k : nat, well_formed (input_wires_circuit k) = true.
Proof.
  intros k. unfold well_formed. apply wf_from_input_wires.
Qed.

Definition d_share_experiment (m : Sharing) (n : nat) : Experiment := {|
  x_share := m;
  x_prob := counting (list (Val m)) (mask_tuples m n);
  x_circuit := input_wires_circuit (S n);
  x_ops := fun _ _ => v_zero m;
  x_secret := Val m;
  x_in := fun s tape _ i => at_member (encode m s tape) i (v_zero m);
  x_init := fun _ _ _ => v_zero m;
  x_order := n
|}.

Lemma d_share_experiment_value :
  forall (m : Sharing) (n : nat) (s : Val m) (tape : list (Val m))
         (t w : nat),
    w <= n ->
    value_at m (fun _ _ => v_zero m) (input_wires_circuit (S n))
      (fun _ => v_zero m)
      (fun _ i => at_member (encode m s tape) i (v_zero m)) t w =
    at_member (encode m s tape) w (v_zero m).
Proof.
  intros m n s tape t w Hw. unfold value_at.
  rewrite input_wires_count. cbn [eval_wire].
  rewrite input_wires_gate_at by lia. reflexivity.
Qed.

(*| discharges: R-15-053a, R-05-004a |*)
Theorem d_share_experiment_probing_secure :
  forall (m : Sharing) (n : nat),
    QualifiedProbingSecure (d_share_experiment m n) ex_stable.
Proof.
  intros m n. split; [apply input_wires_well_formed|]. split.
  - exists (qualified_mask_counting m n). exact I.
  - intros ps Hadm s1 s2.
    unfold admissible_probes in Hadm. apply andb_prop in Hadm.
    destruct Hadm as [Hord Hw].
    unfold x_order in Hord. apply Nat.leb_le in Hord.
    unfold wires_exist in Hw. unfold d_share_experiment in Hw. cbn [x_circuit] in Hw.
    rewrite input_wires_count in Hw.
    assert (Hbound : forall j, In j (map p_wire ps) -> j <= n).
    { intros j Hj. rewrite <- map_over_is_map in Hj.
      clear -Hw Hj. induction ps as [|p r IH]; simpl in *; [contradiction|].
      apply andb_prop in Hw. destruct Hw as [Hp Hr].
      destruct Hj as [Hp_eq|Hj].
      - subst j. apply Nat.ltb_lt in Hp. lia.
      - apply IH; assumption. }
    assert (Hlen : length (map p_wire ps) <= n).
    { rewrite length_map, <- count_of_is_length. exact Hord. }
    pose proof (d_share_encoding_hides_from_d_minus_one_probes m n
                  (map p_wire ps) s1 s2 Hlen Hbound) as Hdist.
    assert (Hview : forall s tape,
      x_view (d_share_experiment m n) ex_stable ps s tape =
      share_view m (map p_wire ps) (encode m s tape)).
    { intros s tape. unfold x_view, probe_set, share_view, d_share_experiment.
      cbn [x_circuit x_ops x_init x_in x_share].
      rewrite <- map_over_is_map.
      clear -Hw. induction ps as [|p r IH]; [reflexivity|].
      simpl in Hw. apply andb_prop in Hw. destruct Hw as [Hp Hr].
      apply Nat.ltb_lt in Hp.
      change (map_over (obs_value m (fun _ _ => v_zero m) (input_wires_circuit (S n))
                         (fun _ => v_zero m)
                         (fun _ i => at_member (encode m s tape) i (v_zero m)))
                       (flat_map_over (ex_stable (input_wires_circuit (S n))) (p :: r)))
        with (cons (value_at m (fun _ _ => v_zero m) (input_wires_circuit (S n))
                      (fun _ => v_zero m)
                      (fun _ i => at_member (encode m s tape) i (v_zero m))
                      (p_cycle p) (p_wire p))
                   (map_over (obs_value m (fun _ _ => v_zero m) (input_wires_circuit (S n))
                                (fun _ => v_zero m)
                                (fun _ i => at_member (encode m s tape) i (v_zero m)))
                             (flat_map_over (ex_stable (input_wires_circuit (S n))) r))).
      rewrite (d_share_experiment_value m n s tape (p_cycle p) (p_wire p) ltac:(lia)).
      change (map_over (fun i => at_member (encode m s tape) i (v_zero m)) (map_over p_wire (p :: r)))
        with (cons (at_member (encode m s tape) (p_wire p) (v_zero m))
                   (map_over (fun i => at_member (encode m s tape) i (v_zero m)) (map_over p_wire r))).
      f_equal. exact (IH Hr). }
    intros o.
    eapply eq_trans; [|eapply eq_trans; [exact (Hdist o)|]].
    + apply pr_ext. intros t. rewrite Hview. reflexivity.
    + apply pr_ext. intros t. rewrite Hview. reflexivity.
Qed.

(*| discharges: R-15-053a, R-05-004a |*)
Theorem adaptive_d_share_hides_secret :
  forall (m : Sharing) (n : nat),
    AdaptiveProbingSecure (d_share_experiment m n) ex_stable.
Proof.
  intros m n.
  destruct (d_share_experiment_probing_secure m n) as [_ [[Hq _] Hsec]].
  apply (fixed_implies_adaptive_probing_secure (d_share_experiment m n) ex_stable Hq Hsec).
Qed.

(* =========================================================================
   Separating witness: difference-only transition observations miss a
   register reuse across complementary masked shares that the full register-
   pair transition observation catches (R-15-053a).
   ========================================================================= *)

Definition diff_reuse_experiment : Experiment := {|
  x_share := gf2;
  x_prob := bit_tapes 1;
  x_circuit := register_circuit;
  x_ops := gf2_ops;
  x_secret := bool;
  x_in := fun s tape t _ =>
            if Nat.even t then andb s (bit_at tape 0)
            else andb (negb s) (bit_at tape 0);
  x_init := fun s tape _ => andb (negb s) (bit_at tape 0);
  x_order := 1
|}.

Lemma diff_reuse_wire0 : forall s tape t,
  value_at gf2 gf2_ops register_circuit
    (x_init diff_reuse_experiment s tape)
    (x_in diff_reuse_experiment s tape) t 0 =
  if Nat.even t then andb s (bit_at tape 0) else andb (negb s) (bit_at tape 0).
Proof.
  intros s tape t. unfold value_at. simpl. reflexivity.
Qed.

Lemma even_succ_bool : forall n : nat, Nat.even (S n) = negb (Nat.even n).
Proof.
  induction n as [|n IH]; [reflexivity|].
  change (Nat.even (S (S n))) with (Nat.even n).
  rewrite IH. destruct (Nat.even n); reflexivity.
Qed.

Lemma diff_reuse_wire1 : forall s tape t,
  value_at gf2 gf2_ops register_circuit
    (x_init diff_reuse_experiment s tape)
    (x_in diff_reuse_experiment s tape) t 1 =
  if Nat.even t then andb (negb s) (bit_at tape 0) else andb s (bit_at tape 0).
Proof.
  intros s tape [|t]; unfold value_at; cbn -[Nat.even]; [reflexivity|].
  rewrite even_succ_bool.
  destruct (Nat.even t); reflexivity.
Qed.

Lemma diff_reuse_delta_secret_free :
  forall s1 s2 tape p,
    Nat.ltb (p_wire p) (wire_count register_circuit) = true ->
    obs_value gf2 gf2_ops register_circuit
      (x_init diff_reuse_experiment s1 tape)
      (x_in diff_reuse_experiment s1 tape) (obs_delta (p_wire p) (p_cycle p)) =
    obs_value gf2 gf2_ops register_circuit
      (x_init diff_reuse_experiment s2 tape)
      (x_in diff_reuse_experiment s2 tape) (obs_delta (p_wire p) (p_cycle p)).
Proof.
  intros s1 s2 tape [w [|c]] Hw; cbn [obs_value p_wire p_cycle prev_cycle] in *.
  - destruct w as [|[|w]]; try discriminate Hw.
    + repeat rewrite diff_reuse_wire0. simpl.
      destruct s1; destruct s2; destruct (bit_at tape 0); reflexivity.
    + repeat rewrite diff_reuse_wire1. simpl.
      destruct s1; destruct s2; destruct (bit_at tape 0); reflexivity.
  - destruct w as [|[|w]]; try discriminate Hw.
    + repeat rewrite diff_reuse_wire0. rewrite even_succ_bool.
      destruct (Nat.even c); destruct s1; destruct s2; destruct (bit_at tape 0); reflexivity.
    + repeat rewrite diff_reuse_wire1. rewrite even_succ_bool.
      destruct (Nat.even c); destruct s1; destruct s2; destruct (bit_at tape 0); reflexivity.
Qed.

(*| discharges: R-15-053a |*)
Theorem diff_only_misses_register_reuse_that_pair_catches :
  ProbingSecure diff_reuse_experiment ex_transition_delta /\
  Leaks diff_reuse_experiment ex_transition.
Proof.
  split.
  - intros ps Hadm s1 s2.
    unfold admissible_probes in Hadm. apply andb_prop in Hadm.
    destruct Hadm as [_ Hw].
    apply identical_views_are_identically_distributed. intros tape.
    induction ps as [|p r IH]; [reflexivity|].
    simpl in Hw. apply andb_prop in Hw. destruct Hw as [Hp Hr].
    unfold x_view, probe_set. simpl.
    f_equal.
    + apply diff_reuse_delta_secret_free. exact Hp.
    + exact (IH Hr).
  - intros H.
    specialize (H (cons (probe_of 1 1) nil) eq_refl false true).
    specialize (H (cons false (cons true nil))).
    vm_compute in H. discriminate H.
Qed.

(* =========================================================================
   General glitch-robust PINI, NI, and SNI composition infrastructure:
   circuit embedding, local expansions, product counting measures, linear
   PINI, sequential/parallel PINI composition, and SNI/NI composition
   (R-05-004a, R-15-053a).
   ========================================================================= *)

Definition obs_wire (o : Obs) : nat :=
  match o with obs_at w _ => w | obs_delta w _ => w end.

Definition obs_shift (off : nat) (o : Obs) : Obs :=
  match o with
  | obs_at w t => obs_at (off + w) t
  | obs_delta w t => obs_delta (off + w) t
  end.

Definition shift_gate_1 (g : Gate) : Gate :=
  match g with
  | g_in i => g_in (2 * i)
  | g_reg s => g_reg s
  | g_op o args => g_op (2 * o) args
  end.

Definition shift_gate_2 (off : nat) (g : Gate) : Gate :=
  match g with
  | g_in i => g_in (S (2 * i))
  | g_reg s => g_reg (off + s)
  | g_op o args => g_op (S (2 * o)) (map_over (Nat.add off) args)
  end.

Definition combine_circuits (c1 c2 : Circuit) : Circuit :=
  app (map_over shift_gate_1 c1) (map_over (shift_gate_2 (wire_count c1)) c2).

Definition combine_ops {m : Sharing}
    (ops1 ops2 : nat -> list (Val m) -> Val m)
    (o : nat) (args : list (Val m)) : Val m :=
  if Nat.even o then ops1 (Nat.div2 o) args else ops2 (Nat.div2 o) args.

Lemma div2_double : forall n : nat, Nat.div2 (2 * n) = n.
Proof.
  induction n as [|n IH]; [reflexivity|].
  replace (2 * S n) with (S (S (2 * n))) by lia.
  simpl. f_equal. exact IH.
Qed.

Lemma even_double : forall n : nat, Nat.even (2 * n) = true.
Proof.
  induction n as [|n IH]; [reflexivity|].
  replace (2 * S n) with (S (S (2 * n))) by lia.
  exact IH.
Qed.

Lemma even_succ_double : forall n : nat, Nat.even (S (2 * n)) = false.
Proof.
  intros n. rewrite even_succ_bool, even_double. reflexivity.
Qed.

Lemma div2_succ_double : forall n : nat, Nat.div2 (S (2 * n)) = n.
Proof.
  induction n as [|n IH]; [reflexivity|].
  replace (S (2 * S n)) with (S (S (S (2 * n)))) by lia.
  cbn [Nat.div2]. f_equal. exact IH.
Qed.

Lemma combine_circuits_count :
  forall c1 c2 : Circuit,
    wire_count (combine_circuits c1 c2) = wire_count c1 + wire_count c2.
Proof.
  intros c1 c2. unfold combine_circuits, wire_count.
  repeat rewrite count_of_is_length.
  rewrite length_app. repeat rewrite map_over_is_map.
  rewrite length_map, length_map.
  reflexivity.
Qed.

Lemma at_member_map_over :
  forall {A B : Type} (f : A -> B) (l : list A) (w : nat) (d1 : A) (d2 : B),
    w < count_of l ->
    at_member (map_over f l) w d2 = f (at_member l w d1).
Proof.
  intros A B f l. induction l as [|x r IH]; intros [|w] d1 d2 Hw; simpl in *; try lia;
    [reflexivity | apply IH; lia].
Qed.

Lemma gate_at_combine_l :
  forall c1 c2 w,
    w < wire_count c1 ->
    gate_at (combine_circuits c1 c2) w = shift_gate_1 (gate_at c1 w).
Proof.
  intros c1 c2 w Hw. unfold gate_at, combine_circuits.
  rewrite at_member_app_l.
  - apply at_member_map_over. exact Hw.
  - rewrite map_over_is_map. repeat rewrite count_of_is_length.
    rewrite length_map. apply Nat.ltb_lt.
    unfold wire_count in Hw. rewrite count_of_is_length in Hw. exact Hw.
Qed.

Lemma at_member_app_r :
  forall {A : Type} (l1 l2 : list A) (i : nat) (d : A),
    count_of l1 <= i ->
    at_member (app l1 l2) i d = at_member l2 (i - count_of l1) d.
Proof.
  intros A l1. induction l1 as [|x r IH]; intros l2 [|i] d Hi; simpl in *; try lia;
    [reflexivity | reflexivity | apply IH; lia].
Qed.

Lemma gate_at_combine_r :
  forall c1 c2 w,
    w < wire_count c2 ->
    gate_at (combine_circuits c1 c2) (wire_count c1 + w) =
    shift_gate_2 (wire_count c1) (gate_at c2 w).
Proof.
  intros c1 c2 w Hw. unfold gate_at, combine_circuits.
  assert (Hlen : count_of (map_over shift_gate_1 c1) = wire_count c1).
  { unfold wire_count. rewrite count_of_is_length, map_over_is_map, length_map, count_of_is_length. reflexivity. }
  rewrite at_member_app_r by lia.
  rewrite Hlen, Nat.add_comm, Nat.add_sub.
  apply at_member_map_over. exact Hw.
Qed.

Lemma wf_from_app :
  forall l1 l2 total j,
    wf_from total j (app l1 l2) =
    andb (wf_from total j l1) (wf_from total (j + count_of l1) l2).
Proof.
  induction l1 as [|g r IH]; intros l2 total j; simpl.
  - rewrite add_zero_r_nat. reflexivity.
  - rewrite IH, add_succ_r_nat. destruct (gate_well_formed total j g); reflexivity.
Qed.

Lemma all_of_map_over :
  forall {A B : Type} (p : B -> bool) (f : A -> B) (l : list A),
    all_of p (map_over f l) = all_of (fun a => p (f a)) l.
Proof.
  intros A B p f l. induction l as [|x r IH]; simpl; [reflexivity|].
  rewrite IH. reflexivity.
Qed.

Lemma combine_circuits_well_formed :
  forall c1 c2 : Circuit,
    well_formed c1 = true -> well_formed c2 = true ->
    well_formed (combine_circuits c1 c2) = true.
Proof.
  intros c1 c2 H1 H2. unfold well_formed in *.
  rewrite combine_circuits_count. unfold combine_circuits.
  rewrite wf_from_app.
  assert (Hlen1 : count_of (map_over shift_gate_1 c1) = wire_count c1).
  { unfold wire_count. repeat rewrite count_of_is_length.
    rewrite map_over_is_map, length_map. reflexivity. }
  rewrite Hlen1.
  apply andb_true_intro. split.
  - assert (Hgen : forall l total j,
      total <= wire_count c1 + wire_count c2 ->
      wf_from (wire_count c1) j l = true ->
      wf_from (wire_count c1 + wire_count c2) j (map_over shift_gate_1 l) = true).
    { clear. induction l as [|g r IH]; intros total j Htot Hg; simpl in *; [reflexivity|].
      apply andb_prop in Hg. destruct Hg as [Hg Hr].
      apply andb_true_intro. split; [|apply IH with (total := total); assumption].
      destruct g as [i|s|o args]; simpl in *; [reflexivity| |].
      - apply Nat.ltb_lt in Hg. apply Nat.ltb_lt. lia.
      - exact Hg. }
    exact (Hgen c1 (wire_count c1) 0 ltac:(lia) H1).
  - assert (Hgen2 : forall l off j,
      wf_from (wire_count c2) j l = true ->
      wf_from (off + wire_count c2) (off + j) (map_over (shift_gate_2 off) l) = true).
    { clear. induction l as [|g r IH]; intros off j Hg; simpl in *; [reflexivity|].
      apply andb_prop in Hg. destruct Hg as [Hg Hr].
      apply andb_true_intro. split.
      - destruct g as [i|s|o args]; simpl in *; [reflexivity| |].
        + apply Nat.ltb_lt in Hg. apply Nat.ltb_lt. lia.
        + rewrite all_of_map_over.
          apply (all_of_mono (fun a => Nat.ltb a j)); [|exact Hg].
          intros a Ha. apply Nat.ltb_lt in Ha. apply Nat.ltb_lt. lia.
      - rewrite <- add_succ_r_nat. apply IH. exact Hr. }
    replace (0 + wire_count c1) with (wire_count c1 + 0) by lia.
    exact (Hgen2 c2 (wire_count c1) 0 H2).
Qed.

Lemma stable_sources_combine_l :
  forall fuel c1 c2 w,
    well_formed c1 = true ->
    w < wire_count c1 ->
    w < fuel ->
    stable_sources (combine_circuits c1 c2) fuel w =
    stable_sources c1 fuel w.
Proof.
  induction fuel as [|f IH]; intros c1 c2 w Hwf Hw Hf; [lia|].
  simpl. rewrite gate_at_combine_l by exact Hw.
  destruct (gate_at c1 w) as [i|s|o args] eqn:Eg; try reflexivity.
  pose proof (well_formed_gate_reads_earlier_wires c1 w o args Hwf (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hargs.
  clear Eg. induction args as [|a r IHa]; simpl; [reflexivity|].
  simpl in Hargs. apply andb_prop in Hargs. destruct Hargs as [Ha Hr].
  apply Nat.ltb_lt in Ha.
  rewrite (IH c1 c2 a Hwf ltac:(lia) ltac:(lia)).
  f_equal. apply IHa. exact Hr.
Qed.

Lemma flat_map_over_map_over :
  forall {A B C : Type} (f : B -> list C) (g : A -> B) (l : list A),
    flat_map_over f (map_over g l) = flat_map_over (fun a => f (g a)) l.
Proof.
  intros A B C f g l. induction l as [|x r IH]; simpl; [reflexivity|].
  rewrite IH. reflexivity.
Qed.

Lemma map_over_flat_map_over :
  forall {A B C : Type} (f : B -> C) (g : A -> list B) (l : list A),
    map_over f (flat_map_over g l) = flat_map_over (fun a => map_over f (g a)) l.
Proof.
  intros A B C f g l. induction l as [|x r IH]; simpl; [reflexivity|].
  rewrite map_over_is_map, map_app, <- map_over_is_map, <- map_over_is_map, IH.
  reflexivity.
Qed.

Lemma stable_sources_combine_r :
  forall fuel c1 c2 w,
    well_formed c2 = true ->
    w < wire_count c2 ->
    w < fuel ->
    stable_sources (combine_circuits c1 c2) fuel (wire_count c1 + w) =
    map_over (Nat.add (wire_count c1)) (stable_sources c2 fuel w).
Proof.
  induction fuel as [|f IH]; intros c1 c2 w Hwf Hw Hf; [lia|].
  simpl. rewrite gate_at_combine_r by exact Hw.
  destruct (gate_at c2 w) as [i|s|o args] eqn:Eg; try reflexivity.
  simpl. rewrite flat_map_over_map_over, map_over_flat_map_over.
  pose proof (well_formed_gate_reads_earlier_wires c2 w o args Hwf (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hargs.
  clear Eg. induction args as [|a r IHa]; simpl; [reflexivity|].
  simpl in Hargs. apply andb_prop in Hargs. destruct Hargs as [Ha Hr].
  apply Nat.ltb_lt in Ha.
  rewrite (IH c1 c2 a Hwf ltac:(lia) ltac:(lia)).
  f_equal. apply IHa. exact Hr.
Qed.

Lemma stable_sources_fuel_irrelevant :
  forall n c w f1 f2,
    well_formed c = true ->
    w < wire_count c ->
    w < n -> w < f1 -> w < f2 ->
    stable_sources c f1 w = stable_sources c f2 w.
Proof.
  induction n as [|n IH]; intros c w f1 f2 Hwf Hw Hn Hf1 Hf2; [lia|].
  destruct f1 as [|g1]; [lia|]. destruct f2 as [|g2]; [lia|].
  simpl. destruct (gate_at c w) as [i|s|o args] eqn:Eg; try reflexivity.
  pose proof (well_formed_gate_reads_earlier_wires c w o args Hwf (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hargs.
  clear Eg. induction args as [|a r IHa]; simpl; [reflexivity|].
  simpl in Hargs. apply andb_prop in Hargs. destruct Hargs as [Ha Hr].
  apply Nat.ltb_lt in Ha.
  rewrite (IH c a g1 g2 Hwf ltac:(lia) ltac:(lia) ltac:(lia) ltac:(lia)).
  f_equal. apply IHa. exact Hr.
Qed.

(* Local expansions depend only on stable sources, the probed wire, and
   the cycle, so circuit embedding and domain separation transport across
   them uniformly. *)
Record LocalExpansion (E : Expansion) : Prop := {
  le_left_embed : forall c1 c2 p,
    well_formed c1 = true -> well_formed c2 = true ->
    p_wire p < wire_count c1 ->
    E (combine_circuits c1 c2) p = E c1 p;
  le_right_embed : forall c1 c2 p,
    well_formed c1 = true -> well_formed c2 = true ->
    p_wire p < wire_count c2 ->
    E (combine_circuits c1 c2) (probe_of (wire_count c1 + p_wire p) (p_cycle p)) =
    map_over (obs_shift (wire_count c1)) (E c2 p);
  le_domain : forall c (dom : nat -> nat) p o,
    well_formed c = true -> p_wire p < wire_count c ->
    (forall w, w < wire_count c ->
       match gate_at c w with
       | g_in _ => True
       | g_reg s => dom s = dom w
       | g_op _ args => all_of (fun a => Nat.eqb (dom a) (dom w)) args = true
       end) ->
    ProofSupport.Member o (E c p) ->
    obs_wire o < wire_count c /\ dom (obs_wire o) = dom (p_wire p)
}.

Lemma stable_sources_domain :
  forall fuel c (dom : nat -> nat) w s,
    well_formed c = true ->
    w < wire_count c ->
    (forall u, u < wire_count c ->
       match gate_at c u with
       | g_in _ => True
       | g_reg r => dom r = dom u
       | g_op _ args => all_of (fun a => Nat.eqb (dom a) (dom u)) args = true
       end) ->
    ProofSupport.Member s (stable_sources c fuel w) ->
    s < wire_count c /\ dom s = dom w.
Proof.
  induction fuel as [|f IH]; intros c dom w s Hwf Hw Hdom Hs; simpl in *.
  - destruct Hs as [<-|[]]. split; [exact Hw | reflexivity].
  - destruct (gate_at c w) as [i|r|o args] eqn:Eg; simpl in Hs.
    + destruct Hs as [<-|[]]. split; [exact Hw | reflexivity].
    + destruct Hs as [<-|[]]. split; [exact Hw | reflexivity].
    + pose proof (well_formed_gate_reads_earlier_wires c w o args Hwf (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hargs.
      pose proof (Hdom w Hw) as Hwdom. rewrite Eg in Hwdom.
      clear Eg. induction args as [|a rest IHa]; simpl in Hs; [contradiction|].
      simpl in Hargs, Hwdom.
      apply andb_prop in Hargs. destruct Hargs as [Ha Hrest].
      apply andb_prop in Hwdom. destruct Hwdom as [Hadom Hrestdom].
      apply Nat.ltb_lt in Ha. apply Nat.eqb_eq in Hadom.
      assert (Hmem_app : forall {A} (l1 l2 : list A) (z : A),
        ProofSupport.Member z (app l1 l2) ->
        ProofSupport.Member z l1 \/ ProofSupport.Member z l2).
      { clear. induction l1 as [|x r1 IHl]; intros l2 z Hz; simpl in *.
        - right. exact Hz.
        - destruct Hz as [->|Hz]; [left; left; reflexivity|].
          destruct (IHl l2 z Hz); [left; right; assumption | right; assumption]. }
      destruct (Hmem_app _ _ _ _ Hs) as [Hs1 | Hs2].
      * destruct (IH c dom a s Hwf ltac:(lia) Hdom Hs1) as [Hs_lt Hs_dom].
        split; [exact Hs_lt | rewrite Hs_dom; exact Hadom].
      * apply IHa; assumption.
Qed.

Lemma member_map_over_inv :
  forall {A B : Type} (f : A -> B) (l : list A) (y : B),
    ProofSupport.Member y (map_over f l) ->
    exists x, ProofSupport.Member x l /\ f x = y.
Proof.
  intros A B f l. induction l as [|a r IH]; intros y Hy; simpl in *; [contradiction|].
  destruct Hy as [Heq | Hy].
  - exists a. split; [left; reflexivity | symmetry; exact Heq].
  - destruct (IH y Hy) as [x [Hx <-]]. exists x. split; [right; exact Hx | reflexivity].
Qed.

Lemma member_flat_map_over_inv :
  forall {A B : Type} (f : A -> list B) (l : list A) (y : B),
    ProofSupport.Member y (flat_map_over f l) ->
    exists x, ProofSupport.Member x l /\ ProofSupport.Member y (f x).
Proof.
  intros A B f l. induction l as [|a r IH]; intros y Hy; simpl in *; [contradiction|].
  assert (Happ : forall l1 l2 : list B,
    ProofSupport.Member y (app l1 l2) ->
    ProofSupport.Member y l1 \/ ProofSupport.Member y l2).
  { clear. induction l1 as [|u r1 IH1]; intros l2 H; simpl in *; [right; exact H|].
    destruct H as [->|H]; [left; left; reflexivity|].
    destruct (IH1 l2 H); [left; right; assumption | right; assumption]. }
  destruct (Happ _ _ Hy) as [H1 | H2].
  - exists a. split; [left; reflexivity | exact H1].
  - destruct (IH y H2) as [x [Hx Hfx]]. exists x. split; [right; exact Hx | exact Hfx].
Qed.

Lemma ex_stable_is_local : LocalExpansion ex_stable.
Proof.
  constructor.
  - intros. reflexivity.
  - intros. reflexivity.
  - intros c dom [w t] o Hwf Hw _ Ho. simpl in *.
    destruct Ho as [->|[]]. split; [exact Hw | reflexivity].
Qed.

Lemma ex_transition_is_local : LocalExpansion ex_transition.
Proof.
  constructor.
  - intros. reflexivity.
  - intros. reflexivity.
  - intros c dom [w t] o Hwf Hw _ Ho. simpl in *.
    destruct Ho as [->|[->|[]]]; split; [exact Hw | reflexivity | exact Hw | reflexivity].
Qed.

Lemma ex_transition_delta_is_local : LocalExpansion ex_transition_delta.
Proof.
  constructor.
  - intros. reflexivity.
  - intros. reflexivity.
  - intros c dom [w t] o Hwf Hw _ Ho. simpl in *.
    destruct Ho as [->|[]]. split; [exact Hw | reflexivity].
Qed.

Lemma ex_glitch_is_local : LocalExpansion ex_glitch.
Proof.
  constructor.
  - intros c1 c2 [w t] H1 H2 Hw. simpl in Hw. unfold ex_glitch. simpl.
    rewrite combine_circuits_count.
    rewrite (stable_sources_fuel_irrelevant (S (wire_count c1 + wire_count c2))
               (combine_circuits c1 c2) w (wire_count c1 + wire_count c2) (wire_count c1)
               (combine_circuits_well_formed c1 c2 H1 H2)
               ltac:(rewrite combine_circuits_count; lia)
               ltac:(lia) ltac:(lia) ltac:(lia)).
    rewrite stable_sources_combine_l by (assumption || lia). reflexivity.
  - intros c1 c2 [w t] H1 H2 Hw. simpl in Hw. unfold ex_glitch. simpl.
    rewrite combine_circuits_count.
    rewrite (stable_sources_combine_r (wire_count c1 + wire_count c2) c1 c2 w H2 Hw ltac:(lia)).
    rewrite (stable_sources_fuel_irrelevant (S (wire_count c2))
               c2 w (wire_count c1 + wire_count c2) (wire_count c2)
               H2 Hw ltac:(lia) ltac:(lia) ltac:(lia)).
    rewrite map_over_compose, map_over_compose. reflexivity.
  - intros c dom [w t] o Hwf Hw Hdom Ho. simpl in Hw. unfold ex_glitch in Ho. simpl in Ho.
    apply member_map_over_inv in Ho. destruct Ho as [s [Hs <-]].
    exact (stable_sources_domain (wire_count c) c dom w s Hwf Hw Hdom Hs).
Qed.

Lemma ex_robust_is_local : LocalExpansion ex_robust.
Proof.
  constructor.
  - intros c1 c2 [w t] H1 H2 Hw. simpl in Hw. unfold ex_robust. simpl.
    rewrite combine_circuits_count.
    rewrite (stable_sources_fuel_irrelevant (S (wire_count c1 + wire_count c2))
               (combine_circuits c1 c2) w (wire_count c1 + wire_count c2) (wire_count c1)
               (combine_circuits_well_formed c1 c2 H1 H2)
               ltac:(rewrite combine_circuits_count; lia)
               ltac:(lia) ltac:(lia) ltac:(lia)).
    rewrite stable_sources_combine_l by (assumption || lia). reflexivity.
  - intros c1 c2 [w t] H1 H2 Hw. simpl in Hw. unfold ex_robust. simpl.
    rewrite combine_circuits_count.
    rewrite (stable_sources_combine_r (wire_count c1 + wire_count c2) c1 c2 w H2 Hw ltac:(lia)).
    rewrite (stable_sources_fuel_irrelevant (S (wire_count c2))
               c2 w (wire_count c1 + wire_count c2) (wire_count c2)
               H2 Hw ltac:(lia) ltac:(lia) ltac:(lia)).
    rewrite flat_map_over_map_over, map_over_flat_map_over. reflexivity.
  - intros c dom [w t] o Hwf Hw Hdom Ho. simpl in Hw. unfold ex_robust in Ho. simpl in Ho.
    apply member_flat_map_over_inv in Ho. destruct Ho as [s [Hs Ho]].
    simpl in Ho. destruct Ho as [-> | [-> | []]];
      exact (stable_sources_domain (wire_count c) c dom w s Hwf Hw Hdom Hs).
Qed.

Definition witness_LocalExpansion : LocalExpansion ex_robust := ex_robust_is_local.

(* -------------------------------------------------------------------------
   Share-domain-separated (linear / sharewise) gadgets are t-PINI for all t
   under any LocalExpansion (including ex_robust).
   ------------------------------------------------------------------------- *)

Record ShareDomainSeparated (g : Gadget) (dom : nat -> nat) : Prop := {
  sds_bound : forall w, w < wire_count (gd_circuit g) -> dom w < gd_shares g;
  sds_out : forall k, k < gd_shares g -> dom (gd_out g k) = k;
  sds_out_wire : forall k, k < gd_shares g -> gd_out g k < wire_count (gd_circuit g);
  sds_in : forall w i a b tape t,
    w < wire_count (gd_circuit g) -> gate_at (gd_circuit g) w = g_in i ->
    (forall j, j < gd_inputs g -> a j (dom w) = b j (dom w)) ->
    gd_assign g a tape t i = gd_assign g b tape t i;
  sds_start : forall w a b tape,
    w < wire_count (gd_circuit g) ->
    (forall j, j < gd_inputs g -> a j (dom w) = b j (dom w)) ->
    gd_start g a tape w = gd_start g b tape w;
  sds_gate : forall w,
    w < wire_count (gd_circuit g) ->
    match gate_at (gd_circuit g) w with
    | g_in _ => True
    | g_reg s => dom s = dom w
    | g_op _ args => all_of (fun a => Nat.eqb (dom a) (dom w)) args = true
    end
}.

Definition witness_ShareDomainSeparated :
  ShareDomainSeparated copy_gadget (fun w => w).
Proof.
  constructor.
  - intros w Hw. simpl in Hw. exact Hw.
  - intros k Hk. reflexivity.
  - intros k Hk. simpl in *. exact Hk.
  - intros w i a b tape t Hw Eg Hag.
    unfold wire_count, gate_at in Hw, Eg. simpl in Hw, Eg.
    destruct w as [|[|w]]; [| |lia]; inversion Eg; subst; apply Hag; simpl; lia.
  - intros w a b tape Hw Hag. reflexivity.
  - intros w Hw. destruct w as [|[|w]]; simpl; exact I.
Defined.

Lemma sds_eval_depends_only_on_domain :
  forall (g : Gadget) (dom : nat -> nat) (a b : ShareMatrix g)
         (tape : Tape (gd_prob g)) (fuel t w : nat),
    well_formed (gd_circuit g) = true ->
    ShareDomainSeparated g dom ->
    w < wire_count (gd_circuit g) ->
    (forall j, j < gd_inputs g -> a j (dom w) = b j (dom w)) ->
    (forall u, u < wire_count (gd_circuit g) -> dom u = dom w ->
       regs_at (gd_share g) (gd_ops g) (gd_circuit g)
               (gd_start g a tape) (gd_assign g a tape) t u =
       regs_at (gd_share g) (gd_ops g) (gd_circuit g)
               (gd_start g b tape) (gd_assign g b tape) t u) ->
    eval_wire (gd_share g) (gd_ops g) (gd_circuit g)
      (regs_at (gd_share g) (gd_ops g) (gd_circuit g)
         (gd_start g a tape) (gd_assign g a tape) t)
      (gd_assign g a tape t) fuel w =
    eval_wire (gd_share g) (gd_ops g) (gd_circuit g)
      (regs_at (gd_share g) (gd_ops g) (gd_circuit g)
         (gd_start g b tape) (gd_assign g b tape) t)
      (gd_assign g b tape t) fuel w.
Proof.
  intros g dom a b tape fuel.
  induction fuel as [|f IH]; intros t w Hwf Hsds Hw Hag Hregs; [reflexivity|].
  simpl. destruct (gate_at (gd_circuit g) w) as [i|s|o args] eqn:Eg.
  - exact (sds_in g dom Hsds w i a b tape t Hw Eg Hag).
  - apply Hregs; [exact Hw | reflexivity].
  - f_equal. apply map_over_ext_nat. intros u Hu.
    pose proof (well_formed_gate_reads_earlier_wires _ w o args Hwf (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hargs.
    pose proof (all_of_mem_nat (fun x => Nat.ltb x w) args u Hargs Hu) as Huw.
    apply Nat.ltb_lt in Huw.
    pose proof (sds_gate g dom Hsds w Hw) as Hdomw. rewrite Eg in Hdomw.
    pose proof (all_of_mem_nat (fun x => Nat.eqb (dom x) (dom w)) args u Hdomw Hu) as Hudom.
    apply Nat.eqb_eq in Hudom.
    apply IH; [exact Hwf | exact Hsds | lia | rewrite Hudom; exact Hag |].
    intros v Hv Hvd. apply Hregs; [exact Hv | rewrite Hvd; exact Hudom].
Qed.

Lemma sds_regs_depend_only_on_domain :
  forall (g : Gadget) (dom : nat -> nat) (a b : ShareMatrix g)
         (tape : Tape (gd_prob g)) (t w : nat),
    well_formed (gd_circuit g) = true ->
    ShareDomainSeparated g dom ->
    w < wire_count (gd_circuit g) ->
    (forall j, j < gd_inputs g -> a j (dom w) = b j (dom w)) ->
    regs_at (gd_share g) (gd_ops g) (gd_circuit g)
      (gd_start g a tape) (gd_assign g a tape) t w =
    regs_at (gd_share g) (gd_ops g) (gd_circuit g)
      (gd_start g b tape) (gd_assign g b tape) t w.
Proof.
  intros g dom a b tape t.
  induction t as [|t IH]; intros w Hwf Hsds Hw Hag.
  - simpl. exact (sds_start g dom Hsds w a b tape Hw Hag).
  - simpl. unfold step_regs.
    destruct (gate_at (gd_circuit g) w) as [i|s|o args] eqn:Eg.
    + apply IH; assumption.
    + pose proof (well_formed_register_source_exists _ w s Hwf (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hs.
      apply Nat.ltb_lt in Hs.
      pose proof (sds_gate g dom Hsds w Hw) as Hdomw. rewrite Eg in Hdomw.
      apply (sds_eval_depends_only_on_domain g dom a b tape (wire_count (gd_circuit g)) t s Hwf Hsds Hs).
      * rewrite Hdomw. exact Hag.
      * intros u Hu Hud. apply IH; [exact Hwf | exact Hsds | exact Hu | rewrite Hud, Hdomw; exact Hag].
    + apply IH; assumption.
Qed.

Lemma sds_value_depends_only_on_domain :
  forall (g : Gadget) (dom : nat -> nat) (a b : ShareMatrix g)
         (tape : Tape (gd_prob g)) (t w : nat),
    well_formed (gd_circuit g) = true ->
    ShareDomainSeparated g dom ->
    w < wire_count (gd_circuit g) ->
    (forall j, j < gd_inputs g -> a j (dom w) = b j (dom w)) ->
    gd_value g a tape t w = gd_value g b tape t w.
Proof.
  intros g dom a b tape t w Hwf Hsds Hw Hag.
  unfold gd_value, value_at.
  apply (sds_eval_depends_only_on_domain g dom a b tape (wire_count (gd_circuit g)) t w Hwf Hsds Hw Hag).
  intros u Hu Hud. apply (sds_regs_depend_only_on_domain g dom a b tape t u Hwf Hsds Hu).
  rewrite Hud. exact Hag.
Qed.

Lemma card_in_le_list :
  forall (g : Gadget) (l : list nat) (j : nat),
    count_of (filter_of (fun k => mem_nat k l) (upto (gd_shares g))) <= count_of l.
Proof.
  intros g l j.
  assert (Hgen : forall (u : list nat),
    NoDup u -> count_of (filter_of (fun k => mem_nat k l) u) <= count_of l).
  { clear. induction l as [|x r IH]; intros u Hnodup.
    - induction u as [|a ua IHu]; simpl; [lia|].
      inversion Hnodup; subst. apply IHu. exact H2.
    - assert (Hsub : count_of (filter_of (fun k => mem_nat k (x :: r)) u) <=
                     S (count_of (filter_of (fun k => mem_nat k r) u))).
      { clear -Hnodup. induction u as [|a ua IHu]; simpl; [lia|].
        inversion Hnodup; subst.
        destruct (Nat.eqb a x) eqn:Eax.
        + apply eqb_sound_nat in Eax. subst a. simpl.
          assert (Hnot : forall z, In z ua -> z <> x) by (intros z Hz E; subst; contradiction).
          assert (Hext : filter_of (fun k => orb (Nat.eqb k x) (mem_nat k r)) ua =
                         filter_of (fun k => mem_nat k r) ua).
          { clear -Hnot. induction ua as [|y ur IHu2]; simpl; [reflexivity|].
            destruct (Nat.eqb y x) eqn:Eyx.
            - exfalso. apply (Hnot y (or_introl eq_refl)). apply eqb_sound_nat. exact Eyx.
            - simpl. destruct (mem_nat y r); rewrite IHu2 by (intros z Hz; apply (Hnot z (or_intror Hz))); reflexivity. }
          rewrite Hext.
          destruct (mem_nat x r); simpl; repeat rewrite count_of_is_length in *; cbn [length] in *; lia.
        + simpl. destruct (mem_nat a r); specialize (IHu H2); simpl in *;
            repeat rewrite count_of_is_length in *; cbn [length] in *; lia. }
      specialize (IH u Hnodup). simpl in *. repeat rewrite count_of_is_length in *; cbn [length] in *; lia. }
  apply Hgen.
  (* upto n is NoDup *)
  clear. generalize (gd_shares g) as n. intros n.
  assert (Hnodup : forall m, NoDup (upto m)).
  { induction m as [|m IHm]; simpl; [constructor|].
    change (upto (S m)) with (ProofSupport.upto (S m)). simpl.
    assert (Happ_nodup : forall l1 (z : nat), NoDup l1 -> ~ In z l1 -> NoDup (app l1 (z :: nil))).
    { clear. induction l1 as [|a r IH1]; intros z Hn Hnin; simpl.
      - constructor; [intros []|constructor].
      - inversion Hn; subst. constructor.
        + intros Hin. apply in_app_or in Hin. destruct Hin as [Ha1|[Ha2|[]]]; auto.
          subst. apply Hnin. left. reflexivity.
        + apply IH1; [exact H2 | intros Hz; apply Hnin; right; exact Hz]. }
    apply Happ_nodup; [exact IHm|].
    assert (Hlt : forall k z, In z (ProofSupport.upto k) -> z < k).
    { clear. induction k as [|k IHk]; intros z Hz; simpl in *; [contradiction|].
      apply in_app_or in Hz. destruct Hz as [Hz|[<-|[]]]; [specialize (IHk z Hz); lia | lia]. }
    intros Hin. pose proof (Hlt m m Hin). lia. }
  apply Hnodup.
Qed.

Lemma support_filter_true :
  forall {A : Type} (p : A -> bool) (l : list A) (x : A),
    ProofSupport.Member x (filter_of p l) -> p x = true.
Proof.
  intros A p l x. induction l as [|y r IH]; simpl; [contradiction|].
  destruct (p y) eqn:Epy; simpl; intros H; [|exact (IH H)].
  destruct H as [->|H]; [exact Epy | exact (IH H)].
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem linear_gadget_is_pini :
  forall (g : Gadget) (dom : nat -> nat) (E : Expansion) (d : nat),
    well_formed (gd_circuit g) = true ->
    ShareDomainSeparated g dom ->
    LocalExpansion E ->
    PINI g E d.
Proof.
  intros g dom E d Hwf Hsds Hloc ps B Hw _.
  set (doms := map_over (fun p => dom (p_wire p)) ps).
  exists (fun _ k => mem_nat k doms). split.
  - intros j _. unfold card_in.
    apply Nat.leb_le.
    pose proof (card_in_le_list g doms j) as Hle.
    assert (Hlen : count_of doms = count_of ps).
    { unfold doms. clear. induction ps as [|p r IH]; simpl; [reflexivity | f_equal; exact IH]. }
    lia.
  - intros a b Hagree.
    apply identical_views_are_identically_distributed. intros tape.
    unfold split_view. f_equal.
    + unfold internal_view, probe_set.
      apply support_map_ext. intros o Ho.
      apply member_flat_map_over_inv in Ho. destruct Ho as [p [Hp Ho]].
      assert (Hpw : p_wire p < wire_count (gd_circuit g)).
      { clear -Hw Hp. unfold wires_exist in Hw.
        induction ps as [|q r IH]; simpl in *; [contradiction|].
        apply andb_prop in Hw. destruct Hw as [Hq Hr].
        destruct Hp as [->|Hp]; [apply Nat.ltb_lt; exact Hq | apply IH; assumption]. }
      destruct (le_domain E Hloc (gd_circuit g) dom p o Hwf Hpw (sds_gate g dom Hsds) Ho) as [How Hdomo].
      assert (Hdom_in : mem_nat (dom (obs_wire o)) doms = true).
      { rewrite Hdomo. unfold doms. clear -Hp.
        induction ps as [|q r IH]; simpl in *; [contradiction|].
        destruct Hp as [->|Hp]; simpl; [rewrite eqb_refl_nat; reflexivity|].
        rewrite (IH Hp). destruct (Nat.eqb (dom (p_wire p)) (dom (p_wire q))); reflexivity. }
      assert (Hag_o : forall j, j < gd_inputs g -> a j (dom (obs_wire o)) = b j (dom (obs_wire o))).
      { intros j Hj. apply Hagree; [apply Nat.ltb_lt; exact Hj | |].
        - apply Nat.ltb_lt. exact (sds_bound g dom Hsds (obs_wire o) How).
        - unfold union_shares. rewrite Hdom_in. reflexivity. }
      destruct o as [w t | w t]; simpl in *.
      * apply (sds_value_depends_only_on_domain g dom a b tape t w Hwf Hsds How Hag_o).
      * f_equal; apply (sds_value_depends_only_on_domain g dom a b tape _ w Hwf Hsds How Hag_o).
    + unfold output_view, selected_outputs.
      apply support_map_ext. intros k Hk.
      pose proof (support_filter_true B (upto (gd_shares g)) k Hk) as HBk.
      apply support_filter_member in Hk.
      assert (Hk_lt : k < gd_shares g).
      { revert Hk. generalize (gd_shares g) as n. intros n Hk.
        unfold upto in *.
        induction n as [|n IH]; simpl in *; [contradiction|].
        assert (Happ : forall l1 l2 : list nat,
          ProofSupport.Member k (app l1 l2) ->
          ProofSupport.Member k l1 \/ ProofSupport.Member k l2).
        { clear. induction l1 as [|x r1 IH1]; intros l2 H; simpl in *; [right; exact H|].
          destruct H as [->|H]; [left; left; reflexivity|].
          destruct (IH1 l2 H); [left; right; assumption | right; assumption]. }
        destruct (Happ _ _ Hk) as [H1|[->|[]]]; [specialize (IH H1); lia | lia]. }
      apply (sds_value_depends_only_on_domain g dom a b tape (gd_read g) (gd_out g k)
               Hwf Hsds (sds_out_wire g dom Hsds k Hk_lt)).
      intros j Hj. rewrite (sds_out g dom Hsds k Hk_lt).
      apply Hagree; [apply Nat.ltb_lt; exact Hj | apply Nat.ltb_lt; exact Hk_lt |].
      unfold union_shares. rewrite HBk. destruct (mem_nat k doms); reflexivity.
Qed.

(* =========================================================================
   Counting product measures and general sequential/parallel PINI, NI, and
   SNI composition theorems (R-05-004a, R-15-053a).
   ========================================================================= *)

Definition HasCountingMass (p : Probability) : Prop :=
  forall (O : Type) (oeqb : O -> O -> bool) (f g : Tape p -> O),
    SameDistribution p O oeqb f g ->
    SameDistribution (counting (Tape p) (tape_enum p)) O oeqb f g.

Lemma counting_has_counting_mass :
  forall (T : Type) (enum : list T), HasCountingMass (counting T enum).
Proof. intros T enum O oeqb f g H. exact H. Qed.

Definition list_prod {A B : Type} (l1 : list A) (l2 : list B) : list (A * B) :=
  flat_map_over (fun a => map_over (fun b => (a, b)) l2) l1.

Lemma count_of_app_eq :
  forall {A : Type} (l1 l2 : list A),
    count_of (app l1 l2) = count_of l1 + count_of l2.
Proof.
  intros A l1 l2. repeat rewrite count_of_is_length. apply length_app.
Qed.

Lemma filter_of_app_eq :
  forall {A : Type} (p : A -> bool) (l1 l2 : list A),
    filter_of p (app l1 l2) = app (filter_of p l1) (filter_of p l2).
Proof.
  intros A p l1 l2. induction l1 as [|x r IH]; simpl; [reflexivity|].
  destruct (p x); simpl; rewrite IH; reflexivity.
Qed.

Lemma count_filter_map_over :
  forall {A B : Type} (f : A -> B) (q : B -> bool) (l : list A),
    count_of (filter_of q (map_over f l)) = count_of (filter_of (fun a => q (f a)) l).
Proof.
  intros A B f q l. symmetry. apply count_filter_image.
Qed.

Fixpoint sum_nat_list (l : list nat) : nat :=
  match l with nil => 0 | x :: r => x + sum_nat_list r end.

Lemma counting_prod_right :
  forall (A B : Type) (l1 : list A) (l2 : list B)
         (O : Type) (oeqb : O -> O -> bool) (f g : A * B -> O),
    (forall a : A, ProofSupport.Member a l1 ->
       SameDistribution (counting B l2) O oeqb (fun b => f (a, b)) (fun b => g (a, b))) ->
    SameDistribution (counting (A * B) (list_prod l1 l2)) O oeqb f g.
Proof.
  intros A B l1 l2 O oeqb f g H o.
  repeat rewrite counting_pr.
  unfold list_prod. induction l1 as [|a r IH]; cbn [flat_map_over]; [reflexivity|].
  repeat rewrite filter_of_app_eq, count_of_app_eq.
  rewrite count_filter_map_over, count_filter_map_over.
  pose proof (H a (or_introl eq_refl) o) as Ha.
  repeat rewrite counting_pr in Ha.
  change (Tape (counting B l2)) with B in Ha.
  rewrite Ha. f_equal. apply IH.
  intros x Hx. apply H. right. exact Hx.
Qed.

Lemma count_prod_swap_sum :
  forall (A B : Type) (l1 : list A) (l2 : list B) (q : A * B -> bool),
    count_of (filter_of q (list_prod l1 l2)) =
    sum_nat_list (map_over (fun b => count_of (filter_of (fun a => q (a, b)) l1)) l2).
Proof.
  intros A B l1 l2 q. unfold list_prod. induction l1 as [|a r IH]; cbn [flat_map_over].
  - clear. induction l2 as [|b r2 IH2]; simpl; [reflexivity | exact IH2].
  - rewrite filter_of_app_eq, count_of_app_eq, count_filter_map_over, IH.
    clear. induction l2 as [|b r2 IH2]; [reflexivity|].
    unfold count_of, map_over, filter_of in *. simpl in *.
    destruct (q (a, b)); simpl in *; lia.
Qed.

Lemma counting_prod_left :
  forall (A B : Type) (l1 : list A) (l2 : list B)
         (O : Type) (oeqb : O -> O -> bool) (f g : A * B -> O),
    (forall b : B, ProofSupport.Member b l2 ->
       SameDistribution (counting A l1) O oeqb (fun a => f (a, b)) (fun a => g (a, b))) ->
    SameDistribution (counting (A * B) (list_prod l1 l2)) O oeqb f g.
Proof.
  intros A B l1 l2 O oeqb f g H o.
  repeat rewrite counting_pr.
  rewrite count_prod_swap_sum, count_prod_swap_sum.
  assert (Hext : map_over (fun b => count_of (filter_of (fun a => oeqb (f (a, b)) o) l1)) l2 =
                 map_over (fun b => count_of (filter_of (fun a => oeqb (g (a, b)) o) l1)) l2).
  { apply support_map_ext. intros b Hb.
    pose proof (H b Hb o) as Hb0. repeat rewrite counting_pr in Hb0.
    change (Tape (counting A l1)) with A in Hb0. exact Hb0. }
  rewrite Hext. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Combined circuit evaluation for sequential and parallel gadget composition.
   ------------------------------------------------------------------------- *)

Definition combine_assign {m : Sharing}
    (asg1 asg2 : nat -> nat -> Val m) (cyc i : nat) : Val m :=
  if Nat.even i then asg1 cyc (Nat.div2 i) else asg2 cyc (Nat.div2 i).

Definition combine_start {m : Sharing}
    (n1 : nat) (st1 st2 : nat -> Val m) (w : nat) : Val m :=
  if Nat.ltb w n1 then st1 w else st2 (w - n1).

Lemma eval_wire_combine_l :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c1 c2 : Circuit) (regs1 regs : nat -> Val m)
         (asg1 asg2 : nat -> nat -> Val m) (cyc fuel w : nat),
    well_formed c1 = true ->
    w < wire_count c1 ->
    (forall u, u < wire_count c1 -> regs u = regs1 u) ->
    eval_wire m (combine_ops ops1 ops2) (combine_circuits c1 c2)
      regs (combine_assign asg1 asg2 cyc) fuel w =
    eval_wire m ops1 c1 regs1 (asg1 cyc) fuel w.
Proof.
  intros m ops1 ops2 c1 c2 regs1 regs asg1 asg2 cyc fuel.
  induction fuel as [|f IH]; intros w Hwf Hw Hregs; [reflexivity|].
  cbn [eval_wire]. rewrite gate_at_combine_l by exact Hw.
  destruct (gate_at c1 w) as [i|s|o args] eqn:Eg; cbn [shift_gate_1].
  - unfold combine_assign. rewrite even_double, div2_double. reflexivity.
  - apply Hregs. exact Hw.
  - unfold combine_ops. rewrite even_double, div2_double. f_equal.
    apply map_over_ext_nat. intros a Ha.
    pose proof (well_formed_gate_reads_earlier_wires c1 w o args Hwf (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hargs.
    pose proof (all_of_mem_nat (fun b => Nat.ltb b w) args a Hargs Ha) as Haw.
    apply Nat.ltb_lt in Haw.
    apply IH; [exact Hwf | lia | exact Hregs].
Qed.

Lemma regs_at_combine_l :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c1 c2 : Circuit) (st1 st2 : nat -> Val m)
         (asg1 asg2 : nat -> nat -> Val m) (t w : nat),
    well_formed c1 = true ->
    well_formed c2 = true ->
    w < wire_count c1 ->
    regs_at m (combine_ops ops1 ops2) (combine_circuits c1 c2)
      (combine_start (wire_count c1) st1 st2)
      (combine_assign asg1 asg2) t w =
    regs_at m ops1 c1 st1 asg1 t w.
Proof.
  intros m ops1 ops2 c1 c2 st1 st2 asg1 asg2 t.
  induction t as [|t IH]; intros w Hwf1 Hwf2 Hw.
  - simpl. unfold combine_start. rewrite (proj2 (Nat.ltb_lt _ _) Hw). reflexivity.
  - simpl. unfold step_regs. rewrite gate_at_combine_l by exact Hw.
    destruct (gate_at c1 w) as [i|s|o args] eqn:Eg; simpl.
    + apply IH; assumption.
    + pose proof (well_formed_register_source_exists c1 w s Hwf1 (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hs.
      apply Nat.ltb_lt in Hs.
      rewrite combine_circuits_count.
      rewrite (eval_fuel_irrelevant m (combine_ops ops1 ops2) (combine_circuits c1 c2)
                 _ _ s (wire_count c1 + wire_count c2) (wire_count c1)
                 (combine_circuits_well_formed c1 c2 Hwf1 Hwf2)
                 ltac:(rewrite combine_circuits_count; apply Nat.ltb_lt; lia)
                 ltac:(apply Nat.ltb_lt; lia) ltac:(apply Nat.ltb_lt; lia)).
      apply eval_wire_combine_l; [exact Hwf1 | exact Hs |].
      intros u Hu. apply IH; assumption.
    + apply IH; assumption.
Qed.

Lemma value_at_combine_l :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c1 c2 : Circuit) (st1 st2 : nat -> Val m)
         (asg1 asg2 : nat -> nat -> Val m) (t w : nat),
    well_formed c1 = true ->
    well_formed c2 = true ->
    w < wire_count c1 ->
    value_at m (combine_ops ops1 ops2) (combine_circuits c1 c2)
      (combine_start (wire_count c1) st1 st2)
      (combine_assign asg1 asg2) t w =
    value_at m ops1 c1 st1 asg1 t w.
Proof.
  intros m ops1 ops2 c1 c2 st1 st2 asg1 asg2 t w Hwf1 Hwf2 Hw.
  unfold value_at. rewrite combine_circuits_count.
  rewrite (eval_fuel_irrelevant m (combine_ops ops1 ops2) (combine_circuits c1 c2)
             _ _ w (wire_count c1 + wire_count c2) (wire_count c1)
             (combine_circuits_well_formed c1 c2 Hwf1 Hwf2)
             ltac:(rewrite combine_circuits_count; apply Nat.ltb_lt; lia)
             ltac:(apply Nat.ltb_lt; lia) ltac:(apply Nat.ltb_lt; lia)).
  apply eval_wire_combine_l; [exact Hwf1 | exact Hw |].
  intros u Hu. apply regs_at_combine_l; assumption.
Qed.

Lemma eval_wire_combine_r :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c1 c2 : Circuit) (regs2 regs : nat -> Val m)
         (asg1 asg2 : nat -> nat -> Val m) (cyc fuel w : nat),
    well_formed c2 = true ->
    w < wire_count c2 ->
    (forall u, u < wire_count c2 -> regs (wire_count c1 + u) = regs2 u) ->
    eval_wire m (combine_ops ops1 ops2) (combine_circuits c1 c2)
      regs (combine_assign asg1 asg2 cyc) fuel (wire_count c1 + w) =
    eval_wire m ops2 c2 regs2 (asg2 cyc) fuel w.
Proof.
  intros m ops1 ops2 c1 c2 regs2 regs asg1 asg2 cyc fuel.
  induction fuel as [|f IH]; intros w Hwf Hw Hregs; [reflexivity|].
  cbn [eval_wire]. rewrite gate_at_combine_r by exact Hw.
  destruct (gate_at c2 w) as [i|s|o args] eqn:Eg; cbn [shift_gate_2].
  - unfold combine_assign. rewrite even_succ_double, div2_succ_double. reflexivity.
  - apply Hregs. exact Hw.
  - unfold combine_ops. rewrite even_succ_double, div2_succ_double. f_equal.
    rewrite map_over_compose. apply map_over_ext_nat. intros a Ha.
    pose proof (well_formed_gate_reads_earlier_wires c2 w o args Hwf (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hargs.
    pose proof (all_of_mem_nat (fun b => Nat.ltb b w) args a Hargs Ha) as Haw.
    apply Nat.ltb_lt in Haw.
    apply IH; [exact Hwf | lia | exact Hregs].
Qed.

Lemma regs_at_combine_r :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c1 c2 : Circuit) (st1 st2 : nat -> Val m)
         (asg1 asg2 : nat -> nat -> Val m) (t w : nat),
    well_formed c1 = true ->
    well_formed c2 = true ->
    w < wire_count c2 ->
    regs_at m (combine_ops ops1 ops2) (combine_circuits c1 c2)
      (combine_start (wire_count c1) st1 st2)
      (combine_assign asg1 asg2) t (wire_count c1 + w) =
    regs_at m ops2 c2 st2 asg2 t w.
Proof.
  intros m ops1 ops2 c1 c2 st1 st2 asg1 asg2 t.
  induction t as [|t IH]; intros w Hwf1 Hwf2 Hw.
  - simpl. unfold combine_start.
    destruct (Nat.ltb (wire_count c1 + w) (wire_count c1)) eqn:Elt.
    + apply Nat.ltb_lt in Elt. lia.
    + rewrite Nat.add_comm, Nat.add_sub. reflexivity.
  - simpl. unfold step_regs. rewrite gate_at_combine_r by exact Hw.
    destruct (gate_at c2 w) as [i|s|o args] eqn:Eg; simpl.
    + apply IH; assumption.
    + pose proof (well_formed_register_source_exists c2 w s Hwf2 (proj2 (Nat.ltb_lt _ _) Hw) Eg) as Hs.
      apply Nat.ltb_lt in Hs.
      rewrite combine_circuits_count.
      rewrite (eval_wire_combine_r m ops1 ops2 c1 c2
                 (regs_at m ops2 c2 st2 asg2 t)
                 (regs_at m (combine_ops ops1 ops2) (combine_circuits c1 c2)
                    (combine_start (wire_count c1) st1 st2) (combine_assign asg1 asg2) t)
                 asg1 asg2 t (wire_count c1 + wire_count c2) s Hwf2 Hs).
      * apply (eval_fuel_irrelevant m ops2 c2 _ _ s (wire_count c1 + wire_count c2) (wire_count c2)
                 Hwf2 ltac:(apply Nat.ltb_lt; exact Hs)
                 ltac:(apply Nat.ltb_lt; lia) ltac:(apply Nat.ltb_lt; exact Hs)).
      * intros u Hu. apply IH; assumption.
    + apply IH; assumption.
Qed.

Lemma value_at_combine_r :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c1 c2 : Circuit) (st1 st2 : nat -> Val m)
         (asg1 asg2 : nat -> nat -> Val m) (t w : nat),
    well_formed c1 = true ->
    well_formed c2 = true ->
    w < wire_count c2 ->
    value_at m (combine_ops ops1 ops2) (combine_circuits c1 c2)
      (combine_start (wire_count c1) st1 st2)
      (combine_assign asg1 asg2) t (wire_count c1 + w) =
    value_at m ops2 c2 st2 asg2 t w.
Proof.
  intros m ops1 ops2 c1 c2 st1 st2 asg1 asg2 t w Hwf1 Hwf2 Hw.
  unfold value_at. rewrite combine_circuits_count.
  rewrite (eval_wire_combine_r m ops1 ops2 c1 c2
             (regs_at m ops2 c2 st2 asg2 t)
             (regs_at m (combine_ops ops1 ops2) (combine_circuits c1 c2)
                (combine_start (wire_count c1) st1 st2) (combine_assign asg1 asg2) t)
             asg1 asg2 t (wire_count c1 + wire_count c2) w Hwf2 Hw).
  - apply (eval_fuel_irrelevant m ops2 c2 _ _ w (wire_count c1 + wire_count c2) (wire_count c2)
             Hwf2 ltac:(apply Nat.ltb_lt; exact Hw)
             ltac:(apply Nat.ltb_lt; lia) ltac:(apply Nat.ltb_lt; exact Hw)).
  - intros u Hu. apply regs_at_combine_r; assumption.
Qed.

(* Splitting and interleaving observations across a combined circuit. *)
Fixpoint split_probes_l (n1 : nat) (ps : list Probe) : list Probe :=
  match ps with
  | nil => nil
  | p :: r => if Nat.ltb (p_wire p) n1 then p :: split_probes_l n1 r else split_probes_l n1 r
  end.

Fixpoint split_probes_r (n1 : nat) (ps : list Probe) : list Probe :=
  match ps with
  | nil => nil
  | p :: r =>
      if Nat.ltb (p_wire p) n1 then split_probes_r n1 r
      else probe_of (p_wire p - n1) (p_cycle p) :: split_probes_r n1 r
  end.

Lemma split_probes_count :
  forall n1 ps, count_of (split_probes_l n1 ps) + count_of (split_probes_r n1 ps) = count_of ps.
Proof.
  intros n1 ps. induction ps as [|p r IH]; simpl; [reflexivity|].
  destruct (Nat.ltb (p_wire p) n1); simpl; lia.
Qed.

Lemma split_probes_wires_exist :
  forall c1 c2 ps,
    wires_exist (combine_circuits c1 c2) (map_over p_wire ps) = true ->
    wires_exist c1 (map_over p_wire (split_probes_l (wire_count c1) ps)) = true /\
    wires_exist c2 (map_over p_wire (split_probes_r (wire_count c1) ps)) = true.
Proof.
  intros c1 c2 ps Hw. unfold wires_exist in *.
  rewrite combine_circuits_count in Hw.
  induction ps as [|p r IH]; simpl in *; [split; reflexivity|].
  apply andb_prop in Hw. destruct Hw as [Hp Hr].
  destruct (IH Hr) as [IH1 IH2].
  destruct (Nat.ltb (p_wire p) (wire_count c1)) eqn:Elt; simpl; split; try assumption.
  - rewrite Elt. exact IH1.
  - apply Nat.ltb_lt in Hp. apply Nat.ltb_ge in Elt.
    replace (Nat.ltb (p_wire p - wire_count c1) (wire_count c2)) with true
      by (symmetry; apply Nat.ltb_lt; lia).
    exact IH2.
Qed.

Fixpoint interleave_obs (E : Expansion) (c1 c2 : Circuit) (ps : list Probe)
    {V : Type} (v1 v2 : list V) : list V :=
  match ps with
  | nil => nil
  | p :: r =>
      if Nat.ltb (p_wire p) (wire_count c1) then
        let k := count_of (E c1 p) in
        app (ProofSupport.take_of k v1)
            (interleave_obs E c1 c2 r (ProofSupport.drop_of k v1) v2)
      else
        let p2 := probe_of (p_wire p - wire_count c1) (p_cycle p) in
        let k := count_of (E c2 p2) in
        app (ProofSupport.take_of k v2)
            (interleave_obs E c1 c2 r v1 (ProofSupport.drop_of k v2))
  end.

Lemma obs_value_combine_l :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c1 c2 : Circuit) (st1 st2 : nat -> Val m)
         (asg1 asg2 : nat -> nat -> Val m) (o : Obs),
    well_formed c1 = true -> well_formed c2 = true ->
    obs_wire o < wire_count c1 ->
    obs_value m (combine_ops ops1 ops2) (combine_circuits c1 c2)
      (combine_start (wire_count c1) st1 st2)
      (combine_assign asg1 asg2) o =
    obs_value m ops1 c1 st1 asg1 o.
Proof.
  intros m ops1 ops2 c1 c2 st1 st2 asg1 asg2 o H1 H2 Hw.
  destruct o as [w t | w t]; simpl in *.
  - apply value_at_combine_l; assumption.
  - f_equal; apply value_at_combine_l; assumption.
Qed.

Lemma obs_value_combine_r :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c1 c2 : Circuit) (st1 st2 : nat -> Val m)
         (asg1 asg2 : nat -> nat -> Val m) (o : Obs),
    well_formed c1 = true -> well_formed c2 = true ->
    obs_wire o < wire_count c2 ->
    obs_value m (combine_ops ops1 ops2) (combine_circuits c1 c2)
      (combine_start (wire_count c1) st1 st2)
      (combine_assign asg1 asg2) (obs_shift (wire_count c1) o) =
    obs_value m ops2 c2 st2 asg2 o.
Proof.
  intros m ops1 ops2 c1 c2 st1 st2 asg1 asg2 o H1 H2 Hw.
  destruct o as [w t | w t]; simpl in *.
  - apply value_at_combine_r; assumption.
  - f_equal; apply value_at_combine_r; assumption.
Qed.

Lemma le_domain_trivial_obs_wire :
  forall E (Hloc : LocalExpansion E) c p o,
    well_formed c = true -> p_wire p < wire_count c ->
    ProofSupport.Member o (E c p) ->
    obs_wire o < wire_count c.
Proof.
  intros E Hloc c p o Hwf Hw Ho.
  destruct (le_domain E Hloc c (fun _ => 0) p o Hwf Hw) as [Hlt _].
  - intros u Hu. destruct (gate_at c u) as [i|s|op args]; try exact I; try reflexivity.
    clear. induction args; simpl; auto.
  - exact Ho.
  - exact Hlt.
Qed.

Lemma interleave_internal_view :
  forall (E : Expansion) (Hloc : LocalExpansion E)
         (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c1 c2 : Circuit) (st1 st2 : nat -> Val m)
         (asg1 asg2 : nat -> nat -> Val m) (ps : list Probe),
    well_formed c1 = true -> well_formed c2 = true ->
    wires_exist (combine_circuits c1 c2) (map_over p_wire ps) = true ->
    map_over (obs_value m (combine_ops ops1 ops2) (combine_circuits c1 c2)
                (combine_start (wire_count c1) st1 st2)
                (combine_assign asg1 asg2))
             (probe_set E (combine_circuits c1 c2) ps) =
    interleave_obs E c1 c2 ps
      (map_over (obs_value m ops1 c1 st1 asg1)
         (probe_set E c1 (split_probes_l (wire_count c1) ps)))
      (map_over (obs_value m ops2 c2 st2 asg2)
         (probe_set E c2 (split_probes_r (wire_count c1) ps))).
Proof.
  intros E Hloc m ops1 ops2 c1 c2 st1 st2 asg1 asg2 ps H1 H2 Hw.
  unfold probe_set, wires_exist in *. rewrite combine_circuits_count in Hw.
  assert (Hmap_app : forall {A B} (f : A -> B) (l1 l2 : list A),
    map_over f (app l1 l2) = app (map_over f l1) (map_over f l2)).
  { clear. intros A B f l1 l2. rewrite map_over_is_map, map_app. repeat rewrite <- map_over_is_map. reflexivity. }
  induction ps as [|p r IH]; [reflexivity|].
  cbn [map_over ProofSupport.map_over all_of ProofSupport.all_of] in Hw.
  apply andb_prop in Hw. destruct Hw as [Hp Hr].
  apply Nat.ltb_lt in Hp.
  cbn [flat_map_over split_probes_l split_probes_r interleave_obs].
  rewrite Hmap_app.
  destruct (Nat.ltb (p_wire p) (wire_count c1)) eqn:Elt.
  - apply Nat.ltb_lt in Elt.
    cbn iota.
    rewrite (le_left_embed E Hloc c1 c2 p H1 H2 Elt).
    cbn [flat_map_over]. rewrite Hmap_app.
    set (l1 := map_over (obs_value m ops1 c1 st1 asg1) (E c1 p)).
    set (l1' := map_over (obs_value m ops1 c1 st1 asg1)
                  (flat_map_over (E c1) (split_probes_l (wire_count c1) r))).
    assert (Hlen : count_of l1 = count_of (E c1 p)).
    { unfold l1. clear. induction (E c1 p); simpl; auto. }
    destruct (take_drop_exact (count_of (E c1 p)) l1 l1' Hlen) as [Ht Hd].
    rewrite Ht, Hd, (IH Hr). unfold l1, l1'. f_equal.
    apply support_map_ext. intros o Ho.
    apply obs_value_combine_l; try assumption.
    exact (le_domain_trivial_obs_wire E Hloc c1 p o H1 Elt Ho).
  - apply Nat.ltb_ge in Elt.
    cbn iota.
    set (p2 := probe_of (p_wire p - wire_count c1) (p_cycle p)).
    assert (Hp2 : p_wire p2 < wire_count c2) by (unfold p2; simpl; lia).
    assert (Hp_eq : p = probe_of (wire_count c1 + p_wire p2) (p_cycle p2)).
    { destruct p as [pw pc]. unfold p2, probe_of in *. simpl in *. f_equal. lia. }
    rewrite Hp_eq at 1.
    rewrite (le_right_embed E Hloc c1 c2 p2 H1 H2 Hp2).
    cbn [flat_map_over]. rewrite Hmap_app.
    set (l2 := map_over (obs_value m ops2 c2 st2 asg2) (E c2 p2)).
    set (l2' := map_over (obs_value m ops2 c2 st2 asg2)
                  (flat_map_over (E c2) (split_probes_r (wire_count c1) r))).
    assert (Hlen : count_of l2 = count_of (E c2 p2)).
    { unfold l2. clear. induction (E c2 p2); simpl; auto. }
    destruct (take_drop_exact (count_of (E c2 p2)) l2 l2' Hlen) as [Ht Hd].
    rewrite Ht, Hd, (IH Hr). unfold l2, l2'. f_equal.
    rewrite map_over_compose. apply support_map_ext. intros o Ho.
    apply obs_value_combine_r; try assumption.
    exact (le_domain_trivial_obs_wire E Hloc c2 p2 o H2 Hp2 Ho).
Qed.

(* -------------------------------------------------------------------------
   Sequential composition of two Gadgets (`seq_gadget`), preserving PINI,
   SNI+NI -> NI, and NI+SNI -> SNI.
   ------------------------------------------------------------------------- *)

Definition val_cast {m1 m2 : Sharing} (H : m1 = m2) (v : Val m1) : Val m2 :=
  match H with eq_refl => v end.

Definition seq_gadget (g1 g2 : Gadget) (Hshare : gd_share g2 = gd_share g1) : Gadget := {|
  gd_share := gd_share g1;
  gd_prob := counting (Tape (gd_prob g1) * Tape (gd_prob g2))
               (list_prod (tape_enum (gd_prob g1)) (tape_enum (gd_prob g2)));
  gd_circuit := combine_circuits (gd_circuit g1) (gd_circuit g2);
  gd_ops := combine_ops (gd_ops g1)
              (fun o args =>
                 val_cast Hshare
                   (gd_ops g2 o (map_over (val_cast (eq_sym Hshare)) args)));
  gd_inputs := gd_inputs g1 + (gd_inputs g2 - 1);
  gd_shares := gd_shares g1;
  gd_out := fun k => wire_count (gd_circuit g1) + gd_out g2 k;
  gd_read := gd_read g2;
  gd_assign := fun a '(t1, t2) cyc i =>
    let a1 : ShareMatrix g1 := fun j k => a j k in
    let a2 : ShareMatrix g2 := fun j k =>
      match j with
      | O => val_cast (eq_sym Hshare)
               (gd_value g1 a1 t1 (gd_read g1) (gd_out g1 k))
      | S r => val_cast (eq_sym Hshare) (a (gd_inputs g1 + r) k)
      end in
    combine_assign (gd_assign g1 a1 t1)
      (fun cyc2 i2 => val_cast Hshare (gd_assign g2 a2 t2 cyc2 i2)) cyc i;
  gd_start := fun a '(t1, t2) w =>
    let a1 : ShareMatrix g1 := fun j k => a j k in
    let a2 : ShareMatrix g2 := fun j k =>
      match j with
      | O => val_cast (eq_sym Hshare)
               (gd_value g1 a1 t1 (gd_read g1) (gd_out g1 k))
      | S r => val_cast (eq_sym Hshare) (a (gd_inputs g1 + r) k)
      end in
    combine_start (wire_count (gd_circuit g1))
      (gd_start g1 a1 t1)
      (fun w2 => val_cast Hshare (gd_start g2 a2 t2 w2)) w
|}.

Fixpoint lookup_selected_share {V : Type} (sel : list nat) (vals : list V)
    (k : nat) (dflt : V) : V :=
  match sel, vals with
  | s :: sr, v :: vr =>
      if Nat.eqb s k then v else lookup_selected_share sr vr k dflt
  | _, _ => dflt
  end.

Lemma lookup_selected_share_map :
  forall {V : Type} (f : nat -> V) (sel : list nat) (k : nat) (dflt : V),
    ProofSupport.Member k sel ->
    lookup_selected_share sel (map_over f sel) k dflt = f k.
Proof.
  intros V f sel k dflt. induction sel as [|s sr IH]; simpl; intros Hk; [contradiction|].
  destruct (Nat.eqb s k) eqn:Esk.
  - apply eqb_sound_nat in Esk. subst s. reflexivity.
  - destruct Hk as [Hk|Hk].
    + subst s. rewrite eqb_refl_nat in Esk. discriminate Esk.
    + exact (IH Hk).
Qed.

Lemma member_selected_outputs :
  forall (g : Gadget) (B : nat -> bool) (k : nat),
    k < gd_shares g -> B k = true ->
    ProofSupport.Member k (selected_outputs g B).
Proof.
  intros g B k Hk HBk. unfold selected_outputs.
  assert (Hmem_filter : forall {A : Type} (p : A -> bool) (l : list A) (x : A),
    ProofSupport.Member x l -> p x = true -> ProofSupport.Member x (filter_of p l)).
  { clear. intros A p l x. induction l as [|y r IH]; simpl; intros Hx Hpx; [contradiction|].
    destruct (p y) eqn:Epy.
    - destruct Hx as [->|Hx]; [left; reflexivity | right; exact (IH Hx Hpx)].
    - destruct Hx as [->|Hx]; [rewrite Hpx in Epy; discriminate Epy | exact (IH Hx Hpx)]. }
  apply Hmem_filter; [|exact HBk].
  revert Hk. generalize (gd_shares g) as n. intros n Hk.
  unfold upto.
  assert (Hmem_app : forall {A : Type} (l1 l2 : list A) (x : A),
    ProofSupport.Member x l1 \/ ProofSupport.Member x l2 ->
    ProofSupport.Member x (app l1 l2)).
  { clear. intros A l1 l2 x. induction l1 as [|y r IH]; simpl; intros [H|H].
    - contradiction.
    - exact H.
    - destruct H as [->|H]; [left; reflexivity | right; exact (IH (or_introl H))].
    - right; exact (IH (or_intror H)). }
  induction n as [|n IH]; [lia|].
  simpl. apply Hmem_app.
  destruct (Nat.eq_dec k n) as [->|Hne]; [right; left; reflexivity | left; apply IH; lia].
Qed.

Definition seq_merge_shares (g1 : Gadget) (I1 I2 : ShareSet) : ShareSet :=
  fun j k => if Nat.ltb j (gd_inputs g1) then I1 j k else I2 (S (j - gd_inputs g1)) k.

Definition gadget_well_formed (g : Gadget) : Prop :=
  well_formed (gd_circuit g) = true /\
  0 < gd_inputs g /\
  (forall k, k < gd_shares g -> gd_out g k < wire_count (gd_circuit g)).

Lemma seq_gadget_well_formed :
  forall g1 g2 Hshare,
    gd_shares g1 = gd_shares g2 ->
    gadget_well_formed g1 -> gadget_well_formed g2 ->
    gadget_well_formed (seq_gadget g1 g2 Hshare).
Proof.
  intros g1 g2 Hshare Hsh [Hwf1 [Hin1 Hout1]] [Hwf2 [Hin2 Hout2]].
  split; [apply combine_circuits_well_formed; assumption|].
  split; [simpl; lia|].
  intros k Hk. simpl in *. rewrite combine_circuits_count.
  pose proof (Hout2 k ltac:(lia)). lia.
Qed.

Lemma selected_outputs_lt :
  forall (g : Gadget) (B : nat -> bool) (k : nat),
    ProofSupport.Member k (selected_outputs g B) -> k < gd_shares g.
Proof.
  intros g B k Hk. unfold selected_outputs in Hk.
  apply support_filter_member in Hk.
  revert Hk. generalize (gd_shares g) as n. intros n Hk.
  unfold upto in Hk.
  induction n as [|n IH]; simpl in *; [contradiction|].
  assert (Happ : forall l1 l2 : list nat,
    ProofSupport.Member k (app l1 l2) ->
    ProofSupport.Member k l1 \/ ProofSupport.Member k l2).
  { clear. induction l1 as [|x r1 IH1]; intros l2 H; simpl in *; [right; exact H|].
    destruct H as [->|H]; [left; left; reflexivity|].
    destruct (IH1 l2 H); [left; right; assumption | right; assumption]. }
  destruct (Happ _ _ Hk) as [H1|[->|[]]]; [specialize (IH H1); lia | lia].
Qed.

(* Helper: combine_ops with identity cast produces identical eval_wire *)
Lemma map_over_id_val : forall {A : Type} (l : list A), map_over (fun x : A => x) l = l.
Proof. intros A l. induction l; simpl; congruence. Qed.

Lemma eval_wire_regs_ops_ext :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c : Circuit) (regs1 regs2 ins : nat -> Val m) (fuel w : nat),
    (forall o args, ops1 o args = ops2 o args) ->
    (forall u, regs1 u = regs2 u) ->
    eval_wire m ops1 c regs1 ins fuel w = eval_wire m ops2 c regs2 ins fuel w.
Proof.
  intros m ops1 ops2 c regs1 regs2 ins fuel.
  induction fuel as [|f IH]; intros w Hops Hregs; [reflexivity|].
  simpl. destruct (gate_at c w) as [i|s|o args].
  - reflexivity.
  - apply Hregs.
  - rewrite Hops. f_equal. apply map_over_ext. intros a. apply IH; assumption.
Qed.

Lemma regs_at_ops_ext :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c : Circuit) (init : nat -> Val m) (ins : nat -> nat -> Val m) (t u : nat),
    (forall o args, ops1 o args = ops2 o args) ->
    regs_at m ops1 c init ins t u = regs_at m ops2 c init ins t u.
Proof.
  intros m ops1 ops2 c init ins t.
  induction t as [|t IH]; intros u Hops; [reflexivity|].
  simpl. unfold step_regs. destruct (gate_at c u) as [i|s|o args]; try apply IH; try exact Hops.
  apply eval_wire_regs_ops_ext; [exact Hops | intros v; apply IH; exact Hops].
Qed.

Lemma value_at_ops_ext :
  forall (m : Sharing) (ops1 ops2 : nat -> list (Val m) -> Val m)
         (c : Circuit) (init : nat -> Val m) (ins : nat -> nat -> Val m) (t w : nat),
    (forall o args, ops1 o args = ops2 o args) ->
    value_at m ops1 c init ins t w = value_at m ops2 c init ins t w.
Proof.
  intros m ops1 ops2 c init ins t w Hops. unfold value_at.
  apply eval_wire_regs_ops_ext; [exact Hops | intros u; apply regs_at_ops_ext; exact Hops].
Qed.

Lemma seq_simulable_compose :
  forall (g1 g2 : Gadget) (Hshare : gd_share g2 = gd_share g1)
         (E : Expansion) (ps : list Probe) (B : nat -> bool)
         (I1 I2 : ShareSet) (B_mid : nat -> bool),
    gd_shares g1 = gd_shares g2 ->
    gadget_well_formed g1 ->
    gadget_well_formed g2 ->
    HasCountingMass (gd_prob g1) ->
    HasCountingMass (gd_prob g2) ->
    LocalExpansion E ->
    wires_exist (combine_circuits (gd_circuit g1) (gd_circuit g2)) (map_over p_wire ps) = true ->
    (forall k, k < gd_shares g2 -> I2 0 k = true -> B_mid k = true) ->
    SimulableFrom g1 I1 (split_view g1 E (split_probes_l (wire_count (gd_circuit g1)) ps) B_mid) ->
    SimulableFrom g2 I2 (split_view g2 E (split_probes_r (wire_count (gd_circuit g1)) ps) B) ->
    SimulableFrom (seq_gadget g1 g2 Hshare) (seq_merge_shares g1 I1 I2)
      (split_view (seq_gadget g1 g2 Hshare) E ps B).
Proof.
  intros g1 g2 Hshare E ps B I1 I2 B_mid Hsh
         [Hwf1 [Hin1 Hout1]] [Hwf2 [Hin2 Hout2]] Hc1 Hc2 Hloc Hw Hmid Hsim1 Hsim2.
  destruct g1 as [m1 p1 c1 ops1 in1 sh1 out1 r1 asg1 st1].
  destruct g2 as [m2 p2 c2 ops2 in2 sh2 out2 r2 asg2 st2].
  simpl in *. destruct Hshare. rename m2 into m1. subst sh2.
  set (g1 := {| gd_share := m1; gd_prob := p1; gd_circuit := c1; gd_ops := ops1;
                gd_inputs := in1; gd_shares := sh1; gd_out := out1; gd_read := r1;
                gd_assign := asg1; gd_start := st1 |}).
  set (g2 := {| gd_share := m1; gd_prob := p2; gd_circuit := c2; gd_ops := ops2;
                gd_inputs := in2; gd_shares := sh1; gd_out := out2; gd_read := r2;
                gd_assign := asg2; gd_start := st2 |}).
  set (ps1 := split_probes_l (wire_count c1) ps).
  set (ps2 := split_probes_r (wire_count c1) ps).
  set (n_int1 := count_of (probe_set E c1 ps1)).
  set (sel_mid := selected_outputs g1 B_mid).
  set (reconstruct_a2 := fun (outer_a : ShareMatrix (seq_gadget g1 g2 eq_refl))
                             (v1 : list (Val m1)) (j k : nat) =>
         match j with
         | O => lookup_selected_share sel_mid (ProofSupport.drop_of n_int1 v1) k (v_zero m1)
         | S r => outer_a (in1 + r) k
         end).
  set (obs_of := fun (outer_a : ShareMatrix (seq_gadget g1 g2 eq_refl))
                     (v1 : list (Val m1)) (t2 : Tape p2) =>
         let a2 := reconstruct_a2 outer_a v1 in
         app (interleave_obs E c1 c2 ps
                (ProofSupport.take_of n_int1 v1)
                (internal_view g2 E ps2 a2 t2))
             (output_view g2 B a2 t2)).
  assert (Hops_ext : forall o args,
    combine_ops ops1 (fun o0 args0 => ops2 o0 (map_over (fun x => x) args0)) o args =
    combine_ops ops1 ops2 o args).
  { intros o args. unfold combine_ops. destruct (Nat.even o); [reflexivity|].
    rewrite map_over_id_val. reflexivity. }
  assert (Hsplit_eq : forall (outer_a : ShareMatrix (seq_gadget g1 g2 eq_refl))
                             (t1 : Tape p1) (t2 : Tape p2),
    let a1 : ShareMatrix g1 := fun j k => outer_a j k in
    let a2_real : ShareMatrix g2 := fun j k =>
      match j with
      | O => gd_value g1 a1 t1 r1 (out1 k)
      | S r => outer_a (in1 + r) k
      end in
    split_view (seq_gadget g1 g2 eq_refl) E ps B outer_a (t1, t2) =
    app (interleave_obs E c1 c2 ps (internal_view g1 E ps1 a1 t1)
                                    (internal_view g2 E ps2 a2_real t2))
        (output_view g2 B a2_real t2)).
  { intros outer_a t1 t2 a1 a2_real. unfold split_view. f_equal.
    - unfold internal_view. simpl.
      transitivity
        (map_over (obs_value m1 (combine_ops ops1 ops2) (combine_circuits c1 c2)
                     (combine_start (wire_count c1) (st1 a1 t1) (st2 a2_real t2))
                     (fun cyc => combine_assign (asg1 a1 t1) (asg2 a2_real t2) cyc))
                  (probe_set E (combine_circuits c1 c2) ps)).
      + apply support_map_ext. intros o _.
        destruct o as [w t | w t]; simpl;
          [apply value_at_ops_ext; exact Hops_ext |
           f_equal; apply value_at_ops_ext; exact Hops_ext].
      + exact (interleave_internal_view E Hloc m1 ops1 ops2 c1 c2
                 (st1 a1 t1) (st2 a2_real t2) (asg1 a1 t1) (asg2 a2_real t2) ps
                 Hwf1 Hwf2 Hw).
    - unfold output_view, selected_outputs. simpl.
      apply support_map_ext. intros k Hk.
      assert (Hk_lt : k < sh1).
      { apply (selected_outputs_lt g1 B k). exact Hk. }
      unfold gd_value. simpl.
      rewrite (value_at_ops_ext m1 _ (combine_ops ops1 ops2) _ _ _ _ _ Hops_ext).
      apply value_at_combine_r; [exact Hwf1 | exact Hwf2 | apply Hout2; exact Hk_lt]. }
  assert (Htake_v1 : forall a1 t1,
    ProofSupport.take_of n_int1 (split_view g1 E ps1 B_mid a1 t1) =
    internal_view g1 E ps1 a1 t1 /\
    ProofSupport.drop_of n_int1 (split_view g1 E ps1 B_mid a1 t1) =
    output_view g1 B_mid a1 t1).
  { intros a1 t1. unfold split_view. apply take_drop_exact.
    unfold internal_view, n_int1. repeat rewrite count_of_is_length.
    rewrite map_over_is_map, length_map. reflexivity. }
  assert (Ha2_agree : forall outer_a t1,
    let a1 : ShareMatrix g1 := fun j k => outer_a j k in
    let a2_real : ShareMatrix g2 := fun j k =>
      match j with
      | O => gd_value g1 a1 t1 r1 (out1 k)
      | S r => outer_a (in1 + r) k
      end in
    agree_on g2 I2 a2_real (reconstruct_a2 outer_a (split_view g1 E ps1 B_mid a1 t1))).
  { intros outer_a t1 a1 a2_real j k Hj Hk HI.
    destruct j as [|r]; [|reflexivity].
    simpl in *. destruct (Htake_v1 a1 t1) as [_ Hdrop]. rewrite Hdrop.
    unfold output_view, sel_mid.
    symmetry. apply (lookup_selected_share_map (fun k0 => gd_value g1 a1 t1 r1 (out1 k0))).
    apply member_selected_outputs; [apply Nat.ltb_lt; exact Hk | apply Hmid; [apply Nat.ltb_lt; exact Hk | exact HI]]. }
  assert (Hpush_g2 : forall (a2_1 a2_2 : ShareMatrix g2) (v1_const : list (Val m1)),
    agree_on g2 I2 a2_1 a2_2 ->
    SameDistribution (counting (Tape p2) (tape_enum p2))
      (list (Val m1)) (list_eqb (v_eqb m1))
      (fun t2 => app (interleave_obs E c1 c2 ps (ProofSupport.take_of n_int1 v1_const)
                        (internal_view g2 E ps2 a2_1 t2))
                     (output_view g2 B a2_1 t2))
      (fun t2 => app (interleave_obs E c1 c2 ps (ProofSupport.take_of n_int1 v1_const)
                        (internal_view g2 E ps2 a2_2 t2))
                     (output_view g2 B a2_2 t2))).
  { intros a2_1 a2_2 v1_const Hag.
    pose proof (Hc2 _ (list_eqb (v_eqb m1)) _ _ (Hsim2 a2_1 a2_2 Hag)) as Hdist2.
    set (n_int2 := count_of (probe_set E c2 ps2)).
    set (lift := fun (sv2 : list (Val m1)) =>
      app (interleave_obs E c1 c2 ps (ProofSupport.take_of n_int1 v1_const)
             (ProofSupport.take_of n_int2 sv2))
          (ProofSupport.drop_of n_int2 sv2)).
    assert (Hlift_eq : forall a2 t2,
      lift (split_view g2 E ps2 B a2 t2) =
      app (interleave_obs E c1 c2 ps (ProofSupport.take_of n_int1 v1_const)
             (internal_view g2 E ps2 a2 t2))
          (output_view g2 B a2 t2)).
    { intros a2 t2. unfold lift, split_view. cbv beta.
      destruct (take_drop_exact n_int2 (internal_view g2 E ps2 a2 t2) (output_view g2 B a2 t2)
                  ltac:(unfold internal_view, n_int2; repeat rewrite count_of_is_length;
                        rewrite map_over_is_map, length_map; reflexivity))
        as [Ht Hd].
      f_equal; [f_equal; exact Ht | exact Hd]. }
    intros o.
    eapply eq_trans; [|eapply eq_trans; [exact (counting_pushforward (Tape p2) (tape_enum p2)
      (list (Val m1)) (list (Val m1)) (list_eqb (v_eqb m1)) (list_eqb (v_eqb m1))
      (split_view g2 E ps2 B a2_1) (split_view g2 E ps2 B a2_2) lift
      (list_eqb_sound m1) (list_eqb_refl_sharing m1) Hdist2 o)|]].
    - apply pr_ext. intros t2. rewrite Hlift_eq. reflexivity.
    - apply pr_ext. intros t2. rewrite Hlift_eq. reflexivity. }
  intros outer_a outer_b Hagree.
  set (a1 := (fun j k => outer_a j k) : ShareMatrix g1).
  set (b1 := (fun j k => outer_b j k) : ShareMatrix g1).
  assert (Hag_1 : agree_on g1 I1 a1 b1).
  { intros j k Hj Hk HI. apply Hagree; [|exact Hk|].
    - apply Nat.ltb_lt in Hj. apply Nat.ltb_lt. unfold g1, g2, seq_gadget in *. simpl in *. lia.
    - unfold seq_merge_shares. rewrite Hj. exact HI. }
  assert (Hag_ext : forall v1_const,
    agree_on g2 I2 (reconstruct_a2 outer_a v1_const) (reconstruct_a2 outer_b v1_const)).
  { intros v1_const j k Hj Hk HI. destruct j as [|r]; [reflexivity|].
    simpl in *. apply Hagree; [|exact Hk|].
    - apply Nat.ltb_lt in Hj. apply Nat.ltb_lt. unfold g1, g2, seq_gadget in *. simpl in *. lia.
    - unfold seq_merge_shares, g1. simpl gd_inputs.
      destruct (Nat.ltb (in1 + r) in1) eqn:Elt; [apply Nat.ltb_lt in Elt; lia|].
      replace (in1 + r - in1) with r by lia. exact HI. }
  assert (Hchain1 : SameDistribution (gd_prob (seq_gadget g1 g2 eq_refl))
    (list (Val m1)) (list_eqb (v_eqb m1))
    (split_view (seq_gadget g1 g2 eq_refl) E ps B outer_a)
    (fun '(t1, t2) => obs_of outer_a (split_view g1 E ps1 B_mid a1 t1) t2)).
  { simpl gd_prob. apply counting_prod_right. intros t1 _.
    unfold obs_of. cbv beta.
    pose proof (Htake_v1 a1 t1) as [Ht1 _].
    intros o.
    eapply eq_trans; [|exact (Hpush_g2 _ _ (split_view g1 E ps1 B_mid a1 t1) (Ha2_agree outer_a t1) o)].
    apply pr_ext. intros t2. rewrite Hsplit_eq.
    f_equal. f_equal. f_equal. f_equal. symmetry. exact Ht1. }
  assert (Hchain2 : SameDistribution (gd_prob (seq_gadget g1 g2 eq_refl))
    (list (Val m1)) (list_eqb (v_eqb m1))
    (fun '(t1, t2) => obs_of outer_a (split_view g1 E ps1 B_mid a1 t1) t2)
    (fun '(t1, t2) => obs_of outer_a (split_view g1 E ps1 B_mid b1 t1) t2)).
  { simpl gd_prob. apply counting_prod_left. intros t2 _.
    pose proof (Hc1 _ (list_eqb (v_eqb m1)) _ _ (Hsim1 a1 b1 Hag_1)) as Hdist1.
    apply (counting_pushforward (Tape p1) (tape_enum p1)
             (list (Val m1)) (list (Val m1)) (list_eqb (v_eqb m1)) (list_eqb (v_eqb m1))
             (split_view g1 E ps1 B_mid a1) (split_view g1 E ps1 B_mid b1)
             (fun v1 => obs_of outer_a v1 t2)
             (list_eqb_sound m1) (list_eqb_refl_sharing m1) Hdist1). }
  assert (Hchain3 : SameDistribution (gd_prob (seq_gadget g1 g2 eq_refl))
    (list (Val m1)) (list_eqb (v_eqb m1))
    (fun '(t1, t2) => obs_of outer_a (split_view g1 E ps1 B_mid b1 t1) t2)
    (fun '(t1, t2) => obs_of outer_b (split_view g1 E ps1 B_mid b1 t1) t2)).
  { simpl gd_prob. apply counting_prod_right. intros t1 _.
    unfold obs_of. cbv beta.
    apply (Hpush_g2 _ _ (split_view g1 E ps1 B_mid b1 t1)
             (Hag_ext (split_view g1 E ps1 B_mid b1 t1))). }
  assert (Hchain4 : SameDistribution (gd_prob (seq_gadget g1 g2 eq_refl))
    (list (Val m1)) (list_eqb (v_eqb m1))
    (fun '(t1, t2) => obs_of outer_b (split_view g1 E ps1 B_mid b1 t1) t2)
    (split_view (seq_gadget g1 g2 eq_refl) E ps B outer_b)).
  { simpl gd_prob. apply counting_prod_right. intros t1 _.
    unfold obs_of. cbv beta.
    pose proof (Htake_v1 b1 t1) as [Ht1 _].
    intros o.
    eapply eq_trans; [exact (Hpush_g2 _ _ (split_view g1 E ps1 B_mid b1 t1)
                              (fun j k Hj Hk HI => eq_sym (Ha2_agree outer_b t1 j k Hj Hk HI)) o)|].
    apply pr_ext. intros t2. rewrite Hsplit_eq.
    f_equal. f_equal. f_equal. f_equal. exact Ht1. }
  intros o.
  eapply eq_trans; [exact (Hchain1 o)|].
  eapply eq_trans; [exact (Hchain2 o)|].
  eapply eq_trans; [exact (Hchain3 o)|].
  exact (Hchain4 o).
Qed.

Lemma card_in_or_le :
  forall (g : Gadget) (P Q : nat -> bool) (j : nat),
    card_in g (fun i k => orb (P k) (Q k)) j <=
    card_in g (fun _ k => P k) j + card_in g (fun _ k => Q k) j.
Proof.
  intros g P Q j. unfold card_in.
  pose proof (count_filter_or P Q (upto (gd_shares g))) as H.
  apply Nat.leb_le in H. exact H.
Qed.

Lemma card_in_ext :
  forall (g : Gadget) (I1 I2 : ShareSet) (j : nat),
    (forall k, I1 j k = I2 j k) ->
    card_in g I1 j = card_in g I2 j.
Proof.
  intros g I1 I2 j H. unfold card_in. f_equal.
  apply filter_of_ext. exact H.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem pini_seq_compose :
  forall (g1 g2 : Gadget) (Hshare : gd_share g2 = gd_share g1)
         (E : Expansion) (d : nat),
    gd_shares g1 = gd_shares g2 ->
    gadget_well_formed g1 ->
    gadget_well_formed g2 ->
    HasCountingMass (gd_prob g1) ->
    HasCountingMass (gd_prob g2) ->
    LocalExpansion E ->
    PINI g1 E d ->
    PINI g2 E d ->
    PINI (seq_gadget g1 g2 Hshare) E d.
Proof.
  intros g1 g2 Hshare E d Hsh Hgw1 Hgw2 Hc1 Hc2 Hloc Hpini1 Hpini2 ps B Hw Hord.
  pose proof Hgw1 as [Hwf1 [Hin1 _]].
  pose proof Hgw2 as [Hwf2 [Hin2 _]].
  simpl in Hw.
  destruct (split_probes_wires_exist (gd_circuit g1) (gd_circuit g2) ps Hw) as [Hw1 Hw2].
  pose proof (split_probes_count (wire_count (gd_circuit g1)) ps) as Hcnt.
  apply Nat.leb_le in Hord.
  set (ps1 := split_probes_l (wire_count (gd_circuit g1)) ps).
  set (ps2 := split_probes_r (wire_count (gd_circuit g1)) ps).
  destruct (Hpini2 ps2 B Hw2 ltac:(apply Nat.leb_le; unfold ps2; lia)) as [I2 [Hb2 Hsim2]].
  set (B_mid := fun k => orb (I2 0 k) (B k)).
  destruct (Hpini1 ps1 B_mid Hw1 ltac:(apply Nat.leb_le; unfold ps1; lia)) as [I1 [Hb1 Hsim1]].
  set (I_comp := seq_merge_shares g1 (fun j k => orb (I1 j k) (I2 0 k)) I2).
  exists I_comp. split.
  - intros j Hj. unfold BoundedBy in *. simpl in Hj. apply Nat.ltb_lt in Hj.
    unfold I_comp, seq_merge_shares.
    destruct (Nat.ltb j (gd_inputs g1)) eqn:Elt.
    + assert (Hj1 : j < gd_inputs g1) by (apply Nat.ltb_lt; exact Elt).
      pose proof (Hb1 j ltac:(apply Nat.ltb_lt; exact Hj1)) as H1.
      pose proof (Hb2 0 ltac:(apply Nat.ltb_lt; exact Hin2)) as H2.
      apply Nat.leb_le in H1. apply Nat.leb_le in H2. apply Nat.leb_le.
      assert (Hc_or : count_of (filter_of (fun k => orb (I1 j k) (I2 0 k)) (upto (gd_shares g1))) <=
                      count_of (filter_of (I1 j) (upto (gd_shares g1))) +
                      count_of (filter_of (I2 0) (upto (gd_shares g1)))).
      { pose proof (count_filter_or (fun k => I1 j k) (fun k => I2 0 k) (upto (gd_shares g1))) as Hle.
        apply Nat.leb_le in Hle.
        replace (filter_of (fun k => I1 j k) (upto (gd_shares g1)))
          with (filter_of (I1 j) (upto (gd_shares g1))) in Hle
          by (apply filter_of_ext; reflexivity).
        replace (filter_of (fun k => I2 0 k) (upto (gd_shares g1)))
          with (filter_of (I2 0) (upto (gd_shares g1))) in Hle
          by (apply filter_of_ext; reflexivity).
        exact Hle. }
      unfold card_in in *. simpl gd_shares in *. rewrite <- Hsh in H2. unfold ps1, ps2 in *.
      replace (filter_of (fun k => if j <? gd_inputs g1 then orb (I1 j k) (I2 0 k) else I2 (S (j - gd_inputs g1)) k) (upto (gd_shares g1)))
        with (filter_of (fun k => orb (I1 j k) (I2 0 k)) (upto (gd_shares g1)))
        by (apply filter_of_ext; intros k; rewrite Elt; reflexivity).
      lia.
    + assert (Hj1 : gd_inputs g1 <= j) by (apply Nat.ltb_ge; exact Elt).
      pose proof (Hb2 (S (j - gd_inputs g1)) ltac:(apply Nat.ltb_lt; lia)) as H2.
      apply Nat.leb_le in H2. apply Nat.leb_le.
      unfold card_in in *. simpl gd_shares in *. rewrite <- Hsh in H2. unfold ps2 in H2.
      replace (filter_of (fun k => if j <? gd_inputs g1 then orb (I1 j k) (I2 0 k) else I2 (S (j - gd_inputs g1)) k) (upto (gd_shares g1)))
        with (filter_of (I2 (S (j - gd_inputs g1))) (upto (gd_shares g1)))
        by (apply filter_of_ext; intros k; rewrite Elt; reflexivity).
      lia.
  - assert (Hmerge_eq : forall a b,
      agree_on (seq_gadget g1 g2 Hshare) (union_shares I_comp B) a b ->
      agree_on (seq_gadget g1 g2 Hshare)
        (seq_merge_shares g1 (union_shares I1 B_mid) (union_shares I2 B)) a b).
    { intros a b Hag j k Hj Hk HI. apply Hag; [exact Hj | exact Hk|].
      unfold union_shares, I_comp, seq_merge_shares, B_mid in *.
      destruct (Nat.ltb j (gd_inputs g1)); simpl in *;
        [rewrite Bool.orb_assoc in HI; exact HI | exact HI]. }
    intros a b Hag.
    apply (seq_simulable_compose g1 g2 Hshare E ps B
             (union_shares I1 B_mid) (union_shares I2 B) B_mid
             Hsh Hgw1 Hgw2 Hc1 Hc2 Hloc Hw).
    + intros k Hk HI. unfold union_shares, B_mid in *. rewrite HI. reflexivity.
    + exact Hsim1.
    + exact Hsim2.
    + apply Hmerge_eq. exact Hag.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem sni_ni_compose :
  forall (g1 g2 : Gadget) (Hshare : gd_share g2 = gd_share g1)
         (E : Expansion) (d : nat),
    gd_shares g1 = gd_shares g2 ->
    gadget_well_formed g1 ->
    gadget_well_formed g2 ->
    HasCountingMass (gd_prob g1) ->
    HasCountingMass (gd_prob g2) ->
    LocalExpansion E ->
    SNI g1 E d ->
    NI g2 E d ->
    NI (seq_gadget g1 g2 Hshare) E d.
Proof.
  intros g1 g2 Hshare E d Hsh Hgw1 Hgw2 Hc1 Hc2 Hloc Hsni1 Hni2 ps B Hw Hs.
  pose proof Hgw1 as [Hwf1 [Hin1 _]].
  pose proof Hgw2 as [Hwf2 [Hin2 _]].
  simpl in Hw.
  destruct (split_probes_wires_exist (gd_circuit g1) (gd_circuit g2) ps Hw) as [Hw1 Hw2].
  pose proof (split_probes_count (wire_count (gd_circuit g1)) ps) as Hcnt.
  unfold split_size in Hs. simpl in Hs.
  apply Nat.leb_le in Hs.
  set (ps1 := split_probes_l (wire_count (gd_circuit g1)) ps).
  set (ps2 := split_probes_r (wire_count (gd_circuit g1)) ps).
  assert (Hsel_eq : selected_outputs (seq_gadget g1 g2 Hshare) B = selected_outputs g2 B).
  { unfold selected_outputs. simpl. rewrite Hsh. reflexivity. }
  assert (Hs2 : Nat.leb (split_size g2 ps2 B) d = true).
  { unfold split_size. apply Nat.leb_le. rewrite Hsel_eq in Hs. unfold ps2. lia. }
  destruct (Hni2 ps2 B Hw2 Hs2) as [I2 [Hb2 Hsim2]].
  set (B_mid := I2 0).
  assert (Hmid_le : count_of (selected_outputs g1 B_mid) <= split_size g2 ps2 B).
  { pose proof (Hb2 0 ltac:(apply Nat.ltb_lt; exact Hin2)) as H2.
    apply Nat.leb_le in H2. unfold card_in, selected_outputs, B_mid in *.
    rewrite Hsh. exact H2. }
  assert (Hs1 : Nat.leb (split_size g1 ps1 B_mid) d = true).
  { unfold split_size in *. apply Nat.leb_le. rewrite Hsel_eq in Hs. unfold ps1, ps2 in *. lia. }
  destruct (Hsni1 ps1 B_mid Hw1 Hs1) as [I1 [Hb1 Hsim1]].
  exists (seq_merge_shares g1 I1 I2). split.
  - intros j Hj. simpl in Hj. apply Nat.ltb_lt in Hj.
    unfold seq_merge_shares. destruct (Nat.ltb j (gd_inputs g1)) eqn:Elt.
    + assert (Hj1 : j < gd_inputs g1) by (apply Nat.ltb_lt; exact Elt).
      pose proof (Hb1 j ltac:(apply Nat.ltb_lt; exact Hj1)) as H1.
      apply Nat.leb_le in H1. apply Nat.leb_le.
      unfold card_in, split_size in *. simpl gd_shares in *. unfold ps1, ps2 in *.
      replace (filter_of (fun k => if j <? gd_inputs g1 then I1 j k else I2 (S (j - gd_inputs g1)) k) (upto (gd_shares g1)))
        with (filter_of (I1 j) (upto (gd_shares g1)))
        by (apply filter_of_ext; intros k; rewrite Elt; reflexivity).
      lia.
    + assert (Hj1 : gd_inputs g1 <= j) by (apply Nat.ltb_ge; exact Elt).
      pose proof (Hb2 (S (j - gd_inputs g1)) ltac:(apply Nat.ltb_lt; lia)) as H2.
      apply Nat.leb_le in H2. apply Nat.leb_le.
      unfold card_in, split_size in *. simpl gd_shares in *. rewrite <- Hsh in H2. rewrite Hsel_eq. unfold ps2 in H2.
      replace (filter_of (fun k => if j <? gd_inputs g1 then I1 j k else I2 (S (j - gd_inputs g1)) k) (upto (gd_shares g1)))
        with (filter_of (I2 (S (j - gd_inputs g1))) (upto (gd_shares g1)))
        by (apply filter_of_ext; intros k; rewrite Elt; reflexivity).
      lia.
  - apply (seq_simulable_compose g1 g2 Hshare E ps B I1 I2 B_mid
             Hsh Hgw1 Hgw2 Hc1 Hc2 Hloc Hw).
    + intros k _ HI. exact HI.
    + exact Hsim1.
    + exact Hsim2.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem ni_sni_compose :
  forall (g1 g2 : Gadget) (Hshare : gd_share g2 = gd_share g1)
         (E : Expansion) (d : nat),
    gd_shares g1 = gd_shares g2 ->
    gadget_well_formed g1 ->
    gadget_well_formed g2 ->
    HasCountingMass (gd_prob g1) ->
    HasCountingMass (gd_prob g2) ->
    LocalExpansion E ->
    NI g1 E d ->
    SNI g2 E d ->
    SNI (seq_gadget g1 g2 Hshare) E d.
Proof.
  intros g1 g2 Hshare E d Hsh Hgw1 Hgw2 Hc1 Hc2 Hloc Hni1 Hsni2 ps B Hw Hs.
  pose proof Hgw1 as [Hwf1 [Hin1 _]].
  pose proof Hgw2 as [Hwf2 [Hin2 _]].
  simpl in Hw.
  destruct (split_probes_wires_exist (gd_circuit g1) (gd_circuit g2) ps Hw) as [Hw1 Hw2].
  pose proof (split_probes_count (wire_count (gd_circuit g1)) ps) as Hcnt.
  unfold split_size in Hs. simpl in Hs.
  apply Nat.leb_le in Hs.
  set (ps1 := split_probes_l (wire_count (gd_circuit g1)) ps).
  set (ps2 := split_probes_r (wire_count (gd_circuit g1)) ps).
  assert (Hsel_eq : selected_outputs (seq_gadget g1 g2 Hshare) B = selected_outputs g2 B).
  { unfold selected_outputs. simpl. rewrite Hsh. reflexivity. }
  assert (Hs2 : Nat.leb (split_size g2 ps2 B) d = true).
  { unfold split_size. apply Nat.leb_le. rewrite Hsel_eq in Hs. unfold ps2. lia. }
  destruct (Hsni2 ps2 B Hw2 Hs2) as [I2 [Hb2 Hsim2]].
  set (B_mid := I2 0).
  assert (Hmid_le : count_of (selected_outputs g1 B_mid) <= count_of ps2).
  { pose proof (Hb2 0 ltac:(apply Nat.ltb_lt; exact Hin2)) as H2.
    apply Nat.leb_le in H2. unfold card_in, selected_outputs, B_mid in *.
    rewrite Hsh. exact H2. }
  assert (Hs1 : Nat.leb (split_size g1 ps1 B_mid) d = true).
  { unfold split_size in *. apply Nat.leb_le. unfold ps1, ps2 in *. lia. }
  destruct (Hni1 ps1 B_mid Hw1 Hs1) as [I1 [Hb1 Hsim1]].
  exists (seq_merge_shares g1 I1 I2). split.
  - intros j Hj. simpl in Hj. apply Nat.ltb_lt in Hj.
    unfold seq_merge_shares. destruct (Nat.ltb j (gd_inputs g1)) eqn:Elt.
    + assert (Hj1 : j < gd_inputs g1) by (apply Nat.ltb_lt; exact Elt).
      pose proof (Hb1 j ltac:(apply Nat.ltb_lt; exact Hj1)) as H1.
      apply Nat.leb_le in H1. apply Nat.leb_le.
      unfold card_in, split_size in *. simpl gd_shares in *. unfold ps1, ps2 in *.
      replace (filter_of (fun k => if j <? gd_inputs g1 then I1 j k else I2 (S (j - gd_inputs g1)) k) (upto (gd_shares g1)))
        with (filter_of (I1 j) (upto (gd_shares g1)))
        by (apply filter_of_ext; intros k; rewrite Elt; reflexivity).
      lia.
    + assert (Hj1 : gd_inputs g1 <= j) by (apply Nat.ltb_ge; exact Elt).
      pose proof (Hb2 (S (j - gd_inputs g1)) ltac:(apply Nat.ltb_lt; lia)) as H2.
      apply Nat.leb_le in H2. apply Nat.leb_le.
      unfold card_in in *. simpl gd_shares in *. rewrite <- Hsh in H2. unfold ps2 in H2.
      replace (filter_of (fun k => if j <? gd_inputs g1 then I1 j k else I2 (S (j - gd_inputs g1)) k) (upto (gd_shares g1)))
        with (filter_of (I2 (S (j - gd_inputs g1))) (upto (gd_shares g1)))
        by (apply filter_of_ext; intros k; rewrite Elt; reflexivity).
      lia.
  - apply (seq_simulable_compose g1 g2 Hshare E ps B I1 I2 B_mid
             Hsh Hgw1 Hgw2 Hc1 Hc2 Hloc Hw).
    + intros k _ HI. exact HI.
    + exact Hsim1.
    + exact Hsim2.
Qed.

(* -------------------------------------------------------------------------
   Parallel composition of two t-PINI gadgets (even sharing common inputs)
   and StrongPINI for arbitrary straight-line DAG composition.
   ------------------------------------------------------------------------- *)

Definition par_split_view (g1 g2 : Gadget) (Hshare : gd_share g2 = gd_share g1)
    (E : Expansion) (ps : list Probe) (B1 B2 : nat -> bool)
    (a : ShareMatrix g1) (tape : Tape (gd_prob g1) * Tape (gd_prob g2))
    : list (Val (gd_share g1)) :=
  let (t1, t2) := tape in
  let a2 : ShareMatrix g2 := fun j k => val_cast (eq_sym Hshare) (a j k) in
  let c_par := combine_circuits (gd_circuit g1) (gd_circuit g2) in
  let ops_par := combine_ops (gd_ops g1)
                   (fun o args =>
                      val_cast Hshare
                        (gd_ops g2 o (map_over (val_cast (eq_sym Hshare)) args))) in
  let st_par := combine_start (wire_count (gd_circuit g1))
                  (gd_start g1 a t1)
                  (fun w2 => val_cast Hshare (gd_start g2 a2 t2 w2)) in
  let asg_par := fun cyc i =>
    combine_assign (gd_assign g1 a t1)
      (fun cyc2 i2 => val_cast Hshare (gd_assign g2 a2 t2 cyc2 i2)) cyc i in
  app (map_over (obs_value (gd_share g1) ops_par c_par st_par asg_par)
                (probe_set E c_par ps))
      (app (output_view g1 B1 a t1)
           (map_over (val_cast Hshare) (output_view g2 B2 a2 t2))).

(*| discharges: R-05-004a, R-15-053a |*)
Theorem pini_par_compose :
  forall (g1 g2 : Gadget) (Hshare : gd_share g2 = gd_share g1)
         (E : Expansion) (d : nat),
    gd_shares g1 = gd_shares g2 ->
    gadget_well_formed g1 ->
    gadget_well_formed g2 ->
    HasCountingMass (gd_prob g1) ->
    HasCountingMass (gd_prob g2) ->
    LocalExpansion E ->
    PINI g1 E d ->
    PINI g2 E d ->
    forall (ps : list Probe) (B1 B2 : nat -> bool),
      wires_exist (combine_circuits (gd_circuit g1) (gd_circuit g2)) (map_over p_wire ps) = true ->
      Nat.leb (count_of ps) d = true ->
      exists I : ShareSet,
        (forall j, (j < gd_inputs g1 \/ j < gd_inputs g2) ->
           Nat.leb (card_in g1 I j) (count_of ps) = true) /\
        (forall a b : ShareMatrix g1,
           (forall j k, (j < gd_inputs g1 \/ j < gd_inputs g2) ->
              k < gd_shares g1 ->
              orb (I j k) (orb (B1 k) (B2 k)) = true -> a j k = b j k) ->
           SameDistribution
             (counting (Tape (gd_prob g1) * Tape (gd_prob g2))
                (list_prod (tape_enum (gd_prob g1)) (tape_enum (gd_prob g2))))
             (list (Val (gd_share g1))) (list_eqb (v_eqb (gd_share g1)))
             (par_split_view g1 g2 Hshare E ps B1 B2 a)
             (par_split_view g1 g2 Hshare E ps B1 B2 b)).
Proof.
  intros g1 g2 Hshare E d Hsh [Hwf1 [Hin1 Hout1]] [Hwf2 [Hin2 Hout2]]
         Hc1 Hc2 Hloc Hpini1 Hpini2 ps B1 B2 Hw Hord.
  destruct g1 as [m1 p1 c1 ops1 in1 sh1 out1 r1 asg1 st1].
  destruct g2 as [m2 p2 c2 ops2 in2 sh2 out2 r2 asg2 st2].
  simpl in *. destruct Hshare. rename m2 into m1. subst sh2.
  set (g1 := {| gd_share := m1; gd_prob := p1; gd_circuit := c1; gd_ops := ops1;
                gd_inputs := in1; gd_shares := sh1; gd_out := out1; gd_read := r1;
                gd_assign := asg1; gd_start := st1 |}).
  set (g2 := {| gd_share := m1; gd_prob := p2; gd_circuit := c2; gd_ops := ops2;
                gd_inputs := in2; gd_shares := sh1; gd_out := out2; gd_read := r2;
                gd_assign := asg2; gd_start := st2 |}).
  destruct (split_probes_wires_exist c1 c2 ps Hw) as [Hw1 Hw2].
  pose proof (split_probes_count (wire_count c1) ps) as Hcnt.
  apply Nat.leb_le in Hord.
  set (ps1 := split_probes_l (wire_count c1) ps).
  set (ps2 := split_probes_r (wire_count c1) ps).
  destruct (Hpini1 ps1 B1 Hw1 ltac:(apply Nat.leb_le; unfold ps1; lia)) as [I1 [Hb1 Hsim1]].
  destruct (Hpini2 ps2 B2 Hw2 ltac:(apply Nat.leb_le; unfold ps2; lia)) as [I2 [Hb2 Hsim2]].
  set (I := fun j k => orb (if Nat.ltb j in1 then I1 j k else false)
                           (if Nat.ltb j in2 then I2 j k else false)).
  exists I. split.
  - intros j Hj. apply Nat.leb_le. unfold I, card_in. simpl.
    set (f1 := fun k => if Nat.ltb j in1 then I1 j k else false).
    set (f2 := fun k => if Nat.ltb j in2 then I2 j k else false).
    pose proof (count_filter_or f1 f2 (upto sh1)) as Hor.
    apply Nat.leb_le in Hor.
    assert (Hext_or : filter_of (fun k => orb (if j <? in1 then I1 j k else false)
                                              (if j <? in2 then I2 j k else false)) (upto sh1) =
                      filter_of (fun a => orb (f1 a) (f2 a)) (upto sh1)).
    { apply filter_of_ext. intros k. unfold f1, f2. reflexivity. }
    rewrite Hext_or.
    assert (Hsub1 : count_of (filter_of f1 (upto sh1)) <= count_of ps1).
    { unfold f1. destruct (Nat.ltb j in1) eqn:Ej1.
      - pose proof (Hb1 j Ej1) as H1. apply Nat.leb_le in H1.
        unfold card_in in H1. simpl in H1.
        replace (filter_of (fun k => I1 j k) (upto sh1))
          with (filter_of (I1 j) (upto sh1)) in * by (apply filter_of_ext; reflexivity).
        exact H1.
      - generalize (upto sh1) as u. intros u.
        induction u as [|x r IH]; simpl; [lia | exact IH]. }
    assert (Hsub2 : count_of (filter_of f2 (upto sh1)) <= count_of ps2).
    { unfold f2. destruct (Nat.ltb j in2) eqn:Ej2.
      - pose proof (Hb2 j Ej2) as H2. apply Nat.leb_le in H2.
        unfold card_in in H2. simpl in H2.
        replace (filter_of (fun k => I2 j k) (upto sh1))
          with (filter_of (I2 j) (upto sh1)) in * by (apply filter_of_ext; reflexivity).
        exact H2.
      - generalize (upto sh1) as u. intros u.
        induction u as [|x r IH]; simpl; [lia | exact IH]. }
    unfold ps1, ps2 in *. lia.
  - intros a b Hagree.
    assert (Hag1 : agree_on g1 (union_shares I1 B1) a b).
    { intros j k Hj Hk HI. unfold g1 in Hj, Hk. simpl in Hj, Hk.
      apply Hagree; [left; apply Nat.ltb_lt; exact Hj | apply Nat.ltb_lt; exact Hk|].
      unfold I, union_shares in *. rewrite Hj in *.
      destruct (I1 j k); destruct (B1 k); simpl in *; try discriminate; auto with bool. }
    assert (Hag2 : agree_on g2 (union_shares I2 B2) a b).
    { intros j k Hj Hk HI. unfold g2 in Hj, Hk. simpl in Hj, Hk.
      apply Hagree; [right; apply Nat.ltb_lt; exact Hj | apply Nat.ltb_lt; exact Hk|].
      unfold I, union_shares in *. rewrite Hj in *.
      destruct (if j <? in1 then I1 j k else false); destruct (I2 j k); destruct (B1 k); destruct (B2 k);
        simpl in *; auto; discriminate. }
    assert (Hops_ext : forall o args,
      combine_ops ops1 (fun o0 args0 => ops2 o0 (map_over (fun x => x) args0)) o args =
      combine_ops ops1 ops2 o args).
    { intros o args. unfold combine_ops. destruct (Nat.even o); [reflexivity|].
      rewrite map_over_id_val. reflexivity. }
    assert (Hpar_eq : forall m_in t1 t2,
      par_split_view g1 g2 eq_refl E ps B1 B2 m_in (t1, t2) =
      app (interleave_obs E c1 c2 ps (internal_view g1 E ps1 m_in t1)
                                      (internal_view g2 E ps2 m_in t2))
          (app (output_view g1 B1 m_in t1) (output_view g2 B2 m_in t2))).
    { intros m_in t1 t2. unfold par_split_view. simpl. f_equal.
      - transitivity
          (map_over (obs_value m1 (combine_ops ops1 ops2) (combine_circuits c1 c2)
                       (combine_start (wire_count c1) (st1 m_in t1) (st2 m_in t2))
                       (fun cyc => combine_assign (asg1 m_in t1) (asg2 m_in t2) cyc))
                    (probe_set E (combine_circuits c1 c2) ps)).
        + apply support_map_ext. intros o _.
          destruct o as [w t|w t]; simpl;
            [apply value_at_ops_ext; exact Hops_ext |
             f_equal; apply value_at_ops_ext; exact Hops_ext].
        + exact (interleave_internal_view E Hloc m1 ops1 ops2 c1 c2
                   (st1 m_in t1) (st2 m_in t2) (asg1 m_in t1) (asg2 m_in t2) ps
                   Hwf1 Hwf2 Hw).
      - f_equal. apply map_over_id_val. }
    set (mid_fn := fun '(t1, t2) =>
      app (interleave_obs E c1 c2 ps (internal_view g1 E ps1 a t1)
                                      (internal_view g2 E ps2 b t2))
          (app (output_view g1 B1 a t1) (output_view g2 B2 b t2))).
    assert (Hstep1 : SameDistribution
      (counting (Tape p1 * Tape p2) (list_prod (tape_enum p1) (tape_enum p2)))
      (list (Val m1)) (list_eqb (v_eqb m1))
      (par_split_view g1 g2 eq_refl E ps B1 B2 a) mid_fn).
    { apply counting_prod_right. intros t1 _.
      pose proof (Hc2 _ (list_eqb (v_eqb m1)) _ _ (Hsim2 a b Hag2)) as Hdist2.
      set (n_int2 := count_of (probe_set E c2 ps2)).
      set (lift2 := fun (sv2 : list (Val m1)) =>
        app (interleave_obs E c1 c2 ps (internal_view g1 E ps1 a t1)
               (ProofSupport.take_of n_int2 sv2))
            (app (output_view g1 B1 a t1) (ProofSupport.drop_of n_int2 sv2))).
      assert (Hlift2_a : forall t2,
        lift2 (split_view g2 E ps2 B2 a t2) =
        par_split_view g1 g2 eq_refl E ps B1 B2 a (t1, t2)).
      { intros t2. rewrite Hpar_eq. unfold lift2, split_view. cbv beta.
        destruct (take_drop_exact n_int2 (internal_view g2 E ps2 a t2) (output_view g2 B2 a t2)
                    ltac:(unfold internal_view, n_int2; repeat rewrite count_of_is_length;
                          rewrite map_over_is_map, length_map; reflexivity))
          as [Ht Hd]. f_equal; [f_equal; exact Ht | f_equal; exact Hd]. }
      assert (Hlift2_b : forall t2,
        lift2 (split_view g2 E ps2 B2 b t2) = mid_fn (t1, t2)).
      { intros t2. unfold lift2, mid_fn, split_view. cbv beta.
        destruct (take_drop_exact n_int2 (internal_view g2 E ps2 b t2) (output_view g2 B2 b t2)
                    ltac:(unfold internal_view, n_int2; repeat rewrite count_of_is_length;
                          rewrite map_over_is_map, length_map; reflexivity))
          as [Ht Hd]. f_equal; [f_equal; exact Ht | f_equal; exact Hd]. }
      intros o.
      eapply eq_trans; [|eapply eq_trans; [exact (counting_pushforward (Tape p2) (tape_enum p2)
        (list (Val m1)) (list (Val m1)) (list_eqb (v_eqb m1)) (list_eqb (v_eqb m1))
        (split_view g2 E ps2 B2 a) (split_view g2 E ps2 B2 b) lift2
        (list_eqb_sound m1) (list_eqb_refl_sharing m1) Hdist2 o)|]].
      - apply pr_ext. intros t2. rewrite Hlift2_a. reflexivity.
      - apply pr_ext. intros t2. rewrite Hlift2_b. reflexivity. }
    assert (Hstep2 : SameDistribution
      (counting (Tape p1 * Tape p2) (list_prod (tape_enum p1) (tape_enum p2)))
      (list (Val m1)) (list_eqb (v_eqb m1))
      mid_fn (par_split_view g1 g2 eq_refl E ps B1 B2 b)).
    { apply counting_prod_left. intros t2 _.
      pose proof (Hc1 _ (list_eqb (v_eqb m1)) _ _ (Hsim1 a b Hag1)) as Hdist1.
      set (n_int1 := count_of (probe_set E c1 ps1)).
      set (lift1 := fun (sv1 : list (Val m1)) =>
        app (interleave_obs E c1 c2 ps (ProofSupport.take_of n_int1 sv1)
               (internal_view g2 E ps2 b t2))
            (app (ProofSupport.drop_of n_int1 sv1) (output_view g2 B2 b t2))).
      assert (Hlift1_a : forall t1,
        lift1 (split_view g1 E ps1 B1 a t1) = mid_fn (t1, t2)).
      { intros t1. unfold lift1, mid_fn, split_view. cbv beta.
        destruct (take_drop_exact n_int1 (internal_view g1 E ps1 a t1) (output_view g1 B1 a t1)
                    ltac:(unfold internal_view, n_int1; repeat rewrite count_of_is_length;
                          rewrite map_over_is_map, length_map; reflexivity))
          as [Ht Hd]. f_equal; [f_equal; exact Ht | f_equal; exact Hd]. }
      assert (Hlift1_b : forall t1,
        lift1 (split_view g1 E ps1 B1 b t1) =
        par_split_view g1 g2 eq_refl E ps B1 B2 b (t1, t2)).
      { intros t1. rewrite Hpar_eq. unfold lift1, split_view. cbv beta.
        destruct (take_drop_exact n_int1 (internal_view g1 E ps1 b t1) (output_view g1 B1 b t1)
                    ltac:(unfold internal_view, n_int1; repeat rewrite count_of_is_length;
                          rewrite map_over_is_map, length_map; reflexivity))
          as [Ht Hd]. f_equal; [f_equal; exact Ht | f_equal; exact Hd]. }
      intros o.
      eapply eq_trans; [|eapply eq_trans; [exact (counting_pushforward (Tape p1) (tape_enum p1)
        (list (Val m1)) (list (Val m1)) (list_eqb (v_eqb m1)) (list_eqb (v_eqb m1))
        (split_view g1 E ps1 B1 a) (split_view g1 E ps1 B1 b) lift1
        (list_eqb_sound m1) (list_eqb_refl_sharing m1) Hdist1 o)|]].
      - apply pr_ext. intros t1. rewrite Hlift1_a. reflexivity.
      - apply pr_ext. intros t1. rewrite Hlift1_b. reflexivity. }
    intros o. exact (eq_trans (Hstep1 o) (Hstep2 o)).
Qed.

(* Uniform-domain PINI (`StrongPINI`), where the same share-index set I_dom
   covers all inputs and therefore composes across arbitrary DAGs with fan-out. *)
Definition StrongPINI (g : Gadget) (E : Expansion) (d : nat) : Prop :=
  forall (ps : list Probe) (B : nat -> bool),
    wires_exist (gd_circuit g) (map_over p_wire ps) = true ->
    Nat.leb (count_of ps) d = true ->
    exists I_dom : nat -> bool,
      Nat.leb (count_of (filter_of I_dom (upto (gd_shares g)))) (count_of ps) = true /\
      SimulableFrom g (union_shares (fun _ k => I_dom k) B) (split_view g E ps B).

(*| discharges: R-05-004a, R-15-053a |*)
Theorem strong_pini_implies_pini :
  forall (g : Gadget) (E : Expansion) (d : nat),
    StrongPINI g E d -> PINI g E d.
Proof.
  intros g E d Hs ps B Hw Hord.
  destruct (Hs ps B Hw Hord) as [I_dom [Hcnt Hsim]].
  exists (fun _ k => I_dom k). split; [|exact Hsim].
  intros j _. exact Hcnt.
Qed.






