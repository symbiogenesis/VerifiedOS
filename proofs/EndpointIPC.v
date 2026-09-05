(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   EndpointIPC.v

   Endpoint and notification IPC and the surviving object inventory, as the
   register fixes them: R-07-031b's invocation enumeration closed at five
   with R-07-031a's four groups over it and R-07-031's *under a dozen*
   above it; R-07-027a's object inventory closed at three classes beside
   two tables that are not objects, with no reply object surviving and the
   return path a badge; R-07-027's capDL-class edge and R-07-028's
   initialisation-refinement obligation over the same three; R-07-029's
   synchronous endpoints, explicit capability transfer and control-only
   kernel, with R-07-029a fixing *synchronous* as rendezvous-or-refusal and
   R-07-030 refusing a submission-queue opcode surface beside it;
   R-07-037a's run-to-completion with no blocking call, R-07-037b's
   composition-fixed intra-slot rotation, R-07-037c's pending-bit swap and
   R-07-037d's in-domain residue; R-07-044's disjunction under both;
   R-08-032's interrupt-send as a store and R-07-039's interrupt-receive as
   ordinary loads, which are what make R-07-031b's notification group
   empty; R-12-096's coalescible hint with its defined reset and its
   recheck; R-04-008's no-mint-at-runtime over the transfer; and R-15-007's
   frozen format, which is where the badge's bit budget is owed and not
   stated.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. Every quantity the register
   leaves to composition is a field of the Machine record rather than a
   literal or a top-level Parameter, which is what keeps the R-05-163
   assumption gate green while leaving the decision where its owner can
   make it. Nothing is admitted and nothing is axiomatized: the Print
   Assumptions block at the end reports every shipped constant closed under
   the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. No constant here is compiled,
   lowered, or run on either emulator, and nothing here executes anywhere.
   The computed checks are decided inside the kernel by conversion and
   print nothing.

   What is deferred, and to which item. M4.3 exercises the capability
   lifecycle, this IPC surface and slot faults through Wasm, and nothing
   below is a Wasm module, a vector, or a QuickChick generator; M4.4 brings
   up the C instance the frozen surface is an ABI of, and nothing below
   states a calling convention, a register assignment, an ABI number, or a
   trap encoding. R-07-028's initialisation-refinement obligation is
   stated by M3.3 over an arbitrary composed cap graph and its discharge
   against an installed graph is deferred; what is here is the inventory
   that obligation quantifies over. The authoring
   constraint this file does keep is the restricted subset a
   Rupicola-class compiler admits: no general recursion, every recursive
   function structural over a list or a finite index, and records and
   finite indices wherever a datatype is not owed, with the one exception
   named next. Eight inductives are declared, each costing a compilation
   lemma per constructor on any such route, and that is a price recorded
   rather than a claim made. Seven are owed because the register itself
   closes their enumerations: Invocation (R-07-031b's five), AbiGroup
   (R-07-031a's four groups), Nameable (R-07-027a's three classes, the two
   tables beside them and the one class that entry refuses), Lifecycle (the
   three acts that entry names, created, derived and revoked), Outcome
   (R-07-029a's *rendezvous or refusal*, its two arms being the typed
   refusal itself), NotifyHalf
   (R-07-031b's two halves of a notification) and Medium (R-08-032's store
   against R-07-039's loads). The exception is Act, at seventeen
   constructors the dearest of the eight and the one no entry closes: it is
   the union of what the register numbers, what it excludes for a reason of
   its own and what a MUST NOT deletes, and no entry states that union. It
   is a datatype and not a finite index because every constructor carries
   the citation of the entry that places it, and an index would put those
   citations on numbers.

   No Require. Nothing beyond the Rocq prelude is reachable, so Classical
   and FunctionalExtensionality are unavailable and every equality below is
   stated pointwise or over a decidable boolean for that reason. A Require
   naming a sibling artifact would be admissible, and there is none to
   name. PartitionContext.v carries R-07-044's pending component as a
   switch-time context component inside a step relation over registers and
   CSRs, and R-15-220's three constants as a cost model; what is below is
   the delivery obligation R-07-037c states over the same bits, which is a
   different level and shares no quantity with it, and R-07-037c's cost
   clause is left where that file's model can carry it. CyclicExecutive.v's
   admission algebra is a frame's and DischargeSequence.v's dwell is a mode
   transition's. A Require of any of the three would be a citation rather
   than a dependency.

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. An invocation is a constructor of a closed inductive and the closure
      is R-07-031b's rather than this file's. Five is written as a literal
      because that entry closes the list outright and carries its own
      amendment criterion; the demo's magnitudes are all fields.
   2. The frozen surface is a set and not an order. R-07-031b fixes what
      the ABI numbers and says the surface assigns the numbers without
      fixing which member takes which, so `frozen_surface` is invariant
      under a permutation of the sequence and refuses only a deletion or a
      duplication. That is why the transposition family below is admitted
      where the deletion and insertion families are refused, and it is a
      judgment: a reading on which the order is normative would refuse all
      three families and would be deciding gap d by fiat.
   3. The cut is what the ABI numbers, and the trap surface is a parameter
      rather than a decision this file takes. R-07-031b's third accept
      clause decides that the schedule transitions take no number and leaves
      *what carries that request* owed at R-11-023, so whether a focus
      rebinding, a rung selection or a suspension traps is gap i and is not
      a judgment available here. `AdmissibleTrapSurface` is the criterion
      the register does fix over a trap surface, `traps_act` and
      `traps_with_the_schedule_transitions` are two values that criterion
      admits, and what this reading claims is proved of every admissible
      value: `no_admissible_trap_surface_is_the_abi_cut` shows that none of
      them is the ABI's cut, because every one carries the exception surface
      the numbering criterion excludes. What is not invariant is the size of
      the over-collection, one act on this file's own value and four on the
      other, and that difference is the gap rather than a result.
   4. The notification group's emptiness is derived, refuted of three
      constructions, and not claimed. Both halves of a notification are
      memory operations (R-08-032's store, R-07-039's loads), so neither is
      a constructor of the invocation type at all and the group's census is
      zero by filtering. A census over a total function this file wrote is
      not by itself a refutation of anything, so the emptiness is stated of
      an arbitrary grouping, derived from R-07-031b's own four-way
      assignment rather than asserted beside it, and refuted of a grouping
      that files the poll-site yield under the notification group and of one
      that files all five there; the numbering criterion is refuted of a
      numbering that gives a notification half a number. The coverage clause
      this file used to carry beside the emptiness is withdrawn and its
      reason recorded: a census summing four filters over a five-member list
      answers five for every total function whatever, so it was true of the
      all-notification grouping too and refutable by nothing.
   5. An endpoint holds readiness and not a queue. R-07-029a leaves no
      partition in a kernel-held wait, so an endpoint's state is a
      predicate on the endpoint and the kernel's parked list exists below
      only so that the construction that uses one can be exhibited and
      refused. A model with no parked list would make the refutation
      inexpressible rather than false.
   6. The refusal is typed, and *typed* is read as: nothing crosses on the
      refusal arm. R-07-029a's criterion is that the refusal is a case the
      caller's reaction handles rather than a value it may ignore, and the
      property a statement can carry is that the medium is absent where the
      transfer did not happen. The status-word construction below is what
      that reading excludes.
   7. Reply-by-badge is a return path and not an object, so a reply object
      is expressible here and refused rather than absent. R-07-027a's *no
      reply object survives* has to have a referent for the refutation to
      be about anything, so `NReplyObject` is a nameable that is not an
      object class and every construction that spends it is refused.
   8. The badge is a bit list of the declared width rather than a number of
      a fixed size, because the width is gap a: everything below quantifies
      over it and the badge space is stated as its own power of two, so a
      later entry fixing the width instantiates a field rather than
      amending a statement.
   9. R-07-037c and R-07-037d are two obligations over one rotation
      answered in opposite directions, and they are stated over different
      carriers: R-07-037c's is a property of a delivery and of a dispatch
      step, and R-07-037d's is a property of a group's label assignment and
      of an inference. So no construction below breaks one and is checked
      against the other, and none could be, the carriers sharing no
      argument. The separation is the carrier, which is what R-07-037c's
      second accept clause separates in words: the pending component is
      delivery and the zeroize class is confidentiality.
  10. R-12-096's *sleep* has exactly one referent and R-07-029a says which:
      the poll-site yield. So the consumer's decision is a decider over two
      ring observations and the lost wakeup is a construction rather than a
      remark.
  11. Boolean rather than propositional wherever the witnesses must
      compute: the surface check, the inventory check, the message bound
      and the readiness test are decidable, so the generated families below
      are checked by conversion in the silent Example form rather than by a
      proof per member.
  12. The kernel state carries a parked list, a wait predicate and a
      runnable predicate the specification never touches, so the three
      obligations over them are separate rather than one obligation stated
      three ways, and each has a construction below that breaks it alone.
  13. R-07-029a's *within the invocation's own bounded cost* admits a
      refusal that spends the whole of it. That is the weaker reading and
      the one the entry's words carry, so
      `the_refusal_that_spends_its_whole_invocation_is_admitted` is proved
      rather than refuted; a statement refusing the boundary would be
      deciding a width the register left open, and the boundary is exactly
      where *within* and *below* part company.
  14. R-07-037c's two clauses are ordered and not independent, and the order
      is stated rather than implied by exhibiting only the separation that
      exists. Seeing one's own pending bits entails not varying with the
      predecessor, which
      `seeing_its_own_pending_entails_predecessor_independence` proves, so
      no construction meets the first and breaks the second and none can.
      The separation that is real is the other direction,
      `head_member_delivery` meeting the weaker clause and breaking the
      stronger, and the weaker clause is stated for that reason rather than
      as an obligation standing on its own.
  15. R-07-037c's second conjunct is stated at the level of state, because
      it is not statable of a delivery. *The bits it leaves are restored to
      it at its next dispatch* is a property of what a dispatch step does to
      a file it is not dispatching, so a file per member and a step over
      them are modelled here, the clause is stated of an arbitrary step, and
      the restoration follows over an arbitrary dispatch sequence rather
      than being assumed. Two steps break it, one sharing the file across
      the group and one clearing the predecessor's as it leaves.

   The literals taken from the design, and there are four. R-07-031b closes
   the invocation list at five, so `there_are_five_invocations` is that
   count checked by conversion; R-07-031a fixes four ABI groups, so
   `there_are_four_abi_groups` is that one; R-07-027a closes the object
   inventory at three classes and two tables, so
   `the_inventory_is_three_classes_and_two_tables` is that pair; and
   R-07-031's *under a dozen* is the twelve
   `five_sits_under_a_dozen_with_margin` compares against. Every other
   magnitude is a field: the partition and endpoint counts, the message
   register and slot budgets, the badge width, the per-invocation cost and
   the refusal cost, the rotation's membership and order, the
   confidentiality label, R-07-044's arm, the interrupt file and its width.

   How the refutations are generated. A refutation is a seeded weakening
   the theorem must reject, so four generators produce families of them
   mechanically. Over the invocation set: `admits_of_mask` walks every
   boolean enumeration of the five, which is 32 predicates of which exactly
   one is the frozen surface. Over an arbitrary invocation sequence:
   `drop_at_inv` deletes a member and `insert_at_inv` starts one twice,
   which is 11 weakenings every one refused, and `swap_at_inv` transposes
   an adjacent pair, which is 4 sequences every one still admitted, that
   contrast being reading 2 made checkable. Over an arbitrary peer
   readiness state: `readiness_of` walks every one of the 16 readiness
   states of a four-endpoint machine and `optimistic_at` walks the family
   of transfers that cross to an unready peer below an index. Beside them
   the generic theorems quantify over the index rather than enumerating.
   The hand-authored refutations below are the ones no index generates,
   being alternative constructions rather than mutations of a list.

   What this file deliberately does not author, with the entry that owes
   each decision. A register gap is reported, not closed:

   a. The badge's width, and which field of the frozen format carries it.
      R-07-031 makes a kernel message registers plus capability slots;
      R-07-027a puts the badge's bit budget at R-15-007's; R-15-007 spends
      all 64 bits with none left over and R-15-007n leaves no field
      uninterpreted for software to give a meaning to. So no entry says how
      wide a badge is or where it sits. `badge_width` is a field, the
      transfer is stated over an arbitrary width, and
      `the_badge_space_is_two_to_the_declared_width` is stated of any
      width at all. Owed at R-07-031 or R-07-027a.
   b. What a typed refusal's type enumerates. R-07-029a requires the
      refusal be typed rather than a status word and enumerates no cause
      set, so `Outcome` carries a refusal arm and no cause enumeration is
      authored; a closed inductive of causes would be this file writing the
      list. Owed at R-07-029a.
   c. Which of the five invocations can refuse. R-07-029a states the
      discipline of a send or a receive; whether a grant redeem or a revoke
      has a refusal arm, and what it says, is unstated. The obligations
      below are stated over the endpoint pair and `refusal_cost` is total
      over the five without claiming that every member has one. Owed at
      R-07-029a or R-08-004c.
   d. The ABI numbers themselves. R-07-031b closes the set and has the
      frozen surface assign numbers; which number each member takes is
      nowhere fixed. The surface check is stated over membership and is
      invariant under permutation, which reading 2 records and
      `every_transposition_is_still_a_frozen_surface` exhibits. That
      invariance does not reach the assignment, and two definitions here do
      read one, so both are stated relative to a sequence: `index_in` and
      `dispatch_of` are the functions of it, and `index_of` and
      `spec_dispatch` are those functions at the one sequence this file
      writes down. `a_transposed_surface_assigns_different_numbers` computes
      a second assignment over the same five members with both sequences
      passing the check, so the choice is exhibited rather than made
      silently; and `every_frozen_surface_numbers_every_member` is the half
      of the question that is not open, every member of every frozen surface
      having a number that dispatches back to it. Owed at R-07-031b.
   e. What a re-offer costs and how many are admitted. R-07-029a puts the
      latency in buffer depth under R-11-010 rather than in kernel state
      and R-07-042 reads its own bound as re-offer latency; no entry bounds
      the number of re-offers or their spacing. The statement below is over
      an arbitrary offer list and says only that nothing is parked. Owed at
      R-07-042 or R-11-010.
   f. Whether a notification word is per partition, per endpoint or per
      ring. R-12-096 gives the consumer *its* notification word and
      R-08-032 makes the signal a store to an interrupt file; which
      granularity binds is unstated, so the obligations are stated of an
      arbitrary word and an arbitrary signal function. Owed at R-12-096 or
      R-08-032.
   g. Whether an endpoint's readiness is one bit or one per offering peer.
      R-07-029a says *meets no ready peer* and says no more, so readiness
      is taken as a predicate on the endpoint, which is the weaker reading
      and the one the entry's words carry. Owed at R-07-029.
   h. Every composition magnitude. The partition and endpoint counts, the
      message budgets, the badge width, the two cost functions, the group
      membership, the label, R-07-044's arm, the interrupt file and its
      width are fields; the demo machines at the end instantiate them with
      arbitrary witness values that carry no composition claim.
   i. What carries the compositor's request for a focus rebinding, a rung
      selection or a suspension, and so whether the three trap. R-07-031b's
      third accept clause decides that all three take no ABI number and says
      in its own words that what carries the request *is owed at R-11-023*;
      R-11-023 has the compositor *request* and the kernel *enact* and names
      no carrier. So the trap surface is a parameter here,
      `AdmissibleTrapSurface` is what the register does fix over it, and two
      values of it are exhibited and both proved admissible. Owed at
      R-11-023.
   j. Which of create, derive and revoke each object class has. R-07-027a
      states the negative of the two tables, that neither is created,
      derived or revoked, and states nothing positive of the three classes;
      R-07-031a deletes the derivation-tree invocation outright and
      R-07-031b's closed five carries no create and no derive. So the twin
      obligation here is the distinction and not the schedule, and
      `the_revoke_only_lifecycle_discharges_both` shows that the two
      obligations do not decide it. Owed at R-07-027a or R-07-031b.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary surface, grouping, numbering, trap surface,
   dispatcher, inventory, designation, lifecycle map, return path, grant,
   transfer, signal, reset, decider, delivery, dispatch step, advancer or
   cost function, proved of the specification, and refuted of an alternative
   construction the register's own sentence excludes. The claim is meant
   without exception and it is meant per obligation rather than per section,
   so a `Prop` here that no construction below is proved to break is a
   defect in this file: two decision procedures accordingly carry a
   completeness lemma apiece, `frozen_surface_complete` and
   `inventory_ok_complete`, without which every refusal of a deletion or an
   insertion would refute the boolean and leave the `Prop` it decides with no
   refutation at all. Inhabitation is concrete: a demo machine whose group,
   label, interrupt file and budgets are inhabited, readiness states on which
   the transfer crosses and readiness states on which it refuses, and a
   frozen surface that passes beside eleven sequences that do not and four
   that still do.

   **What a refutation does not establish, where an obligation quantifies a
   field away.** An obligation stated over an arbitrary carrier says nothing
   about a quantity that carrier hides, and admitting a construction under it
   is not evidence about that quantity. The case worth naming is
   `SeesItsOwnPendingOnly`, which quantifies the interrupt file away: it
   admits the unswapped construction on the whole static arm, a machine
   sharing one file across the boundary included, and
   `the_static_arm_admits_the_construction_of_every_machine` proves exactly
   that rather than leaving it to be discovered. R-07-044's *hidden or
   shared* is refuted on the carrier that can express it, the file-per-member
   state below, where `sharing_step` breaks
   `LeavesEveryOtherMembersBitsAlone` on either arm.

   **Fourteen obligations below carry a hypothesis, and thirteen of them
   quantify it.** Where the hypothesis ranges over a universally quantified
   variable, every construction meets it at some instance and the obligation
   cannot be scoped away by a composition. One reads a machine field instead,
   `SwapsWhereASwapExists`, which is the arm R-07-037c scopes its verb to, so
   it alone can be emptied by the composition and it alone needs an
   inhabitation witness naming a machine: `demo`, recorded by
   `the_two_pending_arms_differ`. On the other arm it is empty, which
   `the_guarded_clause_is_empty_on_the_static_arm` states as a theorem rather
   than leaving to be found, and that is why the observable R-07-044's
   purpose clause owes, `SeesItsOwnPendingOnly`, carries no hypothesis at
   all: a file shipping the guarded clause alone would be shipping an empty
   statement over half of R-07-044's disjunction.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   List, boolean and numeric helpers, defined here rather than imported:
   the prelude carries the list type and not the library over it, and
   importing a module to save a few dozen lines would put its assumptions
   inside the R-05-163 gate's reach for no gain.
   ------------------------------------------------------------------------- *)

Fixpoint all_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => true
  | cons x r => andb (p x) (all_of p r)
  end.

Fixpoint any_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => false
  | cons x r => orb (p x) (any_of p r)
  end.

Fixpoint count_of {A : Type} (l : list A) : nat :=
  match l with nil => 0 | cons _ r => S (count_of r) end.

Fixpoint map_over {A B : Type} (f : A -> B) (l : list A) : list B :=
  match l with nil => nil | cons x r => cons (f x) (map_over f r) end.

Fixpoint filter_of {A : Type} (p : A -> bool) (l : list A) : list A :=
  match l with
  | nil => nil
  | cons x r => if p x then cons x (filter_of p r) else filter_of p r
  end.

Definition head_or {A : Type} (l : list A) (d : A) : A :=
  match l with nil => d | cons x _ => x end.

(* 0 through n-1, in that order: the index set the generators below range
   over. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

Definition before_last (n : nat) : nat :=
  match n with 0 => 0 | S k => k end.

(* Implication as a boolean, written out rather than taken from a library
   for the reason above. *)
Definition only_if (a b : bool) : bool := orb (negb a) b.

(* Agreement of two booleans, which is what a pointwise equality of two
   bit maps is checked with below. *)
Definition same_bool (a b : bool) : bool := if a then b else negb b.

(* Halving, parity and bit extraction, which is how a boolean enumeration
   over a finite set is indexed by a number rather than authored. *)
Fixpoint halve (n : nat) : nat :=
  match n with 0 => 0 | S 0 => 0 | S (S k) => S (halve k) end.

Fixpoint oddb (n : nat) : bool :=
  match n with 0 => false | S 0 => true | S (S k) => oddb k end.

Fixpoint bit_at (i : nat) (n : nat) : bool :=
  match i with 0 => oddb n | S k => bit_at k (halve n) end.

(* The size of a bit space of a declared width. The badge's width is gap a,
   so this is stated of an arbitrary width and instantiated nowhere. *)
Fixpoint two_pow (n : nat) : nat :=
  match n with 0 => 1 | S k => two_pow k + two_pow k end.

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

Lemma nat_eqb_refl : forall n : nat, Nat.eqb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma nat_eqb_true : forall a b : nat, Nat.eqb a b = true -> a = b.
Proof.
  intros a. induction a as [ | x IH ]; intros b H; destruct b as [ | y ];
    try discriminate H.
  - reflexivity.
  - simpl in H. rewrite (IH y H). reflexivity.
Qed.

Lemma nat_leb_refl : forall n : nat, Nat.leb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma nat_leb_succ : forall n : nat, Nat.leb n (S n) = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

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

Lemma all_of_app_intro :
  forall (A : Type) (p : A -> bool) (l r : list A),
    all_of p l = true -> all_of p r = true -> all_of p (app l r) = true.
Proof.
  intros A p l r. induction l as [ | x s IH ]; intros Hl Hr.
  - exact Hr.
  - simpl in Hl. destruct (andb_split _ _ Hl) as [ Hx Hs ].
    simpl. apply andb_join; [ exact Hx | exact (IH Hs Hr) ].
Qed.

Lemma all_of_map :
  forall (A B : Type) (p : B -> bool) (f : A -> B) (l : list A),
    all_of (fun x => p (f x)) l = true -> all_of p (map_over f l) = true.
Proof.
  intros A B p f l. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    simpl. apply andb_join; [ exact Hx | exact (IH Hr) ].
Qed.

Lemma count_of_app :
  forall (A : Type) (l r : list A),
    count_of (app l r) = Nat.add (count_of l) (count_of r).
Proof.
  intros A l r. induction l as [ | x s IH ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

Lemma count_of_map :
  forall (A B : Type) (f : A -> B) (l : list A),
    count_of (map_over f l) = count_of l.
Proof.
  intros A B f l. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

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

(* The helpers' own floors, so that the day one of them stops deciding is
   the day it says so. Each is a base case no other check below reaches. *)
Example the_empty_conjunction_holds : all_of (fun _ : nat => false) nil = true := eq_refl.

Example the_empty_disjunction_fails : any_of (fun _ : nat => true) nil = false := eq_refl.

Example nothing_has_length_zero : count_of (nil : list nat) = 0 := eq_refl.

Example the_head_of_nothing_is_the_fallback : head_or (nil : list nat) 7 = 7 := eq_refl.

Example before_last_of_nothing : before_last 0 = 0 := eq_refl.

Example the_index_set_of_three : upto 3 = cons 0 (cons 1 (cons 2 nil)) := eq_refl.

Example only_if_is_implication :
  cons (only_if true true) (cons (only_if true false)
  (cons (only_if false true) (cons (only_if false false) nil)))
  = cons true (cons false (cons true (cons true nil))) := eq_refl.

Example same_bool_is_agreement :
  cons (same_bool true true) (cons (same_bool true false)
  (cons (same_bool false true) (cons (same_bool false false) nil)))
  = cons true (cons false (cons false (cons true nil))) := eq_refl.

Example halving_and_parity :
  map_over halve (upto 8) = cons 0 (cons 0 (cons 1 (cons 1 (cons 2 (cons 2
    (cons 3 (cons 3 nil)))))))
  /\ map_over oddb (upto 8) = cons false (cons true (cons false (cons true
    (cons false (cons true (cons false (cons true nil))))))) :=
  conj eq_refl eq_refl.

Example the_bits_of_a_mask :
  map_over (fun i => bit_at i 13) (upto 4)
  = cons true (cons false (cons true (cons true nil)))
  /\ map_over (fun i => bit_at i 0) (upto 4)
  = cons false (cons false (cons false (cons false nil))) :=
  conj eq_refl eq_refl.

Example the_powers_of_two :
  map_over two_pow (upto 6)
  = cons 1 (cons 2 (cons 4 (cons 8 (cons 16 (cons 32 nil))))) := eq_refl.

(* =========================================================================
   The closed enumerations, and only these. Each is closed because the
   register itself closes it: a further inductive here would be this file
   inventing an enumeration where the register leaves a composition, which
   is exactly the line a statement artifact does not cross.
   ========================================================================= *)

(* R-07-031b's five invocations, in that entry's own order (i) to (v). Each
   is an act a principal requests by trapping in with an ABI number the
   frozen surface assigns. *)
Inductive Invocation : Type :=
| Send                         (* R-07-029, refusing under R-07-029a       *)
| Receive                      (* R-07-029, refusing under R-07-029a       *)
| PollSiteYield                (* R-07-037b's rotation-advancing yield     *)
| GrantRedeem                  (* R-08-004c's unseal for the call's length *)
| Revoke.                      (* R-08-008's principal-requested trigger   *)

(* R-07-031a's four ABI groups, in that entry's own order. The notification
   group is one of the four and is empty, which is R-07-031b's result and
   not an omission (reading 4). *)
Inductive AbiGroup : Type :=
| EndpointGroup
| NotificationGroup
| PartitionContextGroup
| RevocationGroup.

(* What a design could name inside this kernel. The first three are
   R-07-027a's object classes, the next two are the tables that entry
   places beside them and calls not objects, and the last is the class the
   same entry refuses: it is here so that a construction spending it can be
   exhibited and refused rather than being merely unwritten (reading 7). *)
Inductive Nameable : Type :=
| NEndpoint
| NNotification
| NPartitionContext
| NGrantTable                  (* R-08-004d, outside the restored classes *)
| NScheduleTable               (* R-11-024's rung change swaps it         *)
| NReplyObject.                (* R-07-027a: no reply object survives     *)

(* The three acts a capability-designated object could be subject to, which
   is the sentence R-07-027a makes of the two tables: no capability names
   either and neither is created, derived or revoked. *)
Inductive Lifecycle : Type := LCreate | LDerive | LRevoke.

(* Every act this file distinguishes, whether or not the ABI numbers it.
   The five numbered ones come first and in R-07-031b's order, so the
   filter below and the map over the invocation list are the same list.
   The rest are named by the entries that exclude them. *)
Inductive Act : Type :=
| ASend
| AReceive
| AYield
| AGrantRedeem
| ARevoke
| ANotifySignal                (* R-08-032: a store to an interrupt file  *)
| ANotifyReceive               (* R-07-039: ordinary loads at poll sites  *)
| AGrantMint                   (* R-08-004c: composition-time, not a request *)
| AFocusRebind                 (* R-11-023: the kernel enacts, at a frame *)
| ARungSelect                  (* R-11-024: likewise                      *)
| ASuspend                     (* R-11-026: likewise                      *)
| ASynchronousException        (* R-07-021: a kernel entry, not an invocation *)
| ARetype                      (* R-07-031a MUST NOT                      *)
| ACapSpaceOp                  (* R-07-031a MUST NOT                      *)
| ADerivationTreeOp            (* R-07-031a MUST NOT                      *)
| ASubmissionQueueOpcode       (* R-07-030 MUST NOT                       *)
| AReplyInvocation.            (* R-07-027a's fifth ABI group, not taken  *)

Definition all_invocations : list Invocation :=
  cons Send (cons Receive (cons PollSiteYield (cons GrantRedeem
  (cons Revoke nil)))).

Definition all_groups : list AbiGroup :=
  cons EndpointGroup (cons NotificationGroup (cons PartitionContextGroup
  (cons RevocationGroup nil))).

Definition all_nameable : list Nameable :=
  cons NEndpoint (cons NNotification (cons NPartitionContext
  (cons NGrantTable (cons NScheduleTable (cons NReplyObject nil))))).

Definition all_lifecycles : list Lifecycle :=
  cons LCreate (cons LDerive (cons LRevoke nil)).

(* Written as three segments joined rather than as one seventeen-deep
   nesting: the first is the numbered five in R-07-031b's order, the second
   is what the register excludes for a reason of its own, and the third is
   what a MUST NOT deletes. *)
Definition numbered_acts : list Act :=
  cons ASend (cons AReceive (cons AYield (cons AGrantRedeem
  (cons ARevoke nil)))).

Definition unnumbered_acts : list Act :=
  cons ANotifySignal (cons ANotifyReceive (cons AGrantMint
  (cons AFocusRebind (cons ARungSelect (cons ASuspend
  (cons ASynchronousException nil)))))).

Definition deleted_acts : list Act :=
  cons ARetype (cons ACapSpaceOp (cons ADerivationTreeOp
  (cons ASubmissionQueueOpcode (cons AReplyInvocation nil)))).

Definition all_acts : list Act :=
  app numbered_acts (app unnumbered_acts deleted_acts).

(* The counts the register closes, checked by conversion rather than
   claimed. The day an entry admits a sixth invocation or a fourth object
   class is the day one of them stops holding. *)
Example there_are_five_invocations : count_of all_invocations = 5 := eq_refl.

Example there_are_four_abi_groups : count_of all_groups = 4 := eq_refl.

(* R-07-031's *under a dozen*, with the margin that bound is for. *)
Example five_sits_under_a_dozen_with_margin :
  Nat.ltb (count_of all_invocations) 12 = true := eq_refl.

Definition inv_eqb (i j : Invocation) : bool :=
  match i, j with
  | Send, Send => true
  | Receive, Receive => true
  | PollSiteYield, PollSiteYield => true
  | GrantRedeem, GrantRedeem => true
  | Revoke, Revoke => true
  | _, _ => false
  end.

Lemma inv_eqb_refl : forall i : Invocation, inv_eqb i i = true.
Proof. intros i. destruct i; reflexivity. Qed.

Lemma inv_eqb_true : forall i j : Invocation, inv_eqb i j = true -> i = j.
Proof.
  intros i j. destruct i; destruct j; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition group_eqb (a b : AbiGroup) : bool :=
  match a, b with
  | EndpointGroup, EndpointGroup => true
  | NotificationGroup, NotificationGroup => true
  | PartitionContextGroup, PartitionContextGroup => true
  | RevocationGroup, RevocationGroup => true
  | _, _ => false
  end.

Definition nameable_eqb (a b : Nameable) : bool :=
  match a, b with
  | NEndpoint, NEndpoint => true
  | NNotification, NNotification => true
  | NPartitionContext, NPartitionContext => true
  | NGrantTable, NGrantTable => true
  | NScheduleTable, NScheduleTable => true
  | NReplyObject, NReplyObject => true
  | _, _ => false
  end.

Definition lifecycle_eqb (a b : Lifecycle) : bool :=
  match a, b with
  | LCreate, LCreate => true
  | LDerive, LDerive => true
  | LRevoke, LRevoke => true
  | _, _ => false
  end.

Definition act_eqb (a b : Act) : bool :=
  match a, b with
  | ASend, ASend => true
  | AReceive, AReceive => true
  | AYield, AYield => true
  | AGrantRedeem, AGrantRedeem => true
  | ARevoke, ARevoke => true
  | ANotifySignal, ANotifySignal => true
  | ANotifyReceive, ANotifyReceive => true
  | AGrantMint, AGrantMint => true
  | AFocusRebind, AFocusRebind => true
  | ARungSelect, ARungSelect => true
  | ASuspend, ASuspend => true
  | ASynchronousException, ASynchronousException => true
  | ARetype, ARetype => true
  | ACapSpaceOp, ACapSpaceOp => true
  | ADerivationTreeOp, ADerivationTreeOp => true
  | ASubmissionQueueOpcode, ASubmissionQueueOpcode => true
  | AReplyInvocation, AReplyInvocation => true
  | _, _ => false
  end.

(* Each equality is reflexive on its own carrier and separates every other
   pair, checked as two conversions apiece: the first reads the diagonal
   and the second reads everything off it. All five are here rather than the
   four the obligations below happen to read, because a diagonal no statement
   reads is a constructor whose case can be turned false with nothing
   noticing, which is what a seeded population reports as a survivor. *)
Example the_five_equalities_are_reflexive :
  all_of (fun i => inv_eqb i i) all_invocations = true
  /\ all_of (fun g => group_eqb g g) all_groups = true
  /\ all_of (fun c => nameable_eqb c c) all_nameable = true
  /\ all_of (fun op => lifecycle_eqb op op) all_lifecycles = true
  /\ all_of (fun a => act_eqb a a) all_acts = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example the_five_equalities_separate_every_other_pair :
  all_of (fun i => Nat.eqb (count_of (filter_of (inv_eqb i) all_invocations)) 1)
         all_invocations = true
  /\ all_of (fun g => Nat.eqb (count_of (filter_of (group_eqb g) all_groups)) 1)
         all_groups = true
  /\ all_of (fun c => Nat.eqb (count_of (filter_of (nameable_eqb c) all_nameable)) 1)
         all_nameable = true
  /\ all_of (fun op => Nat.eqb (count_of (filter_of (lifecycle_eqb op)
                                                    all_lifecycles)) 1)
         all_lifecycles = true
  /\ all_of (fun a => Nat.eqb (count_of (filter_of (act_eqb a) all_acts)) 1)
         all_acts = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* =========================================================================
   The four groups over the five members (R-07-031a, R-07-031b).
   ========================================================================= *)

Definition group_of (i : Invocation) : AbiGroup :=
  match i with
  | Send => EndpointGroup
  | Receive => EndpointGroup
  | PollSiteYield => PartitionContextGroup
  | GrantRedeem => RevocationGroup
  | Revoke => RevocationGroup
  end.

Definition members_of (g : AbiGroup) : list Invocation :=
  filter_of (fun i => group_eqb (group_of i) g) all_invocations.

(* The census, computed rather than described. The notification group's
   zero is the whole of reading 4: it is what filtering returns, not a
   claim this file makes about a group it left out. *)
Example the_group_census :
  map_over (fun g => count_of (members_of g)) all_groups
  = cons 2 (cons 0 (cons 1 (cons 2 nil))) := eq_refl.

Example the_notification_group_is_empty : members_of NotificationGroup = nil := eq_refl.

Example the_endpoint_group_is_the_send_and_the_receive :
  members_of EndpointGroup = cons Send (cons Receive nil)
  /\ members_of PartitionContextGroup = cons PollSiteYield nil
  /\ members_of RevocationGroup = cons GrantRedeem (cons Revoke nil) :=
  conj eq_refl (conj eq_refl eq_refl).

(* Every member is in one of the four groups and the four cover the five,
   so the grouping neither drops a member nor invents a fifth group. *)
Example the_four_groups_cover_the_five_members :
  count_of (app (members_of EndpointGroup)
           (app (members_of NotificationGroup)
           (app (members_of PartitionContextGroup)
                (members_of RevocationGroup)))) = 5 := eq_refl.

(* Reading 4 as an obligation over an arbitrary grouping rather than as a
   conversion over the one this file writes. R-07-031b's second accept clause
   is that the notification group is empty and that the emptiness is a
   result: both halves are memory operations, so neither is a member of the
   invocation type at all and no member of that type can be filed under the
   notification group. Stated of an arbitrary grouping so that a grouping
   that files one there is exhibitable and can be refused, which is what the
   conversion above could not be. *)
Definition Grouping : Type := Invocation -> AbiGroup.

Definition census (g : Grouping) (a : AbiGroup) : nat :=
  count_of (filter_of (fun i => group_eqb (g i) a) all_invocations).

Definition TheNotificationGroupIsEmpty (g : Grouping) : Prop :=
  forall i : Invocation, group_eqb (g i) NotificationGroup = false.

(* R-07-031b's four-way assignment transcribed member by member as that entry
   states it, rather than by pointing at `group_of`'s body: *Endpoint: (i)
   send and (ii) receive. Notification: none. Partition-context: (iii) the
   poll-site yield. Revocation: (iv) grant redeem and (v) revoke.* This
   replaces a coverage clause that decided nothing: a census summing the four
   filters over a five-member list answers five for every total function
   whatever, including the one that files all five under the notification
   group, so it was true of every grouping and refutable by none. *)
Definition AssignsTheGroupsTheEntryAssigns (g : Grouping) : Prop :=
  g Send = EndpointGroup
  /\ g Receive = EndpointGroup
  /\ g PollSiteYield = PartitionContextGroup
  /\ g GrantRedeem = RevocationGroup
  /\ g Revoke = RevocationGroup.

(* S9a and S9b (R-07-031a, R-07-031b). *)
Theorem the_specification_grouping_leaves_the_notification_group_empty :
  TheNotificationGroupIsEmpty group_of.
Proof. intros i. destruct i; reflexivity. Qed.

Theorem the_specification_grouping_makes_the_entrys_assignment :
  AssignsTheGroupsTheEntryAssigns group_of.
Proof.
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  split; [ reflexivity | split; reflexivity ].
Qed.

(* S9c: and the emptiness is a consequence of that assignment rather than a
   clause beside it, which is R-07-031b's *the notification group is empty,
   and that is a result rather than an omission* derived instead of restated.
   A grouping that makes the entry's assignment cannot file anything under the
   notification group, because the entry's assignment names a group for every
   one of the five and names that group for none of them. *)
Theorem the_entrys_assignment_empties_the_notification_group :
  forall g : Grouping,
    AssignsTheGroupsTheEntryAssigns g -> TheNotificationGroupIsEmpty g.
Proof.
  intros g [ H1 [ H2 [ H3 [ H4 H5 ] ] ] ] i.
  destruct i; [ rewrite H1 | rewrite H2 | rewrite H3 | rewrite H4
              | rewrite H5 ]; reflexivity.
Qed.

(* =========================================================================
   Which acts the ABI numbers, and which merely trap (R-07-031b's first
   accept clause, R-07-021, R-07-030, R-07-031a).
   ========================================================================= *)

Definition act_of (i : Invocation) : Act :=
  match i with
  | Send => ASend
  | Receive => AReceive
  | PollSiteYield => AYield
  | GrantRedeem => AGrantRedeem
  | Revoke => ARevoke
  end.

Definition numbered_act (a : Act) : bool :=
  match a with
  | ASend => true
  | AReceive => true
  | AYield => true
  | AGrantRedeem => true
  | ARevoke => true
  | _ => false
  end.

(* R-07-031b's own criterion for what may take a number, stated over the
   closed invocation type rather than over `numbered_act`'s own body: an act
   may be numbered exactly where it is the act of one of the five that entry
   closes the list at, and an act outside those five is an amendment under
   R-18-034 rather than an extension of the freeze. Everything below that
   asks *what may be numbered* asks it of this, because an obligation written
   against `numbered_act` would be an implication from a hypothesis to itself
   and would hold of any body whatever, including one that numbered an act
   the entry excludes. *)
Definition is_the_act_of_an_invocation (a : Act) : bool :=
  any_of (fun i => act_eqb (act_of i) a) all_invocations.

(* What R-07-031a's three MUST NOTs, R-07-030's one and R-07-027a's untaken
   fifth group delete, as a boolean: these acts are not on the surface the
   frozen ABI specifies at all, so no admissible trap surface carries one. *)
Definition deleted_act (a : Act) : bool :=
  any_of (fun d => act_eqb d a) deleted_acts.

Example the_numbered_acts_are_exactly_the_five_invocations :
  filter_of numbered_act all_acts = map_over act_of all_invocations := eq_refl.

(* The criterion and this file's numbering agree at every act, which is what
   makes the discharge below a discharge: a `numbered_act` edited to admit a
   sixth act moves one side of this conversion and not the other. *)
Example the_criterion_and_the_specification_numbering_agree_everywhere :
  all_of (fun a => same_bool (is_the_act_of_an_invocation a) (numbered_act a))
         all_acts = true := eq_refl.

Example the_deleted_acts_take_no_number :
  filter_of deleted_act all_acts = deleted_acts
  /\ all_of (fun a => negb (is_the_act_of_an_invocation a)) deleted_acts = true
  := conj eq_refl eq_refl.

(* =========================================================================
   The trap surface is a parameter, and gap i is why.

   R-07-031b's third accept clause decides that the schedule transitions take
   no ABI number, and it decides that much and no more: *what carries that
   request is owed at R-11-023 and is not an ABI act*. So whether a focus
   rebinding (R-11-023), a rung selection (R-11-024) or a suspension
   (R-11-026) reaches the kernel by trapping is open, and a file that decided
   it would be closing a register gap by fiat. What is stated here instead is
   the criterion the register does fix over a trap surface, with two values
   of the parameter both admissible under it and nothing choosing between
   them.
   ========================================================================= *)

Definition TrapSurface : Type := Act -> bool.

(* Clause by clause with the entry that fixes each. The three schedule
   transitions appear in no clause, which is gap i stated as an absence
   rather than described. *)
Definition AdmissibleTrapSurface (t : TrapSurface) : Prop :=
  (forall i : Invocation, t (act_of i) = true)
  /\ t ASynchronousException = true
  /\ t ANotifySignal = false
  /\ t ANotifyReceive = false
  /\ t AGrantMint = false
  /\ (forall a : Act, deleted_act a = true -> t a = false).

(* The value this file's own reading takes: R-07-021 admits a synchronous
   exception as a kernel entry and no entry calls a fault an invocation, so
   on this reading the trap surface is the five plus one. It is a value of
   the parameter and not the parameter. *)
Definition traps_act (a : Act) : bool :=
  match a with
  | ASend => true
  | AReceive => true
  | AYield => true
  | AGrantRedeem => true
  | ARevoke => true
  | ASynchronousException => true
  | _ => false
  end.

(* And the value the other answer to gap i takes: the compositor's request
   carried by a syscall, so the three schedule transitions trap without
   taking a number. R-11-023 has the kernel *enact* and the compositor
   *request*, and a request has to arrive somehow. *)
Definition traps_with_the_schedule_transitions (a : Act) : bool :=
  orb (traps_act a)
      (orb (act_eqb a AFocusRebind)
           (orb (act_eqb a ARungSelect) (act_eqb a ASuspend))).

(* S-i and S-i-a: both are admissible, which is the gap made checkable
   rather than asserted. *)
Theorem the_files_own_trap_surface_is_admissible :
  AdmissibleTrapSurface traps_act.
Proof.
  split; [ intros i; destruct i; reflexivity | ].
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  intros a H. destruct a; first [ discriminate H | reflexivity ].
Qed.

Theorem the_syscall_carried_trap_surface_is_admissible :
  AdmissibleTrapSurface traps_with_the_schedule_transitions.
Proof.
  split; [ intros i; destruct i; reflexivity | ].
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  intros a H. destruct a; first [ discriminate H | reflexivity ].
Qed.

(* And the criterion does exclude something, which is what makes admitting
   two values a result rather than the absence of a test. Three surfaces are
   refused, one per clause the register fixes, each shown to meet the clauses
   it does not break, so what refuses each is the named clause and not the
   shape of the construction. Without these the parameter would be a
   parameter over everything and gap i would be reported wider than the
   register leaves it. *)

(* R-07-031b's first clause: an invocation is requested by trapping in, so a
   poll-site yield carried by a memory write instead is not an invocation on
   any admissible surface. *)
Definition the_polled_yield_surface (a : Act) : bool :=
  andb (traps_act a) (negb (act_eqb a AYield)).

Theorem the_polled_yield_surface_is_inadmissible :
  ~ AdmissibleTrapSurface the_polled_yield_surface
  /\ the_polled_yield_surface ASynchronousException = true
  /\ the_polled_yield_surface ANotifySignal = false
  /\ the_polled_yield_surface AGrantMint = false
  /\ (forall a : Act, deleted_act a = true ->
        the_polled_yield_surface a = false).
Proof.
  split; [ intros [ H _ ]; specialize (H PollSiteYield); discriminate H | ].
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  intros a H. unfold the_polled_yield_surface.
  destruct a; first [ discriminate H | reflexivity ].
Qed.

(* R-08-032's clause: the signal is a store to an interrupt file, so a
   surface on which it traps is refused whatever it does elsewhere. It meets
   every other clause, the receive included. *)
Definition the_trapping_signal_surface (a : Act) : bool :=
  orb (traps_act a) (act_eqb a ANotifySignal).

Theorem the_trapping_signal_surface_is_inadmissible :
  ~ AdmissibleTrapSurface the_trapping_signal_surface
  /\ (forall i : Invocation, the_trapping_signal_surface (act_of i) = true)
  /\ the_trapping_signal_surface ASynchronousException = true
  /\ the_trapping_signal_surface ANotifyReceive = false
  /\ the_trapping_signal_surface AGrantMint = false.
Proof.
  split; [ intros [ _ [ _ [ H _ ] ] ]; discriminate H | ].
  split; [ intros i; destruct i; reflexivity | ].
  split; [ reflexivity | split; reflexivity ].
Qed.

(* R-07-030's and R-07-031a's clause, at the trap level rather than at the
   numbering: a deleted surface is not on the surface the frozen ABI
   specifies at all, so it cannot trap either. This one meets the first five
   clauses outright. *)
Definition the_trapping_opcode_surface (a : Act) : bool :=
  orb (traps_act a) (act_eqb a ASubmissionQueueOpcode).

Theorem the_trapping_opcode_surface_is_inadmissible :
  ~ AdmissibleTrapSurface the_trapping_opcode_surface
  /\ (forall i : Invocation, the_trapping_opcode_surface (act_of i) = true)
  /\ the_trapping_opcode_surface ASynchronousException = true
  /\ the_trapping_opcode_surface ANotifySignal = false
  /\ the_trapping_opcode_surface ANotifyReceive = false
  /\ the_trapping_opcode_surface AGrantMint = false.
Proof.
  split.
  - intros [ _ [ _ [ _ [ _ [ _ H ] ] ] ] ].
    specialize (H ASubmissionQueueOpcode eq_refl). discriminate H.
  - split; [ intros i; destruct i; reflexivity | ].
    split; [ reflexivity | ].
    split; [ reflexivity | split; reflexivity ].
Qed.

(* The three refused surfaces beside the two admitted ones, act by act, so
   the clause each breaks is on the line rather than inferred from it. *)
Example the_refused_surfaces_each_move_one_act :
  filter_of (fun a => negb (same_bool (traps_act a)
                                      (the_polled_yield_surface a))) all_acts
  = cons AYield nil
  /\ filter_of (fun a => negb (same_bool (traps_act a)
                                         (the_trapping_signal_surface a))) all_acts
  = cons ANotifySignal nil
  /\ filter_of (fun a => negb (same_bool (traps_act a)
                                         (the_trapping_opcode_surface a))) all_acts
  = cons ASubmissionQueueOpcode nil :=
  conj eq_refl (conj eq_refl eq_refl).

(* And nothing above chooses between the two admitted values: they differ on
   exactly the three acts gap i is about and agree on the other fourteen. *)
Example the_two_admissible_surfaces_differ_on_the_schedule_transitions_alone :
  filter_of (fun a => negb (same_bool (traps_act a)
                                      (traps_with_the_schedule_transitions a)))
            all_acts
  = cons AFocusRebind (cons ARungSelect (cons ASuspend nil)) := eq_refl.

Example the_trap_surface_is_six_or_nine :
  count_of (filter_of traps_act all_acts) = 6
  /\ count_of (filter_of traps_with_the_schedule_transitions all_acts) = 9 :=
  conj eq_refl eq_refl.

(* Reading 3 restated under the parameter, and this is what it still claims:
   the trap-shaped cut over-collects, by the exception surface alone on one
   value and by the exception surface and the three schedule transitions on
   the other. Which of the two the machine has is gap i; that the cut
   over-collects is invariant under the answer, and that invariance is what
   makes *what the ABI numbers* the decidable cut. *)
Example the_trap_cut_over_collects_by_the_exception_surface :
  filter_of (fun a => andb (traps_act a) (negb (numbered_act a))) all_acts
  = cons ASynchronousException nil := eq_refl.

Example the_syscall_carried_cut_over_collects_by_four :
  filter_of (fun a => andb (traps_with_the_schedule_transitions a)
                           (negb (numbered_act a))) all_acts
  = cons AFocusRebind (cons ARungSelect (cons ASuspend
    (cons ASynchronousException nil))) := eq_refl.

Example nothing_the_abi_numbers_fails_to_trap :
  filter_of (fun a => andb (numbered_act a) (negb (traps_act a))) all_acts
  = nil
  /\ filter_of (fun a => andb (numbered_act a)
                              (negb (traps_with_the_schedule_transitions a)))
               all_acts = nil := conj eq_refl eq_refl.

(* S-i-b: every admissible trap surface numbers every invocation, and none of
   them is the ABI's cut. The witness is the exception surface, which every
   admissible value carries and the criterion excludes from the numbering, so
   neither result turns on how gap i is answered. *)
Theorem every_admissible_trap_surface_carries_the_exception :
  forall t : TrapSurface, AdmissibleTrapSurface t ->
    t ASynchronousException = true
    /\ is_the_act_of_an_invocation ASynchronousException = false.
Proof. intros t [ _ [ H _ ] ]. exact (conj H eq_refl). Qed.

Theorem no_admissible_trap_surface_traps_a_notification_half :
  forall t : TrapSurface, AdmissibleTrapSurface t ->
    t ANotifySignal = false /\ t ANotifyReceive = false.
Proof. intros t [ _ [ _ [ H1 [ H2 _ ] ] ] ]. exact (conj H1 H2). Qed.

(* One candidate two entries already decide, and three the register decides
   only halfway. R-08-004c puts the grant mint at composition time, so it is
   not a principal's request at all and neither traps nor takes a number.
   R-07-031b decides of the three schedule transitions that they take no
   number and leaves what carries the compositor's request owed at R-11-023,
   so the trap column below is the parameter's and not a judgment taken
   here. *)
Example the_grant_mint_neither_traps_nor_takes_a_number :
  numbered_act AGrantMint = false
  /\ is_the_act_of_an_invocation AGrantMint = false
  /\ traps_act AGrantMint = false
  /\ traps_with_the_schedule_transitions AGrantMint = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Definition schedule_transitions : list Act :=
  cons AFocusRebind (cons ARungSelect (cons ASuspend nil)).

Example the_schedule_transitions_take_no_number_on_either_surface :
  all_of (fun a => negb (numbered_act a)) schedule_transitions = true
  /\ all_of (fun a => negb (is_the_act_of_an_invocation a))
            schedule_transitions = true
  /\ map_over traps_act schedule_transitions
     = cons false (cons false (cons false nil))
  /\ map_over traps_with_the_schedule_transitions schedule_transitions
     = cons true (cons true (cons true nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* R-07-031a's three MUST NOTs and R-07-030's one, in the same shape: the
   surface the frozen ABI specifies carries no retype, no capability-space
   and no derivation-tree invocation, and no submission-queue opcode
   dispatch re-enters privileged code. *)
Example the_deleted_surfaces_take_no_number :
  all_of (fun a => negb (numbered_act a))
         (cons ARetype (cons ACapSpaceOp (cons ADerivationTreeOp
         (cons ASubmissionQueueOpcode (cons AReplyInvocation nil)))))
  = true := eq_refl.

(* Both halves of a notification take no number, which is the mechanism
   under reading 4: R-08-032 makes the signal a store and R-07-039 makes
   the receive ordinary loads, so neither is a kernel entry at all. *)
Example neither_notification_half_traps_or_takes_a_number :
  all_of (fun a => andb (negb (numbered_act a)) (negb (traps_act a)))
         (cons ANotifySignal (cons ANotifyReceive nil)) = true
  /\ all_of (fun a => andb (negb (is_the_act_of_an_invocation a))
                           (negb (traps_with_the_schedule_transitions a)))
            (cons ANotifySignal (cons ANotifyReceive nil)) = true :=
  conj eq_refl eq_refl.

(* =========================================================================
   The surviving object inventory (R-07-027, R-07-027a, R-08-004d).
   ========================================================================= *)

Definition is_object (c : Nameable) : bool :=
  match c with
  | NEndpoint => true
  | NNotification => true
  | NPartitionContext => true
  | NGrantTable => false
  | NScheduleTable => false
  | NReplyObject => false
  end.

Definition is_table (c : Nameable) : bool :=
  match c with
  | NGrantTable => true
  | NScheduleTable => true
  | _ => false
  end.

Definition object_classes : list Nameable := filter_of is_object all_nameable.

Definition kernel_tables : list Nameable := filter_of is_table all_nameable.

(* R-07-027a's own arithmetic, computed: three object classes, two tables
   beside them, and one nameable that is neither because that entry refuses
   it. *)
Example the_inventory_is_three_classes_and_two_tables :
  count_of object_classes = 3
  /\ count_of kernel_tables = 2
  /\ object_classes = cons NEndpoint (cons NNotification
       (cons NPartitionContext nil))
  /\ kernel_tables = cons NGrantTable (cons NScheduleTable nil) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example a_table_is_not_an_object_and_a_reply_object_is_neither :
  all_of (fun c => negb (is_object c)) kernel_tables = true
  /\ is_object NReplyObject = false
  /\ is_table NReplyObject = false := conj eq_refl (conj eq_refl eq_refl).

Fixpoint occurrences_nm (c : Nameable) (l : list Nameable) : nat :=
  match l with
  | nil => 0
  | cons x r => if nameable_eqb c x then S (occurrences_nm c r) else occurrences_nm c r
  end.

(* A candidate inventory passes on two counts and they are separate: it
   names nothing but an object class, and it names each of R-07-027a's
   three exactly once. A construction below breaks each alone. *)
Definition inventory_ok (l : list Nameable) : bool :=
  andb (all_of is_object l)
       (all_of (fun c => Nat.eqb (occurrences_nm c l) 1) object_classes).

Definition InventoryIsClosedAtThree (l : list Nameable) : Prop :=
  all_of is_object l = true
  /\ all_of (fun c => Nat.eqb (occurrences_nm c l) 1) object_classes = true.

Lemma inventory_ok_sound :
  forall l : list Nameable, inventory_ok l = true -> InventoryIsClosedAtThree l.
Proof.
  intros l H. unfold inventory_ok in H.
  destruct (andb_split _ _ H) as [ H1 H2 ]. exact (conj H1 H2).
Qed.

Lemma inventory_ok_complete :
  forall l : list Nameable, InventoryIsClosedAtThree l -> inventory_ok l = true.
Proof. intros l [ H1 H2 ]. apply andb_join; [ exact H1 | exact H2 ]. Qed.

Definition spec_inventory : list Nameable := object_classes.

(* S1 (R-07-027a): the composed inventory passes both conjuncts. *)
Theorem the_specification_inventory_is_closed :
  InventoryIsClosedAtThree spec_inventory.
Proof. apply inventory_ok_sound. reflexivity. Qed.

(* =========================================================================
   What a capability may designate, and what has no lifecycle
   (R-07-027, R-07-027a, R-08-004d, R-11-024).
   ========================================================================= *)

Definition Designation : Type := nat -> Nameable.

Definition DesignatesOnlyObjects (d : Designation) : Prop :=
  forall c : nat, is_object (d c) = true.

Definition spec_designation : Designation := fun _ => NEndpoint.

(* S2 (R-07-027a): no capability names a table. *)
Theorem the_specification_designation_names_only_objects :
  DesignatesOnlyObjects spec_designation.
Proof. intros c. reflexivity. Qed.

Definition Lifecycles : Type := Nameable -> Lifecycle -> bool.

(* One value of a map the register does not fix. Which of the three acts each
   object class has is gap j; nothing below reads this map beyond the two
   obligations, and a map answering true at one cell discharges them as well
   as this one does, which `revoke_only_lifecycle` is here to show. *)
Definition spec_lifecycles : Lifecycles := fun c _ => is_object c.

Definition revoke_only_lifecycle : Lifecycles := fun c op =>
  andb (is_object c) (lifecycle_eqb op LRevoke).

(* R-07-027a's second sentence, which is the whole of what that entry states
   about a lifecycle: neither table is created, derived or revoked. Stated of
   an arbitrary map so that one admitting a table can be exhibited. *)
Definition NoTableHasALifecycle (f : Lifecycles) : Prop :=
  forall (c : Nameable) (op : Lifecycle), is_table c = true -> f c op = false.

(* And the twin, which is weaker than the one this file used to carry and
   weaker on purpose. R-07-027a's sentence is a distinction and not a
   schedule: it says the two tables have no lifecycle, and draws that as a
   contrast against the three classes a capability does designate. Which of
   the three acts each class has it does not say, and two entries push the
   other way, R-07-031a deleting the derivation-tree invocation outright and
   R-07-031b's closed five carrying no create and no derive; a statement
   asserting all three of every class would be this file deciding gap j
   rather than reading an entry, and no entry carries it. What is stated
   instead is the distinction itself, which is what a map refusing everything
   fails: on such a map the clause above holds of a map that draws no
   distinction at all. *)
Definition DistinguishesTheClassesFromTheTables (f : Lifecycles) : Prop :=
  exists (c : Nameable) (op : Lifecycle), is_object c = true /\ f c op = true.

(* S3 and S4 (R-07-027a, R-08-004d). *)
Theorem the_specification_gives_no_table_a_lifecycle :
  NoTableHasALifecycle spec_lifecycles.
Proof.
  intros c op H. unfold spec_lifecycles. destruct c; simpl in H;
    try discriminate H; reflexivity.
Qed.

Theorem the_specification_distinguishes_the_classes_from_the_tables :
  DistinguishesTheClassesFromTheTables spec_lifecycles.
Proof. exists NEndpoint. exists LRevoke. exact (conj eq_refl eq_refl). Qed.

(* S4a: and the two obligations do not decide gap j, which is why it is
   reported rather than closed. A map that admits one act of one class
   discharges both exactly as the map above does, so nothing below tells the
   two apart and a later entry fixing the acts instantiates a choice rather
   than amending a statement. *)
Theorem the_revoke_only_lifecycle_discharges_both :
  NoTableHasALifecycle revoke_only_lifecycle
  /\ DistinguishesTheClassesFromTheTables revoke_only_lifecycle.
Proof.
  split.
  - intros c op H. unfold revoke_only_lifecycle. destruct c; simpl in H;
      try discriminate H; reflexivity.
  - exists NEndpoint. exists LRevoke. exact (conj eq_refl eq_refl).
Qed.

Example the_two_lifecycle_maps_disagree_where_no_obligation_reads :
  map_over (spec_lifecycles NEndpoint) all_lifecycles
  = cons true (cons true (cons true nil))
  /\ map_over (revoke_only_lifecycle NEndpoint) all_lifecycles
  = cons false (cons false (cons true nil))
  /\ map_over (spec_lifecycles NGrantTable) all_lifecycles
  = cons false (cons false (cons false nil))
  /\ map_over (revoke_only_lifecycle NGrantTable) all_lifecycles
  = cons false (cons false (cons false nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* =========================================================================
   The return path (R-07-027a's second and third accept clauses, R-04-008,
   R-15-007, R-07-035).

   A synchronous server names its caller by the badge the invocation
   carries and replies by an ordinary send. That is stated as four
   obligations over an arbitrary return path rather than as one, because
   the arms R-07-027a records break different ones and a single obligation
   would not say which.
   ========================================================================= *)

Record ReturnPath : Type := {
  rp_classes : list Nameable;    (* the object classes the path spends     *)
  rp_otypes : nat;               (* R-15-007's object types it spends      *)
  rp_mints : bool;               (* whether the kernel mints at runtime    *)
  rp_act : Act                   (* the act the reply is                   *)
}.

Definition SpendsNoObjectClass (p : ReturnPath) : Prop := p.(rp_classes) = nil.

Definition SpendsNoObjectType (p : ReturnPath) : Prop := Nat.eqb p.(rp_otypes) 0 = true.

Definition MintsNothingAtRuntime (p : ReturnPath) : Prop := p.(rp_mints) = false.

Definition RepliesByAnAdmittedInvocation (p : ReturnPath) : Prop :=
  numbered_act p.(rp_act) = true.

(* R-07-027a's arm taken: the badge names the caller and the reply is an
   ordinary send to the capability that badge designates. *)
Definition badge_return : ReturnPath :=
  {| rp_classes := nil; rp_otypes := 0; rp_mints := false; rp_act := ASend |}.

(* S5 through S8 (R-07-027a, R-04-008, R-15-007). *)
Theorem the_badge_return_path_discharges_all_four :
  SpendsNoObjectClass badge_return
  /\ SpendsNoObjectType badge_return
  /\ MintsNothingAtRuntime badge_return
  /\ RepliesByAnAdmittedInvocation badge_return.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; reflexivity ] ].
Qed.

(* =========================================================================
   The frozen surface: where a member stands in the numbered sequence, and
   what the sequence has to be (R-07-031a, R-07-031b).
   ========================================================================= *)

Fixpoint pos_inv (i : Invocation) (l : list Invocation) : option nat :=
  match l with
  | nil => None
  | cons x r =>
      if inv_eqb i x then Some 0
      else match pos_inv i r with Some k => Some (S k) | None => None end
  end.

Fixpoint nth_inv (l : list Invocation) (n : nat) : option Invocation :=
  match l, n with
  | nil, _ => None
  | cons x _, 0 => Some x
  | cons _ r, S k => nth_inv r k
  end.

Fixpoint occurrences_inv (i : Invocation) (l : list Invocation) : nat :=
  match l with
  | nil => 0
  | cons x r => if inv_eqb i x then S (occurrences_inv i r) else occurrences_inv i r
  end.

Definition spec_surface : list Invocation := all_invocations.

(* Reading 2: the check is over membership and not over order, so a
   permutation of the sequence is still the frozen surface and only a
   deletion or a duplication is refused. *)
Definition frozen_surface (l : list Invocation) : bool :=
  all_of (fun i => Nat.eqb (occurrences_inv i l) 1) all_invocations.

Definition IsTheFrozenSurface (l : list Invocation) : Prop :=
  forall i : Invocation, Nat.eqb (occurrences_inv i l) 1 = true.

Lemma frozen_surface_sound :
  forall l : list Invocation, frozen_surface l = true -> IsTheFrozenSurface l.
Proof.
  intros l H i. unfold frozen_surface in H. unfold all_invocations in H.
  simpl in H.
  destruct (andb_split _ _ H) as [ H1 R1 ].
  destruct (andb_split _ _ R1) as [ H2 R2 ].
  destruct (andb_split _ _ R2) as [ H3 R3 ].
  destruct (andb_split _ _ R3) as [ H4 R4 ].
  destruct (andb_split _ _ R4) as [ H5 _ ].
  destruct i; assumption.
Qed.

(* And the other direction, without which `frozen_surface w = false` says
   nothing about the obligation and every refusal below would be a refusal of
   the decision procedure rather than of what it decides. *)
Lemma frozen_surface_complete :
  forall l : list Invocation, IsTheFrozenSurface l -> frozen_surface l = true.
Proof.
  intros l H. unfold frozen_surface. unfold all_invocations. simpl.
  rewrite (H Send). rewrite (H Receive). rewrite (H PollSiteYield).
  rewrite (H GrantRedeem). rewrite (H Revoke). reflexivity.
Qed.

(* The contrapositive, which is the shape every refusal below is stated in:
   a sequence the check refuses is not the frozen surface. *)
Lemma frozen_surface_refusal :
  forall l : list Invocation, frozen_surface l = false -> ~ IsTheFrozenSurface l.
Proof.
  intros l H C. rewrite (frozen_surface_complete l C) in H. discriminate H.
Qed.

(* S9 (R-07-031a, R-07-031b): the composed surface numbers each of the five
   exactly once. *)
Theorem the_specification_surface_is_the_frozen_one :
  IsTheFrozenSurface spec_surface.
Proof. apply frozen_surface_sound. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The number a member takes, which is stated relative to a sequence because
   gap d is that no entry says which sequence. R-07-031b closes the set and
   has the frozen surface assign the numbers; which number each member takes
   is nowhere fixed, so `index_in` reads a sequence, `index_of` is that
   function at the one sequence this file writes down, and the result that
   holds of every frozen surface is proved of an arbitrary one. A transposed
   surface assigns different numbers and is still the frozen surface, which
   is that gap exhibited rather than described.
   ------------------------------------------------------------------------- *)

Definition index_in (l : list Invocation) (i : Invocation) : nat :=
  match pos_inv i l with
  | Some k => k
  | None => count_of l
  end.

Definition index_of (i : Invocation) : nat := index_in spec_surface i.

Example the_invocation_indices :
  map_over index_of all_invocations
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil)))) := eq_refl.

Example a_number_past_the_surface_dispatches_to_nothing :
  nth_inv spec_surface 5 = None /\ nth_inv spec_surface 0 = Some Send
  /\ nth_inv spec_surface 4 = Some Revoke :=
  conj eq_refl (conj eq_refl eq_refl).

(* The number determines the member, over an arbitrary sequence: this is
   what makes *dispatched by that number* a property rather than an
   intention, and it holds of any sequence at all rather than only of one
   that passes the surface check. *)
Lemma pos_inv_nth :
  forall (l : list Invocation) (i : Invocation) (k : nat),
    pos_inv i l = Some k -> nth_inv l k = Some i.
Proof.
  intros l. induction l as [ | x r IH ]; intros i k H.
  - discriminate H.
  - simpl in H. destruct (inv_eqb i x) eqn:E.
    + injection H as Hk. rewrite <- Hk. simpl.
      rewrite (inv_eqb_true i x E). reflexivity.
    + destruct (pos_inv i r) as [ j | ] eqn:F; [ | discriminate H ].
      injection H as Hk. rewrite <- Hk. simpl. exact (IH i j F).
Qed.

(* S10 (R-07-031b): two members with the same number are the same member. *)
Theorem the_number_determines_the_invocation :
  forall (l : list Invocation) (i j : Invocation) (k : nat),
    pos_inv i l = Some k -> pos_inv j l = Some k -> i = j.
Proof.
  intros l i j k Hi Hj.
  assert (Ai : nth_inv l k = Some i) by exact (pos_inv_nth l i k Hi).
  assert (Aj : nth_inv l k = Some j) by exact (pos_inv_nth l j k Hj).
  rewrite Ai in Aj. injection Aj as Aj. rewrite Aj. reflexivity.
Qed.

(* S10a: and the other half, without which *dispatched by that number* would
   be a property of this file's sequence rather than of a frozen surface.
   Every member of every frozen surface has a number in it and that number
   dispatches back to it, so what gap d leaves open is which assignment a
   composition freezes and not whether there is one. *)
Lemma pos_inv_of_an_occurrence :
  forall (l : list Invocation) (i : Invocation),
    Nat.eqb (occurrences_inv i l) 0 = false ->
    exists k : nat, pos_inv i l = Some k.
Proof.
  intros l. induction l as [ | x r IH ]; intros i H.
  - discriminate H.
  - simpl in H |- *. destruct (inv_eqb i x) eqn:E.
    + exists 0. reflexivity.
    + destruct (IH i H) as [ k Hk ]. rewrite Hk. exists (S k). reflexivity.
Qed.

Theorem every_frozen_surface_numbers_every_member :
  forall l : list Invocation, IsTheFrozenSurface l ->
    forall i : Invocation,
      exists k : nat, pos_inv i l = Some k /\ nth_inv l k = Some i.
Proof.
  intros l H i.
  assert (Ho : Nat.eqb (occurrences_inv i l) 0 = false).
  { rewrite (nat_eqb_true _ _ (H i)). reflexivity. }
  destruct (pos_inv_of_an_occurrence l i Ho) as [ k Hk ].
  exists k. exact (conj Hk (pos_inv_nth l i k Hk)).
Qed.

(* =========================================================================
   Dispatch by the number and by nothing else (R-07-031b, R-07-030).

   A dispatcher is stated over an arbitrary observation of the caller and
   required not to vary with it, which is what *dispatched by that number*
   is as a property; and it is what a submission-queue opcode surface
   fails, R-07-030 refusing exactly the opcode read out of memory.
   ========================================================================= *)

Definition Observation : Type := nat -> nat.

Definition Dispatcher : Type := Observation -> nat -> option Invocation.

(* Dispatch is stated relative to a sequence for gap d's reason: which
   sequence a composition freezes is open, so the property is proved of the
   dispatcher any sequence induces and `spec_dispatch` is that dispatcher at
   the one sequence this file writes down. *)
Definition dispatch_of (l : list Invocation) : Dispatcher :=
  fun _ n => nth_inv l n.

Definition spec_dispatch : Dispatcher := dispatch_of spec_surface.

Definition DispatchesByTheNumberAlone (d : Dispatcher) : Prop :=
  forall (o1 o2 : Observation) (n : nat), d o1 n = d o2 n.

(* S11 (R-07-031b, R-07-030), of every sequence and then of this one. *)
Theorem every_surface_dispatches_by_the_number_alone :
  forall l : list Invocation, DispatchesByTheNumberAlone (dispatch_of l).
Proof. intros l o1 o2 n. reflexivity. Qed.

Theorem the_specification_dispatches_by_the_number_alone :
  DispatchesByTheNumberAlone spec_dispatch.
Proof. exact (every_surface_dispatches_by_the_number_alone spec_surface). Qed.

(* =========================================================================
   The generators over an invocation sequence (R-05-166). A refutation is a
   seeded weakening the theorem must reject, so these three produce
   families of them from the specification's own sequence rather than a
   person authoring each. Two families are refused and one is not, and the
   contrast is reading 2 made checkable.
   ========================================================================= *)

Fixpoint drop_at_inv (n : nat) (l : list Invocation) : list Invocation :=
  match n, l with
  | 0, cons _ r => r
  | 0, nil => nil
  | S k, cons a r => cons a (drop_at_inv k r)
  | S _, nil => nil
  end.

Fixpoint insert_at_inv (n : nat) (i : Invocation) (l : list Invocation)
  : list Invocation :=
  match n, l with
  | 0, _ => cons i l
  | S k, cons a r => cons a (insert_at_inv k i r)
  | S _, nil => cons i nil
  end.

Fixpoint swap_at_inv (n : nat) (l : list Invocation) : list Invocation :=
  match n, l with
  | 0, cons a (cons b r) => cons b (cons a r)
  | 0, _ => l
  | S k, cons a r => cons a (swap_at_inv k r)
  | S _, nil => nil
  end.

Definition deletions_inv (l : list Invocation) : list (list Invocation) :=
  map_over (fun n => drop_at_inv n l) (upto (count_of l)).

Definition insertions_inv (l : list Invocation) : list (list Invocation) :=
  map_over (fun n => insert_at_inv n Send l) (upto (S (count_of l))).

Definition transpositions_inv (l : list Invocation) : list (list Invocation) :=
  map_over (fun n => swap_at_inv n l) (upto (before_last (count_of l))).

Definition refused_weakenings (l : list Invocation) : list (list Invocation) :=
  app (deletions_inv l) (insertions_inv l).

(* The generic facts behind the three families, stated over an arbitrary
   sequence and an arbitrary index rather than over the five: an insertion
   adds one occurrence, a deletion never adds one, and a transposition
   moves none at all. *)
Lemma occurrences_of_insert :
  forall (n : nat) (i : Invocation) (l : list Invocation),
    occurrences_inv i (insert_at_inv n i l) = S (occurrences_inv i l).
Proof.
  intros n. induction n as [ | k IH ]; intros i l.
  - simpl. rewrite (inv_eqb_refl i). reflexivity.
  - destruct l as [ | a r ].
    + simpl. rewrite (inv_eqb_refl i). reflexivity.
    + simpl. rewrite (IH i r). destruct (inv_eqb i a); reflexivity.
Qed.

Lemma occurrences_of_drop :
  forall (n : nat) (i : Invocation) (l : list Invocation),
    Nat.leb (occurrences_inv i (drop_at_inv n l)) (occurrences_inv i l) = true.
Proof.
  intros n. induction n as [ | k IH ]; intros i l.
  - destruct l as [ | a r ]; [ reflexivity | ].
    simpl. destruct (inv_eqb i a).
    + apply nat_leb_succ.
    + apply nat_leb_refl.
  - destruct l as [ | a r ]; [ reflexivity | ].
    simpl. destruct (inv_eqb i a).
    + simpl. exact (IH i r).
    + exact (IH i r).
Qed.

Lemma occurrences_of_swap :
  forall (n : nat) (i : Invocation) (l : list Invocation),
    occurrences_inv i (swap_at_inv n l) = occurrences_inv i l.
Proof.
  intros n. induction n as [ | k IH ]; intros i l.
  - destruct l as [ | a [ | b r ] ]; try reflexivity.
    simpl. destruct (inv_eqb i a); destruct (inv_eqb i b); reflexivity.
  - destruct l as [ | a r ]; [ reflexivity | ].
    simpl. rewrite (IH i r). reflexivity.
Qed.

(* S12: a transposition of any sequence at any index is still the frozen
   surface, because the check reads occurrences and a transposition moves
   none. Stated over an arbitrary sequence, which is what makes the
   admitted family a result rather than a computation over four members. *)
Theorem no_transposition_leaves_the_frozen_surface :
  forall (n : nat) (l : list Invocation),
    frozen_surface l = true -> frozen_surface (swap_at_inv n l) = true.
Proof.
  intros n l H. unfold frozen_surface in H |- *.
  unfold all_invocations in H |- *. simpl in H |- *.
  repeat rewrite (occurrences_of_swap n). exact H.
Qed.

(* S12a: and an insertion of a member the sequence already carries is never
   the frozen surface, for the same reason read the other way. *)
Theorem no_insertion_of_a_present_member_is_the_frozen_surface :
  forall (n : nat) (i : Invocation) (l : list Invocation),
    Nat.eqb (occurrences_inv i l) 1 = true ->
    Nat.eqb (occurrences_inv i (insert_at_inv n i l)) 1 = false.
Proof.
  intros n i l H. rewrite (occurrences_of_insert n i l).
  rewrite (nat_eqb_true _ _ H). reflexivity.
Qed.

(* S12b: the same two at the level of the obligation rather than of the
   check, which the completeness lemma above is what makes available. A
   transposition of a frozen surface is one, and an insertion of a member it
   already carries is not, stated of `IsTheFrozenSurface` and so of what
   R-07-031b obliges rather than of the boolean this file computes it
   with. *)
Theorem no_transposition_leaves_the_frozen_surface_obligation :
  forall (n : nat) (l : list Invocation),
    IsTheFrozenSurface l -> IsTheFrozenSurface (swap_at_inv n l).
Proof.
  intros n l H i. rewrite (occurrences_of_swap n i l). exact (H i).
Qed.

Theorem no_insertion_of_a_present_member_meets_the_obligation :
  forall (n : nat) (i : Invocation) (l : list Invocation),
    IsTheFrozenSurface l -> ~ IsTheFrozenSurface (insert_at_inv n i l).
Proof.
  intros n i l H C.
  assert (Hb : Nat.eqb (occurrences_inv i (insert_at_inv n i l)) 1 = false) by
    exact (no_insertion_of_a_present_member_is_the_frozen_surface n i l (H i)).
  rewrite (C i) in Hb. discriminate Hb.
Qed.

(* Gap d as a conversion rather than a remark: the same five members, a
   different assignment of numbers to them, and both sequences the frozen
   surface. What this file's own `index_of` reads off is therefore a choice
   it makes and not a fact it reads, which is what gap d says and what the
   permutation-invariance of the check alone did not reach. *)
Example a_transposed_surface_assigns_different_numbers :
  map_over (index_in (swap_at_inv 0 spec_surface)) all_invocations
  = cons 1 (cons 0 (cons 2 (cons 3 (cons 4 nil))))
  /\ map_over (index_in spec_surface) all_invocations
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil))))
  /\ frozen_surface (swap_at_inv 0 spec_surface) = true
  /\ dispatch_of (swap_at_inv 0 spec_surface) (fun _ => 0) 0 = Some Receive
  /\ dispatch_of spec_surface (fun _ => 0) 0 = Some Send :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* =========================================================================
   The machine: everything the register leaves to composition. Fields
   rather than Parameters, because a top-level Parameter prints as an
   assumption and fails the R-05-163 gate.
   ========================================================================= *)

Record Machine : Type := {

  (* --- R-04-008's composition-fixed roster, and the endpoints over it --- *)

  partition_count : nat;
  endpoint_count : nat;

  (* --- R-07-031's medium: registers plus capability slots, and nothing
         else. Both budgets are the composition's ---------------------- *)

  word_count : nat;
  slot_count : nat;

  (* --- gap a: how wide the badge R-07-027a names the caller by is, and
         which field of R-15-007's frozen 64 carries it, is owed at
         R-07-031. Everything below quantifies over this --------------- *)

  badge_width : nat;

  (* --- R-07-029a's *within the invocation's own bounded cost*, per
         member, and what a refusal costs of it (gap c) ---------------- *)

  invocation_cost : Invocation -> nat;
  refusal_cost : Invocation -> nat;

  (* --- R-07-037b's same-label group: membership and order are
         composition constants, and R-07-037d makes the label the
         composer's obligation ---------------------------------------- *)

  group_members : list nat;
  label : nat -> nat;

  (* --- R-07-044's disjunction, and the interrupt file R-08-032 stores
         into and R-07-039 reads at poll sites ------------------------- *)

  pending_arm : bool;
  pending : nat -> nat -> bool;
  pending_width : nat
}.

(* -------------------------------------------------------------------------
   The demo machine, for R-05-165's uninhabited-domain mode and for the
   refutation witnesses. Three members of one label in a rotation, a fourth
   partition of another label so a mixed group is exhibitable, four
   endpoints so the readiness family is sixteen states, and a badge three
   bits wide so the badge space is eight. Every figure is an arbitrary
   witness value and carries no composition claim (gap h).
   ------------------------------------------------------------------------- *)

Definition demo_cost (i : Invocation) : nat :=
  match i with
  | Send => 4
  | Receive => 4
  | PollSiteYield => 2
  | GrantRedeem => 6
  | Revoke => 9
  end.

Definition demo_refusal (i : Invocation) : nat :=
  match i with
  | Send => 1
  | Receive => 1
  | PollSiteYield => 1
  | GrantRedeem => 2
  | Revoke => 2
  end.

Definition demo : Machine := {|
  partition_count := 4;
  endpoint_count := 4;
  word_count := 4;
  slot_count := 2;
  badge_width := 3;
  invocation_cost := demo_cost;
  refusal_cost := demo_refusal;
  group_members := cons 0 (cons 1 (cons 2 nil));
  label := fun u => if Nat.ltb u 3 then 0 else 1;
  pending_arm := true;
  pending := fun s b => Nat.eqb s b;
  pending_width := 3
|}.

(* The same composition on the other arm of R-07-044's disjunction: the
   pending bits are statically identity-partitioned rather than swapped, so
   no swap exists for R-07-037c to constrain. *)
Definition demo_static : Machine := {|
  partition_count := 4;
  endpoint_count := 4;
  word_count := 4;
  slot_count := 2;
  badge_width := 3;
  invocation_cost := demo_cost;
  refusal_cost := demo_refusal;
  group_members := cons 0 (cons 1 (cons 2 nil));
  label := fun u => if Nat.ltb u 3 then 0 else 1;
  pending_arm := false;
  pending := fun s b => Nat.eqb s b;
  pending_width := 3
|}.

(* The demo's declared quantities, computed rather than described, so that
   a figure edited on one side of the file and read on the other is a
   failed conversion instead of a silent disagreement. *)
Example the_demo_machine_declares :
  demo.(partition_count) = 4
  /\ demo.(endpoint_count) = 4
  /\ demo.(word_count) = 4
  /\ demo.(slot_count) = 2
  /\ demo.(badge_width) = 3
  /\ demo.(pending_width) = 3
  /\ demo.(pending_arm) = true
  /\ demo.(group_members) = cons 0 (cons 1 (cons 2 nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl)))))).

Example the_demo_costs :
  map_over demo.(invocation_cost) all_invocations
  = cons 4 (cons 4 (cons 2 (cons 6 (cons 9 nil))))
  /\ map_over demo.(refusal_cost) all_invocations
  = cons 1 (cons 1 (cons 1 (cons 2 (cons 2 nil)))) := conj eq_refl eq_refl.

Example the_demo_labels :
  map_over demo.(label) (upto 4) = cons 0 (cons 0 (cons 0 (cons 1 nil)))
  := eq_refl.

Example the_demo_interrupt_file :
  map_over (fun s => map_over (demo.(pending) s) (upto 3)) (upto 3)
  = cons (cons true (cons false (cons false nil)))
    (cons (cons false (cons true (cons false nil)))
    (cons (cons false (cons false (cons true nil))) nil)) := eq_refl.

(* The two machines are one composition on the two arms of R-07-044's
   disjunction, so every other field has to be read back as equal: an arm
   that also moved a budget would make the comparison below a comparison of
   two compositions rather than of two arms. This is also the inhabitation
   witness R-05-166 asks of the one obligation below that carries a
   hypothesis, `SwapsWhereASwapExists`, whose arm is `demo`'s. *)
Example the_two_pending_arms_differ :
  demo.(pending_arm) = true /\ demo_static.(pending_arm) = false :=
  conj eq_refl eq_refl.

Example the_static_arm_moves_nothing_but_the_arm :
  demo_static.(partition_count) = 4
  /\ demo_static.(endpoint_count) = 4
  /\ demo_static.(word_count) = 4
  /\ demo_static.(slot_count) = 2
  /\ demo_static.(badge_width) = 3
  /\ demo_static.(pending_width) = 3
  /\ demo_static.(group_members) = cons 0 (cons 1 (cons 2 nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

Example the_static_arm_declares_the_same_labels_and_costs :
  map_over demo_static.(label) (upto 4) = cons 0 (cons 0 (cons 0 (cons 1 nil)))
  /\ map_over demo_static.(invocation_cost) all_invocations
     = cons 4 (cons 4 (cons 2 (cons 6 (cons 9 nil))))
  /\ map_over demo_static.(refusal_cost) all_invocations
     = cons 1 (cons 1 (cons 1 (cons 2 (cons 2 nil))))
  /\ map_over (fun s => map_over (demo_static.(pending) s) (upto 3)) (upto 3)
     = cons (cons true (cons false (cons false nil)))
       (cons (cons false (cons true (cons false nil)))
       (cons (cons false (cons false (cons true nil))) nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* =========================================================================
   The message medium (R-07-029, R-07-031) and the badge (gap a).
   ========================================================================= *)

(* R-07-031's own sentence: registers plus capability slots, and no third
   component. Nothing here is typed structured data, and the payload's
   meaning is not modelled at all: what the entry fixes is the medium. The
   two components are written at `list nat` rather than behind an
   abbreviation for the reason the badge generator states: an abbreviation
   is opaque to the syntactic matching a rewrite does. *)
Record Message : Type := {
  msg_regs : list nat;         (* R-07-031's registers        *)
  msg_caps : list nat          (* R-07-031's capability slots *)
}.

Definition message_ok (m : Machine) (msg : Message) : bool :=
  andb (Nat.leb (count_of msg.(msg_regs)) m.(word_count))
       (Nat.leb (count_of msg.(msg_caps)) m.(slot_count)).

Definition CarriesNoBulkData (m : Machine) (msg : Message) : Prop :=
  message_ok m msg = true.

(* The badge is a bit list of the declared width, because the width is the
   gap: a later entry fixing it instantiates `badge_width` rather than
   amending anything below (reading 8). *)
Definition Badge : Type := list bool.

Definition badge_ok (m : Machine) (b : Badge) : bool :=
  Nat.eqb (count_of b) m.(badge_width).

(* Written at `list (list bool)` rather than at `list Badge`: the two are
   convertible and only one of them lets a rewrite over `count_of` find its
   own subterm, an abbreviation being opaque to syntactic matching. *)
Fixpoint badges (w : nat) : list (list bool) :=
  match w with
  | 0 => cons nil nil
  | S k => app (map_over (cons true) (badges k)) (map_over (cons false) (badges k))
  end.

(* S13 (R-07-031, R-15-007, gap a): every badge the generator produces at a
   width has that width, stated of an arbitrary width. *)
Theorem every_generated_badge_has_the_declared_width :
  forall w : nat, all_of (fun b => Nat.eqb (count_of b) w) (badges w) = true.
Proof.
  intros w. induction w as [ | k IH ].
  - reflexivity.
  - simpl. apply all_of_app_intro.
    + apply all_of_map. exact IH.
    + apply all_of_map. exact IH.
Qed.

(* S13a: and the badge space is two to the declared width, which is the
   quantity gap a leaves open and which every statement below is stated
   over rather than around. *)
Theorem the_badge_space_is_two_to_the_declared_width :
  forall w : nat, count_of (badges w) = two_pow w.
Proof.
  intros w. induction w as [ | k IH ].
  - reflexivity.
  - change (count_of (app (map_over (cons true) (badges k))
                          (map_over (cons false) (badges k)))
            = Nat.add (two_pow k) (two_pow k)).
    rewrite count_of_app. rewrite count_of_map. rewrite count_of_map.
    rewrite IH. reflexivity.
Qed.

(* =========================================================================
   The endpoint transfer (R-07-029, R-07-029a, R-07-037a, R-17-030x).

   An endpoint holds readiness and not a queue (reading 5), so its state is
   a predicate on the endpoint and the outcome of an offer is decided by
   that predicate alone. The kernel record below carries a parked list, a
   wait predicate and a runnable predicate the specification never touches;
   they are here so that the three constructions R-07-029a excludes are
   expressible and can be refused one obligation each (reading 12).
   ========================================================================= *)

Definition Readiness : Type := nat -> bool.

Record Offer : Type := {
  offer_from : nat;
  offer_at : nat;
  offer_carries : Message;
  offer_badge : Badge          (* R-07-027a's caller name, gap a wide *)
}.

(* R-07-029a's own vocabulary: the transfer either rendezvouses, in which
   case the message crosses at that instant, or it refuses, in which case
   nothing does. The refusal is a case rather than a value the caller may
   ignore, and gap b records that no entry enumerates its causes. *)
Inductive Outcome : Type :=
| Transferred (msg : Message)
| Refused.

Definition delivered (o : Outcome) : option Message :=
  match o with Transferred msg => Some msg | Refused => None end.

Definition is_refused (o : Outcome) : bool :=
  match o with Transferred _ => false | Refused => true end.

Record Parked : Type := {
  parked_from : nat;
  parked_at : nat
}.

Record Kernel : Type := {
  held : list Parked;          (* R-07-029a: there is no such queue      *)
  waiting : nat -> bool;       (* R-07-029a: no wait state either        *)
  runnable : nat -> bool       (* and no act that resumes another        *)
}.

(* The kernel state the specification starts from and never moves off:
   nothing parked, nobody waiting, everybody dispatchable. Its three fields
   are read back below rather than described, so a figure edited here and
   relied on there is a failed conversion. *)
Definition empty_kernel : Kernel :=
  {| held := nil; waiting := fun _ => false; runnable := fun _ => true |}.

Example the_probe_kernel_holds_nothing :
  held empty_kernel = nil
  /\ waiting empty_kernel 0 = false
  /\ waiting empty_kernel 3 = false
  /\ runnable empty_kernel 0 = true
  /\ runnable empty_kernel 3 = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Definition Transfer : Type := Kernel -> Readiness -> Offer -> prod Kernel Outcome.

Definition after (t : Transfer) (k : Kernel) (st : Readiness) (o : Offer) : Kernel :=
  fst (t k st o).

Definition said (t : Transfer) (k : Kernel) (st : Readiness) (o : Offer) : Outcome :=
  snd (t k st o).

Definition spec_transfer : Transfer := fun k st o =>
  pair k (if st o.(offer_at) then Transferred o.(offer_carries) else Refused).

(* The five obligations R-07-029a and R-07-037a put on a transfer, stated
   apart because a construction below breaks each of them alone. *)
Definition RefusesWithNoReadyPeer (t : Transfer) : Prop :=
  forall (k : Kernel) (st : Readiness) (o : Offer),
    st o.(offer_at) = false -> said t k st o = Refused.

Definition RendezvousWithAReadyPeer (t : Transfer) : Prop :=
  forall (k : Kernel) (st : Readiness) (o : Offer),
    st o.(offer_at) = true -> said t k st o = Transferred o.(offer_carries).

Definition ParksNothing (t : Transfer) : Prop :=
  forall (k : Kernel) (st : Readiness) (o : Offer),
    held k = nil -> held (after t k st o) = nil.

Definition LeavesNoPartitionWaiting (t : Transfer) : Prop :=
  forall (k : Kernel) (st : Readiness) (o : Offer) (p : nat),
    waiting k p = false -> waiting (after t k st o) p = false.

Definition ResumesNoPartition (t : Transfer) : Prop :=
  forall (k : Kernel) (st : Readiness) (o : Offer) (p : nat),
    runnable (after t k st o) p = runnable k p.

(* S14 through S18 (R-07-029, R-07-029a, R-07-037a). *)
Theorem the_specification_refuses_with_no_ready_peer :
  RefusesWithNoReadyPeer spec_transfer.
Proof. intros k st o H. unfold said, spec_transfer. simpl. rewrite H. reflexivity. Qed.

Theorem the_specification_rendezvous_with_a_ready_peer :
  RendezvousWithAReadyPeer spec_transfer.
Proof. intros k st o H. unfold said, spec_transfer. simpl. rewrite H. reflexivity. Qed.

Theorem the_specification_parks_nothing : ParksNothing spec_transfer.
Proof. intros k st o H. unfold after, spec_transfer. simpl. exact H. Qed.

Theorem the_specification_leaves_no_partition_waiting :
  LeavesNoPartitionWaiting spec_transfer.
Proof. intros k st o p H. unfold after, spec_transfer. simpl. exact H. Qed.

Theorem the_specification_resumes_no_partition :
  ResumesNoPartition spec_transfer.
Proof. intros k st o p. unfold after, spec_transfer. reflexivity. Qed.

(* S19: the outcome is exactly the readiness bit, over an arbitrary
   readiness state and an arbitrary offer. This is what the generated
   sixteen-state family below is an instance of rather than a substitute
   for. *)
Theorem the_outcome_is_the_readiness_bit :
  forall (k : Kernel) (st : Readiness) (o : Offer),
    is_refused (said spec_transfer k st o) = negb (st o.(offer_at)).
Proof.
  intros k st o. unfold said, spec_transfer. simpl.
  destruct (st o.(offer_at)); reflexivity.
Qed.

(* Reading 6: *typed* is read as nothing crossing on the refusal arm, so
   the property is stated over an arbitrary carrier and an arbitrary
   delivery reading of it, and the status-word construction below is what
   that excludes. *)
Definition CarriesNothingWhereNothingCrossed
           (T : Type) (deliv : T -> option Message)
           (run : Readiness -> Offer -> T) : Prop :=
  forall (st : Readiness) (o : Offer),
    st o.(offer_at) = false -> deliv (run st o) = None.

Definition spec_run (st : Readiness) (o : Offer) : Outcome :=
  said spec_transfer empty_kernel st o.

(* S20 (R-07-029a's typed refusal). *)
Theorem the_specification_carries_nothing_where_nothing_crossed :
  CarriesNothingWhereNothingCrossed Outcome delivered spec_run.
Proof.
  intros st o H. unfold spec_run, said, spec_transfer. simpl.
  rewrite H. reflexivity.
Qed.

(* R-07-029a's Fail-closed clause: a refusal costs the caller its own
   invocation and never the core's slot, so the refusal cost is stated of
   an arbitrary cost function and bounded by the invocation's own. *)
Definition RefusalCostsItsOwnInvocation (m : Machine) (c : Invocation -> nat) : Prop :=
  forall i : Invocation, Nat.leb (c i) (m.(invocation_cost) i) = true.

(* S21 (R-07-029a, R-11-006). *)
Theorem the_specification_refusal_costs_its_own_invocation :
  RefusalCostsItsOwnInvocation demo demo.(refusal_cost).
Proof. intros i. destruct i; reflexivity. Qed.

(* The bound's own boundary, and it is a reading rather than a detail:
   R-07-029a puts the refusal *within the invocation's own bounded cost*,
   which admits a refusal that spends the whole of it and never more. This
   file takes that weaker reading, which is the one the entry's words
   carry; a statement refusing the boundary would be deciding what the
   register left open, and it is what separates *within* from *below*. *)
Definition boundary_refusal (m : Machine) (i : Invocation) : nat :=
  m.(invocation_cost) i.

Theorem the_refusal_that_spends_its_whole_invocation_is_admitted :
  RefusalCostsItsOwnInvocation demo (boundary_refusal demo).
Proof. intros i. unfold boundary_refusal. apply nat_leb_refl. Qed.

Example the_boundary_refusal_spends_exactly_its_invocation :
  map_over (boundary_refusal demo) all_invocations
  = cons 4 (cons 4 (cons 2 (cons 6 (cons 9 nil))))
  /\ Nat.ltb (boundary_refusal demo Send) (demo.(invocation_cost) Send) = false :=
  conj eq_refl eq_refl.

(* =========================================================================
   The re-offer (R-07-029a's third accept clause, R-07-042, R-11-010).

   A caller that must wait re-offers at its next visit, so the statement
   that matters is over an arbitrary sequence of offers: whatever a
   composition does, the kernel is holding nothing at the end of it. That
   is the latency landing in buffer depth rather than in kernel state.
   ========================================================================= *)

Fixpoint run_offers (t : Transfer) (k : Kernel) (st : Readiness)
                    (l : list Offer) : Kernel :=
  match l with
  | nil => k
  | cons o r => run_offers t (after t k st o) st r
  end.

(* S22 (R-07-029a, R-11-010): stated of an arbitrary transfer that parks
   nothing and an arbitrary offer sequence, so it is a property of the
   discipline rather than a computation over one witness. *)
Theorem no_sequence_of_re_offers_parks_anything :
  forall (t : Transfer), ParksNothing t ->
    forall (k : Kernel) (st : Readiness) (l : list Offer),
      held k = nil -> held (run_offers t k st l) = nil.
Proof.
  intros t Hp k st l. generalize dependent k.
  induction l as [ | o r IH ]; intros k H.
  - exact H.
  - simpl. exact (IH (after t k st o) (Hp k st o H)).
Qed.

(* S22a (R-17-030x): the fail-closed seam read as a statement. A partition
   that is never ready holds a standing denial of transfer against every
   peer that offers to it, for as long as it stays unready, so every
   outcome of an arbitrary offer sequence into an unready endpoint set is a
   refusal. *)
Fixpoint outcomes_of (t : Transfer) (k : Kernel) (st : Readiness)
                     (l : list Offer) : list Outcome :=
  match l with
  | nil => nil
  | cons o r => cons (said t k st o) (outcomes_of t (after t k st o) st r)
  end.

Theorem an_unready_peer_refuses_every_offer_in_a_sequence :
  forall (t : Transfer), RefusesWithNoReadyPeer t ->
    forall (st : Readiness), (forall e : nat, st e = false) ->
      forall (k : Kernel) (l : list Offer),
        all_of is_refused (outcomes_of t k st l) = true.
Proof.
  intros t Hr st Hst k l. generalize dependent k.
  induction l as [ | o s IH ]; intros k.
  - reflexivity.
  - simpl. rewrite (Hr k st o (Hst o.(offer_at))). simpl. exact (IH (after t k st o)).
Qed.

(* =========================================================================
   The explicit capability transfer (R-07-029, R-04-008).

   Three obligations over an arbitrary grant, and the three are genuinely
   separate: a construction below satisfies any two and breaks the third.
   ========================================================================= *)

Definition Holdings : Type := nat -> bool.

Definition carried (msg : Message) (c : nat) : bool :=
  any_of (fun s => Nat.eqb s c) msg.(msg_caps).

Definition Grant : Type := Message -> Holdings -> Holdings.

Definition spec_grant : Grant := fun msg h c => orb (h c) (carried msg c).

Definition MintsNothing (g : Grant) : Prop :=
  forall (msg : Message) (h : Holdings) (c : nat),
    g msg h c = true -> orb (h c) (carried msg c) = true.

Definition GrantsEverythingNamed (g : Grant) : Prop :=
  forall (msg : Message) (h : Holdings) (c : nat),
    carried msg c = true -> g msg h c = true.

Definition TransfersOnlyWhatIsNamed (g : Grant) : Prop :=
  forall (msg : Message) (h : Holdings) (c : nat),
    carried msg c = false -> g msg h c = h c.

(* S23 through S25 (R-07-029, R-04-008). *)
Theorem the_specification_grant_mints_nothing : MintsNothing spec_grant.
Proof. intros msg h c H. exact H. Qed.

Theorem the_specification_grant_grants_everything_named :
  GrantsEverythingNamed spec_grant.
Proof.
  intros msg h c H. unfold spec_grant. rewrite H.
  destruct (h c); reflexivity.
Qed.

Theorem the_specification_grant_transfers_only_what_is_named :
  TransfersOnlyWhatIsNamed spec_grant.
Proof.
  intros msg h c H. unfold spec_grant. rewrite H.
  destruct (h c); reflexivity.
Qed.

(* =========================================================================
   The notification path (R-07-031b, R-08-032, R-07-039, R-12-096).

   Both halves are memory operations, which is why the notification group
   is empty (reading 4): the signal is a store to an interrupt file and the
   receive is ordinary loads at poll sites. What is owed here is not an
   object representation but the two properties R-12-096 states of the
   word, and the recheck it states of the consumer.
   ========================================================================= *)

Inductive NotifyHalf : Type := NotifySignal | NotifyReceive.

Definition all_halves : list NotifyHalf :=
  cons NotifySignal (cons NotifyReceive nil).

Inductive Medium : Type := ByStore | ByLoad.

Definition medium_of (h : NotifyHalf) : Medium :=
  match h with NotifySignal => ByStore | NotifyReceive => ByLoad end.

Definition act_of_half (h : NotifyHalf) : Act :=
  match h with NotifySignal => ANotifySignal | NotifyReceive => ANotifyReceive end.

Example both_halves_are_memory_operations :
  map_over medium_of all_halves = cons ByStore (cons ByLoad nil)
  /\ all_of (fun h => negb (numbered_act (act_of_half h))) all_halves = true
  /\ all_of (fun h => negb (traps_act (act_of_half h))) all_halves = true :=
  conj eq_refl (conj eq_refl eq_refl).

(* R-12-096: the word is a binary armed state with a defined reset, and no
   notification counter exists. The two are separate obligations and each
   is stated over an arbitrary carrier so a construction can break one and
   keep the other. *)
Definition Coalescing (T : Type) (sig : T -> T) : Prop :=
  forall w : T, sig (sig w) = sig w.

Definition ResetIsDefined (T : Type) (armedp : T -> bool) (rst : T -> T) : Prop :=
  forall w : T, armedp (rst w) = false.

Definition armed_of (b : bool) : bool := b.

Definition spec_signal (b : bool) : bool := true.

Definition spec_reset (b : bool) : bool := false.

(* S26 and S27 (R-12-096). *)
Theorem the_specification_signal_coalesces : Coalescing bool spec_signal.
Proof. intros w. reflexivity. Qed.

Theorem the_specification_reset_is_defined :
  ResetIsDefined bool armed_of spec_reset.
Proof. intros w. reflexivity. Qed.

Example the_word_is_binary :
  spec_signal false = true /\ spec_signal true = true
  /\ spec_reset true = false /\ spec_reset false = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* R-12-096's protocol: the indices are the source of truth, the consumer
   drains, arms its word, re-reads the producer index, and sleeps only if
   the recheck still shows no work. A decider reads the two observations,
   and the two obligations over it are separate. *)
Record Ring : Type := {
  produced : nat;
  consumed : nat
}.

Definition has_work (r : Ring) : bool := Nat.ltb r.(consumed) r.(produced).

Definition Decider : Type := Ring -> Ring -> bool.

Definition spec_decide : Decider := fun before now =>
  andb (negb (has_work before)) (negb (has_work now)).

Definition RechecksAfterArming (d : Decider) : Prop :=
  forall b n : Ring, has_work n = true -> d b n = false.

Definition YieldsOnlyOnAnEmptyDrain (d : Decider) : Prop :=
  forall b n : Ring, has_work b = true -> d b n = false.

(* S28 and S29 (R-12-096, R-07-029a). *)
Theorem the_specification_decider_rechecks_after_arming :
  RechecksAfterArming spec_decide.
Proof.
  intros b n H. unfold spec_decide. rewrite H.
  destruct (has_work b); reflexivity.
Qed.

Theorem the_specification_decider_yields_only_on_an_empty_drain :
  YieldsOnlyOnAnEmptyDrain spec_decide.
Proof. intros b n H. unfold spec_decide. rewrite H. reflexivity. Qed.

(* R-07-029a's ruling on R-12-096's verb: *sleep* is the poll-site yield,
   which is a synchronous invocation that advances the composition-fixed
   rotation and returns. It is nowhere a block, and it is one of the five
   rather than a sixth. *)
Definition sleep_invocation : Invocation := PollSiteYield.

Example the_sleep_the_consumer_reaches_is_the_poll_site_yield :
  sleep_invocation = PollSiteYield
  /\ numbered_act (act_of sleep_invocation) = true
  /\ group_of sleep_invocation = PartitionContextGroup :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   The rotation (R-07-037b, R-07-037c, R-07-037d, R-07-044).

   Two obligations over one rotation, answered in opposite directions
   (reading 9): the pending component is delivery and is swapped, and the
   zeroize class is confidentiality and is admitted in domain. They are
   stated apart and each construction below is shown to satisfy the other.
   ========================================================================= *)

Fixpoint rotate_from (l : list nat) (u : nat) (wrap : nat) : nat :=
  match l with
  | nil => wrap
  | cons x r => if Nat.eqb x u then head_or r wrap else rotate_from r u wrap
  end.

Definition advance (m : Machine) (u : nat) : nat :=
  rotate_from m.(group_members) u (head_or m.(group_members) u).

Definition Advancer : Type := Observation -> nat -> nat.

Definition spec_advance (m : Machine) : Advancer := fun _ u => advance m u.

(* R-07-037b's *composition-fixed rotation*: the successor does not vary
   with anything observed at run time. *)
Definition IsCompositionFixedRotation (a : Advancer) : Prop :=
  forall (o1 o2 : Observation) (u : nat), a o1 u = a o2 u.

(* S30 (R-07-037b). *)
Theorem the_specification_rotation_is_composition_fixed :
  forall m : Machine, IsCompositionFixedRotation (spec_advance m).
Proof. intros m o1 o2 u. reflexivity. Qed.

Example the_rotation_wraps_over_the_group :
  map_over (advance demo) demo.(group_members) = cons 1 (cons 2 (cons 0 nil))
  := eq_refl.

(* -------------------------------------------------------------------------
   R-07-037c: the pending component is swapped exactly as the switch does,
   on the arm of R-07-044's disjunction where a swap exists at all.
   ------------------------------------------------------------------------- *)

Definition Delivery : Type := nat -> nat -> nat -> bool.

Definition spec_delivery (m : Machine) : Delivery :=
  fun _ succ b => m.(pending) succ b.

(* R-07-044's purpose clause, which is owed on both arms of its disjunction
   and delivered by a different mechanism on each: no interrupt state is
   hidden or shared across a partition boundary, so a member begins its
   reaction seeing its own pending bits and no other member's. It carries no
   hypothesis, and that is the repair: written with `pending_arm = true` in
   front it says nothing at all on the static arm, where R-05-165's first
   mode makes it true of every delivery whatever. *)
Definition SeesItsOwnPendingOnly (m : Machine) (d : Delivery) : Prop :=
  forall p s b : nat, d p s b = m.(pending) s b.

(* R-07-037c's own verb, scoped as that entry scopes it, *on the arm of
   R-07-044's disjunction where a swap exists at all*. Its hypothesis is
   inhabited, `demo` being the witness R-05-166 asks for, and it is empty on
   the other arm by construction, which is stated below rather than left to
   be found. *)
Definition SwapsWhereASwapExists (m : Machine) (d : Delivery) : Prop :=
  m.(pending_arm) = true -> forall p s b : nat, d p s b = m.(pending) s b.

Definition DoesNotVaryWithThePredecessor (d : Delivery) : Prop :=
  forall p q s b : nat, d p s b = d q s b.

(* The inhabitation witness R-05-166 asks of that hypothesis is
   `the_two_pending_arms_differ` above, which reads both arms back off the two
   demo machines; it is cited here rather than restated, one conversion being
   enough to carry one fact. *)

(* S31, S31a and S32 (R-07-037c, R-07-044). *)
Theorem the_specification_delivery_sees_its_own_pending_only :
  forall m : Machine, SeesItsOwnPendingOnly m (spec_delivery m).
Proof. intros m p s b. reflexivity. Qed.

Theorem the_specification_delivery_swaps_where_a_swap_exists :
  forall m : Machine, SwapsWhereASwapExists m (spec_delivery m).
Proof. intros m _ p s b. reflexivity. Qed.

Theorem the_specification_delivery_does_not_vary_with_the_predecessor :
  forall m : Machine, DoesNotVaryWithThePredecessor (spec_delivery m).
Proof. intros m p q s b. reflexivity. Qed.

(* S32a: the two clauses are ordered rather than independent, and this is the
   direction that is real. Seeing one's own pending bits is a statement about
   the successor alone, so it entails not varying with the predecessor; the
   converse fails, `head_member_delivery` below meeting the weaker clause and
   breaking the stronger. So no construction meets the first and breaks the
   second and none can, and what the weaker clause is stated for is that a
   construction can be refuted by it alone. That is one obligation ordering
   another and not two independent ones, which is said here rather than
   implied by exhibiting only the separation that exists. *)
Theorem seeing_its_own_pending_entails_predecessor_independence :
  forall (m : Machine) (d : Delivery),
    SeesItsOwnPendingOnly m d -> DoesNotVaryWithThePredecessor d.
Proof.
  intros m d H p q s b. rewrite (H p s b). rewrite (H q s b). reflexivity.
Qed.

(* -------------------------------------------------------------------------
   R-07-037c's second conjunct: *the bits it leaves are restored to it at its
   next dispatch*.

   It is not statable of a `Delivery`, which reads a state and never moves
   one, so the state is modelled here rather than the conjunct being reported
   missing: a file per member, a dispatch step that runs one member, and the
   obligation that a step dispatching somebody else moves nobody else's bits.
   The restoration is then a consequence over an arbitrary sequence of
   dispatches rather than an assumption, and two constructions break it.
   ------------------------------------------------------------------------- *)

Definition Files : Type := nat -> nat -> bool.

Definition Step : Type := nat -> nat -> Files -> Files.

(* The specification's step: the member being dispatched reacts, writing
   whatever its reaction writes into its own file, and the step touches no
   other member's. The reaction is arbitrary because what a reaction writes
   is not this entry's subject. *)
Definition step_of (react : nat -> nat -> bool) : Step :=
  fun _ s f u b => if Nat.eqb u s then react u b else f u b.

Definition LeavesEveryOtherMembersBitsAlone (st : Step) : Prop :=
  forall (p s u b : nat) (f : Files),
    Nat.eqb u s = false -> st p s f u b = f u b.

Fixpoint run_dispatches (st : Step) (f : Files) (pred : nat) (l : list nat)
  : Files :=
  match l with
  | nil => f
  | cons s r => run_dispatches st (st pred s f) s r
  end.

Theorem the_specification_step_leaves_every_other_members_bits_alone :
  forall react : nat -> nat -> bool,
    LeavesEveryOtherMembersBitsAlone (step_of react).
Proof. intros react p s u b f H. unfold step_of. rewrite H. reflexivity. Qed.

(* S31c (R-07-037c's second conjunct): the bits a member leaves are the bits
   it finds, across any sequence of dispatches that does not name it. Stated
   of an arbitrary step meeting the clause above and of an arbitrary
   sequence, so it is a property of the discipline and not of one trace. *)
Theorem the_bits_a_member_leaves_are_restored_at_its_next_dispatch :
  forall st : Step, LeavesEveryOtherMembersBitsAlone st ->
    forall (l : list nat) (u : nat),
      all_of (fun s => negb (Nat.eqb u s)) l = true ->
      forall (f : Files) (pred b : nat),
        run_dispatches st f pred l u b = f u b.
Proof.
  intros st Hs l. induction l as [ | x r IH ]; intros u Hu f pred b.
  - reflexivity.
  - simpl in Hu. destruct (Nat.eqb u x) eqn:E.
    + simpl in Hu. discriminate Hu.
    + simpl in Hu. simpl.
      rewrite (IH u Hu (st pred x f) x b). exact (Hs pred x u b f E).
Qed.

(* -------------------------------------------------------------------------
   R-07-037d: the members of one group share a confidentiality domain, so a
   member may begin its reaction on the zeroize-class state a sibling left.
   The reviewable obligation is on the composer, and it is a different
   obligation from the one above.
   ------------------------------------------------------------------------- *)

Definition SameLabelGroup (m : Machine) (g : list nat) : bool :=
  all_of (fun u => Nat.eqb (m.(label) u) (m.(label) (head_or g u))) g.

Definition ResidueIsInDomain (m : Machine) (g : list nat) : Prop :=
  SameLabelGroup m g = true.

Lemma all_of_member :
  forall (p : nat -> bool) (l : list nat) (u : nat),
    all_of p l = true -> any_of (fun x => Nat.eqb x u) l = true -> p u = true.
Proof.
  intros p l. induction l as [ | x r IH ]; intros u Ha Ho.
  - discriminate Ho.
  - simpl in Ha. destruct (andb_split _ _ Ha) as [ Hx Hr ].
    simpl in Ho. destruct (Nat.eqb x u) eqn:E.
    + rewrite <- (nat_eqb_true x u E). exact Hx.
    + simpl in Ho. exact (IH u Hr Ho).
Qed.

(* S33 (R-07-037d): in an admissible group every observation of a sibling's
   residue is an observation inside one label, stated of an arbitrary group
   and an arbitrary label assignment. *)
Theorem an_admissible_group_keeps_the_residue_in_domain :
  forall (m : Machine) (g : list nat) (u v : nat),
    SameLabelGroup m g = true ->
    any_of (fun x => Nat.eqb x u) g = true ->
    any_of (fun x => Nat.eqb x v) g = true ->
    m.(label) u = m.(label) v.
Proof.
  intros m g u v Hg Hu Hv.
  assert (Au : Nat.eqb (m.(label) u) (m.(label) (head_or g u)) = true) by
    exact (all_of_member _ g u Hg Hu).
  assert (Av : Nat.eqb (m.(label) v) (m.(label) (head_or g v)) = true) by
    exact (all_of_member _ g v Hg Hv).
  destruct g as [ | x r ]; [ discriminate Hu | ].
  simpl in Au. simpl in Av.
  rewrite (nat_eqb_true _ _ Au). rewrite (nat_eqb_true _ _ Av). reflexivity.
Qed.

(* R-07-037d's third accept clause, which is the permissive reading's own
   limit: no member may assume the residue is any particular sibling's. An
   inference is stated as a partial map from a member to the sibling it
   claims left the residue, and the specification names none. *)
Definition Inference : Type := nat -> option nat.

Definition spec_inference : Inference := fun _ => None.

Definition ClaimsNoParticularSibling (f : Inference) : Prop :=
  forall s : nat, f s = None.

(* S34 (R-07-037d). *)
Theorem the_specification_claims_no_particular_sibling :
  ClaimsNoParticularSibling spec_inference.
Proof. intros s. reflexivity. Qed.

(* And why the claim would be wrong and not merely unlicensed: the residue
   at a class is whatever the last member to touch that class left, so a
   member that touched nothing leaves its predecessor's predecessor's
   value standing. The trace below computes that. *)
Definition Residue : Type := nat -> nat.

Definition leaves (writer : nat) (touches : nat -> bool) (r : Residue) : Residue :=
  fun c => if touches c then writer else r c.

(* =========================================================================
   The generated families (R-05-166). Each is produced from the
   specification's own structure rather than authored member by member,
   every member is decided as one conversion, and the family fact is stated
   again as a quantifier over the index so that a family is refused for a
   reason rather than by a computation over the members it happens to have.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   Family 1: every boolean enumeration over the closed invocation set. The
   five members give 32 predicates and exactly one of them is the frozen
   surface, which is R-07-031a's *the surface the frozen ABI specifies* as
   a computation.
   ------------------------------------------------------------------------- *)

Definition admits_of_mask (n : nat) : Invocation -> bool :=
  fun i => bit_at (index_of i) n.

Definition surface_mask_ok (n : nat) : bool :=
  all_of (admits_of_mask n) all_invocations.

Definition all_masks : list nat := upto (two_pow (count_of all_invocations)).

Example there_are_thirty_two_boolean_enumerations :
  count_of all_masks = 32 := eq_refl.

(* One conversion refusing thirty-one and admitting one. *)
Example only_the_full_enumeration_is_the_frozen_surface :
  filter_of surface_mask_ok all_masks = cons 31 nil := eq_refl.

(* S35: the same content as a quantifier over the index. The 31 is two to
   the five less one, and the five is R-07-031b's. *)
Theorem no_proper_boolean_enumeration_is_the_frozen_surface :
  forall n : nat, Nat.ltb n 31 = true -> surface_mask_ok n = false.
Proof.
  intros n H. do 31 (destruct n as [ | n ]; [ reflexivity | ]). discriminate H.
Qed.

Example the_full_enumeration_admits_every_member :
  all_of (admits_of_mask 31) all_invocations = true
  /\ map_over (admits_of_mask 30) all_invocations
     = cons false (cons true (cons true (cons true (cons true nil)))) :=
  conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   Family 2: deletions, insertions and transpositions over the numbered
   sequence. Two families are refused and one is not, and that contrast is
   reading 2 machine-checked rather than argued.
   ------------------------------------------------------------------------- *)

Example the_deletions_of_the_surface :
  deletions_inv spec_surface
  = cons (cons Receive (cons PollSiteYield (cons GrantRedeem (cons Revoke nil))))
    (cons (cons Send (cons PollSiteYield (cons GrantRedeem (cons Revoke nil))))
    (cons (cons Send (cons Receive (cons GrantRedeem (cons Revoke nil))))
    (cons (cons Send (cons Receive (cons PollSiteYield (cons Revoke nil))))
    (cons (cons Send (cons Receive (cons PollSiteYield (cons GrantRedeem nil))))
     nil)))) := eq_refl.

Example the_generated_weakening_family_size :
  count_of (refused_weakenings spec_surface) = 11
  /\ count_of (deletions_inv spec_surface) = 5
  /\ count_of (insertions_inv spec_surface) = 6
  /\ count_of (transpositions_inv spec_surface) = 4 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* S36: every deletion and every insertion is refused, as one conversion. *)
Example every_generated_weakening_is_refused :
  all_of (fun w => negb (frozen_surface w)) (refused_weakenings spec_surface)
  = true := eq_refl.

(* S36a: and per family, so a family that stopped biting is visible rather
   than absorbed by the conjunction above. *)
Example every_deletion_leaves_a_member_unnumbered :
  all_of (fun w => negb (frozen_surface w)) (deletions_inv spec_surface)
  = true := eq_refl.

Example every_insertion_numbers_a_member_twice :
  all_of (fun w => negb (frozen_surface w)) (insertions_inv spec_surface)
  = true := eq_refl.

(* S36b: and the family that is not refused, which is the whole of reading
   2. A permutation of the sequence is still the frozen surface because
   R-07-031b fixes the set and leaves the numbers to the composition
   (gap d). *)
Example every_transposition_is_still_a_frozen_surface :
  all_of frozen_surface (transpositions_inv spec_surface) = true := eq_refl.

Example the_transpositions_of_the_surface :
  transpositions_inv spec_surface
  = cons (cons Receive (cons Send (cons PollSiteYield (cons GrantRedeem
      (cons Revoke nil)))))
    (cons (cons Send (cons PollSiteYield (cons Receive (cons GrantRedeem
      (cons Revoke nil)))))
    (cons (cons Send (cons Receive (cons GrantRedeem (cons PollSiteYield
      (cons Revoke nil)))))
    (cons (cons Send (cons Receive (cons PollSiteYield (cons Revoke
      (cons GrantRedeem nil))))) nil))) := eq_refl.

(* The three families as quantifiers over the index. *)
Theorem no_deletion_is_the_frozen_surface :
  forall n : nat, Nat.ltb n 5 = true ->
    frozen_surface (drop_at_inv n spec_surface) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | n ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_insertion_is_the_frozen_surface :
  forall n : nat, Nat.ltb n 6 = true ->
    frozen_surface (insert_at_inv n Send spec_surface) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem every_transposition_index_is_still_the_frozen_surface :
  forall n : nat, frozen_surface (swap_at_inv n spec_surface) = true.
Proof.
  intros n. apply (no_transposition_leaves_the_frozen_surface n spec_surface).
  reflexivity.
Qed.

(* And the three families again against `IsTheFrozenSurface` rather than
   against the boolean that decides it, which is what completeness buys: a
   deletion and an insertion are refused by the obligation R-07-031b states
   and not only by this file's decision procedure, and a transposition meets
   it. Without this every refusal above would be a refutation of
   `frozen_surface` and the central Prop of this section would have none. *)
Theorem no_deletion_meets_the_frozen_surface_obligation :
  forall n : nat, Nat.ltb n 5 = true ->
    ~ IsTheFrozenSurface (drop_at_inv n spec_surface).
Proof.
  intros n H. apply frozen_surface_refusal.
  exact (no_deletion_is_the_frozen_surface n H).
Qed.

Theorem no_insertion_meets_the_frozen_surface_obligation :
  forall n : nat, Nat.ltb n 6 = true ->
    ~ IsTheFrozenSurface (insert_at_inv n Send spec_surface).
Proof.
  intros n H. apply frozen_surface_refusal.
  exact (no_insertion_is_the_frozen_surface n H).
Qed.

Theorem every_transposition_meets_the_frozen_surface_obligation :
  forall n : nat, IsTheFrozenSurface (swap_at_inv n spec_surface).
Proof.
  intros n. apply (no_transposition_leaves_the_frozen_surface_obligation n).
  exact the_specification_surface_is_the_frozen_one.
Qed.

(* -------------------------------------------------------------------------
   Family 3: every peer readiness state of a four-endpoint machine, and the
   family of transfers that cross to an unready peer below an index.
   ------------------------------------------------------------------------- *)

Definition probe_message : Message :=
  {| msg_regs := cons 0 (cons 1 nil); msg_caps := cons 7 nil |}.

Definition probe_badge : Badge := cons true (cons false (cons true nil)).

Definition offer_into (e : nat) : Offer :=
  {| offer_from := 0; offer_at := e; offer_carries := probe_message;
     offer_badge := probe_badge |}.

Example the_probe_message_and_the_probe_badge :
  probe_message.(msg_regs) = cons 0 (cons 1 nil)
  /\ probe_message.(msg_caps) = cons 7 nil
  /\ probe_badge = cons true (cons false (cons true nil))
  /\ badge_ok demo probe_badge = true
  /\ map_over offer_at (cons (offer_into 0) (cons (offer_into 3) nil))
     = cons 0 (cons 3 nil) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Definition readiness_of (n : nat) : Readiness := fun e => bit_at e n.

Fixpoint bools_eqb (l r : list bool) : bool :=
  match l, r with
  | nil, nil => true
  | cons a s, cons b t => andb (same_bool a b) (bools_eqb s t)
  | _, _ => false
  end.

(* The row comparison's own floor: it agrees only where every position
   agrees and only where the two rows are the same length, so a family
   conversion below decides all four endpoints rather than one of them. *)
Example bools_eqb_decides_position_by_position :
  bools_eqb nil nil = true
  /\ bools_eqb (cons true nil) (cons true nil) = true
  /\ bools_eqb (cons true nil) (cons false nil) = false
  /\ bools_eqb (cons true (cons false nil)) (cons true (cons true nil)) = false
  /\ bools_eqb nil (cons true nil) = false
  /\ bools_eqb (cons true nil) nil = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Definition outcome_row (n : nat) : list bool :=
  map_over (fun e => negb (is_refused (said spec_transfer empty_kernel
                                            (readiness_of n) (offer_into e))))
           (upto demo.(endpoint_count)).

Definition readiness_row (n : nat) : list bool :=
  map_over (fun e => readiness_of n e) (upto demo.(endpoint_count)).

Example there_are_sixteen_readiness_states :
  count_of (upto (two_pow demo.(endpoint_count))) = 16 := eq_refl.

(* S37: over every one of the sixteen readiness states of the demo machine,
   the transfer rendezvouses exactly where the peer is ready and refuses
   exactly where it is not. One conversion over the whole family. *)
Example the_rendezvous_or_refusal_family_agrees_with_the_readiness_state :
  all_of (fun n => bools_eqb (outcome_row n) (readiness_row n))
         (upto (two_pow demo.(endpoint_count))) = true := eq_refl.

(* S37a: the same content over an arbitrary readiness index and an
   arbitrary endpoint, which is stronger than the enumeration and is what
   makes the enumeration a check rather than the claim. *)
Theorem every_readiness_state_decides_the_outcome :
  forall n e : nat,
    is_refused (said spec_transfer empty_kernel (readiness_of n) (offer_into e))
    = negb (bit_at e n).
Proof.
  intros n e.
  exact (the_outcome_is_the_readiness_bit empty_kernel (readiness_of n)
                                          (offer_into e)).
Qed.

(* The family of transfers that cross to an unready peer at every endpoint
   below an index: `optimistic_at 0` is the specification's own behaviour
   and every later member breaks R-07-029a. *)
Definition optimistic_at (k : nat) : Transfer := fun kn st o =>
  pair kn (if orb (st o.(offer_at)) (Nat.ltb o.(offer_at) k)
           then Transferred o.(offer_carries) else Refused).

Definition refuses_where_unready (t : Transfer) : bool :=
  all_of (fun e => is_refused (said t empty_kernel (fun _ => false)
                                    (offer_into e)))
         (upto demo.(endpoint_count)).

Example the_optimistic_family_is_refused_from_its_first_member :
  map_over (fun k => refuses_where_unready (optimistic_at k))
           (upto (S demo.(endpoint_count)))
  = cons true (cons false (cons false (cons false (cons false nil))))
  := eq_refl.

Theorem no_optimistic_transfer_refuses_where_the_peer_is_unready :
  forall k : nat, Nat.ltb 0 k = true -> Nat.ltb k 5 = true ->
    refuses_where_unready (optimistic_at k) = false.
Proof.
  intros k. destruct k as [ | [ | [ | [ | [ | k ] ] ] ] ];
    intros H1 H2; first [ reflexivity | discriminate H1 | discriminate H2 ].
Qed.

(* -------------------------------------------------------------------------
   Family 4: deletions and insertions over the object inventory. The two
   conjuncts of `inventory_ok` are shown separate by two families, one
   breaking each.
   ------------------------------------------------------------------------- *)

Fixpoint drop_at_nm (n : nat) (l : list Nameable) : list Nameable :=
  match n, l with
  | 0, cons _ r => r
  | 0, nil => nil
  | S k, cons a r => cons a (drop_at_nm k r)
  | S _, nil => nil
  end.

Fixpoint insert_at_nm (n : nat) (c : Nameable) (l : list Nameable)
  : list Nameable :=
  match n, l with
  | 0, _ => cons c l
  | S k, cons a r => cons a (insert_at_nm k c r)
  | S _, nil => cons c nil
  end.

Definition inventory_deletions : list (list Nameable) :=
  map_over (fun n => drop_at_nm n spec_inventory) (upto (count_of spec_inventory)).

Definition inventory_insertions_of (c : Nameable) : list (list Nameable) :=
  map_over (fun n => insert_at_nm n c spec_inventory)
           (upto (S (count_of spec_inventory))).

Example the_inventory_family_sizes :
  count_of inventory_deletions = 3
  /\ count_of (inventory_insertions_of NReplyObject) = 4 := conj eq_refl eq_refl.

(* S38: every deletion is refused, and it is refused by the occurrence
   conjunct while the object conjunct still holds. *)
Example every_inventory_deletion_leaves_a_class_unnamed :
  all_of (fun l => andb (all_of is_object l)
                        (negb (all_of (fun c => Nat.eqb (occurrences_nm c l) 1)
                                      object_classes)))
         inventory_deletions = true := eq_refl.

(* S38a: a fourth class that is a table breaks the object conjunct and
   leaves the occurrence conjunct standing, which is the other half of the
   separation. *)
Example an_inserted_table_breaks_only_the_object_conjunct :
  all_of (fun l => andb (negb (all_of is_object l))
                        (all_of (fun c => Nat.eqb (occurrences_nm c l) 1)
                                object_classes))
         (inventory_insertions_of NGrantTable) = true := eq_refl.

(* S38b: and R-07-027a's own refused class, which breaks the same conjunct
   for the same reason: a reply object is not an object class. *)
Example an_inserted_reply_object_breaks_only_the_object_conjunct :
  all_of (fun l => andb (negb (all_of is_object l))
                        (all_of (fun c => Nat.eqb (occurrences_nm c l) 1)
                                object_classes))
         (inventory_insertions_of NReplyObject) = true := eq_refl.

(* S38c: a duplicated class breaks the occurrence conjunct alone. *)
Example a_duplicated_class_breaks_only_the_occurrence_conjunct :
  all_of (fun l => andb (all_of is_object l)
                        (negb (all_of (fun c => Nat.eqb (occurrences_nm c l) 1)
                                      object_classes)))
         (inventory_insertions_of NEndpoint) = true := eq_refl.

Example every_inventory_weakening_is_refused :
  all_of (fun l => negb (inventory_ok l))
         (app inventory_deletions
              (app (inventory_insertions_of NGrantTable)
                   (app (inventory_insertions_of NReplyObject)
                        (inventory_insertions_of NEndpoint)))) = true := eq_refl.

Theorem no_inventory_deletion_is_closed :
  forall n : nat, Nat.ltb n 3 = true ->
    inventory_ok (drop_at_nm n spec_inventory) = false.
Proof.
  intros n. destruct n as [ | [ | [ | n ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_fourth_class_is_closed :
  forall n : nat, Nat.ltb n 4 = true ->
    inventory_ok (insert_at_nm n NReplyObject spec_inventory) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | n ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* And both families again against the obligation rather than against the
   boolean that decides it, which `inventory_ok_complete` is what makes
   available. Without this the two theorems above would refute a decision
   procedure and `InventoryIsClosedAtThree` would carry no refutation, which
   is the shape the frozen surface's own families are held to. *)
Lemma inventory_refusal :
  forall l : list Nameable,
    inventory_ok l = false -> ~ InventoryIsClosedAtThree l.
Proof.
  intros l H C. rewrite (inventory_ok_complete l C) in H. discriminate H.
Qed.

Theorem no_inventory_deletion_meets_the_obligation :
  forall n : nat, Nat.ltb n 3 = true ->
    ~ InventoryIsClosedAtThree (drop_at_nm n spec_inventory).
Proof.
  intros n H. apply inventory_refusal. exact (no_inventory_deletion_is_closed n H).
Qed.

Theorem no_fourth_class_meets_the_obligation :
  forall n : nat, Nat.ltb n 4 = true ->
    ~ InventoryIsClosedAtThree (insert_at_nm n NReplyObject spec_inventory).
Proof.
  intros n H. apply inventory_refusal. exact (no_fourth_class_is_closed n H).
Qed.

(* -------------------------------------------------------------------------
   Family 5: the badge space at the declared width and at its neighbours.
   Gap a is why this is a family rather than a figure.
   ------------------------------------------------------------------------- *)

Example the_badges_of_width_two :
  badges 2 = cons (cons true (cons true nil))
             (cons (cons true (cons false nil))
             (cons (cons false (cons true nil))
             (cons (cons false (cons false nil)) nil))) := eq_refl.

Example there_are_eight_badges_at_the_declared_width :
  count_of (badges demo.(badge_width)) = 8 := eq_refl.

Example every_badge_of_the_declared_width_is_admitted :
  all_of (badge_ok demo) (badges demo.(badge_width)) = true := eq_refl.

Example no_badge_of_a_neighbouring_width_is_admitted :
  all_of (fun b => negb (badge_ok demo b))
         (app (badges 2) (badges 4)) = true := eq_refl.

(* =========================================================================
   Refutation witnesses over the frozen surface (R-05-166, R-07-031a,
   R-07-031b, R-07-030). Each is an alternative construction no index above
   generates, and each is shown to satisfy the obligations it does not
   break, so what refutes it is the named defect rather than the shape of
   the construction.
   ========================================================================= *)

Definition Numbering : Type := Act -> bool.

Definition NumbersEveryInvocation (f : Numbering) : Prop :=
  forall i : Invocation, f (act_of i) = true.

(* Stated against R-07-031b's own criterion for what may be numbered and not
   against `numbered_act`'s body. The second reading would be an implication
   from a hypothesis to itself: true of any body whatever, including one that
   numbered an act the entry excludes, and so a discharge of nothing. Written
   this way a `numbered_act` that admitted a sixth act fails it. *)
Definition NumbersNothingElse (f : Numbering) : Prop :=
  forall a : Act, is_the_act_of_an_invocation a = false -> f a = false.

Theorem the_specification_numbering_discharges_both :
  NumbersEveryInvocation numbered_act /\ NumbersNothingElse numbered_act.
Proof.
  split.
  - intros i. destruct i; reflexivity.
  - intros a H. destruct a; first [ discriminate H | reflexivity ].
Qed.

(* The trap-shaped cut, which is the reading R-07-031b's first accept clause
   refuses. It is stated of every admissible trap surface rather than of the
   one value this file names, so the result does not turn on how gap i is
   answered: whatever carries the compositor's request, the exception surface
   traps and the criterion excludes it from the numbering, so no admissible
   trap surface is the ABI's cut. That is reading 3 under the parameter, and
   it is what reading 3 still claims. *)
Theorem no_admissible_trap_surface_is_the_abi_cut :
  forall t : TrapSurface, AdmissibleTrapSurface t ->
    NumbersEveryInvocation t /\ ~ NumbersNothingElse t.
Proof.
  intros t A. destruct A as [ Hi [ Hx _ ] ].
  split.
  - intros i. exact (Hi i).
  - intros H. rewrite (H ASynchronousException eq_refl) in Hx. discriminate Hx.
Qed.

Theorem the_trap_shaped_cut_over_collects :
  NumbersEveryInvocation traps_act /\ ~ NumbersNothingElse traps_act.
Proof.
  exact (no_admissible_trap_surface_is_the_abi_cut traps_act
           the_files_own_trap_surface_is_admissible).
Qed.

Theorem the_syscall_carried_cut_over_collects :
  NumbersEveryInvocation traps_with_the_schedule_transitions
  /\ ~ NumbersNothingElse traps_with_the_schedule_transitions.
Proof.
  exact (no_admissible_trap_surface_is_the_abi_cut
           traps_with_the_schedule_transitions
           the_syscall_carried_trap_surface_is_admissible).
Qed.

(* A numbering that gives the schedule transitions ABI numbers, which is the
   other half of gap i and the half the register does close: whatever carries
   the compositor's request, R-07-031b's cut is what the ABI numbers and a
   focus rebinding is not one of the five. It numbers every invocation, so
   what refutes it is the three added acts. *)
Definition schedule_numbering : Numbering := fun a =>
  orb (numbered_act a) (any_of (fun s => act_eqb s a) schedule_transitions).

Theorem the_schedule_numbering_is_refuted :
  NumbersEveryInvocation schedule_numbering
  /\ ~ NumbersNothingElse schedule_numbering.
Proof.
  split.
  - intros i. unfold schedule_numbering. destruct i; reflexivity.
  - intros H. specialize (H AFocusRebind eq_refl). discriminate H.
Qed.

(* And a numbering that gives a notification half a number, which is reading
   4 refuted rather than computed: R-08-032 makes the signal a store and
   R-07-039 makes the receive ordinary loads, so neither is an act a
   principal requests by trapping in and the criterion excludes both. A
   construction that numbers one is the shape the emptiness of the
   notification group had no refutation of. *)
Definition notification_numbering : Numbering := fun a =>
  orb (numbered_act a)
      (orb (act_eqb a ANotifySignal) (act_eqb a ANotifyReceive)).

Theorem the_notification_numbering_is_refuted :
  NumbersEveryInvocation notification_numbering
  /\ ~ NumbersNothingElse notification_numbering.
Proof.
  split.
  - intros i. unfold notification_numbering. destruct i; reflexivity.
  - intros H. specialize (H ANotifySignal eq_refl). discriminate H.
Qed.

Example the_two_added_numberings_agree_with_the_specification_elsewhere :
  filter_of (fun a => negb (same_bool (numbered_act a) (schedule_numbering a)))
            all_acts
  = cons AFocusRebind (cons ARungSelect (cons ASuspend nil))
  /\ filter_of (fun a => negb (same_bool (numbered_act a)
                                         (notification_numbering a))) all_acts
  = cons ANotifySignal (cons ANotifyReceive nil) := conj eq_refl eq_refl.

(* An io_uring-style surface: a submission-queue opcode given a number, so
   an opcode dispatch re-enters privileged code. It numbers the five
   correctly, which is what makes the added opcode and not a different
   table the thing R-07-030 refuses. *)
Definition iouring_numbering : Numbering := fun a =>
  orb (numbered_act a) (act_eqb a ASubmissionQueueOpcode).

Theorem the_iouring_numbering_is_refuted :
  NumbersEveryInvocation iouring_numbering /\ ~ NumbersNothingElse iouring_numbering.
Proof.
  split.
  - intros i. unfold iouring_numbering. destruct i; reflexivity.
  - intros H. specialize (H ASubmissionQueueOpcode eq_refl). discriminate H.
Qed.

(* R-07-027a's first arm not taken: a fifth ABI group carrying a reply act.
   It breaks the same clause and nothing else, which is what makes it an
   amendment under R-18-034 rather than an extension of the freeze. *)
Definition fifth_group_numbering : Numbering := fun a =>
  orb (numbered_act a) (act_eqb a AReplyInvocation).

Theorem the_fifth_group_numbering_is_refuted :
  NumbersEveryInvocation fifth_group_numbering
  /\ ~ NumbersNothingElse fifth_group_numbering.
Proof.
  split.
  - intros i. unfold fifth_group_numbering. destruct i; reflexivity.
  - intros H. specialize (H AReplyInvocation eq_refl). discriminate H.
Qed.

(* And the other side of the separation: a surface that numbers nothing but
   the five and drops one of them satisfies the second clause outright and
   breaks the first, so the two are not one obligation stated twice. *)
Definition short_numbering : Numbering := fun a =>
  andb (numbered_act a) (negb (act_eqb a ARevoke)).

Theorem the_short_numbering_drops_a_member :
  ~ NumbersEveryInvocation short_numbering /\ NumbersNothingElse short_numbering.
Proof.
  split.
  - intros H. specialize (H Revoke). discriminate H.
  - intros a H. unfold short_numbering.
    destruct a; first [ discriminate H | reflexivity ].
Qed.

(* Reading 4's own refutation, which the census could not be: a grouping that
   files the poll-site yield under the notification group, on the reading
   that a yield is a partition waiting for one. It agrees with the
   specification on the other four members and still covers the five, so what
   refutes it is the member it files and not a different table. *)
Definition notifying_grouping : Grouping := fun i =>
  match i with PollSiteYield => NotificationGroup | _ => group_of i end.

Theorem the_notifying_grouping_fills_the_notification_group :
  ~ TheNotificationGroupIsEmpty notifying_grouping
  /\ ~ AssignsTheGroupsTheEntryAssigns notifying_grouping.
Proof.
  split.
  - intros H. specialize (H PollSiteYield). discriminate H.
  - intros [ _ [ _ [ H _ ] ] ]. discriminate H.
Qed.

(* And it breaks the entry's assignment at the one member it moves, meeting
   the other four clauses, so what refutes it is that member and not a
   different table. *)
Theorem the_notifying_grouping_keeps_the_four_clauses_it_does_not_break :
  notifying_grouping Send = EndpointGroup
  /\ notifying_grouping Receive = EndpointGroup
  /\ notifying_grouping GrantRedeem = RevocationGroup
  /\ notifying_grouping Revoke = RevocationGroup.
Proof.
  split; [ reflexivity | ].
  split; [ reflexivity | split; reflexivity ].
Qed.

(* The grouping the coverage clause could not refuse, kept as the witness of
   why it could not: it files every one of the five under the group
   R-07-031b says is empty, and the census the withdrawn clause summed still
   answers five of it. *)
Definition all_notification_grouping : Grouping := fun _ => NotificationGroup.

Theorem the_all_notification_grouping_is_refuted :
  ~ TheNotificationGroupIsEmpty all_notification_grouping
  /\ ~ AssignsTheGroupsTheEntryAssigns all_notification_grouping.
Proof.
  split.
  - intros H. specialize (H Send). discriminate H.
  - intros [ H _ ]. discriminate H.
Qed.

Example the_withdrawn_coverage_clause_answered_five_of_it :
  count_of (app (filter_of (fun i => group_eqb (all_notification_grouping i)
                                                EndpointGroup) all_invocations)
           (app (filter_of (fun i => group_eqb (all_notification_grouping i)
                                                NotificationGroup) all_invocations)
           (app (filter_of (fun i => group_eqb (all_notification_grouping i)
                                                PartitionContextGroup) all_invocations)
                (filter_of (fun i => group_eqb (all_notification_grouping i)
                                                RevocationGroup) all_invocations)))) = 5
  /\ census all_notification_grouping NotificationGroup = 5 :=
  conj eq_refl eq_refl.

Example the_notifying_grouping_moves_one_member_and_one_census :
  map_over (fun i => same_bool (group_eqb (notifying_grouping i) (group_of i))
                               true) all_invocations
  = cons true (cons true (cons false (cons true (cons true nil))))
  /\ map_over (census notifying_grouping) all_groups
     = cons 2 (cons 1 (cons 0 (cons 2 nil)))
  /\ map_over (census group_of) all_groups
     = cons 2 (cons 0 (cons 1 (cons 2 nil))) :=
  conj eq_refl (conj eq_refl eq_refl).

(* A dispatcher that reads its opcode out of memory rather than out of the
   trap's own number: R-07-030's submission-queue surface as a
   construction. *)
Definition submission_queue_dispatch : Dispatcher := fun o n =>
  nth_inv spec_surface (o n).

Definition quiet_memory : Observation := fun _ => 0.

Definition loaded_memory : Observation := fun _ => 4.

Theorem the_submission_queue_dispatch_is_refuted :
  ~ DispatchesByTheNumberAlone submission_queue_dispatch.
Proof.
  intros H. specialize (H quiet_memory loaded_memory 0). discriminate H.
Qed.

(* And it agrees with the specification wherever the memory happens to hold
   the number, so what refutes it is the read and not a different table. *)
Example the_submission_queue_dispatch_agrees_where_the_memory_agrees :
  submission_queue_dispatch (fun n => n) 2 = spec_dispatch quiet_memory 2
  /\ submission_queue_dispatch quiet_memory 2 = Some Send
  /\ submission_queue_dispatch loaded_memory 2 = Some Revoke
  /\ quiet_memory 2 = 0 /\ loaded_memory 2 = 4 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* =========================================================================
   Refutation witnesses over the inventory (R-07-027a, R-08-004d).
   ========================================================================= *)

Definition table_designation : Designation := fun c =>
  if Nat.eqb c 3 then NGrantTable else NEndpoint.

Theorem the_table_designation_is_refuted :
  ~ DesignatesOnlyObjects table_designation.
Proof. intros H. specialize (H 3). discriminate H. Qed.

(* And it names an object at every other index, so what refutes it is the
   one edge R-08-004d places outside the object classes. *)
Example the_table_designation_names_objects_everywhere_else :
  all_of (fun c => is_object (table_designation c)) (cons 0 (cons 1 (cons 2 nil)))
  = true /\ is_object (table_designation 3) = false := conj eq_refl eq_refl.

(* A lifecycle map that lets the schedule table be revoked, which is what
   R-11-024's rung change would be if the table were an object. *)
Definition table_lifecycle : Lifecycles := fun c op =>
  orb (is_object c) (nameable_eqb c NScheduleTable).

Theorem the_table_lifecycle_is_refuted :
  ~ NoTableHasALifecycle table_lifecycle
  /\ DistinguishesTheClassesFromTheTables table_lifecycle.
Proof.
  split.
  - intros H. specialize (H NScheduleTable LRevoke eq_refl). discriminate H.
  - exists NEndpoint. exists LRevoke. exact (conj eq_refl eq_refl).
Qed.

(* And the other side of that separation: a map that admits nothing keeps
   every table out and draws no distinction at all, so the two clauses are
   separate obligations and the second is what refuses this construction. *)
Definition frozen_lifecycle : Lifecycles := fun _ _ => false.

Theorem the_frozen_lifecycle_states_nothing :
  NoTableHasALifecycle frozen_lifecycle
  /\ ~ DistinguishesTheClassesFromTheTables frozen_lifecycle.
Proof.
  split.
  - intros c op H. reflexivity.
  - intros [ c [ op [ _ H ] ] ]. discriminate H.
Qed.

(* =========================================================================
   Refutation witnesses over the return path (R-07-027a, R-04-008,
   R-15-007, R-07-035).

   Four constructions, four clauses, and each construction satisfies the
   three it does not break: that is what makes *no reply object survives* a
   refutation of something rather than the absence of a constructor.
   ========================================================================= *)

Definition reply_object_return : ReturnPath :=
  {| rp_classes := cons NReplyObject nil; rp_otypes := 0; rp_mints := false;
     rp_act := ASend |}.

Theorem the_reply_object_return_spends_a_class :
  ~ SpendsNoObjectClass reply_object_return
  /\ SpendsNoObjectType reply_object_return
  /\ MintsNothingAtRuntime reply_object_return
  /\ RepliesByAnAdmittedInvocation reply_object_return.
Proof.
  split; [ intros H; discriminate H | ].
  split; [ reflexivity | split; reflexivity ].
Qed.

(* R-07-027a's second arm not taken: a one-shot linear reply capability
   sealed with an object type the kernel mints at runtime. It spends no
   object class, so what refutes it is the type and the mint. *)
Definition sealed_reply_return : ReturnPath :=
  {| rp_classes := nil; rp_otypes := 1; rp_mints := true; rp_act := ASend |}.

Theorem the_sealed_reply_return_spends_a_type_and_mints :
  SpendsNoObjectClass sealed_reply_return
  /\ ~ SpendsNoObjectType sealed_reply_return
  /\ ~ MintsNothingAtRuntime sealed_reply_return
  /\ RepliesByAnAdmittedInvocation sealed_reply_return.
Proof.
  split; [ reflexivity | ].
  split; [ intros H; discriminate H | ].
  split; [ intros H; discriminate H | reflexivity ].
Qed.

(* The two clauses that construction breaks are separate, and this is what
   shows it: a sealed reply capability minted at composition time spends
   the object type and mints nothing at runtime. *)
Definition composition_sealed_return : ReturnPath :=
  {| rp_classes := nil; rp_otypes := 1; rp_mints := false; rp_act := ASend |}.

Theorem the_composition_sealed_return_separates_the_type_from_the_mint :
  SpendsNoObjectClass composition_sealed_return
  /\ ~ SpendsNoObjectType composition_sealed_return
  /\ MintsNothingAtRuntime composition_sealed_return
  /\ RepliesByAnAdmittedInvocation composition_sealed_return.
Proof.
  split; [ reflexivity | ].
  split; [ intros H; discriminate H | split; reflexivity ].
Qed.

(* And the fifth-group arm again, from the return path's side: it spends no
   class, no type and no runtime mint, and replies by an act the frozen
   surface does not number. *)
Definition fifth_group_return : ReturnPath :=
  {| rp_classes := nil; rp_otypes := 0; rp_mints := false;
     rp_act := AReplyInvocation |}.

Theorem the_fifth_group_return_replies_by_an_unnumbered_act :
  SpendsNoObjectClass fifth_group_return
  /\ SpendsNoObjectType fifth_group_return
  /\ MintsNothingAtRuntime fifth_group_return
  /\ ~ RepliesByAnAdmittedInvocation fifth_group_return.
Proof.
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  split; [ reflexivity | intros H; discriminate H ].
Qed.

(* R-07-027a's own ground for the badge arm being available at all: with no
   blocking call there is no parked request for a reply object to
   represent. The specification parks nothing at any offer sequence, which
   is what leaves the reply object with nothing to stand for. *)
Definition three_offers : list Offer :=
  cons (offer_into 0) (cons (offer_into 1) (cons (offer_into 2) nil)).

Example the_specification_parks_nothing_across_a_re_offer_sequence :
  count_of (held (run_offers spec_transfer empty_kernel (fun _ => false)
                             three_offers)) = 0 := eq_refl.

(* The four return paths read back field by field, and the offer sequence
   read back endpoint by endpoint, so a figure the refutations above turn
   on is a conversion here rather than a number nothing checks. *)
Example the_four_return_paths_declare :
  map_over rp_otypes (cons badge_return (cons reply_object_return
    (cons sealed_reply_return (cons composition_sealed_return
    (cons fifth_group_return nil)))))
  = cons 0 (cons 0 (cons 1 (cons 1 (cons 0 nil))))
  /\ map_over rp_mints (cons badge_return (cons reply_object_return
    (cons sealed_reply_return (cons composition_sealed_return
    (cons fifth_group_return nil)))))
  = cons false (cons false (cons true (cons false (cons false nil))))
  /\ map_over rp_act (cons badge_return (cons reply_object_return
    (cons sealed_reply_return (cons composition_sealed_return
    (cons fifth_group_return nil)))))
  = cons ASend (cons ASend (cons ASend (cons ASend
    (cons AReplyInvocation nil))))
  /\ reply_object_return.(rp_classes) = cons NReplyObject nil :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_re_offer_sequence_visits_three_endpoints :
  map_over offer_at three_offers = cons 0 (cons 1 (cons 2 nil))
  /\ count_of three_offers = 3 := conj eq_refl eq_refl.

(* =========================================================================
   Refutation witnesses over the transfer (R-07-029, R-07-029a, R-07-037a).

   Five obligations and five constructions, each breaking exactly one: that
   is what makes reading 12 a result rather than a modelling preference.
   ========================================================================= *)

(* An endpoint that parks the offer it cannot satisfy, which is the
   blocked-partition queue R-07-029a says does not exist. It refuses
   correctly, leaves nobody waiting and resumes nobody, so what refutes it
   is the kernel state it accumulates. *)
Definition queueing_transfer : Transfer := fun k st o =>
  if st o.(offer_at)
  then pair k (Transferred o.(offer_carries))
  else pair {| held := cons {| parked_from := o.(offer_from);
                               parked_at := o.(offer_at) |} (held k);
               waiting := waiting k; runnable := runnable k |} Refused.

Theorem the_queueing_transfer_parks_a_request :
  RefusesWithNoReadyPeer queueing_transfer
  /\ RendezvousWithAReadyPeer queueing_transfer
  /\ ~ ParksNothing queueing_transfer
  /\ LeavesNoPartitionWaiting queueing_transfer
  /\ ResumesNoPartition queueing_transfer.
Proof.
  split; [ intros k st o H; unfold said, queueing_transfer; rewrite H;
           reflexivity | ].
  split; [ intros k st o H; unfold said, queueing_transfer; rewrite H;
           reflexivity | ].
  split.
  - intros H. specialize (H empty_kernel (fun _ => false) (offer_into 0) eq_refl).
    discriminate H.
  - split.
    + intros k st o p H. unfold after, queueing_transfer.
      destruct (st o.(offer_at)); exact H.
    + intros k st o p. unfold after, queueing_transfer.
      destruct (st o.(offer_at)); reflexivity.
Qed.

(* And the queue grows with the offer sequence, which is the cost
   R-07-029a's third accept clause puts in buffer depth instead: three
   re-offers into an unready endpoint leave three parked requests. *)
Example the_queueing_kernel_grows_with_the_offer_sequence :
  count_of (held (run_offers queueing_transfer empty_kernel (fun _ => false)
                             three_offers)) = 3 := eq_refl.

(* A send that leaves its caller in a kernel-held wait: R-07-029a's *no
   wait state in the partition context* and R-07-037a's *no blocking call*.
   It parks nothing and resumes nobody. *)
Definition blocking_transfer : Transfer := fun k st o =>
  if st o.(offer_at)
  then pair k (Transferred o.(offer_carries))
  else pair {| held := held k;
               waiting := fun p => orb (waiting k p) (Nat.eqb p o.(offer_from));
               runnable := runnable k |} Refused.

Theorem the_blocking_transfer_leaves_its_caller_waiting :
  RefusesWithNoReadyPeer blocking_transfer
  /\ ParksNothing blocking_transfer
  /\ ~ LeavesNoPartitionWaiting blocking_transfer
  /\ ResumesNoPartition blocking_transfer.
Proof.
  split; [ intros k st o H; unfold said, blocking_transfer; rewrite H;
           reflexivity | ].
  split.
  - intros k st o H. unfold after, blocking_transfer.
    destruct (st o.(offer_at)); exact H.
  - split.
    + intros H.
      specialize (H empty_kernel (fun _ => false) (offer_into 0) 0 eq_refl).
      discriminate H.
    + intros k st o p. unfold after, blocking_transfer.
      destruct (st o.(offer_at)); reflexivity.
Qed.

(* A kernel act that resumes a partition on another partition's behalf,
   which R-07-029a's third sentence refuses by name. It parks nothing and
   leaves nobody waiting, so the wake is what refutes it. *)
Definition waking_transfer : Transfer := fun k st o =>
  pair {| held := held k; waiting := waiting k;
          runnable := fun p => andb (runnable k p) (negb (Nat.eqb p o.(offer_at))) |}
       (if st o.(offer_at) then Transferred o.(offer_carries) else Refused).

Theorem the_waking_transfer_moves_another_partition :
  RefusesWithNoReadyPeer waking_transfer
  /\ ParksNothing waking_transfer
  /\ LeavesNoPartitionWaiting waking_transfer
  /\ ~ ResumesNoPartition waking_transfer.
Proof.
  split; [ intros k st o H; unfold said, waking_transfer; simpl; rewrite H;
           reflexivity | ].
  split; [ intros k st o H; unfold after, waking_transfer; simpl; exact H | ].
  split.
  - intros k st o p H. unfold after, waking_transfer. simpl. exact H.
  - intros H. specialize (H empty_kernel (fun _ => false) (offer_into 0) 0).
    discriminate H.
Qed.

(* An endpoint that never rendezvouses at all: it satisfies every other
   clause, so the refusal discipline alone does not make a transfer, which
   is why R-07-029a's rendezvous half is stated in its own right. *)
Definition deaf_transfer : Transfer := fun k _ _ => pair k Refused.

Theorem the_deaf_transfer_never_rendezvouses :
  RefusesWithNoReadyPeer deaf_transfer
  /\ ~ RendezvousWithAReadyPeer deaf_transfer
  /\ ParksNothing deaf_transfer
  /\ LeavesNoPartitionWaiting deaf_transfer
  /\ ResumesNoPartition deaf_transfer.
Proof.
  split; [ intros k st o H; reflexivity | ].
  split.
  - intros H. specialize (H empty_kernel (fun _ => true) (offer_into 0) eq_refl).
    discriminate H.
  - split; [ intros k st o H; exact H | ].
    split; [ intros k st o p H; exact H | intros k st o p; reflexivity ].
Qed.

(* And the first member of the optimistic family read as a construction
   rather than as a family index: it crosses to a peer that is not ready,
   which is the one thing R-07-029a's first sentence forbids. *)
Theorem the_optimistic_transfer_crosses_to_an_unready_peer :
  ~ RefusesWithNoReadyPeer (optimistic_at 1)
  /\ RendezvousWithAReadyPeer (optimistic_at 1)
  /\ ParksNothing (optimistic_at 1)
  /\ ResumesNoPartition (optimistic_at 1).
Proof.
  split.
  - intros H. specialize (H empty_kernel (fun _ => false) (offer_into 0) eq_refl).
    discriminate H.
  - split.
    + intros k st o H. unfold said, optimistic_at. simpl. rewrite H. reflexivity.
    + split; [ intros k st o H; exact H | intros k st o p; reflexivity ].
Qed.

(* R-07-029a's typed refusal against a status word: a result that carries
   the message buffer whatever it reports, so a caller that ignores the
   flag reads a message that did not cross. It reports the refusal
   correctly, which is what makes the medium and not the flag the defect
   (reading 6). *)
Record StatusResult : Type := {
  status_ok : bool;
  status_buffer : Message
}.

Definition status_delivered (r : StatusResult) : option Message :=
  Some r.(status_buffer).

Definition status_run (st : Readiness) (o : Offer) : StatusResult :=
  {| status_ok := st o.(offer_at); status_buffer := o.(offer_carries) |}.

Theorem the_status_word_carries_what_did_not_cross :
  ~ CarriesNothingWhereNothingCrossed StatusResult status_delivered status_run.
Proof.
  intros H. specialize (H (fun _ => false) (offer_into 0) eq_refl).
  discriminate H.
Qed.

Example the_status_word_reports_the_refusal_correctly :
  status_ok (status_run (fun _ => false) (offer_into 0)) = false
  /\ status_ok (status_run (fun _ => true) (offer_into 0)) = true :=
  conj eq_refl eq_refl.

(* And the specification on the same two readiness states, so the
   obligation above is not proved from a premise nothing satisfies: it
   delivers on one and delivers nothing on the other. *)
Example the_specification_delivers_on_one_state_and_not_the_other :
  delivered (spec_run (fun _ => true) (offer_into 0)) = Some probe_message
  /\ delivered (spec_run (fun _ => false) (offer_into 0)) = None :=
  conj eq_refl eq_refl.

(* A refusal that costs more than the invocation it belongs to, which is
   R-07-029a's Fail-closed clause read backwards: the caller's refusal
   spends the core's slot instead of its own invocation. It is bounded for
   the yield, so what refutes it is the send. *)
Definition retrying_refusal (i : Invocation) : nat :=
  match i with
  | Send => 9
  | Receive => 9
  | PollSiteYield => 1
  | GrantRedeem => 2
  | Revoke => 2
  end.

Theorem the_retrying_refusal_is_refuted :
  ~ RefusalCostsItsOwnInvocation demo retrying_refusal.
Proof. intros H. specialize (H Send). discriminate H. Qed.

Example the_retrying_refusal_is_still_bounded_for_the_yield :
  Nat.leb (retrying_refusal PollSiteYield) (demo.(invocation_cost) PollSiteYield)
  = true
  /\ Nat.leb (retrying_refusal Send) (demo.(invocation_cost) Send) = false :=
  conj eq_refl eq_refl.

Example the_retrying_refusal_costs :
  map_over retrying_refusal all_invocations
  = cons 9 (cons 9 (cons 1 (cons 2 (cons 2 nil))))
  /\ map_over (fun i => Nat.leb (retrying_refusal i) (demo.(invocation_cost) i))
              all_invocations
  = cons false (cons false (cons true (cons true (cons true nil)))) :=
  conj eq_refl eq_refl.

(* =========================================================================
   Refutation witnesses over the capability transfer (R-07-029, R-04-008).
   ========================================================================= *)

(* A grant that hands the receiver a capability the message does not name,
   on the ground that a server needs to be reachable. It grants everything
   named, so what refutes it is the mint. *)
Definition ambient_grant : Grant := fun msg h c =>
  orb (orb (h c) (carried msg c)) (Nat.eqb c 0).

Theorem the_ambient_grant_mints :
  ~ MintsNothing ambient_grant /\ GrantsEverythingNamed ambient_grant.
Proof.
  split.
  - intros H.
    specialize (H {| msg_regs := nil; msg_caps := nil |} (fun _ => false) 0 eq_refl).
    discriminate H.
  - intros msg h c H. unfold ambient_grant. rewrite H.
    destruct (h c); reflexivity.
Qed.

(* A grant that hands over nothing: it mints nothing and transfers only
   what is named, and it never transfers what is named, so the three
   clauses are not one clause stated three ways. *)
Definition stingy_grant : Grant := fun _ h c => h c.

Theorem the_stingy_grant_transfers_nothing :
  MintsNothing stingy_grant
  /\ ~ GrantsEverythingNamed stingy_grant
  /\ TransfersOnlyWhatIsNamed stingy_grant.
Proof.
  split.
  - intros msg h c H. unfold stingy_grant in H. rewrite H. reflexivity.
  - split.
    + intros H.
      specialize (H {| msg_regs := nil; msg_caps := cons 7 nil |}
                    (fun _ => false) 7 eq_refl).
      discriminate H.
    + intros msg h c H. reflexivity.
Qed.

(* A grant that replaces the receiver's holdings with the message's rather
   than adding to them: it mints nothing and grants everything named, and
   it moves a slot the message does not name. That is what shows the third
   clause is strictly stronger than the first rather than the same one. *)
Definition replacing_grant : Grant := fun msg _ c => carried msg c.

Theorem the_replacing_grant_moves_what_is_not_named :
  MintsNothing replacing_grant
  /\ GrantsEverythingNamed replacing_grant
  /\ ~ TransfersOnlyWhatIsNamed replacing_grant.
Proof.
  split.
  - intros msg h c H. unfold replacing_grant in H. rewrite H.
    destruct (h c); reflexivity.
  - split.
    + intros msg h c H. exact H.
    + intros H.
      specialize (H {| msg_regs := nil; msg_caps := nil |} (fun _ => true) 7
                    eq_refl).
      discriminate H.
Qed.

(* =========================================================================
   Refutation witnesses over the medium (R-07-029, R-07-031).
   ========================================================================= *)

Fixpoint bulk (n : nat) : list nat :=
  match n with 0 => nil | S k => cons k (bulk k) end.

Lemma bulk_length : forall n : nat, count_of (bulk n) = n.
Proof.
  intros n. induction n as [ | k IH ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

Definition bulk_message (n : nat) : Message :=
  {| msg_regs := bulk n; msg_caps := nil |}.

(* S39 (R-07-029, R-07-031): the kernel carries control and never bulk
   data, stated of an arbitrary machine and an arbitrary payload size
   rather than of one witness. High-throughput I/O rides a user-level ring
   because this bound refuses it here. *)
Theorem no_bulk_payload_crosses_the_kernel :
  forall (m : Machine) (n : nat),
    Nat.leb n m.(word_count) = false -> message_ok m (bulk_message n) = false.
Proof.
  intros m n H. unfold message_ok, bulk_message. simpl.
  rewrite bulk_length. rewrite H. reflexivity.
Qed.

(* S39a: the same bound read as R-07-029's own sentence, that the kernel
   carries control and never bulk data. The predicate is proved of a
   message inside the budget and refuted of one past it, so it decides
   rather than restating `message_ok`. *)
Theorem the_specification_medium_carries_no_bulk_data :
  CarriesNoBulkData demo probe_message.
Proof. reflexivity. Qed.

Theorem a_payload_past_the_budget_carries_bulk_data :
  ~ CarriesNoBulkData demo (bulk_message 5).
Proof. intros H. discriminate H. Qed.

Example the_medium_admits_a_message_at_the_budget_and_refuses_one_past_it :
  message_ok demo (bulk_message 4) = true
  /\ message_ok demo (bulk_message 5) = false
  /\ message_ok demo probe_message = true :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_slot_budget_binds_beside_the_register_budget :
  message_ok demo {| msg_regs := nil; msg_caps := cons 1 (cons 2 nil) |} = true
  /\ message_ok demo {| msg_regs := nil;
                        msg_caps := cons 1 (cons 2 (cons 3 nil)) |} = false :=
  conj eq_refl eq_refl.

(* =========================================================================
   Refutation witnesses over the notification path (R-12-096, R-08-032,
   R-07-039).
   ========================================================================= *)

(* A notification counter, which R-12-096 says does not exist: signalling
   twice leaves a different state from signalling once, so a hint stops
   being coalescible. It has a defined reset, so what refutes it is the
   counter and not the reset. *)
Definition counting_armed (n : nat) : bool := Nat.ltb 0 n.

Definition counting_signal (n : nat) : nat := S n.

Definition counting_reset (n : nat) : nat := 0.

Theorem the_counting_signal_does_not_coalesce :
  ~ Coalescing nat counting_signal
  /\ ResetIsDefined nat counting_armed counting_reset.
Proof.
  split.
  - intros H. specialize (H 0). discriminate H.
  - intros w. reflexivity.
Qed.

Example the_counter_separates_two_signals_from_one :
  counting_signal (counting_signal 0) = 2 /\ counting_signal 0 = 1
  /\ spec_signal (spec_signal false) = spec_signal false :=
  conj eq_refl (conj eq_refl eq_refl).

(* The counting word's own armed reading, so that *armed* means the same
   thing on both carriers: any count above zero is armed, and the reset
   lands on the one value that is not. *)
Example the_counting_word_is_armed_above_zero :
  map_over counting_armed (upto 4)
  = cons false (cons true (cons true (cons true nil)))
  /\ counting_reset 3 = 0 := conj eq_refl eq_refl.

(* And the other side of the separation: a reset that leaves the word as it
   found it coalesces perfectly and has no defined reset at all, so the two
   obligations R-12-096 states of the word are separate. *)
Definition identity_reset (b : bool) : bool := b.

Theorem the_identity_reset_is_undefined :
  Coalescing bool spec_signal /\ ~ ResetIsDefined bool armed_of identity_reset.
Proof.
  split.
  - intros w. reflexivity.
  - intros H. specialize (H true). discriminate H.
Qed.

(* The lost wakeup: a consumer that decides on its pre-arming read alone
   and never re-reads the producer index. It never yields over work its
   drain already saw, which is what makes the missing recheck and not the
   decision rule the defect. *)
Definition naive_decide : Decider := fun before _ => negb (has_work before).

Theorem the_naive_decider_loses_a_wakeup :
  ~ RechecksAfterArming naive_decide
  /\ YieldsOnlyOnAnEmptyDrain naive_decide.
Proof.
  split.
  - intros H.
    specialize (H {| produced := 2; consumed := 2 |}
                  {| produced := 3; consumed := 2 |} eq_refl).
    discriminate H.
  - intros b n H. unfold naive_decide. rewrite H. reflexivity.
Qed.

(* And a consumer that reads only after arming yields over work its own
   drain already saw, which is the other clause broken alone. *)
Definition post_only_decide : Decider := fun _ now => negb (has_work now).

Theorem the_post_only_decider_yields_over_a_drained_ring :
  RechecksAfterArming post_only_decide
  /\ ~ YieldsOnlyOnAnEmptyDrain post_only_decide.
Proof.
  split.
  - intros b n H. unfold post_only_decide. rewrite H. reflexivity.
  - intros H.
    specialize (H {| produced := 3; consumed := 2 |}
                  {| produced := 2; consumed := 2 |} eq_refl).
    discriminate H.
Qed.

Example the_decider_truth_table :
  spec_decide {| produced := 2; consumed := 2 |} {| produced := 2; consumed := 2 |}
    = true
  /\ spec_decide {| produced := 2; consumed := 2 |}
                 {| produced := 3; consumed := 2 |} = false
  /\ spec_decide {| produced := 3; consumed := 2 |}
                 {| produced := 2; consumed := 2 |} = false
  /\ spec_decide {| produced := 3; consumed := 2 |}
                 {| produced := 3; consumed := 2 |} = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_ring_indices_are_the_source_of_truth :
  has_work {| produced := 2; consumed := 2 |} = false
  /\ has_work {| produced := 3; consumed := 2 |} = true
  /\ has_work {| produced := 2; consumed := 3 |} = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   Refutation witnesses over the rotation (R-07-037b, R-07-037c,
   R-07-037d, R-07-044).
   ========================================================================= *)

(* The rotation that performs no pending swap, written so that the two arms
   of R-07-044's disjunction are what it reads rather than one of them. On
   the swap arm there is one live file and it still holds the predecessor's
   bits, so two rotations reaching one successor from different predecessors
   deliver different pending state to the same member. On the static arm the
   file is partitioned by member and holding it still is what identity
   partitioning means, so the same construction hands each member its own
   bits and coincides with the specification. One construction, two arms,
   opposite verdicts, and neither verdict is reached through a hypothesis
   nothing satisfies: that is the disjunction being real. What the static
   arm's verdict is not is a statement that the arm's file is unshared, and
   the theorem below says so at its own site. *)
Definition unswapped_delivery (m : Machine) : Delivery :=
  fun pred succ b =>
    if m.(pending_arm) then m.(pending) pred b else m.(pending) succ b.

Theorem the_unswapped_delivery_is_refuted_on_the_swap_arm :
  ~ SeesItsOwnPendingOnly demo (unswapped_delivery demo)
  /\ ~ SwapsWhereASwapExists demo (unswapped_delivery demo)
  /\ ~ DoesNotVaryWithThePredecessor (unswapped_delivery demo).
Proof.
  split; [ intros H; specialize (H 0 1 1); discriminate H | ].
  split; [ intros H; specialize (H eq_refl 0 1 1); discriminate H | ].
  intros H. specialize (H 0 1 1 1). discriminate H.
Qed.

(* And admitted on the other arm, by the observable rather than by an empty
   hypothesis. **What it establishes there, exactly.** On the static arm
   `unswapped_delivery m` reduces to `m.(pending) succ b`, which is
   `spec_delivery m`, so the construction and the specification coincide and
   the admission is that coincidence: performing no swap is not a defect
   where no swap exists to omit. That is the verdict the disjunction needs
   and it is not vacuous in R-05-165's first mode, the statement carrying no
   hypothesis at all.

   **What it does not establish, stated because the coincidence invites the
   stronger reading.** It is not a statement that the static arm's file is
   unshared, and no instance of it could be:
   `the_static_arm_admits_the_construction_of_every_machine` below proves it
   holds of every machine on that arm, a sharing one included, because
   `SeesItsOwnPendingOnly` quantifies `pending` away and so cannot express
   sharing. R-07-044's *hidden or shared* is refuted on the carrier that can
   express it, and arm-independently: `sharing_step` against
   `LeavesEveryOtherMembersBitsAlone` below. *)
Theorem the_unswapped_delivery_is_admitted_on_the_static_arm :
  SeesItsOwnPendingOnly demo_static (unswapped_delivery demo_static)
  /\ DoesNotVaryWithThePredecessor (unswapped_delivery demo_static).
Proof.
  split; [ intros p s b; reflexivity | intros p q s b; reflexivity ].
Qed.

(* The reach of that admission, proved rather than described: it is the whole
   static arm and not this machine. A theorem shipped without this beside it
   would read as a property of `demo_static` that some other static machine
   might fail, and none can. *)
Theorem the_static_arm_admits_the_construction_of_every_machine :
  forall m : Machine, m.(pending_arm) = false ->
    SeesItsOwnPendingOnly m (unswapped_delivery m)
    /\ DoesNotVaryWithThePredecessor (unswapped_delivery m).
Proof.
  intros m H. split.
  - intros p s b. unfold unswapped_delivery. rewrite H. reflexivity.
  - intros p q s b. unfold unswapped_delivery. rewrite H. reflexivity.
Qed.

(* And the two coincide on that arm as functions, which is the same fact read
   from the other side and is what makes the admission uninformative about
   sharing. *)
Theorem the_construction_is_the_specification_on_the_static_arm :
  forall m : Machine, m.(pending_arm) = false ->
    forall p s b : nat, unswapped_delivery m p s b = spec_delivery m p s b.
Proof.
  intros m H p s b. unfold unswapped_delivery, spec_delivery.
  rewrite H. reflexivity.
Qed.

(* Why the observable above carries no hypothesis, stated rather than left to
   be discovered: R-07-037c scopes its verb to the arm where a swap exists,
   so on the other arm the guarded clause is discharged by every delivery
   whatever. That is R-05-165's first mode exhibited on purpose, and a file
   shipping only the guarded clause would be shipping an empty statement over
   half of R-07-044's disjunction. *)
Theorem the_guarded_clause_is_empty_on_the_static_arm :
  forall d : Delivery, SwapsWhereASwapExists demo_static d.
Proof. intros d H. discriminate H. Qed.

(* R-07-037c's own accept clause as a computation, and the arm as a column
   beside it: the same successor reached from two different predecessors sees
   two different files on the swap arm and one file on the static arm. *)
Example the_unswapped_rotation_is_predecessor_dependent :
  unswapped_delivery demo 0 2 0 = true
  /\ unswapped_delivery demo 1 2 0 = false
  /\ unswapped_delivery demo_static 0 2 0 = false
  /\ unswapped_delivery demo_static 1 2 0 = false
  /\ unswapped_delivery demo 1 0 0 = false
  /\ unswapped_delivery demo_static 1 0 0 = true
  /\ spec_delivery demo 0 2 0 = false
  /\ spec_delivery demo 1 2 0 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl)))))).

(* A rotation that hands every member the group head's pending bits: it does
   not vary with the predecessor, and it is still not the member's own. That
   is the one direction in which the two clauses come apart, the other being
   closed by the entailment above. *)
Definition head_member_delivery (m : Machine) : Delivery :=
  fun _ succ b => m.(pending) (head_or m.(group_members) succ) b.

Theorem the_head_member_delivery_separates_the_two_clauses :
  ~ SeesItsOwnPendingOnly demo (head_member_delivery demo)
  /\ DoesNotVaryWithThePredecessor (head_member_delivery demo).
Proof.
  split.
  - intros H. specialize (H 0 1 1). discriminate H.
  - intros p q s b. reflexivity.
Qed.

(* R-07-044's *hidden or shared* at the level of state: one file the whole
   group reads, so a member's reaction overwrites every sibling's bits. It
   hands the dispatched member exactly what the specification's step hands
   it, which is what makes the sharing and not the reaction the defect. *)
Definition sharing_step (react : nat -> nat -> bool) : Step :=
  fun _ _ _ u b => react u b.

Theorem the_sharing_step_overwrites_a_sibling :
  ~ LeavesEveryOtherMembersBitsAlone (sharing_step (fun _ _ => false)).
Proof.
  intros H. specialize (H 0 1 2 0 (fun _ _ => true) eq_refl). discriminate H.
Qed.

Example the_sharing_step_agrees_on_the_member_it_dispatches :
  sharing_step (fun _ _ => false) 0 1 (fun _ _ => true) 1 0
  = step_of (fun _ _ => false) 0 1 (fun _ _ => true) 1 0 := eq_refl.

(* And the construction R-07-037c's second conjunct is about by name: a step
   that clears the predecessor's file as it leaves, so the bits a member
   leaves are not the bits it finds at its next dispatch. It delivers the
   dispatched member its own reaction, so what refutes it is the restoration
   and not the delivery. *)
Definition clearing_step (react : nat -> nat -> bool) : Step :=
  fun p s f u b =>
    if Nat.eqb u s then react u b else if Nat.eqb u p then false else f u b.

Theorem the_clearing_step_loses_what_a_member_left :
  ~ LeavesEveryOtherMembersBitsAlone (clearing_step (fun _ _ => false)).
Proof.
  intros H. specialize (H 0 1 0 0 (fun _ _ => true) eq_refl). discriminate H.
Qed.

Example the_round_trip_restores_under_one_step_and_not_the_other :
  run_dispatches (step_of (fun _ _ => false)) (fun _ _ => true) 0
                 (cons 1 (cons 2 nil)) 0 0 = true
  /\ run_dispatches (clearing_step (fun _ _ => false)) (fun _ _ => true) 0
                    (cons 1 (cons 2 nil)) 0 0 = false
  /\ run_dispatches (sharing_step (fun _ _ => false)) (fun _ _ => true) 0
                    (cons 1 (cons 2 nil)) 0 0 = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* A rotation that skips a member with nothing to do, which is the runtime
   decision R-07-037b's *no runtime decision* refuses. It agrees with the
   composition-fixed order wherever nothing is observed, so what refutes it
   is the read. *)
Definition work_stealing_advance (m : Machine) : Advancer := fun obs u =>
  if Nat.ltb 0 (obs u) then advance m (advance m u) else advance m u.

Theorem the_work_stealing_rotation_is_refuted :
  ~ IsCompositionFixedRotation (work_stealing_advance demo).
Proof.
  intros H. specialize (H (fun _ => 0) (fun _ => 1) 0). discriminate H.
Qed.

Example the_work_stealing_rotation_agrees_where_nothing_is_observed :
  work_stealing_advance demo (fun _ => 0) 0 = advance demo 0
  /\ work_stealing_advance demo (fun _ => 1) 0 = 2 := conj eq_refl eq_refl.

(* R-07-037d as a constraint on the composer: a group whose members do not
   share a label is not a candidate at any cadence, because the rotation's
   omission of the eager zeroize would then be an observation across a
   label boundary. *)
Definition mixed_group : list nat := cons 0 (cons 3 nil).

Theorem the_mixed_label_group_is_refused :
  ~ ResidueIsInDomain demo mixed_group.
Proof. intros H. discriminate H. Qed.

Theorem the_composed_group_is_admissible :
  ResidueIsInDomain demo demo.(group_members).
Proof. reflexivity. Qed.

Example the_mixed_group_names_a_partition_of_another_label :
  mixed_group = cons 0 (cons 3 nil)
  /\ map_over demo.(label) mixed_group = cons 0 (cons 1 nil) :=
  conj eq_refl eq_refl.

Example the_mixed_group_crosses_a_label_boundary :
  demo.(label) 0 = 0 /\ demo.(label) 3 = 1
  /\ SameLabelGroup demo demo.(group_members) = true
  /\ SameLabelGroup demo mixed_group = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* R-07-037d's third accept clause: a member that infers which sibling left
   the residue. It is refused, and the residue trace below is why it would
   also be wrong: at a class the predecessor did not touch, the value
   standing there is an earlier member's. *)
Definition predecessor_inference : Inference := fun s => Some s.

Theorem the_predecessor_inference_is_refuted :
  ~ ClaimsNoParticularSibling predecessor_inference.
Proof. intros H. specialize (H 0). discriminate H. Qed.

Definition base_residue : Residue := fun _ => 0.

Definition touches_the_first_class (c : nat) : bool := Nat.eqb c 0.

Definition after_the_second_member : Residue :=
  leaves 1 touches_the_first_class base_residue.

Example the_residue_is_not_the_predecessors_at_an_untouched_class :
  after_the_second_member 0 = 1
  /\ after_the_second_member 1 = 0
  /\ after_the_second_member 2 = 0 := conj eq_refl (conj eq_refl eq_refl).

(* And the twin: the inference is right about the class the predecessor did
   touch, so what refutes it is the untouched class rather than the
   rotation order, which is composition-fixed and known. *)
Example the_inference_is_right_where_the_predecessor_wrote :
  Nat.eqb (after_the_second_member 0) 1 = true
  /\ Nat.eqb (after_the_second_member 1) 1 = false := conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared
   set R-05-164 currently makes empty, so "Closed under the global context"
   is that emptiness checked mechanically.
   ------------------------------------------------------------------------- *)

Print Assumptions all_of.
Print Assumptions any_of.
Print Assumptions count_of.
Print Assumptions map_over.
Print Assumptions filter_of.
Print Assumptions head_or.
Print Assumptions upto.
Print Assumptions before_last.
Print Assumptions only_if.
Print Assumptions same_bool.
Print Assumptions halve.
Print Assumptions oddb.
Print Assumptions bit_at.
Print Assumptions two_pow.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions only_if_elim.
Print Assumptions nat_eqb_refl.
Print Assumptions nat_eqb_true.
Print Assumptions nat_leb_refl.
Print Assumptions nat_leb_succ.
Print Assumptions all_of_app.
Print Assumptions all_of_app_intro.
Print Assumptions all_of_map.
Print Assumptions count_of_app.
Print Assumptions count_of_map.
Print Assumptions leb_split.
Print Assumptions all_of_upto.
Print Assumptions the_empty_conjunction_holds.
Print Assumptions the_empty_disjunction_fails.
Print Assumptions nothing_has_length_zero.
Print Assumptions the_head_of_nothing_is_the_fallback.
Print Assumptions before_last_of_nothing.
Print Assumptions the_index_set_of_three.
Print Assumptions only_if_is_implication.
Print Assumptions same_bool_is_agreement.
Print Assumptions halving_and_parity.
Print Assumptions the_bits_of_a_mask.
Print Assumptions the_powers_of_two.
Print Assumptions all_invocations.
Print Assumptions all_groups.
Print Assumptions all_nameable.
Print Assumptions all_lifecycles.
Print Assumptions numbered_acts.
Print Assumptions unnumbered_acts.
Print Assumptions deleted_acts.
Print Assumptions all_acts.
Print Assumptions there_are_five_invocations.
Print Assumptions there_are_four_abi_groups.
Print Assumptions five_sits_under_a_dozen_with_margin.
Print Assumptions inv_eqb.
Print Assumptions inv_eqb_refl.
Print Assumptions inv_eqb_true.
Print Assumptions group_eqb.
Print Assumptions nameable_eqb.
Print Assumptions lifecycle_eqb.
Print Assumptions act_eqb.
Print Assumptions the_five_equalities_are_reflexive.
Print Assumptions the_five_equalities_separate_every_other_pair.
Print Assumptions group_of.
Print Assumptions members_of.
Print Assumptions the_group_census.
Print Assumptions the_notification_group_is_empty.
Print Assumptions the_endpoint_group_is_the_send_and_the_receive.
Print Assumptions the_four_groups_cover_the_five_members.
Print Assumptions Grouping.
Print Assumptions census.
Print Assumptions TheNotificationGroupIsEmpty.
Print Assumptions AssignsTheGroupsTheEntryAssigns.
Print Assumptions the_specification_grouping_leaves_the_notification_group_empty.
Print Assumptions the_specification_grouping_makes_the_entrys_assignment.
Print Assumptions the_entrys_assignment_empties_the_notification_group.
Print Assumptions act_of.
Print Assumptions numbered_act.
Print Assumptions is_the_act_of_an_invocation.
Print Assumptions deleted_act.
Print Assumptions the_numbered_acts_are_exactly_the_five_invocations.
Print Assumptions the_criterion_and_the_specification_numbering_agree_everywhere.
Print Assumptions the_deleted_acts_take_no_number.
Print Assumptions TrapSurface.
Print Assumptions AdmissibleTrapSurface.
Print Assumptions traps_act.
Print Assumptions traps_with_the_schedule_transitions.
Print Assumptions the_files_own_trap_surface_is_admissible.
Print Assumptions the_syscall_carried_trap_surface_is_admissible.
Print Assumptions the_polled_yield_surface.
Print Assumptions the_polled_yield_surface_is_inadmissible.
Print Assumptions the_trapping_signal_surface.
Print Assumptions the_trapping_signal_surface_is_inadmissible.
Print Assumptions the_trapping_opcode_surface.
Print Assumptions the_trapping_opcode_surface_is_inadmissible.
Print Assumptions the_refused_surfaces_each_move_one_act.
Print Assumptions the_two_admissible_surfaces_differ_on_the_schedule_transitions_alone.
Print Assumptions the_trap_surface_is_six_or_nine.
Print Assumptions the_trap_cut_over_collects_by_the_exception_surface.
Print Assumptions the_syscall_carried_cut_over_collects_by_four.
Print Assumptions nothing_the_abi_numbers_fails_to_trap.
Print Assumptions every_admissible_trap_surface_carries_the_exception.
Print Assumptions no_admissible_trap_surface_traps_a_notification_half.
Print Assumptions the_grant_mint_neither_traps_nor_takes_a_number.
Print Assumptions schedule_transitions.
Print Assumptions the_schedule_transitions_take_no_number_on_either_surface.
Print Assumptions the_deleted_surfaces_take_no_number.
Print Assumptions neither_notification_half_traps_or_takes_a_number.
Print Assumptions is_object.
Print Assumptions is_table.
Print Assumptions object_classes.
Print Assumptions kernel_tables.
Print Assumptions the_inventory_is_three_classes_and_two_tables.
Print Assumptions a_table_is_not_an_object_and_a_reply_object_is_neither.
Print Assumptions occurrences_nm.
Print Assumptions inventory_ok.
Print Assumptions InventoryIsClosedAtThree.
Print Assumptions inventory_ok_sound.
Print Assumptions inventory_ok_complete.
Print Assumptions spec_inventory.
Print Assumptions the_specification_inventory_is_closed.
Print Assumptions Designation.
Print Assumptions DesignatesOnlyObjects.
Print Assumptions spec_designation.
Print Assumptions the_specification_designation_names_only_objects.
Print Assumptions Lifecycles.
Print Assumptions spec_lifecycles.
Print Assumptions revoke_only_lifecycle.
Print Assumptions NoTableHasALifecycle.
Print Assumptions DistinguishesTheClassesFromTheTables.
Print Assumptions the_specification_gives_no_table_a_lifecycle.
Print Assumptions the_specification_distinguishes_the_classes_from_the_tables.
Print Assumptions the_revoke_only_lifecycle_discharges_both.
Print Assumptions the_two_lifecycle_maps_disagree_where_no_obligation_reads.
Print Assumptions SpendsNoObjectClass.
Print Assumptions SpendsNoObjectType.
Print Assumptions MintsNothingAtRuntime.
Print Assumptions RepliesByAnAdmittedInvocation.
Print Assumptions badge_return.
Print Assumptions the_badge_return_path_discharges_all_four.
Print Assumptions pos_inv.
Print Assumptions nth_inv.
Print Assumptions occurrences_inv.
Print Assumptions spec_surface.
Print Assumptions frozen_surface.
Print Assumptions IsTheFrozenSurface.
Print Assumptions frozen_surface_sound.
Print Assumptions frozen_surface_complete.
Print Assumptions frozen_surface_refusal.
Print Assumptions the_specification_surface_is_the_frozen_one.
Print Assumptions index_in.
Print Assumptions index_of.
Print Assumptions the_invocation_indices.
Print Assumptions a_number_past_the_surface_dispatches_to_nothing.
Print Assumptions pos_inv_nth.
Print Assumptions the_number_determines_the_invocation.
Print Assumptions pos_inv_of_an_occurrence.
Print Assumptions every_frozen_surface_numbers_every_member.
Print Assumptions Observation.
Print Assumptions Dispatcher.
Print Assumptions dispatch_of.
Print Assumptions spec_dispatch.
Print Assumptions DispatchesByTheNumberAlone.
Print Assumptions every_surface_dispatches_by_the_number_alone.
Print Assumptions the_specification_dispatches_by_the_number_alone.
Print Assumptions drop_at_inv.
Print Assumptions insert_at_inv.
Print Assumptions swap_at_inv.
Print Assumptions deletions_inv.
Print Assumptions insertions_inv.
Print Assumptions transpositions_inv.
Print Assumptions refused_weakenings.
Print Assumptions occurrences_of_insert.
Print Assumptions occurrences_of_drop.
Print Assumptions occurrences_of_swap.
Print Assumptions no_transposition_leaves_the_frozen_surface.
Print Assumptions no_insertion_of_a_present_member_is_the_frozen_surface.
Print Assumptions no_transposition_leaves_the_frozen_surface_obligation.
Print Assumptions no_insertion_of_a_present_member_meets_the_obligation.
Print Assumptions a_transposed_surface_assigns_different_numbers.
Print Assumptions demo_cost.
Print Assumptions demo_refusal.
Print Assumptions demo.
Print Assumptions demo_static.
Print Assumptions the_demo_machine_declares.
Print Assumptions the_demo_costs.
Print Assumptions the_demo_labels.
Print Assumptions the_demo_interrupt_file.
Print Assumptions the_two_pending_arms_differ.
Print Assumptions the_static_arm_moves_nothing_but_the_arm.
Print Assumptions the_static_arm_declares_the_same_labels_and_costs.
Print Assumptions message_ok.
Print Assumptions CarriesNoBulkData.
Print Assumptions Badge.
Print Assumptions badge_ok.
Print Assumptions badges.
Print Assumptions every_generated_badge_has_the_declared_width.
Print Assumptions the_badge_space_is_two_to_the_declared_width.
Print Assumptions Readiness.
Print Assumptions delivered.
Print Assumptions is_refused.
Print Assumptions empty_kernel.
Print Assumptions the_probe_kernel_holds_nothing.
Print Assumptions Transfer.
Print Assumptions after.
Print Assumptions said.
Print Assumptions spec_transfer.
Print Assumptions RefusesWithNoReadyPeer.
Print Assumptions RendezvousWithAReadyPeer.
Print Assumptions ParksNothing.
Print Assumptions LeavesNoPartitionWaiting.
Print Assumptions ResumesNoPartition.
Print Assumptions the_specification_refuses_with_no_ready_peer.
Print Assumptions the_specification_rendezvous_with_a_ready_peer.
Print Assumptions the_specification_parks_nothing.
Print Assumptions the_specification_leaves_no_partition_waiting.
Print Assumptions the_specification_resumes_no_partition.
Print Assumptions the_outcome_is_the_readiness_bit.
Print Assumptions CarriesNothingWhereNothingCrossed.
Print Assumptions spec_run.
Print Assumptions the_specification_carries_nothing_where_nothing_crossed.
Print Assumptions RefusalCostsItsOwnInvocation.
Print Assumptions the_specification_refusal_costs_its_own_invocation.
Print Assumptions boundary_refusal.
Print Assumptions the_refusal_that_spends_its_whole_invocation_is_admitted.
Print Assumptions the_boundary_refusal_spends_exactly_its_invocation.
Print Assumptions run_offers.
Print Assumptions no_sequence_of_re_offers_parks_anything.
Print Assumptions outcomes_of.
Print Assumptions an_unready_peer_refuses_every_offer_in_a_sequence.
Print Assumptions Holdings.
Print Assumptions carried.
Print Assumptions Grant.
Print Assumptions spec_grant.
Print Assumptions MintsNothing.
Print Assumptions GrantsEverythingNamed.
Print Assumptions TransfersOnlyWhatIsNamed.
Print Assumptions the_specification_grant_mints_nothing.
Print Assumptions the_specification_grant_grants_everything_named.
Print Assumptions the_specification_grant_transfers_only_what_is_named.
Print Assumptions all_halves.
Print Assumptions medium_of.
Print Assumptions act_of_half.
Print Assumptions both_halves_are_memory_operations.
Print Assumptions Coalescing.
Print Assumptions ResetIsDefined.
Print Assumptions armed_of.
Print Assumptions spec_signal.
Print Assumptions spec_reset.
Print Assumptions the_specification_signal_coalesces.
Print Assumptions the_specification_reset_is_defined.
Print Assumptions the_word_is_binary.
Print Assumptions has_work.
Print Assumptions Decider.
Print Assumptions spec_decide.
Print Assumptions RechecksAfterArming.
Print Assumptions YieldsOnlyOnAnEmptyDrain.
Print Assumptions the_specification_decider_rechecks_after_arming.
Print Assumptions the_specification_decider_yields_only_on_an_empty_drain.
Print Assumptions sleep_invocation.
Print Assumptions the_sleep_the_consumer_reaches_is_the_poll_site_yield.
Print Assumptions rotate_from.
Print Assumptions advance.
Print Assumptions Advancer.
Print Assumptions spec_advance.
Print Assumptions IsCompositionFixedRotation.
Print Assumptions the_specification_rotation_is_composition_fixed.
Print Assumptions the_rotation_wraps_over_the_group.
Print Assumptions Delivery.
Print Assumptions spec_delivery.
Print Assumptions SeesItsOwnPendingOnly.
Print Assumptions SwapsWhereASwapExists.
Print Assumptions DoesNotVaryWithThePredecessor.
Print Assumptions the_specification_delivery_sees_its_own_pending_only.
Print Assumptions the_specification_delivery_swaps_where_a_swap_exists.
Print Assumptions the_specification_delivery_does_not_vary_with_the_predecessor.
Print Assumptions seeing_its_own_pending_entails_predecessor_independence.
Print Assumptions Files.
Print Assumptions Step.
Print Assumptions step_of.
Print Assumptions LeavesEveryOtherMembersBitsAlone.
Print Assumptions run_dispatches.
Print Assumptions the_specification_step_leaves_every_other_members_bits_alone.
Print Assumptions the_bits_a_member_leaves_are_restored_at_its_next_dispatch.
Print Assumptions SameLabelGroup.
Print Assumptions ResidueIsInDomain.
Print Assumptions all_of_member.
Print Assumptions an_admissible_group_keeps_the_residue_in_domain.
Print Assumptions Inference.
Print Assumptions spec_inference.
Print Assumptions ClaimsNoParticularSibling.
Print Assumptions the_specification_claims_no_particular_sibling.
Print Assumptions Residue.
Print Assumptions leaves.
Print Assumptions admits_of_mask.
Print Assumptions surface_mask_ok.
Print Assumptions all_masks.
Print Assumptions there_are_thirty_two_boolean_enumerations.
Print Assumptions only_the_full_enumeration_is_the_frozen_surface.
Print Assumptions no_proper_boolean_enumeration_is_the_frozen_surface.
Print Assumptions the_full_enumeration_admits_every_member.
Print Assumptions the_deletions_of_the_surface.
Print Assumptions the_generated_weakening_family_size.
Print Assumptions every_generated_weakening_is_refused.
Print Assumptions every_deletion_leaves_a_member_unnumbered.
Print Assumptions every_insertion_numbers_a_member_twice.
Print Assumptions every_transposition_is_still_a_frozen_surface.
Print Assumptions the_transpositions_of_the_surface.
Print Assumptions no_deletion_is_the_frozen_surface.
Print Assumptions no_insertion_is_the_frozen_surface.
Print Assumptions every_transposition_index_is_still_the_frozen_surface.
Print Assumptions no_deletion_meets_the_frozen_surface_obligation.
Print Assumptions no_insertion_meets_the_frozen_surface_obligation.
Print Assumptions every_transposition_meets_the_frozen_surface_obligation.
Print Assumptions probe_message.
Print Assumptions probe_badge.
Print Assumptions offer_into.
Print Assumptions the_probe_message_and_the_probe_badge.
Print Assumptions readiness_of.
Print Assumptions bools_eqb.
Print Assumptions bools_eqb_decides_position_by_position.
Print Assumptions outcome_row.
Print Assumptions readiness_row.
Print Assumptions there_are_sixteen_readiness_states.
Print Assumptions the_rendezvous_or_refusal_family_agrees_with_the_readiness_state.
Print Assumptions every_readiness_state_decides_the_outcome.
Print Assumptions optimistic_at.
Print Assumptions refuses_where_unready.
Print Assumptions the_optimistic_family_is_refused_from_its_first_member.
Print Assumptions no_optimistic_transfer_refuses_where_the_peer_is_unready.
Print Assumptions drop_at_nm.
Print Assumptions insert_at_nm.
Print Assumptions inventory_deletions.
Print Assumptions inventory_insertions_of.
Print Assumptions the_inventory_family_sizes.
Print Assumptions every_inventory_deletion_leaves_a_class_unnamed.
Print Assumptions an_inserted_table_breaks_only_the_object_conjunct.
Print Assumptions an_inserted_reply_object_breaks_only_the_object_conjunct.
Print Assumptions a_duplicated_class_breaks_only_the_occurrence_conjunct.
Print Assumptions every_inventory_weakening_is_refused.
Print Assumptions no_inventory_deletion_is_closed.
Print Assumptions no_fourth_class_is_closed.
Print Assumptions inventory_refusal.
Print Assumptions no_inventory_deletion_meets_the_obligation.
Print Assumptions no_fourth_class_meets_the_obligation.
Print Assumptions the_badges_of_width_two.
Print Assumptions there_are_eight_badges_at_the_declared_width.
Print Assumptions every_badge_of_the_declared_width_is_admitted.
Print Assumptions no_badge_of_a_neighbouring_width_is_admitted.
Print Assumptions Numbering.
Print Assumptions NumbersEveryInvocation.
Print Assumptions NumbersNothingElse.
Print Assumptions the_specification_numbering_discharges_both.
Print Assumptions no_admissible_trap_surface_is_the_abi_cut.
Print Assumptions the_trap_shaped_cut_over_collects.
Print Assumptions the_syscall_carried_cut_over_collects.
Print Assumptions schedule_numbering.
Print Assumptions the_schedule_numbering_is_refuted.
Print Assumptions notification_numbering.
Print Assumptions the_notification_numbering_is_refuted.
Print Assumptions the_two_added_numberings_agree_with_the_specification_elsewhere.
Print Assumptions iouring_numbering.
Print Assumptions the_iouring_numbering_is_refuted.
Print Assumptions fifth_group_numbering.
Print Assumptions the_fifth_group_numbering_is_refuted.
Print Assumptions short_numbering.
Print Assumptions the_short_numbering_drops_a_member.
Print Assumptions notifying_grouping.
Print Assumptions the_notifying_grouping_fills_the_notification_group.
Print Assumptions the_notifying_grouping_keeps_the_four_clauses_it_does_not_break.
Print Assumptions all_notification_grouping.
Print Assumptions the_all_notification_grouping_is_refuted.
Print Assumptions the_withdrawn_coverage_clause_answered_five_of_it.
Print Assumptions the_notifying_grouping_moves_one_member_and_one_census.
Print Assumptions submission_queue_dispatch.
Print Assumptions quiet_memory.
Print Assumptions loaded_memory.
Print Assumptions the_submission_queue_dispatch_is_refuted.
Print Assumptions the_submission_queue_dispatch_agrees_where_the_memory_agrees.
Print Assumptions table_designation.
Print Assumptions the_table_designation_is_refuted.
Print Assumptions the_table_designation_names_objects_everywhere_else.
Print Assumptions table_lifecycle.
Print Assumptions the_table_lifecycle_is_refuted.
Print Assumptions frozen_lifecycle.
Print Assumptions the_frozen_lifecycle_states_nothing.
Print Assumptions reply_object_return.
Print Assumptions the_reply_object_return_spends_a_class.
Print Assumptions sealed_reply_return.
Print Assumptions the_sealed_reply_return_spends_a_type_and_mints.
Print Assumptions composition_sealed_return.
Print Assumptions the_composition_sealed_return_separates_the_type_from_the_mint.
Print Assumptions fifth_group_return.
Print Assumptions the_fifth_group_return_replies_by_an_unnumbered_act.
Print Assumptions three_offers.
Print Assumptions the_specification_parks_nothing_across_a_re_offer_sequence.
Print Assumptions the_four_return_paths_declare.
Print Assumptions the_re_offer_sequence_visits_three_endpoints.
Print Assumptions queueing_transfer.
Print Assumptions the_queueing_transfer_parks_a_request.
Print Assumptions the_queueing_kernel_grows_with_the_offer_sequence.
Print Assumptions blocking_transfer.
Print Assumptions the_blocking_transfer_leaves_its_caller_waiting.
Print Assumptions waking_transfer.
Print Assumptions the_waking_transfer_moves_another_partition.
Print Assumptions deaf_transfer.
Print Assumptions the_deaf_transfer_never_rendezvouses.
Print Assumptions the_optimistic_transfer_crosses_to_an_unready_peer.
Print Assumptions status_delivered.
Print Assumptions status_run.
Print Assumptions the_status_word_carries_what_did_not_cross.
Print Assumptions the_status_word_reports_the_refusal_correctly.
Print Assumptions the_specification_delivers_on_one_state_and_not_the_other.
Print Assumptions retrying_refusal.
Print Assumptions the_retrying_refusal_is_refuted.
Print Assumptions the_retrying_refusal_is_still_bounded_for_the_yield.
Print Assumptions the_retrying_refusal_costs.
Print Assumptions ambient_grant.
Print Assumptions the_ambient_grant_mints.
Print Assumptions stingy_grant.
Print Assumptions the_stingy_grant_transfers_nothing.
Print Assumptions replacing_grant.
Print Assumptions the_replacing_grant_moves_what_is_not_named.
Print Assumptions bulk.
Print Assumptions bulk_length.
Print Assumptions bulk_message.
Print Assumptions no_bulk_payload_crosses_the_kernel.
Print Assumptions the_specification_medium_carries_no_bulk_data.
Print Assumptions a_payload_past_the_budget_carries_bulk_data.
Print Assumptions the_medium_admits_a_message_at_the_budget_and_refuses_one_past_it.
Print Assumptions the_slot_budget_binds_beside_the_register_budget.
Print Assumptions counting_armed.
Print Assumptions counting_signal.
Print Assumptions counting_reset.
Print Assumptions the_counting_signal_does_not_coalesce.
Print Assumptions the_counter_separates_two_signals_from_one.
Print Assumptions the_counting_word_is_armed_above_zero.
Print Assumptions identity_reset.
Print Assumptions the_identity_reset_is_undefined.
Print Assumptions naive_decide.
Print Assumptions the_naive_decider_loses_a_wakeup.
Print Assumptions post_only_decide.
Print Assumptions the_post_only_decider_yields_over_a_drained_ring.
Print Assumptions the_decider_truth_table.
Print Assumptions the_ring_indices_are_the_source_of_truth.
Print Assumptions unswapped_delivery.
Print Assumptions the_unswapped_delivery_is_refuted_on_the_swap_arm.
Print Assumptions the_unswapped_delivery_is_admitted_on_the_static_arm.
Print Assumptions the_static_arm_admits_the_construction_of_every_machine.
Print Assumptions the_construction_is_the_specification_on_the_static_arm.
Print Assumptions the_guarded_clause_is_empty_on_the_static_arm.
Print Assumptions the_unswapped_rotation_is_predecessor_dependent.
Print Assumptions head_member_delivery.
Print Assumptions the_head_member_delivery_separates_the_two_clauses.
Print Assumptions sharing_step.
Print Assumptions the_sharing_step_overwrites_a_sibling.
Print Assumptions the_sharing_step_agrees_on_the_member_it_dispatches.
Print Assumptions clearing_step.
Print Assumptions the_clearing_step_loses_what_a_member_left.
Print Assumptions the_round_trip_restores_under_one_step_and_not_the_other.
Print Assumptions work_stealing_advance.
Print Assumptions the_work_stealing_rotation_is_refuted.
Print Assumptions the_work_stealing_rotation_agrees_where_nothing_is_observed.
Print Assumptions mixed_group.
Print Assumptions the_mixed_label_group_is_refused.
Print Assumptions the_composed_group_is_admissible.
Print Assumptions the_mixed_group_names_a_partition_of_another_label.
Print Assumptions the_mixed_group_crosses_a_label_boundary.
Print Assumptions predecessor_inference.
Print Assumptions the_predecessor_inference_is_refuted.
Print Assumptions base_residue.
Print Assumptions touches_the_first_class.
Print Assumptions after_the_second_member.
Print Assumptions the_residue_is_not_the_predecessors_at_an_untouched_class.
Print Assumptions the_inference_is_right_where_the_predecessor_wrote.
