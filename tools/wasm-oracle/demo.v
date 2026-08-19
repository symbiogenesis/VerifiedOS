(* M1.5 smoke program for the CertiCoq -> Wasm oracle.

   The shape mirrors the oracle's intended use (§0, §4 of the
   implementation checklist): a pure Gallina computation checked against a
   known answer *inside* Gallina, so the Wasm side only has to carry one
   boolean out. *)

From Stdlib Require Import Arith.
From CertiRocq.Plugin Require Import CertiRocq.

Fixpoint fib (n : nat) : nat :=
  match n with
  | O => O
  | S m => match m with
           | O => 1
           | S k => fib m + fib k
           end
  end.

Definition oracle_demo : bool := Nat.eqb (fib 20) 6765.

CertiRocq Compile Wasm oracle_demo.
