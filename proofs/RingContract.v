(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   RingContract.v

   GENERATED. No hand edit survives: `python tools/run.py ring emit` writes
   this file and rule K-89 holds it byte-identical to what that command
   emits from its owners. Change an owner and regenerate.

   Owners:
     interfaces/ring-reference.json
         everything a composition fixes: the ring constants, the encoding
         widths, the operation set, and each operation's declared record.
     docs/requirements-register.md
         R-12-093's closed status set, R-12-094's lifecycle states,
         R-12-095's full-ring result, and R-12-097's cancellation answers.

   What this is, per the profile's section 4.3.6: the generated interface
   artifact, carrying the interface skeleton, the composition-time
   constants, and the conformance campaign R-18-037 requires. The campaign
   is decided by computation over the declared constants, so a declaration
   whose constants break an obligation fails to compile this file. The
   canonical SPSC, lost-wakeup and typestate proofs that entry also names
   are not here and are not claimed.

   Nothing here is a proof about an implementation: the profile's own rule
   is that its types document the contract and never are it.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   Part 1: the interface skeleton.
   ------------------------------------------------------------------------- *)

(* the closed common set R-12-093 states *)
Inductive status : Set :=
  | status_ok
  | status_refused
  | status_invalid
  | status_cancelled
  | status_deadline_expired
  | status_peer_restarted
  | status_device_fault
  | status_resource_exhausted.

(* the monotone lifecycle R-12-094 states, in its order *)
Inductive slot_state : Set :=
  | state_Free
  | state_Writing
  | state_Submitted
  | state_Accepted
  | state_Terminal
  | state_Reclaimed.

(* the cancellation answers R-12-097 states *)
Inductive cancel_answer : Set :=
  | cancel_cancelled
  | cancel_too_late
  | cancel_not_live.

(* submission, whose full-ring arm R-12-095 names *)
Inductive submit_result : Set :=
  | submit_enqueued
  | submit_would_block.

(* the interface's finite deadline classes *)
Inductive deadline_class : Set :=
  | deadline_immediate
  | deadline_frame
  | deadline_bulk.

(* the closed flag set *)
Inductive ring_flag : Set :=
  | flag_notify_on_completion
  | flag_fence_before.

(* a buffer reference's declared direction *)
Inductive direction : Set :=
  | direction_to_server
  | direction_to_client.

(* a buffer reference's declared content type *)
Inductive content_type : Set :=
  | content_opaque_bytes
  | content_frame_extent.

(* the interface's closed operation variant *)
Inductive op : Set :=
  | op_read_extent
  | op_write_extent
  | op_flush
  | op_query_geometry
  | op_poll_status.

(* each operation's closed result refinement, which R-12-093 admits beside the common set *)
Inductive refinement : Set :=
  | refine_read_extent__short_read
  | refine_write_extent__short_write.

(* The widths IDL-023 fixes: the smallest admissible form for a case count,
   and for a flag set counted in bits. *)
Definition disc_width (cases : nat) : nat :=
  if Nat.leb cases 256 then 1 else if Nat.leb cases 65536 then 2 else 4.

Definition flag_width (bits : nat) : nat :=
  if Nat.leb bits 8 then 1
  else if Nat.leb bits 16 then 2
  else if Nat.leb bits 32 then 4 else 8.

Record labels : Set := mk_labels {
  confidentiality : nat;
  integrity : nat
}.

Record buffer_ref : Set := mk_buffer_ref {
  session_index : nat;
  ref_offset : nat;
  ref_length : nat;
  ref_direction : direction;
  ref_content : content_type
}.

Record descriptor : Set := mk_descriptor {
  descriptor_op : op;
  request_id : nat;
  descriptor_generation : nat;
  scalars : list nat;
  buffers : list buffer_ref;
  deadline : option deadline_class;
  flags : list ring_flag
}.

Record completion : Set := mk_completion {
  completion_request_id : nat;
  completion_status : status;
  completion_refinement : option nat;
  metadata : nat;
  consumed_bytes : nat;
  produced_bytes : nat;
  server_generation : nat
}.

Record op_record : Set := mk_op_record {
  rec_validation_cost : nat;
  rec_max_payload_bytes : nat;
  rec_max_segment_count : nat;
  rec_device_service_bound : nat;
  rec_cancellation_cleanup_cost : nat;
  rec_completion_publication_cost : nat;
  rec_max_notifications : nat;
  rec_max_requests_drained : nat
}.

(* -------------------------------------------------------------------------
   Part 2: the composition-time constants, from the declaration.
   ------------------------------------------------------------------------- *)

Definition ring_capacity : nat := 64.
Definition ring_index_width_bytes : nat := 1.
Definition ring_index_span : nat := 256.
Definition ring_descriptor_size_bytes : nat := 64.
Definition ring_descriptor_alignment_bytes : nat := 8.
Definition ring_completion_size_bytes : nat := 32.
Definition ring_completion_fill : nat := 5.
Definition ring_max_batch_size : nat := 8.
Definition ring_session_generation : nat := 1.
Definition ring_completion_capacity : nat := 64.
Definition ring_max_accepted : nat := 64.
Definition ring_max_segments : nat := 4.
Definition ring_segment_max_bytes : nat := 1024.
Definition ring_slot_budget : nat := 20000.

Definition enc_byte_count_bytes : nat := 4.
Definition enc_content_type_bytes : nat := 1.
Definition enc_direction_bytes : nat := 1.
Definition enc_generation_bytes : nat := 4.
Definition enc_length_bytes : nat := 4.
Definition enc_metadata_bytes : nat := 8.
Definition enc_offset_bytes : nat := 4.
Definition enc_request_id_bytes : nat := 4.
Definition enc_session_index_bytes : nat := 2.

Definition label_levels : nat := 4.

Definition buffer_ref_bytes : nat :=
  enc_session_index_bytes + enc_offset_bytes + enc_length_bytes
  + enc_direction_bytes + enc_content_type_bytes.

Definition op_count : nat := 5.
Definition deadline_class_count : nat := 3.
Definition flag_count : nat := 2.
Definition status_count : nat := 8.
Definition refinement_count : nat := 2.

Definition tag_width : nat := disc_width op_count.
Definition deadline_width : nat := disc_width deadline_class_count.
Definition status_width : nat := disc_width status_count.
Definition refinement_width : nat := disc_width refinement_count.
Definition flag_set_bytes : nat := flag_width flag_count.

Definition op_scalar_bytes (o : op) : nat :=
  match o with
  | op_read_extent => 8
  | op_write_extent => 8
  | op_flush => 0
  | op_query_geometry => 2
  | op_poll_status => 2
  end.

Definition op_buffer_refs (o : op) : nat :=
  match o with
  | op_read_extent => 2
  | op_write_extent => 2
  | op_flush => 0
  | op_query_geometry => 1
  | op_poll_status => 0
  end.

Definition op_has_deadline (o : op) : bool :=
  match o with
  | op_read_extent => true
  | op_write_extent => true
  | op_flush => true
  | op_query_geometry => false
  | op_poll_status => false
  end.

Definition op_marked_scalars (o : op) : nat :=
  match o with
  | op_read_extent => 2
  | op_write_extent => 2
  | op_flush => 0
  | op_query_geometry => 1
  | op_poll_status => 1
  end.

Definition op_empty_validation_claim (o : op) : bool :=
  match o with
  | op_read_extent => false
  | op_write_extent => false
  | op_flush => true
  | op_query_geometry => false
  | op_poll_status => false
  end.

Definition op_labels (o : op) : labels :=
  match o with
  | op_read_extent => mk_labels 1 2
  | op_write_extent => mk_labels 1 2
  | op_flush => mk_labels 0 2
  | op_query_geometry => mk_labels 0 1
  | op_poll_status => mk_labels 0 1
  end.

Definition op_cancellable (o : op) : bool :=
  match o with
  | op_read_extent => true
  | op_write_extent => true
  | op_flush => true
  | op_query_geometry => false
  | op_poll_status => false
  end.

Definition op_cancel_points (o : op) : nat :=
  match o with
  | op_read_extent => 2
  | op_write_extent => 2
  | op_flush => 1
  | op_query_geometry => 0
  | op_poll_status => 0
  end.

Definition op_commit_index (o : op) : nat :=
  match o with
  | op_read_extent => 2
  | op_write_extent => 1
  | op_flush => 1
  | op_query_geometry => 0
  | op_poll_status => 0
  end.

Definition op_quiescence_bound (o : op) : nat :=
  match o with
  | op_read_extent => 200
  | op_write_extent => 200
  | op_flush => 100
  | op_query_geometry => 0
  | op_poll_status => 0
  end.

Definition op_max_to_terminal (o : op) : nat :=
  match o with
  | op_read_extent => 1800
  | op_write_extent => 2000
  | op_flush => 1200
  | op_query_geometry => 0
  | op_poll_status => 0
  end.

Definition op_declared_record (o : op) : op_record :=
  match o with
  | op_read_extent => mk_op_record 24 4096 4 1200 40 16 1 8
  | op_write_extent => mk_op_record 28 4096 4 1600 48 16 1 8
  | op_flush => mk_op_record 8 0 0 900 0 16 1 8
  | op_query_geometry => mk_op_record 6 64 1 120 0 16 1 8
  | op_poll_status => mk_op_record 4 0 0 60 0 16 1 8
  end.

Definition op_fill (o : op) : nat :=
  match o with
  | op_read_extent => 24
  | op_write_extent => 24
  | op_flush => 56
  | op_query_geometry => 44
  | op_poll_status => 56
  end.

Definition op_activation_slack (o : op) : nat :=
  match o with
  | op_read_extent => 10080
  | op_write_extent => 6848
  | op_flush => 12608
  | op_query_geometry => 18864
  | op_poll_status => 19360
  end.

Definition op_payload_slack (o : op) : nat :=
  match o with
  | op_read_extent => 0
  | op_write_extent => 0
  | op_flush => 0
  | op_query_geometry => 960
  | op_poll_status => 0
  end.

Definition op_cancellation_slack (o : op) : nat :=
  match o with
  | op_read_extent => 344
  | op_write_extent => 136
  | op_flush => 184
  | op_query_geometry => 0
  | op_poll_status => 0
  end.

(* The encoded size of a descriptor, by section 4.2's rows: the tag, the
   request identifier, the operation's scalars, its buffer references, its
   optional deadline, and the closed flag set, packed with no interior
   padding. *)
Definition descriptor_bytes (o : op) : nat :=
  tag_width + enc_request_id_bytes + op_scalar_bytes o
  + op_buffer_refs o * buffer_ref_bytes
  + (if op_has_deadline o then 1 + deadline_width else 0)
  + flag_set_bytes.

(* The encoded size of a terminal completion: its status, the request
   identifier it carries back, the optional operation-specific refinement,
   the bounded result metadata, the consumed and produced byte counts, and
   the server generation. *)
Definition completion_bytes : nat :=
  status_width + enc_request_id_bytes + (1 + refinement_width)
  + enc_metadata_bytes + 2 * enc_byte_count_bytes + enc_generation_bytes.

(* An activation's declared cost: the requests one drain admits, each
   validated, served, and published. *)
Definition activation_cost (o : op) : nat :=
  rec_max_requests_drained (op_declared_record o)
  * (rec_validation_cost (op_declared_record o)
     + rec_device_service_bound (op_declared_record o)
     + rec_completion_publication_cost (op_declared_record o)).

(* The interval admission accounts from expiry observation to terminal
   completion: the device's own bound, the declared cleanup, the DMA
   quiescence, and the publication. *)
Definition cancellation_interval (o : op) : nat :=
  rec_device_service_bound (op_declared_record o)
  + rec_cancellation_cleanup_cost (op_declared_record o)
  + op_quiescence_bound o
  + rec_completion_publication_cost (op_declared_record o).

(* -------------------------------------------------------------------------
   Part 3: the lifecycle, the ring machine, and the conformance campaign.
   ------------------------------------------------------------------------- *)

Definition lifecycle_next (o : slot_state) : option slot_state :=
  match o with
  | state_Free => Some state_Writing
  | state_Writing => Some state_Submitted
  | state_Submitted => Some state_Accepted
  | state_Accepted => Some state_Terminal
  | state_Terminal => Some state_Reclaimed
  | state_Reclaimed => None
  end.

Definition lifecycle_rank (o : slot_state) : nat :=
  match o with
  | state_Free => 0
  | state_Writing => 1
  | state_Submitted => 2
  | state_Accepted => 3
  | state_Terminal => 4
  | state_Reclaimed => 5
  end.

Definition lifecycle_malformed (o : slot_state) : option slot_state :=
  match o with
  | state_Free => None
  | state_Writing => None
  | state_Submitted => Some state_Terminal
  | state_Accepted => None
  | state_Terminal => None
  | state_Reclaimed => None
  end.

(* The lifecycle is a sequence and not merely an order, so a successor's rank
   is its predecessor's and one more: a step that only *increased* the rank
   would admit a lifecycle that skipped a state, which is exactly what the
   malformed step below is the one licensed instance of. *)
Definition lifecycle_step_ok (s : slot_state) : bool :=
  match lifecycle_next s with
  | None => true
  | Some t => Nat.eqb (lifecycle_rank t) (S (lifecycle_rank s))
  end.

(* The malformed step skips, and skips exactly the states the register's own
   order puts between the two it names. *)
Definition lifecycle_malformed_ok (s : slot_state) : bool :=
  match lifecycle_malformed s with
  | None => true
  | Some t => Nat.eqb (lifecycle_rank t) (2 + lifecycle_rank s)
  end.

Definition may_reserve (occupancy : nat) : bool :=
  Nat.ltb occupancy ring_capacity.

Definition submit (occupancy : nat) : submit_result :=
  if may_reserve occupancy then submit_enqueued else submit_would_block.

(* Acceptance reads the session table and never the descriptor's contents:
   a stale generation and a duplicate live identifier are each refused. *)
Definition accept (session_generation descriptor_generation : nat)
                  (duplicate_live : bool) : bool :=
  andb (Nat.eqb session_generation descriptor_generation) (negb duplicate_live).

(* The notification discipline: work is pending when the consumer index
   trails the producer's, and the consumer sleeps only on a recheck that
   shows none. *)
Definition work_pending (produced consumed : nat) : bool :=
  Nat.ltb consumed produced.

Definition sleeps (produced consumed : nat) (armed : bool) : bool :=
  andb armed (negb (work_pending produced consumed)).

Definition no_lost_wakeup (produced consumed : nat) (armed : bool) : bool :=
  implb (sleeps produced consumed armed) (negb (work_pending produced consumed)).

(* Cancellation's deterministic race, as the answers depend on where the
   target stands: live and unstarted, live and past a declared point, past
   the commit point, or not live at all. *)
Definition cancel (o : op) (s : slot_state) (position : nat) : cancel_answer :=
  if op_cancellable o then
    match s with
    | state_Submitted => cancel_cancelled
    | state_Accepted =>
        if Nat.ltb position (op_commit_index o) then cancel_cancelled
        else cancel_too_late
    | _ => cancel_not_live
    end
  else cancel_not_live.

(* Every value a receiver uses as an index, length, offset, or selector: a
   marked scalar, and every field of every buffer reference. *)
Definition op_has_validated (o : op) : bool :=
  orb (Nat.ltb 0 (op_marked_scalars o)) (Nat.ltb 0 (op_buffer_refs o)).

(* Boolean agreement, written here because the prelude carries `xorb` and
   the library that carries its complement is not on this file's path. *)
Definition agree (a b : bool) : bool := negb (xorb a b).

Lemma eqb_reflexive : forall n : nat, Nat.eqb n n = true.
Proof. induction n as [| m IH]; simpl; [ reflexivity | exact IH ]. Qed.

Theorem the_width_rule_admits_one_form :
  andb (andb (andb (Nat.eqb (disc_width 256) 1) (Nat.eqb (disc_width 257) 2)) (andb (Nat.eqb (disc_width 65536) 2) (Nat.eqb (disc_width 65537) 4))) (andb (andb (Nat.eqb (flag_width 8) 1) (Nat.eqb (flag_width 9) 2)) (andb (andb (Nat.eqb (flag_width 16) 2) (Nat.eqb (flag_width 17) 4)) (andb (Nat.eqb (flag_width 32) 4) (Nat.eqb (flag_width 33) 8)))) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem descriptor_fills_its_slot_exactly :
  forall o : op, Nat.eqb (descriptor_bytes o + op_fill o) ring_descriptor_size_bytes = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem completion_fills_its_slot_exactly :
  Nat.eqb (completion_bytes + ring_completion_fill) ring_completion_size_bytes = true.
Proof. vm_compute; reflexivity. Qed.

Theorem both_slots_are_aligned :
  andb (Nat.eqb (Nat.modulo ring_descriptor_size_bytes ring_descriptor_alignment_bytes) 0) (Nat.eqb (Nat.modulo ring_completion_size_bytes ring_descriptor_alignment_bytes) 0) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_index_span_is_the_declared_width :
  Nat.eqb ring_index_span (Nat.pow 2 (8 * ring_index_width_bytes)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_capacity_divides_the_index_span :
  andb (Nat.eqb (Nat.modulo ring_index_span ring_capacity) 0) (Nat.leb (2 * ring_capacity) ring_index_span) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem ring_fills_to_capacity :
  may_reserve (Nat.pred ring_capacity) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem ring_refuses_one_past_capacity :
  submit ring_capacity = submit_would_block.
Proof. vm_compute; reflexivity. Qed.

Theorem completion_capacity_covers_accepted :
  andb (Nat.leb ring_max_accepted ring_completion_capacity) (Nat.leb ring_max_accepted ring_capacity) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem batch_is_bounded_by_capacity :
  andb (Nat.ltb 0 ring_max_batch_size) (Nat.leb ring_max_batch_size ring_capacity) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem drain_is_bounded_by_the_batch :
  forall o : op, Nat.leb (rec_max_requests_drained (op_declared_record o)) ring_max_batch_size = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem the_declared_batch_and_segment_maxima_are_attained :
  andb (Nat.eqb (rec_max_requests_drained (op_declared_record op_read_extent)) ring_max_batch_size) (Nat.eqb (rec_max_segment_count (op_declared_record op_read_extent)) ring_max_segments) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem notifications_are_coalesced_to_one :
  forall o : op, Nat.leb (rec_max_notifications (op_declared_record o)) 1 = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem the_payload_is_exactly_the_declared_segments :
  forall o : op, andb (Nat.leb (rec_max_segment_count (op_declared_record o)) ring_max_segments) (Nat.eqb (rec_max_payload_bytes (op_declared_record o) + op_payload_slack o) (rec_max_segment_count (op_declared_record o) * ring_segment_max_bytes)) = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem an_activation_spends_the_declared_slot_budget :
  forall o : op, Nat.eqb (activation_cost o + op_activation_slack o) ring_slot_budget = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem cancellation_spends_the_declared_interval :
  forall o : op, implb (op_cancellable o) (Nat.eqb (cancellation_interval o + op_cancellation_slack o) (op_max_to_terminal o)) = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem a_non_cancellable_operation_declares_no_cancellation :
  forall o : op, implb (negb (op_cancellable o)) (Nat.eqb (rec_cancellation_cleanup_cost (op_declared_record o) + op_quiescence_bound o + op_max_to_terminal o + op_cancel_points o + op_commit_index o + op_cancellation_slack o) 0) = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem cancellability_is_the_declaration_and_nothing_else :
  forall o : op, agree (op_cancellable o) (Nat.ltb 0 (op_cancel_points o)) = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem commit_point_is_one_of_the_declared_points :
  forall o : op, Nat.leb (op_commit_index o) (op_cancel_points o) = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem labels_are_drawn_from_the_declared_lattice :
  forall o : op, andb (Nat.ltb (confidentiality (op_labels o)) label_levels) (Nat.ltb (integrity (op_labels o)) label_levels) = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem the_empty_validation_case_is_a_claim :
  forall o : op, agree (op_empty_validation_claim o) (negb (op_has_validated o)) = true.
Proof. intro o; destruct o; vm_compute; reflexivity. Qed.

Theorem lifecycle_advances_monotonically :
  forall s : slot_state, lifecycle_step_ok s = true.
Proof. intro s; destruct s; vm_compute; reflexivity. Qed.

Theorem lifecycle_has_one_terminal_state :
  lifecycle_next state_Reclaimed = None.
Proof. vm_compute; reflexivity. Qed.

Theorem the_malformed_step_skips_forward :
  forall s : slot_state, lifecycle_malformed_ok s = true.
Proof. intro s; destruct s; vm_compute; reflexivity. Qed.

Theorem the_malformed_step_acquires_no_authority :
  lifecycle_malformed state_Accepted = None.
Proof. vm_compute; reflexivity. Qed.

Theorem a_stale_generation_is_refused :
  forall g h : nat, Nat.eqb g h = false -> forall d : bool, accept g h d = false.
Proof. intros g h H d; unfold accept; rewrite H; reflexivity. Qed.

Theorem a_duplicate_live_identifier_is_refused :
  forall g h : nat, accept g h true = false.
Proof. intros g h; unfold accept; destruct (Nat.eqb g h); reflexivity. Qed.

Theorem a_fresh_unique_request_is_accepted :
  forall g : nat, accept g g false = true.
Proof. intro g; unfold accept; rewrite eqb_reflexive; reflexivity. Qed.

Theorem no_published_work_stays_behind_a_sleep :
  forall produced consumed : nat, forall armed : bool, no_lost_wakeup produced consumed armed = true.
Proof. intros produced consumed armed; unfold no_lost_wakeup, sleeps; destruct armed; destruct (work_pending produced consumed); reflexivity. Qed.

Theorem a_target_past_its_commit_point_is_too_late :
  forall (o : op) (position : nat), op_cancellable o = true -> Nat.ltb position (op_commit_index o) = false -> cancel o state_Accepted position = cancel_too_late.
Proof. intros o position Hc Hp; unfold cancel; rewrite Hc, Hp; reflexivity. Qed.

Theorem a_non_cancellable_operation_is_never_live_to_cancel :
  forall (o : op) (s : slot_state) (position : nat), op_cancellable o = false -> cancel o s position = cancel_not_live.
Proof. intros o s position H; unfold cancel; rewrite H; reflexivity. Qed.

(* -------------------------------------------------------------------------
   The R-05-163 gate: every constant closed under the global context.
   ------------------------------------------------------------------------- *)

Print Assumptions eqb_reflexive.
Print Assumptions the_width_rule_admits_one_form.
Print Assumptions descriptor_fills_its_slot_exactly.
Print Assumptions completion_fills_its_slot_exactly.
Print Assumptions both_slots_are_aligned.
Print Assumptions the_index_span_is_the_declared_width.
Print Assumptions the_capacity_divides_the_index_span.
Print Assumptions ring_fills_to_capacity.
Print Assumptions ring_refuses_one_past_capacity.
Print Assumptions completion_capacity_covers_accepted.
Print Assumptions batch_is_bounded_by_capacity.
Print Assumptions drain_is_bounded_by_the_batch.
Print Assumptions the_declared_batch_and_segment_maxima_are_attained.
Print Assumptions notifications_are_coalesced_to_one.
Print Assumptions the_payload_is_exactly_the_declared_segments.
Print Assumptions an_activation_spends_the_declared_slot_budget.
Print Assumptions cancellation_spends_the_declared_interval.
Print Assumptions a_non_cancellable_operation_declares_no_cancellation.
Print Assumptions cancellability_is_the_declaration_and_nothing_else.
Print Assumptions commit_point_is_one_of_the_declared_points.
Print Assumptions labels_are_drawn_from_the_declared_lattice.
Print Assumptions the_empty_validation_case_is_a_claim.
Print Assumptions lifecycle_advances_monotonically.
Print Assumptions lifecycle_has_one_terminal_state.
Print Assumptions the_malformed_step_skips_forward.
Print Assumptions the_malformed_step_acquires_no_authority.
Print Assumptions a_stale_generation_is_refused.
Print Assumptions a_duplicate_live_identifier_is_refused.
Print Assumptions a_fresh_unique_request_is_accepted.
Print Assumptions no_published_work_stays_behind_a_sleep.
Print Assumptions a_target_past_its_commit_point_is_too_late.
Print Assumptions a_non_cancellable_operation_is_never_live_to_cancel.
