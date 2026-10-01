(* SPDX-License-Identifier: Apache-2.0 *)

(* =========================================================================
   The EndpointIPC.v property sets the walk harness decides over whole
   domains, each with the premise a walk counts, stated once for both halves
   of the randomized side.

   It is here rather than in Walks.v for the reason Probe.v states of the
   composition: Properties.v draws one of these statements too, the
   transposition property over a freely drawn invocation sequence, and a
   statement that differed between the drawn half and the walked half would
   make the two answer different questions while reading as one instrument.
   Each property is the statement Properties.v drew before its set was
   walked, unchanged, with the theorem it shadows named beside it.

   **Each guarded property names its premise, and the walk counts it.** A
   guarded property whose premise no point of its domain meets holds
   vacuously, which a draw could only estimate and a walk decides: Walks.v
   prints how many points of each domain meet the premise beside how many
   refute the property, and the run refuses a walk whose premise no point
   meets. An unguarded property's premise is `true`, its whole content being
   an equality or a conjunct that holds at every point or at none.

   It loads Stdlib alone, so it compiles in any switch the rig compiles a
   harness in. Nothing here runs: Walks.v and Properties.v decide what it
   states.
   ========================================================================= *)

From Stdlib Require Import Bool.
Require EndpointIPC.
Require Import IPCProbe.

(* S13a's: the badge space is two to the declared width, at every width
   (the_badge_space_is_two_to_the_declared_width). *)
Definition prop_badge_space_is_two_to_the_width (w : nat) : bool :=
  Nat.eqb (EndpointIPC.count_of (EndpointIPC.badges w))
          (EndpointIPC.two_pow w).

(* S12's: reading 2, that the frozen surface is a set and not an order, at a
   sequence and an index rather than at the four transpositions of one
   sequence (no_transposition_leaves_the_frozen_surface). *)
Definition prop_a_transposition_does_not_move_the_verdict
             (n : nat) (l : list EndpointIPC.Invocation) : bool :=
  Bool.eqb (EndpointIPC.frozen_surface (EndpointIPC.swap_at_inv n l))
           (EndpointIPC.frozen_surface l).

(* And the other side of that contrast, which is what makes it one: starting a
   member twice is never the frozen surface, at any index of any sequence that
   carried it once (no_insertion_of_a_present_member_is_the_frozen_surface). *)
Definition prop_an_insertion_adds_exactly_one_occurrence
             (n : nat) (i : EndpointIPC.Invocation)
             (l : list EndpointIPC.Invocation) : bool :=
  Nat.eqb (EndpointIPC.occurrences_inv i (EndpointIPC.insert_at_inv n i l))
          (S (EndpointIPC.occurrences_inv i l)).

(* S35's, lifted off its index: the thirty-two-member enumeration says exactly
   one mask is the frozen surface, and this says which one at an index past
   the enumeration (no_proper_boolean_enumeration_is_the_frozen_surface). *)
Definition prop_only_the_full_mask_is_the_surface (n : nat) : bool :=
  let space := EndpointIPC.two_pow
                 (EndpointIPC.count_of EndpointIPC.all_invocations) in
  Bool.eqb (EndpointIPC.surface_mask_ok n)
           (Nat.eqb (Nat.modulo n space) (EndpointIPC.before_last space)).

(* S3's and S4a's. R-07-027a states the negative of the two tables and nothing
   positive of the three classes, so the obligation is the one the entry
   carries, that no table has a lifecycle, held of both admissible maps; and
   beside it the two constructions, the one that lets the schedule table be
   revoked and the one that admits nothing at all. Which acts each class has
   is EndpointIPC.v's gap j and no column here reads it
   (the_specification_gives_no_table_a_lifecycle,
   the_revoke_only_lifecycle_discharges_both, the_table_lifecycle_is_refuted,
   the_frozen_lifecycle_states_nothing). Its premise is a kernel table. *)
Definition prop_lifecycles_split_tables_from_objects
             (c : EndpointIPC.Nameable) (op : EndpointIPC.Lifecycle) : bool :=
  andb (andb (implb (EndpointIPC.is_table c)
                    (negb (EndpointIPC.spec_lifecycles c op)))
             (implb (EndpointIPC.is_table c)
                    (negb (EndpointIPC.revoke_only_lifecycle c op))))
       (andb (implb (EndpointIPC.nameable_eqb c EndpointIPC.NScheduleTable)
                    (EndpointIPC.table_lifecycle c op))
             (negb (EndpointIPC.frozen_lifecycle c op))).

Definition premise_lifecycles_split_tables_from_objects
             (c : EndpointIPC.Nameable) (_ : EndpointIPC.Lifecycle) : bool :=
  EndpointIPC.is_table c.

(* R-07-027a's closure read over a candidate: an inventory that names a
   kernel table or the refused reply object is never closed, whatever else it
   names (no_fourth_class_is_closed, generalised off its index). Its premise
   is an inventory carrying a non-object. *)
Definition prop_no_non_object_survives_the_inventory
             (l : list EndpointIPC.Nameable) : bool :=
  implb (EndpointIPC.any_of (fun c => negb (EndpointIPC.is_object c)) l)
        (negb (EndpointIPC.inventory_ok l)).

Definition premise_no_non_object_survives_the_inventory
             (l : list EndpointIPC.Nameable) : bool :=
  EndpointIPC.any_of (fun c => negb (EndpointIPC.is_object c)) l.

(* S11's: dispatch by the number alone, at two observations
   (the_specification_dispatches_by_the_number_alone). *)
Definition prop_dispatch_ignores_the_observation (n a b : nat) : bool :=
  Nat.eqb (ipc_opt_inv_ix (EndpointIPC.spec_dispatch (fun _ => a) n))
          (ipc_opt_inv_ix (EndpointIPC.spec_dispatch (fun _ => b) n)).

(* And the twin over R-07-030's construction: the submission-queue dispatcher
   agrees with itself wherever the two observations agree, so what refutes it
   is the read of memory and not a different table. Its premise is two
   observations that agree. *)
Definition prop_the_queue_dispatch_agrees_where_the_memory_does
             (n a b : nat) : bool :=
  implb (Nat.eqb a b)
        (Nat.eqb (ipc_opt_inv_ix
                    (EndpointIPC.submission_queue_dispatch (fun _ => a) n))
                 (ipc_opt_inv_ix
                    (EndpointIPC.submission_queue_dispatch (fun _ => b) n))).

Definition premise_the_queue_dispatch_agrees_where_the_memory_does
             (_ a b : nat) : bool :=
  Nat.eqb a b.

(* S28's and S29's, which are twins: the consumer never yields over work its
   recheck saw and never over work its own drain saw
   (the_specification_decider_rechecks_after_arming, ..._yields_only_...).
   Its premise is a ring with work outstanding, before or now. *)
Definition prop_the_decider_never_yields_over_work
             (before now : EndpointIPC.Ring) : bool :=
  andb (implb (EndpointIPC.has_work now)
              (negb (EndpointIPC.spec_decide before now)))
       (implb (EndpointIPC.has_work before)
              (negb (EndpointIPC.spec_decide before now))).

Definition premise_the_decider_never_yields_over_work
             (before now : EndpointIPC.Ring) : bool :=
  orb (EndpointIPC.has_work now) (EndpointIPC.has_work before).

(* And the lost wakeup as a universal rather than a witness, stated against
   the specification and not against the construction's own body. The naive
   consumer and the specification agree everywhere except where the drain saw
   nothing and the recheck would have seen work, and they differ there: that
   is the lost wakeup as an equality between two functions rather than as a
   restatement of one of them, and a redefinition of either decider moves one
   side of it. *)
Definition prop_the_naive_decider_differs_exactly_at_the_lost_wakeup
             (before now : EndpointIPC.Ring) : bool :=
  Bool.eqb (Bool.eqb (EndpointIPC.naive_decide before now)
                     (EndpointIPC.spec_decide before now))
           (negb (andb (negb (EndpointIPC.has_work before))
                       (EndpointIPC.has_work now))).

(* The numbering's two clauses and the three constructions that break one
   each, stated as the clause each construction does *not* break. The
   specification's own second clause is among them, stated against
   R-07-031b's criterion for what may be numbered rather than against
   `numbered_act`'s own body, so a point can falsify it where an implication
   from a hypothesis to itself could not
   (the_specification_numbering_discharges_both, and the standing halves of
   the_iouring_numbering_is_refuted, the_fifth_group_numbering_is_refuted and
   the_short_numbering_drops_a_member). Its premise is an act R-07-031b's
   criterion excludes. *)
Definition prop_the_numberings_split_on_one_clause_each
             (i : EndpointIPC.Invocation) (a : EndpointIPC.Act) : bool :=
  andb (andb (EndpointIPC.numbered_act (EndpointIPC.act_of i))
             (andb (EndpointIPC.iouring_numbering (EndpointIPC.act_of i))
                   (EndpointIPC.fifth_group_numbering (EndpointIPC.act_of i))))
       (andb (implb (negb (EndpointIPC.is_the_act_of_an_invocation a))
                    (negb (EndpointIPC.numbered_act a)))
             (implb (negb (EndpointIPC.is_the_act_of_an_invocation a))
                    (negb (EndpointIPC.short_numbering a)))).

Definition premise_the_numberings_split_on_one_clause_each
             (_ : EndpointIPC.Invocation) (a : EndpointIPC.Act) : bool :=
  negb (EndpointIPC.is_the_act_of_an_invocation a).

(* Gap i as a column. The two trap surfaces the criterion admits differ at
   exactly the three acts R-11-023 owes a carrier for and agree at the other
   fourteen, and every act the ABI numbers traps on both, so what the
   register does fix is decided at every point and what it leaves open is
   visible as the one place the two columns part
   (the_two_admissible_surfaces_differ_on_the_schedule_transitions_alone,
   the_files_own_trap_surface_is_admissible,
   the_syscall_carried_trap_surface_is_admissible). *)
Definition prop_the_trap_surfaces_differ_only_where_the_gap_is
             (a : EndpointIPC.Act) : bool :=
  andb (Bool.eqb (negb (Bool.eqb
                          (EndpointIPC.traps_act a)
                          (EndpointIPC.traps_with_the_schedule_transitions a)))
                 (EndpointIPC.any_of (fun s => EndpointIPC.act_eqb s a)
                                     EndpointIPC.schedule_transitions))
       (implb (EndpointIPC.is_the_act_of_an_invocation a)
              (andb (EndpointIPC.traps_act a)
                    (EndpointIPC.traps_with_the_schedule_transitions a))).
