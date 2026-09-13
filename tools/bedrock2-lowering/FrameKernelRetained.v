(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   FrameKernelRetained.v

   The frame service's pure value kernel, authored inside Rupicola's subset in
   its two-live-array shape and lowered to bedrock2 by relational compilation,
   then to C by bedrock2's printer. This is the retained half of the census
   pair: the input buffer is read and never written, the mapped values are
   written into a second buffer while the checksum accumulates, and the XOR
   pass runs over that second buffer. It is the shape a caller needs when the
   input is borrowed rather than disposable, which is the assumption the
   `lexical-cache` row of `tools/vos/static_memory_transform.py` keeps and the
   `in-place-phased` row drops.

   What the function computes. For a byte buffer `bs`, an output buffer `out`
   of the same declared size and a length `len` no larger than either,

     t[i] = (3 * bs[i] + 1) mod 256      for i < len
     c    = (t[0] + ... + t[len-1]) mod 256
     out[i] = t[i] XOR c

   with `bs` returned unchanged. `frame_value` states the same value in plain
   list vocabulary, and the examples below check the two against each other on
   concrete frames. Those examples are bounded executable agreement and not a
   theorem: no lemma here relates the loop to the list reference at every input.

   What it does not decide. Nothing here is a frame service. There is no
   descriptor, no staging, no reservation, no retirement and no zeroization,
   and both buffers' storage is the caller's, so the second buffer this variant
   needs is charged nowhere in this file. The census this file feeds is an
   emitted-instruction count on plain RV64, the target R-18-002 forbids, so
   every figure taken from it is a proxy and never a target measurement. See
   `docs/implementation/static-memory-census.md`.

   Where the second live array shows in the emitted code. The first loop
   addresses two base pointers, one loaded from and one stored to, so the C
   carries a second array parameter and a second address computation in that
   loop; FrameKernelInPlace.v is the same program with that store sent back to
   the buffer it read, and the census reads the difference between the two.
   ========================================================================= *)

Require Import Rupicola.Lib.Api.
Require Import Rupicola.Lib.Arrays.
Require Import Rupicola.Lib.Loops.
Require Import Rupicola.Lib.ToCString.
Require Import bedrock2.BasicC64Semantics.

Module FrameRetained.
  Import BasicC64Semantics.
  Import LoopCompiler.
  Import SizedListArrayCompiler.

  (* ---- the value the kernel carries ----------------------------------- *)

  Definition mapped (b : byte) : byte :=
    byte.of_Z (3 * byte.unsigned b + 1).

  Definition add_byte (acc b : byte) : byte :=
    byte.of_Z (byte.unsigned acc + byte.unsigned b).

  Definition checksum (bs : list byte) : byte :=
    List.fold_left add_byte (List.map mapped bs) Byte.x00.

  Definition frame_value (bs : list byte) : list byte :=
    List.map (fun b => byte.xor (mapped b) (checksum bs)) bs.

  (* ---- the function, authored in the subset --------------------------- *)

  Definition frame_kernel_retained (bs out : ListArray.t byte) (len : word)
    : ListArray.t byte * ListArray.t byte :=
    let/n c := Byte.x00 in
    let/n (c, out) :=
      ranged_for_u (word.of_Z 0) len
        (fun '\< c, out \> tok idx _ =>
           let/n v := ListArray.get bs idx in
           let/n v := mapped v in
           let/n c := add_byte c v in
           let/n out := ListArray.put out idx v in
           (tok, \< c, out \>))
        \< c, out \> in
    let/n out :=
      ranged_for_u (word.of_Z 0) len
        (fun out tok idx _ =>
           let/n v := ListArray.get out idx in
           let/n v := byte.xor v c in
           let/n out := ListArray.put out idx v in
           (tok, out))
        out in
    (bs, out).

  (* Bounded agreement with the list reference, at the whole buffer, with the
     input returned unchanged. Each is a closed computation and none of them is
     a statement about every input. *)
  Example agrees_empty :
    frame_kernel_retained [] [] (word.of_Z 0) = ([], frame_value []).
  Proof. vm_compute; reflexivity. Qed.

  Example agrees_edges :
    frame_kernel_retained [Byte.x00; Byte.x01; Byte.x7f; Byte.xff]
                          [Byte.x00; Byte.x00; Byte.x00; Byte.x00]
                          (word.of_Z 4)
    = ([Byte.x00; Byte.x01; Byte.x7f; Byte.xff],
       frame_value [Byte.x00; Byte.x01; Byte.x7f; Byte.xff]).
  Proof. vm_compute; reflexivity. Qed.

  Example agrees_wrapping :
    frame_kernel_retained [Byte.x55; Byte.xaa; Byte.x80; Byte.x03; Byte.xfe]
                          [Byte.xff; Byte.xff; Byte.xff; Byte.xff; Byte.xff]
                          (word.of_Z 5)
    = ([Byte.x55; Byte.xaa; Byte.x80; Byte.x03; Byte.xfe],
       frame_value [Byte.x55; Byte.xaa; Byte.x80; Byte.x03; Byte.xfe]).
  Proof. vm_compute; reflexivity. Qed.

  (* ---- the relation --------------------------------------------------- *)

  #[global]
  Instance spec_of_frame_kernel_retained : spec_of "frame_kernel_retained" :=
    fnspec! "frame_kernel_retained" bs_ptr out_ptr len /
      (n : nat) (bs out : ListArray.t byte)
      (pr : word.unsigned len <= Z.of_nat n) R,
    { requires tr mem :=
        (sizedlistarray_value AccessByte n bs_ptr bs *
         sizedlistarray_value AccessByte n out_ptr out * R)%sep mem;
      ensures tr' mem' :=
        tr' = tr /\
        (sizedlistarray_value AccessByte n bs_ptr
           (fst (frame_kernel_retained bs out len)) *
         sizedlistarray_value AccessByte n out_ptr
           (snd (frame_kernel_retained bs out len)) * R)%sep mem' }.

  (* The one compilation hint the pair needs. A byte-valued step lands back in
     the array through `ai_to_word`, which is `word.of_Z (byte.unsigned _)`, so
     the goal reads `byte.unsigned (byte.of_Z z)`; Rupicola's expression
     compiler reaches `byte.wrap z` and this is the step between them. It is
     stated here rather than rewritten into the term so that the locals the
     array lemma expects keep their `byte.of_Z` shape. *)
  Lemma expr_compile_byte_unsigned_of_Z
        (m : @map.rep _ _ mem) (l : @map.rep _ _ locals) (e : Syntax.expr) (z : Z) :
    WeakestPrecondition.dexpr m l e (word.of_Z (byte.wrap z)) ->
    WeakestPrecondition.dexpr m l e (word.of_Z (byte.unsigned (byte.of_Z z))).
  Proof. rewrite byte.unsigned_of_Z; exact (fun h => h). Qed.

  #[local] Hint Extern 4
    (WeakestPrecondition.dexpr _ _ _ (word.of_Z (byte.unsigned (byte.of_Z _)))) =>
    simple eapply expr_compile_byte_unsigned_of_Z : expr_compiler.

  #[local] Hint Unfold mapped add_byte : compiler_cleanup.
  #[local] Hint Extern 1 => lia : compiler_side_conditions.

  Derive frame_kernel_retained_br2fn SuchThat
         (defn! "frame_kernel_retained"("bs", "out", "len")
              { frame_kernel_retained_br2fn },
          implements frame_kernel_retained)
         As frame_kernel_retained_br2fn_ok.
  Proof.
    Time compile.
  Time Qed.

  Definition frame_kernel_retained_c : string :=
    Eval vm_compute in
      c_module [("frame_kernel_retained", frame_kernel_retained_br2fn)].
End FrameRetained.

Require Import Coq.Strings.String.
Goal True. idtac "=== ASSUMPTIONS ===". exact I. Qed.
Print Assumptions FrameRetained.frame_kernel_retained_br2fn_ok.
Redirect "frame_kernel_retained" Compute FrameRetained.frame_kernel_retained_c.
