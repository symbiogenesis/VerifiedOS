(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   BooleanComposition.v

   Arbitrary-order GF(2) glitch-robust Boolean masking, DOM-indep and HPC1/HPC2
   nonlinear multiplication gadgets, DAG Strong-PINI composition, Keccak chi,
   and a 256-entry-verified FIPS 197 AES S-box over [ProbingModel.v](ProbingModel.v)
   (R-05-004a, R-15-053a, R-17-058a, R-17-058d).

   What this file proves:
   1. `GF(2)` (`bool`, `xorb`, `andb`) inhabiting [ProbingModel.v](ProbingModel.v)'s
      `Sharing` record (`gf2_sharing`), duplicate-free enumeration, abelian
      group and Boolean ring laws, plus a general XOR tape reindexing lemma
      for `bit_tapes`.
   2. Arbitrary-order (`n + 1` shares, order `t <= n`) glitch-robust linear
      gadgets (`masked_xor_gadget`, `masked_not_gadget`,
      `masked_const_xor_gadget`), proved functionally correct and `StrongPINI` /
      `PINI` under `ex_robust`.
   3. Arbitrary-order glitch-robust nonlinear AND gadgets with explicit register
      barriers and fresh cross-domain randomness:
      - `dom_and_gadget`: algebraic correctness, `PINI`, and `SNI` under
        `ex_robust` at arbitrary order `t <= n`;
      - `sni_refresh_gadget`: algebraic correctness, `StrongPINI`, `PINI`, and
        `SNI` under `ex_robust` at arbitrary order `t <= n`;
      - `hpc1_and_gadget` and `hpc2_and_gadget`: algebraic correctness,
        glitch-robust `PINI` and `SNI` (`hpc1_and_gadget` also `StrongPINI`)
        at arbitrary order `t <= n`.
   4. Concrete instantiation on Keccak chi (5-bit nonlinear step), proved
      functionally equal to `Keccak.chi_row` and glitch-robust `t`-PINI at
      arbitrary order `t <= n`.
   5. General straight-line `GF(2)` DAG compilation (`BoolCircuit`) preserving
      `StrongPINI` / `PINI` under `ex_robust` at arbitrary order `t <= n`,
      instantiated on a tower-field `GF(((2^2)^2)^2)` AES S-box circuit proved
      by exhaustive `vm_compute` to match `AesGcm.sub_byte` and the canonical
      256-entry FIPS 197 table on all 256 bytes.
   6. Separating negative witnesses: unmasked AND leaks, DOM AND without a
      register barrier leaks under `ex_glitch` while safe under `ex_stable`,
      and reused randomness across two AND gates breaks independence under
      `ex_stable`.

   Scope and open boundaries (R-05-163, R-05-164, R-05-165, R-05-166):
   - Masked datapath refinement to RTL (R-05-004a), combined fault-and-probing
     reductions (R-17-058d), and physical layout residuals (R-17-058a) remain
     with their respective owners.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-004a R-05-163 R-05-164 R-05-165 R-05-166 R-15-053a R-17-058a R-17-058d
   SHA256: 63e3507bd3ebabe7aa071f95df5b56632855ea2ba5a13cb03e70358c8e14d5fa
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import List Arith Lia Bool.
From Stdlib Require Permutation.
Require Import ProbingModel.
Require Keccak AesGcm.

(* =========================================================================
   1. GF(2) carrier, algebra, XOR-sum over share tuples, and tape permutations.
   ========================================================================= *)

Definition gf2_sharing : Sharing := gf2.

Lemma gf2_enum_NoDup : NoDup (v_enum gf2_sharing).
Proof.
  simpl. constructor; [intro H; destruct H as [H|[]]; discriminate H|].
  constructor; [intro H; destruct H|constructor].
Qed.

Lemma gf2_add_assoc : forall a b c : bool, xorb a (xorb b c) = xorb (xorb a b) c.
Proof. intros [] [] []; reflexivity. Qed.

Lemma gf2_add_comm : forall a b : bool, xorb a b = xorb b a.
Proof. intros [] []; reflexivity. Qed.

Lemma gf2_add_zero_l : forall a : bool, xorb false a = a.
Proof. intros []; reflexivity. Qed.

Lemma gf2_add_zero_r : forall a : bool, xorb a false = a.
Proof. intros []; reflexivity. Qed.

Lemma gf2_add_diag : forall a : bool, xorb a a = false.
Proof. intros []; reflexivity. Qed.

Lemma gf2_mul_assoc : forall a b c : bool, andb a (andb b c) = andb (andb a b) c.
Proof. intros [] [] []; reflexivity. Qed.

Lemma gf2_mul_comm : forall a b : bool, andb a b = andb b a.
Proof. intros [] []; reflexivity. Qed.

Lemma gf2_mul_one_l : forall a : bool, andb true a = a.
Proof. intros []; reflexivity. Qed.

Lemma gf2_mul_zero_l : forall a : bool, andb false a = false.
Proof. intros []; reflexivity. Qed.

Lemma gf2_and_xor_distrib_l :
  forall a b c : bool, andb a (xorb b c) = xorb (andb a b) (andb a c).
Proof. intros [] [] []; reflexivity. Qed.

Lemma gf2_and_xor_distrib_r :
  forall a b c : bool, andb (xorb a b) c = xorb (andb a c) (andb b c).
Proof. intros [] [] []; reflexivity. Qed.

Definition xor_sum (l : list bool) : bool := xor_fold l.

Lemma xor_sum_app :
  forall l1 l2 : list bool,
    xor_sum (app l1 l2) = xorb (xor_sum l1) (xor_sum l2).
Proof.
  intros l1 l2. unfold xor_sum. induction l1 as [|x r IH]; simpl.
  - reflexivity.
  - rewrite IH. apply gf2_add_assoc.
Qed.

Definition xor_sum_upto (f : nat -> bool) (m : nat) : bool :=
  xor_sum (map_over f (upto m)).

Lemma upto_succ : forall m : nat, upto (S m) = app (upto m) (cons m nil).
Proof.
  intros m. unfold upto. simpl. reflexivity.
Qed.

Lemma map_over_app_eq :
  forall {A B : Type} (f : A -> B) (l1 l2 : list A),
    map_over f (app l1 l2) = app (map_over f l1) (map_over f l2).
Proof.
  intros A B f l1 l2. induction l1 as [|x r IH]; simpl; [reflexivity | f_equal; exact IH].
Qed.

Lemma xor_sum_upto_0 : forall f, xor_sum_upto f 0 = false.
Proof. intros f. reflexivity. Qed.

Lemma xor_sum_upto_succ :
  forall (f : nat -> bool) (m : nat),
    xor_sum_upto f (S m) = xorb (xor_sum_upto f m) (f m).
Proof.
  intros f m. unfold xor_sum_upto.
  rewrite upto_succ, map_over_app_eq, xor_sum_app.
  simpl. rewrite gf2_add_zero_r. reflexivity.
Qed.

Lemma xor_sum_upto_ext :
  forall (f g : nat -> bool) (m : nat),
    (forall i, i < m -> f i = g i) ->
    xor_sum_upto f m = xor_sum_upto g m.
Proof.
  intros f g m Hext. induction m as [|m IH]; [reflexivity|].
  repeat rewrite xor_sum_upto_succ.
  rewrite IH; [rewrite Hext; [reflexivity | lia] | intros i Hi; apply Hext; lia].
Qed.

Lemma xor_sum_upto_xorb :
  forall (f g : nat -> bool) (m : nat),
    xor_sum_upto (fun i => xorb (f i) (g i)) m =
    xorb (xor_sum_upto f m) (xor_sum_upto g m).
Proof.
  intros f g m. induction m as [|m IH]; [reflexivity|].
  repeat rewrite xor_sum_upto_succ. rewrite IH.
  destruct (xor_sum_upto f m); destruct (xor_sum_upto g m);
    destruct (f m); destruct (g m); reflexivity.
Qed.

Lemma xor_sum_upto_false :
  forall m : nat, xor_sum_upto (fun _ => false) m = false.
Proof.
  intros m. induction m as [|m IH]; [reflexivity|].
  rewrite xor_sum_upto_succ, IH. reflexivity.
Qed.

Lemma xor_sum_upto_point :
  forall (m idx : nat) (v : bool),
    idx < m ->
    xor_sum_upto (fun j => if Nat.eqb j idx then v else false) m = v.
Proof.
  intros m idx v Hlt. induction m as [|m IH]; [lia|].
  rewrite xor_sum_upto_succ.
  destruct (Nat.eq_dec m idx) as [->|Hne].
  - rewrite eqb_refl_nat.
    assert (Hz : xor_sum_upto (fun j => if Nat.eqb j idx then v else false) idx = false).
    { transitivity (xor_sum_upto (fun _ => false) idx).
      - apply xor_sum_upto_ext. intros j Hj.
        assert (Eji : Nat.eqb j idx = false) by (apply Nat.eqb_neq; lia).
        rewrite Eji. reflexivity.
      - apply xor_sum_upto_false. }
    rewrite Hz. reflexivity.
  - assert (Emi : Nat.eqb m idx = false) by (apply Nat.eqb_neq; exact Hne).
    rewrite Emi, gf2_add_zero_r. apply IH. lia.
Qed.

Lemma xor_sum_upto_flip0 :
  forall (f : nat -> bool) (c : bool) (n : nat),
    xor_sum_upto (fun i => if Nat.eqb i 0 then xorb c (f 0) else f i) (S n) =
    xorb c (xor_sum_upto f (S n)).
Proof.
  intros f c n.
  assert (Heq : xor_sum_upto (fun i => if Nat.eqb i 0 then xorb c (f 0) else f i) (S n) =
                xor_sum_upto (fun i => xorb (if Nat.eqb i 0 then c else false) (f i)) (S n)).
  { apply xor_sum_upto_ext. intros [|i] Hi; simpl; [reflexivity | destruct (f (S i)); reflexivity]. }
  rewrite Heq, xor_sum_upto_xorb.
  assert (Hc : xor_sum_upto (fun i => if Nat.eqb i 0 then c else false) (S n) = c).
  { clear -c. induction n as [|k IH].
    - unfold xor_sum_upto. simpl. apply gf2_add_zero_r.
    - rewrite xor_sum_upto_succ. rewrite IH. simpl. apply gf2_add_zero_r. }
  rewrite Hc. reflexivity.
Qed.

Lemma xor_sum_upto_and_l :
  forall (c : bool) (f : nat -> bool) (m : nat),
    xor_sum_upto (fun i => andb c (f i)) m = andb c (xor_sum_upto f m).
Proof.
  intros c f m. induction m as [|m IH]; [destruct c; reflexivity|].
  repeat rewrite xor_sum_upto_succ. rewrite IH, gf2_and_xor_distrib_l. reflexivity.
Qed.

Lemma xor_sum_upto_and_r :
  forall (f : nat -> bool) (c : bool) (m : nat),
    xor_sum_upto (fun i => andb (f i) c) m = andb (xor_sum_upto f m) c.
Proof.
  intros f c m. induction m as [|m IH]; [destruct c; reflexivity|].
  repeat rewrite xor_sum_upto_succ. rewrite IH, gf2_and_xor_distrib_r. reflexivity.
Qed.

Lemma xor_sum_upto_swap :
  forall (f : nat -> nat -> bool) (m k : nat),
    xor_sum_upto (fun i => xor_sum_upto (fun j => f i j) k) m =
    xor_sum_upto (fun j => xor_sum_upto (fun i => f i j) m) k.
Proof.
  intros f m k. induction m as [|m IH].
  - rewrite xor_sum_upto_0. symmetry.
    transitivity (xor_sum_upto (fun _ => false) k).
    + apply xor_sum_upto_ext. intros j _. reflexivity.
    + apply xor_sum_upto_false.
  - rewrite xor_sum_upto_succ, IH. rewrite <- xor_sum_upto_xorb.
    apply xor_sum_upto_ext. intros j _. rewrite xor_sum_upto_succ. reflexivity.
Qed.

Lemma xor_sum_upto_antisym_zero :
  forall (r : nat -> nat -> bool) (m : nat),
    (forall i, r i i = false) ->
    (forall i j, r i j = r j i) ->
    xor_sum_upto (fun i => xor_sum_upto (fun j => r i j) m) m = false.
Proof.
  intros r m Hdiag Hsym. induction m as [|m IH]; [reflexivity|].
  rewrite xor_sum_upto_succ.
  assert (Hstep :
    xor_sum_upto (fun i => xor_sum_upto (fun j => r i j) (S m)) m =
    xorb (xor_sum_upto (fun i => xor_sum_upto (fun j => r i j) m) m)
         (xor_sum_upto (fun i => r i m) m)).
  { rewrite <- xor_sum_upto_xorb. apply xor_sum_upto_ext. intros i _.
    rewrite xor_sum_upto_succ. reflexivity. }
  rewrite Hstep, IH.
  assert (Htail : xor_sum_upto (fun j => r m j) (S m) =
                  xor_sum_upto (fun i => r i m) m).
  { rewrite xor_sum_upto_succ, Hdiag, gf2_add_zero_r.
    apply xor_sum_upto_ext. intros i _. apply Hsym. }
  rewrite Htail, gf2_add_zero_l, gf2_add_diag. reflexivity.
Qed.

(* Bit-vector XOR reindexing over `bit_tapes m`. *)
Fixpoint zip_xorb (xs ys : list bool) : list bool :=
  match xs, ys with
  | x :: xr, y :: yr => xorb x y :: zip_xorb xr yr
  | _, _ => xs
  end.

Lemma zip_xorb_involutive :
  forall xs ys, zip_xorb (zip_xorb xs ys) ys = xs.
Proof.
  induction xs as [|x xr IH]; intros [|y yr]; simpl; try reflexivity.
  rewrite IH. destruct x; destruct y; reflexivity.
Qed.

Lemma bit_at_zip_xorb :
  forall (m : nat) (df : nat -> bool) (t : list bool) (i : nat),
    ProofSupport.Member t (bitvectors m) ->
    bit_at (zip_xorb t (map_over df (upto m))) i =
    if Nat.ltb i m then xorb (bit_at t i) (df i) else false.
Proof.
  intros m df t i Ht.
  assert (Hlen : count_of t = m).
  { clear -Ht. revert t Ht. induction m as [|m IH]; intros t Ht; simpl in Ht.
    - destruct Ht as [H0|[]]; subst; reflexivity.
    - apply member_flat_map_over_inv in Ht. destruct Ht as [v [Hv [H0|[H0|[]]]]];
        subst; simpl; rewrite (IH v Hv); reflexivity. }
  assert (Hgen : forall (l delta : list bool) (off idx : nat),
    delta = map_over (fun k => df (off + k)) (upto (count_of l)) ->
    bit_at (zip_xorb l delta) idx =
    if Nat.ltb idx (count_of l) then xorb (bit_at l idx) (df (off + idx)) else false).
  { clear -df. induction l as [|x lr IH]; intros delta off idx Hd.
    - subst delta. simpl. reflexivity.
    - assert (Hu : map_over (fun k => df (off + k)) (upto (S (count_of lr))) =
                   df off :: map_over (fun k => df (S off + k)) (upto (count_of lr))).
      { clear. generalize (count_of lr) as m. intros m.
        revert off. induction m as [|k IHk]; intros off; [simpl; rewrite add_zero_r_nat; reflexivity|].
        rewrite upto_succ. repeat rewrite map_over_app_eq.
        rewrite IHk. simpl. rewrite map_over_app_eq. simpl.
        repeat f_equal. lia. }
      change (count_of (x :: lr)) with (S (count_of lr)) in Hd.
      rewrite Hu in Hd. subst delta. cbn [zip_xorb].
      change (count_of (x :: lr)) with (S (count_of lr)).
      destruct idx as [|idx].
      + unfold bit_at; simpl. rewrite add_zero_r_nat. reflexivity.
      + change (bit_at (xorb x (df off) :: zip_xorb lr (map_over (fun k => df (S off + k)) (upto (count_of lr)))) (S idx))
          with (bit_at (zip_xorb lr (map_over (fun k => df (S off + k)) (upto (count_of lr)))) idx).
        change (S idx <? S (count_of lr)) with (idx <? count_of lr).
        change (bit_at (x :: lr) (S idx)) with (bit_at lr idx).
        rewrite (IH (map_over (fun k => df (S off + k)) (upto (count_of lr))) (S off) idx eq_refl).
        replace (S off + idx) with (off + S idx) by lia. reflexivity. }
  pose proof (Hgen t (map_over (fun k => df (0 + k)) (upto (count_of t))) 0 i eq_refl) as H.
  simpl in H.
  replace (map_over (fun k => df k) (upto (count_of t)))
    with (map_over df (upto (count_of t))) in H
    by (apply map_over_ext; reflexivity).
  rewrite Hlen in H. exact H.
Qed.

Lemma perm_app_head :
  forall {A : Type} (l l1 l2 : list A),
    Perm l1 l2 -> Perm (app l l1) (app l l2).
Proof.
  intros A l l1 l2 H. induction l as [|x r IH]; simpl; [exact H | apply perm_skip; exact IH].
Qed.

Lemma perm_app_tail :
  forall {A : Type} (l1 l2 l : list A),
    Perm l1 l2 -> Perm (app l1 l) (app l2 l).
Proof.
  intros A l1 l2 l H. induction H; simpl.
  - apply perm_refl.
  - apply perm_skip; exact IHPerm.
  - apply perm_swap.
  - eapply perm_trans; [exact IHPerm1 | exact IHPerm2].
Qed.

Lemma perm_app_comm3 :
  forall {A : Type} (xs ys zs : list A),
    Perm (app xs (app ys zs)) (app ys (app xs zs)).
Proof.
  intros A xs ys zs.
  rewrite app_assoc.
  eapply perm_trans; [apply perm_app_tail; apply perm_app_comm|].
  rewrite <- app_assoc. apply perm_refl.
Qed.

Lemma perm_flat_map_over :
  forall {A B : Type} (f : A -> list B) (l1 l2 : list A),
    Perm l1 l2 ->
    Perm (flat_map_over f l1) (flat_map_over f l2).
Proof.
  intros A B f l1 l2 Hp. induction Hp; simpl.
  - apply perm_refl.
  - apply perm_app_head; exact IHHp.
  - apply perm_app_comm3.
  - eapply perm_trans; [exact IHHp1 | exact IHHp2].
Qed.

Lemma map_over_flat_map_over_local :
  forall {A B C : Type} (g : B -> C) (f : A -> list B) (l : list A),
    map_over g (flat_map_over f l) = flat_map_over (fun x => map_over g (f x)) l.
Proof.
  intros A B C g f l. induction l as [|x r IH]; simpl; [reflexivity|].
  rewrite map_over_app_eq, IH. reflexivity.
Qed.

Lemma flat_map_over_map_over_local :
  forall {A B C : Type} (f : B -> list C) (g : A -> B) (l : list A),
    flat_map_over f (map_over g l) = flat_map_over (fun x => f (g x)) l.
Proof.
  intros A B C f g l. induction l as [|x r IH]; simpl; [reflexivity|].
  rewrite IH. reflexivity.
Qed.

Lemma zip_xorb_perm_bitvectors :
  forall (m : nat) (delta : list bool),
    Perm (map_over (fun t => zip_xorb t delta) (bitvectors m)) (bitvectors m).
Proof.
  intros m. induction m as [|m IH]; intros delta; simpl.
  - destruct delta; simpl; apply perm_refl.
  - rewrite map_over_flat_map_over_local.
    destruct delta as [|d dr].
    + assert (Heq : flat_map_over (fun x => map_over (fun t => zip_xorb t nil)
                      ((false :: x) :: (true :: x) :: nil)) (bitvectors m) =
                    flat_map_over (fun v => (false :: v) :: (true :: v) :: nil) (bitvectors m)).
      { clear. induction (bitvectors m) as [|v r IHr]; [reflexivity|].
        cbn [flat_map_over app].
        change (map_over (fun t : list bool => zip_xorb t nil) ((false :: v) :: (true :: v) :: nil))
          with ((false :: v) :: (true :: v) :: nil).
        rewrite IHr. reflexivity. }
      rewrite Heq. apply perm_refl.
    + eapply perm_trans.
      2: { apply perm_flat_map_over with (f := fun v => (false :: v) :: (true :: v) :: nil).
           exact (IH dr). }
      rewrite flat_map_over_map_over_local.
      clear IH. induction (bitvectors m) as [|v r IH]; [simpl; apply perm_refl|].
      cbn [flat_map_over].
      change (map_over (fun t : list bool => zip_xorb t (d :: dr)) ((false :: v) :: (true :: v) :: nil))
        with ((xorb false d :: zip_xorb v dr) :: (xorb true d :: zip_xorb v dr) :: nil).
      cbn [app].
      destruct d; simpl.
      * eapply perm_trans; [apply perm_swap|].
        apply perm_skip; apply perm_skip; exact IH.
      * apply perm_skip; apply perm_skip; exact IH.
Qed.

Lemma bit_tapes_xor_hides :
  forall (m : nat) (O : Type) (oeqb : O -> O -> bool)
         (f g : list bool -> O) (df : nat -> bool),
    (forall t : list bool, ProofSupport.Member t (bitvectors m) ->
       g (zip_xorb t (map_over df (upto m))) = f t) ->
    SameDistribution (bit_tapes m) O oeqb f g.
Proof.
  intros m O oeqb f g df Hpt.
  apply (rerandomization_hides_on_members (bit_tapes m) O oeqb f g
           (fun t => zip_xorb t (map_over df (upto m)))).
  - intros t _. reflexivity.
  - simpl. apply zip_xorb_perm_bitvectors.
  - exact Hpt.
Qed.

(* =========================================================================
   1b. Indexed circuit builder (`circuit_of_fun`) and `StrongPINI` from
       `ShareDomainSeparated`.
   ========================================================================= *)

Definition circuit_of_fun (len : nat) (f : nat -> Gate) : Circuit :=
  map_over f (upto len).

Lemma circuit_of_fun_count :
  forall len f, wire_count (circuit_of_fun len f) = len.
Proof.
  intros len f. unfold wire_count, circuit_of_fun.
  induction len as [|len IH]; [reflexivity|].
  rewrite upto_succ, map_over_app_eq, count_of_app_eq, IH. simpl. lia.
Qed.

Lemma at_member_upto :
  forall len w, w < len -> at_member (upto len) w 0 = w.
Proof.
  induction len as [|len IH]; intros w Hw; [lia|].
  rewrite upto_succ.
  assert (Hlen : count_of (upto len) = len).
  { clear. induction len as [|l IHl]; [reflexivity|].
    rewrite upto_succ, count_of_app_eq, IHl. simpl. lia. }
  destruct (Nat.ltb w len) eqn:Elt.
  - apply Nat.ltb_lt in Elt.
    assert (Happ_l : forall {A : Type} (l1 l2 : list A) (k : nat) (d : A),
      k < count_of l1 -> at_member (app l1 l2) k d = at_member l1 k d).
    { clear. induction l1 as [|x r IH1]; intros l2 k d Hk; simpl in *; [lia|].
      destruct k; [reflexivity | apply IH1; lia]. }
    rewrite Happ_l; [apply IH; exact Elt | lia].
  - apply Nat.ltb_ge in Elt. assert (w = len) by lia. subst w.
    rewrite at_member_app_r; [rewrite Hlen, Nat.sub_diag; reflexivity | lia].
Qed.

Lemma gate_at_circuit_of_fun :
  forall len f w,
    w < len -> gate_at (circuit_of_fun len f) w = f w.
Proof.
  intros len f w Hw. unfold gate_at, circuit_of_fun.
  assert (Hmap_at : forall {A B : Type} (g : A -> B) (l : list A) (k : nat) (da : A) (db : B),
    k < count_of l -> at_member (map_over g l) k db = g (at_member l k da)).
  { clear. intros A B g l k da db Hk. revert k Hk.
    induction l as [|x r IH]; intros k Hk; simpl in *; [lia|].
    destruct k; [reflexivity | apply IH; lia]. }
  assert (Hlen : count_of (upto len) = len).
  { clear. induction len as [|l IHl]; [reflexivity|].
    rewrite upto_succ, count_of_app_eq, IHl. simpl. lia. }
  rewrite (Hmap_at nat Gate f (upto len) w 0 (g_in 0) ltac:(lia)).
  rewrite at_member_upto; [reflexivity | exact Hw].
Qed.

Lemma well_formed_circuit_of_fun :
  forall len f,
    (forall w, w < len -> gate_well_formed len w (f w) = true) ->
    well_formed (circuit_of_fun len f) = true.
Proof.
  intros len f Hgw. unfold well_formed.
  rewrite circuit_of_fun_count.
  assert (Hgen : forall k, k <= len ->
    wf_from len 0 (circuit_of_fun k f) = true).
  { induction k as [|k IH]; intros Hk; [reflexivity|].
    unfold circuit_of_fun. rewrite upto_succ, map_over_app_eq, wf_from_app.
    apply andb_true_intro; split; [apply IH; lia|].
    assert (Hlen : count_of (map_over f (upto k)) = k).
    { clear. induction k as [|k IHk]; [reflexivity|].
      rewrite upto_succ, map_over_app_eq, count_of_app_eq, IHk. simpl. lia. }
    rewrite Hlen. simpl. rewrite Hgw; [reflexivity | lia]. }
  apply Hgen; lia.
Qed.

Lemma sds_is_strong_pini :
  forall (g : Gadget) (dom : nat -> nat) (E : Expansion) (d : nat),
    well_formed (gd_circuit g) = true ->
    ShareDomainSeparated g dom ->
    LocalExpansion E ->
    StrongPINI g E d.
Proof.
  intros g dom E d Hwf Hsds Hloc ps B Hw _.
  set (doms := map_over (fun p => dom (p_wire p)) ps).
  exists (fun k => mem_nat k doms). split.
  - apply Nat.leb_le.
    pose proof (card_in_le_list g doms 0) as Hle.
    unfold card_in in Hle.
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
        unfold upto in *. induction n as [|n IH]; simpl in *; [contradiction|].
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

Lemma count_filter_any_of_eqb :
  forall {A : Type} (f : A -> option nat) (l : list A) (u : list nat),
    NoDup u ->
    count_of (filter_of (fun k => any_of (fun x => match f x with Some y => Nat.eqb y k | None => false end) l) u)
    <= count_of l.
Proof.
  intros A f l u Hnd. induction l as [|x r IH].
  - assert (Hzero : filter_of (fun k => any_of (fun x => match f x with Some y => Nat.eqb y k | None => false end) nil) u = nil).
    { clear. induction u as [|y ur IHu]; simpl; [reflexivity | exact IHu]. }
    rewrite Hzero. simpl; lia.
  - assert (Hstep :
      filter_of (fun k => any_of (fun x0 => match f x0 with Some y => Nat.eqb y k | None => false end) (x :: r)) u =
      filter_of (fun k => orb (match f x with Some y => Nat.eqb y k | None => false end)
        (any_of (fun x0 => match f x0 with Some y => Nat.eqb y k | None => false end) r)) u).
    { apply filter_of_ext. intros k. reflexivity. }
    rewrite Hstep. change (count_of (x :: r)) with (S (count_of r)).
    destruct (f x) as [y|] eqn:Efx.
    + assert (Hsplit :
        count_of (filter_of (fun k => orb (Nat.eqb y k)
          (any_of (fun x0 => match f x0 with Some y0 => Nat.eqb y0 k | None => false end) r)) u) <=
        count_of (filter_of (fun k => Nat.eqb y k) u) +
        count_of (filter_of (fun k => any_of (fun x0 => match f x0 with Some y0 => Nat.eqb y0 k | None => false end) r) u)).
      { pose proof (count_filter_or (fun k => Nat.eqb y k)
          (fun k => any_of (fun x0 => match f x0 with Some y0 => Nat.eqb y0 k | None => false end) r) u) as Hle.
        apply Nat.leb_le in Hle. exact Hle. }
      assert (Hone : count_of (filter_of (fun k => Nat.eqb y k) u) <= 1).
      { clear -Hnd. induction u as [|z ur IHu]; simpl; [lia|].
        inversion Hnd as [|? ? Hni Hnd']; subst.
        destruct (Nat.eqb y z) eqn:Eyz.
        - apply eqb_sound_nat in Eyz. subst z.
          assert (Hzero : filter_of (fun k => Nat.eqb y k) ur = nil).
          { clear -Hni. induction ur as [|w wr IHw]; simpl; [reflexivity|].
            destruct (Nat.eqb y w) eqn:Eyw.
            - apply eqb_sound_nat in Eyw. subst w. exfalso; apply Hni; left; reflexivity.
            - apply IHw; intro Hw; apply Hni; right; exact Hw. }
          rewrite Hzero; simpl; lia.
        - apply IHu; exact Hnd'. }
      lia.
    + assert (Hext :
        filter_of (fun k => false ||
          any_of (fun x0 => match f x0 with Some y => Nat.eqb y k | None => false end) r) u =
        filter_of (fun k =>
          any_of (fun x0 => match f x0 with Some y => Nat.eqb y k | None => false end) r) u).
      { apply filter_of_ext. reflexivity. }
      rewrite Hext. lia.
Qed.

Lemma upto_NoDup : forall n : nat, NoDup (upto n).
Proof.
  intros n. unfold upto.
  assert (Hmem : forall m k, ProofSupport.Member k (ProofSupport.upto m) -> k < m).
  { induction m as [|m IHm]; intros k Hk; simpl in Hk; [contradiction|].
    assert (Happ : forall l1 l2 : list nat,
      ProofSupport.Member k (app l1 l2) -> ProofSupport.Member k l1 \/ ProofSupport.Member k l2).
    { clear. induction l1 as [|x r IH]; simpl; intros l2 H;
        [right; exact H | destruct H as [->|H]; [left; left; reflexivity | destruct (IH _ H); [left; right; assumption | right; assumption]]]. }
    destruct (Happ _ _ Hk) as [H1|[->|[]]]; [specialize (IHm _ H1); lia | lia]. }
  induction n as [|n IH]; simpl; [constructor|].
  assert (Happ_nd : forall (l1 l2 : list nat),
    NoDup l1 -> NoDup l2 -> (forall x, ProofSupport.Member x l1 -> ~ ProofSupport.Member x l2) ->
    NoDup (app l1 l2)).
  { clear. intros l1 l2 H1 H2 Hdisj. induction H1 as [|x r Hnr Hr IH]; simpl; [exact H2|].
    constructor.
    - intro Hin.
      assert (Happ : forall xs ys : list nat, In x (app xs ys) -> In x xs \/ In x ys)
        by (intros xs ys; apply in_app_or).
      apply Happ in Hin. destruct Hin as [Hin|Hin]; [contradiction|].
      assert (Hmem_in : forall {A : Type} (z : A) (l : list A), In z l -> ProofSupport.Member z l).
      { clear. intros A z l. induction l as [|a lr IHa]; simpl; intros H; [contradiction | destruct H as [->|H]; [left; reflexivity | right; exact (IHa H)]]. }
      apply (Hdisj x); [left; reflexivity | apply Hmem_in; exact Hin].
    - apply IH. intros z Hz. apply Hdisj. right; exact Hz. }
  apply Happ_nd; [exact IH | constructor; [auto | constructor] |].
  intros x Hx [->|[]]. pose proof (Hmem n n Hx). lia.
Qed.

(* =========================================================================
   2. Boolean gate alphabet and arbitrary-order glitch-robust linear gadgets.
   ========================================================================= *)

Definition bool_ops (o : nat) (args : list bool) : bool :=
  match o with
  | 0 => false
  | 1 => true
  | 2 => xor_fold args
  | 3 => andb (at_member args 0 false) (at_member args 1 false)
  | 4 => negb (at_member args 0 false)
  | _ => false
  end.

(* Masked XOR over (S n) shares: primary inputs a (0..n), b (S n..2n+1),
   outputs (2*(S n)..3*(S n)-1). *)
Definition masked_xor_gate (n w : nat) : Gate :=
  let N := S n in
  if Nat.ltb w (2 * N) then g_in w
  else let k := w - 2 * N in g_op 2 (k :: N + k :: nil).

Definition masked_xor_gadget (n : nat) : Gadget :=
  let N := S n in {|
  gd_share := gf2_sharing;
  gd_prob := bit_tapes 0;
  gd_circuit := circuit_of_fun (3 * N) (masked_xor_gate n);
  gd_ops := bool_ops;
  gd_inputs := 2;
  gd_shares := N;
  gd_out := fun k => 2 * N + k;
  gd_read := 0;
  gd_assign := fun a _ _ i =>
    if Nat.ltb i N then a 0 i else a 1 (i - N);
  gd_start := fun _ _ _ => false
|}.

Lemma masked_xor_well_formed :
  forall n, gadget_well_formed (masked_xor_gadget n).
Proof.
  intros n. split; [|split].
  - unfold masked_xor_gadget; simpl gd_circuit.
    apply well_formed_circuit_of_fun. intros w Hw.
    unfold masked_xor_gate. destruct (Nat.ltb w (2 * S n)) eqn:Elt; simpl; [reflexivity|].
    apply Nat.ltb_ge in Elt.
    apply andb_true_intro; split; [apply Nat.ltb_lt; lia|].
    apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity].
  - simpl; lia.
  - intros k Hk. simpl in *. rewrite circuit_of_fun_count. lia.
Qed.

Lemma masked_xor_correct :
  forall n (a : ShareMatrix (masked_xor_gadget n)) tape,
    xor_sum_upto (fun k => gd_value (masked_xor_gadget n) a tape 0 (gd_out (masked_xor_gadget n) k)) (S n) =
    xorb (xor_sum_upto (a 0) (S n)) (xor_sum_upto (a 1) (S n)).
Proof.
  intros n a tape. rewrite <- xor_sum_upto_xorb.
  apply xor_sum_upto_ext. intros k Hk.
  unfold gd_value, value_at, masked_xor_gadget.
  cbn [gd_share gd_ops gd_circuit gd_out gd_read gd_assign gd_start].
  set (N := S n).
  pose proof (eval_fuel_irrelevant gf2_sharing bool_ops
    (circuit_of_fun (3 * N) (masked_xor_gate n))
    (regs_at gf2_sharing bool_ops (circuit_of_fun (3 * N) (masked_xor_gate n))
       (fun _ => false) (fun _ i => if Nat.ltb i N then a 0 i else a 1 (i - N)) 0)
    (fun i => if Nat.ltb i N then a 0 i else a 1 (i - N))
    (2 * N + k) (wire_count (circuit_of_fun (3 * N) (masked_xor_gate n)))
    (S (S (2 * N + k)))
    ltac:(destruct (masked_xor_well_formed n) as [Hwf _]; exact Hwf)
    ltac:(apply Nat.ltb_lt; rewrite circuit_of_fun_count; lia)
    ltac:(apply Nat.ltb_lt; rewrite circuit_of_fun_count; lia)
    ltac:(apply Nat.ltb_lt; lia)) as Hfuel.
  rewrite Hfuel. clear Hfuel.
  cbn [eval_wire].
  rewrite gate_at_circuit_of_fun; [|lia].
  unfold masked_xor_gate at 1.
  destruct (Nat.ltb (2 * N + k) (2 * S n)) eqn:E1; [apply Nat.ltb_lt in E1; lia|].
  replace (2 * N + k - 2 * S n) with k by lia.
  replace (S n + k) with (N + k) by reflexivity.
  cbn [map_over ProofSupport.map_over eval_wire bool_ops xor_fold at_member].
  rewrite (gate_at_circuit_of_fun (3 * N) (masked_xor_gate n) k ltac:(lia)).
  rewrite (gate_at_circuit_of_fun (3 * N) (masked_xor_gate n) (N + k) ltac:(lia)).
  unfold masked_xor_gate.
  destruct (Nat.ltb k (2 * S n)) eqn:Ek; [|apply Nat.ltb_ge in Ek; lia].
  destruct (Nat.ltb (N + k) (2 * S n)) eqn:Enk; [|apply Nat.ltb_ge in Enk; lia].
  destruct (Nat.ltb k N) eqn:EkN; [|apply Nat.ltb_ge in EkN; lia].
  destruct (Nat.ltb (N + k) N) eqn:EnkN; [apply Nat.ltb_lt in EnkN; lia|].
  replace (N + k - N) with k by lia.
  rewrite gf2_add_zero_r. reflexivity.
Qed.

Lemma masked_xor_sds :
  forall n, ShareDomainSeparated (masked_xor_gadget n) (fun w => Nat.modulo w (S n)).
Proof.
  intros n. constructor;
    unfold masked_xor_gadget;
    cbn [gd_circuit gd_shares gd_out gd_inputs gd_assign gd_start].
  - intros w Hw. apply Nat.mod_upper_bound. discriminate.
  - intros k Hk. replace (2 * S n + k) with (k + 2 * S n) by lia.
    rewrite Nat.Div0.mod_add. apply Nat.mod_small; exact Hk.
  - intros k Hk. rewrite circuit_of_fun_count. lia.
  - intros w i a b tape t Hw Eg Hag.
    rewrite circuit_of_fun_count in Hw.
    rewrite gate_at_circuit_of_fun in Eg; [|exact Hw].
    unfold masked_xor_gate in Eg.
    destruct (Nat.ltb w (2 * S n)) eqn:Elt; [|discriminate Eg].
    inversion Eg; subst i. apply Nat.ltb_lt in Elt.
    destruct (Nat.ltb w (S n)) eqn:EwN.
    + apply Nat.ltb_lt in EwN. rewrite Nat.mod_small in Hag; [|exact EwN].
      apply Hag; lia.
    + apply Nat.ltb_ge in EwN.
      assert (Hmod : (w - S n) mod S n = w mod S n).
      { replace w with ((w - S n) + 1 * S n) at 2 by lia.
        rewrite Nat.Div0.mod_add; reflexivity. }
      rewrite Nat.mod_small in Hmod; [|lia].
      rewrite <- Hmod in Hag. apply Hag; lia.
  - intros; reflexivity.
  - intros w Hw. rewrite circuit_of_fun_count in Hw.
    rewrite gate_at_circuit_of_fun; [|exact Hw].
    unfold masked_xor_gate.
    destruct (Nat.ltb w (2 * S n)) eqn:Elt; [exact I|].
    apply Nat.ltb_ge in Elt. cbn [all_of ProofSupport.all_of].
    assert (Hk_bound : w - 2 * S n < S n) by lia.
    assert (Hmodw : (w - 2 * S n) mod S n = w mod S n).
    { replace w with ((w - 2 * S n) + 2 * S n) at 2 by lia.
      rewrite Nat.Div0.mod_add; reflexivity. }
    assert (Hmod1 : (w - 2 * S n) = (w - 2 * S n) mod S n)
      by (rewrite Nat.mod_small; [reflexivity | exact Hk_bound]).
    assert (Hmod2 : (S n + (w - 2 * S n)) mod S n = w mod S n).
    { replace (S n + (w - 2 * S n)) with ((w - 2 * S n) + 1 * S n) by lia.
      rewrite Nat.Div0.mod_add. exact Hmodw. }
    rewrite Hmod2, Hmodw.
    repeat rewrite eqb_refl_nat. reflexivity.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_xor_is_strong_pini :
  forall n E d, LocalExpansion E -> StrongPINI (masked_xor_gadget n) E d.
Proof.
  intros n E d Hloc.
  destruct (masked_xor_well_formed n) as [Hwf _].
  exact (sds_is_strong_pini (masked_xor_gadget n) (fun w => Nat.modulo w (S n)) E d Hwf (masked_xor_sds n) Hloc).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_xor_is_pini :
  forall n E d, LocalExpansion E -> PINI (masked_xor_gadget n) E d.
Proof.
  intros n E d Hloc. apply strong_pini_implies_pini. apply masked_xor_is_strong_pini; exact Hloc.
Qed.

(* Masked constant XOR and masked NOT over (S n) shares. *)
Definition masked_const_xor_gate (n : nat) (c : bool) (w : nat) : Gate :=
  let N := S n in
  if Nat.ltb w N then g_in w
  else if Nat.eqb w N then g_op (if c then 1 else 0) nil
  else g_op 2 (0 :: N :: nil).

Definition masked_const_xor_gadget (n : nat) (c : bool) : Gadget :=
  let N := S n in {|
  gd_share := gf2_sharing;
  gd_prob := bit_tapes 0;
  gd_circuit := circuit_of_fun (N + 2) (masked_const_xor_gate n c);
  gd_ops := bool_ops;
  gd_inputs := 1;
  gd_shares := N;
  gd_out := fun k => match k with 0 => S N | S _ => k end;
  gd_read := 0;
  gd_assign := fun a _ _ i => a 0 i;
  gd_start := fun _ _ _ => false
|}.

Lemma masked_const_xor_well_formed :
  forall n c, gadget_well_formed (masked_const_xor_gadget n c).
Proof.
  intros n c. split; [|split].
  - simpl. apply well_formed_circuit_of_fun. intros w Hw.
    unfold masked_const_xor_gate.
    destruct (Nat.ltb w (S n)) eqn:E1; [reflexivity|].
    destruct (Nat.eqb w (S n)) eqn:E2; [reflexivity|].
    apply Nat.ltb_ge in E1. apply Nat.eqb_neq in E2.
    assert (w = S (S n)) by lia. subst w.
    simpl. apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity].
  - simpl; lia.
  - intros [|k] Hk; simpl in *; rewrite circuit_of_fun_count; lia.
Qed.

Lemma masked_const_xor_correct :
  forall n c (a : ShareMatrix (masked_const_xor_gadget n c)) tape,
    xor_sum_upto (fun k => gd_value (masked_const_xor_gadget n c) a tape 0
      (gd_out (masked_const_xor_gadget n c) k)) (S n) =
    xorb c (xor_sum_upto (a 0) (S n)).
Proof.
  intros n c a tape.
  rewrite <- xor_sum_upto_flip0.
  apply xor_sum_upto_ext. intros [|k] Hk.
  - unfold gd_value, value_at, masked_const_xor_gadget.
    cbn [gd_share gd_ops gd_circuit gd_out gd_read gd_assign gd_start].
    set (N := S n).
    pose proof (eval_fuel_irrelevant gf2_sharing bool_ops
      (circuit_of_fun (N + 2) (masked_const_xor_gate n c))
      (regs_at gf2_sharing bool_ops (circuit_of_fun (N + 2) (masked_const_xor_gate n c))
         (fun _ => false) (fun _ i => a 0 i) 0)
      (fun i => a 0 i)
      (S N) (wire_count (circuit_of_fun (N + 2) (masked_const_xor_gate n c)))
      (S (S (S N)))
      ltac:(destruct (masked_const_xor_well_formed n c) as [Hwf _]; exact Hwf)
      ltac:(apply Nat.ltb_lt; rewrite circuit_of_fun_count; lia)
      ltac:(apply Nat.ltb_lt; rewrite circuit_of_fun_count; lia)
      ltac:(apply Nat.ltb_lt; lia)) as Hfuel.
    rewrite Hfuel. clear Hfuel.
    cbn [eval_wire].
    rewrite gate_at_circuit_of_fun; [|lia].
    unfold masked_const_xor_gate at 1.
    destruct (Nat.ltb (S N) (S n)) eqn:E1; [apply Nat.ltb_lt in E1; lia|].
    destruct (Nat.eqb (S N) (S n)) eqn:E2; [apply eqb_sound_nat in E2; lia|].
    cbn [map_over ProofSupport.map_over eval_wire bool_ops xor_fold at_member].
    rewrite (gate_at_circuit_of_fun (N + 2) (masked_const_xor_gate n c) 0 ltac:(lia)).
    rewrite (gate_at_circuit_of_fun (N + 2) (masked_const_xor_gate n c) (S n) ltac:(lia)).
    unfold masked_const_xor_gate.
    destruct (Nat.ltb 0 (S n)) eqn:E0; [|apply Nat.ltb_ge in E0; lia].
    destruct (Nat.ltb (S n) (S n)) eqn:ENN; [apply Nat.ltb_lt in ENN; lia|].
    rewrite eqb_refl_nat. simpl.
    destruct c; destruct (a 0 0); reflexivity.
  - unfold gd_value, value_at, masked_const_xor_gadget.
    cbn [gd_share gd_ops gd_circuit gd_out gd_read gd_assign gd_start].
    set (N := S n).
    pose proof (eval_fuel_irrelevant gf2_sharing bool_ops
      (circuit_of_fun (N + 2) (masked_const_xor_gate n c))
      (regs_at gf2_sharing bool_ops (circuit_of_fun (N + 2) (masked_const_xor_gate n c))
         (fun _ => false) (fun _ i => a 0 i) 0)
      (fun i => a 0 i)
      (S k) (wire_count (circuit_of_fun (N + 2) (masked_const_xor_gate n c)))
      (S (S k))
      ltac:(destruct (masked_const_xor_well_formed n c) as [Hwf _]; exact Hwf)
      ltac:(apply Nat.ltb_lt; rewrite circuit_of_fun_count; lia)
      ltac:(apply Nat.ltb_lt; rewrite circuit_of_fun_count; lia)
      ltac:(apply Nat.ltb_lt; lia)) as Hfuel.
    rewrite Hfuel. clear Hfuel.
    cbn [eval_wire].
    rewrite gate_at_circuit_of_fun; [|lia].
    unfold masked_const_xor_gate.
    destruct (Nat.ltb (S k) (S n)) eqn:Ek; [reflexivity | apply Nat.ltb_ge in Ek; lia].
Qed.

Definition const_xor_dom (n w : nat) : nat :=
  if Nat.ltb w (S n) then w else 0.

Lemma masked_const_xor_sds :
  forall n c, ShareDomainSeparated (masked_const_xor_gadget n c) (const_xor_dom n).
Proof.
  intros n c. constructor;
    unfold masked_const_xor_gadget;
    cbn [gd_circuit gd_shares gd_out gd_inputs gd_assign gd_start].
  - intros w Hw. unfold const_xor_dom. destruct (Nat.ltb w (S n)) eqn:Elt; [apply Nat.ltb_lt; exact Elt | lia].
  - intros [|k] Hk; unfold const_xor_dom; simpl.
    + destruct (Nat.ltb (S (S n)) (S n)) eqn:Elt; [apply Nat.ltb_lt in Elt; lia | reflexivity].
    + destruct (Nat.ltb (S k) (S n)) eqn:Elt; [reflexivity | apply Nat.ltb_ge in Elt; lia].
  - intros [|k] Hk; rewrite circuit_of_fun_count; lia.
  - intros w i a b tape t Hw Eg Hag.
    rewrite circuit_of_fun_count in Hw.
    rewrite gate_at_circuit_of_fun in Eg; [|exact Hw].
    unfold masked_const_xor_gate in Eg.
    destruct (Nat.ltb w (S n)) eqn:Elt.
    + inversion Eg; subst i. unfold const_xor_dom in Hag. rewrite Elt in Hag. apply Hag; lia.
    + destruct (Nat.eqb w (S n)); discriminate Eg.
  - intros; reflexivity.
  - intros w Hw. rewrite circuit_of_fun_count in Hw.
    rewrite gate_at_circuit_of_fun; [|exact Hw].
    unfold masked_const_xor_gate.
    destruct (Nat.ltb w (S n)) eqn:E1; [exact I|].
    destruct (Nat.eqb w (S n)) eqn:E2; [simpl; reflexivity|].
    simpl. unfold const_xor_dom.
    destruct (Nat.ltb 0 (S n)) eqn:E0; [|apply Nat.ltb_ge in E0; lia].
    destruct (Nat.ltb (S n) (S n)) eqn:ESn; [apply Nat.ltb_lt in ESn; lia|].
    rewrite E1. reflexivity.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_const_xor_is_strong_pini :
  forall n c E d, LocalExpansion E -> StrongPINI (masked_const_xor_gadget n c) E d.
Proof.
  intros n c E d Hloc.
  destruct (masked_const_xor_well_formed n c) as [Hwf _].
  exact (sds_is_strong_pini (masked_const_xor_gadget n c) (const_xor_dom n) E d Hwf (masked_const_xor_sds n c) Hloc).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_const_xor_is_pini :
  forall n c E d, LocalExpansion E -> PINI (masked_const_xor_gadget n c) E d.
Proof.
  intros n c E d Hloc. apply strong_pini_implies_pini. apply masked_const_xor_is_strong_pini; exact Hloc.
Qed.

(* Masked NOT gadget using `g_op 4` on share 0. *)
Definition masked_not_gate (n w : nat) : Gate :=
  let N := S n in
  if Nat.ltb w N then g_in w else g_op 4 (0 :: nil).

Definition masked_not_gadget (n : nat) : Gadget :=
  let N := S n in {|
  gd_share := gf2_sharing;
  gd_prob := bit_tapes 0;
  gd_circuit := circuit_of_fun (S N) (masked_not_gate n);
  gd_ops := bool_ops;
  gd_inputs := 1;
  gd_shares := N;
  gd_out := fun k => match k with 0 => N | S _ => k end;
  gd_read := 0;
  gd_assign := fun a _ _ i => a 0 i;
  gd_start := fun _ _ _ => false
|}.

Lemma masked_not_well_formed :
  forall n, gadget_well_formed (masked_not_gadget n).
Proof.
  intros n. split; [|split].
  - simpl. apply well_formed_circuit_of_fun. intros w Hw.
    unfold masked_not_gate. destruct (Nat.ltb w (S n)) eqn:E1; [reflexivity|].
    apply Nat.ltb_ge in E1. assert (w = S n) by lia. subst w.
    simpl. reflexivity.
  - simpl; lia.
  - intros [|k] Hk; simpl in *; rewrite circuit_of_fun_count; lia.
Qed.

Lemma masked_not_correct :
  forall n (a : ShareMatrix (masked_not_gadget n)) tape,
    xor_sum_upto (fun k => gd_value (masked_not_gadget n) a tape 0
      (gd_out (masked_not_gadget n) k)) (S n) =
    negb (xor_sum_upto (a 0) (S n)).
Proof.
  intros n a tape.
  assert (Hneg : negb (xor_sum_upto (a 0) (S n)) = xorb true (xor_sum_upto (a 0) (S n)))
    by (destruct (xor_sum_upto (a 0) (S n)); reflexivity).
  rewrite Hneg, <- xor_sum_upto_flip0.
  apply xor_sum_upto_ext. intros [|k] Hk.
  - unfold gd_value, value_at, masked_not_gadget.
    cbn [gd_share gd_ops gd_circuit gd_out gd_read gd_assign gd_start].
    set (N := S n).
    pose proof (eval_fuel_irrelevant gf2_sharing bool_ops
      (circuit_of_fun (S N) (masked_not_gate n))
      (regs_at gf2_sharing bool_ops (circuit_of_fun (S N) (masked_not_gate n))
         (fun _ => false) (fun _ i => a 0 i) 0)
      (fun i => a 0 i)
      N (wire_count (circuit_of_fun (S N) (masked_not_gate n)))
      (S (S N))
      ltac:(destruct (masked_not_well_formed n) as [Hwf _]; exact Hwf)
      ltac:(apply Nat.ltb_lt; rewrite circuit_of_fun_count; lia)
      ltac:(apply Nat.ltb_lt; rewrite circuit_of_fun_count; lia)
      ltac:(apply Nat.ltb_lt; lia)) as Hfuel.
    rewrite Hfuel. clear Hfuel.
    cbn [eval_wire].
    rewrite gate_at_circuit_of_fun; [|lia].
    unfold masked_not_gate at 1.
    destruct (Nat.ltb N (S n)) eqn:ENN; [apply Nat.ltb_lt in ENN; lia|].
    cbn [map_over ProofSupport.map_over eval_wire bool_ops xor_fold at_member].
    rewrite (gate_at_circuit_of_fun (S N) (masked_not_gate n) 0 ltac:(lia)).
    unfold masked_not_gate.
    destruct (Nat.ltb 0 (S n)) eqn:E0; [|apply Nat.ltb_ge in E0; lia].
    simpl. destruct (a 0 0); reflexivity.
  - unfold gd_value, value_at, masked_not_gadget.
    cbn [gd_share gd_ops gd_circuit gd_out gd_read gd_assign gd_start].
    set (N := S n).
    pose proof (eval_fuel_irrelevant gf2_sharing bool_ops
      (circuit_of_fun (S N) (masked_not_gate n))
      (regs_at gf2_sharing bool_ops (circuit_of_fun (S N) (masked_not_gate n))
         (fun _ => false) (fun _ i => a 0 i) 0)
      (fun i => a 0 i)
      (S k) (wire_count (circuit_of_fun (S N) (masked_not_gate n)))
      (S (S k))
      ltac:(destruct (masked_not_well_formed n) as [Hwf _]; exact Hwf)
      ltac:(apply Nat.ltb_lt; rewrite circuit_of_fun_count; lia)
      ltac:(apply Nat.ltb_lt; rewrite circuit_of_fun_count; lia)
      ltac:(apply Nat.ltb_lt; lia)) as Hfuel.
    rewrite Hfuel. clear Hfuel.
    cbn [eval_wire].
    rewrite gate_at_circuit_of_fun; [|lia].
    unfold masked_not_gate.
    destruct (Nat.ltb (S k) (S n)) eqn:Ek; [reflexivity | apply Nat.ltb_ge in Ek; lia].
Qed.

Lemma masked_not_sds :
  forall n, ShareDomainSeparated (masked_not_gadget n) (const_xor_dom n).
Proof.
  intros n. constructor;
    unfold masked_not_gadget;
    cbn [gd_circuit gd_shares gd_out gd_inputs gd_assign gd_start].
  - intros w Hw. unfold const_xor_dom. destruct (Nat.ltb w (S n)) eqn:Elt; [apply Nat.ltb_lt; exact Elt | lia].
  - intros [|k] Hk; unfold const_xor_dom; simpl.
    + destruct (Nat.ltb (S n) (S n)) eqn:Elt; [apply Nat.ltb_lt in Elt; lia | reflexivity].
    + destruct (Nat.ltb (S k) (S n)) eqn:Elt; [reflexivity | apply Nat.ltb_ge in Elt; lia].
  - intros [|k] Hk; rewrite circuit_of_fun_count; lia.
  - intros w i a b tape t Hw Eg Hag.
    rewrite circuit_of_fun_count in Hw.
    rewrite gate_at_circuit_of_fun in Eg; [|exact Hw].
    unfold masked_not_gate in Eg.
    destruct (Nat.ltb w (S n)) eqn:Elt; [|discriminate Eg].
    inversion Eg; subst i. unfold const_xor_dom in Hag. rewrite Elt in Hag. apply Hag; lia.
  - intros; reflexivity.
  - intros w Hw. rewrite circuit_of_fun_count in Hw.
    rewrite gate_at_circuit_of_fun; [|exact Hw].
    unfold masked_not_gate.
    destruct (Nat.ltb w (S n)) eqn:Elt; [exact I|].
    simpl. unfold const_xor_dom.
    destruct (Nat.ltb 0 (S n)) eqn:E0; [|apply Nat.ltb_ge in E0; lia].
    rewrite Elt. reflexivity.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_not_is_strong_pini :
  forall n E d, LocalExpansion E -> StrongPINI (masked_not_gadget n) E d.
Proof.
  intros n E d Hloc.
  destruct (masked_not_well_formed n) as [Hwf _].
  exact (sds_is_strong_pini (masked_not_gadget n) (const_xor_dom n) E d Hwf (masked_not_sds n) Hloc).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_not_is_pini :
  forall n E d, LocalExpansion E -> PINI (masked_not_gadget n) E d.
Proof.
  intros n E d Hloc. apply strong_pini_implies_pini. apply masked_not_is_strong_pini; exact Hloc.
Qed.

(* =========================================================================
   3a. Uniform `eval_wire` / `regs_at` / `stable_sources` unfolding helpers,
       Pigeonhole unblocked-index finder, and arbitrary-order DOM-indep AND.
   ========================================================================= *)

Lemma eval_wire_unfold :
  forall m ops c regs ins w,
    well_formed c = true -> w < wire_count c ->
    eval_wire m ops c regs ins (wire_count c) w =
    match gate_at c w with
    | g_in i => ins i
    | g_reg _ => regs w
    | g_op o args => ops o (map_over (eval_wire m ops c regs ins (wire_count c)) args)
    end.
Proof.
  intros m ops c regs ins w Hwf Hw.
  rewrite (eval_fuel_irrelevant m ops c regs ins w (wire_count c) (S w)
             Hwf ltac:(apply Nat.ltb_lt; exact Hw)
             ltac:(apply Nat.ltb_lt; exact Hw) ltac:(apply Nat.ltb_lt; lia)).
  cbn [eval_wire]. destruct (gate_at c w) as [i|s|o args] eqn:Eg; [reflexivity | reflexivity|].
  f_equal. apply support_map_ext. intros a Ha.
  pose proof (well_formed_gate_reads_earlier_wires c w o args Hwf ltac:(apply Nat.ltb_lt; exact Hw) Eg) as Hargs.
  assert (Ha_lt : a < w).
  { clear -Hargs Ha. induction args as [|x r IH]; simpl in *; [contradiction|].
    apply andb_prop in Hargs. destruct Hargs as [Hx Hr].
    destruct Ha as [<-|Ha]; [apply Nat.ltb_lt; exact Hx | exact (IH Ha Hr)]. }
  apply eval_fuel_irrelevant; [exact Hwf | apply Nat.ltb_lt; lia | apply Nat.ltb_lt; exact Ha_lt | apply Nat.ltb_lt; lia].
Qed.

Lemma value_at_unfold :
  forall m ops c start ins cyc w,
    well_formed c = true -> w < wire_count c ->
    value_at m ops c start ins cyc w =
    match gate_at c w with
    | g_in i => ins cyc i
    | g_reg _ => regs_at m ops c start ins cyc w
    | g_op o args => ops o (map_over (value_at m ops c start ins cyc) args)
    end.
Proof.
  intros m ops c start ins cyc w Hwf Hw. unfold value_at.
  apply eval_wire_unfold; [exact Hwf | exact Hw].
Qed.

Lemma regs_at_succ_step :
  forall m ops c start ins t w,
    regs_at m ops c start ins (S t) w =
    match gate_at c w with
    | g_reg src => value_at m ops c start ins t src
    | _ => regs_at m ops c start ins t w
    end.
Proof.
  intros m ops c start ins t w. simpl. reflexivity.
Qed.

Lemma stable_sources_fuel_irrelevant_local :
  forall c f1 f2 w,
    well_formed c = true ->
    w < wire_count c ->
    w < f1 -> w < f2 ->
    stable_sources c f1 w = stable_sources c f2 w.
Proof.
  intros c f1 f2 w Hwf Hw H1 H2.
  exact (stable_sources_fuel_irrelevant (S w) c w f1 f2 Hwf Hw ltac:(lia) H1 H2).
Qed.

Lemma stable_sources_unfold :
  forall c w,
    well_formed c = true -> w < wire_count c ->
    stable_sources c (wire_count c) w =
    match gate_at c w with
    | g_in _ => w :: nil
    | g_reg _ => w :: nil
    | g_op _ args => flat_map_over (stable_sources c (wire_count c)) args
    end.
Proof.
  intros c w Hwf Hw.
  rewrite (stable_sources_fuel_irrelevant_local c (wire_count c) (S w) w Hwf Hw Hw ltac:(lia)).
  cbn [stable_sources]. destruct (gate_at c w) as [i|s|o args] eqn:Eg; [reflexivity | reflexivity|].
  assert (Hargs : all_of (fun a => Nat.ltb a w) args = true)
    by exact (well_formed_gate_reads_earlier_wires c w o args Hwf ltac:(apply Nat.ltb_lt; exact Hw) Eg).
  clear -Hwf Hw Hargs. induction args as [|a r IH]; simpl; [reflexivity|].
  apply andb_prop in Hargs. destruct Hargs as [Ha Hr].
  apply Nat.ltb_lt in Ha.
  rewrite (stable_sources_fuel_irrelevant_local c w (wire_count c) a Hwf ltac:(lia) Ha ltac:(lia)).
  f_equal. exact (IH Hr).
Qed.

Lemma count_upto : forall m, count_of (upto m) = m.
Proof.
  induction m as [|m IH]; [reflexivity|].
  rewrite upto_succ, count_of_app_eq, IH. simpl. lia.
Qed.

Lemma member_upto_lt : forall m k, ProofSupport.Member k (upto m) -> k < m.
Proof.
  induction m as [|m IH]; intros k Hk; [simpl in Hk; contradiction|].
  rewrite upto_succ in Hk.
  assert (Happ : forall l1 l2 : list nat, ProofSupport.Member k (app l1 l2) ->
    ProofSupport.Member k l1 \/ ProofSupport.Member k l2).
  { clear. induction l1 as [|x r IH1]; simpl; intros l2 H;
      [right; exact H | destruct H as [->|H]; [left; left; reflexivity | destruct (IH1 _ H); [left; right; assumption | right; assumption]]]. }
  destruct (Happ _ _ Hk) as [H1|[->|[]]]; [specialize (IH _ H1); lia | lia].
Qed.

Lemma lt_member_upto : forall m k, k < m -> ProofSupport.Member k (upto m).
Proof.
  induction m as [|m IH]; intros k Hk; [lia|].
  rewrite upto_succ.
  assert (Happ : forall l1 l2 : list nat,
    ProofSupport.Member k l1 \/ ProofSupport.Member k l2 -> ProofSupport.Member k (app l1 l2)).
  { clear. induction l1 as [|x r IH1]; intros l2 [H|H]; simpl in *;
      [contradiction | exact H | destruct H as [->|H]; [left; reflexivity | right; apply IH1; left; exact H] | right; apply IH1; right; exact H]. }
  apply Happ. destruct (Nat.eq_dec k m) as [->|Hne]; [right; left; reflexivity | left; apply IH; lia].
Qed.

Lemma count_filter_split :
  forall {A : Type} (p : A -> bool) (l : list A),
    count_of (filter_of p l) + count_of (filter_of (fun x => negb (p x)) l) = count_of l.
Proof.
  intros A p l. induction l as [|x r IH]; simpl; [reflexivity|].
  destruct (p x); simpl; lia.
Qed.

Lemma count_filter_orb :
  forall {A : Type} (p q : A -> bool) (l : list A),
    count_of (filter_of (fun x => orb (p x) (q x)) l) <=
    count_of (filter_of p l) + count_of (filter_of q l).
Proof.
  intros A p q l. induction l as [|x r IH]; simpl; [lia|].
  destruct (p x); destruct (q x); simpl; lia.
Qed.

Definition find_unblocked (N : nat) (blk : nat -> bool) : nat :=
  at_member (filter_of (fun j => negb (blk j)) (upto N)) 0 0.

Lemma find_unblocked_spec :
  forall (N : nat) (blk : nat -> bool),
    count_of (filter_of blk (upto N)) < N ->
    let j := find_unblocked N blk in j < N /\ blk j = false.
Proof.
  intros N blk Hlt. simpl. unfold find_unblocked.
  pose proof (count_filter_split blk (upto N)) as Hsum.
  rewrite count_upto in Hsum.
  destruct (filter_of (fun x => negb (blk x)) (upto N)) as [|x r] eqn:Efilt; [simpl in Hsum; lia|].
  simpl.
  assert (Hmem : ProofSupport.Member x (filter_of (fun x0 => negb (blk x0)) (upto N)))
    by (rewrite Efilt; left; reflexivity).
  pose proof (support_filter_true (fun x0 => negb (blk x0)) (upto N) x Hmem) as Hneg.
  cbv beta in Hneg.
  apply support_filter_member in Hmem.
  split; [apply member_upto_lt; exact Hmem |
    destruct (blk x) eqn:Ebx; simpl in *; [discriminate Hneg | reflexivity]].
Qed.

Lemma count_filter_remove_elem :
  forall (p : nat -> bool) (k : nat) (l : list nat),
    ProofSupport.Member k l -> p k = true ->
    count_of (filter_of (fun j => andb (negb (Nat.eqb j k)) (p j)) l) <
    count_of (filter_of p l).
Proof.
  intros p k l Hmem Hpk. induction l as [|x r IH]; simpl in *; [contradiction|].
  destruct Hmem as [Heq|Hx].
  - subst x. rewrite eqb_refl_nat, Hpk. simpl.
    assert (Hle : forall l0, count_of (filter_of (fun j => andb (negb (Nat.eqb j k)) (p j)) l0) <= count_of (filter_of p l0)).
    { clear -p k. intros l0. induction l0 as [|y yr IHy]; simpl; [lia|].
      destruct (Nat.eqb y k); destruct (p y); simpl; lia. }
    specialize (Hle r). lia.
  - specialize (IH Hx). destruct (Nat.eqb x k); destruct (p x); simpl; lia.
Qed.

(* Pairwise randomness helpers over `bit_tapes (N * N)`. *)
Definition dom_pair_idx (N i j : nat) : nat :=
  if Nat.ltb i j then i * N + j else j * N + i.

Definition dom_rbit (N : nat) (tape : list bool) (i j : nat) : bool :=
  if Nat.eqb i j then false else bit_at tape (dom_pair_idx N i j).

Lemma dom_rbit_diag : forall N tape i, dom_rbit N tape i i = false.
Proof. intros N tape i. unfold dom_rbit. rewrite eqb_refl_nat. reflexivity. Qed.

Lemma dom_rbit_sym : forall N tape i j, dom_rbit N tape i j = dom_rbit N tape j i.
Proof.
  intros N tape i j. unfold dom_rbit, dom_pair_idx.
  destruct (Nat.eqb i j) eqn:Eij.
  - apply eqb_sound_nat in Eij. subst j. rewrite eqb_refl_nat. reflexivity.
  - apply Nat.eqb_neq in Eij.
    assert (Eji : Nat.eqb j i = false) by (apply Nat.eqb_neq; lia).
    rewrite Eji.
    destruct (Nat.ltb i j) eqn:L1; destruct (Nat.ltb j i) eqn:L2;
      try reflexivity;
      [apply Nat.ltb_lt in L1; apply Nat.ltb_lt in L2; lia |
       apply Nat.ltb_ge in L1; apply Nat.ltb_ge in L2; lia].
Qed.

Lemma dom_pair_idx_lt :
  forall N i j, i < N -> j < N -> dom_pair_idx N i j < N * N.
Proof.
  intros N i j Hi Hj. unfold dom_pair_idx.
  destruct (Nat.ltb i j) eqn:L.
  - apply Nat.ltb_lt in L. nia.
  - nia.
Qed.

Lemma div_mod_pair_id :
  forall N u v, u < N -> v < N ->
    (u * N + v) / N = u /\ (u * N + v) mod N = v.
Proof.
  intros N u v Hu Hv.
  assert (HN : N <> 0) by lia.
  rewrite (Nat.add_comm (u * N) v).
  split; [rewrite Nat.div_add; [rewrite Nat.div_small; lia | exact HN]
       | rewrite Nat.Div0.mod_add; [rewrite Nat.mod_small; lia]].
Qed.

Lemma div_mod_pair_bound :
  forall N p, 0 < N -> p < N * N ->
    p / N < N /\ p mod N < N /\ (p / N) * N + (p mod N) = p.
Proof.
  intros N p HN Hp. split; [|split].
  - apply Nat.Div0.div_lt_upper_bound. lia.
  - apply Nat.mod_upper_bound; lia.
  - pose proof (Nat.div_mod p N ltac:(lia)) as Hdm. lia.
Qed.

(* DOM-indep AND gate-level circuit over (S n) shares. *)
Definition dom_wire_count (n : nat) : nat :=
  let N := S n in 3 * N + 4 * N * N.

Definition dom_out_wire (n i : nat) : nat :=
  let N := S n in 2 * N + 4 * N * N + i.

Definition dom_gate (n w : nat) : Gate :=
  let N := S n in
  if Nat.ltb w (2 * N + N * N) then g_in w
  else if Nat.ltb w (2 * N + 2 * N * N) then
    let p := w - (2 * N + N * N) in
    let i := p / N in let j := p mod N in
    g_op 3 (i :: N + j :: nil)
  else if Nat.ltb w (2 * N + 3 * N * N) then
    let p := w - (2 * N + 2 * N * N) in
    let i := p / N in let j := p mod N in
    let w_mul := 2 * N + N * N + p in
    if Nat.eqb i j then g_op 2 (w_mul :: nil)
    else g_op 2 (w_mul :: (2 * N + dom_pair_idx N i j) :: nil)
  else if Nat.ltb w (2 * N + 4 * N * N) then
    let p := w - (2 * N + 3 * N * N) in
    g_reg (2 * N + 2 * N * N + p)
  else
    let i := w - (2 * N + 4 * N * N) in
    g_op 2 (map_over (fun j => 2 * N + 3 * N * N + i * N + j) (upto N)).

Definition dom_and_gadget (n : nat) : Gadget :=
  let N := S n in {|
  gd_share := gf2_sharing;
  gd_prob := bit_tapes (N * N);
  gd_circuit := circuit_of_fun (dom_wire_count n) (dom_gate n);
  gd_ops := bool_ops;
  gd_inputs := 2;
  gd_shares := N;
  gd_out := dom_out_wire n;
  gd_read := 1;
  gd_assign := fun a tape _ i =>
    if Nat.ltb i N then a 0 i
    else if Nat.ltb i (2 * N) then a 1 (i - N)
    else bit_at tape (i - 2 * N);
  gd_start := fun _ _ _ => false
|}.

Lemma dom_and_well_formed :
  forall n, gadget_well_formed (dom_and_gadget n).
Proof.
  intros n. split; [|split].
  - unfold dom_and_gadget; cbn [gd_circuit].
    apply well_formed_circuit_of_fun. intros w Hw.
    unfold dom_wire_count in Hw. set (N := S n) in *.
    unfold dom_gate. change (S n) with N.
    destruct (Nat.ltb w (2 * N + N * N)) eqn:E1; [reflexivity|].
    apply Nat.ltb_ge in E1.
    destruct (Nat.ltb w (2 * N + 2 * N * N)) eqn:E2.
    + apply Nat.ltb_lt in E2.
      destruct (div_mod_pair_bound N (w - (2 * N + N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
      cbn [gate_well_formed all_of ProofSupport.all_of].
      apply andb_true_intro; split; [apply Nat.ltb_lt; lia |].
      apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity].
    + apply Nat.ltb_ge in E2.
      destruct (Nat.ltb w (2 * N + 3 * N * N)) eqn:E3.
      * apply Nat.ltb_lt in E3.
        destruct (div_mod_pair_bound N (w - (2 * N + 2 * N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
        destruct (Nat.eqb ((w - (2 * N + 2 * N * N)) / N) ((w - (2 * N + 2 * N * N)) mod N)) eqn:Eij;
          cbn [gate_well_formed all_of ProofSupport.all_of].
        -- apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity].
        -- apply andb_true_intro; split; [apply Nat.ltb_lt; lia|].
           pose proof (dom_pair_idx_lt N _ _ Hi Hj) as Hpr.
           apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity].
      * apply Nat.ltb_ge in E3.
        destruct (Nat.ltb w (2 * N + 4 * N * N)) eqn:E4.
        -- apply Nat.ltb_lt in E4. cbn [gate_well_formed]. apply Nat.ltb_lt. unfold dom_wire_count. lia.
        -- apply Nat.ltb_ge in E4. cbn [gate_well_formed].
           assert (Hall : forall u, (forall j, ProofSupport.Member j u -> j < N) ->
             all_of (fun a => a <? w) (map_over (fun j => 2 * N + 3 * N * N + (w - (2 * N + 4 * N * N)) * N + j) u) = true).
           { intros u Hu. induction u as [|x ur IHu]; simpl; [reflexivity|].
             apply andb_true_intro; split.
             - apply Nat.ltb_lt. pose proof (Hu x (or_introl eq_refl)). nia.
             - apply IHu. intros y Hy. apply Hu; right; exact Hy. }
           apply Hall. intros j Hj. apply member_upto_lt; exact Hj.
  - simpl; lia.
  - intros k Hk. simpl in *. rewrite circuit_of_fun_count.
    unfold dom_out_wire, dom_wire_count. lia.
Qed.

Definition dom_eval (n : nat) (a b : nat -> bool) (tape : list bool) (cyc w : nat) : bool :=
  let N := S n in
  if Nat.ltb w N then a w
  else if Nat.ltb w (2 * N) then b (w - N)
  else if Nat.ltb w (2 * N + N * N) then bit_at tape (w - 2 * N)
  else if Nat.ltb w (2 * N + 2 * N * N) then
    let p := w - (2 * N + N * N) in andb (a (p / N)) (b (p mod N))
  else if Nat.ltb w (2 * N + 3 * N * N) then
    let p := w - (2 * N + 2 * N * N) in
    let i := p / N in let j := p mod N in
    xorb (andb (a i) (b j)) (dom_rbit N tape i j)
  else if Nat.ltb w (2 * N + 4 * N * N) then
    match cyc with
    | 0 => false
    | S _ =>
      let p := w - (2 * N + 3 * N * N) in
      let i := p / N in let j := p mod N in
      xorb (andb (a i) (b j)) (dom_rbit N tape i j)
    end
  else
    match cyc with
    | 0 => false
    | S _ =>
      let i := w - (2 * N + 4 * N * N) in
      xor_sum_upto (fun j => xorb (andb (a i) (b j)) (dom_rbit N tape i j)) N
    end.

Lemma dom_eval_layer_in :
  forall n regs a b tape w,
    w < 2 * S n + S n * S n ->
    eval_wire gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
      regs
      (fun i => if Nat.ltb i (S n) then a i
                else if Nat.ltb i (2 * S n) then b (i - S n)
                else bit_at tape (i - 2 * S n))
      (wire_count (circuit_of_fun (dom_wire_count n) (dom_gate n))) w =
    if Nat.ltb w (S n) then a w
    else if Nat.ltb w (2 * S n) then b (w - S n)
    else bit_at tape (w - 2 * S n).
Proof.
  intros n regs a b tape w Hw.
  destruct (dom_and_well_formed n) as [Hwf _].
  unfold dom_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
  rewrite eval_wire_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold dom_wire_count; lia].
  rewrite gate_at_circuit_of_fun; [|unfold dom_wire_count; lia].
  unfold dom_gate.
  assert (Elt : (w <? 2 * S n + S n * S n) = true) by (apply Nat.ltb_lt; exact Hw).
  rewrite Elt. reflexivity.
Qed.

Lemma dom_eval_layer_mul :
  forall n regs a b tape p,
    p < S n * S n ->
    eval_wire gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
      regs
      (fun i => if Nat.ltb i (S n) then a i
                else if Nat.ltb i (2 * S n) then b (i - S n)
                else bit_at tape (i - 2 * S n))
      (wire_count (circuit_of_fun (dom_wire_count n) (dom_gate n))) (2 * S n + S n * S n + p) =
    andb (a (p / S n)) (b (p mod S n)).
Proof.
  intros n regs a b tape p Hp.
  destruct (dom_and_well_formed n) as [Hwf _].
  unfold dom_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
  destruct (div_mod_pair_bound (S n) p ltac:(lia) Hp) as [Hi [Hj _]].
  rewrite eval_wire_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold dom_wire_count; lia].
  rewrite gate_at_circuit_of_fun; [|unfold dom_wire_count; lia].
  unfold dom_gate at 1. cbv zeta.
  destruct (Nat.ltb (2 * S n + S n * S n + p) (2 * S n + S n * S n)) eqn:E1; [apply Nat.ltb_lt in E1; lia|].
  destruct (Nat.ltb (2 * S n + S n * S n + p) (2 * S n + 2 * S n * S n)) eqn:E2; [|apply Nat.ltb_ge in E2; lia].
  replace (2 * S n + S n * S n + p - (2 * S n + S n * S n)) with p by lia.
  cbn [map_over ProofSupport.map_over bool_ops at_member].
  repeat (rewrite dom_eval_layer_in; [|lia]).
  destruct (Nat.ltb (p / S n) (S n)) eqn:Ea; [|apply Nat.ltb_ge in Ea; lia].
  destruct (Nat.ltb (S n + p mod S n) (S n)) eqn:Eb1; [apply Nat.ltb_lt in Eb1; lia|].
  destruct (Nat.ltb (S n + p mod S n) (2 * S n)) eqn:Eb2; [|apply Nat.ltb_ge in Eb2; lia].
  replace (S n + p mod S n - S n) with (p mod S n) by lia.
  reflexivity.
Qed.

Lemma dom_eval_layer_mask :
  forall n regs a b tape p,
    p < S n * S n ->
    eval_wire gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
      regs
      (fun i => if Nat.ltb i (S n) then a i
                else if Nat.ltb i (2 * S n) then b (i - S n)
                else bit_at tape (i - 2 * S n))
      (wire_count (circuit_of_fun (dom_wire_count n) (dom_gate n))) (2 * S n + 2 * S n * S n + p) =
    xorb (andb (a (p / S n)) (b (p mod S n))) (dom_rbit (S n) tape (p / S n) (p mod S n)).
Proof.
  intros n regs a b tape p Hp.
  destruct (dom_and_well_formed n) as [Hwf _].
  unfold dom_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
  destruct (div_mod_pair_bound (S n) p ltac:(lia) Hp) as [Hi [Hj _]].
  rewrite eval_wire_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold dom_wire_count; lia].
  rewrite gate_at_circuit_of_fun; [|unfold dom_wire_count; lia].
  unfold dom_gate at 1. cbv zeta.
  destruct (Nat.ltb (2 * S n + 2 * S n * S n + p) (2 * S n + S n * S n)) eqn:E1; [apply Nat.ltb_lt in E1; lia|].
  destruct (Nat.ltb (2 * S n + 2 * S n * S n + p) (2 * S n + 2 * S n * S n)) eqn:E2; [apply Nat.ltb_lt in E2; lia|].
  destruct (Nat.ltb (2 * S n + 2 * S n * S n + p) (2 * S n + 3 * S n * S n)) eqn:E3; [|apply Nat.ltb_ge in E3; lia].
  replace (2 * S n + 2 * S n * S n + p - (2 * S n + 2 * S n * S n)) with p by lia.
  destruct (Nat.eqb (p / S n) (p mod S n)) eqn:Eij;
    cbn [map_over ProofSupport.map_over bool_ops xor_fold].
  - rewrite dom_eval_layer_mul; [|exact Hp].
    unfold dom_rbit. rewrite Eij. repeat rewrite gf2_add_zero_r. reflexivity.
  - rewrite dom_eval_layer_mul; [|exact Hp].
    pose proof (dom_pair_idx_lt (S n) _ _ Hi Hj) as Hpr.
    rewrite dom_eval_layer_in; [|lia].
    destruct (Nat.ltb (2 * S n + dom_pair_idx (S n) (p / S n) (p mod S n)) (S n)) eqn:Er1; [apply Nat.ltb_lt in Er1; lia|].
    destruct (Nat.ltb (2 * S n + dom_pair_idx (S n) (p / S n) (p mod S n)) (2 * S n)) eqn:Er2; [apply Nat.ltb_lt in Er2; lia|].
    replace (2 * S n + dom_pair_idx (S n) (p / S n) (p mod S n) - 2 * S n) with (dom_pair_idx (S n) (p / S n) (p mod S n)) by lia.
    unfold dom_rbit. rewrite Eij. rewrite gf2_add_zero_r. reflexivity.
Qed.

Lemma dom_eval_comb :
  forall n regs a b tape w0,
    w0 < 2 * S n + 3 * S n * S n ->
    eval_wire gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
      regs
      (fun i => if Nat.ltb i (S n) then a i
                else if Nat.ltb i (2 * S n) then b (i - S n)
                else bit_at tape (i - 2 * S n))
      (wire_count (circuit_of_fun (dom_wire_count n) (dom_gate n))) w0 =
    dom_eval n a b tape 0 w0.
Proof.
  intros n regs a b tape w0 Hw0.
  unfold dom_eval. cbv zeta.
  destruct (Nat.ltb w0 (2 * S n + S n * S n)) eqn:E_in.
  - assert (Hw0_lt : w0 < 2 * S n + S n * S n) by (apply Nat.ltb_lt; exact E_in).
    rewrite dom_eval_layer_in; [|exact Hw0_lt].
    destruct (Nat.ltb w0 (S n)); [reflexivity | destruct (Nat.ltb w0 (2 * S n)); reflexivity].
  - assert (Hw0_ge1 : 2 * S n + S n * S n <= w0) by (apply Nat.ltb_ge; exact E_in).
    destruct (Nat.ltb w0 (S n)) eqn:E0; [apply Nat.ltb_lt in E0; lia|].
    destruct (Nat.ltb w0 (2 * S n)) eqn:E1; [apply Nat.ltb_lt in E1; lia|].
    destruct (Nat.ltb w0 (2 * S n + 2 * S n * S n)) eqn:E_mul.
    + assert (Hw0_lt : w0 < 2 * S n + 2 * S n * S n) by (apply Nat.ltb_lt; exact E_mul).
      replace w0 with (2 * S n + S n * S n + (w0 - (2 * S n + S n * S n))) at 1 by lia.
      rewrite dom_eval_layer_mul; [reflexivity | lia].
    + assert (Hw0_ge2 : 2 * S n + 2 * S n * S n <= w0) by (apply Nat.ltb_ge; exact E_mul).
      assert (E_mask : (w0 <? 2 * S n + 3 * S n * S n) = true) by (apply Nat.ltb_lt; exact Hw0).
      rewrite E_mask.
      replace w0 with (2 * S n + 2 * S n * S n + (w0 - (2 * S n + 2 * S n * S n))) at 1 by lia.
      rewrite dom_eval_layer_mask; [reflexivity | lia].
Qed.

Lemma dom_eval_comb_cyc :
  forall n a b tape cyc w0,
    w0 < 2 * S n + 3 * S n * S n ->
    dom_eval n a b tape cyc w0 = dom_eval n a b tape 0 w0.
Proof.
  intros n a b tape cyc w0 Hw0. unfold dom_eval. cbv zeta.
  destruct (Nat.ltb w0 (S n)); [reflexivity|].
  destruct (Nat.ltb w0 (2 * S n)); [reflexivity|].
  destruct (Nat.ltb w0 (2 * S n + S n * S n)); [reflexivity|].
  destruct (Nat.ltb w0 (2 * S n + 2 * S n * S n)); [reflexivity|].
  destruct (Nat.ltb w0 (2 * S n + 3 * S n * S n)) eqn:E; [reflexivity|].
  apply Nat.ltb_ge in E. lia.
Qed.

Lemma dom_value_eq :
  forall n (a : ShareMatrix (dom_and_gadget n)) tape cyc w,
    w < dom_wire_count n ->
    gd_value (dom_and_gadget n) a tape cyc w =
    dom_eval n (a 0) (a 1) tape cyc w.
Proof.
  intros n a tape cyc.
  destruct (dom_and_well_formed n) as [Hwf _].
  unfold dom_and_gadget in Hwf. cbn [gd_circuit] in Hwf.
  assert (Hregs : forall t w, w < dom_wire_count n ->
    regs_at gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
      (fun _ => false)
      (fun _ i => if Nat.ltb i (S n) then a 0 i
                  else if Nat.ltb i (2 * S n) then a 1 (i - S n)
                  else bit_at tape (i - 2 * S n))
      t w =
    match t with
    | 0 => false
    | S _ =>
      if Nat.ltb w (2 * S n + 3 * S n * S n) then false
      else if Nat.ltb w (2 * S n + 4 * S n * S n) then
        xorb (andb (a 0 ((w - (2 * S n + 3 * S n * S n)) / S n))
                   (a 1 ((w - (2 * S n + 3 * S n * S n)) mod S n)))
             (dom_rbit (S n) tape ((w - (2 * S n + 3 * S n * S n)) / S n)
                                  ((w - (2 * S n + 3 * S n * S n)) mod S n))
      else false
    end /\
    forall w0, w0 < dom_wire_count n ->
      value_at gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
        (fun _ => false)
        (fun _ i => if Nat.ltb i (S n) then a 0 i
                    else if Nat.ltb i (2 * S n) then a 1 (i - S n)
                    else bit_at tape (i - 2 * S n))
        t w0 = dom_eval n (a 0) (a 1) tape t w0).
  { induction t as [|t IH]; intros w Hw.
    - assert (Hr0 : regs_at gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
        (fun _ => false)
        (fun _ i => if Nat.ltb i (S n) then a 0 i
                    else if Nat.ltb i (2 * S n) then a 1 (i - S n)
                    else bit_at tape (i - 2 * S n))
        0 w = false) by reflexivity.
      split; [exact Hr0|].
      intros w0 Hw0. set (N := S n) in *.
      destruct (Nat.ltb w0 (2 * N + 3 * N * N)) eqn:Ecomb.
      + apply Nat.ltb_lt in Ecomb. unfold value_at. apply dom_eval_comb; exact Ecomb.
      + apply Nat.ltb_ge in Ecomb.
        rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw0].
        rewrite gate_at_circuit_of_fun; [|exact Hw0].
        unfold dom_gate at 1. unfold dom_eval. change (S n) with N.
        destruct (Nat.ltb w0 N) eqn:E0; [apply Nat.ltb_lt in E0; lia|].
        destruct (Nat.ltb w0 (2 * N)) eqn:E1; [apply Nat.ltb_lt in E1; lia|].
        destruct (Nat.ltb w0 (2 * N + N * N)) eqn:E2; [apply Nat.ltb_lt in E2; lia|].
        destruct (Nat.ltb w0 (2 * N + 2 * N * N)) eqn:E3; [apply Nat.ltb_lt in E3; lia|].
        destruct (Nat.ltb w0 (2 * N + 3 * N * N)) eqn:E4; [apply Nat.ltb_lt in E4; lia|].
        destruct (Nat.ltb w0 (2 * N + 4 * N * N)) eqn:E5; [reflexivity|].
        cbn [bool_ops]. rewrite map_over_compose.
        change (xor_fold (map_over (fun x => value_at gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
          (fun _ => false) (fun _ i => if i <? N then a 0 i else if i <? 2 * N then a 1 (i - N) else bit_at tape (i - 2 * N)) 0
          (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + x)) (upto N)))
          with (xor_sum_upto (fun j => value_at gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
            (fun _ => false) (fun _ i => if i <? N then a 0 i else if i <? 2 * N then a 1 (i - N) else bit_at tape (i - 2 * N)) 0
            (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j)) N).
        transitivity (xor_sum_upto (fun _ => false) N); [|apply xor_sum_upto_false].
        apply xor_sum_upto_ext. intros j Hj.
        assert (Hreg_lt : 2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j < dom_wire_count n)
          by (unfold dom_wire_count in *; nia).
        rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hreg_lt].
        rewrite gate_at_circuit_of_fun; [|exact Hreg_lt].
        unfold dom_gate at 1. change (S n) with N.
        destruct (Nat.ltb (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j) (2 * N + N * N)) eqn:R1;
          [apply Nat.ltb_lt in R1; nia|].
        destruct (Nat.ltb (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j) (2 * N + 2 * N * N)) eqn:R2;
          [apply Nat.ltb_lt in R2; nia|].
        destruct (Nat.ltb (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j) (2 * N + 3 * N * N)) eqn:R3;
          [apply Nat.ltb_lt in R3; nia|].
        destruct (Nat.ltb (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j) (2 * N + 4 * N * N)) eqn:R4;
          [reflexivity | apply Nat.ltb_ge in R4; unfold dom_wire_count in *; nia].
    - destruct (IH 0 ltac:(unfold dom_wire_count; lia)) as [_ IHval].
      assert (Hr_step : forall w1, w1 < dom_wire_count n ->
        regs_at gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
          (fun _ => false)
          (fun _ i => if Nat.ltb i (S n) then a 0 i
                      else if Nat.ltb i (2 * S n) then a 1 (i - S n)
                      else bit_at tape (i - 2 * S n))
          (S t) w1 =
        if Nat.ltb w1 (2 * S n + 3 * S n * S n) then false
        else if Nat.ltb w1 (2 * S n + 4 * S n * S n) then
          xorb (andb (a 0 ((w1 - (2 * S n + 3 * S n * S n)) / S n))
                     (a 1 ((w1 - (2 * S n + 3 * S n * S n)) mod S n)))
               (dom_rbit (S n) tape ((w1 - (2 * S n + 3 * S n * S n)) / S n)
                                    ((w1 - (2 * S n + 3 * S n * S n)) mod S n))
        else false).
      { intros w1 Hw1. rewrite regs_at_succ_step. rewrite gate_at_circuit_of_fun; [|exact Hw1].
        set (N := S n) in *. unfold dom_gate at 1. change (S n) with N.
        destruct (Nat.ltb w1 (2 * N + N * N)) eqn:E1.
        - destruct (IH w1 Hw1) as [IHr _]. rewrite IHr.
          assert (E1': (w1 <? 2 * N + 3 * N * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in E1; lia).
          destruct t; [rewrite E1'; reflexivity | reflexivity].
        - destruct (Nat.ltb w1 (2 * N + 2 * N * N)) eqn:E2.
          + destruct (IH w1 Hw1) as [IHr _]. rewrite IHr.
            assert (E2': (w1 <? 2 * N + 3 * N * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in E2; lia).
            destruct t; [rewrite E2'; reflexivity | reflexivity].
          + destruct (Nat.ltb w1 (2 * N + 3 * N * N)) eqn:E3.
            * destruct (IH w1 Hw1) as [IHr _]. rewrite IHr.
              destruct (Nat.eqb ((w1 - (2 * N + 2 * N * N)) / N) ((w1 - (2 * N + 2 * N * N)) mod N));
                destruct t; try rewrite E3; reflexivity.
            * destruct (Nat.ltb w1 (2 * N + 4 * N * N)) eqn:E4.
              -- apply Nat.ltb_lt in E4. apply Nat.ltb_ge in E3.
                 rewrite IHval; [|unfold dom_wire_count; lia].
                 unfold dom_eval. change (S n) with N.
                 assert (Hs_lt : 2 * N + 2 * N * N + (w1 - (2 * N + 3 * N * N)) < 2 * N + 3 * N * N) by lia.
                 destruct (Nat.ltb (2 * N + 2 * N * N + (w1 - (2 * N + 3 * N * N))) N) eqn:S1; [apply Nat.ltb_lt in S1; lia|].
                 destruct (Nat.ltb (2 * N + 2 * N * N + (w1 - (2 * N + 3 * N * N))) (2 * N)) eqn:S2; [apply Nat.ltb_lt in S2; lia|].
                 destruct (Nat.ltb (2 * N + 2 * N * N + (w1 - (2 * N + 3 * N * N))) (2 * N + N * N)) eqn:S3; [apply Nat.ltb_lt in S3; lia|].
                 destruct (Nat.ltb (2 * N + 2 * N * N + (w1 - (2 * N + 3 * N * N))) (2 * N + 2 * N * N)) eqn:S4; [apply Nat.ltb_lt in S4; lia|].
                 assert (S5 : (2 * N + 2 * N * N + (w1 - (2 * N + 3 * N * N)) <? 2 * N + 3 * N * N) = true)
                   by (apply Nat.ltb_lt; lia).
                 rewrite S5.
                 replace (2 * N + 2 * N * N + (w1 - (2 * N + 3 * N * N)) - (2 * N + 2 * N * N))
                   with (w1 - (2 * N + 3 * N * N)) by lia.
                 reflexivity.
              -- destruct (IH w1 Hw1) as [IHr _]. rewrite IHr.
                 destruct t; try rewrite E3, E4; reflexivity. }
      split; [exact (Hr_step w Hw)|].
      intros w0 Hw0. set (N := S n) in *.
      destruct (Nat.ltb w0 (2 * N + 3 * N * N)) eqn:Ecomb.
      + apply Nat.ltb_lt in Ecomb. unfold value_at.
        rewrite dom_eval_comb; [|exact Ecomb]. symmetry. apply dom_eval_comb_cyc; exact Ecomb.
      + apply Nat.ltb_ge in Ecomb.
        rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw0].
        rewrite gate_at_circuit_of_fun; [|exact Hw0].
        unfold dom_gate at 1. unfold dom_eval. change (S n) with N.
        destruct (Nat.ltb w0 N) eqn:E0; [apply Nat.ltb_lt in E0; lia|].
        destruct (Nat.ltb w0 (2 * N)) eqn:E1; [apply Nat.ltb_lt in E1; lia|].
        destruct (Nat.ltb w0 (2 * N + N * N)) eqn:E2; [apply Nat.ltb_lt in E2; lia|].
        destruct (Nat.ltb w0 (2 * N + 2 * N * N)) eqn:E3; [apply Nat.ltb_lt in E3; lia|].
        destruct (Nat.ltb w0 (2 * N + 3 * N * N)) eqn:E4; [apply Nat.ltb_lt in E4; lia|].
        destruct (Nat.ltb w0 (2 * N + 4 * N * N)) eqn:E5.
        * rewrite Hr_step; [|exact Hw0]. rewrite E4, E5. reflexivity.
        * cbn [bool_ops]. rewrite map_over_compose.
          change (xor_fold (map_over (fun x => value_at gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
            (fun _ => false) (fun _ i => if i <? N then a 0 i else if i <? 2 * N then a 1 (i - N) else bit_at tape (i - 2 * N)) (S t)
            (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + x)) (upto N)))
            with (xor_sum_upto (fun j => value_at gf2_sharing bool_ops (circuit_of_fun (dom_wire_count n) (dom_gate n))
              (fun _ => false) (fun _ i => if i <? N then a 0 i else if i <? 2 * N then a 1 (i - N) else bit_at tape (i - 2 * N)) (S t)
              (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j)) N).
          apply xor_sum_upto_ext. intros j Hj.
          assert (Hreg_lt : 2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j < dom_wire_count n)
            by (unfold dom_wire_count in *; nia).
          rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hreg_lt].
          rewrite gate_at_circuit_of_fun; [|exact Hreg_lt].
          unfold dom_gate at 1. change (S n) with N.
          destruct (Nat.ltb (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j) (2 * N + N * N)) eqn:R1;
            [apply Nat.ltb_lt in R1; nia|].
          destruct (Nat.ltb (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j) (2 * N + 2 * N * N)) eqn:R2;
            [apply Nat.ltb_lt in R2; nia|].
          destruct (Nat.ltb (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j) (2 * N + 3 * N * N)) eqn:R3;
            [apply Nat.ltb_lt in R3; nia|].
          destruct (Nat.ltb (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j) (2 * N + 4 * N * N)) eqn:R4;
            [|apply Nat.ltb_ge in R4; unfold dom_wire_count in *; nia].
          rewrite Hr_step; [|exact Hreg_lt]. rewrite R3, R4.
          change (S n) with N.
          replace (2 * N + 3 * N * N + (w0 - (2 * N + 4 * N * N)) * N + j - (2 * N + 3 * N * N))
            with ((w0 - (2 * N + 4 * N * N)) * N + j)
            by (rewrite <- Nat.add_assoc; rewrite (Nat.add_comm (2 * N + 3 * N * N)); symmetry; apply Nat.add_sub).
          assert (Hi_lt : w0 - (2 * N + 4 * N * N) < N) by (unfold dom_wire_count in *; change (S n) with N in Hw0; nia).
          destruct (div_mod_pair_id N (w0 - (2 * N + 4 * N * N)) j Hi_lt Hj) as [Hd Hm].
          rewrite Hd, Hm. reflexivity. }
  intros w Hw. destruct (Hregs cyc 0 ltac:(unfold dom_wire_count; lia)) as [_ Hval].
  exact (Hval w Hw).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem dom_and_correct :
  forall n (a : ShareMatrix (dom_and_gadget n)) tape,
    xor_sum_upto (fun k => gd_value (dom_and_gadget n) a tape 1 (gd_out (dom_and_gadget n) k)) (S n) =
    andb (xor_sum_upto (a 0) (S n)) (xor_sum_upto (a 1) (S n)).
Proof.
  intros n a tape. set (N := S n).
  assert (Hvals : xor_sum_upto (fun k => gd_value (dom_and_gadget n) a tape 1 (gd_out (dom_and_gadget n) k)) N =
                  xor_sum_upto (fun k => xor_sum_upto (fun j => xorb (andb (a 0 k) (a 1 j)) (dom_rbit N tape k j)) N) N).
  { apply xor_sum_upto_ext. intros k Hk.
    rewrite dom_value_eq; [|unfold dom_and_gadget; cbn [gd_out]; unfold N in Hk; unfold dom_wire_count, dom_out_wire; cbv zeta; lia].
    unfold dom_and_gadget at 1; cbn [gd_out]. unfold dom_eval, dom_out_wire. change (S n) with N.
    destruct (Nat.ltb (2 * N + 4 * N * N + k) N) eqn:E0; [apply Nat.ltb_lt in E0; lia|].
    destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N)) eqn:E1; [apply Nat.ltb_lt in E1; lia|].
    destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N + N * N)) eqn:E2; [apply Nat.ltb_lt in E2; lia|].
    destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N + 2 * N * N)) eqn:E3; [apply Nat.ltb_lt in E3; lia|].
    destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N + 3 * N * N)) eqn:E4; [apply Nat.ltb_lt in E4; lia|].
    destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N + 4 * N * N)) eqn:E5; [apply Nat.ltb_lt in E5; lia|].
    replace (2 * N + 4 * N * N + k - (2 * N + 4 * N * N)) with k
      by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
    reflexivity. }
  rewrite Hvals.
  assert (Hsplit :
    xor_sum_upto (fun k => xor_sum_upto (fun j => xorb (andb (a 0 k) (a 1 j)) (dom_rbit N tape k j)) N) N =
    xorb (xor_sum_upto (fun k => xor_sum_upto (fun j => andb (a 0 k) (a 1 j)) N) N)
         (xor_sum_upto (fun k => xor_sum_upto (fun j => dom_rbit N tape k j) N) N)).
  { rewrite <- xor_sum_upto_xorb. apply xor_sum_upto_ext. intros k _. apply xor_sum_upto_xorb. }
  rewrite Hsplit.
  rewrite (xor_sum_upto_antisym_zero (dom_rbit N tape) N (dom_rbit_diag N tape) (dom_rbit_sym N tape)).
  rewrite gf2_add_zero_r.
  transitivity (xor_sum_upto (fun k => andb (a 0 k) (xor_sum_upto (a 1) N)) N).
  - apply xor_sum_upto_ext. intros k _. apply xor_sum_upto_and_l.
  - apply xor_sum_upto_and_r.
Qed.

(* Clean inductive helper for `flat_map_over` over register lists in `dom_stable_sources`. *)
Lemma flat_map_over_cons :
  forall {A B : Type} (f : A -> list B) (x : A) (r : list A),
    flat_map_over f (x :: r) = app (f x) (flat_map_over f r).
Proof. intros A B f x r. reflexivity. Qed.

Lemma dom_stable_in :
  forall n w, w < 2 * S n + S n * S n ->
    stable_sources (circuit_of_fun (dom_wire_count n) (dom_gate n)) (dom_wire_count n) w = w :: nil.
Proof.
  intros n w Hw.
  destruct (dom_and_well_formed n) as [Hwf _].
  unfold dom_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
  rewrite <- (circuit_of_fun_count (dom_wire_count n) (dom_gate n)) at 2.
  rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold dom_wire_count; lia].
  rewrite gate_at_circuit_of_fun; [|unfold dom_wire_count; lia].
  unfold dom_gate. cbv zeta.
  assert (Elt : (w <? 2 * S n + S n * S n) = true) by (apply Nat.ltb_lt; exact Hw).
  rewrite Elt. reflexivity.
Qed.

Lemma dom_stable_mul :
  forall n p, p < S n * S n ->
    stable_sources (circuit_of_fun (dom_wire_count n) (dom_gate n)) (dom_wire_count n) (2 * S n + S n * S n + p) =
    (p / S n) :: (S n + p mod S n) :: nil.
Proof.
  intros n p Hp.
  destruct (dom_and_well_formed n) as [Hwf _].
  unfold dom_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
  destruct (div_mod_pair_bound (S n) p ltac:(lia) Hp) as [Hi [Hj _]].
  rewrite <- (circuit_of_fun_count (dom_wire_count n) (dom_gate n)) at 2.
  rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold dom_wire_count; lia].
  rewrite gate_at_circuit_of_fun; [|unfold dom_wire_count; lia].
  unfold dom_gate at 1. cbv zeta.
  destruct (Nat.ltb (2 * S n + S n * S n + p) (2 * S n + S n * S n)) eqn:E1; [apply Nat.ltb_lt in E1; lia|].
  destruct (Nat.ltb (2 * S n + S n * S n + p) (2 * S n + 2 * S n * S n)) eqn:E2; [|apply Nat.ltb_ge in E2; lia].
  replace (2 * S n + S n * S n + p - (2 * S n + S n * S n)) with p by lia.
  cbn [flat_map_over app].
  rewrite !circuit_of_fun_count.
  repeat (rewrite dom_stable_in; [|lia]).
  reflexivity.
Qed.

Lemma dom_stable_sources :
  forall n w, w < dom_wire_count n ->
    let N := S n in
    stable_sources (circuit_of_fun (dom_wire_count n) (dom_gate n)) (dom_wire_count n) w =
    if Nat.ltb w (2 * N + N * N) then w :: nil
    else if Nat.ltb w (2 * N + 2 * N * N) then
      let p := w - (2 * N + N * N) in (p / N) :: (N + p mod N) :: nil
    else if Nat.ltb w (2 * N + 3 * N * N) then
      let p := w - (2 * N + 2 * N * N) in
      let i := p / N in let j := p mod N in
      if Nat.eqb i j then i :: (N + j) :: nil
      else i :: (N + j) :: (2 * N + dom_pair_idx N i j) :: nil
    else if Nat.ltb w (2 * N + 4 * N * N) then w :: nil
    else
      let i := w - (2 * N + 4 * N * N) in
      map_over (fun j => 2 * N + 3 * N * N + i * N + j) (upto N).
Proof.
  intros n w Hw. cbv zeta.
  destruct (Nat.ltb w (2 * S n + S n * S n)) eqn:E1.
  - apply dom_stable_in. apply Nat.ltb_lt; exact E1.
  - assert (Hge1 : 2 * S n + S n * S n <= w) by (apply Nat.ltb_ge; exact E1).
    destruct (Nat.ltb w (2 * S n + 2 * S n * S n)) eqn:E2.
    + assert (Hlt2 : w < 2 * S n + 2 * S n * S n) by (apply Nat.ltb_lt; exact E2).
      replace w with (2 * S n + S n * S n + (w - (2 * S n + S n * S n))) at 1 by lia.
      apply dom_stable_mul. lia.
    + assert (Hge2 : 2 * S n + 2 * S n * S n <= w) by (apply Nat.ltb_ge; exact E2).
      destruct (dom_and_well_formed n) as [Hwf _].
      unfold dom_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
      assert (Hw_cnt : w < wire_count (circuit_of_fun (dom_wire_count n) (dom_gate n)))
        by (rewrite circuit_of_fun_count; exact Hw).
      rewrite <- (circuit_of_fun_count (dom_wire_count n) (dom_gate n)) at 2.
      rewrite stable_sources_unfold; [|exact Hwf | exact Hw_cnt].
      rewrite gate_at_circuit_of_fun; [|exact Hw].
      unfold dom_wire_count in Hw.
      destruct (Nat.ltb w (2 * S n + 3 * S n * S n)) eqn:E3.
      * assert (Hlt3 : w < 2 * S n + 3 * S n * S n) by (apply Nat.ltb_lt; exact E3).
        destruct (div_mod_pair_bound (S n) (w - (2 * S n + 2 * S n * S n)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
        unfold dom_gate at 1. cbv zeta.
        rewrite E1, E2, E3.
        destruct (Nat.eqb ((w - (2 * S n + 2 * S n * S n)) / S n) ((w - (2 * S n + 2 * S n * S n)) mod S n)) eqn:Eij;
          cbn [flat_map_over app]; rewrite !circuit_of_fun_count.
        -- replace (2 * S n + S n * S n + (w - (2 * S n + 2 * S n * S n)))
             with (2 * S n + S n * S n + (w - (2 * S n + 2 * S n * S n))) by reflexivity.
           rewrite dom_stable_mul; [reflexivity | lia].
        -- pose proof (dom_pair_idx_lt (S n) _ _ Hi Hj) as Hpr.
           rewrite dom_stable_mul; [|lia].
           rewrite dom_stable_in; [|lia].
           reflexivity.
      * assert (Hge3 : 2 * S n + 3 * S n * S n <= w) by (apply Nat.ltb_ge; exact E3).
        unfold dom_gate at 1. cbv zeta. rewrite E1, E2, E3.
        destruct (Nat.ltb w (2 * S n + 4 * S n * S n)) eqn:E4; [reflexivity|].
        assert (Hge4 : 2 * S n + 4 * S n * S n <= w) by (apply Nat.ltb_ge; exact E4).
        assert (Hlist : forall u, (forall j, ProofSupport.Member j u -> j < S n) ->
          flat_map_over (stable_sources (circuit_of_fun (dom_wire_count n) (dom_gate n))
            (wire_count (circuit_of_fun (dom_wire_count n) (dom_gate n))))
            (map_over (fun j => 2 * S n + 3 * S n * S n + (w - (2 * S n + 4 * S n * S n)) * S n + j) u) =
          map_over (fun j => 2 * S n + 3 * S n * S n + (w - (2 * S n + 4 * S n * S n)) * S n + j) u).
        { intros u Hu. induction u as [|j ur IHu]; [reflexivity|].
          cbn [map_over ProofSupport.map_over flat_map_over].
          assert (Hj : j < S n) by (apply Hu; left; reflexivity).
          assert (Hreg_lt : 2 * S n + 3 * S n * S n + (w - (2 * S n + 4 * S n * S n)) * S n + j < dom_wire_count n)
            by (unfold dom_wire_count in *; nia).
          rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hreg_lt].
          rewrite gate_at_circuit_of_fun; [|exact Hreg_lt].
          unfold dom_gate at 1. cbv zeta.
          destruct (Nat.ltb (2 * S n + 3 * S n * S n + (w - (2 * S n + 4 * S n * S n)) * S n + j) (2 * S n + S n * S n)) eqn:R1;
            [apply Nat.ltb_lt in R1; nia|].
          destruct (Nat.ltb (2 * S n + 3 * S n * S n + (w - (2 * S n + 4 * S n * S n)) * S n + j) (2 * S n + 2 * S n * S n)) eqn:R2;
            [apply Nat.ltb_lt in R2; nia|].
          destruct (Nat.ltb (2 * S n + 3 * S n * S n + (w - (2 * S n + 4 * S n * S n)) * S n + j) (2 * S n + 3 * S n * S n)) eqn:R3;
            [apply Nat.ltb_lt in R3; nia|].
          destruct (Nat.ltb (2 * S n + 3 * S n * S n + (w - (2 * S n + 4 * S n * S n)) * S n + j) (2 * S n + 4 * S n * S n)) eqn:R4;
            [|apply Nat.ltb_ge in R4; nia].
          cbn [app]. f_equal. apply IHu. intros y Hy. apply Hu; right; exact Hy. }
        apply Hlist. intros j Hj. apply member_upto_lt; exact Hj.
Qed.

(* Cross-domain unordered pair touched by a wire, when it involves two shares {u, v} (u < v). *)
Definition dom_wire_pair (n w : nat) : option (nat * nat) :=
  let N := S n in
  if Nat.ltb w (2 * N) then None
  else if Nat.ltb w (2 * N + N * N) then
    let r := w - 2 * N in
    let u := r / N in let v := r mod N in
    if Nat.ltb u v then Some (u, v) else None
  else if Nat.ltb w (2 * N + 4 * N * N) then
    let p := (w - (2 * N + N * N)) mod (N * N) in
    let i := p / N in let j := p mod N in
    if Nat.ltb i j then Some (i, j)
    else if Nat.ltb j i then Some (j, i)
    else None
  else None.

Definition dom_out_probed (n : nat) (ps : list Probe) (k : nat) : bool :=
  any_of (fun p => Nat.eqb (p_wire p) (dom_out_wire n k)) ps.

Definition dom_two_dom_probed (n : nat) (ps : list Probe) (u v : nat) : bool :=
  any_of (fun p =>
    match dom_wire_pair n (p_wire p) with
    | Some (x, y) => andb (Nat.eqb x u) (Nat.eqb y v)
    | None => false
    end) ps.

Lemma dom_wire_pair_spec :
  forall n w,
    let N := S n in
    w < dom_wire_count n ->
    dom_wire_pair n w =
    if Nat.ltb w (2 * N) then None
    else if Nat.ltb w (2 * N + N * N) then
      let r := w - 2 * N in let u := r / N in let v := r mod N in
      if Nat.ltb u v then Some (u, v) else None
    else if Nat.ltb w (2 * N + 2 * N * N) then
      let p := w - (2 * N + N * N) in let i := p / N in let j := p mod N in
      if Nat.ltb i j then Some (i, j) else if Nat.ltb j i then Some (j, i) else None
    else if Nat.ltb w (2 * N + 3 * N * N) then
      let p := w - (2 * N + 2 * N * N) in let i := p / N in let j := p mod N in
      if Nat.ltb i j then Some (i, j) else if Nat.ltb j i then Some (j, i) else None
    else if Nat.ltb w (2 * N + 4 * N * N) then
      let p := w - (2 * N + 3 * N * N) in let i := p / N in let j := p mod N in
      if Nat.ltb i j then Some (i, j) else if Nat.ltb j i then Some (j, i) else None
    else None.
Proof.
  intros n w N Hw. unfold dom_wire_pair, N. cbv zeta.
  destruct (Nat.ltb w (2 * S n)) eqn:E1; [reflexivity|].
  destruct (Nat.ltb w (2 * S n + S n * S n)) eqn:E2; [reflexivity|].
  apply Nat.ltb_ge in E2.
  destruct (Nat.ltb w (2 * S n + 2 * S n * S n)) eqn:E3.
  - apply Nat.ltb_lt in E3.
    assert (E4 : (w <? 2 * S n + 4 * S n * S n) = true) by (apply Nat.ltb_lt; lia).
    rewrite E4.
    replace ((w - (2 * S n + S n * S n)) mod (S n * S n)) with (w - (2 * S n + S n * S n))
      by (symmetry; apply Nat.mod_small; lia).
    reflexivity.
  - apply Nat.ltb_ge in E3.
    destruct (Nat.ltb w (2 * S n + 3 * S n * S n)) eqn:E4.
    + apply Nat.ltb_lt in E4.
      assert (E5 : (w <? 2 * S n + 4 * S n * S n) = true) by (apply Nat.ltb_lt; lia).
      rewrite E5.
      replace (w - (2 * S n + S n * S n)) with ((w - (2 * S n + 2 * S n * S n)) + 1 * (S n * S n)) by lia.
      rewrite Nat.Div0.mod_add.
      replace ((w - (2 * S n + 2 * S n * S n)) mod (S n * S n)) with (w - (2 * S n + 2 * S n * S n))
        by (symmetry; apply Nat.mod_small; lia).
      reflexivity.
    + apply Nat.ltb_ge in E4.
      destruct (Nat.ltb w (2 * S n + 4 * S n * S n)) eqn:E5; [|reflexivity].
      apply Nat.ltb_lt in E5.
      replace (w - (2 * S n + S n * S n)) with ((w - (2 * S n + 3 * S n * S n)) + 2 * (S n * S n)) by lia.
      rewrite Nat.Div0.mod_add.
      replace ((w - (2 * S n + 3 * S n * S n)) mod (S n * S n)) with (w - (2 * S n + 3 * S n * S n))
        by (symmetry; apply Nat.mod_small; lia).
      reflexivity.
Qed.

Lemma dom_two_dom_probed_member :
  forall n ps u v p,
    ProofSupport.Member p ps ->
    dom_wire_pair n (p_wire p) = Some (u, v) ->
    dom_two_dom_probed n ps u v = true.
Proof.
  intros n ps u v p Hp Hwp. unfold dom_two_dom_probed.
  induction ps as [|q r IH]; simpl in *; [contradiction|].
  destruct Hp as [->|Hp].
  - rewrite Hwp. repeat rewrite eqb_refl_nat. reflexivity.
  - rewrite (IH Hp). destruct (dom_wire_pair n (p_wire q)) as [[x y]|];
      [destruct (andb (x =? u) (y =? v)); reflexivity | reflexivity].
Qed.

Lemma dom_out_probed_member :
  forall n ps k p,
    ProofSupport.Member p ps ->
    p_wire p = dom_out_wire n k ->
    dom_out_probed n ps k = true.
Proof.
  intros n ps k p Hp Hw. unfold dom_out_probed.
  induction ps as [|q r IH]; simpl in *; [contradiction|].
  destruct Hp as [->|Hp].
  - rewrite Hw, eqb_refl_nat. reflexivity.
  - rewrite (IH Hp). destruct (Nat.eqb (p_wire q) (dom_out_wire n k)); reflexivity.
Qed.

Lemma dom_out_probed_inv :
  forall n ps k,
    dom_out_probed n ps k = true ->
    exists p, ProofSupport.Member p ps /\ p_wire p = dom_out_wire n k.
Proof.
  intros n ps k Hp. unfold dom_out_probed in Hp.
  induction ps as [|q r IH]; simpl in *; [discriminate|].
  destruct (Nat.eqb (p_wire q) (dom_out_wire n k)) eqn:Eq.
  - apply eqb_sound_nat in Eq. exists q; split; [left; reflexivity | exact Eq].
  - simpl in Hp. destruct (IH Hp) as [p [Hpr Hpw]]. exists p; split; [right; exact Hpr | exact Hpw].
Qed.

Definition dom_pini_contrib (n : nat) (ps : list Probe) (B : nat -> bool) (p : Probe) : option nat * option nat :=
  let N := S n in
  let OutOrB k := orb (B k) (dom_out_probed n ps k) in
  let w := p_wire p in
  if Nat.ltb w N then (Some w, None)
  else if Nat.ltb w (2 * N) then (None, Some (w - N))
  else if Nat.ltb w (2 * N + N * N) then
    let r := w - 2 * N in let u := r / N in let v := r mod N in
    if Nat.ltb u v then
      if OutOrB u then (Some v, Some v)
      else if OutOrB v then (Some u, Some u)
      else (None, None)
    else (None, None)
  else if Nat.ltb w (2 * N + 4 * N * N) then
    let q := (w - (2 * N + N * N)) mod (N * N) in
    let i := q / N in let j := q mod N in
    if Nat.eqb i j then (Some i, Some i)
    else if OutOrB i then (Some j, Some j)
    else if OutOrB j then (Some i, Some i)
    else (Some i, Some j)
  else
    let i := w - (2 * N + 4 * N * N) in (Some i, Some i).

Definition dom_pini_shares (n : nat) (ps : list Probe) (B : nat -> bool) : ShareSet :=
  fun j k =>
    match j with
    | 0 => any_of (fun p => match fst (dom_pini_contrib n ps B p) with Some x => Nat.eqb x k | None => false end) ps
    | 1 => any_of (fun p => match snd (dom_pini_contrib n ps B p) with Some y => Nat.eqb y k | None => false end) ps
    | _ => false
    end.

Lemma any_of_member_true :
  forall {A : Type} (f : A -> bool) (l : list A) (x : A),
    ProofSupport.Member x l -> f x = true -> any_of f l = true.
Proof.
  intros A f l x Hx Hfx. induction l as [|y r IH]; simpl in *; [contradiction|].
  destruct Hx as [->|Hx]; [rewrite Hfx; reflexivity | rewrite (IH Hx); destruct (f y); reflexivity].
Qed.

Lemma dom_pini_shares_hit0 :
  forall n ps B p k y,
    ProofSupport.Member p ps ->
    dom_pini_contrib n ps B p = (Some k, y) ->
    dom_pini_shares n ps B 0 k = true.
Proof.
  intros n ps B p k y Hp Hc. unfold dom_pini_shares.
  eapply any_of_member_true; [exact Hp|].
  cbv beta. rewrite Hc. simpl. apply eqb_refl_nat.
Qed.

Lemma dom_pini_shares_hit1 :
  forall n ps B p x k,
    ProofSupport.Member p ps ->
    dom_pini_contrib n ps B p = (x, Some k) ->
    dom_pini_shares n ps B 1 k = true.
Proof.
  intros n ps B p x k Hp Hc. unfold dom_pini_shares.
  eapply any_of_member_true; [exact Hp|].
  cbv beta. rewrite Hc. simpl. apply eqb_refl_nat.
Qed.

Lemma dom_pini_shares_bounded :
  forall n ps B,
    BoundedBy (dom_and_gadget n) (dom_pini_shares n ps B) (count_of ps).
Proof.
  intros n ps B j Hj. unfold card_in, dom_pini_shares. simpl in Hj.
  apply Nat.ltb_lt in Hj. apply Nat.leb_le.
  destruct j as [|[|j]]; [| |lia].
  - exact (count_filter_any_of_eqb (fun p => fst (dom_pini_contrib n ps B p)) ps (upto (S n)) (upto_NoDup (S n))).
  - exact (count_filter_any_of_eqb (fun p => snd (dom_pini_contrib n ps B p)) ps (upto (S n)) (upto_NoDup (S n))).
Qed.

Definition dom_sim_df (n : nat) (ps : list Probe) (B : nat -> bool)
    (a b : ShareMatrix (dom_and_gadget n)) (df_extra : nat -> bool) (idx : nat) : bool :=
  let N := S n in
  let OutOrB k := orb (B k) (dom_out_probed n ps k) in
  let u := idx / N in let v := idx mod N in
  let base :=
    if Nat.ltb u v then
      if andb (OutOrB u) (andb (negb (OutOrB v)) (negb (dom_two_dom_probed n ps u v))) then
        xorb (andb (a 0 u) (a 1 v)) (andb (b 0 u) (b 1 v))
      else if andb (OutOrB v) (andb (negb (OutOrB u)) (negb (dom_two_dom_probed n ps u v))) then
        xorb (andb (a 0 v) (a 1 u)) (andb (b 0 v) (b 1 u))
      else false
    else false in
  xorb base (df_extra idx).

Lemma dom_and_sim_core :
  forall n ps B a b (df_extra : nat -> bool),
    wires_exist (gd_circuit (dom_and_gadget n)) (map_over p_wire ps) = true ->
    agree_on (dom_and_gadget n) (union_shares (dom_pini_shares n ps B) B) a b ->
    (forall idx, idx < S n * S n -> Nat.ltb (idx / S n) (idx mod S n) = false -> df_extra idx = false) ->
    (forall u v, u < S n -> v < S n -> u < v ->
      (orb (B u) (dom_out_probed n ps u) = true \/
       orb (B v) (dom_out_probed n ps v) = true \/
       dom_two_dom_probed n ps u v = true) ->
      df_extra (u * S n + v) = false) ->
    forall tape, ProofSupport.Member tape (bitvectors (S n * S n)) ->
      internal_view (dom_and_gadget n) ex_robust ps b
        (zip_xorb tape (map_over (dom_sim_df n ps B a b df_extra) (upto (S n * S n)))) =
      internal_view (dom_and_gadget n) ex_robust ps a tape /\
      (forall k, k < S n -> orb (B k) (dom_out_probed n ps k) = true ->
        forall j, j < S n ->
          xorb (andb (b 0 k) (b 1 j))
            (dom_rbit (S n) (zip_xorb tape (map_over (dom_sim_df n ps B a b df_extra) (upto (S n * S n)))) k j) =
          xorb (andb (a 0 k) (a 1 j)) (dom_rbit (S n) tape k j)).
Proof.
  intros n ps B a b df_extra Hw Hagree Hextra_ge Hextra.
  set (N := S n) in *.
  set (OutOrB := fun k => orb (B k) (dom_out_probed n ps k)).
  set (df := dom_sim_df n ps B a b df_extra).
  assert (Hagree_pair : forall u v, u < N -> v < N -> u <> v ->
    OutOrB u = true ->
    orb (OutOrB v) (dom_two_dom_probed n ps (if Nat.ltb u v then u else v) (if Nat.ltb u v then v else u)) = true ->
    a 0 u = b 0 u /\ a 1 u = b 1 u /\ a 0 v = b 0 v /\ a 1 v = b 1 v).
  { intros u v Hu Hv Hne HuO Hor.
    assert (Hu_cov : orb (dom_pini_shares n ps B 0 u) (B u) = true /\
                     orb (dom_pini_shares n ps B 1 u) (B u) = true).
    { unfold OutOrB in HuO. apply orb_prop in HuO. destruct HuO as [HBu | Hpu].
      - rewrite HBu. split; destruct (dom_pini_shares n ps B 0 u); destruct (dom_pini_shares n ps B 1 u); reflexivity.
      - destruct (dom_out_probed_inv n ps u Hpu) as [p [Hp Hpw]].
        assert (Hc : dom_pini_contrib n ps B p = (Some u, Some u)).
        { unfold dom_pini_contrib. rewrite Hpw. unfold dom_out_wire. change (S n) with N.
          destruct (Nat.ltb (2 * N + 4 * N * N + u) N) eqn:L1; [apply Nat.ltb_lt in L1; lia|].
          destruct (Nat.ltb (2 * N + 4 * N * N + u) (2 * N)) eqn:L2; [apply Nat.ltb_lt in L2; lia|].
          destruct (Nat.ltb (2 * N + 4 * N * N + u) (2 * N + N * N)) eqn:L3; [apply Nat.ltb_lt in L3; lia|].
          destruct (Nat.ltb (2 * N + 4 * N * N + u) (2 * N + 4 * N * N)) eqn:L4; [apply Nat.ltb_lt in L4; lia|].
          replace (2 * N + 4 * N * N + u - (2 * N + 4 * N * N)) with u by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
          reflexivity. }
        split; [rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
              |rewrite (dom_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity]. }
    assert (Hv_cov : orb (dom_pini_shares n ps B 0 v) (B v) = true /\
                     orb (dom_pini_shares n ps B 1 v) (B v) = true).
    { destruct (OutOrB v) eqn:HvO.
      - unfold OutOrB in HvO. apply orb_prop in HvO. destruct HvO as [HBv | Hpv].
        + rewrite HBv. split; destruct (dom_pini_shares n ps B 0 v); destruct (dom_pini_shares n ps B 1 v); reflexivity.
        + destruct (dom_out_probed_inv n ps v Hpv) as [p [Hp Hpw]].
          assert (Hc : dom_pini_contrib n ps B p = (Some v, Some v)).
          { unfold dom_pini_contrib. rewrite Hpw. unfold dom_out_wire. change (S n) with N.
            destruct (Nat.ltb (2 * N + 4 * N * N + v) N) eqn:L1; [apply Nat.ltb_lt in L1; lia|].
            destruct (Nat.ltb (2 * N + 4 * N * N + v) (2 * N)) eqn:L2; [apply Nat.ltb_lt in L2; lia|].
            destruct (Nat.ltb (2 * N + 4 * N * N + v) (2 * N + N * N)) eqn:L3; [apply Nat.ltb_lt in L3; lia|].
            destruct (Nat.ltb (2 * N + 4 * N * N + v) (2 * N + 4 * N * N)) eqn:L4; [apply Nat.ltb_lt in L4; lia|].
            replace (2 * N + 4 * N * N + v - (2 * N + 4 * N * N)) with v by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
            reflexivity. }
          split; [rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
                |rewrite (dom_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity].
      - apply orb_prop in Hor. destruct Hor as [Abs | Htd]; [discriminate|].
        unfold dom_two_dom_probed in Htd.
        assert (Hex : exists p, ProofSupport.Member p ps /\
          dom_wire_pair n (p_wire p) = Some (if Nat.ltb u v then u else v, if Nat.ltb u v then v else u)).
        { clear -Htd. induction ps as [|q r IH]; simpl in *; [discriminate|].
          destruct (dom_wire_pair n (p_wire q)) as [[x y]|] eqn:Eq.
          - destruct (andb (Nat.eqb x (if Nat.ltb u v then u else v))
                           (Nat.eqb y (if Nat.ltb u v then v else u))) eqn:Exy.
            + apply andb_prop in Exy. destruct Exy as [Ex Ey].
              apply eqb_sound_nat in Ex; apply eqb_sound_nat in Ey; subst.
              exists q; split; [left; reflexivity | exact Eq].
            + destruct (IH Htd) as [p [Hp Hwp]]. exists p; split; [right; exact Hp | exact Hwp].
          - destruct (IH Htd) as [p [Hp Hwp]]. exists p; split; [right; exact Hp | exact Hwp]. }
        destruct Hex as [p [Hp Hwp]].
        assert (Hpw_lt : p_wire p < dom_wire_count n).
        { clear -Hw Hp. unfold wires_exist in Hw.
          induction ps as [|q r IH]; simpl in *; [contradiction|].
          apply andb_prop in Hw. destruct Hw as [Hq Hr].
          destruct Hp as [->|Hp]; [apply Nat.ltb_lt in Hq; rewrite circuit_of_fun_count in Hq; exact Hq | exact (IH Hr Hp)]. }
        rewrite dom_wire_pair_spec in Hwp; [|exact Hpw_lt].
        cbv zeta in Hwp. change (S n) with N in Hwp.
        assert (Hc : dom_pini_contrib n ps B p = (Some v, Some v)).
        { unfold dom_pini_contrib. change (S n) with N. unfold OutOrB in HuO, HvO.
          destruct (Nat.ltb (p_wire p) N) eqn:L0;
            [assert (L0': (p_wire p <? 2 * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in L0; lia); rewrite L0' in Hwp; discriminate|].
          destruct (Nat.ltb (p_wire p) (2 * N)) eqn:L1; [discriminate|].
          destruct (Nat.ltb (p_wire p) (2 * N + N * N)) eqn:L2.
          - destruct (Nat.ltb ((p_wire p - 2 * N) / N) ((p_wire p - 2 * N) mod N)) eqn:Luv; [|discriminate].
            inversion Hwp as [[Hq1 Hq2]]; clear Hwp.
            destruct (Nat.ltb u v) eqn:Euv.
            + assert (Hq1' : (p_wire p - 2 * N) / N = u) by exact Hq1.
              assert (Hq2' : (p_wire p - 2 * N) mod N = v) by exact Hq2.
              rewrite Hq1', Hq2', HuO. reflexivity.
            + assert (Hq1' : (p_wire p - 2 * N) / N = v) by exact Hq1.
              assert (Hq2' : (p_wire p - 2 * N) mod N = u) by exact Hq2.
              rewrite Hq1', Hq2', HvO, HuO. reflexivity.
          - destruct (Nat.ltb (p_wire p) (2 * N + 4 * N * N)) eqn:L3.
            + apply Nat.ltb_ge in L2. apply Nat.ltb_lt in L3.
              destruct (Nat.ltb (p_wire p) (2 * N + 2 * N * N)) eqn:M1.
              * apply Nat.ltb_lt in M1.
                replace ((p_wire p - (2 * N + N * N)) mod (N * N)) with (p_wire p - (2 * N + N * N))
                  by (symmetry; apply Nat.mod_small; lia).
                destruct (Nat.ltb ((p_wire p - (2 * N + N * N)) / N) ((p_wire p - (2 * N + N * N)) mod N)) eqn:C1.
                -- inversion Hwp as [[Hq1 Hq2]]; clear Hwp.
                   assert (Ceq : ((p_wire p - (2 * N + N * N)) / N =? (p_wire p - (2 * N + N * N)) mod N) = false)
                     by (apply Nat.eqb_neq; apply Nat.ltb_lt in C1; lia).
                   rewrite Ceq.
                   destruct (Nat.ltb u v) eqn:Euv.
                   ++ assert (Hq1' : (p_wire p - (2 * N + N * N)) / N = u) by exact Hq1.
                      assert (Hq2' : (p_wire p - (2 * N + N * N)) mod N = v) by exact Hq2.
                      rewrite Hq1', Hq2', HuO. reflexivity.
                   ++ assert (Hq1' : (p_wire p - (2 * N + N * N)) / N = v) by exact Hq1.
                      assert (Hq2' : (p_wire p - (2 * N + N * N)) mod N = u) by exact Hq2.
                      rewrite Hq1', Hq2', HvO, HuO. reflexivity.
                -- destruct (Nat.ltb ((p_wire p - (2 * N + N * N)) mod N) ((p_wire p - (2 * N + N * N)) / N)) eqn:C2; [|discriminate].
                   inversion Hwp as [[Hq1 Hq2]]; clear Hwp.
                   assert (Ceq : ((p_wire p - (2 * N + N * N)) / N =? (p_wire p - (2 * N + N * N)) mod N) = false)
                     by (apply Nat.eqb_neq; apply Nat.ltb_lt in C2; lia).
                   rewrite Ceq.
                   destruct (Nat.ltb u v) eqn:Euv.
                   ++ assert (Hq1' : (p_wire p - (2 * N + N * N)) mod N = u) by exact Hq1.
                      assert (Hq2' : (p_wire p - (2 * N + N * N)) / N = v) by exact Hq2.
                      rewrite Hq1', Hq2', HvO, HuO. reflexivity.
                   ++ assert (Hq1' : (p_wire p - (2 * N + N * N)) mod N = v) by exact Hq1.
                      assert (Hq2' : (p_wire p - (2 * N + N * N)) / N = u) by exact Hq2.
                      rewrite Hq1', Hq2', HuO. reflexivity.
              * apply Nat.ltb_ge in M1.
                destruct (Nat.ltb (p_wire p) (2 * N + 3 * N * N)) eqn:M2.
                -- apply Nat.ltb_lt in M2.
                   replace (p_wire p - (2 * N + N * N)) with ((p_wire p - (2 * N + 2 * N * N)) + 1 * (N * N)) by lia.
                   rewrite Nat.Div0.mod_add.
                   replace ((p_wire p - (2 * N + 2 * N * N)) mod (N * N)) with (p_wire p - (2 * N + 2 * N * N))
                     by (symmetry; apply Nat.mod_small; lia).
                   destruct (Nat.ltb ((p_wire p - (2 * N + 2 * N * N)) / N) ((p_wire p - (2 * N + 2 * N * N)) mod N)) eqn:C1.
                   ++ inversion Hwp as [[Hq1 Hq2]]; clear Hwp.
                      assert (Ceq : ((p_wire p - (2 * N + 2 * N * N)) / N =? (p_wire p - (2 * N + 2 * N * N)) mod N) = false)
                        by (apply Nat.eqb_neq; apply Nat.ltb_lt in C1; lia).
                      rewrite Ceq.
                      destruct (Nat.ltb u v) eqn:Euv.
                      ** assert (Hq1' : (p_wire p - (2 * N + 2 * N * N)) / N = u) by exact Hq1.
                         assert (Hq2' : (p_wire p - (2 * N + 2 * N * N)) mod N = v) by exact Hq2.
                         rewrite Hq1', Hq2', HuO. reflexivity.
                      ** assert (Hq1' : (p_wire p - (2 * N + 2 * N * N)) / N = v) by exact Hq1.
                         assert (Hq2' : (p_wire p - (2 * N + 2 * N * N)) mod N = u) by exact Hq2.
                         rewrite Hq1', Hq2', HvO, HuO. reflexivity.
                   ++ destruct (Nat.ltb ((p_wire p - (2 * N + 2 * N * N)) mod N) ((p_wire p - (2 * N + 2 * N * N)) / N)) eqn:C2; [|discriminate].
                      inversion Hwp as [[Hq1 Hq2]]; clear Hwp.
                      assert (Ceq : ((p_wire p - (2 * N + 2 * N * N)) / N =? (p_wire p - (2 * N + 2 * N * N)) mod N) = false)
                        by (apply Nat.eqb_neq; apply Nat.ltb_lt in C2; lia).
                      rewrite Ceq.
                      destruct (Nat.ltb u v) eqn:Euv.
                      ** assert (Hq1' : (p_wire p - (2 * N + 2 * N * N)) mod N = u) by exact Hq1.
                         assert (Hq2' : (p_wire p - (2 * N + 2 * N * N)) / N = v) by exact Hq2.
                         rewrite Hq1', Hq2', HvO, HuO. reflexivity.
                      ** assert (Hq1' : (p_wire p - (2 * N + 2 * N * N)) mod N = v) by exact Hq1.
                         assert (Hq2' : (p_wire p - (2 * N + 2 * N * N)) / N = u) by exact Hq2.
                         rewrite Hq1', Hq2', HuO. reflexivity.
                -- apply Nat.ltb_ge in M2.
                   replace (p_wire p - (2 * N + N * N)) with ((p_wire p - (2 * N + 3 * N * N)) + 2 * (N * N)) by lia.
                   rewrite Nat.Div0.mod_add.
                   replace ((p_wire p - (2 * N + 3 * N * N)) mod (N * N)) with (p_wire p - (2 * N + 3 * N * N))
                     by (symmetry; apply Nat.mod_small; lia).
                   destruct (Nat.ltb ((p_wire p - (2 * N + 3 * N * N)) / N) ((p_wire p - (2 * N + 3 * N * N)) mod N)) eqn:C1.
                   ++ inversion Hwp as [[Hq1 Hq2]]; clear Hwp.
                      assert (Ceq : ((p_wire p - (2 * N + 3 * N * N)) / N =? (p_wire p - (2 * N + 3 * N * N)) mod N) = false)
                        by (apply Nat.eqb_neq; apply Nat.ltb_lt in C1; lia).
                      rewrite Ceq.
                      destruct (Nat.ltb u v) eqn:Euv.
                      ** assert (Hq1' : (p_wire p - (2 * N + 3 * N * N)) / N = u) by exact Hq1.
                         assert (Hq2' : (p_wire p - (2 * N + 3 * N * N)) mod N = v) by exact Hq2.
                         rewrite Hq1', Hq2', HuO. reflexivity.
                      ** assert (Hq1' : (p_wire p - (2 * N + 3 * N * N)) / N = v) by exact Hq1.
                         assert (Hq2' : (p_wire p - (2 * N + 3 * N * N)) mod N = u) by exact Hq2.
                         rewrite Hq1', Hq2', HvO, HuO. reflexivity.
                   ++ destruct (Nat.ltb ((p_wire p - (2 * N + 3 * N * N)) mod N) ((p_wire p - (2 * N + 3 * N * N)) / N)) eqn:C2; [|discriminate].
                      inversion Hwp as [[Hq1 Hq2]]; clear Hwp.
                      assert (Ceq : ((p_wire p - (2 * N + 3 * N * N)) / N =? (p_wire p - (2 * N + 3 * N * N)) mod N) = false)
                        by (apply Nat.eqb_neq; apply Nat.ltb_lt in C2; lia).
                      rewrite Ceq.
                      destruct (Nat.ltb u v) eqn:Euv.
                      ** assert (Hq1' : (p_wire p - (2 * N + 3 * N * N)) mod N = u) by exact Hq1.
                         assert (Hq2' : (p_wire p - (2 * N + 3 * N * N)) / N = v) by exact Hq2.
                         rewrite Hq1', Hq2', HvO, HuO. reflexivity.
                      ** assert (Hq1' : (p_wire p - (2 * N + 3 * N * N)) mod N = v) by exact Hq1.
                         assert (Hq2' : (p_wire p - (2 * N + 3 * N * N)) / N = u) by exact Hq2.
                         rewrite Hq1', Hq2', HuO. reflexivity.
            + apply Nat.ltb_ge in L3.
              assert (M1 : (p_wire p <? 2 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (M2 : (p_wire p <? 2 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; lia).
              rewrite M1, M2 in Hwp. discriminate. }
        split; [rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
              |rewrite (dom_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity]. }
    destruct Hu_cov as [Hu0 Hu1]. destruct Hv_cov as [Hv0 Hv1].
    split; [apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hu | exact Hu0]|].
    split; [apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hu | exact Hu1]|].
    split; [apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hv | exact Hv0]|].
    apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hv | exact Hv1]. }
  assert (Hout_eq : forall k tape, ProofSupport.Member tape (bitvectors (N * N)) ->
    k < N -> OutOrB k = true ->
    forall j, j < N ->
      xorb (andb (b 0 k) (b 1 j)) (dom_rbit N (zip_xorb tape (map_over df (upto (N * N)))) k j) =
      xorb (andb (a 0 k) (a 1 j)) (dom_rbit N tape k j)).
  { intros k tape Htape Hk HkO j Hj.
    destruct (Nat.eq_dec k j) as [<-|Hne].
    - repeat rewrite dom_rbit_diag.
      assert (Hk_cov : orb (dom_pini_shares n ps B 0 k) (B k) = true /\
                       orb (dom_pini_shares n ps B 1 k) (B k) = true).
      { unfold OutOrB in HkO. apply orb_prop in HkO. destruct HkO as [HBk | Hpk].
        - rewrite HBk. split; destruct (dom_pini_shares n ps B 0 k); destruct (dom_pini_shares n ps B 1 k); reflexivity.
        - destruct (dom_out_probed_inv n ps k Hpk) as [p [Hp Hpw]].
          assert (Hc : dom_pini_contrib n ps B p = (Some k, Some k)).
          { unfold dom_pini_contrib. rewrite Hpw. unfold dom_out_wire. change (S n) with N.
            destruct (Nat.ltb (2 * N + 4 * N * N + k) N) eqn:L1; [apply Nat.ltb_lt in L1; lia|].
            destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N)) eqn:L2; [apply Nat.ltb_lt in L2; lia|].
            destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N + N * N)) eqn:L3; [apply Nat.ltb_lt in L3; lia|].
            destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N + 4 * N * N)) eqn:L4; [apply Nat.ltb_lt in L4; lia|].
            replace (2 * N + 4 * N * N + k - (2 * N + 4 * N * N)) with k by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
            reflexivity. }
          split; [rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
                |rewrite (dom_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity]. }
      destruct Hk_cov as [Hc0 Hc1].
      rewrite (Hagree 0 k eq_refl ltac:(apply Nat.ltb_lt; exact Hk) Hc0).
      rewrite (Hagree 1 k eq_refl ltac:(apply Nat.ltb_lt; exact Hk) Hc1).
      reflexivity.
    - unfold dom_rbit. assert (Ekj : Nat.eqb k j = false) by (apply Nat.eqb_neq; exact Hne).
      rewrite Ekj. pose proof (dom_pair_idx_lt N k j Hk Hj) as Hidx_lt.
      rewrite bit_at_zip_xorb; [|exact Htape].
      assert (Hilt : (dom_pair_idx N k j <? N * N) = true) by (apply Nat.ltb_lt; exact Hidx_lt).
      rewrite Hilt.
      unfold dom_pair_idx. destruct (Nat.ltb k j) eqn:Lkj.
      + destruct (div_mod_pair_id N k j Hk Hj) as [Hd Hm].
        destruct (orb (OutOrB j) (dom_two_dom_probed n ps k j)) eqn:Hor.
        * pose proof (Hagree_pair k j Hk Hj Hne HkO ltac:(rewrite Lkj; exact Hor)) as [Ha0 [Ha1 [Hb0 Hb1]]].
          assert (Hdf : df (k * N + j) = false).
          { unfold df, dom_sim_df. cbv zeta. change (S n) with N.
            rewrite (Hextra k j Hk Hj ltac:(apply Nat.ltb_lt; exact Lkj) ltac:(left; exact HkO)), gf2_add_zero_r.
            rewrite Hd, Hm, Lkj.
            apply orb_prop in Hor. destruct Hor as [HjO | Htd].
            - unfold OutOrB in HkO, HjO. rewrite HjO, HkO. destruct (dom_two_dom_probed n ps k j); reflexivity.
            - rewrite Htd. rewrite !andb_false_r. destruct (orb (B j) (dom_out_probed n ps j)); reflexivity. }
          rewrite Hdf, gf2_add_zero_r, Ha0, Hb1. reflexivity.
        * apply orb_false_elim in Hor. destruct Hor as [HjO Htd].
          assert (Hk0 : a 0 k = b 0 k).
          { apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hk|].
            unfold union_shares. unfold OutOrB in HkO. apply orb_prop in HkO. destruct HkO as [HBk | Hpk].
            - rewrite HBk. destruct (dom_pini_shares n ps B 0 k); reflexivity.
            - destruct (dom_out_probed_inv n ps k Hpk) as [p [Hp Hpw]].
              assert (Hc : dom_pini_contrib n ps B p = (Some k, Some k)).
              { unfold dom_pini_contrib. rewrite Hpw. unfold dom_out_wire. change (S n) with N.
                destruct (Nat.ltb (2 * N + 4 * N * N + k) N) eqn:L1; [apply Nat.ltb_lt in L1; lia|].
                destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N)) eqn:L2; [apply Nat.ltb_lt in L2; lia|].
                destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N + N * N)) eqn:L3; [apply Nat.ltb_lt in L3; lia|].
                destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N + 4 * N * N)) eqn:L4; [apply Nat.ltb_lt in L4; lia|].
                replace (2 * N + 4 * N * N + k - (2 * N + 4 * N * N)) with k by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
                reflexivity. }
              rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity. }
          assert (Hdf : df (k * N + j) = xorb (andb (a 0 k) (a 1 j)) (andb (b 0 k) (b 1 j))).
          { unfold df, dom_sim_df. cbv zeta. change (S n) with N.
            rewrite (Hextra k j Hk Hj ltac:(apply Nat.ltb_lt; exact Lkj) ltac:(left; exact HkO)), gf2_add_zero_r.
            unfold OutOrB in HkO, HjO. rewrite Hd, Hm, Lkj, HkO, HjO, Htd. reflexivity. }
          rewrite Hdf.
          destruct (a 0 k); destruct (a 1 j); destruct (b 0 k); destruct (b 1 j); destruct (bit_at tape (k * N + j));
            try discriminate Hk0; reflexivity.
      + assert (Hjk : j < k) by (apply Nat.ltb_ge in Lkj; lia).
        assert (Ljk : (j <? k) = true) by (apply Nat.ltb_lt; exact Hjk).
        destruct (div_mod_pair_id N j k Hj Hk) as [Hd Hm].
        destruct (orb (OutOrB j) (dom_two_dom_probed n ps j k)) eqn:Hor.
        * assert (Lkj_c : (if Nat.ltb k j then k else j) = j /\ (if Nat.ltb k j then j else k) = k)
            by (rewrite Lkj; split; reflexivity).
          pose proof (Hagree_pair k j Hk Hj Hne HkO ltac:(rewrite Lkj; exact Hor)) as [Ha0 [Ha1 [Hb0 Hb1]]].
          assert (Hdf : df (j * N + k) = false).
          { unfold df, dom_sim_df. cbv zeta. change (S n) with N.
            rewrite (Hextra j k Hj Hk Hjk ltac:(right; left; exact HkO)), gf2_add_zero_r.
            rewrite Hd, Hm, Ljk.
            apply orb_prop in Hor. destruct Hor as [HjO | Htd].
            - unfold OutOrB in HkO, HjO. rewrite HjO, HkO. destruct (dom_two_dom_probed n ps j k); reflexivity.
            - rewrite Htd. rewrite !andb_false_r. destruct (orb (B j) (dom_out_probed n ps j)); reflexivity. }
          rewrite Hdf, gf2_add_zero_r, Ha0, Hb1. reflexivity.
        * apply orb_false_elim in Hor. destruct Hor as [HjO Htd].
          assert (Hk0 : a 0 k = b 0 k).
          { apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hk|].
            unfold union_shares. unfold OutOrB in HkO. apply orb_prop in HkO. destruct HkO as [HBk | Hpk].
            - rewrite HBk. destruct (dom_pini_shares n ps B 0 k); reflexivity.
            - destruct (dom_out_probed_inv n ps k Hpk) as [p [Hp Hpw]].
              assert (Hc : dom_pini_contrib n ps B p = (Some k, Some k)).
              { unfold dom_pini_contrib. rewrite Hpw. unfold dom_out_wire. change (S n) with N.
                destruct (Nat.ltb (2 * N + 4 * N * N + k) N) eqn:L1; [apply Nat.ltb_lt in L1; lia|].
                destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N)) eqn:L2; [apply Nat.ltb_lt in L2; lia|].
                destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N + N * N)) eqn:L3; [apply Nat.ltb_lt in L3; lia|].
                destruct (Nat.ltb (2 * N + 4 * N * N + k) (2 * N + 4 * N * N)) eqn:L4; [apply Nat.ltb_lt in L4; lia|].
                replace (2 * N + 4 * N * N + k - (2 * N + 4 * N * N)) with k by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
                reflexivity. }
              rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity. }
          assert (Hdf : df (j * N + k) = xorb (andb (a 0 k) (a 1 j)) (andb (b 0 k) (b 1 j))).
          { unfold df, dom_sim_df. cbv zeta. change (S n) with N.
            rewrite (Hextra j k Hj Hk Hjk ltac:(right; left; exact HkO)), gf2_add_zero_r.
            unfold OutOrB in HkO, HjO. rewrite Hd, Hm, Ljk, HkO, HjO, Htd. reflexivity. }
          rewrite Hdf.
          destruct (a 0 k); destruct (a 1 j); destruct (b 0 k); destruct (b 1 j); destruct (bit_at tape (j * N + k));
            try discriminate Hk0; reflexivity. }
  intros tape Htape. split.
  - unfold internal_view, probe_set. apply support_map_ext. intros o Ho.
    apply member_flat_map_over_inv in Ho. destruct Ho as [p [Hp Ho]].
    assert (Hpw_lt : p_wire p < dom_wire_count n).
    { clear -Hw Hp. unfold wires_exist in Hw.
      induction ps as [|q r IH]; simpl in *; [contradiction|].
      apply andb_prop in Hw. destruct Hw as [Hq Hr].
      destruct Hp as [->|Hp]; [apply Nat.ltb_lt in Hq; rewrite circuit_of_fun_count in Hq; exact Hq | exact (IH Hr Hp)]. }
    assert (Hobs_at : forall s cyc,
      ProofSupport.Member s (stable_sources (circuit_of_fun (dom_wire_count n) (dom_gate n)) (dom_wire_count n) (p_wire p)) ->
      gd_value (dom_and_gadget n) b (zip_xorb tape (map_over df (upto (N * N)))) cyc s =
      gd_value (dom_and_gadget n) a tape cyc s).
    { intros s cyc Hs.
      rewrite dom_stable_sources in Hs; [|exact Hpw_lt]. cbv zeta in Hs. change (S n) with N in Hs.
      assert (Hs_lt : s < dom_wire_count n).
      { unfold dom_wire_count. change (S n) with N.
        destruct (Nat.ltb (p_wire p) (2 * N + N * N)) eqn:E1; [apply Nat.ltb_lt in E1; cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s; lia|].
        apply Nat.ltb_ge in E1.
        destruct (Nat.ltb (p_wire p) (2 * N + 2 * N * N)) eqn:E2.
        - apply Nat.ltb_lt in E2.
          destruct (div_mod_pair_bound N (p_wire p - (2 * N + N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
          cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[Hseq|[]]]; subst s; lia.
        - apply Nat.ltb_ge in E2.
          destruct (Nat.ltb (p_wire p) (2 * N + 3 * N * N)) eqn:E3.
          + apply Nat.ltb_lt in E3.
            destruct (div_mod_pair_bound N (p_wire p - (2 * N + 2 * N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
            pose proof (dom_pair_idx_lt N _ _ Hi Hj) as Hpr.
            destruct (Nat.eqb _ _); cbn [ProofSupport.Member] in Hs; [destruct Hs as [Hseq|[Hseq|[]]]; subst s; lia | destruct Hs as [Hseq|[Hseq|[Hseq|[]]]]; subst s; lia].
          + destruct (Nat.ltb (p_wire p) (2 * N + 4 * N * N)) eqn:E4.
            * cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s; exact Hpw_lt.
            * apply Nat.ltb_ge in E4.
              assert (Hex_j : exists j, j < N /\ s = 2 * N + 3 * N * N + (p_wire p - (2 * N + 4 * N * N)) * N + j).
              { destruct (member_map_over_inv _ _ _ Hs) as [j [Hj Heq]].
                exists j. split; [apply member_upto_lt; exact Hj | symmetry; exact Heq]. }
              destruct Hex_j as [j [Hj ->]]. unfold dom_wire_count in Hpw_lt. nia. }
      repeat (rewrite dom_value_eq; [|exact Hs_lt]).
      assert (Hpair_ok : forall i j, i < N -> j < N ->
        ((p_wire p < 2 * N + 4 * N * N /\
          ((i = j /\ dom_pini_contrib n ps B p = (Some i, Some i)) \/
           (i <> j /\ dom_wire_pair n (p_wire p) = Some (if Nat.ltb i j then i else j, if Nat.ltb i j then j else i) /\
            (dom_pini_contrib n ps B p = (Some i, Some j) \/
             (OutOrB i = true /\ dom_pini_contrib n ps B p = (Some j, Some j)) \/
             (OutOrB j = true /\ dom_pini_contrib n ps B p = (Some i, Some i)))))) ->
        a 0 i = b 0 i /\ a 1 j = b 1 j)).
      { intros i j Hi Hj [_ Hc].
        assert (Hcov_out : forall idx, idx < N -> OutOrB idx = true ->
          orb (dom_pini_shares n ps B 0 idx) (B idx) = true /\
          orb (dom_pini_shares n ps B 1 idx) (B idx) = true).
        { intros idx Hidx HO. unfold OutOrB in HO. apply orb_prop in HO. destruct HO as [HB | Hpr].
          - rewrite HB. split; destruct (dom_pini_shares n ps B 0 idx); destruct (dom_pini_shares n ps B 1 idx); reflexivity.
          - destruct (dom_out_probed_inv n ps idx Hpr) as [q [Hq Hqw]].
            assert (Hcq : dom_pini_contrib n ps B q = (Some idx, Some idx)).
            { unfold dom_pini_contrib. rewrite Hqw. unfold dom_out_wire. change (S n) with N.
              destruct (Nat.ltb (2 * N + 4 * N * N + idx) N) eqn:L1; [apply Nat.ltb_lt in L1; lia|].
              destruct (Nat.ltb (2 * N + 4 * N * N + idx) (2 * N)) eqn:L2; [apply Nat.ltb_lt in L2; lia|].
              destruct (Nat.ltb (2 * N + 4 * N * N + idx) (2 * N + N * N)) eqn:L3; [apply Nat.ltb_lt in L3; lia|].
              destruct (Nat.ltb (2 * N + 4 * N * N + idx) (2 * N + 4 * N * N)) eqn:L4; [apply Nat.ltb_lt in L4; lia|].
              replace (2 * N + 4 * N * N + idx - (2 * N + 4 * N * N)) with idx by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
              reflexivity. }
            split; [rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hq Hcq); reflexivity
                  |rewrite (dom_pini_shares_hit1 _ _ _ _ _ _ Hq Hcq); reflexivity]. }
        destruct Hc as [[-> Hc] | [Hne [Hwp Hdisj]]].
        - split; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hj |
            unfold union_shares; rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
          | reflexivity | apply Nat.ltb_lt; exact Hj |
            unfold union_shares; rewrite (dom_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity].
        - destruct Hdisj as [Hc | [[HO Hc] | [HO Hc]]].
          + split; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hi |
              unfold union_shares; rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
            | reflexivity | apply Nat.ltb_lt; exact Hj |
              unfold union_shares; rewrite (dom_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity].
          + destruct (Hcov_out i Hi HO) as [Hi0 _].
            split; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hi | exact Hi0
            | reflexivity | apply Nat.ltb_lt; exact Hj |
              unfold union_shares; rewrite (dom_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity].
          + destruct (Hcov_out j Hj HO) as [_ Hj1].
            split; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hi |
              unfold union_shares; rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
            | reflexivity | apply Nat.ltb_lt; exact Hj | exact Hj1]. }
      destruct (Nat.ltb (p_wire p) N) eqn:W0.
      + assert (Hw0 : p_wire p < N) by (apply Nat.ltb_lt; exact W0).
        assert (W1 : (p_wire p <? 2 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
        rewrite W1 in Hs. cbn [ProofSupport.Member] in Hs. destruct Hs as [Hseq|[]]; subst s.
        unfold dom_eval; change (S n) with N; rewrite W0.
        symmetry; apply Hagree; [reflexivity | exact W0|].
        assert (Hc : dom_pini_contrib n ps B p = (Some (p_wire p), None))
          by (unfold dom_pini_contrib; change (S n) with N; rewrite W0; reflexivity).
        unfold union_shares; rewrite (dom_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity.
      + destruct (Nat.ltb (p_wire p) (2 * N)) eqn:W1.
        * assert (Hw1 : p_wire p < 2 * N) by (apply Nat.ltb_lt; exact W1).
          assert (W1' : (p_wire p <? 2 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
          rewrite W1' in Hs. cbn [ProofSupport.Member] in Hs. destruct Hs as [Hseq|[]]; subst s.
          unfold dom_eval; change (S n) with N; rewrite W0, W1.
          symmetry; apply Hagree; [reflexivity | unfold dom_and_gadget; cbn [gd_shares]; apply Nat.ltb_lt; apply Nat.ltb_ge in W0; unfold N in *; lia|].
          assert (Hc : dom_pini_contrib n ps B p = (None, Some (p_wire p - N)))
            by (unfold dom_pini_contrib; change (S n) with N; rewrite W0, W1; reflexivity).
          unfold union_shares; rewrite (dom_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity.
        * destruct (Nat.ltb (p_wire p) (2 * N + N * N)) eqn:W2.
          -- cbn [ProofSupport.Member] in Hs. destruct Hs as [Hseq|[]]; subst s.
             assert (Hr_lt : p_wire p - 2 * N < N * N) by (apply Nat.ltb_lt in W2; apply Nat.ltb_ge in W1; lia).
             destruct (div_mod_pair_bound N (p_wire p - 2 * N) ltac:(lia) Hr_lt) as [Hu [Hv Hdm]].
             unfold dom_eval; change (S n) with N; rewrite W0, W1, W2.
             rewrite bit_at_zip_xorb; [|exact Htape].
             assert (Hr_b : (p_wire p - 2 * N <? N * N) = true) by (apply Nat.ltb_lt; exact Hr_lt).
             rewrite Hr_b.
             assert (Hdf_zero : df (p_wire p - 2 * N) = false).
             { unfold df, dom_sim_df. cbv zeta. change (S n) with N.
               destruct (Nat.ltb ((p_wire p - 2 * N) / N) ((p_wire p - 2 * N) mod N)) eqn:Luv.
               - assert (Hwp : dom_wire_pair n (p_wire p) = Some ((p_wire p - 2 * N) / N, (p_wire p - 2 * N) mod N)).
                 { rewrite dom_wire_pair_spec; [|exact Hpw_lt]. cbv zeta; change (S n) with N.
                   rewrite W1, W2, Luv. reflexivity. }
                 pose proof (dom_two_dom_probed_member n ps _ _ p Hp Hwp) as Htd.
                 assert (Hdf_e : df_extra (p_wire p - 2 * N) = false)
                   by (rewrite <- Hdm; apply (Hextra _ _ Hu Hv ltac:(apply Nat.ltb_lt; exact Luv) ltac:(right; right; exact Htd))).
                 rewrite Hdf_e, gf2_add_zero_r, Htd, !andb_false_r.
                 destruct (orb (B ((p_wire p - 2 * N) / N)) (dom_out_probed n ps ((p_wire p - 2 * N) / N)));
                 destruct (orb (B ((p_wire p - 2 * N) mod N)) (dom_out_probed n ps ((p_wire p - 2 * N) mod N))); reflexivity.
               - rewrite (Hextra_ge (p_wire p - 2 * N) Hr_lt Luv). reflexivity. }
             rewrite Hdf_zero, gf2_add_zero_r. reflexivity.
          -- apply Nat.ltb_ge in W2.
             assert (Hprop_c : forall i j, i < N -> j < N -> p_wire p < 2 * N + 4 * N * N ->
               (p_wire p - (2 * N + N * N)) mod (N * N) = i * N + j ->
               a 0 i = b 0 i /\ a 1 j = b 1 j /\
               (i <> j -> df (dom_pair_idx N i j) = false)).
             { intros i j Hi Hj Hlt4 Hmod.
               destruct (div_mod_pair_id N i j Hi Hj) as [Hdi Hdj].
               assert (Hpair_ok_ij : a 0 i = b 0 i /\ a 1 j = b 1 j).
               { apply (Hpair_ok i j Hi Hj). split; [exact Hlt4|].
                 destruct (Nat.eq_dec i j) as [->|Hne].
                 - left; split; [reflexivity|].
                   unfold dom_pini_contrib; change (S n) with N.
                   assert (L1 : (p_wire p <? N) = false) by (apply Nat.ltb_ge; lia).
                   assert (L2 : (p_wire p <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (L3 : (p_wire p <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (L4 : (p_wire p <? 2 * N + 4 * N * N) = true) by (apply Nat.ltb_lt; exact Hlt4).
                   rewrite L1, L2, L3, L4, Hmod, Hdi, Hdj, eqb_refl_nat. reflexivity.
                 - right; split; [exact Hne|].
                   assert (Hwp : dom_wire_pair n (p_wire p) = Some (if Nat.ltb i j then i else j, if Nat.ltb i j then j else i)).
                   { unfold dom_wire_pair; cbv zeta; change (S n) with N.
                     rewrite W1.
                     assert (L3 : (p_wire p <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                     assert (L4 : (p_wire p <? 2 * N + 4 * N * N) = true) by (apply Nat.ltb_lt; exact Hlt4).
                     rewrite L3, L4, Hmod, Hdi, Hdj.
                     destruct (Nat.ltb i j) eqn:Lij; [reflexivity|].
                     assert (Lji : (j <? i) = true) by (apply Nat.ltb_ge in Lij; apply Nat.ltb_lt; lia).
                     rewrite Lji. reflexivity. }
                   split; [exact Hwp|].
                   unfold dom_pini_contrib; change (S n) with N.
                   assert (L1 : (p_wire p <? N) = false) by (apply Nat.ltb_ge; lia).
                   assert (L2 : (p_wire p <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (L3 : (p_wire p <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (L4 : (p_wire p <? 2 * N + 4 * N * N) = true) by (apply Nat.ltb_lt; exact Hlt4).
                   rewrite L1, L2, L3, L4, Hmod, Hdi, Hdj.
                   assert (Eij : (i =? j) = false) by (apply Nat.eqb_neq; exact Hne).
                   rewrite Eij.
                   destruct (OutOrB i) eqn:HOi; [right; left; split; [reflexivity | unfold OutOrB in HOi; rewrite HOi; reflexivity]|].
                   destruct (OutOrB j) eqn:HOj; [right; right; split; [reflexivity | unfold OutOrB in HOi, HOj; rewrite HOi, HOj; reflexivity]|].
                   unfold OutOrB in HOi, HOj; rewrite HOi, HOj; left; reflexivity. }
               destruct Hpair_ok_ij as [Ha0 Hb1]. split; [exact Ha0|]; split; [exact Hb1|].
               intros Hne.
               assert (Hwp : dom_wire_pair n (p_wire p) = Some (if Nat.ltb i j then i else j, if Nat.ltb i j then j else i)).
               { unfold dom_wire_pair; cbv zeta; change (S n) with N.
                 rewrite W1.
                 assert (L3 : (p_wire p <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                 assert (L4 : (p_wire p <? 2 * N + 4 * N * N) = true) by (apply Nat.ltb_lt; exact Hlt4).
                 rewrite L3, L4, Hmod, Hdi, Hdj.
                 destruct (Nat.ltb i j) eqn:Lij; [reflexivity|].
                 assert (Lji : (j <? i) = true) by (apply Nat.ltb_ge in Lij; apply Nat.ltb_lt; lia).
                 rewrite Lji. reflexivity. }
               pose proof (dom_two_dom_probed_member n ps _ _ p Hp Hwp) as Htd.
               unfold df, dom_sim_df, dom_pair_idx. cbv zeta. change (S n) with N.
               destruct (Nat.ltb i j) eqn:Lij.
               - rewrite (Hextra i j Hi Hj ltac:(apply Nat.ltb_lt; exact Lij) ltac:(right; right; exact Htd)), gf2_add_zero_r.
                 destruct (div_mod_pair_id N i j Hi Hj) as [Hd2 Hm2]. rewrite Hd2, Hm2, Lij, Htd, !andb_false_r.
                 destruct (orb (B i) (dom_out_probed n ps i)); destruct (orb (B j) (dom_out_probed n ps j)); reflexivity.
               - assert (Hji : j < i) by (apply Nat.ltb_ge in Lij; lia).
                 assert (Lji : (j <? i) = true) by (apply Nat.ltb_lt; exact Hji).
                 rewrite (Hextra j i Hj Hi Hji ltac:(right; right; exact Htd)), gf2_add_zero_r.
                 destruct (div_mod_pair_id N j i Hj Hi) as [Hd2 Hm2]. rewrite Hd2, Hm2, Lji, Htd, !andb_false_r.
                 destruct (orb (B j) (dom_out_probed n ps j)); destruct (orb (B i) (dom_out_probed n ps i)); reflexivity. }
             destruct (Nat.ltb (p_wire p) (2 * N + 2 * N * N)) eqn:W3.
             ++ apply Nat.ltb_lt in W3.
                assert (Hp_lt : p_wire p - (2 * N + N * N) < N * N) by lia.
                destruct (div_mod_pair_bound N (p_wire p - (2 * N + N * N)) ltac:(lia) Hp_lt) as [Hi [Hj Hdm]].
                assert (Hmod : (p_wire p - (2 * N + N * N)) mod (N * N) =
                               ((p_wire p - (2 * N + N * N)) / N) * N + ((p_wire p - (2 * N + N * N)) mod N))
                  by (rewrite Nat.mod_small; [symmetry; exact Hdm | exact Hp_lt]).
                destruct (Hprop_c _ _ Hi Hj ltac:(lia) Hmod) as [Ha0 [Hb1 _]].
                assert (W3b : (p_wire p <? 2 * N + 2 * N * N) = true) by (apply Nat.ltb_lt; exact W3).
                cbn [ProofSupport.Member] in Hs.
                destruct Hs as [Hseq|[Hseq|[]]]; subst s; unfold dom_eval; change (S n) with N.
                ** destruct (Nat.ltb ((p_wire p - (2 * N + N * N)) / N) N) eqn:L1; [|apply Nat.ltb_ge in L1; lia].
                   symmetry; exact Ha0.
                ** destruct (Nat.ltb (N + (p_wire p - (2 * N + N * N)) mod N) N) eqn:L1; [apply Nat.ltb_lt in L1; lia|].
                   destruct (Nat.ltb (N + (p_wire p - (2 * N + N * N)) mod N) (2 * N)) eqn:L2; [|apply Nat.ltb_ge in L2; lia].
                   replace (N + (p_wire p - (2 * N + N * N)) mod N - N) with ((p_wire p - (2 * N + N * N)) mod N) by lia.
                   symmetry; exact Hb1.
             ++ apply Nat.ltb_ge in W3.
                destruct (Nat.ltb (p_wire p) (2 * N + 3 * N * N)) eqn:W4.
                ** apply Nat.ltb_lt in W4.
                   assert (Hp_lt : p_wire p - (2 * N + 2 * N * N) < N * N) by lia.
                   destruct (div_mod_pair_bound N (p_wire p - (2 * N + 2 * N * N)) ltac:(lia) Hp_lt) as [Hi [Hj Hdm]].
                   assert (Hmod : (p_wire p - (2 * N + N * N)) mod (N * N) =
                                  ((p_wire p - (2 * N + 2 * N * N)) / N) * N + ((p_wire p - (2 * N + 2 * N * N)) mod N)).
                   { replace (p_wire p - (2 * N + N * N)) with ((p_wire p - (2 * N + 2 * N * N)) + 1 * (N * N)) by lia.
                     rewrite Nat.Div0.mod_add, Nat.mod_small; [symmetry; exact Hdm | exact Hp_lt]. }
                   destruct (Hprop_c _ _ Hi Hj ltac:(lia) Hmod) as [Ha0 [Hb1 Hdfz]].
                   destruct (Nat.eqb ((p_wire p - (2 * N + 2 * N * N)) / N) ((p_wire p - (2 * N + 2 * N * N)) mod N)) eqn:Eij.
                   --- cbn [ProofSupport.Member] in Hs. destruct Hs as [Hseq|[Hseq|[]]]; subst s; unfold dom_eval; change (S n) with N.
                       +++ destruct (Nat.ltb ((p_wire p - (2 * N + 2 * N * N)) / N) N) eqn:L1; [|apply Nat.ltb_ge in L1; lia].
                           symmetry; exact Ha0.
                       +++ destruct (Nat.ltb (N + (p_wire p - (2 * N + 2 * N * N)) mod N) N) eqn:L1; [apply Nat.ltb_lt in L1; lia|].
                           destruct (Nat.ltb (N + (p_wire p - (2 * N + 2 * N * N)) mod N) (2 * N)) eqn:L2; [|apply Nat.ltb_ge in L2; lia].
                           replace (N + (p_wire p - (2 * N + 2 * N * N)) mod N - N) with ((p_wire p - (2 * N + 2 * N * N)) mod N) by lia.
                           symmetry; exact Hb1.
                   --- assert (Hne : (p_wire p - (2 * N + 2 * N * N)) / N <> (p_wire p - (2 * N + 2 * N * N)) mod N)
                         by (apply Nat.eqb_neq; exact Eij).
                       specialize (Hdfz Hne). cbn [ProofSupport.Member] in Hs.
                       destruct Hs as [Hseq|[Hseq|[Hseq|[]]]]; subst s; unfold dom_eval; change (S n) with N.
                       +++ destruct (Nat.ltb ((p_wire p - (2 * N + 2 * N * N)) / N) N) eqn:L1; [|apply Nat.ltb_ge in L1; lia].
                           symmetry; exact Ha0.
                       +++ destruct (Nat.ltb (N + (p_wire p - (2 * N + 2 * N * N)) mod N) N) eqn:L1; [apply Nat.ltb_lt in L1; lia|].
                           destruct (Nat.ltb (N + (p_wire p - (2 * N + 2 * N * N)) mod N) (2 * N)) eqn:L2; [|apply Nat.ltb_ge in L2; lia].
                           replace (N + (p_wire p - (2 * N + 2 * N * N)) mod N - N) with ((p_wire p - (2 * N + 2 * N * N)) mod N) by lia.
                           symmetry; exact Hb1.
                       +++ pose proof (dom_pair_idx_lt N _ _ Hi Hj) as Hpr.
                           destruct (Nat.ltb (2 * N + dom_pair_idx N ((p_wire p - (2 * N + 2 * N * N)) / N) ((p_wire p - (2 * N + 2 * N * N)) mod N)) N) eqn:L1;
                             [apply Nat.ltb_lt in L1; lia|].
                           destruct (Nat.ltb (2 * N + dom_pair_idx N ((p_wire p - (2 * N + 2 * N * N)) / N) ((p_wire p - (2 * N + 2 * N * N)) mod N)) (2 * N)) eqn:L2;
                             [apply Nat.ltb_lt in L2; lia|].
                           destruct (Nat.ltb (2 * N + dom_pair_idx N ((p_wire p - (2 * N + 2 * N * N)) / N) ((p_wire p - (2 * N + 2 * N * N)) mod N)) (2 * N + N * N)) eqn:L3;
                             [|apply Nat.ltb_ge in L3; lia].
                           replace (2 * N + dom_pair_idx N ((p_wire p - (2 * N + 2 * N * N)) / N) ((p_wire p - (2 * N + 2 * N * N)) mod N) - 2 * N)
                             with (dom_pair_idx N ((p_wire p - (2 * N + 2 * N * N)) / N) ((p_wire p - (2 * N + 2 * N * N)) mod N)) by lia.
                           rewrite bit_at_zip_xorb; [|exact Htape].
                           assert (Lpr : (dom_pair_idx N ((p_wire p - (2 * N + 2 * N * N)) / N) ((p_wire p - (2 * N + 2 * N * N)) mod N) <? N * N) = true)
                             by (apply Nat.ltb_lt; exact Hpr).
                           rewrite Lpr, Hdfz, gf2_add_zero_r. reflexivity.
                ** apply Nat.ltb_ge in W4.
                   destruct (Nat.ltb (p_wire p) (2 * N + 4 * N * N)) eqn:W5.
                   --- apply Nat.ltb_lt in W5.
                       assert (Hp_lt : p_wire p - (2 * N + 3 * N * N) < N * N) by lia.
                       destruct (div_mod_pair_bound N (p_wire p - (2 * N + 3 * N * N)) ltac:(lia) Hp_lt) as [Hi [Hj Hdm]].
                       assert (Hmod : (p_wire p - (2 * N + N * N)) mod (N * N) =
                                      ((p_wire p - (2 * N + 3 * N * N)) / N) * N + ((p_wire p - (2 * N + 3 * N * N)) mod N)).
                       { replace (p_wire p - (2 * N + N * N)) with ((p_wire p - (2 * N + 3 * N * N)) + 2 * (N * N)) by lia.
                         rewrite Nat.Div0.mod_add, Nat.mod_small; [symmetry; exact Hdm | exact Hp_lt]. }
                       destruct (Hprop_c _ _ Hi Hj ltac:(lia) Hmod) as [Ha0 [Hb1 Hdfz]].
                       assert (W5b : (p_wire p <? 2 * N + 4 * N * N) = true) by (apply Nat.ltb_lt; exact W5).
                       cbn [ProofSupport.Member] in Hs. destruct Hs as [Hseq|[]]; subst s.
                       unfold dom_eval; change (S n) with N.
                       destruct (Nat.ltb (p_wire p) N) eqn:L0; [apply Nat.ltb_lt in L0; lia|].
                       destruct (Nat.ltb (p_wire p) (2 * N)) eqn:L1; [apply Nat.ltb_lt in L1; lia|].
                       destruct (Nat.ltb (p_wire p) (2 * N + N * N)) eqn:L2; [apply Nat.ltb_lt in L2; lia|].
                       destruct (Nat.ltb (p_wire p) (2 * N + 2 * N * N)) eqn:L3; [apply Nat.ltb_lt in L3; lia|].
                       destruct (Nat.ltb (p_wire p) (2 * N + 3 * N * N)) eqn:L4; [apply Nat.ltb_lt in L4; lia|].
                       rewrite W5b.
                       destruct cyc as [|cyc]; [reflexivity|].
                       destruct (Nat.eq_dec ((p_wire p - (2 * N + 3 * N * N)) / N) ((p_wire p - (2 * N + 3 * N * N)) mod N)) as [Heq | Hne].
                       +++ rewrite Ha0, Hb1, <- Heq. repeat rewrite dom_rbit_diag. reflexivity.
                       +++ specialize (Hdfz Hne). unfold dom_rbit.
                           assert (Ene : ((p_wire p - (2 * N + 3 * N * N)) / N =? (p_wire p - (2 * N + 3 * N * N)) mod N) = false)
                             by (apply Nat.eqb_neq; exact Hne).
                           rewrite Ene, bit_at_zip_xorb; [|exact Htape].
                           pose proof (dom_pair_idx_lt N _ _ Hi Hj) as Hpr.
                           assert (Lpr : (dom_pair_idx N ((p_wire p - (2 * N + 3 * N * N)) / N) ((p_wire p - (2 * N + 3 * N * N)) mod N) <? N * N) = true)
                             by (apply Nat.ltb_lt; exact Hpr).
                           rewrite Lpr, Hdfz, gf2_add_zero_r, Ha0, Hb1. reflexivity.
                   --- apply Nat.ltb_ge in W5.
                       set (i := p_wire p - (2 * N + 4 * N * N)) in *.
                       assert (Hi_lt : i < N) by (unfold dom_wire_count in Hpw_lt; unfold i; lia).
                       assert (HOi : OutOrB i = true).
                       { unfold OutOrB. rewrite (dom_out_probed_member n ps i p Hp).
                         - destruct (B i); reflexivity.
                         - unfold dom_out_wire. change (S n) with N. unfold i. lia. }
                       destruct (member_map_over_inv _ _ _ Hs) as [j [Hj Hs_eq]].
                       apply member_upto_lt in Hj. subst s.
                       unfold dom_eval; change (S n) with N.
                       assert (R0 : (2 * N + 3 * N * N + i * N + j <? N) = false) by (apply Nat.ltb_ge; nia).
                       assert (R1 : (2 * N + 3 * N * N + i * N + j <? 2 * N) = false) by (apply Nat.ltb_ge; nia).
                       assert (R2 : (2 * N + 3 * N * N + i * N + j <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; nia).
                       assert (R3 : (2 * N + 3 * N * N + i * N + j <? 2 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; nia).
                       assert (R4 : (2 * N + 3 * N * N + i * N + j <? 2 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; nia).
                       assert (R5 : (2 * N + 3 * N * N + i * N + j <? 2 * N + 4 * N * N) = true) by (apply Nat.ltb_lt; nia).
                       rewrite R0, R1, R2, R3, R4, R5.
                       destruct cyc as [|cyc]; [reflexivity|].
                       replace (2 * N + 3 * N * N + i * N + j - (2 * N + 3 * N * N)) with (i * N + j) by lia.
                       destruct (div_mod_pair_id N i j Hi_lt Hj) as [Hd Hm].
                       rewrite Hd, Hm. exact (Hout_eq i tape Htape Hi_lt HOi j Hj). }
    unfold ex_robust, dom_and_gadget in Ho. cbn [gd_circuit] in Ho. rewrite circuit_of_fun_count in Ho.
    (* Check every element of ex_robust (obs_at s cyc / prev_cycle cyc). *)
    assert (Ho_cases : exists s, ProofSupport.Member s (stable_sources (circuit_of_fun (dom_wire_count n) (dom_gate n)) (dom_wire_count n) (p_wire p)) /\
      (o = obs_at s (p_cycle p) \/ o = obs_at s (prev_cycle (p_cycle p)))).
    { clear -Ho. induction (stable_sources (circuit_of_fun (dom_wire_count n) (dom_gate n)) (dom_wire_count n) (p_wire p)) as [|s r IH];
        cbn [flat_map_over] in Ho; [contradiction|].
      destruct Ho as [Ho1|[Ho2|Ho]]; [exists s; split; [left; reflexivity | left; first [exact Ho1 | symmetry; exact Ho1]]
        | exists s; split; [left; reflexivity | right; first [exact Ho2 | symmetry; exact Ho2]]
        | destruct (IH Ho) as [s0 [Hs0 Hdec]]; exists s0; split; [right; exact Hs0 | exact Hdec]]. }
    destruct Ho_cases as [s [Hs [->| ->]]]; simpl; apply Hobs_at; exact Hs.
  - intros k Hk HkO j Hj. exact (Hout_eq k tape Htape Hk HkO j Hj).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem dom_and_is_pini :
  forall n d, PINI (dom_and_gadget n) ex_robust d.
Proof.
  intros n d ps B Hw _.
  exists (dom_pini_shares n ps B). split; [apply dom_pini_shares_bounded|].
  intros a b Hagree.
  set (N := S n) in *.
  set (df := dom_sim_df n ps B a b (fun _ => false)).
  apply (bit_tapes_xor_hides (N * N) (list bool) (list_eqb bool_eqb)
           (split_view (dom_and_gadget n) ex_robust ps B a)
           (split_view (dom_and_gadget n) ex_robust ps B b) df).
  intros tape Htape.
  destruct (dom_and_sim_core n ps B a b (fun _ => false) Hw Hagree
              (fun _ _ _ => eq_refl) (fun _ _ _ _ _ _ => eq_refl) tape Htape) as [Hint Hout].
  unfold split_view. f_equal; [exact Hint|].
  unfold output_view, selected_outputs. apply support_map_ext. intros k Hk.
  change (gd_shares (dom_and_gadget n)) with N in Hk.
  pose proof (support_filter_true B (upto N) k Hk) as HBk.
  apply support_filter_member in Hk. apply member_upto_lt in Hk.
  assert (HOk : orb (B k) (dom_out_probed n ps k) = true) by (rewrite HBk; reflexivity).
  replace (gd_out (dom_and_gadget n) k) with (dom_out_wire n k) by reflexivity.
  rewrite (dom_value_eq n b); [|unfold dom_wire_count, dom_out_wire; unfold N in *; cbv zeta; lia].
  rewrite (dom_value_eq n a); [|unfold dom_wire_count, dom_out_wire; unfold N in *; cbv zeta; lia].
  unfold dom_eval, dom_out_wire. cbv zeta. change (S n) with N.
  assert (L0 : (2 * N + 4 * N * N + k <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L1 : (2 * N + 4 * N * N + k <? 2 * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L2 : (2 * N + 4 * N * N + k <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L3 : (2 * N + 4 * N * N + k <? 2 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L4 : (2 * N + 4 * N * N + k <? 2 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L5 : (2 * N + 4 * N * N + k <? 2 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  rewrite L0, L1, L2, L3, L4, L5.
  destruct (gd_read (dom_and_gadget n)) eqn:Hrd; [unfold dom_and_gadget in Hrd; cbn [gd_read] in Hrd; discriminate|].
  replace (2 * N + 4 * N * N + k - (2 * N + 4 * N * N)) with k by lia.
  apply xor_sum_upto_ext. intros j Hj. exact (Hout k Hk HOk j Hj).
Qed.

(* Arbitrary-order SNI for DOM-indep AND when split_size <= n < S n. *)
Definition dom_sni_shares (n : nat) (ps : list Probe) : ShareSet :=
  dom_pini_shares n ps (fun _ => false).

Definition dom_sni_probe_hit (n k : nat) (p : Probe) : option nat :=
  let N := S n in
  let w := p_wire p in
  if Nat.ltb w (2 * N) then None
  else if Nat.ltb w (2 * N + 4 * N * N) then
    match dom_wire_pair n w with
    | Some (u, v) =>
      if Nat.eqb u k then Some v else if Nat.eqb v k then Some u else None
    | None => None
    end
  else Some (w - (2 * N + 4 * N * N)).

Definition dom_sni_blocked (n : nat) (ps : list Probe) (B : nat -> bool) (k j : nat) : bool :=
  orb (B j) (any_of (fun p => match dom_sni_probe_hit n k p with Some z => Nat.eqb z j | None => false end) ps).

Definition dom_sni_target (n : nat) (ps : list Probe) (B : nat -> bool) (k : nat) : nat :=
  find_unblocked (S n) (dom_sni_blocked n ps B k).

Lemma dom_two_dom_probed_inv :
  forall n ps u v,
    dom_two_dom_probed n ps u v = true ->
    exists p, ProofSupport.Member p ps /\ dom_wire_pair n (p_wire p) = Some (u, v).
Proof.
  intros n ps u v Htd. unfold dom_two_dom_probed in Htd.
  induction ps as [|q r IH]; simpl in *; [discriminate|].
  destruct (dom_wire_pair n (p_wire q)) as [[x y]|] eqn:Eq.
  - destruct (andb (Nat.eqb x u) (Nat.eqb y v)) eqn:Exy.
    + apply andb_prop in Exy. destruct Exy as [Ex Ey].
      apply eqb_sound_nat in Ex; apply eqb_sound_nat in Ey; subst.
      exists q; split; [left; reflexivity | exact Eq].
    + simpl in Htd. destruct (IH Htd) as [p [Hp Hwp]]. exists p; split; [right; exact Hp | exact Hwp].
  - simpl in Htd. destruct (IH Htd) as [p [Hp Hwp]]. exists p; split; [right; exact Hp | exact Hwp].
Qed.

Lemma dom_sni_target_spec :
  forall n ps B k,
    Nat.leb (split_size (dom_and_gadget n) ps B) n = true ->
    B k = true ->
    let j := dom_sni_target n ps B k in
    j < S n /\
    B j = false /\
    dom_out_probed n ps j = false /\
    dom_two_dom_probed n ps (if Nat.ltb k j then k else j) (if Nat.ltb k j then j else k) = false.
Proof.
  intros n ps B k Hsz HBk.
  set (N := S n).
  assert (Hcnt_lt : count_of (filter_of (dom_sni_blocked n ps B k) (upto N)) < N).
  { apply Nat.leb_le in Hsz. unfold split_size, selected_outputs in Hsz.
    change (gd_shares (dom_and_gadget n)) with N in Hsz.
    pose proof (count_filter_orb B
      (fun j => any_of (fun p => match dom_sni_probe_hit n k p with Some z => Nat.eqb z j | None => false end) ps)
      (upto N)) as Horb.
    pose proof (count_filter_any_of_eqb (dom_sni_probe_hit n k) ps (upto N) (upto_NoDup N)) as Hhit.
    unfold dom_sni_blocked. lia. }
  destruct (find_unblocked_spec N (dom_sni_blocked n ps B k) Hcnt_lt) as [Hj_lt Hblk].
  cbv zeta in Hj_lt, Hblk.
  change (find_unblocked N (dom_sni_blocked n ps B k)) with (dom_sni_target n ps B k) in Hj_lt, Hblk.
  set (j := dom_sni_target n ps B k) in *.
  unfold dom_sni_blocked in Hblk. apply orb_false_elim in Hblk. destruct Hblk as [HBj Hany].
  assert (Hne : k <> j) by (intro Heq; rewrite <- Heq, HBk in HBj; discriminate).
  assert (Houtp : dom_out_probed n ps j = false).
  { destruct (dom_out_probed n ps j) eqn:Eop; [|reflexivity].
    destruct (dom_out_probed_inv n ps j Eop) as [p [Hp Hpw]].
    assert (Hhit : dom_sni_probe_hit n k p = Some j).
    { unfold dom_sni_probe_hit. rewrite Hpw. unfold dom_out_wire. change (S n) with N.
      assert (L1 : (2 * N + 4 * N * N + j <? 2 * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
      assert (L2 : (2 * N + 4 * N * N + j <? 2 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
      rewrite L1, L2. f_equal. unfold N in *; lia. }
    pose proof (any_of_member_true
      (fun p0 => match dom_sni_probe_hit n k p0 with Some z => Nat.eqb z j | None => false end)
      ps p Hp ltac:(cbv beta; rewrite Hhit; apply eqb_refl_nat)) as Habs.
    rewrite Habs in Hany. discriminate. }
  assert (Htd : dom_two_dom_probed n ps (if Nat.ltb k j then k else j) (if Nat.ltb k j then j else k) = false).
  { destruct (dom_two_dom_probed n ps (if Nat.ltb k j then k else j) (if Nat.ltb k j then j else k)) eqn:Etd; [|reflexivity].
    destruct (dom_two_dom_probed_inv n ps _ _ Etd) as [p [Hp Hwp]].
    assert (Hrng : 2 * N <= p_wire p /\ p_wire p < 2 * N + 4 * N * N).
    { unfold dom_wire_pair in Hwp. cbv zeta in Hwp. change (S n) with N in Hwp.
      destruct (Nat.ltb (p_wire p) (2 * N)) eqn:L1; [discriminate|].
      destruct (Nat.ltb (p_wire p) (2 * N + N * N)) eqn:L2.
      - apply Nat.ltb_ge in L1. apply Nat.ltb_lt in L2. unfold N in *; lia.
      - destruct (Nat.ltb (p_wire p) (2 * N + 4 * N * N)) eqn:L3; [|discriminate].
        apply Nat.ltb_ge in L1. apply Nat.ltb_lt in L3. unfold N in *; lia. }
    assert (Hhit : dom_sni_probe_hit n k p = Some j).
    { unfold dom_sni_probe_hit. change (S n) with N.
      assert (L1 : (p_wire p <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
      assert (L2 : (p_wire p <? 2 * N + 4 * N * N) = true) by (apply Nat.ltb_lt; lia).
      rewrite L1, L2, Hwp.
      destruct (Nat.ltb k j) eqn:Lkj.
      - rewrite eqb_refl_nat. reflexivity.
      - assert (Ejk : (j =? k) = false) by (apply Nat.eqb_neq; lia).
        rewrite Ejk, eqb_refl_nat. reflexivity. }
    pose proof (any_of_member_true
      (fun p0 => match dom_sni_probe_hit n k p0 with Some z => Nat.eqb z j | None => false end)
      ps p Hp ltac:(cbv beta; rewrite Hhit; apply eqb_refl_nat)) as Habs.
    rewrite Habs in Hany. discriminate. }
  split; [exact Hj_lt | split; [exact HBj | split; [exact Houtp | exact Htd]]].
Qed.

Definition dom_sni_df_base_rbit (n : nat) (ps : list Probe)
    (a b : ShareMatrix (dom_and_gadget n)) (k j : nat) : bool :=
  let N := S n in
  if Nat.eqb k j then false
  else dom_sim_df n ps (fun _ => false) a b (fun _ => false) (dom_pair_idx N k j).

Definition dom_sni_delta (n : nat) (ps : list Probe)
    (a b : ShareMatrix (dom_and_gadget n)) (k : nat) : bool :=
  let N := S n in
  xorb (xor_sum_upto (fun j => andb (a 0 k) (a 1 j)) N)
       (xor_sum_upto (fun j => xorb (andb (b 0 k) (b 1 j)) (dom_sni_df_base_rbit n ps a b k j)) N).

Definition dom_sni_df_out (n : nat) (ps : list Probe) (B : nat -> bool)
    (a b : ShareMatrix (dom_and_gadget n)) (idx : nat) : bool :=
  let N := S n in
  let OutP x := dom_out_probed n ps x in
  let NeedK x := andb (B x) (negb (OutP x)) in
  let u := idx / N in let v := idx mod N in
  if Nat.ltb u v then
    if andb (NeedK u) (Nat.eqb v (dom_sni_target n ps B u)) then dom_sni_delta n ps a b u
    else if andb (NeedK v) (Nat.eqb u (dom_sni_target n ps B v)) then dom_sni_delta n ps a b v
    else false
  else false.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem dom_and_is_sni :
  forall n d, d <= n -> SNI (dom_and_gadget n) ex_robust d.
Proof.
  intros n d Hd ps B Hw Hsz.
  assert (Hsz_n : Nat.leb (split_size (dom_and_gadget n) ps B) n = true)
    by (apply Nat.leb_le; apply Nat.leb_le in Hsz; lia).
  exists (dom_sni_shares n ps).
  split; [unfold dom_sni_shares; apply dom_pini_shares_bounded|].
  intros a b Hagree.
  assert (Hagree0 : agree_on (dom_and_gadget n) (union_shares (dom_pini_shares n ps (fun _ => false)) (fun _ => false)) a b).
  { intros j k Hj Hk Hu. apply Hagree; [exact Hj | exact Hk|].
    unfold union_shares in Hu. rewrite orb_false_r in Hu. exact Hu. }
  set (N := S n) in *.
  set (df_out := dom_sni_df_out n ps B a b).
  set (df := dom_sim_df n ps (fun _ => false) a b df_out).
  assert (Hextra_ge : forall idx, idx < N * N -> Nat.ltb (idx / N) (idx mod N) = false -> df_out idx = false).
  { intros idx _ Lge. unfold df_out, dom_sni_df_out. cbv zeta. change (S n) with N. rewrite Lge. reflexivity. }
  assert (Hextra_uv : forall u v, u < N -> v < N -> u < v ->
    (orb false (dom_out_probed n ps u) = true \/
     orb false (dom_out_probed n ps v) = true \/
     dom_two_dom_probed n ps u v = true) ->
    df_out (u * N + v) = false).
  { intros u v Hu Hv Huv Hdisj.
    destruct (div_mod_pair_id N u v Hu Hv) as [Hdu Hdv].
    unfold df_out, dom_sni_df_out. cbv zeta. change (S n) with N.
    rewrite Hdu, Hdv. assert (Luv : (u <? v) = true) by (apply Nat.ltb_lt; exact Huv). rewrite Luv.
    destruct (andb (andb (B u) (negb (dom_out_probed n ps u))) (Nat.eqb v (dom_sni_target n ps B u))) eqn:E1.
    - apply andb_prop in E1. destruct E1 as [ENu Evt]. apply andb_prop in ENu. destruct ENu as [HBu Hnou].
      apply eqb_sound_nat in Evt. subst v.
      destruct (dom_sni_target_spec n ps B u Hsz_n HBu) as [_ [_ [Hnov Htd]]].
      rewrite Luv in Htd. destruct Hdisj as [H1 | [H2 | H3]]; simpl in *;
        [rewrite H1 in Hnou; discriminate | rewrite H2 in Hnov; discriminate | rewrite H3 in Htd; discriminate].
    - destruct (andb (andb (B v) (negb (dom_out_probed n ps v))) (Nat.eqb u (dom_sni_target n ps B v))) eqn:E2; [|reflexivity].
      apply andb_prop in E2. destruct E2 as [ENv Eut]. apply andb_prop in ENv. destruct ENv as [HBv Hnov].
      apply eqb_sound_nat in Eut. subst u.
      destruct (dom_sni_target_spec n ps B v Hsz_n HBv) as [_ [_ [Hnou Htd]]].
      assert (Lvu : (v <? dom_sni_target n ps B v) = false) by (apply Nat.ltb_ge; lia).
      rewrite Lvu in Htd. destruct Hdisj as [H1 | [H2 | H3]]; simpl in *;
        [rewrite H1 in Hnou; discriminate | rewrite H2 in Hnov; discriminate | rewrite H3 in Htd; discriminate]. }
  apply (bit_tapes_xor_hides (N * N) (list bool) (list_eqb bool_eqb)
           (split_view (dom_and_gadget n) ex_robust ps B a)
           (split_view (dom_and_gadget n) ex_robust ps B b) df).
  intros tape Htape.
  destruct (dom_and_sim_core n ps (fun _ => false) a b df_out Hw Hagree0 Hextra_ge Hextra_uv tape Htape)
    as [Hint Hout_p].
  unfold split_view. f_equal; [exact Hint|].
  unfold output_view, selected_outputs. apply support_map_ext. intros k Hk.
  change (gd_shares (dom_and_gadget n)) with N in Hk.
  pose proof (support_filter_true B (upto N) k Hk) as HBk.
  apply support_filter_member in Hk. apply member_upto_lt in Hk.
  replace (gd_out (dom_and_gadget n) k) with (dom_out_wire n k) by reflexivity.
  rewrite (dom_value_eq n b); [|unfold dom_wire_count, dom_out_wire; unfold N in *; cbv zeta; lia].
  rewrite (dom_value_eq n a); [|unfold dom_wire_count, dom_out_wire; unfold N in *; cbv zeta; lia].
  unfold dom_eval, dom_out_wire. cbv zeta. change (S n) with N.
  assert (L0 : (2 * N + 4 * N * N + k <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L1 : (2 * N + 4 * N * N + k <? 2 * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L2 : (2 * N + 4 * N * N + k <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L3 : (2 * N + 4 * N * N + k <? 2 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L4 : (2 * N + 4 * N * N + k <? 2 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L5 : (2 * N + 4 * N * N + k <? 2 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  rewrite L0, L1, L2, L3, L4, L5.
  destruct (gd_read (dom_and_gadget n)) eqn:Hrd; [unfold dom_and_gadget in Hrd; cbn [gd_read] in Hrd; discriminate|].
  replace (2 * N + 4 * N * N + k - (2 * N + 4 * N * N)) with k by lia.
  destruct (dom_out_probed n ps k) eqn:Hopk.
  - apply xor_sum_upto_ext. intros j Hj. apply Hout_p; [exact Hk | rewrite Hopk; reflexivity | exact Hj].
  - destruct (dom_sni_target_spec n ps B k Hsz_n HBk) as [Ht_lt [HBt _]].
    cbv zeta in Ht_lt, HBt.
    set (t := dom_sni_target n ps B k) in *.
    assert (Hrow : forall j, j < N ->
      dom_rbit N (zip_xorb tape (map_over df (upto (N * N)))) k j =
      xorb (dom_rbit N tape k j)
           (xorb (dom_sni_df_base_rbit n ps a b k j)
                 (if Nat.eqb j t then dom_sni_delta n ps a b k else false))).
    { intros j Hj.
      destruct (Nat.eq_dec k j) as [<-|Hne].
      - repeat rewrite dom_rbit_diag. unfold dom_sni_df_base_rbit. rewrite eqb_refl_nat.
        assert (Ekt : Nat.eqb k t = false) by (apply Nat.eqb_neq; intro Heq; rewrite <- Heq, HBk in HBt; discriminate).
        rewrite Ekt. reflexivity.
      - unfold dom_rbit, dom_sni_df_base_rbit.
        assert (Ekj : Nat.eqb k j = false) by (apply Nat.eqb_neq; exact Hne).
        rewrite Ekj, bit_at_zip_xorb; [|exact Htape].
        pose proof (dom_pair_idx_lt N k j Hk Hj) as Hplt.
        assert (Hpltb : (dom_pair_idx N k j <? N * N) = true) by (apply Nat.ltb_lt; exact Hplt).
        rewrite Hpltb.
        unfold df, dom_sim_df, dom_sni_df_out, df_out. cbv zeta. change (S n) with N.
        assert (Hout_eq : dom_sni_df_out n ps B a b (dom_pair_idx N k j) =
          if Nat.eqb j t then dom_sni_delta n ps a b k else false).
        { unfold dom_sni_df_out, dom_pair_idx. cbv zeta. change (S n) with N.
          destruct (Nat.ltb k j) eqn:Lkj.
          - destruct (div_mod_pair_id N k j Hk Hj) as [Hd2 Hm2]. rewrite Hd2, Hm2, Lkj, HBk, Hopk. simpl.
            fold t. destruct (Nat.eqb j t) eqn:Ejt; [reflexivity|].
            destruct (B j) eqn:HBj; simpl; [|reflexivity].
            destruct (dom_sni_target_spec n ps B j Hsz_n HBj) as [_ [HBtj _]].
            assert (Ekt : Nat.eqb k (dom_sni_target n ps B j) = false)
              by (apply Nat.eqb_neq; intro Heq; rewrite <- Heq, HBk in HBtj; discriminate).
            rewrite Ekt, andb_false_r. reflexivity.
          - assert (Hjk : j < k) by (apply Nat.ltb_ge in Lkj; lia).
            destruct (div_mod_pair_id N j k Hj Hk) as [Hd2 Hm2]. rewrite Hd2, Hm2.
            assert (Ljk : (j <? k) = true) by (apply Nat.ltb_lt; exact Hjk). rewrite Ljk.
            destruct (B j) eqn:HBj; simpl.
            + destruct (dom_sni_target_spec n ps B j Hsz_n HBj) as [_ [HBtj _]].
              assert (Ekt : Nat.eqb k (dom_sni_target n ps B j) = false)
                by (apply Nat.eqb_neq; intro Heq; rewrite <- Heq, HBk in HBtj; discriminate).
              rewrite Ekt, andb_false_r, HBk, Hopk. simpl. fold t. reflexivity.
            + rewrite HBk, Hopk. simpl. fold t. reflexivity. }
        rewrite Hout_eq.
        unfold dom_sim_df; cbv zeta; change (S n) with N; rewrite !gf2_add_zero_r.
        destruct (dom_rbit N tape k j); destruct (if Nat.eqb j t then dom_sni_delta n ps a b k else false); reflexivity. }
    (* Now simplify the xor_sum_upto over N. *)
    transitivity (xor_sum_upto (fun j =>
      xorb (xorb (andb (b 0 k) (b 1 j)) (dom_sni_df_base_rbit n ps a b k j))
           (xorb (dom_rbit N tape k j) (if Nat.eqb j t then dom_sni_delta n ps a b k else false))) N).
    { apply xor_sum_upto_ext. intros j Hj. rewrite (Hrow j Hj).
      destruct (b 0 k && b 1 j); destruct (dom_rbit N tape k j);
        destruct (dom_sni_df_base_rbit n ps a b k j);
        destruct (if Nat.eqb j t then dom_sni_delta n ps a b k else false); reflexivity. }
    rewrite (xor_sum_upto_xorb _ _ N), (xor_sum_upto_xorb (dom_rbit N tape k) _ N).
    rewrite (xor_sum_upto_point N t (dom_sni_delta n ps a b k) Ht_lt).
    unfold dom_sni_delta. change (S n) with N.
    assert (Hrhs : xor_sum_upto (fun j => xorb (andb (a 0 k) (a 1 j)) (dom_rbit N tape k j)) N =
      xorb (xor_sum_upto (fun j => andb (a 0 k) (a 1 j)) N)
           (xor_sum_upto (fun j => dom_rbit N tape k j) N))
      by apply xor_sum_upto_xorb.
    rewrite Hrhs.
    destruct (xor_sum_upto (fun j => xorb (b 0 k && b 1 j) (dom_sni_df_base_rbit n ps a b k j)) N);
    destruct (xor_sum_upto (fun j => dom_rbit N tape k j) N);
    destruct (xor_sum_upto (fun j => a 0 k && a 1 j) N); reflexivity.
Qed.

(* =========================================================================
   Section 3b: Glitch-robust SNI mask refresh, HPC1 AND, and HPC2 AND
   ========================================================================= *)

Definition ref_wire_count (n : nat) : nat :=
  let N := S n in 2 * N + 2 * N * N.

Definition ref_out_wire (n i : nat) : nat :=
  let N := S n in N + 2 * N * N + i.

Definition ref_gate (n w : nat) : Gate :=
  let N := S n in
  if Nat.ltb w (N + N * N) then g_in w
  else if Nat.ltb w (N + 2 * N * N) then
    let p := w - (N + N * N) in
    let i := p / N in let j := p mod N in
    g_reg (if Nat.eqb i j then i else N + dom_pair_idx N i j)
  else
    let i := w - (N + 2 * N * N) in
    g_op 2 (map_over (fun j => N + N * N + i * N + j) (upto N)).

Definition sni_refresh_gadget (n : nat) : Gadget :=
  let N := S n in {|
  gd_share := gf2_sharing;
  gd_prob := bit_tapes (N * N);
  gd_circuit := circuit_of_fun (ref_wire_count n) (ref_gate n);
  gd_ops := bool_ops;
  gd_inputs := 1;
  gd_shares := N;
  gd_out := ref_out_wire n;
  gd_read := 1;
  gd_assign := fun a tape _ i =>
    if Nat.ltb i N then a 0 i else bit_at tape (i - N);
  gd_start := fun _ _ _ => false
|}.

Lemma sni_refresh_well_formed :
  forall n, gadget_well_formed (sni_refresh_gadget n).
Proof.
  intros n. set (N := S n). split; [|split].
  - simpl. apply well_formed_circuit_of_fun. intros w Hw.
    unfold ref_wire_count in Hw. change (S n) with N in Hw.
    unfold ref_gate. cbv zeta. change (S n) with N.
    destruct (Nat.ltb w (N + N * N)) eqn:E1; [reflexivity|].
    apply Nat.ltb_ge in E1.
    destruct (Nat.ltb w (N + 2 * N * N)) eqn:E2.
    + apply Nat.ltb_lt in E2.
      assert (Hp_lt : w - (N + N * N) < N * N) by lia.
      destruct (div_mod_pair_bound N (w - (N + N * N)) ltac:(lia) Hp_lt) as [Hi [Hj _]].
      destruct (Nat.eqb _ _); apply Nat.ltb_lt; unfold ref_wire_count;
        [unfold N in *; nia | pose proof (dom_pair_idx_lt N _ _ Hi Hj); unfold N in *; nia].
    + apply Nat.ltb_ge in E2. cbn [gate_well_formed].
      assert (Hall : forall u, (forall j, ProofSupport.Member j u -> j < N) ->
        all_of (fun a => a <? w) (map_over (fun j => N + N * N + (w - (N + 2 * N * N)) * N + j) u) = true).
      { intros u Hu. induction u as [|x ur IHu]; simpl; [reflexivity|].
        apply andb_true_intro; split; [apply Nat.ltb_lt; pose proof (Hu x (or_introl eq_refl)); nia | apply IHu; intros y Hy; apply Hu; right; exact Hy]. }
      apply Hall. intros j Hj. apply member_upto_lt; exact Hj.
  - simpl; lia.
  - intros k Hk. simpl in *. rewrite circuit_of_fun_count.
    unfold ref_out_wire, ref_wire_count, N in *. lia.
Qed.

Definition ref_eval (n : nat) (a : nat -> bool) (tape : list bool) (cyc w : nat) : bool :=
  let N := S n in
  if Nat.ltb w N then a w
  else if Nat.ltb w (N + N * N) then bit_at tape (w - N)
  else if Nat.ltb w (N + 2 * N * N) then
    match cyc with
    | 0 => false
    | S _ =>
      let p := w - (N + N * N) in
      let i := p / N in let j := p mod N in
      if Nat.eqb i j then a i else dom_rbit N tape i j
    end
  else
    match cyc with
    | 0 => false
    | S _ =>
      let i := w - (N + 2 * N * N) in
      xor_sum_upto (fun j => if Nat.eqb i j then a i else dom_rbit N tape i j) N
    end.

Lemma ref_value_eq :
  forall n (a : ShareMatrix (sni_refresh_gadget n)) tape cyc w,
    w < ref_wire_count n ->
    gd_value (sni_refresh_gadget n) a tape cyc w = ref_eval n (a 0) tape cyc w.
Proof.
  intros n a tape cyc w Hw.
  destruct (sni_refresh_well_formed n) as [Hwf _].
  unfold sni_refresh_gadget in Hwf. cbn [gd_circuit] in Hwf.
  set (N := S n) in *.
  assert (Hpair : forall t,
    (forall w0, w0 < ref_wire_count n ->
      regs_at gf2_sharing bool_ops (circuit_of_fun (ref_wire_count n) (ref_gate n))
        (fun _ => false)
        (fun _ i => if Nat.ltb i N then a 0 i else bit_at tape (i - N)) t w0 =
      match t with
      | 0 => false
      | S _ =>
        if Nat.ltb w0 (N + N * N) then false
        else if Nat.ltb w0 (N + 2 * N * N) then
          let p := w0 - (N + N * N) in let i := p / N in let j := p mod N in
          if Nat.eqb i j then a 0 i else dom_rbit N tape i j
        else false
      end) /\
    (forall w0, w0 < ref_wire_count n ->
      value_at gf2_sharing bool_ops (circuit_of_fun (ref_wire_count n) (ref_gate n))
        (fun _ => false)
        (fun _ i => if Nat.ltb i N then a 0 i else bit_at tape (i - N)) t w0 =
      ref_eval n (a 0) tape t w0)).
  { induction t as [|t [IHr IHv]].
    - assert (Hreg0 : forall w0, regs_at gf2_sharing bool_ops (circuit_of_fun (ref_wire_count n) (ref_gate n))
        (fun _ => false) (fun _ i => if Nat.ltb i N then a 0 i else bit_at tape (i - N)) 0 w0 = false)
        by (intros; reflexivity).
      split; [intros w0 _; exact (Hreg0 w0)|].
      intros w0 Hw0.
      rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw0].
      rewrite gate_at_circuit_of_fun; [|exact Hw0].
      unfold ref_gate, ref_eval. cbv zeta. change (S n) with N.
      destruct (Nat.ltb w0 (N + N * N)) eqn:E1.
      + destruct (Nat.ltb w0 N); reflexivity.
      + destruct (Nat.ltb w0 (N + 2 * N * N)) eqn:E2.
        * destruct (Nat.ltb w0 N) eqn:E0; [apply Nat.ltb_lt in E0; apply Nat.ltb_ge in E1; unfold N in *; lia | reflexivity].
        * apply Nat.ltb_ge in E2.
          assert (E0 : (w0 <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
          rewrite E0. unfold bool_ops.
          assert (Hz : forall u, (forall j, ProofSupport.Member j u -> j < N) ->
            xor_fold
              (map_over (fun x => eval_wire gf2_sharing bool_ops (circuit_of_fun (ref_wire_count n) (ref_gate n))
                (regs_at gf2_sharing bool_ops (circuit_of_fun (ref_wire_count n) (ref_gate n))
                  (fun _ => false) (fun _ i => if Nat.ltb i N then a 0 i else bit_at tape (i - N)) 0)
                (fun i => if Nat.ltb i N then a 0 i else bit_at tape (i - N))
                (wire_count (circuit_of_fun (ref_wire_count n) (ref_gate n))) x)
                (map_over (fun j => N + N * N + (w0 - (N + 2 * N * N)) * N + j) u)) = false).
          { induction u as [|j ur IHu]; intros Hu; [reflexivity|].
            cbn [map_over ProofSupport.map_over xor_fold].
            assert (Hj : j < N) by (apply Hu; left; reflexivity).
            assert (Hwj : N + N * N + (w0 - (N + 2 * N * N)) * N + j < ref_wire_count n)
              by (unfold ref_wire_count in *; unfold N in *; nia).
            rewrite eval_wire_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hwj].
            rewrite gate_at_circuit_of_fun; [|exact Hwj].
            unfold ref_gate. cbv zeta. change (S n) with N.
            assert (R1 : (N + N * N + (w0 - (N + 2 * N * N)) * N + j <? N + N * N) = false) by (apply Nat.ltb_ge; nia).
            assert (R2 : (N + N * N + (w0 - (N + 2 * N * N)) * N + j <? N + 2 * N * N) = true)
              by (apply Nat.ltb_lt; unfold ref_wire_count in *; unfold N in *; nia).
            rewrite R1, R2, Hreg0.
            apply IHu. intros y Hy. apply Hu; right; exact Hy. }
          apply Hz. intros j Hj. apply member_upto_lt; exact Hj.
    - assert (HregS : forall w0, w0 < ref_wire_count n ->
        regs_at gf2_sharing bool_ops (circuit_of_fun (ref_wire_count n) (ref_gate n))
          (fun _ => false) (fun _ i => if Nat.ltb i N then a 0 i else bit_at tape (i - N)) (S t) w0 =
        if Nat.ltb w0 (N + N * N) then false
        else if Nat.ltb w0 (N + 2 * N * N) then
          let p := w0 - (N + N * N) in let i := p / N in let j := p mod N in
          if Nat.eqb i j then a 0 i else dom_rbit N tape i j
        else false).
      { intros w0 Hw0. rewrite regs_at_succ_step, gate_at_circuit_of_fun; [|exact Hw0].
        unfold ref_gate at 1. cbv zeta. change (S n) with N.
        destruct (Nat.ltb w0 (N + N * N)) eqn:E1; [rewrite IHr; [destruct t; [reflexivity | rewrite E1; reflexivity] | exact Hw0]|].
        apply Nat.ltb_ge in E1.
        destruct (Nat.ltb w0 (N + 2 * N * N)) eqn:E2; [|rewrite IHr; [destruct t; [reflexivity | rewrite E2; destruct (Nat.ltb w0 (N + N * N)); reflexivity] | exact Hw0]].
        apply Nat.ltb_lt in E2.
        assert (Hp_lt : w0 - (N + N * N) < N * N) by lia.
        destruct (div_mod_pair_bound N (w0 - (N + N * N)) ltac:(lia) Hp_lt) as [Hi [Hj _]].
        destruct (Nat.eqb ((w0 - (N + N * N)) / N) ((w0 - (N + N * N)) mod N)) eqn:Eij.
        - rewrite IHv; [|unfold ref_wire_count; unfold N in *; nia].
          unfold ref_eval. cbv zeta. change (S n) with N.
          assert (L0 : ((w0 - (N + N * N)) / N <? N) = true) by (apply Nat.ltb_lt; exact Hi).
          rewrite L0. reflexivity.
        - pose proof (dom_pair_idx_lt N _ _ Hi Hj) as Hpr.
          rewrite IHv; [|unfold ref_wire_count; unfold N in *; nia].
          unfold ref_eval. cbv zeta. change (S n) with N.
          assert (L0 : (N + dom_pair_idx N ((w0 - (N + N * N)) / N) ((w0 - (N + N * N)) mod N) <? N) = false)
            by (apply Nat.ltb_ge; lia).
          assert (L1 : (N + dom_pair_idx N ((w0 - (N + N * N)) / N) ((w0 - (N + N * N)) mod N) <? N + N * N) = true)
            by (apply Nat.ltb_lt; lia).
          rewrite L0, L1. replace (N + dom_pair_idx N ((w0 - (N + N * N)) / N) ((w0 - (N + N * N)) mod N) - N)
            with (dom_pair_idx N ((w0 - (N + N * N)) / N) ((w0 - (N + N * N)) mod N)) by lia.
          unfold dom_rbit. rewrite Eij. reflexivity. }
      split; [exact HregS|].
      intros w0 Hw0.
      rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw0].
      rewrite gate_at_circuit_of_fun; [|exact Hw0].
      unfold ref_gate, ref_eval. cbv zeta. change (S n) with N.
      destruct (Nat.ltb w0 (N + N * N)) eqn:E1; [destruct (Nat.ltb w0 N); reflexivity|].
      apply Nat.ltb_ge in E1.
      destruct (Nat.ltb w0 (N + 2 * N * N)) eqn:E2.
      + assert (Hlt2 : w0 < N + 2 * N * N) by (apply Nat.ltb_lt; exact E2).
        assert (E0 : (w0 <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
        assert (E1' : (w0 <? N + N * N) = false) by (apply Nat.ltb_ge; exact E1).
        rewrite E0, HregS; [|exact Hw0]. rewrite E1', E2. reflexivity.
      + apply Nat.ltb_ge in E2.
        assert (E0 : (w0 <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
        rewrite E0. unfold bool_ops.
        assert (Hfold : forall u, (forall j, ProofSupport.Member j u -> j < N) ->
          xor_fold
            (map_over (fun x => eval_wire gf2_sharing bool_ops (circuit_of_fun (ref_wire_count n) (ref_gate n))
              (regs_at gf2_sharing bool_ops (circuit_of_fun (ref_wire_count n) (ref_gate n))
                (fun _ => false) (fun _ i => if Nat.ltb i N then a 0 i else bit_at tape (i - N)) (S t))
              (fun i => if Nat.ltb i N then a 0 i else bit_at tape (i - N))
              (wire_count (circuit_of_fun (ref_wire_count n) (ref_gate n))) x)
              (map_over (fun j => N + N * N + (w0 - (N + 2 * N * N)) * N + j) u)) =
          xor_fold
            (map_over (fun j =>
              if Nat.eqb (w0 - (N + 2 * N * N)) j then a 0 (w0 - (N + 2 * N * N))
              else dom_rbit N tape (w0 - (N + 2 * N * N)) j) u)).
        { induction u as [|j ur IHu]; intros Hu; [reflexivity|].
          cbn [map_over ProofSupport.map_over xor_fold].
          assert (Hj : j < N) by (apply Hu; left; reflexivity).
          assert (Hwj : N + N * N + (w0 - (N + 2 * N * N)) * N + j < ref_wire_count n)
            by (unfold ref_wire_count in *; unfold N in *; nia).
          rewrite eval_wire_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hwj].
          rewrite gate_at_circuit_of_fun; [|exact Hwj].
          unfold ref_gate. cbv zeta. change (S n) with N.
          assert (R1 : (N + N * N + (w0 - (N + 2 * N * N)) * N + j <? N + N * N) = false) by (apply Nat.ltb_ge; nia).
          assert (R2 : (N + N * N + (w0 - (N + 2 * N * N)) * N + j <? N + 2 * N * N) = true)
            by (apply Nat.ltb_lt; unfold ref_wire_count in *; unfold N in *; nia).
          rewrite R1, R2, HregS; [|exact Hwj].
          rewrite R1, R2. cbv zeta.
          assert (Hi_lt : w0 - (N + 2 * N * N) < N) by (unfold ref_wire_count in *; unfold N in *; lia).
          replace (N + N * N + (w0 - (N + 2 * N * N)) * N + j - (N + N * N))
            with ((w0 - (N + 2 * N * N)) * N + j)
            by (rewrite <- Nat.add_assoc, (Nat.add_comm (N + N * N)), Nat.add_sub; reflexivity).
          destruct (div_mod_pair_id N (w0 - (N + 2 * N * N)) j Hi_lt Hj) as [Hd Hm].
          rewrite Hd, Hm.
          f_equal. apply IHu. intros y Hy. apply Hu; right; exact Hy. }
        apply Hfold. intros j Hj; apply member_upto_lt; exact Hj. }
  destruct (Hpair cyc) as [_ Hv].
  unfold gd_value, sni_refresh_gadget. cbn [gd_share gd_ops gd_circuit gd_assign gd_start].
  change (S n) with N. exact (Hv w Hw).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem sni_refresh_correct :
  forall n (a : ShareMatrix (sni_refresh_gadget n)) tape,
    xor_sum_upto (fun k => gd_value (sni_refresh_gadget n) a tape (gd_read (sni_refresh_gadget n))
      (gd_out (sni_refresh_gadget n) k)) (S n) =
    xor_sum_upto (a 0) (S n).
Proof.
  intros n a tape. set (N := S n).
  transitivity (xor_sum_upto (fun k =>
    xorb (a 0 k) (xor_sum_upto (fun j => dom_rbit N tape k j) N)) N).
  - apply xor_sum_upto_ext. intros k Hk.
    replace (gd_out (sni_refresh_gadget n) k) with (ref_out_wire n k) by reflexivity.
    rewrite ref_value_eq; [|unfold ref_out_wire, ref_wire_count; unfold N in *; lia].
    unfold ref_eval, ref_out_wire. cbv zeta. change (S n) with N.
    assert (L0 : (N + 2 * N * N + k <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L1 : (N + 2 * N * N + k <? N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L2 : (N + 2 * N * N + k <? N + 2 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    rewrite L0, L1, L2.
    replace (N + 2 * N * N + k - (N + 2 * N * N)) with k by lia.
    transitivity (xor_sum_upto (fun j => xorb (if Nat.eqb k j then a 0 k else false) (dom_rbit N tape k j)) N).
    + apply xor_sum_upto_ext. intros j _.
      destruct (Nat.eqb k j) eqn:Ekj.
      * apply eqb_sound_nat in Ekj. subst j. rewrite dom_rbit_diag, gf2_add_zero_r. reflexivity.
      * reflexivity.
    + rewrite xor_sum_upto_xorb. f_equal.
      transitivity (xor_sum_upto (fun j => if Nat.eqb j k then a 0 k else false) N).
      * apply xor_sum_upto_ext. intros j _. rewrite Nat.eqb_sym. reflexivity.
      * apply xor_sum_upto_point. exact Hk.
  - rewrite xor_sum_upto_xorb.
    rewrite (xor_sum_upto_antisym_zero (dom_rbit N tape) N (dom_rbit_diag N tape) (dom_rbit_sym N tape)).
    apply gf2_add_zero_r.
Qed.

Lemma ref_stable_sources :
  forall n w, w < ref_wire_count n ->
    let N := S n in
    stable_sources (circuit_of_fun (ref_wire_count n) (ref_gate n)) (ref_wire_count n) w =
    if Nat.ltb w (N + 2 * N * N) then w :: nil
    else
      let i := w - (N + 2 * N * N) in
      map_over (fun j => N + N * N + i * N + j) (upto N).
Proof.
  intros n w Hw. cbv zeta. set (N := S n) in *.
  destruct (sni_refresh_well_formed n) as [Hwf _].
  unfold sni_refresh_gadget in Hwf; cbn [gd_circuit] in Hwf.
  rewrite <- (circuit_of_fun_count (ref_wire_count n) (ref_gate n)) at 2.
  rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw].
  rewrite gate_at_circuit_of_fun; [|exact Hw].
  unfold ref_gate. cbv zeta. change (S n) with N.
  destruct (Nat.ltb w (N + N * N)) eqn:E1.
  - assert (E12 : (w <? N + 2 * N * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in E1; lia).
    rewrite E12. reflexivity.
  - destruct (Nat.ltb w (N + 2 * N * N)) eqn:E2; [reflexivity|].
    apply Nat.ltb_ge in E2.
    assert (Hlist : forall u, (forall j, ProofSupport.Member j u -> j < N) ->
      flat_map_over (stable_sources (circuit_of_fun (ref_wire_count n) (ref_gate n))
        (wire_count (circuit_of_fun (ref_wire_count n) (ref_gate n))))
        (map_over (fun j => N + N * N + (w - (N + 2 * N * N)) * N + j) u) =
      map_over (fun j => N + N * N + (w - (N + 2 * N * N)) * N + j) u).
    { intros u Hu. induction u as [|j ur IHu]; [reflexivity|].
      cbn [map_over ProofSupport.map_over flat_map_over].
      assert (Hj : j < N) by (apply Hu; left; reflexivity).
      assert (Hr_lt : N + N * N + (w - (N + 2 * N * N)) * N + j < ref_wire_count n)
        by (unfold ref_wire_count in *; unfold N in *; nia).
      rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hr_lt].
      rewrite gate_at_circuit_of_fun; [|exact Hr_lt].
      unfold ref_gate. cbv zeta. change (S n) with N.
      assert (R1 : (N + N * N + (w - (N + 2 * N * N)) * N + j <? N + N * N) = false) by (apply Nat.ltb_ge; nia).
      assert (R2 : (N + N * N + (w - (N + 2 * N * N)) * N + j <? N + 2 * N * N) = true)
        by (apply Nat.ltb_lt; unfold ref_wire_count in *; unfold N in *; nia).
      rewrite R1, R2. cbn [app]. f_equal. apply IHu. intros y Hy. apply Hu; right; exact Hy. }
    apply Hlist. intros j Hj. apply member_upto_lt; exact Hj.
Qed.

Definition ref_sni_contrib (n : nat) (p : Probe) : option nat :=
  let N := S n in
  let w := p_wire p in
  if Nat.ltb w N then Some w
  else if Nat.ltb w (N + N * N) then None
  else if Nat.ltb w (N + 2 * N * N) then
    let q := w - (N + N * N) in
    let i := q / N in let j := q mod N in
    if Nat.eqb i j then Some i else None
  else Some (w - (N + 2 * N * N)).

Definition ref_sni_shares (n : nat) (ps : list Probe) : ShareSet :=
  fun _ k => any_of (fun p => match ref_sni_contrib n p with Some x => Nat.eqb x k | None => false end) ps.

Definition ref_sni_probe_hit (n k : nat) (p : Probe) : option nat :=
  let N := S n in
  let w := p_wire p in
  if Nat.ltb w N then None
  else if Nat.ltb w (N + N * N) then
    let r := w - N in let u := r / N in let v := r mod N in
    if Nat.ltb u v then
      if Nat.eqb u k then Some v else if Nat.eqb v k then Some u else None
    else None
  else if Nat.ltb w (N + 2 * N * N) then
    let q := w - (N + N * N) in let i := q / N in let j := q mod N in
    if Nat.eqb i j then None
    else if Nat.eqb i k then Some j else if Nat.eqb j k then Some i else None
  else Some (w - (N + 2 * N * N)).

Definition ref_sni_blocked (n : nat) (ps : list Probe) (B : nat -> bool) (k j : nat) : bool :=
  orb (B j) (any_of (fun p => match ref_sni_probe_hit n k p with Some z => Nat.eqb z j | None => false end) ps).

Definition ref_sni_target (n : nat) (ps : list Probe) (B : nat -> bool) (k : nat) : nat :=
  find_unblocked (S n) (ref_sni_blocked n ps B k).

Lemma ref_sni_shares_bounded :
  forall n ps,
    BoundedBy (sni_refresh_gadget n) (ref_sni_shares n ps) (count_of ps).
Proof.
  intros n ps j Hj. unfold card_in, ref_sni_shares. simpl in Hj.
  apply Nat.ltb_lt in Hj. apply Nat.leb_le.
  exact (count_filter_any_of_eqb (ref_sni_contrib n) ps (upto (S n)) (upto_NoDup (S n))).
Qed.

Lemma ref_sni_shares_hit :
  forall n ps p k,
    ProofSupport.Member p ps ->
    ref_sni_contrib n p = Some k ->
    ref_sni_shares n ps 0 k = true.
Proof.
  intros n ps p k Hp Hc. unfold ref_sni_shares.
  eapply any_of_member_true; [exact Hp|].
  cbv beta. rewrite Hc. apply eqb_refl_nat.
Qed.

Lemma ref_sni_target_spec :
  forall n ps B k,
    Nat.leb (split_size (sni_refresh_gadget n) ps B) n = true ->
    B k = true ->
    let j := ref_sni_target n ps B k in
    j < S n /\
    B j = false /\
    (forall p, ProofSupport.Member p ps -> ref_sni_probe_hit n k p <> Some j).
Proof.
  intros n ps B k Hsz HBk.
  set (N := S n).
  assert (Hcnt_lt : count_of (filter_of (ref_sni_blocked n ps B k) (upto N)) < N).
  { apply Nat.leb_le in Hsz. unfold split_size, selected_outputs in Hsz.
    change (gd_shares (sni_refresh_gadget n)) with N in Hsz.
    pose proof (count_filter_orb B
      (fun j => any_of (fun p => match ref_sni_probe_hit n k p with Some z => Nat.eqb z j | None => false end) ps)
      (upto N)) as Horb.
    pose proof (count_filter_any_of_eqb (ref_sni_probe_hit n k) ps (upto N) (upto_NoDup N)) as Hhit.
    unfold ref_sni_blocked. lia. }
  destruct (find_unblocked_spec N (ref_sni_blocked n ps B k) Hcnt_lt) as [Hj_lt Hblk].
  cbv zeta in Hj_lt, Hblk.
  change (find_unblocked N (ref_sni_blocked n ps B k)) with (ref_sni_target n ps B k) in Hj_lt, Hblk.
  set (j := ref_sni_target n ps B k) in *.
  unfold ref_sni_blocked in Hblk. apply orb_false_elim in Hblk. destruct Hblk as [HBj Hany].
  split; [exact Hj_lt | split; [exact HBj|]].
  intros p Hp Hhit.
  pose proof (any_of_member_true
    (fun p0 => match ref_sni_probe_hit n k p0 with Some z => Nat.eqb z j | None => false end)
    ps p Hp ltac:(cbv beta; rewrite Hhit; apply eqb_refl_nat)) as Habs.
  rewrite Habs in Hany. discriminate.
Qed.

Definition ref_sni_df (n : nat) (ps : list Probe) (B : nat -> bool)
    (a b : ShareMatrix (sni_refresh_gadget n)) (idx : nat) : bool :=
  let N := S n in
  let NeedK x := andb (B x) (negb (ref_sni_shares n ps 0 x)) in
  let u := idx / N in let v := idx mod N in
  if Nat.ltb u v then
    if andb (NeedK u) (Nat.eqb v (ref_sni_target n ps B u)) then xorb (a 0 u) (b 0 u)
    else if andb (NeedK v) (Nat.eqb u (ref_sni_target n ps B v)) then xorb (a 0 v) (b 0 v)
    else false
  else false.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem sni_refresh_is_sni :
  forall n d, d <= n -> SNI (sni_refresh_gadget n) ex_robust d.
Proof.
  intros n d Hd ps B Hw Hsz.
  assert (Hsz_n : Nat.leb (split_size (sni_refresh_gadget n) ps B) n = true)
    by (apply Nat.leb_le; apply Nat.leb_le in Hsz; lia).
  exists (ref_sni_shares n ps).
  split; [apply ref_sni_shares_bounded|].
  intros a b Hagree.
  set (N := S n) in *.
  set (df := ref_sni_df n ps B a b).
  assert (Hdf_zero : forall u v, u < N -> v < N -> u <> v ->
    (forall m, (m = u \/ m = v) ->
      (B m = true /\ ref_sni_shares n ps 0 m = false /\
       (if Nat.eqb m u then v else u) = ref_sni_target n ps B m) -> False) ->
    df (dom_pair_idx N u v) = false).
  { intros u v Hu Hv Hne Hno.
    unfold df, ref_sni_df, dom_pair_idx. cbv zeta. change (S n) with N.
    destruct (Nat.ltb u v) eqn:Luv.
    - destruct (div_mod_pair_id N u v Hu Hv) as [Hd2 Hm2]. rewrite Hd2, Hm2, Luv.
      destruct (andb (andb (B u) (negb (ref_sni_shares n ps 0 u))) (Nat.eqb v (ref_sni_target n ps B u))) eqn:E1.
      + apply andb_prop in E1. destruct E1 as [ENu Evt]. apply andb_prop in ENu. destruct ENu as [HBu Hnou].
        apply eqb_sound_nat in Evt. apply negb_true_iff in Hnou.
        exfalso. apply (Hno u (or_introl eq_refl)). split; [exact HBu | split; [exact Hnou|]].
        rewrite eqb_refl_nat. exact Evt.
      + destruct (andb (andb (B v) (negb (ref_sni_shares n ps 0 v))) (Nat.eqb u (ref_sni_target n ps B v))) eqn:E2; [|reflexivity].
        apply andb_prop in E2. destruct E2 as [ENv Eut]. apply andb_prop in ENv. destruct ENv as [HBv Hnov].
        apply eqb_sound_nat in Eut. apply negb_true_iff in Hnov.
        exfalso. apply (Hno v (or_intror eq_refl)). split; [exact HBv | split; [exact Hnov|]].
        assert (Evu : (v =? u) = false) by (apply Nat.eqb_neq; lia).
        rewrite Evu. exact Eut.
    - assert (Hvu : v < u) by (apply Nat.ltb_ge in Luv; lia).
      assert (Lvu : (v <? u) = true) by (apply Nat.ltb_lt; exact Hvu).
      destruct (div_mod_pair_id N v u Hv Hu) as [Hd2 Hm2]. rewrite Hd2, Hm2, Lvu.
      destruct (andb (andb (B v) (negb (ref_sni_shares n ps 0 v))) (Nat.eqb u (ref_sni_target n ps B v))) eqn:E1.
      + apply andb_prop in E1. destruct E1 as [ENv Eut]. apply andb_prop in ENv. destruct ENv as [HBv Hnov].
        apply eqb_sound_nat in Eut. apply negb_true_iff in Hnov.
        exfalso. apply (Hno v (or_intror eq_refl)). split; [exact HBv | split; [exact Hnov|]].
        assert (Evu : (v =? u) = false) by (apply Nat.eqb_neq; lia).
        rewrite Evu. exact Eut.
      + destruct (andb (andb (B u) (negb (ref_sni_shares n ps 0 u))) (Nat.eqb v (ref_sni_target n ps B u))) eqn:E2; [|reflexivity].
        apply andb_prop in E2. destruct E2 as [ENu Evt]. apply andb_prop in ENu. destruct ENu as [HBu Hnou].
        apply eqb_sound_nat in Evt. apply negb_true_iff in Hnou.
        exfalso. apply (Hno u (or_introl eq_refl)). split; [exact HBu | split; [exact Hnou|]].
        rewrite eqb_refl_nat. exact Evt. }
  apply (bit_tapes_xor_hides (N * N) (list bool) (list_eqb bool_eqb)
           (split_view (sni_refresh_gadget n) ex_robust ps B a)
           (split_view (sni_refresh_gadget n) ex_robust ps B b) df).
  intros tape Htape. unfold split_view. f_equal.
  - unfold internal_view, probe_set. apply support_map_ext. intros o Ho.
    apply member_flat_map_over_inv in Ho. destruct Ho as [p [Hp Ho]].
    assert (Hpw_lt : p_wire p < ref_wire_count n).
    { clear -Hw Hp. unfold wires_exist in Hw.
      induction ps as [|q r IH]; simpl in *; [contradiction|].
      apply andb_prop in Hw. destruct Hw as [Hq Hr].
      destruct Hp as [->|Hp]; [apply Nat.ltb_lt in Hq; rewrite circuit_of_fun_count in Hq; exact Hq | exact (IH Hr Hp)]. }
    unfold ex_robust, sni_refresh_gadget in Ho; cbn [gd_circuit] in Ho; rewrite circuit_of_fun_count in Ho.
    assert (Ho_cases : exists s, ProofSupport.Member s (stable_sources (circuit_of_fun (ref_wire_count n) (ref_gate n)) (ref_wire_count n) (p_wire p)) /\
      (o = obs_at s (p_cycle p) \/ o = obs_at s (prev_cycle (p_cycle p)))).
    { clear -Ho. induction (stable_sources (circuit_of_fun (ref_wire_count n) (ref_gate n)) (ref_wire_count n) (p_wire p)) as [|s r IH];
        cbn [flat_map_over] in Ho; [contradiction|].
      destruct Ho as [Ho1|[Ho2|Ho]]; [exists s; split; [left; reflexivity | left; first [exact Ho1 | symmetry; exact Ho1]]
        | exists s; split; [left; reflexivity | right; first [exact Ho2 | symmetry; exact Ho2]]
        | destruct (IH Ho) as [s0 [Hs0 Hdec]]; exists s0; split; [right; exact Hs0 | exact Hdec]]. }
    destruct Ho_cases as [s [Hs Hdec]].
    assert (Hs_eq : forall cyc,
      gd_value (sni_refresh_gadget n) b (zip_xorb tape (map_over df (upto (N * N)))) cyc s =
      gd_value (sni_refresh_gadget n) a tape cyc s).
    { intros cyc.
      rewrite ref_stable_sources in Hs; [|exact Hpw_lt]. cbv zeta in Hs. change (S n) with N in Hs.
      assert (Hs_lt : s < ref_wire_count n).
      { unfold ref_wire_count. change (S n) with N.
        destruct (Nat.ltb (p_wire p) (N + 2 * N * N)) eqn:E1; [cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s; exact Hpw_lt|].
        destruct (member_map_over_inv _ _ _ Hs) as [j [Hj <-]].
        apply member_upto_lt in Hj. unfold ref_wire_count in Hpw_lt. change (S n) with N in Hpw_lt. nia. }
      rewrite !ref_value_eq; [|exact Hs_lt | exact Hs_lt].
      destruct (Nat.ltb (p_wire p) (N + 2 * N * N)) eqn:Ep1.
      - cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s.
        destruct (Nat.ltb (p_wire p) N) eqn:W0.
        + unfold ref_eval. cbv zeta. change (S n) with N. rewrite W0.
          symmetry; apply Hagree; [reflexivity | exact W0|].
          assert (Hc : ref_sni_contrib n p = Some (p_wire p))
            by (unfold ref_sni_contrib; change (S n) with N; rewrite W0; reflexivity).
          exact (ref_sni_shares_hit n ps p (p_wire p) Hp Hc).
        + destruct (Nat.ltb (p_wire p) (N + N * N)) eqn:W1.
          * assert (Hr_lt : p_wire p - N < N * N) by (apply Nat.ltb_lt in W1; apply Nat.ltb_ge in W0; unfold N in *; lia).
            destruct (div_mod_pair_bound N (p_wire p - N) ltac:(lia) Hr_lt) as [Hu [Hv Hdm]].
            unfold ref_eval. cbv zeta. change (S n) with N. rewrite W0, W1.
            rewrite bit_at_zip_xorb; [|exact Htape].
            assert (Hr_b : (p_wire p - N <? N * N) = true) by (apply Nat.ltb_lt; exact Hr_lt).
            rewrite Hr_b.
            assert (Hdf_z : df (p_wire p - N) = false).
            { unfold df, ref_sni_df. cbv zeta. change (S n) with N.
              destruct (Nat.ltb ((p_wire p - N) / N) ((p_wire p - N) mod N)) eqn:Luv; [|reflexivity].
              destruct (andb (andb (B ((p_wire p - N) / N)) (negb (ref_sni_shares n ps 0 ((p_wire p - N) / N))))
                             (Nat.eqb ((p_wire p - N) mod N) (ref_sni_target n ps B ((p_wire p - N) / N)))) eqn:E1.
              - apply andb_prop in E1. destruct E1 as [ENu Evt]. apply andb_prop in ENu. destruct ENu as [HBu _].
                apply eqb_sound_nat in Evt.
                destruct (ref_sni_target_spec n ps B _ Hsz_n HBu) as [_ [_ Hno]].
                exfalso. apply (Hno p Hp).
                unfold ref_sni_probe_hit. change (S n) with N. rewrite W0, W1, Luv, eqb_refl_nat. f_equal. exact Evt.
              - destruct (andb (andb (B ((p_wire p - N) mod N)) (negb (ref_sni_shares n ps 0 ((p_wire p - N) mod N))))
                               (Nat.eqb ((p_wire p - N) / N) (ref_sni_target n ps B ((p_wire p - N) mod N)))) eqn:E2; [|reflexivity].
                apply andb_prop in E2. destruct E2 as [ENv Eut]. apply andb_prop in ENv. destruct ENv as [HBv _].
                apply eqb_sound_nat in Eut.
                destruct (ref_sni_target_spec n ps B _ Hsz_n HBv) as [_ [_ Hno]].
                exfalso. apply (Hno p Hp).
                unfold ref_sni_probe_hit. change (S n) with N. rewrite W0, W1, Luv.
                assert (Ene : ((p_wire p - N) / N =? (p_wire p - N) mod N) = false)
                  by (apply Nat.eqb_neq; apply Nat.ltb_lt in Luv; lia).
                rewrite Ene, eqb_refl_nat. f_equal. exact Eut. }
            rewrite Hdf_z, gf2_add_zero_r. reflexivity.
          * assert (Hq_lt : p_wire p - (N + N * N) < N * N)
              by (apply Nat.ltb_lt in Ep1; apply Nat.ltb_ge in W1; unfold N in *; lia).
            destruct (div_mod_pair_bound N (p_wire p - (N + N * N)) ltac:(lia) Hq_lt) as [Hi [Hj _]].
            unfold ref_eval. cbv zeta. change (S n) with N. rewrite W0, W1, Ep1.
            destruct cyc as [|cyc]; [reflexivity|].
            destruct (Nat.eqb ((p_wire p - (N + N * N)) / N) ((p_wire p - (N + N * N)) mod N)) eqn:Eij.
            -- symmetry; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hi|].
               assert (Hc : ref_sni_contrib n p = Some ((p_wire p - (N + N * N)) / N))
                 by (unfold ref_sni_contrib; change (S n) with N; rewrite W0, W1, Ep1, Eij; reflexivity).
               exact (ref_sni_shares_hit n ps p _ Hp Hc).
            -- assert (Hne : (p_wire p - (N + N * N)) / N <> (p_wire p - (N + N * N)) mod N)
                 by (apply Nat.eqb_neq; exact Eij).
               unfold dom_rbit. rewrite Eij, bit_at_zip_xorb; [|exact Htape].
               pose proof (dom_pair_idx_lt N _ _ Hi Hj) as Hpr.
               assert (Hprb : (dom_pair_idx N ((p_wire p - (N + N * N)) / N) ((p_wire p - (N + N * N)) mod N) <? N * N) = true)
                 by (apply Nat.ltb_lt; exact Hpr).
               rewrite Hprb.
               assert (Hdf_z : df (dom_pair_idx N ((p_wire p - (N + N * N)) / N) ((p_wire p - (N + N * N)) mod N)) = false).
               { apply (Hdf_zero _ _ Hi Hj Hne).
                 intros m Hm [HBm [_ Hm_eq]]; destruct (ref_sni_target_spec n ps B m Hsz_n HBm) as [_ [_ Hno]];
                   destruct Hm as [->| ->].
                 - rewrite eqb_refl_nat in Hm_eq. apply (Hno p Hp).
                   unfold ref_sni_probe_hit. change (S n) with N. rewrite W0, W1, Ep1, Eij, eqb_refl_nat. f_equal. exact Hm_eq.
                 - assert (Emne : ((p_wire p - (N + N * N)) mod N =? (p_wire p - (N + N * N)) / N) = false)
                     by (apply Nat.eqb_neq; lia).
                   rewrite Emne in Hm_eq. apply (Hno p Hp).
                   unfold ref_sni_probe_hit. change (S n) with N. rewrite W0, W1, Ep1, Eij, eqb_refl_nat. f_equal. exact Hm_eq. }
               rewrite Hdf_z, gf2_add_zero_r. reflexivity.
      - apply Nat.ltb_ge in Ep1.
        set (i := p_wire p - (N + 2 * N * N)) in *.
        assert (Hi_lt : i < N) by (unfold ref_wire_count in Hpw_lt; unfold i, N in *; lia).
        assert (Hcov : ref_sni_shares n ps 0 i = true).
        { assert (Hc : ref_sni_contrib n p = Some i).
          { unfold ref_sni_contrib. change (S n) with N.
            assert (L0 : (p_wire p <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
            assert (L1 : (p_wire p <? N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
            assert (L2 : (p_wire p <? N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact Ep1).
            rewrite L0, L1, L2. reflexivity. }
          exact (ref_sni_shares_hit n ps p i Hp Hc). }
        destruct (member_map_over_inv _ _ _ Hs) as [j [Hj <-]].
        apply member_upto_lt in Hj.
        unfold ref_eval. cbv zeta. change (S n) with N.
        assert (R0 : (N + N * N + i * N + j <? N) = false) by (apply Nat.ltb_ge; nia).
        assert (R1 : (N + N * N + i * N + j <? N + N * N) = false) by (apply Nat.ltb_ge; nia).
        assert (R2 : (N + N * N + i * N + j <? N + 2 * N * N) = true) by (apply Nat.ltb_lt; nia).
        rewrite R0, R1, R2.
        destruct cyc as [|cyc]; [reflexivity|].
        replace (N + N * N + i * N + j - (N + N * N)) with (i * N + j) by lia.
        destruct (div_mod_pair_id N i j Hi_lt Hj) as [Hd2 Hm2]. rewrite Hd2, Hm2.
        destruct (Nat.eqb i j) eqn:Eij.
        + symmetry; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hi_lt | exact Hcov].
        + assert (Hne : i <> j) by (apply Nat.eqb_neq; exact Eij).
          unfold dom_rbit. rewrite Eij, bit_at_zip_xorb; [|exact Htape].
          pose proof (dom_pair_idx_lt N i j Hi_lt Hj) as Hpr.
          assert (Hprb : (dom_pair_idx N i j <? N * N) = true) by (apply Nat.ltb_lt; exact Hpr).
          rewrite Hprb.
          assert (Hdf_z : df (dom_pair_idx N i j) = false).
          { apply (Hdf_zero i j Hi_lt Hj Hne).
            intros m [->| ->] [HBm [Hnom Hm_eq]].
            - rewrite Hcov in Hnom. discriminate.
            - assert (Eji : (j =? i) = false) by (apply Nat.eqb_neq; lia).
              rewrite Eji in Hm_eq.
              destruct (ref_sni_target_spec n ps B j Hsz_n HBm) as [_ [_ Hno]].
              apply (Hno p Hp). unfold ref_sni_probe_hit. change (S n) with N.
              assert (L0 : (p_wire p <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
              assert (L1 : (p_wire p <? N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
              assert (L2 : (p_wire p <? N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact Ep1).
              rewrite L0, L1, L2. f_equal. unfold i in *. lia. }
          rewrite Hdf_z, gf2_add_zero_r. reflexivity. }
    destruct Hdec as [->| ->]; simpl; apply Hs_eq.
  - unfold output_view, selected_outputs. apply support_map_ext. intros k Hk.
    change (gd_shares (sni_refresh_gadget n)) with N in Hk.
    pose proof (support_filter_true B (upto N) k Hk) as HBk.
    apply support_filter_member in Hk. apply member_upto_lt in Hk.
    replace (gd_out (sni_refresh_gadget n) k) with (ref_out_wire n k) by reflexivity.
    rewrite !ref_value_eq; [|unfold ref_out_wire, ref_wire_count; unfold N in *; lia
                           |unfold ref_out_wire, ref_wire_count; unfold N in *; lia].
    unfold ref_eval, ref_out_wire. cbv zeta. change (S n) with N.
    assert (L0 : (N + 2 * N * N + k <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L1 : (N + 2 * N * N + k <? N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L2 : (N + 2 * N * N + k <? N + 2 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    rewrite L0, L1, L2.
    destruct (gd_read (sni_refresh_gadget n)) eqn:Hrd; [unfold sni_refresh_gadget in Hrd; cbn [gd_read] in Hrd; discriminate|].
    replace (N + 2 * N * N + k - (N + 2 * N * N)) with k by lia.
    destruct (ref_sni_shares n ps 0 k) eqn:Hcov.
    + apply xor_sum_upto_ext. intros j Hj.
      destruct (Nat.eqb k j) eqn:Ekj.
      * symmetry; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hk | exact Hcov].
      * assert (Hne : k <> j) by (apply Nat.eqb_neq; exact Ekj).
        unfold dom_rbit. rewrite Ekj, bit_at_zip_xorb; [|exact Htape].
        pose proof (dom_pair_idx_lt N k j Hk Hj) as Hpr.
        assert (Hprb : (dom_pair_idx N k j <? N * N) = true) by (apply Nat.ltb_lt; exact Hpr).
        rewrite Hprb.
        assert (Hdf_z : df (dom_pair_idx N k j) = false).
        { apply (Hdf_zero k j Hk Hj Hne).
          intros m [->| ->] [HBm [Hnom Hm_eq]].
          - rewrite Hcov in Hnom. discriminate.
          - assert (Ejk : (j =? k) = false) by (apply Nat.eqb_neq; lia).
            rewrite Ejk in Hm_eq.
            destruct (ref_sni_target_spec n ps B j Hsz_n HBm) as [_ [HBt _]].
            rewrite <- Hm_eq, HBk in HBt. discriminate. }
        rewrite Hdf_z, gf2_add_zero_r. reflexivity.
    + destruct (ref_sni_target_spec n ps B k Hsz_n HBk) as [Ht_lt [HBt _]].
      cbv zeta in Ht_lt, HBt. set (t := ref_sni_target n ps B k) in *.
      assert (Hrow : forall j, j < N ->
        (if Nat.eqb k j then b 0 k else dom_rbit N (zip_xorb tape (map_over df (upto (N * N)))) k j) =
        xorb (if Nat.eqb k j then a 0 k else dom_rbit N tape k j)
             (if Nat.eqb j t then xorb (a 0 k) (b 0 k)
              else if Nat.eqb j k then xorb (a 0 k) (b 0 k) else false)).
      { intros j Hj. destruct (Nat.eq_dec k j) as [<-|Hne].
        - rewrite !eqb_refl_nat.
          assert (Ekt : Nat.eqb k t = false) by (apply Nat.eqb_neq; intro Heq; rewrite <- Heq, HBk in HBt; discriminate).
          rewrite Ekt. destruct (a 0 k); destruct (b 0 k); reflexivity.
        - assert (Ekj : Nat.eqb k j = false) by (apply Nat.eqb_neq; exact Hne).
          assert (Ejk : Nat.eqb j k = false) by (apply Nat.eqb_neq; lia).
          rewrite Ekj, Ejk. unfold dom_rbit. rewrite Ekj, bit_at_zip_xorb; [|exact Htape].
          pose proof (dom_pair_idx_lt N k j Hk Hj) as Hpr.
          assert (Hprb : (dom_pair_idx N k j <? N * N) = true) by (apply Nat.ltb_lt; exact Hpr).
          rewrite Hprb.
          assert (Hdf_eq : df (dom_pair_idx N k j) = if Nat.eqb j t then xorb (a 0 k) (b 0 k) else false).
          { unfold df, ref_sni_df, dom_pair_idx. cbv zeta. change (S n) with N.
            destruct (Nat.ltb k j) eqn:Lkj.
            - destruct (div_mod_pair_id N k j Hk Hj) as [Hd2 Hm2]. rewrite Hd2, Hm2, Lkj, HBk, Hcov. simpl.
              fold t. destruct (Nat.eqb j t); [reflexivity|].
              destruct (B j) eqn:HBj; simpl; [|reflexivity].
              destruct (ref_sni_target_spec n ps B j Hsz_n HBj) as [_ [HBtj _]].
              assert (Ekt : Nat.eqb k (ref_sni_target n ps B j) = false)
                by (apply Nat.eqb_neq; intro Heq; rewrite <- Heq, HBk in HBtj; discriminate).
              rewrite Ekt, andb_false_r. reflexivity.
            - assert (Hjk : j < k) by (apply Nat.ltb_ge in Lkj; lia).
              destruct (div_mod_pair_id N j k Hj Hk) as [Hd2 Hm2]. rewrite Hd2, Hm2.
              assert (Ljk : (j <? k) = true) by (apply Nat.ltb_lt; exact Hjk). rewrite Ljk.
              destruct (B j) eqn:HBj; simpl.
              + destruct (ref_sni_target_spec n ps B j Hsz_n HBj) as [_ [HBtj _]].
                assert (Ekt : Nat.eqb k (ref_sni_target n ps B j) = false)
                  by (apply Nat.eqb_neq; intro Heq; rewrite <- Heq, HBk in HBtj; discriminate).
                rewrite Ekt, andb_false_r, HBk, Hcov. simpl. fold t. reflexivity.
              + rewrite HBk, Hcov. simpl. fold t. reflexivity. }
          rewrite Hdf_eq. destruct (bit_at tape (dom_pair_idx N k j));
            destruct (if Nat.eqb j t then xorb (a 0 k) (b 0 k) else false); reflexivity. }
      transitivity (xor_sum_upto (fun j =>
        xorb (if Nat.eqb k j then a 0 k else dom_rbit N tape k j)
             (xorb (if Nat.eqb j t then xorb (a 0 k) (b 0 k) else false)
                   (if Nat.eqb j k then xorb (a 0 k) (b 0 k) else false))) N).
      { apply xor_sum_upto_ext. intros j Hj. etransitivity; [exact (Hrow j Hj)|].
        destruct (Nat.eqb j t) eqn:Ejt; destruct (Nat.eqb j k) eqn:Ejk.
        - apply eqb_sound_nat in Ejt. apply eqb_sound_nat in Ejk. rewrite <- Ejt, Ejk, HBk in HBt. discriminate.
        - destruct (if k =? j then a 0 k else dom_rbit N tape k j); destruct (a 0 k); destruct (b 0 k); reflexivity.
        - destruct (if k =? j then a 0 k else dom_rbit N tape k j); destruct (a 0 k); destruct (b 0 k); reflexivity.
        - destruct (if k =? j then a 0 k else dom_rbit N tape k j); destruct (a 0 k); destruct (b 0 k); reflexivity. }
      rewrite xor_sum_upto_xorb, xor_sum_upto_xorb.
      rewrite (xor_sum_upto_point N t (xorb (a 0 k) (b 0 k)) Ht_lt).
      rewrite (xor_sum_upto_point N k (xorb (a 0 k) (b 0 k)) Hk).
      destruct (xor_sum_upto (fun j => if k =? j then a 0 k else dom_rbit N tape k j) N);
      destruct (a 0 k); destruct (b 0 k); reflexivity.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem sni_refresh_is_strong_pini :
  forall n d, StrongPINI (sni_refresh_gadget n) ex_robust d.
Proof.
  intros n d ps B Hw _.
  set (N := S n) in *.
  destruct (Nat.ltb (split_size (sni_refresh_gadget n) ps B) N) eqn:Hlt.
  - assert (Hsz : Nat.leb (split_size (sni_refresh_gadget n) ps B) n = true)
      by (apply Nat.leb_le; apply Nat.ltb_lt in Hlt; unfold N in *; lia).
    destruct (sni_refresh_is_sni n n (le_n n) ps B Hw Hsz) as [I [Hb Hsim]].
    exists (I 0). split; [exact (Hb 0 eq_refl)|].
    intros a b Hagree. apply Hsim.
    intros j k Hj Hk HI. apply Hagree; [exact Hj | exact Hk|].
    unfold union_shares. destruct j as [|j]; [rewrite HI; reflexivity | discriminate].
  - apply Nat.ltb_ge in Hlt.
    exists (fun k => negb (B k)). split.
    + apply Nat.leb_le.
      pose proof (count_filter_split B (upto N)) as Hsum.
      rewrite count_upto in Hsum.
      unfold split_size, selected_outputs in Hlt. change (gd_shares (sni_refresh_gadget n)) with N in *.
      lia.
    + intros a b Hagree. apply identical_views_are_identically_distributed. intros tape.
      assert (Heq_ab : forall j k, j < 1 -> k < N -> a j k = b j k).
      { intros j k Hj Hk. apply Hagree; [apply Nat.ltb_lt; exact Hj | apply Nat.ltb_lt; exact Hk|].
        unfold union_shares. destruct (B k); reflexivity. }
      unfold split_view. f_equal.
      * unfold internal_view, probe_set. apply support_map_ext. intros o Ho.
        apply member_flat_map_over_inv in Ho. destruct Ho as [p [Hp Ho]].
        assert (Hpw_lt : p_wire p < ref_wire_count n).
        { clear -Hw Hp. unfold wires_exist in Hw.
          induction ps as [|q r IH]; simpl in *; [contradiction|].
          apply andb_prop in Hw. destruct Hw as [Hq Hr].
          destruct Hp as [->|Hp]; [apply Nat.ltb_lt in Hq; rewrite circuit_of_fun_count in Hq; exact Hq | exact (IH Hr Hp)]. }
        unfold ex_robust, sni_refresh_gadget in Ho; cbn [gd_circuit] in Ho; rewrite circuit_of_fun_count in Ho.
        assert (Ho_cases : exists s, ProofSupport.Member s (stable_sources (circuit_of_fun (ref_wire_count n) (ref_gate n)) (ref_wire_count n) (p_wire p)) /\
          (o = obs_at s (p_cycle p) \/ o = obs_at s (prev_cycle (p_cycle p)))).
        { clear -Ho. induction (stable_sources (circuit_of_fun (ref_wire_count n) (ref_gate n)) (ref_wire_count n) (p_wire p)) as [|s r IH];
            cbn [flat_map_over] in Ho; [contradiction|].
          destruct Ho as [Ho1|[Ho2|Ho]]; [exists s; split; [left; reflexivity | left; first [exact Ho1 | symmetry; exact Ho1]]
            | exists s; split; [left; reflexivity | right; first [exact Ho2 | symmetry; exact Ho2]]
            | destruct (IH Ho) as [s0 [Hs0 Hdec]]; exists s0; split; [right; exact Hs0 | exact Hdec]]. }
        destruct Ho_cases as [s [Hs Hdec]].
        assert (Hs_lt : s < ref_wire_count n).
        { rewrite ref_stable_sources in Hs; [|exact Hpw_lt]. cbv zeta in Hs. change (S n) with N in Hs.
          destruct (Nat.ltb (p_wire p) (N + 2 * N * N)) eqn:Ep1; [cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s; exact Hpw_lt|].
          apply Nat.ltb_ge in Ep1.
          destruct (member_map_over_inv _ _ _ Hs) as [j [Hj <-]].
          apply member_upto_lt in Hj. unfold ref_wire_count in *; unfold N in *; nia. }
        assert (Hval : forall cyc, gd_value (sni_refresh_gadget n) a tape cyc s = gd_value (sni_refresh_gadget n) b tape cyc s).
        { intros cyc. rewrite !ref_value_eq; [|exact Hs_lt | exact Hs_lt].
          unfold ref_eval. cbv zeta. change (S n) with N.
          destruct (Nat.ltb s N) eqn:L0; [apply Heq_ab; [lia | apply Nat.ltb_lt; exact L0]|].
          destruct (Nat.ltb s (N + N * N)) eqn:L1; [reflexivity|].
          destruct (Nat.ltb s (N + 2 * N * N)) eqn:L2.
          - destruct cyc as [|cyc]; [reflexivity|].
            destruct (Nat.eqb ((s - (N + N * N)) / N) ((s - (N + N * N)) mod N)); [|reflexivity].
            apply Heq_ab; [lia|].
            apply Nat.ltb_ge in L1; apply Nat.ltb_lt in L2.
            destruct (div_mod_pair_bound N (s - (N + N * N)) ltac:(lia) ltac:(lia)) as [Hi _]. exact Hi.
          - destruct cyc as [|cyc]; [reflexivity|].
            apply xor_sum_upto_ext. intros j _.
            destruct (Nat.eqb (s - (N + 2 * N * N)) j); [|reflexivity].
            apply Heq_ab; [lia|].
            apply Nat.ltb_ge in L2. unfold ref_wire_count in Hs_lt. unfold N in *; lia. }
        destruct Hdec as [->| ->]; simpl; apply Hval.
      * unfold output_view, selected_outputs. apply support_map_ext. intros k Hk.
        change (gd_shares (sni_refresh_gadget n)) with N in Hk.
        apply support_filter_member in Hk. apply member_upto_lt in Hk.
        replace (gd_out (sni_refresh_gadget n) k) with (ref_out_wire n k) by reflexivity.
        rewrite !ref_value_eq; [|unfold ref_out_wire, ref_wire_count; unfold N in *; lia
                               |unfold ref_out_wire, ref_wire_count; unfold N in *; lia].
        unfold ref_eval, ref_out_wire. cbv zeta. change (S n) with N.
        assert (L0 : (N + 2 * N * N + k <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
        assert (L1 : (N + 2 * N * N + k <? N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
        assert (L2 : (N + 2 * N * N + k <? N + 2 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
        rewrite L0, L1, L2.
        destruct (gd_read (sni_refresh_gadget n)) eqn:Hrd; [unfold sni_refresh_gadget in Hrd; cbn [gd_read] in Hrd; discriminate|].
        replace (N + 2 * N * N + k - (N + 2 * N * N)) with k by lia.
        apply xor_sum_upto_ext. intros j _.
        destruct (Nat.eqb k j); [apply Heq_ab; lia | reflexivity].
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem sni_refresh_is_pini :
  forall n d, PINI (sni_refresh_gadget n) ex_robust d.
Proof.
  intros n d. apply strong_pini_implies_pini. apply sni_refresh_is_strong_pini.
Qed.

(* HPC1 AND: sequential composition of SNI mask refresh on one operand followed by DOM-indep AND. *)
Definition hpc1_and_gadget (n : nat) : Gadget :=
  seq_gadget (sni_refresh_gadget n) (dom_and_gadget n) eq_refl.

Lemma hpc1_and_well_formed :
  forall n, gadget_well_formed (hpc1_and_gadget n).
Proof.
  intros n. unfold hpc1_and_gadget.
  apply seq_gadget_well_formed; [reflexivity | apply sni_refresh_well_formed | apply dom_and_well_formed].
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem hpc1_and_correct :
  forall n (a : ShareMatrix (hpc1_and_gadget n)) tape,
    xor_sum_upto (fun k => gd_value (hpc1_and_gadget n) a tape (gd_read (hpc1_and_gadget n))
      (gd_out (hpc1_and_gadget n) k)) (S n) =
    andb (xor_sum_upto (a 0) (S n)) (xor_sum_upto (a 1) (S n)).
Proof.
  intros n a [t1 t2].
  destruct (sni_refresh_well_formed n) as [Hwf1 _].
  destruct (dom_and_well_formed n) as [Hwf2 [_ Hout2]].
  set (a1 := (fun j k => a j k) : ShareMatrix (sni_refresh_gadget n)).
  set (a2 := (fun j k =>
    match j with
    | 0 => gd_value (sni_refresh_gadget n) a1 t1 (gd_read (sni_refresh_gadget n)) (gd_out (sni_refresh_gadget n) k)
    | S r => a (1 + r) k
    end) : ShareMatrix (dom_and_gadget n)).
  assert (Hops_ext : forall o args,
    @combine_ops gf2_sharing bool_ops (fun o0 args0 => bool_ops o0 (map_over (fun x => x) args0)) o args =
    @combine_ops gf2_sharing bool_ops bool_ops o args).
  { intros o args. unfold combine_ops. destruct (Nat.even o); [reflexivity | rewrite map_over_id_val; reflexivity]. }
  transitivity (xor_sum_upto (fun k =>
    gd_value (dom_and_gadget n) a2 t2 (gd_read (dom_and_gadget n)) (gd_out (dom_and_gadget n) k)) (S n)).
  - apply xor_sum_upto_ext. intros k Hk.
    unfold gd_value, hpc1_and_gadget, seq_gadget. cbn [gd_share gd_ops gd_circuit gd_out gd_read gd_assign gd_start val_cast].
    rewrite (value_at_ops_ext gf2_sharing _ (@combine_ops gf2_sharing bool_ops bool_ops) _ _ _ _ _ Hops_ext).
    lazymatch goal with |- context [fun w : nat => combine_start ?n0 ?f ?g w] =>
      change (fun w : nat => combine_start n0 f g w) with (combine_start n0 f g) end.
    lazymatch goal with |- context [fun cyc i : nat => combine_assign ?f ?g cyc i] =>
      change (fun cyc i : nat => combine_assign f g cyc i) with (combine_assign f g) end.
    etransitivity; [apply (value_at_combine_r gf2_sharing); [exact Hwf1 | exact Hwf2 | apply Hout2; exact Hk]|].
    reflexivity.
  - rewrite dom_and_correct. unfold a2.
    rewrite sni_refresh_correct.
    unfold a1. simpl (1 + 0). rewrite gf2_mul_comm. reflexivity.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem hpc1_and_is_pini :
  forall n d, PINI (hpc1_and_gadget n) ex_robust d.
Proof.
  intros n d. unfold hpc1_and_gadget.
  apply pini_seq_compose; try reflexivity.
  - apply sni_refresh_well_formed.
  - apply dom_and_well_formed.
  - apply counting_has_counting_mass.
  - apply counting_has_counting_mass.
  - exact ex_robust_is_local.
  - apply sni_refresh_is_pini.
  - apply dom_and_is_pini.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem hpc1_and_is_sni :
  forall n d, d <= n -> SNI (hpc1_and_gadget n) ex_robust d.
Proof.
  intros n d Hd. unfold hpc1_and_gadget.
  apply ni_sni_compose; try reflexivity.
  - apply sni_refresh_well_formed.
  - apply dom_and_well_formed.
  - apply counting_has_counting_mass.
  - apply counting_has_counting_mass.
  - exact ex_robust_is_local.
  - apply sni_implies_ni. apply sni_refresh_is_sni; exact Hd.
  - apply dom_and_is_sni; exact Hd.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem hpc1_and_is_strong_pini :
  forall n d, d <= n -> StrongPINI (hpc1_and_gadget n) ex_robust d.
Proof.
  intros n d Hd ps B Hw _.
  set (N := S n) in *.
  destruct (Nat.ltb (split_size (hpc1_and_gadget n) ps B) N) eqn:Hlt.
  - assert (Hsz : split_size (hpc1_and_gadget n) ps B <= n)
      by (apply Nat.ltb_lt in Hlt; unfold N in *; lia).
    unfold hpc1_and_gadget in Hw. cbn [gd_circuit] in Hw.
    set (c1 := gd_circuit (sni_refresh_gadget n)).
    set (ps1 := split_probes_l (wire_count c1) ps).
    set (ps2 := split_probes_r (wire_count c1) ps).
    destruct (split_probes_wires_exist c1 (gd_circuit (dom_and_gadget n)) ps Hw) as [Hw1 Hw2].
    pose proof (split_probes_count (wire_count c1) ps) as Hcnt.
    destruct (dom_and_is_pini n (count_of ps2) ps2 B Hw2 (Nat.leb_refl _)) as [I2 [Hb2 Hsim2]].
    set (B_mid := fun k => orb (I2 0 k) (B k)).
    assert (Hsz1 : Nat.leb (split_size (sni_refresh_gadget n) ps1 B_mid) n = true).
    { apply Nat.leb_le. unfold split_size, selected_outputs in *.
      change (gd_shares (sni_refresh_gadget n)) with N.
      change (gd_shares (hpc1_and_gadget n)) with N in Hsz.
      pose proof (count_filter_orb (I2 0) B (upto N)) as Horb.
      pose proof (Hb2 0 eq_refl) as Hb20. apply Nat.leb_le in Hb20.
      unfold card_in in Hb20. change (gd_shares (dom_and_gadget n)) with N in Hb20.
      unfold B_mid. unfold ps1, ps2 in *. lia. }
    destruct (sni_refresh_is_sni n n (le_n n) ps1 B_mid Hw1 Hsz1) as [I1 [Hb1 Hsim1]].
    exists (fun k => orb (I1 0 k) (I2 1 k)). split.
    + apply Nat.leb_le.
      pose proof (count_filter_orb (I1 0) (I2 1) (upto N)) as Horb.
      pose proof (Hb1 0 eq_refl) as Hb10. pose proof (Hb2 1 eq_refl) as Hb21.
      apply Nat.leb_le in Hb10; apply Nat.leb_le in Hb21.
      unfold card_in in *. change (gd_shares (sni_refresh_gadget n)) with N in Hb10.
      change (gd_shares (dom_and_gadget n)) with N in Hb21.
      change (gd_shares (hpc1_and_gadget n)) with N. unfold ps1, ps2 in *. lia.
    + intros a b Hagree.
      apply (seq_simulable_compose (sni_refresh_gadget n) (dom_and_gadget n) eq_refl ex_robust ps B
               I1 (union_shares I2 B) B_mid
               eq_refl (sni_refresh_well_formed n) (dom_and_well_formed n)
               (counting_has_counting_mass _ _) (counting_has_counting_mass _ _)
               ex_robust_is_local Hw).
      * intros k _ HI. exact HI.
      * exact Hsim1.
      * exact Hsim2.
      * intros j k Hj Hk Hm. apply Hagree; [exact Hj | exact Hk|].
        unfold union_shares, seq_merge_shares in *.
        change (gd_inputs (sni_refresh_gadget n)) with 1 in Hm.
        destruct (Nat.ltb j 1) eqn:Ej.
        -- assert (Hj0 : j = 0) by (apply Nat.ltb_lt in Ej; lia); subst j.
           rewrite Hm. reflexivity.
        -- assert (Hj1 : S (j - 1) = 1) by (simpl in Hj; apply Nat.ltb_lt in Hj; apply Nat.ltb_ge in Ej; lia).
           rewrite Hj1 in Hm. unfold union_shares in Hm. apply orb_prop in Hm.
           destruct Hm as [H21 | HB]; [rewrite H21; destruct (I1 0 k); reflexivity | rewrite HB; destruct (I1 0 k || I2 1 k); reflexivity].
  - apply Nat.ltb_ge in Hlt.
    exists (fun k => negb (B k)). split.
    + apply Nat.leb_le.
      pose proof (count_filter_split B (upto N)) as Hsum.
      rewrite count_upto in Hsum.
      unfold split_size, selected_outputs in Hlt. change (gd_shares (hpc1_and_gadget n)) with N in *.
      lia.
    + unfold hpc1_and_gadget in Hw. cbn [gd_circuit] in Hw.
      set (c1 := gd_circuit (sni_refresh_gadget n)).
      set (ps1 := split_probes_l (wire_count c1) ps).
      set (ps2 := split_probes_r (wire_count c1) ps).
      destruct (split_probes_wires_exist c1 (gd_circuit (dom_and_gadget n)) ps Hw) as [Hw1 Hw2].
      destruct (sni_refresh_is_pini n (count_of ps1) ps1 (fun _ => true) Hw1 (Nat.leb_refl _)) as [I1 [_ Hsim1]].
      destruct (dom_and_is_pini n (count_of ps2) ps2 B Hw2 (Nat.leb_refl _)) as [I2 [_ Hsim2]].
      intros a b Hagree.
      apply (seq_simulable_compose (sni_refresh_gadget n) (dom_and_gadget n) eq_refl ex_robust ps B
               (union_shares I1 (fun _ => true)) (union_shares I2 B) (fun _ => true)
               eq_refl (sni_refresh_well_formed n) (dom_and_well_formed n)
               (counting_has_counting_mass _ _) (counting_has_counting_mass _ _)
               ex_robust_is_local Hw).
      * intros k _ _. reflexivity.
      * exact Hsim1.
      * exact Hsim2.
      * intros j k Hj Hk _. apply Hagree; [exact Hj | exact Hk|].
        unfold union_shares. destruct (B k); reflexivity.
Qed.

(* HPC2 AND (Cassiers et al. CHES 2021): 2-stage registered cross-domain AND
   using reg_a_i, reg_v_{i,j} = b_j ^ r_{i,j}, reg_u_{i,j} = (~a_i) & r_{i,j},
   and reg_w_{i,j} = (reg_a_i & reg_v_{i,j}) ^ reg_u_{i,j}. *)
Definition hpc2_wire_count (n : nat) : nat :=
  let N := S n in 5 * N + 8 * N * N.

Definition hpc2_out_wire (n i : nat) : nat :=
  let N := S n in 4 * N + 8 * N * N + i.

Definition hpc2_gate (n w : nat) : Gate :=
  let N := S n in
  if Nat.ltb w (2 * N + N * N) then g_in w
  else if Nat.ltb w (3 * N + N * N) then g_reg (w - (2 * N + N * N))
  else if Nat.ltb w (4 * N + N * N) then g_op 4 ((w - (3 * N + N * N)) :: nil)
  else if Nat.ltb w (4 * N + 2 * N * N) then
    let p := w - (4 * N + N * N) in
    let i := p / N in let j := p mod N in
    if Nat.eqb i j then g_op 2 ((N + j) :: nil)
    else g_op 2 ((N + j) :: (2 * N + dom_pair_idx N i j) :: nil)
  else if Nat.ltb w (4 * N + 3 * N * N) then g_reg (w - N * N)
  else if Nat.ltb w (4 * N + 4 * N * N) then
    let p := w - (4 * N + 3 * N * N) in
    let i := p / N in let j := p mod N in
    if Nat.eqb i j then g_op 0 nil
    else g_op 3 ((3 * N + N * N + i) :: (2 * N + dom_pair_idx N i j) :: nil)
  else if Nat.ltb w (4 * N + 5 * N * N) then g_reg (w - N * N)
  else if Nat.ltb w (4 * N + 6 * N * N) then
    let p := w - (4 * N + 5 * N * N) in
    let i := p / N in
    g_op 3 ((2 * N + N * N + i) :: (4 * N + 2 * N * N + p) :: nil)
  else if Nat.ltb w (4 * N + 7 * N * N) then
    let p := w - (4 * N + 6 * N * N) in
    g_op 2 ((4 * N + 5 * N * N + p) :: (4 * N + 4 * N * N + p) :: nil)
  else if Nat.ltb w (4 * N + 8 * N * N) then g_reg (w - N * N)
  else
    let i := w - (4 * N + 8 * N * N) in
    g_op 2 (map_over (fun j => 4 * N + 7 * N * N + i * N + j) (upto N)).

Definition hpc2_and_gadget (n : nat) : Gadget :=
  let N := S n in {|
  gd_share := gf2_sharing;
  gd_prob := bit_tapes (N * N);
  gd_circuit := circuit_of_fun (hpc2_wire_count n) (hpc2_gate n);
  gd_ops := bool_ops;
  gd_inputs := 2;
  gd_shares := N;
  gd_out := hpc2_out_wire n;
  gd_read := 2;
  gd_assign := fun a tape _ i =>
    if Nat.ltb i N then a 0 i
    else if Nat.ltb i (2 * N) then a 1 (i - N)
    else bit_at tape (i - 2 * N);
  gd_start := fun _ _ _ => false
|}.

Lemma hpc2_and_well_formed :
  forall n, gadget_well_formed (hpc2_and_gadget n).
Proof.
  intros n. set (N := S n). split; [|split].
  - unfold hpc2_and_gadget; cbn [gd_circuit].
    apply well_formed_circuit_of_fun. intros w Hw.
    unfold hpc2_wire_count in Hw. change (S n) with N in Hw.
    unfold hpc2_gate. cbv zeta. change (S n) with N.
    destruct (Nat.ltb w (2 * N + N * N)) eqn:E0; [reflexivity|]. apply Nat.ltb_ge in E0.
    destruct (Nat.ltb w (3 * N + N * N)) eqn:E1;
      [apply Nat.ltb_lt in E1; cbn [gate_well_formed]; apply Nat.ltb_lt; unfold hpc2_wire_count; unfold N in *; nia|].
    apply Nat.ltb_ge in E1.
    destruct (Nat.ltb w (4 * N + N * N)) eqn:E2;
      [apply Nat.ltb_lt in E2; cbn [gate_well_formed all_of ProofSupport.all_of]; apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity]|].
    apply Nat.ltb_ge in E2.
    destruct (Nat.ltb w (4 * N + 2 * N * N)) eqn:E3.
    + apply Nat.ltb_lt in E3.
      destruct (div_mod_pair_bound N (w - (4 * N + N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
      destruct (Nat.eqb _ _); cbn [gate_well_formed all_of ProofSupport.all_of];
        [apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity]|].
      pose proof (dom_pair_idx_lt N _ _ Hi Hj).
      apply andb_true_intro; split; [apply Nat.ltb_lt; lia|].
      apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity].
    + apply Nat.ltb_ge in E3.
      destruct (Nat.ltb w (4 * N + 3 * N * N)) eqn:E4;
        [apply Nat.ltb_lt in E4; cbn [gate_well_formed]; apply Nat.ltb_lt; unfold hpc2_wire_count; unfold N in *; nia|].
      apply Nat.ltb_ge in E4.
      destruct (Nat.ltb w (4 * N + 4 * N * N)) eqn:E5.
      * apply Nat.ltb_lt in E5.
        destruct (div_mod_pair_bound N (w - (4 * N + 3 * N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
        destruct (Nat.eqb _ _); cbn [gate_well_formed all_of ProofSupport.all_of]; [reflexivity|].
        pose proof (dom_pair_idx_lt N _ _ Hi Hj).
        apply andb_true_intro; split; [apply Nat.ltb_lt; lia|].
        apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity].
      * apply Nat.ltb_ge in E5.
        destruct (Nat.ltb w (4 * N + 5 * N * N)) eqn:E6;
          [apply Nat.ltb_lt in E6; cbn [gate_well_formed]; apply Nat.ltb_lt; unfold hpc2_wire_count; unfold N in *; nia|].
        apply Nat.ltb_ge in E6.
        destruct (Nat.ltb w (4 * N + 6 * N * N)) eqn:E7.
        -- apply Nat.ltb_lt in E7.
           destruct (div_mod_pair_bound N (w - (4 * N + 5 * N * N)) ltac:(lia) ltac:(lia)) as [Hi _].
           cbn [gate_well_formed all_of ProofSupport.all_of].
           apply andb_true_intro; split; [apply Nat.ltb_lt; lia|].
           apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity].
        -- apply Nat.ltb_ge in E7.
           destruct (Nat.ltb w (4 * N + 7 * N * N)) eqn:E8;
             [apply Nat.ltb_lt in E8; cbn [gate_well_formed all_of ProofSupport.all_of];
              apply andb_true_intro; split; [apply Nat.ltb_lt; lia|];
              apply andb_true_intro; split; [apply Nat.ltb_lt; lia | reflexivity]|].
           apply Nat.ltb_ge in E8.
           destruct (Nat.ltb w (4 * N + 8 * N * N)) eqn:E9;
             [apply Nat.ltb_lt in E9; cbn [gate_well_formed]; apply Nat.ltb_lt; unfold hpc2_wire_count; unfold N in *; nia|].
           apply Nat.ltb_ge in E9. cbn [gate_well_formed].
           assert (Hall : forall u, (forall j, ProofSupport.Member j u -> j < N) ->
             all_of (fun a => a <? w) (map_over (fun j => 4 * N + 7 * N * N + (w - (4 * N + 8 * N * N)) * N + j) u) = true).
           { intros u Hu. induction u as [|x ur IHu]; simpl; [reflexivity|].
             apply andb_true_intro; split; [apply Nat.ltb_lt; pose proof (Hu x (or_introl eq_refl)); nia | apply IHu; intros y Hy; apply Hu; right; exact Hy]. }
           apply Hall. intros j Hj. apply member_upto_lt; exact Hj.
  - simpl; lia.
  - intros k Hk. simpl in *. rewrite circuit_of_fun_count.
    unfold hpc2_out_wire, hpc2_wire_count, N in *. lia.
Qed.

Definition hpc2_eval (n : nat) (a b : nat -> bool) (tape : list bool) (cyc w : nat) : bool :=
  let N := S n in
  if Nat.ltb w N then a w
  else if Nat.ltb w (2 * N) then b (w - N)
  else if Nat.ltb w (2 * N + N * N) then bit_at tape (w - 2 * N)
  else if Nat.ltb w (3 * N + N * N) then
    match cyc with 0 => false | S _ => a (w - (2 * N + N * N)) end
  else if Nat.ltb w (4 * N + N * N) then
    negb (a (w - (3 * N + N * N)))
  else if Nat.ltb w (4 * N + 2 * N * N) then
    let p := w - (4 * N + N * N) in
    xorb (b (p mod N)) (dom_rbit N tape (p / N) (p mod N))
  else if Nat.ltb w (4 * N + 3 * N * N) then
    match cyc with
    | 0 => false
    | S _ =>
      let p := w - (4 * N + 2 * N * N) in
      xorb (b (p mod N)) (dom_rbit N tape (p / N) (p mod N))
    end
  else if Nat.ltb w (4 * N + 4 * N * N) then
    let p := w - (4 * N + 3 * N * N) in
    andb (negb (a (p / N))) (dom_rbit N tape (p / N) (p mod N))
  else if Nat.ltb w (4 * N + 5 * N * N) then
    match cyc with
    | 0 => false
    | S _ =>
      let p := w - (4 * N + 4 * N * N) in
      andb (negb (a (p / N))) (dom_rbit N tape (p / N) (p mod N))
    end
  else if Nat.ltb w (4 * N + 6 * N * N) then
    match cyc with
    | 0 => false
    | S _ =>
      let p := w - (4 * N + 5 * N * N) in
      andb (a (p / N)) (xorb (b (p mod N)) (dom_rbit N tape (p / N) (p mod N)))
    end
  else if Nat.ltb w (4 * N + 7 * N * N) then
    match cyc with
    | 0 => false
    | S _ =>
      let p := w - (4 * N + 6 * N * N) in
      xorb (andb (a (p / N)) (b (p mod N))) (dom_rbit N tape (p / N) (p mod N))
    end
  else if Nat.ltb w (4 * N + 8 * N * N) then
    match cyc with
    | 0 | 1 => false
    | S (S _) =>
      let p := w - (4 * N + 7 * N * N) in
      xorb (andb (a (p / N)) (b (p mod N))) (dom_rbit N tape (p / N) (p mod N))
    end
  else
    match cyc with
    | 0 | 1 => false
    | S (S _) =>
      let i := w - (4 * N + 8 * N * N) in
      xor_sum_upto (fun j => xorb (andb (a i) (b j)) (dom_rbit N tape i j)) N
    end.

Lemma hpc2_value_eq :
  forall n (a : ShareMatrix (hpc2_and_gadget n)) tape cyc w,
    w < hpc2_wire_count n ->
    gd_value (hpc2_and_gadget n) a tape cyc w = hpc2_eval n (a 0) (a 1) tape cyc w.
Proof.
  intros n a tape cyc w Hw.
  destruct (hpc2_and_well_formed n) as [Hwf _].
  unfold hpc2_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
  set (N := S n) in *.
  set (ins := fun (_ : nat) (i : nat) =>
    if Nat.ltb i N then a 0 i else if Nat.ltb i (2 * N) then a 1 (i - N) else bit_at tape (i - 2 * N)).
  assert (Hpair : forall t,
    (forall w0, w0 < hpc2_wire_count n ->
      regs_at gf2_sharing bool_ops (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
        (fun _ => false) ins t w0 =
      match t with
      | 0 => false
      | S t' =>
        if Nat.ltb w0 (2 * N + N * N) then false
        else if Nat.ltb w0 (3 * N + N * N) then a 0 (w0 - (2 * N + N * N))
        else if Nat.ltb w0 (4 * N + 2 * N * N) then false
        else if Nat.ltb w0 (4 * N + 3 * N * N) then
          let p := w0 - (4 * N + 2 * N * N) in xorb (a 1 (p mod N)) (dom_rbit N tape (p / N) (p mod N))
        else if Nat.ltb w0 (4 * N + 4 * N * N) then false
        else if Nat.ltb w0 (4 * N + 5 * N * N) then
          let p := w0 - (4 * N + 4 * N * N) in andb (negb (a 0 (p / N))) (dom_rbit N tape (p / N) (p mod N))
        else if Nat.ltb w0 (4 * N + 7 * N * N) then false
        else if Nat.ltb w0 (4 * N + 8 * N * N) then
          match t' with
          | 0 => false
          | S _ => let p := w0 - (4 * N + 7 * N * N) in xorb (andb (a 0 (p / N)) (a 1 (p mod N))) (dom_rbit N tape (p / N) (p mod N))
          end
        else false
      end) /\
    (forall w0, w0 < hpc2_wire_count n ->
      value_at gf2_sharing bool_ops (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
        (fun _ => false) ins t w0 =
      hpc2_eval n (a 0) (a 1) tape t w0)).
  { induction t as [|t [IHr IHv]].
    - assert (Hreg0 : forall w0, regs_at gf2_sharing bool_ops (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
        (fun _ => false) ins 0 w0 = false) by (intros; reflexivity).
      split; [intros w0 _; exact (Hreg0 w0)|].
      intros w0 Hw0.
      assert (Heval_in : forall u, u < 2 * N + N * N ->
        value_at gf2_sharing bool_ops (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
          (fun _ => false) ins 0 u =
        if Nat.ltb u N then a 0 u else if Nat.ltb u (2 * N) then a 1 (u - N) else bit_at tape (u - 2 * N)).
      { intros u Hu. rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
        rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
        unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
        assert (Eu : (u <? 2 * N + N * N) = true) by (apply Nat.ltb_lt; exact Hu). rewrite Eu.
        unfold ins; reflexivity. }
      assert (Heval_not : forall i, i < N ->
        value_at gf2_sharing bool_ops (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
          (fun _ => false) ins 0 (3 * N + N * N + i) =
        negb (a 0 i)).
      { intros i Hi. rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
        rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
        unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
        assert (E0 : (3 * N + N * N + i <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
        assert (E1 : (3 * N + N * N + i <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
        assert (E2 : (3 * N + N * N + i <? 4 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
        rewrite E0, E1, E2.
        replace (3 * N + N * N + i - (3 * N + N * N)) with i by lia.
        cbn [map_over ProofSupport.map_over bool_ops at_member].
        rewrite Heval_in; [|unfold N in *; nia].
        assert (Ei : (i <? N) = true) by (apply Nat.ltb_lt; exact Hi). rewrite Ei. reflexivity. }
      rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw0].
      rewrite gate_at_circuit_of_fun; [|exact Hw0].
      unfold hpc2_gate at 1, hpc2_eval. cbv zeta. change (S n) with N.
      destruct (Nat.ltb w0 (2 * N + N * N)) eqn:E0;
        [unfold ins; destruct (Nat.ltb w0 N); destruct (Nat.ltb w0 (2 * N)); reflexivity|].
      apply Nat.ltb_ge in E0.
      assert (L0 : (w0 <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
      assert (L1 : (w0 <? 2 * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
      rewrite L0, L1.
      destruct (Nat.ltb w0 (3 * N + N * N)) eqn:E1; [rewrite Hreg0; reflexivity|]. apply Nat.ltb_ge in E1.
      destruct (Nat.ltb w0 (4 * N + N * N)) eqn:E2.
      + apply Nat.ltb_lt in E2. cbn [map_over ProofSupport.map_over bool_ops at_member].
        rewrite Heval_in; [|unfold N in *; lia].
        assert (Li : (w0 - (3 * N + N * N) <? N) = true) by (apply Nat.ltb_lt; lia). rewrite Li. reflexivity.
      + apply Nat.ltb_ge in E2.
        destruct (Nat.ltb w0 (4 * N + 2 * N * N)) eqn:E3.
        * apply Nat.ltb_lt in E3.
          destruct (div_mod_pair_bound N (w0 - (4 * N + N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
          destruct (Nat.eqb ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N)) eqn:Eij;
            cbn [map_over ProofSupport.map_over bool_ops xor_fold]; rewrite Heval_in; [|unfold N in *; lia| |unfold N in *; lia].
          -- assert (G0 : (N + (w0 - (4 * N + N * N)) mod N <? N) = false) by (apply Nat.ltb_ge; lia).
             assert (G1 : (N + (w0 - (4 * N + N * N)) mod N <? 2 * N) = true) by (apply Nat.ltb_lt; lia).
             rewrite G0, G1. replace (N + (w0 - (4 * N + N * N)) mod N - N) with ((w0 - (4 * N + N * N)) mod N) by lia.
             unfold dom_rbit. rewrite Eij. repeat rewrite gf2_add_zero_r. reflexivity.
          -- pose proof (dom_pair_idx_lt N _ _ Hi Hj).
             rewrite Heval_in; [|unfold N in *; lia].
             assert (G0 : (N + (w0 - (4 * N + N * N)) mod N <? N) = false) by (apply Nat.ltb_ge; lia).
             assert (G1 : (N + (w0 - (4 * N + N * N)) mod N <? 2 * N) = true) by (apply Nat.ltb_lt; lia).
             assert (G2 : (2 * N + dom_pair_idx N ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N) <? N) = false) by (apply Nat.ltb_ge; lia).
             assert (G3 : (2 * N + dom_pair_idx N ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N) <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
             rewrite G0, G1, G2, G3.
             replace (N + (w0 - (4 * N + N * N)) mod N - N) with ((w0 - (4 * N + N * N)) mod N) by lia.
             replace (2 * N + dom_pair_idx N ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N) - 2 * N)
               with (dom_pair_idx N ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N)) by lia.
             unfold dom_rbit. rewrite Eij, gf2_add_zero_r. reflexivity.
        * apply Nat.ltb_ge in E3.
          destruct (Nat.ltb w0 (4 * N + 3 * N * N)) eqn:E4; [rewrite Hreg0; reflexivity|]. apply Nat.ltb_ge in E4.
          destruct (Nat.ltb w0 (4 * N + 4 * N * N)) eqn:E5.
          -- apply Nat.ltb_lt in E5.
             destruct (div_mod_pair_bound N (w0 - (4 * N + 3 * N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
             destruct (Nat.eqb ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N)) eqn:Eij.
             ++ unfold dom_rbit. rewrite Eij, andb_false_r. reflexivity.
             ++ cbn [map_over ProofSupport.map_over bool_ops at_member].
                rewrite Heval_not; [|exact Hi].
                pose proof (dom_pair_idx_lt N _ _ Hi Hj).
                rewrite Heval_in; [|unfold N in *; lia].
                assert (G0 : (2 * N + dom_pair_idx N ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N) <? N) = false) by (apply Nat.ltb_ge; lia).
                assert (G1 : (2 * N + dom_pair_idx N ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N) <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                rewrite G0, G1.
                replace (2 * N + dom_pair_idx N ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N) - 2 * N)
                  with (dom_pair_idx N ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N)) by lia.
                unfold dom_rbit. rewrite Eij. reflexivity.
          -- apply Nat.ltb_ge in E5.
             destruct (Nat.ltb w0 (4 * N + 5 * N * N)) eqn:E6; [rewrite Hreg0; reflexivity|]. apply Nat.ltb_ge in E6.
             destruct (Nat.ltb w0 (4 * N + 6 * N * N)) eqn:E7.
             ++ apply Nat.ltb_lt in E7.
                destruct (div_mod_pair_bound N (w0 - (4 * N + 5 * N * N)) ltac:(lia) ltac:(lia)) as [Hi _].
                cbn [map_over ProofSupport.map_over bool_ops at_member].
                rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
                rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
                unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                assert (G0 : (2 * N + N * N + (w0 - (4 * N + 5 * N * N)) / N <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (G1 : (2 * N + N * N + (w0 - (4 * N + 5 * N * N)) / N <? 3 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
                rewrite G0, G1, Hreg0. reflexivity.
             ++ apply Nat.ltb_ge in E7.
                destruct (Nat.ltb w0 (4 * N + 7 * N * N)) eqn:E8.
                ** apply Nat.ltb_lt in E8.
                   cbn [map_over ProofSupport.map_over bool_ops xor_fold].
                   rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
                   rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
                   unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                   assert (A0 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (A1 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (A2 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (A3 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (A4 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (A5 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (A6 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (A7 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 6 * N * N) = true) by (apply Nat.ltb_lt; lia).
                   rewrite A0, A1, A2, A3, A4, A5, A6, A7.
                   replace (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) - (4 * N + 5 * N * N)) with (w0 - (4 * N + 6 * N * N)) by lia.
                   destruct (div_mod_pair_bound N (w0 - (4 * N + 6 * N * N)) ltac:(lia) ltac:(lia)) as [Hi _].
                   cbn [map_over ProofSupport.map_over bool_ops at_member].
                   rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
                   rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
                   unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                   assert (B0 : (2 * N + N * N + (w0 - (4 * N + 6 * N * N)) / N <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (B1 : (2 * N + N * N + (w0 - (4 * N + 6 * N * N)) / N <? 3 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
                   rewrite B0, B1, Hreg0. cbn [andb xorb].
                   rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
                   rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
                   unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                   assert (C0 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (C1 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (C2 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (C3 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (C4 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (C5 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; lia).
                   assert (C6 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 5 * N * N) = true) by (apply Nat.ltb_lt; lia).
                   rewrite C0, C1, C2, C3, C4, C5, C6, Hreg0. reflexivity.
                ** apply Nat.ltb_ge in E8.
                   destruct (Nat.ltb w0 (4 * N + 8 * N * N)) eqn:E9; [rewrite Hreg0; reflexivity|].
                   apply Nat.ltb_ge in E9. unfold bool_ops.
                   assert (Hz : forall u, (forall j, ProofSupport.Member j u -> j < N) ->
                     xor_fold (map_over (fun x => value_at gf2_sharing bool_ops (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
                       (fun _ => false) ins 0 x)
                       (map_over (fun j => 4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j) u)) = false).
                   { induction u as [|j ur IHu]; intros Hu; [reflexivity|].
                     cbn [map_over ProofSupport.map_over xor_fold].
                     assert (Hj : j < N) by (apply Hu; left; reflexivity).
                     assert (Hwj : 4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j < hpc2_wire_count n)
                       by (unfold hpc2_wire_count in *; unfold N in *; nia).
                     rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hwj].
                     rewrite gate_at_circuit_of_fun; [|exact Hwj].
                     unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                     assert (D0 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; nia).
                     assert (D1 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; nia).
                     assert (D2 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; nia).
                     assert (D3 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; nia).
                     assert (D4 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; nia).
                     assert (D5 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; nia).
                     assert (D6 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; nia).
                     assert (D7 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 6 * N * N) = false) by (apply Nat.ltb_ge; nia).
                     assert (D8 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 7 * N * N) = false) by (apply Nat.ltb_ge; nia).
                     assert (D9 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 8 * N * N) = true)
                       by (apply Nat.ltb_lt; unfold hpc2_wire_count in *; unfold N in *; nia).
                     rewrite D0, D1, D2, D3, D4, D5, D6, D7, D8, D9, Hreg0.
                     apply IHu. intros y Hy. apply Hu; right; exact Hy. }
                   apply Hz. intros j Hj. apply member_upto_lt; exact Hj.
    - assert (HregS : forall w0, w0 < hpc2_wire_count n ->
        regs_at gf2_sharing bool_ops (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
          (fun _ => false) ins (S t) w0 =
        if Nat.ltb w0 (2 * N + N * N) then false
        else if Nat.ltb w0 (3 * N + N * N) then a 0 (w0 - (2 * N + N * N))
        else if Nat.ltb w0 (4 * N + 2 * N * N) then false
        else if Nat.ltb w0 (4 * N + 3 * N * N) then
          let p := w0 - (4 * N + 2 * N * N) in xorb (a 1 (p mod N)) (dom_rbit N tape (p / N) (p mod N))
        else if Nat.ltb w0 (4 * N + 4 * N * N) then false
        else if Nat.ltb w0 (4 * N + 5 * N * N) then
          let p := w0 - (4 * N + 4 * N * N) in andb (negb (a 0 (p / N))) (dom_rbit N tape (p / N) (p mod N))
        else if Nat.ltb w0 (4 * N + 7 * N * N) then false
        else if Nat.ltb w0 (4 * N + 8 * N * N) then
          match t with
          | 0 => false
          | S _ => let p := w0 - (4 * N + 7 * N * N) in xorb (andb (a 0 (p / N)) (a 1 (p mod N))) (dom_rbit N tape (p / N) (p mod N))
          end
        else false).
      { intros w0 Hw0. rewrite regs_at_succ_step, gate_at_circuit_of_fun; [|exact Hw0].
        unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
        destruct (Nat.ltb w0 (2 * N + N * N)) eqn:E0;
          [rewrite IHr; [destruct t; [reflexivity | rewrite E0; reflexivity] | exact Hw0]|].
        apply Nat.ltb_ge in E0.
        destruct (Nat.ltb w0 (3 * N + N * N)) eqn:E1.
        - apply Nat.ltb_lt in E1. rewrite IHv; [|unfold hpc2_wire_count; unfold N in *; nia].
          unfold hpc2_eval. cbv zeta. change (S n) with N.
          assert (Li : (w0 - (2 * N + N * N) <? N) = true) by (apply Nat.ltb_lt; lia). rewrite Li. reflexivity.
        - apply Nat.ltb_ge in E1.
          destruct (Nat.ltb w0 (4 * N + N * N)) eqn:E2;
            [rewrite IHr; [
               assert (G2 : (w0 <? 4 * N + 2 * N * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in E2; lia);
               destruct t; [rewrite G2; reflexivity |
               assert (G0 : (w0 <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; exact E0);
               assert (G1 : (w0 <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; exact E1);
               rewrite G0, G1, G2; reflexivity] | exact Hw0]|].
          apply Nat.ltb_ge in E2.
          destruct (Nat.ltb w0 (4 * N + 2 * N * N)) eqn:E3;
            [destruct (Nat.eqb ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N));
             (rewrite IHr; [destruct t; [reflexivity |
               assert (G0 : (w0 <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; exact E0);
               assert (G1 : (w0 <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; exact E1);
               rewrite G0, G1, E3; reflexivity] | exact Hw0])|].
          apply Nat.ltb_ge in E3.
          destruct (Nat.ltb w0 (4 * N + 3 * N * N)) eqn:E4.
          + apply Nat.ltb_lt in E4. rewrite IHv; [|unfold hpc2_wire_count; unfold N in *; nia].
            unfold hpc2_eval. cbv zeta. change (S n) with N.
            assert (G0 : (w0 - N * N <? N) = false) by (apply Nat.ltb_ge; lia).
            assert (G1 : (w0 - N * N <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
            assert (G2 : (w0 - N * N <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
            assert (G3 : (w0 - N * N <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
            assert (G4 : (w0 - N * N <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
            assert (G5 : (w0 - N * N <? 4 * N + 2 * N * N) = true) by (apply Nat.ltb_lt; lia).
            rewrite G0, G1, G2, G3, G4, G5.
            replace (w0 - N * N - (4 * N + N * N)) with (w0 - (4 * N + 2 * N * N)) by lia. reflexivity.
          + apply Nat.ltb_ge in E4.
            destruct (Nat.ltb w0 (4 * N + 4 * N * N)) eqn:E5;
              [destruct (Nat.eqb ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N));
               (rewrite IHr; [destruct t; [reflexivity |
                 assert (G0 : (w0 <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; exact E0);
                 assert (G1 : (w0 <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; exact E1);
                 assert (G2 : (w0 <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact E3);
                 assert (G3 : (w0 <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; exact E4);
                 rewrite G0, G1, G2, G3, E5; reflexivity] | exact Hw0])|].
            apply Nat.ltb_ge in E5.
            destruct (Nat.ltb w0 (4 * N + 5 * N * N)) eqn:E6.
            * apply Nat.ltb_lt in E6. rewrite IHv; [|unfold hpc2_wire_count; unfold N in *; nia].
              unfold hpc2_eval. cbv zeta. change (S n) with N.
              assert (G0 : (w0 - N * N <? N) = false) by (apply Nat.ltb_ge; lia).
              assert (G1 : (w0 - N * N <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
              assert (G2 : (w0 - N * N <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (G3 : (w0 - N * N <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (G4 : (w0 - N * N <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (G5 : (w0 - N * N <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (G6 : (w0 - N * N <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (G7 : (w0 - N * N <? 4 * N + 4 * N * N) = true) by (apply Nat.ltb_lt; lia).
              rewrite G0, G1, G2, G3, G4, G5, G6, G7.
              replace (w0 - N * N - (4 * N + 3 * N * N)) with (w0 - (4 * N + 4 * N * N)) by lia. reflexivity.
            * apply Nat.ltb_ge in E6.
              destruct (Nat.ltb w0 (4 * N + 6 * N * N)) eqn:E7;
                [rewrite IHr; [
                   assert (G6 : (w0 <? 4 * N + 7 * N * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in E7; lia);
                   destruct t; [rewrite G6; reflexivity |
                   assert (G0 : (w0 <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; exact E0);
                   assert (G1 : (w0 <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; exact E1);
                   assert (G2 : (w0 <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact E3);
                   assert (G3 : (w0 <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; exact E4);
                   assert (G4 : (w0 <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; exact E5);
                   assert (G5 : (w0 <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; exact E6);
                   rewrite G0, G1, G2, G3, G4, G5, G6; reflexivity] | exact Hw0]|].
              apply Nat.ltb_ge in E7.
              destruct (Nat.ltb w0 (4 * N + 7 * N * N)) eqn:E8;
                [rewrite IHr; [destruct t; [reflexivity |
                   assert (G0 : (w0 <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; exact E0);
                   assert (G1 : (w0 <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; exact E1);
                   assert (G2 : (w0 <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact E3);
                   assert (G3 : (w0 <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; exact E4);
                   assert (G4 : (w0 <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; exact E5);
                   assert (G5 : (w0 <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; exact E6);
                   rewrite G0, G1, G2, G3, G4, G5, E8; reflexivity] | exact Hw0]|].
              apply Nat.ltb_ge in E8.
              destruct (Nat.ltb w0 (4 * N + 8 * N * N)) eqn:E9.
              -- apply Nat.ltb_lt in E9. rewrite IHv; [|unfold hpc2_wire_count; unfold N in *; nia].
                 unfold hpc2_eval. cbv zeta. change (S n) with N.
                 assert (G0 : (w0 - N * N <? N) = false) by (apply Nat.ltb_ge; lia).
                 assert (G1 : (w0 - N * N <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                 assert (G2 : (w0 - N * N <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                 assert (G3 : (w0 - N * N <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                 assert (G4 : (w0 - N * N <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                 assert (G5 : (w0 - N * N <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
                 assert (G6 : (w0 - N * N <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; lia).
                 assert (G7 : (w0 - N * N <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; lia).
                 assert (G8 : (w0 - N * N <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; lia).
                 assert (G9 : (w0 - N * N <? 4 * N + 6 * N * N) = false) by (apply Nat.ltb_ge; lia).
                 assert (G10 : (w0 - N * N <? 4 * N + 7 * N * N) = true) by (apply Nat.ltb_lt; lia).
                 rewrite G0, G1, G2, G3, G4, G5, G6, G7, G8, G9, G10.
                 replace (w0 - N * N - (4 * N + 6 * N * N)) with (w0 - (4 * N + 7 * N * N)) by lia.
                 destruct t; reflexivity.
              -- apply Nat.ltb_ge in E9. rewrite IHr; [|exact Hw0].
                 destruct t; [reflexivity|].
                 assert (G0 : (w0 <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; exact E0).
                 assert (G1 : (w0 <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; exact E1).
                 assert (G2 : (w0 <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact E3).
                 assert (G3 : (w0 <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; exact E4).
                 assert (G4 : (w0 <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; exact E5).
                 assert (G5 : (w0 <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; exact E6).
                 assert (G6 : (w0 <? 4 * N + 7 * N * N) = false) by (apply Nat.ltb_ge; exact E8).
                 assert (G7 : (w0 <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; exact E9).
                 rewrite G0, G1, G2, G3, G4, G5, G6, G7. reflexivity. }
      split; [exact HregS|].
      assert (Heval_in : forall u, u < 2 * N + N * N ->
        value_at gf2_sharing bool_ops (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
          (fun _ => false) ins (S t) u =
        if Nat.ltb u N then a 0 u else if Nat.ltb u (2 * N) then a 1 (u - N) else bit_at tape (u - 2 * N)).
      { intros u Hu. rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
        rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
        unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
        assert (Eu : (u <? 2 * N + N * N) = true) by (apply Nat.ltb_lt; exact Hu). rewrite Eu.
        unfold ins; reflexivity. }
      assert (Heval_not : forall i, i < N ->
        value_at gf2_sharing bool_ops (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
          (fun _ => false) ins (S t) (3 * N + N * N + i) =
        negb (a 0 i)).
      { intros i Hi. rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
        rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
        unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
        assert (E0 : (3 * N + N * N + i <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
        assert (E1 : (3 * N + N * N + i <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
        assert (E2 : (3 * N + N * N + i <? 4 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
        rewrite E0, E1, E2.
        replace (3 * N + N * N + i - (3 * N + N * N)) with i by lia.
        cbn [map_over ProofSupport.map_over bool_ops at_member].
        rewrite Heval_in; [|unfold N in *; nia].
        assert (Ei : (i <? N) = true) by (apply Nat.ltb_lt; exact Hi). rewrite Ei. reflexivity. }
      intros w0 Hw0.
      rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw0].
      rewrite gate_at_circuit_of_fun; [|exact Hw0].
      unfold hpc2_gate at 1, hpc2_eval. cbv zeta. change (S n) with N.
      destruct (Nat.ltb w0 (2 * N + N * N)) eqn:E0;
        [unfold ins; destruct (Nat.ltb w0 N); destruct (Nat.ltb w0 (2 * N)); reflexivity|].
      apply Nat.ltb_ge in E0.
      assert (L0 : (w0 <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
      assert (L1 : (w0 <? 2 * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
      rewrite L0, L1.
      destruct (Nat.ltb w0 (3 * N + N * N)) eqn:E1.
      + rewrite HregS; [|exact Hw0].
        assert (G0 : (w0 <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; exact E0). rewrite G0, E1. reflexivity.
      + apply Nat.ltb_ge in E1.
        destruct (Nat.ltb w0 (4 * N + N * N)) eqn:E2.
        * apply Nat.ltb_lt in E2. cbn [map_over ProofSupport.map_over bool_ops at_member].
          rewrite Heval_in; [|unfold N in *; lia].
          assert (Li : (w0 - (3 * N + N * N) <? N) = true) by (apply Nat.ltb_lt; lia). rewrite Li. reflexivity.
        * apply Nat.ltb_ge in E2.
          destruct (Nat.ltb w0 (4 * N + 2 * N * N)) eqn:E3.
          -- apply Nat.ltb_lt in E3.
             destruct (div_mod_pair_bound N (w0 - (4 * N + N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
             destruct (Nat.eqb ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N)) eqn:Eij;
               cbn [map_over ProofSupport.map_over bool_ops xor_fold]; rewrite Heval_in; [|unfold N in *; lia| |unfold N in *; lia].
             ++ assert (G0 : (N + (w0 - (4 * N + N * N)) mod N <? N) = false) by (apply Nat.ltb_ge; lia).
                assert (G1 : (N + (w0 - (4 * N + N * N)) mod N <? 2 * N) = true) by (apply Nat.ltb_lt; lia).
                rewrite G0, G1. replace (N + (w0 - (4 * N + N * N)) mod N - N) with ((w0 - (4 * N + N * N)) mod N) by lia.
                unfold dom_rbit. rewrite Eij. repeat rewrite gf2_add_zero_r. reflexivity.
             ++ pose proof (dom_pair_idx_lt N _ _ Hi Hj).
                rewrite Heval_in; [|unfold N in *; lia].
                assert (G0 : (N + (w0 - (4 * N + N * N)) mod N <? N) = false) by (apply Nat.ltb_ge; lia).
                assert (G1 : (N + (w0 - (4 * N + N * N)) mod N <? 2 * N) = true) by (apply Nat.ltb_lt; lia).
                assert (G2 : (2 * N + dom_pair_idx N ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N) <? N) = false) by (apply Nat.ltb_ge; lia).
                assert (G3 : (2 * N + dom_pair_idx N ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N) <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                rewrite G0, G1, G2, G3.
                replace (N + (w0 - (4 * N + N * N)) mod N - N) with ((w0 - (4 * N + N * N)) mod N) by lia.
                replace (2 * N + dom_pair_idx N ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N) - 2 * N)
                  with (dom_pair_idx N ((w0 - (4 * N + N * N)) / N) ((w0 - (4 * N + N * N)) mod N)) by lia.
                unfold dom_rbit. rewrite Eij, gf2_add_zero_r. reflexivity.
          -- apply Nat.ltb_ge in E3.
             destruct (Nat.ltb w0 (4 * N + 3 * N * N)) eqn:E4.
             ++ rewrite HregS; [|exact Hw0].
                assert (G0 : (w0 <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; exact E0).
                assert (G1 : (w0 <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; exact E1).
                assert (G2 : (w0 <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact E3).
                rewrite G0, G1, G2, E4. reflexivity.
             ++ apply Nat.ltb_ge in E4.
                destruct (Nat.ltb w0 (4 * N + 4 * N * N)) eqn:E5.
                ** apply Nat.ltb_lt in E5.
                   destruct (div_mod_pair_bound N (w0 - (4 * N + 3 * N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
                   destruct (Nat.eqb ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N)) eqn:Eij.
                   --- unfold dom_rbit. rewrite Eij, andb_false_r. reflexivity.
                   --- cbn [map_over ProofSupport.map_over bool_ops at_member].
                       rewrite Heval_not; [|exact Hi].
                       pose proof (dom_pair_idx_lt N _ _ Hi Hj).
                       rewrite Heval_in; [|unfold N in *; lia].
                       assert (G0 : (2 * N + dom_pair_idx N ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N) <? N) = false) by (apply Nat.ltb_ge; lia).
                       assert (G1 : (2 * N + dom_pair_idx N ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N) <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                       rewrite G0, G1.
                       replace (2 * N + dom_pair_idx N ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N) - 2 * N)
                         with (dom_pair_idx N ((w0 - (4 * N + 3 * N * N)) / N) ((w0 - (4 * N + 3 * N * N)) mod N)) by lia.
                       unfold dom_rbit. rewrite Eij. reflexivity.
                ** apply Nat.ltb_ge in E5.
                   destruct (Nat.ltb w0 (4 * N + 5 * N * N)) eqn:E6.
                   --- rewrite HregS; [|exact Hw0].
                       assert (G0 : (w0 <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; exact E0).
                       assert (G1 : (w0 <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; exact E1).
                       assert (G2 : (w0 <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact E3).
                       assert (G3 : (w0 <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; exact E4).
                       assert (G4 : (w0 <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; exact E5).
                       rewrite G0, G1, G2, G3, G4, E6. reflexivity.
                   --- apply Nat.ltb_ge in E6.
                       destruct (Nat.ltb w0 (4 * N + 6 * N * N)) eqn:E7.
                       +++ apply Nat.ltb_lt in E7.
                           destruct (div_mod_pair_bound N (w0 - (4 * N + 5 * N * N)) ltac:(lia) ltac:(lia)) as [Hi _].
                           cbn [map_over ProofSupport.map_over bool_ops at_member].
                           rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
                           rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
                           unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                           assert (A0 : (2 * N + N * N + (w0 - (4 * N + 5 * N * N)) / N <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                           assert (A1 : (2 * N + N * N + (w0 - (4 * N + 5 * N * N)) / N <? 3 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
                           rewrite A0, A1, HregS; [|unfold hpc2_wire_count; unfold N in *; nia].
                           rewrite A0, A1.
                           replace (2 * N + N * N + (w0 - (4 * N + 5 * N * N)) / N - (2 * N + N * N)) with ((w0 - (4 * N + 5 * N * N)) / N) by lia.
                           rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
                           rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
                           unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                           assert (B0 : (4 * N + 2 * N * N + (w0 - (4 * N + 5 * N * N)) <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                           assert (B1 : (4 * N + 2 * N * N + (w0 - (4 * N + 5 * N * N)) <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                           assert (B2 : (4 * N + 2 * N * N + (w0 - (4 * N + 5 * N * N)) <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                           assert (B3 : (4 * N + 2 * N * N + (w0 - (4 * N + 5 * N * N)) <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
                           assert (B4 : (4 * N + 2 * N * N + (w0 - (4 * N + 5 * N * N)) <? 4 * N + 3 * N * N) = true) by (apply Nat.ltb_lt; lia).
                           rewrite B0, B1, B2, B3, B4, HregS; [|unfold hpc2_wire_count; unfold N in *; nia].
                           rewrite B0, B1, B3, B4.
                           replace (4 * N + 2 * N * N + (w0 - (4 * N + 5 * N * N)) - (4 * N + 2 * N * N)) with (w0 - (4 * N + 5 * N * N)) by lia.
                           reflexivity.
                       +++ apply Nat.ltb_ge in E7.
                           destruct (Nat.ltb w0 (4 * N + 7 * N * N)) eqn:E8.
                           *** apply Nat.ltb_lt in E8.
                               cbn [map_over ProofSupport.map_over bool_ops xor_fold].
                               rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
                               rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
                               unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                               assert (A0 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (A1 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (A2 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (A3 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (A4 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (A5 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (A6 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (A7 : (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 6 * N * N) = true) by (apply Nat.ltb_lt; lia).
                               rewrite A0, A1, A2, A3, A4, A5, A6, A7.
                               replace (4 * N + 5 * N * N + (w0 - (4 * N + 6 * N * N)) - (4 * N + 5 * N * N)) with (w0 - (4 * N + 6 * N * N)) by lia.
                               destruct (div_mod_pair_bound N (w0 - (4 * N + 6 * N * N)) ltac:(lia) ltac:(lia)) as [Hi _].
                               cbn [map_over ProofSupport.map_over bool_ops at_member].
                               rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
                               rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
                               unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                               assert (B0 : (2 * N + N * N + (w0 - (4 * N + 6 * N * N)) / N <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (B1 : (2 * N + N * N + (w0 - (4 * N + 6 * N * N)) / N <? 3 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
                               rewrite B0, B1, HregS; [|unfold hpc2_wire_count; unfold N in *; nia].
                               rewrite B0, B1.
                               replace (2 * N + N * N + (w0 - (4 * N + 6 * N * N)) / N - (2 * N + N * N)) with ((w0 - (4 * N + 6 * N * N)) / N) by lia.
                               rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
                               rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
                               unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                               assert (C0 : (4 * N + 2 * N * N + (w0 - (4 * N + 6 * N * N)) <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (C1 : (4 * N + 2 * N * N + (w0 - (4 * N + 6 * N * N)) <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (C2 : (4 * N + 2 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (C3 : (4 * N + 2 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (C4 : (4 * N + 2 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 3 * N * N) = true) by (apply Nat.ltb_lt; lia).
                               rewrite C0, C1, C2, C3, C4, HregS; [|unfold hpc2_wire_count; unfold N in *; nia].
                               rewrite C0, C1, C3, C4.
                               replace (4 * N + 2 * N * N + (w0 - (4 * N + 6 * N * N)) - (4 * N + 2 * N * N)) with (w0 - (4 * N + 6 * N * N)) by lia.
                               rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; unfold N in *; nia].
                               rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; unfold N in *; nia].
                               unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                               assert (D0 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (D1 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (D2 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (D3 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (D4 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (D5 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (D6 : (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) <? 4 * N + 5 * N * N) = true) by (apply Nat.ltb_lt; lia).
                               rewrite D0, D1, D2, D3, D4, D5, D6, HregS; [|unfold hpc2_wire_count; unfold N in *; nia].
                               rewrite D0, D1, D3, D4, D5, D6.
                               replace (4 * N + 4 * N * N + (w0 - (4 * N + 6 * N * N)) - (4 * N + 4 * N * N)) with (w0 - (4 * N + 6 * N * N)) by lia.
                               rewrite gf2_add_zero_r. cbv zeta.
                               destruct (a 0 ((w0 - (4 * N + 6 * N * N)) / N));
                               destruct (a 1 ((w0 - (4 * N + 6 * N * N)) mod N));
                               destruct (dom_rbit N tape ((w0 - (4 * N + 6 * N * N)) / N) ((w0 - (4 * N + 6 * N * N)) mod N)); reflexivity.
                           *** apply Nat.ltb_ge in E8.
                               destruct (Nat.ltb w0 (4 * N + 8 * N * N)) eqn:E9.
                               ---- rewrite HregS; [|exact Hw0].
                                    assert (G0 : (w0 <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; exact E0).
                                    assert (G1 : (w0 <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; exact E1).
                                    assert (G2 : (w0 <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact E3).
                                    assert (G3 : (w0 <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; exact E4).
                                    assert (G4 : (w0 <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; exact E5).
                                    assert (G5 : (w0 <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; exact E6).
                                    assert (G6 : (w0 <? 4 * N + 7 * N * N) = false) by (apply Nat.ltb_ge; exact E8).
                                    rewrite G0, G1, G2, G3, G4, G5, G6, E9. reflexivity.
                               ---- apply Nat.ltb_ge in E9. unfold bool_ops.
                                    assert (Hfold : forall u, (forall j, ProofSupport.Member j u -> j < N) ->
                                      xor_fold (map_over (fun x => value_at gf2_sharing bool_ops (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
                                        (fun _ => false) ins (S t) x)
                                        (map_over (fun j => 4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j) u)) =
                                      match t with
                                      | 0 => false
                                      | S _ => xor_fold (map_over (fun j =>
                                          xorb (andb (a 0 (w0 - (4 * N + 8 * N * N))) (a 1 j))
                                               (dom_rbit N tape (w0 - (4 * N + 8 * N * N)) j)) u)
                                      end).
                                    { induction u as [|j ur IHu]; intros Hu; [destruct t; reflexivity|].
                                      cbn [map_over ProofSupport.map_over xor_fold].
                                      assert (Hj : j < N) by (apply Hu; left; reflexivity).
                                      assert (Hwj : 4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j < hpc2_wire_count n)
                                        by (unfold hpc2_wire_count in *; unfold N in *; nia).
                                      rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hwj].
                                      rewrite gate_at_circuit_of_fun; [|exact Hwj].
                                      unfold hpc2_gate at 1. cbv zeta. change (S n) with N.
                                      assert (D0 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; nia).
                                      assert (D1 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; nia).
                                      assert (D2 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; nia).
                                      assert (D3 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                      assert (D4 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                      assert (D5 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                      assert (D6 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                      assert (D7 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 6 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                      assert (D8 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 7 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                      assert (D9 : (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j <? 4 * N + 8 * N * N) = true)
                                        by (apply Nat.ltb_lt; unfold hpc2_wire_count in *; unfold N in *; nia).
                                      rewrite D0, D1, D2, D3, D4, D5, D6, D7, D8, D9, HregS; [|exact Hwj].
                                      rewrite D0, D1, D3, D4, D5, D6, D8, D9.
                                      destruct t as [|t'].
                                      - apply IHu. intros y Hy. apply Hu; right; exact Hy.
                                      - assert (Hi_lt : w0 - (4 * N + 8 * N * N) < N) by (unfold hpc2_wire_count in *; unfold N in *; lia).
                                        replace (4 * N + 7 * N * N + (w0 - (4 * N + 8 * N * N)) * N + j - (4 * N + 7 * N * N))
                                          with ((w0 - (4 * N + 8 * N * N)) * N + j)
                                          by (rewrite <- Nat.add_assoc, (Nat.add_comm (4 * N + 7 * N * N)), Nat.add_sub; reflexivity).
                                        cbv zeta.
                                        destruct (div_mod_pair_id N (w0 - (4 * N + 8 * N * N)) j Hi_lt Hj) as [Hd Hm].
                                        rewrite Hd, Hm.
                                        cbn [xor_fold]. f_equal. apply IHu. intros y Hy. apply Hu; right; exact Hy. }
                                    apply Hfold. intros j Hj. apply member_upto_lt; exact Hj. }
  destruct (Hpair cyc) as [_ Hv].
  unfold gd_value, hpc2_and_gadget. cbn [gd_share gd_ops gd_circuit gd_assign gd_start].
  change (S n) with N. exact (Hv w Hw).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem hpc2_and_correct :
  forall n (a : ShareMatrix (hpc2_and_gadget n)) tape,
    xor_sum_upto (fun k => gd_value (hpc2_and_gadget n) a tape (gd_read (hpc2_and_gadget n))
      (gd_out (hpc2_and_gadget n) k)) (S n) =
    andb (xor_sum_upto (a 0) (S n)) (xor_sum_upto (a 1) (S n)).
Proof.
  intros n a tape. set (N := S n).
  assert (Hsplit :
    xor_sum_upto (fun k => gd_value (hpc2_and_gadget n) a tape (gd_read (hpc2_and_gadget n))
      (gd_out (hpc2_and_gadget n) k)) N =
    xorb (xor_sum_upto (fun i => xor_sum_upto (fun j => andb (a 0 i) (a 1 j)) N) N)
         (xor_sum_upto (fun i => xor_sum_upto (fun j => dom_rbit N tape i j) N) N)).
  { rewrite <- xor_sum_upto_xorb.
    apply xor_sum_upto_ext. intros i Hi.
    replace (gd_out (hpc2_and_gadget n) i) with (hpc2_out_wire n i) by reflexivity.
    rewrite hpc2_value_eq; [|unfold hpc2_out_wire, hpc2_wire_count; unfold N in *; lia].
    unfold hpc2_eval, hpc2_out_wire. cbv zeta. change (S n) with N.
    assert (L0 : (4 * N + 8 * N * N + i <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L1 : (4 * N + 8 * N * N + i <? 2 * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L2 : (4 * N + 8 * N * N + i <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L3 : (4 * N + 8 * N * N + i <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L4 : (4 * N + 8 * N * N + i <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L5 : (4 * N + 8 * N * N + i <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L6 : (4 * N + 8 * N * N + i <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L7 : (4 * N + 8 * N * N + i <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L8 : (4 * N + 8 * N * N + i <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L9 : (4 * N + 8 * N * N + i <? 4 * N + 6 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L10 : (4 * N + 8 * N * N + i <? 4 * N + 7 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    assert (L11 : (4 * N + 8 * N * N + i <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
    rewrite L0, L1, L2, L3, L4, L5, L6, L7, L8, L9, L10, L11.
    cbn [gd_read hpc2_and_gadget].
    replace (4 * N + 8 * N * N + i - (4 * N + 8 * N * N)) with i by lia.
    apply xor_sum_upto_xorb. }
  rewrite Hsplit.
  rewrite (xor_sum_upto_antisym_zero (dom_rbit N tape) N (dom_rbit_diag N tape) (dom_rbit_sym N tape)).
  rewrite gf2_add_zero_r.
  transitivity (xor_sum_upto (fun k => andb (a 0 k) (xor_sum_upto (a 1) N)) N).
  - apply xor_sum_upto_ext. intros k _. apply xor_sum_upto_and_l.
  - apply xor_sum_upto_and_r.
Qed.

Lemma hpc2_stable_in_or_rega :
  forall n w, w < 3 * S n + S n * S n ->
    stable_sources (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n)) (hpc2_wire_count n) w = w :: nil.
Proof.
  intros n w Hw.
  destruct (hpc2_and_well_formed n) as [Hwf _].
  unfold hpc2_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
  rewrite <- (circuit_of_fun_count (hpc2_wire_count n) (hpc2_gate n)) at 2.
  rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; nia].
  rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; nia].
  unfold hpc2_gate at 1. cbv zeta.
  destruct (Nat.ltb w (2 * S n + S n * S n)) eqn:E0; [reflexivity|].
  assert (E1 : (w <? 3 * S n + S n * S n) = true) by (apply Nat.ltb_lt; exact Hw).
  rewrite E1. reflexivity.
Qed.

Lemma hpc2_stable_not :
  forall n i, i < S n ->
    stable_sources (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n)) (hpc2_wire_count n) (3 * S n + S n * S n + i) =
    i :: nil.
Proof.
  intros n i Hi.
  destruct (hpc2_and_well_formed n) as [Hwf _].
  unfold hpc2_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
  rewrite <- (circuit_of_fun_count (hpc2_wire_count n) (hpc2_gate n)) at 2.
  rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; nia].
  rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; nia].
  unfold hpc2_gate at 1. cbv zeta.
  assert (E0 : (3 * S n + S n * S n + i <? 2 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
  assert (E1 : (3 * S n + S n * S n + i <? 3 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
  assert (E2 : (3 * S n + S n * S n + i <? 4 * S n + S n * S n) = true) by (apply Nat.ltb_lt; lia).
  rewrite E0, E1, E2.
  replace (3 * S n + S n * S n + i - (3 * S n + S n * S n)) with i by lia.
  cbn [flat_map_over app]. rewrite circuit_of_fun_count, app_nil_r.
  apply hpc2_stable_in_or_rega. lia.
Qed.

Lemma hpc2_stable_reg_only :
  forall n w,
    (4 * S n + 2 * S n * S n <= w /\ w < 4 * S n + 3 * S n * S n) \/
    (4 * S n + 4 * S n * S n <= w /\ w < 4 * S n + 5 * S n * S n) \/
    (4 * S n + 7 * S n * S n <= w /\ w < 4 * S n + 8 * S n * S n) ->
    stable_sources (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n)) (hpc2_wire_count n) w = w :: nil.
Proof.
  intros n w Hrng.
  destruct (hpc2_and_well_formed n) as [Hwf _].
  unfold hpc2_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
  rewrite <- (circuit_of_fun_count (hpc2_wire_count n) (hpc2_gate n)) at 2.
  rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; nia].
  rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; nia].
  unfold hpc2_gate at 1. cbv zeta.
  destruct Hrng as [[Ha Hb] | [[Ha Hb] | [Ha Hb]]].
  - assert (E0 : (w <? 2 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E1 : (w <? 3 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E2 : (w <? 4 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E3 : (w <? 4 * S n + 2 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E4 : (w <? 4 * S n + 3 * S n * S n) = true) by (apply Nat.ltb_lt; lia).
    rewrite E0, E1, E2, E3, E4. reflexivity.
  - assert (E0 : (w <? 2 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E1 : (w <? 3 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E2 : (w <? 4 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E3 : (w <? 4 * S n + 2 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E4 : (w <? 4 * S n + 3 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E5 : (w <? 4 * S n + 4 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E6 : (w <? 4 * S n + 5 * S n * S n) = true) by (apply Nat.ltb_lt; lia).
    rewrite E0, E1, E2, E3, E4, E5, E6. reflexivity.
  - assert (E0 : (w <? 2 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E1 : (w <? 3 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E2 : (w <? 4 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E3 : (w <? 4 * S n + 2 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E4 : (w <? 4 * S n + 3 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E5 : (w <? 4 * S n + 4 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E6 : (w <? 4 * S n + 5 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E7 : (w <? 4 * S n + 6 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E8 : (w <? 4 * S n + 7 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
    assert (E9 : (w <? 4 * S n + 8 * S n * S n) = true) by (apply Nat.ltb_lt; lia).
    rewrite E0, E1, E2, E3, E4, E5, E6, E7, E8, E9. reflexivity.
Qed.

Lemma hpc2_stable_mul :
  forall n p, p < S n * S n ->
    stable_sources (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n)) (hpc2_wire_count n) (4 * S n + 5 * S n * S n + p) =
    (2 * S n + S n * S n + p / S n) :: (4 * S n + 2 * S n * S n + p) :: nil.
Proof.
  intros n p Hp.
  destruct (hpc2_and_well_formed n) as [Hwf _].
  unfold hpc2_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
  destruct (div_mod_pair_bound (S n) p ltac:(lia) Hp) as [Hi _].
  rewrite <- (circuit_of_fun_count (hpc2_wire_count n) (hpc2_gate n)) at 2.
  rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; unfold hpc2_wire_count; nia].
  rewrite gate_at_circuit_of_fun; [|unfold hpc2_wire_count; nia].
  unfold hpc2_gate at 1. cbv zeta.
  assert (E0 : (4 * S n + 5 * S n * S n + p <? 2 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
  assert (E1 : (4 * S n + 5 * S n * S n + p <? 3 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
  assert (E2 : (4 * S n + 5 * S n * S n + p <? 4 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
  assert (E3 : (4 * S n + 5 * S n * S n + p <? 4 * S n + 2 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
  assert (E4 : (4 * S n + 5 * S n * S n + p <? 4 * S n + 3 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
  assert (E5 : (4 * S n + 5 * S n * S n + p <? 4 * S n + 4 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
  assert (E6 : (4 * S n + 5 * S n * S n + p <? 4 * S n + 5 * S n * S n) = false) by (apply Nat.ltb_ge; lia).
  assert (E7 : (4 * S n + 5 * S n * S n + p <? 4 * S n + 6 * S n * S n) = true) by (apply Nat.ltb_lt; lia).
  rewrite E0, E1, E2, E3, E4, E5, E6, E7.
  replace (4 * S n + 5 * S n * S n + p - (4 * S n + 5 * S n * S n)) with p by lia.
  cbn [flat_map_over app]. rewrite !circuit_of_fun_count.
  rewrite hpc2_stable_in_or_rega; [|lia].
  rewrite hpc2_stable_reg_only; [reflexivity | left; split; lia].
Qed.

Lemma hpc2_stable_sources :
  forall n w, w < hpc2_wire_count n ->
    let N := S n in
    stable_sources (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n)) (hpc2_wire_count n) w =
    if Nat.ltb w (3 * N + N * N) then w :: nil
    else if Nat.ltb w (4 * N + N * N) then (w - (3 * N + N * N)) :: nil
    else if Nat.ltb w (4 * N + 2 * N * N) then
      let p := w - (4 * N + N * N) in
      let i := p / N in let j := p mod N in
      if Nat.eqb i j then (N + j) :: nil
      else (N + j) :: (2 * N + dom_pair_idx N i j) :: nil
    else if Nat.ltb w (4 * N + 3 * N * N) then w :: nil
    else if Nat.ltb w (4 * N + 4 * N * N) then
      let p := w - (4 * N + 3 * N * N) in
      let i := p / N in let j := p mod N in
      if Nat.eqb i j then nil
      else i :: (2 * N + dom_pair_idx N i j) :: nil
    else if Nat.ltb w (4 * N + 5 * N * N) then w :: nil
    else if Nat.ltb w (4 * N + 6 * N * N) then
      let p := w - (4 * N + 5 * N * N) in
      (2 * N + N * N + p / N) :: (4 * N + 2 * N * N + p) :: nil
    else if Nat.ltb w (4 * N + 7 * N * N) then
      let p := w - (4 * N + 6 * N * N) in
      (2 * N + N * N + p / N) :: (4 * N + 2 * N * N + p) :: (4 * N + 4 * N * N + p) :: nil
    else if Nat.ltb w (4 * N + 8 * N * N) then w :: nil
    else
      let i := w - (4 * N + 8 * N * N) in
      map_over (fun j => 4 * N + 7 * N * N + i * N + j) (upto N).
Proof.
  intros n w Hw. cbv zeta.
  destruct (Nat.ltb w (3 * S n + S n * S n)) eqn:E1;
    [apply hpc2_stable_in_or_rega; apply Nat.ltb_lt; exact E1|].
  apply Nat.ltb_ge in E1.
  destruct (Nat.ltb w (4 * S n + S n * S n)) eqn:E2.
  - apply Nat.ltb_lt in E2.
    replace w with (3 * S n + S n * S n + (w - (3 * S n + S n * S n))) at 1 by lia.
    apply hpc2_stable_not. lia.
  - apply Nat.ltb_ge in E2.
    destruct (Nat.ltb w (4 * S n + 2 * S n * S n)) eqn:E3.
    + assert (Hlt3 : w < 4 * S n + 2 * S n * S n) by (apply Nat.ltb_lt; exact E3).
      destruct (div_mod_pair_bound (S n) (w - (4 * S n + S n * S n)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
      destruct (hpc2_and_well_formed n) as [Hwf _].
      unfold hpc2_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
      rewrite <- (circuit_of_fun_count (hpc2_wire_count n) (hpc2_gate n)) at 2.
      rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw].
      rewrite gate_at_circuit_of_fun; [|exact Hw].
      unfold hpc2_gate at 1. cbv zeta.
      assert (E0 : (w <? 2 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
      assert (E1' : (w <? 3 * S n + S n * S n) = false) by (apply Nat.ltb_ge; exact E1).
      assert (E2' : (w <? 4 * S n + S n * S n) = false) by (apply Nat.ltb_ge; exact E2).
      rewrite E0, E1', E2', E3.
      destruct (Nat.eqb ((w - (4 * S n + S n * S n)) / S n) ((w - (4 * S n + S n * S n)) mod S n));
        cbn [flat_map_over app]; rewrite !circuit_of_fun_count;
        [rewrite hpc2_stable_in_or_rega, app_nil_r; [reflexivity | lia]|].
      pose proof (dom_pair_idx_lt (S n) _ _ Hi Hj).
      rewrite hpc2_stable_in_or_rega; [|lia].
      rewrite hpc2_stable_in_or_rega; [cbn [app]; reflexivity | lia].
    + apply Nat.ltb_ge in E3.
      destruct (Nat.ltb w (4 * S n + 3 * S n * S n)) eqn:E4;
        [apply hpc2_stable_reg_only; apply Nat.ltb_lt in E4; left; split; lia|].
      apply Nat.ltb_ge in E4.
      destruct (Nat.ltb w (4 * S n + 4 * S n * S n)) eqn:E5.
      * assert (Hlt5 : w < 4 * S n + 4 * S n * S n) by (apply Nat.ltb_lt; exact E5).
        destruct (div_mod_pair_bound (S n) (w - (4 * S n + 3 * S n * S n)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
        destruct (hpc2_and_well_formed n) as [Hwf _].
        unfold hpc2_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
        rewrite <- (circuit_of_fun_count (hpc2_wire_count n) (hpc2_gate n)) at 2.
        rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw].
        rewrite gate_at_circuit_of_fun; [|exact Hw].
        unfold hpc2_gate at 1. cbv zeta.
        assert (E0 : (w <? 2 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
        assert (E1' : (w <? 3 * S n + S n * S n) = false) by (apply Nat.ltb_ge; exact E1).
        assert (E2' : (w <? 4 * S n + S n * S n) = false) by (apply Nat.ltb_ge; exact E2).
        assert (E3' : (w <? 4 * S n + 2 * S n * S n) = false) by (apply Nat.ltb_ge; exact E3).
        assert (E4' : (w <? 4 * S n + 3 * S n * S n) = false) by (apply Nat.ltb_ge; exact E4).
        rewrite E0, E1', E2', E3', E4', E5.
        destruct (Nat.eqb ((w - (4 * S n + 3 * S n * S n)) / S n) ((w - (4 * S n + 3 * S n * S n)) mod S n));
          [reflexivity|].
        cbn [flat_map_over app]; rewrite !circuit_of_fun_count.
        pose proof (dom_pair_idx_lt (S n) _ _ Hi Hj).
        rewrite hpc2_stable_not; [|exact Hi].
        rewrite hpc2_stable_in_or_rega; [cbn [app]; reflexivity | lia].
      * apply Nat.ltb_ge in E5.
        destruct (Nat.ltb w (4 * S n + 5 * S n * S n)) eqn:E6;
          [apply hpc2_stable_reg_only; apply Nat.ltb_lt in E6; right; left; split; lia|].
        apply Nat.ltb_ge in E6.
        destruct (Nat.ltb w (4 * S n + 6 * S n * S n)) eqn:E7.
        -- apply Nat.ltb_lt in E7.
           replace w with (4 * S n + 5 * S n * S n + (w - (4 * S n + 5 * S n * S n))) at 1 by lia.
           apply hpc2_stable_mul. lia.
        -- apply Nat.ltb_ge in E7.
           destruct (Nat.ltb w (4 * S n + 7 * S n * S n)) eqn:E8.
           ++ assert (Hlt8 : w < 4 * S n + 7 * S n * S n) by (apply Nat.ltb_lt; exact E8).
              destruct (hpc2_and_well_formed n) as [Hwf _].
              unfold hpc2_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
              rewrite <- (circuit_of_fun_count (hpc2_wire_count n) (hpc2_gate n)) at 2.
              rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw].
              rewrite gate_at_circuit_of_fun; [|exact Hw].
              unfold hpc2_gate at 1. cbv zeta.
              assert (E0 : (w <? 2 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
              assert (E1' : (w <? 3 * S n + S n * S n) = false) by (apply Nat.ltb_ge; exact E1).
              assert (E2' : (w <? 4 * S n + S n * S n) = false) by (apply Nat.ltb_ge; exact E2).
              assert (E3' : (w <? 4 * S n + 2 * S n * S n) = false) by (apply Nat.ltb_ge; exact E3).
              assert (E4' : (w <? 4 * S n + 3 * S n * S n) = false) by (apply Nat.ltb_ge; exact E4).
              assert (E5' : (w <? 4 * S n + 4 * S n * S n) = false) by (apply Nat.ltb_ge; exact E5).
              assert (E6' : (w <? 4 * S n + 5 * S n * S n) = false) by (apply Nat.ltb_ge; exact E6).
              assert (E7' : (w <? 4 * S n + 6 * S n * S n) = false) by (apply Nat.ltb_ge; exact E7).
              rewrite E0, E1', E2', E3', E4', E5', E6', E7', E8.
              cbn [flat_map_over app]; rewrite !circuit_of_fun_count.
              rewrite hpc2_stable_mul; [|lia].
              rewrite hpc2_stable_reg_only; [cbn [app]; reflexivity | right; left; split; lia].
           ++ apply Nat.ltb_ge in E8.
              destruct (Nat.ltb w (4 * S n + 8 * S n * S n)) eqn:E9;
                [apply hpc2_stable_reg_only; apply Nat.ltb_lt in E9; right; right; split; lia|].
              apply Nat.ltb_ge in E9.
              destruct (hpc2_and_well_formed n) as [Hwf _].
              unfold hpc2_and_gadget in Hwf; cbn [gd_circuit] in Hwf.
              rewrite <- (circuit_of_fun_count (hpc2_wire_count n) (hpc2_gate n)) at 2.
              rewrite stable_sources_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw].
              rewrite gate_at_circuit_of_fun; [|exact Hw].
              unfold hpc2_gate at 1. cbv zeta.
              assert (E0 : (w <? 2 * S n + S n * S n) = false) by (apply Nat.ltb_ge; lia).
              assert (E1' : (w <? 3 * S n + S n * S n) = false) by (apply Nat.ltb_ge; exact E1).
              assert (E2' : (w <? 4 * S n + S n * S n) = false) by (apply Nat.ltb_ge; exact E2).
              assert (E3' : (w <? 4 * S n + 2 * S n * S n) = false) by (apply Nat.ltb_ge; exact E3).
              assert (E4' : (w <? 4 * S n + 3 * S n * S n) = false) by (apply Nat.ltb_ge; exact E4).
              assert (E5' : (w <? 4 * S n + 4 * S n * S n) = false) by (apply Nat.ltb_ge; exact E5).
              assert (E6' : (w <? 4 * S n + 5 * S n * S n) = false) by (apply Nat.ltb_ge; exact E6).
              assert (E7' : (w <? 4 * S n + 6 * S n * S n) = false) by (apply Nat.ltb_ge; exact E7).
              assert (E8' : (w <? 4 * S n + 7 * S n * S n) = false) by (apply Nat.ltb_ge; exact E8).
              assert (E9' : (w <? 4 * S n + 8 * S n * S n) = false) by (apply Nat.ltb_ge; exact E9).
              rewrite E0, E1', E2', E3', E4', E5', E6', E7', E8', E9'.
              assert (Hlist : forall u, (forall j, ProofSupport.Member j u -> j < S n) ->
                flat_map_over (stable_sources (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))
                  (wire_count (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n))))
                  (map_over (fun j => 4 * S n + 7 * S n * S n + (w - (4 * S n + 8 * S n * S n)) * S n + j) u) =
                map_over (fun j => 4 * S n + 7 * S n * S n + (w - (4 * S n + 8 * S n * S n)) * S n + j) u).
              { intros u Hu. induction u as [|j ur IHu]; [reflexivity|].
                cbn [map_over ProofSupport.map_over flat_map_over].
                assert (Hj : j < S n) by (apply Hu; left; reflexivity).
                assert (Hreg_lt : 4 * S n + 7 * S n * S n + (w - (4 * S n + 8 * S n * S n)) * S n + j < hpc2_wire_count n)
                  by (unfold hpc2_wire_count in *; nia).
                rewrite circuit_of_fun_count at 1.
                rewrite hpc2_stable_reg_only; [|right; right; unfold hpc2_wire_count in Hw; nia].
                cbn [app]. f_equal. apply IHu. intros y Hy. apply Hu; right; exact Hy. }
              apply Hlist. intros j Hj. apply member_upto_lt; exact Hj.
Qed.

Definition hpc2_wire_pair (n w : nat) : option (nat * nat) :=
  let N := S n in
  if Nat.ltb w (2 * N) then None
  else if Nat.ltb w (2 * N + N * N) then
    let r := w - 2 * N in
    let u := r / N in let v := r mod N in
    if Nat.ltb u v then Some (u, v) else None
  else if Nat.ltb w (4 * N + N * N) then None
  else if Nat.ltb w (4 * N + 8 * N * N) then
    let p := (w - (4 * N + N * N)) mod (N * N) in
    let i := p / N in let j := p mod N in
    if Nat.ltb i j then Some (i, j)
    else if Nat.ltb j i then Some (j, i)
    else None
  else None.

Definition hpc2_out_probed (n : nat) (ps : list Probe) (k : nat) : bool :=
  any_of (fun p => Nat.eqb (p_wire p) (hpc2_out_wire n k)) ps.

Definition hpc2_two_dom_probed (n : nat) (ps : list Probe) (u v : nat) : bool :=
  any_of (fun p =>
    match hpc2_wire_pair n (p_wire p) with
    | Some (x, y) => andb (Nat.eqb x u) (Nat.eqb y v)
    | None => false
    end) ps.

Lemma hpc2_two_dom_probed_member :
  forall n ps u v p,
    ProofSupport.Member p ps ->
    hpc2_wire_pair n (p_wire p) = Some (u, v) ->
    hpc2_two_dom_probed n ps u v = true.
Proof.
  intros n ps u v p Hp Hwp. unfold hpc2_two_dom_probed.
  induction ps as [|q r IH]; simpl in *; [contradiction|].
  destruct Hp as [->|Hp].
  - rewrite Hwp. repeat rewrite eqb_refl_nat. reflexivity.
  - rewrite (IH Hp). destruct (hpc2_wire_pair n (p_wire q)) as [[x y]|];
      [destruct (andb (x =? u) (y =? v)); reflexivity | reflexivity].
Qed.

Lemma hpc2_out_probed_member :
  forall n ps k p,
    ProofSupport.Member p ps ->
    p_wire p = hpc2_out_wire n k ->
    hpc2_out_probed n ps k = true.
Proof.
  intros n ps k p Hp Hw. unfold hpc2_out_probed.
  induction ps as [|q r IH]; simpl in *; [contradiction|].
  destruct Hp as [->|Hp].
  - rewrite Hw, eqb_refl_nat. reflexivity.
  - rewrite (IH Hp). destruct (Nat.eqb (p_wire q) (hpc2_out_wire n k)); reflexivity.
Qed.

Lemma hpc2_out_probed_inv :
  forall n ps k,
    hpc2_out_probed n ps k = true ->
    exists p, ProofSupport.Member p ps /\ p_wire p = hpc2_out_wire n k.
Proof.
  intros n ps k Hp. unfold hpc2_out_probed in Hp.
  induction ps as [|q r IH]; simpl in *; [discriminate|].
  destruct (Nat.eqb (p_wire q) (hpc2_out_wire n k)) eqn:Eq.
  - apply eqb_sound_nat in Eq. exists q; split; [left; reflexivity | exact Eq].
  - simpl in Hp. destruct (IH Hp) as [p [Hpr Hpw]]. exists p; split; [right; exact Hpr | exact Hpw].
Qed.

Lemma hpc2_two_dom_probed_inv :
  forall n ps u v,
    hpc2_two_dom_probed n ps u v = true ->
    exists p, ProofSupport.Member p ps /\ hpc2_wire_pair n (p_wire p) = Some (u, v).
Proof.
  intros n ps u v Htd. unfold hpc2_two_dom_probed in Htd.
  induction ps as [|q r IH]; simpl in *; [discriminate|].
  destruct (hpc2_wire_pair n (p_wire q)) as [[x y]|] eqn:Eq.
  - destruct (andb (Nat.eqb x u) (Nat.eqb y v)) eqn:Exy.
    + apply andb_prop in Exy. destruct Exy as [Ex Ey].
      apply eqb_sound_nat in Ex; apply eqb_sound_nat in Ey; subst.
      exists q; split; [left; reflexivity | exact Eq].
    + simpl in Htd. destruct (IH Htd) as [p [Hp Hwp]]. exists p; split; [right; exact Hp | exact Hwp].
  - simpl in Htd. destruct (IH Htd) as [p [Hp Hwp]]. exists p; split; [right; exact Hp | exact Hwp].
Qed.

Lemma hpc2_mod_block :
  forall n w k p,
    4 * S n + S n * S n <= w ->
    w = 4 * S n + S n * S n + k * (S n * S n) + p ->
    p < S n * S n ->
    (w - (4 * S n + S n * S n)) mod (S n * S n) = p.
Proof.
  intros n w k p Hge Hw Hp.
  replace (w - (4 * S n + S n * S n)) with (p + k * (S n * S n)) by lia.
  rewrite Nat.Div0.mod_add. apply Nat.mod_small. exact Hp.
Qed.

Definition hpc2_pini_contrib (n : nat) (ps : list Probe) (B : nat -> bool) (p : Probe) : option nat * option nat :=
  let N := S n in
  let OutOrB k := orb (B k) (hpc2_out_probed n ps k) in
  let w := p_wire p in
  if Nat.ltb w N then (Some w, None)
  else if Nat.ltb w (2 * N) then (None, Some (w - N))
  else if Nat.ltb w (2 * N + N * N) then
    let r := w - 2 * N in let u := r / N in let v := r mod N in
    if Nat.ltb u v then
      if OutOrB u then (Some v, Some v)
      else if OutOrB v then (Some u, Some u)
      else (None, None)
    else (None, None)
  else if Nat.ltb w (3 * N + N * N) then (Some (w - (2 * N + N * N)), None)
  else if Nat.ltb w (4 * N + N * N) then (Some (w - (3 * N + N * N)), None)
  else if Nat.ltb w (4 * N + 8 * N * N) then
    let q := (w - (4 * N + N * N)) mod (N * N) in
    let i := q / N in let j := q mod N in
    if Nat.eqb i j then (Some i, Some i)
    else if OutOrB i then (Some j, Some j)
    else if OutOrB j then (Some i, Some i)
    else (Some i, Some j)
  else
    let i := w - (4 * N + 8 * N * N) in (Some i, Some i).

Definition hpc2_pini_shares (n : nat) (ps : list Probe) (B : nat -> bool) : ShareSet :=
  fun j k =>
    match j with
    | 0 => any_of (fun p => match fst (hpc2_pini_contrib n ps B p) with Some x => Nat.eqb x k | None => false end) ps
    | 1 => any_of (fun p => match snd (hpc2_pini_contrib n ps B p) with Some y => Nat.eqb y k | None => false end) ps
    | _ => false
    end.

Lemma hpc2_pini_shares_hit0 :
  forall n ps B p k y,
    ProofSupport.Member p ps ->
    hpc2_pini_contrib n ps B p = (Some k, y) ->
    hpc2_pini_shares n ps B 0 k = true.
Proof.
  intros n ps B p k y Hp Hc. unfold hpc2_pini_shares.
  eapply any_of_member_true; [exact Hp|].
  cbv beta. rewrite Hc. simpl. apply eqb_refl_nat.
Qed.

Lemma hpc2_pini_shares_hit1 :
  forall n ps B p x k,
    ProofSupport.Member p ps ->
    hpc2_pini_contrib n ps B p = (x, Some k) ->
    hpc2_pini_shares n ps B 1 k = true.
Proof.
  intros n ps B p x k Hp Hc. unfold hpc2_pini_shares.
  eapply any_of_member_true; [exact Hp|].
  cbv beta. rewrite Hc. simpl. apply eqb_refl_nat.
Qed.

Lemma hpc2_pini_shares_bounded :
  forall n ps B,
    BoundedBy (hpc2_and_gadget n) (hpc2_pini_shares n ps B) (count_of ps).
Proof.
  intros n ps B j Hj. unfold card_in, hpc2_pini_shares. simpl in Hj.
  apply Nat.ltb_lt in Hj. apply Nat.leb_le.
  destruct j as [|[|j]]; [| |lia].
  - exact (count_filter_any_of_eqb (fun p => fst (hpc2_pini_contrib n ps B p)) ps (upto (S n)) (upto_NoDup (S n))).
  - exact (count_filter_any_of_eqb (fun p => snd (hpc2_pini_contrib n ps B p)) ps (upto (S n)) (upto_NoDup (S n))).
Qed.

Definition hpc2_sim_df (n : nat) (ps : list Probe) (B : nat -> bool)
    (a b : ShareMatrix (hpc2_and_gadget n)) (df_extra : nat -> bool) (idx : nat) : bool :=
  let N := S n in
  let OutOrB k := orb (B k) (hpc2_out_probed n ps k) in
  let u := idx / N in let v := idx mod N in
  let base :=
    if Nat.ltb u v then
      if andb (OutOrB u) (andb (negb (OutOrB v)) (negb (hpc2_two_dom_probed n ps u v))) then
        xorb (andb (a 0 u) (a 1 v)) (andb (b 0 u) (b 1 v))
      else if andb (OutOrB v) (andb (negb (OutOrB u)) (negb (hpc2_two_dom_probed n ps u v))) then
        xorb (andb (a 0 v) (a 1 u)) (andb (b 0 v) (b 1 u))
      else false
    else false in
  xorb base (df_extra idx).

Lemma hpc2_sim_core :
  forall n ps B a b (df_extra : nat -> bool),
    wires_exist (gd_circuit (hpc2_and_gadget n)) (map_over p_wire ps) = true ->
    agree_on (hpc2_and_gadget n) (union_shares (hpc2_pini_shares n ps B) B) a b ->
    (forall idx, idx < S n * S n -> Nat.ltb (idx / S n) (idx mod S n) = false -> df_extra idx = false) ->
    (forall u v, u < S n -> v < S n -> u < v ->
      (orb (B u) (hpc2_out_probed n ps u) = true \/
       orb (B v) (hpc2_out_probed n ps v) = true \/
       hpc2_two_dom_probed n ps u v = true) ->
      df_extra (u * S n + v) = false) ->
    forall tape, ProofSupport.Member tape (bitvectors (S n * S n)) ->
      internal_view (hpc2_and_gadget n) ex_robust ps b
        (zip_xorb tape (map_over (hpc2_sim_df n ps B a b df_extra) (upto (S n * S n)))) =
      internal_view (hpc2_and_gadget n) ex_robust ps a tape /\
      (forall k, k < S n -> orb (B k) (hpc2_out_probed n ps k) = true ->
        forall j, j < S n ->
          xorb (andb (b 0 k) (b 1 j))
            (dom_rbit (S n) (zip_xorb tape (map_over (hpc2_sim_df n ps B a b df_extra) (upto (S n * S n)))) k j) =
          xorb (andb (a 0 k) (a 1 j)) (dom_rbit (S n) tape k j)).
Proof.
  intros n ps B a b df_extra Hw Hagree Hextra_ge Hextra.
  set (N := S n) in *.
  set (OutOrB := fun k => orb (B k) (hpc2_out_probed n ps k)).
  set (df := hpc2_sim_df n ps B a b df_extra).
  assert (Hagree_pair : forall u v, u < N -> v < N -> u <> v ->
    OutOrB u = true ->
    orb (OutOrB v) (hpc2_two_dom_probed n ps (if Nat.ltb u v then u else v) (if Nat.ltb u v then v else u)) = true ->
    a 0 u = b 0 u /\ a 1 u = b 1 u /\ a 0 v = b 0 v /\ a 1 v = b 1 v).
  { intros u v Hu Hv Hne HuO Hor.
    assert (Hu_cov : orb (hpc2_pini_shares n ps B 0 u) (B u) = true /\
                     orb (hpc2_pini_shares n ps B 1 u) (B u) = true).
    { unfold OutOrB in HuO. apply orb_prop in HuO. destruct HuO as [HBu | Hpu].
      - rewrite HBu. split; destruct (hpc2_pini_shares n ps B 0 u); destruct (hpc2_pini_shares n ps B 1 u); reflexivity.
      - destruct (hpc2_out_probed_inv n ps u Hpu) as [p [Hp Hpw]].
        assert (Hc : hpc2_pini_contrib n ps B p = (Some u, Some u)).
        { unfold hpc2_pini_contrib. rewrite Hpw. unfold hpc2_out_wire. change (S n) with N.
          assert (L0 : (4 * N + 8 * N * N + u <? N) = false) by (apply Nat.ltb_ge; lia).
          assert (L1 : (4 * N + 8 * N * N + u <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
          assert (L2 : (4 * N + 8 * N * N + u <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
          assert (L3 : (4 * N + 8 * N * N + u <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
          assert (L4 : (4 * N + 8 * N * N + u <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
          assert (L5 : (4 * N + 8 * N * N + u <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; lia).
          rewrite L0, L1, L2, L3, L4, L5.
          replace (4 * N + 8 * N * N + u - (4 * N + 8 * N * N)) with u by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
          reflexivity. }
        split; [rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
              |rewrite (hpc2_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity]. }
    assert (Hv_cov : orb (hpc2_pini_shares n ps B 0 v) (B v) = true /\
                     orb (hpc2_pini_shares n ps B 1 v) (B v) = true).
    { destruct (OutOrB v) eqn:HvO.
      - unfold OutOrB in HvO. apply orb_prop in HvO. destruct HvO as [HBv | Hpv].
        + rewrite HBv. split; destruct (hpc2_pini_shares n ps B 0 v); destruct (hpc2_pini_shares n ps B 1 v); reflexivity.
        + destruct (hpc2_out_probed_inv n ps v Hpv) as [p [Hp Hpw]].
          assert (Hc : hpc2_pini_contrib n ps B p = (Some v, Some v)).
          { unfold hpc2_pini_contrib. rewrite Hpw. unfold hpc2_out_wire. change (S n) with N.
            assert (L0 : (4 * N + 8 * N * N + v <? N) = false) by (apply Nat.ltb_ge; lia).
            assert (L1 : (4 * N + 8 * N * N + v <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
            assert (L2 : (4 * N + 8 * N * N + v <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
            assert (L3 : (4 * N + 8 * N * N + v <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
            assert (L4 : (4 * N + 8 * N * N + v <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
            assert (L5 : (4 * N + 8 * N * N + v <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; lia).
            rewrite L0, L1, L2, L3, L4, L5.
            replace (4 * N + 8 * N * N + v - (4 * N + 8 * N * N)) with v by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
            reflexivity. }
          split; [rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
                |rewrite (hpc2_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity].
      - apply orb_prop in Hor. destruct Hor as [Abs | Htd]; [discriminate|].
        destruct (hpc2_two_dom_probed_inv n ps _ _ Htd) as [p [Hp Hwp]].
        assert (Hc : hpc2_pini_contrib n ps B p = (Some v, Some v)).
        { unfold hpc2_wire_pair in Hwp. cbv zeta in Hwp. change (S n) with N in Hwp.
          unfold hpc2_pini_contrib. change (S n) with N. unfold OutOrB in HuO, HvO.
          destruct (Nat.ltb (p_wire p) N) eqn:L0;
            [assert (L0' : (p_wire p <? 2 * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in L0; lia); rewrite L0' in Hwp; discriminate|].
          destruct (Nat.ltb (p_wire p) (2 * N)) eqn:L1; [discriminate|].
          destruct (Nat.ltb (p_wire p) (2 * N + N * N)) eqn:L2.
          - destruct (Nat.ltb ((p_wire p - 2 * N) / N) ((p_wire p - 2 * N) mod N)) eqn:Luv; [|discriminate].
            inversion Hwp as [[Hq1 Hq2]]; clear Hwp.
            destruct (Nat.ltb u v) eqn:Euv.
            + assert (Hq1' : (p_wire p - 2 * N) / N = u) by exact Hq1.
              assert (Hq2' : (p_wire p - 2 * N) mod N = v) by exact Hq2.
              rewrite Hq1', Hq2', HuO. reflexivity.
            + assert (Hq1' : (p_wire p - 2 * N) / N = v) by exact Hq1.
              assert (Hq2' : (p_wire p - 2 * N) mod N = u) by exact Hq2.
              rewrite Hq1', Hq2', HvO, HuO. reflexivity.
          - destruct (Nat.ltb (p_wire p) (3 * N + N * N)) eqn:L3;
              [assert (L3' : (p_wire p <? 4 * N + N * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in L3; lia); rewrite L3' in Hwp; discriminate|].
            destruct (Nat.ltb (p_wire p) (4 * N + N * N)) eqn:L4; [discriminate|].
            destruct (Nat.ltb (p_wire p) (4 * N + 8 * N * N)) eqn:L5; [|discriminate].
            set (i := ((p_wire p - (4 * N + N * N)) mod (N * N)) / N) in *.
            set (j := ((p_wire p - (4 * N + N * N)) mod (N * N)) mod N) in *.
            destruct (Nat.ltb i j) eqn:Lij.
            + assert (Eneq : Nat.eqb i j = false) by (apply Nat.eqb_neq; apply Nat.ltb_lt in Lij; lia).
              rewrite Eneq. inversion Hwp as [[Hq1 Hq2]]; clear Hwp.
              destruct (Nat.ltb u v) eqn:Euv.
              * assert (Hq1' : i = u) by exact Hq1. assert (Hq2' : j = v) by exact Hq2.
                rewrite Hq1', Hq2', HuO. reflexivity.
              * assert (Hq1' : i = v) by exact Hq1. assert (Hq2' : j = u) by exact Hq2.
                rewrite Hq1', Hq2', HvO, HuO. reflexivity.
            + destruct (Nat.ltb j i) eqn:Lji; [|discriminate].
              assert (Eneq : Nat.eqb i j = false) by (apply Nat.eqb_neq; apply Nat.ltb_lt in Lji; lia).
              rewrite Eneq. inversion Hwp as [[Hq1 Hq2]]; clear Hwp.
              destruct (Nat.ltb u v) eqn:Euv.
              * assert (Hq1' : j = u) by exact Hq1. assert (Hq2' : i = v) by exact Hq2.
                rewrite Hq1', Hq2', HvO, HuO. reflexivity.
              * assert (Hq1' : j = v) by exact Hq1. assert (Hq2' : i = u) by exact Hq2.
                rewrite Hq1', Hq2', HuO. reflexivity. }
        split; [rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
              |rewrite (hpc2_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity]. }
    destruct Hu_cov as [Hu0 Hu1]. destruct Hv_cov as [Hv0 Hv1].
    unfold hpc2_and_gadget in Hagree; cbn [gd_shares gd_inputs] in Hagree.
    repeat split; apply Hagree; try reflexivity;
      first [exact Hu0 | exact Hu1 | exact Hv0 | exact Hv1 | apply Nat.ltb_lt; exact Hu | apply Nat.ltb_lt; exact Hv]. }
  assert (Hout : forall tape k, ProofSupport.Member tape (bitvectors (N * N)) ->
    k < N -> OutOrB k = true ->
    forall j, j < N ->
      xorb (andb (b 0 k) (b 1 j)) (dom_rbit N (zip_xorb tape (map_over df (upto (N * N)))) k j) =
      xorb (andb (a 0 k) (a 1 j)) (dom_rbit N tape k j)).
  { intros tape k Htape Hk HkO j Hj.
    destruct (Nat.eq_dec k j) as [<-|Hne].
    - repeat rewrite dom_rbit_diag. repeat rewrite gf2_add_zero_r.
      assert (Hk_cov : orb (hpc2_pini_shares n ps B 0 k) (B k) = true /\
                       orb (hpc2_pini_shares n ps B 1 k) (B k) = true).
      { unfold OutOrB in HkO. apply orb_prop in HkO. destruct HkO as [HBk | Hpk].
        - rewrite HBk. split; destruct (hpc2_pini_shares n ps B 0 k); destruct (hpc2_pini_shares n ps B 1 k); reflexivity.
        - destruct (hpc2_out_probed_inv n ps k Hpk) as [p [Hp Hpw]].
          assert (Hc : hpc2_pini_contrib n ps B p = (Some k, Some k)).
          { unfold hpc2_pini_contrib. rewrite Hpw. unfold hpc2_out_wire. change (S n) with N.
            assert (L0 : (4 * N + 8 * N * N + k <? N) = false) by (apply Nat.ltb_ge; lia).
            assert (L1 : (4 * N + 8 * N * N + k <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
            assert (L2 : (4 * N + 8 * N * N + k <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
            assert (L3 : (4 * N + 8 * N * N + k <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
            assert (L4 : (4 * N + 8 * N * N + k <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
            assert (L5 : (4 * N + 8 * N * N + k <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; lia).
            rewrite L0, L1, L2, L3, L4, L5.
            replace (4 * N + 8 * N * N + k - (4 * N + 8 * N * N)) with k by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
            reflexivity. }
          split; [rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
                |rewrite (hpc2_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity]. }
      destruct Hk_cov as [Hk0 Hk1].
      f_equal; symmetry; apply Hagree; try reflexivity; [apply Nat.ltb_lt; exact Hk | exact Hk0 | apply Nat.ltb_lt; exact Hk | exact Hk1].
    - unfold dom_rbit.
      assert (Hekj : Nat.eqb k j = false) by (apply Nat.eqb_neq; exact Hne).
      rewrite Hekj, bit_at_zip_xorb; [|exact Htape].
      pose proof (dom_pair_idx_lt N k j Hk Hj) as Hplt.
      assert (Hpltb : (dom_pair_idx N k j <? N * N) = true) by (apply Nat.ltb_lt; exact Hplt).
      rewrite Hpltb.
      destruct (Nat.ltb k j) eqn:Lkj.
      + assert (Hkj : k < j) by (apply Nat.ltb_lt; exact Lkj).
        assert (Hidx : dom_pair_idx N k j = k * N + j) by (unfold dom_pair_idx; rewrite Lkj; reflexivity).
        rewrite Hidx.
        destruct (div_mod_pair_id N k j Hk Hj) as [Hd Hm].
        destruct (orb (OutOrB j) (hpc2_two_dom_probed n ps k j)) eqn:Hor.
        * assert (Hor' : orb (OutOrB j) (hpc2_two_dom_probed n ps (if Nat.ltb k j then k else j) (if Nat.ltb k j then j else k)) = true)
            by (rewrite Lkj; exact Hor).
          destruct (Hagree_pair k j Hk Hj Hne HkO Hor') as [Hk0 [Hk1 [Hj0 Hj1]]].
          assert (Hdf : df (k * N + j) = false).
          { unfold df, hpc2_sim_df. cbv zeta. change (S n) with N.
            rewrite Hd, Hm, Lkj.
            assert (Hdf_e : df_extra (k * N + j) = false)
              by (apply (Hextra k j Hk Hj Hkj); left; exact HkO).
            rewrite Hdf_e, gf2_add_zero_r.
            unfold OutOrB in *; rewrite HkO.
            destruct (B j || hpc2_out_probed n ps j) eqn:HjO; destruct (hpc2_two_dom_probed n ps k j) eqn:Htd;
              simpl in Hor; try discriminate Hor;
              try (rewrite Hk0, Hk1, Hj0, Hj1; destruct (b 0 k); destruct (b 1 j); destruct (b 0 j); destruct (b 1 k); reflexivity);
              reflexivity. }
          rewrite Hdf, Hk0, Hj1, gf2_add_zero_r. reflexivity.
        * apply orb_false_elim in Hor. destruct Hor as [HjO Htd].
          assert (Hk0 : a 0 k = b 0 k).
          { apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hk|].
            unfold union_shares, OutOrB in *. apply orb_prop in HkO. destruct HkO as [HBk | Hpk].
            - rewrite HBk, orb_true_r. reflexivity.
            - destruct (hpc2_out_probed_inv n ps k Hpk) as [p [Hp Hpw]].
              assert (Hc : hpc2_pini_contrib n ps B p = (Some k, Some k)).
              { unfold hpc2_pini_contrib. rewrite Hpw. unfold hpc2_out_wire. change (S n) with N.
                assert (L0 : (4 * N + 8 * N * N + k <? N) = false) by (apply Nat.ltb_ge; lia).
                assert (L1 : (4 * N + 8 * N * N + k <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L2 : (4 * N + 8 * N * N + k <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L3 : (4 * N + 8 * N * N + k <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L4 : (4 * N + 8 * N * N + k <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L5 : (4 * N + 8 * N * N + k <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; lia).
                rewrite L0, L1, L2, L3, L4, L5.
                replace (4 * N + 8 * N * N + k - (4 * N + 8 * N * N)) with k by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
                reflexivity. }
              rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc). reflexivity. }
          assert (Hdf : df (k * N + j) = xorb (andb (a 0 k) (a 1 j)) (andb (b 0 k) (b 1 j))).
          { unfold df, hpc2_sim_df. cbv zeta. change (S n) with N.
            rewrite (Hextra k j Hk Hj Hkj ltac:(left; exact HkO)), gf2_add_zero_r.
            unfold OutOrB in HkO, HjO. rewrite Hd, Hm, Lkj, HkO, HjO, Htd. reflexivity. }
          rewrite Hdf.
          destruct (a 0 k); destruct (a 1 j); destruct (b 0 k); destruct (b 1 j); destruct (bit_at tape (k * N + j));
            try discriminate Hk0; reflexivity.
      + assert (Hjk : j < k) by (apply Nat.ltb_ge in Lkj; lia).
        assert (Hidx : dom_pair_idx N k j = j * N + k) by (unfold dom_pair_idx; rewrite Lkj; reflexivity).
        rewrite Hidx.
        destruct (div_mod_pair_id N j k Hj Hk) as [Hd Hm].
        assert (Ljk : (j <? k) = true) by (apply Nat.ltb_lt; exact Hjk).
        destruct (orb (OutOrB j) (hpc2_two_dom_probed n ps j k)) eqn:Hor.
        * assert (Hor' : orb (OutOrB j) (hpc2_two_dom_probed n ps (if Nat.ltb k j then k else j) (if Nat.ltb k j then j else k)) = true)
            by (rewrite Lkj; exact Hor).
          destruct (Hagree_pair k j Hk Hj Hne HkO Hor') as [Hk0 [Hk1 [Hj0 Hj1]]].
          assert (Hdf : df (j * N + k) = false).
          { unfold df, hpc2_sim_df. cbv zeta. change (S n) with N.
            rewrite Hd, Hm, Ljk.
            assert (Hdf_e : df_extra (j * N + k) = false)
              by (apply (Hextra j k Hj Hk Hjk); right; left; exact HkO).
            rewrite Hdf_e, gf2_add_zero_r.
            unfold OutOrB in *; rewrite HkO.
            destruct (B j || hpc2_out_probed n ps j) eqn:HjO; destruct (hpc2_two_dom_probed n ps j k) eqn:Htd;
              simpl in Hor; try discriminate Hor;
              try (rewrite Hk0, Hk1, Hj0, Hj1; destruct (b 0 k); destruct (b 1 j); destruct (b 0 j); destruct (b 1 k); reflexivity);
              reflexivity. }
          rewrite Hdf, Hk0, Hj1, gf2_add_zero_r. reflexivity.
        * apply orb_false_elim in Hor. destruct Hor as [HjO Htd].
          assert (Hk0 : a 0 k = b 0 k).
          { apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hk|].
            unfold union_shares, OutOrB in *. apply orb_prop in HkO. destruct HkO as [HBk | Hpk].
            - rewrite HBk, orb_true_r. reflexivity.
            - destruct (hpc2_out_probed_inv n ps k Hpk) as [p [Hp Hpw]].
              assert (Hc : hpc2_pini_contrib n ps B p = (Some k, Some k)).
              { unfold hpc2_pini_contrib. rewrite Hpw. unfold hpc2_out_wire. change (S n) with N.
                assert (L0 : (4 * N + 8 * N * N + k <? N) = false) by (apply Nat.ltb_ge; lia).
                assert (L1 : (4 * N + 8 * N * N + k <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L2 : (4 * N + 8 * N * N + k <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L3 : (4 * N + 8 * N * N + k <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L4 : (4 * N + 8 * N * N + k <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L5 : (4 * N + 8 * N * N + k <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; lia).
                rewrite L0, L1, L2, L3, L4, L5.
                replace (4 * N + 8 * N * N + k - (4 * N + 8 * N * N)) with k by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
                reflexivity. }
              rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity. }
          assert (Hdf : df (j * N + k) = xorb (andb (a 0 k) (a 1 j)) (andb (b 0 k) (b 1 j))).
          { unfold df, hpc2_sim_df. cbv zeta. change (S n) with N.
            rewrite (Hextra j k Hj Hk Hjk ltac:(right; left; exact HkO)), gf2_add_zero_r.
            unfold OutOrB in HkO, HjO. rewrite Hd, Hm, Ljk, HkO, HjO, Htd. reflexivity. }
          rewrite Hdf.
          destruct (a 0 k); destruct (a 1 j); destruct (b 0 k); destruct (b 1 j); destruct (bit_at tape (j * N + k));
            try discriminate Hk0; reflexivity. }
  intros tape Htape. split.
  - unfold internal_view, probe_set. apply support_map_ext. intros o Ho.
    apply member_flat_map_over_inv in Ho. destruct Ho as [p [Hp Ho]].
    assert (Hpw_lt : p_wire p < hpc2_wire_count n).
    { clear -Hw Hp. unfold wires_exist in Hw.
      induction ps as [|q r IH]; simpl in *; [contradiction|].
      apply andb_prop in Hw. destruct Hw as [Hq Hr].
      destruct Hp as [->|Hp]; [apply Nat.ltb_lt in Hq; rewrite circuit_of_fun_count in Hq; exact Hq | exact (IH Hr Hp)]. }
    assert (Hobs_at : forall s cyc,
      ProofSupport.Member s (stable_sources (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n)) (hpc2_wire_count n) (p_wire p)) ->
      gd_value (hpc2_and_gadget n) b (zip_xorb tape (map_over df (upto (N * N)))) cyc s =
      gd_value (hpc2_and_gadget n) a tape cyc s).
    { intros s cyc Hs.
      rewrite hpc2_stable_sources in Hs; [|exact Hpw_lt]. cbv zeta in Hs. change (S n) with N in Hs.
      assert (Hs_lt : s < hpc2_wire_count n).
      { unfold hpc2_wire_count. change (S n) with N.
        destruct (Nat.ltb (p_wire p) (3 * N + N * N)) eqn:E1;
          [apply Nat.ltb_lt in E1; cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s; lia|].
        apply Nat.ltb_ge in E1.
        destruct (Nat.ltb (p_wire p) (4 * N + N * N)) eqn:E2;
          [apply Nat.ltb_lt in E2; cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s; lia|].
        apply Nat.ltb_ge in E2.
        destruct (Nat.ltb (p_wire p) (4 * N + 2 * N * N)) eqn:E3.
        - apply Nat.ltb_lt in E3.
          destruct (div_mod_pair_bound N (p_wire p - (4 * N + N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
          pose proof (dom_pair_idx_lt N _ _ Hi Hj).
          destruct (Nat.eqb _ _); cbn [ProofSupport.Member] in Hs;
            [destruct Hs as [Hseq|[]]; subst s; lia | destruct Hs as [Hseq|[Hseq|[]]]; subst s; lia].
        - apply Nat.ltb_ge in E3.
          destruct (Nat.ltb (p_wire p) (4 * N + 3 * N * N)) eqn:E4;
            [apply Nat.ltb_lt in E4; cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s; lia|].
          apply Nat.ltb_ge in E4.
          destruct (Nat.ltb (p_wire p) (4 * N + 4 * N * N)) eqn:E5.
          + apply Nat.ltb_lt in E5.
            destruct (div_mod_pair_bound N (p_wire p - (4 * N + 3 * N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
            pose proof (dom_pair_idx_lt N _ _ Hi Hj).
            destruct (Nat.eqb _ _); cbn [ProofSupport.Member] in Hs;
              [contradiction | destruct Hs as [Hseq|[Hseq|[]]]; subst s; lia].
          + apply Nat.ltb_ge in E5.
            destruct (Nat.ltb (p_wire p) (4 * N + 5 * N * N)) eqn:E6;
              [apply Nat.ltb_lt in E6; cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s; lia|].
            apply Nat.ltb_ge in E6.
            destruct (Nat.ltb (p_wire p) (4 * N + 6 * N * N)) eqn:E7.
            * apply Nat.ltb_lt in E7.
              destruct (div_mod_pair_bound N (p_wire p - (4 * N + 5 * N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
              cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[Hseq|[]]]; subst s; lia.
            * apply Nat.ltb_ge in E7.
              destruct (Nat.ltb (p_wire p) (4 * N + 7 * N * N)) eqn:E8.
              -- apply Nat.ltb_lt in E8.
                 destruct (div_mod_pair_bound N (p_wire p - (4 * N + 6 * N * N)) ltac:(lia) ltac:(lia)) as [Hi [Hj _]].
                 cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[Hseq|[Hseq|[]]]]; subst s; lia.
              -- apply Nat.ltb_ge in E8.
                 destruct (Nat.ltb (p_wire p) (4 * N + 8 * N * N)) eqn:E9;
                   [apply Nat.ltb_lt in E9; cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s; lia|].
                 apply Nat.ltb_ge in E9.
                 destruct (member_map_over_inv _ _ _ Hs) as [j [Hj <-]].
                 apply member_upto_lt in Hj. unfold hpc2_wire_count in Hpw_lt. nia. }
      repeat (rewrite hpc2_value_eq; [|exact Hs_lt]).
      assert (Hpair_ok : forall i j, i < N -> j < N ->
        p_wire p >= 4 * N + N * N -> p_wire p < 4 * N + 8 * N * N ->
        (p_wire p - (4 * N + N * N)) mod (N * N) = i * N + j ->
        a 0 i = b 0 i /\ a 1 j = b 1 j /\
        (i <> j -> df (dom_pair_idx N i j) = false)).
      { intros i j Hi Hj Hge4 Hlt8 Hmod.
        destruct (div_mod_pair_id N i j Hi Hj) as [Hdi Hdj].
        assert (Hpair_ij : a 0 i = b 0 i /\ a 1 j = b 1 j).
        { assert (Hc_range :
            (i = j /\ hpc2_pini_contrib n ps B p = (Some i, Some i)) \/
            (i <> j /\ hpc2_wire_pair n (p_wire p) = Some (if Nat.ltb i j then i else j, if Nat.ltb i j then j else i) /\
              (hpc2_pini_contrib n ps B p = (Some i, Some j) \/
               (OutOrB i = true /\ hpc2_pini_contrib n ps B p = (Some j, Some j)) \/
               (OutOrB j = true /\ hpc2_pini_contrib n ps B p = (Some i, Some i))))).
          { destruct (Nat.eq_dec i j) as [->|Hne].
            - left; split; [reflexivity|].
              unfold hpc2_pini_contrib; change (S n) with N.
              assert (L0 : (p_wire p <? N) = false) by (apply Nat.ltb_ge; lia).
              assert (L1 : (p_wire p <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
              assert (L2 : (p_wire p <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (L3 : (p_wire p <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (L4 : (p_wire p <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (L5 : (p_wire p <? 4 * N + 8 * N * N) = true) by (apply Nat.ltb_lt; lia).
              rewrite L0, L1, L2, L3, L4, L5, Hmod.
              destruct (div_mod_pair_id N j j Hj Hj) as [Hdj1 Hdj2]. rewrite Hdj1, Hdj2, eqb_refl_nat. reflexivity.
            - right.
              assert (Hwp : hpc2_wire_pair n (p_wire p) = Some (if Nat.ltb i j then i else j, if Nat.ltb i j then j else i)).
              { unfold hpc2_wire_pair; change (S n) with N.
                assert (L1 : (p_wire p <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L2 : (p_wire p <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L4 : (p_wire p <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L5 : (p_wire p <? 4 * N + 8 * N * N) = true) by (apply Nat.ltb_lt; lia).
                rewrite L1, L2, L4, L5, Hmod, Hdi, Hdj.
                destruct (Nat.ltb i j) eqn:Lij; [reflexivity|].
                assert (Lji : (j <? i) = true) by (apply Nat.ltb_ge in Lij; apply Nat.ltb_lt; lia).
                rewrite Lji. reflexivity. }
              split; [exact Hne | split; [exact Hwp|]].
              unfold hpc2_pini_contrib; change (S n) with N.
              assert (L0 : (p_wire p <? N) = false) by (apply Nat.ltb_ge; lia).
              assert (L1 : (p_wire p <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
              assert (L2 : (p_wire p <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (L3 : (p_wire p <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (L4 : (p_wire p <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
              assert (L5 : (p_wire p <? 4 * N + 8 * N * N) = true) by (apply Nat.ltb_lt; lia).
              rewrite L0, L1, L2, L3, L4, L5, Hmod, Hdi, Hdj.
              assert (Eneq : Nat.eqb i j = false) by (apply Nat.eqb_neq; exact Hne). rewrite Eneq.
              unfold OutOrB.
              destruct (orb (B i) (hpc2_out_probed n ps i)) eqn:HiO;
                [right; left; split; reflexivity|].
              destruct (orb (B j) (hpc2_out_probed n ps j)) eqn:HjO;
                [right; right; split; reflexivity | left; reflexivity]. }
          assert (Hcov_out : forall idx, idx < N -> OutOrB idx = true ->
            orb (hpc2_pini_shares n ps B 0 idx) (B idx) = true /\
            orb (hpc2_pini_shares n ps B 1 idx) (B idx) = true).
          { intros idx Hidx HO. unfold OutOrB in HO. apply orb_prop in HO. destruct HO as [HB | Hpr].
            - rewrite HB. split; destruct (hpc2_pini_shares n ps B 0 idx); destruct (hpc2_pini_shares n ps B 1 idx); reflexivity.
            - destruct (hpc2_out_probed_inv n ps idx Hpr) as [q [Hq Hqw]].
              assert (Hcq : hpc2_pini_contrib n ps B q = (Some idx, Some idx)).
              { unfold hpc2_pini_contrib. rewrite Hqw. unfold hpc2_out_wire. change (S n) with N.
                assert (L0 : (4 * N + 8 * N * N + idx <? N) = false) by (apply Nat.ltb_ge; lia).
                assert (L1 : (4 * N + 8 * N * N + idx <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L2 : (4 * N + 8 * N * N + idx <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L3 : (4 * N + 8 * N * N + idx <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L4 : (4 * N + 8 * N * N + idx <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                assert (L5 : (4 * N + 8 * N * N + idx <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; lia).
                rewrite L0, L1, L2, L3, L4, L5.
                replace (4 * N + 8 * N * N + idx - (4 * N + 8 * N * N)) with idx by (rewrite Nat.add_comm; symmetry; apply Nat.add_sub).
                reflexivity. }
              split; [rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hq Hcq); reflexivity
                    |rewrite (hpc2_pini_shares_hit1 _ _ _ _ _ _ Hq Hcq); reflexivity]. }
          destruct Hc_range as [[-> Hc] | [Hne [Hwp [Hc | [[HO Hc] | [HO Hc]]]]]].
          - split; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hj |
              unfold union_shares; rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
            | reflexivity | apply Nat.ltb_lt; exact Hj |
              unfold union_shares; rewrite (hpc2_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity].
          - split; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hi |
              unfold union_shares; rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
            | reflexivity | apply Nat.ltb_lt; exact Hj |
              unfold union_shares; rewrite (hpc2_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity].
          - destruct (Hcov_out i Hi HO) as [Hi0 _].
            split; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hi | exact Hi0
            | reflexivity | apply Nat.ltb_lt; exact Hj |
              unfold union_shares; rewrite (hpc2_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity].
          - destruct (Hcov_out j Hj HO) as [_ Hj1].
            split; apply Hagree; [reflexivity | apply Nat.ltb_lt; exact Hi |
              unfold union_shares; rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity
            | reflexivity | apply Nat.ltb_lt; exact Hj | exact Hj1]. }
        destruct Hpair_ij as [Hai Hbj]. split; [exact Hai | split; [exact Hbj|]].
        intros Hne.
        assert (Hwp : hpc2_wire_pair n (p_wire p) = Some (if Nat.ltb i j then i else j, if Nat.ltb i j then j else i)).
        { unfold hpc2_wire_pair; change (S n) with N.
          assert (L1 : (p_wire p <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
          assert (L2 : (p_wire p <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
          assert (L4 : (p_wire p <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
          assert (L5 : (p_wire p <? 4 * N + 8 * N * N) = true) by (apply Nat.ltb_lt; lia).
          rewrite L1, L2, L4, L5, Hmod, Hdi, Hdj.
          destruct (Nat.ltb i j) eqn:Lij; [reflexivity|].
          assert (Lji : (j <? i) = true) by (apply Nat.ltb_ge in Lij; apply Nat.ltb_lt; lia).
          rewrite Lji. reflexivity. }
        pose proof (hpc2_two_dom_probed_member n ps _ _ p Hp Hwp) as Htd.
        unfold df, hpc2_sim_df, dom_pair_idx. cbv zeta. change (S n) with N.
        destruct (Nat.ltb i j) eqn:Lij.
        - assert (Hij : i < j) by (apply Nat.ltb_lt; exact Lij).
          destruct (div_mod_pair_id N i j Hi Hj) as [Hd2 Hm2].
          rewrite Hd2, Hm2, Lij, (Hextra i j Hi Hj Hij ltac:(right; right; exact Htd)), gf2_add_zero_r.
          rewrite Htd, !andb_false_r.
          destruct (orb (B i) (hpc2_out_probed n ps i)); destruct (orb (B j) (hpc2_out_probed n ps j)); reflexivity.
        - assert (Hji : j < i) by (apply Nat.ltb_ge in Lij; lia).
          assert (Lji : (j <? i) = true) by (apply Nat.ltb_lt; exact Hji).
          destruct (div_mod_pair_id N j i Hj Hi) as [Hd2 Hm2].
          rewrite Hd2, Hm2, Lji, (Hextra j i Hj Hi Hji ltac:(right; right; exact Htd)), gf2_add_zero_r.
          rewrite Htd, !andb_false_r.
          destruct (orb (B j) (hpc2_out_probed n ps j)); destruct (orb (B i) (hpc2_out_probed n ps i)); reflexivity. }
      destruct (Nat.ltb (p_wire p) N) eqn:W0.
      + assert (W1 : (p_wire p <? 3 * N + N * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in W0; lia).
        rewrite W1 in Hs. cbn [ProofSupport.Member] in Hs. destruct Hs as [Hseq|[]]; subst s.
        unfold hpc2_eval; change (S n) with N; rewrite W0.
        symmetry; apply Hagree; [reflexivity | exact W0|].
        assert (Hc : hpc2_pini_contrib n ps B p = (Some (p_wire p), None))
          by (unfold hpc2_pini_contrib; change (S n) with N; rewrite W0; reflexivity).
        unfold union_shares; rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity.
      + destruct (Nat.ltb (p_wire p) (2 * N)) eqn:W1.
        * assert (W1' : (p_wire p <? 3 * N + N * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in W1; lia).
          rewrite W1' in Hs. cbn [ProofSupport.Member] in Hs. destruct Hs as [Hseq|[]]; subst s.
          unfold hpc2_eval; change (S n) with N; rewrite W0, W1.
          symmetry; apply Hagree; [reflexivity | unfold hpc2_and_gadget; cbn [gd_shares]; apply Nat.ltb_lt; apply Nat.ltb_ge in W0; apply Nat.ltb_lt in W1; lia|].
          assert (Hc : hpc2_pini_contrib n ps B p = (None, Some (p_wire p - N)))
            by (unfold hpc2_pini_contrib; change (S n) with N; rewrite W0, W1; reflexivity).
          unfold union_shares; rewrite (hpc2_pini_shares_hit1 _ _ _ _ _ _ Hp Hc); reflexivity.
        * destruct (Nat.ltb (p_wire p) (2 * N + N * N)) eqn:W2.
          -- assert (W2' : (p_wire p <? 3 * N + N * N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in W2; lia).
             rewrite W2' in Hs. cbn [ProofSupport.Member] in Hs. destruct Hs as [Hseq|[]]; subst s.
             assert (Hr_lt : p_wire p - 2 * N < N * N) by (apply Nat.ltb_lt in W2; apply Nat.ltb_ge in W1; lia).
             destruct (div_mod_pair_bound N (p_wire p - 2 * N) ltac:(lia) Hr_lt) as [Hu [Hv Hdm]].
             unfold hpc2_eval; change (S n) with N; rewrite W0, W1, W2.
             rewrite bit_at_zip_xorb; [|exact Htape].
             assert (Hr_b : (p_wire p - 2 * N <? N * N) = true) by (apply Nat.ltb_lt; exact Hr_lt).
             rewrite Hr_b.
             assert (Hdf_zero : df (p_wire p - 2 * N) = false).
             { unfold df, hpc2_sim_df. cbv zeta. change (S n) with N.
               destruct (Nat.ltb ((p_wire p - 2 * N) / N) ((p_wire p - 2 * N) mod N)) eqn:Luv.
               - assert (Hwp : hpc2_wire_pair n (p_wire p) = Some ((p_wire p - 2 * N) / N, (p_wire p - 2 * N) mod N)).
                 { unfold hpc2_wire_pair; change (S n) with N; rewrite W1, W2, Luv. reflexivity. }
                 pose proof (hpc2_two_dom_probed_member n ps _ _ p Hp Hwp) as Htd.
                 assert (Hdf_e : df_extra (p_wire p - 2 * N) = false)
                   by (rewrite <- Hdm; apply (Hextra _ _ Hu Hv ltac:(apply Nat.ltb_lt; exact Luv) ltac:(right; right; exact Htd))).
                 rewrite Hdf_e, gf2_add_zero_r, Htd, !andb_false_r.
                 destruct (orb (B ((p_wire p - 2 * N) / N)) (hpc2_out_probed n ps ((p_wire p - 2 * N) / N)));
                 destruct (orb (B ((p_wire p - 2 * N) mod N)) (hpc2_out_probed n ps ((p_wire p - 2 * N) mod N))); reflexivity.
               - rewrite (Hextra_ge (p_wire p - 2 * N) Hr_lt Luv). reflexivity. }
             rewrite Hdf_zero, gf2_add_zero_r. reflexivity.
          -- destruct (Nat.ltb (p_wire p) (3 * N + N * N)) eqn:W3.
             ++ cbn [ProofSupport.Member] in Hs. destruct Hs as [Hseq|[]]; subst s.
                unfold hpc2_eval; change (S n) with N; rewrite W0, W1, W2, W3.
                destruct cyc; [reflexivity|].
                assert (Ls : (p_wire p - (2 * N + N * N) <? N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in W3; apply Nat.ltb_ge in W2; lia).
                symmetry; apply Hagree; [reflexivity | unfold hpc2_and_gadget; cbn [gd_shares]; exact Ls|].
                assert (Hc : hpc2_pini_contrib n ps B p = (Some (p_wire p - (2 * N + N * N)), None))
                  by (unfold hpc2_pini_contrib; change (S n) with N; rewrite W0, W1, W2, W3; reflexivity).
                unfold union_shares; rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity.
             ++ destruct (Nat.ltb (p_wire p) (4 * N + N * N)) eqn:W4.
                ** cbn [ProofSupport.Member] in Hs. destruct Hs as [Hseq|[]]; subst s.
                   unfold hpc2_eval; change (S n) with N.
                   assert (Ls0 : (p_wire p - (3 * N + N * N) <? N) = true) by (apply Nat.ltb_lt; apply Nat.ltb_lt in W4; apply Nat.ltb_ge in W3; lia).
                   rewrite Ls0. f_equal.
                   symmetry; apply Hagree; [reflexivity | unfold hpc2_and_gadget; cbn [gd_shares]; exact Ls0|].
                   assert (Hc : hpc2_pini_contrib n ps B p = (Some (p_wire p - (3 * N + N * N)), None))
                     by (unfold hpc2_pini_contrib; change (S n) with N; rewrite W0, W1, W2, W3, W4; reflexivity).
                   unfold union_shares; rewrite (hpc2_pini_shares_hit0 _ _ _ _ _ _ Hp Hc); reflexivity.
                ** apply Nat.ltb_ge in W4.
                   assert (Hrbit_ok : forall i j, i < N -> j < N -> p_wire p >= 4 * N + N * N -> p_wire p < 4 * N + 8 * N * N ->
                     (p_wire p - (4 * N + N * N)) mod (N * N) = i * N + j ->
                     dom_rbit N (zip_xorb tape (map_over df (upto (N * N)))) i j = dom_rbit N tape i j).
                   { intros i j Hi Hj Hge4 Hlt8 Hmod.
                     destruct (Hpair_ok i j Hi Hj Hge4 Hlt8 Hmod) as [_ [_ Hdf]].
                     destruct (Nat.eq_dec i j) as [->|Hne]; [repeat rewrite dom_rbit_diag; reflexivity|].
                     unfold dom_rbit. assert (Ene : Nat.eqb i j = false) by (apply Nat.eqb_neq; exact Hne).
                     rewrite Ene, bit_at_zip_xorb; [|exact Htape].
                     pose proof (dom_pair_idx_lt N i j Hi Hj) as Hplt.
                     assert (Hpltb : (dom_pair_idx N i j <? N * N) = true) by (apply Nat.ltb_lt; exact Hplt).
                     rewrite Hpltb, (Hdf Hne), gf2_add_zero_r. reflexivity. }
                   destruct (Nat.ltb (p_wire p) (4 * N + 2 * N * N)) eqn:W5.
                   --- assert (Hp_lt : p_wire p - (4 * N + N * N) < N * N) by (apply Nat.ltb_lt in W5; lia).
                       destruct (div_mod_pair_bound N (p_wire p - (4 * N + N * N)) ltac:(lia) Hp_lt) as [Hi [Hj Hdm]].
                       set (i := (p_wire p - (4 * N + N * N)) / N) in *.
                       set (j := (p_wire p - (4 * N + N * N)) mod N) in *.
                       pose proof (hpc2_mod_block n (p_wire p) 0 (p_wire p - (4 * N + N * N)) W4 ltac:(lia) Hp_lt) as Hmod.
                       rewrite <- Hdm in Hmod.
                       destruct (Hpair_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W5; lia) Hmod) as [Hai [Hbj _]].
                       pose proof (Hrbit_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W5; lia) Hmod) as Hrbt.
                       destruct (Nat.eqb i j) eqn:Eij; cbn [ProofSupport.Member] in Hs.
                       +++ destruct Hs as [Hseq|[]]; subst s.
                           unfold hpc2_eval; change (S n) with N.
                           assert (Ls0 : (N + j <? N) = false) by (apply Nat.ltb_ge; lia).
                           assert (Ls1 : (N + j <? 2 * N) = true) by (apply Nat.ltb_lt; lia).
                           rewrite Ls0, Ls1. replace (N + j - N) with j by lia. symmetry; exact Hbj.
                       +++ destruct Hs as [Hseq|[Hseq|[]]]; subst s.
                           *** unfold hpc2_eval; change (S n) with N.
                               assert (Ls0 : (N + j <? N) = false) by (apply Nat.ltb_ge; lia).
                               assert (Ls1 : (N + j <? 2 * N) = true) by (apply Nat.ltb_lt; lia).
                               rewrite Ls0, Ls1. replace (N + j - N) with j by lia. symmetry; exact Hbj.
                           *** pose proof (dom_pair_idx_lt N i j Hi Hj) as Hdplt.
                               unfold hpc2_eval; change (S n) with N.
                               assert (Ls0 : (2 * N + dom_pair_idx N i j <? N) = false) by (apply Nat.ltb_ge; lia).
                               assert (Ls1 : (2 * N + dom_pair_idx N i j <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                               assert (Ls2 : (2 * N + dom_pair_idx N i j <? 2 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
                               rewrite Ls0, Ls1, Ls2.
                               replace (2 * N + dom_pair_idx N i j - 2 * N) with (dom_pair_idx N i j) by lia.
                               assert (Ene : Nat.eqb i j = false) by exact Eij.
                               fold (dom_rbit N (zip_xorb tape (map_over df (upto (N * N)))) i j).
                               unfold dom_rbit in Hrbt. rewrite Ene in Hrbt. exact Hrbt.
                   --- apply Nat.ltb_ge in W5.
                       destruct (Nat.ltb (p_wire p) (4 * N + 3 * N * N)) eqn:W6.
                       +++ cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s.
                           assert (Hp_lt : p_wire p - (4 * N + 2 * N * N) < N * N) by (apply Nat.ltb_lt in W6; lia).
                           destruct (div_mod_pair_bound N (p_wire p - (4 * N + 2 * N * N)) ltac:(lia) Hp_lt) as [Hi [Hj Hdm]].
                           set (i := (p_wire p - (4 * N + 2 * N * N)) / N) in *.
                           set (j := (p_wire p - (4 * N + 2 * N * N)) mod N) in *.
                           pose proof (hpc2_mod_block n (p_wire p) 1 (p_wire p - (4 * N + 2 * N * N)) W4 ltac:(lia) Hp_lt) as Hmod.
                           rewrite <- Hdm in Hmod.
                           destruct (Hpair_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W6; lia) Hmod) as [_ [Hbj _]].
                           pose proof (Hrbit_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W6; lia) Hmod) as Hrbt.
                           unfold hpc2_eval; change (S n) with N.
                           assert (W4' : (p_wire p <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; exact W4).
                           assert (W5' : (p_wire p <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact W5).
                           rewrite W0, W1, W2, W3, W4', W5', W6.
                           destruct cyc; [reflexivity|]. cbv zeta. fold i j. rewrite Hbj, Hrbt. reflexivity.
                       +++ apply Nat.ltb_ge in W6.
                           destruct (Nat.ltb (p_wire p) (4 * N + 4 * N * N)) eqn:W7.
                           *** assert (Hp_lt : p_wire p - (4 * N + 3 * N * N) < N * N) by (apply Nat.ltb_lt in W7; lia).
                               destruct (div_mod_pair_bound N (p_wire p - (4 * N + 3 * N * N)) ltac:(lia) Hp_lt) as [Hi [Hj Hdm]].
                               set (i := (p_wire p - (4 * N + 3 * N * N)) / N) in *.
                               set (j := (p_wire p - (4 * N + 3 * N * N)) mod N) in *.
                               pose proof (hpc2_mod_block n (p_wire p) 2 (p_wire p - (4 * N + 3 * N * N)) W4 ltac:(lia) Hp_lt) as Hmod.
                               rewrite <- Hdm in Hmod.
                               destruct (Hpair_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W7; lia) Hmod) as [Hai [_ _]].
                               pose proof (Hrbit_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W7; lia) Hmod) as Hrbt.
                               destruct (Nat.eqb i j) eqn:Eij; cbn [ProofSupport.Member] in Hs; [contradiction|].
                               destruct Hs as [Hseq|[Hseq|[]]]; subst s.
                               ---- unfold hpc2_eval; change (S n) with N.
                                    assert (Ls0 : (i <? N) = true) by (apply Nat.ltb_lt; exact Hi). rewrite Ls0. symmetry; exact Hai.
                               ---- pose proof (dom_pair_idx_lt N i j Hi Hj) as Hdplt.
                                    unfold hpc2_eval; change (S n) with N.
                                    assert (Ls0 : (2 * N + dom_pair_idx N i j <? N) = false) by (apply Nat.ltb_ge; lia).
                                    assert (Ls1 : (2 * N + dom_pair_idx N i j <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                                    assert (Ls2 : (2 * N + dom_pair_idx N i j <? 2 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
                                    rewrite Ls0, Ls1, Ls2.
                                    replace (2 * N + dom_pair_idx N i j - 2 * N) with (dom_pair_idx N i j) by lia.
                                    unfold dom_rbit in Hrbt. rewrite Eij in Hrbt. exact Hrbt.
                           *** apply Nat.ltb_ge in W7.
                               destruct (Nat.ltb (p_wire p) (4 * N + 5 * N * N)) eqn:W8.
                               ---- cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s.
                                    assert (Hp_lt : p_wire p - (4 * N + 4 * N * N) < N * N) by (apply Nat.ltb_lt in W8; lia).
                                    destruct (div_mod_pair_bound N (p_wire p - (4 * N + 4 * N * N)) ltac:(lia) Hp_lt) as [Hi [Hj Hdm]].
                                    set (i := (p_wire p - (4 * N + 4 * N * N)) / N) in *.
                                    set (j := (p_wire p - (4 * N + 4 * N * N)) mod N) in *.
                                    pose proof (hpc2_mod_block n (p_wire p) 3 (p_wire p - (4 * N + 4 * N * N)) W4 ltac:(lia) Hp_lt) as Hmod.
                                    rewrite <- Hdm in Hmod.
                                    destruct (Hpair_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W8; lia) Hmod) as [Hai [_ _]].
                                    pose proof (Hrbit_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W8; lia) Hmod) as Hrbt.
                                    unfold hpc2_eval; change (S n) with N.
                                    assert (W4' : (p_wire p <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; exact W4).
                                    assert (W5' : (p_wire p <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact W5).
                                    assert (W6' : (p_wire p <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; exact W6).
                                    assert (W7' : (p_wire p <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; exact W7).
                                    rewrite W0, W1, W2, W3, W4', W5', W6', W7', W8.
                                    destruct cyc; [reflexivity|]. cbv zeta. fold i j. rewrite Hai, Hrbt. reflexivity.
                               ---- apply Nat.ltb_ge in W8.
                                    destruct (Nat.ltb (p_wire p) (4 * N + 6 * N * N)) eqn:W9.
                                    ++++ assert (Hp_lt : p_wire p - (4 * N + 5 * N * N) < N * N) by (apply Nat.ltb_lt in W9; lia).
                                         destruct (div_mod_pair_bound N (p_wire p - (4 * N + 5 * N * N)) ltac:(lia) Hp_lt) as [Hi [Hj Hdm]].
                                         set (i := (p_wire p - (4 * N + 5 * N * N)) / N) in *.
                                         set (j := (p_wire p - (4 * N + 5 * N * N)) mod N) in *.
                                         pose proof (hpc2_mod_block n (p_wire p) 4 (p_wire p - (4 * N + 5 * N * N)) W4 ltac:(lia) Hp_lt) as Hmod.
                                         rewrite <- Hdm in Hmod.
                                         destruct (Hpair_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W9; lia) Hmod) as [Hai [Hbj _]].
                                         pose proof (Hrbit_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W9; lia) Hmod) as Hrbt.
                                         cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[Hseq|[]]]; subst s.
                                         **** unfold hpc2_eval; change (S n) with N.
                                              assert (Ls0 : (2 * N + N * N + i <? N) = false) by (apply Nat.ltb_ge; lia).
                                              assert (Ls1 : (2 * N + N * N + i <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                                              assert (Ls2 : (2 * N + N * N + i <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                              assert (Ls3 : (2 * N + N * N + i <? 3 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
                                              rewrite Ls0, Ls1, Ls2, Ls3.
                                              replace (2 * N + N * N + i - (2 * N + N * N)) with i by lia.
                                              destruct cyc; [reflexivity | rewrite Hai; reflexivity].
                                         **** unfold hpc2_eval; change (S n) with N.
                                              assert (Ls0 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 5 * N * N)) <? N) = false) by (apply Nat.ltb_ge; lia).
                                              assert (Ls1 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 5 * N * N)) <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                                              assert (Ls2 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 5 * N * N)) <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                              assert (Ls3 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 5 * N * N)) <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                              assert (Ls4 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 5 * N * N)) <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                              assert (Ls5 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 5 * N * N)) <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
                                              assert (Ls6 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 5 * N * N)) <? 4 * N + 3 * N * N) = true) by (apply Nat.ltb_lt; lia).
                                              rewrite Ls0, Ls1, Ls2, Ls3, Ls4, Ls5, Ls6.
                                              replace (4 * N + 2 * N * N + (p_wire p - (4 * N + 5 * N * N)) - (4 * N + 2 * N * N))
                                                with (p_wire p - (4 * N + 5 * N * N)) by lia.
                                              destruct cyc; [reflexivity|]. cbv zeta. fold i j. rewrite Hbj, Hrbt. reflexivity.
                                    ++++ apply Nat.ltb_ge in W9.
                                         destruct (Nat.ltb (p_wire p) (4 * N + 7 * N * N)) eqn:W10.
                                         **** assert (Hp_lt : p_wire p - (4 * N + 6 * N * N) < N * N) by (apply Nat.ltb_lt in W10; lia).
                                              destruct (div_mod_pair_bound N (p_wire p - (4 * N + 6 * N * N)) ltac:(lia) Hp_lt) as [Hi [Hj Hdm]].
                                              set (i := (p_wire p - (4 * N + 6 * N * N)) / N) in *.
                                              set (j := (p_wire p - (4 * N + 6 * N * N)) mod N) in *.
                                              pose proof (hpc2_mod_block n (p_wire p) 5 (p_wire p - (4 * N + 6 * N * N)) W4 ltac:(lia) Hp_lt) as Hmod.
                                              rewrite <- Hdm in Hmod.
                                              destruct (Hpair_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W10; lia) Hmod) as [Hai [Hbj _]].
                                              pose proof (Hrbit_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W10; lia) Hmod) as Hrbt.
                                              cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[Hseq|[Hseq|[]]]]; subst s.
                                              ----- unfold hpc2_eval; change (S n) with N.
                                                    assert (Ls0 : (2 * N + N * N + i <? N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls1 : (2 * N + N * N + i <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls2 : (2 * N + N * N + i <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls3 : (2 * N + N * N + i <? 3 * N + N * N) = true) by (apply Nat.ltb_lt; lia).
                                                    rewrite Ls0, Ls1, Ls2, Ls3.
                                                    replace (2 * N + N * N + i - (2 * N + N * N)) with i by lia.
                                                    destruct cyc; [reflexivity | rewrite Hai; reflexivity].
                                              ----- unfold hpc2_eval; change (S n) with N.
                                                    assert (Ls0 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls1 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls2 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls3 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls4 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls5 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls6 : (4 * N + 2 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 4 * N + 3 * N * N) = true) by (apply Nat.ltb_lt; lia).
                                                    rewrite Ls0, Ls1, Ls2, Ls3, Ls4, Ls5, Ls6.
                                                    replace (4 * N + 2 * N * N + (p_wire p - (4 * N + 6 * N * N)) - (4 * N + 2 * N * N))
                                                      with (p_wire p - (4 * N + 6 * N * N)) by lia.
                                                    destruct cyc; [reflexivity|]. cbv zeta. fold i j. rewrite Hbj, Hrbt. reflexivity.
                                              ----- unfold hpc2_eval; change (S n) with N.
                                                    assert (Ls0 : (4 * N + 4 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls1 : (4 * N + 4 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 2 * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls2 : (4 * N + 4 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls3 : (4 * N + 4 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls4 : (4 * N + 4 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls5 : (4 * N + 4 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls6 : (4 * N + 4 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls7 : (4 * N + 4 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; lia).
                                                    assert (Ls8 : (4 * N + 4 * N * N + (p_wire p - (4 * N + 6 * N * N)) <? 4 * N + 5 * N * N) = true) by (apply Nat.ltb_lt; lia).
                                                    rewrite Ls0, Ls1, Ls2, Ls3, Ls4, Ls5, Ls6, Ls7, Ls8.
                                                    replace (4 * N + 4 * N * N + (p_wire p - (4 * N + 6 * N * N)) - (4 * N + 4 * N * N))
                                                      with (p_wire p - (4 * N + 6 * N * N)) by lia.
                                                    destruct cyc; [reflexivity|]. cbv zeta. fold i j. rewrite Hai, Hrbt. reflexivity.
                                         **** apply Nat.ltb_ge in W10.
                                              destruct (Nat.ltb (p_wire p) (4 * N + 8 * N * N)) eqn:W11.
                                              ----- cbn [ProofSupport.Member] in Hs; destruct Hs as [Hseq|[]]; subst s.
                                                    assert (Hp_lt : p_wire p - (4 * N + 7 * N * N) < N * N) by (apply Nat.ltb_lt in W11; lia).
                                                    destruct (div_mod_pair_bound N (p_wire p - (4 * N + 7 * N * N)) ltac:(lia) Hp_lt) as [Hi [Hj Hdm]].
                                                    set (i := (p_wire p - (4 * N + 7 * N * N)) / N) in *.
                                                    set (j := (p_wire p - (4 * N + 7 * N * N)) mod N) in *.
                                                    pose proof (hpc2_mod_block n (p_wire p) 6 (p_wire p - (4 * N + 7 * N * N)) W4 ltac:(lia) Hp_lt) as Hmod.
                                                    rewrite <- Hdm in Hmod.
                                                    destruct (Hpair_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W11; lia) Hmod) as [Hai [Hbj _]].
                                                    pose proof (Hrbit_ok i j Hi Hj W4 ltac:(apply Nat.ltb_lt in W11; lia) Hmod) as Hrbt.
                                                    unfold hpc2_eval; change (S n) with N.
                                                    assert (W4' : (p_wire p <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; exact W4).
                                                    assert (W5' : (p_wire p <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; exact W5).
                                                    assert (W6' : (p_wire p <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; exact W6).
                                                    assert (W7' : (p_wire p <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; exact W7).
                                                    assert (W8' : (p_wire p <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; exact W8).
                                                    assert (W9' : (p_wire p <? 4 * N + 6 * N * N) = false) by (apply Nat.ltb_ge; exact W9).
                                                    assert (W10' : (p_wire p <? 4 * N + 7 * N * N) = false) by (apply Nat.ltb_ge; exact W10).
                                                    rewrite W0, W1, W2, W3, W4', W5', W6', W7', W8', W9', W10', W11.
                                                    destruct cyc as [|[|cyc']]; [reflexivity | reflexivity|].
                                                    cbv zeta. fold i j. rewrite Hai, Hbj, Hrbt. reflexivity.
                                              ----- apply Nat.ltb_ge in W11.
                                                    destruct (member_map_over_inv _ _ _ Hs) as [j [Hj <-]].
                                                    apply member_upto_lt in Hj.
                                                    set (k := p_wire p - (4 * N + 8 * N * N)) in *.
                                                    assert (Hk_lt : k < N) by (unfold k, hpc2_wire_count in *; nia).
                                                    assert (HkO : OutOrB k = true).
                                                    { unfold OutOrB. rewrite (hpc2_out_probed_member n ps k p Hp); [apply orb_true_r | unfold hpc2_out_wire; change (S n) with N; unfold k; lia]. }
                                                    unfold hpc2_eval; change (S n) with N.
                                                    assert (Ls0 : (4 * N + 7 * N * N + k * N + j <? N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls1 : (4 * N + 7 * N * N + k * N + j <? 2 * N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls2 : (4 * N + 7 * N * N + k * N + j <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls3 : (4 * N + 7 * N * N + k * N + j <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls4 : (4 * N + 7 * N * N + k * N + j <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls5 : (4 * N + 7 * N * N + k * N + j <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls6 : (4 * N + 7 * N * N + k * N + j <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls7 : (4 * N + 7 * N * N + k * N + j <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls8 : (4 * N + 7 * N * N + k * N + j <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls9 : (4 * N + 7 * N * N + k * N + j <? 4 * N + 6 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls10 : (4 * N + 7 * N * N + k * N + j <? 4 * N + 7 * N * N) = false) by (apply Nat.ltb_ge; nia).
                                                    assert (Ls11 : (4 * N + 7 * N * N + k * N + j <? 4 * N + 8 * N * N) = true) by (apply Nat.ltb_lt; nia).
                                                    rewrite Ls0, Ls1, Ls2, Ls3, Ls4, Ls5, Ls6, Ls7, Ls8, Ls9, Ls10, Ls11.
                                                    destruct cyc as [|[|cyc']]; [reflexivity | reflexivity|].
                                                    cbv zeta.
                                                    replace (4 * N + 7 * N * N + k * N + j - (4 * N + 7 * N * N)) with (k * N + j)
                                                      by (rewrite <- Nat.add_assoc, (Nat.add_comm (4 * N + 7 * N * N)), Nat.add_sub; reflexivity).
                                                    destruct (div_mod_pair_id N k j Hk_lt Hj) as [Hd Hm].
                                                    rewrite Hd, Hm. exact (Hout tape k Htape Hk_lt HkO j Hj). }
    unfold ex_robust, hpc2_and_gadget in Ho. cbn [gd_circuit] in Ho. rewrite circuit_of_fun_count in Ho.
    assert (Ho_cases : exists s, ProofSupport.Member s (stable_sources (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n)) (hpc2_wire_count n) (p_wire p)) /\
      (o = obs_at s (p_cycle p) \/ o = obs_at s (prev_cycle (p_cycle p)))).
    { clear -Ho. induction (stable_sources (circuit_of_fun (hpc2_wire_count n) (hpc2_gate n)) (hpc2_wire_count n) (p_wire p)) as [|s r IH];
        cbn [flat_map_over] in Ho; [contradiction|].
      destruct Ho as [Ho1|[Ho2|Ho]]; [exists s; split; [left; reflexivity | left; first [exact Ho1 | symmetry; exact Ho1]]
        | exists s; split; [left; reflexivity | right; first [exact Ho2 | symmetry; exact Ho2]]
        | destruct (IH Ho) as [s0 [Hs0 Hdec]]; exists s0; split; [right; exact Hs0 | exact Hdec]]. }
    destruct Ho_cases as [s [Hs [->| ->]]]; simpl; apply Hobs_at; exact Hs.
  - intros k Hk HkO j Hj. exact (Hout tape k Htape Hk HkO j Hj).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem hpc2_and_is_pini :
  forall n d, PINI (hpc2_and_gadget n) ex_robust d.
Proof.
  intros n d ps B Hw _.
  exists (hpc2_pini_shares n ps B). split; [apply hpc2_pini_shares_bounded|].
  intros a b Hagree.
  set (N := S n) in *.
  set (df := hpc2_sim_df n ps B a b (fun _ => false)).
  apply (bit_tapes_xor_hides (N * N) (list bool) (list_eqb bool_eqb)
           (split_view (hpc2_and_gadget n) ex_robust ps B a)
           (split_view (hpc2_and_gadget n) ex_robust ps B b) df).
  intros tape Htape.
  destruct (hpc2_sim_core n ps B a b (fun _ => false) Hw Hagree
              (fun _ _ _ => eq_refl) (fun _ _ _ _ _ _ => eq_refl) tape Htape) as [Hint Hout].
  unfold split_view. f_equal; [exact Hint|].
  unfold output_view, selected_outputs. apply support_map_ext. intros k Hk.
  change (gd_shares (hpc2_and_gadget n)) with N in Hk.
  pose proof (support_filter_true B (upto N) k Hk) as HBk.
  apply support_filter_member in Hk. apply member_upto_lt in Hk.
  assert (HOk : orb (B k) (hpc2_out_probed n ps k) = true) by (rewrite HBk; reflexivity).
  replace (gd_out (hpc2_and_gadget n) k) with (hpc2_out_wire n k) by reflexivity.
  rewrite (hpc2_value_eq n b); [|unfold hpc2_wire_count, hpc2_out_wire; unfold N in *; cbv zeta; lia].
  rewrite (hpc2_value_eq n a); [|unfold hpc2_wire_count, hpc2_out_wire; unfold N in *; cbv zeta; lia].
  unfold hpc2_eval, hpc2_out_wire. cbv zeta. change (S n) with N.
  assert (L0 : (4 * N + 8 * N * N + k <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L1 : (4 * N + 8 * N * N + k <? 2 * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L2 : (4 * N + 8 * N * N + k <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L3 : (4 * N + 8 * N * N + k <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L4 : (4 * N + 8 * N * N + k <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L5 : (4 * N + 8 * N * N + k <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L6 : (4 * N + 8 * N * N + k <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L7 : (4 * N + 8 * N * N + k <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L8 : (4 * N + 8 * N * N + k <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L9 : (4 * N + 8 * N * N + k <? 4 * N + 6 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L10 : (4 * N + 8 * N * N + k <? 4 * N + 7 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L11 : (4 * N + 8 * N * N + k <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  rewrite L0, L1, L2, L3, L4, L5, L6, L7, L8, L9, L10, L11.
  cbn [gd_read hpc2_and_gadget].
  replace (4 * N + 8 * N * N + k - (4 * N + 8 * N * N)) with k by lia.
  apply xor_sum_upto_ext. intros j Hj. exact (Hout k Hk HOk j Hj).
Qed.

Definition hpc2_sni_shares (n : nat) (ps : list Probe) : ShareSet :=
  hpc2_pini_shares n ps (fun _ => false).

Definition hpc2_sni_probe_hit (n k : nat) (p : Probe) : option nat :=
  let N := S n in
  let w := p_wire p in
  if Nat.ltb w (2 * N) then None
  else if Nat.ltb w (2 * N + N * N) then
    match hpc2_wire_pair n w with
    | Some (u, v) =>
      if Nat.eqb u k then Some v else if Nat.eqb v k then Some u else None
    | None => None
    end
  else if Nat.ltb w (4 * N + N * N) then None
  else if Nat.ltb w (4 * N + 8 * N * N) then
    match hpc2_wire_pair n w with
    | Some (u, v) =>
      if Nat.eqb u k then Some v else if Nat.eqb v k then Some u else None
    | None => None
    end
  else Some (w - (4 * N + 8 * N * N)).

Definition hpc2_sni_blocked (n : nat) (ps : list Probe) (B : nat -> bool) (k j : nat) : bool :=
  orb (B j) (any_of (fun p => match hpc2_sni_probe_hit n k p with Some z => Nat.eqb z j | None => false end) ps).

Definition hpc2_sni_target (n : nat) (ps : list Probe) (B : nat -> bool) (k : nat) : nat :=
  find_unblocked (S n) (hpc2_sni_blocked n ps B k).

Lemma hpc2_sni_target_spec :
  forall n ps B k,
    Nat.leb (split_size (hpc2_and_gadget n) ps B) n = true ->
    B k = true ->
    let j := hpc2_sni_target n ps B k in
    j < S n /\
    B j = false /\
    hpc2_out_probed n ps j = false /\
    hpc2_two_dom_probed n ps (if Nat.ltb k j then k else j) (if Nat.ltb k j then j else k) = false.
Proof.
  intros n ps B k Hsz HBk.
  set (N := S n).
  assert (Hcnt_lt : count_of (filter_of (hpc2_sni_blocked n ps B k) (upto N)) < N).
  { apply Nat.leb_le in Hsz. unfold split_size, selected_outputs in Hsz.
    change (gd_shares (hpc2_and_gadget n)) with N in Hsz.
    pose proof (count_filter_orb B
      (fun j => any_of (fun p => match hpc2_sni_probe_hit n k p with Some z => Nat.eqb z j | None => false end) ps)
      (upto N)) as Horb.
    pose proof (count_filter_any_of_eqb (hpc2_sni_probe_hit n k) ps (upto N) (upto_NoDup N)) as Hhit.
    unfold hpc2_sni_blocked. lia. }
  destruct (find_unblocked_spec N (hpc2_sni_blocked n ps B k) Hcnt_lt) as [Hj_lt Hblk].
  cbv zeta in Hj_lt, Hblk.
  change (find_unblocked N (hpc2_sni_blocked n ps B k)) with (hpc2_sni_target n ps B k) in Hj_lt, Hblk.
  set (j := hpc2_sni_target n ps B k) in *.
  unfold hpc2_sni_blocked in Hblk. apply orb_false_elim in Hblk. destruct Hblk as [HBj Hany].
  assert (Hne : k <> j) by (intro Heq; rewrite <- Heq, HBk in HBj; discriminate).
  assert (Houtp : hpc2_out_probed n ps j = false).
  { destruct (hpc2_out_probed n ps j) eqn:Eop; [|reflexivity].
    destruct (hpc2_out_probed_inv n ps j Eop) as [p [Hp Hpw]].
    assert (Hhit : hpc2_sni_probe_hit n k p = Some j).
    { unfold hpc2_sni_probe_hit. rewrite Hpw. unfold hpc2_out_wire. change (S n) with N.
      assert (L1 : (4 * N + 8 * N * N + j <? 2 * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
      assert (L2 : (4 * N + 8 * N * N + j <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
      assert (L3 : (4 * N + 8 * N * N + j <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
      assert (L4 : (4 * N + 8 * N * N + j <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
      rewrite L1, L2, L3, L4. f_equal. unfold N in *; lia. }
    pose proof (any_of_member_true
      (fun p0 => match hpc2_sni_probe_hit n k p0 with Some z => Nat.eqb z j | None => false end)
      ps p Hp ltac:(cbv beta; rewrite Hhit; apply eqb_refl_nat)) as Habs.
    rewrite Habs in Hany. discriminate. }
  assert (Htd : hpc2_two_dom_probed n ps (if Nat.ltb k j then k else j) (if Nat.ltb k j then j else k) = false).
  { destruct (hpc2_two_dom_probed n ps (if Nat.ltb k j then k else j) (if Nat.ltb k j then j else k)) eqn:Etd; [|reflexivity].
    destruct (hpc2_two_dom_probed_inv n ps _ _ Etd) as [p [Hp Hwp]].
    assert (Hhit : hpc2_sni_probe_hit n k p = Some j).
    { unfold hpc2_wire_pair in Hwp. cbv zeta in Hwp. change (S n) with N in Hwp.
      unfold hpc2_sni_probe_hit. change (S n) with N.
      destruct (Nat.ltb (p_wire p) (2 * N)) eqn:L1; [discriminate|].
      destruct (Nat.ltb (p_wire p) (2 * N + N * N)) eqn:L2.
      - unfold hpc2_wire_pair; change (S n) with N; rewrite L1, L2.
        rewrite Hwp. destruct (Nat.ltb k j); [rewrite eqb_refl_nat; reflexivity |
          assert (Ejk : (j =? k) = false) by (apply Nat.eqb_neq; lia); rewrite Ejk, eqb_refl_nat; reflexivity].
      - destruct (Nat.ltb (p_wire p) (4 * N + N * N)) eqn:L3; [discriminate|].
        destruct (Nat.ltb (p_wire p) (4 * N + 8 * N * N)) eqn:L4; [|discriminate].
        unfold hpc2_wire_pair; change (S n) with N; rewrite L1, L2, L3, L4, Hwp.
        destruct (Nat.ltb k j); [rewrite eqb_refl_nat; reflexivity |
          assert (Ejk : (j =? k) = false) by (apply Nat.eqb_neq; lia); rewrite Ejk, eqb_refl_nat; reflexivity]. }
    pose proof (any_of_member_true
      (fun p0 => match hpc2_sni_probe_hit n k p0 with Some z => Nat.eqb z j | None => false end)
      ps p Hp ltac:(cbv beta; rewrite Hhit; apply eqb_refl_nat)) as Habs.
    rewrite Habs in Hany. discriminate. }
  split; [exact Hj_lt | split; [exact HBj | split; [exact Houtp | exact Htd]]].
Qed.

Definition hpc2_sni_df_base_rbit (n : nat) (ps : list Probe)
    (a b : ShareMatrix (hpc2_and_gadget n)) (k j : nat) : bool :=
  let N := S n in
  if Nat.eqb k j then false
  else hpc2_sim_df n ps (fun _ => false) a b (fun _ => false) (dom_pair_idx N k j).

Definition hpc2_sni_delta (n : nat) (ps : list Probe)
    (a b : ShareMatrix (hpc2_and_gadget n)) (k : nat) : bool :=
  let N := S n in
  xorb (xor_sum_upto (fun j => andb (a 0 k) (a 1 j)) N)
       (xor_sum_upto (fun j => xorb (andb (b 0 k) (b 1 j)) (hpc2_sni_df_base_rbit n ps a b k j)) N).

Definition hpc2_sni_df_out (n : nat) (ps : list Probe) (B : nat -> bool)
    (a b : ShareMatrix (hpc2_and_gadget n)) (idx : nat) : bool :=
  let N := S n in
  let OutP x := hpc2_out_probed n ps x in
  let NeedK x := andb (B x) (negb (OutP x)) in
  let u := idx / N in let v := idx mod N in
  if Nat.ltb u v then
    if andb (NeedK u) (Nat.eqb v (hpc2_sni_target n ps B u)) then hpc2_sni_delta n ps a b u
    else if andb (NeedK v) (Nat.eqb u (hpc2_sni_target n ps B v)) then hpc2_sni_delta n ps a b v
    else false
  else false.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem hpc2_and_is_sni :
  forall n d, d <= n -> SNI (hpc2_and_gadget n) ex_robust d.
Proof.
  intros n d Hd ps B Hw Hsz.
  assert (Hsz_n : Nat.leb (split_size (hpc2_and_gadget n) ps B) n = true)
    by (apply Nat.leb_le; apply Nat.leb_le in Hsz; lia).
  exists (hpc2_sni_shares n ps).
  split; [unfold hpc2_sni_shares; apply hpc2_pini_shares_bounded|].
  intros a b Hagree.
  assert (Hagree0 : agree_on (hpc2_and_gadget n) (union_shares (hpc2_pini_shares n ps (fun _ => false)) (fun _ => false)) a b).
  { intros j k Hj Hk Hu. apply Hagree; [exact Hj | exact Hk|].
    unfold union_shares in Hu. rewrite orb_false_r in Hu. exact Hu. }
  set (N := S n) in *.
  set (df_out := hpc2_sni_df_out n ps B a b).
  set (df := hpc2_sim_df n ps (fun _ => false) a b df_out).
  assert (Hextra_ge : forall idx, idx < N * N -> Nat.ltb (idx / N) (idx mod N) = false -> df_out idx = false).
  { intros idx _ Lge. unfold df_out, hpc2_sni_df_out. cbv zeta. change (S n) with N. rewrite Lge. reflexivity. }
  assert (Hextra_uv : forall u v, u < N -> v < N -> u < v ->
    (orb false (hpc2_out_probed n ps u) = true \/
     orb false (hpc2_out_probed n ps v) = true \/
     hpc2_two_dom_probed n ps u v = true) ->
    df_out (u * N + v) = false).
  { intros u v Hu Hv Huv Hdisj.
    destruct (div_mod_pair_id N u v Hu Hv) as [Hdu Hdv].
    unfold df_out, hpc2_sni_df_out. cbv zeta. change (S n) with N.
    rewrite Hdu, Hdv. assert (Luv : (u <? v) = true) by (apply Nat.ltb_lt; exact Huv). rewrite Luv.
    destruct (andb (andb (B u) (negb (hpc2_out_probed n ps u))) (Nat.eqb v (hpc2_sni_target n ps B u))) eqn:E1.
    - apply andb_prop in E1. destruct E1 as [ENu Evt]. apply andb_prop in ENu. destruct ENu as [HBu Hnou].
      apply eqb_sound_nat in Evt. subst v.
      destruct (hpc2_sni_target_spec n ps B u Hsz_n HBu) as [_ [_ [Hnov Htd]]].
      rewrite Luv in Htd. destruct Hdisj as [H1 | [H2 | H3]]; simpl in *;
        [rewrite H1 in Hnou; discriminate | rewrite H2 in Hnov; discriminate | rewrite H3 in Htd; discriminate].
    - destruct (andb (andb (B v) (negb (hpc2_out_probed n ps v))) (Nat.eqb u (hpc2_sni_target n ps B v))) eqn:E2; [|reflexivity].
      apply andb_prop in E2. destruct E2 as [ENv Eut]. apply andb_prop in ENv. destruct ENv as [HBv Hnov].
      apply eqb_sound_nat in Eut. subst u.
      destruct (hpc2_sni_target_spec n ps B v Hsz_n HBv) as [_ [_ [Hnou Htd]]].
      assert (Lvu : (v <? hpc2_sni_target n ps B v) = false) by (apply Nat.ltb_ge; lia).
      rewrite Lvu in Htd. destruct Hdisj as [H1 | [H2 | H3]]; simpl in *;
        [rewrite H1 in Hnou; discriminate | rewrite H2 in Hnov; discriminate | rewrite H3 in Htd; discriminate]. }
  apply (bit_tapes_xor_hides (N * N) (list bool) (list_eqb bool_eqb)
           (split_view (hpc2_and_gadget n) ex_robust ps B a)
           (split_view (hpc2_and_gadget n) ex_robust ps B b) df).
  intros tape Htape.
  destruct (hpc2_sim_core n ps (fun _ => false) a b df_out Hw Hagree0 Hextra_ge Hextra_uv tape Htape)
    as [Hint Hout_p].
  unfold split_view. f_equal; [exact Hint|].
  unfold output_view, selected_outputs. apply support_map_ext. intros k Hk.
  change (gd_shares (hpc2_and_gadget n)) with N in Hk.
  pose proof (support_filter_true B (upto N) k Hk) as HBk.
  apply support_filter_member in Hk. apply member_upto_lt in Hk.
  replace (gd_out (hpc2_and_gadget n) k) with (hpc2_out_wire n k) by reflexivity.
  rewrite (hpc2_value_eq n b); [|unfold hpc2_wire_count, hpc2_out_wire; unfold N in *; cbv zeta; lia].
  rewrite (hpc2_value_eq n a); [|unfold hpc2_wire_count, hpc2_out_wire; unfold N in *; cbv zeta; lia].
  unfold hpc2_eval, hpc2_out_wire. cbv zeta. change (S n) with N.
  assert (L0 : (4 * N + 8 * N * N + k <? N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L1 : (4 * N + 8 * N * N + k <? 2 * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L2 : (4 * N + 8 * N * N + k <? 2 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L3 : (4 * N + 8 * N * N + k <? 3 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L4 : (4 * N + 8 * N * N + k <? 4 * N + N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L5 : (4 * N + 8 * N * N + k <? 4 * N + 2 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L6 : (4 * N + 8 * N * N + k <? 4 * N + 3 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L7 : (4 * N + 8 * N * N + k <? 4 * N + 4 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L8 : (4 * N + 8 * N * N + k <? 4 * N + 5 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L9 : (4 * N + 8 * N * N + k <? 4 * N + 6 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L10 : (4 * N + 8 * N * N + k <? 4 * N + 7 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  assert (L11 : (4 * N + 8 * N * N + k <? 4 * N + 8 * N * N) = false) by (apply Nat.ltb_ge; unfold N in *; lia).
  rewrite L0, L1, L2, L3, L4, L5, L6, L7, L8, L9, L10, L11.
  cbn [gd_read hpc2_and_gadget].
  replace (4 * N + 8 * N * N + k - (4 * N + 8 * N * N)) with k by lia.
  destruct (hpc2_out_probed n ps k) eqn:Hopk.
  - apply xor_sum_upto_ext. intros j Hj. apply Hout_p; [exact Hk | rewrite Hopk; reflexivity | exact Hj].
  - destruct (hpc2_sni_target_spec n ps B k Hsz_n HBk) as [Ht_lt [HBt _]].
    cbv zeta in Ht_lt, HBt.
    set (t := hpc2_sni_target n ps B k) in *.
    assert (Hrow : forall j, j < N ->
      dom_rbit N (zip_xorb tape (map_over df (upto (N * N)))) k j =
      xorb (dom_rbit N tape k j)
           (xorb (hpc2_sni_df_base_rbit n ps a b k j)
                 (if Nat.eqb j t then hpc2_sni_delta n ps a b k else false))).
    { intros j Hj.
      destruct (Nat.eq_dec k j) as [<-|Hne].
      - repeat rewrite dom_rbit_diag. unfold hpc2_sni_df_base_rbit. rewrite eqb_refl_nat.
        assert (Ekt : Nat.eqb k t = false) by (apply Nat.eqb_neq; intro Heq; rewrite <- Heq, HBk in HBt; discriminate).
        rewrite Ekt. reflexivity.
      - unfold dom_rbit, hpc2_sni_df_base_rbit.
        assert (Ekj : Nat.eqb k j = false) by (apply Nat.eqb_neq; exact Hne).
        rewrite Ekj, bit_at_zip_xorb; [|exact Htape].
        pose proof (dom_pair_idx_lt N k j Hk Hj) as Hplt.
        assert (Hpltb : (dom_pair_idx N k j <? N * N) = true) by (apply Nat.ltb_lt; exact Hplt).
        rewrite Hpltb.
        unfold df, hpc2_sim_df, hpc2_sni_df_out, df_out. cbv zeta. change (S n) with N.
        assert (Hout_eq : hpc2_sni_df_out n ps B a b (dom_pair_idx N k j) =
          if Nat.eqb j t then hpc2_sni_delta n ps a b k else false).
        { unfold hpc2_sni_df_out, dom_pair_idx. cbv zeta. change (S n) with N.
          destruct (Nat.ltb k j) eqn:Lkj.
          - destruct (div_mod_pair_id N k j Hk Hj) as [Hd2 Hm2]. rewrite Hd2, Hm2, Lkj, HBk, Hopk. simpl.
            fold t. destruct (Nat.eqb j t) eqn:Ejt; [reflexivity|].
            destruct (B j) eqn:HBj; simpl; [|reflexivity].
            destruct (hpc2_sni_target_spec n ps B j Hsz_n HBj) as [_ [HBtj _]].
            assert (Ekt : Nat.eqb k (hpc2_sni_target n ps B j) = false)
              by (apply Nat.eqb_neq; intro Heq; rewrite <- Heq, HBk in HBtj; discriminate).
            rewrite Ekt, andb_false_r. reflexivity.
          - assert (Hjk : j < k) by (apply Nat.ltb_ge in Lkj; lia).
            destruct (div_mod_pair_id N j k Hj Hk) as [Hd2 Hm2]. rewrite Hd2, Hm2.
            assert (Ljk : (j <? k) = true) by (apply Nat.ltb_lt; exact Hjk). rewrite Ljk.
            destruct (B j) eqn:HBj; simpl.
            + destruct (hpc2_sni_target_spec n ps B j Hsz_n HBj) as [_ [HBtj _]].
              assert (Ekt : Nat.eqb k (hpc2_sni_target n ps B j) = false)
                by (apply Nat.eqb_neq; intro Heq; rewrite <- Heq, HBk in HBtj; discriminate).
              rewrite Ekt, andb_false_r, HBk, Hopk. simpl. fold t. reflexivity.
            + rewrite HBk, Hopk. simpl. fold t. reflexivity. }
        rewrite Hout_eq.
        unfold hpc2_sim_df; cbv zeta; change (S n) with N; rewrite !gf2_add_zero_r.
        destruct (dom_rbit N tape k j); destruct (if Nat.eqb j t then hpc2_sni_delta n ps a b k else false); reflexivity. }
    transitivity (xor_sum_upto (fun j =>
      xorb (xorb (andb (b 0 k) (b 1 j)) (hpc2_sni_df_base_rbit n ps a b k j))
           (xorb (dom_rbit N tape k j) (if Nat.eqb j t then hpc2_sni_delta n ps a b k else false))) N).
    { apply xor_sum_upto_ext. intros j Hj. rewrite (Hrow j Hj).
      destruct (b 0 k && b 1 j); destruct (dom_rbit N tape k j);
        destruct (hpc2_sni_df_base_rbit n ps a b k j);
        destruct (if Nat.eqb j t then hpc2_sni_delta n ps a b k else false); reflexivity. }
    rewrite (xor_sum_upto_xorb _ _ N), (xor_sum_upto_xorb (dom_rbit N tape k) _ N).
    rewrite (xor_sum_upto_point N t (hpc2_sni_delta n ps a b k) Ht_lt).
    unfold hpc2_sni_delta. change (S n) with N.
    assert (Hrhs : xor_sum_upto (fun j => xorb (andb (a 0 k) (a 1 j)) (dom_rbit N tape k j)) N =
      xorb (xor_sum_upto (fun j => andb (a 0 k) (a 1 j)) N)
           (xor_sum_upto (fun j => dom_rbit N tape k j) N))
      by apply xor_sum_upto_xorb.
    rewrite Hrhs.
    destruct (xor_sum_upto (fun j => xorb (b 0 k && b 1 j) (hpc2_sni_df_base_rbit n ps a b k j)) N);
    destruct (xor_sum_upto (fun j => dom_rbit N tape k j) N);
    destruct (xor_sum_upto (fun j => a 0 k && a 1 j) N); reflexivity.
Qed.

(* =========================================================================
   Section 4: Multi-output BusGadget, Strong-PINI DAG composition, and
              arbitrary-order GF(2) straight-line compiler
   ========================================================================= *)

Record BusGadget : Type := {
  bg_prob : Probability;
  bg_circuit : Circuit;
  bg_ops : nat -> list bool -> bool;
  bg_inputs : nat;
  bg_wires : nat;
  bg_shares : nat;
  bg_out : nat -> nat -> nat;
  bg_wire_read : nat -> nat;
  bg_assign : (nat -> nat -> bool) -> Tape bg_prob -> nat -> nat -> bool;
  bg_start : (nat -> nat -> bool) -> Tape bg_prob -> nat -> bool
}.

Definition bg_value (bg : BusGadget) (a : nat -> nat -> bool)
    (tape : Tape (bg_prob bg)) (cyc w : nat) : bool :=
  value_at gf2_sharing (bg_ops bg) (bg_circuit bg)
    (bg_start bg a tape) (bg_assign bg a tape) cyc w.

Definition bus_selected_pairs (bg : BusGadget) (B : nat -> bool) : list (nat * nat) :=
  flat_map_over (fun u => map_over (fun k => (u, k)) (filter_of B (upto (bg_shares bg))))
    (upto (bg_wires bg)).

Definition bus_output_view (bg : BusGadget) (B : nat -> bool)
    (a : nat -> nat -> bool) (tape : Tape (bg_prob bg)) : list bool :=
  map_over (fun uk => bg_value bg a tape (bg_wire_read bg (fst uk)) (bg_out bg (fst uk) (snd uk)))
    (bus_selected_pairs bg B).

Definition bus_internal_view (bg : BusGadget) (E : Expansion) (ps : list Probe)
    (a : nat -> nat -> bool) (tape : Tape (bg_prob bg)) : list bool :=
  map_over (fun o => obs_value gf2_sharing (bg_ops bg) (bg_circuit bg)
                      (bg_start bg a tape) (bg_assign bg a tape) o)
    (probe_set E (bg_circuit bg) ps).

Definition bus_split_view (bg : BusGadget) (E : Expansion) (ps : list Probe) (B : nat -> bool)
    (a : nat -> nat -> bool) (tape : Tape (bg_prob bg)) : list bool :=
  app (bus_internal_view bg E ps a tape) (bus_output_view bg B a tape).

Definition bus_agree_on (bg : BusGadget) (I : nat -> nat -> bool)
    (a b : nat -> nat -> bool) : Prop :=
  forall j k, j < bg_inputs bg -> k < bg_shares bg -> I j k = true -> a j k = b j k.

Definition BusSimulableFrom (bg : BusGadget) (I : nat -> nat -> bool)
    (view : (nat -> nat -> bool) -> Tape (bg_prob bg) -> list bool) : Prop :=
  forall a b, bus_agree_on bg I a b ->
    SameDistribution (bg_prob bg) (list bool) (list_eqb bool_eqb) (view a) (view b).

Definition BusStrongPINI (bg : BusGadget) (E : Expansion) (d : nat) : Prop :=
  forall ps (B : nat -> bool),
    wires_exist (bg_circuit bg) (map_over p_wire ps) = true ->
    Nat.leb (count_of ps) d = true ->
    exists I_dom : nat -> bool,
      Nat.leb (count_of (filter_of I_dom (upto (bg_shares bg)))) (count_of ps) = true /\
      BusSimulableFrom bg (fun _ k => orb (I_dom k) (B k)) (bus_split_view bg E ps B).

Definition bus_gadget_well_formed (bg : BusGadget) : Prop :=
  well_formed (bg_circuit bg) = true /\
  0 < bg_shares bg /\
  0 < bg_inputs bg /\
  bg_inputs bg <= bg_wires bg /\
  (forall u k, u < bg_wires bg -> k < bg_shares bg ->
    bg_out bg u k < wire_count (bg_circuit bg)).

Definition id_bus_gadget (n m : nat) : BusGadget :=
  let N := S n in {|
  bg_prob := bit_tapes 0;
  bg_circuit := circuit_of_fun (m * N) g_in;
  bg_ops := bool_ops;
  bg_inputs := m;
  bg_wires := m;
  bg_shares := N;
  bg_out := fun u k => u * N + k;
  bg_wire_read := fun _ => 0;
  bg_assign := fun a _ _ i => a (i / N) (i mod N);
  bg_start := fun _ _ _ => false
|}.

Definition witness_BusGadget : BusGadget := id_bus_gadget 1 1.

Lemma id_bus_well_formed :
  forall n m, 0 < m -> bus_gadget_well_formed (id_bus_gadget n m).
Proof.
  intros n m Hm. split; [|split; [|split; [|split]]].
  - unfold id_bus_gadget; cbn [bg_circuit]. apply well_formed_circuit_of_fun. intros; reflexivity.
  - simpl; lia.
  - exact Hm.
  - simpl; lia.
  - intros u k Hu Hk. simpl in *. rewrite circuit_of_fun_count. nia.
Qed.

Lemma id_bus_has_counting_mass :
  forall n m, HasCountingMass (bg_prob (id_bus_gadget n m)).
Proof.
  intros n m. unfold id_bus_gadget; cbn [bg_prob]. apply counting_has_counting_mass.
Qed.

Lemma id_bus_value :
  forall n m a tape cyc w,
    w < m * S n ->
    bg_value (id_bus_gadget n m) a tape cyc w = a (w / S n) (w mod S n).
Proof.
  intros n m a tape cyc w Hw.
  unfold bg_value, id_bus_gadget; cbn [bg_ops bg_circuit bg_start bg_assign].
  assert (Hwf : well_formed (circuit_of_fun (m * S n) g_in) = true)
    by (apply well_formed_circuit_of_fun; intros; reflexivity).
  rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; exact Hw].
  rewrite gate_at_circuit_of_fun; [reflexivity | exact Hw].
Qed.

Lemma div_mod_pair_id_gen :
  forall N u v, v < N ->
    (u * N + v) / N = u /\ (u * N + v) mod N = v.
Proof.
  intros N u v Hv.
  assert (HN : N <> 0) by lia.
  rewrite (Nat.add_comm (u * N) v).
  split; [rewrite Nat.div_add; [rewrite Nat.div_small; lia | exact HN]
       | rewrite Nat.Div0.mod_add; [rewrite Nat.mod_small; lia]].
Qed.

Lemma id_bus_is_bus_strong_pini :
  forall n m E d,
    0 < m ->
    LocalExpansion E ->
    BusStrongPINI (id_bus_gadget n m) E d.
Proof.
  intros n m E d Hm Hloc ps B Hw _.
  set (N := S n) in *.
  set (I_dom := fun k => any_of (fun p => Nat.eqb (p_wire p mod N) k) ps).
  exists I_dom. split.
  - unfold id_bus_gadget; cbn [bg_shares]. apply Nat.leb_le.
    exact (count_filter_any_of_eqb (fun p => Some (p_wire p mod N)) ps (upto N) (upto_NoDup N)).
  - intros a b Hagree.
    apply (identical_views_are_identically_distributed (bg_prob (id_bus_gadget n m))
             (list bool) (list_eqb bool_eqb)).
    intros tape.
    assert (Hwf : well_formed (bg_circuit (id_bus_gadget n m)) = true)
      by (destruct (id_bus_well_formed n m Hm) as [H1 _]; exact H1).
    unfold bus_split_view. f_equal.
    + unfold bus_internal_view. apply support_map_ext. intros o Ho.
      unfold probe_set in Ho. apply member_flat_map_over_inv in Ho.
      destruct Ho as [p [Hp Ho]].
      assert (Hpw_lt : p_wire p < wire_count (bg_circuit (id_bus_gadget n m))).
      { clear -Hw Hp. unfold wires_exist in Hw. induction ps as [|q r IH]; simpl in *; [contradiction|].
        apply andb_prop in Hw. destruct Hw as [Hq Hr].
        destruct Hp as [->|Hp]; [apply Nat.ltb_lt in Hq; exact Hq | exact (IH Hr Hp)]. }
      assert (Hdom : forall w, w < wire_count (bg_circuit (id_bus_gadget n m)) ->
        match gate_at (bg_circuit (id_bus_gadget n m)) w with
        | g_in _ => True
        | g_reg s => s mod N = w mod N
        | g_op _ args => all_of (fun u => Nat.eqb (u mod N) (w mod N)) args = true
        end).
      { intros w Hwl. unfold id_bus_gadget in Hwl; cbn [bg_circuit] in Hwl; rewrite circuit_of_fun_count in Hwl.
        unfold id_bus_gadget; cbn [bg_circuit]. rewrite gate_at_circuit_of_fun; [exact I | exact Hwl]. }
      destruct (le_domain E Hloc (bg_circuit (id_bus_gadget n m)) (fun w => w mod N) p o
                  Hwf Hpw_lt Hdom Ho) as [How_lt How_dom].
      unfold id_bus_gadget in Hpw_lt, How_lt; cbn [bg_circuit] in Hpw_lt, How_lt;
        rewrite circuit_of_fun_count in Hpw_lt, How_lt.
      assert (HI_p : I_dom (obs_wire o mod N) = true).
      { rewrite How_dom. unfold I_dom. eapply any_of_member_true; [exact Hp | apply eqb_refl_nat]. }
      assert (Hdiv_lt : obs_wire o / N < m) by (apply Nat.Div0.div_lt_upper_bound; lia).
      assert (Hmod_lt : obs_wire o mod N < N) by (apply Nat.mod_upper_bound; discriminate).
      assert (Hval_eq : forall cyc,
        bg_value (id_bus_gadget n m) a tape cyc (obs_wire o) =
        bg_value (id_bus_gadget n m) b tape cyc (obs_wire o)).
      { intros cyc. repeat rewrite id_bus_value; [|exact How_lt | exact How_lt].
        apply Hagree; [exact Hdiv_lt | exact Hmod_lt | change (S n) with N; rewrite HI_p; reflexivity]. }
      destruct o as [ow oc | ow oc]; simpl in *; [apply Hval_eq | f_equal; apply Hval_eq].
    + unfold bus_output_view, bus_selected_pairs. apply support_map_ext. intros [u k] Huk.
      apply member_flat_map_over_inv in Huk. destruct Huk as [u0 [Hu0 Huk]].
      apply member_map_over_inv in Huk. destruct Huk as [k0 [Hk0 Heq]].
      inversion Heq; subst u0 k0; clear Heq.
      pose proof (support_filter_true B (upto (bg_shares (id_bus_gadget n m))) k Hk0) as HBk.
      apply member_upto_lt in Hu0. apply support_filter_member in Hk0. apply member_upto_lt in Hk0.
      unfold id_bus_gadget in Hu0, Hk0; cbn [bg_wires bg_shares] in Hu0, Hk0.
      assert (Huk_lt : u * N + k < m * S n) by (unfold N in *; nia).
      simpl fst; simpl snd.
      change (bg_out (id_bus_gadget n m) u k) with (u * N + k).
      repeat rewrite id_bus_value; [|exact Huk_lt | exact Huk_lt].
      destruct (div_mod_pair_id_gen N u k Hk0) as [Hdiv Hm0].
      change (S n) with N. rewrite Hdiv, Hm0.
      apply Hagree; [exact Hu0 | exact Hk0 | rewrite HBk, orb_true_r; reflexivity].
Qed.

(* Constant-output 1-input gadget so every BoolGate satisfies 0 < gd_inputs. *)
Definition masked_const_gadget (n : nat) (c : bool) : Gadget :=
  let N := S n in {|
  gd_share := gf2_sharing;
  gd_prob := bit_tapes 0;
  gd_circuit := circuit_of_fun N (fun w =>
    if andb c (Nat.eqb w 0) then g_op 1 nil else g_op 0 nil);
  gd_ops := bool_ops;
  gd_inputs := 1;
  gd_shares := N;
  gd_out := fun k => k;
  gd_read := 0;
  gd_assign := fun a _ _ i => a 0 i;
  gd_start := fun _ _ _ => false
|}.

Lemma masked_const_well_formed :
  forall n c, gadget_well_formed (masked_const_gadget n c).
Proof.
  intros n c. split; [|split].
  - unfold masked_const_gadget; cbn [gd_circuit].
    apply well_formed_circuit_of_fun. intros w Hw.
    destruct (andb c (Nat.eqb w 0)); reflexivity.
  - simpl; lia.
  - intros k Hk. simpl in *. rewrite circuit_of_fun_count. lia.
Qed.

Lemma masked_const_value :
  forall n c a tape cyc k,
    k < S n ->
    gd_value (masked_const_gadget n c) a tape cyc k =
    andb c (Nat.eqb k 0).
Proof.
  intros n c a tape cyc k Hk.
  destruct (masked_const_well_formed n c) as [Hwf _].
  unfold gd_value, masked_const_gadget in *; cbn [gd_share gd_ops gd_circuit gd_start gd_assign] in *.
  rewrite value_at_unfold; [|exact Hwf | rewrite circuit_of_fun_count; lia].
  rewrite gate_at_circuit_of_fun; [|exact Hk].
  destruct c; destruct k; reflexivity.
Qed.

Lemma masked_const_correct :
  forall n c (a : ShareMatrix (masked_const_gadget n c)) tape,
    xor_sum_upto (fun k => gd_value (masked_const_gadget n c) a tape 0
      (gd_out (masked_const_gadget n c) k)) (S n) = c.
Proof.
  intros n c a tape.
  transitivity (xor_sum_upto (fun k => andb c (Nat.eqb k 0)) (S n)).
  { apply xor_sum_upto_ext. intros k Hk. unfold masked_const_gadget at 1; cbn [gd_out].
    apply masked_const_value; exact Hk. }
  transitivity (xor_sum_upto (fun k => if Nat.eqb k 0 then c else false) (S n)).
  { apply xor_sum_upto_ext. intros k _; destruct c; destruct k; reflexivity. }
  apply (xor_sum_upto_point (S n) 0 c ltac:(lia)).
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_const_is_strong_pini :
  forall n c E d, LocalExpansion E -> StrongPINI (masked_const_gadget n c) E d.
Proof.
  intros n c E d Hloc ps B Hw _.
  exists (fun _ => false). split.
  { apply Nat.leb_le.
    assert (Hz : forall l : list nat, count_of (filter_of (fun _ => false) l) = 0)
      by (clear; intros l; induction l as [|x r IH]; simpl; [reflexivity | exact IH]).
    rewrite Hz. lia. }
  intros a b _.
  apply (identical_views_are_identically_distributed (gd_prob (masked_const_gadget n c))
           (list bool) (list_eqb bool_eqb)).
  intros tape.
  destruct (masked_const_well_formed n c) as [Hwf _].
  assert (Hdom : forall w, w < wire_count (gd_circuit (masked_const_gadget n c)) ->
    match gate_at (gd_circuit (masked_const_gadget n c)) w with
    | g_in _ => True
    | g_reg s => 0 = 0
    | g_op _ args => all_of (fun _ => Nat.eqb 0 0) args = true
    end).
  { intros w Hwl. unfold masked_const_gadget in Hwl; cbn [gd_circuit] in Hwl; rewrite circuit_of_fun_count in Hwl.
    unfold masked_const_gadget; cbn [gd_circuit]. rewrite gate_at_circuit_of_fun; [|exact Hwl].
    destruct (andb c (Nat.eqb w 0)); reflexivity. }
  assert (Hval_eq : forall cyc w, w < S n ->
    gd_value (masked_const_gadget n c) a tape cyc w =
    gd_value (masked_const_gadget n c) b tape cyc w).
  { intros cyc w Hw0. repeat rewrite masked_const_value; [reflexivity | exact Hw0 | exact Hw0]. }
  unfold split_view. f_equal.
  - unfold internal_view, probe_set. apply support_map_ext. intros o Ho.
    apply member_flat_map_over_inv in Ho. destruct Ho as [p [Hp Ho]].
    assert (Hpw_lt : p_wire p < wire_count (gd_circuit (masked_const_gadget n c))).
    { clear -Hw Hp. unfold wires_exist in Hw. induction ps as [|q r IH]; simpl in *; [contradiction|].
      apply andb_prop in Hw. destruct Hw as [Hq Hr].
      destruct Hp as [->|Hp]; [apply Nat.ltb_lt in Hq; exact Hq | exact (IH Hr Hp)]. }
    destruct (le_domain E Hloc (gd_circuit (masked_const_gadget n c)) (fun _ => 0) p o
                Hwf Hpw_lt Hdom Ho) as [How_lt _].
    unfold masked_const_gadget in How_lt; cbn [gd_circuit] in How_lt; rewrite circuit_of_fun_count in How_lt.
    destruct o as [ow oc | ow oc]; simpl in *; [apply Hval_eq; exact How_lt | f_equal; apply Hval_eq; exact How_lt].
  - unfold output_view, selected_outputs. apply support_map_ext. intros k Hk.
    apply support_filter_member in Hk. apply member_upto_lt in Hk.
    unfold masked_const_gadget at 1 3; cbn [gd_out gd_shares] in *.
    apply Hval_eq; exact Hk.
Qed.

Definition step_bus_gadget (bg : BusGadget) (g : Gadget)
    (Hshare : gf2_sharing = gd_share g) (srcs : nat -> nat) : BusGadget := {|
  bg_prob := counting (Tape (bg_prob bg) * Tape (gd_prob g))
               (list_prod (tape_enum (bg_prob bg)) (tape_enum (gd_prob g)));
  bg_circuit := combine_circuits (bg_circuit bg) (gd_circuit g);
  bg_ops := @combine_ops gf2_sharing (bg_ops bg)
              (fun o args =>
                 val_cast (eq_sym Hshare)
                   (gd_ops g o (map_over (val_cast Hshare) args)));
  bg_inputs := bg_inputs bg;
  bg_wires := S (bg_wires bg);
  bg_shares := bg_shares bg;
  bg_out := fun u k =>
    if Nat.ltb u (bg_wires bg) then bg_out bg u k
    else wire_count (bg_circuit bg) + gd_out g k;
  bg_wire_read := fun u =>
    if Nat.ltb u (bg_wires bg) then bg_wire_read bg u else gd_read g;
  bg_assign := fun outer_a '(t1, t2) =>
    let a2 : ShareMatrix g := fun j k =>
      val_cast Hshare
        (bg_value bg outer_a t1 (bg_wire_read bg (srcs j)) (bg_out bg (srcs j) k)) in
    @combine_assign gf2_sharing (bg_assign bg outer_a t1)
      (fun cyc2 i2 => val_cast (eq_sym Hshare) (gd_assign g a2 t2 cyc2 i2));
  bg_start := fun outer_a '(t1, t2) =>
    let a2 : ShareMatrix g := fun j k =>
      val_cast Hshare
        (bg_value bg outer_a t1 (bg_wire_read bg (srcs j)) (bg_out bg (srcs j) k)) in
    @combine_start gf2_sharing (wire_count (bg_circuit bg))
      (bg_start bg outer_a t1)
      (fun w2 => val_cast (eq_sym Hshare) (gd_start g a2 t2 w2))
|}.

Lemma step_bus_well_formed :
  forall bg g Hshare srcs,
    gd_shares g = bg_shares bg ->
    bus_gadget_well_formed bg ->
    gadget_well_formed g ->
    bus_gadget_well_formed (step_bus_gadget bg g Hshare srcs).
Proof.
  intros bg g Hshare srcs Hsh [Hwf1 [Hsh1 [Hin1 [Hle1 Hout1]]]] [Hwf2 [_ Hout2]].
  split; [apply combine_circuits_well_formed; assumption|].
  split; [exact Hsh1 | split; [exact Hin1 | split; [simpl; lia|]]].
  intros u k Hu Hk. simpl in *. rewrite combine_circuits_count.
  destruct (Nat.ltb u (bg_wires bg)) eqn:Eu.
  - apply Nat.ltb_lt in Eu. pose proof (Hout1 u k Eu Hk). lia.
  - pose proof (Hout2 k ltac:(lia)). lia.
Qed.

Lemma step_bus_has_counting_mass :
  forall bg g Hshare srcs,
    HasCountingMass (bg_prob (step_bus_gadget bg g Hshare srcs)).
Proof.
  intros. unfold step_bus_gadget; cbn [bg_prob]. apply counting_has_counting_mass.
Qed.

Lemma step_bus_value_l :
  forall bg g Hshare srcs outer_a t1 t2 cyc w,
    bus_gadget_well_formed bg ->
    gadget_well_formed g ->
    w < wire_count (bg_circuit bg) ->
    bg_value (step_bus_gadget bg g Hshare srcs) outer_a (t1, t2) cyc w =
    bg_value bg outer_a t1 cyc w.
Proof.
  intros bg g Hshare srcs outer_a t1 t2 cyc w [Hwf1 _] [Hwf2 _] Hw.
  unfold bg_value, step_bus_gadget; cbn [bg_ops bg_circuit bg_start bg_assign].
  apply (@value_at_combine_l gf2_sharing); [exact Hwf1 | exact Hwf2 | exact Hw].
Qed.

Lemma step_bus_value_r :
  forall bg g srcs outer_a t1 t2 cyc w,
    bus_gadget_well_formed bg ->
    gadget_well_formed g ->
    forall (Hshare : gf2_sharing = gd_share g),
    w < wire_count (gd_circuit g) ->
    let a2 : ShareMatrix g := fun j k =>
      val_cast Hshare
        (bg_value bg outer_a t1 (bg_wire_read bg (srcs j)) (bg_out bg (srcs j) k)) in
    bg_value (step_bus_gadget bg g Hshare srcs) outer_a (t1, t2) cyc
      (wire_count (bg_circuit bg) + w) =
    val_cast (eq_sym Hshare) (gd_value g a2 t2 cyc w).
Proof.
  intros bg g srcs outer_a t1 t2 cyc w [Hwf1 _] [Hwf2 _] Hshare Hw.
  destruct bg as [bg_prob0 bg_circuit0 bg_ops0 bg_inputs0 bg_wires0 bg_shares0 bg_out0 bg_wire_read0 bg_assign0 bg_start0],
           g as [gd_share0 gd_prob0 gd_circuit0 gd_ops0 gd_inputs0 gd_shares0 gd_out0 gd_read0 gd_assign0 gd_start0].
  simpl in *. destruct Hshare.
  unfold bg_value, gd_value. simpl.
  assert (Hops_ext : forall o args,
    @combine_ops gf2_sharing bg_ops0 (fun o0 args0 => gd_ops0 o0 (map_over (fun x => x) args0)) o args =
    @combine_ops gf2_sharing bg_ops0 gd_ops0 o args).
  { intros o args. unfold combine_ops. destruct (Nat.even o); [reflexivity|].
    rewrite map_over_id_val. reflexivity. }
  rewrite (value_at_ops_ext gf2_sharing _ (@combine_ops gf2_sharing bg_ops0 gd_ops0) _ _ _ _ _ Hops_ext).
  apply (@value_at_combine_r gf2_sharing); [exact Hwf1 | exact Hwf2 | exact Hw].
Qed.

Fixpoint lookup_pair_val {V : Type} (pairs : list (nat * nat)) (vals : list V)
    (u k : nat) (dflt : V) : V :=
  match pairs, vals with
  | (u0, k0) :: pr, v :: vr =>
      if andb (Nat.eqb u0 u) (Nat.eqb k0 k) then v
      else lookup_pair_val pr vr u k dflt
  | _, _ => dflt
  end.

Lemma lookup_pair_val_map :
  forall {V : Type} (f : nat * nat -> V) (pairs : list (nat * nat)) (u k : nat) (dflt : V),
    ProofSupport.Member (u, k) pairs ->
    lookup_pair_val pairs (map_over f pairs) u k dflt = f (u, k).
Proof.
  intros V f pairs u k dflt.
  induction pairs as [|[u0 k0] pr IH]; simpl; intros Hm; [contradiction|].
  destruct (andb (Nat.eqb u0 u) (Nat.eqb k0 k)) eqn:Eq.
  - apply andb_prop in Eq. destruct Eq as [Eu Ek].
    apply eqb_sound_nat in Eu; apply eqb_sound_nat in Ek; subst. reflexivity.
  - destruct Hm as [Heq|Hm].
    + inversion Heq; subst. rewrite !eqb_refl_nat in Eq. discriminate Eq.
    + exact (IH Hm).
Qed.

Lemma member_bus_selected_pairs :
  forall bg B u k,
    u < bg_wires bg -> k < bg_shares bg -> B k = true ->
    ProofSupport.Member (u, k) (bus_selected_pairs bg B).
Proof.
  intros bg B u k Hu Hk HBk. unfold bus_selected_pairs.
  assert (Hmem_flat : forall {A B0 : Type} (f : A -> list B0) (l : list A) (a : A) (b0 : B0),
    ProofSupport.Member a l -> ProofSupport.Member b0 (f a) ->
    ProofSupport.Member b0 (flat_map_over f l)).
  { clear. intros A B0 f l a b0 Ha Hb.
    assert (Happ : forall l1 l2 : list B0, ProofSupport.Member b0 l1 \/ ProofSupport.Member b0 l2 ->
      ProofSupport.Member b0 (app l1 l2)).
    { clear. induction l1 as [|x r IH]; intros l2 [H|H]; simpl in *;
        [contradiction | exact H | destruct H as [->|H]; [left; reflexivity | right; apply IH; left; exact H]
        | right; apply IH; right; exact H]. }
    induction l as [|x r IH]; simpl in *; [contradiction|].
    apply Happ. destruct Ha as [->|Ha]; [left; exact Hb | right; exact (IH Ha)]. }
  apply Hmem_flat with (a := u); [apply lt_member_upto; exact Hu|].
  assert (Hmem_map : forall {A B0 : Type} (f : A -> B0) (l : list A) (x : A),
    ProofSupport.Member x l -> ProofSupport.Member (f x) (map_over f l)).
  { clear. intros A B0 f l x. induction l as [|y r IH]; simpl; intros Hx;
      [contradiction | destruct Hx as [->|Hx]; [left; reflexivity | right; exact (IH Hx)]]. }
  apply Hmem_map.
  assert (Hmem_filt : forall {A : Type} (p : A -> bool) (l : list A) (x : A),
    ProofSupport.Member x l -> p x = true -> ProofSupport.Member x (filter_of p l)).
  { clear. intros A p l x. induction l as [|y r IH]; simpl; intros Hx Hpx; [contradiction|].
    destruct (p y) eqn:Epy; [destruct Hx as [->|Hx]; [left; reflexivity | right; exact (IH Hx Hpx)]
      | destruct Hx as [->|Hx]; [rewrite Hpx in Epy; discriminate | exact (IH Hx Hpx)]]. }
  apply Hmem_filt; [apply lt_member_upto; exact Hk | exact HBk].
Qed.

Lemma flat_map_over_app_eq :
  forall {A B : Type} (f : A -> list B) (l1 l2 : list A),
    flat_map_over f (app l1 l2) = app (flat_map_over f l1) (flat_map_over f l2).
Proof.
  intros A B f l1 l2. induction l1 as [|x r IH]; simpl; [reflexivity|].
  rewrite IH, app_assoc. reflexivity.
Qed.

Lemma flat_map_over_ext :
  forall {A B : Type} (f g : A -> list B) (l : list A),
    (forall x, ProofSupport.Member x l -> f x = g x) ->
    flat_map_over f l = flat_map_over g l.
Proof.
  intros A B f g l Hfg. induction l as [|x r IH]; simpl; [reflexivity|].
  rewrite (Hfg x (or_introl eq_refl)), (IH (fun y Hy => Hfg y (or_intror Hy))).
  reflexivity.
Qed.

Lemma step_bus_is_bus_strong_pini :
  forall bg g Hshare srcs E d,
    gd_shares g = bg_shares bg ->
    bus_gadget_well_formed bg ->
    gadget_well_formed g ->
    HasCountingMass (bg_prob bg) ->
    HasCountingMass (gd_prob g) ->
    (forall j, j < gd_inputs g -> srcs j < bg_wires bg) ->
    LocalExpansion E ->
    BusStrongPINI bg E d ->
    StrongPINI g E d ->
    BusStrongPINI (step_bus_gadget bg g Hshare srcs) E d.
Proof.
  intros bg g Hshare srcs E d Hsh Hbwf Hgwf Hcb Hcg Hsrcs Hloc Hbpini Hgpini ps B Hw Hord.
  pose proof Hbwf as [Hwf1 [Hsh1 [Hin1 [Hle1 Hout1]]]].
  pose proof Hgwf as [Hwf2 [Hin2 Hout2]].
  simpl in Hw.
  destruct (split_probes_wires_exist (bg_circuit bg) (gd_circuit g) ps Hw) as [Hw1 Hw2].
  pose proof (split_probes_count (wire_count (bg_circuit bg)) ps) as Hcnt.
  apply Nat.leb_le in Hord.
  set (ps1 := split_probes_l (wire_count (bg_circuit bg)) ps).
  set (ps2 := split_probes_r (wire_count (bg_circuit bg)) ps).
  destruct (Hgpini ps2 B Hw2 ltac:(apply Nat.leb_le; unfold ps2; lia)) as [I2 [Hb2 Hsim2]].
  set (B_mid := fun k => orb (I2 k) (B k)).
  destruct (Hbpini ps1 B_mid Hw1 ltac:(apply Nat.leb_le; unfold ps1; lia)) as [I1 [Hb1 Hsim1]].
  set (I_comp := fun k => orb (I1 k) (I2 k)).
  exists I_comp. split.
  - unfold step_bus_gadget; cbn [bg_shares].
    apply Nat.leb_le in Hb1. apply Nat.leb_le in Hb2. rewrite Hsh in Hb2.
    apply Nat.leb_le. pose proof (count_filter_orb I1 I2 (upto (bg_shares bg))).
    unfold I_comp, ps1, ps2 in *. lia.
  - destruct bg as [bg_prob0 bg_circuit0 bg_ops0 bg_inputs0 bg_wires0 bg_shares0 bg_out0 bg_wire_read0 bg_assign0 bg_start0],
             g as [gd_share0 gd_prob0 gd_circuit0 gd_ops0 gd_inputs0 gd_shares0 gd_out0 gd_read0 gd_assign0 gd_start0].
    simpl in *. destruct Hshare. subst gd_shares0.
    set (bg := {| bg_prob := bg_prob0; bg_circuit := bg_circuit0;
                  bg_ops := bg_ops0; bg_inputs := bg_inputs0; bg_wires := bg_wires0;
                  bg_shares := bg_shares0; bg_out := bg_out0; bg_wire_read := bg_wire_read0;
                  bg_assign := bg_assign0; bg_start := bg_start0 |}).
    set (g := {| gd_share := gf2_sharing; gd_prob := gd_prob0; gd_circuit := gd_circuit0;
                 gd_ops := gd_ops0; gd_inputs := gd_inputs0; gd_shares := bg_shares0;
                 gd_out := gd_out0; gd_read := gd_read0; gd_assign := gd_assign0;
                 gd_start := gd_start0 |}).
    set (n_int1 := count_of (probe_set E bg_circuit0 ps1)).
    set (sel_mid := bus_selected_pairs bg B_mid).
    set (sel_B := bus_selected_pairs bg B).
    set (reconstruct_a2 := fun (v1 : list bool) (j k : nat) =>
      lookup_pair_val sel_mid (ProofSupport.drop_of n_int1 v1) (srcs j) k false).
    set (obs_of := fun (v1 : list bool) (t2 : Tape gd_prob0) =>
      let a2 := reconstruct_a2 v1 in
      app (interleave_obs E bg_circuit0 gd_circuit0 ps
             (ProofSupport.take_of n_int1 v1)
             (internal_view g E ps2 a2 t2))
          (app (map_over (fun uk => lookup_pair_val sel_mid (ProofSupport.drop_of n_int1 v1)
                                      (fst uk) (snd uk) false) sel_B)
               (output_view g B a2 t2))).
    assert (Hops_ext : forall o args,
      @combine_ops gf2_sharing bg_ops0 (fun o0 args0 => gd_ops0 o0 (map_over (fun x => x) args0)) o args =
      @combine_ops gf2_sharing bg_ops0 gd_ops0 o args).
    { intros o args. unfold combine_ops. destruct (Nat.even o); [reflexivity|].
      rewrite map_over_id_val. reflexivity. }
    assert (Htake_v1 : forall (a1 : nat -> nat -> bool) t1,
      ProofSupport.take_of n_int1 (bus_split_view bg E ps1 B_mid a1 t1) =
      bus_internal_view bg E ps1 a1 t1 /\
      ProofSupport.drop_of n_int1 (bus_split_view bg E ps1 B_mid a1 t1) =
      bus_output_view bg B_mid a1 t1).
    { intros a1 t1. unfold bus_split_view. apply take_drop_exact.
      unfold bus_internal_view, n_int1. repeat rewrite count_of_is_length.
      rewrite map_over_is_map, length_map. reflexivity. }
    assert (Hsplit_eq : forall outer_a t1 t2,
      let a2_real : ShareMatrix g := fun j k =>
        bg_value bg outer_a t1 (bg_wire_read0 (srcs j)) (bg_out0 (srcs j) k) in
      bus_split_view (step_bus_gadget bg g eq_refl srcs) E ps B outer_a (t1, t2) =
      app (interleave_obs E bg_circuit0 gd_circuit0 ps
             (bus_internal_view bg E ps1 outer_a t1)
             (internal_view g E ps2 a2_real t2))
          (app (bus_output_view bg B outer_a t1) (output_view g B a2_real t2))).
    { intros outer_a t1 t2 a2_real. unfold bus_split_view. f_equal.
      - unfold bus_internal_view, internal_view. simpl.
        transitivity
          (map_over (obs_value gf2_sharing (@combine_ops gf2_sharing bg_ops0 gd_ops0) (combine_circuits bg_circuit0 gd_circuit0)
                       (@combine_start gf2_sharing (wire_count bg_circuit0) (bg_start0 outer_a t1) (gd_start0 a2_real t2))
                       (@combine_assign gf2_sharing (bg_assign0 outer_a t1) (gd_assign0 a2_real t2)))
                    (probe_set E (combine_circuits bg_circuit0 gd_circuit0) ps)).
        + apply support_map_ext. intros o _.
          destruct o as [ow oc | ow oc]; simpl;
            [apply (value_at_ops_ext gf2_sharing); exact Hops_ext | f_equal; apply (value_at_ops_ext gf2_sharing); exact Hops_ext].
        + exact (interleave_internal_view E Hloc gf2_sharing bg_ops0 gd_ops0 bg_circuit0 gd_circuit0
                   (bg_start0 outer_a t1) (gd_start0 a2_real t2)
                   (bg_assign0 outer_a t1) (gd_assign0 a2_real t2) ps Hwf1 Hwf2 Hw).
      - unfold bus_output_view, bus_selected_pairs.
        change (bg_wires (step_bus_gadget bg g eq_refl srcs)) with (S bg_wires0).
        change (bg_shares (step_bus_gadget bg g eq_refl srcs)) with bg_shares0.
        rewrite upto_succ, flat_map_over_app_eq. cbn [flat_map_over app].
        rewrite map_over_app_eq. rewrite app_nil_r. f_equal.
        + rewrite map_over_flat_map_over.
          transitivity
            (map_over (fun uk => bg_value bg outer_a t1 (bg_wire_read0 (fst uk)) (bg_out0 (fst uk) (snd uk)))
                      (flat_map_over (fun u => map_over (fun k => (u, k)) (filter_of B (upto bg_shares0))) (upto bg_wires0))).
          * rewrite map_over_flat_map_over. apply flat_map_over_ext. intros u Hu.
            apply member_upto_lt in Hu. rewrite !map_over_compose. apply support_map_ext. intros k Hk.
            apply support_filter_member in Hk. apply member_upto_lt in Hk.
            assert (Eu : (u <? bg_wires0) = true) by (apply Nat.ltb_lt; exact Hu).
            change (bg_wire_read (step_bus_gadget bg g eq_refl srcs) (fst (u, k))) with (if fst (u, k) <? bg_wires0 then bg_wire_read0 (fst (u, k)) else gd_read0).
            change (bg_out (step_bus_gadget bg g eq_refl srcs) (fst (u, k)) (snd (u, k))) with (if fst (u, k) <? bg_wires0 then bg_out0 (fst (u, k)) (snd (u, k)) else wire_count bg_circuit0 + gd_out0 (snd (u, k))).
            simpl fst; simpl snd. rewrite Eu.
            apply (step_bus_value_l bg g eq_refl srcs outer_a t1 t2 (bg_wire_read0 u) (bg_out0 u k) Hbwf Hgwf (Hout1 u k Hu Hk)).
          * reflexivity.
        + unfold output_view, selected_outputs. rewrite map_over_compose. apply support_map_ext. intros k Hk.
          assert (Hk_lt : k < bg_shares0).
          { apply support_filter_member in Hk. apply member_upto_lt in Hk. exact Hk. }
          assert (Enw : (bg_wires0 <? bg_wires0) = false) by (apply Nat.ltb_ge; lia).
          change (bg_wire_read (step_bus_gadget bg g eq_refl srcs) (fst (bg_wires0, k))) with (if fst (bg_wires0, k) <? bg_wires0 then bg_wire_read0 (fst (bg_wires0, k)) else gd_read0).
          change (bg_out (step_bus_gadget bg g eq_refl srcs) (fst (bg_wires0, k)) (snd (bg_wires0, k))) with (if fst (bg_wires0, k) <? bg_wires0 then bg_out0 (fst (bg_wires0, k)) (snd (bg_wires0, k)) else wire_count bg_circuit0 + gd_out0 (snd (bg_wires0, k))).
          simpl fst; simpl snd. rewrite Enw.
          exact (step_bus_value_r bg g srcs outer_a t1 t2 gd_read0 (gd_out0 k) Hbwf Hgwf eq_refl (Hout2 k Hk_lt)). }
    assert (Hproj_B : forall (a1 : nat -> nat -> bool) t1,
      map_over (fun uk => lookup_pair_val sel_mid (ProofSupport.drop_of n_int1 (bus_split_view bg E ps1 B_mid a1 t1))
                            (fst uk) (snd uk) false) sel_B =
      bus_output_view bg B a1 t1).
    { intros a1 t1. destruct (Htake_v1 a1 t1) as [_ Hdrop]. rewrite Hdrop.
      unfold bus_output_view. apply support_map_ext. intros [u k] Huk.
      simpl fst; simpl snd.
      unfold sel_B, bus_selected_pairs in Huk.
      apply member_flat_map_over_inv in Huk. destruct Huk as [u0 [Hu0 Huk]].
      apply member_map_over_inv in Huk. destruct Huk as [k0 [Hk0 Heq]].
      inversion Heq; subst u0 k0; clear Heq.
      pose proof (support_filter_true B (upto bg_shares0) k Hk0) as HBk.
      apply member_upto_lt in Hu0. apply support_filter_member in Hk0. apply member_upto_lt in Hk0.
      apply (lookup_pair_val_map (fun uk => bg_value bg a1 t1 (bg_wire_read0 (fst uk)) (bg_out0 (fst uk) (snd uk)))
               sel_mid u k false).
      apply member_bus_selected_pairs; [exact Hu0 | exact Hk0 | unfold B_mid; rewrite HBk, orb_true_r; reflexivity]. }
    assert (Ha2_agree : forall outer_a t1,
      let a2_real : ShareMatrix g := fun j k =>
        bg_value bg outer_a t1 (bg_wire_read0 (srcs j)) (bg_out0 (srcs j) k) in
      agree_on g (union_shares (fun _ k => I2 k) B) a2_real (reconstruct_a2 (bus_split_view bg E ps1 B_mid outer_a t1))).
    { intros outer_a t1 a2_real j k Hj Hk HI.
      simpl in Hj, Hk. apply Nat.ltb_lt in Hj. apply Nat.ltb_lt in Hk.
      unfold a2_real, reconstruct_a2. cbv beta. symmetry.
      transitivity (lookup_pair_val sel_mid (bus_output_view bg B_mid outer_a t1) (srcs j) k false).
      - f_equal. exact (proj2 (Htake_v1 outer_a t1)).
      - unfold bus_output_view.
        transitivity ((fun uk => bg_value bg outer_a t1 (bg_wire_read0 (fst uk)) (bg_out0 (fst uk) (snd uk))) (srcs j, k)); [|reflexivity].
        apply (lookup_pair_val_map
          (fun uk => bg_value bg outer_a t1 (bg_wire_read0 (fst uk)) (bg_out0 (fst uk) (snd uk)))
          sel_mid (srcs j) k false).
        apply member_bus_selected_pairs; [exact (Hsrcs j Hj) | exact Hk | exact HI]. }
    assert (Hpush_g2 : forall (a2_1 a2_2 : ShareMatrix g) (v1_const : list bool),
      agree_on g (union_shares (fun _ k => I2 k) B) a2_1 a2_2 ->
      SameDistribution (counting (Tape gd_prob0) (tape_enum gd_prob0))
        (list bool) (list_eqb bool_eqb)
        (fun t2 => app (interleave_obs E bg_circuit0 gd_circuit0 ps
                          (ProofSupport.take_of n_int1 v1_const)
                          (internal_view g E ps2 a2_1 t2))
                       (app (map_over (fun uk => lookup_pair_val sel_mid (ProofSupport.drop_of n_int1 v1_const)
                                                   (fst uk) (snd uk) false) sel_B)
                            (output_view g B a2_1 t2)))
        (fun t2 => app (interleave_obs E bg_circuit0 gd_circuit0 ps
                          (ProofSupport.take_of n_int1 v1_const)
                          (internal_view g E ps2 a2_2 t2))
                       (app (map_over (fun uk => lookup_pair_val sel_mid (ProofSupport.drop_of n_int1 v1_const)
                                                   (fst uk) (snd uk) false) sel_B)
                            (output_view g B a2_2 t2)))).
    { intros a2_1 a2_2 v1_const Hag.
      pose proof (Hcg _ (list_eqb bool_eqb) _ _ (Hsim2 a2_1 a2_2 Hag)) as Hdist2.
      set (n_int2 := count_of (probe_set E gd_circuit0 ps2)).
      set (lift := fun (sv2 : list bool) =>
        app (interleave_obs E bg_circuit0 gd_circuit0 ps (ProofSupport.take_of n_int1 v1_const)
               (ProofSupport.take_of n_int2 sv2))
            (app (map_over (fun uk => lookup_pair_val sel_mid (ProofSupport.drop_of n_int1 v1_const)
                                        (fst uk) (snd uk) false) sel_B)
                 (ProofSupport.drop_of n_int2 sv2))).
      assert (Hlift_eq : forall a2 t2,
        lift (split_view g E ps2 B a2 t2) =
        app (interleave_obs E bg_circuit0 gd_circuit0 ps (ProofSupport.take_of n_int1 v1_const)
               (internal_view g E ps2 a2 t2))
            (app (map_over (fun uk => lookup_pair_val sel_mid (ProofSupport.drop_of n_int1 v1_const)
                                        (fst uk) (snd uk) false) sel_B)
                 (output_view g B a2 t2))).
      { intros a2 t2. unfold lift, split_view. cbv beta.
        destruct (take_drop_exact n_int2 (internal_view g E ps2 a2 t2) (output_view g B a2 t2)
                    ltac:(unfold internal_view, n_int2; repeat rewrite count_of_is_length;
                          rewrite map_over_is_map, length_map; reflexivity))
          as [Ht Hd].
        f_equal; [f_equal; exact Ht | f_equal; exact Hd]. }
      intros o.
      eapply eq_trans; [|eapply eq_trans; [exact (counting_pushforward (Tape gd_prob0) (tape_enum gd_prob0)
        (list bool) (list bool) (list_eqb bool_eqb) (list_eqb bool_eqb)
        (split_view g E ps2 B a2_1) (split_view g E ps2 B a2_2) lift
        (list_eqb_sound gf2_sharing) (list_eqb_refl_sharing gf2_sharing) Hdist2 o)|]].
      - apply pr_ext. intros t2. rewrite Hlift_eq. reflexivity.
      - apply pr_ext. intros t2. rewrite Hlift_eq. reflexivity. }
    intros outer_a outer_b Hagree.
    assert (Hag_1 : bus_agree_on bg (fun _ k => orb (I1 k) (B_mid k)) outer_a outer_b).
    { intros j k Hj Hk HI. apply Hagree; [exact Hj | exact Hk|].
      unfold I_comp, B_mid in *. rewrite orb_assoc in HI. exact HI. }
    assert (Hchain1 : SameDistribution (bg_prob (step_bus_gadget bg g eq_refl srcs))
      (list bool) (list_eqb bool_eqb)
      (bus_split_view (step_bus_gadget bg g eq_refl srcs) E ps B outer_a)
      (fun '(t1, t2) => obs_of (bus_split_view bg E ps1 B_mid outer_a t1) t2)).
    { simpl bg_prob. apply counting_prod_right. intros t1 _.
      unfold obs_of. cbv beta.
      pose proof (Htake_v1 outer_a t1) as [Ht1 _].
      intros o.
      eapply eq_trans; [|exact (Hpush_g2 _ _ (bus_split_view bg E ps1 B_mid outer_a t1) (Ha2_agree outer_a t1) o)].
      apply pr_ext. intros t2. apply (f_equal (fun z => list_eqb bool_eqb z o)). rewrite Hsplit_eq.
      apply (f_equal2 (@app _));
        [apply (f_equal2 (interleave_obs E bg_circuit0 gd_circuit0 ps)); [symmetry; exact Ht1 | reflexivity]
        | apply (f_equal2 (@app _)); [symmetry; exact (Hproj_B outer_a t1) | reflexivity]]. }
    assert (Hchain2 : SameDistribution (bg_prob (step_bus_gadget bg g eq_refl srcs))
      (list bool) (list_eqb bool_eqb)
      (fun '(t1, t2) => obs_of (bus_split_view bg E ps1 B_mid outer_a t1) t2)
      (fun '(t1, t2) => obs_of (bus_split_view bg E ps1 B_mid outer_b t1) t2)).
    { simpl bg_prob. apply counting_prod_left. intros t2 _.
      pose proof (Hcb _ (list_eqb bool_eqb) _ _ (Hsim1 outer_a outer_b Hag_1)) as Hdist1.
      apply (counting_pushforward (Tape bg_prob0) (tape_enum bg_prob0)
               (list bool) (list bool) (list_eqb bool_eqb) (list_eqb bool_eqb)
               (bus_split_view bg E ps1 B_mid outer_a) (bus_split_view bg E ps1 B_mid outer_b)
               (fun v1 => obs_of v1 t2)
               (list_eqb_sound gf2_sharing) (list_eqb_refl_sharing gf2_sharing) Hdist1). }
    assert (Hchain3 : SameDistribution (bg_prob (step_bus_gadget bg g eq_refl srcs))
      (list bool) (list_eqb bool_eqb)
      (fun '(t1, t2) => obs_of (bus_split_view bg E ps1 B_mid outer_b t1) t2)
      (bus_split_view (step_bus_gadget bg g eq_refl srcs) E ps B outer_b)).
    { simpl bg_prob. apply counting_prod_right. intros t1 _.
      unfold obs_of. cbv beta.
      pose proof (Htake_v1 outer_b t1) as [Ht1 _].
      intros o.
      eapply eq_trans; [exact (Hpush_g2 _ _ (bus_split_view bg E ps1 B_mid outer_b t1)
                                 (fun j k Hj Hk HI => eq_sym (Ha2_agree outer_b t1 j k Hj Hk HI)) o)|].
      apply pr_ext. intros t2. apply (f_equal (fun z => list_eqb bool_eqb z o)). rewrite Hsplit_eq.
      apply (f_equal2 (@app _));
        [apply (f_equal2 (interleave_obs E bg_circuit0 gd_circuit0 ps)); [exact Ht1 | reflexivity]
        | apply (f_equal2 (@app _)); [exact (Hproj_B outer_b t1) | reflexivity]]. }
    intros o.
    eapply eq_trans; [exact (Hchain1 o)|].
    eapply eq_trans; [exact (Hchain2 o) | exact (Hchain3 o)].
Qed.

(* Projecting any BusGadget onto a single output bus u_out or arbitrary output bus list outs. *)
Definition bus_to_gadget (bg : BusGadget) (u_out : nat) : Gadget := {|
  gd_share := gf2_sharing;
  gd_prob := bg_prob bg;
  gd_circuit := bg_circuit bg;
  gd_ops := bg_ops bg;
  gd_inputs := bg_inputs bg;
  gd_shares := bg_shares bg;
  gd_out := bg_out bg u_out;
  gd_read := bg_wire_read bg u_out;
  gd_assign := bg_assign bg;
  gd_start := bg_start bg
|}.

Definition multi_output_view (bg : BusGadget) (outs : list nat) (B : nat -> bool)
    (a : nat -> nat -> bool) (tape : Tape (bg_prob bg)) : list bool :=
  flat_map_over (fun u =>
    map_over (fun k => bg_value bg a tape (bg_wire_read bg u) (bg_out bg u k))
      (filter_of B (upto (bg_shares bg)))) outs.

Definition MultiOutputPINI (bg : BusGadget) (outs : list nat) (E : Expansion) (d : nat) : Prop :=
  forall ps (B : nat -> bool),
    wires_exist (bg_circuit bg) (map_over p_wire ps) = true ->
    Nat.leb (count_of ps) d = true ->
    exists I_dom : nat -> bool,
      Nat.leb (count_of (filter_of I_dom (upto (bg_shares bg)))) (count_of ps) = true /\
      BusSimulableFrom bg (fun _ k => orb (I_dom k) (B k))
        (fun a tape => app (bus_internal_view bg E ps a tape) (multi_output_view bg outs B a tape)).

Definition IsCountingProb (p : Probability) : Prop :=
  forall (O : Type) (oeqb : O -> O -> bool) (f g : Tape p -> O),
    SameDistribution (counting (Tape p) (tape_enum p)) O oeqb f g ->
    SameDistribution p O oeqb f g.

Lemma counting_is_counting_prob :
  forall T enum, IsCountingProb (counting T enum).
Proof. intros T enum O oeqb f g H. exact H. Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem bus_strong_pini_implies_multi_output_pini :
  forall bg outs E d,
    bus_gadget_well_formed bg ->
    HasCountingMass (bg_prob bg) ->
    IsCountingProb (bg_prob bg) ->
    (forall u, ProofSupport.Member u outs -> u < bg_wires bg) ->
    BusStrongPINI bg E d ->
    MultiOutputPINI bg outs E d.
Proof.
  intros bg outs E d _ Hcm Hicm Houts Hbpini ps B Hw Hord.
  destruct (Hbpini ps B Hw Hord) as [I_dom [Hb Hsim]].
  exists I_dom. split; [exact Hb|].
  intros a b Hag.
  pose proof (Hcm _ (list_eqb bool_eqb) _ _ (Hsim a b Hag)) as Hdist.
  set (n_int := count_of (probe_set E (bg_circuit bg) ps)).
  set (sel_B := bus_selected_pairs bg B).
  set (proj := fun (v : list bool) =>
    app (ProofSupport.take_of n_int v)
        (flat_map_over (fun u =>
           map_over (fun k => lookup_pair_val sel_B (ProofSupport.drop_of n_int v) u k false)
             (filter_of B (upto (bg_shares bg)))) outs)).
  assert (Hproj_eq : forall x t,
    proj (bus_split_view bg E ps B x t) =
    app (bus_internal_view bg E ps x t) (multi_output_view bg outs B x t)).
  { intros x t. unfold proj, bus_split_view.
    destruct (take_drop_exact n_int (bus_internal_view bg E ps x t) (bus_output_view bg B x t)
                ltac:(unfold bus_internal_view, n_int; repeat rewrite count_of_is_length;
                      rewrite map_over_is_map, length_map; reflexivity)) as [Ht Hd].
    rewrite Ht, Hd. f_equal. unfold multi_output_view.
    apply flat_map_over_ext. intros u Hu. apply support_map_ext. intros k Hk.
    pose proof (support_filter_true B (upto (bg_shares bg)) k Hk) as HBk.
    apply support_filter_member in Hk. apply member_upto_lt in Hk.
    unfold bus_output_view.
    apply (lookup_pair_val_map (fun uk => bg_value bg x t (bg_wire_read bg (fst uk)) (bg_out bg (fst uk) (snd uk)))
             sel_B u k false).
    apply member_bus_selected_pairs; [exact (Houts u Hu) | exact Hk | exact HBk]. }
  assert (Hpushed : SameDistribution (bg_prob bg) (list bool)
    (list_eqb bool_eqb)
    (fun t => proj (bus_split_view bg E ps B a t))
    (fun t => proj (bus_split_view bg E ps B b t))).
  { apply Hicm.
    exact (counting_pushforward (Tape (bg_prob bg)) (tape_enum (bg_prob bg))
      (list bool) (list bool)
      (list_eqb bool_eqb) (list_eqb bool_eqb)
      (bus_split_view bg E ps B a) (bus_split_view bg E ps B b) proj
      (list_eqb_sound gf2_sharing) (list_eqb_refl_sharing gf2_sharing) Hdist). }
  intros o.
  eapply eq_trans; [|eapply eq_trans; [exact (Hpushed o)|]].
  - apply pr_ext. intros t. rewrite Hproj_eq. reflexivity.
  - apply pr_ext. intros t. rewrite Hproj_eq. reflexivity.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem bus_strong_pini_implies_out_strong_pini :
  forall bg u_out E d,
    bus_gadget_well_formed bg ->
    HasCountingMass (bg_prob bg) ->
    IsCountingProb (bg_prob bg) ->
    u_out < bg_wires bg ->
    BusStrongPINI bg E d ->
    StrongPINI (bus_to_gadget bg u_out) E d.
Proof.
  intros bg u_out E d Hbwf Hcm Hicm Hu Hbpini ps B Hw Hord.
  destruct (bus_strong_pini_implies_multi_output_pini bg (u_out :: nil) E d Hbwf Hcm Hicm
              ltac:(intros u [->|[]]; exact Hu) Hbpini ps B Hw Hord) as [I_dom [Hb Hsim]].
  exists I_dom. split; [exact Hb|].
  intros a b Hag.
  assert (Hbag : bus_agree_on bg (fun _ k => orb (I_dom k) (B k)) a b).
  { intros j k Hj Hk HI. apply Hag; [apply Nat.ltb_lt; exact Hj | apply Nat.ltb_lt; exact Hk | exact HI]. }
  pose proof (Hsim a b Hbag) as Hdist.
  intros o.
  eapply eq_trans; [|eapply eq_trans; [exact (Hdist o)|]].
  - apply pr_ext. intros t. unfold split_view, bus_internal_view, multi_output_view, internal_view, output_view, selected_outputs, bg_value.
    simpl. rewrite app_nil_r. reflexivity.
  - apply pr_ext. intros t. unfold split_view, bus_internal_view, multi_output_view, internal_view, output_view, selected_outputs, bg_value.
    simpl. rewrite app_nil_r. reflexivity.
Qed.

(* Straight-line GF(2) DAG compiler over BoolGate / BoolCircuit. *)
Inductive BoolGate : Type :=
  | bg_const : bool -> BoolGate
  | bg_not : nat -> BoolGate
  | bg_const_xor : bool -> nat -> BoolGate
  | bg_xor : nat -> nat -> BoolGate
  | bg_and : nat -> nat -> BoolGate.

Record BoolCircuit : Type := {
  bc_inputs : nat;
  bc_gates : list BoolGate;
  bc_outputs : list nat
}.

Definition witness_BoolCircuit : BoolCircuit := {|
  bc_inputs := 1;
  bc_gates := bg_not 0 :: nil;
  bc_outputs := 1 :: nil
|}.

Definition bool_gate_wf (limit : nat) (g : BoolGate) : bool :=
  match g with
  | bg_const _ => true
  | bg_not x => Nat.ltb x limit
  | bg_const_xor _ x => Nat.ltb x limit
  | bg_xor x y => andb (Nat.ltb x limit) (Nat.ltb y limit)
  | bg_and x y => andb (Nat.ltb x limit) (Nat.ltb y limit)
  end.

Fixpoint bool_gates_wf (limit : nat) (gs : list BoolGate) : bool :=
  match gs with
  | nil => true
  | g :: r => andb (bool_gate_wf limit g) (bool_gates_wf (S limit) r)
  end.

Definition bool_circuit_wf (bc : BoolCircuit) : bool :=
  andb (Nat.ltb 0 (bc_inputs bc))
       (andb (bool_gates_wf (bc_inputs bc) (bc_gates bc))
             (all_of (fun u => Nat.ltb u (bc_inputs bc + count_of (bc_gates bc))) (bc_outputs bc))).

Definition eval_bool_gate (vals : list bool) (g : BoolGate) : bool :=
  match g with
  | bg_const c => c
  | bg_not x => negb (bit_at vals x)
  | bg_const_xor c x => xorb c (bit_at vals x)
  | bg_xor x y => xorb (bit_at vals x) (bit_at vals y)
  | bg_and x y => andb (bit_at vals x) (bit_at vals y)
  end.

Fixpoint eval_bool_wires_from (acc : list bool) (gs : list BoolGate) : list bool :=
  match gs with
  | nil => acc
  | g :: r => eval_bool_wires_from (app acc (eval_bool_gate acc g :: nil)) r
  end.

Definition eval_bool_wires (bc : BoolCircuit) (ins : list bool) : list bool :=
  eval_bool_wires_from (map_over (bit_at ins) (upto (bc_inputs bc))) (bc_gates bc).

Definition eval_bool_circuit (bc : BoolCircuit) (ins : list bool) : list bool :=
  map_over (bit_at (eval_bool_wires bc ins)) (bc_outputs bc).

Definition compile_bool_gate (n : nat) (bg : BusGadget) (g : BoolGate) : BusGadget :=
  match g with
  | bg_const c => step_bus_gadget bg (masked_const_gadget n c) eq_refl (fun _ => 0)
  | bg_not x => step_bus_gadget bg (masked_not_gadget n) eq_refl (fun _ => x)
  | bg_const_xor c x => step_bus_gadget bg (masked_const_xor_gadget n c) eq_refl (fun _ => x)
  | bg_xor x y => step_bus_gadget bg (masked_xor_gadget n) eq_refl (fun j => match j with 0 => x | _ => y end)
  | bg_and x y => step_bus_gadget bg (hpc1_and_gadget n) eq_refl (fun j => match j with 0 => x | _ => y end)
  end.

Fixpoint compile_bool_gates (n : nat) (bg : BusGadget) (gs : list BoolGate) : BusGadget :=
  match gs with
  | nil => bg
  | g :: r => compile_bool_gates n (compile_bool_gate n bg g) r
  end.

Definition compile_bool_circuit (n : nat) (bc : BoolCircuit) : BusGadget :=
  compile_bool_gates n (id_bus_gadget n (bc_inputs bc)) (bc_gates bc).

Lemma bit_at_app_l :
  forall l1 l2 i,
    i < count_of l1 ->
    bit_at (app l1 l2) i = bit_at l1 i.
Proof.
  intros l1. induction l1 as [|x r IH]; intros l2 [|i] Hi; simpl in *; try lia;
    [reflexivity | apply IH; lia].
Qed.

Lemma bit_at_app_last :
  forall l1 v i,
    bit_at (app l1 (v :: nil)) i =
    if Nat.ltb i (count_of l1) then bit_at l1 i
    else if Nat.eqb i (count_of l1) then v
    else false.
Proof.
  intros l1 v i.
  destruct (Nat.ltb i (count_of l1)) eqn:Elt.
  - apply bit_at_app_l. apply Nat.ltb_lt; exact Elt.
  - apply Nat.ltb_ge in Elt.
    unfold bit_at. rewrite at_member_app_r; [|exact Elt].
    destruct (i - count_of l1) as [|[|k]] eqn:Ediff.
    + assert (Heq : Nat.eqb i (count_of l1) = true) by (apply Nat.eqb_eq; lia). rewrite Heq. reflexivity.
    + assert (Hne : Nat.eqb i (count_of l1) = false) by (apply Nat.eqb_neq; lia). rewrite Hne. reflexivity.
    + assert (Hne : Nat.eqb i (count_of l1) = false) by (apply Nat.eqb_neq; lia). rewrite Hne. reflexivity.
Qed.

Lemma compile_bool_gates_inv :
  forall n d gs bg (a : nat -> nat -> bool) vals_pre,
    bg_shares bg = S n ->
    d <= n ->
    bus_gadget_well_formed bg ->
    HasCountingMass (bg_prob bg) ->
    bool_gates_wf (bg_wires bg) gs = true ->
    count_of vals_pre = bg_wires bg ->
    (forall t u, u < bg_wires bg ->
       xor_sum_upto (fun k => bg_value bg a t (bg_wire_read bg u) (bg_out bg u k)) (S n) =
       bit_at vals_pre u) ->
    BusStrongPINI bg ex_robust d ->
    let bg' := compile_bool_gates n bg gs in
    bg_shares bg' = S n /\
    bg_wires bg' = bg_wires bg + count_of gs /\
    bus_gadget_well_formed bg' /\
    HasCountingMass (bg_prob bg') /\
    BusStrongPINI bg' ex_robust d /\
    (forall t u, u < bg_wires bg + count_of gs ->
       xor_sum_upto (fun k => bg_value bg' a t (bg_wire_read bg' u) (bg_out bg' u k)) (S n) =
       bit_at (eval_bool_wires_from vals_pre gs) u).
Proof.
  intros n d gs. induction gs as [|g r IH]; intros bg a vals_pre Hshn Hd Hwf Hcm Hgwf Hlen Hvals Hbpini.
  - simpl. split; [exact Hshn | split; [lia | split; [exact Hwf | split; [exact Hcm | split; [exact Hbpini|]]]]].
    intros t u Hu. apply Hvals. lia.
  - destruct bg as [p_b c_b ops_b in_b w_b sh_b out_b wr_b asg_b st_b].
    simpl in Hshn, Hlen. subst sh_b.
    set (bg0 := {| bg_prob := p_b; bg_circuit := c_b;
                   bg_ops := ops_b; bg_inputs := in_b; bg_wires := w_b;
                   bg_shares := S n; bg_out := out_b; bg_wire_read := wr_b;
                   bg_assign := asg_b; bg_start := st_b |}).
    simpl in Hgwf. apply andb_prop in Hgwf. destruct Hgwf as [Hg Hr].
    set (bg1 := compile_bool_gate n bg0 g).
    set (vals1 := app vals_pre (eval_bool_gate vals_pre g :: nil)).
    assert (Hlen1 : count_of vals1 = bg_wires bg1).
    { unfold vals1, bg1. rewrite count_of_app_eq. simpl count_of at 2.
      destruct g; simpl; rewrite Hlen; lia. }
    assert (Hstep_ok :
      bg_shares bg1 = S n /\
      bg_wires bg1 = S w_b /\
      bus_gadget_well_formed bg1 /\
      HasCountingMass (bg_prob bg1) /\
      BusStrongPINI bg1 ex_robust d /\
      (forall t u, u < S w_b ->
         xor_sum_upto (fun k => bg_value bg1 a t (bg_wire_read bg1 u) (bg_out bg1 u k)) (S n) =
         bit_at vals1 u)).
    { assert (Hstep_gen : forall (gg : Gadget) (srcs : nat -> nat),
        forall (Hggsh : gf2_sharing = gd_share gg),
        gd_shares gg = S n ->
        gadget_well_formed gg ->
        HasCountingMass (gd_prob gg) ->
        (forall j, j < gd_inputs gg -> srcs j < w_b) ->
        StrongPINI gg ex_robust d ->
        (forall t1 (t2 : Tape (gd_prob gg)),
           let a2 : ShareMatrix gg := fun j k0 =>
             val_cast Hggsh (bg_value bg0 a t1 (wr_b (srcs j)) (out_b (srcs j) k0)) in
           xor_sum_upto (fun k => val_cast (eq_sym Hggsh) (gd_value gg a2 t2 (gd_read gg) (gd_out gg k))) (S n) =
           eval_bool_gate vals_pre g) ->
        let bgs := step_bus_gadget bg0 gg Hggsh srcs in
        bg1 = bgs ->
        bg_shares bg1 = S n /\
        bg_wires bg1 = S w_b /\
        bus_gadget_well_formed bg1 /\
        HasCountingMass (bg_prob bg1) /\
        BusStrongPINI bg1 ex_robust d /\
        (forall t u, u < S w_b ->
           xor_sum_upto (fun k => bg_value bg1 a t (bg_wire_read bg1 u) (bg_out bg1 u k)) (S n) =
           bit_at vals1 u)).
      { intros gg srcs Hggsh Hggsn Hggwf Hggcm Hsrcs Hggpini Hggcorr bgs Heq1.
        rewrite Heq1.
        split; [reflexivity | split; [reflexivity|]].
        split; [apply (step_bus_well_formed bg0 gg Hggsh srcs Hggsn Hwf Hggwf)|].
        split; [apply step_bus_has_counting_mass|].
        split; [exact (step_bus_is_bus_strong_pini bg0 gg Hggsh srcs ex_robust d
                         Hggsn Hwf Hggwf Hcm Hggcm Hsrcs ex_robust_is_local Hbpini Hggpini)|].
        intros [t1 t2] u Hu.
        unfold vals1. rewrite bit_at_app_last, Hlen.
        destruct (Nat.ltb u w_b) eqn:Eu.
        - assert (Eu_lt : u < w_b) by (apply Nat.ltb_lt; exact Eu).
          simpl. rewrite Eu.
          transitivity (xor_sum_upto (fun k => bg_value bg0 a t1 (wr_b u) (out_b u k)) (S n)).
          + apply xor_sum_upto_ext. intros k Hk.
            pose proof Hwf as [_ [_ [_ [_ Hout0]]]].
            exact (step_bus_value_l bg0 gg Hggsh srcs a t1 t2 (wr_b u) (out_b u k) Hwf Hggwf (Hout0 u k Eu_lt Hk)).
          + apply Hvals; exact Eu_lt.
        - apply Nat.ltb_ge in Eu. assert (Hu_eq : u = w_b) by lia; subst u.
          rewrite eqb_refl_nat. simpl.
          assert (Ew : (w_b <? w_b) = false) by (apply Nat.ltb_ge; lia). rewrite Ew.
          transitivity (xor_sum_upto (fun k =>
            val_cast (eq_sym Hggsh)
              (gd_value gg (fun j k0 => val_cast Hggsh (bg_value bg0 a t1 (wr_b (srcs j)) (out_b (srcs j) k0))) t2 (gd_read gg) (gd_out gg k))) (S n)).
          + apply xor_sum_upto_ext. intros k Hk.
            pose proof Hggwf as [_ [_ Houtg]].
            exact (step_bus_value_r bg0 gg srcs a t1 t2 (gd_read gg) (gd_out gg k) Hwf Hggwf Hggsh (Houtg k ltac:(rewrite Hggsn; exact Hk))).
          + apply (Hggcorr t1 t2). }
      destruct g as [c | x | c x | x y | x y]; simpl in Hg.
      - apply (Hstep_gen (masked_const_gadget n c) (fun _ => 0) eq_refl eq_refl
                 (masked_const_well_formed n c) (counting_has_counting_mass _ _)
                 ltac:(intros j _; destruct Hwf as [_ [_ [Hin0 [Hle0 _]]]]; simpl in *; lia)
                 (masked_const_is_strong_pini n c ex_robust d ex_robust_is_local)); [|reflexivity].
        intros t1 t2. cbv zeta. simpl val_cast. apply masked_const_correct.
      - apply Nat.ltb_lt in Hg.
        apply (Hstep_gen (masked_not_gadget n) (fun _ => x) eq_refl eq_refl
                 (masked_not_well_formed n) (counting_has_counting_mass _ _)
                 ltac:(intros j _; exact Hg)
                 (masked_not_is_strong_pini n ex_robust d ex_robust_is_local)); [|reflexivity].
        intros t1 t2. cbv zeta. simpl val_cast. cbn [gd_read]. rewrite masked_not_correct.
        simpl eval_bool_gate. f_equal. exact (Hvals t1 x Hg).
      - apply Nat.ltb_lt in Hg.
        apply (Hstep_gen (masked_const_xor_gadget n c) (fun _ => x) eq_refl eq_refl
                 (masked_const_xor_well_formed n c) (counting_has_counting_mass _ _)
                 ltac:(intros j _; exact Hg)
                 (masked_const_xor_is_strong_pini n c ex_robust d ex_robust_is_local)); [|reflexivity].
        intros t1 t2. cbv zeta. simpl val_cast. cbn [gd_read]. rewrite masked_const_xor_correct.
        simpl eval_bool_gate. f_equal. exact (Hvals t1 x Hg).
      - apply andb_prop in Hg. destruct Hg as [Hx Hy]. apply Nat.ltb_lt in Hx; apply Nat.ltb_lt in Hy.
        apply (Hstep_gen (masked_xor_gadget n) (fun j => match j with 0 => x | _ => y end) eq_refl eq_refl
                 (masked_xor_well_formed n) (counting_has_counting_mass _ _)
                 ltac:(intros [|j] _; [exact Hx | exact Hy])
                 (masked_xor_is_strong_pini n ex_robust d ex_robust_is_local)); [|reflexivity].
        intros t1 t2. cbv zeta. simpl val_cast. cbn [gd_read]. rewrite masked_xor_correct.
        simpl eval_bool_gate. f_equal; [exact (Hvals t1 x Hx) | exact (Hvals t1 y Hy)].
      - apply andb_prop in Hg. destruct Hg as [Hx Hy]. apply Nat.ltb_lt in Hx; apply Nat.ltb_lt in Hy.
        apply (Hstep_gen (hpc1_and_gadget n) (fun j => match j with 0 => x | _ => y end) eq_refl eq_refl
                 (hpc1_and_well_formed n) (counting_has_counting_mass _ _)
                 ltac:(intros [|j] _; [exact Hx | exact Hy])
                 (hpc1_and_is_strong_pini n d Hd)); [|reflexivity].
        intros t1 t2. cbv zeta. simpl val_cast. cbn [gd_read]. rewrite hpc1_and_correct.
        simpl eval_bool_gate. f_equal; [exact (Hvals t1 x Hx) | exact (Hvals t1 y Hy)]. }
    destruct Hstep_ok as [H2 [H3 [H4 [H5 [H6 H7]]]]].
    rewrite <- H3 in Hr.
    assert (Hvals1 : forall t u, u < bg_wires bg1 ->
      xor_sum_upto (fun k => bg_value bg1 a t (bg_wire_read bg1 u) (bg_out bg1 u k)) (S n) = bit_at vals1 u).
    { rewrite H3. exact H7. }
    destruct (IH bg1 a vals1 H2 Hd H4 H5 Hr Hlen1 Hvals1 H6)
      as [I2 [I3 [I4 [I5 [I6 I7]]]]].
    simpl eval_bool_wires_from.
    split; [exact I2 | split; [transitivity (bg_wires bg1 + count_of r); [exact I3 | rewrite H3, !count_of_is_length; simpl; lia] | split; [exact I4 | split; [exact I5 | split; [exact I6|]]]]].
    rewrite H3 in I7. intros t u Hu; apply I7; rewrite !count_of_is_length in *; simpl in *; lia.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem compile_bool_circuit_correct :
  forall n (bc : BoolCircuit) (a : nat -> nat -> bool) tape,
    bool_circuit_wf bc = true ->
    let bg := compile_bool_circuit n bc in
    let ins := map_over (fun i => xor_sum_upto (a i) (S n)) (upto (bc_inputs bc)) in
    map_over (fun u => xor_sum_upto (fun k => bg_value bg a tape (bg_wire_read bg u) (bg_out bg u k)) (S n))
      (bc_outputs bc) =
    eval_bool_circuit bc ins.
Proof.
  intros n bc a tape Hwf.
  unfold bool_circuit_wf in Hwf.
  apply andb_prop in Hwf. destruct Hwf as [Hin Hwf2].
  apply andb_prop in Hwf2. destruct Hwf2 as [Hgwf Houts].
  apply Nat.ltb_lt in Hin.
  set (ins := map_over (fun i => xor_sum_upto (a i) (S n)) (upto (bc_inputs bc))).
  assert (Hlen0 : count_of ins = bg_wires (id_bus_gadget n (bc_inputs bc))).
  { unfold ins, id_bus_gadget; cbn [bg_wires]. rewrite count_of_is_length, map_over_is_map, length_map, <- count_of_is_length.
    apply count_upto. }
  assert (Hvals0 : forall (t : Tape (bg_prob (id_bus_gadget n (bc_inputs bc)))) u,
    u < bg_wires (id_bus_gadget n (bc_inputs bc)) ->
    xor_sum_upto (fun k => bg_value (id_bus_gadget n (bc_inputs bc)) a t
      (bg_wire_read (id_bus_gadget n (bc_inputs bc)) u)
      (bg_out (id_bus_gadget n (bc_inputs bc)) u k)) (S n) =
    bit_at ins u).
  { intros t u Hu. unfold id_bus_gadget in Hu; cbn [bg_wires] in Hu.
    transitivity (xor_sum_upto (a u) (S n)).
    - apply xor_sum_upto_ext. intros k Hk.
      change (bg_out (id_bus_gadget n (bc_inputs bc)) u k) with (u * S n + k).
      rewrite id_bus_value; [|nia].
      destruct (div_mod_pair_id_gen (S n) u k Hk) as [Hd Hm]. rewrite Hd, Hm. reflexivity.
    - unfold ins, bit_at.
      assert (Hu_lt : u < count_of (upto (bc_inputs bc))) by (rewrite count_upto; exact Hu).
      rewrite (at_member_map_over (fun i => xor_sum_upto (a i) (S n)) (upto (bc_inputs bc)) u 0 false Hu_lt).
      f_equal. clear -Hu. revert u Hu. generalize (bc_inputs bc) as m.
      induction m as [|m IH]; intros u Hu; [lia|].
      rewrite upto_succ. destruct (Nat.ltb u m) eqn:Eu.
      + apply Nat.ltb_lt in Eu. rewrite at_member_app_l; [apply IH; exact Eu | rewrite count_upto; apply Nat.ltb_lt; exact Eu].
      + apply Nat.ltb_ge in Eu. assert (u = m) by lia; subst u.
        rewrite at_member_app_r; rewrite count_upto; [|lia]. replace (m - m) with 0 by lia. reflexivity. }
  destruct (compile_bool_gates_inv n 0 (bc_gates bc) (id_bus_gadget n (bc_inputs bc)) a ins
              eq_refl (Nat.le_0_l n)
              (id_bus_well_formed n (bc_inputs bc) Hin)
              (id_bus_has_counting_mass n (bc_inputs bc))
              Hgwf Hlen0 Hvals0
              (id_bus_is_bus_strong_pini n (bc_inputs bc) ex_robust 0 Hin ex_robust_is_local))
    as [_ [_ [_ [_ [_ Hres]]]]].
  unfold compile_bool_circuit, eval_bool_circuit, eval_bool_wires.
  transitivity (map_over (bit_at (eval_bool_wires_from ins (bc_gates bc))) (bc_outputs bc)).
  - apply support_map_ext. intros u Hu.
    assert (Hu_lt : u < bc_inputs bc + count_of (bc_gates bc)).
    { clear -Houts Hu. induction (bc_outputs bc) as [|x r IH]; simpl in *; [contradiction|].
      apply andb_prop in Houts. destruct Houts as [Hx Hr].
      destruct Hu as [<-|Hu]; [apply Nat.ltb_lt; exact Hx | exact (IH Hr Hu)]. }
    exact (Hres tape u Hu_lt).
  - apply support_map_ext. intros u _. f_equal. unfold eval_bool_wires, ins. f_equal.
    apply support_map_ext. intros i Hi. apply member_upto_lt in Hi.
    unfold bit_at.
    assert (Hi_lt : i < count_of (upto (bc_inputs bc))) by (rewrite count_upto; exact Hi).
    rewrite (at_member_map_over (fun i0 => xor_sum_upto (a i0) (S n)) (upto (bc_inputs bc)) i 0 false Hi_lt).
    f_equal. clear -Hi. revert i Hi. generalize (bc_inputs bc) as m.
    induction m as [|m IH]; intros i Hi; [lia|].
    rewrite upto_succ. destruct (Nat.ltb i m) eqn:Ei.
    + apply Nat.ltb_lt in Ei. rewrite at_member_app_l; [apply IH; exact Ei | rewrite count_upto; apply Nat.ltb_lt; exact Ei].
    + apply Nat.ltb_ge in Ei. assert (i = m) by lia; subst i.
      rewrite at_member_app_r; rewrite count_upto; [|lia]. replace (m - m) with 0 by lia. reflexivity.
Qed.

Lemma compile_bool_circuit_inv_props :
  forall n d (bc : BoolCircuit),
    d <= n ->
    bool_circuit_wf bc = true ->
    bg_wires (compile_bool_circuit n bc) = bc_inputs bc + count_of (bc_gates bc) /\
    bus_gadget_well_formed (compile_bool_circuit n bc) /\
    HasCountingMass (bg_prob (compile_bool_circuit n bc)) /\
    BusStrongPINI (compile_bool_circuit n bc) ex_robust d.
Proof.
  intros n d bc Hd Hwf.
  unfold bool_circuit_wf in Hwf.
  apply andb_prop in Hwf. destruct Hwf as [Hin Hwf2].
  apply andb_prop in Hwf2. destruct Hwf2 as [Hgwf _].
  apply Nat.ltb_lt in Hin.
  set (a0 := fun (_ _ : nat) => false).
  set (vals0 := map_over (fun _ : nat => false) (upto (bc_inputs bc))).
  assert (Hlen0 : count_of vals0 = bg_wires (id_bus_gadget n (bc_inputs bc)))
    by (unfold vals0, id_bus_gadget; cbn [bg_wires]; rewrite count_of_is_length, map_over_is_map, length_map, <- count_of_is_length; apply count_upto).
  assert (Hvals0 : forall (t : Tape (bg_prob (id_bus_gadget n (bc_inputs bc)))) u,
    u < bg_wires (id_bus_gadget n (bc_inputs bc)) ->
    xor_sum_upto (fun k => bg_value (id_bus_gadget n (bc_inputs bc)) a0 t
      (bg_wire_read (id_bus_gadget n (bc_inputs bc)) u)
      (bg_out (id_bus_gadget n (bc_inputs bc)) u k)) (S n) =
    bit_at vals0 u).
  { intros t u Hu. unfold id_bus_gadget in Hu; cbn [bg_wires] in Hu.
    transitivity false.
    - transitivity (xor_sum_upto (fun _ => false) (S n)).
      + apply xor_sum_upto_ext. intros k Hk.
        change (bg_out (id_bus_gadget n (bc_inputs bc)) u k) with (u * S n + k).
        rewrite id_bus_value; [|nia]. reflexivity.
      + clear.
        assert (Happ : forall l1 l2, xor_fold (app l1 l2) = xorb (xor_fold l1) (xor_fold l2))
          by (clear; intros l1 l2; induction l1 as [|x r IHr]; simpl; [reflexivity | rewrite IHr, xorb_assoc; reflexivity]).
        induction (S n) as [|m IH]; [reflexivity|].
        unfold xor_sum_upto. rewrite upto_succ, map_over_app_eq, Happ.
        change (xor_fold (map_over (fun _ : nat => false) (upto m))) with (xor_sum_upto (fun _ : nat => false) m).
        rewrite IH. reflexivity.
    - unfold vals0, bit_at. clear -Hu. revert u Hu. generalize (bc_inputs bc) as m.
      induction m as [|m IH]; intros u Hu; [lia|].
      rewrite upto_succ, map_over_app_eq.
      assert (Hcnt : count_of (map_over (fun _ : nat => false) (upto m)) = m)
        by (rewrite count_of_is_length, map_over_is_map, length_map, <- count_of_is_length, count_upto; reflexivity).
      destruct (Nat.ltb u m) eqn:Eu.
      + apply Nat.ltb_lt in Eu. rewrite at_member_app_l; [apply IH; exact Eu | rewrite Hcnt; apply Nat.ltb_lt; exact Eu].
      + apply Nat.ltb_ge in Eu. assert (u = m) by lia; subst u.
        rewrite at_member_app_r; rewrite Hcnt; [|lia].
        replace (m - m) with 0 by lia. reflexivity. }
  destruct (compile_bool_gates_inv n d (bc_gates bc) (id_bus_gadget n (bc_inputs bc)) a0 vals0
              eq_refl Hd
              (id_bus_well_formed n (bc_inputs bc) Hin)
              (id_bus_has_counting_mass n (bc_inputs bc))
              Hgwf Hlen0 Hvals0
              (id_bus_is_bus_strong_pini n (bc_inputs bc) ex_robust d Hin ex_robust_is_local))
    as [_ [Hwires [Hbwf [Hcm [Hbpini _]]]]].
  unfold compile_bool_circuit. split; [exact Hwires | split; [exact Hbwf | split; [exact Hcm | exact Hbpini]]].
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem compile_bool_circuit_is_bus_strong_pini :
  forall n d (bc : BoolCircuit),
    d <= n ->
    bool_circuit_wf bc = true ->
    BusStrongPINI (compile_bool_circuit n bc) ex_robust d.
Proof.
  intros n d bc Hd Hwf.
  destruct (compile_bool_circuit_inv_props n d bc Hd Hwf) as [_ [_ [_ Hbpini]]].
  exact Hbpini.
Qed.

Lemma compile_bool_gates_is_counting_prob :
  forall n gs bg,
    IsCountingProb (bg_prob bg) ->
    IsCountingProb (bg_prob (compile_bool_gates n bg gs)).
Proof.
  intros n gs. induction gs as [|g r IH]; intros bg Hic; [exact Hic|].
  simpl. apply IH. destruct g; apply counting_is_counting_prob.
Qed.

Lemma compile_bool_circuit_is_counting_prob :
  forall n bc, IsCountingProb (bg_prob (compile_bool_circuit n bc)).
Proof.
  intros n bc. unfold compile_bool_circuit.
  apply compile_bool_gates_is_counting_prob.
  unfold id_bus_gadget; cbn [bg_prob]. apply counting_is_counting_prob.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem compile_bool_circuit_multi_output_pini :
  forall n d (bc : BoolCircuit),
    d <= n ->
    bool_circuit_wf bc = true ->
    MultiOutputPINI (compile_bool_circuit n bc) (bc_outputs bc) ex_robust d.
Proof.
  intros n d bc Hd Hwf.
  destruct (compile_bool_circuit_inv_props n d bc Hd Hwf) as [Hwires [Hbwf [Hcm Hbpini]]].
  unfold bool_circuit_wf in Hwf.
  apply andb_prop in Hwf. destruct Hwf as [_ Hwf2].
  apply andb_prop in Hwf2. destruct Hwf2 as [_ Houts].
  apply (bus_strong_pini_implies_multi_output_pini _ _ ex_robust d Hbwf Hcm
           (compile_bool_circuit_is_counting_prob n bc)); [|exact Hbpini].
  intros u Hu. rewrite Hwires.
  clear -Houts Hu. induction (bc_outputs bc) as [|x r IH]; simpl in *; [contradiction|].
  apply andb_prop in Houts. destruct Houts as [Hx Hr].
  destruct Hu as [<-|Hu]; [apply Nat.ltb_lt; exact Hx | exact (IH Hr Hu)].
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem compile_bool_circuit_out_is_pini :
  forall n d (bc : BoolCircuit) u_out,
    d <= n ->
    bool_circuit_wf bc = true ->
    ProofSupport.Member u_out (bc_outputs bc) ->
    PINI (bus_to_gadget (compile_bool_circuit n bc) u_out) ex_robust d.
Proof.
  intros n d bc u_out Hd Hwf Hu_mem.
  apply strong_pini_implies_pini.
  destruct (compile_bool_circuit_inv_props n d bc Hd Hwf) as [Hwires [Hbwf [Hcm Hbpini]]].
  unfold bool_circuit_wf in Hwf.
  apply andb_prop in Hwf. destruct Hwf as [_ Hwf2].
  apply andb_prop in Hwf2. destruct Hwf2 as [_ Houts].
  apply (bus_strong_pini_implies_out_strong_pini _ u_out ex_robust d Hbwf Hcm
           (compile_bool_circuit_is_counting_prob n bc)); [|exact Hbpini].
  rewrite Hwires.
  clear -Houts Hu_mem. induction (bc_outputs bc) as [|x r IH]; simpl in *; [contradiction|].
  apply andb_prop in Houts. destruct Houts as [Hx Hr].
  destruct Hu_mem as [<-|Hu]; [apply Nat.ltb_lt; exact Hx | exact (IH Hr Hu)].
Qed.


(* =========================================================================
   5. Concrete cryptographic instantiations via BoolCircuit compilation:
      (a) Keccak chi (5-bit nonlinear step, Keccak.chi_row),
      (b) FIPS 197 AES S-box via GF(((2^2)^2)^2) tower-field arithmetic,
          verified against AesGcm.sub_byte and the 256-entry FIPS 197 table.
   ========================================================================= *)

(* --- 5a. Keccak chi ------------------------------------------------------ *)

Definition keccak_chi_row_dag : BoolCircuit := {|
  bc_inputs := 5;
  bc_gates :=
    bg_not 1 :: bg_and 5 2 :: bg_xor 0 6 ::
    bg_not 2 :: bg_and 8 3 :: bg_xor 1 9 ::
    bg_not 3 :: bg_and 11 4 :: bg_xor 2 12 ::
    bg_not 4 :: bg_and 14 0 :: bg_xor 3 15 ::
    bg_not 0 :: bg_and 17 1 :: bg_xor 4 18 :: nil;
  bc_outputs := 7 :: 10 :: 13 :: 16 :: 19 :: nil
|}.

Lemma keccak_chi_row_dag_wf : bool_circuit_wf keccak_chi_row_dag = true.
Proof. vm_compute. reflexivity. Qed.

Lemma keccak_chi_row_dag_eq :
  forall b0 b1 b2 b3 b4 : bool,
    eval_bool_circuit keccak_chi_row_dag (b0 :: b1 :: b2 :: b3 :: b4 :: nil) =
    Keccak.chi_row (b0 :: b1 :: b2 :: b3 :: b4 :: nil).
Proof. intros [] [] [] [] []; vm_compute; reflexivity. Qed.

Definition masked_keccak_chi (n : nat) : BusGadget :=
  compile_bool_circuit n keccak_chi_row_dag.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_keccak_chi_correct :
  forall n (a : nat -> nat -> bool) tape,
    let bg := masked_keccak_chi n in
    let ins := map_over (fun i => xor_sum_upto (a i) (S n)) (upto 5) in
    map_over (fun u => xor_sum_upto (fun k => bg_value bg a tape (bg_wire_read bg u) (bg_out bg u k)) (S n))
      (bc_outputs keccak_chi_row_dag) =
    Keccak.chi_row ins.
Proof.
  intros n a tape. unfold masked_keccak_chi.
  rewrite (compile_bool_circuit_correct n keccak_chi_row_dag a tape keccak_chi_row_dag_wf).
  simpl (bc_inputs keccak_chi_row_dag).
  set (x0 := xor_sum_upto (a 0) (S n)).
  set (x1 := xor_sum_upto (a 1) (S n)).
  set (x2 := xor_sum_upto (a 2) (S n)).
  set (x3 := xor_sum_upto (a 3) (S n)).
  set (x4 := xor_sum_upto (a 4) (S n)).
  change (map_over (fun i => xor_sum_upto (a i) (S n)) (upto 5))
    with (x0 :: x1 :: x2 :: x3 :: x4 :: nil).
  apply keccak_chi_row_dag_eq.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_keccak_chi_multi_output_pini :
  forall n d,
    d <= n ->
    MultiOutputPINI (masked_keccak_chi n) (bc_outputs keccak_chi_row_dag) ex_robust d.
Proof.
  intros n d Hd. unfold masked_keccak_chi.
  apply compile_bool_circuit_multi_output_pini; [exact Hd | exact keccak_chi_row_dag_wf].
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_keccak_chi_out_is_pini :
  forall n d u_out,
    d <= n ->
    ProofSupport.Member u_out (bc_outputs keccak_chi_row_dag) ->
    PINI (bus_to_gadget (masked_keccak_chi n) u_out) ex_robust d.
Proof.
  intros n d u_out Hd Hu. unfold masked_keccak_chi.
  apply compile_bool_circuit_out_is_pini; [exact Hd | exact keccak_chi_row_dag_wf | exact Hu].
Qed.

(* --- 5b. FIPS 197 AES S-box via GF(((2^2)^2)^2) tower-field DAG -------- *)

Definition dag_state : Type := (nat * list BoolGate)%type.

Definition dag_emit (st : dag_state) (g : BoolGate) : nat * dag_state :=
  let '(w, gs) := st in (w, (S w, g :: gs)).

Definition dag_xor (st : dag_state) (x y : nat) : nat * dag_state :=
  dag_emit st (bg_xor x y).

Definition dag_and (st : dag_state) (x y : nat) : nat * dag_state :=
  dag_emit st (bg_and x y).

Definition dag_const_xor (st : dag_state) (c : bool) (x : nat) : nat * dag_state :=
  dag_emit st (bg_const_xor c x).

Fixpoint dag_xor_fold_from (st : dag_state) (acc : nat) (ws : list nat) : nat * dag_state :=
  match ws with
  | nil => (acc, st)
  | w :: r =>
      let '(acc', st') := dag_xor st acc w in
      dag_xor_fold_from st' acc' r
  end.

Definition dag_xor_list (st : dag_state) (ws : list nat) : nat * dag_state :=
  match ws with
  | nil => dag_emit st (bg_const false)
  | w :: r => dag_xor_fold_from st w r
  end.

Fixpoint dag_vec_xor (st : dag_state) (xs ys : list nat) : list nat * dag_state :=
  match xs, ys with
  | x :: xr, y :: yr =>
      let '(z, st1) := dag_xor st x y in
      let '(zr, st2) := dag_vec_xor st1 xr yr in
      (z :: zr, st2)
  | _, _ => (nil, st)
  end.

Definition dag_gf22_mul (st : dag_state) (a b : list nat) : list nat * dag_state :=
  match a, b with
  | a0 :: a1 :: nil, b0 :: b1 :: nil =>
      let '(t0, st1) := dag_and st a0 b0 in
      let '(t1, st2) := dag_and st1 a1 b1 in
      let '(sa, st3) := dag_xor st2 a0 a1 in
      let '(sb, st4) := dag_xor st3 b0 b1 in
      let '(t2, st5) := dag_and st4 sa sb in
      let '(c0, st6) := dag_xor st5 t0 t1 in
      let '(c1, st7) := dag_xor st6 t0 t2 in
      (c0 :: c1 :: nil, st7)
  | _, _ => (nil, st)
  end.

Definition dag_gf22_mul_w (st : dag_state) (a : list nat) : list nat * dag_state :=
  match a with
  | a0 :: a1 :: nil =>
      let '(s, st1) := dag_xor st a0 a1 in
      (a1 :: s :: nil, st1)
  | _ => (nil, st)
  end.

Definition dag_gf22_sq (st : dag_state) (a : list nat) : list nat * dag_state :=
  match a with
  | a0 :: a1 :: nil =>
      let '(s, st1) := dag_xor st a0 a1 in
      (s :: a1 :: nil, st1)
  | _ => (nil, st)
  end.

Definition dag_gf24_mul (st : dag_state) (a b : list nat) : list nat * dag_state :=
  let aL := ProofSupport.take_of 2 a in
  let aH := ProofSupport.drop_of 2 a in
  let bL := ProofSupport.take_of 2 b in
  let bH := ProofSupport.drop_of 2 b in
  let '(pLL, st1) := dag_gf22_mul st aL bL in
  let '(pHH, st2) := dag_gf22_mul st1 aH bH in
  let '(aS, st3) := dag_vec_xor st2 aL aH in
  let '(bS, st4) := dag_vec_xor st3 bL bH in
  let '(pSS, st5) := dag_gf22_mul st4 aS bS in
  let '(pHHw, st6) := dag_gf22_mul_w st5 pHH in
  let '(cL, st7) := dag_vec_xor st6 pLL pHHw in
  let '(cH, st8) := dag_vec_xor st7 pSS pLL in
  (app cL cH, st8).

Definition dag_gf24_sq_z (st : dag_state) (a : list nat) : list nat * dag_state :=
  let aL := ProofSupport.take_of 2 a in
  let aH := ProofSupport.drop_of 2 a in
  let '(sL, st1) := dag_gf22_sq st aL in
  let '(sH, st2) := dag_gf22_sq st1 aH in
  let '(sHw, st3) := dag_gf22_mul_w st2 sH in
  let '(sLw, st4) := dag_vec_xor st3 sL sHw in
  let '(cH, st5) := dag_vec_xor st4 sLw sH in
  (app sHw cH, st5).

Definition dag_gf24_inv (st : dag_state) (a : list nat) : list nat * dag_state :=
  let aL := ProofSupport.take_of 2 a in
  let aH := ProofSupport.drop_of 2 a in
  let '(sL, st1) := dag_gf22_sq st aL in
  let '(sH, st2) := dag_gf22_sq st1 aH in
  let '(mLH, st3) := dag_gf22_mul st2 aL aH in
  let '(sHw, st4) := dag_gf22_mul_w st3 sH in
  let '(d0, st5) := dag_vec_xor st4 sL mLH in
  let '(delta, st6) := dag_vec_xor st5 d0 sHw in
  let '(dinv, st7) := dag_gf22_sq st6 delta in
  let '(aS, st8) := dag_vec_xor st7 aL aH in
  let '(uL, st9) := dag_gf22_mul st8 aS dinv in
  let '(uH, st10) := dag_gf22_mul st9 aH dinv in
  (app uL uH, st10).

Definition bit_of_nat (v row : nat) : bool :=
  Nat.eqb (Nat.modulo (Nat.div v (Nat.pow 2 row)) 2) 1.

Definition select_col_wires (cols wires : list nat) (row : nat) : list nat :=
  ProofSupport.map_over fst
    (ProofSupport.filter_of (fun cw => bit_of_nat (snd cw) row)
       (List.combine wires cols)).

Fixpoint dag_matrix_mul (st : dag_state) (cols wires : list nat) (rows : list nat) : list nat * dag_state :=
  match rows with
  | nil => (nil, st)
  | row :: rr =>
      let '(y, st1) := dag_xor_list st (select_col_wires cols wires row) in
      let '(yr, st2) := dag_matrix_mul st1 cols wires rr in
      (y :: yr, st2)
  end.

Fixpoint dag_apply_const_xor (st : dag_state) (c_val : nat) (ys : list nat) (rows : list nat) : list nat * dag_state :=
  match ys, rows with
  | y :: yr, row :: rr =>
      let '(y', st1) :=
        if bit_of_nat c_val row then dag_const_xor st true y else (y, st) in
      let '(yr', st2) := dag_apply_const_xor st1 c_val yr rr in
      (y' :: yr', st2)
  | _, _ => (nil, st)
  end.

Definition aes_fwd_cols : list nat :=
  1 :: 65 :: 102 :: 108 :: 86 :: 154 :: 88 :: 196 :: nil.

Definition aes_aff_inv_cols : list nat :=
  31 :: 25 :: 178 :: 157 :: 123 :: 246 :: 33 :: 28 :: nil.

Definition build_aes_sbox_dag : BoolCircuit :=
  let x_lsb := 7 :: 6 :: 5 :: 4 :: 3 :: 2 :: 1 :: 0 :: nil in
  let rows8 := 0 :: 1 :: 2 :: 3 :: 4 :: 5 :: 6 :: 7 :: nil in
  let '(t, st1) := dag_matrix_mul (8, nil) aes_fwd_cols x_lsb rows8 in
  let tL := ProofSupport.take_of 4 t in
  let tH := ProofSupport.drop_of 4 t in
  let '(sH, st2) := dag_gf24_sq_z st1 tH in
  let '(nuL, st3) := dag_gf22_mul_w st2 (ProofSupport.take_of 2 sH) in
  let '(nuH, st4) := dag_gf22_mul_w st3 (ProofSupport.drop_of 2 sH) in
  let sH_nu := app nuL nuH in
  let '(tSum, st5) := dag_vec_xor st4 tL tH in
  let '(m, st6) := dag_gf24_mul st5 tSum tL in
  let '(delta, st7) := dag_vec_xor st6 m sH_nu in
  let '(dinv, st8) := dag_gf24_inv st7 delta in
  let '(uL, st9) := dag_gf24_mul st8 tSum dinv in
  let '(uH, st10) := dag_gf24_mul st9 tH dinv in
  let u := app uL uH in
  let '(s_aff, st11) := dag_matrix_mul st10 aes_aff_inv_cols u rows8 in
  let '(y_lsb, st12) := dag_apply_const_xor st11 99 s_aff rows8 in
  {| bc_inputs := 8;
     bc_gates := List.rev (snd st12);
     bc_outputs := List.rev y_lsb |}.

Definition aes_sbox_dag : BoolCircuit := build_aes_sbox_dag.

Lemma aes_sbox_dag_wf : bool_circuit_wf aes_sbox_dag = true.
Proof. vm_cast_no_check (@eq_refl _ true). Qed.

Fixpoint forall_bools (k : nat) (P : list bool -> bool) : bool :=
  match k with
  | 0 => P nil
  | S r => andb (forall_bools r (fun bs => P (false :: bs)))
                (forall_bools r (fun bs => P (true :: bs)))
  end.

Lemma forall_bools_sound :
  forall k (P : list bool -> bool) bs,
    forall_bools k P = true ->
    count_of bs = k ->
    P bs = true.
Proof.
  induction k as [|k IH]; intros P [|b br] H Hlen; simpl in *; try discriminate Hlen.
  - exact H.
  - apply andb_prop in H. destruct H as [Hf Ht].
    destruct b;
      [exact (IH (fun bs => P (true :: bs)) br Ht ltac:(lia))
      | exact (IH (fun bs => P (false :: bs)) br Hf ltac:(lia))].
Qed.

Lemma bits_eqb_eq :
  forall xs ys, AesGcm.bits_eqb xs ys = true -> xs = ys.
Proof.
  induction xs as [|x xr IH]; intros [|y yr] H; simpl in H;
    try discriminate H; [reflexivity|].
  apply andb_prop in H. destruct H as [Hxy Hr].
  f_equal; [destruct x, y; simpl in Hxy; try reflexivity; discriminate Hxy | exact (IH yr Hr)].
Qed.

Lemma all_of_in :
  forall {A : Type} (p : A -> bool) (l : list A) (x : A),
    all_of p l = true ->
    ProofSupport.Member x l ->
    p x = true.
Proof.
  intros A p l x Hall Hmem. induction l as [|y r IH]; simpl in *; [contradiction|].
  apply andb_prop in Hall. destruct Hall as [Hy Hr].
  destruct Hmem as [<-|Hmem]; [exact Hy | exact (IH Hr Hmem)].
Qed.

Lemma aes_sbox_dag_matches_all_bytes_bool :
  all_of (fun b => AesGcm.bits_eqb (eval_bool_circuit aes_sbox_dag b) (AesGcm.sub_byte b))
    AesGcm.all_bytes = true.
Proof. vm_cast_no_check (@eq_refl _ true). Qed.

Lemma aes_sbox_dag_matches_8bits_bool :
  forall_bools 8 (fun b => AesGcm.bits_eqb (eval_bool_circuit aes_sbox_dag b) (AesGcm.sub_byte b)) = true.
Proof. vm_cast_no_check (@eq_refl _ true). Qed.

Lemma aes_sbox_dag_matches_all_bytes :
  forall b : AesGcm.byte,
    ProofSupport.Member b AesGcm.all_bytes ->
    eval_bool_circuit aes_sbox_dag b = AesGcm.sub_byte b.
Proof.
  intros b Hb. apply bits_eqb_eq.
  exact (all_of_in
           (fun b0 => AesGcm.bits_eqb (eval_bool_circuit aes_sbox_dag b0) (AesGcm.sub_byte b0))
           AesGcm.all_bytes b aes_sbox_dag_matches_all_bytes_bool Hb).
Qed.

Lemma aes_sbox_dag_eq_8bits :
  forall b0 b1 b2 b3 b4 b5 b6 b7 : bool,
    eval_bool_circuit aes_sbox_dag (b0 :: b1 :: b2 :: b3 :: b4 :: b5 :: b6 :: b7 :: nil) =
    AesGcm.sub_byte (b0 :: b1 :: b2 :: b3 :: b4 :: b5 :: b6 :: b7 :: nil).
Proof.
  intros b0 b1 b2 b3 b4 b5 b6 b7. apply bits_eqb_eq.
  exact (forall_bools_sound 8
           (fun b => AesGcm.bits_eqb (eval_bool_circuit aes_sbox_dag b) (AesGcm.sub_byte b))
           (b0 :: b1 :: b2 :: b3 :: b4 :: b5 :: b6 :: b7 :: nil)
           aes_sbox_dag_matches_8bits_bool eq_refl).
Qed.

Theorem aes_sbox_dag_table_matches_fips197 :
  map_over (fun b => AesGcm.byte_value (eval_bool_circuit aes_sbox_dag b)) AesGcm.all_bytes =
  map_over (fun b => AesGcm.byte_value (AesGcm.sub_byte b)) AesGcm.all_bytes.
Proof.
  apply support_map_ext. intros b Hb. f_equal.
  exact (aes_sbox_dag_matches_all_bytes b Hb).
Qed.

Definition masked_aes_sbox (n : nat) : BusGadget :=
  compile_bool_circuit n aes_sbox_dag.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_aes_sbox_correct :
  forall n (a : nat -> nat -> bool) tape,
    let bg := masked_aes_sbox n in
    let ins := map_over (fun i => xor_sum_upto (a i) (S n)) (upto 8) in
    map_over (fun u => xor_sum_upto (fun k => bg_value bg a tape (bg_wire_read bg u) (bg_out bg u k)) (S n))
      (bc_outputs aes_sbox_dag) =
    AesGcm.sub_byte ins.
Proof.
  intros n a tape. unfold masked_aes_sbox.
  rewrite (compile_bool_circuit_correct n aes_sbox_dag a tape aes_sbox_dag_wf).
  simpl (bc_inputs aes_sbox_dag).
  set (x0 := xor_sum_upto (a 0) (S n)).
  set (x1 := xor_sum_upto (a 1) (S n)).
  set (x2 := xor_sum_upto (a 2) (S n)).
  set (x3 := xor_sum_upto (a 3) (S n)).
  set (x4 := xor_sum_upto (a 4) (S n)).
  set (x5 := xor_sum_upto (a 5) (S n)).
  set (x6 := xor_sum_upto (a 6) (S n)).
  set (x7 := xor_sum_upto (a 7) (S n)).
  change (map_over (fun i => xor_sum_upto (a i) (S n)) (upto 8))
    with (x0 :: x1 :: x2 :: x3 :: x4 :: x5 :: x6 :: x7 :: nil).
  apply aes_sbox_dag_eq_8bits.
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_aes_sbox_multi_output_pini :
  forall n d,
    d <= n ->
    MultiOutputPINI (masked_aes_sbox n) (bc_outputs aes_sbox_dag) ex_robust d.
Proof.
  intros n d Hd. unfold masked_aes_sbox.
  apply compile_bool_circuit_multi_output_pini; [exact Hd | exact aes_sbox_dag_wf].
Qed.

(*| discharges: R-05-004a, R-15-053a |*)
Theorem masked_aes_sbox_out_is_pini :
  forall n d u_out,
    d <= n ->
    ProofSupport.Member u_out (bc_outputs aes_sbox_dag) ->
    PINI (bus_to_gadget (masked_aes_sbox n) u_out) ex_robust d.
Proof.
  intros n d u_out Hd Hu. unfold masked_aes_sbox.
  apply compile_bool_circuit_out_is_pini; [exact Hd | exact aes_sbox_dag_wf | exact Hu].
Qed.

(* =========================================================================
   6. Separating negative witnesses:
      (a) Unmasked AND leaks its secret operand,
      (b) Barrierless 2-share DOM AND is 1-PINI under ex_stable yet leaks
          under ex_glitch (and ex_robust) with a single probe,
      (c) Reusing the same 1-bit random mask across two 2-share DOM AND
          gates cancels the mask and violates 1-NI even under ex_stable.
   ========================================================================= *)

(* --- 6a. Unmasked AND leaks ---------------------------------------------- *)

Definition unmasked_and_exp : Experiment := {|
  x_share := gf2_sharing;
  x_prob := bit_tapes 0;
  x_circuit := g_in 0 :: g_in 1 :: g_op 3 (0 :: 1 :: nil) :: nil;
  x_ops := bool_ops;
  x_secret := (bool * bool)%type;
  x_in := fun s _ _ i => match i with 0 => fst s | _ => snd s end;
  x_init := fun _ _ _ => false;
  x_order := 1
|}.

(*| discharges: R-05-166 |*)
Theorem unmasked_and_exp_leaks :
  Leaks unmasked_and_exp ex_stable.
Proof.
  intro Hsec.
  specialize (Hsec (probe_of 2 0 :: nil) eq_refl (false, true) (true, true)).
  specialize (Hsec (true :: nil)).
  vm_compute in Hsec. discriminate Hsec.
Qed.

Definition recombined_2share_and_gadget : Gadget := {|
  gd_share := gf2_sharing;
  gd_prob := bit_tapes 0;
  gd_circuit :=
    g_in 0 :: g_in 1 :: g_in 2 :: g_in 3 ::
    g_op 2 (0 :: 1 :: nil) :: g_op 2 (2 :: 3 :: nil) ::
    g_op 3 (4 :: 5 :: nil) :: g_op 0 nil :: nil;
  gd_ops := bool_ops;
  gd_inputs := 2;
  gd_shares := 2;
  gd_out := fun k => match k with 0 => 6 | _ => 7 end;
  gd_read := 0;
  gd_assign := fun a _ _ i => match i with 0 => a 0 0 | 1 => a 0 1 | 2 => a 1 0 | _ => a 1 1 end;
  gd_start := fun _ _ _ => false
|}.

(*| discharges: R-05-166 |*)
Theorem recombined_2share_and_refutes_ni :
  ~ NI recombined_2share_and_gadget ex_stable 1.
Proof.
  intro Hni.
  destruct (Hni (probe_of 6 0 :: nil) (fun _ => false) eq_refl eq_refl) as [I [Hb Hsim]].
  pose proof (Hb 0 eq_refl) as Hb0. unfold card_in in Hb0. simpl in Hb0.
  assert (Hmiss0 : exists k0, k0 < 2 /\ I 0 k0 = false).
  { destruct (I 0 0) eqn:E0; destruct (I 0 1) eqn:E1; simpl in Hb0; try discriminate Hb0;
      [exists 1; split; [lia | exact E1] | exists 0; split; [lia | exact E0] | exists 0; split; [lia | exact E0]]. }
  destruct Hmiss0 as [k0 [Hk0 HI0]].
  set (a := fun j k : nat => match j with 0 => false | _ => Nat.eqb k 0 end).
  set (b := fun j k : nat => match j with 0 => Nat.eqb k k0 | _ => Nat.eqb k 0 end).
  assert (Hag : agree_on recombined_2share_and_gadget I a b).
  { intros j k Hj Hk HI. simpl in Hj, Hk.
    assert (Hj_lt : j < 2) by (apply Nat.ltb_lt; exact Hj).
    assert (Hk_lt : k < 2) by (apply Nat.ltb_lt; exact Hk).
    destruct j as [|[|j]]; [|reflexivity | lia].
    unfold a, b. destruct (Nat.eqb k k0) eqn:Ek; [|reflexivity].
    apply Nat.eqb_eq in Ek; subst k. rewrite HI0 in HI; discriminate HI. }
  specialize (Hsim a b Hag (true :: nil)).
  destruct k0 as [|[|k0]]; [| |lia]; vm_compute in Hsim; discriminate Hsim.
Qed.

(* --- 6b. Barrierless DOM AND: safe under ex_stable, leaks under ex_glitch --- *)

Definition dom_and_no_reg_gadget : Gadget := {|
  gd_share := gf2_sharing;
  gd_prob := bit_tapes 1;
  gd_circuit :=
    g_in 0 :: g_in 1 :: g_in 2 :: g_in 3 :: g_in 4 ::
    g_op 3 (0 :: 2 :: nil) ::
    g_op 3 (0 :: 3 :: nil) ::
    g_op 2 (6 :: 4 :: nil) ::
    g_op 2 (5 :: 7 :: nil) ::
    g_op 3 (1 :: 3 :: nil) ::
    g_op 3 (1 :: 2 :: nil) ::
    g_op 2 (10 :: 4 :: nil) ::
    g_op 2 (9 :: 11 :: nil) :: nil;
  gd_ops := bool_ops;
  gd_inputs := 2;
  gd_shares := 2;
  gd_out := fun k => match k with 0 => 8 | _ => 12 end;
  gd_read := 0;
  gd_assign := fun a tape _ i =>
    match i with 0 => a 0 0 | 1 => a 0 1 | 2 => a 1 0 | 3 => a 1 1 | _ => at_member tape 0 false end;
  gd_start := fun _ _ _ => false
|}.

Lemma bit_tapes_1_same_dist :
  forall (f g : Tape (bit_tapes 1) -> list bool),
    ((forall r : bool, f (r :: nil) = g (r :: nil)) \/
     (forall r : bool, f (r :: nil) = g (negb r :: nil))) ->
    SameDistribution (bit_tapes 1) (list bool) (list_eqb bool_eqb) f g.
Proof.
  intros f g [Hid | Hflip].
  - apply (equal_image_multisets_are_identically_distributed (list bool) (tape_enum (bit_tapes 1))).
    replace (tape_enum (bit_tapes 1)) with ((false :: nil) :: (true :: nil) :: nil) by (vm_compute; reflexivity).
    simpl map_over. rewrite (Hid false), (Hid true). apply perm_refl.
  - apply (equal_image_multisets_are_identically_distributed (list bool) (tape_enum (bit_tapes 1))).
    replace (tape_enum (bit_tapes 1)) with ((false :: nil) :: (true :: nil) :: nil) by (vm_compute; reflexivity).
    simpl map_over. rewrite (Hflip false), (Hflip true). simpl negb.
    apply (perm_app_comm (g (true :: nil) :: nil) (g (false :: nil) :: nil)).
Qed.

Definition dom_no_reg_eval (a0 a1 b0 b1 r : bool) (w : nat) : bool :=
  match w with
  | 0 => a0
  | 1 => a1
  | 2 => b0
  | 3 => b1
  | 4 => r
  | 5 => andb a0 b0
  | 6 => andb a0 b1
  | 7 => xorb (andb a0 b1) r
  | 8 => xorb (andb a0 b0) (xorb (andb a0 b1) r)
  | 9 => andb a1 b1
  | 10 => andb a1 b0
  | 11 => xorb (andb a1 b0) r
  | 12 => xorb (andb a1 b1) (xorb (andb a1 b0) r)
  | _ => false
  end.

Lemma dom_and_no_reg_value_eval :
  forall a r cyc w,
    w < 13 ->
    gd_value dom_and_no_reg_gadget a (r :: nil) cyc w =
    dom_no_reg_eval (a 0 0) (a 0 1) (a 1 0) (a 1 1) r w.
Proof.
  intros a r cyc w Hw.
  destruct w as [|[|[|[|[|[|[|[|[|[|[|[|[|w]]]]]]]]]]]]]; [..|lia];
    unfold gd_value, value_at; simpl; repeat rewrite gf2_add_zero_r; reflexivity.
Qed.

Definition dom_no_reg_view_fn (ow : option nat) (B0 B1 a0 a1 b0 b1 r : bool) : list bool :=
  app (match ow with None => nil | Some w => dom_no_reg_eval a0 a1 b0 b1 r w :: nil end)
      (app (if B0 then dom_no_reg_eval a0 a1 b0 b1 r 8 :: nil else nil)
           (if B1 then dom_no_reg_eval a0 a1 b0 b1 r 12 :: nil else nil)).

Definition dom_no_reg_sim_shares_ow (ow : option nat) (B0 B1 : bool) : ShareSet :=
  match ow with
  | None => fun _ _ => false
  | Some w =>
      match w with
      | 0 | 2 | 5 | 7 | 8 => fun _ k => Nat.eqb k 0
      | 1 | 3 | 9 | 11 | 12 => fun _ k => Nat.eqb k 1
      | 6 => fun j k => if Nat.eqb j 0 then Nat.eqb k 0 else Nat.eqb k 1
      | 10 => fun j k => if Nat.eqb j 0 then Nat.eqb k 1 else Nat.eqb k 0
      | 4 => if B0 then (fun _ k => Nat.eqb k 1)
             else if B1 then (fun _ k => Nat.eqb k 0)
             else (fun _ _ => false)
      | _ => fun _ _ => false
      end
  end.

Definition dom_no_reg_sim_shares (ps : list Probe) (B : nat -> bool) : ShareSet :=
  dom_no_reg_sim_shares_ow
    (match ps with nil => None | p :: _ => Some (p_wire p) end) (B 0) (B 1).

Lemma dom_no_reg_sim_shares_bounded :
  forall ps B,
    (count_of ps <=? 1) = true ->
    BoundedBy dom_and_no_reg_gadget (dom_no_reg_sim_shares ps B) (count_of ps).
Proof.
  intros [|p [|p2 pr]] B Hcnt j Hj; simpl in *; try discriminate Hcnt.
  - unfold card_in. simpl. reflexivity.
  - unfold dom_no_reg_sim_shares, dom_no_reg_sim_shares_ow.
    destruct (p_wire p) as [|[|[|[|[|[|[|[|[|[|[|[|[|w]]]]]]]]]]]]];
      try (unfold card_in; destruct j as [|[|j]]; reflexivity).
    unfold card_in. destruct (B 0), (B 1), j as [|[|j]]; reflexivity.
Qed.

Definition dom_no_reg_ows : list (option nat) :=
  None :: map_over Some (upto 13).

Definition check_no_reg_pair (ow : option nat) (B0 B1 a0 a1 b0 b1 c0 c1 d0 d1 : bool) : bool :=
  let I := dom_no_reg_sim_shares_ow ow B0 B1 in
  let agree :=
    andb (if orb (I 0 0) B0 then bool_eqb a0 c0 else true)
    (andb (if orb (I 0 1) B1 then bool_eqb a1 c1 else true)
    (andb (if orb (I 1 0) B0 then bool_eqb b0 d0 else true)
          (if orb (I 1 1) B1 then bool_eqb b1 d1 else true))) in
  if negb agree then true
  else
    let same_id :=
      andb (list_eqb bool_eqb (dom_no_reg_view_fn ow B0 B1 a0 a1 b0 b1 false)
                              (dom_no_reg_view_fn ow B0 B1 c0 c1 d0 d1 false))
           (list_eqb bool_eqb (dom_no_reg_view_fn ow B0 B1 a0 a1 b0 b1 true)
                              (dom_no_reg_view_fn ow B0 B1 c0 c1 d0 d1 true)) in
    let same_flip :=
      andb (list_eqb bool_eqb (dom_no_reg_view_fn ow B0 B1 a0 a1 b0 b1 false)
                              (dom_no_reg_view_fn ow B0 B1 c0 c1 d0 d1 true))
           (list_eqb bool_eqb (dom_no_reg_view_fn ow B0 B1 a0 a1 b0 b1 true)
                              (dom_no_reg_view_fn ow B0 B1 c0 c1 d0 d1 false)) in
    orb same_id same_flip.

Definition check_no_reg_for_ow (ow : option nat) : bool :=
  forall_bools 2 (fun bs2 =>
    match bs2 with
    | B0 :: B1 :: nil =>
        forall_bools 8 (fun bs8 =>
          match bs8 with
          | a0 :: a1 :: b0 :: b1 :: c0 :: c1 :: d0 :: d1 :: nil =>
              check_no_reg_pair ow B0 B1 a0 a1 b0 b1 c0 c1 d0 d1
          | _ => false
          end)
    | _ => false
    end).

Lemma check_no_reg_all_ok :
  all_of check_no_reg_for_ow dom_no_reg_ows = true.
Proof. vm_cast_no_check (@eq_refl _ true). Qed.

Lemma list_bool_eqb_sound :
  forall xs ys : list bool, list_eqb bool_eqb xs ys = true -> xs = ys.
Proof.
  intros xs ys H. apply (list_eqb_sound gf2_sharing xs ys H).
Qed.

Lemma dom_no_reg_split_view_fn :
  forall ps B ow,
    (match ow with None => ps = nil | Some w => w < 13 /\ exists cyc, ps = probe_of w cyc :: nil end) ->
    forall x r,
      split_view dom_and_no_reg_gadget ex_stable ps B x (r :: nil) =
      dom_no_reg_view_fn ow (B 0) (B 1) (x 0 0) (x 0 1) (x 1 0) (x 1 1) r.
Proof.
  intros ps B ow Hps x r. unfold split_view, dom_no_reg_view_fn. f_equal.
  - destruct ow as [w|]; [destruct Hps as [Hw13 [cyc ->]] | subst ps; reflexivity].
    unfold internal_view, probe_set, flat_map_over, ex_stable, map_over, ProofSupport.map_over, app.
    change (obs_value (gd_share dom_and_no_reg_gadget) (gd_ops dom_and_no_reg_gadget) (gd_circuit dom_and_no_reg_gadget) (gd_start dom_and_no_reg_gadget x (r :: nil)) (gd_assign dom_and_no_reg_gadget x (r :: nil)) (obs_at (p_wire (probe_of w cyc)) (p_cycle (probe_of w cyc)))) with (gd_value dom_and_no_reg_gadget x (r :: nil) cyc w).
    f_equal. apply dom_and_no_reg_value_eval; exact Hw13.
  - unfold output_view, selected_outputs.
    replace (upto (gd_shares dom_and_no_reg_gadget)) with (0 :: 1 :: nil) by reflexivity.
    change (filter_of B (0 :: 1 :: nil)) with
      (if B 0 then 0 :: (if B 1 then 1 :: nil else nil) else (if B 1 then 1 :: nil else nil)).
    destruct (B 0) eqn:EB0; destruct (B 1) eqn:EB1;
      cbv iota; unfold map_over; cbn [ProofSupport.map_over app];
      try change (gd_read dom_and_no_reg_gadget) with 0;
      try change (gd_out dom_and_no_reg_gadget 0) with 8;
      try change (gd_out dom_and_no_reg_gadget 1) with 12;
      repeat f_equal; apply dom_and_no_reg_value_eval; lia.
Qed.

Lemma dom_no_reg_solve_ow :
  forall ps B ow a b,
    agree_on dom_and_no_reg_gadget (union_shares (dom_no_reg_sim_shares ps B) B) a b ->
    ProofSupport.Member ow dom_no_reg_ows ->
    (match ow with None => ps = nil | Some w => w < 13 /\ exists cyc, ps = probe_of w cyc :: nil end) ->
    SameDistribution (bit_tapes 1) (list bool) (list_eqb bool_eqb)
      (split_view dom_and_no_reg_gadget ex_stable ps B a)
      (split_view dom_and_no_reg_gadget ex_stable ps B b).
Proof.
  intros ps B ow a b Hag How_mem Hps.
  assert (Ha_eq : forall j k, j < 2 -> k < 2 ->
    orb (dom_no_reg_sim_shares ps B j k) (B k) = true -> a j k = b j k).
  { intros j k Hj Hk HI. apply Hag; [destruct j as [|[|j]]; try reflexivity; lia | destruct k as [|[|k]]; try reflexivity; lia | exact HI]. }
  pose proof (all_of_in check_no_reg_for_ow dom_no_reg_ows ow check_no_reg_all_ok How_mem) as Hrow.
  unfold check_no_reg_for_ow in Hrow.
  pose proof (forall_bools_sound 2 _ (B 0 :: B 1 :: nil) Hrow eq_refl) as H8.
  pose proof (forall_bools_sound 8 _
    (a 0 0 :: a 0 1 :: a 1 0 :: a 1 1 :: b 0 0 :: b 0 1 :: b 1 0 :: b 1 1 :: nil)
    H8 eq_refl) as Hpair.
  unfold check_no_reg_pair in Hpair.
  assert (Hand4 : forall x1 x2 x3 x4 : bool,
    x1 = true -> x2 = true -> x3 = true -> x4 = true ->
    andb x1 (andb x2 (andb x3 x4)) = true)
    by (intros x1 x2 x3 x4 -> -> -> ->; reflexivity).
  assert (Hbool_refl : forall x, bool_eqb x x = true) by (intros []; reflexivity).
  assert (How_eq : dom_no_reg_sim_shares ps B = dom_no_reg_sim_shares_ow ow (B 0) (B 1)).
  { destruct ow as [w|]; [destruct Hps as [_ [cyc ->]] | subst ps]; reflexivity. }
  assert (Hagree_bool :
    andb (if orb (dom_no_reg_sim_shares_ow ow (B 0) (B 1) 0 0) (B 0) then bool_eqb (a 0 0) (b 0 0) else true)
    (andb (if orb (dom_no_reg_sim_shares_ow ow (B 0) (B 1) 0 1) (B 1) then bool_eqb (a 0 1) (b 0 1) else true)
    (andb (if orb (dom_no_reg_sim_shares_ow ow (B 0) (B 1) 1 0) (B 0) then bool_eqb (a 1 0) (b 1 0) else true)
          (if orb (dom_no_reg_sim_shares_ow ow (B 0) (B 1) 1 1) (B 1) then bool_eqb (a 1 1) (b 1 1) else true))) = true).
  { rewrite <- How_eq.
    apply Hand4;
      [destruct (orb (dom_no_reg_sim_shares ps B 0 0) (B 0)) eqn:E;
         [rewrite (Ha_eq 0 0 ltac:(lia) ltac:(lia) E), Hbool_refl; reflexivity | reflexivity]
      |destruct (orb (dom_no_reg_sim_shares ps B 0 1) (B 1)) eqn:E;
         [rewrite (Ha_eq 0 1 ltac:(lia) ltac:(lia) E), Hbool_refl; reflexivity | reflexivity]
      |destruct (orb (dom_no_reg_sim_shares ps B 1 0) (B 0)) eqn:E;
         [rewrite (Ha_eq 1 0 ltac:(lia) ltac:(lia) E), Hbool_refl; reflexivity | reflexivity]
      |destruct (orb (dom_no_reg_sim_shares ps B 1 1) (B 1)) eqn:E;
         [rewrite (Ha_eq 1 1 ltac:(lia) ltac:(lia) E), Hbool_refl; reflexivity | reflexivity]]. }
  rewrite Hagree_bool in Hpair. simpl negb in Hpair.
  apply orb_prop in Hpair. apply bit_tapes_1_same_dist.
  destruct Hpair as [Hid | Hflip].
  - apply andb_prop in Hid. destruct Hid as [Hf Ht].
    apply list_bool_eqb_sound in Hf. apply list_bool_eqb_sound in Ht.
    left. intros [|].
    + rewrite !(dom_no_reg_split_view_fn ps B ow Hps). exact Ht.
    + rewrite !(dom_no_reg_split_view_fn ps B ow Hps). exact Hf.
  - apply andb_prop in Hflip. destruct Hflip as [Hf Ht].
    apply list_bool_eqb_sound in Hf. apply list_bool_eqb_sound in Ht.
    right. intros [|].
    + rewrite !(dom_no_reg_split_view_fn ps B ow Hps). exact Ht.
    + rewrite !(dom_no_reg_split_view_fn ps B ow Hps). exact Hf.
Qed.

Lemma dom_and_no_reg_stable_1pini :
  PINI dom_and_no_reg_gadget ex_stable 1.
Proof.
  intros ps B Hw Hcnt.
  exists (dom_no_reg_sim_shares ps B). split.
  { apply dom_no_reg_sim_shares_bounded. exact Hcnt. }
  intros a b Hag.
  destruct ps as [|[w cyc] [|p2 pr]]; [| |simpl in Hcnt; discriminate Hcnt].
  - apply (dom_no_reg_solve_ow nil B None a b Hag); [left; reflexivity | reflexivity].
  - unfold probe_of in Hw. simpl in Hw. apply andb_prop in Hw. destruct Hw as [Hw _].
    unfold wire_count in Hw. rewrite count_of_is_length in Hw. simpl length in Hw.
    apply Nat.ltb_lt in Hw.
    apply (dom_no_reg_solve_ow _ B (Some w) a b Hag).
    + destruct w as [|[|[|[|[|[|[|[|[|[|[|[|[|w]]]]]]]]]]]]]; [..|lia];
        unfold dom_no_reg_ows; simpl; auto 20.
    + split; [exact Hw | exists cyc; reflexivity].
Qed.

(*| discharges: R-05-166 |*)
Theorem dom_and_no_reg_refutes_ni_glitch :
  ~ NI dom_and_no_reg_gadget ex_glitch 1.
Proof.
  intro Hni.
  destruct (Hni (probe_of 8 0 :: nil) (fun _ => false) eq_refl eq_refl) as [I [Hb Hsim]].
  pose proof (Hb 1 eq_refl) as Hb1. unfold card_in in Hb1. simpl in Hb1.
  assert (Hmiss1 : exists k1, k1 < 2 /\ I 1 k1 = false).
  { destruct (I 1 0) eqn:E0; destruct (I 1 1) eqn:E1; simpl in Hb1; try discriminate Hb1;
      [exists 1; split; [lia | exact E1] | exists 0; split; [lia | exact E0] | exists 0; split; [lia | exact E0]]. }
  destruct Hmiss1 as [k1 [Hk1 HI1]].
  set (a := fun (_ _ : nat) => false).
  set (b := fun j k : nat => match j with 1 => Nat.eqb k k1 | _ => false end).
  assert (Hag : agree_on dom_and_no_reg_gadget I a b).
  { intros j k Hj Hk HI. simpl in Hj, Hk.
    destruct j as [|[|j]]; [reflexivity | |discriminate Hj].
    unfold a, b. destruct (Nat.eqb k k1) eqn:Ek; [|reflexivity].
    apply Nat.eqb_eq in Ek; subst k. rewrite HI1 in HI; discriminate HI. }
  specialize (Hsim a b Hag).
  destruct k1 as [|[|k1]]; [| |lia].
  - specialize (Hsim (false :: true :: false :: false :: false :: nil)).
    vm_compute in Hsim. discriminate Hsim.
  - specialize (Hsim (false :: false :: false :: true :: false :: nil)).
    vm_compute in Hsim. discriminate Hsim.
Qed.

(*| discharges: R-05-166 |*)
Theorem dom_and_no_reg_refutes_pini_robust :
  ~ PINI dom_and_no_reg_gadget ex_robust 1.
Proof.
  intro Hpini.
  destruct (Hpini (probe_of 8 0 :: nil) (fun _ => false) eq_refl eq_refl) as [I [Hb Hsim]].
  pose proof (Hb 1 eq_refl) as Hb1. unfold card_in in Hb1. simpl in Hb1.
  assert (Hmiss1 : exists k1, k1 < 2 /\ I 1 k1 = false).
  { destruct (I 1 0) eqn:E0; destruct (I 1 1) eqn:E1; simpl in Hb1; try discriminate Hb1;
      [exists 1; split; [lia | exact E1] | exists 0; split; [lia | exact E0] | exists 0; split; [lia | exact E0]]. }
  destruct Hmiss1 as [k1 [Hk1 HI1]].
  set (a := fun (_ _ : nat) => false).
  set (b := fun j k : nat => match j with 1 => Nat.eqb k k1 | _ => false end).
  assert (Hag : agree_on dom_and_no_reg_gadget (union_shares I (fun _ => false)) a b).
  { intros j k Hj Hk HI. unfold union_shares in HI. rewrite orb_false_r in HI.
    simpl in Hj, Hk. destruct j as [|[|j]]; [reflexivity | |discriminate Hj].
    unfold a, b. destruct (Nat.eqb k k1) eqn:Ek; [|reflexivity].
    apply Nat.eqb_eq in Ek; subst k. rewrite HI1 in HI; discriminate HI. }
  specialize (Hsim a b Hag).
  destruct k1 as [|[|k1]]; [| |lia].
  - specialize (Hsim (false :: false :: true :: true :: false :: false ::
                      false :: false :: false :: false :: nil)).
    vm_compute in Hsim. discriminate Hsim.
  - specialize (Hsim (false :: false :: false :: false :: false :: false ::
                      true :: true :: false :: false :: nil)).
    vm_compute in Hsim. discriminate Hsim.
Qed.

(* --- 6c. Reused randomness across two DOM AND gates leaks under ex_stable - *)

Definition reused_rand_two_and_gadget : Gadget := {|
  gd_share := gf2_sharing;
  gd_prob := bit_tapes 1;
  gd_circuit :=
    g_in 0 :: g_in 1 :: g_in 2 :: g_in 3 :: g_in 4 :: g_in 5 :: g_in 6 ::
    (* Gate 1: u = a & b using r (wire 6) *)
    g_op 3 (0 :: 2 :: nil) ::
    g_op 3 (0 :: 3 :: nil) ::
    g_op 2 (8 :: 6 :: nil) ::
    g_reg 9 ::
    g_op 2 (7 :: 10 :: nil) ::
    g_op 3 (1 :: 3 :: nil) ::
    g_op 3 (1 :: 2 :: nil) ::
    g_op 2 (13 :: 6 :: nil) ::
    g_reg 14 ::
    g_op 2 (12 :: 15 :: nil) ::
    (* Gate 2: v = u & c reusing the same r (wire 6) *)
    g_op 3 (11 :: 4 :: nil) ::
    g_op 3 (11 :: 5 :: nil) ::
    g_op 2 (18 :: 6 :: nil) ::
    g_reg 19 ::
    g_op 2 (17 :: 20 :: nil) ::
    g_op 3 (16 :: 5 :: nil) ::
    g_op 3 (16 :: 4 :: nil) ::
    g_op 2 (23 :: 6 :: nil) ::
    g_reg 24 ::
    g_op 2 (22 :: 25 :: nil) :: nil;
  gd_ops := bool_ops;
  gd_inputs := 3;
  gd_shares := 2;
  gd_out := fun k => match k with 0 => 21 | _ => 26 end;
  gd_read := 2;
  gd_assign := fun a tape _ i =>
    match i with
    | 0 => a 0 0 | 1 => a 0 1
    | 2 => a 1 0 | 3 => a 1 1
    | 4 => a 2 0 | 5 => a 2 1
    | _ => at_member tape 0 false
    end;
  gd_start := fun _ _ _ => false
|}.

(*| discharges: R-05-166 |*)
Theorem reused_rand_two_and_refutes_ni_stable :
  ~ NI reused_rand_two_and_gadget ex_stable 1.
Proof.
  intro Hni.
  destruct (Hni (probe_of 21 2 :: nil) (fun _ => false) eq_refl eq_refl) as [I [Hb Hsim]].
  pose proof (Hb 1 eq_refl) as Hb1. unfold card_in in Hb1. simpl in Hb1.
  assert (Hmiss1 : exists k1, k1 < 2 /\ I 1 k1 = false).
  { destruct (I 1 0) eqn:E0; destruct (I 1 1) eqn:E1; simpl in Hb1; try discriminate Hb1;
      [exists 1; split; [lia | exact E1] | exists 0; split; [lia | exact E0] | exists 0; split; [lia | exact E0]]. }
  destruct Hmiss1 as [k1 [Hk1 HI1]].
  set (a := fun j k : nat =>
    match j with
    | 0 => Nat.eqb k 0
    | 1 => false
    | _ => Nat.eqb k 1
    end).
  set (b := fun j k : nat =>
    match j with
    | 0 => Nat.eqb k 0
    | 1 => Nat.eqb k k1
    | _ => Nat.eqb k 1
    end).
  assert (Hag : agree_on reused_rand_two_and_gadget I a b).
  { intros j k Hj Hk HI. simpl in Hj, Hk.
    destruct j as [|[|[|j]]]; [reflexivity | | reflexivity | discriminate Hj].
    unfold a, b. destruct (Nat.eqb k k1) eqn:Ek; [|reflexivity].
    apply Nat.eqb_eq in Ek; subst k. rewrite HI1 in HI; discriminate HI. }
  specialize (Hsim a b Hag (true :: nil)).
  destruct k1 as [|[|k1]]; [| |lia]; vm_compute in Hsim; discriminate Hsim.
Qed.

