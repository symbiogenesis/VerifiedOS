(* SPDX-License-Identifier: Apache-2.0 *)

(* =========================================================================
   The QuickChick harness: random generators over the Gallina front, and the
   one thing no enumeration has, automatic counterexample shrinking.

   Vectors.v beside this file walks a declared grid and prints what the
   admission algebra answers at every point of it. That is the half that runs
   with no install, and its limit is the grid: a defect outside the corners
   somebody named is a defect it does not reach. This half draws instead, so
   what it reaches is decided by the generator's range rather than by a list,
   and when a draw refutes a property QuickChick shrinks the counterexample to
   a minimal one rather than handing back the frame it happened to draw.

   It needs `coq-quickchick`, which is installed in a switch of its own,
   `quickchick-9.1.1`, at 2.2.0 against Rocq 9.1.1. `tools/quickchick.py
   check` says which switch holds it, and the tool's own header states why
   the switch is separate: adding the library to the CertiCoq oracle's switch
   downgrades dune and recompiles fifty-nine packages, and the proof gate's
   switch carries no library at all on purpose.

   The properties are the computable shadows of theorems the shipped proofs
   prove, and that is the point of stating them here rather than only there. A
   theorem is about every frame and holds by construction; a property is about
   the frames a generator produces and holds by computation. Where the two
   agree the generator is exercising the algebra the theorem is about, and
   where they disagree one of them is wrong about the definitions underneath
   both, which is the differential the Wasm oracle was built to make and has
   never had an input side for.

   It has two subjects, as Vectors.v beside it does. The first is
   CyclicExecutive.v's admission algebra. The second is EndpointIPC.v's
   capability lifecycle, endpoint transfer and message medium, whose names are
   spelled `EndpointIPC.x` throughout because five of them are already taken by
   the two modules imported unqualified above: CyclicExecutive.v defines
   `all_of`, `count_of` and an `Outcome`, and PartitionContext.v defines a
   `Machine` and a `demo`. An unqualified import of the second subject would
   shadow one or the other.

   **What a draw reaches here that the enumeration does not.** The second
   block's grid is finite in five places where the composition is not: the
   readiness index runs to sixteen states, the payload grid runs to one past
   each budget, the badge widths run to one past the declared one, the offer
   sequence is one fixed list of five, and the machine is one. Every property
   below is stated over a drawn machine, a drawn readiness index, a drawn
   payload, a drawn width or a drawn offer sequence, so what it reaches is a
   range rather than a list. Two of them are the arithmetic no theorem in
   EndpointIPC.v states and no vector could check at every point:
   `prop_queue_depth_is_the_unsatisfied_offers`, which fixes exactly how much
   state the construction R-07-029a excludes would have accumulated, and
   `prop_only_the_full_mask_is_the_surface`, which is that file's
   thirty-two-member enumeration lifted to an unbounded index.

   **Each refuting construction is drawn against the obligation it does not
   break as well as the one it does.** A property set that only ever exercised
   the defect would be measuring the shape of the construction rather than the
   named defect, so the ambient grant is checked to grant everything named,
   the io_uring numbering to number every invocation, the work-stealing
   rotation to agree wherever nothing is observed, and the submission-queue
   dispatcher to agree wherever the two observations agree.

   **A guarded property whose premise a generator rarely reaches holds
   vacuously, so the premises are measured and not assumed.** Over 10000 draws
   apiece, the refusal arm is reached 5009 times, a capability slot the
   payload names 2770, a slot fault 2366, a register fault 2455, an inventory
   carrying a non-object 6648, two observations that agree 1142, an act the
   criterion excludes 7088, a ring with work outstanding 4217, a kernel table
   3277, and a drawn width that is the machine's declared one 1416. One
   premise is genuinely thin and is answered by a second generator rather than
   left standing: a freely drawn invocation sequence is the frozen surface on
   48 draws of 10000, so the transposition property is run again over
   sequences built from the specification's own by transposing it, where the
   figure is 10000 of 10000. The seventh premise is the one that moved: it
   used to read *an act `numbered_act` answers false at* and now reads *an act
   R-07-031b's criterion excludes*, and the two predicates agree at every one
   of the seventeen acts, which
   `the_criterion_and_the_specification_numbering_agree_everywhere` decides by
   conversion in the artifact, so the figure is the same measurement and not a
   restated one.

   **An unguarded property owes no premise figure, and four of the ones below
   are unguarded for that reason.** A property whose whole content is an
   equality between two definitions cannot hold vacuously; what it can do
   instead is hold by conversion because one side restates the other's body,
   which is the defect the two decider and delivery properties below were
   rewritten to remove. Each is now stated against the specification it is
   about rather than against the construction it is named for, so a
   redefinition of either side moves one column and not both:
   `prop_the_naive_decider_differs_exactly_at_the_lost_wakeup` fails if either
   decider changes, and `prop_delivery_ignores_the_predecessor` fails if the
   unswapped construction stops reading R-07-044's arm or if the
   specification's delivery starts reading the predecessor.
   ========================================================================= *)

From QuickChick Require Import QuickChick.
From Stdlib Require Import List String.
Require Import PartitionContext.
Require Import CyclicExecutive.
Require Import Probe.
Require EndpointIPC.
Require Import IPCProbe.

Import ListNotations.
Import QcDefaultNotation.
Open Scope qc_scope.
Open Scope string_scope.

(* The extraction QuickChick runs a property through touches accessors the
   plugin marks opaque; the warnings are about the extraction and not about
   the properties, and they are what a run would otherwise be read through. *)
Set Warnings "-extraction-opaque-accessed,-extraction".

(* -------------------------------------------------------------------------
   Showing a counterexample. A shrunk frame is only worth having if it can be
   read, so every declared quantity is printed and the tenant is not: reading
   1 is what R-11-023 says admission must not do, and a counterexample that
   displayed it would invite exactly that reading.
   ------------------------------------------------------------------------- *)

#[global] Instance showSlot : Show (Slot bool) :=
  {| show s := "(" ++ show (slot_width s) ++ " " ++ show (slot_offset s)
                   ++ " " ++ show (slot_bound s) ++ " " ++ show (slot_period s)
                   ++ ")" |}.

#[global] Instance showBand : Show (Band bool) :=
  {| show b := show (band_focus b) ++ " " ++ show (band_background b) |}.

#[global] Instance showFrame : Show (Frame bool) :=
  {| show f := "mf=" ++ show (major_frame f)
               ++ " reserved=" ++ show (reserved_band f)
               ++ " band=" ++ show (discretionary_band f) |}.

(* -------------------------------------------------------------------------
   The generators. The ranges are the ones the algebra decides inside: an
   offset and a width that reach past a major frame, a bound that reaches past
   its own width, and periods on both sides of the divisibility the probe's
   harmonic predicate asks for.
   ------------------------------------------------------------------------- *)

Definition genSlot : G (Slot bool) :=
  bindGen (choose (0, 220)) (fun w =>
  bindGen (choose (0, 220)) (fun o =>
  bindGen (choose (0, 220)) (fun b =>
  bindGen (elems_ 100 [25; 50; 100; 200; 3; 7]) (fun p =>
  bindGen (elems_ true [true; false]) (fun t =>
  returnGen (Build_Slot bool w o b p t)))))).

Definition genFrame : G (Frame bool) :=
  bindGen (elems_ 100 [100; 200]) (fun mf =>
  bindGen genSlot (fun r =>
  bindGen genSlot (fun f =>
  bindGen genSlot (fun b =>
  returnGen (probe_frame mf r f b))))).

Definition genTenants : G (list bool) :=
  bindGen (choose (0, 4)) (fun n => vectorOf n (elems_ true [true; false])).

(* -------------------------------------------------------------------------
   The properties.
   ------------------------------------------------------------------------- *)

(* S1's computable shadow: admission reads the four declared quantities and
   never the tenant, so permuting the tenancy cannot move the verdict
   (admission_is_occupancy_blind, admission_survives_every_retenanting). *)
Definition prop_retenanting_is_blind (f : Frame bool) (rts dts : list bool) : bool :=
  Bool.eqb (admits probe_composition (reassign_frame rts dts f))
           (admits probe_composition f).

(* S3's: a frame that is admitted has its reserved band admitted, the reserved
   half being a conjunct of the whole (reserved_band_discharged_once). *)
Definition prop_admitted_implies_reserved (f : Frame bool) : bool :=
  implb (admits probe_composition f) (reserved_half probe_composition f).

(* S5b's: the rung-change cost ignores the size of the rung being entered, so
   it is the same for two bands with different slot counts
   (rung_change_cost_is_one_switch). *)
Definition prop_cost_is_size_independent (f g : Frame bool) : bool :=
  Nat.eqb (rung_change_cost probe_composition (discretionary_band f))
          (rung_change_cost probe_composition (discretionary_band g)).

(* And the one that is not a theorem's shadow but the algebra's own arithmetic,
   which is where a generated draw beats an enumerated grid: the total width
   of a frame's slots is the sum of the reserved band's and the discretionary
   band's, at every draw rather than at the corners a grid names. *)
Definition prop_width_splits (f : Frame bool) : bool :=
  Nat.eqb (total_width (frame_slots f))
          (total_width (reserved_band f)
           + total_width (band_slots (discretionary_band f))).

QuickChick (forAll genFrame (fun f =>
              forAll genTenants (fun rts =>
                forAll genTenants (fun dts =>
                  prop_retenanting_is_blind f rts dts)))).

QuickChick (forAll genFrame prop_admitted_implies_reserved).

QuickChick (forAll genFrame (fun f =>
              forAll genFrame (fun g => prop_cost_is_size_independent f g))).

QuickChick (forAll genFrame prop_width_splits).

(* =========================================================================
   The second subject: EndpointIPC.v (R-07-027a, R-07-029a, R-07-031,
   R-07-031b, R-07-037b through R-07-037d, R-04-008, R-08-032, R-12-096).
   ========================================================================= *)

(* -------------------------------------------------------------------------
   Showing a counterexample. Each closed enumeration is shown at the position
   its own `all_*` list holds it at, which is the same index Vectors.v prints,
   so a counterexample here and a vector there name a member the same way.

   The machine's four function fields are not shown, and that is a property of
   what is asked of them rather than an omission: every obligation below that
   quantifies over a machine holds whatever those functions are, so a
   counterexample that turned on one would be a counterexample to a property
   this file does not state. What is shown is the data a drawn machine
   carries, which is what the shrinker can move.
   ------------------------------------------------------------------------- *)

#[global] Instance showInvocation : Show EndpointIPC.Invocation :=
  {| show i := "inv" ++ show (ipc_inv_ix i) |}.

#[global] Instance showNameable : Show EndpointIPC.Nameable :=
  {| show c := "nm" ++ show (ipc_nm_ix c) |}.

#[global] Instance showLifecycle : Show EndpointIPC.Lifecycle :=
  {| show op := "lc" ++ show (ipc_lc_ix op) |}.

#[global] Instance showAct : Show EndpointIPC.Act :=
  {| show a := "act" ++ show (ipc_act_ix a) |}.

#[global] Instance showMessage : Show EndpointIPC.Message :=
  {| show m := "(regs " ++ show (EndpointIPC.msg_regs m)
               ++ " caps " ++ show (EndpointIPC.msg_caps m) ++ ")" |}.

#[global] Instance showOffer : Show EndpointIPC.Offer :=
  {| show o := "(from " ++ show (EndpointIPC.offer_from o)
               ++ " at " ++ show (EndpointIPC.offer_at o)
               ++ " " ++ show (EndpointIPC.offer_carries o)
               ++ " badge " ++ show (EndpointIPC.offer_badge o) ++ ")" |}.

#[global] Instance showRing : Show EndpointIPC.Ring :=
  {| show r := "(produced " ++ show (EndpointIPC.produced r)
               ++ " consumed " ++ show (EndpointIPC.consumed r) ++ ")" |}.

#[global] Instance showMachine : Show EndpointIPC.Machine :=
  {| show m := "(parts " ++ show (EndpointIPC.partition_count m)
               ++ " eps " ++ show (EndpointIPC.endpoint_count m)
               ++ " words " ++ show (EndpointIPC.word_count m)
               ++ " slots " ++ show (EndpointIPC.slot_count m)
               ++ " badge " ++ show (EndpointIPC.badge_width m)
               ++ " arm " ++ show (EndpointIPC.pending_arm m)
               ++ " pw " ++ show (EndpointIPC.pending_width m)
               ++ " group " ++ show (EndpointIPC.group_members m) ++ ")" |}.

(* -------------------------------------------------------------------------
   The generators. The ranges are the ones the definitions decide inside: a
   payload that reaches past both budgets, a badge width past the declared
   one, a readiness index past the endpoint set, and ring indices on both
   sides of the drain.
   ------------------------------------------------------------------------- *)

Definition genInvocation : G EndpointIPC.Invocation :=
  elems_ EndpointIPC.Send EndpointIPC.all_invocations.

Definition genNameable : G EndpointIPC.Nameable :=
  elems_ EndpointIPC.NEndpoint EndpointIPC.all_nameable.

Definition genLifecycle : G EndpointIPC.Lifecycle :=
  elems_ EndpointIPC.LCreate EndpointIPC.all_lifecycles.

Definition genAct : G EndpointIPC.Act :=
  elems_ EndpointIPC.ASend EndpointIPC.all_acts.

(* A short list of small slot numbers. Small on purpose: a capability slot
   drawn from a wide range is almost never named twice and almost never named
   by two messages, so `carried` would answer false at nearly every draw and
   the grant properties would hold vacuously. *)
Definition genSlots : G (list nat) :=
  bindGen (choose (0, 5)) (fun n => vectorOf n (choose (0, 4))).

Definition genMessage : G EndpointIPC.Message :=
  bindGen genSlots (fun regs =>
  bindGen genSlots (fun caps =>
  returnGen {| EndpointIPC.msg_regs := regs; EndpointIPC.msg_caps := caps |})).

Definition genBadgeAt (w : nat) : G EndpointIPC.Badge :=
  vectorOf w (elems_ true (cons true (cons false nil))).

Definition genOffer : G EndpointIPC.Offer :=
  bindGen (choose (0, 6)) (fun from =>
  bindGen (choose (0, 6)) (fun at_ =>
  bindGen genMessage (fun msg =>
  bindGen (choose (0, 4)) (fun w =>
  bindGen (genBadgeAt w) (fun b =>
  returnGen {| EndpointIPC.offer_from := from; EndpointIPC.offer_at := at_;
               EndpointIPC.offer_carries := msg;
               EndpointIPC.offer_badge := b |}))))).

Definition genOffers : G (list EndpointIPC.Offer) :=
  bindGen (choose (0, 6)) (fun n => vectorOf n genOffer).

Definition genRing : G EndpointIPC.Ring :=
  bindGen (choose (0, 6)) (fun p =>
  bindGen (choose (0, 6)) (fun c => returnGen (ipc_ring p c))).

(* A readiness state is drawn as the index of its bit pattern, which is
   EndpointIPC.v's own `readiness_of`: the index is showable where the
   predicate is not, and it ranges past the sixteen states the enumerative
   half walks. *)
Definition genReadinessIx : G nat := choose (0, 255).

(* An invocation sequence, drawn two ways. The unconstrained one is what the
   generic occurrence facts are stated over; the second is the specification's
   own sequence with a drawn transposition applied, which is the only way a
   draw lands on a frozen surface often enough to decide anything. *)
Definition genInvSeq : G (list EndpointIPC.Invocation) :=
  bindGen (choose (0, 7)) (fun n => vectorOf n genInvocation).

Definition genPermutedSurface : G (list EndpointIPC.Invocation) :=
  bindGen (choose (0, 6)) (fun a =>
  bindGen (choose (0, 6)) (fun b =>
  returnGen (EndpointIPC.swap_at_inv a
               (EndpointIPC.swap_at_inv b EndpointIPC.spec_surface)))).

Definition genNameables : G (list EndpointIPC.Nameable) :=
  bindGen (choose (0, 5)) (fun n => vectorOf n genNameable).

(* The five-member cost table as a function, built from five drawn magnitudes.
   A cost function cannot be drawn directly, and this is the shape that keeps
   every field of the record a field: the table is data and the projection
   into `Invocation -> nat` is the machine's own field. *)
Definition cost_table (a b c d e : nat) : EndpointIPC.Invocation -> nat :=
  fun i => match i with
           | EndpointIPC.Send => a
           | EndpointIPC.Receive => b
           | EndpointIPC.PollSiteYield => c
           | EndpointIPC.GrantRedeem => d
           | EndpointIPC.Revoke => e
           end.

Definition genCosts : G (EndpointIPC.Invocation -> nat) :=
  bindGen (choose (0, 9)) (fun a =>
  bindGen (choose (0, 9)) (fun b =>
  bindGen (choose (0, 9)) (fun c =>
  bindGen (choose (0, 9)) (fun d =>
  bindGen (choose (0, 9)) (fun e => returnGen (cost_table a b c d e)))))).

(* The interrupt file, drawn from the comparisons a real one could be: the
   demo's equality, the probe's inequality, its converse, and the two
   constants. The constants are in the list on purpose, a file that is never
   set and a file that is always set being the two shapes a delivery
   obligation must still hold over. *)
Definition genPending : G (nat -> nat -> bool) :=
  elems_ (fun s b => Nat.eqb s b)
         (cons (fun s b => Nat.eqb s b)
         (cons (fun s b => Nat.ltb b s)
         (cons (fun s b => Nat.ltb s b)
         (cons (fun (_ : nat) (_ : nat) => false)
         (cons (fun (_ : nat) (_ : nat) => true) nil))))).

Definition genLabel : G (nat -> nat) :=
  bindGen (choose (1, 4)) (fun k => returnGen (fun u => Nat.modulo u k)).

Definition genMachine : G EndpointIPC.Machine :=
  bindGen (choose (0, 6)) (fun parts =>
  bindGen (choose (0, 5)) (fun eps =>
  bindGen (choose (0, 5)) (fun words =>
  bindGen (choose (0, 5)) (fun slots =>
  bindGen (choose (0, 4)) (fun bw =>
  bindGen genCosts (fun ic =>
  bindGen genCosts (fun rc =>
  bindGen (bindGen (choose (0, 4)) (fun n => vectorOf n (choose (0, 5))))
          (fun grp =>
  bindGen genLabel (fun lab =>
  bindGen (elems_ true (cons true (cons false nil))) (fun arm =>
  bindGen genPending (fun pend =>
  bindGen (choose (0, 4)) (fun pw =>
  returnGen {| EndpointIPC.partition_count := parts;
               EndpointIPC.endpoint_count := eps;
               EndpointIPC.word_count := words;
               EndpointIPC.slot_count := slots;
               EndpointIPC.badge_width := bw;
               EndpointIPC.invocation_cost := ic;
               EndpointIPC.refusal_cost := rc;
               EndpointIPC.group_members := grp;
               EndpointIPC.label := lab;
               EndpointIPC.pending_arm := arm;
               EndpointIPC.pending := pend;
               EndpointIPC.pending_width := pw |})))))))))))).

(* -------------------------------------------------------------------------
   The properties. Each names the theorem it shadows or, where it shadows
   none, the arithmetic it is the only check of.
   ------------------------------------------------------------------------- *)

(* S19's and S37a's shadow: the outcome of an offer is the peer's readiness
   bit and nothing else, at a drawn readiness index rather than at the sixteen
   the enumeration walks (the_outcome_is_the_readiness_bit). *)
Definition prop_outcome_is_the_readiness_bit (r : nat)
                                             (o : EndpointIPC.Offer) : bool :=
  Bool.eqb (EndpointIPC.is_refused
              (EndpointIPC.said EndpointIPC.spec_transfer
                                EndpointIPC.empty_kernel
                                (EndpointIPC.readiness_of r) o))
           (negb (EndpointIPC.readiness_of r (EndpointIPC.offer_at o))).

(* S20's: reading 6's typed refusal, that nothing crosses on the refusal arm
   (the_specification_carries_nothing_where_nothing_crossed). *)
Definition prop_nothing_crosses_on_a_refusal (r : nat)
                                             (o : EndpointIPC.Offer) : bool :=
  implb (negb (EndpointIPC.readiness_of r (EndpointIPC.offer_at o)))
        (negb (ipc_crossed
                 (EndpointIPC.delivered
                    (EndpointIPC.spec_run (EndpointIPC.readiness_of r) o)))).

(* S22's: nothing is parked at the end of an arbitrary offer sequence, at a
   drawn sequence rather than at the one fixed list of five the enumerative
   half walks (no_sequence_of_re_offers_parks_anything). *)
Definition prop_parks_nothing_over_a_drawn_sequence
             (r : nat) (l : list EndpointIPC.Offer) : bool :=
  Nat.eqb (EndpointIPC.count_of
             (EndpointIPC.held
                (EndpointIPC.run_offers EndpointIPC.spec_transfer
                                        EndpointIPC.empty_kernel
                                        (EndpointIPC.readiness_of r) l))) 0.

(* And the arithmetic no theorem in EndpointIPC.v states: the construction
   R-07-029a excludes accumulates exactly one parked request per offer that
   met an unready peer. The file proves that the queue is non-empty and
   computes one witness at three; this fixes the depth at every draw, which is
   what turns *there is a queue* into *this much of one*. *)
Definition prop_queue_depth_is_the_unsatisfied_offers
             (r : nat) (l : list EndpointIPC.Offer) : bool :=
  Nat.eqb (EndpointIPC.count_of
             (EndpointIPC.held
                (EndpointIPC.run_offers EndpointIPC.queueing_transfer
                                        EndpointIPC.empty_kernel
                                        (EndpointIPC.readiness_of r) l)))
          (EndpointIPC.count_of
             (EndpointIPC.filter_of
                (fun o => negb (EndpointIPC.readiness_of r
                                  (EndpointIPC.offer_at o))) l)).

(* S22a's (R-17-030x): a peer that is never ready refuses every offer of an
   arbitrary sequence (an_unready_peer_refuses_every_offer_in_a_sequence). *)
Definition prop_an_unready_peer_refuses_everything
             (l : list EndpointIPC.Offer) : bool :=
  EndpointIPC.all_of EndpointIPC.is_refused
    (EndpointIPC.outcomes_of EndpointIPC.spec_transfer
                             EndpointIPC.empty_kernel (fun _ => false) l).

(* S25's: the grant moves no slot the message does not name
   (the_specification_grant_transfers_only_what_is_named). *)
Definition prop_grant_moves_only_what_is_named
             (msg : EndpointIPC.Message) (h c : nat) : bool :=
  implb (negb (EndpointIPC.carried msg c))
        (Bool.eqb (EndpointIPC.spec_grant msg
                     (fun x => EndpointIPC.bit_at x h) c)
                  (EndpointIPC.bit_at c h)).

(* S23's, and its twin over the construction that breaks it: the ambient grant
   hands over everything the message names, so what refutes it is the slot it
   adds and not a different table (the_ambient_grant_mints' second half). *)
Definition prop_ambient_grant_still_grants_what_is_named
             (msg : EndpointIPC.Message) (h c : nat) : bool :=
  implb (EndpointIPC.carried msg c)
        (EndpointIPC.ambient_grant msg (fun x => EndpointIPC.bit_at x h) c).

(* The slot fault, over a drawn machine and a drawn payload: a message inside
   the register budget and past the capability-slot budget is refused. This is
   R-07-031's two components decided apart, which no single column of the
   admission check states and which the enumeration can only sample. *)
Definition prop_a_slot_fault_is_refused_on_its_own
             (m : EndpointIPC.Machine) (w s : nat) : bool :=
  implb (andb (Nat.leb w (EndpointIPC.word_count m))
              (Nat.ltb (EndpointIPC.slot_count m) s))
        (negb (EndpointIPC.message_ok m (ipc_message w s))).

(* And its twin, so that the slot budget and the register budget are two
   obligations rather than one stated twice: a payload past the register
   budget and inside the slot budget is refused as well. *)
Definition prop_a_register_fault_is_refused_on_its_own
             (m : EndpointIPC.Machine) (w s : nat) : bool :=
  implb (andb (Nat.ltb (EndpointIPC.word_count m) w)
              (Nat.leb s (EndpointIPC.slot_count m)))
        (negb (EndpointIPC.message_ok m (ipc_message w s))).

(* S13a's: the badge space is two to the declared width, at a drawn width
   (the_badge_space_is_two_to_the_declared_width). *)
Definition prop_badge_space_is_two_to_the_width (w : nat) : bool :=
  Nat.eqb (EndpointIPC.count_of (EndpointIPC.badges w))
          (EndpointIPC.two_pow w).

(* And the admission side of gap a, over a drawn machine and a drawn width:
   the generated space at a width is admitted exactly when that width is the
   machine's declared one, which is what makes `badge_ok` read its field. *)
Definition prop_badges_are_admitted_at_the_declared_width_alone
             (m : EndpointIPC.Machine) (w : nat) : bool :=
  Bool.eqb (EndpointIPC.all_of (EndpointIPC.badge_ok m)
                               (EndpointIPC.badges w))
           (Nat.eqb w (EndpointIPC.badge_width m)).

(* S12's: reading 2, that the frozen surface is a set and not an order, at a
   drawn sequence and a drawn index rather than at the four transpositions of
   one sequence (no_transposition_leaves_the_frozen_surface). *)
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
   one mask is the frozen surface, and this says which one at an unbounded
   index (no_proper_boolean_enumeration_is_the_frozen_surface). *)
Definition prop_only_the_full_mask_is_the_surface (n : nat) : bool :=
  let space := EndpointIPC.two_pow
                 (EndpointIPC.count_of EndpointIPC.all_invocations) in
  Bool.eqb (EndpointIPC.surface_mask_ok n)
           (Nat.eqb (Nat.modulo n space) (EndpointIPC.before_last space)).

(* S3's and S4a's. R-07-027a states the negative of the two tables and nothing
   positive of the three classes, so the obligation drawn here is the one the
   entry carries, that no table has a lifecycle, held of both admissible maps;
   and beside it the two constructions, the one that lets the schedule table
   be revoked and the one that admits nothing at all. Which acts each class
   has is EndpointIPC.v's gap j and no column here reads it
   (the_specification_gives_no_table_a_lifecycle,
   the_revoke_only_lifecycle_discharges_both, the_table_lifecycle_is_refuted,
   the_frozen_lifecycle_states_nothing). *)
Definition prop_lifecycles_split_tables_from_objects
             (c : EndpointIPC.Nameable) (op : EndpointIPC.Lifecycle) : bool :=
  andb (andb (implb (EndpointIPC.is_table c)
                    (negb (EndpointIPC.spec_lifecycles c op)))
             (implb (EndpointIPC.is_table c)
                    (negb (EndpointIPC.revoke_only_lifecycle c op))))
       (andb (implb (EndpointIPC.nameable_eqb c EndpointIPC.NScheduleTable)
                    (EndpointIPC.table_lifecycle c op))
             (negb (EndpointIPC.frozen_lifecycle c op))).

(* R-07-027a's closure read over a drawn candidate: an inventory that names a
   kernel table or the refused reply object is never closed, whatever else it
   names (no_fourth_class_is_closed, generalised off its index). *)
Definition prop_no_non_object_survives_the_inventory
             (l : list EndpointIPC.Nameable) : bool :=
  implb (EndpointIPC.any_of (fun c => negb (EndpointIPC.is_object c)) l)
        (negb (EndpointIPC.inventory_ok l)).

(* S11's: dispatch by the number alone, at two drawn observations
   (the_specification_dispatches_by_the_number_alone). *)
Definition prop_dispatch_ignores_the_observation (n a b : nat) : bool :=
  Nat.eqb (ipc_opt_inv_ix (EndpointIPC.spec_dispatch (fun _ => a) n))
          (ipc_opt_inv_ix (EndpointIPC.spec_dispatch (fun _ => b) n)).

(* And the twin over R-07-030's construction: the submission-queue dispatcher
   agrees with itself wherever the two observations agree, so what refutes it
   is the read of memory and not a different table. *)
Definition prop_the_queue_dispatch_agrees_where_the_memory_does
             (n a b : nat) : bool :=
  implb (Nat.eqb a b)
        (Nat.eqb (ipc_opt_inv_ix
                    (EndpointIPC.submission_queue_dispatch (fun _ => a) n))
                 (ipc_opt_inv_ix
                    (EndpointIPC.submission_queue_dispatch (fun _ => b) n))).

(* S30's: the rotation is composition-fixed, at a drawn machine and two drawn
   observations (the_specification_rotation_is_composition_fixed); and its
   twin, that the work-stealing construction agrees wherever nothing is
   observed, so the read and not the order is what refutes it. *)
Definition prop_the_rotation_is_composition_fixed
             (m : EndpointIPC.Machine) (a b u : nat) : bool :=
  andb (Nat.eqb (EndpointIPC.spec_advance m (fun _ => a) u)
                (EndpointIPC.spec_advance m (fun _ => b) u))
       (Nat.eqb (EndpointIPC.work_stealing_advance m (fun _ => 0) u)
                (EndpointIPC.advance m u)).

(* S32's: the delivered pending file does not vary with the predecessor, at a
   drawn machine whose interrupt file is itself drawn
   (the_specification_delivery_does_not_vary_with_the_predecessor); and the
   twin, which is R-07-044's disjunction as a drawn column rather than a
   restatement of the construction's body. The unswapped rotation varies with
   the predecessor exactly on the swap arm and exactly where the two
   predecessors' rows differ, which is what `implb` of the arm says: on the
   static arm the file is partitioned by member and the construction is
   admitted. This fails at a draw if the construction stops reading the arm,
   and it fails at a draw if the specification's delivery starts reading the
   predecessor, which is what the clause it replaces could not do. *)
Definition prop_delivery_ignores_the_predecessor
             (m : EndpointIPC.Machine) (p q s b : nat) : bool :=
  andb (Bool.eqb (EndpointIPC.spec_delivery m p s b)
                 (EndpointIPC.spec_delivery m q s b))
       (Bool.eqb (Bool.eqb (EndpointIPC.unswapped_delivery m p s b)
                           (EndpointIPC.unswapped_delivery m q s b))
                 (implb (EndpointIPC.pending_arm m)
                        (Bool.eqb (EndpointIPC.pending m p b)
                                  (EndpointIPC.pending m q b)))).

(* S28's and S29's, which are twins: the consumer never yields over work its
   recheck saw and never over work its own drain saw
   (the_specification_decider_rechecks_after_arming, ..._yields_only_...). *)
Definition prop_the_decider_never_yields_over_work
             (before now : EndpointIPC.Ring) : bool :=
  andb (implb (EndpointIPC.has_work now)
              (negb (EndpointIPC.spec_decide before now)))
       (implb (EndpointIPC.has_work before)
              (negb (EndpointIPC.spec_decide before now))).

(* And the lost wakeup as a universal rather than a witness, stated against
   the specification and not against the construction's own body. The naive
   consumer and the specification agree everywhere except where the drain saw
   nothing and the recheck would have seen work, and they differ there: that
   is the lost wakeup as an equality between two functions rather than as a
   restatement of one of them, and a redefinition of either decider moves one
   side of it. The clause it replaces asserted `naive_decide` equal to its own
   body and never mentioned the specification at all. *)
Definition prop_the_naive_decider_differs_exactly_at_the_lost_wakeup
             (before now : EndpointIPC.Ring) : bool :=
  Bool.eqb (Bool.eqb (EndpointIPC.naive_decide before now)
                     (EndpointIPC.spec_decide before now))
           (negb (andb (negb (EndpointIPC.has_work before))
                       (EndpointIPC.has_work now))).

(* Reading 13, over a drawn machine: R-07-029a's *within the invocation's own
   bounded cost* admits a refusal that spends the whole of it, and that holds
   of every composition rather than of the demo
   (the_refusal_that_spends_its_whole_invocation_is_admitted). *)
Definition prop_the_boundary_refusal_is_admitted
             (m : EndpointIPC.Machine) (i : EndpointIPC.Invocation) : bool :=
  Nat.leb (EndpointIPC.boundary_refusal m i) (EndpointIPC.invocation_cost m i).

(* The numbering's two clauses and the three constructions that break one
   each, stated as the clause each construction does *not* break. The
   specification's own second clause is now among them, and that is the
   change: it is stated against R-07-031b's criterion for what may be
   numbered rather than against `numbered_act`'s own body, so a draw can
   falsify it where an implication from a hypothesis to itself could not
   (the_specification_numbering_discharges_both, and the standing halves of
   the_iouring_numbering_is_refuted, the_fifth_group_numbering_is_refuted and
   the_short_numbering_drops_a_member). *)
Definition prop_the_numberings_split_on_one_clause_each
             (i : EndpointIPC.Invocation) (a : EndpointIPC.Act) : bool :=
  andb (andb (EndpointIPC.numbered_act (EndpointIPC.act_of i))
             (andb (EndpointIPC.iouring_numbering (EndpointIPC.act_of i))
                   (EndpointIPC.fifth_group_numbering (EndpointIPC.act_of i))))
       (andb (implb (negb (EndpointIPC.is_the_act_of_an_invocation a))
                    (negb (EndpointIPC.numbered_act a)))
             (implb (negb (EndpointIPC.is_the_act_of_an_invocation a))
                    (negb (EndpointIPC.short_numbering a)))).

(* Gap i as a drawn column. The two trap surfaces the criterion admits differ
   at exactly the three acts R-11-023 owes a carrier for and agree at the
   other fourteen, and every act the ABI numbers traps on both, so what the
   register does fix is decided at every draw and what it leaves open is
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

(* Reading 15's shadow, over a drawn dispatch sequence: R-07-037c's second
   conjunct, that the bits a member leaves are the bits it finds at its next
   dispatch. The sequence is filtered of the member itself and one other is
   prepended, so no draw is the empty one and the clause decides at every
   draw rather than holding where nothing happened. The sharing construction
   is run over the same sequence, so the column that separates them is the
   step and not the sequence
   (the_bits_a_member_leaves_are_restored_at_its_next_dispatch,
   the_sharing_step_overwrites_a_sibling). *)
Definition prop_a_members_bits_survive_a_dispatch_sequence
             (u pred b : nat) (l : list nat) : bool :=
  let others :=
    cons (S u) (EndpointIPC.filter_of (fun s => negb (Nat.eqb u s)) l) in
  andb (EndpointIPC.run_dispatches
          (EndpointIPC.step_of (fun _ _ => false)) (fun _ _ => true) pred
          others u b)
       (negb (EndpointIPC.run_dispatches
                (EndpointIPC.sharing_step (fun _ _ => false))
                (fun _ _ => true) pred others u b)).

QuickChick (forAll genReadinessIx (fun r =>
              forAll genOffer (prop_outcome_is_the_readiness_bit r))).

QuickChick (forAll genReadinessIx (fun r =>
              forAll genOffer (prop_nothing_crosses_on_a_refusal r))).

QuickChick (forAll genReadinessIx (fun r =>
              forAll genOffers (prop_parks_nothing_over_a_drawn_sequence r))).

QuickChick (forAll genReadinessIx (fun r =>
              forAll genOffers (prop_queue_depth_is_the_unsatisfied_offers r))).

QuickChick (forAll genOffers prop_an_unready_peer_refuses_everything).

QuickChick (forAll genMessage (fun msg =>
              forAll (choose (0, 63)) (fun h =>
                forAll (choose (0, 6)) (prop_grant_moves_only_what_is_named
                                          msg h)))).

QuickChick (forAll genMessage (fun msg =>
              forAll (choose (0, 63)) (fun h =>
                forAll (choose (0, 6))
                       (prop_ambient_grant_still_grants_what_is_named msg h)))).

QuickChick (forAll genMachine (fun m =>
              forAll (choose (0, 7)) (fun w =>
                forAll (choose (0, 7))
                       (prop_a_slot_fault_is_refused_on_its_own m w)))).

QuickChick (forAll genMachine (fun m =>
              forAll (choose (0, 7)) (fun w =>
                forAll (choose (0, 7))
                       (prop_a_register_fault_is_refused_on_its_own m w)))).

QuickChick (forAll (choose (0, 8)) prop_badge_space_is_two_to_the_width).

QuickChick (forAll genMachine (fun m =>
              forAll (choose (0, 6))
                     (prop_badges_are_admitted_at_the_declared_width_alone m))).

(* Run twice, over two generators, because one of them almost never reaches
   the interesting side. A sequence drawn freely is the frozen surface on 48
   of 10000 draws, measured rather than estimated, so over `genInvSeq` this
   property is very nearly always the agreement of two falses; over
   `genPermutedSurface` it is the agreement of two trues at every draw. The
   pair is what makes reading 2 checked in both directions rather than in the
   direction a generator happens to favour. *)
QuickChick (forAll (choose (0, 7)) (fun n =>
              forAll genInvSeq
                     (prop_a_transposition_does_not_move_the_verdict n))).

QuickChick (forAll (choose (0, 7)) (fun n =>
              forAll genPermutedSurface
                     (prop_a_transposition_does_not_move_the_verdict n))).

QuickChick (forAll (choose (0, 7)) (fun n =>
              forAll genInvocation (fun i =>
                forAll genPermutedSurface
                       (prop_an_insertion_adds_exactly_one_occurrence n i)))).

QuickChick (forAll (choose (0, 255)) prop_only_the_full_mask_is_the_surface).

QuickChick (forAll genNameable (fun c =>
              forAll genLifecycle
                     (prop_lifecycles_split_tables_from_objects c))).

QuickChick (forAll genNameables prop_no_non_object_survives_the_inventory).

QuickChick (forAll (choose (0, 8)) (fun n =>
              forAll (choose (0, 8)) (fun a =>
                forAll (choose (0, 8))
                       (prop_dispatch_ignores_the_observation n a)))).

QuickChick (forAll (choose (0, 8)) (fun n =>
              forAll (choose (0, 8)) (fun a =>
                forAll (choose (0, 8))
                  (prop_the_queue_dispatch_agrees_where_the_memory_does n a)))).

QuickChick (forAll genMachine (fun m =>
              forAll (choose (0, 6)) (fun a =>
                forAll (choose (0, 6)) (fun b =>
                  forAll (choose (0, 6))
                         (prop_the_rotation_is_composition_fixed m a b))))).

QuickChick (forAll genMachine (fun m =>
              forAll (choose (0, 5)) (fun p =>
                forAll (choose (0, 5)) (fun q =>
                  forAll (choose (0, 5)) (fun s =>
                    forAll (choose (0, 5))
                           (prop_delivery_ignores_the_predecessor m p q s)))))).

QuickChick (forAll genRing (fun before =>
              forAll genRing (prop_the_decider_never_yields_over_work before))).

QuickChick (forAll genRing (fun before =>
              forAll genRing
                (prop_the_naive_decider_differs_exactly_at_the_lost_wakeup
                   before))).

QuickChick (forAll genMachine (fun m =>
              forAll genInvocation (prop_the_boundary_refusal_is_admitted m))).

QuickChick (forAll genInvocation (fun i =>
              forAll genAct (prop_the_numberings_split_on_one_clause_each i))).

QuickChick (forAll genAct prop_the_trap_surfaces_differ_only_where_the_gap_is).

QuickChick (forAll (choose (0, 5)) (fun u =>
              forAll (choose (0, 5)) (fun pred =>
                forAll (choose (0, 3)) (fun b =>
                  forAll genSlots
                    (prop_a_members_bits_survive_a_dispatch_sequence u pred
                       b))))).
