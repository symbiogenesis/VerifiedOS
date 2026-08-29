(* SPDX-License-Identifier: Apache-2.0 *)

(* =========================================================================
   The Gallina front's generated inputs, as vectors.

   The Wasm oracle (tools/wasm-oracle/, M1.5) runs Gallina components on a
   stock engine and nothing generates their inputs, so what it exercises is
   whatever a person thought to write down. This file is the input side, in
   the shape both earlier model-as-oracle rigs took: a domain is walked, the
   definitions under test are called at every point of it, and one line of
   text per point is printed. The vectors cross as text, so the Wasm side and
   this side are not compiled against each other's types and a disagreement
   names a line a person reads on both sides.

   Its subject is CyclicExecutive.v's admission algebra, which is the whole of
   what R-11-006's interval arithmetic and R-11-009's switch duty decide about
   a frame. Every definition it calls is decidable and computes, which is what
   makes a vector out of a proof artifact at all.

   Two things it is deliberately not. It is not a proof: nothing here is
   Required by anything in proofs/, and the proof gate never compiles it, so
   no constant here reaches R-05-163's assumption enumeration. And it is not
   the QuickChick harness: Properties.v beside this file is that, and it needs
   an install this repository has not made. What this supplies without that
   install is the enumerative half, and what the install adds is random
   generation and counterexample shrinking.

   It is compiled by tools/quickchick.py in the CertiRocq oracle's own switch,
   which is where the standard library is; the shipped proofs use the prelude
   alone and are compiled in the proof gate's switch, which carries no library
   at all.
   ========================================================================= *)

From Stdlib Require Import String List Ascii.
Require Import PartitionContext.
Require Import CyclicExecutive.
Require Import Probe.

Import ListNotations.
Open Scope string_scope.

(* The printed list is one logical line and the reader of it is a text
   comparison, so it must not be wrapped at a terminal width. *)
Set Printing Width 100000.

(* -------------------------------------------------------------------------
   Rendering. A vector is text, so a nat has to become digits; the fuel is
   what makes the recursion structural, twenty digits being past any nat this
   file computes.
   ------------------------------------------------------------------------- *)

Definition digit_char (n : nat) : ascii := ascii_of_nat (48 + n).

Fixpoint nat_str (fuel n : nat) : string :=
  match fuel with
  | 0 => "?"
  | S f =>
      if Nat.ltb n 10
      then String (digit_char n) EmptyString
      else append (nat_str f (Nat.div n 10))
                  (String (digit_char (Nat.modulo n 10)) EmptyString)
  end.

Definition ns (n : nat) : string := nat_str 20 n.

Definition bs (b : bool) : string := if b then "1" else "0".

(* `slot_index_at` answers which slot owns an instant, and `None` where none
   does: R-07-036's non-work-conserving frame is exactly the instants that
   answer nothing, so the absence is a value the vector carries rather than a
   case it skips. *)
Definition os (o : option nat) : string :=
  match o with
  | None => "n"
  | Some n => ns n
  end.

(* -------------------------------------------------------------------------
   The domain. Four declared quantities per slot, three slots per frame, and
   two major-frame lengths: the grids below are named rather than drawn,
   because a slot's interesting values are its own boundaries and R1a's
   measurement is that a population off entropy alone misses exactly those.
   Each grid carries the value that fits, the value one unit past it, an
   overlap, a period that divides the major frame and one that does not.
   ------------------------------------------------------------------------- *)

Definition quad : Type := (nat * nat * nat * nat)%type.

Definition slot_of (q : quad) : Slot bool :=
  match q with
  | (w, o, b, p) => Build_Slot bool w o b p true
  end.

Definition q4 (q : quad) : string :=
  match q with
  | (w, o, b, p) => ns w ++ " " ++ ns o ++ " " ++ ns b ++ " " ++ ns p
  end.

Definition majors : list nat := [100; 200].

Definition reserved_grid : list quad :=
  [ (60, 0, 40, 100)
  ; (60, 0, 45, 100)
  ; (60, 0, 46, 100)
  ; (40, 0, 20, 50)
  ; (60, 10, 40, 100)
  ; (0, 0, 0, 100)
  ; (200, 0, 180, 200)
  ; (60, 0, 40, 7)
  ].

Definition focus_grid : list quad :=
  [ (90, 60, 70, 100)
  ; (90, 60, 75, 100)
  ; (90, 60, 76, 100)
  ; (70, 60, 50, 100)
  ; (90, 55, 70, 100)
  ; (140, 60, 120, 200)
  ; (90, 60, 70, 3)
  ; (30, 60, 10, 100)
  ].

(* The last row is here because a mutant survived without it, which is the
   measurement R1a made about its own sweep and this is the same one a lane
   over: `disjoint` is a disjunction of two `Nat.leb`s and every other row puts
   the background *after* the focus, so only the first disjunct was ever
   decided at equality and turning the second one strict changed no vector.
   This row ends exactly where a 60-offset focus begins and clears the
   40-wide reserved slot, which is what makes the second disjunct decide. *)
Definition background_grid : list quad :=
  [ (50, 150, 30, 100)
  ; (50, 140, 30, 100)
  ; (35, 130, 15, 100)
  ; (35, 165, 15, 100)
  ; (50, 150, 40, 100)
  ; (60, 150, 45, 50)
  ; (10, 190, 0, 100)
  ; (50, 150, 30, 9)
  ; (15, 45, 0, 100)
  ].

Definition frame_of (mf : nat) (r f b : quad) : Frame bool :=
  probe_frame mf (slot_of r) (slot_of f) (slot_of b).

(* -------------------------------------------------------------------------
   One vector. Every clause of the admission verdict is printed beside the
   verdict itself, so a defect in one conjunct is a line that differs in the
   field naming that conjunct rather than only in the answer.
   ------------------------------------------------------------------------- *)

Definition line_of (mf : nat) (r f b : quad) : string :=
  let fr := frame_of mf r f b in
  "ce " ++ ns mf ++ " " ++ q4 r ++ " " ++ q4 f ++ " " ++ q4 b ++ " ->"
    ++ " " ++ bs (admits probe_composition fr)
    ++ " " ++ bs (reserved_half probe_composition fr)
    ++ " " ++ bs (all_of (slot_fits probe_composition (major_frame fr))
                         (frame_slots fr))
    ++ " " ++ bs (pairwise_disjoint (frame_slots fr))
    ++ " " ++ ns (total_width (frame_slots fr))
    ++ " " ++ bs (FocusShaped probe_composition (discretionary_band fr))
    ++ " " ++ ns (count_of (frame_slots fr))
    ++ " " ++ ns (rung_change_cost probe_composition (discretionary_band fr))
    ++ " " ++ os (slot_index_at (frame_slots fr) 0 0)
    ++ " " ++ os (slot_index_at (frame_slots fr) 0 60)
    ++ " " ++ os (slot_index_at (frame_slots fr) 0 155)
    ++ " " ++ os (slot_index_at (frame_slots fr) 0 199).

Definition report : list string :=
  flat_map (fun mf =>
    flat_map (fun r =>
      flat_map (fun f =>
        map (fun b => line_of mf r f b) background_grid)
        focus_grid)
      reserved_grid)
    majors.

Compute report.
