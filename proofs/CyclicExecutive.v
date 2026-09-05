(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   CyclicExecutive.v

   The static cyclic executive as the register fixes it: R-07-032's
   table-driven schedule with no runtime decision, R-11-006's
   interval-arithmetic admission check, R-11-020's reserved band identical
   across rungs, R-11-021's rung ladder, R-11-022's one focus slot plus the
   rest, R-11-023's slot-to-tenant permutation and the invariance it
   asserts, R-11-024's table swap, R-11-025's non-load-following rung
   index, R-11-026's hard ceiling, and R-11-014a and R-11-014d's one phase
   offset and one major-frame length.

   The Require is load-bearing rather than decorative: R-11-009 has
   admission count the partition-switch constant explicitly instead of
   absorbing it into slack, and that constant is PartitionContext.v's
   switch_cost, which is R-15-220's three terms. This file consumes it and
   restates none of it.

   What this file is. A statement artifact in ApexTheorem.v's idiom.
   Composition constants are fields of the Composition record, never
   literals: R-11-021's criterion calls the 4/8/16/32 ladder "the reference
   instantiation", the focus majority is "composition-fixed", the phase
   offsets and slot widths are composition inputs, and the per-slot WCET
   magnitudes are R-11-015's derivation, whose timing-annotation
   specification is not authored. Nothing is admitted and nothing is
   axiomatized.

   What this file does not do. It executes nothing, on either emulator or
   anywhere else. The computed checks below are decided inside the kernel
   by conversion and print nothing; the gate's green line means compiled,
   axiom-free, and enumerated rather than verified.

   Readings of the register this statement takes:

   1. Admission reads the declared slot geometry and never an occupant.
      R-11-023's criterion enumerates the check's inputs as slot widths,
      slot offsets, each task's period and the switch-duty ratio R-11-009
      requires counted, and never an occupant, which is the check R-11-006
      and R-11-009 state between them. The load-bearing half is "never
      occupants", so the geometry a slot declares here is its width, its
      offset, its declared in-slot bound, and its declared visit period,
      and the invariance is stated over all four of those. That the
      criterion once read narrower than the check was reported here and
      resolved at that entry's own Accept (S1); carried back at S25.
   2. A slot's declared bound is a property of the slot and not of its
      tenant, which is what keeps reading 1 true. R-11-022a makes the visit
      period a shape choice for the same reason: two shorter focus slots
      per frame halve the focus visit period "at identical share,
      admissible because the interval arithmetic quantifies over widths and
      offsets and never occupants".
   3. Harmonicity is a parameter. R-11-006 says a task's period is
      "harmonic with" the major frame and does not say in which direction,
      so harmonic is a field and no direction is fixed here.
   4. R-11-022's shape is a record and not an invariant. "One focus slot
      plus (n-1) background slots" is realized as a Band carrying one focus
      and a list of background slots, which cannot be violated rather than
      being proved unviolated; what is proved of it is that the focus
      majority reads widths alone and that the shape survives every
      retenanting.
   5. R-11-020 and R-11-014d are stated of a ladder as a side condition and
      not built into its shape, so a ladder whose rungs disagree is
      expressible and the theorems have something to exclude.
   6. The four kernel acts this file touches are transitions of the
      schedule and never ABI entry points: R-11-023's focus rebinding is a
      retenanting of a frame, R-11-024's rung change is a selection among a
      ladder's rungs, R-11-026's suspension is an arm of the arrival step,
      and R-07-037b's poll-site yield is PartitionContext.v's Rotation.
      None is named, signed, or numbered as an invocation.

   What this file deliberately does not author, with the entry that owes
   each decision:

   a. The frozen ABI's invocation list. R-07-031a's criterion audits an
      enumeration no artifact carries. Owed at R-07-031a.
   b. Endpoint and notification IPC in every part: object state, the
      blocking discipline, badges, the message transfer shape, the
      notification object's representation, and whether a reply object
      exists. Owed at R-07-029, R-07-031, R-07-031a, and R-07-007.
   c. A closed inductive of kernel object classes. The Outcome inductive
      below is over R-11-026's own three arms for what an arrival meets and
      is not an object inventory.
   d. Which direction R-11-006's harmonicity runs (reading 3).
   e. Every composition magnitude: the ladder's rungs, the focus majority,
      the phase offsets, the slot widths and offsets, the per-slot WCET
      magnitudes, the top rung's capacity, and the table-load constant.
      The demo composition below instantiates them with arbitrary witness
      values that carry no composition claim.
   f. R-11-006b's intra-group cadence check and its rotation-step constant.
      That entry's arithmetic is over declared visit cadences and rotation
      orders that no artifact carries, so this file states the rotation's
      relation to the switch (in PartitionContext.v) and not its admission.
   g. R-11-015's WCET magnitudes and R-11-017's OPP assignment. Both are
      crown-jewel specifications that are not authored, so a slot's bound
      and a machine's cost fields are declared inputs here.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary check, cost function, index function, arrival
   step or time-to-slot map, proved of the specification, and refuted of an
   alternative construction the register's own sentence excludes. Two of
   the statements are definitional rather than proved content and are
   labelled where they stand: R-11-022's focus shape is a record shape
   (reading 4), and R-11-024's cost ignores the rung's size by
   construction, its content sitting in the refutation beside it.
   Inhabitation is concrete rather than assumed: a two-rung ladder that is
   well formed and admitted, and computed checks in the silent Example form
   for a frame that admits, a frame whose slots overlap, a frame whose
   declared bound plus the switch constant exceeds its width, and a
   composition whose harmonic predicate refuses.
   ========================================================================= *)

Require Import PartitionContext.

(* -------------------------------------------------------------------------
   The composition: every schedule quantity the register leaves to
   composition, carried as fields for the reason PartitionContext.v's
   Machine record is (a top-level Parameter prints as an assumption).
   ------------------------------------------------------------------------- *)

Record Composition : Type := {
  machine : Machine;             (* R-11-009's partition-switch constant is
                                    R-15-220's three terms, consumed and
                                    not restated                            *)
  Tenant : Type;                 (* R-11-023: a sole compartment or one
                                    R-07-037b same-label group              *)
  harmonic : nat -> nat -> bool; (* R-11-006 says "harmonic" and not in
                                    which direction (reading 3)             *)
  focus_majority : nat -> nat -> bool;
                                 (* R-11-022's "composition-fixed majority
                                    of the band"                            *)
  rung_of_count : nat -> nat;    (* R-11-021's ladder, whose 4/8/16/32 is
                                    the reference instantiation             *)
  top_rung_capacity : nat;       (* R-11-026's hard ceiling                 *)
  table_load_cost : nat          (* R-11-024's "plus the table load"        *)
}.

(* -------------------------------------------------------------------------
   Slots, bands, frames, and ladders. A slot declares four geometric
   quantities and carries one tenant; the four are what admission reads and
   the tenant is what R-11-023 permutes.
   ------------------------------------------------------------------------- *)

Record Slot (T : Type) : Type := {
  slot_width : nat;
  slot_offset : nat;
  slot_bound : nat;              (* the declared in-slot bound R-11-015
                                    derives elsewhere                       *)
  slot_period : nat;             (* the declared visit period R-11-006 calls
                                    harmonic with the major frame           *)
  slot_tenant : T
}.

Arguments slot_width {T} _.
Arguments slot_offset {T} _.
Arguments slot_bound {T} _.
Arguments slot_period {T} _.
Arguments slot_tenant {T} _.

(* R-11-022's shape, as a shape (reading 4). *)
Record Band (T : Type) : Type := {
  band_focus : Slot T;
  band_background : list (Slot T)
}.

Arguments band_focus {T} _.
Arguments band_background {T} _.

Record Frame (T : Type) : Type := {
  major_frame : nat;             (* R-11-014d's one length                  *)
  phase_offset : nat;            (* R-11-014a's one offset per core         *)
  reserved_band : list (Slot T); (* R-11-020's identical band               *)
  discretionary_band : Band T
}.

Arguments major_frame {T} _.
Arguments phase_offset {T} _.
Arguments reserved_band {T} _.
Arguments discretionary_band {T} _.

Record Ladder (T : Type) : Type := { ladder_rungs : list (Frame T) }.

Arguments ladder_rungs {T} _.

Definition band_slots {T : Type} (b : Band T) : list (Slot T) :=
  cons (band_focus b) (band_background b).

Definition frame_slots {T : Type} (f : Frame T) : list (Slot T) :=
  app (reserved_band f) (band_slots (discretionary_band f)).

(* -------------------------------------------------------------------------
   List helpers, defined here rather than imported: the prelude carries the
   list type and not the library over it, and importing a module to save
   four lines would put its assumptions inside the R-05-163 gate's reach
   for no gain.
   ------------------------------------------------------------------------- *)

Fixpoint all_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => true
  | cons x r => andb (p x) (all_of p r)
  end.

Fixpoint count_of {A : Type} (l : list A) : nat :=
  match l with nil => 0 | cons _ r => S (count_of r) end.

Fixpoint total_width {T : Type} (l : list (Slot T)) : nat :=
  match l with nil => 0 | cons s r => slot_width s + total_width r end.

(* -------------------------------------------------------------------------
   R-11-006's interval arithmetic, and R-11-009's switch duty inside it.
   Every clause reads a declared geometric quantity and none reads a
   tenant, which is reading 1 made structural.
   ------------------------------------------------------------------------- *)

Definition slot_fits (c : Composition) (mf : nat) (s : Slot (Tenant c)) : bool :=
  andb (Nat.leb (slot_offset s + slot_width s) mf)
       (andb (Nat.leb (slot_bound s + switch_cost c.(machine)) (slot_width s))
             (c.(harmonic) (slot_period s) mf)).

Definition disjoint {T : Type} (s t : Slot T) : bool :=
  orb (Nat.leb (slot_offset s + slot_width s) (slot_offset t))
      (Nat.leb (slot_offset t + slot_width t) (slot_offset s)).

Fixpoint disjoint_from {T : Type} (s : Slot T) (l : list (Slot T)) : bool :=
  match l with
  | nil => true
  | cons t r => andb (disjoint s t) (disjoint_from s r)
  end.

Fixpoint pairwise_disjoint {T : Type} (l : list (Slot T)) : bool :=
  match l with
  | nil => true
  | cons s r => andb (disjoint_from s r) (pairwise_disjoint r)
  end.

Definition admits (c : Composition) (f : Frame (Tenant c)) : bool :=
  andb (all_of (slot_fits c (major_frame f)) (frame_slots f))
       (pairwise_disjoint (frame_slots f)).

(* R-11-020's half of the verdict: the reserved band alone. *)
Definition reserved_half (c : Composition) (f : Frame (Tenant c)) : bool :=
  andb (all_of (slot_fits c (major_frame f)) (reserved_band f))
       (pairwise_disjoint (reserved_band f)).

(* -------------------------------------------------------------------------
   Geometry, and R-11-023's permutation. SameGeometry is what "the same
   schedule under a different tenancy" means: the four declared quantities
   agree slot by slot and the tenants are unconstrained.
   ------------------------------------------------------------------------- *)

Inductive SameGeometry {T : Type} : list (Slot T) -> list (Slot T) -> Prop :=
| SG_nil : SameGeometry nil nil
| SG_cons : forall (s t : Slot T) (l1 l2 : list (Slot T)),
    slot_width s = slot_width t ->
    slot_offset s = slot_offset t ->
    slot_bound s = slot_bound t ->
    slot_period s = slot_period t ->
    SameGeometry l1 l2 ->
    SameGeometry (cons s l1) (cons t l2).

Lemma same_geometry_refl :
  forall (T : Type) (l : list (Slot T)), SameGeometry l l.
Proof.
  intros T l. induction l as [ | s r IH ].
  - apply SG_nil.
  - apply SG_cons; try reflexivity. exact IH.
Qed.

Lemma same_geometry_app :
  forall (T : Type) (a1 a2 b1 b2 : list (Slot T)),
    SameGeometry a1 a2 -> SameGeometry b1 b2 ->
    SameGeometry (app a1 b1) (app a2 b2).
Proof.
  intros T a1 a2 b1 b2 Ha.
  induction Ha as [ | s t l1 l2 Hw Ho Hb Hp Hrest IH ]; intros Hb2.
  - exact Hb2.
  - simpl. apply SG_cons; try assumption. apply IH. exact Hb2.
Qed.

(* R-11-023's own act: the kernel permutes the slot-to-tenant map, the
   widths and offsets being fixed by the rung. *)
Definition retenant_slot {T : Type} (s : Slot T) (t : T) : Slot T :=
  Build_Slot T (slot_width s) (slot_offset s) (slot_bound s) (slot_period s) t.

Fixpoint reassign {T : Type} (ts : list T) (l : list (Slot T)) : list (Slot T) :=
  match ts, l with
  | cons t tr, cons s sr => cons (retenant_slot s t) (reassign tr sr)
  | nil, _ => l
  | _, nil => nil
  end.

Definition reassign_band {T : Type} (ts : list T) (b : Band T) : Band T :=
  match ts with
  | nil => b
  | cons t tr =>
      Build_Band T (retenant_slot (band_focus b) t)
                   (reassign tr (band_background b))
  end.

Definition reassign_frame {T : Type} (rts dts : list T) (f : Frame T) : Frame T :=
  Build_Frame T (major_frame f) (phase_offset f)
    (reassign rts (reserved_band f))
    (reassign_band dts (discretionary_band f)).

Lemma reassign_same_geometry :
  forall (T : Type) (ts : list T) (l : list (Slot T)),
    SameGeometry (reassign ts l) l.
Proof.
  intros T ts. induction ts as [ | t tr IH ]; intros l.
  - apply same_geometry_refl.
  - destruct l as [ | s sr ].
    + apply SG_nil.
    + simpl. apply SG_cons; try reflexivity. apply IH.
Qed.

Lemma band_slots_reassign :
  forall (T : Type) (ts : list T) (b : Band T),
    band_slots (reassign_band ts b) = reassign ts (band_slots b).
Proof. intros T ts b. destruct ts; reflexivity. Qed.

Lemma band_slots_reassign_same_geometry :
  forall (T : Type) (ts : list T) (b : Band T),
    SameGeometry (band_slots (reassign_band ts b)) (band_slots b).
Proof.
  intros T ts b. rewrite band_slots_reassign. apply reassign_same_geometry.
Qed.

Lemma frame_slots_reassign_same_geometry :
  forall (T : Type) (rts dts : list T) (f : Frame T),
    SameGeometry (frame_slots (reassign_frame rts dts f)) (frame_slots f).
Proof.
  intros T rts dts f.
  change (SameGeometry
            (app (reassign rts (reserved_band f))
                 (band_slots (reassign_band dts (discretionary_band f))))
            (app (reserved_band f) (band_slots (discretionary_band f)))).
  apply same_geometry_app.
  - apply reassign_same_geometry.
  - apply band_slots_reassign_same_geometry.
Qed.

(* -------------------------------------------------------------------------
   S1 and S2: R-11-023's invariance, stated of an arbitrary check so that
   an occupancy-sensitive one can be exhibited and refuted.
   ------------------------------------------------------------------------- *)

Definition OccupancyBlind (c : Composition)
                          (chk : Frame (Tenant c) -> bool) : Prop :=
  forall f g : Frame (Tenant c),
    major_frame f = major_frame g ->
    SameGeometry (frame_slots f) (frame_slots g) ->
    chk f = chk g.

Lemma slot_fits_same_geometry :
  forall (c : Composition) (mf : nat) (s t : Slot (Tenant c)),
    slot_width s = slot_width t -> slot_offset s = slot_offset t ->
    slot_bound s = slot_bound t -> slot_period s = slot_period t ->
    slot_fits c mf s = slot_fits c mf t.
Proof.
  intros c mf s t Hw Ho Hb Hp. unfold slot_fits.
  rewrite Hw. rewrite Ho. rewrite Hb. rewrite Hp. reflexivity.
Qed.

Lemma all_of_fits_same_geometry :
  forall (c : Composition) (mf : nat) (l1 l2 : list (Slot (Tenant c))),
    SameGeometry l1 l2 ->
    all_of (slot_fits c mf) l1 = all_of (slot_fits c mf) l2.
Proof.
  intros c mf l1 l2 H.
  induction H as [ | s t r1 r2 Hw Ho Hb Hp Hrest IH ].
  - reflexivity.
  - simpl. rewrite (slot_fits_same_geometry c mf s t Hw Ho Hb Hp).
    rewrite IH. reflexivity.
Qed.

Lemma disjoint_from_same_geometry :
  forall (T : Type) (s t : Slot T) (l1 l2 : list (Slot T)),
    slot_width s = slot_width t -> slot_offset s = slot_offset t ->
    SameGeometry l1 l2 -> disjoint_from s l1 = disjoint_from t l2.
Proof.
  intros T s t l1 l2 Hw Ho H.
  induction H as [ | u v r1 r2 Hw2 Ho2 Hb2 Hp2 Hrest IH ].
  - reflexivity.
  - simpl. unfold disjoint.
    rewrite Hw. rewrite Ho. rewrite Hw2. rewrite Ho2. rewrite IH. reflexivity.
Qed.

Lemma pairwise_disjoint_same_geometry :
  forall (T : Type) (l1 l2 : list (Slot T)),
    SameGeometry l1 l2 -> pairwise_disjoint l1 = pairwise_disjoint l2.
Proof.
  intros T l1 l2 H.
  induction H as [ | s t r1 r2 Hw Ho Hb Hp Hrest IH ].
  - reflexivity.
  - simpl. rewrite (disjoint_from_same_geometry T s t r1 r2 Hw Ho Hrest).
    rewrite IH. reflexivity.
Qed.

(* S1 (R-11-023 and its criterion). Two frames of one geometry receive one
   verdict, whatever occupies their slots. *)
Theorem admission_is_occupancy_blind :
  forall c : Composition, OccupancyBlind c (admits c).
Proof.
  intros c f g Hmf Hgeo. unfold admits. rewrite Hmf.
  rewrite (all_of_fits_same_geometry c (major_frame g) _ _ Hgeo).
  rewrite (pairwise_disjoint_same_geometry (Tenant c) _ _ Hgeo).
  reflexivity.
Qed.

(* S1b: R-11-023's act itself. The compositor's focus rebinding, and every
   other retenanting of a frame, leaves the verdict where it was. *)
Theorem admission_survives_every_retenanting :
  forall (c : Composition) (rts dts : list (Tenant c)) (f : Frame (Tenant c)),
    admits c (reassign_frame rts dts f) = admits c f.
Proof.
  intros c rts dts f.
  apply (admission_is_occupancy_blind c).
  - reflexivity.
  - apply frame_slots_reassign_same_geometry.
Qed.

(* -------------------------------------------------------------------------
   S3 and S4: the ladder, R-11-020's reserved band and R-11-014a and
   R-11-014d's one length and one offset. Membership and the sharing
   condition are recursive predicates rather than inductive relations, so
   every proof below is a structural induction over the rung list and none
   rests on an inversion.
   ------------------------------------------------------------------------- *)

Fixpoint InFrame {T : Type} (f : Frame T) (l : list (Frame T)) : Prop :=
  match l with
  | nil => False
  | cons g r => g = f \/ InFrame f r
  end.

Fixpoint AllShare {T : Type} (mf ph : nat) (res : list (Slot T))
                  (l : list (Frame T)) : Prop :=
  match l with
  | nil => True
  | cons f r =>
      major_frame f = mf /\ phase_offset f = ph /\ reserved_band f = res
      /\ AllShare mf ph res r
  end.

(* R-11-020 and R-11-014d as a side condition on a ladder, not as its shape
   (reading 5). *)
Definition WellFormedLadder {T : Type} (l : Ladder T) : Prop :=
  exists (mf ph : nat) (res : list (Slot T)),
    AllShare mf ph res (ladder_rungs l).

Lemma all_share_member :
  forall (T : Type) (mf ph : nat) (res : list (Slot T))
         (rungs : list (Frame T)) (f : Frame T),
    AllShare mf ph res rungs -> InFrame f rungs ->
    major_frame f = mf /\ phase_offset f = ph /\ reserved_band f = res.
Proof.
  intros T mf ph res rungs. induction rungs as [ | g r IH ]; intros f Hall Hin.
  - destruct Hin.
  - destruct Hall as [ H1 [ H2 [ H3 Hrest ] ] ].
    destruct Hin as [ Heq | Hin ].
    + rewrite <- Heq. split; [ exact H1 | split; [ exact H2 | exact H3 ] ].
    + exact (IH f Hrest Hin).
Qed.

(* S3 (R-11-020 and its criterion): the hard-deadline half of the verdict
   is one value across the whole ladder, so no population change moves it. *)
Theorem reserved_band_discharged_once :
  forall (c : Composition) (mf ph : nat) (res : list (Slot (Tenant c)))
         (rungs : list (Frame (Tenant c))) (f g : Frame (Tenant c)),
    AllShare mf ph res rungs -> InFrame f rungs -> InFrame g rungs ->
    reserved_half c f = reserved_half c g.
Proof.
  intros c mf ph res rungs f g Hall Hf Hg.
  destruct (all_share_member _ _ _ _ _ _ Hall Hf) as [ Hmf1 [ _ Hres1 ] ].
  destruct (all_share_member _ _ _ _ _ _ Hall Hg) as [ Hmf2 [ _ Hres2 ] ].
  unfold reserved_half.
  rewrite Hmf1. rewrite Hmf2. rewrite Hres1. rewrite Hres2. reflexivity.
Qed.

(* S4 (R-11-014d, R-11-014a): no rung swap lengthens the frame or shifts a
   frame origin. *)
Theorem one_frame_length_across_rungs :
  forall (T : Type) (mf ph : nat) (res : list (Slot T))
         (rungs : list (Frame T)) (f g : Frame T),
    AllShare mf ph res rungs -> InFrame f rungs -> InFrame g rungs ->
    major_frame f = major_frame g /\ phase_offset f = phase_offset g.
Proof.
  intros T mf ph res rungs f g Hall Hf Hg.
  destruct (all_share_member _ _ _ _ _ _ Hall Hf) as [ Hmf1 [ Hph1 _ ] ].
  destruct (all_share_member _ _ _ _ _ _ Hall Hg) as [ Hmf2 [ Hph2 _ ] ].
  split.
  - rewrite Hmf1. rewrite Hmf2. reflexivity.
  - rewrite Hph1. rewrite Hph2. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   S5: R-11-024's table swap.
   ------------------------------------------------------------------------- *)

Definition LadderAdmits (c : Composition) (l : Ladder (Tenant c)) : Prop :=
  forall f : Frame (Tenant c), InFrame f (ladder_rungs l) -> admits c f = true.

(* S5 (R-11-024, joined to R-11-020 and R-11-014d): the swap selects among
   schedules the generation already proved, so it creates no admission
   obligation; and inside a ladder that shares what R-11-020 and R-11-014d
   make it share, it moves neither the reserved band's half of the verdict,
   nor the frame length, nor the phase offset. *)
Theorem rung_change_is_a_table_swap :
  forall (c : Composition) (l : Ladder (Tenant c)) (mf ph : nat)
         (res : list (Slot (Tenant c))) (f g : Frame (Tenant c)),
    AllShare mf ph res (ladder_rungs l) -> LadderAdmits c l ->
    InFrame f (ladder_rungs l) -> InFrame g (ladder_rungs l) ->
    admits c f = true /\ admits c g = true
    /\ reserved_half c f = reserved_half c g
    /\ major_frame f = major_frame g
    /\ phase_offset f = phase_offset g.
Proof.
  intros c l mf ph res f g Hall Hadm Hf Hg.
  split; [ exact (Hadm f Hf) | ].
  split; [ exact (Hadm g Hg) | ].
  split.
  - exact (reserved_band_discharged_once c mf ph res (ladder_rungs l)
             f g Hall Hf Hg).
  - exact (one_frame_length_across_rungs (Tenant c) mf ph res (ladder_rungs l)
             f g Hall Hf Hg).
Qed.

(* R-11-024's cost: "one partition-switch constant plus the table load". *)
Definition rung_change_cost (c : Composition) (b : Band (Tenant c)) : nat :=
  switch_cost c.(machine) + c.(table_load_cost).

Definition SizeIndependent (c : Composition)
                           (cost : Band (Tenant c) -> nat) : Prop :=
  forall b d : Band (Tenant c), cost b = cost d.

(* S5b: one switch, not one per slot of the rung being entered. The claim
   is definitional on this side and refutable on the other, which is where
   its content is (per_slot_swap_cost_is_refuted below). *)
Theorem rung_change_cost_is_one_switch :
  forall c : Composition, SizeIndependent c (rung_change_cost c).
Proof. intros c b d. reflexivity. Qed.

(* -------------------------------------------------------------------------
   S6: R-11-022's focus shape.
   ------------------------------------------------------------------------- *)

Definition FocusShaped (c : Composition) (b : Band (Tenant c)) : bool :=
  c.(focus_majority) (slot_width (band_focus b)) (total_width (band_slots b)).

Definition BandOccupancyBlind (c : Composition)
                              (p : Band (Tenant c) -> bool) : Prop :=
  forall (ts : list (Tenant c)) (b : Band (Tenant c)),
    p (reassign_band ts b) = p b.

Lemma total_width_reassign :
  forall (T : Type) (ts : list T) (l : list (Slot T)),
    total_width (reassign ts l) = total_width l.
Proof.
  intros T ts. induction ts as [ | t tr IH ]; intros l.
  - reflexivity.
  - destruct l as [ | s sr ].
    + reflexivity.
    + simpl. rewrite IH. reflexivity.
Qed.

(* S6 (R-11-022, R-11-023): the focus majority is decided by widths, so a
   focus rebinding cannot change whether a band is focus-shaped. *)
Theorem focus_shape_is_occupancy_blind :
  forall c : Composition, BandOccupancyBlind c (FocusShaped c).
Proof.
  intros c ts b. unfold FocusShaped.
  rewrite band_slots_reassign. rewrite total_width_reassign.
  destruct ts; reflexivity.
Qed.

(* S6b (R-11-022): "one focus slot plus (n-1) background slots". *)
Theorem focus_band_is_one_focus_plus_the_rest :
  forall (T : Type) (b : Band T),
    count_of (band_slots b) = S (count_of (band_background b)).
Proof. intros T b. reflexivity. Qed.

(* -------------------------------------------------------------------------
   S7: R-11-025's rung index.
   ------------------------------------------------------------------------- *)

Record Population : Type := {
  live_count : nat;              (* R-11-025's "count of live discretionary
                                    tenants"                                *)
  utilization : nat;             (* what R-11-025 forbids the index to read *)
  queue_depth : nat              (* the same                                *)
}.

Definition rung_index (c : Composition) (p : Population) : nat :=
  c.(rung_of_count) (live_count p).

Definition CountOnly (c : Composition) (f : Population -> nat) : Prop :=
  forall p q : Population, live_count p = live_count q -> f p = f q.

(* S7 (R-11-025): the index moves on the live count and on nothing else. *)
Theorem rung_follows_the_live_count_alone :
  forall c : Composition, CountOnly c (rung_index c).
Proof.
  intros c p q H. unfold rung_index. rewrite H. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   S8: R-11-026's hard ceiling.
   ------------------------------------------------------------------------- *)

(* Exactly R-11-026's three arms: a slot granted below the ceiling, no slot
   at all past it, or a live tenant suspended to retained state to make
   room. This is a list of what an arrival meets and not an object
   inventory (gap c). *)
Inductive Outcome (T : Type) : Type :=
| Granted : Slot T -> Outcome T
| NoSlot : Outcome T
| Suspended : T -> Slot T -> Outcome T.

Definition outcome_slot {T : Type} (o : Outcome T) : option (Slot T) :=
  match o with
  | Granted _ s => Some s
  | NoSlot _ => None
  | Suspended _ _ s => Some s
  end.

Definition bump (p : Population) : Population :=
  Build_Population (S (live_count p)) (utilization p) (queue_depth p).

Definition Arrival (c : Composition) : Type :=
  Slot (Tenant c) -> Tenant c -> Population -> Population * Outcome (Tenant c).

(* The victim choice is a parameter: R-11-026 says the owning population
   manager suspends a live tenant and does not say which, so every theorem
   below quantifies over it. *)
Definition arrive (c : Composition)
                  (choose_victim : Population -> option (Tenant c))
  : Arrival c :=
  fun template t p =>
    if Nat.ltb (live_count p) c.(top_rung_capacity)
    then (bump p, Granted (Tenant c) (retenant_slot template t))
    else match choose_victim p with
         | Some v => (p, Suspended (Tenant c) v (retenant_slot template t))
         | None => (p, NoSlot (Tenant c))
         end.

Definition CeilingInvariant (c : Composition) (step : Arrival c) : Prop :=
  forall (template : Slot (Tenant c)) (t : Tenant c) (p : Population),
    Nat.leb (live_count p) c.(top_rung_capacity) = true ->
    Nat.leb (live_count (fst (step template t p))) c.(top_rung_capacity) = true.

Definition NoNarrowing (c : Composition) (step : Arrival c) : Prop :=
  forall (template : Slot (Tenant c)) (t : Tenant c) (p : Population)
         (s : Slot (Tenant c)),
    outcome_slot (snd (step template t p)) = Some s ->
    slot_width s = slot_width template.

(* S8 (R-11-026): the ceiling holds under every victim choice. *)
Theorem ceiling_is_an_invariant :
  forall (c : Composition) (choose_victim : Population -> option (Tenant c)),
    CeilingInvariant c (arrive c choose_victim).
Proof.
  intros c choose_victim template t p H. unfold arrive.
  destruct (Nat.ltb (live_count p) c.(top_rung_capacity)) eqn:E.
  - exact E.
  - destruct (choose_victim p); exact H.
Qed.

(* S8b (R-11-026): past the ceiling with no victim to suspend, the arrival
   receives no slot. *)
Theorem refusal_arm_grants_no_slot :
  forall (c : Composition) (choose_victim : Population -> option (Tenant c))
         (template : Slot (Tenant c)) (t : Tenant c) (p : Population),
    Nat.ltb (live_count p) c.(top_rung_capacity) = false ->
    choose_victim p = None ->
    outcome_slot (snd (arrive c choose_victim template t p)) = None.
Proof.
  intros c choose_victim template t p Hfull Hnone.
  unfold arrive. rewrite Hfull. rewrite Hnone. reflexivity.
Qed.

(* S8c (R-11-026): "no slot rather than a thinner one". No arm narrows a
   width, under every victim choice. *)
Theorem no_arm_narrows_a_slot :
  forall (c : Composition) (choose_victim : Population -> option (Tenant c)),
    NoNarrowing c (arrive c choose_victim).
Proof.
  intros c choose_victim template t p s H. unfold arrive in H.
  destruct (Nat.ltb (live_count p) c.(top_rung_capacity)).
  - simpl in H. injection H as H. rewrite <- H. reflexivity.
  - destruct (choose_victim p).
    + simpl in H. injection H as H. rewrite <- H. reflexivity.
    + simpl in H. discriminate H.
Qed.

(* S8d (R-11-026): "suspension keeps state and removes a slot; it is not
   termination". The suspension arm names the victim and leaves the
   population count where it was. *)
Theorem suspension_is_not_termination :
  forall (c : Composition) (choose_victim : Population -> option (Tenant c))
         (template : Slot (Tenant c)) (t : Tenant c) (p : Population)
         (v : Tenant c),
    Nat.ltb (live_count p) c.(top_rung_capacity) = false ->
    choose_victim p = Some v ->
    fst (arrive c choose_victim template t p) = p
    /\ snd (arrive c choose_victim template t p)
       = Suspended (Tenant c) v (retenant_slot template t).
Proof.
  intros c choose_victim template t p v Hfull Hvictim.
  unfold arrive. rewrite Hfull. rewrite Hvictim. split; reflexivity.
Qed.

(* -------------------------------------------------------------------------
   S9: R-07-033's slot as the temporal isolation, and R-07-036's
   non-work-conserving frame.
   ------------------------------------------------------------------------- *)

Fixpoint slot_index_at {T : Type} (l : list (Slot T)) (i t : nat) : option nat :=
  match l with
  | nil => None
  | cons s r =>
      if andb (Nat.leb (slot_offset s) t)
              (Nat.ltb t (slot_offset s + slot_width s))
      then Some i
      else slot_index_at r (S i) t
  end.

Definition GeometryOnly {T : Type}
    (mapf : list (Slot T) -> nat -> nat -> option nat) : Prop :=
  forall (l1 l2 : list (Slot T)) (i t : nat),
    SameGeometry l1 l2 -> mapf l1 i t = mapf l2 i t.

(* S9 (R-07-032, R-07-033, R-07-036): which slot owns an instant is a
   function of widths and offsets alone, so an idle slot yields nothing to
   another tenant and no slack crosses a boundary. *)
Theorem geometry_ignores_behaviour :
  forall T : Type, GeometryOnly (@slot_index_at T).
Proof.
  intros T l1 l2 i t H. revert i.
  induction H as [ | s u r1 r2 Hw Ho Hb Hp Hrest IH ]; intros i.
  - reflexivity.
  - simpl. rewrite Hw. rewrite Ho. rewrite IH. reflexivity.
Qed.

(* =========================================================================
   A composition whose every domain is inhabited, for R-05-165's
   uninhabited-domain mode and for the refutation witnesses. Its harmonic
   predicate, its focus majority, its ladder function, its capacity and its
   table load are arbitrary witness values and carry no composition claim
   (gap e); the harmonic predicate in particular is instantiated at the
   weakest one available, precisely so that the witness fixes no direction.
   ========================================================================= *)

Definition demo_composition : Composition := {|
  machine := demo_rotation_swaps;
  Tenant := bool;
  harmonic := fun _ _ => true;
  focus_majority := fun w total => Nat.leb total (w + w);
  rung_of_count := fun n => n;
  top_rung_capacity := 2;
  table_load_cost := 4
|}.

Definition reserved_slot : Slot bool := Build_Slot bool 60 0 40 100 true.
Definition focus_slot_a : Slot bool := Build_Slot bool 90 60 70 100 false.
Definition background_a : Slot bool := Build_Slot bool 50 150 30 100 true.

Definition focus_slot_b : Slot bool := Build_Slot bool 70 60 50 100 false.
Definition background_b1 : Slot bool := Build_Slot bool 35 130 15 100 true.
Definition background_b2 : Slot bool := Build_Slot bool 35 165 15 100 true.

Definition demo_reserved : list (Slot bool) := cons reserved_slot nil.

Definition band_a : Band bool :=
  Build_Band bool focus_slot_a (cons background_a nil).

Definition band_b : Band bool :=
  Build_Band bool focus_slot_b (cons background_b1 (cons background_b2 nil)).

Definition rung_a : Frame bool := Build_Frame bool 200 0 demo_reserved band_a.
Definition rung_b : Frame bool := Build_Frame bool 200 0 demo_reserved band_b.

Definition demo_ladder : Ladder bool :=
  Build_Ladder bool (cons rung_a (cons rung_b nil)).

(* The computed checks, in the silent form the gate requires: an Example
   proved by eq_refl is decided by the kernel and prints nothing, where a
   Compute or an Eval would print its answer and fail the run. *)

Example rung_a_admits : admits demo_composition rung_a = true := eq_refl.
Example rung_b_admits : admits demo_composition rung_b = true := eq_refl.
Example band_a_is_focus_shaped :
  FocusShaped demo_composition band_a = true := eq_refl.

(* A frame whose arithmetic does not close: the background slot overlaps
   the focus slot, and nothing else about it differs. *)
Definition overlapping_background : Slot bool := Build_Slot bool 50 140 30 100 true.

Definition overlapping_rung : Frame bool :=
  Build_Frame bool 200 0 demo_reserved
    (Build_Band bool focus_slot_a (cons overlapping_background nil)).

Example overlap_is_refused :
  admits demo_composition overlapping_rung = false := eq_refl.

(* A slot whose declared bound plus R-15-220's three terms exceeds its
   width, which is R-11-009's switch duty counted rather than absorbed. *)
Definition underwide_background : Slot bool := Build_Slot bool 50 150 40 100 true.

Definition underwide_rung : Frame bool :=
  Build_Frame bool 200 0 demo_reserved
    (Build_Band bool focus_slot_a (cons underwide_background nil)).

Example switch_duty_is_counted :
  admits demo_composition underwide_rung = false := eq_refl.

(* And the margin, which is where the constant is load-bearing rather than
   merely present: one slot's declared bound plus R-15-220's three terms
   exactly fills its width, and one unit more is refused. R-11-009 counts
   the switch-duty ratio explicitly instead of absorbing it into slack, so
   a change to PartitionContext.v's switch_cost changes this verdict, which
   is what makes the Require at the top of this file a dependency rather
   than a citation. *)
Definition tight_focus : Slot bool := Build_Slot bool 90 60 75 100 false.
Definition overtight_focus : Slot bool := Build_Slot bool 90 60 76 100 false.

Definition tight_rung : Frame bool :=
  Build_Frame bool 200 0 demo_reserved
    (Build_Band bool tight_focus (cons background_a nil)).

Definition overtight_rung : Frame bool :=
  Build_Frame bool 200 0 demo_reserved
    (Build_Band bool overtight_focus (cons background_a nil)).

Example one_unit_of_switch_duty_decides :
  admits demo_composition tight_rung = true
  /\ admits demo_composition overtight_rung = false :=
  conj eq_refl eq_refl.

(* The harmonic conjunct is live rather than dead code: the same frame is
   refused by a composition whose harmonic predicate refuses. This fixes no
   direction and says only that the clause decides something. *)
Definition refusing_harmonic : Composition := {|
  machine := demo_rotation_swaps;
  Tenant := bool;
  harmonic := fun _ _ => false;
  focus_majority := fun w total => Nat.leb total (w + w);
  rung_of_count := fun n => n;
  top_rung_capacity := 2;
  table_load_cost := 4
|}.

Example harmonic_conjunct_is_live :
  admits refusing_harmonic rung_a = false := eq_refl.

(* The ladder is well formed and admitted, so S3, S4 and S5 are not proved
   from premises nothing satisfies. *)

Theorem demo_ladder_all_share :
  AllShare 200 0 demo_reserved (ladder_rungs demo_ladder).
Proof. simpl. repeat split. Qed.

Theorem demo_ladder_is_well_formed : WellFormedLadder demo_ladder.
Proof.
  exists 200. exists 0. exists demo_reserved. exact demo_ladder_all_share.
Qed.

Theorem demo_ladder_admits : LadderAdmits demo_composition demo_ladder.
Proof.
  intros f Hin. simpl in Hin.
  destruct Hin as [ Heq | [ Heq | Hempty ] ].
  - rewrite <- Heq. exact rung_a_admits.
  - rewrite <- Heq. exact rung_b_admits.
  - destruct Hempty.
Qed.

(* S5's premises are satisfied by that ladder, so the table swap is proved
   of a ladder that exists rather than of an empty one. *)
Theorem demo_rung_change_is_a_table_swap :
  admits demo_composition rung_a = true
  /\ admits demo_composition rung_b = true
  /\ reserved_half demo_composition rung_a = reserved_half demo_composition rung_b
  /\ major_frame rung_a = major_frame rung_b
  /\ phase_offset rung_a = phase_offset rung_b.
Proof.
  apply (rung_change_is_a_table_swap demo_composition demo_ladder
           200 0 demo_reserved rung_a rung_b
           demo_ladder_all_share demo_ladder_admits).
  - simpl. left. reflexivity.
  - simpl. right. left. reflexivity.
Qed.

(* =========================================================================
   Refutation witnesses (R-05-166). Each is an alternative construction the
   register's own sentence excludes, so the theorems above exclude
   something rather than agreeing with this file's definitions.
   ========================================================================= *)

(* An admission check that reads a tenant. R-11-023's criterion is that the
   interval arithmetic quantifies over widths and offsets and never
   occupants, so this one is not the check. *)
Definition admits_occupancy_sensitive (c : Composition)
    (tenant_ok : Tenant c -> bool) (f : Frame (Tenant c)) : bool :=
  andb (admits c f)
       (all_of (fun s => tenant_ok (slot_tenant s)) (frame_slots f)).

Definition retenanted_rung_a : Frame bool :=
  reassign_frame (cons true nil) (cons true (cons true nil)) rung_a.

Theorem occupancy_sensitive_check_is_refuted :
  ~ OccupancyBlind demo_composition
      (admits_occupancy_sensitive demo_composition (fun t => t)).
Proof.
  intros Hblind.
  specialize (Hblind retenanted_rung_a rung_a eq_refl
                (frame_slots_reassign_same_geometry bool
                   (cons true nil) (cons true (cons true nil)) rung_a)).
  cbv in Hblind. discriminate Hblind.
Qed.

(* A ladder whose second rung carries a different reserved band. Its two
   rungs disagree on the reserved half of the verdict, so R-11-020's
   "identical across every rung" is what discharges that half once and not
   a property a ladder has for free. *)
Definition wide_reserved_slot : Slot bool := Build_Slot bool 260 0 40 100 true.

Definition mismatched_rung : Frame bool :=
  Build_Frame bool 200 0 (cons wide_reserved_slot nil) band_a.

Theorem reserved_band_must_be_identical :
  reserved_half demo_composition rung_a
  <> reserved_half demo_composition mismatched_rung.
Proof. intro H. cbv in H. discriminate H. Qed.

(* A focus-shape predicate that reads the focus slot's tenant. *)
Definition focus_shaped_by_tenant (c : Composition)
    (tenant_ok : Tenant c -> bool) (b : Band (Tenant c)) : bool :=
  andb (FocusShaped c b) (tenant_ok (slot_tenant (band_focus b))).

Theorem focus_shape_by_tenant_is_refuted :
  ~ BandOccupancyBlind demo_composition
      (focus_shaped_by_tenant demo_composition (fun t => t)).
Proof.
  intros Hblind.
  specialize (Hblind (cons true nil) band_a).
  cbv in Hblind. discriminate Hblind.
Qed.

(* A rung change costed one partition switch per slot of the rung entered,
   which R-11-024's "one partition-switch constant plus the table load"
   excludes. *)
Fixpoint switch_per_slot (c : Composition) (l : list (Slot (Tenant c))) : nat :=
  match l with
  | nil => 0
  | cons _ r => switch_cost c.(machine) + switch_per_slot c r
  end.

Definition per_slot_swap_cost (c : Composition) (b : Band (Tenant c)) : nat :=
  switch_per_slot c (band_slots b) + c.(table_load_cost).

Theorem per_slot_swap_cost_is_refuted :
  ~ SizeIndependent demo_composition (per_slot_swap_cost demo_composition).
Proof.
  intros Hsize. specialize (Hsize band_a band_b).
  cbv in Hsize. discriminate Hsize.
Qed.

(* A rung index that follows utilization, which R-11-025 excludes by name:
   the index moves "never on utilization, queue depth, or any
   compartment's computation". *)
Definition load_following_rung (c : Composition) (p : Population) : nat :=
  c.(rung_of_count) (utilization p).

Theorem load_following_rung_is_refuted :
  ~ CountOnly demo_composition (load_following_rung demo_composition).
Proof.
  intros Hcount.
  specialize (Hcount (Build_Population 0 0 0) (Build_Population 0 1 0) eq_refl).
  cbv in Hcount. discriminate Hcount.
Qed.

(* An arrival step that grants a narrower slot past the ceiling instead of
   refusing, which is exactly what R-11-026's "no slot rather than a
   thinner one" forbids. It refutes both the ceiling and the no-narrowing
   property, which is what makes S8 and S8c content. Any narrower width
   serves; zero is the concrete one. *)
Definition narrowed_slot {T : Type} (s : Slot T) (t : T) : Slot T :=
  Build_Slot T 0 (slot_offset s) (slot_bound s) (slot_period s) t.

Definition arrive_thinner (c : Composition) : Arrival c :=
  fun template t p =>
    if Nat.ltb (live_count p) c.(top_rung_capacity)
    then (bump p, Granted (Tenant c) (retenant_slot template t))
    else (bump p, Granted (Tenant c) (narrowed_slot template t)).

Theorem narrowing_step_refutes_the_ceiling :
  ~ CeilingInvariant demo_composition (arrive_thinner demo_composition).
Proof.
  intros Hinv.
  specialize (Hinv focus_slot_a true (Build_Population 2 0 0) eq_refl).
  cbv in Hinv. discriminate Hinv.
Qed.

Theorem narrowing_step_refutes_no_narrowing :
  ~ NoNarrowing demo_composition (arrive_thinner demo_composition).
Proof.
  intros Hno.
  specialize (Hno focus_slot_a true (Build_Population 2 0 0)
                  (narrowed_slot focus_slot_a true) eq_refl).
  cbv in Hno. discriminate Hno.
Qed.

(* A work-conserving time-to-slot map: it passes an idle slot's time to the
   next tenant. R-07-036 makes the schedule non-work-conserving across
   confidentiality boundaries, so no slack ever crosses one, and this map
   is the construction that entry excludes. *)
Fixpoint slot_index_at_work_conserving {T : Type} (idle : T -> bool)
    (l : list (Slot T)) (i t : nat) : option nat :=
  match l with
  | nil => None
  | cons s r =>
      if andb (andb (Nat.leb (slot_offset s) t)
                    (Nat.ltb t (slot_offset s + slot_width s)))
              (negb (idle (slot_tenant s)))
      then Some i
      else slot_index_at_work_conserving idle r (S i) t
  end.

Definition busy_slot : Slot bool := Build_Slot bool 10 0 0 100 false.
Definition idle_slot : Slot bool := Build_Slot bool 10 0 0 100 true.

Theorem work_conserving_map_is_refuted :
  ~ GeometryOnly (slot_index_at_work_conserving (fun t : bool => t)).
Proof.
  intros Hgeo.
  assert (Hsame : SameGeometry (cons busy_slot nil) (cons idle_slot nil)).
  { apply SG_cons; try reflexivity. apply SG_nil. }
  specialize (Hgeo (cons busy_slot nil) (cons idle_slot nil) 0 0 Hsame).
  cbv in Hgeo. discriminate Hgeo.
Qed.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, as in the two artifacts beside this one.
   ------------------------------------------------------------------------- *)

Print Assumptions admits.
Print Assumptions reserved_half.
Print Assumptions rung_index.
Print Assumptions arrive.
Print Assumptions slot_index_at.
Print Assumptions rung_change_cost.
Print Assumptions FocusShaped.
Print Assumptions same_geometry_refl.
Print Assumptions same_geometry_app.
Print Assumptions reassign_same_geometry.
Print Assumptions band_slots_reassign_same_geometry.
Print Assumptions frame_slots_reassign_same_geometry.
Print Assumptions admission_is_occupancy_blind.
Print Assumptions admission_survives_every_retenanting.
Print Assumptions all_share_member.
Print Assumptions reserved_band_discharged_once.
Print Assumptions one_frame_length_across_rungs.
Print Assumptions rung_change_is_a_table_swap.
Print Assumptions rung_change_cost_is_one_switch.
Print Assumptions focus_shape_is_occupancy_blind.
Print Assumptions focus_band_is_one_focus_plus_the_rest.
Print Assumptions rung_follows_the_live_count_alone.
Print Assumptions ceiling_is_an_invariant.
Print Assumptions refusal_arm_grants_no_slot.
Print Assumptions no_arm_narrows_a_slot.
Print Assumptions suspension_is_not_termination.
Print Assumptions geometry_ignores_behaviour.
Print Assumptions rung_a_admits.
Print Assumptions rung_b_admits.
Print Assumptions band_a_is_focus_shaped.
Print Assumptions overlap_is_refused.
Print Assumptions switch_duty_is_counted.
Print Assumptions one_unit_of_switch_duty_decides.
Print Assumptions harmonic_conjunct_is_live.
Print Assumptions demo_ladder_all_share.
Print Assumptions demo_ladder_is_well_formed.
Print Assumptions demo_ladder_admits.
Print Assumptions demo_rung_change_is_a_table_swap.
Print Assumptions reserved_band_must_be_identical.
Print Assumptions occupancy_sensitive_check_is_refuted.
Print Assumptions focus_shape_by_tenant_is_refuted.
Print Assumptions per_slot_swap_cost_is_refuted.
Print Assumptions load_following_rung_is_refuted.
Print Assumptions narrowing_step_refutes_the_ceiling.
Print Assumptions narrowing_step_refutes_no_narrowing.
Print Assumptions work_conserving_map_is_refuted.
