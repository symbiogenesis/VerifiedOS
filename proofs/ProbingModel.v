(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ProbingModel.v

   A gate-level functional model with stable, glitch, transition-pair and
   difference-only observations. The robust expansion follows transitive
   combinational dependencies and observes both sides of a register boundary.
   Physical probe locations are counted before that expansion. Fixed probe
   lists carry cycles; this does not make their choices adaptive. ProbeStrategy
   separately represents value-dependent choices and has a budget theorem,
   but the fixed-list security lemmas are not an adaptive-security theorem.

   R-15-053a and R-17-058a leave the model's faithfulness to silicon as a
   physical premise. No theorem here establishes a netlist, layout, measured
   leakage, delay/coupling bound or resistance outside the model. The DRBG's
   computational connection to independent uniform masks is not proved.
   R-17-058d's combined fault reduction and the arithmetic and Boolean gadget
   composition theorems are separate work. See the committed acceptance
   contract docs/assurance/probing-model-contract.md and U-20.

   Probability is a finite weighted-mass interface, with commutative-monoid
   laws as record fields. It alone neither normalizes nor excludes zero mass.
   FiniteMassQualification adds an order, nonnegative masses, a total weight
   and a nonzero normalizer. Counting over the Cartesian mask enumeration is
   inhabited and has a proved positive denominator. Security below is exact
   equality of finite outcome weights, and the general d-share result also
   equates normalized numerator/denominator pairs. This is original finite
   algebra, not an imported or qualified SSProve/FCF probability development.
   Inspection of the locked installed switch found only the documented Rocq
   core/stdlib/stdpp closure, with no probability or game library. U-20 still
   owns any external foundation adapter and its assumption/normalization audit.

   The general additive-encoding theorem uses n independent masks and n+1
   shares in an arbitrary enumerated finite abelian group. Every valid probe
   list of length at most n has the same distribution for any two secrets.
   If it observes the completing share, a constructive missing-index argument
   identifies a mask to reindex by the secret difference. This includes the
   baseline completing-share case; it is not deferred to gadget composition.
   The whole encoding recovers the secret, so the bound has a refuting case.

   NI, SNI and PINI are distinct local simulation predicates. The proved
   implication to NI carries each definition's stated side conditions.
   Naming PINI does not prove that arbitrary gadgets compose. Its selection,
   the order/share-count convention and the transition-pair observation are
   explicit semantic proposals for the register owner. The difference-only
   arm has a separating witness whose register holds the secret from its
   initial state; initializing it to zero would itself create a leaking
   transition. Constant/copy gadgets are model witnesses, not shipped masking
   hardware. Observation equality uses Sharing's sound and reflexive test.

   The proofs use the Rocq prelude and, for general finite enumeration, the
   standard List/Arith/Lia modules. No global axioms or admitted proofs are
   introduced. Native inventory and assumption audit, not these footer
   commands or the existence of an inhabitant alone, determine proof evidence.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-004a R-05-163 R-05-164 R-05-165 R-05-166 R-15-053a R-15-108 R-17-058a
      R-17-058d
   SHA256: 9a59702b137e4363172a2da2b9206af3b4fba6550be345cb7f6c138533d85c16
   (*| END derived |*)
   ========================================================================= *)

(* -------------------------------------------------------------------------
   Local list, boolean and arithmetic helpers. The general enumeration
   proofs below also use the standard List, Arith and Lia modules.
   ------------------------------------------------------------------------- *)

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

Fixpoint flat_map_over {A B : Type} (f : A -> list B) (l : list A) : list B :=
  match l with nil => nil | cons x r => app (f x) (flat_map_over f r) end.

(* 0 through n-1, in that order. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

(* The nth member of a list, or the declared fallback past its end. Reading
   11 is what the fallback is for: it makes the lookup total and is not a
   claim about a wire the circuit does not carry, which `wires_exist`
   excludes instead. *)
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

Definition bool_eqb (a b : bool) : bool := if a then b else negb b.

Fixpoint list_eqb {A : Type} (eqb : A -> A -> bool) (l1 l2 : list A) : bool :=
  match l1, l2 with
  | nil, nil => true
  | cons x r1, cons y r2 => andb (eqb x y) (list_eqb eqb r1 r2)
  | _, _ => false
  end.

Definition prev_cycle (t : nat) : nat := match t with 0 => 0 | S k => k end.

(* -------------------------------------------------------------------------
   The arithmetic this file needs, proved rather than imported: the stdlib
   modules carrying it are outside the prelude, and adding zero axioms is
   the point of the gate.
   ------------------------------------------------------------------------- *)

Lemma eqb_refl_nat : forall n : nat, Nat.eqb n n = true.
Proof. induction n as [ | n IH ]; simpl; [ reflexivity | exact IH ]. Qed.

Lemma eqb_sound_nat : forall a b : nat, Nat.eqb a b = true -> a = b.
Proof.
  induction a as [ | a IH ]; intros b H.
  - destruct b as [ | b ]; [ reflexivity | discriminate H ].
  - destruct b as [ | b ]; [ discriminate H | ].
    simpl in H. rewrite (IH b H). reflexivity.
Qed.

Lemma add_zero_r_nat : forall n : nat, Nat.add n 0 = n.
Proof.
  induction n as [ | n IH ]; simpl; [ reflexivity | rewrite IH; reflexivity ].
Qed.

Lemma add_zero_l_nat : forall n : nat, Nat.add 0 n = n.
Proof. intros n. reflexivity. Qed.

Lemma add_succ_r_nat : forall n k : nat, Nat.add n (S k) = S (Nat.add n k).
Proof.
  induction n as [ | n IH ]; intros k; simpl;
    [ reflexivity | rewrite IH; reflexivity ].
Qed.

Lemma add_comm_nat : forall a b : nat, Nat.add a b = Nat.add b a.
Proof.
  induction a as [ | a IH ]; intros b; simpl.
  - rewrite add_zero_r_nat. reflexivity.
  - rewrite IH. rewrite add_succ_r_nat. reflexivity.
Qed.

Lemma add_assoc_nat :
  forall a b c : nat, Nat.add a (Nat.add b c) = Nat.add (Nat.add a b) c.
Proof.
  induction a as [ | a IH ]; intros b c; simpl;
    [ reflexivity | rewrite IH; reflexivity ].
Qed.

Lemma leb_refl_nat : forall n : nat, Nat.leb n n = true.
Proof. induction n as [ | n IH ]; simpl; [ reflexivity | exact IH ]. Qed.

Lemma leb_trans_nat :
  forall a b c : nat, Nat.leb a b = true -> Nat.leb b c = true ->
    Nat.leb a c = true.
Proof.
  induction a as [ | a IH ]; intros b c H1 H2.
  - reflexivity.
  - destruct b as [ | b ]; [ discriminate H1 | ].
    destruct c as [ | c ]; [ discriminate H2 | ].
    simpl in H1. simpl in H2. simpl. exact (IH b c H1 H2).
Qed.

Lemma leb_succ_r_nat :
  forall a b : nat, Nat.leb a b = true -> Nat.leb a (S b) = true.
Proof.
  induction a as [ | a IH ]; intros b H.
  - reflexivity.
  - destruct b as [ | b ]; [ discriminate H | ].
    simpl in H. simpl. exact (IH b H).
Qed.

Lemma leb_add_r_nat : forall a b : nat, Nat.leb a (Nat.add a b) = true.
Proof.
  induction a as [ | a IH ]; intros b; simpl; [ reflexivity | exact (IH b) ].
Qed.

Lemma leb_drop_left : forall a b, Nat.leb (S a) b = true -> Nat.leb a b = true.
Proof.
  induction a; intros b H; [reflexivity|].
  destruct b; [discriminate H|]. simpl in *. exact (IHa b H).
Qed.

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
Proof.
  intros A p q l H. induction l as [ | x r IH ]; simpl; intros Hall.
  - reflexivity.
  - destruct (p x) eqn:Ex.
    + rewrite (H x Ex). simpl. exact (IH Hall).
    + discriminate Hall.
Qed.

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

Lemma count_of_map_over :
  forall {A B : Type} (f : A -> B) (l : list A),
    count_of (map_over f l) = count_of l.
Proof.
  intros A B f l. induction l as [ | x r IH ]; simpl;
    [ reflexivity | rewrite IH; reflexivity ].
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
  - simpl. destruct (p y); destruct (p x).
    + apply perm_swap.
    + apply perm_refl.
    + apply perm_refl.
    + apply perm_refl.
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
   The probabilistic interface, U-20's missing input stated as a record of
   hypotheses rather than axiomatized. A sample space with a finite
   enumeration, a mass on each point, and a commutative monoid to add
   masses in. Nothing more is assumed, and the three laws are what the
   re-randomization lemma below actually consumes.
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

Lemma pr_ext :
  forall (p : Probability) (q1 q2 : Tape p -> bool),
    (forall t : Tape p, q1 t = q2 t) -> pr p q1 = pr p q2.
Proof.
  intros p q1 q2 H. unfold pr. rewrite (filter_of_ext q1 q2 (tape_enum p) H).
  reflexivity.
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
  intros p sigma q Hmass Hperm. unfold pr.
  rewrite (map_over_ext (mass p) (fun t => mass p (sigma t))
             (filter_of (fun t => q (sigma t)) (tape_enum p))
             (fun t => eq_sym (Hmass t))).
  rewrite <- (map_over_compose (mass p) sigma
                (filter_of (fun t => q (sigma t)) (tape_enum p))).
  rewrite (map_filter_comm sigma q (tape_enum p)).
  apply fold_mass_perm.
  apply perm_map. apply perm_filter. exact Hperm.
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

(*| discharges: R-15-053a |*)
Theorem rerandomization_hides :
  forall (p : Probability) (O : Type) (oeqb : O -> O -> bool)
         (f g : Tape p -> O) (sigma : Tape p -> Tape p),
    (forall t : Tape p, mass p (sigma t) = mass p t) ->
    Perm (map_over sigma (tape_enum p)) (tape_enum p) ->
    (forall t : Tape p, g (sigma t) = f t) ->
    SameDistribution p O oeqb f g.
Proof.
  intros p O oeqb f g sigma Hmass Hperm Hg o.
  rewrite <- (reindexing_preserves_probability p sigma
                (fun t => oeqb (g t) o) Hmass Hperm).
  apply pr_ext. intros t. rewrite (Hg t). reflexivity.
Qed.

(* -------------------------------------------------------------------------
   The uniform counting measure over a finite enumerated sample space: an
   inhabitant of the interface, and the premise R-05-004a's masking
   theorems take. A foundation U-20 later qualifies enters the same way.
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
   The sharing algebra: reading 2. An arbitrary finite abelian group whose
   carrier is enumerated once and is invariant under translation, which is
   what a uniform mask needs and all a uniform mask needs. GF(2)
   instantiates it below; a prime field instantiates it for the arithmetic
   composition half.
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
   The gate-level circuit (reading 1) and its trace semantics. A wire is an
   index into the gate list and the gate at that index drives it.
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
  fun w => match gate_at c w with
           | g_reg s => eval_wire m ops c regs ins (wire_count c) s
           | _ => regs w
           end.

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
      assert (Hargs : all_of (fun b => Nat.ltb b w) args
                      = true)
        by exact (well_formed_gate_reads_earlier_wires c w o args Hwf Hc Eg).
      assert (Haw : Nat.ltb a w = true)
        by exact (all_of_mem_nat (fun b => Nat.ltb b w) args a Hargs Ha).
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
   Observations and the three probe expansions (readings 3, 4 and 5).
   ========================================================================= *)

Inductive Obs : Type :=
  | obs_at (w : nat) (t : nat)      (* the stable value of wire w at cycle t *)
  | obs_delta (w : nat) (t : nat).  (* the difference across one cycle
                                       boundary at wire w, the difference-only
                                       transition reading of gap c           *)

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

Lemma obs_eqb_refl : forall o : Obs, obs_eqb o o = true.
Proof.
  intros o. destruct o as [ w t | w t ]; simpl;
    rewrite eqb_refl_nat; rewrite eqb_refl_nat; reflexivity.
Qed.

Lemma mem_obs_app :
  forall (o : Obs) (l1 l2 : list Obs),
    mem_obs o (app l1 l2) = orb (mem_obs o l1) (mem_obs o l2).
Proof.
  intros o l1 l2. induction l1 as [ | x r IH ]; simpl.
  - reflexivity.
  - rewrite IH. destruct (obs_eqb o x); reflexivity.
Qed.

Definition obs_value (m : Sharing) (ops : nat -> list (Val m) -> Val m)
    (c : Circuit) (init : nat -> Val m) (ins : nat -> nat -> Val m)
    (o : Obs) : Val m :=
  match o with
  | obs_at w t => value_at m ops c init ins t w
  | obs_delta w t =>
      v_sub m (value_at m ops c init ins t w)
              (value_at m ops c init ins (prev_cycle t) w)
  end.

(* The glitch walk of reading 3: back through combinational gates, stopping
   at a register output and at a primary input. A gate with no arguments is
   a constant and contributes nothing, which is the correct answer and not
   a gap in the walk. *)
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

(* The glitch extension (reading 3). *)
Definition ex_glitch : Expansion :=
  fun c p => map_over (fun s => obs_at s (p_cycle p))
                      (stable_sources c (wire_count c) (p_wire p)).

(* The transition extension, pair reading (reading 4). *)
Definition ex_transition : Expansion :=
  fun _ p => cons (obs_at (p_wire p) (p_cycle p))
                  (cons (obs_at (p_wire p) (prev_cycle (p_cycle p))) nil).

(* The transition extension, difference-only reading: the other arm of
   gap c, carried so the choice can be seen rather than assumed. *)
Definition ex_transition_delta : Expansion :=
  fun _ p => cons (obs_delta (p_wire p) (p_cycle p)) nil.

(* THE MODEL R-15-053a FIXES: both extensions at once (reading 5). Each
   stable source of the probed wire is observed at the probed cycle and at
   the cycle before it. *)
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
  match gate_at c s with
  | g_in i => ins i
  | _ => regs s
  end.

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
    + assert (Hw : stable_value m c regs ins w
                   = stable_value m c regs' ins' w).
      { apply H. simpl. rewrite Eg. simpl. rewrite eqb_refl_nat. reflexivity. }
      unfold stable_value in Hw. rewrite Eg in Hw. exact Hw.
    + assert (Hw : stable_value m c regs ins w
                   = stable_value m c regs' ins' w).
      { apply H. simpl. rewrite Eg. simpl. rewrite eqb_refl_nat. reflexivity. }
      unfold stable_value in Hw. rewrite Eg in Hw. exact Hw.
    + f_equal. apply map_over_ext_nat. intros a Ha.
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
   An experiment: a circuit with a secret, an input assignment that folds
   the secret and the randomness into the primary inputs, and a probe
   budget. `x_order` is the probe budget and never the share count
   (reading 10).
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

(* d-PROBING SECURITY, the statement R-15-053a fixes and R-05-004a's
   masking theorems are verified against: no admissible probe set of at
   most d probes distinguishes two secrets, perfectly (reading 8), under
   the expansion the model names. *)
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
   R-15-108's to select and is a variable here (gap d).
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
  match k with 0 => r | _ => v_sub m s r end.

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
   The composition notions (reading 9). All three are stated over one view
   so that the ladder beneath them is an inclusion of bounds rather than a
   comparison of differently shaped objects: a probe split is a list of
   internal probes and a set of output-share indices, and the view is the
   internal observations followed by the selected output shares.
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

(* Reading 10 as a predicate this file states rather than asserts: the
   convention under which R-05-004a's one letter carries both quantities. *)
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

(* Reading 12: simulability stated as dependence. *)
Definition SimulableFrom (g : Gadget) (I : ShareSet)
    (f : ShareMatrix g -> Tape (gd_prob g) -> list (Val (gd_share g)))
    : Prop :=
  forall a b : ShareMatrix g, agree_on g I a b ->
    SameDistribution (gd_prob g) (list (Val (gd_share g)))
      (list_eqb (v_eqb (gd_share g))) (f a) (f b).

(* The direction of reading 12 that needs proving: a view that depends only
   on I is reproduced by a term that reads only I, which is the simulator a
   simulation-based definition would existentially quantify. The completion
   is the share matrix that agrees with `a` on I and is zero elsewhere. *)
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
  intros j k Hj Hk HI. unfold restrict_to. rewrite HI. reflexivity.
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

(* Operation 0 is the constant-zero gate and every other index is the XOR
   of the gate's arguments. Which operations the alphabet carries is a
   field of the model (reading 1); these two are what the witnesses need. *)
Definition gf2_ops (o : nat) (args : list bool) : bool :=
  match o with
  | 0 => false
  | _ => xor_fold args
  end.

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

(* The composed extension inherits the leak, which is reading 5 made
   checkable: a model carrying both extensions refuses what either refuses.
*)
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
            match t with
            | 0 => bit_at tape 0
            | _ => xorb s (bit_at tape 0)
            end;
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
   Gap c made checkable: the two transition readings are not two spellings
   of one model. A register holding the unmasked secret across a cycle
   boundary is a leak under the pair reading and is invisible under the
   difference-only one, because the difference is zero exactly where the
   value is constant.
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
   The composition notions are inhabited, and they are not one predicate.

   The constant gadget satisfies all three at every order, which closes
   R-05-165's unsatisfiable-premise case for NI, SNI and PINI at once. The
   copy gadget is refused by SNI at exactly the split where PINI's
   obligation is met, which is the separation reading 9 rests on: the two
   notions differ at the output boundary and the difference is observable.
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
  intros g n j Hj. unfold card_in. unfold empty_shares.
  assert (Hf : filter_of (fun _ : nat => false) (upto (gd_shares g)) = nil).
  { generalize (upto (gd_shares g)). intros l.
    induction l as [ | x r IH ]; simpl; [ reflexivity | exact IH ]. }
  rewrite Hf. reflexivity.
Qed.

(*| discharges: R-05-165 |*)
Theorem the_constant_gadget_satisfies_all_three_notions :
  forall (E : Expansion) (d : nat),
    NI constant_gadget E d /\ SNI constant_gadget E d
    /\ PINI constant_gadget E d.
Proof.
  intros E d. split; [ | split ].
  - intros ps B Hw Hs. exists empty_shares. split.
    + apply empty_shares_are_bounded.
    + intros a b _. apply identical_views_are_identically_distributed.
      intros tape. apply constant_gadget_view_ignores_its_inputs.
  - intros ps B Hw Hs. exists empty_shares. split.
    + apply empty_shares_are_bounded.
    + intros a b _. apply identical_views_are_identically_distributed.
      intros tape. apply constant_gadget_view_ignores_its_inputs.
  - intros ps B Hw Hs. exists empty_shares. split.
    + apply empty_shares_are_bounded.
    + intros a b _. apply identical_views_are_identically_distributed.
      intros tape. apply constant_gadget_view_ignores_its_inputs.
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

(* The same gadget, the same split, and PINI's obligation met: the output
   share at index 0 is simulated from input share 0, which is exactly what
   PINI grants and SNI refuses. The two notions are therefore not one
   predicate, and reading 9's selection is a choice with consequences. *)
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
    assert (H00 : a 0 0 = b 0 0).
    { apply Hagree; reflexivity. }
    unfold split_view. unfold internal_view. unfold output_view. simpl.
    change (cons (a 0 0) nil = cons (b 0 0) nil).
    rewrite H00. reflexivity.
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
   Reading 10 made checkable: the two conventions are different arithmetic,
   so one letter cannot carry both without an entry saying which (gap b).
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

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared set
   R-05-164 currently makes empty, so "Closed under the global context" is
   that emptiness checked mechanically. A probing model resting on an
   undeclared probability axiom would be the exact defect R-05-164's
   acceptance clause names, which is why the interface above is a record.
   ------------------------------------------------------------------------- *)

Print Assumptions pr.
Print Assumptions SameDistribution.
Print Assumptions reindexing_preserves_probability.
Print Assumptions rerandomization_hides.
Print Assumptions a_degenerate_equality_test_hides_every_difference.
Print Assumptions identical_views_are_identically_distributed.
Print Assumptions equal_image_multisets_are_identically_distributed.
Print Assumptions the_soundness_law_refuses_a_degenerate_equality_test.
Print Assumptions well_formed_gate_reads_earlier_wires.
Print Assumptions eval_fuel_irrelevant.
Print Assumptions stable_sources_determine_the_probed_value.
Print Assumptions robust_expansion_contains_the_glitch_expansion.
Print Assumptions ProbingSecure.
Print Assumptions Leaks.
Print Assumptions the_whole_sharing_recovers_the_secret.
Print Assumptions masks_alone_carry_no_secret.
Print Assumptions two_share_encoding_hides_the_secret.
Print Assumptions NI.
Print Assumptions SNI.
Print Assumptions PINI.
Print Assumptions dependence_yields_a_simulator.
Print Assumptions sni_implies_ni.
Print Assumptions pini_implies_ni.
Print Assumptions an_unmasked_wire_is_a_leak.
Print Assumptions one_share_of_a_secret_is_not_a_leak.
Print Assumptions a_glitch_extended_probe_is_a_leak.
Print Assumptions the_stable_probe_on_that_wire_is_not_a_leak.
Print Assumptions glitch_probe_sees_strictly_more_than_the_stable_probe.
Print Assumptions the_robust_expansion_inherits_the_glitch_leak.
Print Assumptions a_transition_probe_on_a_reused_register_is_a_leak.
Print Assumptions the_stable_probe_on_that_register_is_not_a_leak.
Print Assumptions a_transition_probe_on_a_held_register_is_not_a_leak.
Print Assumptions the_two_transition_readings_disagree.
Print Assumptions the_constant_gadget_satisfies_all_three_notions.
Print Assumptions copy_gadget_refutes_sni.
Print Assumptions copy_gadget_meets_the_pini_obligation_where_sni_fails.
Print Assumptions three_shares_hide_the_secret_from_the_two_masks.
Print Assumptions three_shares_hide_the_secret_from_a_mask_and_the_last_share.
Print Assumptions three_shares_are_recovered_by_the_whole_sharing.
Print Assumptions the_two_order_conventions_are_not_the_same_number.

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
  intros A B f a b H. induction H; simpl.
  - apply perm_refl.
  - apply perm_append_left. exact IHPerm.
  - repeat rewrite app_assoc. apply perm_append_right. apply perm_app_comm.
  - eapply perm_trans; eauto.
Qed.

Lemma perm_flat_map_pointwise : forall {A B} (f g : A -> list B) a,
  (forall x, In x a -> Perm (f x) (g x)) ->
  Perm (flat_map f a) (flat_map g a).
Proof.
  intros A B f g a. induction a; intros H; simpl.
  - apply perm_refl.
  - eapply perm_trans.
    + apply perm_append_right. apply H. left. reflexivity.
    + apply perm_append_left. apply IHa. intros. apply H. right. assumption.
Qed.

Lemma map_flatten : forall {A B C} (f : B -> C) (g : A -> list B) a,
  map f (flat_map g a) = flat_map (fun x => map f (g x)) a.
Proof. intros A B C f g a. induction a; simpl; auto. rewrite map_app, IHa. reflexivity. Qed.

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
  intros m i delta xs. revert i. induction xs; intros [|i] H; simpl in *; try lia.
  - symmetry. apply v_add_assoc.
  - rewrite IHxs by lia. rewrite (v_add_assoc m a delta (sum_of m xs)).
    rewrite (v_add_comm m a delta). symmetry. apply v_add_assoc.
Qed.

Lemma shift_mask_other : forall m i j delta xs,
  i <> j -> nth j (shift_mask m i delta xs) (v_zero m) = nth j xs (v_zero m).
Proof.
  intros m i j delta xs. revert i j.
  induction xs; intros [|i] [|j] H; simpl; try reflexivity; try congruence.
  apply IHxs. congruence.
Qed.

Lemma mask_tuples_length : forall m n xs,
  In xs (mask_tuples m n) -> length xs = n.
Proof.
  intros m n. induction n; intros xs H.
  - simpl in H. destruct H as [<-|H]; [reflexivity|contradiction].
  - apply in_flat_map in H. destruct H as [x [Hx H]].
    apply in_map_iff in H. destruct H as [r [<- Hr]]. simpl. f_equal. apply IHn. exact Hr.
Qed.

Lemma shift_mask_permutation : forall m n i delta,
  i < n -> Perm (map (shift_mask m i delta) (mask_tuples m n)) (mask_tuples m n).
Proof.
  intros m n. induction n; intros [|i] delta H; try lia;
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
    change (Perm (map (fun xs => share_view m idxs (encode m s1 xs)) (mask_tuples m n))
                 (map (fun xs => share_view m idxs (encode m s2 xs)) (mask_tuples m n))).
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
   these extra laws. The legacy Probability record alone does not assert
   them. A qualified external probability adapter still belongs to U-20. *)
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
  intros. rewrite counting_pr. induction enum; simpl; auto.
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
  intros. split.
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
  induction fuel; intros; [reflexivity|].
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
  - intros ps H s1 s2. apply one_share_of_a_secret_is_not_a_leak.
Qed.

Example four_shares_and_three_probes_have_a_positive_normalizer :
  normalized_counting_observation (mask_tuples gf2 3) (list_eqb bool_eqb)
    (fun xs => share_view gf2 (0 :: 2 :: 3 :: nil) (encode gf2 true xs))
    (false :: true :: false :: nil) = (1, 8).
Proof. reflexivity. Qed.
