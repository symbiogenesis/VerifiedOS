(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   RotFirmware.v

   The Root of Trust's firmware, as the register fixes it: R-09-002's
   measured chain from the RoT through the M-mode image to the static
   image, with no stage executing before its measurement is recorded;
   R-09-006's one path, taken by cold boot, deep-sleep wake and the
   recovery generation alike, so that no second loader exists; R-09-037's
   lifecycle extension as the chain's first extension, before the ROM
   verifies any payload, and its own clause that R-09-025's vector is not
   widened by it; R-09-006a's start-up entropy verdict measured into the
   chain, with no key derived, no material unsealed and no quote completed
   on a failed root; R-09-029's boot-target latch measured like every other
   input; R-09-025's attestation vector and R-09-026's reference-value dual
   over the same vector, appraised by R-12-015's relying party; R-12-014's
   seal and unseal binding secrets to the RoT and the measured state, with
   R-15-079's diversification by lifecycle state and R-09-023's sealing-root
   version beside them; R-09-028 and R-09-030's monotonic anti-rollback
   floor, boot counting and automatic revert; R-10-013's four monotonic
   counters with the events R-10-013 and R-09-023 pair them with;
   R-12-017's attempt counter charged before the comparison and never
   refunded; R-09-036's lifecycle-diversified verification roots;
   R-05-058c's signature split by verifier rather than by signer; and
   R-09-034's lifecycle table for the Debug Module and trace, carrying
   R-15-078's production gate and R-15-079's authenticated entry inside it.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. There is no firmware here:
   what is written down is the obligations a Root-of-Trust firmware
   discharges, each stated of an arbitrary loader, chain, unsealer, quote,
   appraisal, floor, advancement, charge, revert, settlement, boot
   admission, debug entry, machine, ROM or scheme choice, proved of the
   specification, and refuted of an alternative
   construction the register's own sentence excludes. Every quantity the
   register leaves to composition, to a measurement, or to another item is a
   field of the Machine record rather than a literal or a top-level
   Parameter, which is what keeps the R-05-163 assumption gate green while
   leaving the decision where its owner can make it. Nothing is admitted and
   nothing is axiomatized: the Print Assumptions block at the end reports
   every shipped constant closed under the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. No constant here is compiled,
   lowered, or run on either emulator, and nothing here executes anywhere.
   The computed checks are decided inside the kernel by conversion and print
   nothing.

   What is deferred, and to which item. The primitives are M3.4's and are
   not here: the hash is an arbitrary two-argument extension, and what a
   Machine declares of it is R-05-058c's hash-only assumption cut to the
   finite instance the chain draws on, which reading 7 states; no AEAD,
   no signature verifier and no DRBG appears below, R-15-241d's seeding
   discipline being the crypto core's. The boot chain reaching the M-mode
   kernel on the golden emulator is M3.5's: nothing below is an image, an
   address, or an instruction, and no statement here is about a run. The
   windowed watchdog is neither: R-15-240's bark and bite are M3.1's model
   and R-11-017's admission artifact emits the window bounds, so no window,
   no pet and no nonce appears below.

   No Require. Nothing beyond the Rocq prelude is reachable, so Classical
   and FunctionalExtensionality are unavailable and every equality below is
   stated pointwise or over a decidable boolean for that reason. A Require
   naming a sibling artifact would be admissible, and there is none to name:
   DischargeSequence.v's sequencer is R-15-247d's discharge order over
   banks and this file's is R-09-002's measurement order over stages, the
   two sharing a shape and no quantity; MModeFirmware.v is the stage this
   chain hands off to and states R-07-028's refinement over a composed
   capability graph, which no obligation below mentions; SupervisionTree.v's
   boot count is R-16-007's downtime bound where this file's is R-09-028's
   automatic revert. Each would be a citation rather than a dependency.

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. The chain is a list of steps, and a step is either the extension of
      one named input or the execution of one named stage. R-09-002 fixes
      the four stages and R-09-037, R-09-006a and R-09-029 each name one
      input measured into the chain; nothing else below is an item, and no
      item is invented. Modelling execution as a step of the same list is
      what makes "no stage executes before its measurement is recorded" a
      precedence rather than a comment.
   2. The quote's vector is R-09-025's four admission-discipline terms with
      the chain measurement beside them. This is a judgment and not a
      transcription, and gap g is the register question it takes a side of:
      that entry's sentence is "attestation covers the chain *and* the
      admission discipline", while its acceptance clause says "the quote's
      *vector* is exactly this set", which distinguishes the quote from its
      vector and leaves "this set" able to name the four enumerated terms
      alone. Nothing settles it. R-09-037 does not: its clause constrains
      the lifecycle state, ruling out a sixth field and having the state
      enter as a chain measurement, all of which the four-term reading
      satisfies word for word. What is argued rather than derived is the
      consequence: on the narrow reading a relying party's appraisal does
      not decide the chain, which
      `a_vector_without_the_chain_appraises_a_forked_chain` computes as a
      machine appraising clean on a forked chain. That prices the narrow
      reading and is why this file takes the wide one; it does not close it,
      and the coverage check below is written against the wide reading, so
      pointing at that check would argue in a circle.
   3. The vector is a set and not an order. R-09-025's own word is *set*,
      so a transposed vector covers exactly, which is computed below rather
      than assumed; the transposition family therefore carries nothing here
      and the generated families are the deletions, the widenings and the
      duplications instead.
   4. The lifecycle state is measured into the chain and is not a term of
      the vector. R-09-037 says both in as many words, so Field carries a
      sixth constructor whose only role is to be excluded, and the widening
      family is generated over it.
   5. Unseal is one predicate with four independent gates and a fifth
      obligation on what it hands back, so this file states five properties
      of an unseal and not four. The gates are the measured digest
      (R-12-014's "binding secrets to the RoT and measured state"), the
      lifecycle state (R-15-079's diversified hierarchy, whose own
      acceptance clause is that a debuggable part cannot unseal
      production-sealed material), the sealing-root version (R-09-023's
      RoT-fresh conferral into R-10-013), and the latched start-up verdict
      (R-09-006a); reading 6 is the fifth. Each of the five is refuted by a
      construction keeping the other four, so the five are five obligations
      and not one stated five times.
   6. What an unseal returns is a handle and never a key. R-12-014's
      criterion is that apps hold only sealed blobs and capability handles
      and R-12-015a deletes raw key export, so the answer type carries a
      cleartext constructor whose only role is to be excluded, and the
      exporting construction is refuted while satisfying all four gates.
   7. The hash is arbitrary, and what a Machine declares of it is
      R-05-058c's hash-only assumption at the scale this file uses it and
      not a total one. Collisions exist for every hash function, so a field
      separating every pair of distinct inputs is met by no realizable
      machine and a theorem over such a Machine is true of nothing. What a
      Machine declares instead is that at each of the seven digests the
      specification chain extends from, the seven item codes extend to
      seven different digests: a decidable statement over a finite set,
      which the demo machine discharges by conversion and which a counting
      extension and a late-colliding one are computed to fail. The
      assumption the register puts in the trust base is computational, this
      is the finite instance of it the chain draws on, and realizing the
      extension is M3.4's.
   8. Anti-rollback is three mechanisms and not one: the monotone floor
      (R-09-028, R-09-030), the four monotonic counters with the events
      R-10-013 and R-09-023 pair them with, and the boot-attempt count with
      R-09-028's automatic revert. They are stated apart, and a
      construction satisfying two of the three and breaking the third is
      exhibited for each.
   9. The boot-attempt count is charged on the ordinary failure and not on
      the entropy halt. R-09-006a says exactly that, so the outcome
      enumeration below is that entry's own two failure classes and not a
      general fault taxonomy; gap c reports what a success does.
  10. The signature scheme is a function of the verifier and of nothing
      else, which is R-09-002's second acceptance clause read as a property
      rather than as an absence; which stage the metal-mask ROM verifies is
      a field, because R-09-006 fixes the ROM's sequence and not the
      composition's split.
  11. Boolean rather than propositional wherever the witnesses must
      compute: the chain checks, the coverage check and the admission tests
      are decidable, so the generated weakening families are checked by
      conversion in the silent Example form rather than by a proof per
      member.
  12. The order is stated over positions rather than over a rank function
      built into a list's shape, so a chain out of order is expressible and
      the theorems have something to exclude. Precedence is strict and is
      false where either step is absent, which is what makes a deletion a
      refusal rather than a silence; both are theorems over an arbitrary
      carrier rather than properties of the definition's shape, because
      neither case is reachable from the chain check on the generated
      families, the occurrence checks refusing a deletion first.

   The literals taken from the design, and each is an enumeration the
   register itself closes. R-09-002's chain is four stages, so `all_stages`
   is that list and `there_are_four_stages` is its count. R-09-006's
   acceptance clause names three boot kinds, so `all_kinds` is three.
   R-09-032 closes the lifecycle at five states under a fixed relation, so
   `all_lifecycles` is five. R-10-013 enumerates four counters, so
   `all_counters` is four. R-10-013's own advancing events are four, and
   R-09-023's conferral adds the duress erase to the sealing root's, and
   R-10-013 excludes the data commit, so `all_events` is six. R-09-025
   enumerates four admission-discipline terms, so four of `quote_vector`'s
   five are closed. R-05-058c names two schemes. R-09-028's images
   are A/B, so `Slot` is two. R-09-034 closes the Debug Module and trace at
   each of R-09-032's five states, live in development and RMA alone and
   closed everywhere else, so `debug_table` is that table and its five
   values are literals. And a stage is run exactly once and an input
   extended exactly once on one pass, so the occurrence checks compare
   against 1.
   Every other magnitude is a field: the ROM seed, the extension function,
   the measurement encoding, the fuse-held state, the latched entropy
   verdict, the expected debug-entry response per state, the accepted root
   per state, which stages the ROM verifies, the rollback floor, the boot
   bound, each counter's value, and the witness and reference values of
   every term of the vector. The machine's own Debug Module liveness table
   is a field for the opposite reason to the rest: the register closes what
   it must be, so the field is what the obligations below are stated of, and
   a machine whose table differs from `debug_table` is a refuted
   construction rather than an admitted composition.
   And one magnitude is neither, which the inventory says rather than
   rounds: `quote_vector`'s **fifth** term, the chain measurement, is
   reading 2's judgment and gap g's open question, not an enumeration
   R-09-025 closes. It is written as a literal beside the four closed ones
   rather than made a field because a field would hand the register's own
   question to a composition and make R-09-025's *exactly this set* vacuous,
   every machine covering whatever vector it declared. So the term is a
   stated reading carrying its own gap, and the deletion at index 0 is the
   alternative reading rather than a defect: what refuses that deletion is a
   coverage check written against the wide reading, which is why gap g is
   reported and not closed here.

   How the refutations are generated. A refutation is a seeded weakening
   the theorem must reject, so four polymorphic generators produce families
   of them from the specification's own structure rather than a person
   authoring each, which is DischargeSequence.v's method taken over three
   different lists. `swap_at` transposes an adjacent pair, `drop_at`
   deletes a member, `suffix_at` re-enters at a proper suffix, and
   `insert_at` repeats a member. Over R-09-002's stage order they yield
   sixteen weakenings, every one refused. Over the input prologue they
   yield twelve, of which eleven are refused and the twelfth is gap a,
   named and computed rather than described. Over R-09-025's vector the
   deletions, the widenings by the excluded term and the duplications yield
   seventeen, every one refused, while the transpositions are admitted
   because reading 3 says the vector is a set. Each family fact is stated
   twice, once as one conversion over the enumeration and once as a bounded
   quantifier over the index. The hand-authored refutations below are the
   ones no index generates, being alternative constructions rather than
   mutations of a list, and each is shown to satisfy the obligations it
   does not break.

   What this file deliberately does not author, with what owes each
   decision. A register gap is one no entry decides and is reported rather
   than closed; a deferral is an entry that decides it and an item on this
   plan that authors it, which is a different thing and is named as one:

   a. Whether the entropy verdict is extended before or after the
      boot-target latch. R-09-037 fixes the lifecycle extension first and
      R-09-006a fixes the verdict before any measured stage draws; neither
      orders the verdict against R-09-029's latch, which that entry
      measures "like every other input" without saying where. The weakest
      reading admits both, and the two orders reach different digests, which
      `the_two_prologue_orders_measure_differently` computes. Whether that
      difference reaches a relying party depends on gap g: on reading 2's
      wide vector the chain measurement is a term and the quote carries it,
      and on the narrow reading no quote does. Owed at R-09-006a or
      R-09-029.
   b. Whether the chain measures each stage immediately before running it
      or measures the whole payload up front. R-09-002's acceptance clause
      fixes only that no stage executes before its measurement is recorded,
      and R-09-006 has the ROM place the verified M-mode image before
      releasing the boot core, which is the front-loaded shape for one
      stage and says nothing about the rest.
      `the_front_loaded_chain_satisfies_every_stated_obligation` checks
      that both shapes pass. Owed at R-09-002 or R-09-006.
   c. What a successful boot does to the boot-attempt count. R-09-028
      states boot counting with automatic revert and R-09-006a takes the
      entropy halt out of it as a §16 fault class consuming no attempt; no
      entry says whether a success clears the count, so the outcome
      enumeration below is R-09-006a's two failure classes and nothing here
      models a success. A gap, owed at R-09-028.
   d. The TRNG's start-up sample budget. R-15-241b sizes the start-up
      health tests against the source's stochastic model, so nothing below
      carries a sample count, a rate, or an entropy estimate: the verdict is
      a latched boolean field and the budget is the model's. Deferred and
      not a gap: item S5 authors that stochastic model, after the M8a gate,
      the budget being a qualification input rather than a boot condition.
   e. The §16 deterministic-replay nondeterminism record. R-15-241 requires
      every draw accounted for in it and R-16-015 through R-16-021 specify
      it, so nothing below introduces a draw, a seed, a commitment, or the
      sealing of one, and the entropy root enters here only as R-09-006a's
      verdict. Deferred and not a gap: item S6 authors the record, after the
      M8a gate on S5's ground. The plan schedules both this and d, so what
      this file does not author here is deferred rather than unowned.
   f. What the reference integrity manifest covers where it differs from
      the quote. R-09-026 makes it the reference-value dual "covering the
      same vector", so the appraisal below is stated over whatever vector
      the quote covers rather than over a manifest-side enumeration, and no
      second coverage check is invented. A gap, owed at R-09-026.
   g. Whether R-09-025's "this set" is the four admission-discipline terms
      alone or those four with the chain measurement. The MUST has
      attestation cover the chain and the discipline both; the acceptance
      clause names "the quote's *vector*", which is not the quote, and
      "this set", which can name the enumeration the colon introduces.
      R-09-026 carries the referent over to the manifest without fixing it
      and R-09-037 constrains the lifecycle state rather than the chain, so
      no entry decides it. Reading 2 takes the wide reading on the
      consequence `a_vector_without_the_chain_appraises_a_forked_chain`
      computes, which prices the narrow reading and does not refute it. A
      gap, owed at R-09-025.
   h. Every composition magnitude. The ROM seed, the extension, the
      measurement encoding, the fuse-held state, the entropy verdict, the
      expected debug-entry response, the accepted roots, the ROM-verified
      stage set, the rollback floor, the boot bound, the four counter values
      and the witness and reference values are fields; the demo machines at
      the end instantiate them with arbitrary witness values that carry no
      composition claim. Not a gap and not a deferral: it is the field
      discipline stated once, in the list its own paragraph above gives.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary parameter, proved of the specification, and
   refuted of an alternative construction the register's own sentence
   excludes. Inhabitation is concrete: nine demo machines differing one
   field at a time, a blob that unseals here and four presentations at which
   it does not, a chain that passes beside twenty-eight generated weakenings of
   which twenty-seven are refused and the twenty-eighth is gap a, seventeen
   refused weakenings of the vector beside four transpositions that are
   admitted because the vector is a set, a lifecycle table that R-09-034
   closes beside three machines that break a clause of it apiece, one of
   them breaking two at once because the third clause carries the first, and
   an appraisal that holds beside two that fail, and a hash-separation
   declaration the demo extension meets by conversion beside two extensions
   computed to fail it, so no theorem is proved from a premise nothing
   satisfies and none from one everything satisfies.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   List and boolean helpers, defined here rather than imported: the prelude
   carries the list type and not the library over it, and importing a module
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

Fixpoint map_over {A B : Type} (f : A -> B) (l : list A) : list B :=
  match l with nil => nil | cons x r => cons (f x) (map_over f r) end.

Fixpoint filter_of {A : Type} (p : A -> bool) (l : list A) : list A :=
  match l with
  | nil => nil
  | cons x r => if p x then cons x (filter_of p r) else filter_of p r
  end.

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

Definition bool_eqb (a b : bool) : bool := if a then b else negb b.

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

Lemma bool_eqb_sound : forall a b : bool, bool_eqb a b = true -> a = b.
Proof. intros a b. destruct a; destruct b; simpl; intros H;
  try discriminate H; reflexivity. Qed.

Lemma nat_eqb_refl : forall n : nat, Nat.eqb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma nat_eqb_sound : forall a b : nat, Nat.eqb a b = true -> a = b.
Proof.
  intros a. induction a as [ | x IH ]; intros b H.
  - destruct b as [ | y ]; [ reflexivity | discriminate H ].
  - destruct b as [ | y ]; [ discriminate H | ]. simpl in H.
    rewrite (IH y H). reflexivity.
Qed.

Lemma nat_leb_refl : forall n : nat, Nat.leb n n = true.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma nat_eqb_sym : forall a b : nat, Nat.eqb a b = Nat.eqb b a.
Proof.
  intros a. induction a as [ | x IH ]; intros b; destruct b as [ | y ];
    try reflexivity. simpl. exact (IH y).
Qed.

Lemma negb_true : forall b : bool, negb b = true -> b = false.
Proof. intros b H. destruct b; [ discriminate H | reflexivity ]. Qed.

(* The helpers' own floors, so that the day one of them stops deciding is
   the day it says so. Each is a base case no check below reaches. *)
Example the_empty_conjunction_holds :
  all_of (fun _ : nat => false) nil = true := eq_refl.

Example the_empty_disjunction_fails :
  any_of (fun _ : nat => true) nil = false := eq_refl.

Example nothing_has_length_zero : count_of (nil : list nat) = 0 := eq_refl.

Example before_last_of_nothing : before_last 0 = 0 := eq_refl.

Example the_index_set_of_three : upto 3 = cons 0 (cons 1 (cons 2 nil)) := eq_refl.

Example only_if_is_implication :
  cons (only_if true true) (cons (only_if true false)
  (cons (only_if false true) (cons (only_if false false) nil)))
  = cons true (cons false (cons true (cons true nil))) := eq_refl.

Example bool_eqb_is_agreement :
  cons (bool_eqb true true) (cons (bool_eqb true false)
  (cons (bool_eqb false true) (cons (bool_eqb false false) nil)))
  = cons true (cons false (cons false (cons true nil))) := eq_refl.

(* -------------------------------------------------------------------------
   Membership, position and precedence over an arbitrary carrier with a
   decidable equality passed in. Polymorphic because three different lists
   below take the same obligations: the boot chain's steps, the input
   prologue's items, and the credential attempt's two steps.
   ------------------------------------------------------------------------- *)

Definition member {A : Type} (eqb : A -> A -> bool) (x : A) (l : list A) : bool :=
  any_of (fun y => eqb x y) l.

Fixpoint pos_from {A : Type} (eqb : A -> A -> bool) (x : A) (l : list A)
                  (i : nat) : option nat :=
  match l with
  | nil => None
  | cons y r => if eqb x y then Some i else pos_from eqb x r (S i)
  end.

Definition pos {A : Type} (eqb : A -> A -> bool) (x : A) (l : list A)
  : option nat := pos_from eqb x l 0.

Fixpoint occurrences {A : Type} (eqb : A -> A -> bool) (x : A)
                     (l : list A) : nat :=
  match l with
  | nil => 0
  | cons y r => if eqb x y then S (occurrences eqb x r) else occurrences eqb x r
  end.

(* False where either member is absent, which is what makes a deletion a
   refusal rather than a silence (reading 12). *)
Definition precedes {A : Type} (eqb : A -> A -> bool) (x y : A)
                    (l : list A) : bool :=
  match pos eqb x l, pos eqb y l with
  | Some i, Some j => Nat.ltb i j
  | _, _ => false
  end.

Lemma all_of_member :
  forall (A : Type) (eqb : A -> A -> bool),
    (forall x y : A, eqb x y = true -> x = y) ->
    forall (p : A -> bool) (l : list A) (x : A),
      all_of p l = true -> member eqb x l = true -> p x = true.
Proof.
  intros A eqb sound p l. induction l as [ | y r IH ]; intros x Hall Hmem.
  - discriminate Hmem.
  - simpl in Hall. destruct (andb_split _ _ Hall) as [ Hy Hr ].
    unfold member in Hmem. simpl in Hmem.
    destruct (eqb x y) eqn:E.
    + rewrite (sound x y E). exact Hy.
    + exact (IH x Hr Hmem).
Qed.

Lemma nat_ltb_irrefl : forall n : nat, Nat.ltb n n = false.
Proof. intros n. induction n as [ | k IH ]. - reflexivity. - simpl. exact IH. Qed.

Lemma pos_from_none :
  forall (A : Type) (eqb : A -> A -> bool) (x : A) (l : list A) (i : nat),
    member eqb x l = false -> pos_from eqb x l i = None.
Proof.
  intros A eqb x l. induction l as [ | y r IH ]; intros i H.
  - reflexivity.
  - simpl. unfold member in H. simpl in H. destruct (eqb x y).
    + discriminate H.
    + exact (IH (S i) H).
Qed.

(* Precedence is strict, so a chain does not order a step against itself:
   the property every obligation below that reads a precedence rests on, and
   the one an inclusive comparison would silently lose. *)
Theorem precedence_is_strict :
  forall (A : Type) (eqb : A -> A -> bool) (x : A) (l : list A),
    precedes eqb x x l = false.
Proof.
  intros A eqb x l. unfold precedes.
  destruct (pos eqb x l) as [ i | ]; [ exact (nat_ltb_irrefl i) | reflexivity ].
Qed.

(* And reading 12 as a theorem rather than as a comment: a member the list
   omits precedes nothing, which is what makes a deletion a refusal rather
   than a silence. *)
Theorem an_absent_member_precedes_nothing :
  forall (A : Type) (eqb : A -> A -> bool) (x y : A) (l : list A),
    member eqb x l = false -> precedes eqb x y l = false.
Proof.
  intros A eqb x y l H. unfold precedes, pos.
  rewrite (pos_from_none A eqb x l 0 H). reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Distinctness of a list of numbers, decided, and what it says of two
   members: the shape R-05-058c's hash-only assumption takes below, where
   the list is the seven digests the item codes extend one digest to.
   ------------------------------------------------------------------------- *)

Fixpoint distinct (l : list nat) : bool :=
  match l with
  | nil => true
  | cons x r => andb (negb (member Nat.eqb x r)) (distinct r)
  end.

Example the_empty_list_is_distinct : distinct nil = true := eq_refl.

Example a_repeated_number_is_not_distinct :
  distinct (cons 1 (cons 2 (cons 1 nil))) = false
  /\ distinct (cons 1 (cons 2 (cons 3 nil))) = true := conj eq_refl eq_refl.

Lemma member_here_or_there :
  forall (A : Type) (eqb : A -> A -> bool) (x y : A) (r : list A),
    member eqb x (cons y r) = orb (eqb x y) (member eqb x r).
Proof. intros A eqb x y r. reflexivity. Qed.

Lemma member_nat_absent :
  forall (x y : nat) (l : list nat),
    member Nat.eqb x l = false -> member Nat.eqb y l = true ->
    Nat.eqb x y = false.
Proof.
  intros x y l Hx Hy. destruct (Nat.eqb x y) eqn:E; [ | reflexivity ].
  rewrite (nat_eqb_sound x y E) in Hx. rewrite Hy in Hx. discriminate Hx.
Qed.

Lemma member_map :
  forall (A : Type) (eqb : A -> A -> bool) (f : A -> nat) (x : A) (l : list A),
    (forall a b : A, eqb a b = true -> a = b) ->
    member eqb x l = true -> member Nat.eqb (f x) (map_over f l) = true.
Proof.
  intros A eqb f x l sound. induction l as [ | y r IH ]; intros H.
  - discriminate H.
  - rewrite member_here_or_there in H.
    change (member Nat.eqb (f x) (cons (f y) (map_over f r)) = true).
    rewrite member_here_or_there.
    destruct (eqb x y) eqn:E.
    + rewrite (sound x y E). rewrite nat_eqb_refl. reflexivity.
    + change (member eqb x r = true) in H. rewrite (IH H).
      destruct (Nat.eqb (f x) (f y)); reflexivity.
Qed.

(* Two different members of a list whose image is distinct have different
   images: the one direction the obligation below reads, stated over an
   arbitrary carrier so that it is a theorem and not a computation over the
   seven items it is used at. *)
Lemma distinct_separates :
  forall (A : Type) (eqb : A -> A -> bool),
    (forall a b : A, eqb a b = true -> a = b) ->
    (forall a : A, eqb a a = true) ->
    forall (f : A -> nat) (l : list A) (a b : A),
      distinct (map_over f l) = true ->
      member eqb a l = true -> member eqb b l = true ->
      eqb a b = false -> Nat.eqb (f a) (f b) = false.
Proof.
  intros A eqb sound refl f l.
  induction l as [ | y r IH ]; intros a b Hd Ha Hb Hne.
  - discriminate Ha.
  - change (andb (negb (member Nat.eqb (f y) (map_over f r)))
                 (distinct (map_over f r)) = true) in Hd.
    destruct (andb_split _ _ Hd) as [ Hy Hr ].
    rewrite member_here_or_there in Ha. rewrite member_here_or_there in Hb.
    destruct (eqb a y) eqn:Ea; destruct (eqb b y) eqn:Eb.
    + rewrite (sound a y Ea) in Hne. rewrite (sound b y Eb) in Hne.
      rewrite refl in Hne. discriminate Hne.
    + change (member eqb b r = true) in Hb. rewrite (sound a y Ea).
      exact (member_nat_absent _ _ _ (negb_true _ Hy)
               (member_map A eqb f b r sound Hb)).
    + change (member eqb a r = true) in Ha. rewrite (sound b y Eb).
      rewrite nat_eqb_sym.
      exact (member_nat_absent _ _ _ (negb_true _ Hy)
               (member_map A eqb f a r sound Ha)).
    + change (member eqb a r = true) in Ha. change (member eqb b r = true) in Hb.
      exact (IH a b Hr Ha Hb Hne).
Qed.

(* -------------------------------------------------------------------------
   The four weakening generators, polymorphic for the same reason. Each
   yields one weakening per position of whatever list it is handed.
   ------------------------------------------------------------------------- *)

(* Transpose the adjacent pair at n: the natural wrong move on an ordered
   chain, and one weakening per adjacent position. *)
Fixpoint swap_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons a (cons b r) => cons b (cons a r)
  | 0, _ => l
  | S k, cons a r => cons a (swap_at k r)
  | S _, nil => nil
  end.

(* Delete the member at n: a stage never run, or an input never extended. *)
Fixpoint drop_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons _ r => r
  | 0, nil => nil
  | S k, cons a r => cons a (drop_at k r)
  | S _, nil => nil
  end.

(* Re-enter at the suffix beginning at n, which is what a resume path that
   was not a boot-chain variant would be (R-09-010). *)
Fixpoint suffix_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, _ => l
  | S k, cons _ r => suffix_at k r
  | S _, nil => nil
  end.

(* Repeat one member, one weakening per position. *)
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

Definition proper_suffixes {A : Type} (l : list A) : list (list A) :=
  map_over (fun n => suffix_at (S n) l) (upto (count_of l)).

Definition duplications {A : Type} (x : A) (l : list A) : list (list A) :=
  map_over (fun n => insert_at n x l) (upto (S (count_of l))).

(* =========================================================================
   The closed enumerations, and only these. Each is closed because the
   register itself closes it: an enumeration here that the register leaves
   to composition would be this file inventing a specification under a proof
   gate, which is the line a statement artifact does not cross.
   ========================================================================= *)

(* R-09-032's five lifecycle states, in that entry's own order, held as
   one-way OTP fuse state. Nothing below carries the transition relation:
   R-09-033's monotonicity is a stated RTL-refines-Sail obligation and not a
   firmware one. *)
Inductive Lifecycle : Type :=
| Raw
| TestState
| Development
| Production
| Rma.

Definition all_lifecycles : list Lifecycle :=
  cons Raw (cons TestState (cons Development (cons Production (cons Rma nil)))).

Example there_are_five_lifecycle_states : count_of all_lifecycles = 5 := eq_refl.

Definition lifecycle_eqb (a b : Lifecycle) : bool :=
  match a, b with
  | Raw, Raw => true
  | TestState, TestState => true
  | Development, Development => true
  | Production, Production => true
  | Rma, Rma => true
  | _, _ => false
  end.

Lemma lifecycle_eqb_refl : forall a : Lifecycle, lifecycle_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma lifecycle_eqb_sound :
  forall a b : Lifecycle, lifecycle_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

(* R-09-002's chain, stage by stage, in that entry's own order: the RoT
   runtime the ROM verifies and enters (R-09-006), the verified M-mode
   image it places in main SRAM, the per-core kernels of all classes, and
   the static image. *)
Inductive Stage : Type :=
| RotRuntime
| MModeImage
| CoreKernels
| StaticImage.

Definition all_stages : list Stage :=
  cons RotRuntime (cons MModeImage (cons CoreKernels (cons StaticImage nil))).

Example there_are_four_stages : count_of all_stages = 4 := eq_refl.

Definition stage_eqb (a b : Stage) : bool :=
  match a, b with
  | RotRuntime, RotRuntime => true
  | MModeImage, MModeImage => true
  | CoreKernels, CoreKernels => true
  | StaticImage, StaticImage => true
  | _, _ => false
  end.

Lemma stage_eqb_refl : forall a : Stage, stage_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma stage_eqb_sound : forall a b : Stage, stage_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

(* R-09-006's acceptance clause: cold boot, deep-sleep wake and the
   recovery generation all take the one path, so no second loader exists. *)
Inductive BootKind : Type :=
| ColdBoot
| DeepSleepWake
| RecoveryGeneration.

Definition all_kinds : list BootKind :=
  cons ColdBoot (cons DeepSleepWake (cons RecoveryGeneration nil)).

Example there_are_three_boot_kinds : count_of all_kinds = 3 := eq_refl.

(* R-10-013's enumeration of the state the RoT monotonic counter is spent
   on, closed by conferral (R-10-013a) at four members. *)
Inductive Counter : Type :=
| SecurityVersionFloor
| SealingRootVersion
| CredentialAttemptCounter
| FreshnessEpochRoot.

Definition all_counters : list Counter :=
  cons SecurityVersionFloor (cons SealingRootVersion
  (cons CredentialAttemptCounter (cons FreshnessEpochRoot nil))).

Example there_are_four_counters : count_of all_counters = 4 := eq_refl.

Definition counter_eqb (a b : Counter) : bool :=
  match a, b with
  | SecurityVersionFloor, SecurityVersionFloor => true
  | SealingRootVersion, SealingRootVersion => true
  | CredentialAttemptCounter, CredentialAttemptCounter => true
  | FreshnessEpochRoot, FreshnessEpochRoot => true
  | _, _ => false
  end.

Lemma counter_eqb_refl : forall a : Counter, counter_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma counter_eqb_sound : forall a b : Counter, counter_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

(* R-10-013's own advancing events, R-09-023's conferral adding the duress
   erase to the sealing root's, and the one the same sentence excludes.
   Six, because the register names six and not because a taxonomy wanted
   rounding. *)
Inductive Event : Type :=
| SignedUpdate
| KeyRotation
| DuressErase
| AuthAttempt
| SealedEpoch
| DataCommit.

Definition all_events : list Event :=
  cons SignedUpdate (cons KeyRotation (cons DuressErase
  (cons AuthAttempt (cons SealedEpoch (cons DataCommit nil))))).

Example there_are_six_counter_events : count_of all_events = 6 := eq_refl.

(* R-09-025's vector, and the one term R-09-037 keeps out of it. The sixth
   constructor's only role is to be excluded: that entry extends the
   lifecycle state into the chain and says in as many words that the
   vector is not widened by it. *)
Inductive Field : Type :=
| ChainDigest
| CheckerVersion
| SpecAndPolicySet
| IsaProfileVersion
| RadioGenerationIdentity
| LifecycleFuseValue.

Definition all_fields : list Field :=
  cons ChainDigest (cons CheckerVersion (cons SpecAndPolicySet
  (cons IsaProfileVersion (cons RadioGenerationIdentity
  (cons LifecycleFuseValue nil))))).

Example there_are_six_named_terms : count_of all_fields = 6 := eq_refl.

Definition field_eqb (a b : Field) : bool :=
  match a, b with
  | ChainDigest, ChainDigest => true
  | CheckerVersion, CheckerVersion => true
  | SpecAndPolicySet, SpecAndPolicySet => true
  | IsaProfileVersion, IsaProfileVersion => true
  | RadioGenerationIdentity, RadioGenerationIdentity => true
  | LifecycleFuseValue, LifecycleFuseValue => true
  | _, _ => false
  end.

Lemma field_eqb_refl : forall a : Field, field_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma field_eqb_sound : forall a b : Field, field_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

(* R-05-058c's split: everything a metal-mask ROM verifies is SLH-DSA, and
   ML-DSA carries the replaceable paths above it. Two, and the entry names
   two. *)
Inductive Scheme : Type :=
| SlhDsa
| MlDsa.

Definition all_schemes : list Scheme := cons SlhDsa (cons MlDsa nil).

Example there_are_two_signature_schemes : count_of all_schemes = 2 := eq_refl.

(* R-09-028's A/B images. *)
Inductive Slot : Type :=
| SlotA
| SlotB.

Definition all_slots : list Slot := cons SlotA (cons SlotB nil).

Example there_are_two_image_slots : count_of all_slots = 2 := eq_refl.

(* R-09-006a's two failure classes, and only those: the entry separates the
   entropy halt, which is a §16 fault class consuming no attempt, from the
   ordinary failure the automatic revert answers. Gap c records that a
   success is not modelled. *)
Inductive Outcome : Type :=
| EntropyHalt
| OrdinaryFailure.

Definition all_outcomes : list Outcome :=
  cons EntropyHalt (cons OrdinaryFailure nil).

Example there_are_two_boot_failure_classes : count_of all_outcomes = 2 := eq_refl.

(* R-12-014's criterion read as a type: apps hold only sealed blobs and
   capability handles, and R-12-015a deletes raw key export, so the third
   constructor exists to be excluded. *)
Inductive Answer : Type :=
| Refused
| Handle (h : nat)
| Cleartext (k : nat).

Definition is_cleartext (a : Answer) : bool :=
  match a with
  | Refused => false
  | Handle _ => false
  | Cleartext _ => true
  end.

Example only_the_third_answer_is_cleartext :
  cons (is_cleartext Refused) (cons (is_cleartext (Handle 0))
  (cons (is_cleartext (Cleartext 0)) nil))
  = cons false (cons false (cons true nil)) := eq_refl.

(* The chain's items: the three inputs the register names as measured, and
   one measurement per stage (reading 1). *)
Inductive Item : Type :=
| LifecycleFuse           (* R-09-037: the chain's first extension       *)
| EntropyHealthVerdict    (* R-09-006a: the start-up verdict             *)
| BootTargetLatch         (* R-09-029: the one-bit boot-target register  *)
| StageMeasure (s : Stage).

Definition all_items : list Item :=
  cons LifecycleFuse (cons EntropyHealthVerdict (cons BootTargetLatch
  (map_over StageMeasure all_stages))).

Example the_chain_measures_seven_things : count_of all_items = 7 := eq_refl.

Definition item_eqb (a b : Item) : bool :=
  match a, b with
  | LifecycleFuse, LifecycleFuse => true
  | EntropyHealthVerdict, EntropyHealthVerdict => true
  | BootTargetLatch, BootTargetLatch => true
  | StageMeasure s, StageMeasure t => stage_eqb s t
  | _, _ => false
  end.

Lemma item_eqb_refl : forall a : Item, item_eqb a a = true.
Proof. intros a. destruct a as [ | | | s ]; try reflexivity. exact (stage_eqb_refl s). Qed.

Lemma item_eqb_sound : forall a b : Item, item_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a as [ | | | s ]; destruct b as [ | | | t ]; simpl;
    intros H; try discriminate H; try reflexivity.
  rewrite (stage_eqb_sound s t H). reflexivity.
Qed.

(* A step of the chain: an extension of one item, or the execution of one
   stage. Modelling execution as a step of the same list is what makes
   R-09-002's "no stage executes before its measurement is recorded" a
   precedence rather than a comment. *)
Inductive Step : Type :=
| Extend (i : Item)
| Run (s : Stage).

Definition step_eqb (a b : Step) : bool :=
  match a, b with
  | Extend i, Extend j => item_eqb i j
  | Run s, Run t => stage_eqb s t
  | _, _ => false
  end.

Lemma step_eqb_refl : forall a : Step, step_eqb a a = true.
Proof.
  intros a. destruct a as [ i | s ].
  - exact (item_eqb_refl i).
  - exact (stage_eqb_refl s).
Qed.

Lemma step_eqb_sound : forall a b : Step, step_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a as [ i | s ]; destruct b as [ j | t ]; simpl;
    intros H; try discriminate H.
  - rewrite (item_eqb_sound i j H). reflexivity.
  - rewrite (stage_eqb_sound s t H). reflexivity.
Qed.

(* The two steps R-12-017 orders, which is the whole of that entry's
   mechanism: the counter advances before the comparison. *)
Inductive AttemptStep : Type :=
| ChargeTheCounter
| CompareTheCredential.

Definition attempt_eqb (a b : AttemptStep) : bool :=
  match a, b with
  | ChargeTheCounter, ChargeTheCounter => true
  | CompareTheCredential, CompareTheCredential => true
  | _, _ => false
  end.

Lemma attempt_eqb_refl : forall a : AttemptStep, attempt_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma attempt_eqb_sound :
  forall a b : AttemptStep, attempt_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H;
    try discriminate H; reflexivity.
Qed.

(* Reading a conjunction over one of these enumerations back at one of its
   members, which is what lets the obligations below be stated of an
   arbitrary stage, item, field or counter rather than only computed over a
   list. *)
Lemma every_stage_is_in_the_roster :
  forall s : Stage, member stage_eqb s all_stages = true.
Proof. intros s. destruct s; reflexivity. Qed.

Lemma every_item_is_in_the_roster :
  forall i : Item, member item_eqb i all_items = true.
Proof. intros i. destruct i as [ | | | s ]; try reflexivity. destruct s; reflexivity. Qed.

Lemma every_field_is_in_the_roster :
  forall f : Field, member field_eqb f all_fields = true.
Proof. intros f. destruct f; reflexivity. Qed.

Lemma every_counter_is_in_the_roster :
  forall c : Counter, member counter_eqb c all_counters = true.
Proof. intros c. destruct c; reflexivity. Qed.

Lemma all_of_stages :
  forall (p : Stage -> bool) (s : Stage), all_of p all_stages = true -> p s = true.
Proof.
  intros p s H.
  exact (all_of_member Stage stage_eqb stage_eqb_sound p all_stages s H
           (every_stage_is_in_the_roster s)).
Qed.

Lemma all_of_items :
  forall (p : Item -> bool) (i : Item), all_of p all_items = true -> p i = true.
Proof.
  intros p i H.
  exact (all_of_member Item item_eqb item_eqb_sound p all_items i H
           (every_item_is_in_the_roster i)).
Qed.

Lemma all_of_fields :
  forall (p : Field -> bool) (f : Field), all_of p all_fields = true -> p f = true.
Proof.
  intros p f H.
  exact (all_of_member Field field_eqb field_eqb_sound p all_fields f H
           (every_field_is_in_the_roster f)).
Qed.

Lemma all_of_counters :
  forall (p : Counter -> bool) (c : Counter),
    all_of p all_counters = true -> p c = true.
Proof.
  intros p c H.
  exact (all_of_member Counter counter_eqb counter_eqb_sound p all_counters c H
           (every_counter_is_in_the_roster c)).
Qed.

(* =========================================================================
   R-05-058c's hash-only assumption at the scale this file uses it (reading
   7). An extension is applied at seven digests on one pass, the seed and
   the six the items before each stage reach, and at each of them to seven
   item codes; what a Machine declares is that at every one of those seven
   digests the seven codes extend to seven different digests. Stated over
   the extension, the encoding and the seed rather than over a Machine,
   because the record that declares it is not yet defined and because the
   two extensions computed to fail it below are not Machines at all.
   ========================================================================= *)

(* The digest each extension is applied at when the items are extended in
   the roster's order from d: one per item, the seed first, and never the
   digest the last extension reaches, which nothing extends from. *)
Fixpoint extension_points (ext : nat -> nat -> nat) (code : Item -> nat)
                          (d : nat) (is : list Item) : list nat :=
  match is with
  | nil => nil
  | cons i r => cons d (extension_points ext code (ext d (code i)) r)
  end.

Definition separates_at (ext : nat -> nat -> nat) (code : Item -> nat)
                        (d : nat) : bool :=
  distinct (map_over (fun i => ext d (code i)) all_items).

Definition separates_along (ext : nat -> nat -> nat) (code : Item -> nat)
                           (seed : nat) : bool :=
  all_of (separates_at ext code) (extension_points ext code seed all_items).

Example nothing_is_extended_from_no_item :
  extension_points (fun d a => d + a) (fun _ => 1) 5 nil = nil := eq_refl.

(* =========================================================================
   The machine: everything the register leaves to composition, to a
   measurement, or to another item. Fields rather than Parameters, because a
   top-level Parameter prints as an assumption and fails the R-05-163 gate.
   ========================================================================= *)

Record Machine : Type := {

  (* --- R-09-002's chain hash. The extension is arbitrary and the encoding
         of a measurement is the composition's, the primitive being M3.4's
         and not this file's (reading 7) ---------------------------------- *)

  rom_seed : nat;
  extend : nat -> nat -> nat;
  item_code : Item -> nat;

  (* --- R-05-058c's hash-only assumption, which measured boot already puts
         in the trust base, declared by the machine at the scale the chain
         uses it rather than assumed totally by this file: at each of the
         seven digests the specification chain extends from, the seven item
         codes extend to seven different digests. Decidable, so a machine
         discharges it by conversion or is not a Machine (reading 7) ------ *)

  extend_separates_on_the_chain :
    separates_along extend item_code rom_seed = true;

  (* --- R-09-032's fuse-held lifecycle state, and the machine's own Debug
         Module liveness table beside it. The table is a field because the
         obligations below are stated of an arbitrary machine and a machine
         breaking R-09-034's table has to be expressible; what the table must
         be is `debug_table`, which the register closes -------------------- *)

  state : Lifecycle;
  debug_live : Lifecycle -> bool;

  (* --- R-15-079's debug entry, whose expected response is ML-DSA-signed
         and serial-bound, so the value is the crypto core's (M3.4) and what
         is here is the response the RoT holds for each state ------------- *)

  debug_response : Lifecycle -> nat;

  (* --- R-15-241b's latched start-up verdict. A boolean and never a sample
         budget, an entropy rate or an estimate: that is the source's
         stochastic model's, which item S5 authors (gap d) ---------------- *)

  entropy_ok : bool;

  (* --- R-09-036's verification root per lifecycle state, and R-05-058c's
         split read off which stages the metal-mask ROM verifies ---------- *)

  accepted_root : Lifecycle -> nat;
  rom_verifies : Stage -> bool;

  (* --- R-09-028's monotonic anti-rollback floor and boot-attempt bound -- *)

  rollback_floor : nat;
  boot_bound : nat;

  (* --- R-10-013's four counters, at their current values ---------------- *)

  counter : Counter -> nat;

  (* --- R-09-025's vector as the machine measures it, and R-09-026's
         reference-value dual over the same terms ------------------------- *)

  witness : Field -> nat;
  reference : Field -> nat
}.

(* =========================================================================
   The measured chain (R-09-002, R-09-005, R-09-006, R-09-029, R-09-037,
   R-09-006a).

   The specification's chain is built from two lists the register fixes
   separately: the inputs measured before any payload is verified, and
   R-09-002's stage order. Building it rather than writing it out is what
   lets the generated families below run over each list on its own, so that
   a weakening of the stage order and a weakening of the input prologue are
   two different findings.
   ========================================================================= *)

Definition input_prologue : list Item :=
  cons LifecycleFuse (cons EntropyHealthVerdict (cons BootTargetLatch nil)).

Fixpoint stage_chain (ss : list Stage) : list Step :=
  match ss with
  | nil => nil
  | cons s r => cons (Extend (StageMeasure s)) (cons (Run s) (stage_chain r))
  end.

Definition chain_from (pre : list Item) (ss : list Stage) : list Step :=
  app (map_over Extend pre) (stage_chain ss).

Definition boot_steps : list Step := chain_from input_prologue all_stages.

Example the_specification_chain_has_eleven_steps :
  count_of boot_steps = 11 := eq_refl.

Example the_lifecycle_extension_stands_at_the_first_position :
  pos step_eqb (Extend LifecycleFuse) boot_steps = Some 0
  /\ pos step_eqb (Run StaticImage) boot_steps = Some 10
  /\ pos step_eqb (Extend (StageMeasure RotRuntime)) boot_steps = Some 3 :=
  conj eq_refl (conj eq_refl eq_refl).

(* R-09-037: the lifecycle state is the chain's first extension, and it is
   recorded before the ROM verifies any payload. Two conjuncts, because the
   entry states two things and a chain can satisfy either alone. *)
Definition lifecycle_extended_first (l : list Step) : bool :=
  andb (all_of (fun i => only_if (negb (item_eqb i LifecycleFuse))
                                 (precedes step_eqb (Extend LifecycleFuse)
                                           (Extend i) l))
               all_items)
       (all_of (fun s => only_if (member step_eqb (Run s) l)
                                 (precedes step_eqb (Extend LifecycleFuse)
                                           (Run s) l))
               all_stages).

(* R-09-002's acceptance clause: no stage executes before its measurement is
   recorded. *)
Definition measured_before_run (l : list Step) : bool :=
  all_of (fun s => only_if (member step_eqb (Run s) l)
                           (precedes step_eqb (Extend (StageMeasure s))
                                     (Run s) l))
         all_stages.

(* Every stage of the chain runs, and runs once on one pass. The 1 is one of
   this file's two occurrence literals. *)
Definition every_stage_runs_once (l : list Step) : bool :=
  all_of (fun s => Nat.eqb (occurrences step_eqb (Run s) l) 1) all_stages.

(* And every input the register names is extended, once. R-09-029's latch is
   measured "like every other input", which is what makes this one check
   over the whole item roster rather than three. *)
Definition every_input_extended_once (l : list Step) : bool :=
  all_of (fun i => Nat.eqb (occurrences step_eqb (Extend i) l) 1) all_items.

(* R-09-002's own order among the stages, read off the roster rather than
   written out a second time. *)
Fixpoint stages_in_chain_order (l : list Step) (ss : list Stage) : bool :=
  match ss with
  | nil => true
  | cons a rest =>
      match rest with
      | nil => true
      | cons b _ => andb (precedes step_eqb (Run a) (Run b) l)
                         (stages_in_chain_order l rest)
      end
  end.

(* The order check's own floors, which the roster never reaches: a stage
   order with nothing in it and one with a single stage each order
   vacuously, and no obligation over `all_stages` walks either case. *)
Example the_empty_stage_order_is_trivially_ordered :
  stages_in_chain_order boot_steps nil = true
  /\ stages_in_chain_order boot_steps (cons StaticImage nil) = true
  /\ stages_in_chain_order nil all_stages = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* R-09-006a: the start-up health tests complete before the first draw any
   measured stage can make, and the verdict is measured into the chain. *)
Definition verdict_before_any_run (l : list Step) : bool :=
  all_of (fun s => only_if (member step_eqb (Run s) l)
                           (precedes step_eqb (Extend EntropyHealthVerdict)
                                     (Run s) l))
         all_stages.

Definition chain_ok (l : list Step) : bool :=
  andb (lifecycle_extended_first l)
  (andb (measured_before_run l)
  (andb (every_stage_runs_once l)
  (andb (every_input_extended_once l)
  (andb (stages_in_chain_order l all_stages)
        (verdict_before_any_run l))))).

Definition IsAMeasuredChain (l : list Step) : Prop :=
  lifecycle_extended_first l = true
  /\ measured_before_run l = true
  /\ every_stage_runs_once l = true
  /\ every_input_extended_once l = true
  /\ stages_in_chain_order l all_stages = true
  /\ verdict_before_any_run l = true.

Lemma chain_ok_sound : forall l : list Step, chain_ok l = true -> IsAMeasuredChain l.
Proof.
  intros l H. unfold chain_ok in H.
  destruct (andb_split _ _ H) as [ H1 R1 ].
  destruct (andb_split _ _ R1) as [ H2 R2 ].
  destruct (andb_split _ _ R2) as [ H3 R3 ].
  destruct (andb_split _ _ R3) as [ H4 R4 ].
  destruct (andb_split _ _ R4) as [ H5 H6 ].
  exact (conj H1 (conj H2 (conj H3 (conj H4 (conj H5 H6))))).
Qed.

Lemma chain_ok_complete :
  forall l : list Step, IsAMeasuredChain l -> chain_ok l = true.
Proof.
  intros l [ H1 [ H2 [ H3 [ H4 [ H5 H6 ] ] ] ] ]. unfold chain_ok.
  apply andb_join; [ exact H1 | ]. apply andb_join; [ exact H2 | ].
  apply andb_join; [ exact H3 | ]. apply andb_join; [ exact H4 | ].
  apply andb_join; [ exact H5 | exact H6 ].
Qed.

(* C1 (R-09-002): the acceptance clause read at an arbitrary stage of an
   arbitrary chain, which is what lets the specification's chain be one
   witness among the chains this file exhibits rather than the only
   expressible list. *)
Theorem a_measured_chain_records_a_stage_before_it_runs :
  forall (l : list Step) (s : Stage),
    measured_before_run l = true ->
    member step_eqb (Run s) l = true ->
    precedes step_eqb (Extend (StageMeasure s)) (Run s) l = true.
Proof.
  intros l s Hall Hin.
  exact (only_if_elim _ _ (all_of_stages _ s Hall) Hin).
Qed.

(* C2 (R-09-037): and the lifecycle extension precedes every other, at an
   arbitrary item of an arbitrary chain. *)
Theorem a_measured_chain_extends_the_lifecycle_first :
  forall (l : list Step) (i : Item),
    lifecycle_extended_first l = true ->
    item_eqb i LifecycleFuse = false ->
    precedes step_eqb (Extend LifecycleFuse) (Extend i) l = true.
Proof.
  intros l i Hall Hne. destruct (andb_split _ _ Hall) as [ Hitems _ ].
  assert (Hi : only_if (negb (item_eqb i LifecycleFuse))
                       (precedes step_eqb (Extend LifecycleFuse) (Extend i) l)
               = true) by exact (all_of_items _ i Hitems).
  rewrite Hne in Hi. simpl in Hi. exact Hi.
Qed.

(* C3 (R-09-006a): and the verdict precedes every stage that runs. *)
Theorem a_measured_chain_records_the_verdict_before_any_stage_runs :
  forall (l : list Step) (s : Stage),
    verdict_before_any_run l = true ->
    member step_eqb (Run s) l = true ->
    precedes step_eqb (Extend EntropyHealthVerdict) (Run s) l = true.
Proof.
  intros l s Hall Hin.
  exact (only_if_elim _ _ (all_of_stages _ s Hall) Hin).
Qed.

(* Reading 12 at this file's own carrier: a step the chain omits precedes
   nothing and is preceded by nothing, and no step precedes itself. Neither
   case is reachable from `chain_ok` on the generated families, the
   occurrence checks refusing a deletion first, so both are stated here or
   nowhere. *)
Example a_step_the_chain_omits_precedes_nothing :
  precedes step_eqb (Extend BootTargetLatch) (Run RotRuntime)
           (drop_at 2 boot_steps) = false
  /\ precedes step_eqb (Run RotRuntime) (Extend BootTargetLatch)
              (drop_at 2 boot_steps) = false
  /\ precedes step_eqb (Run RotRuntime) (Run MModeImage) nil = false :=
  conj eq_refl (conj eq_refl eq_refl).

Example no_step_of_the_chain_precedes_itself :
  precedes step_eqb (Run RotRuntime) (Run RotRuntime) boot_steps = false
  /\ precedes step_eqb (Extend LifecycleFuse) (Extend LifecycleFuse)
              boot_steps = false := conj eq_refl eq_refl.

(* C4: the specification's chain passes all six conjuncts. *)
Theorem the_specification_chain_is_a_measured_chain :
  IsAMeasuredChain boot_steps.
Proof. apply chain_ok_sound. reflexivity. Qed.

(* =========================================================================
   The one path (R-09-006, R-09-010), and this file's load-bearing theorem.

   R-09-006's acceptance clause is that cold boot, deep-sleep wake and the
   recovery generation all take the one path, so no second loader exists,
   and R-09-010 says the same from the sleep side: suspend is
   seal-and-power-off and wake re-executes the measured chain rather than
   resuming into it. Stated over an arbitrary loader, that clause is what
   carries the measured-boot property from the path it was checked on to
   every path the device takes, and through nothing else.
   ========================================================================= *)

Definition Loader : Type := BootKind -> list Step.

Definition spec_loader : Loader := fun _ => boot_steps.

Definition IsTheOnePath (ld : Loader) : Prop :=
  forall k1 k2 : BootKind, ld k1 = ld k2.

(* C5 (R-09-006). *)
Theorem the_specification_loader_is_the_one_path : IsTheOnePath spec_loader.
Proof. intros k1 k2. reflexivity. Qed.

(* C6, the join (R-09-006 with R-09-002): the singular path is what carries
   a chain checked on cold boot to the deep-sleep wake and the recovery
   generation, and the construction below shows that without it the
   cold-boot check says nothing about either. *)
Theorem the_one_path_carries_the_measured_chain :
  forall (ld : Loader) (k : BootKind),
    IsTheOnePath ld -> chain_ok (ld ColdBoot) = true -> chain_ok (ld k) = true.
Proof. intros ld k H Hc. rewrite (H k ColdBoot). exact Hc. Qed.

(* A second loader in the shape R-09-010 names: on wake it re-enters at the
   last stage rather than re-executing the measured chain, which is the
   resume trampoline the design has no analog of. *)
Definition resume_loader : Loader := fun k =>
  match k with
  | DeepSleepWake => cons (Run StaticImage) nil
  | ColdBoot => boot_steps
  | RecoveryGeneration => boot_steps
  end.

Theorem the_resume_loader_is_a_second_loader :
  ~ IsTheOnePath resume_loader.
Proof. intros H. specialize (H ColdBoot DeepSleepWake). discriminate H. Qed.

(* And it is measured on cold boot and unmeasured on wake, so what the join
   above adds is not a restatement of the chain check: the same loader
   passes on one kind and fails on another. *)
Theorem without_the_one_path_the_cold_boot_check_decides_nothing :
  chain_ok (resume_loader ColdBoot) = true
  /\ chain_ok (resume_loader RecoveryGeneration) = true
  /\ chain_ok (resume_loader DeepSleepWake) = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* =========================================================================
   The chain digest (R-09-025's first term, R-09-027).

   The digest is a fold of the machine's own extension over the items the
   chain extended, and the Run steps contribute nothing: what a measurement
   records is the item, and executing a stage is not itself an extension.
   R-09-027's reference values are *reproduced, not asserted*, which is the
   property stated here: the digest is a function of the chain alone and of
   nothing the boot happened to observe.
   ========================================================================= *)

Fixpoint digest_of (m : Machine) (d : nat) (l : list Step) : nat :=
  match l with
  | nil => d
  | cons (Extend i) r => digest_of m (m.(extend) d (m.(item_code) i)) r
  | cons (Run _) r => digest_of m d r
  end.

(* What a boot may observe and what no reference value may be a function of:
   the boot-attempt count is the one such quantity this file carries. *)
Definition Observation : Type := nat.

Definition Digest (m : Machine) : Type := Observation -> list Step -> nat.

Definition spec_digest (m : Machine) : Digest m :=
  fun _ l => digest_of m m.(rom_seed) l.

Definition IsReproducible (m : Machine) (dg : Digest m) : Prop :=
  forall (o1 o2 : Observation) (l : list Step), dg o1 l = dg o2 l.

(* C7 (R-09-027). *)
Theorem the_specification_digest_is_reproducible :
  forall m : Machine, IsReproducible m (spec_digest m).
Proof. intros m o1 o2 l. reflexivity. Qed.

(* The digests the chain applies its extension at, read off the chain
   itself rather than off the roster: one per Extend step, and the Run steps
   contribute nothing, as above. *)
Fixpoint chain_extension_points (m : Machine) (d : nat) (l : list Step)
  : list nat :=
  match l with
  | nil => nil
  | cons (Extend i) r =>
      cons d (chain_extension_points m (m.(extend) d (m.(item_code) i)) r)
  | cons (Run _) r => chain_extension_points m d r
  end.

(* The specification chain extends from exactly the digests the Machine's
   declaration ranges over, at every machine: the chain extends the roster
   in the roster's order, so the two folds are one list. The declaration
   is stated over the roster because the record cannot name a chain defined
   after it, and this is what makes that a statement about the chain. *)
Theorem the_specification_chain_extends_from_the_declared_digests :
  forall m : Machine,
    chain_extension_points m m.(rom_seed) boot_steps
    = extension_points m.(extend) m.(item_code) m.(rom_seed) all_items.
Proof. intros m. reflexivity. Qed.

Theorem the_specification_chain_extends_from_seven_digests :
  forall m : Machine,
    count_of (chain_extension_points m m.(rom_seed) boot_steps) = 7.
Proof. intros m. reflexivity. Qed.

(* At any digest the declaration ranges over, two different items extend it
   to two different digests: the declaration read back at one digest and
   one pair, through the distinctness lemma. *)
Lemma a_declared_digest_separates_the_items :
  forall (m : Machine) (d : nat) (a b : Item),
    member Nat.eqb d (extension_points m.(extend) m.(item_code) m.(rom_seed)
                                       all_items) = true ->
    item_eqb a b = false ->
    Nat.eqb (m.(extend) d (m.(item_code) a)) (m.(extend) d (m.(item_code) b))
    = false.
Proof.
  intros m d a b Hd Hne.
  assert (Hat : separates_at m.(extend) m.(item_code) d = true)
    by exact (all_of_member nat Nat.eqb nat_eqb_sound
                (separates_at m.(extend) m.(item_code))
                (extension_points m.(extend) m.(item_code) m.(rom_seed) all_items)
                d m.(extend_separates_on_the_chain) Hd).
  exact (distinct_separates Item item_eqb item_eqb_sound item_eqb_refl
           (fun i => m.(extend) d (m.(item_code) i)) all_items a b Hat
           (every_item_is_in_the_roster a) (every_item_is_in_the_roster b)
           Hne).
Qed.

(* C8 (R-05-058c): the hash-only assumption the machine declares, used
   rather than merely carried, so that a machine declaring nothing about its
   extension would fail to be a Machine at all. At any digest the
   specification chain extends from, substituting one item's measurement
   for another's moves the digest; the property is finite where the field
   is, so a real hash meets it (reading 7). *)
Theorem a_different_measurement_moves_the_digest :
  forall (m : Machine) (d : nat) (a b : Item),
    member Nat.eqb d (chain_extension_points m m.(rom_seed) boot_steps) = true ->
    item_eqb a b = false ->
    Nat.eqb (m.(extend) d (m.(item_code) a)) (m.(extend) d (m.(item_code) b))
    = false.
Proof.
  intros m d a b Hd Hne.
  rewrite (the_specification_chain_extends_from_the_declared_digests m) in Hd.
  exact (a_declared_digest_separates_the_items m d a b Hd Hne).
Qed.

(* A digest that folds in what the boot observed, which is what makes a
   reference value un-reproducible: the relying party regenerating the
   golden set from source reaches a different number than the device did.
   It is written to agree with the specification wherever nothing was
   observed rather than to differ everywhere, because a construction that
   moved the seed on the first attempt too would be refused by being a
   different fold and the runtime dependence would never be reached. It is
   also the harder defect: a device on its first attempt reproduces the
   golden value and only a retried boot diverges. *)
Definition attempt_folding_digest (m : Machine) : Digest m := fun o l =>
  match o with
  | 0 => digest_of m m.(rom_seed) l
  | S k => digest_of m (m.(extend) m.(rom_seed) (S k)) l
  end.

(* The twin, over an arbitrary machine and an arbitrary chain: the two folds
   agree at every chain where nothing was observed, so what refutes the
   construction is the dependence on the observation and not the fold. *)
Theorem the_attempt_folding_digest_agrees_where_nothing_was_observed :
  forall (m : Machine) (l : list Step),
    attempt_folding_digest m 0 l = spec_digest m 0 l.
Proof. intros m l. reflexivity. Qed.

(* =========================================================================
   The generated weakenings of the chain (R-05-166). A refutation is a
   seeded weakening the theorem must reject, so the four generators run over
   the two lists the specification is built from rather than over the
   assembled chain: a weakening of R-09-002's stage order and a weakening of
   the input prologue are two different findings, and only one of them is
   refused outright.
   ========================================================================= *)

Definition stage_weakenings : list (list Stage) :=
  app (transpositions all_stages)
      (app (deletions all_stages)
           (app (proper_suffixes all_stages)
                (duplications RotRuntime all_stages))).

(* Three transpositions, four deletions, four proper suffixes and five
   duplications, computed rather than claimed. *)
Example the_stage_family_size : count_of stage_weakenings = 16 := eq_refl.

(* C9: every weakening of R-09-002's stage order fails the chain check, as
   one conversion over the whole family. *)
Example every_stage_weakening_is_refused :
  all_of (fun w => negb (chain_ok (chain_from input_prologue w)))
         stage_weakenings = true := eq_refl.

(* And per family, so a family that stopped biting is visible rather than
   absorbed by the conjunction above. The attribution is stated as it is and
   not as a slogan: the transpositions fail the order check alone, because a
   transposed order still runs each stage once, and the other three fail the
   occurrence checks, because a stage the order dropped or repeated is both a
   stage that does not run once and an item that is not extended once. *)
Example every_stage_transposition_breaks_the_chain_order :
  all_of (fun w => negb (stages_in_chain_order (chain_from input_prologue w)
                                               all_stages))
         (transpositions all_stages) = true := eq_refl.

Example every_stage_transposition_still_runs_each_stage_once :
  all_of (fun w => every_stage_runs_once (chain_from input_prologue w))
         (transpositions all_stages) = true := eq_refl.

Example every_stage_deletion_leaves_a_stage_unrun :
  all_of (fun w => negb (every_stage_runs_once (chain_from input_prologue w)))
         (deletions all_stages) = true := eq_refl.

Example every_proper_suffix_leaves_a_stage_unrun :
  all_of (fun w => negb (every_stage_runs_once (chain_from input_prologue w)))
         (proper_suffixes all_stages) = true := eq_refl.

Example every_stage_duplication_runs_a_stage_twice :
  all_of (fun w => negb (every_stage_runs_once (chain_from input_prologue w)))
         (duplications RotRuntime all_stages) = true := eq_refl.

(* And the same three families read at the other occurrence check, which is
   the second conjunct they break: a stage the order dropped is an item the
   chain never extends, and a stage it repeats is one it extends twice. *)
Example every_stage_deletion_leaves_an_item_unextended :
  all_of (fun w => negb (every_input_extended_once (chain_from input_prologue w)))
         (app (deletions all_stages)
              (app (proper_suffixes all_stages)
                   (duplications RotRuntime all_stages))) = true := eq_refl.

(* C9a: the same content as a bounded quantifier over the index rather than
   an enumeration, so a family is refused for a reason rather than by a
   computation over the three, four, four and five members it happens to
   have. *)
Theorem no_transposition_of_the_stage_order_is_a_chain :
  forall n : nat, Nat.ltb n 3 = true ->
    chain_ok (chain_from input_prologue (swap_at n all_stages)) = false.
Proof.
  intros n. destruct n as [ | [ | [ | n ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_deletion_from_the_stage_order_is_a_chain :
  forall n : nat, Nat.ltb n 4 = true ->
    chain_ok (chain_from input_prologue (drop_at n all_stages)) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | n ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_proper_suffix_of_the_stage_order_is_a_chain :
  forall n : nat, Nat.ltb n 4 = true ->
    chain_ok (chain_from input_prologue (suffix_at (S n) all_stages)) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | n ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_duplication_in_the_stage_order_is_a_chain :
  forall n : nat, Nat.ltb n 5 = true ->
    chain_ok (chain_from input_prologue (insert_at n RotRuntime all_stages))
    = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | n ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* -------------------------------------------------------------------------
   The same four generators over the input prologue, where the answer is
   different and the difference is the finding. Gap a: R-09-037 fixes the
   lifecycle extension first and R-09-006a fixes the verdict before any
   measured stage draws, and no entry orders the verdict against R-09-029's
   boot-target latch, which that entry measures "like every other input"
   without saying where.
   ------------------------------------------------------------------------- *)

Definition prologue_weakenings : list (list Item) :=
  app (transpositions input_prologue)
      (app (deletions input_prologue)
           (app (proper_suffixes input_prologue)
                (duplications LifecycleFuse input_prologue))).

Example the_prologue_family_size : count_of prologue_weakenings = 12 := eq_refl.

(* C10: eleven of the twelve are refused, and the twelfth is gap a as a
   computation rather than as a remark. *)
Example eleven_of_the_twelve_prologue_weakenings_are_refused :
  count_of (filter_of (fun w => negb (chain_ok (chain_from w all_stages)))
                      prologue_weakenings) = 11 := eq_refl.

Example the_admitted_prologue_weakening_transposes_the_verdict :
  filter_of (fun w => chain_ok (chain_from w all_stages)) prologue_weakenings
  = cons (cons LifecycleFuse (cons BootTargetLatch
         (cons EntropyHealthVerdict nil))) nil := eq_refl.

(* C10a: as a bounded quantifier, with the free index named rather than
   silently skipped. Transposing the lifecycle extension with the verdict is
   refused; transposing the verdict with the latch is not. *)
Theorem transposing_the_lifecycle_extension_breaks_the_chain :
  chain_ok (chain_from (swap_at 0 input_prologue) all_stages) = false.
Proof. reflexivity. Qed.

Theorem transposing_the_verdict_with_the_latch_does_not :
  chain_ok (chain_from (swap_at 1 input_prologue) all_stages) = true.
Proof. reflexivity. Qed.

Theorem no_deletion_from_the_prologue_is_a_chain :
  forall n : nat, Nat.ltb n 3 = true ->
    chain_ok (chain_from (drop_at n input_prologue) all_stages) = false.
Proof.
  intros n. destruct n as [ | [ | [ | n ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_proper_suffix_of_the_prologue_is_a_chain :
  forall n : nat, Nat.ltb n 3 = true ->
    chain_ok (chain_from (suffix_at (S n) input_prologue) all_stages) = false.
Proof.
  intros n. destruct n as [ | [ | [ | n ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_duplication_in_the_prologue_is_a_chain :
  forall n : nat, Nat.ltb n 4 = true ->
    chain_ok (chain_from (insert_at n LifecycleFuse input_prologue) all_stages)
    = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | n ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* C10b: and this family is where `every_input_extended_once` bites on its
   own rather than beside a second conjunct. Each of the four extends the
   lifecycle fuse twice and leaves the other five conjuncts standing, so the
   occurrence check over the items is the whole of what refuses it, and the
   conjunct is visible here rather than only inside the conjunction. *)
Example every_prologue_duplication_extends_an_input_twice :
  all_of (fun w => negb (every_input_extended_once (chain_from w all_stages)))
         (duplications LifecycleFuse input_prologue) = true := eq_refl.

Example the_prologue_duplications_break_no_other_conjunct :
  all_of (fun w =>
            andb (lifecycle_extended_first (chain_from w all_stages))
            (andb (measured_before_run (chain_from w all_stages))
            (andb (every_stage_runs_once (chain_from w all_stages))
            (andb (stages_in_chain_order (chain_from w all_stages) all_stages)
                  (verdict_before_any_run (chain_from w all_stages))))))
         (duplications LifecycleFuse input_prologue) = true := eq_refl.

(* -------------------------------------------------------------------------
   Refutation witnesses over the chain that no index generates, each shown to
   satisfy the obligations it does not break, so that the named defect and
   not the construction's shape is what refuses it.
   ------------------------------------------------------------------------- *)

(* A chain that runs a stage it has not yet measured: the measurement is
   still taken, and it is taken after the stage executed. R-09-002's
   acceptance clause is the whole of what refuses it. *)
Definition unmeasured_run_chain : list Step :=
  app (map_over Extend input_prologue)
  (cons (Extend (StageMeasure RotRuntime)) (cons (Run RotRuntime)
  (cons (Run MModeImage) (cons (Extend (StageMeasure MModeImage))
  (cons (Extend (StageMeasure CoreKernels)) (cons (Run CoreKernels)
  (cons (Extend (StageMeasure StaticImage)) (cons (Run StaticImage) nil)))))))).

Theorem the_unmeasured_run_executes_before_it_records :
  lifecycle_extended_first unmeasured_run_chain = true
  /\ every_stage_runs_once unmeasured_run_chain = true
  /\ every_input_extended_once unmeasured_run_chain = true
  /\ stages_in_chain_order unmeasured_run_chain all_stages = true
  /\ verdict_before_any_run unmeasured_run_chain = true
  /\ measured_before_run unmeasured_run_chain = false.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; [ reflexivity |
    split; [ reflexivity | split; reflexivity ] ] ] ].
Qed.

(* A chain that extends the lifecycle state after the payload measurements
   have begun: R-09-037's *first extension* read as *some extension*, which
   is the reading that leaves a later measurement unbound to the state it
   ran under. *)
Definition late_lifecycle_chain : list Step :=
  cons (Extend EntropyHealthVerdict) (cons (Extend BootTargetLatch)
  (cons (Extend LifecycleFuse) (stage_chain all_stages))).

Theorem the_late_lifecycle_chain_extends_it_second :
  measured_before_run late_lifecycle_chain = true
  /\ every_stage_runs_once late_lifecycle_chain = true
  /\ every_input_extended_once late_lifecycle_chain = true
  /\ stages_in_chain_order late_lifecycle_chain all_stages = true
  /\ verdict_before_any_run late_lifecycle_chain = true
  /\ lifecycle_extended_first late_lifecycle_chain = false.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; [ reflexivity |
    split; [ reflexivity | split; reflexivity ] ] ] ].
Qed.

(* A chain that measures the start-up verdict last: the root's health is in
   the quote and the chain drew on it before the verdict was known, which is
   R-09-006a's own ordering read backwards and R-15-241b's degraded path
   arriving by a different route. *)
Definition blind_entropy_chain : list Step :=
  app (map_over Extend (cons LifecycleFuse (cons BootTargetLatch nil)))
      (app (stage_chain all_stages) (cons (Extend EntropyHealthVerdict) nil)).

Theorem the_blind_entropy_chain_draws_before_the_verdict :
  lifecycle_extended_first blind_entropy_chain = true
  /\ measured_before_run blind_entropy_chain = true
  /\ every_stage_runs_once blind_entropy_chain = true
  /\ every_input_extended_once blind_entropy_chain = true
  /\ stages_in_chain_order blind_entropy_chain all_stages = true
  /\ verdict_before_any_run blind_entropy_chain = false.
Proof.
  split; [ reflexivity | split; [ reflexivity | split; [ reflexivity |
    split; [ reflexivity | split; reflexivity ] ] ] ].
Qed.

(* Gap b as a construction rather than as a remark: a chain that measures
   the whole payload up front and then runs the four stages satisfies every
   obligation the register states, and the specification's chain measures
   each stage immediately before running it. R-09-002 fixes only the
   pairwise precedence, so both are admitted and the two differ observably. *)
Definition front_loaded_chain : list Step :=
  app (map_over Extend (app input_prologue (map_over StageMeasure all_stages)))
      (map_over Run all_stages).

Theorem the_front_loaded_chain_satisfies_every_stated_obligation :
  IsAMeasuredChain front_loaded_chain.
Proof. apply chain_ok_sound. reflexivity. Qed.

Theorem the_two_admitted_chain_shapes_differ :
  precedes step_eqb (Extend (StageMeasure StaticImage)) (Run RotRuntime)
           front_loaded_chain = true
  /\ precedes step_eqb (Extend (StageMeasure StaticImage)) (Run RotRuntime)
              boot_steps = false.
Proof. split; reflexivity. Qed.

(* =========================================================================
   Seal and unseal (R-09-008, R-12-014, R-15-079, R-09-023, R-09-006a).

   R-12-014 binds secrets to the RoT and the measured state and R-09-008
   puts seal, unseal and the quote on the RoT's TPM-functional surface. Four
   gates decide an unseal and each comes from its own entry (reading 5), so
   the four are stated apart. What an unseal returns is a handle and never a
   key (reading 6), which is a fifth obligation and is refuted by a
   construction that passes all four gates; so this section states five
   properties of an unseal, and each of the five is refuted by a
   construction that keeps the other four.
   ========================================================================= *)

Record Blob : Type := {
  bound_digest : nat;
  bound_state : Lifecycle;
  bound_root_version : nat;
  blob_handle : nat
}.

Definition Unseal (m : Machine) : Type := nat -> Blob -> Answer.

Definition unseal_admits (m : Machine) (d : nat) (b : Blob) : bool :=
  andb m.(entropy_ok)
  (andb (Nat.eqb d b.(bound_digest))
  (andb (lifecycle_eqb m.(state) b.(bound_state))
        (Nat.eqb (m.(counter) SealingRootVersion) b.(bound_root_version)))).

Definition spec_unseal (m : Machine) : Unseal m := fun d b =>
  if unseal_admits m d b then Handle b.(blob_handle) else Refused.

Definition spec_seal (m : Machine) (d h : nat) : Blob :=
  {| bound_digest := d;
     bound_state := m.(state);
     bound_root_version := m.(counter) SealingRootVersion;
     blob_handle := h |}.

(* R-12-014: secrets are bound to the measured state, so a machine whose
   chain reached a different digest holds no path to the material. *)
Definition BindsToTheMeasuredState (m : Machine) (u : Unseal m) : Prop :=
  forall (d : nat) (b : Blob),
    Nat.eqb d b.(bound_digest) = false -> u d b = Refused.

(* R-15-079: the RoT key hierarchy diversifies by lifecycle state, whose own
   acceptance clause is that a debuggable part cannot unseal
   production-sealed material. *)
Definition DiversifiesByLifecycle (m : Machine) (u : Unseal m) : Prop :=
  forall (d : nat) (b : Blob),
    lifecycle_eqb m.(state) b.(bound_state) = false -> u d b = Refused.

(* R-09-023 with R-10-013: the key-wrapping and sealing-root version is
   under the monotonic counter and advances on the duress erase and on key
   rotation, so material sealed under an earlier version stays sealed. *)
Definition RefusesPastTheSealingRoot (m : Machine) (u : Unseal m) : Prop :=
  forall (d : nat) (b : Blob),
    Nat.eqb (m.(counter) SealingRootVersion) b.(bound_root_version) = false ->
    u d b = Refused.

(* R-09-006a: on a failed start-up health test the RoT derives no key and
   unseals no material, and R-15-241b's fail-closed line is that no reduced
   rate, best-effort or last-known-good path exists. *)
Definition UnsealsNothingOnAFailedRoot (m : Machine) (u : Unseal m) : Prop :=
  m.(entropy_ok) = false -> forall (d : nat) (b : Blob), u d b = Refused.

(* R-12-014's criterion and R-12-015a's deletion of raw key export: what a
   holder gets back is a capability handle and never cleartext. *)
Definition ExportsNoKey (m : Machine) (u : Unseal m) : Prop :=
  forall (d : nat) (b : Blob), is_cleartext (u d b) = false.

(* S1 through S5 (R-12-014, R-15-079, R-09-023, R-09-006a). *)
Theorem the_specification_unseal_binds_to_the_measured_state :
  forall m : Machine, BindsToTheMeasuredState m (spec_unseal m).
Proof.
  intros m d b H. unfold spec_unseal, unseal_admits. rewrite H.
  destruct m.(entropy_ok); reflexivity.
Qed.

Theorem the_specification_unseal_diversifies_by_lifecycle :
  forall m : Machine, DiversifiesByLifecycle m (spec_unseal m).
Proof.
  intros m d b H. unfold spec_unseal, unseal_admits. rewrite H.
  destruct m.(entropy_ok); destruct (Nat.eqb d b.(bound_digest)); reflexivity.
Qed.

Theorem the_specification_unseal_refuses_past_the_sealing_root :
  forall m : Machine, RefusesPastTheSealingRoot m (spec_unseal m).
Proof.
  intros m d b H. unfold spec_unseal, unseal_admits. rewrite H.
  destruct m.(entropy_ok); destruct (Nat.eqb d b.(bound_digest));
    destruct (lifecycle_eqb m.(state) b.(bound_state)); reflexivity.
Qed.

Theorem the_specification_unseal_fails_closed_on_a_failed_root :
  forall m : Machine, UnsealsNothingOnAFailedRoot m (spec_unseal m).
Proof.
  intros m H d b. unfold spec_unseal, unseal_admits. rewrite H. reflexivity.
Qed.

Theorem the_specification_unseal_exports_no_key :
  forall m : Machine, ExportsNoKey m (spec_unseal m).
Proof.
  intros m d b. unfold spec_unseal. destruct (unseal_admits m d b); reflexivity.
Qed.

(* S6: and the round trip, so the five obligations above are not proved of a
   construction that refuses everything. A blob sealed at this digest, this
   state and this sealing root unseals here and hands back the handle it was
   sealed with. *)
Theorem a_blob_sealed_here_unseals_here :
  forall (m : Machine) (d h : nat),
    m.(entropy_ok) = true -> spec_unseal m d (spec_seal m d h) = Handle h.
Proof.
  intros m d h H. unfold spec_unseal, unseal_admits, spec_seal. simpl.
  rewrite H. rewrite nat_eqb_refl. rewrite lifecycle_eqb_refl.
  rewrite nat_eqb_refl. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Refutation witnesses over the unseal. Each drops exactly one gate and is
   shown to keep the other four, so the five are five obligations and not
   one stated five times.
   ------------------------------------------------------------------------- *)

(* An unseal that checks who is asking and not what ran: the lifecycle
   state, the sealing root and the entropy verdict all hold, and the
   measured state does not enter. R-12-014's *binding secrets to the RoT and
   measured state* is the whole of what refuses it. *)
Definition convenient_unseal (m : Machine) : Unseal m := fun _ b =>
  if andb m.(entropy_ok)
       (andb (lifecycle_eqb m.(state) b.(bound_state))
             (Nat.eqb (m.(counter) SealingRootVersion) b.(bound_root_version)))
  then Handle b.(blob_handle) else Refused.

Theorem the_convenient_unseal_keeps_the_other_four :
  forall m : Machine,
    DiversifiesByLifecycle m (convenient_unseal m)
    /\ RefusesPastTheSealingRoot m (convenient_unseal m)
    /\ UnsealsNothingOnAFailedRoot m (convenient_unseal m)
    /\ ExportsNoKey m (convenient_unseal m).
Proof.
  intros m. split; [ | split; [ | split ] ].
  - intros d b H. unfold convenient_unseal. rewrite H.
    destruct m.(entropy_ok); reflexivity.
  - intros d b H. unfold convenient_unseal. rewrite H.
    destruct m.(entropy_ok);
      destruct (lifecycle_eqb m.(state) b.(bound_state)); reflexivity.
  - intros H d b. unfold convenient_unseal. rewrite H. reflexivity.
  - intros d b. unfold convenient_unseal.
    destruct (andb m.(entropy_ok) _); reflexivity.
Qed.

(* An unseal that ignores the lifecycle state, which is the material a
   debuggable part must not reach (R-15-079). *)
Definition portable_unseal (m : Machine) : Unseal m := fun d b =>
  if andb m.(entropy_ok)
       (andb (Nat.eqb d b.(bound_digest))
             (Nat.eqb (m.(counter) SealingRootVersion) b.(bound_root_version)))
  then Handle b.(blob_handle) else Refused.

Theorem the_portable_unseal_keeps_the_other_four :
  forall m : Machine,
    BindsToTheMeasuredState m (portable_unseal m)
    /\ RefusesPastTheSealingRoot m (portable_unseal m)
    /\ UnsealsNothingOnAFailedRoot m (portable_unseal m)
    /\ ExportsNoKey m (portable_unseal m).
Proof.
  intros m. split; [ | split; [ | split ] ].
  - intros d b H. unfold portable_unseal. rewrite H.
    destruct m.(entropy_ok); reflexivity.
  - intros d b H. unfold portable_unseal. rewrite H.
    destruct m.(entropy_ok); destruct (Nat.eqb d b.(bound_digest)); reflexivity.
  - intros H d b. unfold portable_unseal. rewrite H. reflexivity.
  - intros d b. unfold portable_unseal.
    destruct (andb m.(entropy_ok) _); reflexivity.
Qed.

(* An unseal that ignores the sealing-root version, so a duress erase or a
   key rotation leaves the old material reachable: R-09-023's one-way,
   non-rollbackable erase undone by the service that was supposed to enact
   it. *)
Definition stale_unseal (m : Machine) : Unseal m := fun d b =>
  if andb m.(entropy_ok)
       (andb (Nat.eqb d b.(bound_digest))
             (lifecycle_eqb m.(state) b.(bound_state)))
  then Handle b.(blob_handle) else Refused.

Theorem the_stale_unseal_keeps_the_other_four :
  forall m : Machine,
    BindsToTheMeasuredState m (stale_unseal m)
    /\ DiversifiesByLifecycle m (stale_unseal m)
    /\ UnsealsNothingOnAFailedRoot m (stale_unseal m)
    /\ ExportsNoKey m (stale_unseal m).
Proof.
  intros m. split; [ | split; [ | split ] ].
  - intros d b H. unfold stale_unseal. rewrite H.
    destruct m.(entropy_ok); reflexivity.
  - intros d b H. unfold stale_unseal. rewrite H.
    destruct m.(entropy_ok); destruct (Nat.eqb d b.(bound_digest)); reflexivity.
  - intros H d b. unfold stale_unseal. rewrite H. reflexivity.
  - intros d b. unfold stale_unseal.
    destruct (andb m.(entropy_ok) _); reflexivity.
Qed.

(* An unseal that carries on over a failed start-up health test, which is
   the degraded path R-15-241b's criterion says exists in neither hardware
   nor firmware. *)
Definition best_effort_unseal (m : Machine) : Unseal m := fun d b =>
  if andb (Nat.eqb d b.(bound_digest))
       (andb (lifecycle_eqb m.(state) b.(bound_state))
             (Nat.eqb (m.(counter) SealingRootVersion) b.(bound_root_version)))
  then Handle b.(blob_handle) else Refused.

Theorem the_best_effort_unseal_keeps_the_other_four :
  forall m : Machine,
    BindsToTheMeasuredState m (best_effort_unseal m)
    /\ DiversifiesByLifecycle m (best_effort_unseal m)
    /\ RefusesPastTheSealingRoot m (best_effort_unseal m)
    /\ ExportsNoKey m (best_effort_unseal m).
Proof.
  intros m. split; [ | split; [ | split ] ].
  - intros d b H. unfold best_effort_unseal. rewrite H. reflexivity.
  - intros d b H. unfold best_effort_unseal. rewrite H.
    destruct (Nat.eqb d b.(bound_digest)); reflexivity.
  - intros d b H. unfold best_effort_unseal. rewrite H.
    destruct (Nat.eqb d b.(bound_digest));
      destruct (lifecycle_eqb m.(state) b.(bound_state)); reflexivity.
  - intros d b. unfold best_effort_unseal.
    destruct (andb (Nat.eqb d b.(bound_digest)) _); reflexivity.
Qed.

(* An unseal that passes every gate and hands back the key: R-12-015a's raw
   key export, which is the operation that entry says is absent. It is the
   construction that shows the four gates do not carry the fifth
   obligation. *)
Definition exporting_unseal (m : Machine) : Unseal m := fun d b =>
  if unseal_admits m d b then Cleartext b.(blob_handle) else Refused.

Theorem the_exporting_unseal_keeps_all_four_gates :
  forall m : Machine,
    BindsToTheMeasuredState m (exporting_unseal m)
    /\ DiversifiesByLifecycle m (exporting_unseal m)
    /\ RefusesPastTheSealingRoot m (exporting_unseal m)
    /\ UnsealsNothingOnAFailedRoot m (exporting_unseal m).
Proof.
  intros m. split; [ | split; [ | split ] ].
  - intros d b H. unfold exporting_unseal, unseal_admits. rewrite H.
    destruct m.(entropy_ok); reflexivity.
  - intros d b H. unfold exporting_unseal, unseal_admits. rewrite H.
    destruct m.(entropy_ok); destruct (Nat.eqb d b.(bound_digest)); reflexivity.
  - intros d b H. unfold exporting_unseal, unseal_admits. rewrite H.
    destruct m.(entropy_ok); destruct (Nat.eqb d b.(bound_digest));
      destruct (lifecycle_eqb m.(state) b.(bound_state)); reflexivity.
  - intros H d b. unfold exporting_unseal, unseal_admits. rewrite H.
    reflexivity.
Qed.

Theorem the_exporting_unseal_is_refuted :
  forall m : Machine,
    m.(entropy_ok) = true -> ~ ExportsNoKey m (exporting_unseal m).
Proof.
  intros m H C.
  specialize (C (m.(counter) SealingRootVersion)
                {| bound_digest := m.(counter) SealingRootVersion;
                   bound_state := m.(state);
                   bound_root_version := m.(counter) SealingRootVersion;
                   blob_handle := 0 |}).
  unfold exporting_unseal, unseal_admits in C. simpl in C.
  rewrite H in C. rewrite nat_eqb_refl in C. rewrite lifecycle_eqb_refl in C.
  simpl in C. discriminate C.
Qed.

(* =========================================================================
   The attestation quote and its reference dual (R-09-025, R-09-026,
   R-09-037, R-12-015, R-09-006a).

   R-09-025's acceptance clause is that the quote's vector is *exactly* this
   set, which cuts in two directions and is refuted in both: a quote that
   drops a term and a quote that adds one are each refused, and the term the
   widening family adds is the one R-09-037 keeps out by name. The vector is
   a set and not an order (reading 3), which is computed rather than assumed.
   ========================================================================= *)

Definition quote_vector : list Field :=
  cons ChainDigest (cons CheckerVersion (cons SpecAndPolicySet
  (cons IsaProfileVersion (cons RadioGenerationIdentity nil)))).

Example the_vector_carries_five_terms : count_of quote_vector = 5 := eq_refl.

Example the_vector_excludes_the_lifecycle_fuse :
  member field_eqb LifecycleFuseValue quote_vector = false
  /\ member field_eqb ChainDigest quote_vector = true := conj eq_refl eq_refl.

(* Term by term rather than as a set difference, so a term admitted where
   the register excludes it is one moved conversion. *)
Definition covers_exactly (v : list Field) : bool :=
  all_of (fun f => Nat.eqb (occurrences field_eqb f v)
                           (occurrences field_eqb f quote_vector))
         all_fields.

Definition Quote (m : Machine) : Type := option (list Field).

Definition spec_quote (m : Machine) : Quote m :=
  if m.(entropy_ok) then Some quote_vector else None.

Definition CoversTheVectorExactly (m : Machine) (q : Quote m) : Prop :=
  forall v : list Field, q = Some v -> covers_exactly v = true.

(* R-09-006a: on a failed start-up health test the RoT completes no
   attestation quote. *)
Definition CompletesNoQuoteOnAFailedRoot (m : Machine) (q : Quote m) : Prop :=
  m.(entropy_ok) = false -> q = None.

(* Q1 (R-09-025, R-09-037). *)
Theorem the_specification_quote_covers_the_vector_exactly :
  forall m : Machine, CoversTheVectorExactly m (spec_quote m).
Proof.
  intros m v H. unfold spec_quote in H. destruct m.(entropy_ok).
  - injection H as H. rewrite <- H. reflexivity.
  - discriminate H.
Qed.

(* Q2 (R-09-006a). *)
Theorem the_specification_quote_completes_nothing_on_a_failed_root :
  forall m : Machine, CompletesNoQuoteOnAFailedRoot m (spec_quote m).
Proof. intros m H. unfold spec_quote. rewrite H. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The generated weakenings of the vector. Deletions, widenings by the term
   R-09-037 excludes, and duplications: seventeen members, every one
   refused. The transpositions are generated separately and admitted,
   because reading 3 takes R-09-025's own word *set*.
   ------------------------------------------------------------------------- *)

Definition vector_weakenings : list (list Field) :=
  app (deletions quote_vector)
      (app (duplications LifecycleFuseValue quote_vector)
           (duplications ChainDigest quote_vector)).

Example the_vector_family_size : count_of vector_weakenings = 17 := eq_refl.

(* Q3: every weakening of the vector fails the coverage check, as one
   conversion over the whole family. *)
Example every_vector_weakening_is_refused :
  all_of (fun v => negb (covers_exactly v)) vector_weakenings = true := eq_refl.

Example every_vector_deletion_drops_a_term :
  all_of (fun v => negb (covers_exactly v)) (deletions quote_vector)
  = true := eq_refl.

Example every_widening_adds_the_term_the_chain_already_carries :
  all_of (fun v => negb (covers_exactly v))
         (duplications LifecycleFuseValue quote_vector) = true := eq_refl.

Example every_duplication_states_a_term_twice :
  all_of (fun v => negb (covers_exactly v))
         (duplications ChainDigest quote_vector) = true := eq_refl.

(* Reading 3 as a computation: the four adjacent transpositions of the
   vector each cover exactly, so R-09-025 fixes a set and not an order, and
   this file states that rather than assuming it. *)
Example the_vector_is_a_set_and_not_an_order :
  all_of covers_exactly (transpositions quote_vector) = true := eq_refl.

Example there_are_four_vector_transpositions :
  count_of (transpositions quote_vector) = 4 := eq_refl.

(* Q3a: the same content as bounded quantifiers over the index. *)
Theorem no_deletion_from_the_vector_covers_it :
  forall n : nat, Nat.ltb n 5 = true ->
    covers_exactly (drop_at n quote_vector) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | n ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_widening_of_the_vector_covers_it :
  forall n : nat, Nat.ltb n 6 = true ->
    covers_exactly (insert_at n LifecycleFuseValue quote_vector) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

Theorem no_duplication_in_the_vector_covers_it :
  forall n : nat, Nat.ltb n 6 = true ->
    covers_exactly (insert_at n ChainDigest quote_vector) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* -------------------------------------------------------------------------
   Refutation witnesses over the quote that no index generates.
   ------------------------------------------------------------------------- *)

(* A quote that carries the lifecycle fuse value as a term of its own, which
   is the widening R-09-037 refuses in as many words: the state enters as a
   chain measurement and R-09-025's vector is not widened by it. *)
Definition widened_quote (m : Machine) : Quote m :=
  if m.(entropy_ok) then Some (cons LifecycleFuseValue quote_vector) else None.

Theorem the_widened_quote_still_fails_closed :
  forall m : Machine, CompletesNoQuoteOnAFailedRoot m (widened_quote m).
Proof. intros m H. unfold widened_quote. rewrite H. reflexivity. Qed.

(* A quote completed whatever the root did, which is the clause R-09-006a
   states beside the two about keys: no attestation quote is completed on a
   failed start-up health test. *)
Definition best_effort_quote (m : Machine) : Quote m := Some quote_vector.

Theorem the_best_effort_quote_covers_the_vector_exactly :
  forall m : Machine, CoversTheVectorExactly m (best_effort_quote m).
Proof.
  intros m v H. unfold best_effort_quote in H. injection H as H.
  rewrite <- H. reflexivity.
Qed.

(* =========================================================================
   Appraisal (R-09-026, R-12-015).

   R-09-026 makes the reference integrity manifest the reference-value dual
   of the quote over the same vector, and R-12-015 has a relying party
   appraise a quote against it with no vendor-side golden database. The
   appraisal is stated over an arbitrary covered vector for that reason
   (gap f), and the join below is what makes the appraisal decide the chain
   rather than four fields beside it.
   ========================================================================= *)

Definition Appraisal (m : Machine) : Type := list Field -> bool.

Definition spec_appraise (m : Machine) : Appraisal m := fun v =>
  all_of (fun f => Nat.eqb (m.(witness) f) (m.(reference) f)) v.

Definition AppraisesEveryCoveredTerm (m : Machine) (ap : Appraisal m) : Prop :=
  forall (v : list Field) (f : Field),
    ap v = true -> member field_eqb f v = true ->
    Nat.eqb (m.(witness) f) (m.(reference) f) = true.

(* A1 (R-12-015). *)
Theorem the_specification_appraisal_reaches_every_covered_term :
  forall m : Machine, AppraisesEveryCoveredTerm m (spec_appraise m).
Proof.
  intros m v f Ha Hm.
  exact (all_of_member Field field_eqb field_eqb_sound _ v f Ha Hm).
Qed.

Lemma occurrences_gives_member :
  forall (A : Type) (eqb : A -> A -> bool) (x : A) (l : list A) (k : nat),
    occurrences eqb x l = S k -> member eqb x l = true.
Proof.
  intros A eqb x l. induction l as [ | y r IH ]; intros k F.
  - discriminate F.
  - unfold member. simpl. simpl in F. destruct (eqb x y).
    + reflexivity.
    + simpl. exact (IH k F).
Qed.

Lemma a_covered_vector_carries_the_chain :
  forall v : list Field,
    covers_exactly v = true -> member field_eqb ChainDigest v = true.
Proof.
  intros v H.
  assert (E : Nat.eqb (occurrences field_eqb ChainDigest v)
                      (occurrences field_eqb ChainDigest quote_vector) = true)
    by exact (all_of_fields _ ChainDigest H).
  destruct (occurrences field_eqb ChainDigest v) as [ | k ] eqn:F.
  - simpl in E. discriminate E.
  - exact (occurrences_gives_member Field field_eqb ChainDigest v k F).
Qed.

(* A2, the second join (R-09-025 with R-09-026 through R-12-015): a relying
   party's appraisal decides the chain, and it decides it because the vector
   the quote covers is the one R-09-025 fixes. Stated of an arbitrary
   appraisal reaching every covered term, because the join is a property of
   the vector R-09-025 closes and not of this file's appraisal: any relying
   party whose appraisal is sound over what it covers gets the chain with
   it. The construction beside it is what the narrower reading of that
   entry's "this set" would let past. *)
Theorem an_appraisal_over_a_covered_vector_decides_the_chain :
  forall (m : Machine) (ap : Appraisal m) (v : list Field),
    AppraisesEveryCoveredTerm m ap ->
    covers_exactly v = true -> ap v = true ->
    Nat.eqb (m.(witness) ChainDigest) (m.(reference) ChainDigest) = true.
Proof.
  intros m ap v Hap Hc Ha.
  exact (Hap v ChainDigest Ha (a_covered_vector_carries_the_chain v Hc)).
Qed.

(* And at the specification, which is the instance the demo machines below
   compute against. *)
Theorem the_specification_appraisal_over_a_covered_vector_decides_the_chain :
  forall (m : Machine) (v : list Field),
    covers_exactly v = true -> spec_appraise m v = true ->
    Nat.eqb (m.(witness) ChainDigest) (m.(reference) ChainDigest) = true.
Proof.
  intros m v Hc Ha.
  exact (an_appraisal_over_a_covered_vector_decides_the_chain m
           (spec_appraise m) v
           (the_specification_appraisal_reaches_every_covered_term m) Hc Ha).
Qed.

(* An appraisal that skips the chain term and checks the four
   admission-discipline terms beside it, which is R-09-025's acceptance
   clause read as covering the discipline alone. *)
Definition lenient_appraise (m : Machine) : Appraisal m := fun v =>
  all_of (fun f => only_if (negb (field_eqb f ChainDigest))
                           (Nat.eqb (m.(witness) f) (m.(reference) f)))
         v.

(* It reaches every other term, so what refuses it is the term it skips and
   not a weaker check. *)
Theorem the_lenient_appraisal_still_reaches_the_other_terms :
  forall (m : Machine) (v : list Field) (f : Field),
    lenient_appraise m v = true -> member field_eqb f v = true ->
    field_eqb f ChainDigest = false ->
    Nat.eqb (m.(witness) f) (m.(reference) f) = true.
Proof.
  intros m v f Ha Hm Hne.
  assert (E : only_if (negb (field_eqb f ChainDigest))
                      (Nat.eqb (m.(witness) f) (m.(reference) f)) = true)
    by exact (all_of_member Field field_eqb field_eqb_sound _ v f Ha Hm).
  rewrite Hne in E. simpl in E. exact E.
Qed.

(* =========================================================================
   Anti-rollback (R-09-028, R-09-030, R-10-013, R-10-011, R-12-017).

   Three mechanisms and not one (reading 8): the monotone security-version
   floor, the four monotonic counters with the events R-10-013 and R-09-023
   pair them with, and the boot-attempt count with R-09-028's automatic
   revert. Each is stated apart and each has a construction satisfying the
   others and breaking it.
   ========================================================================= *)

(* R-09-030: any retained generation at or above the floor may be selected,
   while generations below it stay visible and diffable and are not
   bootable. The boundary is the entry's own word *at*, so the check is
   inclusive and the strict reading below is refuted rather than preferred. *)
Definition bootable (m : Machine) (v : nat) : bool :=
  Nat.leb m.(rollback_floor) v.

Definition Selection (m : Machine) : Type := nat -> bool.

Definition NothingBelowTheFloorBoots (m : Machine) (sel : Selection m) : Prop :=
  forall v : nat, sel v = true -> Nat.leb m.(rollback_floor) v = true.

Definition TheFloorItselfBoots (m : Machine) (sel : Selection m) : Prop :=
  sel m.(rollback_floor) = true.

(* R1 and R2 (R-09-030): the two halves of *at or above*, stated apart
   because one construction satisfies either and fails the other. *)
Theorem the_specification_selection_refuses_below_the_floor :
  forall m : Machine, NothingBelowTheFloorBoots m (bootable m).
Proof. intros m v H. exact H. Qed.

Theorem the_specification_selection_admits_the_floor_itself :
  forall m : Machine, TheFloorItselfBoots m (bootable m).
Proof. intros m. unfold bootable. exact (nat_leb_refl m.(rollback_floor)). Qed.

(* The strict reading, which refuses the generation the floor itself names:
   R-09-030 says *at or above*, so this is a construction the entry's own
   word excludes rather than a stricter policy it permits. *)
Definition strictly_above (m : Machine) : Selection m := fun v =>
  Nat.ltb m.(rollback_floor) v.

Lemma nat_ltb_gives_leb :
  forall a b : nat, Nat.ltb a b = true -> Nat.leb a b = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b H.
  - reflexivity.
  - destruct b as [ | y ]; [ discriminate H | ]. simpl in H. simpl.
    exact (IH y H).
Qed.

Theorem the_strict_reading_still_refuses_below_the_floor :
  forall m : Machine, NothingBelowTheFloorBoots m (strictly_above m).
Proof.
  intros m v H. unfold strictly_above in H. exact (nat_ltb_gives_leb _ _ H).
Qed.

(* A selection that treats history as a bootable set, which is R-09-030's
   own distinction between visible-and-diffable and bootable. *)
Definition visible_is_bootable (m : Machine) : Selection m := fun _ => true.

Theorem the_visible_is_bootable_selection_admits_the_floor :
  forall m : Machine, TheFloorItselfBoots m (visible_is_bootable m).
Proof. intros m. reflexivity. Qed.

(* R-09-028's floor advance. The floor moves on a signed security update and
   never down, which is what makes booting a below-floor generation
   un-fixing a shipped security update rather than a preference. *)
Definition Floor : Type := nat -> nat -> nat.

Definition spec_floor : Floor := fun current declared =>
  if Nat.ltb current declared then declared else current.

Definition NeverDescends (f : Floor) : Prop :=
  forall current declared : nat, Nat.leb current (f current declared) = true.

Definition ReachesTheDeclaredFloor (f : Floor) : Prop :=
  forall current declared : nat,
    Nat.leb current declared = true -> Nat.leb declared (f current declared) = true.

Lemma nat_ltb_false_gives_leb :
  forall a b : nat, Nat.ltb a b = false -> Nat.leb b a = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b H.
  - destruct b as [ | y ]; [ reflexivity | discriminate H ].
  - destruct b as [ | y ]; [ reflexivity | ]. simpl. simpl in H. exact (IH y H).
Qed.

(* R3 and R4 (R-09-028). *)
Theorem the_specification_floor_never_descends : NeverDescends spec_floor.
Proof.
  intros current declared. unfold spec_floor.
  destruct (Nat.ltb current declared) eqn:E.
  - exact (nat_ltb_gives_leb _ _ E).
  - exact (nat_leb_refl current).
Qed.

Theorem the_specification_floor_reaches_the_declared_value :
  ReachesTheDeclaredFloor spec_floor.
Proof.
  intros current declared H. unfold spec_floor.
  destruct (Nat.ltb current declared) eqn:E.
  - exact (nat_leb_refl declared).
  - assert (K : Nat.leb declared current = true) by exact (nat_ltb_false_gives_leb _ _ E).
    exact K.
Qed.

(* A floor that takes the image's own declared value, which is the
   construction that lets a signed but older generation move the floor back
   down and re-open what a security update fixed. *)
Definition trusting_floor : Floor := fun _ declared => declared.

Theorem the_trusting_floor_still_reaches_the_declared_value :
  ReachesTheDeclaredFloor trusting_floor.
Proof. intros current declared H. unfold trusting_floor. exact (nat_leb_refl declared). Qed.

Theorem the_trusting_floor_descends : ~ NeverDescends trusting_floor.
Proof. intros H. specialize (H 1 0). discriminate H. Qed.

(* A floor that never moves at all, which keeps the monotonicity and loses
   the update: the two obligations are separate, and this is the
   construction that shows it. *)
Definition frozen_floor : Floor := fun current _ => current.

Theorem the_frozen_floor_never_descends : NeverDescends frozen_floor.
Proof. intros current declared. unfold frozen_floor. exact (nat_leb_refl current). Qed.

Theorem the_frozen_floor_never_reaches_the_declared_value :
  ~ ReachesTheDeclaredFloor frozen_floor.
Proof. intros H. specialize (H 0 1 eq_refl). discriminate H. Qed.

(* And a third, which is what makes the boundary of R-09-030's *at or above*
   an obligation rather than a convention: a floor that advances on a
   strictly newer generation and forgets the one it already holds satisfies
   the advance and loses the floor at equality, which is where a generation
   re-installed at its own security version un-fixes a shipped update. *)
Definition forgetful_floor : Floor := fun current declared =>
  if Nat.ltb current declared then declared else 0.

Theorem the_forgetful_floor_reaches_a_strictly_newer_value :
  forall current declared : nat,
    Nat.ltb current declared = true ->
    Nat.leb declared (forgetful_floor current declared) = true.
Proof.
  intros current declared H. unfold forgetful_floor. rewrite H.
  exact (nat_leb_refl declared).
Qed.

Theorem the_forgetful_floor_loses_the_floor_it_holds :
  ~ ReachesTheDeclaredFloor forgetful_floor.
Proof. intros H. specialize (H 1 1 eq_refl). discriminate H. Qed.

Theorem the_forgetful_floor_descends : ~ NeverDescends forgetful_floor.
Proof. intros H. specialize (H 1 1). discriminate H. Qed.

(* -------------------------------------------------------------------------
   The four counters and the events they advance on (R-10-013, R-09-023,
   R-10-011, R-12-017). The table below is R-10-013's own sentence with
   R-09-023's conferral beside it, written out once.
   ------------------------------------------------------------------------- *)

Definition advances_on (c : Counter) (e : Event) : bool :=
  match c, e with
  | SecurityVersionFloor, SignedUpdate => true
  | SealingRootVersion, KeyRotation => true
  | SealingRootVersion, DuressErase => true
  | CredentialAttemptCounter, AuthAttempt => true
  | FreshnessEpochRoot, SealedEpoch => true
  | _, _ => false
  end.

(* The whole table, computed rather than described, so a pairing edited on
   one side of the file and read on the other is a failed conversion instead
   of a silent disagreement. *)
Example the_counter_event_table :
  map_over (fun c => map_over (advances_on c) all_events) all_counters
  = cons (cons true (cons false (cons false (cons false (cons false
         (cons false nil))))))
    (cons (cons false (cons true (cons true (cons false (cons false
         (cons false nil))))))
    (cons (cons false (cons false (cons false (cons true (cons false
         (cons false nil))))))
    (cons (cons false (cons false (cons false (cons false (cons true
         (cons false nil)))))) nil))) := eq_refl.

Definition Advancement : Type := Counter -> Event -> bool.

(* R-10-013's own exclusion, which is what R-10-011 raises against sealing
   the mutable volume root: no OTP or hardware monotonic counter sustains a
   commit-frequency advance. *)
Definition NeverOnADataCommit (adv : Advancement) : Prop :=
  all_of (fun c => negb (adv c DataCommit)) all_counters = true.

(* And no member of the enumeration is dead: R-10-013a admits a member only
   against a requirement that confers it, so a counter nothing advances is a
   budget spent by nobody. *)
Definition EveryCounterAdvancesOnSomething (adv : Advancement) : Prop :=
  all_of (fun c => any_of (adv c) all_events) all_counters = true.

(* R5 and R6 (R-10-013, R-10-013a). *)
Theorem the_specification_advancement_spares_the_data_commit :
  NeverOnADataCommit advances_on.
Proof. reflexivity. Qed.

Theorem the_specification_advancement_leaves_no_counter_dead :
  EveryCounterAdvancesOnSomething advances_on.
Proof. reflexivity. Qed.

(* R7: and read at an arbitrary counter rather than only over the roster,
   so the obligation is about the enumeration and not about the list's
   order. *)
Theorem no_counter_of_the_enumeration_advances_on_a_data_commit :
  forall c : Counter, advances_on c DataCommit = false.
Proof.
  intros c.
  assert (E : negb (advances_on c DataCommit) = true)
    by exact (all_of_counters _ c the_specification_advancement_spares_the_data_commit).
  destruct (advances_on c DataCommit); [ discriminate E | reflexivity ].
Qed.

(* The construction R-10-011 names: the freshness epoch root advanced once
   per data commit rather than once per sealed epoch, which spends the
   counter at CoW-commit frequency. It leaves no counter dead, so the named
   defect and not the shape of the table is what refuses it. *)
Definition commit_advancing (c : Counter) (e : Event) : bool :=
  orb (advances_on c e)
      (match c, e with FreshnessEpochRoot, DataCommit => true | _, _ => false end).

(* Its own table beside the specification's, so that the construction is one
   cell away from the specification rather than a different table: the day
   it stops being one cell away is the day this conversion moves. *)
Example the_commit_advancing_table :
  map_over (fun c => map_over (commit_advancing c) all_events) all_counters
  = cons (cons true (cons false (cons false (cons false (cons false
         (cons false nil))))))
    (cons (cons false (cons true (cons true (cons false (cons false
         (cons false nil))))))
    (cons (cons false (cons false (cons false (cons true (cons false
         (cons false nil))))))
    (cons (cons false (cons false (cons false (cons false (cons true
         (cons true nil)))))) nil))) := eq_refl.

Theorem the_commit_advancing_table_leaves_no_counter_dead :
  EveryCounterAdvancesOnSomething commit_advancing.
Proof. reflexivity. Qed.

Theorem the_commit_advancing_table_spends_the_counter_on_a_commit :
  ~ NeverOnADataCommit commit_advancing.
Proof. intros H. discriminate H. Qed.

(* And the other way: a table that spares the data commit and leaves the
   credential attempt counter dead, which is the offline brute force
   R-12-017 exists to refuse. *)
Definition dead_attempt_counter (c : Counter) (e : Event) : bool :=
  match c with
  | CredentialAttemptCounter => false
  | _ => advances_on c e
  end.

Example the_dead_attempt_counter_table :
  map_over (fun c => map_over (dead_attempt_counter c) all_events) all_counters
  = cons (cons true (cons false (cons false (cons false (cons false
         (cons false nil))))))
    (cons (cons false (cons true (cons true (cons false (cons false
         (cons false nil))))))
    (cons (cons false (cons false (cons false (cons false (cons false
         (cons false nil))))))
    (cons (cons false (cons false (cons false (cons false (cons true
         (cons false nil)))))) nil))) := eq_refl.

Theorem the_dead_attempt_counter_spares_the_data_commit :
  NeverOnADataCommit dead_attempt_counter.
Proof. reflexivity. Qed.

Theorem the_dead_attempt_counter_is_dead :
  ~ EveryCounterAdvancesOnSomething dead_attempt_counter.
Proof. intros H. discriminate H. Qed.

(* -------------------------------------------------------------------------
   Boot counting and the automatic revert (R-09-028, R-09-006a).
   ------------------------------------------------------------------------- *)

Definition BootAdmission (m : Machine) : Type := nat -> bool.

Definition spec_boot_admits (m : Machine) : BootAdmission m := fun n =>
  Nat.ltb n m.(boot_bound).

Definition RevertsPastTheBound (m : Machine) (adm : BootAdmission m) : Prop :=
  forall n : nat, Nat.ltb n m.(boot_bound) = false -> adm n = false.

(* And the admitting direction, on the floor's own pattern: R-09-028 counts
   boots so that the bound is where the revert happens, which says as much
   about the attempts below it as about the ones past it. Without this half
   an admission that admits nothing discharges the counting obligation, and
   a device that never boots is not what an automatic revert buys. *)
Definition AdmitsBelowTheBound (m : Machine) (adm : BootAdmission m) : Prop :=
  forall n : nat, Nat.ltb n m.(boot_bound) = true -> adm n = true.

(* R8 and R8a (R-09-028), stated apart because one construction satisfies
   either and fails the other. *)
Theorem the_specification_boot_admission_reverts_past_the_bound :
  forall m : Machine, RevertsPastTheBound m (spec_boot_admits m).
Proof. intros m n H. exact H. Qed.

Theorem the_specification_boot_admission_admits_below_the_bound :
  forall m : Machine, AdmitsBelowTheBound m (spec_boot_admits m).
Proof. intros m n H. exact H. Qed.

(* A boot admission with no count, which is the reset loop R-09-028's
   automatic revert exists to break. It admits every attempt below the bound
   as well, so what refuses it is the attempt past the bound and not a
   generally wider admission. *)
Definition unbounded_boot (m : Machine) : BootAdmission m := fun _ => true.

Theorem the_unbounded_boot_still_admits_below_the_bound :
  forall m : Machine, AdmitsBelowTheBound m (unbounded_boot m).
Proof. intros m n H. reflexivity. Qed.

(* And the other way: an admission that admits nothing reverts past the
   bound vacuously and boots no attempt at all, which is the half a
   single-sided statement of R-09-028's counting would leave standing. *)
Definition refusing_boot (m : Machine) : BootAdmission m := fun _ => false.

Theorem the_refusing_boot_reverts_past_the_bound :
  forall m : Machine, RevertsPastTheBound m (refusing_boot m).
Proof. intros m n H. reflexivity. Qed.

(* R-09-006a: the entropy halt is a §16 fault class and not a boot-counting
   event, so the automatic revert is not its response and it consumes no
   attempt. The outcome enumeration is that entry's own two failure classes
   (reading 9); gap c records that a success is not modelled. *)
Definition Charge : Type := Outcome -> nat -> nat.

Definition spec_charge : Charge := fun o n =>
  match o with EntropyHalt => n | OrdinaryFailure => S n end.

Definition SpendsNoAttemptOnTheEntropyHalt (ch : Charge) : Prop :=
  forall n : nat, ch EntropyHalt n = n.

Definition ChargesTheOrdinaryFailure (ch : Charge) : Prop :=
  forall n : nat, Nat.ltb n (ch OrdinaryFailure n) = true.

(* R9 and R10 (R-09-006a, R-09-028), stated apart because one construction
   satisfies either and fails the other. *)
Theorem the_specification_charge_spares_the_entropy_halt :
  SpendsNoAttemptOnTheEntropyHalt spec_charge.
Proof. intros n. reflexivity. Qed.

Theorem the_specification_charge_spends_on_the_ordinary_failure :
  ChargesTheOrdinaryFailure spec_charge.
Proof.
  intros n. simpl. induction n as [ | k IH ]; [ reflexivity | simpl ]. exact IH.
Qed.

(* A boot counter that charges every failure, so a device whose entropy root
   latched off spends its attempts and takes the automatic revert, which is
   the response R-09-006a says this stop does not have. *)
Definition uniform_charge : Charge := fun _ n => S n.

Theorem the_uniform_charge_still_spends_on_the_ordinary_failure :
  ChargesTheOrdinaryFailure uniform_charge.
Proof.
  intros n. unfold uniform_charge. simpl.
  induction n as [ | k IH ]; [ reflexivity | simpl ]. exact IH.
Qed.

Theorem the_uniform_charge_spends_on_the_entropy_halt :
  ~ SpendsNoAttemptOnTheEntropyHalt uniform_charge.
Proof. intros H. specialize (H 0). discriminate H. Qed.

(* And the other way: a counter that charges nothing keeps R-09-006a's
   carve-out and loses R-09-028's counting, so the two are two obligations. *)
Definition forgiving_charge : Charge := fun _ n => n.

Theorem the_forgiving_charge_spares_the_entropy_halt :
  SpendsNoAttemptOnTheEntropyHalt forgiving_charge.
Proof. intros n. reflexivity. Qed.

Theorem the_forgiving_charge_counts_nothing :
  ~ ChargesTheOrdinaryFailure forgiving_charge.
Proof. intros H. specialize (H 0). discriminate H. Qed.

(* R-09-028's A/B revert, which is what the count is counted for. *)
Definition Revert : Type := Slot -> Slot.

Definition spec_revert : Revert := fun s =>
  match s with SlotA => SlotB | SlotB => SlotA end.

Definition RevertsToTheOtherSlot (rv : Revert) : Prop :=
  forall s : Slot, rv s <> s.

Definition IsAnInvolution (rv : Revert) : Prop :=
  forall s : Slot, rv (rv s) = s.

(* R11 and R12 (R-09-028). *)
Theorem the_specification_revert_reaches_the_other_slot :
  RevertsToTheOtherSlot spec_revert.
Proof. intros s. destruct s; discriminate. Qed.

Theorem the_specification_revert_is_an_involution : IsAnInvolution spec_revert.
Proof. intros s. destruct s; reflexivity. Qed.

(* Over R-09-028's two slots the first obligation carries the second, which
   is proved rather than assumed, and the converse fails: an involution that
   reverts to the slot that failed is the revert that is not one. *)
Theorem reaching_the_other_slot_gives_the_involution :
  forall rv : Revert, RevertsToTheOtherSlot rv -> IsAnInvolution rv.
Proof.
  intros rv H s.
  destruct s.
  - destruct (rv SlotA) eqn:E1.
    + exfalso. exact (H SlotA E1).
    + destruct (rv SlotB) eqn:E2.
      * reflexivity.
      * exfalso. exact (H SlotB E2).
  - destruct (rv SlotB) eqn:E1.
    + destruct (rv SlotA) eqn:E2.
      * exfalso. exact (H SlotA E2).
      * reflexivity.
    + exfalso. exact (H SlotB E1).
Qed.

Definition stuck_revert : Revert := fun s => s.

Theorem the_stuck_revert_is_an_involution : IsAnInvolution stuck_revert.
Proof. intros s. reflexivity. Qed.

Theorem the_stuck_revert_reverts_to_nothing :
  ~ RevertsToTheOtherSlot stuck_revert.
Proof. intros H. exact (H SlotA eq_refl). Qed.

(* A revert that always selects the same image, which is the pinned slot an
   automatic revert becomes when it forgets which one failed. Over
   R-09-028's two slots it is the only shape that is not an involution, and
   it breaks the other-slot obligation too, which is why the implication
   above runs one way and not both. *)
Definition constant_revert : Revert := fun _ => SlotA.

Theorem the_constant_revert_is_not_an_involution :
  ~ IsAnInvolution constant_revert.
Proof. intros H. specialize (H SlotB). discriminate H. Qed.

Theorem the_constant_revert_reverts_to_nothing :
  ~ RevertsToTheOtherSlot constant_revert.
Proof. intros H. exact (H SlotA eq_refl). Qed.

(* -------------------------------------------------------------------------
   The credential attempt counter (R-12-017).

   Two clauses, and both are mechanisms rather than policies: the counter
   advances *before* the comparison, and nothing rolls it back, so an
   attempt cut short spends itself rather than being refunded and there is
   no oracle to take off the device.
   ------------------------------------------------------------------------- *)

Definition spec_attempt : list AttemptStep :=
  cons ChargeTheCounter (cons CompareTheCredential nil).

Definition AdvancesBeforeTheComparison (l : list AttemptStep) : Prop :=
  precedes attempt_eqb ChargeTheCounter CompareTheCredential l = true.

(* R13 (R-12-017). *)
Theorem the_specification_attempt_charges_before_it_compares :
  AdvancesBeforeTheComparison spec_attempt.
Proof. reflexivity. Qed.

(* The order reversed: both steps still happen and each happens once, and an
   attempt cut short between them is free. *)
Definition compare_first_attempt : list AttemptStep :=
  cons CompareTheCredential (cons ChargeTheCounter nil).

Theorem the_compare_first_attempt_still_takes_both_steps :
  Nat.eqb (occurrences attempt_eqb ChargeTheCounter compare_first_attempt) 1
  = true
  /\ Nat.eqb (occurrences attempt_eqb CompareTheCredential
                          compare_first_attempt) 1 = true.
Proof. split; reflexivity. Qed.

Theorem the_compare_first_attempt_compares_before_it_charges :
  ~ AdvancesBeforeTheComparison compare_first_attempt.
Proof. intros H. discriminate H. Qed.

Definition Settle : Type := bool -> nat -> nat.

Definition spec_settle : Settle := fun _ n => n.

Definition RefundsNothing (st : Settle) : Prop :=
  forall (cut : bool) (n : nat), Nat.leb n (st cut n) = true.

Definition KeepsTheCompletedAttempt (st : Settle) : Prop :=
  forall n : nat, st false n = n.

(* R14 and R15 (R-12-017). *)
Theorem the_specification_settlement_refunds_nothing :
  RefundsNothing spec_settle.
Proof. intros cut n. unfold spec_settle. exact (nat_leb_refl n). Qed.

Theorem the_specification_settlement_keeps_the_completed_attempt :
  KeepsTheCompletedAttempt spec_settle.
Proof. intros n. reflexivity. Qed.

(* A settlement that refunds the attempt an attacker cut short, which is the
   offline brute force R-12-017's second clause exists to close. It agrees
   with the specification wherever the attempt completed, so what refuses it
   is the refund and not a different accounting. *)
Definition refunding_settle : Settle := fun cut n =>
  if cut then before_last n else n.

Theorem the_refunding_settlement_keeps_the_completed_attempt :
  KeepsTheCompletedAttempt refunding_settle.
Proof. intros n. reflexivity. Qed.

Theorem the_refunding_settlement_refunds :
  ~ RefundsNothing refunding_settle.
Proof. intros H. specialize (H true 1). discriminate H. Qed.

(* And the other way: a settlement that charges a completed attempt a second
   time refunds nothing and loses R-12-017's *advances before the
   comparison*, the counter running ahead of what was tried, so the two
   clauses are two obligations and this construction is what shows it. *)
Definition double_charging_settle : Settle := fun _ n => S n.

Theorem the_double_charging_settlement_refunds_nothing :
  RefundsNothing double_charging_settle.
Proof.
  intros cut n. unfold double_charging_settle. simpl.
  induction n as [ | k IH ]; [ reflexivity | ]. simpl. exact IH.
Qed.

Theorem the_double_charging_settlement_charges_a_completed_attempt_twice :
  ~ KeepsTheCompletedAttempt double_charging_settle.
Proof. intros H. specialize (H 0). discriminate H. Qed.

(* =========================================================================
   The roots the boot ROM accepts (R-09-036), and the scheme split
   (R-09-002, R-05-058c).
   ========================================================================= *)

Definition Rom (m : Machine) : Type := nat -> bool.

Definition spec_rom (m : Machine) : Rom m := fun r =>
  Nat.eqb r (m.(accepted_root) m.(state)).

(* R-09-036: in production the ROM accepts the production root alone, and no
   fuse, strap, or signed unlock token widens the accepted set. Stated as
   the state's own root and as the singleton, because a ROM can accept the
   right root and still accept a second one. *)
Definition AcceptsTheStatesOwnRoot (m : Machine) (rm : Rom m) : Prop :=
  rm (m.(accepted_root) m.(state)) = true.

Definition AcceptsNoSecondRoot (m : Machine) (rm : Rom m) : Prop :=
  forall r1 r2 : nat, rm r1 = true -> rm r2 = true -> r1 = r2.

(* V1 and V2 (R-09-036). *)
Theorem the_specification_rom_accepts_the_states_own_root :
  forall m : Machine, AcceptsTheStatesOwnRoot m (spec_rom m).
Proof.
  intros m. unfold spec_rom. exact (nat_eqb_refl (m.(accepted_root) m.(state))).
Qed.

Theorem the_specification_rom_accepts_no_second_root :
  forall m : Machine, AcceptsNoSecondRoot m (spec_rom m).
Proof.
  intros m r1 r2 H1 H2. unfold spec_rom in H1, H2.
  rewrite (nat_eqb_sound _ _ H1). rewrite (nat_eqb_sound _ _ H2). reflexivity.
Qed.

(* A ROM widened by a signed unlock token: it still accepts the state's own
   root, so what refuses it is the second root and not a wrong one. *)
Definition unlockable_rom (m : Machine) (token : nat) : Rom m := fun r =>
  orb (Nat.eqb r (m.(accepted_root) m.(state))) (Nat.eqb r token).

Lemma the_unlockable_rom_takes_the_states_own_root :
  forall (m : Machine) (token : nat),
    unlockable_rom m token (m.(accepted_root) m.(state)) = true.
Proof.
  intros m token. unfold unlockable_rom.
  assert (E : Nat.eqb (m.(accepted_root) m.(state))
                      (m.(accepted_root) m.(state)) = true)
    by exact (nat_eqb_refl _).
  simpl. rewrite E. reflexivity.
Qed.

Lemma the_unlockable_rom_takes_the_token :
  forall (m : Machine) (token : nat), unlockable_rom m token token = true.
Proof.
  intros m token. unfold unlockable_rom.
  assert (E : Nat.eqb token token = true) by exact (nat_eqb_refl token).
  simpl. rewrite E.
  destruct (Nat.eqb token (m.(accepted_root) m.(state))); reflexivity.
Qed.

Theorem the_unlockable_rom_still_accepts_the_states_own_root :
  forall (m : Machine) (token : nat),
    AcceptsTheStatesOwnRoot m (unlockable_rom m token).
Proof. intros m token. exact (the_unlockable_rom_takes_the_states_own_root m token). Qed.

Theorem the_unlockable_rom_accepts_a_second_root :
  forall (m : Machine) (token : nat),
    Nat.eqb token (m.(accepted_root) m.(state)) = false ->
    ~ AcceptsNoSecondRoot m (unlockable_rom m token).
Proof.
  intros m token Hne C.
  specialize (C (m.(accepted_root) m.(state)) token
                (the_unlockable_rom_takes_the_states_own_root m token)
                (the_unlockable_rom_takes_the_token m token)).
  rewrite <- C in Hne.
  rewrite (nat_eqb_refl (m.(accepted_root) m.(state))) in Hne.
  discriminate Hne.
Qed.

(* A ROM rooted somewhere other than its own lifecycle state, which accepts
   one root and the wrong one: R-09-036's diversification is what refuses
   it, and it satisfies the singleton clause, so the two are two
   obligations. It is the development-rooted image verifying in a production
   part that the entry names by its consequence. *)
Definition foreign_rooted_rom (m : Machine) (token : nat) : Rom m := fun r =>
  Nat.eqb r token.

Theorem the_foreign_rooted_rom_accepts_no_second_root :
  forall (m : Machine) (token : nat),
    AcceptsNoSecondRoot m (foreign_rooted_rom m token).
Proof.
  intros m token r1 r2 H1 H2. unfold foreign_rooted_rom in H1, H2.
  rewrite (nat_eqb_sound _ _ H1). rewrite (nat_eqb_sound _ _ H2). reflexivity.
Qed.

Theorem the_foreign_rooted_rom_refuses_the_states_own_root :
  forall (m : Machine) (token : nat),
    Nat.eqb (m.(accepted_root) m.(state)) token = false ->
    ~ AcceptsTheStatesOwnRoot m (foreign_rooted_rom m token).
Proof.
  intros m token Hne C. unfold AcceptsTheStatesOwnRoot, foreign_rooted_rom in C.
  rewrite C in Hne. discriminate Hne.
Qed.

(* R-09-002's second acceptance clause, read as a property: no stage's
   scheme is chosen by what signs it rather than by what verifies it
   (reading 10). *)
Definition Signer : Type := nat.

Definition SchemeChoice (m : Machine) : Type := Stage -> Signer -> Scheme.

Definition spec_scheme (m : Machine) : SchemeChoice m := fun s _ =>
  if m.(rom_verifies) s then SlhDsa else MlDsa.

Definition ChosenByTheVerifier (m : Machine) (sc : SchemeChoice m) : Prop :=
  forall (s : Stage) (x y : Signer), sc s x = sc s y.

Definition RomVerifiesWithSlhDsa (m : Machine) (sc : SchemeChoice m) : Prop :=
  forall (s : Stage) (x : Signer), m.(rom_verifies) s = true -> sc s x = SlhDsa.

(* V3 and V4 (R-09-002, R-05-058c). *)
Theorem the_specification_scheme_is_chosen_by_the_verifier :
  forall m : Machine, ChosenByTheVerifier m (spec_scheme m).
Proof. intros m s x y. reflexivity. Qed.

Theorem the_specification_scheme_gives_the_rom_slh_dsa :
  forall m : Machine, RomVerifiesWithSlhDsa m (spec_scheme m).
Proof. intros m s x H. unfold spec_scheme. rewrite H. reflexivity. Qed.

(* A choice that varies with who signed, above the ROM: the metal-mask
   verifier still gets SLH-DSA, so the two obligations are separate and this
   construction is what shows it. *)
Definition signer_chosen_scheme (m : Machine) : SchemeChoice m := fun s g =>
  if m.(rom_verifies) s then SlhDsa else (if Nat.ltb 0 g then MlDsa else SlhDsa).

Theorem the_signer_chosen_scheme_still_gives_the_rom_slh_dsa :
  forall m : Machine, RomVerifiesWithSlhDsa m (signer_chosen_scheme m).
Proof. intros m s x H. unfold signer_chosen_scheme. rewrite H. reflexivity. Qed.

Theorem the_signer_chosen_scheme_reads_the_signer :
  forall (m : Machine) (s : Stage),
    m.(rom_verifies) s = false -> ~ ChosenByTheVerifier m (signer_chosen_scheme m).
Proof.
  intros m s H C. specialize (C s 0 1).
  unfold signer_chosen_scheme in C. rewrite H in C. discriminate C.
Qed.

(* And the other way: one scheme everywhere is a function of the verifier
   and gives the metal-mask ROM the wrong one, which is the assumption
   R-05-058c's grounds turn on. *)
Definition uniform_ml_scheme (m : Machine) : SchemeChoice m := fun _ _ => MlDsa.

Theorem the_uniform_scheme_is_chosen_by_the_verifier :
  forall m : Machine, ChosenByTheVerifier m (uniform_ml_scheme m).
Proof. intros m s x y. reflexivity. Qed.

Theorem the_uniform_scheme_denies_the_rom_slh_dsa :
  forall (m : Machine) (s : Stage),
    m.(rom_verifies) s = true -> ~ RomVerifiesWithSlhDsa m (uniform_ml_scheme m).
Proof. intros m s H C. specialize (C s 0 H). discriminate C. Qed.

(* =========================================================================
   The Debug Module and trace, at each lifecycle state (R-09-034, R-15-078,
   R-15-079, R-09-035).

   R-09-034's second sentence closes this table rather than leaving it open.
   The Debug Module and trace are closed permanently in production, are live
   in development and RMA alone, gated there by R-15-079's authenticated
   entry, and in every other lifecycle state are closed on the same terms as
   the five manufacturing surfaces beside them. That is a value at each of
   R-09-032's five states, so the table below is the specification and its
   five entries are literals the entry closes; a machine whose own table
   differs from it is a refuted construction and not a second reading.
   R-15-078's production gate, the predicate that entry puts in the Sail
   model, is one clause of the table, and R-09-035 stands inside it rather
   than against it, RMA being one of the two states the Module is live in.
   ========================================================================= *)

Definition debug_table (l : Lifecycle) : bool :=
  match l with
  | Raw => false         (* R-09-034: closed, on the five's own terms     *)
  | TestState => false   (* R-09-034: closed, on the five's own terms     *)
  | Development => true  (* R-09-034: live in development and RMA alone   *)
  | Production => false  (* R-09-034, R-15-078: closed permanently        *)
  | Rma => true          (* R-09-034, R-09-035: live at RMA behind entry  *)
  end.

Example the_register_closes_the_debug_table :
  map_over debug_table all_lifecycles
  = cons false (cons false (cons true (cons false (cons true nil))))
  := eq_refl.

(* D1 (R-15-078): no DM transaction reaches the fabric in the production
   state, which is that entry's own criterion and what the absence
   contract's auditor searches the netlist for. Stated of the machine's own
   table rather than of a bare function, so a machine whose Debug Module is
   live in production is one this file refuses rather than one it does not
   mention. *)
Definition ClosesTheDebugModuleInProduction (m : Machine) : Prop :=
  m.(debug_live) Production = false.

(* D2 (R-09-034, R-09-035): and live in development and RMA, which is the
   half the production gate alone does not carry. A Module fused off in
   every state satisfies the gate and leaves R-15-079's authenticated entry
   and R-09-035's RMA debug with nothing to enter. *)
Definition OpensTheDebugModuleWhereTheEntryDoes (m : Machine) : Prop :=
  m.(debug_live) Development = true /\ m.(debug_live) Rma = true.

(* D3 (R-09-034): *live in development and RMA alone*, so every other state
   is closed on the same terms as the five manufacturing surfaces. Stated at
   an arbitrary state rather than at the three the roster happens to leave,
   so the clause is about R-09-032's enumeration and not about a list. *)
Definition ClosesTheDebugModuleEverywhereElse (m : Machine) : Prop :=
  forall l : Lifecycle,
    lifecycle_eqb l Development = false -> lifecycle_eqb l Rma = false ->
    m.(debug_live) l = false.

Definition CarriesTheRegistersDebugTable (m : Machine) : Prop :=
  forall l : Lifecycle, m.(debug_live) l = debug_table l.

(* D1a, D2a and D3a: the specification satisfies all three, stated of an
   arbitrary machine carrying the register's table rather than of one demo
   machine, so the three are properties of the table and not of a witness. *)
Theorem the_registers_table_closes_production :
  forall m : Machine,
    CarriesTheRegistersDebugTable m -> ClosesTheDebugModuleInProduction m.
Proof. intros m H. unfold ClosesTheDebugModuleInProduction. exact (H Production). Qed.

Theorem the_registers_table_opens_development_and_rma :
  forall m : Machine,
    CarriesTheRegistersDebugTable m -> OpensTheDebugModuleWhereTheEntryDoes m.
Proof. intros m H. split; [ exact (H Development) | exact (H Rma) ]. Qed.

Theorem the_registers_table_closes_every_other_state :
  forall m : Machine,
    CarriesTheRegistersDebugTable m -> ClosesTheDebugModuleEverywhereElse m.
Proof.
  intros m H l Hd Hr. rewrite (H l). destruct l.
  - reflexivity.
  - reflexivity.
  - discriminate Hd.
  - reflexivity.
  - discriminate Hr.
Qed.

(* The three clauses above are not three independent obligations, and this
   file says so rather than letting the count of them imply it. D3 carries
   D1 outright, production being one of the states R-09-034 leaves outside
   development and RMA, so no machine breaks D1 alone and D1 is D3's
   instance at one state. The converse fails, `test_live_table` below being
   what shows it, so D3 is strictly the stronger. D1 is stated anyway and
   for a reason that is not independence: it is the predicate R-15-078 owns
   by name, the one that entry's RTL refinement obligation quantifies over
   and the absence contract's auditor searches the netlist for, so it is
   stated here to be citable there. What is independent is D2 and D3, and
   `dark_debug_table` below keeps both D1 and D3 while breaking D2. *)
Theorem closing_every_other_state_closes_production :
  forall m : Machine,
    ClosesTheDebugModuleEverywhereElse m -> ClosesTheDebugModuleInProduction m.
Proof. intros m H. exact (H Production eq_refl eq_refl). Qed.

(* D4, the join, and the sentence that makes this a closed table rather than
   a preference among the tables the entry admits: the clauses do not merely
   hold of R-09-034's table, they fix it. Stated over the two independent
   ones rather than over all three, so the redundancy above is checked here
   rather than asserted above: D1 is never used, and a machine satisfying D2
   and D3 carries `debug_table` at every one of the five states, D1
   following from D3 by the lemma just proved. *)
Theorem the_two_independent_clauses_fix_the_table :
  forall m : Machine,
    OpensTheDebugModuleWhereTheEntryDoes m ->
    ClosesTheDebugModuleEverywhereElse m ->
    CarriesTheRegistersDebugTable m.
Proof.
  intros m [ H2 H3 ] H4 l. destruct l.
  - exact (H4 Raw eq_refl eq_refl).
  - exact (H4 TestState eq_refl eq_refl).
  - exact H2.
  - exact (H4 Production eq_refl eq_refl).
  - exact H3.
Qed.

(* -------------------------------------------------------------------------
   The three tables the entry refuses. Each is installed in a machine at the
   end of the file and each is shown to keep every clause it leaves standing,
   which is two clauses for two of them and one for the third: because D3
   carries D1, the table live in production breaks both at once and there is
   no table that breaks D1 alone. That is stated where each is refuted rather
   than absorbed into a count.
   ------------------------------------------------------------------------- *)

(* A Debug Module live in the production state, which is the transaction
   R-15-078's RTL refinement obligation says reaches no fabric. It breaks D1
   and D3 together, production being one of the states outside development
   and RMA, and it keeps D2, being live exactly where R-09-034 says live. So
   what refuses it is the production entry, reached through both clauses that
   read production, and not a generally open table: raw and test stay closed
   under it. *)
Definition live_in_production_table (l : Lifecycle) : bool :=
  match l with
  | Raw => false
  | TestState => false
  | Development => true
  | Production => true
  | Rma => true
  end.

(* R-09-034's first sentence read past that entry's own carve-out, closing
   the Module at the test exit and leaving development dark. The entry
   refuses it in as many words, being live in development and RMA alone, and
   its acceptance clause states what the unqualified reading costs: R-15-079
   and R-09-035 amended together and a mechanism nothing specifies. It keeps
   the production gate and closes every state outside development and RMA,
   so what refuses it is development. *)
Definition dark_debug_table (l : Lifecycle) : bool :=
  match l with
  | Raw => false
  | TestState => false
  | Development => false
  | Production => false
  | Rma => true
  end.

(* And a table live at the test state, which R-09-034's *live in development
   and RMA alone* excludes and its next clause closes by name, the test state
   being one of the others the Module is closed in on the same terms as scan,
   BIST, the straps, the flash-programming path and the provisioning
   interface. It keeps the production gate and opens exactly where the entry
   opens, so what refuses it is the state it adds. *)
Definition test_live_table (l : Lifecycle) : bool :=
  match l with
  | Raw => false
  | TestState => true
  | Development => true
  | Production => false
  | Rma => true
  end.

Example the_three_refused_tables_beside_the_registers :
  map_over live_in_production_table all_lifecycles
  = cons false (cons false (cons true (cons true (cons true nil))))
  /\ map_over dark_debug_table all_lifecycles
  = cons false (cons false (cons false (cons false (cons true nil))))
  /\ map_over test_live_table all_lifecycles
  = cons false (cons true (cons true (cons false (cons true nil))))
  := conj eq_refl (conj eq_refl eq_refl).

(* -------------------------------------------------------------------------
   R-15-079's authenticated entry, which gates the two states the table
   leaves live. In development and RMA, DM entry is an RoT challenge-response
   that is ML-DSA-signed and serial-bound; the signature is the crypto core's
   (M3.4), so what is stated here is the two things the entry fixes about the
   decision itself: the fuse gates it and the response decides it.
   ------------------------------------------------------------------------- *)

Definition Credential : Type := nat.

Definition DebugEntry (m : Machine) : Type := Lifecycle -> Credential -> bool.

Definition spec_debug_entry (m : Machine) : DebugEntry m := fun l c =>
  andb (m.(debug_live) l) (Nat.eqb c (m.(debug_response) l)).

(* D5 (R-09-034's third acceptance clause): the Module's liveness is a
   property of the lifecycle state read from the fuse bank rather than of a
   software check, so no credential opens an entry in a state the table
   closes. This is the obligation that reads the machine's own liveness
   table, which is what makes that table load-bearing rather than carried. *)
Definition EntersNoClosedState (m : Machine) (en : DebugEntry m) : Prop :=
  forall (l : Lifecycle) (c : Credential),
    m.(debug_live) l = false -> en l c = false.

(* D6 (R-15-079): and where the fuse leaves it live, what opens it is the
   challenge-response and not the state alone. *)
Definition EntersOnlyOnTheResponse (m : Machine) (en : DebugEntry m) : Prop :=
  forall (l : Lifecycle) (c : Credential),
    en l c = true -> Nat.eqb c (m.(debug_response) l) = true.

Theorem the_specification_entry_opens_no_closed_state :
  forall m : Machine, EntersNoClosedState m (spec_debug_entry m).
Proof. intros m l c H. unfold spec_debug_entry. rewrite H. reflexivity. Qed.

Theorem the_specification_entry_takes_only_the_response :
  forall m : Machine, EntersOnlyOnTheResponse m (spec_debug_entry m).
Proof.
  intros m l c H. unfold spec_debug_entry in H.
  destruct (andb_split _ _ H) as [ _ Hr ]. exact Hr.
Qed.

(* D7: and it opens where both hold, so the two obligations above are not
   proved of a decision that refuses every entry there is. *)
Theorem the_specification_entry_admits_the_authenticated_response :
  forall (m : Machine) (l : Lifecycle),
    m.(debug_live) l = true ->
    spec_debug_entry m l (m.(debug_response) l) = true.
Proof.
  intros m l H. unfold spec_debug_entry. rewrite H. simpl.
  exact (nat_eqb_refl (m.(debug_response) l)).
Qed.

(* An entry that reads the fuse and asks for nothing, which is the
   unauthenticated DM entry R-15-079 replaces with a challenge-response. It
   opens no state the table closes, so what refuses it is the missing
   response and not a wider reach. *)
Definition unauthenticated_entry (m : Machine) : DebugEntry m := fun l _ =>
  m.(debug_live) l.

Theorem the_unauthenticated_entry_opens_no_closed_state :
  forall m : Machine, EntersNoClosedState m (unauthenticated_entry m).
Proof. intros m l c H. unfold unauthenticated_entry. exact H. Qed.

(* And an entry that checks the response and not the fuse, which is
   R-09-034's *gated by the fuse state and not by a software check* read
   backwards: a production part whose response is known is entered. It takes
   only the response, so what refuses it is the state it does not read. *)
Definition software_gated_entry (m : Machine) : DebugEntry m := fun l c =>
  Nat.eqb c (m.(debug_response) l).

Theorem the_software_gated_entry_takes_only_the_response :
  forall m : Machine, EntersOnlyOnTheResponse m (software_gated_entry m).
Proof. intros m l c H. exact H. Qed.

(* =========================================================================
   The demo machines, for R-05-165's uninhabited-domain mode and for the
   refutation witnesses. One record literal parameterized by the five fields
   the constructions below vary, so a figure edited on one side of the file
   and read on the other is a failed conversion instead of a silent
   disagreement. Every figure is an arbitrary witness value and carries no
   composition claim (gap h).
   ------------------------------------------------------------------------- *)

Definition demo_item_code (i : Item) : nat :=
  match i with
  | LifecycleFuse => 1
  | EntropyHealthVerdict => 2
  | BootTargetLatch => 3
  | StageMeasure RotRuntime => 4
  | StageMeasure MModeImage => 5
  | StageMeasure CoreKernels => 6
  | StageMeasure StaticImage => 7
  end.

Example the_demo_measurement_encoding :
  map_over demo_item_code all_items
  = cons 1 (cons 2 (cons 3 (cons 4 (cons 5 (cons 6 (cons 7 nil))))))
  := eq_refl.

(* R-15-079's expected challenge-response per state, at arbitrary witness
   values: what an ML-DSA-signed, serial-bound response actually is belongs
   to M3.4, and these five numbers carry no claim about it (gap h). *)
Definition demo_debug_response (l : Lifecycle) : nat :=
  match l with
  | Raw => 30
  | TestState => 31
  | Development => 32
  | Production => 33
  | Rma => 34
  end.

Example the_demo_debug_responses :
  map_over demo_debug_response all_lifecycles
  = cons 30 (cons 31 (cons 32 (cons 33 (cons 34 nil)))) := eq_refl.

Definition demo_accepted_root (l : Lifecycle) : nat :=
  match l with
  | Raw => 0
  | TestState => 1
  | Development => 2
  | Production => 3
  | Rma => 4
  end.

Example the_demo_roots_are_diversified :
  map_over demo_accepted_root all_lifecycles
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil)))) := eq_refl.

(* R-09-006: the ROM verifies and enters the RoT runtime and places the
   verified M-mode image, and the paths above it are the replaceable ones. *)
Definition demo_rom_verifies (s : Stage) : bool :=
  match s with
  | RotRuntime => true
  | MModeImage => true
  | CoreKernels => false
  | StaticImage => false
  end.

Example the_demo_rom_verifies_the_first_two_stages :
  map_over demo_rom_verifies all_stages
  = cons true (cons true (cons false (cons false nil))) := eq_refl.

Definition demo_counter (c : Counter) : nat :=
  match c with
  | SecurityVersionFloor => 4
  | SealingRootVersion => 7
  | CredentialAttemptCounter => 2
  | FreshnessEpochRoot => 9
  end.

(* The same machine after R-09-023's duress erase or a key rotation: the
   sealing-root version alone has advanced. *)
Definition erased_counter (c : Counter) : nat :=
  match c with
  | SecurityVersionFloor => 4
  | SealingRootVersion => 8
  | CredentialAttemptCounter => 2
  | FreshnessEpochRoot => 9
  end.

Example the_demo_counters_and_the_advanced_one :
  map_over demo_counter all_counters = cons 4 (cons 7 (cons 2 (cons 9 nil)))
  /\ map_over erased_counter all_counters = cons 4 (cons 8 (cons 2 (cons 9 nil)))
  := conj eq_refl eq_refl.

Definition demo_witness (f : Field) : nat :=
  match f with
  | ChainDigest => 11
  | CheckerVersion => 12
  | SpecAndPolicySet => 13
  | IsaProfileVersion => 14
  | RadioGenerationIdentity => 15
  | LifecycleFuseValue => 16
  end.

(* A machine whose chain disagrees with the reference set and whose four
   admission-discipline terms do not, which is what prices the narrower
   reading of R-09-025's "this set". *)
Definition forked_witness (f : Field) : nat :=
  match f with
  | ChainDigest => 99
  | CheckerVersion => 12
  | SpecAndPolicySet => 13
  | IsaProfileVersion => 14
  | RadioGenerationIdentity => 15
  | LifecycleFuseValue => 16
  end.

(* And one whose profile version disagrees, so a lenient appraisal that
   skips the chain is still shown to refuse a term it does check. *)
Definition stale_witness (f : Field) : nat :=
  match f with
  | ChainDigest => 11
  | CheckerVersion => 12
  | SpecAndPolicySet => 13
  | IsaProfileVersion => 99
  | RadioGenerationIdentity => 15
  | LifecycleFuseValue => 16
  end.

Example the_three_witness_sets :
  map_over demo_witness all_fields
  = cons 11 (cons 12 (cons 13 (cons 14 (cons 15 (cons 16 nil)))))
  /\ map_over forked_witness all_fields
  = cons 99 (cons 12 (cons 13 (cons 14 (cons 15 (cons 16 nil)))))
  /\ map_over stale_witness all_fields
  = cons 11 (cons 12 (cons 13 (cons 99 (cons 15 (cons 16 nil)))))
  := conj eq_refl (conj eq_refl eq_refl).

(* The demo machine's declaration of R-05-058c's hash-only assumption at
   the chain's scale, discharged by conversion over the seven digests its
   extension reaches from its seed and not by an axiom: a machine that
   could not discharge it would not be a Machine (reading 7). *)
Lemma demo_extend_separates_on_the_chain :
  separates_along (fun d a => S (S (d + d + a))) demo_item_code 0 = true.
Proof. reflexivity. Qed.

Definition demo_with (st : Lifecycle) (ent : bool) (dl : Lifecycle -> bool)
                     (ctr : Counter -> nat) (wit : Field -> nat) : Machine := {|
  rom_seed := 0;
  extend := fun d a => S (S (d + d + a));
  item_code := demo_item_code;
  extend_separates_on_the_chain := demo_extend_separates_on_the_chain;
  state := st;
  debug_live := dl;
  debug_response := demo_debug_response;
  entropy_ok := ent;
  accepted_root := demo_accepted_root;
  rom_verifies := demo_rom_verifies;
  rollback_floor := 4;
  boot_bound := 3;
  counter := ctr;
  witness := wit;
  reference := demo_witness
|}.

Definition demo : Machine :=
  demo_with Production true debug_table demo_counter demo_witness.

Definition demo_debug : Machine :=
  demo_with Development true debug_table demo_counter demo_witness.

Definition demo_erased : Machine :=
  demo_with Production true debug_table erased_counter demo_witness.

Definition demo_flat : Machine :=
  demo_with Production false debug_table demo_counter demo_witness.

Definition demo_forked : Machine :=
  demo_with Production true debug_table demo_counter forked_witness.

Definition demo_stale : Machine :=
  demo_with Production true debug_table demo_counter stale_witness.

(* The three machines carrying the tables R-09-034 refuses, differing from
   `demo` in that field alone. *)
Definition demo_open : Machine :=
  demo_with Production true live_in_production_table demo_counter demo_witness.

Definition demo_dark : Machine :=
  demo_with Production true dark_debug_table demo_counter demo_witness.

Definition demo_test_live : Machine :=
  demo_with Production true test_live_table demo_counter demo_witness.

Example the_demo_machine_declares :
  demo.(rom_seed) = 0
  /\ demo.(rollback_floor) = 4
  /\ demo.(boot_bound) = 3
  /\ demo.(state) = Production
  /\ demo.(entropy_ok) = true
  /\ demo_flat.(entropy_ok) = false
  /\ demo_debug.(state) = Development
  /\ demo.(counter) SealingRootVersion = 7
  /\ demo_erased.(counter) SealingRootVersion = 8 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))))))).

(* R-15-241b's latched verdict at every machine below, so that a machine
   varied for one reason is not silently varied for a second: exactly one of
   the nine holds a failed root, and it is the one the fail-closed
   refutations are stated at. *)
Example the_entropy_verdict_at_every_demo_machine :
  map_over entropy_ok (cons demo (cons demo_debug (cons demo_erased
    (cons demo_flat (cons demo_forked (cons demo_stale (cons demo_open
    (cons demo_dark (cons demo_test_live nil)))))))))
  = cons true (cons true (cons true (cons false (cons true (cons true
    (cons true (cons true (cons true nil)))))))) := eq_refl.

Example the_lifecycle_state_at_every_demo_machine :
  map_over state (cons demo (cons demo_debug (cons demo_erased
    (cons demo_flat (cons demo_forked (cons demo_stale (cons demo_open
    (cons demo_dark (cons demo_test_live nil)))))))))
  = cons Production (cons Development (cons Production (cons Production
    (cons Production (cons Production (cons Production (cons Production
    (cons Production nil)))))))) := eq_refl.

(* And the liveness table at every machine below, so that the three the
   entry refuses are one cell away from R-09-034's table rather than three
   different tables: six carry the register's, and the other three break one
   of its clauses each. *)
Example the_debug_table_at_every_demo_machine :
  map_over (fun m => map_over m.(debug_live) all_lifecycles)
    (cons demo (cons demo_debug (cons demo_erased (cons demo_flat
    (cons demo_forked (cons demo_stale (cons demo_open (cons demo_dark
    (cons demo_test_live nil)))))))))
  = cons (cons false (cons false (cons true (cons false (cons true nil)))))
    (cons (cons false (cons false (cons true (cons false (cons true nil)))))
    (cons (cons false (cons false (cons true (cons false (cons true nil)))))
    (cons (cons false (cons false (cons true (cons false (cons true nil)))))
    (cons (cons false (cons false (cons true (cons false (cons true nil)))))
    (cons (cons false (cons false (cons true (cons false (cons true nil)))))
    (cons (cons false (cons false (cons true (cons true (cons true nil)))))
    (cons (cons false (cons false (cons false (cons false (cons true nil)))))
    (cons (cons false (cons true (cons true (cons false (cons true nil)))))
      nil)))))))) := eq_refl.

Example the_demo_extension_is_order_sensitive :
  demo.(extend) 0 1 = 3 /\ demo.(extend) 3 2 = 10 /\ demo.(extend) 0 2 = 4
  := conj eq_refl (conj eq_refl eq_refl).

(* The seven digests the demo chain extends from, computed, so the
   declaration above is seen to range over the chain's own digests and
   over nothing outside it. *)
Example the_demo_chain_extends_from_these_digests :
  chain_extension_points demo 0 boot_steps
  = cons 0 (cons 3 (cons 10 (cons 25 (cons 56 (cons 119 (cons 246 nil))))))
  := eq_refl.

(* The two extensions refused by the declaration, and neither is a Machine,
   which is the refusal: the record cannot be built over either. A counting
   extension ignores the measurement, so every item extends a digest to the
   same digest, and it fails at the seed. A late-colliding one separates the
   seven codes at the seed and collides at the second digest the chain
   reaches, which is what shows the declaration reads every digest the chain
   extends from and not the seed alone. Away from that digest it is the
   demo's own extension, which is pinned so that what refutes it is the
   one collision and not a different fold. *)
Definition counting_extend : nat -> nat -> nat := fun d _ => S d.

Definition late_colliding_extend : nat -> nat -> nat := fun d a =>
  if Nat.eqb d 3 then d else S (S (d + d + a)).

Example the_counting_extension_separates_nothing :
  separates_at counting_extend demo_item_code 0 = false
  /\ separates_along counting_extend demo_item_code 0 = false
  := conj eq_refl eq_refl.

Example the_late_collision_passes_the_seed_and_fails_the_chain :
  separates_at late_colliding_extend demo_item_code 0 = true
  /\ separates_at late_colliding_extend demo_item_code 3 = false
  /\ separates_along late_colliding_extend demo_item_code 0 = false
  := conj eq_refl (conj eq_refl eq_refl).

Example the_late_collision_is_the_demo_extension_elsewhere :
  late_colliding_extend 0 1 = demo.(extend) 0 1
  /\ late_colliding_extend 10 3 = demo.(extend) 10 3
  /\ late_colliding_extend 3 1 = 3
  /\ Nat.eqb (late_colliding_extend 3 1) (demo.(extend) 3 1) = false
  := conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   The chain, at a machine (R-09-027, and gap a made observable).
   ------------------------------------------------------------------------- *)

Theorem the_attempt_folding_digest_is_refuted :
  ~ IsReproducible demo (attempt_folding_digest demo).
Proof. intros H. specialize (H 0 1 nil). discriminate H. Qed.

(* The twin at a machine, beside the general one above: on the first attempt
   the construction reaches the specification's digest exactly, and on the
   second it does not. So what refutes it is the dependence on what the boot
   observed and not a different fold, and the defect is the one that hides,
   a device reproducing the golden value until it retries. *)
Example the_attempt_folding_digest_agrees_at_the_first_attempt :
  attempt_folding_digest demo 0 boot_steps = spec_digest demo 0 boot_steps
  /\ Nat.eqb (attempt_folding_digest demo 1 boot_steps)
             (spec_digest demo 1 boot_steps) = false
  := conj eq_refl eq_refl.

(* Gap a reaches a relying party on reading 2's vector and not otherwise,
   which is the one place the two open questions meet: the two admitted
   prologue orders reach different digests, so on the wide reading, where
   the chain measurement is a term, which order the register meant is a
   difference a relying party appraises against, and on gap g's narrow
   reading it is a difference no quote carries. The computation below is the
   digests; the reach is reading 2's. *)
Theorem the_two_prologue_orders_measure_differently :
  Nat.eqb (spec_digest demo 0 boot_steps)
          (spec_digest demo 0 (chain_from (swap_at 1 input_prologue)
                                          all_stages)) = false.
Proof. reflexivity. Qed.

(* And the two shapes gap b leaves open do not, the front-loaded chain
   extending the same items in the same order: the second gap is about what
   ran between the extensions and not about what was measured. *)
Theorem the_two_admitted_chain_shapes_measure_alike :
  Nat.eqb (spec_digest demo 0 boot_steps)
          (spec_digest demo 0 front_loaded_chain) = true.
Proof. reflexivity. Qed.

(* -------------------------------------------------------------------------
   Seal and unseal, at a machine. One blob, sealed in production under
   sealing-root version 7 at the digest the chain reached, and the four
   machines at which it does not open.
   ------------------------------------------------------------------------- *)

Definition demo_blob : Blob :=
  {| bound_digest := 5; bound_state := Production;
     bound_root_version := 7; blob_handle := 21 |}.

Example the_demo_blob_declares :
  demo_blob.(bound_digest) = 5 /\ demo_blob.(bound_state) = Production
  /\ demo_blob.(bound_root_version) = 7 /\ demo_blob.(blob_handle) = 21 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* S7: the specification opens it here and at none of the four machines that
   differ by one gate, which is what keeps the five obligations above from
   being proved of a construction that refuses everything. *)
Example the_blob_opens_here_and_nowhere_else :
  spec_unseal demo 5 demo_blob = Handle 21
  /\ spec_unseal demo 6 demo_blob = Refused
  /\ spec_unseal demo_debug 5 demo_blob = Refused
  /\ spec_unseal demo_erased 5 demo_blob = Refused
  /\ spec_unseal demo_flat 5 demo_blob = Refused :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Theorem the_convenient_unseal_ignores_the_measured_state :
  ~ BindsToTheMeasuredState demo (convenient_unseal demo).
Proof. intros H. specialize (H 6 demo_blob eq_refl). discriminate H. Qed.

Theorem the_portable_unseal_opens_production_material_on_a_debuggable_part :
  ~ DiversifiesByLifecycle demo_debug (portable_unseal demo_debug).
Proof. intros H. specialize (H 5 demo_blob eq_refl). discriminate H. Qed.

Theorem the_stale_unseal_survives_the_erase :
  ~ RefusesPastTheSealingRoot demo_erased (stale_unseal demo_erased).
Proof. intros H. specialize (H 5 demo_blob eq_refl). discriminate H. Qed.

Theorem the_best_effort_unseal_opens_on_a_failed_root :
  ~ UnsealsNothingOnAFailedRoot demo_flat (best_effort_unseal demo_flat).
Proof. intros H. specialize (H eq_refl 5 demo_blob). discriminate H. Qed.

Theorem the_exporting_unseal_hands_back_the_key :
  ~ ExportsNoKey demo (exporting_unseal demo).
Proof. exact (the_exporting_unseal_is_refuted demo eq_refl). Qed.

(* Each of the four refuted constructions agrees with the specification
   where its own gate is not the one being crossed, so the named defect and
   not the construction's shape is what refuses it. *)
Example the_four_refuted_unseals_agree_where_their_gate_is_not_crossed :
  convenient_unseal demo 5 demo_blob = Handle 21
  /\ portable_unseal demo 5 demo_blob = Handle 21
  /\ stale_unseal demo 5 demo_blob = Handle 21
  /\ best_effort_unseal demo 5 demo_blob = Handle 21
  /\ exporting_unseal demo 6 demo_blob = Refused :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* -------------------------------------------------------------------------
   The quote and the appraisal, at a machine.
   ------------------------------------------------------------------------- *)

Example the_specification_quote_at_two_machines :
  spec_quote demo = Some quote_vector /\ spec_quote demo_flat = None :=
  conj eq_refl eq_refl.

Theorem the_widened_quote_is_refuted :
  ~ CoversTheVectorExactly demo (widened_quote demo).
Proof.
  intros H. specialize (H (cons LifecycleFuseValue quote_vector) eq_refl).
  discriminate H.
Qed.

Theorem the_best_effort_quote_is_refuted :
  ~ CompletesNoQuoteOnAFailedRoot demo_flat (best_effort_quote demo_flat).
Proof. intros H. specialize (H eq_refl). discriminate H. Qed.

Example the_appraisal_holds_and_fails_where_it_should :
  spec_appraise demo quote_vector = true
  /\ spec_appraise demo_forked quote_vector = false
  /\ spec_appraise demo_stale quote_vector = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* Gap g priced rather than closed, as a computation rather than as a
   remark: with the chain term out of the vector a machine whose chain
   disagrees appraises clean, so the narrow reading is the one on which
   attestation stops deciding the chain. That is the argument reading 2
   rests on and the whole of it. The third conjunct is the honest limit of
   the other two: the vector they compute over is one `covers_exactly`
   refuses, because that check is written against the wide reading, so it
   records which reading this file took and settles nothing. *)
Theorem a_vector_without_the_chain_appraises_a_forked_chain :
  spec_appraise demo_forked (drop_at 0 quote_vector) = true
  /\ spec_appraise demo_forked quote_vector = false
  /\ covers_exactly (drop_at 0 quote_vector) = false.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

Theorem the_lenient_appraisal_is_refuted :
  ~ AppraisesEveryCoveredTerm demo_forked (lenient_appraise demo_forked).
Proof.
  intros H. specialize (H quote_vector ChainDigest eq_refl eq_refl).
  discriminate H.
Qed.

(* And it still refuses a term it does check, so what refutes it is the term
   it skips and not a weaker comparison. *)
Example the_lenient_appraisal_refuses_a_term_it_checks :
  lenient_appraise demo_forked quote_vector = true
  /\ lenient_appraise demo_stale quote_vector = false
  /\ lenient_appraise demo quote_vector = true :=
  conj eq_refl (conj eq_refl eq_refl).

(* -------------------------------------------------------------------------
   Anti-rollback, at a machine.
   ------------------------------------------------------------------------- *)

Example the_floor_admits_at_and_above_and_refuses_below :
  bootable demo 3 = false /\ bootable demo 4 = true /\ bootable demo 5 = true
  := conj eq_refl (conj eq_refl eq_refl).

Theorem the_strict_reading_refuses_the_floor_itself :
  ~ TheFloorItselfBoots demo (strictly_above demo).
Proof. intros H. discriminate H. Qed.

Theorem the_visible_is_bootable_selection_is_refuted :
  ~ NothingBelowTheFloorBoots demo (visible_is_bootable demo).
Proof. intros H. specialize (H 0 eq_refl). discriminate H. Qed.

Example the_floor_advance_and_the_two_refuted_ones :
  spec_floor 4 7 = 7 /\ spec_floor 7 4 = 7
  /\ trusting_floor 7 4 = 4 /\ frozen_floor 4 7 = 4 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_boot_count_bound :
  spec_boot_admits demo 2 = true /\ spec_boot_admits demo 3 = false
  /\ unbounded_boot demo 7 = true /\ refusing_boot demo 0 = false
  := conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem the_unbounded_boot_is_refuted :
  ~ RevertsPastTheBound demo (unbounded_boot demo).
Proof. intros H. specialize (H 7 eq_refl). discriminate H. Qed.

(* And the other side of R-09-028's counting, which a single-sided
   statement would leave standing: an admission that boots nothing reverts
   past the bound and is not what the bound was counted for. *)
Theorem the_refusing_boot_is_refuted :
  ~ AdmitsBelowTheBound demo (refusing_boot demo).
Proof. intros H. specialize (H 0 eq_refl). discriminate H. Qed.

Example the_charge_and_the_two_refuted_ones :
  spec_charge EntropyHalt 2 = 2 /\ spec_charge OrdinaryFailure 2 = 3
  /\ uniform_charge EntropyHalt 2 = 3 /\ forgiving_charge OrdinaryFailure 2 = 2
  := conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_revert_and_the_stuck_one :
  spec_revert SlotA = SlotB /\ spec_revert SlotB = SlotA
  /\ stuck_revert SlotA = SlotA := conj eq_refl (conj eq_refl eq_refl).

Example the_settlement_and_the_refunding_one :
  spec_settle true 2 = 2 /\ refunding_settle true 2 = 1
  /\ refunding_settle false 2 = 2 := conj eq_refl (conj eq_refl eq_refl).

Example the_attempt_order_and_the_reversed_one :
  precedes attempt_eqb ChargeTheCounter CompareTheCredential spec_attempt = true
  /\ precedes attempt_eqb ChargeTheCounter CompareTheCredential
              compare_first_attempt = false := conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   The roots, the scheme split, and the Debug Module's production gate, at a
   machine.
   ------------------------------------------------------------------------- *)

Example the_rom_accepts_the_production_root_alone :
  spec_rom demo 3 = true /\ spec_rom demo 2 = false
  /\ spec_rom demo_debug 2 = true /\ spec_rom demo_debug 3 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem the_unlockable_rom_is_refuted :
  ~ AcceptsNoSecondRoot demo (unlockable_rom demo 9).
Proof. exact (the_unlockable_rom_accepts_a_second_root demo 9 eq_refl). Qed.

Theorem the_foreign_rooted_rom_is_refuted :
  ~ AcceptsTheStatesOwnRoot demo (foreign_rooted_rom demo 2).
Proof. exact (the_foreign_rooted_rom_refuses_the_states_own_root demo 2 eq_refl). Qed.

Example the_two_refuted_roms_at_a_production_part :
  unlockable_rom demo 9 3 = true /\ unlockable_rom demo 9 9 = true
  /\ foreign_rooted_rom demo 2 2 = true /\ foreign_rooted_rom demo 2 3 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_scheme_split_at_the_four_stages :
  map_over (fun s => spec_scheme demo s 0) all_stages
  = cons SlhDsa (cons SlhDsa (cons MlDsa (cons MlDsa nil)))
  /\ signer_chosen_scheme demo CoreKernels 0 = SlhDsa
  /\ signer_chosen_scheme demo CoreKernels 1 = MlDsa :=
  conj eq_refl (conj eq_refl eq_refl).

Theorem the_signer_chosen_scheme_is_refuted :
  ~ ChosenByTheVerifier demo (signer_chosen_scheme demo).
Proof. exact (the_signer_chosen_scheme_reads_the_signer demo CoreKernels eq_refl). Qed.

Theorem the_uniform_scheme_is_refuted :
  ~ RomVerifiesWithSlhDsa demo (uniform_ml_scheme demo).
Proof. exact (the_uniform_scheme_denies_the_rom_slh_dsa demo RotRuntime eq_refl). Qed.

(* -------------------------------------------------------------------------
   The Debug Module's table and its authenticated entry, at a machine.
   ------------------------------------------------------------------------- *)

(* The specification machine carries R-09-034's table, so the three clauses
   above are proved of something rather than only of a hypothesis. *)
Theorem the_demo_machine_carries_the_registers_debug_table :
  CarriesTheRegistersDebugTable demo.
Proof. intros l. destruct l; reflexivity. Qed.

Example the_demo_machine_satisfies_the_three_debug_clauses :
  demo.(debug_live) Production = false
  /\ demo.(debug_live) Development = true
  /\ demo.(debug_live) Rma = true
  /\ demo.(debug_live) Raw = false
  /\ demo.(debug_live) TestState = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* The three refused machines, each breaking what it breaks and keeping what
   it leaves standing. Two of them break one clause; the third breaks two,
   and it breaks two necessarily rather than incidentally, D3 carrying D1 so
   that no table opens production without also opening a state R-09-034
   closes. That is `constant_revert`'s shape one section over: a construction
   that crosses two obligations at once is stated as crossing both. *)
Theorem the_open_machine_leaves_the_debug_module_live_in_production :
  ~ ClosesTheDebugModuleInProduction demo_open
  /\ ~ ClosesTheDebugModuleEverywhereElse demo_open.
Proof.
  split.
  - intros H. discriminate H.
  - intros H. specialize (H Production eq_refl eq_refl). discriminate H.
Qed.

(* And it keeps the one clause it leaves standing, named as the predicate it
   is rather than read off the field state by state, so the machine is
   refuted by D1 and D3 and by nothing else this section states. *)
Theorem the_open_machine_keeps_the_clause_it_leaves_standing :
  OpensTheDebugModuleWhereTheEntryDoes demo_open.
Proof. split; reflexivity. Qed.

Theorem the_dark_machine_closes_the_state_the_entry_opens :
  ~ OpensTheDebugModuleWhereTheEntryDoes demo_dark.
Proof. intros [ H _ ]. discriminate H. Qed.

Theorem the_dark_machine_keeps_the_other_two_clauses :
  ClosesTheDebugModuleInProduction demo_dark
  /\ ClosesTheDebugModuleEverywhereElse demo_dark.
Proof.
  split; [ reflexivity | ].
  intros l Hd Hr. destruct l.
  - reflexivity.
  - reflexivity.
  - reflexivity.
  - reflexivity.
  - discriminate Hr.
Qed.

Theorem the_test_live_machine_opens_a_closed_manufacturing_state :
  ~ ClosesTheDebugModuleEverywhereElse demo_test_live.
Proof. intros H. specialize (H TestState eq_refl eq_refl). discriminate H. Qed.

Theorem the_test_live_machine_keeps_the_other_two_clauses :
  ClosesTheDebugModuleInProduction demo_test_live
  /\ OpensTheDebugModuleWhereTheEntryDoes demo_test_live.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* And the converse of D3 fails at that same machine, which is what keeps
   the production gate and the closure of every other state apart. *)
Theorem closing_production_does_not_close_every_other_state :
  ClosesTheDebugModuleInProduction demo_test_live
  /\ ~ ClosesTheDebugModuleEverywhereElse demo_test_live.
Proof.
  split; [ reflexivity | exact the_test_live_machine_opens_a_closed_manufacturing_state ].
Qed.

(* R-15-079's entry, at a machine: the two refuted decisions each cross the
   obligation their twin above keeps. *)
Example the_specification_entry_at_the_five_states :
  spec_debug_entry demo Development 32 = true
  /\ spec_debug_entry demo Development 31 = false
  /\ spec_debug_entry demo Rma 34 = true
  /\ spec_debug_entry demo Production 33 = false
  /\ spec_debug_entry demo TestState 31 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Theorem the_unauthenticated_entry_asks_for_no_response :
  ~ EntersOnlyOnTheResponse demo (unauthenticated_entry demo).
Proof. intros H. specialize (H Development 0 eq_refl). discriminate H. Qed.

Theorem the_software_gated_entry_enters_a_production_part :
  ~ EntersNoClosedState demo (software_gated_entry demo).
Proof. intros H. specialize (H Production 33 eq_refl). discriminate H. Qed.

(* The two agree with the specification where their own obligation is not
   the one being crossed, so the named defect and not the decision's shape
   is what refuses each. *)
Example the_two_refuted_entries_agree_where_their_obligation_is_not_crossed :
  unauthenticated_entry demo Development 32 = true
  /\ unauthenticated_entry demo Production 33 = false
  /\ software_gated_entry demo Development 32 = true
  /\ software_gated_entry demo Development 31 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The refused tables change the table and nothing else: every obligation
   this file states of a machine outside R-09-034's own three clauses holds
   of all three, which is what makes each a refutation of one clause rather
   than a machine that fails generally. *)
Theorem the_refused_tables_break_nothing_but_the_table :
  BindsToTheMeasuredState demo_open (spec_unseal demo_open)
  /\ DiversifiesByLifecycle demo_dark (spec_unseal demo_dark)
  /\ CoversTheVectorExactly demo_test_live (spec_quote demo_test_live)
  /\ AcceptsNoSecondRoot demo_open (spec_rom demo_open)
  /\ ChosenByTheVerifier demo_dark (spec_scheme demo_dark).
Proof.
  split; [ exact (the_specification_unseal_binds_to_the_measured_state demo_open) | ].
  split; [ exact (the_specification_unseal_diversifies_by_lifecycle demo_dark) | ].
  split; [ exact (the_specification_quote_covers_the_vector_exactly demo_test_live) | ].
  split; [ exact (the_specification_rom_accepts_no_second_root demo_open) | ].
  exact (the_specification_scheme_is_chosen_by_the_verifier demo_dark).
Qed.



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
Print Assumptions upto.
Print Assumptions before_last.
Print Assumptions only_if.
Print Assumptions bool_eqb.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions only_if_elim.
Print Assumptions bool_eqb_sound.
Print Assumptions nat_eqb_refl.
Print Assumptions nat_eqb_sound.
Print Assumptions nat_leb_refl.
Print Assumptions nat_eqb_sym.
Print Assumptions negb_true.
Print Assumptions the_empty_conjunction_holds.
Print Assumptions the_empty_disjunction_fails.
Print Assumptions nothing_has_length_zero.
Print Assumptions before_last_of_nothing.
Print Assumptions the_index_set_of_three.
Print Assumptions only_if_is_implication.
Print Assumptions bool_eqb_is_agreement.
Print Assumptions member.
Print Assumptions pos_from.
Print Assumptions pos.
Print Assumptions occurrences.
Print Assumptions precedes.
Print Assumptions all_of_member.
Print Assumptions nat_ltb_irrefl.
Print Assumptions pos_from_none.
Print Assumptions precedence_is_strict.
Print Assumptions an_absent_member_precedes_nothing.
Print Assumptions distinct.
Print Assumptions the_empty_list_is_distinct.
Print Assumptions a_repeated_number_is_not_distinct.
Print Assumptions member_here_or_there.
Print Assumptions member_nat_absent.
Print Assumptions member_map.
Print Assumptions distinct_separates.
Print Assumptions swap_at.
Print Assumptions drop_at.
Print Assumptions suffix_at.
Print Assumptions insert_at.
Print Assumptions transpositions.
Print Assumptions deletions.
Print Assumptions proper_suffixes.
Print Assumptions duplications.
Print Assumptions Lifecycle.
Print Assumptions all_lifecycles.
Print Assumptions there_are_five_lifecycle_states.
Print Assumptions lifecycle_eqb.
Print Assumptions lifecycle_eqb_refl.
Print Assumptions lifecycle_eqb_sound.
Print Assumptions Stage.
Print Assumptions all_stages.
Print Assumptions there_are_four_stages.
Print Assumptions stage_eqb.
Print Assumptions stage_eqb_refl.
Print Assumptions stage_eqb_sound.
Print Assumptions BootKind.
Print Assumptions all_kinds.
Print Assumptions there_are_three_boot_kinds.
Print Assumptions Counter.
Print Assumptions all_counters.
Print Assumptions there_are_four_counters.
Print Assumptions counter_eqb.
Print Assumptions counter_eqb_refl.
Print Assumptions counter_eqb_sound.
Print Assumptions Event.
Print Assumptions all_events.
Print Assumptions there_are_six_counter_events.
Print Assumptions Field.
Print Assumptions all_fields.
Print Assumptions there_are_six_named_terms.
Print Assumptions field_eqb.
Print Assumptions field_eqb_refl.
Print Assumptions field_eqb_sound.
Print Assumptions Scheme.
Print Assumptions all_schemes.
Print Assumptions there_are_two_signature_schemes.
Print Assumptions Slot.
Print Assumptions all_slots.
Print Assumptions there_are_two_image_slots.
Print Assumptions Outcome.
Print Assumptions all_outcomes.
Print Assumptions there_are_two_boot_failure_classes.
Print Assumptions Answer.
Print Assumptions is_cleartext.
Print Assumptions only_the_third_answer_is_cleartext.
Print Assumptions Item.
Print Assumptions all_items.
Print Assumptions the_chain_measures_seven_things.
Print Assumptions item_eqb.
Print Assumptions item_eqb_refl.
Print Assumptions item_eqb_sound.
Print Assumptions Step.
Print Assumptions step_eqb.
Print Assumptions step_eqb_refl.
Print Assumptions step_eqb_sound.
Print Assumptions AttemptStep.
Print Assumptions attempt_eqb.
Print Assumptions attempt_eqb_refl.
Print Assumptions attempt_eqb_sound.
Print Assumptions every_stage_is_in_the_roster.
Print Assumptions every_item_is_in_the_roster.
Print Assumptions every_field_is_in_the_roster.
Print Assumptions every_counter_is_in_the_roster.
Print Assumptions all_of_stages.
Print Assumptions all_of_items.
Print Assumptions all_of_fields.
Print Assumptions all_of_counters.
Print Assumptions extension_points.
Print Assumptions separates_at.
Print Assumptions separates_along.
Print Assumptions nothing_is_extended_from_no_item.
Print Assumptions Machine.
Print Assumptions input_prologue.
Print Assumptions stage_chain.
Print Assumptions chain_from.
Print Assumptions boot_steps.
Print Assumptions the_specification_chain_has_eleven_steps.
Print Assumptions the_lifecycle_extension_stands_at_the_first_position.
Print Assumptions lifecycle_extended_first.
Print Assumptions measured_before_run.
Print Assumptions every_stage_runs_once.
Print Assumptions every_input_extended_once.
Print Assumptions stages_in_chain_order.
Print Assumptions the_empty_stage_order_is_trivially_ordered.
Print Assumptions verdict_before_any_run.
Print Assumptions chain_ok.
Print Assumptions IsAMeasuredChain.
Print Assumptions chain_ok_sound.
Print Assumptions chain_ok_complete.
Print Assumptions a_measured_chain_records_a_stage_before_it_runs.
Print Assumptions a_measured_chain_extends_the_lifecycle_first.
Print Assumptions a_measured_chain_records_the_verdict_before_any_stage_runs.
Print Assumptions a_step_the_chain_omits_precedes_nothing.
Print Assumptions no_step_of_the_chain_precedes_itself.
Print Assumptions the_specification_chain_is_a_measured_chain.
Print Assumptions Loader.
Print Assumptions spec_loader.
Print Assumptions IsTheOnePath.
Print Assumptions the_specification_loader_is_the_one_path.
Print Assumptions the_one_path_carries_the_measured_chain.
Print Assumptions resume_loader.
Print Assumptions the_resume_loader_is_a_second_loader.
Print Assumptions without_the_one_path_the_cold_boot_check_decides_nothing.
Print Assumptions digest_of.
Print Assumptions Observation.
Print Assumptions Digest.
Print Assumptions spec_digest.
Print Assumptions IsReproducible.
Print Assumptions the_specification_digest_is_reproducible.
Print Assumptions chain_extension_points.
Print Assumptions the_specification_chain_extends_from_the_declared_digests.
Print Assumptions the_specification_chain_extends_from_seven_digests.
Print Assumptions a_declared_digest_separates_the_items.
Print Assumptions a_different_measurement_moves_the_digest.
Print Assumptions attempt_folding_digest.
Print Assumptions the_attempt_folding_digest_agrees_where_nothing_was_observed.
Print Assumptions stage_weakenings.
Print Assumptions the_stage_family_size.
Print Assumptions every_stage_weakening_is_refused.
Print Assumptions every_stage_transposition_breaks_the_chain_order.
Print Assumptions every_stage_transposition_still_runs_each_stage_once.
Print Assumptions every_stage_deletion_leaves_a_stage_unrun.
Print Assumptions every_proper_suffix_leaves_a_stage_unrun.
Print Assumptions every_stage_duplication_runs_a_stage_twice.
Print Assumptions every_stage_deletion_leaves_an_item_unextended.
Print Assumptions no_transposition_of_the_stage_order_is_a_chain.
Print Assumptions no_deletion_from_the_stage_order_is_a_chain.
Print Assumptions no_proper_suffix_of_the_stage_order_is_a_chain.
Print Assumptions no_duplication_in_the_stage_order_is_a_chain.
Print Assumptions prologue_weakenings.
Print Assumptions the_prologue_family_size.
Print Assumptions eleven_of_the_twelve_prologue_weakenings_are_refused.
Print Assumptions the_admitted_prologue_weakening_transposes_the_verdict.
Print Assumptions transposing_the_lifecycle_extension_breaks_the_chain.
Print Assumptions transposing_the_verdict_with_the_latch_does_not.
Print Assumptions no_deletion_from_the_prologue_is_a_chain.
Print Assumptions no_proper_suffix_of_the_prologue_is_a_chain.
Print Assumptions no_duplication_in_the_prologue_is_a_chain.
Print Assumptions every_prologue_duplication_extends_an_input_twice.
Print Assumptions the_prologue_duplications_break_no_other_conjunct.
Print Assumptions unmeasured_run_chain.
Print Assumptions the_unmeasured_run_executes_before_it_records.
Print Assumptions late_lifecycle_chain.
Print Assumptions the_late_lifecycle_chain_extends_it_second.
Print Assumptions blind_entropy_chain.
Print Assumptions the_blind_entropy_chain_draws_before_the_verdict.
Print Assumptions front_loaded_chain.
Print Assumptions the_front_loaded_chain_satisfies_every_stated_obligation.
Print Assumptions the_two_admitted_chain_shapes_differ.
Print Assumptions Blob.
Print Assumptions Unseal.
Print Assumptions unseal_admits.
Print Assumptions spec_unseal.
Print Assumptions spec_seal.
Print Assumptions BindsToTheMeasuredState.
Print Assumptions DiversifiesByLifecycle.
Print Assumptions RefusesPastTheSealingRoot.
Print Assumptions UnsealsNothingOnAFailedRoot.
Print Assumptions ExportsNoKey.
Print Assumptions the_specification_unseal_binds_to_the_measured_state.
Print Assumptions the_specification_unseal_diversifies_by_lifecycle.
Print Assumptions the_specification_unseal_refuses_past_the_sealing_root.
Print Assumptions the_specification_unseal_fails_closed_on_a_failed_root.
Print Assumptions the_specification_unseal_exports_no_key.
Print Assumptions a_blob_sealed_here_unseals_here.
Print Assumptions convenient_unseal.
Print Assumptions the_convenient_unseal_keeps_the_other_four.
Print Assumptions portable_unseal.
Print Assumptions the_portable_unseal_keeps_the_other_four.
Print Assumptions stale_unseal.
Print Assumptions the_stale_unseal_keeps_the_other_four.
Print Assumptions best_effort_unseal.
Print Assumptions the_best_effort_unseal_keeps_the_other_four.
Print Assumptions exporting_unseal.
Print Assumptions the_exporting_unseal_keeps_all_four_gates.
Print Assumptions the_exporting_unseal_is_refuted.
Print Assumptions quote_vector.
Print Assumptions the_vector_carries_five_terms.
Print Assumptions the_vector_excludes_the_lifecycle_fuse.
Print Assumptions covers_exactly.
Print Assumptions Quote.
Print Assumptions spec_quote.
Print Assumptions CoversTheVectorExactly.
Print Assumptions CompletesNoQuoteOnAFailedRoot.
Print Assumptions the_specification_quote_covers_the_vector_exactly.
Print Assumptions the_specification_quote_completes_nothing_on_a_failed_root.
Print Assumptions vector_weakenings.
Print Assumptions the_vector_family_size.
Print Assumptions every_vector_weakening_is_refused.
Print Assumptions every_vector_deletion_drops_a_term.
Print Assumptions every_widening_adds_the_term_the_chain_already_carries.
Print Assumptions every_duplication_states_a_term_twice.
Print Assumptions the_vector_is_a_set_and_not_an_order.
Print Assumptions there_are_four_vector_transpositions.
Print Assumptions no_deletion_from_the_vector_covers_it.
Print Assumptions no_widening_of_the_vector_covers_it.
Print Assumptions no_duplication_in_the_vector_covers_it.
Print Assumptions widened_quote.
Print Assumptions the_widened_quote_still_fails_closed.
Print Assumptions best_effort_quote.
Print Assumptions the_best_effort_quote_covers_the_vector_exactly.
Print Assumptions Appraisal.
Print Assumptions spec_appraise.
Print Assumptions AppraisesEveryCoveredTerm.
Print Assumptions the_specification_appraisal_reaches_every_covered_term.
Print Assumptions occurrences_gives_member.
Print Assumptions a_covered_vector_carries_the_chain.
Print Assumptions an_appraisal_over_a_covered_vector_decides_the_chain.
Print Assumptions the_specification_appraisal_over_a_covered_vector_decides_the_chain.
Print Assumptions lenient_appraise.
Print Assumptions the_lenient_appraisal_still_reaches_the_other_terms.
Print Assumptions bootable.
Print Assumptions Selection.
Print Assumptions NothingBelowTheFloorBoots.
Print Assumptions TheFloorItselfBoots.
Print Assumptions the_specification_selection_refuses_below_the_floor.
Print Assumptions the_specification_selection_admits_the_floor_itself.
Print Assumptions strictly_above.
Print Assumptions nat_ltb_gives_leb.
Print Assumptions the_strict_reading_still_refuses_below_the_floor.
Print Assumptions visible_is_bootable.
Print Assumptions the_visible_is_bootable_selection_admits_the_floor.
Print Assumptions Floor.
Print Assumptions spec_floor.
Print Assumptions NeverDescends.
Print Assumptions ReachesTheDeclaredFloor.
Print Assumptions nat_ltb_false_gives_leb.
Print Assumptions the_specification_floor_never_descends.
Print Assumptions the_specification_floor_reaches_the_declared_value.
Print Assumptions trusting_floor.
Print Assumptions the_trusting_floor_still_reaches_the_declared_value.
Print Assumptions the_trusting_floor_descends.
Print Assumptions frozen_floor.
Print Assumptions the_frozen_floor_never_descends.
Print Assumptions the_frozen_floor_never_reaches_the_declared_value.
Print Assumptions forgetful_floor.
Print Assumptions the_forgetful_floor_reaches_a_strictly_newer_value.
Print Assumptions the_forgetful_floor_loses_the_floor_it_holds.
Print Assumptions the_forgetful_floor_descends.
Print Assumptions advances_on.
Print Assumptions the_counter_event_table.
Print Assumptions Advancement.
Print Assumptions NeverOnADataCommit.
Print Assumptions EveryCounterAdvancesOnSomething.
Print Assumptions the_specification_advancement_spares_the_data_commit.
Print Assumptions the_specification_advancement_leaves_no_counter_dead.
Print Assumptions no_counter_of_the_enumeration_advances_on_a_data_commit.
Print Assumptions commit_advancing.
Print Assumptions the_commit_advancing_table.
Print Assumptions the_commit_advancing_table_leaves_no_counter_dead.
Print Assumptions the_commit_advancing_table_spends_the_counter_on_a_commit.
Print Assumptions dead_attempt_counter.
Print Assumptions the_dead_attempt_counter_table.
Print Assumptions the_dead_attempt_counter_spares_the_data_commit.
Print Assumptions the_dead_attempt_counter_is_dead.
Print Assumptions BootAdmission.
Print Assumptions spec_boot_admits.
Print Assumptions RevertsPastTheBound.
Print Assumptions AdmitsBelowTheBound.
Print Assumptions the_specification_boot_admission_reverts_past_the_bound.
Print Assumptions the_specification_boot_admission_admits_below_the_bound.
Print Assumptions unbounded_boot.
Print Assumptions the_unbounded_boot_still_admits_below_the_bound.
Print Assumptions refusing_boot.
Print Assumptions the_refusing_boot_reverts_past_the_bound.
Print Assumptions Charge.
Print Assumptions spec_charge.
Print Assumptions SpendsNoAttemptOnTheEntropyHalt.
Print Assumptions ChargesTheOrdinaryFailure.
Print Assumptions the_specification_charge_spares_the_entropy_halt.
Print Assumptions the_specification_charge_spends_on_the_ordinary_failure.
Print Assumptions uniform_charge.
Print Assumptions the_uniform_charge_still_spends_on_the_ordinary_failure.
Print Assumptions the_uniform_charge_spends_on_the_entropy_halt.
Print Assumptions forgiving_charge.
Print Assumptions the_forgiving_charge_spares_the_entropy_halt.
Print Assumptions the_forgiving_charge_counts_nothing.
Print Assumptions Revert.
Print Assumptions spec_revert.
Print Assumptions RevertsToTheOtherSlot.
Print Assumptions IsAnInvolution.
Print Assumptions the_specification_revert_reaches_the_other_slot.
Print Assumptions the_specification_revert_is_an_involution.
Print Assumptions reaching_the_other_slot_gives_the_involution.
Print Assumptions stuck_revert.
Print Assumptions the_stuck_revert_is_an_involution.
Print Assumptions the_stuck_revert_reverts_to_nothing.
Print Assumptions constant_revert.
Print Assumptions the_constant_revert_is_not_an_involution.
Print Assumptions the_constant_revert_reverts_to_nothing.
Print Assumptions spec_attempt.
Print Assumptions AdvancesBeforeTheComparison.
Print Assumptions the_specification_attempt_charges_before_it_compares.
Print Assumptions compare_first_attempt.
Print Assumptions the_compare_first_attempt_still_takes_both_steps.
Print Assumptions the_compare_first_attempt_compares_before_it_charges.
Print Assumptions Settle.
Print Assumptions spec_settle.
Print Assumptions RefundsNothing.
Print Assumptions KeepsTheCompletedAttempt.
Print Assumptions the_specification_settlement_refunds_nothing.
Print Assumptions the_specification_settlement_keeps_the_completed_attempt.
Print Assumptions refunding_settle.
Print Assumptions the_refunding_settlement_keeps_the_completed_attempt.
Print Assumptions the_refunding_settlement_refunds.
Print Assumptions double_charging_settle.
Print Assumptions the_double_charging_settlement_refunds_nothing.
Print Assumptions the_double_charging_settlement_charges_a_completed_attempt_twice.
Print Assumptions Rom.
Print Assumptions spec_rom.
Print Assumptions AcceptsTheStatesOwnRoot.
Print Assumptions AcceptsNoSecondRoot.
Print Assumptions the_specification_rom_accepts_the_states_own_root.
Print Assumptions the_specification_rom_accepts_no_second_root.
Print Assumptions unlockable_rom.
Print Assumptions the_unlockable_rom_takes_the_states_own_root.
Print Assumptions the_unlockable_rom_takes_the_token.
Print Assumptions the_unlockable_rom_still_accepts_the_states_own_root.
Print Assumptions the_unlockable_rom_accepts_a_second_root.
Print Assumptions foreign_rooted_rom.
Print Assumptions the_foreign_rooted_rom_accepts_no_second_root.
Print Assumptions the_foreign_rooted_rom_refuses_the_states_own_root.
Print Assumptions Signer.
Print Assumptions SchemeChoice.
Print Assumptions spec_scheme.
Print Assumptions ChosenByTheVerifier.
Print Assumptions RomVerifiesWithSlhDsa.
Print Assumptions the_specification_scheme_is_chosen_by_the_verifier.
Print Assumptions the_specification_scheme_gives_the_rom_slh_dsa.
Print Assumptions signer_chosen_scheme.
Print Assumptions the_signer_chosen_scheme_still_gives_the_rom_slh_dsa.
Print Assumptions the_signer_chosen_scheme_reads_the_signer.
Print Assumptions uniform_ml_scheme.
Print Assumptions the_uniform_scheme_is_chosen_by_the_verifier.
Print Assumptions the_uniform_scheme_denies_the_rom_slh_dsa.
Print Assumptions debug_table.
Print Assumptions the_register_closes_the_debug_table.
Print Assumptions ClosesTheDebugModuleInProduction.
Print Assumptions OpensTheDebugModuleWhereTheEntryDoes.
Print Assumptions ClosesTheDebugModuleEverywhereElse.
Print Assumptions CarriesTheRegistersDebugTable.
Print Assumptions the_registers_table_closes_production.
Print Assumptions the_registers_table_opens_development_and_rma.
Print Assumptions the_registers_table_closes_every_other_state.
Print Assumptions closing_every_other_state_closes_production.
Print Assumptions the_two_independent_clauses_fix_the_table.
Print Assumptions live_in_production_table.
Print Assumptions dark_debug_table.
Print Assumptions test_live_table.
Print Assumptions the_three_refused_tables_beside_the_registers.
Print Assumptions Credential.
Print Assumptions DebugEntry.
Print Assumptions spec_debug_entry.
Print Assumptions EntersNoClosedState.
Print Assumptions EntersOnlyOnTheResponse.
Print Assumptions the_specification_entry_opens_no_closed_state.
Print Assumptions the_specification_entry_takes_only_the_response.
Print Assumptions the_specification_entry_admits_the_authenticated_response.
Print Assumptions unauthenticated_entry.
Print Assumptions the_unauthenticated_entry_opens_no_closed_state.
Print Assumptions software_gated_entry.
Print Assumptions the_software_gated_entry_takes_only_the_response.
Print Assumptions demo_item_code.
Print Assumptions the_demo_measurement_encoding.
Print Assumptions demo_debug_response.
Print Assumptions the_demo_debug_responses.
Print Assumptions demo_accepted_root.
Print Assumptions the_demo_roots_are_diversified.
Print Assumptions demo_rom_verifies.
Print Assumptions the_demo_rom_verifies_the_first_two_stages.
Print Assumptions demo_counter.
Print Assumptions erased_counter.
Print Assumptions the_demo_counters_and_the_advanced_one.
Print Assumptions demo_witness.
Print Assumptions forked_witness.
Print Assumptions stale_witness.
Print Assumptions the_three_witness_sets.
Print Assumptions demo_extend_separates_on_the_chain.
Print Assumptions demo_with.
Print Assumptions demo.
Print Assumptions demo_debug.
Print Assumptions demo_erased.
Print Assumptions demo_flat.
Print Assumptions demo_forked.
Print Assumptions demo_stale.
Print Assumptions demo_open.
Print Assumptions demo_dark.
Print Assumptions demo_test_live.
Print Assumptions the_demo_machine_declares.
Print Assumptions the_entropy_verdict_at_every_demo_machine.
Print Assumptions the_lifecycle_state_at_every_demo_machine.
Print Assumptions the_debug_table_at_every_demo_machine.
Print Assumptions the_demo_extension_is_order_sensitive.
Print Assumptions the_demo_chain_extends_from_these_digests.
Print Assumptions counting_extend.
Print Assumptions late_colliding_extend.
Print Assumptions the_counting_extension_separates_nothing.
Print Assumptions the_late_collision_passes_the_seed_and_fails_the_chain.
Print Assumptions the_late_collision_is_the_demo_extension_elsewhere.
Print Assumptions the_attempt_folding_digest_is_refuted.
Print Assumptions the_attempt_folding_digest_agrees_at_the_first_attempt.
Print Assumptions the_two_prologue_orders_measure_differently.
Print Assumptions the_two_admitted_chain_shapes_measure_alike.
Print Assumptions demo_blob.
Print Assumptions the_demo_blob_declares.
Print Assumptions the_blob_opens_here_and_nowhere_else.
Print Assumptions the_convenient_unseal_ignores_the_measured_state.
Print Assumptions the_portable_unseal_opens_production_material_on_a_debuggable_part.
Print Assumptions the_stale_unseal_survives_the_erase.
Print Assumptions the_best_effort_unseal_opens_on_a_failed_root.
Print Assumptions the_exporting_unseal_hands_back_the_key.
Print Assumptions the_four_refuted_unseals_agree_where_their_gate_is_not_crossed.
Print Assumptions the_specification_quote_at_two_machines.
Print Assumptions the_widened_quote_is_refuted.
Print Assumptions the_best_effort_quote_is_refuted.
Print Assumptions the_appraisal_holds_and_fails_where_it_should.
Print Assumptions a_vector_without_the_chain_appraises_a_forked_chain.
Print Assumptions the_lenient_appraisal_is_refuted.
Print Assumptions the_lenient_appraisal_refuses_a_term_it_checks.
Print Assumptions the_floor_admits_at_and_above_and_refuses_below.
Print Assumptions the_strict_reading_refuses_the_floor_itself.
Print Assumptions the_visible_is_bootable_selection_is_refuted.
Print Assumptions the_floor_advance_and_the_two_refuted_ones.
Print Assumptions the_boot_count_bound.
Print Assumptions the_unbounded_boot_is_refuted.
Print Assumptions the_refusing_boot_is_refuted.
Print Assumptions the_charge_and_the_two_refuted_ones.
Print Assumptions the_revert_and_the_stuck_one.
Print Assumptions the_settlement_and_the_refunding_one.
Print Assumptions the_attempt_order_and_the_reversed_one.
Print Assumptions the_rom_accepts_the_production_root_alone.
Print Assumptions the_unlockable_rom_is_refuted.
Print Assumptions the_foreign_rooted_rom_is_refuted.
Print Assumptions the_two_refuted_roms_at_a_production_part.
Print Assumptions the_scheme_split_at_the_four_stages.
Print Assumptions the_signer_chosen_scheme_is_refuted.
Print Assumptions the_uniform_scheme_is_refuted.
Print Assumptions the_demo_machine_carries_the_registers_debug_table.
Print Assumptions the_demo_machine_satisfies_the_three_debug_clauses.
Print Assumptions the_open_machine_leaves_the_debug_module_live_in_production.
Print Assumptions the_open_machine_keeps_the_clause_it_leaves_standing.
Print Assumptions the_dark_machine_closes_the_state_the_entry_opens.
Print Assumptions the_dark_machine_keeps_the_other_two_clauses.
Print Assumptions the_test_live_machine_opens_a_closed_manufacturing_state.
Print Assumptions the_test_live_machine_keeps_the_other_two_clauses.
Print Assumptions closing_production_does_not_close_every_other_state.
Print Assumptions the_specification_entry_at_the_five_states.
Print Assumptions the_unauthenticated_entry_asks_for_no_response.
Print Assumptions the_software_gated_entry_enters_a_production_part.
Print Assumptions the_two_refuted_entries_agree_where_their_obligation_is_not_crossed.
Print Assumptions the_refused_tables_break_nothing_but_the_table.
