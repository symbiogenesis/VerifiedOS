(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35g probe: the modules the canonical term loads as Sail 0.20.3 emits it,
   SailStdpp.Real included, with riscv_extras.v's own requires. *)
From stdpp Require Import base countable pretty.
Require Import SailStdpp.Base SailStdpp.Real SailStdpp.ConcurrencyInterfaceTypes
  SailStdpp.ConcurrencyInterface SailStdpp.ConcurrencyInterfaceBuiltins.
Require Import Stdlib.Lists.List Stdlib.micromega.Lia.
Definition q35g_probe_anchor : unit := tt.
