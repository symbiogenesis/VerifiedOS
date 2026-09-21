(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   KernelInstance.v

   What one run of one kernel instance decides, as M4.4's acceptance
   predicate states it over three questions: R-07-006's runtime half, that
   the instance derives nothing past its root's top or past a declared
   shared window's top; R-07-015's total restore, read off the commit
   trace's own `X` and `C` records rather than restated; and R-07-032's
   table-driven frame, whose order a run decides and whose duration it does
   not. Q22a's revocation interface joins the second of those: a saved image
   sanitized at R-08-006's barrier, or R-08-005b's defined filtered load
   result, is what turns total restoration into removal of stale authority,
   and neither this file nor R-07-015 gets that for free.

   This file supplies source specifications and proofs over typed traces.
   RunAnswersM44 checks the three questions, including unique attempt sites,
   identified result registers and exactly one observed register/CSR write.
   QualifiedRunAnswersM44 joins them to the semantic barrier and sanitized
   image predicates. These are not an executable target kernel. Every quantity a composition
   or the profile fixes is a field of the Kernel record rather than a
   literal, which is what keeps the R-05-163 assumption gate green while
   leaving the decision where its owner can make it. Nothing is admitted and
   nothing is axiomatized.

   What this file does not do, and it is the whole of what M4.4 still owes.
   No backend lowers a corpus member here. No C is compiled, no image is
   composed, no emulator runs, and no HTIF verdict is produced: the target
   join M4.4's dispatch note names, M1.2f's backend, M1.7's path and M3.5's
   actual initial-capability handoff, is absent, so nothing below is
   evidence that the predicate passes. What is here is the predicate itself,
   decidable, with the constructions it rejects proved rejected. The gate's
   green line means compiled, axiom-free, non-vacuous and enumerated, and it
   does not mean verified. Every state equality is stated pointwise, because
   functional extensionality is an axiom and would fail that gate.

   The Requires are load-bearing rather than decorative, on the one-owner
   rule. R-07-015's restore set is PartitionContext.v's `RestoresRegisters`
   and `RestoresNameableCsrs` and is consumed here, never restated; the
   schedule table is CyclicExecutive.v's `Frame`, and the three clauses
   below read that record's own bands rather than a second table. Both
   Requires are paid once per mutant `run.py seed coq` stages, which is the
   cost the dependency is worth here and was not worth in HandlerGraph.v.

   Readings of the register and of the trace schema this statement takes,
   each a reviewable judgment rather than a neutral transcription:

   1. A refused derivation is an untagged result and not a trap. R-15-007h
      states it outright: non-monotonic capability modification clears the
      validity tag, owes no cause code and owes no control-flow term, so a
      failed derivation is a data result. The run's observation of R-07-006's
      runtime half is therefore the `X` record's tag bit, and the adjudicator
      that reads it needs none of the 64 data bits. That is what
      `confinement_reads_the_tag_and_not_the_value` states and what
      `a_bounds_decoding_check_is_refuted` excludes, on the corpus document's
      own ground that base and top are the decode of the bounds triple and a
      second implementation of the bounds algorithm inside a reader is a
      second place for it to be wrong.
   2. The attempt list is declared and not discovered. A run cannot find the
      root's top without decoding it, so the member declares one attempt per
      question it asks and `AttemptsCover` decides that the declaration
      reaches R-07-006's whole subject: the root's top, and each of the
      statically declared shared windows. A member that attempts fewer is
      refused before any trace is read. The result register is declared too;
      unrelated untagged writes cannot witness a refusal. WellFormedAttempts
      rejects duplicate attempt PCs. The compiled corpus still has to bind
      each declared target and PC to the real over-bound instruction.
   3. The run's register domain is not the statement's. R-15-007i fixes the
      merged file at 32 registers and PartitionContext.v's `RestoresRegisters`
      quantifies over all 32, index zero included; the curated model emits no
      register-write record for index zero at all, its `wX` guarding the
      callback with `if r != 0` (model/model/core/regs.sail). So the observed
      domain here is the statement's domain less that one register, and the
      gap is closed by an architectural premise rather than by a record:
      `ZeroRegisterIsFixed` says the zero register reads alike in every
      context, which is `zero_reg : regtype = null_cap` in the model's own
      reg_type.sail and R-15-182's all-zeroes granule. That premise is
      stated, discharged nowhere in this file, and refuted of an arbitrary
      machine by `the_fixed_zero_register_is_a_premise_and_not_a_theorem`, so
      it cannot be mistaken for something the run establishes.
   4. The nameable CSR bank enters as a list and not only as a predicate.
      PartitionContext.v carries `csr_nameable` as a predicate because
      isa-profile.md section 5.1 owns the bank register by register; a
      decidable check over a trace needs the bank enumerated, because the
      obligation is that every nameable CSR was written and a predicate
      cannot be walked. `csr_roster` is that enumeration, a field with a
      covering law beside it, and gap b below records that no artifact in
      this tree carries the list itself.
   5. The `X` and `C` records are the whole of what M4.4's clause reads, and
      that is the cell's own sentence rather than a narrowing taken here. Two
      consequences follow and both are stated as theorems rather than left to
      a reader. The four capability registers outside the merged file get
      records of their own under the schema's section 4, and R-07-015's
      sentence names "capability register" alongside the general-purpose
      ones, so a burst writing MEPCC to anything at all passes this clause:
      `clause_two_does_not_read_the_capability_registers_outside_the_file`.
      And R-07-044's pending component is reached by no `X` and no `C`
      record, so two runs from one successor context can pass this clause and
      disagree on it, which is R-07-015's own no-residue criterion failing
      inside a green clause: `clause_two_admits_a_burst_that_fails_no_residue`.
      Both are gaps in the acceptance predicate rather than defects in
      PartitionContext.v, and gaps c and d book them.
   6. Total restoration is not removal of stale authority, and the two arms
      that make it so are not interchangeable. R-08-005 and R-08-005b put the
      revocation check on the capability-width load and say outright that a
      register-held capability is not revoked merely because that rule
      exists; R-08-006 makes containment complete only after every affected
      bit is published, every live root cleared, every saved context made
      restorable only through the filter, every loan cancelled and the device
      boundary reached. So a burst that satisfies R-07-015 exactly can
      install a tagged capability whose base a published bit marks, which
      `total_restoration_is_not_removal_of_stale_authority` exhibits. The
      filtered arm removes it and stops satisfying R-07-015 while doing so,
      which `a_filtered_restore_of_an_unsanitized_image_is_not_total`
      exhibits. The two meet only where the barrier already sanitized the
      saved image, which is `the_filter_is_the_identity_on_a_sanitized_image`;
      gap a books the entry that owes the choice.
   7. A run decides the frame's order and never its duration. R-15-077 leaves
      no counter to read a cycle from, the trace schema's `I` record carries
      the retire order and the decoded word and no cycle field, and R-11-006
      puts the schedulability check in a Coq artifact where CyclicExecutive.v
      discharges it as a static sum with R-11-009's switch duty inside it. So
      the frame check below is a function of the run sequence alone, which
      `the_frame_check_decides_order_and_not_duration` states, and a check
      that reads how long a slot dwelt is refuted rather than merely
      declined. The schema's own instruction that the `order` field is
      dropped when comparing is read the same way, at
      `the_frame_check_ignores_the_order_numeral`.
   8. The boundaries are the switch text and not a marker the reader invents.
      A run sequence is the maximal runs of retired instructions classified by
      whose declared extent their `pc` falls in, with the kernel's own switch
      text one such extent; a `pc` in none of them is `Astray` and refuses the
      run outright, because a reading that silently skipped it would answer a
      question about a different program. That the extents separate is a side
      condition of the reading rather than an assumption, decided by
      `ExtentsAreReadable` and refuted at a kernel whose partition text
      overlaps its switch text.
   9. The duplication axis is absent on purpose and its absence is this
      item's own name. R-15-005's emulator composes one hart, so R-07-003's
      identical text at strictly disjoint state and R-07-004's absence of
      shared mutable kernel data have no second instance to be false of.
      Nothing below quantifies over two instances, nothing below is evidence
      about them, and R2 owns that measurement over one trace format against
      a second implementation.

   What this file deliberately does not author, with the entry that owes each
   decision:

   a. Which arm of the revocation join a composition is on. R-08-006 requires
      that saved contexts cannot restore retired authority unfiltered and
      does not say whether the barrier sanitizes the saved image or the
      restore is obliged to run through R-08-005b's filtered load. The two
      differ observably against R-07-015: one satisfies the total restore and
      one does not, which is `a_filtered_restore_of_an_unsanitized_image_is_not_total`.
      Owed at R-08-006 or at R-07-015.
   b. The nameable CSR bank as an enumeration. R-07-015 quantifies over every
      CSR a partition can name and no artifact carries that list; isa-profile.md
      section 5.1 owns the bank in prose and PartitionContext.v carries a
      predicate. A run cannot walk a predicate, so `csr_roster` is a field
      here and the list is owed at its owner. Owed at R-15-001b.
   c. Whether a run must witness the four capability registers outside the
      merged file. R-07-015 names capability registers; the trace schema gives
      them `S` records of their own; M4.4's clause reads `X` and `C` records.
      Owed at R-07-015.
   d. Whether a run must witness R-07-044's pending component. That entry
      disposes of the interrupt-file pending bits at the switch and no record
      kind in the schema carries them; a store into the interrupt file would
      appear as a `W` record, which M4.4's clause does not read. Owed at
      R-07-044.
   e. Whether the zero register is inside the run's obligation. Reading 3
      says why it cannot be, and closing the gap needs an entry that states
      the architectural fact rather than a Gallina premise. Owed at R-15-007i.
   f. Every composition magnitude: the partition extents, the switch text
      extent, the shared-window count, the attempt sites, the CSR roster and
      the schedule table's widths and offsets. The demo kernel at the end
      instantiates them with arbitrary witness values that carry no
      composition claim, in CyclicExecutive.v's gap e and PartitionContext.v's
      gap j.
   g. The C implementation of the partition, switch and executive. M4.4 owns
      it; nothing here is that code, and nothing here can be compiled into it.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   decidable predicate over a trace, proved of a concrete run that satisfies
   it, and refuted of an alternative run or an alternative adjudicator the
   register's own sentence excludes. Every blindness obligation is stated of
   an arbitrary adjudicator and refuted of one that reads what the obligation
   forbids. Inhabitation is concrete: one kernel whose every domain is
   inhabited, one admitted frame, and computed checks in the silent Example
   form for the run that passes and for each run that does not.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-07-003 R-07-004 R-07-005 R-07-006
      R-07-015 R-07-032 R-07-033 R-07-036 R-07-044 R-08-005 R-08-005a R-08-005b R-08-006
      R-08-007a R-11-006 R-11-009 R-15-001b R-15-005 R-15-007h R-15-007i R-15-077 R-15-182
   SHA256: e462531d7f0c2eed39884b326a561e698cb5454876e0925d60633a10d9a840db
   (*| END derived |*)
   ========================================================================= *)

Require Import PartitionContext.
Require Import CyclicExecutive.

(* -------------------------------------------------------------------------
   List and boolean helpers the prelude does not carry and the two Requires
   do not already define. `all_of`, `count_of` and the list type come from
   CyclicExecutive.v, and are used rather than shadowed: a helper written
   twice is one fact stated twice.
   ------------------------------------------------------------------------- *)

Fixpoint any_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => false
  | cons x r => orb (p x) (any_of p r)
  end.

Fixpoint filter_of {A : Type} (p : A -> bool) (l : list A) : list A :=
  match l with
  | nil => nil
  | cons x r => if p x then cons x (filter_of p r) else filter_of p r
  end.

Fixpoint map_over {A B : Type} (f : A -> B) (l : list A) : list B :=
  match l with nil => nil | cons x r => cons (f x) (map_over f r) end.

(* 0 through n-1, in that order. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

Definition tally {A : Type} (p : A -> bool) (l : list A) : nat :=
  count_of (filter_of p l).

Definition only_if (a b : bool) : bool := orb (negb a) b.

Definition bool_eqb (a b : bool) : bool :=
  match a, b with
  | true, true => true
  | false, false => true
  | _, _ => false
  end.

Fixpoint pairwise {A : Type} (p : A -> A -> bool) (l : list A) : bool :=
  match l with
  | nil => true
  | cons x r => andb (all_of (p x) r) (pairwise p r)
  end.

(* -------------------------------------------------------------------------
   The small lemmas, proved here rather than imported for the reason
   PartitionContext.v gives of `lt_add_pos`: the stdlib modules carrying them
   are outside the prelude, and adding zero axioms is the point of the gate.
   ------------------------------------------------------------------------- *)

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof.
  intros a b H. destruct a; destruct b; try discriminate H; split; reflexivity.
Qed.

Lemma andb_join : forall a b : bool, a = true -> b = true -> andb a b = true.
Proof. intros a b Ha Hb. rewrite Ha. rewrite Hb. reflexivity. Qed.

Lemma only_if_elim : forall a b : bool, only_if a b = true -> a = true -> b = true.
Proof. intros a b H Ha. rewrite Ha in H. exact H. Qed.

Lemma bool_eqb_sound : forall a b : bool, bool_eqb a b = true -> a = b.
Proof. intros a b H. destruct a; destruct b; try discriminate H; reflexivity. Qed.

Lemma bool_eqb_holds : forall a : bool, bool_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma nat_eqb_sound : forall a b : nat, Nat.eqb a b = true -> a = b.
Proof.
  intros a. induction a as [ | x IH ]; intros b H.
  - destruct b as [ | y ]; [ reflexivity | discriminate H ].
  - destruct b as [ | y ]; [ discriminate H | rewrite (IH y H); reflexivity ].
Qed.

Lemma nat_eqb_holds : forall n : nat, Nat.eqb n n = true.
Proof. intros n. induction n as [ | k IH ]; [ reflexivity | exact IH ]. Qed.

Lemma leb_cases :
  forall g k : nat, Nat.leb g k = true -> g = k \/ Nat.leb (S g) k = true.
Proof.
  intros g. induction g as [ | g IH ]; intros k H.
  - destruct k as [ | k ]; [ left; reflexivity | right; reflexivity ].
  - destruct k as [ | k ]; [ discriminate H | ].
    destruct (IH k H) as [ Heq | Hlt ]; [ left; f_equal; exact Heq | right; exact Hlt ].
Qed.

Lemma all_of_app :
  forall (A : Type) (p : A -> bool) (l r : list A),
    all_of p (app l r) = andb (all_of p l) (all_of p r).
Proof.
  intros A p l. induction l as [ | x s IH ]; intros r.
  - reflexivity.
  - simpl. rewrite IH. destruct (p x); reflexivity.
Qed.

Lemma filter_of_app :
  forall (A : Type) (q : A -> bool) (l r : list A),
    filter_of q (app l r) = app (filter_of q l) (filter_of q r).
Proof.
  intros A q l. induction l as [ | x s IH ]; intros r.
  - reflexivity.
  - simpl. destruct (q x); rewrite IH; reflexivity.
Qed.

Lemma all_of_ext :
  forall (A : Type) (p q : A -> bool) (l : list A),
    (forall x : A, p x = q x) -> all_of p l = all_of q l.
Proof.
  intros A p q l H. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. rewrite (H x). rewrite IH. reflexivity.
Qed.

Lemma all_of_true :
  forall (A : Type) (p : A -> bool) (l : list A),
    (forall x : A, p x = true) -> all_of p l = true.
Proof.
  intros A p l H. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. rewrite (H x). rewrite IH. reflexivity.
Qed.

Lemma all_of_member :
  forall (A : Type) (eqb : A -> A -> bool),
    (forall a b : A, eqb a b = true -> a = b) ->
    forall (p : A -> bool) (l : list A) (c : A),
      all_of p l = true -> any_of (fun d => eqb c d) l = true -> p c = true.
Proof.
  intros A eqb sound p l. induction l as [ | x r IH ]; intros c Hall Hany.
  - discriminate Hany.
  - simpl in Hall. destruct (andb_split _ _ Hall) as [ Hx Hr ].
    simpl in Hany. destruct (eqb c x) eqn:E.
    + rewrite (sound c x E). exact Hx.
    + exact (IH c Hr Hany).
Qed.

Lemma all_of_filter_upto :
  forall (p q : nat -> bool) (n g : nat),
    all_of p (filter_of q (upto n)) = true ->
    Nat.ltb g n = true -> q g = true -> p g = true.
Proof.
  intros p q n. induction n as [ | n IH ]; intros g Hall Hlt Hq.
  - discriminate Hlt.
  - change (upto (S n)) with (app (upto n) (cons n nil)) in Hall.
    rewrite filter_of_app, all_of_app in Hall.
    destruct (andb_split _ _ Hall) as [ Hpre Hlast ].
    destruct (leb_cases g n Hlt) as [ Heq | Hlt2 ].
    + subst g. simpl in Hlast. rewrite Hq in Hlast. simpl in Hlast.
      destruct (p n); [ reflexivity | discriminate Hlast ].
    + exact (IH g Hpre Hlt2 Hq).
Qed.

(* =========================================================================
   Extents: the one geometric quantity a trace reader needs, and the only one
   it may compute. A partition's text extent and the kernel's switch text
   extent are composition declarations, never decodes of a capability's
   bounds triple.
   ========================================================================= *)

Record Extent : Type := { ext_base : nat; ext_top : nat }.

Definition within (e : Extent) (a : nat) : bool :=
  andb (Nat.leb (ext_base e) a) (Nat.ltb a (ext_top e)).

Definition extent_eqb (a b : Extent) : bool :=
  andb (Nat.eqb (ext_base a) (ext_base b)) (Nat.eqb (ext_top a) (ext_top b)).

Definition separated (a b : Extent) : bool :=
  orb (Nat.leb (ext_top a) (ext_base b)) (Nat.leb (ext_top b) (ext_base a)).

(* Two declared extents are readable together when they are the same extent,
   which two slots of one tenant declare, or when they do not meet. *)
Definition compatible (a b : Extent) : bool :=
  orb (extent_eqb a b) (separated a b).

Fixpoint extent_list_eqb (a b : list Extent) : bool :=
  match a, b with
  | nil, nil => true
  | cons x r, cons y t => andb (extent_eqb x y) (extent_list_eqb r t)
  | _, _ => false
  end.

(* =========================================================================
   The kernel instance: the composition it runs under, the decidable
   equalities a rig needs and a statement artifact does not, and the
   declarations a trace is read against.
   ========================================================================= *)

Record Kernel : Type := {

  (* --- the schedule and the machine beneath it, both consumed ----------- *)

  composition : Composition;

  (* --- what a decidable check needs of the machine's word type (reading 4) *)

  word_eqb : composition.(machine).(Word) -> composition.(machine).(Word) -> bool;
  word_eqb_sound :
    forall a b : composition.(machine).(Word), word_eqb a b = true -> a = b;
  word_eqb_holds : forall a : composition.(machine).(Word), word_eqb a a = true;

  csr_eqb : composition.(machine).(Csr) -> composition.(machine).(Csr) -> bool;
  csr_eqb_sound :
    forall a b : composition.(machine).(Csr), csr_eqb a b = true -> a = b;

  (* --- the CSR bank as a list, owned by isa-profile.md section 5.1 and
         enumerated by no artifact (gap b) ------------------------------- *)

  csr_roster : list composition.(machine).(Csr);
  csr_roster_covers :
    forall c : composition.(machine).(Csr),
      composition.(machine).(csr_nameable) c = true ->
      any_of (fun d => csr_eqb c d) csr_roster = true;

  (* --- the capability registers outside the merged file, which the trace
         schema gives records of their own (reading 5, gap c) ------------- *)

  Scr : Type;

  (* --- the revocation bitmap's key: R-08-005a has the loaded capability's
         base select the bit, and the decode of that base is the model's, a
         field here and never a second implementation ---------------------- *)

  Base : Type;
  base_of : composition.(machine).(Word) -> Base;

  (* --- what a run is read against (reading 8) --------------------------- *)

  switch_text : Extent;
  text_of : Tenant composition -> Extent;
  window_count : nat
}.

Definition kmachine (k : Kernel) : Machine := k.(composition).(machine).
Definition kword (k : Kernel) : Type := (kmachine k).(Word).
Definition kcsr (k : Kernel) : Type := (kmachine k).(Csr).
Definition ktenant (k : Kernel) : Type := Tenant k.(composition).

(* =========================================================================
   The commit-trace schema, version 1, as differential-corpus.md section 4
   declares it: one record per retired instruction and one per effect under
   it, the effects following the instruction that caused them. Every record
   kind that section names is carried, including the three no clause below
   reads, because a schema with a kind missing is not the schema the rig
   emits and a statement over a subset would quietly answer about a
   different stream.
   ========================================================================= *)

Inductive TraceRecord (W Cs Sr : Type) : Type :=
| RecI : nat -> nat -> nat -> TraceRecord W Cs Sr        (* order, pc, insn   *)
| RecX : nat -> bool -> W -> TraceRecord W Cs Sr         (* reg, tag, value   *)
| RecS : Sr -> bool -> W -> TraceRecord W Cs Sr          (* scr, tag, value   *)
| RecC : Cs -> W -> TraceRecord W Cs Sr                  (* csr, value        *)
| RecR : nat -> nat -> bool -> W -> TraceRecord W Cs Sr  (* addr, width, tag  *)
| RecW : nat -> nat -> bool -> W -> TraceRecord W Cs Sr  (* addr, width, tag  *)
| RecT : bool -> nat -> TraceRecord W Cs Sr.             (* interrupt, cause  *)

Arguments RecI {W Cs Sr} _ _ _.
Arguments RecX {W Cs Sr} _ _ _.
Arguments RecS {W Cs Sr} _ _ _.
Arguments RecC {W Cs Sr} _ _.
Arguments RecR {W Cs Sr} _ _ _ _.
Arguments RecW {W Cs Sr} _ _ _ _.
Arguments RecT {W Cs Sr} _ _.

Definition Trace (k : Kernel) : Type :=
  list (TraceRecord (kword k) (kcsr k) k.(Scr)).

(* The one transformation every value-blindness statement below quantifies
   over: the 64 data bits replaced by the machine's zero word, tags, register
   numbers and programme counters left standing. *)
Definition blank {W Cs Sr : Type} (z : W) (r : TraceRecord W Cs Sr)
  : TraceRecord W Cs Sr :=
  match r with
  | RecI o p i => RecI o p i
  | RecX g t _ => RecX g t z
  | RecS s t _ => RecS s t z
  | RecC c _ => RecC c z
  | RecR a w t _ => RecR a w t z
  | RecW a w t _ => RecW a w t z
  | RecT i c => RecT i c
  end.

Definition blanked (k : Kernel) (tr : Trace k) : Trace k :=
  map_over (blank (kmachine k).(zero_word)) tr.

(* The schema's own instruction that the `order` field is dropped when a
   record is compared: two executors entering through different reset vectors
   disagree on it while agreeing on everything else. *)
Definition shift_order {W Cs Sr : Type} (n : nat) (r : TraceRecord W Cs Sr)
  : TraceRecord W Cs Sr :=
  match r with
  | RecI o p i => RecI (n + o) p i
  | RecX g t v => RecX g t v
  | RecS s t v => RecS s t v
  | RecC c v => RecC c v
  | RecR a w t v => RecR a w t v
  | RecW a w t v => RecW a w t v
  | RecT i c => RecT i c
  end.

Definition reordered (k : Kernel) (n : nat) (tr : Trace k) : Trace k :=
  map_over (shift_order n) tr.

(* =========================================================================
   Question one: the root is the partition's (R-07-006, R-07-005).

   R-07-005 makes composition-time disjointness a build-time artifact, so
   what a run decides is the runtime half R-07-006 states: monotonicity lets
   the instance derive nothing outside its partition plus the statically
   declared shared windows. The member declares one attempt per question and
   each must be refused, which on this machine is an untagged result
   (reading 1).
   ========================================================================= *)

Inductive Target : Type := RootTop | WindowTop : nat -> Target.

Record Attempt : Type := { att_pc : nat; att_result_register : nat; att_target : Target }.

Definition target_eqb (a b : Target) : bool :=
  match a, b with
  | RootTop, RootTop => true
  | WindowTop i, WindowTop j => Nat.eqb i j
  | _, _ => false
  end.

Definition covers (l : list Attempt) (t : Target) : bool :=
  any_of (fun a => target_eqb (att_target a) t) l.

(* R-07-006's whole subject: the root's top, and each declared shared
   window's top. A member attempting fewer is refused before a trace is
   read, which is reading 2. *)
Definition AttemptsCover (k : Kernel) (l : list Attempt) : bool :=
  andb (covers l RootTop)
       (all_of (fun w => covers l (WindowTop w)) (upto k.(window_count))).

(* The effect under the deriving instruction, read by the schema's own rule
   that effects follow the instruction that caused them. A burst with no
   write at all is not a witnessed refusal, which is the fail-closed answer:
   the trace did not observe the derivation's result. *)
Fixpoint next_result_untagged {W Cs Sr : Type} (reg : nat) (l : list (TraceRecord W Cs Sr))
  : bool :=
  match l with
  | nil => false
  | cons (RecX g t _) r => if Nat.eqb g reg then negb t else next_result_untagged reg r
  | cons (RecI _ _ _) _ => false
  | cons _ r => next_result_untagged reg r
  end.

Fixpoint refused_at {W Cs Sr : Type} (pc reg : nat) (l : list (TraceRecord W Cs Sr))
  : bool :=
  match l with
  | nil => false
  | cons (RecI _ p _) r =>
      if Nat.eqb p pc then next_result_untagged reg r else refused_at pc reg r
  | cons _ r => refused_at pc reg r
  end.

Definition RootIsThePartitions (k : Kernel) (l : list Attempt) (tr : Trace k)
  : bool :=
  andb (AttemptsCover k l) (all_of (fun a => refused_at (att_pc a) (att_result_register a) tr) l).

(* The obligation the corpus document's section 4 states of the reader: base
   and top are the decode of the bounds triple and the rig does not re-derive
   them. Stated of an arbitrary adjudicator so that one which does is
   exhibited and refuted rather than merely differing. *)
Definition ValueBlind (k : Kernel) (adj : Trace k -> bool) : Prop :=
  forall tr : Trace k, adj (blanked k tr) = adj tr.

Lemma next_result_untagged_blank :
  forall (W Cs Sr : Type) (z : W) (reg : nat) (l : list (TraceRecord W Cs Sr)),
    next_result_untagged reg (map_over (blank z) l) = next_result_untagged reg l.
Proof.
  intros W Cs Sr z reg l. induction l as [ | r rest IH ].
  - reflexivity.
  - destruct r as [ o p i | g t v | s t v | c v | a w t v | a w t v | i c ];
      simpl; try rewrite IH; reflexivity.
Qed.

Lemma refused_at_blank :
  forall (W Cs Sr : Type) (z : W) (pc reg : nat) (l : list (TraceRecord W Cs Sr)),
    refused_at pc reg (map_over (blank z) l) = refused_at pc reg l.
Proof.
  intros W Cs Sr z pc reg l. induction l as [ | r rest IH ].
  - reflexivity.
  - destruct r as [ o p i | g t v | s t v | c v | a w t v | a w t v | i c ];
      simpl; try exact IH.
    rewrite next_result_untagged_blank, IH. reflexivity.
Qed.

(* C1 (R-07-006, R-15-007h): the confinement question is decided on tags, so
   the reader carries no second implementation of the bounds algorithm. *)
(*| discharges: R-07-006 |*)
Theorem confinement_reads_the_tag_and_not_the_value :
  forall (k : Kernel) (l : list Attempt), ValueBlind k (RootIsThePartitions k l).
Proof.
  intros k l tr. unfold RootIsThePartitions, blanked.
  f_equal. apply all_of_ext. intros a. apply refused_at_blank.
Qed.

(* =========================================================================
   Question two: the switch is total (R-07-015, R-15-007i, R-15-001b).

   PartitionContext.v states the restore over the merged file and over every
   CSR a partition can name. What a run adds is the enumeration read from the
   other side: the `X` and `C` records between two slot boundaries are that
   set with their tags and carry nothing else.
   ========================================================================= *)

Definition nonzero (g : nat) : bool := negb (Nat.eqb g 0).

(* PartitionContext.v's domain, and the run's, which is that domain less the
   one register the model emits no record for (reading 3). *)
Definition reg_domain : list nat := upto register_count.
Definition observed_registers : list nat := filter_of nonzero reg_domain.

(* Keep the imported count symbolic while checking generic trace lemmas. *)
Local Opaque register_count.
Lemma observed_register_reached :
  forall (p : nat -> bool) (g : nat),
    all_of p observed_registers = true ->
    Nat.ltb g register_count = true -> nonzero g = true -> p g = true.
Proof.
  intros p g H. exact (all_of_filter_upto p nonzero register_count g H).
Qed.

Fixpoint last_reg_write {W Cs Sr : Type} (g : nat)
    (l : list (TraceRecord W Cs Sr)) : option (bool * W) :=
  match l with
  | nil => None
  | cons (RecX h t v) r =>
      match last_reg_write g r with
      | Some found => Some found
      | None => if Nat.eqb h g then Some (t, v) else None
      end
  | cons _ r => last_reg_write g r
  end.

Fixpoint last_csr_write {W Cs Sr : Type} (eqb : Cs -> Cs -> bool) (c : Cs)
    (l : list (TraceRecord W Cs Sr)) : option W :=
  match l with
  | nil => None
  | cons (RecC d v) r =>
      match last_csr_write eqb c r with
      | Some found => Some found
      | None => if eqb c d then Some v else None
      end
  | cons _ r => last_csr_write eqb c r
  end.

(* Section 5.1's two dispositions, consumed from PartitionContext.v's fields
   rather than restated: restored where the bank restores, written to zero
   where it zeroizes. *)
Definition csr_target (k : Kernel) (succ : Context (kmachine k)) (c : kcsr k)
  : kword k :=
  if (kmachine k).(csr_zeroized) c then (kmachine k).(zero_word)
  else ctx_csr succ c.

Definition RegisterBurstTotal (k : Kernel) (succ : Context (kmachine k))
    (b : Trace k) : bool :=
  all_of (fun g =>
    match last_reg_write g b with
    | None => false
    | Some (t, v) =>
        andb (bool_eqb t (snd (ctx_reg succ g)))
             (k.(word_eqb) v (fst (ctx_reg succ g)))
    end) observed_registers.

Definition CsrBurstTotal (k : Kernel) (succ : Context (kmachine k))
    (b : Trace k) : bool :=
  all_of (fun c =>
    only_if ((kmachine k).(csr_nameable) c)
      (match last_csr_write k.(csr_eqb) c b with
       | None => false
       | Some v => k.(word_eqb) v (csr_target k succ c)
       end)) k.(csr_roster).

(* "and carry nothing else": no register write outside the merged file, and
   no CSR write the partition cannot name. *)
Definition BurstCarriesNothingElse (k : Kernel) (b : Trace k) : bool :=
  all_of (fun r =>
    match r with
    | RecX g _ _ => andb (Nat.ltb g register_count) (nonzero g)
    | RecC c _ => (kmachine k).(csr_nameable) c
    | _ => true
    end) b.

Definition SwitchIsTotal (k : Kernel) (succ : Context (kmachine k))
    (b : Trace k) : bool :=
  andb (RegisterBurstTotal k succ b)
       (andb (CsrBurstTotal k succ b) (BurstCarriesNothingElse k b)).

(* The state a burst installs on a predecessor. The pending component is
   carried from the predecessor because no `X` and no `C` record reaches it,
   which is reading 5 made structural rather than asserted. *)
Definition replay (k : Kernel) (pre : Context (kmachine k)) (b : Trace k)
  : Context (kmachine k) :=
  Build_Context (kmachine k)
    (fun g => match last_reg_write g b with
              | Some (t, v) => (v, t)
              | None => ctx_reg pre g
              end)
    (fun c => match last_csr_write k.(csr_eqb) c b with
              | Some v => v
              | None => ctx_csr pre c
              end)
    (ctx_pending pre).

(* The burst as a step relation of PartitionContext.v's own kind, which is
   what lets the run's enumeration be compared against that file's
   obligations instead of against a second statement of them. *)
Definition BurstStep (k : Kernel) (b : Trace k) : Step (kmachine k) :=
  fun succ pre post =>
    SwitchIsTotal k succ b = true
    /\ (forall g : nat, ctx_reg post g = ctx_reg (replay k pre b) g)
    /\ (forall c : kcsr k, ctx_csr post c = ctx_csr (replay k pre b) c)
    /\ ctx_pending post = ctx_pending pre.

(* PartitionContext.v's `RestoresRegisters` over the domain a run witnesses
   (reading 3). *)
Definition RestoresWitnessedRegisters (m : Machine) (R : Step m) : Prop :=
  forall succ pre post, R succ pre post ->
    forall r : nat, Nat.ltb r register_count = true -> nonzero r = true ->
      ctx_reg post r = ctx_reg succ r.

(* C2 (R-07-015, R-15-007i): a burst this clause admits restores every
   register a run can witness, value and validity tag together. *)
(*| discharges: R-07-015 |*)
Theorem the_burst_restores_every_witnessed_register :
  forall (k : Kernel) (b : Trace k),
    RestoresWitnessedRegisters (kmachine k) (BurstStep k b).
Proof.
  intros k b succ pre post Hstep r Hr Hnz.
  destruct Hstep as [ Htotal [ Hreg _ ] ].
  rewrite (Hreg r).
  destruct (andb_split _ _ Htotal) as [ Hregs _ ].
  assert (Hp := observed_register_reached _ r Hregs Hr Hnz).
  unfold replay. simpl in Hp |- *.
  destruct (last_reg_write r b) as [ [ t v ] | ].
  - destruct (andb_split _ _ Hp) as [ Ht Hv ].
    rewrite (bool_eqb_sound _ _ Ht). rewrite (k.(word_eqb_sound) _ _ Hv).
    destruct (ctx_reg succ r). reflexivity.
  - discriminate Hp.
Qed.

(* C2b (R-07-015, R-15-001b): and writes every CSR the partition can name,
   restored or zeroized as the profile's own disposition says. *)
(*| discharges: R-07-015 |*)
Theorem the_burst_restores_every_nameable_csr :
  forall (k : Kernel) (b : Trace k),
    RestoresNameableCsrs (kmachine k) (BurstStep k b).
Proof.
  intros k b succ pre post Hstep c Hc.
  destruct Hstep as [ Htotal [ _ [ Hcsr _ ] ] ].
  rewrite (Hcsr c).
  destruct (andb_split _ _ Htotal) as [ _ Hrest ].
  destruct (andb_split _ _ Hrest) as [ Hcsrs _ ].
  assert (Hm := k.(csr_roster_covers) c Hc).
  assert (Hp := all_of_member _ k.(csr_eqb) k.(csr_eqb_sound) _ _ c Hcsrs Hm).
  assert (Hq := only_if_elim _ _ Hp Hc).
  unfold replay. simpl.
  destruct (last_csr_write k.(csr_eqb) c b) as [ v | ].
  - rewrite (k.(word_eqb_sound) _ _ Hq). unfold csr_target. reflexivity.
  - discriminate Hq.
Qed.

(* The premise reading 3 names, stated so it cannot be mistaken for something
   the run establishes: the zero register reads alike in every context. *)
Definition ZeroRegisterIsFixed (m : Machine) : Prop :=
  forall c d : Context m, ctx_reg c 0 = ctx_reg d 0.

(* C2c (R-07-015): with that premise the run's enumeration gives
   PartitionContext.v's own totality, and without it it does not. *)
(*| discharges: R-07-015 |*)
Theorem a_fixed_zero_register_closes_the_gap :
  forall (k : Kernel) (b : Trace k),
    ZeroRegisterIsFixed (kmachine k) ->
    RestoresRegisters (kmachine k) (BurstStep k b).
Proof.
  intros k b Hfix succ pre post Hstep r Hr.
  destruct (Nat.eqb r 0) eqn:E.
  - rewrite (nat_eqb_sound r 0 E). apply Hfix.
  - apply (the_burst_restores_every_witnessed_register k b succ pre post Hstep r Hr).
    unfold nonzero. rewrite E. reflexivity.
Qed.

(* =========================================================================
   Question three: the frame is the table's (R-07-032, R-07-033, R-07-036).

   R-07-032 makes the executive table-driven with no runtime scheduling
   decision, and a runtime decision is observable as a departure from the
   declared order. The duration is not a run's to take (reading 7).
   ========================================================================= *)

Inductive Site : Type :=
| AtSwitch : Site
| AtSlot : Extent -> Site
| Astray : nat -> Site.

Definition site_eqb (a b : Site) : bool :=
  match a, b with
  | AtSwitch, AtSwitch => true
  | AtSlot e, AtSlot d => extent_eqb e d
  | Astray p, Astray q => Nat.eqb p q
  | _, _ => false
  end.

Fixpoint locate (l : list Extent) (pc : nat) : option Extent :=
  match l with
  | nil => None
  | cons e r => if within e pc then Some e else locate r pc
  end.

Definition site_of (k : Kernel) (ext : list Extent) (pc : nat) : Site :=
  if within k.(switch_text) pc then AtSwitch
  else match locate ext pc with
       | Some e => AtSlot e
       | None => Astray pc
       end.

Fixpoint pcs {W Cs Sr : Type} (l : list (TraceRecord W Cs Sr)) : list nat :=
  match l with
  | nil => nil
  | cons (RecI _ p _) r => cons p (pcs r)
  | cons _ r => pcs r
  end.

(* Maximal runs: consecutive retires at one site are one visit. This is where
   duration leaves the reading, and it leaves it in the definition rather
   than in a convention. *)
Fixpoint runs (l : list Site) : list Site :=
  match l with
  | nil => nil
  | cons s tail =>
      match tail with
      | nil => cons s nil
      | cons t r => if site_eqb s t then runs tail else cons s (runs tail)
      end
  end.

Definition declared_extents (k : Kernel) (f : Frame (ktenant k)) : list Extent :=
  map_over (fun s => k.(text_of) (slot_tenant s)) (frame_slots f).

Definition reserved_extents (k : Kernel) (f : Frame (ktenant k)) : list Extent :=
  map_over (fun s => k.(text_of) (slot_tenant s)) (reserved_band f).

Definition sites (k : Kernel) (f : Frame (ktenant k)) (tr : Trace k) : list Site :=
  runs (map_over (site_of k (declared_extents k f)) (pcs tr)).

Fixpoint slot_visits (l : list Site) : list Extent :=
  match l with
  | nil => nil
  | cons (AtSlot e) r => cons e (slot_visits r)
  | cons _ r => slot_visits r
  end.

Definition is_switch (s : Site) : bool :=
  match s with AtSwitch => true | _ => false end.

Definition is_astray (s : Site) : bool :=
  match s with Astray _ => true | _ => false end.

(* The side condition of the reading itself (reading 8): a pc decides one
   site, or the classification is not a function of the declaration. *)
Definition ExtentsAreReadable (k : Kernel) (f : Frame (ktenant k)) : bool :=
  andb (pairwise compatible (declared_extents k f))
       (all_of (fun e => separated k.(switch_text) e) (declared_extents k f)).

Definition ReservedEnteredOnce (k : Kernel) (f : Frame (ktenant k))
    (tr : Trace k) : bool :=
  all_of (fun e =>
    Nat.eqb (tally (extent_eqb e) (slot_visits (sites k f tr)))
            (tally (extent_eqb e) (reserved_extents k f)))
    (reserved_extents k f).

Definition SwitchesInTableOrder (k : Kernel) (f : Frame (ktenant k))
    (tr : Trace k) : bool :=
  extent_list_eqb (slot_visits (sites k f tr)) (declared_extents k f).

Definition NoUnnamedSwitch (k : Kernel) (f : Frame (ktenant k))
    (tr : Trace k) : bool :=
  andb (Nat.eqb (tally is_switch (sites k f tr)) (count_of (declared_extents k f)))
       (Nat.eqb (tally is_astray (sites k f tr)) 0).

Definition FrameIsTheTables (k : Kernel) (f : Frame (ktenant k))
    (tr : Trace k) : bool :=
  andb (ExtentsAreReadable k f)
       (andb (ReservedEnteredOnce k f tr)
             (andb (SwitchesInTableOrder k f tr) (NoUnnamedSwitch k f tr))).

(* The obligation reading 7 states, of an arbitrary adjudicator: two runs
   with one run sequence receive one verdict, whatever they spent inside a
   slot. *)
Definition RunBlind (k : Kernel) (f : Frame (ktenant k))
    (adj : Trace k -> bool) : Prop :=
  forall tr tr' : Trace k, sites k f tr = sites k f tr' -> adj tr = adj tr'.

(* C3 (R-07-032, R-07-033, R-07-036, R-15-077): what a run decides is the
   order. R-11-006 puts the duration in a Coq artifact and CyclicExecutive.v
   is that artifact, so a retire count held against a bound here would
   restate a discharged obligation in a unit this machine does not carry. *)
(*| discharges: R-07-032 |*)
Theorem the_frame_check_decides_order_and_not_duration :
  forall (k : Kernel) (f : Frame (ktenant k)), RunBlind k f (FrameIsTheTables k f).
Proof.
  intros k f tr tr' H.
  unfold FrameIsTheTables, ReservedEnteredOnce, SwitchesInTableOrder,
         NoUnnamedSwitch.
  rewrite H. reflexivity.
Qed.

Lemma pcs_shift :
  forall (W Cs Sr : Type) (n : nat) (l : list (TraceRecord W Cs Sr)),
    pcs (map_over (shift_order n) l) = pcs l.
Proof.
  intros W Cs Sr n l. induction l as [ | r rest IH ].
  - reflexivity.
  - destruct r as [ o p i | g t v | s t v | c v | a w t v | a w t v | i c ];
      simpl; rewrite IH; reflexivity.
Qed.

(* C3b: the `order` field is emitted and dropped from the compared record,
   so no verdict may turn on its numeral. *)
(*| discharges: R-07-032 |*)
Theorem the_frame_check_ignores_the_order_numeral :
  forall (k : Kernel) (f : Frame (ktenant k)) (n : nat) (tr : Trace k),
    FrameIsTheTables k f (reordered k n tr) = FrameIsTheTables k f tr.
Proof.
  intros k f n tr.
  unfold FrameIsTheTables, ReservedEnteredOnce, SwitchesInTableOrder,
         NoUnnamedSwitch, sites, reordered.
  rewrite pcs_shift. reflexivity.
Qed.

(* =========================================================================
   The revocation join (R-08-005, R-08-005a, R-08-005b, R-08-006, R-08-007a),
   which Q22a's qualification hands M4.4 on the single-hart path. Two
   sentences of that output are what this section is stated against: an epoch
   mark alone cannot witness semantic completion, and total restoration alone
   establishes no removal of stale authority.
   ========================================================================= *)

(* R-08-005b: the load's own definition permits the revocation-driven tag
   clear, the loaded capability's base selecting the bit. *)
Definition filtered (k : Kernel) (bm : k.(Base) -> bool) (t : bool) (v : kword k)
  : bool :=
  andb t (negb (bm (k.(base_of) v))).

Definition BurstCarriesNoStaleAuthority (k : Kernel) (bm : k.(Base) -> bool)
    (b : Trace k) : bool :=
  all_of (fun r =>
    match r with
    | RecX _ t v => only_if t (negb (bm (k.(base_of) v)))
    | _ => true
    end) b.

Definition ImageIsSanitized (k : Kernel) (bm : k.(Base) -> bool)
    (succ : Context (kmachine k)) : bool :=
  all_of (fun g =>
    only_if (snd (ctx_reg succ g)) (negb (bm (k.(base_of) (fst (ctx_reg succ g))))))
    observed_registers.

(* The two shapes of restore burst the register leaves open (gap a): the
   saved image written out as it stands, and the same image written out
   through R-08-005b's filter. *)
Definition image_burst (k : Kernel) (succ : Context (kmachine k)) : Trace k :=
  map_over (fun g => RecX g (snd (ctx_reg succ g)) (fst (ctx_reg succ g)))
           observed_registers.

Definition filtered_burst (k : Kernel) (bm : k.(Base) -> bool)
    (succ : Context (kmachine k)) : Trace k :=
  map_over (fun g =>
    RecX g (filtered k bm (snd (ctx_reg succ g)) (fst (ctx_reg succ g)))
           (fst (ctx_reg succ g)))
    observed_registers.

Definition csr_burst (k : Kernel) (succ : Context (kmachine k)) : Trace k :=
  map_over (fun c => RecC c (csr_target k succ c))
           (filter_of (kmachine k).(csr_nameable) k.(csr_roster)).

Definition full_burst (k : Kernel) (succ : Context (kmachine k)) : Trace k :=
  app (image_burst k succ) (csr_burst k succ).

Definition filtered_full_burst (k : Kernel) (bm : k.(Base) -> bool)
    (succ : Context (kmachine k)) : Trace k :=
  app (filtered_burst k bm succ) (csr_burst k succ).

Lemma all_of_map :
  forall (A B : Type) (p : B -> bool) (f : A -> B) (l : list A),
    all_of p (map_over f l) = all_of (fun x => p (f x)) l.
Proof.
  intros A B p f l. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

Lemma only_if_filtered :
  forall t b : bool, only_if (andb t (negb b)) (negb b) = true.
Proof. intros t b. destruct t; destruct b; reflexivity. Qed.

(* R1 (R-08-005b): a filtered restore installs no authority the published
   bitmap marks, whatever the saved image held. *)
(*| discharges: R-08-005b |*)
Theorem a_filtered_restore_carries_no_marked_authority :
  forall (k : Kernel) (bm : k.(Base) -> bool) (succ : Context (kmachine k)),
    BurstCarriesNoStaleAuthority k bm (filtered_burst k bm succ) = true.
Proof.
  intros k bm succ.
  unfold BurstCarriesNoStaleAuthority, filtered_burst.
  rewrite all_of_map.
  apply all_of_true. intros g. unfold filtered. apply only_if_filtered.
Qed.

(* R2 (R-08-006): where the barrier sanitized the saved image, the filter is
   the identity on it, which is the one place the two arms of gap a agree. *)
(*| discharges: R-08-006 |*)
Theorem the_filter_is_the_identity_on_a_sanitized_image :
  forall (k : Kernel) (bm : k.(Base) -> bool) (succ : Context (kmachine k)),
    ImageIsSanitized k bm succ = true ->
    forall g : nat, Nat.ltb g register_count = true -> nonzero g = true ->
      filtered k bm (snd (ctx_reg succ g)) (fst (ctx_reg succ g))
        = snd (ctx_reg succ g).
Proof.
  intros k bm succ Hsan g Hg Hnz.
  assert (Hp := observed_register_reached _ g Hsan Hg Hnz).
  simpl in Hp. unfold filtered.
  destruct (snd (ctx_reg succ g)) eqn:Et.
  - assert (Hb := only_if_elim _ _ Hp eq_refl). rewrite Hb. reflexivity.
  - reflexivity.
Qed.

(* Completion, as R-08-006 enumerates it and Q22a hands it to M4.4 on the
   single-hart path. The epoch is a field and deliberately not a conjunct:
   that entry's own sentence is that advancing it does not establish
   containment. The static proxy acknowledgement R-08-006 also requires is
   absent here rather than assumed away: one hart has no peer to acknowledge,
   and R2 owns the multi-hart and proxy join. *)
Record Completion : Type := {
  bits_published : bool;
  epoch_advanced : bool;
  resident_roots_cleared : bool;
  saved_contexts_filtered : bool;
  loans_cancelled : bool;
  device_boundary_reached : bool
}.

Definition SemanticCompletion (c : Completion) : bool :=
  andb (bits_published c)
    (andb (resident_roots_cleared c)
      (andb (saved_contexts_filtered c)
        (andb (loans_cancelled c) (device_boundary_reached c)))).

Definition RefusesAResidentRoot (p : Completion -> bool) : Prop :=
  forall c : Completion, resident_roots_cleared c = false -> p c = false.

Definition RefusesAnUnfilteredSavedContext (p : Completion -> bool) : Prop :=
  forall c : Completion, saved_contexts_filtered c = false -> p c = false.

Definition RefusesAnOutstandingLoan (p : Completion -> bool) : Prop :=
  forall c : Completion, loans_cancelled c = false -> p c = false.

Definition RefusesAnOpenDeviceBoundary (p : Completion -> bool) : Prop :=
  forall c : Completion, device_boundary_reached c = false -> p c = false.

(* R3 (R-08-006): the three predicates Q22a names, and the device boundary
   beside them. *)
(*| discharges: R-08-006 |*)
Theorem completion_refuses_a_resident_root :
  RefusesAResidentRoot SemanticCompletion.
Proof.
  intros c H. unfold SemanticCompletion. rewrite H.
  destruct (bits_published c); reflexivity.
Qed.

(*| discharges: R-08-006 |*)
Theorem completion_refuses_an_unfiltered_saved_context :
  RefusesAnUnfilteredSavedContext SemanticCompletion.
Proof.
  intros c H. unfold SemanticCompletion. rewrite H.
  destruct (bits_published c); destruct (resident_roots_cleared c); reflexivity.
Qed.

(*| discharges: R-08-006 |*)
Theorem completion_refuses_an_outstanding_loan :
  RefusesAnOutstandingLoan SemanticCompletion.
Proof.
  intros c H. unfold SemanticCompletion. rewrite H.
  destruct (bits_published c); destruct (resident_roots_cleared c);
    destruct (saved_contexts_filtered c); reflexivity.
Qed.

(*| discharges: R-08-006 |*)
Theorem completion_refuses_an_open_device_boundary :
  RefusesAnOpenDeviceBoundary SemanticCompletion.
Proof.
  intros c H. unfold SemanticCompletion. rewrite H.
  destruct (bits_published c); destruct (resident_roots_cleared c);
    destruct (saved_contexts_filtered c); destruct (loans_cancelled c);
    reflexivity.
Qed.

(* The reading Q22a warns against, as a predicate rather than as a sentence.
   R-08-007a makes the epoch a monotone counter naming containment events;
   reading it is not deciding one. *)
Definition epoch_completion (c : Completion) : bool := epoch_advanced c.

(* =========================================================================
   A kernel whose every domain is inhabited, for R-05-165's uninhabited
   domain mode and for the refutation witnesses. Every magnitude below is an
   arbitrary witness value carrying no composition claim (gap f).
   ========================================================================= *)

(* Three CSRs: two the partition can name, one it cannot, and of the two
   nameable ones section 5.1's two dispositions are exercised one each. *)
Definition kernel_machine : Machine := {|
  Csr := nat;
  csr_nameable := fun c => Nat.ltb c 2;
  csr_zeroized := fun c => Nat.eqb c 0;
  Word := bool;
  zero_word := false;
  Pending := bool;
  pending_swapped := true;
  pending_partition := fun p => negb p;
  rotation_swaps_pending := true;
  fence_t_cost := 7;
  vmclear_cost := 5;
  opp_relock_cost := 3;
  drain_cost := 2
|}.

Definition kernel_composition : Composition := {|
  machine := kernel_machine;
  boundary_inputs := BoundaryCost.demo_boundary_inputs;
  Tenant := nat;
  harmonic := fun _ _ => true;
  focus_majority := fun w total => Nat.leb total (w + w);
  rung_of_count := fun n => n;
  top_rung_capacity := 2;
  table_load_cost := 4
|}.

Lemma kernel_roster_covers :
  forall c : nat, kernel_machine.(csr_nameable) c = true ->
    any_of (fun d => Nat.eqb c d) (cons 0 (cons 1 (cons 2 nil))) = true.
Proof.
  intros c H. destruct c as [ | [ | c2 ] ];
    [ reflexivity | reflexivity | discriminate H ].
Qed.

Definition partition_text (t : nat) : Extent :=
  match t with
  | 0 => {| ext_base := 1000; ext_top := 1100 |}
  | 1 => {| ext_base := 2000; ext_top := 2100 |}
  | _ => {| ext_base := 3000; ext_top := 3100 |}
  end.

Definition kernel_at (tx : nat -> Extent) (sw : Extent) : Kernel := {|
  composition := kernel_composition;
  word_eqb := bool_eqb;
  word_eqb_sound := bool_eqb_sound;
  word_eqb_holds := bool_eqb_holds;
  csr_eqb := Nat.eqb;
  csr_eqb_sound := nat_eqb_sound;
  csr_roster := cons 0 (cons 1 (cons 2 nil));
  csr_roster_covers := kernel_roster_covers;
  Scr := bool;
  Base := bool;
  base_of := fun v => v;
  switch_text := sw;
  text_of := tx;
  window_count := 2
|}.

Definition demo_kernel : Kernel :=
  kernel_at partition_text {| ext_base := 100; ext_top := 200 |}.

(* A kernel whose partition text overlaps its own switch text, which is the
   construction reading 8's side condition excludes. *)
Definition overlapping_kernel : Kernel :=
  kernel_at (fun _ => {| ext_base := 150; ext_top := 250 |})
            {| ext_base := 100; ext_top := 200 |}.

(* The schedule table, in CyclicExecutive.v's own record and admitted by that
   file's own check, so the table a run is read against is the table the
   generation proved. *)
Definition kernel_reserved : list (Slot nat) :=
  cons (Build_Slot nat 60 0 40 100 0) nil.

Definition kernel_band : Band nat :=
  Build_Band nat (Build_Slot nat 90 60 70 100 1)
                 (cons (Build_Slot nat 50 150 30 100 2) nil).

Definition kernel_frame : Frame nat :=
  Build_Frame nat 200 0 kernel_reserved kernel_band.

Example the_demo_table_is_admitted :
  admits kernel_composition kernel_frame = true := eq_refl.

Example the_demo_extents_are_readable :
  ExtentsAreReadable demo_kernel kernel_frame = true := eq_refl.

(* =========================================================================
   Question one at the demo: the run that answers it, and the three
   constructions it refuses.
   ========================================================================= *)

Local Transparent register_count.
Definition demo_attempts : list Attempt :=
  cons {| att_pc := 300; att_result_register := 8; att_target := RootTop |}
  (cons {| att_pc := 304; att_result_register := 9; att_target := WindowTop 0 |}
  (cons {| att_pc := 308; att_result_register := 10; att_target := WindowTop 1 |} nil)).

(* A member that skips one declared shared window. *)
Definition short_attempts : list Attempt :=
  cons {| att_pc := 300; att_result_register := 8; att_target := RootTop |}
  (cons {| att_pc := 304; att_result_register := 9; att_target := WindowTop 0 |} nil).

Definition at_pc (p : nat) : TraceRecord bool nat bool := RecI 0 p 0.

Definition confinement_trace : Trace demo_kernel :=
  cons (at_pc 300) (cons (RecX 8 false true)
  (cons (at_pc 304) (cons (RecX 9 false true)
  (cons (at_pc 308) (cons (RecX 10 false true) nil))))).

(* The same run with one derivation retaining its validity tag, which is the
   derivation R-07-006 says monotonicity does not permit. *)
Definition admitted_derivation_trace : Trace demo_kernel :=
  cons (at_pc 300) (cons (RecX 8 false true)
  (cons (at_pc 304) (cons (RecX 9 true true)
  (cons (at_pc 308) (cons (RecX 10 false true) nil))))).

Example the_declared_attempts_are_all_refused :
  RootIsThePartitions demo_kernel demo_attempts confinement_trace = true
  := eq_refl.

Example a_derivation_that_kept_its_tag_is_refused :
  RootIsThePartitions demo_kernel demo_attempts admitted_derivation_trace = false
  := eq_refl.

Example a_member_skipping_a_declared_window_is_refused :
  RootIsThePartitions demo_kernel short_attempts confinement_trace = false
  := eq_refl.

(* An adjudicator that decodes a bound out of the 64 data bits, which is the
   second implementation of the bounds algorithm the corpus document refuses
   to put inside a reader. *)
Definition decoding_check (k : Kernel) (top : kword k -> nat) (limit : nat)
    (l : list Attempt) (tr : Trace k) : bool :=
  andb (RootIsThePartitions k l tr)
       (all_of (fun r =>
          match r with
          | RecX _ _ v => Nat.leb (top v) limit
          | _ => true
          end) tr).

Definition demo_top (v : bool) : nat := if v then 1 else 0.

(*| discharges: R-07-006 |*)
Theorem a_bounds_decoding_check_is_refuted :
  ~ ValueBlind demo_kernel
      (decoding_check demo_kernel demo_top 0 demo_attempts).
Proof.
  intros H. specialize (H confinement_trace). cbv in H. discriminate H.
Qed.

(* =========================================================================
   Question two at the demo: the burst that answers it, the four
   constructions it refuses, and the two components the clause does not
   reach.
   ========================================================================= *)

(* A successor image every one of whose registers carries a tagged value
   whose base is the one the demo bitmap marks. *)
Definition succ_image : Context (kmachine demo_kernel) :=
  Build_Context (kmachine demo_kernel) (fun _ => (true, true)) (fun _ => true) true.

(* The same shape at the other base, which the demo bitmap does not mark. *)
Definition unmarked_succ : Context (kmachine demo_kernel) :=
  Build_Context (kmachine demo_kernel) (fun _ => (false, true)) (fun _ => true) true.

Definition pre_low : Context (kmachine demo_kernel) :=
  Build_Context (kmachine demo_kernel) (fun _ => (false, false)) (fun _ => false) false.

Definition pre_high : Context (kmachine demo_kernel) :=
  Build_Context (kmachine demo_kernel) (fun _ => (false, false)) (fun _ => false) true.

Definition restore_burst : Trace demo_kernel := full_burst demo_kernel succ_image.

Example the_restore_burst_is_total :
  SwitchIsTotal demo_kernel succ_image restore_burst = true := eq_refl.

(* A restore truncated to the low registers, which is the first of
   PartitionContext.v's own three refuting constructions read at the run. *)
Definition truncated_burst : Trace demo_kernel :=
  app (map_over (fun g => RecX g true true) (filter_of nonzero (upto 16)))
      (csr_burst demo_kernel succ_image).

Example a_restore_truncated_to_the_low_registers_is_refused :
  SwitchIsTotal demo_kernel succ_image truncated_burst = false := eq_refl.

(* A restore that writes each register's 64 data bits and drops its validity
   tag, which is the second. *)
Definition tagless_burst : Trace demo_kernel :=
  app (map_over (fun g => RecX g false true) observed_registers)
      (csr_burst demo_kernel succ_image).

Example a_restore_dropping_a_validity_tag_is_refused :
  SwitchIsTotal demo_kernel succ_image tagless_burst = false := eq_refl.

(* A restore exempting one nameable CSR, which is the third. *)
Definition exempting_burst : Trace demo_kernel :=
  app (image_burst demo_kernel succ_image) (cons (RecC 0 false) nil).

Example a_restore_exempting_a_nameable_csr_is_refused :
  SwitchIsTotal demo_kernel succ_image exempting_burst = false := eq_refl.

(* And the clause's own second half: a burst carrying something else. *)
Definition wide_burst : Trace demo_kernel :=
  app restore_burst (cons (RecX 40 true true) nil).

Definition unnameable_csr_burst : Trace demo_kernel :=
  app restore_burst (cons (RecC 2 true) nil).

Example a_write_outside_the_merged_file_is_refused :
  SwitchIsTotal demo_kernel succ_image wide_burst = false := eq_refl.

Example a_write_to_a_csr_the_partition_cannot_name_is_refused :
  SwitchIsTotal demo_kernel succ_image unnameable_csr_burst = false := eq_refl.

(* Reading 5, made checkable rather than asserted. The four capability
   registers outside the merged file get records of their own, and this
   clause reads none of them, so a burst installing any value at all in one
   passes. *)
Definition burst_with_scr (v : bool) : Trace demo_kernel :=
  app restore_burst (cons (RecS true true v) nil).

(*| discharges: R-07-015 |*)
Theorem clause_two_does_not_read_the_capability_registers_outside_the_file :
  SwitchIsTotal demo_kernel succ_image (burst_with_scr true) = true
  /\ SwitchIsTotal demo_kernel succ_image (burst_with_scr false) = true.
Proof. split; reflexivity. Qed.

(* Reading 5's other half. Two runs from one successor context pass this
   clause and disagree on R-07-044's pending component, which is
   PartitionContext.v's own `NoResidue` failing inside a green clause. *)
Definition post_low : Context (kmachine demo_kernel) :=
  replay demo_kernel pre_low restore_burst.

Definition post_high : Context (kmachine demo_kernel) :=
  replay demo_kernel pre_high restore_burst.

Lemma burst_step_low :
  BurstStep demo_kernel restore_burst succ_image pre_low post_low.
Proof. repeat split; intros; reflexivity. Qed.

Lemma burst_step_high :
  BurstStep demo_kernel restore_burst succ_image pre_high post_high.
Proof. repeat split; intros; reflexivity. Qed.

(*| discharges: R-07-044 |*)
Theorem clause_two_admits_a_burst_that_fails_no_residue :
  ~ NoResidue (kmachine demo_kernel) (BurstStep demo_kernel restore_burst).
Proof.
  intros H.
  destruct (H succ_image pre_low post_low pre_high post_high
              burst_step_low burst_step_high) as [ _ [ _ Hp ] ].
  cbv in Hp. discriminate Hp.
Qed.

(* Reading 3, made checkable the same way. The zero register is outside what
   a run witnesses, so the clause is green over a burst whose post-state
   disagrees with the successor there. *)
Example the_zero_register_is_outside_what_a_run_witnesses :
  any_of (Nat.eqb 0) observed_registers = false := eq_refl.

(*| discharges: R-15-007i |*)
Theorem clause_two_does_not_reach_the_zero_register :
  SwitchIsTotal demo_kernel succ_image restore_burst = true
  /\ ctx_reg post_low 0 <> ctx_reg succ_image 0.
Proof.
  split; [ reflexivity | ]. intros H. cbv in H. discriminate H.
Qed.

(*| discharges: R-15-007i |*)
Theorem the_burst_step_alone_is_not_partition_contexts_totality :
  ~ RestoresRegisters (kmachine demo_kernel) (BurstStep demo_kernel restore_burst).
Proof.
  intros H.
  specialize (H succ_image pre_low post_low burst_step_low 0 eq_refl).
  cbv in H. discriminate H.
Qed.

(* And the premise that closes it is a premise: an arbitrary machine's
   contexts disagree at the zero register, so `ZeroRegisterIsFixed` is a
   claim about this machine's architecture and not a tautology. *)
(*| discharges: R-15-007i |*)
Theorem the_fixed_zero_register_is_a_premise_and_not_a_theorem :
  ~ ZeroRegisterIsFixed (kmachine demo_kernel).
Proof.
  intros H. specialize (H succ_image pre_low). cbv in H. discriminate H.
Qed.

(* =========================================================================
   Question three at the demo: the frame that answers it, and the four
   departures it refuses.
   ========================================================================= *)

Definition frame_trace : Trace demo_kernel :=
  map_over at_pc (cons 100 (cons 104 (cons 1000 (cons 1004 (cons 120 (cons 2000 (cons 130 (cons 3000 nil)))))))).

(* The same run sequence with more retires inside two of its slots. *)
Definition long_frame_trace : Trace demo_kernel :=
  map_over at_pc (cons 100 (cons 104 (cons 1000 (cons 1004 (cons 1008 (cons 120 (cons 2000 (cons 2004 (cons 130 (cons 3000 nil)))))))))).

Example the_demo_frame_runs_in_the_tables_order :
  FrameIsTheTables demo_kernel kernel_frame frame_trace = true := eq_refl.

Example the_longer_run_has_the_same_run_sequence :
  sites demo_kernel kernel_frame frame_trace
    = sites demo_kernel kernel_frame long_frame_trace := eq_refl.

(* A run that enters the table's third slot before its second, which is what
   a runtime scheduling decision looks like in the trace. *)
Definition reordered_frame_trace : Trace demo_kernel :=
  map_over at_pc (cons 100 (cons 1000 (cons 120 (cons 3000 (cons 130 (cons 2000 nil)))))).

Example a_departure_from_the_declared_order_is_refused :
  SwitchesInTableOrder demo_kernel kernel_frame reordered_frame_trace = false
  := eq_refl.

(* A run that enters the reserved slot twice in one major frame. *)
Definition revisiting_frame_trace : Trace demo_kernel :=
  map_over at_pc (cons 100 (cons 1000 (cons 120 (cons 2000 (cons 130 (cons 1004 (cons 140 (cons 3000 nil)))))))).

Example a_reserved_slot_entered_twice_is_refused :
  ReservedEnteredOnce demo_kernel kernel_frame revisiting_frame_trace = false
  := eq_refl.

(* A run with a switch inside a slot, where the table names no boundary. *)
Definition unnamed_switch_trace : Trace demo_kernel :=
  map_over at_pc (cons 100 (cons 1000 (cons 120 (cons 2000 (cons 124 (cons 2004 (cons 130 (cons 3000 nil)))))))).

Example a_switch_the_table_names_no_boundary_for_is_refused :
  NoUnnamedSwitch demo_kernel kernel_frame unnamed_switch_trace = false
  := eq_refl.

(* A run retiring an instruction in no declared extent at all. *)
Definition astray_trace : Trace demo_kernel :=
  map_over at_pc (cons 100 (cons 1000 (cons 120 (cons 2000 (cons 130 (cons 3000 (cons 5000 nil))))))).

Example a_retire_outside_every_declared_extent_is_refused :
  NoUnnamedSwitch demo_kernel kernel_frame astray_trace = false := eq_refl.

(* And the reading's own side condition excludes something. *)
Example overlapping_extents_are_not_readable :
  ExtentsAreReadable overlapping_kernel kernel_frame = false := eq_refl.

(* The check reading 7 refuses: one that reads how long the run spent rather
   than the order it ran in. R-15-077 leaves no counter to read a cycle from,
   so a retire count is the nearest a trace comes to a duration, and this
   construction is what excluding it means. *)
Definition dwell_checking (k : Kernel) (f : Frame (ktenant k)) (least : nat)
    (tr : Trace k) : bool :=
  andb (FrameIsTheTables k f tr) (Nat.leb least (count_of (pcs tr))).

(*| discharges: R-15-077 |*)
Theorem a_dwell_reading_check_is_refuted :
  ~ RunBlind demo_kernel kernel_frame
      (dwell_checking demo_kernel kernel_frame 9).
Proof.
  intros H.
  specialize (H frame_trace long_frame_trace
                the_longer_run_has_the_same_run_sequence).
  cbv in H. discriminate H.
Qed.

(* =========================================================================
   The revocation join at the demo: the two arms of gap a, and the sentence
   Q22a warns M4.4 about, made checkable.
   ========================================================================= *)

(* The published bitmap marks one base. `retired_bases` is the observer
   annotation Q22a describes, not an architectural field: it is what the
   retirement actually covers, where the bitmap is what the kernel
   published. *)
Definition marked_base (b : bool) : bool := b.
Definition retired_bases (b : bool) : bool := true.

(* R4 (R-07-015, R-08-006): a restore can satisfy R-07-015 exactly and
   install a tagged capability whose base a published bit marks. This is
   Q22a's own sentence that total restoration alone establishes no removal of
   stale authority, as two computed verdicts on one burst. *)
(*| discharges: R-08-006 |*)
Theorem total_restoration_is_not_removal_of_stale_authority :
  SwitchIsTotal demo_kernel succ_image restore_burst = true
  /\ BurstCarriesNoStaleAuthority demo_kernel marked_base restore_burst = false.
Proof. split; reflexivity. Qed.

(* R5 (R-08-005b, R-07-015): and the other arm removes the stale authority by
   ceasing to satisfy R-07-015, because the tag it writes is the filter's
   answer rather than the saved image's tag. The two arms are therefore not
   interchangeable, which is what gap a books. *)
(*| discharges: R-08-005b |*)
Theorem a_filtered_restore_of_an_unsanitized_image_is_not_total :
  BurstCarriesNoStaleAuthority demo_kernel marked_base
    (filtered_full_burst demo_kernel marked_base succ_image) = true
  /\ SwitchIsTotal demo_kernel succ_image
       (filtered_full_burst demo_kernel marked_base succ_image) = false.
Proof. split; reflexivity. Qed.

(* R6 (R-08-006): where the barrier sanitized the image, both arms are the
   same burst and both obligations hold at once. *)
(*| discharges: R-08-006 |*)
Theorem a_sanitized_image_satisfies_both_obligations :
  ImageIsSanitized demo_kernel marked_base unmarked_succ = true
  /\ SwitchIsTotal demo_kernel unmarked_succ
       (filtered_full_burst demo_kernel marked_base unmarked_succ) = true
  /\ BurstCarriesNoStaleAuthority demo_kernel marked_base
       (filtered_full_burst demo_kernel marked_base unmarked_succ) = true.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* R7 (R-08-006, R-08-007a): and sanitization is relative to what was
   published. A retirement set that marks an object's original base alone
   leaves a capability at a derived base tagged, so the same burst reads
   clean against the bitmap and stale against the retirement. Q22a states
   this of the holder map; here it is the same fact at the restore. *)
(*| discharges: R-08-007a |*)
Theorem marking_one_base_alone_leaves_a_derived_base_live :
  BurstCarriesNoStaleAuthority demo_kernel marked_base
    (filtered_burst demo_kernel marked_base unmarked_succ) = true
  /\ BurstCarriesNoStaleAuthority demo_kernel retired_bases
       (filtered_burst demo_kernel marked_base unmarked_succ) = false.
Proof. split; reflexivity. Qed.

(* Completion at the demo: the mark that is not one, and the two runs that
   show the epoch is not what decides. *)
Definition mark_only : Completion := {|
  bits_published := true;
  epoch_advanced := true;
  resident_roots_cleared := false;
  saved_contexts_filtered := false;
  loans_cancelled := false;
  device_boundary_reached := false
|}.

Definition complete_with_epoch : Completion := {|
  bits_published := true;
  epoch_advanced := true;
  resident_roots_cleared := true;
  saved_contexts_filtered := true;
  loans_cancelled := true;
  device_boundary_reached := true
|}.

Definition complete_without_epoch : Completion := {|
  bits_published := true;
  epoch_advanced := false;
  resident_roots_cleared := true;
  saved_contexts_filtered := true;
  loans_cancelled := true;
  device_boundary_reached := true
|}.

(*| discharges: R-08-006 |*)
Theorem an_epoch_mark_alone_is_not_semantic_completion :
  epoch_completion mark_only = true
  /\ SemanticCompletion mark_only = false.
Proof. split; reflexivity. Qed.

(*| discharges: R-08-006 |*)
Theorem an_epoch_reading_predicate_admits_a_resident_root :
  ~ RefusesAResidentRoot epoch_completion.
Proof. intros H. specialize (H mark_only eq_refl). discriminate H. Qed.

(*| discharges: R-08-007a |*)
Theorem completion_does_not_turn_on_the_epoch_mark :
  SemanticCompletion complete_with_epoch = true
  /\ SemanticCompletion complete_without_epoch = true
  /\ epoch_advanced complete_with_epoch <> epoch_advanced complete_without_epoch.
Proof. split; [ reflexivity | split; [ reflexivity | discriminate ] ]. Qed.

(* =========================================================================
   The whole predicate, and the run that answers it.

   The three questions joined, so that what a run of one member decides is
   one verdict rather than three readings. Nothing lowers this to a member:
   the target join is absent and a green line here is a statement about the
   predicate and not about a machine.
   ========================================================================= *)

Definition WellFormedAttempts (l : list Attempt) : bool :=
  andb (pairwise (fun a b => negb (Nat.eqb (att_pc a) (att_pc b))) l)
       (all_of (fun a => andb (Nat.ltb 0 (att_result_register a))
                              (Nat.ltb (att_result_register a) register_count)) l).
Definition BurstWritesExactlyOnce (k : Kernel) (b : Trace k) : bool :=
  andb
    (all_of (fun g => Nat.eqb (tally (fun r =>
      match r with RecX h _ _ => Nat.eqb h g | _ => false end) b) 1)
      observed_registers)
    (all_of (fun c => only_if ((kmachine k).(csr_nameable) c)
      (Nat.eqb (tally (fun r =>
        match r with RecC d _ => k.(csr_eqb) c d | _ => false end) b) 1))
      k.(csr_roster)).

Definition RunAnswersM44 (k : Kernel) (f : Frame (ktenant k))
    (l : list Attempt) (succ : Context (kmachine k))
    (confinement : Trace k) (burst : Trace k) (frame : Trace k) : bool :=
  andb (WellFormedAttempts l)
    (andb (RootIsThePartitions k l confinement)
      (andb (andb (SwitchIsTotal k succ burst) (BurstWritesExactlyOnce k burst))
            (FrameIsTheTables k f frame))).

Example the_demo_run_answers_all_three_questions :
  RunAnswersM44 demo_kernel kernel_frame demo_attempts succ_image
    confinement_trace restore_burst frame_trace = true := eq_refl.

Example a_run_failing_any_one_question_is_refused :
  RunAnswersM44 demo_kernel kernel_frame demo_attempts succ_image
    admitted_derivation_trace restore_burst frame_trace = false
  /\ RunAnswersM44 demo_kernel kernel_frame demo_attempts succ_image
       confinement_trace tagless_burst frame_trace = false
  /\ RunAnswersM44 demo_kernel kernel_frame demo_attempts succ_image
       confinement_trace restore_burst reordered_frame_trace = false
  := conj eq_refl (conj eq_refl eq_refl).

(* -------------------------------------------------------------------------
   R-05-166's inhabitation witnesses: one closed definition per record this
   file's statements quantify over, named for that record and ascribed at it.
   A record this file reaches through a Require is witnessed in the file that
   declares it.
   ------------------------------------------------------------------------- *)

Definition witness_Kernel : Kernel := demo_kernel.
Definition witness_Extent : Extent := {| ext_base := 100; ext_top := 200 |}.
Definition witness_Attempt : Attempt := {| att_pc := 300; att_result_register := 8; att_target := RootTop |}.
Definition witness_Completion : Completion := complete_with_epoch.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared set
   R-05-164 currently makes empty, so "Closed under the global context" is
   that emptiness checked mechanically.
   ------------------------------------------------------------------------- *)

Print Assumptions RootIsThePartitions.
Print Assumptions AttemptsCover.
Print Assumptions SwitchIsTotal.
Print Assumptions RegisterBurstTotal.
Print Assumptions CsrBurstTotal.
Print Assumptions BurstCarriesNothingElse.
Print Assumptions replay.
Print Assumptions BurstStep.
Print Assumptions FrameIsTheTables.
Print Assumptions ExtentsAreReadable.
Print Assumptions ReservedEnteredOnce.
Print Assumptions SwitchesInTableOrder.
Print Assumptions NoUnnamedSwitch.
Print Assumptions SemanticCompletion.
Print Assumptions BurstCarriesNoStaleAuthority.
Print Assumptions ImageIsSanitized.
Print Assumptions RunAnswersM44.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions only_if_elim.
Print Assumptions bool_eqb_sound.
Print Assumptions bool_eqb_holds.
Print Assumptions nat_eqb_sound.
Print Assumptions nat_eqb_holds.
Print Assumptions leb_cases.
Print Assumptions all_of_app.
Print Assumptions filter_of_app.
Print Assumptions all_of_ext.
Print Assumptions all_of_true.
Print Assumptions all_of_member.
Print Assumptions all_of_filter_upto.
Print Assumptions all_of_map.
Print Assumptions only_if_filtered.
Print Assumptions observed_register_reached.
Print Assumptions next_result_untagged_blank.
Print Assumptions refused_at_blank.
Print Assumptions pcs_shift.
Print Assumptions kernel_roster_covers.
Print Assumptions confinement_reads_the_tag_and_not_the_value.
Print Assumptions the_burst_restores_every_witnessed_register.
Print Assumptions the_burst_restores_every_nameable_csr.
Print Assumptions a_fixed_zero_register_closes_the_gap.
Print Assumptions the_frame_check_decides_order_and_not_duration.
Print Assumptions the_frame_check_ignores_the_order_numeral.
Print Assumptions a_filtered_restore_carries_no_marked_authority.
Print Assumptions the_filter_is_the_identity_on_a_sanitized_image.
Print Assumptions completion_refuses_a_resident_root.
Print Assumptions completion_refuses_an_unfiltered_saved_context.
Print Assumptions completion_refuses_an_outstanding_loan.
Print Assumptions completion_refuses_an_open_device_boundary.
Print Assumptions the_demo_table_is_admitted.
Print Assumptions the_demo_extents_are_readable.
Print Assumptions the_declared_attempts_are_all_refused.
Print Assumptions a_derivation_that_kept_its_tag_is_refused.
Print Assumptions a_member_skipping_a_declared_window_is_refused.
Print Assumptions a_bounds_decoding_check_is_refuted.
Print Assumptions the_restore_burst_is_total.
Print Assumptions a_restore_truncated_to_the_low_registers_is_refused.
Print Assumptions a_restore_dropping_a_validity_tag_is_refused.
Print Assumptions a_restore_exempting_a_nameable_csr_is_refused.
Print Assumptions a_write_outside_the_merged_file_is_refused.
Print Assumptions a_write_to_a_csr_the_partition_cannot_name_is_refused.
Print Assumptions clause_two_does_not_read_the_capability_registers_outside_the_file.
Print Assumptions burst_step_low.
Print Assumptions burst_step_high.
Print Assumptions clause_two_admits_a_burst_that_fails_no_residue.
Print Assumptions the_zero_register_is_outside_what_a_run_witnesses.
Print Assumptions clause_two_does_not_reach_the_zero_register.
Print Assumptions the_burst_step_alone_is_not_partition_contexts_totality.
Print Assumptions the_fixed_zero_register_is_a_premise_and_not_a_theorem.
Print Assumptions the_demo_frame_runs_in_the_tables_order.
Print Assumptions the_longer_run_has_the_same_run_sequence.
Print Assumptions a_departure_from_the_declared_order_is_refused.
Print Assumptions a_reserved_slot_entered_twice_is_refused.
Print Assumptions a_switch_the_table_names_no_boundary_for_is_refused.
Print Assumptions a_retire_outside_every_declared_extent_is_refused.
Print Assumptions overlapping_extents_are_not_readable.
Print Assumptions a_dwell_reading_check_is_refuted.
Print Assumptions total_restoration_is_not_removal_of_stale_authority.
Print Assumptions a_filtered_restore_of_an_unsanitized_image_is_not_total.
Print Assumptions a_sanitized_image_satisfies_both_obligations.
Print Assumptions marking_one_base_alone_leaves_a_derived_base_live.
Print Assumptions an_epoch_mark_alone_is_not_semantic_completion.
Print Assumptions an_epoch_reading_predicate_admits_a_resident_root.
Print Assumptions completion_does_not_turn_on_the_epoch_mark.
Print Assumptions the_demo_run_answers_all_three_questions.
Print Assumptions a_run_failing_any_one_question_is_refused.

(* The final single-hart acceptance joins all three trace questions to the
   semantic barrier and to the concrete image/burst checked by this run.
   Completion fields are trusted observations of the listed mechanisms;
   merely constructing true Booleans supplies no target observation. *)
Definition QualifiedRunAnswersM44 (k : Kernel) (f : Frame (ktenant k))
    (l : list Attempt) (succ : Context (kmachine k))
    (confinement burst frame : Trace k) (done : Completion) (bm : k.(Base) -> bool) : bool :=
  andb (RunAnswersM44 k f l succ confinement burst frame)
    (andb (SemanticCompletion done)
      (andb (ImageIsSanitized k bm succ) (BurstCarriesNoStaleAuthority k bm burst))).
Theorem qualified_run_requires_the_actual_barrier_and_image : forall k f l succ conf burst frame done bm,
  QualifiedRunAnswersM44 k f l succ conf burst frame done bm = true ->
  RunAnswersM44 k f l succ conf burst frame = true /\
  SemanticCompletion done = true /\ ImageIsSanitized k bm succ = true /\
  BurstCarriesNoStaleAuthority k bm burst = true.
Proof.
  intros k f l succ conf burst frame done bm H; unfold QualifiedRunAnswersM44 in H.
  apply andb_split in H as [Hr H]; apply andb_split in H as [Hc H].
  apply andb_split in H as [Hi Hb]; repeat split; assumption.
Qed.
Example the_sanitized_run_passes_the_joined_predicate :
  QualifiedRunAnswersM44 demo_kernel kernel_frame demo_attempts unmarked_succ
    confinement_trace (full_burst demo_kernel unmarked_succ) frame_trace
    complete_with_epoch marked_base = true := eq_refl.
Example stale_restore_and_epoch_only_completion_fail_the_joined_predicate :
  QualifiedRunAnswersM44 demo_kernel kernel_frame demo_attempts succ_image
    confinement_trace restore_burst frame_trace complete_with_epoch marked_base = false /\
  QualifiedRunAnswersM44 demo_kernel kernel_frame demo_attempts unmarked_succ
    confinement_trace (full_burst demo_kernel unmarked_succ) frame_trace mark_only marked_base = false.
Proof. split; reflexivity. Qed.
Example unrelated_untagged_writes_are_not_derivation_results :
  refused_at 300 8
    (cons (at_pc 300) (cons (RecX 9 false true) (cons (RecX 8 true true) nil))) = false /\
  refused_at 300 8 (cons (at_pc 300) (cons (RecX 9 false true) nil)) = false.
Proof. split; reflexivity. Qed.
Example one_instruction_cannot_witness_three_declared_targets :
  WellFormedAttempts
    (cons {|att_pc := 300; att_result_register := 8; att_target := RootTop|}
    (cons {|att_pc := 300; att_result_register := 8; att_target := WindowTop 0|} nil)) = false.
Proof. reflexivity. Qed.
Example repeated_register_or_csr_writes_are_refused :
  BurstWritesExactlyOnce demo_kernel (cons (RecX 8 false false) restore_burst) = false /\
  BurstWritesExactlyOnce demo_kernel (cons (RecC 0 false) restore_burst) = false.
Proof. split; reflexivity. Qed.
Print Assumptions qualified_run_requires_the_actual_barrier_and_image.
Print Assumptions the_sanitized_run_passes_the_joined_predicate.
Print Assumptions unrelated_untagged_writes_are_not_derivation_results.
Print Assumptions repeated_register_or_csr_writes_are_refused.

Example attempt_register_bounds_are_attained_and_exclusive :
  WellFormedAttempts (cons {|att_pc := 300; att_result_register := 1; att_target := RootTop|} nil) = true /\
  WellFormedAttempts (cons {|att_pc := 300; att_result_register := 31; att_target := RootTop|} nil) = true /\
  WellFormedAttempts (cons {|att_pc := 300; att_result_register := 0; att_target := RootTop|} nil) = false /\
  WellFormedAttempts (cons {|att_pc := 300; att_result_register := 32; att_target := RootTop|} nil) = false.
Proof. repeat split; reflexivity. Qed.
Example the_next_instruction_cannot_supply_the_missing_result :
  next_result_untagged 8 (cons (at_pc 304) (cons (RecX 8 false true) nil)) = false.
Proof. reflexivity. Qed.
