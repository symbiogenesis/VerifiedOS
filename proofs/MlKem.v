(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   MlKem.v

   Functional ML-KEM-1024 reference against FIPS 203 (2024-08-13), using
   PqArith's shared ring/NTT/codec and Keccak's SHA3/SHAKE definitions.
   The concrete adapter follows Algorithms 7 and 8, matrix index order,
   PRF counter bytes, G=SHA3-512, H=SHA3-256 and J=SHAKE256. The K-PKE core,
   key layout and Fujisaki-Okamoto re-encryption/implicit rejection steps
   follow the standard. Raw core functions have caller preconditions;
   mlkem1024_keygen/encaps/decaps are checked public functional entry points.
   They reject malformed sizes/bytes, noncanonical encapsulation keys,
   inconsistent embedded key hashes and matrix-sampler exhaustion.
   SampleNTT uses Appendix B's permitted bound of 280 three-byte iterations,
   returns one failure value on exhaustion and releases no partial polynomial.
   Functional None does not prove implementation zeroization or timing.

   The parameter set is fixed by R-05-058a. Its key/ciphertext dimensions are
   1568/3168/1568 bytes. The generic Oracles record also supports deterministic
   algebraic examples; demo_oracles is explicitly neither random nor the
   standard hash adapter. Those examples are separate from the independent
   official known-answer campaign in proofs/campaigns/mlkem_vectors.py.
   That campaign downloads the pinned NIST ACVP-Server corpus and runs the
   actual extracted Gallina, including Keccak, through key generation,
   encapsulation, decapsulation and both input-validation categories.
   mlkem_openssl.py separately compares generated test inputs with the
   independent OpenSSL implementation, including both encapsulation directions.
   Extraction, OCaml, Zarith and the host execution are evidence boundaries,
   not a proved compiler bridge; receipts bind exact source and input hashes.
   FIPS 203's published potential errata change an array-index explanation
   and an Algorithm 15 comment, neither the computations implemented here.

   General theorems state the FO branch contract and checked-input refusal.
   An accepted matching re-encryption returns the candidate shared key; an
   accepted nonmatching re-encryption returns J(z || c). This is distinct
   from ML-DSA's Fiat-Shamir-with-aborts contract. Examples refute omission
   of the check, a recognizable failure constant, a tolerance comparison,
   message omission, sampler reduction and short-stream acceptance.

   PqArith proves NTT inversion for arbitrary reduced polynomials and a
   general bounded byte-codec roundtrip. Its transform multiplication
   equivalence and selected compression bounds are finite checks. Neither
   these algebraic results nor the official vectors prove universal K-PKE
   decryption correctness, a decryption-failure bound, IND-CCA security,
   random-oracle assumptions, malicious-key binding or a hybrid combiner.
   No CompCert-C/target refinement, constant-time or masking claim is made;
   R-05-022's interim-crypto retirement condition remains separate.
   The committed contract is docs/assurance/pq-reference-contract.md.
   No global axioms or admitted proofs are introduced. Native inventory,
   assumption closure and rocqchk, separately from the executable campaign,
   determine the proof evidence.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-022 R-05-058 R-05-058a R-05-059 R-05-165 R-05-166
   SHA256: 79f6b3f7e74755e0ba1b808c7c1f5a0c2fb4878221a67b92f50cd455fd9a1d52
   (*| END derived |*)
   ========================================================================= *)

Require Import PqArith.
Require Import Keccak.

From Stdlib Require Import ZArith List Arith Lia.

Open Scope Z_scope.

(* -------------------------------------------------------------------------
   The parameter set. R-05-058a freezes ML-KEM-1024; the statements below are
   over an arbitrary record and the instance decides only what the executable
   checks run at.
   ------------------------------------------------------------------------- *)

Record Params : Type := {
  kem_ring : Ring;         (* the shared ring, PqArith.v's *)
  kem_rank : nat;          (* k, the module rank *)
  kem_eta1 : nat;          (* the secret and key-generation noise width *)
  kem_eta2 : nat;          (* the encryption noise width *)
  kem_du : nat;            (* the compression width of the ciphertext vector *)
  kem_dv : nat;            (* the compression width of the ciphertext scalar *)
  kem_dt : nat;            (* the uncompressed coefficient packing width *)
  kem_seed_bytes : nat     (* the seed, hash and shared-secret length *)
}.

Definition mlkem_1024 : Params :=
  {| kem_ring := mlkem_ring; kem_rank := 4; kem_eta1 := 2; kem_eta2 := 2;
     kem_du := 11; kem_dv := 5; kem_dt := 12; kem_seed_bytes := 32 |}.

Definition kem_modulus (p : Params) : Z := ring_modulus (kem_ring p).
Definition kem_degree (p : Params) : nat := ring_degree (kem_ring p).

Definition kem_poly_bytes (p : Params) (d : nat) : nat :=
  encoded_bytes (kem_ring p) d.

Definition kem_vector_bytes (p : Params) (d : nat) : nat :=
  kem_rank p * kem_poly_bytes p d.

Definition kem_ek_bytes (p : Params) : nat :=
  kem_vector_bytes p (kem_dt p) + kem_seed_bytes p.

Definition kem_dk_bytes (p : Params) : nat :=
  kem_vector_bytes p (kem_dt p) + kem_ek_bytes p + 2 * kem_seed_bytes p.

Definition kem_ct_bytes (p : Params) : nat :=
  kem_vector_bytes p (kem_du p) + kem_poly_bytes p (kem_dv p).

(* -------------------------------------------------------------------------
   The oracle interface separates generic FO laws from the concrete FIPS
   adapter. The standard fixes that adapter's byte inputs and hash domains;
   the deterministic demonstration instance supplies local algebraic cases.
   ------------------------------------------------------------------------- *)

Record Oracles : Type := {
  (* the public matrix entry at a seed and a pair of indices, already in the
     transform domain, which is where the standard's own sampler puts it *)
  kem_matrix : list Z -> nat -> nat -> list Z;
  (* the noise polynomial at a width, a seed and a counter *)
  kem_noise : nat -> list Z -> nat -> list Z;
  (* the two-output hash, the one-output hash, and the rejection hash *)
  kem_g : list Z -> (list Z * list Z);
  kem_h : list Z -> list Z;
  kem_j : list Z -> list Z
}.

(* -------------------------------------------------------------------------
   Vectors and matrices over the ring, in the transform domain. Each product
   uses `mul_ntt_quadratic`, which is ML-KEM's own contract: its transform
   leaves residue rings of degree two and a coefficientwise product computes
   a different polynomial, which PqArith.v refutes rather than remarks on.
   ------------------------------------------------------------------------- *)

Definition vec_add (p : Params) (u v : list (list Z)) : list (list Z) :=
  map (fun pr => vadd (kem_modulus p) (fst pr) (snd pr)) (combine u v).

Definition vec_sub (p : Params) (u v : list (list Z)) : list (list Z) :=
  map (fun pr => vsub (kem_modulus p) (fst pr) (snd pr)) (combine u v).

Definition vec_ntt (p : Params) (v : list (list Z)) : list (list Z) :=
  map (ntt (kem_ring p)) v.

Definition vec_intt (p : Params) (v : list (list Z)) : list (list Z) :=
  map (intt (kem_ring p)) v.

Definition dot_ntt (p : Params) (u v : list (list Z)) : list Z :=
  fold_left (fun acc pr => vadd (kem_modulus p) acc
                                (mul_ntt_quadratic (kem_ring p) (fst pr) (snd pr)))
            (combine u v) (zero_poly (kem_degree p)).

Definition mat_times (p : Params) (a : list (list (list Z)))
                     (v : list (list Z)) : list (list Z) :=
  map (fun row => dot_ntt p row v) a.

(* The matrix at a seed, and the same matrix read transposed. The two differ
   by the order the two indices reach the oracle and by nothing else, which
   is what makes the pair one line apart and the convention visible. *)
Definition matrix_at (p : Params) (o : Oracles) (rho : list Z)
  : list (list (list Z)) :=
  map (fun i => map (fun j => kem_matrix o rho i j) (seq 0 (kem_rank p)))
      (seq 0 (kem_rank p)).

Definition matrix_transposed (p : Params) (o : Oracles) (rho : list Z)
  : list (list (list Z)) :=
  map (fun i => map (fun j => kem_matrix o rho j i) (seq 0 (kem_rank p)))
      (seq 0 (kem_rank p)).

Definition encode_vec (p : Params) (d : nat) (v : list (list Z)) : list Z :=
  concat (map (byte_encode d) v).

Definition decode_vec (p : Params) (d : nat) (bs : list Z) : list (list Z) :=
  map (fun part =>
         let raw := byte_decode d part in
         if Nat.eqb d (kem_dt p) then map (fun x => x mod kem_modulus p) raw else raw)
      (chunk_of (kem_rank p) (kem_poly_bytes p d) bs).

Definition compress_vec (p : Params) (d : nat) (v : list (list Z)) : list (list Z) :=
  map (compress_poly (kem_modulus p) d) v.

Definition decompress_vec (p : Params) (d : nat) (v : list (list Z)) : list (list Z) :=
  map (decompress_poly (kem_modulus p) d) v.

(* -------------------------------------------------------------------------
   The public-key encryption underneath the transform.
   ------------------------------------------------------------------------- *)

Definition pke_keygen (p : Params) (o : Oracles) (d : list Z) : list Z * list Z :=
  let seeds := kem_g o (d ++ (Z.of_nat (kem_rank p) :: nil)) in
  let rho := fst seeds in
  let sigma := snd seeds in
  let s := vec_ntt p (map (fun i => kem_noise o (kem_eta1 p) sigma i)
                          (seq 0 (kem_rank p))) in
  let e := vec_ntt p (map (fun i => kem_noise o (kem_eta1 p) sigma (kem_rank p + i))
                          (seq 0 (kem_rank p))) in
  let t := vec_add p (mat_times p (matrix_at p o rho) s) e in
  (encode_vec p (kem_dt p) t ++ rho, encode_vec p (kem_dt p) s).

Definition ek_vector (p : Params) (ek : list Z) : list (list Z) :=
  decode_vec p (kem_dt p) (firstn (kem_vector_bytes p (kem_dt p)) ek).

Definition ek_seed (p : Params) (ek : list Z) : list Z :=
  skipn (kem_vector_bytes p (kem_dt p)) ek.

(* The message is one bit per coefficient, decompressed to zero or half the
   modulus, which is what makes the quarter-modulus test at decryption the
   thing that recovers it. *)
Definition message_poly (p : Params) (m : list Z) : list Z :=
  decompress_poly (kem_modulus p) 1 (byte_decode 1 m).

Definition pke_encrypt (p : Params) (o : Oracles) (ek m rnd : list Z) : list Z :=
  let rho := ek_seed p ek in
  let t := ek_vector p ek in
  let y := vec_ntt p (map (fun i => kem_noise o (kem_eta1 p) rnd i)
                          (seq 0 (kem_rank p))) in
  let e1 := map (fun i => kem_noise o (kem_eta2 p) rnd (kem_rank p + i))
                (seq 0 (kem_rank p)) in
  let e2 := kem_noise o (kem_eta2 p) rnd (2 * kem_rank p) in
  let u := vec_add p (vec_intt p (mat_times p (matrix_transposed p o rho) y)) e1 in
  let v := vadd (kem_modulus p)
                (vadd (kem_modulus p) (intt (kem_ring p) (dot_ntt p t y)) e2)
                (message_poly p m) in
  encode_vec p (kem_du p) (compress_vec p (kem_du p) u)
  ++ byte_encode (kem_dv p) (compress_poly (kem_modulus p) (kem_dv p) v).

Definition ct_vector (p : Params) (c : list Z) : list (list Z) :=
  decompress_vec p (kem_du p)
    (decode_vec p (kem_du p) (firstn (kem_vector_bytes p (kem_du p)) c)).

Definition ct_scalar (p : Params) (c : list Z) : list Z :=
  decompress_poly (kem_modulus p) (kem_dv p)
    (byte_decode (kem_dv p) (skipn (kem_vector_bytes p (kem_du p)) c)).

Definition pke_decrypt (p : Params) (dkpke c : list Z) : list Z :=
  let s := decode_vec p (kem_dt p) dkpke in
  let w := vsub (kem_modulus p) (ct_scalar p c)
                (intt (kem_ring p)
                      (dot_ntt p s (vec_ntt p (ct_vector p c)))) in
  byte_encode 1 (compress_poly (kem_modulus p) 1 w).

(* -------------------------------------------------------------------------
   The Fujisaki-Okamoto transform. Its four decapsulation-key fields are read
   at offsets the parameter set computes, and the accessors are named so that
   a statement can say which field it reads.
   ------------------------------------------------------------------------- *)

Definition dk_secret (p : Params) (dk : list Z) : list Z :=
  firstn (kem_vector_bytes p (kem_dt p)) dk.

Definition dk_public (p : Params) (dk : list Z) : list Z :=
  firstn (kem_ek_bytes p) (skipn (kem_vector_bytes p (kem_dt p)) dk).

Definition dk_digest (p : Params) (dk : list Z) : list Z :=
  firstn (kem_seed_bytes p)
         (skipn (kem_vector_bytes p (kem_dt p) + kem_ek_bytes p) dk).

Definition dk_reject (p : Params) (dk : list Z) : list Z :=
  skipn (kem_vector_bytes p (kem_dt p) + kem_ek_bytes p + kem_seed_bytes p) dk.

Definition kem_keygen (p : Params) (o : Oracles) (d z : list Z) : list Z * list Z :=
  let pair := pke_keygen p o d in
  let ek := fst pair in
  (ek, snd pair ++ ek ++ kem_h o ek ++ z).

(* Encapsulation derives the shared secret and the encryption randomness from
   the message and the public key's digest together, so a ciphertext under
   one key cannot be replayed under another without changing both. *)
Definition kem_encaps_pair (p : Params) (o : Oracles) (ek m : list Z)
  : list Z * list Z :=
  kem_g o (m ++ kem_h o ek).

Definition kem_encaps (p : Params) (o : Oracles) (ek m : list Z) : list Z * list Z :=
  (fst (kem_encaps_pair p o ek m),
   pke_encrypt p o ek m (snd (kem_encaps_pair p o ek m))).

Definition decaps_message (p : Params) (dk c : list Z) : list Z :=
  pke_decrypt p (dk_secret p dk) c.

Definition decaps_pair (p : Params) (o : Oracles) (dk c : list Z) : list Z * list Z :=
  kem_g o (decaps_message p dk c ++ dk_digest p dk).

Definition decaps_reencryption (p : Params) (o : Oracles) (dk c : list Z) : list Z :=
  pke_encrypt p o (dk_public p dk) (decaps_message p dk c)
              (snd (decaps_pair p o dk c)).

Definition decaps_rejection (p : Params) (o : Oracles) (dk c : list Z) : list Z :=
  kem_j o (dk_reject p dk ++ c).

Definition kem_decaps (p : Params) (o : Oracles) (dk c : list Z) : list Z :=
  if poly_eqb (decaps_reencryption p o dk c) c
  then fst (decaps_pair p o dk c)
  else decaps_rejection p o dk c.

(* -------------------------------------------------------------------------
   The three constructions the transform rejects, each held to one difference
   from `kem_decaps` and keeping every clause it does not break.
   ------------------------------------------------------------------------- *)

(* No check at all, which is the transform's own subject: the recovered
   message's derived key is returned whatever the ciphertext was. *)
Definition decaps_without_the_reencryption_check
  (p : Params) (o : Oracles) (dk c : list Z) : list Z :=
  fst (decaps_pair p o dk c).

(* A distinguishable refusal, which is what implicit rejection exists to
   deny: the failure answer is a constant every observer can recognize. *)
Definition decaps_with_an_explicit_refusal
  (p : Params) (o : Oracles) (dk c : list Z) : list Z :=
  if poly_eqb (decaps_reencryption p o dk c) c
  then fst (decaps_pair p o dk c)
  else zero_poly (kem_seed_bytes p).

(* And the conflation this file exists to keep apart: a check that accepts a
   ciphertext near the re-encrypted one instead of equal to it, which is the
   shape of a signature scheme's bounded response and not of this transform's
   observable. *)
Definition decaps_tolerance (p : Params) : Z := 256.

Definition decaps_on_a_bound_instead_of_an_equality
  (p : Params) (o : Oracles) (dk c : list Z) : list Z :=
  if Z.ltb (norm_inf (kem_modulus p)
                     (vsub (kem_modulus p) (decaps_reencryption p o dk c) c))
           (decaps_tolerance p)
  then fst (decaps_pair p o dk c)
  else decaps_rejection p o dk c.

(* An encryption that omits the message, which is the weakening no size and
   no round trip reports: the ciphertext is the right length, it decrypts,
   and it carries the wrong thing. *)
Definition encrypt_without_the_message (p : Params) (o : Oracles)
                                       (ek m rnd : list Z) : list Z :=
  let rho := ek_seed p ek in
  let t := ek_vector p ek in
  let y := vec_ntt p (map (fun i => kem_noise o (kem_eta1 p) rnd i)
                          (seq 0 (kem_rank p))) in
  let e1 := map (fun i => kem_noise o (kem_eta2 p) rnd (kem_rank p + i))
                (seq 0 (kem_rank p)) in
  let e2 := kem_noise o (kem_eta2 p) rnd (2 * kem_rank p) in
  let u := vec_add p (vec_intt p (mat_times p (matrix_transposed p o rho) y)) e1 in
  let v := vadd (kem_modulus p) (intt (kem_ring p) (dot_ntt p t y)) e2 in
  encode_vec p (kem_du p) (compress_vec p (kem_du p) u)
  ++ byte_encode (kem_dv p) (compress_poly (kem_modulus p) (kem_dv p) v).


(* -------------------------------------------------------------------------
   What the transform does, over an arbitrary parameter set, an arbitrary
   oracle and arbitrary keys and ciphertexts. These four are the whole of the
   FO contract this file states, and none of them is a conversion at a chosen
   input.
   ------------------------------------------------------------------------- *)

(*| discharges: R-05-058 |*)
Theorem the_shared_secret_is_returned_exactly_where_re_encryption_reproduces_it :
  forall (p : Params) (o : Oracles) (dk c : list Z),
    poly_eqb (decaps_reencryption p o dk c) c = true ->
    kem_decaps p o dk c = fst (decaps_pair p o dk c).
Proof. intros p o dk c H. unfold kem_decaps. rewrite H. reflexivity. Qed.

(*| discharges: R-05-058 |*)
Theorem the_rejection_value_is_returned_where_re_encryption_does_not :
  forall (p : Params) (o : Oracles) (dk c : list Z),
    poly_eqb (decaps_reencryption p o dk c) c = false ->
    kem_decaps p o dk c = kem_j o (dk_reject p dk ++ c).
Proof. intros p o dk c H. unfold kem_decaps, decaps_rejection. rewrite H. reflexivity. Qed.

(* The implicit-rejection value reads the rejection seed and the ciphertext
   and nothing else, so two decapsulation keys that agree there and fail
   answer the same value however their secret vectors differ. That is the
   property a distinguishable refusal destroys, and it is stated over
   arbitrary keys rather than exhibited at one. *)
(*| discharges: R-05-058 |*)
Theorem a_failed_decapsulation_reads_only_the_rejection_seed_and_the_ciphertext :
  forall (p : Params) (o : Oracles) (dk dk' c : list Z),
    dk_reject p dk = dk_reject p dk' ->
    poly_eqb (decaps_reencryption p o dk c) c = false ->
    poly_eqb (decaps_reencryption p o dk' c) c = false ->
    kem_decaps p o dk c = kem_decaps p o dk' c.
Proof.
  intros p o dk dk' c Hz H1 H2.
  rewrite (the_rejection_value_is_returned_where_re_encryption_does_not p o dk c H1).
  rewrite (the_rejection_value_is_returned_where_re_encryption_does_not p o dk' c H2).
  rewrite Hz. reflexivity.
Qed.

(* And the construction with no check answers the same value on both branches,
   which is exactly the difference the check makes. *)
(*| discharges: R-05-165 |*)
Theorem the_unchecked_decapsulation_ignores_the_ciphertext_comparison :
  forall (p : Params) (o : Oracles) (dk c : list Z),
    decaps_without_the_reencryption_check p o dk c = fst (decaps_pair p o dk c).
Proof. intros. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The demonstration oracle. It is arithmetic and it is not a sampler: no
   draw here has a distribution, nothing here is the standard's SampleNTT or
   centred binomial sampler, and no statement in this file rests on it being
   either. What it buys is that the algebra above runs: a key pair, a
   ciphertext and a decapsulation are computed inside the kernel, so the
   matrix product, the noise placement, the compression and the re-encryption
   check are exercised rather than only described.
   ------------------------------------------------------------------------- *)

Fixpoint lcg_values (n : nat) (x : Z) : list Z :=
  match n with
  | O => nil
  | S k => let y := (x * 1103515245 + 12345) mod 2147483648 in y :: lcg_values k y
  end.

Definition seed_value (seed : list Z) (tag : Z) : Z :=
  fold_left (fun acc x => (acc * 257 + x + 1) mod 2147483647) seed (tag + 1).

Definition demo_bytes (seed : list Z) (tag : Z) (n : nat) : list Z :=
  map (fun y => (y / 65536) mod 256) (lcg_values n (seed_value seed tag)).

(* The centred binomial shape, which is what keeps the demonstration's noise
   small enough for the algebra to close: the difference of two counts of the
   same width. *)
Definition popcount_bits (x : Z) (from count : nat) : Z :=
  fold_left (fun acc i => acc + (if Z.testbit x (Z.of_nat (from + i)) then 1 else 0))
            (seq 0 count) 0.

Definition binomial_value (eta : nat) (y : Z) : Z :=
  popcount_bits (y / 256) 0 eta - popcount_bits (y / 256) eta eta.

Definition demo_noise_poly (p : Params) (eta : nat) (seed : list Z) (tag : nat)
  : list Z :=
  map (fun y => (binomial_value eta y) mod kem_modulus p)
      (lcg_values (kem_degree p) (seed_value seed (Z.of_nat tag))).

Definition demo_uniform_poly (p : Params) (seed : list Z) (tag : Z) : list Z :=
  map (fun y => (y / 8) mod kem_modulus p)
      (lcg_values (kem_degree p) (seed_value seed tag)).

Definition demo_oracles (p : Params) : Oracles :=
  {| kem_matrix := fun rho i j =>
       demo_uniform_poly p rho (Z.of_nat (i * kem_rank p + j));
     kem_noise := fun eta seed tag => demo_noise_poly p eta seed tag;
     kem_g := fun m => (demo_bytes m 3 (kem_seed_bytes p),
                        demo_bytes m 4 (kem_seed_bytes p));
     kem_h := fun m => demo_bytes m 1 (kem_seed_bytes p);
     kem_j := fun m => demo_bytes m 2 (kem_seed_bytes p) |}.

(* -------------------------------------------------------------------------
   The concrete FIPS 203 hash and sampler adapter. The full scheme is run
   through these definitions by the extracted official-vector campaign.
   ------------------------------------------------------------------------- *)

Definition shake_bytes (strength out_bytes : nat) (m : list Z) : list Z :=
  map Z.of_nat (bytes_of (shake strength (8 * out_bytes)
                                (bits_of_bytes (map Z.to_nat m)))).

Definition sha3_bytes (digest_bits : nat) (m : list Z) : list Z :=
  map Z.of_nat (bytes_of (sha3 digest_bits (bits_of_bytes (map Z.to_nat m)))).

(* FIPS 203 Algorithms 7 and 8. SampleNTT rejects candidates >= q rather
   than reducing them. A bounded stream returns one uniform exhaustion
   result and never releases a prefix as a polynomial. 280 three-byte
   iterations is the minimum permitted bound in Appendix B. *)
Definition sample_ntt_bytes (p : Params) (bs : list Z) : option (list Z) :=
  let accepted := firstn (kem_degree p)
    (filter (fun x => Z.ltb x (kem_modulus p)) (byte_decode 12 bs)) in
  if Nat.eqb (length accepted) (kem_degree p) then Some accepted else None.

Definition cbd_value (eta : nat) (x : Z) : Z :=
  popcount_bits x 0 eta - popcount_bits x eta eta.

Definition sample_cbd_bytes (p : Params) (eta : nat) (bs : list Z) : list Z :=
  map (fun x => cbd_value eta x mod kem_modulus p) (byte_decode (2*eta) bs).

Definition sample_ntt_bounded (p : Params) (rho : list Z) (i j : nat)
  : option (list Z) :=
  sample_ntt_bytes p
    (shake_bytes 128 (3*280) (rho ++ (Z.of_nat j :: Z.of_nat i :: nil))).

Definition shake_oracles (p : Params) : Oracles :=
  {| kem_matrix := fun rho i j =>
       match sample_ntt_bounded p rho i j with Some a => a | None => nil end;
     kem_noise := fun eta seed tag =>
       sample_cbd_bytes p eta
           (shake_bytes 256 (64*eta) (seed ++ (Z.of_nat tag :: nil)));
     kem_g := fun m => let digest := sha3_bytes 512 m in (firstn 32 digest, skipn 32 digest);
     kem_h := sha3_bytes 256;
     kem_j := shake_bytes 256 32 |}.

Definition bytes_valid (bs : list Z) : bool :=
  forallb (fun x => andb (0 <=? x) (x <? 256)) bs.

Definition bytes_length (n : nat) (bs : list Z) : bool :=
  andb (Nat.eqb (length bs) n) (bytes_valid bs).

Definition matrix_complete (p : Params) (o : Oracles) (rho : list Z) : bool :=
  forallb (fun row => forallb (fun a => Nat.eqb (length a) (kem_degree p)) row)
    (matrix_at p o rho).

Definition encapsulation_key_valid (p : Params) (ek : list Z) : bool :=
  andb (bytes_length (kem_ek_bytes p) ek)
  (poly_eqb (encode_vec p (kem_dt p) (ek_vector p ek))
           (firstn (kem_vector_bytes p (kem_dt p)) ek)).

Local Open Scope bool_scope.

Definition decapsulation_input_valid (p : Params) (o : Oracles) (dk c : list Z) : bool :=
  bytes_length (kem_dk_bytes p) dk && bytes_length (kem_ct_bytes p) c &&
  poly_eqb (kem_h o (dk_public p dk)) (dk_digest p dk).

Definition kem_keygen_checked (p : Params) (o : Oracles) (d z : list Z)
  : option (list Z * list Z) :=
  if bytes_length (kem_seed_bytes p) d && bytes_length (kem_seed_bytes p) z &&
     matrix_complete p o (fst (kem_g o (d ++ (Z.of_nat (kem_rank p) :: nil))))
  then Some (kem_keygen p o d z) else None.

Definition kem_encaps_checked (p : Params) (o : Oracles) (ek m : list Z)
  : option (list Z * list Z) :=
  if encapsulation_key_valid p ek && bytes_length (kem_seed_bytes p) m &&
     matrix_complete p o (ek_seed p ek)
  then Some (kem_encaps p o ek m) else None.

Definition kem_decaps_checked (p : Params) (o : Oracles) (dk c : list Z)
  : option (list Z) :=
  if decapsulation_input_valid p o dk c && matrix_complete p o (ek_seed p (dk_public p dk))
  then Some (kem_decaps p o dk c) else None.

Definition mlkem1024_keygen := kem_keygen_checked mlkem_1024 (shake_oracles mlkem_1024).
Definition mlkem1024_encaps := kem_encaps_checked mlkem_1024 (shake_oracles mlkem_1024).
Definition mlkem1024_decaps := kem_decaps_checked mlkem_1024 (shake_oracles mlkem_1024).

Theorem checked_decapsulation_refuses_malformed_inputs : forall p o dk c,
  decapsulation_input_valid p o dk c = false -> kem_decaps_checked p o dk c = None.
Proof. intros p o dk c H. unfold kem_decaps_checked. rewrite H. reflexivity. Qed.

Theorem checked_encapsulation_refuses_noncanonical_keys : forall p o ek m,
  encapsulation_key_valid p ek = false -> kem_encaps_checked p o ek m = None.
Proof. intros p o ek m H. unfold kem_encaps_checked. rewrite H. reflexivity. Qed.

Theorem checked_keygen_refuses_sampler_exhaustion : forall p o d z,
  matrix_complete p o (fst (kem_g o (d ++ (Z.of_nat (kem_rank p) :: nil)))) = false ->
  kem_keygen_checked p o d z = None.
Proof.
  intros p o d z H. unfold kem_keygen_checked. rewrite H.
  destruct (bytes_length (kem_seed_bytes p) d && bytes_length (kem_seed_bytes p) z); reflexivity.
Qed.

Theorem checked_encapsulation_refuses_sampler_exhaustion : forall p o ek m,
  matrix_complete p o (ek_seed p ek) = false -> kem_encaps_checked p o ek m = None.
Proof.
  intros p o ek m H. unfold kem_encaps_checked. rewrite H.
  destruct (encapsulation_key_valid p ek && bytes_length (kem_seed_bytes p) m); reflexivity.
Qed.

Theorem checked_decapsulation_refuses_sampler_exhaustion : forall p o dk c,
  matrix_complete p o (ek_seed p (dk_public p dk)) = false ->
  kem_decaps_checked p o dk c = None.
Proof.
  intros p o dk c H. unfold kem_decaps_checked. rewrite H.
  destruct (decapsulation_input_valid p o dk c); reflexivity.
Qed.

Theorem checked_decapsulation_preserves_implicit_rejection : forall p o dk c,
  decapsulation_input_valid p o dk c = true ->
  matrix_complete p o (ek_seed p (dk_public p dk)) = true ->
  poly_eqb (decaps_reencryption p o dk c) c = false ->
  kem_decaps_checked p o dk c = Some (kem_j o (dk_reject p dk ++ c)).
Proof.
  intros p o dk c Hv Hm Hc. unfold kem_decaps_checked.
  rewrite Hv, Hm. simpl.
  rewrite (the_rejection_value_is_returned_where_re_encryption_does_not p o dk c Hc).
  reflexivity.
Qed.

Theorem checked_decapsulation_preserves_matching_reencryption : forall p o dk c,
  decapsulation_input_valid p o dk c = true ->
  matrix_complete p o (ek_seed p (dk_public p dk)) = true ->
  poly_eqb (decaps_reencryption p o dk c) c = true ->
  kem_decaps_checked p o dk c = Some (fst (decaps_pair p o dk c)).
Proof.
  intros p o dk c Hv Hm Hc. unfold kem_decaps_checked.
  rewrite Hv, Hm. simpl.
  rewrite (the_shared_secret_is_returned_exactly_where_re_encryption_reproduces_it p o dk c Hc).
  reflexivity.
Qed.

Example byte_parser_refuses_values_outside_a_byte :
  (bytes_valid (-1 :: nil), bytes_valid (256 :: nil), bytes_valid (0 :: 255 :: nil))
    = (false, false, true).
Proof. reflexivity. Qed.

Example matrix_sampler_does_not_reduce_rejected_candidates :
  sample_ntt_bytes mlkem_1024 (repeat 255 (3*280)) = None.
Proof. vm_compute. reflexivity. Qed.

Example matrix_sampler_accepts_exactly_a_whole_polynomial :
  sample_ntt_bytes mlkem_1024 (repeat 0 384) = Some (repeat 0 256).
Proof. vm_compute. reflexivity. Qed.

Example matrix_sampler_refuses_a_short_stream :
  sample_ntt_bytes mlkem_1024 (repeat 0 381) = None.
Proof. vm_compute. reflexivity. Qed.

Example cbd_uses_consecutive_groups_of_bits :
  sample_cbd_bytes mlkem_1024 2 (3 :: 12 :: nil) = (2 :: 0 :: 3327 :: 0 :: nil).
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The sizes the parameter set determines. Each is computed from the
   selected FIPS 203 parameter set.
   ------------------------------------------------------------------------- *)

Example the_parameter_set_determines_these_sizes :
  (kem_ek_bytes mlkem_1024, kem_dk_bytes mlkem_1024, kem_ct_bytes mlkem_1024,
   kem_seed_bytes mlkem_1024)
  = (1568%nat, 3168%nat, 1568%nat, 32%nat).
Proof. vm_compute. reflexivity. Qed.

Example the_parameter_set_is_the_category_five_one :
  (kem_rank mlkem_1024, kem_eta1 mlkem_1024, kem_eta2 mlkem_1024,
   kem_du mlkem_1024, kem_dv mlkem_1024, kem_dt mlkem_1024)
  = (4%nat, 2%nat, 2%nat, 11%nat, 5%nat, 12%nat).
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The scheme, run inside the kernel at the demonstration oracle.
   ------------------------------------------------------------------------- *)

Definition demo_p : Params := mlkem_1024.
Definition demo_o : Oracles := demo_oracles demo_p.

Definition demo_d : list Z := demo_bytes (1 :: 2 :: 3 :: nil) 9 32.
Definition demo_z : list Z := demo_bytes (1 :: 2 :: 3 :: nil) 10 32.
Definition demo_m : list Z := demo_bytes (4 :: 5 :: nil) 11 32.

Definition demo_keys : list Z * list Z := kem_keygen demo_p demo_o demo_d demo_z.
Definition demo_ek : list Z := fst demo_keys.
Definition demo_dk : list Z := snd demo_keys.
Definition demo_ct : list Z := snd (kem_encaps demo_p demo_o demo_ek demo_m).
Definition demo_key : list Z := fst (kem_encaps demo_p demo_o demo_ek demo_m).

(* A ciphertext one byte different from the honest one, which is the input
   every refutation below is taken at. *)
Definition demo_tampered : list Z :=
  match demo_ct with
  | nil => nil
  | b :: rest => ((b + 1) mod 256) :: rest
  end.

Example the_generated_keys_have_the_sizes_the_parameters_give :
  (length demo_ek, length demo_dk, length demo_ct, length demo_key)
  = (kem_ek_bytes demo_p, kem_dk_bytes demo_p, kem_ct_bytes demo_p,
     kem_seed_bytes demo_p).
Proof. vm_compute. reflexivity. Qed.

(* The public key inside the decapsulation key is the encapsulation key, and
   the digest field is its hash, which is what makes the re-encryption above
   a re-encryption under the same key. *)
Example the_decapsulation_key_carries_its_own_public_key_and_digest :
  (poly_eqb (dk_public demo_p demo_dk) demo_ek,
   poly_eqb (dk_digest demo_p demo_dk) (kem_h demo_o demo_ek),
   poly_eqb (dk_reject demo_p demo_dk) demo_z)
  = (true, true, true).
Proof. vm_compute. reflexivity. Qed.

(* The encryption recovers its message, which is the bound PqArith.v's
   one-bit compression states and this file does not prove: at this
   parameter set and this stand-in noise the accumulated error stays inside a
   quarter of the modulus, and that is a computation rather than a theorem. *)
(*| discharges: R-05-059 |*)
Example the_encryption_recovers_its_message :
  poly_eqb (decaps_message demo_p demo_dk demo_ct) demo_m = true.
Proof. vm_compute. reflexivity. Qed.

(*| discharges: R-05-058 |*)
Example decapsulation_returns_the_encapsulated_key :
  poly_eqb (kem_decaps demo_p demo_o demo_dk demo_ct) demo_key = true.
Proof. vm_compute. reflexivity. Qed.

(* And on a ciphertext one byte different the re-encryption does not
   reproduce it, so the transform takes its other branch. *)
Example a_tampered_ciphertext_fails_the_re_encryption_check :
  poly_eqb (decaps_reencryption demo_p demo_o demo_dk demo_tampered)
           demo_tampered = false.
Proof. vm_compute. reflexivity. Qed.

(*| discharges: R-05-058 |*)
Example a_tampered_ciphertext_decapsulates_to_the_rejection_value :
  (poly_eqb (kem_decaps demo_p demo_o demo_dk demo_tampered)
            (decaps_rejection demo_p demo_o demo_dk demo_tampered),
   poly_eqb (kem_decaps demo_p demo_o demo_dk demo_tampered) demo_key)
  = (true, false).
Proof. vm_compute. reflexivity. Qed.

(* The refutations, at that same ciphertext. Each construction keeps every
   clause it does not break and answers differently exactly where the
   transform's own check decides. *)
(*| discharges: R-05-165 |*)
Example a_decapsulation_with_no_re_encryption_check_is_refused :
  poly_eqb (decaps_without_the_reencryption_check demo_p demo_o demo_dk demo_tampered)
           (kem_decaps demo_p demo_o demo_dk demo_tampered) = false.
Proof. vm_compute. reflexivity. Qed.

(* It agrees with the transform wherever the check passes, which holds it to
   that single difference. *)
Example the_unchecked_decapsulation_agrees_on_an_honest_ciphertext :
  poly_eqb (decaps_without_the_reencryption_check demo_p demo_o demo_dk demo_ct)
           (kem_decaps demo_p demo_o demo_dk demo_ct) = true.
Proof. vm_compute. reflexivity. Qed.

(*| discharges: R-05-165 |*)
Example a_distinguishable_refusal_is_refused :
  (poly_eqb (decaps_with_an_explicit_refusal demo_p demo_o demo_dk demo_tampered)
            (zero_poly (kem_seed_bytes demo_p)),
   poly_eqb (kem_decaps demo_p demo_o demo_dk demo_tampered)
            (zero_poly (kem_seed_bytes demo_p)))
  = (true, false).
Proof. vm_compute. reflexivity. Qed.

(* And the conflation: a check that accepts a ciphertext near the
   re-encrypted one accepts this one, where the equality refuses it. That is
   the whole reason this transform's observable is an equality, and why no
   statement here is shared with a scheme whose observable is a bound. *)
(*| discharges: R-05-165 |*)
Example a_bounded_check_accepts_what_the_equality_refuses :
  (poly_eqb (decaps_on_a_bound_instead_of_an_equality demo_p demo_o demo_dk demo_tampered)
            (fst (decaps_pair demo_p demo_o demo_dk demo_tampered)),
   poly_eqb (kem_decaps demo_p demo_o demo_dk demo_tampered)
            (fst (decaps_pair demo_p demo_o demo_dk demo_tampered)))
  = (true, false).
Proof. vm_compute. reflexivity. Qed.

(*| discharges: R-05-165 |*)
Example an_encryption_that_omits_the_message_is_refused :
  (Nat.eqb (length (encrypt_without_the_message demo_p demo_o demo_ek demo_m
                      (snd (kem_encaps_pair demo_p demo_o demo_ek demo_m))))
           (kem_ct_bytes demo_p),
   poly_eqb (encrypt_without_the_message demo_p demo_o demo_ek demo_m
               (snd (kem_encaps_pair demo_p demo_o demo_ek demo_m)))
            demo_ct)
  = (true, false).
Proof. vm_compute. reflexivity. Qed.

(* The two matrix readings are different matrices, which is what makes the
   transposition at encryption a decision rather than a spelling. *)
Example the_matrix_and_its_transpose_are_different_matrices :
  poly_eqb (concat (concat (matrix_at demo_p demo_o (ek_seed demo_p demo_ek))))
           (concat (concat (matrix_transposed demo_p demo_o
                              (ek_seed demo_p demo_ek)))) = false.
Proof. vm_compute. reflexivity. Qed.

(* The two noise widths at one seed and two counters are two draws, as a
   local check of the deterministic demonstration oracle. *)
Example two_counters_at_one_seed_are_two_draws :
  poly_eqb (kem_noise demo_o (kem_eta1 demo_p) demo_d 0%nat)
           (kem_noise demo_o (kem_eta1 demo_p) demo_d 1%nat) = false.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The adapter onto Keccak.v, checked where it can be wrong silently: the
   output length, the byte order, and that the two strengths are two
   functions. Full-scheme checks are in the extracted campaign.
   ------------------------------------------------------------------------- *)

Example the_adapter_returns_the_requested_number_of_bytes :
  (length (shake_bytes 256 32 (1 :: 2 :: nil)),
   length (shake_bytes 128 8 (1 :: 2 :: nil)))
  = (32%nat, 8%nat).
Proof. vm_compute. reflexivity. Qed.

Example the_adapter_returns_bytes :
  forallb (fun b => andb (Z.leb 0 b) (Z.ltb b 256)) (shake_bytes 256 32 (7 :: nil))
  = true.
Proof. vm_compute. reflexivity. Qed.

Example the_two_strengths_are_two_functions :
  poly_eqb (shake_bytes 128 32 nil) (shake_bytes 256 32 nil) = false.
Proof. vm_compute. reflexivity. Qed.

(* A direct local check of the concrete hash adapter's digest length. *)
Example the_keccak_oracles_are_an_oracle_record :
  kem_seed_bytes demo_p = length (kem_h (shake_oracles demo_p) (1 :: nil)).
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The decisions a reader would otherwise take on trust because nothing above
   reaches them.
   ------------------------------------------------------------------------- *)

Example the_message_is_one_bit_a_coefficient :
  (length (byte_decode 1 demo_m), length demo_m) = (256%nat, 32%nat).
Proof. vm_compute. reflexivity. Qed.

Example a_message_bit_decompresses_to_zero_or_half_the_modulus :
  (decompress (kem_modulus demo_p) 1 0, decompress (kem_modulus demo_p) 1 1)
  = (0, 1665).
Proof. vm_compute. reflexivity. Qed.

Example the_tampered_ciphertext_differs_in_one_byte :
  (Nat.eqb (length demo_tampered) (length demo_ct),
   Nat.eqb (length (filter (fun pr => negb (Z.eqb (fst pr) (snd pr)))
                           (combine demo_ct demo_tampered))) 1)
  = (true, true).
Proof. vm_compute. reflexivity. Qed.

Example the_demonstration_seeds_are_these :
  (digest_of 3329 demo_d, digest_of 3329 demo_z, digest_of 3329 demo_m)
  = (2746, 894, 167).
Proof. vm_compute. reflexivity. Qed.

Example the_bounded_check_s_tolerance :
  decaps_tolerance demo_p = 256.
Proof. reflexivity. Qed.

Example an_empty_matrix_product_is_the_zero_polynomial :
  poly_eqb (dot_ntt demo_p nil nil) (zero_poly (kem_degree demo_p)) = true.
Proof. vm_compute. reflexivity. Qed.

(* The four decapsulation-key accessors read four fields whose lengths sum to
   the whole key, which is what the statements above need of the layout and
   all they need of it. *)
Example the_key_fields_cover_the_decapsulation_key :
  (length (dk_secret demo_p demo_dk), length (dk_public demo_p demo_dk),
   length (dk_digest demo_p demo_dk), length (dk_reject demo_p demo_dk),
   length demo_dk)
  = (1536%nat, 1568%nat, 32%nat, 32%nat, 3168%nat).
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   R-05-166's decidable half: the two records this file's statements range
   over, each inhabited by a closed definition ascribed at it.
   ------------------------------------------------------------------------- *)

Definition witness_Params : Params := mlkem_1024.

Definition witness_Oracles : Oracles := demo_oracles mlkem_1024.
