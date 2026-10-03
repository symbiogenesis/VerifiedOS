(* Q35f: the prelude's quotient and remainder externs, evaluated.

   model/model/prelude/prelude.sail binds quot_round_zero and
   rem_round_zero, and their nonnegative-dividend forms, to Z.quot and Z.rem
   under the Rocq backend's key. Their contract is the one the C and C++
   bindings (tdiv_int, tmod_int) and the names state: for a divisor m <> 0
   (the Sail types refuse m = 0), q = quot n m and r = rem n m satisfy
     n = q * m + r,  |r| < |m|,  r = 0 or sign r = sign n,
   and q rounds toward zero: |q| = floor (|n| / |m|), with q = 0 or
   sign q = sign n * sign m. The positive forms, for n >= 0 and m > 0, are
   also Sail's div and mod there, which are Euclidean.

   Each check below is decided by vm_compute over the stated inputs; `contract`
   is parametric in the functions so that floor division can be shown to fail
   it, which is the negative control. *)

From Stdlib Require Import ZArith List Bool.
Import ListNotations.
Open Scope Z_scope.

Definition contract (quot rem : Z -> Z -> Z) (n m : Z) : bool :=
  let q := quot n m in
  let r := rem n m in
  (n =? q * m + r)
  && (Z.abs r <? Z.abs m)
  && ((r =? 0) || (Z.sgn r =? Z.sgn n))
  && (Z.abs q =? Z.abs n / Z.abs m)
  && ((q =? 0) || (Z.sgn q =? Z.sgn n * Z.sgn m)).

(* Signed boundary values at the widths the model divides at, 8 to 64 bits, and
   past them, with small values of both signs. *)
Definition magnitudes : list Z :=
  [0; 1; 2; 3; 5; 7; 127; 128; 255; 256; 32767; 32768; 65535; 65536;
   2^31 - 1; 2^31; 2^32 - 1; 2^32; 2^63 - 1; 2^63; 2^64 - 1; 2^64; 2^65].

Definition signed (xs : list Z) : list Z := xs ++ map Z.opp xs.

Definition dividends : list Z := signed magnitudes.
Definition divisors : list Z := filter (fun m => negb (m =? 0)) (signed magnitudes).

Definition all_pairs (quot rem : Z -> Z -> Z) : bool :=
  forallb (fun n => forallb (fun m => contract quot rem n m) divisors) dividends.

Definition pairs_checked : Z := Z.of_nat (length dividends * length divisors).
Eval vm_compute in pairs_checked.

Example quot_rem_round_toward_zero : all_pairs Z.quot Z.rem = true.
Proof. vm_compute. reflexivity. Qed.

(* The most negative 64-bit and 32-bit dividends over -1 and 1: the quotient is
   the unbounded integer, which the model truncates to the register width. *)
Example most_negative :
  (Z.quot (-2^63) (-1), Z.rem (-2^63) (-1), Z.quot (-2^63) 1, Z.rem (-2^63) 1,
   Z.quot (-2^31) (-1), Z.rem (-2^31) (-1))
  = (2^63, 0, -2^63, 0, 2^31, 0).
Proof. vm_compute. reflexivity. Qed.

(* Round toward zero, not toward negative infinity, in each sign quadrant. *)
Example quadrants :
  (Z.quot 7 2, Z.rem 7 2, Z.quot (-7) 2, Z.rem (-7) 2,
   Z.quot 7 (-2), Z.rem 7 (-2), Z.quot (-7) (-2), Z.rem (-7) (-2))
  = (3, 1, -3, -1, -3, 1, 3, -1).
Proof. vm_compute. reflexivity. Qed.

(* The nonnegative forms agree with Euclidean division where their types admit
   them, n >= 0 and m > 0. *)
Example positive_forms :
  forallb (fun n => forallb (fun m => (Z.quot n m =? n / m) && (Z.rem n m =? n mod m))
                            (filter (fun m => 0 <? m) divisors))
          (filter (fun n => 0 <=? n) dividends) = true.
Proof. vm_compute. reflexivity. Qed.

(* Outside the contract: a zero divisor, which every binding's type refuses.
   Rocq's answer is recorded, not relied on. *)
Eval vm_compute in (Z.quot 5 0, Z.rem 5 0, Z.quot (-5) 0, Z.rem (-5) 0).

(* Negative control: floor division and its modulus fail the contract, so the
   check discriminates the rounding direction. *)
Example floor_refuted : all_pairs Z.div Z.modulo = false.
Proof. vm_compute. reflexivity. Qed.

Print Assumptions quot_rem_round_toward_zero.
