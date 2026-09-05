(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   AesGcm.v

   The AES block cipher at all three key lengths, the GF(2^128) multiplication
   and GHASH, the counter mode over them, and the authenticated encryption and
   authenticated decryption functions of AES-GCM, written in Gallina against
   FIPS 197 and NIST SP 800-38D and checked against the standards' own
   published known answers.

   What this file is, and what it is not. It is a **functional reference** for
   the one cipher R-10-024 freezes: *the cipher is frozen to AES-GCM via
   Zvkned/Zvkg, one cipher and not a menu*, with ChaCha20/Poly1305 the
   frozen-out alternative. It is a second transcription of the same two
   standards the curated model's vector-crypto unit transcribes, so the two are
   a differential pair rather than two independent chances to be wrong. It is
   not an implementation, no binary corresponds to it, and it discharges no
   acceptance clause of any entry.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. Nothing here executes on either
   emulator. The computed checks are decided inside the kernel, the light ones
   by conversion in the silent `Example ... := eq_refl` form and the ones that
   run a cipher by the bytecode machine, which contributes nothing to the
   Print Assumptions block at the end.

   The three assurance layers, and which one this is. R-05-059 wants functional
   correctness, constant-time and reduction-level security per primitive, and
   what is here is the **functional layer alone**.

   - **No constant-time property is claimed and none is implied.** R-05-062
     makes constant time a 2-safety hyperproperty verified directly on the
     binary, and R-05-067 names AES by name among the control-flow-heavy
     primitives that are written branchless on secrets and *then verified on
     the artifact*. A Gallina reference is not a binary. That the S-box below
     is computed from the field inverse rather than read out of a table, and
     that every value-dependent operation here is xorb, andb, negb or a
     rotation, is a remark about the shape of this text and never evidence.
   - **No masking claim.** R-05-004a puts the secret-handling datapath's
     d-probing security and its composition property on the artifact against
     the R-15-053a probing model. Nothing here is a sharing of anything.
   - **No reduction and no distributional claim.** R-05-077a states the
     reduction over uniformly drawn keys and nonces, and a functional
     reference carries no distribution of any kind. The nonce-reuse
     construction below is a computation and not a game.

   So nothing here is a shipped primitive under R-05-059, and the tag
   comparison in `gcm_open` is ordinary structural equality: a constant-time
   comparison is the *binary's* obligation under R-05-062, taken at the
   artifact and not at this text.

   No Require. Nothing beyond the Rocq prelude is reachable, so `map`, `nth`,
   `firstn`, `skipn`, `seq`, `rev`, `repeat`, `fold_left` and `concat` are
   authored below in the idiom Keccak.v and DischargeSequence.v author theirs
   in. An assumption reachable through an import is an assumption inside the
   R-05-163 gate's reach, which is what that rule buys and what a convenience
   import would spend.

   The representation, and the one place it deliberately disagrees with
   Keccak.v. No register entry fixes any of this, so all four are readings of
   this file:

   1. A **byte** is a `list bool` of length 8 with the **most significant bit
      at the head**, which is FIPS 197 s3.1's own left-to-right writing of
      {b7 b6 b5 b4 b3 b2 b1 b0} and the order in which that byte's polynomial
      coefficients descend. `bit_num` reads FIPS 197's own index, where b0 is
      the least significant, and it is the only place the two orders meet.
   2. A **block** is a `list bool` of length 128 and is the concatenation of
      its sixteen bytes with **no reversal anywhere**, so the head of a block
      is the most significant bit of its first byte. That is SP 800-38D's own
      bit string x_0 x_1 ... x_127, and its head is the standard's x_0.
   3. **The GF(2^128) convention is the standard's own and it is reflected.**
      SP 800-38D s6.3 reads the block x_0 ... x_127 as the field element
      x_0 + x_1 a + ... + x_127 a^127, so the **leftmost** bit is the constant
      term, and its Algorithm 1 multiplies by a with a **right** shift and a
      reduction by R = 11100001 || 0^120 at the left end. That is the opposite
      of the convention an implementer reaches for, and getting it wrong is
      the defect `ghash_mul_without_the_reflection` below exhibits.
   4. Keccak.v puts the **least** significant bit of a lane at the head,
      because FIPS 202 s3.1.2 numbers a lane by z upward and reads a squeezed
      byte least significant bit first. The two files therefore disagree about
      bit order **on purpose**: each takes its own standard's, and a shared
      convention would have made one of the two a transcription of the other
      rather than of its source.

   The readings of the register this file takes:

   1. **R-10-024 fixes the cipher and this file is that cipher.** The entry
      freezes AES-GCM and names ChaCha20/Poly1305 the frozen-out alternative,
      so there is one AEAD to author and no menu. The plan's own M3.4 cell has
      *both AEADs* authored in Gallina, which disagrees with that entry; the
      disagreement is F-205d, it is open, and it is reported here rather than
      resolved, an entry being the review gate's to move.
   2. **The pair with the model is a pair because one derives what the other
      writes down.** `model/model/extensions/K/types_kext.sail` transcribes the
      forward and inverse S-box tables as 256-entry vectors and decodes the
      round constants by a case table; this file derives the S-box from the
      multiplicative inverse in GF(2^8) composed with the affine transform, and
      the round constants from the x^i recurrence, and then computes that what
      it derived is what FIPS 197 publishes. A derived-versus-published
      equality catches a transcription defect from the other side, which a
      second transcription of the same table cannot.
   3. **The two GHASH forms are stated against each other.**
      `model/model/extensions/vector_crypto/zvkg_insts.sail` reverses the bits
      inside each byte and then multiplies with a **left** shift and a
      reduction by 0x87 at the low byte, which is the standard's Algorithm 1
      seen through `brev8`. Both forms are written below and computed equal, so
      either is the other's image or one of them is wrong.
   4. **The oracle enters no trust base.** Every published answer below is a
      constant inside an `Example`'s own statement, never a `Definition`, and
      nothing above it depends on the answer being right: what a known-answer
      check buys is that the constant and the transcription were produced by
      different routes. Putting an answer in a `Definition` would also put it
      inside the seeded-mutation population, where a published byte moved off
      by one would score as a kill of the oracle rather than of the subject.
   5. **The four step mappings are the standard's own, by the standard's own
      names, in the standard's own order, and unfused**: SubBytes, ShiftRows,
      MixColumns and AddRoundKey, one definition each, composed once in
      `aes_round_over`; and their four inverses composed once in `inv_round`.
   6. **How much of the word "invertible" is discharged, and whose obligation
      that is.** No entry calls AES a permutation, so the obligation is one
      **this file states of itself**. Three of the four step maps carry it
      outright: SubBytes is a bijection on a byte, checked over all 256 and
      inverted by `inv_sub_byte` over all 256; ShiftRows is a permutation of
      the sixteen positions whose inverse recovers a state of sixteen
      **arbitrary** bytes; and AddRoundKey is an involution in the round key
      over arbitrary bits of equal length. **MixColumns is not shown a
      bijection.** What is shown is the algebraic fact underneath it, that the
      standard's a(x) and a^-1(x) multiply to {01} modulo x^4 + 1, and the
      round trip on the thirty-two single-bit columns, which span the column
      space over GF(2). The step from a spanning set to the whole map is
      GF(2)-linearity, which this file does not prove, so the composite claim
      that AES is a bijection is an obligation this file states and does not
      close. What stands beside it is the whole-cipher round trip at each of
      the three published key lengths, which is a value and not a proof.
   7. **The nonce is where the AEAD's security lives and the reference cannot
      hold it.** Two ciphertexts drawn under one key and one nonce carry the
      exclusive-or of their plaintexts, which is computed below at a published
      key. That is why R-05-126b gives a nonce-typed value the linear grade and
      why R-10-023 keeps the nonce per-extent random; neither is a property of
      this text, and the bound SP 800-38D places on one key's invocations is
      carried by no entry at all.

   Where this file sits in the storage stack, which is why the AEAD was the
   half of M3.4c worth authoring on its own. R-10-022 makes confidentiality and
   integrity of data at rest one pass, per-extent AEAD with a per-extent nonce
   and the tag serving as the stored checksum; R-10-022a puts the nonce and the
   tag in the index node rather than beside the ciphertext; R-10-023 keeps the
   tag off the dedup address. All three quantify over an AEAD, and until this
   file there was none in the tree.

   What is deliberately absent, with the entry that owes each decision. A
   register gap is reported, not closed:

   a. **No entry fixes the key length.** R-10-024 says AES-GCM and stops.
      R-05-058a freezes the suite by parameter set at Category 5 throughout and
      names ML-KEM-1024, ML-DSA-87 and SLH-DSA-SHAKE-256s, all three of them
      asymmetric or hash-based; Category 5 is itself *defined* by reference to
      the difficulty of an AES-256 key search, so reading a symmetric key
      length out of it would be reading the yardstick as the measurement. So
      the key length is a parameter here, `key_words`, and all three of FIPS
      197's own key lengths carry a published answer below.
   b. **No entry fixes the tag length.** SP 800-38D s5.2.1.2 admits 128, 120,
      112, 104 and 96 bits generally and 64 and 32 for named applications
      only; R-10-022 makes the tag the stored checksum and fixes no t. It is
      the parameter `tag_bits`, and `gcm_open` truncates by it.
   c. **No entry fixes the nonce length or which J0 construction is taken.**
      SP 800-38D s7.1 splits at a 96-bit IV, the short arm being a
      concatenation and the long one a GHASH. Both arms are exercised below at
      published answers. R-10-022 wants a per-extent nonce and R-10-023 wants
      it random, and neither is a length.
   d. **No entry carries the invocation bound.** SP 800-38D s8.3 bounds the
      invocations of the authenticated encryption function under one key. It
      is the field `invocations_per_key` below, and the theorem beside it is
      that nothing this file computes reads it, which is the shape of the gap:
      the bound is a discipline on the caller and no artifact here states one.
   e. **What a per-extent AEAD authenticates besides the extent is unstated.**
      R-10-022 and R-10-022a say where the nonce and the tag live and say
      nothing about the associated data. An extent sealed with empty A and one
      sealed with its own address are different constructions against the
      block services R-10-021 puts below the integrity line, and no entry
      chooses. It is the field `associated_data`.
   f. **R-10-022 names two tag constructions and R-10-024 freezes one out.**
      The entry says *the Poly1305/GHASH tag serving as the stored checksum*
      where R-10-024 freezes the cipher to AES-GCM and names ChaCha20/Poly1305
      the frozen-out alternative. Only GHASH is authored here.
   g. **No entry fixes the oracle pair for an authored AEAD**, exactly as none
      fixes it for an authored hash. R-15-058 names FIPS 202 and the ACVP
      vectors for the *model's* Keccak unit; nothing names anything for this.

   The literals taken from the standards, and there are no others. FIPS 197's
   8-bit byte, 4-by-4 state and four-word round key; the key lengths 4, 6 and 8
   words with Nr = Nk + 6 and the second substitution's Nk-above-six guard,
   which is a parameter here rather than a literal for the reason its own
   definition states; the reduction polynomial x^8 + x^4 + x^3 + x + 1 as
   its own exponent list; the affine transform's taps {0, 4, 5, 6, 7} and
   constant 0x63 and the inverse transform's taps {2, 5, 7} and constant 0x05;
   the MixColumns polynomial {03}x^3 + {01}x^2 + {01}x + {02} and its inverse
   {0b}x^3 + {0d}x^2 + {09}x + {0e}; and SP 800-38D's 128-bit block, its
   96-bit IV split, its 32-bit counter field, its 64-bit length fields, its
   s5.2.1.2 tag lengths as the two lists it states them in, five general and
   two restricted, and its reduction polynomial a^128 + a^7 + a^2 + a + 1 as
   its own exponent list.
   Everything else is derived: the round constants are the recurrence's, the
   S-box is the inverse and the affine map's, 0x1B is computed from the
   modulus, 0xE1 is computed from R's exponents, and the MixColumns matrix is
   computed from its polynomial.

   Non-vacuity (R-05-165, R-05-166). Every structural obligation below is
   stated of an arbitrary byte, state, key or construction, or enumerated over
   a domain the statement names, and seven constructions the standards' own
   sentences exclude are built here and refuted: an affine transform with the
   constant one below the standard's, a ShiftRows written against a transposed
   flattening of the state, the forward and inverse ShiftRows exchanged, a key
   expansion whose second-substitution guard is one higher, a GF(2^128)
   multiplication without the standard's byte-wise bit reflection, a GHASH
   input with A and C concatenated unpadded, and a counter mode started at J0
   rather than at inc32(J0). **Each is held to the single difference it
   exists to exhibit**, and each is shown to satisfy the obligations it does
   *not* break, so what refuses it is the named defect and not its shape.
   **Three of the seven are invisible to a whole family of inputs and the file
   says which**: the unpadded GHASH agrees with the standard's at every input
   whose associated data and ciphertext are both block-aligned, the counter
   started at J0 agrees at every empty plaintext, and the raised guard agrees
   at every key length FIPS 197 admits, parting from the standard's only at a
   key of seven words, which the standard does not carry. Inhabitation is the published
   answers themselves, so no check below holds of everything and none holds of
   nothing.

   Where each published answer came from, and under what instrument. The
   S-box table, the round-constant table, the MixColumns matrices, the key
   expansion words for the Appendix A key and the Appendix B ciphertext are
   FIPS 197's own, read at Appendices A.1, B and C.1 through C.3 and at
   sections 5.1.1, 5.1.3, 5.2 and 5.3.3. The five AES-GCM cases are the test
   cases published with the GCM specification, numbered 1 through 5 there, and
   that is the whole of their provenance: no ACVP file is quoted here and
   nothing in this repository pins what NIST's own validation sets carry, so
   saying these were those would be a claim about an external corpus with no
   measurement under it. **Every one of them was recomputed on 2026-09-03 by a
   second implementation before it was written down here**, an independent
   transcription of the two standards run against OpenSSL 3.5.5 through its
   Python binding, so each literal below reached this file by two routes and
   not one. Neither instrument is pinned, neither enters any trust base, and
   nothing above the answers depends on them.
   ========================================================================= *)

Open Scope list_scope.

(* -------------------------------------------------------------------------
   List helpers, authored rather than imported: the prelude carries the list
   type and not the library over it.
   ------------------------------------------------------------------------- *)

Fixpoint map_over {A B : Type} (f : A -> B) (l : list A) : list B :=
  match l with nil => nil | x :: r => f x :: map_over f r end.

Fixpoint length_of {A : Type} (l : list A) : nat :=
  match l with nil => 0 | _ :: r => S (length_of r) end.

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

(* The one out-of-range answer this file relies on, named once so that it is a
   decision rather than a default repeated at twenty sites, and pinned by an
   Example below rather than left unreachable. *)
Definition bit_at (l : list bool) (i : nat) : bool := nth_of i l false.

Fixpoint rev_onto {A : Type} (l acc : list A) : list A :=
  match l with nil => acc | x :: r => rev_onto r (x :: acc) end.

Definition rev_of {A : Type} (l : list A) : list A := rev_onto l nil.

Fixpoint repeat_of {A : Type} (n : nat) (x : A) : list A :=
  match n with 0 => nil | S k => x :: repeat_of k x end.

(* start through start + count - 1, built by a downward count rather than by
   appending one element at a time, an append per element being quadratic. *)
Fixpoint up_from (start count : nat) : list nat :=
  match count with 0 => nil | S k => start :: up_from (S start) k end.

Definition upto (n : nat) : list nat := up_from 0 n.

Fixpoint fold_over {A B : Type} (f : B -> A -> B) (acc : B) (l : list A) : B :=
  match l with nil => acc | x :: r => fold_over f (f acc x) r end.

Fixpoint concat_of {A : Type} (l : list (list A)) : list A :=
  match l with nil => nil | x :: r => x ++ concat_of r end.

Fixpoint all_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with nil => true | x :: r => andb (p x) (all_of p r) end.

Fixpoint count_where {A : Type} (p : A -> bool) (l : list A) : nat :=
  match l with
  | nil => 0
  | x :: r => if p x then S (count_where p r) else count_where p r
  end.

Fixpoint keep_where {A : Type} (p : A -> bool) (l : list A) : list A :=
  match l with
  | nil => nil
  | x :: r => if p x then x :: keep_where p r else keep_where p r
  end.

(* The fuel argument is the caller's bound on how many chunks there can be, the
   recursion being on the chunk count rather than on the list, which `drop_of`
   does not decrease structurally. *)
Fixpoint chunks_of {A : Type} (fuel n : nat) (l : list A) : list (list A) :=
  match fuel with
  | 0 => nil
  | S k => match l with
           | nil => nil
           | _ => take_of n l :: chunks_of k n (drop_of n l)
           end
  end.

Definition eqb_bool (x y : bool) : bool := negb (xorb x y).

Fixpoint bits_eqb (a b : list bool) : bool :=
  match a with
  | nil => match b with nil => true | _ => false end
  | x :: xs => match b with nil => false | y :: ys => andb (eqb_bool x y) (bits_eqb xs ys) end
  end.

Definition mem_nat (n : nat) (l : list nat) : bool :=
  negb (Nat.eqb (count_where (fun k => Nat.eqb k n) l) 0).

(* n bits of v, least significant first and then reversed, so no power of two
   is ever built: a 64-bit length field is a fold of halvings and never 2^64. *)
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

Fixpoint bxor (a b : list bool) : list bool :=
  match a with
  | nil => nil
  | x :: xs => match b with nil => nil | y :: ys => xorb x y :: bxor xs ys end
  end.

Definition bits_of_byte (v : nat) : byte := bits_be_of byte_bits v.

Definition byte_value (b : byte) : nat :=
  fold_over (fun (acc : nat) (x : bool) => 2 * acc + (if x then 1 else 0)) 0 b.

Definition bytes_from (l : list nat) : list byte := map_over bits_of_byte l.

Definition block_from (l : list nat) : block := concat_of (bytes_from l).

Definition bytes_of (s : list bool) : list nat :=
  map_over byte_value (chunks_of (length_of s) byte_bits s).

Definition state_of_block (b : block) : state := chunks_of block_bytes byte_bits b.

Definition block_of_state (s : state) : block := concat_of s.

(* FIPS 197's own bit index inside a byte, where b0 is the least significant.
   This is the only place the standard's numbering and this file's head-first
   list meet, and it is stated once for that reason. *)
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

(* a^254. The multiplicative group has order 255, so a^254 is a^-1 at every
   nonzero a; at zero it is zero, which is FIPS 197 s5.1.1's own convention for
   the element that has no inverse. Seven squarings and six products, rather
   than a search over 256 candidates. *)
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

(* The same clause read under the transposed flattening i = c + 4r, which is
   the defect a state drawn as a picture invites. It is a permutation of the
   sixteen positions like the standard's and it leaves four of them fixed like
   the standard's, and the two agree at exactly one position. *)
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

(* FIPS 197 s5.2 takes the second substitution where Nk exceeds six. **The
   guard is a parameter here and not a literal in the loop**, because it is a
   clause no key length the standard admits can decide: 6 < Nk and 7 < Nk agree
   at 4, at 6 and at 8, and part only at 7, which is not a key length FIPS 197
   carries. A seeded weakening of the six survives every published vector, so
   the alternative is built beside it and the two are parted below at the key
   length between them. *)
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

(* -------------------------------------------------------------------------
   The same multiplication as the curated model writes it. zvkg_insts.sail
   holds its operand as a Sail bits(128) whose byte 0 sits in the least
   significant eight bits, reverses the bits inside every byte with `brev8`,
   and then multiplies with a **left** shift and a reduction by 0x87 at the low
   byte. Written out here so that either form is the other's image or one of
   the two is wrong; and written out a second time **without** the reflection,
   which is the defect the reflected convention exists to invite.
   ------------------------------------------------------------------------- *)

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
  | S k => match x with
           | nil => nil
           | _ => bxor (take_of block_bits x)
                       (block_of_state (encrypt_with sched nr (state_of_block cb)))
                  ++ gctr_from k sched nr (inc32 cb) (drop_of block_bits x)
           end
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

(* Authenticated decryption, SP 800-38D s7.2. The tag comparison is ordinary
   structural equality: a constant-time comparison is the binary's obligation
   under R-05-062 and R-05-067, taken on the artifact, and this text makes no
   such claim. FAIL is `None` and it carries no plaintext with it, which is the
   whole of what the standard asks of the failure arm. *)
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

(* The same parameters with a bound stated. Nothing this file computes reads
   the field, which is the shape of the gap and not a bound taken here. *)
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
  rewrite Hk. rewrite Ht. rewrite Hn. rewrite Ha. reflexivity.
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
Proof. vm_compute. reflexivity. Qed.

Example the_derived_round_constants_are_the_published_table :
  map_over (fun i => byte_value (gpow_x i)) (upto 10) =
  0x01 :: 0x02 :: 0x04 :: 0x08 :: 0x10 ::
  0x20 :: 0x40 :: 0x80 :: 0x1B :: 0x36 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_derived_mix_matrix_is_the_published_one :
  mix_matrix mix_polynomial =
  0x02 :: 0x03 :: 0x01 :: 0x01 ::
  0x01 :: 0x02 :: 0x03 :: 0x01 ::
  0x01 :: 0x01 :: 0x02 :: 0x03 ::
  0x03 :: 0x01 :: 0x01 :: 0x02 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_derived_inverse_mix_matrix_is_the_published_one :
  mix_matrix inv_mix_polynomial =
  0x0E :: 0x0B :: 0x0D :: 0x09 ::
  0x09 :: 0x0E :: 0x0B :: 0x0D ::
  0x0D :: 0x09 :: 0x0E :: 0x0B ::
  0x0B :: 0x0D :: 0x09 :: 0x0E :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_low_half_of_the_modulus_is_the_published_byte :
  byte_value aes_modulus_low = 0x1B := eq_refl.

Example the_ghash_reduction_string_is_the_published_one :
  bytes_of ghash_R =
  0xE1 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 ::
  0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: nil.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The cipher against FIPS 197's own published answers, at all three key
   lengths. Every key, plaintext and ciphertext is a constant inside the
   statement that decides against it.
   ------------------------------------------------------------------------- *)

Example the_appendix_b_example_reaches_the_published_ciphertext :
  map_over byte_value
    (aes_encrypt 4
       (bytes_from (0x2B :: 0x7E :: 0x15 :: 0x16 :: 0x28 :: 0xAE :: 0xD2 :: 0xA6 ::
                    0xAB :: 0xF7 :: 0x15 :: 0x88 :: 0x09 :: 0xCF :: 0x4F :: 0x3C :: nil))
       (bytes_from (0x32 :: 0x43 :: 0xF6 :: 0xA8 :: 0x88 :: 0x5A :: 0x30 :: 0x8D ::
                    0x31 :: 0x31 :: 0x98 :: 0xA2 :: 0xE0 :: 0x37 :: 0x07 :: 0x34 :: nil))) =
  0x39 :: 0x25 :: 0x84 :: 0x1D :: 0x02 :: 0xDC :: 0x09 :: 0xFB ::
  0xDC :: 0x11 :: 0x85 :: 0x97 :: 0x19 :: 0x6A :: 0x0B :: 0x32 :: nil.
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

Example the_last_expanded_round_key_is_the_published_one :
  map_over byte_value
    (round_key (key_schedule 4
       (bytes_from (0x2B :: 0x7E :: 0x15 :: 0x16 :: 0x28 :: 0xAE :: 0xD2 :: 0xA6 ::
                    0xAB :: 0xF7 :: 0x15 :: 0x88 :: 0x09 :: 0xCF :: 0x4F :: 0x3C :: nil))) 10) =
  0xD0 :: 0x14 :: 0xF9 :: 0xA8 :: 0xC9 :: 0xEE :: 0x25 :: 0x89 ::
  0xE1 :: 0x3F :: 0x0C :: 0xC8 :: 0xB6 :: 0x63 :: 0x0C :: 0xA6 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_appendix_c_one_example_reaches_the_published_ciphertext :
  map_over byte_value
    (aes_encrypt 4 (bytes_from (upto 16))
       (bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                    0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil))) =
  0x69 :: 0xC4 :: 0xE0 :: 0xD8 :: 0x6A :: 0x7B :: 0x04 :: 0x30 ::
  0xD8 :: 0xCD :: 0xB7 :: 0x80 :: 0x70 :: 0xB4 :: 0xC5 :: 0x5A :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_appendix_c_two_example_reaches_the_published_ciphertext :
  map_over byte_value
    (aes_encrypt 6 (bytes_from (upto 24))
       (bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                    0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil))) =
  0xDD :: 0xA9 :: 0x7C :: 0xA4 :: 0x86 :: 0x4C :: 0xDF :: 0xE0 ::
  0x6E :: 0xAF :: 0x70 :: 0xA0 :: 0xEC :: 0x0D :: 0x71 :: 0x91 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_appendix_c_three_example_reaches_the_published_ciphertext :
  map_over byte_value
    (aes_encrypt 8 (bytes_from (upto 32))
       (bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                    0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil))) =
  0x8E :: 0xA2 :: 0xB7 :: 0xCA :: 0x51 :: 0x67 :: 0x45 :: 0xBF ::
  0xEA :: 0xFC :: 0x49 :: 0x90 :: 0x4B :: 0x49 :: 0x60 :: 0x89 :: nil.
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The step maps, over arbitrary inputs or over the whole domain they act on.
   ------------------------------------------------------------------------- *)

(* The image is taken once and counted against, rather than the map being
   applied inside the count: 256 applications and 65,536 comparisons where the
   other order is 65,536 applications. *)
Definition is_a_bijection_on_bytes (f : byte -> byte) : bool :=
  let image := map_over f all_bytes in
  all_of (fun b => Nat.eqb (count_where (fun a => bits_eqb a b) image) 1) all_bytes.

Example sub_byte_is_a_bijection_on_a_byte :
  is_a_bijection_on_bytes sub_byte = true.
Proof. vm_compute. reflexivity. Qed.

Example the_inverse_substitution_recovers_every_byte :
  all_of (fun b => bits_eqb (inv_sub_byte (sub_byte b)) b) all_bytes = true.
Proof. vm_compute. reflexivity. Qed.

Example the_field_inverse_is_an_inverse_at_every_nonzero_byte :
  all_of (fun b => if bits_eqb b zero_byte
                   then bits_eqb (ginv b) zero_byte
                   else bits_eqb (gmul b (ginv b)) one_byte)
         all_bytes = true.
Proof. vm_compute. reflexivity. Qed.

(* The field multiplication is commutative over the whole of its domain, which
   is 65,536 pairs and not a sample. *)
Example the_field_multiplication_is_commutative :
  all_of (fun a => all_of (fun b => bits_eqb (gmul a b) (gmul b a)) all_bytes) all_bytes = true.
Proof. vm_compute. reflexivity. Qed.

Example one_is_the_identity_and_zero_the_annihilator :
  all_of (fun a => andb (bits_eqb (gmul one_byte a) a)
                        (bits_eqb (gmul zero_byte a) zero_byte))
         all_bytes = true.
Proof. vm_compute. reflexivity. Qed.

(* Distribution and association over every element in the first argument and
   over the eight basis elements in the other two, the basis being what spans
   the additive group. The domain is named because it is not the whole one. *)
Example the_field_multiplication_distributes_over_the_basis :
  all_of (fun a => all_of (fun b => all_of (fun c =>
            bits_eqb (gmul a (bxor b c)) (bxor (gmul a b) (gmul a c)))
            basis_bytes) basis_bytes) all_bytes = true.
Proof. vm_compute. reflexivity. Qed.

Example the_field_multiplication_associates_over_the_basis :
  all_of (fun a => all_of (fun b => all_of (fun c =>
            bits_eqb (gmul (gmul a b) c) (gmul a (gmul b c)))
            basis_bytes) basis_bytes) all_bytes = true.
Proof. vm_compute. reflexivity. Qed.

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
Theorem the_row_shift_is_invertible_on_an_arbitrary_state :
  forall b0 b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 b11 b12 b13 b14 b15 : byte,
    inv_shift_rows (shift_rows (
      b0 :: b1 :: b2 :: b3 :: b4 :: b5 :: b6 :: b7 ::
      b8 :: b9 :: b10 :: b11 :: b12 :: b13 :: b14 :: b15 :: nil))
    =
    b0 :: b1 :: b2 :: b3 :: b4 :: b5 :: b6 :: b7 ::
    b8 :: b9 :: b10 :: b11 :: b12 :: b13 :: b14 :: b15 :: nil.
Proof. intros. vm_compute. reflexivity. Qed.

(* AddRoundKey is an involution in the round key, over arbitrary bits. *)
Lemma xorb_cancels : forall x y : bool, xorb (xorb x y) y = x.
Proof. intros x y. destruct x; destruct y; reflexivity. Qed.

Lemma bxor_cancels : forall a k : list bool, length_of a = length_of k -> bxor (bxor a k) k = a.
Proof.
  induction a as [|x a IH]; intros k H.
  - reflexivity.
  - destruct k as [|y k].
    + discriminate H.
    + simpl in H. injection H as H. simpl.
      rewrite xorb_cancels. rewrite (IH k H). reflexivity.
Qed.

Lemma eqb_nat_eq : forall m n : nat, Nat.eqb m n = true -> m = n.
Proof.
  induction m as [|m IH]; intros n H.
  - destruct n as [|n]. + reflexivity. + discriminate H.
  - destruct n as [|n]. + discriminate H. + simpl in H. rewrite (IH n H). reflexivity.
Qed.

(* Two states of the same shape: the same number of bytes, each of the same
   width. The hypothesis is stated because a state and a round key of
   different shapes are xored to the shorter of the two, and an involution
   over that is a claim about truncation rather than about the key. *)
Fixpoint same_shape (a b : state) : bool :=
  match a with
  | nil => match b with nil => true | _ => false end
  | x :: xs => match b with
               | nil => false
               | y :: ys => andb (Nat.eqb (length_of x) (length_of y)) (same_shape xs ys)
               end
  end.

Theorem add_round_key_is_an_involution_in_the_round_key :
  forall s k : state, same_shape s k = true -> add_round_key k (add_round_key k s) = s.
Proof.
  unfold add_round_key. intros s. induction s as [|x s IH]; intros k H.
  - reflexivity.
  - destruct k as [|y k].
    + discriminate H.
    + simpl in H. simpl.
      destruct (Nat.eqb (length_of x) (length_of y)) eqn:E.
      * simpl in H. rewrite (bxor_cancels x y (eqb_nat_eq _ _ E)).
        rewrite (IH k H). reflexivity.
      * discriminate H.
Qed.

Example the_round_key_and_the_state_have_the_same_shape :
  same_shape (state_of_block (block_from (upto block_bytes)))
             (round_key (key_schedule 4 (bytes_from (upto block_bytes))) 3) = true.
Proof. vm_compute. reflexivity. Qed.

(* MixColumns: the two polynomials are inverse in the ring the step multiplies
   in, and the round trip holds on the thirty-two columns that span the column
   space. The step from a spanning set to the whole map is GF(2)-linearity,
   which this file does not prove and does not claim. *)
Example the_two_mix_polynomials_are_inverse_modulo_x_to_the_fourth_plus_one :
  map_over byte_value (poly4_mul mix_polynomial inv_mix_polynomial) = 1 :: 0 :: 0 :: 0 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example there_are_thirty_two_single_bit_columns :
  length_of single_bit_columns = 32 := eq_refl.

Example the_inverse_polynomial_recovers_every_single_bit_column :
  all_of (fun col => bits_eqb (concat_of (poly4_mul inv_mix_polynomial (poly4_mul mix_polynomial col)))
                              (concat_of col))
         single_bit_columns = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The three near alternatives to a step map, each held to the single
   difference it exists to exhibit and each shown to keep the obligations it
   does not break.
   ------------------------------------------------------------------------- *)

Example the_wrong_affine_constant_is_still_a_bijection :
  is_a_bijection_on_bytes sub_byte_with_the_wrong_constant = true.
Proof. vm_compute. reflexivity. Qed.

Example the_wrong_affine_constant_moves_the_low_bit_and_nothing_else :
  all_of (fun b => Nat.eqb (byte_value (bxor (sub_byte b) (sub_byte_with_the_wrong_constant b))) 1)
         all_bytes = true.
Proof. vm_compute. reflexivity. Qed.

Example the_wrong_affine_constant_misses_the_published_ciphertext :
  bits_eqb (block_of_state
              (aes_encrypt_over sub_byte_with_the_wrong_constant shift_rows 4
                 (bytes_from (upto 16))
                 (bytes_from (0x00 :: 0x11 :: 0x22 :: 0x33 :: 0x44 :: 0x55 :: 0x66 :: 0x77 ::
                              0x88 :: 0x99 :: 0xAA :: 0xBB :: 0xCC :: 0xDD :: 0xEE :: 0xFF :: nil))))
           (block_from (0x69 :: 0xC4 :: 0xE0 :: 0xD8 :: 0x6A :: 0x7B :: 0x04 :: 0x30 ::
                        0xD8 :: 0xCD :: 0xB7 :: 0x80 :: 0x70 :: 0xB4 :: 0xC5 :: 0x5A :: nil))
  = false.
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

Example one_is_the_identity_of_the_field_multiplication :
  all_of (fun x => bits_eqb (gf128_mul x (block_from (0x80 :: repeat_of 15 0 ))) x)
         ghash_probe_blocks = true.
Proof. vm_compute. reflexivity. Qed.

Example the_field_multiplication_on_blocks_is_commutative :
  all_of (fun p => bits_eqb (gf128_mul (fst p) (snd p)) (gf128_mul (snd p) (fst p)))
         ghash_probe_pairs = true.
Proof. vm_compute. reflexivity. Qed.

Example the_models_form_and_the_standards_form_are_one_multiplication :
  all_of (fun p => bits_eqb (ghash_mul_the_models_way (fst p) (snd p))
                            (gf128_mul (fst p) (snd p)))
         ghash_probe_pairs = true.
Proof. vm_compute. reflexivity. Qed.

(* The form without the reflection is the standard's multiplication under a
   byte-wise reversal of the bits, so it is a field multiplication too and
   commutative just as the standard's is. What refuses it is that it names the
   wrong bit strings, and the unit is where that is smallest and sharpest: its
   identity is the standard's reflected, 0x01 00..00 where the standard's is
   0x80 00..00. Both are computed below, the second as a refusal, because an
   identity carried over from the isomorphism rather than decided at the
   element is the one obligation this near alternative could be let off. *)
Example the_unreflected_form_is_the_standards_under_a_byte_wise_reversal :
  all_of (fun p => bits_eqb (ghash_mul_without_the_reflection (fst p) (snd p))
                            (reflect_block (gf128_mul (reflect_block (fst p))
                                                      (reflect_block (snd p)))))
         ghash_probe_pairs = true.
Proof. vm_compute. reflexivity. Qed.

Example the_unreflected_form_is_commutative_too :
  all_of (fun p => bits_eqb (ghash_mul_without_the_reflection (fst p) (snd p))
                            (ghash_mul_without_the_reflection (snd p) (fst p)))
         ghash_probe_pairs = true.
Proof. vm_compute. reflexivity. Qed.

Example the_unreflected_form_has_the_reflected_identity :
  all_of (fun x => bits_eqb (ghash_mul_without_the_reflection x
                               (block_from (0x01 :: repeat_of 15 0))) x)
         ghash_probe_blocks = true.
Proof. vm_compute. reflexivity. Qed.

Example the_standards_identity_is_not_the_unreflected_forms :
  all_of (fun x => bits_eqb (ghash_mul_without_the_reflection x
                               (block_from (0x80 :: repeat_of 15 0))) x)
         ghash_probe_blocks = false.
Proof. vm_compute. reflexivity. Qed.

Example the_unreflected_form_is_a_different_multiplication :
  all_of (fun p => bits_eqb (ghash_mul_without_the_reflection (fst p) (snd p))
                            (gf128_mul (fst p) (snd p)))
         ghash_probe_pairs = false.
Proof. vm_compute. reflexivity. Qed.

Example the_counter_field_wraps_and_leaves_the_rest_of_the_block_alone :
  bytes_of (inc32 (block_from (repeat_of 12 0xAA ++ (0xFF :: 0xFF :: 0xFF :: 0xFF :: nil)))) =
  0xAA :: 0xAA :: 0xAA :: 0xAA :: 0xAA :: 0xAA :: 0xAA :: 0xAA ::
  0xAA :: 0xAA :: 0xAA :: 0xAA :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: nil.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   AES-GCM against the published test cases. Each key, IV, plaintext,
   associated data, ciphertext and tag is a constant inside the statement that
   decides against it.
   ------------------------------------------------------------------------- *)

Example the_hash_subkey_of_the_all_zero_key_is_the_published_one :
  bytes_of (gcm_subkey (key_schedule 4 (bytes_from (repeat_of 16 0))) 10) =
  0x66 :: 0xE9 :: 0x4B :: 0xD4 :: 0xEF :: 0x8A :: 0x2C :: 0x3B ::
  0x88 :: 0x4C :: 0xFA :: 0x59 :: 0xCA :: 0x34 :: 0x2B :: 0x2E :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_first_published_case_reaches_its_tag :
  bytes_of (snd (gcm_encrypt 4 (bytes_from (repeat_of 16 0))
                             (block_from (repeat_of 12 0)) nil nil)) =
  0x58 :: 0xE2 :: 0xFC :: 0xCE :: 0xFA :: 0x7E :: 0x30 :: 0x61 ::
  0x36 :: 0x7F :: 0x1D :: 0x57 :: 0xA4 :: 0xE7 :: 0x45 :: 0x5A :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_second_published_case_reaches_its_ciphertext_and_tag :
  let r := gcm_encrypt 4 (bytes_from (repeat_of 16 0)) (block_from (repeat_of 12 0)) nil
                       (block_from (repeat_of 16 0)) in
  pair (bytes_of (fst r)) (bytes_of (snd r)) =
  pair (0x03 :: 0x88 :: 0xDA :: 0xCE :: 0x60 :: 0xB6 :: 0xA3 :: 0x92 ::
        0xF3 :: 0x28 :: 0xC2 :: 0xB9 :: 0x71 :: 0xB2 :: 0xFE :: 0x78 :: nil)
       (0xAB :: 0x6E :: 0x47 :: 0xD4 :: 0x2C :: 0xEC :: 0x13 :: 0xBD ::
        0xF5 :: 0x3A :: 0x67 :: 0xB2 :: 0x12 :: 0x57 :: 0xBD :: 0xDF :: nil).
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

(* The fifth published case takes the other J0 arm: its IV is 64 bits, so the
   initial counter block is a GHASH of the IV and its length rather than a
   concatenation. Without this case the long arm is a branch no vector enters. *)
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
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   Authenticated decryption, and the two near alternatives to the composition.
   ------------------------------------------------------------------------- *)

Example the_open_of_a_seal_returns_the_message_and_a_flipped_tag_bit_returns_nothing :
  let key := bytes_from (0xFE :: 0xFF :: 0xE9 :: 0x92 :: 0x86 :: 0x65 :: 0x73 :: 0x1C ::
                         0x6D :: 0x6A :: 0x8F :: 0x94 :: 0x67 :: 0x30 :: 0x83 :: 0x08 :: nil) in
  let iv := block_from (0xCA :: 0xFE :: 0xBA :: 0xBE :: 0xFA :: 0xCE :: 0xDB :: 0xAD ::
                        0xDE :: 0xCA :: 0xF8 :: 0x88 :: nil) in
  let aad := block_from (0xFE :: 0xED :: 0xFA :: 0xCE :: 0xDE :: 0xAD :: 0xBE :: 0xEF :: nil) in
  let m := block_from (upto block_bytes) in
  let r := gcm_encrypt 4 key iv aad m in
  andb (match gcm_open block_bits 4 key iv aad (fst r) (snd r) with
        | Some p => bits_eqb p m
        | None => false
        end)
       (match gcm_open block_bits 4 key iv aad (fst r) (bxor (snd r) (block_from (1 :: repeat_of 15 0))) with
        | Some _ => false
        | None => true
        end) = true.
Proof. vm_compute. reflexivity. Qed.

(* The unpadded GHASH input agrees with the standard's at every published case
   whose associated data and ciphertext are both block-aligned, which is the
   first three of the five, and parts from it at the fourth. All three of those
   carry an **empty** associated data, where the padding of A is absent in any
   case, so a fourth conjunct of this file's own carries the aligned case the
   five do not: a sixteen-byte associated data beside a thirty-two-byte
   plaintext, where both paddings are present and both are empty. A vector set
   with no unaligned member cannot see this defect at all. *)
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
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

(* And the counter started at J0 agrees at every empty plaintext, which is the
   first published case, and parts from the standard at the second. A vector
   set with no nonempty plaintext cannot see this defect either. *)
Example the_counter_started_at_j0_agrees_at_the_empty_plaintext :
  let a := gcm_encrypt_from_j0 4 (bytes_from (repeat_of 16 0))
                               (block_from (repeat_of 12 0)) nil nil in
  let b := gcm_encrypt 4 (bytes_from (repeat_of 16 0)) (block_from (repeat_of 12 0)) nil nil in
  andb (bits_eqb (fst a) (fst b)) (bits_eqb (snd a) (snd b)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_counter_started_at_j0_misses_the_second_published_ciphertext :
  bits_eqb (fst (gcm_encrypt_from_j0 4 (bytes_from (repeat_of 16 0))
                                     (block_from (repeat_of 12 0)) nil
                                     (block_from (repeat_of 16 0))))
           (block_from (0x03 :: 0x88 :: 0xDA :: 0xCE :: 0x60 :: 0xB6 :: 0xA3 :: 0x92 ::
                        0xF3 :: 0x28 :: 0xC2 :: 0xB9 :: 0x71 :: 0xB2 :: 0xFE :: 0x78 :: nil))
  = false.
Proof. vm_compute. reflexivity. Qed.

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
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The parameter record inhabited, and the field nothing reads.
   ------------------------------------------------------------------------- *)

Example the_witness_at_the_platform_parameters_is_the_first_published_case :
  bytes_of (snd (seal_under demo demo_key nil)) =
  0x58 :: 0xE2 :: 0xFC :: 0xCE :: 0xFA :: 0x7E :: 0x30 :: 0x61 ::
  0x36 :: 0x7F :: 0x1D :: 0x57 :: 0xA4 :: 0xE7 :: 0x45 :: 0x5A :: nil.
Proof. vm_compute. reflexivity. Qed.

Example a_stated_invocation_bound_changes_nothing_the_primitive_computes :
  let a := seal_under demo demo_key nil in
  let b := seal_under demo_with_a_stated_bound demo_key nil in
  andb (bits_eqb (fst a) (fst b)) (bits_eqb (snd a) (snd b)) = true.
Proof. vm_compute. reflexivity. Qed.

Example a_truncated_tag_is_a_prefix_of_the_full_one :
  let full := snd (seal_under demo demo_key nil) in
  let short := snd (seal_under demo_truncated_tag demo_key nil) in
  andb (Nat.eqb (length_of short) shortest_admissible_tag)
       (bits_eqb short (take_of shortest_admissible_tag full)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_three_key_lengths_carry_three_round_counts :
  map_over (fun p => rounds_for (key_words p)) (demo :: demo_aes192 :: demo_aes256 :: nil) =
  10 :: 12 :: 14 :: nil := eq_refl.

(* -------------------------------------------------------------------------
   The decisions a reader would otherwise take on trust because nothing above
   reaches them: the out-of-range answer, the geometry, the key schedule's own
   size, and the admissible tag lengths the standard states and the register
   does not choose from. A fixture nothing reaches is a site a seeded weakening
   survives at rather than a site nothing can go wrong in.
   ------------------------------------------------------------------------- *)

Example a_bit_off_the_end_of_a_byte_is_zero : bit_at nil 0 = false := eq_refl.

Example the_block_is_sixteen_bytes_of_eight_bits :
  andb (Nat.eqb block_bytes 16) (Nat.eqb block_bits 128) = true := eq_refl.

Example the_key_schedule_has_one_round_key_per_round_and_one_more :
  map_over (fun nk => length_of (key_schedule nk (bytes_from (upto (4 * nk)))))
           (4 :: 6 :: 8 :: nil) =
  44 :: 52 :: 60 :: nil.
Proof. vm_compute. reflexivity. Qed.

(* The second substitution's guard, at the key lengths that decide it. The three
   FIPS 197 key lengths do not: they agree under either guard, and only a key of
   seven words parts them, which the standard does not carry and this file
   therefore states of the expansion rather than of the cipher. Without this
   pair the six is a literal every published vector accepts one higher. *)
(* RotWord, FIPS 197 s5.2, is a cyclic rotation of the four bytes of a word, so
   it moves each byte one place, adds none, and is the identity after four
   applications. **Neither clause is decided by anything else in this file**:
   `xor_bytes` truncates to the shorter of its two operands, so a rotation
   returning a longer word is silently cut back to four bytes by the
   exclusive-or that consumes it, and every published answer stands. Both are
   stated over four arbitrary bytes for that reason. *)
Theorem rotating_a_word_moves_each_byte_one_place_and_adds_none :
  forall b0 b1 b2 b3 : byte,
    rot_word (b0 :: b1 :: b2 :: b3 :: nil) = b1 :: b2 :: b3 :: b0 :: nil.
Proof. intros. reflexivity. Qed.

Theorem rotating_a_word_four_times_is_the_identity :
  forall b0 b1 b2 b3 : byte,
    rot_word (rot_word (rot_word (rot_word (b0 :: b1 :: b2 :: b3 :: nil)))) =
    b0 :: b1 :: b2 :: b3 :: nil.
Proof. intros. reflexivity. Qed.

Example the_two_substitution_guards_agree_at_every_key_length_the_standard_carries :
  all_of (fun nk =>
            let k := bytes_from (upto (nb * nk)) in
            bits_eqb (concat_of (concat_of (key_schedule_over sub_byte
                                              second_substitution_guard nk k)))
                     (concat_of (concat_of (key_schedule_over sub_byte
                                              raised_substitution_guard nk k))))
         (4 :: 6 :: 8 :: nil) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_two_substitution_guards_part_at_the_key_length_between_them :
  let k := bytes_from (upto (nb * 7)) in
  bits_eqb (concat_of (concat_of (key_schedule_over sub_byte
                                    second_substitution_guard 7 k)))
           (concat_of (concat_of (key_schedule_over sub_byte
                                    raised_substitution_guard 7 k))) = false.
Proof. vm_compute. reflexivity. Qed.

Example the_last_round_key_is_the_last_four_words :
  all_of (fun nk => Nat.eqb (length_of (round_key (key_schedule nk (bytes_from (upto (4 * nk))))
                                                  (rounds_for nk)))
                            block_bytes)
         (4 :: 6 :: 8 :: nil) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_full_tag_is_the_longest_admissible_one :
  Nat.eqb (nth_of 0 admissible_tag_lengths 0) block_bits = true := eq_refl.

(* Both lists held to the standard's own shape **and to its own count**, rather
   than left as literals no computation visits. The admissible lengths descend
   one byte at a time from the full tag and there are five of them; each
   restricted length is a whole number of bytes below the shortest admissible
   one and there are two. The counts are exactly what the shape alone leaves
   free, and they are not decoration: without them a sixth admissible length of
   88 descends one byte at a time like the five above it, and a third
   restricted length of 24 is a whole number of bytes below the shortest
   admissible one like the two beside it, so both checks below pass on lists SP
   800-38D s5.2.1.2 does not admit. A tag length nothing reaches is a site a
   seeded weakening survives at rather than a site nothing can go wrong in. *)
Example the_admissible_tag_lengths_descend_one_byte_at_a_time_from_the_full_tag :
  all_of (fun i => Nat.eqb (nth_of i admissible_tag_lengths 0) (block_bits - byte_bits * i))
         (upto (length_of admissible_tag_lengths)) = true.
Proof. vm_compute. reflexivity. Qed.

Example every_restricted_tag_length_is_whole_bytes_below_the_shortest_admissible_one :
  all_of (fun t => andb (Nat.eqb (Nat.modulo t byte_bits) 0)
                        (Nat.ltb t shortest_admissible_tag))
         restricted_tag_lengths = true.
Proof. vm_compute. reflexivity. Qed.

Example the_two_tag_length_lists_carry_the_counts_the_standard_states :
  andb (Nat.eqb (length_of admissible_tag_lengths) 5)
       (Nat.eqb (length_of restricted_tag_lengths) 2) = true := eq_refl.

(* Truncating at a listed length takes a whole number of bytes off the front of
   the published tag and no more, which is the whole of what makes a listed
   length a length *of this tag*. The equality is the weakest of the three
   clauses and holds of every natural number, both sides being the same block
   under `take_of`; the length clause is what refuses a t above 128 and the
   whole-byte clause what refuses a t that is not a byte boundary, so the
   statement decides the domain it quantifies over rather than passing over it.
   Without the two the check is true of `7 :: 5000 :: 3 :: 999 :: nil`. *)
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
Proof. vm_compute. reflexivity. Qed.

(* The sixteen bytes that are their own bit reversal, which is what makes the
   reflection invisible on a byte and visible on a block. *)
Definition palindromic_bytes : list byte :=
  keep_where (fun b => bits_eqb (rev_of b) b) all_bytes.

Example there_are_sixteen_bytes_that_are_their_own_reversal :
  length_of palindromic_bytes = 16.
Proof. vm_compute. reflexivity. Qed.

Example the_reflection_fixes_a_block_of_those_bytes_and_moves_the_others :
  andb (all_of (fun b => bits_eqb (reflect_block (concat_of (repeat_of block_bytes b)))
                                  (concat_of (repeat_of block_bytes b)))
               palindromic_bytes)
       (negb (bits_eqb (reflect_block (block_from (upto block_bytes)))
                       (block_from (upto block_bytes)))) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The R-05-163 assumption gate reads this block. Every shipped constant is
   enumerated from its own proof term and held against the declared set: there
   is no Admitted, no Axiom, no top-level Parameter and no Require anywhere
   above, and nothing is declared inside the development to make the gate pass.
   R-05-164 reads the declared set from the register and it is empty, so the
   only passing line is the one this block prints, once per constant.
   ------------------------------------------------------------------------- *)
Print Assumptions map_over.
Print Assumptions length_of.
Print Assumptions take_of.
Print Assumptions drop_of.
Print Assumptions nth_of.
Print Assumptions bit_at.
Print Assumptions rev_onto.
Print Assumptions rev_of.
Print Assumptions repeat_of.
Print Assumptions up_from.
Print Assumptions upto.
Print Assumptions fold_over.
Print Assumptions concat_of.
Print Assumptions all_of.
Print Assumptions count_where.
Print Assumptions keep_where.
Print Assumptions chunks_of.
Print Assumptions eqb_bool.
Print Assumptions bits_eqb.
Print Assumptions mem_nat.
Print Assumptions bits_le_of.
Print Assumptions bits_be_of.
Print Assumptions byte.
Print Assumptions block.
Print Assumptions state.
Print Assumptions byte_bits.
Print Assumptions rows.
Print Assumptions nb.
Print Assumptions block_bytes.
Print Assumptions block_bits.
Print Assumptions zero_byte.
Print Assumptions zero_block.
Print Assumptions bxor.
Print Assumptions bits_of_byte.
Print Assumptions byte_value.
Print Assumptions bytes_from.
Print Assumptions block_from.
Print Assumptions bytes_of.
Print Assumptions state_of_block.
Print Assumptions block_of_state.
Print Assumptions bit_num.
Print Assumptions byte_of_exponents.
Print Assumptions all_bytes.
Print Assumptions basis_bytes.
Print Assumptions one_byte.
Print Assumptions aes_modulus_exponents.
Print Assumptions aes_modulus_low.
Print Assumptions xtime.
Print Assumptions gmul_from.
Print Assumptions gmul.
Print Assumptions gsquare.
Print Assumptions ginv_from.
Print Assumptions ginv.
Print Assumptions affine_taps.
Print Assumptions affine_constant.
Print Assumptions inv_affine_taps.
Print Assumptions inv_affine_constant.
Print Assumptions wrong_affine_constant.
Print Assumptions affine_over.
Print Assumptions sub_byte_over.
Print Assumptions sub_byte.
Print Assumptions sub_byte_with_the_wrong_constant.
Print Assumptions inv_sub_byte.
Print Assumptions state_index.
Print Assumptions row_index.
Print Assumptions column_index.
Print Assumptions byte_of_state.
Print Assumptions permute.
Print Assumptions shift_rows_index.
Print Assumptions inv_shift_rows_index.
Print Assumptions transposed_shift_rows_index.
Print Assumptions shift_rows.
Print Assumptions inv_shift_rows.
Print Assumptions shift_rows_transposed.
Print Assumptions poly4_mul.
Print Assumptions mix_polynomial.
Print Assumptions inv_mix_polynomial.
Print Assumptions mix_matrix.
Print Assumptions mix_columns_over.
Print Assumptions mix_columns.
Print Assumptions inv_mix_columns.
Print Assumptions single_bit_columns.
Print Assumptions xor_bytes.
Print Assumptions add_round_key.
Print Assumptions gpow_x.
Print Assumptions rcon_word.
Print Assumptions rot_word.
Print Assumptions sub_word_over.
Print Assumptions expand_from.
Print Assumptions second_substitution_guard.
Print Assumptions raised_substitution_guard.
Print Assumptions rounds_for.
Print Assumptions key_schedule_over.
Print Assumptions key_schedule.
Print Assumptions round_key.
Print Assumptions aes_round_over.
Print Assumptions aes_final_round_over.
Print Assumptions encrypt_over.
Print Assumptions encrypt_with.
Print Assumptions aes_encrypt_over.
Print Assumptions aes_encrypt.
Print Assumptions inv_round.
Print Assumptions aes_decrypt.
Print Assumptions ghash_modulus_exponents.
Print Assumptions ghash_R.
Print Assumptions shift_right_1.
Print Assumptions gf128_double.
Print Assumptions gf128_mul_from.
Print Assumptions gf128_mul.
Print Assumptions sail_word_of_block.
Print Assumptions block_of_sail_word.
Print Assumptions brev8.
Print Assumptions reflect_block.
Print Assumptions sail_reduction.
Print Assumptions sail_shift_left.
Print Assumptions sail_gmul_from.
Print Assumptions sail_gmul.
Print Assumptions ghash_mul_the_models_way.
Print Assumptions ghash_mul_without_the_reflection.
Print Assumptions ghash_over.
Print Assumptions ghash.
Print Assumptions counter_bits.
Print Assumptions increment_lsb_first.
Print Assumptions inc32.
Print Assumptions gctr_from.
Print Assumptions gctr.
Print Assumptions nonce_split.
Print Assumptions length_field_bits.
Print Assumptions gcm_pad.
Print Assumptions ghash_input_padded.
Print Assumptions ghash_input_unpadded.
Print Assumptions gcm_j0.
Print Assumptions gcm_subkey.
Print Assumptions gcm_over.
Print Assumptions gcm_encrypt.
Print Assumptions gcm_encrypt_unpadded.
Print Assumptions gcm_encrypt_from_j0.
Print Assumptions gcm_open.
Print Assumptions admissible_tag_lengths.
Print Assumptions restricted_tag_lengths.
Print Assumptions AeadParameters.
Print Assumptions key_words.
Print Assumptions tag_bits.
Print Assumptions nonce.
Print Assumptions associated_data.
Print Assumptions invocations_per_key.
Print Assumptions seal_under.
Print Assumptions demo.
Print Assumptions demo_aes192.
Print Assumptions demo_aes256.
Print Assumptions shortest_admissible_tag.
Print Assumptions demo_truncated_tag.
Print Assumptions demo_with_a_stated_bound.
Print Assumptions demo_key.
Print Assumptions the_seal_reads_four_fields_and_the_invocation_bound_is_not_one_of_them.
Print Assumptions the_derived_sbox_is_the_published_table.
Print Assumptions the_derived_round_constants_are_the_published_table.
Print Assumptions the_derived_mix_matrix_is_the_published_one.
Print Assumptions the_derived_inverse_mix_matrix_is_the_published_one.
Print Assumptions the_low_half_of_the_modulus_is_the_published_byte.
Print Assumptions the_ghash_reduction_string_is_the_published_one.
Print Assumptions the_appendix_b_example_reaches_the_published_ciphertext.
Print Assumptions the_first_expanded_round_key_is_the_published_one.
Print Assumptions the_last_expanded_round_key_is_the_published_one.
Print Assumptions the_appendix_c_one_example_reaches_the_published_ciphertext.
Print Assumptions the_appendix_c_two_example_reaches_the_published_ciphertext.
Print Assumptions the_appendix_c_three_example_reaches_the_published_ciphertext.
Print Assumptions the_inverse_cipher_recovers_the_plaintext_at_every_key_length.
Print Assumptions is_a_bijection_on_bytes.
Print Assumptions sub_byte_is_a_bijection_on_a_byte.
Print Assumptions the_inverse_substitution_recovers_every_byte.
Print Assumptions the_field_inverse_is_an_inverse_at_every_nonzero_byte.
Print Assumptions the_field_multiplication_is_commutative.
Print Assumptions one_is_the_identity_and_zero_the_annihilator.
Print Assumptions the_field_multiplication_distributes_over_the_basis.
Print Assumptions the_field_multiplication_associates_over_the_basis.
Print Assumptions covers_each_index_once.
Print Assumptions shift_rows_is_a_permutation_of_the_sixteen_positions.
Print Assumptions the_inverse_row_shift_is_a_permutation_too.
Print Assumptions the_row_shift_is_invertible_on_an_arbitrary_state.
Print Assumptions xorb_cancels.
Print Assumptions bxor_cancels.
Print Assumptions eqb_nat_eq.
Print Assumptions same_shape.
Print Assumptions add_round_key_is_an_involution_in_the_round_key.
Print Assumptions the_round_key_and_the_state_have_the_same_shape.
Print Assumptions the_two_mix_polynomials_are_inverse_modulo_x_to_the_fourth_plus_one.
Print Assumptions there_are_thirty_two_single_bit_columns.
Print Assumptions the_inverse_polynomial_recovers_every_single_bit_column.
Print Assumptions the_wrong_affine_constant_is_still_a_bijection.
Print Assumptions the_wrong_affine_constant_moves_the_low_bit_and_nothing_else.
Print Assumptions the_wrong_affine_constant_misses_the_published_ciphertext.
Print Assumptions the_transposed_flattening_is_a_permutation_too.
Print Assumptions both_readings_leave_four_positions_fixed.
Print Assumptions the_two_readings_agree_at_exactly_one_position.
Print Assumptions the_transposed_flattening_misses_the_published_ciphertext.
Print Assumptions the_exchanged_directions_agree_on_half_the_state.
Print Assumptions the_exchanged_directions_miss_the_published_ciphertext.
Print Assumptions ghash_probe_blocks.
Print Assumptions ghash_probe_pairs.
Print Assumptions the_probe_family_is_thirty_six_pairs.
Print Assumptions one_is_the_identity_of_the_field_multiplication.
Print Assumptions the_field_multiplication_on_blocks_is_commutative.
Print Assumptions the_models_form_and_the_standards_form_are_one_multiplication.
Print Assumptions the_unreflected_form_is_the_standards_under_a_byte_wise_reversal.
Print Assumptions the_unreflected_form_is_commutative_too.
Print Assumptions the_unreflected_form_has_the_reflected_identity.
Print Assumptions the_standards_identity_is_not_the_unreflected_forms.
Print Assumptions the_unreflected_form_is_a_different_multiplication.
Print Assumptions the_counter_field_wraps_and_leaves_the_rest_of_the_block_alone.
Print Assumptions the_hash_subkey_of_the_all_zero_key_is_the_published_one.
Print Assumptions the_first_published_case_reaches_its_tag.
Print Assumptions the_second_published_case_reaches_its_ciphertext_and_tag.
Print Assumptions the_third_published_case_reaches_its_ciphertext_and_tag.
Print Assumptions the_fourth_published_case_carries_associated_data_and_an_unaligned_plaintext.
Print Assumptions the_fifth_published_case_takes_the_other_initial_counter_arm.
Print Assumptions the_open_of_a_seal_returns_the_message_and_a_flipped_tag_bit_returns_nothing.
Print Assumptions the_unpadded_ghash_input_agrees_at_every_aligned_published_case.
Print Assumptions the_unpadded_ghash_input_misses_the_fourth_published_tag.
Print Assumptions the_counter_started_at_j0_agrees_at_the_empty_plaintext.
Print Assumptions the_counter_started_at_j0_misses_the_second_published_ciphertext.
Print Assumptions a_reused_nonce_carries_the_exclusive_or_of_the_two_messages.
Print Assumptions the_witness_at_the_platform_parameters_is_the_first_published_case.
Print Assumptions a_stated_invocation_bound_changes_nothing_the_primitive_computes.
Print Assumptions a_truncated_tag_is_a_prefix_of_the_full_one.
Print Assumptions the_three_key_lengths_carry_three_round_counts.
Print Assumptions a_bit_off_the_end_of_a_byte_is_zero.
Print Assumptions the_block_is_sixteen_bytes_of_eight_bits.
Print Assumptions the_key_schedule_has_one_round_key_per_round_and_one_more.
Print Assumptions rotating_a_word_moves_each_byte_one_place_and_adds_none.
Print Assumptions rotating_a_word_four_times_is_the_identity.
Print Assumptions the_two_substitution_guards_agree_at_every_key_length_the_standard_carries.
Print Assumptions the_two_substitution_guards_part_at_the_key_length_between_them.
Print Assumptions the_last_round_key_is_the_last_four_words.
Print Assumptions the_full_tag_is_the_longest_admissible_one.
Print Assumptions the_admissible_tag_lengths_descend_one_byte_at_a_time_from_the_full_tag.
Print Assumptions every_restricted_tag_length_is_whole_bytes_below_the_shortest_admissible_one.
Print Assumptions the_two_tag_length_lists_carry_the_counts_the_standard_states.
Print Assumptions truncating_at_every_listed_tag_length_takes_whole_bytes_of_the_published_tag.
Print Assumptions palindromic_bytes.
Print Assumptions there_are_sixteen_bytes_that_are_their_own_reversal.
Print Assumptions the_reflection_fixes_a_block_of_those_bytes_and_moves_the_others.
