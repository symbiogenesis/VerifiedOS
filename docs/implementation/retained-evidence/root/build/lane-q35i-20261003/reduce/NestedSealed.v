(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35i reduction: modules nested under an interactive seal whose type declares them.
   The checker replaces a body-less field of the seal with what its implementation
   uses only when, checking under that seal, it meets a constant with a body whose
   canonical name is that field. A nested structure body (O2) and the strengthened
   type of a nested transparent application (O3) supply one. A nested alias (O),
   whose constants keep the aliased module's canonical names, a nested application of
   a sealing functor (O4), whose fields have no body, and a nested ascribed alias (O5)
   do not, so their fields are named. *)
Module Type SIG.
  Parameter x : nat.
  Axiom x_le : x <= x.
End SIG.

Module Type OSIG.
  Declare Module Inner : SIG.
End OSIG.

Module Type ARG.
  Parameter a : nat.
End ARG.

Module Impl.
  Definition x := 1.
  Lemma x_le : x <= x. Proof. apply le_n. Qed.
End Impl.

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

Module O : OSIG.
  Module Inner := Impl.
End O.

Module O2 : OSIG.
  Module Inner.
    Definition x := 1.
    Lemma x_le : x <= x. Proof. apply le_n. Qed.
  End Inner.
End O2.

Module O3 : OSIG.
  Module Inner := G Arg.
End O3.

Module O4 : OSIG.
  Module Inner := F Arg.
End O4.

Module O5 : OSIG.
  Module Inner : SIG := Impl.
End O5.

Theorem use :
  O.Inner.x <= O.Inner.x /\ O2.Inner.x <= O2.Inner.x /\ O3.Inner.x <= O3.Inner.x
  /\ O4.Inner.x <= O4.Inner.x /\ O5.Inner.x <= O5.Inner.x.
Proof.
  exact (conj O.Inner.x_le (conj O2.Inner.x_le (conj O3.Inner.x_le
          (conj O4.Inner.x_le O5.Inner.x_le)))).
Qed.
