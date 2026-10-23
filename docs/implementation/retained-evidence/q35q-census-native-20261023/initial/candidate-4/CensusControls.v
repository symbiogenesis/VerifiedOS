(* SPDX-License-Identifier: Apache-2.0 *)
From SailStdpp Require Import MachineWordInterface TypeCasts State_monad.
Module Type S.
Parameter T : Type.
Parameter value : T.
Inductive answer : Type := yes | no.
End S.
Module F (X : S).
Definition copied : X.T := X.value.
End F.
Module Concrete.
Definition T := nat.
Definition value : T := O.
Inductive answer : Type := yes | no.
End Concrete.
Module Sealed : S := Concrete.
Module Applied := F Concrete.
Module Empty. End Empty.
Module AliasOnly.
Notation copied_nat := nat.
End AliasOnly.
Module Type HiddenS.
Parameter witness : True.
End HiddenS.
Module HiddenImplementation.
Axiom hidden_control_axiom : True.
Definition witness : True := hidden_control_axiom.
End HiddenImplementation.
Module HiddenSealed : HiddenS := HiddenImplementation.
