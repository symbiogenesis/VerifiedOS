(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35i reduction: functor applications. F seals its result; G does not. App and
   AppT apply them without an ascription, AppSealed and AppTSealed with one. *)
Module Type ARG.
  Parameter a : nat.
End ARG.

Module Type SIG.
  Parameter x : nat.
  Axiom x_le : x <= x.
End SIG.

Module F (A : ARG) : SIG.
  Definition x := A.a.
  Lemma x_le : x <= x. Proof. apply le_n. Qed.
End F.

Module G (A : ARG).
  Definition x := A.a.
  Lemma x_le : x <= x. Proof. apply le_n. Qed.
End G.

Module Arg.
  Definition a := 2.
End Arg.

Module App := F Arg.
Module AppSealed : SIG := F Arg.
Module AppT := G Arg.
Module AppTSealed : SIG := G Arg.

Theorem use : App.x <= App.x. Proof. exact App.x_le. Qed.
Theorem use_t : AppT.x <= AppT.x. Proof. exact AppT.x_le. Qed.
