(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   AdmissionPath.v

   The composition-time admission path, as the register fixes it: R-13-001c's
   composer, an untrusted producer off-device with the rest of the certifying
   toolchain, joining no trust base and free to be any party, whose output
   fails admission rather than shipping; R-13-013's artifact-not-pedigree,
   under which no admission rule reads a producer identity; R-06-008's
   stratification, the CHERI-TAL type-checker running over typing derivations
   and the CIC kernel elsewhere; R-06-009's decided set, read off R-05-029's
   eleven type-level obligations rather than enumerated again; R-05-036's
   three checker moves with R-05-037, R-05-038 and R-05-039 assigning one to
   each facet of those eleven; R-06-015b's checker authority, read over the
   candidate artifact, its certificate and the profile, and write over one
   verdict record; R-13-011's three assurance tiers, each artifact carrying
   exactly one and its required evidence, with R-13-012 scoping the Tier-2
   subset; R-13-003's named certificate parts and R-13-022's gate on the
   derivation rather than on the toolchain; R-11-005's generation-scoped
   proofs against the spec-set and Sail-model versions, with R-05-135b's
   pinned language specification and profile beside them, so revving any of
   them forces re-admission; R-11-005's commit-only-after-validation, which
   makes a generation atomic; R-13-010a and R-13-010b's whole-image passes,
   which emit new bytes and owe a derivation covering them; R-13-014's
   refuse-uncertified-code polarity and R-13-025's admission gate that never
   relaxes enforcement; and R-17-033's completeness polarity, which books an
   incomplete checker as a delivery failure and an unsound one as a safety
   breach. The order the phases run in is TAL-074's, in the typed assembly
   language R-05-135a pins.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. Every quantity a composition
   fixes is a field of the Machine record rather than a literal or a top-level
   Parameter, which is what keeps the R-05-163 assumption gate green while
   leaving the decision where its owner can make it. Nothing is admitted and
   nothing is axiomatized: the Print Assumptions block at the end reports every
   shipped constant closed under the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. No constant here is compiled,
   lowered, or run on either emulator, and nothing here executes anywhere. No
   artifact is decoded, no instruction is typed, no hash is computed, and
   nothing below is the checker R-06-015d owes a refinement for. The computed
   checks are decided inside the kernel by conversion and print nothing.

   Which half of M6.2a's cell each part answers. The cell has two clauses.
   *The packages it checks the golden-model components themselves* is the
   roster: `golden_roster` below is the plan's sections 2 through 8 named as
   component identities, the Root-of-Trust firmware, the M-mode firmware, the
   crypto core, the kernel, the object system and its transactor, the
   filesystem, and the init system's supervision tree. The plan's section 9
   names two more components and they are deliberately not roster members:
   R-06-014 makes the two checkers exactly the admitters no admission
   certificate covers, so a roster naming them would be claiming the one thing
   that entry refuses. *Their derivations thin until the Tier-0/1/2 proofs
   exist* is the carrier: a derivation here is a list of discharge records and
   carries no proof term at all, which is what thin means at this carrier, and
   `Terse` is the carrier whose every value reads as a certificate with no
   record whatever. What a component's identifier, tier, producer and
   attestation are is a witness value gap g records; what the roster *is* is
   the cell's.

   What is deferred, and to which item. M6.2 was split at entry on the ruling
   that measured boot covers a statically composed image and the device does
   not re-admit it, so admission of a composed image is an offline act and the
   device verifies a signature. **M6.2b owns the on-device CIC kernel**, and
   nothing below is a proof term, a reduction, a conversion check, or a term
   language: the derivation carrier here is arbitrary precisely so that the
   proof language M6.2b refines is not chosen by this file. **M6.2b also owns
   the CompCert-C refinement**, so no line below is a program, and R-06-015d's
   `CJ-ADMIT-IMPL` obligation, that a shipped evaluator accepts exactly where
   the pinned language's rule table does, is stated of nothing here. What is
   here is the composition-time act: a checker over a package and its
   derivation, and a composer that turns a roster into a generation or into
   nothing.

   No Require. Nothing beyond the Rocq prelude is reachable, so Classical and
   FunctionalExtensionality are unavailable and every equality below is stated
   pointwise or over a decidable boolean for that reason. A Require naming a
   sibling artifact in proofs/ would be admissible, and there is none to name:
   SupervisionTree.v's roster is R-10-026's signed generation read at bring-up
   rather than at composition, MModeFirmware.v's build-time check is a
   property of the booted machine, and neither meets a package, a derivation
   or a verdict. A Require here would be a citation rather than a dependency.

   Readings of the register this statement takes, each a reviewable judgment
   rather than a neutral transcription:

   1. Admission is a predicate over a package and its derivation, and the
      composer's ambient state is a parameter it must not read. R-06-015b
      makes a checker's read authority exactly the candidate artifact, its
      certificate and the profile, and R-13-001c puts the composer outside
      every trust base, so `Ambient` below is what a composer is carrying and
      the obligation is that the verdict does not vary with it. The
      specification's checker takes the parameter and ignores it, which is
      what makes a checker that reads it expressible.
   2. Determinism and state-independence are two obligations, not one.
      TAL-001's criterion is that two runs over identical inputs return
      identical verdicts *and identical rejection sites*, which is a property
      of the run and not of the composer's state; R-06-015b is the state
      half. `Ambient` therefore carries both a run index and a state, and
      `the_two_halves_compose` proves the conjunction from the two with a
      mediating ambient. The rejection-site half is a third predicate rather
      than a decoration: `NamesAStableRule` and `NamesAStableSite` are stated
      apart and each is broken by a construction that keeps the other.
   3. The derivation carrier is arbitrary and the reading is what the checker
      sees, and that is an obligation with something to exclude rather than
      what parametricity already gives. R-13-003 names the typing derivation
      as a certificate part and fixes no term language; M6.2b owes the
      proof-term checker. `IsAFunctionOfTheReading` is stated of an arbitrary
      checker over an arbitrary carrier and an arbitrary reading, and
      `Tagged` below is a carrier two of whose values read alike, so a checker
      that looks behind the reading is definable and is refuted. A thin
      derivation is then a value of a carrier whose reading is short, and not
      a special case.
   4. A derivation that is *absent* and one that is *thin* are decided by
      different rules. R-13-003 makes the derivation a named part of the
      admitted artifact and R-13-011 has every admitted artifact carry its
      required evidence, so a missing derivation is refused before any rule
      over derivations runs, while a derivation carrying no record is refused,
      or not, by the ordinary coverage rule against its tier's required set.
      The two refusals carry different rule identifiers, and
      `the_absent_and_the_thin_are_refused_apart` checks that they do.
   5. The unit that carries exactly one discharge is R-05-036's facet, and
      there are thirteen. R-05-029 closes the type-level obligations at eleven
      rows in the register's own words; R-05-036's criterion adds that each of
      them maps to exactly one move *except the two whose halves split*,
      memory safety taking move (I) for its spatial half and move (II) for its
      temporal half and control-flow integrity taking move (I) for its runtime
      half and move (II) for its compose-time callee-set enumeration. Eleven
      rows with two of them split is thirteen facets, and R-05-037, R-05-038
      and R-05-039 are the three rows of the move table, three facets, eight
      and two. `Obligation` below is the eleven, `Facet` is the thirteen,
      `row_of` is the map back, and `move_of` is the move table; the three
      counts are checked by conversion, so a facet added or a move reassigned
      stops one of them.
   6. Recognition precedes coverage, and the order of the whole check is
      TAL-074's rather than this file's. That requirement closes a six-phase
      enumeration and orders it, rejecting at the first failure: bind, parse
      and limit, decode and structure, then the deletions of move III, the
      citations of move I and the attributes of move II. So the version
      comparison is in the first phase and not the third, the coverage walk
      runs the three move phases in *that* order rather than in the order a
      machine happens to declare its required set, and `phase_of_rule` places
      every refusal below in one of the six. What TAL-074 does not order is
      the two halves of its own phase 0: this file compares the version before
      it recomputes the binding, because TAL-008 makes a certificate naming a
      version the checker does not implement a rejection *before the checker
      proceeds*, so a commitment recomputed under an unimplemented version
      decides nothing. An absent derivation is phase 0's first act, there
      being no certificate for that phase to bind or to read a version off.
      The order among the first three phases is stated as three clauses of its
      own rather than left as prose, one per adjacent pair, each proved of the
      specification and each refuted by a checker that hoists the later phase
      above the earlier one; every one of those three accepts exactly where
      the specification accepts, so what separates it is the refusal it names.
   7. Coverage is a set property in its facets and a sequence property in its
      phases. R-05-029's criterion is that a derivation carries an attribute,
      citation or deletion-check *for each* listed obligation, which fixes no
      order and no multiplicity among the records, so the checker is invariant
      under reordering and duplication of a derivation's records and sensitive
      only to deletion and to misrouting. Which of the three a record is, on
      the other hand, is not free: R-05-037, R-05-038 and R-05-039 assign one
      to each facet, so a record discharging a cited facet by an attribute
      discharges nothing, and the checker that reads the facet and ignores the
      move is refuted below.
   8. A rejection is total at the composer, and total means the *generation*
      and not the package. R-11-005 has the transactor commit a generation
      only after the checker validates every new binary's proof, R-13-001a
      makes the install atomic and a generation rather than an amendment to
      one, and R-13-001c has a composer that gets its inputs wrong fail
      admission rather than ship. So the composer's codomain is a generation
      or nothing, one refused package costs the generation, and the composer
      that ships the sub-roster it could admit is refuted rather than
      specified.
   9. A whole-image pass emits bytes no roster names, and the obligation is
      coverage rather than absence. R-13-010b requires *one shared service
      compartment in place of a library statically linked into each consumer*,
      which is a component the roster cannot have named, and R-13-001c
      requires the pass to emit the CHERI-TAL derivation covering the new
      bytes. So the obligation is that every emitted package is named by the
      roster *or* declared as the pass's own product, with every declared
      product carried by the image; a composer emitting an undeclared stranger
      and one declaring a product it did not carry are both refuted, and the
      merging composer that does what R-13-010b requires satisfies all of it.
  10. Boolean rather than propositional wherever the witnesses must compute:
      the recognition tests, the coverage test, the verdict comparison and the
      composer's own test are decidable, so the generated families below are
      checked by conversion in the silent Example form rather than by a proof
      per member.
  11. The waived-rule family is the natural weakening of a fail-closed
      checker, so it is generated over the rule enumeration rather than
      authored. `waiving r` is the checker that accepts what rule `r` alone
      refused; the two theorems about it hold of an arbitrary base checker and
      an arbitrary pair of rules, and one theorem per rule links the waiving
      to the negation of that rule's own clause, so the eight clauses are
      eight obligations rather than one stated eight times.

   The literals taken from the design, and there are seven. Four are the
   register's own. R-05-029's enumeration is eleven, so `all_obligations` is
   that list and `there_are_eleven_type_level_obligations` is the count
   checked by conversion. R-05-036 fixes three moves and no fourth mechanism,
   so `all_moves` is three. R-05-036's criterion splits two of the eleven rows
   and no other, so `all_facets` is thirteen, and R-05-037's three, R-05-038's
   eight and R-05-039's two are checked against the move table beside it.
   R-13-011's tier enumeration is three. Two more are inherited through the
   pin R-05-135a makes and gap a reports: the typed assembly language's
   judgment block is seven, and TAL-074's phase enumeration is six. The
   seventh is the file's own: `all_rules` is its refusal vocabulary at eight,
   TAL-078 fixing only a rejecting verdict's shape, one requirement and one
   site, and closing no vocabulary of requirement names. What is not the
   file's is the *order*, which `phase_of_rule` reads off TAL-074, and every
   one of the six phases carries at least one refusal. Every other magnitude
   is a field, is derived, or is a demo witness value gap g records: the
   per-tier required sets past R-13-012's, the admitted versions and the
   composer's identity are fields of the Machine; every code past an
   enumeration is `count_of` that enumeration rather than a written number;
   every site a verdict names is read off the package, the record or the facet
   that failed; and every figure the demo roster carries is declared in a
   conversion beside it, because a magnitude no check reads is one a weakening
   moves in silence.

   How the refutations are generated. A refutation is a seeded weakening the
   theorem must reject, so the families below are produced mechanically rather
   than authored, which is SupervisionTree.v's method taken to a different
   order. Over the rule enumeration: `waiving` yields one unsound checker per
   rule, eight of them, each keeping every other rule as one generic theorem,
   dropping its own as another, and breaking that rule's own clause as a
   third. Over a derivation's own record list: `drop_at` deletes a discharge
   and yields one weakening per record; `patch_at` with `unknown_form`, with
   `unknown_move` and with `unknown_facet` replaces one third of a record's
   codes with the first code past its enumeration and yields three families of
   one per record; `patch_at attributed` rewrites one record's move to an
   attribute and yields the misrouting family, whose refused members are
   exactly the facets R-05-037 routes through a citation; and `swap_at` and
   `dup_at` are the two families the specification is invariant under. Over
   the judgment enumeration itself: `retag` rewrites every record to one
   judgment form and yields one weakening per form, seven of them, every one
   verdict-preserving because no entry pairs a form with the obligation it
   discharges (gap c). Over an arbitrary package list: the same generators
   over a roster, with the insertion family carrying the refused package that
   must cost the generation. Beside them the generic theorems quantify over an
   arbitrary position, an arbitrary roster and an arbitrary package rather
   than enumerating. The hand-authored refutations are the ones no index
   generates, being alternative constructions rather than mutations of a list.

   What this file deliberately does not author, with the entry that owes each
   decision. A register gap is reported, not closed:

   a. Where the judgment forms and the phase order are closed. R-05-135a puts
      the type theory in
      [typed-assembly-language.md](../docs/typed-assembly-language.md), whose
      section 8.4 block fixes seven judgment forms and whose TAL-074 closes
      and orders six checker phases, and no register entry states either
      number in its own words. The register's review gate audits the register,
      so both enumerations below are inherited through a pin rather than
      audited, and an eighth form or a seventh phase added to that document is
      not a register edit. Owed at R-05-135a or R-06-009.
   b. What Tier 0 and Tier 1 require, in the canonical vocabulary. R-13-011
      states their evidence in its own words, and most of it is not among
      R-05-029's eleven at all: R-05-030 puts Tier-0 refinement,
      non-interference and the residual cases outside every type system, and
      Tier 1's handler termination and information-flow theorems are named by
      no facet. R-06-009 says what of Tier 1 the type-checker does decide,
      *the memory/ABI half*, and that is what the demo machine's Tier-1 row
      follows, as a witness value and not as a reading of R-13-011. Tier 2 is
      not in this gap: R-13-012 states its six rows and R-05-036 with
      R-05-038 supplies the one facet split those rows need, so `required
      TierTwo` is the register's outright. Owed at R-13-011 or R-05-030.
   c. Which judgment form discharges which facet. The judgment block fixes the
      forms and R-05-029 fixes the obligations, and no entry pairs them, so
      the checker below requires a record's form to be recognised and requires
      nothing about which form it is.
      `every_retagging_of_the_judgment_form_is_admitted` machine-checks that
      the pairing is free rather than merely unstated. What is *not* free is
      the move, which R-05-037, R-05-038 and R-05-039 assign exactly, and the
      two axes are stated apart for that reason. Owed at R-06-009 or
      R-05-135a.
   d. Whether a package's manifest-consistency check is an obligation.
      R-13-012 adds it to the Tier-2 certificate and calls it "a tier-local
      admission check that is not one of the eleven", so it is a required
      check that no enumeration carries. Nothing below models it, because
      putting it in `Obligation` would make R-05-029's list twelve. Owed at
      R-13-012 or R-05-029.
   e. Whether a roster may name one identifier twice. R-13-001 makes a package
      content-addressed and R-13-007 makes the store deduplicated, which
      together suggest an identifier is a key, and no entry says a roster with
      two packages at one identifier is malformed. Nothing below requires
      distinct identifiers, and the composer's obligations are accordingly
      stated over the packages it emits rather than over the identifiers,
      which is the weaker reading and the one the words carry. Owed at
      R-13-001.
   f. Which side of R-11-005a's line the composition-time act stands on.
      Which versions a derivation is scoped to is not open: R-11-005 names the
      spec-set and the Sail model, R-05-135b adds the pinned language
      specification and its profile, and `Versions` below carries all four and
      compares them componentwise. What no entry says is whether the
      composition-time act compares against the versions the composer targets
      or the versions the device runs, R-11-005a separating *admissible* from
      *current* without deciding it. `admitted_versions` below is one field
      and the file states the obligation over it. TAL-072 adds a fifth
      version, the decoder's, to a verdict's key, and no register entry names
      it, which is gap a's delegation again. Owed at R-11-005 or R-11-005a.
   g. Which facet partition a derivation's discharge records are keyed by.
      R-05-036's move table partitions R-05-029's eleven into thirteen; the
      pinned language's TAL-012 partitions the same eleven into sixteen, its
      three extra splits falling inside rows 8, 9 and 11. The two agree about
      moves, each of the three finer splits taking the move its row takes, so
      no verdict below turns on the choice, and this file takes the register's
      thirteen because R-05-037, R-05-038 and R-05-039 are what assign the
      moves it checks. That neither document says which partition a
      *derivation record* names is the gap. Owed at R-05-036 or R-05-135a.
   h. Every composition magnitude. The per-tier required sets past Tier 2's,
      the admitted versions, the composer's identity, the golden roster's
      identifiers, tiers, producers, attestations and certificates are fields
      or demo definitions instantiated with arbitrary witness values that
      carry no composition claim. In particular no entry assigns a component
      to a tier, so the tiers the roster claims are chosen to inhabit all
      three of R-13-011's and are a witness value.

   What is expressible here and what is not. R-06-015b's authority clause has
   two halves and only one of them is a property of a verdict: that a checker
   reads nothing but the candidate, its certificate and the profile is stated
   and refuted below, and that it holds no capability into the store, the
   transactor's roots or another compartment's state is a fact about the
   composed capability topology, which this carrier does not express and which
   nothing below claims.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary checker, composer, derivation carrier, reading,
   roster, position or typing relation, proved of the specification, and
   refuted of an alternative construction the register's own sentence
   excludes. Inhabitation is concrete: a demo machine whose three tier
   requirements are inhabited, a seven-component roster the composer admits
   whole, a witness for each of the eight refusal rules, three derivation
   carriers with three readings, and generated families over the roster and
   over a derivation that are refused beside families that are not, so no
   theorem is proved from a premise nothing satisfies and none from one
   everything satisfies.
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

(* 0 through n-1, in that order: the index set every generated family below
   ranges over. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

Definition before_last (n : nat) : nat :=
  match n with 0 => 0 | S k => k end.

(* Implication as a boolean, written out rather than taken from a library for
   the reason above. *)
Definition only_if (a b : bool) : bool := orb (negb a) b.

Definition bool_eqb (a b : bool) : bool :=
  match a, b with
  | true, true => true
  | false, false => true
  | _, _ => false
  end.

Definition is_some {A : Type} (o : option A) : bool :=
  match o with Some _ => true | None => false end.

Definition map_option {A B : Type} (f : A -> B) (o : option A) : option B :=
  match o with None => None | Some x => Some (f x) end.

Definition mem_nat (i : nat) (l : list nat) : bool :=
  any_of (fun j => Nat.eqb i j) l.

Fixpoint nat_list_eqb (l r : list nat) : bool :=
  match l, r with
  | nil, nil => true
  | cons a s, cons b t => andb (Nat.eqb a b) (nat_list_eqb s t)
  | _, _ => false
  end.

(* -------------------------------------------------------------------------
   The five generators. Each is polymorphic because the same operators run
   over a derivation's record list and over a roster of packages, and
   generating both families from one set is what makes the two axes
   comparable.
   ------------------------------------------------------------------------- *)

(* Transpose the adjacent pair at n. *)
Fixpoint swap_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons a (cons b r) => cons b (cons a r)
  | 0, _ => l
  | S k, cons a r => cons a (swap_at k r)
  | S _, nil => nil
  end.

(* Delete the member at n. *)
Fixpoint drop_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons _ r => r
  | 0, nil => nil
  | S k, cons a r => cons a (drop_at k r)
  | S _, nil => nil
  end.

(* Insert x at n. *)
Fixpoint insert_at {A : Type} (n : nat) (x : A) (l : list A) : list A :=
  match n, l with
  | 0, _ => cons x l
  | S k, cons a r => cons a (insert_at k x r)
  | S _, nil => cons x nil
  end.

(* Repeat the member at n, which is the insertion whose inserted value the
   list already carries. *)
Fixpoint dup_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons x r => cons x (cons x r)
  | 0, nil => nil
  | S k, cons x r => cons x (dup_at k r)
  | S _, nil => nil
  end.

(* Rewrite the member at n through f, which is how a family corrupts one site
   of a derivation without touching the rest of it. *)
Fixpoint patch_at {A : Type} (f : A -> A) (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons x r => cons (f x) r
  | 0, nil => nil
  | S k, cons x r => cons x (patch_at f k r)
  | S _, nil => nil
  end.

(* -------------------------------------------------------------------------
   The small lemmas the prelude does not carry.
   ------------------------------------------------------------------------- *)

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
  intros a. induction a as [ | x IH ]; intros b H.
  - destruct b as [ | y ]; [ reflexivity | discriminate H ].
  - destruct b as [ | y ]; [ discriminate H | ].
    simpl in H. rewrite (IH y H). reflexivity.
Qed.

Lemma nat_leb_refl : forall n : nat, Nat.leb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma nat_leb_succ : forall n : nat, Nat.leb n (S n) = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma nat_leb_trans :
  forall a b c : nat, Nat.leb a b = true -> Nat.leb b c = true -> Nat.leb a c = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b c Hab Hbc.
  - reflexivity.
  - destruct b as [ | y ]; [ discriminate Hab | ].
    destruct c as [ | z ]; [ discriminate Hbc | ].
    simpl in Hab. simpl in Hbc. simpl. exact (IH y z Hab Hbc).
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

Lemma all_of_filter :
  forall (A : Type) (p : A -> bool) (l : list A), all_of p (filter_of p l) = true.
Proof.
  intros A p l. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. destruct (p x) eqn:E.
    + simpl. rewrite E. simpl. exact IH.
    + exact IH.
Qed.

Lemma filter_of_within :
  forall (A : Type) (p q : A -> bool) (l : list A),
    all_of q l = true -> all_of q (filter_of p l) = true.
Proof.
  intros A p q l. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    simpl. destruct (p x).
    + simpl. apply andb_join; [ exact Hx | exact (IH Hr) ].
    + exact (IH Hr).
Qed.

Lemma mem_nat_cons :
  forall (i j : nat) (l : list nat), mem_nat i l = true -> mem_nat i (cons j l) = true.
Proof.
  intros i j l H. unfold mem_nat. simpl. unfold mem_nat in H. rewrite H.
  destruct (Nat.eqb i j); reflexivity.
Qed.

Lemma mem_nat_here : forall (i : nat) (l : list nat), mem_nat i (cons i l) = true.
Proof. intros i l. unfold mem_nat. simpl. rewrite (nat_eqb_refl i). reflexivity. Qed.

(* The helpers' own floors, so that the day one of them stops deciding is the
   day it says so. Each is a base case no check below reaches. *)
Example the_empty_conjunction_holds : all_of (fun _ : nat => false) nil = true := eq_refl.

Example the_empty_disjunction_fails : any_of (fun _ : nat => true) nil = false := eq_refl.

Example nothing_has_length_zero : count_of (nil : list nat) = 0 := eq_refl.

Example before_last_of_nothing : before_last 0 = 0 := eq_refl.

Example the_index_set_of_three : upto 3 = cons 0 (cons 1 (cons 2 nil)) := eq_refl.

Example only_if_is_implication :
  cons (only_if true true) (cons (only_if true false)
  (cons (only_if false true) (cons (only_if false false) nil)))
  = cons true (cons false (cons true (cons true nil))) := eq_refl.

Example bool_eqb_is_equality :
  cons (bool_eqb true true) (cons (bool_eqb true false)
  (cons (bool_eqb false true) (cons (bool_eqb false false) nil)))
  = cons true (cons false (cons false (cons true nil))) := eq_refl.

Example nothing_is_a_member_of_nothing : mem_nat 4 nil = false := eq_refl.

Example the_empty_lists_agree : nat_list_eqb nil nil = true := eq_refl.

Example a_longer_list_does_not_agree :
  nat_list_eqb (cons 1 nil) (cons 1 (cons 2 nil)) = false := eq_refl.

(* The five generators at their own boundaries, where nothing below reaches
   them: past the end of a list each is the identity or an append, and a
   transposition of a singleton is that singleton. *)
Example the_generators_past_the_end :
  swap_at 5 (cons 1 (cons 2 nil)) = cons 1 (cons 2 nil)
  /\ drop_at 5 (cons 1 (cons 2 nil)) = cons 1 (cons 2 nil)
  /\ insert_at 5 9 (cons 1 (cons 2 nil)) = cons 1 (cons 2 (cons 9 nil))
  /\ dup_at 5 (cons 1 (cons 2 nil)) = cons 1 (cons 2 nil)
  /\ patch_at S 5 (cons 1 (cons 2 nil)) = cons 1 (cons 2 nil) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example a_transposition_of_one_member_is_that_member :
  swap_at 0 (cons 7 nil) = cons 7 nil := eq_refl.

Example the_generators_at_the_front :
  swap_at 0 (cons 1 (cons 2 (cons 3 nil))) = cons 2 (cons 1 (cons 3 nil))
  /\ drop_at 0 (cons 1 (cons 2 nil)) = cons 2 nil
  /\ insert_at 0 9 (cons 1 nil) = cons 9 (cons 1 nil)
  /\ dup_at 0 (cons 1 (cons 2 nil)) = cons 1 (cons 1 (cons 2 nil))
  /\ patch_at S 0 (cons 1 (cons 2 nil)) = cons 2 (cons 2 nil) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* =========================================================================
   The closed enumerations, and which document closes each.

   Four are the register's: R-05-029's eleven obligation rows, R-05-036's
   three checker moves, the thirteen facets that entry's criterion splits the
   eleven into, and R-13-011's three assurance tiers. Two are inherited
   through the pin R-05-135a makes, and gap a reports both: the judgment forms
   of the language's own section 8.4 block, and TAL-074's six checker phases.
   One is this file's, the refusal vocabulary, whose count is checked only so
   that a ninth refusal cannot be added below in silence.
   ========================================================================= *)

(* The judgment forms of the typed assembly language's own judgment block. *)
Inductive Judgment : Type :=
| TypeWellFormed              (* |- t ok                        *)
| RegisterFileWellFormed      (* |- G ok                        *)
| InstructionTransfer         (* S |- instr => S'               *)
| StateRefinement             (* S' <= S                        *)
| BlockTransfer               (* |- block b : S -> S'           *)
| ImageWellFormed             (* |- image ok                    *)
| AdmissionJudgment.          (* |- cert |> artifact : verdict  *)

(* R-05-029's eleven type-level obligations, in that entry's own order. Each
   is a *row*: control-flow integrity carries both halves and is not two rows,
   which is the same entry's own sentence, and memory safety is one row for
   the same reason. What the rows split into is `Facet` below. *)
Inductive Obligation : Type :=
| MemorySafety
| DefiniteInitialization
| DataRaceFreedom
| ControlFlowIntegrity
| NoRuntimeCodegen
| AbiTypeConformance
| ExaminedVerdicts
| AbsentAmbientState
| RepresentationAndProvenance
| ConstantTime
| WorstCaseExecutionTime.

(* R-05-036's three moves, and there is no fourth mechanism. *)
Inductive Move : Type :=
| CiteAnInvariant             (* I:   R-05-037 *)
| EvaluateAnAttribute         (* II:  R-05-038 *)
| ConfirmADeletion.           (* III: R-05-039 *)

(* The unit that carries exactly one move. R-05-036's criterion is that each
   of R-05-029's eleven maps to exactly one move *except* the two whose halves
   split, so nine rows contribute one facet each and rows 1 and 4 contribute
   two, which is thirteen. The names follow the language document's, the
   register naming the rows and not the halves. *)
Inductive Facet : Type :=
| MemSpatial                  (* row 1,  move I   (R-05-037) *)
| MemTemporal                 (* row 1,  move II  (R-05-038) *)
| InitDefinite                (* row 2,  move II  *)
| RaceFreedom                 (* row 3,  move II  *)
| CfiRuntime                  (* row 4,  move I   *)
| CfiCalleeSet                (* row 4,  move II  *)
| CodegenNone                 (* row 5,  move I   *)
| AbiConform                  (* row 6,  move II  *)
| VerdictRelevance            (* row 7,  move II  *)
| AmbientAbsent               (* row 8,  move III (R-05-039) *)
| ReprProvenance              (* row 9,  move III *)
| CtTaint                     (* row 10, move II  *)
| CostWcet.                   (* row 11, move II  *)

(* R-13-011's three assurance tiers. Every admitted artifact carries exactly
   one, which is why a package below names a tier by a code the checker must
   recognise rather than by a value it cannot fail to hold. *)
Inductive Tier : Type :=
| TierZero
| TierOne
| TierTwo.

(* TAL-074's six phases, in that requirement's own order. The checker runs
   them in this order and rejects at the first failure, and the last three are
   R-05-036's three moves in the order that requirement's table gives them:
   deletions, then citations, then attributes. *)
Inductive Phase : Type :=
| PhaseBind                   (* 0. recompute the commitments; compare versions *)
| PhaseParse                  (* 1. parse the certificate; check the limits     *)
| PhaseStructure              (* 2. decode and structure                        *)
| PhaseDeletions              (* 3. move III                                    *)
| PhaseCitations              (* 4. move I                                      *)
| PhaseAttributes.            (* 5. move II                                     *)

(* The refusals this file's own check makes. TAL-078 fixes the shape of a
   rejecting verdict, one requirement and one site, and closes no vocabulary
   of requirement names, so this enumeration is the file's; what is not the
   file's is its order, which is `phase_of_rule`'s and therefore TAL-074's. *)
Inductive RuleId : Type :=
| DerivationAbsent            (* R-13-003, R-13-011: no certificate to bind  *)
| VersionMismatch             (* R-11-005, R-05-135b, TAL-008                *)
| BindingMismatch             (* R-13-003, TAL-067: the derivation is elsewhere's *)
| TierUnrecognised            (* R-13-011: exactly one tier, and a known one *)
| FormUnrecognised            (* TAL-023: a form with no rule is not a permissive default *)
| DeletionUnconfirmed         (* R-05-039: a move-III facet undischarged     *)
| CitationMissing             (* R-05-037: a move-I facet undischarged       *)
| AttributeMissing.           (* R-05-038: a move-II facet undischarged      *)

Inductive Verdict : Type :=
| Accepted
| Refused (rule : RuleId) (site : nat).

Definition all_judgments : list Judgment :=
  cons TypeWellFormed (cons RegisterFileWellFormed (cons InstructionTransfer
  (cons StateRefinement (cons BlockTransfer (cons ImageWellFormed
  (cons AdmissionJudgment nil)))))).

Definition all_obligations : list Obligation :=
  cons MemorySafety (cons DefiniteInitialization (cons DataRaceFreedom
  (cons ControlFlowIntegrity (cons NoRuntimeCodegen (cons AbiTypeConformance
  (cons ExaminedVerdicts (cons AbsentAmbientState
  (cons RepresentationAndProvenance (cons ConstantTime
  (cons WorstCaseExecutionTime nil)))))))))).

Definition all_moves : list Move :=
  cons CiteAnInvariant (cons EvaluateAnAttribute (cons ConfirmADeletion nil)).

Definition all_facets : list Facet :=
  cons MemSpatial (cons MemTemporal (cons InitDefinite (cons RaceFreedom
  (cons CfiRuntime (cons CfiCalleeSet (cons CodegenNone (cons AbiConform
  (cons VerdictRelevance (cons AmbientAbsent (cons ReprProvenance
  (cons CtTaint (cons CostWcet nil)))))))))))).

Definition all_tiers : list Tier :=
  cons TierZero (cons TierOne (cons TierTwo nil)).

Definition all_phases : list Phase :=
  cons PhaseBind (cons PhaseParse (cons PhaseStructure (cons PhaseDeletions
  (cons PhaseCitations (cons PhaseAttributes nil))))).

Definition all_rules : list RuleId :=
  cons DerivationAbsent (cons VersionMismatch (cons BindingMismatch
  (cons TierUnrecognised (cons FormUnrecognised (cons DeletionUnconfirmed
  (cons CitationMissing (cons AttributeMissing nil))))))).

(* The seven counts, checked by conversion rather than claimed. The day
   R-05-029 admits a twelfth row, R-05-036 a fourth move, R-13-011 a fourth
   tier or TAL-074 a seventh phase is the day one of them stops holding. *)
Example there_are_eleven_type_level_obligations : count_of all_obligations = 11 := eq_refl.

Example there_are_three_checker_moves : count_of all_moves = 3 := eq_refl.

Example there_are_thirteen_facets : count_of all_facets = 13 := eq_refl.

Example there_are_three_assurance_tiers : count_of all_tiers = 3 := eq_refl.

Example there_are_seven_judgment_forms : count_of all_judgments = 7 := eq_refl.

Example there_are_six_checker_phases : count_of all_phases = 6 := eq_refl.

Example there_are_eight_refusal_rules : count_of all_rules = 8 := eq_refl.

Definition judgment_eqb (a b : Judgment) : bool :=
  match a, b with
  | TypeWellFormed, TypeWellFormed => true
  | RegisterFileWellFormed, RegisterFileWellFormed => true
  | InstructionTransfer, InstructionTransfer => true
  | StateRefinement, StateRefinement => true
  | BlockTransfer, BlockTransfer => true
  | ImageWellFormed, ImageWellFormed => true
  | AdmissionJudgment, AdmissionJudgment => true
  | _, _ => false
  end.

Lemma judgment_eqb_refl : forall j : Judgment, judgment_eqb j j = true.
Proof. intros j. destruct j; reflexivity. Qed.

Lemma judgment_eqb_true : forall a b : Judgment, judgment_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition obligation_eqb (a b : Obligation) : bool :=
  match a, b with
  | MemorySafety, MemorySafety => true
  | DefiniteInitialization, DefiniteInitialization => true
  | DataRaceFreedom, DataRaceFreedom => true
  | ControlFlowIntegrity, ControlFlowIntegrity => true
  | NoRuntimeCodegen, NoRuntimeCodegen => true
  | AbiTypeConformance, AbiTypeConformance => true
  | ExaminedVerdicts, ExaminedVerdicts => true
  | AbsentAmbientState, AbsentAmbientState => true
  | RepresentationAndProvenance, RepresentationAndProvenance => true
  | ConstantTime, ConstantTime => true
  | WorstCaseExecutionTime, WorstCaseExecutionTime => true
  | _, _ => false
  end.

Lemma obligation_eqb_refl : forall o : Obligation, obligation_eqb o o = true.
Proof. intros o. destruct o; reflexivity. Qed.

Lemma obligation_eqb_true : forall a b : Obligation, obligation_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition move_eqb (a b : Move) : bool :=
  match a, b with
  | CiteAnInvariant, CiteAnInvariant => true
  | EvaluateAnAttribute, EvaluateAnAttribute => true
  | ConfirmADeletion, ConfirmADeletion => true
  | _, _ => false
  end.

Lemma move_eqb_refl : forall k : Move, move_eqb k k = true.
Proof. intros k. destruct k; reflexivity. Qed.

Lemma move_eqb_true : forall a b : Move, move_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition facet_eqb (a b : Facet) : bool :=
  match a, b with
  | MemSpatial, MemSpatial => true
  | MemTemporal, MemTemporal => true
  | InitDefinite, InitDefinite => true
  | RaceFreedom, RaceFreedom => true
  | CfiRuntime, CfiRuntime => true
  | CfiCalleeSet, CfiCalleeSet => true
  | CodegenNone, CodegenNone => true
  | AbiConform, AbiConform => true
  | VerdictRelevance, VerdictRelevance => true
  | AmbientAbsent, AmbientAbsent => true
  | ReprProvenance, ReprProvenance => true
  | CtTaint, CtTaint => true
  | CostWcet, CostWcet => true
  | _, _ => false
  end.

Lemma facet_eqb_refl : forall f : Facet, facet_eqb f f = true.
Proof. intros f. destruct f; reflexivity. Qed.

Lemma facet_eqb_true : forall a b : Facet, facet_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition tier_eqb (a b : Tier) : bool :=
  match a, b with
  | TierZero, TierZero => true
  | TierOne, TierOne => true
  | TierTwo, TierTwo => true
  | _, _ => false
  end.

Lemma tier_eqb_refl : forall t : Tier, tier_eqb t t = true.
Proof. intros t. destruct t; reflexivity. Qed.

Lemma tier_eqb_true : forall a b : Tier, tier_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

Definition phase_eqb (a b : Phase) : bool :=
  match a, b with
  | PhaseBind, PhaseBind => true
  | PhaseParse, PhaseParse => true
  | PhaseStructure, PhaseStructure => true
  | PhaseDeletions, PhaseDeletions => true
  | PhaseCitations, PhaseCitations => true
  | PhaseAttributes, PhaseAttributes => true
  | _, _ => false
  end.

Lemma phase_eqb_refl : forall q : Phase, phase_eqb q q = true.
Proof. intros q. destruct q; reflexivity. Qed.

Definition rule_eqb (a b : RuleId) : bool :=
  match a, b with
  | DerivationAbsent, DerivationAbsent => true
  | VersionMismatch, VersionMismatch => true
  | BindingMismatch, BindingMismatch => true
  | TierUnrecognised, TierUnrecognised => true
  | FormUnrecognised, FormUnrecognised => true
  | DeletionUnconfirmed, DeletionUnconfirmed => true
  | CitationMissing, CitationMissing => true
  | AttributeMissing, AttributeMissing => true
  | _, _ => false
  end.

Lemma rule_eqb_refl : forall r : RuleId, rule_eqb r r = true.
Proof. intros r. destruct r; reflexivity. Qed.

Lemma rule_eqb_true : forall a b : RuleId, rule_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

(* Each comparison off its own diagonal, as one conversion per enumeration: a
   comparison answering true across two members would collapse the sets those
   members index, and R-13-011's *exactly one tier* is the sharpest case. *)
Example each_member_is_told_from_every_other :
  all_of (fun t => Nat.eqb (count_of (filter_of (fun u => tier_eqb t u) all_tiers)) 1)
         all_tiers = true
  /\ all_of (fun k => Nat.eqb (count_of (filter_of (fun j => move_eqb k j) all_moves)) 1)
            all_moves = true
  /\ all_of (fun f => Nat.eqb (count_of (filter_of (fun g => facet_eqb f g) all_facets)) 1)
            all_facets = true
  /\ all_of (fun j => Nat.eqb (count_of (filter_of (fun i => judgment_eqb j i)
                                                   all_judgments)) 1)
            all_judgments = true
  /\ all_of (fun r => Nat.eqb (count_of (filter_of (fun s => rule_eqb r s) all_rules)) 1)
            all_rules = true
  /\ all_of (fun q => Nat.eqb (count_of (filter_of (fun s => phase_eqb q s) all_phases)) 1)
            all_phases = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Definition verdict_eqb (u v : Verdict) : bool :=
  match u, v with
  | Accepted, Accepted => true
  | Refused r1 s1, Refused r2 s2 => andb (rule_eqb r1 r2) (Nat.eqb s1 s2)
  | _, _ => false
  end.

Lemma verdict_eqb_refl : forall v : Verdict, verdict_eqb v v = true.
Proof.
  intros v. destruct v as [ | r s ].
  - reflexivity.
  - simpl. apply andb_join; [ exact (rule_eqb_refl r) | exact (nat_eqb_refl s) ].
Qed.

(* A verdict is one of exactly two shapes, which is TAL-079's *rejection is
   total and silent about repair* read at the type: there is no partial
   admission, no warning tier and no override to express, because the codomain
   carries no third value. What that leaves with something to exclude is the
   composer's behaviour, which is stated further down. *)
Theorem a_verdict_is_acceptance_or_a_named_refusal :
  forall v : Verdict, v = Accepted \/ (exists (r : RuleId) (s : nat), v = Refused r s).
Proof.
  intros v. destruct v as [ | r s ].
  - left. reflexivity.
  - right. exists r. exists s. reflexivity.
Qed.

Definition accepts (v : Verdict) : bool :=
  match v with Accepted => true | Refused _ _ => false end.

Definition rule_of (v : Verdict) : option RuleId :=
  match v with Accepted => None | Refused r _ => Some r end.

Definition site_of (v : Verdict) : option nat :=
  match v with Accepted => None | Refused _ s => Some s end.

Example acceptance_and_refusal_are_told_apart :
  accepts Accepted = true
  /\ accepts (Refused DerivationAbsent 0) = false
  /\ rule_of Accepted = None
  /\ rule_of (Refused FormUnrecognised 2) = Some FormUnrecognised
  /\ site_of Accepted = None
  /\ site_of (Refused FormUnrecognised 2) = Some 2 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Example two_refusals_differ_at_the_rule_and_at_the_site :
  verdict_eqb (Refused FormUnrecognised 2) (Refused FormUnrecognised 2) = true
  /\ verdict_eqb (Refused FormUnrecognised 2) (Refused FormUnrecognised 3) = false
  /\ verdict_eqb (Refused FormUnrecognised 2) (Refused BindingMismatch 2) = false
  /\ verdict_eqb Accepted (Refused FormUnrecognised 2) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* =========================================================================
   The move table (R-05-036, R-05-037, R-05-038, R-05-039), and the phase
   order it feeds (TAL-074).
   ========================================================================= *)

(* Which of R-05-029's eleven rows a facet belongs to. Nine rows have one
   facet; rows 1 and 4 have two, which is R-05-036's own exception. *)
Definition row_of (f : Facet) : Obligation :=
  match f with
  | MemSpatial => MemorySafety
  | MemTemporal => MemorySafety
  | InitDefinite => DefiniteInitialization
  | RaceFreedom => DataRaceFreedom
  | CfiRuntime => ControlFlowIntegrity
  | CfiCalleeSet => ControlFlowIntegrity
  | CodegenNone => NoRuntimeCodegen
  | AbiConform => AbiTypeConformance
  | VerdictRelevance => ExaminedVerdicts
  | AmbientAbsent => AbsentAmbientState
  | ReprProvenance => RepresentationAndProvenance
  | CtTaint => ConstantTime
  | CostWcet => WorstCaseExecutionTime
  end.

(* The move table itself: R-05-037's three, R-05-038's eight, R-05-039's two. *)
Definition move_of (f : Facet) : Move :=
  match f with
  | MemSpatial => CiteAnInvariant
  | MemTemporal => EvaluateAnAttribute
  | InitDefinite => EvaluateAnAttribute
  | RaceFreedom => EvaluateAnAttribute
  | CfiRuntime => CiteAnInvariant
  | CfiCalleeSet => EvaluateAnAttribute
  | CodegenNone => CiteAnInvariant
  | AbiConform => EvaluateAnAttribute
  | VerdictRelevance => EvaluateAnAttribute
  | AmbientAbsent => ConfirmADeletion
  | ReprProvenance => ConfirmADeletion
  | CtTaint => EvaluateAnAttribute
  | CostWcet => EvaluateAnAttribute
  end.

Definition facets_of_row (o : Obligation) : list Facet :=
  filter_of (fun f => obligation_eqb o (row_of f)) all_facets.

Definition facets_of_move_in (k : Move) (l : list Facet) : list Facet :=
  filter_of (fun f => move_eqb (move_of f) k) l.

(* R-05-036's criterion, checked rather than transcribed: every row has at
   least one facet, exactly two rows have two, and the rest have one. *)
Example every_row_is_partitioned_into_facets :
  map_over (fun o => count_of (facets_of_row o)) all_obligations
  = cons 2 (cons 1 (cons 1 (cons 2 (cons 1 (cons 1 (cons 1 (cons 1
    (cons 1 (cons 1 (cons 1 nil))))))))))
  /\ count_of (filter_of (fun o => Nat.eqb (count_of (facets_of_row o)) 2)
                         all_obligations) = 2
  /\ facets_of_row MemorySafety = cons MemSpatial (cons MemTemporal nil)
  /\ facets_of_row ControlFlowIntegrity = cons CfiRuntime (cons CfiCalleeSet nil) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* And the two rows that split are the two R-05-036 names, split the way it
   names them: memory safety cited for its spatial half and attributed for its
   temporal one, control-flow integrity cited for its runtime half and
   attributed for its compose-time callee-set enumeration. *)
Example the_two_split_rows_split_as_the_criterion_says :
  map_over move_of (facets_of_row MemorySafety)
  = cons CiteAnInvariant (cons EvaluateAnAttribute nil)
  /\ map_over move_of (facets_of_row ControlFlowIntegrity)
     = cons CiteAnInvariant (cons EvaluateAnAttribute nil) := conj eq_refl eq_refl.

(* The three rows of the move table, against the three entries that state
   them. R-05-037 carries spatial memory safety, no-runtime-codegen and
   CFI-runtime; R-05-039 carries representation-and-provenance and absence of
   ambient mutable state; R-05-038 carries the remaining eight. Three, two and
   eight is thirteen, which is the cross-check on the facet count. *)
Example the_move_table_is_the_registers :
  facets_of_move_in CiteAnInvariant all_facets
  = cons MemSpatial (cons CfiRuntime (cons CodegenNone nil))
  /\ facets_of_move_in ConfirmADeletion all_facets
     = cons AmbientAbsent (cons ReprProvenance nil)
  /\ facets_of_move_in EvaluateAnAttribute all_facets
     = cons MemTemporal (cons InitDefinite (cons RaceFreedom (cons CfiCalleeSet
       (cons AbiConform (cons VerdictRelevance (cons CtTaint (cons CostWcet nil)))))))
  /\ count_of (facets_of_move_in CiteAnInvariant all_facets) = 3
  /\ count_of (facets_of_move_in EvaluateAnAttribute all_facets) = 8
  /\ count_of (facets_of_move_in ConfirmADeletion all_facets) = 2 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* TAL-074's own order, as a rank, so that *rejects at the first failure* is a
   comparison rather than a paragraph. *)
Definition phase_rank (q : Phase) : nat :=
  match q with
  | PhaseBind => 0
  | PhaseParse => 1
  | PhaseStructure => 2
  | PhaseDeletions => 3
  | PhaseCitations => 4
  | PhaseAttributes => 5
  end.

(* TAL-074's last three phases are R-05-036's three moves, in the order that
   table gives them. *)
Definition phase_of_move (k : Move) : Phase :=
  match k with
  | ConfirmADeletion => PhaseDeletions
  | CiteAnInvariant => PhaseCitations
  | EvaluateAnAttribute => PhaseAttributes
  end.

Definition rule_of_move (k : Move) : RuleId :=
  match k with
  | ConfirmADeletion => DeletionUnconfirmed
  | CiteAnInvariant => CitationMissing
  | EvaluateAnAttribute => AttributeMissing
  end.

(* Where each of this file's refusals sits in TAL-074's enumeration. This is
   the map that makes the order below inherited rather than invented. *)
Definition phase_of_rule (r : RuleId) : Phase :=
  match r with
  | DerivationAbsent => PhaseBind
  | VersionMismatch => PhaseBind
  | BindingMismatch => PhaseBind
  | TierUnrecognised => PhaseParse
  | FormUnrecognised => PhaseStructure
  | DeletionUnconfirmed => PhaseDeletions
  | CitationMissing => PhaseCitations
  | AttributeMissing => PhaseAttributes
  end.

(* The three coverage refusals sit in the phases their own moves do, so the
   move table and the phase order are one fact and not two. *)
Theorem the_move_phases_and_the_move_rules_agree :
  forall k : Move, phase_of_rule (rule_of_move k) = phase_of_move k.
Proof. intros k. destruct k; reflexivity. Qed.

(* `all_rules` is listed in the order the checker tries the refusals, and that
   order is non-decreasing in TAL-074's rank, which is what makes it TAL-074's
   order rather than this file's. *)
Example the_refusals_are_tried_in_phase_order :
  map_over (fun r => phase_rank (phase_of_rule r)) all_rules
  = cons 0 (cons 0 (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 nil)))))))
  := eq_refl.

(* And no phase is empty: every one of TAL-074's six carries a refusal this
   file can name, so the enumeration is inherited whole rather than in part. *)
Example every_phase_carries_a_refusal :
  all_of (fun q => any_of (fun r => phase_eqb q (phase_of_rule r)) all_rules)
         all_phases = true := eq_refl.

(* =========================================================================
   Codes, and the decoding that has no permissive default.

   A derivation names a judgment form, a move and a facet by a code, because a
   code the checker does not recognise is exactly the input TAL-023's *not a
   permissive default* is about and an enumeration alone cannot express one.
   The first code past each enumeration is `count_of` that enumeration rather
   than a written number, so the boundary moves with the list it bounds.
   ========================================================================= *)

Definition code_of_judgment (j : Judgment) : nat :=
  match j with
  | TypeWellFormed => 0
  | RegisterFileWellFormed => 1
  | InstructionTransfer => 2
  | StateRefinement => 3
  | BlockTransfer => 4
  | ImageWellFormed => 5
  | AdmissionJudgment => 6
  end.

Definition judgment_of_code (n : nat) : option Judgment :=
  match n with
  | 0 => Some TypeWellFormed
  | 1 => Some RegisterFileWellFormed
  | 2 => Some InstructionTransfer
  | 3 => Some StateRefinement
  | 4 => Some BlockTransfer
  | 5 => Some ImageWellFormed
  | 6 => Some AdmissionJudgment
  | _ => None
  end.

Definition code_of_move (k : Move) : nat :=
  match k with
  | CiteAnInvariant => 0
  | EvaluateAnAttribute => 1
  | ConfirmADeletion => 2
  end.

Definition move_of_code (n : nat) : option Move :=
  match n with
  | 0 => Some CiteAnInvariant
  | 1 => Some EvaluateAnAttribute
  | 2 => Some ConfirmADeletion
  | _ => None
  end.

Definition code_of_facet (f : Facet) : nat :=
  match f with
  | MemSpatial => 0
  | MemTemporal => 1
  | InitDefinite => 2
  | RaceFreedom => 3
  | CfiRuntime => 4
  | CfiCalleeSet => 5
  | CodegenNone => 6
  | AbiConform => 7
  | VerdictRelevance => 8
  | AmbientAbsent => 9
  | ReprProvenance => 10
  | CtTaint => 11
  | CostWcet => 12
  end.

Definition facet_of_code (n : nat) : option Facet :=
  match n with
  | 0 => Some MemSpatial
  | 1 => Some MemTemporal
  | 2 => Some InitDefinite
  | 3 => Some RaceFreedom
  | 4 => Some CfiRuntime
  | 5 => Some CfiCalleeSet
  | 6 => Some CodegenNone
  | 7 => Some AbiConform
  | 8 => Some VerdictRelevance
  | 9 => Some AmbientAbsent
  | 10 => Some ReprProvenance
  | 11 => Some CtTaint
  | 12 => Some CostWcet
  | _ => None
  end.

Definition code_of_tier (t : Tier) : nat :=
  match t with TierZero => 0 | TierOne => 1 | TierTwo => 2 end.

Definition tier_of_code (n : nat) : option Tier :=
  match n with
  | 0 => Some TierZero
  | 1 => Some TierOne
  | 2 => Some TierTwo
  | _ => None
  end.

(* The first code past each enumeration, derived from the enumeration rather
   than written, so that a family below corrupting a site to an unrecognised
   code stays a corruption when the enumeration grows. *)
Definition past_the_judgments : nat := count_of all_judgments.

Definition past_the_moves : nat := count_of all_moves.

Definition past_the_facets : nat := count_of all_facets.

Definition past_the_tiers : nat := count_of all_tiers.

(* Each decode against its own enumeration, and one code past it. These four
   conversions are what hold the two tables of each pair together: a code
   moved on either side stops the round trip. *)
Example the_judgment_codes_decode :
  map_over judgment_of_code (upto 8)
  = cons (Some TypeWellFormed) (cons (Some RegisterFileWellFormed)
    (cons (Some InstructionTransfer) (cons (Some StateRefinement)
    (cons (Some BlockTransfer) (cons (Some ImageWellFormed)
    (cons (Some AdmissionJudgment) (cons None nil))))))) := eq_refl.

Example the_move_codes_decode :
  map_over move_of_code (upto 4)
  = cons (Some CiteAnInvariant) (cons (Some EvaluateAnAttribute)
    (cons (Some ConfirmADeletion) (cons None nil))) := eq_refl.

Example the_facet_codes_decode :
  map_over facet_of_code (upto 14)
  = cons (Some MemSpatial) (cons (Some MemTemporal) (cons (Some InitDefinite)
    (cons (Some RaceFreedom) (cons (Some CfiRuntime) (cons (Some CfiCalleeSet)
    (cons (Some CodegenNone) (cons (Some AbiConform) (cons (Some VerdictRelevance)
    (cons (Some AmbientAbsent) (cons (Some ReprProvenance) (cons (Some CtTaint)
    (cons (Some CostWcet) (cons None nil))))))))))))) := eq_refl.

Example the_tier_codes_decode :
  map_over tier_of_code (upto 4)
  = cons (Some TierZero) (cons (Some TierOne) (cons (Some TierTwo)
    (cons None nil))) := eq_refl.

Example the_boundaries_are_the_enumerations :
  past_the_judgments = 7 /\ past_the_moves = 3 /\ past_the_facets = 13
  /\ past_the_tiers = 3
  /\ judgment_of_code past_the_judgments = None
  /\ move_of_code past_the_moves = None
  /\ facet_of_code past_the_facets = None
  /\ tier_of_code past_the_tiers = None
  /\ judgment_of_code (before_last past_the_judgments) = Some AdmissionJudgment
  /\ move_of_code (before_last past_the_moves) = Some ConfirmADeletion
  /\ facet_of_code (before_last past_the_facets) = Some CostWcet
  /\ tier_of_code (before_last past_the_tiers) = Some TierTwo :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl)))))))))).

(* The round trips, stated of an arbitrary member rather than computed over
   the enumeration, so that the two tables of each pair cannot drift. *)
Theorem every_judgment_form_decodes_to_itself :
  forall j : Judgment, judgment_of_code (code_of_judgment j) = Some j.
Proof. intros j. destruct j; reflexivity. Qed.

Theorem every_move_decodes_to_itself :
  forall k : Move, move_of_code (code_of_move k) = Some k.
Proof. intros k. destruct k; reflexivity. Qed.

Theorem every_facet_decodes_to_itself :
  forall f : Facet, facet_of_code (code_of_facet f) = Some f.
Proof. intros f. destruct f; reflexivity. Qed.

Theorem every_tier_decodes_to_itself :
  forall t : Tier, tier_of_code (code_of_tier t) = Some t.
Proof. intros t. destruct t; reflexivity. Qed.

Theorem the_judgment_decoding_is_the_inverse_coding :
  forall (n : nat) (j : Judgment), judgment_of_code n = Some j -> code_of_judgment j = n.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | [ | k ] ] ] ] ] ] ];
    intros j H; simpl in H; try discriminate H;
    injection H as H2; rewrite <- H2; reflexivity.
Qed.

Theorem the_move_decoding_is_the_inverse_coding :
  forall (n : nat) (k : Move), move_of_code n = Some k -> code_of_move k = n.
Proof.
  intros n. destruct n as [ | [ | [ | j ] ] ];
    intros k H; simpl in H; try discriminate H;
    injection H as H2; rewrite <- H2; reflexivity.
Qed.

Theorem the_facet_decoding_is_the_inverse_coding :
  forall (n : nat) (f : Facet), facet_of_code n = Some f -> code_of_facet f = n.
Proof.
  intros n.
  destruct n as [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | k
    ] ] ] ] ] ] ] ] ] ] ] ] ];
    intros f H; simpl in H; try discriminate H;
    injection H as H2; rewrite <- H2; reflexivity.
Qed.

Theorem the_tier_decoding_is_the_inverse_coding :
  forall (n : nat) (t : Tier), tier_of_code n = Some t -> code_of_tier t = n.
Proof.
  intros n. destruct n as [ | [ | [ | k ] ] ];
    intros t H; simpl in H; try discriminate H;
    injection H as H2; rewrite <- H2; reflexivity.
Qed.

(* And there is no permissive default anywhere past each enumeration: not only
   at the first code past it, which the family generators use, but at every
   one. TAL-023's *a form with no rule is a profile defect, not a permissive
   default* is what this states, and it is an infinite statement rather than a
   boundary conversion. *)
Theorem no_code_past_the_judgments_is_recognised :
  forall n : nat, Nat.leb past_the_judgments n = true -> judgment_of_code n = None.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | [ | k ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_code_past_the_moves_is_recognised :
  forall n : nat, Nat.leb past_the_moves n = true -> move_of_code n = None.
Proof.
  intros n. destruct n as [ | [ | [ | k ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_code_past_the_facets_is_recognised :
  forall n : nat, Nat.leb past_the_facets n = true -> facet_of_code n = None.
Proof.
  intros n.
  destruct n as [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | [ | k
    ] ] ] ] ] ] ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_code_past_the_tiers_is_recognised :
  forall n : nat, Nat.leb past_the_tiers n = true -> tier_of_code n = None.
Proof.
  intros n. destruct n as [ | [ | [ | k ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* =========================================================================
   The versions a derivation is scoped to, the certificate, the arbitrary
   carrier, and the package.

   R-11-005 makes proofs generation-scoped against *the current spec-set and
   Sail-model versions*, which is two, and R-05-135b adds *a named, pinned
   version of the language specification and its profile*, which is two more.
   Carrying one number for the four would make a derivation produced against a
   re-pinned profile indistinguishable from one produced against this
   generation, so the record carries four and the comparison is componentwise.
   ========================================================================= *)

Record Versions : Type := {
  ver_spec_set : nat;        (* R-11-005 *)
  ver_sail_model : nat;      (* R-11-005 *)
  ver_language : nat;        (* R-05-135b, and TAL-008's spec version  *)
  ver_profile : nat          (* R-05-135b, and TAL-008's profile version *)
}.

Definition versions_eqb (u v : Versions) : bool :=
  andb (andb (Nat.eqb u.(ver_spec_set) v.(ver_spec_set))
             (Nat.eqb u.(ver_sail_model) v.(ver_sail_model)))
       (andb (Nat.eqb u.(ver_language) v.(ver_language))
             (Nat.eqb u.(ver_profile) v.(ver_profile))).

Lemma versions_eqb_refl : forall v : Versions, versions_eqb v v = true.
Proof.
  intros v. unfold versions_eqb. apply andb_join; apply andb_join;
    apply nat_eqb_refl.
Qed.

Lemma versions_eqb_true : forall u v : Versions, versions_eqb u v = true -> u = v.
Proof.
  intros u v H. destruct u as [ a1 b1 c1 d1 ]. destruct v as [ a2 b2 c2 d2 ].
  unfold versions_eqb in H. simpl in H.
  destruct (andb_split _ _ H) as [ H1 H2 ].
  destruct (andb_split _ _ H1) as [ Ha Hb ].
  destruct (andb_split _ _ H2) as [ Hc Hd ].
  rewrite (nat_eqb_true a1 a2 Ha). rewrite (nat_eqb_true b1 b2 Hb).
  rewrite (nat_eqb_true c1 c2 Hc). rewrite (nat_eqb_true d1 d2 Hd).
  reflexivity.
Qed.

(* One discharge record: the judgment form it is an instance of, the *move* it
   makes, the facet it discharges, and the site a refusal at it would name.
   The move is a field of the record because R-05-029's criterion is that a
   derivation carries *an attribute, citation, or deletion-check* for each
   listed obligation, and R-05-037, R-05-038 and R-05-039 say which of the
   three each facet takes. All three codes are `nat` and not enumeration
   members, because a code the checker does not recognise is exactly the input
   the fail-closed obligation is about. *)
Record Step : Type := {
  st_judgment : nat;
  st_move : nat;
  st_facet : nat;
  st_site : nat
}.

(* What a checker reads: R-11-005's and R-05-135b's four versions, R-13-003's
   binding of the derivation to the artifact it is about, and the records. *)
Record Cert : Type := {
  cert_versions : Versions;
  cert_binds : nat;
  cert_steps : list Step
}.

Definition Reading (D : Type) : Type := D -> Cert.

Definition with_steps (c : Cert) (l : list Step) : Cert :=
  {| cert_versions := c.(cert_versions);
     cert_binds := c.(cert_binds);
     cert_steps := l |}.

(* A package as the composition-time act sees it: its content-addressed name,
   the tier it claims, the producer that emitted it and whatever attestation
   it carries, and its derivation. The last two fields exist so that a checker
   reading them is expressible: R-13-013 says no admission rule reads a
   producer identity, which is a property with something to exclude only where
   the identity is there to be read. *)
Record Package (D : Type) : Type := {
  pkg_id : nat;
  pkg_tier : nat;
  pkg_producer : nat;
  pkg_attested : bool;
  pkg_cert : option D
}.

Arguments pkg_id {D} p.
Arguments pkg_tier {D} p.
Arguments pkg_producer {D} p.
Arguments pkg_attested {D} p.
Arguments pkg_cert {D} p.

Definition read_cert (D : Type) (rd : Reading D) (p : Package D) : option Cert :=
  map_option rd p.(pkg_cert).

(* =========================================================================
   The machine: everything a composition fixes. Fields rather than
   Parameters, because a top-level Parameter prints as an assumption and fails
   the R-05-163 gate.
   ========================================================================= *)

Record Machine : Type := {

  (* --- R-13-011's per-tier required evidence, in R-05-036's facet
         vocabulary. R-13-012 states Tier 2's outright, as six of R-05-029's
         rows with the memory-safety row scoped to its temporal facet; the
         other two rows are witness values, which is gap b ---------------- *)

  required : Tier -> list Facet;

  (* --- R-11-005's and R-05-135b's four versions: a derivation produced
         against any other is not a verdict for this generation (gap f) --- *)

  admitted_versions : Versions;

  (* --- R-13-001c's composer, named so that a checker trusting its output is
         expressible and refutable rather than merely absent ---------------- *)

  composer_id : nat
}.

(* =========================================================================
   The ambient state a composer carries, which no admission rule may read.

   Two components and not one, because TAL-001's criterion has two halves:
   two runs over identical inputs return identical verdicts, which is the run
   index, and R-06-015b bounds a checker's reads to the candidate, its
   certificate and the profile, which is the state. A checker satisfying
   either half alone is exhibited below, so the file proves they are separate.
   ========================================================================= *)

Record Ambient : Type := {
  amb_run : nat;
  amb_state : nat
}.

Definition Checker (D : Type) : Type := Ambient -> Package D -> Verdict.

(* =========================================================================
   The check itself, in TAL-074's order.

   An absent derivation first, there being no certificate for phase 0 to read
   (R-13-003); then phase 0's own two comparisons, the version before the
   binding because TAL-008 makes an unimplemented version a rejection before
   the checker proceeds; then the tier, a header field phase 1 parses and the
   selection phases 3 to 5 decide against; then phase 2's recognition of every
   record; then the three move phases, deletions, citations and attributes, in
   that order.
   ========================================================================= *)

(* A record is recognised when all three of its codes decode. The judgment
   half is required to decode and nothing more is required of it, which is
   gap c; the move half is required to decode *and* to be the move the facet
   takes, which is R-05-037, R-05-038 and R-05-039 and is `discharges`. *)
Definition step_recognised (s : Step) : bool :=
  andb (andb (is_some (judgment_of_code s.(st_judgment)))
             (is_some (move_of_code s.(st_move))))
       (is_some (facet_of_code s.(st_facet))).

(* What it is for one record to discharge one facet: it names that facet, and
   it makes the move the move table assigns to it. A citation offered where an
   attribute is owed discharges nothing, and so does an attribute offered
   where a citation is owed, which is R-05-036's *no fourth mechanism* read
   from the side that has something to exclude. *)
Definition discharges (s : Step) (f : Facet) : bool :=
  match facet_of_code s.(st_facet), move_of_code s.(st_move) with
  | Some g, Some k => andb (facet_eqb f g) (move_eqb k (move_of f))
  | _, _ => false
  end.

(* Whether some record of the derivation discharges this facet. R-05-029's
   criterion is one discharge *for each* listed obligation and fixes no order
   and no multiplicity, which is reading 7 and is why this is `any_of` over
   the records rather than a walk in record order. *)
Definition discharged (c : Cert) (f : Facet) : bool :=
  any_of (fun s => discharges s f) c.(cert_steps).

Definition covers (m : Machine) (t : Tier) (c : Cert) : bool :=
  all_of (discharged c) (m.(required) t).

(* Membership over facets, which the phase-order lemmas quantify with. *)
Definition mem_facet (f : Facet) (l : list Facet) : bool :=
  any_of (fun g => facet_eqb f g) l.

Lemma mem_facet_here : forall (f : Facet) (l : list Facet), mem_facet f (cons f l) = true.
Proof. intros f l. unfold mem_facet. simpl. rewrite (facet_eqb_refl f). reflexivity. Qed.

Lemma mem_facet_app :
  forall (f : Facet) (x y : list Facet),
    mem_facet f (app x y) = orb (mem_facet f x) (mem_facet f y).
Proof.
  intros f x y. unfold mem_facet. induction x as [ | a s IH ].
  - reflexivity.
  - simpl. destruct (facet_eqb f a); simpl; [ reflexivity | exact IH ].
Qed.

Lemma all_of_mem :
  forall (q : Facet -> bool) (l : list Facet) (f : Facet),
    all_of q l = true -> mem_facet f l = true -> q f = true.
Proof.
  intros q l. induction l as [ | x r IH ]; intros f Ha Hm.
  - discriminate Hm.
  - simpl in Ha. destruct (andb_split _ _ Ha) as [ Hx Hr ].
    unfold mem_facet in Hm. simpl in Hm. destruct (facet_eqb f x) eqn:E.
    + rewrite (facet_eqb_true f x E). exact Hx.
    + simpl in Hm. exact (IH f Hr Hm).
Qed.

Lemma mem_all_of :
  forall (q : Facet -> bool) (l : list Facet),
    (forall f : Facet, mem_facet f l = true -> q f = true) -> all_of q l = true.
Proof.
  intros q l. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl. apply andb_join.
    + apply H. exact (mem_facet_here x r).
    + apply IH. intros f Hf. apply H. unfold mem_facet. simpl.
      unfold mem_facet in Hf. rewrite Hf. destruct (facet_eqb f x); reflexivity.
Qed.

(* TAL-074's phases 3, 4 and 5 as a reordering of a required set: the
   deletions first, the citations next, the attributes last. Nothing is added
   and nothing is dropped, every facet taking exactly one move. *)
Definition in_phase_order (l : list Facet) : list Facet :=
  app (facets_of_move_in ConfirmADeletion l)
      (app (facets_of_move_in CiteAnInvariant l)
           (facets_of_move_in EvaluateAnAttribute l)).

Lemma mem_facets_of_move_in :
  forall (f : Facet) (l : list Facet),
    mem_facet f l = true -> mem_facet f (facets_of_move_in (move_of f) l) = true.
Proof.
  intros f l. unfold facets_of_move_in. induction l as [ | x r IH ]; intros H.
  - discriminate H.
  - unfold mem_facet in H. simpl in H. destruct (facet_eqb f x) eqn:E.
    + rewrite (facet_eqb_true f x E). simpl.
      rewrite (move_eqb_refl (move_of x)). exact (mem_facet_here x _).
    + simpl in H. simpl. destruct (move_eqb (move_of x) (move_of f)).
      * unfold mem_facet. simpl. rewrite E. simpl.
        unfold mem_facet in IH. exact (IH H).
      * exact (IH H).
Qed.

Lemma the_facets_of_a_move_take_it :
  forall (k : Move) (l : list Facet) (g : Facet),
    mem_facet g (facets_of_move_in k l) = true -> move_of g = k.
Proof.
  intros k l. unfold facets_of_move_in. induction l as [ | x r IH ]; intros g H.
  - discriminate H.
  - simpl in H. destruct (move_eqb (move_of x) k) eqn:E.
    + unfold mem_facet in H. simpl in H. destruct (facet_eqb g x) eqn:Eg.
      * rewrite (facet_eqb_true g x Eg). exact (move_eqb_true _ _ E).
      * simpl in H. exact (IH g H).
    + exact (IH g H).
Qed.

Lemma mem_in_phase_order :
  forall (f : Facet) (l : list Facet),
    mem_facet f l = true -> mem_facet f (in_phase_order l) = true.
Proof.
  intros f l H. assert (Hk := mem_facets_of_move_in f l H).
  unfold in_phase_order.
  rewrite (mem_facet_app f _ _). rewrite (mem_facet_app f _ _).
  remember (move_of f) as k. destruct k; rewrite Hk.
  - destruct (mem_facet f (facets_of_move_in ConfirmADeletion l)); reflexivity.
  - destruct (mem_facet f (facets_of_move_in ConfirmADeletion l));
      destruct (mem_facet f (facets_of_move_in CiteAnInvariant l)); reflexivity.
  - reflexivity.
Qed.

Lemma in_phase_order_keeps_a_conjunction :
  forall (q : Facet -> bool) (l : list Facet),
    all_of q l = true -> all_of q (in_phase_order l) = true.
Proof.
  intros q l H. unfold in_phase_order. unfold facets_of_move_in.
  apply all_of_app_join.
  - apply (filter_of_within Facet _ q l H).
  - apply all_of_app_join; apply (filter_of_within Facet _ q l H).
Qed.

Lemma a_conjunction_over_the_phase_order_is_one_over_the_set :
  forall (q : Facet -> bool) (l : list Facet),
    all_of q (in_phase_order l) = true -> all_of q l = true.
Proof.
  intros q l H. apply mem_all_of. intros f Hf.
  exact (all_of_mem q (in_phase_order l) f H (mem_in_phase_order f l Hf)).
Qed.

(* The first failure of each kind, so that a refusal names a site rather than
   a fact. TAL-078's rejecting verdict names one requirement and one site, and
   these two are where the site comes from. *)
Fixpoint first_unrecognised (l : list Step) : option Step :=
  match l with
  | nil => None
  | cons s r => if step_recognised s then first_unrecognised r else Some s
  end.

Fixpoint first_undischarged (c : Cert) (l : list Facet) : option Facet :=
  match l with
  | nil => None
  | cons f r => if discharged c f then first_undischarged c r else Some f
  end.

Lemma first_unrecognised_none :
  forall l : list Step, first_unrecognised l = None -> all_of step_recognised l = true.
Proof.
  intros l. induction l as [ | s r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (step_recognised s) eqn:E.
    + simpl. rewrite E. simpl. exact (IH H).
    + discriminate H.
Qed.

Lemma first_unrecognised_some :
  forall (l : list Step) (s : Step),
    first_unrecognised l = Some s -> all_of step_recognised l = false.
Proof.
  intros l. induction l as [ | x r IH ]; intros s H.
  - discriminate H.
  - simpl in H. destruct (step_recognised x) eqn:E.
    + simpl. rewrite E. simpl. exact (IH s H).
    + simpl. rewrite E. reflexivity.
Qed.

Lemma all_recognised_first_none :
  forall l : list Step,
    all_of step_recognised l = true -> first_unrecognised l = None.
Proof.
  intros l. induction l as [ | s r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hs Hr ].
    simpl. rewrite Hs. exact (IH Hr).
Qed.

Lemma first_undischarged_none :
  forall (c : Cert) (l : list Facet),
    first_undischarged c l = None -> all_of (discharged c) l = true.
Proof.
  intros c l. induction l as [ | f r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (discharged c f) eqn:E.
    + simpl. rewrite E. simpl. exact (IH H).
    + discriminate H.
Qed.

Lemma first_undischarged_some :
  forall (c : Cert) (l : list Facet) (f : Facet),
    first_undischarged c l = Some f -> all_of (discharged c) l = false.
Proof.
  intros c l. induction l as [ | x r IH ]; intros f H.
  - discriminate H.
  - simpl in H. destruct (discharged c x) eqn:E.
    + simpl. rewrite E. simpl. exact (IH f H).
    + simpl. rewrite E. reflexivity.
Qed.

Lemma all_discharged_first_none :
  forall (c : Cert) (l : list Facet),
    all_of (discharged c) l = true -> first_undischarged c l = None.
Proof.
  intros c l. induction l as [ | f r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hf Hr ].
    simpl. rewrite Hf. exact (IH Hr).
Qed.

Lemma first_undischarged_app :
  forall (c : Cert) (x y : list Facet),
    first_undischarged c (app x y)
    = match first_undischarged c x with
      | Some g => Some g
      | None => first_undischarged c y
      end.
Proof.
  intros c x y. induction x as [ | a s IH ].
  - reflexivity.
  - simpl. destruct (discharged c a); [ exact IH | reflexivity ].
Qed.

Lemma first_undischarged_mem :
  forall (c : Cert) (l : list Facet) (g : Facet),
    first_undischarged c l = Some g -> mem_facet g l = true.
Proof.
  intros c l. induction l as [ | x r IH ]; intros g H.
  - discriminate H.
  - simpl in H. destruct (discharged c x) eqn:E.
    + unfold mem_facet. simpl. unfold mem_facet in IH. rewrite (IH g H).
      destruct (facet_eqb g x); reflexivity.
    + injection H as H2. rewrite <- H2. exact (mem_facet_here x r).
Qed.

Lemma first_undischarged_open :
  forall (c : Cert) (l : list Facet) (f : Facet),
    mem_facet f l = true -> discharged c f = false ->
    is_some (first_undischarged c l) = true.
Proof.
  intros c l. induction l as [ | x r IH ]; intros f Hm Hd.
  - discriminate Hm.
  - simpl. destruct (discharged c x) eqn:E.
    + apply (IH f); [ | exact Hd ].
      unfold mem_facet in Hm. simpl in Hm. destruct (facet_eqb f x) eqn:Ef.
      * rewrite (facet_eqb_true f x Ef) in Hd. rewrite E in Hd. discriminate Hd.
      * simpl in Hm. exact Hm.
    + reflexivity.
Qed.

(* An open facet breaks the coverage of its whole tier, which is the bridge
   between the facet-level clauses below and the set-level test. *)
Lemma an_open_facet_breaks_the_coverage :
  forall (m : Machine) (t : Tier) (c : Cert) (f : Facet),
    mem_facet f (m.(required) t) = true -> discharged c f = false ->
    covers m t c = false.
Proof.
  intros m t c f Hm Hd. destruct (covers m t c) eqn:E; [ | reflexivity ].
  unfold covers in E.
  rewrite (all_of_mem (discharged c) (m.(required) t) f E Hm) in Hd.
  discriminate Hd.
Qed.

(* TAL-074's *rejects at the first failure*, as the fact the walk order buys:
   whatever facet the phase-ordered walk stops at, its phase is no later than
   the phase of any facet of the set that is open. A walk in the machine's own
   declared order does not have this property, and the construction that takes
   one is refuted below. *)
Lemma the_first_open_facet_is_no_later :
  forall (c : Cert) (l : list Facet) (f g : Facet),
    mem_facet f l = true -> discharged c f = false ->
    first_undischarged c (in_phase_order l) = Some g ->
    Nat.leb (phase_rank (phase_of_move (move_of g)))
            (phase_rank (phase_of_move (move_of f))) = true.
Proof.
  intros c l f g Hm Hd Hf. unfold in_phase_order in Hf.
  rewrite (first_undischarged_app c (facets_of_move_in ConfirmADeletion l)
             (app (facets_of_move_in CiteAnInvariant l)
                  (facets_of_move_in EvaluateAnAttribute l))) in Hf.
  assert (Hk := mem_facets_of_move_in f l Hm).
  remember (move_of f) as kf. destruct kf.
  - destruct (first_undischarged c (facets_of_move_in ConfirmADeletion l))
      as [ h | ] eqn:EA.
    + injection Hf as Hf2. rewrite <- Hf2.
      rewrite (the_facets_of_a_move_take_it ConfirmADeletion l h
                 (first_undischarged_mem c _ h EA)). reflexivity.
    + rewrite (first_undischarged_app c (facets_of_move_in CiteAnInvariant l)
                 (facets_of_move_in EvaluateAnAttribute l)) in Hf.
      destruct (first_undischarged c (facets_of_move_in CiteAnInvariant l))
        as [ h | ] eqn:EB.
      * injection Hf as Hf2. rewrite <- Hf2.
        rewrite (the_facets_of_a_move_take_it CiteAnInvariant l h
                   (first_undischarged_mem c _ h EB)). reflexivity.
      * assert (Hop := first_undischarged_open c
                         (facets_of_move_in CiteAnInvariant l) f Hk Hd).
        rewrite EB in Hop. discriminate Hop.
  - destruct (move_of g); reflexivity.
  - destruct (first_undischarged c (facets_of_move_in ConfirmADeletion l))
      as [ h | ] eqn:EA.
    + injection Hf as Hf2. rewrite <- Hf2.
      rewrite (the_facets_of_a_move_take_it ConfirmADeletion l h
                 (first_undischarged_mem c _ h EA)). reflexivity.
    + assert (Hop := first_undischarged_open c
                       (facets_of_move_in ConfirmADeletion l) f Hk Hd).
      rewrite EA in Hop. discriminate Hop.
Qed.

(* The derivation half, over a certificate the reading has already produced.
   Its arguments are the identifier and the tier code the package claims, so a
   derivation binding to other bytes is refused rather than silently accepted
   for them, and a tier the checker does not recognise is refused before the
   phases that would have to guess a required set. *)
Definition check_cert (m : Machine) (id : nat) (tc : nat) (c : Cert) : Verdict :=
  if negb (versions_eqb c.(cert_versions) m.(admitted_versions))
  then Refused VersionMismatch id
  else if negb (Nat.eqb c.(cert_binds) id)
  then Refused BindingMismatch id
  else match tier_of_code tc with
       | None => Refused TierUnrecognised id
       | Some t =>
           match first_unrecognised c.(cert_steps) with
           | Some s => Refused FormUnrecognised s.(st_site)
           | None =>
               match first_undischarged c (in_phase_order (m.(required) t)) with
               | Some f => Refused (rule_of_move (move_of f)) (code_of_facet f)
               | None => Accepted
               end
           end
       end.

(* The specification's checker. The `Ambient` argument is taken and not read,
   which is what makes reading 1's obligation a property with something to
   exclude rather than a shape the type already forces. *)
Definition spec_check (m : Machine) (D : Type) (rd : Reading D) : Checker D :=
  fun _ p =>
    match p.(pkg_cert) with
    | None => Refused DerivationAbsent p.(pkg_id)
    | Some d => check_cert m p.(pkg_id) p.(pkg_tier) (rd d)
    end.

(* The four ways `check_cert` refuses past the version, as lemmas, so that a
   construction sharing that half of the algorithm inherits them rather than
   reproving them. *)
Lemma check_cert_refuses_a_stale_version :
  forall (m : Machine) (id tc : nat) (c : Cert),
    versions_eqb c.(cert_versions) m.(admitted_versions) = false ->
    accepts (check_cert m id tc c) = false.
Proof. intros m id tc c H. unfold check_cert. rewrite H. reflexivity. Qed.

Lemma check_cert_refuses_a_wrong_binding :
  forall (m : Machine) (id tc : nat) (c : Cert),
    Nat.eqb c.(cert_binds) id = false -> accepts (check_cert m id tc c) = false.
Proof.
  intros m id tc c H. unfold check_cert. rewrite H.
  destruct (negb (versions_eqb c.(cert_versions) m.(admitted_versions)));
    reflexivity.
Qed.

Lemma check_cert_refuses_an_unrecognised_tier :
  forall (m : Machine) (id tc : nat) (c : Cert),
    tier_of_code tc = None -> accepts (check_cert m id tc c) = false.
Proof.
  intros m id tc c H. unfold check_cert. rewrite H.
  destruct (negb (versions_eqb c.(cert_versions) m.(admitted_versions)));
    [ reflexivity | ].
  destruct (negb (Nat.eqb c.(cert_binds) id)); reflexivity.
Qed.

Lemma check_cert_refuses_an_unrecognised_form :
  forall (m : Machine) (id tc : nat) (c : Cert),
    all_of step_recognised c.(cert_steps) = false ->
    accepts (check_cert m id tc c) = false.
Proof.
  intros m id tc c H. unfold check_cert.
  destruct (negb (versions_eqb c.(cert_versions) m.(admitted_versions)));
    [ reflexivity | ].
  destruct (negb (Nat.eqb c.(cert_binds) id)); [ reflexivity | ].
  destruct (tier_of_code tc) as [ t | ]; [ | reflexivity ].
  destruct (first_unrecognised c.(cert_steps)) as [ s | ] eqn:E; [ reflexivity | ].
  rewrite (first_unrecognised_none c.(cert_steps) E) in H. discriminate H.
Qed.

Lemma check_cert_refuses_an_undischarged_facet :
  forall (m : Machine) (id tc : nat) (t : Tier) (c : Cert),
    tier_of_code tc = Some t -> covers m t c = false ->
    accepts (check_cert m id tc c) = false.
Proof.
  intros m id tc t c Ht H. unfold check_cert. rewrite Ht.
  destruct (negb (versions_eqb c.(cert_versions) m.(admitted_versions)));
    [ reflexivity | ].
  destruct (negb (Nat.eqb c.(cert_binds) id)); [ reflexivity | ].
  destruct (first_unrecognised c.(cert_steps)) as [ s | ]; [ reflexivity | ].
  destruct (first_undischarged c (in_phase_order (m.(required) t)))
    as [ f | ] eqn:E; [ reflexivity | ].
  unfold covers in H.
  rewrite (a_conjunction_over_the_phase_order_is_one_over_the_set
             (discharged c) (m.(required) t)
             (first_undischarged_none c _ E)) in H.
  discriminate H.
Qed.

(* =========================================================================
   Admission is a function of the package and its derivation (R-06-015b,
   R-13-001c, TAL-001), and that is two obligations rather than one.
   ========================================================================= *)

Definition ReadsNoComposerState (D : Type) (chk : Checker D) : Prop :=
  forall (a1 a2 : Ambient) (p : Package D),
    a1.(amb_run) = a2.(amb_run) -> chk a1 p = chk a2 p.

Definition IsRunIndependent (D : Type) (chk : Checker D) : Prop :=
  forall (a1 a2 : Ambient) (p : Package D),
    a1.(amb_state) = a2.(amb_state) -> chk a1 p = chk a2 p.

Definition IsAFunctionOfThePackage (D : Type) (chk : Checker D) : Prop :=
  forall (a1 a2 : Ambient) (p : Package D), chk a1 p = chk a2 p.

(* S1: the conjunction is what the two halves buy, and the proof is where the
   two meet: an ambient carrying one run and the other state mediates between
   them, so neither half alone is the property and the two together are. *)
Theorem the_two_halves_compose :
  forall (D : Type) (chk : Checker D),
    ReadsNoComposerState D chk -> IsRunIndependent D chk ->
    IsAFunctionOfThePackage D chk.
Proof.
  intros D chk Hstate Hrun a1 a2 p.
  assert (H1 : chk a1 p
               = chk {| amb_run := a1.(amb_run); amb_state := a2.(amb_state) |} p)
    by exact (Hstate a1 {| amb_run := a1.(amb_run);
                           amb_state := a2.(amb_state) |} p eq_refl).
  assert (H2 : chk {| amb_run := a1.(amb_run); amb_state := a2.(amb_state) |} p
               = chk a2 p)
    by exact (Hrun {| amb_run := a1.(amb_run);
                      amb_state := a2.(amb_state) |} a2 p eq_refl).
  rewrite H1. exact H2.
Qed.

Theorem the_conjunction_gives_back_both_halves :
  forall (D : Type) (chk : Checker D),
    IsAFunctionOfThePackage D chk ->
    ReadsNoComposerState D chk /\ IsRunIndependent D chk.
Proof.
  intros D chk H. split.
  - intros a1 a2 p H2. exact (H a1 a2 p).
  - intros a1 a2 p H2. exact (H a1 a2 p).
Qed.

(* S2 (R-06-015b, TAL-001). *)
Theorem the_specification_is_a_function_of_the_package :
  forall (m : Machine) (D : Type) (rd : Reading D),
    IsAFunctionOfThePackage D (spec_check m D rd).
Proof. intros m D rd a1 a2 p. reflexivity. Qed.

(* TAL-001's criterion has a second half, *identical rejection sites*, and it
   is a predicate of its own rather than a decoration on the first: a checker
   may name one rule on every run and move the site with the run, and another
   may hold the site and move the rule. Both are exhibited below, so neither
   half implies the other. *)
Definition NamesAStableRule (D : Type) (chk : Checker D) : Prop :=
  forall (a1 a2 : Ambient) (p : Package D), rule_of (chk a1 p) = rule_of (chk a2 p).

Definition NamesAStableSite (D : Type) (chk : Checker D) : Prop :=
  forall (a1 a2 : Ambient) (p : Package D), site_of (chk a1 p) = site_of (chk a2 p).

Theorem a_function_of_the_package_names_a_stable_rule_and_site :
  forall (D : Type) (chk : Checker D),
    IsAFunctionOfThePackage D chk -> NamesAStableRule D chk /\ NamesAStableSite D chk.
Proof.
  intros D chk H. split; intros a1 a2 p; rewrite (H a1 a2 p); reflexivity.
Qed.

(* S19 (TAL-001's second half at the specification). *)
Theorem the_specification_names_a_stable_rule_and_site :
  forall (m : Machine) (D : Type) (rd : Reading D),
    NamesAStableRule D (spec_check m D rd) /\ NamesAStableSite D (spec_check m D rd).
Proof.
  intros m D rd.
  exact (a_function_of_the_package_names_a_stable_rule_and_site D (spec_check m D rd)
           (the_specification_is_a_function_of_the_package m D rd)).
Qed.

(* =========================================================================
   The verdict is a function of the reading and not of the carrier behind it
   (R-13-003, and the reason M6.2b's term language is not chosen here).

   This is an obligation over an arbitrary checker rather than a shape the
   type forces: two values of one carrier may read alike, and a checker that
   tells them apart is definable and is refuted below.
   ========================================================================= *)

Definition IsAFunctionOfTheReading (D : Type) (rd : Reading D)
    (chk : Checker D) : Prop :=
  forall (a b : Ambient) (p q : Package D),
    p.(pkg_id) = q.(pkg_id) ->
    p.(pkg_tier) = q.(pkg_tier) ->
    read_cert D rd p = read_cert D rd q ->
    chk a p = chk b q.

Definition reads_alike (D E : Type) (rd : Reading D) (re : Reading E)
    (p : Package D) (q : Package E) : Prop :=
  p.(pkg_id) = q.(pkg_id)
  /\ p.(pkg_tier) = q.(pkg_tier)
  /\ read_cert D rd p = read_cert E re q.

(* S3: two packages over two different carriers that read the same get the
   same verdict, whatever ambient either was checked in. This is reading 3
   made checkable across carriers; the single-carrier obligation above is what
   a construction can break. *)
Theorem the_verdict_is_a_function_of_the_reading :
  forall (m : Machine) (D E : Type) (rd : Reading D) (re : Reading E)
         (a b : Ambient) (p : Package D) (q : Package E),
    reads_alike D E rd re p q ->
    spec_check m D rd a p = spec_check m E re b q.
Proof.
  intros m D E rd re a b p q H. destruct H as [ Hid H2 ]. destruct H2 as [ Ht Hc ].
  unfold spec_check. unfold read_cert in Hc. unfold map_option in Hc.
  rewrite Ht. rewrite Hid.
  remember (pkg_cert p) as cp. remember (pkg_cert q) as cq.
  destruct cp as [ d | ]; destruct cq as [ e | ]; try discriminate Hc.
  - injection Hc as Hc2. rewrite Hc2. reflexivity.
  - reflexivity.
Qed.

Theorem the_specification_is_a_function_of_the_reading :
  forall (m : Machine) (D : Type) (rd : Reading D),
    IsAFunctionOfTheReading D rd (spec_check m D rd).
Proof.
  intros m D rd a b p q Hid Ht Hc.
  exact (the_verdict_is_a_function_of_the_reading m D D rd rd a b p q
           (conj Hid (conj Ht Hc))).
Qed.

(* =========================================================================
   The typing relation, and soundness stated against it (R-13-022, R-06-009,
   R-17-033).

   R-13-022 puts the gate on the derivation and the source-correspondence
   theorem rather than on the toolchain, so the property a checker owes is
   stated against the relation *well-typed* and not against a proof language.
   That is what keeps this file's obligation independent of M6.2b: the
   relation below quantifies over the carrier and mentions no term.
   ========================================================================= *)

Definition Typing (D : Type) : Type := Package D -> Prop.

Definition SoundFor (D : Type) (T : Typing D) (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D), accepts (chk a p) = true -> T p.

Definition CompleteFor (D : Type) (T : Typing D) (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D), T p -> accepts (chk a p) = true.

(* The relation the specification decides. Every conjunct is one of R-05-029's
   or R-13-003's or R-11-005's own clauses, and none is a fact about a proof
   term: a derivation is present, it was produced against the admitted
   versions, it binds to these bytes, the package claims a tier the checker
   recognises, every record it carries names a form, a move and a facet the
   checker recognises, and it discharges every facet the package's tier
   requires by the move that facet's own row of the move table assigns. *)
Definition WellTyped (m : Machine) (D : Type) (rd : Reading D) : Typing D :=
  fun p => exists (d : D) (t : Tier),
    p.(pkg_cert) = Some d
    /\ (rd d).(cert_versions) = m.(admitted_versions)
    /\ (rd d).(cert_binds) = p.(pkg_id)
    /\ tier_of_code p.(pkg_tier) = Some t
    /\ all_of step_recognised (rd d).(cert_steps) = true
    /\ covers m t (rd d) = true.

(* Fail-closed is soundness against that relation and nothing weaker: a
   checker that accepts is a checker whose acceptance the relation carries.
   R-13-014's *no admitted path runs code that failed a check* and R-13-025's
   *admission gates and never relaxes* are the two entries this reads. *)
Definition FailsClosed (m : Machine) (D : Type) (rd : Reading D)
    (chk : Checker D) : Prop :=
  SoundFor D (WellTyped m D rd) chk.

(* S4 (R-13-014, R-13-022, R-06-009). *)
Theorem the_specification_fails_closed :
  forall (m : Machine) (D : Type) (rd : Reading D),
    FailsClosed m D rd (spec_check m D rd).
Proof.
  intros m D rd a p H. unfold FailsClosed in *. unfold spec_check in H.
  remember (pkg_cert p) as cp.
  destruct cp as [ d | ]; [ | discriminate H ].
  unfold check_cert in H.
  destruct (versions_eqb (cert_versions (rd d)) (admitted_versions m)) eqn:Ev;
    [ | simpl in H; discriminate H ].
  simpl in H.
  destruct (Nat.eqb (cert_binds (rd d)) (pkg_id p)) eqn:Eb;
    [ | simpl in H; discriminate H ].
  simpl in H.
  destruct (tier_of_code (pkg_tier p)) as [ t | ] eqn:Et; [ | discriminate H ].
  destruct (first_unrecognised (cert_steps (rd d))) as [ s | ] eqn:Eu;
    [ discriminate H | ].
  destruct (first_undischarged (rd d) (in_phase_order (required m t)))
    as [ f | ] eqn:Ed; [ discriminate H | ].
  exists d. exists t. split; [ symmetry; exact Heqcp | ].
  split; [ exact (versions_eqb_true _ _ Ev) | ].
  split; [ exact (nat_eqb_true _ _ Eb) | ].
  split; [ exact Et | ].
  split; [ exact (first_unrecognised_none _ Eu) | ].
  unfold covers.
  exact (a_conjunction_over_the_phase_order_is_one_over_the_set
           (discharged (rd d)) (required m t) (first_undischarged_none _ _ Ed)).
Qed.

(* S5: and it is complete for the same relation, so the fail-closed theorem is
   not proved by a checker that refuses everything. The two are separate
   obligations and R-17-033 is what says so in the register's own words: a
   producer that cannot emit a valid derivation for a safe program costs
   availability, and one whose output is admitted without one costs safety. *)
Theorem the_specification_is_complete_for_the_typing_relation :
  forall (m : Machine) (D : Type) (rd : Reading D),
    CompleteFor D (WellTyped m D rd) (spec_check m D rd).
Proof.
  intros m D rd a p H.
  destruct H as [ d H1 ]. destruct H1 as [ t H2 ].
  destruct H2 as [ Hc H3 ]. destruct H3 as [ Hv H4 ].
  destruct H4 as [ Hb H5 ]. destruct H5 as [ Ht H6 ]. destruct H6 as [ Hr Hcov ].
  unfold spec_check. rewrite Hc. unfold check_cert.
  rewrite Hv. rewrite Hb. rewrite (versions_eqb_refl (admitted_versions m)).
  rewrite (nat_eqb_refl (pkg_id p)). simpl. rewrite Ht.
  rewrite (all_recognised_first_none (cert_steps (rd d)) Hr).
  unfold covers in Hcov.
  rewrite (all_discharged_first_none (rd d) (in_phase_order (required m t))
             (in_phase_order_keeps_a_conjunction (discharged (rd d))
                (required m t) Hcov)).
  reflexivity.
Qed.

(* =========================================================================
   The eight named refusals, each stated of an arbitrary checker.

   Fail-closed above is one property; these eight are the clauses it
   decomposes into, and they are stated apart because a construction can
   satisfy any seven and break the eighth. The generated `waiving` family
   below exhibits exactly that, and one theorem per clause links the waiving
   to the negation of that clause rather than leaving the exhibition asserted.
   ========================================================================= *)

Definition RefusesAnAbsentDerivation (D : Type) (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D),
    p.(pkg_cert) = None -> accepts (chk a p) = false.

Definition RefusesAStaleVersion (m : Machine) (D : Type) (rd : Reading D)
    (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D) (d : D),
    p.(pkg_cert) = Some d ->
    versions_eqb (rd d).(cert_versions) m.(admitted_versions) = false ->
    accepts (chk a p) = false.

Definition RefusesAWrongBinding (D : Type) (rd : Reading D)
    (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D) (d : D),
    p.(pkg_cert) = Some d ->
    Nat.eqb (rd d).(cert_binds) p.(pkg_id) = false ->
    accepts (chk a p) = false.

Definition RefusesAnUnrecognisedTier (D : Type) (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D),
    tier_of_code p.(pkg_tier) = None -> accepts (chk a p) = false.

Definition RefusesAnUnrecognisedForm (D : Type) (rd : Reading D)
    (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D) (d : D),
    p.(pkg_cert) = Some d ->
    all_of step_recognised (rd d).(cert_steps) = false ->
    accepts (chk a p) = false.

(* One definition for the three coverage clauses, indexed by the move the
   facet takes: R-05-039's deletions, R-05-037's citations and R-05-038's
   attributes are three phases of TAL-074 and three clauses here, and a
   checker can keep two of them and break the third. *)
Definition RefusesAnUndischargedFacetOf (m : Machine) (D : Type) (rd : Reading D)
    (k : Move) (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D) (d : D) (t : Tier) (f : Facet),
    p.(pkg_cert) = Some d ->
    tier_of_code p.(pkg_tier) = Some t ->
    mem_facet f (m.(required) t) = true ->
    move_of f = k ->
    discharged (rd d) f = false ->
    accepts (chk a p) = false.

(* Each of the eight is a consequence of fail-closed rather than a ninth
   obligation, which is what makes the decomposition a reading of one property
   rather than eight properties. Stated of an arbitrary checker, so the
   constructions below are refuted by the clause they break. *)
Theorem fail_closed_refuses_an_absent_derivation :
  forall (m : Machine) (D : Type) (rd : Reading D) (chk : Checker D),
    FailsClosed m D rd chk -> RefusesAnAbsentDerivation D chk.
Proof.
  intros m D rd chk Hfc a p Hc.
  destruct (accepts (chk a p)) eqn:E; [ | reflexivity ].
  destruct (Hfc a p E) as [ d H1 ]. destruct H1 as [ t H2 ].
  destruct H2 as [ Hd _ ]. rewrite Hc in Hd. discriminate Hd.
Qed.

Theorem fail_closed_refuses_a_stale_version :
  forall (m : Machine) (D : Type) (rd : Reading D) (chk : Checker D),
    FailsClosed m D rd chk -> RefusesAStaleVersion m D rd chk.
Proof.
  intros m D rd chk Hfc a p d Hc Hv.
  destruct (accepts (chk a p)) eqn:E; [ | reflexivity ].
  destruct (Hfc a p E) as [ e H1 ]. destruct H1 as [ t H2 ].
  destruct H2 as [ Hd H3 ]. destruct H3 as [ Hver _ ].
  rewrite Hc in Hd. injection Hd as Hd2. rewrite <- Hd2 in Hver.
  rewrite Hver in Hv. rewrite (versions_eqb_refl (admitted_versions m)) in Hv.
  discriminate Hv.
Qed.

Theorem fail_closed_refuses_a_wrong_binding :
  forall (m : Machine) (D : Type) (rd : Reading D) (chk : Checker D),
    FailsClosed m D rd chk -> RefusesAWrongBinding D rd chk.
Proof.
  intros m D rd chk Hfc a p d Hc Hb.
  destruct (accepts (chk a p)) eqn:E; [ | reflexivity ].
  destruct (Hfc a p E) as [ e H1 ]. destruct H1 as [ t H2 ].
  destruct H2 as [ Hd H3 ]. destruct H3 as [ _ H4 ]. destruct H4 as [ Hbind _ ].
  rewrite Hc in Hd. injection Hd as Hd2. rewrite <- Hd2 in Hbind.
  rewrite Hbind in Hb. rewrite (nat_eqb_refl (pkg_id p)) in Hb.
  discriminate Hb.
Qed.

Theorem fail_closed_refuses_an_unrecognised_tier :
  forall (m : Machine) (D : Type) (rd : Reading D) (chk : Checker D),
    FailsClosed m D rd chk -> RefusesAnUnrecognisedTier D chk.
Proof.
  intros m D rd chk Hfc a p Ht.
  destruct (accepts (chk a p)) eqn:E; [ | reflexivity ].
  destruct (Hfc a p E) as [ d H1 ]. destruct H1 as [ t H2 ].
  destruct H2 as [ _ H3 ]. destruct H3 as [ _ H4 ]. destruct H4 as [ _ H5 ].
  destruct H5 as [ Hd _ ]. rewrite Ht in Hd. discriminate Hd.
Qed.

Theorem fail_closed_refuses_an_unrecognised_form :
  forall (m : Machine) (D : Type) (rd : Reading D) (chk : Checker D),
    FailsClosed m D rd chk -> RefusesAnUnrecognisedForm D rd chk.
Proof.
  intros m D rd chk Hfc a p d Hc Hr.
  destruct (accepts (chk a p)) eqn:E; [ | reflexivity ].
  destruct (Hfc a p E) as [ e H1 ]. destruct H1 as [ t H2 ].
  destruct H2 as [ Hd H3 ]. destruct H3 as [ _ H4 ]. destruct H4 as [ _ H5 ].
  destruct H5 as [ _ H6 ]. destruct H6 as [ Hrec _ ].
  rewrite Hc in Hd. injection Hd as Hd2. rewrite <- Hd2 in Hrec.
  rewrite Hrec in Hr. discriminate Hr.
Qed.

Theorem fail_closed_refuses_an_undischarged_facet :
  forall (m : Machine) (D : Type) (rd : Reading D) (k : Move) (chk : Checker D),
    FailsClosed m D rd chk -> RefusesAnUndischargedFacetOf m D rd k chk.
Proof.
  intros m D rd k chk Hfc a p d t f Hc Ht Hm Hk Hd.
  destruct (accepts (chk a p)) eqn:E; [ | reflexivity ].
  destruct (Hfc a p E) as [ e H1 ]. destruct H1 as [ u H2 ].
  destruct H2 as [ He H3 ]. destruct H3 as [ _ H4 ]. destruct H4 as [ _ H5 ].
  destruct H5 as [ Hu H6 ]. destruct H6 as [ _ Hcov ].
  rewrite Hc in He. injection He as He2. rewrite <- He2 in Hcov.
  rewrite Ht in Hu. injection Hu as Hu2. rewrite <- Hu2 in Hcov.
  rewrite (an_open_facet_breaks_the_coverage m t (rd d) f Hm Hd) in Hcov.
  discriminate Hcov.
Qed.

(* S18: the specification satisfies all eight, which is
   `the_specification_fails_closed` read clause by clause. *)
Theorem the_specification_satisfies_every_named_refusal :
  forall (m : Machine) (D : Type) (rd : Reading D),
    RefusesAnAbsentDerivation D (spec_check m D rd)
    /\ RefusesAStaleVersion m D rd (spec_check m D rd)
    /\ RefusesAWrongBinding D rd (spec_check m D rd)
    /\ RefusesAnUnrecognisedTier D (spec_check m D rd)
    /\ RefusesAnUnrecognisedForm D rd (spec_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd ConfirmADeletion (spec_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd CiteAnInvariant (spec_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd EvaluateAnAttribute (spec_check m D rd).
Proof.
  intros m D rd.
  split.
  { exact (fail_closed_refuses_an_absent_derivation m D rd (spec_check m D rd)
             (the_specification_fails_closed m D rd)). }
  split.
  { exact (fail_closed_refuses_a_stale_version m D rd (spec_check m D rd)
             (the_specification_fails_closed m D rd)). }
  split.
  { exact (fail_closed_refuses_a_wrong_binding m D rd (spec_check m D rd)
             (the_specification_fails_closed m D rd)). }
  split.
  { exact (fail_closed_refuses_an_unrecognised_tier m D rd (spec_check m D rd)
             (the_specification_fails_closed m D rd)). }
  split.
  { exact (fail_closed_refuses_an_unrecognised_form m D rd (spec_check m D rd)
             (the_specification_fails_closed m D rd)). }
  split.
  { exact (fail_closed_refuses_an_undischarged_facet m D rd ConfirmADeletion
             (spec_check m D rd) (the_specification_fails_closed m D rd)). }
  split.
  { exact (fail_closed_refuses_an_undischarged_facet m D rd CiteAnInvariant
             (spec_check m D rd) (the_specification_fails_closed m D rd)). }
  exact (fail_closed_refuses_an_undischarged_facet m D rd EvaluateAnAttribute
           (spec_check m D rd) (the_specification_fails_closed m D rd)).
Qed.

(* =========================================================================
   The phase order as an obligation (TAL-074).

   *The checker runs these six phases in this order, and rejects at the first
   failure.* A checker that walks a tier's required set in the order the
   machine declares it satisfies every clause above and still names a later
   phase's refusal while an earlier phase's facet is open, so this is a
   property of its own and is refuted of that construction below.
   ========================================================================= *)

Definition phase_of_verdict (v : Verdict) : option Phase :=
  match v with Accepted => None | Refused r _ => Some (phase_of_rule r) end.

Definition no_later_than (v : Verdict) (q : Phase) : bool :=
  match phase_of_verdict v with
  | None => false
  | Some s => Nat.leb (phase_rank s) (phase_rank q)
  end.

Definition RejectsAtTheEarliestOpenPhase (m : Machine) (D : Type) (rd : Reading D)
    (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D) (d : D) (t : Tier) (f : Facet),
    p.(pkg_cert) = Some d ->
    tier_of_code p.(pkg_tier) = Some t ->
    mem_facet f (m.(required) t) = true ->
    discharged (rd d) f = false ->
    no_later_than (chk a p) (phase_of_move (move_of f)) = true.

Theorem the_specification_rejects_at_the_earliest_open_phase :
  forall (m : Machine) (D : Type) (rd : Reading D),
    RejectsAtTheEarliestOpenPhase m D rd (spec_check m D rd).
Proof.
  intros m D rd a p d t f Hc Ht Hm Hd.
  unfold spec_check. rewrite Hc. unfold check_cert.
  destruct (negb (versions_eqb (cert_versions (rd d)) (admitted_versions m))).
  { unfold no_later_than. simpl. destruct (move_of f); reflexivity. }
  destruct (negb (Nat.eqb (cert_binds (rd d)) (pkg_id p))).
  { unfold no_later_than. simpl. destruct (move_of f); reflexivity. }
  rewrite Ht.
  destruct (first_unrecognised (cert_steps (rd d))) as [ s | ].
  { unfold no_later_than. simpl. destruct (move_of f); reflexivity. }
  destruct (first_undischarged (rd d) (in_phase_order (required m t)))
    as [ g | ] eqn:Eg.
  - unfold no_later_than. simpl.
    rewrite (the_move_phases_and_the_move_rules_agree (move_of g)).
    exact (the_first_open_facet_is_no_later (rd d) (required m t) f g Hm Hd Eg).
  - assert (Hop := first_undischarged_open (rd d)
                     (in_phase_order (required m t)) f
                     (mem_in_phase_order f (required m t) Hm) Hd).
    rewrite Eg in Hop. discriminate Hop.
Qed.

(* The clause above constrains the three move phases and says nothing about
   the three before them, so the order there is stated as three clauses of its
   own, each an adjacent pair of the phase enumeration and each refuted by a
   construction that hoists the later phase above the earlier one. The first
   of the three is the only ordering judgment in this file that TAL-074 does
   not fix, phase 0 carrying both the commitment recomputation and the version
   comparison and that requirement not ordering them against each other; it is
   stated here rather than left as prose for exactly that reason. *)

(* TAL-008: a checker rejects a certificate naming a version it does not
   implement, and rejects it *before proceeding*, so a stale version is what
   the verdict names whatever else the package carries. *)
Definition RefusesUnderTheStaleVersionFirst (m : Machine) (D : Type)
    (rd : Reading D) (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D) (d : D),
    p.(pkg_cert) = Some d ->
    versions_eqb (rd d).(cert_versions) m.(admitted_versions) = false ->
    rule_of (chk a p) = Some VersionMismatch.

(* TAL-074's phase 0 before its phase 1: the commitment is recomputed over the
   installed bytes before the certificate is parsed, and the tier is a header
   field the parse reads, so a package whose binding and whose tier are both
   wrong is refused under the binding. *)
Definition RefusesUnderTheWrongBindingBeforeTheTier (m : Machine) (D : Type)
    (rd : Reading D) (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D) (d : D),
    p.(pkg_cert) = Some d ->
    versions_eqb (rd d).(cert_versions) m.(admitted_versions) = true ->
    Nat.eqb (rd d).(cert_binds) p.(pkg_id) = false ->
    rule_of (chk a p) = Some BindingMismatch.

(* TAL-074's phase 1 before its phase 2: an unrecognised tier decides nothing
   about the records, and the facet set phases 3 to 5 read is what it selects,
   so a package whose tier and whose records are both unrecognised is refused
   under the tier. *)
Definition RefusesUnderTheUnrecognisedTierBeforeTheForm (m : Machine) (D : Type)
    (rd : Reading D) (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D) (d : D),
    p.(pkg_cert) = Some d ->
    versions_eqb (rd d).(cert_versions) m.(admitted_versions) = true ->
    Nat.eqb (rd d).(cert_binds) p.(pkg_id) = true ->
    tier_of_code p.(pkg_tier) = None ->
    rule_of (chk a p) = Some TierUnrecognised.

Theorem the_specification_refuses_in_the_early_phase_order :
  forall (m : Machine) (D : Type) (rd : Reading D),
    RefusesUnderTheStaleVersionFirst m D rd (spec_check m D rd)
    /\ RefusesUnderTheWrongBindingBeforeTheTier m D rd (spec_check m D rd)
    /\ RefusesUnderTheUnrecognisedTierBeforeTheForm m D rd (spec_check m D rd).
Proof.
  intros m D rd. split.
  { intros a p d Hc Hv. unfold spec_check. rewrite Hc. unfold check_cert.
    rewrite Hv. reflexivity. }
  split.
  { intros a p d Hc Hv Hb. unfold spec_check. rewrite Hc. unfold check_cert.
    rewrite Hv. simpl. rewrite Hb. reflexivity. }
  intros a p d Hc Hv Hb Ht. unfold spec_check. rewrite Hc. unfold check_cert.
  rewrite Hv. simpl. rewrite Hb. simpl. rewrite Ht. reflexivity.
Qed.

(* =========================================================================
   The generated family of unsound checkers: one per refusal rule.

   `waiving r` is the checker that accepts exactly what rule `r` alone
   refused. It is the natural weakening of a fail-closed checker, and stating
   it as a generator over the rule enumeration rather than as eight authored
   constructions is what makes the twin discipline one theorem: the waived
   checker keeps every rule but its own, and drops its own.
   ========================================================================= *)

Definition waiving (r : RuleId) (D : Type) (chk : Checker D) : Checker D :=
  fun a p => match chk a p with
             | Accepted => Accepted
             | Refused r2 s => if rule_eqb r r2 then Accepted else Refused r2 s
             end.

(* What it is for a checker to keep a rule of some other checker's: wherever
   the base refuses under that rule, this one refuses too. *)
Definition RefusesUnder (D : Type) (base : Checker D) (r : RuleId)
    (chk : Checker D) : Prop :=
  forall (a : Ambient) (p : Package D),
    rule_of (base a p) = Some r -> accepts (chk a p) = false.

(* S7 (the twin, first half): waiving one rule keeps every other. Stated of an
   arbitrary base checker and an arbitrary pair of distinct rules, so the
   whole family is covered by one theorem rather than by eight. *)
Theorem waiving_one_rule_keeps_every_other :
  forall (D : Type) (base : Checker D) (r r2 : RuleId),
    rule_eqb r r2 = false -> RefusesUnder D base r2 (waiving r D base).
Proof.
  intros D base r r2 Hne a p H. unfold waiving.
  remember (base a p) as v. destruct v as [ | r3 s ].
  - simpl in H. discriminate H.
  - simpl in H. injection H as H2. rewrite <- H2 in Hne. rewrite Hne. reflexivity.
Qed.

(* S8 (the twin, second half): and it drops its own, wherever the base uses
   it. So the eight clauses of fail-closed are eight obligations and not one
   stated eight times: for each, a construction satisfying the other seven. *)
Theorem waiving_a_rule_admits_what_that_rule_refused :
  forall (D : Type) (base : Checker D) (r : RuleId) (a : Ambient) (p : Package D),
    rule_of (base a p) = Some r -> accepts (waiving r D base a p) = true.
Proof.
  intros D base r a p H. unfold waiving.
  remember (base a p) as v. destruct v as [ | r2 s ].
  - simpl in H. discriminate H.
  - simpl in H. injection H as H2. rewrite H2. rewrite (rule_eqb_refl r).
    reflexivity.
Qed.

(* S9: and every waiving is therefore unsound, wherever its rule is reachable.
   Stated of an arbitrary base, an arbitrary rule and an arbitrary witness,
   with the demo roster below supplying a witness for each of the eight. *)
Theorem a_reachable_waived_rule_breaks_fail_closed :
  forall (m : Machine) (D : Type) (rd : Reading D) (r : RuleId)
         (a : Ambient) (p : Package D),
    rule_of (spec_check m D rd a p) = Some r ->
    ~ FailsClosed m D rd (waiving r D (spec_check m D rd)).
Proof.
  intros m D rd r a p H Hfc.
  assert (Hacc : accepts (waiving r D (spec_check m D rd) a p) = true)
    by exact (waiving_a_rule_admits_what_that_rule_refused D (spec_check m D rd) r a p H).
  assert (Hwt : WellTyped m D rd p) by exact (Hfc a p Hacc).
  assert (Hspec : accepts (spec_check m D rd a p) = true)
    by exact (the_specification_is_complete_for_the_typing_relation m D rd a p Hwt).
  destruct (spec_check m D rd a p) as [ | r2 s ];
    [ simpl in H; discriminate H | simpl in Hspec; discriminate Hspec ].
Qed.

(* =========================================================================
   The checker joins no trust base (R-13-001c, R-13-013, R-13-022).

   R-13-013's criterion is that no admission rule reads a producer identity,
   and R-13-001c's is that the composer accordingly joins no trust base and
   may be any party. This is not the same obligation as reading no composer
   state, and the separation runs in both directions: a producer identity is a
   field of the package, so a checker reading it is still a function of the
   package, and a composer's state is not a field of the package, so a checker
   reading that reads no pedigree. Both directions are exhibited below.
   ========================================================================= *)

Definition same_but_the_pedigree (D : Type) (p q : Package D) : Prop :=
  p.(pkg_id) = q.(pkg_id)
  /\ p.(pkg_tier) = q.(pkg_tier)
  /\ p.(pkg_cert) = q.(pkg_cert).

Definition ReadsNoPedigree (D : Type) (chk : Checker D) : Prop :=
  forall (a : Ambient) (p q : Package D),
    same_but_the_pedigree D p q -> chk a p = chk a q.

(* S10 (R-13-013): removing every producer attestation changes no verdict. *)
Theorem the_specification_reads_no_pedigree :
  forall (m : Machine) (D : Type) (rd : Reading D),
    ReadsNoPedigree D (spec_check m D rd).
Proof.
  intros m D rd a p q H.
  destruct H as [ Hid H1 ]. destruct H1 as [ Ht Hc ].
  unfold spec_check. rewrite Ht. rewrite Hid. rewrite Hc. reflexivity.
Qed.

(* And R-13-013's own sentence as a consequence: a package admitted under one
   producer is admitted under any, which is *any producer of a well-typed
   binary is admitted identically* stated where it can be refuted. *)
Theorem admission_does_not_move_with_the_producer :
  forall (m : Machine) (D : Type) (rd : Reading D) (a : Ambient)
         (p : Package D) (who : nat) (att : bool),
    spec_check m D rd a p
    = spec_check m D rd a {| pkg_id := p.(pkg_id); pkg_tier := p.(pkg_tier);
                             pkg_producer := who; pkg_attested := att;
                             pkg_cert := p.(pkg_cert) |}.
Proof.
  intros m D rd a p who att.
  apply (the_specification_reads_no_pedigree m D rd a).
  split; [ reflexivity | ]. split; reflexivity.
Qed.

(* =========================================================================
   The composer, and what a rejection being total means of it.

   R-11-005 has the transactor commit a generation only after the checker
   validates *every* new binary's proof, R-13-001a makes an install a
   generation rather than an amendment to one and therefore atomic, and
   R-13-001c has a composer that gets its inputs wrong fail admission rather
   than ship. So the codomain is a generation or nothing: one refused package
   costs the generation, not itself.

   A generation is more than the image, because R-13-010b's whole-image
   duplication pass emits *one shared service compartment in place of a
   library statically linked into each consumer*, which is a component no
   roster names and which R-13-001c requires the pass to emit a derivation
   covering. So the generation carries the image and the identifiers the
   passes synthesized, and the obligation about strangers is coverage rather
   than absence.
   ========================================================================= *)

Definition Roster (D : Type) : Type := list (Package D).

Record Generation (D : Type) : Type := {
  gen_image : list (Package D);
  gen_synthesized : list nat
}.

Arguments gen_image {D} g.
Arguments gen_synthesized {D} g.

Definition Composer (D : Type) : Type := Ambient -> Roster D -> option (Generation D).

Definition image_ids (D : Type) (r : list (Package D)) : list nat :=
  map_over (fun p => p.(pkg_id)) r.

Definition admissible (m : Machine) (D : Type) (rd : Reading D) (a : Ambient)
    (r : Roster D) : bool :=
  all_of (fun p => accepts (spec_check m D rd a p)) r.

Definition spec_compose (m : Machine) (D : Type) (rd : Reading D) : Composer D :=
  fun a r => if admissible m D rd a r
             then Some {| gen_image := r; gen_synthesized := nil |}
             else None.

(* The five obligations a composer carries. *)

(* R-11-005, R-13-001a, R-13-001c: a roster the checker does not admit whole
   yields no generation at all. This is the obligation the filtering composer
   below breaks and every other one keeps. *)
Definition IsAllOrNothing (m : Machine) (D : Type) (rd : Reading D)
    (cmp : Composer D) : Prop :=
  forall (a : Ambient) (r : Roster D),
    admissible m D rd a r = false -> cmp a r = None.

(* R-11-005: every binary a committed generation carries was validated. *)
Definition CommitsOnlyTheAccepted (m : Machine) (D : Type) (rd : Reading D)
    (cmp : Composer D) : Prop :=
  forall (a : Ambient) (r : Roster D) (g : Generation D),
    cmp a r = Some g ->
    all_of (fun p => accepts (spec_check m D rd a p)) g.(gen_image) = true.

(* R-13-001c's *the device names the roster it wants*, widened by R-13-010b's
   shared service compartment: a package in the image is named by the roster
   or is declared as a whole-image pass's own product. Stating it as absence
   rather than as coverage would forbid the pass R-13-010b requires. *)
Definition EmitsNoUncoveredStranger (D : Type) (cmp : Composer D) : Prop :=
  forall (a : Ambient) (r : Roster D) (g : Generation D),
    cmp a r = Some g ->
    all_of (fun p => orb (mem_nat p.(pkg_id) (image_ids D r))
                         (mem_nat p.(pkg_id) g.(gen_synthesized)))
           g.(gen_image) = true.

(* R-13-001c, R-13-010a, R-13-010b: the passes emit new bytes and must emit
   the derivation covering them, so nothing is declared synthesized that the
   image does not carry. With the clause above it, a declaration is a claim
   the image answers rather than a licence. *)
Definition CoversWhatItSynthesized (D : Type) (cmp : Composer D) : Prop :=
  forall (a : Ambient) (r : Roster D) (g : Generation D),
    cmp a r = Some g ->
    all_of (fun i => mem_nat i (image_ids D g.(gen_image)))
           g.(gen_synthesized) = true.

(* R-17-033's other polarity: a composer that admits nothing costs delivery
   rather than safety, and this is the clause that books it. *)
Definition CommitsEveryAccepted (m : Machine) (D : Type) (rd : Reading D)
    (cmp : Composer D) : Prop :=
  forall (a : Ambient) (r : Roster D),
    admissible m D rd a r = true ->
    exists g : Generation D,
      cmp a r = Some g
      /\ all_of (fun p => mem_nat p.(pkg_id) (image_ids D g.(gen_image))) r = true.

Lemma every_member_names_itself :
  forall (D : Type) (r : list (Package D)),
    all_of (fun p => mem_nat p.(pkg_id) (image_ids D r)) r = true.
Proof.
  intros D r. induction r as [ | x s IH ].
  - reflexivity.
  - simpl. apply andb_join.
    + exact (mem_nat_here x.(pkg_id) (image_ids D s)).
    + apply (all_of_mono (Package D)
              (fun p => mem_nat p.(pkg_id) (image_ids D s))
              (fun p => mem_nat p.(pkg_id) (cons x.(pkg_id) (image_ids D s))));
        [ | exact IH ].
      intros y Hy. exact (mem_nat_cons y.(pkg_id) x.(pkg_id) (image_ids D s) Hy).
Qed.

(* S11 (R-11-005, R-13-001a, R-13-001c): the specification is atomic. *)
Theorem the_specification_is_all_or_nothing :
  forall (m : Machine) (D : Type) (rd : Reading D),
    IsAllOrNothing m D rd (spec_compose m D rd).
Proof.
  intros m D rd a r H. unfold spec_compose. rewrite H. reflexivity.
Qed.

(* S11a: and what it does commit was validated whole. *)
Theorem the_specification_commits_only_the_accepted :
  forall (m : Machine) (D : Type) (rd : Reading D),
    CommitsOnlyTheAccepted m D rd (spec_compose m D rd).
Proof.
  intros m D rd a r g H. unfold spec_compose in H.
  destruct (admissible m D rd a r) eqn:E; [ | discriminate H ].
  injection H as H2. rewrite <- H2. simpl. exact E.
Qed.

(* S12 (R-13-001c, R-13-010b): and it emits no stranger the roster does not
   name and its own passes did not declare. *)
Theorem the_specification_emits_no_uncovered_stranger :
  forall (m : Machine) (D : Type) (rd : Reading D),
    EmitsNoUncoveredStranger D (spec_compose m D rd).
Proof.
  intros m D rd a r g H. unfold spec_compose in H.
  destruct (admissible m D rd a r) eqn:E; [ | discriminate H ].
  injection H as H2. rewrite <- H2. simpl.
  apply (all_of_mono (Package D)
           (fun p => mem_nat p.(pkg_id) (image_ids D r))
           (fun p => orb (mem_nat p.(pkg_id) (image_ids D r))
                         (mem_nat p.(pkg_id) nil)));
    [ | exact (every_member_names_itself D r) ].
  intros y Hy. rewrite Hy. reflexivity.
Qed.

Theorem the_specification_covers_what_it_synthesized :
  forall (m : Machine) (D : Type) (rd : Reading D),
    CoversWhatItSynthesized D (spec_compose m D rd).
Proof.
  intros m D rd a r g H. unfold spec_compose in H.
  destruct (admissible m D rd a r); [ | discriminate H ].
  injection H as H2. rewrite <- H2. reflexivity.
Qed.

(* S13 (R-17-033's polarity): and every package of an admissible roster
   reaches the image, so the atomicity theorem is not proved by a composer
   that emits nothing. *)
Theorem the_specification_commits_every_accepted :
  forall (m : Machine) (D : Type) (rd : Reading D),
    CommitsEveryAccepted m D rd (spec_compose m D rd).
Proof.
  intros m D rd a r H. exists {| gen_image := r; gen_synthesized := nil |}.
  split.
  - unfold spec_compose. rewrite H. reflexivity.
  - simpl. exact (every_member_names_itself D r).
Qed.

(* =========================================================================
   The generated families over an arbitrary package list, stated as theorems
   over an arbitrary position and an arbitrary roster rather than as
   enumerations. The enumerations at the demo roster below are what makes each
   non-vacuous; these are what makes each a reason.
   ========================================================================= *)

Lemma all_of_insert :
  forall (A : Type) (q : A -> bool) (x : A) (l : list A) (n : nat),
    all_of q (insert_at n x l) = andb (q x) (all_of q l).
Proof.
  intros A q x l n. revert l. induction n as [ | k IH ]; intros l.
  - reflexivity.
  - destruct l as [ | y s ].
    + simpl. destruct (q x); reflexivity.
    + simpl. rewrite (IH s). destruct (q y); destruct (q x); reflexivity.
Qed.

Lemma all_of_drop :
  forall (A : Type) (q : A -> bool) (l : list A) (n : nat),
    all_of q l = true -> all_of q (drop_at n l) = true.
Proof.
  intros A q l n. revert l. induction n as [ | k IH ]; intros l H.
  - destruct l as [ | y s ]; [ reflexivity | ].
    simpl in H. destruct (andb_split _ _ H) as [ _ Hs ]. exact Hs.
  - destruct l as [ | y s ]; [ reflexivity | ].
    simpl in H. destruct (andb_split _ _ H) as [ Hy Hs ].
    simpl. apply andb_join; [ exact Hy | exact (IH s Hs) ].
Qed.

Lemma all_of_swap :
  forall (A : Type) (p : A -> bool) (l : list A) (n : nat),
    all_of p (swap_at n l) = all_of p l.
Proof.
  intros A p l n. revert l. induction n as [ | k IH ]; intros l.
  - destruct l as [ | a s ]; [ reflexivity | ].
    destruct s as [ | b t ]; [ reflexivity | ].
    simpl. destruct (p a); destruct (p b); reflexivity.
  - destruct l as [ | a s ]; [ reflexivity | ].
    simpl. rewrite (IH s). reflexivity.
Qed.

Lemma all_of_dup :
  forall (A : Type) (p : A -> bool) (l : list A) (n : nat),
    all_of p (dup_at n l) = all_of p l.
Proof.
  intros A p l n. revert l. induction n as [ | k IH ]; intros l.
  - destruct l as [ | a s ]; [ reflexivity | ].
    simpl. destruct (p a); reflexivity.
  - destruct l as [ | a s ]; [ reflexivity | ].
    simpl. rewrite (IH s). reflexivity.
Qed.

Lemma count_of_insert :
  forall (A : Type) (x : A) (l : list A) (n : nat),
    count_of (insert_at n x l) = S (count_of l).
Proof.
  intros A x l n. revert l. induction n as [ | k IH ]; intros l.
  - reflexivity.
  - destruct l as [ | y s ]; [ reflexivity | ]. simpl. rewrite (IH s). reflexivity.
Qed.

Lemma count_of_swap :
  forall (A : Type) (l : list A) (n : nat), count_of (swap_at n l) = count_of l.
Proof.
  intros A l n. revert l. induction n as [ | k IH ]; intros l.
  - destruct l as [ | a s ]; [ reflexivity | ].
    destruct s as [ | b t ]; reflexivity.
  - destruct l as [ | a s ]; [ reflexivity | ]. simpl. rewrite (IH s). reflexivity.
Qed.

Lemma count_of_drop :
  forall (A : Type) (l : list A) (n : nat),
    Nat.leb (count_of (drop_at n l)) (count_of l) = true.
Proof.
  intros A l n. revert l. induction n as [ | k IH ]; intros l.
  - destruct l as [ | a s ]; [ reflexivity | ]. simpl.
    exact (nat_leb_succ (count_of s)).
  - destruct l as [ | a s ]; [ reflexivity | ]. simpl. exact (IH s).
Qed.

(* Insertion of a refused package costs the generation, wherever it goes. This
   is *a rejection is total* as a family fact, and total at the generation:
   the composer that ships the rest is refuted below. *)
Theorem inserting_a_refused_package_costs_the_generation :
  forall (m : Machine) (D : Type) (rd : Reading D) (a : Ambient)
         (x : Package D) (r : Roster D) (n : nat),
    accepts (spec_check m D rd a x) = false ->
    spec_compose m D rd a (insert_at n x r) = None.
Proof.
  intros m D rd a x r n Hx. apply the_specification_is_all_or_nothing.
  unfold admissible.
  rewrite (all_of_insert (Package D) (fun p => accepts (spec_check m D rd a p))
             x r n).
  rewrite Hx. reflexivity.
Qed.

(* And insertion of an admissible one into an admissible roster keeps the
   generation and adds exactly one member, wherever it goes. *)
Theorem inserting_an_accepted_package_adds_exactly_one :
  forall (m : Machine) (D : Type) (rd : Reading D) (a : Ambient)
         (x : Package D) (r : Roster D) (n : nat) (g : Generation D),
    accepts (spec_check m D rd a x) = true ->
    spec_compose m D rd a r = Some g ->
    exists h : Generation D,
      spec_compose m D rd a (insert_at n x r) = Some h
      /\ count_of h.(gen_image) = S (count_of g.(gen_image)).
Proof.
  intros m D rd a x r n g Hx Hg.
  unfold spec_compose in Hg. destruct (admissible m D rd a r) eqn:E;
    [ | discriminate Hg ].
  injection Hg as Hg2.
  exists {| gen_image := insert_at n x r; gen_synthesized := nil |}. split.
  - unfold spec_compose. unfold admissible.
    rewrite (all_of_insert (Package D) (fun p => accepts (spec_check m D rd a p))
               x r n).
    rewrite Hx. unfold admissible in E. rewrite E. reflexivity.
  - rewrite <- Hg2. simpl. exact (count_of_insert (Package D) x r n).
Qed.

(* A deletion from an admissible roster still composes: dropping a package
   cannot make a roster inadmissible, which is what makes the atomicity above
   a property of the refused member rather than of the roster's length. *)
Theorem a_deletion_from_an_admissible_roster_still_composes :
  forall (m : Machine) (D : Type) (rd : Reading D) (a : Ambient)
         (r : Roster D) (n : nat),
    admissible m D rd a r = true -> admissible m D rd a (drop_at n r) = true.
Proof.
  intros m D rd a r n H. unfold admissible. unfold admissible in H.
  exact (all_of_drop (Package D) (fun p => accepts (spec_check m D rd a p)) r n H).
Qed.

(* A transposition composes exactly as many, at any position of any roster,
   because admission is per package and reads no neighbour. The construction
   whose verdict does read one is refuted below. *)
Theorem a_transposition_composes_the_same_roster :
  forall (m : Machine) (D : Type) (rd : Reading D) (a : Ambient)
         (r : Roster D) (n : nat),
    admissible m D rd a (swap_at n r) = admissible m D rd a r.
Proof.
  intros m D rd a r n. unfold admissible.
  exact (all_of_swap (Package D) (fun p => accepts (spec_check m D rd a p)) r n).
Qed.

Theorem a_duplication_composes_the_same_roster :
  forall (m : Machine) (D : Type) (rd : Reading D) (a : Ambient)
         (r : Roster D) (n : nat),
    admissible m D rd a (dup_at n r) = admissible m D rd a r.
Proof.
  intros m D rd a r n. unfold admissible.
  exact (all_of_dup (Package D) (fun p => accepts (spec_check m D rd a p)) r n).
Qed.

(* The four generators over a roster, as the families the enumerations below
   walk. *)
Definition roster_deletions (D : Type) (r : Roster D) : list (Roster D) :=
  map_over (fun n => drop_at n r) (upto (count_of r)).

Definition roster_insertions (D : Type) (x : Package D) (r : Roster D)
    : list (Roster D) :=
  map_over (fun n => insert_at n x r) (upto (S (count_of r))).

Definition roster_transpositions (D : Type) (r : Roster D) : list (Roster D) :=
  map_over (fun n => swap_at n r) (upto (before_last (count_of r))).

Definition roster_duplications (D : Type) (r : Roster D) : list (Roster D) :=
  map_over (fun n => dup_at n r) (upto (count_of r)).

(* =========================================================================
   The generated families over a derivation's own record list, over the move
   table and over the judgment enumeration.
   ========================================================================= *)

(* Replace one third of a record's codes with the first code past its
   enumeration, which is derived rather than written so the corruption stays
   one when the enumeration grows. *)
Definition unknown_form (s : Step) : Step :=
  {| st_judgment := past_the_judgments;
     st_move := s.(st_move);
     st_facet := s.(st_facet);
     st_site := s.(st_site) |}.

Definition unknown_move (s : Step) : Step :=
  {| st_judgment := s.(st_judgment);
     st_move := past_the_moves;
     st_facet := s.(st_facet);
     st_site := s.(st_site) |}.

Definition unknown_facet (s : Step) : Step :=
  {| st_judgment := s.(st_judgment);
     st_move := s.(st_move);
     st_facet := past_the_facets;
     st_site := s.(st_site) |}.

(* Rewrite one record's move to an attribute. This is the misrouting the move
   table forbids and nothing else does: the record stays recognised, names the
   same facet and makes a move R-05-038 assigns to eight facets and R-05-037
   to none of them, so it discharges its facet exactly when that facet was an
   attributed one already. *)
Definition attributed (s : Step) : Step :=
  {| st_judgment := s.(st_judgment);
     st_move := code_of_move EvaluateAnAttribute;
     st_facet := s.(st_facet);
     st_site := s.(st_site) |}.

(* Rewrite every record to one judgment form. Gap c is that no entry pairs a
   form with the facet it discharges, so this family is the weakest reading
   made checkable rather than asserted. *)
Definition retag (j : Judgment) (c : Cert) : Cert :=
  with_steps c (map_over (fun s => {| st_judgment := code_of_judgment j;
                                      st_move := s.(st_move);
                                      st_facet := s.(st_facet);
                                      st_site := s.(st_site) |})
                         c.(cert_steps)).

Definition step_deletions (c : Cert) : list Cert :=
  map_over (fun n => with_steps c (drop_at n c.(cert_steps)))
           (upto (count_of c.(cert_steps))).

Definition step_transpositions (c : Cert) : list Cert :=
  map_over (fun n => with_steps c (swap_at n c.(cert_steps)))
           (upto (before_last (count_of c.(cert_steps)))).

Definition step_duplications (c : Cert) : list Cert :=
  map_over (fun n => with_steps c (dup_at n c.(cert_steps)))
           (upto (count_of c.(cert_steps))).

Definition step_form_corruptions (c : Cert) : list Cert :=
  map_over (fun n => with_steps c (patch_at unknown_form n c.(cert_steps)))
           (upto (count_of c.(cert_steps))).

Definition step_move_corruptions (c : Cert) : list Cert :=
  map_over (fun n => with_steps c (patch_at unknown_move n c.(cert_steps)))
           (upto (count_of c.(cert_steps))).

Definition step_facet_corruptions (c : Cert) : list Cert :=
  map_over (fun n => with_steps c (patch_at unknown_facet n c.(cert_steps)))
           (upto (count_of c.(cert_steps))).

Definition step_misroutings (c : Cert) : list Cert :=
  map_over (fun n => with_steps c (patch_at attributed n c.(cert_steps)))
           (upto (count_of c.(cert_steps))).

Definition retaggings (c : Cert) : list Cert :=
  map_over (fun j => retag j c) all_judgments.

(* None of the three corruptions is recognised, whatever the record it was
   applied to, which is what makes the three families families rather than
   coincidences of the demo's own codes. *)
Theorem an_unknown_form_is_never_recognised :
  forall s : Step, step_recognised (unknown_form s) = false.
Proof. intros s. unfold step_recognised. unfold unknown_form. reflexivity. Qed.

Theorem an_unknown_move_is_never_recognised :
  forall s : Step, step_recognised (unknown_move s) = false.
Proof.
  intros s. unfold step_recognised. unfold unknown_move. simpl.
  destruct (judgment_of_code s.(st_judgment)); reflexivity.
Qed.

Theorem an_unknown_facet_is_never_recognised :
  forall s : Step, step_recognised (unknown_facet s) = false.
Proof.
  intros s. unfold step_recognised. unfold unknown_facet. simpl.
  destruct (judgment_of_code s.(st_judgment));
    destruct (move_of_code s.(st_move)); reflexivity.
Qed.

(* A misrouted record stays recognised, which is what makes it a different
   defect from a corrupted one: recognition is phase 2 and the move table is
   phases 3 to 5, and the two are refused under different rules. *)
Theorem a_misrouted_record_is_still_recognised :
  forall s : Step, step_recognised s = true -> step_recognised (attributed s) = true.
Proof.
  intros s H. unfold step_recognised. unfold attributed. simpl.
  unfold step_recognised in H. destruct (andb_split _ _ H) as [ H1 Hf ].
  destruct (andb_split _ _ H1) as [ Hj _ ].
  apply andb_join; [ | exact Hf ]. apply andb_join; [ exact Hj | reflexivity ].
Qed.

(* And it discharges its facet exactly when that facet is an attributed one,
   which is the move table read from the side a weakening approaches it: a
   citation rewritten as an attribute discharges nothing. *)
Theorem a_misrouted_record_discharges_only_an_attributed_facet :
  forall (s : Step) (f : Facet),
    discharges (attributed s) f = true -> move_of f = EvaluateAnAttribute.
Proof.
  intros s f H. unfold discharges in H. unfold attributed in H. simpl in H.
  destruct (facet_of_code s.(st_facet)) as [ g | ]; [ | discriminate H ].
  remember (move_of f) as k. destruct k;
    destruct (andb_split _ _ H) as [ _ Hm ];
    first [ discriminate Hm | reflexivity ].
Qed.

(* Retagging changes no record's move or facet, so it changes no discharge:
   the coverage test reads the move and the facet halves of a record and never
   the form half. This is gap c as a theorem over an arbitrary form and an
   arbitrary certificate, with the seven-member enumeration below as its
   witness. *)
Lemma retagging_preserves_the_discharges :
  forall (j : Judgment) (c : Cert) (f : Facet),
    discharged (retag j c) f = discharged c f.
Proof.
  intros j c f. unfold discharged. unfold retag. unfold with_steps. simpl.
  induction c.(cert_steps) as [ | s r IH ].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

Theorem retagging_preserves_coverage :
  forall (m : Machine) (t : Tier) (j : Judgment) (c : Cert),
    covers m t (retag j c) = covers m t c.
Proof.
  intros m t j c. unfold covers.
  induction (required m t) as [ | f l IH ].
  - reflexivity.
  - simpl. rewrite (retagging_preserves_the_discharges j c f). rewrite IH.
    reflexivity.
Qed.

Lemma retag_preserves_recognition :
  forall (j : Judgment) (c : Cert),
    all_of step_recognised c.(cert_steps) = true ->
    all_of step_recognised (retag j c).(cert_steps) = true.
Proof.
  intros j c. unfold retag. unfold with_steps. simpl.
  induction c.(cert_steps) as [ | s r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hs Hr ].
    simpl. apply andb_join; [ | exact (IH Hr) ].
    unfold step_recognised. simpl.
    rewrite (every_judgment_form_decodes_to_itself j). simpl.
    unfold step_recognised in Hs. destruct (andb_split _ _ Hs) as [ H1 Hf ].
    destruct (andb_split _ _ H1) as [ _ Hm ].
    apply andb_join; [ exact Hm | exact Hf ].
Qed.

(* The invariances, as one lemma the three families are instances of: a
   rewriting that keeps every discharge and keeps every record recognised
   keeps the verdict, whatever the machine, the identifier and the tier. *)
Lemma any_of_swap :
  forall (A : Type) (p : A -> bool) (l : list A) (n : nat),
    any_of p (swap_at n l) = any_of p l.
Proof.
  intros A p l n. revert l. induction n as [ | k IH ]; intros l.
  - destruct l as [ | a s ]; [ reflexivity | ].
    destruct s as [ | b t ]; [ reflexivity | ].
    simpl. destruct (p a); destruct (p b); reflexivity.
  - destruct l as [ | a s ]; [ reflexivity | ].
    simpl. rewrite (IH s). reflexivity.
Qed.

Lemma any_of_dup :
  forall (A : Type) (p : A -> bool) (l : list A) (n : nat),
    any_of p (dup_at n l) = any_of p l.
Proof.
  intros A p l n. revert l. induction n as [ | k IH ]; intros l.
  - destruct l as [ | a s ]; [ reflexivity | ].
    simpl. destruct (p a); reflexivity.
  - destruct l as [ | a s ]; [ reflexivity | ].
    simpl. rewrite (IH s). reflexivity.
Qed.

Lemma first_undischarged_congruent :
  forall (c1 c2 : Cert) (l : list Facet),
    (forall f : Facet, discharged c1 f = discharged c2 f) ->
    first_undischarged c1 l = first_undischarged c2 l.
Proof.
  intros c1 c2 l Hd. induction l as [ | f r IH ].
  - reflexivity.
  - simpl. rewrite (Hd f). destruct (discharged c2 f).
    + exact IH.
    + reflexivity.
Qed.

Lemma a_congruent_rewriting_keeps_the_verdict :
  forall (m : Machine) (id tc : nat) (c1 c2 : Cert),
    c1.(cert_versions) = c2.(cert_versions) ->
    c1.(cert_binds) = c2.(cert_binds) ->
    all_of step_recognised c1.(cert_steps) = true ->
    all_of step_recognised c2.(cert_steps) = true ->
    (forall f : Facet, discharged c1 f = discharged c2 f) ->
    check_cert m id tc c1 = check_cert m id tc c2.
Proof.
  intros m id tc c1 c2 Hv Hb H1 H2 Hd. unfold check_cert.
  rewrite Hv. rewrite Hb.
  destruct (negb (versions_eqb c2.(cert_versions) m.(admitted_versions)));
    [ reflexivity | ].
  destruct (negb (Nat.eqb c2.(cert_binds) id)); [ reflexivity | ].
  destruct (tier_of_code tc) as [ t | ]; [ | reflexivity ].
  rewrite (all_recognised_first_none c1.(cert_steps) H1).
  rewrite (all_recognised_first_none c2.(cert_steps) H2).
  rewrite (first_undischarged_congruent c1 c2
             (in_phase_order (m.(required) t)) Hd).
  reflexivity.
Qed.

(* S15: a transposition of a derivation's records changes no verdict, at any
   position of any derivation whose records the checker recognises. Reading 7
   as a theorem rather than as a conversion over the demo's seven. *)
Theorem a_transposition_of_the_records_changes_no_verdict :
  forall (m : Machine) (id tc : nat) (c : Cert) (n : nat),
    all_of step_recognised c.(cert_steps) = true ->
    check_cert m id tc (with_steps c (swap_at n c.(cert_steps)))
    = check_cert m id tc c.
Proof.
  intros m id tc c n H.
  apply (a_congruent_rewriting_keeps_the_verdict m id tc
           (with_steps c (swap_at n c.(cert_steps))) c);
    try reflexivity.
  - simpl. rewrite (all_of_swap Step step_recognised c.(cert_steps) n). exact H.
  - exact H.
  - intros f. unfold discharged. simpl.
    exact (any_of_swap Step (fun s => discharges s f) c.(cert_steps) n).
Qed.

(* S16: and a duplication does not either. R-05-029's criterion fixes no
   multiplicity, so a derivation discharging one facet twice discharges it. *)
Theorem a_duplication_of_a_record_changes_no_verdict :
  forall (m : Machine) (id tc : nat) (c : Cert) (n : nat),
    all_of step_recognised c.(cert_steps) = true ->
    check_cert m id tc (with_steps c (dup_at n c.(cert_steps)))
    = check_cert m id tc c.
Proof.
  intros m id tc c n H.
  apply (a_congruent_rewriting_keeps_the_verdict m id tc
           (with_steps c (dup_at n c.(cert_steps))) c);
    try reflexivity.
  - simpl. rewrite (all_of_dup Step step_recognised c.(cert_steps) n). exact H.
  - exact H.
  - intros f. unfold discharged. simpl.
    exact (any_of_dup Step (fun s => discharges s f) c.(cert_steps) n).
Qed.

(* S17 (gap c as a theorem): rewriting every record to one judgment form
   changes no verdict, whatever the form. No entry pairs a form with the facet
   it discharges, so the checker requires a form to be recognised and requires
   nothing about which one it is; a rewrite of this file that fixed the
   pairing would decide what the register left open. The move axis, which the
   register does fix, is refuted rather than shown free. *)
Theorem retagging_the_judgment_form_changes_no_verdict :
  forall (m : Machine) (id tc : nat) (j : Judgment) (c : Cert),
    all_of step_recognised c.(cert_steps) = true ->
    check_cert m id tc (retag j c) = check_cert m id tc c.
Proof.
  intros m id tc j c H.
  apply (a_congruent_rewriting_keeps_the_verdict m id tc (retag j c) c);
    try reflexivity.
  - exact (retag_preserves_recognition j c H).
  - exact H.
  - intros f. exact (retagging_preserves_the_discharges j c f).
Qed.

(* =========================================================================
   The demo machine, its three derivation carriers, and the golden-model
   roster, for R-05-165's uninhabited-domain mode and for the refutation
   witnesses.

   The roster is M6.2a's cell read literally: the packages the checker checks
   are the golden-model components themselves, which are the plan's sections 2
   through 8. Their identifiers, tiers, producers and attestations are
   arbitrary witness values carrying no composition claim (gap h); their
   identities are not.
   ------------------------------------------------------------------------- *)

(* R-13-012 states the Tier-2 certificate as the subset of R-05-029's eleven
   this tier requires, and names six rows: ABI and type well-formedness, no
   runtime codegen, temporal safety, definite initialization, data-race
   freedom, and control-flow integrity. Two of those six are rows R-05-036
   splits. *Temporal safety* is the memory-safety row's move-II half by
   R-05-038, so the row's move-I half, spatial safety, is not required here
   and requiring it would be a bar stronger than the register's; the machine
   that does require it is exhibited below and refuses what R-13-012 admits.
   *Control-flow integrity* is named whole, and R-05-029's own sentence is
   that it carries both halves and is not two obligations, so both of its
   facets are required. Six rows, seven facets.

   Tier 0's and Tier 1's rows are witness values, which is gap b: R-13-011
   states their evidence in words R-05-030 puts outside every type system, and
   the only part of it R-06-009 hands the type-checker is Tier 1's memory and
   ABI half, which is what the Tier-1 witness follows. *)
Definition demo_required (t : Tier) : list Facet :=
  match t with
  | TierZero => all_facets
  | TierOne =>
      cons MemSpatial (cons MemTemporal (cons AbiConform (cons CtTaint nil)))
  | TierTwo =>
      cons AbiConform (cons CodegenNone (cons MemTemporal (cons InitDefinite
      (cons RaceFreedom (cons CfiRuntime (cons CfiCalleeSet nil))))))
  end.

Definition demo_versions : Versions :=
  {| ver_spec_set := 4; ver_sail_model := 2;
     ver_language := 1; ver_profile := 3 |}.

Definition demo : Machine := {|
  required := demo_required;
  admitted_versions := demo_versions;
  composer_id := 20
|}.

(* The reading of R-13-012 this file refuses: the memory-safety *row* required
   whole rather than its temporal facet. It is a bar strictly stronger than
   the register's, and the conversion below is what says so. *)
Definition demo_row_granular : Machine := {|
  required := fun t => match t with
                       | TierTwo =>
                           cons AbiConform (cons CodegenNone (cons MemSpatial
                           (cons MemTemporal (cons InitDefinite (cons RaceFreedom
                           (cons CfiRuntime (cons CfiCalleeSet nil)))))))
                       | u => demo_required u
                       end;
  admitted_versions := demo_versions;
  composer_id := 20
|}.

(* A machine that requires nothing of any tier, which is what makes the thin
   derivation's disposition a property of the required set rather than of the
   checker: the same derivation the demo machine refuses this one admits. *)
Definition demo_lenient : Machine := {|
  required := fun _ => nil;
  admitted_versions := demo_versions;
  composer_id := 20
|}.

Example the_demo_machine_declares :
  demo.(admitted_versions) = demo_versions
  /\ demo.(composer_id) = 20
  /\ demo_versions.(ver_spec_set) = 4
  /\ demo_versions.(ver_sail_model) = 2
  /\ demo_versions.(ver_language) = 1
  /\ demo_versions.(ver_profile) = 3
  /\ demo_lenient.(required) TierTwo = nil
  /\ demo_lenient.(admitted_versions) = demo.(admitted_versions) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl)))))).

(* The two machines beside the demo one differ from it in their required sets
   and in nothing else, which is what makes each a reading of one entry rather
   than a second composition: a verdict that moved with a version or with a
   composer identity here would be answering a different question. *)
Example the_three_machines_differ_only_in_what_they_require :
  demo_row_granular.(admitted_versions) = demo.(admitted_versions)
  /\ demo_row_granular.(composer_id) = demo.(composer_id)
  /\ demo_lenient.(composer_id) = demo.(composer_id)
  /\ demo_row_granular.(required) TierZero = demo.(required) TierZero
  /\ demo_row_granular.(required) TierOne = demo.(required) TierOne
  /\ demo_lenient.(required) TierZero = nil
  /\ demo_lenient.(required) TierOne = nil :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

(* R-13-012's six rows, checked rather than asserted: the rows the Tier-2
   requirement names are exactly those six, the memory-safety row contributes
   its temporal facet alone, and the control-flow-integrity row contributes
   both of its halves. *)
Example the_tier_two_requirement_is_r_13_012_s_six_rows :
  map_over row_of (demo.(required) TierTwo)
  = cons AbiTypeConformance (cons NoRuntimeCodegen (cons MemorySafety
    (cons DefiniteInitialization (cons DataRaceFreedom
    (cons ControlFlowIntegrity (cons ControlFlowIntegrity nil))))))
  /\ count_of (demo.(required) TierTwo) = 7
  /\ mem_facet MemSpatial (demo.(required) TierTwo) = false
  /\ mem_facet MemTemporal (demo.(required) TierTwo) = true
  /\ mem_facet CfiRuntime (demo.(required) TierTwo) = true
  /\ mem_facet CfiCalleeSet (demo.(required) TierTwo) = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* And the move table read at the Tier-2 requirement: no deletion is owed
   there, two citations are, five attributes are. That is what makes the three
   coverage rules reachable at three different tiers rather than at one. *)
Example the_tier_two_requirement_owes_two_citations_and_no_deletion :
  count_of (facets_of_move_in ConfirmADeletion (demo.(required) TierTwo)) = 0
  /\ facets_of_move_in CiteAnInvariant (demo.(required) TierTwo)
     = cons CodegenNone (cons CfiRuntime nil)
  /\ count_of (facets_of_move_in EvaluateAnAttribute (demo.(required) TierTwo)) = 5
  /\ count_of (facets_of_move_in ConfirmADeletion (demo.(required) TierZero)) = 2 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_tier_requirements_are_inhabited_and_nested :
  count_of (demo.(required) TierZero) = 13
  /\ count_of (demo.(required) TierOne) = 4
  /\ count_of (demo.(required) TierTwo) = 7
  /\ count_of (demo_row_granular.(required) TierTwo) = 8 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   The three carriers. `Cert` read by the identity is the fullest derivation
   this file expresses; `Terse` is a carrier whose every value reads as a
   certificate with no record at all, which is a thin derivation as a *value*
   rather than as a case in the checker; and `Tagged` is a carrier two of
   whose values read alike, which is what gives reading 3's obligation
   something to exclude.
   ------------------------------------------------------------------------- *)

Definition full_reading : Reading Cert := fun c => c.

Definition Terse : Type := nat.

Definition terse_reading : Reading Terse := fun n =>
  {| cert_versions := demo_versions;
     cert_binds := n;
     cert_steps := nil |}.

Definition Tagged : Type := prod nat Cert.

Definition tag_reading : Reading Tagged := fun x => snd x.

Example the_terse_carrier_reads_as_a_thin_derivation :
  (terse_reading 6).(cert_steps) = nil
  /\ (terse_reading 6).(cert_binds) = 6
  /\ (terse_reading 6).(cert_versions) = demo_versions :=
  conj eq_refl (conj eq_refl eq_refl).

(* -------------------------------------------------------------------------
   Building derivations. One record per facet the tier requires, carrying the
   move that facet's own row of the move table assigns, sites numbered from
   the front, so that a deletion at position n loses exactly the n-th required
   facet and the refusal it draws names that facet's own code and its own
   move's phase.
   ------------------------------------------------------------------------- *)

Fixpoint records_from (j : Judgment) (fs : list Facet) (site : nat) : list Step :=
  match fs with
  | nil => nil
  | cons f r => cons {| st_judgment := code_of_judgment j;
                        st_move := code_of_move (move_of f);
                        st_facet := code_of_facet f;
                        st_site := site |}
                     (records_from j r (S site))
  end.

Definition covering_cert (t : Tier) (id : nat) : Cert :=
  {| cert_versions := demo_versions;
     cert_binds := id;
     cert_steps := records_from InstructionTransfer (demo.(required) t) 0 |}.

Definition thin_cert (id : nat) : Cert :=
  {| cert_versions := demo_versions;
     cert_binds := id;
     cert_steps := nil |}.

(* Re-stamp one of a derivation's four versions and change nothing else, which
   is what a derivation produced against another generation is: R-11-005 makes
   proofs generation-scoped, so revving the Sail model leaves the derivation
   intact and makes it no longer a verdict for this generation. *)
Definition with_sail_model (v : nat) (c : Cert) : Cert :=
  {| cert_versions := {| ver_spec_set := c.(cert_versions).(ver_spec_set);
                         ver_sail_model := v;
                         ver_language := c.(cert_versions).(ver_language);
                         ver_profile := c.(cert_versions).(ver_profile) |};
     cert_binds := c.(cert_binds);
     cert_steps := c.(cert_steps) |}.

Definition with_profile (v : nat) (c : Cert) : Cert :=
  {| cert_versions := {| ver_spec_set := c.(cert_versions).(ver_spec_set);
                         ver_sail_model := c.(cert_versions).(ver_sail_model);
                         ver_language := c.(cert_versions).(ver_language);
                         ver_profile := v |};
     cert_binds := c.(cert_binds);
     cert_steps := c.(cert_steps) |}.

(* R-11-005's two versions and R-05-135b's two are four obligations and not
   one: a derivation agreeing on three of them is refused on the fourth, and
   the checker that compares the spec-set alone is refuted below. *)
Example re_stamping_moves_one_version_and_no_other :
  (with_sail_model 8 (covering_cert TierTwo 2)).(cert_versions).(ver_sail_model) = 8
  /\ (with_sail_model 8 (covering_cert TierTwo 2)).(cert_versions).(ver_spec_set) = 4
  /\ (with_profile 8 (covering_cert TierTwo 2)).(cert_versions).(ver_profile) = 8
  /\ (with_sail_model 8 (covering_cert TierTwo 2)).(cert_binds) = 2
  /\ (with_sail_model 8 (covering_cert TierTwo 2)).(cert_steps)
     = (covering_cert TierTwo 2).(cert_steps)
  /\ versions_eqb (with_sail_model 8 (covering_cert TierTwo 2)).(cert_versions)
                  demo_versions = false
  /\ versions_eqb (with_profile 8 (covering_cert TierTwo 2)).(cert_versions)
                  demo_versions = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

Definition corrupt_form_at (n : nat) (c : Cert) : Cert :=
  with_steps c (patch_at unknown_form n c.(cert_steps)).

Definition corrupt_move_at (n : nat) (c : Cert) : Cert :=
  with_steps c (patch_at unknown_move n c.(cert_steps)).

Definition corrupt_facet_at (n : nat) (c : Cert) : Cert :=
  with_steps c (patch_at unknown_facet n c.(cert_steps)).

Definition misroute_at (n : nat) (c : Cert) : Cert :=
  with_steps c (patch_at attributed n c.(cert_steps)).

Definition drop_record_at (n : nat) (c : Cert) : Cert :=
  with_steps c (drop_at n c.(cert_steps)).

Example the_tier_two_covering_derivation :
  (covering_cert TierTwo 0).(cert_steps)
  = cons {| st_judgment := 2; st_move := 1; st_facet := 7; st_site := 0 |}
    (cons {| st_judgment := 2; st_move := 0; st_facet := 6; st_site := 1 |}
    (cons {| st_judgment := 2; st_move := 1; st_facet := 1; st_site := 2 |}
    (cons {| st_judgment := 2; st_move := 1; st_facet := 2; st_site := 3 |}
    (cons {| st_judgment := 2; st_move := 1; st_facet := 3; st_site := 4 |}
    (cons {| st_judgment := 2; st_move := 0; st_facet := 4; st_site := 5 |}
    (cons {| st_judgment := 2; st_move := 1; st_facet := 5; st_site := 6 |}
     nil))))))
  := eq_refl.

Example the_covering_derivations_are_as_long_as_their_requirements :
  count_of (covering_cert TierTwo 0).(cert_steps) = 7
  /\ count_of (covering_cert TierOne 0).(cert_steps) = 4
  /\ count_of (covering_cert TierZero 0).(cert_steps) = 13
  /\ count_of (thin_cert 0).(cert_steps) = 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The covering derivation covers, the thin one does not, the corruption is
   unrecognised and the misrouting is recognised and still discharges nothing:
   the four inputs the clauses distinguish, computed. *)
Example the_covering_derivation_covers_its_tier :
  covers demo TierTwo (covering_cert TierTwo 0) = true
  /\ covers demo TierZero (covering_cert TierTwo 0) = false
  /\ covers demo TierTwo (thin_cert 0) = false
  /\ covers demo_lenient TierTwo (thin_cert 0) = true
  /\ covers demo_row_granular TierTwo (covering_cert TierTwo 0) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example the_corruption_and_the_misrouting_differ :
  all_of step_recognised (covering_cert TierTwo 0).(cert_steps) = true
  /\ all_of step_recognised (corrupt_form_at 0 (covering_cert TierTwo 0)).(cert_steps)
     = false
  /\ all_of step_recognised (corrupt_move_at 3 (covering_cert TierTwo 0)).(cert_steps)
     = false
  /\ all_of step_recognised (corrupt_facet_at 3 (covering_cert TierTwo 0)).(cert_steps)
     = false
  /\ all_of step_recognised (misroute_at 1 (covering_cert TierTwo 0)).(cert_steps)
     = true
  /\ discharged (misroute_at 1 (covering_cert TierTwo 0)) CodegenNone = false
  /\ discharged (covering_cert TierTwo 0) CodegenNone = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

(* -------------------------------------------------------------------------
   The roster: the golden-model components, named as identities.

   The plan's sections 2 through 8 are the seven software components a
   composed generation carries. Section 9 names two more, the CHERI-TAL
   type-checker and the CIC proof kernel, and they are deliberately absent
   here: R-06-014 makes them the admitters no admission certificate can cover,
   so a roster naming them would claim exactly what that entry refuses, and
   their trust rests on reproducible build, DDC and RoT measurement instead
   (R-13-026). The tier each component claims is a witness value chosen so
   that all three of R-13-011's tiers are inhabited; no entry assigns a
   component to a tier (gap h).
   ------------------------------------------------------------------------- *)

Definition package_at (id t who : nat) (att : bool) (c : option Cert) : Package Cert :=
  {| pkg_id := id; pkg_tier := t; pkg_producer := who;
     pkg_attested := att; pkg_cert := c |}.

(* Section 2: the Root-of-Trust firmware. *)
Definition rot_firmware : Package Cert :=
  package_at 0 (code_of_tier TierZero) 3 false (Some (covering_cert TierZero 0)).

(* Section 3: the M-mode firmware. *)
Definition mmode_firmware : Package Cert :=
  package_at 1 (code_of_tier TierZero) 3 false (Some (covering_cert TierZero 1)).

(* Section 5: the kernel. *)
Definition kernel : Package Cert :=
  package_at 2 (code_of_tier TierZero) 3 false (Some (covering_cert TierZero 2)).

(* Section 4: the verified crypto core. *)
Definition crypto_core : Package Cert :=
  package_at 3 (code_of_tier TierOne) 3 false (Some (covering_cert TierOne 3)).

(* Section 6: the object system and its update transactor. *)
Definition object_store : Package Cert :=
  package_at 4 (code_of_tier TierOne) 3 false (Some (covering_cert TierOne 4)).

(* Section 7: the filesystem. *)
Definition filesystem : Package Cert :=
  package_at 5 (code_of_tier TierOne) 3 false (Some (covering_cert TierOne 5)).

(* Section 8: the init system's static supervision tree. *)
Definition supervision_tree : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false (Some (covering_cert TierTwo 6)).

Definition golden_roster : Roster Cert :=
  cons rot_firmware (cons mmode_firmware (cons kernel (cons crypto_core
  (cons object_store (cons filesystem (cons supervision_tree nil)))))).

(* R-13-010b's shared service compartment: a component in place of a library
   statically linked into each consumer, which no roster names and which the
   pass must emit a derivation covering. *)
Definition shared_service : Package Cert :=
  package_at 7 (code_of_tier TierTwo) 3 false (Some (covering_cert TierTwo 7)).

(* The same compartment with the derivation the pass forgot to emit. *)
Definition shared_service_uncovered : Package Cert :=
  package_at 7 (code_of_tier TierTwo) 3 false None.

(* A package the roster does not name and no pass declared, admissible on its
   own terms: the witness the substituting composer emits. *)
Definition stock_package : Package Cert :=
  package_at 8 (code_of_tier TierTwo) 3 false (Some (covering_cert TierTwo 8)).

(* An identifier no image carries, for the composer that books a merge it did
   not ship. *)
Definition phantom_id : nat := 21.

(* -------------------------------------------------------------------------
   One refusal witness per rule, each a golden-model component carrying one
   seeded defect, so that what each rule refuses is a component and not a
   synthetic package. Eight defects, eight rules.
   ------------------------------------------------------------------------- *)

(* Phase 0: no certificate for the binding phase to read (R-13-003). *)
Definition w_absent : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false None.

(* Phase 0: produced against another Sail-model version (R-11-005). *)
Definition w_stale_version : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false
    (Some (with_sail_model (S demo_versions.(ver_sail_model))
             (covering_cert TierTwo 6))).

(* Phase 0: the derivation is about other bytes (R-13-003, TAL-067). *)
Definition w_wrong_binding : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false (Some (covering_cert TierTwo 8)).

(* Phase 1: a tier code outside R-13-011's three. *)
Definition w_unknown_tier : Package Cert :=
  package_at 6 past_the_tiers 3 false (Some (covering_cert TierTwo 6)).

(* Phase 2: a record whose judgment form the checker does not recognise
   (TAL-023). *)
Definition w_unknown_form : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false
    (Some (corrupt_form_at 0 (covering_cert TierTwo 6))).

(* Phase 3: a move-III facet undischarged (R-05-039). The Tier-2 requirement
   owes no deletion, so this witness is a Tier-0 component. *)
Definition w_missing_deletion : Package Cert :=
  package_at 0 (code_of_tier TierZero) 3 false
    (Some (drop_record_at 9 (covering_cert TierZero 0))).

(* Phase 4: a move-I facet undischarged (R-05-037). *)
Definition w_missing_citation : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false
    (Some (drop_record_at 1 (covering_cert TierTwo 6))).

(* Phase 5: a move-II facet undischarged (R-05-038). *)
Definition w_missing_attribute : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false
    (Some (drop_record_at 0 (covering_cert TierTwo 6))).

Definition refusal_witnesses : Roster Cert :=
  cons w_absent (cons w_stale_version (cons w_wrong_binding
  (cons w_unknown_tier (cons w_unknown_form (cons w_missing_deletion
  (cons w_missing_citation (cons w_missing_attribute nil))))))).

(* The ninth witness, which no rule of its own refuses: the citation R-05-037
   assigns to no-runtime-codegen, offered as the attribute R-05-038 assigns to
   eight other facets. It is recognised, it names a required facet, and it
   discharges nothing, which is the whole content of the move table. *)
Definition w_misrouted : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false
    (Some (misroute_at 1 (covering_cert TierTwo 6))).

(* A component with a thin derivation, which is what the bring-up reading
   invites and what R-13-011's *its required evidence* refuses. *)
Definition p_thin : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false (Some (thin_cert 6)).

(* An attested one, and one the composer itself produced. R-13-013 says no
   admission rule reads a producer identity and R-13-001c puts the composer
   outside every trust base, so neither buys anything. *)
Definition p_attested_and_thin : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 true (Some (thin_cert 6)).

Definition p_from_the_composer : Package Cert :=
  package_at 6 (code_of_tier TierTwo) demo.(composer_id) true (Some (thin_cert 6)).

(* A package failing two phases at once, so that the phase order is observable
   rather than described: its one record is unrecognised *and* its derivation
   covers nothing. *)
Definition p_two_faults : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false
    (Some (with_steps (thin_cert 6)
             (cons {| st_judgment := past_the_judgments;
                      st_move := past_the_moves;
                      st_facet := past_the_facets;
                      st_site := 8 |} nil))).

(* A package whose derivation leaves a move-I facet and a move-II facet both
   open, so that the phase order decides which the verdict names. *)
Definition p_two_open_phases : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false
    (Some (drop_record_at 0 (drop_record_at 1 (covering_cert TierTwo 6)))).

(* Three more packages, each failing two of TAL-074's first three phases at
   once, so that the order among those three is observable rather than
   described. Without them the early order would be a reading no witness
   exercises, and a checker that hoisted the tier above the version would pass
   every theorem this file states. *)

(* Phase 0's own two halves: a derivation produced against another Sail-model
   version *and* binding to other bytes. *)
Definition p_stale_and_misbound : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false
    (Some (with_sail_model (S demo_versions.(ver_sail_model))
             (covering_cert TierTwo 8))).

(* Phase 0 against phase 1: a derivation binding to other bytes, under a tier
   code outside R-13-011's three. *)
Definition p_misbound_and_unknown_tier : Package Cert :=
  package_at 6 past_the_tiers 3 false (Some (covering_cert TierTwo 8)).

(* Phase 1 against phase 2: a tier code outside the three, with a record whose
   judgment form the checker does not recognise. *)
Definition p_unknown_tier_and_unknown_form : Package Cert :=
  package_at 6 past_the_tiers 3 false
    (Some (corrupt_form_at 0 (covering_cert TierTwo 6))).

Definition amb_first : Ambient := {| amb_run := 0; amb_state := 0 |}.

Definition amb_second : Ambient :=
  {| amb_run := S amb_first.(amb_run); amb_state := amb_first.(amb_state) |}.

Definition amb_composing : Ambient :=
  {| amb_run := amb_first.(amb_run); amb_state := demo.(composer_id) |}.

Definition demo_check (p : Package Cert) : Verdict :=
  spec_check demo Cert full_reading amb_first p.

Definition demo_compose (r : Roster Cert) : option (Generation Cert) :=
  spec_compose demo Cert full_reading amb_first r.

Example the_probe_ambients :
  amb_first.(amb_run) = 0 /\ amb_first.(amb_state) = 0
  /\ amb_second.(amb_run) = 1 /\ amb_second.(amb_state) = 0
  /\ amb_composing.(amb_run) = 0 /\ amb_composing.(amb_state) = 20 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* -------------------------------------------------------------------------
   The demo's own figures, computed rather than described, so that a value
   edited on one side of the file and read on the other is a failed conversion
   instead of a silent disagreement.
   ------------------------------------------------------------------------- *)

Example the_roster_names_the_golden_model_components :
  image_ids Cert golden_roster
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 (cons 6 nil))))))
  /\ count_of golden_roster = 7
  /\ map_over (fun p => p.(pkg_tier)) golden_roster
     = cons 0 (cons 0 (cons 0 (cons 1 (cons 1 (cons 1 (cons 2 nil))))))
  /\ map_over (fun p => p.(pkg_producer)) golden_roster
     = cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 nil))))))
  /\ map_over (fun p => p.(pkg_attested)) golden_roster
     = cons false (cons false (cons false (cons false (cons false
       (cons false (cons false nil))))))
  /\ map_over (fun p => map_option (fun c => c.(cert_binds)) p.(pkg_cert))
              golden_roster
     = cons (Some 0) (cons (Some 1) (cons (Some 2) (cons (Some 3) (cons (Some 4)
       (cons (Some 5) (cons (Some 6) nil))))))
  /\ map_over (fun p => map_option (fun c => count_of c.(cert_steps)) p.(pkg_cert))
              golden_roster
     = cons (Some 13) (cons (Some 13) (cons (Some 13) (cons (Some 4) (cons (Some 4)
       (cons (Some 4) (cons (Some 7) nil)))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

(* All three of R-13-011's tiers are inhabited by a roster member, so no tier
   requirement is a set nothing is checked against. *)
Example every_tier_is_inhabited_by_a_component :
  all_of (fun t => any_of (fun p => Nat.eqb p.(pkg_tier) (code_of_tier t))
                          golden_roster) all_tiers = true := eq_refl.

(* The roster composes: every golden-model component is admitted and the
   generation is committed whole. *)
Example the_golden_roster_composes :
  map_over demo_check golden_roster
  = cons Accepted (cons Accepted (cons Accepted (cons Accepted (cons Accepted
    (cons Accepted (cons Accepted nil))))))
  /\ admissible demo Cert full_reading amb_first golden_roster = true
  /\ map_option (fun g => image_ids Cert g.(gen_image)) (demo_compose golden_roster)
     = Some (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 (cons 6 nil)))))))
  /\ map_option (fun g => g.(gen_synthesized)) (demo_compose golden_roster)
     = Some nil :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* One witness per rule, and the verdict each draws. Every one of the eight
   fires, so no clause below is dead, and each names the site its own phase
   reads: a package identifier at phases 0 and 1, a record's site at phase 2,
   a facet's code at phases 3 to 5. *)
Example the_witness_verdicts :
  map_over demo_check refusal_witnesses
  = cons (Refused DerivationAbsent 6)
    (cons (Refused VersionMismatch 6)
    (cons (Refused BindingMismatch 6)
    (cons (Refused TierUnrecognised 6)
    (cons (Refused FormUnrecognised 0)
    (cons (Refused DeletionUnconfirmed (code_of_facet AmbientAbsent))
    (cons (Refused CitationMissing (code_of_facet CodegenNone))
    (cons (Refused AttributeMissing (code_of_facet AbiConform)) nil))))))) :=
  eq_refl.

Example every_refusal_rule_fires_on_a_witness :
  all_of (fun r => any_of (fun p => match rule_of (demo_check p) with
                                    | Some r2 => rule_eqb r r2
                                    | None => false
                                    end) refusal_witnesses) all_rules = true
  := eq_refl.

(* And every one of TAL-074's six phases is reached by one of them, so the
   phase enumeration is exercised and not only mapped. *)
Example every_phase_is_reached_by_a_witness :
  all_of (fun q => any_of (fun p => match rule_of (demo_check p) with
                                    | Some r => phase_eqb q (phase_of_rule r)
                                    | None => false
                                    end) refusal_witnesses) all_phases = true
  := eq_refl.

(* Reading 6 as a computation, twice. A package failing recognition and
   coverage at once is refused under the earlier phase; and a package leaving
   a move-I facet and a move-II facet both open is refused under the citation
   phase rather than the attribute phase, which is the whole content of
   TAL-074's ordering of its last three. *)
Example the_refusal_names_the_first_failing_phase :
  demo_check p_two_faults = Refused FormUnrecognised 8
  /\ covers demo TierTwo (with_steps (thin_cert 6)
       (cons {| st_judgment := past_the_judgments;
                st_move := past_the_moves;
                st_facet := past_the_facets;
                st_site := 8 |} nil)) = false
  /\ demo_check p_two_open_phases = Refused CitationMissing (code_of_facet CodegenNone)
  /\ discharged (drop_record_at 0 (drop_record_at 1 (covering_cert TierTwo 6)))
                AbiConform = false
  /\ discharged (drop_record_at 0 (drop_record_at 1 (covering_cert TierTwo 6)))
                CodegenNone = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* Reading 4 as a computation: a derivation that is absent and one that is
   thin draw different refusals, so the two are decided by different rules
   and not by one rule reading an emptiness twice. *)
Example the_absent_and_the_thin_are_refused_apart :
  demo_check w_absent = Refused DerivationAbsent 6
  /\ demo_check p_thin = Refused CitationMissing (code_of_facet CodegenNone)
  /\ verdict_eqb (demo_check w_absent) (demo_check p_thin) = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* And a thin derivation is admitted where the tier requires nothing, which is
   what makes it a value of the carrier rather than a case in the checker: the
   same package, the same reading, a different required set. *)
Example a_thin_derivation_is_admitted_where_the_tier_requires_nothing :
  spec_check demo_lenient Cert full_reading amb_first p_thin = Accepted
  /\ spec_check demo_lenient Cert full_reading amb_first w_absent
     = Refused DerivationAbsent 6 := conj eq_refl eq_refl.

(* The stale witness's derivation is otherwise complete: it recognises and it
   covers, and R-11-005's generation scope is the whole of what refuses it.
   Without this the version rule would be one of several failing at once. *)
Example the_stale_derivation_is_otherwise_complete :
  covers demo TierTwo (with_sail_model (S demo_versions.(ver_sail_model))
                         (covering_cert TierTwo 6)) = true
  /\ all_of step_recognised
       (with_sail_model (S demo_versions.(ver_sail_model))
          (covering_cert TierTwo 6)).(cert_steps) = true := conj eq_refl eq_refl.

(* Neither the attestation nor the composer's own authorship moves a verdict,
   which is R-13-013's *no admission rule reads a producer identity* and
   R-13-001c's *joins no trust base* at the demo roster. *)
Example neither_attestation_nor_authorship_moves_a_verdict :
  demo_check p_attested_and_thin = demo_check p_thin
  /\ demo_check p_from_the_composer = demo_check p_thin
  /\ p_attested_and_thin.(pkg_attested) = true
  /\ p_from_the_composer.(pkg_producer) = demo.(composer_id) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   The Tier-2 bar is the register's, and a stronger one is not.

   The reading that takes R-13-012's *temporal safety* for R-05-029's whole
   memory-safety row requires spatial safety of every Tier-2 package. That is
   a bar strictly stronger than the register's, and it is observable: the
   supervision tree's derivation discharges exactly R-13-012's seven facets,
   the register's machine admits it, and the row-granular one refuses it under
   the citation phase at the spatial facet's own code.
   ------------------------------------------------------------------------- *)

Example the_row_granular_reading_refuses_what_the_register_admits :
  demo_check supervision_tree = Accepted
  /\ spec_check demo_row_granular Cert full_reading amb_first supervision_tree
     = Refused CitationMissing (code_of_facet MemSpatial)
  /\ mem_facet MemSpatial (demo_row_granular.(required) TierTwo) = true
  /\ mem_facet MemSpatial (demo.(required) TierTwo) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* And the two required sets differ in exactly that one facet, so what
   separates them is the split R-05-036 states and nothing else. *)
Example the_two_readings_differ_in_exactly_one_facet :
  count_of (demo_row_granular.(required) TierTwo) = 8
  /\ count_of (demo.(required) TierTwo) = 7
  /\ all_of (fun f => mem_facet f (demo_row_granular.(required) TierTwo))
            (demo.(required) TierTwo) = true
  /\ count_of (filter_of (fun f => negb (mem_facet f (demo.(required) TierTwo)))
                         (demo_row_granular.(required) TierTwo)) = 1 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   The three carriers meet at one reading (reading 3).
   ------------------------------------------------------------------------- *)

Definition p_terse_thin : Package Terse :=
  {| pkg_id := 6; pkg_tier := code_of_tier TierTwo; pkg_producer := 3;
     pkg_attested := false; pkg_cert := Some 6 |}.

Example the_two_carriers_carry_the_same_package :
  p_terse_thin.(pkg_id) = p_thin.(pkg_id)
  /\ p_terse_thin.(pkg_tier) = p_thin.(pkg_tier)
  /\ p_terse_thin.(pkg_producer) = p_thin.(pkg_producer)
  /\ p_terse_thin.(pkg_attested) = p_thin.(pkg_attested)
  /\ p_terse_thin.(pkg_cert) = Some 6 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Theorem the_two_carriers_are_read_alike :
  reads_alike Terse Cert terse_reading full_reading p_terse_thin p_thin.
Proof. split; [ reflexivity | ]. split; reflexivity. Qed.

(* S14: and therefore they are decided alike, in any ambient, by the theorem
   quantified over arbitrary carriers rather than by a conversion at these
   two. The conversion beside it is what makes that theorem non-vacuous. *)
Theorem the_thin_derivation_is_decided_alike_over_either_carrier :
  forall a b : Ambient,
    spec_check demo Terse terse_reading a p_terse_thin
    = spec_check demo Cert full_reading b p_thin.
Proof.
  intros a b.
  exact (the_verdict_is_a_function_of_the_reading demo Terse Cert terse_reading
           full_reading a b p_terse_thin p_thin the_two_carriers_are_read_alike).
Qed.

Example the_terse_carrier_draws_the_same_refusal :
  spec_check demo Terse terse_reading amb_first p_terse_thin
  = Refused CitationMissing (code_of_facet CodegenNone) := eq_refl.

(* =========================================================================
   Refutation witnesses over the checker (R-05-166). Each is an alternative
   construction no index generates, and each is shown to satisfy the
   obligations it does not break, so what refutes it is the named defect
   rather than the shape of the construction.
   ========================================================================= *)

Lemma orb_split : forall a b : bool, orb a b = false -> a = false /\ b = false.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

(* A checker that admits whatever the composer is carrying the right state
   for: the composer's build record read as evidence, which R-06-015b's
   authority clause excludes by bounding a checker's reads to the candidate,
   its certificate and the profile. *)
Definition state_reading_check (m : Machine) (D : Type) (rd : Reading D) : Checker D :=
  fun a p => if Nat.eqb a.(amb_state) m.(composer_id)
             then Accepted
             else spec_check m D rd a p.

Theorem the_state_reading_check_reads_the_composer :
  ~ ReadsNoComposerState Cert (state_reading_check demo Cert full_reading).
Proof.
  intros H. specialize (H amb_first amb_composing p_thin eq_refl). discriminate H.
Qed.

(* And it is perfectly deterministic across runs, so what refutes it is the
   read and not a flakiness: the two halves of reading 2 are separate. *)
Theorem the_state_reading_check_is_run_independent :
  forall (m : Machine) (D : Type) (rd : Reading D),
    IsRunIndependent D (state_reading_check m D rd).
Proof.
  intros m D rd a1 a2 p H. unfold state_reading_check. rewrite H. reflexivity.
Qed.

(* And it reads no pedigree at all, which is the direction the file owes
   beside the attestation checker's: a composer's state is not a field of the
   package, so a checker reading it satisfies R-13-013's clause and breaks
   R-06-015b's. *)
Theorem the_state_reading_check_reads_no_pedigree :
  forall (m : Machine) (D : Type) (rd : Reading D),
    ReadsNoPedigree D (state_reading_check m D rd).
Proof.
  intros m D rd a p q H. unfold state_reading_check.
  destruct (Nat.eqb a.(amb_state) m.(composer_id)); [ reflexivity | ].
  exact (the_specification_reads_no_pedigree m D rd a p q H).
Qed.

Theorem the_state_reading_check_is_not_a_function_of_the_package :
  ~ IsAFunctionOfThePackage Cert (state_reading_check demo Cert full_reading).
Proof.
  intros H. specialize (H amb_first amb_composing p_thin). discriminate H.
Qed.

Example the_state_reading_check_agrees_away_from_the_composer :
  state_reading_check demo Cert full_reading amb_first p_thin = demo_check p_thin
  /\ state_reading_check demo Cert full_reading amb_composing p_thin = Accepted :=
  conj eq_refl eq_refl.

(* A checker that answers differently on a second run over the same input,
   which is TAL-001's own criterion read backwards. It reads no composer
   state at all. *)
Definition flaky_check (m : Machine) (D : Type) (rd : Reading D) : Checker D :=
  fun a p => match a.(amb_run) with
             | 0 => spec_check m D rd a p
             | S _ => Accepted
             end.

Theorem the_flaky_check_answers_differently_on_a_second_run :
  ~ IsRunIndependent Cert (flaky_check demo Cert full_reading).
Proof.
  intros H. specialize (H amb_first amb_second p_thin eq_refl). discriminate H.
Qed.

Theorem the_flaky_check_reads_no_composer_state :
  forall (m : Machine) (D : Type) (rd : Reading D),
    ReadsNoComposerState D (flaky_check m D rd).
Proof.
  intros m D rd a1 a2 p H. unfold flaky_check. rewrite H.
  destruct (amb_run a2); reflexivity.
Qed.

Example the_flaky_check_agrees_on_the_first_run :
  flaky_check demo Cert full_reading amb_first p_thin = demo_check p_thin
  /\ flaky_check demo Cert full_reading amb_second p_thin = Accepted :=
  conj eq_refl eq_refl.

(* The two constructions together are what proves reading 2's halves are two
   obligations: each satisfies one and breaks the other, and the conjunction
   is what neither has. *)
Theorem neither_half_alone_is_the_property :
  IsRunIndependent Cert (state_reading_check demo Cert full_reading)
  /\ ~ ReadsNoComposerState Cert (state_reading_check demo Cert full_reading)
  /\ ReadsNoComposerState Cert (flaky_check demo Cert full_reading)
  /\ ~ IsRunIndependent Cert (flaky_check demo Cert full_reading).
Proof.
  split; [ exact (the_state_reading_check_is_run_independent demo Cert full_reading) | ].
  split; [ exact the_state_reading_check_reads_the_composer | ].
  split; [ exact (the_flaky_check_reads_no_composer_state demo Cert full_reading) | ].
  exact the_flaky_check_answers_differently_on_a_second_run.
Qed.

(* -------------------------------------------------------------------------
   The carrier the checker may not look behind (reading 3, R-13-003).
   ------------------------------------------------------------------------- *)

Definition p_tagged_zero : Package Tagged :=
  {| pkg_id := 6; pkg_tier := code_of_tier TierTwo; pkg_producer := 3;
     pkg_attested := false; pkg_cert := Some (pair 0 (covering_cert TierTwo 6)) |}.

Definition p_tagged_one : Package Tagged :=
  {| pkg_id := 6; pkg_tier := code_of_tier TierTwo; pkg_producer := 3;
     pkg_attested := false; pkg_cert := Some (pair 1 (covering_cert TierTwo 6)) |}.

(* Two values of one carrier that read alike: the reading forgets the tag, so
   nothing a checker is entitled to see tells them apart. *)
Example the_two_tagged_packages_read_alike :
  read_cert Tagged tag_reading p_tagged_zero
  = read_cert Tagged tag_reading p_tagged_one
  /\ p_tagged_zero.(pkg_id) = p_tagged_one.(pkg_id)
  /\ p_tagged_zero.(pkg_tier) = p_tagged_one.(pkg_tier) :=
  conj eq_refl (conj eq_refl eq_refl).

(* A checker that looks behind the reading at the carrier itself. It is not
   even unsound for it, refusing where it looks rather than admitting, which
   is exactly why carrier-abstraction is an obligation of its own rather than
   a corollary of fail-closed. *)
Definition tag_peeking_check (m : Machine) : Checker Tagged :=
  fun a p => match p.(pkg_cert) with
             | Some x => if Nat.eqb (fst x) 0
                         then spec_check m Tagged tag_reading a p
                         else Refused BindingMismatch p.(pkg_id)
             | None => spec_check m Tagged tag_reading a p
             end.

Theorem the_tag_peeking_check_reads_the_carrier :
  ~ IsAFunctionOfTheReading Tagged tag_reading (tag_peeking_check demo).
Proof.
  intros H.
  specialize (H amb_first amb_first p_tagged_zero p_tagged_one
                eq_refl eq_refl eq_refl).
  discriminate H.
Qed.

(* And it keeps every obligation the reading obligation is not: it fails
   closed, it is a function of the package, and it reads no pedigree. *)
Theorem the_tag_peeking_check_fails_closed :
  forall m : Machine, FailsClosed m Tagged tag_reading (tag_peeking_check m).
Proof.
  intros m a p H. unfold tag_peeking_check in H.
  destruct (pkg_cert p) as [ x | ].
  - destruct (Nat.eqb (fst x) 0).
    + exact (the_specification_fails_closed m Tagged tag_reading a p H).
    + discriminate H.
  - exact (the_specification_fails_closed m Tagged tag_reading a p H).
Qed.

Theorem the_tag_peeking_check_is_a_function_of_the_package :
  forall m : Machine, IsAFunctionOfThePackage Tagged (tag_peeking_check m).
Proof.
  intros m a1 a2 p. unfold tag_peeking_check.
  destruct (pkg_cert p) as [ x | ]; [ destruct (Nat.eqb (fst x) 0) | ];
    reflexivity.
Qed.

Theorem the_tag_peeking_check_reads_no_pedigree :
  forall m : Machine, ReadsNoPedigree Tagged (tag_peeking_check m).
Proof.
  intros m a p q H. assert (H2 := H). destruct H2 as [ Hid H3 ].
  destruct H3 as [ Ht Hc ]. unfold tag_peeking_check. rewrite Hc. rewrite Hid.
  destruct (pkg_cert q) as [ x | ]; [ destruct (Nat.eqb (fst x) 0) | ];
    try reflexivity;
    exact (the_specification_reads_no_pedigree m Tagged tag_reading a p q H).
Qed.

Example the_tag_peeking_check_answers_two_readings_alike_apart :
  tag_peeking_check demo amb_first p_tagged_zero = Accepted
  /\ tag_peeking_check demo amb_first p_tagged_one = Refused BindingMismatch 6
  /\ spec_check demo Tagged tag_reading amb_first p_tagged_zero = Accepted
  /\ spec_check demo Tagged tag_reading amb_first p_tagged_one = Accepted :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   The pedigree constructions (R-13-013, R-13-001c, R-13-022).
   ------------------------------------------------------------------------- *)

(* The same package under another author and another attestation: the pair
   R-13-013's *no admission rule reads a producer identity* quantifies over. *)
Definition p_badged : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 5 true (Some (thin_cert 6)).

Example the_badged_package_differs_only_in_its_pedigree :
  p_badged.(pkg_id) = p_thin.(pkg_id)
  /\ p_badged.(pkg_tier) = p_thin.(pkg_tier)
  /\ p_badged.(pkg_producer) = 5
  /\ p_thin.(pkg_producer) = 3
  /\ p_badged.(pkg_attested) = true
  /\ p_thin.(pkg_attested) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Theorem the_badged_package_differs_only_there :
  same_but_the_pedigree Cert p_thin p_badged.
Proof. split; [ reflexivity | ]. split; reflexivity. Qed.

(* A checker that admits an attested package: the producer attestation read as
   evidence, which R-13-022's *another producer emitting equivalent checked
   evidence is admitted identically* excludes from the other side. *)
Definition attestation_check (m : Machine) (D : Type) (rd : Reading D) : Checker D :=
  fun a p => if p.(pkg_attested) then Accepted else spec_check m D rd a p.

Theorem the_attestation_check_reads_a_pedigree :
  ~ ReadsNoPedigree Cert (attestation_check demo Cert full_reading).
Proof.
  intros H. specialize (H amb_first p_thin p_badged the_badged_package_differs_only_there).
  discriminate H.
Qed.

Theorem the_attestation_check_is_a_function_of_the_package :
  forall (m : Machine) (D : Type) (rd : Reading D),
    IsAFunctionOfThePackage D (attestation_check m D rd).
Proof.
  intros m D rd a1 a2 p. unfold attestation_check.
  destruct (pkg_attested p); reflexivity.
Qed.

(* The two authority obligations are two, and the separation runs both ways.
   A producer identity is a field of the package, so a checker reading it is a
   function of the package and reads a pedigree; a composer's state is not a
   field of the package, so a checker reading that reads no pedigree and is no
   function of the package. Neither obligation implies the other. *)
Theorem neither_authority_obligation_implies_the_other :
  IsAFunctionOfThePackage Cert (attestation_check demo Cert full_reading)
  /\ ~ ReadsNoPedigree Cert (attestation_check demo Cert full_reading)
  /\ ReadsNoPedigree Cert (state_reading_check demo Cert full_reading)
  /\ ~ IsAFunctionOfThePackage Cert (state_reading_check demo Cert full_reading).
Proof.
  split; [ exact (the_attestation_check_is_a_function_of_the_package
                    demo Cert full_reading) | ].
  split; [ exact the_attestation_check_reads_a_pedigree | ].
  split; [ exact (the_state_reading_check_reads_no_pedigree demo Cert full_reading) | ].
  exact the_state_reading_check_is_not_a_function_of_the_package.
Qed.

(* A checker that trusts the composer's own output: the construction
   R-13-001c's *the composer joins no trust base* excludes in its own words,
   and the one an offline composition is most tempted by, its own bytes being
   the ones it has just emitted. *)
Definition trusting_check (m : Machine) (D : Type) (rd : Reading D) : Checker D :=
  fun a p => if Nat.eqb p.(pkg_producer) m.(composer_id)
             then Accepted
             else spec_check m D rd a p.

Definition p_other_author : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 true (Some (thin_cert 6)).

Theorem the_other_author_differs_only_there :
  same_but_the_pedigree Cert p_from_the_composer p_other_author.
Proof. split; [ reflexivity | ]. split; reflexivity. Qed.

(* The other author's package is attested and is still refused, which is what
   makes the trusting checker's defect the *composer's* identity rather than
   the presence of an attestation: an attested package from anyone else buys
   nothing from it either. *)
Example the_other_author_is_attested_and_still_refused :
  p_other_author.(pkg_producer) = 3
  /\ p_other_author.(pkg_attested) = true
  /\ p_from_the_composer.(pkg_producer) = demo.(composer_id)
  /\ demo_check p_other_author = Refused CitationMissing (code_of_facet CodegenNone)
  /\ trusting_check demo Cert full_reading amb_first p_other_author
     = Refused CitationMissing (code_of_facet CodegenNone)
  /\ trusting_check demo Cert full_reading amb_first p_from_the_composer = Accepted :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Theorem the_trusting_check_reads_a_pedigree :
  ~ ReadsNoPedigree Cert (trusting_check demo Cert full_reading).
Proof.
  intros H.
  specialize (H amb_first p_from_the_composer p_other_author
                the_other_author_differs_only_there).
  discriminate H.
Qed.

(* And it is unsound, which the attestation checker on its own does not show:
   the package it waves through carries a thin derivation covering none of its
   tier's facets. *)
Theorem the_thin_package_is_not_well_typed :
  ~ WellTyped demo Cert full_reading p_thin.
Proof.
  intros H.
  assert (Hacc : accepts (spec_check demo Cert full_reading amb_first p_thin) = true)
    by exact (the_specification_is_complete_for_the_typing_relation
                demo Cert full_reading amb_first p_thin H).
  discriminate Hacc.
Qed.

Theorem the_composer_authored_package_is_not_well_typed :
  ~ WellTyped demo Cert full_reading p_from_the_composer.
Proof.
  intros H.
  assert (Hacc : accepts (spec_check demo Cert full_reading amb_first
                            p_from_the_composer) = true)
    by exact (the_specification_is_complete_for_the_typing_relation
                demo Cert full_reading amb_first p_from_the_composer H).
  discriminate Hacc.
Qed.

Theorem the_trusting_check_fails_open :
  ~ FailsClosed demo Cert full_reading (trusting_check demo Cert full_reading).
Proof.
  intros H.
  exact (the_composer_authored_package_is_not_well_typed
           (H amb_first p_from_the_composer eq_refl)).
Qed.

(* And it agrees with the specification on every package the composer did not
   author, so what refutes it is the pedigree read and not a different table.
   That is R-13-001c's clause made checkable: what the entry buys is not that
   the composer is honest but that its output is checked on the same terms as
   anyone's. *)
Example the_trusting_check_agrees_on_the_golden_roster :
  map_over (fun p => trusting_check demo Cert full_reading amb_first p) golden_roster
  = map_over demo_check golden_roster := eq_refl.

(* -------------------------------------------------------------------------
   The two poles: a checker that refuses everything and one that admits
   everything. R-17-033 is what puts them on different sides, an incomplete
   checker costing delivery and an unsound one costing safety, and the pair is
   what shows soundness and completeness are two obligations.
   ------------------------------------------------------------------------- *)

Definition paranoid_check (D : Type) : Checker D :=
  fun _ p => Refused AttributeMissing p.(pkg_id).

Definition blanket_check (D : Type) : Checker D := fun _ _ => Accepted.

(* The paranoid checker is sound for *every* typing relation, including ones
   nothing satisfies, which is exactly why soundness alone is not the
   property. *)
Theorem the_paranoid_check_is_sound_for_anything :
  forall (D : Type) (T : Typing D), SoundFor D T (paranoid_check D).
Proof. intros D T a p H. discriminate H. Qed.

Theorem the_admitted_component_is_well_typed :
  WellTyped demo Cert full_reading supervision_tree.
Proof.
  exact (the_specification_fails_closed demo Cert full_reading amb_first
           supervision_tree eq_refl).
Qed.

Theorem the_paranoid_check_is_not_complete :
  ~ CompleteFor Cert (WellTyped demo Cert full_reading) (paranoid_check Cert).
Proof.
  intros H. specialize (H amb_first supervision_tree the_admitted_component_is_well_typed).
  discriminate H.
Qed.

(* The blanket checker is complete for every relation and sound for none that
   anything fails, which is the same pair from the other end. *)
Theorem the_blanket_check_is_complete_for_anything :
  forall (D : Type) (T : Typing D), CompleteFor D T (blanket_check D).
Proof. intros D T a p H. reflexivity. Qed.

Theorem the_blanket_check_fails_open :
  ~ FailsClosed demo Cert full_reading (blanket_check Cert).
Proof.
  intros H. exact (the_thin_package_is_not_well_typed (H amb_first p_thin eq_refl)).
Qed.

(* And both are functions of the package alone and read no pedigree, so
   neither of those two obligations is what separates a checker worth having
   from one that is not. *)
Theorem the_two_poles_satisfy_the_other_obligations :
  IsAFunctionOfThePackage Cert (paranoid_check Cert)
  /\ ReadsNoPedigree Cert (paranoid_check Cert)
  /\ IsAFunctionOfThePackage Cert (blanket_check Cert)
  /\ ReadsNoPedigree Cert (blanket_check Cert).
Proof.
  split; [ intros a1 a2 p; reflexivity | ].
  split.
  - intros a p q H. destruct H as [ Hid _ ]. unfold paranoid_check. rewrite Hid.
    reflexivity.
  - split; [ intros a1 a2 p; reflexivity | ]. intros a p q H. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   TAL-001's two halves at the verdict's payload: a stable rule and a stable
   site are two properties, and each has a construction that keeps it while
   breaking the other.
   ------------------------------------------------------------------------- *)

Definition wandering_site_check (D : Type) : Checker D :=
  fun a p => Refused AttributeMissing a.(amb_run).

Definition wandering_rule_check (D : Type) : Checker D :=
  fun a p => match a.(amb_run) with
             | 0 => Refused CitationMissing p.(pkg_id)
             | S _ => Refused AttributeMissing p.(pkg_id)
             end.

Theorem the_wandering_site_check_names_a_stable_rule :
  forall D : Type, NamesAStableRule D (wandering_site_check D).
Proof. intros D a1 a2 p. reflexivity. Qed.

Theorem the_wandering_site_check_moves_the_site :
  ~ NamesAStableSite Cert (wandering_site_check Cert).
Proof. intros H. specialize (H amb_first amb_second p_thin). discriminate H. Qed.

Theorem the_wandering_rule_check_names_a_stable_site :
  forall D : Type, NamesAStableSite D (wandering_rule_check D).
Proof.
  intros D a1 a2 p. unfold wandering_rule_check.
  destruct (amb_run a1); destruct (amb_run a2); reflexivity.
Qed.

Theorem the_wandering_rule_check_moves_the_rule :
  ~ NamesAStableRule Cert (wandering_rule_check Cert).
Proof. intros H. specialize (H amb_first amb_second p_thin). discriminate H. Qed.

(* Both are sound for every relation, so what refutes each is the payload and
   not an admission. TAL-001's *identical verdicts and identical rejection
   sites* is therefore two clauses, and this is the pair that says so. *)
Theorem neither_payload_half_implies_the_other :
  NamesAStableRule Cert (wandering_site_check Cert)
  /\ ~ NamesAStableSite Cert (wandering_site_check Cert)
  /\ NamesAStableSite Cert (wandering_rule_check Cert)
  /\ ~ NamesAStableRule Cert (wandering_rule_check Cert)
  /\ (forall T : Typing Cert, SoundFor Cert T (wandering_site_check Cert))
  /\ (forall T : Typing Cert, SoundFor Cert T (wandering_rule_check Cert)).
Proof.
  split; [ exact (the_wandering_site_check_names_a_stable_rule Cert) | ].
  split; [ exact the_wandering_site_check_moves_the_site | ].
  split; [ exact (the_wandering_rule_check_names_a_stable_site Cert) | ].
  split; [ exact the_wandering_rule_check_moves_the_rule | ].
  split; [ intros T a p H; discriminate H | ].
  intros T a p H. unfold wandering_rule_check in H.
  destruct (amb_run a); discriminate H.
Qed.

Example the_two_wandering_checks_move_different_halves :
  rule_of (wandering_site_check Cert amb_first p_thin)
  = rule_of (wandering_site_check Cert amb_second p_thin)
  /\ site_of (wandering_site_check Cert amb_first p_thin) = Some 0
  /\ site_of (wandering_site_check Cert amb_second p_thin) = Some 1
  /\ site_of (wandering_rule_check Cert amb_first p_thin)
     = site_of (wandering_rule_check Cert amb_second p_thin)
  /\ rule_of (wandering_rule_check Cert amb_first p_thin) = Some CitationMissing
  /\ rule_of (wandering_rule_check Cert amb_second p_thin) = Some AttributeMissing :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* =========================================================================
   Five fail-open or mis-ordered constructions no index generates.

   The waived family above weakens a checker by rewriting its verdict; these
   five weaken the algorithm instead, each in the way its own clause invites.
   Each is shown to keep the clauses it does not break, so what refuses it is
   the named defect and not the shape of the construction.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   A checker for which an absent derivation is nothing to check.

   R-13-003 names the typing derivation as a part of the admitted artifact and
   R-13-011 has every admitted artifact carry its required evidence, so a
   package with no derivation carries none of it. The construction that reads
   the absence as a vacuous success is the one those two exclude, and it is
   the natural mistake at a bring-up where the derivations are thin: a
   derivation with no records and no derivation at all look alike from a
   distance, and reading 4 is that they are not.
   ------------------------------------------------------------------------- *)

Definition nothing_to_check (m : Machine) (D : Type) (rd : Reading D) : Checker D :=
  fun _ p =>
    match tier_of_code p.(pkg_tier) with
    | None => Refused TierUnrecognised p.(pkg_id)
    | Some _ =>
        match p.(pkg_cert) with
        | None => Accepted
        | Some d => check_cert m p.(pkg_id) p.(pkg_tier) (rd d)
        end
    end.

Theorem the_vacuous_check_admits_an_absent_derivation :
  ~ RefusesAnAbsentDerivation Cert (nothing_to_check demo Cert full_reading).
Proof.
  intros H. specialize (H amb_first w_absent eq_refl). discriminate H.
Qed.

Theorem the_vacuous_check_keeps_the_other_seven :
  forall (m : Machine) (D : Type) (rd : Reading D),
    RefusesAStaleVersion m D rd (nothing_to_check m D rd)
    /\ RefusesAWrongBinding D rd (nothing_to_check m D rd)
    /\ RefusesAnUnrecognisedTier D (nothing_to_check m D rd)
    /\ RefusesAnUnrecognisedForm D rd (nothing_to_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd ConfirmADeletion (nothing_to_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd CiteAnInvariant (nothing_to_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd EvaluateAnAttribute
         (nothing_to_check m D rd).
Proof.
  intros m D rd. unfold nothing_to_check. split.
  { intros a p d Hc Hv. destruct (tier_of_code p.(pkg_tier)) as [ t | ];
      [ | reflexivity ]. rewrite Hc.
    exact (check_cert_refuses_a_stale_version m p.(pkg_id) p.(pkg_tier) (rd d) Hv). }
  split.
  { intros a p d Hc Hb. destruct (tier_of_code p.(pkg_tier)) as [ t | ];
      [ | reflexivity ]. rewrite Hc.
    exact (check_cert_refuses_a_wrong_binding m p.(pkg_id) p.(pkg_tier) (rd d) Hb). }
  split.
  { intros a p Ht. rewrite Ht. reflexivity. }
  split.
  { intros a p d Hc Hr. destruct (tier_of_code p.(pkg_tier)) as [ t | ];
      [ | reflexivity ]. rewrite Hc.
    exact (check_cert_refuses_an_unrecognised_form m p.(pkg_id) p.(pkg_tier) (rd d) Hr). }
  split.
  { intros a p d t f Hc Ht Hm Hk Hd. rewrite Ht. rewrite Hc.
    exact (check_cert_refuses_an_undischarged_facet m p.(pkg_id) p.(pkg_tier) t (rd d)
             Ht (an_open_facet_breaks_the_coverage m t (rd d) f Hm Hd)). }
  split.
  { intros a p d t f Hc Ht Hm Hk Hd. rewrite Ht. rewrite Hc.
    exact (check_cert_refuses_an_undischarged_facet m p.(pkg_id) p.(pkg_tier) t (rd d)
             Ht (an_open_facet_breaks_the_coverage m t (rd d) f Hm Hd)). }
  intros a p d t f Hc Ht Hm Hk Hd. rewrite Ht. rewrite Hc.
  exact (check_cert_refuses_an_undischarged_facet m p.(pkg_id) p.(pkg_tier) t (rd d)
           Ht (an_open_facet_breaks_the_coverage m t (rd d) f Hm Hd)).
Qed.

Example the_vacuous_check_differs_at_exactly_one_witness :
  map_over (fun p => nothing_to_check demo Cert full_reading amb_first p)
           refusal_witnesses
  = cons Accepted
    (cons (Refused VersionMismatch 6)
    (cons (Refused BindingMismatch 6)
    (cons (Refused TierUnrecognised 6)
    (cons (Refused FormUnrecognised 0)
    (cons (Refused DeletionUnconfirmed (code_of_facet AmbientAbsent))
    (cons (Refused CitationMissing (code_of_facet CodegenNone))
    (cons (Refused AttributeMissing (code_of_facet AbiConform)) nil)))))))
  /\ map_over (fun p => nothing_to_check demo Cert full_reading amb_first p)
              golden_roster
     = map_over demo_check golden_roster :=
  conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   A checker with a permissive default at an unrecognised record.
   ------------------------------------------------------------------------- *)

Lemma any_of_filter_implies :
  forall (A : Type) (p q : A -> bool) (l : list A),
    any_of p (filter_of q l) = true -> any_of p l = true.
Proof.
  intros A p q l. induction l as [ | x r IH ]; intros H.
  - discriminate H.
  - simpl. simpl in H. destruct (q x) eqn:E.
    + simpl in H. destruct (p x); [ reflexivity | simpl in H; simpl; exact (IH H) ].
    + rewrite (IH H). destruct (p x); reflexivity.
Qed.

Lemma an_open_facet_stays_open_when_records_are_dropped :
  forall (c : Cert) (f : Facet),
    discharged c f = false ->
    discharged (with_steps c (filter_of step_recognised c.(cert_steps))) f = false.
Proof.
  intros c f H.
  destruct (discharged (with_steps c (filter_of step_recognised c.(cert_steps))) f)
    eqn:E; [ | reflexivity ].
  unfold discharged in E. simpl in E. unfold discharged in H.
  rewrite (any_of_filter_implies Step (fun s => discharges s f)
             step_recognised c.(cert_steps) E) in H.
  discriminate H.
Qed.

Lemma dropping_a_record_can_only_lose_coverage :
  forall (m : Machine) (t : Tier) (c : Cert),
    covers m t c = false ->
    covers m t (with_steps c (filter_of step_recognised c.(cert_steps))) = false.
Proof.
  intros m t c H.
  destruct (covers m t (with_steps c (filter_of step_recognised c.(cert_steps))))
    eqn:E; [ | reflexivity ].
  unfold covers in E. unfold covers in H.
  assert (Himp : forall f : Facet,
            discharged (with_steps c (filter_of step_recognised c.(cert_steps))) f
              = true -> discharged c f = true).
  { intros f Hf. destruct (discharged c f) eqn:Ec; [ reflexivity | ].
    rewrite (an_open_facet_stays_open_when_records_are_dropped c f Ec) in Hf.
    discriminate Hf. }
  rewrite (all_of_mono Facet _ (discharged c) (m.(required) t) Himp E) in H.
  discriminate H.
Qed.

(* TAL-023's own words are that an instruction form with no rule is a profile
   defect and *not a permissive default*. This is that default: a record the
   checker does not recognise is dropped and the rest of the derivation is
   checked as though it were the whole. It is the most plausible weakening
   there is, because it makes the checker tolerant of a producer emitting a
   record it has not yet learned to read. *)
Definition permissive_form_check (m : Machine) (D : Type) (rd : Reading D)
    : Checker D :=
  fun _ p =>
    match p.(pkg_cert) with
    | None => Refused DerivationAbsent p.(pkg_id)
    | Some d =>
        check_cert m p.(pkg_id) p.(pkg_tier)
          (with_steps (rd d) (filter_of step_recognised (rd d).(cert_steps)))
    end.

(* Append one record to a derivation and change nothing else. *)
Definition with_extra_record (s : Step) (c : Cert) : Cert :=
  with_steps c (app c.(cert_steps) (cons s nil)).

Definition the_unreadable_record : Step :=
  {| st_judgment := past_the_judgments;
     st_move := code_of_move EvaluateAnAttribute;
     st_facet := code_of_facet CtTaint;
     st_site := 7 |}.

Example the_unreadable_record_is_unrecognised :
  step_recognised the_unreadable_record = false
  /\ the_unreadable_record.(st_facet) = code_of_facet CtTaint
  /\ the_unreadable_record.(st_site) = 7
  /\ facet_of_code the_unreadable_record.(st_facet) = Some CtTaint :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* A component whose derivation covers its tier and carries one further record
   the checker cannot read: the input on which dropping and refusing differ. *)
Definition p_extra_unknown_record : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false
    (Some (with_extra_record the_unreadable_record (covering_cert TierTwo 6))).

Theorem the_permissive_check_admits_an_unrecognised_form :
  ~ RefusesAnUnrecognisedForm Cert full_reading
      (permissive_form_check demo Cert full_reading).
Proof.
  intros H.
  specialize (H amb_first p_extra_unknown_record
                (with_extra_record the_unreadable_record (covering_cert TierTwo 6))
                eq_refl eq_refl).
  discriminate H.
Qed.

(* And it keeps every other clause: dropping a record can only lose coverage,
   so the coverage refusals survive the drop, and the version, binding, tier
   and absence clauses are untouched by it. *)
Theorem the_permissive_check_keeps_the_other_seven :
  forall (m : Machine) (D : Type) (rd : Reading D),
    RefusesAnAbsentDerivation D (permissive_form_check m D rd)
    /\ RefusesAStaleVersion m D rd (permissive_form_check m D rd)
    /\ RefusesAWrongBinding D rd (permissive_form_check m D rd)
    /\ RefusesAnUnrecognisedTier D (permissive_form_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd ConfirmADeletion
         (permissive_form_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd CiteAnInvariant
         (permissive_form_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd EvaluateAnAttribute
         (permissive_form_check m D rd).
Proof.
  intros m D rd. unfold permissive_form_check. split.
  { intros a p Hc. rewrite Hc. reflexivity. }
  split.
  { intros a p d Hc Hv. rewrite Hc.
    exact (check_cert_refuses_a_stale_version m p.(pkg_id) p.(pkg_tier)
             (with_steps (rd d) (filter_of step_recognised (rd d).(cert_steps))) Hv). }
  split.
  { intros a p d Hc Hb. rewrite Hc.
    exact (check_cert_refuses_a_wrong_binding m p.(pkg_id) p.(pkg_tier)
             (with_steps (rd d) (filter_of step_recognised (rd d).(cert_steps))) Hb). }
  split.
  { intros a p Ht. destruct (pkg_cert p) as [ d | ]; [ | reflexivity ].
    exact (check_cert_refuses_an_unrecognised_tier m p.(pkg_id) p.(pkg_tier)
             (with_steps (rd d) (filter_of step_recognised (rd d).(cert_steps))) Ht). }
  split.
  { intros a p d t f Hc Ht Hm Hk Hd. rewrite Hc.
    exact (check_cert_refuses_an_undischarged_facet m p.(pkg_id) p.(pkg_tier) t
             (with_steps (rd d) (filter_of step_recognised (rd d).(cert_steps))) Ht
             (an_open_facet_breaks_the_coverage m t
                (with_steps (rd d) (filter_of step_recognised (rd d).(cert_steps)))
                f Hm (an_open_facet_stays_open_when_records_are_dropped (rd d) f Hd))). }
  split.
  { intros a p d t f Hc Ht Hm Hk Hd. rewrite Hc.
    exact (check_cert_refuses_an_undischarged_facet m p.(pkg_id) p.(pkg_tier) t
             (with_steps (rd d) (filter_of step_recognised (rd d).(cert_steps))) Ht
             (an_open_facet_breaks_the_coverage m t
                (with_steps (rd d) (filter_of step_recognised (rd d).(cert_steps)))
                f Hm (an_open_facet_stays_open_when_records_are_dropped (rd d) f Hd))). }
  intros a p d t f Hc Ht Hm Hk Hd. rewrite Hc.
  exact (check_cert_refuses_an_undischarged_facet m p.(pkg_id) p.(pkg_tier) t
           (with_steps (rd d) (filter_of step_recognised (rd d).(cert_steps))) Ht
           (an_open_facet_breaks_the_coverage m t
              (with_steps (rd d) (filter_of step_recognised (rd d).(cert_steps)))
              f Hm (an_open_facet_stays_open_when_records_are_dropped (rd d) f Hd))).
Qed.

(* On the golden roster it agrees with the specification exactly, so the
   defect is invisible to any roster whose derivations the checker can read
   whole. That is what makes it worth stating: a permissive default costs
   nothing until the day a producer emits a record the checker has not
   learned. *)
Example the_permissive_check_is_invisible_until_a_record_is_unreadable :
  map_over (fun p => permissive_form_check demo Cert full_reading amb_first p)
           golden_roster
  = map_over demo_check golden_roster
  /\ demo_check p_extra_unknown_record = Refused FormUnrecognised 7
  /\ permissive_form_check demo Cert full_reading amb_first p_extra_unknown_record
     = Accepted :=
  conj eq_refl (conj eq_refl eq_refl).

(* -------------------------------------------------------------------------
   A checker that reads a record's facet and ignores its move.

   R-05-029's criterion is that a derivation carries *an attribute, citation,
   or deletion-check* for each listed obligation, and R-05-037, R-05-038 and
   R-05-039 assign one of the three to each facet. The checker below reads
   every record as though it made the move its facet requires, which is
   exactly the reading that drops the assignment, and it admits a derivation
   discharging no-runtime-codegen by an attribute where R-05-037 assigns a
   citation. It is the axis the register constrains exactly, so it is refuted
   rather than shown free.
   ------------------------------------------------------------------------- *)

Definition reroute (s : Step) : Step :=
  match facet_of_code s.(st_facet), move_of_code s.(st_move) with
  | Some f, Some _ => {| st_judgment := s.(st_judgment);
                         st_move := code_of_move (move_of f);
                         st_facet := s.(st_facet);
                         st_site := s.(st_site) |}
  | _, _ => s
  end.

Definition move_blind_check (m : Machine) (D : Type) (rd : Reading D) : Checker D :=
  fun _ p =>
    match p.(pkg_cert) with
    | None => Refused DerivationAbsent p.(pkg_id)
    | Some d => check_cert m p.(pkg_id) p.(pkg_tier)
                  (with_steps (rd d) (map_over reroute (rd d).(cert_steps)))
    end.

Lemma reroute_preserves_recognition :
  forall s : Step, step_recognised (reroute s) = step_recognised s.
Proof.
  intros s. unfold reroute. unfold step_recognised.
  destruct (facet_of_code s.(st_facet)) as [ f | ] eqn:Ef;
    destruct (move_of_code s.(st_move)) as [ k | ] eqn:Ek; simpl;
    try (rewrite Ef); try (rewrite Ek); try reflexivity.
  rewrite (every_move_decodes_to_itself (move_of f)). reflexivity.
Qed.

Lemma rerouting_preserves_every_recognition :
  forall l : list Step,
    all_of step_recognised (map_over reroute l) = all_of step_recognised l.
Proof.
  intros l. induction l as [ | s r IH ].
  - reflexivity.
  - simpl. rewrite (reroute_preserves_recognition s). rewrite IH. reflexivity.
Qed.

(* Which facet a record names, whatever move it makes. Rerouting does not
   change it, so a facet no record names is undischarged for the blind checker
   too: what it loses is the move assignment and not the facet assignment. *)
Definition names_facet (f : Facet) (s : Step) : bool :=
  match facet_of_code s.(st_facet) with Some g => facet_eqb f g | None => false end.

Lemma a_discharge_names_its_facet :
  forall (s : Step) (f : Facet), discharges s f = true -> names_facet f s = true.
Proof.
  intros s f H. unfold discharges in H. unfold names_facet.
  destruct (facet_of_code s.(st_facet)) as [ g | ]; [ | discriminate H ].
  destruct (move_of_code s.(st_move)) as [ k | ]; [ | discriminate H ].
  destruct (andb_split _ _ H) as [ Hg _ ]. exact Hg.
Qed.

Lemma reroute_names_the_same_facet :
  forall (s : Step) (f : Facet), names_facet f (reroute s) = names_facet f s.
Proof.
  intros s f. unfold reroute. unfold names_facet.
  destruct (facet_of_code s.(st_facet)) as [ g | ] eqn:Eg;
    destruct (move_of_code s.(st_move)) as [ k | ] eqn:Ek; simpl;
    try (rewrite Eg); reflexivity.
Qed.

Lemma an_unnamed_facet_is_undischarged_after_rerouting :
  forall (l : list Step) (f : Facet),
    any_of (names_facet f) l = false ->
    any_of (fun s => discharges s f) (map_over reroute l) = false.
Proof.
  intros l f. induction l as [ | s r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (orb_split _ _ H) as [ Hs Hr ].
    simpl. destruct (discharges (reroute s) f) eqn:E.
    + rewrite <- (reroute_names_the_same_facet s f) in Hs.
      rewrite (a_discharge_names_its_facet (reroute s) f E) in Hs.
      discriminate Hs.
    + simpl. exact (IH Hr).
Qed.

Theorem the_move_blind_check_admits_a_misrouted_discharge :
  ~ RefusesAnUndischargedFacetOf demo Cert full_reading CiteAnInvariant
      (move_blind_check demo Cert full_reading).
Proof.
  intros H.
  specialize (H amb_first w_misrouted (misroute_at 1 (covering_cert TierTwo 6))
                TierTwo CodegenNone eq_refl eq_refl eq_refl eq_refl eq_refl).
  discriminate H.
Qed.

(* And it keeps the five clauses that are not about the move table, and still
   refuses a facet no record of the derivation names at all: what it loses is
   R-05-037's and R-05-039's assignment and nothing else. *)
Theorem the_move_blind_check_keeps_the_five_clauses_before_the_moves :
  forall (m : Machine) (D : Type) (rd : Reading D),
    RefusesAnAbsentDerivation D (move_blind_check m D rd)
    /\ RefusesAStaleVersion m D rd (move_blind_check m D rd)
    /\ RefusesAWrongBinding D rd (move_blind_check m D rd)
    /\ RefusesAnUnrecognisedTier D (move_blind_check m D rd)
    /\ RefusesAnUnrecognisedForm D rd (move_blind_check m D rd).
Proof.
  intros m D rd. unfold move_blind_check. split.
  { intros a p Hc. rewrite Hc. reflexivity. }
  split.
  { intros a p d Hc Hv. rewrite Hc.
    exact (check_cert_refuses_a_stale_version m p.(pkg_id) p.(pkg_tier)
             (with_steps (rd d) (map_over reroute (rd d).(cert_steps))) Hv). }
  split.
  { intros a p d Hc Hb. rewrite Hc.
    exact (check_cert_refuses_a_wrong_binding m p.(pkg_id) p.(pkg_tier)
             (with_steps (rd d) (map_over reroute (rd d).(cert_steps))) Hb). }
  split.
  { intros a p Ht. destruct (pkg_cert p) as [ d | ]; [ | reflexivity ].
    exact (check_cert_refuses_an_unrecognised_tier m p.(pkg_id) p.(pkg_tier)
             (with_steps (rd d) (map_over reroute (rd d).(cert_steps))) Ht). }
  intros a p d Hc Hr. rewrite Hc.
  apply (check_cert_refuses_an_unrecognised_form m p.(pkg_id) p.(pkg_tier)
           (with_steps (rd d) (map_over reroute (rd d).(cert_steps)))).
  simpl. rewrite (rerouting_preserves_every_recognition (rd d).(cert_steps)).
  exact Hr.
Qed.

Theorem the_move_blind_check_still_refuses_an_unnamed_facet :
  forall (m : Machine) (D : Type) (rd : Reading D) (a : Ambient) (p : Package D)
         (d : D) (t : Tier) (f : Facet),
    p.(pkg_cert) = Some d ->
    tier_of_code p.(pkg_tier) = Some t ->
    mem_facet f (m.(required) t) = true ->
    any_of (names_facet f) (rd d).(cert_steps) = false ->
    accepts (move_blind_check m D rd a p) = false.
Proof.
  intros m D rd a p d t f Hc Ht Hm Hn. unfold move_blind_check. rewrite Hc.
  apply (check_cert_refuses_an_undischarged_facet m p.(pkg_id) p.(pkg_tier) t
           (with_steps (rd d) (map_over reroute (rd d).(cert_steps))) Ht).
  apply (an_open_facet_breaks_the_coverage m t
           (with_steps (rd d) (map_over reroute (rd d).(cert_steps))) f Hm).
  unfold discharged. simpl.
  exact (an_unnamed_facet_is_undischarged_after_rerouting (rd d).(cert_steps) f Hn).
Qed.

(* At the demo it differs from the specification at exactly the misrouted
   witness, which is what makes the move table's content visible: every other
   package the two decide alike. *)
Example the_move_blind_check_differs_at_the_misrouted_witness :
  demo_check w_misrouted = Refused CitationMissing (code_of_facet CodegenNone)
  /\ move_blind_check demo Cert full_reading amb_first w_misrouted = Accepted
  /\ map_over (fun p => move_blind_check demo Cert full_reading amb_first p)
              golden_roster
     = map_over demo_check golden_roster
  /\ map_over (fun p => move_blind_check demo Cert full_reading amb_first p)
              refusal_witnesses
     = map_over demo_check refusal_witnesses :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   A checker that walks a tier's required set in the order the machine
   declares it rather than in TAL-074's phase order.

   It satisfies every one of the eight clauses and fails closed, so nothing
   about admission separates it from the specification. What separates it is
   which refusal it names, and TAL-074's *rejects at the first failure* is
   what it breaks.
   ------------------------------------------------------------------------- *)

Definition check_in_declared_order (m : Machine) (id tc : nat) (c : Cert) : Verdict :=
  if negb (versions_eqb c.(cert_versions) m.(admitted_versions))
  then Refused VersionMismatch id
  else if negb (Nat.eqb c.(cert_binds) id)
  then Refused BindingMismatch id
  else match tier_of_code tc with
       | None => Refused TierUnrecognised id
       | Some t =>
           match first_unrecognised c.(cert_steps) with
           | Some s => Refused FormUnrecognised s.(st_site)
           | None =>
               match first_undischarged c (m.(required) t) with
               | Some f => Refused (rule_of_move (move_of f)) (code_of_facet f)
               | None => Accepted
               end
           end
       end.

Definition declared_order_check (m : Machine) (D : Type) (rd : Reading D)
    : Checker D :=
  fun _ p =>
    match p.(pkg_cert) with
    | None => Refused DerivationAbsent p.(pkg_id)
    | Some d => check_in_declared_order m p.(pkg_id) p.(pkg_tier) (rd d)
    end.

Theorem the_declared_order_check_fails_closed :
  forall (m : Machine) (D : Type) (rd : Reading D),
    FailsClosed m D rd (declared_order_check m D rd).
Proof.
  intros m D rd a p H. unfold declared_order_check in H.
  remember (pkg_cert p) as cp.
  destruct cp as [ d | ]; [ | discriminate H ].
  unfold check_in_declared_order in H.
  destruct (versions_eqb (cert_versions (rd d)) (admitted_versions m)) eqn:Ev;
    [ | simpl in H; discriminate H ].
  simpl in H.
  destruct (Nat.eqb (cert_binds (rd d)) (pkg_id p)) eqn:Eb;
    [ | simpl in H; discriminate H ].
  simpl in H.
  destruct (tier_of_code (pkg_tier p)) as [ t | ] eqn:Et; [ | discriminate H ].
  destruct (first_unrecognised (cert_steps (rd d))) as [ s | ] eqn:Eu;
    [ discriminate H | ].
  destruct (first_undischarged (rd d) (required m t)) as [ f | ] eqn:Ed;
    [ discriminate H | ].
  exists d. exists t. split; [ symmetry; exact Heqcp | ].
  split; [ exact (versions_eqb_true _ _ Ev) | ].
  split; [ exact (nat_eqb_true _ _ Eb) | ].
  split; [ exact Et | ].
  split; [ exact (first_unrecognised_none _ Eu) | ].
  unfold covers. exact (first_undischarged_none _ _ Ed).
Qed.

Theorem the_declared_order_check_is_complete :
  forall (m : Machine) (D : Type) (rd : Reading D),
    CompleteFor D (WellTyped m D rd) (declared_order_check m D rd).
Proof.
  intros m D rd a p H.
  destruct H as [ d H1 ]. destruct H1 as [ t H2 ].
  destruct H2 as [ Hc H3 ]. destruct H3 as [ Hv H4 ].
  destruct H4 as [ Hb H5 ]. destruct H5 as [ Ht H6 ]. destruct H6 as [ Hr Hcov ].
  unfold declared_order_check. rewrite Hc. unfold check_in_declared_order.
  rewrite Hv. rewrite Hb. rewrite (versions_eqb_refl (admitted_versions m)).
  rewrite (nat_eqb_refl (pkg_id p)). simpl. rewrite Ht.
  rewrite (all_recognised_first_none (cert_steps (rd d)) Hr).
  unfold covers in Hcov.
  rewrite (all_discharged_first_none (rd d) (required m t) Hcov). reflexivity.
Qed.

(* A Tier-0 component with a thin derivation leaves every facet open, two of
   them move-III ones. TAL-074 puts the deletions before the citations, so the
   specification names a deletion; the declared-order walk names the citation
   its machine happens to have declared first. *)
Definition p_thin_tier_zero : Package Cert :=
  package_at 0 (code_of_tier TierZero) 3 false (Some (thin_cert 0)).

Theorem the_declared_order_check_rejects_at_a_later_phase :
  ~ RejectsAtTheEarliestOpenPhase demo Cert full_reading
      (declared_order_check demo Cert full_reading).
Proof.
  intros H.
  specialize (H amb_first p_thin_tier_zero (thin_cert 0) TierZero AmbientAbsent
                eq_refl eq_refl eq_refl eq_refl).
  discriminate H.
Qed.

Example the_two_walks_name_different_phases :
  demo_check p_thin_tier_zero
  = Refused DeletionUnconfirmed (code_of_facet AmbientAbsent)
  /\ declared_order_check demo Cert full_reading amb_first p_thin_tier_zero
     = Refused CitationMissing (code_of_facet MemSpatial)
  /\ phase_rank (phase_of_rule DeletionUnconfirmed) = 3
  /\ phase_rank (phase_of_rule CitationMissing) = 4
  /\ map_over (fun p => declared_order_check demo Cert full_reading amb_first p)
              golden_roster
     = map_over demo_check golden_roster :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* -------------------------------------------------------------------------
   Three checkers that hoist one of TAL-074's first three phases above the one
   before it.

   Each accepts exactly where the specification accepts, so none is a fail-open
   construction and none is an incomplete one: what separates each from the
   specification is which refusal it names and nothing else. That is what makes
   the early order a decision this file takes rather than a sentence it states,
   and it is where the one ordering judgment TAL-074 leaves open, phase 0's own
   two halves, is put where a construction can break it.
   ------------------------------------------------------------------------- *)

(* Phase 0's binding recomputation hoisted above its version comparison. *)
Definition binding_first_check (m : Machine) (D : Type) (rd : Reading D)
    : Checker D :=
  fun _ p =>
    match p.(pkg_cert) with
    | None => Refused DerivationAbsent p.(pkg_id)
    | Some d =>
        if negb (Nat.eqb (rd d).(cert_binds) p.(pkg_id))
        then Refused BindingMismatch p.(pkg_id)
        else check_cert m p.(pkg_id) p.(pkg_tier) (rd d)
    end.

(* Phase 1's tier lookup hoisted above phase 0's binding recomputation. *)
Definition tier_before_binding_check (m : Machine) (D : Type) (rd : Reading D)
    : Checker D :=
  fun _ p =>
    match p.(pkg_cert) with
    | None => Refused DerivationAbsent p.(pkg_id)
    | Some d =>
        if negb (versions_eqb (rd d).(cert_versions) m.(admitted_versions))
        then Refused VersionMismatch p.(pkg_id)
        else match tier_of_code p.(pkg_tier) with
             | None => Refused TierUnrecognised p.(pkg_id)
             | Some _ => check_cert m p.(pkg_id) p.(pkg_tier) (rd d)
             end
    end.

(* Phase 2's record recognition hoisted above phase 1's tier lookup. *)
Definition form_first_check (m : Machine) (D : Type) (rd : Reading D)
    : Checker D :=
  fun _ p =>
    match p.(pkg_cert) with
    | None => Refused DerivationAbsent p.(pkg_id)
    | Some d =>
        if negb (versions_eqb (rd d).(cert_versions) m.(admitted_versions))
        then Refused VersionMismatch p.(pkg_id)
        else if negb (Nat.eqb (rd d).(cert_binds) p.(pkg_id))
        then Refused BindingMismatch p.(pkg_id)
        else match first_unrecognised (rd d).(cert_steps) with
             | Some s => Refused FormUnrecognised s.(st_site)
             | None => check_cert m p.(pkg_id) p.(pkg_tier) (rd d)
             end
    end.

Theorem the_binding_first_check_accepts_where_the_specification_does :
  forall (m : Machine) (D : Type) (rd : Reading D) (a : Ambient) (p : Package D),
    accepts (binding_first_check m D rd a p) = accepts (spec_check m D rd a p).
Proof.
  intros m D rd a p. unfold binding_first_check. unfold spec_check.
  destruct (pkg_cert p) as [ d | ]; [ | reflexivity ].
  destruct (Nat.eqb (cert_binds (rd d)) (pkg_id p)) eqn:Eb; simpl.
  - reflexivity.
  - symmetry.
    exact (check_cert_refuses_a_wrong_binding m p.(pkg_id) p.(pkg_tier) (rd d) Eb).
Qed.

Theorem the_tier_before_binding_check_accepts_where_the_specification_does :
  forall (m : Machine) (D : Type) (rd : Reading D) (a : Ambient) (p : Package D),
    accepts (tier_before_binding_check m D rd a p)
    = accepts (spec_check m D rd a p).
Proof.
  intros m D rd a p. unfold tier_before_binding_check. unfold spec_check.
  destruct (pkg_cert p) as [ d | ]; [ | reflexivity ].
  destruct (versions_eqb (cert_versions (rd d)) (admitted_versions m)) eqn:Ev;
    simpl.
  - destruct (tier_of_code (pkg_tier p)) as [ t | ] eqn:Et.
    + reflexivity.
    + symmetry.
      exact (check_cert_refuses_an_unrecognised_tier m p.(pkg_id) p.(pkg_tier)
               (rd d) Et).
  - symmetry.
    exact (check_cert_refuses_a_stale_version m p.(pkg_id) p.(pkg_tier) (rd d) Ev).
Qed.

Theorem the_form_first_check_accepts_where_the_specification_does :
  forall (m : Machine) (D : Type) (rd : Reading D) (a : Ambient) (p : Package D),
    accepts (form_first_check m D rd a p) = accepts (spec_check m D rd a p).
Proof.
  intros m D rd a p. unfold form_first_check. unfold spec_check.
  destruct (pkg_cert p) as [ d | ]; [ | reflexivity ].
  destruct (versions_eqb (cert_versions (rd d)) (admitted_versions m)) eqn:Ev;
    simpl.
  - destruct (Nat.eqb (cert_binds (rd d)) (pkg_id p)) eqn:Eb; simpl.
    + destruct (first_unrecognised (cert_steps (rd d))) as [ s | ] eqn:Eu.
      * symmetry.
        exact (check_cert_refuses_an_unrecognised_form m p.(pkg_id) p.(pkg_tier)
                 (rd d) (first_unrecognised_some _ _ Eu)).
      * reflexivity.
    + symmetry.
      exact (check_cert_refuses_a_wrong_binding m p.(pkg_id) p.(pkg_tier) (rd d) Eb).
  - symmetry.
    exact (check_cert_refuses_a_stale_version m p.(pkg_id) p.(pkg_tier) (rd d) Ev).
Qed.

(* So none of the three is a fail-open or an incomplete construction: each
   satisfies the fail-closed obligation and the completeness one, and what
   separates it from the specification is the refusal it names. *)
Theorem the_reordered_checkers_fail_closed_and_are_complete :
  forall (m : Machine) (D : Type) (rd : Reading D),
    FailsClosed m D rd (binding_first_check m D rd)
    /\ FailsClosed m D rd (tier_before_binding_check m D rd)
    /\ FailsClosed m D rd (form_first_check m D rd)
    /\ CompleteFor D (WellTyped m D rd) (binding_first_check m D rd)
    /\ CompleteFor D (WellTyped m D rd) (tier_before_binding_check m D rd)
    /\ CompleteFor D (WellTyped m D rd) (form_first_check m D rd).
Proof.
  intros m D rd. split.
  { intros a p H.
    rewrite (the_binding_first_check_accepts_where_the_specification_does
               m D rd a p) in H.
    exact (the_specification_fails_closed m D rd a p H). }
  split.
  { intros a p H.
    rewrite (the_tier_before_binding_check_accepts_where_the_specification_does
               m D rd a p) in H.
    exact (the_specification_fails_closed m D rd a p H). }
  split.
  { intros a p H.
    rewrite (the_form_first_check_accepts_where_the_specification_does
               m D rd a p) in H.
    exact (the_specification_fails_closed m D rd a p H). }
  split.
  { intros a p H.
    rewrite (the_binding_first_check_accepts_where_the_specification_does
               m D rd a p).
    exact (the_specification_is_complete_for_the_typing_relation m D rd a p H). }
  split.
  { intros a p H.
    rewrite (the_tier_before_binding_check_accepts_where_the_specification_does
               m D rd a p).
    exact (the_specification_is_complete_for_the_typing_relation m D rd a p H). }
  intros a p H.
  rewrite (the_form_first_check_accepts_where_the_specification_does m D rd a p).
  exact (the_specification_is_complete_for_the_typing_relation m D rd a p H).
Qed.

Theorem the_binding_first_check_names_the_binding_where_the_version_is_stale :
  ~ RefusesUnderTheStaleVersionFirst demo Cert full_reading
      (binding_first_check demo Cert full_reading).
Proof.
  intros H.
  specialize (H amb_first p_stale_and_misbound
                (with_sail_model (S demo_versions.(ver_sail_model))
                   (covering_cert TierTwo 8)) eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_binding_first_check_keeps_the_other_two :
  forall (m : Machine) (D : Type) (rd : Reading D),
    RefusesUnderTheWrongBindingBeforeTheTier m D rd (binding_first_check m D rd)
    /\ RefusesUnderTheUnrecognisedTierBeforeTheForm m D rd
         (binding_first_check m D rd).
Proof.
  intros m D rd. unfold binding_first_check. split.
  { intros a p d Hc Hv Hb. rewrite Hc. rewrite Hb. reflexivity. }
  intros a p d Hc Hv Hb Ht. rewrite Hc. rewrite Hb. simpl. unfold check_cert.
  rewrite Hv. simpl. rewrite Hb. simpl. rewrite Ht. reflexivity.
Qed.

Theorem the_tier_before_binding_check_names_the_tier_where_the_binding_is_wrong :
  ~ RefusesUnderTheWrongBindingBeforeTheTier demo Cert full_reading
      (tier_before_binding_check demo Cert full_reading).
Proof.
  intros H.
  specialize (H amb_first p_misbound_and_unknown_tier (covering_cert TierTwo 8)
                eq_refl eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_tier_before_binding_check_keeps_the_other_two :
  forall (m : Machine) (D : Type) (rd : Reading D),
    RefusesUnderTheStaleVersionFirst m D rd (tier_before_binding_check m D rd)
    /\ RefusesUnderTheUnrecognisedTierBeforeTheForm m D rd
         (tier_before_binding_check m D rd).
Proof.
  intros m D rd. unfold tier_before_binding_check. split.
  { intros a p d Hc Hv. rewrite Hc. rewrite Hv. reflexivity. }
  intros a p d Hc Hv Hb Ht. rewrite Hc. rewrite Hv. simpl. rewrite Ht.
  reflexivity.
Qed.

Theorem the_form_first_check_names_the_form_where_the_tier_is_unrecognised :
  ~ RefusesUnderTheUnrecognisedTierBeforeTheForm demo Cert full_reading
      (form_first_check demo Cert full_reading).
Proof.
  intros H.
  specialize (H amb_first p_unknown_tier_and_unknown_form
                (corrupt_form_at 0 (covering_cert TierTwo 6))
                eq_refl eq_refl eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_form_first_check_keeps_the_other_two :
  forall (m : Machine) (D : Type) (rd : Reading D),
    RefusesUnderTheStaleVersionFirst m D rd (form_first_check m D rd)
    /\ RefusesUnderTheWrongBindingBeforeTheTier m D rd (form_first_check m D rd).
Proof.
  intros m D rd. unfold form_first_check. split.
  { intros a p d Hc Hv. rewrite Hc. rewrite Hv. reflexivity. }
  intros a p d Hc Hv Hb. rewrite Hc. rewrite Hv. simpl. rewrite Hb. reflexivity.
Qed.

(* The three witnesses, and what each of the four checkers names on them: the
   algorithm's own order read off the verdicts rather than off the order the
   rule enumeration happens to be written in. *)
Example the_early_phases_are_tried_in_order :
  demo_check p_stale_and_misbound = Refused VersionMismatch 6
  /\ demo_check p_misbound_and_unknown_tier = Refused BindingMismatch 6
  /\ demo_check p_unknown_tier_and_unknown_form = Refused TierUnrecognised 6
  /\ binding_first_check demo Cert full_reading amb_first p_stale_and_misbound
     = Refused BindingMismatch 6
  /\ tier_before_binding_check demo Cert full_reading amb_first
       p_misbound_and_unknown_tier = Refused TierUnrecognised 6
  /\ form_first_check demo Cert full_reading amb_first
       p_unknown_tier_and_unknown_form = Refused FormUnrecognised 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* And each witness genuinely fails both of the phases its pair is about, so
   the conversion above is an ordering and not a coincidence of one fault. *)
Example each_early_witness_fails_two_phases :
  versions_eqb (with_sail_model (S demo_versions.(ver_sail_model))
                  (covering_cert TierTwo 8)).(cert_versions) demo_versions = false
  /\ Nat.eqb (with_sail_model (S demo_versions.(ver_sail_model))
                (covering_cert TierTwo 8)).(cert_binds)
             p_stale_and_misbound.(pkg_id) = false
  /\ Nat.eqb (covering_cert TierTwo 8).(cert_binds)
             p_misbound_and_unknown_tier.(pkg_id) = false
  /\ tier_of_code p_misbound_and_unknown_tier.(pkg_tier) = None
  /\ tier_of_code p_unknown_tier_and_unknown_form.(pkg_tier) = None
  /\ all_of step_recognised
       (corrupt_form_at 0 (covering_cert TierTwo 6)).(cert_steps) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* On the golden roster all four agree, so what separates them is the order and
   not a different table. *)
Example the_reordered_checkers_agree_on_the_golden_roster :
  map_over (fun p => binding_first_check demo Cert full_reading amb_first p)
           golden_roster = map_over demo_check golden_roster
  /\ map_over (fun p => tier_before_binding_check demo Cert full_reading amb_first p)
              golden_roster = map_over demo_check golden_roster
  /\ map_over (fun p => form_first_check demo Cert full_reading amb_first p)
              golden_roster = map_over demo_check golden_roster :=
  conj eq_refl (conj eq_refl eq_refl).

(* -------------------------------------------------------------------------
   A checker that compares one of the four versions.

   R-11-005 names the spec-set and the Sail model and R-05-135b names the
   language specification and its profile, so a derivation agreeing on the
   spec-set alone is not a verdict for this generation. The construction that
   compares the spec-set and lets the other three through is the one a single
   version field would have made inexpressible.
   ------------------------------------------------------------------------- *)

Definition with_versions (v : Versions) (c : Cert) : Cert :=
  {| cert_versions := v; cert_binds := c.(cert_binds); cert_steps := c.(cert_steps) |}.

Definition only_the_spec_set (v w : Versions) : Versions :=
  {| ver_spec_set := v.(ver_spec_set);
     ver_sail_model := w.(ver_sail_model);
     ver_language := w.(ver_language);
     ver_profile := w.(ver_profile) |}.

Definition partial_version_check (m : Machine) (D : Type) (rd : Reading D)
    : Checker D :=
  fun _ p =>
    match p.(pkg_cert) with
    | None => Refused DerivationAbsent p.(pkg_id)
    | Some d =>
        check_cert m p.(pkg_id) p.(pkg_tier)
          (with_versions (only_the_spec_set (rd d).(cert_versions)
                                            m.(admitted_versions)) (rd d))
    end.

Theorem the_partial_version_check_admits_a_stale_model :
  ~ RefusesAStaleVersion demo Cert full_reading
      (partial_version_check demo Cert full_reading).
Proof.
  intros H.
  specialize (H amb_first w_stale_version
                (with_sail_model (S demo_versions.(ver_sail_model))
                   (covering_cert TierTwo 6)) eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_partial_version_check_keeps_the_other_seven :
  forall (m : Machine) (D : Type) (rd : Reading D),
    RefusesAnAbsentDerivation D (partial_version_check m D rd)
    /\ RefusesAWrongBinding D rd (partial_version_check m D rd)
    /\ RefusesAnUnrecognisedTier D (partial_version_check m D rd)
    /\ RefusesAnUnrecognisedForm D rd (partial_version_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd ConfirmADeletion
         (partial_version_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd CiteAnInvariant
         (partial_version_check m D rd)
    /\ RefusesAnUndischargedFacetOf m D rd EvaluateAnAttribute
         (partial_version_check m D rd).
Proof.
  intros m D rd. unfold partial_version_check. split.
  { intros a p Hc. rewrite Hc. reflexivity. }
  split.
  { intros a p d Hc Hb. rewrite Hc.
    exact (check_cert_refuses_a_wrong_binding m p.(pkg_id) p.(pkg_tier)
             (with_versions (only_the_spec_set (rd d).(cert_versions)
                               m.(admitted_versions)) (rd d)) Hb). }
  split.
  { intros a p Ht. destruct (pkg_cert p) as [ d | ]; [ | reflexivity ].
    exact (check_cert_refuses_an_unrecognised_tier m p.(pkg_id) p.(pkg_tier)
             (with_versions (only_the_spec_set (rd d).(cert_versions)
                               m.(admitted_versions)) (rd d)) Ht). }
  split.
  { intros a p d Hc Hr. rewrite Hc.
    exact (check_cert_refuses_an_unrecognised_form m p.(pkg_id) p.(pkg_tier)
             (with_versions (only_the_spec_set (rd d).(cert_versions)
                               m.(admitted_versions)) (rd d)) Hr). }
  split.
  { intros a p d t f Hc Ht Hm Hk Hd. rewrite Hc.
    exact (check_cert_refuses_an_undischarged_facet m p.(pkg_id) p.(pkg_tier) t
             (with_versions (only_the_spec_set (rd d).(cert_versions)
                               m.(admitted_versions)) (rd d)) Ht
             (an_open_facet_breaks_the_coverage m t
                (with_versions (only_the_spec_set (rd d).(cert_versions)
                                  m.(admitted_versions)) (rd d)) f Hm Hd)). }
  split.
  { intros a p d t f Hc Ht Hm Hk Hd. rewrite Hc.
    exact (check_cert_refuses_an_undischarged_facet m p.(pkg_id) p.(pkg_tier) t
             (with_versions (only_the_spec_set (rd d).(cert_versions)
                               m.(admitted_versions)) (rd d)) Ht
             (an_open_facet_breaks_the_coverage m t
                (with_versions (only_the_spec_set (rd d).(cert_versions)
                                  m.(admitted_versions)) (rd d)) f Hm Hd)). }
  intros a p d t f Hc Ht Hm Hk Hd. rewrite Hc.
  exact (check_cert_refuses_an_undischarged_facet m p.(pkg_id) p.(pkg_tier) t
           (with_versions (only_the_spec_set (rd d).(cert_versions)
                             m.(admitted_versions)) (rd d)) Ht
           (an_open_facet_breaks_the_coverage m t
              (with_versions (only_the_spec_set (rd d).(cert_versions)
                                m.(admitted_versions)) (rd d)) f Hm Hd)).
Qed.

(* And a derivation stale in the profile rather than in the Sail model is
   admitted by it too, so what it loses is three of R-11-005's and R-05-135b's
   four versions and not one of them. *)
Definition w_stale_profile : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false
    (Some (with_profile (S demo_versions.(ver_profile)) (covering_cert TierTwo 6))).

Example the_partial_version_check_admits_two_stale_derivations :
  demo_check w_stale_version = Refused VersionMismatch 6
  /\ demo_check w_stale_profile = Refused VersionMismatch 6
  /\ partial_version_check demo Cert full_reading amb_first w_stale_version = Accepted
  /\ partial_version_check demo Cert full_reading amb_first w_stale_profile = Accepted
  /\ map_over (fun p => partial_version_check demo Cert full_reading amb_first p)
              golden_roster
     = map_over demo_check golden_roster :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* =========================================================================
   Refutation witnesses over the composer (R-13-001c, R-13-010b, R-17-033).
   ========================================================================= *)

Lemma filter_of_all :
  forall (A : Type) (q : A -> bool) (l : list A),
    all_of q l = true -> filter_of q l = l.
Proof.
  intros A q l. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    simpl. rewrite Hx. rewrite (IH Hr). reflexivity.
Qed.

(* The composer that ships the sub-roster it could admit and drops the rest.
   It is the shape a per-package verdict invites, filtering being what a
   decidable predicate over a list is for, and it is the one R-11-005
   excludes: the transactor commits a generation only after every new binary's
   proof validates, R-13-001a makes an install a generation rather than an
   amendment to one, and R-13-001c has a composer that gets its inputs wrong
   fail admission rather than ship. One refused package costs the generation,
   not itself. *)
Definition filtering_composer (m : Machine) (D : Type) (rd : Reading D)
    : Composer D :=
  fun a r => Some {| gen_image := filter_of (fun p => accepts (spec_check m D rd a p)) r;
                     gen_synthesized := nil |}.

(* A roster with one component whose derivation the composer cannot admit. *)
Definition faulted_roster : Roster Cert := insert_at 3 w_absent golden_roster.

Theorem the_filtering_composer_ships_a_partial_generation :
  ~ IsAllOrNothing demo Cert full_reading (filtering_composer demo Cert full_reading).
Proof.
  intros H. specialize (H amb_first faulted_roster eq_refl). discriminate H.
Qed.

(* And it keeps the other four, so what refuses it is the partial emission and
   not a package it admitted or a stranger it added. *)
Theorem the_filtering_composer_keeps_the_other_four :
  forall (m : Machine) (D : Type) (rd : Reading D),
    CommitsOnlyTheAccepted m D rd (filtering_composer m D rd)
    /\ EmitsNoUncoveredStranger D (filtering_composer m D rd)
    /\ CoversWhatItSynthesized D (filtering_composer m D rd)
    /\ CommitsEveryAccepted m D rd (filtering_composer m D rd).
Proof.
  intros m D rd. unfold filtering_composer. split.
  { intros a r g H. injection H as H2. rewrite <- H2. simpl.
    exact (all_of_filter (Package D) (fun p => accepts (spec_check m D rd a p)) r). }
  split.
  { intros a r g H. injection H as H2. rewrite <- H2. simpl.
    apply (all_of_mono (Package D)
             (fun p => mem_nat p.(pkg_id) (image_ids D r))
             (fun p => orb (mem_nat p.(pkg_id) (image_ids D r))
                           (mem_nat p.(pkg_id) nil))).
    - intros y Hy. rewrite Hy. reflexivity.
    - apply (filter_of_within (Package D)
               (fun p => accepts (spec_check m D rd a p))
               (fun p => mem_nat p.(pkg_id) (image_ids D r)) r).
      exact (every_member_names_itself D r). }
  split.
  { intros a r g H. injection H as H2. rewrite <- H2. reflexivity. }
  intros a r H. unfold admissible in H.
  exists {| gen_image := filter_of (fun p => accepts (spec_check m D rd a p)) r;
            gen_synthesized := nil |}.
  split; [ reflexivity | ]. simpl.
  rewrite (filter_of_all (Package D) (fun p => accepts (spec_check m D rd a p)) r H).
  exact (every_member_names_itself D r).
Qed.

(* At the demo the difference is one conversion: the specification refuses the
   whole generation and the filtering composer ships seven of eight. *)
Example one_refused_component_costs_the_generation :
  admissible demo Cert full_reading amb_first faulted_roster = false
  /\ demo_compose faulted_roster = None
  /\ count_of faulted_roster = 8
  /\ map_option (fun g => count_of g.(gen_image))
                (filtering_composer demo Cert full_reading amb_first faulted_roster)
     = Some 7 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* And no position of the insertion is where a refused component could hide. *)
Example no_position_of_a_refused_component_composes :
  all_of (fun n => negb (is_some (demo_compose (insert_at n w_absent golden_roster))))
         (upto (S (count_of golden_roster))) = true := eq_refl.

(* -------------------------------------------------------------------------
   The composer that adds a package of its own beside the roster's.

   R-13-010b requires exactly this of the duplication pass: one shared service
   compartment in place of a library statically linked into each consumer,
   which no roster names. R-13-001c requires the pass to emit the derivation
   covering the new bytes. So the same construction, instantiated at a
   compartment carrying its derivation and at one carrying none, satisfies the
   obligations and breaks them; and a composer adding a package it declares
   nothing about is the stranger the roster clause excludes.
   ------------------------------------------------------------------------- *)

Definition merging_composer (m : Machine) (D : Type) (rd : Reading D)
    (x : Package D) : Composer D :=
  fun a r => match spec_compose m D rd a r with
             | Some g => Some {| gen_image := cons x g.(gen_image);
                                 gen_synthesized := cons x.(pkg_id) nil |}
             | None => None
             end.

Definition substituting_composer (m : Machine) (D : Type) (rd : Reading D)
    (x : Package D) : Composer D :=
  fun a r => match spec_compose m D rd a r with
             | Some g => Some {| gen_image := cons x g.(gen_image);
                                 gen_synthesized := nil |}
             | None => None
             end.

(* The pass that does what R-13-010b requires satisfies all five, and the
   package it adds is one the roster does not name, which is the point: the
   obligation is coverage and not absence. *)
Theorem the_merging_composer_satisfies_every_clause :
  forall (m : Machine) (D : Type) (rd : Reading D) (x : Package D),
    (forall a : Ambient, accepts (spec_check m D rd a x) = true) ->
    IsAllOrNothing m D rd (merging_composer m D rd x)
    /\ CommitsOnlyTheAccepted m D rd (merging_composer m D rd x)
    /\ EmitsNoUncoveredStranger D (merging_composer m D rd x)
    /\ CoversWhatItSynthesized D (merging_composer m D rd x)
    /\ CommitsEveryAccepted m D rd (merging_composer m D rd x).
Proof.
  intros m D rd x Hx. unfold merging_composer. unfold spec_compose. split.
  { intros a r H. rewrite H. reflexivity. }
  split.
  { intros a r g H. destruct (admissible m D rd a r) eqn:E; [ | discriminate H ].
    injection H as H2. rewrite <- H2. simpl. apply andb_join; [ exact (Hx a) | ].
    exact E. }
  split.
  { intros a r g H. destruct (admissible m D rd a r) eqn:E; [ | discriminate H ].
    injection H as H2. rewrite <- H2. simpl. apply andb_join.
    - rewrite (mem_nat_here x.(pkg_id) nil).
      destruct (mem_nat x.(pkg_id) (image_ids D r)); reflexivity.
    - apply (all_of_mono (Package D)
               (fun p => mem_nat p.(pkg_id) (image_ids D r))
               (fun p => orb (mem_nat p.(pkg_id) (image_ids D r))
                             (mem_nat p.(pkg_id) (cons x.(pkg_id) nil))));
        [ | exact (every_member_names_itself D r) ].
      intros y Hy. rewrite Hy. reflexivity. }
  split.
  { intros a r g H. destruct (admissible m D rd a r) eqn:E; [ | discriminate H ].
    injection H as H2. rewrite <- H2. simpl. unfold mem_nat. unfold image_ids.
    simpl. rewrite (nat_eqb_refl x.(pkg_id)). reflexivity. }
  intros a r H. rewrite H.
  exists {| gen_image := cons x r; gen_synthesized := cons x.(pkg_id) nil |}.
  split; [ reflexivity | ]. simpl.
  apply (all_of_mono (Package D)
           (fun p => mem_nat p.(pkg_id) (image_ids D r))
           (fun p => mem_nat p.(pkg_id) (cons x.(pkg_id) (image_ids D r))));
    [ | exact (every_member_names_itself D r) ].
  intros y Hy. exact (mem_nat_cons y.(pkg_id) x.(pkg_id) (image_ids D r) Hy).
Qed.

(* The compartment R-13-010b's pass emits is admissible in every ambient, and
   the roster does not name it: the two facts the theorem above is
   instantiated with, discharged here rather than left standing. *)
Theorem the_shared_service_is_admissible_in_every_ambient :
  forall a : Ambient, accepts (spec_check demo Cert full_reading a shared_service) = true.
Proof.
  intros a.
  rewrite (the_specification_is_a_function_of_the_package demo Cert full_reading
             a amb_first shared_service).
  reflexivity.
Qed.

Theorem the_stock_package_is_admissible_in_every_ambient :
  forall a : Ambient, accepts (spec_check demo Cert full_reading a stock_package) = true.
Proof.
  intros a.
  rewrite (the_specification_is_a_function_of_the_package demo Cert full_reading
             a amb_first stock_package).
  reflexivity.
Qed.

Theorem the_merging_composer_at_the_shared_service_satisfies_every_clause :
  IsAllOrNothing demo Cert full_reading
    (merging_composer demo Cert full_reading shared_service)
  /\ CommitsOnlyTheAccepted demo Cert full_reading
       (merging_composer demo Cert full_reading shared_service)
  /\ EmitsNoUncoveredStranger Cert
       (merging_composer demo Cert full_reading shared_service)
  /\ CoversWhatItSynthesized Cert
       (merging_composer demo Cert full_reading shared_service)
  /\ CommitsEveryAccepted demo Cert full_reading
       (merging_composer demo Cert full_reading shared_service).
Proof.
  exact (the_merging_composer_satisfies_every_clause demo Cert full_reading
           shared_service the_shared_service_is_admissible_in_every_ambient).
Qed.

Example the_merged_compartment_is_a_package_the_roster_does_not_name :
  mem_nat shared_service.(pkg_id) (image_ids Cert golden_roster) = false
  /\ demo_check shared_service = Accepted
  /\ map_option (fun g => image_ids Cert g.(gen_image))
       (merging_composer demo Cert full_reading shared_service amb_first golden_roster)
     = Some (cons 7 (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 (cons 6 nil))))))))
  /\ map_option (fun g => g.(gen_synthesized))
       (merging_composer demo Cert full_reading shared_service amb_first golden_roster)
     = Some (cons 7 nil) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The same pass with the derivation R-13-001c requires left unemitted: the
   compartment is declared and is in the image, and nothing covers it. *)
Theorem the_stripping_merge_commits_an_unvalidated_binary :
  ~ CommitsOnlyTheAccepted demo Cert full_reading
      (merging_composer demo Cert full_reading shared_service_uncovered).
Proof.
  intros H. specialize (H amb_first golden_roster). simpl in H.
  discriminate (H _ eq_refl).
Qed.

(* And a package added with no declaration at all is the stranger the roster
   clause excludes, whether or not it is admissible on its own terms. *)
Theorem the_substituting_composer_emits_an_uncovered_stranger :
  ~ EmitsNoUncoveredStranger Cert
      (substituting_composer demo Cert full_reading stock_package).
Proof.
  intros H. specialize (H amb_first golden_roster). simpl in H.
  discriminate (H _ eq_refl).
Qed.

Theorem the_substituting_composer_keeps_the_other_four :
  forall (m : Machine) (D : Type) (rd : Reading D) (x : Package D),
    (forall a : Ambient, accepts (spec_check m D rd a x) = true) ->
    IsAllOrNothing m D rd (substituting_composer m D rd x)
    /\ CommitsOnlyTheAccepted m D rd (substituting_composer m D rd x)
    /\ CoversWhatItSynthesized D (substituting_composer m D rd x)
    /\ CommitsEveryAccepted m D rd (substituting_composer m D rd x).
Proof.
  intros m D rd x Hx. unfold substituting_composer. unfold spec_compose. split.
  { intros a r H. rewrite H. reflexivity. }
  split.
  { intros a r g H. destruct (admissible m D rd a r) eqn:E; [ | discriminate H ].
    injection H as H2. rewrite <- H2. simpl. apply andb_join; [ exact (Hx a) | ].
    exact E. }
  split.
  { intros a r g H. destruct (admissible m D rd a r) eqn:E; [ | discriminate H ].
    injection H as H2. rewrite <- H2. reflexivity. }
  intros a r H. rewrite H.
  exists {| gen_image := cons x r; gen_synthesized := nil |}.
  split; [ reflexivity | ]. simpl.
  apply (all_of_mono (Package D)
           (fun p => mem_nat p.(pkg_id) (image_ids D r))
           (fun p => mem_nat p.(pkg_id) (cons x.(pkg_id) (image_ids D r))));
    [ | exact (every_member_names_itself D r) ].
  intros y Hy. exact (mem_nat_cons y.(pkg_id) x.(pkg_id) (image_ids D r) Hy).
Qed.

Theorem the_substituting_composer_at_the_stock_package_keeps_the_other_four :
  IsAllOrNothing demo Cert full_reading
    (substituting_composer demo Cert full_reading stock_package)
  /\ CommitsOnlyTheAccepted demo Cert full_reading
       (substituting_composer demo Cert full_reading stock_package)
  /\ CoversWhatItSynthesized Cert
       (substituting_composer demo Cert full_reading stock_package)
  /\ CommitsEveryAccepted demo Cert full_reading
       (substituting_composer demo Cert full_reading stock_package).
Proof.
  exact (the_substituting_composer_keeps_the_other_four demo Cert full_reading
           stock_package the_stock_package_is_admissible_in_every_ambient).
Qed.

(* -------------------------------------------------------------------------
   Two more composers, each breaking one remaining clause.
   ------------------------------------------------------------------------- *)

(* A pass that books a merge it did not ship: it declares a compartment
   synthesized and carries nothing for it, so the derivation R-13-001c
   requires covers nothing in the image. *)
Definition phantom_merge_composer (m : Machine) (D : Type) (rd : Reading D)
    (i : nat) : Composer D :=
  fun a r => match spec_compose m D rd a r with
             | Some g => Some {| gen_image := g.(gen_image);
                                 gen_synthesized := cons i nil |}
             | None => None
             end.

Theorem the_phantom_merge_covers_nothing_it_declared :
  ~ CoversWhatItSynthesized Cert
      (phantom_merge_composer demo Cert full_reading phantom_id).
Proof.
  intros H. specialize (H amb_first golden_roster). simpl in H.
  discriminate (H _ eq_refl).
Qed.

Theorem the_phantom_merge_keeps_the_other_four :
  forall (m : Machine) (D : Type) (rd : Reading D) (i : nat),
    IsAllOrNothing m D rd (phantom_merge_composer m D rd i)
    /\ CommitsOnlyTheAccepted m D rd (phantom_merge_composer m D rd i)
    /\ EmitsNoUncoveredStranger D (phantom_merge_composer m D rd i)
    /\ CommitsEveryAccepted m D rd (phantom_merge_composer m D rd i).
Proof.
  intros m D rd i. unfold phantom_merge_composer. unfold spec_compose. split.
  { intros a r H. rewrite H. reflexivity. }
  split.
  { intros a r g H. destruct (admissible m D rd a r) eqn:E; [ | discriminate H ].
    injection H as H2. rewrite <- H2. simpl. exact E. }
  split.
  { intros a r g H. destruct (admissible m D rd a r) eqn:E; [ | discriminate H ].
    injection H as H2. rewrite <- H2. simpl.
    apply (all_of_mono (Package D)
             (fun p => mem_nat p.(pkg_id) (image_ids D r))
             (fun p => orb (mem_nat p.(pkg_id) (image_ids D r))
                           (mem_nat p.(pkg_id) (cons i nil))));
      [ | exact (every_member_names_itself D r) ].
    intros y Hy. rewrite Hy. reflexivity. }
  intros a r H. rewrite H.
  exists {| gen_image := r; gen_synthesized := cons i nil |}.
  split; [ reflexivity | ]. simpl. exact (every_member_names_itself D r).
Qed.

(* And a composer that admits the roster and ships nothing: R-17-033 books it
   as a delivery failure rather than a safety one, and it is what keeps the
   four refusal clauses from being proved by a composer with nothing to
   refuse. *)
Definition starving_composer (m : Machine) (D : Type) (rd : Reading D) : Composer D :=
  fun a r => if admissible m D rd a r
             then Some {| gen_image := nil; gen_synthesized := nil |}
             else None.

Theorem the_starving_composer_drops_the_admissible :
  ~ CommitsEveryAccepted demo Cert full_reading
      (starving_composer demo Cert full_reading).
Proof.
  intros H. destruct (H amb_first golden_roster eq_refl) as [ g Hg ].
  destruct Hg as [ He Hin ]. unfold starving_composer in He.
  simpl in He. injection He as He2. rewrite <- He2 in Hin. simpl in Hin.
  discriminate Hin.
Qed.

Theorem the_starving_composer_keeps_the_other_four :
  forall (m : Machine) (D : Type) (rd : Reading D),
    IsAllOrNothing m D rd (starving_composer m D rd)
    /\ CommitsOnlyTheAccepted m D rd (starving_composer m D rd)
    /\ EmitsNoUncoveredStranger D (starving_composer m D rd)
    /\ CoversWhatItSynthesized D (starving_composer m D rd).
Proof.
  intros m D rd. unfold starving_composer. split.
  { intros a r H. rewrite H. reflexivity. }
  split.
  { intros a r g H. destruct (admissible m D rd a r); [ | discriminate H ].
    injection H as H2. rewrite <- H2. reflexivity. }
  split.
  { intros a r g H. destruct (admissible m D rd a r); [ | discriminate H ].
    injection H as H2. rewrite <- H2. reflexivity. }
  intros a r g H. destruct (admissible m D rd a r); [ | discriminate H ].
  injection H as H2. rewrite <- H2. reflexivity.
Qed.

(* =========================================================================
   The generated family of waived rules at the demo, and the clause each one
   breaks.

   The twin theorems above say a waiving keeps every other rule and drops its
   own. What makes the eight clauses eight obligations rather than one stated
   eight times is that each waiving breaks its own clause, and that is a
   theorem per clause rather than a sentence: the conversion below supplies
   each witness and the eight theorems after it do the linking.
   ========================================================================= *)

Definition waived (r : RuleId) : Checker Cert :=
  waiving r Cert (spec_check demo Cert full_reading).

(* One conversion over the whole eight-by-eight matrix: each waived checker
   admits exactly what the specification admitted plus exactly what its own
   rule refused, and nothing else. That is the twin read together at every
   pair the witnesses offer. *)
Example each_waived_rule_admits_exactly_what_it_waives :
  all_of (fun r =>
    all_of (fun p => bool_eqb (accepts (waived r amb_first p))
                              (orb (accepts (demo_check p))
                                   (match rule_of (demo_check p) with
                                    | Some r2 => rule_eqb r r2
                                    | None => false
                                    end)))
           refusal_witnesses)
    all_rules = true := eq_refl.

Example every_waived_rule_admits_a_package_the_specification_refused :
  all_of (fun r => any_of (fun p => andb (negb (accepts (demo_check p)))
                                         (accepts (waived r amb_first p)))
                          refusal_witnesses) all_rules = true := eq_refl.

(* And therefore none of the eight is fail-closed, by the generic theorem
   rather than by the conversion: the conversion is what supplies each
   witness. *)
Theorem no_waived_rule_fails_closed :
  ~ FailsClosed demo Cert full_reading (waived DerivationAbsent)
  /\ ~ FailsClosed demo Cert full_reading (waived VersionMismatch)
  /\ ~ FailsClosed demo Cert full_reading (waived BindingMismatch)
  /\ ~ FailsClosed demo Cert full_reading (waived TierUnrecognised)
  /\ ~ FailsClosed demo Cert full_reading (waived FormUnrecognised)
  /\ ~ FailsClosed demo Cert full_reading (waived DeletionUnconfirmed)
  /\ ~ FailsClosed demo Cert full_reading (waived CitationMissing)
  /\ ~ FailsClosed demo Cert full_reading (waived AttributeMissing).
Proof.
  split.
  { exact (a_reachable_waived_rule_breaks_fail_closed demo Cert full_reading
             DerivationAbsent amb_first w_absent eq_refl). }
  split.
  { exact (a_reachable_waived_rule_breaks_fail_closed demo Cert full_reading
             VersionMismatch amb_first w_stale_version eq_refl). }
  split.
  { exact (a_reachable_waived_rule_breaks_fail_closed demo Cert full_reading
             BindingMismatch amb_first w_wrong_binding eq_refl). }
  split.
  { exact (a_reachable_waived_rule_breaks_fail_closed demo Cert full_reading
             TierUnrecognised amb_first w_unknown_tier eq_refl). }
  split.
  { exact (a_reachable_waived_rule_breaks_fail_closed demo Cert full_reading
             FormUnrecognised amb_first w_unknown_form eq_refl). }
  split.
  { exact (a_reachable_waived_rule_breaks_fail_closed demo Cert full_reading
             DeletionUnconfirmed amb_first w_missing_deletion eq_refl). }
  split.
  { exact (a_reachable_waived_rule_breaks_fail_closed demo Cert full_reading
             CitationMissing amb_first w_missing_citation eq_refl). }
  exact (a_reachable_waived_rule_breaks_fail_closed demo Cert full_reading
           AttributeMissing amb_first w_missing_attribute eq_refl).
Qed.

(* Each waiving against its own clause: eight theorems, one per rule, so that
   the decomposition's non-vacuity is machine-checked rather than asserted. *)
Theorem waiving_the_absent_derivation_rule_breaks_its_clause :
  ~ RefusesAnAbsentDerivation Cert (waived DerivationAbsent).
Proof. intros H. specialize (H amb_first w_absent eq_refl). discriminate H. Qed.

Theorem waiving_the_version_rule_breaks_its_clause :
  ~ RefusesAStaleVersion demo Cert full_reading (waived VersionMismatch).
Proof.
  intros H.
  specialize (H amb_first w_stale_version
                (with_sail_model (S demo_versions.(ver_sail_model))
                   (covering_cert TierTwo 6)) eq_refl eq_refl).
  discriminate H.
Qed.

Theorem waiving_the_binding_rule_breaks_its_clause :
  ~ RefusesAWrongBinding Cert full_reading (waived BindingMismatch).
Proof.
  intros H.
  specialize (H amb_first w_wrong_binding (covering_cert TierTwo 8) eq_refl eq_refl).
  discriminate H.
Qed.

Theorem waiving_the_tier_rule_breaks_its_clause :
  ~ RefusesAnUnrecognisedTier Cert (waived TierUnrecognised).
Proof. intros H. specialize (H amb_first w_unknown_tier eq_refl). discriminate H. Qed.

Theorem waiving_the_form_rule_breaks_its_clause :
  ~ RefusesAnUnrecognisedForm Cert full_reading (waived FormUnrecognised).
Proof.
  intros H.
  specialize (H amb_first w_unknown_form
                (corrupt_form_at 0 (covering_cert TierTwo 6)) eq_refl eq_refl).
  discriminate H.
Qed.

Theorem waiving_the_deletion_rule_breaks_its_clause :
  ~ RefusesAnUndischargedFacetOf demo Cert full_reading ConfirmADeletion
      (waived DeletionUnconfirmed).
Proof.
  intros H.
  specialize (H amb_first w_missing_deletion
                (drop_record_at 9 (covering_cert TierZero 0)) TierZero AmbientAbsent
                eq_refl eq_refl eq_refl eq_refl eq_refl).
  discriminate H.
Qed.

Theorem waiving_the_citation_rule_breaks_its_clause :
  ~ RefusesAnUndischargedFacetOf demo Cert full_reading CiteAnInvariant
      (waived CitationMissing).
Proof.
  intros H.
  specialize (H amb_first w_missing_citation
                (drop_record_at 1 (covering_cert TierTwo 6)) TierTwo CodegenNone
                eq_refl eq_refl eq_refl eq_refl eq_refl).
  discriminate H.
Qed.

Theorem waiving_the_attribute_rule_breaks_its_clause :
  ~ RefusesAnUndischargedFacetOf demo Cert full_reading EvaluateAnAttribute
      (waived AttributeMissing).
Proof.
  intros H.
  specialize (H amb_first w_missing_attribute
                (drop_record_at 0 (covering_cert TierTwo 6)) TierTwo AbiConform
                eq_refl eq_refl eq_refl eq_refl eq_refl).
  discriminate H.
Qed.

(* And each keeps every rule but its own, which is the other half of the twin.
   Instantiated at the pair the enumeration above cannot state, a quantifier
   over two distinct rules. *)
Theorem a_waived_checker_still_refuses_every_other_rule :
  forall r r2 : RuleId,
    rule_eqb r r2 = false ->
    RefusesUnder Cert (spec_check demo Cert full_reading) r2 (waived r).
Proof.
  intros r r2 H.
  exact (waiving_one_rule_keeps_every_other Cert (spec_check demo Cert full_reading)
           r r2 H).
Qed.

(* =========================================================================
   The generated families at the demo derivation.

   Reading 7 is what makes two of the families admitted and five refused:
   R-05-029's criterion is a discharge *for each* listed obligation, which
   fixes no order and no multiplicity among the records, and R-05-037,
   R-05-038 and R-05-039 fix which of the three moves each facet takes. The
   generic theorems above are why; the enumerations here are what makes each
   non-vacuous.
   ========================================================================= *)

Definition demo_cert : Cert := covering_cert TierTwo 6.

Definition with_cert (c : Cert) : Package Cert :=
  package_at 6 (code_of_tier TierTwo) 3 false (Some c).

Definition check_of (c : Cert) : Verdict := demo_check (with_cert c).

Example the_demo_derivation_is_the_supervision_tree_s :
  check_of demo_cert = Accepted
  /\ with_cert demo_cert = supervision_tree
  /\ count_of demo_cert.(cert_steps) = 7 :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_generated_family_sizes :
  count_of (step_deletions demo_cert) = 7
  /\ count_of (step_form_corruptions demo_cert) = 7
  /\ count_of (step_move_corruptions demo_cert) = 7
  /\ count_of (step_facet_corruptions demo_cert) = 7
  /\ count_of (step_misroutings demo_cert) = 7
  /\ count_of (step_transpositions demo_cert) = 6
  /\ count_of (step_duplications demo_cert) = 7
  /\ count_of (retaggings demo_cert) = 7 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl)))))).

(* Every deletion is refused, and the refusal names the facet it lost and the
   phase that facet's own move belongs to: the two citations R-05-037 assigns
   draw the citation phase, the five attributes R-05-038 assigns draw the
   attribute phase. *)
Example every_record_deletion_is_refused :
  map_over check_of (step_deletions demo_cert)
  = cons (Refused AttributeMissing (code_of_facet AbiConform))
    (cons (Refused CitationMissing (code_of_facet CodegenNone))
    (cons (Refused AttributeMissing (code_of_facet MemTemporal))
    (cons (Refused AttributeMissing (code_of_facet InitDefinite))
    (cons (Refused AttributeMissing (code_of_facet RaceFreedom))
    (cons (Refused CitationMissing (code_of_facet CfiRuntime))
    (cons (Refused AttributeMissing (code_of_facet CfiCalleeSet)) nil))))))
  := eq_refl.

(* Every corruption of any of a record's three codes is refused at phase 2,
   and the refusal names that record's own site. *)
Example every_code_corruption_is_refused_at_the_structure_phase :
  map_over check_of (step_form_corruptions demo_cert)
  = cons (Refused FormUnrecognised 0) (cons (Refused FormUnrecognised 1)
    (cons (Refused FormUnrecognised 2) (cons (Refused FormUnrecognised 3)
    (cons (Refused FormUnrecognised 4) (cons (Refused FormUnrecognised 5)
    (cons (Refused FormUnrecognised 6) nil))))))
  /\ map_over check_of (step_move_corruptions demo_cert)
     = map_over check_of (step_form_corruptions demo_cert)
  /\ map_over check_of (step_facet_corruptions demo_cert)
     = map_over check_of (step_form_corruptions demo_cert) :=
  conj eq_refl (conj eq_refl eq_refl).

(* And the three corruption families are three defects and not one stated
   three times: recognition runs before coverage, so a corrupted judgment code
   leaves the coverage intact beneath the refusal while a corrupted facet code
   destroys it. That is reading 6 and gap c together. *)
Example the_three_corruptions_differ_beneath_the_refusal :
  all_of (fun c => covers demo TierTwo c) (step_form_corruptions demo_cert) = true
  /\ all_of (fun c => negb (covers demo TierTwo c))
            (step_facet_corruptions demo_cert) = true
  /\ all_of (fun c => negb (covers demo TierTwo c))
            (step_move_corruptions demo_cert) = true := conj eq_refl (conj eq_refl eq_refl).

(* The misrouting family is the move table's own content: rewriting a record's
   move to an attribute costs the derivation exactly the facets R-05-037
   routes through a citation, and costs it nothing anywhere else. Two of the
   seven are refused, and they are the two the move table names. *)
Example the_misrouting_family_refuses_exactly_the_cited_facets :
  map_over check_of (step_misroutings demo_cert)
  = cons Accepted
    (cons (Refused CitationMissing (code_of_facet CodegenNone))
    (cons Accepted (cons Accepted (cons Accepted
    (cons (Refused CitationMissing (code_of_facet CfiRuntime))
    (cons Accepted nil))))))
  /\ count_of (filter_of (fun c => negb (accepts (check_of c)))
                         (step_misroutings demo_cert)) = 2
  /\ count_of (facets_of_move_in CiteAnInvariant (demo.(required) TierTwo)) = 2 :=
  conj eq_refl (conj eq_refl eq_refl).

(* And the two families the specification is invariant under, with the
   judgment-form family beside them: gap c made checkable. *)
Example every_transposition_of_the_records_is_admitted :
  all_of (fun c => accepts (check_of c)) (step_transpositions demo_cert) = true
  := eq_refl.

Example every_duplication_of_a_record_is_admitted :
  all_of (fun c => accepts (check_of c)) (step_duplications demo_cert) = true
  := eq_refl.

Example every_retagging_of_the_judgment_form_is_admitted :
  all_of (fun c => accepts (check_of c)) (retaggings demo_cert) = true := eq_refl.

(* The retagged derivations are genuinely different derivations, so the family
   above is an invariance and not a family of one member repeated. *)
Example the_retaggings_name_seven_different_forms :
  map_over (fun c => map_over (fun s => s.(st_judgment)) c.(cert_steps))
           (retaggings demo_cert)
  = cons (cons 0 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0 nil)))))))
    (cons (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 (cons 1 nil)))))))
    (cons (cons 2 (cons 2 (cons 2 (cons 2 (cons 2 (cons 2 (cons 2 nil)))))))
    (cons (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 nil)))))))
    (cons (cons 4 (cons 4 (cons 4 (cons 4 (cons 4 (cons 4 (cons 4 nil)))))))
    (cons (cons 5 (cons 5 (cons 5 (cons 5 (cons 5 (cons 5 (cons 5 nil)))))))
    (cons (cons 6 (cons 6 (cons 6 (cons 6 (cons 6 (cons 6 (cons 6 nil)))))))
     nil))))))
  := eq_refl.

(* The same content as a quantifier over the index rather than an enumeration,
   so a family is decided for a reason rather than by a computation over the
   seven or six members it happens to have. *)
Theorem no_record_deletion_is_admitted :
  forall n : nat, Nat.ltb n 7 = true ->
    accepts (check_of (with_steps demo_cert (drop_at n demo_cert.(cert_steps))))
    = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | [ | k ] ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_code_corruption_is_admitted :
  forall n : nat, Nat.ltb n 7 = true ->
    accepts (check_of (with_steps demo_cert
               (patch_at unknown_form n demo_cert.(cert_steps)))) = false
    /\ accepts (check_of (with_steps demo_cert
               (patch_at unknown_move n demo_cert.(cert_steps)))) = false
    /\ accepts (check_of (with_steps demo_cert
               (patch_at unknown_facet n demo_cert.(cert_steps)))) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | [ | k ] ] ] ] ] ] ];
    intros H; first [ exact (conj eq_refl (conj eq_refl eq_refl)) | discriminate H ].
Qed.

(* The two invariant families as quantifiers too, and these hold at *every*
   index rather than below a bound, because the generic theorems above are
   what they are instances of. *)
Theorem every_transposition_index_is_admitted :
  forall n : nat,
    check_of (with_steps demo_cert (swap_at n demo_cert.(cert_steps)))
    = check_of demo_cert.
Proof.
  intros n. unfold check_of. unfold demo_check. unfold spec_check.
  simpl. exact (a_transposition_of_the_records_changes_no_verdict demo 6
                  (code_of_tier TierTwo) demo_cert n eq_refl).
Qed.

Theorem every_duplication_index_is_admitted :
  forall n : nat,
    check_of (with_steps demo_cert (dup_at n demo_cert.(cert_steps)))
    = check_of demo_cert.
Proof.
  intros n. unfold check_of. unfold demo_check. unfold spec_check.
  simpl. exact (a_duplication_of_a_record_changes_no_verdict demo 6
                  (code_of_tier TierTwo) demo_cert n eq_refl).
Qed.

Theorem every_judgment_form_is_admitted :
  forall j : Judgment, check_of (retag j demo_cert) = check_of demo_cert.
Proof.
  intros j. unfold check_of. unfold demo_check. unfold spec_check.
  simpl. exact (retagging_the_judgment_form_changes_no_verdict demo 6
                  (code_of_tier TierTwo) j demo_cert eq_refl).
Qed.

(* =========================================================================
   The generated families over the roster.
   ========================================================================= *)

Example the_roster_family_sizes :
  count_of (roster_deletions Cert golden_roster) = 7
  /\ count_of (roster_insertions Cert w_absent golden_roster) = 8
  /\ count_of (roster_insertions Cert shared_service golden_roster) = 8
  /\ count_of (roster_transpositions Cert golden_roster) = 6
  /\ count_of (roster_duplications Cert golden_roster) = 7 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* A refused component inserted at any position costs the generation, and no
   position is where it could hide: *a rejection is total* as a whole family
   at once, and total at the generation rather than at the package. *)
Example every_insertion_of_a_refused_component_costs_the_generation :
  all_of (fun r => negb (is_some (demo_compose r)))
         (roster_insertions Cert w_absent golden_roster) = true := eq_refl.

(* And an admissible one inserted at any position still composes, so the
   atomicity is a property of the refused member and not of the insertion. *)
Example every_insertion_of_an_admissible_component_still_composes :
  all_of (fun r => is_some (demo_compose r))
         (roster_insertions Cert shared_service golden_roster) = true := eq_refl.

Example every_deletion_still_composes_and_carries_one_fewer :
  all_of (fun r => is_some (demo_compose r))
         (roster_deletions Cert golden_roster) = true
  /\ map_over (fun r => map_option (fun g => count_of g.(gen_image))
                                   (demo_compose r))
              (roster_deletions Cert golden_roster)
     = cons (Some 6) (cons (Some 6) (cons (Some 6) (cons (Some 6) (cons (Some 6)
       (cons (Some 6) (cons (Some 6) nil)))))) := conj eq_refl eq_refl.

Example every_transposition_and_duplication_still_composes :
  all_of (fun r => is_some (demo_compose r))
         (roster_transpositions Cert golden_roster) = true
  /\ all_of (fun r => is_some (demo_compose r))
            (roster_duplications Cert golden_roster) = true :=
  conj eq_refl eq_refl.

(* =========================================================================
   The demo's own pedigree ledger, and the figures no obligation reads.

   R-13-013 makes a producer identity and an attestation fields no admission
   rule reads, which is the point and is also the hazard: a field nothing
   reads is a field a weakening moves in silence. So every package this file
   defines outside the golden roster declares its identifier, its producer and
   its attestation in a conversion, and so does every magnitude the demo
   carries that no obligation above happens to read. Gap h is what these
   figures are; this is where they are pinned.
   ========================================================================= *)

Definition the_packages_off_the_roster : Roster Cert :=
  cons shared_service (cons shared_service_uncovered (cons stock_package
  (cons w_misrouted (cons p_thin (cons p_attested_and_thin
  (cons p_from_the_composer (cons p_two_faults (cons p_two_open_phases
  (cons p_badged (cons p_other_author (cons p_extra_unknown_record
  (cons p_thin_tier_zero (cons w_stale_profile (cons p_stale_and_misbound
  (cons p_misbound_and_unknown_tier
  (cons p_unknown_tier_and_unknown_form nil)))))))))))))))).

Example every_witness_declares_its_pedigree :
  image_ids Cert refusal_witnesses
  = cons 6 (cons 6 (cons 6 (cons 6 (cons 6 (cons 0 (cons 6 (cons 6 nil)))))))
  /\ map_over (fun p => p.(pkg_producer)) refusal_witnesses
     = cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 nil)))))))
  /\ map_over (fun p => p.(pkg_attested)) refusal_witnesses
     = cons false (cons false (cons false (cons false (cons false (cons false
       (cons false (cons false nil))))))) :=
  conj eq_refl (conj eq_refl eq_refl).

Example every_package_off_the_roster_declares_its_pedigree :
  image_ids Cert the_packages_off_the_roster
  = cons 7 (cons 7 (cons 8 (cons 6 (cons 6 (cons 6 (cons 6 (cons 6
    (cons 6 (cons 6 (cons 6 (cons 6 (cons 0 (cons 6 (cons 6 (cons 6
    (cons 6 nil))))))))))))))))
  /\ map_over (fun p => p.(pkg_producer)) the_packages_off_the_roster
     = cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons 3 (cons demo.(composer_id)
       (cons 3 (cons 3 (cons 5 (cons 3 (cons 3 (cons 3 (cons 3
       (cons 3 (cons 3 (cons 3 nil))))))))))))))))
  /\ map_over (fun p => p.(pkg_attested)) the_packages_off_the_roster
     = cons false (cons false (cons false (cons false (cons false (cons true
       (cons true (cons false (cons false (cons true (cons true (cons false
       (cons false (cons false (cons false (cons false (cons false
        nil)))))))))))))))) :=
  conj eq_refl (conj eq_refl eq_refl).

(* And the two packages R-13-013's clause is quantified over declare the halves
   the clause above does not: an attested package carries an ordinary
   producer, and the composer's own package carries an attestation. *)
Example the_pedigree_witnesses_declare_both_halves :
  p_attested_and_thin.(pkg_producer) = 3
  /\ p_attested_and_thin.(pkg_attested) = true
  /\ p_from_the_composer.(pkg_producer) = demo.(composer_id)
  /\ p_from_the_composer.(pkg_attested) = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The shared service compartment and the one whose derivation the pass forgot
   are the same compartment, which is what makes the pair a statement about
   R-13-001c's covering derivation rather than about two components. *)
Example the_uncovered_compartment_is_the_same_compartment :
  shared_service_uncovered.(pkg_id) = shared_service.(pkg_id)
  /\ shared_service_uncovered.(pkg_tier) = shared_service.(pkg_tier)
  /\ shared_service_uncovered.(pkg_cert) = None
  /\ is_some shared_service.(pkg_cert) = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The phantom identifier, and the property that makes it one: it is 21, and
   no image the composer emits carries it. *)
Example the_phantom_identifier_is_carried_by_no_image :
  phantom_id = 21
  /\ mem_nat phantom_id (image_ids Cert golden_roster) = false
  /\ mem_nat phantom_id (image_ids Cert the_packages_off_the_roster) = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* The two-open-phases package read through its own definition rather than
   through a copy of it: one move-I facet and one move-II facet open, five
   records left, and the rest of the tier's requirement discharged. *)
Example the_two_open_phases_package_leaves_one_facet_of_each_move :
  map_option (fun c => count_of c.(cert_steps)) p_two_open_phases.(pkg_cert)
  = Some 5
  /\ map_option (fun c => discharged c CodegenNone) p_two_open_phases.(pkg_cert)
     = Some false
  /\ map_option (fun c => discharged c AbiConform) p_two_open_phases.(pkg_cert)
     = Some false
  /\ map_option (fun c => discharged c MemTemporal) p_two_open_phases.(pkg_cert)
     = Some true
  /\ map_option (fun c => discharged c CfiRuntime) p_two_open_phases.(pkg_cert)
     = Some true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* The tagged carrier's two values, declared: they differ in the tag and in
   nothing the reading can see. *)
Example the_two_tagged_values_differ_in_the_tag :
  p_tagged_zero.(pkg_cert) = Some (pair 0 (covering_cert TierTwo 6))
  /\ p_tagged_one.(pkg_cert) = Some (pair 1 (covering_cert TierTwo 6))
  /\ p_tagged_zero.(pkg_producer) = 3
  /\ p_tagged_one.(pkg_producer) = 3
  /\ p_tagged_zero.(pkg_attested) = false
  /\ p_tagged_one.(pkg_attested) = false
  /\ p_terse_thin.(pkg_producer) = 3
  /\ p_terse_thin.(pkg_attested) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl)))))).

(* And the faulted roster's own shape, so that the position the refused
   component sits at is a figure a check reads rather than one a weakening
   moves. The atomicity result does not depend on it, which the family over
   every position is what says. *)
Example the_faulted_roster_carries_the_refused_component_at_one_position :
  image_ids Cert faulted_roster
  = cons 0 (cons 1 (cons 2 (cons 6 (cons 3 (cons 4 (cons 5 (cons 6 nil)))))))
  /\ count_of faulted_roster = S (count_of golden_roster) := conj eq_refl eq_refl.

(* A record whose facet code the checker cannot read names no facet at all,
   which is what makes the move-blind checker's surviving obligation a
   statement about the facet assignment rather than a vacuous one. *)
Theorem an_unrecognised_facet_code_names_no_facet :
  forall (s : Step) (f : Facet),
    facet_of_code s.(st_facet) = None -> names_facet f s = false.
Proof. intros s f H. unfold names_facet. rewrite H. reflexivity. Qed.

Example an_unreadable_facet_code_names_nothing_and_a_readable_one_names_one :
  all_of (fun f => negb (names_facet f (unknown_facet the_unreadable_record)))
         all_facets = true
  /\ names_facet CtTaint the_unreadable_record = true
  /\ count_of (filter_of (fun f => names_facet f the_unreadable_record)
                         all_facets) = 1 :=
  conj eq_refl (conj eq_refl eq_refl).

(* And a checker that accepts while a required facet is open rejects at no
   phase at all, which is the other way TAL-074's *rejects at the first
   failure* can be broken: the declared-order checker names too late a phase,
   and this one names none. *)
Theorem the_blanket_check_rejects_at_no_phase :
  ~ RejectsAtTheEarliestOpenPhase demo Cert full_reading (blanket_check Cert).
Proof.
  intros H.
  specialize (H amb_first p_thin (thin_cert 6) TierTwo CodegenNone
                eq_refl eq_refl eq_refl eq_refl).
  discriminate H.
Qed.


(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared set
   R-05-164 currently makes empty, so `Closed under the global context` is
   that emptiness checked mechanically.
   ------------------------------------------------------------------------- *)
Print Assumptions all_of.
Print Assumptions any_of.
Print Assumptions count_of.
Print Assumptions map_over.
Print Assumptions filter_of.
Print Assumptions upto.
Print Assumptions before_last.
Print Assumptions only_if.
Print Assumptions bool_eqb.
Print Assumptions is_some.
Print Assumptions map_option.
Print Assumptions mem_nat.
Print Assumptions nat_list_eqb.
Print Assumptions swap_at.
Print Assumptions drop_at.
Print Assumptions insert_at.
Print Assumptions dup_at.
Print Assumptions patch_at.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions only_if_elim.
Print Assumptions nat_eqb_refl.
Print Assumptions nat_eqb_true.
Print Assumptions nat_leb_refl.
Print Assumptions nat_leb_succ.
Print Assumptions nat_leb_trans.
Print Assumptions all_of_app.
Print Assumptions all_of_app_join.
Print Assumptions all_of_mono.
Print Assumptions all_of_filter.
Print Assumptions filter_of_within.
Print Assumptions mem_nat_cons.
Print Assumptions mem_nat_here.
Print Assumptions the_empty_conjunction_holds.
Print Assumptions the_empty_disjunction_fails.
Print Assumptions nothing_has_length_zero.
Print Assumptions before_last_of_nothing.
Print Assumptions the_index_set_of_three.
Print Assumptions only_if_is_implication.
Print Assumptions bool_eqb_is_equality.
Print Assumptions nothing_is_a_member_of_nothing.
Print Assumptions the_empty_lists_agree.
Print Assumptions a_longer_list_does_not_agree.
Print Assumptions the_generators_past_the_end.
Print Assumptions a_transposition_of_one_member_is_that_member.
Print Assumptions the_generators_at_the_front.
Print Assumptions all_judgments.
Print Assumptions all_obligations.
Print Assumptions all_moves.
Print Assumptions all_facets.
Print Assumptions all_tiers.
Print Assumptions all_phases.
Print Assumptions all_rules.
Print Assumptions there_are_eleven_type_level_obligations.
Print Assumptions there_are_three_checker_moves.
Print Assumptions there_are_thirteen_facets.
Print Assumptions there_are_three_assurance_tiers.
Print Assumptions there_are_seven_judgment_forms.
Print Assumptions there_are_six_checker_phases.
Print Assumptions there_are_eight_refusal_rules.
Print Assumptions judgment_eqb.
Print Assumptions judgment_eqb_refl.
Print Assumptions judgment_eqb_true.
Print Assumptions obligation_eqb.
Print Assumptions obligation_eqb_refl.
Print Assumptions obligation_eqb_true.
Print Assumptions move_eqb.
Print Assumptions move_eqb_refl.
Print Assumptions move_eqb_true.
Print Assumptions facet_eqb.
Print Assumptions facet_eqb_refl.
Print Assumptions facet_eqb_true.
Print Assumptions tier_eqb.
Print Assumptions tier_eqb_refl.
Print Assumptions tier_eqb_true.
Print Assumptions phase_eqb.
Print Assumptions phase_eqb_refl.
Print Assumptions rule_eqb.
Print Assumptions rule_eqb_refl.
Print Assumptions rule_eqb_true.
Print Assumptions each_member_is_told_from_every_other.
Print Assumptions verdict_eqb.
Print Assumptions verdict_eqb_refl.
Print Assumptions a_verdict_is_acceptance_or_a_named_refusal.
Print Assumptions accepts.
Print Assumptions rule_of.
Print Assumptions site_of.
Print Assumptions acceptance_and_refusal_are_told_apart.
Print Assumptions two_refusals_differ_at_the_rule_and_at_the_site.
Print Assumptions row_of.
Print Assumptions move_of.
Print Assumptions facets_of_row.
Print Assumptions facets_of_move_in.
Print Assumptions every_row_is_partitioned_into_facets.
Print Assumptions the_two_split_rows_split_as_the_criterion_says.
Print Assumptions the_move_table_is_the_registers.
Print Assumptions phase_rank.
Print Assumptions phase_of_move.
Print Assumptions rule_of_move.
Print Assumptions phase_of_rule.
Print Assumptions the_move_phases_and_the_move_rules_agree.
Print Assumptions the_refusals_are_tried_in_phase_order.
Print Assumptions every_phase_carries_a_refusal.
Print Assumptions code_of_judgment.
Print Assumptions judgment_of_code.
Print Assumptions code_of_move.
Print Assumptions move_of_code.
Print Assumptions code_of_facet.
Print Assumptions facet_of_code.
Print Assumptions code_of_tier.
Print Assumptions tier_of_code.
Print Assumptions past_the_judgments.
Print Assumptions past_the_moves.
Print Assumptions past_the_facets.
Print Assumptions past_the_tiers.
Print Assumptions the_judgment_codes_decode.
Print Assumptions the_move_codes_decode.
Print Assumptions the_facet_codes_decode.
Print Assumptions the_tier_codes_decode.
Print Assumptions the_boundaries_are_the_enumerations.
Print Assumptions every_judgment_form_decodes_to_itself.
Print Assumptions every_move_decodes_to_itself.
Print Assumptions every_facet_decodes_to_itself.
Print Assumptions every_tier_decodes_to_itself.
Print Assumptions the_judgment_decoding_is_the_inverse_coding.
Print Assumptions the_move_decoding_is_the_inverse_coding.
Print Assumptions the_facet_decoding_is_the_inverse_coding.
Print Assumptions the_tier_decoding_is_the_inverse_coding.
Print Assumptions no_code_past_the_judgments_is_recognised.
Print Assumptions no_code_past_the_moves_is_recognised.
Print Assumptions no_code_past_the_facets_is_recognised.
Print Assumptions no_code_past_the_tiers_is_recognised.
Print Assumptions versions_eqb.
Print Assumptions versions_eqb_refl.
Print Assumptions versions_eqb_true.
Print Assumptions Reading.
Print Assumptions with_steps.
Print Assumptions read_cert.
Print Assumptions Checker.
Print Assumptions step_recognised.
Print Assumptions discharges.
Print Assumptions discharged.
Print Assumptions covers.
Print Assumptions mem_facet.
Print Assumptions mem_facet_here.
Print Assumptions mem_facet_app.
Print Assumptions all_of_mem.
Print Assumptions mem_all_of.
Print Assumptions in_phase_order.
Print Assumptions mem_facets_of_move_in.
Print Assumptions the_facets_of_a_move_take_it.
Print Assumptions mem_in_phase_order.
Print Assumptions in_phase_order_keeps_a_conjunction.
Print Assumptions a_conjunction_over_the_phase_order_is_one_over_the_set.
Print Assumptions first_unrecognised.
Print Assumptions first_undischarged.
Print Assumptions first_unrecognised_none.
Print Assumptions first_unrecognised_some.
Print Assumptions all_recognised_first_none.
Print Assumptions first_undischarged_none.
Print Assumptions first_undischarged_some.
Print Assumptions all_discharged_first_none.
Print Assumptions first_undischarged_app.
Print Assumptions first_undischarged_mem.
Print Assumptions first_undischarged_open.
Print Assumptions an_open_facet_breaks_the_coverage.
Print Assumptions the_first_open_facet_is_no_later.
Print Assumptions check_cert.
Print Assumptions spec_check.
Print Assumptions check_cert_refuses_a_stale_version.
Print Assumptions check_cert_refuses_a_wrong_binding.
Print Assumptions check_cert_refuses_an_unrecognised_tier.
Print Assumptions check_cert_refuses_an_unrecognised_form.
Print Assumptions check_cert_refuses_an_undischarged_facet.
Print Assumptions ReadsNoComposerState.
Print Assumptions IsRunIndependent.
Print Assumptions IsAFunctionOfThePackage.
Print Assumptions the_two_halves_compose.
Print Assumptions the_conjunction_gives_back_both_halves.
Print Assumptions the_specification_is_a_function_of_the_package.
Print Assumptions NamesAStableRule.
Print Assumptions NamesAStableSite.
Print Assumptions a_function_of_the_package_names_a_stable_rule_and_site.
Print Assumptions the_specification_names_a_stable_rule_and_site.
Print Assumptions IsAFunctionOfTheReading.
Print Assumptions reads_alike.
Print Assumptions the_verdict_is_a_function_of_the_reading.
Print Assumptions the_specification_is_a_function_of_the_reading.
Print Assumptions Typing.
Print Assumptions SoundFor.
Print Assumptions CompleteFor.
Print Assumptions WellTyped.
Print Assumptions FailsClosed.
Print Assumptions the_specification_fails_closed.
Print Assumptions the_specification_is_complete_for_the_typing_relation.
Print Assumptions RefusesAnAbsentDerivation.
Print Assumptions RefusesAStaleVersion.
Print Assumptions RefusesAWrongBinding.
Print Assumptions RefusesAnUnrecognisedTier.
Print Assumptions RefusesAnUnrecognisedForm.
Print Assumptions RefusesAnUndischargedFacetOf.
Print Assumptions fail_closed_refuses_an_absent_derivation.
Print Assumptions fail_closed_refuses_a_stale_version.
Print Assumptions fail_closed_refuses_a_wrong_binding.
Print Assumptions fail_closed_refuses_an_unrecognised_tier.
Print Assumptions fail_closed_refuses_an_unrecognised_form.
Print Assumptions fail_closed_refuses_an_undischarged_facet.
Print Assumptions the_specification_satisfies_every_named_refusal.
Print Assumptions phase_of_verdict.
Print Assumptions no_later_than.
Print Assumptions RejectsAtTheEarliestOpenPhase.
Print Assumptions the_specification_rejects_at_the_earliest_open_phase.
Print Assumptions RefusesUnderTheStaleVersionFirst.
Print Assumptions RefusesUnderTheWrongBindingBeforeTheTier.
Print Assumptions RefusesUnderTheUnrecognisedTierBeforeTheForm.
Print Assumptions the_specification_refuses_in_the_early_phase_order.
Print Assumptions waiving.
Print Assumptions RefusesUnder.
Print Assumptions waiving_one_rule_keeps_every_other.
Print Assumptions waiving_a_rule_admits_what_that_rule_refused.
Print Assumptions a_reachable_waived_rule_breaks_fail_closed.
Print Assumptions same_but_the_pedigree.
Print Assumptions ReadsNoPedigree.
Print Assumptions the_specification_reads_no_pedigree.
Print Assumptions admission_does_not_move_with_the_producer.
Print Assumptions Roster.
Print Assumptions Composer.
Print Assumptions image_ids.
Print Assumptions admissible.
Print Assumptions spec_compose.
Print Assumptions IsAllOrNothing.
Print Assumptions CommitsOnlyTheAccepted.
Print Assumptions EmitsNoUncoveredStranger.
Print Assumptions CoversWhatItSynthesized.
Print Assumptions CommitsEveryAccepted.
Print Assumptions every_member_names_itself.
Print Assumptions the_specification_is_all_or_nothing.
Print Assumptions the_specification_commits_only_the_accepted.
Print Assumptions the_specification_emits_no_uncovered_stranger.
Print Assumptions the_specification_covers_what_it_synthesized.
Print Assumptions the_specification_commits_every_accepted.
Print Assumptions all_of_insert.
Print Assumptions all_of_drop.
Print Assumptions all_of_swap.
Print Assumptions all_of_dup.
Print Assumptions count_of_insert.
Print Assumptions count_of_swap.
Print Assumptions count_of_drop.
Print Assumptions inserting_a_refused_package_costs_the_generation.
Print Assumptions inserting_an_accepted_package_adds_exactly_one.
Print Assumptions a_deletion_from_an_admissible_roster_still_composes.
Print Assumptions a_transposition_composes_the_same_roster.
Print Assumptions a_duplication_composes_the_same_roster.
Print Assumptions roster_deletions.
Print Assumptions roster_insertions.
Print Assumptions roster_transpositions.
Print Assumptions roster_duplications.
Print Assumptions unknown_form.
Print Assumptions unknown_move.
Print Assumptions unknown_facet.
Print Assumptions attributed.
Print Assumptions retag.
Print Assumptions step_deletions.
Print Assumptions step_transpositions.
Print Assumptions step_duplications.
Print Assumptions step_form_corruptions.
Print Assumptions step_move_corruptions.
Print Assumptions step_facet_corruptions.
Print Assumptions step_misroutings.
Print Assumptions retaggings.
Print Assumptions an_unknown_form_is_never_recognised.
Print Assumptions an_unknown_move_is_never_recognised.
Print Assumptions an_unknown_facet_is_never_recognised.
Print Assumptions a_misrouted_record_is_still_recognised.
Print Assumptions a_misrouted_record_discharges_only_an_attributed_facet.
Print Assumptions retagging_preserves_the_discharges.
Print Assumptions retagging_preserves_coverage.
Print Assumptions retag_preserves_recognition.
Print Assumptions any_of_swap.
Print Assumptions any_of_dup.
Print Assumptions first_undischarged_congruent.
Print Assumptions a_congruent_rewriting_keeps_the_verdict.
Print Assumptions a_transposition_of_the_records_changes_no_verdict.
Print Assumptions a_duplication_of_a_record_changes_no_verdict.
Print Assumptions retagging_the_judgment_form_changes_no_verdict.
Print Assumptions demo_required.
Print Assumptions demo_versions.
Print Assumptions demo.
Print Assumptions demo_row_granular.
Print Assumptions demo_lenient.
Print Assumptions the_demo_machine_declares.
Print Assumptions the_three_machines_differ_only_in_what_they_require.
Print Assumptions the_tier_two_requirement_is_r_13_012_s_six_rows.
Print Assumptions the_tier_two_requirement_owes_two_citations_and_no_deletion.
Print Assumptions the_tier_requirements_are_inhabited_and_nested.
Print Assumptions full_reading.
Print Assumptions Terse.
Print Assumptions terse_reading.
Print Assumptions Tagged.
Print Assumptions tag_reading.
Print Assumptions the_terse_carrier_reads_as_a_thin_derivation.
Print Assumptions records_from.
Print Assumptions covering_cert.
Print Assumptions thin_cert.
Print Assumptions with_sail_model.
Print Assumptions with_profile.
Print Assumptions re_stamping_moves_one_version_and_no_other.
Print Assumptions corrupt_form_at.
Print Assumptions corrupt_move_at.
Print Assumptions corrupt_facet_at.
Print Assumptions misroute_at.
Print Assumptions drop_record_at.
Print Assumptions the_tier_two_covering_derivation.
Print Assumptions the_covering_derivations_are_as_long_as_their_requirements.
Print Assumptions the_covering_derivation_covers_its_tier.
Print Assumptions the_corruption_and_the_misrouting_differ.
Print Assumptions package_at.
Print Assumptions rot_firmware.
Print Assumptions mmode_firmware.
Print Assumptions kernel.
Print Assumptions crypto_core.
Print Assumptions object_store.
Print Assumptions filesystem.
Print Assumptions supervision_tree.
Print Assumptions golden_roster.
Print Assumptions shared_service.
Print Assumptions shared_service_uncovered.
Print Assumptions stock_package.
Print Assumptions phantom_id.
Print Assumptions w_absent.
Print Assumptions w_stale_version.
Print Assumptions w_wrong_binding.
Print Assumptions w_unknown_tier.
Print Assumptions w_unknown_form.
Print Assumptions w_missing_deletion.
Print Assumptions w_missing_citation.
Print Assumptions w_missing_attribute.
Print Assumptions refusal_witnesses.
Print Assumptions w_misrouted.
Print Assumptions p_thin.
Print Assumptions p_attested_and_thin.
Print Assumptions p_from_the_composer.
Print Assumptions p_two_faults.
Print Assumptions p_two_open_phases.
Print Assumptions p_stale_and_misbound.
Print Assumptions p_misbound_and_unknown_tier.
Print Assumptions p_unknown_tier_and_unknown_form.
Print Assumptions amb_first.
Print Assumptions amb_second.
Print Assumptions amb_composing.
Print Assumptions demo_check.
Print Assumptions demo_compose.
Print Assumptions the_probe_ambients.
Print Assumptions the_roster_names_the_golden_model_components.
Print Assumptions every_tier_is_inhabited_by_a_component.
Print Assumptions the_golden_roster_composes.
Print Assumptions the_witness_verdicts.
Print Assumptions every_refusal_rule_fires_on_a_witness.
Print Assumptions every_phase_is_reached_by_a_witness.
Print Assumptions the_refusal_names_the_first_failing_phase.
Print Assumptions the_absent_and_the_thin_are_refused_apart.
Print Assumptions a_thin_derivation_is_admitted_where_the_tier_requires_nothing.
Print Assumptions the_stale_derivation_is_otherwise_complete.
Print Assumptions neither_attestation_nor_authorship_moves_a_verdict.
Print Assumptions the_row_granular_reading_refuses_what_the_register_admits.
Print Assumptions the_two_readings_differ_in_exactly_one_facet.
Print Assumptions p_terse_thin.
Print Assumptions the_two_carriers_carry_the_same_package.
Print Assumptions the_two_carriers_are_read_alike.
Print Assumptions the_thin_derivation_is_decided_alike_over_either_carrier.
Print Assumptions the_terse_carrier_draws_the_same_refusal.
Print Assumptions orb_split.
Print Assumptions state_reading_check.
Print Assumptions the_state_reading_check_reads_the_composer.
Print Assumptions the_state_reading_check_is_run_independent.
Print Assumptions the_state_reading_check_reads_no_pedigree.
Print Assumptions the_state_reading_check_is_not_a_function_of_the_package.
Print Assumptions the_state_reading_check_agrees_away_from_the_composer.
Print Assumptions flaky_check.
Print Assumptions the_flaky_check_answers_differently_on_a_second_run.
Print Assumptions the_flaky_check_reads_no_composer_state.
Print Assumptions the_flaky_check_agrees_on_the_first_run.
Print Assumptions neither_half_alone_is_the_property.
Print Assumptions p_tagged_zero.
Print Assumptions p_tagged_one.
Print Assumptions the_two_tagged_packages_read_alike.
Print Assumptions tag_peeking_check.
Print Assumptions the_tag_peeking_check_reads_the_carrier.
Print Assumptions the_tag_peeking_check_fails_closed.
Print Assumptions the_tag_peeking_check_is_a_function_of_the_package.
Print Assumptions the_tag_peeking_check_reads_no_pedigree.
Print Assumptions the_tag_peeking_check_answers_two_readings_alike_apart.
Print Assumptions p_badged.
Print Assumptions the_badged_package_differs_only_in_its_pedigree.
Print Assumptions the_badged_package_differs_only_there.
Print Assumptions attestation_check.
Print Assumptions the_attestation_check_reads_a_pedigree.
Print Assumptions the_attestation_check_is_a_function_of_the_package.
Print Assumptions neither_authority_obligation_implies_the_other.
Print Assumptions trusting_check.
Print Assumptions p_other_author.
Print Assumptions the_other_author_differs_only_there.
Print Assumptions the_other_author_is_attested_and_still_refused.
Print Assumptions the_trusting_check_reads_a_pedigree.
Print Assumptions the_thin_package_is_not_well_typed.
Print Assumptions the_composer_authored_package_is_not_well_typed.
Print Assumptions the_trusting_check_fails_open.
Print Assumptions the_trusting_check_agrees_on_the_golden_roster.
Print Assumptions paranoid_check.
Print Assumptions blanket_check.
Print Assumptions the_paranoid_check_is_sound_for_anything.
Print Assumptions the_admitted_component_is_well_typed.
Print Assumptions the_paranoid_check_is_not_complete.
Print Assumptions the_blanket_check_is_complete_for_anything.
Print Assumptions the_blanket_check_fails_open.
Print Assumptions the_two_poles_satisfy_the_other_obligations.
Print Assumptions wandering_site_check.
Print Assumptions wandering_rule_check.
Print Assumptions the_wandering_site_check_names_a_stable_rule.
Print Assumptions the_wandering_site_check_moves_the_site.
Print Assumptions the_wandering_rule_check_names_a_stable_site.
Print Assumptions the_wandering_rule_check_moves_the_rule.
Print Assumptions neither_payload_half_implies_the_other.
Print Assumptions the_two_wandering_checks_move_different_halves.
Print Assumptions nothing_to_check.
Print Assumptions the_vacuous_check_admits_an_absent_derivation.
Print Assumptions the_vacuous_check_keeps_the_other_seven.
Print Assumptions the_vacuous_check_differs_at_exactly_one_witness.
Print Assumptions any_of_filter_implies.
Print Assumptions an_open_facet_stays_open_when_records_are_dropped.
Print Assumptions dropping_a_record_can_only_lose_coverage.
Print Assumptions permissive_form_check.
Print Assumptions with_extra_record.
Print Assumptions the_unreadable_record.
Print Assumptions the_unreadable_record_is_unrecognised.
Print Assumptions p_extra_unknown_record.
Print Assumptions the_permissive_check_admits_an_unrecognised_form.
Print Assumptions the_permissive_check_keeps_the_other_seven.
Print Assumptions the_permissive_check_is_invisible_until_a_record_is_unreadable.
Print Assumptions reroute.
Print Assumptions move_blind_check.
Print Assumptions reroute_preserves_recognition.
Print Assumptions rerouting_preserves_every_recognition.
Print Assumptions names_facet.
Print Assumptions a_discharge_names_its_facet.
Print Assumptions reroute_names_the_same_facet.
Print Assumptions an_unnamed_facet_is_undischarged_after_rerouting.
Print Assumptions the_move_blind_check_admits_a_misrouted_discharge.
Print Assumptions the_move_blind_check_keeps_the_five_clauses_before_the_moves.
Print Assumptions the_move_blind_check_still_refuses_an_unnamed_facet.
Print Assumptions the_move_blind_check_differs_at_the_misrouted_witness.
Print Assumptions check_in_declared_order.
Print Assumptions declared_order_check.
Print Assumptions the_declared_order_check_fails_closed.
Print Assumptions the_declared_order_check_is_complete.
Print Assumptions p_thin_tier_zero.
Print Assumptions the_declared_order_check_rejects_at_a_later_phase.
Print Assumptions the_two_walks_name_different_phases.
Print Assumptions binding_first_check.
Print Assumptions tier_before_binding_check.
Print Assumptions form_first_check.
Print Assumptions the_binding_first_check_accepts_where_the_specification_does.
Print Assumptions the_tier_before_binding_check_accepts_where_the_specification_does.
Print Assumptions the_form_first_check_accepts_where_the_specification_does.
Print Assumptions the_reordered_checkers_fail_closed_and_are_complete.
Print Assumptions the_binding_first_check_names_the_binding_where_the_version_is_stale.
Print Assumptions the_binding_first_check_keeps_the_other_two.
Print Assumptions the_tier_before_binding_check_names_the_tier_where_the_binding_is_wrong.
Print Assumptions the_tier_before_binding_check_keeps_the_other_two.
Print Assumptions the_form_first_check_names_the_form_where_the_tier_is_unrecognised.
Print Assumptions the_form_first_check_keeps_the_other_two.
Print Assumptions the_early_phases_are_tried_in_order.
Print Assumptions each_early_witness_fails_two_phases.
Print Assumptions the_reordered_checkers_agree_on_the_golden_roster.
Print Assumptions with_versions.
Print Assumptions only_the_spec_set.
Print Assumptions partial_version_check.
Print Assumptions the_partial_version_check_admits_a_stale_model.
Print Assumptions the_partial_version_check_keeps_the_other_seven.
Print Assumptions w_stale_profile.
Print Assumptions the_partial_version_check_admits_two_stale_derivations.
Print Assumptions filter_of_all.
Print Assumptions filtering_composer.
Print Assumptions faulted_roster.
Print Assumptions the_filtering_composer_ships_a_partial_generation.
Print Assumptions the_filtering_composer_keeps_the_other_four.
Print Assumptions one_refused_component_costs_the_generation.
Print Assumptions no_position_of_a_refused_component_composes.
Print Assumptions merging_composer.
Print Assumptions substituting_composer.
Print Assumptions the_merging_composer_satisfies_every_clause.
Print Assumptions the_shared_service_is_admissible_in_every_ambient.
Print Assumptions the_stock_package_is_admissible_in_every_ambient.
Print Assumptions the_merging_composer_at_the_shared_service_satisfies_every_clause.
Print Assumptions the_merged_compartment_is_a_package_the_roster_does_not_name.
Print Assumptions the_stripping_merge_commits_an_unvalidated_binary.
Print Assumptions the_substituting_composer_emits_an_uncovered_stranger.
Print Assumptions the_substituting_composer_keeps_the_other_four.
Print Assumptions the_substituting_composer_at_the_stock_package_keeps_the_other_four.
Print Assumptions phantom_merge_composer.
Print Assumptions the_phantom_merge_covers_nothing_it_declared.
Print Assumptions the_phantom_merge_keeps_the_other_four.
Print Assumptions starving_composer.
Print Assumptions the_starving_composer_drops_the_admissible.
Print Assumptions the_starving_composer_keeps_the_other_four.
Print Assumptions waived.
Print Assumptions each_waived_rule_admits_exactly_what_it_waives.
Print Assumptions every_waived_rule_admits_a_package_the_specification_refused.
Print Assumptions no_waived_rule_fails_closed.
Print Assumptions waiving_the_absent_derivation_rule_breaks_its_clause.
Print Assumptions waiving_the_version_rule_breaks_its_clause.
Print Assumptions waiving_the_binding_rule_breaks_its_clause.
Print Assumptions waiving_the_tier_rule_breaks_its_clause.
Print Assumptions waiving_the_form_rule_breaks_its_clause.
Print Assumptions waiving_the_deletion_rule_breaks_its_clause.
Print Assumptions waiving_the_citation_rule_breaks_its_clause.
Print Assumptions waiving_the_attribute_rule_breaks_its_clause.
Print Assumptions a_waived_checker_still_refuses_every_other_rule.
Print Assumptions demo_cert.
Print Assumptions with_cert.
Print Assumptions check_of.
Print Assumptions the_demo_derivation_is_the_supervision_tree_s.
Print Assumptions the_generated_family_sizes.
Print Assumptions every_record_deletion_is_refused.
Print Assumptions every_code_corruption_is_refused_at_the_structure_phase.
Print Assumptions the_three_corruptions_differ_beneath_the_refusal.
Print Assumptions the_misrouting_family_refuses_exactly_the_cited_facets.
Print Assumptions every_transposition_of_the_records_is_admitted.
Print Assumptions every_duplication_of_a_record_is_admitted.
Print Assumptions every_retagging_of_the_judgment_form_is_admitted.
Print Assumptions the_retaggings_name_seven_different_forms.
Print Assumptions no_record_deletion_is_admitted.
Print Assumptions no_code_corruption_is_admitted.
Print Assumptions every_transposition_index_is_admitted.
Print Assumptions every_duplication_index_is_admitted.
Print Assumptions every_judgment_form_is_admitted.
Print Assumptions the_roster_family_sizes.
Print Assumptions every_insertion_of_a_refused_component_costs_the_generation.
Print Assumptions every_insertion_of_an_admissible_component_still_composes.
Print Assumptions every_deletion_still_composes_and_carries_one_fewer.
Print Assumptions every_transposition_and_duplication_still_composes.
Print Assumptions the_packages_off_the_roster.
Print Assumptions every_witness_declares_its_pedigree.
Print Assumptions every_package_off_the_roster_declares_its_pedigree.
Print Assumptions the_pedigree_witnesses_declare_both_halves.
Print Assumptions the_uncovered_compartment_is_the_same_compartment.
Print Assumptions the_phantom_identifier_is_carried_by_no_image.
Print Assumptions the_two_open_phases_package_leaves_one_facet_of_each_move.
Print Assumptions the_two_tagged_values_differ_in_the_tag.
Print Assumptions the_faulted_roster_carries_the_refused_component_at_one_position.
Print Assumptions an_unrecognised_facet_code_names_no_facet.
Print Assumptions an_unreadable_facet_code_names_nothing_and_a_readable_one_names_one.
Print Assumptions the_blanket_check_rejects_at_no_phase.
