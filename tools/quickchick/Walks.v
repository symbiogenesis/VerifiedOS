(* SPDX-License-Identifier: Apache-2.0 *)

(* =========================================================================
   The walk harness: the randomized side's property sets whose domain holds
   no more points than the draws QuickChick would spend on it, each decided
   at every point of that domain instead.

   QuickChick spends 10,000 draws on a property set. A domain of no more
   points than that is one a draw of that size samples without covering,
   repeating some points and missing others, so each set over such a domain
   is walked here rather than drawn in Properties.v: every point the drawn
   generator could produce is enumerated and the property is computed at
   each. The statements are IPCProperties.v's, which Properties.v reads too.

   It loads Stdlib alone and is compiled by tools/vos/gallina.py in
   QuickChick's switch beside Properties.v, by `run.py quickchick
   properties` and for every mutant of `run.py seed coq --quickchick`. It
   ends in a `Compute` over a `list string`, one entry per set:

     name points premise refuted first

   `points` is the domain's size, `premise` how many points meet the set's
   premise, every point for an unguarded property, `refuted` how many points
   the property is false at, and `first` the position of the first such
   point in the walk's order, `-` where none is. A run fails a set any point
   refutes, a domain holding no point, and a premise no point meets, the
   last being a property that holds vacuously.

   **Each domain is the drawn generator's, choice for choice.** `choose (a,
   b)` is every nat from a to b, `elems_ d l` every member of l, and
   `vectorOf n g` every list of length n over g's points; a generator that
   binds several of these is their product, in the order it binds them.
   What that gives each set, which the run prints back as `points`:

     prop_badge_space_is_two_to_the_width                    9
       choose (0, 8)
     prop_a_transposition_does_not_move_the_verdict,
       permuted surface                                    392
       choose (0, 7), then genPermutedSurface's two choose (0, 6)
     prop_an_insertion_adds_exactly_one_occurrence       1,960
       choose (0, 7), the five invocations, genPermutedSurface's 49
     prop_only_the_full_mask_is_the_surface                256
       choose (0, 255)
     prop_lifecycles_split_tables_from_objects              18
       the six nameables, the three lifecycles
     prop_no_non_object_survives_the_inventory           9,331
       lists of length 0 to 5 over the six nameables
     prop_dispatch_ignores_the_observation                 729
       choose (0, 8) three times
     prop_the_queue_dispatch_agrees_where_the_memory_does  729
       choose (0, 8) three times
     prop_the_decider_never_yields_over_work             2,401
       two rings, each choose (0, 6) twice
     prop_the_naive_decider_differs_exactly_at_the_lost_wakeup
                                                         2,401
       two rings, each choose (0, 6) twice
     prop_the_numberings_split_on_one_clause_each           85
       the five invocations, the seventeen acts
     prop_the_trap_surfaces_differ_only_where_the_gap_is    17
       the seventeen acts
   ========================================================================= *)

From Stdlib Require Import String List Ascii.
Require EndpointIPC.
Require Import IPCProbe.
Require Import IPCProperties.

Import ListNotations.
Open Scope string_scope.

(* The printed list is one logical line and the reader of it is a text
   comparison, so it must not be wrapped at a terminal width. *)
Set Printing Width 100000.

(* -------------------------------------------------------------------------
   Rendering, as Vectors.v renders a nat. Restated rather than shared:
   Vectors.v is an entry point, and Requiring it would run its walk.
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

(* -------------------------------------------------------------------------
   The domains, one constructor per generator shape.
   ------------------------------------------------------------------------- *)

(* `choose (a, b)`: every nat from a to b, both included. *)
Definition chosen (a b : nat) : list nat := seq a (S b - a).

(* `vectorOf n g`: every list of length n over the points of g. *)
Fixpoint vectors_of {A : Type} (n : nat) (points : list A) : list (list A) :=
  match n with
  | 0 => [nil]
  | S k => flat_map (fun x => map (cons x) (vectors_of k points)) points
  end.

(* `bindGen (choose (0, k)) (fun n => vectorOf n g)`: every list of length 0
   to k over the points of g. *)
Definition lists_upto {A : Type} (k : nat) (points : list A) : list (list A) :=
  flat_map (fun n => vectors_of n points) (chosen 0 k).

(* Properties.v's `genRing`: a produced and a consumed index, each choose
   (0, 6). *)
Definition rings : list EndpointIPC.Ring :=
  flat_map (fun p => map (fun c => ipc_ring p c) (chosen 0 6)) (chosen 0 6).

(* Properties.v's `genPermutedSurface`: the specification's own sequence
   with two transpositions applied, at each choose (0, 6). *)
Definition permuted_surfaces : list (list EndpointIPC.Invocation) :=
  flat_map (fun a =>
              map (fun b => EndpointIPC.swap_at_inv a
                              (EndpointIPC.swap_at_inv b EndpointIPC.spec_surface))
                  (chosen 0 6))
           (chosen 0 6).

(* -------------------------------------------------------------------------
   The walk.
   ------------------------------------------------------------------------- *)

Fixpoint first_false {A : Type} (p : A -> bool) (here : nat) (xs : list A)
  : option nat :=
  match xs with
  | nil => None
  | cons x rest => if p x then first_false p (S here) rest else Some here
  end.

Definition count_true {A : Type} (p : A -> bool) (xs : list A) : nat :=
  EndpointIPC.count_of (EndpointIPC.filter_of p xs).

Definition always {A : Type} (_ : A) : bool := true.

Definition walk {A : Type} (name : string) (domain : list A)
                (premise property : A -> bool) : string :=
  name ++ " " ++ ns (EndpointIPC.count_of domain)
  ++ " " ++ ns (count_true premise domain)
  ++ " " ++ ns (count_true (fun x => negb (property x)) domain)
  ++ " " ++ (match first_false property 0 domain with
             | None => "-"
             | Some at_point => ns at_point
             end).

Definition walked : list string := [
  walk "prop_badge_space_is_two_to_the_width"
       (chosen 0 8) always prop_badge_space_is_two_to_the_width;
  walk "prop_a_transposition_does_not_move_the_verdict, permuted surface"
       (list_prod (chosen 0 7) permuted_surfaces) always
       (fun '(n, l) => prop_a_transposition_does_not_move_the_verdict n l);
  walk "prop_an_insertion_adds_exactly_one_occurrence"
       (list_prod (list_prod (chosen 0 7) EndpointIPC.all_invocations)
                  permuted_surfaces) always
       (fun '(n, i, l) => prop_an_insertion_adds_exactly_one_occurrence n i l);
  walk "prop_only_the_full_mask_is_the_surface"
       (chosen 0 255) always prop_only_the_full_mask_is_the_surface;
  walk "prop_lifecycles_split_tables_from_objects"
       (list_prod EndpointIPC.all_nameable EndpointIPC.all_lifecycles)
       (fun '(c, op) => premise_lifecycles_split_tables_from_objects c op)
       (fun '(c, op) => prop_lifecycles_split_tables_from_objects c op);
  walk "prop_no_non_object_survives_the_inventory"
       (lists_upto 5 EndpointIPC.all_nameable)
       premise_no_non_object_survives_the_inventory
       prop_no_non_object_survives_the_inventory;
  walk "prop_dispatch_ignores_the_observation"
       (list_prod (list_prod (chosen 0 8) (chosen 0 8)) (chosen 0 8)) always
       (fun '(n, a, b) => prop_dispatch_ignores_the_observation n a b);
  walk "prop_the_queue_dispatch_agrees_where_the_memory_does"
       (list_prod (list_prod (chosen 0 8) (chosen 0 8)) (chosen 0 8))
       (fun '(n, a, b) => premise_the_queue_dispatch_agrees_where_the_memory_does n a b)
       (fun '(n, a, b) => prop_the_queue_dispatch_agrees_where_the_memory_does n a b);
  walk "prop_the_decider_never_yields_over_work"
       (list_prod rings rings)
       (fun '(before, now) => premise_the_decider_never_yields_over_work before now)
       (fun '(before, now) => prop_the_decider_never_yields_over_work before now);
  walk "prop_the_naive_decider_differs_exactly_at_the_lost_wakeup"
       (list_prod rings rings) always
       (fun '(before, now) =>
          prop_the_naive_decider_differs_exactly_at_the_lost_wakeup before now);
  walk "prop_the_numberings_split_on_one_clause_each"
       (list_prod EndpointIPC.all_invocations EndpointIPC.all_acts)
       (fun '(i, a) => premise_the_numberings_split_on_one_clause_each i a)
       (fun '(i, a) => prop_the_numberings_split_on_one_clause_each i a);
  walk "prop_the_trap_surfaces_differ_only_where_the_gap_is"
       EndpointIPC.all_acts always prop_the_trap_surfaces_differ_only_where_the_gap_is
].

Compute walked.
