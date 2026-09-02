(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   HandlerGraph.v

   The package composer's emitted object, as the register fixes it:
   R-12-024b's finite signed composition-time handler and translator graph,
   compiled from installed packages' interface descriptors, rebuilt and
   re-signed with the generation an install composes, never amended in a
   running one, with deterministic typed routing and none of the five
   mechanisms that entry names; R-13-002's installation path that executes
   no package-supplied code; R-13-001a's install-is-a-generation, with
   uninstall the same operation over a roster with the package removed;
   R-12-013a's closed intent variant, bounded input and output types,
   declared resource limits and interface world; R-12-024c's composition-time
   template bound from pre-composed node and bounded-ring pools, with every
   node's WCET, memory, labels and device reservation admitted under
   section 11 before it may be bound, at release time for base-image nodes
   and at install time for package-supplied ones, and its acceptance clause
   that a runtime binding creates no code, compartment, edge type or
   unbounded queue; R-13-001b's rule that no reservation is composed ahead of
   the content that would occupy it; R-08-046's declared bounded pool and
   R-08-047's typed CapacityExhausted verdict; R-12-005's bounded rings;
   R-12-024f with R-05-042 on every parsed format being inventoried
   attacker-facing wire carrying a verified parser; R-12-024e's composition
   half, that no composed edge carries authority absent from the declaring
   package's manifest; and R-08-021's flow condition read over a bound
   template's chain.

   Which entries this file is stated over is a judgment and not a reading of
   its own cell, and the judgment is taken in three steps a reviewer can check
   one at a time. M6.3a's cell cites no requirement id: it carries the class-X
   ground and points at the inspirations note. **Step one** reads the four
   core entries off the milestone's own sentence, that the package composer
   emits the finite typed handler and translator graph and pre-admitted media
   templates: R-12-024b is the graph, R-12-024c the template, R-12-024f the
   formats it parses, R-12-013a the transformation type an edge is.
   **Step two** takes the ids those four spell out, which is a reading and not
   a judgment: R-12-024b's sentence cites R-13-001a and its acceptance clause
   R-13-001 and R-13-002, and R-12-024f's acceptance clause cites R-05-042.
   Those four and no others. One entry cites back the other way and is
   therefore also a reading: R-13-001b's acceptance clause names R-12-024c by
   id, to say that a composition-time template is not the pre-proved empty
   slot it forbids. Of the five step two reaches, four carry a statement
   below and R-13-001 carries none: it is the ordinary install path the graph
   is admitted on, which is the act M6.2a states in AdmissionPath.v, and this
   file says that the graph is emitted and never how it is admitted. A
   derived scope that named it and stated nothing over it would be a scope
   a reviewer cannot check, so it is named here with what it is owed by.
   **Step three** is the judgment, and it reaches five
   entries by a noun one of the four uses and does not itself define:
   R-12-024c's "pools" reaches R-08-046, which says what a declared bounded
   pool is, and R-08-047, which says what a full one answers; its
   "bounded-ring" reaches R-12-005; its acceptance clause's "confidentiality
   domain" reaches R-08-021, which is where a flow condition over levels
   lives; and R-12-024b's "routing" reaches R-12-024e, which is the entry
   that says what routing may and may not carry. A reviewer who disagrees
   with the scope disagrees with step three rather than with a statement
   below; steps one and two are checkable against the register's own text.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. Every quantity a composition
   fixes is a field of the Machine record rather than a literal or a
   top-level Parameter, which is what keeps the R-05-163 assumption gate
   green while leaving the decision where its owner can make it. Nothing is
   admitted and nothing is axiomatized: the Print Assumptions block at the
   end reports every shipped constant closed under the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. Nothing here is compiled,
   lowered, or run on either emulator; no content format is decoded, no
   object is hashed, no ring is instantiated, no signature is checked, and no
   node executes. The computed checks are decided inside the kernel by
   conversion and print nothing.

   What is deferred, and to which item. M6.3b owns the contained object
   router: private namespaces, intents at run time, live queries,
   R-12-024d's deterministic translation cache and its key, and
   protocol-bound credential handles. Nothing below states any of that, and
   in particular no cache, no cache key and no domain confinement appears
   here. M6.2a owns the admission of the object this file emits:
   AdmissionPath.v's package, derivation and verdict belong to the act this
   graph is admitted *by*, and R-13-001c is what puts the composer outside
   every trust base on both sides of that seam. KeyspaceDomains.v already
   states R-12-024e's *resolution* face at the storage side, its namespace
   and object capabilities and its derivability relation; this file states
   only that entry's composition-side half, that no composed edge's declared
   bounds exceed the declaring package's manifest, and states nothing about
   how an object capability is derived or what a session delegates.

   One clause of a cited entry is deferred rather than stated, and it is
   named here rather than left to a reader to notice. R-08-047's sentence
   names four obligations of the typed `CapacityExhausted(pool)` verdict: it
   cannot be dropped, it cannot be converted into an implicit wait, it cannot
   be answered by borrowing from another pool, and it is relevance-graded
   under R-05-097's discipline. Three of the four are stated at O14 below,
   where the entry's own fail-closed line adds a further predicate beside
   them. The relevance grade is not, and it is not a
   gap either: R-05-098 puts "bounded-pool binding outcomes (R-08-047)" on
   its closed list of results that carry the grade, and its acceptance clause
   puts the grade *in the IDL or ABI declaration*, which M6.0b's typed IDL
   profile authors and M6.4 generates bindings from. R-05-097's own
   acceptance clause puts the enforcement in a derivation that fails to
   type-check when a graded value is dropped, which is the CHERI-TAL track's.
   Neither is a composer's act, and a Gallina function cannot exhibit the
   denial of weakening in any case, its own metatheory admitting it. So
   `Verdict` below carries no grade marker and nothing below claims one.

   Three landed artifacts state neighbouring facts, and the lines between
   them are drawn here rather than left for a reviewer to find. AdmissionPath.v
   has a composer that turns a roster into a generation and an `Ambient` its
   *checker* must not read; this file's `Ambient` is the *composer's*, being
   what a composition observes at the moment it runs, and obligation 1 below
   is that file's reading 1 at a different subject rather than a second
   statement of one fact. SupervisionTree.v has a loader obliged to return
   the signed composition whatever it observes; that loader reads a roster
   out of a generation and this composer compiles a graph out of interface
   descriptors, so the two are the same shape at two objects. Neither of
   those files carries an edge, a template, a pool or a format.

   No Require. Nothing beyond the Rocq prelude is reachable, so Classical and
   FunctionalExtensionality are unavailable and every equality below is
   stated pointwise or over a decidable boolean for that reason. A Require
   naming a sibling artifact would be admissible and there is none to name:
   the three neighbours above meet this file's subject nowhere, so a Require
   here would be a citation rather than a dependency. There is a second
   reason and it is a cost rather than a principle: `run.py seed coq`
   recompiles every source under proofs/ for every mutant it stages, so a
   Require is paid once per member of the seeded population.

   Readings of the register this statement takes, each a reviewable judgment
   rather than a neutral transcription:

   1. What a composer observes at composition time is the ambient, and the
      emitted graph does not vary with it. R-12-024b makes the graph a
      composition-time object compiled from installed packages' interface
      descriptors, so the descriptors and the roster are its whole input and
      anything else the composition can see is excluded by that sentence.
      `Ambient` below carries a probe and a clock, standing for whatever a
      composer could read, and the obligation quantifies over two of them.
   2. A node is a package on the composed roster and an edge is a
      transformation one package declares. R-12-024b's own sentence gives no
      node set beyond "compiled from installed packages' interface
      descriptors", and it is the spec's prose at that entry's anchor that
      says nodes are already-admitted compartments and an edge is the
      section 12 IDL transformation type. This file takes the register's
      narrower reading: a node is an index below the package count and an
      edge names its declaring package and the node it routes to. That is
      the finite-index choice SupervisionTree.v took at the roster, taken
      here at the package set, and the distance between the two readings is
      exactly what gap d is about, the prose's compartment set being wider
      than the roster the entry gives.
   3. Executing package-supplied code is modelled refutably rather than as an
      absence. R-13-002 forbids maintainer scripts, post-install execution
      and runtime code fetching, and an absence cannot be refuted, so the
      machine carries a `script` field per package producing edges and the
      obligation is that the emitted graph is unchanged when that field is
      replaced by an arbitrary other one. The executing composer appends what
      the script produced and is refuted at exactly that quantifier.
   4. Well-formedness is a list of conjuncts rather than a nest of
      conjunctions. `edge_conjuncts` holds twelve predicates and
      `admissible_edge` is `all_of` over them, so a composer that drops one
      conjunct is `compose_without` at that index rather than a construction
      authored by hand, and the count of conjuncts a malformed edge breaks is
      a measure rather than an assertion. R-12-024b, R-12-013a, R-12-024e,
      R-12-024f and R-12-005 each own one or more of the twelve, and the
      comment at each conjunct says which.
   5. Routing is stated at selection and not at binding. R-12-013a declares a
      transformation's resource limits and the spec's prose makes routing
      deterministic graph selection under the caller's requested intent and
      resource bound; neither entry puts the comparison of the two on a side,
      and this file compares them where the selection happens. Gap h records
      that the register does not choose.
   6. An intent is an index below a count and a name beside it. R-12-013a
      fixes that an intent is a closed variant rather than an executable name
      or command string and closes no variant set anywhere, so `Intent`
      carries an index the specification routes on and a caller-supplied name
      it ignores, and the obligation is that two intents agreeing on the
      index route identically. Inventing an inductive for the variants would
      be closing an enumeration the R-05-150 review gate audits, which is the
      author's act and not this file's.
   7. A media template is an ordered chain of stages and its ends are typed.
      R-12-013a's bounded input and output types are read over the chain: the
      output type of stage i is the input type of stage i+1, and the chain's
      own first input and last output are the template's declared ones. The
      stage *set* is a field, because no entry closes it; the spec's
      parenthetical names four stages and a parenthetical the register does
      not carry is not an enumeration the review gate audits (gap a).
   8. Boundedness is stated at two places because the register states it at
      two. R-12-005 and R-12-024c's bounded-ring pools fix a declared ring
      depth at *composition*, which is conjunct 10 and conjunct 11 below and
      the template's own ring conjuncts; R-12-024c's acceptance clause
      forbids an unbounded queue at *binding*, which is `CreatedUnboundedQueue`
      in the forbidden-creation enumeration. They are two halves and not one
      clause stated twice: a composer can emit a zero-depth ring without any
      binding creating a queue, and a binder can create one over a graph
      whose every declared depth is inside the ceiling.
   9. Every generated family is a list of constructions whose fallback past
      the last index is the specification's own. That is what makes a bounded
      quantifier over the index decide anything: a bound raised by one reaches
      the fallback, where the specification's construction satisfies the
      obligation the family is refuted for breaking, so the theorem fails
      rather than holding vacuously wider.
  10. Boolean rather than propositional wherever the witnesses must compute:
      the well-formedness conjuncts, the template check, the selection and
      the pool arithmetic are decidable, so the generated families below are
      checked by conversion in the silent Example form rather than by a proof
      per member.

   The literals taken from the design, and there are seven. The criterion is
   the same at each: one sentence of one entry names its members and closes
   the set, and the count sits beside the sentence rather than in prose. A
   sentence that names no member closes nothing, which is why the stage set
   (gap a) and the intent variants (gap c) are fields and not enumerations:

   - R-12-024b's "no runtime registration, executable lookup, shell command,
     plugin load, or content sniffing" is five, so `all_banned_mechanisms` is
     that list and `there_are_five_banned_mechanisms` is its count.
   - R-12-024c's "every node's WCET, memory, labels, and device reservation
     admitted under section 11" is four, so `all_admitted_quantities` is that
     list and `there_are_four_admitted_quantities` is its count.
   - R-12-024c's acceptance clause, "runtime binding creates no code,
     compartment, edge type, or unbounded queue", is four, so
     `all_forbidden_creations` is that list and
     `there_are_four_forbidden_creations` is its count.
   - R-12-024c's "at release time for base-image nodes and at install time
     for package-supplied ones" is two, so `NodeOrigin` has two constructors
     and `there_are_two_node_origins` is its count. The admission *time* is
     not a third enumeration: a node's admission time is named by the origin
     whose time it is, so the obligation is an equality between two values of
     one type rather than a correspondence between two types.
   - R-12-024c's "pre-composed node and bounded-ring pools" is two, so `Pool`
     has two constructors and `there_are_two_pools` is its count. R-08-047's
     `CapacityExhausted(pool)` is a verdict over that type rather than an
     enumeration of its own.
   - R-12-024f's acceptance clause, "the image, media, font, archive, and
     document formats the graph admits appear in the R-05-042 inventory on
     the same terms as the radio and USB grammars", is five, so `FormatClass`
     has five constructors and `there_are_five_format_classes` is its count.
     What "on the same terms" is made to decide is that no class of the five
     is exempt: the obligation is quantified over the closed list, so
     dropping a constructor drops an obligation, and one exempting composer
     per class is refuted.
   - R-12-013a's acceptance clause, "no desktop-specific wire protocol,
     open-ended intent string, or authority-bearing path is introduced", is
     three, so `ForbiddenIntroduction` has three constructors and
     `there_are_three_forbidden_introductions` is its count. Each of the
     three is read at a quantity the composition already fixes, so the
     enumeration collects three obligations rather than inventing a fourth,
     and each is refuted by a construction this file already carries.

   Every other magnitude is a field: the package count and the composed
   roster, each package's declared edges, script, manifest width, origin,
   admission time, admitted quantities and confidentiality label, the type
   count, the intent count, the world count, the wire-format inventory with
   its per-format verified-parser flag and its per-format class, the node and
   ring pool capacities,
   the ring depth ceiling, the template's stage list and its declared end
   types, the declared inter-level channels, whether an ambiguous graph is
   admitted, and the graph's own identity.

   How the refutations are generated. A refutation is a seeded weakening the
   theorem must reject, so the families below are produced mechanically
   rather than authored one by one, which is DischargeSequence.v's method and
   SupervisionTree.v's, taken to a graph and a chain. Over the demo
   template's stage chain: `swap_at` transposes an adjacent pair, `drop_at`
   deletes a stage, `suffix_at` re-enters at a proper suffix, and `insert_at`
   binds one stage a second time, and the four families are refused as one
   conversion and again per family and again as theorems quantified over the
   index. Over the twelve well-formedness conjuncts: `spoiled_at` sets one
   field of the composed edge to the value on that conjunct's own boundary
   and `compose_without` drops one conjunct from the composer's own filter,
   so the twelve conjuncts are decided twice, once
   from the edge side and once from the composer side. Over the four closed
   enumerations that name a defect: five amenders, one per banned mechanism;
   four partial binders, one per admitted quantity dropped; four creating
   binders, one per forbidden creation; and five exempting composers with an
   uninventoried edge apiece, one per format class. The hand-authored
   refutations are the ones no index generates, being alternative
   constructions rather than mutations of a list.

   What this file deliberately does not author, with the entry that owes each
   decision. A register gap is reported, not closed. One lettered item, e, is
   not a gap and keeps its letter, so that the letters below it do not move
   and the finding indexed at it goes on naming the question it answers:

   a. What stages a media template may carry. R-12-024c names templates,
      pools and the four admitted quantities and names no stage; the spec's
      parenthetical names demux/decode, colour or sample conversion,
      resample/mix, and render or audio output, and a parenthetical the
      register does not carry is not an enumeration the review gate audits.
      So the stage count and the stage kinds are fields and the demo
      instantiates them. Owed at R-12-024c.
   b. Whether a graph may carry two edges matching one intent. R-12-024b
      requires deterministic typed routing, and a deterministic selector over
      an ambiguous graph and one over an unambiguous graph are both
      deterministic; the two disciplines differ observably on a graph with
      two matching edges, where a first-match and a last-match selector
      disagree and each is a function of the graph, the intent and the bound.
      `ambiguity_admitted` is a field, both disciplines are exhibited, each is
      proved to keep every obligation the other keeps, and
      `the_ambiguity_is_observable` machine-checks the difference. Owed at
      R-12-024b.
   c. Which intent variants the closed variant closes. R-12-013a fixes that
      an intent is a closed variant rather than an executable name or command
      string and closes no variant set anywhere, so `intent_count` is a field
      and an intent is a finite index below it. Owed at R-12-013a.
   d. Whether the graph may carry a node for R-13-010b's shared service
      compartment. That entry's duplication pass emits one shared service
      compartment into the composed image in place of a library statically
      linked into each consumer: a compartment, and no package on the roster
      the composer was handed. Nothing says whether a handler-graph edge may
      name it as an endpoint. The closure obligation below refuses one,
      because R-12-024b's own sentence gives the composer no node set but the
      installed packages it compiled the descriptors from; the spec's prose
      at that anchor says nodes are already-admitted compartments, which is
      the wider set that would admit it, and the two readings differ exactly
      here (reading 2). Owed at R-13-010b or R-12-024b.
   e. Not a gap, and named here because it reads like one. The question is
      whether R-05-050's hand-transcribed exception reaches a graph node's
      format, and three entries answer it. R-12-024f's own sentence: every
      content format a translator or media node parses "carries a section 5
      Narcissus copy-once verified parser and is enumerated in the wire-format
      inventory", with no exception clause; R-05-042 makes the hand-written
      attacker-facing set empty except as R-05-050 permits, and R-05-050
      permits exactly one format, 5G-core NAS, which is neither an image,
      media, font, archive nor document format the graph admits. R-12-084a
      decides the media case a third time by name. So the exception does not
      reach a graph node's format, conjunct 8 below requires the verified
      parser of every admitted edge unconditionally, and `verified_parser`
      stays a per-format field only because *which* formats an inventory
      carries is a composition (gap j), not because the obligation over them
      is open. What R-12-024f does leave to this file is the "same terms"
      clause over the five families it names, which is O20 and the sixth
      closed enumeration.
   f. At what granularity the graph is re-signed. R-12-024b has it rebuilt
      and re-signed with the generation an install composes and its
      acceptance clause calls it a typed signed configuration object carried
      by the generation root; whether that is one signature or a second one
      over the graph object is not fixed, and the difference is observable on
      R-10-030's retained roots when R-11-002 pins a prior one.
      `graph_identity` is a field and nothing below reads it as a signature.
      Owed at R-12-024b or R-10-030.
   g. Whether binding a template consumes a schedule slot the composition
      reserved. R-12-024c requires each node's four quantities admitted under
      section 11 before it may be bound, section 11's admission is over the
      task set and the schedule, and R-11-008's two standing reservations are
      the display scanout and the revocation sweep and name neither a node
      pool nor a template. So whether a run-time binding is free against an
      already-admitted schedule or consumes a reserved class is undecided,
      and the four-quantity obligation below is stated without deciding it.
      Owed at R-12-024c or R-11-008.
   h. Whether an edge's declared resource limit is compared against the
      caller's requested bound at selection or at binding, and what a caller
      bound looser than the edge's limit means. R-12-013a declares the
      transformation's resource limits and the spec makes routing selection
      under the caller's requested intent and resource bound; neither puts
      the comparison on a side. This file compares at selection and says so
      as reading 5. Owed at R-12-013a or R-12-024b.
   i. Whether the graph carries one of R-13-011's three assurance tiers.
      R-12-024b makes it a typed signed configuration object admitted on the
      ordinary install path, and R-13-011's acceptance clause is that every
      admitted artifact carries exactly one tier and its required evidence; a
      configuration object is data rather than code, so either it is not an
      admitted artifact in that entry's sense or it carries a tier and
      required evidence nothing names. This file assigns none. Owed at
      R-13-011 or R-12-024b.
   j. Every composition magnitude. The package count, the roster, each
      package's declared edges, script, manifest width, origin, admission
      time, admitted quantities and label, the type, intent and world counts,
      the inventory with its per-format parser flag and its per-format class,
      the two pool capacities,
      the ring depth ceiling, the template's stages and end types, the
      declared channels, the ambiguity discipline and the graph identity are
      fields; the demo machine at the end instantiates each with a witness
      value that carries no composition claim, and the ledger pins every one
      of them.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary composer, selector, installer, binder, admission
   schedule, template or amender, proved of the specification, and refuted of
   an alternative construction the register's own sentence excludes.
   Inhabitation is concrete: a roster of four packages whose descriptors
   declare sixteen edges of which four are admissible and twelve break one
   conjunct each, a composed graph, intents that route and an intent that
   fails closed, a media template that binds and sixteen generated weakenings
   of it that do not, one edge per format class carrying a format the
   inventory does not hold, both pools with an occupancy sitting exactly on
   the capacity boundary, and a value on the boundary of every comparison the
   file makes. The ledger at the end pins every field of every witness no
   obligation reads, which is the hazard M6.2a measured: a field nothing
   reads is a field a weakening moves in silence.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   List and boolean helpers, defined here rather than imported: the prelude
   carries the list type and not the library over it, and importing a module
   to save a dozen lines would put its assumptions inside the R-05-163 gate's
   reach for no gain.
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

Fixpoint concat_of {A : Type} (l : list (list A)) : list A :=
  match l with nil => nil | cons x r => app x (concat_of r) end.

(* 0 through n-1, in that order: the index set every generated family below
   ranges over. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

Definition before_last (n : nat) : nat :=
  match n with 0 => 0 | S k => k end.

(* The nth member of a list, or the declared fallback past its end. Reading 9
   is what this is for: every generated family below is a list of
   constructions whose fallback is the specification's own, so a bounded
   quantifier over the index decides something at the bound rather than
   widening into a case that satisfies it for free. *)
Fixpoint at_member {A : Type} (l : list A) (n : nat) (dflt : A) : A :=
  match l with
  | nil => dflt
  | cons x r => match n with 0 => x | S k => at_member r k dflt end
  end.

Fixpoint mem_nat (x : nat) (l : list nat) : bool :=
  match l with
  | nil => false
  | cons y r => orb (Nat.eqb x y) (mem_nat x r)
  end.

Fixpoint remove_nat (x : nat) (l : list nat) : list nat :=
  match l with
  | nil => nil
  | cons y r => if Nat.eqb x y then remove_nat x r else cons y (remove_nat x r)
  end.

(* Transpose the adjacent pair at n, delete the member at n, re-enter at the
   suffix beginning at n, and bind one member a second time at n. The four
   generators of the template families (R-05-166). *)
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

(* The first member satisfying a predicate, or none. The selection below is
   this and nothing else, which is what lets a selector's obligations be read
   off three small lemmas rather than off a decidable equality on edges. *)
Fixpoint find_of {A : Type} (p : A -> bool) (l : list A) : option A :=
  match l with
  | nil => None
  | cons x r => if p x then Some x else find_of p r
  end.

(* The last member satisfying a predicate, which is the other deterministic
   discipline gap b leaves open. *)
Fixpoint find_last_of {A : Type} (p : A -> bool) (l : list A) : option A :=
  match l with
  | nil => None
  | cons x r =>
      match find_last_of p r with
      | Some y => Some y
      | None => if p x then Some x else None
      end
  end.

Definition is_some {A : Type} (o : option A) : bool :=
  match o with Some _ => true | None => false end.

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

Lemma andb_join : forall a b : bool, a = true -> b = true -> andb a b = true.
Proof. intros a b Ha Hb. rewrite Ha. rewrite Hb. reflexivity. Qed.

Lemma nat_leb_refl : forall n : nat, Nat.leb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma nat_eqb_refl : forall n : nat, Nat.eqb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma leb_trans :
  forall a b c : nat,
    Nat.leb a b = true -> Nat.leb b c = true -> Nat.leb a c = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b c Hab Hbc.
  - reflexivity.
  - destruct b as [ | y ]; [ discriminate Hab | ].
    destruct c as [ | z ]; [ discriminate Hbc | ].
    simpl in Hab. simpl in Hbc. simpl. exact (IH y z Hab Hbc).
Qed.

(* A conjunction over a list read back at a stronger predicate, and the two
   facts about `filter_of` every closure proof below rests on. *)
Lemma all_of_mono :
  forall (A : Type) (p q : A -> bool) (l : list A),
    (forall x : A, p x = true -> q x = true) ->
    all_of p l = true -> all_of q l = true.
Proof.
  intros A p q l Himp. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    simpl. apply andb_join; [ exact (Himp x Hx) | exact (IH Hr) ].
Qed.

Lemma all_of_filter_self :
  forall (A : Type) (p : A -> bool) (l : list A),
    all_of p (filter_of p l) = true.
Proof.
  intros A p l. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. destruct (p x) eqn:Hx.
    + simpl. rewrite Hx. simpl. exact IH.
    + exact IH.
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

(* Everything is a member of the list it came from: what makes a graph whose
   node set is the roster closed without any further hypothesis. *)
Lemma mem_nat_cons :
  forall (x y : nat) (l : list nat),
    mem_nat x l = true -> mem_nat x (cons y l) = true.
Proof.
  intros x y l H. simpl. rewrite H.
  destruct (Nat.eqb x y); reflexivity.
Qed.

Lemma all_of_mem_self :
  forall l : list nat, all_of (fun n => mem_nat n l) l = true.
Proof.
  intros l. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. rewrite nat_eqb_refl. simpl.
    apply (all_of_mono nat (fun n => mem_nat n r)
                       (fun n => orb (Nat.eqb n x) (mem_nat n r)) r).
    + intros n Hn. rewrite Hn. destruct (Nat.eqb n x); reflexivity.
    + exact IH.
Qed.

(* Reading a conjunction over `upto n` back at one of its members: the lemma
   that lets a bounded family be stated of an arbitrary index. *)
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

(* The three facts a selection carries, each stated once over an arbitrary
   predicate so that every selector below is an instance rather than a fourth
   induction. *)
Lemma find_of_holds :
  forall (A : Type) (p : A -> bool) (l : list A) (x : A),
    find_of p l = Some x -> p x = true.
Proof.
  intros A p l. induction l as [ | y r IH ]; intros x H.
  - discriminate H.
  - simpl in H. destruct (p y) eqn:Hy.
    + injection H as H. rewrite <- H. exact Hy.
    + exact (IH x H).
Qed.

Lemma find_of_in :
  forall (A : Type) (q p : A -> bool) (l : list A) (x : A),
    all_of q l = true -> find_of p l = Some x -> q x = true.
Proof.
  intros A q p l. induction l as [ | y r IH ]; intros x Hq H.
  - discriminate H.
  - simpl in Hq. destruct (andb_split _ _ Hq) as [ Hy Hr ].
    simpl in H. destruct (p y) eqn:Hp.
    + injection H as H. rewrite <- H. exact Hy.
    + exact (IH x Hr H).
Qed.

Lemma find_of_none :
  forall (A : Type) (p : A -> bool) (l : list A),
    any_of p l = false -> find_of p l = None.
Proof.
  intros A p l. induction l as [ | y r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (p y) eqn:Hy; simpl in H.
    + discriminate H.
    + simpl. rewrite Hy. exact (IH H).
Qed.

Lemma find_last_of_holds :
  forall (A : Type) (p : A -> bool) (l : list A) (x : A),
    find_last_of p l = Some x -> p x = true.
Proof.
  intros A p l. induction l as [ | y r IH ]; intros x H.
  - discriminate H.
  - simpl in H. destruct (find_last_of p r) as [ z | ] eqn:Hr.
    + injection H as H. rewrite <- H. exact (IH z eq_refl).
    + destruct (p y) eqn:Hy; [ | discriminate H ].
      injection H as H. rewrite <- H. exact Hy.
Qed.

Lemma find_last_of_in :
  forall (A : Type) (q p : A -> bool) (l : list A) (x : A),
    all_of q l = true -> find_last_of p l = Some x -> q x = true.
Proof.
  intros A q p l. induction l as [ | y r IH ]; intros x Hq H.
  - discriminate H.
  - simpl in Hq. destruct (andb_split _ _ Hq) as [ Hy Hr ].
    simpl in H. destruct (find_last_of p r) as [ z | ] eqn:Hf.
    + injection H as H. rewrite <- H. exact (IH z Hr eq_refl).
    + destruct (p y) eqn:Hp; [ | discriminate H ].
      injection H as H. rewrite <- H. exact Hy.
Qed.

Lemma find_last_of_none :
  forall (A : Type) (p : A -> bool) (l : list A),
    any_of p l = false -> find_last_of p l = None.
Proof.
  intros A p l. induction l as [ | y r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (p y) eqn:Hy; simpl in H.
    + discriminate H.
    + simpl. rewrite (IH H). rewrite Hy. reflexivity.
Qed.

(* The helpers' own floors, so that the day one of them stops deciding is the
   day it says so. Each is a base case no check below reaches. *)
(* Each floor is stated beside the case one step above it, so that the
   constant the floor happens to carry is read rather than merely written:
   an empty conjunction holds whatever its predicate says, and a one-member
   one does not. *)
Example the_empty_conjunction_holds :
  all_of (fun _ : nat => false) nil = true
  /\ all_of (fun _ : nat => false) (cons 0 nil) = false := conj eq_refl eq_refl.

Example the_empty_disjunction_fails :
  any_of (fun _ : nat => true) nil = false
  /\ any_of (fun _ : nat => true) (cons 0 nil) = true := conj eq_refl eq_refl.

Example nothing_has_length_zero : count_of (nil : list nat) = 0 := eq_refl.

Example the_empty_concatenation : concat_of (nil : list (list nat)) = nil := eq_refl.

Example before_last_of_nothing : before_last 0 = 0 := eq_refl.

Example the_index_set_of_three : upto 3 = cons 0 (cons 1 (cons 2 nil)) := eq_refl.

Example nothing_is_a_member_of_nothing : mem_nat 0 nil = false := eq_refl.

Example a_member_is_found_and_a_stranger_is_not :
  mem_nat 2 (cons 0 (cons 1 (cons 2 nil))) = true
  /\ mem_nat 9 (cons 0 (cons 1 (cons 2 nil))) = false := conj eq_refl eq_refl.

Example removing_what_is_absent_changes_nothing :
  remove_nat 9 (cons 0 (cons 1 nil)) = cons 0 (cons 1 nil)
  /\ remove_nat 0 (cons 0 (cons 1 nil)) = cons 1 nil := conj eq_refl eq_refl.

Example the_fallback_is_reached_past_the_last_index :
  at_member (cons 7 (cons 8 nil)) 0 3 = 7
  /\ at_member (cons 7 (cons 8 nil)) 1 3 = 8
  /\ at_member (cons 7 (cons 8 nil)) 2 3 = 3 :=
  conj eq_refl (conj eq_refl eq_refl).

Example nothing_is_found_in_nothing :
  find_of (fun _ : nat => true) nil = None
  /\ find_of (fun _ : nat => true) (cons 0 nil) = Some 0
  /\ find_last_of (fun _ : nat => true) nil = None
  /\ find_last_of (fun _ : nat => true) (cons 0 nil) = Some 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_first_and_the_last_differ_where_two_match :
  find_of (fun n => Nat.ltb 0 n) (cons 0 (cons 1 (cons 2 nil))) = Some 1
  /\ find_last_of (fun n => Nat.ltb 0 n) (cons 0 (cons 1 (cons 2 nil))) = Some 2
  /\ find_of (fun n => Nat.ltb 1 n) (cons 0 (cons 1 (cons 2 nil))) = Some 2
  /\ find_last_of (fun n => Nat.ltb 1 n) (cons 0 (cons 1 (cons 2 nil))) = Some 2 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example something_is_present_and_nothing_is_absent :
  is_some (Some 0) = true /\ is_some (None : option nat) = false :=
  conj eq_refl eq_refl.

(* =========================================================================
   The seven closed enumerations, and only these seven, with R-08-047's typed
   verdict beside them as a variant carrying a member of the fifth of them
   rather than an enumeration of its own. Each is closed because one sentence
   of one entry names its members and closes the set, and that sentence is
   quoted at the enumeration; an eighth here would be this file inventing one
   where the register leaves a composition, which is exactly the line a
   statement artifact does not cross. The two the reader looks for and does
   not find are the media template's stage set (gap a) and the intent
   variants (gap c), and each is absent for the same reason: the entry that
   would close it names no member.
   ========================================================================= *)

(* R-12-024b: "no runtime registration, executable lookup, shell command,
   plugin load, or content sniffing". Five routes into a running graph, and
   the entry's own order. *)
Inductive BannedMechanism : Type :=
| RuntimeRegistration          (* a handler registering itself while running  *)
| ExecutableLookup             (* a handler reached by looking up a name      *)
| ShellCommand                 (* a handler reached by running a command      *)
| PluginLoad                   (* a handler arriving as a loadable object     *)
| ContentSniffing.             (* an edge chosen by guessing at the content   *)

(* R-12-024c: "every node's WCET, memory, labels, and device reservation
   admitted under section 11 before it may be bound". Four quantities, the
   entry's own order. *)
Inductive AdmittedQuantity : Type :=
| AdmittedWcet
| AdmittedMemory
| AdmittedLabels
| AdmittedDeviceReservation.

(* R-12-024c's acceptance clause: "runtime binding creates no code,
   compartment, edge type, or unbounded queue". Four creations, the entry's
   own order. The fourth is the binding-time half of boundedness, whose
   composition-time half is the ring-depth conjuncts below (reading 8). *)
Inductive ForbiddenCreation : Type :=
| CreatedCode
| CreatedCompartment
| CreatedEdgeType
| CreatedUnboundedQueue.

(* R-12-024c: "at release time for base-image nodes and at install time for
   package-supplied ones". Two origins, and the admission time is named by
   the origin whose time it is rather than by a third enumeration. *)
Inductive NodeOrigin : Type :=
| BaseImage
| PackageSupplied.

(* R-12-024c: "pre-composed node and bounded-ring pools". Two pools, and
   R-08-047's typed verdict carries a member of this type rather than being
   an eighth enumeration. *)
Inductive Pool : Type :=
| NodePool
| RingPool.

(* R-12-024f's acceptance clause: "the image, media, font, archive, and
   document formats the graph admits appear in the R-05-042 inventory on the
   same terms as the radio and USB grammars". Five classes, the entry's own
   order. What the class is for is the "same terms" clause: the obligation
   below is quantified over this list, so a class exempted from the inventory
   is a refutation and dropping a constructor drops an obligation. *)
Inductive FormatClass : Type :=
| ImageFormat
| MediaFormat
| FontFormat
| ArchiveFormat
| DocumentFormat.

(* R-12-013a's acceptance clause: "no desktop-specific wire protocol,
   open-ended intent string, or authority-bearing path is introduced". Three
   introductions, the entry's own order. Each is read at a quantity the
   composition already fixes: the declared interface world, the
   caller-supplied intent name the selection ignores, and the declaring
   package's manifest an edge's bounds sit inside. *)
Inductive ForbiddenIntroduction : Type :=
| DesktopWireProtocol
| OpenEndedIntentString
| AuthorityBearingPath.

(* R-08-047: "A request to bind a member of a full pool returns a typed
   `CapacityExhausted(pool)` verdict". The pool is the argument, which is
   what makes the verdict name the pool that is actually full rather than
   merely report a shortfall. The same sentence's relevance-grading clause is
   deferred and the header says to whom. *)
Inductive Verdict : Type :=
| Bound
| CapacityExhausted (p : Pool).

Definition all_banned_mechanisms : list BannedMechanism :=
  cons RuntimeRegistration (cons ExecutableLookup (cons ShellCommand
  (cons PluginLoad (cons ContentSniffing nil)))).

Definition all_admitted_quantities : list AdmittedQuantity :=
  cons AdmittedWcet (cons AdmittedMemory (cons AdmittedLabels
  (cons AdmittedDeviceReservation nil))).

Definition all_forbidden_creations : list ForbiddenCreation :=
  cons CreatedCode (cons CreatedCompartment (cons CreatedEdgeType
  (cons CreatedUnboundedQueue nil))).

Definition all_node_origins : list NodeOrigin :=
  cons BaseImage (cons PackageSupplied nil).

Definition all_pools : list Pool := cons NodePool (cons RingPool nil).

Definition all_format_classes : list FormatClass :=
  cons ImageFormat (cons MediaFormat (cons FontFormat
  (cons ArchiveFormat (cons DocumentFormat nil)))).

Definition all_forbidden_introductions : list ForbiddenIntroduction :=
  cons DesktopWireProtocol (cons OpenEndedIntentString
  (cons AuthorityBearingPath nil)).

(* The seven counts, checked by conversion rather than claimed. The day an
   entry admits a sixth banned mechanism is the day one of them stops
   holding. *)
Example there_are_five_banned_mechanisms :
  count_of all_banned_mechanisms = 5 := eq_refl.

Example there_are_four_admitted_quantities :
  count_of all_admitted_quantities = 4 := eq_refl.

Example there_are_four_forbidden_creations :
  count_of all_forbidden_creations = 4 := eq_refl.

Example there_are_two_node_origins : count_of all_node_origins = 2 := eq_refl.

Example there_are_two_pools : count_of all_pools = 2 := eq_refl.

Example there_are_five_format_classes :
  count_of all_format_classes = 5 := eq_refl.

Example there_are_three_forbidden_introductions :
  count_of all_forbidden_introductions = 3 := eq_refl.

Definition mechanism_eqb (a b : BannedMechanism) : bool :=
  match a, b with
  | RuntimeRegistration, RuntimeRegistration => true
  | ExecutableLookup, ExecutableLookup => true
  | ShellCommand, ShellCommand => true
  | PluginLoad, PluginLoad => true
  | ContentSniffing, ContentSniffing => true
  | _, _ => false
  end.

Lemma mechanism_eqb_refl : forall a : BannedMechanism, mechanism_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma mechanism_eqb_true :
  forall a b : BannedMechanism, mechanism_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition quantity_eqb (a b : AdmittedQuantity) : bool :=
  match a, b with
  | AdmittedWcet, AdmittedWcet => true
  | AdmittedMemory, AdmittedMemory => true
  | AdmittedLabels, AdmittedLabels => true
  | AdmittedDeviceReservation, AdmittedDeviceReservation => true
  | _, _ => false
  end.

Lemma quantity_eqb_refl : forall a : AdmittedQuantity, quantity_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma quantity_eqb_true :
  forall a b : AdmittedQuantity, quantity_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition creation_eqb (a b : ForbiddenCreation) : bool :=
  match a, b with
  | CreatedCode, CreatedCode => true
  | CreatedCompartment, CreatedCompartment => true
  | CreatedEdgeType, CreatedEdgeType => true
  | CreatedUnboundedQueue, CreatedUnboundedQueue => true
  | _, _ => false
  end.

Lemma creation_eqb_refl : forall a : ForbiddenCreation, creation_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma creation_eqb_true :
  forall a b : ForbiddenCreation, creation_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition origin_eqb (a b : NodeOrigin) : bool :=
  match a, b with
  | BaseImage, BaseImage => true
  | PackageSupplied, PackageSupplied => true
  | _, _ => false
  end.

Lemma origin_eqb_refl : forall a : NodeOrigin, origin_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma origin_eqb_true :
  forall a b : NodeOrigin, origin_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition pool_eqb (a b : Pool) : bool :=
  match a, b with
  | NodePool, NodePool => true
  | RingPool, RingPool => true
  | _, _ => false
  end.

Lemma pool_eqb_refl : forall a : Pool, pool_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma pool_eqb_true : forall a b : Pool, pool_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition class_eqb (a b : FormatClass) : bool :=
  match a, b with
  | ImageFormat, ImageFormat => true
  | MediaFormat, MediaFormat => true
  | FontFormat, FontFormat => true
  | ArchiveFormat, ArchiveFormat => true
  | DocumentFormat, DocumentFormat => true
  | _, _ => false
  end.

Lemma class_eqb_refl : forall a : FormatClass, class_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma class_eqb_true : forall a b : FormatClass, class_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition introduction_eqb (a b : ForbiddenIntroduction) : bool :=
  match a, b with
  | DesktopWireProtocol, DesktopWireProtocol => true
  | OpenEndedIntentString, OpenEndedIntentString => true
  | AuthorityBearingPath, AuthorityBearingPath => true
  | _, _ => false
  end.

Lemma introduction_eqb_refl :
  forall a : ForbiddenIntroduction, introduction_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma introduction_eqb_true :
  forall a b : ForbiddenIntroduction, introduction_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

(* The seven tables read across their own enumerations, so an equality that
   stopped separating two constructors says so here rather than in a theorem
   that happens to quantify over it. *)
Example the_mechanisms_are_pairwise_distinct :
  map_over (mechanism_eqb RuntimeRegistration) all_banned_mechanisms
  = cons true (cons false (cons false (cons false (cons false nil))))
  /\ map_over (mechanism_eqb ContentSniffing) all_banned_mechanisms
  = cons false (cons false (cons false (cons false (cons true nil)))) :=
  conj eq_refl eq_refl.

Example the_quantities_are_pairwise_distinct :
  map_over (quantity_eqb AdmittedWcet) all_admitted_quantities
  = cons true (cons false (cons false (cons false nil)))
  /\ map_over (quantity_eqb AdmittedDeviceReservation) all_admitted_quantities
  = cons false (cons false (cons false (cons true nil))) :=
  conj eq_refl eq_refl.

Example the_creations_are_pairwise_distinct :
  map_over (creation_eqb CreatedCode) all_forbidden_creations
  = cons true (cons false (cons false (cons false nil)))
  /\ map_over (creation_eqb CreatedUnboundedQueue) all_forbidden_creations
  = cons false (cons false (cons false (cons true nil))) :=
  conj eq_refl eq_refl.

Example the_origins_are_distinct :
  map_over (origin_eqb BaseImage) all_node_origins = cons true (cons false nil)
  /\ map_over (origin_eqb PackageSupplied) all_node_origins
  = cons false (cons true nil) := conj eq_refl eq_refl.

Example the_pools_are_distinct :
  map_over (pool_eqb NodePool) all_pools = cons true (cons false nil)
  /\ map_over (pool_eqb RingPool) all_pools = cons false (cons true nil) :=
  conj eq_refl eq_refl.

Example the_format_classes_are_pairwise_distinct :
  map_over (class_eqb ImageFormat) all_format_classes
  = cons true (cons false (cons false (cons false (cons false nil))))
  /\ map_over (class_eqb DocumentFormat) all_format_classes
  = cons false (cons false (cons false (cons false (cons true nil)))) :=
  conj eq_refl eq_refl.

Example the_forbidden_introductions_are_pairwise_distinct :
  map_over (introduction_eqb DesktopWireProtocol) all_forbidden_introductions
  = cons true (cons false (cons false nil))
  /\ map_over (introduction_eqb AuthorityBearingPath) all_forbidden_introductions
  = cons false (cons false (cons true nil)) := conj eq_refl eq_refl.

(* =========================================================================
   The composed object: an edge, a stage, a descriptor, a graph.

   Reading 2: a node is a package on the composed roster and an edge is a
   transformation the declaring package's interface descriptor states. Every
   field below is a quantity R-12-013a or R-12-024b requires a transformation
   to declare, and none is a magnitude this file chooses.
   ========================================================================= *)

Record Edge : Type := {

  (* --- the two endpoints, both nodes of the graph (R-12-024b) ------------- *)

  edge_owner : nat;    (* the package whose descriptor declares it            *)
  edge_target : nat;   (* the node the transformation routes to               *)

  (* --- R-12-013a's declared shape of a transformation --------------------- *)

  edge_intent : nat;   (* the closed variant's index this edge answers        *)
  edge_from : nat;     (* the bounded input type                              *)
  edge_to : nat;       (* the bounded output type                             *)
  edge_limit : nat;    (* the declared resource limit                         *)
  edge_world : nat;    (* the declared interface world                        *)

  (* --- R-12-024f's parsed content format, R-12-024e's declared bounds, and
         R-12-005's bounded ring ---------------------------------------------- *)

  edge_format : nat;   (* the content format the transformation parses        *)
  edge_bounds : nat;   (* the authority the handoff is attenuated to          *)
  edge_ring : nat      (* the declared depth of the ring the edge carries     *)
}.

(* R-12-024c's composition-time template, as an ordered chain. Reading 7: the
   stage set is a field and this is one stage's declared shape. *)
Record Stage : Type := {
  stage_node : nat;    (* the pre-composed node the stage binds              *)
  stage_in : nat;      (* the bounded input type                             *)
  stage_out : nat;     (* the bounded output type                            *)
  stage_ring : nat     (* the declared depth of the ring leaving the stage   *)
}.

(* R-12-024b's interface descriptor, which is the composer's whole input
   beside the roster. *)
Record Descriptor : Type := {
  desc_edges : list Edge;                    (* the declared transformations *)
  desc_manifest : nat;                       (* R-12-024e's manifest width   *)
  desc_origin : NodeOrigin;                  (* R-12-024c's node origin      *)
  desc_admitted_at : NodeOrigin;             (* the time it was admitted at  *)
  desc_admits : AdmittedQuantity -> bool;    (* R-12-024c's four quantities  *)
  desc_label : nat                           (* R-08-021's confidentiality   *)
}.

Record Graph : Type := {
  graph_nodes : list nat;
  graph_edges : list Edge
}.

(* What a composer can observe at the moment it runs, standing for whatever
   an implementation would have to hand (reading 1). Nothing below reads it
   and the obligation is exactly that. *)
Record Ambient : Type := {
  amb_probe : nat;
  amb_clock : nat
}.

(* R-12-013a's intent: a closed variant's index, and beside it the
   caller-supplied name the specification ignores, which is what makes "an
   executable name or command string" refutable at the graph rather than left
   as an absence. Which variants the closed set holds is gap c. *)
Record Intent : Type := {
  int_index : nat;
  int_name : nat
}.

Record Request : Type := {
  req_intent : Intent;
  req_bound : nat;     (* the caller's requested resource bound              *)
  req_run : nat;       (* which run this is, which no selection may read     *)
  req_content : nat    (* the bytes handed over, which no selection sniffs   *)
}.

(* R-08-046's occupancy: the runtime-varying half of a declared bounded pool,
   whose backing storage is static and whose capacity is a field. *)
Record Occupancy : Type := {
  nodes_bound : nat;
  rings_bound : nat
}.

(* =========================================================================
   The machine: everything the register leaves to composition. Fields rather
   than Parameters, because a top-level Parameter prints as an assumption and
   fails the R-05-163 gate.
   ========================================================================= *)

Record Machine : Type := {

  (* --- R-13-001a's roster, over which an install composes a generation ---- *)

  package_count : nat;
  roster : list nat;
  descriptor : nat -> Descriptor;

  (* --- R-13-002's package-supplied code, carried so that executing it is a
         construction rather than an absence (reading 3) ------------------- *)

  script : nat -> list Edge;

  (* --- R-12-013a's type, intent and world spaces, none of which any entry
         enumerates (gap c) ------------------------------------------------ *)

  type_count : nat;
  intent_count : nat;
  world_count : nat;

  (* --- R-05-042's wire-format inventory, its per-format verified-parser
         flag, and R-12-024f's five format classes read over the same
         inventory. Which formats an inventory carries is a composition
         (gap j); that each of the five classes is on the same terms is
         not, and O20 states it ------------------------------------------- *)

  in_inventory : nat -> bool;
  verified_parser : nat -> bool;
  format_class : nat -> FormatClass;

  (* --- R-08-046's two declared bounded pools and R-12-005's ring depth --- *)

  node_pool_capacity : nat;
  ring_pool_capacity : nat;
  ring_depth_ceiling : nat;

  (* --- R-12-024c's composition-time template and its declared end types -- *)

  template_stages : list Stage;
  template_in : nat;
  template_out : nat;

  (* --- R-08-021's declared inter-level channels, read off the composed
         graph rather than configured -------------------------------------- *)

  channel : nat -> nat -> bool;

  (* --- the two the register leaves undecided, carried as fields so that
         nothing below decides them by fiat (gaps b and f) ------------------ *)

  ambiguity_admitted : bool;
  graph_identity : nat
}.

(* The machine with one package's script replaced, which is the substitution
   R-13-002's obligation quantifies over (reading 3). Every other field is
   carried across unchanged, so a composer that answers differently under it
   answered by running the script. *)
Definition with_script (m : Machine) (s : nat -> list Edge) : Machine := {|
  package_count := m.(package_count);
  roster := m.(roster);
  descriptor := m.(descriptor);
  script := s;
  type_count := m.(type_count);
  intent_count := m.(intent_count);
  world_count := m.(world_count);
  in_inventory := m.(in_inventory);
  verified_parser := m.(verified_parser);
  format_class := m.(format_class);
  node_pool_capacity := m.(node_pool_capacity);
  ring_pool_capacity := m.(ring_pool_capacity);
  ring_depth_ceiling := m.(ring_depth_ceiling);
  template_stages := m.(template_stages);
  template_in := m.(template_in);
  template_out := m.(template_out);
  channel := m.(channel);
  ambiguity_admitted := m.(ambiguity_admitted);
  graph_identity := m.(graph_identity)
|}.

Lemma with_script_changes_nothing_else :
  forall (m : Machine) (s : nat -> list Edge),
    (with_script m s).(descriptor) = m.(descriptor)
    /\ (with_script m s).(roster) = m.(roster)
    /\ (with_script m s).(script) = s.
Proof. intros m s. split; [ reflexivity | split; reflexivity ]. Qed.

(* =========================================================================
   What makes an edge admissible: twelve conjuncts, held as a list rather
   than as a nest of conjunctions (reading 4). The comment at each names the
   entry that owns it. A composer that drops one is `compose_without` at that
   index and an edge that breaks one is `spoiled_at` at that index, so the
   twelve are decided from both sides and neither family is authored.
   ========================================================================= *)

Definition edge_conjuncts (m : Machine) (r : list nat) : list (Edge -> bool) :=
  (* 0, 1: R-12-024b's finite closed graph. Both endpoints are nodes, and the
     node set is the composed roster and nothing else. Gap d is what conjunct
     1 refuses: the shared service compartment R-13-010b's duplication pass
     emits is a compartment and no package the roster names. *)
  cons (fun e => mem_nat e.(edge_owner) r)
  (cons (fun e => mem_nat e.(edge_target) r)
  (* 2: R-12-013a's declared resource limit. A transformation declaring none
     declares nothing the caller's bound can be compared against. *)
  (cons (fun e => Nat.ltb 0 e.(edge_limit))
  (* 3: R-12-013a's closed intent variant, as an index below the count the
     composition fixes (gap c). *)
  (cons (fun e => Nat.ltb e.(edge_intent) m.(intent_count))
  (* 4, 5: R-12-013a's bounded input and output types. *)
  (cons (fun e => Nat.ltb e.(edge_from) m.(type_count))
  (cons (fun e => Nat.ltb e.(edge_to) m.(type_count))
  (* 6: R-12-013a's declared interface world. *)
  (cons (fun e => Nat.ltb e.(edge_world) m.(world_count))
  (* 7, 8: R-12-024f with R-05-042. Every content format the transformation
     parses is enumerated in the wire-format inventory and carries a Narcissus
     copy-once verified parser. Two conjuncts because the entry states two
     things and a format can be on the inventory with no parser beside it. *)
  (cons (fun e => m.(in_inventory) e.(edge_format))
  (cons (fun e => m.(verified_parser) e.(edge_format))
  (* 9: R-12-024e's composition-side half. The handoff is attenuated to the
     selected edge's declared bounds, so a composer may not declare bounds
     wider than the declaring package's own manifest. *)
  (cons (fun e => Nat.leb e.(edge_bounds)
                          (m.(descriptor) e.(edge_owner)).(desc_manifest))
  (* 10, 11: R-12-005 with R-12-024c's bounded-ring pools, at composition
     (reading 8). A declared depth of zero is a ring that carries nothing and
     one past the ceiling is a ring the composition did not size. *)
  (cons (fun e => Nat.ltb 0 e.(edge_ring))
  (cons (fun e => Nat.leb e.(edge_ring) m.(ring_depth_ceiling))
   nil))))))))))).

Definition admissible_edge (m : Machine) (r : list nat) (e : Edge) : bool :=
  all_of (fun p => p e) (edge_conjuncts m r).

(* How many of the twelve an edge breaks: the measure that makes "this
   weakening broke exactly one conjunct" a computation rather than a claim. *)
Definition conjuncts_broken (m : Machine) (r : list nat) (e : Edge) : nat :=
  count_of (filter_of (fun p => negb (p e)) (edge_conjuncts m r)).

Example there_are_twelve_conjuncts :
  forall (m : Machine) (r : list nat), count_of (edge_conjuncts m r) = 12.
Proof. intros m r. reflexivity. Qed.

(* The conjuncts every closure and attenuation theorem below reads back out
   of the conjunction, one small lemma each rather than a `simpl` inside each
   theorem. *)
Lemma admissible_owner_on_roster :
  forall (m : Machine) (r : list nat) (e : Edge),
    admissible_edge m r e = true -> mem_nat e.(edge_owner) r = true.
Proof.
  intros m r e H. unfold admissible_edge, edge_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ H0 _ ]. exact H0.
Qed.

Lemma admissible_target_on_roster :
  forall (m : Machine) (r : list nat) (e : Edge),
    admissible_edge m r e = true -> mem_nat e.(edge_target) r = true.
Proof.
  intros m r e H. unfold admissible_edge, edge_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ H2 _ ]. exact H2.
Qed.

Lemma admissible_declares_a_limit :
  forall (m : Machine) (r : list nat) (e : Edge),
    admissible_edge m r e = true -> Nat.ltb 0 e.(edge_limit) = true.
Proof.
  intros m r e H. unfold admissible_edge, edge_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ H3 _ ]. exact H3.
Qed.

Lemma admissible_world_is_declared :
  forall (m : Machine) (r : list nat) (e : Edge),
    admissible_edge m r e = true ->
    Nat.ltb e.(edge_world) m.(world_count) = true.
Proof.
  intros m r e H. unfold admissible_edge, edge_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ _ H4 ].
  destruct (andb_split _ _ H4) as [ _ H5 ].
  destruct (andb_split _ _ H5) as [ _ H6 ].
  destruct (andb_split _ _ H6) as [ H7 _ ]. exact H7.
Qed.

Lemma admissible_format_is_inventoried :
  forall (m : Machine) (r : list nat) (e : Edge),
    admissible_edge m r e = true -> m.(in_inventory) e.(edge_format) = true.
Proof.
  intros m r e H. unfold admissible_edge, edge_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ _ H4 ].
  destruct (andb_split _ _ H4) as [ _ H5 ].
  destruct (andb_split _ _ H5) as [ _ H6 ].
  destruct (andb_split _ _ H6) as [ _ H7 ].
  destruct (andb_split _ _ H7) as [ H8 _ ]. exact H8.
Qed.

Lemma admissible_format_has_a_verified_parser :
  forall (m : Machine) (r : list nat) (e : Edge),
    admissible_edge m r e = true -> m.(verified_parser) e.(edge_format) = true.
Proof.
  intros m r e H. unfold admissible_edge, edge_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ _ H4 ].
  destruct (andb_split _ _ H4) as [ _ H5 ].
  destruct (andb_split _ _ H5) as [ _ H6 ].
  destruct (andb_split _ _ H6) as [ _ H7 ].
  destruct (andb_split _ _ H7) as [ _ H8 ].
  destruct (andb_split _ _ H8) as [ H9 _ ]. exact H9.
Qed.

Lemma admissible_bounds_inside_the_manifest :
  forall (m : Machine) (r : list nat) (e : Edge),
    admissible_edge m r e = true ->
    Nat.leb e.(edge_bounds) (m.(descriptor) e.(edge_owner)).(desc_manifest) = true.
Proof.
  intros m r e H. unfold admissible_edge, edge_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ _ H4 ].
  destruct (andb_split _ _ H4) as [ _ H5 ].
  destruct (andb_split _ _ H5) as [ _ H6 ].
  destruct (andb_split _ _ H6) as [ _ H7 ].
  destruct (andb_split _ _ H7) as [ _ H8 ].
  destruct (andb_split _ _ H8) as [ _ H9 ].
  destruct (andb_split _ _ H9) as [ H10 _ ]. exact H10.
Qed.

Lemma admissible_ring_is_inside_the_ceiling :
  forall (m : Machine) (r : list nat) (e : Edge),
    admissible_edge m r e = true ->
    Nat.leb e.(edge_ring) m.(ring_depth_ceiling) = true.
Proof.
  intros m r e H. unfold admissible_edge, edge_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ _ H4 ].
  destruct (andb_split _ _ H4) as [ _ H5 ].
  destruct (andb_split _ _ H5) as [ _ H6 ].
  destruct (andb_split _ _ H6) as [ _ H7 ].
  destruct (andb_split _ _ H7) as [ _ H8 ].
  destruct (andb_split _ _ H8) as [ _ H9 ].
  destruct (andb_split _ _ H9) as [ _ H10 ].
  destruct (andb_split _ _ H10) as [ _ H11 ].
  destruct (andb_split _ _ H11) as [ H12 _ ]. exact H12.
Qed.

(* =========================================================================
   The composer (R-12-024b, R-13-002).

   O1: the emitted graph is a function of the descriptors and the roster
   alone, and does not vary with what the composition observes.
   O2: it is unchanged when every package's script is replaced.
   O3: it is finite and closed.
   ========================================================================= *)

Definition Composer : Type := Machine -> Ambient -> list nat -> Graph.

(* Every edge every package on the roster declares, in roster order. *)
Definition declared_edges (m : Machine) (r : list nat) : list Edge :=
  concat_of (map_over (fun p => (m.(descriptor) p).(desc_edges)) r).

(* What a script would produce if the installation path ran one, which
   R-13-002 says it does not. *)
Definition scripted_edges (m : Machine) (r : list nat) : list Edge :=
  concat_of (map_over m.(script) r).

Definition spec_compose : Composer := fun m _ r => {|
  graph_nodes := r;
  graph_edges := filter_of (admissible_edge m r) (declared_edges m r)
|}.

(* O1 (R-12-024b). Stated of an arbitrary composer over two arbitrary
   ambients: this is AdmissionPath.v's reading 1 at a different subject, that
   file's ambient being the checker's and this one's the composer's. *)
Definition ComposesFromDescriptorsAlone (c : Composer) : Prop :=
  forall (m : Machine) (a1 a2 : Ambient) (r : list nat), c m a1 r = c m a2 r.

Theorem the_specification_composes_from_descriptors_alone :
  ComposesFromDescriptorsAlone spec_compose.
Proof. intros m a1 a2 r. reflexivity. Qed.

(* O2 (R-13-002). The installation path executes no package-supplied code,
   stated as: the emitted graph is unchanged under an arbitrary replacement
   of every package's script (reading 3). *)
Definition ExecutesNoPackageCode (c : Composer) : Prop :=
  forall (m : Machine) (s : nat -> list Edge) (a : Ambient) (r : list nat),
    c (with_script m s) a r = c m a r.

Theorem the_specification_executes_no_package_code :
  ExecutesNoPackageCode spec_compose.
Proof. intros m s a r. reflexivity. Qed.

(* O3 (R-12-024b). Finite and closed: every edge's two endpoints are nodes of
   the graph, and every node is a package the composed roster names. Stated
   over the emitted lists rather than over a membership relation, so no
   decidable equality on edges is owed. *)
Definition endpoints_inside (g : Graph) : bool :=
  all_of (fun e => andb (mem_nat e.(edge_owner) g.(graph_nodes))
                        (mem_nat e.(edge_target) g.(graph_nodes)))
         g.(graph_edges).

Definition IsFiniteAndClosed (r : list nat) (g : Graph) : Prop :=
  endpoints_inside g = true
  /\ all_of (fun n => mem_nat n r) g.(graph_nodes) = true.

Theorem the_specification_emits_a_finite_closed_graph :
  forall (m : Machine) (a : Ambient) (r : list nat),
    IsFiniteAndClosed r (spec_compose m a r).
Proof.
  intros m a r. split.
  - unfold endpoints_inside. simpl.
    apply (all_of_mono Edge (admissible_edge m r)
             (fun e => andb (mem_nat e.(edge_owner) r) (mem_nat e.(edge_target) r))).
    + intros e He. apply andb_join.
      * exact (admissible_owner_on_roster m r e He).
      * exact (admissible_target_on_roster m r e He).
    + exact (all_of_filter_self Edge (admissible_edge m r) (declared_edges m r)).
  - simpl. exact (all_of_mem_self r).
Qed.

(* The specification's own graph is admissible edge by edge, which is what the
   selection obligations below are stated against. *)
Theorem the_specification_emits_admissible_edges_only :
  forall (m : Machine) (a : Ambient) (r : list nat),
    all_of (admissible_edge m r) (spec_compose m a r).(graph_edges) = true.
Proof.
  intros m a r. simpl.
  exact (all_of_filter_self Edge (admissible_edge m r) (declared_edges m r)).
Qed.

(* O9a (R-12-013a), O10 (R-12-024e), O16 (R-12-024f, R-05-042) and O18
   (R-12-005) read off the same emitted list, each as the conjunct its entry
   owns. They are separate theorems because each is refuted by a separate
   composer below. *)
Theorem every_composed_edge_declares_a_resource_limit :
  forall (m : Machine) (a : Ambient) (r : list nat),
    all_of (fun e => Nat.ltb 0 e.(edge_limit)) (spec_compose m a r).(graph_edges)
    = true.
Proof.
  intros m a r. simpl.
  apply (all_of_mono Edge (admissible_edge m r)).
  - intros e He. exact (admissible_declares_a_limit m r e He).
  - exact (all_of_filter_self Edge (admissible_edge m r) (declared_edges m r)).
Qed.

Theorem every_composed_edge_declares_an_interface_world :
  forall (m : Machine) (a : Ambient) (r : list nat),
    all_of (fun e => Nat.ltb e.(edge_world) m.(world_count))
           (spec_compose m a r).(graph_edges) = true.
Proof.
  intros m a r. simpl.
  apply (all_of_mono Edge (admissible_edge m r)).
  - intros e He. exact (admissible_world_is_declared m r e He).
  - exact (all_of_filter_self Edge (admissible_edge m r) (declared_edges m r)).
Qed.

Theorem the_specification_never_widens_a_manifest :
  forall (m : Machine) (a : Ambient) (r : list nat),
    all_of (fun e => Nat.leb e.(edge_bounds)
                              (m.(descriptor) e.(edge_owner)).(desc_manifest))
           (spec_compose m a r).(graph_edges) = true.
Proof.
  intros m a r. simpl.
  apply (all_of_mono Edge (admissible_edge m r)).
  - intros e He. exact (admissible_bounds_inside_the_manifest m r e He).
  - exact (all_of_filter_self Edge (admissible_edge m r) (declared_edges m r)).
Qed.

Theorem every_parsed_format_is_inventoried_and_verified :
  forall (m : Machine) (a : Ambient) (r : list nat),
    all_of (fun e => m.(in_inventory) e.(edge_format))
           (spec_compose m a r).(graph_edges) = true
    /\ all_of (fun e => m.(verified_parser) e.(edge_format))
              (spec_compose m a r).(graph_edges) = true.
Proof.
  intros m a r. split; simpl.
  - apply (all_of_mono Edge (admissible_edge m r)).
    + intros e He. exact (admissible_format_is_inventoried m r e He).
    + exact (all_of_filter_self Edge (admissible_edge m r) (declared_edges m r)).
  - apply (all_of_mono Edge (admissible_edge m r)).
    + intros e He. exact (admissible_format_has_a_verified_parser m r e He).
    + exact (all_of_filter_self Edge (admissible_edge m r) (declared_edges m r)).
Qed.

Theorem every_composed_ring_is_inside_the_ceiling :
  forall (m : Machine) (a : Ambient) (r : list nat),
    all_of (fun e => Nat.leb e.(edge_ring) m.(ring_depth_ceiling))
           (spec_compose m a r).(graph_edges) = true.
Proof.
  intros m a r. simpl.
  apply (all_of_mono Edge (admissible_edge m r)).
  - intros e He. exact (admissible_ring_is_inside_the_ceiling m r e He).
  - exact (all_of_filter_self Edge (admissible_edge m r) (declared_edges m r)).
Qed.

(* O20 (R-12-024f's acceptance clause): the five format classes are admitted
   on the same terms, so no class is exempt from the inventory or from the
   verified parser. Quantified over the closed enumeration rather than stated
   once, which is what makes the enumeration load-bearing: drop a constructor
   and an obligation goes with it. The class of a format is a field, because
   which formats an inventory carries is a composition; that none of the five
   is exempt is not. *)
Definition ExemptsNoFormatClass (c : Composer) : Prop :=
  forall (m : Machine) (a : Ambient) (r : list nat) (k : FormatClass),
    all_of (fun e => orb (negb (class_eqb (m.(format_class) e.(edge_format)) k))
                         (andb (m.(in_inventory) e.(edge_format))
                               (m.(verified_parser) e.(edge_format))))
           (c m a r).(graph_edges) = true.

Theorem the_specification_exempts_no_format_class :
  ExemptsNoFormatClass spec_compose.
Proof.
  intros m a r k. simpl.
  apply (all_of_mono Edge (admissible_edge m r)).
  - intros e He.
    rewrite (admissible_format_is_inventoried m r e He).
    rewrite (admissible_format_has_a_verified_parser m r e He).
    destruct (class_eqb (m.(format_class) e.(edge_format)) k); reflexivity.
  - exact (all_of_filter_self Edge (admissible_edge m r) (declared_edges m r)).
Qed.

(* =========================================================================
   The refuting composers (R-05-166).

   `compose_without k` is the specification with conjunct k dropped from its
   own filter: one construction per conjunct, generated over the index rather
   than authored, and each is named below at the entry whose clause it
   breaks. The discovering and executing composers are the two no index
   generates, being alternative constructions rather than a weakened filter.
   ========================================================================= *)

Definition compose_without (k : nat) : Composer := fun m _ r => {|
  graph_nodes := r;
  graph_edges :=
    filter_of (fun e => all_of (fun p => p e) (drop_at k (edge_conjuncts m r)))
              (declared_edges m r)
|}.

(* The named members of that family, one per obligation the register states
   separately. Each is `compose_without` at the index its entry owns, so the
   name is a citation and not a second construction. *)
Definition trusting_compose : Composer := compose_without 1.
Definition limitless_compose : Composer := compose_without 2.
Definition worldless_compose : Composer := compose_without 6.
Definition widening_compose : Composer := compose_without 9.
Definition uninventoried_compose : Composer := compose_without 7.
Definition unverified_compose : Composer := compose_without 8.
Definition ringless_compose : Composer := compose_without 10.
Definition deep_ring_compose : Composer := compose_without 11.

(* O20's refuters, one per class, generated over the closed enumeration
   rather than authored: the two format conjuncts are dropped for edges whose
   format is of the named class and kept for every other edge, which is
   exactly the "on the same terms" clause failing at one family. Conjuncts 0
   and 1 survive the drop, so each of the five still emits a closed graph and
   what refutes it is the exemption. *)
Definition admits_class_exempt (m : Machine) (r : list nat) (k : FormatClass)
                               (e : Edge) : bool :=
  if class_eqb (m.(format_class) e.(edge_format)) k
  then all_of (fun p => p e) (drop_at 7 (drop_at 8 (edge_conjuncts m r)))
  else admissible_edge m r e.

Definition exempting_compose (k : FormatClass) : Composer := fun m _ r => {|
  graph_nodes := r;
  graph_edges := filter_of (admits_class_exempt m r k) (declared_edges m r)
|}.

(* The family as a list, with the specification's own filter as the fallback
   past the last class (reading 9): a bound raised by one reaches a predicate
   that refuses the exempted edge, so the theorem below fails rather than
   holding vacuously wider. *)
Definition all_class_exemptions (m : Machine) (r : list nat)
  : list (Edge -> bool) :=
  map_over (admits_class_exempt m r) all_format_classes.

Definition exemption_at (m : Machine) (r : list nat) (n : nat) : Edge -> bool :=
  at_member (all_class_exemptions m r) n (admissible_edge m r).

Example the_class_exemptions_are_five :
  forall (m : Machine) (r : list nat),
    count_of (all_class_exemptions m r) = 5.
Proof. intros m r. reflexivity. Qed.

Lemma class_exempt_owner_on_roster :
  forall (m : Machine) (r : list nat) (k : FormatClass) (e : Edge),
    admits_class_exempt m r k e = true -> mem_nat e.(edge_owner) r = true.
Proof.
  intros m r k e H. unfold admits_class_exempt in H.
  destruct (class_eqb (m.(format_class) e.(edge_format)) k).
  - unfold edge_conjuncts in H. simpl in H.
    destruct (andb_split _ _ H) as [ H0 _ ]. exact H0.
  - exact (admissible_owner_on_roster m r e H).
Qed.

Lemma class_exempt_target_on_roster :
  forall (m : Machine) (r : list nat) (k : FormatClass) (e : Edge),
    admits_class_exempt m r k e = true -> mem_nat e.(edge_target) r = true.
Proof.
  intros m r k e H. unfold admits_class_exempt in H.
  destruct (class_eqb (m.(format_class) e.(edge_format)) k).
  - unfold edge_conjuncts in H. simpl in H.
    destruct (andb_split _ _ H) as [ _ H1 ].
    destruct (andb_split _ _ H1) as [ H2 _ ]. exact H2.
  - exact (admissible_target_on_roster m r e H).
Qed.

Theorem every_exempting_composer_still_emits_a_closed_graph :
  forall (k : FormatClass) (m : Machine) (a : Ambient) (r : list nat),
    IsFiniteAndClosed r (exempting_compose k m a r).
Proof.
  intros k m a r. split.
  - unfold endpoints_inside. simpl.
    apply (all_of_mono Edge (admits_class_exempt m r k)
             (fun e => andb (mem_nat e.(edge_owner) r) (mem_nat e.(edge_target) r))).
    + intros e He. apply andb_join.
      * exact (class_exempt_owner_on_roster m r k e He).
      * exact (class_exempt_target_on_roster m r k e He).
    + exact (all_of_filter_self Edge (admits_class_exempt m r k)
               (declared_edges m r)).
  - simpl. exact (all_of_mem_self r).
Qed.

(* A composer that reads what it observed: under a probe it emits the empty
   graph, which R-12-024b's compilation from interface descriptors excludes.
   It still emits a finite closed typed graph, so what refutes it is the
   observation and not the object. *)
Definition discovering_compose : Composer := fun m a r =>
  if Nat.ltb 0 a.(amb_probe)
  then {| graph_nodes := r; graph_edges := nil |}
  else spec_compose m a r.

(* A composer that runs what the packages supplied: it appends the edges each
   script produced, admitting them on the same terms as the declared ones, so
   what refutes it is R-13-002's own clause and not a malformed edge. It still
   emits a finite closed typed graph. *)
Definition executing_compose : Composer := fun m a r => {|
  graph_nodes := r;
  graph_edges :=
    app (filter_of (admissible_edge m r) (declared_edges m r))
        (filter_of (admissible_edge m r) (scripted_edges m r))
|}.

(* Both alternative composers keep the two obligations they are not aimed at
   as well as the closure obligation, each stated of an arbitrary machine and
   roster rather than computed on the demo, so what refutes each below is the
   named defect and not the shape of the construction. Three theorems apiece
   rather than one: a composer shown only to be closed could also be reading
   the ambient or running the script, and then the refutation below would not
   isolate anything. *)
Theorem the_discovering_composer_still_emits_a_closed_graph :
  forall (m : Machine) (a : Ambient) (r : list nat),
    IsFiniteAndClosed r (discovering_compose m a r).
Proof.
  intros m a r. unfold discovering_compose.
  destruct (Nat.ltb 0 a.(amb_probe)).
  - split; [ reflexivity | simpl; exact (all_of_mem_self r) ].
  - exact (the_specification_emits_a_finite_closed_graph m a r).
Qed.

Theorem the_executing_composer_still_emits_a_closed_graph :
  forall (m : Machine) (a : Ambient) (r : list nat),
    IsFiniteAndClosed r (executing_compose m a r).
Proof.
  intros m a r. split.
  - unfold endpoints_inside. simpl.
    apply all_of_app_join;
      (apply (all_of_mono Edge (admissible_edge m r));
       [ intros e He; apply andb_join;
         [ exact (admissible_owner_on_roster m r e He)
         | exact (admissible_target_on_roster m r e He) ]
       | apply all_of_filter_self ]).
  - simpl. exact (all_of_mem_self r).
Qed.

(* The discovering composer runs no package code: its two arms are the empty
   graph and the specification's own, and neither reads the script. So what
   refutes it is the ambient alone. *)
Theorem the_discovering_composer_executes_no_package_code :
  ExecutesNoPackageCode discovering_compose.
Proof.
  intros m s a r. unfold discovering_compose.
  destruct (Nat.ltb 0 a.(amb_probe)); reflexivity.
Qed.

(* And the executing composer composes from the descriptors alone: it ignores
   the ambient exactly as the specification does, so what refutes it is the
   script alone. *)
Theorem the_executing_composer_composes_from_descriptors_alone :
  ComposesFromDescriptorsAlone executing_compose.
Proof. intros m a1 a2 r. reflexivity. Qed.

(* And the discovering composer agrees with the specification wherever it
   observes nothing, so what refutes it is the runtime dependence rather than
   a different graph. *)
Theorem the_discovering_composer_agrees_where_it_observes_nothing :
  forall (m : Machine) (r : list nat) (c : nat),
    discovering_compose m {| amb_probe := 0; amb_clock := c |} r
    = spec_compose m {| amb_probe := 0; amb_clock := c |} r.
Proof. intros m r c. reflexivity. Qed.

(* =========================================================================
   O4: the graph is never amended in a running one, and the five mechanisms
   R-12-024b names are not routes into it.

   An amendment is a function from a graph to a graph, so the obligation is
   that the only admitted one is the identity. Five amenders are generated
   over the closed enumeration, one per mechanism, each adding an edge at run
   time by its own route; each keeps finiteness and typedness, so what
   refuses it is the named defect and not its shape.
   ========================================================================= *)

Definition Amender : Type := Graph -> Graph.

Definition no_amendment : Amender := fun g => g.

Definition NeverAmendsARunningGraph (f : Amender) : Prop :=
  forall g : Graph, f g = g.

Theorem the_specification_never_amends_a_running_graph :
  NeverAmendsARunningGraph no_amendment.
Proof. intros g. reflexivity. Qed.

(* The edge each mechanism would add. Its fields are the ones the route
   itself fixes: the mechanism's index stands in the intent, so the five
   edges are five different edges and not one edge added five ways. *)
Definition mechanism_index (b : BannedMechanism) : nat :=
  match b with
  | RuntimeRegistration => 0
  | ExecutableLookup => 1
  | ShellCommand => 2
  | PluginLoad => 3
  | ContentSniffing => 4
  end.

Definition runtime_edge (b : BannedMechanism) : Edge := {|
  edge_owner := mechanism_index b;
  edge_target := mechanism_index b;
  edge_intent := mechanism_index b;
  edge_from := 0;
  edge_to := 0;
  edge_limit := 1;
  edge_world := 0;
  edge_format := 0;
  edge_bounds := 0;
  edge_ring := 1
|}.

Definition amend_by (b : BannedMechanism) : Amender := fun g => {|
  graph_nodes := g.(graph_nodes);
  graph_edges := cons (runtime_edge b) g.(graph_edges)
|}.

(* The whole family, with the specification's own non-amendment as the
   fallback past the last index (reading 9). *)
Definition all_amenders : list Amender :=
  map_over amend_by all_banned_mechanisms.

Definition amender_at (n : nat) : Amender := at_member all_amenders n no_amendment.

(* Whether an amendment moved the graph, as a computation: the edge count of
   the amended graph against the edge count of the graph it was handed. *)
Definition amends (f : Amender) (g : Graph) : bool :=
  negb (Nat.eqb (count_of (f g).(graph_edges)) (count_of g.(graph_edges))).

Theorem no_amender_leaves_the_graph_unamended :
  forall b : BannedMechanism, ~ NeverAmendsARunningGraph (amend_by b).
Proof.
  intros b H. specialize (H {| graph_nodes := nil; graph_edges := nil |}).
  apply (f_equal (fun g => count_of g.(graph_edges))) in H. discriminate H.
Qed.

(* Every amendment keeps the node set, so a graph amended by any of the five
   is still closed over the roster it was composed for: what refuses it is
   R-12-024b's "never amended in a running one" and not a stranger node. *)
Theorem every_amendment_keeps_the_node_set :
  forall (f : Amender) (g : Graph),
    (exists b : BannedMechanism, f = amend_by b) ->
    (f g).(graph_nodes) = g.(graph_nodes).
Proof. intros f g [ b Hb ]. rewrite Hb. reflexivity. Qed.

(* =========================================================================
   O5: an install rebuilds and re-signs rather than amends (R-12-024b with
   R-13-001a), and uninstalling is the same operation over a roster with the
   package removed rather than a distinct teardown path.
   ========================================================================= *)

Definition Installer : Type := Machine -> list nat -> nat -> Graph.

Definition after_install (r : list nat) (p : nat) : list nat := cons p r.
Definition after_uninstall (r : list nat) (p : nat) : list nat := remove_nat p r.

(* The ambient a recomposition runs under, named once rather than written out
   at each of the three sites that need one: obligation 1 is that no composer
   reads it, so writing a fresh one per site would put three figures in the
   file that nothing reads. The ledger pins its two fields. *)
Definition composition_ambient : Ambient := {| amb_probe := 0; amb_clock := 0 |}.

Definition spec_install : Installer := fun m r p =>
  spec_compose m composition_ambient (after_install r p).

Definition spec_uninstall : Installer := fun m r p =>
  spec_compose m composition_ambient (after_uninstall r p).

(* R-13-001a: the act is a recomposition over the resulting roster, whichever
   act it is, which is what makes uninstall the same operation rather than a
   teardown path of its own. Stated of an arbitrary installer against an
   arbitrary roster function. *)
Definition IsRecomposition
  (ins : Installer) (after : list nat -> nat -> list nat) : Prop :=
  forall (m : Machine) (r : list nat) (p : nat),
    ins m r p = spec_compose m composition_ambient (after r p).

Theorem the_specification_install_is_a_recomposition :
  IsRecomposition spec_install after_install.
Proof. intros m r p. reflexivity. Qed.

Theorem the_specification_uninstall_is_a_recomposition :
  IsRecomposition spec_uninstall after_uninstall.
Proof. intros m r p. reflexivity. Qed.

(* The amending installer: it keeps the graph it had and appends only the
   edges the arriving package declares, admitted against the new roster. It
   misses every edge an installed package already declared whose target the
   arriving package is, which is the difference R-13-001a's "not an amendment
   to one" names. *)
Definition amending_install : Installer := fun m r p => {|
  graph_nodes := after_install r p;
  graph_edges :=
    app (filter_of (admissible_edge m r) (declared_edges m r))
        (filter_of (admissible_edge m (after_install r p))
                   ((m.(descriptor) p).(desc_edges)))
|}.

(* The amending uninstaller: it deletes the departing package's own edges and
   leaves the rest, so an edge whose target it was survives into a graph
   whose roster no longer carries that node. *)
Definition amending_uninstall : Installer := fun m r p => {|
  graph_nodes := after_uninstall r p;
  graph_edges :=
    filter_of (fun e => negb (Nat.eqb e.(edge_owner) p))
              (filter_of (admissible_edge m r) (declared_edges m r))
|}.

(* How many edges of a graph route into one node: the measure that makes the
   uninstall difference observable rather than argued. This is
   SupervisionTree.v's `the_regrant_extent_is_observable` method at a
   different subject. *)
Definition edges_into (g : Graph) (p : nat) : nat :=
  count_of (filter_of (fun e => Nat.eqb e.(edge_target) p) g.(graph_edges)).

(* =========================================================================
   O6, O7, O8, O9a, O9b and O9c: deterministic typed routing over a finite
   closed graph under the caller's requested intent and resource bound
   (R-12-024b with R-12-013a), and an intent naming no admitted edge failing
   closed. There is no bare O9: the ninth obligation is three, the intent the
   selection answers, the bound it respects, and the graph it may not leave,
   and each is refuted by a different selector.

   Reading 5 puts the comparison of the edge's declared limit against the
   caller's bound at selection; gap h records that the register does not
   choose the side.
   ========================================================================= *)

Definition Selector : Type := Graph -> Request -> option Edge.

(* The two things a selection is a function of, and nothing else: the closed
   variant's index and the requested bound. *)
Definition matches (q : Request) (e : Edge) : bool :=
  andb (Nat.eqb e.(edge_intent) q.(req_intent).(int_index))
       (Nat.leb e.(edge_limit) q.(req_bound)).

Definition spec_select : Selector :=
  fun g q => find_of (matches q) g.(graph_edges).

(* The same request with one field moved, so that each independence
   obligation quantifies over exactly the field its entry names. *)
Definition with_run (q : Request) (n : nat) : Request := {|
  req_intent := q.(req_intent);
  req_bound := q.(req_bound);
  req_run := n;
  req_content := q.(req_content)
|}.

Definition with_name (q : Request) (n : nat) : Request := {|
  req_intent := {| int_index := q.(req_intent).(int_index); int_name := n |};
  req_bound := q.(req_bound);
  req_run := q.(req_run);
  req_content := q.(req_content)
|}.

Definition with_bound (q : Request) (b : nat) : Request := {|
  req_intent := q.(req_intent);
  req_bound := b;
  req_run := q.(req_run);
  req_content := q.(req_content)
|}.

Definition with_content (q : Request) (n : nat) : Request := {|
  req_intent := q.(req_intent);
  req_bound := q.(req_bound);
  req_run := q.(req_run);
  req_content := n
|}.

(* O6 (R-12-024b's "deterministic typed routing"): the selection does not
   vary with which run it is. *)
Definition DoesNotVaryWithTheRun (sel : Selector) : Prop :=
  forall (g : Graph) (q : Request) (n1 n2 : nat),
    sel g (with_run q n1) = sel g (with_run q n2).

(* O7 (R-12-013a, and R-12-024b's "no executable lookup"): two intents
   agreeing on the closed variant's index route identically, so a
   caller-supplied name is not a handler name. *)
Definition DoesNotReadTheName (sel : Selector) : Prop :=
  forall (g : Graph) (q : Request) (n1 n2 : nat),
    sel g (with_name q n1) = sel g (with_name q n2).

(* O8's second half read at the selection side (R-12-024b's "no content
   sniffing"): the bytes the caller handed over do not select an edge. This
   is the fifth banned mechanism met here rather than at the amendment, and
   the two meet at exactly this construction. *)
Definition DoesNotSniffTheContent (sel : Selector) : Prop :=
  forall (g : Graph) (q : Request) (n1 n2 : nat),
    sel g (with_content q n1) = sel g (with_content q n2).

Theorem the_specification_selection_does_not_vary_with_the_run :
  DoesNotVaryWithTheRun spec_select.
Proof. intros g q n1 n2. reflexivity. Qed.

Theorem the_specification_selection_does_not_read_the_name :
  DoesNotReadTheName spec_select.
Proof. intros g q n1 n2. reflexivity. Qed.

Theorem the_specification_selection_does_not_sniff_the_content :
  DoesNotSniffTheContent spec_select.
Proof. intros g q n1 n2. reflexivity. Qed.

(* O9b (R-12-013a's declared resource limits, read at selection): the
   selected edge's declared limit is inside the caller's requested bound. *)
Definition RespectsTheRequestedBound (sel : Selector) : Prop :=
  forall (g : Graph) (q : Request) (e : Edge),
    sel g q = Some e -> Nat.leb e.(edge_limit) q.(req_bound) = true.

Theorem the_specification_respects_the_requested_bound :
  RespectsTheRequestedBound spec_select.
Proof.
  intros g q e H.
  assert (Hm : matches q e = true) by
    exact (find_of_holds Edge (matches q) g.(graph_edges) e H).
  unfold matches in Hm. destruct (andb_split _ _ Hm) as [ _ Hb ]. exact Hb.
Qed.

(* And the selected edge answers the intent the caller named, which is the
   other half of `matches` and is what makes the routing typed rather than
   merely bounded. *)
Definition AnswersTheRequestedIntent (sel : Selector) : Prop :=
  forall (g : Graph) (q : Request) (e : Edge),
    sel g q = Some e ->
    Nat.eqb e.(edge_intent) q.(req_intent).(int_index) = true.

Theorem the_specification_answers_the_requested_intent :
  AnswersTheRequestedIntent spec_select.
Proof.
  intros g q e H.
  assert (Hm : matches q e = true) by
    exact (find_of_holds Edge (matches q) g.(graph_edges) e H).
  unfold matches in Hm. destruct (andb_split _ _ Hm) as [ Hi _ ]. exact Hi.
Qed.

(* O9c (R-12-024b): a selection returns only an edge the graph carries, so
   raising the requested bound admits no edge the composition did not emit. *)
Definition ReturnsOnlyAdmittedEdges (m : Machine) (r : list nat)
                                    (sel : Selector) : Prop :=
  forall (g : Graph) (q : Request) (e : Edge),
    all_of (admissible_edge m r) g.(graph_edges) = true ->
    sel g q = Some e -> admissible_edge m r e = true.

Theorem the_specification_returns_only_admitted_edges :
  forall (m : Machine) (r : list nat),
    ReturnsOnlyAdmittedEdges m r spec_select.
Proof.
  intros m r g q e Hg H.
  exact (find_of_in Edge (admissible_edge m r) (matches q) g.(graph_edges) e Hg H).
Qed.

(* The monotonicity clause: what sits inside a bound sits inside every wider
   one, so raising the request is a widening of the admitted set and never a
   widening of the graph. *)
Theorem an_edge_inside_a_bound_is_inside_every_wider_one :
  forall (e : Edge) (b1 b2 : nat),
    Nat.leb e.(edge_limit) b1 = true -> Nat.leb b1 b2 = true ->
    Nat.leb e.(edge_limit) b2 = true.
Proof. intros e b1 b2 H1 H2. exact (leb_trans _ _ _ H1 H2). Qed.

(* O8 (R-12-024b's acceptance clause): an intent naming no admitted edge
   fails closed. *)
Definition FailsClosed (sel : Selector) : Prop :=
  forall (g : Graph) (q : Request),
    any_of (matches q) g.(graph_edges) = false -> sel g q = None.

Theorem the_specification_fails_closed :
  FailsClosed spec_select.
Proof.
  intros g q H. exact (find_of_none Edge (matches q) g.(graph_edges) H).
Qed.

(* =========================================================================
   O21: the three introductions R-12-013a's acceptance clause forbids, as a
   Prop over the closed enumeration rather than as three separate statements.
   It carries the number after the last one taken and sits where its
   obligation belongs, which is beside the selection half it reads, rather
   than taking a number between two that are already spoken for. That is the
   register's own convention for an id inserted between two others, kept here
   so that an obligation number in a note goes on naming what it named.

   Each of the three is read at a quantity the composition already fixes,
   which is what stops the enumeration from being decorative: a desktop-
   specific wire protocol is an edge declaring a world the composition did
   not, an open-ended intent string is a selection that moves with the
   caller-supplied name, and an authority-bearing path is an edge whose
   declared bounds exceed the declaring package's own manifest. Two are the
   composer's and one is the selector's, so the obligation is over the pair
   and each is refuted by a construction this file already carries. Dropping
   a constructor here drops one of the three.
   ========================================================================= *)

Definition IntroducesNothing (c : Composer) (sel : Selector) : Prop :=
  forall (m : Machine) (a : Ambient) (r : list nat) (k : ForbiddenIntroduction),
    match k with
    | DesktopWireProtocol =>
        all_of (fun e => Nat.ltb e.(edge_world) m.(world_count))
               (c m a r).(graph_edges) = true
    | OpenEndedIntentString => DoesNotReadTheName sel
    | AuthorityBearingPath =>
        all_of (fun e => Nat.leb e.(edge_bounds)
                                 (m.(descriptor) e.(edge_owner)).(desc_manifest))
               (c m a r).(graph_edges) = true
    end.

Theorem the_specification_introduces_nothing :
  IntroducesNothing spec_compose spec_select.
Proof.
  intros m a r k. destruct k.
  - exact (every_composed_edge_declares_an_interface_world m a r).
  - exact the_specification_selection_does_not_read_the_name.
  - exact (the_specification_never_widens_a_manifest m a r).
Qed.

(* The two dropped-conjunct composers keep the other member of the pair they
   do not break, read out of the weakened filter rather than computed on the
   demo: dropping conjunct 6 leaves conjunct 9 at index 8, and dropping
   conjunct 9 leaves conjunct 6 where it was. *)
Lemma dropping_the_world_keeps_the_manifest :
  forall (m : Machine) (r : list nat) (e : Edge),
    all_of (fun p => p e) (drop_at 6 (edge_conjuncts m r)) = true ->
    Nat.leb e.(edge_bounds) (m.(descriptor) e.(edge_owner)).(desc_manifest) = true.
Proof.
  intros m r e H. unfold edge_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ _ H4 ].
  destruct (andb_split _ _ H4) as [ _ H5 ].
  destruct (andb_split _ _ H5) as [ _ H6 ].
  destruct (andb_split _ _ H6) as [ _ H7 ].
  destruct (andb_split _ _ H7) as [ _ H8 ].
  destruct (andb_split _ _ H8) as [ H9 _ ]. exact H9.
Qed.

Lemma dropping_the_manifest_keeps_the_world :
  forall (m : Machine) (r : list nat) (e : Edge),
    all_of (fun p => p e) (drop_at 9 (edge_conjuncts m r)) = true ->
    Nat.ltb e.(edge_world) m.(world_count) = true.
Proof.
  intros m r e H. unfold edge_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ _ H4 ].
  destruct (andb_split _ _ H4) as [ _ H5 ].
  destruct (andb_split _ _ H5) as [ _ H6 ].
  destruct (andb_split _ _ H6) as [ H7 _ ]. exact H7.
Qed.

Theorem the_worldless_composer_keeps_the_manifest_clause :
  forall (m : Machine) (a : Ambient) (r : list nat),
    all_of (fun e => Nat.leb e.(edge_bounds)
                             (m.(descriptor) e.(edge_owner)).(desc_manifest))
           (worldless_compose m a r).(graph_edges) = true.
Proof.
  intros m a r. unfold worldless_compose, compose_without. simpl.
  apply (all_of_mono Edge
           (fun e => all_of (fun p => p e) (drop_at 6 (edge_conjuncts m r)))).
  - intros e He. exact (dropping_the_world_keeps_the_manifest m r e He).
  - apply all_of_filter_self.
Qed.

Theorem the_widening_composer_keeps_the_world_clause :
  forall (m : Machine) (a : Ambient) (r : list nat),
    all_of (fun e => Nat.ltb e.(edge_world) m.(world_count))
           (widening_compose m a r).(graph_edges) = true.
Proof.
  intros m a r. unfold widening_compose, compose_without. simpl.
  apply (all_of_mono Edge
           (fun e => all_of (fun p => p e) (drop_at 9 (edge_conjuncts m r)))).
  - intros e He. exact (dropping_the_manifest_keeps_the_world m r e He).
  - apply all_of_filter_self.
Qed.

(* -------------------------------------------------------------------------
   The refuting selectors. Each is `find_of` or `find_last_of` over the same
   edge list, so every one of them returns only edges the graph carries and
   what refutes it is the clause it reads rather than the list it scans.
   ------------------------------------------------------------------------- *)

(* Gap b's other discipline: a last-match selector is as deterministic as a
   first-match one, is a function of the graph, the intent and the bound, and
   keeps every obligation. The two differ observably on a graph carrying two
   edges that match one intent, and no entry chooses. *)
Definition last_match_select : Selector :=
  fun g q => find_last_of (matches q) g.(graph_edges).

(* O6's refuter: a round-robin or load-following selector, which returns only
   admitted edges and answers differently on the second run. *)
Definition round_robin_select : Selector := fun g q =>
  if Nat.ltb 0 q.(req_run)
  then find_last_of (matches q) g.(graph_edges)
  else find_of (matches q) g.(graph_edges).

(* O7's refuter: a selector that reads the caller-supplied name, which is
   R-12-024d's "caller-controlled handler naming" and R-12-024b's
   "executable lookup" met at the graph rather than left as absences. *)
Definition name_reading_select : Selector := fun g q =>
  if Nat.ltb 0 q.(req_intent).(int_name)
  then find_last_of (matches q) g.(graph_edges)
  else find_of (matches q) g.(graph_edges).

(* O8's first refuter: where the intent names no admitted edge it picks the
   nearest compatible one, which is the fallback R-12-024b's acceptance
   clause excludes. It is deterministic and returns only admitted edges. *)
Definition fallback_select : Selector := fun g q =>
  match find_of (matches q) g.(graph_edges) with
  | Some e => Some e
  | None => find_of (fun e => Nat.leb e.(edge_limit) q.(req_bound))
                    g.(graph_edges)
  end.

(* O8's second refuter, which is O4's fifth mechanism read from the selection
   side: where the intent names no admitted edge it guesses from the bytes.
   It is deterministic in the run and in the name and returns only admitted
   edges, and it both fails to fail closed and sniffs. *)
Definition sniffing_select : Selector := fun g q =>
  match find_of (matches q) g.(graph_edges) with
  | Some e => Some e
  | None => find_of (fun e => Nat.eqb e.(edge_format) q.(req_content))
                    g.(graph_edges)
  end.

(* O9b's refuter: a selector that answers the intent and ignores the bound. *)
Definition overrunning_select : Selector := fun g q =>
  find_of (fun e => Nat.eqb e.(edge_intent) q.(req_intent).(int_index))
          g.(graph_edges).

(* O9c's refuter: where nothing inside the bound answers, it invents an edge
   at exactly the bound rather than refusing, which is a widening of the
   graph rather than of the request. Its declared limit is the caller's own
   bound, so it keeps the bound clause; it carries no ring the composition
   sized, which is what makes it an edge no composition emitted. *)
Definition widened_edge (q : Request) : Edge := {|
  edge_owner := 0;
  edge_target := 0;
  edge_intent := q.(req_intent).(int_index);
  edge_from := 0;
  edge_to := 0;
  edge_limit := q.(req_bound);
  edge_world := 0;
  edge_format := 0;
  edge_bounds := 0;
  edge_ring := 0
|}.

Definition widening_select : Selector := fun g q =>
  match find_of (matches q) g.(graph_edges) with
  | Some e => Some e
  | None => Some (widened_edge q)
  end.

(* The obligations each refuter keeps, stated of an arbitrary graph and
   request rather than computed on the demo, so that what refutes each below
   is the named defect and not the shape of the construction. *)
Theorem the_last_match_selector_keeps_every_selection_obligation :
  DoesNotVaryWithTheRun last_match_select
  /\ DoesNotReadTheName last_match_select
  /\ DoesNotSniffTheContent last_match_select
  /\ RespectsTheRequestedBound last_match_select
  /\ AnswersTheRequestedIntent last_match_select
  /\ FailsClosed last_match_select.
Proof.
  split; [ intros g q n1 n2; reflexivity | ].
  split; [ intros g q n1 n2; reflexivity | ].
  split; [ intros g q n1 n2; reflexivity | ].
  split.
  - intros g q e H.
    assert (Hm : matches q e = true) by
      exact (find_last_of_holds Edge (matches q) g.(graph_edges) e H).
    unfold matches in Hm. destruct (andb_split _ _ Hm) as [ _ Hb ]. exact Hb.
  - split.
    + intros g q e H.
      assert (Hm : matches q e = true) by
        exact (find_last_of_holds Edge (matches q) g.(graph_edges) e H).
      unfold matches in Hm. destruct (andb_split _ _ Hm) as [ Hi _ ]. exact Hi.
    + intros g q H.
      exact (find_last_of_none Edge (matches q) g.(graph_edges) H).
Qed.

Theorem the_last_match_selector_returns_only_admitted_edges :
  forall (m : Machine) (r : list nat),
    ReturnsOnlyAdmittedEdges m r last_match_select.
Proof.
  intros m r g q e Hg H.
  exact (find_last_of_in Edge (admissible_edge m r) (matches q)
           g.(graph_edges) e Hg H).
Qed.

Theorem the_round_robin_selector_keeps_the_name_and_the_content :
  DoesNotReadTheName round_robin_select
  /\ DoesNotSniffTheContent round_robin_select.
Proof.
  split; intros g q n1 n2; unfold round_robin_select; simpl; reflexivity.
Qed.

Theorem the_name_reading_selector_keeps_the_run_and_the_content :
  DoesNotVaryWithTheRun name_reading_select
  /\ DoesNotSniffTheContent name_reading_select.
Proof.
  split; intros g q n1 n2; unfold name_reading_select; simpl; reflexivity.
Qed.

Theorem the_fallback_selector_keeps_the_run_the_name_and_the_content :
  DoesNotVaryWithTheRun fallback_select
  /\ DoesNotReadTheName fallback_select
  /\ DoesNotSniffTheContent fallback_select.
Proof.
  split; [ intros g q n1 n2; reflexivity | ].
  split; intros g q n1 n2; reflexivity.
Qed.

Theorem the_sniffing_selector_keeps_the_run_and_the_name :
  DoesNotVaryWithTheRun sniffing_select
  /\ DoesNotReadTheName sniffing_select.
Proof.
  split; intros g q n1 n2; reflexivity.
Qed.

Theorem the_overrunning_selector_answers_the_requested_intent :
  AnswersTheRequestedIntent overrunning_select
  /\ DoesNotVaryWithTheRun overrunning_select.
Proof.
  split.
  - intros g q e H.
    exact (find_of_holds Edge
             (fun e0 => Nat.eqb e0.(edge_intent) q.(req_intent).(int_index))
             g.(graph_edges) e H).
  - intros g q n1 n2. reflexivity.
Qed.

Theorem the_overrunning_selector_returns_only_admitted_edges :
  forall (m : Machine) (r : list nat),
    ReturnsOnlyAdmittedEdges m r overrunning_select.
Proof.
  intros m r g q e Hg H.
  exact (find_of_in Edge (admissible_edge m r)
           (fun e0 => Nat.eqb e0.(edge_intent) q.(req_intent).(int_index))
           g.(graph_edges) e Hg H).
Qed.

Theorem the_widening_selector_keeps_the_requested_bound :
  RespectsTheRequestedBound widening_select.
Proof.
  intros g q e H. unfold widening_select in H.
  destruct (find_of (matches q) g.(graph_edges)) as [ f | ] eqn:Hf.
  - injection H as H. rewrite <- H.
    assert (Hm : matches q f = true) by
      exact (find_of_holds Edge (matches q) g.(graph_edges) f Hf).
    unfold matches in Hm. destruct (andb_split _ _ Hm) as [ _ Hb ]. exact Hb.
  - injection H as H. rewrite <- H. simpl. exact (nat_leb_refl q.(req_bound)).
Qed.

(* What the selection did with a bound, and whether it left the graph: the two
   computations the monotonicity witnesses below are read off, so no leb sits
   in a hypothesis where a weakening could pass it by. *)
Definition selects_inside (sel : Selector) (g : Graph) (q : Request)
                          (b : nat) : bool :=
  match sel g (with_bound q b) with
  | None => true
  | Some e => Nat.leb e.(edge_limit) b
  end.

Definition widens (m : Machine) (r : list nat) (sel : Selector) (g : Graph)
                  (q : Request) (b : nat) : bool :=
  match sel g (with_bound q b) with
  | None => false
  | Some e => negb (admissible_edge m r e)
  end.

(* Reading a conjunction over a list back at its head and its tail, which is
   how each conjunct of `template_ok` below is read out of the whole and how
   a partial binder is refuted at exactly the quantity it dropped. *)
Lemma all_of_head_false :
  forall (A : Type) (p : A -> bool) (x : A) (l : list A),
    p x = false -> all_of p (cons x l) = false.
Proof. intros A p x l H. simpl. rewrite H. reflexivity. Qed.

Lemma all_of_tail_false :
  forall (A : Type) (p : A -> bool) (x : A) (l : list A),
    all_of p l = false -> all_of p (cons x l) = false.
Proof.
  intros A p x l H. simpl. rewrite H. destruct (p x); reflexivity.
Qed.

(* =========================================================================
   O11: the four quantities R-12-024c admits before a node may be bound.

   Four partial binders are generated over the closed enumeration, each
   dropping one quantity and keeping the other three. The family's fallback
   past the last index is the specification's own binder (reading 9).
   ========================================================================= *)

Definition MayBind : Type := Machine -> nat -> bool.

Definition spec_may_bind : MayBind := fun m n =>
  all_of (m.(descriptor) n).(desc_admits) all_admitted_quantities.

Definition RequiresEveryQuantity (b : MayBind) : Prop :=
  forall (m : Machine) (n : nat) (q : AdmittedQuantity),
    (m.(descriptor) n).(desc_admits) q = false -> b m n = false.

Theorem the_specification_requires_every_quantity :
  RequiresEveryQuantity spec_may_bind.
Proof.
  intros m n q H. unfold spec_may_bind, all_admitted_quantities. destruct q.
  - apply all_of_head_false. exact H.
  - apply all_of_tail_false. apply all_of_head_false. exact H.
  - apply all_of_tail_false. apply all_of_tail_false.
    apply all_of_head_false. exact H.
  - apply all_of_tail_false. apply all_of_tail_false.
    apply all_of_tail_false. apply all_of_head_false. exact H.
Qed.

Definition binder_without (k : nat) : MayBind := fun m n =>
  all_of (m.(descriptor) n).(desc_admits) (drop_at k all_admitted_quantities).

Definition all_partial_binders : list MayBind :=
  map_over binder_without (upto 4).

Definition partial_binder_at (n : nat) : MayBind :=
  at_member all_partial_binders n spec_may_bind.

Example the_partial_binders_are_four :
  count_of all_partial_binders = 4 := eq_refl.

(* How many of the four a binder still requires: the measure that makes the
   family one refutation per quantity rather than one weaker binder exhibited
   four times. *)
Definition quantities_required (k : nat) : nat :=
  count_of (drop_at k all_admitted_quantities).

Example each_partial_binder_still_requires_three :
  map_over quantities_required (upto 4)
  = cons 3 (cons 3 (cons 3 (cons 3 nil))) := eq_refl.

Example dropping_past_the_last_quantity_drops_nothing :
  quantities_required 4 = 4 := eq_refl.

(* =========================================================================
   O12: admission time by node origin (R-12-024c).

   Each node's admission time is the one its origin fixes, and the register
   names two origins and no third time, so the obligation is an equality
   between two values of `NodeOrigin` rather than a correspondence between
   two types.
   ========================================================================= *)

Definition Schedule : Type := Machine -> nat -> NodeOrigin.

Definition spec_schedule : Schedule := fun m n => (m.(descriptor) n).(desc_origin).

Definition AdmitsAtTheTimeTheOriginFixes (s : Schedule) : Prop :=
  forall (m : Machine) (n : nat), s m n = (m.(descriptor) n).(desc_origin).

Theorem the_specification_admits_at_the_time_the_origin_fixes :
  AdmitsAtTheTimeTheOriginFixes spec_schedule.
Proof. intros m n. reflexivity. Qed.

(* The composition's own record of when each node was admitted, which the
   check below compares against the time its origin fixes. *)
Definition recorded_schedule : Schedule :=
  fun m n => (m.(descriptor) n).(desc_admitted_at).

Definition admitted_at_its_origin_time (m : Machine) (n : nat) : bool :=
  origin_eqb (recorded_schedule m n) (spec_schedule m n).

(* The refuter: a composer that admits every node at release time, leaving
   the install-time admission R-12-024c requires of a package-supplied node
   unmade. It agrees with the specification on every base-image node and
   touches no quantity, so it keeps the four-quantity obligation entire. *)
Definition release_time_schedule : Schedule := fun _ _ => BaseImage.

Theorem the_release_time_schedule_agrees_on_every_base_image_node :
  forall (m : Machine) (n : nat),
    (m.(descriptor) n).(desc_origin) = BaseImage ->
    release_time_schedule m n = spec_schedule m n.
Proof. intros m n H. unfold release_time_schedule, spec_schedule. rewrite H. reflexivity. Qed.

(* =========================================================================
   O13: what a runtime binding may not create (R-12-024c's acceptance
   clause). Four creating binders generated over the closed enumeration, each
   keeping the other three, with the specification's own binder as the
   family's fallback (reading 9).
   ========================================================================= *)

Definition Creation : Type := ForbiddenCreation -> bool.

Definition spec_creates : Creation := fun _ => false.

Definition CreatesNothing (c : Creation) : Prop :=
  all_of (fun k => negb (c k)) all_forbidden_creations = true.

Theorem the_specification_binding_creates_nothing :
  CreatesNothing spec_creates.
Proof. reflexivity. Qed.

Definition all_creating_binders : list Creation :=
  map_over (fun k => fun j => creation_eqb j k) all_forbidden_creations.

Definition creating_at (n : nat) : Creation :=
  at_member all_creating_binders n spec_creates.

Example the_creating_binders_are_four :
  count_of all_creating_binders = 4 := eq_refl.

(* =========================================================================
   O14: a template binds from bounded pools and a full pool answers with a
   typed verdict (R-12-024c with R-08-046 and R-08-047).

   R-08-047's sentence names four obligations of the verdict and this file
   states three. It cannot be dropped and it cannot be converted into an
   implicit wait, which `AlwaysAnswers` states as one predicate because a
   binder that answers at every occupancy does neither. It cannot be answered
   by borrowing from another pool, which `BorrowsNothing` states in both
   directions rather than one, since a shortfall charged to the node pool is
   the same defect as one charged to the ring pool; stating it both ways is
   also what makes the typed verdict name the pool that is actually full
   rather than merely report a shortfall. The fourth is the relevance grade,
   and it is the one not stated here: the header defers it to R-05-098's IDL
   or ABI declaration and R-05-097's derivation type-check, neither being a
   composer's act.

   A third predicate comes from outside that sentence and is marked as such:
   the entry's own fail-closed line adds that a full pool declines rather
   than blocking, borrowing or overcommitting, which is `DeclinesWhenFull`.

   Four refuting binders, each breaking exactly one predicate and keeping the
   other two: one drops the request, one overcommits, and two borrow, one in
   each direction.
   ========================================================================= *)

Definition Binder : Type := Machine -> Occupancy -> list Stage -> option Verdict.

Definition node_full (m : Machine) (occ : Occupancy) (t : list Stage) : bool :=
  Nat.ltb m.(node_pool_capacity) (occ.(nodes_bound) + count_of t).

Definition ring_full (m : Machine) (occ : Occupancy) (t : list Stage) : bool :=
  Nat.ltb m.(ring_pool_capacity) (occ.(rings_bound) + count_of t).

Definition spec_bind : Binder := fun m occ t =>
  if node_full m occ t then Some (CapacityExhausted NodePool)
  else if ring_full m occ t then Some (CapacityExhausted RingPool)
  else Some Bound.

Definition is_bound (v : option Verdict) : bool :=
  match v with Some Bound => true | _ => false end.

(* R-08-047: the request cannot be dropped or converted into an implicit
   wait, so a binder answers at every occupancy. *)
Definition AlwaysAnswers (b : Binder) : Prop :=
  forall (m : Machine) (occ : Occupancy) (t : list Stage),
    is_some (b m occ t) = true.

(* R-08-047's fail-closed clause: a full pool declines the binding rather
   than blocking, borrowing, or overcommitting. *)
Definition DeclinesWhenFull (b : Binder) : Prop :=
  forall (m : Machine) (occ : Occupancy) (t : list Stage),
    node_full m occ t = true -> is_bound (b m occ t) = false.

(* R-08-047's borrowing clause: a decline names the pool that is actually
   full, so the shortfall is not charged to the other one. Both directions,
   because a clause stated at one pool alone leaves a binder free to charge
   the node pool for a ring shortfall and call it typed. *)
Definition BorrowsNothing (b : Binder) : Prop :=
  forall (m : Machine) (occ : Occupancy) (t : list Stage),
    (b m occ t = Some (CapacityExhausted RingPool) -> ring_full m occ t = true)
    /\ (b m occ t = Some (CapacityExhausted NodePool) -> node_full m occ t = true).

Theorem the_specification_binder_always_answers : AlwaysAnswers spec_bind.
Proof.
  intros m occ t. unfold spec_bind.
  destruct (node_full m occ t); [ reflexivity | ].
  destruct (ring_full m occ t); reflexivity.
Qed.

Theorem the_specification_binder_declines_when_full : DeclinesWhenFull spec_bind.
Proof. intros m occ t H. unfold spec_bind. rewrite H. reflexivity. Qed.

Theorem the_specification_binder_borrows_nothing : BorrowsNothing spec_bind.
Proof.
  intros m occ t. split.
  - intros H. unfold spec_bind in H.
    destruct (node_full m occ t); [ discriminate H | ].
    destruct (ring_full m occ t) eqn:Hr; [ reflexivity | discriminate H ].
  - intros H. unfold spec_bind in H.
    destruct (node_full m occ t) eqn:Hn; [ reflexivity | ].
    destruct (ring_full m occ t); discriminate H.
Qed.

(* Three of the four refuters, the fourth being the reverse borrower stated
   beside its refutation below. Each answers exactly as the specification
   does wherever the node pool has room, so what refutes each is the arm it
   took when the pool was full. *)
Definition blocking_bind : Binder := fun m occ t =>
  if node_full m occ t then None else spec_bind m occ t.

Definition growing_bind : Binder := fun m occ t =>
  if node_full m occ t then Some Bound else spec_bind m occ t.

Definition borrowing_bind : Binder := fun m occ t =>
  if node_full m occ t then Some (CapacityExhausted RingPool)
  else spec_bind m occ t.

Theorem the_blocking_binder_keeps_the_decline_and_the_borrowing_clause :
  DeclinesWhenFull blocking_bind /\ BorrowsNothing blocking_bind.
Proof.
  split.
  - intros m occ t H. unfold blocking_bind. rewrite H. reflexivity.
  - intros m occ t. split; intros H.
    + apply (proj1 (the_specification_binder_borrows_nothing m occ t)).
      unfold blocking_bind in H.
      destruct (node_full m occ t); [ discriminate H | exact H ].
    + apply (proj2 (the_specification_binder_borrows_nothing m occ t)).
      unfold blocking_bind in H.
      destruct (node_full m occ t); [ discriminate H | exact H ].
Qed.

Theorem the_growing_binder_keeps_the_answer_and_the_borrowing_clause :
  AlwaysAnswers growing_bind /\ BorrowsNothing growing_bind.
Proof.
  split.
  - intros m occ t. unfold growing_bind.
    destruct (node_full m occ t); [ reflexivity | ].
    exact (the_specification_binder_always_answers m occ t).
  - intros m occ t. split; intros H.
    + apply (proj1 (the_specification_binder_borrows_nothing m occ t)).
      unfold growing_bind in H.
      destruct (node_full m occ t); [ discriminate H | exact H ].
    + apply (proj2 (the_specification_binder_borrows_nothing m occ t)).
      unfold growing_bind in H.
      destruct (node_full m occ t); [ discriminate H | exact H ].
Qed.

Theorem the_borrowing_binder_keeps_the_answer_and_the_decline :
  AlwaysAnswers borrowing_bind /\ DeclinesWhenFull borrowing_bind.
Proof.
  split.
  - intros m occ t. unfold borrowing_bind.
    destruct (node_full m occ t); [ reflexivity | ].
    exact (the_specification_binder_always_answers m occ t).
  - intros m occ t H. unfold borrowing_bind. rewrite H. reflexivity.
Qed.

(* =========================================================================
   The composition-time template (R-12-024c, R-13-001b, R-12-013a, R-12-005,
   R-08-021).

   Reading 7: a template is an ordered chain of stages, its joins typed and
   its two ends the declared ones. Seven conjuncts, held as a list for the
   same reason the edge's twelve are (reading 4).
   ========================================================================= *)

(* R-12-013a's bounded input and output types, read along the chain: the
   output type of stage i is the input type of stage i+1. *)
Fixpoint chain_typed (t : list Stage) : bool :=
  match t with
  | nil => true
  | cons s r =>
      match r with
      | nil => true
      | cons s2 _ => andb (Nat.eqb s.(stage_out) s2.(stage_in)) (chain_typed r)
      end
  end.

Fixpoint last_out (t : list Stage) : nat :=
  match t with
  | nil => 0
  | cons s r => match r with nil => s.(stage_out) | cons _ _ => last_out r end
  end.

(* The chain's own two ends against the ones the composition declared. An
   empty chain declares neither, so it is refused here rather than passing
   every conjunct vacuously, which is what makes a proper suffix down to
   nothing a refusal rather than a silence. *)
Definition ends_match (m : Machine) (t : list Stage) : bool :=
  match t with
  | nil => false
  | cons s _ => andb (Nat.eqb s.(stage_in) m.(template_in))
                     (Nat.eqb (last_out t) m.(template_out))
  end.

(* How many joins of a chain are broken: the measure that says which conjunct
   a generated weakening broke rather than that some conjunct did. *)
Fixpoint joins_broken (t : list Stage) : nat :=
  match t with
  | nil => 0
  | cons s r =>
      match r with
      | nil => 0
      | cons s2 _ =>
          (if Nat.eqb s.(stage_out) s2.(stage_in) then 0 else 1) + joins_broken r
      end
  end.

(* R-08-021 read over a bound template's chain: every join is between two
   nodes at one confidentiality level, or the composition declared the
   inter-level channel. This is that entry applied rather than R-12-024c
   stated, R-12-024c requiring labels admitted and saying nothing about the
   flow condition over a chain, and it is a reading rather than a
   transcription. *)
Definition stage_label (m : Machine) (s : Stage) : nat :=
  (m.(descriptor) s.(stage_node)).(desc_label).

Fixpoint labels_joined (m : Machine) (t : list Stage) : bool :=
  match t with
  | nil => true
  | cons s r =>
      match r with
      | nil => true
      | cons s2 _ =>
          andb (orb (Nat.eqb (stage_label m s) (stage_label m s2))
                    (m.(channel) (stage_label m s) (stage_label m s2)))
               (labels_joined m r)
      end
  end.

Definition template_conjuncts (m : Machine) : list (list Stage -> bool) :=
  (* 0, 1: R-12-013a's bounded input and output types, along the chain and at
     its two declared ends (O17). *)
  cons chain_typed
  (cons (ends_match m)
  (* 2, 3: R-13-001b with R-12-024c. Every node a template names is already on
     the composed roster and already admitted under section 11, so a template
     is not a pre-proved empty slot (O15). *)
  (cons (fun t => all_of (fun s => mem_nat s.(stage_node) m.(roster)) t)
  (cons (fun t => all_of (fun s => spec_may_bind m s.(stage_node)) t)
  (* 4, 5: R-12-005 with R-12-024c's bounded-ring pools, at composition; the
     binding-time half is `CreatedUnboundedQueue` above (reading 8, O18). *)
  (cons (fun t => all_of (fun s => Nat.ltb 0 s.(stage_ring)) t)
  (cons (fun t => all_of (fun s => Nat.leb s.(stage_ring) m.(ring_depth_ceiling)) t)
  (* 6: R-08-021's flow condition over the chain (O19). *)
  (cons (labels_joined m) nil)))))).

Definition template_ok (m : Machine) (t : list Stage) : bool :=
  all_of (fun p => p t) (template_conjuncts m).

Definition template_conjuncts_broken (m : Machine) (t : list Stage) : nat :=
  count_of (filter_of (fun p => negb (p t)) (template_conjuncts m)).

Example there_are_seven_template_conjuncts :
  forall m : Machine, count_of (template_conjuncts m) = 7.
Proof. intros m. reflexivity. Qed.

(* O17 (R-12-013a): a well-formed template is a typed chain between its two
   declared ends, stated of an arbitrary machine and an arbitrary chain. *)
Theorem a_well_formed_template_is_a_typed_chain :
  forall (m : Machine) (t : list Stage),
    template_ok m t = true -> chain_typed t = true /\ ends_match m t = true.
Proof.
  intros m t H. unfold template_ok, template_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ H0 H1' ].
  destruct (andb_split _ _ H1') as [ H1 _ ].
  exact (conj H0 H1).
Qed.

(* O15 (R-13-001b with R-12-024c): every node a template names is already
   composed and already admitted, so the template is not a pre-proved empty
   slot and no package binds into one. *)
Theorem a_well_formed_template_binds_composed_admitted_nodes :
  forall (m : Machine) (t : list Stage),
    template_ok m t = true ->
    all_of (fun s => mem_nat s.(stage_node) m.(roster)) t = true
    /\ all_of (fun s => spec_may_bind m s.(stage_node)) t = true.
Proof.
  intros m t H. unfold template_ok, template_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ H3 H4' ].
  destruct (andb_split _ _ H4') as [ H4 _ ].
  exact (conj H3 H4).
Qed.

(* O18 (R-12-005 with R-12-024c): every ring a template declares has a
   nonzero depth inside the ceiling the composition sized. *)
Theorem a_well_formed_template_declares_bounded_rings :
  forall (m : Machine) (t : list Stage),
    template_ok m t = true ->
    all_of (fun s => Nat.ltb 0 s.(stage_ring)) t = true
    /\ all_of (fun s => Nat.leb s.(stage_ring) m.(ring_depth_ceiling)) t = true.
Proof.
  intros m t H. unfold template_ok, template_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ _ H4 ].
  destruct (andb_split _ _ H4) as [ H5 H6' ].
  destruct (andb_split _ _ H6') as [ H6 _ ].
  exact (conj H5 H6).
Qed.

(* O19 (R-08-021 applied): every join of a bound template is between two
   nodes at one level, or the composition declared the channel. *)
Theorem a_well_formed_template_crosses_no_undeclared_label :
  forall (m : Machine) (t : list Stage),
    template_ok m t = true -> labels_joined m t = true.
Proof.
  intros m t H. unfold template_ok, template_conjuncts in H. simpl in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ _ H4 ].
  destruct (andb_split _ _ H4) as [ _ H5 ].
  destruct (andb_split _ _ H5) as [ _ H6 ].
  destruct (andb_split _ _ H6) as [ H7 _ ].
  exact H7.
Qed.

(* The four generated families over a chain (R-05-166), which is this item's
   answer to the generate-rather-than-author clause: a transposition, a
   deletion, a proper suffix and a duplicated stage, one per position, from
   the composed template's own stage list rather than authored one by one. *)
Definition transpositions (t : list Stage) : list (list Stage) :=
  map_over (fun n => swap_at n t) (upto (before_last (count_of t))).

Definition deletions (t : list Stage) : list (list Stage) :=
  map_over (fun n => drop_at n t) (upto (count_of t)).

Definition proper_suffixes (t : list Stage) : list (list Stage) :=
  map_over (fun n => suffix_at (S n) t) (upto (count_of t)).

Definition duplicate_stages (s : Stage) (t : list Stage) : list (list Stage) :=
  map_over (fun n => insert_at n s t) (upto (S (count_of t))).

Definition generated_weakenings (s : Stage) (t : list Stage) : list (list Stage) :=
  app (transpositions t)
      (app (deletions t) (app (proper_suffixes t) (duplicate_stages s t))).

(* =========================================================================
   The demo composition, for R-05-165's uninhabited-domain mode and for the
   refutation witnesses. Four packages on the roster, whose descriptors
   declare sixteen edges of which four are admissible; a four-stage media
   template; both pools with an occupancy sitting exactly on the capacity
   boundary; and a value on the boundary of every comparison the file makes.
   Every figure below is an arbitrary witness value and carries no
   composition claim (gap j); the ledger at the end pins each one.
   ------------------------------------------------------------------------- *)

Definition edge_of (own tgt itn frm too lim wld fmt bnd rng : nat) : Edge := {|
  edge_owner := own;
  edge_target := tgt;
  edge_intent := itn;
  edge_from := frm;
  edge_to := too;
  edge_limit := lim;
  edge_world := wld;
  edge_format := fmt;
  edge_bounds := bnd;
  edge_ring := rng
|}.

Definition stage_of (nd inn outp rng : nat) : Stage := {|
  stage_node := nd;
  stage_in := inn;
  stage_out := outp;
  stage_ring := rng
|}.

Definition descriptor_of (es : list Edge) (man : nat) (org adm : NodeOrigin)
                         (ad : AdmittedQuantity -> bool) (lab : nat) : Descriptor := {|
  desc_edges := es;
  desc_manifest := man;
  desc_origin := org;
  desc_admitted_at := adm;
  desc_admits := ad;
  desc_label := lab
|}.

Definition full_admits : AdmittedQuantity -> bool := fun _ => true.
Definition none_admits : AdmittedQuantity -> bool := fun _ => false.
Definition all_but (q : AdmittedQuantity) : AdmittedQuantity -> bool :=
  fun j => negb (quantity_eqb j q).

(* The four admissible transformations, a decode, a conversion, a mix and a
   render, each declaring the ten things R-12-013a, R-12-024e, R-12-024f and
   R-12-005 require of it. Two of them sit exactly on a boundary: the decode's
   declared bounds equal its package's whole manifest, and the conversion's
   ring depth equals the ceiling the composition sized. *)
Definition e_decode : Edge := edge_of 0 1 0 0 1 2 0 0 5 1.
Definition e_convert : Edge := edge_of 1 2 1 1 2 3 0 1 2 3.
Definition e_mix : Edge := edge_of 1 3 2 2 3 4 1 1 4 2.
Definition e_render : Edge := edge_of 3 0 3 3 0 2 1 1 1 1.

(* The edge a package-supplied script would produce if the installation path
   ran one (R-13-002). It is admissible on every conjunct, so what keeps it
   out of the graph is the specification's own indifference to the script and
   not a malformed field. *)
Definition e_scripted : Edge := edge_of 2 1 4 0 1 2 0 0 1 1.

(* A second edge answering the intent the decode answers, which is the graph
   gap b is about: two admissible edges matching one intent, on which a
   first-match and a last-match selector disagree and each is deterministic. *)
Definition e_second_decode : Edge := edge_of 2 1 0 0 1 2 0 0 1 1.

(* One setter per field, so that a spoiled edge is the decode with exactly one
   field moved rather than a second edge that happens to differ in one place.
   Ten definitions carrying no figure between them, which is what makes the
   twelve spoilers below carry twelve numbers and not a hundred and twenty. *)
Definition set_owner (v : nat) (e : Edge) : Edge :=
  edge_of v e.(edge_target) e.(edge_intent) e.(edge_from) e.(edge_to)
          e.(edge_limit) e.(edge_world) e.(edge_format) e.(edge_bounds)
          e.(edge_ring).

Definition set_target (v : nat) (e : Edge) : Edge :=
  edge_of e.(edge_owner) v e.(edge_intent) e.(edge_from) e.(edge_to)
          e.(edge_limit) e.(edge_world) e.(edge_format) e.(edge_bounds)
          e.(edge_ring).

Definition set_intent (v : nat) (e : Edge) : Edge :=
  edge_of e.(edge_owner) e.(edge_target) v e.(edge_from) e.(edge_to)
          e.(edge_limit) e.(edge_world) e.(edge_format) e.(edge_bounds)
          e.(edge_ring).

Definition set_from (v : nat) (e : Edge) : Edge :=
  edge_of e.(edge_owner) e.(edge_target) e.(edge_intent) v e.(edge_to)
          e.(edge_limit) e.(edge_world) e.(edge_format) e.(edge_bounds)
          e.(edge_ring).

Definition set_to (v : nat) (e : Edge) : Edge :=
  edge_of e.(edge_owner) e.(edge_target) e.(edge_intent) e.(edge_from) v
          e.(edge_limit) e.(edge_world) e.(edge_format) e.(edge_bounds)
          e.(edge_ring).

Definition set_limit (v : nat) (e : Edge) : Edge :=
  edge_of e.(edge_owner) e.(edge_target) e.(edge_intent) e.(edge_from)
          e.(edge_to) v e.(edge_world) e.(edge_format) e.(edge_bounds)
          e.(edge_ring).

Definition set_world (v : nat) (e : Edge) : Edge :=
  edge_of e.(edge_owner) e.(edge_target) e.(edge_intent) e.(edge_from)
          e.(edge_to) e.(edge_limit) v e.(edge_format) e.(edge_bounds)
          e.(edge_ring).

Definition set_format (v : nat) (e : Edge) : Edge :=
  edge_of e.(edge_owner) e.(edge_target) e.(edge_intent) e.(edge_from)
          e.(edge_to) e.(edge_limit) e.(edge_world) v e.(edge_bounds)
          e.(edge_ring).

Definition set_bounds (v : nat) (e : Edge) : Edge :=
  edge_of e.(edge_owner) e.(edge_target) e.(edge_intent) e.(edge_from)
          e.(edge_to) e.(edge_limit) e.(edge_world) e.(edge_format) v
          e.(edge_ring).

Definition set_ring (v : nat) (e : Edge) : Edge :=
  edge_of e.(edge_owner) e.(edge_target) e.(edge_intent) e.(edge_from)
          e.(edge_to) e.(edge_limit) e.(edge_world) e.(edge_format)
          e.(edge_bounds) v.

(* The twelve spoiled edges, one per conjunct: the decode with exactly one
   field set, and each set to the value sitting on that conjunct's own
   boundary rather than far past it. *)
Definition spoiled_edges : list Edge :=
  cons (set_owner 4 e_decode)      (* 0: an owner the roster does not carry  *)
  (cons (set_target 4 e_decode)    (* 1: a target the roster does not carry  *)
  (cons (set_limit 0 e_decode)     (* 2: no declared resource limit          *)
  (cons (set_intent 5 e_decode)    (* 3: an intent index at the count        *)
  (cons (set_from 4 e_decode)      (* 4: an input type at the count          *)
  (cons (set_to 4 e_decode)        (* 5: an output type at the count         *)
  (cons (set_world 2 e_decode)     (* 6: an interface world at the count     *)
  (cons (set_format 3 e_decode)    (* 7: a format off the inventory          *)
  (cons (set_format 2 e_decode)    (* 8: a format with no verified parser    *)
  (cons (set_bounds 6 e_decode)    (* 9: bounds past the owner's manifest    *)
  (cons (set_ring 0 e_decode)      (* 10: a ring of no depth                 *)
  (cons (set_ring 4 e_decode)      (* 11: a ring past the declared ceiling   *)
   nil))))))))))).

Definition spoiled_at (n : nat) : Edge := at_member spoiled_edges n e_decode.

Example the_spoiled_edges_are_twelve : count_of spoiled_edges = 12 := eq_refl.

(* One edge per format class whose format the inventory does not carry, the
   decode with only its format moved, generated over the closed enumeration
   rather than authored. Each breaks conjunct 7 and nothing else, so what the
   exemption family below admits is exactly the inventory clause failing at
   one class. The family's fallback past the last class is the composed
   decode itself (reading 9), which is admissible, so a bound raised by one
   makes the theorem fail rather than hold wider. *)
Definition class_index (k : FormatClass) : nat :=
  match k with
  | ImageFormat => 0
  | MediaFormat => 1
  | FontFormat => 2
  | ArchiveFormat => 3
  | DocumentFormat => 4
  end.

Definition uninventoried_edge (k : FormatClass) : Edge :=
  set_format (5 + class_index k) e_decode.

Definition all_uninventoried_edges : list Edge :=
  map_over uninventoried_edge all_format_classes.

Definition uninventoried_at (n : nat) : Edge :=
  at_member all_uninventoried_edges n e_decode.

Example the_uninventoried_edges_are_five :
  count_of all_uninventoried_edges = 5 := eq_refl.

(* The four stages of the demo media template. Which stages a template may
   carry is gap a: the register names none, so these four are witness values
   and not an enumeration. The conversion's ring depth sits exactly on the
   ceiling. *)
Definition s_decode : Stage := stage_of 0 0 1 1.
Definition s_convert : Stage := stage_of 1 1 2 3.
Definition s_mix : Stage := stage_of 2 2 3 2.
Definition s_render : Stage := stage_of 3 3 0 1.

Definition demo_template : list Stage :=
  cons s_decode (cons s_convert (cons s_mix (cons s_render nil))).

(* The four refuting templates, each breaking one conjunct of the seven and
   keeping the rest. The reserved one is R-13-001b's pre-proved empty slot:
   a node the roster does not carry and nothing has admitted. *)
Definition set_stage_node (v : nat) (s : Stage) : Stage :=
  stage_of v s.(stage_in) s.(stage_out) s.(stage_ring).

Definition set_stage_ring (v : nat) (s : Stage) : Stage :=
  stage_of s.(stage_node) s.(stage_in) s.(stage_out) v.

Definition s_reserved : Stage := set_stage_node 9 s_decode.
Definition s_cross_high : Stage := stage_of 3 0 1 1.
Definition s_cross_low : Stage := stage_of 0 1 0 1.
Definition s_zero_ring : Stage := set_stage_ring 0 s_decode.
Definition s_deep_ring : Stage := set_stage_ring 4 s_decode.

Definition reserved_template : list Stage :=
  cons s_reserved (cons s_convert (cons s_mix (cons s_render nil))).

Definition crossing_template : list Stage :=
  cons s_cross_high (cons s_cross_low nil).

Definition zero_ring_template : list Stage :=
  cons s_zero_ring (cons s_convert (cons s_mix (cons s_render nil))).

Definition deep_ring_template : list Stage :=
  cons s_deep_ring (cons s_convert (cons s_mix (cons s_render nil))).

(* The roster: four packages, and package 4 is the one it does not carry. *)
Definition demo_roster : list nat := cons 0 (cons 1 (cons 2 (cons 3 nil))).

Definition demo_descriptor (p : nat) : Descriptor :=
  match p with
  (* the decode's package also declares the twelve spoiled edges, so that
     every conjunct is decided from the composer's side as well as from the
     edge's and no conjunct is refuted only by a witness nothing composed *)
  | 0 => descriptor_of (cons e_decode spoiled_edges) 5 BaseImage BaseImage
                       full_admits 0
  | 1 => descriptor_of (cons e_convert (cons e_mix nil)) 4 BaseImage BaseImage
                       full_admits 0
  (* a package on the roster declaring no transformation, whose script would
     declare one *)
  | 2 => descriptor_of nil 4 PackageSupplied PackageSupplied full_admits 0
  | 3 => descriptor_of (cons e_render nil) 3 PackageSupplied PackageSupplied
                       full_admits 1
  (* the package the roster does not carry, whose manifest is wide enough that
     the stranger-owner spoiler breaks conjunct 0 and no other *)
  | 4 => descriptor_of nil 5 PackageSupplied PackageSupplied full_admits 0
  (* four nodes, each with one of the four quantities not admitted *)
  | 5 => descriptor_of nil 5 BaseImage BaseImage (all_but AdmittedWcet) 0
  | 6 => descriptor_of nil 5 BaseImage BaseImage (all_but AdmittedMemory) 0
  | 7 => descriptor_of nil 5 BaseImage BaseImage (all_but AdmittedLabels) 0
  | 8 => descriptor_of nil 5 BaseImage BaseImage
                       (all_but AdmittedDeviceReservation) 0
  (* R-13-001b's reserved empty slot: composed for an occupant that does not
     exist, so nothing about it is admitted *)
  | 9 => descriptor_of nil 0 PackageSupplied PackageSupplied none_admits 0
  (* a node whose admission was recorded at the wrong time: package-supplied,
     and admitted at release time (O12) *)
  | 10 => descriptor_of nil 5 PackageSupplied BaseImage full_admits 0
  | _ => descriptor_of nil 0 BaseImage BaseImage none_admits 0
  end.

Definition short_node (k : nat) : nat :=
  at_member (cons 5 (cons 6 (cons 7 (cons 8 nil)))) k 0.

Definition demo_script (p : nat) : list Edge :=
  if Nat.eqb p 2 then cons e_scripted nil else nil.

Definition no_script (_ : nat) : list Edge := nil.

(* R-08-021's declared inter-level channels: one, from level 0 to level 1, so
   the template's last join crosses a level the composition declared and the
   crossing template's does not. *)
Definition demo_channel (a b : nat) : bool :=
  andb (Nat.eqb a 0) (Nat.eqb b 1).

(* R-12-024f's five classes over the demo's format space, assigned so that
   every class has a format on the inventory and a format off it: the
   inventory carries 0, 1 and 2, and the class cycles with period five, so
   the five formats at 5 through 9 are one per class and none of them is
   inventoried. That is what lets the exemption family below be decided at
   all five classes rather than at the two the spoiled edges happen to
   carry. Which formats an inventory holds is a composition (gap j); the
   cycle is a witness and carries no claim about a real inventory. *)
Definition demo_format_class (f : nat) : FormatClass :=
  at_member all_format_classes (Nat.modulo f 5) DocumentFormat.

Definition demo : Machine := {|
  package_count := 6;
  roster := demo_roster;
  descriptor := demo_descriptor;
  script := demo_script;
  type_count := 4;
  intent_count := 5;
  world_count := 2;
  in_inventory := fun f => Nat.ltb f 3;
  verified_parser := fun f => negb (Nat.eqb f 2);
  format_class := demo_format_class;
  node_pool_capacity := 4;
  ring_pool_capacity := 5;
  ring_depth_ceiling := 3;
  template_stages := demo_template;
  template_in := 0;
  template_out := 0;
  channel := demo_channel;
  ambiguity_admitted := false;
  graph_identity := 7
|}.

Definition demo_ambient : Ambient := {| amb_probe := 0; amb_clock := 0 |}.
Definition probing_ambient : Ambient := {| amb_probe := 1; amb_clock := 2 |}.

Definition demo_graph : Graph := spec_compose demo demo_ambient demo_roster.

(* The graph gap b is about: the composed one with a second admissible edge
   answering the intent the decode answers. *)
Definition ambiguous_graph : Graph := {|
  graph_nodes := demo_roster;
  graph_edges := app demo_graph.(graph_edges) (cons e_second_decode nil)
|}.

Definition intent_of (i n : nat) : Intent := {| int_index := i; int_name := n |}.

Definition request_of (i n b run content : nat) : Request := {|
  req_intent := intent_of i n;
  req_bound := b;
  req_run := run;
  req_content := content
|}.

(* A request whose bound sits exactly on the decode's declared limit, one
   whose bound is below the conversion's, one naming an intent no admitted
   edge answers, and the same first request under a different caller-supplied
   name. *)
Definition q_decode : Request := request_of 0 0 2 0 0.
Definition q_tight : Request := request_of 1 0 2 0 0.
Definition q_unknown : Request := request_of 4 0 9 0 0.
Definition q_sniffable : Request := request_of 4 0 9 0 1.
Definition q_named : Request := request_of 0 7 2 0 0.

(* A request naming no admitted edge whose bound sits exactly on one edge's
   declared limit. The specification refuses it, and the fallback selector
   reaches that edge, which is the boundary the fallback's own comparison
   turns on: without it a fallback that took only the edges strictly inside
   the bound would answer the same wherever this file looked. *)
Definition q_at_the_limit : Request := request_of 4 0 2 0 0.

Definition occ_empty : Occupancy := {| nodes_bound := 0; rings_bound := 0 |}.
Definition occ_ring_boundary : Occupancy := {| nodes_bound := 0; rings_bound := 1 |}.
Definition occ_node_full : Occupancy := {| nodes_bound := 1; rings_bound := 0 |}.
Definition occ_ring_full : Occupancy := {| nodes_bound := 0; rings_bound := 2 |}.

(* -------------------------------------------------------------------------
   The composed graph, and the twelve conjuncts decided from both sides.
   ------------------------------------------------------------------------- *)

Example the_composition_declares_sixteen_edges_and_admits_four :
  count_of (declared_edges demo demo_roster) = 16
  /\ count_of demo_graph.(graph_edges) = 4 := conj eq_refl eq_refl.

Example the_composed_graph_is_admissible_edge_by_edge :
  all_of (admissible_edge demo demo_roster) demo_graph.(graph_edges) = true
  /\ endpoints_inside demo_graph = true := conj eq_refl eq_refl.

Example the_specification_edge_breaks_no_conjunct :
  conjuncts_broken demo demo_roster e_decode = 0
  /\ admissible_edge demo demo_roster e_decode = true := conj eq_refl eq_refl.

(* Every spoiled edge is refused, and each breaks exactly one of the twelve,
   which is the check that no conjunct is dead. *)
Example every_spoiled_edge_is_refused :
  all_of (fun e => negb (admissible_edge demo demo_roster e)) spoiled_edges
  = true := eq_refl.

Example each_spoiled_edge_breaks_exactly_one_conjunct :
  map_over (conjuncts_broken demo demo_roster) spoiled_edges
  = cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1
    (cons 1 (cons 1 (cons 1 nil)))))))))))
  := eq_refl.

Theorem no_spoiled_edge_is_admissible :
  forall n : nat, Nat.ltb n 12 = true ->
    admissible_edge demo demo_roster (spoiled_at n) = false.
Proof.
  intros n.
  destruct n as [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* And from the composer's side: dropping any one of the twelve admits an
   edge the specification refuses, one more in every case, so no conjunct of
   the composer's own filter is dead either. *)
Example every_dropped_conjunct_admits_one_more_edge :
  map_over (fun k => count_of (compose_without k demo demo_ambient demo_roster).(graph_edges))
           (upto 12)
  = cons 5 (cons 5 (cons 5 (cons 5 (cons 5 (cons 5 (cons 5 (cons 5 (cons 5
    (cons 5 (cons 5 (cons 5 nil)))))))))))
  := eq_refl.

(* -------------------------------------------------------------------------
   O1, O2, O3: the composer's own three obligations, refuted.
   ------------------------------------------------------------------------- *)

Theorem the_discovering_composer_is_refuted :
  ~ ComposesFromDescriptorsAlone discovering_compose.
Proof.
  intros H. specialize (H demo demo_ambient probing_ambient demo_roster).
  apply (f_equal (fun g => count_of g.(graph_edges))) in H. discriminate H.
Qed.

Example the_discovering_composer_drops_the_graph_under_a_probe :
  count_of (discovering_compose demo probing_ambient demo_roster).(graph_edges) = 0
  /\ count_of (discovering_compose demo demo_ambient demo_roster).(graph_edges) = 4 :=
  conj eq_refl eq_refl.

Theorem the_executing_composer_runs_package_code :
  ~ ExecutesNoPackageCode executing_compose.
Proof.
  intros H. specialize (H demo no_script demo_ambient demo_roster).
  apply (f_equal (fun g => count_of g.(graph_edges))) in H. discriminate H.
Qed.

Example the_executing_composer_emits_the_edge_the_script_produced :
  count_of (executing_compose demo demo_ambient demo_roster).(graph_edges) = 5
  /\ count_of (executing_compose (with_script demo no_script) demo_ambient
                                 demo_roster).(graph_edges) = 4
  /\ admissible_edge demo demo_roster e_scripted = true :=
  conj eq_refl (conj eq_refl eq_refl).

Definition EmitsAFiniteClosedGraph (c : Composer) : Prop :=
  forall (m : Machine) (a : Ambient) (r : list nat), IsFiniteAndClosed r (c m a r).

Theorem the_trusting_composer_is_refuted :
  ~ EmitsAFiniteClosedGraph trusting_compose.
Proof.
  intros H. destruct (H demo demo_ambient demo_roster) as [ K _ ]. discriminate K.
Qed.

(* And it composes from the descriptors alone and executes no package code,
   so what refutes it is the stranger endpoint and not the shape of the
   construction. *)
Theorem the_trusting_composer_keeps_the_other_two_obligations :
  ComposesFromDescriptorsAlone trusting_compose
  /\ ExecutesNoPackageCode trusting_compose.
Proof.
  split; [ intros m a1 a2 r; reflexivity | intros m s a r; reflexivity ].
Qed.

Theorem the_limitless_composer_is_refuted :
  ~ (forall (m : Machine) (a : Ambient) (r : list nat),
       all_of (fun e => Nat.ltb 0 e.(edge_limit))
              (limitless_compose m a r).(graph_edges) = true).
Proof. intros H. specialize (H demo demo_ambient demo_roster). discriminate H. Qed.

Theorem the_widening_composer_is_refuted :
  ~ (forall (m : Machine) (a : Ambient) (r : list nat),
       all_of (fun e => Nat.leb e.(edge_bounds)
                                 (m.(descriptor) e.(edge_owner)).(desc_manifest))
              (widening_compose m a r).(graph_edges) = true).
Proof. intros H. specialize (H demo demo_ambient demo_roster). discriminate H. Qed.

Theorem the_uninventoried_composer_is_refuted :
  ~ (forall (m : Machine) (a : Ambient) (r : list nat),
       all_of (fun e => m.(in_inventory) e.(edge_format))
              (uninventoried_compose m a r).(graph_edges) = true).
Proof. intros H. specialize (H demo demo_ambient demo_roster). discriminate H. Qed.

Theorem the_unverified_composer_is_refuted :
  ~ (forall (m : Machine) (a : Ambient) (r : list nat),
       all_of (fun e => m.(verified_parser) e.(edge_format))
              (unverified_compose m a r).(graph_edges) = true).
Proof. intros H. specialize (H demo demo_ambient demo_roster). discriminate H. Qed.

Theorem the_ringless_composer_is_refuted :
  ~ (forall (m : Machine) (a : Ambient) (r : list nat),
       all_of (fun e => Nat.ltb 0 e.(edge_ring))
              (ringless_compose m a r).(graph_edges) = true).
Proof. intros H. specialize (H demo demo_ambient demo_roster). discriminate H. Qed.

Theorem the_deep_ring_composer_is_refuted :
  ~ (forall (m : Machine) (a : Ambient) (r : list nat),
       all_of (fun e => Nat.leb e.(edge_ring) m.(ring_depth_ceiling))
              (deep_ring_compose m a r).(graph_edges) = true).
Proof. intros H. specialize (H demo demo_ambient demo_roster). discriminate H. Qed.

Theorem the_worldless_composer_is_refuted :
  ~ (forall (m : Machine) (a : Ambient) (r : list nat),
       all_of (fun e => Nat.ltb e.(edge_world) m.(world_count))
              (worldless_compose m a r).(graph_edges) = true).
Proof. intros H. specialize (H demo demo_ambient demo_roster). discriminate H. Qed.

(* Each of the seven keeps the closure obligation except the one that drops
   it, so what refutes each is its own conjunct. The count in the name is the
   named members of `compose_without` other than the trusting one, and it
   moves when that list does. *)
Example the_seven_other_dropped_conjuncts_keep_the_graph_closed :
  endpoints_inside (limitless_compose demo demo_ambient demo_roster) = true
  /\ endpoints_inside (worldless_compose demo demo_ambient demo_roster) = true
  /\ endpoints_inside (widening_compose demo demo_ambient demo_roster) = true
  /\ endpoints_inside (uninventoried_compose demo demo_ambient demo_roster) = true
  /\ endpoints_inside (unverified_compose demo demo_ambient demo_roster) = true
  /\ endpoints_inside (ringless_compose demo demo_ambient demo_roster) = true
  /\ endpoints_inside (deep_ring_compose demo demo_ambient demo_roster) = true
  /\ endpoints_inside (trusting_compose demo demo_ambient demo_roster) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl)))))).

(* -------------------------------------------------------------------------
   O20: the five format classes, and the exemption refuted at each.
   ------------------------------------------------------------------------- *)

(* Each of the five edges carries the class the family names it for and a
   format the inventory does not hold, so the class assignment is read rather
   than assumed. *)
Example every_uninventoried_edge_carries_its_own_class :
  map_over (fun k => class_eqb (demo.(format_class) (uninventoried_edge k).(edge_format)) k)
           all_format_classes
  = cons true (cons true (cons true (cons true (cons true nil))))
  /\ map_over (fun e => demo.(in_inventory) e.(edge_format)) all_uninventoried_edges
     = cons false (cons false (cons false (cons false (cons false nil))))
  /\ map_over (fun e => demo.(verified_parser) e.(edge_format)) all_uninventoried_edges
     = cons true (cons true (cons true (cons true (cons true nil)))) :=
  conj eq_refl (conj eq_refl eq_refl).

(* Each breaks exactly the inventory conjunct, and the exemption at its own
   class admits it. Decided as one conversion across the whole family. *)
Example every_class_exemption_admits_the_edge_the_inventory_refuses :
  all_of (fun e => negb (admissible_edge demo demo_roster e))
         all_uninventoried_edges = true
  /\ map_over (conjuncts_broken demo demo_roster) all_uninventoried_edges
     = cons 1 (cons 1 (cons 1 (cons 1 (cons 1 nil))))
  /\ all_of (fun k => admits_class_exempt demo demo_roster k (uninventoried_edge k))
            all_format_classes = true := conj eq_refl (conj eq_refl eq_refl).

(* And the same content as a theorem quantified over the index, whose bound
   raised by one reaches the composed decode, which is admissible, so the
   first half fails there rather than holding wider. *)
Theorem no_format_class_may_be_exempted :
  forall n : nat, Nat.ltb n 5 = true ->
    admissible_edge demo demo_roster (uninventoried_at n) = false
    /\ exemption_at demo demo_roster n (uninventoried_at n) = true.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | n ] ] ] ] ];
    intros H; first [ split; reflexivity | discriminate H ].
Qed.

(* The obligation itself, refuted at two classes the demo's own declared
   edges reach: the archive-class format the inventory does not carry, and
   the font-class format that carries no verified parser. Each exempting
   composer still emits a closed graph, which is stated of an arbitrary
   machine above. *)
Theorem the_archive_exempting_composer_is_refuted :
  ~ ExemptsNoFormatClass (exempting_compose ArchiveFormat).
Proof.
  intros H. specialize (H demo demo_ambient demo_roster ArchiveFormat).
  discriminate H.
Qed.

Theorem the_font_exempting_composer_is_refuted :
  ~ ExemptsNoFormatClass (exempting_compose FontFormat).
Proof.
  intros H. specialize (H demo demo_ambient demo_roster FontFormat).
  discriminate H.
Qed.

Example each_exempting_composer_admits_what_its_class_carries :
  map_over (fun k => count_of (exempting_compose k demo demo_ambient
                                                 demo_roster).(graph_edges))
           all_format_classes
  = cons 4 (cons 4 (cons 5 (cons 5 (cons 4 nil))))
  /\ count_of demo_graph.(graph_edges) = 4 := conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   O4: the five amenders.
   ------------------------------------------------------------------------- *)

Example the_amenders_are_five : count_of all_amenders = 5 := eq_refl.

Example every_banned_mechanism_amends_the_running_graph :
  all_of (fun f => amends f demo_graph) all_amenders = true
  /\ amends no_amendment demo_graph = false := conj eq_refl eq_refl.

Theorem no_amender_in_the_family_leaves_the_graph_unamended :
  forall n : nat, Nat.ltb n 5 = true -> amends (amender_at n) demo_graph = true.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | n ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* Each of the five keeps the node set and the graph's closure, so what
   refuses it is R-12-024b's own clause and not a stranger endpoint. *)
Example every_amendment_keeps_the_graph_closed :
  all_of (fun f => all_of (fun n => mem_nat n demo_roster) (f demo_graph).(graph_nodes))
         all_amenders = true := eq_refl.

(* -------------------------------------------------------------------------
   O5: install and uninstall, and the observable difference.
   ------------------------------------------------------------------------- *)

Definition roster_before : list nat := cons 0 (cons 1 (cons 2 nil)).

Example the_roster_before_the_install_composes_two_edges :
  count_of (spec_compose demo demo_ambient roster_before).(graph_edges) = 2 := eq_refl.

Example the_install_recomposes_and_the_amendment_misses_an_edge :
  count_of (spec_install demo roster_before 3).(graph_edges) = 4
  /\ count_of (amending_install demo roster_before 3).(graph_edges) = 3
  /\ edges_into (spec_install demo roster_before 3) 3 = 1
  /\ edges_into (amending_install demo roster_before 3) 3 = 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem the_amending_install_is_not_a_recomposition :
  ~ IsRecomposition amending_install after_install.
Proof.
  intros H. specialize (H demo roster_before 3).
  apply (f_equal (fun g => count_of g.(graph_edges))) in H. discriminate H.
Qed.

(* And it emits the node set the recomposition emits, so what refutes it is
   the edge it missed and not a different roster. The uninstall side states
   the same thing below, and neither is a fact about the construction's
   shape: both installers write the resulting roster into the graph and the
   difference is entirely in the edge list. *)
Example the_amending_install_keeps_the_roster :
  (amending_install demo roster_before 3).(graph_nodes) = cons 3 roster_before
  /\ (spec_install demo roster_before 3).(graph_nodes) = cons 3 roster_before
  /\ count_of (amending_install demo roster_before 3).(graph_nodes) = 4
  /\ edges_into (spec_install demo roster_before 3) 3 = 1 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The uninstall difference, machine-checked rather than argued: the
   amendment that deletes only the departing package's own edges leaves an
   edge routing into a node the roster no longer carries, and the
   recomposition does not. *)
Theorem the_uninstall_extent_is_observable :
  edges_into (spec_uninstall demo demo_roster 3) 3 = 0
  /\ edges_into (amending_uninstall demo demo_roster 3) 3 = 1
  /\ count_of (spec_uninstall demo demo_roster 3).(graph_edges) = 2
  /\ count_of (amending_uninstall demo demo_roster 3).(graph_edges) = 3.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; reflexivity ] ].
Qed.

Theorem the_amending_uninstall_is_not_a_recomposition :
  ~ IsRecomposition amending_uninstall after_uninstall.
Proof.
  intros H. specialize (H demo demo_roster 3).
  apply (f_equal (fun g => count_of g.(graph_edges))) in H. discriminate H.
Qed.

(* And it keeps the node set the recomposition gives, so what refutes it is
   the edge it left behind and not a different roster. *)
Example the_amending_uninstall_keeps_the_roster :
  (amending_uninstall demo demo_roster 3).(graph_nodes) = roster_before
  /\ (spec_uninstall demo demo_roster 3).(graph_nodes) = roster_before :=
  conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   O6, O7, O8, O9a, O9b and O9c: the selection, and gap b exhibited.
   ------------------------------------------------------------------------- *)

Definition selected_owner (o : option Edge) : nat :=
  match o with None => 9 | Some e => e.(edge_owner) end.

Example a_refusal_names_no_owner :
  selected_owner (spec_select demo_graph q_unknown) = 9
  /\ selected_owner (last_match_select demo_graph q_unknown) = 9
  /\ selected_owner (spec_select demo_graph q_decode) = 0 :=
  conj eq_refl (conj eq_refl eq_refl).

(* The bound sitting exactly on the selected edge's declared limit, and one
   step below it: the boundary R-12-013a's resource limit names, read at
   selection (reading 5). *)
Example the_selection_admits_the_bound_it_sits_on :
  spec_select demo_graph q_decode = Some e_decode
  /\ spec_select demo_graph (with_bound q_decode 1) = None
  /\ spec_select demo_graph q_tight = None :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_selection_does_not_move_with_the_name_or_the_run :
  spec_select demo_graph q_named = Some e_decode
  /\ spec_select demo_graph (with_run q_decode 3) = Some e_decode
  /\ spec_select demo_graph (with_content q_decode 3) = Some e_decode :=
  conj eq_refl (conj eq_refl eq_refl).

(* Gap b, made checkable rather than asserted: two admissible edges answering
   one intent, on which the first-match and the last-match disciplines
   disagree; on a graph carrying one they agree. Both are deterministic and
   both keep every obligation, and no entry chooses. *)
Theorem the_ambiguity_is_observable :
  selected_owner (spec_select ambiguous_graph q_decode) = 0
  /\ selected_owner (last_match_select ambiguous_graph q_decode) = 2
  /\ selected_owner (spec_select demo_graph q_decode) = 0
  /\ selected_owner (last_match_select demo_graph q_decode) = 0.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; reflexivity ] ].
Qed.

Example the_ambiguous_graph_carries_one_more_edge :
  count_of ambiguous_graph.(graph_edges) = 5
  /\ admissible_edge demo demo_roster e_second_decode = true
  /\ demo.(ambiguity_admitted) = false := conj eq_refl (conj eq_refl eq_refl).

Theorem the_round_robin_selector_is_refuted :
  ~ DoesNotVaryWithTheRun round_robin_select.
Proof.
  intros H. specialize (H ambiguous_graph q_decode 1 0).
  apply (f_equal selected_owner) in H. discriminate H.
Qed.

Theorem the_name_reading_selector_is_refuted :
  ~ DoesNotReadTheName name_reading_select.
Proof.
  intros H. specialize (H ambiguous_graph q_decode 1 0).
  apply (f_equal selected_owner) in H. discriminate H.
Qed.

Theorem the_fallback_selector_is_refuted : ~ FailsClosed fallback_select.
Proof. intros H. specialize (H demo_graph q_unknown eq_refl). discriminate H. Qed.

(* What the fallback picks, and at the boundary its own comparison turns on:
   a request naming no admitted edge whose bound sits exactly on the decode's
   declared limit reaches the decode, where the specification refuses. A
   fallback taking only the edges strictly inside the bound would answer
   differently here and nowhere else this file looks. *)
Example the_fallback_selector_reaches_the_edge_the_bound_sits_on :
  spec_select demo_graph q_at_the_limit = None
  /\ fallback_select demo_graph q_at_the_limit = Some e_decode
  /\ fallback_select demo_graph q_unknown = Some e_decode
  /\ fallback_select demo_graph q_decode = Some e_decode :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem the_sniffing_selector_is_refuted : ~ FailsClosed sniffing_select.
Proof. intros H. specialize (H demo_graph q_sniffable eq_refl). discriminate H. Qed.

Theorem the_sniffing_selector_reads_the_content :
  ~ DoesNotSniffTheContent sniffing_select.
Proof.
  intros H. specialize (H demo_graph q_unknown 1 3).
  apply (f_equal selected_owner) in H. discriminate H.
Qed.

Theorem the_overrunning_selector_is_refuted :
  ~ RespectsTheRequestedBound overrunning_select.
Proof.
  intros H. specialize (H demo_graph q_tight e_convert eq_refl). discriminate H.
Qed.

Theorem the_widening_selector_is_refuted :
  ~ ReturnsOnlyAdmittedEdges demo demo_roster widening_select.
Proof.
  intros H.
  specialize (H demo_graph q_unknown (widened_edge q_unknown) eq_refl eq_refl).
  discriminate H.
Qed.

(* The monotonicity witnesses, computed rather than left in a hypothesis a
   weakening could pass by: raising the requested bound never takes the
   selection outside it and never leaves the graph, and the widening selector
   does both. *)
Example the_specification_stays_inside_every_bound :
  all_of (selects_inside spec_select demo_graph q_decode) (upto 8) = true
  /\ all_of (fun b => negb (widens demo demo_roster spec_select demo_graph
                                  q_decode b))
            (upto 8) = true := conj eq_refl eq_refl.

Example the_widening_selector_leaves_the_graph :
  widens demo demo_roster widening_select demo_graph q_unknown 9 = true
  /\ selects_inside widening_select demo_graph q_unknown 9 = true :=
  conj eq_refl eq_refl.

Example the_overrunning_selector_leaves_the_bound :
  selects_inside overrunning_select demo_graph q_tight 2 = false
  /\ selected_owner (overrunning_select demo_graph q_tight) = 1 :=
  conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   O21: the three forbidden introductions, refuted one per member.
   ------------------------------------------------------------------------- *)

Theorem the_worldless_composer_introduces_a_wire_protocol :
  ~ IntroducesNothing worldless_compose spec_select.
Proof.
  intros H. specialize (H demo demo_ambient demo_roster DesktopWireProtocol).
  simpl in H. discriminate H.
Qed.

Theorem the_name_reading_selector_introduces_an_open_ended_intent_string :
  ~ IntroducesNothing spec_compose name_reading_select.
Proof.
  intros H. specialize (H demo demo_ambient demo_roster OpenEndedIntentString).
  exact (the_name_reading_selector_is_refuted H).
Qed.

Theorem the_widening_composer_introduces_an_authority_bearing_path :
  ~ IntroducesNothing widening_compose spec_select.
Proof.
  intros H. specialize (H demo demo_ambient demo_roster AuthorityBearingPath).
  simpl in H. discriminate H.
Qed.

(* Each of the three keeps the other two, so what refutes each is the member
   it introduces. The two composer members are kept of an arbitrary machine
   above; the selector member is kept because the specification's own
   selector is the one the other two are stated with. *)
Example the_three_introducers_keep_the_two_they_do_not_break :
  all_of (fun e => Nat.leb e.(edge_bounds)
                           (demo.(descriptor) e.(edge_owner)).(desc_manifest))
         (worldless_compose demo demo_ambient demo_roster).(graph_edges) = true
  /\ all_of (fun e => Nat.ltb e.(edge_world) demo.(world_count))
            (widening_compose demo demo_ambient demo_roster).(graph_edges) = true
  /\ all_of (fun e => Nat.ltb e.(edge_world) demo.(world_count))
            demo_graph.(graph_edges) = true
  /\ all_of (fun e => Nat.leb e.(edge_bounds)
                              (demo.(descriptor) e.(edge_owner)).(desc_manifest))
            demo_graph.(graph_edges) = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   O11: the four quantities, and the four partial binders.
   ------------------------------------------------------------------------- *)

Example the_composed_nodes_are_admitted_and_the_short_ones_are_not :
  all_of (spec_may_bind demo) demo_roster = true
  /\ map_over (fun k => spec_may_bind demo (short_node k)) (upto 4)
     = cons false (cons false (cons false (cons false nil)))
  /\ spec_may_bind demo 9 = false := conj eq_refl (conj eq_refl eq_refl).

(* Each partial binder admits exactly the node whose missing quantity it
   stopped checking, and the specification refuses it. The conclusion is a
   conjunction of the two verdicts rather than one boolean, so a bound raised
   past the last index reaches the fallback and fails on the first half. *)
Theorem no_partial_binder_requires_every_quantity :
  forall k : nat, Nat.ltb k 4 = true ->
    spec_may_bind demo (short_node k) = false
    /\ partial_binder_at k demo (short_node k) = true.
Proof.
  intros k. destruct k as [ | [ | [ | [ | k ] ] ] ];
    intros H; first [ split; reflexivity | discriminate H ].
Qed.

Example each_partial_binder_admits_the_node_it_stopped_checking :
  map_over (fun k => partial_binder_at k demo (short_node k)) (upto 4)
  = cons true (cons true (cons true (cons true nil)))
  /\ map_over (fun k => partial_binder_at k demo 9) (upto 4)
     = cons false (cons false (cons false (cons false nil))) :=
  conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   O12: admission time by node origin.
   ------------------------------------------------------------------------- *)

Example the_composed_roster_is_admitted_at_the_time_its_origins_fix :
  all_of (admitted_at_its_origin_time demo) demo_roster = true
  /\ admitted_at_its_origin_time demo 10 = false := conj eq_refl eq_refl.

Example the_demo_origins :
  map_over (fun n => (demo.(descriptor) n).(desc_origin)) demo_roster
  = cons BaseImage (cons BaseImage (cons PackageSupplied (cons PackageSupplied nil)))
  /\ map_over (fun n => (demo.(descriptor) n).(desc_admitted_at)) demo_roster
     = cons BaseImage (cons BaseImage (cons PackageSupplied
       (cons PackageSupplied nil))) := conj eq_refl eq_refl.

Theorem the_release_time_schedule_is_refuted :
  ~ AdmitsAtTheTimeTheOriginFixes release_time_schedule.
Proof. intros H. specialize (H demo 3). discriminate H. Qed.

(* It agrees with the specification on every base-image node and touches no
   quantity, so what refutes it is the package-supplied half alone. *)
Example the_release_time_schedule_agrees_on_the_base_image_half :
  map_over (fun n => origin_eqb (release_time_schedule demo n)
                                (spec_schedule demo n)) demo_roster
  = cons true (cons true (cons false (cons false nil)))
  /\ all_of (spec_may_bind demo) demo_roster = true := conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   O13: the four forbidden creations.
   ------------------------------------------------------------------------- *)

Theorem no_creating_binder_creates_nothing :
  forall n : nat, Nat.ltb n 4 = true -> ~ CreatesNothing (creating_at n).
Proof.
  intros n. destruct n as [ | [ | [ | [ | n ] ] ] ];
    intros H K; first [ discriminate K | discriminate H ].
Qed.

Example each_creating_binder_creates_exactly_one :
  map_over (fun n => count_of (filter_of (creating_at n) all_forbidden_creations))
           (upto 4)
  = cons 1 (cons 1 (cons 1 (cons 1 nil)))
  /\ count_of (filter_of spec_creates all_forbidden_creations) = 0 :=
  conj eq_refl eq_refl.

(* The fourth creation is the binding-time half of boundedness, whose
   composition-time half is the ring conjuncts (reading 8): one binder
   creates an unbounded queue over a graph whose every declared depth is
   inside the ceiling, and one composer emits a zero-depth ring while no
   binding creates a queue. The two are not one clause stated twice. *)
Example the_two_halves_of_boundedness_are_independent :
  creating_at 3 CreatedUnboundedQueue = true
  /\ all_of (fun e => Nat.ltb 0 e.(edge_ring)) demo_graph.(graph_edges) = true
  /\ spec_creates CreatedUnboundedQueue = false
  /\ all_of (fun e => Nat.ltb 0 e.(edge_ring))
            (ringless_compose demo demo_ambient demo_roster).(graph_edges)
     = false := conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   O14: the two bounded pools and the typed verdict.
   ------------------------------------------------------------------------- *)

(* The occupancy sitting exactly on each pool's capacity binds, and one
   member past it declines: the boundary R-08-046's fixed capacity names. *)
Example the_pools_bind_at_their_capacity_and_decline_past_it :
  spec_bind demo occ_empty demo_template = Some Bound
  /\ spec_bind demo occ_ring_boundary demo_template = Some Bound
  /\ spec_bind demo occ_node_full demo_template
     = Some (CapacityExhausted NodePool)
  /\ spec_bind demo occ_ring_full demo_template
     = Some (CapacityExhausted RingPool) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_pool_occupancies_at_the_boundary :
  node_full demo occ_empty demo_template = false
  /\ node_full demo occ_node_full demo_template = true
  /\ ring_full demo occ_ring_boundary demo_template = false
  /\ ring_full demo occ_ring_full demo_template = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem the_blocking_binder_drops_the_request : ~ AlwaysAnswers blocking_bind.
Proof.
  intros H. specialize (H demo occ_node_full demo_template). discriminate H.
Qed.

Theorem the_growing_binder_overcommits : ~ DeclinesWhenFull growing_bind.
Proof.
  intros H. specialize (H demo occ_node_full demo_template eq_refl).
  discriminate H.
Qed.

Theorem the_borrowing_binder_borrows : ~ BorrowsNothing borrowing_bind.
Proof.
  intros H. destruct (H demo occ_node_full demo_template) as [ H1 _ ].
  specialize (H1 eq_refl). discriminate H1.
Qed.

(* The other direction of the same clause, refuted at the other pool: a
   binder that charges the node pool for a ring shortfall is the borrowing
   defect with the two pools exchanged, and the clause stated at one pool
   alone would admit it. It keeps the answer and the decline, exactly as its
   twin does. *)
Definition reverse_borrowing_bind : Binder := fun m occ t =>
  if node_full m occ t then Some (CapacityExhausted NodePool)
  else if ring_full m occ t then Some (CapacityExhausted NodePool)
  else Some Bound.

Theorem the_reverse_borrowing_binder_keeps_the_answer_and_the_decline :
  AlwaysAnswers reverse_borrowing_bind /\ DeclinesWhenFull reverse_borrowing_bind.
Proof.
  split.
  - intros m occ t. unfold reverse_borrowing_bind.
    destruct (node_full m occ t); [ reflexivity | ].
    destruct (ring_full m occ t); reflexivity.
  - intros m occ t H. unfold reverse_borrowing_bind. rewrite H. reflexivity.
Qed.

Theorem the_reverse_borrowing_binder_borrows :
  ~ BorrowsNothing reverse_borrowing_bind.
Proof.
  intros H. destruct (H demo occ_ring_full demo_template) as [ _ H2 ].
  specialize (H2 eq_refl). discriminate H2.
Qed.

Example the_four_binders_differ_only_where_a_pool_is_full :
  blocking_bind demo occ_node_full demo_template = None
  /\ growing_bind demo occ_node_full demo_template = Some Bound
  /\ borrowing_bind demo occ_node_full demo_template
     = Some (CapacityExhausted RingPool)
  /\ reverse_borrowing_bind demo occ_ring_full demo_template
     = Some (CapacityExhausted NodePool)
  /\ blocking_bind demo occ_empty demo_template = Some Bound
  /\ growing_bind demo occ_ring_full demo_template
     = Some (CapacityExhausted RingPool)
  /\ borrowing_bind demo occ_ring_full demo_template
     = Some (CapacityExhausted RingPool)
  /\ reverse_borrowing_bind demo occ_empty demo_template = Some Bound :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl)))))).

(* -------------------------------------------------------------------------
   O15, O17, O18, O19: the template and its generated weakenings.
   ------------------------------------------------------------------------- *)

Example the_composed_template_is_well_formed :
  template_ok demo demo_template = true
  /\ template_conjuncts_broken demo demo_template = 0
  /\ joins_broken demo_template = 0
  /\ labels_joined demo demo_template = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The empty chain's own floors, which nothing else below reaches: a chain
   with no join is vacuously typed and its labels vacuously join, and what
   refuses it is that it declares neither of the two ends the composition
   fixed. Stating them here is what makes the empty proper suffix a refusal
   for a reason rather than by three conjuncts happening to agree. *)
Example the_empty_chain_declares_no_ends :
  chain_typed nil = true
  /\ labels_joined demo nil = true
  /\ ends_match demo nil = false
  /\ last_out nil = 0
  /\ joins_broken nil = 0
  /\ template_ok demo nil = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Example the_four_refuting_templates_break_what_they_name :
  map_over (template_conjuncts_broken demo)
           (cons reserved_template (cons crossing_template
           (cons zero_ring_template (cons deep_ring_template nil))))
  = cons 2 (cons 1 (cons 1 (cons 1 nil)))
  /\ all_of (fun t => negb (template_ok demo t))
            (cons reserved_template (cons crossing_template
            (cons zero_ring_template (cons deep_ring_template nil)))) = true :=
  conj eq_refl eq_refl.

(* R-13-001b's pre-proved empty slot, as a construction: the reserved
   template names a node the roster does not carry and nothing has admitted,
   and it keeps the type chain, both ends, both ring conjuncts and the flow
   condition, so what refuses it is exactly that entry's own clause. *)
Example the_reserved_template_keeps_everything_but_the_slot :
  chain_typed reserved_template = true
  /\ ends_match demo reserved_template = true
  /\ labels_joined demo reserved_template = true
  /\ mem_nat 9 demo_roster = false
  /\ spec_may_bind demo 9 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* R-08-021's flow condition, as a construction: a chain whose one join goes
   from a level the composition labelled high to one it labelled low, with no
   inter-level channel declared for that direction. It keeps every other
   conjunct. *)
Example the_crossing_template_keeps_everything_but_the_flow :
  chain_typed crossing_template = true
  /\ ends_match demo crossing_template = true
  /\ labels_joined demo crossing_template = false
  /\ demo_channel 0 1 = true
  /\ demo_channel 1 0 = false
  /\ demo_channel 0 0 = false
  /\ demo_channel 1 1 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

Example the_two_ring_templates_sit_on_the_two_ring_boundaries :
  chain_typed zero_ring_template = true
  /\ chain_typed deep_ring_template = true
  /\ all_of (fun s => Nat.ltb 0 s.(stage_ring)) zero_ring_template = false
  /\ all_of (fun s => Nat.leb s.(stage_ring) demo.(ring_depth_ceiling))
            zero_ring_template = true
  /\ all_of (fun s => Nat.ltb 0 s.(stage_ring)) deep_ring_template = true
  /\ all_of (fun s => Nat.leb s.(stage_ring) demo.(ring_depth_ceiling))
            deep_ring_template = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* The four generated families, refused as one conversion. *)
Example the_generated_family_is_sixteen :
  count_of (generated_weakenings s_decode demo_template) = 16 := eq_refl.

Example every_generated_weakening_is_refused :
  all_of (fun w => negb (template_ok demo w))
         (generated_weakenings s_decode demo_template) = true := eq_refl.

(* And per family, with the conjunct each breaks computed rather than
   claimed. A transposition breaks two or three joins on a chain of four
   distinct types, a deletion breaks one join or none and is then refused at
   the ends, a proper suffix always misses the declared input, and a
   duplicated stage breaks a join except at the end, where it moves the
   declared output. *)
Example each_transposition_breaks_two_or_three_joins :
  map_over joins_broken (transpositions demo_template)
  = cons 2 (cons 3 (cons 2 nil)) := eq_refl.

Example each_deletion_breaks_a_join_or_moves_an_end :
  map_over joins_broken (deletions demo_template)
  = cons 0 (cons 1 (cons 1 (cons 0 nil)))
  /\ map_over (ends_match demo) (deletions demo_template)
     = cons false (cons true (cons true (cons false nil))) :=
  conj eq_refl eq_refl.

Example every_proper_suffix_misses_the_declared_input :
  map_over (ends_match demo) (proper_suffixes demo_template)
  = cons false (cons false (cons false (cons false nil))) := eq_refl.

Example each_duplicate_stage_breaks_a_join_or_moves_the_output :
  map_over joins_broken (duplicate_stages s_decode demo_template)
  = cons 1 (cons 1 (cons 2 (cons 2 (cons 0 nil))))
  /\ map_over (ends_match demo) (duplicate_stages s_decode demo_template)
     = cons true (cons true (cons true (cons true (cons false nil)))) :=
  conj eq_refl eq_refl.

(* The same content as theorems quantified over the index, each family read
   through `at_member` with the composed template as the fallback, so a bound
   raised by one reaches a template that is well-formed and the theorem fails
   rather than holding wider (reading 9). *)
Theorem no_transposition_is_a_well_formed_template :
  forall n : nat, Nat.ltb n 3 = true ->
    template_ok demo (at_member (transpositions demo_template) n demo_template)
    = false.
Proof.
  intros n. destruct n as [ | [ | [ | n ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_deletion_is_a_well_formed_template :
  forall n : nat, Nat.ltb n 4 = true ->
    template_ok demo (at_member (deletions demo_template) n demo_template)
    = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | n ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_proper_suffix_is_a_well_formed_template :
  forall n : nat, Nat.ltb n 4 = true ->
    template_ok demo (at_member (proper_suffixes demo_template) n demo_template)
    = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | n ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_duplicate_stage_is_a_well_formed_template :
  forall n : nat, Nat.ltb n 5 = true ->
    template_ok demo
      (at_member (duplicate_stages s_decode demo_template) n demo_template)
    = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | n ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* =========================================================================
   The demo's own pedigree ledger, and the figures no obligation reads.

   Gap j is what these figures are; this is where they are pinned. M6.2a
   measured the hazard and F-191 records it: a field no rule reads is a field
   a weakening moves in silence, and forty-six of that item's fifty-five
   seeded survivors were exactly such fields. So every field of every witness
   this file defines is stated in a conversion here, whether or not an
   obligation above happens to read it, and so is every magnitude the demo
   machine carries.
   ========================================================================= *)

Definition all_the_edges : list Edge :=
  cons e_decode (cons e_convert (cons e_mix (cons e_render (cons e_scripted
  (cons e_second_decode nil))))).

Example the_ledger_covers_six_authored_edges :
  count_of all_the_edges = 6 := eq_refl.

Example every_edge_declares_its_two_endpoints :
  map_over (fun e => e.(edge_owner)) all_the_edges
  = cons 0 (cons 1 (cons 1 (cons 3 (cons 2 (cons 2 nil)))))
  /\ map_over (fun e => e.(edge_target)) all_the_edges
     = cons 1 (cons 2 (cons 3 (cons 0 (cons 1 (cons 1 nil))))) :=
  conj eq_refl eq_refl.

Example every_edge_declares_its_intent_and_its_two_types :
  map_over (fun e => e.(edge_intent)) all_the_edges
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 0 nil)))))
  /\ map_over (fun e => e.(edge_from)) all_the_edges
     = cons 0 (cons 1 (cons 2 (cons 3 (cons 0 (cons 0 nil)))))
  /\ map_over (fun e => e.(edge_to)) all_the_edges
     = cons 1 (cons 2 (cons 3 (cons 0 (cons 1 (cons 1 nil))))) :=
  conj eq_refl (conj eq_refl eq_refl).

Example every_edge_declares_its_limit_and_its_world :
  map_over (fun e => e.(edge_limit)) all_the_edges
  = cons 2 (cons 3 (cons 4 (cons 2 (cons 2 (cons 2 nil)))))
  /\ map_over (fun e => e.(edge_world)) all_the_edges
     = cons 0 (cons 0 (cons 1 (cons 1 (cons 0 (cons 0 nil))))) :=
  conj eq_refl eq_refl.

Example every_edge_declares_its_format_its_bounds_and_its_ring :
  map_over (fun e => e.(edge_format)) all_the_edges
  = cons 0 (cons 1 (cons 1 (cons 1 (cons 0 (cons 0 nil)))))
  /\ map_over (fun e => e.(edge_bounds)) all_the_edges
     = cons 5 (cons 2 (cons 4 (cons 1 (cons 1 (cons 1 nil)))))
  /\ map_over (fun e => e.(edge_ring)) all_the_edges
     = cons 1 (cons 3 (cons 2 (cons 1 (cons 1 (cons 1 nil))))) :=
  conj eq_refl (conj eq_refl eq_refl).

(* The twelve spoilers carry no field of their own beyond the one each moves,
   the setters carrying the rest across from the decode, so the ledger owes
   twelve figures rather than a hundred and twenty. Each is the value sitting
   on its conjunct's own boundary, and the index beside it is which conjunct
   that is. *)
Example each_spoiler_moves_its_own_field_to_that_conjunct_s_boundary :
  (spoiled_at 0).(edge_owner) = 4
  /\ (spoiled_at 1).(edge_target) = 4
  /\ (spoiled_at 2).(edge_limit) = 0
  /\ (spoiled_at 3).(edge_intent) = 5
  /\ (spoiled_at 4).(edge_from) = 4
  /\ (spoiled_at 5).(edge_to) = 4
  /\ (spoiled_at 6).(edge_world) = 2
  /\ (spoiled_at 7).(edge_format) = 3
  /\ (spoiled_at 8).(edge_format) = 2
  /\ (spoiled_at 9).(edge_bounds) = 6
  /\ (spoiled_at 10).(edge_ring) = 0
  /\ (spoiled_at 11).(edge_ring) = 4 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl)))))))))).

(* And each carries the decode's own value everywhere else, which is what the
   setters make structural rather than asserted: the two the ledger reads are
   the two conjuncts every spoiler passes. *)
Example every_spoiler_keeps_the_decode_s_other_fields :
  all_of (fun e => Nat.eqb e.(edge_owner) e_decode.(edge_owner))
         (drop_at 0 spoiled_edges) = true
  /\ all_of (fun e => Nat.eqb e.(edge_ring) e_decode.(edge_ring))
            (drop_at 10 (drop_at 11 spoiled_edges)) = true :=
  conj eq_refl eq_refl.

(* The edge an amendment would add by each of the five routes. The route's own
   index is the only field that varies across the five, so the other seven are
   read at one witness rather than at five. *)
Example every_runtime_edge_carries_its_own_route_index :
  map_over mechanism_index all_banned_mechanisms
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil))))
  /\ map_over (fun b => (runtime_edge b).(edge_owner)) all_banned_mechanisms
     = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil))))
  /\ map_over (fun b => (runtime_edge b).(edge_target)) all_banned_mechanisms
     = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil))))
  /\ map_over (fun b => (runtime_edge b).(edge_intent)) all_banned_mechanisms
     = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil)))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_runtime_edge_carries_the_same_other_fields_by_every_route :
  (runtime_edge ContentSniffing).(edge_from) = 0
  /\ (runtime_edge ContentSniffing).(edge_to) = 0
  /\ (runtime_edge ContentSniffing).(edge_limit) = 1
  /\ (runtime_edge ContentSniffing).(edge_world) = 0
  /\ (runtime_edge ContentSniffing).(edge_format) = 0
  /\ (runtime_edge ContentSniffing).(edge_bounds) = 0
  /\ (runtime_edge ContentSniffing).(edge_ring) = 1
  /\ all_of (fun b => Nat.eqb (runtime_edge b).(edge_limit)
                              (runtime_edge ContentSniffing).(edge_limit))
            all_banned_mechanisms = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl)))))).

Example the_widened_edge_declares_the_bound_and_no_ring :
  (widened_edge q_unknown).(edge_owner) = 0
  /\ (widened_edge q_unknown).(edge_target) = 0
  /\ (widened_edge q_unknown).(edge_intent) = 4
  /\ (widened_edge q_unknown).(edge_from) = 0
  /\ (widened_edge q_unknown).(edge_to) = 0
  /\ (widened_edge q_unknown).(edge_limit) = 9
  /\ (widened_edge q_unknown).(edge_world) = 0
  /\ (widened_edge q_unknown).(edge_format) = 0
  /\ (widened_edge q_unknown).(edge_bounds) = 0
  /\ (widened_edge q_unknown).(edge_ring) = 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))))))).

(* Every stage of every template this file defines. *)
Definition all_the_stages : list Stage :=
  cons s_decode (cons s_convert (cons s_mix (cons s_render
  (cons s_cross_high (cons s_cross_low nil))))).

Example every_stage_declares_its_node_its_types_and_its_ring :
  map_over (fun s => s.(stage_node)) all_the_stages
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 3 (cons 0 nil)))))
  /\ map_over (fun s => s.(stage_in)) all_the_stages
     = cons 0 (cons 1 (cons 2 (cons 3 (cons 0 (cons 1 nil)))))
  /\ map_over (fun s => s.(stage_out)) all_the_stages
     = cons 1 (cons 2 (cons 3 (cons 0 (cons 1 (cons 0 nil)))))
  /\ map_over (fun s => s.(stage_ring)) all_the_stages
     = cons 1 (cons 3 (cons 2 (cons 1 (cons 1 (cons 1 nil))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The three stages derived from the decode by a setter carry one figure each
   and the decode's own values elsewhere. *)
Example every_derived_stage_moves_one_field :
  s_reserved.(stage_node) = 9
  /\ s_zero_ring.(stage_ring) = 0
  /\ s_deep_ring.(stage_ring) = 4
  /\ s_reserved.(stage_ring) = s_decode.(stage_ring)
  /\ s_zero_ring.(stage_node) = s_decode.(stage_node)
  /\ s_deep_ring.(stage_in) = s_decode.(stage_in) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* Every descriptor the demo machine carries, at every package identifier the
   file names and one past the last of them. *)
Definition all_the_packages : list nat := upto 12.

Example every_descriptor_declares_its_manifest_and_its_label :
  map_over (fun p => (demo.(descriptor) p).(desc_manifest)) all_the_packages
  = cons 5 (cons 4 (cons 4 (cons 3 (cons 5 (cons 5 (cons 5 (cons 5 (cons 5
    (cons 0 (cons 5 (cons 0 nil)))))))))))
  /\ map_over (fun p => (demo.(descriptor) p).(desc_label)) all_the_packages
     = cons 0 (cons 0 (cons 0 (cons 1 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0
       (cons 0 (cons 0 (cons 0 nil))))))))))) := conj eq_refl eq_refl.

Example every_descriptor_declares_its_edges_and_its_script :
  map_over (fun p => count_of (demo.(descriptor) p).(desc_edges)) all_the_packages
  = cons 13 (cons 2 (cons 0 (cons 1 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0
    (cons 0 (cons 0 (cons 0 nil)))))))))))
  /\ map_over (fun p => count_of (demo.(script) p)) all_the_packages
     = cons 0 (cons 0 (cons 1 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0
       (cons 0 (cons 0 (cons 0 nil))))))))))) := conj eq_refl eq_refl.

Example every_descriptor_declares_its_origin_and_its_admission_time :
  map_over (fun p => (demo.(descriptor) p).(desc_origin)) all_the_packages
  = cons BaseImage (cons BaseImage (cons PackageSupplied (cons PackageSupplied
    (cons PackageSupplied (cons BaseImage (cons BaseImage (cons BaseImage
    (cons BaseImage (cons PackageSupplied (cons PackageSupplied
    (cons BaseImage nil)))))))))))
  /\ map_over (fun p => (demo.(descriptor) p).(desc_admitted_at)) all_the_packages
     = cons BaseImage (cons BaseImage (cons PackageSupplied (cons PackageSupplied
       (cons PackageSupplied (cons BaseImage (cons BaseImage (cons BaseImage
       (cons BaseImage (cons PackageSupplied (cons BaseImage
       (cons BaseImage nil))))))))))) := conj eq_refl eq_refl.

Example every_descriptor_declares_which_quantities_are_admitted :
  map_over (fun p => all_of (demo.(descriptor) p).(desc_admits)
                            all_admitted_quantities) all_the_packages
  = cons true (cons true (cons true (cons true (cons true (cons false
    (cons false (cons false (cons false (cons false (cons true
    (cons false nil)))))))))))
  /\ map_over (fun p => count_of (filter_of (demo.(descriptor) p).(desc_admits)
                                            all_admitted_quantities))
              all_the_packages
     = cons 4 (cons 4 (cons 4 (cons 4 (cons 4 (cons 3 (cons 3 (cons 3 (cons 3
       (cons 0 (cons 4 (cons 0 nil))))))))))) := conj eq_refl eq_refl.

Example the_short_nodes_and_the_fallback_past_them :
  map_over short_node (upto 5) = cons 5 (cons 6 (cons 7 (cons 8 (cons 0 nil))))
  /\ spec_may_bind demo 0 = true := conj eq_refl eq_refl.

(* The wire-format inventory, its per-format verified-parser flag and its
   per-format class, at every format the file names and past the last of
   them. Which formats an inventory holds is a composition (gap j); that no
   class of the five is exempt from either flag is R-12-024f's, and O20 is
   where it is stated. *)
Example the_inventory_the_parser_flag_and_the_classes :
  map_over demo.(in_inventory) (upto 10)
  = cons true (cons true (cons true (cons false (cons false (cons false
    (cons false (cons false (cons false (cons false nil)))))))))
  /\ map_over demo.(verified_parser) (upto 10)
     = cons true (cons true (cons false (cons true (cons true (cons true
       (cons true (cons true (cons true (cons true nil)))))))))
  /\ map_over demo.(format_class) (upto 10)
     = cons ImageFormat (cons MediaFormat (cons FontFormat (cons ArchiveFormat
       (cons DocumentFormat (cons ImageFormat (cons MediaFormat (cons FontFormat
       (cons ArchiveFormat (cons DocumentFormat nil))))))))) :=
  conj eq_refl (conj eq_refl eq_refl).

(* The five edges the exemption family is decided at, each carrying one
   figure of its own: the format its class puts it at, and the decode's
   values everywhere else. *)
Example every_uninventoried_edge_moves_only_its_format :
  map_over (fun e => e.(edge_format)) all_uninventoried_edges
  = cons 5 (cons 6 (cons 7 (cons 8 (cons 9 nil))))
  /\ map_over class_index all_format_classes
     = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil))))
  /\ all_of (fun e => Nat.eqb e.(edge_owner) e_decode.(edge_owner))
            all_uninventoried_edges = true
  /\ all_of (fun e => Nat.eqb e.(edge_ring) e_decode.(edge_ring))
            all_uninventoried_edges = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* Every magnitude the demo machine fixes, computed rather than described, so
   that a figure edited on one side of the file and read on the other is a
   failed conversion instead of a silent disagreement. *)
Example the_demo_machine_declares :
  demo.(package_count) = 6
  /\ demo.(roster) = cons 0 (cons 1 (cons 2 (cons 3 nil)))
  /\ demo.(type_count) = 4
  /\ demo.(intent_count) = 5
  /\ demo.(world_count) = 2
  /\ demo.(node_pool_capacity) = 4
  /\ demo.(ring_pool_capacity) = 5
  /\ demo.(ring_depth_ceiling) = 3
  /\ demo.(template_in) = 0
  /\ demo.(template_out) = 0
  /\ demo.(ambiguity_admitted) = false
  /\ demo.(graph_identity) = 7 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl)))))))))).

Example the_demo_machine_carries_the_composed_template :
  demo.(template_stages) = demo_template
  /\ count_of demo.(template_stages) = 4
  /\ count_of demo.(roster) = 4 :=
  conj eq_refl (conj eq_refl eq_refl).

(* The two ambients, and the fields a composer could read and does not
   (reading 1). *)
Example the_three_ambients :
  demo_ambient.(amb_probe) = 0
  /\ demo_ambient.(amb_clock) = 0
  /\ probing_ambient.(amb_probe) = 1
  /\ probing_ambient.(amb_clock) = 2
  /\ composition_ambient.(amb_probe) = 0
  /\ composition_ambient.(amb_clock) = 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* The five requests, every field of each, including the caller-supplied name
   and the content bytes the specification never reads. *)
Definition all_the_requests : list Request :=
  cons q_decode (cons q_tight (cons q_unknown (cons q_sniffable
  (cons q_named (cons q_at_the_limit nil))))).

Example every_request_declares_its_intent_bound_run_and_content :
  map_over (fun q => q.(req_intent).(int_index)) all_the_requests
  = cons 0 (cons 1 (cons 4 (cons 4 (cons 0 (cons 4 nil)))))
  /\ map_over (fun q => q.(req_intent).(int_name)) all_the_requests
     = cons 0 (cons 0 (cons 0 (cons 0 (cons 7 (cons 0 nil)))))
  /\ map_over (fun q => q.(req_bound)) all_the_requests
     = cons 2 (cons 2 (cons 9 (cons 9 (cons 2 (cons 2 nil)))))
  /\ map_over (fun q => q.(req_run)) all_the_requests
     = cons 0 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0 nil)))))
  /\ map_over (fun q => q.(req_content)) all_the_requests
     = cons 0 (cons 0 (cons 0 (cons 1 (cons 0 (cons 0 nil))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* The four occupancies, each named for the boundary it sits on. *)
Definition all_the_occupancies : list Occupancy :=
  cons occ_empty (cons occ_ring_boundary (cons occ_node_full
  (cons occ_ring_full nil))).

Example every_occupancy_declares_both_pools :
  map_over (fun o => o.(nodes_bound)) all_the_occupancies
  = cons 0 (cons 0 (cons 1 (cons 0 nil)))
  /\ map_over (fun o => o.(rings_bound)) all_the_occupancies
     = cons 0 (cons 1 (cons 0 (cons 2 nil))) := conj eq_refl eq_refl.

(* The composed graph's own node set and the ambiguous graph's, so that the
   two differ in exactly the edge and not in the roster. *)
Example the_two_graphs_carry_one_node_set :
  demo_graph.(graph_nodes) = demo_roster
  /\ ambiguous_graph.(graph_nodes) = demo_roster
  /\ count_of demo_graph.(graph_nodes) = 4 :=
  conj eq_refl (conj eq_refl eq_refl).

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
Print Assumptions concat_of.
Print Assumptions upto.
Print Assumptions before_last.
Print Assumptions at_member.
Print Assumptions mem_nat.
Print Assumptions remove_nat.
Print Assumptions swap_at.
Print Assumptions drop_at.
Print Assumptions suffix_at.
Print Assumptions insert_at.
Print Assumptions find_of.
Print Assumptions find_last_of.
Print Assumptions is_some.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions nat_leb_refl.
Print Assumptions nat_eqb_refl.
Print Assumptions leb_trans.
Print Assumptions all_of_mono.
Print Assumptions all_of_filter_self.
Print Assumptions all_of_app.
Print Assumptions all_of_app_join.
Print Assumptions mem_nat_cons.
Print Assumptions all_of_mem_self.
Print Assumptions leb_split.
Print Assumptions all_of_upto.
Print Assumptions find_of_holds.
Print Assumptions find_of_in.
Print Assumptions find_of_none.
Print Assumptions find_last_of_holds.
Print Assumptions find_last_of_in.
Print Assumptions find_last_of_none.
Print Assumptions the_empty_conjunction_holds.
Print Assumptions the_empty_disjunction_fails.
Print Assumptions nothing_has_length_zero.
Print Assumptions the_empty_concatenation.
Print Assumptions before_last_of_nothing.
Print Assumptions the_index_set_of_three.
Print Assumptions nothing_is_a_member_of_nothing.
Print Assumptions a_member_is_found_and_a_stranger_is_not.
Print Assumptions removing_what_is_absent_changes_nothing.
Print Assumptions the_fallback_is_reached_past_the_last_index.
Print Assumptions nothing_is_found_in_nothing.
Print Assumptions the_first_and_the_last_differ_where_two_match.
Print Assumptions something_is_present_and_nothing_is_absent.
Print Assumptions all_banned_mechanisms.
Print Assumptions all_admitted_quantities.
Print Assumptions all_forbidden_creations.
Print Assumptions all_node_origins.
Print Assumptions all_pools.
Print Assumptions all_format_classes.
Print Assumptions all_forbidden_introductions.
Print Assumptions there_are_five_banned_mechanisms.
Print Assumptions there_are_four_admitted_quantities.
Print Assumptions there_are_four_forbidden_creations.
Print Assumptions there_are_two_node_origins.
Print Assumptions there_are_two_pools.
Print Assumptions there_are_five_format_classes.
Print Assumptions there_are_three_forbidden_introductions.
Print Assumptions mechanism_eqb.
Print Assumptions mechanism_eqb_refl.
Print Assumptions mechanism_eqb_true.
Print Assumptions quantity_eqb.
Print Assumptions quantity_eqb_refl.
Print Assumptions quantity_eqb_true.
Print Assumptions creation_eqb.
Print Assumptions creation_eqb_refl.
Print Assumptions creation_eqb_true.
Print Assumptions origin_eqb.
Print Assumptions origin_eqb_refl.
Print Assumptions origin_eqb_true.
Print Assumptions pool_eqb.
Print Assumptions pool_eqb_refl.
Print Assumptions pool_eqb_true.
Print Assumptions class_eqb.
Print Assumptions class_eqb_refl.
Print Assumptions class_eqb_true.
Print Assumptions introduction_eqb.
Print Assumptions introduction_eqb_refl.
Print Assumptions introduction_eqb_true.
Print Assumptions the_mechanisms_are_pairwise_distinct.
Print Assumptions the_quantities_are_pairwise_distinct.
Print Assumptions the_creations_are_pairwise_distinct.
Print Assumptions the_origins_are_distinct.
Print Assumptions the_pools_are_distinct.
Print Assumptions the_format_classes_are_pairwise_distinct.
Print Assumptions the_forbidden_introductions_are_pairwise_distinct.
Print Assumptions with_script.
Print Assumptions with_script_changes_nothing_else.
Print Assumptions edge_conjuncts.
Print Assumptions admissible_edge.
Print Assumptions conjuncts_broken.
Print Assumptions there_are_twelve_conjuncts.
Print Assumptions admissible_owner_on_roster.
Print Assumptions admissible_target_on_roster.
Print Assumptions admissible_declares_a_limit.
Print Assumptions admissible_world_is_declared.
Print Assumptions admissible_format_is_inventoried.
Print Assumptions admissible_format_has_a_verified_parser.
Print Assumptions admissible_bounds_inside_the_manifest.
Print Assumptions admissible_ring_is_inside_the_ceiling.
Print Assumptions Composer.
Print Assumptions declared_edges.
Print Assumptions scripted_edges.
Print Assumptions spec_compose.
Print Assumptions ComposesFromDescriptorsAlone.
Print Assumptions the_specification_composes_from_descriptors_alone.
Print Assumptions ExecutesNoPackageCode.
Print Assumptions the_specification_executes_no_package_code.
Print Assumptions endpoints_inside.
Print Assumptions IsFiniteAndClosed.
Print Assumptions the_specification_emits_a_finite_closed_graph.
Print Assumptions the_specification_emits_admissible_edges_only.
Print Assumptions every_composed_edge_declares_a_resource_limit.
Print Assumptions every_composed_edge_declares_an_interface_world.
Print Assumptions the_specification_never_widens_a_manifest.
Print Assumptions every_parsed_format_is_inventoried_and_verified.
Print Assumptions every_composed_ring_is_inside_the_ceiling.
Print Assumptions ExemptsNoFormatClass.
Print Assumptions the_specification_exempts_no_format_class.
Print Assumptions compose_without.
Print Assumptions trusting_compose.
Print Assumptions limitless_compose.
Print Assumptions worldless_compose.
Print Assumptions widening_compose.
Print Assumptions uninventoried_compose.
Print Assumptions unverified_compose.
Print Assumptions ringless_compose.
Print Assumptions deep_ring_compose.
Print Assumptions admits_class_exempt.
Print Assumptions exempting_compose.
Print Assumptions all_class_exemptions.
Print Assumptions exemption_at.
Print Assumptions the_class_exemptions_are_five.
Print Assumptions class_exempt_owner_on_roster.
Print Assumptions class_exempt_target_on_roster.
Print Assumptions every_exempting_composer_still_emits_a_closed_graph.
Print Assumptions discovering_compose.
Print Assumptions executing_compose.
Print Assumptions the_discovering_composer_still_emits_a_closed_graph.
Print Assumptions the_executing_composer_still_emits_a_closed_graph.
Print Assumptions the_discovering_composer_executes_no_package_code.
Print Assumptions the_executing_composer_composes_from_descriptors_alone.
Print Assumptions the_discovering_composer_agrees_where_it_observes_nothing.
Print Assumptions Amender.
Print Assumptions no_amendment.
Print Assumptions NeverAmendsARunningGraph.
Print Assumptions the_specification_never_amends_a_running_graph.
Print Assumptions mechanism_index.
Print Assumptions runtime_edge.
Print Assumptions amend_by.
Print Assumptions all_amenders.
Print Assumptions amender_at.
Print Assumptions amends.
Print Assumptions no_amender_leaves_the_graph_unamended.
Print Assumptions every_amendment_keeps_the_node_set.
Print Assumptions Installer.
Print Assumptions after_install.
Print Assumptions after_uninstall.
Print Assumptions composition_ambient.
Print Assumptions spec_install.
Print Assumptions spec_uninstall.
Print Assumptions IsRecomposition.
Print Assumptions the_specification_install_is_a_recomposition.
Print Assumptions the_specification_uninstall_is_a_recomposition.
Print Assumptions amending_install.
Print Assumptions amending_uninstall.
Print Assumptions edges_into.
Print Assumptions Selector.
Print Assumptions matches.
Print Assumptions spec_select.
Print Assumptions with_run.
Print Assumptions with_name.
Print Assumptions with_bound.
Print Assumptions with_content.
Print Assumptions DoesNotVaryWithTheRun.
Print Assumptions DoesNotReadTheName.
Print Assumptions DoesNotSniffTheContent.
Print Assumptions the_specification_selection_does_not_vary_with_the_run.
Print Assumptions the_specification_selection_does_not_read_the_name.
Print Assumptions the_specification_selection_does_not_sniff_the_content.
Print Assumptions RespectsTheRequestedBound.
Print Assumptions the_specification_respects_the_requested_bound.
Print Assumptions AnswersTheRequestedIntent.
Print Assumptions the_specification_answers_the_requested_intent.
Print Assumptions ReturnsOnlyAdmittedEdges.
Print Assumptions the_specification_returns_only_admitted_edges.
Print Assumptions an_edge_inside_a_bound_is_inside_every_wider_one.
Print Assumptions FailsClosed.
Print Assumptions the_specification_fails_closed.
Print Assumptions IntroducesNothing.
Print Assumptions the_specification_introduces_nothing.
Print Assumptions dropping_the_world_keeps_the_manifest.
Print Assumptions dropping_the_manifest_keeps_the_world.
Print Assumptions the_worldless_composer_keeps_the_manifest_clause.
Print Assumptions the_widening_composer_keeps_the_world_clause.
Print Assumptions last_match_select.
Print Assumptions round_robin_select.
Print Assumptions name_reading_select.
Print Assumptions fallback_select.
Print Assumptions sniffing_select.
Print Assumptions overrunning_select.
Print Assumptions widened_edge.
Print Assumptions widening_select.
Print Assumptions the_last_match_selector_keeps_every_selection_obligation.
Print Assumptions the_last_match_selector_returns_only_admitted_edges.
Print Assumptions the_round_robin_selector_keeps_the_name_and_the_content.
Print Assumptions the_name_reading_selector_keeps_the_run_and_the_content.
Print Assumptions the_fallback_selector_keeps_the_run_the_name_and_the_content.
Print Assumptions the_sniffing_selector_keeps_the_run_and_the_name.
Print Assumptions the_overrunning_selector_answers_the_requested_intent.
Print Assumptions the_overrunning_selector_returns_only_admitted_edges.
Print Assumptions the_widening_selector_keeps_the_requested_bound.
Print Assumptions selects_inside.
Print Assumptions widens.
Print Assumptions all_of_head_false.
Print Assumptions all_of_tail_false.
Print Assumptions MayBind.
Print Assumptions spec_may_bind.
Print Assumptions RequiresEveryQuantity.
Print Assumptions the_specification_requires_every_quantity.
Print Assumptions binder_without.
Print Assumptions all_partial_binders.
Print Assumptions partial_binder_at.
Print Assumptions the_partial_binders_are_four.
Print Assumptions quantities_required.
Print Assumptions each_partial_binder_still_requires_three.
Print Assumptions dropping_past_the_last_quantity_drops_nothing.
Print Assumptions Schedule.
Print Assumptions spec_schedule.
Print Assumptions AdmitsAtTheTimeTheOriginFixes.
Print Assumptions the_specification_admits_at_the_time_the_origin_fixes.
Print Assumptions recorded_schedule.
Print Assumptions admitted_at_its_origin_time.
Print Assumptions release_time_schedule.
Print Assumptions the_release_time_schedule_agrees_on_every_base_image_node.
Print Assumptions Creation.
Print Assumptions spec_creates.
Print Assumptions CreatesNothing.
Print Assumptions the_specification_binding_creates_nothing.
Print Assumptions all_creating_binders.
Print Assumptions creating_at.
Print Assumptions the_creating_binders_are_four.
Print Assumptions Binder.
Print Assumptions node_full.
Print Assumptions ring_full.
Print Assumptions spec_bind.
Print Assumptions is_bound.
Print Assumptions AlwaysAnswers.
Print Assumptions DeclinesWhenFull.
Print Assumptions BorrowsNothing.
Print Assumptions the_specification_binder_always_answers.
Print Assumptions the_specification_binder_declines_when_full.
Print Assumptions the_specification_binder_borrows_nothing.
Print Assumptions blocking_bind.
Print Assumptions growing_bind.
Print Assumptions borrowing_bind.
Print Assumptions the_blocking_binder_keeps_the_decline_and_the_borrowing_clause.
Print Assumptions the_growing_binder_keeps_the_answer_and_the_borrowing_clause.
Print Assumptions the_borrowing_binder_keeps_the_answer_and_the_decline.
Print Assumptions chain_typed.
Print Assumptions last_out.
Print Assumptions ends_match.
Print Assumptions joins_broken.
Print Assumptions stage_label.
Print Assumptions labels_joined.
Print Assumptions template_conjuncts.
Print Assumptions template_ok.
Print Assumptions template_conjuncts_broken.
Print Assumptions there_are_seven_template_conjuncts.
Print Assumptions a_well_formed_template_is_a_typed_chain.
Print Assumptions a_well_formed_template_binds_composed_admitted_nodes.
Print Assumptions a_well_formed_template_declares_bounded_rings.
Print Assumptions a_well_formed_template_crosses_no_undeclared_label.
Print Assumptions transpositions.
Print Assumptions deletions.
Print Assumptions proper_suffixes.
Print Assumptions duplicate_stages.
Print Assumptions generated_weakenings.
Print Assumptions edge_of.
Print Assumptions stage_of.
Print Assumptions descriptor_of.
Print Assumptions full_admits.
Print Assumptions none_admits.
Print Assumptions all_but.
Print Assumptions e_decode.
Print Assumptions e_convert.
Print Assumptions e_mix.
Print Assumptions e_render.
Print Assumptions e_scripted.
Print Assumptions e_second_decode.
Print Assumptions set_owner.
Print Assumptions set_target.
Print Assumptions set_intent.
Print Assumptions set_from.
Print Assumptions set_to.
Print Assumptions set_limit.
Print Assumptions set_world.
Print Assumptions set_format.
Print Assumptions set_bounds.
Print Assumptions set_ring.
Print Assumptions spoiled_edges.
Print Assumptions spoiled_at.
Print Assumptions the_spoiled_edges_are_twelve.
Print Assumptions class_index.
Print Assumptions uninventoried_edge.
Print Assumptions all_uninventoried_edges.
Print Assumptions uninventoried_at.
Print Assumptions the_uninventoried_edges_are_five.
Print Assumptions s_decode.
Print Assumptions s_convert.
Print Assumptions s_mix.
Print Assumptions s_render.
Print Assumptions demo_template.
Print Assumptions set_stage_node.
Print Assumptions set_stage_ring.
Print Assumptions s_reserved.
Print Assumptions s_cross_high.
Print Assumptions s_cross_low.
Print Assumptions s_zero_ring.
Print Assumptions s_deep_ring.
Print Assumptions reserved_template.
Print Assumptions crossing_template.
Print Assumptions zero_ring_template.
Print Assumptions deep_ring_template.
Print Assumptions demo_roster.
Print Assumptions demo_descriptor.
Print Assumptions short_node.
Print Assumptions demo_script.
Print Assumptions no_script.
Print Assumptions demo_channel.
Print Assumptions demo_format_class.
Print Assumptions demo.
Print Assumptions demo_ambient.
Print Assumptions probing_ambient.
Print Assumptions demo_graph.
Print Assumptions ambiguous_graph.
Print Assumptions intent_of.
Print Assumptions request_of.
Print Assumptions q_decode.
Print Assumptions q_tight.
Print Assumptions q_unknown.
Print Assumptions q_sniffable.
Print Assumptions q_named.
Print Assumptions q_at_the_limit.
Print Assumptions occ_empty.
Print Assumptions occ_ring_boundary.
Print Assumptions occ_node_full.
Print Assumptions occ_ring_full.
Print Assumptions the_composition_declares_sixteen_edges_and_admits_four.
Print Assumptions the_composed_graph_is_admissible_edge_by_edge.
Print Assumptions the_specification_edge_breaks_no_conjunct.
Print Assumptions every_spoiled_edge_is_refused.
Print Assumptions each_spoiled_edge_breaks_exactly_one_conjunct.
Print Assumptions no_spoiled_edge_is_admissible.
Print Assumptions every_dropped_conjunct_admits_one_more_edge.
Print Assumptions the_discovering_composer_is_refuted.
Print Assumptions the_discovering_composer_drops_the_graph_under_a_probe.
Print Assumptions the_executing_composer_runs_package_code.
Print Assumptions the_executing_composer_emits_the_edge_the_script_produced.
Print Assumptions EmitsAFiniteClosedGraph.
Print Assumptions the_trusting_composer_is_refuted.
Print Assumptions the_trusting_composer_keeps_the_other_two_obligations.
Print Assumptions the_limitless_composer_is_refuted.
Print Assumptions the_widening_composer_is_refuted.
Print Assumptions the_uninventoried_composer_is_refuted.
Print Assumptions the_unverified_composer_is_refuted.
Print Assumptions the_ringless_composer_is_refuted.
Print Assumptions the_deep_ring_composer_is_refuted.
Print Assumptions the_worldless_composer_is_refuted.
Print Assumptions the_seven_other_dropped_conjuncts_keep_the_graph_closed.
Print Assumptions every_uninventoried_edge_carries_its_own_class.
Print Assumptions every_class_exemption_admits_the_edge_the_inventory_refuses.
Print Assumptions no_format_class_may_be_exempted.
Print Assumptions the_archive_exempting_composer_is_refuted.
Print Assumptions the_font_exempting_composer_is_refuted.
Print Assumptions each_exempting_composer_admits_what_its_class_carries.
Print Assumptions the_amenders_are_five.
Print Assumptions every_banned_mechanism_amends_the_running_graph.
Print Assumptions no_amender_in_the_family_leaves_the_graph_unamended.
Print Assumptions every_amendment_keeps_the_graph_closed.
Print Assumptions roster_before.
Print Assumptions the_roster_before_the_install_composes_two_edges.
Print Assumptions the_install_recomposes_and_the_amendment_misses_an_edge.
Print Assumptions the_amending_install_is_not_a_recomposition.
Print Assumptions the_amending_install_keeps_the_roster.
Print Assumptions the_uninstall_extent_is_observable.
Print Assumptions the_amending_uninstall_is_not_a_recomposition.
Print Assumptions the_amending_uninstall_keeps_the_roster.
Print Assumptions selected_owner.
Print Assumptions a_refusal_names_no_owner.
Print Assumptions the_selection_admits_the_bound_it_sits_on.
Print Assumptions the_selection_does_not_move_with_the_name_or_the_run.
Print Assumptions the_ambiguity_is_observable.
Print Assumptions the_ambiguous_graph_carries_one_more_edge.
Print Assumptions the_round_robin_selector_is_refuted.
Print Assumptions the_name_reading_selector_is_refuted.
Print Assumptions the_fallback_selector_is_refuted.
Print Assumptions the_fallback_selector_reaches_the_edge_the_bound_sits_on.
Print Assumptions the_sniffing_selector_is_refuted.
Print Assumptions the_sniffing_selector_reads_the_content.
Print Assumptions the_overrunning_selector_is_refuted.
Print Assumptions the_widening_selector_is_refuted.
Print Assumptions the_specification_stays_inside_every_bound.
Print Assumptions the_widening_selector_leaves_the_graph.
Print Assumptions the_overrunning_selector_leaves_the_bound.
Print Assumptions the_worldless_composer_introduces_a_wire_protocol.
Print Assumptions the_name_reading_selector_introduces_an_open_ended_intent_string.
Print Assumptions the_widening_composer_introduces_an_authority_bearing_path.
Print Assumptions the_three_introducers_keep_the_two_they_do_not_break.
Print Assumptions the_composed_nodes_are_admitted_and_the_short_ones_are_not.
Print Assumptions no_partial_binder_requires_every_quantity.
Print Assumptions each_partial_binder_admits_the_node_it_stopped_checking.
Print Assumptions the_composed_roster_is_admitted_at_the_time_its_origins_fix.
Print Assumptions the_demo_origins.
Print Assumptions the_release_time_schedule_is_refuted.
Print Assumptions the_release_time_schedule_agrees_on_the_base_image_half.
Print Assumptions no_creating_binder_creates_nothing.
Print Assumptions each_creating_binder_creates_exactly_one.
Print Assumptions the_two_halves_of_boundedness_are_independent.
Print Assumptions the_pools_bind_at_their_capacity_and_decline_past_it.
Print Assumptions the_pool_occupancies_at_the_boundary.
Print Assumptions the_blocking_binder_drops_the_request.
Print Assumptions the_growing_binder_overcommits.
Print Assumptions the_borrowing_binder_borrows.
Print Assumptions reverse_borrowing_bind.
Print Assumptions the_reverse_borrowing_binder_keeps_the_answer_and_the_decline.
Print Assumptions the_reverse_borrowing_binder_borrows.
Print Assumptions the_four_binders_differ_only_where_a_pool_is_full.
Print Assumptions the_composed_template_is_well_formed.
Print Assumptions the_empty_chain_declares_no_ends.
Print Assumptions the_four_refuting_templates_break_what_they_name.
Print Assumptions the_reserved_template_keeps_everything_but_the_slot.
Print Assumptions the_crossing_template_keeps_everything_but_the_flow.
Print Assumptions the_two_ring_templates_sit_on_the_two_ring_boundaries.
Print Assumptions the_generated_family_is_sixteen.
Print Assumptions every_generated_weakening_is_refused.
Print Assumptions each_transposition_breaks_two_or_three_joins.
Print Assumptions each_deletion_breaks_a_join_or_moves_an_end.
Print Assumptions every_proper_suffix_misses_the_declared_input.
Print Assumptions each_duplicate_stage_breaks_a_join_or_moves_the_output.
Print Assumptions no_transposition_is_a_well_formed_template.
Print Assumptions no_deletion_is_a_well_formed_template.
Print Assumptions no_proper_suffix_is_a_well_formed_template.
Print Assumptions no_duplicate_stage_is_a_well_formed_template.
Print Assumptions all_the_edges.
Print Assumptions the_ledger_covers_six_authored_edges.
Print Assumptions every_edge_declares_its_two_endpoints.
Print Assumptions every_edge_declares_its_intent_and_its_two_types.
Print Assumptions every_edge_declares_its_limit_and_its_world.
Print Assumptions every_edge_declares_its_format_its_bounds_and_its_ring.
Print Assumptions each_spoiler_moves_its_own_field_to_that_conjunct_s_boundary.
Print Assumptions every_spoiler_keeps_the_decode_s_other_fields.
Print Assumptions every_runtime_edge_carries_its_own_route_index.
Print Assumptions the_runtime_edge_carries_the_same_other_fields_by_every_route.
Print Assumptions the_widened_edge_declares_the_bound_and_no_ring.
Print Assumptions all_the_stages.
Print Assumptions every_stage_declares_its_node_its_types_and_its_ring.
Print Assumptions every_derived_stage_moves_one_field.
Print Assumptions all_the_packages.
Print Assumptions every_descriptor_declares_its_manifest_and_its_label.
Print Assumptions every_descriptor_declares_its_edges_and_its_script.
Print Assumptions every_descriptor_declares_its_origin_and_its_admission_time.
Print Assumptions every_descriptor_declares_which_quantities_are_admitted.
Print Assumptions the_short_nodes_and_the_fallback_past_them.
Print Assumptions the_inventory_the_parser_flag_and_the_classes.
Print Assumptions every_uninventoried_edge_moves_only_its_format.
Print Assumptions the_demo_machine_declares.
Print Assumptions the_demo_machine_carries_the_composed_template.
Print Assumptions the_three_ambients.
Print Assumptions all_the_requests.
Print Assumptions every_request_declares_its_intent_bound_run_and_content.
Print Assumptions all_the_occupancies.
Print Assumptions every_occupancy_declares_both_pools.
Print Assumptions the_two_graphs_carry_one_node_set.
