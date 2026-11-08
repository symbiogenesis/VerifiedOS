(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   AesGcm.v

   Functional Gallina reference for the AES block cipher at 128-, 192-, and
   256-bit key lengths, GF(2^128) multiplication and GHASH, counter mode, and
   AES-GCM authenticated encryption and decryption (FIPS 197 and NIST SP
   800-38D), paired with the Sail vector-crypto model
   ([types_kext.sail](../model/model/extensions/K/types_kext.sail) and
   [zvkg_insts.sail](../model/model/extensions/vector_crypto/zvkg_insts.sail))
   for the AEAD frozen by R-10-024 (with R-05-058a fixing Category 5
   asymmetric parameters and R-10-021, R-10-022, R-10-022a, and R-10-023
   governing per-extent storage AEAD, nonces, and tags; R-05-126b grades
   nonces linearly).

   Scope: functional specification layer of R-05-059 only. Binary constant-time
   behavior (R-05-062, R-05-067), d-probing masking (R-05-004a, R-15-053a),
   and distributional security reductions (R-05-077a) are separate obligations
   (compare R-15-058 for the model's Keccak unit).

   Representation and derived tables:
   - Bytes are 8-element MSB-first `list bool` (FIPS 197 s3.1); blocks are
     128-element MSB-first `list bool` (SP 800-38D s6.3, opposite to
     [Keccak.v](Keccak.v)'s LSB-first lanes).
   - Forward/inverse S-boxes and round constants are derived from the GF(2^8)
     multiplicative inverse, affine transform, and x^i recurrence and checked
     against FIPS 197's published tables; reflected SP 800-38D GHASH
     multiplication is proved equal to the byte-bit-reversed `brev8` form.
   - Known-answer vectors from FIPS 197 Appendices A.1, B, C.1--C.3 and GCM
     test cases 1--5 (independently recomputed against OpenSSL 3.5.5) sit in
     `Example` statements outside `Definition`s, with seven refuting
     constructions for non-vacuity (R-05-163, R-05-164, R-05-165, R-05-166).
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-004a R-05-058a R-05-059 R-05-062 R-05-067 R-05-077a R-05-126b R-05-163
      R-05-164 R-05-165 R-05-166 R-10-021 R-10-022 R-10-022a R-10-023 R-10-024 R-15-053a
      R-15-058
   SHA256: 48319a28b5c9be96ca91647ba1b59ea00b6f81404c9e8ffad48c23895e466998
   (*| END derived |*)
   ========================================================================= *)

Require ProofSupport CryptoLists.
Open Scope list_scope.

(* Defer evaluation of the equality to the kernel's VM cast check at Qed. *)
Local Ltac vm_reflexivity :=
  intros; lazymatch goal with |- _ = ?b => vm_cast_no_check (@eq_refl _ b) end.

(* -------------------------------------------------------------------------
   List helpers retain their public names as aliases of the shared prelude
   support; the primitive references use no Stdlib list library.
   ------------------------------------------------------------------------- *)

Definition map_over {A B : Type} : (A -> B) -> list A -> list B := @ProofSupport.map_over A B.

Definition length_of {A : Type} : list A -> nat := @ProofSupport.length_of A.

Definition take_of {A : Type} : nat -> list A -> list A := @ProofSupport.take_of A.

Definition drop_of {A : Type} : nat -> list A -> list A := @ProofSupport.drop_of A.

Definition nth_of {A : Type} : nat -> list A -> A -> A := @ProofSupport.nth_of A.

(* Out-of-range bit reads return false; an Example below checks this
   default. *)
Definition bit_at (l : list bool) (i : nat) : bool := nth_of i l false.

Definition rev_onto {A : Type} : list A -> list A -> list A := @ProofSupport.rev_onto A.

Definition rev_of {A : Type} (l : list A) : list A := rev_onto l nil.

Definition repeat_of {A : Type} : nat -> A -> list A := @ProofSupport.repeat_of A.

(* Generate start through start + count - 1 without repeated append. *)
Definition up_from : nat -> nat -> list nat := ProofSupport.up_from.

Definition upto (n : nat) : list nat := up_from 0 n.

Definition fold_over {A B : Type} : (B -> A -> B) -> B -> list A -> B := @ProofSupport.fold_over A B.

Definition concat_of {A : Type} : list (list A) -> list A := @ProofSupport.concat_of A.

Definition all_of {A : Type} : (A -> bool) -> list A -> bool := @ProofSupport.all_of A.

Definition count_where {A : Type} : (A -> bool) -> list A -> nat := @ProofSupport.count_where A.

Definition keep_where {A : Type} : (A -> bool) -> list A -> list A := @ProofSupport.filter_of A.

(* Recurse on a chunk-count bound because drop_of does not produce a
   structural subterm of the list. *)
Fixpoint chunks_of {A : Type} (fuel n : nat) (l : list A) : list (list A) :=
  match fuel with
  | 0 => nil
  | S k => if l is nil then nil else take_of n l :: chunks_of k n (drop_of n l)
  end.

Definition eqb_bool (x y : bool) : bool := negb (xorb x y).

Fixpoint bits_eqb (a b : list bool) : bool :=
  match a with
  | nil => if b is nil then true else false
  | x :: xs => match b with nil => false | y :: ys => andb (eqb_bool x y) (bits_eqb xs ys) end
  end.

Definition mem_nat (n : nat) (l : list nat) : bool :=
  negb (Nat.eqb (count_where (fun k => Nat.eqb k n) l) 0).

(* Extract n low bits by repeated halving. Reversing this list gives the
   big-endian length field without constructing 2^64. *)
Fixpoint bits_le_of (n v : nat) : list bool :=
  match n with
  | 0 => nil
  | S k => Nat.eqb (Nat.modulo v 2) 1 :: bits_le_of k (Nat.div v 2)
  end.

Definition bits_be_of (n v : nat) : list bool := rev_of (bits_le_of n v).

(* -------------------------------------------------------------------------
   The two alphabets. A byte is eight bits most significant first (FIPS 197
   s3.1); a block is sixteen bytes concatenated, whose head is SP 800-38D's
   x_0 (s6.3); a state is those sixteen bytes in FIPS 197's own input order.
   ------------------------------------------------------------------------- *)

Definition byte : Type := list bool.
Definition block : Type := list bool.
Definition state : Type := list byte.

Definition byte_bits : nat := 8.
Definition rows : nat := 4.
Definition nb : nat := 4.
Definition block_bytes : nat := rows * nb.
Definition block_bits : nat := block_bytes * byte_bits.

Definition zero_byte : byte := repeat_of byte_bits false.
Definition zero_block : block := repeat_of block_bits false.

Definition bxor : list bool -> list bool -> list bool := CryptoLists.zip_with xorb.

Definition bits_of_byte (v : nat) : byte := bits_be_of byte_bits v.

Definition byte_value (b : byte) : nat :=
  fold_over (fun (acc : nat) (x : bool) => 2 * acc + (if x then 1 else 0)) 0 b.

Definition bytes_from (l : list nat) : list byte := map_over bits_of_byte l.

Definition block_from (l : list nat) : block := concat_of (bytes_from l).

Definition bytes_of (s : list bool) : list nat :=
  map_over byte_value (chunks_of (length_of s) byte_bits s).

Definition state_of_block (b : block) : state := chunks_of block_bytes byte_bits b.

Definition block_of_state (s : state) : block := concat_of s.

(* FIPS 197 numbers byte bits from the least significant bit; the list
   stores the most significant bit first. *)
Definition bit_num (b : byte) (i : nat) : bool :=
  bit_at b (byte_bits - 1 - Nat.modulo i byte_bits).

Definition byte_of_exponents (l : list nat) : byte :=
  map_over (fun j => mem_nat (byte_bits - 1 - j) l) (upto byte_bits).

Definition all_bytes : list byte := map_over bits_of_byte (upto (Nat.pow 2 byte_bits)).

Definition basis_bytes : list byte :=
  map_over (fun j => byte_of_exponents (j :: nil)) (upto byte_bits).

Definition one_byte : byte := byte_of_exponents (0 :: nil).

(* -------------------------------------------------------------------------
   GF(2^8), FIPS 197 s4.1 and s4.2. The modulus is written as its own exponent
   list, so the 0x1B every implementation carries is computed here rather than
   transcribed.
   ------------------------------------------------------------------------- *)

Definition aes_modulus_exponents : list nat := 8 :: 4 :: 3 :: 1 :: 0 :: nil.

Definition aes_modulus_low : byte := byte_of_exponents aes_modulus_exponents.

(* xtime: multiplication by x, which shifts the coefficients up by one and
   folds the modulus back in when the degree-7 coefficient leaves the byte. *)
Definition xtime (a : byte) : byte :=
  let shifted := drop_of 1 a ++ (false :: nil) in
  if bit_at a 0 then bxor shifted aes_modulus_low else shifted.

(* The bits of the second operand least significant first, each selecting a
   successive doubling of the first. *)
Fixpoint gmul_from (bs : list bool) (a : byte) : byte :=
  match bs with
  | nil => zero_byte
  | c :: r => bxor (if c then a else zero_byte) (gmul_from r (xtime a))
  end.

Definition gmul (a b : byte) : byte := gmul_from (rev_of b) a.

Definition gsquare (a : byte) : byte := gmul a a.

(* Compute a^254 with seven squarings and six products. In GF(2^8) this is
   the inverse of nonzero a and maps zero to zero, as FIPS 197 s5.1.1
   requires. *)
Fixpoint ginv_from (n : nat) (sq acc : byte) : byte :=
  match n with
  | 0 => acc
  | S k => let s := gsquare sq in ginv_from k s (gmul acc s)
  end.

Definition ginv (a : byte) : byte := ginv_from (byte_bits - 1) a one_byte.

(* -------------------------------------------------------------------------
   The affine transform, FIPS 197 s5.1.1, and its inverse, s5.3.2. Both are one
   definition parameterized by the taps and the constant, so an alternative
   constant is a different argument rather than a different function.
   ------------------------------------------------------------------------- *)

Definition affine_taps : list nat := 0 :: 4 :: 5 :: 6 :: 7 :: nil.

Definition affine_constant : byte := bits_of_byte 99.

Definition inv_affine_taps : list nat := 2 :: 5 :: 7 :: nil.

Definition inv_affine_constant : byte := bits_of_byte 5.

(* The standard's constant with its low bit dropped. It is an affine map like
   the standard's, so the S-box it produces is a bijection like the standard's,
   and it differs from the standard's in bit zero at every one of the 256
   inputs and nowhere else. *)
Definition wrong_affine_constant : byte := bits_of_byte 98.

Definition affine_over (c : byte) (taps : list nat) (b : byte) : byte :=
  map_over (fun j =>
              let i := byte_bits - 1 - j in
              fold_over (fun acc t => xorb acc (bit_num b (i + t))) (bit_num c i) taps)
           (upto byte_bits).

Definition sub_byte_over (c : byte) (b : byte) : byte := affine_over c affine_taps (ginv b).

Definition sub_byte (b : byte) : byte := sub_byte_over affine_constant b.

Definition sub_byte_with_the_wrong_constant (b : byte) : byte :=
  sub_byte_over wrong_affine_constant b.

Definition inv_sub_byte (b : byte) : byte :=
  ginv (affine_over inv_affine_constant inv_affine_taps b).

(* -------------------------------------------------------------------------
   The state, FIPS 197 s3.4: sixteen bytes flattened as r + 4c, which is the
   order the standard's own input mapping puts them in, so byte i of a block is
   byte i of the state with no reordering anywhere.
   ------------------------------------------------------------------------- *)

Definition state_index (r c : nat) : nat := r + rows * c.

Definition row_index (i : nat) : nat := Nat.modulo i rows.

Definition column_index (i : nat) : nat := Nat.div i rows.

Definition byte_of_state (s : state) (i : nat) : byte := nth_of i s zero_byte.

Definition permute (p : nat -> nat) (s : state) : state :=
  map_over (fun i => byte_of_state s (p i)) (upto block_bytes).

(* ShiftRows, FIPS 197 s5.1.2: row r moves left by r, so the byte written at
   (r, c) is read from (r, (c + r) mod 4). *)
Definition shift_rows_index (i : nat) : nat :=
  state_index (row_index i) (Nat.modulo (column_index i + row_index i) nb).

Definition inv_shift_rows_index (i : nat) : nat :=
  state_index (row_index i) (Nat.modulo (column_index i + nb - row_index i) nb).

(* ShiftRows under the incorrect transposed layout i = c + 4r. This
   permutation fixes four positions but agrees with the standard at only
   one position. *)
Definition transposed_shift_rows_index (i : nat) : nat :=
  Nat.modulo (Nat.modulo i nb + Nat.div i nb) nb + nb * Nat.div i nb.

Definition shift_rows (s : state) : state := permute shift_rows_index s.

Definition inv_shift_rows (s : state) : state := permute inv_shift_rows_index s.

Definition shift_rows_transposed (s : state) : state := permute transposed_shift_rows_index s.

(* -------------------------------------------------------------------------
   MixColumns, FIPS 197 s4.3 and s5.1.3. The step is multiplication by a fixed
   polynomial in GF(2^8)[x]/(x^4 + 1), written as that product rather than as
   the matrix the standard also prints, so the matrix is computed below and not
   transcribed.
   ------------------------------------------------------------------------- *)

Definition poly4_mul (a b : list byte) : list byte :=
  map_over (fun i =>
              fold_over (fun acc j =>
                           bxor acc (gmul (nth_of j a zero_byte)
                                          (nth_of (Nat.modulo (i + nb - Nat.modulo j nb) nb)
                                                  b zero_byte)))
                        zero_byte (upto nb))
           (upto nb).

Definition mix_polynomial : list byte := bytes_from (2 :: 1 :: 1 :: 3 :: nil).

Definition inv_mix_polynomial : list byte := bytes_from (14 :: 9 :: 13 :: 11 :: nil).

Definition mix_matrix (p : list byte) : list nat :=
  concat_of (map_over (fun i =>
                         map_over (fun k =>
                                     byte_value (nth_of (Nat.modulo (i + nb - Nat.modulo k nb) nb)
                                                        p zero_byte))
                                  (upto nb))
                      (upto nb)).

Definition mix_columns_over (p : list byte) (s : state) : state :=
  concat_of (map_over (fun c => poly4_mul p (take_of nb (drop_of (nb * c) s))) (upto nb)).

Definition mix_columns (s : state) : state := mix_columns_over mix_polynomial s.

Definition inv_mix_columns (s : state) : state := mix_columns_over inv_mix_polynomial s.

(* The thirty-two columns with a single bit set, which span the column space
   over GF(2) and are what the round trip below is enumerated on. *)
Definition single_bit_columns : list (list byte) :=
  concat_of (map_over
               (fun p => map_over
                           (fun e => map_over
                                       (fun q => if Nat.eqb p q
                                                 then byte_of_exponents (e :: nil)
                                                 else zero_byte)
                                       (upto nb))
                           (upto byte_bits))
               (upto nb)).

(* -------------------------------------------------------------------------
   AddRoundKey, FIPS 197 s5.1.4, which is the exclusive-or of two states and is
   therefore an involution in the key.
   ------------------------------------------------------------------------- *)

Fixpoint xor_bytes (a b : list byte) : list byte :=
  match a with
  | nil => nil
  | x :: xs => match b with nil => nil | y :: ys => bxor x y :: xor_bytes xs ys end
  end.

Definition add_round_key (k s : state) : state := xor_bytes s k.

(* -------------------------------------------------------------------------
   The key expansion, FIPS 197 s5.2. The round constants are x^(i-1) in
   GF(2^8), derived from the doubling recurrence rather than transcribed.
   ------------------------------------------------------------------------- *)

Fixpoint gpow_x (j : nat) : byte :=
  match j with 0 => one_byte | S k => xtime (gpow_x k) end.

Definition rcon_word (i : nat) : list byte :=
  gpow_x (i - 1) :: zero_byte :: zero_byte :: zero_byte :: nil.

Definition rot_word (w : list byte) : list byte := drop_of 1 w ++ take_of 1 w.

Definition sub_word_over (sb : byte -> byte) (w : list byte) : list byte := map_over sb w.

(* The accumulator holds the words already produced, so `nth_of (i - 1)` is the
   one just written and `nth_of (i - nk)` is the one a key length back. The
   second branch is the one only a key of more than six words reaches, which is
   the clause an AES-128 vector cannot see. *)
Fixpoint expand_from (fuel : nat) (sb : byte -> byte) (guard nk i : nat)
                     (acc : list (list byte)) : list (list byte) :=
  match fuel with
  | 0 => acc
  | S f =>
      let prev := nth_of (i - 1) acc nil in
      let temp :=
        if Nat.eqb (Nat.modulo i nk) 0
        then xor_bytes (sub_word_over sb (rot_word prev)) (rcon_word (Nat.div i nk))
        else if andb (Nat.ltb guard nk) (Nat.eqb (Nat.modulo i nk) 4)
             then sub_word_over sb prev
             else prev in
      expand_from f sb guard nk (S i) (acc ++ (xor_bytes (nth_of (i - nk) acc nil) temp :: nil))
  end.

(* FIPS 197 s5.2 requires Nk > 6 for the second substitution. Raising the
   guard to 7 preserves every standard key length (Nk = 4, 6, 8), so the
   distinguishing check uses Nk = 7 on the expansion function. *)
Definition second_substitution_guard : nat := 6.

Definition raised_substitution_guard : nat := 7.

Definition rounds_for (nk : nat) : nat := nk + 6.

Definition key_schedule_over (sb : byte -> byte) (guard nk : nat) (key : list byte)
  : list (list byte) :=
  expand_from (nb * (rounds_for nk + 1) - nk) sb guard nk nk (chunks_of nk nb key).

Definition key_schedule (nk : nat) (key : list byte) : list (list byte) :=
  key_schedule_over sub_byte second_substitution_guard nk key.

Definition round_key (sched : list (list byte)) (r : nat) : state :=
  concat_of (take_of nb (drop_of (nb * r) sched)).

(* -------------------------------------------------------------------------
   The cipher and the inverse cipher, FIPS 197 s5.1 and s5.3. Both are
   parameterized over the byte substitution and over the row shift, so each
   near alternative below is one argument changed and nothing else.
   ------------------------------------------------------------------------- *)

Definition aes_round_over (sb : byte -> byte) (sr : state -> state) (k s : state) : state :=
  add_round_key k (mix_columns (sr (map_over sb s))).

Definition aes_final_round_over (sb : byte -> byte) (sr : state -> state) (k s : state) : state :=
  add_round_key k (sr (map_over sb s)).

Definition encrypt_over (sb : byte -> byte) (sr : state -> state)
                        (sched : list (list byte)) (nr : nat) (blk : state) : state :=
  let s0 := add_round_key (round_key sched 0) blk in
  let s := fold_over (fun s r => aes_round_over sb sr (round_key sched r) s)
                     s0 (up_from 1 (nr - 1)) in
  aes_final_round_over sb sr (round_key sched nr) s.

Definition encrypt_with (sched : list (list byte)) (nr : nat) (blk : state) : state :=
  encrypt_over sub_byte shift_rows sched nr blk.

Definition aes_encrypt_over (sb : byte -> byte) (sr : state -> state)
                            (nk : nat) (key : list byte) (blk : state) : state :=
  encrypt_over sb sr (key_schedule_over sb second_substitution_guard nk key)
               (rounds_for nk) blk.

Definition aes_encrypt (nk : nat) (key : list byte) (blk : state) : state :=
  aes_encrypt_over sub_byte shift_rows nk key blk.

Definition inv_round (k s : state) : state :=
  inv_mix_columns (add_round_key k (map_over inv_sub_byte (inv_shift_rows s))).

Definition aes_decrypt (nk : nat) (key : list byte) (blk : state) : state :=
  let sched := key_schedule nk key in
  let nr := rounds_for nk in
  let s0 := add_round_key (round_key sched nr) blk in
  let s := fold_over (fun s r => inv_round (round_key sched r) s)
                     s0 (rev_of (up_from 1 (nr - 1))) in
  add_round_key (round_key sched 0) (map_over inv_sub_byte (inv_shift_rows s)).

(* -------------------------------------------------------------------------
   GF(2^128), SP 800-38D s6.3. R is written as its own exponent list, so the
   0xE1 every implementation carries is computed rather than transcribed, and
   Algorithm 1 is transcribed clause for clause: the leftmost bit of X selects
   the first partial product, and multiplying by the generator shifts the whole
   string one place to the **right**, folding R in at the left end when the
   rightmost coefficient leaves the block.
   ------------------------------------------------------------------------- *)

Definition ghash_modulus_exponents : list nat := 128 :: 7 :: 2 :: 1 :: 0 :: nil.

Definition ghash_R : block :=
  map_over (fun i => mem_nat i ghash_modulus_exponents) (upto block_bits).

Definition shift_right_1 (v : block) : block := false :: take_of (block_bits - 1) v.

Definition gf128_double (v : block) : block :=
  let s := shift_right_1 v in
  if bit_at v (block_bits - 1) then bxor s ghash_R else s.

Fixpoint gf128_mul_from (xs : list bool) (v z : block) : block :=
  match xs with
  | nil => z
  | x :: r => gf128_mul_from r (gf128_double v) (if x then bxor z v else z)
  end.

Definition gf128_mul (x y : block) : block := gf128_mul_from x y zero_block.

(* The model's equivalent GF(2^128) representation: zvkg_insts.sail stores
   byte 0 in the low eight bits, applies brev8 within each byte, then
   multiplies by left shifts with reduction 0x87. The variant without
   reflection below tests the bit-order error. *)

Definition sail_word_of_block (b : block) : list bool :=
  concat_of (rev_of (state_of_block b)).

Definition block_of_sail_word (v : list bool) : block :=
  concat_of (rev_of (chunks_of block_bytes byte_bits v)).

Definition brev8 (v : list bool) : list bool :=
  concat_of (map_over rev_of (chunks_of block_bytes byte_bits v)).

Definition reflect_block (b : block) : block :=
  concat_of (map_over rev_of (state_of_block b)).

Definition sail_reduction : byte := bits_of_byte 135.

Definition sail_shift_left (h : list bool) : list bool :=
  let s := drop_of 1 h ++ (false :: nil) in
  if bit_at h 0
  then take_of (block_bits - byte_bits) s
       ++ bxor (drop_of (block_bits - byte_bits) s) sail_reduction
  else s.

Fixpoint sail_gmul_from (bs : list bool) (h z : list bool) : list bool :=
  match bs with
  | nil => z
  | x :: r => sail_gmul_from r (sail_shift_left h) (if x then bxor z h else z)
  end.

(* The model walks bit index 0 upward and its bit 0 is the last element of a
   most significant first word, so the walk is over the reversal. *)
Definition sail_gmul (s h : list bool) : list bool :=
  sail_gmul_from (rev_of s) h zero_block.

Definition ghash_mul_the_models_way (x y : block) : block :=
  block_of_sail_word (brev8 (sail_gmul (brev8 (sail_word_of_block x))
                                       (brev8 (sail_word_of_block y)))).

Definition ghash_mul_without_the_reflection (x y : block) : block :=
  block_of_sail_word (sail_gmul (sail_word_of_block x) (sail_word_of_block y)).

(* -------------------------------------------------------------------------
   GHASH, the counter, and GCTR: SP 800-38D s6.4, s6.2 and s6.5.
   ------------------------------------------------------------------------- *)

Definition ghash_over (mul : block -> block -> block) (h : block) (x : list bool) : block :=
  fold_over (fun y blk => mul (bxor y blk) h) zero_block
            (chunks_of (S (Nat.div (length_of x) block_bits)) block_bits x).

Definition ghash (h : block) (x : list bool) : block := ghash_over gf128_mul h x.

Definition counter_bits : nat := 32.

(* Incrementing the counter field is carry propagation over its own bits, so
   the wrap at 2^32 is the carry falling off the end and no power of two is
   ever constructed. *)
Fixpoint increment_lsb_first (l : list bool) : list bool :=
  match l with
  | nil => nil
  | b :: r => if b then false :: increment_lsb_first r else true :: r
  end.

Definition inc32 (x : block) : block :=
  take_of (block_bits - counter_bits) x
  ++ rev_of (increment_lsb_first (rev_of (drop_of (block_bits - counter_bits) x))).

Fixpoint gctr_from (fuel : nat) (sched : list (list byte)) (nr : nat)
                   (cb : block) (x : list bool) : list bool :=
  match fuel with
  | 0 => nil
  | S k => if x is nil then nil
           else bxor (take_of block_bits x)
                     (block_of_state (encrypt_with sched nr (state_of_block cb)))
                ++ gctr_from k sched nr (inc32 cb) (drop_of block_bits x)
  end.

Definition gctr (sched : list (list byte)) (nr : nat) (icb : block) (x : list bool) : list bool :=
  gctr_from (S (Nat.div (length_of x) block_bits)) sched nr icb x.

(* -------------------------------------------------------------------------
   AES-GCM, SP 800-38D s7.1 and s7.2. The whole construction is parameterized
   over the GHASH input and over the first counter block, so the two near
   alternatives below are one argument changed and nothing else.
   ------------------------------------------------------------------------- *)

Definition nonce_split : nat := 96.

Definition length_field_bits : nat := 64.

Definition gcm_pad (n : nat) : nat :=
  Nat.modulo (block_bits - Nat.modulo n block_bits) block_bits.

Definition ghash_input_padded (aad c : list bool) : list bool :=
  aad ++ repeat_of (gcm_pad (length_of aad)) false
      ++ c ++ repeat_of (gcm_pad (length_of c)) false
      ++ bits_be_of length_field_bits (length_of aad)
      ++ bits_be_of length_field_bits (length_of c).

(* The same input with A and C run together unpadded. It agrees with the
   standard's at every input whose associated data and ciphertext are both
   block-aligned, which is three of the five published cases. *)
Definition ghash_input_unpadded (aad c : list bool) : list bool :=
  aad ++ c ++ bits_be_of length_field_bits (length_of aad)
          ++ bits_be_of length_field_bits (length_of c).

Definition gcm_j0 (h : block) (iv : list bool) : block :=
  if Nat.eqb (length_of iv) nonce_split
  then iv ++ repeat_of (counter_bits - 1) false ++ (true :: nil)
  else ghash h (iv ++ repeat_of (gcm_pad (length_of iv)) false
                   ++ repeat_of length_field_bits false
                   ++ bits_be_of length_field_bits (length_of iv)).

Definition gcm_subkey (sched : list (list byte)) (nr : nat) : block :=
  block_of_state (encrypt_with sched nr (state_of_block zero_block)).

Definition gcm_over (gin : list bool -> list bool -> list bool)
                    (first_counter : block -> block)
                    (nk : nat) (key : list byte) (iv aad m : list bool)
  : (list bool * block) :=
  let sched := key_schedule nk key in
  let nr := rounds_for nk in
  let h := gcm_subkey sched nr in
  let j0 := gcm_j0 h iv in
  let c := gctr sched nr (first_counter j0) m in
  pair c (gctr sched nr j0 (ghash h (gin aad c))).

Definition gcm_encrypt (nk : nat) (key : list byte) (iv aad m : list bool)
  : (list bool * block) := gcm_over ghash_input_padded inc32 nk key iv aad m.

Definition gcm_encrypt_unpadded (nk : nat) (key : list byte) (iv aad m : list bool)
  : (list bool * block) := gcm_over ghash_input_unpadded inc32 nk key iv aad m.

(* The counter mode started at J0 rather than at inc32(J0), which is the
   off-by-one that makes the tag block and the first keystream block one thing.
   It agrees with the standard's at every empty plaintext, which is one of the
   five published cases. *)
Definition gcm_encrypt_from_j0 (nk : nat) (key : list byte) (iv aad m : list bool)
  : (list bool * block) := gcm_over ghash_input_padded (fun j => j) nk key iv aad m.

(* Authenticated decryption, SP 800-38D s7.2. Tag failure returns None with
   no plaintext. The structural tag comparison has no constant-time
   guarantee; R-05-062 and R-05-067 require that guarantee on the binary. *)
Definition gcm_open (t_bits nk : nat) (key : list byte) (iv aad c t : list bool)
  : option (list bool) :=
  let sched := key_schedule nk key in
  let nr := rounds_for nk in
  let h := gcm_subkey sched nr in
  let j0 := gcm_j0 h iv in
  let expected := take_of t_bits (gctr sched nr j0 (ghash h (ghash_input_padded aad c))) in
  if bits_eqb expected t then Some (gctr sched nr (inc32 j0) c) else None.

(* -------------------------------------------------------------------------
   The five magnitudes the register leaves to composition, as fields rather
   than as literals. Four of them reach the primitive and the fifth does not,
   which is what the theorem below says and what makes carrying it a statement
   of the gap rather than a decision taken by fiat.
   ------------------------------------------------------------------------- *)

(* SP 800-38D s5.2.1.2's two lists, written here as what the standard admits
   and never as what the platform takes: the register chooses from neither. *)
Definition admissible_tag_lengths : list nat := 128 :: 120 :: 112 :: 104 :: 96 :: nil.

Definition restricted_tag_lengths : list nat := 64 :: 32 :: nil.

Record AeadParameters : Type := {
  key_words : nat;
  tag_bits : nat;
  nonce : list bool;
  associated_data : list bool;
  invocations_per_key : option nat
}.

Definition seal_under (p : AeadParameters) (key : list byte) (m : list bool)
  : (list bool * list bool) :=
  let r := gcm_encrypt (key_words p) key (nonce p) (associated_data p) m in
  pair (fst r) (take_of (tag_bits p) (snd r)).

(* The three key lengths FIPS 197 carries, each at the 96-bit nonce SP 800-38D
   splits at, an empty associated data and the full tag. `demo` is the first
   published GCM case whole: its key is the all-zero AES-128 key and its nonce
   the all-zero 96-bit IV. *)
Definition demo : AeadParameters :=
  {| key_words := 4; tag_bits := block_bits; nonce := repeat_of nonce_split false;
     associated_data := nil; invocations_per_key := None |}.

Definition demo_aes192 : AeadParameters :=
  {| key_words := 6; tag_bits := block_bits; nonce := repeat_of nonce_split false;
     associated_data := nil; invocations_per_key := None |}.

Definition demo_aes256 : AeadParameters :=
  {| key_words := 8; tag_bits := block_bits; nonce := repeat_of nonce_split false;
     associated_data := nil; invocations_per_key := None |}.

Definition shortest_admissible_tag : nat := nth_of 4 admissible_tag_lengths 0.

Definition demo_truncated_tag : AeadParameters :=
  {| key_words := 4; tag_bits := shortest_admissible_tag;
     nonce := repeat_of nonce_split false;
     associated_data := nil; invocations_per_key := None |}.

(* A stated usage bound that the reference does not enforce. *)
Definition demo_with_a_stated_bound : AeadParameters :=
  {| key_words := 4; tag_bits := block_bits; nonce := repeat_of nonce_split false;
     associated_data := nil; invocations_per_key := Some 1 |}.

Definition demo_key : list byte := repeat_of block_bytes zero_byte.

Theorem the_seal_reads_four_fields_and_the_invocation_bound_is_not_one_of_them :
  forall p q : AeadParameters,
    key_words p = key_words q ->
    tag_bits p = tag_bits q ->
    nonce p = nonce q ->
    associated_data p = associated_data q ->
    forall (key : list byte) (m : list bool), seal_under p key m = seal_under q key m.
Proof.
  intros p q Hk Ht Hn Ha key m. unfold seal_under.
  rewrite Hk, Ht, Hn, Ha. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   The derived tables against the published ones. This is what makes the pair
   with the curated model a differential pair: types_kext.sail writes the
   S-box out as a 256-entry vector and decodes the round constants by a case
   table, and this file computes both from the standard's own construction.
   ------------------------------------------------------------------------- *)

Example the_derived_sbox_is_the_published_table :
  map_over (fun b => byte_value (sub_byte b)) all_bytes =
  0x63 :: 0x7C :: 0x77 :: 0x7B :: 0xF2 :: 0x6B :: 0x6F :: 0xC5 ::
  0x30 :: 0x01 :: 0x67 :: 0x2B :: 0xFE :: 0xD7 :: 0xAB :: 0x76 ::
  0xCA :: 0x82 :: 0xC9 :: 0x7D :: 0xFA :: 0x59 :: 0x47 :: 0xF0 ::
  0xAD :: 0xD4 :: 0xA2 :: 0xAF :: 0x9C :: 0xA4 :: 0x72 :: 0xC0 ::
  0xB7 :: 0xFD :: 0x93 :: 0x26 :: 0x36 :: 0x3F :: 0xF7 :: 0xCC ::
  0x34 :: 0xA5 :: 0xE5 :: 0xF1 :: 0x71 :: 0xD8 :: 0x31 :: 0x15 ::
  0x04 :: 0xC7 :: 0x23 :: 0xC3 :: 0x18 :: 0x96 :: 0x05 :: 0x9A ::
  0x07 :: 0x12 :: 0x80 :: 0xE2 :: 0xEB :: 0x27 :: 0xB2 :: 0x75 ::
  0x09 :: 0x83 :: 0x2C :: 0x1A :: 0x1B :: 0x6E :: 0x5A :: 0xA0 ::
  0x52 :: 0x3B :: 0xD6 :: 0xB3 :: 0x29 :: 0xE3 :: 0x2F :: 0x84 ::
  0x53 :: 0xD1 :: 0x00 :: 0xED :: 0x20 :: 0xFC :: 0xB1 :: 0x5B ::
  0x6A :: 0xCB :: 0xBE :: 0x39 :: 0x4A :: 0x4C :: 0x58 :: 0xCF ::
  0xD0 :: 0xEF :: 0xAA :: 0xFB :: 0x43 :: 0x4D :: 0x33 :: 0x85 ::
  0x45 :: 0xF9 :: 0x02 :: 0x7F :: 0x50 :: 0x3C :: 0x9F :: 0xA8 ::
  0x51 :: 0xA3 :: 0x40 :: 0x8F :: 0x92 :: 0x9D :: 0x38 :: 0xF5 ::
  0xBC :: 0xB6 :: 0xDA :: 0x21 :: 0x10 :: 0xFF :: 0xF3 :: 0xD2 ::
  0xCD :: 0x0C :: 0x13 :: 0xEC :: 0x5F :: 0x97 :: 0x44 :: 0x17 ::
  0xC4 :: 0xA7 :: 0x7E :: 0x3D :: 0x64 :: 0x5D :: 0x19 :: 0x73 ::
  0x60 :: 0x81 :: 0x4F :: 0xDC :: 0x22 :: 0x2A :: 0x90 :: 0x88 ::
  0x46 :: 0xEE :: 0xB8 :: 0x14 :: 0xDE :: 0x5E :: 0x0B :: 0xDB ::
  0xE0 :: 0x32 :: 0x3A :: 0x0A :: 0x49 :: 0x06 :: 0x24 :: 0x5C ::
  0xC2 :: 0xD3 :: 0xAC :: 0x62 :: 0x91 :: 0x95 :: 0xE4 :: 0x79 ::
  0xE7 :: 0xC8 :: 0x37 :: 0x6D :: 0x8D :: 0xD5 :: 0x4E :: 0xA9 ::
  0x6C :: 0x56 :: 0xF4 :: 0xEA :: 0x65 :: 0x7A :: 0xAE :: 0x08 ::
  0xBA :: 0x78 :: 0x25 :: 0x2E :: 0x1C :: 0xA6 :: 0xB4 :: 0xC6 ::
  0xE8 :: 0xDD :: 0x74 :: 0x1F :: 0x4B :: 0xBD :: 0x8B :: 0x8A ::
  0x70 :: 0x3E :: 0xB5 :: 0x66 :: 0x48 :: 0x03 :: 0xF6 :: 0x0E ::
  0x61 :: 0x35 :: 0x57 :: 0xB9 :: 0x86 :: 0xC1 :: 0x1D :: 0x9E ::
  0xE1 :: 0xF8 :: 0x98 :: 0x11 :: 0x69 :: 0xD9 :: 0x8E :: 0x94 ::
  0x9B :: 0x1E :: 0x87 :: 0xE9 :: 0xCE :: 0x55 :: 0x28 :: 0xDF ::
  0x8C :: 0xA1 :: 0x89 :: 0x0D :: 0xBF :: 0xE6 :: 0x42 :: 0x68 ::
  0x41 :: 0x99 :: 0x2D :: 0x0F :: 0xB0 :: 0x54 :: 0xBB :: 0x16 :: nil.
Proof. vm_reflexivity. Qed.

Example the_derived_round_constants_are_the_published_table :
  map_over (fun i => byte_value (gpow_x i)) (upto 10) =
  0x01 :: 0x02 :: 0x04 :: 0x08 :: 0x10 ::
  0x20 :: 0x40 :: 0x80 :: 0x1B :: 0x36 :: nil.
Proof. vm_reflexivity. Qed.

Example the_derived_mix_matrix_is_the_published_one :
  mix_matrix mix_polynomial =
  0x02 :: 0x03 :: 0x01 :: 0x01 ::
  0x01 :: 0x02 :: 0x03 :: 0x01 ::
  0x01 :: 0x01 :: 0x02 :: 0x03 ::
  0x03 :: 0x01 :: 0x01 :: 0x02 :: nil.
Proof. vm_reflexivity. Qed.

Example the_derived_inverse_mix_matrix_is_the_published_one :
  mix_matrix inv_mix_polynomial =
  0x0E :: 0x0B :: 0x0D :: 0x09 ::
  0x09 :: 0x0E :: 0x0B :: 0x0D ::
  0x0D :: 0x09 :: 0x0E :: 0x0B ::
  0x0B :: 0x0D :: 0x09 :: 0x0E :: nil.
Proof. vm_reflexivity. Qed.

Example the_low_half_of_the_modulus_is_the_published_byte :
  byte_value aes_modulus_low = 0x1B := eq_refl.

Example the_ghash_reduction_string_is_the_published_one :
  bytes_of ghash_R =
  0xE1 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 ::
  0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: nil.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   The cipher against FIPS 197's own published answers, at all three key
   lengths. Every key, plaintext and ciphertext is a constant inside the
   statement that decides against it.
   ------------------------------------------------------------------------- *)

(*| discharges: R-10-024 |*)
Example the_appendix_b_example_reaches_the_published_ciphertext :
  map_over byte_value
    (aes_encrypt 4
       (bytes_from (0x2B :: 0x7E :: 0x15 :: 0x16 :: 0x28 :: 0xAE :: 0xD2 :: 0xA6 ::
                    0xAB :: 0xF7 :: 0x15 :: 0x88 :: 0x09 :: 0xCF :: 0x4F :: 0x3C :: nil))
       (bytes_from (0x32 :: 0x43 :: 0xF6 :: 0xA8 :: 0x88 :: 0x5A :: 0x30 :: 0x8D ::
                    0x31 :: 0x31 :: 0x98 :: 0xA2 :: 0xE0 :: 0x37 :: 0x07 :: 0x34 :: nil))) =
  0x39 :: 0x25 :: 0x84 :: 0x1D :: 0x02 :: 0xDC :: 0x09 :: 0xFB ::
  0xDC :: 0x11 :: 0x85 :: 0x97 :: 0x19 :: 0x6A :: 0x0B :: 0x32 :: nil.
Proof. vm_reflexivity. Qed.

(* The first expanded round key of the same schedule, which is FIPS 197
   Appendix A.1's w4 through w7, and the last, which is w40 through w43. The
   pair fixes both ends of the expansion, where a ciphertext alone fixes the
   composition. *)
Example the_first_expanded_round_key_is_the_published_one :
  map_over byte_value
    (round_key (key_schedule 4
       (bytes_from (0x2B :: 0x7E :: 0x15 :: 0x16 :: 0x28 :: 0xAE :: 0xD2 :: 0xA6 ::
                    0xAB :: 0xF7 :: 0x15 :: 0x88 :: 0x09 :: 0xCF :: 0x4F :: 0x3C :: nil))) 1) =
  0xA0 :: 0xFA :: 0xFE :: 0x17 :: 0x88 :: 0x54 :: 0x2C :: 0xB1 ::
  0x23 :: 0xA3 :: 0x39 :: 0x39 :: 0x2A :: 0x6C :: 0x76 :: 0x05 :: nil.
Proof. vm_reflexivity. Qed.

Example the_last_expanded_round_key_is_the_published_one :
  map_over byte_value
    (round_key (key_schedule 4
       (bytes_from (0x2B :: 0x7E :: 0x15 :: 0x16 :: 0x28 :: 0xAE :: 0xD2 :: 0xA6 ::
                    0xAB :: 0xF7 :: 0x15 :: 0x88 :: 0x09 :: 0xCF :: 0x4F :: 0x3C :: nil))) 10) =
  0xD0 :: 0x14 :: 0xF9 :: 0xA8 :: 0xC9 :: 0xEE :: 0x25 :: 0x89 ::
  0xE1 :: 0x3F :: 0x0C :: 0xC8 :: 0xB6 :: 0x63 :: 0x0C :: 0xA6 :: nil.
Proof. vm_reflexivity. Qed.

(*| discharges: R-10-024 |*)
Example the_appendix_c_one_example_reaches_the_published_ciphertext :
  map_over byte_value
    (aes_encrypt 4 (bytes_from (upto 16))
       (bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                    0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil))) =
  0x69 :: 0xC4 :: 0xE0 :: 0xD8 :: 0x6A :: 0x7B :: 0x04 :: 0x30 ::
  0xD8 :: 0xCD :: 0xB7 :: 0x80 :: 0x70 :: 0xB4 :: 0xC5 :: 0x5A :: nil.
Proof. vm_reflexivity. Qed.

(*| discharges: R-10-024 |*)
Example the_appendix_c_two_example_reaches_the_published_ciphertext :
  map_over byte_value
    (aes_encrypt 6 (bytes_from (upto 24))
       (bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                    0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil))) =
  0xDD :: 0xA9 :: 0x7C :: 0xA4 :: 0x86 :: 0x4C :: 0xDF :: 0xE0 ::
  0x6E :: 0xAF :: 0x70 :: 0xA0 :: 0xEC :: 0x0D :: 0x71 :: 0x91 :: nil.
Proof. vm_reflexivity. Qed.

(*| discharges: R-10-024 |*)
Example the_appendix_c_three_example_reaches_the_published_ciphertext :
  map_over byte_value
    (aes_encrypt 8 (bytes_from (upto 32))
       (bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                    0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil))) =
  0x8E :: 0xA2 :: 0xB7 :: 0xCA :: 0x51 :: 0x67 :: 0x45 :: 0xBF ::
  0xEA :: 0xFC :: 0x49 :: 0x90 :: 0x4B :: 0x49 :: 0x60 :: 0x89 :: nil.
Proof. vm_reflexivity. Qed.

(* The inverse cipher recovers the plaintext at each of the three key lengths,
   which is the whole-cipher half of the invertibility account and a value
   rather than a proof. *)
Example the_inverse_cipher_recovers_the_plaintext_at_every_key_length :
  all_of (fun nk =>
            let p := bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                                 0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil) in
            let k := bytes_from (upto (4 * nk)) in
            bits_eqb (block_of_state (aes_decrypt nk k (aes_encrypt nk k p)))
                     (block_of_state p))
         (4 :: 6 :: 8 :: nil) = true.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   The step maps, over arbitrary inputs or over the whole domain they act on.
   ------------------------------------------------------------------------- *)

(* Compute the 256 map results once, then compare all 65,536 pairs. *)
Definition is_a_bijection_on_bytes (f : byte -> byte) : bool :=
  let image := map_over f all_bytes in
  all_of (fun b => Nat.eqb (count_where (fun a => bits_eqb a b) image) 1) all_bytes.

Example sub_byte_is_a_bijection_on_a_byte :
  is_a_bijection_on_bytes sub_byte = true.
Proof. vm_reflexivity. Qed.

Example the_inverse_substitution_recovers_every_byte :
  all_of (fun b => bits_eqb (inv_sub_byte (sub_byte b)) b) all_bytes = true.
Proof. vm_reflexivity. Qed.

Example the_field_inverse_is_an_inverse_at_every_nonzero_byte :
  all_of (fun b => if bits_eqb b zero_byte
                   then bits_eqb (ginv b) zero_byte
                   else bits_eqb (gmul b (ginv b)) one_byte)
         all_bytes = true.
Proof. vm_reflexivity. Qed.

(* The field multiplication is commutative over the whole of its domain, which
   is 65,536 pairs and not a sample. *)
Example the_field_multiplication_is_commutative :
  all_of (fun a => all_of (fun b => bits_eqb (gmul a b) (gmul b a)) all_bytes) all_bytes = true.
Proof. vm_reflexivity. Qed.

Example one_is_the_identity_and_zero_the_annihilator :
  all_of (fun a => andb (bits_eqb (gmul one_byte a) a)
                        (bits_eqb (gmul zero_byte a) zero_byte))
         all_bytes = true.
Proof. vm_reflexivity. Qed.

(* Distribution and association over every element in the first argument and
   over the eight basis elements in the other two, the basis being what spans
   the additive group. The domain is named because it is not the whole one. *)
Example the_field_multiplication_distributes_over_the_basis :
  all_of (fun a => all_of (fun b => all_of (fun c =>
            bits_eqb (gmul a (bxor b c)) (bxor (gmul a b) (gmul a c)))
            basis_bytes) basis_bytes) all_bytes = true.
Proof. vm_reflexivity. Qed.

Example the_field_multiplication_associates_over_the_basis :
  all_of (fun a => all_of (fun b => all_of (fun c =>
            bits_eqb (gmul (gmul a b) c) (gmul a (gmul b c)))
            basis_bytes) basis_bytes) all_bytes = true.
Proof. vm_reflexivity. Qed.

Definition covers_each_index_once (l : list nat) (n : nat) : bool :=
  all_of (fun i => Nat.eqb (count_where (fun v => Nat.eqb v i) l) 1) (upto n).

Example shift_rows_is_a_permutation_of_the_sixteen_positions :
  covers_each_index_once (map_over shift_rows_index (upto block_bytes)) block_bytes = true
  := eq_refl.

Example the_inverse_row_shift_is_a_permutation_too :
  covers_each_index_once (map_over inv_shift_rows_index (upto block_bytes)) block_bytes = true
  := eq_refl.

(* And it recovers a state whose sixteen bytes are sixteen arbitrary bytes,
   which is what a known answer cannot show. *)
Lemma inverse_row_index_conditions : forall i : nat,
  ProofSupport.Member i (upto block_bytes) ->
  Nat.ltb (inv_shift_rows_index i) block_bytes = true /\
  shift_rows_index (inv_shift_rows_index i) = i.
Proof.
  intros i Hi.
  assert (Hindices : ProofSupport.all_of (fun j =>
    andb (Nat.ltb (inv_shift_rows_index j) block_bytes)
      (Nat.eqb (shift_rows_index (inv_shift_rows_index j)) j)) (upto block_bytes) = true).
  { reflexivity. }
  pose proof (ProofSupport.all_of_member nat _ (upto block_bytes) i Hindices Hi) as H.
  destruct (ProofSupport.andb_split _ _ H) as [Hbound Hinverse].
  split; [exact Hbound | exact (ProofSupport.nat_eqb_true _ _ Hinverse)].
Qed.

Theorem row_shift_inverse_for_state_length : forall s : state,
  length_of s = block_bytes -> inv_shift_rows (shift_rows s) = s.
Proof.
  intros s Hlength. unfold inv_shift_rows, shift_rows, permute, byte_of_state, upto.
  apply (CryptoLists.gather_inverse byte block_bytes shift_rows_index inv_shift_rows_index s zero_byte).
  - exact Hlength.
  - intros i Hi. exact (proj1 (inverse_row_index_conditions i Hi)).
  - intros i Hi. exact (proj2 (inverse_row_index_conditions i Hi)).
Qed.

Theorem the_row_shift_is_invertible_on_an_arbitrary_state :
  forall b0 b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 b11 b12 b13 b14 b15 : byte,
    inv_shift_rows (shift_rows (
      b0 :: b1 :: b2 :: b3 :: b4 :: b5 :: b6 :: b7 ::
      b8 :: b9 :: b10 :: b11 :: b12 :: b13 :: b14 :: b15 :: nil))
    =
    b0 :: b1 :: b2 :: b3 :: b4 :: b5 :: b6 :: b7 ::
    b8 :: b9 :: b10 :: b11 :: b12 :: b13 :: b14 :: b15 :: nil.
Proof. intros. apply row_shift_inverse_for_state_length. reflexivity. Qed.

(* AddRoundKey is an involution in the round key, over arbitrary bits. *)
Lemma xorb_cancels : forall x y : bool, xorb (xorb x y) y = x.
Proof. exact CryptoLists.xorb_cancels. Qed.

Lemma bxor_cancels : forall a k : list bool, length_of a = length_of k -> bxor (bxor a k) k = a.
Proof.
  exact CryptoLists.xor_involution.
Qed.

Lemma eqb_nat_eq : forall m n : nat, Nat.eqb m n = true -> m = n.
Proof.
  induction m as [|m IH]; intros [|n] H; try discriminate H.
  - reflexivity.
  - simpl in H. rewrite (IH n H). reflexivity.
Qed.

(* Two states of the same shape: the same number of bytes, each of the same
   width. The hypothesis is stated because a state and a round key of
   different shapes are xored to the shorter of the two, and an involution
   over that is a claim about truncation rather than about the key. *)
Fixpoint same_shape (a b : state) : bool :=
  match a with
  | nil => if b is nil then true else false
  | x :: xs => match b with
               | nil => false
               | y :: ys => andb (Nat.eqb (length_of x) (length_of y)) (same_shape xs ys)
               end
  end.

Theorem add_round_key_is_an_involution_in_the_round_key :
  forall s k : state, same_shape s k = true -> add_round_key k (add_round_key k s) = s.
Proof.
  unfold add_round_key. induction s as [|x s IH]; intros [|y k] H; try discriminate H.
  - reflexivity.
  - simpl in H. apply andb_prop in H as [E Hs]. simpl.
    rewrite (bxor_cancels x y (eqb_nat_eq _ _ E)), (IH k Hs). reflexivity.
Qed.

Example the_round_key_and_the_state_have_the_same_shape :
  same_shape (state_of_block (block_from (upto block_bytes)))
             (round_key (key_schedule 4 (bytes_from (upto block_bytes))) 3) = true.
Proof. vm_reflexivity. Qed.

(* MixColumns' polynomials are inverse, and the round trip is checked on
   the thirty-two GF(2) basis columns. Extending this check to all columns
   requires a linearity proof, which this file does not supply. *)
Example the_two_mix_polynomials_are_inverse_modulo_x_to_the_fourth_plus_one :
  map_over byte_value (poly4_mul mix_polynomial inv_mix_polynomial) = 1 :: 0 :: 0 :: 0 :: nil.
Proof. vm_reflexivity. Qed.

Example there_are_thirty_two_single_bit_columns :
  length_of single_bit_columns = 32 := eq_refl.

Example the_inverse_polynomial_recovers_every_single_bit_column :
  all_of (fun col => bits_eqb (concat_of (poly4_mul inv_mix_polynomial (poly4_mul mix_polynomial col)))
                              (concat_of col))
         single_bit_columns = true.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   The three near alternatives to a step map, each held to the single
   difference it exists to exhibit and each shown to keep the obligations it
   does not break.
   ------------------------------------------------------------------------- *)

Example the_wrong_affine_constant_is_still_a_bijection :
  is_a_bijection_on_bytes sub_byte_with_the_wrong_constant = true.
Proof. vm_reflexivity. Qed.

Example the_wrong_affine_constant_moves_the_low_bit_and_nothing_else :
  all_of (fun b => Nat.eqb (byte_value (bxor (sub_byte b) (sub_byte_with_the_wrong_constant b))) 1)
         all_bytes = true.
Proof. vm_reflexivity. Qed.

Example the_wrong_affine_constant_misses_the_published_ciphertext :
  bits_eqb (block_of_state
              (aes_encrypt_over sub_byte_with_the_wrong_constant shift_rows 4
                 (bytes_from (upto 16))
                 (bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                              0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil))))
           (block_from (0x69 :: 0xC4 :: 0xE0 :: 0xD8 :: 0x6A :: 0x7B :: 0x04 :: 0x30 ::
                        0xD8 :: 0xCD :: 0xB7 :: 0x80 :: 0x70 :: 0xB4 :: 0xC5 :: 0x5A :: nil))
  = false.
Proof. vm_reflexivity. Qed.

Example the_transposed_flattening_is_a_permutation_too :
  covers_each_index_once (map_over transposed_shift_rows_index (upto block_bytes)) block_bytes = true
  := eq_refl.

(* Both readings leave four of the sixteen positions where they were, and the
   two agree at exactly one of them, which is what makes the transposition a
   reading of the same clause rather than a different step. *)
Example both_readings_leave_four_positions_fixed :
  andb (Nat.eqb (count_where (fun i => Nat.eqb (shift_rows_index i) i) (upto block_bytes)) 4)
       (Nat.eqb (count_where (fun i => Nat.eqb (transposed_shift_rows_index i) i)
                             (upto block_bytes)) 4) = true := eq_refl.

Example the_two_readings_agree_at_exactly_one_position :
  count_where (fun i => Nat.eqb (shift_rows_index i) (transposed_shift_rows_index i))
              (upto block_bytes) = 1 := eq_refl.

Example the_transposed_flattening_misses_the_published_ciphertext :
  bits_eqb (block_of_state
              (aes_encrypt_over sub_byte shift_rows_transposed 4 (bytes_from (upto 16))
                 (bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                              0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil))))
           (block_from (0x69 :: 0xC4 :: 0xE0 :: 0xD8 :: 0x6A :: 0x7B :: 0x04 :: 0x30 ::
                        0xD8 :: 0xCD :: 0xB7 :: 0x80 :: 0x70 :: 0xB4 :: 0xC5 :: 0x5A :: nil))
  = false.
Proof. vm_reflexivity. Qed.

(* The two directions exchanged is the closest of the three: it is the same
   permutation on rows zero and two, which is half the state, and it differs
   only on the two rows whose shift is not its own inverse. *)
Example the_exchanged_directions_agree_on_half_the_state :
  count_where (fun i => Nat.eqb (shift_rows_index i) (inv_shift_rows_index i))
              (upto block_bytes) = 8 := eq_refl.

Example the_exchanged_directions_miss_the_published_ciphertext :
  bits_eqb (block_of_state
              (aes_encrypt_over sub_byte inv_shift_rows 4 (bytes_from (upto 16))
                 (bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                              0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil))))
           (block_from (0x69 :: 0xC4 :: 0xE0 :: 0xD8 :: 0x6A :: 0x7B :: 0x04 :: 0x30 ::
                        0xD8 :: 0xCD :: 0xB7 :: 0x80 :: 0x70 :: 0xB4 :: 0xC5 :: 0x5A :: nil))
  = false.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   The GF(2^128) multiplication: the standard's form, the model's form, and
   the form without the reflection.
   ------------------------------------------------------------------------- *)

Definition ghash_probe_blocks : list block :=
  zero_block ::
  ghash_R ::
  block_from (upto block_bytes) ::
  block_from (rev_of (upto block_bytes)) ::
  block_from (repeat_of block_bytes 255) ::
  block_from (0x66 :: 0xE9 :: 0x4B :: 0xD4 :: 0xEF :: 0x8A :: 0x2C :: 0x3B ::
              0x88 :: 0x4C :: 0xFA :: 0x59 :: 0xCA :: 0x34 :: 0x2B :: 0x2E :: nil) :: nil.

Definition ghash_probe_pairs : list (block * block) :=
  concat_of (map_over (fun a => map_over (fun b => pair a b) ghash_probe_blocks)
                      ghash_probe_blocks).

Example the_probe_family_is_thirty_six_pairs :
  length_of ghash_probe_pairs = 36.
Proof. vm_reflexivity. Qed.

Example one_is_the_identity_of_the_field_multiplication :
  all_of (fun x => bits_eqb (gf128_mul x (block_from (0x80 :: repeat_of 15 0 ))) x)
         ghash_probe_blocks = true.
Proof. vm_reflexivity. Qed.

Example the_field_multiplication_on_blocks_is_commutative :
  all_of (fun p => bits_eqb (gf128_mul (fst p) (snd p)) (gf128_mul (snd p) (fst p)))
         ghash_probe_pairs = true.
Proof. vm_reflexivity. Qed.

Example the_models_form_and_the_standards_form_are_one_multiplication :
  all_of (fun p => bits_eqb (ghash_mul_the_models_way (fst p) (snd p))
                            (gf128_mul (fst p) (snd p)))
         ghash_probe_pairs = true.
Proof. vm_reflexivity. Qed.

(* Removing reflection preserves commutativity but changes the bit-string
   representation. Its identity is 0x01 00..00 instead of the standard's
   0x80 00..00; the checks below distinguish them. *)
Example the_unreflected_form_is_the_standards_under_a_byte_wise_reversal :
  all_of (fun p => bits_eqb (ghash_mul_without_the_reflection (fst p) (snd p))
                            (reflect_block (gf128_mul (reflect_block (fst p))
                                                      (reflect_block (snd p)))))
         ghash_probe_pairs = true.
Proof. vm_reflexivity. Qed.

Example the_unreflected_form_is_commutative_too :
  all_of (fun p => bits_eqb (ghash_mul_without_the_reflection (fst p) (snd p))
                            (ghash_mul_without_the_reflection (snd p) (fst p)))
         ghash_probe_pairs = true.
Proof. vm_reflexivity. Qed.

Example the_unreflected_form_has_the_reflected_identity :
  all_of (fun x => bits_eqb (ghash_mul_without_the_reflection x
                               (block_from (0x01 :: repeat_of 15 0))) x)
         ghash_probe_blocks = true.
Proof. vm_reflexivity. Qed.

Example the_standards_identity_is_not_the_unreflected_forms :
  all_of (fun x => bits_eqb (ghash_mul_without_the_reflection x
                               (block_from (0x80 :: repeat_of 15 0))) x)
         ghash_probe_blocks = false.
Proof. vm_reflexivity. Qed.

Example the_unreflected_form_is_a_different_multiplication :
  all_of (fun p => bits_eqb (ghash_mul_without_the_reflection (fst p) (snd p))
                            (gf128_mul (fst p) (snd p)))
         ghash_probe_pairs = false.
Proof. vm_reflexivity. Qed.

Example the_counter_field_wraps_and_leaves_the_rest_of_the_block_alone :
  bytes_of (inc32 (block_from (repeat_of 12 0xAA ++ (0xFF :: 0xFF :: 0xFF :: 0xFF :: nil)))) =
  0xAA :: 0xAA :: 0xAA :: 0xAA :: 0xAA :: 0xAA :: 0xAA :: 0xAA ::
  0xAA :: 0xAA :: 0xAA :: 0xAA :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: nil.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   AES-GCM against the published test cases. Each key, IV, plaintext,
   associated data, ciphertext and tag is a constant inside the statement that
   decides against it.
   ------------------------------------------------------------------------- *)

Example the_hash_subkey_of_the_all_zero_key_is_the_published_one :
  bytes_of (gcm_subkey (key_schedule 4 (bytes_from (repeat_of 16 0))) 10) =
  0x66 :: 0xE9 :: 0x4B :: 0xD4 :: 0xEF :: 0x8A :: 0x2C :: 0x3B ::
  0x88 :: 0x4C :: 0xFA :: 0x59 :: 0xCA :: 0x34 :: 0x2B :: 0x2E :: nil.
Proof. vm_reflexivity. Qed.

(*| discharges: R-10-024 |*)
Example the_first_published_case_reaches_its_tag :
  bytes_of (snd (gcm_encrypt 4 (bytes_from (repeat_of 16 0))
                             (block_from (repeat_of 12 0)) nil nil)) =
  0x58 :: 0xE2 :: 0xFC :: 0xCE :: 0xFA :: 0x7E :: 0x30 :: 0x61 ::
  0x36 :: 0x7F :: 0x1D :: 0x57 :: 0xA4 :: 0xE7 :: 0x45 :: 0x5A :: nil.
Proof. vm_reflexivity. Qed.

(*| discharges: R-10-024 |*)
Example the_second_published_case_reaches_its_ciphertext_and_tag :
  let r := gcm_encrypt 4 (bytes_from (repeat_of 16 0)) (block_from (repeat_of 12 0)) nil
                       (block_from (repeat_of 16 0)) in
  pair (bytes_of (fst r)) (bytes_of (snd r)) =
  pair (0x03 :: 0x88 :: 0xDA :: 0xCE :: 0x60 :: 0xB6 :: 0xA3 :: 0x92 ::
        0xF3 :: 0x28 :: 0xC2 :: 0xB9 :: 0x71 :: 0xB2 :: 0xFE :: 0x78 :: nil)
       (0xAB :: 0x6E :: 0x47 :: 0xD4 :: 0x2C :: 0xEC :: 0x13 :: 0xBD ::
        0xF5 :: 0x3A :: 0x67 :: 0xB2 :: 0x12 :: 0x57 :: 0xBD :: 0xDF :: nil).
Proof. vm_reflexivity. Qed.

(*| discharges: R-10-024 |*)
Example the_third_published_case_reaches_its_ciphertext_and_tag :
  let r := gcm_encrypt 4
             (bytes_from (0xFE :: 0xFF :: 0xE9 :: 0x92 :: 0x86 :: 0x65 :: 0x73 :: 0x1C ::
                          0x6D :: 0x6A :: 0x8F :: 0x94 :: 0x67 :: 0x30 :: 0x83 :: 0x08 :: nil))
             (block_from (0xCA :: 0xFE :: 0xBA :: 0xBE :: 0xFA :: 0xCE :: 0xDB :: 0xAD ::
                          0xDE :: 0xCA :: 0xF8 :: 0x88 :: nil))
             nil
             (block_from (0xD9 :: 0x31 :: 0x32 :: 0x25 :: 0xF8 :: 0x84 :: 0x06 :: 0xE5 ::
                          0xA5 :: 0x59 :: 0x09 :: 0xC5 :: 0xAF :: 0xF5 :: 0x26 :: 0x9A ::
                          0x86 :: 0xA7 :: 0xA9 :: 0x53 :: 0x15 :: 0x34 :: 0xF7 :: 0xDA ::
                          0x2E :: 0x4C :: 0x30 :: 0x3D :: 0x8A :: 0x31 :: 0x8A :: 0x72 ::
                          0x1C :: 0x3C :: 0x0C :: 0x95 :: 0x95 :: 0x68 :: 0x09 :: 0x53 ::
                          0x2F :: 0xCF :: 0x0E :: 0x24 :: 0x49 :: 0xA6 :: 0xB5 :: 0x25 ::
                          0xB1 :: 0x6A :: 0xED :: 0xF5 :: 0xAA :: 0x0D :: 0xE6 :: 0x57 ::
                          0xBA :: 0x63 :: 0x7B :: 0x39 :: 0x1A :: 0xAF :: 0xD2 :: 0x55 :: nil)) in
  pair (bytes_of (fst r)) (bytes_of (snd r)) =
  pair (0x42 :: 0x83 :: 0x1E :: 0xC2 :: 0x21 :: 0x77 :: 0x74 :: 0x24 ::
        0x4B :: 0x72 :: 0x21 :: 0xB7 :: 0x84 :: 0xD0 :: 0xD4 :: 0x9C ::
        0xE3 :: 0xAA :: 0x21 :: 0x2F :: 0x2C :: 0x02 :: 0xA4 :: 0xE0 ::
        0x35 :: 0xC1 :: 0x7E :: 0x23 :: 0x29 :: 0xAC :: 0xA1 :: 0x2E ::
        0x21 :: 0xD5 :: 0x14 :: 0xB2 :: 0x54 :: 0x66 :: 0x93 :: 0x1C ::
        0x7D :: 0x8F :: 0x6A :: 0x5A :: 0xAC :: 0x84 :: 0xAA :: 0x05 ::
        0x1B :: 0xA3 :: 0x0B :: 0x39 :: 0x6A :: 0x0A :: 0xAC :: 0x97 ::
        0x3D :: 0x58 :: 0xE0 :: 0x91 :: 0x47 :: 0x3F :: 0x59 :: 0x85 :: nil)
       (0x4D :: 0x5C :: 0x2A :: 0xF3 :: 0x27 :: 0xCD :: 0x64 :: 0xA6 ::
        0x2C :: 0xF3 :: 0x5A :: 0xBD :: 0x2B :: 0xA6 :: 0xFA :: 0xB4 :: nil).
Proof. vm_reflexivity. Qed.

(*| discharges: R-10-024 |*)
Example the_fourth_published_case_carries_associated_data_and_an_unaligned_plaintext :
  let r := gcm_encrypt 4
             (bytes_from (0xFE :: 0xFF :: 0xE9 :: 0x92 :: 0x86 :: 0x65 :: 0x73 :: 0x1C ::
                          0x6D :: 0x6A :: 0x8F :: 0x94 :: 0x67 :: 0x30 :: 0x83 :: 0x08 :: nil))
             (block_from (0xCA :: 0xFE :: 0xBA :: 0xBE :: 0xFA :: 0xCE :: 0xDB :: 0xAD ::
                          0xDE :: 0xCA :: 0xF8 :: 0x88 :: nil))
             (block_from (0xFE :: 0xED :: 0xFA :: 0xCE :: 0xDE :: 0xAD :: 0xBE :: 0xEF ::
                          0xFE :: 0xED :: 0xFA :: 0xCE :: 0xDE :: 0xAD :: 0xBE :: 0xEF ::
                          0xAB :: 0xAD :: 0xDA :: 0xD2 :: nil))
             (block_from (0xD9 :: 0x31 :: 0x32 :: 0x25 :: 0xF8 :: 0x84 :: 0x06 :: 0xE5 ::
                          0xA5 :: 0x59 :: 0x09 :: 0xC5 :: 0xAF :: 0xF5 :: 0x26 :: 0x9A ::
                          0x86 :: 0xA7 :: 0xA9 :: 0x53 :: 0x15 :: 0x34 :: 0xF7 :: 0xDA ::
                          0x2E :: 0x4C :: 0x30 :: 0x3D :: 0x8A :: 0x31 :: 0x8A :: 0x72 ::
                          0x1C :: 0x3C :: 0x0C :: 0x95 :: 0x95 :: 0x68 :: 0x09 :: 0x53 ::
                          0x2F :: 0xCF :: 0x0E :: 0x24 :: 0x49 :: 0xA6 :: 0xB5 :: 0x25 ::
                          0xB1 :: 0x6A :: 0xED :: 0xF5 :: 0xAA :: 0x0D :: 0xE6 :: 0x57 ::
                          0xBA :: 0x63 :: 0x7B :: 0x39 :: nil)) in
  pair (bytes_of (fst r)) (bytes_of (snd r)) =
  pair (0x42 :: 0x83 :: 0x1E :: 0xC2 :: 0x21 :: 0x77 :: 0x74 :: 0x24 ::
        0x4B :: 0x72 :: 0x21 :: 0xB7 :: 0x84 :: 0xD0 :: 0xD4 :: 0x9C ::
        0xE3 :: 0xAA :: 0x21 :: 0x2F :: 0x2C :: 0x02 :: 0xA4 :: 0xE0 ::
        0x35 :: 0xC1 :: 0x7E :: 0x23 :: 0x29 :: 0xAC :: 0xA1 :: 0x2E ::
        0x21 :: 0xD5 :: 0x14 :: 0xB2 :: 0x54 :: 0x66 :: 0x93 :: 0x1C ::
        0x7D :: 0x8F :: 0x6A :: 0x5A :: 0xAC :: 0x84 :: 0xAA :: 0x05 ::
        0x1B :: 0xA3 :: 0x0B :: 0x39 :: 0x6A :: 0x0A :: 0xAC :: 0x97 ::
        0x3D :: 0x58 :: 0xE0 :: 0x91 :: nil)
       (0x5B :: 0xC9 :: 0x4F :: 0xBC :: 0x32 :: 0x21 :: 0xA5 :: 0xDB ::
        0x94 :: 0xFA :: 0xE9 :: 0x5A :: 0xE7 :: 0x12 :: 0x1A :: 0x47 :: nil).
Proof. vm_reflexivity. Qed.

(* The fifth published case takes the other J0 arm: its IV is 64 bits, so the
   initial counter block is a GHASH of the IV and its length rather than a
   concatenation. Without this case the long arm is a branch no vector enters. *)
(*| discharges: R-10-024 |*)
Example the_fifth_published_case_takes_the_other_initial_counter_arm :
  let r := gcm_encrypt 4
             (bytes_from (0xFE :: 0xFF :: 0xE9 :: 0x92 :: 0x86 :: 0x65 :: 0x73 :: 0x1C ::
                          0x6D :: 0x6A :: 0x8F :: 0x94 :: 0x67 :: 0x30 :: 0x83 :: 0x08 :: nil))
             (block_from (0xCA :: 0xFE :: 0xBA :: 0xBE :: 0xFA :: 0xCE :: 0xDB :: 0xAD :: nil))
             (block_from (0xFE :: 0xED :: 0xFA :: 0xCE :: 0xDE :: 0xAD :: 0xBE :: 0xEF ::
                          0xFE :: 0xED :: 0xFA :: 0xCE :: 0xDE :: 0xAD :: 0xBE :: 0xEF ::
                          0xAB :: 0xAD :: 0xDA :: 0xD2 :: nil))
             (block_from (0xD9 :: 0x31 :: 0x32 :: 0x25 :: 0xF8 :: 0x84 :: 0x06 :: 0xE5 ::
                          0xA5 :: 0x59 :: 0x09 :: 0xC5 :: 0xAF :: 0xF5 :: 0x26 :: 0x9A ::
                          0x86 :: 0xA7 :: 0xA9 :: 0x53 :: 0x15 :: 0x34 :: 0xF7 :: 0xDA ::
                          0x2E :: 0x4C :: 0x30 :: 0x3D :: 0x8A :: 0x31 :: 0x8A :: 0x72 ::
                          0x1C :: 0x3C :: 0x0C :: 0x95 :: 0x95 :: 0x68 :: 0x09 :: 0x53 ::
                          0x2F :: 0xCF :: 0x0E :: 0x24 :: 0x49 :: 0xA6 :: 0xB5 :: 0x25 ::
                          0xB1 :: 0x6A :: 0xED :: 0xF5 :: 0xAA :: 0x0D :: 0xE6 :: 0x57 ::
                          0xBA :: 0x63 :: 0x7B :: 0x39 :: nil)) in
  pair (bytes_of (fst r)) (bytes_of (snd r)) =
  pair (0x61 :: 0x35 :: 0x3B :: 0x4C :: 0x28 :: 0x06 :: 0x93 :: 0x4A ::
        0x77 :: 0x7F :: 0xF5 :: 0x1F :: 0xA2 :: 0x2A :: 0x47 :: 0x55 ::
        0x69 :: 0x9B :: 0x2A :: 0x71 :: 0x4F :: 0xCD :: 0xC6 :: 0xF8 ::
        0x37 :: 0x66 :: 0xE5 :: 0xF9 :: 0x7B :: 0x6C :: 0x74 :: 0x23 ::
        0x73 :: 0x80 :: 0x69 :: 0x00 :: 0xE4 :: 0x9F :: 0x24 :: 0xB2 ::
        0x2B :: 0x09 :: 0x75 :: 0x44 :: 0xD4 :: 0x89 :: 0x6B :: 0x42 ::
        0x49 :: 0x89 :: 0xB5 :: 0xE1 :: 0xEB :: 0xAC :: 0x0F :: 0x07 ::
        0xC2 :: 0x3F :: 0x45 :: 0x98 :: nil)
       (0x36 :: 0x12 :: 0xD2 :: 0xE7 :: 0x9E :: 0x3B :: 0x07 :: 0x85 ::
        0x56 :: 0x1B :: 0xE1 :: 0x4A :: 0xAC :: 0xA2 :: 0xFC :: 0xCB :: nil).
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   Authenticated decryption, and the two near alternatives to the composition.
   ------------------------------------------------------------------------- *)

(*| discharges: R-10-024 |*)
Example the_open_of_a_seal_returns_the_message_and_a_flipped_tag_bit_returns_nothing :
  let key := bytes_from (0xFE :: 0xFF :: 0xE9 :: 0x92 :: 0x86 :: 0x65 :: 0x73 :: 0x1C ::
                         0x6D :: 0x6A :: 0x8F :: 0x94 :: 0x67 :: 0x30 :: 0x83 :: 0x08 :: nil) in
  let iv := block_from (0xCA :: 0xFE :: 0xBA :: 0xBE :: 0xFA :: 0xCE :: 0xDB :: 0xAD ::
                        0xDE :: 0xCA :: 0xF8 :: 0x88 :: nil) in
  let aad := block_from (0xFE :: 0xED :: 0xFA :: 0xCE :: 0xDE :: 0xAD :: 0xBE :: 0xEF :: nil) in
  let m := block_from (upto block_bytes) in
  let r := gcm_encrypt 4 key iv aad m in
  andb (if gcm_open block_bits 4 key iv aad (fst r) (snd r) is Some p
        then bits_eqb p m else false)
       (if gcm_open block_bits 4 key iv aad (fst r) (bxor (snd r) (block_from (1 :: repeat_of 15 0)))
        is Some _ then false else true) = true.
Proof. vm_reflexivity. Qed.

(* The unpadded GHASH variant passes the first three published cases, whose
   associated data is empty and ciphertext is block-aligned, and fails the
   fourth. An additional case checks nonempty aligned associated data and
   ciphertext. An unaligned case is needed to expose the missing padding. *)
Example the_unpadded_ghash_input_agrees_at_every_aligned_published_case :
  andb (andb (andb (bits_eqb (snd (gcm_encrypt_unpadded 4 (bytes_from (repeat_of 16 0))
                                                       (block_from (repeat_of 12 0)) nil nil))
                             (snd (gcm_encrypt 4 (bytes_from (repeat_of 16 0))
                                               (block_from (repeat_of 12 0)) nil nil)))
                   (bits_eqb (snd (gcm_encrypt_unpadded 4 (bytes_from (repeat_of 16 0))
                                                        (block_from (repeat_of 12 0)) nil
                                                        (block_from (repeat_of 16 0))))
                             (snd (gcm_encrypt 4 (bytes_from (repeat_of 16 0))
                                               (block_from (repeat_of 12 0)) nil
                                               (block_from (repeat_of 16 0))))))
             (let key := bytes_from (0xFE :: 0xFF :: 0xE9 :: 0x92 :: 0x86 :: 0x65 :: 0x73 :: 0x1C ::
                                     0x6D :: 0x6A :: 0x8F :: 0x94 :: 0x67 :: 0x30 :: 0x83 :: 0x08 :: nil) in
              let iv := block_from (0xCA :: 0xFE :: 0xBA :: 0xBE :: 0xFA :: 0xCE :: 0xDB :: 0xAD ::
                                    0xDE :: 0xCA :: 0xF8 :: 0x88 :: nil) in
              let m := block_from (0xD9 :: 0x31 :: 0x32 :: 0x25 :: 0xF8 :: 0x84 :: 0x06 :: 0xE5 ::
                                   0xA5 :: 0x59 :: 0x09 :: 0xC5 :: 0xAF :: 0xF5 :: 0x26 :: 0x9A ::
                                   0x86 :: 0xA7 :: 0xA9 :: 0x53 :: 0x15 :: 0x34 :: 0xF7 :: 0xDA ::
                                   0x2E :: 0x4C :: 0x30 :: 0x3D :: 0x8A :: 0x31 :: 0x8A :: 0x72 ::
                                   0x1C :: 0x3C :: 0x0C :: 0x95 :: 0x95 :: 0x68 :: 0x09 :: 0x53 ::
                                   0x2F :: 0xCF :: 0x0E :: 0x24 :: 0x49 :: 0xA6 :: 0xB5 :: 0x25 ::
                                   0xB1 :: 0x6A :: 0xED :: 0xF5 :: 0xAA :: 0x0D :: 0xE6 :: 0x57 ::
                                   0xBA :: 0x63 :: 0x7B :: 0x39 :: 0x1A :: 0xAF :: 0xD2 :: 0x55 :: nil) in
              bits_eqb (snd (gcm_encrypt_unpadded 4 key iv nil m))
                       (snd (gcm_encrypt 4 key iv nil m))))
       (bits_eqb (snd (gcm_encrypt_unpadded 4 (bytes_from (upto 16))
                                            (block_from (repeat_of 12 7)) (block_from (upto 16))
                                            (block_from (upto 32))))
                 (snd (gcm_encrypt 4 (bytes_from (upto 16))
                                   (block_from (repeat_of 12 7)) (block_from (upto 16))
                                   (block_from (upto 32))))) = true.
Proof. vm_reflexivity. Qed.

Example the_unpadded_ghash_input_misses_the_fourth_published_tag :
  bits_eqb (snd (gcm_encrypt_unpadded 4
             (bytes_from (0xFE :: 0xFF :: 0xE9 :: 0x92 :: 0x86 :: 0x65 :: 0x73 :: 0x1C ::
                          0x6D :: 0x6A :: 0x8F :: 0x94 :: 0x67 :: 0x30 :: 0x83 :: 0x08 :: nil))
             (block_from (0xCA :: 0xFE :: 0xBA :: 0xBE :: 0xFA :: 0xCE :: 0xDB :: 0xAD ::
                          0xDE :: 0xCA :: 0xF8 :: 0x88 :: nil))
             (block_from (0xFE :: 0xED :: 0xFA :: 0xCE :: 0xDE :: 0xAD :: 0xBE :: 0xEF ::
                          0xFE :: 0xED :: 0xFA :: 0xCE :: 0xDE :: 0xAD :: 0xBE :: 0xEF ::
                          0xAB :: 0xAD :: 0xDA :: 0xD2 :: nil))
             (block_from (0xD9 :: 0x31 :: 0x32 :: 0x25 :: 0xF8 :: 0x84 :: 0x06 :: 0xE5 ::
                          0xA5 :: 0x59 :: 0x09 :: 0xC5 :: 0xAF :: 0xF5 :: 0x26 :: 0x9A ::
                          0x86 :: 0xA7 :: 0xA9 :: 0x53 :: 0x15 :: 0x34 :: 0xF7 :: 0xDA ::
                          0x2E :: 0x4C :: 0x30 :: 0x3D :: 0x8A :: 0x31 :: 0x8A :: 0x72 ::
                          0x1C :: 0x3C :: 0x0C :: 0x95 :: 0x95 :: 0x68 :: 0x09 :: 0x53 ::
                          0x2F :: 0xCF :: 0x0E :: 0x24 :: 0x49 :: 0xA6 :: 0xB5 :: 0x25 ::
                          0xB1 :: 0x6A :: 0xED :: 0xF5 :: 0xAA :: 0x0D :: 0xE6 :: 0x57 ::
                          0xBA :: 0x63 :: 0x7B :: 0x39 :: nil))))
           (block_from (0x5B :: 0xC9 :: 0x4F :: 0xBC :: 0x32 :: 0x21 :: 0xA5 :: 0xDB ::
                        0x94 :: 0xFA :: 0xE9 :: 0x5A :: 0xE7 :: 0x12 :: 0x1A :: 0x47 :: nil))
  = false.
Proof. vm_reflexivity. Qed.

(* Starting the counter at J0 passes the empty-plaintext case and fails the
   second published case. Nonempty plaintext is needed to expose this
   error. *)
Example the_counter_started_at_j0_agrees_at_the_empty_plaintext :
  let a := gcm_encrypt_from_j0 4 (bytes_from (repeat_of 16 0))
                               (block_from (repeat_of 12 0)) nil nil in
  let b := gcm_encrypt 4 (bytes_from (repeat_of 16 0)) (block_from (repeat_of 12 0)) nil nil in
  andb (bits_eqb (fst a) (fst b)) (bits_eqb (snd a) (snd b)) = true.
Proof. vm_reflexivity. Qed.

Example the_counter_started_at_j0_misses_the_second_published_ciphertext :
  bits_eqb (fst (gcm_encrypt_from_j0 4 (bytes_from (repeat_of 16 0))
                                     (block_from (repeat_of 12 0)) nil
                                     (block_from (repeat_of 16 0))))
           (block_from (0x03 :: 0x88 :: 0xDA :: 0xCE :: 0x60 :: 0xB6 :: 0xA3 :: 0x92 ::
                        0xF3 :: 0x28 :: 0xC2 :: 0xB9 :: 0x71 :: 0xB2 :: 0xFE :: 0x78 :: nil))
  = false.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   What a reused nonce costs, computed rather than argued. Two messages sealed
   under one key and one nonce carry the exclusive-or of their plaintexts in
   the exclusive-or of their ciphertexts, which is why R-05-126b gives a
   nonce-typed value the linear grade and why R-10-023 keeps the per-extent
   nonce random. Neither is a property of this text.
   ------------------------------------------------------------------------- *)

Example a_reused_nonce_carries_the_exclusive_or_of_the_two_messages :
  let key := bytes_from (0xFE :: 0xFF :: 0xE9 :: 0x92 :: 0x86 :: 0x65 :: 0x73 :: 0x1C ::
                         0x6D :: 0x6A :: 0x8F :: 0x94 :: 0x67 :: 0x30 :: 0x83 :: 0x08 :: nil) in
  let iv := block_from (0xCA :: 0xFE :: 0xBA :: 0xBE :: 0xFA :: 0xCE :: 0xDB :: 0xAD ::
                        0xDE :: 0xCA :: 0xF8 :: 0x88 :: nil) in
  let m1 := block_from (upto block_bytes) in
  let m2 := block_from (rev_of (upto block_bytes)) in
  bits_eqb (bxor (fst (gcm_encrypt 4 key iv nil m1)) (fst (gcm_encrypt 4 key iv nil m2)))
           (bxor m1 m2) = true.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   The parameter record inhabited, and the field nothing reads.
   ------------------------------------------------------------------------- *)

Example the_witness_at_the_platform_parameters_is_the_first_published_case :
  bytes_of (snd (seal_under demo demo_key nil)) =
  0x58 :: 0xE2 :: 0xFC :: 0xCE :: 0xFA :: 0x7E :: 0x30 :: 0x61 ::
  0x36 :: 0x7F :: 0x1D :: 0x57 :: 0xA4 :: 0xE7 :: 0x45 :: 0x5A :: nil.
Proof. vm_reflexivity. Qed.

Example a_stated_invocation_bound_changes_nothing_the_primitive_computes :
  let a := seal_under demo demo_key nil in
  let b := seal_under demo_with_a_stated_bound demo_key nil in
  andb (bits_eqb (fst a) (fst b)) (bits_eqb (snd a) (snd b)) = true.
Proof. vm_reflexivity. Qed.

Example a_truncated_tag_is_a_prefix_of_the_full_one :
  let full := snd (seal_under demo demo_key nil) in
  let short := snd (seal_under demo_truncated_tag demo_key nil) in
  andb (Nat.eqb (length_of short) shortest_admissible_tag)
       (bits_eqb short (take_of shortest_admissible_tag full)) = true.
Proof. vm_reflexivity. Qed.

Example the_three_key_lengths_carry_three_round_counts :
  map_over (fun p => rounds_for (key_words p)) (demo :: demo_aes192 :: demo_aes256 :: nil) =
  10 :: 12 :: 14 :: nil := eq_refl.

(* Checks for defaults and geometry not exercised above: out-of-range
   reads, key-schedule size, and the standard's tag-length lists. *)

Example a_bit_off_the_end_of_a_byte_is_zero : bit_at nil 0 = false := eq_refl.

Example the_block_is_sixteen_bytes_of_eight_bits :
  andb (Nat.eqb block_bytes 16) (Nat.eqb block_bits 128) = true := eq_refl.

Example the_key_schedule_has_one_round_key_per_round_and_one_more :
  map_over (fun nk => length_of (key_schedule nk (bytes_from (upto (4 * nk)))))
           (4 :: 6 :: 8 :: nil) =
  44 :: 52 :: 60 :: nil.
Proof. vm_reflexivity. Qed.

(* RotWord, FIPS 197 s5.2, rotates four bytes once and returns to the
   original word after four rotations. Checking both shape and rotation
   prevents xor_bytes from hiding an oversized result by truncation. *)
Theorem rotating_a_word_moves_each_byte_one_place_and_adds_none :
  forall b0 b1 b2 b3 : byte,
    rot_word (b0 :: b1 :: b2 :: b3 :: nil) = b1 :: b2 :: b3 :: b0 :: nil.
Proof. intros. reflexivity. Qed.

Theorem rotating_a_word_four_times_is_the_identity :
  forall b0 b1 b2 b3 : byte,
    rot_word (rot_word (rot_word (rot_word (b0 :: b1 :: b2 :: b3 :: nil)))) =
    b0 :: b1 :: b2 :: b3 :: nil.
Proof. intros. reflexivity. Qed.

(* The guards agree at every standard key length and differ only at Nk = 7.
   These checks concern expansion, not an AES cipher with a standard key
   size. *)
Example the_two_substitution_guards_agree_at_every_key_length_the_standard_carries :
  all_of (fun nk =>
            let k := bytes_from (upto (nb * nk)) in
            bits_eqb (concat_of (concat_of (key_schedule_over sub_byte
                                              second_substitution_guard nk k)))
                     (concat_of (concat_of (key_schedule_over sub_byte
                                              raised_substitution_guard nk k))))
         (4 :: 6 :: 8 :: nil) = true.
Proof. vm_reflexivity. Qed.

Example the_two_substitution_guards_part_at_the_key_length_between_them :
  let k := bytes_from (upto (nb * 7)) in
  bits_eqb (concat_of (concat_of (key_schedule_over sub_byte
                                    second_substitution_guard 7 k)))
           (concat_of (concat_of (key_schedule_over sub_byte
                                    raised_substitution_guard 7 k))) = false.
Proof. vm_reflexivity. Qed.

Example the_last_round_key_is_the_last_four_words :
  all_of (fun nk => Nat.eqb (length_of (round_key (key_schedule nk (bytes_from (upto (4 * nk))))
                                                  (rounds_for nk)))
                            block_bytes)
         (4 :: 6 :: 8 :: nil) = true.
Proof. vm_reflexivity. Qed.

Example the_full_tag_is_the_longest_admissible_one :
  Nat.eqb (nth_of 0 admissible_tag_lengths 0) block_bits = true := eq_refl.

(* Check the tag-length lists' shapes and counts against SP 800-38D
   s5.2.1.2. Shape alone admits extra lengths: 88 in the admissible list
   and 24 in the restricted list. *)
Example the_admissible_tag_lengths_descend_one_byte_at_a_time_from_the_full_tag :
  all_of (fun i => Nat.eqb (nth_of i admissible_tag_lengths 0) (block_bits - byte_bits * i))
         (upto (length_of admissible_tag_lengths)) = true.
Proof. vm_reflexivity. Qed.

Example every_restricted_tag_length_is_whole_bytes_below_the_shortest_admissible_one :
  all_of (fun t => andb (Nat.eqb (Nat.modulo t byte_bits) 0)
                        (Nat.ltb t shortest_admissible_tag))
         restricted_tag_lengths = true.
Proof. vm_reflexivity. Qed.

Example the_two_tag_length_lists_carry_the_counts_the_standard_states :
  andb (Nat.eqb (length_of admissible_tag_lengths) 5)
       (Nat.eqb (length_of restricted_tag_lengths) 2) = true := eq_refl.

(* Check that each listed tag length is at most 128 bits and a whole number
   of bytes, and that truncation selects the corresponding prefix. Prefix
   equality alone holds for arbitrary natural lengths and does not validate
   the list. *)
Example truncating_at_every_listed_tag_length_takes_whole_bytes_of_the_published_tag :
  all_of (fun t =>
            let short := take_of t (snd (gcm_encrypt 4 (bytes_from (repeat_of 16 0))
                                                     (block_from (repeat_of 12 0)) nil nil)) in
            andb (andb (Nat.eqb (length_of short) t)
                       (Nat.eqb (Nat.modulo t byte_bits) 0))
                 (bits_eqb short
                    (take_of t (block_from
                       (0x58 :: 0xE2 :: 0xFC :: 0xCE :: 0xFA :: 0x7E :: 0x30 :: 0x61 ::
                        0x36 :: 0x7F :: 0x1D :: 0x57 :: 0xA4 :: 0xE7 :: 0x45 :: 0x5A :: nil)))))
         (admissible_tag_lengths ++ restricted_tag_lengths) = true.
Proof. vm_reflexivity. Qed.

(* The sixteen bytes that are their own bit reversal, which is what makes the
   reflection invisible on a byte and visible on a block. *)
Definition palindromic_bytes : list byte :=
  keep_where (fun b => bits_eqb (rev_of b) b) all_bytes.

Example there_are_sixteen_bytes_that_are_their_own_reversal :
  length_of palindromic_bytes = 16.
Proof. vm_reflexivity. Qed.

Example the_reflection_fixes_a_block_of_those_bytes_and_moves_the_others :
  andb (all_of (fun b => bits_eqb (reflect_block (concat_of (repeat_of block_bytes b)))
                                  (concat_of (repeat_of block_bytes b)))
               palindromic_bytes)
       (negb (bits_eqb (reflect_block (block_from (upto block_bytes)))
                       (block_from (upto block_bytes)))) = true.
Proof. vm_reflexivity. Qed.

(* -------------------------------------------------------------------------
   R-05-166's inhabitation witnesses: one closed definition per record this
   file's statements quantify over, named for that record and ascribed at it.
   The prover decides inhabitation by type-checking the ascription, so
   `run.py proofs` reads a name rather than approximating a type judgement.
   A record this file reaches through a Require is witnessed in the file that
   declares it.
   ------------------------------------------------------------------------- *)

Definition witness_AeadParameters : AeadParameters := demo.

(* R-05-164: `run.py proofs` audits the complete native inventory. *)
