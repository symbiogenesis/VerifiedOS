(* SPDX-License-Identifier: Apache-2.0 *)
Require CensusControls.
Set Printing All.
Set Printing Universes.
Set Printing Width 1000000.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|CensusControls.HiddenSealed.witness". Abort.
Print Assumptions CensusControls.HiddenSealed.witness.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|CensusControls.HiddenAlias.witness". Abort.
Print Assumptions CensusControls.HiddenAlias.witness.
