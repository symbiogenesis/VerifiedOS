(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   Keccak.v

   The Keccak-*p*[1600] permutation, the sponge over it, and the six FIPS 202
   functions SHA3-224, SHA3-256, SHA3-384, SHA3-512, SHAKE128 and SHAKE256,
   written in Gallina against FIPS 202 and checked against the standard's own
   published known answers.

   What this file is, and what it is not. It is a **functional reference**: a
   second transcription of FIPS 202, deliberately made against the same
   standard and the same published answers as the Sail unit in
   model/model/extensions/keccak/keccak_p1600.sail, so that the two
   transcriptions are a differential pair rather than two independent chances
   to be wrong. It is not a discharge of R-15-058, whose subject is the Sail
   invariant; it is not an implementation, and no binary corresponds to it.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. Nothing here executes on either
   emulator. The computed checks are decided inside the kernel, the light ones
   by conversion in the silent `Example ... := eq_refl` form and the ones that
   run a permutation by the bytecode machine, which contributes nothing to the
   Print Assumptions block at the end.

   The three assurance layers, and which one this is. R-05-059 wants
   functional correctness, constant-time and reduction-level security per
   primitive, and what is here is the **functional layer alone**. No
   constant-time property is claimed: R-05-062 and R-05-067 put that
   obligation on a binary as a 2-safety hyperproperty, a Gallina reference is
   not a binary, and the fact that every value-dependent operation below is
   xorb, andb, negb or a rotation by a table constant is a remark about the
   shape and never evidence. No reduction and no distributional claim is made
   either: R-05-077a's reduction is stated over uniformly drawn keys and
   nonces, and a functional reference carries no distribution of any kind. So
   nothing here is a shipped primitive under R-05-059.

   No Require. Nothing beyond the Rocq prelude is reachable, so there is no Z,
   no N, no String and no List library: `map`, `nth`, `firstn`, `skipn`,
   `seq`, `rev`, `repeat`, `fold_left` and `concat` are authored below in the
   idiom DischargeSequence.v authors `map_over`, `all_of` and `upto` in, and a
   64-bit lane is a `list bool` rather than a machine integer. An assumption
   reachable through an import is an assumption inside the R-05-163 gate's
   reach, which is what that rule buys and what a convenience import would
   spend.

   The representation, which no register entry fixes and which is therefore a
   reading of this file rather than a transcription of the register:

   1. A lane is `list bool` of length 64, indexed by FIPS 202's *z* with the
      **least significant bit at the head**, so the head of a lane is z = 0.
   2. The state is a 25-element `list word` flattened as *x* + 5*y*, which is
      the flattening keccak_p1600.sail states and the order FIPS 202's own
      string-to-state conversion puts the lanes in, so element *i* is lane *i*
      in both files with no reordering anywhere.
   3. A bit string is the concatenation of the lanes in that order, which is
      FIPS 202 s3.1.2 read backwards, and a byte of a squeezed output is eight
      consecutive bits with the head as the byte's least significant bit,
      which is FIPS 202 sB.1. That is why the known answers below read as the
      published hexadecimal, digit pair by digit pair, with no reversal.
   4. Every message here is byte-aligned, so no sub-byte convention is
      exercised and none is claimed.

   A flat 1600-bit list is the arm not taken. It would make `nth_of` linear in
   1600 at every lane read and the known-answer checks quadratic and unusable,
   and it buys nothing the 25-lane list does not already give.

   The readings of the register this file takes:

   1. **R-15-058's subject is the Sail invariant, not this file.** The entry
      makes the fixed-permutation invariant a fresh Sail statement disciplined
      against FIPS 202 and the NIST ACVP vectors, with software Keccak as the
      portable path and the differential reference. What is here is a second
      transcription of the same standard against the same published answers,
      which is what makes the pair a pair. Nothing here closes that entry.
   2. **The oracle enters no trust base.** Every published answer below is a
      constant inside an `Example`'s own statement, never a `Definition`, and
      nothing above it depends on the answer being right: what a known-answer
      check buys is that the constant and the transcription were produced by
      different routes. Putting an answer in a `Definition` would also put it
      inside the seeded-mutation population, where a constant moved off by one
      would score as a kill of the oracle rather than of the subject.
   3. **The five step mappings are the standard's own, by the standard's own
      names, in the standard's own order, and unfused**: theta, rho, pi, chi,
      iota, one definition each, composed once in `keccak_round`. R-15-056's
      acceptance names them that way and the shape is what the entry buys.
   4. **The rho offsets and the round constants are derived here and
      transcribed there.** keccak_p1600.sail writes both tables out, on the
      ground that a reader checks a written row against the published one.
      This file instead derives the offsets from FIPS 202's own (t+1)(t+2)/2
      triangular recurrence over the (x, y) walk and the constants from
      Algorithm 5's linear-feedback shift register, and then computes that
      what it derived equals what the standard publishes. That is what makes
      the pair a differential pair rather than a copy, and it is the pair that
      would have caught both of the defects the Sail unit's own known-answer
      vectors found: a mod-5 arm written one row early, and a table read in
      the wrong direction.
   5. **Keccak-p[1600, n] is the last n rounds** (FIPS 202 s3.3, R-15-056a),
      so `round_indices` is a suffix of the round-index list and the twelve-
      round form is rounds 12 through 23 of the same constant table. That is
      stated here as a theorem over an arbitrary state and an arbitrary round
      count rather than as a known-answer check, because it is the one thing
      about R-15-056a a round-count argument cannot show and the one thing a
      published answer for the short form would show only at one input.
   6. **What "permutation" means in R-15-056, and how much of it is
      discharged.** The entry's acceptance calls Keccak-f a permutation, which
      is a bijection on the 1600-bit state. This file discharges three
      quarters of that and says so: pi is a bijection on the twenty-five
      lanes, and its inverse recovers an arbitrary state; every rotation the
      rho table actually uses is invertible on an arbitrary sixty-four-bit
      word; iota is an involution over an arbitrary constant and an arbitrary
      lane; and chi is a bijection on an arbitrary row of five bits, checked
      over all thirty-two rows. **Theta's invertibility is not stated here.**
      It is a linear map on the 320-bit column-parity space whose inverse is
      dense, and no prelude-only argument for it fits in this item; the gap is
      named rather than papered over, and the composite claim that Keccak-p is
      a bijection is therefore an obligation this file states and does not
      close.
   7. **The domain separators decide, and no known answer says so.** SHA3-256
      and SHAKE256 have the same rate and the same capacity and differ only in
      the suffix appended before the padding, so the property that separates
      them is that they disagree, and the refutation is a construction with no
      separator at all under which they agree. A missing suffix is the defect
      no digest vector names, because a wrong digest and a wrong domain read
      alike.

   Where this file sits in the boot chain, which is why it is the half of
   M3.4a that was authored. R-05-058c splits the signature schemes by verifier
   and puts SLH-DSA at every ROM-verified object, R-05-058a freezes the
   parameter sets at Category 5 and names SLH-DSA-SHAKE-256s, and a hash-based
   signature is a construction over an extendable-output function and nothing
   else. So the ROM verifier's whole substrate is `shake256` below, **no
   classical signature appears in the frozen suite at all**, and the primitive
   that had to exist before anything above it could be assembled is this one.
   R-05-022's disposition for the pinned comparators is beside it and is the
   licence record's rather than this file's: an oracle is a behavioural
   comparator, it enters no trust base, and it is therefore not an interim
   anchor and carries no retirement rule.

   What is deliberately absent, with the entry that owes each decision. A
   register gap is reported, not closed:

   a. **No entry fixes the oracle pair for an authored SHA-3.** R-15-058 names
      FIPS 202 and the ACVP vectors for the Sail unit and names software
      Keccak as the reference; M3.4's own cell requires two oracles of
      independent verification lineage. Which two those are for this artifact
      is nobody's decision in the register. Owed at R-15-058 or in the plan.
   b. **No entry fixes the representation obligations above.** Word width and
      bit order, the lane flattening, the byte order of a squeezed output, and
      whether a Gallina reference is inside any acceptance at all are readings
      of this file and nothing else.
   c. **RotFirmware.v's `extend_separates` is not realized here.** That
      Machine field asks a hash to separate every pair of distinct inputs
      totally, and no function has that property, collisions existing;
      R-05-058c's hash-only assumption is computational. What M3.4a supplies
      is the function, and the field stays a declared Machine assumption.
      Owed at R-05-058c or R-09-002.
   d. **No AEAD, no DRBG and no signature is authored here.** R-15-241d's
      seeding discipline, its reseed bounds and its prediction- and
      backtracking-resistance clauses have no artifact in this repository and
      the DRBG this file does not author is where they would land; R-10-024
      freezes the cipher to AES-GCM where the plan's own sentence has both
      AEADs authored; and R-05-058c's split carries no classical scheme to
      author at all. All three are named as residue at checklist item M3.4c
      and are absent rather than implied.

   The literals taken from the standard, and there are no others. The 5 x 5 x
   64 geometry (`side`, `width`, `lanes`), the twenty-four and twelve round
   counts, the four SHA-3 output lengths and the two SHAKE security strengths,
   the capacity rule c = 2n, the two domain separators, the seven bit
   positions of Algorithm 6 and the eight-bit register and 255-step period of
   Algorithm 5. Everything else is derived: the rate is b minus the capacity,
   b is 25 lanes of 64 bits, the rho offsets are the recurrence's, the round
   constants are the register's, and every table's shape is `lanes` or `side`
   rather than 25 or 5 written again.

   Non-vacuity (R-05-165, R-05-166). Every structural obligation below is
   stated of an arbitrary table, word, state or construction and refuted of an
   alternative that the standard's own sentence excludes: a mod-5 arm written
   one row early, a rho recurrence started one step early, a constant table
   read in reverse, a first-twelve-rounds short form, a chi missing its own
   term, a pad that admits an empty block, a pad without its final one, and a
   sponge with no domain separator. Inhabitation is the published answers
   themselves, so no check below holds of everything and none holds of
   nothing.

   Where each published answer came from, which also discharges the
   acknowledgement condition the NIST terms state. The round-constant table,
   the rho offsets and both all-zero permutation states are read from
   `tests/TestVectors/KeccakF-1600-IntermediateValues.txt` in `XKCP/XKCP` at
   commit `eb5244d6`, on 2026-08-31. The digests and squeezed outputs are read
   from `tests/TestVectors/ShortMsgKAT_SHA3-224.txt` and its five siblings in
   the same tree at the same commit on the same date, which are the known-
   answer files NIST's own genKAT harness emits. The empty-message SHA3-256
   answer is the same one the NIST ACVP SHA3-256 sets carry for the same
   input, and it is the answer the Sail unit's own harness checks, which is
   where the two transcriptions meet.
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

(* The two out-of-range answers this file relies on, each named once so that
   the answer is a decision rather than a default repeated at twenty sites,
   and each pinned by an Example below rather than left unreachable. *)
Definition bit_at (l : list bool) (i : nat) : bool := nth_of i l false.

Definition offset_at (l : list nat) (i : nat) : nat := nth_of i l 0.

Fixpoint rev_onto {A : Type} (l acc : list A) : list A :=
  match l with nil => acc | x :: r => rev_onto r (x :: acc) end.

Definition rev_of {A : Type} (l : list A) : list A := rev_onto l nil.

Fixpoint repeat_of {A : Type} (n : nat) (x : A) : list A :=
  match n with 0 => nil | S k => x :: repeat_of k x end.

(* 0 through n-1, in that order. Built by a downward count rather than by
   appending one element at a time, an append per element being quadratic and
   this list being rebuilt inside every round. *)
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

(* -------------------------------------------------------------------------
   The geometry, which is FIPS 202's b = 1600 and nothing else.
   ------------------------------------------------------------------------- *)

Definition side : nat := 5.
Definition width : nat := 64.
Definition lanes : nat := side * side.
Definition b_bits : nat := lanes * width.

Definition word : Type := list bool.
Definition state : Type := list word.

Definition zero_word : word := repeat_of width false.
Definition zero_state : state := repeat_of lanes zero_word.

Fixpoint wxor (a b : word) : word :=
  match a with
  | nil => nil
  | x :: xs => match b with nil => nil | y :: ys => xorb x y :: wxor xs ys end
  end.

Fixpoint wand (a b : word) : word :=
  match a with
  | nil => nil
  | x :: xs => match b with nil => nil | y :: ys => andb x y :: wand xs ys end
  end.

Definition wnot (w : word) : word := map_over negb w.

(* A left rotation by r: the bit at z lands at z + r modulo the lane width,
   which is FIPS 202's A'[x, y, z] = A[x, y, (z - offset) mod w] read from the
   destination's side. *)
Definition rotl (r : nat) (w : word) : word :=
  let k := width - Nat.modulo r width in
  drop_of k w ++ take_of k w.

Definition idx (x y : nat) : nat := x + side * y.
Definition col_of (i : nat) : nat := Nat.modulo i side.
Definition row_of (i : nat) : nat := Nat.div i side.
Definition lane (a : state) (i : nat) : word := nth_of i a zero_word.

Definition next5 (x : nat) : nat := Nat.modulo (x + 1) side.
Definition prev5 (x : nat) : nat := Nat.modulo (x + side - 1) side.

Fixpoint set_bit (i : nat) (b : bool) (w : word) : word :=
  match w with
  | nil => nil
  | x :: r => match i with 0 => b :: r | S k => x :: set_bit k b r end
  end.

Fixpoint xor_at (i : nat) (b : bool) (l : list bool) : list bool :=
  match l with
  | nil => nil
  | x :: r => match i with 0 => xorb x b :: r | S k => x :: xor_at k b r end
  end.

Fixpoint set_lane (i : nat) (w : word) (a : state) : state :=
  match a with
  | nil => nil
  | x :: r => match i with 0 => w :: r | S k => x :: set_lane k w r end
  end.

(* -------------------------------------------------------------------------
   theta, FIPS 202 Algorithm 1, in its own three steps.
   ------------------------------------------------------------------------- *)

Definition theta_C (a : state) (x : nat) : word :=
  fold_over (fun acc y => wxor acc (lane a (idx x y))) zero_word (upto side).

Definition theta (a : state) : state :=
  let c := map_over (theta_C a) (upto side) in
  let d := map_over (fun x => wxor (nth_of (prev5 x) c zero_word)
                                   (rotl 1 (nth_of (next5 x) c zero_word)))
                    (upto side) in
  map_over (fun i => wxor (lane a i) (nth_of (col_of i) d zero_word)) (upto lanes).

(* -------------------------------------------------------------------------
   rho, FIPS 202 Algorithm 2. The offsets are **derived** from the standard's
   own walk rather than transcribed: start at (x, y) = (1, 0), give the lane
   reached at step t the offset (t+1)(t+2)/2 modulo the lane width, and step
   to (y, (2x + 3y) mod 5). Lane (0, 0) is never reached by the walk and its
   offset is zero, which is exactly what the lookup's default says.
   ------------------------------------------------------------------------- *)

Definition rho_step (p : nat * nat) : nat * nat :=
  pair (snd p) (Nat.modulo (2 * fst p + 3 * snd p) side).

Definition triangular (t : nat) : nat := Nat.div (S t * S (S t)) 2.

Fixpoint rho_walk (n t : nat) (p : nat * nat) : list (nat * nat) :=
  match n with
  | 0 => nil
  | S k => pair (idx (fst p) (snd p)) (Nat.modulo (triangular t) width)
           :: rho_walk k (S t) (rho_step p)
  end.

Definition rho_lookup (l : list (nat * nat)) (i : nat) : nat :=
  fold_over (fun acc e => if Nat.eqb (fst e) i then snd e else acc) 0 l.

Definition rho_table : list nat :=
  let walked := rho_walk (lanes - 1) 0 (pair 1 0) in
  map_over (rho_lookup walked) (upto lanes).

Definition rho (a : state) : state :=
  let t := rho_table in
  map_over (fun i => rotl (offset_at t i) (lane a i)) (upto lanes).

(* The same walk with the recurrence started one step early, which is the
   transcription defect a table of triangular numbers invites: the first lane
   the walk reaches then carries offset 0, which lane (0, 0) already carries,
   so the offsets stop being distinct. *)
Definition triangular_one_step_early (t : nat) : nat := Nat.div (t * S t) 2.

Fixpoint rho_walk_one_step_early (n t : nat) (p : nat * nat) : list (nat * nat) :=
  match n with
  | 0 => nil
  | S k => pair (idx (fst p) (snd p)) (Nat.modulo (triangular_one_step_early t) width)
           :: rho_walk_one_step_early k (S t) (rho_step p)
  end.

Definition rho_table_one_step_early : list nat :=
  let walked := rho_walk_one_step_early (lanes - 1) 0 (pair 1 0) in
  map_over (rho_lookup walked) (upto lanes).

(* -------------------------------------------------------------------------
   pi, FIPS 202 Algorithm 3, written in the standard's own source-indexed
   form: A'[x, y] = A[(x + 3y) mod 5, x]. keccak_p1600.sail writes the same
   step destination-indexed, sending lane (x, y) to (y, (2x + 3y) mod 5), and
   the two forms are checked against each other below. That second form is
   where the mod-5 argument reaches 20, which is where the Sail unit's own
   defect was.
   ------------------------------------------------------------------------- *)

Definition pi_source (i : nat) : nat :=
  idx (Nat.modulo (col_of i + 3 * row_of i) side) (col_of i).

Definition pi_dest (x y : nat) : nat := idx y (Nat.modulo (2 * x + 3 * y) side).

Definition pi (a : state) : state :=
  map_over (fun i => lane a (pi_source i)) (upto lanes).

Definition pi_inverse (a : state) : state :=
  map_over (fun i => lane a (pi_dest (col_of i) (row_of i))) (upto lanes).

(* A mod-5 table whose wildcard arm is written one row early: correct at 0
   through 19 and wrong at 20, which is the only argument only lane (4, 4)
   reaches. *)
Definition mod5_one_row_early (n : nat) : nat :=
  nth_of n (map_over (fun k => Nat.modulo k side)
                     (upto (2 * (side - 1) + 3 * (side - 1))))
         4.

Definition pi_dest_one_row_early (x y : nat) : nat :=
  idx y (mod5_one_row_early (2 * x + 3 * y)).

(* -------------------------------------------------------------------------
   chi, FIPS 202 Algorithm 4, and the same clause on a bare row of five bits,
   which is the unit chi actually acts on: it reads only lanes (x, y),
   (x+1, y) and (x+2, y) and is bitwise in z.
   ------------------------------------------------------------------------- *)

Definition chi (a : state) : state :=
  map_over (fun i =>
              let x := col_of i in
              let y := row_of i in
              wxor (lane a i)
                   (wand (wnot (lane a (idx (next5 x) y)))
                         (lane a (idx (next5 (next5 x)) y))))
           (upto lanes).

Definition chi_row (r : list bool) : list bool :=
  map_over (fun x => xorb (bit_at r x)
                          (andb (negb (bit_at r (next5 x)))
                                (bit_at r (next5 (next5 x)))))
           (upto side).

(* The same clause with its own term dropped, which is the weakening that
   sends every all-equal row to the same image. *)
Definition chi_row_without_its_own_term (r : list bool) : list bool :=
  map_over (fun x => andb (negb (bit_at r (next5 x)))
                          (bit_at r (next5 (next5 x))))
           (upto side).

Definition row_at (a : state) (y z : nat) : list bool :=
  map_over (fun x => bit_at (lane a (idx x y)) z) (upto side).

Definition all_rows : list (list bool) :=
  map_over (fun n => map_over (fun j => Nat.eqb (Nat.modulo (Nat.div n (Nat.pow 2 j)) 2) 1)
                              (upto side))
           (upto (Nat.pow 2 side)).

Definition is_a_bijection_on_rows (f : list bool -> list bool) : bool :=
  all_of (fun r => Nat.eqb (count_where (fun s => bits_eqb (f s) r) all_rows) 1) all_rows.

(* -------------------------------------------------------------------------
   iota, FIPS 202 Algorithm 6, over round constants **derived** from Algorithm
   5's linear-feedback shift register rather than transcribed. The register is
   eight bits with R[0] at the head; a step prepends a zero, folds R[8] into
   positions 0, 4, 5 and 6, and truncates back to eight, which is Algorithm 5
   step 3 clause for clause. Algorithm 5's first clause, that rc(t) is 1 when
   t mod 255 is zero, needs no arm of its own: the loop then runs zero times
   and the register still holds its initial 10000000.
   ------------------------------------------------------------------------- *)

Definition lfsr_init : list bool := true :: repeat_of 7 false.

Definition lfsr_step (r : list bool) : list bool :=
  let s := false :: r in
  let f := bit_at s 8 in
  take_of 8 (xor_at 0 f (xor_at 4 f (xor_at 5 f (xor_at 6 f s)))).

(* n successive outputs and the register they leave behind, so the whole
   twenty-four-constant table costs one run of the register rather than one
   run per bit. *)
Fixpoint lfsr_take (n : nat) (r : list bool) : (list bool * list bool) :=
  match n with
  | 0 => pair nil r
  | S k => let p := lfsr_take k (lfsr_step r) in
           pair (bit_at r 0 :: fst p) (snd p)
  end.

(* Algorithm 6: RC[2^j - 1] is rc(j + 7 i_r) for j from 0 to l, and l is 6 at
   this lane width; every other bit of the constant is zero. *)
Definition rc_positions : nat := 7.

Definition rc_word (bs : list bool) : word :=
  fold_over (fun w j => set_bit (Nat.pow 2 j - 1) (bit_at bs j) w)
            zero_word (upto rc_positions).

Fixpoint round_constants_from (n : nat) (r : list bool) : list word :=
  match n with
  | 0 => nil
  | S k => let p := lfsr_take rc_positions r in
           rc_word (fst p) :: round_constants_from k (snd p)
  end.

Definition rounds_total : nat := 24.
Definition rounds_short : nat := 12.

Definition round_constants : list word := round_constants_from rounds_total lfsr_init.

Definition round_constant_at (ir : nat) : word := nth_of ir round_constants zero_word.

Definition iota (rc : word) (a : state) : state :=
  set_lane 0 (wxor (lane a 0) rc) a.

(* -------------------------------------------------------------------------
   The round, and the permutation at either frozen round count. FIPS 202 s3.3
   defines Keccak-p[b, n] as the **last** n rounds of Keccak-f[b], so the
   index list is a suffix and the twelve-round form starts at round 12 of the
   same constant table rather than at a second table.
   ------------------------------------------------------------------------- *)

Definition keccak_round (rc : word) (a : state) : state :=
  iota rc (chi (pi (rho (theta a)))).

Definition keccak_step (a : state) (ir : nat) : state :=
  keccak_round (round_constant_at ir) a.

Definition round_indices (n : nat) : list nat :=
  drop_of (rounds_total - n) (upto rounds_total).

Definition prefix_indices (n : nat) : list nat :=
  take_of (rounds_total - n) (upto rounds_total).

Definition keccak_p (n : nat) (a : state) : state :=
  fold_over keccak_step a (round_indices n).

(* The construction R-15-056a's sentence excludes: the same number of rounds,
   taken from the front of the same table. *)
Definition keccak_prefix (n : nat) (a : state) : state :=
  fold_over keccak_step a (prefix_indices n).

Definition keccak_f1600 (a : state) : state := keccak_p rounds_total a.

Definition keccak_p1600_12 (a : state) : state := keccak_p rounds_short a.

(* -------------------------------------------------------------------------
   The state as a bit string and as bytes, FIPS 202 s3.1.2 and sB.1.
   ------------------------------------------------------------------------- *)

Definition bits_of_state (a : state) : list bool := concat_of a.

Definition state_of_bits (s : list bool) : state := chunks_of lanes width s.

(* A byte is eight bits with the head as its least significant, which is FIPS
   202 sB.1. Written as a fold over the chunk itself rather than over an index
   range, so the byte's width is the chunking's business and is stated once. *)
Fixpoint byte_of_bits (l : list bool) : nat :=
  match l with nil => 0 | x :: r => (if x then 1 else 0) + 2 * byte_of_bits r end.

Definition bytes_of (s : list bool) : list nat :=
  map_over byte_of_bits (chunks_of (length_of s) 8 s).

Definition bits_of_byte (n : nat) : list bool :=
  map_over (fun j => Nat.eqb (Nat.modulo (Nat.div n (Nat.pow 2 j)) 2) 1) (upto 8).

Definition bits_of_bytes (l : list nat) : list bool :=
  concat_of (map_over bits_of_byte l).

(* A lane as the eight bytes its published hexadecimal reads as, most
   significant first, which is the order both the standard's own tables and
   keccak_p1600.sail's literals are written in. *)
Definition hex_bytes_of (w : word) : list nat := rev_of (bytes_of w).

(* -------------------------------------------------------------------------
   The sponge, FIPS 202 s4, and pad10*1 (s5.1).
   ------------------------------------------------------------------------- *)

Definition pad10star1 (rate m : nat) : list bool :=
  let j := Nat.modulo (rate - Nat.modulo (m + 2) rate) rate in
  true :: (repeat_of j false ++ (true :: nil)).

(* A pad that adds nothing where the message already fills a block, so the
   padded string is not a **positive** multiple of the rate at the empty
   message. *)
Definition pad_admitting_an_empty_block (rate m : nat) : list bool :=
  if Nat.eqb (Nat.modulo m rate) 0 then nil else pad10star1 rate m.

(* And a pad of the right length whose final bit is not one. *)
Definition pad_without_its_final_one (rate m : nat) : list bool :=
  let j := Nat.modulo (rate - Nat.modulo (m + 2) rate) rate in
  true :: repeat_of (S j) false.

Fixpoint xor_prefix (s b : list bool) : list bool :=
  match s with
  | nil => nil
  | x :: xs => match b with
               | nil => x :: xs
               | y :: ys => xorb x y :: xor_prefix xs ys
               end
  end.

Definition xor_into (block : list bool) (a : state) : state :=
  state_of_bits (xor_prefix (bits_of_state a) block).

Fixpoint absorb (fuel rate : nat) (m : list bool) (a : state) : state :=
  match fuel with
  | 0 => a
  | S k => match m with
           | nil => a
           | _ => absorb k rate (drop_of rate m)
                         (keccak_f1600 (xor_into (take_of rate m) a))
           end
  end.

(* The branch is taken on what is left after this block rather than on a
   comparison, because at d exactly equal to the rate the two arms of a
   comparison give the same answer and a weakening of it would be a defect
   nothing could observe. *)
Fixpoint squeeze (fuel rate d : nat) (a : state) : list bool :=
  match fuel with
  | 0 => nil
  | S k => match d - rate with
           | 0 => take_of d (bits_of_state a)
           | S _ => take_of rate (bits_of_state a)
                    ++ squeeze k rate (d - rate) (keccak_f1600 a)
           end
  end.

(* Both fuels are block counts and not bit counts. A fuel is only there to
   satisfy the termination checker, since neither loop recurses on a
   structurally smaller list, and one generous enough to count bits would let
   a weakening of the loop run thousands of permutations before the answer it
   returns can be looked at. A block count is the smallest fuel that is still
   never the thing that stops a correct run. *)
Definition sponge (rate : nat) (m : list bool) (d : nat) : list bool :=
  let padded := m ++ pad10star1 rate (length_of m) in
  let absorbed := absorb (S (Nat.div (length_of padded) rate)) rate padded zero_state in
  squeeze (S (Nat.div d rate)) rate d absorbed.

(* -------------------------------------------------------------------------
   The six functions FIPS 202 defines, each named by its output length or its
   security strength rather than by the family word, which is what R-05-058a
   asks of every statement of an obligation.
   ------------------------------------------------------------------------- *)

Definition sha3_suffix : list bool := false :: true :: nil.

Definition shake_suffix : list bool := true :: true :: true :: true :: nil.

Definition sha3 (d : nat) (m : list bool) : list bool :=
  sponge (b_bits - 2 * d) (m ++ sha3_suffix) d.

Definition shake (s d : nat) (m : list bool) : list bool :=
  sponge (b_bits - 2 * s) (m ++ shake_suffix) d.

Definition sha3_224 (m : list bool) : list bool := sha3 224 m.
Definition sha3_256 (m : list bool) : list bool := sha3 256 m.
Definition sha3_384 (m : list bool) : list bool := sha3 384 m.
Definition sha3_512 (m : list bool) : list bool := sha3 512 m.
Definition shake128 (d : nat) (m : list bool) : list bool := shake 128 d m.
Definition shake256 (d : nat) (m : list bool) : list bool := shake 256 d m.

Definition sha3_lengths : list nat := 224 :: 256 :: 384 :: 512 :: nil.
Definition shake_strengths : list nat := 128 :: 256 :: nil.

Definition frozen_rates : list nat :=
  map_over (fun n => b_bits - 2 * n) (sha3_lengths ++ shake_strengths).

(* The construction that makes the separator's absence observable: the same
   rate, the same capacity, and no suffix at all. *)
Definition sponge_without_a_separator (c d : nat) (m : list bool) : list bool :=
  sponge (b_bits - c) m d.


(* -------------------------------------------------------------------------
   The two derived tables against the two published ones. This is the whole
   of what makes the pair a differential pair: keccak_p1600.sail writes both
   tables out and this file computes them, so a defect in either
   transcription is a disagreement with a published table rather than a
   disagreement between two things this repository wrote.
   ------------------------------------------------------------------------- *)

Example the_derived_rho_offsets_are_the_published_table :
  rho_table =
  0 :: 1 :: 62 :: 28 :: 27 ::
  36 :: 44 :: 6 :: 55 :: 20 ::
  3 :: 10 :: 43 :: 25 :: 39 ::
  41 :: 45 :: 15 :: 21 :: 8 ::
  18 :: 2 :: 61 :: 56 :: 14 :: nil
  := eq_refl.

Example the_derived_round_constants_are_the_published_table :
  map_over hex_bytes_of round_constants =
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x01 :: nil) ::
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x82 :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x8A :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x00 :: 0x80 :: 0x00 :: nil) ::
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x8B :: nil) ::
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x00 :: 0x00 :: 0x01 :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x00 :: 0x80 :: 0x81 :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x09 :: nil) ::
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x8A :: nil) ::
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x88 :: nil) ::
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x00 :: 0x80 :: 0x09 :: nil) ::
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x00 :: 0x00 :: 0x0A :: nil) ::
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x00 :: 0x80 :: 0x8B :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x8B :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x89 :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x03 :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x02 :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: nil) ::
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x0A :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x00 :: 0x00 :: 0x0A :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x00 :: 0x80 :: 0x81 :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x80 :: nil) ::
  (0x00 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x00 :: 0x00 :: 0x01 :: nil) ::
  (0x80 :: 0x00 :: 0x00 :: 0x00 :: 0x80 :: 0x00 :: 0x80 :: 0x08 :: nil) :: nil
  := eq_refl.

(* -------------------------------------------------------------------------
   The permutation, against the standard published state. The all-zero state
   is invariant under any permutation of its lanes, so a single application
   fixes the tables and the round order and says nothing about the lane
   flattening; the second application, and the sponge vectors below, are
   where a lane-order defect becomes visible.
   ------------------------------------------------------------------------- *)

Example keccak_f1600_of_the_all_zero_state :
  bytes_of (bits_of_state (keccak_f1600 zero_state)) =
  0xE7 :: 0xDD :: 0xE1 :: 0x40 :: 0x79 :: 0x8F :: 0x25 :: 0xF1 ::
  0x8A :: 0x47 :: 0xC0 :: 0x33 :: 0xF9 :: 0xCC :: 0xD5 :: 0x84 ::
  0xEE :: 0xA9 :: 0x5A :: 0xA6 :: 0x1E :: 0x26 :: 0x98 :: 0xD5 ::
  0x4D :: 0x49 :: 0x80 :: 0x6F :: 0x30 :: 0x47 :: 0x15 :: 0xBD ::
  0x57 :: 0xD0 :: 0x53 :: 0x62 :: 0x05 :: 0x4E :: 0x28 :: 0x8B ::
  0xD4 :: 0x6F :: 0x8E :: 0x7F :: 0x2D :: 0xA4 :: 0x97 :: 0xFF ::
  0xC4 :: 0x47 :: 0x46 :: 0xA4 :: 0xA0 :: 0xE5 :: 0xFE :: 0x90 ::
  0x76 :: 0x2E :: 0x19 :: 0xD6 :: 0x0C :: 0xDA :: 0x5B :: 0x8C ::
  0x9C :: 0x05 :: 0x19 :: 0x1B :: 0xF7 :: 0xA6 :: 0x30 :: 0xAD ::
  0x64 :: 0xFC :: 0x8F :: 0xD0 :: 0xB7 :: 0x5A :: 0x93 :: 0x30 ::
  0x35 :: 0xD6 :: 0x17 :: 0x23 :: 0x3F :: 0xA9 :: 0x5A :: 0xEB ::
  0x03 :: 0x21 :: 0x71 :: 0x0D :: 0x26 :: 0xE6 :: 0xA6 :: 0xA9 ::
  0x5F :: 0x55 :: 0xCF :: 0xDB :: 0x16 :: 0x7C :: 0xA5 :: 0x81 ::
  0x26 :: 0xC8 :: 0x47 :: 0x03 :: 0xCD :: 0x31 :: 0xB8 :: 0x43 ::
  0x9F :: 0x56 :: 0xA5 :: 0x11 :: 0x1A :: 0x2F :: 0xF2 :: 0x01 ::
  0x61 :: 0xAE :: 0xD9 :: 0x21 :: 0x5A :: 0x63 :: 0xE5 :: 0x05 ::
  0xF2 :: 0x70 :: 0xC9 :: 0x8C :: 0xF2 :: 0xFE :: 0xBE :: 0x64 ::
  0x11 :: 0x66 :: 0xC4 :: 0x7B :: 0x95 :: 0x70 :: 0x36 :: 0x61 ::
  0xCB :: 0x0E :: 0xD0 :: 0x4F :: 0x55 :: 0x5A :: 0x7C :: 0xB8 ::
  0xC8 :: 0x32 :: 0xCF :: 0x1C :: 0x8A :: 0xE8 :: 0x3E :: 0x8C ::
  0x14 :: 0x26 :: 0x3A :: 0xAE :: 0x22 :: 0x79 :: 0x0C :: 0x94 ::
  0xE4 :: 0x09 :: 0xC5 :: 0xA2 :: 0x24 :: 0xF9 :: 0x41 :: 0x18 ::
  0xC2 :: 0x65 :: 0x04 :: 0xE7 :: 0x26 :: 0x35 :: 0xF5 :: 0x16 ::
  0x3B :: 0xA1 :: 0x30 :: 0x7F :: 0xE9 :: 0x44 :: 0xF6 :: 0x75 ::
  0x49 :: 0xA2 :: 0xEC :: 0x5C :: 0x7B :: 0xFF :: 0xF1 :: 0xEA :: nil
.
Proof. vm_compute. reflexivity. Qed.

Example keccak_f1600_applied_twice_to_the_all_zero_state :
  bytes_of (bits_of_state (keccak_f1600 (keccak_f1600 zero_state))) =
  0x3C :: 0xCB :: 0x6E :: 0xF9 :: 0x4D :: 0x95 :: 0x5C :: 0x2D ::
  0x6D :: 0xB5 :: 0x57 :: 0x70 :: 0xD0 :: 0x2C :: 0x33 :: 0x6A ::
  0x6C :: 0x6B :: 0xD7 :: 0x70 :: 0x12 :: 0x8D :: 0x3D :: 0x09 ::
  0x94 :: 0xD0 :: 0x69 :: 0x55 :: 0xB2 :: 0xD9 :: 0x20 :: 0x8A ::
  0x56 :: 0xF1 :: 0xE7 :: 0xE5 :: 0x99 :: 0x4F :: 0x9C :: 0x4F ::
  0x38 :: 0xFB :: 0x65 :: 0xDA :: 0xA2 :: 0xB9 :: 0x57 :: 0xF9 ::
  0x0D :: 0xAF :: 0x75 :: 0x12 :: 0xAE :: 0x3D :: 0x77 :: 0x85 ::
  0xF7 :: 0x10 :: 0xD8 :: 0xC3 :: 0x47 :: 0xF2 :: 0xF4 :: 0xFA ::
  0x59 :: 0x87 :: 0x9A :: 0xF7 :: 0xE6 :: 0x9E :: 0x1B :: 0x1F ::
  0x25 :: 0xB4 :: 0x98 :: 0xEE :: 0x0F :: 0xCC :: 0xFE :: 0xE4 ::
  0xA1 :: 0x68 :: 0xCE :: 0xB9 :: 0xB6 :: 0x61 :: 0xCE :: 0x68 ::
  0x4F :: 0x97 :: 0x8F :: 0xBA :: 0xC4 :: 0x66 :: 0xEA :: 0xDE ::
  0xF5 :: 0xB1 :: 0xAF :: 0x6E :: 0x83 :: 0x3D :: 0xC4 :: 0x33 ::
  0xD9 :: 0xDB :: 0x19 :: 0x27 :: 0x04 :: 0x54 :: 0x06 :: 0xE0 ::
  0x65 :: 0x12 :: 0x83 :: 0x09 :: 0xF0 :: 0xA9 :: 0xF8 :: 0x7C ::
  0x43 :: 0x47 :: 0x17 :: 0xBF :: 0xA6 :: 0x49 :: 0x54 :: 0xFD ::
  0x40 :: 0x4B :: 0x99 :: 0xD8 :: 0x33 :: 0xAD :: 0xDD :: 0x97 ::
  0x74 :: 0xE7 :: 0x0B :: 0x5D :: 0xFC :: 0xD5 :: 0xEA :: 0x48 ::
  0x3C :: 0xB0 :: 0xB7 :: 0x55 :: 0xEE :: 0xC8 :: 0xB8 :: 0xE3 ::
  0xE9 :: 0x42 :: 0x9E :: 0x64 :: 0x6E :: 0x22 :: 0xA0 :: 0x91 ::
  0x7B :: 0xDD :: 0xBA :: 0xE7 :: 0x29 :: 0x31 :: 0x0E :: 0x90 ::
  0xE8 :: 0xCC :: 0xA3 :: 0xFA :: 0xC5 :: 0x9E :: 0x2A :: 0x20 ::
  0xB6 :: 0x3D :: 0x1C :: 0x4E :: 0x46 :: 0x02 :: 0x34 :: 0x5B ::
  0x59 :: 0x10 :: 0x4C :: 0xA4 :: 0x62 :: 0x4E :: 0x9F :: 0x60 ::
  0x5C :: 0xBF :: 0x8F :: 0x6A :: 0xD2 :: 0x6C :: 0xD0 :: 0x20 :: nil
.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   The six functions FIPS 202 defines, against the published known answers.
   Each answer is a constant inside the statement it decides and never a
   definition, and so is every message: nothing above an answer depends on
   the answer being right, and nothing here is inside the seeded-mutation
   population, where a published byte moved off by one would score as a kill
   of the oracle rather than of the subject.
   ------------------------------------------------------------------------- *)

Example sha3_224_of_the_empty_message :
  bytes_of (sha3_224 nil) =
  0x6B :: 0x4E :: 0x03 :: 0x42 :: 0x36 :: 0x67 :: 0xDB :: 0xB7 ::
  0x3B :: 0x6E :: 0x15 :: 0x45 :: 0x4F :: 0x0E :: 0xB1 :: 0xAB ::
  0xD4 :: 0x59 :: 0x7F :: 0x9A :: 0x1B :: 0x07 :: 0x8E :: 0x3F ::
  0x5B :: 0x5A :: 0x6B :: 0xC7 :: nil
.
Proof. vm_compute. reflexivity. Qed.

Example sha3_256_of_the_empty_message :
  bytes_of (sha3_256 nil) =
  0xA7 :: 0xFF :: 0xC6 :: 0xF8 :: 0xBF :: 0x1E :: 0xD7 :: 0x66 ::
  0x51 :: 0xC1 :: 0x47 :: 0x56 :: 0xA0 :: 0x61 :: 0xD6 :: 0x62 ::
  0xF5 :: 0x80 :: 0xFF :: 0x4D :: 0xE4 :: 0x3B :: 0x49 :: 0xFA ::
  0x82 :: 0xD8 :: 0x0A :: 0x4B :: 0x80 :: 0xF8 :: 0x43 :: 0x4A :: nil
.
Proof. vm_compute. reflexivity. Qed.

Example sha3_384_of_the_empty_message :
  bytes_of (sha3_384 nil) =
  0x0C :: 0x63 :: 0xA7 :: 0x5B :: 0x84 :: 0x5E :: 0x4F :: 0x7D ::
  0x01 :: 0x10 :: 0x7D :: 0x85 :: 0x2E :: 0x4C :: 0x24 :: 0x85 ::
  0xC5 :: 0x1A :: 0x50 :: 0xAA :: 0xAA :: 0x94 :: 0xFC :: 0x61 ::
  0x99 :: 0x5E :: 0x71 :: 0xBB :: 0xEE :: 0x98 :: 0x3A :: 0x2A ::
  0xC3 :: 0x71 :: 0x38 :: 0x31 :: 0x26 :: 0x4A :: 0xDB :: 0x47 ::
  0xFB :: 0x6B :: 0xD1 :: 0xE0 :: 0x58 :: 0xD5 :: 0xF0 :: 0x04 :: nil
.
Proof. vm_compute. reflexivity. Qed.

Example sha3_512_of_the_empty_message :
  bytes_of (sha3_512 nil) =
  0xA6 :: 0x9F :: 0x73 :: 0xCC :: 0xA2 :: 0x3A :: 0x9A :: 0xC5 ::
  0xC8 :: 0xB5 :: 0x67 :: 0xDC :: 0x18 :: 0x5A :: 0x75 :: 0x6E ::
  0x97 :: 0xC9 :: 0x82 :: 0x16 :: 0x4F :: 0xE2 :: 0x58 :: 0x59 ::
  0xE0 :: 0xD1 :: 0xDC :: 0xC1 :: 0x47 :: 0x5C :: 0x80 :: 0xA6 ::
  0x15 :: 0xB2 :: 0x12 :: 0x3A :: 0xF1 :: 0xF5 :: 0xF9 :: 0x4C ::
  0x11 :: 0xE3 :: 0xE9 :: 0x40 :: 0x2C :: 0x3A :: 0xC5 :: 0x58 ::
  0xF5 :: 0x00 :: 0x19 :: 0x9D :: 0x95 :: 0xB6 :: 0xD3 :: 0xE3 ::
  0x01 :: 0x75 :: 0x85 :: 0x86 :: 0x28 :: 0x1D :: 0xCD :: 0x26 :: nil
.
Proof. vm_compute. reflexivity. Qed.

(* One byte of message, which is the first vector that puts two distinct
   non-zero lanes into the state and so the first that fixes where lane 16
   is: an all-zero state is invariant under any permutation of its lanes. *)
Example sha3_256_of_the_one_byte_message :
  bytes_of (sha3_256 (bits_of_bytes (0xCC :: nil))) =
  0x67 :: 0x70 :: 0x35 :: 0x39 :: 0x1C :: 0xD3 :: 0x70 :: 0x12 ::
  0x93 :: 0xD3 :: 0x85 :: 0xF0 :: 0x37 :: 0xBA :: 0x32 :: 0x79 ::
  0x62 :: 0x52 :: 0xBB :: 0x7C :: 0xE1 :: 0x80 :: 0xB0 :: 0x0B ::
  0x58 :: 0x2D :: 0xD9 :: 0xB2 :: 0x0A :: 0xAA :: 0xD7 :: 0xF0 :: nil
.
Proof. vm_compute. reflexivity. Qed.

(* Seventy-three bytes, which is 584 bits: two absorbed blocks at the
   SHA3-256 rate of 1088 bits and two at the SHA3-512 rate of 576, so the
   absorb loop is exercised at two rates rather than assumed. *)
Example sha3_256_of_a_message_spanning_two_blocks :
  bytes_of (sha3_256 (bits_of_bytes (
     0xBA :: 0x5B :: 0x67 :: 0xB5 :: 0xEC :: 0x3A :: 0x3F :: 0xFA ::
     0xE2 :: 0xC1 :: 0x9D :: 0xD8 :: 0x17 :: 0x6A :: 0x2E :: 0xF7 ::
     0x5C :: 0x0C :: 0xD9 :: 0x03 :: 0x72 :: 0x5D :: 0x45 :: 0xC9 ::
     0xCB :: 0x70 :: 0x09 :: 0xA9 :: 0x00 :: 0xC0 :: 0xB0 :: 0xCA ::
     0x7A :: 0x29 :: 0x67 :: 0xA9 :: 0x5A :: 0xE6 :: 0x82 :: 0x69 ::
     0xA6 :: 0xDB :: 0xF8 :: 0x46 :: 0x6C :: 0x7B :: 0x68 :: 0x44 ::
     0xA1 :: 0xD6 :: 0x08 :: 0xAC :: 0x66 :: 0x1F :: 0x7E :: 0xFF ::
     0x00 :: 0x53 :: 0x8E :: 0x32 :: 0x3D :: 0xB5 :: 0xF2 :: 0xC6 ::
     0x44 :: 0xB7 :: 0x8B :: 0x2D :: 0x48 :: 0xDE :: 0x1A :: 0x08 ::
     0xAA :: nil))
  ) =
  0x6C :: 0x47 :: 0xE2 :: 0xEA :: 0x4B :: 0xA2 :: 0x9E :: 0x17 ::
  0x79 :: 0x2D :: 0xEF :: 0xC4 :: 0xB7 :: 0x07 :: 0x75 :: 0x4C ::
  0x46 :: 0x64 :: 0xBD :: 0xE1 :: 0x51 :: 0x68 :: 0xA5 :: 0x10 ::
  0x0B :: 0xF8 :: 0x81 :: 0xEC :: 0x7C :: 0x02 :: 0xB2 :: 0x58 :: nil
.
Proof. vm_compute. reflexivity. Qed.

Example sha3_512_of_a_message_spanning_two_blocks :
  bytes_of (sha3_512 (bits_of_bytes (
     0xBA :: 0x5B :: 0x67 :: 0xB5 :: 0xEC :: 0x3A :: 0x3F :: 0xFA ::
     0xE2 :: 0xC1 :: 0x9D :: 0xD8 :: 0x17 :: 0x6A :: 0x2E :: 0xF7 ::
     0x5C :: 0x0C :: 0xD9 :: 0x03 :: 0x72 :: 0x5D :: 0x45 :: 0xC9 ::
     0xCB :: 0x70 :: 0x09 :: 0xA9 :: 0x00 :: 0xC0 :: 0xB0 :: 0xCA ::
     0x7A :: 0x29 :: 0x67 :: 0xA9 :: 0x5A :: 0xE6 :: 0x82 :: 0x69 ::
     0xA6 :: 0xDB :: 0xF8 :: 0x46 :: 0x6C :: 0x7B :: 0x68 :: 0x44 ::
     0xA1 :: 0xD6 :: 0x08 :: 0xAC :: 0x66 :: 0x1F :: 0x7E :: 0xFF ::
     0x00 :: 0x53 :: 0x8E :: 0x32 :: 0x3D :: 0xB5 :: 0xF2 :: 0xC6 ::
     0x44 :: 0xB7 :: 0x8B :: 0x2D :: 0x48 :: 0xDE :: 0x1A :: 0x08 ::
     0xAA :: nil))
  ) =
  0x63 :: 0x57 :: 0x41 :: 0xB3 :: 0x7F :: 0x66 :: 0xCD :: 0x5C ::
  0xE4 :: 0xDB :: 0xD1 :: 0xF7 :: 0x8A :: 0xCC :: 0xD9 :: 0x07 ::
  0xF9 :: 0x61 :: 0x46 :: 0xE7 :: 0x70 :: 0xB2 :: 0x39 :: 0x04 ::
  0x6A :: 0xFB :: 0x91 :: 0x81 :: 0x91 :: 0x0B :: 0x61 :: 0x2D ::
  0x0E :: 0x65 :: 0x84 :: 0x1F :: 0xF8 :: 0x66 :: 0x80 :: 0x6E ::
  0xED :: 0x83 :: 0xC3 :: 0xAE :: 0x70 :: 0x12 :: 0xFC :: 0x55 ::
  0xE4 :: 0x2C :: 0x3F :: 0xFC :: 0x9C :: 0x6E :: 0x3D :: 0x03 ::
  0xCE :: 0x28 :: 0x70 :: 0x44 :: 0x2F :: 0x29 :: 0x3A :: 0xB4 :: nil
.
Proof. vm_compute. reflexivity. Qed.

(* SHAKE128 and SHAKE256 at the output lengths their security strengths
   name, and SHAKE128 again past one rate, which is where the squeeze loop
   permutes a second time rather than truncating a single block. *)
Example shake128_of_the_empty_message_at_256_bits :
  bytes_of (shake128 256 nil) =
  0x7F :: 0x9C :: 0x2B :: 0xA4 :: 0xE8 :: 0x8F :: 0x82 :: 0x7D ::
  0x61 :: 0x60 :: 0x45 :: 0x50 :: 0x76 :: 0x05 :: 0x85 :: 0x3E ::
  0xD7 :: 0x3B :: 0x80 :: 0x93 :: 0xF6 :: 0xEF :: 0xBC :: 0x88 ::
  0xEB :: 0x1A :: 0x6E :: 0xAC :: 0xFA :: 0x66 :: 0xEF :: 0x26 :: nil
.
Proof. vm_compute. reflexivity. Qed.

Example shake256_of_the_empty_message_at_512_bits :
  bytes_of (shake256 512 nil) =
  0x46 :: 0xB9 :: 0xDD :: 0x2B :: 0x0B :: 0xA8 :: 0x8D :: 0x13 ::
  0x23 :: 0x3B :: 0x3F :: 0xEB :: 0x74 :: 0x3E :: 0xEB :: 0x24 ::
  0x3F :: 0xCD :: 0x52 :: 0xEA :: 0x62 :: 0xB8 :: 0x1B :: 0x82 ::
  0xB5 :: 0x0C :: 0x27 :: 0x64 :: 0x6E :: 0xD5 :: 0x76 :: 0x2F ::
  0xD7 :: 0x5D :: 0xC4 :: 0xDD :: 0xD8 :: 0xC0 :: 0xF2 :: 0x00 ::
  0xCB :: 0x05 :: 0x01 :: 0x9D :: 0x67 :: 0xB5 :: 0x92 :: 0xF6 ::
  0xFC :: 0x82 :: 0x1C :: 0x49 :: 0x47 :: 0x9A :: 0xB4 :: 0x86 ::
  0x40 :: 0x29 :: 0x2E :: 0xAC :: 0xB3 :: 0xB7 :: 0xC4 :: 0xBE :: nil
.
Proof. vm_compute. reflexivity. Qed.

Example shake128_of_the_empty_message_across_two_squeezes :
  bytes_of (shake128 1360 nil) =
  0x7F :: 0x9C :: 0x2B :: 0xA4 :: 0xE8 :: 0x8F :: 0x82 :: 0x7D ::
  0x61 :: 0x60 :: 0x45 :: 0x50 :: 0x76 :: 0x05 :: 0x85 :: 0x3E ::
  0xD7 :: 0x3B :: 0x80 :: 0x93 :: 0xF6 :: 0xEF :: 0xBC :: 0x88 ::
  0xEB :: 0x1A :: 0x6E :: 0xAC :: 0xFA :: 0x66 :: 0xEF :: 0x26 ::
  0x3C :: 0xB1 :: 0xEE :: 0xA9 :: 0x88 :: 0x00 :: 0x4B :: 0x93 ::
  0x10 :: 0x3C :: 0xFB :: 0x0A :: 0xEE :: 0xFD :: 0x2A :: 0x68 ::
  0x6E :: 0x01 :: 0xFA :: 0x4A :: 0x58 :: 0xE8 :: 0xA3 :: 0x63 ::
  0x9C :: 0xA8 :: 0xA1 :: 0xE3 :: 0xF9 :: 0xAE :: 0x57 :: 0xE2 ::
  0x35 :: 0xB8 :: 0xCC :: 0x87 :: 0x3C :: 0x23 :: 0xDC :: 0x62 ::
  0xB8 :: 0xD2 :: 0x60 :: 0x16 :: 0x9A :: 0xFA :: 0x2F :: 0x75 ::
  0xAB :: 0x91 :: 0x6A :: 0x58 :: 0xD9 :: 0x74 :: 0x91 :: 0x88 ::
  0x35 :: 0xD2 :: 0x5E :: 0x6A :: 0x43 :: 0x50 :: 0x85 :: 0xB2 ::
  0xBA :: 0xDF :: 0xD6 :: 0xDF :: 0xAA :: 0xC3 :: 0x59 :: 0xA5 ::
  0xEF :: 0xBB :: 0x7B :: 0xCC :: 0x4B :: 0x59 :: 0xD5 :: 0x38 ::
  0xDF :: 0x9A :: 0x04 :: 0x30 :: 0x2E :: 0x10 :: 0xC8 :: 0xBC ::
  0x1C :: 0xBF :: 0x1A :: 0x0B :: 0x3A :: 0x51 :: 0x20 :: 0xEA ::
  0x17 :: 0xCD :: 0xA7 :: 0xCF :: 0xAD :: 0x76 :: 0x5F :: 0x56 ::
  0x23 :: 0x47 :: 0x4D :: 0x36 :: 0x8C :: 0xCC :: 0xA8 :: 0xAF ::
  0x00 :: 0x07 :: 0xCD :: 0x9F :: 0x5E :: 0x4C :: 0x84 :: 0x9F ::
  0x16 :: 0x7A :: 0x58 :: 0x0B :: 0x14 :: 0xAA :: 0xBD :: 0xEF ::
  0xAE :: 0xE7 :: 0xEE :: 0xF4 :: 0x7C :: 0xB0 :: 0xFC :: 0xA9 ::
  0x76 :: 0x7B :: nil
.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   pi. The step is a permutation of the twenty-five lanes and nothing else,
   which is the one clause of R-15-056's "permutation" a table can be wrong
   about silently: a mod-5 arm transcribed one row early makes pi drop one
   lane and write another twice, and every round-count and offset argument
   still passes.
   ------------------------------------------------------------------------- *)

Definition covers_each_index_once (l : list nat) (n : nat) : bool :=
  all_of (fun i => Nat.eqb (count_where (fun v => Nat.eqb v i) l) 1) (upto n).

Example pi_is_a_bijection_on_the_twenty_five_lanes :
  covers_each_index_once (map_over pi_source (upto lanes)) lanes = true := eq_refl.

Example the_destination_form_is_a_bijection_too :
  covers_each_index_once
    (map_over (fun i => pi_dest (col_of i) (row_of i)) (upto lanes)) lanes = true := eq_refl.

(* The two forms against each other, which is where this file and
   keccak_p1600.sail meet: that file sends lane (x, y) to (y, (2x + 3y) mod 5)
   and this one reads lane (x, y) from ((x + 3y) mod 5, x), and either is the
   other's inverse or one of the two is wrong. *)
Example the_source_and_destination_forms_are_one_permutation :
  all_of (fun i => Nat.eqb (pi_dest (col_of (pi_source i)) (row_of (pi_source i))) i)
         (upto lanes) = true := eq_refl.

Example a_mod_five_arm_written_one_row_early_drops_a_lane :
  covers_each_index_once
    (map_over (fun i => pi_dest_one_row_early (col_of i) (row_of i)) (upto lanes))
    lanes = false := eq_refl.

(* And the reason that defect is invisible to a reader: the argument reaches
   twenty, and exactly one lane of the twenty-five sends it there. *)
Example the_wildcard_arm_disagrees_at_twenty_and_nowhere_below_it :
  count_where (fun n => negb (Nat.eqb (mod5_one_row_early n) (Nat.modulo n side)))
              (upto (2 * (side - 1) + 3 * (side - 1) + 1)) = 1 := eq_refl.

Example one_lane_alone_reaches_the_largest_argument :
  count_where (fun i => Nat.eqb (2 * col_of i + 3 * row_of i)
                                (2 * (side - 1) + 3 * (side - 1)))
              (upto lanes) = 1 := eq_refl.

(* -------------------------------------------------------------------------
   rho. The offsets are the triangular numbers modulo the lane width and are
   therefore distinct, lane (0, 0) alone being left unrotated, and every
   rotation the table uses is undone by its complement.
   ------------------------------------------------------------------------- *)

Definition offsets_are_distinct (t : list nat) : bool :=
  all_of (fun i => Nat.eqb (count_where (fun o => Nat.eqb o (offset_at t i)) t) 1)
         (upto (length_of t)).

Example the_rho_offsets_are_distinct_and_leave_lane_zero_unrotated :
  andb (offsets_are_distinct rho_table) (Nat.eqb (nth_of 0 rho_table 0) 0) = true := eq_refl.

Example the_recurrence_started_one_step_early_repeats_an_offset :
  offsets_are_distinct rho_table_one_step_early = false := eq_refl.

(* -------------------------------------------------------------------------
   chi, on the unit it acts on. The step reads lanes (x, y), (x+1, y) and
   (x+2, y) and is bitwise in z, so what it does is a map on a row of five
   bits, and that map is a bijection on all thirty-two rows. Dropping its own
   term leaves a map that sends the all-zero row and the all-one row to the
   same image, which is the weakening a digest vector reports as an unreadable
   difference and this reports as its cause.
   ------------------------------------------------------------------------- *)

Example chi_is_a_bijection_on_a_row_of_five_bits :
  is_a_bijection_on_rows chi_row = true := eq_refl.

Example dropping_chis_own_term_collapses_the_row_map :
  is_a_bijection_on_rows chi_row_without_its_own_term = false := eq_refl.

Example the_dropped_term_sends_two_rows_to_one :
  bits_eqb (chi_row_without_its_own_term (repeat_of side false))
           (chi_row_without_its_own_term (repeat_of side true)) = true := eq_refl.

(* And chi on the state is that row map, at every row and every bit position
   of a state with no structure left in it. *)
Example chi_is_the_row_map_at_every_row_and_bit_of_a_permuted_state :
  let a := keccak_f1600 zero_state in
  all_of (fun y => all_of (fun z => bits_eqb (row_at (chi a) y z) (chi_row (row_at a y z)))
                          (upto width))
         (upto side) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   iota is an involution, over an arbitrary round constant, an arbitrary lane
   zero and an arbitrary remainder of the state.
   ------------------------------------------------------------------------- *)

Lemma xorb_cancels : forall x y : bool, xorb (xorb x y) y = x.
Proof. intros x y. destruct x; destruct y; reflexivity. Qed.

Lemma wxor_cancels : forall w c : word, length_of w = length_of c -> wxor (wxor w c) c = w.
Proof.
  induction w as [|x w IH]; intros c H.
  - reflexivity.
  - destruct c as [|y c].
    + discriminate H.
    + simpl in H. injection H as H. simpl.
      rewrite xorb_cancels. rewrite (IH c H). reflexivity.
Qed.

Theorem iota_is_an_involution :
  forall (rc w : word) (rest : state),
    length_of w = length_of rc ->
    iota rc (iota rc (w :: rest)) = w :: rest.
Proof.
  intros rc w rest H. unfold iota, lane. simpl.
  rewrite (wxor_cancels w rc H). reflexivity.
Qed.

(* -------------------------------------------------------------------------
   The two frozen round counts (R-15-056a). Keccak-p[1600, n] is the **last**
   n rounds of Keccak-f[1600], so running the first n rounds and then the
   short form is the whole permutation: that is stated over an arbitrary state
   and an arbitrary round count rather than checked at one input, because it
   is the one thing about R-15-056a a round-count argument cannot show.
   ------------------------------------------------------------------------- *)

Lemma fold_over_app :
  forall (A B : Type) (f : B -> A -> B) (acc : B) (l m : list A),
    fold_over f acc (l ++ m) = fold_over f (fold_over f acc l) m.
Proof.
  intros A B f acc l. revert acc.
  induction l as [|x l IH]; intros acc m; simpl.
  - reflexivity.
  - apply IH.
Qed.

Lemma take_drop_join :
  forall (A : Type) (n : nat) (l : list A), take_of n l ++ drop_of n l = l.
Proof.
  intros A n. induction n as [|n IH]; intros l.
  - reflexivity.
  - destruct l as [|x l].
    + reflexivity.
    + simpl. rewrite IH. reflexivity.
Qed.

Lemma drop_of_zero : forall (A : Type) (l : list A), drop_of 0 l = l.
Proof. intros A l. reflexivity. Qed.

Theorem the_short_form_is_the_last_rounds_and_not_the_first :
  forall (n : nat) (a : state), keccak_p n (keccak_prefix n a) = keccak_p rounds_total a.
Proof.
  intros n a. unfold keccak_p, keccak_prefix, round_indices, prefix_indices.
  rewrite <- fold_over_app. rewrite take_drop_join.
  replace (rounds_total - rounds_total) with 0 by reflexivity.
  rewrite drop_of_zero. reflexivity.
Qed.

Example the_short_form_starts_at_round_twelve :
  nth_of 0 (round_indices rounds_short) 0 = rounds_short := eq_refl.

Example the_long_form_starts_at_round_zero :
  nth_of 0 (round_indices rounds_total) 0 = 0 := eq_refl.

Example the_first_twelve_rounds_are_not_the_last_twelve :
  bits_eqb (bits_of_state (keccak_prefix rounds_short zero_state))
           (bits_of_state (keccak_p1600_12 zero_state)) = false.
Proof. vm_compute. reflexivity. Qed.

Example the_two_frozen_round_counts_are_two_permutations :
  bits_eqb (bits_of_state (keccak_p1600_12 zero_state))
           (bits_of_state (keccak_f1600 zero_state)) = false.
Proof. vm_compute. reflexivity. Qed.

(* The constant table is not its own reverse, which is why a table literal
   read in the wrong direction is a different permutation rather than a
   harmless reordering. keccak_p1600.sail carries exactly that hazard, a Sail
   vector literal being dec-ordered, and answers it with an accessor. *)
Example the_constant_table_read_in_reverse_is_a_different_table :
  all_of (fun i => bits_eqb (round_constant_at i)
                            (round_constant_at (rounds_total - 1 - i)))
         (upto rounds_total) = false := eq_refl.

(* -------------------------------------------------------------------------
   pad10*1 (FIPS 202 s5.1). The padded string is a positive multiple of the
   rate and its last bit is one, at every rate the frozen suite uses and at
   every message length around a block boundary.
   ------------------------------------------------------------------------- *)

Definition padded_length (pad : nat -> nat -> list bool) (rate m : nat) : nat :=
  m + length_of (pad rate m).

Definition pad_is_well_formed (pad : nat -> nat -> list bool) (rate m : nat) : bool :=
  let p := pad rate m in
  andb (Nat.eqb (Nat.modulo (padded_length pad rate m) rate) 0)
       (bit_at p (length_of p - 1)).

Definition pad_probe_lengths (rate : nat) : list nat :=
  upto 8 ++ map_over (fun d => rate - d) (upto side) ++ (rate + 1 :: 2 * rate :: nil).

Example pad10star1_is_a_positive_multiple_of_the_rate_ending_in_one :
  all_of (fun r => all_of (pad_is_well_formed pad10star1 r) (pad_probe_lengths r))
         frozen_rates = true.
Proof. vm_compute. reflexivity. Qed.

Example a_pad_that_adds_nothing_to_an_aligned_message_is_refused :
  all_of (fun r => all_of (pad_is_well_formed pad_admitting_an_empty_block r)
                          (pad_probe_lengths r))
         frozen_rates = false.
Proof. vm_compute. reflexivity. Qed.

Example a_pad_without_its_final_one_is_refused :
  all_of (fun r => all_of (pad_is_well_formed pad_without_its_final_one r)
                          (pad_probe_lengths r))
         frozen_rates = false.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The domain separators. SHA3-256 and SHAKE256 take the same capacity from
   the same rule and therefore the same rate, and differ only in the suffix
   appended to the message before the padding. So the separator is what
   decides between them, no digest vector names it, and a construction with no
   separator makes the two the same function.
   ------------------------------------------------------------------------- *)

Definition sha3_unseparated (d : nat) (m : list bool) : list bool :=
  sponge_without_a_separator (2 * d) d m.

Definition shake_unseparated (s d : nat) (m : list bool) : list bool :=
  sponge_without_a_separator (2 * s) d m.

Example the_domain_separator_decides :
  bits_eqb (sha3_256 nil) (shake256 256 nil) = false.
Proof. vm_compute. reflexivity. Qed.

Example without_a_domain_separator_the_two_coincide :
  bits_eqb (sha3_unseparated 256 nil) (shake_unseparated 256 256 nil) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_two_suffixes_are_different :
  bits_eqb sha3_suffix shake_suffix = false := eq_refl.


(* -------------------------------------------------------------------------
   The decisions a reader would otherwise take on trust because nothing above
   reaches them: the two out-of-range answers, the width of Algorithm 5's
   register, the rates the capacity rule produces, and the message lengths the
   pad is probed at. Each is pinned here rather than left to a default no
   computation visits, a fixture nothing reaches being a site a seeded
   weakening survives at rather than a site nothing can go wrong in.
   ------------------------------------------------------------------------- *)

Example a_bit_off_the_end_of_a_word_is_zero : bit_at nil 0 = false := eq_refl.

Example an_offset_off_the_end_of_the_table_is_zero : offset_at nil 0 = 0 := eq_refl.

Example the_shift_register_is_eight_bits_wide :
  Nat.eqb (length_of lfsr_init) 8 = true := eq_refl.

Example the_first_output_of_the_register_is_one :
  bit_at lfsr_init 0 = true := eq_refl.

(* FIPS 202 Table 3's rates, which are what the capacity rule c = 2n produces
   at the four SHA-3 output lengths and the two SHAKE security strengths. *)
Example the_capacity_rule_gives_the_published_rates :
  frozen_rates = 1152 :: 1088 :: 832 :: 576 :: 1344 :: 1088 :: nil := eq_refl.

Example the_pad_is_probed_across_a_block_boundary :
  pad_probe_lengths 8 = 0 :: 1 :: 2 :: 3 :: 4 :: 5 :: 6 :: 7 ::
                        8 :: 7 :: 6 :: 5 :: 4 :: 9 :: 16 :: nil := eq_refl.

Example pad10star1_never_yields_an_empty_string :
  all_of (fun r => all_of (fun m => Nat.ltb 0 (padded_length pad10star1 r m))
                          (pad_probe_lengths r))
         frozen_rates = true.
Proof. vm_compute. reflexivity. Qed.

Example the_pad_that_adds_nothing_yields_an_empty_string :
  Nat.ltb 0 (padded_length pad_admitting_an_empty_block
                           (nth_of 0 frozen_rates 0) 0) = false := eq_refl.

(* And it is exactly the aligned lengths it gets wrong, which is what makes it
   the weakening it is rather than a different pad. *)
Example the_pad_that_adds_nothing_differs_only_where_the_message_is_aligned :
  all_of (fun r => all_of (fun m => eqb_bool (Nat.eqb (Nat.modulo m r) 0)
                                             (negb (bits_eqb (pad_admitting_an_empty_block r m)
                                                             (pad10star1 r m))))
                          (pad_probe_lengths r))
         frozen_rates = true.
Proof. vm_compute. reflexivity. Qed.

(* And the pad without its final one is the right length and the wrong string
   at every probe, which is what separates it from a length defect. *)
Example the_pad_without_its_final_one_keeps_the_length_and_loses_the_bit :
  all_of (fun r => all_of (fun m =>
                     andb (Nat.eqb (length_of (pad_without_its_final_one r m))
                                   (length_of (pad10star1 r m)))
                          (negb (bit_at (pad_without_its_final_one r m)
                                        (length_of (pad_without_its_final_one r m) - 1))))
                          (pad_probe_lengths r))
         frozen_rates = true.
Proof. vm_compute. reflexivity. Qed.


(* -------------------------------------------------------------------------
   Each refuted construction against the specification it weakens. A
   construction is only a refutation of what it is *near*: an alternative that
   differs everywhere refutes nothing in particular, and a weakening nothing
   pins can drift into a second wrong thing while the refutation it serves
   still reads green. So each one is held to the single difference it exists
   to exhibit.
   ------------------------------------------------------------------------- *)

(* The wildcard one row early moves exactly one lane, which is lane (4, 4),
   and it answers 4 where the standard answers 0. *)
Example the_early_wildcard_moves_exactly_one_lane :
  count_where (fun i => negb (Nat.eqb (pi_dest_one_row_early (col_of i) (row_of i))
                                      (pi_dest (col_of i) (row_of i))))
              (upto lanes) = 1 := eq_refl.

Example the_early_wildcard_answers_four_where_the_standard_answers_zero :
  Nat.eqb (mod5_one_row_early (2 * (side - 1) + 3 * (side - 1))) (side - 1) = true := eq_refl.

(* The recurrence started one step early gives the first walked lane the
   offset lane (0, 0) already has, and nothing else collides: the table has
   exactly two zeros where the standard's has one. *)
Example the_early_recurrence_repeats_only_the_unrotated_offset :
  count_where (fun o => Nat.eqb o 0) rho_table_one_step_early = 2 := eq_refl.

Example the_standard_recurrence_leaves_one_lane_unrotated :
  count_where (fun o => Nat.eqb o 0) rho_table = 1 := eq_refl.

(* And the term chi is missing is chi's own lane, so the two differ by exactly
   that lane at every one of the thirty-two rows. *)
Example the_dropped_term_is_chis_own_lane :
  all_of (fun r => bits_eqb (chi_row r) (wxor r (chi_row_without_its_own_term r)))
         all_rows = true := eq_refl.


(* A comparison whose two operands are never of different lengths anywhere
   above is a comparison whose short-list arms nothing reaches, so both are
   decided here rather than left as answers no computation visits. *)
Example a_word_is_not_equal_to_a_shorter_one : bits_eqb (true :: nil) nil = false := eq_refl.

Example a_word_is_not_equal_to_a_longer_one : bits_eqb nil (true :: nil) = false := eq_refl.

(* Algorithm 5's register is eight bits before a step and eight bits after it.
   A step that truncated one bit wider would carry a ninth bit no later step
   reads, so every output it produced would be the standard's and the register
   would still be the wrong register. *)
Example the_register_stays_eight_bits_wide_across_a_step :
  Nat.eqb (length_of (lfsr_step lfsr_init)) 8 = true := eq_refl.

(* The table the one-step-early recurrence produces, pinned whole. A refuted
   construction that drifts under an edit stops refuting what it was written
   to refute while the statement about it still reads green, so the
   construction is held to its own content the way the specification is held
   to the published one. *)
Example the_early_recurrence_produces_this_table :
  rho_table_one_step_early =
  0 :: 0 :: 43 :: 21 :: 14 ::
  28 :: 20 :: 3 :: 45 :: 61 ::
  1 :: 6 :: 25 :: 8 :: 18 ::
  27 :: 36 :: 10 :: 15 :: 56 ::
  62 :: 55 :: 39 :: 41 :: 2 :: nil := eq_refl.

(* The pad without its final one is the same string up to that bit, which is
   what makes it a refutation of the final-bit clause rather than of the
   length clause. *)
Example the_pad_without_its_final_one_differs_only_in_its_last_bit :
  all_of (fun r => all_of (fun m =>
                     bits_eqb (take_of (length_of (pad10star1 r m) - 1)
                                       (pad_without_its_final_one r m))
                              (take_of (length_of (pad10star1 r m) - 1)
                                       (pad10star1 r m)))
                          (pad_probe_lengths r))
         frozen_rates = true.
Proof. vm_compute. reflexivity. Qed.

(* And the unseparated construction is the separated one with the suffix taken
   out of the function and handed to it as message, which is what makes the
   coincidence above a statement about the separator rather than about a rate.
   Both are stated, because the two functions take their capacity from two
   different rules that happen to agree at this pair of parameters. *)
Example the_unseparated_sha3_is_sha3_with_its_suffix_handed_in :
  bits_eqb (sha3_unseparated 256 sha3_suffix) (sha3_256 nil) = true.
Proof. vm_compute. reflexivity. Qed.

Example the_unseparated_shake_is_shake_with_its_suffix_handed_in :
  bits_eqb (shake_unseparated 256 512 shake_suffix) (shake256 512 nil) = true.
Proof. vm_compute. reflexivity. Qed.

(* -------------------------------------------------------------------------
   How much of R-15-056's word "permutation" is discharged here, stated over
   arbitrary lanes and an arbitrary lane rather than at a chosen state.

   pi is invertible: its inverse is the destination form above, and it
   recovers a state whose twenty-five lanes are twenty-five arbitrary words.
   ------------------------------------------------------------------------- *)

Theorem pi_is_invertible_on_an_arbitrary_state :
  forall w0 w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11 w12 w13 w14 w15 w16 w17 w18 w19 w20 w21 w22 w23 w24 : word,
    pi_inverse (pi (
      w0 :: w1 :: w2 :: w3 :: w4 ::
      w5 :: w6 :: w7 :: w8 :: w9 ::
      w10 :: w11 :: w12 :: w13 :: w14 ::
      w15 :: w16 :: w17 :: w18 :: w19 ::
      w20 :: w21 :: w22 :: w23 :: w24 :: nil))
    =
    w0 :: w1 :: w2 :: w3 :: w4 ::
    w5 :: w6 :: w7 :: w8 :: w9 ::
    w10 :: w11 :: w12 :: w13 :: w14 ::
    w15 :: w16 :: w17 :: w18 :: w19 ::
    w20 :: w21 :: w22 :: w23 :: w24 :: nil.
Proof. intros. vm_compute. reflexivity. Qed.

(* Every rotation the rho table uses is undone by its complement, on a lane
   of sixty-four arbitrary bits. That is rho's invertibility: the step moves
   no lane and rotates each by its own offset. *)
Theorem the_rho_rotations_are_invertible_on_an_arbitrary_lane :
  forall b0 b1 b2 b3 b4 b5 b6 b7 b8 b9 b10 b11 b12 b13 b14 b15 b16 b17 b18 b19 b20 b21 b22 b23 b24 b25 b26 b27 b28 b29 b30 b31 b32 b33 b34 b35 b36 b37 b38 b39 b40 b41 b42 b43 b44 b45 b46 b47 b48 b49 b50 b51 b52 b53 b54 b55 b56 b57 b58 b59 b60 b61 b62 b63 : bool,
    let w :=
      b0 :: b1 :: b2 :: b3 :: b4 :: b5 :: b6 :: b7 ::
      b8 :: b9 :: b10 :: b11 :: b12 :: b13 :: b14 :: b15 ::
      b16 :: b17 :: b18 :: b19 :: b20 :: b21 :: b22 :: b23 ::
      b24 :: b25 :: b26 :: b27 :: b28 :: b29 :: b30 :: b31 ::
      b32 :: b33 :: b34 :: b35 :: b36 :: b37 :: b38 :: b39 ::
      b40 :: b41 :: b42 :: b43 :: b44 :: b45 :: b46 :: b47 ::
      b48 :: b49 :: b50 :: b51 :: b52 :: b53 :: b54 :: b55 ::
      b56 :: b57 :: b58 :: b59 :: b60 :: b61 :: b62 :: b63 :: nil in
    map_over (fun r => rotl (width - r) (rotl r w)) rho_table = repeat_of lanes w.
Proof. intros. vm_compute. reflexivity. Qed.




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
Print Assumptions offset_at.
Print Assumptions rev_onto.
Print Assumptions rev_of.
Print Assumptions repeat_of.
Print Assumptions up_from.
Print Assumptions upto.
Print Assumptions fold_over.
Print Assumptions concat_of.
Print Assumptions all_of.
Print Assumptions count_where.
Print Assumptions chunks_of.
Print Assumptions eqb_bool.
Print Assumptions bits_eqb.
Print Assumptions side.
Print Assumptions width.
Print Assumptions lanes.
Print Assumptions b_bits.
Print Assumptions word.
Print Assumptions state.
Print Assumptions zero_word.
Print Assumptions zero_state.
Print Assumptions wxor.
Print Assumptions wand.
Print Assumptions wnot.
Print Assumptions rotl.
Print Assumptions idx.
Print Assumptions col_of.
Print Assumptions row_of.
Print Assumptions lane.
Print Assumptions next5.
Print Assumptions prev5.
Print Assumptions set_bit.
Print Assumptions xor_at.
Print Assumptions set_lane.
Print Assumptions theta_C.
Print Assumptions theta.
Print Assumptions rho_step.
Print Assumptions triangular.
Print Assumptions rho_walk.
Print Assumptions rho_lookup.
Print Assumptions rho_table.
Print Assumptions rho.
Print Assumptions triangular_one_step_early.
Print Assumptions rho_walk_one_step_early.
Print Assumptions rho_table_one_step_early.
Print Assumptions pi_source.
Print Assumptions pi_dest.
Print Assumptions pi.
Print Assumptions pi_inverse.
Print Assumptions mod5_one_row_early.
Print Assumptions pi_dest_one_row_early.
Print Assumptions chi.
Print Assumptions chi_row.
Print Assumptions chi_row_without_its_own_term.
Print Assumptions row_at.
Print Assumptions all_rows.
Print Assumptions is_a_bijection_on_rows.
Print Assumptions lfsr_init.
Print Assumptions lfsr_step.
Print Assumptions lfsr_take.
Print Assumptions rc_positions.
Print Assumptions rc_word.
Print Assumptions round_constants_from.
Print Assumptions rounds_total.
Print Assumptions rounds_short.
Print Assumptions round_constants.
Print Assumptions round_constant_at.
Print Assumptions iota.
Print Assumptions keccak_round.
Print Assumptions keccak_step.
Print Assumptions round_indices.
Print Assumptions prefix_indices.
Print Assumptions keccak_p.
Print Assumptions keccak_prefix.
Print Assumptions keccak_f1600.
Print Assumptions keccak_p1600_12.
Print Assumptions bits_of_state.
Print Assumptions state_of_bits.
Print Assumptions byte_of_bits.
Print Assumptions bytes_of.
Print Assumptions bits_of_byte.
Print Assumptions bits_of_bytes.
Print Assumptions hex_bytes_of.
Print Assumptions pad10star1.
Print Assumptions pad_admitting_an_empty_block.
Print Assumptions pad_without_its_final_one.
Print Assumptions xor_prefix.
Print Assumptions xor_into.
Print Assumptions absorb.
Print Assumptions squeeze.
Print Assumptions sponge.
Print Assumptions sha3_suffix.
Print Assumptions shake_suffix.
Print Assumptions sha3.
Print Assumptions shake.
Print Assumptions sha3_224.
Print Assumptions sha3_256.
Print Assumptions sha3_384.
Print Assumptions sha3_512.
Print Assumptions shake128.
Print Assumptions shake256.
Print Assumptions sha3_lengths.
Print Assumptions shake_strengths.
Print Assumptions frozen_rates.
Print Assumptions sponge_without_a_separator.
Print Assumptions the_derived_rho_offsets_are_the_published_table.
Print Assumptions the_derived_round_constants_are_the_published_table.
Print Assumptions keccak_f1600_of_the_all_zero_state.
Print Assumptions keccak_f1600_applied_twice_to_the_all_zero_state.
Print Assumptions sha3_224_of_the_empty_message.
Print Assumptions sha3_256_of_the_empty_message.
Print Assumptions sha3_384_of_the_empty_message.
Print Assumptions sha3_512_of_the_empty_message.
Print Assumptions sha3_256_of_the_one_byte_message.
Print Assumptions sha3_256_of_a_message_spanning_two_blocks.
Print Assumptions sha3_512_of_a_message_spanning_two_blocks.
Print Assumptions shake128_of_the_empty_message_at_256_bits.
Print Assumptions shake256_of_the_empty_message_at_512_bits.
Print Assumptions shake128_of_the_empty_message_across_two_squeezes.
Print Assumptions covers_each_index_once.
Print Assumptions pi_is_a_bijection_on_the_twenty_five_lanes.
Print Assumptions the_destination_form_is_a_bijection_too.
Print Assumptions the_source_and_destination_forms_are_one_permutation.
Print Assumptions a_mod_five_arm_written_one_row_early_drops_a_lane.
Print Assumptions the_wildcard_arm_disagrees_at_twenty_and_nowhere_below_it.
Print Assumptions one_lane_alone_reaches_the_largest_argument.
Print Assumptions offsets_are_distinct.
Print Assumptions the_rho_offsets_are_distinct_and_leave_lane_zero_unrotated.
Print Assumptions the_recurrence_started_one_step_early_repeats_an_offset.
Print Assumptions chi_is_a_bijection_on_a_row_of_five_bits.
Print Assumptions dropping_chis_own_term_collapses_the_row_map.
Print Assumptions the_dropped_term_sends_two_rows_to_one.
Print Assumptions chi_is_the_row_map_at_every_row_and_bit_of_a_permuted_state.
Print Assumptions xorb_cancels.
Print Assumptions wxor_cancels.
Print Assumptions iota_is_an_involution.
Print Assumptions fold_over_app.
Print Assumptions take_drop_join.
Print Assumptions drop_of_zero.
Print Assumptions the_short_form_is_the_last_rounds_and_not_the_first.
Print Assumptions the_short_form_starts_at_round_twelve.
Print Assumptions the_long_form_starts_at_round_zero.
Print Assumptions the_first_twelve_rounds_are_not_the_last_twelve.
Print Assumptions the_two_frozen_round_counts_are_two_permutations.
Print Assumptions the_constant_table_read_in_reverse_is_a_different_table.
Print Assumptions padded_length.
Print Assumptions pad_is_well_formed.
Print Assumptions pad_probe_lengths.
Print Assumptions pad10star1_is_a_positive_multiple_of_the_rate_ending_in_one.
Print Assumptions a_pad_that_adds_nothing_to_an_aligned_message_is_refused.
Print Assumptions a_pad_without_its_final_one_is_refused.
Print Assumptions sha3_unseparated.
Print Assumptions shake_unseparated.
Print Assumptions the_domain_separator_decides.
Print Assumptions without_a_domain_separator_the_two_coincide.
Print Assumptions the_two_suffixes_are_different.
Print Assumptions a_bit_off_the_end_of_a_word_is_zero.
Print Assumptions an_offset_off_the_end_of_the_table_is_zero.
Print Assumptions the_shift_register_is_eight_bits_wide.
Print Assumptions the_first_output_of_the_register_is_one.
Print Assumptions the_capacity_rule_gives_the_published_rates.
Print Assumptions the_pad_is_probed_across_a_block_boundary.
Print Assumptions pad10star1_never_yields_an_empty_string.
Print Assumptions the_pad_that_adds_nothing_yields_an_empty_string.
Print Assumptions the_pad_that_adds_nothing_differs_only_where_the_message_is_aligned.
Print Assumptions the_pad_without_its_final_one_keeps_the_length_and_loses_the_bit.
Print Assumptions the_early_wildcard_moves_exactly_one_lane.
Print Assumptions the_early_wildcard_answers_four_where_the_standard_answers_zero.
Print Assumptions the_early_recurrence_repeats_only_the_unrotated_offset.
Print Assumptions the_standard_recurrence_leaves_one_lane_unrotated.
Print Assumptions the_dropped_term_is_chis_own_lane.
Print Assumptions a_word_is_not_equal_to_a_shorter_one.
Print Assumptions a_word_is_not_equal_to_a_longer_one.
Print Assumptions the_register_stays_eight_bits_wide_across_a_step.
Print Assumptions the_early_recurrence_produces_this_table.
Print Assumptions the_pad_without_its_final_one_differs_only_in_its_last_bit.
Print Assumptions the_unseparated_sha3_is_sha3_with_its_suffix_handed_in.
Print Assumptions the_unseparated_shake_is_shake_with_its_suffix_handed_in.
Print Assumptions pi_is_invertible_on_an_arbitrary_state.
Print Assumptions the_rho_rotations_are_invertible_on_an_arbitrary_lane.
