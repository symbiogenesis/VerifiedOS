Require Q35i.AliasAdmitted.
Set Printing All.
Set Printing Depth 1000000.
Set Printing Width 1000000.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|Q35i.AliasAdmitted.Alias.x". Abort.
Print Assumptions Q35i.AliasAdmitted.Alias.x.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|Q35i.AliasAdmitted.Alias.x_le". Abort.
Print Assumptions Q35i.AliasAdmitted.Alias.x_le.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|Q35i.AliasAdmitted.Impl.x_le". Abort.
Print Assumptions Q35i.AliasAdmitted.Impl.x_le.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|Q35i.AliasAdmitted.use". Abort.
Print Assumptions Q35i.AliasAdmitted.use.
