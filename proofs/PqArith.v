(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   PqArith.v

   Shared modular polynomial and byte interfaces for ML-KEM-1024 and
   ML-DSA-87, under docs/assurance/pq-reference-contract.md. The algorithm
   editions are FIPS 203 and FIPS 204, both published 2024-08-13. ML-KEM
   uses q=3329, root=17, seven layers and quadratic leaves; ML-DSA uses
   q=8380417, root=1753, eight layers and linear leaves. Both have degree
   256. Matrix-domain multiplication preserves this complete/incomplete
   transform distinction. Negacyclic schoolbook multiplication is an
   independent reference, not an optimized implementation.

   ntt_roundtrip_general lifts scalar butterfly identities through the actual
   list transform and proves the half lengths. It takes reduced coefficients,
   an input-length factorization, inverse-root certificates and the final
   inverse-scale identity. The selected rings' certificates are computed and
   yield mlkem_ntt_roundtrip and mldsa_ntt_roundtrip for EVERY reduced
   256-coefficient polynomial. These universal statements do not depend on
   the finite probe examples. General transform multiplication equivalence to
   the quotient ring is not proved; the schoolbook/product examples exercise
   that separate boundary.

   byte_codec_roundtrip proves decode(encode(xs))=xs for every positive
   width, bounded coefficient list and whole-byte alignment, using general
   bit and chunk laws. External keys/signatures still need prescribed length
   and canonical-range checks. Compression/error checks exhaust the selected
   ML-KEM residue/width domains; they are finite enumeration, not a symbolic
   bound for every modulus and width. Official scheme-vector campaigns own
   interoperability with the standard, separately from inverse identities.

   pow_mod has a 64-step binary exponent budget. The selected transform
   exponents are at most 512; arbitrary exponents above that budget are
   outside its modular-power specification. The general inverse theorem
   checks resulting root-unit identities rather than assuming a prime modulus
   or an unproved power law. Ring carries parameters; ring_wf alone does not
   contain every shape/range premise. The FIPS standards fix the bit and
   residue orders. Alternative-order examples demonstrate different outputs;
   they are not unresolved normative choices.

   No computational reduction, randomness claim, masking, constant-time or
   binary refinement theorem is supplied. Centered reduction branches on its
   coefficient and is not asserted secret-independent. The native constant
   and assumption audit owns the proof inventory. No global axiom is added.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-058a R-05-163 R-05-164 R-05-165 R-05-166
   SHA256: 71013dad2bf49eb5ed193853d158773449ee1a3ac4108ce256e26e0e0f41c1c7
   (*| END derived |*)
   ========================================================================= *)
From Stdlib Require Import ZArith List Arith Lia.

Open Scope Z_scope.

(* -------------------------------------------------------------------------
   Helpers over the standard list library, in the idiom the sibling
   artifacts use: a boolean where a Prop would need extensionality, and a
   fuel where a recursion is not structural.
   ------------------------------------------------------------------------- *)

(* The out-of-range answer this file relies on, named once so that it is a
   decision rather than a default repeated at every coefficient read, and
   pinned by an Example below rather than left unreachable. *)
Definition coeff (a : list Z) (i : nat) : Z := nth i a 0.

Definition poly_eqb (a b : list Z) : bool :=
  Nat.eqb (length a) (length b) && forallb (fun p => Z.eqb (fst p) (snd p)) (combine a b).

(* The fuel is the caller's bound on how many chunks there can be, the
   recursion being on the chunk count rather than on the list, which `skipn`
   does not decrease structurally. *)
Fixpoint chunk_of {A : Type} (fuel k : nat) (l : list A) : list (list A) :=
  match fuel with
  | O => nil
  | S f => match l with
           | nil => nil
           | _ => firstn k l :: chunk_of f k (skipn k l)
           end
  end.

Definition two_pow (d : nat) : Z := 2 ^ Z.of_nat d.

(* A run of consecutive integers, counted down in `nat` and carried in `Z`.
   `seq` counts in `nat` alone, and a unary index converted at every element
   costs the square of the run's length, which is the difference between a
   check that runs and one that is not written. *)
Fixpoint z_range (n : nat) (start : Z) : list Z :=
  match n with O => nil | S k => start :: z_range k (start + 1) end.

Definition indices (n : nat) : list Z := z_range n 0.

(* A positional fold, so that a probe polynomial is pinned by its contents
   and their order rather than by a length nothing reads. *)
Definition digest_of (q : Z) (a : list Z) : Z :=
  fold_left (fun acc x => (3 * acc + x) mod q) a 1.

(* -------------------------------------------------------------------------
   Arithmetic modulo q. `Z.modulo` at a positive divisor already returns a
   non-negative remainder, so a reduced coefficient needs no second step.
   ------------------------------------------------------------------------- *)

Definition addmod (q x y : Z) : Z := (x + y) mod q.
Definition submod (q x y : Z) : Z := (x - y) mod q.
Definition mulmod (q x y : Z) : Z := (x * y) mod q.

(* Square and multiply, the fuel being the exponent itself, which bounds the
   halving chain with room to spare. A linear exponentiation would be
   correct and would cost the inverse transform its own leaf count times the
   group order in multiplications, which is the difference between a check
   that runs and one that is not written. *)
Fixpoint pow_mod_go (q b : Z) (fuel : nat) (e : Z) : Z :=
  match fuel with
  | O => 1 mod q
  | S f =>
      if Z.leb e 0 then 1 mod q
      else let h := pow_mod_go q b f (e / 2) in
           let s := mulmod q h h in
           if Z.eqb (e mod 2) 0 then s else mulmod q s b
  end.

(* Sixty-four halvings reach zero from any exponent below 2^64, which is far
   above both group orders, and the fuel is never what stops a run. *)
Definition pow_mod (q b e : Z) : Z := pow_mod_go q b 64 e.

(* The centred representative, which is the standards' mod-plus-minus: for an
   odd modulus the range is the symmetric interval and there is no tie. *)
Definition centred (q x : Z) : Z :=
  let r := x mod q in if q <? 2 * r then r - q else r.

Definition norm_inf (q : Z) (a : list Z) : Z :=
  fold_left (fun m x => Z.max m (Z.abs (centred q x))) a 0.

Definition norm_inf_vec (q : Z) (v : list (list Z)) : Z :=
  fold_left (fun m a => Z.max m (norm_inf q a)) v 0.

(* -------------------------------------------------------------------------
   Coefficientwise operations. `combine` truncates to the shorter argument,
   which is what keeps every one of these total.
   ------------------------------------------------------------------------- *)

Definition vadd (q : Z) (a b : list Z) : list Z :=
  map (fun p => addmod q (fst p) (snd p)) (combine a b).

Definition vsub (q : Z) (a b : list Z) : list Z :=
  map (fun p => submod q (fst p) (snd p)) (combine a b).

Definition vpointwise (q : Z) (a b : list Z) : list Z :=
  map (fun p => mulmod q (fst p) (snd p)) (combine a b).

Definition vscale (q c : Z) (a : list Z) : list Z := map (mulmod q c) a.

Definition vneg (q : Z) (a : list Z) : list Z := map (fun x => submod q 0 x) a.

Definition zero_poly (n : nat) : list Z := map (fun _ => 0) (indices n).

(* -------------------------------------------------------------------------
   The ring, and every quantity that separates the two schemes' rings.
   ------------------------------------------------------------------------- *)

Record Ring : Type := {
  ring_degree : nat;      (* n, the number of coefficients *)
  ring_layers : nat;      (* L, the number of transform layers *)
  ring_modulus : Z;       (* q *)
  ring_root : Z;          (* a primitive 2^(L+1)-th root of unity mod q *)
  ring_inv_scale : Z      (* 2^(-L) mod q, checked rather than trusted *)
}.

Definition ring_split (r : Ring) : Z := two_pow (ring_layers r).
Definition ring_order (r : Ring) : Z := 2 * ring_split r.
Definition ring_leaf_degree (r : Ring) : Z :=
  Z.of_nat (ring_degree r) / ring_split r.

(* The top modulus is X^n + 1, which is X^n - psi^(2^L), so the recursion's
   first exponent is the same 2^L that names the negation. *)
Definition ring_top_exponent (r : Ring) : Z := ring_split r.

(* What a ring must satisfy for every statement below to be about it: a
   modulus above one and a root whose 2^L-th power is -1. For the selected
   odd moduli this gives order exactly 2^(L+1). Also a scaling inverting 2^L
   and a degree the layer count divides. *)
Definition ring_wf (r : Ring) : bool :=
  (1 <? ring_modulus r)
  && Z.eqb (pow_mod (ring_modulus r) (ring_root r) (ring_split r))
           (ring_modulus r - 1)
  && Z.eqb (mulmod (ring_modulus r) (ring_split r) (ring_inv_scale r)) 1
  && Z.eqb (ring_leaf_degree r * ring_split r) (Z.of_nat (ring_degree r)).

(* FIPS 203's ring. The 2-adic valuation of 3329 - 1 is eight, so there is no
   512th root of unity and the transform stops at seven layers with 128
   quadratic residue rings left standing. *)
Definition mlkem_ring : Ring :=
  {| ring_degree := 256; ring_layers := 7; ring_modulus := 3329;
     ring_root := 17; ring_inv_scale := 3303 |}.

(* FIPS 204's ring. The valuation of 8380417 - 1 is thirteen, so a 512th root
   exists and the eighth layer leaves 256 copies of Z_q. *)
Definition mldsa_ring : Ring :=
  {| ring_degree := 256; ring_layers := 8; ring_modulus := 8380417;
     ring_root := 1753; ring_inv_scale := 8347681 |}.

(* -------------------------------------------------------------------------
   The transform. One recursion, two instantiations, and no table.
   ------------------------------------------------------------------------- *)

Fixpoint ntt_go (q psi split : Z) (layers : nat) (e : Z) (a : list Z) : list Z :=
  match layers with
  | O => a
  | S k =>
      let m := Nat.div (length a) 2 in
      let half := e / 2 in
      let t := vscale q (pow_mod q psi half) (skipn m a) in
      ntt_go q psi split k half (vadd q (firstn m a) t)
        ++ ntt_go q psi split k (half + split) (vsub q (firstn m a) t)
  end.

Fixpoint intt_go (q psi split : Z) (layers : nat) (e : Z) (a : list Z) : list Z :=
  match layers with
  | O => a
  | S k =>
      let m := Nat.div (length a) 2 in
      let half := e / 2 in
      let b0 := intt_go q psi split k half (firstn m a) in
      let b1 := intt_go q psi split k (half + split) (skipn m a) in
      vadd q b0 b1
        ++ vscale q (pow_mod q psi (2 * split - half)) (vsub q b0 b1)
  end.

Definition ntt (r : Ring) (a : list Z) : list Z :=
  ntt_go (ring_modulus r) (ring_root r) (ring_split r) (ring_layers r)
         (ring_top_exponent r) a.

Definition intt (r : Ring) (a : list Z) : list Z :=
  vscale (ring_modulus r) (ring_inv_scale r)
         (intt_go (ring_modulus r) (ring_root r) (ring_split r) (ring_layers r)
                  (ring_top_exponent r) a).

(* The exponents the recursion reaches at its leaves, in the order the
   concatenations above put them, so a leaf's modulus is X^(n/2^L) minus this
   power of the root. *)
Fixpoint leaf_exponents (split : Z) (layers : nat) (e : Z) : list Z :=
  match layers with
  | O => e :: nil
  | S k => leaf_exponents split k (e / 2) ++ leaf_exponents split k (e / 2 + split)
  end.

Definition leaf_roots (r : Ring) : list Z :=
  map (pow_mod (ring_modulus r) (ring_root r))
      (leaf_exponents (ring_split r) (ring_layers r) (ring_top_exponent r)).

(* -------------------------------------------------------------------------
   The two multiplication contracts, which are where the two schemes' rings
   stop being one object. A transform that leaves residue rings of degree one
   multiplies coefficientwise; one that leaves residue rings of degree two
   multiplies in Z_q[X]/(X^2 - gamma) at each leaf's own gamma, and the two
   are not interchangeable in either direction.
   ------------------------------------------------------------------------- *)

Fixpoint basemul_quadratic (q : Z) (gammas a b : list Z) : list Z :=
  match gammas with
  | nil => nil
  | g :: gs =>
      match a, b with
      | a0 :: a1 :: ar, b0 :: b1 :: br =>
          addmod q (mulmod q a0 b0) (mulmod q g (mulmod q a1 b1))
          :: addmod q (mulmod q a0 b1) (mulmod q a1 b0)
          :: basemul_quadratic q gs ar br
      | _, _ => nil
      end
  end.

Definition mul_ntt_quadratic (r : Ring) (a b : list Z) : list Z :=
  basemul_quadratic (ring_modulus r) (leaf_roots r) a b.

Definition mul_ntt_pointwise (r : Ring) (a b : list Z) : list Z :=
  vpointwise (ring_modulus r) a b.

(* The schoolbook reference both contracts are held against: the negacyclic
   convolution, accumulated one multiplier at a time over the running shift
   of the multiplicand, where the coefficient that leaves the top comes back
   at the bottom with its sign changed because X^n is -1. *)
Definition shift_negacyclic (q : Z) (p : list Z) : list Z :=
  match rev p with
  | nil => nil
  | top :: below => submod q 0 top :: rev below
  end.

Fixpoint convolve_go (shift : list Z -> list Z) (q : Z) (a b acc : list Z) : list Z :=
  match a with
  | nil => acc
  | x :: rest => convolve_go shift q rest (shift b) (vadd q acc (vscale q x b))
  end.

Definition negacyclic (q : Z) (n : nat) (a b : list Z) : list Z :=
  convolve_go (shift_negacyclic q) q a b (zero_poly n).

(* The construction the ring's own defining polynomial excludes: the same
   convolution with the wrapped coefficient keeping its sign, which is the
   quotient by X^n - 1 rather than by X^n + 1. It agrees with the negacyclic
   product wherever nothing wraps and differs everywhere else. *)
Definition shift_cyclic (q : Z) (p : list Z) : list Z :=
  match rev p with
  | nil => nil
  | top :: below => addmod q 0 top :: rev below
  end.

Definition cyclic (q : Z) (n : nat) (a b : list Z) : list Z :=
  convolve_go (shift_cyclic q) q a b (zero_poly n).

(* -------------------------------------------------------------------------
   Bytes. A coefficient's bits run from the least significant upward and so
   do a byte's, as required by the FIPS 203 and FIPS 204 byte encodings.
   ------------------------------------------------------------------------- *)

Definition bits_le (d : nat) (x : Z) : list bool :=
  map (Z.testbit x) (indices d).

Fixpoint bits_value (l : list bool) : Z :=
  match l with
  | nil => 0
  | b :: r => (if b then 1 else 0) + 2 * bits_value r
  end.

Definition byte_encode (d : nat) (a : list Z) : list Z :=
  map bits_value (chunk_of (length a * d) 8 (concat (map (bits_le d) a))).

Definition byte_decode (d : nat) (bs : list Z) : list Z :=
  map bits_value (chunk_of (length bs * 8) d (concat (map (bits_le 8) bs))).

(* A counterexample to using roundtrip alone as a conformance criterion:
   most-significant-first packing also has an inverse, but disagrees with
   the standards' prescribed little-endian byte order. *)
Definition bits_be (d : nat) (x : Z) : list bool := rev (bits_le d x).

Definition byte_encode_be (d : nat) (a : list Z) : list Z :=
  map (fun c => bits_value (rev c))
      (chunk_of (length a * d) 8 (concat (map (bits_be d) a))).

Definition byte_decode_be (d : nat) (bs : list Z) : list Z :=
  map (fun c => bits_value (rev c))
      (chunk_of (length bs * 8) d (concat (map (bits_be 8) bs))).

(* An encoder that packs one bit fewer per coefficient, which is the defect a
   width carried at two sites invites: it is the same function at every
   coefficient below 2^(d-1) and loses the rest. *)
Definition byte_encode_short (d : nat) (a : list Z) : list Z :=
  map bits_value (chunk_of (length a * d) 8 (concat (map (bits_le (d - 1)) a))).

Definition encoded_bytes (r : Ring) (d : nat) : nat :=
  Nat.div (ring_degree r * d) 8.

(* -------------------------------------------------------------------------
   Compression, which is ML-KEM's alone and is here because it is arithmetic
   over the same modulus. The quotient rounds to nearest with a tie going
   upward, which is what adding half the divisor before an integer division
   does.
   ------------------------------------------------------------------------- *)

Definition compress (q : Z) (d : nat) (x : Z) : Z :=
  ((two_pow d * x + q / 2) / q) mod two_pow d.

Definition decompress (q : Z) (d : nat) (y : Z) : Z :=
  (q * y + two_pow (d - 1)) / two_pow d.

(* The construction the standard's rounding excludes rather than leaves
   open: a compression that truncates, whose error reaches the full width of
   a step where rounding reaches half of it. *)
Definition compress_truncating (q : Z) (d : nat) (x : Z) : Z :=
  ((two_pow d * x) / q) mod two_pow d.

Definition compress_poly (q : Z) (d : nat) (a : list Z) : list Z :=
  map (compress q d) a.

Definition decompress_poly (q : Z) (d : nat) (a : list Z) : list Z :=
  map (decompress q d) a.

(* The bound the width gives: half a step, rounded up. *)
Definition compression_bound (q : Z) (d : nat) : Z :=
  (q + two_pow (S d) - 1) / two_pow (S d).

Definition compression_error (q : Z) (d : nat) (x : Z) : Z :=
  Z.abs (centred q (decompress q d (compress q d x) - x)).

Definition truncation_error (q : Z) (d : nat) (x : Z) : Z :=
  Z.abs (centred q (decompress q d (compress_truncating q d x) - x)).

(* -------------------------------------------------------------------------
   Probe polynomials. Every check that runs a transform runs it at these and
   at nothing else, so they are pinned by their own contents below rather
   than left as a fixture a weakening survives inside.
   ------------------------------------------------------------------------- *)

Definition unit_poly (n : nat) (i : Z) : list Z :=
  map (fun x => if Z.eqb x i then 1 else 0) (indices n).

Definition ramp_poly (n : nat) : list Z :=
  map (fun x => (x * x + 3 * x + 1) mod 97) (indices n).

Definition stride_poly (n : nat) : list Z :=
  map (fun x => (5 * x + 2) mod 61) (indices n).

Definition alternating_poly (n : nat) : list Z :=
  map (fun x => if Z.eqb (x mod 2) 0 then 7 else 11) (indices n).

Definition probes (n : nat) : list (list Z) :=
  zero_poly n
  :: unit_poly n 0
  :: unit_poly n 1
  :: unit_poly n 2
  :: unit_poly n 128
  :: unit_poly n 255
  :: ramp_poly n
  :: stride_poly n
  :: alternating_poly n
  :: vadd 3329 (ramp_poly n) (stride_poly n)
  :: nil.

Definition round_trips (r : Ring) (a : list Z) : bool :=
  poly_eqb (intt r (ntt r a)) a.


(* -------------------------------------------------------------------------
   The two rings are well formed, which is what makes every statement below
   a statement about them.
   ------------------------------------------------------------------------- *)

Example the_mlkem_ring_is_well_formed : ring_wf mlkem_ring = true.
Proof. vm_compute. reflexivity. Qed.

Example the_mldsa_ring_is_well_formed : ring_wf mldsa_ring = true.
Proof. vm_compute. reflexivity. Qed.

(* And the two are different rings rather than one written twice: the moduli
   differ, the layer counts differ, and the residue rings the transform
   leaves have different degrees. *)
Example the_two_rings_leave_residue_rings_of_different_degree :
  (ring_leaf_degree mlkem_ring, ring_leaf_degree mldsa_ring) = (2, 1).
Proof. vm_compute. reflexivity. Qed.

Example the_two_rings_split_into_different_numbers_of_residues :
  (ring_split mlkem_ring, ring_split mldsa_ring) = (128, 256).
Proof. vm_compute. reflexivity. Qed.

(* A root of the wrong order fails the well-formedness check, which is what
   keeps that check from holding of everything. *)
Definition mlkem_ring_with_a_square_root : Ring :=
  {| ring_degree := 256; ring_layers := 7; ring_modulus := 3329;
     ring_root := 289; ring_inv_scale := 3303 |}.

Example a_root_of_half_the_order_is_refused :
  ring_wf mlkem_ring_with_a_square_root = false.
Proof. vm_compute. reflexivity. Qed.

Definition mlkem_ring_with_a_wrong_inverse_scale : Ring :=
  {| ring_degree := 256; ring_layers := 7; ring_modulus := 3329;
     ring_root := 17; ring_inv_scale := 3304 |}.

Example a_scaling_that_does_not_invert_the_layer_count_is_refused :
  ring_wf mlkem_ring_with_a_wrong_inverse_scale = false.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The butterfly, over an arbitrary modulus, an arbitrary root and arbitrary
   coefficients. This is the algebra the whole transform is L layers of, and
   it is the one statement here that is not a conversion at chosen inputs.
   ------------------------------------------------------------------------- *)

Lemma the_butterfly_sum_recovers_twice_the_low_half :
  forall q nu a0 a1 : Z,
    addmod q (addmod q a0 (mulmod q nu a1)) (submod q a0 (mulmod q nu a1))
    = (2 * a0) mod q.
Proof.
  intros q nu a0 a1. unfold addmod, submod, mulmod.
  rewrite <- Zplus_mod.
  replace (a0 + (nu * a1) mod q + (a0 - (nu * a1) mod q)) with (2 * a0) by ring.
  reflexivity.
Qed.

Lemma the_butterfly_difference_recovers_twice_the_scaled_high_half :
  forall q nu a0 a1 : Z,
    submod q (addmod q a0 (mulmod q nu a1)) (submod q a0 (mulmod q nu a1))
    = (2 * (nu * a1)) mod q.
Proof.
  intros q nu a0 a1. unfold addmod, submod, mulmod.
  rewrite <- Zminus_mod.
  replace (a0 + (nu * a1) mod q - (a0 - (nu * a1) mod q))
    with (2 * ((nu * a1) mod q)) by ring.
  rewrite Zmult_mod_idemp_r. reflexivity.
Qed.

(*| discharges: R-05-165 |*)
Theorem the_butterfly_is_invertible_at_an_arbitrary_root :
  forall q nu nuinv a0 a1 : Z,
    (nu * nuinv) mod q = 1 mod q ->
    mulmod q nuinv
      (submod q (addmod q a0 (mulmod q nu a1)) (submod q a0 (mulmod q nu a1)))
    = (2 * a1) mod q.
Proof.
  intros q nu nuinv a0 a1 H.
  rewrite the_butterfly_difference_recovers_twice_the_scaled_high_half.
  unfold mulmod.
  rewrite Zmult_mod_idemp_r.
  replace (nuinv * (2 * (nu * a1))) with (nu * nuinv * (2 * a1)) by ring.
  rewrite Zmult_mod. rewrite H. rewrite <- Zmult_mod.
  replace (1 * (2 * a1)) with (2 * a1) by ring.
  reflexivity.
Qed.

(* General list-level inverse theorems and ring instantiations are proved
   below. The following finite examples remain executable regressions. *)


(* -------------------------------------------------------------------------
   The transform round trips, at both rings, at every probe.
   ------------------------------------------------------------------------- *)

Example the_transform_round_trips_at_the_mlkem_ring :
  forallb (round_trips mlkem_ring) (probes (ring_degree mlkem_ring)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_transform_round_trips_at_the_mldsa_ring :
  forallb (round_trips mldsa_ring) (probes (ring_degree mldsa_ring)) = true.
Proof. vm_compute. reflexivity. Qed.

(* The probes are pinned by their own contents and their order, so a
   weakening inside one of them moves a statement here rather than leaving a
   round trip that still holds of a different polynomial. *)
Example the_probe_polynomials_are_these :
  map (digest_of 3329) (probes 256)
  = 2970 :: 631 :: 3300 :: 3080 :: 939 :: 2971 :: 527 :: 2244 :: 1530 :: 3130 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example there_are_ten_probe_polynomials_of_the_full_degree :
  (length (probes 256),
   forallb (fun p => Nat.eqb (length p) 256) (probes 256)) = (10%nat, true).
Proof. vm_compute. reflexivity. Qed.

(* An inverse with no final scaling is not an inverse: it returns 2^L times
   the input, which is the input only where the input is zero. *)
Definition intt_without_the_final_scale (r : Ring) (a : list Z) : list Z :=
  intt_go (ring_modulus r) (ring_root r) (ring_split r) (ring_layers r)
          (ring_top_exponent r) a.

Example an_inverse_with_no_final_scaling_is_not_an_inverse :
  poly_eqb (intt_without_the_final_scale mlkem_ring
              (ntt mlkem_ring (ramp_poly 256))) (ramp_poly 256) = false.
Proof. vm_compute. reflexivity. Qed.

(* And it is exactly the scaling it is missing, which is what holds it to the
   single difference it exists to exhibit. *)
Example the_missing_scaling_is_the_layer_count :
  poly_eqb (vscale 3329 (ring_split mlkem_ring) (ramp_poly 256))
           (intt_without_the_final_scale mlkem_ring
              (ntt mlkem_ring (ramp_poly 256))) = true.
Proof. vm_compute. reflexivity. Qed.

(* An inverse using the forward root at each layer instead of its inverse. It
   is the same recursion, the same scaling and the same splits. *)
Fixpoint intt_go_forward_root (q psi split : Z) (layers : nat) (e : Z) (a : list Z) : list Z :=
  match layers with
  | O => a
  | S k =>
      let m := Nat.div (length a) 2 in
      let half := e / 2 in
      let b0 := intt_go_forward_root q psi split k half (firstn m a) in
      let b1 := intt_go_forward_root q psi split k (half + split) (skipn m a) in
      vadd q b0 b1 ++ vscale q (pow_mod q psi half) (vsub q b0 b1)
  end.

Definition intt_forward_root (r : Ring) (a : list Z) : list Z :=
  vscale (ring_modulus r) (ring_inv_scale r)
         (intt_go_forward_root (ring_modulus r) (ring_root r) (ring_split r)
                               (ring_layers r) (ring_top_exponent r) a).

Example an_inverse_using_the_forward_root_is_not_an_inverse :
  poly_eqb (intt_forward_root mlkem_ring (ntt mlkem_ring (ramp_poly 256)))
           (ramp_poly 256) = false.
Proof. vm_compute. reflexivity. Qed.

(* It agrees with the inverse wherever the root is its own inverse, which is
   the first layer's exponent alone at the top of the recursion; what
   separates them is every layer below it. *)
Example the_forward_root_inverse_agrees_at_the_zero_polynomial :
  poly_eqb (intt_forward_root mlkem_ring (ntt mlkem_ring (zero_poly 256)))
           (zero_poly 256) = true.
Proof. vm_compute. reflexivity. Qed.

(* A transform whose two children both add, which is the defect a butterfly
   written once and reused invites. *)
Fixpoint ntt_go_both_children_add (q psi split : Z) (layers : nat) (e : Z) (a : list Z) : list Z :=
  match layers with
  | O => a
  | S k =>
      let m := Nat.div (length a) 2 in
      let half := e / 2 in
      let t := vscale q (pow_mod q psi half) (skipn m a) in
      ntt_go_both_children_add q psi split k half (vadd q (firstn m a) t)
        ++ ntt_go_both_children_add q psi split k (half + split)
             (vadd q (firstn m a) t)
  end.

Definition ntt_both_children_add (r : Ring) (a : list Z) : list Z :=
  ntt_go_both_children_add (ring_modulus r) (ring_root r) (ring_split r)
                           (ring_layers r) (ring_top_exponent r) a.

Example a_transform_whose_children_both_add_is_not_invertible :
  poly_eqb (intt mlkem_ring (ntt_both_children_add mlkem_ring (ramp_poly 256)))
           (ramp_poly 256) = false.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The order the residues come out in, both arms, and neither is a refuted
   construction. The recursion above emits the child of exponent e/2 before
   the child of exponent e/2 + 2^L; a recursion that emits them the other way
   round is the same algebra at a different coefficient order, it round trips
   against its own inverse, and it computes the same product against its own
   leaf roots. So every check in this file holds of both, and which one a
   peer reads is decided by the standard's own text and by nothing here.
   ------------------------------------------------------------------------- *)

Fixpoint ntt_go_other_order (q psi split : Z) (layers : nat) (e : Z) (a : list Z) : list Z :=
  match layers with
  | O => a
  | S k =>
      let m := Nat.div (length a) 2 in
      let half := e / 2 in
      let t := vscale q (pow_mod q psi half) (skipn m a) in
      ntt_go_other_order q psi split k (half + split) (vsub q (firstn m a) t)
        ++ ntt_go_other_order q psi split k half (vadd q (firstn m a) t)
  end.

Fixpoint intt_go_other_order (q psi split : Z) (layers : nat) (e : Z) (a : list Z) : list Z :=
  match layers with
  | O => a
  | S k =>
      let m := Nat.div (length a) 2 in
      let half := e / 2 in
      let b1 := intt_go_other_order q psi split k (half + split) (firstn m a) in
      let b0 := intt_go_other_order q psi split k half (skipn m a) in
      vadd q b0 b1
        ++ vscale q (pow_mod q psi (2 * split - half)) (vsub q b0 b1)
  end.

Fixpoint leaf_exponents_other_order (split : Z) (layers : nat) (e : Z) : list Z :=
  match layers with
  | O => e :: nil
  | S k => leaf_exponents_other_order split k (e / 2 + split)
             ++ leaf_exponents_other_order split k (e / 2)
  end.

Definition ntt_other_order (r : Ring) (a : list Z) : list Z :=
  ntt_go_other_order (ring_modulus r) (ring_root r) (ring_split r)
                     (ring_layers r) (ring_top_exponent r) a.

Definition intt_other_order (r : Ring) (a : list Z) : list Z :=
  vscale (ring_modulus r) (ring_inv_scale r)
         (intt_go_other_order (ring_modulus r) (ring_root r) (ring_split r)
                              (ring_layers r) (ring_top_exponent r) a).

Definition leaf_roots_other_order (r : Ring) : list Z :=
  map (pow_mod (ring_modulus r) (ring_root r))
      (leaf_exponents_other_order (ring_split r) (ring_layers r)
                                  (ring_top_exponent r)).

Definition mul_ntt_quadratic_other_order (r : Ring) (a b : list Z) : list Z :=
  basemul_quadratic (ring_modulus r) (leaf_roots_other_order r) a b.

Example the_other_residue_order_round_trips_too :
  forallb (fun a => poly_eqb (intt_other_order mlkem_ring
                                (ntt_other_order mlkem_ring a)) a)
          (probes 256) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_other_residue_order_computes_the_same_product :
  poly_eqb (intt_other_order mlkem_ring
              (mul_ntt_quadratic_other_order mlkem_ring
                 (ntt_other_order mlkem_ring (ramp_poly 256))
                 (ntt_other_order mlkem_ring (stride_poly 256))))
           (negacyclic 3329 256 (ramp_poly 256) (stride_poly 256)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_two_residue_orders_are_different_transforms :
  poly_eqb (ntt mlkem_ring (ramp_poly 256))
           (ntt_other_order mlkem_ring (ramp_poly 256)) = false.
Proof. vm_compute. reflexivity. Qed.

(* And mixing them is wrong, which is what makes the order a contract between
   two implementations rather than a presentation detail: this file's leaf
   roots against the other order's transform compute neither product. *)
Example one_order_s_leaf_roots_against_the_other_order_s_transform_is_wrong :
  poly_eqb (intt_other_order mlkem_ring
              (mul_ntt_quadratic mlkem_ring
                 (ntt_other_order mlkem_ring (ramp_poly 256))
                 (ntt_other_order mlkem_ring (stride_poly 256))))
           (negacyclic 3329 256 (ramp_poly 256) (stride_poly 256)) = false.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The two multiplication contracts, which is the whole of what the two
   schemes must not share. At ML-KEM's ring the quadratic base case is the
   product and the coefficientwise one is not; at ML-DSA's ring the
   coefficientwise one is the product and the quadratic one is not even
   applicable, its leaf roots being one per coefficient pair where the
   transform left one per coefficient.
   ------------------------------------------------------------------------- *)

(* The four answers sit in one statement rather than in four, because what
   they say is one thing: each ring's own contract reproduces the schoolbook
   product and the other ring's contract does not, in both directions. A
   reader who takes only the two positive answers has read half of it. *)
(*| discharges: R-05-058a |*)
Example the_two_rings_multiply_under_two_different_contracts :
  let f := ramp_poly 256 in
  let g := stride_poly 256 in
  let kem_product := negacyclic 3329 256 f g in
  let dsa_product := negacyclic 8380417 256 f g in
  (poly_eqb (intt mlkem_ring (mul_ntt_quadratic mlkem_ring
                                (ntt mlkem_ring f) (ntt mlkem_ring g)))
            kem_product,
   poly_eqb (intt mlkem_ring (mul_ntt_pointwise mlkem_ring
                                (ntt mlkem_ring f) (ntt mlkem_ring g)))
            kem_product,
   poly_eqb (intt mldsa_ring (mul_ntt_pointwise mldsa_ring
                                (ntt mldsa_ring f) (ntt mldsa_ring g)))
            dsa_product,
   poly_eqb (intt mldsa_ring (mul_ntt_quadratic mldsa_ring
                                (ntt mldsa_ring f) (ntt mldsa_ring g)))
            dsa_product)
  = (true, false, true, false).
Proof. vm_compute. reflexivity. Qed.

(* Each ring has one leaf root per residue ring, and that count is what
   decides which contract applies. *)
Example each_ring_has_one_leaf_root_per_residue_ring :
  (length (leaf_roots mlkem_ring), length (leaf_roots mldsa_ring))
  = (128%nat, 256%nat).
Proof. vm_compute. reflexivity. Qed.

(* Every leaf root is of odd exponent, which is what makes a leaf's modulus
   irreducible over the residues above it and the split stop where it does. *)
Example every_leaf_exponent_is_odd :
  forallb (fun e => Z.eqb (e mod 2) 1)
          (leaf_exponents (ring_split mlkem_ring) (ring_layers mlkem_ring)
                          (ring_top_exponent mlkem_ring)) = true.
Proof. vm_compute. reflexivity. Qed.

(* The defining polynomial is X^n + 1 and not X^n - 1, which the transform
   decides: the cyclic convolution is a different product and the transform
   computes neither of it. *)
Example the_ring_is_negacyclic_and_the_transform_computes_that_product :
  let f := ramp_poly 256 in
  let g := stride_poly 256 in
  let wrapped := cyclic 3329 256 f g in
  (poly_eqb (negacyclic 3329 256 f g) wrapped,
   poly_eqb (intt mlkem_ring (mul_ntt_quadratic mlkem_ring
                                (ntt mlkem_ring f) (ntt mlkem_ring g)))
            wrapped)
  = (false, false).
Proof. vm_compute. reflexivity. Qed.

(* And the two products agree wherever nothing wraps, which holds the cyclic
   construction to the single difference it exists to exhibit: at two
   polynomials supported below half the degree the wrapped terms are all
   zero. *)
Example the_two_convolutions_agree_where_nothing_wraps :
  poly_eqb (negacyclic 3329 8 (1 :: 2 :: 3 :: 0 :: 0 :: 0 :: 0 :: 0 :: nil)
                              (4 :: 5 :: 0 :: 0 :: 0 :: 0 :: 0 :: 0 :: nil))
           (cyclic 3329 8 (1 :: 2 :: 3 :: 0 :: 0 :: 0 :: 0 :: 0 :: nil)
                          (4 :: 5 :: 0 :: 0 :: 0 :: 0 :: 0 :: 0 :: nil)) = true.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   Bytes. The round trip holds at every width either scheme packs at, and it
   holds of the most-significant-first arm too, which is why it decides
   nothing about which arm a peer speaks.
   ------------------------------------------------------------------------- *)

Definition packing_widths : list nat :=
  (1 :: 4 :: 5 :: 6 :: 10 :: 11 :: 12 :: 13 :: nil)%nat.

Definition encodes_and_decodes (d : nat) (a : list Z) : bool :=
  poly_eqb (byte_decode d (byte_encode d a)) a.

Definition bounded_poly (d : nat) (a : list Z) : list Z :=
  map (fun x => x mod two_pow d) a.

Example packing_and_unpacking_are_inverse_at_every_width :
  forallb (fun d => encodes_and_decodes d (bounded_poly d (ramp_poly 256)))
          packing_widths = true.
Proof. vm_compute. reflexivity. Qed.

Example the_packed_length_is_the_width_times_the_degree_over_eight :
  map (fun d => length (byte_encode d (bounded_poly d (ramp_poly 256))))
      packing_widths
  = map (encoded_bytes mlkem_ring) packing_widths.
Proof. vm_compute. reflexivity. Qed.

(* An encoder one bit narrow round trips against nothing: its own decoder at
   the declared width reads the fields back misaligned. *)
Example an_encoder_one_bit_narrow_is_refused :
  poly_eqb (byte_decode 12 (byte_encode_short 12 (bounded_poly 12 (ramp_poly 256))))
           (bounded_poly 12 (ramp_poly 256)) = false.
Proof. vm_compute. reflexivity. Qed.

(* And it is the top bit it drops, which is what holds it to that single
   difference: at coefficients below half the width the two encoders would
   pack the same field values, and they still disagree because the fields
   are laid at different offsets. *)
Example the_narrow_encoder_packs_fewer_bytes :
  (length (byte_encode 12 (bounded_poly 12 (ramp_poly 256))),
   length (byte_encode_short 12 (bounded_poly 12 (ramp_poly 256))))
  = (384%nat, 352%nat).
Proof. vm_compute. reflexivity. Qed.

(* The other bit order round trips exactly as well, which is the whole of why
   no check here decides between them. *)
Example the_other_bit_order_round_trips_too :
  forallb (fun d => poly_eqb (byte_decode_be d
                                (byte_encode_be d (bounded_poly d (ramp_poly 256))))
                             (bounded_poly d (ramp_poly 256)))
          packing_widths = true.
Proof. vm_compute. reflexivity. Qed.

(* And the two arms produce different bytes, so the choice is observable on
   the wire and unobservable in this file. *)
Example the_two_bit_orders_produce_different_bytes :
  poly_eqb (byte_encode 12 (bounded_poly 12 (ramp_poly 256)))
           (byte_encode_be 12 (bounded_poly 12 (ramp_poly 256))) = false.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   Compression. The error is inside half a step at every input and at every
   width either scheme's ciphertext uses, which is the fact ML-KEM's
   decryption correctness is read against; truncation is outside it.
   ------------------------------------------------------------------------- *)

Definition compression_widths : list nat := (1 :: 4 :: 5 :: 10 :: 11 :: nil)%nat.

Definition residues (q : Z) : list Z := z_range (Z.to_nat q) 0.

(*| discharges: R-05-058a |*)
Example compression_error_is_inside_half_a_step_at_every_residue :
  forallb (fun d => forallb (fun x => Z.leb (compression_error 3329 d x)
                                            (compression_bound 3329 d))
                            (residues 3329))
          compression_widths = true.
Proof. vm_compute. reflexivity. Qed.

Example a_truncating_compression_leaves_the_bound :
  forallb (fun x => Z.leb (truncation_error 3329 11 x)
                          (compression_bound 3329 11))
          (residues 3329) = false.
Proof. vm_compute. reflexivity. Qed.

(* And truncation agrees with rounding at most residues and not at all of
   them, which is what makes it the weakening it is rather than a different
   function: the count below is strictly between none and every one. *)
Definition truncation_agreement (q : Z) (d : nat) : Z :=
  Z.of_nat (length (filter (fun x => Z.eqb (compress_truncating q d x)
                                           (compress q d x))
                           (residues q))).

Example truncation_agrees_at_most_residues_and_not_at_all_of_them :
  forallb (fun d => andb (Z.ltb 0 (truncation_agreement 3329 d))
                         (Z.ltb (truncation_agreement 3329 d) 3329))
          compression_widths = true.
Proof. vm_compute. reflexivity. Qed.

(* The one-bit compression is the message encoding, and what it decides is
   the sign of the centred representative against a quarter of the modulus.
   That is the clause ML-KEM's decryption correctness turns on, so it is
   stated of every residue rather than of a chosen one. *)
Example one_bit_compression_is_the_quarter_modulus_test :
  forallb (fun x => Z.eqb (compress 3329 1 x)
                          (if Z.leb (Z.abs (centred 3329 x)) 832 then 0 else 1))
          (residues 3329) = true.
Proof. vm_compute. reflexivity. Qed.

Example decompressing_one_bit_gives_zero_or_half_the_modulus :
  (decompress 3329 1 0, decompress 3329 1 1) = (0, 1665).
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The centred representative and the infinity norm, which is how ML-DSA's
   bounds are read. Stated of every residue at ML-KEM's modulus, which is
   small enough to enumerate, and of the interval's own ends at ML-DSA's.
   ------------------------------------------------------------------------- *)

Example the_centred_representative_is_symmetric_about_zero :
  forallb (fun x => Z.leb (2 * Z.abs (centred 3329 x)) 3328) (residues 3329) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_centred_representative_agrees_with_its_residue :
  forallb (fun x => Z.eqb ((centred 3329 x) mod 3329) x) (residues 3329) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_centred_representative_at_the_mldsa_interval_ends :
  (centred 8380417 0, centred 8380417 4190208, centred 8380417 4190209,
   centred 8380417 8380416)
  = (0, 4190208, -4190208, -1).
Proof. vm_compute. reflexivity. Qed.

Example the_infinity_norm_reads_the_largest_centred_magnitude :
  norm_inf 8380417 (0 :: 5 :: 8380416 :: 4190208 :: nil) = 4190208.
Proof. vm_compute. reflexivity. Qed.

Example the_infinity_norm_of_a_zero_polynomial_is_zero :
  norm_inf 8380417 (zero_poly 256) = 0.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The decisions a reader would otherwise take on trust because nothing above
   reaches them: the out-of-range coefficient, the comparison's short-list
   arms, the exponentiation's own edges, and the widths the checks are run
   at. Each is pinned here rather than left to a default no computation
   visits, a fixture nothing reaches being a site a seeded weakening survives
   at rather than a site nothing can go wrong in.
   ------------------------------------------------------------------------- *)

Example a_coefficient_off_the_end_of_a_polynomial_is_zero :
  coeff nil 0 = 0.
Proof. reflexivity. Qed.

Example a_polynomial_is_not_equal_to_a_shorter_one :
  poly_eqb (1 :: nil) nil = false.
Proof. reflexivity. Qed.

Example a_polynomial_is_not_equal_to_a_longer_one :
  poly_eqb nil (1 :: nil) = false.
Proof. reflexivity. Qed.

Example the_empty_exponent_is_one : pow_mod 3329 17 0 = 1.
Proof. vm_compute. reflexivity. Qed.

Example the_first_power_is_the_base : pow_mod 3329 17 1 = 17.
Proof. vm_compute. reflexivity. Qed.

Example squaring_and_multiplying_agrees_with_repeated_multiplication :
  map (pow_mod 3329 17) (0 :: 1 :: 2 :: 3 :: 4 :: 5 :: nil)
  = 1 :: 17 :: 289 :: 1584 :: 296 :: 1703 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_root_has_order_exactly_twice_the_split :
  (pow_mod 3329 17 (ring_order mlkem_ring), pow_mod 8380417 1753 (ring_order mldsa_ring))
  = (1, 1).
Proof. vm_compute. reflexivity. Qed.

Example a_chunking_of_an_empty_string_is_empty :
  chunk_of 8 8 (nil : list bool) = nil.
Proof. reflexivity. Qed.

Example a_bit_string_shorter_than_its_chunk_is_one_short_chunk :
  chunk_of 8 8 (true :: nil) = (true :: nil) :: nil.
Proof. reflexivity. Qed.

Example the_power_of_two_is_the_width :
  map two_pow ((0 :: 1 :: 8 :: 12 :: nil)%nat) = 1 :: 2 :: 256 :: 4096 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_widths_the_checks_run_at :
  (packing_widths, compression_widths)
  = ((1 :: 4 :: 5 :: 6 :: 10 :: 11 :: 12 :: 13 :: nil)%nat,
     (1 :: 4 :: 5 :: 10 :: 11 :: nil)%nat).
Proof. vm_compute. reflexivity. Qed.

Example the_negacyclic_shift_moves_the_top_coefficient_down_with_its_sign :
  (shift_negacyclic 3329 (1 :: 2 :: 3 :: nil),
   shift_cyclic 3329 (1 :: 2 :: 3 :: nil))
  = (3326 :: 1 :: 2 :: nil, 3 :: 1 :: 2 :: nil).
Proof. vm_compute. reflexivity. Qed.

Example the_compression_bounds_at_those_widths :
  map (compression_bound 3329) compression_widths
  = 833 :: 105 :: 53 :: 2 :: 1 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_negation_of_zero_is_zero : vneg 3329 (0 :: nil) = 0 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example a_vector_norm_reads_the_largest_of_its_polynomials :
  norm_inf_vec 8380417 ((0 :: 5 :: nil) :: (8380416 :: 9 :: nil) :: nil) = 9.
Proof. vm_compute. reflexivity. Qed.

Example the_residue_enumeration_is_the_whole_modulus :
  length (residues 3329) = 3329%nat.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   R-05-166's decidable half: the one record this file's statements range
   over, inhabited by a closed definition ascribed at it.
   ------------------------------------------------------------------------- *)

Definition witness_Ring : Ring := mlkem_ring.

(* General inversion. The finite certificate checks only roots, never an
   input polynomial. The theorem below quantifies over every coefficient. *)
Fixpoint inverse_roots (q psi split : Z) (layers : nat) (e : Z) : bool :=
  match layers with
  | O => true
  | S k =>
      Z.eqb (mulmod q (pow_mod q psi (e / 2))
                       (pow_mod q psi (2 * split - e / 2))) (1 mod q)
      && inverse_roots q psi split k (e / 2)
      && inverse_roots q psi split k (e / 2 + split)
  end.

Definition reduced_poly (q : Z) (a : list Z) : Prop :=
  Forall (fun x => x mod q = x) a.

Lemma vscale_length : forall q c a, length (vscale q c a) = length a.
Proof. intros. unfold vscale. apply map_length. Qed.

Lemma vadd_length : forall q a b, length a = length b ->
  length (vadd q a b) = length a.
Proof.
  intros q a b H. unfold vadd. rewrite map_length, combine_length, H.
  apply Nat.min_id.
Qed.

Lemma vsub_length : forall q a b, length a = length b ->
  length (vsub q a b) = length a.
Proof.
  intros q a b H. unfold vsub. rewrite map_length, combine_length, H.
  apply Nat.min_id.
Qed.

Lemma vadd_reduced : forall q a b, reduced_poly q (vadd q a b).
Proof.
  intros. unfold reduced_poly, vadd. apply Forall_forall.
  intros x H. apply in_map_iff in H. destruct H as [[u v] [<- H]].
  simpl. unfold addmod. apply Zmod_mod.
Qed.

Lemma vsub_reduced : forall q a b, reduced_poly q (vsub q a b).
Proof.
  intros. unfold reduced_poly, vsub. apply Forall_forall.
  intros x H. apply in_map_iff in H. destruct H as [[u v] [<- H]].
  simpl. unfold submod. apply Zmod_mod.
Qed.

Lemma vscale_one : forall q a, reduced_poly q a -> vscale q 1 a = a.
Proof.
  intros q a H. unfold vscale. induction H; simpl; auto.
  f_equal; auto. unfold mulmod. rewrite Z.mul_1_l. exact H.
Qed.

Lemma scaled_butterfly_low : forall q c nu a b,
  length a = length b ->
  vadd q (vscale q c (vadd q a (vscale q nu b)))
         (vscale q c (vsub q a (vscale q nu b))) = vscale q (2*c) a.
Proof.
  intros q c nu a. induction a as [|a ar IH]; intros [|b br] H;
    simpl in H; try discriminate; [reflexivity|].
  unfold vadd, vsub, vscale in *. cbn [map combine fst snd].
  f_equal; [|apply IH; lia]. unfold addmod, submod, mulmod.
  repeat rewrite Zmult_mod_idemp_r. rewrite <- Zplus_mod.
  f_equal. ring.
Qed.

Lemma scaled_butterfly_high : forall q c nu nui a b,
  (nu * nui) mod q = 1 mod q -> length a = length b ->
  vscale q nui
    (vsub q (vscale q c (vadd q a (vscale q nu b)))
            (vscale q c (vsub q a (vscale q nu b)))) = vscale q (2*c) b.
Proof.
  intros q c nu nui a. induction a as [|a ar IH]; intros [|b br] Hu H;
    simpl in H; try discriminate; [reflexivity|].
  unfold vadd, vsub, vscale in *. cbn [map combine fst snd].
  f_equal; [|apply IH; [exact Hu|lia]]. unfold addmod, submod, mulmod.
  rewrite <- Zminus_mod. repeat rewrite Zmult_mod_idemp_r.
  rewrite Z.mul_sub_distr_l, Zminus_mod.
  repeat rewrite Z.mul_assoc. repeat rewrite Zmult_mod_idemp_r.
  rewrite <- Zminus_mod.
  replace (nui * c * (a + (nu * b) mod q) - nui * c * (a - (nu * b) mod q))
    with ((2*c*nui) * ((nu*b) mod q)) by ring.
  rewrite Zmult_mod_idemp_r.
  replace (2*c*nui*(nu*b)) with ((nu*nui)*(2*c*b)) by ring.
  rewrite Zmult_mod, Hu, <- Zmult_mod, Z.mul_1_l. reflexivity.
Qed.

Lemma ntt_length_general : forall q psi split layers e a leaf,
  length a = (2 ^ layers * leaf)%nat ->
  length (ntt_go q psi split layers e a) = length a.
Proof.
  intros q psi split layers. induction layers as [|k IH]; intros e a leaf H;
    [reflexivity|].
  assert (Hm : (length a / 2 = 2 ^ k * leaf)%nat).
  { rewrite H, Nat.pow_succ_r'.
    replace (2 * 2 ^ k * leaf)%nat with ((2 ^ k * leaf) * 2)%nat by nia.
    apply Nat.div_mul. lia. }
  assert (Hlo : length (firstn (length a / 2) a) = (2 ^ k * leaf)%nat).
  { rewrite firstn_length, Hm. apply Nat.min_l. simpl in H. lia. }
  assert (Hhi : length (skipn (length a / 2) a) = (2 ^ k * leaf)%nat).
  { rewrite skipn_length, Hm. simpl in H. lia. }
  cbn [ntt_go]. rewrite app_length.
  rewrite (IH _ _ leaf), (IH _ _ leaf).
  - rewrite vadd_length, vsub_length, Hlo; try (rewrite vscale_length, Hlo, Hhi; reflexivity).
    simpl in H. lia.
  - rewrite vsub_length, Hlo; [reflexivity|rewrite vscale_length, Hlo, Hhi; reflexivity].
  - rewrite vadd_length, Hlo; [reflexivity|rewrite vscale_length, Hlo, Hhi; reflexivity].
Qed.

Local Opaque pow_mod.

Theorem ntt_inverse_unscaled : forall q psi split layers e a leaf,
  length a = (2 ^ layers * leaf)%nat -> reduced_poly q a ->
  inverse_roots q psi split layers e = true ->
  intt_go q psi split layers e (ntt_go q psi split layers e a)
    = vscale q (2 ^ Z.of_nat layers) a.
Proof.
  intros q psi split layers. induction layers as [|k IH]; intros e a leaf H Hr Hu.
  - simpl. symmetry. apply vscale_one. exact Hr.
  - cbn [inverse_roots] in Hu. apply andb_prop in Hu.
    destruct Hu as [Hu Hh]. apply andb_prop in Hu.
    destruct Hu as [Hu Hl]. apply Z.eqb_eq in Hu.
    assert (Hm : (length a / 2 = 2 ^ k * leaf)%nat).
    { rewrite H, Nat.pow_succ_r'.
      replace (2 * 2 ^ k * leaf)%nat with ((2 ^ k * leaf) * 2)%nat by nia.
      apply Nat.div_mul. lia. }
    set (lo := firstn (length a / 2) a).
    set (hi := skipn (length a / 2) a).
    assert (Hlo : length lo = (2 ^ k * leaf)%nat).
    { unfold lo. rewrite firstn_length, Hm. apply Nat.min_l. simpl in H. lia. }
    assert (Hhi : length hi = (2 ^ k * leaf)%nat).
    { unfold hi. rewrite skipn_length, Hm. simpl in H. lia. }
    set (t := vscale q (pow_mod q psi (e/2)) hi).
    assert (Ht : length t = length lo) by (unfold t; rewrite vscale_length, Hlo, Hhi; reflexivity).
    assert (Ha : length (vadd q lo t) = (2 ^ k * leaf)%nat)
      by (rewrite vadd_length, Hlo; congruence).
    assert (Hb : length (vsub q lo t) = (2 ^ k * leaf)%nat)
      by (rewrite vsub_length, Hlo; congruence).
    cbn [ntt_go]. fold lo hi t.
    cbn [intt_go].
    rewrite app_length, (ntt_length_general q psi split k _ _ leaf Ha),
      (ntt_length_general q psi split k _ _ leaf Hb), Ha, Hb.
    replace ((2 ^ k * leaf + 2 ^ k * leaf) / 2)%nat with (2 ^ k * leaf)%nat
      by (replace (2 ^ k * leaf + 2 ^ k * leaf)%nat with ((2 ^ k * leaf)*2)%nat by lia;
          rewrite Nat.div_mul; lia).
    rewrite <- Ha, <- (ntt_length_general q psi split k (e/2) _ leaf Ha).
    rewrite firstn_app, firstn_all, Nat.sub_diag. cbn [firstn].
    rewrite app_nil_r, skipn_app, skipn_all, Nat.sub_diag. cbn [skipn app].
    rewrite (IH _ _ leaf Ha (vadd_reduced q lo t) Hl),
      (IH _ _ leaf Hb (vsub_reduced q lo t) Hh).
    unfold t.
    rewrite (scaled_butterfly_low q (2 ^ Z.of_nat k) (pow_mod q psi (e/2)) lo hi
      (eq_trans Hlo (eq_sym Hhi))).
    rewrite (scaled_butterfly_high q (2 ^ Z.of_nat k) (pow_mod q psi (e/2))
      (pow_mod q psi (2*split-e/2)) lo hi Hu (eq_trans Hlo (eq_sym Hhi))).
    unfold lo, hi. unfold vscale. rewrite <- map_app, firstn_skipn.
    rewrite Nat2Z.inj_succ, Z.pow_succ_r; [reflexivity|lia].
Qed.

Local Transparent pow_mod.

Lemma vscale_compose : forall q u v a,
  vscale q u (vscale q v a) = vscale q (u*v) a.
Proof.
  intros q u v a. induction a; unfold vscale in *; cbn [map].
  - reflexivity.
  - rewrite IHa. f_equal. unfold mulmod.
    rewrite Zmult_mod_idemp_r, Z.mul_assoc. reflexivity.
Qed.

Lemma vscale_unit : forall q c a,
  c mod q = 1 mod q -> reduced_poly q a -> vscale q c a = a.
Proof.
  intros q c a Hc Ha. unfold vscale. induction Ha; cbn [map]; auto.
  rewrite IHHa. f_equal. unfold mulmod.
  rewrite Zmult_mod, Hc, <- Zmult_mod, Z.mul_1_l. exact H.
Qed.

Theorem ntt_roundtrip_general : forall r a leaf,
  length a = (2 ^ ring_layers r * leaf)%nat ->
  reduced_poly (ring_modulus r) a ->
  inverse_roots (ring_modulus r) (ring_root r) (ring_split r)
                (ring_layers r) (ring_split r) = true ->
  (ring_inv_scale r * 2 ^ Z.of_nat (ring_layers r)) mod ring_modulus r
    = 1 mod ring_modulus r ->
  intt r (ntt r a) = a.
Proof.
  intros r a leaf H Hr Hu Hs. unfold intt, ntt, ring_top_exponent.
  rewrite (ntt_inverse_unscaled _ _ _ _ _ _ leaf H Hr Hu), vscale_compose.
  apply vscale_unit; assumption.
Qed.

Example both_selected_rings_have_inverse_roots :
  inverse_roots 3329 17 128 7 128 = true /\
  inverse_roots 8380417 1753 256 8 256 = true.
Proof. vm_compute. split; reflexivity. Qed.

Theorem mlkem_ntt_roundtrip : forall a,
  length a = 256%nat -> reduced_poly 3329 a ->
  intt mlkem_ring (ntt mlkem_ring a) = a.
Proof.
  intros a H Hr. apply (ntt_roundtrip_general mlkem_ring a 2).
  - exact H.
  - exact Hr.
  - exact (proj1 both_selected_rings_have_inverse_roots).
  - vm_compute. reflexivity.
Qed.

Theorem mldsa_ntt_roundtrip : forall a,
  length a = 256%nat -> reduced_poly 8380417 a ->
  intt mldsa_ring (ntt mldsa_ring a) = a.
Proof.
  intros a H Hr. apply (ntt_roundtrip_general mldsa_ring a 1).
  - exact H.
  - exact Hr.
  - exact (proj2 both_selected_rings_have_inverse_roots).
  - vm_compute. reflexivity.
Qed.

(* General bit and chunk codec laws. Encoding width and whole-byte alignment
   are explicit; out-of-domain integers are not silently called canonical. *)
Lemma bit_range_div2 : forall n x start,
  0 <= start ->
  map (Z.testbit x) (z_range n (start + 1)) =
  map (Z.testbit (x/2)) (z_range n start).
Proof.
  induction n; intros x start H; cbn [z_range map]; [reflexivity|].
  f_equal.
  - replace (start+1) with (Z.succ start) by lia.
    symmetry. apply Z.div2_bits. exact H.
  - apply IHn. lia.
Qed.

Lemma bits_le_succ : forall n x,
  bits_le (S n) x = Z.testbit x 0 :: bits_le n (x/2).
Proof.
  intros. unfold bits_le, indices. cbn [z_range map]. f_equal.
  change (map (Z.testbit x) (z_range n (0+1)) = map (Z.testbit (x/2)) (z_range n 0)).
  apply bit_range_div2. lia.
Qed.

Lemma bits_value_bound : forall bs,
  0 <= bits_value bs < 2 ^ Z.of_nat (length bs).
Proof.
  induction bs as [|b bs IH]; cbn [bits_value length].
  - lia.
  - rewrite Nat2Z.inj_succ, Z.pow_succ_r by lia.
    destruct b; nia.
Qed.

Theorem bits_value_of_bits_le : forall n x,
  0 <= x < 2 ^ Z.of_nat n -> bits_value (bits_le n x) = x.
Proof.
  induction n; intros x H.
  - cbn in H. assert (x=0) by lia. subst. reflexivity.
  - rewrite bits_le_succ. cbn [bits_value]. rewrite IHn.
    + replace (if Z.testbit x 0 then 1 else 0) with (Z.b2z (Z.testbit x 0))
        by (destruct (Z.testbit x 0); reflexivity).
      rewrite Z.bit0_mod. pose proof (Z.div_mod x 2 (ltac:(lia))). lia.
    + split; [apply Z.div_pos; lia|].
      apply Z.div_lt_upper_bound; [lia|].
      rewrite Nat2Z.inj_succ, Z.pow_succ_r in H by lia. nia.
Qed.

Theorem bits_le_of_bits_value : forall bs,
  bits_le (length bs) (bits_value bs) = bs.
Proof.
  induction bs as [|b bs IH]; [reflexivity|].
  cbn [length bits_value]. rewrite bits_le_succ.
  replace (if b then 1 else 0) with (Z.b2z b) by (destruct b; reflexivity).
  rewrite Z.add_b2z_double_bit0.
  assert (Hdiv : (Z.b2z b + 2 * bits_value bs) / 2 = bits_value bs).
  { symmetry. apply Z.div_unique with (r := Z.b2z b); destruct b; cbn [Z.b2z]; lia. }
  rewrite Hdiv, IH. reflexivity.
Qed.

Lemma bits_le_length : forall n x, length (bits_le n x) = n.
Proof. induction n; intros; [reflexivity|]. rewrite bits_le_succ. simpl. rewrite IHn. reflexivity. Qed.

Lemma chunk_of_exact : forall {A} fuel width (chunks : list (list A)),
  (0 < width)%nat -> (length chunks <= fuel)%nat ->
  Forall (fun xs => length xs = width) chunks ->
  chunk_of fuel width (concat chunks) = chunks.
Proof.
  intros A fuel width chunks Hw. revert fuel.
  induction chunks as [|xs chunks IH]; intros [|fuel] Hf Hall; cbn [chunk_of concat];
    try reflexivity; try (simpl in Hf; lia).
  inversion Hall as [|? ? Hxs Hrest].
  destruct xs as [|y xs]; [simpl in Hxs; lia|].
  change (firstn width ((y :: xs) ++ concat chunks) ::
    chunk_of fuel width (skipn width ((y :: xs) ++ concat chunks)) = (y :: xs) :: chunks).
  rewrite <- Hxs, firstn_app, firstn_all, Nat.sub_diag, skipn_app, skipn_all, Nat.sub_diag.
  cbn [firstn skipn app]. rewrite app_nil_r. f_equal. rewrite Hxs.
  apply IH; [simpl in Hf; lia|exact Hrest].
Qed.

Lemma chunk_of_concat : forall {A} fuel width (xs : list A),
  (0 < width)%nat -> (length xs <= fuel * width)%nat ->
  concat (chunk_of fuel width xs) = xs.
Proof.
  intros A fuel. induction fuel; intros width xs Hw Hlen.
  - destruct xs; [reflexivity|simpl in Hlen; lia].
  - destruct xs as [|x xs]; [reflexivity|].
    change (firstn width (x :: xs) ++ concat (chunk_of fuel width (skipn width (x :: xs))) = x :: xs).
    rewrite IHfuel; [apply firstn_skipn|exact Hw|]. rewrite skipn_length.
    cbn [length] in *. simpl in Hlen. nia.
Qed.

Lemma chunk_of_lengths : forall {A} fuel width (xs : list A),
  (0 < width)%nat -> (length xs mod width = 0)%nat ->
  Forall (fun part => length part = width) (chunk_of fuel width xs).
Proof.
  intros A fuel. induction fuel; intros width xs Hw Hmod; [constructor|].
  destruct xs as [|x xs]; [constructor|].
  assert (Hle : (width <= length (x :: xs))%nat).
  { destruct (Nat.lt_ge_cases (length (x :: xs)) width); [rewrite Nat.mod_small in Hmod by lia; simpl in Hmod; lia|lia]. }
  change (Forall (fun part => length part = width)
    (firstn width (x :: xs) :: chunk_of fuel width (skipn width (x :: xs)))).
  constructor.
  - rewrite firstn_length. apply Nat.min_l. exact Hle.
  - apply IHfuel; [exact Hw|]. rewrite skipn_length.
    pose proof (Nat.div_mod (length (x :: xs)) width (ltac:(lia))) as Hd.
    rewrite Hmod in Hd. replace (length (x :: xs) - width)%nat
      with ((length (x :: xs) / width - 1) * width)%nat by nia.
    apply Nat.mod_mul. lia.
Qed.

Lemma bit_codec_chunks : forall width chunks,
  Forall (fun bs => length bs = width) chunks ->
  map (bits_le width) (map bits_value chunks) = chunks.
Proof.
  intros width chunks H. induction H; cbn [map]; [reflexivity|].
  f_equal; [rewrite <- H; apply bits_le_of_bits_value|exact IHForall].
Qed.

Lemma concat_bits_length : forall width xs,
  length (concat (map (bits_le width) xs)) = (length xs * width)%nat.
Proof.
  intros width xs. induction xs; cbn [map concat length]; [reflexivity|].
  rewrite app_length, bits_le_length, IHxs. lia.
Qed.

Theorem byte_codec_roundtrip : forall width xs,
  (0 < width)%nat -> ((length xs * width) mod 8 = 0)%nat ->
  Forall (fun x => 0 <= x < 2 ^ Z.of_nat width) xs ->
  byte_decode width (byte_encode width xs) = xs.
Proof.
  intros width xs Hw Halign Hbounds. unfold byte_decode, byte_encode.
  rewrite bit_codec_chunks.
  2: { apply chunk_of_lengths; [lia|rewrite concat_bits_length; exact Halign]. }
  rewrite chunk_of_concat.
  2: lia.
  2: { rewrite concat_bits_length. nia. }
  rewrite chunk_of_exact.
  - clear Halign. induction Hbounds; cbn [map]; [reflexivity|].
    rewrite bits_value_of_bits_le by exact H. rewrite IHHbounds. reflexivity.
  - exact Hw.
  - rewrite map_length.
    (* Each coefficient requires width bits, and each output byte carries 8. *)
    assert (Htotal : length (concat (map (bits_le width) xs)) =
      (length (chunk_of (length xs * width) 8 (concat (map (bits_le width) xs))) * 8)%nat).
    { rewrite <- (chunk_of_concat (length xs * width) 8 (concat (map (bits_le width) xs))) at 1;
        [|lia|rewrite concat_bits_length; nia].
      pose proof (chunk_of_lengths (length xs * width) 8
        (concat (map (bits_le width) xs)) (ltac:(lia)) (ltac:(rewrite concat_bits_length; exact Halign))) as Hparts.
      induction Hparts; cbn [concat length]; [reflexivity|]. rewrite app_length, H, IHHparts. lia. }
    rewrite concat_bits_length in Htotal. rewrite map_length. nia.
  - apply Forall_forall. intros bs Hbs. apply in_map_iff in Hbs.
    destruct Hbs as [x [<- Hx]]. apply bits_le_length.
Qed.


(* -------------------------------------------------------------------------
   The R-05-163 assumption gate reads the native environment rather than this
   block, and the block is here because a reader wants the same list the gate
   enumerates: there is no Admitted, no Axiom, no top-level Parameter, and
   the only Require is the four Stdlib modules the header names. R-05-164
   reads the declared set from the register and it is empty, so the only
   passing line is the one this block prints, once per constant.
   ------------------------------------------------------------------------- *)
