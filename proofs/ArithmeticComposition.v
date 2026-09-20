(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ArithmeticComposition.v

   The arithmetic half of the post-M10 composition work, authored over
   ProbingModel.v's finite interfaces. Prime-field additive sharing over
   Z/pZ, a k-stage refresh pipeline with fresh masks between stages, the
   preimage-cardinality statement for a single observed wire, the finite
   probability reading of that cardinality with its normalizer stated, and
   the completing-share refutation that makes the bound tight.

   No Lean code is ported and no foreign tactic script is replayed. The
   MIT-licensed prime-field/k-stage artifact recorded in the crypto source
   inventory was read for citation only; every theorem below is authored
   here and checked by this repository's own prover.

   THE STATEMENT COMPARISON THE CHECK BULLET ASKS FOR.

   The source statement, as the inventory entry records it, bounds the
   preimage cardinality of a single-wire observation over a prime field
   with fresh masks between the stages of a k-stage composition. Read
   against R-15-053a's required statement, three hypotheses differ and one
   step is missing.

   a. Observation. The source observes one algebraic wire: one share of one
      stage, at its settled value. R-15-053a fixes the robust expansion,
      which observes every stable source of a probed wire at the probed
      cycle and at the cycle before it, so one physical probe yields a set
      of observations rather than one value. The single-wire statement is
      the ex_stable reading of one probe and reaches neither extension.
   b. Circuit. The source's circuit is the algebraic stage structure: share
      tuples and a refresh relation between them. R-15-053a's circuit is a
      gate list with registers, whose netlist half is discharged by
      execution-aware verification of the masked implementation. Nothing
      below evaluates a gate; the pipeline here is an algebraic model and
      `the_algebraic_pipeline_is_not_a_netlist_claim` says so as a
      statement rather than as prose.
   c. Order. The source bounds one observation. R-15-053a requires
      arbitrary order d, and the checklist's parent cell prices that
      generalization separately. What is proved below at arbitrary order is
      the share-observation case reached through ProbingModel.v's general
      additive-encoding theorem, instantiated at a prime field; the
      single-wire pipeline statements are first order in the probe count.
   d. The missing step. The source distinguishes its checked cardinality
      statement from an informal translation to a conditional-probability
      bound. That translation is supplied here, in the finite weighted-mass
      interface ProbingModel.v already carries: equality of outcome weights
      for any two secrets, a normalizer proved positive, and the exact
      identity p * numerator = denominator, which is the conditional
      probability 1/p written without a rational field.

   WHAT THIS FILE PROVES.

   1. Z/pZ as a finite carrier with a decidable equality whose soundness law
      holds, a complete duplicate-free enumeration, and the abelian-group
      laws; the result inhabits ProbingModel.v's `Sharing` record, so the
      arithmetic half and the Boolean half stand on one algebra.
   2. The k-stage pipeline: stage 0 is an additive encoding, each later
      stage is the previous tuple refreshed by that stage's fresh masks,
      and every stage's share list sums to the same secret.
   3. The preimage-cardinality statement in this prover's own terms. For a
      fixed secret, a fixed stage, a fixed wire and a fixed observed value,
      the number of mask tuples producing that observation, multiplied by
      p, is the whole tape count p^((k+1)n); equivalently the count is
      p^((k+1)n - 1). The mask wires and the completing share are both
      covered.
   4. The cardinality-to-probability connection: the weight of each
      single-wire observation is equal for any two secrets at every stage,
      in ProbingModel.v's exact-equality-of-outcome-weights notion, and the
      conditional reading is stated as a numerator/denominator pair whose
      denominator is positive and whose normalizer identity is proved.
   5. The refutation. A completing set of shares at one stage recovers the
      secret, and at p = 5 with one mask and one refresh the completing
      view separates two secrets by outcome weight 5 against 0, both weights
      computed by conversion and pinned as a statement rather than asserted
      here alone. The bound therefore has a refuting instance and is not
      vacuous.
   6. What primality buys and what it does not. The hiding argument
      consumes the abelian-group laws and a translation-invariant
      enumeration and nothing else, which is exhibited by instantiating the
      same theorem at the composite modulus 4. What primality does buy is
      invertibility, decided by conversion at 5 and refuted by conversion
      at 4. A concrete small prime witness discharges every field of the
      concrete-field record by conversion.

   WHAT REMAINS OWED, WITH ITS OWNER.

   Gadget composition is not among what is proved. Nothing is computed
   between the stages below: the pipeline is k successive refreshes of one
   sharing, and no gadget is applied to it, so "k-stage" here names the
   refresh depth and not a chain of composed operations. The composition
   notion R-15-053a requires, and the PINI ladder that carries it, stay with
   the Boolean half. Arbitrary order d over the glitch/transition model is
   the parent probing cell's and the Boolean half's, not this file's:
   nothing below observes a glitch walk or a transition pair. Fresh-mask
   renewal and the pipeline claims at that order are owed with it, since the
   refresh here is algebraic and its masks are independent by construction
   rather than by a proved property of a generator; R-05-004a's DRBG
   connection to uniform independent masks is a named assumption elsewhere
   and is not proved here. The algebraic-to-hardware arithmetic relation
   belongs at its consumer, the dedicated masked datapath of R-05-004a, and
   no theorem below relates a share tuple to a wire of that datapath.
   R-17-058d's combined fault and probing reduction is separate work over
   both axioms. R-17-058a keeps the physical residual: delay imbalance,
   coupling, layout and collection beyond the modeled order are outside
   every statement here. U-20 still owns any external probability
   foundation; the mass algebra used below is ProbingModel.v's own finite
   counting measure.

   READINGS THIS FILE TAKES, EACH A REVIEWABLE JUDGMENT.

   i.   A stage is an index and a wire is a share index, so a single-wire
        observation is `wire_value` at one stage and one index. The
        completing share is index n and the mask wires are the indices
        below it.
   ii.  The randomness is one flat tape of (k+1)n field elements, read at
        coordinate stage*n + wire. The pipeline's stage tuple is the
        prefix sum of those coordinates, which makes the refresh relation
        hold by computation rather than by an extra hypothesis.
   iii. A refresh adds this stage's fresh mask to each mask wire and
        subtracts their total from the completing share. That is the
        standard additive refresh and it is what `encode` over a prefix-sum
        tuple already is; `each_stage_refreshes_the_previous_tuple` records
        the identity.
   iv.  Independence of the fresh masks is the Cartesian tape enumeration,
        not a hypothesis about a generator.
   v.   Uniformity is the counting measure over that enumeration, and the
        probability reading is a pair of naturals with a proved normalizer
        rather than a rational.
   vi.  The adversary interface every theorem below covers is the fixed one,
        in the probing-model contract's own words, and no theorem here
        covers an adaptive one. Each statement quantifies its observation,
        a share index list or a stage-and-wire pair, ahead of the tape, and
        nothing below lets a later choice read an earlier observed value. A
        fixed observation list is not an adaptive strategy and is not
        described as one.

   The proofs use the Rocq prelude, the standard List, Arith, Bool, Lia and
   Eqdep_dec modules, and ProbingModel.v. Decidable-equality uniqueness of
   identity proofs is the constructive Eqdep_dec result and introduces no
   axiom. No global axioms and no admitted proofs are introduced. The Print
   Assumptions block at the end enumerates this file's named results, which
   is not the same set as every constant it ships: the four inhabitation
   witnesses of section 10 are reachable from no listed name. What covers
   every shipped constant is R-05-163's assumption gate, run by
   `run.py proofs`, which compares each constant's enumerated assumption set
   against the declared set R-05-164 makes empty, as section 11 records.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-004a R-05-163 R-05-164 R-05-165 R-05-166 R-15-053a R-17-058a R-17-058d
   SHA256: 76fbc1f9380b48e5cd6146ab3f9b454899f7cbc4a0d4ed0d2396031648460105
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

(* `primeb` is a decision about divisors and this is what it decides, so a
   later reader is not asked to take the name for the property. *)
(*| discharges: R-05-166 |*)
Theorem primeb_refuses_every_proper_divisor :
  forall (p d : nat), primeb p = true -> 2 <= d -> d < p -> Nat.modulo p d <> 0.
Proof.
  intros p d Hp H2 Hlt.
  unfold primeb in Hp. apply andb_prop in Hp. destruct Hp as [_ Hall].
  assert (Hin : In d (trial_divisors p)).
  { unfold trial_divisors. apply (proj2 (filter_In _ d (seq 0 p))). split.
    - apply (proj2 (in_seq p 0 d)). lia.
    - apply Nat.ltb_lt. lia. }
  pose proof (proj1 (forallb_forall _ (trial_divisors p)) Hall d Hin) as Hd.
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
  assert (Hr : fp_rep (fp_of P x) = fp_rep (fp_of P y)) by (rewrite H; reflexivity).
  rewrite fp_rep_of, fp_rep_of in Hr.
  rewrite (Nat.mod_small x _ Hx), (Nat.mod_small y _ Hy) in Hr. exact Hr.
Qed.

Lemma fp_in_enum : forall (P : Modulus) (a : Fp P), In a (fp_enum P).
Proof.
  intros P a. pose proof (fp_rep_lt P a) as Hlt.
  unfold fp_enum. rewrite <- (fp_of_rep P a) at 1.
  apply in_map. apply (proj2 (in_seq (pm_mod P) 0 (fp_rep a))). lia.
Qed.

Lemma nodup_map_injective :
  forall {A B : Type} (f : A -> B) (l : list A),
    (forall x y : A, In x l -> In y l -> f x = f y -> x = y) ->
    NoDup l -> NoDup (map f l).
Proof.
  intros A B f l. induction l as [ | x r IH ]; simpl; intros Hinj Hnd.
  - constructor.
  - inversion Hnd as [ | x' r' Hx Hr ]; subst. constructor.
    + intros Hin. apply (proj1 (in_map_iff f r (f x))) in Hin.
      destruct Hin as [ y [ Heq Hy ] ]. apply Hx.
      assert (Hxy : x = y).
      { apply Hinj; [ left; reflexivity | right; exact Hy | symmetry; exact Heq ]. }
      rewrite Hxy. exact Hy.
    + apply IH; [ | exact Hr ]. intros u v Hu Hv He.
      apply Hinj; [ right; exact Hu | right; exact Hv | exact He ].
Qed.

Lemma fp_enum_nodup : forall P : Modulus, NoDup (fp_enum P).
Proof.
  intros P. unfold fp_enum. apply nodup_map_injective; [ | apply seq_NoDup ].
  intros x y Hx Hy H.
  apply (proj1 (in_seq (pm_mod P) 0 x)) in Hx.
  apply (proj1 (in_seq (pm_mod P) 0 y)) in Hy.
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
  - apply nodup_map_injective; [ | apply fp_enum_nodup ].
    intros x y _ _ H. exact (fp_add_injective P k x y H).
  - apply fp_enum_nodup.
  - intros x. split; intros _.
    + apply fp_in_enum.
    + apply (proj2 (in_map_iff (fp_add P k) (fp_enum P) x)).
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
  induction stage as [ | k IH ].
  - cbn [stage_mask]. unfold fresh_mask. apply shift_mask_other. intros E.
    destruct (coordinate_unique n c i0 0 i Hi0 Hi E) as [ _ Heq ]. exact (Hne Heq).
  - cbn [stage_mask]. rewrite IH. f_equal.
    unfold fresh_mask. apply shift_mask_other. intros E.
    destruct (coordinate_unique n c i0 (S k) i Hi0 Hi E) as [ _ Heq ]. exact (Hne Heq).
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
  - intros i Hi. apply (proj1 (in_seq (n - 1) 1 i)) in Hi.
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
Proof. intros A p x l. cbn [filter_of]. destruct (p x); reflexivity. Qed.

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
    exfalso. assert (Hxy : x = y) by (symmetry; exact Heq).
    rewrite Hxy in E. rewrite (v_eqb_refl m y) in E. discriminate E.
Qed.

Lemma value_in_enumeration : forall (m : Sharing) (a : Val m), In a (v_enum m).
Proof.
  intros m a.
  assert (H : exists x : Val m, In x (v_enum m) /\ v_eqb m a x = true).
  { pose proof (v_enum_total m a) as Ht.
    generalize dependent Ht. generalize (v_enum m). intros l.
    induction l as [ | y r IH ]; simpl; intros Ht; [ discriminate Ht | ].
    destruct (v_eqb m a y) eqn:E.
    - exists y. split; [ left; reflexivity | exact E ].
    - simpl in Ht. destruct (IH Ht) as [ x [ Hx He ] ].
      exists x. split; [ right; exact Hx | exact He ]. }
  destruct H as [ x [ Hx He ] ]. rewrite (v_eqb_sound m a x He). exact Hx.
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

Lemma length_flat_map_constant :
  forall {A B : Type} (g : A -> list B) (l : list A) (c : nat),
    (forall a : A, In a l -> length (g a) = c) ->
    length (flat_map g l) = length l * c.
Proof.
  intros A B g l c. induction l as [ | x r IH ]; simpl; intros H; [ reflexivity | ].
  rewrite length_app. rewrite (H x (or_introl eq_refl)).
  rewrite IH; [ lia | intros a Ha; apply H; right; exact Ha ].
Qed.

Lemma mask_tuples_length_pow :
  forall (m : Sharing) (n : nat),
    length (mask_tuples m n) = (length (v_enum m)) ^ n.
Proof.
  intros m n. induction n as [ | k IH ]; [ reflexivity | ].
  cbn [mask_tuples].
  rewrite (length_flat_map_constant
             (fun x => map (cons x) (mask_tuples m k)) (v_enum m)
             ((length (v_enum m)) ^ k)).
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

(* A membership-restricted rerandomization over the counting measure. The
   general lemma in ProbingModel.v asks for its reindexing identity at every
   point of the carrier; a tape outside the enumeration is not one this
   pipeline's coordinates reach, so the restriction is what the pipeline
   can actually supply. *)
Lemma counting_rerandomization_on_members :
  forall (T : Type) (enum : list T) (O : Type) (oeqb : O -> O -> bool)
         (f g : T -> O) (sigma : T -> T),
    Perm (map_over sigma enum) enum ->
    (forall t : T, In t enum -> g (sigma t) = f t) ->
    SameDistribution (counting T enum) O oeqb f g.
Proof.
  intros T enum O oeqb f g sigma Hperm Hg o.
  rewrite counting_pr, counting_pr.
  transitivity (count_of (filter_of (fun t => oeqb (g (sigma t)) o) enum)).
  - f_equal. apply filter_of_ext_in. intros t Ht. rewrite (Hg t Ht). reflexivity.
  - rewrite (count_filter_image sigma (fun u => oeqb (g u) o) enum).
    apply count_of_perm. apply perm_filter. exact Hperm.
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
   11. R-05-163's assumption gate. Every shipped constant's enumerated
   assumption set is compared against the declared set R-05-164 makes empty.
   ========================================================================= *)

Print Assumptions primeb_refuses_every_proper_divisor.
Print Assumptions five_is_prime_and_four_is_not.
Print Assumptions fp_eq_rep.
Print Assumptions fp_sharing.
Print Assumptions prime_field_sharing_hides_from_short_share_lists.
Print Assumptions the_composite_modulus_is_refused_as_a_field.
Print Assumptions the_group_laws_survive_a_composite_modulus.
Print Assumptions each_stage_refreshes_the_previous_tuple.
Print Assumptions every_stage_shares_the_same_secret.
Print Assumptions the_algebraic_pipeline_is_not_a_netlist_claim.
Print Assumptions shiftable_observations_have_uniform_preimage_counts.
Print Assumptions mask_tuples_length_pow.
Print Assumptions the_single_wire_preimage_count.
Print Assumptions the_single_wire_observation_has_one_in_p_of_the_tapes.
Print Assumptions counting_rerandomization_on_members.
Print Assumptions every_stage_hides_the_secret_from_one_wire.
Print Assumptions the_conditional_reading_of_the_single_wire_bound.
Print Assumptions the_prime_field_pipeline_hides_every_single_wire.
Print Assumptions the_prime_field_single_wire_preimage_count.
Print Assumptions the_hiding_argument_does_not_consume_primality.
Print Assumptions the_demo_single_wire_has_five_preimages.
Print Assumptions a_completing_stage_view_recovers_the_secret.
Print Assumptions the_completing_stage_view_distinguishes_two_secrets.
Print Assumptions the_completing_stage_view_weighs_five_against_zero.
Print Assumptions the_demo_single_wire_is_not_a_leak.
Print Assumptions the_prime_field_inhabits_the_probing_model_sharing.
