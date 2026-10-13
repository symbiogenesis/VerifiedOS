From stdpp Require Import base countable pretty.
Require Import SailStdpp.Base SailStdpp.ConcurrencyInterfaceTypes
  SailStdpp.ConcurrencyInterface SailStdpp.ConcurrencyInterfaceBuiltins.
Require Import Stdlib.Lists.List Stdlib.micromega.Lia.
Definition compatibility_probe_anchor : unit := tt.
Definition notation_probe (r : Explicit_access_kind) (e : Access_variety) :=
  sail_update (r with Explicit_access_kind_variety := e).
Lemma notation_probe_expansion r e :
  notation_probe r e =
  match r with Build_Explicit_access_kind _ f1 => Build_Explicit_access_kind e f1 end.
Proof. reflexivity. Qed.
