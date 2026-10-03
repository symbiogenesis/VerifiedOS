(* SPDX-License-Identifier: Apache-2.0 *)
(* The smallest trigger found for the kernel checker's "Incompatible resolver roots"
   anomaly (F-486): a functor whose body opaquely ascribes a module holding a submodule,
   applied once. rocq c accepts the file; rocqchk -silent -o aborts with exit 129 at
   releases 9.1.1, 9.2.0 and 9.3.0. MinimalTransparent.v differs only in the
   ascription and checks. Authored from scratch for Q35h; it copies no upstream source. *)

Module Type S. End S.

Module F (X : S).
  Module M : S.
    Module N. End N.
  End M.
End F.

Module Z. End Z.

Module R := F Z.
