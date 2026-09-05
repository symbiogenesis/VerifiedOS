(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   CopyRingService.v

   One copy-based service over the ring contract M6.4 generated, as the
   register fixes it: R-12-005's bounded SPSC ring whose peer is a server;
   R-12-008a's four payload-slot ownership phases and the three paths its
   acceptance clause rejects; R-12-091's composition-time constants and its
   criterion that indices are interpreted modulo the declared capacity with
   sequence information distinguishing full from empty; R-12-092's descriptor
   and the validation that precedes eligibility; R-12-093's one terminal
   completion per accepted request; R-12-094's monotone six-state lifecycle
   with its one malformed step; R-12-095's fail-closed exhaustion on both
   sides; R-12-096's coalescible notification hint, its binary armed word with
   a defined reset, its arm-recheck-sleep order and the lost wakeup that order
   excludes; R-12-097's cleanup bound and the interval admission accounts;
   R-12-098's batch as an amortization unit and never a transaction;
   R-12-100's bounded segment list read through R-12-101's per-variant record;
   and R-12-101's per-operation accounting and the joint bound the composition
   is required to prove. R-12-012a is what makes the copy-once statement the
   file's own subject rather than a detail: a declared type bounds what a
   value is and never what it means to the receiver, and a service that reads
   a delegated buffer twice has validated one image and copied another.

   Which entries this file is stated over is derived, and the derivation is
   stated in three steps a reviewer checks one at a time. M6.5a's cell cites
   no requirement id; it carries the class-X ground alone. **Step one** reads
   the three families off M6.5's own lead, that the copy-based service carries
   the SPSC, notification and capacity proofs: R-12-005 and R-12-008a are the
   SPSC, R-12-096 the notification, R-12-095 with R-12-098 the capacity.
   **Step two** takes what those spell out, which is a reading and not a
   judgment: R-12-005's sentence cites R-07-029, R-12-008a's cites R-12-008a's
   own CHERI-TAL derivation, R-12-095's acceptance clause cites R-08-047,
   R-05-097, R-07-036 and R-17-030u, R-12-096's names no id, and R-12-098's
   cites R-12-009. **Step three** is the judgment, and it reaches the rest by
   section 6's own lead, that a service which cannot state its finite
   capacities, lifecycle semantics, cleanup bounds and per-operation WCET is
   not admitted through the ring profile: the lifecycle is R-12-094, the
   cleanup bound R-12-097, the per-operation WCET R-12-101, and the finite
   capacities R-12-091's constants read through R-12-095. Two more are reached
   by a noun one of those uses and does not define: R-12-096's *sleep* reaches
   R-07-029a, which is the entry that says what a sleep is here and that it is
   nowhere a block, and R-12-101's *slot budget* reaches R-11-006, which is
   what an in-slot WCET is admitted against. A reviewer who disagrees with the
   scope disagrees with step three; steps one and two are checkable against
   the register's own text.

   This file Requires RingContract.v, and that is a dependency rather than a
   citation. That artifact is the generated interface artifact IDL-064 names,
   K-89 holds it byte-identical to what `run.py ring emit` writes, and it is
   the one owner of the declared constants, the closed status set, the six
   lifecycle states, the cancellation answers and the per-variant records this
   file is stated over. Re-declaring any of them here would be a second copy
   of a generated artifact, which is the one thing this repository's whole
   discipline refuses. So every constant below is instantiated and none is
   transcribed, and nothing declared here shadows a name that file exports:
   the ring constants, `submit`, `accept`, `may_reserve`, `work_pending`,
   `sleeps`, `agree`, `eqb_reflexive`, `activation_cost`,
   `cancellation_interval`, the five record types and every `op_`, `enc_`,
   `rec_` and `lifecycle_` name are used at the spelling RingContract gives
   them. `cancel` is the one exported name this file deliberately does not
   reach, R-12-097's four answers being M6.5b's family and this file stating
   only the cleanup accounting beside them. `work_pending` and `sleeps` are
   reached at the two bridge theorems and nowhere else, because this file's
   algebra is sequence numbers where the contract's is wire indices, and the
   bridge is what makes those one algebra rather than two that agree in a
   comment. A mutant of this file costs its own compile and
   RingContract's is already on disk from the baseline, so the Require is paid
   once per run rather than once per member of the seeded population.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. Every quantity a composition
   fixes and the contract does not is a field of the `Service` record rather
   than a literal or a top-level Parameter, which is what keeps the R-05-163
   assumption gate green while leaving the decision where its owner can make
   it. Nothing is admitted and nothing is axiomatized: the Print Assumptions
   block at the end reports every shipped constant closed under the global
   context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. Nothing here is compiled,
   lowered, or run on either emulator. No ring exists and no service rides
   one: no page is mapped, no descriptor is encoded or parsed, no byte is
   copied, no notification word is written, no partition is scheduled and no
   device is touched. The computed checks are decided inside the kernel by
   conversion and print nothing. R-18-037's canonical SPSC proof is a proof
   about an implementation under Ztso and this is not one: what is stated here
   is a discipline over an index algebra and an ordered protocol, which is the
   thing an implementation would be refined to and never a substitute for the
   refinement.

   What is deferred, and to which item. M6.5b owns the DMA service, and with
   it the whole of R-12-100's capability face: the session-table capability
   whose permissions match the declared direction, the extent validated before
   the transfer starts, the per-segment fabric check, the tag clearing of
   R-15-183, the DMA quiescence rule and the teardown that revokes it. It also
   owns cancellation's race semantics as a family; RingContract already states
   the four answers R-12-097 fixes and this file states only the cleanup
   accounting beside them, which is what section 6's lead asks of every
   service. M6.2's admission checker does not exist on either side, so what is
   below is a declaration with an admission rule to satisfy and nothing to be
   admitted by, which is IDL-068's own second limit and is not repaired by
   narrowing anything here. R-12-011's flow labels are the contract's and
   RingContract states them against the declared lattice; nothing here adds a
   flow theorem, the lattice having no membership anywhere (F-216j).

   Readings of the register this statement takes, each a reviewable judgment
   rather than a neutral transcription:

   1. The index algebra is a pair of free-running sequence numbers and the
      wire index is that number modulo the declared span. R-12-091's criterion
      says indices are interpreted modulo the declared capacity with sequence
      information distinguishing full from empty, which is exactly the pair:
      the sequence number is what distinguishes them and the modulus is what
      the wire carries. So `rv_produced` and `rv_consumed` are monotone and
      `rv_wire` and `rv_slot` are the two reductions, and the separation of a
      live window is a computed fact about the declared constants rather than
      an assumption.
   2. Occupancy is the difference of the two sequence numbers, and the
      ordering `consumed <= produced` is carried in the invariant rather than
      assumed. That is what makes the two-consumer construction refutable: it
      breaks the ordering and not the capacity bound.
   3. An interleaving is an arbitrary list of turns. R-12-005's SPSC and
      R-12-008a's three concurrently shared cells together say that each agent
      writes one index and reads the other, so a schedule is a list over a
      two-member alphabet and the invariant is stated of every one of them.
      This is the only place a genuine quantifier over executions appears, and
      it is a quantifier over a list rather than over a memory model: Ztso is
      R-18-037's and is not modelled here.
   4. Ordering is stated as an ordered list of acts and never as a memory
      fence. R-12-096 names the producer's release publication and the
      consumer's drain, arm, recheck and sleep in that order, so the producer
      chain is three acts and the consumer chain is four, and each weakening
      is generated over the chain rather than authored.
   5. The lost wakeup is a property of an interleaving and not of a decision
      rule. RingContract already states R-12-096's decision rule over two
      reads of the producer index and holds a consumer that skips the recheck
      to it. What is left, and what this file states, is the interleaving: the
      producer publishes at one step of the consumer's chain, reads the armed
      word at that instant, and signals only if it is armed. The obligation is
      that no schedule leaves the consumer asleep with work pending and no
      signal sent.
   6. The notification word's reset is a declared field and both arms are
      exhibited. R-12-096 requires a binary armed state with a *defined*
      reset and defines none, and IDL-059 restates the requirement without
      choosing (gap a). Both arms exclude the lost wakeup; they differ on
      coalescing, and R-12-101's declared maximum notifications is what
      refuses one of them, so the arm this file's admission conjunct takes is
      taken on a declared bound and not by fiat.
   7. R-12-100's segment discipline reaches a service that copies only through
      R-12-101's per-variant record. That entry's own sentence is about
      zero-copy DMA and this service delegates nothing; what obliges a copying
      service to bound its segments is the record field R-12-101 requires of
      *every* operation variant (gap b). The bound is stated over that field
      and nothing of R-12-100's capability face is claimed.
   8. Copy-once is R-05-124 read at a service rather than at a parser. That
      requirement has a copy-once parser write its fixed destination buffer
      whole, and R-12-012a puts the validation of every index, length, offset
      and selector at the receiver. A service that reads a delegated buffer
      twice has validated the first image and copied the second, and no entry
      excludes it (gap j), so it is refuted here by construction rather than
      cited as an absence.
   9. Every generated family is a list of constructions whose fallback past
      the last index is the specification's own chain. That is what makes a
      bounded quantifier over the index decide anything: a bound raised by one
      reaches the specification, which satisfies the obligation the family is
      refuted for breaking, so the theorem fails rather than holding vacuously
      wider.
  10. Boolean rather than propositional wherever the witnesses must compute:
      the chain conjuncts, the service conjuncts, the interleaved run and the
      accounting arithmetic are all decidable, so the generated families are
      checked by conversion rather than by a proof per member.
  11. A lifecycle step is lawful by the contract's own two *relations* and never
      by the rank arithmetic that agrees with them. R-12-094 puts one malformed
      step, from Submitted to Terminal, and `lifecycle_malformed` answers
      `None` at the other five states; a conjunct reading "one rank more or two
      ranks more" licenses a skip at *every* state, which is a second malformed
      step the entry does not license. The two readings are both carried below
      and the construction that separates them is the skipping advancer, so
      what the reading buys is machine-checked rather than asserted.

   The literals taken from the register, and there are five. The criterion is
   the same at each: one sentence of one entry names its members and closes
   the set, and the count sits beside the sentence rather than in prose. A
   sentence that names no member closes nothing, which is why the live-state
   subset (gap d) and the polling cadence (gap f) are fields:

   - R-12-008a's "producer-exclusive writable; release-published and
     producer-inaccessible; consumer-acquired immutable; completed and
     returned to producer ownership" is four, so `ownership` has four
     constructors and `there_are_four_ownership_phases` is its count.
   - R-12-008a's acceptance clause, "rejects any path that reads a slot before
     acquire, writes it after publication, or restores producer write
     ownership before every consumer reader is consumed", is three, so
     `ownership_defect` has three constructors and
     `there_are_three_rejected_paths` is its count.
   - R-12-008a's "only head, tail, and notification cells are concurrently
     shared" is three, and R-12-091's header is exactly four words, so
     `header_word` has four constructors, `is_shared_cell` marks three of them,
     and the two counts are stated against each other rather than separately.
   - R-12-096's "drains within its admitted budget, arms its notification
     word, re-reads the producer index, and sleeps only if the recheck still
     shows no work" is four acts in one order, so `consumer_act` has four
     constructors and `spec_consumer_chain` is that order.
   - R-12-096's "the producer publishes with release ordering and signals only
     when the consumer may sleep" is three acts in one order once the
     publication is read as R-12-008a reads it, staging the payload and then
     releasing it, so `producer_act` has three constructors and
     `spec_producer_chain` is that order.

   Two further enumerations are the *contract's* and are used at RingContract's
   own spelling rather than restated: R-12-093's eight statuses and
   R-12-094's six lifecycle states. `all_slot_states` below is a list over
   that inductive and its length is checked against the contract's own
   lifecycle rank rather than written as a figure.

   Every other magnitude is a field: the service's accepted ceiling and its
   two declared slacks, its batch and the batch's slack, and per operation its
   segment count, staging buffer, cleanup cost, released-reference count, the
   three costs it reproduces from the declaration, its accounted latency, its
   progress slack and its declared progress bound; and beside those the live
   state set, the notification reset owner, whether a counter exists, the
   polling cadence, which accounting the service declares, whether the copy is
   charged at the declared maximum, and the service's own identity.

   How the refutations are generated. Over the two act chains: `swap_at`
   transposes an adjacent pair, `drop_at` deletes an act, `suffix_at` re-enters
   at a proper suffix, and `insert_at` binds one act a second time, so the four
   families are refused as one conversion, again per family, and again as a
   bounded quantifier over the index. Over the thirteen service conjuncts:
   `spoiled_at` moves one declared field to the value on that conjunct's own
   boundary and `declared_without` drops one conjunct from the admission
   filter, so the thirteen are decided twice, once from the declaration side
   and once from the filter side. The hand-authored refutations are the ones
   no index generates, being alternative constructions rather than mutations
   of a list: the dual producer, the dual consumer, the untested producer and
   consumer, the staging-only producer, the reordering consumer read at the
   interleaving rather than at the chain, the never-signalling publisher, the
   counting consumer, the greedy consumer, the transactional batch, the
   backward, skipping and reader-holding advancers, the acceptor before
   validation, the revalidating copy and the arrival-charged accounting. The
   partial enqueue is the untested producer met at the other obligation and not
   a fourteenth construction.

   What this file deliberately does not author, with the entry that owes each
   decision. A register gap is reported, not closed:

   a. Which agent resets the notification word and at which point.
      R-12-096 requires a binary armed state with a *defined* reset and
      defines none; IDL-059 restates the requirement. Both arms are exhibited,
      both exclude the lost wakeup, and they differ on how many signals one
      arming admits. Owed at R-12-096.
   b. Whether R-12-100's bounded-segment discipline reaches a service that
      copies. That entry's sentence is about zero-copy DMA throughout; what
      reaches a copying service is R-12-101's per-variant maximum segment
      count, which is a record field rather than an obligation of an entry.
      Owed at R-12-100 or R-12-101.
   c. What a copy-based service's device-service bound is a bound on.
      R-12-101 has it imported from the device contract and a copy-based
      service has no device and no device contract, so the largest term of
      this service's per-operation WCET has no named owner. Owed at R-12-101.
   d. Which of R-12-094's six states make a request identifier live.
      R-12-092 requires the identifier unique among the session's *live*
      requests and R-12-094 has the derivation reject reuse of a live one,
      and nothing marks the subset. Submitted and Accepted are forced and
      Free and Reclaimed are excluded, on pain of no identifier ever being
      reusable; Writing and Terminal are left to the declaration and both
      arms are exhibited. Owed at R-12-092 or R-12-094.
   e. Whether the accounted latency of R-12-101's declared progress bound
      includes the queueing delay of the requests ahead of a submission. The
      entry names capacity, batch size, polling cadence, slot budget and
      device latency and no relation among them, so an accounting that charges
      the queue and one that charges the operation alone are both readings.
      Both are exhibited and the difference is machine-checked. Owed at
      R-12-101.
   f. Where the polling cadence is declared. It is one of the five terms
      R-12-101's joint bound is over and it is not among the constants
      R-12-091 enumerates, nor among the fourteen the ring declaration fixes,
      so the term the arithmetic turns on is declared nowhere. Owed at
      R-12-101 or R-12-091.
   g. How R-12-008a's four ownership phases refine into R-12-094's six
      lifecycle states. R-12-094's acceptance clause says the lifecycle
      refines those transitions without weakening them and gives no map, and
      four and six do not pair by counting. Both are carried here and neither
      is stated as a function of the other. Owed at R-12-094.
   h. What the producer reads when R-12-096 has it signal "only when the
      consumer may sleep". Whether the consumer may sleep is the consumer's
      own recheck, and the only thing R-12-091's header gives the producer is
      the notification word, so either the armed word is that predicate or the
      clause names something no header cell carries. This file reads the armed
      word as the predicate and says so. Owed at R-12-096.
   i. What a copy-based service copies into. R-05-124 has a copy-once parser
      write its fixed destination buffer whole and no entry gives a server a
      staging buffer, a size for it, or a lifetime. `so_staging` is a field
      and the obligation over it is that it holds the declared payload plus
      its own declared headroom. Owed at R-05-124 or R-12-101.
   j. Whether a server may re-read a delegated buffer after validating it.
      R-12-092 puts the validation before eligibility and says nothing about a
      second read; R-12-100's *never reinterpreted after* is stated of the DMA
      extent alone. So the time-of-check defect a copying service is exposed
      to is excluded by no entry, and it is refuted here by construction.
      Owed at R-12-092 or R-12-012a.
   k. Every composition magnitude. The accepted ceiling and its two slacks,
      the batch and its slack, and per operation the segments, the staging
      buffer, the cleanup cost, the released-reference count, the three
      reproduced costs, the accounted latency, the progress slack and the
      progress bound are fields; so are the live state set, the reset owner,
      the counter flag, the cadence, the accounting arm, the charging rule and
      the identity. The demo service at the end instantiates each with a
      witness value that carries no composition claim, and the ledger pins
      every one of them.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary service, schedule, chain, publisher, consumer,
   batch, advancer or copier, proved of the specification, and refuted of an
   alternative construction the register's own sentence excludes. Every
   refuting construction is also shown to satisfy the obligations it does not
   break, so what refuses it is the named defect and not its shape.
   Inhabitation is concrete: one declared service over the contract's five
   operations, thirteen one-field spoilings of it, a schedule algebra with a
   value on every boundary the file compares at, twenty-six generated chain
   weakenings, two publication bursts, two accounting arms, two live-state
   arms and two buffer images.
   ========================================================================= *)

Require Import RingContract.

(* -------------------------------------------------------------------------
   List, boolean and arithmetic helpers, defined here rather than imported:
   the prelude carries the list type and not the library over it, and
   RingContract carries `agree` and `eqb_reflexive` and nothing else, so those
   two are used at its spelling and the rest are authored. Importing a module
   to save a page would put its assumptions inside the R-05-163 gate's reach
   for no gain.
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

Fixpoint sum_of (l : list nat) : nat :=
  match l with nil => 0 | cons x r => x + sum_of r end.

Fixpoint map_over {A B : Type} (f : A -> B) (l : list A) : list B :=
  match l with nil => nil | cons x r => cons (f x) (map_over f r) end.

Fixpoint filter_of {A : Type} (p : A -> bool) (l : list A) : list A :=
  match l with
  | nil => nil
  | cons x r => if p x then cons x (filter_of p r) else filter_of p r
  end.

(* 0 through n-1, in that order: the index set every generated family ranges
   over. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

(* The nth member of a list, or the declared fallback past its end. Reading 9
   is what this is for. *)
Fixpoint at_member {A : Type} (l : list A) (n : nat) (dflt : A) : A :=
  match l with
  | nil => dflt
  | cons x r => match n with 0 => x | S k => at_member r k dflt end
  end.

(* Transpose the adjacent pair at n, delete the member at n, re-enter at the
   suffix beginning at n, and bind one member a second time at n. The four
   generators of the chain families (R-05-166). *)
Fixpoint swap_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons a (cons b r) => cons b (cons a r)
  | 0, _ => l
  | S k, cons a r => cons a (swap_at k r)
  | S _, nil => nil
  end.

Fixpoint drop_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons _ r => r
  | 0, nil => nil
  | S k, cons a r => cons a (drop_at k r)
  | S _, nil => nil
  end.

Fixpoint suffix_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, _ => l
  | S k, cons _ r => suffix_at k r
  | S _, nil => nil
  end.

Fixpoint insert_at {A : Type} (n : nat) (x : A) (l : list A) : list A :=
  match n, l with
  | 0, _ => cons x l
  | S k, cons a r => cons a (insert_at k x r)
  | S _, nil => cons x nil
  end.

(* How many times a member occurs, the index of its first occurrence, and the
   index of its last, each answering the list's own length where it does not
   occur at all. The three readings every chain conjunct below is built from,
   so that "some drain precedes the first arm" is a computation and not a
   pattern. *)
Fixpoint occurrences {A : Type} (eq : A -> A -> bool) (x : A) (l : list A) : nat :=
  match l with
  | nil => 0
  | cons y r => (if eq x y then 1 else 0) + occurrences eq x r
  end.

Fixpoint first_at {A : Type} (eq : A -> A -> bool) (x : A) (l : list A) : nat :=
  match l with
  | nil => 0
  | cons y r => if eq x y then 0 else S (first_at eq x r)
  end.

Fixpoint last_at {A : Type} (eq : A -> A -> bool) (x : A) (l : list A) : nat :=
  match l with
  | nil => 0
  | cons y r =>
      if Nat.ltb (last_at eq x r) (count_of r) then S (last_at eq x r)
      else if eq x y then 0 else S (last_at eq x r)
  end.

(* The smaller of two, written here rather than taken from a library so that
   nothing below rests on a name the prelude may or may not carry. *)
Definition svc_least (a b : nat) : nat := if Nat.leb a b then a else b.

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

Lemma andb_join : forall a b : bool, a = true -> b = true -> andb a b = true.
Proof. intros a b Ha Hb. rewrite Ha. rewrite Hb. reflexivity. Qed.

Lemma nat_leb_refl : forall n : nat, Nat.leb n n = true.
Proof. induction n as [| k IH]; simpl; [ reflexivity | exact IH ]. Qed.

Lemma nat_leb_succ_r : forall a b : nat, Nat.leb a b = true -> Nat.leb a (S b) = true.
Proof.
  induction a as [| x IH]; intros b H.
  - reflexivity.
  - destruct b as [| y]; [ discriminate H | simpl in H; simpl; exact (IH y H) ].
Qed.

Lemma nat_leb_from_succ : forall a b : nat, Nat.leb (S a) b = true -> Nat.leb a b = true.
Proof.
  induction a as [| x IH]; intros b H.
  - reflexivity.
  - destruct b as [| y]; [ discriminate H | simpl in H; simpl; exact (IH y H) ].
Qed.

Lemma nat_leb_pred : forall n m : nat, Nat.leb n m = true -> Nat.leb (Nat.pred n) m = true.
Proof.
  intros n m H. destruct n as [| k].
  - reflexivity.
  - simpl. exact (nat_leb_from_succ k m H).
Qed.

(* Subtraction matches on its first argument, so `n - 0` is stuck wherever `n`
   is a variable and this is not the identity the prelude reduces for free. *)
Lemma nat_sub_zero : forall n : nat, n - 0 = n.
Proof. destruct n; reflexivity. Qed.

Lemma nat_sub_succ_l :
  forall p c : nat, Nat.leb c p = true -> S p - c = S (p - c).
Proof.
  intros p c. revert p. induction c as [| k IH]; intros p H.
  - simpl. rewrite (nat_sub_zero p). reflexivity.
  - destruct p as [| q]; [ discriminate H | simpl in H; simpl; exact (IH q H) ].
Qed.

Lemma nat_sub_succ_r : forall p c : nat, p - S c = Nat.pred (p - c).
Proof.
  induction p as [| q IH]; intros c.
  - reflexivity.
  - destruct c as [| d].
    + simpl. exact (nat_sub_zero q).
    + simpl. exact (IH d).
Qed.

Lemma nat_ltb_sub_pos :
  forall p c : nat, Nat.ltb 0 (p - c) = true -> Nat.leb (S c) p = true.
Proof.
  intros p c. revert p. induction c as [| k IH]; intros p H.
  - destruct p as [| q]; [ discriminate H | reflexivity ].
  - destruct p as [| q]; [ discriminate H | simpl in H; simpl; exact (IH q H) ].
Qed.

(* The two arithmetic facts the ring invariant turns on, stated syntactically
   so that the rewriting happens here and the invariant proofs below are
   conversions rather than simplifications. *)
Lemma leb_sub_succ :
  forall p c cap : nat,
    Nat.leb c p = true -> Nat.ltb (p - c) cap = true -> Nat.leb (S p - c) cap = true.
Proof.
  intros p c cap Hord Hg. rewrite (nat_sub_succ_l p c Hord). exact Hg.
Qed.

Lemma leb_pred_sub :
  forall p c cap : nat, Nat.leb (p - c) cap = true -> Nat.leb (p - S c) cap = true.
Proof.
  intros p c cap H. rewrite nat_sub_succ_r. exact (nat_leb_pred _ _ H).
Qed.

(* A conjunction over a list and the count of what it breaks are one fact
   read two ways, which is what lets a declaration's admission and its broken
   count be stated of an arbitrary declaration rather than of a witness. *)
Lemma all_of_is_none_broken :
  forall (A : Type) (p : A -> bool) (l : list A),
    agree (all_of p l)
          (Nat.eqb (count_of (filter_of (fun x => negb (p x)) l)) 0) = true.
Proof.
  intros A p l. induction l as [| x r IH].
  - reflexivity.
  - simpl. destruct (p x); simpl; [ exact IH | reflexivity ].
Qed.

(* =========================================================================
   The closed enumerations this file adds, each with the sentence that closes
   it beside its count. Two more are the contract's and are used at
   RingContract's own spelling: R-12-093's eight statuses and R-12-094's six
   lifecycle states.
   ========================================================================= *)

(* R-12-008a: "producer-exclusive writable; release-published and
   producer-inaccessible; consumer-acquired immutable; completed and returned
   to producer ownership". Four phases of one payload slot. *)
Inductive ownership : Set :=
  | own_producer_writable
  | own_published
  | own_consumer_acquired
  | own_returned.

(* R-12-008a's acceptance clause: "rejects any path that reads a slot before
   acquire, writes it after publication, or restores producer write ownership
   before every consumer reader is consumed". Three paths. *)
Inductive ownership_defect : Set :=
  | reads_before_acquire
  | writes_after_publication
  | restores_under_a_reader.

(* R-12-091: the header is exactly a producer index, a consumer index, a
   notification word and a generation word. Four cells. *)
Inductive header_word : Set :=
  | hw_producer_index
  | hw_consumer_index
  | hw_notification
  | hw_generation.

(* R-12-096, the consumer's own order: drain, arm, recheck, sleep. *)
Inductive consumer_act : Set :=
  | act_drain
  | act_arm
  | act_recheck
  | act_sleep.

(* R-12-096 with R-12-008a, the producer's: stage the payload, release it by
   advancing the index, signal. *)
Inductive producer_act : Set :=
  | act_stage
  | act_advance
  | act_signal.

(* The two the register leaves open and this file carries as declarations
   rather than deciding (gaps a and e). *)
Inductive reset_owner : Set :=
  | reset_at_the_signal
  | reset_at_the_drain.

Inductive accounting : Set :=
  | accounts_the_queue
  | accounts_the_service_alone.

(* The service's own acts on one request slot, which is what drives R-12-094's
   lifecycle. Six, one per transition that entry states, the last being its
   one admitted step past a successor. *)
Inductive service_event : Set :=
  | ev_reserve
  | ev_publish
  | ev_accept
  | ev_complete
  | ev_reclaim
  | ev_malformed.

(* Which agent takes a turn, which is what an interleaving is a list of
   (reading 3). *)
Inductive turn : Set :=
  | producer_turn
  | consumer_turn.

Definition all_ownership_phases : list ownership :=
  cons own_producer_writable
  (cons own_published (cons own_consumer_acquired (cons own_returned nil))).

Definition all_rejected_paths : list ownership_defect :=
  cons reads_before_acquire
  (cons writes_after_publication (cons restores_under_a_reader nil)).

Definition all_header_words : list header_word :=
  cons hw_producer_index
  (cons hw_consumer_index (cons hw_notification (cons hw_generation nil))).

(* R-12-008a: only head, tail and notification are concurrently shared. The
   generation word is the fourth header cell and is immutable between
   reinitializations, so it is not one of the atomics. *)
Definition is_shared_cell (h : header_word) : bool :=
  match h with
  | hw_producer_index => true
  | hw_consumer_index => true
  | hw_notification => true
  | hw_generation => false
  end.

Definition all_slot_states : list slot_state :=
  cons state_Free (cons state_Writing (cons state_Submitted
  (cons state_Accepted (cons state_Terminal (cons state_Reclaimed nil))))).

Definition all_ops : list op :=
  cons op_read_extent (cons op_write_extent (cons op_flush
  (cons op_query_geometry (cons op_poll_status nil)))).

Definition all_events : list service_event :=
  cons ev_reserve (cons ev_publish (cons ev_accept
  (cons ev_complete (cons ev_reclaim (cons ev_malformed nil))))).

Example there_are_four_ownership_phases :
  count_of all_ownership_phases = 4.
Proof. reflexivity. Qed.

Example there_are_three_rejected_paths :
  count_of all_rejected_paths = 3.
Proof. reflexivity. Qed.

(* Stated against each other rather than separately: the header is four cells
   and exactly three of them are the atomics R-12-008a names. *)
Example three_of_the_four_header_words_are_shared :
  andb (Nat.eqb (count_of all_header_words) 4)
       (Nat.eqb (count_of (filter_of is_shared_cell all_header_words)) 3) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_generation_word_is_the_one_that_is_not_shared :
  is_shared_cell hw_generation = false.
Proof. reflexivity. Qed.

(* The contract's own two counts, read back through its own definitions rather
   than written here as figures: `op_count` is RingContract's and the
   lifecycle's length is its rank at the terminal state plus one. *)
Example the_operation_list_is_the_contracts :
  Nat.eqb (count_of all_ops) op_count = true.
Proof. vm_compute; reflexivity. Qed.

Example the_state_list_is_the_contracts_lifecycle :
  Nat.eqb (count_of all_slot_states) (S (lifecycle_rank state_Reclaimed)) = true.
Proof. vm_compute; reflexivity. Qed.

(* One event per step the contract states, which is what makes the count six:
   five states carry a successor and one carries the malformed step. Checking
   it against the number of *states* would be a coincidence, six states and six
   events agreeing for unrelated reasons. *)
Example there_are_six_service_events :
  Nat.eqb (count_of all_events)
          (count_of (filter_of (fun t => match lifecycle_next t with
                                         | Some _ => true
                                         | None => false
                                         end)
                               all_slot_states)
           + count_of (filter_of (fun t => match lifecycle_malformed t with
                                           | Some _ => true
                                           | None => false
                                           end)
                                 all_slot_states)) = true.
Proof. vm_compute; reflexivity. Qed.

Definition consumer_act_eqb (a b : consumer_act) : bool :=
  match a, b with
  | act_drain, act_drain => true
  | act_arm, act_arm => true
  | act_recheck, act_recheck => true
  | act_sleep, act_sleep => true
  | _, _ => false
  end.

Definition producer_act_eqb (a b : producer_act) : bool :=
  match a, b with
  | act_stage, act_stage => true
  | act_advance, act_advance => true
  | act_signal, act_signal => true
  | _, _ => false
  end.

Definition op_eqb (a b : op) : bool :=
  match a, b with
  | op_read_extent, op_read_extent => true
  | op_write_extent, op_write_extent => true
  | op_flush, op_flush => true
  | op_query_geometry, op_query_geometry => true
  | op_poll_status, op_poll_status => true
  | _, _ => false
  end.

Lemma op_eqb_refl : forall o : op, op_eqb o o = true.
Proof. intro o; destruct o; reflexivity. Qed.

Lemma consumer_act_eqb_refl : forall a : consumer_act, consumer_act_eqb a a = true.
Proof. intro a; destruct a; reflexivity. Qed.

Lemma producer_act_eqb_refl : forall a : producer_act, producer_act_eqb a a = true.
Proof. intro a; destruct a; reflexivity. Qed.

Example the_operations_are_pairwise_distinct :
  all_of (fun o => Nat.eqb (count_of (filter_of (op_eqb o) all_ops)) 1) all_ops = true.
Proof. vm_compute; reflexivity. Qed.

(* =========================================================================
   Part 1: the index algebra (readings 1, 2 and 3).

   R-12-091's criterion is that indices are interpreted modulo the declared
   capacity with sequence information distinguishing full from empty, so a
   view is a pair of free-running sequence numbers and the two reductions are
   what the wire and the slot table carry.
   ========================================================================= *)

Record ring_view : Set := mk_ring_view {
  rv_produced : nat;
  rv_consumed : nat
}.

Definition rv_occupancy (v : ring_view) : nat := rv_produced v - rv_consumed v.

Definition rv_ordered (v : ring_view) : bool :=
  Nat.leb (rv_consumed v) (rv_produced v).

Definition rv_bounded (v : ring_view) : bool :=
  Nat.leb (rv_occupancy v) ring_capacity.

Definition rv_ok (v : ring_view) : bool := andb (rv_ordered v) (rv_bounded v).

(* The wire index R-12-091 declares a width for, and the slot the capacity
   selects. Both are reductions of the sequence number and neither is the
   sequence number. *)
Definition rv_wire (i : nat) : nat := Nat.modulo i ring_index_span.
Definition rv_slot (i : nat) : nat := Nat.modulo i ring_capacity.

(* Sequence information distinguishes full from empty: over any window the
   capacity admits, two sequence numbers carry the same wire index only when
   they are the same number. This is a fact about the declared constants and
   it is what makes `work_pending`'s modular difference the occupancy. *)
Theorem the_wire_index_separates_a_live_window :
  all_of (fun base =>
            all_of (fun d => agree (Nat.eqb (rv_wire (base + d)) (rv_wire base))
                                   (Nat.eqb d 0))
                   (upto (S ring_capacity)))
         (upto ring_index_span) = true.
Proof. vm_compute; reflexivity. Qed.

(* A slot is reused exactly a capacity later, which is the whole content of
   "the producer never overwrites an unconsumed entry": every distance strictly
   inside the capacity lands on a different slot. *)
Theorem the_producer_never_writes_a_live_slot :
  all_of (fun base =>
            all_of (fun d => implb (Nat.ltb 0 d)
                                   (negb (Nat.eqb (rv_slot (base + d)) (rv_slot base))))
                   (upto ring_capacity))
         (upto ring_capacity) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_slot_is_reused_exactly_a_capacity_later :
  all_of (fun base => Nat.eqb (rv_slot (base + ring_capacity)) (rv_slot base))
         (upto ring_capacity) = true.
Proof. vm_compute; reflexivity. Qed.

(* And the two algebras are joined rather than asserted to be joined: over every
   occupancy the capacity admits and from every base the span carries, the
   contract's own `work_pending` on the two *wire* indices answers exactly
   whether this file's sequence-number occupancy is non-zero. Reading 1 rests
   on that identity, and until this it was a comment. A file that computes its
   occupancy by subtraction while the contract computes it modulo the span owes
   the bridge as a statement, because the two agree only inside a window the
   declared constants make. *)
Theorem the_occupancy_is_the_contracts_modular_difference :
  all_of (fun base =>
            all_of (fun occ => agree (work_pending (rv_wire (base + occ))
                                                   (rv_wire base))
                                     (Nat.ltb 0 occ))
                   (upto (S ring_capacity)))
         (upto ring_index_span) = true.
Proof. vm_compute; reflexivity. Qed.

(* The specification's two steps. Each writes one index and reads the other,
   which is what R-12-008a's three concurrently shared atomics buy: no
   read-modify-write on a shared cell is needed, and that is exactly why the
   single-producer, single-consumer restriction is load-bearing rather than
   decorative. *)
Definition rv_publish (v : ring_view) : ring_view :=
  if Nat.ltb (rv_occupancy v) ring_capacity
  then mk_ring_view (S (rv_produced v)) (rv_consumed v)
  else v.

Definition rv_take (v : ring_view) : ring_view :=
  if Nat.ltb 0 (rv_occupancy v)
  then mk_ring_view (rv_produced v) (S (rv_consumed v))
  else v.

Definition rv_step (t : turn) (v : ring_view) : ring_view :=
  match t with
  | producer_turn => rv_publish v
  | consumer_turn => rv_take v
  end.

Fixpoint rv_run (sched : list turn) (v : ring_view) : ring_view :=
  match sched with
  | nil => v
  | cons t r => rv_run r (rv_step t v)
  end.

Definition WritesOnlyTheProducerIndex (f : ring_view -> ring_view) : Prop :=
  forall v : ring_view, rv_consumed (f v) = rv_consumed v.

Definition WritesOnlyTheConsumerIndex (f : ring_view -> ring_view) : Prop :=
  forall v : ring_view, rv_produced (f v) = rv_produced v.

Theorem the_publisher_writes_only_the_producer_index :
  WritesOnlyTheProducerIndex rv_publish.
Proof.
  unfold WritesOnlyTheProducerIndex. intro v. unfold rv_publish.
  destruct (Nat.ltb (rv_occupancy v) ring_capacity); reflexivity.
Qed.

Theorem the_consumer_writes_only_the_consumer_index :
  WritesOnlyTheConsumerIndex rv_take.
Proof.
  unfold WritesOnlyTheConsumerIndex. intro v. unfold rv_take.
  destruct (Nat.ltb 0 (rv_occupancy v)); reflexivity.
Qed.

Lemma publish_keeps_the_invariant :
  forall v : ring_view, rv_ok v = true -> rv_ok (rv_publish v) = true.
Proof.
  intros v H. unfold rv_ok in H. destruct (andb_split _ _ H) as [ Hord Hbd ].
  unfold rv_publish. destruct (Nat.ltb (rv_occupancy v) ring_capacity) eqn:Hg.
  - unfold rv_ok. apply andb_join.
    + exact (nat_leb_succ_r (rv_consumed v) (rv_produced v) Hord).
    + exact (leb_sub_succ (rv_produced v) (rv_consumed v) ring_capacity Hord Hg).
  - unfold rv_ok. apply andb_join; [ exact Hord | exact Hbd ].
Qed.

Lemma take_keeps_the_invariant :
  forall v : ring_view, rv_ok v = true -> rv_ok (rv_take v) = true.
Proof.
  intros v H. unfold rv_ok in H. destruct (andb_split _ _ H) as [ Hord Hbd ].
  unfold rv_take. destruct (Nat.ltb 0 (rv_occupancy v)) eqn:Hg.
  - unfold rv_ok. apply andb_join.
    + exact (nat_ltb_sub_pos (rv_produced v) (rv_consumed v) Hg).
    + exact (leb_pred_sub (rv_produced v) (rv_consumed v) ring_capacity Hbd).
  - unfold rv_ok. apply andb_join; [ exact Hord | exact Hbd ].
Qed.

(* The SPSC statement: the invariant survives an arbitrary interleaving, which
   is a quantifier over every schedule of the two agents (reading 3). *)
Theorem the_invariant_survives_every_interleaving :
  forall (sched : list turn) (v : ring_view),
    rv_ok v = true -> rv_ok (rv_run sched v) = true.
Proof.
  induction sched as [| t r IH]; intros v H.
  - exact H.
  - simpl. apply IH. destruct t.
    + exact (publish_keeps_the_invariant v H).
    + exact (take_keeps_the_invariant v H).
Qed.

(* And the two boundaries the invariant is decided at, so that neither
   conjunct is dead: a ring exactly at capacity refuses, and a ring exactly at
   empty yields nothing. Both are RingContract's own results instantiated at
   this view. *)
Definition service_submit (v : ring_view) : submit_result := submit (rv_occupancy v).

Definition full_view : ring_view := mk_ring_view ring_capacity 0.
Definition brimming_view : ring_view := mk_ring_view (Nat.pred ring_capacity) 0.
Definition empty_view : ring_view := mk_ring_view 0 0.
Definition single_view : ring_view := mk_ring_view 1 0.

Theorem the_ring_fills_to_capacity_and_refuses_one_past :
  andb (may_reserve (rv_occupancy brimming_view))
       (match service_submit full_view with
        | submit_would_block => true
        | submit_enqueued => false
        end) = true.
Proof. vm_compute; reflexivity. Qed.

(* R-12-095's "no partial enqueue" as a property of the step rather than as a
   sentence: a refused submission leaves the view exactly where it was. *)
Definition NoPartialEnqueue (f : ring_view -> ring_view) : Prop :=
  forall v : ring_view,
    match service_submit v with
    | submit_would_block => andb (Nat.eqb (rv_produced (f v)) (rv_produced v))
                                 (Nat.eqb (rv_consumed (f v)) (rv_consumed v)) = true
    | submit_enqueued => True
    end.

Theorem the_specification_never_partially_enqueues : NoPartialEnqueue rv_publish.
Proof.
  unfold NoPartialEnqueue. intro v.
  unfold service_submit, submit, may_reserve, rv_publish.
  destruct (Nat.ltb (rv_occupancy v) ring_capacity).
  - exact I.
  - apply andb_join; apply eqb_reflexive.
Qed.

(* -------------------------------------------------------------------------
   The four constructions the SPSC restriction excludes, each refuted at the
   obligation it breaks and each shown to keep the one it does not.
   ------------------------------------------------------------------------- *)

(* Two producers that each read the same occupancy and each reserve against
   it. The single-producer restriction is exactly what makes the test-then-
   write above sound without an atomic read-modify-write. *)
Definition rv_publish_dual (v : ring_view) : ring_view :=
  if Nat.ltb (rv_occupancy v) ring_capacity
  then mk_ring_view (S (S (rv_produced v))) (rv_consumed v)
  else v.

(* Two consumers that each find the ring non-empty and each take. *)
Definition rv_take_dual (v : ring_view) : ring_view :=
  if Nat.ltb 0 (rv_occupancy v)
  then mk_ring_view (rv_produced v) (S (S (rv_consumed v)))
  else v.

(* A producer that publishes without testing the capacity, which is the
   overwrite R-12-095's first clause forbids. *)
Definition rv_publish_untested (v : ring_view) : ring_view :=
  mk_ring_view (S (rv_produced v)) (rv_consumed v).

(* A consumer that takes without testing for work. *)
Definition rv_take_untested (v : ring_view) : ring_view :=
  mk_ring_view (rv_produced v) (S (rv_consumed v)).

Definition KeepsTheInvariant (f : ring_view -> ring_view) : Prop :=
  forall v : ring_view, rv_ok v = true -> rv_ok (f v) = true.

Definition KeepsTheOrdering (f : ring_view -> ring_view) : Prop :=
  forall v : ring_view, rv_ok v = true -> rv_ordered (f v) = true.

Definition KeepsTheCapacity (f : ring_view -> ring_view) : Prop :=
  forall v : ring_view, rv_ok v = true -> rv_bounded (f v) = true.

Theorem the_dual_producer_is_refuted : ~ KeepsTheInvariant rv_publish_dual.
Proof.
  unfold KeepsTheInvariant. intro H.
  assert (E : rv_ok brimming_view = true) by (vm_compute; reflexivity).
  specialize (H brimming_view E). vm_compute in H. discriminate H.
Qed.

(* And it breaks the capacity bound alone: it still writes only the producer
   index and it still leaves the ordering standing, so what refuses it is the
   second reservation and not its shape. *)
Theorem the_dual_producer_keeps_the_ordering : KeepsTheOrdering rv_publish_dual.
Proof.
  unfold KeepsTheOrdering. intros v H. unfold rv_ok in H.
  destruct (andb_split _ _ H) as [ Hord _ ].
  unfold rv_publish_dual. destruct (Nat.ltb (rv_occupancy v) ring_capacity).
  - exact (nat_leb_succ_r _ _ (nat_leb_succ_r _ _ Hord)).
  - exact Hord.
Qed.

Theorem the_dual_producer_writes_only_the_producer_index :
  WritesOnlyTheProducerIndex rv_publish_dual.
Proof.
  unfold WritesOnlyTheProducerIndex. intro v. unfold rv_publish_dual.
  destruct (Nat.ltb (rv_occupancy v) ring_capacity); reflexivity.
Qed.

Theorem the_dual_consumer_is_refuted : ~ KeepsTheInvariant rv_take_dual.
Proof.
  unfold KeepsTheInvariant. intro H.
  assert (E : rv_ok single_view = true) by (vm_compute; reflexivity).
  specialize (H single_view E). vm_compute in H. discriminate H.
Qed.

(* The dual consumer breaks the ordering and keeps the capacity bound, which
   is the opposite half from the dual producer: the two refutations are not
   one refutation twice. *)
Theorem the_dual_consumer_keeps_the_capacity : KeepsTheCapacity rv_take_dual.
Proof.
  unfold KeepsTheCapacity. intros v H. unfold rv_ok in H.
  destruct (andb_split _ _ H) as [ _ Hbd ].
  unfold rv_take_dual. destruct (Nat.ltb 0 (rv_occupancy v)).
  - exact (leb_pred_sub (rv_produced v) (S (rv_consumed v)) ring_capacity
             (leb_pred_sub (rv_produced v) (rv_consumed v) ring_capacity Hbd)).
  - exact Hbd.
Qed.

Theorem the_dual_consumer_writes_only_the_consumer_index :
  WritesOnlyTheConsumerIndex rv_take_dual.
Proof.
  unfold WritesOnlyTheConsumerIndex. intro v. unfold rv_take_dual.
  destruct (Nat.ltb 0 (rv_occupancy v)); reflexivity.
Qed.

Theorem the_untested_producer_is_refuted : ~ KeepsTheInvariant rv_publish_untested.
Proof.
  unfold KeepsTheInvariant. intro H.
  assert (E : rv_ok full_view = true) by (vm_compute; reflexivity).
  specialize (H full_view E). vm_compute in H. discriminate H.
Qed.

Theorem the_untested_producer_keeps_the_ordering :
  KeepsTheOrdering rv_publish_untested.
Proof.
  unfold KeepsTheOrdering. intros v H. unfold rv_ok in H.
  destruct (andb_split _ _ H) as [ Hord _ ].
  exact (nat_leb_succ_r _ _ Hord).
Qed.

Theorem the_untested_consumer_is_refuted : ~ KeepsTheInvariant rv_take_untested.
Proof.
  unfold KeepsTheInvariant. intro H.
  assert (E : rv_ok empty_view = true) by (vm_compute; reflexivity).
  specialize (H empty_view E). vm_compute in H. discriminate H.
Qed.

Theorem the_untested_consumer_keeps_the_capacity :
  KeepsTheCapacity rv_take_untested.
Proof.
  unfold KeepsTheCapacity. intros v H. unfold rv_ok in H.
  destruct (andb_split _ _ H) as [ _ Hbd ].
  exact (leb_pred_sub (rv_produced v) (rv_consumed v) ring_capacity Hbd).
Qed.

(* R-12-095's *no partial enqueue* refuted, which the four theorems above do
   not reach: they are about the invariant and this is about what a *refused*
   submission leaves behind. The untested producer is the construction, because
   the only thing a refused submission can partially do in this algebra is move
   an index, and moving the producer index past a `would_block` answer is
   exactly the half-enqueue the clause forbids. *)
Theorem the_untested_producer_partially_enqueues :
  ~ NoPartialEnqueue rv_publish_untested.
Proof.
  unfold NoPartialEnqueue. intro H. specialize (H full_view).
  vm_compute in H. discriminate H.
Qed.

(* And the dual producer keeps that obligation, which is what makes the
   refutation the missing capacity test and not the extra reservation: a
   construction that over-reserves still leaves a refused submission alone. *)
Theorem the_dual_producer_never_partially_enqueues :
  NoPartialEnqueue rv_publish_dual.
Proof.
  unfold NoPartialEnqueue. intro v.
  unfold service_submit, submit, may_reserve, rv_publish_dual.
  destruct (Nat.ltb (rv_occupancy v) ring_capacity).
  - exact I.
  - apply andb_join; apply eqb_reflexive.
Qed.

(* The two boundaries the four refutations sit on, pinned so that a reader can
   see the invariant is decided somewhere and not merely stated. *)
Example the_refuting_views_sit_on_the_two_boundaries :
  andb (Nat.eqb (rv_occupancy brimming_view) (Nat.pred ring_capacity))
       (andb (Nat.eqb (rv_occupancy full_view) ring_capacity)
             (Nat.eqb (rv_occupancy empty_view) 0)) = true.
Proof. vm_compute; reflexivity. Qed.

(* =========================================================================
   Part 2: the two ordered protocols, and the weakenings generated over them
   (reading 4).
   ========================================================================= *)

Definition spec_consumer_chain : list consumer_act :=
  cons act_drain (cons act_arm (cons act_recheck (cons act_sleep nil))).

Definition spec_producer_chain : list producer_act :=
  cons act_stage (cons act_advance (cons act_signal nil)).

(* Seven conjuncts over a consumer chain. The first three are R-12-096's own
   order and the last four are its own count: the entry names each act once,
   and a second drain is a second budget, a second arm discards the recheck's
   information, a second recheck reads past the decision it feeds, and a
   second sleep is a second activation. *)
Definition consumer_conjuncts : list (list consumer_act -> bool) :=
  (* 0: some drain precedes the first arm *)
  cons (fun l => Nat.ltb (first_at consumer_act_eqb act_drain l)
                         (first_at consumer_act_eqb act_arm l))
  (* 1: the arm precedes the recheck *)
  (cons (fun l => Nat.ltb (last_at consumer_act_eqb act_arm l)
                          (last_at consumer_act_eqb act_recheck l))
  (* 2: the recheck precedes the sleep *)
  (cons (fun l => Nat.ltb (last_at consumer_act_eqb act_recheck l)
                          (last_at consumer_act_eqb act_sleep l))
  (* 3: exactly one drain *)
  (cons (fun l => Nat.eqb (occurrences consumer_act_eqb act_drain l) 1)
  (* 4: exactly one arm *)
  (cons (fun l => Nat.eqb (occurrences consumer_act_eqb act_arm l) 1)
  (* 5: exactly one recheck *)
  (cons (fun l => Nat.eqb (occurrences consumer_act_eqb act_recheck l) 1)
  (* 6: exactly one sleep *)
  (cons (fun l => Nat.eqb (occurrences consumer_act_eqb act_sleep l) 1)
   nil)))))).

Definition consumer_chain_ok (l : list consumer_act) : bool :=
  all_of (fun p => p l) consumer_conjuncts.

Definition consumer_broken (l : list consumer_act) : nat :=
  count_of (filter_of (fun p => negb (p l)) consumer_conjuncts).

(* Five conjuncts over a producer chain. The first two are the release order
   R-12-096 states; the third is R-05-124's copy-once read at the staging act,
   so a second stage is the time-of-check defect and not a redundancy; the
   fourth is R-12-094's publication consuming writable ownership once; and the
   fifth is R-12-101's declared maximum notifications met from the chain side,
   a signal being sent and being sent once. *)
Definition producer_conjuncts : list (list producer_act -> bool) :=
  (* 0: the payload is staged before the index is released *)
  cons (fun l => Nat.ltb (first_at producer_act_eqb act_stage l)
                         (first_at producer_act_eqb act_advance l))
  (* 1: the index is released before the signal *)
  (cons (fun l => Nat.ltb (last_at producer_act_eqb act_advance l)
                          (last_at producer_act_eqb act_signal l))
  (* 2: exactly one stage *)
  (cons (fun l => Nat.eqb (occurrences producer_act_eqb act_stage l) 1)
  (* 3: exactly one release *)
  (cons (fun l => Nat.eqb (occurrences producer_act_eqb act_advance l) 1)
  (* 4: exactly one signal *)
  (cons (fun l => Nat.eqb (occurrences producer_act_eqb act_signal l) 1)
   nil)))).

Definition producer_chain_ok (l : list producer_act) : bool :=
  all_of (fun p => p l) producer_conjuncts.

Definition producer_broken (l : list producer_act) : nat :=
  count_of (filter_of (fun p => negb (p l)) producer_conjuncts).

Example there_are_seven_consumer_conjuncts :
  count_of consumer_conjuncts = 7.
Proof. reflexivity. Qed.

Example there_are_five_producer_conjuncts :
  count_of producer_conjuncts = 5.
Proof. reflexivity. Qed.

Theorem the_specification_consumer_chain_breaks_nothing :
  andb (consumer_chain_ok spec_consumer_chain)
       (Nat.eqb (consumer_broken spec_consumer_chain) 0) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_specification_producer_chain_breaks_nothing :
  andb (producer_chain_ok spec_producer_chain)
       (Nat.eqb (producer_broken spec_producer_chain) 0) = true.
Proof. vm_compute; reflexivity. Qed.

(* The four generators, over any chain. *)
Definition transpositions {A : Type} (l : list A) : list (list A) :=
  map_over (fun k => swap_at k l) (upto (Nat.pred (count_of l))).

Definition deletions {A : Type} (l : list A) : list (list A) :=
  map_over (fun k => drop_at k l) (upto (count_of l)).

Definition proper_suffixes {A : Type} (l : list A) : list (list A) :=
  map_over (fun k => suffix_at (S k) l) (upto (count_of l)).

Definition duplications {A : Type} (l : list A) (d : A) : list (list A) :=
  map_over (fun k => insert_at k (at_member l k d) l) (upto (count_of l)).

Definition all_weakenings {A : Type} (l : list A) (d : A) : list (list A) :=
  app (transpositions l)
      (app (deletions l) (app (proper_suffixes l) (duplications l d))).

(* Reading 9: the fallback past the last index is the specification's own
   chain, so a bounded quantifier one wider reaches a case that satisfies the
   obligation and the theorem fails rather than widening vacuously. *)
Definition consumer_weakening_at (n : nat) : list consumer_act :=
  at_member (all_weakenings spec_consumer_chain act_drain) n spec_consumer_chain.

Definition producer_weakening_at (n : nat) : list producer_act :=
  at_member (all_weakenings spec_producer_chain act_stage) n spec_producer_chain.

Example the_consumer_family_is_fifteen :
  count_of (all_weakenings spec_consumer_chain act_drain) = 15.
Proof. vm_compute; reflexivity. Qed.

Example the_producer_family_is_eleven :
  count_of (all_weakenings spec_producer_chain act_stage) = 11.
Proof. vm_compute; reflexivity. Qed.

(* Refused as one conversion. *)
Theorem every_consumer_weakening_is_refused :
  all_of (fun c => negb (consumer_chain_ok c))
         (all_weakenings spec_consumer_chain act_drain) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem every_producer_weakening_is_refused :
  all_of (fun c => negb (producer_chain_ok c))
         (all_weakenings spec_producer_chain act_stage) = true.
Proof. vm_compute; reflexivity. Qed.

(* And again per family, so that a family emptied by an edit says so where it
   is rather than one theorem later. *)
Theorem no_consumer_transposition_is_a_well_formed_chain :
  andb (Nat.eqb (count_of (transpositions spec_consumer_chain)) 3)
       (all_of (fun c => negb (consumer_chain_ok c))
               (transpositions spec_consumer_chain)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem no_consumer_deletion_is_a_well_formed_chain :
  andb (Nat.eqb (count_of (deletions spec_consumer_chain)) 4)
       (all_of (fun c => negb (consumer_chain_ok c))
               (deletions spec_consumer_chain)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem no_consumer_suffix_is_a_well_formed_chain :
  andb (Nat.eqb (count_of (proper_suffixes spec_consumer_chain)) 4)
       (all_of (fun c => negb (consumer_chain_ok c))
               (proper_suffixes spec_consumer_chain)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem no_duplicated_consumer_act_is_a_well_formed_chain :
  andb (Nat.eqb (count_of (duplications spec_consumer_chain act_drain)) 4)
       (all_of (fun c => negb (consumer_chain_ok c))
               (duplications spec_consumer_chain act_drain)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem no_producer_transposition_is_a_well_formed_chain :
  andb (Nat.eqb (count_of (transpositions spec_producer_chain)) 2)
       (all_of (fun c => negb (producer_chain_ok c))
               (transpositions spec_producer_chain)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem no_producer_deletion_is_a_well_formed_chain :
  andb (Nat.eqb (count_of (deletions spec_producer_chain)) 3)
       (all_of (fun c => negb (producer_chain_ok c))
               (deletions spec_producer_chain)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem no_producer_suffix_is_a_well_formed_chain :
  andb (Nat.eqb (count_of (proper_suffixes spec_producer_chain)) 3)
       (all_of (fun c => negb (producer_chain_ok c))
               (proper_suffixes spec_producer_chain)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem no_duplicated_producer_act_is_a_well_formed_chain :
  andb (Nat.eqb (count_of (duplications spec_producer_chain act_stage)) 3)
       (all_of (fun c => negb (producer_chain_ok c))
               (duplications spec_producer_chain act_stage)) = true.
Proof. vm_compute; reflexivity. Qed.

(* And again as a bounded quantifier over the index, whose bound decides
   something: one wider reaches the fallback, which is the specification. *)
Theorem every_consumer_weakening_is_refused_by_index :
  all_of (fun n => negb (consumer_chain_ok (consumer_weakening_at n))) (upto 15) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_consumer_index_bound_is_exact :
  all_of (fun n => negb (consumer_chain_ok (consumer_weakening_at n))) (upto 16) = false.
Proof. vm_compute; reflexivity. Qed.

Theorem every_producer_weakening_is_refused_by_index :
  all_of (fun n => negb (producer_chain_ok (producer_weakening_at n))) (upto 11) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_producer_index_bound_is_exact :
  all_of (fun n => negb (producer_chain_ok (producer_weakening_at n))) (upto 12) = false.
Proof. vm_compute; reflexivity. Qed.

(* Each transposition breaks exactly one conjunct and the specification breaks
   none, which is the check that no conjunct is dead. *)
Theorem each_consumer_transposition_breaks_exactly_one :
  all_of (fun c => Nat.eqb (consumer_broken c) 1)
         (transpositions spec_consumer_chain) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem each_duplicated_consumer_act_breaks_exactly_one :
  all_of (fun c => Nat.eqb (consumer_broken c) 1)
         (duplications spec_consumer_chain act_drain) = true.
Proof. vm_compute; reflexivity. Qed.

(* A producer that stages and neither releases nor signals. It is not in the
   generated family and it is what makes conjunct 1 a strict order: two acts
   that are both absent sit at one index, so a chain reading that order as
   *at or before* would admit this one. It breaks three conjuncts and not two. *)
Definition staging_only : list producer_act := cons act_stage nil.

Theorem a_producer_that_only_stages_breaks_the_order_and_both_counts :
  andb (Nat.eqb (producer_broken staging_only) 3)
       (negb (at_member producer_conjuncts 1 (fun _ => true) staging_only)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_consumer_order_is_strict_at_the_same_place :
  andb (Nat.eqb (consumer_broken (cons act_drain nil)) 5)
       (negb (at_member consumer_conjuncts 1 (fun _ => true)
                        (cons act_drain nil))) = true.
Proof. vm_compute; reflexivity. Qed.

(* The other two order conjuncts are strict for the same reason, and each is
   decided on the chain where the two acts it orders are both absent: a reading
   at or before would let two absent acts satisfy the order by sitting at one
   index, which is the index past the chain's own end. *)
Theorem the_drain_order_is_strict_at_its_own_boundary :
  andb (Nat.eqb (consumer_broken (suffix_at 2 spec_consumer_chain)) 4)
       (negb (at_member consumer_conjuncts 0 (fun _ => true)
                        (suffix_at 2 spec_consumer_chain))) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_release_order_is_strict_at_its_own_boundary :
  andb (Nat.eqb (producer_broken (suffix_at 2 spec_producer_chain)) 4)
       (negb (at_member producer_conjuncts 0 (fun _ => true)
                        (suffix_at 2 spec_producer_chain))) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem each_producer_transposition_breaks_exactly_one :
  all_of (fun c => Nat.eqb (producer_broken c) 1)
         (transpositions spec_producer_chain) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem each_duplicated_producer_act_breaks_exactly_one :
  all_of (fun c => Nat.eqb (producer_broken c) 1)
         (duplications spec_producer_chain act_stage) = true.
Proof. vm_compute; reflexivity. Qed.

(* Every conjunct is broken by some member of the two families, which is the
   other half of the same check: a conjunct nothing reaches decides nothing. *)
Theorem every_consumer_conjunct_is_reached :
  all_of (fun k => any_of (fun c => negb (at_member consumer_conjuncts k
                                                    (fun _ => true) c))
                          (all_weakenings spec_consumer_chain act_drain))
         (upto 7) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem every_producer_conjunct_is_reached :
  all_of (fun k => any_of (fun c => negb (at_member producer_conjuncts k
                                                    (fun _ => true) c))
                          (all_weakenings spec_producer_chain act_stage))
         (upto 5) = true.
Proof. vm_compute; reflexivity. Qed.

(* =========================================================================
   Part 3: the interleaved notification protocol (readings 5, 6 and 8 of
   gap h).

   The world is the view with the notification word and what one activation
   of the consumer has done. The producer acts at exactly one step of the
   consumer's chain, reads the armed word at that instant, and signals only
   if it is armed, which is the only predicate R-12-091's header gives it.
   ========================================================================= *)

Record world : Set := mk_world {
  w_view : ring_view;
  w_armed : bool;
  w_signals : nat;
  w_seen : nat;
  w_drained : nat;
  w_asleep : bool
}.

Definition w_pending (w : world) : nat := rv_occupancy (w_view w).

(* The producer's whole visible act: publish where the capacity admits it, and
   signal on the armed word. The reset owner is a declared field of the
   service (gap a), so it is a parameter here and not a choice. *)
Definition producer_publishes (r : reset_owner) (w : world) : world :=
  if Nat.ltb (w_pending w) ring_capacity
  then mk_world (mk_ring_view (S (rv_produced (w_view w))) (rv_consumed (w_view w)))
                (match r with
                 | reset_at_the_signal => false
                 | reset_at_the_drain => w_armed w
                 end)
                (w_signals w + (if w_armed w then 1 else 0))
                (w_seen w) (w_drained w) (w_asleep w)
  else w.

Definition consumer_steps (r : reset_owner) (b : nat) (a : consumer_act)
                          (w : world) : world :=
  match a with
  | act_drain =>
      mk_world (mk_ring_view (rv_produced (w_view w))
                             (rv_consumed (w_view w) + svc_least b (w_pending w)))
               (match r with
                | reset_at_the_drain => false
                | reset_at_the_signal => w_armed w
                end)
               (w_signals w) (rv_produced (w_view w))
               (w_drained w + svc_least b (w_pending w)) (w_asleep w)
  | act_arm =>
      mk_world (w_view w) true (w_signals w) (w_seen w) (w_drained w) (w_asleep w)
  | act_recheck =>
      mk_world (w_view w) (w_armed w) (w_signals w) (rv_produced (w_view w))
               (w_drained w) (w_asleep w)
  | act_sleep =>
      mk_world (w_view w) (w_armed w) (w_signals w) (w_seen w) (w_drained w)
               (andb (w_armed w) (Nat.eqb (w_seen w) (rv_consumed (w_view w))))
  end.

(* The producer acts at step p, where p is any step of the chain or the
   instant after its last act; a publication later than that is a publication
   into the next activation and is not this schedule. *)
Fixpoint run_with (r : reset_owner) (b : nat) (l : list consumer_act)
                  (t p : nat) (w : world) : world :=
  let w1 := if Nat.eqb t p then producer_publishes r w else w in
  match l with
  | nil => w1
  | cons a rest => run_with r b rest (S t) p (consumer_steps r b a w1)
  end.

Definition pub_step (l : list consumer_act) (p : nat) : nat :=
  if Nat.ltb p (count_of l) then p else count_of l.

Definition activation (r : reset_owner) (b : nat) (l : list consumer_act)
                      (p : nat) (w : world) : world :=
  run_with r b l 0 (pub_step l p) w.

Definition quiet_world : world := mk_world (mk_ring_view 0 0) false 0 0 0 false.

Definition armed_world : world := mk_world (mk_ring_view 0 0) true 0 0 0 true.

(* R-12-096's acceptance clause, as a property of a schedule: no execution
   leaves published work behind a consumer that is asleep and was never
   signalled. *)
Definition loses_a_wakeup (r : reset_owner) (b : nat) (l : list consumer_act)
                          (p : nat) : bool :=
  let z := activation r b l p quiet_world in
  andb (w_asleep z)
       (andb (Nat.ltb (rv_consumed (w_view z)) (rv_produced (w_view z)))
             (Nat.eqb (w_signals z) 0)).

(* The budget is the contract's own `ring_max_batch_size` instantiated and never
   a figure of this file: R-12-096's *admitted budget* is what R-12-098's batch
   declares and RingContract's `drain_is_bounded_by_the_batch` holds every
   variant's drain to. Writing the number here would be a second copy of a
   generated constant. *)
Definition ExcludesEveryLostWakeup (r : reset_owner) (l : list consumer_act) : Prop :=
  forall p : nat, loses_a_wakeup r ring_max_batch_size l p = false.

Theorem the_specification_chain_excludes_every_lost_wakeup :
  ExcludesEveryLostWakeup reset_at_the_signal spec_consumer_chain.
Proof.
  unfold ExcludesEveryLostWakeup. intro p.
  destruct p as [| [| [| [| k]]]]; vm_compute; reflexivity.
Qed.

(* The other reset arm excludes it too, which is what makes the choice a gap
   rather than a defect (gap a). *)
Theorem the_drain_reset_also_excludes_every_lost_wakeup :
  ExcludesEveryLostWakeup reset_at_the_drain spec_consumer_chain.
Proof.
  unfold ExcludesEveryLostWakeup. intro p.
  destruct p as [| [| [| [| k]]]]; vm_compute; reflexivity.
Qed.

(* The consumer that arms after rechecking, which is the transposition the
   generated family already refuses syntactically, refuted here on the
   interleaving it admits: the producer publishes between the read and the
   arm, finds the word unarmed, sends nothing, and the consumer sleeps. *)
Definition arm_after_recheck : list consumer_act := swap_at 1 spec_consumer_chain.

Theorem the_arm_after_the_recheck_loses_a_wakeup :
  ~ ExcludesEveryLostWakeup reset_at_the_signal arm_after_recheck.
Proof.
  unfold ExcludesEveryLostWakeup. intro H. specialize (H 2).
  vm_compute in H. discriminate H.
Qed.

(* And it keeps the obligations it does not break: it never consumes past what
   the producer published, and it takes no more than its budget. What refuses
   it is the order of its arm against its recheck and nothing else.

   Each is stated over an *arbitrary* publication step and not over a bounded
   index. `pub_step` clamps every step past the chain's last act onto that
   last act, so the schedules are finitely many, but a bounded index would be a
   bound no theorem decides anything at: unlike the weakening families, whose
   bound one wider reaches the specification and fails, a bound here could be
   raised without limit and still hold. *)
Theorem the_transposed_consumer_never_consumes_past_the_producer :
  forall p : nat,
    Nat.leb (rv_consumed (w_view (activation reset_at_the_signal ring_max_batch_size
                                    arm_after_recheck p quiet_world)))
            (rv_produced (w_view (activation reset_at_the_signal ring_max_batch_size
                                    arm_after_recheck p quiet_world))) = true.
Proof. intro p. destruct p as [| [| [| [| k]]]]; vm_compute; reflexivity. Qed.

Theorem the_transposed_consumer_stays_inside_its_budget :
  forall p : nat,
    Nat.leb (w_drained (activation reset_at_the_signal ring_max_batch_size
                          arm_after_recheck p quiet_world)) ring_max_batch_size = true.
Proof. intro p. destruct p as [| [| [| [| k]]]]; vm_compute; reflexivity. Qed.

(* The specification stays inside its budget too, which is the obligation the
   refutation above is *not* about. *)
Theorem the_specification_consumer_stays_inside_its_budget :
  forall p : nat,
    Nat.leb (w_drained (activation reset_at_the_signal ring_max_batch_size
                          spec_consumer_chain p quiet_world)) ring_max_batch_size = true.
Proof. intro p. destruct p as [| [| [| [| k]]]]; vm_compute; reflexivity. Qed.

(* A producer chain with the signal deleted, met from the semantic side: the
   consumer arms, rechecks an empty ring, sleeps, and nothing wakes it. *)
Definition producer_publishes_silently (w : world) : world :=
  if Nat.ltb (w_pending w) ring_capacity
  then mk_world (mk_ring_view (S (rv_produced (w_view w))) (rv_consumed (w_view w)))
                (w_armed w) (w_signals w) (w_seen w) (w_drained w) (w_asleep w)
  else w.

Definition silent_activation (b : nat) (l : list consumer_act) (w : world) : world :=
  producer_publishes_silently
    (run_with reset_at_the_signal b l 0 (S (count_of l)) w).

Theorem a_producer_that_never_signals_leaves_work_behind_a_sleep :
  let z := silent_activation ring_max_batch_size spec_consumer_chain quiet_world in
  andb (w_asleep z) (andb (Nat.ltb (rv_consumed (w_view z)) (rv_produced (w_view z)))
                          (Nat.eqb (w_signals z) 0)) = true.
Proof. vm_compute; reflexivity. Qed.

(* And the same schedule with a signalling producer wakes it, which is what
   makes the refutation the missing signal and not the schedule. *)
Theorem the_same_schedule_with_a_signal_wakes_the_consumer :
  let z := producer_publishes reset_at_the_signal
             (run_with reset_at_the_signal ring_max_batch_size spec_consumer_chain 0
                       (S (count_of spec_consumer_chain)) quiet_world) in
  andb (w_asleep z) (Nat.ltb 0 (w_signals z)) = true.
Proof. vm_compute; reflexivity. Qed.

(* And the silent producer keeps the obligation it does not break, stated of an
   arbitrary world rather than of the schedule above: its view moves exactly as
   the specification's does, so it still tests the capacity before reserving
   and R-12-095's overwrite is not what refuses it. What refuses it is the
   signal it never sends. *)
Lemma the_silent_publisher_moves_the_view_like_the_specification :
  forall w : world, w_view (producer_publishes_silently w) = rv_publish (w_view w).
Proof.
  intro w. unfold producer_publishes_silently, rv_publish, w_pending.
  destruct (Nat.ltb (rv_occupancy (w_view w)) ring_capacity); reflexivity.
Qed.

Theorem the_silent_publisher_keeps_the_capacity_bound :
  forall w : world,
    rv_ok (w_view w) = true -> rv_ok (w_view (producer_publishes_silently w)) = true.
Proof.
  intros w H.
  rewrite (the_silent_publisher_moves_the_view_like_the_specification w).
  exact (publish_keeps_the_invariant (w_view w) H).
Qed.

(* And it never overwrites at the boundary the bound is decided at: on a full
   ring it leaves the producer index exactly where it was. *)
Theorem the_silent_publisher_refuses_a_full_ring :
  Nat.eqb (rv_produced (w_view (producer_publishes_silently
                                  (mk_world full_view false 0 0 0 false))))
          ring_capacity = true.
Proof. vm_compute; reflexivity. Qed.

(* R-12-096's coalescing, and where the two reset arms differ. A burst is two
   publications with no drain between them: the signal reset sends one signal
   and the drain reset sends two, and R-12-101's declared maximum
   notifications is what refuses the second. *)
Definition burst (r : reset_owner) (w : world) : world :=
  producer_publishes r (producer_publishes r w).

Definition signals_in_a_burst (r : reset_owner) : nat :=
  w_signals (burst r armed_world).

Theorem the_signal_reset_coalesces_a_burst_to_one :
  Nat.eqb (signals_in_a_burst reset_at_the_signal) 1 = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_drain_reset_sends_two_signals_for_one_arming :
  Nat.eqb (signals_in_a_burst reset_at_the_drain) 2 = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_two_reset_arms_differ_only_on_the_second_publication :
  andb (Nat.eqb (w_signals (producer_publishes reset_at_the_signal armed_world))
                (w_signals (producer_publishes reset_at_the_drain armed_world)))
       (negb (Nat.eqb (signals_in_a_burst reset_at_the_signal)
                      (signals_in_a_burst reset_at_the_drain))) = true.
Proof. vm_compute; reflexivity. Qed.

(* Both bursts publish the same two items, so what separates the arms is the
   signal count and never the ring. *)
Theorem the_two_bursts_publish_the_same_two_items :
  Nat.eqb (rv_produced (w_view (burst reset_at_the_signal armed_world)))
          (rv_produced (w_view (burst reset_at_the_drain armed_world))) = true.
Proof. vm_compute; reflexivity. Qed.

(* R-12-096's "the indices are the source of truth", refutably: a sleep
   decision is a function of what the consumer has seen against what it has
   consumed, and never of a count of notifications. *)
Definition NeverSleepsOverASeenGap (decide : world -> bool) : Prop :=
  forall w : world,
    decide w = true -> Nat.eqb (w_seen w) (rv_consumed (w_view w)) = true.

Definition spec_sleep_rule (w : world) : bool :=
  andb (w_armed w) (Nat.eqb (w_seen w) (rv_consumed (w_view w))).

(* The consumer R-12-096's "no notification counter exists" excludes: one that
   sleeps when its count of signals is spent, whatever the indices say. *)
Definition counting_sleep_rule (w : world) : bool := Nat.eqb (w_signals w) 0.

(* The world a coalesced burst leaves the consumer in: two items published,
   one signal sent and already consumed, and a recheck that has seen both. *)
Definition after_a_coalesced_burst : world :=
  mk_world (w_view (burst reset_at_the_signal armed_world)) true 0
           (rv_produced (w_view (burst reset_at_the_signal armed_world))) 0 false.

Definition after_the_signal_arrived : world :=
  mk_world (mk_ring_view 2 0) true 1 2 0 false.

Theorem the_specification_sleep_rule_reads_the_indices :
  NeverSleepsOverASeenGap spec_sleep_rule.
Proof.
  unfold NeverSleepsOverASeenGap. intros w H. unfold spec_sleep_rule in H.
  destruct (andb_split _ _ H) as [ _ Hs ]. exact Hs.
Qed.

(* And this rule is the contract's own `sleeps` read at the wire, which is the
   other half of the same bridge: RingContract states R-12-096's decision rule
   over two reads of the producer index and this file states the interleaving,
   so the two must be the one rule. Over every base the span carries and every
   gap the capacity admits, an armed word with an empty recheck is the
   contract's answer and this file's alike. `sleeps` ignores the index the
   drain ended on, so the drained argument is passed the consumed index and
   decides nothing, which is the entry's own sentence. *)
Theorem the_specification_sleep_rule_is_the_contracts :
  all_of (fun c =>
            all_of (fun d =>
                      all_of (fun a =>
                                agree (andb a (Nat.eqb d 0))
                                      (sleeps (rv_wire c) (rv_wire (c + d))
                                              (rv_wire c) a))
                             (cons true (cons false nil)))
                   (upto (S ring_capacity)))
         (upto ring_index_span) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_counting_sleep_rule_is_refuted :
  ~ NeverSleepsOverASeenGap counting_sleep_rule.
Proof.
  unfold NeverSleepsOverASeenGap. intro H.
  specialize (H after_a_coalesced_burst).
  vm_compute in H. discriminate (H eq_refl).
Qed.

(* And the counting rule keeps what it is not refuted for: it still declines
   to sleep once a signal has arrived, which is the obligation the coalescing
   defect is not about. *)
Theorem the_counting_sleep_rule_declines_after_a_signal :
  counting_sleep_rule after_the_signal_arrived = false.
Proof. vm_compute; reflexivity. Qed.

(* The two rules on one burst, which is the observable difference: the
   coalesced burst leaves two items pending with one signal spent. *)
Theorem the_counting_rule_and_the_index_rule_differ_on_a_coalesced_burst :
  andb (counting_sleep_rule after_a_coalesced_burst)
       (negb (spec_sleep_rule after_a_coalesced_burst)) = true.
Proof. vm_compute; reflexivity. Qed.

(* R-07-029a is what a sleep here is: the poll-site yield of R-07-037b, a
   synchronous invocation that returns, and nowhere a block. Stated as a
   property of an activation rather than as a sentence: the activation is a
   finite fold over a finite chain and its cost is bounded by the chain's
   length, so it has a WCET for R-11-006's admission to read. A construction
   that waits has none, and the way it is refuted is that no fold over a
   finite list can express it: what stands in for it is a consumer whose
   drain is unbounded, and the bound below is what refuses that. *)
Definition ActivationIsBounded (b : nat) (l : list consumer_act) : Prop :=
  forall p : nat,
    Nat.leb (w_drained (activation reset_at_the_signal b l p quiet_world)) b = true.

Theorem the_specification_activation_is_bounded :
  ActivationIsBounded ring_max_batch_size spec_consumer_chain.
Proof.
  unfold ActivationIsBounded. intro p.
  destruct p as [| [| [| [| k]]]]; vm_compute; reflexivity.
Qed.

(* The unbounded drain: a consumer that takes whatever is pending rather than
   what its budget admits, which is the shape a blocking wait would take here
   and is refused at the same place. *)
Definition greedy_consumer_steps (b : nat) (a : consumer_act) (w : world) : world :=
  match a with
  | act_drain =>
      mk_world (mk_ring_view (rv_produced (w_view w)) (rv_produced (w_view w)))
               (w_armed w) (w_signals w) (rv_produced (w_view w))
               (w_drained w + w_pending w) (w_asleep w)
  | _ => consumer_steps reset_at_the_signal b a w
  end.

Definition all_consumer_acts : list consumer_act :=
  cons act_drain (cons act_arm (cons act_recheck (cons act_sleep nil))).

Definition world_eqb (a b : world) : bool :=
  andb (Nat.eqb (rv_produced (w_view a)) (rv_produced (w_view b)))
  (andb (Nat.eqb (rv_consumed (w_view a)) (rv_consumed (w_view b)))
  (andb (agree (w_armed a) (w_armed b))
  (andb (Nat.eqb (w_signals a) (w_signals b))
  (andb (Nat.eqb (w_seen a) (w_seen b))
  (andb (Nat.eqb (w_drained a) (w_drained b))
        (agree (w_asleep a) (w_asleep b))))))).

Lemma world_eqb_refl : forall w : world, world_eqb w w = true.
Proof.
  intro w. unfold world_eqb, agree.
  apply andb_join; [ apply eqb_reflexive | ].
  apply andb_join; [ apply eqb_reflexive | ].
  apply andb_join; [ destruct (w_armed w); reflexivity | ].
  apply andb_join; [ apply eqb_reflexive | ].
  apply andb_join; [ apply eqb_reflexive | ].
  apply andb_join; [ apply eqb_reflexive | ].
  destruct (w_asleep w); reflexivity.
Qed.

(* A backlog past one budget, which is the boundary the bound is decided at. *)
Definition backlogged_world : world :=
  mk_world (mk_ring_view 20 0) false 0 0 0 false.

Theorem the_greedy_consumer_leaves_its_budget :
  Nat.leb (w_drained (greedy_consumer_steps ring_max_batch_size act_drain
                                            backlogged_world)) ring_max_batch_size
  = false.
Proof. vm_compute; reflexivity. Qed.

Theorem the_specification_consumer_stops_at_its_budget :
  Nat.eqb (w_drained (consumer_steps reset_at_the_signal ring_max_batch_size act_drain
                                     backlogged_world)) ring_max_batch_size = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_greedy_consumer_still_drains_what_it_saw :
  Nat.eqb (rv_consumed (w_view (greedy_consumer_steps ring_max_batch_size act_drain
                                                      backlogged_world)))
          (rv_produced (w_view backlogged_world)) = true.
Proof. vm_compute; reflexivity. Qed.

(* And the two consumers agree at every act but the drain, so what refuses the
   greedy one is the budget it does not read and not a second difference. *)
Theorem the_two_consumers_differ_only_at_the_drain :
  all_of (fun a => agree (negb (consumer_act_eqb a act_drain))
                         (world_eqb (greedy_consumer_steps ring_max_batch_size a
                                                           backlogged_world)
                                    (consumer_steps reset_at_the_signal
                                                    ring_max_batch_size a
                                                    backlogged_world)))
         all_consumer_acts = true.
Proof. vm_compute; reflexivity. Qed.

(* =========================================================================
   Part 4: R-12-008a's ownership phases, and R-12-094's lifecycle over one
   request slot (reading of gap g).

   The four phases and the six states are carried apart and neither is stated
   as a function of the other, because R-12-094's acceptance clause says the
   lifecycle refines those transitions and gives no map.
   ========================================================================= *)

Definition ownership_next (o : ownership) : ownership :=
  match o with
  | own_producer_writable => own_published
  | own_published => own_consumer_acquired
  | own_consumer_acquired => own_returned
  | own_returned => own_producer_writable
  end.

Definition producer_may_write (o : ownership) : bool :=
  match o with
  | own_producer_writable => true
  | own_published => false
  | own_consumer_acquired => false
  | own_returned => true
  end.

Definition consumer_may_read (o : ownership) : bool :=
  match o with
  | own_producer_writable => false
  | own_published => false
  | own_consumer_acquired => true
  | own_returned => false
  end.

(* R-12-008a's three rejected paths, decided over the phase a construction
   acts in rather than named as absences. *)
Definition breaks_ownership (d : ownership_defect) (o : ownership) : bool :=
  match d with
  | reads_before_acquire => andb (consumer_may_read (ownership_next o))
                                 (negb (consumer_may_read o))
  | writes_after_publication => negb (producer_may_write o)
  | restores_under_a_reader => consumer_may_read o
  end.

Theorem no_phase_is_both_producer_writable_and_consumer_readable :
  all_of (fun o => negb (andb (producer_may_write o) (consumer_may_read o)))
         all_ownership_phases = true.
Proof. vm_compute; reflexivity. Qed.

Theorem exactly_one_phase_admits_the_consumer :
  Nat.eqb (count_of (filter_of consumer_may_read all_ownership_phases)) 1 = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_publication_consumes_writable_ownership :
  andb (producer_may_write own_producer_writable)
       (negb (producer_may_write (ownership_next own_producer_writable))) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem each_rejected_path_is_broken_somewhere :
  all_of (fun d => any_of (breaks_ownership d) all_ownership_phases)
         all_rejected_paths = true.
Proof. vm_compute; reflexivity. Qed.

(* And each is broken at the phase its own name points at and not at another,
   so the three predicates are three and not one predicate spelled three ways.
   Each pair is a phase the path is at and a phase it is not. *)
Theorem each_rejected_path_is_at_the_phase_that_names_it :
  andb (andb (breaks_ownership reads_before_acquire own_published)
             (negb (breaks_ownership reads_before_acquire own_consumer_acquired)))
       (andb (andb (breaks_ownership writes_after_publication own_published)
                   (negb (breaks_ownership writes_after_publication
                                           own_producer_writable)))
             (andb (breaks_ownership restores_under_a_reader own_consumer_acquired)
                   (negb (breaks_ownership restores_under_a_reader own_returned))))
  = true.
Proof. vm_compute; reflexivity. Qed.

(* One request slot, and what a service's own acts do to it. *)
Record slot : Set := mk_slot {
  sl_state : slot_state;
  sl_readers : nat;
  sl_validated : bool;
  sl_request : nat
}.

Definition Advancer : Type := service_event -> slot -> option slot.

Definition with_state (s : slot) (t : slot_state) : slot :=
  mk_slot t (sl_readers s) (sl_validated s) (sl_request s).

(* The setter moves one field of an arbitrary slot and nothing else, which is
   what makes every advancer below decidable on the state alone: a step that
   moved a reader count or a request identifier would be a different act. *)
Theorem the_state_setter_moves_only_the_state :
  forall (z : slot) (t : slot_state),
    andb (Nat.eqb (sl_request (with_state z t)) (sl_request z))
         (andb (Nat.eqb (sl_readers (with_state z t)) (sl_readers z))
               (agree (sl_validated (with_state z t)) (sl_validated z))) = true.
Proof.
  intros z t. apply andb_join; [ apply eqb_reflexive | ].
  apply andb_join; [ apply eqb_reflexive | ].
  unfold with_state, agree. destruct (sl_validated z); reflexivity.
Qed.

(* The specification's advancer. Every step is the contract's own successor
   except the malformed one, which is the contract's own second relation;
   acceptance requires validation (R-12-092 and R-12-094's acceptance clause)
   and reclamation requires no outstanding reader (R-12-094's own sentence). *)
Definition spec_advance : Advancer := fun e s =>
  match e, sl_state s with
  | ev_reserve, state_Free =>
      match lifecycle_next state_Free with
      | Some t => Some (with_state s t)
      | None => None
      end
  | ev_publish, state_Writing =>
      match lifecycle_next state_Writing with
      | Some t => Some (with_state s t)
      | None => None
      end
  | ev_accept, state_Submitted =>
      if sl_validated s
      then match lifecycle_next state_Submitted with
           | Some t => Some (with_state s t)
           | None => None
           end
      else None
  | ev_complete, state_Accepted =>
      match lifecycle_next state_Accepted with
      | Some t => Some (with_state s t)
      | None => None
      end
  | ev_reclaim, state_Terminal =>
      if Nat.eqb (sl_readers s) 0
      then match lifecycle_next state_Terminal with
           | Some t => Some (with_state s t)
           | None => None
           end
      else None
  | ev_malformed, state_Submitted =>
      match lifecycle_malformed state_Submitted with
      | Some t => Some (with_state s t)
      | None => None
      end
  | _, _ => None
  end.

(* The witnesses every advancer below is decided over: one slot per state,
   with a reader outstanding and without, and validated and not. *)
Definition slot_at (t : slot_state) : slot := mk_slot t 0 true 7.
Definition held_slot (t : slot_state) : slot := mk_slot t 1 true 7.
Definition unvalidated_slot (t : slot_state) : slot := mk_slot t 0 false 7.

Definition demo_slot : slot := slot_at state_Submitted.
Definition held_terminal_slot : slot := held_slot state_Terminal.
Definition unvalidated_submitted_slot : slot := unvalidated_slot state_Submitted.

Definition all_slots : list slot :=
  app (map_over slot_at all_slot_states)
      (app (map_over held_slot all_slot_states)
           (map_over unvalidated_slot all_slot_states)).

(* The rank is injective over the six states, so comparing two ranks is
   comparing two states and the readings below decide state equality rather
   than an arithmetic coincidence. *)
Definition state_eqb (a b : slot_state) : bool :=
  Nat.eqb (lifecycle_rank a) (lifecycle_rank b).

Example the_lifecycle_rank_separates_the_six_states :
  all_of (fun t => Nat.eqb (count_of (filter_of (state_eqb t) all_slot_states)) 1)
         all_slot_states = true.
Proof. vm_compute; reflexivity. Qed.

(* A step is the contract's own successor or the contract's own malformed step
   *at the state that licenses it*. R-12-094 puts the malformed step from
   Submitted to Terminal and nowhere else, and `lifecycle_malformed` answers
   `None` at the other five, so the reading is the contract's two relations
   read as relations and never a rank arithmetic that happens to agree with
   them at one state. *)
Definition contract_step_ok (s z : slot_state) : bool :=
  orb (match lifecycle_next s with
       | Some t => state_eqb z t
       | None => false
       end)
      (match lifecycle_malformed s with
       | Some t => state_eqb z t
       | None => false
       end).

(* Every step an advancer takes is the contract's successor or its one
   malformed step, decided over every event and every slot. *)
Definition step_is_lawful (f : Advancer) : bool :=
  all_of (fun e =>
            all_of (fun s =>
                      match f e s with
                      | None => true
                      | Some z => contract_step_ok (sl_state s) (sl_state z)
                      end)
                   all_slots)
         all_events.

(* The reading this replaced, kept as a construction so that what the repair
   buys is machine-checked rather than asserted: a step whose rank is its
   predecessor's plus one or plus two, which is `lifecycle_malformed_ok`'s
   arithmetic read as a licence at every state instead of at the one state
   that carries the relation. *)
Definition rank_only_step_is_lawful (f : Advancer) : bool :=
  all_of (fun e =>
            all_of (fun s =>
                      match f e s with
                      | None => true
                      | Some z =>
                          orb (Nat.eqb (lifecycle_rank (sl_state z))
                                       (S (lifecycle_rank (sl_state s))))
                              (Nat.eqb (lifecycle_rank (sl_state z))
                                       (2 + lifecycle_rank (sl_state s)))
                      end)
                   all_slots)
         all_events.

Definition never_reclaims_under_a_reader (f : Advancer) : bool :=
  all_of (fun s => match f ev_reclaim s with
                   | None => true
                   | Some _ => Nat.eqb (sl_readers s) 0
                   end)
         all_slots.

Definition never_accepts_before_validation (f : Advancer) : bool :=
  all_of (fun s => match f ev_accept s with
                   | None => true
                   | Some _ => sl_validated s
                   end)
         all_slots.

Definition advancer_obligations : list (Advancer -> bool) :=
  cons step_is_lawful
  (cons never_reclaims_under_a_reader (cons never_accepts_before_validation nil)).

Definition advancer_ok (f : Advancer) : bool :=
  all_of (fun p => p f) advancer_obligations.

Definition advancer_broken (f : Advancer) : nat :=
  count_of (filter_of (fun p => negb (p f)) advancer_obligations).

Example there_are_three_advancer_obligations :
  count_of advancer_obligations = 3.
Proof. reflexivity. Qed.

Theorem the_specification_advancer_keeps_every_obligation :
  andb (advancer_ok spec_advance) (Nat.eqb (advancer_broken spec_advance) 0) = true.
Proof. vm_compute; reflexivity. Qed.

(* The advancer that reclaims a slot straight back to Free, which is the
   lifecycle read as a cycle rather than as R-12-094's monotone sequence. *)
Definition advance_backwards : Advancer := fun e s =>
  match e, sl_state s with
  | ev_reclaim, state_Terminal =>
      if Nat.eqb (sl_readers s) 0 then Some (with_state s state_Free) else None
  | _, _ => spec_advance e s
  end.

(* The advancer that accepts a request that has not been validated, which is
   R-12-094's fourth rejected path. *)
Definition advance_unvalidated : Advancer := fun e s =>
  match e, sl_state s with
  | ev_accept, state_Submitted =>
      match lifecycle_next state_Submitted with
      | Some t => Some (with_state s t)
      | None => None
      end
  | _, _ => spec_advance e s
  end.

(* The advancer that reclaims with a reader still outstanding, which is
   R-12-008a's third rejected path met at the lifecycle. *)
Definition advance_under_a_reader : Advancer := fun e s =>
  match e, sl_state s with
  | ev_reclaim, state_Terminal =>
      match lifecycle_next state_Terminal with
      | Some t => Some (with_state s t)
      | None => None
      end
  | _, _ => spec_advance e s
  end.

(* The advancer that takes the malformed step's *shape* at a state the contract
   does not license it at: reservation carries a Free slot straight to
   Submitted, skipping Writing. R-12-094 puts the one malformed step from
   Submitted to Terminal, so this is a second skip and not that one, and it is
   the construction a rank-only reading of lawfulness admits. *)
Definition advance_skipping : Advancer := fun e s =>
  match e, sl_state s with
  | ev_reserve, state_Free => Some (with_state s state_Submitted)
  | _, _ => spec_advance e s
  end.

Definition all_refuting_advancers : list Advancer :=
  cons advance_backwards
  (cons advance_unvalidated
  (cons advance_under_a_reader (cons advance_skipping nil))).

Theorem no_refuting_advancer_keeps_every_obligation :
  all_of (fun f => negb (advancer_ok f)) all_refuting_advancers = true.
Proof. vm_compute; reflexivity. Qed.

Theorem each_refuting_advancer_breaks_exactly_one :
  all_of (fun f => Nat.eqb (advancer_broken f) 1) all_refuting_advancers = true.
Proof. vm_compute; reflexivity. Qed.

(* And each breaks the one it is named for, which is what makes the refutation
   the named defect rather than its shape. *)
Theorem the_backward_advancer_breaks_the_lifecycle_alone :
  andb (negb (step_is_lawful advance_backwards))
       (andb (never_reclaims_under_a_reader advance_backwards)
             (never_accepts_before_validation advance_backwards)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_unvalidated_advancer_breaks_the_validation_alone :
  andb (negb (never_accepts_before_validation advance_unvalidated))
       (andb (step_is_lawful advance_unvalidated)
             (never_reclaims_under_a_reader advance_unvalidated)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_reader_advancer_breaks_the_reclamation_alone :
  andb (negb (never_reclaims_under_a_reader advance_under_a_reader))
       (andb (step_is_lawful advance_under_a_reader)
             (never_accepts_before_validation advance_under_a_reader)) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_skipping_advancer_breaks_the_lifecycle_alone :
  andb (negb (step_is_lawful advance_skipping))
       (andb (never_reclaims_under_a_reader advance_skipping)
             (never_accepts_before_validation advance_skipping)) = true.
Proof. vm_compute; reflexivity. Qed.

(* And this is what the repaired reading buys, stated rather than asserted: the
   rank-only reading admits the skipping advancer and the contract's own two
   relations refuse it. A lawfulness conjunct written as *one more or two more*
   licenses a skip at every state, where R-12-094 licenses exactly one, from
   Submitted. *)
Theorem the_rank_only_reading_admits_the_skipping_advancer :
  andb (rank_only_step_is_lawful advance_skipping)
       (negb (step_is_lawful advance_skipping)) = true.
Proof. vm_compute; reflexivity. Qed.

(* The two readings agree on the specification and on the other three
   refuters, so what separates them is the skip alone. *)
Theorem the_two_lawfulness_readings_agree_on_everything_else :
  all_of (fun f => agree (rank_only_step_is_lawful f) (step_is_lawful f))
         (cons spec_advance
         (cons advance_backwards
         (cons advance_unvalidated (cons advance_under_a_reader nil)))) = true.
Proof. vm_compute; reflexivity. Qed.

(* And the licensed skip is still licensed: the contract's own malformed step
   is lawful under the repaired reading, so the repair excludes the second skip
   and not the first. *)
Theorem the_licensed_malformed_step_is_still_lawful :
  andb (contract_step_ok state_Submitted state_Terminal)
       (negb (contract_step_ok state_Free state_Submitted)) = true.
Proof. vm_compute; reflexivity. Qed.

(* The malformed step is the one admitted step past a successor, and it
   acquires no authority: the contract's own second relation, instantiated
   here at the service's own event. *)
Theorem the_malformed_event_takes_the_contracts_own_step :
  match spec_advance ev_malformed (slot_at state_Submitted) with
  | Some z => Nat.eqb (lifecycle_rank (sl_state z))
                      (2 + lifecycle_rank state_Submitted)
  | None => false
  end = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_malformed_event_is_admitted_at_one_state_only :
  Nat.eqb (count_of (filter_of (fun s => match spec_advance ev_malformed s with
                                         | Some _ => true
                                         | None => false
                                         end)
                               (map_over slot_at all_slot_states))) 1 = true.
Proof. vm_compute; reflexivity. Qed.

(* =========================================================================
   Part 5: the copy itself (reading 8, gaps i and j).

   A delegated buffer is the client's own memory and the client is a
   Byzantine peer under R-12-008a's own posture, so the buffer has two images
   and a service that reads it twice has validated one and copied the other.
   ========================================================================= *)

Record buffer : Set := mk_buffer {
  buf_length : nat;
  buf_datum : nat
}.

Record copy_run : Set := mk_copy_run {
  cr_reads : nat;
  cr_staged : nat;
  cr_bytes : nat
}.

Definition Copier : Type := nat -> buffer -> buffer -> option copy_run.

(* The two images the refutation turns on: the client's buffer as the
   validation read it, and as it stands when a second read would happen. Only
   the length moves, so what a refutation isolates is the field the validation
   read and not the payload. *)
Definition first_image : buffer := mk_buffer 4 7.
Definition second_image : buffer := mk_buffer 9 7.
Definition declared_extent : nat := 4.
Definition staged_run : copy_run := mk_copy_run 1 7 4.
Definition revalidated_run : copy_run := mk_copy_run 2 7 9.

(* R-05-124's copy-once, read at a service: one read of the source decides the
   validation and supplies the payload, and everything downstream reads the
   staged copy. *)
Definition copy_once : Copier := fun declared before _ =>
  if Nat.leb (buf_length before) declared
  then Some (mk_copy_run 1 (buf_datum before) (buf_length before))
  else None.

(* The service gap j names: one that validates the length it first read and
   then reads the source again to do the copy. *)
Definition copy_revalidating : Copier := fun declared before after =>
  if Nat.leb (buf_length before) declared
  then Some (mk_copy_run 2 (buf_datum after) (buf_length after))
  else None.

Definition StaysInsideTheValidatedExtent (f : Copier) : Prop :=
  forall (d : nat) (b a : buffer) (r : copy_run),
    f d b a = Some r -> Nat.leb (cr_bytes r) d = true.

Definition ReadsTheSourceOnce (f : Copier) : Prop :=
  forall (d : nat) (b a : buffer) (r : copy_run),
    f d b a = Some r -> Nat.eqb (cr_reads r) 1 = true.

Definition DoesNotVaryWithTheSecondImage (f : Copier) : Prop :=
  forall (d : nat) (b a1 a2 : buffer), f d b a1 = f d b a2.

Definition RefusesAnOverlongLength (f : Copier) : Prop :=
  forall (d : nat) (b a : buffer),
    Nat.leb (buf_length b) d = false -> f d b a = None.

Theorem the_copy_once_service_stays_inside_the_validated_extent :
  StaysInsideTheValidatedExtent copy_once.
Proof.
  unfold StaysInsideTheValidatedExtent. intros d b a r H. unfold copy_once in H.
  destruct (Nat.leb (buf_length b) d) eqn:E.
  - injection H as H. rewrite <- H. exact E.
  - discriminate H.
Qed.

Theorem the_copy_once_service_reads_the_source_once : ReadsTheSourceOnce copy_once.
Proof.
  unfold ReadsTheSourceOnce. intros d b a r H. unfold copy_once in H.
  destruct (Nat.leb (buf_length b) d) eqn:E.
  - injection H as H. rewrite <- H. reflexivity.
  - discriminate H.
Qed.

Theorem the_copy_once_service_does_not_vary_with_the_second_image :
  DoesNotVaryWithTheSecondImage copy_once.
Proof. unfold DoesNotVaryWithTheSecondImage. intros d b a1 a2. reflexivity. Qed.

Theorem the_copy_once_service_refuses_an_overlong_length :
  RefusesAnOverlongLength copy_once.
Proof.
  unfold RefusesAnOverlongLength. intros d b a H. unfold copy_once.
  rewrite H. reflexivity.
Qed.

(* The revalidating copier is refuted at all three obligations copy-once is
   for, and it keeps the fourth, which is the fail-closed refusal: what
   refuses it is the second read and not a failure to check anything. *)
Lemma the_revalidating_copier_answers_on_the_two_images :
  copy_revalidating declared_extent first_image second_image = Some revalidated_run.
Proof. vm_compute; reflexivity. Qed.

Theorem the_revalidating_copier_leaves_the_validated_extent :
  ~ StaysInsideTheValidatedExtent copy_revalidating.
Proof.
  unfold StaysInsideTheValidatedExtent. intro H.
  specialize (H declared_extent first_image second_image revalidated_run
                the_revalidating_copier_answers_on_the_two_images).
  vm_compute in H. discriminate H.
Qed.

Theorem the_revalidating_copier_reads_the_source_twice :
  ~ ReadsTheSourceOnce copy_revalidating.
Proof.
  unfold ReadsTheSourceOnce. intro H.
  specialize (H declared_extent first_image second_image revalidated_run
                the_revalidating_copier_answers_on_the_two_images).
  vm_compute in H. discriminate H.
Qed.

Theorem the_revalidating_copier_varies_with_the_second_image :
  ~ DoesNotVaryWithTheSecondImage copy_revalidating.
Proof.
  unfold DoesNotVaryWithTheSecondImage. intro H.
  specialize (H declared_extent first_image first_image second_image).
  vm_compute in H. discriminate H.
Qed.

Theorem the_revalidating_copier_still_refuses_an_overlong_length :
  RefusesAnOverlongLength copy_revalidating.
Proof.
  unfold RefusesAnOverlongLength. intros d b a H. unfold copy_revalidating.
  rewrite H. reflexivity.
Qed.

(* The two images the refutation turns on, pinned so that the difference is
   the length and never the datum: a reader can see that what moved is the
   field the validation read. *)
Example the_two_buffer_images_differ_only_in_their_length :
  andb (Nat.eqb (buf_datum first_image) (buf_datum second_image))
       (negb (Nat.eqb (buf_length first_image) (buf_length second_image))) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_copy_once_run_is_the_one_the_specification_answers :
  match copy_once declared_extent first_image second_image with
  | Some r => andb (Nat.eqb (cr_reads r) (cr_reads staged_run))
                   (andb (Nat.eqb (cr_bytes r) (cr_bytes staged_run))
                         (Nat.eqb (cr_staged r) (cr_staged staged_run)))
  | None => false
  end = true.
Proof. vm_compute; reflexivity. Qed.

Example the_revalidated_run_is_the_one_the_refuter_answers :
  match copy_revalidating declared_extent first_image second_image with
  | Some r => andb (Nat.eqb (cr_reads r) (cr_reads revalidated_run))
                   (andb (Nat.eqb (cr_bytes r) (cr_bytes revalidated_run))
                         (Nat.eqb (cr_staged r) (cr_staged revalidated_run)))
  | None => false
  end = true.
Proof. vm_compute; reflexivity. Qed.

(* And the copy is charged at the declared maximum rather than at what
   arrived, which is what gives R-11-006's admission a bound to read: the cost
   is a function of the declared segment count and segment size alone. *)
Definition declared_copy_cost (segments : nat) : nat := segments * ring_segment_max_bytes.

Definition actual_copy_cost (r : copy_run) : nat := cr_bytes r.

Definition CostIsIndependentOfTheArrival (cost : nat -> copy_run -> nat) : Prop :=
  forall (segments : nat) (r1 r2 : copy_run),
    cost segments r1 = cost segments r2.

Definition charged_at_the_maximum (segments : nat) (_ : copy_run) : nat :=
  declared_copy_cost segments.

Definition charged_at_the_arrival (_ : nat) (r : copy_run) : nat :=
  actual_copy_cost r.

Theorem charging_at_the_maximum_is_independent_of_the_arrival :
  CostIsIndependentOfTheArrival charged_at_the_maximum.
Proof.
  unfold CostIsIndependentOfTheArrival. intros segments r1 r2. reflexivity.
Qed.

Theorem charging_at_the_arrival_is_refuted :
  ~ CostIsIndependentOfTheArrival charged_at_the_arrival.
Proof.
  unfold CostIsIndependentOfTheArrival. intro H.
  specialize (H ring_max_segments staged_run revalidated_run).
  vm_compute in H. discriminate H.
Qed.

(* The arrival charging keeps the obligation it is not aimed at: it still
   bounds a run that stayed inside its declared extent. *)
Theorem charging_at_the_arrival_still_bounds_a_run_inside_its_extent :
  Nat.leb (charged_at_the_arrival ring_max_segments staged_run)
          (declared_copy_cost ring_max_segments) = true.
Proof. vm_compute; reflexivity. Qed.

(* =========================================================================
   Part 6: the batch (R-12-098).

   A batch is an amortization unit and never a transaction, so the results of
   the members already enqueued do not move when a later one is refused.
   ========================================================================= *)

Fixpoint submit_batch (n : nat) (v : ring_view) : list submit_result :=
  match n with
  | 0 => nil
  | S k => cons (service_submit v) (submit_batch k (rv_publish v))
  end.

(* The transactional batch R-12-098 forbids: one refused member converts every
   member's result into a refusal. *)
Definition transactional_batch (n : nat) (v : ring_view) : list submit_result :=
  if any_of (fun r => match r with
                      | submit_would_block => true
                      | submit_enqueued => false
                      end)
            (submit_batch n v)
  then map_over (fun _ => submit_would_block) (submit_batch n v)
  else submit_batch n v.

(* Two views: one with room for the whole batch and one with room for three of
   five, which is the boundary the two disciplines differ at. *)
Definition roomy_view : ring_view := mk_ring_view 0 0.
Definition crowded_view : ring_view :=
  mk_ring_view (Nat.pred (Nat.pred (Nat.pred ring_capacity))) 0.

Definition enqueued_count (l : list submit_result) : nat :=
  count_of (filter_of (fun r => match r with
                                | submit_enqueued => true
                                | submit_would_block => false
                                end) l).

Theorem the_batch_admits_what_the_ring_holds_and_refuses_the_rest :
  andb (Nat.eqb (enqueued_count (submit_batch 5 crowded_view)) 3)
       (Nat.eqb (enqueued_count (submit_batch 5 roomy_view)) 5) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_transactional_batch_rolls_back_what_it_enqueued :
  andb (Nat.eqb (enqueued_count (transactional_batch 5 crowded_view)) 0)
       (Nat.eqb (enqueued_count (submit_batch 5 crowded_view)) 3) = true.
Proof. vm_compute; reflexivity. Qed.

(* And the transactional batch keeps the obligation it is not aimed at: where
   nothing is refused, the two disciplines agree exactly. *)
Theorem the_two_batches_agree_where_nothing_is_refused :
  Nat.eqb (enqueued_count (transactional_batch 5 roomy_view))
          (enqueued_count (submit_batch 5 roomy_view)) = true.
Proof. vm_compute; reflexivity. Qed.

(* A batch's publication is bounded by the declared maximum batch size, which
   is the contract's own constant and never a figure of this file. *)
Theorem a_batch_is_bounded_by_the_declared_maximum :
  Nat.eqb (enqueued_count (submit_batch ring_max_batch_size roomy_view))
          ring_max_batch_size = true.
Proof. vm_compute; reflexivity. Qed.

(* =========================================================================
   Part 7: the service declaration, and section 6's admission rule over it.

   No service is grandfathered: one that cannot state its finite capacities,
   its lifecycle semantics, its cleanup bounds and its per-operation WCET is
   not admitted through the ring profile. That is the milestone's own rule and
   it is stated here as thirteen conjuncts over a declaration, decided from
   the declaration side by a one-field spoiling and from the filter side by a
   dropped conjunct.
   ========================================================================= *)

Record svc_capacities : Set := mk_svc_capacities {
  cap_accepted : nat;
  cap_accepted_slack : nat;
  cap_ring_slack : nat;
  cap_batch : nat;
  cap_batch_slack : nat
}.

Record svc_op_record : Set := mk_svc_op_record {
  so_segments : nat;
  so_segment_slack : nat;
  so_staging : nat;
  so_staging_slack : nat;
  so_cleanup : nat;
  so_cleanup_slack : nat;
  so_released : nat;
  so_validation : nat;
  so_service : nat;
  so_publication : nat;
  so_latency : nat;
  so_progress_slack : nat;
  so_progress_bound : nat
}.

Record Service : Set := mk_service {
  svc_caps : svc_capacities;
  svc_per_op : op -> svc_op_record;
  svc_live : slot_state -> bool;
  svc_reset : reset_owner;
  svc_counter : bool;
  svc_cadence : nat;
  svc_accounting : accounting;
  svc_charges_at_the_maximum : bool;
  svc_identity : nat
}.

(* How many activations of a drain bounded by `b` empty a full ring. Counted
   rather than divided, so nothing here rests on a division the prelude may or
   may not carry. *)
Fixpoint activations_from (k b fuel : nat) : nat :=
  match fuel with
  | 0 => k
  | S f => if Nat.leb ring_capacity (k * b) then k else activations_from (S k) b f
  end.

Definition drain_activations (b : nat) : nat :=
  activations_from 0 b (S ring_capacity).

(* R-12-101's joint bound, over the five terms that entry names and no others:
   the capacity and the batch size through `drain_activations`, the polling
   cadence, the device latency through the declared record, and the slot
   budget through the contract's own `activation_cost`. Which relation those
   five stand in is gap e, so the accounting is a declared field and both arms
   are exhibited. *)
Definition accounted_latency (s : Service) (o : op) : nat :=
  match svc_accounting s with
  | accounts_the_queue =>
      drain_activations (cap_batch (svc_caps s)) * svc_cadence s
      + so_service (svc_per_op s o)
  | accounts_the_service_alone => so_service (svc_per_op s o)
  end.

Definition service_conjuncts : list (Service -> bool) :=
  (* 0: R-12-095. The accepted ceiling spends the completion capacity exactly. *)
  cons (fun s => Nat.eqb (cap_accepted (svc_caps s) + cap_accepted_slack (svc_caps s))
                         ring_completion_capacity)
  (* 1: R-12-095. And it spends the request ring's capacity exactly. *)
  (cons (fun s => Nat.eqb (cap_accepted (svc_caps s) + cap_ring_slack (svc_caps s))
                          ring_capacity)
  (* 2: R-12-098. The batch is not empty and spends the declared maximum
        exactly. *)
  (cons (fun s => andb (Nat.ltb 0 (cap_batch (svc_caps s)))
                       (Nat.eqb (cap_batch (svc_caps s) + cap_batch_slack (svc_caps s))
                                ring_max_batch_size))
  (* 3: R-12-100 through R-12-101 (gap b). The segments spend the declared
        maximum segment count exactly. *)
  (cons (fun s => all_of (fun o =>
                            Nat.eqb (so_segments (svc_per_op s o)
                                     + so_segment_slack (svc_per_op s o))
                                    (rec_max_segment_count (op_declared_record o)))
                         all_ops)
  (* 4: R-05-124 with R-12-101 (gap i). The staging buffer holds the declared
        payload and its own declared headroom. *)
  (cons (fun s => all_of (fun o =>
                            Nat.eqb (rec_max_payload_bytes (op_declared_record o)
                                     + so_staging_slack (svc_per_op s o))
                                    (so_staging (svc_per_op s o)))
                         all_ops)
  (* 5: R-12-097. The cleanup cost spends the declared cleanup bound exactly. *)
  (cons (fun s => all_of (fun o =>
                            Nat.eqb (so_cleanup (svc_per_op s o)
                                     + so_cleanup_slack (svc_per_op s o))
                                    (rec_cancellation_cleanup_cost
                                       (op_declared_record o)))
                         all_ops)
  (* 6: R-12-097. Every reference the operation holds is released at cleanup. *)
  (cons (fun s => all_of (fun o => Nat.eqb (so_released (svc_per_op s o))
                                           (op_buffer_refs o))
                         all_ops)
  (* 7: R-12-101. The three costs the per-variant record fixes are the
        declaration's own and not the service's second opinion. *)
  (cons (fun s => all_of (fun o =>
                     andb (Nat.eqb (so_validation (svc_per_op s o))
                                   (rec_validation_cost (op_declared_record o)))
                     (andb (Nat.eqb (so_service (svc_per_op s o))
                                    (rec_device_service_bound (op_declared_record o)))
                           (Nat.eqb (so_publication (svc_per_op s o))
                                    (rec_completion_publication_cost
                                       (op_declared_record o)))))
                         all_ops)
  (* 8: R-12-101 (gap e). The declared latency is the one the declared
        accounting computes. *)
  (cons (fun s => all_of (fun o => Nat.eqb (so_latency (svc_per_op s o))
                                           (accounted_latency s o))
                         all_ops)
  (* 9: R-12-101. The accounted latency spends the declared progress bound
        exactly. *)
  (cons (fun s => all_of (fun o => Nat.eqb (so_latency (svc_per_op s o)
                                            + so_progress_slack (svc_per_op s o))
                                           (so_progress_bound (svc_per_op s o)))
                         all_ops)
  (* 10: R-12-092 with R-12-094 (gap d). A submitted or accepted request holds
         its identifier live, and a free or reclaimed slot does not, on pain of
         no identifier ever being reusable. Writing and Terminal are the
         declaration's. *)
  (cons (fun s => andb (andb (svc_live s state_Submitted) (svc_live s state_Accepted))
                       (andb (negb (svc_live s state_Free))
                             (negb (svc_live s state_Reclaimed))))
  (* 11: R-12-096 with R-12-101 (gap a). The notification word is binary, so no
         counter exists, and the declared reset meets the declared maximum
         notifications. The maximum is a field of the *per-variant* record, so
         the reset is held to every variant's and not to one variant's read as
         the ring's: one word serves every operation, so a bound read at one
         operation is a bound the declaration did not state. *)
  (cons (fun s => andb (negb (svc_counter s))
                       (all_of (fun o =>
                                  Nat.leb (signals_in_a_burst (svc_reset s))
                                          (rec_max_notifications
                                             (op_declared_record o)))
                               all_ops))
  (* 12: R-11-006 with R-12-100. The copy is charged at the declared maximum,
         so the admitted binary's cost does not move with its input. *)
  (cons (fun s => svc_charges_at_the_maximum s)
   nil)))))))))))).

Definition admissible_service (s : Service) : bool :=
  all_of (fun p => p s) service_conjuncts.

Definition service_broken (s : Service) : nat :=
  count_of (filter_of (fun p => negb (p s)) service_conjuncts).

Definition declared_without (k : nat) (s : Service) : bool :=
  all_of (fun p => p s) (drop_at k service_conjuncts).

Example there_are_thirteen_service_conjuncts :
  count_of service_conjuncts = 13.
Proof. reflexivity. Qed.

(* =========================================================================
   The declared service, and the one-field setters every spoiling is built
   from: a witness written out carries thirteen figures where one derived by a
   setter carries one, and the seeded population is counted in figures.
   ========================================================================= *)

Definition demo_capacities : svc_capacities := mk_svc_capacities 48 16 16 8 0.

Definition demo_op_record (o : op) : svc_op_record :=
  match o with
  | op_read_extent =>
      mk_svc_op_record 3 1 4352 256 32 8 2 24 1200 16 21200 800 22000
  | op_write_extent =>
      mk_svc_op_record 3 1 4352 256 40 8 2 28 1600 16 21600 400 22000
  | op_flush =>
      mk_svc_op_record 0 0 0 0 0 0 0 8 900 16 20900 1100 22000
  | op_query_geometry =>
      mk_svc_op_record 1 0 64 0 0 0 1 6 120 16 20120 1880 22000
  | op_poll_status =>
      mk_svc_op_record 0 0 0 0 0 0 0 4 60 16 20060 1940 22000
  end.

(* The live-state arm this declaration takes: Writing and Terminal hold their
   identifiers live, which is the conservative reading of gap d. *)
Definition demo_live (t : slot_state) : bool :=
  match t with
  | state_Free => false
  | state_Writing => true
  | state_Submitted => true
  | state_Accepted => true
  | state_Terminal => true
  | state_Reclaimed => false
  end.

Definition demo_service : Service :=
  mk_service demo_capacities demo_op_record demo_live reset_at_the_signal false
             2500 accounts_the_queue true 1.

(* The other arm of gap d: a declaration on which a slot still being written
   does not hold its identifier live. It is admitted too, and the difference
   is observable on a slot in that state. *)
Definition writing_not_live (t : slot_state) : bool :=
  match t with state_Writing => false | _ => demo_live t end.

Definition with_caps (s : Service) (c : svc_capacities) : Service :=
  mk_service c (svc_per_op s) (svc_live s) (svc_reset s) (svc_counter s)
             (svc_cadence s) (svc_accounting s) (svc_charges_at_the_maximum s)
             (svc_identity s).

Definition with_op (s : Service) (o : op) (r : svc_op_record) : Service :=
  mk_service (svc_caps s) (fun x => if op_eqb x o then r else svc_per_op s x)
             (svc_live s) (svc_reset s) (svc_counter s) (svc_cadence s)
             (svc_accounting s) (svc_charges_at_the_maximum s) (svc_identity s).

Definition with_live (s : Service) (f : slot_state -> bool) : Service :=
  mk_service (svc_caps s) (svc_per_op s) f (svc_reset s) (svc_counter s)
             (svc_cadence s) (svc_accounting s) (svc_charges_at_the_maximum s)
             (svc_identity s).

Definition with_reset (s : Service) (r : reset_owner) : Service :=
  mk_service (svc_caps s) (svc_per_op s) (svc_live s) r (svc_counter s)
             (svc_cadence s) (svc_accounting s) (svc_charges_at_the_maximum s)
             (svc_identity s).

Definition with_counter (s : Service) (c : bool) : Service :=
  mk_service (svc_caps s) (svc_per_op s) (svc_live s) (svc_reset s) c
             (svc_cadence s) (svc_accounting s) (svc_charges_at_the_maximum s)
             (svc_identity s).

Definition with_cadence (s : Service) (n : nat) : Service :=
  mk_service (svc_caps s) (svc_per_op s) (svc_live s) (svc_reset s) (svc_counter s)
             n (svc_accounting s) (svc_charges_at_the_maximum s) (svc_identity s).

Definition with_charging (s : Service) (c : bool) : Service :=
  mk_service (svc_caps s) (svc_per_op s) (svc_live s) (svc_reset s) (svc_counter s)
             (svc_cadence s) (svc_accounting s) c (svc_identity s).

Definition set_accepted_slack (c : svc_capacities) (n : nat) : svc_capacities :=
  mk_svc_capacities (cap_accepted c) n (cap_ring_slack c) (cap_batch c)
                    (cap_batch_slack c).

Definition set_ring_slack (c : svc_capacities) (n : nat) : svc_capacities :=
  mk_svc_capacities (cap_accepted c) (cap_accepted_slack c) n (cap_batch c)
                    (cap_batch_slack c).

Definition set_batch_slack (c : svc_capacities) (n : nat) : svc_capacities :=
  mk_svc_capacities (cap_accepted c) (cap_accepted_slack c) (cap_ring_slack c)
                    (cap_batch c) n.

Definition set_segment_slack (r : svc_op_record) (n : nat) : svc_op_record :=
  mk_svc_op_record (so_segments r) n (so_staging r) (so_staging_slack r)
                   (so_cleanup r) (so_cleanup_slack r) (so_released r)
                   (so_validation r) (so_service r) (so_publication r)
                   (so_latency r) (so_progress_slack r) (so_progress_bound r).

Definition set_staging_slack (r : svc_op_record) (n : nat) : svc_op_record :=
  mk_svc_op_record (so_segments r) (so_segment_slack r) (so_staging r) n
                   (so_cleanup r) (so_cleanup_slack r) (so_released r)
                   (so_validation r) (so_service r) (so_publication r)
                   (so_latency r) (so_progress_slack r) (so_progress_bound r).

Definition set_cleanup_slack (r : svc_op_record) (n : nat) : svc_op_record :=
  mk_svc_op_record (so_segments r) (so_segment_slack r) (so_staging r)
                   (so_staging_slack r) (so_cleanup r) n (so_released r)
                   (so_validation r) (so_service r) (so_publication r)
                   (so_latency r) (so_progress_slack r) (so_progress_bound r).

Definition set_released (r : svc_op_record) (n : nat) : svc_op_record :=
  mk_svc_op_record (so_segments r) (so_segment_slack r) (so_staging r)
                   (so_staging_slack r) (so_cleanup r) (so_cleanup_slack r) n
                   (so_validation r) (so_service r) (so_publication r)
                   (so_latency r) (so_progress_slack r) (so_progress_bound r).

Definition set_validation (r : svc_op_record) (n : nat) : svc_op_record :=
  mk_svc_op_record (so_segments r) (so_segment_slack r) (so_staging r)
                   (so_staging_slack r) (so_cleanup r) (so_cleanup_slack r)
                   (so_released r) n (so_service r) (so_publication r)
                   (so_latency r) (so_progress_slack r) (so_progress_bound r).

Definition set_service (r : svc_op_record) (n : nat) : svc_op_record :=
  mk_svc_op_record (so_segments r) (so_segment_slack r) (so_staging r)
                   (so_staging_slack r) (so_cleanup r) (so_cleanup_slack r)
                   (so_released r) (so_validation r) n (so_publication r)
                   (so_latency r) (so_progress_slack r) (so_progress_bound r).

Definition set_publication (r : svc_op_record) (n : nat) : svc_op_record :=
  mk_svc_op_record (so_segments r) (so_segment_slack r) (so_staging r)
                   (so_staging_slack r) (so_cleanup r) (so_cleanup_slack r)
                   (so_released r) (so_validation r) (so_service r) n
                   (so_latency r) (so_progress_slack r) (so_progress_bound r).

Definition set_progress_slack (r : svc_op_record) (n : nat) : svc_op_record :=
  mk_svc_op_record (so_segments r) (so_segment_slack r) (so_staging r)
                   (so_staging_slack r) (so_cleanup r) (so_cleanup_slack r)
                   (so_released r) (so_validation r) (so_service r)
                   (so_publication r) (so_latency r) n (so_progress_bound r).

Definition spoil_op (s : Service) (o : op)
                    (f : svc_op_record -> nat -> svc_op_record) (n : nat) : Service :=
  with_op s o (f (svc_per_op s o) n).

(* Thirteen spoilings, one per conjunct, each moving one declared field to the
   value on that conjunct's own boundary. *)
Definition spoiled_at (k : nat) : Service :=
  match k with
  | 0 => with_caps demo_service (set_accepted_slack demo_capacities 17)
  | 1 => with_caps demo_service (set_ring_slack demo_capacities 17)
  | 2 => with_caps demo_service (set_batch_slack demo_capacities 1)
  | 3 => spoil_op demo_service op_read_extent set_segment_slack 2
  | 4 => spoil_op demo_service op_read_extent set_staging_slack 257
  | 5 => spoil_op demo_service op_read_extent set_cleanup_slack 9
  | 6 => spoil_op demo_service op_read_extent set_released 1
  | 7 => spoil_op demo_service op_read_extent set_validation 25
  | 8 => with_cadence demo_service 2501
  | 9 => spoil_op demo_service op_read_extent set_progress_slack 801
  | 10 => with_live demo_service (fun t => match t with
                                           | state_Submitted => false
                                           | _ => demo_live t
                                           end)
  | 11 => with_counter demo_service true
  | _ => with_charging demo_service false
  end.

Definition demo_read_record : svc_op_record := demo_op_record op_read_extent.

(* Section 6's own rule, of an arbitrary declaration rather than of a witness:
   a service is admitted exactly when it breaks no conjunct, so "no service is
   grandfathered" is one statement and not a property of this demo. *)
Theorem admission_is_exactly_the_absence_of_a_broken_conjunct :
  forall s : Service,
    agree (admissible_service s) (Nat.eqb (service_broken s) 0) = true.
Proof.
  intro s. unfold admissible_service, service_broken.
  exact (all_of_is_none_broken (Service -> bool) (fun p => p s) service_conjuncts).
Qed.

Theorem the_declared_service_is_admitted :
  andb (admissible_service demo_service) (Nat.eqb (service_broken demo_service) 0)
  = true.
Proof. vm_compute; reflexivity. Qed.

Theorem every_spoiling_breaks_exactly_one_conjunct :
  all_of (fun k => Nat.eqb (service_broken (spoiled_at k)) 1) (upto 13) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem no_spoiled_service_is_admitted :
  all_of (fun k => negb (admissible_service (spoiled_at k))) (upto 13) = true.
Proof. vm_compute; reflexivity. Qed.

(* And from the filter side: each dropped conjunct admits exactly the service
   it stopped checking, which is what makes a conjunct's presence decide
   something rather than merely be present. *)
Theorem every_dropped_conjunct_admits_the_service_it_stopped_checking :
  all_of (fun k => declared_without k (spoiled_at k)) (upto 13) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem no_dropped_conjunct_admits_another_spoiling :
  all_of (fun k =>
            Nat.eqb (count_of (filter_of (fun j => declared_without k (spoiled_at j))
                                         (upto 13))) 1)
         (upto 13) = true.
Proof. vm_compute; reflexivity. Qed.

(* Each numeric spoiling moves its own field by exactly one, so the ledger
   pins the weakening rather than merely reporting that one happened: a
   spoiler free to move a field by any amount is a witness whose value no
   statement reads. *)
Example every_numeric_spoiling_moves_its_field_by_one :
  all_of (fun b => b)
    (cons (Nat.eqb (cap_accepted_slack (svc_caps (spoiled_at 0)))
                   (S (cap_accepted_slack demo_capacities)))
    (cons (Nat.eqb (cap_ring_slack (svc_caps (spoiled_at 1)))
                   (S (cap_ring_slack demo_capacities)))
    (cons (Nat.eqb (cap_batch_slack (svc_caps (spoiled_at 2)))
                   (S (cap_batch_slack demo_capacities)))
    (cons (Nat.eqb (so_segment_slack (svc_per_op (spoiled_at 3) op_read_extent))
                   (S (so_segment_slack demo_read_record)))
    (cons (Nat.eqb (so_staging_slack (svc_per_op (spoiled_at 4) op_read_extent))
                   (S (so_staging_slack demo_read_record)))
    (cons (Nat.eqb (so_cleanup_slack (svc_per_op (spoiled_at 5) op_read_extent))
                   (S (so_cleanup_slack demo_read_record)))
    (cons (Nat.eqb (so_released (svc_per_op (spoiled_at 6) op_read_extent))
                   (Nat.pred (so_released demo_read_record)))
    (cons (Nat.eqb (so_validation (svc_per_op (spoiled_at 7) op_read_extent))
                   (S (so_validation demo_read_record)))
    (cons (Nat.eqb (svc_cadence (spoiled_at 8)) (S (svc_cadence demo_service)))
    (cons (Nat.eqb (so_progress_slack (svc_per_op (spoiled_at 9) op_read_extent))
                   (S (so_progress_slack demo_read_record)))
     nil)))))))))) = true.
Proof. vm_compute; reflexivity. Qed.

(* Conjunct 2 is decided at both of its own boundaries: a batch of one is a
   legal amortization unit and an empty one is not, so the test is against zero
   and not against the declared maximum. *)
Definition batch_of_one : svc_capacities := mk_svc_capacities 48 16 16 1 7.
Definition batch_of_none : svc_capacities := mk_svc_capacities 48 16 16 0 8.

Theorem the_batch_conjunct_admits_one_and_refuses_none :
  andb (at_member service_conjuncts 2 (fun _ => false)
                  (with_caps demo_service batch_of_one))
       (negb (at_member service_conjuncts 2 (fun _ => false)
                        (with_caps demo_service batch_of_none))) = true.
Proof. vm_compute; reflexivity. Qed.

(* Conjunct 7 reads all three of the costs R-12-101's record fixes, decided
   once per cost rather than once for the conjunct. *)
Theorem the_cost_conjunct_reads_all_three_costs :
  all_of (fun s => negb (at_member service_conjuncts 7 (fun _ => false) s))
    (cons (spoil_op demo_service op_read_extent set_validation 25)
    (cons (spoil_op demo_service op_read_extent set_service 1201)
    (cons (spoil_op demo_service op_read_extent set_publication 17)
     nil))) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_declared_service_keeps_the_cost_conjunct :
  at_member service_conjuncts 7 (fun _ => false) demo_service = true.
Proof. vm_compute; reflexivity. Qed.

(* The reset arm the declared bound refuses, and it is refused at conjunct 11
   alone: R-12-096 states no reset owner, and what decides between the two is
   R-12-101's declared maximum notifications (gap a). *)
Theorem the_drain_reset_service_is_refused_at_the_notification_bound :
  andb (negb (admissible_service (with_reset demo_service reset_at_the_drain)))
       (Nat.eqb (service_broken (with_reset demo_service reset_at_the_drain)) 1)
  = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_drain_reset_service_keeps_every_other_conjunct :
  declared_without 11 (with_reset demo_service reset_at_the_drain) = true.
Proof. vm_compute; reflexivity. Qed.

(* And the conjunct's quantifier is decided at every variant rather than at
   one: the drain reset's second signal exceeds the declared maximum at each of
   the five, so no operation carries the bound for the others. *)
Theorem the_notification_bound_is_exceeded_at_every_variant :
  all_of (fun o => Nat.ltb (rec_max_notifications (op_declared_record o))
                           (signals_in_a_burst reset_at_the_drain))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

(* The other live-state arm is admitted, so gap d is exhibited rather than
   decided, and the difference is observable on a slot being written. *)
Theorem the_other_live_state_arm_is_admitted_too :
  admissible_service (with_live demo_service writing_not_live) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_two_live_state_arms_differ_on_a_slot_being_written :
  andb (svc_live demo_service state_Writing)
       (negb (svc_live (with_live demo_service writing_not_live) state_Writing))
  = true.
Proof. vm_compute; reflexivity. Qed.

(* R-12-092's duplicate live identifier, decided over the declared live set
   and handed to the contract's own `accept`. *)
Definition holds_live (s : Service) (slots : list slot) (id : nat) : bool :=
  any_of (fun z => andb (svc_live s (sl_state z)) (Nat.eqb (sl_request z) id)) slots.

Definition service_accept (s : Service) (slots : list slot)
                          (generation descriptor_gen id : nat) : bool :=
  accept generation descriptor_gen (holds_live s slots id).

Definition busy_slots : list slot :=
  cons (mk_slot state_Writing 0 true 7) (cons (mk_slot state_Accepted 0 true 9) nil).

Theorem a_duplicate_live_identifier_is_refused_at_this_service :
  service_accept demo_service busy_slots ring_session_generation
                 ring_session_generation 9 = false.
Proof. vm_compute; reflexivity. Qed.

Theorem a_fresh_identifier_is_accepted_at_this_service :
  service_accept demo_service busy_slots ring_session_generation
                 ring_session_generation 11 = true.
Proof. vm_compute; reflexivity. Qed.

Theorem a_stale_generation_is_refused_at_this_service :
  service_accept demo_service busy_slots ring_session_generation
                 (S ring_session_generation) 11 = false.
Proof. vm_compute; reflexivity. Qed.

(* The two live-state arms differ observably here and not merely in the
   declaration: an identifier held by a slot being written is reusable under
   one arm and not under the other. *)
Theorem the_live_state_arms_differ_on_an_identifier_being_written :
  andb (negb (service_accept demo_service busy_slots ring_session_generation
                             ring_session_generation 7))
       (service_accept (with_live demo_service writing_not_live) busy_slots
                       ring_session_generation ring_session_generation 7) = true.
Proof. vm_compute; reflexivity. Qed.

(* =========================================================================
   Part 8: the accounting arms, and what the joint bound turns on (gaps e
   and f).
   ========================================================================= *)

Theorem the_drain_activations_empty_a_full_ring :
  Nat.leb ring_capacity (drain_activations (cap_batch demo_capacities)
                         * cap_batch demo_capacities) = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_drain_activations_are_the_least_such_count :
  Nat.ltb (Nat.pred (drain_activations (cap_batch demo_capacities))
           * cap_batch demo_capacities) ring_capacity = true.
Proof. vm_compute; reflexivity. Qed.

(* The service the other accounting arm declares, admitted on its own terms:
   the same costs and the same slacks, with the latency and the progress bound
   the service-alone reading gives. *)
Definition service_alone_op_record (o : op) : svc_op_record :=
  mk_svc_op_record
    (so_segments (demo_op_record o)) (so_segment_slack (demo_op_record o))
    (so_staging (demo_op_record o)) (so_staging_slack (demo_op_record o))
    (so_cleanup (demo_op_record o)) (so_cleanup_slack (demo_op_record o))
    (so_released (demo_op_record o)) (so_validation (demo_op_record o))
    (so_service (demo_op_record o)) (so_publication (demo_op_record o))
    (so_service (demo_op_record o))
    (so_progress_bound (demo_op_record o) - so_service (demo_op_record o))
    (so_progress_bound (demo_op_record o)).

Definition service_alone : Service :=
  mk_service demo_capacities service_alone_op_record demo_live reset_at_the_signal
             false 2500 accounts_the_service_alone true 2.

Theorem the_service_alone_accounting_is_admitted_too :
  admissible_service service_alone = true.
Proof. vm_compute; reflexivity. Qed.

(* The two arms are compared at one cadence and one batch, so what separates
   them is the accounting they declare and nothing else about them. *)
Theorem the_two_accountings_are_compared_at_one_cadence :
  andb (Nat.eqb (svc_cadence service_alone) (svc_cadence demo_service))
       (Nat.eqb (svc_identity service_alone) (S (svc_identity demo_service))) = true.
Proof. vm_compute; reflexivity. Qed.

(* And the arm that charges the service alone does not read the cadence at all,
   which is the other half of what gap e leaves open: one of the two readings
   makes one of R-12-101's five terms inert. *)
Theorem the_service_alone_accounting_does_not_read_the_cadence :
  all_of (fun o => Nat.eqb (accounted_latency (with_cadence service_alone 1) o)
                           (accounted_latency service_alone o))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_queueing_accounting_does_read_the_cadence :
  all_of (fun o => negb (Nat.eqb (accounted_latency (with_cadence demo_service 1) o)
                                 (accounted_latency demo_service o)))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

(* And the two arms differ observably at every operation, by exactly the
   queueing term: eight activations of the declared cadence. *)
Theorem the_two_accountings_differ_by_the_queueing_term :
  all_of (fun o => Nat.eqb (accounted_latency demo_service o)
                           (drain_activations (cap_batch demo_capacities)
                            * svc_cadence demo_service
                            + accounted_latency service_alone o))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_two_accountings_are_never_equal :
  all_of (fun o => negb (Nat.eqb (accounted_latency demo_service o)
                                 (accounted_latency service_alone o)))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

(* The activation cost is the contract's own and this service reproduces it
   rather than restating it: what the service adds is the copy, which rides
   the declared device-service bound (gap c). *)
Theorem the_service_reproduces_the_contracts_activation_cost :
  all_of (fun o => Nat.eqb (activation_cost o)
                           (rec_max_requests_drained (op_declared_record o)
                            * (so_validation (svc_per_op demo_service o)
                               + so_service (svc_per_op demo_service o)
                               + so_publication (svc_per_op demo_service o))))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_activation_still_spends_the_declared_slot_budget :
  all_of (fun o => Nat.eqb (activation_cost o + op_activation_slack o) ring_slot_budget)
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

(* R-12-097's cleanup: the interval admission accounts from expiry observation
   to terminal completion is the contract's, and what this service adds is
   that its own cleanup cost sits inside the declared cleanup bound with a
   declared margin, and that every reference the operation holds is released. *)
Theorem the_cleanup_sits_inside_the_declared_bound :
  all_of (fun o => Nat.leb (so_cleanup (svc_per_op demo_service o))
                           (rec_cancellation_cleanup_cost (op_declared_record o)))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

Theorem every_held_reference_is_released_at_cleanup :
  all_of (fun o => Nat.eqb (so_released (svc_per_op demo_service o)) (op_buffer_refs o))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_cancellation_interval_is_the_contracts :
  all_of (fun o => implb (op_cancellable o)
                         (Nat.eqb (cancellation_interval o + op_cancellation_slack o)
                                  (op_max_to_terminal o)))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

(* The segment bound this service takes through R-12-101's record rather than
   through R-12-100's own sentence (gap b), and the payload the contract
   already holds to its declared segments. *)
Theorem every_declared_segment_count_is_inside_the_rings :
  all_of (fun o => Nat.leb (so_segments (svc_per_op demo_service o)) ring_max_segments)
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

Theorem the_staging_buffer_holds_the_declared_payload :
  all_of (fun o => Nat.leb (rec_max_payload_bytes (op_declared_record o))
                           (so_staging (svc_per_op demo_service o)))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

(* =========================================================================
   The ledger. Every field of every witness no obligation reads is pinned
   here, which is the hazard M6.2a measured: a field nothing reads is a field
   a weakening moves in silence.
   ========================================================================= *)

Example the_declared_capacities :
  andb (andb (Nat.eqb (cap_accepted demo_capacities) 48)
             (Nat.eqb (cap_accepted_slack demo_capacities) 16))
       (andb (Nat.eqb (cap_ring_slack demo_capacities) 16)
             (andb (Nat.eqb (cap_batch demo_capacities) 8)
                   (Nat.eqb (cap_batch_slack demo_capacities) 0))) = true.
Proof. vm_compute; reflexivity. Qed.

(* Pinned as sums over the five records rather than as bounds. A bound admits
   every value below it, so a field moved downward is a field the ledger did
   not read; a sum moves whenever any one of the five does. *)
Example every_declared_record_states_its_segments_and_its_staging :
  all_of (fun b => b)
    (cons (Nat.eqb (sum_of (map_over (fun o => so_segments (demo_op_record o))
                                     all_ops)) 7)
    (cons (Nat.eqb (sum_of (map_over (fun o => so_segment_slack (demo_op_record o))
                                     all_ops)) 2)
    (cons (Nat.eqb (sum_of (map_over (fun o => so_staging (demo_op_record o))
                                     all_ops)) 8768)
    (cons (Nat.eqb (sum_of (map_over (fun o => so_staging_slack (demo_op_record o))
                                     all_ops)) 512)
     nil)))) = true.
Proof. vm_compute; reflexivity. Qed.

Example every_declared_record_states_its_cleanup_and_its_releases :
  all_of (fun b => b)
    (cons (Nat.eqb (sum_of (map_over (fun o => so_cleanup (demo_op_record o))
                                     all_ops)) 72)
    (cons (Nat.eqb (sum_of (map_over (fun o => so_cleanup_slack (demo_op_record o))
                                     all_ops)) 16)
    (cons (Nat.eqb (sum_of (map_over (fun o => so_released (demo_op_record o))
                                     all_ops)) 5)
     nil))) = true.
Proof. vm_compute; reflexivity. Qed.

Example every_declared_record_states_its_three_costs :
  all_of (fun o => andb (Nat.eqb (so_validation (demo_op_record o))
                                 (rec_validation_cost (op_declared_record o)))
                        (andb (Nat.eqb (so_service (demo_op_record o))
                                       (rec_device_service_bound (op_declared_record o)))
                              (Nat.eqb (so_publication (demo_op_record o)) 16)))
         all_ops = true.
Proof. vm_compute; reflexivity. Qed.

Example every_declared_record_states_one_progress_bound :
  all_of (fun o => Nat.eqb (so_progress_bound (demo_op_record o)) 22000) all_ops = true.
Proof. vm_compute; reflexivity. Qed.

Example the_declared_service_states_its_seven_other_fields :
  andb (andb (negb (svc_counter demo_service))
             (Nat.eqb (svc_cadence demo_service) 2500))
       (andb (svc_charges_at_the_maximum demo_service)
             (andb (Nat.eqb (svc_identity demo_service) 1)
                   (andb (svc_live demo_service state_Terminal)
                         (andb (match svc_reset demo_service with
                                | reset_at_the_signal => true
                                | reset_at_the_drain => false
                                end)
                               (match svc_accounting demo_service with
                                | accounts_the_queue => true
                                | accounts_the_service_alone => false
                                end))))) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_read_record_states_its_thirteen_fields :
  all_of (fun b => b)
    (cons (Nat.eqb (so_segments demo_read_record) 3)
    (cons (Nat.eqb (so_segment_slack demo_read_record) 1)
    (cons (Nat.eqb (so_staging demo_read_record) 4352)
    (cons (Nat.eqb (so_staging_slack demo_read_record) 256)
    (cons (Nat.eqb (so_cleanup demo_read_record) 32)
    (cons (Nat.eqb (so_cleanup_slack demo_read_record) 8)
    (cons (Nat.eqb (so_released demo_read_record) 2)
    (cons (Nat.eqb (so_validation demo_read_record) 24)
    (cons (Nat.eqb (so_service demo_read_record) 1200)
    (cons (Nat.eqb (so_publication demo_read_record) 16)
    (cons (Nat.eqb (so_latency demo_read_record) 21200)
    (cons (Nat.eqb (so_progress_slack demo_read_record) 800)
    (cons (Nat.eqb (so_progress_bound demo_read_record) 22000)
     nil))))))))))))) = true.
Proof. vm_compute; reflexivity. Qed.

Example every_spoiling_moves_one_field_and_keeps_the_identity :
  all_of (fun k => Nat.eqb (svc_identity (spoiled_at k)) (svc_identity demo_service))
         (upto 13) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_two_services_carry_different_identities :
  negb (Nat.eqb (svc_identity demo_service) (svc_identity service_alone)) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_four_ring_views :
  andb (Nat.eqb (rv_produced full_view) ring_capacity)
       (andb (Nat.eqb (rv_consumed full_view) 0)
             (andb (Nat.eqb (rv_produced brimming_view) (Nat.pred ring_capacity))
                   (andb (Nat.eqb (rv_produced empty_view) 0)
                         (andb (Nat.eqb (rv_consumed empty_view) 0)
                               (Nat.eqb (rv_occupancy single_view) 1))))) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_two_batch_views :
  andb (Nat.eqb (rv_occupancy roomy_view) 0)
       (Nat.eqb (rv_occupancy crowded_view + 3) ring_capacity) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_four_worlds :
  all_of (fun b => b)
    (cons (world_eqb quiet_world (mk_world (mk_ring_view 0 0) false 0 0 0 false))
    (cons (world_eqb armed_world (mk_world (mk_ring_view 0 0) true 0 0 0 true))
    (cons (world_eqb backlogged_world (mk_world (mk_ring_view 20 0) false 0 0 0 false))
    (cons (world_eqb after_a_coalesced_burst
                     (mk_world (mk_ring_view 2 0) true 0 2 0 false))
    (cons (world_eqb after_the_signal_arrived
                     (mk_world (mk_ring_view 2 0) true 1 2 0 false))
     nil))))) = true.
Proof. vm_compute; reflexivity. Qed.

(* The three slot witnesses are one request seen three ways, so their
   identifiers agree and what separates them is the reader count and the
   validation flag. *)
Example the_slot_witnesses_carry_their_readers_and_their_validation :
  all_of (fun b => b)
    (cons (Nat.eqb (count_of all_slots) 18)
    (cons (Nat.eqb (sl_readers held_terminal_slot) 1)
    (cons (negb (sl_validated unvalidated_submitted_slot))
    (cons (Nat.eqb (sl_readers demo_slot) 0)
    (cons (sl_validated demo_slot)
    (cons (Nat.eqb (sl_request demo_slot) (sl_request held_terminal_slot))
    (cons (Nat.eqb (sl_request demo_slot) (sl_request unvalidated_submitted_slot))
    (cons (Nat.eqb (sl_request demo_slot) 7)
    (cons (Nat.eqb (sl_readers unvalidated_submitted_slot) 0)
    (cons (sl_validated held_terminal_slot)
     nil)))))))))) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_copy_witnesses_carry_their_lengths_and_their_extent :
  all_of (fun b => b)
    (cons (Nat.eqb (buf_length first_image) declared_extent)
    (cons (Nat.eqb (cr_reads staged_run) 1)
    (cons (Nat.eqb (cr_reads revalidated_run) 2)
    (cons (Nat.eqb (cr_staged staged_run) (buf_datum first_image))
    (cons (Nat.eqb (cr_staged revalidated_run) (buf_datum second_image))
    (cons (Nat.eqb (cr_bytes staged_run) (buf_length first_image))
    (cons (Nat.eqb (cr_bytes revalidated_run) (buf_length second_image))
     nil))))))) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_two_busy_slots :
  andb (Nat.eqb (count_of busy_slots) 2)
       (Nat.eqb (count_of (filter_of (fun z => svc_live demo_service (sl_state z))
                                     busy_slots)) 2) = true.
Proof. vm_compute; reflexivity. Qed.

(* The contract's own records, inhabited here so that a statement quantifying
   over one has a witness on this side of the Require and the campaign's
   descriptor and completion are things rather than types. *)
Definition demo_descriptor : descriptor :=
  mk_descriptor op_read_extent 11 ring_session_generation
                (cons 0 (cons 4096 nil))
                (cons (mk_buffer_ref 0 0 4096 direction_to_client content_opaque_bytes)
                      (cons (mk_buffer_ref 1 0 64 direction_to_server
                                           content_opaque_bytes) nil))
                (Some deadline_bulk)
                (cons flag_notify_on_completion nil).

Definition demo_completion : completion :=
  mk_completion 11 status_ok None 0 64 4096 ring_session_generation.

Definition demo_op_declaration : op_record := op_declared_record op_read_extent.

Definition demo_labels : labels := op_labels op_read_extent.

Definition demo_buffer_ref : buffer_ref :=
  mk_buffer_ref 0 0 4096 direction_to_client content_opaque_bytes.

(* Every field of both of the descriptor's buffer references and of its
   scalars, pinned as sums over the list rather than left unread: a field no
   obligation reads is a field a weakening moves in silence. *)
Example the_descriptor_states_both_of_its_buffer_references :
  all_of (fun b => b)
    (cons (Nat.eqb (count_of (buffers demo_descriptor)) 2)
    (cons (Nat.eqb (sum_of (map_over session_index (buffers demo_descriptor))) 1)
    (cons (Nat.eqb (sum_of (map_over ref_offset (buffers demo_descriptor))) 0)
    (cons (Nat.eqb (sum_of (map_over ref_length (buffers demo_descriptor))) 4160)
    (cons (Nat.eqb (count_of (scalars demo_descriptor))
                   (op_marked_scalars (descriptor_op demo_descriptor)))
    (cons (Nat.eqb (sum_of (scalars demo_descriptor)) 4096)
    (cons (Nat.eqb (count_of (flags demo_descriptor)) 1)
     nil))))))) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_completion_states_its_byte_counts_and_its_metadata :
  all_of (fun b => b)
    (cons (Nat.eqb (metadata demo_completion) 0)
    (cons (Nat.eqb (consumed_bytes demo_completion) 64)
    (cons (Nat.eqb (produced_bytes demo_completion) 4096)
    (cons (match completion_refinement demo_completion with
           | None => true
           | Some _ => false
           end)
    (cons (match completion_status demo_completion with
           | status_ok => true
           | _ => false
           end)
     nil))))) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_descriptor_and_the_completion_carry_one_request :
  andb (Nat.eqb (request_id demo_descriptor) (completion_request_id demo_completion))
       (andb (Nat.eqb (descriptor_generation demo_descriptor)
                      (server_generation demo_completion))
             (Nat.eqb (count_of (buffers demo_descriptor))
                      (op_buffer_refs (descriptor_op demo_descriptor)))) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_declared_labels_are_inside_the_lattice :
  andb (Nat.ltb (confidentiality demo_labels) label_levels)
       (Nat.ltb (integrity demo_labels) label_levels) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_declared_record_is_the_contracts :
  Nat.eqb (rec_max_requests_drained demo_op_declaration) ring_max_batch_size = true.
Proof. vm_compute; reflexivity. Qed.

Example the_buffer_reference_declares_its_direction_and_its_content :
  andb (Nat.eqb (ref_length demo_buffer_ref) 4096)
       (andb (match ref_direction demo_buffer_ref with
              | direction_to_client => true
              | direction_to_server => false
              end)
             (match ref_content demo_buffer_ref with
              | content_opaque_bytes => true
              | content_frame_extent => false
              end)) = true.
Proof. vm_compute; reflexivity. Qed.

Example the_two_copy_runs :
  andb (Nat.eqb (cr_reads (mk_copy_run 1 7 4)) 1)
       (andb (Nat.eqb (cr_staged (mk_copy_run 1 7 4)) 7)
             (Nat.eqb (cr_bytes (mk_copy_run 2 7 9)) 9)) = true.
Proof. vm_compute; reflexivity. Qed.

(* -------------------------------------------------------------------------
   The R-05-163 gate: every constant closed under the global context.
   ------------------------------------------------------------------------- *)

Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions nat_leb_refl.
Print Assumptions nat_leb_succ_r.
Print Assumptions nat_leb_from_succ.
Print Assumptions nat_leb_pred.
Print Assumptions nat_sub_zero.
Print Assumptions nat_sub_succ_l.
Print Assumptions nat_sub_succ_r.
Print Assumptions nat_ltb_sub_pos.
Print Assumptions leb_sub_succ.
Print Assumptions leb_pred_sub.
Print Assumptions all_of_is_none_broken.
Print Assumptions there_are_four_ownership_phases.
Print Assumptions there_are_three_rejected_paths.
Print Assumptions three_of_the_four_header_words_are_shared.
Print Assumptions the_generation_word_is_the_one_that_is_not_shared.
Print Assumptions the_operation_list_is_the_contracts.
Print Assumptions the_state_list_is_the_contracts_lifecycle.
Print Assumptions there_are_six_service_events.
Print Assumptions op_eqb_refl.
Print Assumptions consumer_act_eqb_refl.
Print Assumptions producer_act_eqb_refl.
Print Assumptions the_operations_are_pairwise_distinct.
Print Assumptions the_wire_index_separates_a_live_window.
Print Assumptions the_producer_never_writes_a_live_slot.
Print Assumptions the_slot_is_reused_exactly_a_capacity_later.
Print Assumptions the_occupancy_is_the_contracts_modular_difference.
Print Assumptions the_publisher_writes_only_the_producer_index.
Print Assumptions the_consumer_writes_only_the_consumer_index.
Print Assumptions publish_keeps_the_invariant.
Print Assumptions take_keeps_the_invariant.
Print Assumptions the_invariant_survives_every_interleaving.
Print Assumptions the_ring_fills_to_capacity_and_refuses_one_past.
Print Assumptions the_specification_never_partially_enqueues.
Print Assumptions the_dual_producer_is_refuted.
Print Assumptions the_dual_producer_keeps_the_ordering.
Print Assumptions the_dual_producer_writes_only_the_producer_index.
Print Assumptions the_dual_consumer_is_refuted.
Print Assumptions the_dual_consumer_keeps_the_capacity.
Print Assumptions the_dual_consumer_writes_only_the_consumer_index.
Print Assumptions the_untested_producer_is_refuted.
Print Assumptions the_untested_producer_keeps_the_ordering.
Print Assumptions the_untested_consumer_is_refuted.
Print Assumptions the_untested_consumer_keeps_the_capacity.
Print Assumptions the_untested_producer_partially_enqueues.
Print Assumptions the_dual_producer_never_partially_enqueues.
Print Assumptions the_refuting_views_sit_on_the_two_boundaries.
Print Assumptions there_are_seven_consumer_conjuncts.
Print Assumptions there_are_five_producer_conjuncts.
Print Assumptions the_specification_consumer_chain_breaks_nothing.
Print Assumptions the_specification_producer_chain_breaks_nothing.
Print Assumptions the_consumer_family_is_fifteen.
Print Assumptions the_producer_family_is_eleven.
Print Assumptions every_consumer_weakening_is_refused.
Print Assumptions every_producer_weakening_is_refused.
Print Assumptions no_consumer_transposition_is_a_well_formed_chain.
Print Assumptions no_consumer_deletion_is_a_well_formed_chain.
Print Assumptions no_consumer_suffix_is_a_well_formed_chain.
Print Assumptions no_duplicated_consumer_act_is_a_well_formed_chain.
Print Assumptions no_producer_transposition_is_a_well_formed_chain.
Print Assumptions no_producer_deletion_is_a_well_formed_chain.
Print Assumptions no_producer_suffix_is_a_well_formed_chain.
Print Assumptions no_duplicated_producer_act_is_a_well_formed_chain.
Print Assumptions every_consumer_weakening_is_refused_by_index.
Print Assumptions the_consumer_index_bound_is_exact.
Print Assumptions every_producer_weakening_is_refused_by_index.
Print Assumptions the_producer_index_bound_is_exact.
Print Assumptions a_producer_that_only_stages_breaks_the_order_and_both_counts.
Print Assumptions the_consumer_order_is_strict_at_the_same_place.
Print Assumptions the_drain_order_is_strict_at_its_own_boundary.
Print Assumptions the_release_order_is_strict_at_its_own_boundary.
Print Assumptions each_consumer_transposition_breaks_exactly_one.
Print Assumptions each_duplicated_consumer_act_breaks_exactly_one.
Print Assumptions each_producer_transposition_breaks_exactly_one.
Print Assumptions each_duplicated_producer_act_breaks_exactly_one.
Print Assumptions every_consumer_conjunct_is_reached.
Print Assumptions every_producer_conjunct_is_reached.
Print Assumptions the_specification_chain_excludes_every_lost_wakeup.
Print Assumptions the_drain_reset_also_excludes_every_lost_wakeup.
Print Assumptions the_arm_after_the_recheck_loses_a_wakeup.
Print Assumptions the_transposed_consumer_never_consumes_past_the_producer.
Print Assumptions the_transposed_consumer_stays_inside_its_budget.
Print Assumptions the_specification_consumer_stays_inside_its_budget.
Print Assumptions a_producer_that_never_signals_leaves_work_behind_a_sleep.
Print Assumptions the_same_schedule_with_a_signal_wakes_the_consumer.
Print Assumptions the_silent_publisher_moves_the_view_like_the_specification.
Print Assumptions the_silent_publisher_keeps_the_capacity_bound.
Print Assumptions the_silent_publisher_refuses_a_full_ring.
Print Assumptions the_signal_reset_coalesces_a_burst_to_one.
Print Assumptions the_drain_reset_sends_two_signals_for_one_arming.
Print Assumptions the_two_reset_arms_differ_only_on_the_second_publication.
Print Assumptions the_two_bursts_publish_the_same_two_items.
Print Assumptions the_specification_sleep_rule_reads_the_indices.
Print Assumptions the_specification_sleep_rule_is_the_contracts.
Print Assumptions the_counting_sleep_rule_is_refuted.
Print Assumptions the_counting_sleep_rule_declines_after_a_signal.
Print Assumptions the_counting_rule_and_the_index_rule_differ_on_a_coalesced_burst.
Print Assumptions the_specification_activation_is_bounded.
Print Assumptions the_greedy_consumer_leaves_its_budget.
Print Assumptions the_specification_consumer_stops_at_its_budget.
Print Assumptions the_greedy_consumer_still_drains_what_it_saw.
Print Assumptions world_eqb_refl.
Print Assumptions the_two_consumers_differ_only_at_the_drain.
Print Assumptions no_phase_is_both_producer_writable_and_consumer_readable.
Print Assumptions exactly_one_phase_admits_the_consumer.
Print Assumptions the_publication_consumes_writable_ownership.
Print Assumptions each_rejected_path_is_broken_somewhere.
Print Assumptions each_rejected_path_is_at_the_phase_that_names_it.
Print Assumptions the_state_setter_moves_only_the_state.
Print Assumptions the_lifecycle_rank_separates_the_six_states.
Print Assumptions there_are_three_advancer_obligations.
Print Assumptions the_specification_advancer_keeps_every_obligation.
Print Assumptions no_refuting_advancer_keeps_every_obligation.
Print Assumptions each_refuting_advancer_breaks_exactly_one.
Print Assumptions the_backward_advancer_breaks_the_lifecycle_alone.
Print Assumptions the_unvalidated_advancer_breaks_the_validation_alone.
Print Assumptions the_reader_advancer_breaks_the_reclamation_alone.
Print Assumptions the_skipping_advancer_breaks_the_lifecycle_alone.
Print Assumptions the_rank_only_reading_admits_the_skipping_advancer.
Print Assumptions the_two_lawfulness_readings_agree_on_everything_else.
Print Assumptions the_licensed_malformed_step_is_still_lawful.
Print Assumptions the_malformed_event_takes_the_contracts_own_step.
Print Assumptions the_malformed_event_is_admitted_at_one_state_only.
Print Assumptions the_copy_once_service_stays_inside_the_validated_extent.
Print Assumptions the_copy_once_service_reads_the_source_once.
Print Assumptions the_copy_once_service_does_not_vary_with_the_second_image.
Print Assumptions the_copy_once_service_refuses_an_overlong_length.
Print Assumptions the_revalidating_copier_answers_on_the_two_images.
Print Assumptions the_revalidating_copier_leaves_the_validated_extent.
Print Assumptions the_revalidating_copier_reads_the_source_twice.
Print Assumptions the_revalidating_copier_varies_with_the_second_image.
Print Assumptions the_revalidating_copier_still_refuses_an_overlong_length.
Print Assumptions the_two_buffer_images_differ_only_in_their_length.
Print Assumptions the_copy_once_run_is_the_one_the_specification_answers.
Print Assumptions the_revalidated_run_is_the_one_the_refuter_answers.
Print Assumptions charging_at_the_maximum_is_independent_of_the_arrival.
Print Assumptions charging_at_the_arrival_is_refuted.
Print Assumptions charging_at_the_arrival_still_bounds_a_run_inside_its_extent.
Print Assumptions the_batch_admits_what_the_ring_holds_and_refuses_the_rest.
Print Assumptions the_transactional_batch_rolls_back_what_it_enqueued.
Print Assumptions the_two_batches_agree_where_nothing_is_refused.
Print Assumptions a_batch_is_bounded_by_the_declared_maximum.
Print Assumptions there_are_thirteen_service_conjuncts.
Print Assumptions admission_is_exactly_the_absence_of_a_broken_conjunct.
Print Assumptions the_declared_service_is_admitted.
Print Assumptions every_spoiling_breaks_exactly_one_conjunct.
Print Assumptions no_spoiled_service_is_admitted.
Print Assumptions every_dropped_conjunct_admits_the_service_it_stopped_checking.
Print Assumptions no_dropped_conjunct_admits_another_spoiling.
Print Assumptions every_numeric_spoiling_moves_its_field_by_one.
Print Assumptions the_batch_conjunct_admits_one_and_refuses_none.
Print Assumptions the_cost_conjunct_reads_all_three_costs.
Print Assumptions the_declared_service_keeps_the_cost_conjunct.
Print Assumptions the_drain_reset_service_is_refused_at_the_notification_bound.
Print Assumptions the_drain_reset_service_keeps_every_other_conjunct.
Print Assumptions the_notification_bound_is_exceeded_at_every_variant.
Print Assumptions the_other_live_state_arm_is_admitted_too.
Print Assumptions the_two_live_state_arms_differ_on_a_slot_being_written.
Print Assumptions a_duplicate_live_identifier_is_refused_at_this_service.
Print Assumptions a_fresh_identifier_is_accepted_at_this_service.
Print Assumptions a_stale_generation_is_refused_at_this_service.
Print Assumptions the_live_state_arms_differ_on_an_identifier_being_written.
Print Assumptions the_drain_activations_empty_a_full_ring.
Print Assumptions the_drain_activations_are_the_least_such_count.
Print Assumptions the_service_alone_accounting_is_admitted_too.
Print Assumptions the_two_accountings_are_compared_at_one_cadence.
Print Assumptions the_service_alone_accounting_does_not_read_the_cadence.
Print Assumptions the_queueing_accounting_does_read_the_cadence.
Print Assumptions the_two_accountings_differ_by_the_queueing_term.
Print Assumptions the_two_accountings_are_never_equal.
Print Assumptions the_service_reproduces_the_contracts_activation_cost.
Print Assumptions the_activation_still_spends_the_declared_slot_budget.
Print Assumptions the_cleanup_sits_inside_the_declared_bound.
Print Assumptions every_held_reference_is_released_at_cleanup.
Print Assumptions the_cancellation_interval_is_the_contracts.
Print Assumptions every_declared_segment_count_is_inside_the_rings.
Print Assumptions the_staging_buffer_holds_the_declared_payload.
Print Assumptions the_declared_capacities.
Print Assumptions every_declared_record_states_its_segments_and_its_staging.
Print Assumptions every_declared_record_states_its_cleanup_and_its_releases.
Print Assumptions every_declared_record_states_its_three_costs.
Print Assumptions every_declared_record_states_one_progress_bound.
Print Assumptions the_declared_service_states_its_seven_other_fields.
Print Assumptions the_read_record_states_its_thirteen_fields.
Print Assumptions every_spoiling_moves_one_field_and_keeps_the_identity.
Print Assumptions the_two_services_carry_different_identities.
Print Assumptions the_four_ring_views.
Print Assumptions the_two_batch_views.
Print Assumptions the_four_worlds.
Print Assumptions the_slot_witnesses_carry_their_readers_and_their_validation.
Print Assumptions the_copy_witnesses_carry_their_lengths_and_their_extent.
Print Assumptions the_two_busy_slots.
Print Assumptions demo_capacities.
Print Assumptions demo_read_record.
Print Assumptions demo_slot.
Print Assumptions held_terminal_slot.
Print Assumptions unvalidated_submitted_slot.
Print Assumptions first_image.
Print Assumptions second_image.
Print Assumptions staged_run.
Print Assumptions revalidated_run.
Print Assumptions quiet_world.
Print Assumptions armed_world.
Print Assumptions backlogged_world.
Print Assumptions after_a_coalesced_burst.
Print Assumptions after_the_signal_arrived.
Print Assumptions full_view.
Print Assumptions brimming_view.
Print Assumptions empty_view.
Print Assumptions single_view.
Print Assumptions roomy_view.
Print Assumptions crowded_view.
Print Assumptions demo_service.
Print Assumptions service_alone.
Print Assumptions demo_descriptor.
Print Assumptions demo_completion.
Print Assumptions demo_op_declaration.
Print Assumptions demo_labels.
Print Assumptions demo_buffer_ref.
Print Assumptions the_descriptor_states_both_of_its_buffer_references.
Print Assumptions the_completion_states_its_byte_counts_and_its_metadata.
Print Assumptions the_descriptor_and_the_completion_carry_one_request.
Print Assumptions batch_of_one.
Print Assumptions batch_of_none.
Print Assumptions staging_only.
Print Assumptions the_declared_labels_are_inside_the_lattice.
Print Assumptions the_declared_record_is_the_contracts.
Print Assumptions the_buffer_reference_declares_its_direction_and_its_content.
Print Assumptions the_two_copy_runs.
