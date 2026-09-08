(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   Sha256.v

   SHA-256 as FIPS 180-4 states it, and HMAC over it as FIPS 198-1 states it,
   written in Gallina and checked against the published known answers of the
   two standards, of NIST's own validation corpus, and of RFC 4231.

   What this file is, and what it is not. It is a **functional reference**: a
   transcription of FIPS 180-4 s5.1.1, s5.2.1, s5.3.3, s6.2.1 and s6.2.2 and
   of FIPS 198-1 s4 and s5, made so that the DRBG in HmacDrbg.v has a hash to
   ride and so that the acquisition route M3.4a's read reopened is closed by
   an artifact rather than by a sentence. It is not an implementation, no
   binary corresponds to it, and it discharges no acceptance clause of any
   entry. It is not a discharge of R-15-041 or R-15-055 either: those entries
   are about which SHA-2 round datapath a core carries, and this file carries
   none.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. Nothing here executes on either
   emulator. The computed checks are decided inside the kernel, the light ones
   by conversion in the silent `Example ... := eq_refl` form and the ones that
   run a compression by the bytecode machine, which contributes nothing to
   the Print Assumptions block at the end.

   The three assurance layers, and which one this is. R-05-059 wants
   functional correctness, constant-time and reduction-level security per
   primitive, and what is here is the **functional layer alone**. No
   constant-time property is claimed: R-05-062 and R-05-067 put that
   obligation on a binary as a 2-safety hyperproperty, a Gallina reference is
   not a binary, and the fact that every value-dependent operation below is
   xorb, andb, negb, a rotation by a constant or a ripple-carry addition is a
   remark about the shape and never evidence. No masking claim is made under
   R-05-004a. No reduction and no distributional claim is made either: HMAC's
   pseudorandomness and the collision resistance of the compression function
   are assumptions R-05-077a states over uniformly drawn keys, and a functional
   reference carries no distribution of any kind. So nothing here is a
   shipped primitive under R-05-059.

   No Require. Nothing beyond the Rocq prelude is reachable, so there is no
   Z, no N, no String and no List library: `map`, `nth`, `firstn`, `skipn`,
   `seq`, `rev`, `repeat`, `fold_left`, `filter` and `concat` are authored
   below in the idiom Keccak.v and AesGcm.v author theirs in. An assumption
   reachable through an import is an assumption inside the R-05-163 gate's
   reach, which is what that rule buys and what a convenience import would
   spend. The one thing this file needs that neither sibling needed is
   arbitrary-precision integer arithmetic, for the derivation of the constant
   tables, and it is authored below over `list bool` rather than imported:
   the prelude's `nat` is unary and cannot carry a 105-bit integer, and the
   binary numbers live behind a Require.

   The representation, which no register entry fixes and which is therefore a
   reading of this file:

   1. A **byte** is a `list bool` of length 8 with the **most significant bit
      at the head**, which is AesGcm.v's convention and the opposite of
      Keccak.v's, each file taking its own standard's: FIPS 180-4 s3.1 writes
      a word's bits most significant first and reads a message's bytes in
      order, so a bit string here is the standard's own, with no reversal
      anywhere.
   2. A **word** is a `list bool` of length 32 in the same order, so the head
      of a word is its bit 31 and `rotr` moves the tail to the head.
   3. **Addition modulo 2^32 is a ripple-carry adder over the reversed word
      with the final carry discarded**, and never `nat` arithmetic: a 32-bit
      value is a `nat` no kernel can build, and the discarded carry is the
      whole of the reduction. The adder is stated commutative over arbitrary
      lists below, which is the property that separates an adder from a
      ripple of the right length.
   4. A **message** is a bit string of any length; every published answer
      below is byte-aligned, so no sub-byte convention is exercised and none
      is claimed. The length field is 64 bits big-endian, which is s5.1.1.
   5. **Arbitrary-precision integers, used for the derivation alone**, are
      `list bool` with the **least** significant bit at the head, the order
      in which a ripple adder and a shift-and-add multiplier are simplest.
      Nothing in the hash reads one.

   The readings of the register this file takes:

   1. **No entry names SHA-256 or HMAC.** R-15-241d names *the verified DRBG*
      and the plan's cell names HMAC-DRBG-SHA-256 as that DRBG; the register
      itself carries the hash only in R-15-041's and R-15-055's sentences
      about which SHA-2 round datapath a core carries, and in the prose's
      sentence that SHA-256, if needed, stays table-free constant-time integer
      code. So which hash the DRBG rides is the plan's sentence and not an
      entry's, and this file is written against that sentence. Reported, not
      closed.
   2. **The oracle enters no trust base.** Every published answer below is a
      constant inside an `Example`'s own statement, never a `Definition`, and
      nothing above it depends on the answer being right: what a known-answer
      check buys is that the constant and the transcription were produced by
      different routes. Putting an answer in a `Definition` would also put it
      inside the seeded-mutation population, where a published byte moved off
      by one would score as a kill of the oracle rather than of the subject.
   3. **The two constant tables are derived and then computed equal to the
      published ones**, which is the shape M3.4a set at FIPS 202 and M3.4d at
      FIPS 197. FIPS 180-4 s4.2.2 states the sixty-four round constants as
      the first thirty-two bits of the fractional parts of the cube roots of
      the first sixty-four primes, and s5.3.3 states the eight initial hash
      words the same way over square roots and the first eight primes. This
      file derives the primes by trial division, the roots by a bit-serial
      restoring root over the integers authored below, and the fraction as
      the low thirty-two bits of the root of the prime shifted left by
      thirty-two bits per degree; then it computes that what it derived is
      what the standard publishes. The derived tables are the ones the hash
      reads, so a transcription defect is a disagreement with a published
      table and not a disagreement between two things this file wrote.
   4. **The six logical functions are the standard's own, by the standard's
      own names, and unfused**: Ch, Maj, the two upper-case sigmas and the
      two lower-case sigmas of s4.1.2, one definition each, and the round is
      composed once from them. The curated model's vector-crypto unit at
      model/model/extensions/vector_crypto/zvknhab_insts.sail transcribes the
      same functions for the `Zvknhb` instructions; no rule reads the two
      together and this file does not claim the pair, which is reported
      below as F-205b's shape one hash over.
   5. **The compression function is not a permutation and this file says
      so.** It maps a 512-bit block and a 256-bit state to a 256-bit state,
      so no inverse is stated and no bijection is claimed of it. What is
      stated on arbitrary inputs is what is true: every rotation the four
      sigmas use is undone by its complement on a word of thirty-two
      arbitrary bits, the adder is commutative on arbitrary lists, and the
      message schedule keeps a block of sixteen arbitrary words as its first
      sixteen entries.
   6. **The padding is where a hash reference goes wrong silently**, so the
      boundary is exercised where it lies: the message lengths that leave
      room for the length field in the same block (55 bytes), that do not
      (56 bytes), that fill a block short of one byte (63) and exactly (64),
      and one that spans three blocks, each at NIST's own published answer;
      and three near alternatives are built and refuted, a pad that omits its
      one bit, a length field written byte-reversed, and the two lower-case
      sigmas exchanged in the schedule. The byte-reversed length field is
      the interesting one: at the empty message its field is all zero either
      way, so the empty-message vector decides nothing about it, and the
      file computes that agreement rather than leaving it to be found.
   7. **HMAC's long-key arm is where an HMAC reference goes wrong silently**,
      because every key of the block size or shorter never reaches it. The
      published cases with keys of 70, 74 and 131 bytes exercise it, and the
      alternative that truncates such a key rather than hashing it is built
      and computed to agree with the standard on every shorter key it is
      given and to part from it on every longer one.

   What is deliberately absent, with the entry that owes each decision. A
   register gap is reported, not closed:

   a. **No entry names the hash the DRBG rides** (reading 1). Owed at
      R-15-241d or in the plan.
   b. **No entry fixes the oracle pair for an authored SHA-256**, exactly as
      none fixes it for an authored SHA-3 (F-205b) or an authored AEAD. The
      answers below are NIST's own validation corpus, the two standards'
      example documents and RFC 4231, and that is this file's choice on the
      stated ground and not the register's.
   c. **No entry fixes the representation obligations above.** Byte and word
      order, the reduction as a discarded carry, and whether a Gallina
      reference is inside any acceptance at all are readings of this file.
   d. **HMAC's truncation length is a parameter and no entry fixes one.**
      FIPS 198-1 s5 admits any leftmost `t` bytes; `hmac_sha256_truncated`
      takes `t` as an argument and the published truncated cases carry their
      own. The DRBG never truncates.
   e. **No constant-time claim, no masking claim, no reduction** (above).

   The literals taken from the standards, and there are no others. FIPS
   180-4's 8-bit byte, 32-bit word, 512-bit block, 64-bit length field,
   256-bit digest and sixty-four rounds; the ten rotation and shift amounts
   of s4.1.2, {2, 13, 22}, {6, 11, 25}, {7, 18, 3} and {17, 19, 10}; the
   schedule's four taps {2, 7, 15, 16} of s6.2.2; and FIPS 198-1's two pad
   bytes 0x36 and 0x5C. Everything else is derived: the sixteen words of a
   block and the eight words of a digest are quotients of the sizes, the
   sixty-four constants and the eight initial words are the roots of the
   primes, the block size in bytes HMAC pads a key to is the block size over
   the byte size, and the sixteen-bit field a prime is carried in is a width
   of this file's derivation and nothing the standard states.

   Non-vacuity (R-05-165, R-05-166). Every structural obligation below is
   stated of an arbitrary word, an arbitrary block or arbitrary lists, or is
   enumerated over a domain the statement names, and six constructions the
   standards' own sentences exclude are built here and refuted: a pad
   without its one bit, a pad whose length field is written byte-reversed, a
   schedule with its two lower-case sigmas exchanged, a compression with Maj
   written as Ch, an HMAC whose inner and outer pads are exchanged, and an
   HMAC that truncates a long key where the standard hashes it. Each is held
   to the single difference it exists to exhibit: the two pads keep the
   standard's length, the exchanged schedule keeps the block as its first
   sixteen words, and the truncating HMAC agrees with the standard on every
   key it never hashes. **Two of the six are invisible to a family of inputs
   and the file says which**: the byte-reversed length field agrees with the
   standard's at the empty message, and the truncating HMAC agrees at every
   key of the block size or shorter, which is five of RFC 4231's seven cases
   and two of the five validation cases quoted. Inhabitation is the published
   answers themselves, so no check below holds of everything and none holds
   of nothing.

   Where each published answer came from, and under what instrument. The
   round-constant and initial-hash tables are FIPS 180-4's own, s4.2.2 and
   s5.3.3. The digests of "abc" and of the fifty-six-byte two-block message
   and the first-round working variables are read from NIST's SHA-256
   example document `SHA256.pdf` under
   csrc.nist.gov/CSRC/media/Projects/Cryptographic-Standards-and-Guidelines/documents/examples/,
   on 2026-09-05. The five boundary-length digests are read from
   `SHA256ShortMsg.rsp` and `SHA256LongMsg.rsp` in NIST's CAVP archive
   `shabytetestvectors.zip` (header "CAVS 11.0", generated 2011-03-15), and
   the five keyed answers from `HMAC.rsp` in `hmactestvectors.zip` (header
   "CAVS 11.0", generated 2011-02-28), both under
   csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/,
   on the same date. **The instrument on NIST's files is the one NIST states
   at nist.gov/oism/copyrights**, read the same day, and it is not the flat
   grant a first reading takes it for. That page carries three paragraphs
   that could each reach these files and they do not say the same thing: its
   *Software disclaimer* states the same three conditions the ACVP
   repository's README states, notice retention, a change notice on a
   modified work and explicit acknowledgement of NIST as the source, and
   ends "The software developed by NIST employees is not subject to
   copyright protection within the United States"; its *Data disclaimer*
   states a warranty term and no condition at all; and its *Use of NIST
   information* paragraph makes what is on NIST's pages public information
   with a byline credit requested. **Which of the three reaches a `.rsp`
   file the CAVS system emitted is not settled by the page**, so what is
   done here is to meet the strictest of them: the archive, its own CAVS
   header line and NIST as the source are named above, the answers are
   quoted unmodified, and no change notice is owed because nothing was
   changed. Reading the last sentence alone and concluding that no condition
   is stated would be a grant inferred from one paragraph of an instrument
   that carries three. The seven HMAC cases of RFC 4231 s4.2 through s4.8 are read at
   rfc-editor.org/rfc/rfc4231.txt on the same date; its notice reads
   "Copyright (C) The Internet Society (2005)" and "This document is subject
   to the rights, licenses and restrictions contained in BCP 78", which is
   the instrument on a quotation of its test cases, and no residue of it
   reaches a reader of this file beyond the notice retained here. **Every
   literal was recomputed on 2026-09-05 by a second and independent
   transcription before it was written down here**, the two tables by an
   integer root in Python over the same primes and the digests and keyed
   answers by the host's `hashlib` and `hmac`, so each reached this file by
   two routes and not one. Neither instrument is pinned, neither enters any
   trust base, and nothing above the answers depends on them.
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

(* The one out-of-range answer this file relies on, named once so that it is
   a decision rather than a default repeated at twenty sites. *)
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

Fixpoint zip_with {A B C : Type} (f : A -> B -> C) (a : list A) (b : list B) : list C :=
  match a with
  | nil => nil
  | x :: xs => match b with nil => nil | y :: ys => f x y :: zip_with f xs ys end
  end.

Fixpoint last_of {A : Type} (l : list A) (d : A) : A :=
  match l with nil => d | x :: nil => x | _ :: r => last_of r d end.

(* The fuel argument is the caller's bound on how many chunks there can be,
   the recursion being on the chunk count rather than on the list, which
   `drop_of` does not decrease structurally. *)
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

(* n bits of v, least significant first and then reversed, so no power of two
   is ever built: a 64-bit length field is a fold of halvings and never 2^64. *)
Fixpoint bits_le_of (n v : nat) : list bool :=
  match n with
  | 0 => nil
  | S k => Nat.eqb (Nat.modulo v 2) 1 :: bits_le_of k (Nat.div v 2)
  end.

Definition bits_be_of (n v : nat) : list bool := rev_of (bits_le_of n v).

Fixpoint set_bit (i : nat) (b : bool) (w : list bool) : list bool :=
  match w with
  | nil => nil
  | x :: r => match i with 0 => b :: r | S k => x :: set_bit k b r end
  end.

(* -------------------------------------------------------------------------
   The sizes, which are FIPS 180-4's own (s1, s2.2.1, s5.1.1, s6.2.2) and
   nothing else. The counts a table has are quotients of them.
   ------------------------------------------------------------------------- *)

Definition byte_bits : nat := 8.
Definition word_bits : nat := 32.
Definition block_bits : nat := 512.
Definition length_bits : nat := 64.
Definition digest_bits : nat := 256.
Definition rounds : nat := 64.

Definition words_per_block : nat := Nat.div block_bits word_bits.
Definition hash_words : nat := Nat.div digest_bits word_bits.

Example a_block_is_sixteen_words : words_per_block = 16 := eq_refl.
Example a_digest_is_eight_words : hash_words = 8 := eq_refl.

(* -------------------------------------------------------------------------
   Bytes and words, most significant bit first (s3.1).
   ------------------------------------------------------------------------- *)

Definition byte : Type := list bool.
Definition word : Type := list bool.

Definition zero_word : word := repeat_of word_bits false.

Definition bits_of_byte (n : nat) : byte :=
  map_over (fun j => Nat.eqb (Nat.modulo (Nat.div n (Nat.pow 2 (byte_bits - 1 - j))) 2) 1)
           (upto byte_bits).

Definition byte_value (b : byte) : nat :=
  fold_over (fun (acc : nat) (x : bool) => 2 * acc + (if x then 1 else 0)) 0 b.

Definition bytes_from (l : list nat) : list bool := concat_of (map_over bits_of_byte l).

Definition bytes_of (s : list bool) : list nat :=
  map_over byte_value (chunks_of (length_of s) byte_bits s).

Example a_byte_round_trips_over_all_two_hundred_and_fifty_six :
  all_of (fun n => Nat.eqb (byte_value (bits_of_byte n)) n) (upto (Nat.pow 2 byte_bits)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_head_of_a_byte_is_its_most_significant_bit :
  bits_of_byte 0x80 = true :: repeat_of (byte_bits - 1) false.
Proof. vm_compute. reflexivity. Qed.

Fixpoint wxor (a b : list bool) : list bool :=
  match a with
  | nil => nil
  | x :: xs => match b with nil => nil | y :: ys => xorb x y :: wxor xs ys end
  end.

Fixpoint wand (a b : list bool) : list bool :=
  match a with
  | nil => nil
  | x :: xs => match b with nil => nil | y :: ys => andb x y :: wand xs ys end
  end.

Definition wnot (w : list bool) : list bool := map_over negb w.

Definition wxor3 (a b c : word) : word := wxor a (wxor b c).

(* A right rotation by n: the n bits at the tail move to the head, which is
   s3.2's ROTR^n(x) = (x >> n) | (x << (w - n)) read on a word whose head is
   its most significant bit. *)
Definition rotr (n : nat) (w : word) : word :=
  let k := word_bits - Nat.modulo n word_bits in
  drop_of k w ++ take_of k w.

(* A right shift by n: n zeros at the head and the tail dropped (s3.2). *)
Definition shr (n : nat) (w : word) : word :=
  repeat_of n false ++ take_of (word_bits - n) w.

(* -------------------------------------------------------------------------
   Addition modulo 2^32 as a ripple-carry adder (s3.2's + operation). The
   adder works least significant bit first over lists of any length and keeps
   its final carry, which is what the derivation below needs of it; the word
   form reverses, adds, keeps the low thirty-two bits and reverses back, and
   the dropped carry is the reduction.
   ------------------------------------------------------------------------- *)

Definition majb (x y z : bool) : bool := orb (andb x y) (orb (andb x z) (andb y z)).

Fixpoint carry_into (c : bool) (b : list bool) : list bool :=
  match b with nil => c :: nil | y :: ys => xorb y c :: carry_into (andb y c) ys end.

Fixpoint add_le (a b : list bool) (c : bool) : list bool :=
  match a with
  | nil => carry_into c b
  | x :: xs => match b with
               | nil => carry_into c (x :: xs)
               | y :: ys => xorb (xorb x y) c :: add_le xs ys (majb x y c)
               end
  end.

Definition wadd (a b : word) : word :=
  rev_of (take_of word_bits (add_le (rev_of a) (rev_of b) false)).

Definition wsum (l : list word) : word := fold_over wadd zero_word l.

(* -------------------------------------------------------------------------
   Arbitrary-precision integers over `list bool`, least significant bit
   first, for the derivation of the two constant tables and for nothing else.
   ------------------------------------------------------------------------- *)

Definition shift_le (k : nat) (a : list bool) : list bool := repeat_of k false ++ a.

Definition mul_le (a b : list bool) : list bool :=
  fold_over (fun acc i => if bit_at b i then add_le acc (shift_le i a) false else acc)
            nil (upto (length_of b)).

Definition pad_le (n : nat) (a : list bool) : list bool :=
  a ++ repeat_of (n - length_of a) false.

(* a <= b on two most-significant-first strings of one length. *)
Fixpoint leb_be (a b : list bool) : bool :=
  match a with
  | nil => true
  | x :: xs => match b with
               | nil => true
               | y :: ys => if eqb_bool x y then leb_be xs ys else negb x
               end
  end.

Definition leb_le (a b : list bool) : bool :=
  let n := Nat.max (length_of a) (length_of b) in
  leb_be (rev_of (pad_le n a)) (rev_of (pad_le n b)).

Definition with_bit (i : nat) (a : list bool) : list bool :=
  set_bit i true (pad_le (S i) a).

(* The restoring root: from the highest candidate bit down, keep a bit
   wherever the candidate's power still fits under x. `power` is the square
   or the cube, and `bits` bounds the root's width. *)
Definition root_by_bits (power : list bool -> list bool) (bits : nat) (x : list bool)
  : list bool :=
  fold_over (fun r i => let t := with_bit i r in if leb_le (power t) x then t else r)
            nil (rev_of (upto bits)).

Definition square_le (r : list bool) : list bool := mul_le r r.
Definition cube_le (r : list bool) : list bool := mul_le r (mul_le r r).

(* The first thirty-two bits of the fractional part of the degree-th root of
   p, which is the low thirty-two bits of the integer root of p shifted left
   by thirty-two bits per degree (s4.2.2, s5.3.3). Returned as a word, most
   significant bit first. `prime_bits` is the field a prime is carried in and
   is a width of this derivation rather than a figure of the standard. *)
Definition prime_bits : nat := 16.

Definition root_fraction (power : list bool -> list bool) (degree p : nat) : word :=
  let x := shift_le (word_bits * degree) (bits_le_of prime_bits p) in
  let r := root_by_bits power (prime_bits + word_bits) x in
  rev_of (take_of word_bits r).

Definition cube_root_fraction : nat -> word := root_fraction cube_le 3.
Definition square_root_fraction : nat -> word := root_fraction square_le 2.

(* -------------------------------------------------------------------------
   The primes, by trial division. The fuel bounds the candidates walked and
   is k^2 + 2, on the classical bound that the k-th prime is below k^2.
   ------------------------------------------------------------------------- *)

Definition divides (d n : nat) : bool := Nat.eqb (Nat.modulo n d) 0.

Definition is_prime (n : nat) : bool :=
  andb (Nat.leb 2 n) (all_of (fun d => negb (divides d n)) (up_from 2 (n - 2))).

Fixpoint primes_from (fuel n k : nat) : list nat :=
  match fuel with
  | 0 => nil
  | S f => match k with
           | 0 => nil
           | S k' => if is_prime n then n :: primes_from f (S n) k'
                     else primes_from f (S n) k
           end
  end.

Definition first_primes (k : nat) : list nat := primes_from (k * k + 2) 2 k.

Example the_first_eight_primes :
  first_primes hash_words = 2 :: 3 :: 5 :: 7 :: 11 :: 13 :: 17 :: 19 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example there_are_sixty_four_primes_and_the_last_is_311 :
  andb (Nat.eqb (length_of (first_primes rounds)) rounds)
       (Nat.eqb (last_of (first_primes rounds) 0) 311) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The two tables, derived (s4.2.2, s5.3.3). Each is evaluated once at its
   definition so that the hash reads a value rather than re-deriving sixty-four
   cube roots at every known answer; what it evaluates is the derivation and
   never a written-down table, and the Examples beneath hold the value to
   the derivation and the derivation to the standard's own list.
   ------------------------------------------------------------------------- *)

Definition derived_round_constants : list word :=
  map_over cube_root_fraction (first_primes rounds).

Definition round_constants : list word := Eval vm_compute in derived_round_constants.

Definition derived_initial_hash : list word :=
  map_over square_root_fraction (first_primes hash_words).

Definition initial_hash : list word := Eval vm_compute in derived_initial_hash.

Example the_round_constants_are_the_derivation :
  round_constants = derived_round_constants.
Proof. vm_compute. reflexivity. Qed.

Example the_initial_hash_is_the_derivation :
  initial_hash = derived_initial_hash.
Proof. vm_compute. reflexivity. Qed.

Example the_round_constants_are_the_published_table :
  bytes_of (concat_of round_constants) =
  0x42 :: 0x8A :: 0x2F :: 0x98 :: 0x71 :: 0x37 :: 0x44 :: 0x91 ::
  0xB5 :: 0xC0 :: 0xFB :: 0xCF :: 0xE9 :: 0xB5 :: 0xDB :: 0xA5 ::
  0x39 :: 0x56 :: 0xC2 :: 0x5B :: 0x59 :: 0xF1 :: 0x11 :: 0xF1 ::
  0x92 :: 0x3F :: 0x82 :: 0xA4 :: 0xAB :: 0x1C :: 0x5E :: 0xD5 ::
  0xD8 :: 0x07 :: 0xAA :: 0x98 :: 0x12 :: 0x83 :: 0x5B :: 0x01 ::
  0x24 :: 0x31 :: 0x85 :: 0xBE :: 0x55 :: 0x0C :: 0x7D :: 0xC3 ::
  0x72 :: 0xBE :: 0x5D :: 0x74 :: 0x80 :: 0xDE :: 0xB1 :: 0xFE ::
  0x9B :: 0xDC :: 0x06 :: 0xA7 :: 0xC1 :: 0x9B :: 0xF1 :: 0x74 ::
  0xE4 :: 0x9B :: 0x69 :: 0xC1 :: 0xEF :: 0xBE :: 0x47 :: 0x86 ::
  0x0F :: 0xC1 :: 0x9D :: 0xC6 :: 0x24 :: 0x0C :: 0xA1 :: 0xCC ::
  0x2D :: 0xE9 :: 0x2C :: 0x6F :: 0x4A :: 0x74 :: 0x84 :: 0xAA ::
  0x5C :: 0xB0 :: 0xA9 :: 0xDC :: 0x76 :: 0xF9 :: 0x88 :: 0xDA ::
  0x98 :: 0x3E :: 0x51 :: 0x52 :: 0xA8 :: 0x31 :: 0xC6 :: 0x6D ::
  0xB0 :: 0x03 :: 0x27 :: 0xC8 :: 0xBF :: 0x59 :: 0x7F :: 0xC7 ::
  0xC6 :: 0xE0 :: 0x0B :: 0xF3 :: 0xD5 :: 0xA7 :: 0x91 :: 0x47 ::
  0x06 :: 0xCA :: 0x63 :: 0x51 :: 0x14 :: 0x29 :: 0x29 :: 0x67 ::
  0x27 :: 0xB7 :: 0x0A :: 0x85 :: 0x2E :: 0x1B :: 0x21 :: 0x38 ::
  0x4D :: 0x2C :: 0x6D :: 0xFC :: 0x53 :: 0x38 :: 0x0D :: 0x13 ::
  0x65 :: 0x0A :: 0x73 :: 0x54 :: 0x76 :: 0x6A :: 0x0A :: 0xBB ::
  0x81 :: 0xC2 :: 0xC9 :: 0x2E :: 0x92 :: 0x72 :: 0x2C :: 0x85 ::
  0xA2 :: 0xBF :: 0xE8 :: 0xA1 :: 0xA8 :: 0x1A :: 0x66 :: 0x4B ::
  0xC2 :: 0x4B :: 0x8B :: 0x70 :: 0xC7 :: 0x6C :: 0x51 :: 0xA3 ::
  0xD1 :: 0x92 :: 0xE8 :: 0x19 :: 0xD6 :: 0x99 :: 0x06 :: 0x24 ::
  0xF4 :: 0x0E :: 0x35 :: 0x85 :: 0x10 :: 0x6A :: 0xA0 :: 0x70 ::
  0x19 :: 0xA4 :: 0xC1 :: 0x16 :: 0x1E :: 0x37 :: 0x6C :: 0x08 ::
  0x27 :: 0x48 :: 0x77 :: 0x4C :: 0x34 :: 0xB0 :: 0xBC :: 0xB5 ::
  0x39 :: 0x1C :: 0x0C :: 0xB3 :: 0x4E :: 0xD8 :: 0xAA :: 0x4A ::
  0x5B :: 0x9C :: 0xCA :: 0x4F :: 0x68 :: 0x2E :: 0x6F :: 0xF3 ::
  0x74 :: 0x8F :: 0x82 :: 0xEE :: 0x78 :: 0xA5 :: 0x63 :: 0x6F ::
  0x84 :: 0xC8 :: 0x78 :: 0x14 :: 0x8C :: 0xC7 :: 0x02 :: 0x08 ::
  0x90 :: 0xBE :: 0xFF :: 0xFA :: 0xA4 :: 0x50 :: 0x6C :: 0xEB ::
  0xBE :: 0xF9 :: 0xA3 :: 0xF7 :: 0xC6 :: 0x71 :: 0x78 :: 0xF2 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_initial_hash_is_the_published_table :
  bytes_of (concat_of initial_hash) =
  0x6A :: 0x09 :: 0xE6 :: 0x67 :: 0xBB :: 0x67 :: 0xAE :: 0x85 ::
  0x3C :: 0x6E :: 0xF3 :: 0x72 :: 0xA5 :: 0x4F :: 0xF5 :: 0x3A ::
  0x51 :: 0x0E :: 0x52 :: 0x7F :: 0x9B :: 0x05 :: 0x68 :: 0x8C ::
  0x1F :: 0x83 :: 0xD9 :: 0xAB :: 0x5B :: 0xE0 :: 0xCD :: 0x19 :: nil.
Proof. vm_compute. reflexivity. Qed.

(* The table is not its own reverse and carries no repeated entry, which is
   the defect a table read in the wrong direction or off by a row would
   share with a correct one at a glance. *)
Example the_round_constants_are_sixty_four_distinct_words :
  andb (Nat.eqb (length_of round_constants) rounds)
       (all_of (fun i => all_of (fun j => orb (Nat.eqb i j)
                                              (negb (bits_eqb (nth_of i round_constants zero_word)
                                                              (nth_of j round_constants zero_word))))
                                 (upto rounds))
               (upto rounds)) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The six logical functions, s4.1.2, equations 4.2 through 4.7, one
   definition each and by the standard's names.
   ------------------------------------------------------------------------- *)

Definition ch (x y z : word) : word := wxor (wand x y) (wand (wnot x) z).

Definition maj (x y z : word) : word := wxor3 (wand x y) (wand x z) (wand y z).

Definition big_sigma0 (x : word) : word := wxor3 (rotr 2 x) (rotr 13 x) (rotr 22 x).
Definition big_sigma1 (x : word) : word := wxor3 (rotr 6 x) (rotr 11 x) (rotr 25 x).
Definition small_sigma0 (x : word) : word := wxor3 (rotr 7 x) (rotr 18 x) (shr 3 x).
Definition small_sigma1 (x : word) : word := wxor3 (rotr 17 x) (rotr 19 x) (shr 10 x).

Definition rotation_amounts : list nat :=
  2 :: 13 :: 22 :: 6 :: 11 :: 25 :: 7 :: 18 :: 17 :: 19 :: nil.

(* The list above is the standard's own table of the ten rotation amounts
   and the four functions above write theirs inline, which makes the list a
   second statement of a fact the functions already own. It is held to them
   here rather than left beside them: a table nothing computes from is a
   table nothing can be wrong against. *)
Example the_listed_amounts_are_the_ones_the_four_sigmas_use :
  let a := fun i => nth_of i rotation_amounts 0 in
  let x := bytes_from (0x6A :: 0x09 :: 0xE6 :: 0x67 :: nil) in
  andb (andb (bits_eqb (big_sigma0 x) (wxor3 (rotr (a 0) x) (rotr (a 1) x) (rotr (a 2) x)))
             (bits_eqb (big_sigma1 x) (wxor3 (rotr (a 3) x) (rotr (a 4) x) (rotr (a 5) x))))
       (andb (bits_eqb (small_sigma0 x) (wxor3 (rotr (a 6) x) (rotr (a 7) x) (shr 3 x)))
             (bits_eqb (small_sigma1 x) (wxor3 (rotr (a 8) x) (rotr (a 9) x) (shr 10 x))))
  = true.
Proof. vm_compute. reflexivity. Qed.

Example the_ten_amounts_are_ten_and_none_of_them_is_a_whole_word :
  andb (Nat.eqb (length_of rotation_amounts) 10)
       (all_of (fun r => Nat.ltb r word_bits) rotation_amounts) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The message schedule, s6.2.2 step 1: the block's sixteen words and then
   forty-eight computed from the taps at t - 2, t - 7, t - 15 and t - 16.
   Parameterized over the two lower-case sigmas so that their exchange has
   something to be an alternative to.
   ------------------------------------------------------------------------- *)

Definition word_at (w : list word) (t : nat) : word := nth_of t w zero_word.

Definition block_at (bs : list (list word)) (i : nat) : list word := nth_of i bs nil.

Definition schedule_over (s0 s1 : word -> word) (block : list word) : list word :=
  fold_over (fun w t =>
               w ++ (wsum (s1 (word_at w (t - 2)) :: word_at w (t - 7)
                           :: s0 (word_at w (t - 15)) :: word_at w (t - 16) :: nil)
                     :: nil))
            block (up_from words_per_block (rounds - words_per_block)).

Definition schedule : list word -> list word := schedule_over small_sigma0 small_sigma1.

(* The transcription defect two functions with one name and two subscripts
   invite: the lower-case sigmas exchanged. It keeps the block as its first
   sixteen words and differs in every computed one. *)
Definition schedule_with_the_sigmas_exchanged : list word -> list word :=
  schedule_over small_sigma1 small_sigma0.

(* -------------------------------------------------------------------------
   The eight working variables and one round, s6.2.2 steps 2 and 3, with the
   round parameterized over its majority function for the same reason the
   schedule is parameterized over its sigmas.
   ------------------------------------------------------------------------- *)

Record Working : Type := {
  va : word; vb : word; vc : word; vd : word;
  ve : word; vf : word; vg : word; vh : word
}.

Definition working_of (hs : list word) : Working :=
  {| va := word_at hs 0; vb := word_at hs 1; vc := word_at hs 2; vd := word_at hs 3;
     ve := word_at hs 4; vf := word_at hs 5; vg := word_at hs 6; vh := word_at hs 7 |}.

Definition list_of (v : Working) : list word :=
  va v :: vb v :: vc v :: vd v :: ve v :: vf v :: vg v :: vh v :: nil.

Definition round_over (majority : word -> word -> word -> word) (k w : word) (v : Working)
  : Working :=
  let t1 := wsum (vh v :: big_sigma1 (ve v) :: ch (ve v) (vf v) (vg v) :: k :: w :: nil) in
  let t2 := wadd (big_sigma0 (va v)) (majority (va v) (vb v) (vc v)) in
  {| va := wadd t1 t2; vb := va v; vc := vb v; vd := vc v;
     ve := wadd (vd v) t1; vf := ve v; vg := vf v; vh := vg v |}.

Definition round_step : word -> word -> Working -> Working := round_over maj.

(* s6.2.2 steps 2 through 4: sixty-four rounds from the incoming hash and the
   working variables folded back into it. *)
Definition compress_over (majority : word -> word -> word -> word) (ws hs : list word)
  : list word :=
  let v := fold_over (fun v t => round_over majority (word_at round_constants t) (word_at ws t) v)
                     (working_of hs) (upto rounds) in
  zip_with wadd hs (list_of v).

Definition compress : list word -> list word -> list word := compress_over maj.

(* Maj written as Ch, which is the defect two three-argument functions over
   the same three words invite. *)
Definition compress_with_maj_written_as_ch : list word -> list word -> list word :=
  compress_over ch.

(* -------------------------------------------------------------------------
   Padding, s5.1.1, and parsing, s5.2.1. The one bit, the fewest zeros that
   leave sixty-four bits for the length, and the length big-endian.
   ------------------------------------------------------------------------- *)

Definition zeros_after (l : nat) : nat :=
  Nat.modulo (block_bits - Nat.modulo (l + 1 + length_bits) block_bits) block_bits.

Definition big_endian_length (l : nat) : list bool := bits_be_of length_bits l.

Definition pad_over (length_field : nat -> list bool) (m : list bool) : list bool :=
  m ++ (true :: repeat_of (zeros_after (length_of m)) false) ++ length_field (length_of m).

Definition pad : list bool -> list bool := pad_over big_endian_length.

(* The length field with its eight bytes reversed, which is the defect a
   little-endian machine invites and which the empty message cannot see. *)
Definition byte_reversed_length (l : nat) : list bool :=
  concat_of (rev_of (chunks_of (Nat.div length_bits byte_bits) byte_bits (big_endian_length l))).

Definition pad_with_a_byte_reversed_length : list bool -> list bool :=
  pad_over byte_reversed_length.

(* A pad of the standard's length whose one bit is a zero. *)
Definition pad_without_its_one (m : list bool) : list bool :=
  m ++ repeat_of (S (zeros_after (length_of m))) false ++ big_endian_length (length_of m).

Definition blocks_of (padded : list bool) : list (list word) :=
  map_over (chunks_of words_per_block word_bits)
           (chunks_of (S (Nat.div (length_of padded) block_bits)) block_bits padded).

(* -------------------------------------------------------------------------
   SHA-256, s6.2, composed once from the pad, the schedule and the
   compression, and the near alternatives composed from the same pieces with
   one exchanged.
   ------------------------------------------------------------------------- *)

Definition sha256_over (padding : list bool -> list bool) (sched : list word -> list word)
                       (compression : list word -> list word -> list word) (m : list bool)
  : list bool :=
  concat_of (fold_over (fun hs blk => compression (sched blk) hs)
                       initial_hash (blocks_of (padding m))).

Definition sha256 : list bool -> list bool := sha256_over pad schedule compress.

Definition sha256_with_the_pad_missing_its_one : list bool -> list bool :=
  sha256_over pad_without_its_one schedule compress.

Definition sha256_with_a_byte_reversed_length : list bool -> list bool :=
  sha256_over pad_with_a_byte_reversed_length schedule compress.

Definition sha256_with_the_sigmas_exchanged : list bool -> list bool :=
  sha256_over pad schedule_with_the_sigmas_exchanged compress.

Definition sha256_with_maj_written_as_ch : list bool -> list bool :=
  sha256_over pad schedule compress_with_maj_written_as_ch.

(* -------------------------------------------------------------------------
   HMAC, FIPS 198-1 s4 and s5, over the block size B its Table 1 gives
   SHA-256, which is the block size over the byte size. A key longer than a
   block is hashed to L bytes first (s4 step 2) and every key is then padded
   to B with zeros (step 3); ipad and opad are the two bytes of s4 repeated B
   times. Parameterized over the long-key treatment and over the two pad
   bytes so that each alternative below is the standard's with one thing
   exchanged.
   ------------------------------------------------------------------------- *)

Definition hmac_block_bytes : nat := Nat.div block_bits byte_bits.
Definition ipad_byte : nat := 0x36.
Definition opad_byte : nat := 0x5C.

Definition pad_block (bs : list bool) : list bool :=
  bs ++ repeat_of (block_bits - length_of bs) false.

Definition hmac_key_over (treatment : list bool -> list bool) (key : list bool) : list bool :=
  pad_block (if Nat.ltb block_bits (length_of key) then treatment key else key).

Definition hmac_over (treatment : list bool -> list bool) (inner outer : nat)
                     (key text : list bool) : list bool :=
  let k0 := hmac_key_over treatment key in
  sha256 (wxor k0 (bytes_from (repeat_of hmac_block_bytes outer))
          ++ sha256 (wxor k0 (bytes_from (repeat_of hmac_block_bytes inner)) ++ text)).

Definition hmac_sha256 : list bool -> list bool -> list bool :=
  hmac_over sha256 ipad_byte opad_byte.

Definition hmac_sha256_truncated (bytes : nat) (key text : list bool) : list bool :=
  take_of (bytes * byte_bits) (hmac_sha256 key text).

(* The two pads exchanged, which is the defect two constants with one role
   each invite; it is an HMAC in every other respect. *)
Definition hmac_with_the_pads_exchanged : list bool -> list bool -> list bool :=
  hmac_over sha256 opad_byte ipad_byte.

(* A long key truncated to the block rather than hashed, which agrees with
   the standard at every key of the block size or shorter, so that only a
   longer key decides against it. *)
Definition hmac_with_the_long_key_truncated : list bool -> list bool -> list bool :=
  hmac_over (take_of block_bits) ipad_byte opad_byte.

(* -------------------------------------------------------------------------
   What is stated on arbitrary inputs.
   ------------------------------------------------------------------------- *)

Lemma xorb_comm_local : forall x y : bool, xorb x y = xorb y x.
Proof. intros x y. destruct x; destruct y; reflexivity. Qed.

Lemma majb_comm_local : forall x y c : bool, majb x y c = majb y x c.
Proof. intros x y c. destruct x; destruct y; destruct c; reflexivity. Qed.

(* The adder is commutative over arbitrary lists of arbitrary lengths, which
   is the property that separates an adder from a ripple of the right length:
   a defect in the carry or the sum bit that treats its two operands
   differently fails this, where every published digest below is a value. *)
Theorem the_adder_is_commutative :
  forall (a b : list bool) (c : bool), add_le a b c = add_le b a c.
Proof.
  induction a as [| x xs IH]; intros b c; destruct b as [| y ys]; simpl.
  - reflexivity.
  - reflexivity.
  - reflexivity.
  - rewrite (xorb_comm_local x y). rewrite (majb_comm_local x y c). rewrite IH. reflexivity.
Qed.

Theorem word_addition_is_commutative :
  forall a b : word, wadd a b = wadd b a.
Proof.
  intros a b. unfold wadd. rewrite (the_adder_is_commutative (rev_of a) (rev_of b) false).
  reflexivity.
Qed.

(* Every rotation the four sigmas use is undone by its complement on a word
   of thirty-two arbitrary bits. That is the whole of what is invertible
   here: the shifts drop bits, the compression maps 768 bits to 256, and no
   inverse of either is stated. *)
Theorem the_rotations_are_invertible_on_an_arbitrary_word :
  forall b0 b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 b11 b12 b13 b14 b15 b16 b17 b18 b19 b20 b21 b22 b23 b24 b25 b26 b27 b28 b29 b30 b31 : bool,
    let w :=
      b0 :: b1 :: b2 :: b3 :: b4 :: b5 :: b6 :: b7 ::
      b8 :: b9 :: b10 :: b11 :: b12 :: b13 :: b14 :: b15 ::
      b16 :: b17 :: b18 :: b19 :: b20 :: b21 :: b22 :: b23 ::
      b24 :: b25 :: b26 :: b27 :: b28 :: b29 :: b30 :: b31 :: nil in
    map_over (fun r => rotr (word_bits - r) (rotr r w)) rotation_amounts
    = repeat_of (length_of rotation_amounts) w.
Proof. intros. vm_compute. reflexivity. Qed.

(* The schedule keeps a block of sixteen arbitrary words as its first sixteen
   entries, standard's sigmas or exchanged: the exchange is a defect of the
   computed words alone. *)
Theorem the_schedule_keeps_the_block_as_its_first_sixteen_words :
  forall w0 w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11 w12 w13 w14 w15 : word,
    let blk := w0 :: w1 :: w2 :: w3 :: w4 :: w5 :: w6 :: w7 ::
               w8 :: w9 :: w10 :: w11 :: w12 :: w13 :: w14 :: w15 :: nil in
    take_of words_per_block (schedule blk) = blk
    /\ take_of words_per_block (schedule_with_the_sigmas_exchanged blk) = blk.
Proof. intros. split; vm_compute; reflexivity. Qed.

(* -------------------------------------------------------------------------
   The padding boundary, enumerated over every bit length up to two blocks
   and a byte: the padded string is a positive multiple of the block, the
   message is its prefix, and the length field is its suffix.
   ------------------------------------------------------------------------- *)

Definition probe_lengths : list nat := upto (2 * block_bits + byte_bits).

(* The probe set has to reach past two whole blocks, because a padding that
   is right on every message of one or two blocks and wrong on the first
   that needs a third is the defect the boundary lengths exist to catch. *)
Example the_probes_reach_past_two_whole_blocks :
  andb (Nat.leb (S (2 * block_bits)) (length_of probe_lengths))
       (Nat.eqb (nth_of (2 * block_bits) probe_lengths 0) (2 * block_bits)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_pad_is_a_positive_multiple_of_the_block_at_every_probed_length :
  all_of (fun l => let p := length_of (pad (repeat_of l true)) in
                   andb (Nat.eqb (Nat.modulo p block_bits) 0) (Nat.ltb l p))
         probe_lengths = true.
Proof. vm_compute. reflexivity. Qed.

Example the_message_is_a_prefix_of_its_pad_and_the_length_is_its_suffix :
  all_of (fun l => let m := repeat_of l true in
                   let p := pad m in
                   andb (bits_eqb (take_of l p) m)
                        (bits_eqb (drop_of (length_of p - length_bits) p) (big_endian_length l)))
         probe_lengths = true.
Proof. vm_compute. reflexivity. Qed.

Example the_one_bit_follows_the_message :
  all_of (fun l => bit_at (pad (repeat_of l false)) l) probe_lengths = true.
Proof. vm_compute. reflexivity. Qed.

(* The two defective pads keep the standard's length, so what refuses each
   is the one bit or the byte order and not a shape. *)
(*| discharges: R-05-165, R-05-166 |*)
Example the_defective_pads_keep_the_standards_length :
  all_of (fun l => let m := repeat_of l true in
                   andb (Nat.eqb (length_of (pad_without_its_one m)) (length_of (pad m)))
                        (Nat.eqb (length_of (pad_with_a_byte_reversed_length m))
                                 (length_of (pad m))))
         probe_lengths = true.
Proof. vm_compute. reflexivity. Qed.

(*| discharges: R-05-165, R-05-166 |*)
Example the_pad_without_its_one_differs_from_the_pad_in_that_bit_alone :
  all_of (fun l => let m := repeat_of l true in
                   let p := pad m in
                   let q := pad_without_its_one m in
                   andb (bits_eqb (take_of l q) (take_of l p))
                        (andb (negb (eqb_bool (bit_at q l) (bit_at p l)))
                              (bits_eqb (drop_of (S l) q) (drop_of (S l) p))))
         probe_lengths = true.
Proof. vm_compute. reflexivity. Qed.

(*| discharges: R-05-165, R-05-166 |*)
Example the_byte_reversed_length_agrees_with_the_standard_only_where_the_field_is_zero :
  andb (bits_eqb (pad_with_a_byte_reversed_length nil) (pad nil))
       (all_of (fun l => negb (bits_eqb (pad_with_a_byte_reversed_length (repeat_of l true))
                                        (pad (repeat_of l true))))
               (up_from 1 (2 * block_bits))) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The published answers. FIPS 180-4's own example first, read from NIST's
   SHA-256 example document: the message "abc", its first and last schedule
   words, the working variables after the first round, and its digest.
   ------------------------------------------------------------------------- *)

Definition abc : list bool := bytes_from (0x61 :: 0x62 :: 0x63 :: nil).

Example the_first_schedule_word_of_abc_is_the_message_and_its_one_bit :
  bytes_of (word_at (schedule (block_at (blocks_of (pad abc)) 0)) 0) =
  0x61 :: 0x62 :: 0x63 :: 0x80 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_sixteenth_schedule_word_of_abc_is_its_bit_length :
  bytes_of (word_at (schedule (block_at (blocks_of (pad abc)) 0)) 15) =
  0x00 :: 0x00 :: 0x00 :: 0x18 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_first_round_of_abc_reaches_the_published_working_variables :
  let blk := block_at (blocks_of (pad abc)) 0 in
  bytes_of (concat_of (list_of (round_step (word_at round_constants 0)
                                           (word_at (schedule blk) 0)
                                           (working_of initial_hash)))) =
  0x5D :: 0x6A :: 0xEB :: 0xCD :: 0x6A :: 0x09 :: 0xE6 :: 0x67 ::
  0xBB :: 0x67 :: 0xAE :: 0x85 :: 0x3C :: 0x6E :: 0xF3 :: 0x72 ::
  0xFA :: 0x2A :: 0x46 :: 0x22 :: 0x51 :: 0x0E :: 0x52 :: 0x7F ::
  0x9B :: 0x05 :: 0x68 :: 0x8C :: 0x1F :: 0x83 :: 0xD9 :: 0xAB :: nil.
Proof. vm_compute. reflexivity. Qed.

Example sha256_of_abc :
  bytes_of (sha256 abc) =
  0xBA :: 0x78 :: 0x16 :: 0xBF :: 0x8F :: 0x01 :: 0xCF :: 0xEA ::
  0x41 :: 0x41 :: 0x40 :: 0xDE :: 0x5D :: 0xAE :: 0x22 :: 0x23 ::
  0xB0 :: 0x03 :: 0x61 :: 0xA3 :: 0x96 :: 0x17 :: 0x7A :: 0x9C ::
  0xB4 :: 0x10 :: 0xFF :: 0x61 :: 0xF2 :: 0x00 :: 0x15 :: 0xAD :: nil.
Proof. vm_compute. reflexivity. Qed.

(* Fifty-six bytes: the length that no longer leaves room for the length
   field in its own block, so the pad makes two blocks of one. *)
Definition two_block_message : list bool := bytes_from (
  0x61 :: 0x62 :: 0x63 :: 0x64 :: 0x62 :: 0x63 :: 0x64 :: 0x65 ::
  0x63 :: 0x64 :: 0x65 :: 0x66 :: 0x64 :: 0x65 :: 0x66 :: 0x67 ::
  0x65 :: 0x66 :: 0x67 :: 0x68 :: 0x66 :: 0x67 :: 0x68 :: 0x69 ::
  0x67 :: 0x68 :: 0x69 :: 0x6A :: 0x68 :: 0x69 :: 0x6A :: 0x6B ::
  0x69 :: 0x6A :: 0x6B :: 0x6C :: 0x6A :: 0x6B :: 0x6C :: 0x6D ::
  0x6B :: 0x6C :: 0x6D :: 0x6E :: 0x6C :: 0x6D :: 0x6E :: 0x6F ::
  0x6D :: 0x6E :: 0x6F :: 0x70 :: 0x6E :: 0x6F :: 0x70 :: 0x71 :: nil).

Example the_two_block_message_pads_to_two_blocks :
  length_of (blocks_of (pad two_block_message)) = 2.
Proof. vm_compute. reflexivity. Qed.

Example sha256_of_the_two_block_message :
  bytes_of (sha256 two_block_message) =
  0x24 :: 0x8D :: 0x6A :: 0x61 :: 0xD2 :: 0x06 :: 0x38 :: 0xB8 ::
  0xE5 :: 0xC0 :: 0x26 :: 0x93 :: 0x0C :: 0x3E :: 0x60 :: 0x39 ::
  0xA3 :: 0x3C :: 0xE4 :: 0x59 :: 0x64 :: 0xFF :: 0x21 :: 0x67 ::
  0xF6 :: 0xEC :: 0xED :: 0xD4 :: 0x19 :: 0xDB :: 0x06 :: 0xC1 :: nil.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   NIST's validation corpus at the padding boundary: the empty message and
   the messages of 55, 56, 63 and 64 bytes from SHA256ShortMsg.rsp, and the
   163-byte message from SHA256LongMsg.rsp, which is three blocks.
   ------------------------------------------------------------------------- *)

Example sha256_of_the_empty_message :
  bytes_of (sha256 nil) =
  0xE3 :: 0xB0 :: 0xC4 :: 0x42 :: 0x98 :: 0xFC :: 0x1C :: 0x14 ::
  0x9A :: 0xFB :: 0xF4 :: 0xC8 :: 0x99 :: 0x6F :: 0xB9 :: 0x24 ::
  0x27 :: 0xAE :: 0x41 :: 0xE4 :: 0x64 :: 0x9B :: 0x93 :: 0x4C ::
  0xA4 :: 0x95 :: 0x99 :: 0x1B :: 0x78 :: 0x52 :: 0xB8 :: 0x55 :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition message_of_55_bytes : list bool := bytes_from (
  0x3E :: 0xBF :: 0xB0 :: 0x6D :: 0xB8 :: 0xC3 :: 0x8D :: 0x5B ::
  0xA0 :: 0x37 :: 0xF1 :: 0x36 :: 0x3E :: 0x11 :: 0x85 :: 0x50 ::
  0xAA :: 0xD9 :: 0x46 :: 0x06 :: 0xE2 :: 0x68 :: 0x35 :: 0xA0 ::
  0x1A :: 0xF0 :: 0x50 :: 0x78 :: 0x53 :: 0x3C :: 0xC2 :: 0x5F ::
  0x2F :: 0x39 :: 0x57 :: 0x3C :: 0x04 :: 0xB6 :: 0x32 :: 0xF6 ::
  0x2F :: 0x68 :: 0xC2 :: 0x94 :: 0xAB :: 0x31 :: 0xF2 :: 0xA3 ::
  0xE2 :: 0xA1 :: 0xA0 :: 0xD8 :: 0xC2 :: 0xBE :: 0x51 :: nil).

Example sha256_of_55_bytes_fits_its_length_in_one_block :
  andb (Nat.eqb (length_of (blocks_of (pad message_of_55_bytes))) 1)
       (bits_eqb (sha256 message_of_55_bytes) (bytes_from (
  0x65 :: 0x95 :: 0xA2 :: 0xEF :: 0x53 :: 0x7A :: 0x69 :: 0xBA ::
  0x85 :: 0x83 :: 0xDF :: 0xBF :: 0x7F :: 0x5B :: 0xEC :: 0x0A ::
  0xB1 :: 0xF9 :: 0x3C :: 0xE4 :: 0xC8 :: 0xEE :: 0x19 :: 0x16 ::
  0xEF :: 0xF4 :: 0x4A :: 0x93 :: 0xAF :: 0x57 :: 0x49 :: 0xC4 :: nil))) = true.
Proof. vm_compute. reflexivity. Qed.

Definition message_of_56_bytes : list bool := bytes_from (
  0x2D :: 0x52 :: 0x44 :: 0x7D :: 0x12 :: 0x44 :: 0xD2 :: 0xEB ::
  0xC2 :: 0x86 :: 0x50 :: 0xE7 :: 0xB0 :: 0x56 :: 0x54 :: 0xBA ::
  0xD3 :: 0x5B :: 0x3A :: 0x68 :: 0xEE :: 0xDC :: 0x7F :: 0x85 ::
  0x15 :: 0x30 :: 0x6B :: 0x49 :: 0x6D :: 0x75 :: 0xF3 :: 0xE7 ::
  0x33 :: 0x85 :: 0xDD :: 0x1B :: 0x00 :: 0x26 :: 0x25 :: 0x02 ::
  0x4B :: 0x81 :: 0xA0 :: 0x2F :: 0x2F :: 0xD6 :: 0xDF :: 0xFB ::
  0x6E :: 0x6D :: 0x56 :: 0x1C :: 0xB7 :: 0xD0 :: 0xBD :: 0x7A :: nil).

Example sha256_of_56_bytes_needs_a_second_block :
  andb (Nat.eqb (length_of (blocks_of (pad message_of_56_bytes))) 2)
       (bits_eqb (sha256 message_of_56_bytes) (bytes_from (
  0xCF :: 0xB8 :: 0x8D :: 0x6F :: 0xAF :: 0x2D :: 0xE3 :: 0xA6 ::
  0x9D :: 0x36 :: 0x19 :: 0x5A :: 0xCE :: 0xC2 :: 0xE2 :: 0x55 ::
  0xE2 :: 0xAF :: 0x2B :: 0x7D :: 0x93 :: 0x39 :: 0x97 :: 0xF3 ::
  0x48 :: 0xE0 :: 0x9F :: 0x6C :: 0xE5 :: 0x75 :: 0x83 :: 0x60 :: nil))) = true.
Proof. vm_compute. reflexivity. Qed.

Definition message_of_63_bytes : list bool := bytes_from (
  0xE2 :: 0xF7 :: 0x6E :: 0x97 :: 0x60 :: 0x6A :: 0x87 :: 0x2E ::
  0x31 :: 0x74 :: 0x39 :: 0xF1 :: 0xA0 :: 0x3F :: 0xCD :: 0x92 ::
  0xE6 :: 0x32 :: 0xE5 :: 0xBD :: 0x4E :: 0x7C :: 0xBC :: 0x4E ::
  0x97 :: 0xF1 :: 0xAF :: 0xC1 :: 0x9A :: 0x16 :: 0xFD :: 0xE9 ::
  0x2D :: 0x77 :: 0xCB :: 0xE5 :: 0x46 :: 0x41 :: 0x6B :: 0x51 ::
  0x64 :: 0x0C :: 0xDD :: 0xB9 :: 0x2A :: 0xF9 :: 0x96 :: 0x53 ::
  0x4D :: 0xFD :: 0x81 :: 0xED :: 0xB1 :: 0x7C :: 0x44 :: 0x24 ::
  0xCF :: 0x1A :: 0xC4 :: 0xD7 :: 0x5A :: 0xCE :: 0xEB :: nil).

Example sha256_of_63_bytes :
  bytes_of (sha256 message_of_63_bytes) =
  0x18 :: 0x04 :: 0x1B :: 0xD4 :: 0x66 :: 0x50 :: 0x83 :: 0x00 ::
  0x1F :: 0xBA :: 0x8C :: 0x54 :: 0x11 :: 0xD2 :: 0xD7 :: 0x48 ::
  0xE8 :: 0xAB :: 0xBF :: 0xDC :: 0xDF :: 0xD9 :: 0x21 :: 0x8C ::
  0xB0 :: 0x2B :: 0x68 :: 0xA7 :: 0x8E :: 0x7D :: 0x4C :: 0x23 :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition message_of_64_bytes : list bool := bytes_from (
  0x5A :: 0x86 :: 0xB7 :: 0x37 :: 0xEA :: 0xEA :: 0x8E :: 0xE9 ::
  0x76 :: 0xA0 :: 0xA2 :: 0x4D :: 0xA6 :: 0x3E :: 0x7E :: 0xD7 ::
  0xEE :: 0xFA :: 0xD1 :: 0x8A :: 0x10 :: 0x1C :: 0x12 :: 0x11 ::
  0xE2 :: 0xB3 :: 0x65 :: 0x0C :: 0x51 :: 0x87 :: 0xC2 :: 0xA8 ::
  0xA6 :: 0x50 :: 0x54 :: 0x72 :: 0x08 :: 0x25 :: 0x1F :: 0x6D ::
  0x42 :: 0x37 :: 0xE6 :: 0x61 :: 0xC7 :: 0xBF :: 0x4C :: 0x77 ::
  0xF3 :: 0x35 :: 0x39 :: 0x03 :: 0x94 :: 0xC3 :: 0x7F :: 0xA1 ::
  0xA9 :: 0xF9 :: 0xBE :: 0x83 :: 0x6A :: 0xC2 :: 0x85 :: 0x09 :: nil).

Example sha256_of_64_bytes_fills_a_block_and_pads_into_a_second :
  andb (Nat.eqb (length_of (blocks_of (pad message_of_64_bytes))) 2)
       (bits_eqb (sha256 message_of_64_bytes) (bytes_from (
  0x42 :: 0xE6 :: 0x1E :: 0x17 :: 0x4F :: 0xBB :: 0x38 :: 0x97 ::
  0xD6 :: 0xDD :: 0x6C :: 0xEF :: 0x3D :: 0xD2 :: 0x80 :: 0x2F ::
  0xE6 :: 0x7B :: 0x33 :: 0x19 :: 0x53 :: 0xB0 :: 0x61 :: 0x14 ::
  0xA6 :: 0x5C :: 0x77 :: 0x28 :: 0x59 :: 0xDF :: 0xC1 :: 0xAA :: nil))) = true.
Proof. vm_compute. reflexivity. Qed.

Definition message_of_163_bytes : list bool := bytes_from (
  0x45 :: 0x11 :: 0x01 :: 0x25 :: 0x0E :: 0xC6 :: 0xF2 :: 0x66 ::
  0x52 :: 0x24 :: 0x9D :: 0x59 :: 0xDC :: 0x97 :: 0x4B :: 0x73 ::
  0x61 :: 0xD5 :: 0x71 :: 0xA8 :: 0x10 :: 0x1C :: 0xDF :: 0xD3 ::
  0x6A :: 0xBA :: 0x3B :: 0x58 :: 0x54 :: 0xD3 :: 0xAE :: 0x08 ::
  0x6B :: 0x5F :: 0xDD :: 0x45 :: 0x97 :: 0x72 :: 0x1B :: 0x66 ::
  0xE3 :: 0xC0 :: 0xDC :: 0x5D :: 0x8C :: 0x60 :: 0x6D :: 0x96 ::
  0x57 :: 0xD0 :: 0xE3 :: 0x23 :: 0x28 :: 0x3A :: 0x52 :: 0x17 ::
  0xD1 :: 0xF5 :: 0x3F :: 0x2F :: 0x28 :: 0x4F :: 0x57 :: 0xB8 ::
  0x5C :: 0x8A :: 0x61 :: 0xAC :: 0x89 :: 0x24 :: 0x71 :: 0x1F ::
  0x89 :: 0x5C :: 0x5E :: 0xD9 :: 0x0E :: 0xF1 :: 0x77 :: 0x45 ::
  0xED :: 0x2D :: 0x72 :: 0x8A :: 0xBD :: 0x22 :: 0xA5 :: 0xF7 ::
  0xA1 :: 0x34 :: 0x79 :: 0xA4 :: 0x62 :: 0xD7 :: 0x1B :: 0x56 ::
  0xC1 :: 0x9A :: 0x74 :: 0xA4 :: 0x0B :: 0x65 :: 0x5C :: 0x58 ::
  0xED :: 0xFE :: 0x0A :: 0x18 :: 0x8A :: 0xD2 :: 0xCF :: 0x46 ::
  0xCB :: 0xF3 :: 0x05 :: 0x24 :: 0xF6 :: 0x5D :: 0x42 :: 0x3C ::
  0x83 :: 0x7D :: 0xD1 :: 0xFF :: 0x2B :: 0xF4 :: 0x62 :: 0xAC ::
  0x41 :: 0x98 :: 0x00 :: 0x73 :: 0x45 :: 0xBB :: 0x44 :: 0xDB ::
  0xB7 :: 0xB1 :: 0xC8 :: 0x61 :: 0x29 :: 0x8C :: 0xDF :: 0x61 ::
  0x98 :: 0x2A :: 0x83 :: 0x3A :: 0xFC :: 0x72 :: 0x8F :: 0xAE ::
  0x1E :: 0xDA :: 0x2F :: 0x87 :: 0xAA :: 0x2C :: 0x94 :: 0x80 ::
  0x85 :: 0x8B :: 0xEC :: nil).

Example sha256_of_163_bytes_spans_three_blocks :
  andb (Nat.eqb (length_of (blocks_of (pad message_of_163_bytes))) 3)
       (bits_eqb (sha256 message_of_163_bytes) (bytes_from (
  0x3C :: 0x59 :: 0x3A :: 0xA5 :: 0x39 :: 0xFD :: 0xCD :: 0xAE ::
  0x51 :: 0x6C :: 0xDF :: 0x2F :: 0x15 :: 0x00 :: 0x0F :: 0x66 ::
  0x34 :: 0x18 :: 0x5C :: 0x88 :: 0xF5 :: 0x05 :: 0xB3 :: 0x97 ::
  0x75 :: 0xFB :: 0x9A :: 0xB1 :: 0x37 :: 0xA1 :: 0x0A :: 0xA2 :: nil))) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The near alternatives refuted at the standard's own example. Each
   construction above is held to its single difference; here each is shown to
   miss the published digest, and the one that is invisible at the empty
   message is shown to agree there.
   ------------------------------------------------------------------------- *)

Example the_pad_without_its_one_misses_the_published_digest :
  bits_eqb (sha256_with_the_pad_missing_its_one abc) (sha256 abc) = false.
Proof. vm_compute. reflexivity. Qed.

Example the_byte_reversed_length_misses_the_published_digest :
  bits_eqb (sha256_with_a_byte_reversed_length abc) (sha256 abc) = false.
Proof. vm_compute. reflexivity. Qed.

Example the_byte_reversed_length_agrees_at_the_empty_message :
  bits_eqb (sha256_with_a_byte_reversed_length nil) (sha256 nil) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_exchanged_sigmas_miss_the_published_digest :
  bits_eqb (sha256_with_the_sigmas_exchanged abc) (sha256 abc) = false.
Proof. vm_compute. reflexivity. Qed.

Example maj_written_as_ch_misses_the_published_digest :
  bits_eqb (sha256_with_maj_written_as_ch abc) (sha256 abc) = false.
Proof. vm_compute. reflexivity. Qed.

(* Ch and Maj agree wherever their last two words coincide, each returning
   that word, so a check at such a state would not separate them; the
   published example's first round does, and the file computes both rather
   than saying so. *)
Example ch_and_maj_agree_where_the_last_two_words_coincide :
  let x := word_at initial_hash 0 in
  let y := word_at initial_hash 1 in
  andb (bits_eqb (ch x y y) (maj x y y)) (bits_eqb (ch x y y) y) = true.
Proof. vm_compute. reflexivity. Qed.

Example ch_and_maj_part_at_the_initial_hash :
  bits_eqb (ch (word_at initial_hash 0) (word_at initial_hash 1) (word_at initial_hash 2))
           (maj (word_at initial_hash 0) (word_at initial_hash 1) (word_at initial_hash 2)) = false.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   HMAC-SHA-256 at RFC 4231's seven cases: two short keys, a key of twenty
   0xAA bytes, a twenty-five-byte key, a truncated output, and two keys of
   131 bytes, which is more than two blocks and is the arm every shorter key
   never reaches.
   ------------------------------------------------------------------------- *)

Definition rfc4231_key_1 : list bool := bytes_from (repeat_of 20 0x0B).
Definition rfc4231_data_1 : list bool :=
  bytes_from (0x48 :: 0x69 :: 0x20 :: 0x54 :: 0x68 :: 0x65 :: 0x72 :: 0x65 :: nil).

Example hmac_of_rfc4231_case_1 :
  bytes_of (hmac_sha256 rfc4231_key_1 rfc4231_data_1) =
  0xB0 :: 0x34 :: 0x4C :: 0x61 :: 0xD8 :: 0xDB :: 0x38 :: 0x53 ::
  0x5C :: 0xA8 :: 0xAF :: 0xCE :: 0xAF :: 0x0B :: 0xF1 :: 0x2B ::
  0x88 :: 0x1D :: 0xC2 :: 0x00 :: 0xC9 :: 0x83 :: 0x3D :: 0xA7 ::
  0x26 :: 0xE9 :: 0x37 :: 0x6C :: 0x2E :: 0x32 :: 0xCF :: 0xF7 :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition rfc4231_key_2 : list bool := bytes_from (0x4A :: 0x65 :: 0x66 :: 0x65 :: nil).
Definition rfc4231_data_2 : list bool := bytes_from (
  0x77 :: 0x68 :: 0x61 :: 0x74 :: 0x20 :: 0x64 :: 0x6F :: 0x20 ::
  0x79 :: 0x61 :: 0x20 :: 0x77 :: 0x61 :: 0x6E :: 0x74 :: 0x20 ::
  0x66 :: 0x6F :: 0x72 :: 0x20 :: 0x6E :: 0x6F :: 0x74 :: 0x68 ::
  0x69 :: 0x6E :: 0x67 :: 0x3F :: nil).

Example hmac_of_rfc4231_case_2 :
  bytes_of (hmac_sha256 rfc4231_key_2 rfc4231_data_2) =
  0x5B :: 0xDC :: 0xC1 :: 0x46 :: 0xBF :: 0x60 :: 0x75 :: 0x4E ::
  0x6A :: 0x04 :: 0x24 :: 0x26 :: 0x08 :: 0x95 :: 0x75 :: 0xC7 ::
  0x5A :: 0x00 :: 0x3F :: 0x08 :: 0x9D :: 0x27 :: 0x39 :: 0x83 ::
  0x9D :: 0xEC :: 0x58 :: 0xB9 :: 0x64 :: 0xEC :: 0x38 :: 0x43 :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition rfc4231_key_3 : list bool := bytes_from (repeat_of 20 0xAA).
Definition rfc4231_data_3 : list bool := bytes_from (repeat_of 50 0xDD).

Example hmac_of_rfc4231_case_3 :
  bytes_of (hmac_sha256 rfc4231_key_3 rfc4231_data_3) =
  0x77 :: 0x3E :: 0xA9 :: 0x1E :: 0x36 :: 0x80 :: 0x0E :: 0x46 ::
  0x85 :: 0x4D :: 0xB8 :: 0xEB :: 0xD0 :: 0x91 :: 0x81 :: 0xA7 ::
  0x29 :: 0x59 :: 0x09 :: 0x8B :: 0x3E :: 0xF8 :: 0xC1 :: 0x22 ::
  0xD9 :: 0x63 :: 0x55 :: 0x14 :: 0xCE :: 0xD5 :: 0x65 :: 0xFE :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition rfc4231_key_4 : list bool := bytes_from (up_from 1 25).
Definition rfc4231_data_4 : list bool := bytes_from (repeat_of 50 0xCD).

Example hmac_of_rfc4231_case_4 :
  bytes_of (hmac_sha256 rfc4231_key_4 rfc4231_data_4) =
  0x82 :: 0x55 :: 0x8A :: 0x38 :: 0x9A :: 0x44 :: 0x3C :: 0x0E ::
  0xA4 :: 0xCC :: 0x81 :: 0x98 :: 0x99 :: 0xF2 :: 0x08 :: 0x3A ::
  0x85 :: 0xF0 :: 0xFA :: 0xA3 :: 0xE5 :: 0x78 :: 0xF8 :: 0x07 ::
  0x7A :: 0x2E :: 0x3F :: 0xF4 :: 0x67 :: 0x29 :: 0x66 :: 0x5B :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition rfc4231_key_5 : list bool := bytes_from (repeat_of 20 0x0C).
Definition rfc4231_data_5 : list bool := bytes_from (
  0x54 :: 0x65 :: 0x73 :: 0x74 :: 0x20 :: 0x57 :: 0x69 :: 0x74 ::
  0x68 :: 0x20 :: 0x54 :: 0x72 :: 0x75 :: 0x6E :: 0x63 :: 0x61 ::
  0x74 :: 0x69 :: 0x6F :: 0x6E :: nil).

Example hmac_of_rfc4231_case_5_truncated_to_sixteen_bytes :
  bytes_of (hmac_sha256_truncated 16 rfc4231_key_5 rfc4231_data_5) =
  0xA3 :: 0xB6 :: 0x16 :: 0x74 :: 0x73 :: 0x10 :: 0x0E :: 0xE0 ::
  0x6E :: 0x0C :: 0x79 :: 0x6C :: 0x29 :: 0x55 :: 0x55 :: 0x2B :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition rfc4231_key_long : list bool := bytes_from (repeat_of 131 0xAA).
Definition rfc4231_data_6 : list bool := bytes_from (
  0x54 :: 0x65 :: 0x73 :: 0x74 :: 0x20 :: 0x55 :: 0x73 :: 0x69 ::
  0x6E :: 0x67 :: 0x20 :: 0x4C :: 0x61 :: 0x72 :: 0x67 :: 0x65 ::
  0x72 :: 0x20 :: 0x54 :: 0x68 :: 0x61 :: 0x6E :: 0x20 :: 0x42 ::
  0x6C :: 0x6F :: 0x63 :: 0x6B :: 0x2D :: 0x53 :: 0x69 :: 0x7A ::
  0x65 :: 0x20 :: 0x4B :: 0x65 :: 0x79 :: 0x20 :: 0x2D :: 0x20 ::
  0x48 :: 0x61 :: 0x73 :: 0x68 :: 0x20 :: 0x4B :: 0x65 :: 0x79 ::
  0x20 :: 0x46 :: 0x69 :: 0x72 :: 0x73 :: 0x74 :: nil).

Example hmac_of_rfc4231_case_6_hashes_its_long_key :
  bytes_of (hmac_sha256 rfc4231_key_long rfc4231_data_6) =
  0x60 :: 0xE4 :: 0x31 :: 0x59 :: 0x1E :: 0xE0 :: 0xB6 :: 0x7F ::
  0x0D :: 0x8A :: 0x26 :: 0xAA :: 0xCB :: 0xF5 :: 0xB7 :: 0x7F ::
  0x8E :: 0x0B :: 0xC6 :: 0x21 :: 0x37 :: 0x28 :: 0xC5 :: 0x14 ::
  0x05 :: 0x46 :: 0x04 :: 0x0F :: 0x0E :: 0xE3 :: 0x7F :: 0x54 :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition rfc4231_data_7 : list bool := bytes_from (
  0x54 :: 0x68 :: 0x69 :: 0x73 :: 0x20 :: 0x69 :: 0x73 :: 0x20 ::
  0x61 :: 0x20 :: 0x74 :: 0x65 :: 0x73 :: 0x74 :: 0x20 :: 0x75 ::
  0x73 :: 0x69 :: 0x6E :: 0x67 :: 0x20 :: 0x61 :: 0x20 :: 0x6C ::
  0x61 :: 0x72 :: 0x67 :: 0x65 :: 0x72 :: 0x20 :: 0x74 :: 0x68 ::
  0x61 :: 0x6E :: 0x20 :: 0x62 :: 0x6C :: 0x6F :: 0x63 :: 0x6B ::
  0x2D :: 0x73 :: 0x69 :: 0x7A :: 0x65 :: 0x20 :: 0x6B :: 0x65 ::
  0x79 :: 0x20 :: 0x61 :: 0x6E :: 0x64 :: 0x20 :: 0x61 :: 0x20 ::
  0x6C :: 0x61 :: 0x72 :: 0x67 :: 0x65 :: 0x72 :: 0x20 :: 0x74 ::
  0x68 :: 0x61 :: 0x6E :: 0x20 :: 0x62 :: 0x6C :: 0x6F :: 0x63 ::
  0x6B :: 0x2D :: 0x73 :: 0x69 :: 0x7A :: 0x65 :: 0x20 :: 0x64 ::
  0x61 :: 0x74 :: 0x61 :: 0x2E :: 0x20 :: 0x54 :: 0x68 :: 0x65 ::
  0x20 :: 0x6B :: 0x65 :: 0x79 :: 0x20 :: 0x6E :: 0x65 :: 0x65 ::
  0x64 :: 0x73 :: 0x20 :: 0x74 :: 0x6F :: 0x20 :: 0x62 :: 0x65 ::
  0x20 :: 0x68 :: 0x61 :: 0x73 :: 0x68 :: 0x65 :: 0x64 :: 0x20 ::
  0x62 :: 0x65 :: 0x66 :: 0x6F :: 0x72 :: 0x65 :: 0x20 :: 0x62 ::
  0x65 :: 0x69 :: 0x6E :: 0x67 :: 0x20 :: 0x75 :: 0x73 :: 0x65 ::
  0x64 :: 0x20 :: 0x62 :: 0x79 :: 0x20 :: 0x74 :: 0x68 :: 0x65 ::
  0x20 :: 0x48 :: 0x4D :: 0x41 :: 0x43 :: 0x20 :: 0x61 :: 0x6C ::
  0x67 :: 0x6F :: 0x72 :: 0x69 :: 0x74 :: 0x68 :: 0x6D :: 0x2E :: nil).

Example hmac_of_rfc4231_case_7_hashes_its_long_key_over_a_long_message :
  bytes_of (hmac_sha256 rfc4231_key_long rfc4231_data_7) =
  0x9B :: 0x09 :: 0xFF :: 0xA7 :: 0x1B :: 0x94 :: 0x2F :: 0xCB ::
  0x27 :: 0x63 :: 0x5F :: 0xBC :: 0xD5 :: 0xB0 :: 0xE9 :: 0x44 ::
  0xBF :: 0xDC :: 0x63 :: 0x64 :: 0x4F :: 0x07 :: 0x13 :: 0x93 ::
  0x8A :: 0x7F :: 0x51 :: 0x53 :: 0x5C :: 0x3A :: 0x35 :: 0xE2 :: nil.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   NIST's HMAC validation corpus at L = 32: a key of exactly one block, and
   keys of 45, 70 and 74 bytes, the last two longer than a block, with the
   truncated forms the file carries.
   ------------------------------------------------------------------------- *)

Definition cavp_key_64 : list bool := bytes_from (
  0x99 :: 0x28 :: 0x68 :: 0x50 :: 0x4D :: 0x25 :: 0x64 :: 0xC4 ::
  0xFB :: 0x47 :: 0xBC :: 0xBD :: 0x4A :: 0xE4 :: 0x82 :: 0xD8 ::
  0xFB :: 0x0E :: 0x8E :: 0x56 :: 0xD7 :: 0xB8 :: 0x18 :: 0x64 ::
  0xE6 :: 0x19 :: 0x86 :: 0xA0 :: 0xE2 :: 0x56 :: 0x82 :: 0xDA ::
  0xEB :: 0x5B :: 0x50 :: 0x17 :: 0x7C :: 0x09 :: 0x5E :: 0xDC ::
  0x9E :: 0x97 :: 0x1D :: 0xA9 :: 0x5C :: 0x32 :: 0x10 :: 0xC3 ::
  0x76 :: 0xE7 :: 0x23 :: 0x36 :: 0x5A :: 0xC3 :: 0x3D :: 0x1B ::
  0x4F :: 0x39 :: 0x18 :: 0x17 :: 0xF4 :: 0xC3 :: 0x51 :: 0x24 :: nil).

Definition cavp_msg_64 : list bool := bytes_from (
  0xED :: 0x4F :: 0x26 :: 0x9A :: 0x88 :: 0x51 :: 0xEB :: 0x31 ::
  0x54 :: 0x77 :: 0x15 :: 0x16 :: 0xB2 :: 0x72 :: 0x28 :: 0x15 ::
  0x52 :: 0x00 :: 0x77 :: 0x80 :: 0x49 :: 0xB2 :: 0xDC :: 0x19 ::
  0x63 :: 0xF3 :: 0xAC :: 0x32 :: 0xBA :: 0x46 :: 0xEA :: 0x13 ::
  0x87 :: 0xCF :: 0xBB :: 0x9C :: 0x39 :: 0x15 :: 0x1A :: 0x2C ::
  0xC4 :: 0x06 :: 0xCD :: 0xC1 :: 0x3C :: 0x3C :: 0x98 :: 0x60 ::
  0xA2 :: 0x7E :: 0xB0 :: 0xB7 :: 0xFE :: 0x8A :: 0x72 :: 0x01 ::
  0xAD :: 0x11 :: 0x55 :: 0x2A :: 0xFD :: 0x04 :: 0x1E :: 0x33 ::
  0xF7 :: 0x0E :: 0x53 :: 0xD9 :: 0x7C :: 0x62 :: 0xF1 :: 0x71 ::
  0x94 :: 0xB6 :: 0x61 :: 0x17 :: 0x02 :: 0x8F :: 0xA9 :: 0x07 ::
  0x1C :: 0xC0 :: 0xE0 :: 0x4B :: 0xD9 :: 0x2D :: 0xE4 :: 0x97 ::
  0x2C :: 0xD5 :: 0x4F :: 0x71 :: 0x90 :: 0x10 :: 0xA6 :: 0x94 ::
  0xE4 :: 0x14 :: 0xD4 :: 0x97 :: 0x7A :: 0xBE :: 0xD7 :: 0xCA ::
  0x6B :: 0x90 :: 0xBA :: 0x61 :: 0x2D :: 0xF6 :: 0xC3 :: 0xD4 ::
  0x67 :: 0xCD :: 0xED :: 0x85 :: 0x03 :: 0x25 :: 0x98 :: 0xA4 ::
  0x85 :: 0x46 :: 0x80 :: 0x4F :: 0x9C :: 0xF2 :: 0xEC :: 0xFE :: nil).

Example hmac_of_the_validation_case_with_a_one_block_key :
  bytes_of (hmac_sha256 cavp_key_64 cavp_msg_64) =
  0x2F :: 0x83 :: 0x21 :: 0xF4 :: 0x16 :: 0xB9 :: 0xBB :: 0x24 ::
  0x9F :: 0x11 :: 0x3B :: 0x13 :: 0xFC :: 0x12 :: 0xD7 :: 0x0E ::
  0x16 :: 0x68 :: 0xDC :: 0x33 :: 0x28 :: 0x39 :: 0xC1 :: 0x0D ::
  0xAA :: 0x57 :: 0x17 :: 0x89 :: 0x6C :: 0xB7 :: 0x0D :: 0xDF :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition cavp_key_45 : list bool := bytes_from (
  0xB7 :: 0x63 :: 0x26 :: 0x3D :: 0xC4 :: 0xFC :: 0x62 :: 0xB2 ::
  0x27 :: 0xCD :: 0x3F :: 0x6B :: 0x4E :: 0x9E :: 0x35 :: 0x8C ::
  0x21 :: 0xCA :: 0x03 :: 0x6C :: 0xE3 :: 0x96 :: 0xAB :: 0x92 ::
  0x59 :: 0xC1 :: 0xBE :: 0xDD :: 0x2F :: 0x5C :: 0xD9 :: 0x02 ::
  0x97 :: 0xDC :: 0x70 :: 0x3C :: 0x33 :: 0x6E :: 0xCA :: 0x3E ::
  0x35 :: 0x8A :: 0x4D :: 0x6D :: 0xC5 :: nil).

Definition cavp_msg_45 : list bool := bytes_from (
  0x53 :: 0xCB :: 0x09 :: 0xD0 :: 0xA7 :: 0x88 :: 0xE4 :: 0x46 ::
  0x6D :: 0x01 :: 0x58 :: 0x8D :: 0xF6 :: 0x94 :: 0x5D :: 0x87 ::
  0x28 :: 0xD9 :: 0x36 :: 0x3F :: 0x76 :: 0xCD :: 0x01 :: 0x2A ::
  0x10 :: 0x30 :: 0x8D :: 0xAD :: 0x56 :: 0x2B :: 0x6B :: 0xE0 ::
  0x93 :: 0x36 :: 0x48 :: 0x92 :: 0xE8 :: 0x39 :: 0x7A :: 0x8D ::
  0x86 :: 0xF1 :: 0xD8 :: 0x1A :: 0x20 :: 0x96 :: 0xCF :: 0xC8 ::
  0xA1 :: 0xBB :: 0xB2 :: 0x6A :: 0x1A :: 0x75 :: 0x52 :: 0x5F ::
  0xFE :: 0xBF :: 0xCF :: 0x16 :: 0x91 :: 0x1D :: 0xAD :: 0xD0 ::
  0x9E :: 0x80 :: 0x2A :: 0xA8 :: 0x68 :: 0x6A :: 0xCF :: 0xD1 ::
  0xE4 :: 0x52 :: 0x46 :: 0x20 :: 0x25 :: 0x4A :: 0x6B :: 0xCA ::
  0x18 :: 0xDF :: 0xA5 :: 0x6E :: 0x71 :: 0x41 :: 0x77 :: 0x56 ::
  0xE5 :: 0xA4 :: 0x52 :: 0xFA :: 0x9A :: 0xE5 :: 0xAE :: 0xC5 ::
  0xDC :: 0x71 :: 0x59 :: 0x1C :: 0x11 :: 0x63 :: 0x0E :: 0x9D ::
  0xEF :: 0xEC :: 0x49 :: 0xA4 :: 0xEC :: 0xF8 :: 0x5A :: 0x14 ::
  0xF6 :: 0x0E :: 0xB8 :: 0x54 :: 0x65 :: 0x78 :: 0x99 :: 0x97 ::
  0x2E :: 0xA5 :: 0xBF :: 0x61 :: 0x59 :: 0xCB :: 0x95 :: 0x47 :: nil).

Example hmac_of_the_validation_case_with_a_forty_five_byte_key :
  bytes_of (hmac_sha256 cavp_key_45 cavp_msg_45) =
  0x73 :: 0x73 :: 0x01 :: 0xDE :: 0xA9 :: 0x3D :: 0xB6 :: 0xBC ::
  0xBA :: 0xDD :: 0x7B :: 0xF7 :: 0x96 :: 0x69 :: 0x39 :: 0x61 ::
  0x31 :: 0x7C :: 0xA6 :: 0x80 :: 0xB3 :: 0x80 :: 0x41 :: 0x6F ::
  0x12 :: 0xF4 :: 0x66 :: 0xF0 :: 0x65 :: 0x26 :: 0xB3 :: 0x6B :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition cavp_key_70 : list bool := bytes_from (
  0xC0 :: 0x9E :: 0x29 :: 0x07 :: 0x1C :: 0x40 :: 0x5D :: 0x5E ::
  0x82 :: 0x0D :: 0x34 :: 0x5A :: 0x46 :: 0xDB :: 0xBF :: 0x1E ::
  0x0F :: 0x82 :: 0x02 :: 0xE9 :: 0x2D :: 0xE3 :: 0xED :: 0x3E ::
  0x2D :: 0x29 :: 0x8E :: 0x43 :: 0xAA :: 0x4F :: 0x84 :: 0x68 ::
  0x66 :: 0xE3 :: 0xB7 :: 0x48 :: 0x99 :: 0x09 :: 0x46 :: 0xD4 ::
  0x88 :: 0xC2 :: 0xC1 :: 0xAE :: 0x5A :: 0x6E :: 0x99 :: 0xD3 ::
  0x27 :: 0x90 :: 0xD4 :: 0x7D :: 0x53 :: 0xD2 :: 0x05 :: 0x48 ::
  0x1A :: 0x49 :: 0x7C :: 0x93 :: 0x6B :: 0xF9 :: 0xBA :: 0x29 ::
  0xFA :: 0x9C :: 0x28 :: 0x21 :: 0x91 :: 0x9F :: nil).

Definition cavp_msg_70 : list bool := bytes_from (
  0xEA :: 0x72 :: 0x40 :: 0x52 :: 0x99 :: 0x80 :: 0x07 :: 0x6D ::
  0x3B :: 0x02 :: 0x8A :: 0x08 :: 0x3E :: 0xBC :: 0x4E :: 0x24 ::
  0xEF :: 0xDA :: 0xA0 :: 0x6C :: 0x9C :: 0x84 :: 0xD7 :: 0x6B ::
  0xF5 :: 0xB2 :: 0xD9 :: 0xFD :: 0xB8 :: 0x42 :: 0xE1 :: 0x03 ::
  0x8E :: 0x48 :: 0x7F :: 0x5B :: 0x30 :: 0xA5 :: 0xE0 :: 0x10 ::
  0xCD :: 0xDB :: 0x4F :: 0xCD :: 0xB0 :: 0x1F :: 0xFC :: 0x98 ::
  0x1E :: 0xB0 :: 0xFC :: 0xBC :: 0x7D :: 0x68 :: 0x92 :: 0x07 ::
  0xBC :: 0x90 :: 0xAD :: 0x36 :: 0xEE :: 0xF9 :: 0xB1 :: 0xAE ::
  0x38 :: 0x48 :: 0x7A :: 0x6D :: 0xEE :: 0x92 :: 0x9F :: 0x3F ::
  0xF9 :: 0x29 :: 0xF3 :: 0x35 :: 0x7C :: 0xB5 :: 0x52 :: 0x53 ::
  0xB7 :: 0x86 :: 0x9A :: 0x89 :: 0x2B :: 0x28 :: 0xF7 :: 0xE5 ::
  0xFE :: 0x38 :: 0x64 :: 0x06 :: 0xA2 :: 0x77 :: 0x6E :: 0xD4 ::
  0xB2 :: 0x1D :: 0x3B :: 0x6E :: 0x1C :: 0x70 :: 0xCC :: 0x64 ::
  0x85 :: 0x94 :: 0x7F :: 0x27 :: 0xE9 :: 0xA5 :: 0xD8 :: 0xBD ::
  0x82 :: 0x03 :: 0x80 :: 0xB9 :: 0xEC :: 0xED :: 0x8E :: 0x6B ::
  0x86 :: 0x52 :: 0x06 :: 0x54 :: 0x1B :: 0xE3 :: 0x9F :: 0xDC :: nil).

Example hmac_of_the_validation_case_with_a_seventy_byte_key :
  bytes_of (hmac_sha256 cavp_key_70 cavp_msg_70) =
  0x49 :: 0xAE :: 0x1C :: 0x4A :: 0x7A :: 0x57 :: 0x0F :: 0xDE ::
  0x47 :: 0xF7 :: 0x51 :: 0x7A :: 0xB1 :: 0x88 :: 0x98 :: 0xB1 ::
  0xB9 :: 0x91 :: 0xD0 :: 0x3C :: 0xFC :: 0xF8 :: 0xC4 :: 0x5B ::
  0xB3 :: 0x61 :: 0x5B :: 0x5F :: 0x75 :: 0x5D :: 0xA6 :: 0x82 :: nil.
Proof. vm_compute. reflexivity. Qed.

Definition cavp_key_74 : list bool := bytes_from (
  0x81 :: 0x5C :: 0x2A :: 0x91 :: 0x1A :: 0xAF :: 0x0F :: 0x84 ::
  0x98 :: 0x70 :: 0x61 :: 0x10 :: 0xA9 :: 0x5E :: 0x6F :: 0x9C ::
  0x26 :: 0xC3 :: 0xEF :: 0x52 :: 0xA3 :: 0xB1 :: 0x37 :: 0x81 ::
  0x44 :: 0x8C :: 0xB0 :: 0x3F :: 0xD2 :: 0xC8 :: 0x87 :: 0x52 ::
  0x0D :: 0xF4 :: 0xA5 :: 0x51 :: 0x44 :: 0xF8 :: 0xE2 :: 0x06 ::
  0x24 :: 0x9B :: 0x75 :: 0x17 :: 0xCE :: 0x48 :: 0xAF :: 0xE5 ::
  0x2C :: 0x11 :: 0xEA :: 0xB5 :: 0x84 :: 0xF4 :: 0xBC :: 0x0E ::
  0x4D :: 0x5D :: 0x70 :: 0x61 :: 0x42 :: 0xED :: 0xB6 :: 0xF0 ::
  0xB6 :: 0x7A :: 0x99 :: 0xE8 :: 0x27 :: 0x57 :: 0xB2 :: 0xD0 ::
  0x15 :: 0xD5 :: nil).

Definition cavp_msg_74 : list bool := bytes_from (
  0x8B :: 0x7F :: 0xDF :: 0x79 :: 0x2A :: 0x90 :: 0x21 :: 0x8F ::
  0x91 :: 0x99 :: 0x8B :: 0x08 :: 0x47 :: 0x56 :: 0xF3 :: 0x2F ::
  0xF8 :: 0x14 :: 0x88 :: 0x46 :: 0x6B :: 0xCD :: 0x66 :: 0xCE ::
  0xB4 :: 0x95 :: 0x67 :: 0x02 :: 0xAB :: 0x34 :: 0x3C :: 0xA5 ::
  0x9C :: 0x15 :: 0xBD :: 0xFD :: 0x40 :: 0x5F :: 0x7E :: 0x20 ::
  0xEC :: 0x61 :: 0xA3 :: 0x6E :: 0x09 :: 0x33 :: 0xF5 :: 0x5F ::
  0xC4 :: 0x9A :: 0x35 :: 0x7F :: 0x06 :: 0x2D :: 0xB0 :: 0xB6 ::
  0xA7 :: 0xB6 :: 0x13 :: 0xCD :: 0xDF :: 0xDB :: 0x81 :: 0x2E ::
  0xFD :: 0xFE :: 0xE3 :: 0xEB :: 0x5B :: 0x61 :: 0x7F :: 0x02 ::
  0x91 :: 0x8E :: 0xCD :: 0xE0 :: 0xE9 :: 0xF6 :: 0x85 :: 0x23 ::
  0x13 :: 0xD8 :: 0xFD :: 0xA4 :: 0x1A :: 0x64 :: 0xB2 :: 0xB5 ::
  0x97 :: 0x21 :: 0x24 :: 0xA7 :: 0x25 :: 0x8C :: 0xE8 :: 0x90 ::
  0x14 :: 0x02 :: 0xF8 :: 0x4A :: 0x62 :: 0xDF :: 0x4D :: 0xBF ::
  0xE6 :: 0xE8 :: 0xB0 :: 0x64 :: 0xCF :: 0xE6 :: 0xCD :: 0x04 ::
  0x4D :: 0x94 :: 0x89 :: 0xBF :: 0x8E :: 0xBB :: 0x95 :: 0x52 ::
  0xEC :: 0x9C :: 0x43 :: 0x99 :: 0x65 :: 0x8E :: 0x99 :: 0x52 :: nil).

Example hmac_of_the_validation_case_with_a_seventy_four_byte_key_truncated :
  bytes_of (hmac_sha256_truncated 16 cavp_key_74 cavp_msg_74) =
  0x79 :: 0x66 :: 0x44 :: 0x0D :: 0xF7 :: 0x9B :: 0x13 :: 0xE9 ::
  0x5C :: 0x41 :: 0x34 :: 0x6E :: 0xB7 :: 0x92 :: 0xF3 :: 0xEC :: nil.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The HMAC alternatives refuted, and the family the truncating one is
   invisible to computed rather than asserted.
   ------------------------------------------------------------------------- *)

Example the_exchanged_pads_miss_the_published_answer :
  bits_eqb (hmac_with_the_pads_exchanged rfc4231_key_1 rfc4231_data_1)
           (hmac_sha256 rfc4231_key_1 rfc4231_data_1) = false.
Proof. vm_compute. reflexivity. Qed.

Definition short_key_cases : list (list bool * list bool) :=
  pair rfc4231_key_1 rfc4231_data_1 :: pair rfc4231_key_2 rfc4231_data_2 ::
  pair rfc4231_key_3 rfc4231_data_3 :: pair rfc4231_key_4 rfc4231_data_4 ::
  pair rfc4231_key_5 rfc4231_data_5 :: pair cavp_key_64 cavp_msg_64 ::
  pair cavp_key_45 cavp_msg_45 :: nil.

Definition long_key_cases : list (list bool * list bool) :=
  pair rfc4231_key_long rfc4231_data_6 :: pair rfc4231_key_long rfc4231_data_7 ::
  pair cavp_key_70 cavp_msg_70 :: pair cavp_key_74 cavp_msg_74 :: nil.

Example the_truncating_hmac_agrees_at_every_key_within_the_block :
  all_of (fun c => bits_eqb (hmac_with_the_long_key_truncated (fst c) (snd c))
                            (hmac_sha256 (fst c) (snd c)))
         short_key_cases = true.
Proof. vm_compute. reflexivity. Qed.

Example the_truncating_hmac_parts_at_every_key_beyond_the_block :
  all_of (fun c => negb (bits_eqb (hmac_with_the_long_key_truncated (fst c) (snd c))
                                  (hmac_sha256 (fst c) (snd c))))
         long_key_cases = true.
Proof. vm_compute. reflexivity. Qed.

Example the_short_and_long_key_cases_are_split_at_the_block :
  andb (all_of (fun c => Nat.leb (length_of (fst c)) block_bits) short_key_cases)
       (all_of (fun c => Nat.ltb block_bits (length_of (fst c))) long_key_cases) = true.
Proof. vm_compute. reflexivity. Qed.

(* A key of exactly one block is used as it is, so the truncating and the
   hashing forms are the same function on it: this is the boundary the
   corpus's 64-byte case stands on. *)
Example a_one_block_key_is_neither_hashed_nor_padded :
  bits_eqb (hmac_key_over sha256 cavp_key_64) cavp_key_64 = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The edges the composition above computes over and never states, each one
   a site `run.py seed` reached and no statement of this file did. Three
   kinds sit here. A **width**: the shift and the schedule are consumed by
   operations that truncate to the shorter of their operands, so a longer
   answer is cut back to size and the composition's own answers do not move
   with it. An **intermediate**: the multiplier runs only inside a
   comparison, where a product wrong by a little decides the same
   comparison. And a **default**: what a total function answers where its
   input runs out, which nothing above reaches because nothing above hands
   it a ragged input. Each is the transcription's own claim and is stated
   here rather than left to a reader to infer from the functions that
   happen to consume it.
   ------------------------------------------------------------------------- *)

(* s3.2's SHR^n is a shift within the word, so its answer is a word of the
   same width: the exclusive-or in each lower-case sigma truncates to the
   shorter of its operands and cuts a longer answer back again, which is
   what leaves both the width and the shift itself unsaid by every digest
   above. Stated on 0x12345678 at the two amounts the sigmas use, so the
   answer decides the amount as well as the width. The word and both
   answers are written a byte at a time, which is how every other word in
   this file is written and which keeps every literal inside a byte: a
   thirty-two-bit value spelled as one `nat` is a unary numeral the
   evaluator would have to build before it could shift it. *)
Definition shift_probe : word := bytes_from (0x12 :: 0x34 :: 0x56 :: 0x78 :: nil).

Example the_right_shift_by_three_answers_the_standard_s_word :
  bits_eqb (shr 3 shift_probe) (bytes_from (0x02 :: 0x46 :: 0x8A :: 0xCF :: nil)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_right_shift_by_ten_answers_the_standard_s_word :
  bits_eqb (shr 10 shift_probe) (bytes_from (0x00 :: 0x04 :: 0x8D :: 0x15 :: nil)) = true.
Proof. vm_compute. reflexivity. Qed.

(* s6.2.2 step 1 computes the block's sixteen words and forty-eight more,
   and the compression reads the first sixty-four words of whatever it is
   handed, so a schedule computed over too many indices is read short
   rather than refused and no digest above moves with it. *)
Example the_schedule_is_exactly_the_rounds_long :
  Nat.eqb (length_of (schedule (block_at (blocks_of (pad abc)) 0))) rounds = true.
Proof. vm_compute. reflexivity. Qed.

(* The multiplier of the constant derivation, stated on a product rather
   than left inside the comparison the root search makes of it, where a
   product wrong by a little decides the same comparison: 11 * 13 is 143,
   held from both sides so the pair decides the value and not one bound. *)
Example the_multiplier_answers_its_product_from_below :
  leb_le (mul_le (bits_le_of word_bits 11) (bits_le_of word_bits 13))
         (bits_le_of word_bits 143) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_multiplier_answers_its_product_from_above :
  leb_le (bits_le_of word_bits 143)
         (mul_le (bits_le_of word_bits 11) (bits_le_of word_bits 13)) = true.
Proof. vm_compute. reflexivity. Qed.

(* The defaults, each stated at the input that reaches it. Nothing above
   hands any of these functions a ragged input, so each answer below is the
   transcription's own and is stated here rather than inferred from the
   callers that never ask. *)
Example the_bits_past_the_end_of_a_string_are_zero :
  bits_eqb (map_over (bit_at zero_word) (up_from word_bits word_bits)) zero_word = true.
Proof. vm_compute. reflexivity. Qed.

Example a_string_is_unequal_to_its_own_prefix :
  negb (bits_eqb zero_word (take_of hash_words zero_word)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_comparison_answers_where_the_first_string_runs_out :
  leb_be nil zero_word = true.
Proof. vm_compute. reflexivity. Qed.

Example the_comparison_answers_where_the_second_string_runs_out :
  leb_be zero_word nil = true.
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
Print Assumptions zip_with.
Print Assumptions last_of.
Print Assumptions chunks_of.
Print Assumptions eqb_bool.
Print Assumptions bits_eqb.
Print Assumptions bits_le_of.
Print Assumptions bits_be_of.
Print Assumptions set_bit.
Print Assumptions byte_bits.
Print Assumptions word_bits.
Print Assumptions block_bits.
Print Assumptions length_bits.
Print Assumptions digest_bits.
Print Assumptions rounds.
Print Assumptions words_per_block.
Print Assumptions hash_words.
Print Assumptions a_block_is_sixteen_words.
Print Assumptions a_digest_is_eight_words.
Print Assumptions byte.
Print Assumptions word.
Print Assumptions zero_word.
Print Assumptions bits_of_byte.
Print Assumptions byte_value.
Print Assumptions bytes_from.
Print Assumptions bytes_of.
Print Assumptions a_byte_round_trips_over_all_two_hundred_and_fifty_six.
Print Assumptions the_head_of_a_byte_is_its_most_significant_bit.
Print Assumptions wxor.
Print Assumptions wand.
Print Assumptions wnot.
Print Assumptions wxor3.
Print Assumptions rotr.
Print Assumptions shr.
Print Assumptions majb.
Print Assumptions carry_into.
Print Assumptions add_le.
Print Assumptions wadd.
Print Assumptions wsum.
Print Assumptions shift_le.
Print Assumptions mul_le.
Print Assumptions pad_le.
Print Assumptions leb_be.
Print Assumptions leb_le.
Print Assumptions with_bit.
Print Assumptions root_by_bits.
Print Assumptions square_le.
Print Assumptions cube_le.
Print Assumptions prime_bits.
Print Assumptions root_fraction.
Print Assumptions cube_root_fraction.
Print Assumptions square_root_fraction.
Print Assumptions divides.
Print Assumptions is_prime.
Print Assumptions primes_from.
Print Assumptions first_primes.
Print Assumptions the_first_eight_primes.
Print Assumptions there_are_sixty_four_primes_and_the_last_is_311.
Print Assumptions derived_round_constants.
Print Assumptions round_constants.
Print Assumptions derived_initial_hash.
Print Assumptions initial_hash.
Print Assumptions the_round_constants_are_the_derivation.
Print Assumptions the_initial_hash_is_the_derivation.
Print Assumptions the_round_constants_are_the_published_table.
Print Assumptions the_initial_hash_is_the_published_table.
Print Assumptions the_round_constants_are_sixty_four_distinct_words.
Print Assumptions ch.
Print Assumptions maj.
Print Assumptions big_sigma0.
Print Assumptions big_sigma1.
Print Assumptions small_sigma0.
Print Assumptions small_sigma1.
Print Assumptions rotation_amounts.
Print Assumptions the_listed_amounts_are_the_ones_the_four_sigmas_use.
Print Assumptions the_ten_amounts_are_ten_and_none_of_them_is_a_whole_word.
Print Assumptions word_at.
Print Assumptions block_at.
Print Assumptions schedule_over.
Print Assumptions schedule.
Print Assumptions schedule_with_the_sigmas_exchanged.
Print Assumptions Working.
Print Assumptions working_of.
Print Assumptions list_of.
Print Assumptions round_over.
Print Assumptions round_step.
Print Assumptions compress_over.
Print Assumptions compress.
Print Assumptions compress_with_maj_written_as_ch.
Print Assumptions zeros_after.
Print Assumptions big_endian_length.
Print Assumptions pad_over.
Print Assumptions pad.
Print Assumptions byte_reversed_length.
Print Assumptions pad_with_a_byte_reversed_length.
Print Assumptions pad_without_its_one.
Print Assumptions blocks_of.
Print Assumptions sha256_over.
Print Assumptions sha256.
Print Assumptions sha256_with_the_pad_missing_its_one.
Print Assumptions sha256_with_a_byte_reversed_length.
Print Assumptions sha256_with_the_sigmas_exchanged.
Print Assumptions sha256_with_maj_written_as_ch.
Print Assumptions hmac_block_bytes.
Print Assumptions ipad_byte.
Print Assumptions opad_byte.
Print Assumptions pad_block.
Print Assumptions hmac_key_over.
Print Assumptions hmac_over.
Print Assumptions hmac_sha256.
Print Assumptions hmac_sha256_truncated.
Print Assumptions hmac_with_the_pads_exchanged.
Print Assumptions hmac_with_the_long_key_truncated.
Print Assumptions xorb_comm_local.
Print Assumptions majb_comm_local.
Print Assumptions the_adder_is_commutative.
Print Assumptions word_addition_is_commutative.
Print Assumptions the_rotations_are_invertible_on_an_arbitrary_word.
Print Assumptions the_schedule_keeps_the_block_as_its_first_sixteen_words.
Print Assumptions probe_lengths.
Print Assumptions the_probes_reach_past_two_whole_blocks.
Print Assumptions the_pad_is_a_positive_multiple_of_the_block_at_every_probed_length.
Print Assumptions the_message_is_a_prefix_of_its_pad_and_the_length_is_its_suffix.
Print Assumptions the_one_bit_follows_the_message.
Print Assumptions the_defective_pads_keep_the_standards_length.
Print Assumptions the_pad_without_its_one_differs_from_the_pad_in_that_bit_alone.
Print Assumptions the_byte_reversed_length_agrees_with_the_standard_only_where_the_field_is_zero.
Print Assumptions abc.
Print Assumptions the_first_schedule_word_of_abc_is_the_message_and_its_one_bit.
Print Assumptions the_sixteenth_schedule_word_of_abc_is_its_bit_length.
Print Assumptions the_first_round_of_abc_reaches_the_published_working_variables.
Print Assumptions sha256_of_abc.
Print Assumptions two_block_message.
Print Assumptions the_two_block_message_pads_to_two_blocks.
Print Assumptions sha256_of_the_two_block_message.
Print Assumptions sha256_of_the_empty_message.
Print Assumptions message_of_55_bytes.
Print Assumptions sha256_of_55_bytes_fits_its_length_in_one_block.
Print Assumptions message_of_56_bytes.
Print Assumptions sha256_of_56_bytes_needs_a_second_block.
Print Assumptions message_of_63_bytes.
Print Assumptions sha256_of_63_bytes.
Print Assumptions message_of_64_bytes.
Print Assumptions sha256_of_64_bytes_fills_a_block_and_pads_into_a_second.
Print Assumptions message_of_163_bytes.
Print Assumptions sha256_of_163_bytes_spans_three_blocks.
Print Assumptions the_pad_without_its_one_misses_the_published_digest.
Print Assumptions the_byte_reversed_length_misses_the_published_digest.
Print Assumptions the_byte_reversed_length_agrees_at_the_empty_message.
Print Assumptions the_exchanged_sigmas_miss_the_published_digest.
Print Assumptions maj_written_as_ch_misses_the_published_digest.
Print Assumptions ch_and_maj_agree_where_the_last_two_words_coincide.
Print Assumptions ch_and_maj_part_at_the_initial_hash.
Print Assumptions rfc4231_key_1.
Print Assumptions rfc4231_data_1.
Print Assumptions hmac_of_rfc4231_case_1.
Print Assumptions rfc4231_key_2.
Print Assumptions rfc4231_data_2.
Print Assumptions hmac_of_rfc4231_case_2.
Print Assumptions rfc4231_key_3.
Print Assumptions rfc4231_data_3.
Print Assumptions hmac_of_rfc4231_case_3.
Print Assumptions rfc4231_key_4.
Print Assumptions rfc4231_data_4.
Print Assumptions hmac_of_rfc4231_case_4.
Print Assumptions rfc4231_key_5.
Print Assumptions rfc4231_data_5.
Print Assumptions hmac_of_rfc4231_case_5_truncated_to_sixteen_bytes.
Print Assumptions rfc4231_key_long.
Print Assumptions rfc4231_data_6.
Print Assumptions hmac_of_rfc4231_case_6_hashes_its_long_key.
Print Assumptions rfc4231_data_7.
Print Assumptions hmac_of_rfc4231_case_7_hashes_its_long_key_over_a_long_message.
Print Assumptions cavp_key_64.
Print Assumptions cavp_msg_64.
Print Assumptions hmac_of_the_validation_case_with_a_one_block_key.
Print Assumptions cavp_key_45.
Print Assumptions cavp_msg_45.
Print Assumptions hmac_of_the_validation_case_with_a_forty_five_byte_key.
Print Assumptions cavp_key_70.
Print Assumptions cavp_msg_70.
Print Assumptions hmac_of_the_validation_case_with_a_seventy_byte_key.
Print Assumptions cavp_key_74.
Print Assumptions cavp_msg_74.
Print Assumptions hmac_of_the_validation_case_with_a_seventy_four_byte_key_truncated.
Print Assumptions the_exchanged_pads_miss_the_published_answer.
Print Assumptions short_key_cases.
Print Assumptions long_key_cases.
Print Assumptions the_truncating_hmac_agrees_at_every_key_within_the_block.
Print Assumptions the_truncating_hmac_parts_at_every_key_beyond_the_block.
Print Assumptions the_short_and_long_key_cases_are_split_at_the_block.
Print Assumptions a_one_block_key_is_neither_hashed_nor_padded.
Print Assumptions shift_probe.
Print Assumptions the_right_shift_by_three_answers_the_standard_s_word.
Print Assumptions the_right_shift_by_ten_answers_the_standard_s_word.
Print Assumptions the_schedule_is_exactly_the_rounds_long.
Print Assumptions the_multiplier_answers_its_product_from_below.
Print Assumptions the_multiplier_answers_its_product_from_above.
Print Assumptions the_bits_past_the_end_of_a_string_are_zero.
Print Assumptions a_string_is_unequal_to_its_own_prefix.
Print Assumptions the_comparison_answers_where_the_first_string_runs_out.
Print Assumptions the_comparison_answers_where_the_second_string_runs_out.
