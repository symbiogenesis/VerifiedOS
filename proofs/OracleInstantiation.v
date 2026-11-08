(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   OracleInstantiation.v

   Finite model-boundary witness for R-05-162a and R-17-049f: uniform
   enumeration of the four Boolean function tables (`bool -> bool`) defines
   an ideal distribution inside the logic without axioms, where any guesser
   predicting `oracle a b true` from `oracle a b false` succeeds on exactly
   2 of 4 tables, whereas instantiating the oracle with a constant function
   allows 4 of 4 successes.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-162a R-17-049f
   SHA256: cfd99c883b6c6cfe3117a038a1b818ad6b689c8c96116b3e0de59f721a7e3e77
   (*| END derived |*)
   ========================================================================= *)

Definition oracle (a b input : bool) : bool := if input then b else a.

Definition success (guess : bool -> bool) (a b : bool) : nat :=
  if guess (oracle a b false)
  then if oracle a b true then 1 else 0
  else if oracle a b true then 0 else 1.

Definition ideal_successes (guess : bool -> bool) : nat :=
  success guess false false + success guess false true +
  success guess true false + success guess true true.

Theorem fresh_ideal_answer_has_two_successes : forall guess,
  ideal_successes guess = 2.
Proof.
  intros guess. unfold ideal_successes, success, oracle.
  destruct (guess false), (guess true); reflexivity.
Qed.

Definition guess_false & bool : bool := false.

(* Four equal-weight seeds all select the same concrete constant function. *)
Definition constant_successes (guess : bool -> bool) : nat :=
  success guess false false + success guess false false +
  success guess false false + success guess false false.

Example constant_answer_is_always_predicted :
  constant_successes guess_false = 4 := eq_refl.

Theorem ideal_bound_does_not_transfer_to_every_implementation :
  ~ (forall guess, constant_successes guess = 2).
Proof.
  intro H. specialize (H guess_false). discriminate H.
Qed.

Example the_ideal_game_has_a_concrete_attacker :
  ideal_successes guess_false = 2 := eq_refl.
