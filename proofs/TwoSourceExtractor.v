(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   TwoSourceExtractor.v

   The finite two-source extraction statement R-15-241ca asks for before the
   TRNG selection closes: an exact theorem over named block widths, per-block
   min-entropy lower bounds, a joint independence premise, an adversary
   side-information premise, an output width and a statistical-distance
   bound, with accepted and failing parameter witnesses beside it. The
   construction is the binary inner product of Chor and Goldreich, which is
   the route the source-model contract's clause 10 selects as the first
   candidate. R-15-241a is why the entry exists at all: the single-root rule
   R-15-037 concentrates the entropy risk, and a predictable root is a
   failure of R-15-241b, R-15-241c, R-15-241d and R-15-241e rather than a
   case left to the crypto core.

   What this file is. A statement artifact over finite integer weights, not
   an implementation and not a source model. Probability is an exact integer
   formulation: a distribution on n-bit strings is a weight function into Z
   with a total weight, min-entropy k is the premise that every weight times
   2^k is at most the total, and independence of the two sources is the
   product of their weights. Nothing is divided, no real number appears, and
   the inequality is stated squared so that both sides are integers. No
   probability or game library exists in the locked switch, which
   ProbingModel.v records; the finite algebra below is original and imports
   only the standard List, Bool, Arith, ZArith and Lia modules. Every
   quantity the source contract fixes, the block width n, the two min-entropy
   bounds kX and kY, the invocation count m and the security parameter s, is
   a record field or a hypothesis, never a literal outside the witnesses.
   Nothing is admitted and nothing is axiomatized: the Print Assumptions
   block at the end reports every shipped constant closed under the global
   context, which is the R-05-163 assumption gate against R-05-164's
   currently empty declared set.

   What the gate's green line means. The stated theorems are compiled,
   axiom-free, non-vacuous and enumerated. No noise source is modelled, no
   sample is drawn, no health test is evaluated, no conditioner is computed
   and no bit is measured. Every entropy figure enters as a hypothesis about
   a weight function and never as a property of silicon.

   What this file establishes.

   1. chor_goldreich_squared. For independent finite sources of width n with
      min-entropy kX and kY, the signed bias numerator B, the totals W and V,
      B^2 * 2^(kX + kY) <= W^2 * V^2 * 2^n. The route is the weighted
      Cauchy-Schwarz inequality over finite integer sums and Parseval over
      the Walsh-Hadamard characters of the n-bit cube, both proved here by
      induction with no ordering or probability theory behind them.
   2. total_variation_scaling and total_variation_squared. The output bit's
      two masses, their sum W * V, and the identity 2 * mass(0) - W * V = B,
      which is the scaling 2 * Delta = |B| / (W * V) written without
      division. The squared bound is then the contract's displayed
      Delta <= (1/2) * 2^((n - kX - kY)/2).
   3. per_bit_squared_error, per_bit_total_variation_squared and
      bias_linear_bound. Under the contract's symbolic target
      kX + kY >= n + 2s, squared error at most 2^(-2s) in the bias scaling,
      which is Delta^2 <= 2^(-2s-2) in the total-variation reading; and the
      same bound without the square, |B| * 2^s <= W * V, both sides being
      squares of non-negative integers, so no square root is taken.
   4. conditional_pairs_carry_the_same_bound,
      observer_joint_distance_is_the_weighted_bias and
      observer_joint_meets_the_per_bit_budget. The observer clause. A
      conditioned family supplies a weight for every supported
      side-information value and, at each of them, a pair that is independent
      and carries both entropy bounds after conditioning. Each conditional
      pair then carries the bound; and the joint object (side value, output
      bit) stands at statistical distance exactly twice the weighted sum of
      the conditional biases from that same observer beside a uniform bit, so
      the per-invocation budget bounds the observer's joint view and not one
      conditional pair at a time. The premises are pointwise by construction,
      which is what the contract requires and what
      conditioning_can_destroy_independence and
      cond_joint_marginals_keep_full_min_entropy show cannot be inferred from
      the marginal premises.
   5. hybrid_aggregation and hybrid_error_budget. Statistical distance in the
      same integer scaling is a metric, so an m-step hybrid has total error
      at most the sum of the m per-invocation errors, and m invocations each
      within 2^(-s-1) aggregate to m * 2^(-s-1).
   6. conditioner_join and conditioner_join_over_bit_strings. A fixed map
      does not increase statistical distance, so a block epsilon-close to
      uniform is carried to an output epsilon-close to the image of uniform.
      conditioner_target_bound adds the separate distance from that image to
      a named target. hybrid_conditioner_error_budget carries both the
      accumulated invocation error and the conditioner image error in the
      same integer scaling. These algebraic inequalities are statistical
      distance bounds only for nonnegative distributions with equal positive
      totals; they do not supply a concrete conditioner's image error.
   7. parameters_bound_a_matching_pair, parameter_output_budget and
      accepted_parameters_are_realized. The parameter record joined to the
      distributions it prices: an admissible record bounds every pair whose
      three widths it names, out_width reads the output width off the record
      as the invocation count of one-bit outputs, the aggregate budget is
      stated at that width, and the accepted record is realized by a pair
      whose block width and min-entropy bounds are its own.
   8. finite_min_entropy_fits_width and two_source_entropy_fits_width.
      Positive finite n-bit source weights cannot meet a min-entropy lower
      bound k above n. matching_parameters_have_feasible_security therefore
      gives 2s <= n for a realizable record meeting this construction's
      sufficient entropy-sum premise, not for every extractor or every error
      bound. An arithmetically admissible record with impossible entropy
      widths has no realizing pair.

   What this file does not author, with the owner of each decision.

   a. The source model and every physical premise. S5 owns the actual noise
      sources, their stochastic model, across-sample and across-invocation
      dependence, common-mode coupling and the independently reviewed
      physical premises; R-15-241e owns source attribution and mechanism
      diversity, R-15-241b the health tests and their ordering before any
      extraction credit. No theorem here supplies a min-entropy figure, and a
      mathematical witness supplies no fabricated-source evidence. R-17-049a
      keeps undetectable source subversion and common-mode control of both
      sources open, and nothing below narrows that residual.
   b. The seed-accumulation invocation premises. The hybrid lemma consumes a
      per-invocation bound and a sequence of distributions; that each
      invocation's conditional premises hold against the prior history,
      including every observable rejection and timing transcript, is the
      qualification record's own obligation and is discharged nowhere here.
      The invocation count and the exact seed-length relation stay with
      R-15-241d and the crypto-core contract.
   c. The conditioner's actual map. The join lemma is stated for an arbitrary
      fixed function whose image values are enumerated once. The TM-8 map of
      R-15-241c, its widths, its vetted-function evidence and the separate
      instantiated distance delta_C from the image of uniform to the target
      uniform seed are not supplied here. The symbolic composition includes
      that term, and post_processing_keeps_distance_from_the_image_only
      is the construction showing why that second term cannot be dropped. A
      cryptographic claim about the conditioner remains a cryptographic claim
      with its own advantage and model.
   d. Resource fit. Raw-sample counts, representation fit, throughput,
      startup and reseed delay, storage and sustainable draw rate are the
      contract's cost row and are not evaluated here. An unaffordable
      candidate records an unqualified verdict whatever this file proves.
   e. Implementation refinement. No bit operation, buffer, erasure or
      execution bound is modelled, so nothing here connects an implemented
      circuit to the function IP.
   f. Which widths a fabricated source meets. accepted_pair realizes the
      accepted parameter record with a uniform pair, which is a mathematical
      object and no evidence about silicon; the block width, the two
      min-entropy bounds, the invocation count and the security parameter a
      real source supports are the qualification record's to fill. out_width
      names the output width as this construction's own invocation count of
      one-bit outputs, which is not a decision about the selected chain's
      output rate or the seed length R-15-241d owns.

   Readings of the register and the contract this statement takes, each a
   reviewable judgment rather than a neutral transcription.

   1. Min-entropy is stated as the exact integer premise `weight * 2^k <=
      total`, which is `Pr[X = x] <= 2^(-k)` cleared of its denominator. The
      total is a field-derived sum rather than a second field, so a
      distribution cannot declare a total its weights contradict.
   2. Independence is the product of the two weight functions and is not a
      separate hypothesis. This is why the observer clause is a family of
      pairs rather than a joint distribution with a side channel: a
      conditional pair that is not a product is outside the record, which is
      exactly what conditioning_can_destroy_independence exhibits.
   3. The bound is stated squared and multiplied out because the register
      asks for an exact finite theorem. Taking a square root would introduce
      either reals or a rounding convention, and neither is decided by a
      register entry.
   4. The failing parameter witness records a premise that does not hold. It
      is not a proof that no extraction is possible at those parameters; the
      construction that shows independence alone is insufficient is
      independence_without_an_entropy_sum_does_not_extract, at n = 2 with
      min-entropy exactly n/2 in each source, where the output is constant
      and the theorem holds with equality.
   5. Statistical distance is carried unnormalized, as the sum of absolute
      weight differences, so distributions compared by it share a total. A
      normalized reading divides by twice that total, which is the same
      scaling the total-variation corollary states.
   6. The conditioned family is the premise's shape and not a derivation. It
      carries the enumerated side-information values, their weights and the
      conditional pairs, and nothing here derives those pairs from an
      unconditioned joint by conditioning on an observer's value. That the
      supplied family is the one a real observer induces, and that its
      enumeration is the supported set, are premises the qualification record
      owes and that no theorem below checks.

   Non-vacuity (R-05-165, R-05-166). Every record the statements quantify
   over carries a closed inhabitant named for it. Each positive theorem has a
   refuting construction beside it: orthogonal supports whose sum of
   min-entropies only reaches n, a conditional joint no product of weights
   realizes although both its marginals keep full min-entropy, a conditioner
   carrying a uniform input to the maximum distance from uniform, and a
   hybrid whose aggregate reaches the sum of its steps rather than their
   maximum. The composed conditioner budget has an identity-map witness with
   nonzero hybrid error, and an admissible but unrealizable parameter record
   distinguishes an arithmetic budget from inhabited source premises.
   The observer statement, the accepted parameter record and its
   realizing pair are instantiated at computed values rather than left
   quantified. Whether a refuted construction is a telling one
   is a reading, discharged at R-05-150's review gate and booked under
   R-17-016 rather than claimed here.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-150 R-05-163 R-05-164 R-05-165 R-05-166 R-15-037 R-15-241a R-15-241b
      R-15-241c R-15-241ca R-15-241d R-15-241e R-17-016 R-17-049a
   SHA256: 2ab9561393d675fd1e7a1a9f11851fb4bac82e4e31c050f78fd2025ed33b37d2
   (*| END derived |*)
   ========================================================================= *)
From Stdlib Require Import ZArith List Bool Arith Lia.
Import ListNotations.
Open Scope Z_scope.

(* ---- finite integer sums over a list ---- *)

Fixpoint sumZ {A : Type} (l : list A) (g : A -> Z) : Z :=
  match l with
  | [] => 0
  | a :: r => g a + sumZ r g
  end.

Lemma sumZ_ext : forall {A} (l : list A) (g h : A -> Z),
  (forall a, In a l -> g a = h a) -> sumZ l g = sumZ l h.
Proof.
  intros A l g h H. induction l as [| a r IH]; cbn [sumZ]; [reflexivity |].
  rewrite (H a (or_introl eq_refl)). rewrite IH; [reflexivity |].
  intros b Hb. apply H. right. exact Hb.
Qed.

Lemma sumZ_app : forall {A} (l1 l2 : list A) (g : A -> Z),
  sumZ (l1 ++ l2) g = sumZ l1 g + sumZ l2 g.
Proof.
  intros A l1 l2 g. induction l1 as [| a r IH]; cbn [sumZ app]; lia.
Qed.

Lemma sumZ_map : forall {A B} (f : A -> B) (l : list A) (g : B -> Z),
  sumZ (map f l) g = sumZ l (fun a => g (f a)).
Proof.
  intros A B f l g. induction l as [| a r IH]; cbn [sumZ map]; [reflexivity |].
  rewrite IH. reflexivity.
Qed.

Lemma sumZ_scale : forall {A} (l : list A) (c : Z) (g : A -> Z),
  sumZ l (fun a => c * g a) = c * sumZ l g.
Proof.
  intros A l c g. induction l as [| a r IH]; cbn [sumZ]; [lia | rewrite IH; lia].
Qed.

Lemma sumZ_add : forall {A} (l : list A) (g h : A -> Z),
  sumZ l (fun a => g a + h a) = sumZ l g + sumZ l h.
Proof.
  intros A l g h. induction l as [| a r IH]; cbn [sumZ]; [lia | rewrite IH; lia].
Qed.

Lemma sumZ_zero : forall {A} (l : list A) (g : A -> Z),
  (forall a, In a l -> g a = 0) -> sumZ l g = 0.
Proof.
  intros A l g H. induction l as [| a r IH]; cbn [sumZ]; [reflexivity |].
  rewrite (H a (or_introl eq_refl)). rewrite IH; [reflexivity |].
  intros b Hb. apply H. right. exact Hb.
Qed.

Lemma sumZ_nonneg : forall {A} (l : list A) (g : A -> Z),
  (forall a, In a l -> 0 <= g a) -> 0 <= sumZ l g.
Proof.
  intros A l g H. induction l as [| a r IH]; cbn [sumZ]; [lia |].
  assert (0 <= g a) by (apply H; left; reflexivity).
  assert (0 <= sumZ r g) by (apply IH; intros b Hb; apply H; right; exact Hb).
  lia.
Qed.

Lemma sumZ_le : forall {A} (l : list A) (g h : A -> Z),
  (forall a, In a l -> g a <= h a) -> sumZ l g <= sumZ l h.
Proof.
  intros A l g h H. induction l as [| a r IH]; cbn [sumZ]; [lia |].
  assert (g a <= h a) by (apply H; left; reflexivity).
  assert (sumZ r g <= sumZ r h) by (apply IH; intros b Hb; apply H; right; exact Hb).
  lia.
Qed.

Lemma sumZ_swap : forall {A B} (l : list A) (m : list B) (f : A -> B -> Z),
  sumZ l (fun a => sumZ m (fun b => f a b))
  = sumZ m (fun b => sumZ l (fun a => f a b)).
Proof.
  intros A B l m f. induction l as [| a r IH]; cbn [sumZ].
  - symmetry. apply sumZ_zero. intros b _. reflexivity.
  - rewrite IH. rewrite <- sumZ_add. reflexivity.
Qed.

(* ---- powers of two, as an explicit recursion ---- *)

Fixpoint two_pow (n : nat) : Z :=
  match n with O => 1 | S m => 2 * two_pow m end.

Lemma two_pow_S : forall n, two_pow (S n) = 2 * two_pow n.
Proof. intro n. reflexivity. Qed.

Lemma two_pow_ge_one : forall n, 1 <= two_pow n.
Proof.
  induction n as [| m IH]; [cbn [two_pow]; lia | rewrite two_pow_S; lia].
Qed.

Lemma two_pow_pos : forall n, 0 < two_pow n.
Proof. intro n. pose proof (two_pow_ge_one n). lia. Qed.

Lemma two_pow_add : forall a b, two_pow (a + b) = two_pow a * two_pow b.
Proof.
  induction a as [| a IH]; intro b.
  - cbn [two_pow Nat.add]. lia.
  - replace (S a + b)%nat with (S (a + b)) by lia.
    rewrite two_pow_S, two_pow_S, (IH b). lia.
Qed.

Lemma two_pow_mono : forall a b, (a <= b)%nat -> two_pow a <= two_pow b.
Proof.
  intros a b H. replace b with (a + (b - a))%nat by lia.
  rewrite two_pow_add. pose proof (two_pow_pos a) as Hp.
  pose proof (two_pow_ge_one (b - a)) as Hq. nia.
Qed.

(* ---- n-bit strings, the sign character and the inner product ---- *)

Fixpoint strings (n : nat) : list (list bool) :=
  match n with
  | O => [[]]
  | S m => map (cons false) (strings m) ++ map (cons true) (strings m)
  end.

Lemma sumZ_cube_split : forall m (g : list bool -> Z),
  sumZ (strings (S m)) g
  = sumZ (strings m) (fun r => g (false :: r))
    + sumZ (strings m) (fun r => g (true :: r)).
Proof.
  intros m g. cbn [strings]. rewrite sumZ_app, sumZ_map, sumZ_map. reflexivity.
Qed.

Lemma strings_length : forall n x, In x (strings n) -> length x = n.
Proof.
  induction n as [| m IH]; intros x H; cbn [strings] in H.
  - destruct H as [H | H]; [subst; reflexivity | contradiction].
  - apply in_app_or in H. destruct H as [H | H]; apply in_map_iff in H;
      destruct H as [r [Hr Hin]]; subst x; cbn [length];
      rewrite (IH r Hin); reflexivity.
Qed.

Lemma strings_inhabited : forall n, exists x, In x (strings n).
Proof.
  induction n as [| m IH].
  - exists []. left. reflexivity.
  - destruct IH as [r Hr]. exists (false :: r). cbn [strings].
    apply in_or_app. left. apply in_map. exact Hr.
Qed.

Lemma strings_count : forall n, sumZ (strings n) (fun _ => 1) = two_pow n.
Proof.
  induction n as [| m IH].
  - cbn [strings sumZ two_pow]. lia.
  - rewrite sumZ_cube_split. cbv beta. rewrite IH, two_pow_S. lia.
Qed.

(* The sign character: +1 on false, -1 on true. *)
Definition chi (b : bool) : Z := if b then -1 else 1.

Lemma chi_xorb : forall a b, chi (xorb a b) = chi a * chi b.
Proof. intros [] []; reflexivity. Qed.

Fixpoint ip (x y : list bool) : bool :=
  match x, y with
  | a :: xs, b :: ys => xorb (andb a b) (ip xs ys)
  | _, _ => false
  end.

Fixpoint bxor (y y' : list bool) : list bool :=
  match y, y' with
  | b :: ys, b' :: ys' => xorb b b' :: bxor ys ys'
  | _, _ => []
  end.

Fixpoint allfalse (z : list bool) : bool :=
  match z with [] => true | b :: r => andb (negb b) (allfalse r) end.

Definition beqb (a b : bool) : bool := if a then b else negb b.

Fixpoint eqbits (a b : list bool) : bool :=
  match a, b with
  | [], [] => true
  | p :: r, q :: s => andb (beqb p q) (eqbits r s)
  | _, _ => false
  end.

Lemma eqbits_true : forall a b, eqbits a b = true -> a = b.
Proof.
  induction a as [| p r IH]; intros [| q s] H; cbn [eqbits] in H;
    try reflexivity; try discriminate.
  apply andb_true_iff in H as [H1 H2]. rewrite (IH s H2).
  destruct p; destruct q; cbn [beqb negb] in H1; try discriminate; reflexivity.
Qed.

Lemma eqbits_refl : forall a, eqbits a a = true.
Proof.
  induction a as [| p r IH]; cbn [eqbits]; [reflexivity |].
  rewrite IH. destruct p; reflexivity.
Qed.

Lemma ip_bxor : forall x y y', length y = length y' ->
  xorb (ip x y) (ip x y') = ip x (bxor y y').
Proof.
  induction x as [| a xs IH]; intros y y' Hlen; cbn [ip]; [reflexivity |].
  destruct y as [| b ys]; destruct y' as [| b' ys']; cbn [length] in Hlen;
    try discriminate.
  - reflexivity.
  - cbn [bxor ip]. rewrite <- (IH ys ys') by lia.
    destruct a; destruct b; destruct b'; cbn [andb xorb];
      destruct (ip xs ys); destruct (ip xs ys'); reflexivity.
Qed.

Lemma bxor_length : forall y y', length y = length y' ->
  length (bxor y y') = length y.
Proof.
  induction y as [| b ys IH]; intros [| b' ys'] H; cbn [length bxor] in *;
    try discriminate; [reflexivity |].
  rewrite (IH ys') by lia. reflexivity.
Qed.

Lemma bxor_allfalse_eq : forall y y', length y = length y' ->
  allfalse (bxor y y') = eqbits y y'.
Proof.
  induction y as [| b ys IH]; intros [| b' ys'] H; cbn [length bxor allfalse eqbits] in *;
    try discriminate; [reflexivity |].
  rewrite (IH ys') by lia. destruct b; destruct b'; reflexivity.
Qed.

(* Walsh-Hadamard orthogonality, by induction on the mask. *)
Lemma character_sum : forall z,
  sumZ (strings (length z)) (fun x => chi (ip x z))
  = if allfalse z then two_pow (length z) else 0.
Proof.
  induction z as [| b zs IH].
  - cbn [length strings sumZ ip allfalse chi two_pow]. lia.
  - cbn [length allfalse]. rewrite sumZ_cube_split. cbv beta.
    assert (Hf : sumZ (strings (length zs)) (fun r => chi (ip (false :: r) (b :: zs)))
                 = sumZ (strings (length zs)) (fun r => chi (ip r zs))).
    { apply sumZ_ext. intros r _. cbn [ip andb xorb]. reflexivity. }
    assert (Ht : sumZ (strings (length zs)) (fun r => chi (ip (true :: r) (b :: zs)))
                 = chi b * sumZ (strings (length zs)) (fun r => chi (ip r zs))).
    { rewrite <- sumZ_scale. apply sumZ_ext. intros r _. cbn [ip andb].
      rewrite chi_xorb. reflexivity. }
    rewrite Hf, Ht, IH, two_pow_S.
    generalize (two_pow (length zs)); intro P.
    destruct b; destruct (allfalse zs); cbn [chi negb andb]; lia.
Qed.

(* One point of an enumerated cube carries its own value and nothing else. *)
Lemma sumZ_delta : forall n y, length y = n -> forall (h : list bool -> Z),
  sumZ (strings n) (fun y' => h y' * (if eqbits y y' then 1 else 0)) = h y.
Proof.
  induction n as [| m IH]; intros y Hlen h.
  - destruct y as [| b ys]; [| cbn [length] in Hlen; discriminate].
    cbn [strings sumZ eqbits]. lia.
  - destruct y as [| b ys]; [cbn [length] in Hlen; discriminate |].
    assert (Hys : length ys = m) by (cbn [length] in Hlen; lia).
    rewrite sumZ_cube_split. cbv beta. specialize (IH ys Hys).
    destruct b.
    + assert (E0 : sumZ (strings m)
        (fun r => h (false :: r) * (if eqbits (true :: ys) (false :: r) then 1 else 0)) = 0).
      { apply sumZ_zero. intros r _. cbn [eqbits beqb andb]. lia. }
      assert (E1 : sumZ (strings m)
        (fun r => h (true :: r) * (if eqbits (true :: ys) (true :: r) then 1 else 0))
        = h (true :: ys)).
      { rewrite <- (IH (fun r => h (true :: r))). apply sumZ_ext.
        intros r _. cbn [eqbits beqb andb]. reflexivity. }
      rewrite E0, E1. lia.
    + assert (E0 : sumZ (strings m)
        (fun r => h (true :: r) * (if eqbits (false :: ys) (true :: r) then 1 else 0)) = 0).
      { apply sumZ_zero. intros r _. cbn [eqbits beqb negb andb]. lia. }
      assert (E1 : sumZ (strings m)
        (fun r => h (false :: r) * (if eqbits (false :: ys) (false :: r) then 1 else 0))
        = h (false :: ys)).
      { rewrite <- (IH (fun r => h (false :: r))). apply sumZ_ext.
        intros r _. cbn [eqbits beqb negb andb]. reflexivity. }
      rewrite E0, E1. lia.
Qed.

(* ---- weighted Cauchy-Schwarz over a finite list ---- *)

Lemma sumZ_mul_r : forall {A} (l : list A) (g : A -> Z) (c : Z),
  sumZ l g * c = sumZ l (fun a => g a * c).
Proof.
  intros A l g c. induction l as [| a r IH]; cbn [sumZ];
    [ring | rewrite <- IH; ring].
Qed.

Lemma sq_nonneg : forall z : Z, 0 <= z * z.
Proof. intro z. nia. Qed.

Lemma weighted_shift_nonneg : forall {A} (l : list A) (wf f : A -> Z) (c : Z),
  (forall a, In a l -> 0 <= wf a) ->
  2 * c * sumZ l (fun a => wf a * f a)
  <= sumZ l (fun a => wf a * f a * f a) + c * c * sumZ l wf.
Proof.
  intros A l wf f c H. induction l as [| a r IH]; cbn [sumZ]; [lia |].
  assert (Hw : 0 <= wf a) by (apply H; left; reflexivity).
  assert (Hr : forall b, In b r -> 0 <= wf b)
    by (intros b Hb; apply H; right; exact Hb).
  specialize (IH Hr).
  assert (Hsq : 0 <= wf a * ((f a - c) * (f a - c))).
  { apply Z.mul_nonneg_nonneg; [exact Hw | apply sq_nonneg]. }
  nia.
Qed.

Lemma cauchy_schwarz : forall {A} (l : list A) (wf f : A -> Z),
  (forall a, In a l -> 0 <= wf a) ->
  sumZ l (fun a => wf a * f a) * sumZ l (fun a => wf a * f a)
  <= sumZ l wf * sumZ l (fun a => wf a * f a * f a).
Proof.
  intros A l wf f H. induction l as [| a r IH]; cbn [sumZ]; [lia |].
  assert (Hw : 0 <= wf a) by (apply H; left; reflexivity).
  assert (Hr : forall b, In b r -> 0 <= wf b)
    by (intros b Hb; apply H; right; exact Hb).
  specialize (IH Hr).
  pose proof (weighted_shift_nonneg r wf f (f a) Hr) as Haux.
  assert (Hmul : wf a * (2 * f a * sumZ r (fun b => wf b * f b))
                 <= wf a * (sumZ r (fun b => wf b * f b * f b)
                            + f a * f a * sumZ r wf)).
  { apply Z.mul_le_mono_nonneg_l; [exact Hw | exact Haux]. }
  nia.
Qed.

(* ---- the Walsh transform of a weight function, and Parseval ---- *)

Definition walsh (n : nat) (v : list bool -> Z) (x : list bool) : Z :=
  sumZ (strings n) (fun y => v y * chi (ip x y)).

Lemma orthogonality : forall n y y', length y = n -> length y' = n ->
  sumZ (strings n) (fun x => chi (ip x y) * chi (ip x y'))
  = (if eqbits y y' then two_pow n else 0).
Proof.
  intros n y y' Hy Hy'.
  assert (Hb : length (bxor y y') = n) by (rewrite bxor_length by lia; exact Hy).
  transitivity (sumZ (strings n) (fun x => chi (ip x (bxor y y')))).
  { apply sumZ_ext. intros x _. rewrite <- chi_xorb.
    rewrite ip_bxor by lia. reflexivity. }
  replace n with (length (bxor y y')) by exact Hb.
  rewrite character_sum. rewrite bxor_allfalse_eq by lia. reflexivity.
Qed.

Lemma walsh_square : forall n v x,
  walsh n v x * walsh n v x
  = sumZ (strings n) (fun y => sumZ (strings n) (fun y' =>
      (v y * v y') * (chi (ip x y) * chi (ip x y')))).
Proof.
  intros n v x. unfold walsh. rewrite sumZ_mul_r.
  apply sumZ_ext. intros y _. rewrite <- sumZ_scale.
  apply sumZ_ext. intros y' _. ring.
Qed.

Lemma parseval : forall n v,
  sumZ (strings n) (fun x => walsh n v x * walsh n v x)
  = two_pow n * sumZ (strings n) (fun y => v y * v y).
Proof.
  intros n v.
  transitivity (sumZ (strings n) (fun y => sumZ (strings n) (fun y' =>
      sumZ (strings n) (fun x => (v y * v y') * (chi (ip x y) * chi (ip x y')))))).
  { erewrite sumZ_ext by (intros x _; apply walsh_square).
    rewrite sumZ_swap. apply sumZ_ext. intros y _. apply sumZ_swap. }
  transitivity (sumZ (strings n) (fun y => sumZ (strings n) (fun y' =>
      (v y * two_pow n) * (v y' * (if eqbits y y' then 1 else 0))))).
  { apply sumZ_ext. intros y Hy. apply sumZ_ext. intros y' Hy'.
    rewrite sumZ_scale.
    rewrite (orthogonality n y y') by (apply strings_length; assumption).
    destruct (eqbits y y'); ring. }
  transitivity (sumZ (strings n) (fun y => (v y * two_pow n) * v y)).
  { apply sumZ_ext. intros y Hy. rewrite sumZ_scale.
    rewrite (sumZ_delta n y (strings_length n y Hy) v). reflexivity. }
  rewrite <- sumZ_scale. apply sumZ_ext. intros y _. ring.
Qed.
(* ---- the two-source premises, as record fields ---- *)

Record TwoSource : Type := {
  ts_n : nat;
  ts_kX : nat;
  ts_kY : nat;
  ts_w : list bool -> Z;
  ts_v : list bool -> Z;
  ts_w_nonneg : forall x, In x (strings ts_n) -> 0 <= ts_w x;
  ts_v_nonneg : forall y, In y (strings ts_n) -> 0 <= ts_v y;
  ts_w_positive : 0 < sumZ (strings ts_n) ts_w;
  ts_v_positive : 0 < sumZ (strings ts_n) ts_v;
  ts_w_minent : forall x, In x (strings ts_n) ->
    ts_w x * two_pow ts_kX <= sumZ (strings ts_n) ts_w;
  ts_v_minent : forall y, In y (strings ts_n) ->
    ts_v y * two_pow ts_kY <= sumZ (strings ts_n) ts_v
}.

Definition totX (s : TwoSource) : Z := sumZ (strings (ts_n s)) (ts_w s).
Definition totY (s : TwoSource) : Z := sumZ (strings (ts_n s)) (ts_v s).

Definition joint (s : TwoSource) (x y : list bool) : Z := ts_w s x * ts_v s y.

Definition cg_bias (s : TwoSource) : Z :=
  sumZ (strings (ts_n s)) (fun x =>
    sumZ (strings (ts_n s)) (fun y => joint s x y * chi (ip x y))).

Lemma chor_goldreich_raw : forall (n kX kY : nat) (w v : list bool -> Z),
  (forall x, In x (strings n) -> 0 <= w x) ->
  (forall y, In y (strings n) -> 0 <= v y) ->
  (forall x, In x (strings n) -> w x * two_pow kX <= sumZ (strings n) w) ->
  (forall y, In y (strings n) -> v y * two_pow kY <= sumZ (strings n) v) ->
  sumZ (strings n) (fun x => w x * walsh n v x)
  * sumZ (strings n) (fun x => w x * walsh n v x)
  * two_pow (kX + kY)
  <= (sumZ (strings n) w * sumZ (strings n) w)
     * (sumZ (strings n) v * sumZ (strings n) v) * two_pow n.
Proof.
  intros n kX kY w v Hw Hv HkX HkY.
  assert (HW0 : 0 <= sumZ (strings n) w) by (apply sumZ_nonneg; exact Hw).
  assert (HB : sumZ (strings n) (fun x => w x * walsh n v x)
               * sumZ (strings n) (fun x => w x * walsh n v x)
               <= sumZ (strings n) w
                  * sumZ (strings n) (fun x => w x * walsh n v x * walsh n v x))
    by (apply cauchy_schwarz; exact Hw).
  assert (HQ : sumZ (strings n) (fun x => w x * walsh n v x * walsh n v x)
                 * two_pow kX
               <= sumZ (strings n) w
                  * sumZ (strings n) (fun x => walsh n v x * walsh n v x)).
  { apply Z.le_trans with (sumZ (strings n)
      (fun x => sumZ (strings n) w * (walsh n v x * walsh n v x))).
    - rewrite sumZ_mul_r. cbv beta. apply sumZ_le. intros x Hx.
      pose proof (HkX x Hx). pose proof (sq_nonneg (walsh n v x)). nia.
    - rewrite sumZ_scale. lia. }
  assert (HP : sumZ (strings n) (fun x => walsh n v x * walsh n v x)
               = two_pow n * sumZ (strings n) (fun y => v y * v y))
    by (apply parseval).
  assert (HQv : sumZ (strings n) (fun y => v y * v y) * two_pow kY
                <= sumZ (strings n) v * sumZ (strings n) v).
  { apply Z.le_trans with (sumZ (strings n) (fun y => v y * sumZ (strings n) v)).
    - rewrite sumZ_mul_r. cbv beta. apply sumZ_le. intros y Hy.
      pose proof (HkY y Hy). pose proof (Hv y Hy). nia.
    - rewrite <- sumZ_mul_r. lia. }
  rewrite two_pow_add.
  set (W := sumZ (strings n) w) in *.
  set (V := sumZ (strings n) v) in *.
  set (B := sumZ (strings n) (fun x => w x * walsh n v x)) in *.
  set (Q := sumZ (strings n) (fun x => w x * walsh n v x * walsh n v x)) in *.
  set (P := sumZ (strings n) (fun x => walsh n v x * walsh n v x)) in *.
  set (Qv := sumZ (strings n) (fun y => v y * v y)) in *.
  pose proof (two_pow_pos kX) as HX. pose proof (two_pow_pos kY) as HY.
  pose proof (two_pow_pos n) as Hn.
  assert (T1 : B * B * (two_pow kX * two_pow kY)
               <= (W * Q) * (two_pow kX * two_pow kY)).
  { apply Z.mul_le_mono_nonneg_r; [nia | exact HB]. }
  assert (T2 : (W * Q) * (two_pow kX * two_pow kY)
               <= (W * (W * P)) * two_pow kY).
  { replace ((W * Q) * (two_pow kX * two_pow kY))
      with ((W * (Q * two_pow kX)) * two_pow kY) by ring.
    apply Z.mul_le_mono_nonneg_r; [lia |].
    apply Z.mul_le_mono_nonneg_l; [exact HW0 | exact HQ]. }
  assert (T3 : (W * (W * P)) * two_pow kY
               = (W * W * two_pow n) * (Qv * two_pow kY))
    by (rewrite HP; ring).
  assert (T4 : (W * W * two_pow n) * (Qv * two_pow kY)
               <= (W * W * two_pow n) * (V * V)).
  { apply Z.mul_le_mono_nonneg_l; [| exact HQv].
    pose proof (sq_nonneg W). nia. }
  replace (W * W * (V * V) * two_pow n) with ((W * W * two_pow n) * (V * V)) by ring.
  lia.
Qed.

Lemma cg_bias_walsh : forall s : TwoSource,
  cg_bias s = sumZ (strings (ts_n s)) (fun x => ts_w s x * walsh (ts_n s) (ts_v s) x).
Proof.
  intro s. unfold cg_bias. apply sumZ_ext. intros x _.
  unfold walsh, joint. rewrite <- sumZ_scale.
  apply sumZ_ext. intros y _. ring.
Qed.

(* The Chor-Goldreich bound in squared integer form. *)
(*| discharges: R-15-241ca |*)
Theorem chor_goldreich_squared : forall s : TwoSource,
  cg_bias s * cg_bias s * two_pow (ts_kX s + ts_kY s)
  <= (totX s * totX s) * (totY s * totY s) * two_pow (ts_n s).
Proof.
  intro s. rewrite cg_bias_walsh. unfold totX, totY.
  apply chor_goldreich_raw.
  - apply ts_w_nonneg.
  - apply ts_v_nonneg.
  - apply ts_w_minent.
  - apply ts_v_minent.
Qed.
(* ---- the output bit's mass and the total-variation reading ---- *)

Lemma sumZ_sub : forall {A} (l : list A) (g h : A -> Z),
  sumZ l (fun a => g a - h a) = sumZ l g - sumZ l h.
Proof.
  intros A l g h. induction l as [| a r IH]; cbn [sumZ]; [lia | rewrite IH; lia].
Qed.

Definition ip_mass (s : TwoSource) (b : bool) : Z :=
  sumZ (strings (ts_n s)) (fun x =>
    sumZ (strings (ts_n s)) (fun y =>
      joint s x y * (if beqb (ip x y) b then 1 else 0))).

Lemma joint_total : forall s : TwoSource,
  sumZ (strings (ts_n s)) (fun x => sumZ (strings (ts_n s)) (fun y => joint s x y))
  = totX s * totY s.
Proof.
  intro s. unfold joint, totX, totY.
  transitivity (sumZ (strings (ts_n s))
    (fun x => ts_w s x * sumZ (strings (ts_n s)) (ts_v s))).
  { apply sumZ_ext. intros x _. cbv beta. rewrite sumZ_scale. reflexivity. }
  rewrite <- sumZ_mul_r. reflexivity.
Qed.

Lemma ip_mass_split : forall s : TwoSource,
  ip_mass s false + ip_mass s true = totX s * totY s.
Proof.
  intro s. unfold ip_mass. rewrite <- sumZ_add.
  rewrite <- (joint_total s). apply sumZ_ext. intros x _. cbv beta.
  rewrite <- sumZ_add. apply sumZ_ext. intros y _. cbv beta.
  destruct (ip x y); cbn [beqb negb]; ring.
Qed.

Lemma ip_mass_difference : forall s : TwoSource,
  ip_mass s false - ip_mass s true = cg_bias s.
Proof.
  intro s. unfold ip_mass, cg_bias. rewrite <- sumZ_sub.
  apply sumZ_ext. intros x _. cbv beta.
  rewrite <- sumZ_sub. apply sumZ_ext. intros y _. cbv beta.
  destruct (ip x y); cbn [beqb negb chi]; ring.
Qed.

(* Delta is |cg_bias| / (2 * totX * totY): the signed numerator is what the
   squared bound below constrains, and the scaling is stated here. *)
(*| discharges: R-15-241ca |*)
Corollary total_variation_scaling : forall s : TwoSource,
  ip_mass s false + ip_mass s true = totX s * totY s
  /\ ip_mass s false - ip_mass s true = cg_bias s
  /\ 2 * ip_mass s false - totX s * totY s = cg_bias s.
Proof.
  intro s. pose proof (ip_mass_split s) as Hs. pose proof (ip_mass_difference s) as Hd.
  split; [exact Hs | split; [exact Hd | lia]].
Qed.

(*| discharges: R-15-241ca |*)
Corollary total_variation_squared : forall s : TwoSource,
  (2 * ip_mass s false - totX s * totY s)
  * (2 * ip_mass s false - totX s * totY s)
  * two_pow (ts_kX s + ts_kY s)
  <= (totX s * totX s) * (totY s * totY s) * two_pow (ts_n s).
Proof.
  intro s. destruct (total_variation_scaling s) as [_ [_ Hb]].
  rewrite Hb. apply chor_goldreich_squared.
Qed.

(* ---- the parameter record the source contract fills ---- *)

Record Params : Type := {
  p_n : nat;
  p_kX : nat;
  p_kY : nat;
  p_m : nat;
  p_s : nat
}.

Definition admissible (p : Params) : bool :=
  Nat.leb (p_n p + 2 * p_s p) (p_kX p + p_kY p).

Lemma admissible_premise : forall p : Params,
  admissible p = true -> (p_n p + 2 * p_s p <= p_kX p + p_kY p)%nat.
Proof. intros p H. apply Nat.leb_le. exact H. Qed.

Lemma mul_cancel_le_pos : forall a b c : Z, 0 < c -> a * c <= b * c -> a <= b.
Proof. intros a b c Hc H. nia. Qed.

(* kX + kY >= n + 2s gives squared error at most 2^(-2s) in the bias scaling,
   which is Delta^2 <= 2^(-2s-2) in the total-variation reading below. *)
(*| discharges: R-15-241ca |*)
Corollary per_bit_squared_error : forall (s : TwoSource) (sec : nat),
  (ts_n s + 2 * sec <= ts_kX s + ts_kY s)%nat ->
  cg_bias s * cg_bias s * two_pow (2 * sec)
  <= (totX s * totX s) * (totY s * totY s).
Proof.
  intros s sec Hp.
  pose proof (chor_goldreich_squared s) as Hmain.
  pose proof (sq_nonneg (cg_bias s)) as Hb.
  pose proof (two_pow_pos (ts_n s)) as Hn.
  assert (Hstep : cg_bias s * cg_bias s * two_pow (ts_n s + 2 * sec)
                  <= cg_bias s * cg_bias s * two_pow (ts_kX s + ts_kY s)).
  { apply Z.mul_le_mono_nonneg_l; [exact Hb | apply two_pow_mono; lia]. }
  rewrite two_pow_add in Hstep.
  apply (mul_cancel_le_pos _ _ (two_pow (ts_n s)) Hn).
  replace (cg_bias s * cg_bias s * two_pow (2 * sec) * two_pow (ts_n s))
    with (cg_bias s * cg_bias s * (two_pow (ts_n s) * two_pow (2 * sec))) by ring.
  lia.
Qed.

(*| discharges: R-15-241ca |*)
Corollary per_bit_total_variation_squared : forall (s : TwoSource) (sec : nat),
  (ts_n s + 2 * sec <= ts_kX s + ts_kY s)%nat ->
  (2 * ip_mass s false - totX s * totY s)
  * (2 * ip_mass s false - totX s * totY s)
  * two_pow (2 * sec + 2)
  <= 4 * ((totX s * totX s) * (totY s * totY s)).
Proof.
  intros s sec Hp. destruct (total_variation_scaling s) as [_ [_ Hb]].
  rewrite Hb.
  pose proof (per_bit_squared_error s sec Hp) as Hmain.
  rewrite two_pow_add.
  replace (cg_bias s * cg_bias s * (two_pow (2 * sec) * two_pow 2))
    with ((cg_bias s * cg_bias s * two_pow (2 * sec)) * two_pow 2) by ring.
  cbn [two_pow]. lia.
Qed.

(* ---- the same bound without the square, and the widths a record names ---- *)

Lemma abs_sq : forall z : Z, Z.abs z * Z.abs z = z * z.
Proof. intro z. rewrite <- Z.abs_mul. apply Z.abs_eq. apply sq_nonneg. Qed.

Lemma two_pow_double : forall k, two_pow k * two_pow k = two_pow (2 * k).
Proof.
  intro k. replace (2 * k)%nat with (k + k)%nat by lia.
  rewrite two_pow_add. reflexivity.
Qed.

Lemma sq_le_nonneg : forall a b : Z, 0 <= a -> 0 <= b -> a * a <= b * b -> a <= b.
Proof.
  intros a b Ha Hb H.
  destruct (Z.le_gt_cases a b) as [Hle | Hgt]; [exact Hle | exfalso]. nia.
Qed.

(* Both sides of the squared bound are squares of non-negative integers, so the
   bound also holds without the square: |B| * 2^s <= W * V, which is the
   total-variation reading 2 * Delta <= 2^(-s). No square root is taken and no
   rounding convention is introduced; the linear form is what a weighted sum
   over an observer's values can be compared term by term. *)
(*| discharges: R-15-241ca |*)
Corollary bias_linear_bound : forall (s : TwoSource) (sec : nat),
  (ts_n s + 2 * sec <= ts_kX s + ts_kY s)%nat ->
  Z.abs (cg_bias s) * two_pow sec <= totX s * totY s.
Proof.
  intros s sec Hp.
  pose proof (per_bit_squared_error s sec Hp) as Hsq.
  pose proof (two_pow_pos sec) as Hpow.
  assert (HX : 0 < totX s) by (unfold totX; apply ts_w_positive).
  assert (HY : 0 < totY s) by (unfold totY; apply ts_v_positive).
  apply sq_le_nonneg.
  - apply Z.mul_nonneg_nonneg; [apply Z.abs_nonneg | lia].
  - apply Z.mul_nonneg_nonneg; lia.
  - replace (Z.abs (cg_bias s) * two_pow sec * (Z.abs (cg_bias s) * two_pow sec))
      with (Z.abs (cg_bias s) * Z.abs (cg_bias s) * (two_pow sec * two_pow sec))
      by ring.
    rewrite abs_sq, two_pow_double.
    replace (totX s * totY s * (totX s * totY s))
      with (totX s * totX s * (totY s * totY s)) by ring.
    exact Hsq.
Qed.

(* The construction emits one bit per invocation, so a parameter record's
   output width in bits is its invocation count. Naming it makes the register's
   output-width field a quantity of the statement rather than a sentence beside
   it; which width a selected source contract fills is not decided here. *)
Definition out_width (p : Params) : nat := p_m p.

(* A parameter record bounds any pair whose widths it names. Without this step
   the record and the distributions are two disconnected objects and
   `admissible` decides nothing about any source. *)
(*| discharges: R-15-241ca |*)
Theorem parameters_bound_a_matching_pair : forall (p : Params) (s : TwoSource),
  admissible p = true ->
  ts_n s = p_n p -> ts_kX s = p_kX p -> ts_kY s = p_kY p ->
  cg_bias s * cg_bias s * two_pow (2 * p_s p)
  <= (totX s * totX s) * (totY s * totY s).
Proof.
  intros p s Ha Hn HkX HkY. apply admissible_premise in Ha.
  apply per_bit_squared_error. rewrite Hn, HkX, HkY. exact Ha.
Qed.

(* ---- the observer clause: premises conditioned on every supported value ---- *)

Record ConditionedFamily : Type := {
  cf_side : Type;
  cf_enum : list cf_side;
  cf_pair : cf_side -> TwoSource;
  cf_w : cf_side -> Z;
  cf_w_nonneg : forall e, In e cf_enum -> 0 <= cf_w e
}.

(*| discharges: R-15-241ca |*)
Theorem conditional_pairs_carry_the_same_bound :
  forall (f : ConditionedFamily) (e : cf_side f), In e (cf_enum f) ->
  cg_bias (cf_pair f e) * cg_bias (cf_pair f e)
    * two_pow (ts_kX (cf_pair f e) + ts_kY (cf_pair f e))
  <= (totX (cf_pair f e) * totX (cf_pair f e))
     * (totY (cf_pair f e) * totY (cf_pair f e)) * two_pow (ts_n (cf_pair f e)).
Proof. intros f e _. apply chor_goldreich_squared. Qed.

(*| discharges: R-15-241ca |*)
Corollary conditional_pairs_meet_the_parameter_premise :
  forall (f : ConditionedFamily) (sec : nat) (e : cf_side f), In e (cf_enum f) ->
  (ts_n (cf_pair f e) + 2 * sec <= ts_kX (cf_pair f e) + ts_kY (cf_pair f e))%nat ->
  cg_bias (cf_pair f e) * cg_bias (cf_pair f e) * two_pow (2 * sec)
  <= (totX (cf_pair f e) * totX (cf_pair f e))
     * (totY (cf_pair f e) * totY (cf_pair f e)).
Proof. intros f sec e _ Hp. apply per_bit_squared_error. exact Hp. Qed.

(* ---- statistical distance, the hybrid, and post-processing ---- *)

Definition statdist {A} (l : list A) (f g : A -> Z) : Z :=
  sumZ l (fun a => Z.abs (f a - g a)).

Lemma statdist_nonneg : forall {A} (l : list A) (f g : A -> Z), 0 <= statdist l f g.
Proof. intros A l f g. apply sumZ_nonneg. intros a _. apply Z.abs_nonneg. Qed.

Lemma statdist_refl : forall {A} (l : list A) (f : A -> Z), statdist l f f = 0.
Proof.
  intros A l f. unfold statdist. apply sumZ_zero. intros a _.
  rewrite Z.sub_diag. reflexivity.
Qed.

Lemma statdist_triangle : forall {A} (l : list A) (f g h : A -> Z),
  statdist l f h <= statdist l f g + statdist l g h.
Proof.
  intros A l f g h. unfold statdist. rewrite <- sumZ_add.
  apply sumZ_le. intros a _. cbv beta.
  pose proof (Z.abs_triangle (f a - g a) (g a - h a)) as Ht.
  replace (f a - g a + (g a - h a)) with (f a - h a) in Ht by ring.
  lia.
Qed.

Lemma sumZ_abs : forall {A} (l : list A) (h : A -> Z),
  Z.abs (sumZ l h) <= sumZ l (fun a => Z.abs (h a)).
Proof.
  intros A l h. induction l as [| a r IH]; cbn [sumZ]; [lia |].
  pose proof (Z.abs_triangle (h a) (sumZ r h)). lia.
Qed.

Fixpoint natupto (m : nat) : list nat :=
  match m with O => [] | S k => natupto k ++ [k] end.

Lemma natupto_length : forall m, length (natupto m) = m.
Proof.
  induction m as [| k IH]; cbn [natupto length]; [reflexivity |].
  rewrite length_app, IH. cbn [length]. lia.
Qed.

Lemma sumZ_const : forall {A} (l : list A) (c : Z),
  sumZ l (fun _ => c) = Z.of_nat (length l) * c.
Proof.
  intros A l c. induction l as [| a r IH]; cbn [sumZ length]; [lia |].
  rewrite IH, Nat2Z.inj_succ. lia.
Qed.

(* A finite entropy bound cannot exceed the width of an inhabited source.
   Positivity of the total is essential: zero weights would satisfy every
   pointwise inequality at every claimed entropy. *)
Lemma two_pow_le_reflect : forall k n,
  two_pow k <= two_pow n -> (k <= n)%nat.
Proof.
  intros k n Hpow. destruct (Nat.le_gt_cases k n) as [Hle | Hgt].
  - exact Hle.
  - pose proof (two_pow_mono (S n) k Hgt) as Hmono.
    rewrite two_pow_S in Hmono. pose proof (two_pow_pos n). lia.
Qed.

(*| discharges: R-15-241ca |*)
Theorem finite_min_entropy_fits_width : forall (n k : nat) (w : list bool -> Z),
  0 < sumZ (strings n) w ->
  (forall x, In x (strings n) ->
     w x * two_pow k <= sumZ (strings n) w) ->
  (k <= n)%nat.
Proof.
  intros n k w Hpos Hent.
  pose proof (sumZ_le (strings n) (fun x => w x * two_pow k)
    (fun _ => sumZ (strings n) w) Hent) as Hsum.
  rewrite <- sumZ_mul_r, sumZ_const in Hsum.
  pose proof (strings_count n) as Hcount. rewrite sumZ_const in Hcount.
  apply two_pow_le_reflect. nia.
Qed.

(*| discharges: R-15-241ca |*)
Theorem two_source_entropy_fits_width : forall s : TwoSource,
  (ts_kX s <= ts_n s)%nat /\ (ts_kY s <= ts_n s)%nat.
Proof.
  intro s. split.
  - exact (finite_min_entropy_fits_width (ts_n s) (ts_kX s) (ts_w s)
      (ts_w_positive s) (ts_w_minent s)).
  - exact (finite_min_entropy_fits_width (ts_n s) (ts_kY s) (ts_v s)
      (ts_v_positive s) (ts_v_minent s)).
Qed.

(* This bounds the sufficient entropy-sum premise for the current candidate;
   it is not an impossibility theorem for other extraction constructions. *)
(*| discharges: R-15-241ca |*)
Theorem matching_parameters_have_feasible_security :
  forall (p : Params) (s : TwoSource),
  admissible p = true ->
  ts_n s = p_n p -> ts_kX s = p_kX p -> ts_kY s = p_kY p ->
  (2 * p_s p <= p_n p)%nat.
Proof.
  intros p s Hadm Hn HkX HkY.
  apply admissible_premise in Hadm.
  destruct (two_source_entropy_fits_width s) as [HX HY].
  rewrite Hn, HkX in HX. rewrite Hn, HkY in HY. lia.
Qed.

(* The m-output hybrid: total error at most the sum of the per-invocation
   errors, with no maximum taken and nothing assumed about the intermediate
   distributions beyond their being distributions on the same enumeration. *)
(*| discharges: R-15-241ca |*)
Theorem hybrid_aggregation : forall {A} (l : list A) (hyb : nat -> (A -> Z)) (m : nat),
  statdist l (hyb O) (hyb m)
  <= sumZ (natupto m) (fun i => statdist l (hyb i) (hyb (S i))).
Proof.
  intros A l hyb m. induction m as [| k IH].
  - cbn [natupto sumZ]. rewrite statdist_refl. lia.
  - cbn [natupto]. rewrite sumZ_app. cbn [sumZ].
    pose proof (statdist_triangle l (hyb O) (hyb k) (hyb (S k))). lia.
Qed.

(*| discharges: R-15-241ca |*)
Corollary hybrid_error_budget : forall {A} (l : list A) (hyb : nat -> (A -> Z))
    (m sec : nat) (bound : Z),
  (forall i, In i (natupto m) ->
     statdist l (hyb i) (hyb (S i)) * two_pow sec <= bound) ->
  statdist l (hyb O) (hyb m) * two_pow sec <= Z.of_nat m * bound.
Proof.
  intros A l hyb m sec bound H.
  pose proof (hybrid_aggregation l hyb m) as Hagg.
  pose proof (two_pow_pos sec) as Hs.
  assert (Hstep : sumZ (natupto m) (fun i => statdist l (hyb i) (hyb (S i)))
                    * two_pow sec
                  <= Z.of_nat m * bound).
  { rewrite sumZ_mul_r. cbv beta.
    apply Z.le_trans with (sumZ (natupto m) (fun _ : nat => bound)).
    - apply sumZ_le. exact H.
    - rewrite sumZ_const, natupto_length. lia. }
  assert (Hmul : statdist l (hyb O) (hyb m) * two_pow sec
                 <= sumZ (natupto m) (fun i => statdist l (hyb i) (hyb (S i)))
                    * two_pow sec)
    by (apply Z.mul_le_mono_nonneg_r; [lia | exact Hagg]).
  lia.
Qed.

(* The output width is the invocation count, so a parameter record's aggregate
   budget is its own m times the per-invocation bound: p_m enters a statement
   here rather than sitting inert in the record. *)
(*| discharges: R-15-241ca |*)
Corollary parameter_output_budget : forall (p : Params) (A : Type) (l : list A)
    (hyb : nat -> (A -> Z)) (bound : Z),
  (forall i, In i (natupto (out_width p)) ->
     statdist l (hyb i) (hyb (S i)) * two_pow (p_s p) <= bound) ->
  statdist l (hyb O) (hyb (out_width p)) * two_pow (p_s p)
  <= Z.of_nat (out_width p) * bound.
Proof. intros p A l hyb bound H. apply hybrid_error_budget. exact H. Qed.

Definition pushforward {A B} (enumA : list A) (eqB : B -> B -> bool)
    (C : A -> B) (f : A -> Z) (b : B) : Z :=
  sumZ enumA (fun a => f a * (if eqB (C a) b then 1 else 0)).

(* Post-processing by a fixed map does not increase statistical distance. *)
(*| discharges: R-15-241ca |*)
Theorem conditioner_join : forall {A B} (enumA : list A) (enumB : list B)
    (eqB : B -> B -> bool) (C : A -> B) (f g : A -> Z),
  (forall a, In a enumA ->
     sumZ enumB (fun b => if eqB (C a) b then 1 else 0) = 1) ->
  statdist enumB (pushforward enumA eqB C f) (pushforward enumA eqB C g)
  <= statdist enumA f g.
Proof.
  intros A B enumA enumB eqB C f g Hone.
  unfold statdist, pushforward.
  apply Z.le_trans with (sumZ enumB (fun b =>
      sumZ enumA (fun a => Z.abs (f a - g a) * (if eqB (C a) b then 1 else 0)))).
  - apply sumZ_le. intros b _. cbv beta.
    rewrite <- sumZ_sub. cbv beta.
    rewrite (sumZ_ext enumA
      (fun a => f a * (if eqB (C a) b then 1 else 0)
                - g a * (if eqB (C a) b then 1 else 0))
      (fun a => (f a - g a) * (if eqB (C a) b then 1 else 0)))
      by (intros a _; ring).
    apply Z.le_trans with (sumZ enumA
      (fun a => Z.abs ((f a - g a) * (if eqB (C a) b then 1 else 0)))).
    + apply sumZ_abs.
    + apply sumZ_le. intros a _. cbv beta.
      destruct (eqB (C a) b); [rewrite !Z.mul_1_r | rewrite !Z.mul_0_r]; lia.
  - rewrite sumZ_swap. apply Z.eq_le_incl. apply sumZ_ext. intros a Ha. cbv beta.
    rewrite sumZ_scale. rewrite (Hone a Ha). ring.
Qed.

Lemma bits_enumerated_once : forall n a, length a = n ->
  sumZ (strings n) (fun b => if eqbits a b then 1 else 0) = 1.
Proof.
  intros n a Ha.
  transitivity (sumZ (strings n) (fun b => (fun _ : list bool => 1) b
                                           * (if eqbits a b then 1 else 0))).
  - apply sumZ_ext. intros b _. ring.
  - exact (sumZ_delta n a Ha (fun _ => 1)).
Qed.

(*| discharges: R-15-241ca |*)
Corollary conditioner_join_over_bit_strings :
  forall (n n' : nat) (C : list bool -> list bool) (f g : list bool -> Z),
  (forall a, In a (strings n) -> length (C a) = n') ->
  statdist (strings n') (pushforward (strings n) eqbits C f)
                        (pushforward (strings n) eqbits C g)
  <= statdist (strings n) f g.
Proof.
  intros n n' C f g HC. apply conditioner_join.
  intros a Ha. apply bits_enumerated_once. apply HC. exact Ha.
Qed.

(* The distance to a target includes the error of the reference image.
   Interpreting these integer inequalities as normalized statistical distance
   requires nonnegative weights with equal positive totals. Neither the
   algebra nor a choice of target establishes those premises. *)
(*| discharges: R-15-241ca |*)
Theorem conditioner_target_bound :
  forall {A B} (enumA : list A) (enumB : list B)
    (eqB : B -> B -> bool) (C : A -> B) (f g : A -> Z) (target : B -> Z),
  (forall a, In a enumA ->
     sumZ enumB (fun b => if eqB (C a) b then 1 else 0) = 1) ->
  statdist enumB (pushforward enumA eqB C f) target
  <= statdist enumA f g
     + statdist enumB (pushforward enumA eqB C g) target.
Proof.
  intros A B enumA enumB eqB C f g target Hone.
  pose proof (statdist_triangle enumB (pushforward enumA eqB C f)
    (pushforward enumA eqB C g) target) as Htriangle.
  pose proof (conditioner_join enumA enumB eqB C f g Hone) as Hjoin. lia.
Qed.

(*| discharges: R-15-241ca |*)
Corollary conditioner_target_bound_over_bit_strings :
  forall (n n' : nat) (C : list bool -> list bool)
    (f g target : list bool -> Z),
  (forall a, In a (strings n) -> length (C a) = n') ->
  statdist (strings n') (pushforward (strings n) eqbits C f) target
  <= statdist (strings n) f g
     + statdist (strings n') (pushforward (strings n) eqbits C g) target.
Proof.
  intros n n' C f g target HC. apply conditioner_target_bound.
  intros a Ha. apply bits_enumerated_once. apply HC. exact Ha.
Qed.

(* Both budgets use the same 2^sec scaling. The invocation hypotheses still
   belong to the source qualification, and the image bound still belongs to
   the actual conditioner; neither is inferred from the other. *)
(*| discharges: R-15-241ca |*)
Theorem hybrid_conditioner_error_budget :
  forall {A B} (enumA : list A) (enumB : list B)
    (eqB : B -> B -> bool) (C : A -> B) (hyb : nat -> (A -> Z))
    (target : B -> Z) (m sec : nat) (bound image_bound : Z),
  (forall a, In a enumA ->
     sumZ enumB (fun b => if eqB (C a) b then 1 else 0) = 1) ->
  (forall i, In i (natupto m) ->
     statdist enumA (hyb i) (hyb (S i)) * two_pow sec <= bound) ->
  statdist enumB (pushforward enumA eqB C (hyb m)) target
    * two_pow sec <= image_bound ->
  statdist enumB (pushforward enumA eqB C (hyb O)) target
    * two_pow sec <= Z.of_nat m * bound + image_bound.
Proof.
  intros A B enumA enumB eqB C hyb target m sec bound image_bound
    Hone Hsteps Himage.
  pose proof (conditioner_target_bound enumA enumB eqB C
    (hyb O) (hyb m) target Hone) as Hjoin.
  pose proof (hybrid_error_budget enumA hyb m sec bound Hsteps) as Hhybrid.
  pose proof (two_pow_pos sec) as Hscale.
  assert (Hscaled :
    statdist enumB (pushforward enumA eqB C (hyb O)) target * two_pow sec
    <= (statdist enumA (hyb O) (hyb m)
      + statdist enumB (pushforward enumA eqB C (hyb m)) target) * two_pow sec).
  { apply Z.mul_le_mono_nonneg_r; [lia | exact Hjoin]. }
  nia.
Qed.

(* ---- the observer's joint output, as one statistical distance ---- *)

(* The observer holds a value e of weight cf_w e, and the pair conditioned on
   it is cf_pair e. The object compared below is the joint (side value, output
   bit), carried in the doubled scaling that keeps both halves integers: the
   real joint gives (e, b) the weight 2 * cf_w e * ip_mass e b, and the ideal
   joint gives each of the two bits cf_w e * totX e * totY e, which is the
   observer's own weight beside a uniform bit. *)
Definition obs_enum (f : ConditionedFamily) : list (cf_side f * bool) :=
  flat_map (fun e => [(e, false); (e, true)]) (cf_enum f).

Definition obs_real (f : ConditionedFamily) (p : cf_side f * bool) : Z :=
  2 * cf_w f (fst p) * ip_mass (cf_pair f (fst p)) (snd p).

Definition obs_ideal (f : ConditionedFamily) (p : cf_side f * bool) : Z :=
  cf_w f (fst p) * (totX (cf_pair f (fst p)) * totY (cf_pair f (fst p))).

Lemma sumZ_obs_enum : forall (f : ConditionedFamily) (g : cf_side f * bool -> Z),
  sumZ (obs_enum f) g = sumZ (cf_enum f) (fun e => g (e, false) + g (e, true)).
Proof.
  intros f g. unfold obs_enum.
  induction (cf_enum f) as [| e r IH]; cbn [flat_map app sumZ]; [reflexivity |].
  rewrite IH. lia.
Qed.

Lemma obs_pointwise : forall (f : ConditionedFamily) (e : cf_side f),
  In e (cf_enum f) ->
  Z.abs (obs_real f (e, false) - obs_ideal f (e, false))
  + Z.abs (obs_real f (e, true) - obs_ideal f (e, true))
  = 2 * (cf_w f e * Z.abs (cg_bias (cf_pair f e))).
Proof.
  intros f e He.
  pose proof (cf_w_nonneg f e He) as Hw.
  pose proof (ip_mass_split (cf_pair f e)) as Hs.
  pose proof (ip_mass_difference (cf_pair f e)) as Hd.
  unfold obs_real, obs_ideal. cbn [fst snd].
  set (s := cf_pair f e) in *. set (c := cf_w f e) in *.
  assert (H0 : 2 * ip_mass s false - totX s * totY s = cg_bias s) by lia.
  assert (H1 : 2 * ip_mass s true - totX s * totY s = - cg_bias s) by lia.
  replace (2 * c * ip_mass s false - c * (totX s * totY s))
    with (c * (2 * ip_mass s false - totX s * totY s)) by ring.
  replace (2 * c * ip_mass s true - c * (totX s * totY s))
    with (c * (2 * ip_mass s true - totX s * totY s)) by ring.
  rewrite H0, H1, !Z.abs_mul, Z.abs_opp, (Z.abs_eq c Hw). lia.
Qed.

(* The observer's value is inside the object the distance is taken over, so
   this is the distance of the pair (side value, output bit) from that same
   observer beside a uniform bit, and not a distance taken for one conditional
   pair at a time. *)
(*| discharges: R-15-241ca |*)
Theorem observer_joint_distance_is_the_weighted_bias :
  forall f : ConditionedFamily,
  statdist (obs_enum f) (obs_real f) (obs_ideal f)
  = 2 * sumZ (cf_enum f) (fun e => cf_w f e * Z.abs (cg_bias (cf_pair f e))).
Proof.
  intro f. unfold statdist. rewrite sumZ_obs_enum, <- sumZ_scale.
  apply sumZ_ext. intros e He. cbv beta. apply obs_pointwise. exact He.
Qed.

(*| discharges: R-15-241ca |*)
Corollary observer_joint_meets_the_per_bit_budget :
  forall (f : ConditionedFamily) (sec : nat),
  (forall e, In e (cf_enum f) ->
     (ts_n (cf_pair f e) + 2 * sec
      <= ts_kX (cf_pair f e) + ts_kY (cf_pair f e))%nat) ->
  statdist (obs_enum f) (obs_real f) (obs_ideal f) * two_pow sec
  <= 2 * sumZ (cf_enum f)
         (fun e => cf_w f e * (totX (cf_pair f e) * totY (cf_pair f e))).
Proof.
  intros f sec Hp.
  rewrite observer_joint_distance_is_the_weighted_bias.
  assert (Hstep :
    sumZ (cf_enum f) (fun e => cf_w f e * Z.abs (cg_bias (cf_pair f e)))
      * two_pow sec
    <= sumZ (cf_enum f)
         (fun e => cf_w f e * (totX (cf_pair f e) * totY (cf_pair f e)))).
  { rewrite sumZ_mul_r. apply sumZ_le. intros e He. cbv beta.
    pose proof (bias_linear_bound (cf_pair f e) sec (Hp e He)) as Hb.
    pose proof (cf_w_nonneg f e He) as Hw.
    assert (Hm : cf_w f e * (Z.abs (cg_bias (cf_pair f e)) * two_pow sec)
                 <= cf_w f e * (totX (cf_pair f e) * totY (cf_pair f e)))
      by (apply Z.mul_le_mono_nonneg_l; [exact Hw | exact Hb]).
    lia. }
  lia.
Qed.

(* ---- an accepted witness: two uniform n-bit sources ---- *)

Definition unif (x : list bool) : Z := 1.

Lemma unif_nonneg : forall n x, In x (strings n) -> 0 <= unif x.
Proof. intros n x _. unfold unif. lia. Qed.

Lemma unif_total : forall n, sumZ (strings n) unif = two_pow n.
Proof. intro n. unfold unif. apply strings_count. Qed.

Lemma unif_positive : forall n, 0 < sumZ (strings n) unif.
Proof. intro n. rewrite unif_total. apply two_pow_pos. Qed.

Lemma unif_minent : forall n x, In x (strings n) ->
  unif x * two_pow n <= sumZ (strings n) unif.
Proof. intros n x _. rewrite unif_total. unfold unif. lia. Qed.

Definition uniform_pair : TwoSource :=
  {| ts_n := 2; ts_kX := 2; ts_kY := 2; ts_w := unif; ts_v := unif;
     ts_w_nonneg := unif_nonneg 2; ts_v_nonneg := unif_nonneg 2;
     ts_w_positive := unif_positive 2; ts_v_positive := unif_positive 2;
     ts_w_minent := unif_minent 2; ts_v_minent := unif_minent 2 |}.

(*| discharges: R-15-241ca |*)
Theorem accepted_source_witness :
  totX uniform_pair = 4 /\ totY uniform_pair = 4
  /\ cg_bias uniform_pair = 4
  /\ ip_mass uniform_pair false = 10
  /\ ip_mass uniform_pair true = 6
  /\ ip_mass uniform_pair false + ip_mass uniform_pair true = 16.
Proof. repeat split; vm_compute; reflexivity. Qed.

Example accepted_source_meets_the_budget :
  cg_bias uniform_pair * cg_bias uniform_pair * two_pow (2 * 1)
  <= (totX uniform_pair * totX uniform_pair) * (totY uniform_pair * totY uniform_pair).
Proof.
  apply per_bit_squared_error. cbv [uniform_pair ts_n ts_kX ts_kY]. lia.
Qed.

(* ---- a refuting witness: orthogonal supports at entropy exactly n/2 ---- *)

Definition orth_w (x : list bool) : Z :=
  if orb (eqbits x [false; false]) (eqbits x [true; false]) then 1 else 0.
Definition orth_v (y : list bool) : Z :=
  if orb (eqbits y [false; false]) (eqbits y [false; true]) then 1 else 0.

Lemma orth_w_total : sumZ (strings 2) orth_w = 2.
Proof. vm_compute. reflexivity. Qed.
Lemma orth_v_total : sumZ (strings 2) orth_v = 2.
Proof. vm_compute. reflexivity. Qed.

Lemma orth_w_nonneg : forall x, In x (strings 2) -> 0 <= orth_w x.
Proof.
  intros x _. unfold orth_w.
  destruct (orb (eqbits x [false; false]) (eqbits x [true; false])); lia.
Qed.

Lemma orth_v_nonneg : forall y, In y (strings 2) -> 0 <= orth_v y.
Proof.
  intros y _. unfold orth_v.
  destruct (orb (eqbits y [false; false]) (eqbits y [false; true])); lia.
Qed.

Lemma orth_w_positive : 0 < sumZ (strings 2) orth_w.
Proof. rewrite orth_w_total. lia. Qed.
Lemma orth_v_positive : 0 < sumZ (strings 2) orth_v.
Proof. rewrite orth_v_total. lia. Qed.

Lemma orth_w_minent : forall x, In x (strings 2) ->
  orth_w x * two_pow 1 <= sumZ (strings 2) orth_w.
Proof.
  intros x _. rewrite orth_w_total. unfold orth_w. cbn [two_pow].
  destruct (orb (eqbits x [false; false]) (eqbits x [true; false])); lia.
Qed.

Lemma orth_v_minent : forall y, In y (strings 2) ->
  orth_v y * two_pow 1 <= sumZ (strings 2) orth_v.
Proof.
  intros y _. rewrite orth_v_total. unfold orth_v. cbn [two_pow].
  destruct (orb (eqbits y [false; false]) (eqbits y [false; true])); lia.
Qed.

Definition orth_pair : TwoSource :=
  {| ts_n := 2; ts_kX := 1; ts_kY := 1; ts_w := orth_w; ts_v := orth_v;
     ts_w_nonneg := orth_w_nonneg; ts_v_nonneg := orth_v_nonneg;
     ts_w_positive := orth_w_positive; ts_v_positive := orth_v_positive;
     ts_w_minent := orth_w_minent; ts_v_minent := orth_v_minent |}.

(* Independence and min-entropy exactly n/2 in each source leave the output
   bit constant, so the bound is met with equality and extracts nothing. *)
(*| discharges: R-15-241ca |*)
Theorem independence_without_an_entropy_sum_does_not_extract :
  (ts_kX orth_pair + ts_kY orth_pair = ts_n orth_pair)%nat
  /\ ip_mass orth_pair true = 0
  /\ ip_mass orth_pair false = totX orth_pair * totY orth_pair
  /\ cg_bias orth_pair = totX orth_pair * totY orth_pair
  /\ cg_bias orth_pair * cg_bias orth_pair
       * two_pow (ts_kX orth_pair + ts_kY orth_pair)
     = (totX orth_pair * totX orth_pair) * (totY orth_pair * totY orth_pair)
       * two_pow (ts_n orth_pair).
Proof. repeat split; vm_compute; reflexivity. Qed.

(* ---- a refuting witness for the observer clause ---- *)

(* The joint weight of two uniform bits conditioned on their exclusive-or
   being one. No pair of weight functions has this joint as its product, and
   the marginals keep full min-entropy, which the two theorems below state
   separately: conditional independence is a premise to be supplied and never
   a consequence of the marginal premises. *)
Definition cond_joint (x y : list bool) : Z := if eqbits x y then 0 else 1.

(*| discharges: R-15-241ca |*)
Theorem conditioning_can_destroy_independence :
  forall w v : list bool -> Z,
    (forall x y, In x (strings 1) -> In y (strings 1) ->
       cond_joint x y = w x * v y) -> False.
Proof.
  intros w v H.
  assert (I0 : In [false] (strings 1)) by (simpl; auto).
  assert (I1 : In [true] (strings 1)) by (simpl; auto).
  pose proof (H [false] [false] I0 I0) as H00.
  pose proof (H [true] [true] I1 I1) as H11.
  pose proof (H [false] [true] I0 I1) as H01.
  pose proof (H [true] [false] I1 I0) as H10.
  cbv [cond_joint eqbits beqb negb andb] in H00, H11, H01, H10.
  assert (E : (w [false] * v [false]) * (w [true] * v [true])
              = (w [false] * v [true]) * (w [true] * v [false])) by ring.
  rewrite <- H00, <- H11, <- H01, <- H10 in E. lia.
Qed.

(* Each marginal of that conditioned joint carries mass 1 against the total 2,
   which is the min-entropy premise at k = n = 1 met with equality. Flat
   marginals therefore supply no conditional independence, and the observer
   clause's pointwise premises are not recoverable from them. *)
(*| discharges: R-15-241ca |*)
Theorem cond_joint_marginals_keep_full_min_entropy :
  sumZ (strings 1) (fun x => sumZ (strings 1) (fun y => cond_joint x y)) = 2
  /\ sumZ (strings 1) (fun y => cond_joint [false] y) * two_pow 1 = 2
  /\ sumZ (strings 1) (fun y => cond_joint [true] y) * two_pow 1 = 2
  /\ sumZ (strings 1) (fun x => cond_joint x [false]) * two_pow 1 = 2
  /\ sumZ (strings 1) (fun x => cond_joint x [true]) * two_pow 1 = 2.
Proof. repeat split; vm_compute; reflexivity. Qed.

(* ---- a refuting witness for the conditioner join ---- *)

Definition const_zero_string (x : list bool) : list bool := [false].

(* Post-processing keeps distance from the image of uniform input, never from
   uniform output: a source at distance zero from uniform is carried to an
   output at the maximum distance from uniform. *)
(*| discharges: R-15-241ca |*)
Theorem post_processing_keeps_distance_from_the_image_only :
  statdist (strings 1) unif unif = 0
  /\ statdist (strings 1) (pushforward (strings 1) eqbits const_zero_string unif)
       (pushforward (strings 1) eqbits const_zero_string unif) = 0
  /\ statdist (strings 1) (pushforward (strings 1) eqbits const_zero_string unif) unif = 2.
Proof. repeat split; vm_compute; reflexivity. Qed.

(* ---- a refuting witness for the hybrid ---- *)

Definition ramp (i : nat) : list bool -> Z :=
  fun x => if eqbits x [false] then 4 - Z.of_nat i else Z.of_nat i.

(* The aggregate is the sum of the per-invocation errors and not their
   maximum: three invocations reach three times one invocation's error. *)
(*| discharges: R-15-241ca |*)
Theorem hybrid_sum_is_not_a_maximum :
  statdist (strings 1) (ramp O) (ramp 1) = 2
  /\ statdist (strings 1) (ramp O) (ramp 3) = 6
  /\ sumZ (natupto 3) (fun i => statdist (strings 1) (ramp i) (ramp (S i))) = 6.
Proof. repeat split; vm_compute; reflexivity. Qed.

(* ---- accepted and failing parameter witnesses ---- *)

Definition accepted_params : Params :=
  {| p_n := 8; p_kX := 6; p_kY := 6; p_m := 4; p_s := 2 |}.
Definition short_params : Params :=
  {| p_n := 8; p_kX := 3; p_kY := 3; p_m := 4; p_s := 2 |}.

(*| discharges: R-15-241ca |*)
Theorem parameter_witnesses :
  admissible accepted_params = true /\ admissible short_params = false.
Proof. split; vm_compute; reflexivity. Qed.

Lemma six_le_eight : (6 <= 8)%nat.
Proof. lia. Qed.

Lemma unif_minent_at : forall n k, (k <= n)%nat ->
  forall x, In x (strings n) -> unif x * two_pow k <= sumZ (strings n) unif.
Proof.
  intros n k Hk x _. rewrite unif_total. unfold unif.
  pose proof (two_pow_mono k n Hk). lia.
Qed.

(* The accepted parameter record realized as a pair of sources: a uniform pair
   at the record's block width, whose min-entropy premises hold at the record's
   two bounds because they lie below that width. Without it the record and the
   theorem are two objects and nothing says the accepted widths are ever met.
   The pair is a mathematical object; which distribution a fabricated source
   has is decided by the qualification record and not here. *)
Definition accepted_pair : TwoSource :=
  {| ts_n := 8; ts_kX := 6; ts_kY := 6; ts_w := unif; ts_v := unif;
     ts_w_nonneg := unif_nonneg 8; ts_v_nonneg := unif_nonneg 8;
     ts_w_positive := unif_positive 8; ts_v_positive := unif_positive 8;
     ts_w_minent := unif_minent_at 8 6 six_le_eight;
     ts_v_minent := unif_minent_at 8 6 six_le_eight |}.

(*| discharges: R-15-241ca |*)
Theorem accepted_parameters_are_realized :
  ts_n accepted_pair = p_n accepted_params
  /\ ts_kX accepted_pair = p_kX accepted_params
  /\ ts_kY accepted_pair = p_kY accepted_params
  /\ (out_width accepted_params = 4)%nat
  /\ admissible accepted_params = true
  /\ cg_bias accepted_pair * cg_bias accepted_pair
       * two_pow (2 * p_s accepted_params)
     <= (totX accepted_pair * totX accepted_pair)
        * (totY accepted_pair * totY accepted_pair).
Proof.
  repeat (split; [reflexivity |]).
  apply parameters_bound_a_matching_pair; reflexivity.
Qed.

(* The existing realized record also inhabits the finite-width statements. *)
(*| discharges: R-15-241ca |*)
Example accepted_parameters_meet_the_finite_bound :
  (ts_kX accepted_pair <= ts_n accepted_pair)%nat
  /\ (ts_kY accepted_pair <= ts_n accepted_pair)%nat
  /\ (2 * p_s accepted_params <= p_n accepted_params)%nat.
Proof.
  destruct (two_source_entropy_fits_width accepted_pair) as [HX HY].
  split; [exact HX |]. split; [exact HY |].
  apply (matching_parameters_have_feasible_security accepted_params accepted_pair);
    reflexivity.
Qed.

Definition impossible_entropy_params : Params :=
  {| p_n := 8; p_kX := 9; p_kY := 9; p_m := 4; p_s := 5 |}.

(* Admissibility prices an arithmetic inequality, not an inhabited source.
   The missing source cannot be supplied by a larger claimed entropy bound. *)
(*| discharges: R-15-241ca |*)
Theorem arithmetically_admissible_parameters_can_be_unrealizable :
  admissible impossible_entropy_params = true
  /\ ~ (exists s : TwoSource,
    ts_n s = p_n impossible_entropy_params
    /\ ts_kX s = p_kX impossible_entropy_params
    /\ ts_kY s = p_kY impossible_entropy_params).
Proof.
  split; [reflexivity |]. intros [s [Hn [HkX HkY]]].
  destruct (two_source_entropy_fits_width s) as [HX _].
  rewrite Hn, HkX in HX. change (9 <= 8)%nat in HX. lia.
Qed.

(* A constant map refutes dropping the additional image error, even for a
   uniform input with a positive total and the same input/output width. *)
(*| discharges: R-15-241ca |*)
Theorem conditioner_target_error_requires_the_image_term :
  ~ (forall C : list bool -> list bool,
    (forall a, In a (strings 1) -> length (C a) = 1%nat) ->
    statdist (strings 1) (pushforward (strings 1) eqbits C unif) unif
      <= statdist (strings 1) unif unif).
Proof.
  intro H.
  assert (HC : forall a, In a (strings 1) ->
    length (const_zero_string a) = 1%nat) by (intros; reflexivity).
  specialize (H const_zero_string HC).
  destruct post_processing_keeps_distance_from_the_image_only as [Hinput [_ Hout]].
  rewrite Hinput, Hout in H. lia.
Qed.

(* The additional image term is attainable, not merely a conservative bound. *)
(*| discharges: R-15-241ca |*)
Example constant_conditioner_target_bound_is_tight :
  statdist (strings 1)
    (pushforward (strings 1) eqbits const_zero_string unif) unif = 2
  /\ statdist (strings 1)
    (pushforward (strings 1) eqbits const_zero_string unif) unif <= 0 + 2.
Proof.
  destruct post_processing_keeps_distance_from_the_image_only as [Hinput [_ Hout]].
  split; [exact Hout |].
  pose proof (conditioner_target_bound_over_bit_strings 1 1 const_zero_string
    unif unif unif (fun a _ => eq_refl)) as Hbound.
  rewrite Hinput, Hout in Hbound. rewrite Hout. exact Hbound.
Qed.

(* All three hybrid members below have nonnegative weights and total four.
   With the identity conditioner the two per-step errors add exactly to the
   final error, while the reference image is exactly the target. *)
(*| discharges: R-15-241ca |*)
Example hybrid_conditioner_budget_is_realized :
  (forall i, In i (natupto 3) ->
    (forall x, In x (strings 1) -> 0 <= ramp i x)
    /\ sumZ (strings 1) (ramp i) = 4)
  /\ (forall i, In i (natupto 2) ->
    statdist (strings 1) (ramp i) (ramp (S i)) * two_pow 1 <= 4)
  /\ statdist (strings 1)
       (pushforward (strings 1) eqbits (fun x => x) (ramp 2)) (fun _ => 2) = 0
  /\ statdist (strings 1)
       (pushforward (strings 1) eqbits (fun x => x) (ramp O)) (fun _ => 2)
       * two_pow 1 = 8
  /\ statdist (strings 1)
       (pushforward (strings 1) eqbits (fun x => x) (ramp O)) (fun _ => 2)
       * two_pow 1 <= Z.of_nat 2 * 4 + 0.
Proof.
  assert (Hdistributions : forall i, In i (natupto 3) ->
    (forall x, In x (strings 1) -> 0 <= ramp i x)
    /\ sumZ (strings 1) (ramp i) = 4).
  { intros i Hi.
    assert (Hi2 : (i <= 2)%nat).
    { cbn [natupto app In] in Hi.
      destruct Hi as [Hi | [Hi | [Hi | Hi]]]; lia. }
    split.
    - intros x Hx. unfold ramp. destruct (eqbits x [false]); lia.
    - cbn [ramp strings map app sumZ eqbits beqb negb andb]. lia. }
  assert (Hsteps : forall i, In i (natupto 2) ->
    statdist (strings 1) (ramp i) (ramp (S i)) * two_pow 1 <= 4).
  { intros i Hi. cbn [natupto app In] in Hi.
    destruct Hi as [Hi | [Hi | Hi]]; [subst i | subst i | contradiction];
      change (4 <= 4); lia. }
  split; [exact Hdistributions |]. split; [exact Hsteps |].
  split; [vm_compute; reflexivity |].
  split; [vm_compute; reflexivity |].
  apply (hybrid_conditioner_error_budget (strings 1) (strings 1) eqbits
    (fun x => x) ramp (fun _ => 2) 2 1 4 0).
  - intros a Ha. apply bits_enumerated_once. exact (strings_length 1 a Ha).
  - exact Hsteps.
  - change (0 <= 0). lia.
Qed.

Lemma demo_weight_nonneg : forall e : bool, In e [true; false] -> 0 <= 1.
Proof. intros e _. lia. Qed.

Definition demo_family : ConditionedFamily :=
  {| cf_side := bool; cf_enum := [true; false];
     cf_pair := fun _ => uniform_pair;
     cf_w := fun _ => 1;
     cf_w_nonneg := demo_weight_nonneg |}.

(* The observer statement instantiated: two side-information values of weight
   one over the uniform pair, the joint (value, bit) at distance 16 from that
   observer beside a uniform bit, against the budget 64 at s = 1. *)
(*| discharges: R-15-241ca |*)
Theorem observer_joint_witness :
  statdist (obs_enum demo_family) (obs_real demo_family) (obs_ideal demo_family)
    = 16
  /\ 2 * sumZ (cf_enum demo_family)
           (fun e => cf_w demo_family e
                     * (totX (cf_pair demo_family e)
                        * totY (cf_pair demo_family e)))
     = 64
  /\ statdist (obs_enum demo_family) (obs_real demo_family)
       (obs_ideal demo_family) * two_pow 1 <= 64.
Proof.
  split; [vm_compute; reflexivity |].
  split; [vm_compute; reflexivity |].
  replace (statdist (obs_enum demo_family) (obs_real demo_family)
             (obs_ideal demo_family)) with 16 by (vm_compute; reflexivity).
  cbn [two_pow]. lia.
Qed.

(*| discharges: R-15-241ca |*)
Theorem witness_premises_are_jointly_inhabited :
  In true (cf_enum demo_family)
  /\ (ts_n (cf_pair demo_family true) + 2 * 1
      <= ts_kX (cf_pair demo_family true) + ts_kY (cf_pair demo_family true))%nat
  /\ admissible accepted_params = true
  /\ 0 < totX uniform_pair /\ 0 < totY uniform_pair.
Proof.
  split; [left; reflexivity |].
  split; [cbv [demo_family cf_pair uniform_pair ts_n ts_kX ts_kY]; lia |].
  split; [vm_compute; reflexivity |].
  split; vm_compute; reflexivity.
Qed.

Example inhabited_conditional_application :
  cg_bias (cf_pair demo_family true) * cg_bias (cf_pair demo_family true)
    * two_pow (2 * 1)
  <= (totX (cf_pair demo_family true) * totX (cf_pair demo_family true))
     * (totY (cf_pair demo_family true) * totY (cf_pair demo_family true)).
Proof.
  apply (conditional_pairs_meet_the_parameter_premise demo_family 1 true).
  - left. reflexivity.
  - cbv [demo_family cf_pair uniform_pair ts_n ts_kX ts_kY]. lia.
Qed.

(* ---- R-05-166's inhabitation witnesses ---- *)

Definition witness_TwoSource : TwoSource := uniform_pair.
Definition witness_Params : Params := accepted_params.
Definition witness_ConditionedFamily : ConditionedFamily := demo_family.

(* ---- R-05-163's assumption gate ---- *)

Print Assumptions chor_goldreich_squared.
Print Assumptions total_variation_scaling.
Print Assumptions total_variation_squared.
Print Assumptions per_bit_squared_error.
Print Assumptions per_bit_total_variation_squared.
Print Assumptions bias_linear_bound.
Print Assumptions parameters_bound_a_matching_pair.
Print Assumptions conditional_pairs_carry_the_same_bound.
Print Assumptions conditional_pairs_meet_the_parameter_premise.
Print Assumptions observer_joint_distance_is_the_weighted_bias.
Print Assumptions observer_joint_meets_the_per_bit_budget.
Print Assumptions hybrid_aggregation.
Print Assumptions hybrid_error_budget.
Print Assumptions parameter_output_budget.
Print Assumptions conditioner_join.
Print Assumptions conditioner_join_over_bit_strings.
Print Assumptions finite_min_entropy_fits_width.
Print Assumptions two_source_entropy_fits_width.
Print Assumptions matching_parameters_have_feasible_security.
Print Assumptions conditioner_target_bound.
Print Assumptions conditioner_target_bound_over_bit_strings.
Print Assumptions hybrid_conditioner_error_budget.
Print Assumptions accepted_source_witness.
Print Assumptions accepted_source_meets_the_budget.
Print Assumptions independence_without_an_entropy_sum_does_not_extract.
Print Assumptions conditioning_can_destroy_independence.
Print Assumptions cond_joint_marginals_keep_full_min_entropy.
Print Assumptions post_processing_keeps_distance_from_the_image_only.
Print Assumptions hybrid_sum_is_not_a_maximum.
Print Assumptions parameter_witnesses.
Print Assumptions accepted_parameters_are_realized.
Print Assumptions accepted_parameters_meet_the_finite_bound.
Print Assumptions arithmetically_admissible_parameters_can_be_unrealizable.
Print Assumptions conditioner_target_error_requires_the_image_term.
Print Assumptions constant_conditioner_target_bound_is_tight.
Print Assumptions hybrid_conditioner_budget_is_realized.
Print Assumptions observer_joint_witness.
Print Assumptions witness_premises_are_jointly_inhabited.
Print Assumptions inhabited_conditional_application.
