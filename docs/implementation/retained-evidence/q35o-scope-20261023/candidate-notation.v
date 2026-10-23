(* SPDX-License-Identifier: Apache-2.0 *)
Require Import SyntaxProbe_types SyntaxProbe.
Import -(notations) Defs.
Open Scope sail_concurrency_scope.
Definition bind_notation : M unit := returnM tt >>= (fun _ => returnM tt).
Definition bind_expansion : M unit := Defs.bind (returnM tt) (fun _ => returnM tt).
Goal bind_notation = bind_expansion. Proof. reflexivity. Qed.
Definition bind0_notation : M unit := returnM tt >> returnM tt.
Definition bind0_expansion : M unit := Defs.bind0 (returnM tt) (returnM tt).
Goal bind0_notation = bind0_expansion. Proof. reflexivity. Qed.
Definition pure_bind_notation : (unit + unit)%type := (inr tt : (unit + unit)%type) >>$= (fun (_ : unit) => inr tt).
Definition pure_bind_expansion : (unit + unit)%type := Defs.pure_early_return_bind (inr tt) (fun (_ : unit) => inr tt).
Goal pure_bind_notation = pure_bind_expansion. Proof. reflexivity. Qed.
Definition pure_bind0_notation : (unit + unit)%type := (inr tt : (unit + unit)%type) >>$ (inr tt : (unit + unit)%type).
Definition pure_bind0_expansion : (unit + unit)%type := Defs.pure_early_return_bind (inr tt) (fun _ : unit => inr tt).
Goal pure_bind0_notation = pure_bind0_expansion. Proof. reflexivity. Qed.
Print Assumptions bind_notation.
Print Assumptions bind0_notation.
Print Assumptions pure_bind_notation.
Print Assumptions pure_bind0_notation.
