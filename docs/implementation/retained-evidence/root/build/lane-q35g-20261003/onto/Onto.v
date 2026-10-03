(* SPDX-License-Identifier: Apache-2.0 *)
(* Q35g: Rabst reaches every classical real, so a real choice made through a
   constructive Cauchy real and Rabst has the same results as one over R. *)
From Stdlib Require Import Reals.
Lemma q35g_Rabst_Rrepr (r : R) : RbaseSymbolsImpl.Rabst (RbaseSymbolsImpl.Rrepr r) = r.
Proof.
  apply RbaseSymbolsImpl.Rquot1.
  apply RbaseSymbolsImpl.Rquot2.
Qed.
Print Assumptions q35g_Rabst_Rrepr.
