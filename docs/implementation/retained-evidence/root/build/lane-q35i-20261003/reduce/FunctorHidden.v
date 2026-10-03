(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35i reduction: the sealing functor of FunctorSealed with an axiom declared
   inside the functor body, outside its result signature, and used by the lemma
   the signature exports. *)
Module Type ARG.
  Parameter a : nat.
End ARG.

Module Type SIG.
  Parameter x : nat.
  Axiom x_le : x <= x.
End SIG.

Module F (A : ARG) : SIG.
  Definition x := A.a.
  Axiom hidden : False.
  Lemma x_le : x <= x. Proof. destruct hidden. Qed.
End F.

Module Arg.
  Definition a := 2.
End Arg.

Module App := F Arg.

Theorem use : App.x <= App.x. Proof. exact App.x_le. Qed.
