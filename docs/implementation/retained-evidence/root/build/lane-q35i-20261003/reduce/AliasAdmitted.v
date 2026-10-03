(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35i reduction: the alias-sealed module of AliasSealed with its lemma admitted
   in the implementation. *)
Module Type SIG.
  Parameter x : nat.
  Axiom x_le : x <= x.
End SIG.

Module Impl.
  Definition x := 1.
  Lemma x_le : x <= x. Admitted.
End Impl.

Module Alias : SIG := Impl.

Theorem use : Alias.x <= Alias.x. Proof. exact Alias.x_le. Qed.
