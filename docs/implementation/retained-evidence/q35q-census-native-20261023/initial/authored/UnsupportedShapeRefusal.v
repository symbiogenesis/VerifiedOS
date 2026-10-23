(* SPDX-License-Identifier: Apache-2.0 *)
Module Type UnsupportedS.
Parameter value : nat.
End UnsupportedS.
Declare Module Unsupported : UnsupportedS.
Declare ML Module "vos_rocq_census".
