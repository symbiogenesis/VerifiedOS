(* SPDX-License-Identifier: Apache-2.0 *)
From SailStdpp Require Import MachineWordInterface.
Set Universe Polymorphism.
Module NativeControls.
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
Module Type DependentTypes.
Parameter case_probe : forall b : bool, match b with true => nat | false => bool end.
Parameter fix_probe : forall n : nat,
  (fix loop (k : nat) : Type := match k with O => nat | S j => loop j end) n.
Parameter let_probe : let T := nat in T.
Parameter lambda_probe : (fun T : Type => T) nat.
End DependentTypes.
End NativeControls.
Declare ML Module "vos_rocq_census".
