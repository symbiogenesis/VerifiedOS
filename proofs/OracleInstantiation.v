(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   Q28a's finite model-boundary witness for R-05-162a and R-17-049f.
   This is not a GCM reduction, a cryptographic hash, or a quantum game.
   Uniformly enumerating the four Boolean function tables defines the ideal
   distribution inside the logic. No axiom supplies its randomness. An attacker
   reads the answer at false and guesses the answer at the fresh input true.
   Counting successes gives the numerator over four equally weighted tables.
   Replacing that distribution by a constant function changes the experiment,
   even though both computations and their proofs have no global assumptions.
   No claim annotation discharges a platform requirement from this toy model.
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

Definition guess_false (_ : bool) : bool := false.

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

Print Assumptions fresh_ideal_answer_has_two_successes.
Print Assumptions constant_answer_is_always_predicted.
Print Assumptions ideal_bound_does_not_transfer_to_every_implementation.
Print Assumptions the_ideal_game_has_a_concrete_attacker.
