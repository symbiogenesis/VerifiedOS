(* SPDX-License-Identifier: Apache-2.0 *)

(* =========================================================================
   The QuickChick harness: random generators over the Gallina front, for the
   property sets whose domains are too large to walk.

   Vectors.v beside this file walks a declared grid and prints what the
   admission algebra answers at every point of it. That is the half that runs
   with no install, and its limit is the grid: a defect outside the corners
   somebody named is a defect it does not reach. This half draws instead, so
   what it reaches is decided by the generator's range rather than by a list.
   A draw that refutes a property is reported as drawn: `forAll` shrinks
   nothing, so the counterexample QuickChick prints is the point it happened
   to draw and not a minimal one.

   **A set is drawn here only where its domain outruns the draws.**
   QuickChick spends 10,000 draws on a set, and a domain holding no more
   points than that is one a draw that size samples without covering. Each
   such set is decided at every point of its domain by Walks.v beside this
   file, which loads Stdlib alone, over the statements IPCProperties.v holds
   for both halves. The size of each domain left here is stated beside its
   `QuickChick` command, counted as Walks.v counts one: `choose (a, b)` holds
   b - a + 1 points, `elems_ d l` the members of l, `vectorOf n g` the
   n-length lists over g's points, and a generator binding several their
   product.

   **What a run extracts is fixed in this file, so a verdict replays.** One
   sentence below the imports replaces one of QuickChick's own extraction
   choices. QuickChick seeds its random state with
   `Random.State.make_self_init`, from system-dependent data, so no verdict
   need replay; the sentence fixes the seed, which `run.py quickchick
   properties` reads and reports, and every set is drawn from that seed.

   It needs `coq-quickchick`, which this repository installs in a switch of
   its own, the one tools/vos/gallina.py's QUICKCHICK_SWITCH names, from the
   snapshot tools/opam/quickchick.lock fixes. `run.py quickchick check` says
   which QuickChick that switch holds, by its release or, for a build from a
   commit pin, by the commit, and tools/opam/README.md states why the switch
   is separate from the proof gate's and what the snapshot installs.

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
   drawn below is stated over a drawn machine, a drawn readiness index, a
   drawn payload, a drawn width or a drawn offer sequence, so what it reaches
   is a range rather than a list. One of them is arithmetic no theorem in
   EndpointIPC.v states and no vector could check at every point:
   `prop_queue_depth_is_the_unsatisfied_offers`, which fixes exactly how much
   state the construction R-07-029a excludes would have accumulated.

   **Each refuting construction is decided against the obligation it does
   not break as well as the one it does,** here or in Walks.v. A property set
   that only ever exercised the defect would be measuring the shape of the
   construction rather than the named defect, so the ambient grant is checked
   to grant everything named, the io_uring numbering to number every
   invocation, the work-stealing rotation to agree wherever nothing is
   observed, and the submission-queue dispatcher to agree wherever the two
   observations agree.

   **A guarded property whose premise a generator rarely reaches holds
   vacuously, so the premises are measured and not assumed.** Over 10000 draws
   apiece, measured before the seed was fixed, the refusal arm is reached 5009
   times, a capability slot the payload names 2770, a slot fault 2366, a
   register fault 2455, and a drawn width that is the machine's declared one
   1416. A freely drawn invocation sequence is the frozen surface on 48 draws
   of 10000, so the transposition property is decided again over the
   sequences built from the specification's own by transposing it, every one
   of which is the frozen surface, and Walks.v walks that domain whole. The
   walked sets' premises are counted at every point of their domains by the
   walk itself, which fails a set whose premise no point meets.

   **An unguarded property owes no premise figure.** A property whose whole
   content is an equality between two definitions cannot hold vacuously; what
   it can do instead is hold by conversion because one side restates the
   other's body. The delivery property below and IPCProperties.v's lost-wakeup
   property are each stated against the specification they are about rather
   than against the construction they are named for, so a redefinition of
   either side moves one column and not both:
   `prop_the_naive_decider_differs_exactly_at_the_lost_wakeup` fails if either
   decider changes, and `prop_delivery_ignores_the_predecessor` fails if the
   unswapped construction stops reading R-07-044's arm or if the
   specification's delivery starts reading the predecessor.
   ========================================================================= *)

From QuickChick Require Import QuickChick.
From Stdlib Require Import List String.
Require Import PartitionContext.
Require Import BoundaryCost.
Require Import CyclicExecutive.
Require Import Probe.
Require EndpointIPC.
Require Import IPCProbe.
Require Import IPCProperties.

Import ListNotations.
Import QcDefaultNotation.
Open Scope qc_scope.
Open Scope string_scope.

(* The extraction QuickChick runs a property through touches accessors the
   plugin marks opaque; the warnings are about the extraction and not about
   the properties, and they are what a run would otherwise be read through. *)
Set Warnings "-extraction-opaque-accessed,-extraction".

(* QuickChick draws from `Random.State.make_self_init ()`, seeded from
   system-dependent data. Every set here is drawn from this one seed
   instead, so a run replays; tools/vos/gallina.py reads it and refuses a
   harness that fixes none, or fixes it ahead of a Require of QuickChick,
   whose loading states QuickChick's own seed over it. *)
Extract Constant RandomQC.newRandomSeed => "(Random.State.make [|20260930|])".

(* -------------------------------------------------------------------------
   Showing a counterexample. A drawn frame is only worth having if it can be
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

(* The domains below, each past the 10,000 draws. `genSlot` holds 12 * 221^3
   points, `genFrame` 2 * (12 * 221^3)^3 and `genTenants` 31. *)

(* genFrame * genTenants^2 = 2 * (12 * 221^3)^3 * 31^2 points: drawn. *)
QuickChick (forAll genFrame (fun f =>
              forAll genTenants (fun rts =>
                forAll genTenants (fun dts =>
                  prop_retenanting_is_blind f rts dts)))).

(* genFrame = 2 * (12 * 221^3)^3 points: drawn. *)
QuickChick (forAll genFrame prop_admitted_implies_reserved).

(* genFrame^2 = 4 * (12 * 221^3)^6 points: drawn. *)
QuickChick (forAll genFrame (fun f =>
              forAll genFrame (fun g => prop_cost_is_size_independent f g))).

(* genFrame = 2 * (12 * 221^3)^3 points: drawn. *)
QuickChick (forAll genFrame prop_width_splits).

(* An independently written arithmetic decision over generated boundary
   inputs. The expected cost adds each sequential component; it reads no
   residency_max, boundary_cost or full_switch_cost result. *)
Definition prop_boundary_admission (ctx op handler width workload : nat) (populated : bool) : bool :=
  let c := probe_boundary ctx op handler populated in
  Bool.eqb (slot_fits c (width + 1) (Build_Slot bool width 0 workload 100 true))
    (andb populated (Nat.leb (workload + (op + handler + (7 + 5 + 3 + ctx))) width)).

Definition prop_boundary_padding (ctx op handler sample : nat) : bool :=
  let c := probe_boundary ctx op handler true in
  let total := op + handler + (7 + 5 + 3 + ctx) in
  let elapsed := Nat.modulo sample (S total) in
  Nat.eqb (padded_release (machine c) (boundary_inputs c) 100
              elapsed) (100 + total).

(* 31^3 * 151 * 31 * 2 = 278,903,342 points: drawn. *)
QuickChick (forAll (choose (0, 30)) (fun ctx =>
  forAll (choose (0, 30)) (fun op => forAll (choose (0, 30)) (fun handler =>
    forAll (choose (0, 150)) (fun width => forAll (choose (0, 30)) (fun workload =>
      forAll (elems_ true [false; true]) (fun populated =>
        prop_boundary_admission ctx op handler width workload populated))))))).

(* 31^3 * 151 = 4,498,441 points: drawn. *)
QuickChick (forAll (choose (0, 30)) (fun ctx =>
  forAll (choose (0, 30)) (fun op => forAll (choose (0, 30)) (fun handler =>
    forAll (choose (0, 150)) (fun sample =>
      prop_boundary_padding ctx op handler sample))))).

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
   carries, which is what a counterexample can name.
   ------------------------------------------------------------------------- *)

#[global] Instance showInvocation : Show EndpointIPC.Invocation :=
  {| show i := "inv" ++ show (ipc_inv_ix i) |}.

#[global] Instance showMessage : Show EndpointIPC.Message :=
  {| show m := "(regs " ++ show (EndpointIPC.msg_regs m)
               ++ " caps " ++ show (EndpointIPC.msg_caps m) ++ ")" |}.

#[global] Instance showOffer : Show EndpointIPC.Offer :=
  {| show o := "(from " ++ show (EndpointIPC.offer_from o)
               ++ " at " ++ show (EndpointIPC.offer_at o)
               ++ " " ++ show (EndpointIPC.offer_carries o)
               ++ " badge " ++ show (EndpointIPC.offer_badge o) ++ ")" |}.

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
   one, and a readiness index past the endpoint set. The generators of the
   walked sets are Walks.v's domains, which enumerate what they drew.
   ------------------------------------------------------------------------- *)

Definition genInvocation : G EndpointIPC.Invocation :=
  elems_ EndpointIPC.Send EndpointIPC.all_invocations.

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

(* A readiness state is drawn as the index of its bit pattern, which is
   EndpointIPC.v's own `readiness_of`: the index is showable where the
   predicate is not, and it ranges past the sixteen states the enumerative
   half walks. *)
Definition genReadinessIx : G nat := choose (0, 255).

(* An unconstrained invocation sequence, which the generic occurrence facts
   are stated over. Its twin, the specification's own sequence with two
   transpositions applied, is the only way to land on a frozen surface often
   enough to decide anything, and its 49 points are walked by Walks.v. *)
Definition genInvSeq : G (list EndpointIPC.Invocation) :=
  bindGen (choose (0, 7)) (fun n => vectorOf n genInvocation).

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

(* The admission side of gap a, over a drawn machine and a drawn width: the
   generated space at a width is admitted exactly when that width is the
   machine's declared one, which is what makes `badge_ok` read its field. The
   badge space itself, two to the declared width, is IPCProperties.v's and is
   walked. *)
Definition prop_badges_are_admitted_at_the_declared_width_alone
             (m : EndpointIPC.Machine) (w : nat) : bool :=
  Bool.eqb (EndpointIPC.all_of (EndpointIPC.badge_ok m)
                               (EndpointIPC.badges w))
           (Nat.eqb w (EndpointIPC.badge_width m)).

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

(* Reading 13, over a drawn machine: R-07-029a's *within the invocation's own
   bounded cost* admits a refusal that spends the whole of it, and that holds
   of every composition rather than of the demo
   (the_refusal_that_spends_its_whole_invocation_is_admitted). *)
Definition prop_the_boundary_refusal_is_admitted
             (m : EndpointIPC.Machine) (i : EndpointIPC.Invocation) : bool :=
  Nat.leb (EndpointIPC.boundary_refusal m i) (EndpointIPC.invocation_cost m i).

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

(* The domains below, each past the 10,000 draws. `genMessage` holds 3,906^2
   = 15,256,836 points, `genOffer` 7 * 7 * 15,256,836 * 31 = 23,175,133,884,
   `genOffers` the sum of genOffer^n for n from 0 to 6, and `genMachine`
   7 * 6^3 * 5 * (10^5)^2 * 1,555 * 4 * 2 * 5 * 5, about 2.35 * 10^19. *)

(* 256 * genOffer = 5,932,834,274,304 points: drawn. *)
QuickChick (forAll genReadinessIx (fun r =>
              forAll genOffer (prop_outcome_is_the_readiness_bit r))).

(* 256 * genOffer = 5,932,834,274,304 points: drawn. *)
QuickChick (forAll genReadinessIx (fun r =>
              forAll genOffer (prop_nothing_crosses_on_a_refusal r))).

(* 256 * genOffers points: drawn. *)
QuickChick (forAll genReadinessIx (fun r =>
              forAll genOffers (prop_parks_nothing_over_a_drawn_sequence r))).

(* 256 * genOffers points: drawn. *)
QuickChick (forAll genReadinessIx (fun r =>
              forAll genOffers (prop_queue_depth_is_the_unsatisfied_offers r))).

(* genOffers points: drawn. *)
QuickChick (forAll genOffers prop_an_unready_peer_refuses_everything).

(* genMessage * 64 * 7 = 6,835,062,528 points: drawn. *)
QuickChick (forAll genMessage (fun msg =>
              forAll (choose (0, 63)) (fun h =>
                forAll (choose (0, 6)) (prop_grant_moves_only_what_is_named
                                          msg h)))).

(* genMessage * 64 * 7 = 6,835,062,528 points: drawn. *)
QuickChick (forAll genMessage (fun msg =>
              forAll (choose (0, 63)) (fun h =>
                forAll (choose (0, 6))
                       (prop_ambient_grant_still_grants_what_is_named msg h)))).

(* genMachine * 8 * 8 points: drawn. *)
QuickChick (forAll genMachine (fun m =>
              forAll (choose (0, 7)) (fun w =>
                forAll (choose (0, 7))
                       (prop_a_slot_fault_is_refused_on_its_own m w)))).

(* genMachine * 8 * 8 points: drawn. *)
QuickChick (forAll genMachine (fun m =>
              forAll (choose (0, 7)) (fun w =>
                forAll (choose (0, 7))
                       (prop_a_register_fault_is_refused_on_its_own m w)))).

(* genMachine * 7 points: drawn. *)
QuickChick (forAll genMachine (fun m =>
              forAll (choose (0, 6))
                     (prop_badges_are_admitted_at_the_declared_width_alone m))).

(* Decided over two domains, because one of them almost never reaches the
   interesting side. A sequence drawn freely is the frozen surface on 48 of
   10000 draws, measured rather than estimated, so over `genInvSeq` this
   property is very nearly always the agreement of two falses; over the
   specification's own sequence transposed, which Walks.v walks whole, it is
   the agreement of two trues at every point. The pair is what makes reading
   2 checked in both directions rather than in the direction a generator
   happens to favour. Here, 8 * (5^0 + ... + 5^7) = 781,248 points: drawn. *)
QuickChick (forAll (choose (0, 7)) (fun n =>
              forAll genInvSeq
                     (prop_a_transposition_does_not_move_the_verdict n))).

(* genMachine * 7^3 points: drawn. *)
QuickChick (forAll genMachine (fun m =>
              forAll (choose (0, 6)) (fun a =>
                forAll (choose (0, 6)) (fun b =>
                  forAll (choose (0, 6))
                         (prop_the_rotation_is_composition_fixed m a b))))).

(* genMachine * 6^4 points: drawn. *)
QuickChick (forAll genMachine (fun m =>
              forAll (choose (0, 5)) (fun p =>
                forAll (choose (0, 5)) (fun q =>
                  forAll (choose (0, 5)) (fun s =>
                    forAll (choose (0, 5))
                           (prop_delivery_ignores_the_predecessor m p q s)))))).

(* genMachine * 5 points: drawn. *)
QuickChick (forAll genMachine (fun m =>
              forAll genInvocation (prop_the_boundary_refusal_is_admitted m))).

(* 6 * 6 * 4 * 3,906 = 562,464 points: drawn. *)
QuickChick (forAll (choose (0, 5)) (fun u =>
              forAll (choose (0, 5)) (fun pred =>
                forAll (choose (0, 3)) (fun b =>
                  forAll genSlots
                    (prop_a_members_bits_survive_a_dispatch_sequence u pred
                       b))))).
