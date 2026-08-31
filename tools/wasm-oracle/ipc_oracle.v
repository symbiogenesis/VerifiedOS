(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ipc_oracle.v

   M4.3 staging: a computable shadow of EndpointIPC.v's decision procedures
   put through the CertiCoq -> Wasm loop in demo.v's own shape.

   Every check below is a boolean over one of that file's deciders compared
   against a known answer *inside* Gallina, so exactly one boolean crosses
   the Wasm boundary. Nothing here is a proof and nothing here restates a
   theorem: what a check decides is what the decider returns on an input
   the register's own sentence fixes the answer for.

   The battery spans the surfaces EndpointIPC.v carries: the closed
   enumerations, what the ABI numbers against both of the trap surfaces the
   register admits, the four groups over the five members, the surviving
   object inventory and its two weakening families, the frozen surface and
   its deletion, insertion and transposition families, the 32-member mask
   family, the message and badge budgets, the transfer over all sixteen
   readiness states of the demo machine and over the optimistic family
   beside it, the three capability grants and their refutations, the two
   ring deciders, the notification word against the counter, the rotation
   against its work-stealing refutation, and the pending component at the
   switch on both arms of R-07-044's disjunction.

   **Nothing here reads a quantity a register gap leaves open.** The trap
   surface is EndpointIPC.v's gap i and is a parameter there, so the checks
   over it are stated of both values the criterion admits and of the
   difference between them; a check reading one value against a literal
   would go red the day a composition answers gap i the other way, which is
   not a defect an oracle should report. The lifecycle acts are gap j and no
   check reads one.

   What the green line means, and what it does not. `true` out of Wasm says
   that every one of these deciders, compiled through CertiRocq's erasure
   and its Wasm backend and run on a stock engine, returns the answer it
   returns inside the kernel. It is a differential check on the compiled
   pipeline, not a proof of anything about IPC: EndpointIPC.v's own theorems
   are `Prop` and are erased, so none of them crosses this boundary and none
   of the obligations they carry is exercised here. The battery is a
   regression net with a known failure mode: each check compares a decider
   against an answer measured on the file as it stands, so a decider that
   goes wrong turns it red, and a literal updated to match a decider that
   has gone wrong turns it green again. It cannot tell a corrected answer
   from a corrupted one.
   ========================================================================= *)

From CertiRocq.Plugin Require Import CertiRocq.
Require Import EndpointIPC.

(* -------------------------------------------------------------------------
   1. The closed enumerations (R-07-031b, R-07-031a, R-07-027a).
   ------------------------------------------------------------------------- *)

Definition c_five_invocations : bool := Nat.eqb (count_of all_invocations) 5.

Definition c_four_abi_groups : bool := Nat.eqb (count_of all_groups) 4.

Definition c_six_nameables : bool := Nat.eqb (count_of all_nameable) 6.

Definition c_seventeen_acts : bool := Nat.eqb (count_of all_acts) 17.

Definition c_five_sits_under_a_dozen : bool :=
  Nat.ltb (count_of all_invocations) 12.

Definition enumeration_checks : list bool :=
  cons c_five_invocations (cons c_four_abi_groups (cons c_six_nameables
  (cons c_seventeen_acts (cons c_five_sits_under_a_dozen nil)))).

(* -------------------------------------------------------------------------
   2. What the ABI numbers, and what merely traps (R-07-031b, R-07-021,
   R-07-030, R-07-031a).
   ------------------------------------------------------------------------- *)

Definition c_the_abi_numbers_five : bool :=
  Nat.eqb (count_of (filter_of numbered_act all_acts)) 5.

(* The trap surface is EndpointIPC.v's gap i and is a parameter there, so the
   checks over it are stated of both values the register's own criterion
   admits rather than of a literal count under one of them. A check reading
   `traps_act` alone would go red the day the composition answers gap i the
   other way, which is not a defect the oracle should report. *)
Definition c_the_two_trap_surfaces_are_six_and_nine : bool :=
  andb (Nat.eqb (count_of (filter_of traps_act all_acts)) 6)
       (Nat.eqb (count_of
         (filter_of traps_with_the_schedule_transitions all_acts)) 9).

Definition c_the_two_trap_surfaces_part_only_at_the_gap : bool :=
  all_of (fun a => same_bool
                     (negb (same_bool (traps_act a)
                                      (traps_with_the_schedule_transitions a)))
                     (any_of (fun s => act_eqb s a) schedule_transitions))
         all_acts.

Definition c_neither_trap_cut_is_the_abi_cut : bool :=
  andb (Nat.eqb (count_of (filter_of
          (fun a => andb (traps_act a) (negb (numbered_act a))) all_acts)) 1)
       (Nat.eqb (count_of (filter_of
          (fun a => andb (traps_with_the_schedule_transitions a)
                         (negb (numbered_act a))) all_acts)) 4).

Definition c_something_traps_without_a_number : bool :=
  andb (any_of (fun a => andb (traps_act a) (negb (numbered_act a))) all_acts)
       (any_of (fun a => andb (traps_with_the_schedule_transitions a)
                              (negb (numbered_act a))) all_acts).

Definition c_every_invocation_is_numbered : bool :=
  all_of (fun i => numbered_act (act_of i)) all_invocations.

Definition c_the_criterion_and_the_numbering_agree : bool :=
  all_of (fun a => same_bool (is_the_act_of_an_invocation a) (numbered_act a))
         all_acts.

Definition c_the_send_is_numbered_and_traps : bool :=
  andb (numbered_act ASend)
       (andb (traps_act ASend) (traps_with_the_schedule_transitions ASend)).

Definition c_the_exception_traps_unnumbered : bool :=
  andb (andb (traps_act ASynchronousException)
             (traps_with_the_schedule_transitions ASynchronousException))
       (negb (numbered_act ASynchronousException)).

Definition c_the_submission_queue_opcode_is_deleted : bool :=
  andb (andb (negb (numbered_act ASubmissionQueueOpcode))
             (deleted_act ASubmissionQueueOpcode))
       (andb (negb (traps_act ASubmissionQueueOpcode))
             (negb (traps_with_the_schedule_transitions ASubmissionQueueOpcode))).

Definition c_the_schedule_transitions_take_no_number : bool :=
  all_of (fun a => andb (negb (numbered_act a))
                        (negb (is_the_act_of_an_invocation a)))
         schedule_transitions.

Definition act_checks : list bool :=
  cons c_the_abi_numbers_five
  (cons c_the_two_trap_surfaces_are_six_and_nine
  (cons c_the_two_trap_surfaces_part_only_at_the_gap
  (cons c_neither_trap_cut_is_the_abi_cut
  (cons c_something_traps_without_a_number
  (cons c_every_invocation_is_numbered
  (cons c_the_criterion_and_the_numbering_agree
  (cons c_the_send_is_numbered_and_traps
  (cons c_the_exception_traps_unnumbered
  (cons c_the_submission_queue_opcode_is_deleted
  (cons c_the_schedule_transitions_take_no_number nil)))))))))).

(* -------------------------------------------------------------------------
   3. The four groups over the five members (R-07-031a, R-07-031b).
   ------------------------------------------------------------------------- *)

Definition c_the_notification_group_is_empty : bool :=
  Nat.eqb (count_of (members_of NotificationGroup)) 0.

Definition c_the_endpoint_group_is_two : bool :=
  Nat.eqb (count_of (members_of EndpointGroup)) 2.

Definition c_the_yield_sits_alone_in_its_group : bool :=
  Nat.eqb (count_of (members_of (group_of PollSiteYield))) 1.

Definition c_the_revocation_group_is_two : bool :=
  Nat.eqb (count_of (members_of (group_of Revoke))) 2.

Definition group_checks : list bool :=
  cons c_the_notification_group_is_empty (cons c_the_endpoint_group_is_two
  (cons c_the_yield_sits_alone_in_its_group
  (cons c_the_revocation_group_is_two nil))).

(* -------------------------------------------------------------------------
   4. The surviving object inventory and its two weakening families
   (R-07-027a, R-08-004d).
   ------------------------------------------------------------------------- *)

Definition c_three_classes_and_two_tables : bool :=
  andb (Nat.eqb (count_of object_classes) 3)
       (Nat.eqb (count_of kernel_tables) 2).

Definition c_the_composed_inventory_is_closed : bool :=
  inventory_ok spec_inventory.

Definition c_the_inventory_family_sizes : bool :=
  andb (Nat.eqb (count_of inventory_deletions) 3)
       (Nat.eqb (count_of (inventory_insertions_of NReplyObject)) 4).

Definition c_every_inventory_deletion_is_refused : bool :=
  all_of (fun l => negb (inventory_ok l)) inventory_deletions.

Definition c_no_table_joins_the_inventory : bool :=
  all_of (fun l => negb (inventory_ok l)) (inventory_insertions_of NGrantTable).

Definition c_no_reply_object_joins_the_inventory : bool :=
  all_of (fun l => negb (inventory_ok l)) (inventory_insertions_of NReplyObject).

Definition c_no_class_is_named_twice : bool :=
  all_of (fun l => negb (inventory_ok l)) (inventory_insertions_of NEndpoint).

Definition inventory_checks : list bool :=
  cons c_three_classes_and_two_tables (cons c_the_composed_inventory_is_closed
  (cons c_the_inventory_family_sizes
  (cons c_every_inventory_deletion_is_refused
  (cons c_no_table_joins_the_inventory
  (cons c_no_reply_object_joins_the_inventory
  (cons c_no_class_is_named_twice nil)))))).

(* -------------------------------------------------------------------------
   5. The frozen surface and its three generated families (R-07-031a,
   R-07-031b). Two families are refused and one is not, which is the
   set-not-order reading made computable.
   ------------------------------------------------------------------------- *)

Definition c_the_composed_surface_is_frozen : bool := frozen_surface spec_surface.

Definition c_each_member_is_numbered_once : bool :=
  all_of (fun i => Nat.eqb (occurrences_inv i spec_surface) 1) all_invocations.

Definition c_the_weakening_family_sizes : bool :=
  andb (Nat.eqb (count_of (deletions_inv spec_surface)) 5)
       (andb (Nat.eqb (count_of (insertions_inv spec_surface)) 6)
             (Nat.eqb (count_of (transpositions_inv spec_surface)) 4)).

Definition c_every_deletion_is_refused : bool :=
  all_of (fun w => negb (frozen_surface w)) (deletions_inv spec_surface).

Definition c_every_insertion_is_refused : bool :=
  all_of (fun w => negb (frozen_surface w)) (insertions_inv spec_surface).

Definition c_every_transposition_is_admitted : bool :=
  all_of frozen_surface (transpositions_inv spec_surface).

Definition c_one_drop_one_insert_and_one_swap : bool :=
  andb (negb (frozen_surface (drop_at_inv 2 spec_surface)))
       (andb (negb (frozen_surface (insert_at_inv 3 Send spec_surface)))
             (frozen_surface (swap_at_inv 1 spec_surface))).

Definition c_the_five_indices : bool :=
  andb (Nat.eqb (index_of Send) 0)
       (andb (Nat.eqb (index_of Receive) 1)
             (andb (Nat.eqb (index_of PollSiteYield) 2)
                   (andb (Nat.eqb (index_of GrantRedeem) 3)
                         (Nat.eqb (index_of Revoke) 4)))).

Definition c_every_index_is_inside_the_surface : bool :=
  all_of (fun b => b)
         (map_over (fun i => Nat.ltb (index_of i) (count_of spec_surface))
                   all_invocations).

Definition surface_checks : list bool :=
  cons c_the_composed_surface_is_frozen (cons c_each_member_is_numbered_once
  (cons c_the_weakening_family_sizes (cons c_every_deletion_is_refused
  (cons c_every_insertion_is_refused (cons c_every_transposition_is_admitted
  (cons c_one_drop_one_insert_and_one_swap (cons c_the_five_indices
  (cons c_every_index_is_inside_the_surface nil)))))))).

(* -------------------------------------------------------------------------
   6. The mask family: 32 boolean enumerations over the five, exactly one of
   which is the frozen surface (R-07-031a).
   ------------------------------------------------------------------------- *)

Definition c_thirty_two_enumerations : bool := Nat.eqb (count_of all_masks) 32.

Definition c_exactly_one_mask_is_the_surface : bool :=
  Nat.eqb (count_of (filter_of surface_mask_ok all_masks)) 1.

Definition c_the_full_mask_is_the_surface : bool := surface_mask_ok 31.

Definition c_no_proper_mask_is_the_surface : bool :=
  all_of (fun n => negb (surface_mask_ok n)) (upto 31).

Definition c_the_full_mask_admits_every_member : bool :=
  all_of (admits_of_mask 31) all_invocations.

Definition c_mask_thirty_drops_the_send_alone : bool :=
  andb (negb (admits_of_mask 30 Send)) (admits_of_mask 30 Receive).

Definition mask_checks : list bool :=
  cons c_thirty_two_enumerations (cons c_exactly_one_mask_is_the_surface
  (cons c_the_full_mask_is_the_surface (cons c_no_proper_mask_is_the_surface
  (cons c_the_full_mask_admits_every_member
  (cons c_mask_thirty_drops_the_send_alone nil))))).

(* -------------------------------------------------------------------------
   7. The message medium and the badge space (R-07-029, R-07-031, gap a).
   ------------------------------------------------------------------------- *)

Definition c_the_register_budget_binds : bool :=
  andb (message_ok demo (bulk_message 4))
       (negb (message_ok demo (bulk_message 5))).

Definition c_every_payload_inside_the_budget_is_admitted : bool :=
  all_of (fun n => message_ok demo (bulk_message n)) (upto 5).

Definition c_every_payload_past_the_budget_is_refused : bool :=
  all_of (fun n => negb (message_ok demo (bulk_message (Nat.add 5 n)))) (upto 4).

Definition c_the_badge_space_is_two_to_the_width : bool :=
  andb (Nat.eqb (count_of (badges 3)) 8)
       (Nat.eqb (count_of (badges 4)) (two_pow 4)).

Definition c_every_badge_of_the_width_is_admitted : bool :=
  all_of (badge_ok demo) (badges 3).

Definition c_no_neighbouring_width_is_admitted : bool :=
  andb (all_of (fun b => negb (badge_ok demo b)) (badges 2))
       (all_of (fun b => negb (badge_ok demo b)) (badges 4)).

Definition medium_checks : list bool :=
  cons c_the_register_budget_binds
  (cons c_every_payload_inside_the_budget_is_admitted
  (cons c_every_payload_past_the_budget_is_refused
  (cons c_the_badge_space_is_two_to_the_width
  (cons c_every_badge_of_the_width_is_admitted
  (cons c_no_neighbouring_width_is_admitted nil))))).

(* -------------------------------------------------------------------------
   8. The transfer over every readiness state, and the optimistic family
   beside it (R-07-029, R-07-029a, R-07-037a, R-11-010).
   ------------------------------------------------------------------------- *)

Definition probe_offers :=
  cons (offer_into 0) (cons (offer_into 1) (cons (offer_into 2) nil)).

Definition c_the_readiness_family_agrees_with_the_state : bool :=
  all_of (fun n =>
    all_of (fun e =>
      same_bool (negb (is_refused (said spec_transfer empty_kernel
                                        (readiness_of n) (offer_into e))))
                (bit_at e n))
      (upto 4))
    (upto 16).

Definition c_the_specification_is_the_first_optimistic_member : bool :=
  all_of (fun e => is_refused (said (optimistic_at 0) empty_kernel
                                    (fun _ => false) (offer_into e)))
         (upto 4).

Definition c_every_later_optimistic_member_crosses : bool :=
  all_of (fun k =>
    negb (all_of (fun e => is_refused (said (optimistic_at (S k)) empty_kernel
                                            (fun _ => false) (offer_into e)))
                 (upto 4)))
    (upto 4).

Definition c_a_ready_peer_takes_every_offer : bool :=
  all_of (fun e => negb (is_refused (said spec_transfer empty_kernel
                                          (fun _ => true) (offer_into e))))
         (upto 4).

Definition c_an_unready_peer_refuses_every_offer : bool :=
  all_of is_refused
         (outcomes_of spec_transfer empty_kernel (fun _ => false) probe_offers).

Definition c_one_transfer_moves_no_kernel_state : bool :=
  Nat.eqb (count_of (held (after spec_transfer empty_kernel
                                 (fun _ => false) (offer_into 0)))) 0.

Definition c_no_re_offer_sequence_parks_anything : bool :=
  Nat.eqb (count_of (held (run_offers spec_transfer empty_kernel
                                      (fun _ => false) probe_offers))) 0.

Definition c_the_queueing_transfer_parks_one_per_offer : bool :=
  Nat.eqb (count_of (held (run_offers queueing_transfer empty_kernel
                                      (fun _ => false) probe_offers))) 3.

Definition transfer_checks : list bool :=
  cons c_the_readiness_family_agrees_with_the_state
  (cons c_the_specification_is_the_first_optimistic_member
  (cons c_every_later_optimistic_member_crosses
  (cons c_a_ready_peer_takes_every_offer
  (cons c_an_unready_peer_refuses_every_offer
  (cons c_one_transfer_moves_no_kernel_state
  (cons c_no_re_offer_sequence_parks_anything
  (cons c_the_queueing_transfer_parks_one_per_offer nil))))))).

(* -------------------------------------------------------------------------
   9. The explicit capability transfer and its three refutations
   (R-07-029, R-04-008).
   ------------------------------------------------------------------------- *)

Definition c_a_register_only_message_names_no_slot : bool :=
  negb (carried (bulk_message 4) 2).

Definition c_the_grant_keeps_what_the_message_does_not_name : bool :=
  andb (spec_grant (bulk_message 4) (fun _ => true) 5)
       (stingy_grant (bulk_message 4) (fun _ => true) 5).

Definition c_the_replacing_grant_drops_an_unnamed_holding : bool :=
  andb (negb (replacing_grant (bulk_message 4) (fun _ => true) 5))
       (spec_grant (bulk_message 4) (fun _ => true) 5).

Definition c_the_ambient_grant_mints_where_the_specification_does_not : bool :=
  andb (ambient_grant (bulk_message 4) (fun _ => false) 0)
       (negb (spec_grant (bulk_message 4) (fun _ => false) 0)).

Definition grant_checks : list bool :=
  cons c_a_register_only_message_names_no_slot
  (cons c_the_grant_keeps_what_the_message_does_not_name
  (cons c_the_replacing_grant_drops_an_unnamed_holding
  (cons c_the_ambient_grant_mints_where_the_specification_does_not nil))).

(* -------------------------------------------------------------------------
   10. The two ring deciders and the two ways of losing (R-12-096,
   R-07-029a).
   ------------------------------------------------------------------------- *)

Definition c_the_ring_indices_are_the_source_of_truth : bool :=
  andb (has_work {| produced := 3; consumed := 2 |})
       (negb (has_work {| produced := 2; consumed := 2 |})).

Definition c_the_decider_truth_table : bool :=
  andb (spec_decide {| produced := 2; consumed := 2 |}
                    {| produced := 2; consumed := 2 |})
  (andb (negb (spec_decide {| produced := 2; consumed := 2 |}
                           {| produced := 3; consumed := 2 |}))
  (andb (negb (spec_decide {| produced := 3; consumed := 2 |}
                           {| produced := 2; consumed := 2 |}))
        (negb (spec_decide {| produced := 3; consumed := 2 |}
                           {| produced := 3; consumed := 2 |})))).

Definition c_the_naive_decider_loses_a_wakeup : bool :=
  andb (naive_decide {| produced := 2; consumed := 2 |}
                     {| produced := 3; consumed := 2 |})
       (negb (spec_decide {| produced := 2; consumed := 2 |}
                          {| produced := 3; consumed := 2 |})).

Definition c_the_post_only_decider_yields_over_a_drained_ring : bool :=
  andb (post_only_decide {| produced := 3; consumed := 2 |}
                         {| produced := 2; consumed := 2 |})
       (negb (spec_decide {| produced := 3; consumed := 2 |}
                          {| produced := 2; consumed := 2 |})).

Definition decider_checks : list bool :=
  cons c_the_ring_indices_are_the_source_of_truth
  (cons c_the_decider_truth_table
  (cons c_the_naive_decider_loses_a_wakeup
  (cons c_the_post_only_decider_yields_over_a_drained_ring nil))).

(* -------------------------------------------------------------------------
   11. The notification word against the counter (R-12-096).
   ------------------------------------------------------------------------- *)

Definition c_the_signal_coalesces : bool :=
  same_bool (spec_signal (spec_signal false)) (spec_signal false).

Definition c_the_reset_is_defined : bool :=
  andb (negb (spec_reset true)) (negb (spec_reset false)).

Definition c_the_counter_does_not_coalesce : bool :=
  negb (Nat.eqb (counting_signal (counting_signal 0)) (counting_signal 0)).

Definition c_the_counting_word_is_armed_above_zero : bool :=
  andb (negb (counting_armed 0))
       (andb (counting_armed 1) (negb (counting_armed (counting_reset 3)))).

Definition notification_checks : list bool :=
  cons c_the_signal_coalesces (cons c_the_reset_is_defined
  (cons c_the_counter_does_not_coalesce
  (cons c_the_counting_word_is_armed_above_zero nil))).

(* -------------------------------------------------------------------------
   12. The rotation, and the work-stealing advance that reads memory
   (R-07-037b, R-07-037d).
   ------------------------------------------------------------------------- *)

Definition c_the_rotation_wraps_over_the_group : bool :=
  andb (Nat.eqb (advance demo 0) 1)
       (andb (Nat.eqb (advance demo 1) 2) (Nat.eqb (advance demo 2) 0)).

Definition c_the_rotation_is_composition_fixed : bool :=
  Nat.eqb (spec_advance demo quiet_memory 0)
          (spec_advance demo loaded_memory 0).

Definition c_the_work_stealing_rotation_reads_memory : bool :=
  andb (Nat.eqb (work_stealing_advance demo quiet_memory 0) 1)
       (andb (Nat.eqb (work_stealing_advance demo loaded_memory 0) 2)
             (negb (Nat.eqb (work_stealing_advance demo quiet_memory 0)
                            (work_stealing_advance demo loaded_memory 0)))).

Definition c_the_composed_group_shares_a_label : bool :=
  andb (SameLabelGroup demo (upto 3)) (negb (SameLabelGroup demo (upto 4))).

Definition rotation_checks : list bool :=
  cons c_the_rotation_wraps_over_the_group
  (cons c_the_rotation_is_composition_fixed
  (cons c_the_work_stealing_rotation_reads_memory
  (cons c_the_composed_group_shares_a_label nil))).

(* -------------------------------------------------------------------------
   13. The pending component at the switch (R-07-037c, R-07-044).
   ------------------------------------------------------------------------- *)

Definition c_the_interrupt_file_is_the_identity : bool :=
  andb (pending demo 1 1) (negb (pending demo 1 0)).

Definition c_the_delivery_is_the_successors_own_file : bool :=
  andb (negb (spec_delivery demo 0 2 0)) (spec_delivery demo 0 2 2).

Definition c_the_delivery_does_not_vary_with_the_predecessor : bool :=
  all_of (fun s =>
    all_of (fun b => same_bool (spec_delivery demo 0 s b)
                               (spec_delivery demo 1 s b)) (upto 3))
    (upto 3).

Definition c_the_head_member_delivery_is_not_the_members_own : bool :=
  andb (head_member_delivery demo 0 2 0) (negb (spec_delivery demo 0 2 0)).

(* R-07-044's two arms as a computation, which is what makes the disjunction
   real: the rotation that performs no swap is the predecessor's file on the
   swap arm and the successor's on the static one, so one construction
   answers differently on the two machines. *)
Definition c_the_unswapped_delivery_reads_the_arm : bool :=
  andb (all_of (fun s =>
          all_of (fun b => same_bool (unswapped_delivery demo_static 0 s b)
                                     (spec_delivery demo_static 0 s b))
                 (upto 3))
          (upto 3))
       (negb (all_of (fun s =>
                all_of (fun b => same_bool (unswapped_delivery demo 0 s b)
                                           (spec_delivery demo 0 s b))
                       (upto 3))
                (upto 3))).

Definition c_the_arms_part_at_one_point : bool :=
  andb (negb (unswapped_delivery demo 1 0 0))
       (unswapped_delivery demo_static 1 0 0).

(* R-07-037c's second conjunct: a dispatch sequence that never names a member
   leaves that member's bits as it found them, and the two steps that break it
   do not. *)
Definition c_the_bits_survive_a_dispatch_sequence : bool :=
  andb (run_dispatches (step_of (fun _ _ => false)) (fun _ _ => true) 0
                       (cons 1 (cons 2 nil)) 0 0)
       (andb (negb (run_dispatches (clearing_step (fun _ _ => false))
                                   (fun _ _ => true) 0 (cons 1 (cons 2 nil)) 0 0))
             (negb (run_dispatches (sharing_step (fun _ _ => false))
                                   (fun _ _ => true) 0 (cons 1 (cons 2 nil)) 0 0))).

(* Reading 4 refuted rather than computed: a grouping that files the yield
   under the notification group fills it, and still covers the five. *)
Definition c_the_notification_group_can_be_filled_and_is_not : bool :=
  andb (Nat.eqb (census group_of NotificationGroup) 0)
       (Nat.eqb (census notifying_grouping NotificationGroup) 1).

Definition pending_checks : list bool :=
  cons c_the_interrupt_file_is_the_identity
  (cons c_the_delivery_is_the_successors_own_file
  (cons c_the_delivery_does_not_vary_with_the_predecessor
  (cons c_the_head_member_delivery_is_not_the_members_own
  (cons c_the_unswapped_delivery_reads_the_arm
  (cons c_the_arms_part_at_one_point
  (cons c_the_bits_survive_a_dispatch_sequence
  (cons c_the_notification_group_can_be_filled_and_is_not nil))))))).

(* -------------------------------------------------------------------------
   14. The bit and power helpers the families above are indexed by.
   ------------------------------------------------------------------------- *)

Definition c_the_bits_of_a_mask : bool :=
  andb (same_bool (bit_at 0 13) true)
       (andb (same_bool (bit_at 1 13) false)
             (andb (same_bool (bit_at 2 13) true)
                   (same_bool (bit_at 3 13) true))).

Definition c_the_zero_mask_has_no_bits : bool :=
  all_of (fun i => negb (bit_at i 0)) (upto 5).

Definition c_two_to_the_five_is_thirty_two : bool := Nat.eqb (two_pow 5) 32.

Definition c_the_index_set_has_its_length : bool :=
  Nat.eqb (count_of (upto 7)) 7.

Definition helper_checks : list bool :=
  cons c_the_bits_of_a_mask (cons c_the_zero_mask_has_no_bits
  (cons c_two_to_the_five_is_thirty_two
  (cons c_the_index_set_has_its_length nil))).

(* =========================================================================
   The one boolean that crosses.
   ========================================================================= *)

Definition ipc_checks : list bool :=
  app enumeration_checks (app act_checks (app group_checks
  (app inventory_checks (app surface_checks (app mask_checks
  (app medium_checks (app transfer_checks (app grant_checks
  (app decider_checks (app notification_checks (app rotation_checks
  (app pending_checks helper_checks)))))))))))).

Definition ipc_oracle : bool := all_of (fun b : bool => b) ipc_checks.

Compute count_of ipc_checks.
Compute ipc_oracle.

CertiRocq Compile Wasm ipc_oracle.
