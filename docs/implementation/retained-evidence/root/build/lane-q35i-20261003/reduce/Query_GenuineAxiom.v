Require Q35i.GenuineAxiom.
Set Printing All.
Set Printing Depth 1000000.
Set Printing Width 1000000.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|Q35i.GenuineAxiom.genuine". Abort.
Print Assumptions Q35i.GenuineAxiom.genuine.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|Q35i.GenuineAxiom.Alias.x". Abort.
Print Assumptions Q35i.GenuineAxiom.Alias.x.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|Q35i.GenuineAxiom.AliasP.x". Abort.
Print Assumptions Q35i.GenuineAxiom.AliasP.x.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|Q35i.GenuineAxiom.ParamImpl.x". Abort.
Print Assumptions Q35i.GenuineAxiom.ParamImpl.x.
Goal True. Proof. idtac "VOS_PROOF_AUDIT|Q35i.GenuineAxiom.use". Abort.
Print Assumptions Q35i.GenuineAxiom.use.
