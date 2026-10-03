(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35i negative controls: a top-level axiom that an alias-sealed field's
   implementation uses, and a sealed field whose implementation is itself a
   parameter. *)
Axiom genuine : False.

Module Type SIG.
  Parameter x : nat.
End SIG.

Module Impl.
  Definition x : nat := match genuine return nat with end.
End Impl.

Module Alias : SIG := Impl.

Module ParamImpl.
  Parameter x : nat.
End ParamImpl.

Module AliasP : SIG := ParamImpl.

Definition use : False := genuine.
