(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   RomVerifier.v

   What the boot chain's ROM verifier needs, stated over Keccak.v's
   `shake256`: the SLH-DSA-SHAKE-256s parameter set R-05-058a freezes, the
   six function instantiations FIPS 205 s11.1 puts over SHAKE256, the sizes
   and the hash-call census that parameter set determines, and the shape
   R-09-005, R-09-005a and R-09-036 put on the object that runs them.

   What this file is, and what it is not. It is a **statement** and not a
   scheme. **No part of SLH-DSA is authored here**: there is no WOTS+ chain,
   no FORS tree, no Merkle path, no hypertree and no verification algorithm,
   because authoring one is M3.4b-class work and because the item this file
   lands under owes a statement of what the verifier needs rather than a
   scheme nothing in the frozen suite names. What is here is the substrate,
   the parameter literals, the arithmetic those literals determine, and the
   record the register's own clauses become when they are written as things
   a construction either has or does not have. It is not an implementation,
   no binary corresponds to it, and it discharges no acceptance clause of
   any entry.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. Nothing here executes on
   either emulator. The computed checks are decided inside the kernel, the
   light ones by conversion in the silent `Example ... := eq_refl` form and
   the ones that run a sponge by the bytecode machine, which contributes
   nothing to the Print Assumptions block at the end.

   The three assurance layers, and which one this is. What is here is the
   **functional layer** and, for the verifier itself, a **shape**. No
   constant-time property is claimed (R-05-062, R-05-067); no masking claim
   is made (R-05-004a); no reduction and no distributional claim is made
   (R-05-077a), and this file states nothing at all about the hardness the
   hash-only assumption rests on. R-17-049's irreducible assumptions stay
   irreducible and this file neither weakens nor discharges one.

   One Require, and what it reaches. `Require Import Keccak.` is a sibling
   artifact under proofs/ that Requires nothing, so the reach of this file
   is the prelude, that file and this one, and every constant enumerated at
   the end of both is closed under the global context. `shake256` below is
   that file's, at that file's bit order, and no second transcription of
   FIPS 202 is made here.

   The representation, which no register entry fixes and which is therefore
   a reading of this file:

   1. **Bit strings are Keccak.v's**, and an output length is in bits, so
      the standard's `8n` is written `8 * hash_bytes p` and reaches
      `shake256` as its first argument.
   2. **A parameter set is a record of the seven quantities FIPS 205's
      Table 2 tabulates independently** and every other quantity, the two
      Winternitz lengths, the message-digest length, the public key size and
      the signature size, is computed from them by the standard's own
      formulas. The table's own `m`, its public key size and its signature
      size are then held equal to what the formulas give, which is the
      differential shape M3.4a and M3.4d set at FIPS 202 and FIPS 197: what
      is derived is checked against what the standard publishes.
   3. **The verifier is a record of what it has rather than a function that
      runs.** Its phases are a list, its primitive calls are a list of tags
      naming which primitive each reaches, its accepted roots are a map from
      the lifecycle state, and its anti-rollback floor is a number. A
      predicate over that record is decidable, which is what lets each of
      the register's clauses be a thing the witness does rather than a
      sentence beside it.
   4. **The absence of an unlock path is modelled as the absence of an
      argument.** R-09-036 wants no fuse, strap or signed unlock token to
      widen the accepted root set, and the field's type here is
      `Lifecycle -> list Root`, which has nowhere for such a token to enter.
      That is a **shape and not a proof**: it says this model cannot express
      the widening, not that no implementation can, and the file says so
      here rather than letting the type read as evidence.

   The readings of the register this file takes:

   1. **R-05-058c's ground is the hash-only assumption, and `HashOnly` is
      that ground made decidable.** The entry splits the schemes by verifier,
      puts SLH-DSA at everything a metal-mask ROM verifies, and its
      acceptance is that no ROM-resident lattice verifier exists. The four
      things it names a lattice verifier needing, an NTT, a matrix
      expansion, a rejection sampler and a hint decoder, are four
      constructors of `Prim` here, and a verifier is hash-only exactly when
      every call it makes tags `Shake256`. The refuted instance below is a
      verifier carrying all four, and it is held to that single difference:
      it still measures before it executes, still checks the floor and still
      accepts the production root alone.
   2. **The six instantiations are FIPS 205 s11.1's and three of them are
      one function.** At the SHAKE parameter sets `F`, `H` and `T_l` are all
      `SHAKE256(PK.seed || ADRS || M, 8n)`, so what separates a chain step
      from a tree node from a leaf compression is the address and nothing
      else. That is stated here as an equality holding at every argument,
      and the near alternative it exists to exclude is the same call with
      the address dropped, which has the same output length, is `shake256`
      in every other respect, and collapses the three roles into one.
      **`PRF` is the one of the six whose signature and whose concatenation
      disagree**, the standard writing `PRF(PK.seed, SK.seed, ADRS)` and
      instantiating it over `PK.seed || ADRS || SK.seed`, so both are
      written out below and the alternative that concatenates in its own
      argument order is built and refuted. That alternative agrees with the
      standard's at every input whose address and secret seed are the same
      string, which is exactly the family a test reusing one value for both
      would not separate them on, and the file computes that agreement
      rather than leaving it to be found.
   3. **R-09-005a's two figures are read differently, and the file says
      which is which.** *Tens of kilobytes* is made a figure: the signature
      size the parameter set determines is 29,792 bytes, which the file
      computes and holds inside ten and a hundred kibibytes. *Thousands of
      Keccak permutations* is a typical-case figure and not a bound the
      parameters force: the census below is 8,444 calls where every WOTS+
      chain is walked whole and 764 where none is, so the low end is
      hundreds. Both ends are computed and the gap is reported at that
      entry rather than repaired here.
   4. **The census counts calls and not permutations.** Every call of the
      six absorbs at least one block and so costs at least one Keccak
      permutation, and the two tree-root compressions absorb more than one,
      so the census is a lower bound on the permutations of a verification
      that makes those calls. It is arithmetic over the parameter set with
      each term named to the clause of FIPS 205 it counts, and it is not a
      construction: nothing here computes a chain, a path or a root.
   5. **The oracle enters no trust base.** Every published answer below is a
      constant inside an `Example`'s own statement, never a `Definition`.

   What is deliberately absent, with the entry that owes each decision. A
   register gap is reported, not closed:

   a. **No verification algorithm.** WOTS+, FORS, the Merkle path and the
      hypertree are M3.4b's, and a classical signature scheme is what the
      frozen suite does not contain at all (R-17-049b: no requirement claims
      a hybrid signature, and the two roles the diversity is stated over are
      the ROM-verified and the re-signable). Owed at M3.4b.
   b. **No entry states the header's field offsets, its length bound or the
      order of its fields.** R-09-005 says fixed-layout and length-bounded
      and states no number, so the witness's offsets are this file's and the
      predicate holds the shape rather than the values. Owed at R-09-005.
   c. **No entry states the anti-rollback floor's width, its unit or where
      it is stored.** The floor is a `nat` here and the comparison is the
      only thing stated of it. Owed at R-09-005.
   d. **No entry says which roots the four lifecycle states other than
      production accept.** R-09-036 fixes production's set at one and says
      nothing of raw, test, development or RMA; the witness's other four
      sets are this file's reading and are not held by the predicate. Owed
      at R-09-036.
   e. **Nothing in the register names an address at all**, so whether the
      domain separation `ADRS` supplies is the reading R-05-058c's hash-only
      ground wants is unstated. Owed at R-05-058c.
   f. **No constant-time claim, no masking claim, no reduction** (above).

   The literals taken from the standards, and there are no others. FIPS
   205's Table 2 row for SLH-DSA-SHAKE-256s, which is n = 32, h = 64,
   d = 8, h' = 8, a = 14, k = 22 and lg_w = 4 together with that row's own
   m = 47, public key of 64 bytes and signature of 29,792 bytes; and s11.1's
   32-byte address, which is the full `ADRS` the SHAKE parameter sets use
   where the SHA-2 sets compress it. Every other quantity here is computed.

   Non-vacuity (R-05-165, R-05-166). `demo` inhabits the parameter set, the
   header, the call, the phase order and the verifier, and discharges
   `Admissible` by conversion. Five verifiers the predicate refuses are
   built and refuted, one carrying a lattice verifier's four primitives, one
   executing before it is measured, one with no floor check, one accepting a
   development root in production, and one whose header sizes the signature
   field at the public key's size; each is held to its single difference,
   keeping every clause it does not break. Beside them the address-free hash
   is built and refuted at two addresses that separate under the standard's
   own form. Inhabitation is the published sizes themselves, so no check
   below holds of everything and none holds of nothing.

   Where each published answer came from. FIPS 205, *Stateless Hash-Based
   Digital Signature Standard*, read on 2026-09-05 at the copy fetched from
   nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.205.pdf: Table 2 for the
   parameter row and the three published sizes, s5 for the two Winternitz
   lengths, s10.1 for the message-digest length, and s11.1 for the six
   instantiations and the address size. The instrument is the one
   Sha256.v records for NIST's own files at nist.gov/oism/copyrights, whose
   three paragraphs do not agree on what reaches a published standard, so
   the strictest is met here as it is there: the document and NIST as its
   source are named, the parameters are quoted unmodified, and no change
   notice is owed because nothing was changed. Every derived quantity was
   recomputed by hand from the standard's formulas before it was written
   down here.
   ========================================================================= *)

Require Import Keccak.

Open Scope list_scope.

(* -------------------------------------------------------------------------
   Helpers this file adds to Keccak.v's, in the same idiom.
   ------------------------------------------------------------------------- *)

Definition ceil_div (a b : nat) : nat := Nat.div (a + b - 1) b.

(* The number of digits x takes in the given base, which is FIPS 205's
   floor(lg X / lg w) + 1 written without a logarithm. *)
Fixpoint digits_base (fuel base x : nat) : nat :=
  match fuel with
  | 0 => 0
  | S f => if Nat.ltb x base then 1 else S (digits_base f base (Nat.div x base))
  end.

Fixpoint index_from {A : Type} (eqb : A -> A -> bool) (x : A) (l : list A) (i : nat) : nat :=
  match l with
  | nil => i
  | y :: rest => if eqb x y then i else index_from eqb x rest (S i)
  end.

Definition index_of {A : Type} (eqb : A -> A -> bool) (x : A) (l : list A) : nat :=
  index_from eqb x l 0.

Definition precedes_in {A : Type} (eqb : A -> A -> bool) (x y : A) (l : list A) : bool :=
  Nat.ltb (index_of eqb x l) (index_of eqb y l).

Definition occurs_once {A : Type} (eqb : A -> A -> bool) (x : A) (l : list A) : bool :=
  Nat.eqb (count_where (eqb x) l) 1.

Definition any_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  negb (all_of (fun x => negb (p x)) l).

(* The two arithmetic helpers are checked where they round rather than only
   where they are used, because every value the parameter sets below feed
   them happens to divide and a helper checked at those alone is checked at
   the case that cannot go wrong. *)
Example the_ceiling_rounds_up_where_the_division_does_not_divide :
  andb (andb (Nat.eqb (ceil_div 8 8) 1) (Nat.eqb (ceil_div 9 8) 2))
       (andb (Nat.eqb (ceil_div 0 8) 0) (Nat.eqb (ceil_div 16 8) 2)) = true.
Proof. vm_compute. reflexivity. Qed.

Example a_value_equal_to_the_base_takes_two_digits :
  andb (andb (Nat.eqb (digits_base 8 16 15) 1) (Nat.eqb (digits_base 8 16 16) 2))
       (andb (Nat.eqb (digits_base 8 16 255) 2) (Nat.eqb (digits_base 8 16 256) 3)) = true.
Proof. vm_compute. reflexivity. Qed.

(* The prelude carries `Nat.leb` and `Nat.ltb` and none of the arithmetic
   theory about them, so the one ordering fact the floor check needs is
   authored here rather than imported. *)
Lemma leb_false_of_ltb : forall a b : nat, Nat.ltb a b = true -> Nat.leb b a = false.
Proof.
  unfold Nat.ltb.
  induction a as [| a IH]; intros b H.
  - destruct b as [| b]. discriminate H. reflexivity.
  - destruct b as [| b]. discriminate H.
    simpl. apply IH. simpl in H. exact H.
Qed.

Lemma andb_left : forall a b : bool, andb a b = true -> a = true.
Proof. intros a b H. destruct a. reflexivity. simpl in H. discriminate H. Qed.

Lemma andb_right : forall a b : bool, andb a b = true -> b = true.
Proof. intros a b H. destruct a. exact H. simpl in H. discriminate H. Qed.

(* -------------------------------------------------------------------------
   The parameter set: the seven quantities FIPS 205's Table 2 tabulates
   independently, and the formulas of s5 and s10.1 over them.
   ------------------------------------------------------------------------- *)

Record ParameterSet : Type := {
  hash_bytes : nat;       (* n *)
  tree_height : nat;      (* h *)
  layers : nat;           (* d *)
  subtree_height : nat;   (* h', which the table gives and h / d determines *)
  fors_height : nat;      (* a *)
  fors_trees : nat;       (* k *)
  lg_winternitz : nat     (* lg_w *)
}.

Definition winternitz (p : ParameterSet) : nat := Nat.pow 2 (lg_winternitz p).

Definition message_len (p : ParameterSet) : nat :=
  ceil_div (8 * hash_bytes p) (lg_winternitz p).

Definition checksum_len (p : ParameterSet) : nat :=
  digits_base 64 (winternitz p) (message_len p * (winternitz p - 1)).

Definition chain_count (p : ParameterSet) : nat := message_len p + checksum_len p.

Definition digest_bytes (p : ParameterSet) : nat :=
  ceil_div (fors_trees p * fors_height p) 8
  + ceil_div (tree_height p - Nat.div (tree_height p) (layers p)) 8
  + ceil_div (Nat.div (tree_height p) (layers p)) 8.

Definition public_key_bytes (p : ParameterSet) : nat := 2 * hash_bytes p.

Definition signature_bytes (p : ParameterSet) : nat :=
  (1 + fors_trees p * (1 + fors_height p) + tree_height p + layers p * chain_count p)
  * hash_bytes p.

(* R-05-058a's frozen choice, read from Table 2. *)
Definition shake_256s : ParameterSet :=
  {| hash_bytes := 32;
     tree_height := 64;
     layers := 8;
     subtree_height := 8;
     fors_height := 14;
     fors_trees := 22;
     lg_winternitz := 4 |}.

Example the_table_row_agrees_with_the_height_it_implies :
  Nat.eqb (subtree_height shake_256s)
          (Nat.div (tree_height shake_256s) (layers shake_256s)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_two_winternitz_lengths_are_sixty_four_and_three :
  andb (Nat.eqb (message_len shake_256s) 64) (Nat.eqb (checksum_len shake_256s) 3) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_chain_count_is_sixty_seven : Nat.eqb (chain_count shake_256s) 67 = true.
Proof. vm_compute. reflexivity. Qed.

(* Table 2's own m, pk and sig columns, against the formulas above. *)
Example the_message_digest_is_the_published_forty_seven_bytes :
  Nat.eqb (digest_bytes shake_256s) 47 = true.
Proof. vm_compute. reflexivity. Qed.

Example the_public_key_is_the_published_sixty_four_bytes :
  Nat.eqb (public_key_bytes shake_256s) 64 = true.
Proof. vm_compute. reflexivity. Qed.

Example the_signature_is_the_published_twenty_nine_thousand_seven_hundred_and_ninety_two_bytes :
  Nat.eqb (signature_bytes shake_256s) 29792 = true.
Proof. vm_compute. reflexivity. Qed.

(* R-09-005a's first figure, made a figure. *)
Example the_signature_is_tens_of_kilobytes :
  andb (Nat.leb (10 * 1024) (signature_bytes shake_256s))
       (Nat.ltb (signature_bytes shake_256s) (100 * 1024)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_signature_is_four_hundred_and_sixty_five_times_the_public_key_and_a_half :
  Nat.eqb (2 * signature_bytes shake_256s)
          (931 * public_key_bytes shake_256s) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_maximum_checksum_takes_three_base_sixteen_digits :
  andb (Nat.eqb (message_len shake_256s * (winternitz shake_256s - 1)) 960)
       (Nat.eqb (checksum_len shake_256s) 3) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The whole of Table 2's SHAKE half, because one row checks the formulas at
   one point and six check them where they differ. Each row's seven
   tabulated quantities are definitions, being inputs; each row's published
   m, public key size and signature size stays inside the statement that
   decides against it, so no published answer is a mutation target.
   ------------------------------------------------------------------------- *)

Definition shake_128s : ParameterSet :=
  {| hash_bytes := 16; tree_height := 63; layers := 7; subtree_height := 9;
     fors_height := 12; fors_trees := 14; lg_winternitz := 4 |}.

Definition shake_128f : ParameterSet :=
  {| hash_bytes := 16; tree_height := 66; layers := 22; subtree_height := 3;
     fors_height := 6; fors_trees := 33; lg_winternitz := 4 |}.

Definition shake_192s : ParameterSet :=
  {| hash_bytes := 24; tree_height := 63; layers := 7; subtree_height := 9;
     fors_height := 14; fors_trees := 17; lg_winternitz := 4 |}.

Definition shake_192f : ParameterSet :=
  {| hash_bytes := 24; tree_height := 66; layers := 22; subtree_height := 3;
     fors_height := 8; fors_trees := 33; lg_winternitz := 4 |}.

Definition shake_256f : ParameterSet :=
  {| hash_bytes := 32; tree_height := 68; layers := 17; subtree_height := 4;
     fors_height := 9; fors_trees := 35; lg_winternitz := 4 |}.

Definition shake_sets : list ParameterSet :=
  shake_128s :: shake_128f :: shake_192s :: shake_192f :: shake_256s :: shake_256f :: nil.

Example the_six_rows_derive_their_published_message_digest_lengths :
  map_over digest_bytes shake_sets = 30 :: 34 :: 39 :: 42 :: 47 :: 49 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_six_rows_derive_their_published_public_key_sizes :
  map_over public_key_bytes shake_sets = 32 :: 32 :: 48 :: 48 :: 64 :: 64 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_six_rows_derive_their_published_signature_sizes :
  map_over signature_bytes shake_sets = 7856 :: 17088 :: 16224 :: 35664 :: 29792 :: 49856 :: nil.
Proof. vm_compute. reflexivity. Qed.

(* h' is tabulated and h / d determines it, so the table states one quantity
   twice and the two are held together here rather than left to agree. *)
Example every_rows_subtree_height_is_its_own_quotient :
  all_of (fun p => Nat.eqb (subtree_height p) (Nat.div (tree_height p) (layers p)))
         shake_sets = true.
Proof. vm_compute. reflexivity. Qed.

Example every_rows_checksum_takes_three_digits :
  all_of (fun p => Nat.eqb (checksum_len p) 3) shake_sets = true.
Proof. vm_compute. reflexivity. Qed.

Example the_six_rows_derive_their_chain_counts :
  map_over chain_count shake_sets = 35 :: 35 :: 51 :: 51 :: 67 :: 67 :: nil.
Proof. vm_compute. reflexivity. Qed.

Example the_frozen_row_is_the_one_the_suite_names :
  andb (Nat.eqb (hash_bytes shake_256s) 32)
       (negb (Nat.eqb (tree_height shake_256s) (tree_height shake_256f))) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   FIPS 205 s11.1: the six functions at the SHAKE parameter sets, each of
   them SHAKE256 over a concatenation the standard fixes. The address is
   the full thirty-two bytes here, which is what the SHAKE sets use where
   the SHA-2 sets compress it.
   ------------------------------------------------------------------------- *)

Definition address_bytes : nat := 32.

Definition h_msg (p : ParameterSet) (randomizer pk_seed pk_root message : list bool) : list bool :=
  shake256 (8 * digest_bytes p) (randomizer ++ pk_seed ++ pk_root ++ message).

(* PRF is the one of the six whose argument order is not its concatenation
   order: the standard writes `PRF(PK.seed, SK.seed, ADRS)` and instantiates
   it as `SHAKE256(PK.seed || ADRS || SK.seed, 8n)`, so the address sits
   between the two seeds while the signature puts it last. The signature
   here is the standard's and so is the concatenation, which is the whole
   point of writing both down. *)
Definition prf (p : ParameterSet) (pk_seed sk_seed address : list bool) : list bool :=
  shake256 (8 * hash_bytes p) (pk_seed ++ address ++ sk_seed).

(* The transcription defect that exists: a PRF that concatenates in its own
   argument order. It has the same output length and reads the same three
   inputs, and it is the reading a transcriber who copied the signature and
   not the body would produce. *)
Definition prf_in_its_argument_order (p : ParameterSet)
                                     (pk_seed sk_seed address : list bool) : list bool :=
  shake256 (8 * hash_bytes p) (pk_seed ++ sk_seed ++ address).

Definition prf_msg (p : ParameterSet) (sk_prf opt_rand message : list bool) : list bool :=
  shake256 (8 * hash_bytes p) (sk_prf ++ opt_rand ++ message).

Definition f_chain (p : ParameterSet) (pk_seed address m : list bool) : list bool :=
  shake256 (8 * hash_bytes p) (pk_seed ++ address ++ m).

Definition h_node (p : ParameterSet) (pk_seed address m : list bool) : list bool :=
  shake256 (8 * hash_bytes p) (pk_seed ++ address ++ m).

Definition t_compress (p : ParameterSet) (pk_seed address m : list bool) : list bool :=
  shake256 (8 * hash_bytes p) (pk_seed ++ address ++ m).

(* The near alternative: the same call with the address dropped. It is
   `shake256` in every other respect and returns the same length. *)
Definition f_without_its_address (p : ParameterSet) (pk_seed address m : list bool) : list bool :=
  shake256 (8 * hash_bytes p) (pk_seed ++ m).

(* At the SHAKE sets the three short functions are one function, so the
   address is the whole of what separates the three roles. Stated at every
   argument rather than at a value. *)
Theorem the_chain_the_node_and_the_compression_are_one_function :
  forall (p : ParameterSet) (s a m : list bool),
    f_chain p s a m = h_node p s a m /\ h_node p s a m = t_compress p s a m.
Proof. intros. split. reflexivity. reflexivity. Qed.

Theorem the_address_free_hash_ignores_its_address :
  forall (p : ParameterSet) (s a1 a2 m : list bool),
    f_without_its_address p s a1 m = f_without_its_address p s a2 m.
Proof. intros. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The substrate, computed. Two addresses, a seed and a message, run
   through the standard's form and through the address-free one.
   ------------------------------------------------------------------------- *)

Definition demo_seed : list bool := bits_of_bytes (repeat_of 32 0x5A).
Definition demo_message : list bool := bits_of_bytes (repeat_of 32 0xA5).
Definition demo_address_one : list bool := bits_of_bytes (repeat_of 32 0x00).
Definition demo_address_two : list bool :=
  bits_of_bytes (0x01 :: repeat_of 31 0x00).

Example the_addresses_are_the_standards_thirty_two_bytes :
  andb (Nat.eqb (length_of demo_address_one) (8 * address_bytes))
       (Nat.eqb (length_of demo_address_two) (8 * address_bytes)) = true.
Proof. vm_compute. reflexivity. Qed.

(* The seed and the message are n bytes, which is what the standard's own
   arguments to these functions are. *)
Example the_seed_and_the_message_are_n_bytes :
  andb (Nat.eqb (length_of demo_seed) (8 * hash_bytes shake_256s))
       (Nat.eqb (length_of demo_message) (8 * hash_bytes shake_256s)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_two_addresses_differ_in_one_byte :
  andb (negb (bits_eqb demo_address_one demo_address_two))
       (bits_eqb (drop_of 8 demo_address_one) (drop_of 8 demo_address_two)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_six_functions_return_the_lengths_the_standard_fixes :
  andb (Nat.eqb (length_of (h_msg shake_256s demo_seed demo_seed demo_seed demo_message))
                (8 * digest_bytes shake_256s))
  (andb (Nat.eqb (length_of (prf shake_256s demo_seed demo_seed demo_address_one))
                 (8 * hash_bytes shake_256s))
  (andb (Nat.eqb (length_of (prf_msg shake_256s demo_seed demo_seed demo_message))
                 (8 * hash_bytes shake_256s))
        (Nat.eqb (length_of (f_chain shake_256s demo_seed demo_address_one demo_message))
                 (8 * hash_bytes shake_256s)))) = true.
Proof. vm_compute. reflexivity. Qed.

Example two_addresses_separate_the_same_message :
  negb (bits_eqb (f_chain shake_256s demo_seed demo_address_one demo_message)
                 (f_chain shake_256s demo_seed demo_address_two demo_message)) = true.
Proof. vm_compute. reflexivity. Qed.

(* The two PRFs read the same three inputs, return the same length, and
   differ at the first pair of seeds that are not the address. *)
Example the_argument_ordered_prf_misses_the_standards_answer :
  andb (Nat.eqb (length_of (prf_in_its_argument_order shake_256s demo_seed demo_message
                                                      demo_address_one))
                (length_of (prf shake_256s demo_seed demo_message demo_address_one)))
       (negb (bits_eqb (prf_in_its_argument_order shake_256s demo_seed demo_message
                                                  demo_address_one)
                       (prf shake_256s demo_seed demo_message demo_address_one))) = true.
Proof. vm_compute. reflexivity. Qed.

(* And it agrees with the standard's wherever the address and the secret
   seed are the same string, which is the family of inputs a test that
   reused one value for both would not separate them on. *)
Example the_argument_ordered_prf_agrees_where_the_two_tails_coincide :
  bits_eqb (prf_in_its_argument_order shake_256s demo_seed demo_message demo_message)
           (prf shake_256s demo_seed demo_message demo_message) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_address_free_hash_collapses_the_two_addresses :
  andb (bits_eqb (f_without_its_address shake_256s demo_seed demo_address_one demo_message)
                 (f_without_its_address shake_256s demo_seed demo_address_two demo_message))
       (Nat.eqb (length_of (f_without_its_address shake_256s demo_seed demo_address_one
                                                  demo_message))
                (length_of (f_chain shake_256s demo_seed demo_address_one demo_message)))
  = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The hash-call census: arithmetic over the parameter set, with each term
   named to the clause of FIPS 205 it counts. It is a count and not a
   construction, and it counts calls of the six functions above rather than
   Keccak permutations, every call costing at least one of those.
   ------------------------------------------------------------------------- *)

(* s8: one leaf per tree and one node per authentication-path step, then one
   compression over the k roots. Message-independent. *)
Definition fors_calls (p : ParameterSet) : nat :=
  fors_trees p * (1 + fors_height p) + 1.

(* s5: a verifier walks each chain from the signature's digit to w - 1, so
   the steps a layer costs run from none, where every message digit is
   w - 1 and the checksum digits are therefore all zero, to all of them. *)
Definition chain_steps_at_most (p : ParameterSet) : nat :=
  chain_count p * (winternitz p - 1).

Definition chain_steps_at_least (p : ParameterSet) : nat :=
  checksum_len p * (winternitz p - 1).

(* s6 and s7: one compression per layer over that layer's chain ends, and
   h' nodes up the subtree. *)
Definition layer_calls (steps : nat) (p : ParameterSet) : nat :=
  steps + 1 + subtree_height p.

Definition verify_calls (steps : nat) (p : ParameterSet) : nat :=
  1 + fors_calls p + layers p * layer_calls steps p.

Definition verify_calls_at_most (p : ParameterSet) : nat :=
  verify_calls (chain_steps_at_most p) p.

Definition verify_calls_at_least (p : ParameterSet) : nat :=
  verify_calls (chain_steps_at_least p) p.

Example the_census_runs_from_seven_hundred_and_sixty_four_to_eight_thousand_four_hundred_and_forty_four :
  andb (Nat.eqb (verify_calls_at_least shake_256s) 764)
       (Nat.eqb (verify_calls_at_most shake_256s) 8444) = true.
Proof. vm_compute. reflexivity. Qed.

(* R-09-005a's second figure, and the half of it the parameters do not
   force: the high end is thousands and the low end is hundreds. *)
Example the_high_end_is_thousands_and_the_low_end_is_hundreds :
  andb (andb (Nat.leb 1000 (verify_calls_at_most shake_256s))
             (Nat.ltb (verify_calls_at_most shake_256s) 10000))
       (Nat.ltb (verify_calls_at_least shake_256s) 1000) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_forty_seven_byte_digest_is_the_only_call_that_is_not_n_bytes :
  andb (Nat.eqb (digest_bytes shake_256s) 47)
       (negb (Nat.eqb (digest_bytes shake_256s) (hash_bytes shake_256s))) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The verifier as a record of what it has: R-09-005's fixed-layout header
   and its order, R-09-005's floor check, R-09-036's lifecycle-diversified
   roots, and R-05-058c's hash-only ground.
   ------------------------------------------------------------------------- *)

Inductive Prim : Type :=
| Shake256
| Ntt
| MatrixExpansion
| RejectionSampler
| HintDecoder.

Definition prim_eqb (a b : Prim) : bool :=
  match a, b with
  | Shake256, Shake256 => true
  | Ntt, Ntt => true
  | MatrixExpansion, MatrixExpansion => true
  | RejectionSampler, RejectionSampler => true
  | HintDecoder, HintDecoder => true
  | _, _ => false
  end.

Definition all_prims : list Prim :=
  Shake256 :: Ntt :: MatrixExpansion :: RejectionSampler :: HintDecoder :: nil.

(* The four R-05-058c names beside the hash, which is what makes a verifier
   a lattice one. *)
Definition lattice_prims : list Prim :=
  Ntt :: MatrixExpansion :: RejectionSampler :: HintDecoder :: nil.

Inductive Role : Type :=
| MessageDigest
| ChainStep
| TreeNode
| LeafCompression
| RootCompression.

Record Call : Type := {
  call_prim : Prim;
  call_role : Role;
  call_out_bits : nat
}.

Inductive Phase : Type :=
| ReadHeader
| CheckFloor
| VerifySignature
| Measure
| Execute.

Definition phase_eqb (a b : Phase) : bool :=
  match a, b with
  | ReadHeader, ReadHeader => true
  | CheckFloor, CheckFloor => true
  | VerifySignature, VerifySignature => true
  | Measure, Measure => true
  | Execute, Execute => true
  | _, _ => false
  end.

Definition all_phases : list Phase :=
  ReadHeader :: CheckFloor :: VerifySignature :: Measure :: Execute :: nil.

Inductive Lifecycle : Type :=
| Raw
| TestState
| Development
| Production
| Rma.

Definition all_lifecycles : list Lifecycle :=
  Raw :: TestState :: Development :: Production :: Rma :: nil.

Inductive Root : Type :=
| ProductionRoot
| DevelopmentRoot
| TestRoot
| EngineeringRoot.

Definition root_eqb (a b : Root) : bool :=
  match a, b with
  | ProductionRoot, ProductionRoot => true
  | DevelopmentRoot, DevelopmentRoot => true
  | TestRoot, TestRoot => true
  | EngineeringRoot, EngineeringRoot => true
  | _, _ => false
  end.

Definition all_roots : list Root :=
  ProductionRoot :: DevelopmentRoot :: TestRoot :: EngineeringRoot :: nil.

(* R-09-005's fixed-layout, length-bounded header. A field is an offset and
   a length, both constants, which is the whole of what fixed-layout means
   here: no field's position is read from any other field's value, because
   a `nat` has nowhere to read one from. *)
Record HeaderField : Type := {
  field_offset : nat;
  field_length : nat
}.

Record Header : Type := {
  image_offset : HeaderField;
  image_length : HeaderField;
  image_hash : HeaderField;
  image_signature : HeaderField;
  header_bytes : nat
}.

Definition header_fields (hd : Header) : list HeaderField :=
  image_offset hd :: image_length hd :: image_hash hd :: image_signature hd :: nil.

Definition field_ends (f : HeaderField) : nat := field_offset f + field_length f.

Fixpoint fields_ascend (l : list HeaderField) : bool :=
  match l with
  | nil => true
  | f :: rest =>
      match rest with
      | nil => true
      | g :: _ => andb (Nat.leb (field_ends f) (field_offset g)) (fields_ascend rest)
      end
  end.

Definition header_is_fixed_layout (hd : Header) : bool :=
  andb (fields_ascend (header_fields hd))
  (andb (all_of (fun f => Nat.leb (field_ends f) (header_bytes hd)) (header_fields hd))
        (all_of (fun f => Nat.ltb 0 (field_length f)) (header_fields hd))).

Definition signature_field_holds_the_scheme (p : ParameterSet) (hd : Header) : bool :=
  Nat.eqb (field_length (image_signature hd)) (signature_bytes p).

Record RomVerifier : Type := {
  parameters : ParameterSet;
  header : Header;
  order : list Phase;
  calls : list Call;
  accepted_roots : Lifecycle -> list Root;
  rollback_floor : nat
}.

(* The three decidable equalities are decided rather than assumed: each is
   reflexive on every constructor of its own type and false on every
   distinct pair of them, over the whole enumeration in both directions. A
   diagonal arm nobody exercises is a comparison that quietly answers false
   of a thing and itself. *)
Definition eqb_decides {A : Type} (eqb : A -> A -> bool) (l : list A) : bool :=
  all_of (fun x => andb (eqb x x)
                        (Nat.eqb (count_where (eqb x) l) 1)) l.

Example the_three_equalities_decide_their_own_enumerations :
  andb (eqb_decides prim_eqb all_prims)
  (andb (eqb_decides phase_eqb all_phases)
        (eqb_decides root_eqb all_roots)) = true.
Proof. vm_compute. reflexivity. Qed.

Definition admits_version (v : RomVerifier) (version : nat) : bool :=
  Nat.leb (rollback_floor v) version.

(* R-05-058c: every primitive the verifier reaches is the hash. *)
Definition hash_only_b (v : RomVerifier) : bool :=
  all_of (fun c => prim_eqb (call_prim c) Shake256) (calls v).

Definition HashOnly (v : RomVerifier) : Prop := hash_only_b v = true.

(* R-09-005: the order is the five phases once each, the floor check and
   the signature check and the measurement all before execution. *)
Definition order_is_fixed_b (v : RomVerifier) : bool :=
  andb (all_of (fun ph => occurs_once phase_eqb ph (order v)) all_phases)
  (andb (Nat.eqb (length_of (order v)) 5)
  (andb (precedes_in phase_eqb ReadHeader Execute (order v))
  (andb (precedes_in phase_eqb CheckFloor Execute (order v))
  (andb (precedes_in phase_eqb VerifySignature Execute (order v))
        (precedes_in phase_eqb Measure Execute (order v)))))).

(* R-09-036: in production the accepted set is the production root alone. *)
Definition production_accepts_one_root_b (v : RomVerifier) : bool :=
  andb (Nat.eqb (length_of (accepted_roots v Production)) 1)
       (all_of (fun r => root_eqb r ProductionRoot) (accepted_roots v Production)).

Definition floor_is_set_b (v : RomVerifier) : bool := Nat.ltb 0 (rollback_floor v).

Definition header_is_well_formed_b (v : RomVerifier) : bool :=
  andb (header_is_fixed_layout (header v))
       (signature_field_holds_the_scheme (parameters v) (header v)).

Definition admissible_b (v : RomVerifier) : bool :=
  andb (hash_only_b v)
  (andb (order_is_fixed_b v)
  (andb (production_accepts_one_root_b v)
  (andb (floor_is_set_b v)
        (header_is_well_formed_b v)))).

Definition Admissible (v : RomVerifier) : Prop := admissible_b v = true.

(* -------------------------------------------------------------------------
   What is stated of an arbitrary verifier and an arbitrary version.
   ------------------------------------------------------------------------- *)

Theorem a_version_below_the_floor_is_refused :
  forall (v : RomVerifier) (version : nat),
    Nat.ltb version (rollback_floor v) = true -> admits_version v version = false.
Proof.
  intros v version H. unfold admits_version. apply leb_false_of_ltb. exact H.
Qed.

Theorem an_admissible_verifier_reaches_nothing_but_the_hash :
  forall v : RomVerifier, Admissible v -> HashOnly v.
Proof.
  intros v H. unfold Admissible, admissible_b in H. unfold HashOnly.
  apply andb_left in H. exact H.
Qed.

Theorem an_admissible_verifier_measures_before_it_executes :
  forall v : RomVerifier,
    Admissible v -> precedes_in phase_eqb Measure Execute (order v) = true.
Proof.
  intros v H. unfold Admissible, admissible_b in H.
  apply andb_right in H. apply andb_left in H.
  unfold order_is_fixed_b in H.
  apply andb_right in H. apply andb_right in H. apply andb_right in H.
  apply andb_right in H. apply andb_right in H. exact H.
Qed.

Theorem an_admissible_verifier_verifies_before_it_executes :
  forall v : RomVerifier,
    Admissible v -> precedes_in phase_eqb VerifySignature Execute (order v) = true.
Proof.
  intros v H. unfold Admissible, admissible_b in H.
  apply andb_right in H. apply andb_left in H.
  unfold order_is_fixed_b in H.
  apply andb_right in H. apply andb_right in H. apply andb_right in H.
  apply andb_right in H. apply andb_left in H. exact H.
Qed.

Theorem an_admissible_verifier_checks_the_floor_before_it_executes :
  forall v : RomVerifier,
    Admissible v -> precedes_in phase_eqb CheckFloor Execute (order v) = true.
Proof.
  intros v H. unfold Admissible, admissible_b in H.
  apply andb_right in H. apply andb_left in H.
  unfold order_is_fixed_b in H.
  apply andb_right in H. apply andb_right in H. apply andb_right in H.
  apply andb_left in H. exact H.
Qed.

Theorem an_admissible_verifier_sizes_its_signature_field_to_its_parameter_set :
  forall v : RomVerifier,
    Admissible v ->
    Nat.eqb (field_length (image_signature (header v))) (signature_bytes (parameters v)) = true.
Proof.
  intros v H. unfold Admissible, admissible_b in H.
  apply andb_right in H. apply andb_right in H. apply andb_right in H.
  apply andb_right in H. unfold header_is_well_formed_b in H.
  apply andb_right in H. exact H.
Qed.

(* -------------------------------------------------------------------------
   The witness, and the five constructions the predicate refuses.
   ------------------------------------------------------------------------- *)

Definition demo_header : Header :=
  {| image_offset := {| field_offset := 0; field_length := 8 |};
     image_length := {| field_offset := 8; field_length := 8 |};
     image_hash := {| field_offset := 16; field_length := hash_bytes shake_256s |};
     image_signature := {| field_offset := 48;
                           field_length := signature_bytes shake_256s |};
     header_bytes := 48 + signature_bytes shake_256s |}.

Definition spec_order : list Phase :=
  ReadHeader :: CheckFloor :: VerifySignature :: Measure :: Execute :: nil.

Definition hash_call (r : Role) (bits : nat) : Call :=
  {| call_prim := Shake256; call_role := r; call_out_bits := bits |}.

Definition spec_calls : list Call :=
  hash_call MessageDigest (8 * digest_bytes shake_256s)
  :: hash_call ChainStep (8 * hash_bytes shake_256s)
  :: hash_call TreeNode (8 * hash_bytes shake_256s)
  :: hash_call LeafCompression (8 * hash_bytes shake_256s)
  :: hash_call RootCompression (8 * hash_bytes shake_256s)
  :: nil.

Definition spec_roots (l : Lifecycle) : list Root :=
  match l with
  | Production => ProductionRoot :: nil
  | Development => DevelopmentRoot :: nil
  | TestState => TestRoot :: nil
  | Rma => DevelopmentRoot :: nil
  | Raw => nil
  end.

Definition demo : RomVerifier :=
  {| parameters := shake_256s;
     header := demo_header;
     order := spec_order;
     calls := spec_calls;
     accepted_roots := spec_roots;
     rollback_floor := 1 |}.

Example the_witness_is_admissible : Admissible demo.
Proof. vm_compute. reflexivity. Qed.

Example the_witness_reaches_five_calls_and_every_one_is_the_hash :
  andb (Nat.eqb (length_of (calls demo)) 5) (hash_only_b demo) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_witness_refuses_a_version_below_its_floor :
  andb (negb (admits_version demo 0)) (admits_version demo 1) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_witness_accepts_no_engineering_root_in_any_state :
  all_of (fun l => negb (any_of (fun r => root_eqb r EngineeringRoot) (accepted_roots demo l)))
         all_lifecycles = true.
Proof. vm_compute. reflexivity. Qed.

(* One: R-05-058c's refused shape, a ROM-resident lattice verifier. Its four
   primitives are the four that entry names beside the hash. *)
Definition with_a_lattice_verifier : RomVerifier :=
  {| parameters := parameters demo;
     header := header demo;
     order := order demo;
     calls := calls demo
              ++ map_over (fun q => {| call_prim := q; call_role := ChainStep;
                                       call_out_bits := 8 * hash_bytes shake_256s |})
                          lattice_prims;
     accepted_roots := accepted_roots demo;
     rollback_floor := rollback_floor demo |}.

Example the_lattice_verifier_is_refused : admissible_b with_a_lattice_verifier = false.
Proof. vm_compute. reflexivity. Qed.

Example the_lattice_verifier_keeps_every_clause_but_the_hash_only_one :
  andb (andb (order_is_fixed_b with_a_lattice_verifier)
             (production_accepts_one_root_b with_a_lattice_verifier))
  (andb (andb (floor_is_set_b with_a_lattice_verifier)
              (header_is_well_formed_b with_a_lattice_verifier))
        (negb (hash_only_b with_a_lattice_verifier))) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_lattice_verifier_carries_all_four_of_the_entrys_names :
  all_of (fun q => any_of (fun c => prim_eqb (call_prim c) q) (calls with_a_lattice_verifier))
         lattice_prims = true.
Proof. vm_compute. reflexivity. Qed.

(* Two: a verifier that executes before it is measured. It still verifies
   the signature first, which is what makes the measurement's own clause
   the single difference. *)
Definition executing_before_it_is_measured : RomVerifier :=
  {| parameters := parameters demo;
     header := header demo;
     order := ReadHeader :: CheckFloor :: VerifySignature :: Execute :: Measure :: nil;
     calls := calls demo;
     accepted_roots := accepted_roots demo;
     rollback_floor := rollback_floor demo |}.

Example the_unmeasured_verifier_is_refused :
  admissible_b executing_before_it_is_measured = false.
Proof. vm_compute. reflexivity. Qed.

Example the_unmeasured_verifier_still_verifies_first :
  andb (andb (precedes_in phase_eqb VerifySignature Execute
                          (order executing_before_it_is_measured))
             (precedes_in phase_eqb CheckFloor Execute
                          (order executing_before_it_is_measured)))
       (negb (precedes_in phase_eqb Measure Execute
                          (order executing_before_it_is_measured))) = true.
Proof. vm_compute. reflexivity. Qed.

(* Three: a verifier whose order drops the floor check. Every other phase
   is in place and each occurs once. *)
Definition with_no_floor_check : RomVerifier :=
  {| parameters := parameters demo;
     header := header demo;
     order := ReadHeader :: VerifySignature :: Measure :: Execute :: nil;
     calls := calls demo;
     accepted_roots := accepted_roots demo;
     rollback_floor := rollback_floor demo |}.

Example the_verifier_with_no_floor_check_is_refused :
  admissible_b with_no_floor_check = false.
Proof. vm_compute. reflexivity. Qed.

Example the_verifier_with_no_floor_check_still_measures_first :
  andb (precedes_in phase_eqb Measure Execute (order with_no_floor_check))
       (negb (precedes_in phase_eqb CheckFloor Execute (order with_no_floor_check))) = true.
Proof. vm_compute. reflexivity. Qed.

(* Four: R-09-036's refused shape, a production part that also accepts a
   development root. It accepts the production root too, which is why the
   set's size and not its membership is what catches it. *)
Definition accepting_a_development_root_in_production : RomVerifier :=
  {| parameters := parameters demo;
     header := header demo;
     order := order demo;
     calls := calls demo;
     accepted_roots := fun l => match l with
                                | Production => ProductionRoot :: DevelopmentRoot :: nil
                                | other => spec_roots other
                                end;
     rollback_floor := rollback_floor demo |}.

Example the_widened_root_set_is_refused :
  admissible_b accepting_a_development_root_in_production = false.
Proof. vm_compute. reflexivity. Qed.

Example the_widened_root_set_still_accepts_the_production_root :
  andb (any_of (fun r => root_eqb r ProductionRoot)
               (accepted_roots accepting_a_development_root_in_production Production))
       (negb (production_accepts_one_root_b accepting_a_development_root_in_production))
  = true.
Proof. vm_compute. reflexivity. Qed.

(* Five: a header whose signature field is sized at the public key's size,
   which is the transcription defect of reading Table 2's two size columns
   the wrong way round. The layout is still fixed and still bounded. *)
Definition signature_field_sized_at_the_public_key : RomVerifier :=
  {| parameters := parameters demo;
     header := {| image_offset := image_offset demo_header;
                  image_length := image_length demo_header;
                  image_hash := image_hash demo_header;
                  image_signature := {| field_offset := 48;
                                        field_length := public_key_bytes shake_256s |};
                  header_bytes := 48 + public_key_bytes shake_256s |};
     order := order demo;
     calls := calls demo;
     accepted_roots := accepted_roots demo;
     rollback_floor := rollback_floor demo |}.

Example the_undersized_signature_field_is_refused :
  admissible_b signature_field_sized_at_the_public_key = false.
Proof. vm_compute. reflexivity. Qed.

Example the_undersized_signature_field_is_still_a_fixed_layout :
  andb (header_is_fixed_layout (header signature_field_sized_at_the_public_key))
       (negb (signature_field_holds_the_scheme
                (parameters signature_field_sized_at_the_public_key)
                (header signature_field_sized_at_the_public_key))) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   Three headers that break one clause of the layout each, and two verifiers
   that break one clause of the predicate each, so that every conjunct above
   is decided by something rather than carried by the conjunct beside it.
   Each is the witness with one field moved.
   ------------------------------------------------------------------------- *)

Definition header_with (sig_field : HeaderField) (bytes : nat) : Header :=
  {| image_offset := image_offset demo_header;
     image_length := image_length demo_header;
     image_hash := image_hash demo_header;
     image_signature := sig_field;
     header_bytes := bytes |}.

(* One: the signature field starts inside the hash field, so the fields do
   not ascend. It is still inside the header's own length and still sized to
   the scheme. *)
Definition header_whose_fields_overlap : Header :=
  header_with {| field_offset := 40; field_length := signature_bytes shake_256s |}
              (48 + signature_bytes shake_256s).

(* Two: the signature field runs past the header's declared length, which is
   the length bound R-09-005 asks for. The fields still ascend. *)
Definition header_running_past_its_length : Header :=
  header_with {| field_offset := 48; field_length := signature_bytes shake_256s |}
              (48 + signature_bytes shake_256s - 1).

(* Three: a field of no length at all, which ascends and stays inside the
   bound and names nothing. *)
Definition header_with_an_empty_field : Header :=
  {| image_offset := image_offset demo_header;
     image_length := {| field_offset := 8; field_length := 0 |};
     image_hash := image_hash demo_header;
     image_signature := image_signature demo_header;
     header_bytes := header_bytes demo_header |}.

Example each_broken_header_breaks_exactly_the_clause_it_exists_for :
  andb (andb (negb (fields_ascend (header_fields header_whose_fields_overlap)))
             (all_of (fun f => Nat.leb (field_ends f) (header_bytes header_whose_fields_overlap))
                     (header_fields header_whose_fields_overlap)))
  (andb (andb (fields_ascend (header_fields header_running_past_its_length))
              (negb (all_of (fun f => Nat.leb (field_ends f)
                                              (header_bytes header_running_past_its_length))
                            (header_fields header_running_past_its_length))))
        (andb (fields_ascend (header_fields header_with_an_empty_field))
              (negb (all_of (fun f => Nat.ltb 0 (field_length f))
                            (header_fields header_with_an_empty_field))))) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_three_broken_headers_are_refused_and_the_witness_is_not :
  andb (header_is_fixed_layout demo_header)
  (andb (negb (header_is_fixed_layout header_whose_fields_overlap))
  (andb (negb (header_is_fixed_layout header_running_past_its_length))
        (negb (header_is_fixed_layout header_with_an_empty_field)))) = true.
Proof. vm_compute. reflexivity. Qed.

Example each_broken_header_still_sizes_its_signature_field_to_the_scheme :
  andb (signature_field_holds_the_scheme shake_256s header_whose_fields_overlap)
  (andb (signature_field_holds_the_scheme shake_256s header_running_past_its_length)
        (signature_field_holds_the_scheme shake_256s header_with_an_empty_field)) = true.
Proof. vm_compute. reflexivity. Qed.

(* Four: a production part whose accepted set has one member and it is the
   wrong one, which is what separates the set's size from its membership. *)
Definition accepting_one_wrong_root_in_production : RomVerifier :=
  {| parameters := parameters demo;
     header := header demo;
     order := order demo;
     calls := calls demo;
     accepted_roots := fun l => match l with
                                | Production => DevelopmentRoot :: nil
                                | other => spec_roots other
                                end;
     rollback_floor := rollback_floor demo |}.

Example one_wrong_root_is_refused_though_the_set_is_still_a_singleton :
  andb (Nat.eqb (length_of (accepted_roots accepting_one_wrong_root_in_production Production)) 1)
       (negb (admissible_b accepting_one_wrong_root_in_production)) = true.
Proof. vm_compute. reflexivity. Qed.

(* Five: a verifier with no floor at all, which keeps the floor check in its
   order and admits every version there is. *)
Definition with_the_floor_at_zero : RomVerifier :=
  {| parameters := parameters demo;
     header := header demo;
     order := order demo;
     calls := calls demo;
     accepted_roots := accepted_roots demo;
     rollback_floor := 0 |}.

Example a_floor_of_zero_is_refused_and_admits_every_version :
  andb (andb (negb (admissible_b with_the_floor_at_zero))
             (precedes_in phase_eqb CheckFloor Execute (order with_the_floor_at_zero)))
       (andb (admits_version with_the_floor_at_zero 0)
             (hash_only_b with_the_floor_at_zero)) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_witness_and_its_order_place_every_phase_where_the_entry_wants_it :
  andb (andb (Nat.eqb (index_of phase_eqb ReadHeader spec_order) 0)
             (Nat.eqb (index_of phase_eqb Execute spec_order) 4))
       (andb (negb (precedes_in phase_eqb Execute Execute spec_order))
             (negb (precedes_in phase_eqb Execute ReadHeader spec_order))) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The R-05-163 assumption gate reads this block. Every shipped constant is
   enumerated from its own proof term and held against the declared set: the
   one Require above is a sibling under proofs/ that Requires nothing, so
   there is no Admitted, no Axiom and no top-level Parameter reachable, and
   nothing is declared inside the development to make the gate pass.
   ------------------------------------------------------------------------- *)

Print Assumptions ceil_div.
Print Assumptions digits_base.
Print Assumptions index_from.
Print Assumptions index_of.
Print Assumptions precedes_in.
Print Assumptions occurs_once.
Print Assumptions any_of.
Print Assumptions the_ceiling_rounds_up_where_the_division_does_not_divide.
Print Assumptions a_value_equal_to_the_base_takes_two_digits.
Print Assumptions leb_false_of_ltb.
Print Assumptions andb_left.
Print Assumptions andb_right.
Print Assumptions ParameterSet.
Print Assumptions winternitz.
Print Assumptions message_len.
Print Assumptions checksum_len.
Print Assumptions chain_count.
Print Assumptions digest_bytes.
Print Assumptions public_key_bytes.
Print Assumptions signature_bytes.
Print Assumptions shake_256s.
Print Assumptions the_table_row_agrees_with_the_height_it_implies.
Print Assumptions the_two_winternitz_lengths_are_sixty_four_and_three.
Print Assumptions the_chain_count_is_sixty_seven.
Print Assumptions the_message_digest_is_the_published_forty_seven_bytes.
Print Assumptions the_public_key_is_the_published_sixty_four_bytes.
Print Assumptions the_signature_is_the_published_twenty_nine_thousand_seven_hundred_and_ninety_two_bytes.
Print Assumptions the_signature_is_tens_of_kilobytes.
Print Assumptions the_signature_is_four_hundred_and_sixty_five_times_the_public_key_and_a_half.
Print Assumptions the_maximum_checksum_takes_three_base_sixteen_digits.
Print Assumptions shake_128s.
Print Assumptions shake_128f.
Print Assumptions shake_192s.
Print Assumptions shake_192f.
Print Assumptions shake_256f.
Print Assumptions shake_sets.
Print Assumptions the_six_rows_derive_their_published_message_digest_lengths.
Print Assumptions the_six_rows_derive_their_published_public_key_sizes.
Print Assumptions the_six_rows_derive_their_published_signature_sizes.
Print Assumptions every_rows_subtree_height_is_its_own_quotient.
Print Assumptions every_rows_checksum_takes_three_digits.
Print Assumptions the_six_rows_derive_their_chain_counts.
Print Assumptions the_frozen_row_is_the_one_the_suite_names.
Print Assumptions address_bytes.
Print Assumptions h_msg.
Print Assumptions prf.
Print Assumptions prf_in_its_argument_order.
Print Assumptions prf_msg.
Print Assumptions f_chain.
Print Assumptions h_node.
Print Assumptions t_compress.
Print Assumptions f_without_its_address.
Print Assumptions the_chain_the_node_and_the_compression_are_one_function.
Print Assumptions the_address_free_hash_ignores_its_address.
Print Assumptions demo_seed.
Print Assumptions demo_message.
Print Assumptions demo_address_one.
Print Assumptions demo_address_two.
Print Assumptions the_addresses_are_the_standards_thirty_two_bytes.
Print Assumptions the_seed_and_the_message_are_n_bytes.
Print Assumptions the_two_addresses_differ_in_one_byte.
Print Assumptions the_six_functions_return_the_lengths_the_standard_fixes.
Print Assumptions two_addresses_separate_the_same_message.
Print Assumptions the_argument_ordered_prf_misses_the_standards_answer.
Print Assumptions the_argument_ordered_prf_agrees_where_the_two_tails_coincide.
Print Assumptions the_address_free_hash_collapses_the_two_addresses.
Print Assumptions fors_calls.
Print Assumptions chain_steps_at_most.
Print Assumptions chain_steps_at_least.
Print Assumptions layer_calls.
Print Assumptions verify_calls.
Print Assumptions verify_calls_at_most.
Print Assumptions verify_calls_at_least.
Print Assumptions the_census_runs_from_seven_hundred_and_sixty_four_to_eight_thousand_four_hundred_and_forty_four.
Print Assumptions the_high_end_is_thousands_and_the_low_end_is_hundreds.
Print Assumptions the_forty_seven_byte_digest_is_the_only_call_that_is_not_n_bytes.
Print Assumptions Prim.
Print Assumptions prim_eqb.
Print Assumptions all_prims.
Print Assumptions lattice_prims.
Print Assumptions Role.
Print Assumptions Call.
Print Assumptions Phase.
Print Assumptions phase_eqb.
Print Assumptions all_phases.
Print Assumptions Lifecycle.
Print Assumptions all_lifecycles.
Print Assumptions Root.
Print Assumptions root_eqb.
Print Assumptions all_roots.
Print Assumptions HeaderField.
Print Assumptions Header.
Print Assumptions header_fields.
Print Assumptions field_ends.
Print Assumptions fields_ascend.
Print Assumptions header_is_fixed_layout.
Print Assumptions signature_field_holds_the_scheme.
Print Assumptions RomVerifier.
Print Assumptions eqb_decides.
Print Assumptions the_three_equalities_decide_their_own_enumerations.
Print Assumptions admits_version.
Print Assumptions hash_only_b.
Print Assumptions HashOnly.
Print Assumptions order_is_fixed_b.
Print Assumptions production_accepts_one_root_b.
Print Assumptions floor_is_set_b.
Print Assumptions header_is_well_formed_b.
Print Assumptions admissible_b.
Print Assumptions Admissible.
Print Assumptions a_version_below_the_floor_is_refused.
Print Assumptions an_admissible_verifier_reaches_nothing_but_the_hash.
Print Assumptions an_admissible_verifier_measures_before_it_executes.
Print Assumptions an_admissible_verifier_verifies_before_it_executes.
Print Assumptions an_admissible_verifier_checks_the_floor_before_it_executes.
Print Assumptions an_admissible_verifier_sizes_its_signature_field_to_its_parameter_set.
Print Assumptions demo_header.
Print Assumptions spec_order.
Print Assumptions hash_call.
Print Assumptions spec_calls.
Print Assumptions spec_roots.
Print Assumptions demo.
Print Assumptions the_witness_is_admissible.
Print Assumptions the_witness_reaches_five_calls_and_every_one_is_the_hash.
Print Assumptions the_witness_refuses_a_version_below_its_floor.
Print Assumptions the_witness_accepts_no_engineering_root_in_any_state.
Print Assumptions with_a_lattice_verifier.
Print Assumptions the_lattice_verifier_is_refused.
Print Assumptions the_lattice_verifier_keeps_every_clause_but_the_hash_only_one.
Print Assumptions the_lattice_verifier_carries_all_four_of_the_entrys_names.
Print Assumptions executing_before_it_is_measured.
Print Assumptions the_unmeasured_verifier_is_refused.
Print Assumptions the_unmeasured_verifier_still_verifies_first.
Print Assumptions with_no_floor_check.
Print Assumptions the_verifier_with_no_floor_check_is_refused.
Print Assumptions the_verifier_with_no_floor_check_still_measures_first.
Print Assumptions accepting_a_development_root_in_production.
Print Assumptions the_widened_root_set_is_refused.
Print Assumptions the_widened_root_set_still_accepts_the_production_root.
Print Assumptions signature_field_sized_at_the_public_key.
Print Assumptions the_undersized_signature_field_is_refused.
Print Assumptions the_undersized_signature_field_is_still_a_fixed_layout.
Print Assumptions header_with.
Print Assumptions header_whose_fields_overlap.
Print Assumptions header_running_past_its_length.
Print Assumptions header_with_an_empty_field.
Print Assumptions each_broken_header_breaks_exactly_the_clause_it_exists_for.
Print Assumptions the_three_broken_headers_are_refused_and_the_witness_is_not.
Print Assumptions each_broken_header_still_sizes_its_signature_field_to_the_scheme.
Print Assumptions accepting_one_wrong_root_in_production.
Print Assumptions one_wrong_root_is_refused_though_the_set_is_still_a_singleton.
Print Assumptions with_the_floor_at_zero.
Print Assumptions a_floor_of_zero_is_refused_and_admits_every_version.
Print Assumptions the_witness_and_its_order_place_every_phase_where_the_entry_wants_it.
