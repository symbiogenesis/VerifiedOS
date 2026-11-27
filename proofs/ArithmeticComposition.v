(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ArithmeticComposition.v

   Prime-field (`Z/pZ`) additive sharing and `k`-stage mask-refresh pipeline
   over [ProbingModel.v](ProbingModel.v)'s finite probing interfaces (R-05-004a,
   R-15-053a, R-17-058a, R-17-058d).

   What this file proves:
   1. `Z/pZ` as a finite carrier with decidable equality, duplicate-free
     enumeration, and abelian-group laws inhabiting
     [ProbingModel.v](ProbingModel.v)'s `Sharing` record, plus multiplicative
     invertibility for prime moduli (`p = 5`) contrasted with composite moduli
     (`m = 4`).
   2. A `k`-stage refresh pipeline over a flat tape of `(k + 1) * n` field
     elements, where stage `0` is an additive encoding and each subsequent stage
     refreshes the previous tuple while preserving the shared secret sum.
   3. Exact preimage cardinality for any single-wire observation (`p` times the
     observation preimage count equals `p^((k + 1) * n)`), secret-independent
     outcome weights across all stages, and a completing-share refutation showing
     tightness.

   Scope and open boundaries (R-05-163, R-05-164, R-05-165, R-05-166):
   - The pipeline models algebraic stage refreshes under fixed (non-adaptive)
     single-wire observations and arbitrary-order share observations; glitch
     and transition extensions (`ex_stable` vs. full robust probing), netlist
     gate evaluation (`the_algebraic_pipeline_is_not_a_netlist_claim`),
     masked-datapath refinement (R-05-004a), combined fault-and-probing
     reductions (R-17-058d), and physical layout residuals (R-17-058a) remain
     with their respective owners.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-004a R-05-163 R-05-164 R-05-165 R-05-166 R-15-053a R-17-058a R-17-058d
   SHA256: 63e3507bd3ebabe7aa071f95df5b56632855ea2ba5a13cb03e70358c8e14d5fa
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import List Arith Lia Bool Eqdep_dec.
From Stdlib Require Permutation.
Require Import ProbingModel.

(* =========================================================================
   1. The modulus, its primality predicate, and what each one carries.
   ========================================================================= *)

(* Every candidate divisor strictly between one and p, which is the whole of
   what trial division has to rule out for a modulus that is at least two. *)
Definition trial_divisors (p : nat) : list nat :=
  filter (fun d => Nat.ltb 1 d) (seq 0 p).

Definition primeb (p : nat) : bool :=
  andb (Nat.leb 2 p)
       (forallb (fun d => negb (Nat.eqb (Nat.modulo p d) 0)) (trial_divisors p)).

(* The modulus carries only the bound the additive theory consumes. *)
Record Modulus : Type := {
  pm_mod : nat;
  pm_two : Nat.leb 2 pm_mod = true
}.

(* Primality is a separate record on purpose: the masking theorems below
   quantify over `Modulus` and never over this one, which is the honest
   statement of what the arithmetic half rests on. *)
Record PrimeModulus : Type := {
  pm_base : Modulus;
  pm_prime : primeb (pm_mod pm_base) = true
}.

Lemma modulus_at_least_two : forall P : Modulus, 2 <= pm_mod P.
Proof. intros P. apply Nat.leb_le. exact (pm_two P). Qed.

Lemma modulus_positive : forall P : Modulus, 0 < pm_mod P.
Proof. intros P. pose proof (modulus_at_least_two P). lia. Qed.

(* The trial divisor list contains every candidate in [2, p). *)
(*| discharges: R-05-166 |*)
Theorem primeb_refuses_every_proper_divisor :
  forall (p d : nat), primeb p = true -> 2 <= d -> d < p -> Nat.modulo p d <> 0.
Proof.
  intros p d Hp H2 Hlt.
  unfold primeb in Hp. apply andb_prop in Hp. destruct Hp as [_ Hall].
  assert (Hin : In d (trial_divisors p)).
  { unfold trial_divisors. apply filter_In. split.
    - apply in_seq. lia.
    - apply Nat.ltb_lt. lia. }
  pose proof (proj1 (forallb_forall _ _) Hall d Hin) as Hd.
  cbv beta in Hd. intros E. rewrite E in Hd. simpl in Hd. discriminate Hd.
Qed.

(*| discharges: R-05-165 |*)
Example five_is_prime_and_four_is_not : (primeb 5, primeb 4) = (true, false).
Proof. reflexivity. Qed.

(* =========================================================================
   2. The carrier: residues below p, with the bound carried as a decidable
   proposition so that equality is decided by the representative alone.
   ========================================================================= *)

Record Fp (P : Modulus) : Type := mk_fp {
  fp_rep : nat;
  fp_bounded : Nat.ltb fp_rep (pm_mod P) = true
}.

Arguments mk_fp {P} _ _.
Arguments fp_rep {P} _.
Arguments fp_bounded {P} _.

Lemma fp_rep_lt : forall (P : Modulus) (a : Fp P), fp_rep a < pm_mod P.
Proof. intros P a. apply Nat.ltb_lt. exact (fp_bounded a). Qed.

(* Two residues with one representative are one residue. The bound lives in
   a type with decidable equality, so this is the constructive uniqueness
   result rather than an axiom about proofs. *)
Lemma fp_eq_rep : forall (P : Modulus) (a b : Fp P), fp_rep a = fp_rep b -> a = b.
Proof.
  intros P [ra pa] [rb pb] H. simpl in H. subst rb.
  f_equal. apply (@UIP_dec bool bool_dec).
Qed.

Lemma fp_mod_bounded :
  forall (P : Modulus) (n : nat), Nat.ltb (Nat.modulo n (pm_mod P)) (pm_mod P) = true.
Proof.
  intros P n. apply Nat.ltb_lt. apply Nat.mod_upper_bound.
  pose proof (modulus_positive P). lia.
Qed.

Definition fp_of (P : Modulus) (n : nat) : Fp P :=
  mk_fp (Nat.modulo n (pm_mod P)) (fp_mod_bounded P n).

Lemma fp_rep_of :
  forall (P : Modulus) (n : nat), fp_rep (fp_of P n) = Nat.modulo n (pm_mod P).
Proof. reflexivity. Qed.

Lemma fp_of_rep : forall (P : Modulus) (a : Fp P), fp_of P (fp_rep a) = a.
Proof.
  intros P a. apply fp_eq_rep. rewrite fp_rep_of.
  apply Nat.mod_small. apply fp_rep_lt.
Qed.

Definition fp_zero (P : Modulus) : Fp P := fp_of P 0.
Definition fp_one (P : Modulus) : Fp P := fp_of P 1.
Definition fp_add (P : Modulus) (a b : Fp P) : Fp P := fp_of P (fp_rep a + fp_rep b).
Definition fp_sub (P : Modulus) (a b : Fp P) : Fp P :=
  fp_of P (fp_rep a + (pm_mod P - fp_rep b)).
Definition fp_mul (P : Modulus) (a b : Fp P) : Fp P := fp_of P (fp_rep a * fp_rep b).
Definition fp_eqb (P : Modulus) (a b : Fp P) : bool := Nat.eqb (fp_rep a) (fp_rep b).
Definition fp_enum (P : Modulus) : list (Fp P) := map (fp_of P) (seq 0 (pm_mod P)).

Definition witness_Modulus : Modulus := {| pm_mod := 5; pm_two := eq_refl |}.
Definition witness_Fp : Fp witness_Modulus := fp_of witness_Modulus 0.

(* =========================================================================
   3. The additive group laws, and the enumeration laws a uniform mask needs.
   ========================================================================= *)

Lemma fp_eqb_sound : forall (P : Modulus) (a b : Fp P), fp_eqb P a b = true -> a = b.
Proof. intros P a b H. apply fp_eq_rep. apply Nat.eqb_eq. exact H. Qed.

Lemma fp_eqb_refl : forall (P : Modulus) (a : Fp P), fp_eqb P a a = true.
Proof. intros P a. unfold fp_eqb. apply Nat.eqb_refl. Qed.

Lemma fp_add_comm : forall (P : Modulus) (a b : Fp P), fp_add P a b = fp_add P b a.
Proof. intros P a b. unfold fp_add. f_equal. lia. Qed.

Lemma fp_add_assoc :
  forall (P : Modulus) (a b c : Fp P),
    fp_add P a (fp_add P b c) = fp_add P (fp_add P a b) c.
Proof.
  intros P a b c. unfold fp_add. apply fp_eq_rep.
  repeat rewrite fp_rep_of.
  rewrite Nat.Div0.add_mod_idemp_l, Nat.Div0.add_mod_idemp_r.
  f_equal. lia.
Qed.

Lemma fp_add_zero_l : forall (P : Modulus) (a : Fp P), fp_add P (fp_zero P) a = a.
Proof.
  intros P a. unfold fp_add, fp_zero. apply fp_eq_rep.
  repeat rewrite fp_rep_of.
  rewrite Nat.Div0.add_mod_idemp_l, Nat.add_0_l.
  apply Nat.mod_small. apply fp_rep_lt.
Qed.

Lemma fp_sub_add : forall (P : Modulus) (a b : Fp P), fp_add P (fp_sub P a b) b = a.
Proof.
  intros P a b. unfold fp_add, fp_sub. apply fp_eq_rep.
  repeat rewrite fp_rep_of.
  rewrite Nat.Div0.add_mod_idemp_l.
  pose proof (fp_rep_lt P a) as Ha. pose proof (fp_rep_lt P b) as Hb.
  replace (fp_rep a + (pm_mod P - fp_rep b) + fp_rep b)
    with (fp_rep a + pm_mod P) by lia.
  rewrite <- Nat.Div0.add_mod_idemp_r, Nat.Div0.mod_same, Nat.add_0_r.
  apply Nat.mod_small. exact Ha.
Qed.

Lemma fp_add_sub : forall (P : Modulus) (a b : Fp P), fp_sub P (fp_add P a b) b = a.
Proof.
  intros P a b. unfold fp_add, fp_sub. apply fp_eq_rep.
  repeat rewrite fp_rep_of.
  rewrite Nat.Div0.add_mod_idemp_l.
  pose proof (fp_rep_lt P a) as Ha. pose proof (fp_rep_lt P b) as Hb.
  replace (fp_rep a + fp_rep b + (pm_mod P - fp_rep b))
    with (fp_rep a + pm_mod P) by lia.
  rewrite <- Nat.Div0.add_mod_idemp_r, Nat.Div0.mod_same, Nat.add_0_r.
  apply Nat.mod_small. exact Ha.
Qed.

Lemma fp_of_injective_below :
  forall (P : Modulus) (x y : nat),
    x < pm_mod P -> y < pm_mod P -> fp_of P x = fp_of P y -> x = y.
Proof.
  intros P x y Hx Hy H.
  pose proof (f_equal (@fp_rep P) H) as Hr.
  rewrite fp_rep_of, fp_rep_of in Hr.
  rewrite (Nat.mod_small x _ Hx), (Nat.mod_small y _ Hy) in Hr. exact Hr.
Qed.

Lemma fp_in_enum : forall (P : Modulus) (a : Fp P), In a (fp_enum P).
Proof.
  intros P a. pose proof (fp_rep_lt P a) as Hlt.
  unfold fp_enum. rewrite <- (fp_of_rep P a) at 1.
  apply in_map. apply in_seq. lia.
Qed.

Lemma fp_enum_nodup : forall P : Modulus, NoDup (fp_enum P).
Proof.
  intros P. unfold fp_enum. apply NoDup_map_NoDup_ForallPairs; [ | apply seq_NoDup ].
  intros x y Hx Hy H.
  apply in_seq in Hx. apply in_seq in Hy.
  apply (fp_of_injective_below P); [ lia | lia | exact H ].
Qed.

Lemma fp_enum_length : forall P : Modulus, length (fp_enum P) = pm_mod P.
Proof. intros P. unfold fp_enum. rewrite length_map. apply length_seq. Qed.

Lemma any_of_member :
  forall {A : Type} (p : A -> bool) (l : list A) (x : A),
    In x l -> p x = true -> any_of p l = true.
Proof.
  intros A p l x. induction l as [ | y r IH ]; simpl; intros Hin Hp;
    [ contradiction | ].
  destruct Hin as [ Heq | Hin ].
  - subst. rewrite Hp. reflexivity.
  - rewrite (IH Hin Hp). destruct (p y); reflexivity.
Qed.

Lemma fp_enum_total :
  forall (P : Modulus) (a : Fp P), any_of (fp_eqb P a) (fp_enum P) = true.
Proof.
  intros P a.
  exact (any_of_member (fp_eqb P a) (fp_enum P) a (fp_in_enum P a) (fp_eqb_refl P a)).
Qed.

Lemma perm_of_permutation :
  forall {A : Type} (l1 l2 : list A), Permutation.Permutation l1 l2 -> Perm l1 l2.
Proof.
  intros A l1 l2 H.
  induction H as [ | x l l' H IH | x y l | l l' l'' H1 IH1 H2 IH2 ].
  - apply perm_nil.
  - apply perm_skip. exact IH.
  - apply perm_swap.
  - exact (perm_trans _ _ _ IH1 IH2).
Qed.

Lemma fp_add_translate : forall (P : Modulus) (k x : Fp P), fp_add P k (fp_sub P x k) = x.
Proof.
  intros P k x. rewrite (fp_add_comm P k (fp_sub P x k)). apply fp_sub_add.
Qed.

Lemma fp_add_injective :
  forall (P : Modulus) (k a b : Fp P), fp_add P k a = fp_add P k b -> a = b.
Proof.
  intros P k a b H.
  rewrite (fp_add_comm P k a), (fp_add_comm P k b) in H.
  rewrite <- (fp_add_sub P a k), <- (fp_add_sub P b k), H. reflexivity.
Qed.

Lemma fp_enum_shift :
  forall (P : Modulus) (k : Fp P),
    Perm (map_over (fp_add P k) (fp_enum P)) (fp_enum P).
Proof.
  intros P k. rewrite map_over_is_map. apply perm_of_permutation.
  apply Permutation.NoDup_Permutation.
  - apply NoDup_map_NoDup_ForallPairs; [ | apply fp_enum_nodup ].
    intros x y _ _ H. exact (fp_add_injective P k x y H).
  - apply fp_enum_nodup.
  - intros x. split; intros _.
    + apply fp_in_enum.
    + apply in_map_iff.
      exists (fp_sub P x k). split; [ apply fp_add_translate | apply fp_in_enum ].
Qed.

(* The prime field instantiates the same carrier record GF(2) instantiates,
   which is what lets the arithmetic half reuse the general share result
   rather than restate it. *)
Definition fp_sharing (P : Modulus) : Sharing.
Proof.
  refine {|
    Val := Fp P;
    v_eqb := fp_eqb P;
    v_zero := fp_zero P;
    v_add := fp_add P;
    v_sub := fp_sub P;
    v_enum := fp_enum P
  |}.
  - exact (fp_eqb_sound P).
  - exact (fp_eqb_refl P).
  - exact (fp_add_comm P).
  - exact (fp_add_assoc P).
  - exact (fp_add_zero_l P).
  - exact (fp_sub_add P).
  - exact (fp_add_sub P).
  - exact (fp_enum_total P).
  - exact (fp_enum_shift P).
Defined.

Lemma fp_sharing_enum_nodup : forall P : Modulus, NoDup (v_enum (fp_sharing P)).
Proof. intros P. apply fp_enum_nodup. Qed.

Lemma fp_sharing_enum_length : forall P : Modulus, length (v_enum (fp_sharing P)) = pm_mod P.
Proof. intros P. apply fp_enum_length. Qed.

(* The arithmetic instance of the general additive-encoding theorem: over a
   prime field, at any share count, every probe list short of the whole
   sharing has one distribution for any two secrets. This is arbitrary order
   in the share-observation reading and is reused rather than reproved. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem prime_field_sharing_hides_from_short_share_lists :
  forall (P : Modulus) (n : nat) (idxs : list nat) (s1 s2 : Fp P),
    length idxs <= n -> (forall j : nat, In j idxs -> j <= n) ->
    SameDistribution (counting (list (Fp P)) (mask_tuples (fp_sharing P) n))
      (list (Fp P)) (list_eqb (fp_eqb P))
      (fun xs => share_view (fp_sharing P) idxs (encode (fp_sharing P) s1 xs))
      (fun xs => share_view (fp_sharing P) idxs (encode (fp_sharing P) s2 xs)).
Proof.
  intros P n idxs s1 s2 Hlen Hbound.
  exact (d_share_encoding_hides_from_d_minus_one_probes
           (fp_sharing P) n idxs s1 s2 Hlen Hbound).
Qed.

(* =========================================================================
   4. What primality buys, decided by conversion, and what it does not.
   ========================================================================= *)

Definition nonzero_elements (P : Modulus) : list (Fp P) :=
  filter (fun a => negb (fp_eqb P a (fp_zero P))) (fp_enum P).

Definition has_inverse (P : Modulus) (a : Fp P) : bool :=
  existsb (fun b => fp_eqb P (fp_mul P a b) (fp_one P)) (fp_enum P).

Definition every_nonzero_is_invertible (P : Modulus) : bool :=
  forallb (has_inverse P) (nonzero_elements P).

Definition enumeration_is_complete (P : Modulus) : bool :=
  Nat.eqb (length (fp_enum P)) (pm_mod P).

Definition addition_commutes (P : Modulus) : bool :=
  forallb (fun a => forallb (fun b => fp_eqb P (fp_add P a b) (fp_add P b a))
                            (fp_enum P))
          (fp_enum P).

Definition zero_is_neutral (P : Modulus) : bool :=
  forallb (fun a => fp_eqb P (fp_add P (fp_zero P) a) a) (fp_enum P).

Definition subtraction_inverts (P : Modulus) : bool :=
  forallb (fun a => forallb (fun b => fp_eqb P (fp_add P (fp_sub P a b) b) a)
                            (fp_enum P))
          (fp_enum P).

Definition translation_is_onto (P : Modulus) : bool :=
  forallb (fun k => forallb (fun a => existsb (fun b => fp_eqb P (fp_add P k b) a)
                                              (fp_enum P))
                            (fp_enum P))
          (fp_enum P).

(* Every field of this record is a decidable statement about one concrete
   modulus, so the witness below discharges each of them by conversion. *)
Record ConcreteField : Type := {
  cf_modulus : Modulus;
  cf_prime : primeb (pm_mod cf_modulus) = true;
  cf_complete : enumeration_is_complete cf_modulus = true;
  cf_commutes : addition_commutes cf_modulus = true;
  cf_neutral : zero_is_neutral cf_modulus = true;
  cf_subtracts : subtraction_inverts cf_modulus = true;
  cf_translates : translation_is_onto cf_modulus = true;
  cf_invertible : every_nonzero_is_invertible cf_modulus = true
}.

Definition five : Modulus := {| pm_mod := 5; pm_two := eq_refl |}.
Definition four : Modulus := {| pm_mod := 4; pm_two := eq_refl |}.

Definition witness_PrimeModulus : PrimeModulus :=
  {| pm_base := five; pm_prime := eq_refl |}.

Definition witness_ConcreteField : ConcreteField :=
  {| cf_modulus := five;
     cf_prime := eq_refl;
     cf_complete := eq_refl;
     cf_commutes := eq_refl;
     cf_neutral := eq_refl;
     cf_subtracts := eq_refl;
     cf_translates := eq_refl;
     cf_invertible := eq_refl |}.

(* The refuting companion: the composite modulus fails both the primality
   decision and the invertibility decision, by conversion. *)
(*| discharges: R-05-165, R-05-166 |*)
Example the_composite_modulus_is_refused_as_a_field :
  (primeb (pm_mod four), every_nonzero_is_invertible four) = (false, false).
Proof. reflexivity. Qed.

(* And the other direction of the same reading: the group laws the masking
   argument consumes hold at that composite modulus, so primality is not
   what the hiding rests on. *)
(*| discharges: R-05-165 |*)
Example the_group_laws_survive_a_composite_modulus :
  (addition_commutes four, zero_is_neutral four, subtraction_inverts four,
   translation_is_onto four) = (true, true, true, true).
Proof. reflexivity. Qed.

(* =========================================================================
   5. The k-stage pipeline: stage tuples, shares and single-wire values.

   The randomness is one flat tape of (stages+1) * n field elements. The
   fresh mask of stage `l` at wire `i` is coordinate l*n + i, and the stage
   tuple is the prefix sum of those coordinates, which is the same object as
   the previous tuple refreshed by this stage's fresh masks.
   ========================================================================= *)

Definition fresh_mask (m : Sharing) (tape : list (Val m)) (n stage i : nat) : Val m :=
  nth (stage * n + i) tape (v_zero m).

Fixpoint stage_mask (m : Sharing) (tape : list (Val m)) (n stage i : nat) : Val m :=
  match stage with
  | 0 => fresh_mask m tape n 0 i
  | S k => v_add m (stage_mask m tape n k i) (fresh_mask m tape n (S k) i)
  end.

Definition stage_tuple (m : Sharing) (tape : list (Val m)) (n stage : nat)
  : list (Val m) := map (fun i => stage_mask m tape n stage i) (seq 0 n).

Definition stage_shares (m : Sharing) (s : Val m) (tape : list (Val m))
    (n stage : nat) : list (Val m) := encode m s (stage_tuple m tape n stage).

Definition wire_value (m : Sharing) (s : Val m) (tape : list (Val m))
    (n stage i : nat) : Val m := nth i (stage_shares m s tape n stage) (v_zero m).

Definition pipeline_tapes (m : Sharing) (n stages : nat) : list (list (Val m)) :=
  mask_tuples m (S stages * n).

(* Reading iii as an identity rather than as prose: each stage is the
   previous tuple with this stage's fresh mask added at every wire. *)
(*| discharges: R-05-004a |*)
Theorem each_stage_refreshes_the_previous_tuple :
  forall (m : Sharing) (tape : list (Val m)) (n stage : nat),
    stage_tuple m tape n (S stage)
    = map (fun i => v_add m (stage_mask m tape n stage i)
                            (fresh_mask m tape n (S stage) i)) (seq 0 n).
Proof. reflexivity. Qed.

(* Correctness of the pipeline: refreshing changes the sharing and never the
   secret, at every stage. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem every_stage_shares_the_same_secret :
  forall (m : Sharing) (s : Val m) (tape : list (Val m)) (n stage : nat),
    sum_of m (stage_shares m s tape n stage) = s.
Proof.
  intros m s tape n stage. unfold stage_shares.
  apply the_whole_sharing_recovers_the_secret.
Qed.

Lemma stage_tuple_length :
  forall (m : Sharing) (tape : list (Val m)) (n stage : nat),
    length (stage_tuple m tape n stage) = n.
Proof. intros m tape n stage. unfold stage_tuple. rewrite length_map. apply length_seq. Qed.

Lemma nth_map_seq :
  forall {A : Type} (f : nat -> A) (n i : nat) (d : A),
    i < n -> nth i (map f (seq 0 n)) d = f i.
Proof.
  intros A f n i d Hi.
  rewrite (nth_indep (map f (seq 0 n)) d (f 0))
    by (rewrite length_map, length_seq; exact Hi).
  rewrite map_nth. f_equal. rewrite seq_nth by exact Hi. reflexivity.
Qed.

Lemma mask_wire_value :
  forall (m : Sharing) (s : Val m) (tape : list (Val m)) (n stage i : nat),
    i < n -> wire_value m s tape n stage i = stage_mask m tape n stage i.
Proof.
  intros m s tape n stage i Hi. unfold wire_value, stage_shares, encode.
  rewrite app_nth1 by (rewrite stage_tuple_length; exact Hi).
  unfold stage_tuple. apply nth_map_seq. exact Hi.
Qed.

Lemma completing_wire_value :
  forall (m : Sharing) (s : Val m) (tape : list (Val m)) (n stage : nat),
    wire_value m s tape n stage n = v_sub m s (sum_of m (stage_tuple m tape n stage)).
Proof.
  intros m s tape n stage. unfold wire_value, stage_shares, encode.
  rewrite app_nth2 by (rewrite stage_tuple_length; lia).
  rewrite stage_tuple_length, Nat.sub_diag. reflexivity.
Qed.

(* The reading that keeps this file inside its own domain: the pipeline is
   an algebraic model, and the share at a wire is a projection of a share
   list rather than a value a gate drives. R-15-053a's netlist half is not
   claimed anywhere below. The statement is the definition of wire_value
   unfolded, R-05-165's second shape, so it carries no discharge marker: it
   records a reading and discharges nothing of R-17-058a. *)
Theorem the_algebraic_pipeline_is_not_a_netlist_claim :
  forall (m : Sharing) (s : Val m) (tape : list (Val m)) (n stage i : nat),
    wire_value m s tape n stage i = nth i (stage_shares m s tape n stage) (v_zero m).
Proof. reflexivity. Qed.

(* =========================================================================
   6. Coordinate arithmetic: which tape coordinate a stage and a wire name.
   ========================================================================= *)

Lemma coordinate_unique :
  forall (n a i b j : nat),
    i < n -> j < n -> a * n + i = b * n + j -> a = b /\ i = j.
Proof.
  intros n a i b j Hi Hj H.
  assert (Hab : a = b).
  { destruct (Nat.lt_trichotomy a b) as [ L | [ E | G ] ]; [ | exact E | ];
      exfalso; nia. }
  split; [ exact Hab | subst b; lia ].
Qed.

Lemma pipeline_index_bound :
  forall (n stages stage i : nat),
    stage <= stages -> i < n -> stage * n + i < S stages * n.
Proof. intros n stages stage i Hs Hi. nia. Qed.

Lemma shift_mask_at :
  forall (m : Sharing) (i : nat) (delta : Val m) (xs : list (Val m)),
    i < length xs ->
    nth i (shift_mask m i delta xs) (v_zero m) = v_add m delta (nth i xs (v_zero m)).
Proof.
  intros m i delta xs. revert i.
  induction xs as [ | x r IH ]; intros [ | i ] H; simpl in *; try lia.
  - reflexivity.
  - apply IH. lia.
Qed.

Lemma stage_mask_unbumped :
  forall (m : Sharing) (n c i : nat) (delta : Val m) (tape : list (Val m)) (stage : nat),
    0 < n -> stage < c ->
    stage_mask m (shift_mask m (c * n + i) delta tape) n stage i
    = stage_mask m tape n stage i.
Proof.
  intros m n c i delta tape stage Hn. revert c.
  induction stage as [ | k IH ]; intros c Hlt.
  - cbn [stage_mask]. unfold fresh_mask. apply shift_mask_other. nia.
  - cbn [stage_mask]. rewrite (IH c) by lia. f_equal.
    unfold fresh_mask. apply shift_mask_other. nia.
Qed.

Lemma stage_mask_other_wire :
  forall (m : Sharing) (tape : list (Val m)) (n stage c i0 i : nat) (delta : Val m),
    i0 < n -> i < n -> i0 <> i ->
    stage_mask m (shift_mask m (c * n + i0) delta tape) n stage i
    = stage_mask m tape n stage i.
Proof.
  intros m tape n stage c i0 i delta Hi0 Hi Hne.
  assert (Hfresh : forall l : nat,
            fresh_mask m (shift_mask m (c * n + i0) delta tape) n l i
            = fresh_mask m tape n l i).
  { intros l. unfold fresh_mask. apply shift_mask_other. intros E.
    destruct (coordinate_unique n c i0 l i Hi0 Hi E) as [ _ Heq ]. exact (Hne Heq). }
  induction stage as [ | k IH ]; cbn [stage_mask]; [ apply Hfresh | ].
  rewrite IH, Hfresh. reflexivity.
Qed.

Lemma stage_mask_bumped :
  forall (m : Sharing) (n i : nat) (delta : Val m) (tape : list (Val m)) (stage : nat),
    0 < n -> stage * n + i < length tape ->
    stage_mask m (shift_mask m (stage * n + i) delta tape) n stage i
    = v_add m delta (stage_mask m tape n stage i).
Proof.
  intros m n i delta tape stage Hn Hlen. destruct stage as [ | k ].
  - cbn [stage_mask]. unfold fresh_mask. apply shift_mask_at. exact Hlen.
  - cbn [stage_mask].
    rewrite (stage_mask_unbumped m n (S k) i delta tape k Hn (Nat.lt_succ_diag_r k)).
    unfold fresh_mask. rewrite shift_mask_at by exact Hlen.
    rewrite (v_add_assoc m (stage_mask m tape n k i) delta
               (nth (S k * n + i) tape (v_zero m))).
    rewrite (v_add_assoc m delta (stage_mask m tape n k i)
               (nth (S k * n + i) tape (v_zero m))).
    f_equal. apply v_add_comm.
Qed.

Lemma sum_of_seq_split :
  forall (m : Sharing) (f : nat -> Val m) (n : nat),
    0 < n ->
    sum_of m (map f (seq 0 n)) = v_add m (f 0) (sum_of m (map f (seq 1 (n - 1)))).
Proof.
  intros m f n Hn. destruct n as [ | k ]; [ lia | ].
  replace (S k - 1) with k by lia. reflexivity.
Qed.

Lemma sum_of_map_ext_in :
  forall (m : Sharing) (f g : nat -> Val m) (l : list nat),
    (forall i : nat, In i l -> f i = g i) ->
    sum_of m (map f l) = sum_of m (map g l).
Proof. intros m f g l H. f_equal. apply map_ext_in. exact H. Qed.

Lemma stage_tuple_sum_bumped :
  forall (m : Sharing) (tape : list (Val m)) (n stage : nat) (delta : Val m),
    0 < n -> stage * n + 0 < length tape ->
    sum_of m (stage_tuple m (shift_mask m (stage * n + 0) delta tape) n stage)
    = v_add m delta (sum_of m (stage_tuple m tape n stage)).
Proof.
  intros m tape n stage delta Hn Hlen. unfold stage_tuple.
  rewrite (sum_of_seq_split m
             (fun i => stage_mask m (shift_mask m (stage * n + 0) delta tape) n stage i)
             n Hn).
  rewrite (sum_of_seq_split m (fun i => stage_mask m tape n stage i) n Hn).
  cbv beta.
  rewrite (stage_mask_bumped m n 0 delta tape stage Hn Hlen).
  rewrite (sum_of_map_ext_in m
             (fun i => stage_mask m (shift_mask m (stage * n + 0) delta tape) n stage i)
             (fun i => stage_mask m tape n stage i) (seq 1 (n - 1))).
  - rewrite <- (v_add_assoc m delta (stage_mask m tape n stage 0)
                 (sum_of m (map (fun i => stage_mask m tape n stage i) (seq 1 (n - 1))))).
    reflexivity.
  - intros i Hi. apply in_seq in Hi.
    apply (stage_mask_other_wire m tape n stage stage 0 i delta); lia.
Qed.

(* =========================================================================
   7. The finite counting machinery: a fiber, its size, and why every fiber
   of a shiftable observation has the same size.
   ========================================================================= *)

Fixpoint nat_sum (l : list nat) : nat :=
  match l with nil => 0 | cons x r => x + nat_sum r end.

Lemma nat_sum_zeros : forall {A : Type} (l : list A), nat_sum (map (fun _ => 0) l) = 0.
Proof. intros A l. induction l as [ | x r IH ]; simpl; lia. Qed.

Lemma nat_sum_map_add :
  forall {A : Type} (f g : A -> nat) (l : list A),
    nat_sum (map (fun a => f a + g a) l) = nat_sum (map f l) + nat_sum (map g l).
Proof. intros A f g l. induction l as [ | x r IH ]; simpl; lia. Qed.

Lemma nat_sum_indicator :
  forall {A : Type} (p : A -> bool) (l : list A),
    nat_sum (map (fun a => if p a then 1 else 0) l) = count_of (filter_of p l).
Proof.
  intros A p l. induction l as [ | x r IH ]; simpl; [ reflexivity | ].
  destruct (p x); simpl; lia.
Qed.

Lemma count_of_filter_cons :
  forall {A : Type} (p : A -> bool) (x : A) (l : list A),
    count_of (filter_of p (cons x l))
    = (if p x then 1 else 0) + count_of (filter_of p l).
Proof. intros A p x l. unfold filter_of. cbn [ProofSupport.filter_of]. destruct (p x); reflexivity. Qed.

Lemma nat_sum_constant :
  forall {A : Type} (g : A -> nat) (l : list A) (c : nat),
    (forall a : A, In a l -> g a = c) -> nat_sum (map g l) = length l * c.
Proof.
  intros A g l c. induction l as [ | x r IH ]; simpl; intros H; [ lia | ].
  rewrite (H x (or_introl eq_refl)). rewrite IH; [ lia | ].
  intros a Ha. apply H. right. exact Ha.
Qed.

Lemma filter_of_ext_in :
  forall {A : Type} (p q : A -> bool) (l : list A),
    (forall a : A, In a l -> p a = q a) -> filter_of p l = filter_of q l.
Proof.
  intros A p q l. induction l as [ | x r IH ]; simpl; intros H; [ reflexivity | ].
  rewrite (H x (or_introl eq_refl)). rewrite IH; [ reflexivity | ].
  intros a Ha. apply H. right. exact Ha.
Qed.

Lemma no_match_outside :
  forall (m : Sharing) (x : Val m) (l : list (Val m)),
    ~ In x l -> filter_of (fun v => v_eqb m x v) l = nil.
Proof.
  intros m x l. induction l as [ | y r IH ]; simpl; intros H; [ reflexivity | ].
  destruct (v_eqb m x y) eqn:E.
  - exfalso. apply H. left. symmetry. exact (v_eqb_sound m x y E).
  - apply IH. intros Hin. apply H. right. exact Hin.
Qed.

Lemma fiber_of_enumeration_is_one :
  forall (m : Sharing) (x : Val m) (l : list (Val m)),
    NoDup l -> In x l -> count_of (filter_of (fun v => v_eqb m x v) l) = 1.
Proof.
  intros m x l Hnd. induction Hnd as [ | y r Hy Hr IH ]; simpl; intros Hin;
    [ contradiction | ].
  destruct (v_eqb m x y) eqn:E.
  - simpl. f_equal. rewrite (no_match_outside m x r); [ reflexivity | ].
    rewrite (v_eqb_sound m x y E). exact Hy.
  - apply IH. destruct Hin as [ Heq | Hin ]; [ | exact Hin ].
    rewrite <- Heq, (v_eqb_refl m y) in E. discriminate E.
Qed.

Lemma value_in_enumeration : forall (m : Sharing) (a : Val m), In a (v_enum m).
Proof.
  intros m a. pose proof (v_enum_total m a) as Ht.
  generalize dependent Ht. generalize (v_enum m). intros l.
  induction l as [ | y r IH ]; simpl; intros Ht; [ discriminate Ht | ].
  destruct (v_eqb m a y) eqn:E.
  - left. symmetry. exact (v_eqb_sound m a y E).
  - simpl in Ht. right. exact (IH Ht).
Qed.

Lemma fiber_partition :
  forall (m : Sharing) (T : Type) (f : T -> Val m) (l : list T),
    NoDup (v_enum m) ->
    nat_sum (map (fun v => count_of (filter_of (fun t => v_eqb m (f t) v) l))
                 (v_enum m))
    = length l.
Proof.
  intros m T f l Hnd. induction l as [ | t r IH ].
  - change (nat_sum (map (fun _ : Val m => 0) (v_enum m)) = length (@nil T)).
    apply nat_sum_zeros.
  - transitivity (nat_sum (map (fun v => (if v_eqb m (f t) v then 1 else 0)
                                  + count_of (filter_of (fun u => v_eqb m (f u) v) r))
                               (v_enum m))).
    + f_equal. apply map_ext. intros v.
      exact (count_of_filter_cons (fun u : T => v_eqb m (f u) v) t r).
    + rewrite (nat_sum_map_add (fun v => if v_eqb m (f t) v then 1 else 0)
                 (fun v => count_of (filter_of (fun u => v_eqb m (f u) v) r))
                 (v_enum m)).
      rewrite (nat_sum_indicator (fun v => v_eqb m (f t) v) (v_enum m)).
      rewrite (fiber_of_enumeration_is_one m (f t) (v_enum m) Hnd
                 (value_in_enumeration m (f t))).
      rewrite IH. reflexivity.
Qed.

Lemma v_add_cancel_l :
  forall (m : Sharing) (a b c : Val m), v_add m c a = v_add m c b -> a = b.
Proof.
  intros m a b c H. apply (v_add_cancel_r m a b c).
  rewrite (v_add_comm m a c), (v_add_comm m b c). exact H.
Qed.

Lemma shift_matches_the_other_fiber :
  forall (m : Sharing) (x v w : Val m),
    v_eqb m x v = v_eqb m (v_add m (v_sub m w v) x) w.
Proof.
  intros m x v w.
  destruct (v_eqb m x v) eqn:E1;
    destruct (v_eqb m (v_add m (v_sub m w v) x) w) eqn:E2; try reflexivity.
  - exfalso. rewrite (v_eqb_sound m x v E1) in E2.
    rewrite (v_sub_add m w v) in E2. rewrite (v_eqb_refl m w) in E2. discriminate E2.
  - exfalso.
    assert (Hx : v_add m (v_sub m w v) x = v_add m (v_sub m w v) v).
    { rewrite (v_eqb_sound m (v_add m (v_sub m w v) x) w E2).
      rewrite (v_sub_add m w v). reflexivity. }
    rewrite (v_add_cancel_l m x v (v_sub m w v) Hx) in E1.
    rewrite (v_eqb_refl m v) in E1. discriminate E1.
Qed.

Lemma fiber_sizes_agree :
  forall (m : Sharing) (T : Type) (f : T -> Val m) (l : list T)
         (shift : Val m -> T -> T),
    (forall (d : Val m) (t : T), In t l -> f (shift d t) = v_add m d (f t)) ->
    (forall d : Val m, Perm (map_over (shift d) l) l) ->
    forall v w : Val m,
      count_of (filter_of (fun t => v_eqb m (f t) v) l)
      = count_of (filter_of (fun t => v_eqb m (f t) w) l).
Proof.
  intros m T f l shift Hsh Hperm v w.
  transitivity (count_of (filter_of (fun t => v_eqb m (f (shift (v_sub m w v) t)) w) l)).
  - f_equal. apply filter_of_ext_in. intros t Ht.
    rewrite (Hsh (v_sub m w v) t Ht). apply shift_matches_the_other_fiber.
  - rewrite (count_filter_image (shift (v_sub m w v))
               (fun u => v_eqb m (f u) w) l).
    apply count_of_perm. apply perm_filter. exact (Hperm (v_sub m w v)).
Qed.

(* The preimage-cardinality statement in general form: every fiber of a
   shiftable finite observation has the same size, and the enumeration's
   length times that size is the whole sample count. *)
(*| discharges: R-15-053a |*)
Theorem shiftable_observations_have_uniform_preimage_counts :
  forall (m : Sharing) (T : Type) (f : T -> Val m) (l : list T)
         (shift : Val m -> T -> T),
    NoDup (v_enum m) ->
    (forall (d : Val m) (t : T), In t l -> f (shift d t) = v_add m d (f t)) ->
    (forall d : Val m, Perm (map_over (shift d) l) l) ->
    forall v : Val m,
      length (v_enum m) * count_of (filter_of (fun t => v_eqb m (f t) v) l) = length l.
Proof.
  intros m T f l shift Hnd Hsh Hperm v.
  assert (Hall : forall w : Val m, In w (v_enum m) ->
            count_of (filter_of (fun t => v_eqb m (f t) w) l)
            = count_of (filter_of (fun t => v_eqb m (f t) v) l)).
  { intros w _. exact (fiber_sizes_agree m T f l shift Hsh Hperm w v). }
  rewrite <- (fiber_partition m T f l Hnd).
  rewrite (nat_sum_constant
             (fun w => count_of (filter_of (fun t => v_eqb m (f t) w) l))
             (v_enum m)
             (count_of (filter_of (fun t => v_eqb m (f t) v) l)) Hall).
  reflexivity.
Qed.

Lemma mask_tuples_length_pow :
  forall (m : Sharing) (n : nat),
    length (mask_tuples m n) = (length (v_enum m)) ^ n.
Proof.
  intros m n. induction n as [ | k IH ]; [ reflexivity | ].
  cbn [mask_tuples].
  rewrite (flat_map_constant_length (c := (length (v_enum m)) ^ k)
             (fun x => map (cons x) (mask_tuples m k)) (v_enum m)).
  - rewrite Nat.pow_succ_r by lia. reflexivity.
  - intros x _. rewrite length_map. exact IH.
Qed.

(* =========================================================================
   8. The single observed wire: its shift family, its preimage count, and
   the probability reading of that count.
   ========================================================================= *)

Lemma sub_of_a_shifted_sum :
  forall (m : Sharing) (s x d : Val m),
    v_sub m s (v_add m (v_sub m (v_zero m) d) x) = v_add m d (v_sub m s x).
Proof.
  intros m s x d.
  apply (v_add_cancel_r m _ _ (v_add m (v_sub m (v_zero m) d) x)).
  rewrite (v_sub_add m s (v_add m (v_sub m (v_zero m) d) x)).
  rewrite (v_add_assoc m (v_add m d (v_sub m s x)) (v_sub m (v_zero m) d) x).
  rewrite <- (v_add_assoc m d (v_sub m s x) (v_sub m (v_zero m) d)).
  rewrite (v_add_comm m (v_sub m s x) (v_sub m (v_zero m) d)).
  rewrite (v_add_assoc m d (v_sub m (v_zero m) d) (v_sub m s x)).
  rewrite (v_add_comm m d (v_sub m (v_zero m) d)).
  rewrite (v_sub_add m (v_zero m) d).
  rewrite (v_add_zero_l m (v_sub m s x)).
  rewrite (v_sub_add m s x).
  reflexivity.
Qed.

Lemma single_wire_shift_family :
  forall (m : Sharing) (s : Val m) (n stages stage i : nat),
    0 < n -> stage <= stages -> i <= n ->
    exists shift : Val m -> list (Val m) -> list (Val m),
      (forall (d : Val m) (tape : list (Val m)),
         In tape (pipeline_tapes m n stages) ->
         wire_value m s (shift d tape) n stage i
         = v_add m d (wire_value m s tape n stage i))
      /\ (forall d : Val m,
            Perm (map_over (shift d) (pipeline_tapes m n stages))
                 (pipeline_tapes m n stages)).
Proof.
  intros m s n stages stage i Hn Hs Hi.
  destruct (Nat.lt_ge_cases i n) as [ Hlt | Hge ].
  - exists (fun d tape => shift_mask m (stage * n + i) d tape). split.
    + intros d tape Htape.
      assert (Hlen : length tape = S stages * n)
        by exact (mask_tuples_length m (S stages * n) tape Htape).
      rewrite (mask_wire_value m s _ n stage i Hlt).
      rewrite (mask_wire_value m s tape n stage i Hlt).
      apply (stage_mask_bumped m n i d tape stage Hn).
      rewrite Hlen. exact (pipeline_index_bound n stages stage i Hs Hlt).
    + intros d. rewrite map_over_is_map. unfold pipeline_tapes.
      apply shift_mask_permutation.
      exact (pipeline_index_bound n stages stage i Hs Hlt).
  - assert (Hin : i = n) by lia. subst i.
    exists (fun d tape => shift_mask m (stage * n + 0) (v_sub m (v_zero m) d) tape).
    split.
    + intros d tape Htape.
      assert (Hlen : length tape = S stages * n)
        by exact (mask_tuples_length m (S stages * n) tape Htape).
      rewrite (completing_wire_value m s _ n stage).
      rewrite (completing_wire_value m s tape n stage).
      rewrite (stage_tuple_sum_bumped m tape n stage (v_sub m (v_zero m) d) Hn).
      * apply sub_of_a_shifted_sum.
      * rewrite Hlen. exact (pipeline_index_bound n stages stage 0 Hs Hn).
    + intros d. rewrite map_over_is_map. unfold pipeline_tapes.
      apply shift_mask_permutation.
      exact (pipeline_index_bound n stages stage 0 Hs Hn).
Qed.

(* THE PREIMAGE-CARDINALITY STATEMENT. For a fixed secret, a fixed stage of
   the k-stage pipeline, a fixed observed wire and a fixed observed value,
   the number of mask tuples producing that observation, multiplied by the
   field size, is the whole tape count. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem the_single_wire_preimage_count :
  forall (m : Sharing) (s : Val m) (n stages stage i : nat) (v : Val m),
    NoDup (v_enum m) -> 0 < n -> stage <= stages -> i <= n ->
    length (v_enum m)
      * count_of (filter_of (fun tape => v_eqb m (wire_value m s tape n stage i) v)
                            (pipeline_tapes m n stages))
    = length (v_enum m) ^ (S stages * n).
Proof.
  intros m s n stages stage i v Hnd Hn Hs Hi.
  destruct (single_wire_shift_family m s n stages stage i Hn Hs Hi)
    as [ shift [ Hsh Hperm ] ].
  rewrite <- (mask_tuples_length_pow m (S stages * n)).
  exact (shiftable_observations_have_uniform_preimage_counts m (list (Val m))
           (fun tape => wire_value m s tape n stage i) (pipeline_tapes m n stages)
           shift Hnd Hsh Hperm v).
Qed.

(* The same figure written as a count rather than as a product. *)
(*| discharges: R-15-053a |*)
Corollary the_single_wire_observation_has_one_in_p_of_the_tapes :
  forall (m : Sharing) (s : Val m) (n stages stage i : nat) (v : Val m),
    NoDup (v_enum m) -> 0 < n -> stage <= stages -> i <= n ->
    count_of (filter_of (fun tape => v_eqb m (wire_value m s tape n stage i) v)
                        (pipeline_tapes m n stages))
    = length (v_enum m) ^ (S stages * n - 1).
Proof.
  intros m s n stages stage i v Hnd Hn Hs Hi.
  pose proof (the_single_wire_preimage_count m s n stages stage i v Hnd Hn Hs Hi) as H.
  assert (Hp : 0 < length (v_enum m)).
  { destruct (v_enum m) eqn:E; [ | simpl; lia ].
    exfalso. exact (sharing_enumeration_nonempty m E). }
  assert (HN : S stages * n = S (S stages * n - 1)) by nia.
  rewrite HN in H. rewrite Nat.pow_succ_r in H by lia. nia.
Qed.

(* The counting instance consumes ProbingModel's support-local law. A tape
   outside the enumeration is not one this pipeline's coordinates reach. *)
Lemma support_members_are_in : forall (T : Type) (enum : list T) (t : T),
  ProofSupport.Member t enum -> In t enum.
Proof.
  intros T enum. induction enum as [|a r IH]; intros t Ht; simpl in *.
  - exact Ht.
  - destruct Ht as [Ht | Ht].
    + left. symmetry. exact Ht.
    + right. exact (IH t Ht).
Qed.

Lemma counting_rerandomization_on_members :
  forall (T : Type) (enum : list T) (O : Type) (oeqb : O -> O -> bool)
         (f g : T -> O) (sigma : T -> T),
    Perm (map_over sigma enum) enum ->
    (forall t : T, In t enum -> g (sigma t) = f t) ->
    SameDistribution (counting T enum) O oeqb f g.
Proof.
  intros T enum O oeqb f g sigma Hperm Hg.
  apply (rerandomization_hides_on_members (counting T enum) O oeqb f g sigma).
  - intros t _. reflexivity.
  - exact Hperm.
  - intros t Ht. apply Hg. exact (support_members_are_in T enum t Ht).
Qed.

(* THE CARDINALITY-TO-PROBABILITY CONNECTION. Under uniform independent
   fresh masks, the weight of each single-wire observation is the same for
   any two secrets, at every stage of the k-stage pipeline, in the exact
   equality of finite outcome weights ProbingModel.v fixes. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem every_stage_hides_the_secret_from_one_wire :
  forall (m : Sharing) (n stages stage i : nat) (s1 s2 : Val m),
    0 < n -> stage <= stages -> i <= n ->
    SameDistribution (counting (list (Val m)) (pipeline_tapes m n stages))
      (Val m) (v_eqb m)
      (fun tape => wire_value m s1 tape n stage i)
      (fun tape => wire_value m s2 tape n stage i).
Proof.
  intros m n stages stage i s1 s2 Hn Hs Hi.
  destruct (Nat.lt_ge_cases i n) as [ Hlt | Hge ].
  - apply identical_views_are_identically_distributed. intros tape.
    rewrite (mask_wire_value m s1 tape n stage i Hlt).
    rewrite (mask_wire_value m s2 tape n stage i Hlt). reflexivity.
  - assert (Hin : i = n) by lia. subst i.
    apply (counting_rerandomization_on_members (list (Val m))
             (pipeline_tapes m n stages) (Val m) (v_eqb m)
             (fun tape => wire_value m s1 tape n stage n)
             (fun tape => wire_value m s2 tape n stage n)
             (fun tape => shift_mask m (stage * n + 0) (v_sub m s2 s1) tape)).
    + rewrite map_over_is_map. unfold pipeline_tapes.
      apply shift_mask_permutation.
      exact (pipeline_index_bound n stages stage 0 Hs Hn).
    + intros tape Htape.
      assert (Hlen : length tape = S stages * n)
        by exact (mask_tuples_length m (S stages * n) tape Htape).
      rewrite (completing_wire_value m s2 _ n stage).
      rewrite (completing_wire_value m s1 tape n stage).
      rewrite (stage_tuple_sum_bumped m tape n stage (v_sub m s2 s1) Hn).
      * apply v_sub_shift.
      * rewrite Hlen. exact (pipeline_index_bound n stages stage 0 Hs Hn).
Qed.

(* The conditional reading, with its normalizer. The numerator and the
   denominator are the same pair for any two secrets; the denominator is
   positive; and the field size times the numerator is the denominator, so
   the conditional probability of a single-wire observation is exactly one
   over the field size for every secret, stated without a rational field. *)
(*| discharges: R-05-004a, R-15-053a, R-05-165 |*)
Theorem the_conditional_reading_of_the_single_wire_bound :
  forall (m : Sharing) (n stages stage i : nat) (s1 s2 : Val m) (o : Val m),
    NoDup (v_enum m) -> 0 < n -> stage <= stages -> i <= n ->
    normalized_counting_observation (pipeline_tapes m n stages) (v_eqb m)
      (fun tape => wire_value m s1 tape n stage i) o
    = normalized_counting_observation (pipeline_tapes m n stages) (v_eqb m)
        (fun tape => wire_value m s2 tape n stage i) o
    /\ length (v_enum m)
       * fst (normalized_counting_observation (pipeline_tapes m n stages) (v_eqb m)
                (fun tape => wire_value m s1 tape n stage i) o)
       = snd (normalized_counting_observation (pipeline_tapes m n stages) (v_eqb m)
                (fun tape => wire_value m s1 tape n stage i) o)
    /\ 0 < snd (normalized_counting_observation (pipeline_tapes m n stages) (v_eqb m)
                  (fun tape => wire_value m s1 tape n stage i) o).
Proof.
  intros m n stages stage i s1 s2 o Hnd Hn Hs Hi.
  unfold normalized_counting_observation. split; [ | split ]; simpl.
  - f_equal.
    exact (every_stage_hides_the_secret_from_one_wire m n stages stage i s1 s2
             Hn Hs Hi o).
  - rewrite counting_pr.
    rewrite (the_single_wire_preimage_count m s1 n stages stage i o Hnd Hn Hs Hi).
    symmetry. apply mask_tuples_length_pow.
  - unfold pipeline_tapes. rewrite mask_tuples_length_pow.
    assert (Hp : 0 < length (v_enum m)).
    { destruct (v_enum m) eqn:E; [ | simpl; lia ].
      exfalso. exact (sharing_enumeration_nonempty m E). }
    assert (Hnz : length (v_enum m) ^ (S stages * n) <> 0)
      by (apply Nat.pow_nonzero; lia).
    lia.
Qed.

(* =========================================================================
   9. The prime-field instances, and the refuting case that makes the bound
   tight rather than vacuous.
   ========================================================================= *)

(*| discharges: R-05-004a, R-15-053a |*)
Corollary the_prime_field_pipeline_hides_every_single_wire :
  forall (P : Modulus) (n stages stage i : nat) (s1 s2 : Fp P),
    0 < n -> stage <= stages -> i <= n ->
    SameDistribution (counting (list (Fp P)) (pipeline_tapes (fp_sharing P) n stages))
      (Fp P) (fp_eqb P)
      (fun tape => wire_value (fp_sharing P) s1 tape n stage i)
      (fun tape => wire_value (fp_sharing P) s2 tape n stage i).
Proof.
  intros P n stages stage i s1 s2 Hn Hs Hi.
  exact (every_stage_hides_the_secret_from_one_wire (fp_sharing P) n stages stage i
           s1 s2 Hn Hs Hi).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Corollary the_prime_field_single_wire_preimage_count :
  forall (P : Modulus) (s : Fp P) (n stages stage i : nat) (v : Fp P),
    0 < n -> stage <= stages -> i <= n ->
    pm_mod P
      * count_of (filter_of
                    (fun tape => fp_eqb P (wire_value (fp_sharing P) s tape n stage i) v)
                    (pipeline_tapes (fp_sharing P) n stages))
    = pm_mod P ^ (S stages * n).
Proof.
  intros P s n stages stage i v Hn Hs Hi.
  rewrite <- (fp_sharing_enum_length P).
  exact (the_single_wire_preimage_count (fp_sharing P) s n stages stage i v
           (fp_sharing_enum_nodup P) Hn Hs Hi).
Qed.

(* Primality is not what the hiding rests on. The same theorem holds at the
   composite modulus four, whose non-field status is decided above. *)
(*| discharges: R-05-165 |*)
Corollary the_hiding_argument_does_not_consume_primality :
  forall (n stages stage i : nat) (s1 s2 : Fp four),
    0 < n -> stage <= stages -> i <= n ->
    SameDistribution (counting (list (Fp four)) (pipeline_tapes (fp_sharing four) n stages))
      (Fp four) (fp_eqb four)
      (fun tape => wire_value (fp_sharing four) s1 tape n stage i)
      (fun tape => wire_value (fp_sharing four) s2 tape n stage i).
Proof.
  intros n stages stage i s1 s2 Hn Hs Hi.
  exact (the_prime_field_pipeline_hides_every_single_wire four n stages stage i
           s1 s2 Hn Hs Hi).
Qed.

(* The demo: one mask wire and one completing share, refreshed once, over
   Z/5Z. The tape space is the twenty-five mask pairs. *)
Definition demo_stage_view (s : Fp five) (tape : list (Fp five)) : list (Fp five) :=
  share_view (fp_sharing five) (cons 0 (cons 1 nil))
             (stage_shares (fp_sharing five) s tape 1 1).

(* The positive side, computed by conversion: one observed mask wire has
   five preimages among the twenty-five tapes, which is the general figure
   p^((k+1)n - 1) at p = 5, n = 1 and k = 1. *)
(*| discharges: R-15-053a, R-05-166 |*)
Example the_demo_single_wire_has_five_preimages :
  count_of (filter_of
              (fun tape => fp_eqb five
                 (wire_value (fp_sharing five) (fp_of five 3) tape 1 1 0)
                 (fp_of five 2))
              (pipeline_tapes (fp_sharing five) 1 1)) = 5.
Proof. vm_compute. reflexivity. Qed.

(* THE REFUTING CASE. A completing set of shares at one stage recovers the
   secret, so the single-wire bound has a refuting instance: the completing
   view separates two secrets by outcome weight, computed by conversion. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem a_completing_stage_view_recovers_the_secret :
  forall (m : Sharing) (s : Val m) (tape : list (Val m)) (n stage : nat),
    sum_of m (stage_shares m s tape n stage) = s.
Proof. intros m s tape n stage. apply every_stage_shares_the_same_secret. Qed.

(*| discharges: R-05-165, R-05-166, R-15-053a |*)
Theorem the_completing_stage_view_distinguishes_two_secrets :
  ~ SameDistribution (counting (list (Fp five)) (pipeline_tapes (fp_sharing five) 1 1))
      (list (Fp five)) (list_eqb (fp_eqb five))
      (fun tape => demo_stage_view (fp_of five 0) tape)
      (fun tape => demo_stage_view (fp_of five 1) tape).
Proof.
  intros H. specialize (H (cons (fp_of five 0) (cons (fp_of five 0) nil))).
  vm_compute in H. discriminate H.
Qed.

(* The two weights that separation is made of, pinned as a statement rather
   than left to the header's prose. The theorem above discriminates them and
   so says only that they differ; these are the numbers. At p = 5 with one
   mask and one refresh, five of the twenty-five tapes put both shares of
   the completing view at zero when the secret is zero, and none do when
   the secret is one. *)
(*| discharges: R-05-165, R-15-053a |*)
Example the_completing_stage_view_weighs_five_against_zero :
  pr (counting (list (Fp five)) (pipeline_tapes (fp_sharing five) 1 1))
     (fun tape => list_eqb (fp_eqb five)
        (demo_stage_view (fp_of five 0) tape)
        (cons (fp_of five 0) (cons (fp_of five 0) nil))) = 5
  /\ pr (counting (list (Fp five)) (pipeline_tapes (fp_sharing five) 1 1))
       (fun tape => list_eqb (fp_eqb five)
          (demo_stage_view (fp_of five 1) tape)
          (cons (fp_of five 0) (cons (fp_of five 0) nil))) = 0.
Proof. split; vm_compute; reflexivity. Qed.

(* And the single wire of that same demo is hidden, so the separation above
   is the completing set and not the pipeline. *)
(*| discharges: R-15-053a |*)
Example the_demo_single_wire_is_not_a_leak :
  forall o : Fp five,
    pr (counting (list (Fp five)) (pipeline_tapes (fp_sharing five) 1 1))
       (fun tape => fp_eqb five
          (wire_value (fp_sharing five) (fp_of five 0) tape 1 1 1) o)
    = pr (counting (list (Fp five)) (pipeline_tapes (fp_sharing five) 1 1))
         (fun tape => fp_eqb five
            (wire_value (fp_sharing five) (fp_of five 1) tape 1 1 1) o).
Proof.
  exact (the_prime_field_pipeline_hides_every_single_wire five 1 1 1 1
           (fp_of five 0) (fp_of five 1)
           (Nat.lt_0_succ 0) (Nat.le_refl 1) (Nat.le_refl 1)).
Qed.

(* =========================================================================
   10. R-05-166's inhabitation witnesses for the records this file declares.
   The records ProbingModel.v declares are inhabited by its own witnesses.
   ========================================================================= *)

(* `witness_Modulus`, `witness_Fp`, `witness_PrimeModulus` and
   `witness_ConcreteField` stand above, each beside the record it inhabits.
   `Sharing` is quantified here and inhabited by ProbingModel.v's own
   witness; what this file adds is that the prime field is one of its
   instances rather than a separate algebra. *)
(*| discharges: R-05-166 |*)
Example the_prime_field_inhabits_the_probing_model_sharing :
  Val (fp_sharing five) = Fp five.
Proof. reflexivity. Qed.

(* =========================================================================
   11. Arbitrary-order (n+1)-share prime-field operations: sec_add, sec_scale,
   and iterative k-stage sec_refresh_pipeline.
   ========================================================================= *)

Fixpoint vec_add (m : Sharing) (xs ys : list (Val m)) : list (Val m) :=
  match xs, ys with
  | cons x xr, cons y yr => cons (v_add m x y) (vec_add m xr yr)
  | _, _ => nil
  end.

Lemma vec_add_length :
  forall (m : Sharing) (xs ys : list (Val m)),
    length xs = length ys -> length (vec_add m xs ys) = length xs.
Proof.
  intros m xs. induction xs as [ | x xr IH ]; intros [ | y yr ] H;
    simpl in *; try discriminate H; try reflexivity.
  f_equal. apply IH. lia.
Qed.

Lemma vec_add_sum :
  forall (m : Sharing) (xs ys : list (Val m)),
    length xs = length ys ->
    sum_of m (vec_add m xs ys) = v_add m (sum_of m xs) (sum_of m ys).
Proof.
  intros m xs. induction xs as [ | x xr IH ]; intros [ | y yr ] H;
    simpl in *; try discriminate H.
  - symmetry. apply v_add_zero_l.
  - rewrite (IH yr) by lia.
    rewrite (v_add_assoc m (v_add m x y) (sum_of m xr) (sum_of m yr)).
    rewrite <- (v_add_assoc m x y (sum_of m xr)).
    rewrite (v_add_comm m y (sum_of m xr)).
    rewrite (v_add_assoc m x (sum_of m xr) y).
    rewrite <- (v_add_assoc m (v_add m x (sum_of m xr)) y (sum_of m yr)).
    reflexivity.
Qed.

Definition sec_add (P : Modulus) (xs ys : list (Fp P)) : list (Fp P) :=
  vec_add (fp_sharing P) xs ys.

Lemma sec_add_length :
  forall (P : Modulus) (xs ys : list (Fp P)),
    length xs = length ys -> length (sec_add P xs ys) = length xs.
Proof. intros P xs ys H. exact (vec_add_length (fp_sharing P) xs ys H). Qed.

Lemma sec_add_sum :
  forall (P : Modulus) (xs ys : list (Fp P)),
    length xs = length ys ->
    sum_of (fp_sharing P) (sec_add P xs ys)
    = fp_add P (sum_of (fp_sharing P) xs) (sum_of (fp_sharing P) ys).
Proof. intros P xs ys H. exact (vec_add_sum (fp_sharing P) xs ys H). Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem sec_add_preserves_masked_sum :
  forall (P : Modulus) (n : nat) (s1 s2 : Fp P) (mx my : list (Fp P)),
    length mx = n -> length my = n ->
    length (sec_add P (encode (fp_sharing P) s1 mx) (encode (fp_sharing P) s2 my)) = S n
    /\ sum_of (fp_sharing P)
              (sec_add P (encode (fp_sharing P) s1 mx) (encode (fp_sharing P) s2 my))
       = fp_add P s1 s2.
Proof.
  intros P n s1 s2 mx my Hx Hy.
  assert (Hlen1 : @length (Fp P) (encode (fp_sharing P) s1 mx) = S n)
    by (unfold encode; rewrite length_app; simpl; lia).
  assert (Hlen2 : @length (Fp P) (encode (fp_sharing P) s2 my) = S n)
    by (unfold encode; rewrite length_app; simpl; lia).
  split.
  - rewrite sec_add_length by (rewrite Hlen1, Hlen2; reflexivity). exact Hlen1.
  - rewrite sec_add_sum by (rewrite Hlen1, Hlen2; reflexivity).
    rewrite !the_whole_sharing_recovers_the_secret. reflexivity.
Qed.

Fixpoint sec_scale (P : Modulus) (c : Fp P) (xs : list (Fp P)) : list (Fp P) :=
  match xs with
  | nil => nil
  | cons x xr => cons (fp_mul P c x) (sec_scale P c xr)
  end.

Lemma fp_mul_zero_r : forall (P : Modulus) (c : Fp P), fp_mul P c (fp_zero P) = fp_zero P.
Proof.
  intros P c. unfold fp_mul, fp_zero. apply fp_eq_rep.
  repeat rewrite fp_rep_of. rewrite Nat.Div0.mod_0_l, Nat.mul_0_r. apply Nat.Div0.mod_0_l.
Qed.

Lemma fp_mul_add_distr_l :
  forall (P : Modulus) (c a b : Fp P),
    fp_mul P c (fp_add P a b) = fp_add P (fp_mul P c a) (fp_mul P c b).
Proof.
  intros P c a b. unfold fp_mul, fp_add. apply fp_eq_rep.
  repeat rewrite fp_rep_of.
  rewrite Nat.Div0.mul_mod_idemp_r.
  rewrite Nat.Div0.add_mod_idemp_l, Nat.Div0.add_mod_idemp_r.
  f_equal. ring.
Qed.

Lemma sec_scale_length :
  forall (P : Modulus) (c : Fp P) (xs : list (Fp P)),
    length (sec_scale P c xs) = length xs.
Proof.
  intros P c xs. induction xs as [ | x xr IH ]; simpl; [ reflexivity | f_equal; exact IH ].
Qed.

Lemma sec_scale_sum :
  forall (P : Modulus) (c : Fp P) (xs : list (Fp P)),
    sum_of (fp_sharing P) (sec_scale P c xs)
    = fp_mul P c (sum_of (fp_sharing P) xs).
Proof.
  intros P c xs. induction xs as [ | x xr IH ]; simpl.
  - symmetry. apply fp_mul_zero_r.
  - rewrite IH. change (fp_add P (fp_mul P c x) (fp_mul P c (sum_of (fp_sharing P) xr))
                        = fp_mul P c (fp_add P x (sum_of (fp_sharing P) xr))).
    symmetry. apply fp_mul_add_distr_l.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem sec_scale_preserves_masked_product :
  forall (P : Modulus) (n : nat) (c s : Fp P) (mx : list (Fp P)),
    length mx = n ->
    length (sec_scale P c (encode (fp_sharing P) s mx)) = S n
    /\ sum_of (fp_sharing P) (sec_scale P c (encode (fp_sharing P) s mx))
       = fp_mul P c s.
Proof.
  intros P n c s mx Hx. split.
  - rewrite sec_scale_length. unfold encode. rewrite length_app. simpl. lia.
  - rewrite sec_scale_sum, the_whole_sharing_recovers_the_secret. reflexivity.
Qed.

Definition refresh_step (m : Sharing) (xs masks : list (Val m)) : list (Val m) :=
  vec_add m xs (encode m (v_zero m) masks).

Definition fresh_stage_masks (m : Sharing) (tape : list (Val m)) (n l : nat)
  : list (Val m) := map (fun i => fresh_mask m tape n l i) (seq 0 n).

Fixpoint refresh_pipeline (m : Sharing) (n : nat) (s : Val m)
    (tape : list (Val m)) (stages : nat) : list (Val m) :=
  match stages with
  | 0 => encode m s (fresh_stage_masks m tape n 0)
  | S k => refresh_step m (refresh_pipeline m n s tape k)
             (fresh_stage_masks m tape n (S k))
  end.

Definition sec_refresh_pipeline (P : Modulus) (n : nat) (s : Fp P)
    (tape : list (Fp P)) (stages : nat) : list (Fp P) :=
  refresh_pipeline (fp_sharing P) n s tape stages.

Lemma vec_add_app :
  forall (m : Sharing) (a1 b1 a2 b2 : list (Val m)),
    length a1 = length a2 ->
    vec_add m (a1 ++ b1) (a2 ++ b2) = vec_add m a1 a2 ++ vec_add m b1 b2.
Proof.
  intros m a1 b1 a2 b2. revert a2.
  induction a1 as [ | x r1 IH ]; intros [ | y r2 ] H; simpl in *;
    try discriminate H; [ reflexivity | ].
  f_equal. apply IH. lia.
Qed.

Lemma v_sub_add_zero :
  forall (m : Sharing) (s a b : Val m),
    v_add m (v_sub m s a) (v_sub m (v_zero m) b) = v_sub m s (v_add m a b).
Proof.
  intros m s a b. apply (v_add_cancel_r m _ _ (v_add m a b)).
  rewrite (v_sub_add m s (v_add m a b)).
  rewrite (v_add_assoc m (v_add m (v_sub m s a) (v_sub m (v_zero m) b)) a b).
  rewrite <- (v_add_assoc m (v_sub m s a) (v_sub m (v_zero m) b) a).
  rewrite (v_add_comm m (v_sub m (v_zero m) b) a).
  rewrite (v_add_assoc m (v_sub m s a) a (v_sub m (v_zero m) b)).
  rewrite (v_sub_add m s a).
  rewrite <- (v_add_assoc m s (v_sub m (v_zero m) b) b).
  rewrite (v_sub_add m (v_zero m) b).
  rewrite (v_add_comm m s (v_zero m)), (v_add_zero_l m s).
  reflexivity.
Qed.

Lemma vec_add_encode_zero :
  forall (m : Sharing) (s : Val m) (xs masks : list (Val m)),
    length xs = length masks ->
    vec_add m (encode m s xs) (encode m (v_zero m) masks)
    = encode m s (vec_add m xs masks).
Proof.
  intros m s xs masks Hlen. unfold encode.
  rewrite vec_add_app by exact Hlen. f_equal. simpl. f_equal.
  rewrite vec_add_sum by exact Hlen. apply v_sub_add_zero.
Qed.

Lemma fresh_stage_masks_length :
  forall (m : Sharing) (tape : list (Val m)) (n l : nat),
    length (fresh_stage_masks m tape n l) = n.
Proof.
  intros m tape n l. unfold fresh_stage_masks. rewrite length_map. apply length_seq.
Qed.

Lemma vec_add_stage_tuple_fresh :
  forall (m : Sharing) (tape : list (Val m)) (n k : nat),
    vec_add m (stage_tuple m tape n k) (fresh_stage_masks m tape n (S k))
    = stage_tuple m tape n (S k).
Proof.
  intros m tape n k. unfold stage_tuple, fresh_stage_masks.
  generalize (seq 0 n) as l. induction l as [ | i r IH ]; simpl; [ reflexivity | ].
  f_equal. exact IH.
Qed.

Lemma refresh_pipeline_eq_stage_shares :
  forall (m : Sharing) (n : nat) (s : Val m) (tape : list (Val m)) (stages : nat),
    refresh_pipeline m n s tape stages = stage_shares m s tape n stages.
Proof.
  intros m n s tape stages. induction stages as [ | k IH ]; simpl.
  - reflexivity.
  - unfold refresh_step. rewrite IH. unfold stage_shares.
    rewrite vec_add_encode_zero
      by (rewrite stage_tuple_length, fresh_stage_masks_length; reflexivity).
    rewrite vec_add_stage_tuple_fresh. reflexivity.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem sec_refresh_pipeline_preserves_secret :
  forall (P : Modulus) (n : nat) (s : Fp P) (tape : list (Fp P)) (stages : nat),
    length (sec_refresh_pipeline P n s tape stages) = S n
    /\ sum_of (fp_sharing P) (sec_refresh_pipeline P n s tape stages) = s.
Proof.
  intros P n s tape stages. unfold sec_refresh_pipeline.
  rewrite refresh_pipeline_eq_stage_shares. split.
  - unfold stage_shares, encode. rewrite length_app, stage_tuple_length. simpl. lia.
  - apply every_stage_shares_the_same_secret.
Qed.

(* =========================================================================
   12. Arbitrary-order t <= n share-observation security across k stages
   with fresh per-stage masks and register barriers between stages.
   ========================================================================= *)

Definition pipeline_probe_view (m : Sharing) (s : Val m) (tape : list (Val m))
    (n : nat) (probes : list (nat * nat)) : list (Val m) :=
  map (fun p => wire_value m s tape n (fst p) (snd p)) probes.

Definition pipeline_probe_admissible (n stages : nat) (probes : list (nat * nat))
  : Prop :=
  forall p : nat * nat, In p probes -> fst p <= stages /\ snd p <= n.

Definition stage_probes_at (probes : list (nat * nat)) (st : nat) : list nat :=
  map snd (filter (fun p => Nat.eqb (fst p) st) probes).

Lemma stage_probes_at_length :
  forall (probes : list (nat * nat)) (st : nat),
    length (stage_probes_at probes st) <= length probes.
Proof.
  intros probes st. unfold stage_probes_at. rewrite length_map.
  induction probes as [ | p r IH ]; simpl; [ lia | ].
  destruct (Nat.eqb (fst p) st); simpl; lia.
Qed.

Lemma in_stage_probes_at :
  forall (probes : list (nat * nat)) (st j : nat),
    In (st, j) probes -> In j (stage_probes_at probes st).
Proof.
  intros probes st j H. unfold stage_probes_at.
  apply in_map_iff. exists (st, j). split; [ reflexivity | ].
  apply filter_In. split; [ exact H | apply Nat.eqb_refl ].
Qed.

Definition missing_wire (n : nat) (probes : list (nat * nat)) (st : nat) : nat :=
  match find (fun i => negb (mem_nat i (stage_probes_at probes st))) (seq 0 (S n)) with
  | Some i => i
  | None => n
  end.

Lemma mem_nat_in :
  forall (x : nat) (l : list nat), mem_nat x l = true <-> In x l.
Proof.
  intros x l. induction l as [ | y r IH ]; simpl; [ split; [ intros H; discriminate H | contradiction ] | ].
  rewrite orb_true_iff, Nat.eqb_eq, IH. split; intros [H | H]; auto.
Qed.

Lemma missing_wire_spec :
  forall (n : nat) (probes : list (nat * nat)) (st : nat),
    length (stage_probes_at probes st) <= n ->
    missing_wire n probes st <= n /\ ~ In (missing_wire n probes st) (stage_probes_at probes st).
Proof.
  intros n probes st Hlen. unfold missing_wire.
  destruct (find (fun i => negb (mem_nat i (stage_probes_at probes st))) (seq 0 (S n)))
    as [ i | ] eqn:Hfind.
  - apply find_some in Hfind. destruct Hfind as [Hin Hneg].
    apply in_seq in Hin. split; [ lia | ].
    intros Hin'. apply (proj2 (mem_nat_in i (stage_probes_at probes st))) in Hin'.
    rewrite Hin' in Hneg. discriminate Hneg.
  - exfalso.
    assert (Hincl : incl (seq 0 (S n)) (stage_probes_at probes st)).
    { intros i Hi. pose proof (find_none _ _ Hfind i Hi) as Hn.
      cbv beta in Hn. destruct (mem_nat i (stage_probes_at probes st)) eqn:Em;
        [ apply mem_nat_in; exact Em | discriminate Hn ]. }
    pose proof (NoDup_incl_length (seq_NoDup (S n) 0) Hincl) as Hle.
    rewrite length_seq in Hle. lia.
Qed.

Fixpoint shift_tuple (m : Sharing) (shifts xs : list (Val m)) : list (Val m) :=
  match shifts, xs with
  | cons d ds, cons x xr => cons (v_add m d x) (shift_tuple m ds xr)
  | _, _ => nil
  end.

Lemma shift_tuple_length :
  forall (m : Sharing) (shifts xs : list (Val m)),
    length shifts = length xs -> length (shift_tuple m shifts xs) = length xs.
Proof.
  intros m shifts. induction shifts as [ | d ds IH ]; intros [ | x xr ] H;
    simpl in *; try discriminate H; [ reflexivity | ].
  f_equal. apply IH. lia.
Qed.

Lemma shift_tuple_nth :
  forall (m : Sharing) (shifts xs : list (Val m)) (i : nat),
    i < length shifts -> length shifts = length xs ->
    nth i (shift_tuple m shifts xs) (v_zero m)
    = v_add m (nth i shifts (v_zero m)) (nth i xs (v_zero m)).
Proof.
  intros m shifts. induction shifts as [ | d ds IH ]; intros [ | x xr ] [ | i ] Hi Hlen;
    simpl in *; try lia; try reflexivity.
  apply IH; lia.
Qed.

Lemma shift_tuple_permutation :
  forall (m : Sharing) (len : nat) (shifts : list (Val m)),
    length shifts = len ->
    Perm (map (shift_tuple m shifts) (mask_tuples m len)) (mask_tuples m len).
Proof.
  intros m len. induction len as [ | k IH ]; intros shifts Hlen.
  - destruct shifts; simpl in Hlen; [ | discriminate Hlen ].
    simpl. apply perm_refl.
  - destruct shifts as [ | d ds ]; simpl in Hlen; [ discriminate Hlen | ].
    cbn [mask_tuples]. rewrite map_flatten.
    apply perm_trans with
      (flat_map (fun x => map (cons (v_add m d x)) (mask_tuples m k)) (v_enum m)).
    + apply perm_flat_map_pointwise. intros x _. rewrite map_map.
      change (Perm (map (fun r => cons (v_add m d x) (shift_tuple m ds r)) (mask_tuples m k))
                   (map (cons (v_add m d x)) (mask_tuples m k))).
      rewrite <- map_map. apply perm_map_std. apply IH. lia.
    + replace (flat_map (fun x => map (cons (v_add m d x)) (mask_tuples m k)) (v_enum m))
        with (flat_map (fun y => map (cons y) (mask_tuples m k)) (map (v_add m d) (v_enum m)))
        by (rewrite flat_map_mapped; reflexivity).
      apply perm_flat_map_std. rewrite <- map_over_is_map. exact (v_enum_shift m d).
Qed.

Definition fresh_delta_at (m : Sharing) (n : nat) (stage_delta : nat -> nat -> Val m)
    (idx : nat) : Val m :=
  let st := idx / n in
  let wire := idx mod n in
  match st with
  | 0 => stage_delta 0 wire
  | S k => v_sub m (stage_delta (S k) wire) (stage_delta k wire)
  end.

Definition pipeline_tape_shifts (m : Sharing) (n stages : nat)
    (stage_delta : nat -> nat -> Val m) : list (Val m) :=
  map (fresh_delta_at m n stage_delta) (seq 0 (S stages * n)).

Lemma pipeline_tape_shifts_length :
  forall (m : Sharing) (n stages : nat) (stage_delta : nat -> nat -> Val m),
    length (pipeline_tape_shifts m n stages stage_delta) = S stages * n.
Proof.
  intros m n stages stage_delta. unfold pipeline_tape_shifts.
  rewrite length_map. apply length_seq.
Qed.

Lemma fresh_mask_shift_tuple :
  forall (m : Sharing) (n stages st i : nat) (stage_delta : nat -> nat -> Val m)
         (tape : list (Val m)),
    0 < n -> st <= stages -> i < n -> length tape = S stages * n ->
    fresh_mask m (shift_tuple m (pipeline_tape_shifts m n stages stage_delta) tape) n st i
    = v_add m
        (match st with
         | 0 => stage_delta 0 i
         | S k => v_sub m (stage_delta (S k) i) (stage_delta k i)
         end)
        (fresh_mask m tape n st i).
Proof.
  intros m n stages st i stage_delta tape Hn Hs Hi Hlen.
  unfold fresh_mask.
  assert (Hidx : st * n + i < S stages * n) by nia.
  rewrite shift_tuple_nth;
    [ | rewrite pipeline_tape_shifts_length; exact Hidx
      | rewrite pipeline_tape_shifts_length, Hlen; reflexivity ].
  f_equal. unfold pipeline_tape_shifts.
  rewrite nth_map_seq by exact Hidx.
  unfold fresh_delta_at.
  assert (Hdiv : (st * n + i) / n = st)
    by (symmetry; apply (Nat.div_unique (st * n + i) n st i Hi); lia).
  assert (Hmod : (st * n + i) mod n = i)
    by (symmetry; apply (Nat.mod_unique (st * n + i) n st i Hi); lia).
  rewrite Hdiv, Hmod. reflexivity.
Qed.

Lemma stage_mask_shift_tuple :
  forall (m : Sharing) (n stages st i : nat) (stage_delta : nat -> nat -> Val m)
         (tape : list (Val m)),
    0 < n -> st <= stages -> i < n -> length tape = S stages * n ->
    stage_mask m (shift_tuple m (pipeline_tape_shifts m n stages stage_delta) tape) n st i
    = v_add m (stage_delta st i) (stage_mask m tape n st i).
Proof.
  intros m n stages st i stage_delta tape Hn Hs Hi Hlen.
  induction st as [ | k IH ].
  - cbn [stage_mask].
    exact (fresh_mask_shift_tuple m n stages 0 i stage_delta tape Hn Hs Hi Hlen).
  - cbn [stage_mask].
    rewrite IH by lia.
    rewrite (fresh_mask_shift_tuple m n stages (S k) i stage_delta tape Hn Hs Hi Hlen).
    set (d0 := stage_delta k i). set (d1 := stage_delta (S k) i).
    set (a := stage_mask m tape n k i). set (b := fresh_mask m tape n (S k) i).
    rewrite (v_add_assoc m (v_add m d0 a) (v_sub m d1 d0) b).
    rewrite (v_add_comm m (v_add m d0 a) (v_sub m d1 d0)).
    rewrite (v_add_assoc m (v_sub m d1 d0) d0 a).
    rewrite (v_sub_add m d1 d0).
    rewrite <- (v_add_assoc m d1 a b).
    reflexivity.
Qed.

Definition pipeline_stage_delta (m : Sharing) (n : nat) (probes : list (nat * nat))
    (delta : Val m) (st i : nat) : Val m :=
  if Nat.eqb i (missing_wire n probes st) then delta else v_zero m.

Lemma sum_of_stage_tuple_single_delta :
  forall (m : Sharing) (n stages st i0 : nat) (probes : list (nat * nat))
         (delta : Val m) (tape : list (Val m)),
    0 < n -> st <= stages -> i0 < n -> missing_wire n probes st = i0 ->
    length tape = S stages * n ->
    sum_of m (stage_tuple m
                (shift_tuple m (pipeline_tape_shifts m n stages
                                  (pipeline_stage_delta m n probes delta)) tape)
                n st)
    = v_add m delta (sum_of m (stage_tuple m tape n st)).
Proof.
  intros m n stages st i0 probes delta tape Hn Hs Hi0 Hmiss Hlen.
  set (tape' := shift_tuple m
                  (pipeline_tape_shifts m n stages
                     (pipeline_stage_delta m n probes delta)) tape).
  assert (Hext : forall i : nat, i < n ->
            stage_mask m tape' n st i
            = if Nat.eqb i i0
              then v_add m delta (stage_mask m tape n st i)
              else stage_mask m tape n st i).
  { intros i Hi. unfold tape'.
    rewrite (stage_mask_shift_tuple m n stages st i
               (pipeline_stage_delta m n probes delta) tape Hn Hs Hi Hlen).
    unfold pipeline_stage_delta. rewrite Hmiss.
    destruct (Nat.eqb i i0); [ reflexivity | apply v_add_zero_l ]. }
  unfold stage_tuple.
  assert (Hsum_gen : forall (l : list nat),
            (forall i : nat, In i l -> i < n) ->
            NoDup l ->
            sum_of m (map (fun i => stage_mask m tape' n st i) l)
            = v_add m (if mem_nat i0 l then delta else v_zero m)
                      (sum_of m (map (fun i => stage_mask m tape n st i) l))).
  { intros l. induction l as [ | x r IH ]; intros Hbound Hnd.
    - simpl. symmetry. apply v_add_zero_l.
    - inversion Hnd as [ | x0 r0 Hx Hr ]; subst x0 r0.
      assert (Hxlt : x < n) by (apply Hbound; left; reflexivity).
      assert (Hrbound : forall i : nat, In i r -> i < n)
        by (intros i Hi; apply Hbound; right; exact Hi).
      simpl. rewrite (IH Hrbound Hr).
      rewrite (Hext x Hxlt).
      destruct (Nat.eqb x i0) eqn:Ex.
      + apply Nat.eqb_eq in Ex. subst x.
        assert (Hmem : mem_nat i0 r = false).
        { destruct (mem_nat i0 r) eqn:Em; [ | reflexivity ].
          exfalso. apply Hx. apply mem_nat_in. exact Em. }
        change (mem_nat i0 (i0 :: r)) with (orb (Nat.eqb i0 i0) (mem_nat i0 r)).
        rewrite Nat.eqb_refl, Hmem. simpl.
        rewrite <- (v_add_assoc m delta (stage_mask m tape n st i0)
                      (v_add m (v_zero m) (sum_of m (map (fun i => stage_mask m tape n st i) r)))).
        f_equal. f_equal. apply v_add_zero_l.
      + assert (Eflip : Nat.eqb i0 x = false)
          by (apply Nat.eqb_neq; apply Nat.eqb_neq in Ex; lia).
        change (mem_nat i0 (x :: r)) with (orb (Nat.eqb i0 x) (mem_nat i0 r)).
        rewrite Eflip. simpl.
        destruct (mem_nat i0 r).
        * rewrite (v_add_assoc m (stage_mask m tape n st x) delta _).
          rewrite (v_add_comm m (stage_mask m tape n st x) delta).
          rewrite <- (v_add_assoc m delta (stage_mask m tape n st x) _).
          reflexivity.
        * rewrite !(v_add_zero_l m _). reflexivity. }
  assert (Hseq_bound : forall i : nat, In i (seq 0 n) -> i < n)
    by (intros i Hi; apply in_seq in Hi; lia).
  rewrite (Hsum_gen (seq 0 n) Hseq_bound (seq_NoDup n 0)).
  assert (Hmem : mem_nat i0 (seq 0 n) = true)
    by (apply mem_nat_in; apply in_seq; lia).
  rewrite Hmem. reflexivity.
Qed.

Lemma pipeline_probe_view_shift :
  forall (m : Sharing) (n stages : nat) (probes : list (nat * nat))
         (s1 s2 : Val m) (tape : list (Val m)),
    0 < n ->
    pipeline_probe_admissible n stages probes ->
    (forall st : nat, st <= stages -> length (stage_probes_at probes st) <= n) ->
    length tape = S stages * n ->
    pipeline_probe_view m s2
      (shift_tuple m
         (pipeline_tape_shifts m n stages
            (pipeline_stage_delta m n probes (v_sub m s2 s1)))
         tape)
      n probes
    = pipeline_probe_view m s1 tape n probes.
Proof.
  intros m n stages probes s1 s2 tape Hn Hadm Hper Hlen.
  set (tape' := shift_tuple m
                  (pipeline_tape_shifts m n stages
                     (pipeline_stage_delta m n probes (v_sub m s2 s1)))
                  tape).
  unfold pipeline_probe_view. apply map_ext_in. intros [ st j ] Hp.
  simpl. destruct (Hadm (st, j) Hp) as [ Hst Hj ]. simpl in Hst, Hj.
  destruct (missing_wire_spec n probes st (Hper st Hst)) as [ Hmiss_le Hmiss_out ].
  assert (Hnot : j <> missing_wire n probes st).
  { intros E. apply Hmiss_out. rewrite <- E. apply in_stage_probes_at. exact Hp. }
  destruct (Nat.lt_ge_cases j n) as [ Hjlt | Hjge ].
  - rewrite (mask_wire_value m s2 tape' n st j Hjlt).
    rewrite (mask_wire_value m s1 tape n st j Hjlt).
    unfold tape'.
    rewrite (stage_mask_shift_tuple m n stages st j
               (pipeline_stage_delta m n probes (v_sub m s2 s1)) tape
               Hn Hst Hjlt Hlen).
    unfold pipeline_stage_delta.
    assert (Ejf : Nat.eqb j (missing_wire n probes st) = false)
      by (apply Nat.eqb_neq; exact Hnot).
    rewrite Ejf. apply v_add_zero_l.
  - assert (Ejn : j = n) by lia. subst j.
    assert (Hmiss_lt : missing_wire n probes st < n) by lia.
    rewrite (completing_wire_value m s2 tape' n st).
    rewrite (completing_wire_value m s1 tape n st).
    unfold tape'.
    rewrite (sum_of_stage_tuple_single_delta m n stages st
               (missing_wire n probes st) probes (v_sub m s2 s1) tape
               Hn Hst Hmiss_lt eq_refl Hlen).
    apply v_sub_shift.
Qed.

(* Per-stage <= n share-observation security across all k+1 stages: every
   stage receives fresh masks, so even (k+1)*n total probes (at most n per
   stage) yield identical observation preimage multisets for any s1, s2. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem per_stage_bounded_pipeline_hides_secret :
  forall (m : Sharing) (n stages : nat) (probes : list (nat * nat)) (s1 s2 : Val m),
    0 < n ->
    pipeline_probe_admissible n stages probes ->
    (forall st : nat, st <= stages -> length (stage_probes_at probes st) <= n) ->
    Perm (map (fun tape => pipeline_probe_view m s1 tape n probes)
              (pipeline_tapes m n stages))
         (map (fun tape => pipeline_probe_view m s2 tape n probes)
              (pipeline_tapes m n stages))
    /\ SameDistribution (counting (list (Val m)) (pipeline_tapes m n stages))
         (list (Val m)) (list_eqb (v_eqb m))
         (fun tape => pipeline_probe_view m s1 tape n probes)
         (fun tape => pipeline_probe_view m s2 tape n probes).
Proof.
  intros m n stages probes s1 s2 Hn Hadm Hper.
  set (shifts := pipeline_tape_shifts m n stages
                   (pipeline_stage_delta m n probes (v_sub m s2 s1))).
  assert (Hperm : Perm (map (fun tape => pipeline_probe_view m s1 tape n probes)
                            (pipeline_tapes m n stages))
                       (map (fun tape => pipeline_probe_view m s2 tape n probes)
                            (pipeline_tapes m n stages))).
  { replace (map (fun tape => pipeline_probe_view m s1 tape n probes)
                 (pipeline_tapes m n stages))
      with (map (fun tape => pipeline_probe_view m s2 (shift_tuple m shifts tape) n probes)
                (pipeline_tapes m n stages)).
    - rewrite <- (map_map (shift_tuple m shifts)
                    (fun tape => pipeline_probe_view m s2 tape n probes)
                    (pipeline_tapes m n stages)).
      apply perm_map_std. unfold pipeline_tapes.
      apply shift_tuple_permutation. apply pipeline_tape_shifts_length.
    - apply map_ext_in. intros tape Htape.
      apply pipeline_probe_view_shift;
        [ exact Hn | exact Hadm | exact Hper | ].
      exact (mask_tuples_length m (S stages * n) tape Htape). }
  split; [ exact Hperm | ].
  apply equal_image_multisets_are_identically_distributed.
  repeat rewrite map_over_is_map. exact Hperm.
Qed.

(* Any t <= n probes across all k+1 stages of the pipeline yield identical
   observation preimage multisets and identical distributions for any two
   secrets s1, s2. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem arbitrary_order_pipeline_hides_secret :
  forall (m : Sharing) (n stages : nat) (probes : list (nat * nat)) (s1 s2 : Val m),
    0 < n ->
    length probes <= n ->
    pipeline_probe_admissible n stages probes ->
    Perm (map (fun tape => pipeline_probe_view m s1 tape n probes)
              (pipeline_tapes m n stages))
         (map (fun tape => pipeline_probe_view m s2 tape n probes)
              (pipeline_tapes m n stages))
    /\ SameDistribution (counting (list (Val m)) (pipeline_tapes m n stages))
         (list (Val m)) (list_eqb (v_eqb m))
         (fun tape => pipeline_probe_view m s1 tape n probes)
         (fun tape => pipeline_probe_view m s2 tape n probes).
Proof.
  intros m n stages probes s1 s2 Hn Hlen Hadm.
  apply per_stage_bounded_pipeline_hides_secret; [ exact Hn | exact Hadm | ].
  intros st _. pose proof (stage_probes_at_length probes st). lia.
Qed.

(* Prime-field instance written directly in terms of `sec_refresh_pipeline`
   at the final stage and the stage-wire projection across all stages. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem arbitrary_order_prime_field_pipeline_hides_secret :
  forall (P : Modulus) (n stages : nat) (probes : list (nat * nat)) (s1 s2 : Fp P),
    0 < n ->
    length probes <= n ->
    pipeline_probe_admissible n stages probes ->
    (forall tape : list (Fp P),
       sec_refresh_pipeline P n s1 tape stages
       = stage_shares (fp_sharing P) s1 tape n stages)
    /\ Perm (map (fun tape => pipeline_probe_view (fp_sharing P) s1 tape n probes)
                 (pipeline_tapes (fp_sharing P) n stages))
            (map (fun tape => pipeline_probe_view (fp_sharing P) s2 tape n probes)
                 (pipeline_tapes (fp_sharing P) n stages))
    /\ SameDistribution
         (counting (list (Fp P)) (pipeline_tapes (fp_sharing P) n stages))
         (list (Fp P)) (list_eqb (fp_eqb P))
         (fun tape => pipeline_probe_view (fp_sharing P) s1 tape n probes)
         (fun tape => pipeline_probe_view (fp_sharing P) s2 tape n probes).
Proof.
  intros P n stages probes s1 s2 Hn Hlen Hadm. split.
  - intros tape. unfold sec_refresh_pipeline.
    exact (refresh_pipeline_eq_stage_shares (fp_sharing P) n s1 tape stages).
  - exact (arbitrary_order_pipeline_hides_secret (fp_sharing P) n stages probes
             s1 s2 Hn Hlen Hadm).
Qed.

(* =========================================================================
   13. Cardinality-to-conditional-probability over exact integer mass ratios.
   ========================================================================= *)

Definition cond_prob_ratio {T O : Type} (enum : list T) (cond : T -> bool)
    (eqb : O -> O -> bool) (f : T -> O) (o : O) : nat * nat :=
  normalized_counting_observation (filter_of cond enum) eqb f o.

(* Proportional uniform preimage cardinalities (M * count1 = den1 and
   M * count2 = den2 with M > 0 and nonzero denominators) imply exact
   conditional probability equality num1 * den2 = num2 * den1. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem preimage_cardinality_implies_conditional_probability_equality :
  forall {T1 T2 O : Type}
         (enum1 : list T1) (enum2 : list T2)
         (cond1 : T1 -> bool) (cond2 : T2 -> bool)
         (eqb : O -> O -> bool) (f1 : T1 -> O) (f2 : T2 -> O)
         (o : O) (M : nat),
    0 < M ->
    0 < count_of (filter_of cond1 enum1) ->
    0 < count_of (filter_of cond2 enum2) ->
    M * count_of (filter_of (fun t => eqb (f1 t) o) (filter_of cond1 enum1))
      = count_of (filter_of cond1 enum1) ->
    M * count_of (filter_of (fun t => eqb (f2 t) o) (filter_of cond2 enum2))
      = count_of (filter_of cond2 enum2) ->
    let num1 := fst (cond_prob_ratio enum1 cond1 eqb f1 o) in
    let den1 := snd (cond_prob_ratio enum1 cond1 eqb f1 o) in
    let num2 := fst (cond_prob_ratio enum2 cond2 eqb f2 o) in
    let den2 := snd (cond_prob_ratio enum2 cond2 eqb f2 o) in
    num1 * den2 = num2 * den1 /\ den1 <> 0 /\ den2 <> 0.
Proof.
  intros T1 T2 O enum1 enum2 cond1 cond2 eqb f1 f2 o M HM Hpos1 Hpos2 Hc1 Hc2.
  unfold cond_prob_ratio, normalized_counting_observation. simpl.
  rewrite !counting_pr, !count_of_is_length in *.
  split; [ | split; lia ].
  assert (Hmul : M * (length (filter_of (fun t => eqb (f1 t) o) (filter_of cond1 enum1))
                      * length (filter_of cond2 enum2))
               = M * (length (filter_of (fun t => eqb (f2 t) o) (filter_of cond2 enum2))
                      * length (filter_of cond1 enum1))).
  { replace (M * (length (filter_of (fun t => eqb (f1 t) o) (filter_of cond1 enum1))
                  * length (filter_of cond2 enum2)))
      with ((M * length (filter_of (fun t => eqb (f1 t) o) (filter_of cond1 enum1)))
            * length (filter_of cond2 enum2)) by lia.
    replace (M * (length (filter_of (fun t => eqb (f2 t) o) (filter_of cond2 enum2))
                  * length (filter_of cond1 enum1)))
      with ((M * length (filter_of (fun t => eqb (f2 t) o) (filter_of cond2 enum2)))
            * length (filter_of cond1 enum1)) by lia.
    rewrite Hc1, Hc2. lia. }
  nia.
Qed.

(* Equal preimage multisets over a nonempty conditioned uniform space also
   imply exact conditional probability equality num1 * den2 = num2 * den1. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem equal_preimage_multiset_implies_conditional_probability_equality :
  forall {T O : Type} (enum : list T) (cond : T -> bool)
         (eqb : O -> O -> bool) (f1 f2 : T -> O) (o : O),
    0 < count_of (filter_of cond enum) ->
    Perm (map f1 (filter_of cond enum)) (map f2 (filter_of cond enum)) ->
    let num1 := fst (cond_prob_ratio enum cond eqb f1 o) in
    let den1 := snd (cond_prob_ratio enum cond eqb f1 o) in
    let num2 := fst (cond_prob_ratio enum cond eqb f2 o) in
    let den2 := snd (cond_prob_ratio enum cond eqb f2 o) in
    num1 * den2 = num2 * den1 /\ den1 <> 0 /\ den2 <> 0.
Proof.
  intros T O enum cond eqb f1 f2 o Hpos Hperm.
  unfold cond_prob_ratio, normalized_counting_observation. simpl.
  rewrite !counting_pr.
  assert (Hcnt : count_of (filter_of (fun t => eqb (f1 t) o) (filter_of cond enum))
               = count_of (filter_of (fun t => eqb (f2 t) o) (filter_of cond enum))).
  { rewrite (count_filter_image f1 (fun v => eqb v o) (filter_of cond enum)).
    rewrite (count_filter_image f2 (fun v => eqb v o) (filter_of cond enum)).
    rewrite !map_over_is_map.
    apply count_of_perm, perm_filter. exact Hperm. }
  rewrite Hcnt, count_of_is_length in *. split; [ lia | split; lia ].
Qed.

Lemma pipeline_tapes_count_positive :
  forall (m : Sharing) (n stages : nat),
    0 < count_of (pipeline_tapes m n stages).
Proof.
  intros m n stages. unfold pipeline_tapes.
  destruct (mask_tuples_nonempty m (S stages * n)) as [ xs Hxs ].
  destruct (mask_tuples m (S stages * n)) eqn:E; [ contradiction | simpl; lia ].
Qed.

Lemma filter_true_id :
  forall {A : Type} (l : list A), filter_of (fun _ => true) l = l.
Proof.
  intros A l. induction l as [ | x r IH ]; simpl; [ reflexivity | rewrite IH; reflexivity ].
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem single_wire_conditional_probability_equality :
  forall (m : Sharing) (n stages stage i : nat) (s1 s2 o : Val m),
    NoDup (v_enum m) -> 0 < n -> stage <= stages -> i <= n ->
    let num1 := fst (cond_prob_ratio (pipeline_tapes m n stages) (fun _ => true)
                       (v_eqb m) (fun tape => wire_value m s1 tape n stage i) o) in
    let den1 := snd (cond_prob_ratio (pipeline_tapes m n stages) (fun _ => true)
                       (v_eqb m) (fun tape => wire_value m s1 tape n stage i) o) in
    let num2 := fst (cond_prob_ratio (pipeline_tapes m n stages) (fun _ => true)
                       (v_eqb m) (fun tape => wire_value m s2 tape n stage i) o) in
    let den2 := snd (cond_prob_ratio (pipeline_tapes m n stages) (fun _ => true)
                       (v_eqb m) (fun tape => wire_value m s2 tape n stage i) o) in
    num1 * den2 = num2 * den1 /\ den1 <> 0 /\ den2 <> 0.
Proof.
  intros m n stages stage i s1 s2 o Hnd Hn Hs Hi.
  apply (preimage_cardinality_implies_conditional_probability_equality
           (pipeline_tapes m n stages) (pipeline_tapes m n stages)
           (fun _ => true) (fun _ => true)
           (v_eqb m)
           (fun tape => wire_value m s1 tape n stage i)
           (fun tape => wire_value m s2 tape n stage i)
           o (length (v_enum m))).
  - destruct (v_enum m) eqn:E; [ exfalso; exact (sharing_enumeration_nonempty m E) | simpl; lia ].
  - rewrite filter_true_id. apply pipeline_tapes_count_positive.
  - rewrite filter_true_id. apply pipeline_tapes_count_positive.
  - rewrite !filter_true_id.
    unfold pipeline_tapes at 2.
    rewrite (count_of_is_length (mask_tuples m (S stages * n))), mask_tuples_length_pow.
    exact (the_single_wire_preimage_count m s1 n stages stage i o Hnd Hn Hs Hi).
  - rewrite !filter_true_id.
    unfold pipeline_tapes at 2.
    rewrite (count_of_is_length (mask_tuples m (S stages * n))), mask_tuples_length_pow.
    exact (the_single_wire_preimage_count m s2 n stages stage i o Hnd Hn Hs Hi).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem arbitrary_order_pipeline_conditional_probability_equality :
  forall (m : Sharing) (n stages : nat) (probes : list (nat * nat))
         (s1 s2 : Val m) (o : list (Val m)),
    0 < n -> length probes <= n -> pipeline_probe_admissible n stages probes ->
    let num1 := fst (cond_prob_ratio (pipeline_tapes m n stages) (fun _ => true)
                       (list_eqb (v_eqb m))
                       (fun tape => pipeline_probe_view m s1 tape n probes) o) in
    let den1 := snd (cond_prob_ratio (pipeline_tapes m n stages) (fun _ => true)
                       (list_eqb (v_eqb m))
                       (fun tape => pipeline_probe_view m s1 tape n probes) o) in
    let num2 := fst (cond_prob_ratio (pipeline_tapes m n stages) (fun _ => true)
                       (list_eqb (v_eqb m))
                       (fun tape => pipeline_probe_view m s2 tape n probes) o) in
    let den2 := snd (cond_prob_ratio (pipeline_tapes m n stages) (fun _ => true)
                       (list_eqb (v_eqb m))
                       (fun tape => pipeline_probe_view m s2 tape n probes) o) in
    num1 * den2 = num2 * den1 /\ den1 <> 0 /\ den2 <> 0.
Proof.
  intros m n stages probes s1 s2 o Hn Hlen Hadm.
  apply equal_preimage_multiset_implies_conditional_probability_equality.
  - rewrite filter_true_id. apply pipeline_tapes_count_positive.
  - rewrite filter_true_id.
    exact (proj1 (arbitrary_order_pipeline_hides_secret m n stages probes s1 s2 Hn Hlen Hadm)).
Qed.

(* =========================================================================
   14. Negative witnesses:
   (a) Reused refresh mask across two stages leaks s1 - s2.
   (b) Omitted register barrier across prime-field linear recombination leaks
       under glitch expansion while remaining hidden under stable probing.
   ========================================================================= *)

Definition reused_mask_stage0 (P : Modulus) (s r : Fp P) : list (Fp P) :=
  encode (fp_sharing P) s (cons r nil).

Definition reused_mask_stage1 (P : Modulus) (s r : Fp P) : list (Fp P) :=
  refresh_step (fp_sharing P) (reused_mask_stage0 P s r) (cons r nil).

Definition reused_mask_joint_view (P : Modulus) (s r : Fp P) : Fp P * Fp P :=
  (nth 0 (reused_mask_stage0 P s r) (fp_zero P),
   nth 1 (reused_mask_stage1 P s r) (fp_zero P)).

Lemma v_sub_diff_cancel :
  forall (m : Sharing) (s1 s2 x : Val m),
    v_sub m (v_sub m s1 x) (v_sub m s2 x) = v_sub m s1 s2.
Proof.
  intros m s1 s2 x.
  apply (v_add_cancel_r m _ _ (v_sub m s2 x)).
  rewrite (v_sub_add m (v_sub m s1 x) (v_sub m s2 x)).
  apply (v_add_cancel_r m _ _ x).
  rewrite (v_sub_add m s1 x).
  rewrite <- (v_add_assoc m (v_sub m s1 s2) (v_sub m s2 x) x).
  rewrite (v_sub_add m s2 x).
  rewrite (v_sub_add m s1 s2).
  reflexivity.
Qed.

(* Even though stage 1 shares are valid secret shares of s, reusing stage 0's
   mask r in stage 1 leaks s1 - s2 across one probe per stage. *)
(*| discharges: R-05-165, R-05-166, R-15-053a |*)
Theorem reused_mask_recovers_secret_and_leaks_difference :
  forall (P : Modulus) (s s1 s2 r : Fp P),
    sum_of (fp_sharing P) (reused_mask_stage1 P s r) = s
    /\ fp_add P (fp_add P (fst (reused_mask_joint_view P s r))
                          (fst (reused_mask_joint_view P s r)))
                (snd (reused_mask_joint_view P s r)) = s
    /\ fp_sub P (snd (reused_mask_joint_view P s1 r))
                (snd (reused_mask_joint_view P s2 r)) = fp_sub P s1 s2.
Proof.
  intros P s s1 s2 r.
  assert (Hst1 : forall x : Fp P,
            reused_mask_stage1 P x r
            = encode (fp_sharing P) x (cons (fp_add P r r) nil)).
  { intros x. unfold reused_mask_stage1, reused_mask_stage0, refresh_step.
    rewrite vec_add_encode_zero by reflexivity. reflexivity. }
  split; [ rewrite Hst1; apply the_whole_sharing_recovers_the_secret | ].
  split.
  - unfold reused_mask_joint_view. rewrite Hst1.
    unfold reused_mask_stage0, encode. simpl.
    change (fp_add P (fp_add P r r)
              (fp_sub P s (fp_add P (fp_add P r r) (fp_zero P))) = s).
    rewrite (fp_add_comm P (fp_add P r r) (fp_zero P)), fp_add_zero_l.
    rewrite fp_add_comm. apply fp_sub_add.
  - unfold reused_mask_joint_view. rewrite !Hst1.
    unfold encode. simpl.
    exact (v_sub_diff_cancel (fp_sharing P) s1 s2 (fp_add P (fp_add P r r) (fp_zero P))).
Qed.

(* Each stage of the reused-mask pipeline is individually 1-probe hidden over F_5,
   yet probing one wire per stage distinguishes s1 = 0 from s2 = 1. *)
Definition fp_pair_eqb (P : Modulus) (a b : Fp P * Fp P) : bool :=
  andb (fp_eqb P (fst a) (fst b)) (fp_eqb P (snd a) (snd b)).

(*| discharges: R-05-165, R-05-166, R-15-053a |*)
Theorem reused_mask_stages_individually_hide_but_jointly_leak :
  (forall (i : nat) (s1 s2 : Fp five),
     i <= 1 ->
     SameDistribution (counting (Fp five) (fp_enum five)) (Fp five) (fp_eqb five)
       (fun r => nth i (reused_mask_stage0 five s1 r) (fp_zero five))
       (fun r => nth i (reused_mask_stage0 five s2 r) (fp_zero five)))
  /\ (forall (i : nat) (s1 s2 : Fp five),
        i <= 1 ->
        SameDistribution (counting (Fp five) (fp_enum five)) (Fp five) (fp_eqb five)
          (fun r => nth i (reused_mask_stage1 five s1 r) (fp_zero five))
          (fun r => nth i (reused_mask_stage1 five s2 r) (fp_zero five)))
  /\ ~ SameDistribution (counting (Fp five) (fp_enum five))
         (Fp five * Fp five) (fp_pair_eqb five)
         (fun r => reused_mask_joint_view five (fp_of five 0) r)
         (fun r => reused_mask_joint_view five (fp_of five 1) r).
Proof.
  split.
  - intros [ | [ | i ] ] s1 s2 Hi; [ | | lia ].
    + apply identical_views_are_identically_distributed. intros r. reflexivity.
    + apply (rerandomization_hides (counting (Fp five) (fp_enum five))
               (Fp five) (fp_eqb five) _ _
               (fp_add five (fp_sub five s2 s1))).
      * intros r. reflexivity.
      * apply fp_enum_shift.
      * intros r. unfold reused_mask_stage0, encode. simpl.
        rewrite !(fp_add_comm five _ (fp_zero five)), !fp_add_zero_l.
        exact (v_sub_shift (fp_sharing five) s1 s2 r).
  - split.
    + intros [ | [ | i ] ] s1 s2 Hi; [ | | lia ].
      * apply identical_views_are_identically_distributed. intros r. reflexivity.
      * apply (rerandomization_hides (counting (Fp five) (fp_enum five))
                 (Fp five) (fp_eqb five) _ _
                 (fp_add five (fp_mul five (fp_of five 3) (fp_sub five s2 s1)))).
        -- intros r. reflexivity.
        -- apply fp_enum_shift.
        -- intros r. unfold reused_mask_stage1, reused_mask_stage0, refresh_step.
           rewrite !(vec_add_encode_zero (fp_sharing five)) by reflexivity.
           unfold encode. simpl.
           rewrite !(fp_add_comm five _ (fp_zero five)), !fp_add_zero_l.
           set (d := fp_mul five (fp_of five 3) (fp_sub five s2 s1)).
           assert (H2d : fp_add five (fp_add five d r) (fp_add five d r)
                         = fp_add five (fp_sub five s2 s1) (fp_add five r r)).
           { assert (Hd : fp_add five d d = fp_sub five s2 s1).
             { unfold d, fp_add, fp_mul. apply fp_eq_rep. repeat rewrite fp_rep_of.
               rewrite Nat.Div0.add_mod_idemp_l, Nat.Div0.add_mod_idemp_r.
               pose proof (fp_rep_lt five (fp_sub five s2 s1)) as Hu.
               destruct (fp_rep (fp_sub five s2 s1)) as [ | [ | [ | [ | [ | k ] ] ] ] ];
                 simpl in *; try reflexivity; lia. }
             rewrite <- (fp_add_assoc five d r (fp_add five d r)).
             rewrite (fp_add_comm five r (fp_add five d r)).
             rewrite <- (fp_add_assoc five d r r).
             rewrite (fp_add_assoc five d d (fp_add five r r)).
             rewrite Hd. reflexivity. }
           rewrite H2d. exact (v_sub_shift (fp_sharing five) s1 s2 (fp_add five r r)).
  + intros H. specialize (H (fp_of five 0, fp_of five 0)).
    vm_compute in H. discriminate H.
Qed.

(* (b) Omitted register barrier across prime-field linear recombination:
   wire 3 computes x0 + r without a register, and wire 4 recombines
   (x0 + r) + x1. Stable probing on wire 4 observes s + r and hides s;
   glitch expansion on wire 4 observes [x0; r; x1] = [m; r; s - m] and
   recovers s. Placing a register barrier g_reg 3 on wire 4 restores
   1-probing security across every wire and cycle under ex_glitch. *)

Definition fp_ops (P : Modulus) (o : nat) (args : list (Fp P)) : Fp P :=
  match o with
  | 0 => fp_zero P
  | _ => sum_of (fp_sharing P) args
  end.

Definition omitted_barrier_circuit : Circuit :=
  cons (g_in 0)
  (cons (g_in 1)
  (cons (g_in 2)
  (cons (g_op 1 (cons 0 (cons 2 nil)))
  (cons (g_op 1 (cons 3 (cons 1 nil)))
  (cons (g_reg 4) nil))))).

Definition omitted_barrier_experiment : Experiment := {|
  x_share := fp_sharing five;
  x_prob := counting (list (Fp five)) (mask_tuples (fp_sharing five) 2);
  x_circuit := omitted_barrier_circuit;
  x_ops := fp_ops five;
  x_secret := Fp five;
  x_in := fun s tape _ i =>
            match i with
            | 0 => nth 0 tape (fp_zero five)
            | 1 => fp_sub five s (nth 0 tape (fp_zero five))
            | _ => nth 1 tape (fp_zero five)
            end;
  x_init := fun _ _ _ => fp_zero five;
  x_order := 1
|}.

(*| discharges: R-15-053a |*)
Theorem omitted_barrier_circuit_is_well_formed :
  well_formed omitted_barrier_circuit = true.
Proof. reflexivity. Qed.

(*| discharges: R-05-165, R-15-053a |*)
Theorem omitted_barrier_recombination_is_secure_under_stable :
  forall s1 s2 : Fp five,
    SameDistribution (x_prob omitted_barrier_experiment)
      (list (Fp five)) (list_eqb (fp_eqb five))
      (x_view omitted_barrier_experiment ex_stable (cons (probe_of 4 0) nil) s1)
      (x_view omitted_barrier_experiment ex_stable (cons (probe_of 4 0) nil) s2).
Proof.
  intros s1 s2.
  apply (counting_rerandomization_on_members (list (Fp five))
           (mask_tuples (fp_sharing five) 2)
           (list (Fp five)) (list_eqb (fp_eqb five))
           (x_view omitted_barrier_experiment ex_stable (cons (probe_of 4 0) nil) s1)
           (x_view omitted_barrier_experiment ex_stable (cons (probe_of 4 0) nil) s2)
           (shift_mask (fp_sharing five) 1 (fp_sub five s1 s2))).
  - rewrite map_over_is_map.
    exact (shift_mask_permutation (fp_sharing five) 2 1 (fp_sub five s1 s2) (ltac:(lia))).
  - intros tape Htape.
    assert (Hlen : length tape = 2)
      by (exact (mask_tuples_length (fp_sharing five) 2 tape Htape)).
    destruct tape as [ | m [ | r [ | ? ? ] ] ]; simpl in Hlen; try discriminate Hlen.
    unfold x_view, probe_set, ex_stable. simpl. unfold value_at. simpl.
    f_equal.
    rewrite !(fp_add_comm five _ (fp_zero five)), !fp_add_zero_l.
    rewrite (fp_add_comm five m (fp_add five (fp_sub five s1 s2) r)).
    rewrite <- (fp_add_assoc five (fp_sub five s1 s2) r m).
    rewrite (fp_add_comm five (fp_add five (fp_sub five s1 s2) (fp_add five r m)) (fp_sub five s2 m)).
    rewrite (fp_add_assoc five (fp_sub five s2 m) (fp_sub five s1 s2) (fp_add five r m)).
    rewrite (fp_add_comm five (fp_sub five s2 m) (fp_sub five s1 s2)).
    assert (Hs : fp_add five (fp_sub five s1 s2) (fp_sub five s2 m) = fp_sub five s1 m).
    { apply (v_add_cancel_r (fp_sharing five) _ _ m).
      change (fp_add five (fp_add five (fp_sub five s1 s2) (fp_sub five s2 m)) m
              = fp_add five (fp_sub five s1 m) m).
      rewrite <- (fp_add_assoc five (fp_sub five s1 s2) (fp_sub five s2 m) m).
      rewrite (fp_sub_add five s2 m).
      rewrite (fp_sub_add five s1 s2).
      rewrite (fp_sub_add five s1 m). reflexivity. }
    rewrite Hs.
    rewrite (fp_add_comm five (fp_sub five s1 m) (fp_add five r m)).
    rewrite (fp_add_comm five r m). reflexivity.
Qed.

(*| discharges: R-05-165, R-05-166, R-15-053a |*)
Theorem omitted_barrier_recombination_leaks_under_glitch :
  Leaks omitted_barrier_experiment ex_glitch.
Proof.
  intros H.
  specialize (H (cons (probe_of 4 0) nil) eq_refl (fp_of five 0) (fp_of five 1)).
  specialize (H (cons (fp_of five 0) (cons (fp_of five 0) (cons (fp_of five 0) nil)))).
  vm_compute in H. discriminate H.
Qed.

Definition barriered_recombination_circuit : Circuit :=
  cons (g_in 0)
  (cons (g_in 1)
  (cons (g_in 2)
  (cons (g_op 1 (cons 0 (cons 2 nil)))
  (cons (g_reg 3)
  (cons (g_op 1 (cons 4 (cons 1 nil))) nil))))).

Definition barriered_recombination_experiment : Experiment := {|
  x_share := fp_sharing five;
  x_prob := counting (list (Fp five)) (mask_tuples (fp_sharing five) 2);
  x_circuit := barriered_recombination_circuit;
  x_ops := fp_ops five;
  x_secret := Fp five;
  x_in := fun s tape _ i =>
            match i with
            | 0 => nth 0 tape (fp_zero five)
            | 1 => fp_sub five s (nth 0 tape (fp_zero five))
            | _ => nth 1 tape (fp_zero five)
            end;
  x_init := fun _ _ _ => fp_zero five;
  x_order := 1
|}.

(*| discharges: R-15-053a |*)
Theorem barriered_recombination_circuit_is_well_formed :
  well_formed barriered_recombination_circuit = true.
Proof. reflexivity. Qed.

(* Restoring the register barrier between x0 + r and + x1 makes every single
   wire at every cycle 1-probe secure even under glitch expansion. *)
(*| discharges: R-05-004a, R-15-053a |*)
Theorem barriered_recombination_is_probing_secure_under_glitch :
  ProbingSecure barriered_recombination_experiment ex_glitch.
Proof.
  intros ps Hps s1 s2.
  destruct ps as [ | [ w cyc ] [ | ? ? ] ].
  - apply identical_views_are_identically_distributed. intros t. reflexivity.
  - unfold admissible_probes in Hps.
    apply andb_prop in Hps as [ _ Hw ].
    unfold wires_exist, wire_count in Hw.
    rewrite all_of_is_forallb in Hw. simpl in Hw.
    rewrite andb_true_r in Hw. apply Nat.ltb_lt in Hw.
    assert (Hreg4 : forall (s : Fp five) (m r : Fp five) (k : nat),
              regs_at (fp_sharing five) (fp_ops five) barriered_recombination_circuit
                (fun _ => fp_zero five)
                (fun _ i => match i with
                            | 0 => m
                            | 1 => fp_sub five s m
                            | _ => r
                            end)
                k 4
              = match k with
                | 0 => fp_zero five
                | S _ => fp_add five m (fp_add five r (fp_zero five))
                end).
    { intros s m r k. induction k as [ | k IH ]; simpl; [ reflexivity | ].
      reflexivity. }
    destruct w as [ | [ | [ | [ | [ | [ | w ] ] ] ] ] ]; try lia.
    + (* w = 0 *)
      apply identical_views_are_identically_distributed. intros tape. reflexivity.
    + (* w = 1 *)
      set (d := fp_sub five s2 s1).
      apply (counting_rerandomization_on_members (list (Fp five))
               (mask_tuples (fp_sharing five) 2)
               (list (Fp five)) (list_eqb (fp_eqb five))
               (x_view barriered_recombination_experiment ex_glitch (cons (probe_of 1 cyc) nil) s1)
               (x_view barriered_recombination_experiment ex_glitch (cons (probe_of 1 cyc) nil) s2)
               (shift_mask (fp_sharing five) 0 d)).
      * rewrite map_over_is_map.
        exact (shift_mask_permutation (fp_sharing five) 2 0 d (ltac:(lia))).
      * intros tape Htape.
        assert (Hlen : length tape = 2)
          by (exact (mask_tuples_length (fp_sharing five) 2 tape Htape)).
        destruct tape as [ | m [ | r [ | ? ? ] ] ]; simpl in Hlen; try discriminate Hlen.
        unfold x_view, probe_set, ex_glitch. simpl. unfold value_at. simpl.
        f_equal. exact (v_sub_shift (fp_sharing five) s1 s2 m).
    + (* w = 2 *)
      apply identical_views_are_identically_distributed. intros tape. reflexivity.
    + (* w = 3 *)
      apply identical_views_are_identically_distributed. intros tape. reflexivity.
    + (* w = 4 *)
      apply identical_views_are_identically_distributed. intros tape.
      unfold x_view, probe_set, ex_glitch. simpl.
      unfold value_at. simpl.
      f_equal. rewrite !Hreg4. reflexivity.
    + (* w = 5 *)
      set (d := fp_sub five s2 s1).
      set (sigma := shift_tuple (fp_sharing five) (cons d (cons (fp_sub five (fp_zero five) d) nil))).
      apply (counting_rerandomization_on_members (list (Fp five))
               (mask_tuples (fp_sharing five) 2)
               (list (Fp five)) (list_eqb (fp_eqb five))
               (x_view barriered_recombination_experiment ex_glitch (cons (probe_of 5 cyc) nil) s1)
               (x_view barriered_recombination_experiment ex_glitch (cons (probe_of 5 cyc) nil) s2)
               sigma).
      * rewrite map_over_is_map.
        exact (shift_tuple_permutation (fp_sharing five) 2
                 (cons d (cons (fp_sub five (fp_zero five) d) nil)) eq_refl).
      * intros tape Htape.
        assert (Hlen : length tape = 2)
          by (exact (mask_tuples_length (fp_sharing five) 2 tape Htape)).
        destruct tape as [ | m [ | r [ | ? ? ] ] ]; simpl in Hlen; try discriminate Hlen.
        unfold x_view, probe_set, ex_glitch. simpl. unfold value_at. simpl.
        unfold value_at. simpl.
        rewrite !Hreg4. f_equal.
        -- destruct cyc as [ | k ]; [ reflexivity | ].
           rewrite !(fp_add_comm five _ (fp_zero five)), !fp_add_zero_l.
           unfold d.
           rewrite (fp_add_assoc five (fp_add five (fp_sub five s2 s1) m)
                                      (fp_sub five (fp_zero five) (fp_sub five s2 s1)) r).
           rewrite (fp_add_comm five (fp_sub five s2 s1) m).
           rewrite <- (fp_add_assoc five m (fp_sub five s2 s1)
                                    (fp_sub five (fp_zero five) (fp_sub five s2 s1))).
           rewrite (fp_add_comm five (fp_sub five s2 s1)
                                (fp_sub five (fp_zero five) (fp_sub five s2 s1))).
           rewrite (fp_sub_add five (fp_zero five) (fp_sub five s2 s1)).
           rewrite (fp_add_comm five m (fp_zero five)), fp_add_zero_l.
           reflexivity.
        -- f_equal. exact (v_sub_shift (fp_sharing five) s1 s2 m).
  - unfold admissible_probes in Hps. simpl in Hps. discriminate Hps.
Qed.



