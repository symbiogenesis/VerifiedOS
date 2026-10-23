From SailStdpp Require Import MachineWordInterface.
Module NativeControls.
Module Type S.
Parameter T : Type.
Parameter value : T.
Inductive answer : Type := yes | no.
End S.
Module F (X : S).
Definition copied : X.T := X.value.
End F.
Module Empty. End Empty.
End NativeControls.
Declare ML Module "q35q_probe".
