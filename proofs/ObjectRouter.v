(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ObjectRouter.v

   M6.3b's contained object router, at the two of its five subjects whose
   register entries carry an acceptance clause that decides and whose
   measurement is the router's own act rather than the storage layer's:
   R-10-005b's private namespaces and R-10-005c's live queries, read
   together with R-12-024a, which is the fabric entry itself, R-12-024e's
   resolution face, R-12-005's bounded ring, R-12-095's full-ring result,
   and R-08-046's declared bounded pool over the subscription queue.

   Which entries this file is stated over is a judgment and not a reading of
   its own cell, and the judgment is taken in three steps a reviewer can
   check one at a time. **Step one** reads the two entries off M6.3b's own
   cell, which cites them by id: R-10-005b for private namespaces and
   R-10-005c for live queries. **Step two** takes the ids those two spell
   out, which is a reading and not a judgment: R-10-005b's sentence cites
   R-10-003 for the one parametric index it instantiates, and R-10-005c's
   cites nothing. Of the one step two reaches, R-10-003 carries no statement
   below: this file states nothing about an index's internal structure, that
   being JournalIndex.v's subject and KeyspaceDomains.v's instantiation of
   it, and a derived scope that named it and stated nothing over it would be
   a scope a reviewer cannot check, so it is named here with what it is owed
   by. **Step three** is the judgment, and it reaches five entries by a noun
   one of the two uses and does not itself define. R-10-005b's "the
   presented namespace capability" reaches R-12-024a, which is where a
   caller's delegation of a namespace capability for the duration of a
   session is defined, and R-12-024e, which is where what a resolution may
   derive from it is defined; R-10-005c's "bounded SPSC ring" reaches
   R-12-005, which is where a bounded ring is defined, and R-12-095, which
   is where a full ring's one typed result is defined; and its "queue bound"
   reaches R-08-046, which is what a declared bounded pool is. A reviewer
   who disagrees with the scope disagrees with step three rather than with a
   statement below; steps one and two are checkable against the register's
   own text.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. Every quantity a composition
   fixes is a field of the Composition record rather than a literal or a
   top-level Parameter, which is what keeps the R-05-163 assumption gate
   green while leaving the decision where its owner can make it. Nothing is
   admitted and nothing is axiomatized: the Print Assumptions block at the
   end reports every shipped constant closed under the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. Nothing below is compiled,
   lowered, or run on either emulator; no key is persisted, no index is
   instantiated, no ring is created, no transaction commits and no
   subscription delivers. The computed checks are decided inside the kernel
   by conversion and print nothing.

   The one Require, and why it is a dependency rather than a citation.
   `Require Import RingContract.` names M6.4's generated ring interface,
   which M6.3b's dispatch note makes this item's start condition, and it is
   load-bearing at two places R-10-005c puts it. That entry delivers a live
   query's deltas *over a bounded SPSC ring*, so the answer a publication
   gets from the ring is that file's own closed `submit_result` and not a
   local twin of it, and the backpressure obligation below is stated over
   both of its constructors rather than over a boolean this file invented.
   And the declared queue bound has to fit the ring that carries it, so
   conjunct 3 of the composition's admission compares the bound against a
   declared capacity, which the demo instantiates with that file's own
   `ring_capacity`. Nothing else it exports is read, and no name declared
   here shadows one it exports, so the assumption block at the end audits
   the imported constants and not local twins of them, which is a hazard a
   `Require` carries and no gate reads. **What is not claimed is that the
   subscription rides the reference world**: that declaration's five
   operations are extents a storage server serves, a delta stream is none of
   them, and a live-query world is a world no landed declaration carries,
   exactly as M6.5b's cell says of the DMA world. Gap f records it.

   The two Requires this file declines, and the reason differs in each case.
   KeyspaceDomains.v states R-10-005b and R-10-005c at the *keyspace* and
   the *journal*, and its vocabulary meets this file's subject at a name
   rather than at a type: its `Delta` is indexed by the six-component
   storage key `K2`, which a router holds no part of, and reaching its
   `NsCap` would drag JournalIndex.v in behind it and put four hundred
   kilobytes of exported names in a position to shadow this file's
   silently. HandlerGraph.v is M6.3a's emitted graph and carries no
   namespace, no subscription and no key at all. So both are cited here and
   neither is required, and the seams between the three are drawn below
   rather than left for a reviewer to find.

   Where the seam with KeyspaceDomains.v runs, because the two files read
   two of the same sentences and do not state the same thing.

   * R-10-005b's "no capability is written into a key" has two readings and
     they are independent. That file reads it as *the persisted keyspace is
     a function of what was written and never of the authority under which
     it was written*, which is its reading 12 and is stated over a
     `Keyspace`. M6.3b's cell reads it as *no W record inside a declared
     index extent carries a tag*, which is a property of the write records
     the router emits and of the machine's tag plane. Neither implies the
     other, and this file machine-checks that:
     `the_two_readings_of_one_sentence_are_independent` exhibits a writer
     that is authority-independent and tagged and a second that is untagged
     and authority-dependent, each keeping the reading the other breaks.
     Finding a below is that independence reported at its entry.
   * R-10-005b's "no index spans confidentiality domains" is read there as a
     two-state agreement over the *contents* of a keyspace and here, as
     M6.3b's cell puts it, as a property the *composed image's declared
     extents* decide: no two declared extents carrying different domains
     overlap, and every record a key writer emits for an entry lands inside
     the extent declared for that entry's own domain and namespace. Those
     are two different obligations over two different objects and both are
     owed.
   * R-10-005c's overflow answer is bounded there and *counted* here.
     `AtMostOneMarker` over that file's emitter compares a marker count
     against 1; M6.3b's cell says *exactly one* marker and *no further
     delta*, which is strictly stronger in both halves and needs a
     subscription with a phase rather than an emitter with a list.
     `EmitsExactlyOneMarkerOnOverflow` is the first half and
     `NoFurtherDeltaAfterTheMarker` the second, and the resuming publisher
     below keeps every other obligation and breaks the second alone.
   * What this file does not restate is that file's own subjects: no index
     order, no journal, no crash cut, no transaction record, no extent
     encryption, no dedup digest and no freshness epoch appears below, and
     `Txn` here carries an identifier and a committed bit and nothing that
     would make it a second journal.

   What is deferred, and to which item. Three of the router's five subjects
   are not stated here and the reason differs.

   * Protocol-bound credential handles are M6.3b's third decided subject and
     are stated in CredentialHandles.v, which this item extends rather than
     duplicates. Nothing below carries a credential, a role, a transcript or
     a use count.
   * Intents and the deterministic translation cache have no predicate and
     the ground is the register's. No entry enumerates the intent variants
     R-12-013a calls closed, and no entry says whether a graph may carry two
     edges matching one intent; HandlerGraph.v exhibits a first-match and a
     last-match selector, each proved to keep every obligation the other
     keeps and the two differing observably on an ambiguous graph. A cache
     keyed on an intent therefore has no closed vocabulary to quantify over
     and no settled selection discipline to be deterministic against. This
     file states neither, carries no intent and no cache key, and reports
     both as open register acts at R-12-013a and R-12-024b rather than
     closing either by writing a predicate for it.
   * The measurements M6.3b's cell states are a member's and not an
     artifact's: a W record read out of a declared extent on the machine, a
     composed image's extents, an HTIF refusal verdict, and two runs of a
     subscription over an executable ring. None of them is decided here, all
     of them join M5.3's storage and an executable ring service, and nothing
     below narrows that predicate or claims any part of it discharged.

   Readings of the register this statement takes, each a reviewable judgment
   rather than a neutral transcription:

   1. A key's components are a composition's list and not a closed set. The
      entry keys a secondary index by "confidentiality domain and a stable
      namespace identifier as well as typed attribute value and object
      identity", which is four; R-10-005 puts the kind and the snapshot
      version in the key too, and KeyspaceDomains.v's `K2` carries six. So
      `en_components` is a list of values and no count is closed here, and
      the tag obligation is over whatever list the composition's key shape
      gives. The demo carries six, matching that file's shape, and the
      ledger pins the figure as the demo's rather than as a claim.
   2. A key is written into an extent the composed image declares, and the
      extent is what makes "inside a declared index extent" decidable. No
      entry states a layout, so `Extent` carries a base, a span, a domain
      and a namespace, the index for a domain and namespace pair is the
      extent declared for it, and an entry names the slot inside that extent
      it occupies. Gap b records that the placement is this file's.
   3. A tag is a bit on a word. R-10-005b's prohibition is over authority
      and the machine's authority is the validity tag, so `Word` carries a
      bit beside its bits and a write record carries an address and a word.
      Writing a tagged word is therefore a construction the obligation
      refutes rather than an absence nothing can express, which is reading 3
      of HandlerGraph.v taken at the tag plane.
   4. A delegation is a session and it dies with its epoch. R-12-024a has
      the caller delegate its namespace capability "for the duration of a
      session" and the service hold "no standing cross-caller namespace
      authority, each delegation ending with its session at the revocation
      epoch", so a `Session` carries an identifier, a capability and an
      epoch, a session is live exactly where its epoch is the composition's,
      and both defects are constructions: `standing_route` reads a
      capability the composition gave the fabric and `immortal_route` reads
      a session whose epoch has passed.
   5. The answer space is three-valued because three candidate disciplines
      inhabit it, not because an entry closes it. R-10-005b constrains what
      a query *returns* and nothing else, so a typed refusal, an empty
      result and a truncated grant all keep its clause while a holder tells
      them apart; `Answer` carries one constructor per candidate and
      `answer_discipline` is a field. Gap a is that question at its entry.
   6. Resolution is a per-ask relation and not a result set. R-12-024e makes
      resolution derive an object capability from the delegated namespace
      capability, and the bounded result set R-10-005c's own clause declares
      is a composition figure the router reads rather than a list this file
      quantifies over, so `result_bound` is a field the admission check
      reads and no theorem below enumerates a result set.
   7. A subscription has a phase, because "no further delta" is a property
      of what the subscription does *next*. R-10-005c's overflow answer is
      one marker, and a queue that carried the marker and then carried a
      delta would have emitted the marker and gone on publishing; the phase
      is what makes that a refutable construction.
   8. Backpressure is a two-state agreement. R-10-005c's "rather than
      backpressuring commit" is the statement that what a commit does is not
      a function of the subscription table's state nor of the ring's answer,
      so the obligation quantifies over two tables and two `submit_result`
      values and the two blocking committers below are refuted at exactly
      that quantifier.
   9. Every generated family is a list of constructions whose fallback past
      the last index is the specification's own. That is what makes a
      bounded quantifier over the index decide anything: a bound raised by
      one reaches the fallback, where the specification's construction
      satisfies the obligation the family is refuted for breaking, so the
      theorem fails rather than holding vacuously wider.
  10. Boolean rather than propositional wherever the witnesses must compute:
      the composition's admission conjuncts, the extent arithmetic, the
      derivability check and the queue arithmetic are decidable, so the
      generated families below are checked by conversion in the silent
      Example form rather than by a proof per member.

   The literals taken from the design, and there are three. The criterion is
   the same at each: one sentence of one entry names its members and closes
   the set, and the count sits beside the sentence rather than in prose.

   - R-10-005b's acceptance clause, "no capability is written into a key
     ..., no index spans confidentiality domains, and no query returns an
     object capability not derivable from the presented namespace
     capability", is three, so `all_namespace_prohibitions` is that list and
     `there_are_three_namespace_prohibitions` is its count. Each of the
     three carries its own obligation below and its own refuting
     construction, so dropping a constructor drops an obligation.
   - R-10-005c's delta alphabet is adds, removes and the one rescan-required
     marker, which names what a delta *is* rather than sampling what one
     might be, so `Delta` carries three constructors and no fourth. That is
     KeyspaceDomains.v's licence read at the router's object identity rather
     than at the storage key.
   - R-10-005c's overflow answer is *one* marker, so
     `EmitsExactlyOneMarkerOnOverflow` compares a count against 1 rather
     than bounding it by 1.

   Every other magnitude is a field: the declared index extents with their
   bases, spans, domains and namespaces; the queue bound, the result bound
   and the declared ring capacity; the live revocation epoch; the answer
   discipline; and the standing capability no obligation reads. The demo at
   the end instantiates each with a witness value that carries no
   composition claim, and the ledger pins every one of them.

   How the refutations are generated. A refutation is a seeded weakening the
   theorem must reject, so the families below are produced mechanically
   rather than authored one by one, which is DischargeSequence.v's method
   and HandlerGraph.v's, taken to an extent list and a subscription. Over
   the composition's five admission conjuncts: `spoiled_composition_at`
   moves one field of the demo composition to that conjunct's own boundary
   and `admit_without` drops one conjunct from the admission check, so the
   five are decided twice, once from the composition's side and once from
   the checker's. Over the key writers: one combinator at two axes, a key
   body and a placement offset, so the five writers are points of a grid and
   the three obligations are a table over them rather than fifteen
   sentences. Over the three answer disciplines: one router per discipline,
   each proved to mint nothing and the three proved pairwise
   distinguishable on one widening ask. The hand-authored refutations are
   the ones no index generates, being alternative constructions rather than
   mutations of a list.

   What this file deliberately does not author, with the entry that owes
   each decision. A register gap is reported, not closed:

   a. What a query the presented namespace capability does not admit is
      answered by. R-10-005b's acceptance clause constrains only what a
      query *returns*, "no object capability not derivable from the
      presented namespace capability", and a typed refusal, an empty result
      and a grant truncated to the presented capability's own rights all
      keep it. A holder distinguishes all three, and only one of them lets a
      caller tell an authority error from an empty namespace. The two landed
      readings already differ: KeyspaceDomains.v's resolver answers `nil`
      where the presented capability does not admit the query, and M6.3b's
      cell has the member report a refusal. `answer_discipline` is therefore
      a field, all three disciplines are exhibited, each is proved to mint
      nothing, and `the_answer_discipline_is_observable` machine-checks that
      the three differ on one ask. Owed at R-10-005b.
   b. Where a secondary index sits. R-10-005b requires an index per
      confidentiality domain and namespace and states no layout, so the
      extent list, its bases and its spans are fields and the placement rule
      below, one extent per domain and namespace pair with the entry naming
      its slot, is this file's. What is not this file's is the separation
      obligation over those extents, which is the entry's own sentence.
      Owed at R-10-005b.
   c. Whether a capability may be written outside a declared index extent.
      M6.3b's cell scopes the tag prohibition to a W record *inside a
      declared index extent*, and `CarriesNoTagInsideAnExtent` is scoped the
      same way, so a writer that emits a tagged word at an address no extent
      covers is refuted by the placement obligation and not by this one.
      Whether the entry means the narrower or the wider prohibition is not
      settled anywhere. Owed at R-10-005b.
   d. What the declared result bound bounds. R-10-005c gives a subscription
      "a composition-time result and queue bound" and the queue bound is
      what the overflow clause is stated against; nothing says whether the
      result bound bounds one delivery, one rescan's result set or the
      matching set itself. `result_bound` is a field the admission check
      requires positive; bounded_result_delivery additionally bounds each returned
      batch. A lifetime matching-set budget remains a query-engine join at
      R-10-005c.
   e. Whether the rescan-required marker occupies a slot of the declared
      queue bound or sits beside it. The reading taken below is
      KeyspaceDomains.v's, the marker inside the bound, so an overflowing
      publication is the bound's first steps and then the one marker and
      never one delta more than the bound admits. That file's gap e records
      the same question and this file takes the same arm rather than a
      second one. Owed at R-10-005c.
   f. Which interface world a live subscription's ring is. R-10-005c
      delivers deltas over a bounded SPSC ring and M6.4's landed
      declaration carries one world, whose five operations are extents a
      storage server serves and none of which is a delta stream. So the
      declared ring capacity is a field of the composition, the demo
      instantiates it with the reference world's own constant and claims
      nothing by doing so, and the world itself is owed at the declaration
      exactly as M6.5b's DMA world is. Owed at R-12-005.
   g. Every composition magnitude. The extent list with each extent's base,
      span, domain and namespace; the queue bound, the result bound and the
      declared ring capacity; the live epoch; the answer discipline; and the
      standing capability are fields, the demo instantiates each with a
      witness value that carries no composition claim, and the ledger pins
      every one of them.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary key writer, composition, router, publisher,
   committer, reboot or establishment, proved of the specification, and
   refuted of an alternative construction the register's own sentence
   excludes or, where the register does not exclude one, exhibited beside
   its siblings with the question reported rather than decided.
   Inhabitation is concrete: three declared extents over two confidentiality
   domains, an entry of six components sitting inside one of them, five
   compositions each breaking one admission conjunct, five key writers
   decided at three obligations apiece, a fabric of three sessions of which
   one is a peer's and one has outlived its epoch, four asks of which one
   sits exactly on the rights boundary and three widen, and a subscription
   whose publication lands exactly on its bound and one past it. The ledger
   at the end pins every field of every witness no obligation reads, which
   is the hazard M6.2a measured: a field nothing reads is a field a
   weakening moves in silence.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-164 R-05-165 R-05-166 R-08-046 R-10-003 R-10-005 R-10-005b
      R-10-005c R-12-005 R-12-095 R-12-013a R-12-024a R-12-024b R-12-024e
   SHA256: 0ae6b44441b9704601a23ed85f9e60a167e6de28a9072ffe59b6448ab38942b4
   (*| END derived |*)
   ========================================================================= *)

Require Import RingContract.

(* -------------------------------------------------------------------------
   List and boolean helpers, defined here rather than imported: the prelude
   carries the list type and not the library over it, and importing a module
   to save a dozen lines would put its assumptions inside the R-05-163
   gate's reach for no gain. Every name below is this file's own; none
   shadows one RingContract.v exports.
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

Fixpoint append_of {A : Type} (l m : list A) : list A :=
  match l with nil => m | cons x r => cons x (append_of r m) end.

Fixpoint take_of {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, _ => nil
  | _, nil => nil
  | S k, cons x r => cons x (take_of k r)
  end.

Fixpoint find_of {A : Type} (p : A -> bool) (l : list A) : option A :=
  match l with nil => None | cons x r => if p x then Some x else find_of p r end.

(* 0 through n-1, in that order: the index set every generated family below
   ranges over. *)
Fixpoint upto (n : nat) : list nat :=
  match n with 0 => nil | S k => append_of (upto k) (cons k nil) end.

(* A family's member at an index, with the specification's own construction
   past the last one (reading 9). *)
Fixpoint at_member {A : Type} (l : list A) (n : nat) (fallback : A) : A :=
  match l, n with
  | nil, _ => fallback
  | cons x _, 0 => x
  | cons _ r, S k => at_member r k fallback
  end.

(* One conjunct of a list replaced by a filler, which is the weakening every
   dropped-conjunct checker below is built from. *)
Fixpoint drop_at {A : Type} (n : nat) (l : list A) (filler : A) : list A :=
  match l, n with
  | nil, _ => nil
  | cons _ r, 0 => cons filler r
  | cons x r, S k => cons x (drop_at k r filler)
  end.

(* The last index a bound of n admits, which is where the overflow answer
   puts its final delta before the marker (gap e). *)
Definition before_last (n : nat) : nat := match n with 0 => 0 | S k => k end.

Fixpoint nat_list_eqb (l m : list nat) : bool :=
  match l, m with
  | nil, nil => true
  | cons x r, cons y t => andb (Nat.eqb x y) (nat_list_eqb r t)
  | _, _ => false
  end.

(* -------------------------------------------------------------------------
   The boolean and arithmetic lemmas the statements below read back out of
   their own conjunctions, one small lemma each rather than a tactic inside
   every theorem.
   ------------------------------------------------------------------------- *)

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof. destruct a, b; simpl; intros H; try discriminate H; split; reflexivity. Qed.

Lemma nat_eqb_refl : forall n : nat, Nat.eqb n n = true.
Proof. induction n as [| k IH]; simpl; [ reflexivity | exact IH ]. Qed.

Lemma nat_leb_refl : forall n : nat, Nat.leb n n = true.
Proof. induction n as [| k IH]; simpl; [ reflexivity | exact IH ]. Qed.

Lemma leb_succ_right : forall a b : nat, Nat.leb a b = true -> Nat.leb a (S b) = true.
Proof.
  induction a as [| k IH]; intros b H.
  - reflexivity.
  - destruct b as [| j]; [ discriminate H | ]. exact (IH j H).
Qed.

Lemma leb_trans : forall a b c : nat,
  Nat.leb a b = true -> Nat.leb b c = true -> Nat.leb a c = true.
Proof.
  induction a as [| k IH]; intros b c Hab Hbc.
  - reflexivity.
  - destruct b as [| j]; [ discriminate Hab | ].
    destruct c as [| i]; [ discriminate Hbc | ].
    exact (IH j i Hab Hbc).
Qed.

Lemma add_succ_right : forall a k : nat, a + S k = S (a + k).
Proof.
  induction a as [| n IH]; intros k; simpl;
    [ reflexivity | rewrite (IH k); reflexivity ].
Qed.

Lemma leb_add_right : forall a k : nat, Nat.leb a (a + k) = true.
Proof. induction a as [| n IH]; intros k; simpl; [ reflexivity | exact (IH k) ]. Qed.

Lemma leb_add_left : forall k a b : nat,
  Nat.leb a b = true -> Nat.leb (k + a) (k + b) = true.
Proof. induction k as [| n IH]; intros a b H; simpl; [ exact H | exact (IH a b H) ]. Qed.

Lemma add_assoc_nat : forall a b c : nat, a + b + c = a + (b + c).
Proof.
  induction a as [| n IH]; intros b c; simpl;
    [ reflexivity | rewrite (IH b c); reflexivity ].
Qed.

Lemma all_of_cons : forall (A : Type) (p : A -> bool) (x : A) (l : list A),
  p x = true -> all_of p l = true -> all_of p (cons x l) = true.
Proof. intros A p x l Hx Hl. simpl. rewrite Hx. exact Hl. Qed.

Lemma all_of_weaken : forall (A : Type) (p q : A -> bool) (l : list A),
  (forall x : A, p x = true -> q x = true) -> all_of p l = true -> all_of q l = true.
Proof.
  intros A p q l H. induction l as [| x r IH]; intros Hl.
  - reflexivity.
  - simpl in Hl. destruct (andb_split _ _ Hl) as [ Hx Hr ].
    apply all_of_cons; [ exact (H x Hx) | exact (IH Hr) ].
Qed.

Lemma all_of_map : forall (A B : Type) (p : B -> bool) (f : A -> B) (l : list A),
  all_of p (map_over f l) = all_of (fun x => p (f x)) l.
Proof.
  intros A B p f. induction l as [| x r IH]; simpl;
    [ reflexivity | rewrite IH; reflexivity ].
Qed.

Lemma all_of_const : forall (A : Type) (p : A -> bool) (l : list A),
  (forall x : A, p x = true) -> all_of p l = true.
Proof.
  intros A p l H. induction l as [| x r IH]; simpl;
    [ reflexivity | rewrite (H x); exact IH ].
Qed.

Lemma all_of_take : forall (A : Type) (p : A -> bool) (n : nat) (l : list A),
  all_of p l = true -> all_of p (take_of n l) = true.
Proof.
  intros A p. induction n as [| k IH]; intros l H.
  - destruct l; reflexivity.
  - destruct l as [| x r]; [ reflexivity | ].
    simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    change (take_of (S k) (cons x r)) with (cons x (take_of k r)).
    apply all_of_cons; [ exact Hx | exact (IH r Hr) ].
Qed.

Lemma count_take_bounded : forall (A : Type) (n : nat) (l : list A),
  Nat.leb (count_of (take_of n l)) n = true.
Proof.
  intros A. induction n as [| k IH]; intros l.
  - destruct l; reflexivity.
  - destruct l as [| x r]; [ reflexivity | ].
    change (count_of (take_of (S k) (cons x r)))
      with (S (count_of (take_of k r))).
    exact (IH r).
Qed.

Lemma count_append_one : forall (A : Type) (l : list A) (x : A),
  count_of (append_of l (cons x nil)) = S (count_of l).
Proof.
  intros A. induction l as [| y r IH]; intros x; simpl;
    [ reflexivity | rewrite (IH x); reflexivity ].
Qed.

Lemma count_append_two : forall (A : Type) (l : list A) (x y : A),
  count_of (append_of l (cons x (cons y nil))) = S (S (count_of l)).
Proof.
  intros A. induction l as [| z r IH]; intros x y; simpl;
    [ reflexivity | rewrite (IH x y); reflexivity ].
Qed.

(* The two arithmetic shapes every overflow answer below ends at: a prefix
   of the bound's own length plus the one marker, and the twin publisher's
   shorter prefix plus two. Both are stated over a variable bound rather
   than over a projection, so the case split is on a name. *)
Lemma bound_take_plus_one : forall (A : Type) (n : nat) (l : list A),
  Nat.ltb 0 n = true ->
  Nat.leb (S (count_of (take_of (before_last n) l))) n = true.
Proof.
  intros A n l H. destruct n as [| k]; [ discriminate H | ].
  exact (count_take_bounded A k l).
Qed.

Lemma bound_take_plus_two : forall (A : Type) (n : nat) (l : list A),
  Nat.leb 2 n = true ->
  Nat.leb (S (S (count_of (take_of (before_last (before_last n)) l)))) n = true.
Proof.
  intros A n l H. destruct n as [| k]; [ discriminate H | ].
  destruct k as [| j]; [ discriminate H | ].
  exact (count_take_bounded A j l).
Qed.

Lemma count_map_over : forall (A B : Type) (f : A -> B) (l : list A),
  count_of (map_over f l) = count_of l.
Proof.
  intros A B f. induction l as [| x r IH]; simpl;
    [ reflexivity | rewrite IH; reflexivity ].
Qed.

Lemma filter_append : forall (A : Type) (p : A -> bool) (l m : list A),
  filter_of p (append_of l m) = append_of (filter_of p l) (filter_of p m).
Proof.
  intros A p. induction l as [| x r IH]; intros m.
  - reflexivity.
  - simpl. destruct (p x); simpl; rewrite (IH m); reflexivity.
Qed.

Lemma filter_none : forall (A : Type) (p : A -> bool) (l : list A),
  all_of (fun x => negb (p x)) l = true -> filter_of p l = nil.
Proof.
  intros A p. induction l as [| x r IH]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    simpl. destruct (p x); [ discriminate Hx | exact (IH Hr) ].
Qed.

(* The helpers' own boundaries, so that no lemma above rests on a case its
   own definition never reaches. *)
Example the_empty_conjunction_holds : all_of (fun b : bool => b) nil = true := eq_refl.
Example the_empty_disjunction_fails : any_of (fun b : bool => b) nil = false := eq_refl.
Example nothing_has_length_zero : count_of (nil : list nat) = 0 := eq_refl.
Example before_last_of_nothing : before_last 0 = 0 := eq_refl.
Example the_index_set_of_three : upto 3 = cons 0 (cons 1 (cons 2 nil)) := eq_refl.
Example the_fallback_is_reached_past_the_last_index :
  at_member (cons 1 (cons 2 nil)) 5 9 = 9 := eq_refl.
Example nothing_is_found_in_nothing :
  find_of (fun n : nat => Nat.eqb n 0) nil = None := eq_refl.
Example taking_more_than_there_is_takes_all :
  take_of 5 (cons 1 (cons 2 nil)) = cons 1 (cons 2 nil) := eq_refl.
Example dropping_past_the_last_conjunct_drops_nothing :
  drop_at 4 (cons false (cons false nil)) true = cons false (cons false nil) := eq_refl.
Example two_lists_agree_only_element_by_element :
  nat_list_eqb (cons 1 (cons 2 nil)) (cons 1 (cons 2 nil)) = true
  /\ nat_list_eqb (cons 1 (cons 2 nil)) (cons 1 (cons 3 nil)) = false
  /\ nat_list_eqb (cons 1 nil) (cons 1 (cons 2 nil)) = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   The closed enumerations, each with the sentence that closes it.
   ========================================================================= *)

(* R-10-005b's acceptance clause, as the three prohibitions its own sentence
   names. Each carries an obligation below and a refuting construction. *)
Inductive Prohibition : Type :=
| NoCapabilityInAKey
| NoIndexSpansTwoDomains
| NoQueryWidensThePresentedCapability.

Definition all_namespace_prohibitions : list Prohibition :=
  cons NoCapabilityInAKey
  (cons NoIndexSpansTwoDomains (cons NoQueryWidensThePresentedCapability nil)).

Example there_are_three_namespace_prohibitions :
  count_of all_namespace_prohibitions = 3 := eq_refl.

Definition prohibition_eqb (a b : Prohibition) : bool :=
  match a, b with
  | NoCapabilityInAKey, NoCapabilityInAKey => true
  | NoIndexSpansTwoDomains, NoIndexSpansTwoDomains => true
  | NoQueryWidensThePresentedCapability, NoQueryWidensThePresentedCapability => true
  | _, _ => false
  end.

Example the_prohibitions_are_pairwise_distinct :
  all_of (fun p => Nat.eqb (count_of (filter_of (prohibition_eqb p)
                                                all_namespace_prohibitions)) 1)
         all_namespace_prohibitions = true := eq_refl.

(* R-10-005c's delta alphabet, closed by that entry's own sentence: ordered
   add and remove deltas, and the one rescan-required marker overflow emits.
   No entry of this register names a third delta form. *)
Inductive Delta : Type :=
| DeltaAdded (obj : nat)
| DeltaRemoved (obj : nat)
| DeltaRescan.

Definition is_rescan (d : Delta) : bool :=
  match d with
  | DeltaAdded _ => false
  | DeltaRemoved _ => false
  | DeltaRescan => true
  end.

(* Reading 7: the subscription's phase, which is what makes "no further
   delta" a property of the next publication rather than of this one. *)
Inductive Phase : Type :=
| PhaseLive
| PhaseRescanRequired.

(* Reading 5 and gap a: one constructor per candidate answer discipline,
   carrying no claim that R-10-005b closes the answer set. *)
Inductive Discipline : Type :=
| RefuseTyped
| AnswerEmpty
| GrantTruncated.

Definition all_disciplines : list Discipline :=
  cons RefuseTyped (cons AnswerEmpty (cons GrantTruncated nil)).

Example there_are_three_candidate_disciplines :
  count_of all_disciplines = 3 := eq_refl.

(* =========================================================================
   The machine's own words, the extents a composed image declares, and the
   capabilities a session carries.
   ========================================================================= *)

(* Reading 3: a word is bits and the validity tag beside them. *)
Record Word : Type := {
  w_bits : nat;
  w_tag : bool
}.

Definition plain (n : nat) : Word := {| w_bits := n; w_tag := false |}.
Definition sealed (n : nat) : Word := {| w_bits := n; w_tag := true |}.

Record WriteRecord : Type := {
  wr_address : nat;
  wr_word : Word
}.

(* Reading 2: the extent a composed image declares for one secondary index,
   which is one confidentiality domain's one namespace. *)
Record Extent : Type := {
  ex_base : nat;
  ex_span : nat;
  ex_domain : nat;
  ex_space : nat
}.

Definition inside (x : Extent) (a : nat) : bool :=
  andb (Nat.leb (ex_base x) a) (Nat.ltb a (ex_base x + ex_span x)).

(* Two extents overlap when each begins before the other ends, which is a
   question only about extents that hold something: an extent of span zero
   covers no address and therefore overlaps nothing, including itself. *)
Definition overlaps (x y : Extent) : bool :=
  andb (andb (Nat.ltb 0 (ex_span x)) (Nat.ltb 0 (ex_span y)))
       (andb (Nat.ltb (ex_base x) (ex_base y + ex_span y))
             (Nat.ltb (ex_base y) (ex_base x + ex_span x))).

(* Reading 1: the key's components are a list the composition's key shape
   gives, and this file closes no count over them. *)
Record Entry : Type := {
  en_domain : nat;
  en_space : nat;
  en_slot : nat;
  en_components : list nat
}.

(* Reading 4: the namespace capability a caller delegates for a session. *)
Record NsCap : Type := {
  ns_domain : nat;
  ns_space : nat;
  ns_rights : nat
}.

Record ObjCap : Type := {
  oc_domain : nat;
  oc_space : nat;
  oc_object : nat;
  oc_rights : nat
}.

Record Ask : Type := {
  ak_domain : nat;
  ak_space : nat;
  ak_object : nat;
  ak_rights : nat
}.

Record Session : Type := {
  se_id : nat;
  se_cap : NsCap;
  se_epoch : nat
}.

Definition Fabric : Type := list Session.

Record Subscription : Type := {
  sb_id : nat;
  sb_domain : nat;
  sb_space : nat;
  sb_phase : Phase;
  sb_queue : list Delta
}.

Record Txn : Type := {
  tx_id : nat;
  tx_committed : bool
}.

(* The three answers the three candidate disciplines give (reading 5). *)
Inductive Answer : Type :=
| Granted (o : ObjCap)
| EmptyResult
| Refused.

(* =========================================================================
   The composition: everything the register leaves to composition. Fields
   rather than Parameters, because a top-level Parameter prints as an
   assumption and fails the R-05-163 gate.
   ========================================================================= *)

Record Composition : Type := {

  (* --- R-10-005b's declared index extents, one per domain and namespace - *)

  index_extents : list Extent;

  (* --- R-10-005c's composition-time queue and result bounds (gap d) ----- *)

  queue_bound : nat;
  result_bound : nat;

  (* --- R-12-005's bounded ring, inside whose declared capacity the
         subscription's queue sits. Which world that ring is remains open
         (gap f); the demo instantiates this with RingContract.v's own
         reference constant and claims nothing by doing so ---------------- *)

  ring_capacity_declared : nat;

  (* --- R-12-024a's revocation epoch, the one a live delegation carries -- *)

  live_epoch : nat;

  (* --- the answer discipline no entry decides (gap a) ------------------- *)

  answer_discipline : Discipline;

  (* --- the standing cross-caller authority R-12-024a says the service
         does not hold, carried so that holding one is a construction
         rather than an absence nothing can refute ------------------------ *)

  standing_cap : NsCap
}.

(* One constructor for the demo and for every variant of it below, so that a
   spoiled composition moves one figure and carries the demo's everywhere
   else. *)
Definition remake (xs : list Extent) (qb rb cap ep : nat)
                  (d : Discipline) (sc : NsCap) : Composition :=
  {| index_extents := xs; queue_bound := qb; result_bound := rb;
     ring_capacity_declared := cap; live_epoch := ep;
     answer_discipline := d; standing_cap := sc |}.

(* =========================================================================
   What makes a composition admissible: five conjuncts, held as a list
   rather than as a nest of conjunctions. A checker that drops one is
   `admit_without` at that index and a composition that breaks one is
   `spoiled_composition_at` at that index, so the five are decided from both
   sides and neither family is authored.
   ========================================================================= *)

Definition extents_separated (xs : list Extent) : bool :=
  all_of (fun x => all_of (fun y =>
            implb (negb (Nat.eqb (ex_domain x) (ex_domain y)))
                  (negb (overlaps x y))) xs) xs.

Definition composition_conjuncts (c : Composition) : list bool :=
  (* 0: R-10-005b's "no index spans confidentiality domains", read as
     M6.3b's cell reads it, over the composed image's declared extents. *)
  cons (extents_separated (index_extents c))
  (* 1: an extent that covers no address is an index the composition did
     not place, and the separation above would hold of it vacuously. *)
  (cons (all_of (fun x => Nat.ltb 0 (ex_span x)) (index_extents c))
  (* 2: R-08-046's declared bounded pool over the subscription queue. A
     bound of zero is a queue that admits no delta and no marker either. *)
  (cons (Nat.ltb 0 (queue_bound c))
  (* 3: R-10-005c with R-12-005. The declared queue bound is delivered over
     a bounded ring, so a bound past that ring's declared capacity is a
     queue the composition did not size (gap f). *)
  (cons (Nat.leb (queue_bound c) (ring_capacity_declared c))
  (* 4: R-10-005c's composition-time result bound, required positive and
     read no further here (gap d). *)
  (cons (Nat.ltb 0 (result_bound c)) nil)))).

Definition admissible_composition (c : Composition) : bool :=
  all_of (fun b => b) (composition_conjuncts c).

(* How many of the five a composition breaks: the measure that makes "this
   weakening broke exactly one conjunct" a computation rather than a claim. *)
Definition conjuncts_broken (c : Composition) : nat :=
  count_of (filter_of negb (composition_conjuncts c)).

Example there_are_five_composition_conjuncts :
  forall c : Composition, count_of (composition_conjuncts c) = 5.
Proof. intros c. reflexivity. Qed.

Definition admit_without (k : nat) (c : Composition) : bool :=
  all_of (fun b => b) (drop_at k (composition_conjuncts c) true).

Definition SeparatesTheDomains (c : Composition) : Prop :=
  extents_separated (index_extents c) = true.

(*| discharges: R-10-005b |*)
Theorem an_admitted_composition_separates_the_domains :
  forall c : Composition, admissible_composition c = true -> SeparatesTheDomains c.
Proof.
  intros c H. unfold admissible_composition, composition_conjuncts in H.
  simpl in H. destruct (andb_split _ _ H) as [ H0 _ ]. exact H0.
Qed.

Theorem an_admitted_composition_places_every_index :
  forall c : Composition, admissible_composition c = true ->
    all_of (fun x => Nat.ltb 0 (ex_span x)) (index_extents c) = true.
Proof.
  intros c H. unfold admissible_composition, composition_conjuncts in H.
  simpl in H. destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ H2 _ ]. exact H2.
Qed.

(*| discharges: R-08-046 |*)
Theorem an_admitted_composition_sizes_its_queue :
  forall c : Composition, admissible_composition c = true ->
    Nat.ltb 0 (queue_bound c) = true
    /\ Nat.leb (queue_bound c) (ring_capacity_declared c) = true
    /\ Nat.ltb 0 (result_bound c) = true.
Proof.
  intros c H. unfold admissible_composition, composition_conjuncts in H.
  simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ]. clear H.
  destruct (andb_split _ _ H1) as [ _ H2 ]. clear H1.
  destruct (andb_split _ _ H2) as [ H3 H4 ]. clear H2.
  destruct (andb_split _ _ H4) as [ H5 H6 ]. clear H4.
  destruct (andb_split _ _ H6) as [ H7 _ ]. clear H6.
  exact (conj H3 (conj H5 H7)).
Qed.

(* =========================================================================
   R-10-005b's first two prohibitions, at the places M6.3b's cell puts them:
   no W record inside a declared index extent carries a tag, and every
   record lands inside the extent the composed image declared for its own
   domain and namespace.

   The five writers are points of one grid rather than five authored
   constructions: `placed` takes a key body and a placement offset, the
   bodies are four and the offsets two, and the five the file names are the
   pairs that decide something.
   ========================================================================= *)

Definition extent_matches (d s : nat) (x : Extent) : bool :=
  andb (Nat.eqb (ex_domain x) d) (Nat.eqb (ex_space x) s).

Definition extent_for (c : Composition) (d s : nat) : option Extent :=
  find_of (extent_matches d s) (index_extents c).

Fixpoint records_at (a : nat) (ws : list Word) : list WriteRecord :=
  match ws with
  | nil => nil
  | cons w r => cons {| wr_address := a; wr_word := w |} (records_at (S a) r)
  end.

Fixpoint replace_last_word (w : Word) (l : list Word) : list Word :=
  match l with
  | nil => nil
  | cons x r => match r with
                | nil => cons w nil
                | cons _ _ => cons x (replace_last_word w r)
                end
  end.

Lemma count_replace_last_word : forall (w : Word) (l : list Word),
  count_of (replace_last_word w l) = count_of l.
Proof.
  intros w. induction l as [| x r IH].
  - reflexivity.
  - destruct r as [| y t]; [ reflexivity | ].
    change (count_of (replace_last_word w (cons x (cons y t))))
      with (S (count_of (replace_last_word w (cons y t)))).
    rewrite IH. reflexivity.
Qed.

Lemma replace_last_word_untagged : forall (w : Word) (l : list Word),
  negb (w_tag w) = true -> all_of (fun u => negb (w_tag u)) l = true ->
  all_of (fun u => negb (w_tag u)) (replace_last_word w l) = true.
Proof.
  intros w. induction l as [| x r IH]; intros Hw Hl.
  - reflexivity.
  - simpl in Hl. destruct (andb_split _ _ Hl) as [ Hx Hr ].
    destruct r as [| y t].
    + change (replace_last_word w (cons x nil)) with (cons w nil).
      apply all_of_cons; [ exact Hw | reflexivity ].
    + change (replace_last_word w (cons x (cons y t)))
        with (cons x (replace_last_word w (cons y t))).
      apply all_of_cons; [ exact Hx | exact (IH Hw Hr) ].
Qed.

Lemma map_over_plain_untagged : forall l : list nat,
  all_of (fun w => negb (w_tag w)) (map_over plain l) = true.
Proof.
  intros l. rewrite (all_of_map nat Word (fun w => negb (w_tag w)) plain l).
  apply all_of_const. intros x. reflexivity.
Qed.

Lemma records_at_untagged : forall (ws : list Word) (a : nat),
  all_of (fun w => negb (w_tag w)) ws = true ->
  all_of (fun r => negb (w_tag (wr_word r))) (records_at a ws) = true.
Proof.
  induction ws as [| w rest IH]; intros a H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hw Hr ].
    change (records_at a (cons w rest))
      with (cons {| wr_address := a; wr_word := w |} (records_at (S a) rest)).
    apply all_of_cons; [ exact Hw | exact (IH (S a) Hr) ].
Qed.

Lemma records_at_inside : forall (ws : list Word) (x : Extent) (a : nat),
  Nat.leb (ex_base x) a = true ->
  Nat.leb (a + count_of ws) (ex_base x + ex_span x) = true ->
  all_of (fun r => inside x (wr_address r)) (records_at a ws) = true.
Proof.
  induction ws as [| w rest IH]; intros x a Hlo Hhi.
  - reflexivity.
  - change (count_of (cons w rest)) with (S (count_of rest)) in Hhi.
    rewrite add_succ_right in Hhi.
    assert (Hlt : Nat.ltb a (ex_base x + ex_span x) = true).
    { exact (leb_trans (S a) (S (a + count_of rest)) (ex_base x + ex_span x)
               (leb_add_right (S a) (count_of rest)) Hhi). }
    assert (Hrest : all_of (fun r => inside x (wr_address r))
                           (records_at (S a) rest) = true).
    { exact (IH x (S a) (leb_succ_right _ _ Hlo) Hhi). }
    change (records_at a (cons w rest))
      with (cons {| wr_address := a; wr_word := w |} (records_at (S a) rest)).
    apply all_of_cons; [ | exact Hrest ].
    unfold inside. simpl. rewrite Hlo. rewrite Hlt. reflexivity.
Qed.

(* The grid's two axes. A body is what the key's words are; an offset is
   where inside the declared extent they go. *)
Definition KeyBody : Type := NsCap -> Entry -> list Word.
Definition KeyOffset : Type := Extent -> Entry -> nat.
Definition KeyWriter : Type := Composition -> NsCap -> Entry -> list WriteRecord.

Definition placed (body : KeyBody) (offset : KeyOffset) : KeyWriter :=
  fun c n e => match extent_for c (en_domain e) (en_space e) with
               | None => nil
               | Some x => records_at (offset x e) (body n e)
               end.

Lemma placed_at : forall (body : KeyBody) (offset : KeyOffset) (c : Composition)
    (n : NsCap) (e : Entry) (x : Extent),
  extent_for c (en_domain e) (en_space e) = Some x ->
  placed body offset c n e = records_at (offset x e) (body n e).
Proof. intros body offset c n e x H. unfold placed. rewrite H. reflexivity. Qed.

Lemma placed_unplaced : forall (body : KeyBody) (offset : KeyOffset)
    (c : Composition) (n : NsCap) (e : Entry),
  extent_for c (en_domain e) (en_space e) = None -> placed body offset c n e = nil.
Proof. intros body offset c n e H. unfold placed. rewrite H. reflexivity. Qed.

Definition slot_offset : KeyOffset := fun x e => ex_base x + en_slot e.
Definition past_offset : KeyOffset := fun x _ => ex_base x + ex_span x.

Definition plain_key : KeyBody := fun _ e => map_over plain (en_components e).
Definition sealed_key : KeyBody := fun _ e => map_over sealed (en_components e).
Definition capability_key : KeyBody := fun n e =>
  replace_last_word (sealed (ns_rights n)) (map_over plain (en_components e)).
Definition stamped_key : KeyBody := fun n e =>
  replace_last_word (plain (ns_rights n)) (map_over plain (en_components e)).

(* The specification: the key's own component words, at the slot the entry
   names inside the extent the composition declared for it. *)
Definition spec_write : KeyWriter := placed plain_key slot_offset.

(* A key every word of which carries the validity tag, which is what a
   capability written into a key is on this machine. Every address and every
   bit pattern is the specification's; the tag alone moves. *)
Definition sealing_write : KeyWriter := placed sealed_key slot_offset.

(* A key carrying the presented capability itself, tagged, in the slot the
   key's last component occupies: the construction M6.3b's cell names. *)
Definition capability_write : KeyWriter := placed capability_key slot_offset.

(* The presented capability's rights written into a key as an ordinary
   untagged number, which is what KeyspaceDomains.v's stamped persister does
   at the keyspace. No tag is set, so the reading M6.3b's cell takes is
   kept and the reading that file takes is broken. *)
Definition stamped_write : KeyWriter := placed stamped_key slot_offset.

(* A writer that puts the key at the first address past the extent declared
   for it, which is an index reaching where the composition placed another. *)
Definition spilling_write : KeyWriter := placed plain_key past_offset.

(* M6.3b's cell's own sentence, and it is scoped to a record inside a
   declared extent rather than to every record (gap c). *)
Definition record_inside_some_extent (c : Composition) (r : WriteRecord) : bool :=
  any_of (fun x => inside x (wr_address r)) (index_extents c).

Definition CarriesNoTagInsideAnExtent (kw : KeyWriter) : Prop :=
  forall (c : Composition) (n : NsCap) (e : Entry),
    all_of (fun r => implb (record_inside_some_extent c r)
                           (negb (w_tag (wr_word r)))) (kw c n e) = true.

(* An entry whose slot and component list fit the extent declared for it.
   The placement obligation is scoped to those, because a component list
   longer than the extent it was placed in is a composition defect and not
   a writer's. *)
Definition entry_fits (x : Extent) (e : Entry) : bool :=
  Nat.leb (en_slot e + count_of (en_components e)) (ex_span x).

Definition PlacesInsideTheDeclaredExtent (kw : KeyWriter) : Prop :=
  forall (c : Composition) (n : NsCap) (e : Entry) (x : Extent),
    extent_for c (en_domain e) (en_space e) = Some x ->
    entry_fits x e = true ->
    all_of (fun r => inside x (wr_address r)) (kw c n e) = true.

(* KeyspaceDomains.v's reading 12, taken at the write record rather than at
   the keyspace, and stated here only so that the independence of the two
   readings of one sentence is machine-checked rather than asserted. *)
Definition WritesNoAuthority (kw : KeyWriter) : Prop :=
  forall (c : Composition) (n1 n2 : NsCap) (e : Entry), kw c n1 e = kw c n2 e.

(* The three obligations, each proved of a whole class of grid points rather
   than of one writer, so that adding a body or an offset costs a lemma
   application and not a proof. *)
Lemma placed_keeps_the_tag_reading : forall (body : KeyBody) (offset : KeyOffset),
  (forall (n : NsCap) (e : Entry),
     all_of (fun w => negb (w_tag w)) (body n e) = true) ->
  CarriesNoTagInsideAnExtent (placed body offset).
Proof.
  intros body offset Hbody c n e.
  destruct (extent_for c (en_domain e) (en_space e)) as [ x | ] eqn:Hx.
  - rewrite (placed_at body offset c n e x Hx).
    apply (all_of_weaken WriteRecord (fun r => negb (w_tag (wr_word r)))).
    + intros r H. rewrite H. destruct (record_inside_some_extent c r); reflexivity.
    + exact (records_at_untagged (body n e) (offset x e) (Hbody n e)).
  - rewrite (placed_unplaced body offset c n e Hx). reflexivity.
Qed.

Lemma placed_at_the_slot_stays_inside : forall body : KeyBody,
  (forall (n : NsCap) (e : Entry),
     count_of (body n e) = count_of (en_components e)) ->
  PlacesInsideTheDeclaredExtent (placed body slot_offset).
Proof.
  intros body Hcount c n e x Hx Hfit.
  rewrite (placed_at body slot_offset c n e x Hx).
  apply records_at_inside.
  - exact (leb_add_right (ex_base x) (en_slot e)).
  - unfold slot_offset. rewrite (Hcount n e).
    rewrite (add_assoc_nat (ex_base x) (en_slot e) (count_of (en_components e))).
    exact (leb_add_left (ex_base x) (en_slot e + count_of (en_components e))
                        (ex_span x) Hfit).
Qed.

Lemma placed_from_a_closed_body_writes_no_authority :
  forall (body : KeyBody) (offset : KeyOffset),
    (forall (n1 n2 : NsCap) (e : Entry), body n1 e = body n2 e) ->
    WritesNoAuthority (placed body offset).
Proof.
  intros body offset Hbody c n1 n2 e. unfold placed.
  destruct (extent_for c (en_domain e) (en_space e)) as [ x | ]; [ | reflexivity ].
  rewrite (Hbody n1 n2 e). reflexivity.
Qed.

Lemma plain_key_untagged : forall (n : NsCap) (e : Entry),
  all_of (fun w => negb (w_tag w)) (plain_key n e) = true.
Proof. intros n e. exact (map_over_plain_untagged (en_components e)). Qed.

Lemma stamped_key_untagged : forall (n : NsCap) (e : Entry),
  all_of (fun w => negb (w_tag w)) (stamped_key n e) = true.
Proof.
  intros n e. unfold stamped_key.
  apply replace_last_word_untagged;
    [ reflexivity | exact (map_over_plain_untagged (en_components e)) ].
Qed.

Lemma plain_key_count : forall (n : NsCap) (e : Entry),
  count_of (plain_key n e) = count_of (en_components e).
Proof. intros n e. exact (count_map_over nat Word plain (en_components e)). Qed.

Lemma sealed_key_count : forall (n : NsCap) (e : Entry),
  count_of (sealed_key n e) = count_of (en_components e).
Proof. intros n e. exact (count_map_over nat Word sealed (en_components e)). Qed.

Lemma capability_key_count : forall (n : NsCap) (e : Entry),
  count_of (capability_key n e) = count_of (en_components e).
Proof.
  intros n e. unfold capability_key.
  rewrite (count_replace_last_word (sealed (ns_rights n))
             (map_over plain (en_components e))).
  exact (count_map_over nat Word plain (en_components e)).
Qed.

Lemma stamped_key_count : forall (n : NsCap) (e : Entry),
  count_of (stamped_key n e) = count_of (en_components e).
Proof.
  intros n e. unfold stamped_key.
  rewrite (count_replace_last_word (plain (ns_rights n))
             (map_over plain (en_components e))).
  exact (count_map_over nat Word plain (en_components e)).
Qed.

(*| discharges: R-10-005b |*)
Theorem the_specification_writes_no_tag_inside_an_extent :
  CarriesNoTagInsideAnExtent spec_write.
Proof. exact (placed_keeps_the_tag_reading plain_key slot_offset plain_key_untagged). Qed.

(*| discharges: R-10-005b |*)
Theorem the_specification_places_inside_the_declared_extent :
  PlacesInsideTheDeclaredExtent spec_write.
Proof. exact (placed_at_the_slot_stays_inside plain_key plain_key_count). Qed.

Theorem the_specification_writes_no_authority : WritesNoAuthority spec_write.
Proof.
  apply (placed_from_a_closed_body_writes_no_authority plain_key slot_offset).
  intros n1 n2 e. reflexivity.
Qed.

(* Every construction's twin: what each keeps, proved rather than assumed,
   so that the obligation it breaks is the one defect it carries. *)
Theorem the_sealing_writer_keeps_the_authority_reading :
  WritesNoAuthority sealing_write.
Proof.
  apply (placed_from_a_closed_body_writes_no_authority sealed_key slot_offset).
  intros n1 n2 e. reflexivity.
Qed.

Theorem the_sealing_writer_keeps_the_placement :
  PlacesInsideTheDeclaredExtent sealing_write.
Proof. exact (placed_at_the_slot_stays_inside sealed_key sealed_key_count). Qed.

Theorem the_capability_writer_keeps_the_placement :
  PlacesInsideTheDeclaredExtent capability_write.
Proof. exact (placed_at_the_slot_stays_inside capability_key capability_key_count). Qed.

Theorem the_stamped_writer_keeps_the_tag_reading :
  CarriesNoTagInsideAnExtent stamped_write.
Proof. exact (placed_keeps_the_tag_reading stamped_key slot_offset stamped_key_untagged). Qed.

Theorem the_stamped_writer_keeps_the_placement :
  PlacesInsideTheDeclaredExtent stamped_write.
Proof. exact (placed_at_the_slot_stays_inside stamped_key stamped_key_count). Qed.

Theorem the_spilling_writer_keeps_the_tag_reading :
  CarriesNoTagInsideAnExtent spilling_write.
Proof. exact (placed_keeps_the_tag_reading plain_key past_offset plain_key_untagged). Qed.

Theorem the_spilling_writer_keeps_the_authority_reading :
  WritesNoAuthority spilling_write.
Proof.
  apply (placed_from_a_closed_body_writes_no_authority plain_key past_offset).
  intros n1 n2 e. reflexivity.
Qed.

Definition all_the_writers : list KeyWriter :=
  cons spec_write (cons sealing_write (cons capability_write
  (cons stamped_write (cons spilling_write nil)))).

Definition writer_at (n : nat) : KeyWriter := at_member all_the_writers n spec_write.

Example the_writers_are_five : count_of all_the_writers = 5 := eq_refl.

(* =========================================================================
   R-12-024a's session fabric and R-10-005b's third prohibition: what a
   delegation may reach, and what a resolution may hand back.
   ========================================================================= *)

Definition derivable (n : NsCap) (o : ObjCap) : bool :=
  andb (Nat.eqb (oc_domain o) (ns_domain n))
  (andb (Nat.eqb (oc_space o) (ns_space n))
        (Nat.leb (oc_rights o) (ns_rights n))).

(* R-10-005b's "the presented namespace capability is checked at query
   admission against that identifier", read at the router's own ask. *)
Definition ask_admitted (n : NsCap) (a : Ask) : bool :=
  andb (Nat.eqb (ak_domain a) (ns_domain n))
  (andb (Nat.eqb (ak_space a) (ns_space n))
        (Nat.leb (ak_rights a) (ns_rights n))).

Definition grant_of (n : NsCap) (a : Ask) : ObjCap :=
  {| oc_domain := ns_domain n; oc_space := ns_space n;
     oc_object := ak_object a; oc_rights := ak_rights a |}.

Definition truncated_grant (n : NsCap) (a : Ask) : ObjCap :=
  {| oc_domain := ns_domain n; oc_space := ns_space n;
     oc_object := ak_object a;
     oc_rights := if Nat.leb (ak_rights a) (ns_rights n) then ak_rights a
                  else ns_rights n |}.

(* Reading 4: a delegation is live exactly while its epoch is the
   composition's, which is R-12-024a's "each delegation ending with its
   session at the revocation epoch". *)
Definition live_session (c : Composition) (f : Fabric) (sid : nat) : option Session :=
  find_of (fun s => andb (Nat.eqb (se_id s) sid)
                         (Nat.eqb (se_epoch s) (live_epoch c))) f.

Definition any_session (f : Fabric) (sid : nat) : option Session :=
  find_of (fun s => Nat.eqb (se_id s) sid) f.

Definition first_live (c : Composition) (f : Fabric) : option Session :=
  find_of (fun s => Nat.eqb (se_epoch s) (live_epoch c)) f.

Definition refuse_by (d : Discipline) (n : NsCap) (a : Ask) : Answer :=
  match d with
  | RefuseTyped => Refused
  | AnswerEmpty => EmptyResult
  | GrantTruncated => Granted (truncated_grant n a)
  end.

Definition answer_under (c : Composition) (n : NsCap) (a : Ask) : Answer :=
  if ask_admitted n a then Granted (grant_of n a)
  else refuse_by (answer_discipline c) n a.

Definition Router : Type := Composition -> Fabric -> nat -> Ask -> Answer.

Definition spec_route : Router := fun c f sid a =>
  match live_session c f sid with
  | None => Refused
  | Some s => answer_under c (se_cap s) a
  end.

Definition grant_derivable (n : NsCap) (v : Answer) : bool :=
  match v with
  | Granted o => derivable n o
  | EmptyResult => true
  | Refused => true
  end.

(* The four obligations, each of an arbitrary router. *)
Definition MintsNothing (rt : Router) : Prop :=
  forall (c : Composition) (f : Fabric) (sid : nat) (a : Ask) (s : Session),
    live_session c f sid = Some s ->
    grant_derivable (se_cap s) (rt c f sid a) = true.

Definition GrantsNothingWithoutALiveSession (rt : Router) : Prop :=
  forall (c : Composition) (f : Fabric) (sid : nat) (a : Ask),
    live_session c f sid = None -> rt c f sid a = Refused.

Definition HoldsNoStandingAuthority (rt : Router) : Prop :=
  forall (c : Composition) (f g : Fabric) (sid : nat) (a : Ask),
    live_session c f sid = live_session c g sid -> rt c f sid a = rt c g sid a.

(* Gap a's first arm, stated of a composition rather than of a router,
   because which arm holds is the composition's declaration and the register
   decides none of the three. *)
Definition RefusesTheWidening (c : Composition) (rt : Router) : Prop :=
  forall (f : Fabric) (sid : nat) (a : Ask) (s : Session),
    live_session c f sid = Some s -> ask_admitted (se_cap s) a = false ->
    rt c f sid a = Refused.

Lemma grant_of_is_derivable : forall (n : NsCap) (a : Ask),
  ask_admitted n a = true -> derivable n (grant_of n a) = true.
Proof.
  intros n a H. unfold ask_admitted in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  unfold derivable, grant_of. simpl.
  rewrite nat_eqb_refl. rewrite nat_eqb_refl. rewrite H2. reflexivity.
Qed.

Lemma truncated_grant_is_derivable : forall (n : NsCap) (a : Ask),
  derivable n (truncated_grant n a) = true.
Proof.
  intros n a. unfold derivable, truncated_grant. simpl.
  rewrite nat_eqb_refl. rewrite nat_eqb_refl. simpl.
  destruct (Nat.leb (ak_rights a) (ns_rights n)) eqn:E;
    [ exact E | exact (nat_leb_refl (ns_rights n)) ].
Qed.

Lemma answer_under_is_derivable : forall (c : Composition) (n : NsCap) (a : Ask),
  grant_derivable n (answer_under c n a) = true.
Proof.
  intros c n a. unfold answer_under.
  destruct (ask_admitted n a) eqn:E.
  - exact (grant_of_is_derivable n a E).
  - unfold refuse_by. destruct (answer_discipline c);
      [ reflexivity | reflexivity | exact (truncated_grant_is_derivable n a) ].
Qed.

(*| discharges: R-12-024e |*)
Theorem the_specification_mints_nothing : MintsNothing spec_route.
Proof.
  intros c f sid a s H. unfold spec_route. rewrite H.
  exact (answer_under_is_derivable c (se_cap s) a).
Qed.

(*| discharges: R-12-024a |*)
Theorem the_specification_grants_nothing_without_a_live_session :
  GrantsNothingWithoutALiveSession spec_route.
Proof. intros c f sid a H. unfold spec_route. rewrite H. reflexivity. Qed.

(*| discharges: R-12-024a |*)
Theorem the_specification_holds_no_standing_authority :
  HoldsNoStandingAuthority spec_route.
Proof. intros c f g sid a H. unfold spec_route. rewrite H. reflexivity. Qed.

(*| discharges: R-10-005b |*)
Theorem the_specification_refuses_the_widening_where_the_composition_says_so :
  forall c : Composition, answer_discipline c = RefuseTyped ->
    RefusesTheWidening c spec_route.
Proof.
  intros c Hd f sid a s Hs Ha. unfold spec_route. rewrite Hs.
  unfold answer_under. rewrite Ha. unfold refuse_by. rewrite Hd. reflexivity.
Qed.

(* --- The four routers the register's own sentences exclude. ---------------- *)

(* R-12-024a's "no standing cross-caller namespace authority" refused: a
   router that answers where no live delegation exists, under the capability
   the composition gave the fabric. *)
Definition standing_route : Router := fun c f sid a =>
  match live_session c f sid with
  | Some s => answer_under c (se_cap s) a
  | None => answer_under c (standing_cap c) a
  end.

(* The same entry's "each delegation ending with its session at the
   revocation epoch" refused: a router that falls back to a session whose
   epoch has passed. *)
Definition immortal_route : Router := fun c f sid a =>
  match live_session c f sid with
  | Some s => answer_under c (se_cap s) a
  | None => match any_session f sid with
            | None => Refused
            | Some s => answer_under c (se_cap s) a
            end
  end.

(* R-12-024e's "resolution derives object capabilities only from the
   namespace capability the caller delegated for that session" refused: a
   router that answers this caller under another live session's capability. *)
Definition peer_route : Router := fun c f sid a =>
  match live_session c f sid with
  | None => Refused
  | Some _ => match first_live c f with
              | None => Refused
              | Some t => answer_under c (se_cap t) a
              end
  end.

(* R-10-005b's third prohibition refused outright: a router that hands back
   exactly the rights the ask names. *)
Definition widening_route : Router := fun c f sid a =>
  match live_session c f sid with
  | None => Refused
  | Some s => Granted (grant_of (se_cap s) a)
  end.

Theorem the_standing_router_mints_nothing : MintsNothing standing_route.
Proof.
  intros c f sid a s H. unfold standing_route. rewrite H.
  exact (answer_under_is_derivable c (se_cap s) a).
Qed.

Theorem the_standing_router_holds_the_fabric_fixed :
  HoldsNoStandingAuthority standing_route.
Proof. intros c f g sid a H. unfold standing_route. rewrite H. reflexivity. Qed.

Theorem the_standing_router_refuses_the_widening_it_admits :
  forall c : Composition, answer_discipline c = RefuseTyped ->
    RefusesTheWidening c standing_route.
Proof.
  intros c Hd f sid a s Hs Ha. unfold standing_route. rewrite Hs.
  unfold answer_under. rewrite Ha. unfold refuse_by. rewrite Hd. reflexivity.
Qed.

Theorem the_immortal_router_mints_nothing : MintsNothing immortal_route.
Proof.
  intros c f sid a s H. unfold immortal_route. rewrite H.
  exact (answer_under_is_derivable c (se_cap s) a).
Qed.

Theorem the_immortal_router_refuses_the_widening_it_admits :
  forall c : Composition, answer_discipline c = RefuseTyped ->
    RefusesTheWidening c immortal_route.
Proof.
  intros c Hd f sid a s Hs Ha. unfold immortal_route. rewrite Hs.
  unfold answer_under. rewrite Ha. unfold refuse_by. rewrite Hd. reflexivity.
Qed.

Theorem the_peer_router_grants_nothing_without_a_live_session :
  GrantsNothingWithoutALiveSession peer_route.
Proof. intros c f sid a H. unfold peer_route. rewrite H. reflexivity. Qed.

Theorem the_widening_router_grants_nothing_without_a_live_session :
  GrantsNothingWithoutALiveSession widening_route.
Proof. intros c f sid a H. unfold widening_route. rewrite H. reflexivity. Qed.

Theorem the_widening_router_holds_the_fabric_fixed :
  HoldsNoStandingAuthority widening_route.
Proof. intros c f g sid a H. unfold widening_route. rewrite H. reflexivity. Qed.

(* =========================================================================
   R-10-005c at the router: the subscription, its phase, and what a
   publication past the declared queue bound emits.
   ========================================================================= *)

Definition with_queue (s : Subscription) (p : Phase) (q : list Delta) : Subscription :=
  {| sb_id := sb_id s; sb_domain := sb_domain s; sb_space := sb_space s;
     sb_phase := p; sb_queue := q |}.

Lemma queue_of_with_queue : forall (s : Subscription) (p : Phase) (q : list Delta),
  sb_queue (with_queue s p q) = q.
Proof. intros s p q. reflexivity. Qed.

Lemma phase_of_with_queue : forall (s : Subscription) (p : Phase) (q : list Delta),
  sb_phase (with_queue s p q) = p.
Proof. intros s p q. reflexivity. Qed.

Definition Publisher : Type :=
  Composition -> Txn -> Subscription -> list Delta -> Subscription.

Definition spec_publish : Publisher := fun c x s ds =>
  match tx_committed x with
  | false => s
  | true =>
      match sb_phase s with
      | PhaseRescanRequired => s
      | PhaseLive =>
          if Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c)
          then with_queue s PhaseLive (append_of (sb_queue s) ds)
          else with_queue s PhaseRescanRequired
                 (append_of (take_of (before_last (queue_bound c))
                                     (append_of (sb_queue s) ds))
                            (cons DeltaRescan nil))
      end
  end.

(* The specification's four arms as equations, so that every theorem below
   rewrites rather than reduces a nested match by tactic. *)
Lemma spec_publish_uncommitted : forall (c : Composition) (x : Txn)
    (s : Subscription) (ds : list Delta),
  tx_committed x = false -> spec_publish c x s ds = s.
Proof. intros c x s ds H. unfold spec_publish. rewrite H. reflexivity. Qed.

Lemma spec_publish_after_the_marker : forall (c : Composition) (x : Txn)
    (s : Subscription) (ds : list Delta),
  sb_phase s = PhaseRescanRequired -> spec_publish c x s ds = s.
Proof.
  intros c x s ds H. unfold spec_publish.
  destruct (tx_committed x); [ rewrite H; reflexivity | reflexivity ].
Qed.

Lemma spec_publish_fits : forall (c : Composition) (x : Txn)
    (s : Subscription) (ds : list Delta),
  tx_committed x = true -> sb_phase s = PhaseLive ->
  Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c) = true ->
  spec_publish c x s ds = with_queue s PhaseLive (append_of (sb_queue s) ds).
Proof.
  intros c x s ds Hc Hp Hq. unfold spec_publish.
  rewrite Hc. rewrite Hp. rewrite Hq. reflexivity.
Qed.

Lemma spec_publish_overflows : forall (c : Composition) (x : Txn)
    (s : Subscription) (ds : list Delta),
  tx_committed x = true -> sb_phase s = PhaseLive ->
  Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c) = false ->
  spec_publish c x s ds
  = with_queue s PhaseRescanRequired
      (append_of (take_of (before_last (queue_bound c))
                          (append_of (sb_queue s) ds))
                 (cons DeltaRescan nil)).
Proof.
  intros c x s ds Hc Hp Hq. unfold spec_publish.
  rewrite Hc. rewrite Hp. rewrite Hq. reflexivity.
Qed.

(* R-08-046's declared bounded pool over the subscription's queue. *)
Definition StaysInsideTheDeclaredBound (pb : Publisher) : Prop :=
  forall (c : Composition) (x : Txn) (s : Subscription) (ds : list Delta),
    Nat.ltb 0 (queue_bound c) = true ->
    Nat.leb (count_of (sb_queue s)) (queue_bound c) = true ->
    Nat.leb (count_of (sb_queue (pb c x s ds))) (queue_bound c) = true.

(* M6.3b's cell's own words, and the count is exactly one rather than at
   most one, which is the half KeyspaceDomains.v's emitter does not carry. *)
Definition EmitsExactlyOneMarkerOnOverflow (pb : Publisher) : Prop :=
  forall (c : Composition) (x : Txn) (s : Subscription) (ds : list Delta),
    tx_committed x = true -> sb_phase s = PhaseLive ->
    all_of (fun d => negb (is_rescan d)) (append_of (sb_queue s) ds) = true ->
    Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c) = false ->
    count_of (filter_of is_rescan (sb_queue (pb c x s ds))) = 1.

(* The cell's second half, and reading 7 is why it needs a phase. *)
Definition NoFurtherDeltaAfterTheMarker (pb : Publisher) : Prop :=
  forall (c : Composition) (x : Txn) (s : Subscription) (ds : list Delta),
    sb_phase s = PhaseRescanRequired -> pb c x s ds = s.

(* R-10-005c's "derived only after the committing L0 transaction", at the
   router's publication rather than at the journal's scan. *)
Definition PublishesOnlyAfterTheCommit (pb : Publisher) : Prop :=
  forall (c : Composition) (x : Txn) (s : Subscription) (ds : list Delta),
    tx_committed x = false -> pb c x s ds = s.

(*| discharges: R-08-046 |*)
Theorem the_specification_stays_inside_the_declared_bound :
  StaysInsideTheDeclaredBound spec_publish.
Proof.
  intros c x s ds Hpos Hstart.
  destruct (tx_committed x) eqn:Hc;
    [ | rewrite (spec_publish_uncommitted c x s ds Hc); exact Hstart ].
  destruct (sb_phase s) eqn:Hp;
    [ | rewrite (spec_publish_after_the_marker c x s ds Hp); exact Hstart ].
  destruct (Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c)) eqn:Hq.
  - rewrite (spec_publish_fits c x s ds Hc Hp Hq).
    rewrite queue_of_with_queue. exact Hq.
  - rewrite (spec_publish_overflows c x s ds Hc Hp Hq).
    rewrite queue_of_with_queue.
    rewrite (count_append_one Delta
               (take_of (before_last (queue_bound c)) (append_of (sb_queue s) ds))
               DeltaRescan).
    exact (bound_take_plus_one Delta (queue_bound c)
             (append_of (sb_queue s) ds) Hpos).
Qed.

(*| discharges: R-10-005c |*)
Theorem the_specification_emits_exactly_one_marker :
  EmitsExactlyOneMarkerOnOverflow spec_publish.
Proof.
  intros c x s ds Hc Hp Hno Hq.
  rewrite (spec_publish_overflows c x s ds Hc Hp Hq).
  rewrite queue_of_with_queue.
  rewrite (filter_append Delta is_rescan
             (take_of (before_last (queue_bound c)) (append_of (sb_queue s) ds))
             (cons DeltaRescan nil)).
  rewrite (filter_none Delta is_rescan
             (take_of (before_last (queue_bound c)) (append_of (sb_queue s) ds))
             (all_of_take Delta (fun d => negb (is_rescan d))
                          (before_last (queue_bound c))
                          (append_of (sb_queue s) ds) Hno)).
  reflexivity.
Qed.

(*| discharges: R-10-005c |*)
Theorem the_specification_emits_no_further_delta :
  NoFurtherDeltaAfterTheMarker spec_publish.
Proof. intros c x s ds H. exact (spec_publish_after_the_marker c x s ds H). Qed.

(*| discharges: R-10-005c |*)
Theorem the_specification_publishes_only_after_the_commit :
  PublishesOnlyAfterTheCommit spec_publish.
Proof. intros c x s ds H. exact (spec_publish_uncommitted c x s ds H). Qed.

(* The overflowing publication leaves the subscription needing a rescan,
   which is what makes the obligation above about the next publication. *)
Theorem an_overflow_leaves_the_subscription_needing_a_rescan :
  forall (c : Composition) (x : Txn) (s : Subscription) (ds : list Delta),
    tx_committed x = true -> sb_phase s = PhaseLive ->
    Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c) = false ->
    sb_phase (spec_publish c x s ds) = PhaseRescanRequired.
Proof.
  intros c x s ds Hc Hp Hq.
  rewrite (spec_publish_overflows c x s ds Hc Hp Hq).
  exact (phase_of_with_queue s PhaseRescanRequired _).
Qed.

(* --- The four publishers R-10-005c's own sentence excludes. ---------------- *)

(* "rather than buffering without bound" refused. *)
Definition hoarding_publish : Publisher := fun c x s ds =>
  match tx_committed x with
  | false => s
  | true =>
      match sb_phase s with
      | PhaseRescanRequired => s
      | PhaseLive => with_queue s PhaseLive (append_of (sb_queue s) ds)
      end
  end.

(* "one rescan-required marker" refused by a publisher whose markers count
   the deltas it dropped, which publishes how many changes the domain
   committed. *)
Definition twin_marker_publish : Publisher := fun c x s ds =>
  match tx_committed x with
  | false => s
  | true =>
      match sb_phase s with
      | PhaseRescanRequired => s
      | PhaseLive =>
          if Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c)
          then with_queue s PhaseLive (append_of (sb_queue s) ds)
          else with_queue s PhaseRescanRequired
                 (append_of (take_of (before_last (before_last (queue_bound c)))
                                     (append_of (sb_queue s) ds))
                            (cons DeltaRescan (cons DeltaRescan nil)))
      end
  end.

(* "no further delta" refused: a publisher that reads the queue and not the
   phase, so a subscription that has emitted its marker goes on delivering. *)
Definition resuming_publish : Publisher := fun c x s ds =>
  match tx_committed x with
  | false => s
  | true =>
      if Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c)
      then with_queue s (sb_phase s) (append_of (sb_queue s) ds)
      else with_queue s PhaseRescanRequired
             (append_of (take_of (before_last (queue_bound c))
                                 (append_of (sb_queue s) ds))
                        (cons DeltaRescan nil))
  end.

(* "derived only after the committing L0 transaction" refused: a publisher
   that delivers an open transaction's changes before it commits, and before
   a crash would have rolled them back. *)
Definition prepare_publish : Publisher := fun c x s ds =>
  match sb_phase s with
  | PhaseRescanRequired => s
  | PhaseLive =>
      if Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c)
      then with_queue s PhaseLive (append_of (sb_queue s) ds)
      else with_queue s PhaseRescanRequired
             (append_of (take_of (before_last (queue_bound c))
                                 (append_of (sb_queue s) ds))
                        (cons DeltaRescan nil))
  end.

Theorem the_hoarding_publisher_emits_no_further_delta :
  NoFurtherDeltaAfterTheMarker hoarding_publish.
Proof.
  intros c x s ds H. unfold hoarding_publish.
  destruct (tx_committed x); [ rewrite H; reflexivity | reflexivity ].
Qed.

Theorem the_hoarding_publisher_publishes_only_after_the_commit :
  PublishesOnlyAfterTheCommit hoarding_publish.
Proof. intros c x s ds H. unfold hoarding_publish. rewrite H. reflexivity. Qed.

Theorem the_twin_marker_publisher_emits_no_further_delta :
  NoFurtherDeltaAfterTheMarker twin_marker_publish.
Proof.
  intros c x s ds H. unfold twin_marker_publish.
  destruct (tx_committed x); [ rewrite H; reflexivity | reflexivity ].
Qed.

Theorem the_twin_marker_publisher_publishes_only_after_the_commit :
  PublishesOnlyAfterTheCommit twin_marker_publish.
Proof. intros c x s ds H. unfold twin_marker_publish. rewrite H. reflexivity. Qed.

(* The twin: what refuses the second publisher is the marker count and not
   the queue, its emission fitting the same declared bound the
   specification's does wherever the bound admits two markers. Two
   obligations, and neither is the other stated twice. *)
Theorem the_twin_marker_publisher_still_bounds_the_queue :
  forall (c : Composition) (x : Txn) (s : Subscription) (ds : list Delta),
    Nat.leb 2 (queue_bound c) = true ->
    Nat.leb (count_of (sb_queue s)) (queue_bound c) = true ->
    Nat.leb (count_of (sb_queue (twin_marker_publish c x s ds)))
            (queue_bound c) = true.
Proof.
  intros c x s ds Htwo Hstart. unfold twin_marker_publish.
  destruct (tx_committed x); [ | exact Hstart ].
  destruct (sb_phase s); [ | exact Hstart ].
  destruct (Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c)) eqn:Hq;
    [ rewrite queue_of_with_queue; exact Hq | ].
  rewrite queue_of_with_queue.
  rewrite (count_append_two Delta
             (take_of (before_last (before_last (queue_bound c)))
                      (append_of (sb_queue s) ds)) DeltaRescan DeltaRescan).
  exact (bound_take_plus_two Delta (queue_bound c)
           (append_of (sb_queue s) ds) Htwo).
Qed.

Theorem the_resuming_publisher_publishes_only_after_the_commit :
  PublishesOnlyAfterTheCommit resuming_publish.
Proof. intros c x s ds H. unfold resuming_publish. rewrite H. reflexivity. Qed.

Theorem the_resuming_publisher_stays_inside_the_declared_bound :
  StaysInsideTheDeclaredBound resuming_publish.
Proof.
  intros c x s ds Hpos Hstart. unfold resuming_publish.
  destruct (tx_committed x); [ | exact Hstart ].
  destruct (Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c)) eqn:Hq;
    [ rewrite queue_of_with_queue; exact Hq | ].
  rewrite queue_of_with_queue.
  rewrite (count_append_one Delta
             (take_of (before_last (queue_bound c)) (append_of (sb_queue s) ds))
             DeltaRescan).
  exact (bound_take_plus_one Delta (queue_bound c)
           (append_of (sb_queue s) ds) Hpos).
Qed.

Theorem the_prepare_time_publisher_emits_no_further_delta :
  NoFurtherDeltaAfterTheMarker prepare_publish.
Proof. intros c x s ds H. unfold prepare_publish. rewrite H. reflexivity. Qed.

Theorem the_prepare_time_publisher_stays_inside_the_declared_bound :
  StaysInsideTheDeclaredBound prepare_publish.
Proof.
  intros c x s ds Hpos Hstart. unfold prepare_publish.
  destruct (sb_phase s); [ | exact Hstart ].
  destruct (Nat.leb (count_of (append_of (sb_queue s) ds)) (queue_bound c)) eqn:Hq;
    [ rewrite queue_of_with_queue; exact Hq | ].
  rewrite queue_of_with_queue.
  rewrite (count_append_one Delta
             (take_of (before_last (queue_bound c)) (append_of (sb_queue s) ds))
             DeltaRescan).
  exact (bound_take_plus_one Delta (queue_bound c)
           (append_of (sb_queue s) ds) Hpos).
Qed.

(* =========================================================================
   R-10-005c's volatility: no subscription survives a reboot, and recovery
   re-establishes one by rescan.
   ========================================================================= *)

Definition Table : Type := list Subscription.

Definition Reboot : Type := Table -> Table.

Definition spec_reboot : Reboot := fun _ => nil.

Definition SurvivesNoReboot (rb : Reboot) : Prop := forall t : Table, rb t = nil.

(*| discharges: R-10-005c |*)
Theorem the_specification_survives_no_reboot : SurvivesNoReboot spec_reboot.
Proof. intros t. reflexivity. Qed.

(* The construction the same clause excludes: a subscription table carried
   across the boot, so a client resumes a stream it never rescanned. *)
Definition warm_reboot : Reboot := fun t => t.

Definition Establish : Type := nat -> nat -> nat -> Subscription.

Definition spec_establish : Establish := fun i d sp =>
  {| sb_id := i; sb_domain := d; sb_space := sp; sb_phase := PhaseLive;
     sb_queue := cons DeltaRescan nil |}.

Definition ReestablishesByRescan (es : Establish) : Prop :=
  forall i d sp : nat,
    sb_queue (es i d sp) = cons DeltaRescan nil /\ sb_phase (es i d sp) = PhaseLive.

(*| discharges: R-10-005c |*)
Theorem the_specification_reestablishes_by_rescan :
  ReestablishesByRescan spec_establish.
Proof. intros i d sp. split; reflexivity. Qed.

(* And the construction that clause excludes at the other end: a
   re-established subscription whose first delivery is a delta, so a client
   that missed the crash reads an index it never rescanned. *)
Definition silent_establish : Establish := fun i d sp =>
  {| sb_id := i; sb_domain := d; sb_space := sp; sb_phase := PhaseLive;
     sb_queue := nil |}.

Theorem the_silent_establishment_still_starts_inside_the_bound :
  forall (c : Composition) (i d sp : nat),
    Nat.leb (count_of (sb_queue (silent_establish i d sp))) (queue_bound c) = true.
Proof. intros c i d sp. reflexivity. Qed.

(* =========================================================================
   R-10-005c's "rather than backpressuring commit", read at the router as
   the two-state agreement of reading 8: what a commit does is a function
   neither of the subscription table nor of the ring's own answer.
   ========================================================================= *)

Definition Commit : Type := Table -> submit_result -> Txn -> Txn.

Definition spec_commit : Commit := fun _ _ x =>
  {| tx_id := tx_id x; tx_committed := true |}.

Definition NeverBackpressuresTheCommit (cm : Commit) : Prop :=
  forall (t1 t2 : Table) (r1 r2 : submit_result) (x : Txn),
    cm t1 r1 x = cm t2 r2 x.

(*| discharges: R-10-005c |*)
Theorem the_specification_never_backpressures_the_commit :
  NeverBackpressuresTheCommit spec_commit.
Proof. intros t1 t2 r1 r2 x. reflexivity. Qed.

(* The ring's own full-ring result reaching the commit, which is what
   backpressure is: R-12-095 gives a full request ring the sole typed result
   `submit_would_block`, and a commit that reads it has made the committing
   transaction wait on a subscriber's queue. *)
Definition ring_blocking_commit : Commit := fun _ r x =>
  match r with
  | submit_enqueued => {| tx_id := tx_id x; tx_committed := true |}
  | submit_would_block => x
  end.

(* And the same defect reached from the table rather than from the ring: a
   commit that waits while any subscription is already past its bound. *)
Definition queue_sensitive_commit : Commit := fun t _ x =>
  if any_of (fun s => match sb_phase s with
                      | PhaseRescanRequired => true
                      | PhaseLive => false
                      end) t
  then x
  else {| tx_id := tx_id x; tx_committed := true |}.

Theorem the_ring_blocking_commit_agrees_where_the_ring_accepted :
  forall (t : Table) (x : Txn),
    ring_blocking_commit t submit_enqueued x = spec_commit t submit_enqueued x.
Proof. intros t x. reflexivity. Qed.

Theorem the_queue_sensitive_commit_agrees_on_an_empty_table :
  forall (r : submit_result) (x : Txn),
    queue_sensitive_commit nil r x = spec_commit nil r x.
Proof. intros r x. reflexivity. Qed.

(* =========================================================================
   The demo: one composition, one fabric, one entry, one subscription, and
   the boundary values every comparison this file makes is exercised on.
   Every figure here is a witness value carrying no composition claim
   (gap g), and the ledger at the end pins each of them.
   ========================================================================= *)

Definition user_photos : Extent :=
  {| ex_base := 10; ex_span := 40; ex_domain := 0; ex_space := 0 |}.
Definition work_mail : Extent :=
  {| ex_base := 50; ex_span := 40; ex_domain := 1; ex_space := 0 |}.
Definition user_notes : Extent :=
  {| ex_base := 90; ex_span := 20; ex_domain := 0; ex_space := 1 |}.

Definition demo_extents : list Extent :=
  cons user_photos (cons work_mail (cons user_notes nil)).

(* The extent that spans two confidentiality domains: a second domain's
   index laid over the first domain's addresses. *)
Definition spanning_extent : Extent :=
  {| ex_base := 40; ex_span := 40; ex_domain := 1; ex_space := 2 |}.

(* And the extent that covers no address at all. *)
Definition empty_extent : Extent :=
  {| ex_base := 10; ex_span := 0; ex_domain := 0; ex_space := 0 |}.

Definition demo_cap : NsCap := {| ns_domain := 0; ns_space := 0; ns_rights := 2 |}.
Definition peer_cap : NsCap := {| ns_domain := 1; ns_space := 0; ns_rights := 3 |}.
Definition standing : NsCap := {| ns_domain := 0; ns_space := 0; ns_rights := 5 |}.

Definition demo_composition : Composition :=
  remake demo_extents 4 8 ring_capacity 4 RefuseTyped standing.
Definition empty_answer_composition : Composition :=
  remake demo_extents 4 8 ring_capacity 4 AnswerEmpty standing.
Definition truncating_composition : Composition :=
  remake demo_extents 4 8 ring_capacity 4 GrantTruncated standing.

Definition spanning_composition : Composition :=
  remake (cons user_photos (cons spanning_extent nil)) 4 8 ring_capacity 4
         RefuseTyped standing.
Definition unplaced_composition : Composition :=
  remake (cons empty_extent nil) 4 8 ring_capacity 4 RefuseTyped standing.
Definition no_queue_composition : Composition :=
  remake demo_extents 0 8 ring_capacity 4 RefuseTyped standing.
Definition oversize_queue_composition : Composition :=
  remake demo_extents (S ring_capacity) 8 ring_capacity 4 RefuseTyped standing.
Definition no_result_composition : Composition :=
  remake demo_extents 4 0 ring_capacity 4 RefuseTyped standing.

Definition spoiled_compositions : list Composition :=
  cons spanning_composition
  (cons unplaced_composition
  (cons no_queue_composition
  (cons oversize_queue_composition (cons no_result_composition nil)))).

Definition spoiled_composition_at (n : nat) : Composition :=
  at_member spoiled_compositions n demo_composition.

(* Six components, which is KeyspaceDomains.v's own key shape read at the
   router. The count is the demo's and not a claim (reading 1). *)
Definition demo_entry : Entry :=
  {| en_domain := 0; en_space := 0; en_slot := 6;
     en_components := cons 0 (cons 0 (cons 2 (cons 11 (cons 5 (cons 3 nil))))) |}.

Definition demo_session : Session :=
  {| se_id := 0; se_cap := demo_cap; se_epoch := 4 |}.
Definition peer_session : Session :=
  {| se_id := 1; se_cap := peer_cap; se_epoch := 4 |}.
Definition stale_session : Session :=
  {| se_id := 2; se_cap := standing; se_epoch := 3 |}.

Definition demo_fabric : Fabric :=
  cons demo_session (cons peer_session (cons stale_session nil)).
Definition peer_first_fabric : Fabric :=
  cons peer_session (cons demo_session (cons stale_session nil)).

Definition demo_ask : Ask :=
  {| ak_domain := 0; ak_space := 0; ak_object := 11; ak_rights := 2 |}.
Definition widening_ask : Ask :=
  {| ak_domain := 0; ak_space := 0; ak_object := 11; ak_rights := 3 |}.
Definition foreign_domain_ask : Ask :=
  {| ak_domain := 1; ak_space := 0; ak_object := 11; ak_rights := 2 |}.
Definition foreign_space_ask : Ask :=
  {| ak_domain := 0; ak_space := 1; ak_object := 11; ak_rights := 2 |}.

Definition all_the_asks : list Ask :=
  cons demo_ask (cons widening_ask
  (cons foreign_domain_ask (cons foreign_space_ask nil))).

Definition demo_subscription : Subscription :=
  {| sb_id := 0; sb_domain := 0; sb_space := 0; sb_phase := PhaseLive;
     sb_queue := cons (DeltaAdded 11) (cons (DeltaRemoved 12) nil) |}.

Definition marked_subscription : Subscription :=
  {| sb_id := 0; sb_domain := 0; sb_space := 0; sb_phase := PhaseRescanRequired;
     sb_queue := cons DeltaRescan nil |}.

Definition committed_txn : Txn := {| tx_id := 7; tx_committed := true |}.
Definition open_txn : Txn := {| tx_id := 8; tx_committed := false |}.

(* A publication that lands exactly on the bound, and one that lands one
   past it. *)
Definition two_deltas : list Delta := cons (DeltaAdded 13) (cons (DeltaAdded 14) nil).
Definition three_deltas : list Delta :=
  cons (DeltaAdded 13) (cons (DeltaAdded 14) (cons (DeltaAdded 15) nil)).

Definition after_two : Subscription :=
  spec_publish demo_composition committed_txn demo_subscription two_deltas.
Definition after_three : Subscription :=
  spec_publish demo_composition committed_txn demo_subscription three_deltas.

(* =========================================================================
   The composition's own admission, decided from both sides.
   ========================================================================= *)

Example the_demo_composition_is_admissible :
  admissible_composition demo_composition = true := eq_refl.

Example the_demo_composition_breaks_no_conjunct :
  conjuncts_broken demo_composition = 0 := eq_refl.

Example every_spoiled_composition_is_refused :
  all_of (fun c => negb (admissible_composition c)) spoiled_compositions = true
  := eq_refl.

Example each_spoiled_composition_breaks_exactly_one_conjunct :
  map_over conjuncts_broken spoiled_compositions
  = cons 1 (cons 1 (cons 1 (cons 1 (cons 1 nil)))) := eq_refl.

Example every_dropped_conjunct_admits_its_own_composition :
  all_of (fun n => admit_without n (spoiled_composition_at n)) (upto 5) = true
  := eq_refl.

Example the_spoiled_compositions_are_five :
  count_of spoiled_compositions = 5 := eq_refl.

Theorem no_spoiled_composition_is_admissible :
  forall n : nat, Nat.ltb n 5 = true ->
    admissible_composition (spoiled_composition_at n) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | k ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* The pairs the first conjunct decides, and the pair the spanning
   composition puts in their place. *)
Example the_declared_extents_separate_the_two_domains :
  overlaps user_photos work_mail = false
  /\ overlaps work_mail user_notes = false
  /\ overlaps user_photos spanning_extent = true
  /\ Nat.eqb (ex_domain user_photos) (ex_domain spanning_extent) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* And the one pair the conjunct deliberately says nothing about: two
   extents of the *same* domain may sit where they like, which is why the
   separation is stated over the domain and not over the address. *)
Example two_extents_of_one_domain_are_unconstrained :
  Nat.eqb (ex_domain user_photos) (ex_domain user_notes) = true
  /\ extents_separated (cons user_photos (cons user_photos nil)) = true :=
  conj eq_refl eq_refl.

(* An empty extent overlaps nothing, which is the case conjunct 1 exists
   for: the separation above would hold of an unplaced index vacuously. *)
Example an_empty_extent_overlaps_nothing :
  overlaps empty_extent user_photos = false
  /\ extents_separated (cons empty_extent (cons spanning_extent nil)) = true
  /\ admissible_composition unplaced_composition = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   The five key writers, decided at all three obligations as one table.
   ========================================================================= *)

Definition key_bits (kw : KeyWriter) (n : NsCap) : list nat :=
  map_over (fun r => w_bits (wr_word r)) (kw demo_composition n demo_entry).

Example every_writer_is_decided_at_every_obligation :
  map_over (fun kw => all_of (fun r => implb (record_inside_some_extent demo_composition r)
                                             (negb (w_tag (wr_word r))))
                             (kw demo_composition demo_cap demo_entry))
           all_the_writers
  = cons true (cons false (cons false (cons true (cons true nil))))
  /\ map_over (fun kw => all_of (fun r => inside user_photos (wr_address r))
                                (kw demo_composition demo_cap demo_entry))
              all_the_writers
     = cons true (cons true (cons true (cons true (cons false nil))))
  /\ map_over (fun kw => negb (nat_list_eqb (key_bits kw demo_cap)
                                            (key_bits kw peer_cap)))
              all_the_writers
     = cons false (cons false (cons true (cons true (cons false nil)))) :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_specification_write_lands_where_the_extent_declares :
  map_over wr_address (spec_write demo_composition demo_cap demo_entry)
  = cons 16 (cons 17 (cons 18 (cons 19 (cons 20 (cons 21 nil)))))
  /\ key_bits spec_write demo_cap = en_components demo_entry
  /\ entry_fits user_photos demo_entry = true :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_sealing_write_lands_at_the_same_addresses :
  map_over wr_address (sealing_write demo_composition demo_cap demo_entry)
  = map_over wr_address (spec_write demo_composition demo_cap demo_entry)
  /\ all_of (fun r => w_tag (wr_word r))
            (sealing_write demo_composition demo_cap demo_entry) = true :=
  conj eq_refl eq_refl.

(* The spilled key lands in the neighbouring domain's own index, which is
   what the placement obligation is for. *)
Example the_spilled_write_lands_in_another_domain_s_index :
  all_of (fun r => inside work_mail (wr_address r))
         (spilling_write demo_composition demo_cap demo_entry) = true
  /\ Nat.eqb (ex_domain work_mail) (ex_domain user_photos) = false :=
  conj eq_refl eq_refl.

Theorem the_sealing_writer_is_refuted : ~ CarriesNoTagInsideAnExtent sealing_write.
Proof.
  intros H. specialize (H demo_composition demo_cap demo_entry).
  vm_compute in H. discriminate H.
Qed.

Theorem the_capability_writer_is_refuted :
  ~ CarriesNoTagInsideAnExtent capability_write.
Proof.
  intros H. specialize (H demo_composition demo_cap demo_entry).
  vm_compute in H. discriminate H.
Qed.

Theorem the_capability_writer_also_writes_the_authority :
  ~ WritesNoAuthority capability_write.
Proof.
  intros H.
  assert (Hb : key_bits capability_write demo_cap = key_bits capability_write peer_cap).
  { unfold key_bits. rewrite (H demo_composition demo_cap peer_cap demo_entry).
    reflexivity. }
  vm_compute in Hb. discriminate Hb.
Qed.

Theorem the_stamped_writer_is_refuted : ~ WritesNoAuthority stamped_write.
Proof.
  intros H.
  assert (Hb : key_bits stamped_write demo_cap = key_bits stamped_write peer_cap).
  { unfold key_bits. rewrite (H demo_composition demo_cap peer_cap demo_entry).
    reflexivity. }
  vm_compute in Hb. discriminate Hb.
Qed.

Theorem the_spilling_writer_is_refuted :
  ~ PlacesInsideTheDeclaredExtent spilling_write.
Proof.
  intros H.
  specialize (H demo_composition demo_cap demo_entry user_photos eq_refl eq_refl).
  vm_compute in H. discriminate H.
Qed.

(* The independence M6.3b's cell and KeyspaceDomains.v's reading 12 leave
   between them, machine-checked rather than asserted: one writer keeps each
   reading of one sentence and breaks the other. *)
Theorem the_two_readings_of_one_sentence_are_independent :
  (CarriesNoTagInsideAnExtent stamped_write /\ ~ WritesNoAuthority stamped_write)
  /\ (WritesNoAuthority sealing_write /\ ~ CarriesNoTagInsideAnExtent sealing_write).
Proof.
  split; split.
  - exact the_stamped_writer_keeps_the_tag_reading.
  - exact the_stamped_writer_is_refuted.
  - exact the_sealing_writer_keeps_the_authority_reading.
  - exact the_sealing_writer_is_refuted.
Qed.

(* =========================================================================
   The session fabric, computed and refuted.
   ========================================================================= *)

Example the_specification_answers_every_ask_as_the_delegation_admits :
  map_over (fun a => spec_route demo_composition demo_fabric 0 a) all_the_asks
  = cons (Granted {| oc_domain := 0; oc_space := 0; oc_object := 11;
                     oc_rights := 2 |})
    (cons Refused (cons Refused (cons Refused nil)))
  /\ map_over (ask_admitted demo_cap) all_the_asks
     = cons true (cons false (cons false (cons false nil))) :=
  conj eq_refl eq_refl.

(* The rights comparison exercised on its boundary as well as either side of
   it: an ask at the delegated rights is admitted and one right more is not. *)
Example the_rights_comparison_is_exercised_on_its_boundary :
  map_over (fun r => ask_admitted demo_cap
                       {| ak_domain := 0; ak_space := 0; ak_object := 11;
                          ak_rights := r |}) (upto 4)
  = cons true (cons true (cons true (cons false nil))) := eq_refl.

Example a_dead_delegation_answers_nothing :
  spec_route demo_composition demo_fabric 2 demo_ask = Refused
  /\ spec_route demo_composition demo_fabric 9 demo_ask = Refused
  /\ live_session demo_composition demo_fabric 2 = None
  /\ any_session demo_fabric 2 = Some stale_session :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_three_disciplines_answer_one_widening_differently :
  spec_route demo_composition demo_fabric 0 widening_ask = Refused
  /\ spec_route empty_answer_composition demo_fabric 0 widening_ask = EmptyResult
  /\ spec_route truncating_composition demo_fabric 0 widening_ask
     = Granted {| oc_domain := 0; oc_space := 0; oc_object := 11;
                  oc_rights := 2 |} :=
  conj eq_refl (conj eq_refl eq_refl).

(* And every one of the three mints only what the delegation derives, which
   is why R-10-005b's own clause does not choose between them (gap a). *)
Example every_discipline_mints_only_what_the_delegation_derives :
  all_of (fun d => grant_derivable demo_cap (refuse_by d demo_cap widening_ask))
         all_disciplines = true := eq_refl.

Theorem the_answer_discipline_is_observable :
  spec_route demo_composition demo_fabric 0 widening_ask
    <> spec_route empty_answer_composition demo_fabric 0 widening_ask
  /\ spec_route empty_answer_composition demo_fabric 0 widening_ask
     <> spec_route truncating_composition demo_fabric 0 widening_ask
  /\ spec_route demo_composition demo_fabric 0 widening_ask
     <> spec_route truncating_composition demo_fabric 0 widening_ask.
Proof. repeat split; intros H; vm_compute in H; discriminate H. Qed.

Theorem the_empty_answer_discipline_does_not_refuse :
  ~ RefusesTheWidening empty_answer_composition spec_route.
Proof.
  intros H. specialize (H demo_fabric 0 widening_ask demo_session eq_refl eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_truncating_discipline_does_not_refuse :
  ~ RefusesTheWidening truncating_composition spec_route.
Proof.
  intros H. specialize (H demo_fabric 0 widening_ask demo_session eq_refl eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_standing_router_is_refuted :
  ~ GrantsNothingWithoutALiveSession standing_route.
Proof.
  intros H. specialize (H demo_composition demo_fabric 2 demo_ask eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_immortal_router_is_refuted :
  ~ GrantsNothingWithoutALiveSession immortal_route.
Proof.
  intros H. specialize (H demo_composition demo_fabric 2 demo_ask eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_peer_router_is_refuted : ~ HoldsNoStandingAuthority peer_route.
Proof.
  intros H.
  specialize (H demo_composition demo_fabric peer_first_fabric 0 demo_ask eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_peer_router_mints_what_another_session_delegated :
  ~ MintsNothing peer_route.
Proof.
  intros H.
  specialize (H demo_composition peer_first_fabric 0 foreign_domain_ask
                demo_session eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_widening_router_is_refuted : ~ MintsNothing widening_route.
Proof.
  intros H.
  specialize (H demo_composition demo_fabric 0 widening_ask demo_session eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_widening_router_answers_the_widening :
  ~ RefusesTheWidening demo_composition widening_route.
Proof.
  intros H. specialize (H demo_fabric 0 widening_ask demo_session eq_refl eq_refl).
  vm_compute in H. discriminate H.
Qed.

(* The two fabrics differ in nothing the named delegation can see, which is
   what makes the peer router's answer a reading of another session. *)
Example the_two_fabrics_hold_one_delegation_fixed :
  live_session demo_composition demo_fabric 0
  = live_session demo_composition peer_first_fabric 0
  /\ first_live demo_composition demo_fabric = Some demo_session
  /\ first_live demo_composition peer_first_fabric = Some peer_session :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   The live subscription, computed and refuted.
   ========================================================================= *)

Example a_publication_on_the_bound_carries_every_delta :
  count_of (sb_queue after_two) = 4
  /\ sb_phase after_two = PhaseLive
  /\ count_of (filter_of is_rescan (sb_queue after_two)) = 0
  /\ sb_queue after_two
     = cons (DeltaAdded 11) (cons (DeltaRemoved 12)
       (cons (DeltaAdded 13) (cons (DeltaAdded 14) nil))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example a_publication_one_past_the_bound_collapses_to_one_marker :
  count_of (sb_queue after_three) = 4
  /\ sb_phase after_three = PhaseRescanRequired
  /\ count_of (filter_of is_rescan (sb_queue after_three)) = 1
  /\ sb_queue after_three
     = cons (DeltaAdded 11) (cons (DeltaRemoved 12)
       (cons (DeltaAdded 13) (cons DeltaRescan nil))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_next_publication_after_the_marker_adds_nothing :
  spec_publish demo_composition committed_txn after_three two_deltas = after_three
  /\ spec_publish demo_composition open_txn demo_subscription two_deltas
     = demo_subscription :=
  conj eq_refl eq_refl.

Theorem the_hoarding_publisher_is_refuted :
  ~ StaysInsideTheDeclaredBound hoarding_publish.
Proof.
  intros H.
  specialize (H demo_composition committed_txn demo_subscription three_deltas
                eq_refl eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_hoarding_publisher_emits_no_marker_at_all :
  ~ EmitsExactlyOneMarkerOnOverflow hoarding_publish.
Proof.
  intros H.
  specialize (H demo_composition committed_txn demo_subscription three_deltas
                eq_refl eq_refl eq_refl eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_twin_marker_publisher_is_refuted :
  ~ EmitsExactlyOneMarkerOnOverflow twin_marker_publish.
Proof.
  intros H.
  specialize (H demo_composition committed_txn demo_subscription three_deltas
                eq_refl eq_refl eq_refl eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_resuming_publisher_is_refuted :
  ~ NoFurtherDeltaAfterTheMarker resuming_publish.
Proof.
  intros H.
  assert (Hq : sb_queue (resuming_publish demo_composition committed_txn
                           marked_subscription two_deltas)
               = sb_queue marked_subscription).
  { rewrite (H demo_composition committed_txn marked_subscription two_deltas
               eq_refl). reflexivity. }
  vm_compute in Hq. discriminate Hq.
Qed.

Theorem the_prepare_time_publisher_is_refuted :
  ~ PublishesOnlyAfterTheCommit prepare_publish.
Proof.
  intros H.
  assert (Hq : sb_queue (prepare_publish demo_composition open_txn
                           demo_subscription two_deltas)
               = sb_queue demo_subscription).
  { rewrite (H demo_composition open_txn demo_subscription two_deltas eq_refl).
    reflexivity. }
  vm_compute in Hq. discriminate Hq.
Qed.

(* The four publishers' own answers to the one overflowing publication, so
   that each is seen to differ from the specification where it differs and
   nowhere else. *)
Example the_four_publishers_differ_only_at_the_overflow :
  count_of (sb_queue (hoarding_publish demo_composition committed_txn
                        demo_subscription three_deltas)) = 5
  /\ count_of (filter_of is_rescan
       (sb_queue (twin_marker_publish demo_composition committed_txn
                    demo_subscription three_deltas))) = 2
  /\ resuming_publish demo_composition committed_txn demo_subscription three_deltas
     = after_three
  /\ prepare_publish demo_composition committed_txn demo_subscription three_deltas
     = after_three :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem the_warm_reboot_is_refuted : ~ SurvivesNoReboot warm_reboot.
Proof. intros H. specialize (H (cons demo_subscription nil)). discriminate H. Qed.

Theorem the_silent_establishment_is_refuted :
  ~ ReestablishesByRescan silent_establish.
Proof.
  intros H. destruct (H 0 0 0) as [ Hq _ ]. vm_compute in Hq. discriminate Hq.
Qed.

Example a_reboot_leaves_no_subscription_and_recovery_rescans :
  spec_reboot (cons demo_subscription (cons marked_subscription nil)) = nil
  /\ warm_reboot (cons demo_subscription nil) = cons demo_subscription nil
  /\ sb_queue (spec_establish 0 0 0) = cons DeltaRescan nil
  /\ sb_queue (silent_establish 0 0 0) = nil :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem the_ring_blocking_commit_is_refuted :
  ~ NeverBackpressuresTheCommit ring_blocking_commit.
Proof.
  intros H.
  assert (Hc : tx_committed (ring_blocking_commit nil submit_enqueued open_txn)
               = tx_committed (ring_blocking_commit nil submit_would_block open_txn)).
  { rewrite (H nil nil submit_enqueued submit_would_block open_txn). reflexivity. }
  vm_compute in Hc. discriminate Hc.
Qed.

Theorem the_queue_sensitive_commit_is_refuted :
  ~ NeverBackpressuresTheCommit queue_sensitive_commit.
Proof.
  intros H.
  assert (Hc : tx_committed (queue_sensitive_commit nil submit_enqueued open_txn)
               = tx_committed (queue_sensitive_commit
                                 (cons marked_subscription nil)
                                 submit_enqueued open_txn)).
  { rewrite (H nil (cons marked_subscription nil) submit_enqueued
               submit_enqueued open_txn). reflexivity. }
  vm_compute in Hc. discriminate Hc.
Qed.

(* The ring's two answers reach the specification's commit alike, which is
   the join RingContract.v's closed result type makes checkable. *)
Example the_commit_answers_both_of_the_ring_s_results :
  spec_commit nil submit_enqueued open_txn = spec_commit nil submit_would_block open_txn
  /\ tx_committed (spec_commit nil submit_would_block open_txn) = true
  /\ tx_committed (ring_blocking_commit nil submit_would_block open_txn) = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   The demo's own pedigree ledger, and the figures no obligation reads.

   Gap g is what these figures are; this is where they are pinned. M6.2a
   measured the hazard and F-191 records it: a field no rule reads is a
   field a weakening moves in silence, and forty-six of that item's
   fifty-five seeded survivors were exactly such fields. So every field of
   every witness this file defines is stated in a conversion here, whether
   or not an obligation above happens to read it, and so is every magnitude
   the demo composition carries.
   ========================================================================= *)

Definition all_the_extents : list Extent :=
  cons user_photos (cons work_mail (cons user_notes
  (cons spanning_extent (cons empty_extent nil)))).

Example the_ledger_covers_five_authored_extents :
  count_of all_the_extents = 5 := eq_refl.

Example every_extent_declares_its_base_span_domain_and_namespace :
  map_over ex_base all_the_extents = cons 10 (cons 50 (cons 90 (cons 40 (cons 10 nil))))
  /\ map_over ex_span all_the_extents
     = cons 40 (cons 40 (cons 20 (cons 40 (cons 0 nil))))
  /\ map_over ex_domain all_the_extents
     = cons 0 (cons 1 (cons 0 (cons 1 (cons 0 nil))))
  /\ map_over ex_space all_the_extents
     = cons 0 (cons 0 (cons 1 (cons 2 (cons 0 nil)))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Definition all_the_caps : list NsCap := cons demo_cap (cons peer_cap (cons standing nil)).

Example every_capability_declares_its_domain_namespace_and_rights :
  map_over ns_domain all_the_caps = cons 0 (cons 1 (cons 0 nil))
  /\ map_over ns_space all_the_caps = cons 0 (cons 0 (cons 0 nil))
  /\ map_over ns_rights all_the_caps = cons 2 (cons 3 (cons 5 nil)) :=
  conj eq_refl (conj eq_refl eq_refl).

Definition all_the_sessions : list Session :=
  cons demo_session (cons peer_session (cons stale_session nil)).

Example every_session_declares_its_identifier_capability_and_epoch :
  map_over se_id all_the_sessions = cons 0 (cons 1 (cons 2 nil))
  /\ map_over (fun s => ns_rights (se_cap s)) all_the_sessions
     = cons 2 (cons 3 (cons 5 nil))
  /\ map_over se_epoch all_the_sessions = cons 4 (cons 4 (cons 3 nil)) :=
  conj eq_refl (conj eq_refl eq_refl).

Example every_ask_declares_its_domain_namespace_object_and_rights :
  map_over ak_domain all_the_asks = cons 0 (cons 0 (cons 1 (cons 0 nil)))
  /\ map_over ak_space all_the_asks = cons 0 (cons 0 (cons 0 (cons 1 nil)))
  /\ map_over ak_object all_the_asks = cons 11 (cons 11 (cons 11 (cons 11 nil)))
  /\ map_over ak_rights all_the_asks = cons 2 (cons 3 (cons 2 (cons 2 nil))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_demo_entry_declares :
  en_domain demo_entry = 0
  /\ en_space demo_entry = 0
  /\ en_slot demo_entry = 6
  /\ count_of (en_components demo_entry) = 6
  /\ en_components demo_entry = cons 0 (cons 0 (cons 2 (cons 11 (cons 5 (cons 3 nil))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Definition all_the_subscriptions : list Subscription :=
  cons demo_subscription (cons marked_subscription
  (cons after_two (cons after_three nil))).

Example every_subscription_declares_its_identity_domain_and_namespace :
  map_over sb_id all_the_subscriptions = cons 0 (cons 0 (cons 0 (cons 0 nil)))
  /\ map_over sb_domain all_the_subscriptions = cons 0 (cons 0 (cons 0 (cons 0 nil)))
  /\ map_over sb_space all_the_subscriptions = cons 0 (cons 0 (cons 0 (cons 0 nil)))
  /\ map_over (fun s => count_of (sb_queue s)) all_the_subscriptions
     = cons 2 (cons 1 (cons 4 (cons 4 nil))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example every_transaction_declares_its_identifier_and_its_commit :
  tx_id committed_txn = 7
  /\ tx_committed committed_txn = true
  /\ tx_id open_txn = 8
  /\ tx_committed open_txn = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_two_publications_declare_their_deltas :
  count_of two_deltas = 2
  /\ count_of three_deltas = 3
  /\ two_deltas = cons (DeltaAdded 13) (cons (DeltaAdded 14) nil)
  /\ three_deltas
     = cons (DeltaAdded 13) (cons (DeltaAdded 14) (cons (DeltaAdded 15) nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* Every magnitude the demo composition fixes, computed rather than
   described, so that a figure edited on one side of the file and read on
   the other is a failed conversion instead of a silent disagreement. The
   declared ring capacity is RingContract.v's own reference constant, read
   here and claimed nowhere (gap f). *)
Example the_demo_composition_declares :
  index_extents demo_composition = demo_extents
  /\ count_of (index_extents demo_composition) = 3
  /\ queue_bound demo_composition = 4
  /\ result_bound demo_composition = 8
  /\ ring_capacity_declared demo_composition = ring_capacity
  /\ live_epoch demo_composition = 4
  /\ answer_discipline demo_composition = RefuseTyped
  /\ standing_cap demo_composition = standing :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl)))))).

(* And the one figure each spoiled composition moves, with the demo's
   everywhere else, so the family owes five figures rather than forty. *)
Example each_spoiled_composition_moves_its_own_field :
  index_extents (spoiled_composition_at 0)
    = cons user_photos (cons spanning_extent nil)
  /\ index_extents (spoiled_composition_at 1) = cons empty_extent nil
  /\ queue_bound (spoiled_composition_at 2) = 0
  /\ queue_bound (spoiled_composition_at 3) = S ring_capacity
  /\ result_bound (spoiled_composition_at 4) = 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example every_spoiled_composition_keeps_the_demo_s_other_figures :
  all_of (fun n => andb (Nat.eqb (live_epoch (spoiled_composition_at n)) 4)
                        (Nat.eqb (ring_capacity_declared (spoiled_composition_at n))
                                 ring_capacity)) (upto 5) = true := eq_refl.

(* The three compositions that differ only in the answer discipline, which
   is what makes gap a's difference the discipline's and not a figure's. *)
Example the_three_disciplined_compositions_differ_in_one_field :
  answer_discipline demo_composition = RefuseTyped
  /\ answer_discipline empty_answer_composition = AnswerEmpty
  /\ answer_discipline truncating_composition = GrantTruncated
  /\ queue_bound empty_answer_composition = queue_bound demo_composition
  /\ index_extents truncating_composition = index_extents demo_composition :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* -------------------------------------------------------------------------
   R-05-166's inhabitation witnesses: one closed definition per record this
   file's statements quantify over, named for that record and ascribed at
   it. The prover decides inhabitation by type-checking the ascription, so
   `run.py proofs` reads a name rather than approximating a type judgement.
   A record this file reaches through a Require is witnessed in the file
   that declares it.
   ------------------------------------------------------------------------- *)

Definition witness_Word : Word := plain 0.
Definition witness_WriteRecord : WriteRecord :=
  {| wr_address := 16; wr_word := plain 0 |}.
Definition witness_Extent : Extent := user_photos.
Definition witness_Entry : Entry := demo_entry.
Definition witness_NsCap : NsCap := demo_cap.
Definition witness_ObjCap : ObjCap := grant_of demo_cap demo_ask.
Definition witness_Ask : Ask := demo_ask.
Definition witness_Session : Session := demo_session.
Definition witness_Composition : Composition := demo_composition.
Definition witness_Subscription : Subscription := demo_subscription.
Definition witness_Txn : Txn := committed_txn.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared set
   R-05-164 currently makes empty, so "Closed under the global context" is
   that emptiness checked mechanically.
   ------------------------------------------------------------------------- *)

Print Assumptions all_of.
Print Assumptions any_of.
Print Assumptions count_of.
Print Assumptions map_over.
Print Assumptions filter_of.
Print Assumptions append_of.
Print Assumptions take_of.
Print Assumptions find_of.
Print Assumptions upto.
Print Assumptions at_member.
Print Assumptions drop_at.
Print Assumptions before_last.
Print Assumptions nat_list_eqb.
Print Assumptions andb_split.
Print Assumptions nat_eqb_refl.
Print Assumptions nat_leb_refl.
Print Assumptions leb_succ_right.
Print Assumptions leb_trans.
Print Assumptions add_succ_right.
Print Assumptions leb_add_right.
Print Assumptions leb_add_left.
Print Assumptions add_assoc_nat.
Print Assumptions all_of_cons.
Print Assumptions all_of_weaken.
Print Assumptions all_of_map.
Print Assumptions all_of_const.
Print Assumptions all_of_take.
Print Assumptions count_take_bounded.
Print Assumptions count_append_one.
Print Assumptions count_append_two.
Print Assumptions count_map_over.
Print Assumptions filter_append.
Print Assumptions filter_none.
Print Assumptions there_are_three_namespace_prohibitions.
Print Assumptions the_prohibitions_are_pairwise_distinct.
Print Assumptions there_are_three_candidate_disciplines.
Print Assumptions there_are_five_composition_conjuncts.
Print Assumptions an_admitted_composition_separates_the_domains.
Print Assumptions an_admitted_composition_places_every_index.
Print Assumptions an_admitted_composition_sizes_its_queue.
Print Assumptions count_replace_last_word.
Print Assumptions replace_last_word_untagged.
Print Assumptions map_over_plain_untagged.
Print Assumptions records_at_untagged.
Print Assumptions records_at_inside.
Print Assumptions placed_at.
Print Assumptions placed_unplaced.
Print Assumptions placed_keeps_the_tag_reading.
Print Assumptions placed_at_the_slot_stays_inside.
Print Assumptions placed_from_a_closed_body_writes_no_authority.
Print Assumptions plain_key_untagged.
Print Assumptions stamped_key_untagged.
Print Assumptions plain_key_count.
Print Assumptions sealed_key_count.
Print Assumptions capability_key_count.
Print Assumptions stamped_key_count.
Print Assumptions the_specification_writes_no_tag_inside_an_extent.
Print Assumptions the_specification_places_inside_the_declared_extent.
Print Assumptions the_specification_writes_no_authority.
Print Assumptions the_sealing_writer_keeps_the_authority_reading.
Print Assumptions the_sealing_writer_keeps_the_placement.
Print Assumptions the_capability_writer_keeps_the_placement.
Print Assumptions the_stamped_writer_keeps_the_tag_reading.
Print Assumptions the_stamped_writer_keeps_the_placement.
Print Assumptions the_spilling_writer_keeps_the_tag_reading.
Print Assumptions the_spilling_writer_keeps_the_authority_reading.
Print Assumptions the_writers_are_five.
Print Assumptions grant_of_is_derivable.
Print Assumptions truncated_grant_is_derivable.
Print Assumptions answer_under_is_derivable.
Print Assumptions the_specification_mints_nothing.
Print Assumptions the_specification_grants_nothing_without_a_live_session.
Print Assumptions the_specification_holds_no_standing_authority.
Print Assumptions the_specification_refuses_the_widening_where_the_composition_says_so.
Print Assumptions the_standing_router_mints_nothing.
Print Assumptions the_standing_router_holds_the_fabric_fixed.
Print Assumptions the_standing_router_refuses_the_widening_it_admits.
Print Assumptions the_immortal_router_mints_nothing.
Print Assumptions the_immortal_router_refuses_the_widening_it_admits.
Print Assumptions the_peer_router_grants_nothing_without_a_live_session.
Print Assumptions the_widening_router_grants_nothing_without_a_live_session.
Print Assumptions the_widening_router_holds_the_fabric_fixed.
Print Assumptions queue_of_with_queue.
Print Assumptions phase_of_with_queue.
Print Assumptions spec_publish_uncommitted.
Print Assumptions spec_publish_after_the_marker.
Print Assumptions spec_publish_fits.
Print Assumptions spec_publish_overflows.
Print Assumptions the_specification_stays_inside_the_declared_bound.
Print Assumptions the_specification_emits_exactly_one_marker.
Print Assumptions the_specification_emits_no_further_delta.
Print Assumptions the_specification_publishes_only_after_the_commit.
Print Assumptions an_overflow_leaves_the_subscription_needing_a_rescan.
Print Assumptions the_hoarding_publisher_emits_no_further_delta.
Print Assumptions the_hoarding_publisher_publishes_only_after_the_commit.
Print Assumptions the_twin_marker_publisher_emits_no_further_delta.
Print Assumptions the_twin_marker_publisher_publishes_only_after_the_commit.
Print Assumptions the_twin_marker_publisher_still_bounds_the_queue.
Print Assumptions the_resuming_publisher_publishes_only_after_the_commit.
Print Assumptions the_resuming_publisher_stays_inside_the_declared_bound.
Print Assumptions the_prepare_time_publisher_emits_no_further_delta.
Print Assumptions the_prepare_time_publisher_stays_inside_the_declared_bound.
Print Assumptions the_specification_survives_no_reboot.
Print Assumptions the_specification_reestablishes_by_rescan.
Print Assumptions the_silent_establishment_still_starts_inside_the_bound.
Print Assumptions the_specification_never_backpressures_the_commit.
Print Assumptions the_ring_blocking_commit_agrees_where_the_ring_accepted.
Print Assumptions the_queue_sensitive_commit_agrees_on_an_empty_table.
Print Assumptions the_demo_composition_is_admissible.
Print Assumptions each_spoiled_composition_breaks_exactly_one_conjunct.
Print Assumptions every_dropped_conjunct_admits_its_own_composition.
Print Assumptions no_spoiled_composition_is_admissible.
Print Assumptions the_declared_extents_separate_the_two_domains.
Print Assumptions two_extents_of_one_domain_are_unconstrained.
Print Assumptions an_empty_extent_overlaps_nothing.
Print Assumptions every_writer_is_decided_at_every_obligation.
Print Assumptions the_specification_write_lands_where_the_extent_declares.
Print Assumptions the_sealing_write_lands_at_the_same_addresses.
Print Assumptions the_spilled_write_lands_in_another_domain_s_index.
Print Assumptions the_sealing_writer_is_refuted.
Print Assumptions the_capability_writer_is_refuted.
Print Assumptions the_capability_writer_also_writes_the_authority.
Print Assumptions the_stamped_writer_is_refuted.
Print Assumptions the_spilling_writer_is_refuted.
Print Assumptions the_two_readings_of_one_sentence_are_independent.
Print Assumptions the_specification_answers_every_ask_as_the_delegation_admits.
Print Assumptions the_rights_comparison_is_exercised_on_its_boundary.
Print Assumptions a_dead_delegation_answers_nothing.
Print Assumptions the_three_disciplines_answer_one_widening_differently.
Print Assumptions every_discipline_mints_only_what_the_delegation_derives.
Print Assumptions the_answer_discipline_is_observable.
Print Assumptions the_empty_answer_discipline_does_not_refuse.
Print Assumptions the_truncating_discipline_does_not_refuse.
Print Assumptions the_standing_router_is_refuted.
Print Assumptions the_immortal_router_is_refuted.
Print Assumptions the_peer_router_is_refuted.
Print Assumptions the_peer_router_mints_what_another_session_delegated.
Print Assumptions the_widening_router_is_refuted.
Print Assumptions the_widening_router_answers_the_widening.
Print Assumptions the_two_fabrics_hold_one_delegation_fixed.
Print Assumptions a_publication_on_the_bound_carries_every_delta.
Print Assumptions a_publication_one_past_the_bound_collapses_to_one_marker.
Print Assumptions the_next_publication_after_the_marker_adds_nothing.
Print Assumptions the_hoarding_publisher_is_refuted.
Print Assumptions the_hoarding_publisher_emits_no_marker_at_all.
Print Assumptions the_twin_marker_publisher_is_refuted.
Print Assumptions the_resuming_publisher_is_refuted.
Print Assumptions the_prepare_time_publisher_is_refuted.
Print Assumptions the_four_publishers_differ_only_at_the_overflow.
Print Assumptions the_warm_reboot_is_refuted.
Print Assumptions the_silent_establishment_is_refuted.
Print Assumptions a_reboot_leaves_no_subscription_and_recovery_rescans.
Print Assumptions the_ring_blocking_commit_is_refuted.
Print Assumptions the_queue_sensitive_commit_is_refuted.
Print Assumptions the_commit_answers_both_of_the_ring_s_results.
Print Assumptions the_ledger_covers_five_authored_extents.
Print Assumptions every_extent_declares_its_base_span_domain_and_namespace.
Print Assumptions every_capability_declares_its_domain_namespace_and_rights.
Print Assumptions every_session_declares_its_identifier_capability_and_epoch.
Print Assumptions every_ask_declares_its_domain_namespace_object_and_rights.
Print Assumptions the_demo_entry_declares.
Print Assumptions every_subscription_declares_its_identity_domain_and_namespace.
Print Assumptions every_transaction_declares_its_identifier_and_its_commit.
Print Assumptions the_two_publications_declare_their_deltas.
Print Assumptions the_demo_composition_declares.
Print Assumptions each_spoiled_composition_moves_its_own_field.
Print Assumptions every_spoiled_composition_keeps_the_demo_s_other_figures.
Print Assumptions the_three_disciplined_compositions_differ_in_one_field.

(* Every returned batch is bounded and derives from the currently presented
   session capability. Result discovery and the lifetime matching-set budget
   remain storage/query-engine interfaces, not claims of this delivery guard. *)
Definition bounded_result_delivery (c : Composition) (f : Fabric) (sid : nat)
    (objects : list ObjCap) : option (list ObjCap) :=
  match live_session c f sid with
  | None => None
  | Some s =>
      if andb (Nat.leb (count_of objects) (result_bound c))
              (all_of (derivable (se_cap s)) objects)
      then Some objects else None
  end.
Theorem delivered_results_obey_the_bound_and_presented_capability : forall c f sid objects result s,
  live_session c f sid = Some s ->
  bounded_result_delivery c f sid objects = Some result ->
  result = objects /\ Nat.leb (count_of result) (result_bound c) = true /\
  all_of (derivable (se_cap s)) result = true.
Proof.
  intros c f sid objects result s Hlive Hresult.
  unfold bounded_result_delivery in Hresult; rewrite Hlive in Hresult.
  destruct (andb (Nat.leb (count_of objects) (result_bound c))
                (all_of (derivable (se_cap s)) objects)) eqn:E; try discriminate.
  inversion Hresult; subst result; apply andb_split in E as [Hb Ha].
  repeat split; assumption || reflexivity.
Qed.
Fixpoint result_copies (n : nat) (o : ObjCap) : list ObjCap :=
  match n with 0 => nil | S k => cons o (result_copies k o) end.
Example result_delivery_accepts_the_bound_and_refuses_one_past :
  bounded_result_delivery demo_composition demo_fabric 0
    (result_copies 8 (grant_of demo_cap demo_ask))
    = Some (result_copies 8 (grant_of demo_cap demo_ask)) /\
  bounded_result_delivery demo_composition demo_fabric 0
    (result_copies 9 (grant_of demo_cap demo_ask)) = None.
Proof. split; reflexivity. Qed.
Example result_delivery_cannot_launder_wider_or_stale_authority :
  bounded_result_delivery demo_composition demo_fabric 0
    (cons (grant_of demo_cap widening_ask) nil) = None /\
  bounded_result_delivery demo_composition demo_fabric 2
    (cons (grant_of demo_cap demo_ask) nil) = None.
Proof. split; reflexivity. Qed.
Print Assumptions delivered_results_obey_the_bound_and_presented_capability.
