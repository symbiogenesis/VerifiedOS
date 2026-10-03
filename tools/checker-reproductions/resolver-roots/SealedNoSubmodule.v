(* SPDX-License-Identifier: Apache-2.0 *)
(* Control for VstShape.v: the sealed module holds a constant and no submodule. rocq c
   accepts it and rocqchk -silent -o checks it with exit 0 at releases 9.2.0 and 9.3.0,
   so a seal inside an applied functor body is not enough on its own; the sealed module
   must hold a module field. *)

Module Type DEF.
  Parameter t : Type.
End DEF.

Module Type CONSEQ.
  Parameter n : nat.
End CONSEQ.

Module DeepEmbedded (Def : DEF).
  Module CConseq : CONSEQ.
    Definition n := 0.
  End CConseq.
End DeepEmbedded.

Module DeepEmbeddedSoundness (Def : DEF).
  Module DeepEmbedded := DeepEmbedded (Def).
End DeepEmbeddedSoundness.
