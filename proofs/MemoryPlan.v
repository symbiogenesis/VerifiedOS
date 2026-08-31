(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   MemoryPlan.v

   The two-class static memory plan and its placement WCET delta, as the
   register fixes them: R-08-011's whole-program slot plan with its
   live-range colouring, which fixes each object's allocation and free
   points at compile time; R-15-247's two static latency classes under one
   placement discipline, each entering section 11 as one fixed latency
   constant, with no cache, no migration, no tiering and no runtime
   promotion between them; R-15-247s's two class lists, its
   latency-criticality boundary that carries no trust gradient, and its
   placement of application payloads by criterion and not by name;
   R-15-247j's placement rule, all hard-task and all hot code on the first
   class and an admission-visible WCET delta for second-class code
   computed against that class's fetch constant; R-14-015's
   interpreter-arena placement, the arenas second class and the
   interpreter body first class, with the origin-pool ceiling *P* raised
   for the same first-class budget as its booked consequence; R-15-007k's
   exact representability at R-15-007c's own two-regime granule,
   discharged against the slot plan rather than by a runtime instrument;
   R-08-012c's island containment; R-08-012's collapse of over-reservation
   onto the proven simultaneous peak and R-08-014's decidable interference
   side condition over it; R-08-045's charge, every physical byte claimed
   by one line item; R-14-009 and R-14-010's origin pool and its ceiling;
   and R-11-006's interval arithmetic with R-11-009's switch duty inside
   it, which is what the delta is an input to.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. It is a Gallina statement
   artifact rather than a Wasm-parallel item because this cell carries no
   such label and the tree's precedent for an item of exactly this shape,
   an algebra with an admission predicate over it stated over arbitrary
   parameters, is CyclicExecutive.v; that call is recorded here as a call
   and reported as one. Every quantity the register leaves to composition
   is a field of the Plan record rather than a literal or a top-level
   Parameter, which is what keeps the R-05-163 assumption gate green while
   leaving the decision where its owner can make it. Nothing is admitted
   and nothing is axiomatized: the Print Assumptions block at the end
   reports every shipped constant closed under the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. No constant here is
   compiled, lowered, or run on either emulator, and nothing here executes
   anywhere. The computed checks are decided inside the kernel by
   conversion and print nothing.

   What is deferred, and to which item. The backend that emits the
   narrowings R-15-007k constrains is M1.2's, and nothing below is a
   lowering, an instruction selection, or a claim about emitted code: what
   is here is the plan-side side condition M1.2's axis-6 paragraph says is
   otherwise written against a plan that lands two items later. The
   per-instruction latency table R-11-015 derives a bound from is
   R-11-015's own and is not authored, so a region's fetch count and a
   slot's declared in-slot bound are declared inputs here. The per-class
   constants themselves are R-15-247m's to measure at part qualification;
   the model carries them as a composition-time declaration
   (model/model/core/memory_class.sail) with `qualified` false in every
   shipped configuration, and this file states no magnitude for either.

   The one Require, and why it is a dependency rather than a citation.
   R-15-247j's own acceptance clause makes the delta an input to section
   11 admission rather than a report about it, and section 11 admission in
   this tree is CyclicExecutive.v's R-11-006 interval arithmetic with
   R-11-009's partition-switch constant already inside it. So the delta is
   charged into the declared bound of the slot the region's code runs in,
   and the margin below moves `admits` itself: at the composed constants
   one unit more of delta turns an admitted frame into a refused one.
   Nothing else is reachable. Classical and FunctionalExtensionality are
   unavailable, and every equality below is stated pointwise or over a
   decidable boolean for that reason; `all_of` and `count_of` are consumed
   from the required artifact rather than restated, and the helpers this
   file adds are defined here rather than imported, the prelude carrying
   the list type and not the library over it. The arithmetic lemmas below
   are proved rather than imported for the same reason: the stdlib module
   carrying them is outside the prelude, and adding zero axioms is the
   point of the gate.

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. "That class's fetch constant" is that class's own read latency
      constant. R-15-247 makes each class enter section 11 as **one** fixed
      latency constant and R-15-164 deletes every cache, so there is no
      instruction cache, nothing to amortize, and a fetch is a read of
      whichever class the code resides on. This is not an open question:
      M0.14's landed cell reads R-15-247j and R-15-164 together and records
      that there is no separate fetch constant to declare and that the
      delta is the difference of two numbers R-15-247m's per-class record
      already carries, computed by this plan. Two fields carry the two
      constants and no magnitude is written down.
   2. The delta is a product and not a per-region constant. R-15-247j
      prices a *placement*, and R-11-015 derives a bound as a
      syntax-directed max-path sum over the typed control-flow graph, so
      what the placement multiplies is a count of fetches that derivation
      already carries. The count is a field and the delta is that count
      times the difference of the two class constants.
   3. The delta never credits. Nat's difference truncates at zero, which
      is what a composition declaring a faster second class produces here,
      and R-11-015a makes a claimed tightening the derivation does not
      support fail admission rather than ship. So the second class being
      at least as slow is a declared side condition and not a fact, a plan
      that breaks it is exhibited below with the truncation it produces,
      and a plan whose two constants coincide carries no delta at all,
      which is R-15-247s's boundary being latency and nothing else.
   4. The register places by name where it names and by criterion where it
      does not, and both halves are obligations. R-15-247s's two lists
      place twenty region kinds by name and R-14-015 a twenty-first, so a
      composition choosing there would be a composition amending the
      register: `placed_by_name` is a definition this file does not
      parameterize. But that entry also settles one term of R-08-045's
      charge *without naming it*: ownership is no part of a latency
      criterion, so an application payload is placed by criterion, its
      cycle-critical part carried by the scalar working set and every
      cycle-critical array and its bulk by bulk by volume. Which regions
      are genuinely cycle-critical is therefore a per-region judgment the
      composition supplies, carried by the `cycle_critical` field, and a
      placement that reads the payload's name instead is refuted below.
      `class_of` is a field a plan may get wrong and `register_place` is
      what it is checked against.
   5. The interpreter body is a region kind the two lists do not name, and
      that is not a gap. R-15-247s's closure criterion is stated of "a term
      of that charge", which is R-08-045's ten-term enumeration of every
      physical byte; that enumeration names the interpreter object
      *arenas* and not the body, so the criterion says nothing about the
      body. R-14-015 places it on the first class by name, and that is the
      placement.
   6. A transposition of the placement list is not a weakening and a
      transposition of the class vector is. No entry orders the placed
      regions, so the deletion and insertion families are generated over
      the placement list, where R-08-045's charge decides, while the class
      vector is decided by R-15-247j. That a transposition of the
      placement list is refused by nothing is stated as a computed fact
      rather than left as a silence, and the transposed class vectors are
      shown to be members of the whole assignment family rather than
      credited as content of their own.
   7. Two regions may share one slot, and this reading is taken against
      R-08-014's literal words. That entry says slot disjointness over
      *disjoint* live ranges; R-08-012 collapses over-reservation onto the
      proven simultaneous peak by live-range colouring, which is exactly
      two disjoint live ranges sharing one slot, so the side condition
      that mechanism needs is disjointness over *overlapping* live ranges.
      The literal reading is carried below as a construction and shown to
      refuse the sharing, and gap f reports the inversion at the entry.
   8. Exactness is decided against granule counts the plan declares rather
      than by a division, the granule is not a declaration at all, and
      above the threshold it is a *bound* rather than a value. R-15-007c
      fixes it as a function of the object's length, byte-exact to 128
      bytes at any base and rounding outward above that "at a granularity
      of at worst the length over 2^6"; that sentence bounds the
      encoding's granule and does not name it, and the same entry says the
      exponent is chosen so the decoder knows the length mantissa's top
      two bits, which makes every granule the encoding can use a power of
      two. R-15-007k lays each object at *that array's* representable
      alignment, so the plan must align to the coarsest granule the
      encoding may use rather than to any finer one it might: a finer
      alignment admits a base the encoding rounds. The quantum here is
      therefore the coarsest power of two within the entry's bound, stated
      as four clauses a quantum can fail, and the division itself is
      refuted below: at the demo roster's own 192-byte region it yields 3,
      which is no encoding's alignment and which admits an odd base. The
      two bound clauses are the band the entry's own model test states,
      one part in 64 to one part in 128 of the length on each side
      (model/model/unit_tests/test_capability.sail), and the power of two
      is the one member that band leaves. A plan-wide granule is refuted
      too, whatever its magnitude.
   9. A narrowing's address is a composition-time slot base plus a
      composition-time offset plus a dynamic index times a
      composition-time stride, and its length is its type's. That is
      R-15-007k's own sentence taken as the shape of the Narrowing record,
      which is what makes exactness decidable where the index is not.
  10. Boolean rather than propositional wherever the witnesses must
      compute: the placement check, the colouring, the island containment,
      the representability tests and the pool arithmetic are decidable, so
      the generated families below are checked by conversion in the silent
      Example form rather than by a proof per member. The class-assignment
      family, both placement-list families and the two ladders read at the
      focus and at the reserved band are each also stated as a bounded
      quantifier over their own index; the background slot's ladder is a
      single computed contrast and carries no quantifier (limit ii).
  11. A charged slot index is a slot the frame carries. R-15-247j's
      acceptance clause makes the delta an input to section 11 admission
      rather than a report about it, and the arithmetic it is an input to
      is stated over the frame's own slot list, so an index past the end
      of that list charges no bound and the delta stops being an input at
      all. The range is the frame's rather than the plan's, so the
      obligation is stated of a plan against a frame and conjoined with
      R-08-045's charge below; a plan that declares an index no frame
      carries is refuted, and the verdict it flips is exhibited.

   The literals taken from the design, and there are nine numerals. They
   are read from the entries' own words, term by term, and from no tooling
   table. R-15-247 closes the class enumeration at two, so `all_classes` is
   that list and `there_are_two_latency_classes` is its count. R-15-247s's
   first list names eleven terms and R-15-247j closes it with a twelfth, so
   `the_first_list_names_twelve_kinds` is that count; its second list names
   eight, so `the_second_list_names_eight_kinds` is that one; twenty is
   their sum and twenty-one is that sum plus the one kind R-14-015 names
   and neither list carries. R-08-045 charges every physical byte to one
   line item, so `each_region_once` compares an occurrence count against 1.
   And R-15-007c fixes the representable granule at 1 up to 128 bytes and
   bounds it by the length over 2^6 above it, so 128 and 64 are that
   entry's two figures, and the 2 the exponent search steps by is that
   entry's own exponent base, the ninth. No construction below writes a
   granule down: the refuted one takes it as a parameter and is
   instantiated at the entry's own division of a length the plan declares.
   What is *not* a literal here is any total over the region
   kinds: no entry closes that enumeration (gap a), so `all_kinds` carries
   no count. Every other magnitude is a field: the roster size, each
   region's kind, cycle-criticality, class, slot base, slot length,
   declared base and length granule counts, live range, owning island,
   fetch count and charged slot; the island extents; both class constants;
   the placement list; the origin pool's per-member roster; the fixed
   first-class charge; and the first-class budget.

   How the refutations are generated. A refutation is a seeded weakening
   the theorem must reject, so four generators produce families of them
   mechanically rather than a person authoring each, which is
   SupervisionTree.v's method taken to a placement. Over the two classes
   and the roster: `all_masks` enumerates every assignment of the two
   classes across the regions, 256 of them at the composed roster, of which
   exactly one places as the register places. Over that vector: `swap_at`
   transposes an adjacent pair, and the composed roster alternates classes
   so every adjacent transposition is refused; that family is a subset of
   the first, computed here rather than claimed, so what it carries is the
   contrast with the placement list and not a second refusal. Over the
   placement list: `drop_at` deletes a region and `insert_at` places one
   twice, which is R-08-045's charge broken in each direction, while
   `swap_at` over the same list is refused by nothing. And over the delta:
   a ladder of second-class constants exhibits the admission verdict at
   every delta from zero through past the margin. The hand-authored
   refutations below are the ones no index generates, being alternative
   constructions rather than mutations of a list, and each is shown to
   satisfy the obligations it does not break.

   What this file deliberately does not author, with the entry that owes
   each decision. A register gap is reported, not closed:

   a. What closes the region-kind enumeration. R-15-247s's two lists name
      twenty kinds, R-14-015 names a twenty-first, and R-08-045's charge
      names application payloads, which that entry answers by criterion
      rather than by name; no entry says these are all the kinds a
      composition may place, and R-15-247s's own closure criterion is
      stated over the charge's ten terms rather than over the kinds. The
      inductive below is therefore the register's own names plus the
      by-criterion arm, and it is a floor rather than a total: no count is
      asserted over it. Owed at R-15-247s.
   b. Whether the delta is charged per region or per task. R-15-247j says
      second-class *code placement* carries the delta, and R-11-009
      charges a *task*'s real cost. A task whose code spans two regions is
      addressed by neither, and this file charges per region and sums
      nothing. Owed at R-15-247j.
   c. Whether a hard task may hold any code on the second class at all.
      R-15-247j places all hard-task code on the first class and says
      nothing about a hard task calling a cold second-class routine, which
      is the case the delta would price if it arose. This file states the
      placement rule over region kinds and states no reachability
      relation. Owed at R-15-247j.
   d. Which regions an origin-pool member owns. R-14-015 books the ceiling
      raise as a consequence and R-14-009 fixes the pool at *P* identical
      compartments with one manifest and one static memory plan, and no
      entry enumerates the member's own regions. The roster is a field and
      the ceiling is stated over an arbitrary one and over an arbitrary
      population bound. Owed at R-14-015 or R-14-009.
   e. What R-08-011's live range is measured in. The entry fixes each
      object's live range at compile time and R-08-014 makes the side
      condition an interference test over it, and no entry states the
      ordering the range is an interval of. Two fields carry an interval
      over nat and no unit is claimed. Owed at R-08-011.
   f. R-08-014's own quantifier. The entry states the side condition as
      slot disjointness over *disjoint* live ranges, and read literally
      that refuses exactly the sharing R-08-012's collapse onto the proven
      simultaneous peak exists to produce, which that entry calls the
      minimum any non-moving scheme can use. The literal reading cannot be
      meant, and it is carried below as `literal_colouring_ok` and shown
      refusing the shared-slot plan; the reading taken is disjointness over
      overlapping live ranges (reading 7). Owed at R-08-014.
   g. Every composition magnitude. The roster, the kinds, the
      cycle-criticality judgment, the assignment, the bases, the lengths,
      the granule counts, the live ranges, the islands and their extents,
      both class constants, the fetch counts, the charged slots, the
      placement list, the origin roster, the fixed first-class charge and
      the first-class budget are fields; the demo plan at the end
      instantiates them with arbitrary witness values that carry no
      composition claim.

   What this statement does not decide about itself. These are limits of
   the coverage below rather than gaps in the register, recorded here
   because a limit nothing states reads as a claim:

   i. `ChargesTheRegionSOwnSlot` decides more than its name says. It is
      pointwise equality to the specification's admission, so what it
      excludes is every admission that differs from that one anywhere, and
      it does not isolate the slot: `brittle_admission` counts the delta
      and fails this property too, for a reason that has nothing to do
      with which slot it reads. The slot is isolated by the two witnesses
      beside the refutation instead, which read the same plan at the
      region's own slot and at the frame's focus, and that separation is a
      pair of computed facts rather than a stated property.
  ii. The background slot's delta ladder is an Example alone. The focus
      ladder and the reserved ladder each carry a Definition and a bounded
      quantifier over its own rungs; the third is one conversion over the
      same generator at a third slot, and it carries neither.
 iii. Reading 9's narrowing shape is exercised by one witness. The
      exactness theorem quantifies over an arbitrary plan and an arbitrary
      narrowing, so the shape itself is not what a witness decides, but
      the only narrowing constructed below sits at offset zero with one
      granule of length, so two of the record's five terms are pinned by
      no construction. The shape is register-faithful and the coverage is
      one point of it.
  iv. `rounding_narrow_ok` admits everything, so its twin is true by
      construction and carries nothing. It is counted apart below for that
      reason.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary assignment, placer, delta, admission, quantum,
   narrowing check, placement, colouring, plan or population bound, proved
   of the specification, and refuted of an alternative construction the
   register's own sentence excludes. The refutation is of the obligation
   and not of a check that decides it: where an obligation is stated as a
   bounded quantifier and computed by a boolean, that boolean is proved
   sound *and* complete, so a check answering false is a refutation of the
   property and not a report that a decision procedure moved. Inhabitation
   is concrete: a plan whose roster, islands, live ranges and slots are
   inhabited, whose two class constants differ, whose placement admits and
   whose margin is exact, beside 255 assignments that do not place as the
   register places, 17 weakenings of the placement list that are refused, 7
   transpositions of the placement list that are refused by nothing, and
   three nine-rung delta ladders read at the three slots three regions
   declare, whose margins are five, three and one, each admitting at its
   own margin and refusing one unit past it.
   Sixteen authored constructions carry a twin with content, each shown to
   satisfy what it does not break: `promoting_placer` and `demoting_placer`
   still make the by-name placements they do not move;
   `by_name_payload_assign` keeps every by-name placement and breaks only
   the criterion; `length_scaled_delta` still charges nothing on the first
   class and nothing where the constants coincide; `reporting_admission` is
   monotone and `brittle_admission` counts the delta;
   `focus_charging_admission` agrees wherever the region is charged to the
   focus; `within_one_granule_narrow_ok` admits everything the
   specification admits; `flat_quantum 1` keeps the regime below the
   threshold and stays inside the entry's bound on a power-of-two
   alignment; `single_regime_quantum` keeps all three clauses above the
   threshold; `coarser_quantum` keeps the regime below it and aligns on a
   power of two; `granule_inside_the_window` keeps both bounds and the
   regime below; `clamped_placement` agrees wherever the plan stays inside;
   `strict_colouring_ok` and `literal_colouring_ok` agree with the
   specification's colouring on the demo plan; and `brittle_bound` admits
   every population the specification admits at a costed member. A
   seventeenth, `rounding_narrow_ok`, carries a twin that is true by
   construction and is counted apart for that reason (limit iv). Fifteen
   further plans differ in exactly one declared quantity each from the
   specification's or from the named variant, which is what makes each
   refutation a single-defect witness: four move the second class's own
   constant alone, one unit dearer than the first class's, equal to it, one
   unit past the margin, and below it; seven move one slot base alone, into
   a shared slot, into an overlapping one, past its island, below its
   island, off its granule, off it by exactly a granule, and onto the odd
   base a granule computed by division would have admitted; two move one
   region's declared length, off its granule and onto a shorter one; and
   two move one region's charged slot, the second of them past the count of
   slots the frame carries.
   ========================================================================= *)

Require Import CyclicExecutive.

(* -------------------------------------------------------------------------
   List and boolean helpers, defined here rather than imported: the prelude
   carries the list type and not the library over it, and importing a
   module to save a dozen lines would put its assumptions inside the
   R-05-163 gate's reach for no gain. `all_of` and `count_of` come from the
   required artifact and are not restated.
   ------------------------------------------------------------------------- *)

Fixpoint any_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => false
  | cons x r => orb (p x) (any_of p r)
  end.

Fixpoint map_over {A B : Type} (f : A -> B) (l : list A) : list B :=
  match l with nil => nil | cons x r => cons (f x) (map_over f r) end.

Fixpoint filter_of {A : Type} (p : A -> bool) (l : list A) : list A :=
  match l with
  | nil => nil
  | cons x r => if p x then cons x (filter_of p r) else filter_of p r
  end.

(* 0 through n-1, in that order: the index set the roster and the
   generators below range over. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

Definition before_last (n : nat) : nat :=
  match n with 0 => 0 | S k => k end.

(* The nth member of a list, or the declared fallback past its end. What
   the fallback is for is reading a per-region declaration at an index the
   roster does not carry: R-08-045 charges every physical byte to a line
   item, so a region outside the roster declares nothing rather than
   declaring something arbitrary. *)
Fixpoint at_list {A : Type} (l : list A) (n : nat) (d : A) : A :=
  match l with
  | nil => d
  | cons x r => match n with 0 => x | S k => at_list r k d end
  end.

Fixpoint occurrences (u : nat) (l : list nat) : nat :=
  match l with
  | nil => 0
  | cons v r => if Nat.eqb u v then S (occurrences u r) else occurrences u r
  end.

(* Implication as a boolean, written out rather than taken from a library
   for the reason above. *)
Definition only_if (a b : bool) : bool := orb (negb a) b.

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

Lemma andb_join : forall a b : bool, a = true -> b = true -> andb a b = true.
Proof. intros a b Ha Hb. rewrite Ha. rewrite Hb. reflexivity. Qed.

Lemma only_if_elim :
  forall a b : bool, only_if a b = true -> a = true -> b = true.
Proof.
  intros a b H Ha. unfold only_if in H. rewrite Ha in H. simpl in H. exact H.
Qed.

(* And the other direction, which is what a completeness proof needs: a
   boolean implication holds wherever the implication does. *)
Lemma only_if_intro :
  forall a b : bool, (a = true -> b = true) -> only_if a b = true.
Proof.
  intros a b H. destruct a; simpl; [ exact (H eq_refl) | reflexivity ].
Qed.

Lemma all_of_const :
  forall (A : Type) (p : A -> bool) (l : list A),
    (forall x : A, p x = true) -> all_of p l = true.
Proof.
  intros A p l H. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. rewrite (H x). exact IH.
Qed.

Lemma all_of_app :
  forall (A : Type) (p : A -> bool) (l r : list A),
    all_of p (app l r) = true -> all_of p l = true /\ all_of p r = true.
Proof.
  intros A p l r. induction l as [ | x s IH ]; intros H.
  - split; [ reflexivity | exact H ].
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hs ].
    destruct (IH Hs) as [ Hl Hr ]. split; [ | exact Hr ].
    simpl. apply andb_join; [ exact Hx | exact Hl ].
Qed.

Lemma all_of_app_join :
  forall (A : Type) (p : A -> bool) (l r : list A),
    all_of p l = true -> all_of p r = true -> all_of p (app l r) = true.
Proof.
  intros A p l r. induction l as [ | x s IH ]; intros Hl Hr.
  - exact Hr.
  - simpl in Hl. destruct (andb_split _ _ Hl) as [ Hx Hs ].
    simpl. apply andb_join; [ exact Hx | exact (IH Hs Hr) ].
Qed.

Lemma any_of_app_true :
  forall (A : Type) (p : A -> bool) (l r : list A),
    orb (any_of p l) (any_of p r) = true -> any_of p (app l r) = true.
Proof.
  intros A p l r. induction l as [ | x s IH ]; intros H.
  - exact H.
  - simpl in H. simpl. destruct (p x); [ reflexivity | exact (IH H) ].
Qed.

(* Reading a conjunction over an index set back at one of its members, and
   at one of its positions. The first is what lets an obligation over the
   roster be stated of an arbitrary region rather than only computed over
   a demo one; the second is what lets a generated family's fact be stated
   as a bounded quantifier over the index rather than only as the
   enumeration that decided it. *)
Lemma leb_split : forall v k : nat, Nat.leb v k = true -> Nat.ltb v k = true \/ v = k.
Proof.
  intros v. induction v as [ | a IH ]; intros k H.
  - destruct k as [ | b ]; [ right; reflexivity | left; reflexivity ].
  - destruct k as [ | b ].
    + discriminate H.
    + simpl in H. destruct (IH b H) as [ Hlt | Heq ].
      * left. exact Hlt.
      * right. rewrite Heq. reflexivity.
Qed.

Lemma all_of_upto :
  forall (p : nat -> bool) (n v : nat),
    all_of p (upto n) = true -> Nat.ltb v n = true -> p v = true.
Proof.
  intros p n. induction n as [ | k IH ]; intros v H Hv.
  - discriminate Hv.
  - simpl in H. destruct (all_of_app nat p (upto k) (cons k nil) H) as [ Hk Hlast ].
    simpl in Hlast. destruct (andb_split _ _ Hlast) as [ Hpk _ ].
    simpl in Hv. destruct (leb_split v k Hv) as [ Hlt | Heq ].
    + exact (IH v Hk Hlt).
    + rewrite Heq. exact Hpk.
Qed.

(* And the same conjunction built rather than read, which is what turns a
   boolean check over the roster into a decision procedure for the
   obligation stated over it: with this direction and the one above, a
   check answering false refutes the property rather than reporting that
   the check moved. *)
Lemma ltb_succ_r : forall v k : nat, Nat.ltb v k = true -> Nat.ltb v (S k) = true.
Proof.
  intros v. induction v as [ | a IH ]; intros k H.
  - reflexivity.
  - destruct k as [ | b ]; [ discriminate H | ].
    simpl in H. simpl. exact (IH b H).
Qed.

Lemma ltb_succ_diag : forall k : nat, Nat.ltb k (S k) = true.
Proof. intros k. induction k as [ | j IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma all_of_upto_intro :
  forall (p : nat -> bool) (n : nat),
    (forall v : nat, Nat.ltb v n = true -> p v = true) ->
    all_of p (upto n) = true.
Proof.
  intros p n. induction n as [ | k IH ]; intros H.
  - reflexivity.
  - apply (all_of_app_join nat p (upto k) (cons k nil)).
    + apply IH. intros v Hv. exact (H v (ltb_succ_r v k Hv)).
    + simpl. apply andb_join; [ exact (H k (ltb_succ_diag k)) | reflexivity ].
Qed.

Lemma any_of_upto_intro :
  forall (p : nat -> bool) (n v : nat),
    Nat.ltb v n = true -> p v = true -> any_of p (upto n) = true.
Proof.
  intros p n. induction n as [ | k IH ]; intros v Hv Hp.
  - discriminate Hv.
  - apply (any_of_app_true nat p (upto k) (cons k nil)).
    simpl in Hv. destruct (leb_split v k Hv) as [ Hlt | Heq ].
    + rewrite (IH v Hlt Hp). reflexivity.
    + rewrite <- Heq. simpl. rewrite Hp.
      destruct (any_of p (upto v)); reflexivity.
Qed.

Lemma all_of_at :
  forall (A : Type) (p : A -> bool) (l : list A) (d : A) (n : nat),
    all_of p l = true -> Nat.ltb n (count_of l) = true -> p (at_list l n d) = true.
Proof.
  intros A p l d. induction l as [ | x r IH ]; intros n Hall Hn.
  - discriminate Hn.
  - simpl in Hall. destruct (andb_split _ _ Hall) as [ Hx Hr ].
    destruct n as [ | k ]; simpl.
    + exact Hx.
    + simpl in Hn. exact (IH k Hr Hn).
Qed.

(* -------------------------------------------------------------------------
   The arithmetic this file needs and the prelude does not carry. Proved
   rather than imported: the stdlib modules holding these are outside the
   prelude, and an assumption reachable through an import is an assumption
   inside R-05-163's gate.
   ------------------------------------------------------------------------- *)

Lemma add_0_r : forall n : nat, n + 0 = n.
Proof.
  intros n. induction n as [ | k IH ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

Lemma add_succ_r : forall n m : nat, n + S m = S (n + m).
Proof.
  intros n m. induction n as [ | k IH ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

Lemma add_comm : forall n m : nat, n + m = m + n.
Proof.
  intros n m. induction n as [ | k IH ].
  - simpl. rewrite add_0_r. reflexivity.
  - simpl. rewrite IH. rewrite add_succ_r. reflexivity.
Qed.

Lemma add_assoc : forall n m k : nat, n + (m + k) = n + m + k.
Proof.
  intros n m k. induction n as [ | a IH ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

Lemma mul_add_distr_l : forall a b c : nat, a * (b + c) = a * b + a * c.
Proof.
  intros a b c. induction a as [ | k IH ].
  - reflexivity.
  - simpl. rewrite IH.
    rewrite <- (add_assoc b c (k * b + k * c)).
    rewrite (add_assoc c (k * b) (k * c)).
    rewrite (add_comm c (k * b)).
    rewrite <- (add_assoc (k * b) c (k * c)).
    rewrite (add_assoc b (k * b) (c + k * c)).
    reflexivity.
Qed.

Lemma sub_diag : forall n : nat, n - n = 0.
Proof.
  intros n. induction n as [ | k IH ].
  - reflexivity.
  - simpl. exact IH.
Qed.

Lemma sub_0_r : forall n : nat, n - 0 = n.
Proof. intros n. destruct n as [ | k ]; reflexivity. Qed.

Lemma mul_0_r : forall n : nat, n * 0 = 0.
Proof.
  intros n. induction n as [ | k IH ].
  - reflexivity.
  - simpl. exact IH.
Qed.

Lemma add_sub_cancel : forall n m : nat, Nat.leb n m = true -> n + (m - n) = m.
Proof.
  intros n. induction n as [ | k IH ]; intros m H.
  - simpl. destruct m as [ | j ]; reflexivity.
  - destruct m as [ | j ]; [ discriminate H | ].
    simpl in H. simpl. rewrite (IH j H). reflexivity.
Qed.

Lemma ltb_add_pos :
  forall n k : nat, Nat.ltb 0 k = true -> Nat.ltb n (n + k) = true.
Proof.
  intros n k H. induction n as [ | a IH ].
  - simpl. destruct k as [ | b ]; [ discriminate H | reflexivity ].
  - simpl. exact IH.
Qed.

Lemma leb_refl : forall n : nat, Nat.leb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma leb_trans :
  forall a b c : nat, Nat.leb a b = true -> Nat.leb b c = true -> Nat.leb a c = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b c Hab Hbc.
  - reflexivity.
  - destruct b as [ | y ]; [ discriminate Hab | ].
    destruct c as [ | z ]; [ discriminate Hbc | ].
    simpl in Hab. simpl in Hbc. simpl. exact (IH y z Hab Hbc).
Qed.

Lemma ltb_leb_false : forall n m : nat, Nat.ltb m n = true -> Nat.leb n m = false.
Proof.
  intros n. induction n as [ | b IH ]; intros m H.
  - discriminate H.
  - destruct m as [ | a ].
    + reflexivity.
    + simpl in H. simpl. exact (IH a H).
Qed.

Lemma leb_add_l : forall n k : nat, Nat.leb n (n + k) = true.
Proof. intros n k. induction n as [ | a IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma leb_add_r : forall n k : nat, Nat.leb n (k + n) = true.
Proof. intros n k. rewrite (add_comm k n). exact (leb_add_l n k). Qed.

Lemma add_le_mono :
  forall a b c d : nat,
    Nat.leb a b = true -> Nat.leb c d = true -> Nat.leb (a + c) (b + d) = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b c d Hab Hcd.
  - simpl. exact (leb_trans c d (b + d) Hcd (leb_add_r d b)).
  - destruct b as [ | y ]; [ discriminate Hab | ].
    simpl in Hab. simpl. exact (IH y c d Hab Hcd).
Qed.

Lemma mul_le_mono_l :
  forall a b c : nat, Nat.leb b c = true -> Nat.leb (a * b) (a * c) = true.
Proof.
  intros a. induction a as [ | k IH ]; intros b c H.
  - reflexivity.
  - simpl. exact (add_le_mono b c (k * b) (k * c) H (IH b c H)).
Qed.

Lemma eqb_true : forall n m : nat, Nat.eqb n m = true -> n = m.
Proof.
  intros n. induction n as [ | k IH ]; intros m H.
  - destruct m as [ | j ]; [ reflexivity | discriminate H ].
  - destruct m as [ | j ]; [ discriminate H | ].
    simpl in H. rewrite (IH j H). reflexivity.
Qed.

Lemma eqb_refl : forall n : nat, Nat.eqb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

(* A refused comparison read the other way, which is what a search that
   stops needs: the step it declined is the step past its own bound. *)
Lemma leb_false_ltb : forall n m : nat, Nat.leb n m = false -> Nat.ltb m n = true.
Proof.
  intros n. induction n as [ | k IH ]; intros m H.
  - discriminate H.
  - destruct m as [ | j ].
    + reflexivity.
    + simpl in H. simpl. exact (IH j H).
Qed.

Lemma leb_succ_false : forall n : nat, Nat.leb (S n) n = false.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma leb_mul_self :
  forall a x : nat, Nat.leb 1 a = true -> Nat.leb x (a * x) = true.
Proof.
  intros a x H. destruct a as [ | k ]; [ discriminate H | ].
  simpl. exact (leb_add_l x (k * x)).
Qed.

(* What a prefix leaves: a bound over a sum read as a bound over the tail,
   which is the arithmetic of an index past a band's own slots. *)
Lemma leb_sub_of_add :
  forall a b i : nat, Nat.leb (a + b) i = true -> Nat.leb b (i - a) = true.
Proof.
  intros a. induction a as [ | k IH ]; intros b i H.
  - rewrite (sub_0_r i). exact H.
  - destruct i as [ | j ]; [ discriminate H | ].
    simpl in H. simpl. exact (IH b j H).
Qed.

Lemma count_of_app :
  forall (A : Type) (l r : list A),
    count_of (app l r) = count_of l + count_of r.
Proof.
  intros A l r. induction l as [ | x s IH ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

(* The helpers' own floors, so that the day one of them stops deciding is
   the day it says so. Each is a base case no other check below reaches. *)

Example the_empty_disjunction_fails : any_of (fun _ : nat => true) nil = false := eq_refl.

Example before_last_of_nothing : before_last 0 = 0 := eq_refl.

Example the_index_set_of_three : upto 3 = cons 0 (cons 1 (cons 2 nil)) := eq_refl.

Example the_fallback_past_the_end :
  at_list (cons 7 (cons 8 nil)) 0 3 = 7
  /\ at_list (cons 7 (cons 8 nil)) 1 3 = 8
  /\ at_list (cons 7 (cons 8 nil)) 2 3 = 3 := conj eq_refl (conj eq_refl eq_refl).

Example nothing_occurs_in_nothing :
  occurrences 1 nil = 0 /\ occurrences 1 (cons 1 (cons 2 (cons 1 nil))) = 2 :=
  conj eq_refl eq_refl.

Example a_filter_that_keeps_nothing :
  filter_of (fun _ : nat => false) (cons 1 (cons 2 nil)) = nil
  /\ filter_of (fun n => Nat.ltb 1 n) (cons 1 (cons 2 nil)) = cons 2 nil :=
  conj eq_refl eq_refl.

Example a_map_over_nothing : map_over S (nil : list nat) = nil := eq_refl.

Example only_if_is_implication :
  cons (only_if true true) (cons (only_if true false)
  (cons (only_if false true) (cons (only_if false false) nil)))
  = cons true (cons false (cons true (cons true nil))) := eq_refl.

(* =========================================================================
   The one closed enumeration, and the one that is not closed. The classes
   are closed because R-15-247 closes them at two. The region kinds are not:
   the two lists below are read from R-15-247s's own words term by term,
   R-14-015 adds the one kind neither list carries, and R-08-045's charge
   adds the term that entry answers by criterion rather than by name, but
   no entry says these are all the kinds a composition may place (gap a).
   So this inductive is the register's own names plus the by-criterion arm,
   and it carries no count.
   ========================================================================= *)

(* R-15-247's two static latency classes under one placement discipline.
   A second class is a second constant and not a hierarchy, so there is no
   third constructor and no ordering between these two. *)
Inductive MemClass : Type :=
| FirstClass    (* bespoke volatile 6T SRAM, the scalar working set and
                   every cycle-critical array                              *)
| SecondClass.  (* oxide-semiconductor 2T0C decks, bulk                    *)

(* R-15-247s's two lists, in that entry's own order and with its own terms,
   with R-15-247j's hard-task and hot code closing the first and R-14-015's
   arenas standing in the second; beside them the one kind R-14-015 places
   by name and neither list carries (reading 5); and last the term of
   R-08-045's charge that entry answers without naming, which is placed by
   criterion and not by name (reading 4). *)
Inductive RegionKind : Type :=
(* the first list *)
| ScalarWorkingSet
| CycleCriticalArray
| KernelObjects
| Stacks
| RegisterSaveAreas
| DmaWindows
| Rings
| GrantSlots
| QuarantineEntries
| RecoveryWorkspaces
| ServerScalarWorkingSets
| HardTaskAndHotCode           (* R-15-247j                                *)
(* the second list *)
| BulkByVolume
| Framebuffers
| Images
| VectorAndMatrixExtents
| InterpreterObjectArenas      (* R-14-015                                 *)
| MediaBuffers
| ColdStaticallyPlacedCode
| ModelWeights
(* named by R-14-015 and carried by neither list *)
| InterpreterBody
(* R-08-045's tenth charged term, placed by criterion and not by name *)
| ApplicationPayload.

Definition all_classes : list MemClass :=
  cons FirstClass (cons SecondClass nil).

(* R-15-247s's first list in that entry's own order, with R-15-247j's
   hard-task and hot code closing it. Twelve terms and not eleven: the
   servers' scalar working sets are the entry's eleventh. *)
Definition first_class_list : list RegionKind :=
  cons ScalarWorkingSet (cons CycleCriticalArray
  (cons KernelObjects (cons Stacks
  (cons RegisterSaveAreas (cons DmaWindows
  (cons Rings (cons GrantSlots
  (cons QuarantineEntries (cons RecoveryWorkspaces
  (cons ServerScalarWorkingSets (cons HardTaskAndHotCode nil))))))))))).

(* And its second list, with R-14-015's arenas standing in it. *)
Definition second_class_list : list RegionKind :=
  cons BulkByVolume (cons Framebuffers
  (cons Images (cons VectorAndMatrixExtents
  (cons InterpreterObjectArenas (cons MediaBuffers
  (cons ColdStaticallyPlacedCode (cons ModelWeights nil))))))).

Definition listed_kinds : list RegionKind :=
  app first_class_list second_class_list.

(* The kinds the register places by name, which is the two lists and
   R-14-015's interpreter body. The by-criterion term is deliberately not
   here: it is placed, and it is not placed by name. *)
Definition named_kinds : list RegionKind :=
  app listed_kinds (cons InterpreterBody nil).

(* Every kind this file can express. It is a floor and not a total, so
   nothing below counts it (gap a). *)
Definition all_kinds : list RegionKind :=
  app named_kinds (cons ApplicationPayload nil).

(* Which class the register itself puts each kind on, where it puts it by
   name (reading 4). This is a definition and not a field: R-15-247s places
   twenty of these by name and R-14-015 the twenty-first, so a composition
   choosing here would be a composition amending the register. The one term
   it does not name answers `None`, which is not an omission but that
   entry's own "answered without being named". *)
Definition placed_by_name (k : RegionKind) : option MemClass :=
  match k with
  | ScalarWorkingSet => Some FirstClass
  | CycleCriticalArray => Some FirstClass
  | KernelObjects => Some FirstClass
  | Stacks => Some FirstClass
  | RegisterSaveAreas => Some FirstClass
  | DmaWindows => Some FirstClass
  | Rings => Some FirstClass
  | GrantSlots => Some FirstClass
  | QuarantineEntries => Some FirstClass
  | RecoveryWorkspaces => Some FirstClass
  | ServerScalarWorkingSets => Some FirstClass
  | HardTaskAndHotCode => Some FirstClass
  | BulkByVolume => Some SecondClass
  | Framebuffers => Some SecondClass
  | Images => Some SecondClass
  | VectorAndMatrixExtents => Some SecondClass
  | InterpreterObjectArenas => Some SecondClass
  | MediaBuffers => Some SecondClass
  | ColdStaticallyPlacedCode => Some SecondClass
  | ModelWeights => Some SecondClass
  | InterpreterBody => Some FirstClass
  | ApplicationPayload => None
  end.

(* R-15-247s's criterion, as a criterion: ownership is no part of a latency
   criterion, so what decides an application payload's class is whether the
   part is cycle-critical, its cycle-critical part being carried by the
   scalar working set and every cycle-critical array the first list opens
   with and its bulk by the bulk by volume the second opens with. The
   judgment itself is the composition's and is a field of the plan. *)
Definition criterion_class (critical : bool) : MemClass :=
  if critical then FirstClass else SecondClass.

Definition class_eqb (c d : MemClass) : bool :=
  match c, d with
  | FirstClass, FirstClass => true
  | SecondClass, SecondClass => true
  | _, _ => false
  end.

Lemma class_eqb_refl : forall c : MemClass, class_eqb c c = true.
Proof. intros c. destruct c; reflexivity. Qed.

Lemma class_eqb_true : forall c d : MemClass, class_eqb c d = true -> c = d.
Proof.
  intros c d. destruct c; destruct d; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition kind_eqb (k j : RegionKind) : bool :=
  match k, j with
  | ScalarWorkingSet, ScalarWorkingSet => true
  | CycleCriticalArray, CycleCriticalArray => true
  | KernelObjects, KernelObjects => true
  | Stacks, Stacks => true
  | RegisterSaveAreas, RegisterSaveAreas => true
  | DmaWindows, DmaWindows => true
  | Rings, Rings => true
  | GrantSlots, GrantSlots => true
  | QuarantineEntries, QuarantineEntries => true
  | RecoveryWorkspaces, RecoveryWorkspaces => true
  | ServerScalarWorkingSets, ServerScalarWorkingSets => true
  | HardTaskAndHotCode, HardTaskAndHotCode => true
  | BulkByVolume, BulkByVolume => true
  | Framebuffers, Framebuffers => true
  | Images, Images => true
  | VectorAndMatrixExtents, VectorAndMatrixExtents => true
  | InterpreterObjectArenas, InterpreterObjectArenas => true
  | MediaBuffers, MediaBuffers => true
  | ColdStaticallyPlacedCode, ColdStaticallyPlacedCode => true
  | ModelWeights, ModelWeights => true
  | InterpreterBody, InterpreterBody => true
  | ApplicationPayload, ApplicationPayload => true
  | _, _ => false
  end.

Lemma kind_eqb_refl : forall k : RegionKind, kind_eqb k k = true.
Proof. intros k. destruct k; reflexivity. Qed.

Lemma kind_eqb_true : forall k j : RegionKind, kind_eqb k j = true -> k = j.
Proof.
  intros k j. destruct k; destruct j; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

(* The counts, checked by conversion rather than claimed, each one a count
   the entry cited beside it closes outright in its own words. The day an
   entry moves a term across the boundary is the day one of them stops
   holding. There is deliberately no count over `all_kinds`: no entry
   closes that enumeration (gap a). *)
Example there_are_two_latency_classes : count_of all_classes = 2 := eq_refl.

Example the_first_list_names_twelve_kinds : count_of first_class_list = 12 := eq_refl.

Example the_second_list_names_eight_kinds : count_of second_class_list = 8 := eq_refl.

Example the_two_lists_name_twenty_kinds : count_of listed_kinds = 20 := eq_refl.

Example the_entries_place_twenty_one_kinds_by_name :
  count_of named_kinds = 21 := eq_refl.

(* The partition itself, computed rather than described: each of
   R-15-247s's two lists carries exactly the class that entry puts it on,
   read from the entry's own two lists and from no table over them. *)
Example the_first_list_is_all_first_class :
  all_of (fun k => match placed_by_name k with
                   | Some c => class_eqb c FirstClass
                   | None => false
                   end) first_class_list = true := eq_refl.

Example the_second_list_is_all_second_class :
  all_of (fun k => match placed_by_name k with
                   | Some c => class_eqb c SecondClass
                   | None => false
                   end) second_class_list = true := eq_refl.

(* The three placements the register makes by name outside R-15-247s's own
   two lists, so that a rewrite of any one of the three moves a conversion
   here rather than passing silently. *)
Example the_three_placements_named_by_their_own_entries :
  placed_by_name HardTaskAndHotCode = Some FirstClass
  /\ placed_by_name InterpreterObjectArenas = Some SecondClass
  /\ placed_by_name InterpreterBody = Some FirstClass :=
  conj eq_refl (conj eq_refl eq_refl).

(* Reading 5 as a computation rather than a remark: the kind R-14-015 places
   is the one the two lists do not carry, and the term R-08-045's charge
   names as the arenas is in the second list, so the criterion's closure
   clause reaches the arenas and not the body. *)
Example the_interpreter_body_is_in_neither_list :
  any_of (fun k => kind_eqb k InterpreterBody) listed_kinds = false
  /\ any_of (fun k => kind_eqb k InterpreterBody) named_kinds = true
  /\ any_of (fun k => kind_eqb k InterpreterObjectArenas) listed_kinds = true :=
  conj eq_refl (conj eq_refl eq_refl).

(* And reading 4's other half: the one term neither list names is the one
   the register places by criterion, and it is the only such term here. *)
Example one_kind_is_placed_by_criterion_and_not_by_name :
  any_of (fun k => kind_eqb k ApplicationPayload) named_kinds = false
  /\ count_of (filter_of (fun k => match placed_by_name k with
                                   | Some _ => false | None => true end)
                         all_kinds) = 1 := conj eq_refl eq_refl.

(* The entry's own sentence about where the criterion sends each half,
   taken as a conversion: a payload's cycle-critical part is carried by the
   kinds the first list opens with and its bulk by the kind the second opens
   with, so the criterion's two answers are those carriers' own classes. *)
Example the_criterion_agrees_with_the_carriers_the_entry_names :
  placed_by_name ScalarWorkingSet = Some (criterion_class true)
  /\ placed_by_name CycleCriticalArray = Some (criterion_class true)
  /\ placed_by_name BulkByVolume = Some (criterion_class false) :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   The plan: everything the register leaves to composition. Fields rather
   than Parameters, because a top-level Parameter prints as an assumption
   and fails the R-05-163 gate.
   ========================================================================= *)

Record Plan : Type := {

  (* --- R-08-011's roster of placed regions. A region is an index below
         this count, the whole-program plan fixing the roster at
         composition exactly as it fixes each slot ------------------------ *)

  region_count : nat;
  kind_of : nat -> RegionKind;
  cycle_critical : nat -> bool; (* R-15-247s's criterion, per region
                                   (reading 4): the judgment M1.9 reads
                                   rather than assumes                     *)
  class_of : nat -> MemClass;   (* the plan's own assignment (reading 4)   *)

  (* --- R-08-011's slot assignment and R-08-012's live-range colouring:
         a base, a length, and the interval R-08-014's side condition is
         stated over (gap e) ---------------------------------------------- *)

  base_of : nat -> nat;
  length_of : nat -> nat;
  live_from : nat -> nat;
  live_to : nat -> nat;

  (* --- R-15-007k's quantization, checked against the counts the plan
         declares (reading 8). The granule itself is not here: R-15-007c
         fixes it as a function of the object's length ------------------- *)

  base_granules : nat -> nat;
  length_granules_of : nat -> nat;

  (* --- R-08-012c's island containment, read from the bank/macro/tier to
         island map the plan consumes and never writes ------------------- *)

  island_of : nat -> nat;
  island_base : nat -> nat;
  island_span : nat -> nat;

  (* --- R-15-247's two per-class constants, each entering section 11 as
         one fixed latency constant, R-11-015's derived count of fetches a
         region's code costs, and the frame slot the region's code runs in,
         which is the slot its delta is charged to (readings 1 and 2) ----- *)

  first_fetch : nat;
  second_fetch : nat;
  fetch_count : nat -> nat;
  slot_of : nat -> nat;

  (* --- the plan's own placement list, which is what R-08-045's charge is
         read over: every region claimed by one line item and nothing
         claimed that the roster does not carry --------------------------- *)

  placed : list nat;

  (* --- R-14-009's pool of P identical origin compartments, R-14-010's
         ceiling over it, and R-18-004b's first-class budget the ceiling is
         scored against (gap d) ------------------------------------------- *)

  origin_regions : list nat;
  fixed_first_class : nat;
  first_budget : nat
}.

(* =========================================================================
   The class assignment (R-15-247, R-15-247j, R-14-015, R-15-247s).

   An assignment is stated as an arbitrary function from a region to a
   class, so a plan that places a region on the wrong class is expressible
   and the theorems below have something to exclude. What the register
   places by name it places by name, and what it answers by criterion the
   plan's own cycle-criticality judgment decides (reading 4).
   ========================================================================= *)

Definition Assignment : Type := nat -> MemClass.

Definition register_place (p : Plan) (r : nat) : MemClass :=
  match placed_by_name (p.(kind_of) r) with
  | Some c => c
  | None => criterion_class (p.(cycle_critical) r)
  end.

Definition spec_assign (p : Plan) : Assignment := register_place p.

Definition places_ok (p : Plan) (a : Assignment) : bool :=
  all_of (fun r => class_eqb (a r) (register_place p r)) (upto p.(region_count)).

Definition PlacesAsTheRegisterPlaces (p : Plan) (a : Assignment) : Prop :=
  forall r : nat, Nat.ltb r p.(region_count) = true -> a r = register_place p r.

Lemma places_ok_sound :
  forall (p : Plan) (a : Assignment),
    places_ok p a = true -> PlacesAsTheRegisterPlaces p a.
Proof.
  intros p a H r Hr. unfold places_ok in H.
  exact (class_eqb_true _ _
           (all_of_upto (fun s => class_eqb (a s) (register_place p s))
                        p.(region_count) r H Hr)).
Qed.

(* S1 (R-15-247's placement discipline, R-15-247s's two lists and its
   criterion): the specification's assignment is the register's own
   placement read off each region's kind where the register names it and
   off the plan's cycle-criticality judgment where it does not, stated of
   an arbitrary plan rather than computed over a demo one. *)
Theorem the_specification_places_as_the_register_places :
  forall p : Plan, PlacesAsTheRegisterPlaces p (spec_assign p).
Proof. intros p r _. reflexivity. Qed.

Theorem the_specification_assignment_passes_the_check :
  forall p : Plan, places_ok p (spec_assign p) = true.
Proof.
  intros p. unfold places_ok, spec_assign.
  apply all_of_const. intros r. apply class_eqb_refl.
Qed.

(* -------------------------------------------------------------------------
   The placements the register makes by name, stated apart from the whole
   assignment and apart from each other. They are separate obligations and
   not one stated three times: each is broken below by a construction that
   satisfies the others, and the whole assignment is broken by a
   construction that satisfies all of them.
   ------------------------------------------------------------------------- *)

Definition PlacesKindOn (p : Plan) (a : Assignment) (k : RegionKind)
                        (c : MemClass) : Prop :=
  forall r : nat,
    Nat.ltb r p.(region_count) = true ->
    kind_eqb (p.(kind_of) r) k = true -> a r = c.

(* R-15-247j: all section 11 hard-task code and all hot code on the first
   class. *)
Definition HardTaskCodeIsFirstClass (p : Plan) (a : Assignment) : Prop :=
  PlacesKindOn p a HardTaskAndHotCode FirstClass.

(* R-14-015: the arenas are second-class regions. *)
Definition ArenasAreSecondClass (p : Plan) (a : Assignment) : Prop :=
  PlacesKindOn p a InterpreterObjectArenas SecondClass.

(* R-14-015: and the interpreter body is first-class. *)
Definition TheInterpreterBodyIsFirstClass (p : Plan) (a : Assignment) : Prop :=
  PlacesKindOn p a InterpreterBody FirstClass.

(* R-15-247s's other half, which is the one M1.9 exists to read rather than
   assume: a term of R-08-045's charge the entry answers without naming is
   placed by criterion, so a region the register does not name lands where
   the composition's cycle-criticality judgment puts it and nowhere else. *)
Definition PlacesPayloadsByTheCriterion (p : Plan) (a : Assignment) : Prop :=
  forall r : nat,
    Nat.ltb r p.(region_count) = true ->
    placed_by_name (p.(kind_of) r) = None ->
    a r = criterion_class (p.(cycle_critical) r).

Lemma whole_placement_gives_each :
  forall (p : Plan) (a : Assignment) (k : RegionKind) (c : MemClass),
    PlacesAsTheRegisterPlaces p a -> placed_by_name k = Some c ->
    PlacesKindOn p a k c.
Proof.
  intros p a k c H Hk r Hr Hj.
  assert (Hi : p.(kind_of) r = k) by exact (kind_eqb_true _ _ Hj).
  rewrite (H r Hr). unfold register_place. rewrite Hi. rewrite Hk. reflexivity.
Qed.

(* S1a, S1b and S1c (R-15-247j, R-14-015): each of the three by-name
   placements follows from the whole assignment, and each is stated so that
   a construction breaking it alone can be exhibited. *)
Theorem the_specification_places_hard_task_code_first :
  forall p : Plan, HardTaskCodeIsFirstClass p (spec_assign p).
Proof.
  intros p. exact (whole_placement_gives_each p (spec_assign p) HardTaskAndHotCode
                     FirstClass (the_specification_places_as_the_register_places p)
                     eq_refl).
Qed.

Theorem the_specification_places_the_arenas_second :
  forall p : Plan, ArenasAreSecondClass p (spec_assign p).
Proof.
  intros p. exact (whole_placement_gives_each p (spec_assign p)
                     InterpreterObjectArenas SecondClass
                     (the_specification_places_as_the_register_places p) eq_refl).
Qed.

Theorem the_specification_places_the_interpreter_body_first :
  forall p : Plan, TheInterpreterBodyIsFirstClass p (spec_assign p).
Proof.
  intros p. exact (whole_placement_gives_each p (spec_assign p) InterpreterBody
                     FirstClass (the_specification_places_as_the_register_places p)
                     eq_refl).
Qed.

(* S1d (R-15-247s's criterion clause): and the placement the register makes
   by criterion, stated of an arbitrary plan. *)
Theorem the_specification_places_payloads_by_the_criterion :
  forall p : Plan, PlacesPayloadsByTheCriterion p (spec_assign p).
Proof.
  intros p r _ H. unfold spec_assign, register_place. rewrite H. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   The mutations of an assignment a refutation needs, generated from a kind
   rather than authored per construction: everything the register places is
   placed as the register places it, except the one kind named, which is
   moved.
   ------------------------------------------------------------------------- *)

Definition demote (k : RegionKind) (p : Plan) : Assignment := fun r =>
  if kind_eqb (p.(kind_of) r) k then SecondClass else register_place p r.

Definition promote (k : RegionKind) (p : Plan) : Assignment := fun r =>
  if kind_eqb (p.(kind_of) r) k then FirstClass else register_place p r.

(* And the twins, stated of an arbitrary plan: moving one kind leaves every
   other by-name placement standing. *)
Lemma demote_keeps_other_placements :
  forall (p : Plan) (k j : RegionKind) (c : MemClass),
    kind_eqb j k = false -> placed_by_name j = Some c ->
    PlacesKindOn p (demote k p) j c.
Proof.
  intros p k j c Hjk Hj r _ Hr.
  assert (Hi : p.(kind_of) r = j) by exact (kind_eqb_true _ _ Hr).
  unfold demote. rewrite Hi. rewrite Hjk. unfold register_place.
  rewrite Hi. rewrite Hj. reflexivity.
Qed.

Lemma promote_keeps_other_placements :
  forall (p : Plan) (k j : RegionKind) (c : MemClass),
    kind_eqb j k = false -> placed_by_name j = Some c ->
    PlacesKindOn p (promote k p) j c.
Proof.
  intros p k j c Hjk Hj r _ Hr.
  assert (Hi : p.(kind_of) r = j) by exact (kind_eqb_true _ _ Hr).
  unfold promote. rewrite Hi. rewrite Hjk. unfold register_place.
  rewrite Hi. rewrite Hj. reflexivity.
Qed.

(* The construction R-15-247s excludes by name, and it is the one this file
   would ship if `cycle_critical` were a constructor rather than a judgment:
   a placement that reads the payload's name and puts every payload on one
   class whatever the criterion says. Ownership is no part of a latency
   criterion, and a placement by name is exactly the ownership reading. *)
Definition by_name_payload_assign (c : MemClass) (p : Plan) : Assignment := fun r =>
  match placed_by_name (p.(kind_of) r) with
  | Some d => d
  | None => c
  end.

(* Its twin: it agrees with the register on every kind the register names,
   so what refutes it is the criterion and not a mis-placement. *)
Theorem the_by_name_payload_placement_keeps_every_named_placement :
  forall (c : MemClass) (p : Plan) (k : RegionKind) (d : MemClass),
    placed_by_name k = Some d -> PlacesKindOn p (by_name_payload_assign c p) k d.
Proof.
  intros c p k d Hk r _ Hr.
  assert (Hi : p.(kind_of) r = k) by exact (kind_eqb_true _ _ Hr).
  unfold by_name_payload_assign. rewrite Hi. rewrite Hk. reflexivity.
Qed.

(* =========================================================================
   The class is decided once, at composition (R-15-247, R-15-247r).

   A placer is stated over an arbitrary runtime observation and required
   not to vary with it, which is "no cache, no migration, no tiering, no
   wake-on-access and no runtime promotion" as a property rather than as an
   absence. R-15-247r names the temptation and this is it excluded.
   ========================================================================= *)

Definition Observation : Type := nat -> nat.

Definition Placer : Type := Observation -> Assignment.

Definition spec_placer (p : Plan) : Placer := fun _ => spec_assign p.

Definition DecidedOnceAtComposition (pl : Placer) : Prop :=
  forall (o1 o2 : Observation) (r : nat), pl o1 r = pl o2 r.

(* S2 (R-15-247's own criterion: no instruction, no fault and no power
   transition moves a region across the boundary). *)
Theorem the_specification_placer_is_decided_once :
  forall p : Plan, DecidedOnceAtComposition (spec_placer p).
Proof. intros p o1 o2 r. reflexivity. Qed.

(* The two constructions R-15-247 excludes, in each direction. The
   threshold is a parameter rather than a literal: a construction the
   register refuses still may not carry a magnitude this file invented. *)
Definition promoting_placer (p : Plan) (threshold : nat) : Placer := fun o r =>
  if Nat.ltb threshold (o r) then FirstClass else spec_assign p r.

Definition demoting_placer (p : Plan) (threshold : nat) : Placer := fun o r =>
  if Nat.ltb threshold (o r) then SecondClass else spec_assign p r.

(* =========================================================================
   The fetch constant and the placement delta (R-15-247j, R-15-247,
   R-15-164, R-11-015).

   Reading 1: with every cache deleted there is no instruction cache and
   nothing to amortize, so a fetch is a read of whichever class the code
   resides on, which is what M0.14's landed cell records as "no separate
   fetch constant to declare". Reading 2: what the placement multiplies is
   the count of fetches R-11-015's max-path sum already carries, so the
   delta is a product and not a per-region constant.
   ========================================================================= *)

Definition fetch_constant (p : Plan) (c : MemClass) : nat :=
  match c with
  | FirstClass => p.(first_fetch)
  | SecondClass => p.(second_fetch)
  end.

Lemma fetch_constant_first :
  forall p : Plan, fetch_constant p FirstClass = p.(first_fetch).
Proof. intros p. reflexivity. Qed.

Lemma fetch_constant_second :
  forall p : Plan, fetch_constant p SecondClass = p.(second_fetch).
Proof. intros p. reflexivity. Qed.

(* R-15-247j's delta: what a region's placement costs over what the same
   code would cost on the first class. Reading 3: the difference truncates,
   so a composition declaring a faster second class carries no credit. *)
Definition placement_delta (p : Plan) (a : Assignment) (r : nat) : nat :=
  p.(fetch_count) r * (fetch_constant p (a r) - p.(first_fetch)).

Definition per_fetch_delta (p : Plan) (a : Assignment) (r : nat) : nat :=
  fetch_constant p (a r) - p.(first_fetch).

(* The declared side condition reading 3 names, stated of a plan rather
   than assumed of the machine, beside what it buys: under it the delta is
   faithful rather than truncated, the first-class constant plus the
   per-fetch delta being exactly the constant of the class the region sits
   on. Both are properties of an arbitrary plan, and a plan breaking the
   first and exhibiting the truncation that follows is below. *)
Definition SecondClassIsNoFaster (p : Plan) : Prop :=
  Nat.leb p.(first_fetch) p.(second_fetch) = true.

Definition DeltaIsFaithful (p : Plan) : Prop :=
  forall (a : Assignment) (r : nat),
    p.(first_fetch) + per_fetch_delta p a r = fetch_constant p (a r).

Theorem the_delta_is_faithful_under_the_side_condition :
  forall p : Plan, SecondClassIsNoFaster p -> DeltaIsFaithful p.
Proof.
  intros p H a r. unfold per_fetch_delta. destruct (a r).
  - rewrite (fetch_constant_first p). apply add_sub_cancel. apply leb_refl.
  - rewrite (fetch_constant_second p). apply add_sub_cancel. exact H.
Qed.

(* And the delta is that per-fetch quantity taken as many times as R-11-015's
   derivation counts a fetch (reading 2), stated as an identity so the two
   halves cannot drift. *)
Theorem the_delta_is_the_count_times_the_per_fetch_delta :
  forall (p : Plan) (a : Assignment) (r : nat),
    placement_delta p a r = p.(fetch_count) r * per_fetch_delta p a r.
Proof. intros p a r. reflexivity. Qed.

(* S3a (R-15-247j): first-class placement carries no delta at all, which is
   why the rule prices second-class code and says nothing about the first. *)
Theorem the_first_class_carries_no_delta :
  forall (p : Plan) (a : Assignment) (r : nat),
    a r = FirstClass -> placement_delta p a r = 0.
Proof.
  intros p a r H. unfold placement_delta. rewrite H.
  rewrite (fetch_constant_first p). rewrite (sub_diag p.(first_fetch)).
  apply mul_0_r.
Qed.

(* S3b (R-15-247s): the boundary is latency-criticality and nothing else,
   so a composition whose two constants coincide carries no delta whatever
   the placement. What separates the classes in this arithmetic is the pair
   of constants and never the class's name. *)
Theorem equal_constants_carry_no_delta :
  forall (p : Plan) (a : Assignment) (r : nat),
    p.(second_fetch) = p.(first_fetch) -> placement_delta p a r = 0.
Proof.
  intros p a r H. unfold placement_delta.
  assert (Hc : fetch_constant p (a r) - p.(first_fetch) = 0).
  { destruct (a r).
    - rewrite (fetch_constant_first p). apply sub_diag.
    - rewrite (fetch_constant_second p). rewrite H. apply sub_diag. }
  rewrite Hc. apply mul_0_r.
Qed.

(* S3c (R-15-247j, R-11-015): the delta reads the placement and the count
   and nothing else, so two plans agreeing on the two class constants and
   on a region's fetch count charge that region alike under one
   assignment. Stated over an arbitrary delta, which is what makes the
   construction below a refutation rather than a remark. *)
Definition Delta : Type := Plan -> Assignment -> nat -> nat.

Definition DeltaReadsThePlacementAlone (d : Delta) : Prop :=
  forall (p q : Plan) (a b : Assignment) (r : nat),
    p.(first_fetch) = q.(first_fetch) ->
    p.(second_fetch) = q.(second_fetch) ->
    p.(fetch_count) r = q.(fetch_count) r ->
    a r = b r ->
    d p a r = d q b r.

Theorem the_placement_delta_reads_the_placement_alone :
  DeltaReadsThePlacementAlone placement_delta.
Proof.
  intros p q a b r H1 H2 H3 H4. unfold placement_delta.
  rewrite H3. rewrite H4. destruct (b r).
  - rewrite (fetch_constant_first p). rewrite (fetch_constant_first q).
    rewrite H1. reflexivity.
  - rewrite (fetch_constant_second p). rewrite (fetch_constant_second q).
    rewrite H1. rewrite H2. reflexivity.
Qed.

(* The construction R-11-015 excludes, and it is the tempting one: a delta
   priced by the region's bytes rather than by the fetches the derivation
   counts. R-11-015 derives a bound as a max-path sum over the typed
   control-flow graph, so a byte-priced placement reads a quantity that
   derivation does not carry. *)
Definition length_scaled_delta : Delta := fun p a r =>
  p.(length_of) r * (fetch_constant p (a r) - p.(first_fetch)).

(* Its twins: it still charges nothing on the first class and nothing where
   the two constants coincide, so what refutes it is the quantity it reads
   and not a different arithmetic. *)
Theorem the_length_scaled_delta_charges_nothing_on_the_first_class :
  forall (p : Plan) (a : Assignment) (r : nat),
    a r = FirstClass -> length_scaled_delta p a r = 0.
Proof.
  intros p a r H. unfold length_scaled_delta. rewrite H.
  rewrite (fetch_constant_first p). rewrite (sub_diag p.(first_fetch)).
  apply mul_0_r.
Qed.

Theorem the_length_scaled_delta_charges_nothing_where_the_constants_agree :
  forall (p : Plan) (a : Assignment) (r : nat),
    p.(second_fetch) = p.(first_fetch) -> length_scaled_delta p a r = 0.
Proof.
  intros p a r H. unfold length_scaled_delta.
  assert (Hc : fetch_constant p (a r) - p.(first_fetch) = 0).
  { destruct (a r).
    - rewrite (fetch_constant_first p). apply sub_diag.
    - rewrite (fetch_constant_second p). rewrite H. apply sub_diag. }
  rewrite Hc. apply mul_0_r.
Qed.

(* =========================================================================
   The join: the delta as an input to section 11 admission (R-15-247j's
   acceptance clause, R-11-006, R-11-009).

   Charging a region's delta into the declared bound of the slot that
   region's code runs in is what makes the delta an input rather than a
   report: the check it enters is the interval arithmetic
   CyclicExecutive.v states, with R-11-009's partition-switch constant
   already inside it, so one unit more of delta moves `admits`. Which slot
   is a field, so a frame's reserved band is chargeable and not only its
   discretionary focus, and a construction that charges the focus whatever
   the region declares is refuted below.
   ========================================================================= *)

Definition charge_slot {T : Type} (d : nat) (s : Slot T) : Slot T :=
  Build_Slot T (slot_width s) (slot_offset s) (slot_bound s + d) (slot_period s)
             (slot_tenant s).

(* The structural argument is the list and not the index, which decides
   what charging past the end of a band does: it is the identity, so a
   slot index the frame does not carry absorbs the whole delta and the
   frame is admitted exactly as it would have been with no delta at all.
   That is a consequence and not a convenience. It is stated as one below
   (`a_slot_the_frame_does_not_carry_absorbs_the_whole_delta`), which is
   why the plan's slot index carries an obligation of its own (reading 11)
   rather than being a field a composition may declare freely: without it
   a plan opts out of R-15-247j's acceptance clause by declaring a number.
   The plan that does exactly that is refuted below. *)
Fixpoint charge_nth {T : Type} (i d : nat) (l : list (Slot T))
                    {struct l} : list (Slot T) :=
  match l with
  | nil => nil
  | cons s r =>
      match i with
      | 0 => cons (charge_slot d s) r
      | S k => cons s (charge_nth k d r)
      end
  end.

Definition charge_band_at {T : Type} (i d : nat) (b : Band T) : Band T :=
  match i with
  | 0 => Build_Band T (charge_slot d (band_focus b)) (band_background b)
  | S k => Build_Band T (band_focus b) (charge_nth k d (band_background b))
  end.

Definition charge_frame_at {T : Type} (i d : nat) (f : Frame T) : Frame T :=
  if Nat.ltb i (count_of (reserved_band f))
  then Build_Frame T (major_frame f) (phase_offset f)
         (charge_nth i d (reserved_band f)) (discretionary_band f)
  else Build_Frame T (major_frame f) (phase_offset f) (reserved_band f)
         (charge_band_at (i - count_of (reserved_band f)) d
                         (discretionary_band f)).

Lemma charge_nth_app_lt :
  forall (T : Type) (i d : nat) (l1 l2 : list (Slot T)),
    Nat.ltb i (count_of l1) = true ->
    charge_nth i d (app l1 l2) = app (charge_nth i d l1) l2.
Proof.
  intros T i d l1. revert i. induction l1 as [ | x r IH ]; intros i l2 H.
  - discriminate H.
  - destruct i as [ | k ].
    + reflexivity.
    + simpl in H. simpl. rewrite (IH k l2 H). reflexivity.
Qed.

Lemma charge_nth_app_ge :
  forall (T : Type) (i d : nat) (l1 l2 : list (Slot T)),
    Nat.ltb i (count_of l1) = false ->
    charge_nth i d (app l1 l2) = app l1 (charge_nth (i - count_of l1) d l2).
Proof.
  intros T i d l1. revert i. induction l1 as [ | x r IH ]; intros i l2 H.
  - simpl. rewrite (sub_0_r i). reflexivity.
  - destruct i as [ | k ].
    + discriminate H.
    + simpl in H. simpl. rewrite (IH k l2 H). reflexivity.
Qed.

Lemma band_slots_charge_at :
  forall (T : Type) (i d : nat) (b : Band T),
    band_slots (charge_band_at i d b) = charge_nth i d (band_slots b).
Proof. intros T i d b. destruct i as [ | k ]; reflexivity. Qed.

Lemma major_frame_charge_at :
  forall (T : Type) (i d : nat) (f : Frame T),
    major_frame (charge_frame_at i d f) = major_frame f.
Proof.
  intros T i d f. unfold charge_frame_at.
  destruct (Nat.ltb i (count_of (reserved_band f))); reflexivity.
Qed.

Lemma frame_slots_charge_at :
  forall (T : Type) (i d : nat) (f : Frame T),
    frame_slots (charge_frame_at i d f) = charge_nth i d (frame_slots f).
Proof.
  intros T i d f. unfold charge_frame_at, frame_slots.
  destruct (Nat.ltb i (count_of (reserved_band f))) eqn:E.
  - exact (eq_sym (charge_nth_app_lt T i d (reserved_band f)
             (band_slots (discretionary_band f)) E)).
  - rewrite (charge_nth_app_ge T i d (reserved_band f)
               (band_slots (discretionary_band f)) E).
    exact (f_equal (app (reserved_band f))
             (band_slots_charge_at T (i - count_of (reserved_band f)) d
                (discretionary_band f))).
Qed.

(* Charging past the last slot the frame carries, which is the identity:
   the delta lands nowhere and the frame is the frame. What makes this a
   hole rather than a convenience is that `slot_of` is the plan's own
   field, so a plan declaring a number no frame answers to is a plan whose
   delta is not an input to admission at all. *)
Lemma charge_nth_past_the_end :
  forall (T : Type) (i d : nat) (l : list (Slot T)),
    Nat.leb (count_of l) i = true -> charge_nth i d l = l.
Proof.
  intros T i d l. revert i. induction l as [ | x r IH ]; intros i H.
  - reflexivity.
  - destruct i as [ | k ]; [ discriminate H | ].
    simpl in H. simpl. rewrite (IH k H). reflexivity.
Qed.

Lemma charge_band_past_the_end :
  forall (T : Type) (i d : nat) (b : Band T),
    Nat.leb (count_of (band_slots b)) i = true -> charge_band_at i d b = b.
Proof.
  intros T i d b H. destruct b as [ fo bg ]. simpl in H.
  destruct i as [ | k ]; simpl in H.
  - discriminate H.
  - simpl. rewrite (charge_nth_past_the_end T k d bg H). reflexivity.
Qed.

Lemma charge_frame_past_the_end :
  forall (T : Type) (i d : nat) (f : Frame T),
    Nat.leb (count_of (frame_slots f)) i = true -> charge_frame_at i d f = f.
Proof.
  intros T i d f H. unfold frame_slots in H.
  rewrite (count_of_app (Slot T) (reserved_band f)
             (band_slots (discretionary_band f))) in H.
  unfold charge_frame_at.
  destruct (Nat.ltb i (count_of (reserved_band f))) eqn:E.
  - assert (Hc : Nat.leb (count_of (reserved_band f)) i = true)
      by exact (leb_trans (count_of (reserved_band f))
                  (count_of (reserved_band f)
                   + count_of (band_slots (discretionary_band f))) i
                  (leb_add_l (count_of (reserved_band f))
                     (count_of (band_slots (discretionary_band f)))) H).
    rewrite (ltb_leb_false _ _ E) in Hc. discriminate Hc.
  - rewrite (charge_band_past_the_end T (i - count_of (reserved_band f)) d
               (discretionary_band f)
               (leb_sub_of_add (count_of (reserved_band f))
                  (count_of (band_slots (discretionary_band f))) i H)).
    destruct f as [ mf po rb db ]. reflexivity.
Qed.

(* The delta enters the bound and never the layout: charging moves no
   offset and no width, so R-15-247j's WCET delta cannot turn an admitted
   frame into an overlapping one and the only clause it can move is the one
   R-11-006 states over widths. *)
Lemma disjoint_from_charge_head :
  forall (T : Type) (d : nat) (s : Slot T) (l : list (Slot T)),
    disjoint_from (charge_slot d s) l = disjoint_from s l.
Proof.
  intros T d s l. induction l as [ | t r IH ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

Lemma disjoint_from_charge_nth :
  forall (T : Type) (i d : nat) (s : Slot T) (l : list (Slot T)),
    disjoint_from s (charge_nth i d l) = disjoint_from s l.
Proof.
  intros T i d s l. revert i. induction l as [ | x r IH ]; intros i.
  - reflexivity.
  - destruct i as [ | k ].
    + reflexivity.
    + simpl. rewrite (IH k). reflexivity.
Qed.

Lemma pairwise_disjoint_charge_nth :
  forall (T : Type) (i d : nat) (l : list (Slot T)),
    pairwise_disjoint (charge_nth i d l) = pairwise_disjoint l.
Proof.
  intros T i d l. revert i. induction l as [ | x r IH ]; intros i.
  - reflexivity.
  - destruct i as [ | k ]; simpl.
    + rewrite (disjoint_from_charge_head T d x r). reflexivity.
    + rewrite (disjoint_from_charge_nth T k d x r). rewrite (IH k). reflexivity.
Qed.

(* S4a (R-15-247j, R-11-006): the delta is a bound and not a relayout, at
   whichever slot it is charged to. *)
Theorem charging_moves_no_offset_and_no_width :
  forall (T : Type) (i d : nat) (f : Frame T),
    pairwise_disjoint (frame_slots (charge_frame_at i d f))
    = pairwise_disjoint (frame_slots f).
Proof.
  intros T i d f. rewrite (frame_slots_charge_at T i d f).
  exact (pairwise_disjoint_charge_nth T i d (frame_slots f)).
Qed.

(* An admission is stated over an arbitrary composition, plan, assignment,
   region and frame, so a check that reports the delta beside its verdict
   rather than consuming it, and a check that charges it to the wrong slot,
   are both expressible. *)
Definition Admission : Type :=
  forall c : Composition, Plan -> Assignment -> nat -> Frame (Tenant c) -> bool.

Definition spec_admission : Admission := fun c p a r f =>
  admits c (charge_frame_at (p.(slot_of) r) (placement_delta p a r) f).

(* R-15-247j's own words read the other way: the delta computed, published
   beside the schedule, and not consumed. It is the construction that
   entry's acceptance clause excludes by name. *)
Definition reporting_admission : Admission := fun c _ _ _ f => admits c f.

(* And the construction that consumes the delta but charges it to a slot
   the region does not run in: the discretionary focus, whatever the plan
   declares. A frame's reserved band is where R-11-020 puts the identical
   band every rung shares, so a hard-task slot that lives there can never
   be charged at all under this reading. *)
Definition focus_charging_admission : Admission := fun c p a r f =>
  admits c (charge_frame_at (count_of (reserved_band f))
              (placement_delta p a r) f).

Definition CountsTheDelta (adm : Admission) : Prop :=
  forall (c : Composition) (p : Plan) (a : Assignment) (r : nat)
         (f : Frame (Tenant c)),
    admits c (charge_frame_at (p.(slot_of) r) (placement_delta p a r) f) = false ->
    adm c p a r f = false.

Definition ChargesTheRegionSOwnSlot (adm : Admission) : Prop :=
  forall (c : Composition) (p : Plan) (a : Assignment) (r : nat)
         (f : Frame (Tenant c)),
    adm c p a r f
    = admits c (charge_frame_at (p.(slot_of) r) (placement_delta p a r) f).

(* S4b (R-15-247j): the specification's admission refuses whatever the
   charged arithmetic refuses, which is the acceptance clause's "an input
   to section 11 admission rather than a report about it" as a property. *)
Theorem the_specification_admission_counts_the_delta :
  CountsTheDelta spec_admission.
Proof. intros c p a r f H. exact H. Qed.

(* S4d (R-15-247j, R-11-020): and it is the check that charges the slot the
   region's code runs in, which is what ties a region index to a bound
   rather than to whichever slot the frame happens to open with. What the
   property decides is pointwise agreement with that check and not the slot
   alone, so it excludes every admission differing from it anywhere,
   `brittle_admission` included (limit i); what isolates the slot is the
   pair of witnesses beside the refutation below, which read one plan at
   the region's own slot and at the frame's focus. *)
Theorem the_specification_admission_charges_the_region_s_own_slot :
  ChargesTheRegionSOwnSlot spec_admission.
Proof. intros c p a r f. reflexivity. Qed.

(* -------------------------------------------------------------------------
   Reading 11: which slot indices a plan may declare, and what happens where
   it declares one the frame does not carry.

   R-15-247j's acceptance clause makes the delta an input to section 11
   admission, and the arithmetic it is an input to is stated over the
   frame's own slot list. Charging past the end of that list is the
   identity, so a plan declaring an index past it is admitted exactly as
   the uncharged frame is: the delta is computed, lands nowhere, and the
   acceptance clause is opted out of by a self-declared number. The range
   is the frame's rather than the plan's, so the obligation is stated of a
   plan against a frame and is conjoined with R-08-045's charge below.
   ------------------------------------------------------------------------- *)

Definition slot_indices_held {T : Type} (p : Plan) (f : Frame T) : bool :=
  all_of (fun r => Nat.ltb (p.(slot_of) r) (count_of (frame_slots f)))
         (upto p.(region_count)).

Definition ChargesOnlySlotsTheFrameHolds {T : Type} (p : Plan)
                                         (f : Frame T) : Prop :=
  forall r : nat,
    Nat.ltb r p.(region_count) = true ->
    Nat.ltb (p.(slot_of) r) (count_of (frame_slots f)) = true.

Lemma slot_indices_held_sound :
  forall (T : Type) (p : Plan) (f : Frame T),
    slot_indices_held p f = true -> ChargesOnlySlotsTheFrameHolds p f.
Proof.
  intros T p f H r Hr. unfold slot_indices_held in H.
  exact (all_of_upto _ p.(region_count) r H Hr).
Qed.

Lemma slot_indices_held_complete :
  forall (T : Type) (p : Plan) (f : Frame T),
    ChargesOnlySlotsTheFrameHolds p f -> slot_indices_held p f = true.
Proof.
  intros T p f H. unfold slot_indices_held. apply all_of_upto_intro. exact H.
Qed.

(* S4e (R-15-247j's acceptance clause): the consequence stated, which is
   what makes the obligation above an obligation and not a tidiness. At a
   slot index the frame does not carry, the specification's own admission
   is the uncharged verdict whatever the delta, so one unit more of delta
   moves nothing and the input stops being an input. *)
Theorem a_slot_the_frame_does_not_carry_absorbs_the_whole_delta :
  forall (c : Composition) (p : Plan) (a : Assignment) (r : nat)
         (f : Frame (Tenant c)),
    Nat.leb (count_of (frame_slots f)) (p.(slot_of) r) = true ->
    spec_admission c p a r f = admits c f.
Proof.
  intros c p a r f H. unfold spec_admission.
  rewrite (charge_frame_past_the_end (Tenant c) (p.(slot_of) r)
             (placement_delta p a r) f H).
  reflexivity.
Qed.

(* And the general reason a reporting admission cannot count: it is a
   function of the frame alone, so it cannot depend on the plan at all.
   Stated over an arbitrary composition, plan and assignment, which is what
   makes the refutation below a witness rather than the whole content. *)
Definition IgnoresThePlan (adm : Admission) : Prop :=
  forall (c : Composition) (p q : Plan) (a b : Assignment) (r s : nat)
         (f : Frame (Tenant c)),
    adm c p a r f = adm c q b s f.

Theorem the_reporting_admission_ignores_the_plan :
  IgnoresThePlan reporting_admission.
Proof. intros c p q a b r s f. reflexivity. Qed.

(* The focus-charging construction's twin: wherever the plan does charge
   the region to the frame's focus, the two agree, so what refutes it is
   the slot it reads and not a different arithmetic. *)
Theorem the_focus_charging_admission_agrees_at_the_focus :
  forall (c : Composition) (p : Plan) (a : Assignment) (r : nat)
         (f : Frame (Tenant c)),
    p.(slot_of) r = count_of (reserved_band f) ->
    focus_charging_admission c p a r f = spec_admission c p a r f.
Proof.
  intros c p a r f H. unfold focus_charging_admission, spec_admission.
  rewrite H. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   The second obligation, and it is a second one: a delta is a cost, so a
   smaller one never refuses more. Counting the delta and being monotone in
   it are separate, which the constructions below make machine-checked
   rather than asserted: the reporting admission is monotone and counts
   nothing, and the brittle one counts the delta and is not monotone.
   ------------------------------------------------------------------------- *)

(* The arithmetic of the bound clause, stated over the partition-switch
   constant as an anonymous term rather than by name: R-11-009's constant is
   PartitionContext.v's and this file consumes the check that carries it
   without restating either. *)
Lemma charged_bound_mono :
  forall b d e sw x : nat,
    Nat.leb d e = true ->
    Nat.leb (b + e + x) sw = true ->
    Nat.leb (b + d + x) sw = true.
Proof.
  intros b d e sw x Hde H.
  apply (leb_trans (b + d + x) (b + e + x) sw); [ | exact H ].
  apply add_le_mono; [ | apply leb_refl ].
  apply add_le_mono; [ apply leb_refl | exact Hde ].
Qed.

Lemma slot_fits_charge_mono :
  forall (c : Composition) (mf d e : nat) (s : Slot (Tenant c)),
    Nat.leb d e = true ->
    slot_fits c mf (charge_slot e s) = true ->
    slot_fits c mf (charge_slot d s) = true.
Proof.
  intros c mf d e s Hde H. unfold slot_fits in H. unfold slot_fits. simpl in H. simpl.
  destruct (andb_split _ _ H) as [ H1 H2 ].
  destruct (andb_split _ _ H2) as [ H3 H4 ].
  apply andb_join; [ exact H1 | ].
  apply andb_join; [ | exact H4 ].
  exact (charged_bound_mono (slot_bound s) d e (slot_width s) _ Hde H3).
Qed.

Lemma all_of_fits_charge_nth_mono :
  forall (c : Composition) (mf i d e : nat) (l : list (Slot (Tenant c))),
    Nat.leb d e = true ->
    all_of (slot_fits c mf) (charge_nth i e l) = true ->
    all_of (slot_fits c mf) (charge_nth i d l) = true.
Proof.
  intros c mf i d e l. revert i. induction l as [ | x r IH ]; intros i Hde H.
  - exact H.
  - destruct i as [ | k ]; simpl in H; simpl;
      destruct (andb_split _ _ H) as [ Hx Hr ].
    + apply andb_join; [ exact (slot_fits_charge_mono c mf d e x Hde Hx) | exact Hr ].
    + apply andb_join; [ exact Hx | exact (IH k Hde Hr) ].
Qed.

(* S4c (R-15-247j): a smaller delta is admitted wherever a larger one is,
   stated of an arbitrary composition, slot index and frame. This is what
   makes the margin below a margin rather than a coincidence. *)
Theorem a_smaller_delta_is_admitted_wherever_a_larger_one_is :
  forall (c : Composition) (i d e : nat) (f : Frame (Tenant c)),
    Nat.leb d e = true ->
    admits c (charge_frame_at i e f) = true ->
    admits c (charge_frame_at i d f) = true.
Proof.
  intros c i d e f Hde H. unfold admits in H. unfold admits.
  rewrite (major_frame_charge_at (Tenant c) i e f) in H.
  rewrite (frame_slots_charge_at (Tenant c) i e f) in H.
  rewrite (major_frame_charge_at (Tenant c) i d f).
  rewrite (frame_slots_charge_at (Tenant c) i d f).
  destruct (andb_split _ _ H) as [ Hfits Hdisj ].
  apply andb_join.
  - exact (all_of_fits_charge_nth_mono c (major_frame f) i d e (frame_slots f)
             Hde Hfits).
  - rewrite (pairwise_disjoint_charge_nth (Tenant c) i d (frame_slots f)).
    rewrite (pairwise_disjoint_charge_nth (Tenant c) i e (frame_slots f)) in Hdisj.
    exact Hdisj.
Qed.

Definition MonotoneInTheDelta (adm : Admission) : Prop :=
  forall (c : Composition) (p : Plan) (a b : Assignment) (r : nat)
         (f : Frame (Tenant c)),
    Nat.leb (placement_delta p a r) (placement_delta p b r) = true ->
    adm c p b r f = true -> adm c p a r f = true.

Theorem the_specification_admission_is_monotone_in_the_delta :
  MonotoneInTheDelta spec_admission.
Proof.
  intros c p a b r f Hle H. unfold spec_admission in H. unfold spec_admission.
  exact (a_smaller_delta_is_admitted_wherever_a_larger_one_is c (p.(slot_of) r)
           (placement_delta p a r) (placement_delta p b r) f Hle H).
Qed.

(* The reporting admission is monotone and counts nothing, so monotonicity
   alone is not the obligation. *)
Theorem the_reporting_admission_is_monotone :
  MonotoneInTheDelta reporting_admission.
Proof. intros c p a b r f _ H. exact H. Qed.

(* And the focus-charging one is monotone too, so what separates it from
   the specification is the slot alone. *)
Theorem the_focus_charging_admission_is_monotone :
  MonotoneInTheDelta focus_charging_admission.
Proof.
  intros c p a b r f Hle H.
  unfold focus_charging_admission in H. unfold focus_charging_admission.
  exact (a_smaller_delta_is_admitted_wherever_a_larger_one_is c
           (count_of (reserved_band f))
           (placement_delta p a r) (placement_delta p b r) f Hle H).
Qed.

(* And a construction that counts the delta and is not monotone: it refuses
   a frame whose delta is zero, which is a first-class placement refused for
   having cost nothing. It satisfies CountsTheDelta because a conjunction
   refuses wherever its first conjunct does. *)
Definition brittle_admission : Admission := fun c p a r f =>
  andb (admits c (charge_frame_at (p.(slot_of) r) (placement_delta p a r) f))
       (Nat.ltb 0 (placement_delta p a r)).

Theorem the_brittle_admission_counts_the_delta :
  CountsTheDelta brittle_admission.
Proof.
  intros c p a r f H. unfold brittle_admission. rewrite H. reflexivity.
Qed.

(* =========================================================================
   Exact representability, discharged against the slot plan (R-15-007k) at
   R-15-007c's granule.

   Reading 8: the granule is not a declaration, and above the threshold it
   is a bound rather than a value. R-15-007c makes bounds byte-exact for
   objects up to 128 bytes at any base and rounds the representable region
   outward above that at a granularity of *at worst* the length over 2^6,
   which bounds the encoding's granule without naming it, and fixes the
   exponent as the field the decoder derives the length mantissa's top bits
   from, which makes every granule the encoding can use a power of two.
   R-15-007k lays each object at *its representable alignment* and at a
   granule-quantized length and constrains a split of an array to that
   array's representable granule, so it is per region and it is the
   coarsest alignment the entry's bound admits: aligning finer than the
   encoding rounds admits a base the encoding cannot represent, and the
   entry states only the worst case, so the worst case is what the plan
   lays to. The quantum is therefore four clauses and not one equation,
   each a check a quantum can fail: byte-exact below the threshold; above
   it, no coarser than the length over 2^6 and coarse enough that doubling
   it would leave that bound; and, at every length, a power of two. What
   the plan declares is the two granule counts, and
   both equations are checks a plan can fail. Reading 9: a narrowable
   subobject's address is a composition-time slot base plus a
   composition-time offset plus a dynamic index times a composition-time
   stride, and its length is its type's.
   ========================================================================= *)

(* The encoding's own exponent, which is what a granule is a power of.
   R-15-007c fixes the exponent as the field that lets the top mantissa be
   stored in six bits and derived into eight, so the granule is 2^e and the
   doubling below is that exponent stepping rather than a magnitude this
   file chose. *)
Fixpoint pow2 (e : nat) : nat :=
  match e with 0 => 1 | S k => 2 * pow2 k end.

Lemma pow2_step : forall e : nat, pow2 (S e) = 2 * pow2 e.
Proof. intros e. reflexivity. Qed.

Lemma mul_two : forall x : nat, 2 * x = x + x.
Proof. intros x. simpl. rewrite (add_0_r x). reflexivity. Qed.

Lemma pow2_pos : forall e : nat, Nat.leb 1 (pow2 e) = true.
Proof.
  intros e. induction e as [ | k IH ].
  - reflexivity.
  - rewrite (pow2_step k).
    exact (leb_trans 1 (pow2 k) (2 * pow2 k) IH (leb_mul_self 2 (pow2 k) eq_refl)).
Qed.

(* Why the length is fuel enough for its own exponent search: a power of
   two outruns its exponent. *)
Lemma len_lt_pow2 : forall n : nat, Nat.ltb n (pow2 n) = true.
Proof.
  intros n. induction n as [ | k IH ].
  - reflexivity.
  - rewrite (pow2_step k). rewrite (mul_two (pow2 k)).
    exact (add_le_mono 1 (pow2 k) (S k) (pow2 k) (pow2_pos k) IH).
Qed.

(* Whether a number is a granule the encoding can align on, decided rather
   than asserted: the exponent of a power of two is smaller than the power,
   so the search range is the number itself. *)
Definition is_pow2 (n : nat) : bool :=
  any_of (fun e => Nat.eqb n (pow2 e)) (upto n).

Lemma a_power_of_two_is_recognized : forall e : nat, is_pow2 (pow2 e) = true.
Proof.
  intros e. unfold is_pow2.
  exact (any_of_upto_intro (fun x => Nat.eqb (pow2 e) (pow2 x)) (pow2 e) e
           (len_lt_pow2 e) (eqb_refl (pow2 e))).
Qed.

Example a_granule_the_encoding_can_align_on_and_two_it_cannot :
  is_pow2 1 = true /\ is_pow2 2 = true /\ is_pow2 3 = false
  /\ is_pow2 4 = true /\ is_pow2 6 = false /\ is_pow2 0 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* The exponent search, which is R-15-007c's bound read as the bound it is:
   step while 2^6 times the next power of two still fits inside the length,
   and stop where it does not. The fuel is the length itself, which
   `len_lt_pow2` shows is past enough, and the step is bound once so the
   search costs one pass and not three. *)
Fixpoint granule_exponent (fuel len : nat) : nat :=
  match fuel with
  | 0 => 0
  | S f =>
      let e := granule_exponent f len in
      if Nat.leb (64 * (2 * pow2 e)) len then S e else e
  end.

Lemma granule_exponent_step :
  forall f len : nat,
    granule_exponent (S f) len
    = if Nat.leb (64 * (2 * pow2 (granule_exponent f len))) len
      then S (granule_exponent f len)
      else granule_exponent f len.
Proof. intros f len. reflexivity. Qed.

Example the_exponent_of_no_fuel : granule_exponent 0 1024 = 0 := eq_refl.

(* R-15-007c's own two figures, and this file's only two magnitudes from
   that entry: byte-exact to 128 bytes, and above that the coarsest power
   of two whose 2^6 multiple still fits inside the length. *)
Definition representable_granule (len : nat) : nat :=
  if Nat.leb len 128 then 1 else pow2 (granule_exponent len len).

Definition Quantum : Type := nat -> nat.

Definition spec_quantum : Quantum := representable_granule.

Definition ByteExactBelowTheThreshold (q : Quantum) : Prop :=
  forall len : nat, Nat.leb len 128 = true -> q len = 1.

(* "At worst the length over 2^6", stated by multiplying the granule back
   rather than by dividing: a granule of which 2^6 fit inside the length is
   exactly a granule no coarser than the length over 2^6. *)
Definition NoCoarserThanTheLengthOverTheSixthPower (q : Quantum) : Prop :=
  forall len : nat, Nat.ltb 128 len = true -> Nat.leb (64 * q len) len = true.

(* And the other side of "lays each object at its representable
   alignment": the plan aligns to the worst case the entry admits, so
   doubling the granule would leave the bound. Without this clause a
   plan-wide granule of one byte satisfies the bound everywhere. *)
Definition TheCoarsestGranuleWithinThatBound (q : Quantum) : Prop :=
  forall len : nat,
    Nat.ltb 128 len = true -> Nat.ltb len (64 * (2 * q len)) = true.

(* And the clause the two bounds do not decide: the encoding's granule is a
   power of two, so a granule inside the bound that is not one is no
   alignment the encoding has. *)
Definition AlignsOnAPowerOfTwo (q : Quantum) : Prop :=
  forall len : nat, is_pow2 (q len) = true.

Theorem the_specification_quantum_is_byte_exact_below_the_threshold :
  ByteExactBelowTheThreshold spec_quantum.
Proof.
  intros len H. unfold spec_quantum, representable_granule. rewrite H. reflexivity.
Qed.

Lemma granule_exponent_within_the_bound :
  forall fuel len : nat,
    Nat.ltb 128 len = true ->
    Nat.leb (64 * pow2 (granule_exponent fuel len)) len = true.
Proof.
  intros fuel. induction fuel as [ | f IH ]; intros len H.
  - exact (leb_trans 64 129 len eq_refl H).
  - rewrite (granule_exponent_step f len).
    destruct (Nat.leb (64 * (2 * pow2 (granule_exponent f len))) len) eqn:E.
    + exact E.
    + exact (IH len H).
Qed.

(* The search either stopped, which is the coarsest granule inside the
   bound, or it never stopped and its exponent is the whole fuel. *)
Lemma granule_exponent_stopped_or_unspent :
  forall fuel len : nat,
    Nat.ltb len (64 * (2 * pow2 (granule_exponent fuel len))) = true
    \/ granule_exponent fuel len = fuel.
Proof.
  intros fuel. induction fuel as [ | f IH ]; intros len.
  - right. reflexivity.
  - rewrite (granule_exponent_step f len).
    destruct (Nat.leb (64 * (2 * pow2 (granule_exponent f len))) len) eqn:E.
    + destruct (IH len) as [ Hlt | Heq ].
      * rewrite (ltb_leb_false _ _ Hlt) in E. discriminate E.
      * right. rewrite Heq. reflexivity.
    + left. exact (leb_false_ltb _ _ E).
Qed.

Theorem the_specification_quantum_is_no_coarser_than_the_bound :
  NoCoarserThanTheLengthOverTheSixthPower spec_quantum.
Proof.
  intros len H. unfold spec_quantum, representable_granule.
  rewrite (ltb_leb_false len 128 H).
  exact (granule_exponent_within_the_bound len len H).
Qed.

Theorem the_specification_quantum_is_the_coarsest_within_that_bound :
  TheCoarsestGranuleWithinThatBound spec_quantum.
Proof.
  intros len H. unfold spec_quantum, representable_granule.
  rewrite (ltb_leb_false len 128 H).
  destruct (granule_exponent_stopped_or_unspent len len) as [ Hlt | Heq ].
  - exact Hlt.
  - assert (Hb : Nat.leb (64 * pow2 (granule_exponent len len)) len = true)
      by exact (granule_exponent_within_the_bound len len H).
    rewrite Heq in Hb.
    assert (Hs : Nat.leb (S len) len = true).
    { apply (leb_trans (S len) (64 * pow2 len) len); [ | exact Hb ].
      apply (leb_trans (S len) (pow2 len) (64 * pow2 len)).
      - exact (len_lt_pow2 len).
      - exact (leb_mul_self 64 (pow2 len) eq_refl). }
    rewrite (leb_succ_false len) in Hs. discriminate Hs.
Qed.

Theorem the_specification_quantum_aligns_on_a_power_of_two :
  AlignsOnAPowerOfTwo spec_quantum.
Proof.
  intros len. unfold spec_quantum, representable_granule.
  destruct (Nat.leb len 128).
  - exact (a_power_of_two_is_recognized 0).
  - exact (a_power_of_two_is_recognized (granule_exponent len len)).
Qed.

(* The construction this file would ship if the granule were a field: one
   plan-wide quantity, whatever its magnitude. R-15-007c fixes the granule
   as a function of the length and a constant is a function of nothing, so
   no plan-wide granule is both byte-exact below the threshold and the
   coarsest inside the bound above it. It is the coarseness clause that
   refuses it: a plan-wide byte granule stays inside the bound everywhere,
   and is an alignment the encoding does not have at any length past it. *)
Definition flat_quantum (g : nat) : Quantum := fun _ => g.

Theorem no_plan_wide_granule_quantizes_as_the_encoding_does :
  forall g : nat,
    ByteExactBelowTheThreshold (flat_quantum g) ->
    TheCoarsestGranuleWithinThatBound (flat_quantum g) -> False.
Proof.
  intros g H1 H2.
  assert (Hlo : g = 1) by exact (H1 1 eq_refl).
  rewrite Hlo in H2.
  assert (Hhi : Nat.ltb 129 (64 * (2 * flat_quantum 1 129)) = true)
    by exact (H2 129 eq_refl).
  cbv in Hhi. discriminate Hhi.
Qed.

(* And the same at one magnitude, with its twins: the byte-exact plan-wide
   granule keeps the regime below the threshold, stays inside the bound
   above it, and aligns on a power of two, so what refutes it is the
   coarseness alone. *)
Theorem the_byte_exact_plan_wide_granule_keeps_the_regime_it_does_not_break :
  ByteExactBelowTheThreshold (flat_quantum 1).
Proof. intros len _. reflexivity. Qed.

Theorem the_byte_exact_plan_wide_granule_keeps_the_bound_and_the_alignment :
  NoCoarserThanTheLengthOverTheSixthPower (flat_quantum 1)
  /\ AlignsOnAPowerOfTwo (flat_quantum 1).
Proof.
  split.
  - intros len H. exact (leb_trans 64 129 len eq_refl H).
  - intros len. exact (a_power_of_two_is_recognized 0).
Qed.

Theorem the_byte_exact_plan_wide_granule_is_refuted :
  ~ TheCoarsestGranuleWithinThatBound (flat_quantum 1).
Proof. intros H. specialize (H 129 eq_refl). cbv in H. discriminate H. Qed.

(* The construction R-15-007c's 128-byte figure exists to rule out: one
   regime rather than two, the exponent search run at every length. It
   keeps all three clauses above the threshold and breaks the byte-exact
   one, at exactly the length the entry names and nowhere below it. *)
Definition single_regime_quantum : Quantum := fun len =>
  pow2 (granule_exponent len len).

Theorem the_single_regime_quantum_keeps_every_clause_above_the_threshold :
  NoCoarserThanTheLengthOverTheSixthPower single_regime_quantum
  /\ TheCoarsestGranuleWithinThatBound single_regime_quantum
  /\ AlignsOnAPowerOfTwo single_regime_quantum.
Proof.
  split; [ | split ].
  - intros len H. exact (granule_exponent_within_the_bound len len H).
  - intros len H.
    destruct (granule_exponent_stopped_or_unspent len len) as [ Hlt | Heq ].
    + exact Hlt.
    + assert (Hb : Nat.leb (64 * pow2 (granule_exponent len len)) len = true)
        by exact (granule_exponent_within_the_bound len len H).
      rewrite Heq in Hb.
      assert (Hs : Nat.leb (S len) len = true).
      { apply (leb_trans (S len) (64 * pow2 len) len); [ | exact Hb ].
        apply (leb_trans (S len) (pow2 len) (64 * pow2 len)).
        - exact (len_lt_pow2 len).
        - exact (leb_mul_self 64 (pow2 len) eq_refl). }
      rewrite (leb_succ_false len) in Hs. discriminate Hs.
  - intros len. exact (a_power_of_two_is_recognized (granule_exponent len len)).
Qed.

Theorem the_single_regime_quantum_is_refuted :
  ~ ByteExactBelowTheThreshold single_regime_quantum.
Proof. intros H. specialize (H 128 eq_refl). cbv in H. discriminate H. Qed.

Example the_single_regime_quantum_breaks_at_the_entry_s_own_figure :
  single_regime_quantum 64 = 1
  /\ single_regime_quantum 127 = 1
  /\ single_regime_quantum 128 = 2
  /\ representable_granule 128 = 1 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* And the construction that rounds one exponent past the entry's bound:
   the granule the encoding aligns on, doubled. It keeps the regime below
   the threshold and it is a power of two, so what refutes it is the
   coarseness the entry bounds and nothing else. *)
Definition coarser_quantum : Quantum := fun len =>
  if Nat.leb len 128 then 1 else 2 * representable_granule len.

Theorem the_coarser_quantum_keeps_the_regime_below_and_the_alignment :
  ByteExactBelowTheThreshold coarser_quantum
  /\ AlignsOnAPowerOfTwo coarser_quantum.
Proof.
  split.
  - intros len H. unfold coarser_quantum. rewrite H. reflexivity.
  - intros len. unfold coarser_quantum, representable_granule.
    destruct (Nat.leb len 128).
    + exact (a_power_of_two_is_recognized 0).
    + exact (a_power_of_two_is_recognized (S (granule_exponent len len))).
Qed.

Theorem the_coarser_quantum_is_refuted :
  ~ NoCoarserThanTheLengthOverTheSixthPower coarser_quantum.
Proof. intros H. specialize (H 129 eq_refl). cbv in H. discriminate H. Qed.

Example the_coarser_quantum_rounds_one_exponent_past_the_bound :
  coarser_quantum 128 = 1 /\ coarser_quantum 129 = 4
  /\ coarser_quantum 192 = 4 /\ representable_granule 192 = 2 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* And the construction the two bound clauses leave standing: a granule
   inside R-15-007c's own window at one length and the encoding's
   everywhere else. The window is half-open and wider than one value
   wherever the length over 2^6 is not itself a power of two, so what pins
   the granule inside it is the exponent and not the bound. The magnitude
   is not this file's: it is read off the entry's own division at a length
   the plan declares, below. *)
Definition granule_inside_the_window (at_length g : nat) : Quantum := fun len =>
  if Nat.eqb len at_length then g else representable_granule len.

Theorem a_granule_inside_the_window_keeps_both_bounds :
  forall at_length g : nat,
    Nat.ltb 128 at_length = true ->
    Nat.leb (64 * g) at_length = true ->
    Nat.ltb at_length (64 * (2 * g)) = true ->
    ByteExactBelowTheThreshold (granule_inside_the_window at_length g)
    /\ NoCoarserThanTheLengthOverTheSixthPower
         (granule_inside_the_window at_length g)
    /\ TheCoarsestGranuleWithinThatBound (granule_inside_the_window at_length g).
Proof.
  intros at_length g Ha Hlo Hhi. split; [ | split ].
  - intros len H. unfold granule_inside_the_window.
    destruct (Nat.eqb len at_length) eqn:E.
    + rewrite (eqb_true _ _ E) in H.
      rewrite (ltb_leb_false at_length 128 Ha) in H. discriminate H.
    + exact (the_specification_quantum_is_byte_exact_below_the_threshold len H).
  - intros len H. unfold granule_inside_the_window.
    destruct (Nat.eqb len at_length) eqn:E.
    + rewrite (eqb_true _ _ E). exact Hlo.
    + exact (the_specification_quantum_is_no_coarser_than_the_bound len H).
  - intros len H. unfold granule_inside_the_window.
    destruct (Nat.eqb len at_length) eqn:E.
    + rewrite (eqb_true _ _ E). exact Hhi.
    + exact (the_specification_quantum_is_the_coarsest_within_that_bound len H).
Qed.

Example the_two_regimes_meet_at_the_threshold :
  representable_granule 1 = 1
  /\ representable_granule 128 = 1
  /\ representable_granule 129 = 2
  /\ representable_granule 192 = 2
  /\ representable_granule 384 = 4
  /\ representable_granule 512 = 8
  /\ representable_granule 1024 = 16 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

(* Each region's own granule, which is that array's representable granule
   and not the plan's. *)
Definition granule_of (p : Plan) (r : nat) : nat :=
  representable_granule (p.(length_of) r).

(* R-15-007k's two obligations on the plan, each an equation the plan can
   fail: the slot base is laid at the region's representable alignment, and
   the length is granule-quantized. Both are checked by multiplying the
   declared count back rather than by a division (reading 8). *)
Definition base_is_quantized (p : Plan) (r : nat) : bool :=
  Nat.eqb (granule_of p r * p.(base_granules) r) (p.(base_of) r).

Definition length_is_quantized (p : Plan) (r : nat) : bool :=
  Nat.eqb (granule_of p r * p.(length_granules_of) r) (p.(length_of) r).

Definition slot_bases_quantized (p : Plan) : bool :=
  all_of (base_is_quantized p) (upto p.(region_count)).

Definition slot_lengths_quantized (p : Plan) : bool :=
  all_of (length_is_quantized p) (upto p.(region_count)).

Definition BasesAreRepresentablyAligned (p : Plan) : Prop :=
  forall r : nat, Nat.ltb r p.(region_count) = true ->
    granule_of p r * p.(base_granules) r = p.(base_of) r.

Definition LengthsAreGranuleQuantized (p : Plan) : Prop :=
  forall r : nat, Nat.ltb r p.(region_count) = true ->
    granule_of p r * p.(length_granules_of) r = p.(length_of) r.

Lemma slot_bases_quantized_sound :
  forall p : Plan, slot_bases_quantized p = true -> BasesAreRepresentablyAligned p.
Proof.
  intros p H r Hr. unfold slot_bases_quantized in H.
  exact (eqb_true _ _ (all_of_upto (base_is_quantized p) p.(region_count) r H Hr)).
Qed.

Lemma slot_lengths_quantized_sound :
  forall p : Plan, slot_lengths_quantized p = true -> LengthsAreGranuleQuantized p.
Proof.
  intros p H r Hr. unfold slot_lengths_quantized in H.
  exact (eqb_true _ _ (all_of_upto (length_is_quantized p) p.(region_count) r H Hr)).
Qed.

(* And both checks the other way, which is what makes a false check a
   refutation of the obligation rather than a report that the check moved:
   with soundness alone a plan the check refuses might still satisfy
   R-15-007k, and the theorems below would record a decision procedure's
   verdict instead of a violated obligation. *)
Lemma slot_bases_quantized_complete :
  forall p : Plan, BasesAreRepresentablyAligned p -> slot_bases_quantized p = true.
Proof.
  intros p H. unfold slot_bases_quantized. apply all_of_upto_intro.
  intros r Hr. unfold base_is_quantized. rewrite (H r Hr). apply eqb_refl.
Qed.

Lemma slot_lengths_quantized_complete :
  forall p : Plan, LengthsAreGranuleQuantized p -> slot_lengths_quantized p = true.
Proof.
  intros p H. unfold slot_lengths_quantized. apply all_of_upto_intro.
  intros r Hr. unfold length_is_quantized. rewrite (H r Hr). apply eqb_refl.
Qed.

Record Narrowing : Type := {
  at_region : nat;
  offset_granules : nat;
  stride_granules : nat;
  dyn_index : nat;
  length_granules : nat
}.

Definition narrowing_granules (p : Plan) (n : Narrowing) : nat :=
  p.(base_granules) n.(at_region)
  + n.(offset_granules) + n.(stride_granules) * n.(dyn_index).

Definition narrowing_base (p : Plan) (n : Narrowing) : nat :=
  p.(base_of) n.(at_region)
  + granule_of p n.(at_region)
    * (n.(offset_granules) + n.(stride_granules) * n.(dyn_index)).

(* R-15-007k's "that array's representable granule": a split of an array is
   constrained to the granule of the array it splits and not to a
   plan-wide one, which is what makes this projection read `at_region`. *)
Definition narrowing_length (p : Plan) (n : Narrowing) : nat :=
  granule_of p n.(at_region) * n.(length_granules).

(* What "exactly representable" means here: the narrowed base is a whole
   number of that array's granules, so a `csetbounds` at it rounds outward
   nowhere. *)
Definition Exact (p : Plan) (n : Narrowing) : Prop :=
  narrowing_base p n = granule_of p n.(at_region) * narrowing_granules p n.

(* S5a (R-15-007k): a quantized slot base narrows exactly at every dynamic
   index, which is that entry's "the residue class is known where the layout
   is decided even where the address is not known to the compartment
   holding it". Stated of an arbitrary plan, narrowing and index. *)
Theorem a_quantized_slot_base_narrows_exactly :
  forall (p : Plan) (n : Narrowing),
    base_is_quantized p n.(at_region) = true -> Exact p n.
Proof.
  intros p n H. unfold Exact, narrowing_base, narrowing_granules.
  rewrite <- (eqb_true _ _ H).
  rewrite <- (mul_add_distr_l (granule_of p n.(at_region))
                (p.(base_granules) n.(at_region))
                (n.(offset_granules) + n.(stride_granules) * n.(dyn_index))).
  rewrite (add_assoc (p.(base_granules) n.(at_region)) n.(offset_granules)
             (n.(stride_granules) * n.(dyn_index))).
  reflexivity.
Qed.

(* The narrowing record's length half is structural, a length stated in
   granules being a granule multiple by construction. It is not the
   obligation: R-15-007k's "at a granule-quantized length" falls on the
   plan's own lengths, which is `LengthsAreGranuleQuantized` above and is a
   check a plan fails below. *)
Lemma a_narrowed_length_is_a_whole_number_of_granules :
  forall (p : Plan) (n : Narrowing),
    narrowing_length p n = granule_of p n.(at_region) * n.(length_granules).
Proof. intros p n. reflexivity. Qed.

Definition NarrowingCheck : Type := Plan -> Narrowing -> bool.

Definition spec_narrow_ok : NarrowingCheck :=
  fun p n => base_is_quantized p n.(at_region).

Definition AdmitsOnlyExactNarrowings (chk : NarrowingCheck) : Prop :=
  forall (p : Plan) (n : Narrowing), chk p n = true -> Exact p n.

(* S5c (R-15-007k): a `csetbounds` whose result rounds outward is a defect
   in the slot plan, so the check the plan carries admits only what is
   exact. *)
Theorem the_specification_narrowing_check_admits_only_exact_narrowings :
  AdmitsOnlyExactNarrowings spec_narrow_ok.
Proof. intros p n H. exact (a_quantized_slot_base_narrows_exactly p n H). Qed.

(* The construction R-15-007k declines by name: a check that admits every
   narrowing and reports the rounding, which is what `CRAM` and `CRRL` are
   for and what an outward round would leak past a subobject. *)
Definition rounding_narrow_ok : NarrowingCheck := fun _ _ => true.

(* And one that rounds outward and accepts, which is the same declination
   read from the other side: it admits every narrowing whose base falls
   inside the granule the plan would have to round it up to. R-15-007c
   prices that round at one part in 64 of the length on each side, and
   R-15-007k's whole point is that it must be impossible rather than
   reported. It admits every narrowing the specification admits, so what
   refutes it is the acceptance and not a different arithmetic. *)
Definition within_one_granule_narrow_ok : NarrowingCheck := fun p n =>
  Nat.ltb (narrowing_base p n)
          (granule_of p n.(at_region) * narrowing_granules p n
           + granule_of p n.(at_region)).

Theorem the_within_one_granule_check_admits_what_the_specification_admits :
  forall (p : Plan) (n : Narrowing),
    Nat.ltb 0 (granule_of p n.(at_region)) = true ->
    spec_narrow_ok p n = true -> within_one_granule_narrow_ok p n = true.
Proof.
  intros p n Hg H. unfold within_one_granule_narrow_ok.
  rewrite (the_specification_narrowing_check_admits_only_exact_narrowings p n H).
  apply ltb_add_pos. exact Hg.
Qed.

Theorem the_rounding_check_admits_what_the_specification_admits :
  forall (p : Plan) (n : Narrowing),
    spec_narrow_ok p n = true -> rounding_narrow_ok p n = true.
Proof. intros p n _. reflexivity. Qed.

(* =========================================================================
   Island containment (R-08-012c).

   Every slot the plan assigns lies inside the region the owning island's
   root capability bounds, and the bank/macro/tier to island map is read and
   never written. A placement is stated as an arbitrary base function so an
   out-of-island one is expressible, and what the check must read is the
   plan's own bases rather than a report about them.
   ========================================================================= *)

Definition Placement : Type := nat -> nat.

Definition island_lo (p : Plan) (r : nat) : nat :=
  p.(island_base) (p.(island_of) r).

Definition island_hi (p : Plan) (r : nat) : nat :=
  p.(island_base) (p.(island_of) r) + p.(island_span) (p.(island_of) r).

Definition inside_island (p : Plan) (place : Placement) (r : nat) : bool :=
  andb (Nat.leb (island_lo p r) (place r))
       (Nat.leb (place r + p.(length_of) r) (island_hi p r)).

Definition containment_ok (p : Plan) (place : Placement) : bool :=
  all_of (inside_island p place) (upto p.(region_count)).

Definition StaysInsideItsIsland (p : Plan) (place : Placement) : Prop :=
  forall r : nat,
    Nat.ltb r p.(region_count) = true -> inside_island p place r = true.

Lemma containment_ok_sound :
  forall (p : Plan) (place : Placement),
    containment_ok p place = true -> StaysInsideItsIsland p place.
Proof.
  intros p place H r Hr. unfold containment_ok in H.
  exact (all_of_upto (inside_island p place) p.(region_count) r H Hr).
Qed.

Lemma containment_ok_complete :
  forall (p : Plan) (place : Placement),
    StaysInsideItsIsland p place -> containment_ok p place = true.
Proof.
  intros p place H. unfold containment_ok. apply all_of_upto_intro. exact H.
Qed.

Definition spec_placement (p : Plan) : Placement := p.(base_of).

Definition ChecksThePlanSOwnBases (place : Plan -> Placement) : Prop :=
  forall (p : Plan) (r : nat), place p r = p.(base_of) r.

Theorem the_specification_placement_is_the_plan_s_own_bases :
  ChecksThePlanSOwnBases spec_placement.
Proof. intros p r. reflexivity. Qed.

(* S6 (R-08-012c): the plan's own placement stays inside every island it
   places into, at both edges and over an arbitrary plan. An out-of-island
   placement has no capability derivation, so the obligation is on the base
   the plan actually assigns and both inequalities are load-bearing: the
   lower edge is refuted below by a plan that starts under its island. *)
Theorem the_plan_s_own_placement_stays_inside_every_island :
  forall p : Plan,
    containment_ok p (spec_placement p) = true ->
    forall r : nat, Nat.ltb r p.(region_count) = true ->
      Nat.leb (island_lo p r) (p.(base_of) r) = true
      /\ Nat.leb (p.(base_of) r + p.(length_of) r) (island_hi p r) = true.
Proof.
  intros p H r Hr.
  exact (andb_split _ _ (containment_ok_sound p (spec_placement p) H r Hr)).
Qed.

(* The construction R-08-012c excludes: a placement that reports the
   island's own base wherever the plan's would escape, so containment holds
   of the report and not of the plan. *)
Definition clamped_placement (p : Plan) : Placement := fun r =>
  if inside_island p (spec_placement p) r then spec_placement p r else island_lo p r.

(* Its twin: wherever the plan does stay inside, the clamp is the plan's own
   base, so what refutes it is the escape it hides and not a different
   arithmetic. *)
Theorem the_clamped_placement_agrees_wherever_the_plan_stays_inside :
  forall (p : Plan) (r : nat),
    containment_ok p (spec_placement p) = true ->
    Nat.ltb r p.(region_count) = true ->
    clamped_placement p r = p.(base_of) r.
Proof.
  intros p r H Hr. unfold clamped_placement.
  rewrite (containment_ok_sound p (spec_placement p) H r Hr). reflexivity.
Qed.

(* =========================================================================
   The live-range colouring and its interference side condition (R-08-011,
   R-08-012, R-08-014).

   Reading 7: R-08-014's side condition is read here as slot disjointness
   over *overlapping* live ranges, against that entry's own word "disjoint",
   because R-08-012's collapse of over-reservation onto the proven
   simultaneous peak is exactly two disjoint live ranges sharing one slot.
   The entry's literal words are carried below as a construction and shown
   to refuse that mechanism, and gap f owes the inversion to R-08-014.
   ========================================================================= *)

Definition live_overlap (p : Plan) (r s : nat) : bool :=
  andb (Nat.ltb (p.(live_from) r) (p.(live_to) s))
       (Nat.ltb (p.(live_from) s) (p.(live_to) r)).

Definition slots_disjoint (p : Plan) (place : Placement) (r s : nat) : bool :=
  orb (Nat.leb (place r + p.(length_of) r) (place s))
      (Nat.leb (place s + p.(length_of) s) (place r)).

Definition colouring_ok (p : Plan) (place : Placement) : bool :=
  all_of (fun r =>
            all_of (fun s =>
                      only_if (andb (negb (Nat.eqb r s)) (live_overlap p r s))
                              (slots_disjoint p place r s))
                   (upto p.(region_count)))
         (upto p.(region_count)).

Definition NoInterference (p : Plan) (place : Placement) : Prop :=
  forall r s : nat,
    Nat.ltb r p.(region_count) = true ->
    Nat.ltb s p.(region_count) = true ->
    Nat.eqb r s = false ->
    live_overlap p r s = true ->
    slots_disjoint p place r s = true.

Lemma colouring_ok_sound :
  forall (p : Plan) (place : Placement),
    colouring_ok p place = true -> NoInterference p place.
Proof.
  intros p place H r s Hr Hs Hne Hov. unfold colouring_ok in H.
  assert (Hr' : all_of (fun t =>
                   only_if (andb (negb (Nat.eqb r t)) (live_overlap p r t))
                           (slots_disjoint p place r t))
                 (upto p.(region_count)) = true) by
    exact (all_of_upto _ p.(region_count) r H Hr).
  assert (Hs' : only_if (andb (negb (Nat.eqb r s)) (live_overlap p r s))
                        (slots_disjoint p place r s) = true) by
    exact (all_of_upto _ p.(region_count) s Hr' Hs).
  apply (only_if_elim _ _ Hs').
  apply andb_join; [ rewrite Hne; reflexivity | exact Hov ].
Qed.

Lemma colouring_ok_complete :
  forall (p : Plan) (place : Placement),
    NoInterference p place -> colouring_ok p place = true.
Proof.
  intros p place H. unfold colouring_ok.
  apply all_of_upto_intro. intros r Hr.
  apply all_of_upto_intro. intros s Hs.
  apply only_if_intro. intros Hc.
  destruct (andb_split _ _ Hc) as [ Hne Hov ].
  apply (H r s Hr Hs); [ | exact Hov ].
  destruct (Nat.eqb r s); [ discriminate Hne | reflexivity ].
Qed.

(* The reading R-08-012 excludes, as a construction rather than as a remark:
   a colouring that requires disjointness outright refuses the mechanism the
   plan exists to use. *)
Definition strict_colouring_ok (p : Plan) (place : Placement) : bool :=
  all_of (fun r =>
            all_of (fun s => only_if (negb (Nat.eqb r s))
                                     (slots_disjoint p place r s))
                   (upto p.(region_count)))
         (upto p.(region_count)).

(* And R-08-014's own words taken literally: slot disjointness over
   *disjoint* live ranges. It is the inversion gap f reports, and it refuses
   the same mechanism from the other direction, demanding separate slots of
   exactly the pair R-08-012 exists to colour together. *)
Definition literal_colouring_ok (p : Plan) (place : Placement) : bool :=
  all_of (fun r =>
            all_of (fun s =>
                      only_if (andb (negb (Nat.eqb r s))
                                    (negb (live_overlap p r s)))
                              (slots_disjoint p place r s))
                   (upto p.(region_count)))
         (upto p.(region_count)).

(* =========================================================================
   R-08-045's charge over the placement list: every region claimed by one
   line item, and nothing claimed the roster does not carry. They are two
   conjuncts and not one, and a construction that satisfies the first and
   fails the second is exhibited below.
   ========================================================================= *)

(* A region of the roster is placed exactly once. The 1 is R-08-045's own
   arity: every physical byte is charged to one line item, so a region
   claimed twice and a region claimed by nothing are the same defect read in
   two directions. *)
Definition each_region_once (p : Plan) (l : list nat) : bool :=
  all_of (fun r => Nat.eqb (occurrences r l) 1) (upto p.(region_count)).

Definition no_stranger (p : Plan) (l : list nat) : bool :=
  all_of (fun r => Nat.ltb r p.(region_count)) l.

Definition plan_ok (p : Plan) (l : list nat) : bool :=
  andb (each_region_once p l) (no_stranger p l).

Definition ChargedExactlyOnce (p : Plan) (l : list nat) : Prop :=
  each_region_once p l = true /\ no_stranger p l = true.

Lemma plan_ok_sound :
  forall (p : Plan) (l : list nat), plan_ok p l = true -> ChargedExactlyOnce p l.
Proof.
  intros p l H. unfold plan_ok in H.
  destruct (andb_split _ _ H) as [ H1 H2 ]. exact (conj H1 H2).
Qed.

Lemma plan_ok_complete :
  forall (p : Plan) (l : list nat), ChargedExactlyOnce p l -> plan_ok p l = true.
Proof.
  intros p l [ H1 H2 ]. unfold plan_ok. apply andb_join; [ exact H1 | exact H2 ].
Qed.

(* And R-15-247j's acceptance clause joined to that charge (reading 11): a
   plan is well formed against the frame it is admitted into when every
   region is charged to one line item and every region's declared slot is
   one the frame carries. It is a conjunct rather than a check of its own
   because a plan satisfying the first and breaking the second passes every
   other check this file ships and still absorbs its own delta. *)
Definition plan_ok_against {T : Type} (p : Plan) (l : list nat)
                           (f : Frame T) : bool :=
  andb (plan_ok p l) (slot_indices_held p f).

Definition WellFormedAgainstTheFrame {T : Type} (p : Plan) (l : list nat)
                                     (f : Frame T) : Prop :=
  ChargedExactlyOnce p l /\ ChargesOnlySlotsTheFrameHolds p f.

Lemma plan_ok_against_sound :
  forall (T : Type) (p : Plan) (l : list nat) (f : Frame T),
    plan_ok_against p l f = true -> WellFormedAgainstTheFrame p l f.
Proof.
  intros T p l f H. unfold plan_ok_against in H.
  destruct (andb_split _ _ H) as [ H1 H2 ].
  exact (conj (plan_ok_sound p l H1) (slot_indices_held_sound T p f H2)).
Qed.

Lemma plan_ok_against_complete :
  forall (T : Type) (p : Plan) (l : list nat) (f : Frame T),
    WellFormedAgainstTheFrame p l f -> plan_ok_against p l f = true.
Proof.
  intros T p l f [ H1 H2 ]. unfold plan_ok_against.
  apply andb_join; [ exact (plan_ok_complete p l H1)
                   | exact (slot_indices_held_complete T p f H2) ].
Qed.

(* =========================================================================
   The origin pool and its ceiling (R-14-009, R-14-010, R-14-015,
   R-18-004b).

   R-14-015 books the consequence rather than leaving it implicit: moving
   the arenas raises the origin-pool ceiling *P* for the same first-class
   budget. Which regions a pool member owns is gap d, so the roster is a
   field; and the obligation is stated over an arbitrary population bound
   rather than proved of one definition, so a bound that reads the member
   cost and answers non-monotonically is refutable.
   ========================================================================= *)

Fixpoint bytes_on (p : Plan) (a : Assignment) (c : MemClass) (l : list nat) : nat :=
  match l with
  | nil => 0
  | cons r t =>
      (if class_eqb (a r) c then p.(length_of) r else 0) + bytes_on p a c t
  end.

Definition member_first_class_cost (p : Plan) (a : Assignment) : nat :=
  bytes_on p a FirstClass p.(origin_regions).

Definition PopulationBound : Type := Plan -> Assignment -> nat -> bool.

Definition pool_fits : PopulationBound := fun p a n =>
  Nat.leb (p.(fixed_first_class) + n * member_first_class_cost p a)
          p.(first_budget).

(* R-14-015's booked consequence as a property of an arbitrary bound: a
   cheaper member admits every population a dearer one admits, for the same
   budget, which is what makes the ceiling a function of the placement
   rather than of the class's name. *)
Definition MonotoneInTheMemberCost (bnd : PopulationBound) : Prop :=
  forall (p : Plan) (a b : Assignment) (n : nat),
    Nat.leb (member_first_class_cost p b) (member_first_class_cost p a) = true ->
    bnd p a n = true -> bnd p b n = true.

(* S8a: the specification's bound is that property. *)
Theorem the_specification_bound_is_monotone_in_the_member_cost :
  MonotoneInTheMemberCost pool_fits.
Proof.
  intros p a b n Hle H. unfold pool_fits in H. unfold pool_fits.
  apply (leb_trans (p.(fixed_first_class) + n * member_first_class_cost p b)
                   (p.(fixed_first_class) + n * member_first_class_cost p a)
                   p.(first_budget)); [ | exact H ].
  apply add_le_mono; [ apply leb_refl | ].
  apply mul_le_mono_l. exact Hle.
Qed.

(* A bound that reads the member cost and is not monotone in it: it refuses
   a member costing nothing, which is a pool whose members hold no
   first-class bytes refused for holding none. *)
Definition brittle_bound : PopulationBound := fun p a n =>
  andb (pool_fits p a n) (Nat.ltb 0 (member_first_class_cost p a)).

(* Its twin: it refuses nothing the specification admits wherever the member
   costs something, so what refutes it is the floor and not the arithmetic. *)
Theorem the_brittle_bound_agrees_where_the_member_costs_something :
  forall (p : Plan) (a : Assignment) (n : nat),
    Nat.ltb 0 (member_first_class_cost p a) = true ->
    brittle_bound p a n = pool_fits p a n.
Proof.
  intros p a n H. unfold brittle_bound. rewrite H.
  destruct (pool_fits p a n); reflexivity.
Qed.

Lemma bytes_on_promote_ge :
  forall (p : Plan) (k : RegionKind) (l : list nat),
    Nat.leb (bytes_on p (spec_assign p) FirstClass l)
            (bytes_on p (promote k p) FirstClass l) = true.
Proof.
  intros p k l. induction l as [ | r t IH ].
  - reflexivity.
  - simpl. apply add_le_mono; [ | exact IH ].
    unfold promote, spec_assign.
    destruct (kind_eqb (p.(kind_of) r) k).
    + simpl. destruct (class_eqb (register_place p r) FirstClass).
      * apply leb_refl.
      * reflexivity.
    + apply leb_refl.
Qed.

Theorem promoting_a_kind_never_lowers_the_member_cost :
  forall (p : Plan) (k : RegionKind),
    Nat.leb (member_first_class_cost p (spec_assign p))
            (member_first_class_cost p (promote k p)) = true.
Proof.
  intros p k. unfold member_first_class_cost.
  exact (bytes_on_promote_ge p k p.(origin_regions)).
Qed.

(* S8b (R-14-015, R-14-009, R-14-010): the register's own placement admits
   every population a first-class placement of any one kind admits, which is
   "moving the arenas raises the origin-pool ceiling P for the same
   first-class budget" as a theorem over an arbitrary bound, kind, plan and
   population rather than as a remark. *)
Theorem the_register_placement_admits_every_population_a_promotion_admits :
  forall (bnd : PopulationBound) (p : Plan) (k : RegionKind) (n : nat),
    MonotoneInTheMemberCost bnd ->
    bnd p (promote k p) n = true -> bnd p (spec_assign p) n = true.
Proof.
  intros bnd p k n Hm H.
  exact (Hm p (promote k p) (spec_assign p) n
           (promoting_a_kind_never_lowers_the_member_cost p k) H).
Qed.

(* =========================================================================
   The generators (R-05-166). A refutation is a seeded weakening the
   theorem must reject, so these produce families of them from the
   specification's own structure rather than a person authoring each. The
   theorems below quantify over the index; the Examples check each whole
   family by conversion and print nothing.
   ========================================================================= *)

(* Transpose the adjacent pair at n. Over the class vector this is two
   regions swapping classes, which is the placement error R-15-247j names;
   over the placement list it is a reordering no entry forbids (reading 6). *)
Fixpoint swap_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons a (cons b r) => cons b (cons a r)
  | 0, _ => l
  | S k, cons a r => cons a (swap_at k r)
  | S _, nil => nil
  end.

(* Delete the entry at n: over the placement list, a region of the roster
   no line item claims. *)
Fixpoint drop_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons _ r => r
  | 0, nil => nil
  | S k, cons a r => cons a (drop_at k r)
  | S _, nil => nil
  end.

(* Place one region a second time: two line items claiming one region. *)
Fixpoint insert_at {A : Type} (n : nat) (x : A) (l : list A) : list A :=
  match n, l with
  | 0, _ => cons x l
  | S k, cons a r => cons a (insert_at k x r)
  | S _, nil => cons x nil
  end.

Definition transpositions {A : Type} (l : list A) : list (list A) :=
  map_over (fun n => swap_at n l) (upto (before_last (count_of l))).

Definition deletions {A : Type} (l : list A) : list (list A) :=
  map_over (fun n => drop_at n l) (upto (count_of l)).

Definition duplications (l : list nat) : list (list nat) :=
  map_over (fun n => insert_at n 0 l) (upto (S (count_of l))).

(* Every assignment of the two classes across n regions, as a boolean
   enumeration over the roster: the class-assignment family, generated from
   the enumeration R-15-247 closes rather than authored. *)
Fixpoint all_masks (n : nat) : list (list MemClass) :=
  match n with
  | 0 => cons nil nil
  | S k =>
      app (map_over (fun m => cons FirstClass m) (all_masks k))
          (map_over (fun m => cons SecondClass m) (all_masks k))
  end.

Fixpoint mask_eqb (a b : list MemClass) : bool :=
  match a, b with
  | nil, nil => true
  | cons x r, cons y s => andb (class_eqb x y) (mask_eqb r s)
  | _, _ => false
  end.

(* A class vector read as an assignment. An index the vector does not carry
   reads the fallback, which is what makes a vector shorter than the roster
   a weakening rather than a silence. *)
Definition assignment_of (m : list MemClass) : Assignment :=
  fun r => at_list m r FirstClass.

(* The generators' own floors. *)
Example the_generators_on_a_short_list :
  swap_at 0 (cons 1 (cons 2 (cons 3 nil))) = cons 2 (cons 1 (cons 3 nil))
  /\ drop_at 1 (cons 1 (cons 2 (cons 3 nil))) = cons 1 (cons 3 nil)
  /\ insert_at 3 9 (cons 1 (cons 2 (cons 3 nil)))
     = cons 1 (cons 2 (cons 3 (cons 9 nil))) :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_generators_on_nothing :
  swap_at 0 (nil : list nat) = nil
  /\ drop_at 0 (nil : list nat) = nil
  /\ insert_at 1 9 (nil : list nat) = cons 9 nil :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_masks_of_two :
  all_masks 2
  = cons (cons FirstClass (cons FirstClass nil))
    (cons (cons FirstClass (cons SecondClass nil))
    (cons (cons SecondClass (cons FirstClass nil))
    (cons (cons SecondClass (cons SecondClass nil)) nil))) := eq_refl.

Example the_masks_of_nothing : all_masks 0 = cons nil nil := eq_refl.

Example mask_equality_is_pointwise :
  mask_eqb (cons FirstClass nil) (cons FirstClass nil) = true
  /\ mask_eqb (cons FirstClass nil) (cons SecondClass nil) = false
  /\ mask_eqb (cons FirstClass nil) nil = false
  /\ mask_eqb (cons FirstClass (cons SecondClass nil))
              (cons FirstClass (cons FirstClass nil)) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example a_vector_shorter_than_the_roster_reads_the_fallback :
  assignment_of (cons SecondClass nil) 0 = SecondClass
  /\ assignment_of (cons SecondClass nil) 1 = FirstClass :=
  conj eq_refl eq_refl.

(* =========================================================================
   The demo plan, for R-05-165's uninhabited-domain mode and for the
   refutation witnesses. Eight regions across two islands: three code kinds
   and three data kinds the register places by name, and two application
   payloads the register places by criterion, one cycle-critical and one
   not, so the criterion decides rather than being assumed. The classes
   alternate, so every adjacent transposition of the class vector is a
   placement error; one second-class code region's delta sits exactly on the
   admission margin; and one pair of regions has disjoint live ranges, so
   that R-08-012's slot sharing is exhibited rather than described. Every
   figure below is an arbitrary witness value and carries no composition
   claim (gap g).
   ========================================================================= *)

Definition demo_kinds : list RegionKind :=
  cons HardTaskAndHotCode (cons InterpreterObjectArenas
  (cons ScalarWorkingSet (cons ColdStaticallyPlacedCode
  (cons InterpreterBody (cons ModelWeights
  (cons ApplicationPayload (cons ApplicationPayload nil))))))).

(* The composition's own cycle-criticality judgment, which is what M1.9
   reads rather than assumes: one payload is cycle-critical and the other is
   bulk, and neither is decided by its name. *)
Definition demo_critical : list bool :=
  cons false (cons false (cons false (cons false
  (cons false (cons false (cons true (cons false nil))))))).

Definition demo_lengths : list nat :=
  cons 64 (cons 256 (cons 32 (cons 96
  (cons 128 (cons 512 (cons 192 (cons 1024 nil))))))).

(* Region 6 is laid at 224 and not at 225: its length is 192, its
   representable granule is therefore 2, and an odd base is no whole number
   of that granule (reading 8). The base a granule computed by division
   would have admitted there is carried below as `odd_base_plan`. *)
Definition demo_bases : list nat :=
  cons 0 (cons 2048 (cons 64 (cons 2304
  (cons 96 (cons 2400 (cons 224 (cons 2928 nil))))))).

Definition demo_base_granules : list nat :=
  cons 0 (cons 512 (cons 64 (cons 2304
  (cons 96 (cons 300 (cons 112 (cons 183 nil))))))).

Definition demo_length_granules : list nat :=
  cons 64 (cons 64 (cons 32 (cons 96
  (cons 128 (cons 64 (cons 96 (cons 64 nil))))))).

Definition demo_islands : list nat :=
  cons 0 (cons 1 (cons 0 (cons 1 (cons 0 (cons 1 (cons 0 (cons 1 nil))))))).

Definition demo_island_bases : list nat := cons 0 (cons 2048 nil).

Definition demo_island_spans : list nat := cons 1024 (cons 1904 nil).

Definition demo_live_starts : list nat :=
  cons 0 (cons 0 (cons 0 (cons 0 (cons 10 (cons 0 (cons 0 (cons 0 nil))))))).

Definition demo_live_ends : list nat :=
  cons 30 (cons 30 (cons 10 (cons 30 (cons 30 (cons 30 (cons 30 (cons 30 nil))))))).

Definition demo_fetch_counts : list nat :=
  cons 12 (cons 0 (cons 0 (cons 1 (cons 40 (cons 0 (cons 0 (cons 0 nil))))))).

(* Which frame slot each region's code runs in, and so which slot's declared
   bound its delta is charged to. Three distinct slots are declared, so that
   the index is a quantity the arithmetic reads rather than a constant: the
   hard-task region runs in the reserved band R-11-020 makes identical across
   rungs, the interpreter body in the background band, and everything else in
   the discretionary focus. *)
Definition demo_slots : list nat :=
  cons 0 (cons 1 (cons 1 (cons 1 (cons 2 (cons 1 (cons 1 (cons 1 nil))))))).

Definition demo_placed : list nat :=
  cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 (cons 6 (cons 7 nil))))))).

Definition demo_origin_regions : list nat := cons 1 (cons 2 nil).

Definition demo_kind_of (r : nat) : RegionKind := at_list demo_kinds r ModelWeights.

Definition demo_cycle_critical (r : nat) : bool := at_list demo_critical r false.

(* The plan's own class field, written out rather than referring to the
   record being built: it is the register's placement, by name where the
   register names and by criterion where it does not. *)
Definition demo_class_of (r : nat) : MemClass :=
  match placed_by_name (demo_kind_of r) with
  | Some c => c
  | None => criterion_class (demo_cycle_critical r)
  end.

(* The plan, with the quantities the variants below move taken as
   arguments: the lengths with their declared granule counts, the slot bases
   with theirs, the charged slots, and the second class's own constant.
   Everything else is one composition. *)
Definition build_plan (lengths bases bgran lgran slots : list nat)
                      (second : nat) : Plan := {|
  region_count := 8;
  kind_of := demo_kind_of;
  cycle_critical := demo_cycle_critical;
  class_of := demo_class_of;
  base_of := fun r => at_list bases r 0;
  length_of := fun r => at_list lengths r 0;
  live_from := fun r => at_list demo_live_starts r 0;
  live_to := fun r => at_list demo_live_ends r 0;
  base_granules := fun r => at_list bgran r 0;
  length_granules_of := fun r => at_list lgran r 0;
  island_of := fun r => at_list demo_islands r 0;
  island_base := fun i => at_list demo_island_bases i 0;
  island_span := fun i => at_list demo_island_spans i 0;
  first_fetch := 10;
  second_fetch := second;
  fetch_count := fun r => at_list demo_fetch_counts r 0;
  slot_of := fun r => at_list slots r 0;
  placed := demo_placed;
  origin_regions := demo_origin_regions;
  fixed_first_class := 1024;
  first_budget := 2048
|}.

Definition demo_plan : Plan :=
  build_plan demo_lengths demo_bases demo_base_granules demo_length_granules
             demo_slots 15.

(* One unit more on the second class's own constant, and nothing else
   moved: the margin's other side. *)
Definition over_margin_plan : Plan :=
  build_plan demo_lengths demo_bases demo_base_granules demo_length_granules
             demo_slots 16.

(* A composition whose two class constants coincide: R-15-247s's boundary
   is latency-criticality and nothing else, so this plan places exactly as
   the specification does and charges nothing for it. *)
Definition flat_plan : Plan :=
  build_plan demo_lengths demo_bases demo_base_granules demo_length_granules
             demo_slots 10.

(* And one whose second class is dearer by exactly one, which is the delta
   ladder's first rung above zero. *)
Definition unit_delta_plan : Plan :=
  build_plan demo_lengths demo_bases demo_base_granules demo_length_granules
             demo_slots 11.

(* A composition declaring a second class faster than the first, which is
   the side condition of reading 3 broken and the truncation it produces. *)
Definition fast_second_plan : Plan :=
  build_plan demo_lengths demo_bases demo_base_granules demo_length_granules
             demo_slots 9.

(* R-08-012's collapse of over-reservation onto the proven simultaneous
   peak: two regions whose live ranges are disjoint share one slot. *)
Definition shared_bases : list nat :=
  cons 0 (cons 2048 (cons 64 (cons 2304
  (cons 64 (cons 2400 (cons 224 (cons 2928 nil))))))).

Definition shared_base_granules : list nat :=
  cons 0 (cons 512 (cons 64 (cons 2304
  (cons 64 (cons 300 (cons 112 (cons 183 nil))))))).

Definition shared_slot_plan : Plan :=
  build_plan demo_lengths shared_bases shared_base_granules demo_length_granules
             demo_slots 15.

(* And the same act where the live ranges do overlap, which is R-08-014's
   side condition broken. *)
Definition overlapping_bases : list nat :=
  cons 0 (cons 2048 (cons 32 (cons 2304
  (cons 96 (cons 2400 (cons 224 (cons 2928 nil))))))).

Definition overlapping_base_granules : list nat :=
  cons 0 (cons 512 (cons 32 (cons 2304
  (cons 96 (cons 300 (cons 112 (cons 183 nil))))))).

Definition overlapping_live_plan : Plan :=
  build_plan demo_lengths overlapping_bases overlapping_base_granules
             demo_length_granules demo_slots 15.

(* A slot that runs past the top of the region its owning island's root
   capability bounds (R-08-012c). *)
Definition escaping_bases : list nat :=
  cons 0 (cons 2048 (cons 64 (cons 2304
  (cons 960 (cons 2400 (cons 224 (cons 2928 nil))))))).

Definition escaping_base_granules : list nat :=
  cons 0 (cons 512 (cons 64 (cons 2304
  (cons 960 (cons 300 (cons 112 (cons 183 nil))))))).

Definition island_escaping_plan : Plan :=
  build_plan demo_lengths escaping_bases escaping_base_granules
             demo_length_granules demo_slots 15.

(* And one that starts below its island's own base, which is the other edge
   of R-08-012c's containment and the conjunct the escaping plan leaves
   untested. *)
Definition underflow_bases : list nat :=
  cons 0 (cons 2044 (cons 64 (cons 2304
  (cons 96 (cons 2400 (cons 224 (cons 2928 nil))))))).

Definition underflow_base_granules : list nat :=
  cons 0 (cons 511 (cons 64 (cons 2304
  (cons 96 (cons 300 (cons 112 (cons 183 nil))))))).

Definition island_underflow_plan : Plan :=
  build_plan demo_lengths underflow_bases underflow_base_granules
             demo_length_granules demo_slots 15.

(* A slot base that is not the granule count the plan declares for it, which
   is R-15-007k's defect in the slot plan. *)
Definition unquantized_bases : list nat :=
  cons 0 (cons 2048 (cons 64 (cons 2304
  (cons 96 (cons 2404 (cons 224 (cons 2928 nil))))))).

Definition unquantized_plan : Plan :=
  build_plan demo_lengths unquantized_bases demo_base_granules
             demo_length_granules demo_slots 15.

(* The same defect at exactly one granule, which is where a check that
   rounds outward and accepts stops accepting. *)
Definition off_by_one_bases : list nat :=
  cons 0 (cons 2048 (cons 64 (cons 2304
  (cons 96 (cons 2408 (cons 224 (cons 2928 nil))))))).

Definition off_by_one_plan : Plan :=
  build_plan demo_lengths off_by_one_bases demo_base_granules
             demo_length_granules demo_slots 15.

(* And the base the reading this file does not take would have admitted: a
   192-byte region laid at 225, which is three of the granules a division
   by 2^6 computes there and no whole number of the granule the encoding
   aligns on. Nothing else about the plan moves, and R-15-007c's own two
   figures are what refuse it (reading 8). *)
Definition odd_bases : list nat :=
  cons 0 (cons 2048 (cons 64 (cons 2304
  (cons 96 (cons 2400 (cons 225 (cons 2928 nil))))))).

Definition odd_base_granules : list nat :=
  cons 0 (cons 512 (cons 64 (cons 2304
  (cons 96 (cons 300 (cons 75 (cons 183 nil))))))).

Definition odd_base_plan : Plan :=
  build_plan demo_lengths odd_bases odd_base_granules demo_length_granules
             demo_slots 15.

(* A region whose declared length is not a whole number of its own
   representable granules, which is R-15-007k's other half broken: the
   length is 200 where that region's granule is 2. *)
Definition unquantized_lengths : list nat :=
  cons 64 (cons 256 (cons 32 (cons 96
  (cons 128 (cons 512 (cons 200 (cons 1024 nil))))))).

Definition unquantized_length_plan : Plan :=
  build_plan unquantized_lengths demo_bases demo_base_granules
             demo_length_granules demo_slots 15.

(* One region's declared length moved and nothing else: the length and the
   granule count that states it are one declaration, so both halves move
   together. It is what a delta priced by bytes rather than by fetches
   reads, and what the placement delta does not. *)
Definition shorter_lengths : list nat :=
  cons 64 (cons 256 (cons 32 (cons 64
  (cons 128 (cons 512 (cons 192 (cons 1024 nil))))))).

Definition shorter_length_granules : list nat :=
  cons 64 (cons 64 (cons 32 (cons 64
  (cons 128 (cons 64 (cons 96 (cons 64 nil))))))).

Definition shorter_region_plan : Plan :=
  build_plan shorter_lengths demo_bases demo_base_granules
             shorter_length_granules demo_slots 15.

(* And one region's charged slot moved, so that the delta of a second-class
   code region lands in the reserved band rather than in the discretionary
   focus. Nothing else about the plan differs. *)
Definition reserved_charged_slots : list nat :=
  cons 0 (cons 1 (cons 1 (cons 0 (cons 1 (cons 1 (cons 1 (cons 1 nil))))))).

Definition reserved_charged_plan : Plan :=
  build_plan demo_lengths demo_bases demo_base_granules demo_length_granules
             reserved_charged_slots 15.

(* And the same region's charged slot moved once more, past the count of
   slots the frame carries (reading 11). It differs from the plan above in
   that one entry alone, so what the pair separates is an index the frame
   answers to from an index it does not. *)
Definition escaped_charged_slots : list nat :=
  cons 0 (cons 1 (cons 1 (cons 3 (cons 1 (cons 1 (cons 1 (cons 1 nil))))))).

Definition slot_escaping_plan : Plan :=
  build_plan demo_lengths demo_bases demo_base_granules demo_length_granules
             escaped_charged_slots 15.

(* A frame whose three slots have three different slacks, so that a delta
   charged to one is admitted where the same delta charged to another is
   refused and the slot index is a quantity rather than a coincidence. It is
   the rung CyclicExecutive.v composes with two declared in-slot bounds
   moved and no other field touched, which the comparison below states
   field by field against that file's own slots. *)
Definition tight_reserved : Slot bool := Build_Slot bool 60 0 44 100 true.

Definition slack_background : Slot bool := Build_Slot bool 50 150 32 100 true.

Definition charged_rung : Frame bool :=
  Build_Frame bool 200 0 (cons tight_reserved nil)
    (Build_Band bool focus_slot_a (cons slack_background nil)).

Example the_charged_rung_moves_two_declared_bounds_and_nothing_else :
  major_frame charged_rung = major_frame rung_a
  /\ phase_offset charged_rung = phase_offset rung_a
  /\ band_focus (discretionary_band charged_rung) = focus_slot_a
  /\ count_of (reserved_band charged_rung) = count_of (reserved_band rung_a)
  /\ slot_width tight_reserved = slot_width reserved_slot
  /\ slot_offset tight_reserved = slot_offset reserved_slot
  /\ slot_period tight_reserved = slot_period reserved_slot
  /\ slot_tenant tight_reserved = slot_tenant reserved_slot
  /\ Nat.ltb (slot_bound reserved_slot) (slot_bound tight_reserved) = true
  /\ slot_width slack_background = slot_width background_a
  /\ slot_offset slack_background = slot_offset background_a
  /\ slot_period slack_background = slot_period background_a
  /\ slot_tenant slack_background = slot_tenant background_a
  /\ Nat.ltb (slot_bound background_a) (slot_bound slack_background) = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))))))))))).

(* -------------------------------------------------------------------------
   The demo's declared quantities, computed rather than described, so that a
   figure edited on one side of the file and read on the other is a failed
   conversion instead of a silent disagreement.
   ------------------------------------------------------------------------- *)

Example the_demo_plan_declares :
  demo_plan.(region_count) = 8
  /\ demo_plan.(first_fetch) = 10
  /\ demo_plan.(second_fetch) = 15
  /\ demo_plan.(fixed_first_class) = 1024
  /\ demo_plan.(first_budget) = 2048
  /\ over_margin_plan.(second_fetch) = 16
  /\ fast_second_plan.(second_fetch) = 9 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

Example the_demo_rosters :
  demo_plan.(placed)
    = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 (cons 6 (cons 7 nil)))))))
  /\ demo_plan.(origin_regions) = cons 1 (cons 2 nil) :=
  conj eq_refl eq_refl.

Example the_demo_geometry :
  map_over demo_plan.(base_of) (upto 8)
    = cons 0 (cons 2048 (cons 64 (cons 2304
      (cons 96 (cons 2400 (cons 224 (cons 2928 nil)))))))
  /\ map_over demo_plan.(length_of) (upto 8)
    = cons 64 (cons 256 (cons 32 (cons 96
      (cons 128 (cons 512 (cons 192 (cons 1024 nil)))))))
  /\ map_over demo_plan.(base_granules) (upto 8)
    = cons 0 (cons 512 (cons 64 (cons 2304
      (cons 96 (cons 300 (cons 112 (cons 183 nil)))))))
  /\ map_over demo_plan.(island_of) (upto 8)
    = cons 0 (cons 1 (cons 0 (cons 1 (cons 0 (cons 1 (cons 0 (cons 1 nil))))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The granule is a function of the length and not a declaration, so it is
   read back over the roster rather than stated: three regions here are
   below the byte-exact threshold, one sits exactly on it, and four are
   above. Region 6 is where the two readings of R-15-007c differ, its
   granule being the coarsest power of two inside the entry's bound and not
   the bound itself (reading 8). *)
Example the_demo_granules_are_read_from_the_lengths :
  map_over (granule_of demo_plan) (upto 8)
  = cons 1 (cons 4 (cons 1 (cons 1 (cons 1 (cons 8 (cons 2 (cons 16 nil)))))))
  /\ map_over demo_plan.(length_granules_of) (upto 8)
    = cons 64 (cons 64 (cons 32 (cons 96
      (cons 128 (cons 64 (cons 96 (cons 64 nil))))))) :=
  conj eq_refl eq_refl.

Example the_demo_islands_and_lives :
  map_over demo_plan.(island_base) (upto 2) = cons 0 (cons 2048 nil)
  /\ map_over demo_plan.(island_span) (upto 2) = cons 1024 (cons 1904 nil)
  /\ map_over demo_plan.(live_from) (upto 8)
    = cons 0 (cons 0 (cons 0 (cons 0 (cons 10 (cons 0 (cons 0 (cons 0 nil)))))))
  /\ map_over demo_plan.(live_to) (upto 8)
    = cons 30 (cons 30 (cons 10 (cons 30
      (cons 30 (cons 30 (cons 30 (cons 30 nil))))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_demo_fetch_counts_and_slots :
  map_over demo_plan.(fetch_count) (upto 8)
    = cons 12 (cons 0 (cons 0 (cons 1 (cons 40 (cons 0 (cons 0 (cons 0 nil)))))))
  /\ map_over demo_plan.(slot_of) (upto 8)
    = cons 0 (cons 1 (cons 1 (cons 1 (cons 2 (cons 1 (cons 1 (cons 1 nil)))))))
  /\ map_over reserved_charged_plan.(slot_of) (upto 8)
    = cons 0 (cons 1 (cons 1 (cons 0 (cons 1 (cons 1 (cons 1 (cons 1 nil)))))))
  /\ map_over slot_escaping_plan.(slot_of) (upto 8)
    = cons 0 (cons 1 (cons 1 (cons 3 (cons 1 (cons 1 (cons 1 (cons 1 nil))))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* R-08-045's charge read at an index the roster does not carry: a region
   outside the roster declares nothing rather than declaring something
   arbitrary, which is what the fallbacks above are for. *)
Example nothing_is_declared_past_the_roster :
  demo_plan.(length_of) 8 = 0
  /\ demo_plan.(base_of) 8 = 0
  /\ demo_plan.(base_granules) 8 = 0
  /\ demo_plan.(length_granules_of) 8 = 0
  /\ demo_plan.(fetch_count) 8 = 0
  /\ demo_plan.(live_from) 8 = 0
  /\ demo_plan.(live_to) 8 = 0
  /\ demo_plan.(island_of) 8 = 0
  /\ demo_plan.(island_base) 2 = 0
  /\ demo_plan.(island_span) 2 = 0
  /\ demo_plan.(slot_of) 8 = 0
  /\ demo_cycle_critical 8 = false
  /\ demo_kind_of 8 = ModelWeights :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))))))))))).

(* Each variant plan below moves exactly one declared quantity of the
   specification's, which is what makes each refutation a single-defect
   witness rather than a different composition: the layout variants keep the
   second class's own constant where the specification puts it, and the
   constant variants keep the specification's every slot. *)
Example the_variant_plans_keep_the_class_constants :
  shared_slot_plan.(second_fetch) = 15
  /\ overlapping_live_plan.(second_fetch) = 15
  /\ island_escaping_plan.(second_fetch) = 15
  /\ island_underflow_plan.(second_fetch) = 15
  /\ unquantized_plan.(second_fetch) = 15
  /\ off_by_one_plan.(second_fetch) = 15
  /\ unquantized_length_plan.(second_fetch) = 15
  /\ shorter_region_plan.(second_fetch) = 15
  /\ reserved_charged_plan.(second_fetch) = 15
  /\ slot_escaping_plan.(second_fetch) = 15
  /\ odd_base_plan.(second_fetch) = 15
  /\ shared_slot_plan.(first_fetch) = 10
  /\ over_margin_plan.(first_fetch) = 10 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))))))))))).

Example the_constant_variants_keep_every_slot :
  map_over over_margin_plan.(base_of) (upto 8)
    = map_over demo_plan.(base_of) (upto 8)
  /\ map_over fast_second_plan.(base_of) (upto 8)
    = map_over demo_plan.(base_of) (upto 8)
  /\ map_over flat_plan.(base_of) (upto 8)
    = map_over demo_plan.(base_of) (upto 8) :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_layout_variants_each_move_one_base :
  map_over shared_slot_plan.(base_of) (upto 8)
    = cons 0 (cons 2048 (cons 64 (cons 2304
      (cons 64 (cons 2400 (cons 224 (cons 2928 nil)))))))
  /\ map_over overlapping_live_plan.(base_of) (upto 8)
    = cons 0 (cons 2048 (cons 32 (cons 2304
      (cons 96 (cons 2400 (cons 224 (cons 2928 nil)))))))
  /\ map_over island_escaping_plan.(base_of) (upto 8)
    = cons 0 (cons 2048 (cons 64 (cons 2304
      (cons 960 (cons 2400 (cons 224 (cons 2928 nil)))))))
  /\ map_over island_underflow_plan.(base_of) (upto 8)
    = cons 0 (cons 2044 (cons 64 (cons 2304
      (cons 96 (cons 2400 (cons 224 (cons 2928 nil)))))))
  /\ map_over unquantized_plan.(base_of) (upto 8)
    = cons 0 (cons 2048 (cons 64 (cons 2304
      (cons 96 (cons 2404 (cons 224 (cons 2928 nil)))))))
  /\ map_over off_by_one_plan.(base_of) (upto 8)
    = cons 0 (cons 2048 (cons 64 (cons 2304
      (cons 96 (cons 2408 (cons 224 (cons 2928 nil)))))))
  /\ map_over odd_base_plan.(base_of) (upto 8)
    = cons 0 (cons 2048 (cons 64 (cons 2304
      (cons 96 (cons 2400 (cons 225 (cons 2928 nil)))))))
  /\ map_over odd_base_plan.(base_granules) (upto 8)
    = cons 0 (cons 512 (cons 64 (cons 2304
      (cons 96 (cons 300 (cons 75 (cons 183 nil))))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))))).

Example the_length_variants_each_move_one_length :
  map_over unquantized_length_plan.(length_of) (upto 8)
    = cons 64 (cons 256 (cons 32 (cons 96
      (cons 128 (cons 512 (cons 200 (cons 1024 nil)))))))
  /\ map_over shorter_region_plan.(length_of) (upto 8)
    = cons 64 (cons 256 (cons 32 (cons 64
      (cons 128 (cons 512 (cons 192 (cons 1024 nil)))))))
  /\ map_over unquantized_length_plan.(base_of) (upto 8)
    = map_over demo_plan.(base_of) (upto 8)
  /\ map_over shorter_region_plan.(base_of) (upto 8)
    = map_over demo_plan.(base_of) (upto 8) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The kinds, the criticality judgment, and the classes the register puts
   them on. The vector alternates, which is what makes every adjacent
   transposition below a placement error rather than a no-op. *)
Definition spec_mask : list MemClass :=
  cons FirstClass (cons SecondClass (cons FirstClass (cons SecondClass
  (cons FirstClass (cons SecondClass (cons FirstClass (cons SecondClass nil))))))).

Example the_demo_kinds :
  map_over demo_kind_of (upto 8)
  = cons HardTaskAndHotCode (cons InterpreterObjectArenas
    (cons ScalarWorkingSet (cons ColdStaticallyPlacedCode
    (cons InterpreterBody (cons ModelWeights
    (cons ApplicationPayload (cons ApplicationPayload nil)))))))
  /\ map_over demo_cycle_critical (upto 8)
  = cons false (cons false (cons false (cons false
    (cons false (cons false (cons true (cons false nil))))))) :=
  conj eq_refl eq_refl.

Example the_demo_classes :
  map_over demo_plan.(class_of) (upto 8) = spec_mask := eq_refl.

Example the_demo_class_vector_alternates :
  spec_mask = cons FirstClass (cons SecondClass (cons FirstClass
    (cons SecondClass (cons FirstClass (cons SecondClass
    (cons FirstClass (cons SecondClass nil))))))) := eq_refl.

(* The criterion doing the deciding, computed: the two payload regions carry
   one kind between them and land on different classes, which is exactly the
   placement no constructor name could have made. *)
Example the_two_payloads_share_a_kind_and_differ_in_class :
  demo_kind_of 6 = demo_kind_of 7
  /\ placed_by_name (demo_kind_of 6) = None
  /\ register_place demo_plan 6 = FirstClass
  /\ register_place demo_plan 7 = SecondClass :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   The specification's own verdicts, so that no obligation above is proved
   from a premise nothing satisfies.
   ------------------------------------------------------------------------- *)

Theorem the_demo_plan_places_as_the_register_places :
  PlacesAsTheRegisterPlaces demo_plan demo_plan.(class_of).
Proof. apply places_ok_sound. reflexivity. Qed.

Theorem the_demo_plan_places_its_payloads_by_the_criterion :
  PlacesPayloadsByTheCriterion demo_plan demo_plan.(class_of).
Proof.
  intros r Hr H.
  rewrite (the_demo_plan_places_as_the_register_places r Hr).
  unfold register_place. rewrite H. reflexivity.
Qed.

Example the_demo_plan_is_charged_exactly_once :
  plan_ok demo_plan demo_plan.(placed) = true := eq_refl.

Example the_demo_plan_colours_contains_and_quantizes :
  colouring_ok demo_plan (spec_placement demo_plan) = true
  /\ containment_ok demo_plan (spec_placement demo_plan) = true
  /\ slot_bases_quantized demo_plan = true
  /\ slot_lengths_quantized demo_plan = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem the_demo_plan_has_no_interference :
  NoInterference demo_plan (spec_placement demo_plan).
Proof. apply colouring_ok_sound. reflexivity. Qed.

Theorem the_demo_plan_stays_inside_its_islands :
  StaysInsideItsIsland demo_plan (spec_placement demo_plan).
Proof. apply containment_ok_sound. reflexivity. Qed.

Theorem the_demo_plan_lays_every_base_at_its_representable_alignment :
  BasesAreRepresentablyAligned demo_plan.
Proof. apply slot_bases_quantized_sound. reflexivity. Qed.

Theorem the_demo_plan_quantizes_every_length :
  LengthsAreGranuleQuantized demo_plan.
Proof. apply slot_lengths_quantized_sound. reflexivity. Qed.

Theorem the_demo_plan_is_charged_once_per_region :
  ChargedExactlyOnce demo_plan demo_plan.(placed).
Proof. apply plan_ok_sound. reflexivity. Qed.

Example the_demo_plan_charges_only_slots_the_frames_hold :
  count_of (frame_slots charged_rung) = 3
  /\ slot_indices_held demo_plan charged_rung = true
  /\ slot_indices_held demo_plan rung_a = true
  /\ slot_indices_held reserved_charged_plan charged_rung = true
  /\ slot_indices_held slot_escaping_plan charged_rung = false
  /\ plan_ok_against demo_plan demo_plan.(placed) charged_rung = true
  /\ plan_ok_against slot_escaping_plan slot_escaping_plan.(placed) charged_rung
     = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

Theorem the_demo_plan_is_well_formed_against_the_charged_rung :
  WellFormedAgainstTheFrame demo_plan demo_plan.(placed) charged_rung.
Proof. apply (plan_ok_against_sound bool). reflexivity. Qed.

Theorem the_specification_declares_the_side_condition :
  SecondClassIsNoFaster demo_plan.
Proof. reflexivity. Qed.

Theorem a_plan_whose_classes_agree_declares_the_side_condition :
  SecondClassIsNoFaster flat_plan.
Proof. reflexivity. Qed.

Theorem the_demo_plan_charges_a_faithful_delta :
  DeltaIsFaithful demo_plan.
Proof.
  apply the_delta_is_faithful_under_the_side_condition.
  exact the_specification_declares_the_side_condition.
Qed.

Example a_plan_whose_classes_agree_charges_nothing :
  flat_plan.(second_fetch) = 10
  /\ map_over (placement_delta flat_plan flat_plan.(class_of)) (upto 8)
     = cons 0 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0 nil)))))))
  /\ places_ok flat_plan flat_plan.(class_of) = true :=
  conj eq_refl (conj eq_refl eq_refl).

Theorem the_flat_plan_carries_no_delta :
  forall (a : Assignment) (r : nat), placement_delta flat_plan a r = 0.
Proof. intros a r. apply equal_constants_carry_no_delta. reflexivity. Qed.

Example the_unit_delta_plan_charges_one_fetch :
  unit_delta_plan.(second_fetch) = 11
  /\ placement_delta unit_delta_plan unit_delta_plan.(class_of) 3 = 1
  /\ per_fetch_delta unit_delta_plan unit_delta_plan.(class_of) 3 = 1 :=
  conj eq_refl (conj eq_refl eq_refl).

(* R-15-247j's delta over the whole roster: zero on every first-class
   region, and on the one second-class code region the product of its fetch
   count and the difference of the two class constants (reading 2). *)
Example the_demo_deltas :
  map_over (placement_delta demo_plan demo_plan.(class_of)) (upto 8)
  = cons 0 (cons 0 (cons 0 (cons 5 (cons 0 (cons 0 (cons 0 (cons 0 nil))))))) :=
  eq_refl.

Example the_delta_at_the_margin_and_one_unit_past_it :
  placement_delta demo_plan demo_plan.(class_of) 3 = 5
  /\ placement_delta over_margin_plan over_margin_plan.(class_of) 3 = 6 :=
  conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   The boundary witnesses. Every comparison the checks above make is read at
   the value where it decides, so a bound made strict or inclusive is a
   failed conversion here rather than a silence.
   ------------------------------------------------------------------------- *)

Example an_island_holds_a_slot_at_each_of_its_own_ends :
  inside_island demo_plan (spec_placement demo_plan) 1 = true
  /\ inside_island demo_plan (spec_placement demo_plan) 7 = true
  /\ demo_plan.(base_of) 1 = island_lo demo_plan 1
  /\ demo_plan.(base_of) 7 + demo_plan.(length_of) 7 = island_hi demo_plan 7
  /\ inside_island island_escaping_plan (spec_placement island_escaping_plan) 4
     = false
  /\ inside_island island_underflow_plan (spec_placement island_underflow_plan) 1
     = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Example a_slot_ending_where_the_next_begins_is_disjoint :
  slots_disjoint demo_plan (spec_placement demo_plan) 0 2 = true
  /\ slots_disjoint demo_plan (spec_placement demo_plan) 2 4 = true
  /\ slots_disjoint overlapping_live_plan
       (spec_placement overlapping_live_plan) 0 2 = false :=
  conj eq_refl (conj eq_refl eq_refl).

Example a_live_range_ending_where_the_next_begins_does_not_overlap :
  live_overlap demo_plan 2 4 = false
  /\ live_overlap demo_plan 4 2 = false
  /\ live_overlap demo_plan 0 2 = true :=
  conj eq_refl (conj eq_refl eq_refl).

Example a_region_outside_the_roster_is_refused :
  no_stranger demo_plan (cons 7 nil) = true
  /\ no_stranger demo_plan (cons 8 nil) = false :=
  conj eq_refl eq_refl.

Example a_region_claimed_twice_is_refused :
  each_region_once demo_plan demo_placed = true
  /\ each_region_once demo_plan (app demo_placed (cons 0 nil)) = false :=
  conj eq_refl eq_refl.

Example a_quantized_base_and_one_that_is_not :
  base_is_quantized demo_plan 5 = true
  /\ base_is_quantized unquantized_plan 5 = false
  /\ slot_bases_quantized unquantized_plan = false
  /\ length_is_quantized demo_plan 6 = true
  /\ length_is_quantized unquantized_length_plan 6 = false
  /\ slot_lengths_quantized unquantized_length_plan = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* =========================================================================
   Family A: every assignment of the two classes across the roster.

   The enumeration is the register's own (R-15-247 closes the classes at
   two), so what is generated here is the whole space a composition could
   choose from, and exactly one member of it places as the register places,
   by name and by criterion together.
   ========================================================================= *)

Definition class_masks : list (list MemClass) := all_masks 8.

Definition mask_admitted (m : list MemClass) : bool :=
  places_ok demo_plan (assignment_of m).

Example the_class_assignment_family_size : count_of class_masks = 256 := eq_refl.

Example exactly_one_assignment_places_as_the_register_places :
  count_of (filter_of mask_admitted class_masks) = 1 := eq_refl.

Example the_one_admitted_assignment_is_the_register_s :
  filter_of mask_admitted class_masks = cons spec_mask nil := eq_refl.

Example every_assignment_but_the_register_s_is_refused :
  all_of (fun m => only_if (negb (mask_eqb m spec_mask)) (negb (mask_admitted m)))
         class_masks = true := eq_refl.

(* And the same content as a bounded quantifier over the index rather than
   as a computation over the 256 members the roster happens to have. *)
Theorem no_assignment_but_the_register_s_is_admitted :
  forall n : nat,
    Nat.ltb n 256 = true ->
    only_if (negb (mask_eqb (at_list class_masks n nil) spec_mask))
            (negb (mask_admitted (at_list class_masks n nil))) = true.
Proof.
  intros n H.
  exact (all_of_at (list MemClass)
           (fun m => only_if (negb (mask_eqb m spec_mask)) (negb (mask_admitted m)))
           class_masks nil n every_assignment_but_the_register_s_is_refused H).
Qed.

(* =========================================================================
   Family B: the adjacent transpositions of the class vector, which is
   reading 6's contrast and not a second refusal. Every member of it is a
   member of Family A, computed here rather than claimed, so what this
   family carries is the pairing with the placement-list transpositions
   below: the same generator run over the two lists answers oppositely.
   ========================================================================= *)

Definition mask_transpositions : list (list MemClass) := transpositions spec_mask.

Example the_mask_transposition_family_size :
  count_of mask_transpositions = 7 := eq_refl.

Example the_first_mask_transposition :
  at_list mask_transpositions 0 nil
  = cons SecondClass (cons FirstClass (cons FirstClass (cons SecondClass
    (cons FirstClass (cons SecondClass (cons FirstClass
    (cons SecondClass nil))))))) := eq_refl.

Example every_transposition_of_the_class_vector_is_one_of_the_assignments :
  all_of (fun m => any_of (mask_eqb m) class_masks) mask_transpositions = true :=
  eq_refl.

Example every_transposition_of_the_class_vector_is_refused :
  all_of (fun m => negb (mask_admitted m)) mask_transpositions = true := eq_refl.

Theorem no_transposed_class_vector_is_admitted :
  forall n : nat,
    Nat.ltb n 7 = true ->
    negb (mask_admitted (at_list mask_transpositions n nil)) = true.
Proof.
  intros n H.
  exact (all_of_at (list MemClass) (fun m => negb (mask_admitted m))
           mask_transpositions nil n
           every_transposition_of_the_class_vector_is_refused H).
Qed.

(* =========================================================================
   Family C: the deletions and the duplications of the placement list, which
   is R-08-045's charge broken in each direction, and the transpositions of
   the same list, which reading 6 says are not weakenings at all.
   ========================================================================= *)

Definition placement_deletions : list (list nat) := deletions demo_placed.

Definition placement_duplications : list (list nat) := duplications demo_placed.

Definition placement_transpositions : list (list nat) := transpositions demo_placed.

Example the_placement_family_sizes :
  count_of placement_deletions = 8
  /\ count_of placement_duplications = 9
  /\ count_of placement_transpositions = 7 :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_first_deletion_and_the_first_duplication :
  at_list placement_deletions 0 nil
    = cons 1 (cons 2 (cons 3 (cons 4 (cons 5 (cons 6 (cons 7 nil))))))
  /\ at_list placement_duplications 0 nil
    = cons 0 (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 (cons 6
      (cons 7 nil))))))))
  /\ occurrences 0 (at_list placement_duplications 0 nil) = 2 :=
  conj eq_refl (conj eq_refl eq_refl).

Example every_deletion_leaves_a_region_unclaimed :
  all_of (fun w => negb (plan_ok demo_plan w)) placement_deletions = true := eq_refl.

Example every_duplication_claims_a_region_twice :
  all_of (fun w => negb (plan_ok demo_plan w)) placement_duplications = true :=
  eq_refl.

(* Reading 6 stated rather than left as a silence: no entry orders the
   placed regions, so a reordering of the placement list is refused by
   nothing, where the same generator over the class vector is refused
   everywhere. That pairing is what Family B carries. *)
Example no_transposition_of_the_placement_list_is_a_weakening :
  all_of (fun w => plan_ok demo_plan w) placement_transpositions = true := eq_refl.

Theorem no_deletion_of_the_placement_list_charges_every_region :
  forall n : nat,
    Nat.ltb n 8 = true ->
    negb (plan_ok demo_plan (at_list placement_deletions n nil)) = true.
Proof.
  intros n H.
  exact (all_of_at (list nat) (fun w => negb (plan_ok demo_plan w))
           placement_deletions nil n every_deletion_leaves_a_region_unclaimed H).
Qed.

Theorem no_duplication_of_the_placement_list_charges_a_region_once :
  forall n : nat,
    Nat.ltb n 9 = true ->
    negb (plan_ok demo_plan (at_list placement_duplications n nil)) = true.
Proof.
  intros n H.
  exact (all_of_at (list nat) (fun w => negb (plan_ok demo_plan w))
           placement_duplications nil n every_duplication_claims_a_region_twice H).
Qed.

(* And the transposition family as a bounded quantifier over its own index
   too, so that reading 6's second half is stated in the same form as its
   first and not only enumerated. *)
Theorem every_transposition_of_the_placement_list_is_charged_exactly_once :
  forall n : nat,
    Nat.ltb n 7 = true ->
    plan_ok demo_plan (at_list placement_transpositions n nil) = true.
Proof.
  intros n H.
  exact (all_of_at (list nat) (fun w => plan_ok demo_plan w)
           placement_transpositions nil n
           no_transposition_of_the_placement_list_is_a_weakening H).
Qed.

(* A construction the deletions and duplications do not reach, because both
   are decided by the first conjunct alone: a placement list that claims
   every region exactly once and also claims one the roster does not carry.
   R-08-045's charge is two obligations and this is the second one broken
   with the first standing. *)
Definition stranger_placement : list nat := app demo_placed (cons 8 nil).

Theorem the_stranger_placement_breaks_the_second_conjunct_alone :
  each_region_once demo_plan stranger_placement = true
  /\ no_stranger demo_plan stranger_placement = false
  /\ plan_ok demo_plan stranger_placement = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

Theorem the_stranger_placement_is_refuted :
  ~ ChargedExactlyOnce demo_plan stranger_placement.
Proof. intros [ _ H ]. cbv in H. discriminate H. Qed.

(* The stranger read at the value where it decides: it is the roster's own
   count, which is the first index the roster does not carry, so a line item
   one lower is not a stranger at all and the second conjunct is a boundary
   rather than a blanket. *)
Example the_stranger_is_the_first_index_the_roster_does_not_carry :
  at_list stranger_placement (count_of demo_plan.(placed)) 0
    = demo_plan.(region_count)
  /\ count_of stranger_placement = S (count_of demo_plan.(placed))
  /\ no_stranger demo_plan (cons (before_last demo_plan.(region_count)) nil) = true
  /\ no_stranger demo_plan (cons demo_plan.(region_count) nil) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* =========================================================================
   Family D: the delta at, below and above the admission margin.

   The ladder is generated over the delta itself and read through the
   admission check CyclicExecutive.v states, so what it reports is where
   R-11-006's interval arithmetic stops closing. It is read at the slot the
   region declares and over a frame whose three slots have three margins, so
   which region the ladder is about is a quantity too: the same ladder over
   the interpreter body's slot stops three rungs earlier.
   ========================================================================= *)

Definition margin_ladder : list bool :=
  map_over (fun d => admits demo_composition
                       (charge_frame_at (demo_plan.(slot_of) 3) d charged_rung))
           (upto 9).

Example the_margin_ladder :
  margin_ladder
  = cons true (cons true (cons true (cons true (cons true (cons true
    (cons false (cons false (cons false nil)))))))) := eq_refl.

(* The same generator over the slot a different region declares, which is
   what makes the region index of a ladder a quantity: the interpreter
   body's code runs in the background band, whose margin is three. *)
Example the_background_slot_s_ladder_stops_earlier :
  map_over (fun d => admits demo_composition
                       (charge_frame_at (demo_plan.(slot_of) 4) d charged_rung))
           (upto 9)
  = cons true (cons true (cons true (cons true (cons false (cons false
    (cons false (cons false (cons false nil)))))))) := eq_refl.

Theorem every_delta_at_or_below_the_margin_is_admitted :
  forall n : nat, Nat.ltb n 6 = true -> at_list margin_ladder n false = true.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | k ] ] ] ] ] ]; intros H;
    first [ reflexivity | discriminate H ].
Qed.

Theorem no_delta_past_the_margin_is_admitted :
  forall n : nat,
    Nat.leb 6 n = true -> Nat.ltb n 9 = true ->
    at_list margin_ladder n false = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | [ | [ | [ | k ] ] ] ] ] ] ] ] ];
    intros H1 H2; first [ reflexivity | discriminate H1 | discriminate H2 ].
Qed.

(* And the join itself: one unit more on the second class's own constant,
   with the plan otherwise unmoved, turns an admitted frame into a refused
   one. R-15-247j's delta is an input to section 11 admission and not a
   report about it, and this is that sentence machine-checked against the
   check R-11-006 owns. *)
Example one_unit_of_placement_delta_decides :
  spec_admission demo_composition demo_plan demo_plan.(class_of) 3 rung_a = true
  /\ spec_admission demo_composition over_margin_plan over_margin_plan.(class_of) 3
       rung_a = false :=
  conj eq_refl eq_refl.

(* The reserved band is chargeable and has a margin of its own, which is
   what makes the slot a field rather than a constant: at the composed
   geometry the reserved slot admits one unit and refuses two where the
   focus admits five and refuses six. *)
Example the_reserved_band_slot_carries_a_charge :
  admits demo_composition charged_rung = true
  /\ admits demo_composition (charge_frame_at 0 1 charged_rung) = true
  /\ admits demo_composition (charge_frame_at 0 2 charged_rung) = false
  /\ admits demo_composition (charge_frame_at 1 5 charged_rung) = true
  /\ admits demo_composition (charge_frame_at 1 6 charged_rung) = false
  /\ admits demo_composition (charge_frame_at 2 3 charged_rung) = true
  /\ admits demo_composition (charge_frame_at 2 4 charged_rung) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

(* And the same ladder read at the slot a plan declares rather than at an
   index: charging the region's own slot on a frame whose reserved band is
   the tight one gives a margin of one where the discretionary focus gives
   five, so which slot the delta lands in is a quantity the arithmetic
   reads. *)
Definition reserved_ladder : list bool :=
  map_over (fun d => admits demo_composition
                       (charge_frame_at (reserved_charged_plan.(slot_of) 3) d
                          charged_rung))
           (upto 9).

Example the_reserved_ladder :
  reserved_ladder
  = cons true (cons true (cons false (cons false (cons false (cons false
    (cons false (cons false (cons false nil)))))))) := eq_refl.

Theorem the_reserved_slot_s_margin_is_one :
  forall n : nat,
    Nat.ltb n 9 = true -> at_list reserved_ladder n false = Nat.ltb n 2.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | [ | [ | [ | k ] ] ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* =========================================================================
   Refutation witnesses over the class assignment (R-05-166). Each is an
   alternative construction no index above generates, and each is shown to
   satisfy the obligations it does not break, so what refutes it is the
   named defect rather than the shape of the construction.
   ========================================================================= *)

Example the_demo_class_field_is_the_register_placement :
  map_over demo_plan.(class_of) (upto 8)
  = map_over (spec_assign demo_plan) (upto 8) := eq_refl.

Definition hard_task_demoted : Assignment := demote HardTaskAndHotCode demo_plan.

Definition arenas_promoted : Assignment := promote InterpreterObjectArenas demo_plan.

Definition body_demoted : Assignment := demote InterpreterBody demo_plan.

Definition scalar_demoted : Assignment := demote ScalarWorkingSet demo_plan.

(* R-15-247j's own sentence broken: hard-task code on the second class. *)
Theorem the_demoted_hard_task_code_is_refuted :
  ~ HardTaskCodeIsFirstClass demo_plan hard_task_demoted.
Proof.
  intros H. specialize (H 0 eq_refl eq_refl). cbv in H. discriminate H.
Qed.

Theorem the_demoted_hard_task_code_keeps_the_other_two_placements :
  ArenasAreSecondClass demo_plan hard_task_demoted
  /\ TheInterpreterBodyIsFirstClass demo_plan hard_task_demoted.
Proof.
  split.
  - exact (demote_keeps_other_placements demo_plan HardTaskAndHotCode
             InterpreterObjectArenas SecondClass eq_refl eq_refl).
  - exact (demote_keeps_other_placements demo_plan HardTaskAndHotCode
             InterpreterBody FirstClass eq_refl eq_refl).
Qed.

(* R-14-015's first half broken: the arenas on the first class. *)
Theorem the_promoted_arenas_are_refuted :
  ~ ArenasAreSecondClass demo_plan arenas_promoted.
Proof.
  intros H. specialize (H 1 eq_refl eq_refl). cbv in H. discriminate H.
Qed.

Theorem the_promoted_arenas_keep_the_other_two_placements :
  HardTaskCodeIsFirstClass demo_plan arenas_promoted
  /\ TheInterpreterBodyIsFirstClass demo_plan arenas_promoted.
Proof.
  split.
  - exact (promote_keeps_other_placements demo_plan InterpreterObjectArenas
             HardTaskAndHotCode FirstClass eq_refl eq_refl).
  - exact (promote_keeps_other_placements demo_plan InterpreterObjectArenas
             InterpreterBody FirstClass eq_refl eq_refl).
Qed.

(* R-14-015's second half broken: the interpreter body on the second class,
   which is the dispatch loop that entry calls the worst tenant a bulk fetch
   constant could have. *)
Theorem the_demoted_interpreter_body_is_refuted :
  ~ TheInterpreterBodyIsFirstClass demo_plan body_demoted.
Proof.
  intros H. specialize (H 4 eq_refl eq_refl). cbv in H. discriminate H.
Qed.

Theorem the_demoted_interpreter_body_keeps_the_other_two_placements :
  HardTaskCodeIsFirstClass demo_plan body_demoted
  /\ ArenasAreSecondClass demo_plan body_demoted.
Proof.
  split.
  - exact (demote_keeps_other_placements demo_plan InterpreterBody
             HardTaskAndHotCode FirstClass eq_refl eq_refl).
  - exact (demote_keeps_other_placements demo_plan InterpreterBody
             InterpreterObjectArenas SecondClass eq_refl eq_refl).
Qed.

(* And the construction that separates the whole placement discipline from
   the three placements the register makes by name: a scalar working set on
   the second class breaks R-15-247s and breaks none of the three, and its
   fetch count is zero, so the admission arithmetic does not see it either.
   The placement rule and the delta are two obligations. *)
Theorem the_demoted_scalar_working_set_keeps_all_three_named_placements :
  HardTaskCodeIsFirstClass demo_plan scalar_demoted
  /\ ArenasAreSecondClass demo_plan scalar_demoted
  /\ TheInterpreterBodyIsFirstClass demo_plan scalar_demoted.
Proof.
  split; [ | split ].
  - exact (demote_keeps_other_placements demo_plan ScalarWorkingSet
             HardTaskAndHotCode FirstClass eq_refl eq_refl).
  - exact (demote_keeps_other_placements demo_plan ScalarWorkingSet
             InterpreterObjectArenas SecondClass eq_refl eq_refl).
  - exact (demote_keeps_other_placements demo_plan ScalarWorkingSet
             InterpreterBody FirstClass eq_refl eq_refl).
Qed.

Theorem the_demoted_scalar_working_set_is_refuted :
  ~ PlacesAsTheRegisterPlaces demo_plan scalar_demoted.
Proof.
  intros H. specialize (H 2 eq_refl). cbv in H. discriminate H.
Qed.

Example the_demoted_scalar_working_set_moves_no_delta :
  placement_delta demo_plan scalar_demoted 2 = 0
  /\ spec_admission demo_composition demo_plan scalar_demoted 2 rung_a
     = spec_admission demo_composition demo_plan demo_plan.(class_of) 2 rung_a :=
  conj eq_refl eq_refl.

(* The construction R-15-247s excludes by name rather than by criterion:
   application payloads placed on one class whatever their cycle-criticality.
   It is refuted at whichever class it names, because the composed roster
   carries one payload of each criticality, and it keeps every by-name
   placement the register makes. *)
Definition payloads_named_second : Assignment :=
  by_name_payload_assign SecondClass demo_plan.

Definition payloads_named_first : Assignment :=
  by_name_payload_assign FirstClass demo_plan.

Theorem no_by_name_payload_placement_places_by_the_criterion :
  forall c : MemClass,
    ~ PlacesPayloadsByTheCriterion demo_plan (by_name_payload_assign c demo_plan).
Proof.
  intros c H. destruct c.
  - specialize (H 7 eq_refl eq_refl). cbv in H. discriminate H.
  - specialize (H 6 eq_refl eq_refl). cbv in H. discriminate H.
Qed.

Theorem the_by_name_payload_placements_keep_the_three_named_placements :
  HardTaskCodeIsFirstClass demo_plan payloads_named_second
  /\ ArenasAreSecondClass demo_plan payloads_named_second
  /\ TheInterpreterBodyIsFirstClass demo_plan payloads_named_second
  /\ HardTaskCodeIsFirstClass demo_plan payloads_named_first
  /\ ArenasAreSecondClass demo_plan payloads_named_first
  /\ TheInterpreterBodyIsFirstClass demo_plan payloads_named_first.
Proof.
  split; [ | split; [ | split; [ | split; [ | split ] ] ] ];
    unfold payloads_named_second, payloads_named_first;
    first
      [ exact (the_by_name_payload_placement_keeps_every_named_placement
                 SecondClass demo_plan HardTaskAndHotCode FirstClass eq_refl)
      | exact (the_by_name_payload_placement_keeps_every_named_placement
                 SecondClass demo_plan InterpreterObjectArenas SecondClass eq_refl)
      | exact (the_by_name_payload_placement_keeps_every_named_placement
                 SecondClass demo_plan InterpreterBody FirstClass eq_refl)
      | exact (the_by_name_payload_placement_keeps_every_named_placement
                 FirstClass demo_plan HardTaskAndHotCode FirstClass eq_refl)
      | exact (the_by_name_payload_placement_keeps_every_named_placement
                 FirstClass demo_plan InterpreterObjectArenas SecondClass eq_refl)
      | exact (the_by_name_payload_placement_keeps_every_named_placement
                 FirstClass demo_plan InterpreterBody FirstClass eq_refl) ].
Qed.

Example the_by_name_payload_placement_differs_at_one_payload :
  map_over payloads_named_second (upto 8)
  = cons FirstClass (cons SecondClass (cons FirstClass (cons SecondClass
    (cons FirstClass (cons SecondClass (cons SecondClass
    (cons SecondClass nil)))))))
  /\ map_over payloads_named_first (upto 8)
  = cons FirstClass (cons SecondClass (cons FirstClass (cons SecondClass
    (cons FirstClass (cons SecondClass (cons FirstClass
    (cons FirstClass nil)))))))
  /\ places_ok demo_plan payloads_named_second = false
  /\ places_ok demo_plan payloads_named_first = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The two demotions the arithmetic does see, which is the other half of the
   separation: the same act on a region with a fetch count is refused by
   R-11-006's own check, and the hard-task one is refused in the reserved
   band rather than in the focus. *)
Example the_demoted_hard_task_code_is_refused_by_the_arithmetic :
  placement_delta demo_plan hard_task_demoted 0 = 60
  /\ demo_plan.(slot_of) 0 = 0
  /\ spec_admission demo_composition demo_plan hard_task_demoted 0 rung_a = false :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_demoted_interpreter_body_is_refused_by_the_arithmetic :
  placement_delta demo_plan body_demoted 4 = 200
  /\ spec_admission demo_composition demo_plan body_demoted 4 rung_a = false :=
  conj eq_refl eq_refl.

(* =========================================================================
   Refutation witnesses over the placer (R-15-247, R-15-247r).
   ========================================================================= *)

Definition obs_quiet : Observation := fun _ => 0.

Definition obs_hot : Observation := fun _ => 9.

Example the_probe_observations :
  obs_quiet 0 = 0 /\ obs_hot 0 = 9 /\ obs_quiet 5 = 0 :=
  conj eq_refl (conj eq_refl eq_refl).

(* Runtime promotion: under load a bulk region becomes first-class. This is
   the hierarchy R-15-247 refuses and the feedback loop R-15-247r names by
   its temptation. *)
Theorem the_promoting_placer_is_refuted :
  ~ DecidedOnceAtComposition (promoting_placer demo_plan 0).
Proof.
  intros H. specialize (H obs_quiet obs_hot 1). cbv in H. discriminate H.
Qed.

(* And the same act downward, so the obligation excludes migration in both
   directions rather than promotion alone. *)
Theorem the_demoting_placer_is_refuted :
  ~ DecidedOnceAtComposition (demoting_placer demo_plan 0).
Proof.
  intros H. specialize (H obs_quiet obs_hot 0). cbv in H. discriminate H.
Qed.

(* Each keeps a placement the other breaks, so what refutes both is the
   runtime dependence and not a mis-placement. *)
Theorem the_promoting_placer_still_places_hard_task_code_first :
  forall o : Observation,
    HardTaskCodeIsFirstClass demo_plan (promoting_placer demo_plan 0 o).
Proof.
  intros o r _ Hk. unfold promoting_placer.
  destruct (Nat.ltb 0 (o r)).
  - reflexivity.
  - unfold spec_assign, register_place. rewrite (kind_eqb_true _ _ Hk). reflexivity.
Qed.

Theorem the_demoting_placer_still_places_the_arenas_second :
  forall o : Observation,
    ArenasAreSecondClass demo_plan (demoting_placer demo_plan 0 o).
Proof.
  intros o r _ Hk. unfold demoting_placer.
  destruct (Nat.ltb 0 (o r)).
  - reflexivity.
  - unfold spec_assign, register_place. rewrite (kind_eqb_true _ _ Hk). reflexivity.
Qed.

Example the_promoting_placer_agrees_where_nothing_is_observed :
  promoting_placer demo_plan 0 obs_quiet 1 = SecondClass
  /\ promoting_placer demo_plan 0 obs_hot 1 = FirstClass
  /\ demoting_placer demo_plan 0 obs_quiet 0 = FirstClass
  /\ demoting_placer demo_plan 0 obs_hot 0 = SecondClass :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* =========================================================================
   Refutation witnesses over the delta and the side condition it declares
   (R-15-247j, R-11-015, R-11-015a).
   ========================================================================= *)

(* A composition declaring a second class faster than the first: the side
   condition of reading 3 broken, and the truncation that follows. Nat's
   difference truncates at zero, so the plan charges nothing for a placement
   that is in fact cheaper, which is a tightening R-11-015a makes fail
   admission rather than ship. *)
Theorem a_faster_second_class_is_refuted :
  ~ SecondClassIsNoFaster fast_second_plan.
Proof. intros H. cbv in H. discriminate H. Qed.

Theorem the_faster_second_class_plan_truncates_its_delta :
  ~ DeltaIsFaithful fast_second_plan.
Proof.
  intros H. specialize (H (spec_assign fast_second_plan) 3). cbv in H.
  discriminate H.
Qed.

Example the_truncation_the_faster_second_class_produces :
  fetch_constant fast_second_plan SecondClass = 9
  /\ fast_second_plan.(first_fetch) = 10
  /\ per_fetch_delta fast_second_plan (spec_assign fast_second_plan) 3 = 0
  /\ placement_delta fast_second_plan (spec_assign fast_second_plan) 3 = 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* Its twin: everything else about the plan stands, so what refutes it is
   the declared constant and not a broken layout. *)
Theorem the_faster_second_class_plan_keeps_everything_else :
  places_ok fast_second_plan fast_second_plan.(class_of) = true
  /\ colouring_ok fast_second_plan (spec_placement fast_second_plan) = true
  /\ containment_ok fast_second_plan (spec_placement fast_second_plan) = true
  /\ slot_bases_quantized fast_second_plan = true
  /\ slot_lengths_quantized fast_second_plan = true
  /\ plan_ok fast_second_plan fast_second_plan.(placed) = true.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; [ reflexivity
    | split; [ reflexivity | split; reflexivity ] ] ] ].
Qed.

(* And a delta that reads a quantity R-11-015's derivation does not carry:
   the region's bytes rather than its fetches. Two plans agreeing on both
   class constants, on the region's fetch count and on its placement charge
   it differently, which is the property broken. *)
Theorem the_length_scaled_delta_is_refuted :
  ~ DeltaReadsThePlacementAlone length_scaled_delta.
Proof.
  intros H.
  specialize (H demo_plan shorter_region_plan demo_plan.(class_of)
                shorter_region_plan.(class_of) 3 eq_refl eq_refl eq_refl eq_refl).
  cbv in H. discriminate H.
Qed.

(* Its twin: the shorter plan is a plan, so the quantity the byte-priced
   delta reads is a declared length like any other and not a defect. Its
   lengths are still granule-quantized, its bases still representably
   aligned, and its colouring, containment and placement all stand. *)
Theorem the_shorter_region_plan_keeps_everything_else :
  slot_bases_quantized shorter_region_plan = true
  /\ slot_lengths_quantized shorter_region_plan = true
  /\ colouring_ok shorter_region_plan (spec_placement shorter_region_plan) = true
  /\ containment_ok shorter_region_plan (spec_placement shorter_region_plan) = true
  /\ places_ok shorter_region_plan shorter_region_plan.(class_of) = true.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; [ reflexivity
    | split; reflexivity ] ] ].
Qed.

Example the_two_plans_the_length_scaled_delta_separates :
  demo_plan.(fetch_count) 3 = shorter_region_plan.(fetch_count) 3
  /\ demo_plan.(class_of) 3 = shorter_region_plan.(class_of) 3
  /\ placement_delta demo_plan demo_plan.(class_of) 3
     = placement_delta shorter_region_plan shorter_region_plan.(class_of) 3
  /\ length_scaled_delta demo_plan demo_plan.(class_of) 3 = 480
  /\ length_scaled_delta shorter_region_plan shorter_region_plan.(class_of) 3
     = 320 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* =========================================================================
   Refutation witnesses over admission (R-15-247j's acceptance clause).
   ========================================================================= *)

Theorem the_reporting_admission_is_refuted :
  ~ CountsTheDelta reporting_admission.
Proof.
  intros H.
  specialize (H demo_composition over_margin_plan over_margin_plan.(class_of) 3
                rung_a eq_refl).
  cbv in H. discriminate H.
Qed.

Example the_reporting_admission_agrees_where_the_delta_is_zero :
  reporting_admission demo_composition demo_plan demo_plan.(class_of) 1 rung_a
    = spec_admission demo_composition demo_plan demo_plan.(class_of) 1 rung_a
  /\ reporting_admission demo_composition over_margin_plan
       over_margin_plan.(class_of) 3 rung_a = true :=
  conj eq_refl eq_refl.

Theorem the_brittle_admission_is_refuted :
  ~ MonotoneInTheDelta brittle_admission.
Proof.
  intros H.
  specialize (H demo_composition demo_plan (fun _ => FirstClass)
                demo_plan.(class_of) 3 rung_a eq_refl eq_refl).
  cbv in H. discriminate H.
Qed.

Example the_brittle_admission_refuses_a_costless_placement :
  brittle_admission demo_composition demo_plan demo_plan.(class_of) 3 rung_a = true
  /\ brittle_admission demo_composition demo_plan demo_plan.(class_of) 1 rung_a
     = false
  /\ brittle_admission demo_composition unit_delta_plan
       unit_delta_plan.(class_of) 3 rung_a = true :=
  conj eq_refl (conj eq_refl eq_refl).

(* And the construction that charges the discretionary focus whatever the
   region declares. On a frame whose reserved slot has less slack than its
   focus, a region charged to the reserved band is admitted by this check
   and refused by the arithmetic that reads the region's own slot, so a
   reserved-band hard-task slot is never charged at all under it. *)
Theorem the_focus_charging_admission_is_refuted :
  ~ ChargesTheRegionSOwnSlot focus_charging_admission.
Proof.
  intros H.
  specialize (H demo_composition reserved_charged_plan
                reserved_charged_plan.(class_of) 3 charged_rung).
  cbv in H. discriminate H.
Qed.

Theorem the_focus_charging_admission_does_not_count_the_delta :
  ~ CountsTheDelta focus_charging_admission.
Proof.
  intros H.
  specialize (H demo_composition reserved_charged_plan
                reserved_charged_plan.(class_of) 3 charged_rung eq_refl).
  cbv in H. discriminate H.
Qed.

Example the_slot_the_mischarge_misses :
  reserved_charged_plan.(slot_of) 3 = 0
  /\ count_of (reserved_band charged_rung) = 1
  /\ placement_delta reserved_charged_plan reserved_charged_plan.(class_of) 3 = 5
  /\ spec_admission demo_composition reserved_charged_plan
       reserved_charged_plan.(class_of) 3 charged_rung = false
  /\ focus_charging_admission demo_composition reserved_charged_plan
       reserved_charged_plan.(class_of) 3 charged_rung = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example the_focus_charging_admission_agrees_on_the_demo_plan :
  focus_charging_admission demo_composition demo_plan demo_plan.(class_of) 3 rung_a
  = spec_admission demo_composition demo_plan demo_plan.(class_of) 3 rung_a :=
  eq_refl.

(* And the construction that opts out of R-15-247j's acceptance clause
   without naming a different check at all: a plan that declares, for one
   region, a slot index the frame does not carry (reading 11). Charging
   past the frame's last slot is the identity, so the delta is computed,
   lands nowhere, and the verdict is the uncharged one. It differs from the
   reserved-charged plan in that one index and in nothing else, so what the
   pair separates is an index the frame answers to from an index it does
   not. *)
Theorem the_slot_escaping_plan_is_refuted :
  ~ ChargesOnlySlotsTheFrameHolds slot_escaping_plan charged_rung.
Proof.
  intros H.
  assert (Hs : slot_indices_held slot_escaping_plan charged_rung = true)
    by exact (slot_indices_held_complete bool slot_escaping_plan charged_rung H).
  cbv in Hs. discriminate Hs.
Qed.

(* Its twin: every other region is charged to a slot the frame does carry,
   and every other check the file ships stands, so what refutes it is the
   one index. *)
Theorem the_slot_escaping_plan_keeps_everything_else :
  plan_ok slot_escaping_plan slot_escaping_plan.(placed) = true
  /\ places_ok slot_escaping_plan slot_escaping_plan.(class_of) = true
  /\ colouring_ok slot_escaping_plan (spec_placement slot_escaping_plan) = true
  /\ containment_ok slot_escaping_plan (spec_placement slot_escaping_plan) = true
  /\ slot_bases_quantized slot_escaping_plan = true
  /\ slot_lengths_quantized slot_escaping_plan = true.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; [ reflexivity
    | split; [ reflexivity | split; reflexivity ] ] ] ].
Qed.

Example the_one_region_the_escaping_plan_charges_nowhere :
  map_over (fun r => Nat.ltb (slot_escaping_plan.(slot_of) r)
                             (count_of (frame_slots charged_rung)))
           (upto 8)
  = cons true (cons true (cons true (cons false (cons true (cons true
    (cons true (cons true nil)))))))
  /\ slot_escaping_plan.(slot_of) 3 = 3
  /\ reserved_charged_plan.(slot_of) 3 = 0 :=
  conj eq_refl (conj eq_refl eq_refl).

(* The consequence at the composed geometry: the same delta, the same
   frame, and a verdict that flips because the index names no slot. *)
Theorem the_escaped_slot_absorbs_its_whole_delta :
  forall a : Assignment,
    spec_admission demo_composition slot_escaping_plan a 3 charged_rung
    = admits demo_composition charged_rung.
Proof.
  intros a.
  exact (a_slot_the_frame_does_not_carry_absorbs_the_whole_delta demo_composition
           slot_escaping_plan a 3 charged_rung eq_refl).
Qed.

Example the_verdict_the_escaped_slot_flips :
  placement_delta slot_escaping_plan slot_escaping_plan.(class_of) 3 = 5
  /\ placement_delta reserved_charged_plan reserved_charged_plan.(class_of) 3 = 5
  /\ spec_admission demo_composition reserved_charged_plan
       reserved_charged_plan.(class_of) 3 charged_rung = false
  /\ spec_admission demo_composition slot_escaping_plan
       slot_escaping_plan.(class_of) 3 charged_rung = true
  /\ admits demo_composition charged_rung = true
  /\ charge_frame_at (slot_escaping_plan.(slot_of) 3) 5 charged_rung
     = charged_rung :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* =========================================================================
   Refutation witnesses over the narrowing check and the quantum
   (R-15-007k, R-15-007c).
   ========================================================================= *)

Definition inner_narrowing : Narrowing :=
  {| at_region := 5; offset_granules := 0; stride_granules := 1;
     dyn_index := 1; length_granules := 1 |}.

Example the_narrowing_the_plan_admits :
  granule_of demo_plan 5 = 8
  /\ narrowing_base demo_plan inner_narrowing = 2408
  /\ narrowing_granules demo_plan inner_narrowing = 301
  /\ narrowing_length demo_plan inner_narrowing = 8
  /\ spec_narrow_ok demo_plan inner_narrowing = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Theorem the_specification_narrowing_is_exact :
  Exact demo_plan inner_narrowing.
Proof.
  apply the_specification_narrowing_check_admits_only_exact_narrowings.
  reflexivity.
Qed.

(* The same narrowing over a slot base the plan did not lay at that array's
   representable alignment: the base is 2404 where a whole number of
   granules would be 2400, so the derived region rounds outward. R-15-007k
   makes that a defect in the slot plan and not a runtime event. *)
Theorem the_unquantized_slot_base_rounds_outward :
  ~ Exact unquantized_plan inner_narrowing.
Proof. intros H. cbv in H. discriminate H. Qed.

Example the_rounding_the_unquantized_base_produces :
  narrowing_base unquantized_plan inner_narrowing = 2412
  /\ granule_of unquantized_plan 5
     * narrowing_granules unquantized_plan inner_narrowing = 2408 :=
  conj eq_refl eq_refl.

Theorem the_rounding_narrowing_check_is_refuted :
  ~ AdmitsOnlyExactNarrowings rounding_narrow_ok.
Proof.
  intros H. specialize (H unquantized_plan inner_narrowing eq_refl).
  cbv in H. discriminate H.
Qed.

Theorem the_within_one_granule_check_is_refuted :
  ~ AdmitsOnlyExactNarrowings within_one_granule_narrow_ok.
Proof.
  intros H. specialize (H unquantized_plan inner_narrowing eq_refl).
  cbv in H. discriminate H.
Qed.

(* Its own boundary, which is what makes the check a rounding rather than a
   blanket acceptance: a base exactly one granule above the count the plan
   declares is refused, and one anywhere below that is admitted. *)
Example the_rounding_check_stops_at_one_granule :
  within_one_granule_narrow_ok demo_plan inner_narrowing = true
  /\ within_one_granule_narrow_ok unquantized_plan inner_narrowing = true
  /\ within_one_granule_narrow_ok off_by_one_plan inner_narrowing = false
  /\ narrowing_base off_by_one_plan inner_narrowing = 2416
  /\ granule_of off_by_one_plan 5
     * narrowing_granules off_by_one_plan inner_narrowing = 2408 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* R-15-007k's length half, refuted of a plan rather than made true by
   construction: a region declared 200 bytes long where its own
   representable granule is 2 is not laid at a granule-quantized length,
   and everything else about the plan stands. *)
Theorem the_unquantized_length_plan_is_refuted :
  ~ LengthsAreGranuleQuantized unquantized_length_plan.
Proof.
  intros H. specialize (H 6 eq_refl). cbv in H. discriminate H.
Qed.

Theorem the_unquantized_length_plan_keeps_everything_else :
  slot_lengths_quantized unquantized_length_plan = false
  /\ slot_bases_quantized unquantized_length_plan = true
  /\ colouring_ok unquantized_length_plan (spec_placement unquantized_length_plan)
     = true
  /\ containment_ok unquantized_length_plan (spec_placement unquantized_length_plan)
     = true
  /\ places_ok unquantized_length_plan unquantized_length_plan.(class_of) = true.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; [ reflexivity
    | split; reflexivity ] ] ].
Qed.

Example the_granule_the_unquantized_length_would_need :
  granule_of unquantized_length_plan 6 = 2
  /\ unquantized_length_plan.(length_of) 6 = 200
  /\ granule_of unquantized_length_plan 6
     * unquantized_length_plan.(length_granules_of) 6 = 192 :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   Reading 8's own witness, and the one this file's granule turns on
   (R-15-007c, R-15-007k).

   At the demo roster's 192-byte region the entry's bound leaves two
   granules open and its exponent leaves one. The division by 2^6 computes
   the other, which satisfies both bound clauses and is no alignment the
   encoding has; the alignment clause alone refuses it, and the base it
   would have admitted is refused with it.
   ========================================================================= *)

Definition the_divided_granule_at_the_payload : Quantum :=
  granule_inside_the_window (demo_plan.(length_of) 6)
                            (Nat.div (demo_plan.(length_of) 6) 64).

(* Its twins, and they are the whole point of the construction: it is
   byte-exact below the threshold, it is no coarser than the length over
   2^6, and it is the coarsest inside that bound, so what refutes it is the
   exponent and not an arithmetic the entry does not state. *)
Theorem the_divided_granule_keeps_every_bound_clause :
  ByteExactBelowTheThreshold the_divided_granule_at_the_payload
  /\ NoCoarserThanTheLengthOverTheSixthPower the_divided_granule_at_the_payload
  /\ TheCoarsestGranuleWithinThatBound the_divided_granule_at_the_payload.
Proof.
  exact (a_granule_inside_the_window_keeps_both_bounds
           (demo_plan.(length_of) 6) (Nat.div (demo_plan.(length_of) 6) 64)
           eq_refl eq_refl eq_refl).
Qed.

Theorem the_divided_granule_is_refuted :
  ~ AlignsOnAPowerOfTwo the_divided_granule_at_the_payload.
Proof.
  intros H. specialize (H (demo_plan.(length_of) 6)). cbv in H. discriminate H.
Qed.

Example the_window_the_two_bound_clauses_leave_open :
  demo_plan.(length_of) 6 = 192
  /\ Nat.div (demo_plan.(length_of) 6) 64 = 3
  /\ the_divided_granule_at_the_payload 192 = 3
  /\ spec_quantum 192 = 2
  /\ granule_of demo_plan 6 = 2 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* And the base that granule would have admitted, refuted of the plan that
   lays it: 225 is a whole number of threes and no whole number of twos.
   The check deciding it is complete as well as sound, so this is
   R-15-007k's obligation refused rather than a decision procedure
   answering false. *)
Theorem the_odd_base_plan_is_refuted :
  ~ BasesAreRepresentablyAligned odd_base_plan.
Proof.
  intros H.
  assert (Hq : slot_bases_quantized odd_base_plan = true)
    by exact (slot_bases_quantized_complete odd_base_plan H).
  cbv in Hq. discriminate Hq.
Qed.

Theorem the_odd_base_plan_keeps_everything_else :
  slot_bases_quantized odd_base_plan = false
  /\ slot_lengths_quantized odd_base_plan = true
  /\ colouring_ok odd_base_plan (spec_placement odd_base_plan) = true
  /\ containment_ok odd_base_plan (spec_placement odd_base_plan) = true
  /\ places_ok odd_base_plan odd_base_plan.(class_of) = true
  /\ plan_ok odd_base_plan odd_base_plan.(placed) = true.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; [ reflexivity
    | split; [ reflexivity | split; reflexivity ] ] ] ].
Qed.

Example the_odd_base_is_no_whole_number_of_its_own_granule :
  odd_base_plan.(base_of) 6 = 225
  /\ odd_base_plan.(base_granules) 6 = 75
  /\ granule_of odd_base_plan 6 = 2
  /\ granule_of odd_base_plan 6 * odd_base_plan.(base_granules) 6 = 150
  /\ base_is_quantized odd_base_plan 6 = false
  /\ demo_plan.(base_of) 6 = 224
  /\ base_is_quantized demo_plan 6 = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

(* =========================================================================
   Refutation witnesses over the layout (R-08-012, R-08-012c, R-08-014).
   ========================================================================= *)

(* A slot that runs past the top of the region its owning island's root
   capability bounds. Its colouring, its charge and its class assignment are
   all unmoved, so what refutes it is the containment alone. *)
Theorem the_island_escaping_plan_is_refuted :
  containment_ok island_escaping_plan (spec_placement island_escaping_plan) = false
  /\ Nat.leb (island_lo island_escaping_plan 4)
             (spec_placement island_escaping_plan 4) = true
  /\ Nat.leb (spec_placement island_escaping_plan 4
              + island_escaping_plan.(length_of) 4)
             (island_hi island_escaping_plan 4) = false
  /\ colouring_ok island_escaping_plan (spec_placement island_escaping_plan) = true
  /\ slot_bases_quantized island_escaping_plan = true
  /\ places_ok island_escaping_plan island_escaping_plan.(class_of) = true.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; [ reflexivity
    | split; [ reflexivity | split; reflexivity ] ] ] ].
Qed.

(* And the obligation itself refused, which is what the containment check
   being complete as well as sound buys: a false check would otherwise
   record that a decision procedure moved. *)
Theorem the_island_escaping_plan_leaves_its_island :
  ~ StaysInsideItsIsland island_escaping_plan (spec_placement island_escaping_plan).
Proof.
  intros H.
  assert (Hc : containment_ok island_escaping_plan
                 (spec_placement island_escaping_plan) = true)
    by exact (containment_ok_complete island_escaping_plan
                (spec_placement island_escaping_plan) H).
  cbv in Hc. discriminate Hc.
Qed.

(* And one that starts below its island's own base, which is the other
   conjunct of R-08-012c's containment and the one the escaping plan leaves
   standing. Without it a plan could open under its island and pass. *)
Theorem the_island_underflow_plan_is_refuted :
  containment_ok island_underflow_plan (spec_placement island_underflow_plan) = false
  /\ Nat.leb (island_lo island_underflow_plan 1)
             (spec_placement island_underflow_plan 1) = false
  /\ Nat.leb (spec_placement island_underflow_plan 1
              + island_underflow_plan.(length_of) 1)
             (island_hi island_underflow_plan 1) = true
  /\ colouring_ok island_underflow_plan (spec_placement island_underflow_plan) = true
  /\ slot_bases_quantized island_underflow_plan = true
  /\ places_ok island_underflow_plan island_underflow_plan.(class_of) = true.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; [ reflexivity
    | split; [ reflexivity | split; reflexivity ] ] ] ].
Qed.

Theorem the_island_underflow_plan_leaves_its_island :
  ~ StaysInsideItsIsland island_underflow_plan
      (spec_placement island_underflow_plan).
Proof.
  intros H.
  assert (Hc : containment_ok island_underflow_plan
                 (spec_placement island_underflow_plan) = true)
    by exact (containment_ok_complete island_underflow_plan
                (spec_placement island_underflow_plan) H).
  cbv in Hc. discriminate Hc.
Qed.

(* And the placement that would hide either of them: a report that clamps an
   escaping base back into its island contains where the plan does not. *)
Theorem the_clamped_placement_is_refuted :
  ~ ChecksThePlanSOwnBases clamped_placement.
Proof.
  intros H. specialize (H island_escaping_plan 4). cbv in H. discriminate H.
Qed.

Theorem the_clamped_placement_contains_what_the_plan_does_not :
  containment_ok island_escaping_plan (clamped_placement island_escaping_plan) = true
  /\ containment_ok island_underflow_plan (clamped_placement island_underflow_plan)
     = true
  /\ containment_ok island_escaping_plan (spec_placement island_escaping_plan)
     = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

Theorem the_clamped_placement_agrees_on_the_demo_plan :
  forall r : nat,
    Nat.ltb r demo_plan.(region_count) = true ->
    clamped_placement demo_plan r = demo_plan.(base_of) r.
Proof.
  intros r Hr.
  exact (the_clamped_placement_agrees_wherever_the_plan_stays_inside demo_plan r
           eq_refl Hr).
Qed.

(* Two regions live at once in one slot: R-08-014's side condition broken,
   with the containment, the quantization and the assignment unmoved. *)
Theorem the_overlapping_live_plan_is_refuted :
  colouring_ok overlapping_live_plan (spec_placement overlapping_live_plan) = false
  /\ containment_ok overlapping_live_plan (spec_placement overlapping_live_plan)
     = true
  /\ slot_bases_quantized overlapping_live_plan = true
  /\ places_ok overlapping_live_plan overlapping_live_plan.(class_of) = true.
Proof. split; [ reflexivity | split; [ reflexivity | split; reflexivity ] ]. Qed.

Theorem the_overlapping_live_plan_interferes :
  ~ NoInterference overlapping_live_plan (spec_placement overlapping_live_plan).
Proof.
  intros H.
  assert (Hc : colouring_ok overlapping_live_plan
                 (spec_placement overlapping_live_plan) = true)
    by exact (colouring_ok_complete overlapping_live_plan
                (spec_placement overlapping_live_plan) H).
  cbv in Hc. discriminate Hc.
Qed.

(* A slot base that is not the granule count the plan declares for it, with
   everything else standing. *)
Theorem the_unquantized_plan_is_refuted :
  slot_bases_quantized unquantized_plan = false
  /\ colouring_ok unquantized_plan (spec_placement unquantized_plan) = true
  /\ containment_ok unquantized_plan (spec_placement unquantized_plan) = true
  /\ places_ok unquantized_plan unquantized_plan.(class_of) = true.
Proof. split; [ reflexivity | split; [ reflexivity | split; reflexivity ] ]. Qed.

Theorem the_unquantized_plan_lays_a_base_off_its_own_granule :
  ~ BasesAreRepresentablyAligned unquantized_plan.
Proof.
  intros H.
  assert (Hq : slot_bases_quantized unquantized_plan = true)
    by exact (slot_bases_quantized_complete unquantized_plan H).
  cbv in Hq. discriminate Hq.
Qed.

(* And the plan that is admitted rather than refuted: two regions whose live
   ranges are disjoint share one slot, which is R-08-012's collapse of
   over-reservation onto the proven simultaneous peak (reading 7). *)
Theorem the_shared_slot_plan_is_admitted :
  colouring_ok shared_slot_plan (spec_placement shared_slot_plan) = true
  /\ slots_disjoint shared_slot_plan (spec_placement shared_slot_plan) 2 4 = false
  /\ containment_ok shared_slot_plan (spec_placement shared_slot_plan) = true
  /\ slot_bases_quantized shared_slot_plan = true.
Proof. split; [ reflexivity | split; [ reflexivity | split; reflexivity ] ]. Qed.

Theorem the_shared_slot_plan_has_no_interference :
  NoInterference shared_slot_plan (spec_placement shared_slot_plan).
Proof. apply colouring_ok_sound. reflexivity. Qed.

(* The two colourings that refuse the mechanism, one from each side. The
   strict one demands disjointness outright; the literal one is R-08-014's
   own words, disjointness over *disjoint* live ranges, which demands
   separate slots of exactly the pair R-08-012 exists to colour together
   (gap f). Both agree with the specification's colouring on a plan that
   shares no slot, so what separates them is the sharing and not a different
   arithmetic. *)
Theorem the_strict_colouring_refuses_the_mechanism :
  strict_colouring_ok demo_plan (spec_placement demo_plan) = true
  /\ colouring_ok shared_slot_plan (spec_placement shared_slot_plan) = true
  /\ strict_colouring_ok shared_slot_plan (spec_placement shared_slot_plan)
     = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

Theorem the_literal_reading_of_the_side_condition_refuses_the_mechanism :
  literal_colouring_ok demo_plan (spec_placement demo_plan) = true
  /\ literal_colouring_ok shared_slot_plan (spec_placement shared_slot_plan)
     = false
  /\ colouring_ok shared_slot_plan (spec_placement shared_slot_plan) = true.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* And it admits exactly what the reading taken refuses, which is the other
   half of why the entry's literal words cannot be meant: two regions live at
   once in one slot pass the literal side condition, because their live
   ranges are not disjoint and so the literal antecedent never fires on
   them. The two readings are not a stronger and a weaker check but opposite
   ones. *)
Theorem the_literal_reading_admits_what_the_side_condition_must_refuse :
  literal_colouring_ok overlapping_live_plan (spec_placement overlapping_live_plan)
    = true
  /\ colouring_ok overlapping_live_plan (spec_placement overlapping_live_plan)
    = false.
Proof. split; reflexivity. Qed.

(* And the two readings answer oppositely on exactly the sharing pair, which
   is what makes the inversion a reading rather than a transcription. *)
Example the_two_readings_differ_at_the_shared_pair :
  live_overlap shared_slot_plan 2 4 = false
  /\ slots_disjoint shared_slot_plan (spec_placement shared_slot_plan) 2 4 = false
  /\ live_overlap shared_slot_plan 0 2 = true
  /\ slots_disjoint shared_slot_plan (spec_placement shared_slot_plan) 0 2 = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* =========================================================================
   The origin pool's ceiling (R-14-015, R-14-009, R-14-010, R-18-004b).
   ========================================================================= *)

Example the_member_cost_under_each_placement :
  member_first_class_cost demo_plan demo_plan.(class_of) = 32
  /\ member_first_class_cost demo_plan arenas_promoted = 288
  /\ member_first_class_cost demo_plan (fun _ => SecondClass) = 0 :=
  conj eq_refl (conj eq_refl eq_refl).

(* The consequence R-14-015 books, computed: for one first-class budget the
   ceiling P is 3 with the arenas on the first class and 32 with them on the
   second. Nothing else about the plan moves. *)
Example the_origin_pool_ceiling_rises_when_the_arenas_move :
  pool_fits demo_plan arenas_promoted 3 = true
  /\ pool_fits demo_plan arenas_promoted 4 = false
  /\ pool_fits demo_plan demo_plan.(class_of) 32 = true
  /\ pool_fits demo_plan demo_plan.(class_of) 33 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem the_demo_pool_survives_every_promotion :
  forall (k : RegionKind) (n : nat),
    pool_fits demo_plan (promote k demo_plan) n = true ->
    pool_fits demo_plan (spec_assign demo_plan) n = true.
Proof.
  intros k n.
  exact (the_register_placement_admits_every_population_a_promotion_admits
           pool_fits demo_plan k n
           the_specification_bound_is_monotone_in_the_member_cost).
Qed.

(* And the bound that reads the member cost and is not monotone in it: a
   pool whose members hold no first-class bytes is refused for holding none,
   so the ceiling stops being a function of the budget. It counts the member
   cost, which is why monotonicity is a second obligation. *)
Theorem the_brittle_bound_is_refuted :
  ~ MonotoneInTheMemberCost brittle_bound.
Proof.
  intros H.
  specialize (H demo_plan demo_plan.(class_of) (fun _ => SecondClass) 32
                eq_refl eq_refl).
  cbv in H. discriminate H.
Qed.

Example the_brittle_bound_refuses_a_costless_member :
  brittle_bound demo_plan demo_plan.(class_of) 32 = true
  /\ brittle_bound demo_plan (fun _ => SecondClass) 32 = false
  /\ pool_fits demo_plan (fun _ => SecondClass) 32 = true :=
  conj eq_refl (conj eq_refl eq_refl).

Theorem the_brittle_bound_agrees_on_the_demo_placement :
  forall n : nat, brittle_bound demo_plan demo_plan.(class_of) n
                  = pool_fits demo_plan demo_plan.(class_of) n.
Proof.
  intros n.
  exact (the_brittle_bound_agrees_where_the_member_costs_something demo_plan
           demo_plan.(class_of) n eq_refl).
Qed.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared set
   R-05-164 currently makes empty, so "Closed under the global context" is
   that emptiness checked mechanically.
   ------------------------------------------------------------------------- *)

Print Assumptions any_of.
Print Assumptions map_over.
Print Assumptions filter_of.
Print Assumptions upto.
Print Assumptions before_last.
Print Assumptions at_list.
Print Assumptions occurrences.
Print Assumptions only_if.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions only_if_elim.
Print Assumptions only_if_intro.
Print Assumptions all_of_const.
Print Assumptions all_of_app.
Print Assumptions all_of_app_join.
Print Assumptions any_of_app_true.
Print Assumptions leb_split.
Print Assumptions all_of_upto.
Print Assumptions ltb_succ_r.
Print Assumptions ltb_succ_diag.
Print Assumptions all_of_upto_intro.
Print Assumptions any_of_upto_intro.
Print Assumptions all_of_at.
Print Assumptions add_0_r.
Print Assumptions add_succ_r.
Print Assumptions add_comm.
Print Assumptions add_assoc.
Print Assumptions mul_add_distr_l.
Print Assumptions sub_diag.
Print Assumptions sub_0_r.
Print Assumptions mul_0_r.
Print Assumptions add_sub_cancel.
Print Assumptions ltb_add_pos.
Print Assumptions leb_refl.
Print Assumptions leb_trans.
Print Assumptions ltb_leb_false.
Print Assumptions leb_add_l.
Print Assumptions leb_add_r.
Print Assumptions add_le_mono.
Print Assumptions mul_le_mono_l.
Print Assumptions eqb_true.
Print Assumptions eqb_refl.
Print Assumptions leb_false_ltb.
Print Assumptions leb_succ_false.
Print Assumptions leb_mul_self.
Print Assumptions leb_sub_of_add.
Print Assumptions count_of_app.
Print Assumptions the_empty_disjunction_fails.
Print Assumptions before_last_of_nothing.
Print Assumptions the_index_set_of_three.
Print Assumptions the_fallback_past_the_end.
Print Assumptions nothing_occurs_in_nothing.
Print Assumptions a_filter_that_keeps_nothing.
Print Assumptions a_map_over_nothing.
Print Assumptions only_if_is_implication.
Print Assumptions all_classes.
Print Assumptions first_class_list.
Print Assumptions second_class_list.
Print Assumptions listed_kinds.
Print Assumptions named_kinds.
Print Assumptions all_kinds.
Print Assumptions placed_by_name.
Print Assumptions criterion_class.
Print Assumptions class_eqb.
Print Assumptions class_eqb_refl.
Print Assumptions class_eqb_true.
Print Assumptions kind_eqb.
Print Assumptions kind_eqb_refl.
Print Assumptions kind_eqb_true.
Print Assumptions there_are_two_latency_classes.
Print Assumptions the_first_list_names_twelve_kinds.
Print Assumptions the_second_list_names_eight_kinds.
Print Assumptions the_two_lists_name_twenty_kinds.
Print Assumptions the_entries_place_twenty_one_kinds_by_name.
Print Assumptions the_first_list_is_all_first_class.
Print Assumptions the_second_list_is_all_second_class.
Print Assumptions the_three_placements_named_by_their_own_entries.
Print Assumptions the_interpreter_body_is_in_neither_list.
Print Assumptions one_kind_is_placed_by_criterion_and_not_by_name.
Print Assumptions the_criterion_agrees_with_the_carriers_the_entry_names.
Print Assumptions Assignment.
Print Assumptions register_place.
Print Assumptions spec_assign.
Print Assumptions places_ok.
Print Assumptions PlacesAsTheRegisterPlaces.
Print Assumptions places_ok_sound.
Print Assumptions the_specification_places_as_the_register_places.
Print Assumptions the_specification_assignment_passes_the_check.
Print Assumptions PlacesKindOn.
Print Assumptions HardTaskCodeIsFirstClass.
Print Assumptions ArenasAreSecondClass.
Print Assumptions TheInterpreterBodyIsFirstClass.
Print Assumptions PlacesPayloadsByTheCriterion.
Print Assumptions whole_placement_gives_each.
Print Assumptions the_specification_places_hard_task_code_first.
Print Assumptions the_specification_places_the_arenas_second.
Print Assumptions the_specification_places_the_interpreter_body_first.
Print Assumptions the_specification_places_payloads_by_the_criterion.
Print Assumptions demote.
Print Assumptions promote.
Print Assumptions demote_keeps_other_placements.
Print Assumptions promote_keeps_other_placements.
Print Assumptions by_name_payload_assign.
Print Assumptions the_by_name_payload_placement_keeps_every_named_placement.
Print Assumptions Observation.
Print Assumptions Placer.
Print Assumptions spec_placer.
Print Assumptions DecidedOnceAtComposition.
Print Assumptions the_specification_placer_is_decided_once.
Print Assumptions promoting_placer.
Print Assumptions demoting_placer.
Print Assumptions fetch_constant.
Print Assumptions fetch_constant_first.
Print Assumptions fetch_constant_second.
Print Assumptions placement_delta.
Print Assumptions per_fetch_delta.
Print Assumptions SecondClassIsNoFaster.
Print Assumptions DeltaIsFaithful.
Print Assumptions the_delta_is_faithful_under_the_side_condition.
Print Assumptions the_delta_is_the_count_times_the_per_fetch_delta.
Print Assumptions the_first_class_carries_no_delta.
Print Assumptions equal_constants_carry_no_delta.
Print Assumptions Delta.
Print Assumptions DeltaReadsThePlacementAlone.
Print Assumptions the_placement_delta_reads_the_placement_alone.
Print Assumptions length_scaled_delta.
Print Assumptions the_length_scaled_delta_charges_nothing_on_the_first_class.
Print Assumptions the_length_scaled_delta_charges_nothing_where_the_constants_agree.
Print Assumptions charge_slot.
Print Assumptions charge_nth.
Print Assumptions charge_band_at.
Print Assumptions charge_frame_at.
Print Assumptions charge_nth_app_lt.
Print Assumptions charge_nth_app_ge.
Print Assumptions band_slots_charge_at.
Print Assumptions major_frame_charge_at.
Print Assumptions frame_slots_charge_at.
Print Assumptions charge_nth_past_the_end.
Print Assumptions charge_band_past_the_end.
Print Assumptions charge_frame_past_the_end.
Print Assumptions disjoint_from_charge_head.
Print Assumptions disjoint_from_charge_nth.
Print Assumptions pairwise_disjoint_charge_nth.
Print Assumptions charging_moves_no_offset_and_no_width.
Print Assumptions Admission.
Print Assumptions spec_admission.
Print Assumptions reporting_admission.
Print Assumptions focus_charging_admission.
Print Assumptions CountsTheDelta.
Print Assumptions ChargesTheRegionSOwnSlot.
Print Assumptions the_specification_admission_counts_the_delta.
Print Assumptions the_specification_admission_charges_the_region_s_own_slot.
Print Assumptions slot_indices_held.
Print Assumptions ChargesOnlySlotsTheFrameHolds.
Print Assumptions slot_indices_held_sound.
Print Assumptions slot_indices_held_complete.
Print Assumptions a_slot_the_frame_does_not_carry_absorbs_the_whole_delta.
Print Assumptions IgnoresThePlan.
Print Assumptions the_reporting_admission_ignores_the_plan.
Print Assumptions the_focus_charging_admission_agrees_at_the_focus.
Print Assumptions charged_bound_mono.
Print Assumptions slot_fits_charge_mono.
Print Assumptions all_of_fits_charge_nth_mono.
Print Assumptions a_smaller_delta_is_admitted_wherever_a_larger_one_is.
Print Assumptions MonotoneInTheDelta.
Print Assumptions the_specification_admission_is_monotone_in_the_delta.
Print Assumptions the_reporting_admission_is_monotone.
Print Assumptions the_focus_charging_admission_is_monotone.
Print Assumptions brittle_admission.
Print Assumptions the_brittle_admission_counts_the_delta.
Print Assumptions pow2.
Print Assumptions pow2_step.
Print Assumptions mul_two.
Print Assumptions pow2_pos.
Print Assumptions len_lt_pow2.
Print Assumptions is_pow2.
Print Assumptions a_power_of_two_is_recognized.
Print Assumptions a_granule_the_encoding_can_align_on_and_two_it_cannot.
Print Assumptions granule_exponent.
Print Assumptions granule_exponent_step.
Print Assumptions the_exponent_of_no_fuel.
Print Assumptions representable_granule.
Print Assumptions Quantum.
Print Assumptions spec_quantum.
Print Assumptions ByteExactBelowTheThreshold.
Print Assumptions NoCoarserThanTheLengthOverTheSixthPower.
Print Assumptions TheCoarsestGranuleWithinThatBound.
Print Assumptions AlignsOnAPowerOfTwo.
Print Assumptions the_specification_quantum_is_byte_exact_below_the_threshold.
Print Assumptions granule_exponent_within_the_bound.
Print Assumptions granule_exponent_stopped_or_unspent.
Print Assumptions the_specification_quantum_is_no_coarser_than_the_bound.
Print Assumptions the_specification_quantum_is_the_coarsest_within_that_bound.
Print Assumptions the_specification_quantum_aligns_on_a_power_of_two.
Print Assumptions flat_quantum.
Print Assumptions no_plan_wide_granule_quantizes_as_the_encoding_does.
Print Assumptions the_byte_exact_plan_wide_granule_keeps_the_regime_it_does_not_break.
Print Assumptions the_byte_exact_plan_wide_granule_keeps_the_bound_and_the_alignment.
Print Assumptions the_byte_exact_plan_wide_granule_is_refuted.
Print Assumptions single_regime_quantum.
Print Assumptions the_single_regime_quantum_keeps_every_clause_above_the_threshold.
Print Assumptions the_single_regime_quantum_is_refuted.
Print Assumptions the_single_regime_quantum_breaks_at_the_entry_s_own_figure.
Print Assumptions coarser_quantum.
Print Assumptions the_coarser_quantum_keeps_the_regime_below_and_the_alignment.
Print Assumptions the_coarser_quantum_is_refuted.
Print Assumptions the_coarser_quantum_rounds_one_exponent_past_the_bound.
Print Assumptions granule_inside_the_window.
Print Assumptions a_granule_inside_the_window_keeps_both_bounds.
Print Assumptions the_two_regimes_meet_at_the_threshold.
Print Assumptions granule_of.
Print Assumptions base_is_quantized.
Print Assumptions length_is_quantized.
Print Assumptions slot_bases_quantized.
Print Assumptions slot_lengths_quantized.
Print Assumptions BasesAreRepresentablyAligned.
Print Assumptions LengthsAreGranuleQuantized.
Print Assumptions slot_bases_quantized_sound.
Print Assumptions slot_lengths_quantized_sound.
Print Assumptions slot_bases_quantized_complete.
Print Assumptions slot_lengths_quantized_complete.
Print Assumptions narrowing_granules.
Print Assumptions narrowing_base.
Print Assumptions narrowing_length.
Print Assumptions Exact.
Print Assumptions a_quantized_slot_base_narrows_exactly.
Print Assumptions a_narrowed_length_is_a_whole_number_of_granules.
Print Assumptions NarrowingCheck.
Print Assumptions spec_narrow_ok.
Print Assumptions AdmitsOnlyExactNarrowings.
Print Assumptions the_specification_narrowing_check_admits_only_exact_narrowings.
Print Assumptions rounding_narrow_ok.
Print Assumptions within_one_granule_narrow_ok.
Print Assumptions the_within_one_granule_check_admits_what_the_specification_admits.
Print Assumptions the_rounding_check_admits_what_the_specification_admits.
Print Assumptions Placement.
Print Assumptions island_lo.
Print Assumptions island_hi.
Print Assumptions inside_island.
Print Assumptions containment_ok.
Print Assumptions StaysInsideItsIsland.
Print Assumptions containment_ok_sound.
Print Assumptions containment_ok_complete.
Print Assumptions spec_placement.
Print Assumptions ChecksThePlanSOwnBases.
Print Assumptions the_specification_placement_is_the_plan_s_own_bases.
Print Assumptions the_plan_s_own_placement_stays_inside_every_island.
Print Assumptions clamped_placement.
Print Assumptions the_clamped_placement_agrees_wherever_the_plan_stays_inside.
Print Assumptions live_overlap.
Print Assumptions slots_disjoint.
Print Assumptions colouring_ok.
Print Assumptions NoInterference.
Print Assumptions colouring_ok_sound.
Print Assumptions colouring_ok_complete.
Print Assumptions strict_colouring_ok.
Print Assumptions literal_colouring_ok.
Print Assumptions each_region_once.
Print Assumptions no_stranger.
Print Assumptions plan_ok.
Print Assumptions ChargedExactlyOnce.
Print Assumptions plan_ok_sound.
Print Assumptions plan_ok_complete.
Print Assumptions plan_ok_against.
Print Assumptions WellFormedAgainstTheFrame.
Print Assumptions plan_ok_against_sound.
Print Assumptions plan_ok_against_complete.
Print Assumptions bytes_on.
Print Assumptions member_first_class_cost.
Print Assumptions PopulationBound.
Print Assumptions pool_fits.
Print Assumptions MonotoneInTheMemberCost.
Print Assumptions the_specification_bound_is_monotone_in_the_member_cost.
Print Assumptions brittle_bound.
Print Assumptions the_brittle_bound_agrees_where_the_member_costs_something.
Print Assumptions bytes_on_promote_ge.
Print Assumptions promoting_a_kind_never_lowers_the_member_cost.
Print Assumptions the_register_placement_admits_every_population_a_promotion_admits.
Print Assumptions swap_at.
Print Assumptions drop_at.
Print Assumptions insert_at.
Print Assumptions transpositions.
Print Assumptions deletions.
Print Assumptions duplications.
Print Assumptions all_masks.
Print Assumptions mask_eqb.
Print Assumptions assignment_of.
Print Assumptions the_generators_on_a_short_list.
Print Assumptions the_generators_on_nothing.
Print Assumptions the_masks_of_two.
Print Assumptions the_masks_of_nothing.
Print Assumptions mask_equality_is_pointwise.
Print Assumptions a_vector_shorter_than_the_roster_reads_the_fallback.
Print Assumptions demo_kinds.
Print Assumptions demo_critical.
Print Assumptions demo_lengths.
Print Assumptions demo_bases.
Print Assumptions demo_base_granules.
Print Assumptions demo_length_granules.
Print Assumptions demo_islands.
Print Assumptions demo_island_bases.
Print Assumptions demo_island_spans.
Print Assumptions demo_live_starts.
Print Assumptions demo_live_ends.
Print Assumptions demo_fetch_counts.
Print Assumptions demo_slots.
Print Assumptions demo_placed.
Print Assumptions demo_origin_regions.
Print Assumptions demo_kind_of.
Print Assumptions demo_cycle_critical.
Print Assumptions demo_class_of.
Print Assumptions build_plan.
Print Assumptions demo_plan.
Print Assumptions over_margin_plan.
Print Assumptions flat_plan.
Print Assumptions unit_delta_plan.
Print Assumptions fast_second_plan.
Print Assumptions shared_bases.
Print Assumptions shared_base_granules.
Print Assumptions shared_slot_plan.
Print Assumptions overlapping_bases.
Print Assumptions overlapping_base_granules.
Print Assumptions overlapping_live_plan.
Print Assumptions escaping_bases.
Print Assumptions escaping_base_granules.
Print Assumptions island_escaping_plan.
Print Assumptions underflow_bases.
Print Assumptions underflow_base_granules.
Print Assumptions island_underflow_plan.
Print Assumptions unquantized_bases.
Print Assumptions unquantized_plan.
Print Assumptions off_by_one_bases.
Print Assumptions off_by_one_plan.
Print Assumptions odd_bases.
Print Assumptions odd_base_granules.
Print Assumptions odd_base_plan.
Print Assumptions unquantized_lengths.
Print Assumptions unquantized_length_plan.
Print Assumptions shorter_lengths.
Print Assumptions shorter_length_granules.
Print Assumptions shorter_region_plan.
Print Assumptions reserved_charged_slots.
Print Assumptions reserved_charged_plan.
Print Assumptions escaped_charged_slots.
Print Assumptions slot_escaping_plan.
Print Assumptions tight_reserved.
Print Assumptions slack_background.
Print Assumptions charged_rung.
Print Assumptions the_charged_rung_moves_two_declared_bounds_and_nothing_else.
Print Assumptions the_demo_plan_declares.
Print Assumptions the_demo_rosters.
Print Assumptions the_demo_geometry.
Print Assumptions the_demo_granules_are_read_from_the_lengths.
Print Assumptions the_demo_islands_and_lives.
Print Assumptions the_demo_fetch_counts_and_slots.
Print Assumptions nothing_is_declared_past_the_roster.
Print Assumptions the_variant_plans_keep_the_class_constants.
Print Assumptions the_constant_variants_keep_every_slot.
Print Assumptions the_layout_variants_each_move_one_base.
Print Assumptions the_length_variants_each_move_one_length.
Print Assumptions spec_mask.
Print Assumptions the_demo_kinds.
Print Assumptions the_demo_classes.
Print Assumptions the_demo_class_vector_alternates.
Print Assumptions the_two_payloads_share_a_kind_and_differ_in_class.
Print Assumptions the_demo_plan_places_as_the_register_places.
Print Assumptions the_demo_plan_places_its_payloads_by_the_criterion.
Print Assumptions the_demo_plan_is_charged_exactly_once.
Print Assumptions the_demo_plan_colours_contains_and_quantizes.
Print Assumptions the_demo_plan_has_no_interference.
Print Assumptions the_demo_plan_stays_inside_its_islands.
Print Assumptions the_demo_plan_lays_every_base_at_its_representable_alignment.
Print Assumptions the_demo_plan_quantizes_every_length.
Print Assumptions the_demo_plan_is_charged_once_per_region.
Print Assumptions the_demo_plan_charges_only_slots_the_frames_hold.
Print Assumptions the_demo_plan_is_well_formed_against_the_charged_rung.
Print Assumptions the_specification_declares_the_side_condition.
Print Assumptions a_plan_whose_classes_agree_declares_the_side_condition.
Print Assumptions the_demo_plan_charges_a_faithful_delta.
Print Assumptions a_plan_whose_classes_agree_charges_nothing.
Print Assumptions the_flat_plan_carries_no_delta.
Print Assumptions the_unit_delta_plan_charges_one_fetch.
Print Assumptions the_demo_deltas.
Print Assumptions the_delta_at_the_margin_and_one_unit_past_it.
Print Assumptions an_island_holds_a_slot_at_each_of_its_own_ends.
Print Assumptions a_slot_ending_where_the_next_begins_is_disjoint.
Print Assumptions a_live_range_ending_where_the_next_begins_does_not_overlap.
Print Assumptions a_region_outside_the_roster_is_refused.
Print Assumptions a_region_claimed_twice_is_refused.
Print Assumptions a_quantized_base_and_one_that_is_not.
Print Assumptions class_masks.
Print Assumptions mask_admitted.
Print Assumptions the_class_assignment_family_size.
Print Assumptions exactly_one_assignment_places_as_the_register_places.
Print Assumptions the_one_admitted_assignment_is_the_register_s.
Print Assumptions every_assignment_but_the_register_s_is_refused.
Print Assumptions no_assignment_but_the_register_s_is_admitted.
Print Assumptions mask_transpositions.
Print Assumptions the_mask_transposition_family_size.
Print Assumptions the_first_mask_transposition.
Print Assumptions every_transposition_of_the_class_vector_is_one_of_the_assignments.
Print Assumptions every_transposition_of_the_class_vector_is_refused.
Print Assumptions no_transposed_class_vector_is_admitted.
Print Assumptions placement_deletions.
Print Assumptions placement_duplications.
Print Assumptions placement_transpositions.
Print Assumptions the_placement_family_sizes.
Print Assumptions the_first_deletion_and_the_first_duplication.
Print Assumptions every_deletion_leaves_a_region_unclaimed.
Print Assumptions every_duplication_claims_a_region_twice.
Print Assumptions no_transposition_of_the_placement_list_is_a_weakening.
Print Assumptions no_deletion_of_the_placement_list_charges_every_region.
Print Assumptions no_duplication_of_the_placement_list_charges_a_region_once.
Print Assumptions every_transposition_of_the_placement_list_is_charged_exactly_once.
Print Assumptions stranger_placement.
Print Assumptions the_stranger_placement_breaks_the_second_conjunct_alone.
Print Assumptions the_stranger_placement_is_refuted.
Print Assumptions the_stranger_is_the_first_index_the_roster_does_not_carry.
Print Assumptions margin_ladder.
Print Assumptions the_margin_ladder.
Print Assumptions the_background_slot_s_ladder_stops_earlier.
Print Assumptions every_delta_at_or_below_the_margin_is_admitted.
Print Assumptions no_delta_past_the_margin_is_admitted.
Print Assumptions one_unit_of_placement_delta_decides.
Print Assumptions the_reserved_band_slot_carries_a_charge.
Print Assumptions reserved_ladder.
Print Assumptions the_reserved_ladder.
Print Assumptions the_reserved_slot_s_margin_is_one.
Print Assumptions the_demo_class_field_is_the_register_placement.
Print Assumptions hard_task_demoted.
Print Assumptions arenas_promoted.
Print Assumptions body_demoted.
Print Assumptions scalar_demoted.
Print Assumptions the_demoted_hard_task_code_is_refuted.
Print Assumptions the_demoted_hard_task_code_keeps_the_other_two_placements.
Print Assumptions the_promoted_arenas_are_refuted.
Print Assumptions the_promoted_arenas_keep_the_other_two_placements.
Print Assumptions the_demoted_interpreter_body_is_refuted.
Print Assumptions the_demoted_interpreter_body_keeps_the_other_two_placements.
Print Assumptions the_demoted_scalar_working_set_keeps_all_three_named_placements.
Print Assumptions the_demoted_scalar_working_set_is_refuted.
Print Assumptions the_demoted_scalar_working_set_moves_no_delta.
Print Assumptions payloads_named_second.
Print Assumptions payloads_named_first.
Print Assumptions no_by_name_payload_placement_places_by_the_criterion.
Print Assumptions the_by_name_payload_placements_keep_the_three_named_placements.
Print Assumptions the_by_name_payload_placement_differs_at_one_payload.
Print Assumptions the_demoted_hard_task_code_is_refused_by_the_arithmetic.
Print Assumptions the_demoted_interpreter_body_is_refused_by_the_arithmetic.
Print Assumptions obs_quiet.
Print Assumptions obs_hot.
Print Assumptions the_probe_observations.
Print Assumptions the_promoting_placer_is_refuted.
Print Assumptions the_demoting_placer_is_refuted.
Print Assumptions the_promoting_placer_still_places_hard_task_code_first.
Print Assumptions the_demoting_placer_still_places_the_arenas_second.
Print Assumptions the_promoting_placer_agrees_where_nothing_is_observed.
Print Assumptions a_faster_second_class_is_refuted.
Print Assumptions the_faster_second_class_plan_truncates_its_delta.
Print Assumptions the_truncation_the_faster_second_class_produces.
Print Assumptions the_faster_second_class_plan_keeps_everything_else.
Print Assumptions the_length_scaled_delta_is_refuted.
Print Assumptions the_shorter_region_plan_keeps_everything_else.
Print Assumptions the_two_plans_the_length_scaled_delta_separates.
Print Assumptions the_reporting_admission_is_refuted.
Print Assumptions the_reporting_admission_agrees_where_the_delta_is_zero.
Print Assumptions the_brittle_admission_is_refuted.
Print Assumptions the_brittle_admission_refuses_a_costless_placement.
Print Assumptions the_focus_charging_admission_is_refuted.
Print Assumptions the_focus_charging_admission_does_not_count_the_delta.
Print Assumptions the_slot_the_mischarge_misses.
Print Assumptions the_focus_charging_admission_agrees_on_the_demo_plan.
Print Assumptions the_slot_escaping_plan_is_refuted.
Print Assumptions the_slot_escaping_plan_keeps_everything_else.
Print Assumptions the_one_region_the_escaping_plan_charges_nowhere.
Print Assumptions the_escaped_slot_absorbs_its_whole_delta.
Print Assumptions the_verdict_the_escaped_slot_flips.
Print Assumptions inner_narrowing.
Print Assumptions the_narrowing_the_plan_admits.
Print Assumptions the_specification_narrowing_is_exact.
Print Assumptions the_unquantized_slot_base_rounds_outward.
Print Assumptions the_rounding_the_unquantized_base_produces.
Print Assumptions the_rounding_narrowing_check_is_refuted.
Print Assumptions the_within_one_granule_check_is_refuted.
Print Assumptions the_rounding_check_stops_at_one_granule.
Print Assumptions the_unquantized_length_plan_is_refuted.
Print Assumptions the_unquantized_length_plan_keeps_everything_else.
Print Assumptions the_granule_the_unquantized_length_would_need.
Print Assumptions the_divided_granule_at_the_payload.
Print Assumptions the_divided_granule_keeps_every_bound_clause.
Print Assumptions the_divided_granule_is_refuted.
Print Assumptions the_window_the_two_bound_clauses_leave_open.
Print Assumptions the_odd_base_plan_is_refuted.
Print Assumptions the_odd_base_plan_keeps_everything_else.
Print Assumptions the_odd_base_is_no_whole_number_of_its_own_granule.
Print Assumptions the_island_escaping_plan_is_refuted.
Print Assumptions the_island_escaping_plan_leaves_its_island.
Print Assumptions the_island_underflow_plan_is_refuted.
Print Assumptions the_island_underflow_plan_leaves_its_island.
Print Assumptions the_clamped_placement_is_refuted.
Print Assumptions the_clamped_placement_contains_what_the_plan_does_not.
Print Assumptions the_clamped_placement_agrees_on_the_demo_plan.
Print Assumptions the_overlapping_live_plan_is_refuted.
Print Assumptions the_overlapping_live_plan_interferes.
Print Assumptions the_unquantized_plan_is_refuted.
Print Assumptions the_unquantized_plan_lays_a_base_off_its_own_granule.
Print Assumptions the_shared_slot_plan_is_admitted.
Print Assumptions the_shared_slot_plan_has_no_interference.
Print Assumptions the_strict_colouring_refuses_the_mechanism.
Print Assumptions the_literal_reading_of_the_side_condition_refuses_the_mechanism.
Print Assumptions the_literal_reading_admits_what_the_side_condition_must_refuse.
Print Assumptions the_two_readings_differ_at_the_shared_pair.
Print Assumptions the_member_cost_under_each_placement.
Print Assumptions the_origin_pool_ceiling_rises_when_the_arenas_move.
Print Assumptions the_demo_pool_survives_every_promotion.
Print Assumptions the_brittle_bound_is_refuted.
Print Assumptions the_brittle_bound_refuses_a_costless_member.
Print Assumptions the_brittle_bound_agrees_on_the_demo_placement.
