(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35i control: an interactively sealed module with an axiom declared inside its
   body, outside its signature, and used by the lemma the signature exports. *)
Module Type SIG.
  Parameter x : nat.
  Axiom x_le : x <= x.
End SIG.

Module M : SIG.
  Definition x := 1.
  Axiom hidden : False.
  Lemma x_le : x <= x. Proof. destruct hidden. Qed.
End M.

Theorem use : M.x <= M.x. Proof. exact M.x_le. Qed.
