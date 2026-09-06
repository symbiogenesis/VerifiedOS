(* SPDX-License-Identifier: Apache-2.0 *)
(* The yardstick. Rupicola ships one wire-shaped derivation of its own, RFC
   1071's checksum over a byte array with an explicit length, and this file
   emits its C through the same printer so that the descriptor check's
   figures are taken beside a figure taken the same way. Nothing here is
   derived: the `Derive` is the package's, already closed in the switch, and
   the timing the record quotes for it comes from re-running the package's
   own `IPChecksum.v` in the staging directory, which the driver does. *)

Require Import Rupicola.Lib.Api.
Require Import Rupicola.Lib.ToCString.
Require Import Rupicola.Examples.Net.IPChecksum.IPChecksum.
Require Import Stdlib.Strings.String.

Definition ip_checksum_c : string :=
  Eval vm_compute in c_module [("ip_checksum", ip_checksum_br2fn)].

Goal True. idtac "=== ASSUMPTIONS ===". exact I. Qed.
Print Assumptions ip_checksum_br2fn_ok.
Redirect "ip_checksum" Compute ip_checksum_c.
