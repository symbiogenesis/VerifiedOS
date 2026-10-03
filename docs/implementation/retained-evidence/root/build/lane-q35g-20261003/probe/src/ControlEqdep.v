(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35g positive control: TermProbe's modules plus Stdlib's Eqdep, which
   loads exactly one of the five axioms, eq_rect_eq. *)
From stdpp Require Import base countable pretty.
Require Import SailStdpp.Base SailStdpp.ConcurrencyInterfaceTypes
  SailStdpp.ConcurrencyInterface SailStdpp.ConcurrencyInterfaceBuiltins.
Require Import Stdlib.Lists.List Stdlib.micromega.Lia.
From Stdlib Require Eqdep.
Definition q35g_probe_anchor : unit := tt.
