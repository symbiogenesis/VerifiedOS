(* SPDX-License-Identifier: Apache-2.0 *)

(* =========================================================================
   The freeze's density arithmetic, as vectors.

   R-15-036i makes the instruction dictionary a permanent freeze-time
   commitment: every stored executable object is in that encoding, so a later
   change invalidates stored code wholesale rather than costing a recompile.
   That makes this the one arithmetic in the tree whose wrong answer cannot be
   repaired downstream, and it is stated twice on purpose. This file is the
   second statement. tools/vos/freezemodel.py is the first, and
   `run.py quickchick freeze` runs this one and holds the two against each
   other and against the four figures R-15-036h and R-15-036j quote in the
   register's own prose.

   **What it states.** R-15-036h's slot model, (w + h/k)(2 - p) bits per
   instruction; R-15-036j's packing term, (w + h/k)(2 - p + L) with L bounded
   above by (2 - p)/(k - 1); R-15-036's acceptance bar as the product of its
   two operands rather than as the figure 22.4; the three constraints that
   derive the slot width instead of sweeping it; the geometry candidates
   scored against that bar; and R-15-036p's outlining break-even.

   **What it does NOT decide, and the list is the point.**

   - It decides nothing about the *measurement*. p is a measured input
     (R-15-036i) and the corpus it would be measured over does not exist yet,
     so every figure below is the shape a candidate must satisfy whatever the
     observation turns out to be, and none of them is evidence about an image.
   - It decides nothing about which geometries the freeze weighs. The
     candidate set is the freeze measurement contract's §8 to declare and rule
     K-77's to hold; the grid below is this comparison's own domain, chosen
     wider than that set so that a column which is constant down a family is
     visible as one.
   - It decides nothing about lambda's *realized* value. Only the bound is
     stated here, because the bound is arithmetic over (p, k) and the realized
     term is a property of a greedy packing over a stream nothing has emitted.
     A row printing the model at L = its own bound is the worst case and never
     a prediction; at p = 1 the bound is 1/(k - 1) while the true term is 0,
     so that row is loose there by construction.
   - It is not a proof. Nothing here is Required by anything in proofs/, the
     proof gate never compiles it, and no constant here reaches R-05-163's
     assumption enumeration.

   **Why Z and not nat.** Rocq's nat is unary, and the intermediate a
   fixed-point rendering forms is 2 * num * scale: for the bare model at the
   256-bit bundle that is above 10^8, which is 10^8 constructors to allocate
   and a division that walks them. Z is binary and the same expression is a
   handful of machine words. The rendering is still exact fixed point rather
   than QArith: every figure crosses as an integer at a declared scale, so the
   comparison against the Python is an integer equality and never a float
   epsilon, and Z buys the sign the required packing term needs.

   **Why it renders its own digits rather than sharing Vectors.v's.** The two
   harnesses Require nothing of each other, so a defect seeded in one file's
   renderer cannot move the other file's answer; a shared renderer would make
   every vector in this tree one artifact.

   It is compiled by tools/vos/gallina.py in the CertiRocq oracle's own
   switch, which is where the standard library is; the shipped proofs use the
   prelude alone and are compiled in the proof gate's switch, which carries no
   library at all.
   ========================================================================= *)

From Stdlib Require Import String List Ascii ZArith.

Import ListNotations.

(* Z_scope first and string_scope over it: `++` and a quoted literal are then
   the string's, and every bare numeral falls through to Z, which is what every
   arithmetic definition below is written in. A nat is wanted at exactly two
   places, the digit fuel and the ascii offset, and both say `%nat`. *)
Open Scope Z_scope.
Open Scope string_scope.

(* The printed list is one logical line and the reader of it is a text
   comparison, so it must not be wrapped at a terminal width. *)
Set Printing Width 100000.

(* -------------------------------------------------------------------------
   Rendering. A vector is text, so an integer has to become digits; the fuel
   is what makes the recursion structural, twenty digits being past any
   magnitude this file computes.
   ------------------------------------------------------------------------- *)

Definition digit_char (n : nat) : ascii := ascii_of_nat (48 + n)%nat.

Fixpoint z_digits (fuel : nat) (n : Z) : string :=
  match fuel with
  | O => "?"
  | S f =>
      if Z.ltb n 10
      then String (digit_char (Z.to_nat n)) EmptyString
      else append (z_digits f (Z.div n 10))
                  (String (digit_char (Z.to_nat (Z.modulo n 10))) EmptyString)
  end.

(* The sign is a character and not a magnitude, so a value that rounds to zero
   from below prints `0` and never `-0`: Z has one zero and the Python's
   integers have one too, and a rendering that invented a second would make the
   two disagree about a point on which they agree. *)
Definition zs (n : Z) : string :=
  if Z.ltb n 0
  then append "-" (z_digits 20%nat (Z.opp n))
  else z_digits 20%nat n.

Definition bs (b : bool) : string := if b then "1" else "0".

(* `never pays` is a result and not a missing figure, so the absence is a value
   the vector carries rather than a row it skips. *)
Definition os (o : option Z) : string :=
  match o with
  | None => "n"
  | Some n => zs n
  end.

(* -------------------------------------------------------------------------
   The scales. Every figure below crosses as an integer at one of these, and
   the rounding rule is stated once: floor(value * scale + 1/2), which is one
   flooring division and so is one rule rather than a rule per sign.
   ------------------------------------------------------------------------- *)

Definition p_scale : Z := 1000.        (* a hit rate, in thousandths *)
Definition bits_scale : Z := 100.      (* a bits-per-instruction figure *)
Definition rate_scale : Z := 10000.    (* a probability or a packing term *)
Definition coeff_scale : Z := 10.      (* the linear form's coefficients *)

(* num/den at `scale`, rounded to the nearest with a half rounded up. `Z.div`
   is floor division for a positive divisor, and every `den` handed here is
   positive. The value alone decides the answer, so this fraction may be
   unreduced where the Python's `Fraction` is not and the two still agree. *)
Definition scaled (num den scale : Z) : Z :=
  Z.div (2 * num * scale + den) (2 * den).

(* -------------------------------------------------------------------------
   R-15-036's bar, derived from its two operands rather than stated as 22.4:
   the `C` counterfactual's share of a canonical stream. In hundredths of a
   bit, which is what a whole-percent share of a whole-bit stream already is.
   ------------------------------------------------------------------------- *)

Definition canonical_bits : Z := 32.
Definition optimistic_share : Z := 70.
Definition pessimistic_share : Z := 75.
Definition dictionary_index_bound : Z := 16.
Definition escape_pair_width : Z := Z.div canonical_bits 2.

Definition optimistic_bar : Z := optimistic_share * canonical_bits.
Definition pessimistic_bar : Z := pessimistic_share * canonical_bits.

(* The three constraints that derive w rather than sweeping it: an escape is
   two slots holding one canonical instruction verbatim; a wider slot wastes
   escape bits and buys index space the profile has no use for; and a slot must
   index a dictionary bounded at 2^16 entries. *)
Definition swd_escape (w : Z) : bool := Z.leb canonical_bits (2 * w).
Definition swd_waste (w : Z) : bool := Z.leb w escape_pair_width.
Definition swd_index (w : Z) : bool := Z.leb dictionary_index_bound w.

(* -------------------------------------------------------------------------
   The model. R-15-036h charges an instruction for the slots it occupies, one
   on a hit and two on a miss, so w + h/k per slot and (w + h/k)(2 - p) per
   instruction; w + h/k is the bundle width over the slot count, which is what
   lets every figure below be one exact fraction rather than a sum of two.
   ------------------------------------------------------------------------- *)

Definition bundle_of (w h k : Z) : Z := h + w * k.

Definition bare_bits (w h k pm : Z) : Z :=
  scaled (bundle_of w h k * (2 * p_scale - pm)) (p_scale * k) bits_scale.

(* R-15-036j's bound on the packing term, (2 - p)/(k - 1), as its own unreduced
   fraction: the register states it as 1/3 at p = 0 and k = 7, and a cross
   multiplication decides that exactly where a rounded figure would not. *)
Definition bound_num (pm : Z) : Z := 2 * p_scale - pm.
Definition bound_den (k : Z) : Z := p_scale * (k - 1).

(* R-15-036j's corrected model at a stated packing term ln/ld. *)
Definition packed_bits (w h k pm ln ld : Z) : Z :=
  scaled (bundle_of w h k * ((2 * p_scale - pm) * ld + p_scale * ln))
         (p_scale * k * ld) bits_scale.

(* The packing term a geometry may realize and still sit on the bar at this hit
   rate: bar/(w + h/k) - (2 - p). Negative is a result, and the strongest one
   this arithmetic produces: no packing at all clears the bar there, so no
   measurement can rescue the candidate. *)
Definition required_num (w h k pm : Z) : Z :=
  optimistic_bar * k * 10 - (2 * p_scale - pm) * bundle_of w h k.
Definition required_den (w h k : Z) : Z := p_scale * bundle_of w h k.

(* The hit rate the geometry needs with the packing at its own bound, and with
   no packing loss at all: 2 - bar(k - 1)/(w*k + h) and 2 - bar*k/(w*k + h). *)
Definition min_p_at_bound_num (w h k : Z) : Z :=
  200 * bundle_of w h k - optimistic_bar * (k - 1).
Definition min_p_unpacked_num (w h k : Z) : Z :=
  200 * bundle_of w h k - optimistic_bar * k.
Definition min_p_den (w h k : Z) : Z := 100 * bundle_of w h k.

(* Whether the geometry clears the bar at this hit rate for every packing term
   its own bound admits, and whether it fails at every one. Cross multiplied
   against the bound rather than compared through two rounded figures. *)
Definition clears (w h k pm : Z) : bool :=
  Z.leb (bound_num pm * required_den w h k)
        (required_num w h k pm * bound_den k).

Definition infeasible (w h k pm : Z) : bool :=
  Z.ltb (required_num w h k pm) 0.

(* FD-2's structural constraint: the header carries one escape-start bit per
   slot, so a candidate below h >= k is not a narrower search, it is a bundle
   whose header cannot say where its escapes begin. *)
Definition legal (h k : Z) : bool := Z.leb k h.

(* R-15-036p: a region of n instructions at m site-invariant sites costs nm
   slots inline, n + m + 1 outlined under a composition-time absolute call
   whose one target is one shared dictionary entry, and n + 2m + 1 under a
   PC-relative one whose per-site displacement is a site-varying two-slot
   escape. So nm > n + m + 1 iff m(n - 1) > n + 1, and nm > n + 2m + 1 iff
   m(n - 2) > n + 1. *)
Definition obe_absolute (n : Z) : option Z :=
  if Z.ltb 1 n then Some (Z.div (n + 1) (n - 1) + 1) else None.
Definition obe_pcrelative (n : Z) : option Z :=
  if Z.ltb 2 n then Some (Z.div (n + 1) (n - 2) + 1) else None.

(* -------------------------------------------------------------------------
   The domain. The reference instantiation R-15-036h names is (16, 16, 7); the
   grids around it are this comparison's own and are wider than the freeze
   measurement contract's declared candidate set on purpose. Each carries the
   value the format fixes, one either side of a constraint's boundary, and at
   least one member on which a column answers the other way: a slot width the
   escape rule refuses, a header narrower than its slot count, a hit rate below
   the break-even and one above it, and the p = 0 endpoint the register quotes.
   ------------------------------------------------------------------------- *)

Definition slot_width : Z := 16.
Definition ref_header : Z := 16.
Definition ref_slots : Z := 7.

Definition slot_widths : list Z := [8; 12; 16; 17; 20; 32].
Definition headers : list Z := [8; 16; 32].
Definition slot_counts : list Z := [2; 3; 4; 7; 8; 15; 16].
Definition hit_rates : list Z :=
  [0; 500; 728; 775; 800; 804; 850; 900; 950; 1000].
Definition geometry_rates : list Z := [0; 804; 950].
Definition region_lengths : list Z := [1; 2; 3; 4; 5; 6; 7; 8].

(* -------------------------------------------------------------------------
   One vector per point. Every operand of a verdict is printed beside the
   verdict, so a defect in one term is a line that differs in the field naming
   that term rather than only in the answer.
   ------------------------------------------------------------------------- *)

Definition bar_line : string :=
  "fm bar ->"
    ++ " " ++ zs canonical_bits
    ++ " " ++ zs optimistic_share
    ++ " " ++ zs pessimistic_share
    ++ " " ++ zs optimistic_bar
    ++ " " ++ zs pessimistic_bar.

Definition swd_line (w : Z) : string :=
  "fm swd " ++ zs w ++ " ->"
    ++ " " ++ bs (swd_escape w)
    ++ " " ++ bs (swd_waste w)
    ++ " " ++ bs (swd_index w)
    ++ " " ++ bs (andb (swd_escape w) (andb (swd_waste w) (swd_index w))).

(* R-15-036h's own linear form, which the register quotes at the reference
   instantiation as 36.6 - 18.3p: the intercept is twice the per-slot cost and
   the slope is the per-slot cost, both in tenths of a bit, which is the
   precision that sentence states them to. *)
Definition lin_line (h k : Z) : string :=
  "fm lin " ++ zs slot_width ++ " " ++ zs h ++ " " ++ zs k ++ " ->"
    ++ " " ++ zs (scaled (2 * bundle_of slot_width h k) k coeff_scale)
    ++ " " ++ zs (scaled (bundle_of slot_width h k) k coeff_scale)
    ++ " " ++ zs (bundle_of slot_width h k)
    ++ " " ++ zs (scaled (bundle_of slot_width h k) k bits_scale).

Definition ref_line (pm : Z) : string :=
  "fm ref " ++ zs pm ++ " ->"
    ++ " " ++ zs (bare_bits slot_width ref_header ref_slots pm)
    ++ " " ++ zs (bound_num pm)
    ++ " " ++ zs (bound_den ref_slots)
    ++ " " ++ zs (scaled (bound_num pm) (bound_den ref_slots) rate_scale)
    ++ " " ++ zs (packed_bits slot_width ref_header ref_slots pm
                              (bound_num pm) (bound_den ref_slots)).

Definition geo_line (h k pm : Z) : string :=
  "fm geo " ++ zs slot_width ++ " " ++ zs h ++ " " ++ zs k
            ++ " " ++ zs pm ++ " ->"
    ++ " " ++ zs (bundle_of slot_width h k)
    ++ " " ++ bs (legal h k)
    ++ " " ++ zs (scaled (bundle_of slot_width h k) k bits_scale)
    ++ " " ++ zs (scaled (bound_num pm) (bound_den k) rate_scale)
    ++ " " ++ zs (scaled (required_num slot_width h k pm)
                         (required_den slot_width h k) rate_scale)
    ++ " " ++ zs (scaled (min_p_at_bound_num slot_width h k)
                         (min_p_den slot_width h k) rate_scale)
    ++ " " ++ zs (scaled (min_p_unpacked_num slot_width h k)
                         (min_p_den slot_width h k) rate_scale)
    ++ " " ++ bs (clears slot_width h k pm)
    ++ " " ++ bs (infeasible slot_width h k pm)
    ++ " " ++ zs (bare_bits slot_width h k pm).

Definition obe_line (n : Z) : string :=
  "fm obe " ++ zs n ++ " ->"
    ++ " " ++ os (obe_absolute n)
    ++ " " ++ os (obe_pcrelative n).

(* -------------------------------------------------------------------------
   The walk, in the order the Python states it. The comparison is keyed by the
   fields before the arrow rather than by position, so this order is what a
   person reads the two files in and not what decides the verdict.
   ------------------------------------------------------------------------- *)

Definition report : list string :=
  List.app (cons bar_line nil)
  (List.app (map swd_line slot_widths)
  (List.app (flat_map (fun h => map (lin_line h) slot_counts) headers)
  (List.app (map ref_line hit_rates)
  (List.app (flat_map (fun h =>
               flat_map (fun k => map (geo_line h k) geometry_rates)
                        slot_counts)
             headers)
            (map obe_line region_lengths))))).

Compute report.
