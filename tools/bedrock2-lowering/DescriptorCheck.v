(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   DescriptorCheck.v

   The ring descriptor header check, authored inside Rupicola's subset and
   lowered to bedrock2 by relational compilation, then to C by bedrock2's
   printer. Q2a's component: bounded, wire-parser-shaped, with an error path
   and explicit buffer bounds, and every layout constant read from the
   generated interface artifact rather than typed here.

   What the function decides. `descriptor_check bs len` reads a descriptor
   from a byte buffer of declared length `len` and answers R-12-093's
   `status_ok` when the header is well formed under the profile's encoding
   rows, and `status_invalid` otherwise. It checks, in wire order: that the
   buffer holds a tag byte; that the tag is a case index below the operation
   count (WF-7); that the buffer holds the operation's packed descriptor
   (WF-6, no interior padding); each buffer reference's direction and content
   type discriminants (WF-7 over WF-11's two enumerations); the optional
   deadline's presence discriminant, `0` with no payload or `1` followed by a
   class index below the class count (WF-8, WF-7); and the flag set, every bit
   above the declared flag count zero (WF-10). No byte past `len` is read on
   any path: every read is preceded by the length test that admits it, and
   the derivation below discharges that side condition at each read.

   What it does not decide. The request identifier, the operation's scalars
   and each reference's session index, offset and length are `validated_at_use`
   in the owner and pass through untouched; R-12-092's validation of bounds,
   permissions and generation against the session table is the server's, after
   this check. Bytes past the descriptor inside `len` are the slot's and not a
   field, so they are not read. A descriptor is checked and never copied.

   Where the constants come from. `RingContract.v` is generated from
   `interfaces/ring-reference.json` and held byte-identical to its generator
   by rule K-89; this file imports it and evaluates every offset, size and
   case count from its definitions at compile time, so a change to the
   declaration reaches the emitted C through one regeneration. The two things
   this file states rather than reads are the case indices of `op` and
   `status`, which WF-7 fixes as declaration order and Gallina cannot reflect:
   each is a total match, so a constructor added to or removed from the owner
   fails this file rather than drifting past it. The two-case enumerations are
   held complete by the lemmas beside their lists.
   ========================================================================= *)

Require Import Rupicola.Lib.Api.
Require Import Rupicola.Lib.Arrays.
Require Import Rupicola.Lib.ToCString.
Require Import bedrock2.BasicC64Semantics.
Require Import RingContract.

Module Descriptor.
  Import BasicC64Semantics.
  Import UnsizedListArrayCompiler.

  (* ---- the owner, read ---------------------------------------------- *)

  (* WF-7: a case index in declaration order. *)
  Definition op_tag (o : op) : Z :=
    match o with
    | op_read_extent => 0
    | op_write_extent => 1
    | op_flush => 2
    | op_query_geometry => 3
    | op_poll_status => 4
    end.

  Definition status_code (s : status) : Z :=
    match s with
    | status_ok => 0
    | status_refused => 1
    | status_invalid => 2
    | status_cancelled => 3
    | status_deadline_expired => 4
    | status_peer_restarted => 5
    | status_device_fault => 6
    | status_resource_exhausted => 7
    end.

  Definition direction_cases : list direction :=
    [direction_to_server; direction_to_client].
  Lemma direction_cases_complete (d : direction) : In d direction_cases.
  Proof. destruct d; simpl; auto. Qed.

  Definition content_cases : list content_type :=
    [content_opaque_bytes; content_frame_extent].
  Lemma content_cases_complete (c : content_type) : In c content_cases.
  Proof. destruct c; simpl; auto. Qed.

  (* Offsets in the packed encoding, by the owner's section order: the tag,
     the request identifier, the scalars, the buffer references, the
     optional deadline, the flag set. *)
  Definition refs_off (o : op) : Z :=
    Z.of_nat (tag_width + enc_request_id_bytes + op_scalar_bytes o).
  Definition ref_direction_off (o : op) (i : nat) : Z :=
    refs_off o
    + Z.of_nat (i * buffer_ref_bytes
                + enc_session_index_bytes + enc_offset_bytes + enc_length_bytes).
  Definition ref_content_off (o : op) (i : nat) : Z :=
    ref_direction_off o i + Z.of_nat enc_direction_bytes.
  Definition deadline_off (o : op) : Z :=
    refs_off o + Z.of_nat (op_buffer_refs o * buffer_ref_bytes).
  (* the packed size with the deadline present, which is the owner's figure *)
  Definition full_bytes (o : op) : Z := Z.of_nat (descriptor_bytes o).

  (* ---- the numerals the lowered code carries -------------------------- *)

  Definition code_ok : Z := Eval compute in status_code status_ok.
  Definition code_invalid : Z := Eval compute in status_code status_invalid.
  Definition tag_count : Z := Eval compute in Z.of_nat op_count.
  Definition direction_count : Z := Eval compute in Z.of_nat (length direction_cases).
  Definition content_count : Z := Eval compute in Z.of_nat (length content_cases).
  Definition deadline_count : Z := Eval compute in Z.of_nat deadline_class_count.
  Definition flag_limit : Z := Eval compute in Z.shiftl 1 (Z.of_nat flag_count).

  (* The two extent operations share one arm below; this is what admits it. *)
  Definition tag_read : Z := Eval compute in op_tag op_read_extent.
  Definition tag_write : Z := Eval compute in op_tag op_write_extent.
  Definition tag_flush : Z := Eval compute in op_tag op_flush.
  Definition tag_query : Z := Eval compute in op_tag op_query_geometry.
  Definition tag_poll : Z := Eval compute in op_tag op_poll_status.
  Lemma extent_arm_shared :
    tag_read = 0 /\ tag_write = 1
    /\ op_scalar_bytes op_read_extent = op_scalar_bytes op_write_extent
    /\ op_buffer_refs op_read_extent = op_buffer_refs op_write_extent
    /\ op_has_deadline op_read_extent = op_has_deadline op_write_extent.
  Proof. repeat split; reflexivity. Qed.
  Definition extent_tags_end : Z := Eval compute in tag_write + 1.

  Definition ext_dir0 : Z := Eval compute in ref_direction_off op_read_extent 0.
  Definition ext_ct0 : Z := Eval compute in ref_content_off op_read_extent 0.
  Definition ext_dir1 : Z := Eval compute in ref_direction_off op_read_extent 1.
  Definition ext_ct1 : Z := Eval compute in ref_content_off op_read_extent 1.
  Definition ext_dl : Z := Eval compute in deadline_off op_read_extent.
  Definition ext_dl_class : Z := Eval compute in deadline_off op_read_extent + 1.
  Definition ext_flags_absent : Z := Eval compute in deadline_off op_read_extent + 1.
  Definition ext_flags_present : Z := Eval compute in deadline_off op_read_extent + 2.
  Definition ext_min : Z := Eval compute in full_bytes op_read_extent - 1.
  Definition ext_full : Z := Eval compute in full_bytes op_read_extent.

  Definition flush_dl : Z := Eval compute in deadline_off op_flush.
  Definition flush_dl_class : Z := Eval compute in deadline_off op_flush + 1.
  Definition flush_flags_absent : Z := Eval compute in deadline_off op_flush + 1.
  Definition flush_flags_present : Z := Eval compute in deadline_off op_flush + 2.
  Definition flush_min : Z := Eval compute in full_bytes op_flush - 1.
  Definition flush_full : Z := Eval compute in full_bytes op_flush.

  Definition query_dir0 : Z := Eval compute in ref_direction_off op_query_geometry 0.
  Definition query_ct0 : Z := Eval compute in ref_content_off op_query_geometry 0.
  Definition query_flags : Z := Eval compute in deadline_off op_query_geometry.
  Definition query_full : Z := Eval compute in full_bytes op_query_geometry.

  Definition poll_flags : Z := Eval compute in deadline_off op_poll_status.
  Definition poll_full : Z := Eval compute in full_bytes op_poll_status.

  (* The arms' reads sit where the owner says the fields are: each operation
     that carries no deadline puts its flag byte last, and each that carries
     one puts the presence byte first among the tail bytes. *)
  Lemma tails_agree :
    ext_flags_present = ext_full - 1 /\ flush_flags_present = flush_full - 1
    /\ query_flags = query_full - 1 /\ poll_flags = poll_full - 1
    /\ op_has_deadline op_read_extent = true /\ op_has_deadline op_flush = true
    /\ op_has_deadline op_query_geometry = false /\ op_has_deadline op_poll_status = false.
  Proof. repeat split; reflexivity. Qed.

  (* ---- the function ------------------------------------------------- *)

  Definition invalid : word := word.of_Z code_invalid.
  Definition ok_word : word := word.of_Z code_ok.

  (* WF-10: the flag byte, every bit above the declared count zero. *)
  Definition flags_ok (f : byte) : bool :=
    word.ltu (word_of_byte f : word) (word.of_Z flag_limit).

  (* WF-7 over WF-11's two enumerations, for one buffer reference. *)
  Definition ref_ok (bs : ListArray.t byte) (dir ct : Z) : bool :=
    let/n d := ListArray.get bs dir in
    let/n ok := word.ltu (word_of_byte d : word) (word.of_Z direction_count) in
    if ok then
      let/n c := ListArray.get bs ct in
      let/n ok := word.ltu (word_of_byte c : word) (word.of_Z content_count) in
      ok
    else ok.

  (* WF-8 then WF-10: the presence discriminant, the class it admits, and
     the flag byte wherever the option leaves it. *)
  Definition check_deadline_tail (bs : ListArray.t byte) (len : word)
             (dl dl_class flags_absent flags_present full : Z) : word :=
    let/n p := ListArray.get bs dl in
    let/n absent := word.eqb (word_of_byte p : word) (word.of_Z 0) in
    if absent then
      let/n f := ListArray.get bs flags_absent in
      let/n ok := flags_ok f in
      if ok then let/n st := ok_word in st
      else let/n st := invalid in st
    else
      let/n present := word.eqb (word_of_byte p : word) (word.of_Z 1) in
      if present then
        let/n too_short := word.ltu len (word.of_Z full) in
        if too_short then let/n st := invalid in st
        else
          let/n cls := ListArray.get bs dl_class in
          let/n cls_ok := word.ltu (word_of_byte cls : word) (word.of_Z deadline_count) in
          if cls_ok then
            let/n f := ListArray.get bs flags_present in
            let/n ok := flags_ok f in
            if ok then let/n st := ok_word in st
            else let/n st := invalid in st
          else let/n st := invalid in st
      else let/n st := invalid in st.

  Definition descriptor_check (bs : ListArray.t byte) (len : word) : word :=
    let/n no_tag := word.ltu len (word.of_Z 1) in
    if no_tag then let/n st := invalid in st
    else
      let/n tag := ListArray.get bs 0 in
      let/n tag_ok := word.ltu (word_of_byte tag : word) (word.of_Z tag_count) in
      if tag_ok then
        let/n is_extent := word.ltu (word_of_byte tag : word) (word.of_Z extent_tags_end) in
        if is_extent then
          let/n too_short := word.ltu len (word.of_Z ext_min) in
          if too_short then let/n st := invalid in st
          else
            let/n ok := ref_ok bs ext_dir0 ext_ct0 in
            if ok then
              let/n ok := ref_ok bs ext_dir1 ext_ct1 in
              if ok then
                check_deadline_tail bs len ext_dl ext_dl_class
                                    ext_flags_absent ext_flags_present ext_full
              else let/n st := invalid in st
            else let/n st := invalid in st
        else
          let/n is_flush := word.eqb (word_of_byte tag : word) (word.of_Z tag_flush) in
          if is_flush then
            let/n too_short := word.ltu len (word.of_Z flush_min) in
            if too_short then let/n st := invalid in st
            else
              check_deadline_tail bs len flush_dl flush_dl_class
                                  flush_flags_absent flush_flags_present flush_full
          else
            let/n is_query := word.eqb (word_of_byte tag : word) (word.of_Z tag_query) in
            if is_query then
              let/n too_short := word.ltu len (word.of_Z query_full) in
              if too_short then let/n st := invalid in st
              else
                let/n ok := ref_ok bs query_dir0 query_ct0 in
                if ok then
                  let/n f := ListArray.get bs query_flags in
                  let/n ok := flags_ok f in
                  if ok then let/n st := ok_word in st
                  else let/n st := invalid in st
                else let/n st := invalid in st
            else
              (* the one case index left below the count is poll_status *)
              let/n too_short := word.ltu len (word.of_Z poll_full) in
              if too_short then let/n st := invalid in st
              else
                let/n f := ListArray.get bs poll_flags in
                let/n ok := flags_ok f in
                if ok then let/n st := ok_word in st
                else let/n st := invalid in st
      else let/n st := invalid in st.

  (* ---- the relation ------------------------------------------------- *)

  #[global]
  Instance spec_of_descriptor_check : spec_of "descriptor_check" :=
    fnspec! "descriptor_check" bs_ptr len / (bs : ListArray.t byte) R ~> st,
    { requires tr mem :=
        len = word.of_Z (Z.of_nat (length bs)) /\
        Z.of_nat (length bs) < 2 ^ 64 /\
        (listarray_value AccessByte bs_ptr bs * R)%sep mem;
      ensures tr' mem' :=
        tr' = tr /\
        st = descriptor_check bs len /\
        (listarray_value AccessByte bs_ptr bs * R)%sep mem' }.

  #[local] Hint Unfold invalid ok_word flags_ok ref_ok check_deadline_tail : compiler_cleanup.
  #[local] Hint Unfold
    code_ok code_invalid tag_count direction_count content_count deadline_count flag_limit
    extent_tags_end tag_flush tag_query
    ext_dir0 ext_ct0 ext_dir1 ext_ct1 ext_dl ext_dl_class ext_flags_absent ext_flags_present
    ext_min ext_full flush_dl flush_dl_class flush_flags_absent flush_flags_present flush_min
    flush_full query_dir0 query_ct0 query_flags query_full poll_flags poll_full
    : compiler_cleanup.

  (* The one side condition the derivation raises: every read's index is
     below the buffer's length, which the length tests admit it. *)
  Ltac length_facts :=
    repeat match goal with
           | H : word.ltu _ _ = false |- _ =>
               rewrite word.unsigned_ltu in H; apply Z.ltb_ge in H
           | H : word.ltu _ _ = true |- _ =>
               rewrite word.unsigned_ltu in H; apply Z.ltb_lt in H
           end;
    rewrite ?word.unsigned_of_Z_nowrap in * by lia.
  #[local] Hint Extern 10 => length_facts; cbn; lia : compiler_side_conditions.

  Derive descriptor_check_br2fn SuchThat
         (defn! "descriptor_check"("bs", "len") ~> "st"
              { descriptor_check_br2fn },
          implements descriptor_check)
         As descriptor_check_br2fn_ok.
  Proof.
    Time compile.
  Time Qed.

  Definition descriptor_check_c : string :=
    Eval vm_compute in c_module [("descriptor_check", descriptor_check_br2fn)].
End Descriptor.

Require Import Coq.Strings.String.
Goal True. idtac "=== ASSUMPTIONS ===". exact I. Qed.
Print Assumptions Descriptor.descriptor_check_br2fn_ok.
Redirect "descriptor_check" Compute Descriptor.descriptor_check_c.
