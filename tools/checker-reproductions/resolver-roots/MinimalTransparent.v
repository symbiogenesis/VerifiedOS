(* SPDX-License-Identifier: Apache-2.0 *)
(* Control for Minimal.v: the same file with the inner module transparently ascribed
   (<: in place of :). rocq c accepts it and rocqchk -silent -o checks it with exit 0 at
   releases 9.1.1, 9.2.0 and 9.3.0. *)

Module Type S. End S.

Module F (X : S).
  Module M <: S.
    Module N. End N.
  End M.
End F.

Module Z. End Z.

Module R := F Z.
