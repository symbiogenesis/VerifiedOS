(* SPDX-License-Identifier: Apache-2.0 *)
(* VstShape.v with one constant added to the sealed module, typed through the module's
   own alias field. rocq c accepts the file. rocqchk -silent -o aborts with exit 129 in
   every case, but the message differs by release: "Incompatible resolver roots" at
   9.1.1, and "Type error: IllFormedConstant" at 9.2.0 and 9.3.0, which the checker
   raises first on this file. Typing the constant through Def.t instead restores the
   resolver-roots message at every release. *)

Module Type DEF.
  Parameter t : Type.
End DEF.

Module Type CONSEQ.
  Declare Module CSHL_Def : DEF.
  Parameter conseq : CSHL_Def.t -> Prop.
End CONSEQ.

Module DeepEmbedded (Def : DEF).
  Module CConseq : CONSEQ with Module CSHL_Def := Def.
    Module CSHL_Def := Def.
    Definition conseq (x : CSHL_Def.t) : Prop := True.
  End CConseq.
End DeepEmbedded.

Module DeepEmbeddedSoundness (Def : DEF).
  Module DeepEmbedded := DeepEmbedded (Def).
End DeepEmbeddedSoundness.
