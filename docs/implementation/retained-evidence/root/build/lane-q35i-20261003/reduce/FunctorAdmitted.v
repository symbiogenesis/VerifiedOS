(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35i reduction: the sealing functor of FunctorSealed with its lemma admitted
   inside the functor body. *)
Module Type ARG.
  Parameter a : nat.
End ARG.

Module Type SIG.
  Parameter x : nat.
  Axiom x_le : x <= x.
End SIG.

Module F (A : ARG) : SIG.
  Definition x := A.a.
  Lemma x_le : x <= x. Admitted.
End F.

Module Arg.
  Definition a := 2.
End Arg.

Module App := F Arg.

Theorem use : App.x <= App.x. Proof. exact App.x_le. Qed.
