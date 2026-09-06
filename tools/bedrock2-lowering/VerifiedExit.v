(* SPDX-License-Identifier: Apache-2.0 *)
(* The verified exit, run over this component rather than over M1.6's probe:
   coq-bedrock2-compiler over coq-riscv, at the width and instruction set the
   shipped recipe instantiates, `Words32Naive` and `RV32I`, so that the
   alphabet it emits for the descriptor check is measured here and not
   carried from the memequal figure. Two things this file does not claim. The
   theorem this exit transports is the compiler's own, about that 32-bit
   machine, which is the target R-18-002 forbids at either width; and the
   derivation in DescriptorCheck.v is stated over 64-bit words, so nothing
   here relates the two instantiations. What is measured is the instruction
   census: how many, over which mnemonics, and that none is a capability
   instruction, riscv-coq's `InstructionSet` having no arm for one. The
   instance block is the shipped compilerExamples recipe's, reproduced
   because the opam package installs the compiler and not its examples. *)

Require Import Coq.Lists.List. Import ListNotations.
Require Import Coq.Init.Byte.
Require Import coqutil.Decidable.
Require Import bedrock2.NotationsCustomEntry coqutil.Macros.WithBaseName.
Require Import compiler.ExprImp.
Require Import compiler.NameGen.
Require Import compiler.Pipeline.
Require Import riscv.Spec.Decode.
Require Import riscv.Utility.Words32Naive.
Require Import riscv.Utility.DefaultMemImpl32.
Require Import riscv.Utility.Monads.
Require Import compiler.util.Common.
Require Import riscv.Utility.Encode.
Require Import coqutil.Map.SortedList.
Require Import compiler.MemoryLayout.
Require Import compiler.StringNameGen.
Require Import riscv.Utility.InstructionCoercions.
Require Import compiler.MMIO.
Require Import bedrock2.FE310CSemantics.
Require Import coqutil.Map.SortedListZ.
Require Import DescriptorCheck.

Open Scope Z_scope. Open Scope string_scope. Open Scope ilist_scope.

Local Existing Instance coqutil.Map.SortedListString.map.
Local Existing Instance coqutil.Map.SortedListString.ok.
Local Instance mem32 : map.map Words32Naive.word Init.Byte.byte
  := SortedListWord.map Words32Naive.word byte.
Local Instance mem32_ok : map.ok mem32 := SortedListWord.ok _ _.
Local Instance localsL32 : map.map Z Words32Naive.word := SortedListZ.map Words32Naive.word.
Local Instance localsL32_ok : map.ok localsL32 := SortedListZ.ok _.
Local Instance localsH32 : map.map string Words32Naive.word := SortedListString.map Words32Naive.word.
Local Instance localsH32_ok : map.ok localsH32 := SortedListString.ok _.
Local Instance RV32I_bitwidth : FlatToRiscvCommon.bitwidth_iset 32 RV32I := eq_refl.

Definition fs := [("descriptor_check", Descriptor.descriptor_check_br2fn)].
Definition instrs :=
  match (compile compile_ext_call fs) with
  | Success (instrs, _, _) => instrs
  | _ => nil
  end.

Goal True. idtac "=== INSTRUCTION COUNT ===". exact I. Qed.
Compute List.length instrs.
Goal True. idtac "=== THE EMITTED INSTRUCTION LIST ===". exact I. Qed.
Compute instrs.
Goal True. idtac "=== ENCODED WORD COUNT ===". exact I. Qed.
Compute List.length (List.map Encode.encode instrs).
