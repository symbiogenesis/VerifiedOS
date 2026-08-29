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

   The properties are the computable shadows of three theorems
   CyclicExecutive.v proves, and that is the point of stating them here rather
   than only there. A theorem is about every frame and holds by construction;
   a property is about the frames a generator produces and holds by
   computation. Where the two agree the generator is exercising the algebra
   the theorem is about, and where they disagree one of them is wrong about
   the definitions underneath both, which is the differential the Wasm oracle
   was built to make and has never had an input side for.
   ========================================================================= *)

From QuickChick Require Import QuickChick.
From Stdlib Require Import List String.
Require Import PartitionContext.
Require Import CyclicExecutive.
Require Import Probe.

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
