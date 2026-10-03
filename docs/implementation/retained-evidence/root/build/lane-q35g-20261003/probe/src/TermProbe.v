(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35g probe: the modules the canonical term loads once the term no longer
   requires SailStdpp.Real: the backend's imports for a concurrency-interface
   model, the stdpp header it emits, and riscv_extras.v's own requires. *)
From stdpp Require Import base countable pretty.
Require Import SailStdpp.Base SailStdpp.ConcurrencyInterfaceTypes
  SailStdpp.ConcurrencyInterface SailStdpp.ConcurrencyInterfaceBuiltins.
Require Import Stdlib.Lists.List Stdlib.micromega.Lia.
Definition q35g_probe_anchor : unit := tt.
