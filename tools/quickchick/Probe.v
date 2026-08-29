(* SPDX-License-Identifier: Apache-2.0 *)

(* =========================================================================
   The composition both halves of the Gallina front are exercised over.

   It is here rather than in either harness because both of them need it and
   two copies of one fact is the defect this repository is built to catch:
   Vectors.v enumerates a domain over it and Properties.v draws from one, and
   a probe that differed between the two would make the two halves answer
   different questions while reading as one instrument.

   Its harmonic predicate is a real one and not the constant witness
   demo_composition carries. A constant-true conjunct is a conjunct no vector
   and no draw can tell from its absence, which is the dead-arm shape M0.16
   found in a validator and R1a measured again inside setCapBounds; a probe
   built on one would report a clause held that nothing holds.

   Nothing here is a claim about a real composition. R-11-006 says "harmonic"
   and not in which direction, which CyclicExecutive.v's own gap (e) records,
   so the divisibility below is a witness that fixes a direction for the
   purpose of exercising the clause and for no other purpose.
   ========================================================================= *)

Require Import PartitionContext.
Require Import CyclicExecutive.

Definition probe_harmonic (period major : nat) : bool :=
  Nat.eqb (Nat.modulo major period) 0.

Definition probe_composition : Composition := {|
  machine := demo_rotation_swaps;
  Tenant := bool;
  harmonic := probe_harmonic;
  focus_majority := fun w total => Nat.leb total (w + w);
  rung_of_count := fun n => n;
  top_rung_capacity := 2;
  table_load_cost := 4
|}.

(* The frame shape both halves build: one reserved slot, one focus, one
   background. It is the smallest shape in which every conjunct of `admits`
   can decide something, the reserved band being non-empty, the band carrying
   a focus and a background so `pairwise_disjoint` has a pair to look at, and
   the three slots giving `total_width` three terms. *)
Definition probe_frame (mf : nat) (r f b : Slot bool) : Frame bool :=
  Build_Frame bool mf 0 (cons r nil)
    (Build_Band bool f (cons b nil)).
