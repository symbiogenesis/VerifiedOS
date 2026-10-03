(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35i reduction, authored for this qualification: an alias-sealed module whose
   fields are all defined or proved. Controls: a nested alias, a `with` constraint,
   a transparent alias, an Include of the sealed module, and an interactively
   sealed module with the same signature and the same bodies. *)
Module Type SIG.
  Parameter x : nat.
  Axiom x_le : x <= x.
  Parameter f : nat -> nat.
End SIG.

Module Impl.
  Definition x := 1.
  Lemma x_le : x <= x. Proof. apply le_n. Qed.
  Definition f (n : nat) := n.
End Impl.

Module Alias : SIG := Impl.
Module Nested : SIG := Alias.
Module Constrained : SIG with Definition x := Impl.x := Impl.
Module Transparent := Impl.
Module Included. Include Alias. End Included.

Module Inter : SIG.
  Definition x := 1.
  Lemma x_le : x <= x. Proof. apply le_n. Qed.
  Definition f (n : nat) := n.
End Inter.

Theorem use : Alias.x <= Alias.x. Proof. exact Alias.x_le. Qed.
Theorem use_nested : Nested.x <= Nested.x. Proof. exact Nested.x_le. Qed.
Theorem use_inter : Inter.x <= Inter.x. Proof. exact Inter.x_le. Qed.
