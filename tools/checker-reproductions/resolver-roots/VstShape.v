(* SPDX-License-Identifier: Apache-2.0 *)
(* The anomaly in the shape VST 2.17's floyd/SeparationLogicAsLogicSoundness.v has, with
   its module names and nothing of its content: a functor (VST's DeepEmbedded) whose body
   seals a module (CConseq) against a signature with a `with Module` clause, the sealed
   body aliasing the functor's parameter as CSHL_Def, applied inside another functor's
   body (VST's DeepEmbeddedSoundness). rocq c accepts the file; rocqchk -silent -o aborts
   with exit 129 and the message naming
   Repro.VstShape.DeepEmbeddedSoundness.DeepEmbedded.CConseq.CSHL_Def and
   Repro.VstShape.DeepEmbedded.CConseq.CSHL_Def at releases 9.1.1, 9.2.0 and 9.3.0.
   VstShapeTransparent.v differs only in the ascription and checks. The reduction
   recorded in docs/assurance/checker-resolver-anomaly.md shows the alias and the
   `with Module` clause are not what triggers it; Minimal.v keeps only what does. *)

Module Type DEF.
  Parameter t : Type.
End DEF.

Module Type CONSEQ.
  Declare Module CSHL_Def : DEF.
End CONSEQ.

Module DeepEmbedded (Def : DEF).
  Module CConseq : CONSEQ with Module CSHL_Def := Def.
    Module CSHL_Def := Def.
  End CConseq.
End DeepEmbedded.

Module DeepEmbeddedSoundness (Def : DEF).
  Module DeepEmbedded := DeepEmbedded (Def).
End DeepEmbeddedSoundness.
