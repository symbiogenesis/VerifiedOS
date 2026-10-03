(* SPDX-License-Identifier: Apache-2.0 *)
(* Control for VstShape.v: the same file with CConseq transparently ascribed (<: in
   place of :), the alias and the `with Module` clause kept. rocq c accepts it and
   rocqchk -silent -o checks it with exit 0 at releases 9.1.1, 9.2.0 and 9.3.0. *)

Module Type DEF.
  Parameter t : Type.
End DEF.

Module Type CONSEQ.
  Declare Module CSHL_Def : DEF.
End CONSEQ.

Module DeepEmbedded (Def : DEF).
  Module CConseq <: CONSEQ with Module CSHL_Def := Def.
    Module CSHL_Def := Def.
  End CConseq.
End DeepEmbedded.

Module DeepEmbeddedSoundness (Def : DEF).
  Module DeepEmbedded := DeepEmbedded (Def).
End DeepEmbeddedSoundness.
