(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   JournalIndex.v

   The two lowest storage layers as the register fixes them. R-10-002 names
   the roster and the prover: L0 is the Perennial/GoJournal-lineage
   crash-safe write-ahead log and L1 is the VeriBetrFS B^epsilon-tree
   design, both re-proved on one prover, and its acceptance clause is about
   each layer's proof being a Coq artifact. That entry states no property of
   a commit at all, so the multi-block atomicity obligation below is owed at
   R-10-036, whose checkpoint is committed as a single L0 transaction and
   whose acceptance clause is that no partially updated region is ever
   committed. Beside those two: R-10-003's one parametric index generic over
   key type, verified once and instantiated per object class; R-10-004's
   B^epsilon buffered-update refinement with the plain copy-on-write B+ tree
   named as its fallback; R-10-001a's torn or misdirected write costing a
   copy and not the generation, and its candidates verified on their own
   bytes; R-10-010's retained snapshot roots and refcounted copy-on-write
   extent sharing, which is the section-10 entry the copy-on-write
   allocation discipline below is read from; R-10-021's below-the-line block
   services free to move a block; R-10-022a's nonce and tag held by the
   index node that references the extent and never beside the ciphertext;
   R-10-009's whole stack outside the trust base; R-16-003's machine-checked
   crash consistency and R-16-005's "nothing is lost but uncommitted work";
   and R-12-026 and R-12-030 on a device code that composes with this layer
   rather than replacing it.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. Every quantity the register
   leaves to composition is a field of the Machine record, of the Commit
   record, or of the KeyAlgebra record, rather than a literal or a top-level
   Parameter, which is what keeps the R-05-163 assumption gate green while
   leaving the decision where its owner can make it. Nothing is admitted and
   nothing is axiomatized: the Print Assumptions block at the end reports
   every shipped constant closed under the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. No constant here is compiled,
   lowered, or run on either emulator, and nothing here executes anywhere.
   The computed checks are decided inside the kernel by conversion and print
   nothing. In particular no byte below reaches a device: R-12-025's raw
   NAND, R-12-026's per-page code and R-12-029's patrol scrub are not
   modelled, and R-12-030 is the reason that is admissible rather than a
   hole, the device code composing with this layer rather than replacing it.

   What is deferred, and to which item. R-10-005, R-10-005a, R-10-005b and
   R-10-005c are L2 and are M5.2's, so no inode, dirent, xattr, live query,
   namespace identifier or secondary index appears below; R-10-016's
   cross-domain incomparability and R-10-022's AEAD are L3 and the crypto
   core's, so the `mac` field here is an opaque function the filesystem
   never opens and no cipher, key, nonce or domain is named. R-10-008 puts
   this layer through CompCert-C with VST/Iris and M5.3 runs it on the
   emulator; nothing below states a refinement, a WCET or a compilation
   property. The authoring constraint this file does keep is the restricted
   subset that lowering admits: no general recursion, every recursive
   function structural over a list or a finite index, and records and finite
   indices wherever a datatype is not owed. No inductive is declared at all,
   because the register closes no enumeration this layer needs: §10 carries
   nothing of the shape R-12-087's detector list has, so a journal record
   kind, a node class or a status set written here would be this file
   inventing an enumeration the register left open.

   No Require. Nothing beyond the Rocq prelude is reachable, so Classical
   and FunctionalExtensionality are unavailable and every equality below is
   stated pointwise or over a decidable boolean for that reason: a medium
   and a store are functions, and two of them are compared block by block
   rather than as functions. A Require naming a sibling artifact would be
   admissible, and there is none to name: PartitionContext.v's switch cost,
   CyclicExecutive.v's admission algebra, DischargeSequence.v's dwell and
   SupervisionTree.v's supervisor quantities are all schedule and authority
   magnitudes, and none of them meets a block, a record or a key.

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. A block is a finite index and a medium is a total map from it.
      R-10-021 puts replication, tiering, the bucket allocator and the FTL
      below the integrity line as services free to move a block, so what
      this layer holds of a device is an address and nothing else: no
      geometry, no erase unit, no wear state and no failure model appears.
   2. A persisted unit is verified on its own bytes. R-10-001a says that of
      the root copies, and this file reads the same discipline onto a
      journal record and onto an index node: each declares its own length
      and one whose landed length differs from its declared length is not
      replayed and is not complete. That the register states it of the root
      and not of the log is gap c.
   3. The recovery discipline is a parameter and not a choice made here. The
      first record that does not verify either ends the read or is stepped
      over, and no entry chooses: a write-ahead log's prefix discipline
      stops, while R-10-001a's own root selection *enumerates* candidates
      and takes the best that verifies, which skips. So every L0 obligation
      below is stated over an arbitrary discipline, both arms are exhibited,
      each is proved to satisfy every shared obligation, and
      `the_two_recovery_readings_disagree` machine-checks that the choice is
      observable rather than free. Gap e records that no entry chooses, and
      nothing below calls either arm normative or wrong. What the two arms
      differ on is stated as `StopsAtTheFirstTear` and `SkipsTheTornRecord`,
      each proved of one arm and refuted of the other, so the pair is a
      separation and not a verdict.
   4. A transaction is closed by a record and its effects are visible only
      then. R-10-036 commits a checkpoint as a single L0 transaction and
      does not say whether the commit is a record, a barrier or a superblock
      field, so `rec_closes` is a boolean field on the record and no
      representation is asserted (gap d).
   5. A copy-on-write commit writes only blank blocks. The section-10 entry
      this is read from is R-10-010, whose refcounted copy-on-write extent
      sharing and retained snapshot roots are what decide whether a block is
      still live, with R-10-004 and R-10-009 naming the structure
      copy-on-write in the first place and R-10-021 leaving the bucket
      allocator below the integrity line, trusted for availability and not
      for this. No entry of section 10 states the non-reuse rule itself, and
      gap f books that where R-10-010 owns it. R-08-007a does state such a
      rule and is deliberately not cited for it: its sentence is wholly
      about capability revocation, a 64-bit monotone epoch, a revocation bit
      and the granule under it, and it reaches no disk block.
   6. The reachable set is a list computed to a declared height, so
      `covered` and `reaches` are two readings of one list and no separate
      reachability relation exists. The height is a field, which is what
      keeps the walk structural.
   7. Sharing is the second disjunct of a child's resolution. R-10-010's
      reflinks make an unmodified subtree reflinked rather than rewritten,
      so a child of a newly written node is either a block this commit
      writes or a block the medium already holds whole.
   8. A retained root is a separate obligation from the current one.
      R-10-010 makes snapshots retained roots, and a commit that spares
      every block the *current* root reaches can still reuse a block only a
      *retained* root reaches. The two are stated apart, and
      `the_retained_reuse_is_crash_consistent_all_the_same` exhibits a
      construction satisfying one and breaking the other, so the file proves
      they are not one obligation stated twice.
   9. Freshness is surrendered for one asset class of three, and this file
      models that one. R-10-013b makes the split under the RoT monotonic
      counter three-way and not two: beside the low-rate platform state the
      counter keeps fresh and the bulk user data whose freshness is
      surrendered stands durable component state, "declared `Fresh` and
      carried by a freshness epoch rather than by the mutable volume's
      root". R-10-011's MUST NOT is scoped to "The mutable user-data volume"
      alone and gives its reason, that sealing its root would advance the
      counter at CoW-commit frequency; R-10-012 keeps tamper-*detection*
      there and says "only *freshness* is surrendered", its acceptance
      clause scoping the reading to that class rather than to every stored
      byte. So what this file states no freshness property of is the L1 root
      of the mutable volume, which is exactly the class R-10-011 holds out,
      and that is a scope with a ground rather than a silence R-10-013i
      would find against.

      The third class is not this file's and is not unowned. R-10-013c's
      epoch root over every `Fresh` region's version, its acknowledgement at
      the seal, and R-10-013e's refusal of a region that does not verify are
      stated in KeyspaceDomains.v, where R-10-035's manifest-declared
      durable regions land; the counter itself is M3.2's and is shipped,
      RotFirmware.v carrying `FreshnessEpochRoot` as the fourth member of
      R-10-013's closed set with the seal as its only advancing event and
      the data commit refused. Nothing below is that region, that root or
      that counter, and R-10-013c's sealed epoch is therefore not modelled
      *here* rather than not modelled at all.
  10. Boolean rather than propositional wherever the witnesses must compute:
      intactness, completeness, coverage, sortedness and the fanout ceiling
      are decidable, so the generated families below are checked by
      conversion in the silent Example form rather than by a proof per
      member.
  11. R-10-003's "generic over key type, verified once" is a
      parameterization and not a polymorphic function, so the key type, its
      order, its equality and the five laws the index needs are fields of a
      KeyAlgebra record. The prelude carries no order class, and a law
      hidden in a tactic would put the obligation where the review gate
      cannot read it.
  12. A node's occupancy is a property of the node and not of the helper
      that builds one. R-10-003 fixes no node capacity, so `fanout` is a
      field and the ceiling is stated over `Node`, of an arbitrary builder,
      and computed over the nodes the demo medium and the landed commit
      actually hold; the chunking lemma beneath it is named for what it is.
      R-10-022a's tag per referenced child is the second half of what makes
      a node well formed, so `node_fits` reads both.

   The literals taken from the design, and there are none. §10 closes no
   count of the shape R-12-087's detector enumeration has, so every
   magnitude below is a field: the record and node granule counts, the block
   count, the node fanout, the tree height, the allocator, the roots, the
   retained set, the plan, the key type and the message authenticator. The
   only numerals in a definition on the specification side are three: the
   `0` a blank block has landed, the `0` a node with no tag for a child is
   given, and the `0` a recovery that zeroes an untouched block writes. Each
   is commented at its site and pinned by a computed check. Every other
   numeral below is either a demo or probe witness value carrying no
   composition claim (gap h) or a family size the file computes rather than
   claims.

   How the refutations are generated. A refutation is a seeded weakening the
   theorem must reject, so five generators produce families of them
   mechanically rather than a person authoring each. Over the journal's own
   record sequence: `cuts` takes the crash point at every index, and
   `tear_at` cuts one record at every granule below its declared length.
   Over the journal read as a replay: `swap_at`, `replay_prefix` and
   `replay_suffix` transpose, re-enter and repeat. Over an arbitrary key
   list: `swap_at`, `drop_at`, `suffix_at` and `insert_at` give the
   permutations, deletions, proper suffixes and duplications a key order
   admits. Beside every family the generic theorem quantifies over the index
   rather than enumerating. The hand-authored refutations are the ones no
   index generates, being alternative constructions rather than mutations of
   a list.

   What this file deliberately does not author, with the entry that owes
   each decision. A register gap is reported, not closed:

   a. The atomic write unit of the persistent medium. R-15-181 fixes one for
      the main-memory array ("no sub-granule write exists at the array") and
      R-15-247b has data, tag and both ECC planes commit atomically at the
      granule, "never a granule left half-written"; R-12-026 fixes a
      per-page code for NAND. No entry fixes an atomic write unit for the
      persistent medium, and R-10-001a speaks of a torn write costing a copy
      without saying at what unit a write is atomic. So a record's and a
      node's declared length in granules is a field and the torn-write
      family runs over every granule below it. Owed at R-10-001a or
      R-10-002.
   b. The node fanout. The word occurs in no entry of this register.
      R-10-003 makes L1 one parametric index and fixes no node capacity, and
      R-10-004 keeps the B^epsilon refinement without fixing its epsilon. So
      `fanout` is a field, and the only occupancy obligation stated below is
      the *maximum*, because no entry fixes a minimum. Owed at R-10-003.
   c. Whether a journal record is self-verifying, and by what. R-10-001a has
      boot verify each root candidate "on its own bytes"; no entry says the
      same of an L0 record, and a log that cannot tell a torn record from a
      whole one has no recovery point at all. This file takes the weakest
      reading that leaves the layer statable (reading 2), and
      `the_whole_journal_admits_a_torn_record` is the discipline that does
      not take it. Owed at R-10-002.
   d. What ends a transaction. R-10-036 commits a checkpoint as a single L0
      transaction and names no mechanism for the commit itself, and no other
      entry of section 10 names one either; R-10-002 is a layer roster and a
      prover-provenance criterion and does not reach the question.
      `rec_closes` is a boolean field and no representation is asserted
      (reading 4). Owed at R-10-036.
   e. Whether recovery stops at the first record that does not verify or
      steps over it (reading 3). R-10-002 names the GoJournal lineage and
      states no recovery rule, and R-10-001a states the enumerate-and-select
      rule of the *root* copies and not of the log. So the discipline is a
      parameter of every L0 obligation below and neither arm is normative.
      Owed at R-10-002 or R-10-036.
   f. Whether any entry of section 10 states a block-reuse rule at all.
      R-10-010 makes snapshots retained roots and dedup refcounted extent
      sharing, which is the nearest thing: a refcount is what decides
      whether a block is dead. It states no obligation over the allocator,
      R-10-021 leaves the allocator below the integrity line trusted for
      availability, and R-10-027 gives the subvolumes one shared free-space
      pool without saying who may take from it. So nothing in section 10
      says a commit may not reuse a block a retained root still reaches, and
      that is why the two obligations are separated here rather than merged.
      R-08-007a states the rule for capability revocation and reaches no
      disk block, so it is named here and cited nowhere. Owed at R-10-010.
   g. The minimum occupancy of a node, and whether an empty index is a legal
      tree. No entry fixes either, so both the empty and the singleton case
      are admitted below, which is the weaker reading, and `node_fits`
      states a ceiling and no floor. Owed at R-10-003, beside gap b.
   h. Every composition magnitude. The granule counts, the block count, the
      fanout, the height, the allocator, the current root, the retained
      roots, the plan, the key algebra and the authenticator are fields; the
      demo machine, journal, medium, commit and key list at the end
      instantiate them with arbitrary witness values that carry no
      composition claim.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary recovery discipline, recovery, allocator, plan,
   sequencer, key algebra, node builder or tag placement, proved of the
   specification, and refuted of an alternative construction the register's
   own sentence excludes. Two exceptions are stated rather than papered
   over. `ReplayIsIdempotent` has no construction that breaks it alone,
   because `an_honest_recovery_replays_idempotently` derives it from the two
   obligations beneath it, and that derivation is what says why. And
   `ReadsOnlyWhatTheDisciplineAdmits` has no construction that breaks it
   alone either: a recovery reading past its own discipline's cut also
   touches blocks the cut never named, so `unscanned_recover` is exhibited
   breaking both and keeping the other two.

   Inhabitation is concrete: a journal of six records over three
   transactions, one of which never commits; a medium with a current root, a
   retained snapshot root and a blank free pool; a commit whose plan is
   admissible beside four that are not; and a key list whose permutations
   agree and whose deletions do not.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   List and boolean helpers, defined here rather than imported: the prelude
   carries the list type and not the library over it, and importing a module
   to save a hundred lines would put its assumptions inside the R-05-163
   gate's reach for no gain.
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

Fixpoint concat_of {A : Type} (ls : list (list A)) : list A :=
  match ls with nil => nil | cons x r => app x (concat_of r) end.

(* 0 through n-1, in that order: the index set every generator below walks. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

Definition before_last (n : nat) : nat :=
  match n with 0 => 0 | S k => k end.

Fixpoint take {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, _ => nil
  | S _, nil => nil
  | S k, cons x r => cons x (take k r)
  end.

Fixpoint drop {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, _ => l
  | S _, nil => nil
  | S k, cons _ r => drop k r
  end.

Fixpoint nth_opt {A : Type} (l : list A) (n : nat) : option A :=
  match l, n with
  | nil, _ => None
  | cons x _, 0 => Some x
  | cons _ r, S k => nth_opt r k
  end.

Fixpoint last_opt {A : Type} (l : list A) : option A :=
  match l with
  | nil => None
  | cons x nil => Some x
  | cons _ r => last_opt r
  end.

(* The nth member of a list of numbers, or the declared fallback past its
   end. The fallback is a parameter and never a literal at the call site. *)
Fixpoint nth_or (l : list nat) (n : nat) (dflt : nat) : nat :=
  match l, n with
  | nil, _ => dflt
  | cons x _, 0 => x
  | cons _ r, S k => nth_or r k dflt
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

Lemma orb_split : forall a b : bool, orb a b = false -> a = false /\ b = false.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

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

Lemma nat_leb_total : forall a b : nat, orb (Nat.leb a b) (Nat.leb b a) = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b.
  - reflexivity.
  - destruct b as [ | y ]; [ reflexivity | simpl; exact (IH y) ].
Qed.

Lemma nat_leb_trans :
  forall a b c : nat, Nat.leb a b = true -> Nat.leb b c = true -> Nat.leb a c = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b c H1 H2.
  - reflexivity.
  - destruct b as [ | y ]; [ discriminate H1 | ].
    destruct c as [ | z ]; [ discriminate H2 | ].
    simpl in H1. simpl in H2. simpl. exact (IH y z H1 H2).
Qed.

Lemma nat_leb_antisym :
  forall a b : nat, Nat.leb a b = true -> Nat.leb b a = true -> Nat.eqb a b = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b H1 H2.
  - destruct b as [ | y ]; [ reflexivity | discriminate H2 ].
  - destruct b as [ | y ]; [ discriminate H1 | ].
    simpl in H1. simpl in H2. simpl. exact (IH y H1 H2).
Qed.

Lemma all_of_app :
  forall (A : Type) (p : A -> bool) (l r : list A),
    all_of p (app l r) = andb (all_of p l) (all_of p r).
Proof.
  intros A p l. induction l as [ | x s IH ]; intros r.
  - reflexivity.
  - simpl. rewrite IH.
    destruct (p x); destruct (all_of p s); destruct (all_of p r); reflexivity.
Qed.

Lemma any_of_app :
  forall (A : Type) (p : A -> bool) (l r : list A),
    any_of p (app l r) = orb (any_of p l) (any_of p r).
Proof.
  intros A p l. induction l as [ | x s IH ]; intros r.
  - reflexivity.
  - simpl. rewrite IH.
    destruct (p x); destruct (any_of p s); destruct (any_of p r); reflexivity.
Qed.

Lemma all_of_const :
  forall (A : Type) (p : A -> bool) (l : list A),
    (forall x : A, p x = true) -> all_of p l = true.
Proof.
  intros A p l H. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. rewrite (H x). exact IH.
Qed.

Lemma all_of_mono :
  forall (A : Type) (p q : A -> bool) (l : list A),
    (forall x : A, p x = true -> q x = true) ->
    all_of p l = true -> all_of q l = true.
Proof.
  intros A p q l H. induction l as [ | x r IH ]; intros Hl.
  - reflexivity.
  - simpl in Hl. destruct (andb_split _ _ Hl) as [ Hx Hr ].
    simpl. rewrite (H x Hx). exact (IH Hr).
Qed.

(* Membership is written as a decidable search rather than as `In`, so that
   every hypothesis below computes and no propositional membership relation
   is introduced that the conversions would then have to reason about. *)
Definition mem_of (x : nat) (l : list nat) : bool :=
  any_of (fun y => Nat.eqb y x) l.

Lemma mem_of_head : forall (x : nat) (l : list nat), mem_of x (cons x l) = true.
Proof.
  intros x l. unfold mem_of. simpl. rewrite nat_eqb_refl. reflexivity.
Qed.

Lemma mem_of_tail :
  forall (x y : nat) (l : list nat), mem_of x l = true -> mem_of x (cons y l) = true.
Proof.
  intros x y l H. unfold mem_of in H. unfold mem_of. simpl. rewrite H.
  destruct (Nat.eqb y x); reflexivity.
Qed.

Lemma all_of_elim :
  forall (p : nat -> bool) (l : list nat) (x : nat),
    all_of p l = true -> mem_of x l = true -> p x = true.
Proof.
  intros p l. induction l as [ | y r IH ]; intros x Hl Hm.
  - discriminate Hm.
  - simpl in Hl. destruct (andb_split _ _ Hl) as [ Hy Hr ].
    unfold mem_of in Hm. simpl in Hm.
    destruct (Nat.eqb y x) eqn:E.
    + rewrite <- (nat_eqb_true y x E). exact Hy.
    + simpl in Hm. exact (IH x Hr Hm).
Qed.

Lemma all_of_intro :
  forall (p : nat -> bool) (l : list nat),
    (forall x : nat, mem_of x l = true -> p x = true) -> all_of p l = true.
Proof.
  intros p l. induction l as [ | y r IH ]; intros H.
  - reflexivity.
  - simpl. rewrite (H y (mem_of_head y r)).
    apply IH. intros x Hx. exact (H x (mem_of_tail x y r Hx)).
Qed.

Lemma all_of_agree :
  forall (p q : nat -> bool) (l : list nat),
    (forall x : nat, mem_of x l = true -> p x = q x) -> all_of p l = all_of q l.
Proof.
  intros p q l. induction l as [ | y r IH ]; intros H.
  - reflexivity.
  - simpl. rewrite (H y (mem_of_head y r)).
    rewrite (IH (fun x Hx => H x (mem_of_tail x y r Hx))). reflexivity.
Qed.

Lemma map_over_agree :
  forall (f g : nat -> list nat) (l : list nat),
    (forall x : nat, mem_of x l = true -> f x = g x) ->
    map_over f l = map_over g l.
Proof.
  intros f g l. induction l as [ | y r IH ]; intros H.
  - reflexivity.
  - simpl. rewrite (H y (mem_of_head y r)).
    rewrite (IH (fun x Hx => H x (mem_of_tail x y r Hx))). reflexivity.
Qed.

Lemma mem_of_app :
  forall (x : nat) (l r : list nat),
    mem_of x (app l r) = orb (mem_of x l) (mem_of x r).
Proof. intros x l r. unfold mem_of. exact (any_of_app nat _ l r). Qed.

Lemma orb_false_right : forall a : bool, orb a false = a.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma orb_true_split : forall a b : bool, orb a b = true -> a = true \/ b = true.
Proof. intros a b H. destruct a; [ left; reflexivity | right; exact H ]. Qed.

Lemma all_of_take :
  forall (A : Type) (p : A -> bool) (n : nat) (l : list A),
    all_of p l = true -> all_of p (take n l) = true.
Proof.
  intros A p n. induction n as [ | k IH ]; intros l H.
  - reflexivity.
  - destruct l as [ | x r ]; [ reflexivity | ].
    simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    simpl. rewrite Hx. exact (IH r Hr).
Qed.

Lemma all_of_map :
  forall (A B : Type) (p : B -> bool) (f : A -> B) (l : list A),
    all_of p (map_over f l) = all_of (fun x => p (f x)) l.
Proof.
  intros A B p f l. induction l as [ | x r IH ];
    [ reflexivity | simpl; rewrite IH; reflexivity ].
Qed.

Lemma app_assoc_of :
  forall (A : Type) (a b c : list A), app (app a b) c = app a (app b c).
Proof.
  intros A a. induction a as [ | x r IH ]; intros b c;
    [ reflexivity | simpl; rewrite IH; reflexivity ].
Qed.

Lemma map_over_app :
  forall (A B : Type) (f : A -> B) (l r : list A),
    map_over f (app l r) = app (map_over f l) (map_over f r).
Proof.
  intros A B f l. induction l as [ | x s IH ]; intros r;
    [ reflexivity | simpl; rewrite IH; reflexivity ].
Qed.

Lemma concat_of_app :
  forall (A : Type) (l r : list (list A)),
    concat_of (app l r) = app (concat_of l) (concat_of r).
Proof.
  intros A l. induction l as [ | x s IH ]; intros r.
  - reflexivity.
  - simpl. rewrite IH.
    rewrite (app_assoc_of A x (concat_of s) (concat_of r)). reflexivity.
Qed.

Lemma app_of_take_and_drop :
  forall (A : Type) (n : nat) (l : list A), app (take n l) (drop n l) = l.
Proof.
  intros A n. induction n as [ | k IH ]; intros l.
  - reflexivity.
  - destruct l as [ | x r ]; [ reflexivity | simpl; rewrite IH; reflexivity ].
Qed.

Lemma mem_of_concat :
  forall (f : nat -> list nat) (l : list nat) (y : nat),
    mem_of y (concat_of (map_over f l)) = true ->
    exists x : nat, mem_of x l = true /\ mem_of y (f x) = true.
Proof.
  intros f l. induction l as [ | z r IH ]; intros y H.
  - discriminate H.
  - simpl in H. rewrite mem_of_app in H.
    destruct (orb_true_split _ _ H) as [ A | B ].
    + exists z. split; [ exact (mem_of_head z r) | exact A ].
    + destruct (IH y B) as [ x [ Hx Hy ] ].
      exists x. split; [ exact (mem_of_tail x z r Hx) | exact Hy ].
Qed.

Lemma leb_of_succ : forall a b : nat, Nat.leb (S a) b = true -> Nat.leb a b = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b H.
  - reflexivity.
  - destruct b as [ | y ]; [ discriminate H | simpl; simpl in H; exact (IH y H) ].
Qed.

(* The helpers' own floors, so that the day one of them stops deciding is
   the day it says so. Each is a base case no other check below reaches. *)
Example the_empty_conjunction_holds : all_of (fun _ : nat => false) nil = true := eq_refl.

Example the_empty_disjunction_fails : any_of (fun _ : nat => true) nil = false := eq_refl.

Example nothing_has_length_zero : count_of (nil : list nat) = 0 := eq_refl.

Example the_index_set_of_three : upto 3 = cons 0 (cons 1 (cons 2 nil)) := eq_refl.

Example before_last_of_nothing : before_last 0 = 0 := eq_refl.

Example a_cut_at_zero_keeps_nothing :
  take 0 (cons 7 (cons 8 nil)) = nil
  /\ drop 0 (cons 7 (cons 8 nil)) = cons 7 (cons 8 nil)
  /\ take 5 (cons 7 (cons 8 nil)) = cons 7 (cons 8 nil)
  /\ drop 5 (cons 7 (cons 8 nil)) = nil :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_index_past_the_end_is_none :
  nth_opt (cons 7 (cons 8 nil)) 1 = Some 8
  /\ nth_opt (cons 7 (cons 8 nil)) 2 = (None : option nat)
  /\ last_opt (cons 7 (cons 8 nil)) = Some 8
  /\ last_opt (nil : list nat) = None :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example the_fallback_is_taken_past_the_end :
  nth_or (cons 7 (cons 8 nil)) 1 3 = 8 /\ nth_or (cons 7 (cons 8 nil)) 9 3 = 3 :=
  conj eq_refl eq_refl.

Example only_if_is_implication :
  cons (only_if true true) (cons (only_if true false)
  (cons (only_if false true) (cons (only_if false false) nil)))
  = cons true (cons false (cons true (cons true nil))) := eq_refl.

Example membership_is_decided_and_not_assumed :
  mem_of 2 (cons 1 (cons 2 nil)) = true /\ mem_of 3 (cons 1 (cons 2 nil)) = false
  /\ mem_of 3 nil = false := conj eq_refl (conj eq_refl eq_refl).

Example concatenation_flattens_one_level :
  concat_of (cons (cons 1 nil) (cons (cons 2 (cons 3 nil)) nil))
  = cons 1 (cons 2 (cons 3 nil)) := eq_refl.

(* =========================================================================
   The machine: everything the register leaves to composition. Fields rather
   than Parameters, because a top-level Parameter prints as an assumption
   and fails the R-05-163 gate.
   ========================================================================= *)

Record Machine : Type := {

  (* --- L0: a record's declared length in write granules. The register
         fixes an atomic write unit for the main-memory array (R-15-181,
         R-15-247b) and a per-page code for NAND (R-12-026) and none for the
         persistent medium, so this is a field (gap a) ------------------- *)

  record_granules : nat;

  (* --- the block address space the store and the medium span ---------- *)

  block_count : nat;

  (* --- L1: R-10-003's index geometry. `fanout` names a quantity no entry
         of this register carries (gap b), and `height` is the declared
         bound that keeps the reachability walk structural (reading 6) --- *)

  fanout : nat;
  height : nat;
  node_granules : nat;

  (* --- R-10-021's bucket allocator, read only for the blocks it hands
         out: an arbitrary function of an index, so a composition that
         allocates differently is expressible (reading 5) --------------- *)

  fresh_block : nat -> nat;

  (* --- the root the previous generation published ---------------------- *)

  root_block : nat;

  (* --- R-10-022's crypto core as the filesystem sees it: an opaque map
         from bytes to a tag, never a key and never a cipher ------------- *)

  mac : nat -> nat
}.

(* =========================================================================
   L0: the write-ahead log (R-10-002, R-10-036, R-16-005).

   A record names its transaction, the block it updates and the value it
   writes there, says whether it closes its transaction (reading 4, gap d),
   and declares its own length beside the number of granules that actually
   reached the medium (reading 2, gap a and gap c).
   ========================================================================= *)

Record Rec : Type := {
  rec_txn : nat;
  rec_block : nat;
  rec_value : nat;
  rec_closes : bool;
  rec_len : nat;
  rec_landed : nat
}.

(* R-10-001a's "verifies each candidate on its own bytes", read onto a log
   record: a record whose landed length is not its declared length is torn,
   and a torn record decides nothing. *)
Definition intact (r : Rec) : bool := Nat.eqb (rec_landed r) (rec_len r).

(* Reading 3 and gap e: which records of a crashed journal are read at all
   is a *discipline*, and no entry chooses one. Every obligation below is
   therefore stated over an arbitrary discipline and both arms are exhibited
   at once. *)
Definition Discipline : Type := list Rec -> list Rec.

(* The stopping arm: the first record that does not verify ends the read and
   nothing past it is replayed, which is a write-ahead log's own prefix
   discipline. *)
Fixpoint scan (j : list Rec) : list Rec :=
  match j with
  | nil => nil
  | cons r t => if intact r then cons r (scan t) else nil
  end.

(* The skipping arm: the torn record is stepped over and the read goes on,
   which is what R-10-001a's root selection does among its candidates.
   Neither arm is called normative here. *)
Fixpoint sieve (j : list Rec) : list Rec :=
  match j with
  | nil => nil
  | cons r t => if intact r then cons r (sieve t) else sieve t
  end.

(* The discipline that reads the whole journal, torn records included: gap c
   as a construction rather than a remark, being the log that cannot tell a
   torn record from a whole one. *)
Definition keep_all : Discipline := fun j => j.

(* And one that admits only intact records and drops the last of them, so
   reading a log it has already read loses one record more each time. *)
Definition bite : Discipline :=
  fun j => take (before_last (count_of (scan j))) (scan j).

(* The two obligations on a discipline itself, neither of which chooses an
   arm. *)
Definition AdmitsOnlyIntactRecords (cut : Discipline) : Prop :=
  forall j : list Rec, all_of intact (cut j) = true.

Definition IsIdempotent (cut : Discipline) : Prop :=
  forall j : list Rec, cut (cut j) = cut j.

(* And the two the arms differ on. Gap e is exactly that no entry states
   either, so each is proved of one arm and refuted of the other and neither
   is an obligation. *)
Definition StopsAtTheFirstTear (cut : Discipline) : Prop :=
  forall (r : Rec) (t : list Rec), intact r = false -> cut (cons r t) = nil.

Definition SkipsTheTornRecord (cut : Discipline) : Prop :=
  forall (r : Rec) (t : list Rec), intact r = false -> cut (cons r t) = cut t.

(* R-10-036's transactional commit: a transaction is closed by a record of
   its own that the surviving prefix carries. *)
Definition commits (p : list Rec) (t : nat) : bool :=
  any_of (fun r => andb (Nat.eqb (rec_txn r) t) (rec_closes r)) p.

Definition Store : Type := nat -> nat.

Definition put (s : Store) (b v : nat) : Store :=
  fun x => if Nat.eqb b x then v else s x.

(* The replay: each record of the prefix in order, and only where its own
   transaction is closed by that prefix. *)
Fixpoint apply_all (p : list Rec) (cm : nat -> bool) (s : Store) : Store :=
  match p with
  | nil => s
  | cons r t =>
      apply_all t cm (if cm (rec_txn r) then put s (rec_block r) (rec_value r) else s)
  end.

Definition Recovery : Type := list Rec -> Store -> Store.

(* A discipline's own recovery: replay what it admits, under the commit set
   that same admission decides. Every arm below is an instance of this, so
   what separates two recoveries is the discipline and never the replay. *)
Definition recover_under (cut : Discipline) : Recovery :=
  fun j s => apply_all (cut j) (commits (cut j)) s.

Definition spec_recover : Recovery := recover_under scan.

Definition sieve_recover : Recovery := recover_under sieve.

(* Which committed record of the prefix wrote a block last, or nothing. The
   *last* is what makes the journal's order load-bearing rather than
   decorative, and the transposition family below is what shows it. *)
Fixpoint last_write (p : list Rec) (cm : nat -> bool) (b : nat) : option nat :=
  match p with
  | nil => None
  | cons r t =>
      match last_write t cm b with
      | Some v => Some v
      | None =>
          if andb (Nat.eqb (rec_block r) b) (cm (rec_txn r))
          then Some (rec_value r) else None
      end
  end.

Definition writes_committed (p : list Rec) (cm : nat -> bool) (b : nat) : bool :=
  any_of (fun r => andb (Nat.eqb (rec_block r) b) (cm (rec_txn r))) p.

Definition touched_under (cut : Discipline) (j : list Rec) (b : nat) : bool :=
  writes_committed (cut j) (commits (cut j)) b.

Definition touched (j : list Rec) (b : nat) : bool := touched_under scan j b.

(* -------------------------------------------------------------------------
   The four obligations on a recovery, beside the two on a discipline above.
   Each is stated of an arbitrary recovery and read against an arbitrary
   discipline rather than against the stopping arm alone, so gap e costs no
   obligation. Three of the four have a construction that breaks them; the
   fourth is derived from two of the others, and the derivation is what says
   why no construction breaks it alone.
   ------------------------------------------------------------------------- *)

(* R-16-005's "nothing is lost but uncommitted work", read from the other
   side: nothing is *gained* either. A block no committed record of the
   surviving prefix wrote reads exactly what it read before the crash. *)
Definition LeavesUntouchedBlocks (cut : Discipline) (rc : Recovery) : Prop :=
  forall (j : list Rec) (s : Store) (b : nat),
    touched_under cut j b = false -> rc j s b = s b.

(* R-10-036's "no partially updated region is ever committed", read as the
   positive half: every write of a closed transaction is there, and the last
   of them is what stands. *)
Definition LandsEveryCommittedWrite (cut : Discipline) (rc : Recovery) : Prop :=
  forall (j : list Rec) (s : Store) (b v : nat),
    last_write (cut j) (commits (cut j)) b = Some v -> rc j s b = v.

(* Reading 2 and 3 together: a recovery reads what its own discipline
   admitted and nothing beside it, so a torn record is a cut and never a
   corruption. Which cut is gap e's, and this obligation is the same
   whichever arm answers it. *)
Definition ReadsOnlyWhatTheDisciplineAdmits (cut : Discipline)
                                            (rc : Recovery) : Prop :=
  forall (j : list Rec) (s : Store) (b : nat), rc j s b = rc (cut j) s b.

(* The property a crash during recovery needs: replaying a log over a store
   that log has already been replayed onto changes nothing. R-10-036's "no
   partially updated region is ever committed" is what fails without it,
   because a recovery interrupted by a second crash restarts from the log. *)
Definition ReplayIsIdempotent (rc : Recovery) : Prop :=
  forall (j : list Rec) (s : Store) (b : nat), rc j (rc j s) b = rc j s b.

(* -------------------------------------------------------------------------
   The lemmas the four rest on.
   ------------------------------------------------------------------------- *)

Lemma apply_all_untouched :
  forall (p : list Rec) (cm : nat -> bool) (s : Store) (b : nat),
    writes_committed p cm b = false -> apply_all p cm s b = s b.
Proof.
  intros p. induction p as [ | r t IH ]; intros cm s b H.
  - reflexivity.
  - unfold writes_committed in H. simpl in H.
    destruct (orb_split _ _ H) as [ Hr Ht ].
    simpl. rewrite (IH cm _ b Ht).
    destruct (cm (rec_txn r)) eqn:Ec.
    + unfold put. destruct (Nat.eqb (rec_block r) b) eqn:Eb.
      * discriminate Hr.
      * reflexivity.
    + reflexivity.
Qed.

Lemma last_write_none :
  forall (p : list Rec) (cm : nat -> bool) (b : nat),
    last_write p cm b = None -> writes_committed p cm b = false.
Proof.
  intros p. induction p as [ | r t IH ]; intros cm b H.
  - reflexivity.
  - simpl in H. destruct (last_write t cm b) eqn:E; [ discriminate H | ].
    unfold writes_committed. simpl.
    destruct (andb (Nat.eqb (rec_block r) b) (cm (rec_txn r))) eqn:Ea.
    + discriminate H.
    + simpl. exact (IH cm b E).
Qed.

Lemma apply_all_last :
  forall (p : list Rec) (cm : nat -> bool) (s : Store) (b v : nat),
    last_write p cm b = Some v -> apply_all p cm s b = v.
Proof.
  intros p. induction p as [ | r t IH ]; intros cm s b v H.
  - discriminate H.
  - simpl in H. simpl. destruct (last_write t cm b) eqn:E.
    + injection H as H. rewrite <- H. exact (IH cm _ b n E).
    + destruct (andb (Nat.eqb (rec_block r) b) (cm (rec_txn r))) eqn:Ea;
        [ | discriminate H ].
      injection H as H. rewrite <- H.
      destruct (andb_split _ _ Ea) as [ Eb Ec ].
      rewrite Ec. rewrite (apply_all_untouched t cm _ b (last_write_none t cm b E)).
      unfold put. rewrite Eb. reflexivity.
Qed.

Lemma last_write_some :
  forall (p : list Rec) (cm : nat -> bool) (b v : nat),
    last_write p cm b = Some v -> writes_committed p cm b = true.
Proof.
  intros p. induction p as [ | r t IH ]; intros cm b v H.
  - discriminate H.
  - simpl in H. unfold writes_committed. simpl.
    destruct (last_write t cm b) eqn:E.
    + assert (Ht : writes_committed t cm b = true) by exact (IH cm b n E).
      unfold writes_committed in Ht. rewrite Ht.
      destruct (andb (Nat.eqb (rec_block r) b) (cm (rec_txn r))); reflexivity.
    + destruct (andb (Nat.eqb (rec_block r) b) (cm (rec_txn r))) eqn:Ea;
        [ reflexivity | discriminate H ].
Qed.

Lemma scan_is_idempotent : forall j : list Rec, scan (scan j) = scan j.
Proof.
  intros j. induction j as [ | r t IH ].
  - reflexivity.
  - simpl. destruct (intact r) eqn:E.
    + simpl. rewrite E. rewrite IH. reflexivity.
    + reflexivity.
Qed.

Lemma sieve_is_idempotent : forall j : list Rec, sieve (sieve j) = sieve j.
Proof.
  intros j. induction j as [ | r t IH ].
  - reflexivity.
  - simpl. destruct (intact r) eqn:E.
    + simpl. rewrite E. rewrite IH. reflexivity.
    + exact IH.
Qed.

Lemma scan_admits_only_intact_records :
  forall j : list Rec, all_of intact (scan j) = true.
Proof.
  intros j. induction j as [ | r t IH ].
  - reflexivity.
  - simpl. destruct (intact r) eqn:E;
      [ simpl; rewrite E; exact IH | reflexivity ].
Qed.

Lemma sieve_admits_only_intact_records :
  forall j : list Rec, all_of intact (sieve j) = true.
Proof.
  intros j. induction j as [ | r t IH ].
  - reflexivity.
  - simpl. destruct (intact r) eqn:E;
      [ simpl; rewrite E; exact IH | exact IH ].
Qed.

(* Whatever a discipline admits, replaying it is a recovery: the theorem is
   stated once over the parameter and every arm below is an instance, so no
   arm gets its own proof of the same three obligations. *)

(* S1 (R-16-005, R-10-036). *)
Theorem a_discipline_leaves_untouched_blocks_alone :
  forall cut : Discipline, LeavesUntouchedBlocks cut (recover_under cut).
Proof.
  intros cut j s b H. unfold recover_under. unfold touched_under in H.
  exact (apply_all_untouched (cut j) (commits (cut j)) s b H).
Qed.

(* S2 (R-10-036). *)
Theorem a_discipline_lands_every_committed_write :
  forall cut : Discipline, LandsEveryCommittedWrite cut (recover_under cut).
Proof.
  intros cut j s b v H. unfold recover_under.
  exact (apply_all_last (cut j) (commits (cut j)) s b v H).
Qed.

(* S3 (R-10-001a, reading 2): an idempotent discipline's recovery reads
   nothing its own discipline did not admit. *)
Theorem an_idempotent_discipline_reads_only_what_it_admits :
  forall cut : Discipline,
    IsIdempotent cut -> ReadsOnlyWhatTheDisciplineAdmits cut (recover_under cut).
Proof.
  intros cut H j s b. unfold recover_under. rewrite (H j). reflexivity.
Qed.

(* S4 (R-10-036): a crash during recovery costs nothing, because replaying
   the same log again reaches the same store. And it is not a fourth
   independent obligation: a recovery that leaves untouched blocks alone and
   lands every committed write is idempotent *for that reason*, which is why
   no construction below refutes it alone. The two obligations beneath it
   are what a construction has to break. *)
Theorem an_honest_recovery_replays_idempotently :
  forall (cut : Discipline) (rc : Recovery),
    LeavesUntouchedBlocks cut rc -> LandsEveryCommittedWrite cut rc ->
    ReplayIsIdempotent rc.
Proof.
  intros cut rc Hu Hl j s b.
  destruct (last_write (cut j) (commits (cut j)) b) eqn:E.
  - rewrite (Hl j (rc j s) b n E). rewrite (Hl j s b n E). reflexivity.
  - rewrite (Hu j (rc j s) b (last_write_none (cut j) (commits (cut j)) b E)).
    reflexivity.
Qed.

Theorem a_discipline_replays_idempotently :
  forall cut : Discipline, ReplayIsIdempotent (recover_under cut).
Proof.
  intros cut.
  exact (an_honest_recovery_replays_idempotently cut (recover_under cut)
           (a_discipline_leaves_untouched_blocks_alone cut)
           (a_discipline_lands_every_committed_write cut)).
Qed.

(* The four read at the stopping arm, which is the discipline every
   computation below is done under. Each is the general theorem instantiated
   and nothing more: what makes the arm the demo's is a choice of witness,
   not a choice of obligation. *)
Theorem the_specification_leaves_untouched_blocks_alone :
  LeavesUntouchedBlocks scan spec_recover.
Proof. exact (a_discipline_leaves_untouched_blocks_alone scan). Qed.

Theorem the_specification_lands_every_committed_write :
  LandsEveryCommittedWrite scan spec_recover.
Proof. exact (a_discipline_lands_every_committed_write scan). Qed.

Theorem the_specification_reads_only_what_the_discipline_admits :
  ReadsOnlyWhatTheDisciplineAdmits scan spec_recover.
Proof.
  exact (an_idempotent_discipline_reads_only_what_it_admits scan
           scan_is_idempotent).
Qed.

Theorem the_specification_replay_is_idempotent : ReplayIsIdempotent spec_recover.
Proof. exact (a_discipline_replays_idempotently scan). Qed.

(* -------------------------------------------------------------------------
   The two arms, each an instance, and the separation gap e reports. Neither
   arm is asserted to be the register's, and each is shown to keep every
   obligation the other keeps.
   ------------------------------------------------------------------------- *)

Theorem the_stopping_arm_keeps_every_shared_obligation :
  AdmitsOnlyIntactRecords scan /\ IsIdempotent scan
  /\ LeavesUntouchedBlocks scan spec_recover
  /\ LandsEveryCommittedWrite scan spec_recover
  /\ ReadsOnlyWhatTheDisciplineAdmits scan spec_recover
  /\ ReplayIsIdempotent spec_recover.
Proof.
  split; [ exact scan_admits_only_intact_records | ].
  split; [ exact scan_is_idempotent | ].
  split; [ exact (a_discipline_leaves_untouched_blocks_alone scan) | ].
  split; [ exact (a_discipline_lands_every_committed_write scan) | ].
  split; [ exact (an_idempotent_discipline_reads_only_what_it_admits scan
                    scan_is_idempotent)
         | exact (a_discipline_replays_idempotently scan) ].
Qed.

Theorem the_skipping_arm_keeps_every_shared_obligation :
  AdmitsOnlyIntactRecords sieve /\ IsIdempotent sieve
  /\ LeavesUntouchedBlocks sieve sieve_recover
  /\ LandsEveryCommittedWrite sieve sieve_recover
  /\ ReadsOnlyWhatTheDisciplineAdmits sieve sieve_recover
  /\ ReplayIsIdempotent sieve_recover.
Proof.
  split; [ exact sieve_admits_only_intact_records | ].
  split; [ exact sieve_is_idempotent | ].
  split; [ exact (a_discipline_leaves_untouched_blocks_alone sieve) | ].
  split; [ exact (a_discipline_lands_every_committed_write sieve) | ].
  split; [ exact (an_idempotent_discipline_reads_only_what_it_admits sieve
                    sieve_is_idempotent)
         | exact (a_discipline_replays_idempotently sieve) ].
Qed.

(* Gap e made checkable rather than asserted: the two arms differ on exactly
   the clause no entry states, each satisfying its own and refuting the
   other's. *)
Theorem the_stopping_arm_stops : StopsAtTheFirstTear scan.
Proof. intros r t H. simpl. rewrite H. reflexivity. Qed.

Theorem the_skipping_arm_skips : SkipsTheTornRecord sieve.
Proof. intros r t H. simpl. rewrite H. reflexivity. Qed.

(* Two probe records, the smallest a discipline can be read at: one whose
   landed length is its declared length and one whose is not. Every figure
   is a witness value and carries no composition claim (gap h). *)
Definition whole_probe (b v : nat) : Rec :=
  {| rec_txn := 0; rec_block := b; rec_value := v; rec_closes := true;
     rec_len := 1; rec_landed := 1 |}.

Definition torn_probe : Rec :=
  {| rec_txn := 0; rec_block := 0; rec_value := 0; rec_closes := true;
     rec_len := 1; rec_landed := 0 |}.

Example the_probe_records_declare :
  rec_txn (whole_probe 3 7) = 0 /\ rec_block (whole_probe 3 7) = 3
  /\ rec_value (whole_probe 3 7) = 7 /\ rec_closes (whole_probe 3 7) = true
  /\ rec_len (whole_probe 3 7) = 1 /\ rec_landed (whole_probe 3 7) = 1
  /\ intact (whole_probe 3 7) = true
  /\ rec_txn torn_probe = 0 /\ rec_block torn_probe = 0
  /\ rec_value torn_probe = 0 /\ rec_closes torn_probe = true
  /\ rec_len torn_probe = 1 /\ rec_landed torn_probe = 0
  /\ intact torn_probe = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))))))))))))
.

Definition probe_journal : list Rec :=
  cons torn_probe (cons (whole_probe 1 9) nil).

(* A journal whose transaction closes *before* the tear and whose record
   past the tear writes the same block again: the smallest journal on which
   reading past a discipline's own cut is observable. *)
Definition past_the_cut_journal : list Rec :=
  cons (whole_probe 1 11) (cons torn_probe (cons (whole_probe 1 99) nil)).

Definition probe_store : Store := fun b => S b.

Example the_probe_store_and_journal_declare :
  probe_store 0 = 1 /\ probe_store 4 = 5
  /\ count_of past_the_cut_journal = 3
  /\ scan past_the_cut_journal = cons (whole_probe 1 11) nil
  /\ commits (scan past_the_cut_journal) 0 = true
  /\ map_over rec_block past_the_cut_journal = cons 1 (cons 0 (cons 1 nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Theorem the_stopping_arm_does_not_skip : ~ SkipsTheTornRecord scan.
Proof.
  intros H. specialize (H torn_probe (cons (whole_probe 1 9) nil) eq_refl).
  discriminate H.
Qed.

Theorem the_skipping_arm_does_not_stop : ~ StopsAtTheFirstTear sieve.
Proof.
  intros H. specialize (H torn_probe (cons (whole_probe 1 9) nil) eq_refl).
  discriminate H.
Qed.

(* -------------------------------------------------------------------------
   The refuting constructions over a discipline, one obligation apiece.
   ------------------------------------------------------------------------- *)

(* Gap c as a construction: a log that cannot tell a torn record from a whole
   one replays the torn one. Reading 2 is what refuses it, and no entry
   states that reading of an L0 record. *)
Theorem the_whole_journal_admits_a_torn_record :
  ~ AdmitsOnlyIntactRecords keep_all.
Proof. intros H. specialize (H (cons torn_probe nil)). discriminate H. Qed.

(* The twin: reading everything is idempotent, so what refuses it is the
   torn record it admits and not a second read that moves. *)
Theorem the_whole_journal_is_still_idempotent : IsIdempotent keep_all.
Proof. intros j. reflexivity. Qed.

(* And one that admits only intact records and is not idempotent: a recovery
   interrupted by a second crash reads one record less than the first read
   did, so a store the first replay reached is not one the second reaches. *)
Theorem the_biting_discipline_is_not_idempotent : ~ IsIdempotent bite.
Proof.
  intros H.
  specialize (H (cons (whole_probe 0 0) (cons (whole_probe 1 1) nil))).
  discriminate H.
Qed.

Theorem the_biting_discipline_still_admits_only_intact_records :
  AdmitsOnlyIntactRecords bite.
Proof.
  intros j. unfold bite.
  exact (all_of_take Rec intact (before_last (count_of (scan j))) (scan j)
           (scan_admits_only_intact_records j)).
Qed.

Example what_the_four_disciplines_admit :
  scan probe_journal = nil
  /\ sieve probe_journal = cons (whole_probe 1 9) nil
  /\ keep_all probe_journal = probe_journal
  /\ bite probe_journal = nil
  /\ bite (cons (whole_probe 0 0) (cons (whole_probe 1 1) nil))
     = cons (whole_probe 0 0) nil :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* -------------------------------------------------------------------------
   The refuting constructions over a recovery. Each is a recovery that is
   not any discipline's own replay, and each is shown to keep what it does
   not break.
   ------------------------------------------------------------------------- *)

(* A recovery that zeroes every block the surviving prefix did not write.
   R-16-005 read from the other side is what it breaks: nothing is lost but
   uncommitted work, and nothing is gained either. *)
Definition zeroing_recover : Recovery :=
  fun j s b => if touched j b then spec_recover j s b else 0.

(* A recovery that replays nothing at all. It leaves every untouched block
   alone and reads only what the discipline admitted, because it reads
   nothing; what it loses is exactly the committed work R-16-005 says is not
   lost. *)
Definition stale_recover : Recovery := fun _ s => s.

(* A recovery that replays the whole journal under the stopping arm's own
   commit set, so it reads past the cut its discipline made. *)
Definition unscanned_recover : Recovery :=
  fun j s => apply_all j (commits (scan j)) s.

Theorem the_zeroing_recovery_still_lands_every_committed_write :
  LandsEveryCommittedWrite scan zeroing_recover.
Proof.
  intros j s b v H. unfold zeroing_recover. unfold touched. unfold touched_under.
  rewrite (last_write_some (scan j) (commits (scan j)) b v H).
  exact (a_discipline_lands_every_committed_write scan j s b v H).
Qed.

Theorem the_stale_recovery_keeps_every_other_obligation :
  LeavesUntouchedBlocks scan stale_recover
  /\ ReadsOnlyWhatTheDisciplineAdmits scan stale_recover
  /\ ReplayIsIdempotent stale_recover.
Proof.
  split; [ intros j s b _; reflexivity | ].
  split; intros j s b; reflexivity.
Qed.

Theorem the_unscanned_recovery_still_replays_idempotently :
  ReplayIsIdempotent unscanned_recover.
Proof.
  intros j s b. unfold unscanned_recover.
  destruct (last_write j (commits (scan j)) b) eqn:E.
  - rewrite (apply_all_last j (commits (scan j))
               (apply_all j (commits (scan j)) s) b n E).
    rewrite (apply_all_last j (commits (scan j)) s b n E). reflexivity.
  - rewrite (apply_all_untouched j (commits (scan j))
               (apply_all j (commits (scan j)) s) b
               (last_write_none j (commits (scan j)) b E)).
    reflexivity.
Qed.

(* -------------------------------------------------------------------------
   The crash point, as a property of every prefix rather than of a list of
   them. `honest_at` is the conjunction of S1 and S2 read at one journal
   over a bounded block range, so the family conversions below and the
   theorem here decide the same thing.
   ------------------------------------------------------------------------- *)

Definition honest_at (rc : Recovery) (s : Store) (blocks : nat)
                     (j : list Rec) : bool :=
  andb
    (all_of (fun b => only_if (negb (touched j b)) (Nat.eqb (rc j s b) (s b)))
            (upto blocks))
    (all_of (fun b => match last_write (scan j) (commits (scan j)) b with
                      | None => true
                      | Some v => Nat.eqb (rc j s b) v
                      end)
            (upto blocks)).

(* S5 (R-10-002, R-10-036, R-16-005): every crash point at once, and for an
   arbitrary journal rather than for the demo's. A prefix is a journal, so
   this is the crash-point family stated as a quantifier over the cut and
   not as an enumeration of one. *)
Theorem the_specification_recovers_honestly_from_every_journal :
  forall (j : list Rec) (s : Store) (blocks : nat),
    honest_at spec_recover s blocks j = true.
Proof.
  intros j s blocks. unfold honest_at. apply andb_join.
  - apply all_of_const. intros b. unfold only_if.
    destruct (touched j b) eqn:E.
    + reflexivity.
    + simpl.
      rewrite (the_specification_leaves_untouched_blocks_alone j s b E).
      exact (nat_eqb_refl (s b)).
  - apply all_of_const. intros b.
    destruct (last_write (scan j) (commits (scan j)) b) eqn:E.
    + rewrite (the_specification_lands_every_committed_write j s b n E).
      exact (nat_eqb_refl n).
    + reflexivity.
Qed.

(* S6 (R-10-002): recovery never un-commits. A transaction the machine has
   closed at one crash point is closed at every later one, so the cut index
   is monotone in what it admits. *)
Lemma scan_of_a_cut_is_carried_forward :
  forall (p : Rec -> bool) (i : nat) (j : list Rec),
    any_of p (scan (take i j)) = true -> any_of p (scan j) = true.
Proof.
  intros p i. induction i as [ | k IH ]; intros j H.
  - discriminate H.
  - destruct j as [ | r t ]; [ discriminate H | ].
    simpl in H. simpl. destruct (intact r) eqn:E; [ | discriminate H ].
    simpl in H. simpl. destruct (p r); [ reflexivity | ].
    simpl in H. simpl. exact (IH t H).
Qed.

Theorem no_later_crash_point_uncommits_a_transaction :
  forall (i t : nat) (j : list Rec),
    commits (scan (take i j)) t = true -> commits (scan j) t = true.
Proof.
  intros i t j H. unfold commits in H. unfold commits.
  exact (scan_of_a_cut_is_carried_forward _ i j H).
Qed.

(* -------------------------------------------------------------------------
   The generated families over a journal. Four generators, over the
   journal's own record sequence rather than over a list a person wrote.
   ------------------------------------------------------------------------- *)

(* The crash point at every index, from before the first record to past the
   last. *)
Definition cuts (j : list Rec) : list (list Rec) :=
  map_over (fun i => take i j) (upto (S (count_of j))).

(* One record cut short at g granules: R-10-001a's torn write, at the
   granule gap a says the register does not fix. *)
Definition tear (g : nat) (r : Rec) : Rec :=
  {| rec_txn := rec_txn r; rec_block := rec_block r; rec_value := rec_value r;
     rec_closes := rec_closes r; rec_len := rec_len r; rec_landed := g |}.

Fixpoint tear_at (k g : nat) (j : list Rec) : list Rec :=
  match k, j with
  | _, nil => nil
  | 0, cons r t => cons (tear g r) t
  | S n, cons r t => cons r (tear_at n g t)
  end.

(* The replay arms: a prefix replayed twice, a suffix replayed, and one
   record moved out of order. *)
Definition replay_prefix (i : nat) (j : list Rec) : list Rec := app (take i j) j.

Definition replay_suffix (i : nat) (j : list Rec) : list Rec := app j (drop i j).

(* -------------------------------------------------------------------------
   And the replay arms as theorems over an arbitrary journal, an arbitrary
   store and an arbitrary cut, rather than as conversions over the demo's
   six records at seven indices. The demo family below decides the same
   thing at the demo; these decide the reason.
   ------------------------------------------------------------------------- *)

Lemma scan_of_an_intact_journal :
  forall j : list Rec, all_of intact j = true -> scan j = j.
Proof.
  intros j. induction j as [ | r t IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hr Ht ].
    simpl. rewrite Hr. rewrite (IH Ht). reflexivity.
Qed.

Lemma apply_all_app :
  forall (p q : list Rec) (cm : nat -> bool) (s : Store),
    apply_all (app p q) cm s = apply_all q cm (apply_all p cm s).
Proof.
  intros p. induction p as [ | r t IH ]; intros q cm s;
    [ reflexivity | simpl; exact (IH q cm _) ].
Qed.

Lemma apply_all_agrees :
  forall (p : list Rec) (cm1 cm2 : nat -> bool) (s1 s2 : Store) (b : nat),
    (forall t : nat, cm1 t = cm2 t) -> (forall x : nat, s1 x = s2 x) ->
    apply_all p cm1 s1 b = apply_all p cm2 s2 b.
Proof.
  intros p. induction p as [ | r t IH ]; intros cm1 cm2 s1 s2 b Hc Hs.
  - exact (Hs b).
  - simpl. apply (IH cm1 cm2 _ _ b Hc). intros x.
    rewrite (Hc (rec_txn r)). destruct (cm2 (rec_txn r)).
    + unfold put. destruct (Nat.eqb (rec_block r) x);
        [ reflexivity | exact (Hs x) ].
    + exact (Hs x).
Qed.

Lemma last_write_app :
  forall (p q : list Rec) (cm : nat -> bool) (b : nat),
    last_write (app p q) cm b
    = match last_write q cm b with
      | Some v => Some v
      | None => last_write p cm b
      end.
Proof.
  intros p. induction p as [ | r t IH ]; intros q cm b.
  - simpl. destruct (last_write q cm b); reflexivity.
  - simpl. rewrite (IH q cm b). destruct (last_write q cm b); reflexivity.
Qed.

Lemma commits_app :
  forall (p q : list Rec) (t : nat),
    commits (app p q) t = orb (commits p t) (commits q t).
Proof. intros p q t. unfold commits. exact (any_of_app Rec _ p q). Qed.

Lemma writes_committed_app :
  forall (p q : list Rec) (cm : nat -> bool) (b : nat),
    writes_committed (app p q) cm b
    = orb (writes_committed p cm b) (writes_committed q cm b).
Proof. intros p q cm b. unfold writes_committed. exact (any_of_app Rec _ p q). Qed.

(* A prefix and a suffix of a journal each commit only what the journal
   commits, which is why replaying either again moves no commit set. *)
Lemma the_commit_set_of_a_replay_is_the_journal_s :
  forall (i : nat) (j : list Rec) (t : nat),
    commits (replay_prefix i j) t = commits j t
    /\ commits (replay_suffix i j) t = commits j t.
Proof.
  intros i j t.
  assert (Hj : commits j t
               = orb (commits (take i j) t) (commits (drop i j) t)).
  { rewrite <- (commits_app (take i j) (drop i j) t).
    rewrite (app_of_take_and_drop Rec i j). reflexivity. }
  unfold replay_prefix. unfold replay_suffix.
  rewrite (commits_app (take i j) j t). rewrite (commits_app j (drop i j) t).
  rewrite Hj.
  destruct (commits (take i j) t); destruct (commits (drop i j) t);
    split; reflexivity.
Qed.

(* S16 (R-10-036): replaying a prefix again reaches the store the journal
   itself reaches, of an arbitrary intact journal, an arbitrary store, an
   arbitrary cut and an arbitrary block. *)
Theorem replaying_a_prefix_reaches_the_same_store :
  forall (j : list Rec) (s : Store) (i b : nat),
    all_of intact j = true ->
    spec_recover (replay_prefix i j) s b = spec_recover j s b.
Proof.
  intros j s i b Hj. unfold spec_recover. unfold recover_under.
  assert (Hp : all_of intact (replay_prefix i j) = true).
  { unfold replay_prefix. rewrite (all_of_app Rec intact (take i j) j).
    apply andb_join; [ exact (all_of_take Rec intact i j Hj) | exact Hj ]. }
  rewrite (scan_of_an_intact_journal _ Hp).
  rewrite (scan_of_an_intact_journal j Hj).
  rewrite (apply_all_agrees (replay_prefix i j)
             (commits (replay_prefix i j)) (commits j) s s b
             (fun t => proj1 (the_commit_set_of_a_replay_is_the_journal_s i j t))
             (fun x => eq_refl)).
  unfold replay_prefix. rewrite (apply_all_app (take i j) j (commits j) s).
  destruct (last_write j (commits j) b) eqn:E.
  - rewrite (apply_all_last j (commits j) (apply_all (take i j) (commits j) s) b n E).
    rewrite (apply_all_last j (commits j) s b n E). reflexivity.
  - assert (Hw : writes_committed j (commits j) b = false)
      by exact (last_write_none j (commits j) b E).
    assert (Ht : writes_committed (take i j) (commits j) b = false).
    { assert (Hs : writes_committed j (commits j) b
                   = orb (writes_committed (take i j) (commits j) b)
                         (writes_committed (drop i j) (commits j) b)).
      { rewrite <- (writes_committed_app (take i j) (drop i j) (commits j) b).
        rewrite (app_of_take_and_drop Rec i j). reflexivity. }
      rewrite Hs in Hw. destruct (orb_split _ _ Hw) as [ A _ ]. exact A. }
    rewrite (apply_all_untouched j (commits j)
               (apply_all (take i j) (commits j) s) b Hw).
    rewrite (apply_all_untouched (take i j) (commits j) s b Ht).
    rewrite (apply_all_untouched j (commits j) s b Hw). reflexivity.
Qed.

(* S16b: and replaying a suffix again, on the same terms. *)
Theorem replaying_a_suffix_reaches_the_same_store :
  forall (j : list Rec) (s : Store) (i b : nat),
    all_of intact j = true ->
    spec_recover (replay_suffix i j) s b = spec_recover j s b.
Proof.
  intros j s i b Hj. unfold spec_recover. unfold recover_under.
  assert (Hp : all_of intact (replay_suffix i j) = true).
  { unfold replay_suffix. rewrite (all_of_app Rec intact j (drop i j)).
    apply andb_join; [ exact Hj | ].
    assert (Hd : all_of intact (app (take i j) (drop i j)) = true).
    { rewrite (app_of_take_and_drop Rec i j). exact Hj. }
    rewrite (all_of_app Rec intact (take i j) (drop i j)) in Hd.
    destruct (andb_split _ _ Hd) as [ _ B ]. exact B. }
  rewrite (scan_of_an_intact_journal _ Hp).
  rewrite (scan_of_an_intact_journal j Hj).
  rewrite (apply_all_agrees (replay_suffix i j)
             (commits (replay_suffix i j)) (commits j) s s b
             (fun t => proj2 (the_commit_set_of_a_replay_is_the_journal_s i j t))
             (fun x => eq_refl)).
  unfold replay_suffix. rewrite (apply_all_app j (drop i j) (commits j) s).
  assert (Hsplit : last_write j (commits j) b
                   = match last_write (drop i j) (commits j) b with
                     | Some v => Some v
                     | None => last_write (take i j) (commits j) b
                     end).
  { rewrite <- (last_write_app (take i j) (drop i j) (commits j) b).
    rewrite (app_of_take_and_drop Rec i j). reflexivity. }
  destruct (last_write (drop i j) (commits j) b) eqn:E.
  - assert (Hn : last_write j (commits j) b = Some n) by exact Hsplit.
    rewrite (apply_all_last (drop i j) (commits j)
               (apply_all j (commits j) s) b n E).
    rewrite (apply_all_last j (commits j) s b n Hn). reflexivity.
  - rewrite (apply_all_untouched (drop i j) (commits j)
               (apply_all j (commits j) s) b
               (last_write_none (drop i j) (commits j) b E)).
    reflexivity.
Qed.

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

(* Two recoveries agree when they agree block by block over the declared
   address space, which is how a function equality is stated where
   FunctionalExtensionality is unreachable. *)
Definition agrees_on (blocks : nat) (s : Store) (rc1 rc2 : Recovery)
                     (j1 j2 : list Rec) : bool :=
  all_of (fun b => Nat.eqb (rc1 j1 s b) (rc2 j2 s b)) (upto blocks).

(* =========================================================================
   L1: the copy-on-write index on the medium (R-10-002, R-10-009, R-10-010,
   R-10-022a, R-16-003).

   A node carries its keys, the blocks of its children, and R-10-022a's tag
   for each of those children. A block carries the node, its declared length
   in granules beside the number that landed (reading 2), and the extent
   bytes with the tag a placement that stored the tag beside the ciphertext
   would compare against.
   ========================================================================= *)

Record Node : Type := {
  node_keys : list nat;
  node_kids : list nat;
  node_tags : list nat
}.

Record Blk : Type := {
  blk_node : Node;
  blk_len : nat;
  blk_landed : nat;
  blk_content : nat;
  blk_tag : nat
}.

Definition Medium : Type := nat -> Blk.

Definition complete (bk : Blk) : bool := Nat.eqb (blk_landed bk) (blk_len bk).

(* A block that has landed no granule at all. The second conjunct is what
   rules out a zero-length block, which would have landed nothing and be
   complete at the same time; the `0` is the boundary this definition fixes
   and not a magnitude a composition chooses. *)
Definition blank (bk : Blk) : bool :=
  andb (Nat.eqb (blk_landed bk) 0) (negb (complete bk)).

Lemma a_blank_block_is_not_complete :
  forall bk : Blk, blank bk = true -> complete bk = false.
Proof.
  intros bk H. unfold blank in H. destruct (andb_split _ _ H) as [ _ Hn ].
  destruct (complete bk); [ discriminate Hn | reflexivity ].
Qed.

Definition kids_of (md : Medium) (b : nat) : list nat := node_kids (blk_node (md b)).

(* Reading 6: the reachable set is a list computed to the declared height,
   and `covered` and `reaches` are two readings of that one list. *)
Fixpoint layers (fuel : nat) (md : Medium) (l : list nat) : list nat :=
  match fuel with
  | 0 => l
  | S k => app l (layers k md (concat_of (map_over (kids_of md) l)))
  end.

Definition reach_set (m : Machine) (md : Medium) (b : nat) : list nat :=
  layers (height m) md (cons b nil).

Definition reaches (m : Machine) (md : Medium) (b x : nat) : bool :=
  mem_of x (reach_set m md b).

(* The property the whole copy-on-write argument is about: no block the root
   reaches is half written. *)
Definition covered (m : Machine) (md : Medium) (b : nat) : bool :=
  all_of (fun x => complete (md x)) (reach_set m md b).

Lemma covered_reaches_complete :
  forall (m : Machine) (md : Medium) (b x : nat),
    covered m md b = true -> reaches m md b x = true -> complete (md x) = true.
Proof.
  intros m md b x Hc Hr. unfold covered in Hc. unfold reaches in Hr.
  exact (all_of_elim _ _ x Hc Hr).
Qed.

Lemma covered_intro :
  forall (m : Machine) (md : Medium) (b : nat),
    (forall x : nat, reaches m md b x = true -> complete (md x) = true) ->
    covered m md b = true.
Proof.
  intros m md b H. unfold covered. apply all_of_intro. intros x Hx.
  exact (H x Hx).
Qed.

(* A block the cover reaches is complete, so a blank block is out of every
   cover: the lemma that turns "the allocator hands out blank blocks" into
   "the current root does not reach what this commit writes". *)
Lemma a_blank_block_is_out_of_every_cover :
  forall (m : Machine) (md : Medium) (b x : nat),
    covered m md b = true -> blank (md x) = true -> reaches m md b x = false.
Proof.
  intros m md b x Hc Hb. destruct (reaches m md b x) eqn:E; [ | reflexivity ].
  assert (Hcomp : complete (md x) = true)
    by exact (covered_reaches_complete m md b x Hc E).
  rewrite (a_blank_block_is_not_complete (md x) Hb) in Hcomp. discriminate Hcomp.
Qed.

(* The frame lemma: a medium changed only outside a cover has the same
   cover. The walk is over a list the medium itself computes, so the list
   has to be shown unchanged before the conjunction over it can be. *)
Lemma layers_frame :
  forall (fuel : nat) (md1 md2 : Medium) (l : list nat),
    (forall x : nat, mem_of x (layers fuel md1 l) = true -> md2 x = md1 x) ->
    layers fuel md2 l = layers fuel md1 l.
Proof.
  intros fuel. induction fuel as [ | k IH ]; intros md1 md2 l H.
  - reflexivity.
  - simpl. simpl in H.
    assert (Hk : map_over (kids_of md2) l = map_over (kids_of md1) l).
    { apply map_over_agree. intros x Hx.
      assert (Hm : md2 x = md1 x).
      { apply H. rewrite mem_of_app. rewrite Hx. reflexivity. }
      unfold kids_of. rewrite Hm. reflexivity. }
    rewrite Hk.
    assert (Hrest : layers k md2 (concat_of (map_over (kids_of md1) l))
                    = layers k md1 (concat_of (map_over (kids_of md1) l))).
    { apply IH. intros x Hx. apply H. rewrite mem_of_app. rewrite Hx.
      destruct (mem_of x l); reflexivity. }
    rewrite Hrest. reflexivity.
Qed.

Lemma cover_survives_a_write_off_the_cover :
  forall (m : Machine) (md1 md2 : Medium) (b : nat),
    covered m md1 b = true ->
    (forall x : nat, reaches m md1 b x = true -> md2 x = md1 x) ->
    covered m md2 b = true.
Proof.
  intros m md1 md2 b Hc H. unfold covered. unfold reach_set.
  rewrite (layers_frame (height m) md1 md2 (cons b nil) H).
  unfold covered in Hc. unfold reach_set in Hc.
  rewrite (all_of_agree (fun x => complete (md2 x)) (fun x => complete (md1 x))
             (layers (height m) md1 (cons b nil))).
  - exact Hc.
  - intros x Hx. rewrite (H x Hx). reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Coverage at a bounded depth, which is what the walk down a newly written
   tree needs: `covered` is the walk to the declared height, and a child of
   a covered block is covered to one step less. Reading 6's height being a
   field is exactly why this is a family and not one predicate.
   ------------------------------------------------------------------------- *)

Definition covered_to (fuel : nat) (md : Medium) (b : nat) : bool :=
  all_of (fun x => complete (md x)) (layers fuel md (cons b nil)).

Lemma layers_of_app :
  forall (fuel : nat) (md : Medium) (p : nat -> bool) (l r : list nat),
    all_of p (layers fuel md (app l r)) = true ->
    all_of p (layers fuel md l) = true /\ all_of p (layers fuel md r) = true.
Proof.
  intros fuel. induction fuel as [ | k IH ]; intros md p l r H.
  - simpl in H. rewrite (all_of_app nat p l r) in H.
    destruct (andb_split _ _ H) as [ A B ]. split; [ exact A | exact B ].
  - simpl in H.
    rewrite (all_of_app nat p (app l r)
               (layers k md (concat_of (map_over (kids_of md) (app l r))))) in H.
    destruct (andb_split _ _ H) as [ A B ].
    rewrite (all_of_app nat p l r) in A. destruct (andb_split _ _ A) as [ A1 A2 ].
    rewrite (map_over_app nat (list nat) (kids_of md) l r) in B.
    rewrite (concat_of_app nat (map_over (kids_of md) l)
               (map_over (kids_of md) r)) in B.
    destruct (IH md p (concat_of (map_over (kids_of md) l))
                (concat_of (map_over (kids_of md) r)) B) as [ B1 B2 ].
    split; simpl; rewrite (all_of_app nat p _ _); apply andb_join; assumption.
Qed.

Lemma covered_to_monotone :
  forall (h fuel : nat) (md : Medium) (p : nat -> bool) (l : list nat),
    Nat.leb fuel h = true ->
    all_of p (layers h md l) = true -> all_of p (layers fuel md l) = true.
Proof.
  intros h. induction h as [ | k IH ]; intros fuel md p l Hf H.
  - destruct fuel as [ | n ]; [ exact H | discriminate Hf ].
  - destruct fuel as [ | n ].
    + simpl in H.
      rewrite (all_of_app nat p l
                 (layers k md (concat_of (map_over (kids_of md) l)))) in H.
      destruct (andb_split _ _ H) as [ A _ ]. exact A.
    + simpl in Hf. simpl in H. simpl.
      rewrite (all_of_app nat p l
                 (layers k md (concat_of (map_over (kids_of md) l)))) in H.
      destruct (andb_split _ _ H) as [ A B ].
      rewrite (all_of_app nat p l
                 (layers n md (concat_of (map_over (kids_of md) l)))).
      apply andb_join; [ exact A | ].
      exact (IH n md p (concat_of (map_over (kids_of md) l)) Hf B).
Qed.

Lemma layers_of_a_member :
  forall (fuel : nat) (md : Medium) (p : nat -> bool) (l : list nat) (y : nat),
    mem_of y l = true -> all_of p (layers fuel md l) = true ->
    all_of p (layers fuel md (cons y nil)) = true.
Proof.
  intros fuel md p l. induction l as [ | z r IH ]; intros y Hm H.
  - discriminate Hm.
  - destruct (layers_of_app fuel md p (cons z nil) r H) as [ A B ].
    assert (Hm2 : orb (Nat.eqb z y) (mem_of y r) = true) by exact Hm.
    destruct (orb_true_split _ _ Hm2) as [ A1 | A2 ].
    + rewrite <- (nat_eqb_true z y A1). exact A.
    + exact (IH y A2 B).
Qed.

Lemma a_block_is_in_its_own_reach :
  forall (fuel : nat) (md : Medium) (b : nat),
    mem_of b (layers fuel md (cons b nil)) = true.
Proof.
  intros fuel md b. destruct fuel as [ | k ].
  - exact (mem_of_head b nil).
  - change (layers (S k) md (cons b nil))
      with (app (cons b nil)
             (layers k md (concat_of (map_over (kids_of md) (cons b nil))))).
    rewrite mem_of_app. rewrite (mem_of_head b nil). reflexivity.
Qed.

(* Reading 6's floor: a root is inside its own reachable set, so a covered
   root is itself whole. It is the case the walk below never revisits, every
   step of the walk being about a *child*. *)
Lemma a_covered_root_is_itself_whole :
  forall (m : Machine) (md : Medium) (b : nat),
    covered m md b = true -> complete (md b) = true.
Proof.
  intros m md b H.
  exact (covered_reaches_complete m md b b H
           (a_block_is_in_its_own_reach (height m) md b)).
Qed.

(* =========================================================================
   The copy-on-write commit, its plan, and what a crash point does to it.
   ========================================================================= *)

Record Write : Type := { w_block : nat; w_node : Node }.

Record Commit : Type := {
  cm_plan : list Write;
  cm_new_root : nat;
  cm_old_root : nat;
  cm_retained : list nat   (* R-10-010's retained snapshot roots *)
}.

Definition in_plan (p : list Write) (b : nat) : bool :=
  any_of (fun w => Nat.eqb (w_block w) b) p.

Definition place (md : Medium) (b : nat) (bk : Blk) : Medium :=
  fun x => if Nat.eqb b x then bk else md x.

Definition whole_of (m : Machine) (nd : Node) (c : nat) : Blk :=
  {| blk_node := nd; blk_len := node_granules m; blk_landed := node_granules m;
     blk_content := c; blk_tag := mac m c |}.

Definition torn_of (m : Machine) (nd : Node) (c g : nat) : Blk :=
  {| blk_node := nd; blk_len := node_granules m; blk_landed := g;
     blk_content := c; blk_tag := mac m c |}.

(* A node's extent bytes are its own block number here, which is a witness
   value and not a claim: what the statements need of `blk_content` is only
   that two blocks differ, which is R-10-022a's whole point. *)
(* The plan is scrutinized before the crash index, so that a crash past the
   end of a known plan reduces without the index being known: a family
   member is then decided by conversion at every index at once rather than
   at the finitely many a destruct would reach. *)
Fixpoint land (m : Machine) (n : nat) (p : list Write) (md : Medium)
              {struct p} : Medium :=
  match p with
  | nil => md
  | cons w r =>
      match n with
      | 0 => md
      | S k => land m k r (place md (w_block w) (whole_of m (w_node w) (w_block w)))
      end
  end.

(* The crash that catches one write in the middle of its granules: the first
   n writes landed whole and the next landed g of its granules. *)
Definition land_torn (m : Machine) (n g : nat) (p : list Write)
                     (md : Medium) : Medium :=
  match nth_opt p n with
  | None => land m n p md
  | Some w =>
      place (land m n p md) (w_block w) (torn_of m (w_node w) (w_block w) g)
  end.

Definition Sequencer : Type := Commit -> nat -> nat.

(* Reading 4 on the index side: the root is published by the last write of
   the plan, so the new root is current exactly when every write has
   landed. *)
Definition spec_sequencer : Sequencer :=
  fun c i => if Nat.leb (count_of (cm_plan c)) i then cm_new_root c else cm_old_root c.

(* -------------------------------------------------------------------------
   The admission predicate over a plan: what a composition must declare
   before the crash-consistency obligation is even askable of it. Each
   conjunct is stated of an arbitrary plan and each is refuted below.
   ------------------------------------------------------------------------- *)

(* Reading 5: a copy-on-write commit writes only blank blocks. *)
Definition allocates_blank (md : Medium) (c : Commit) : bool :=
  all_of (fun w => blank (md (w_block w))) (cm_plan c).

(* Reading 8: and none of them under a retained snapshot root. *)
Definition spares_the_retained (m : Machine) (md : Medium) (c : Commit) : bool :=
  all_of (fun w => negb (any_of (fun r => reaches m md r (w_block w))
                                (cm_retained c)))
         (cm_plan c).

(* The publish is last, which is what makes a crash before it a crash that
   never happened. *)
Definition root_is_last (c : Commit) : bool :=
  match last_opt (cm_plan c) with
  | None => false
  | Some w => Nat.eqb (w_block w) (cm_new_root c)
  end.

(* Reading 7: every child of a newly written node is either a block this
   commit writes or a block the medium already holds whole. *)
Definition kids_resolve (m : Machine) (md : Medium) (c : Commit) : bool :=
  all_of (fun w => all_of (fun k => orb (in_plan (cm_plan c) k) (covered m md k))
                          (node_kids (w_node w)))
         (cm_plan c).

Definition admissible (m : Machine) (md : Medium) (c : Commit) : bool :=
  andb (root_is_last c)
  (andb (allocates_blank md c)
  (andb (spares_the_retained m md c)
        (kids_resolve m md c))).

(* -------------------------------------------------------------------------
   The two obligations, each of an arbitrary sequencer, and stated over
   every crash point and every torn granule at once.
   ------------------------------------------------------------------------- *)

(* The copy-on-write property that matters: no committed root ever points at
   a partially written node. *)
Definition CrashConsistent (m : Machine) (md : Medium) (c : Commit)
                           (sq : Sequencer) : Prop :=
  forall i g : nat, covered m (land_torn m i g (cm_plan c) md) (sq c i) = true.

(* R-10-010's retained roots read exactly what they read before, at every
   crash point: a separate obligation, and reading 8 says why. *)
Definition RetainedRootsUnmoved (m : Machine) (md : Medium) (c : Commit) : Prop :=
  forall i g x : nat,
    any_of (fun r => reaches m md r x) (cm_retained c) = true ->
    land_torn m i g (cm_plan c) md x = md x.

(* -------------------------------------------------------------------------
   The lemmas about what a partial land does and does not touch.
   ------------------------------------------------------------------------- *)

Lemma in_plan_cons :
  forall (w : Write) (r : list Write) (b : nat),
    in_plan (cons w r) b = orb (Nat.eqb (w_block w) b) (in_plan r b).
Proof. intros w r b. reflexivity. Qed.

(* Reading a conjunction over a plan back at one of its blocks, in the two
   polarities the conjuncts below come in. Both are stated of an arbitrary
   predicate so that `allocates_blank` and `spares_the_retained` are
   instances rather than two more inductions. *)
Lemma a_plan_block_takes_the_conjunct :
  forall (q : nat -> bool) (p : list Write) (x : nat),
    all_of (fun w => q (w_block w)) p = true -> in_plan p x = true -> q x = true.
Proof.
  intros q p. induction p as [ | w r IH ]; intros x Ha H.
  - discriminate H.
  - simpl in Ha. destruct (andb_split _ _ Ha) as [ Hw Hr ].
    rewrite in_plan_cons in H. destruct (Nat.eqb (w_block w) x) eqn:Ew.
    + rewrite (nat_eqb_true _ _ Ew) in Hw. exact Hw.
    + simpl in H. exact (IH x Hr H).
Qed.

Lemma a_plan_block_takes_the_negated_conjunct :
  forall (q : nat -> bool) (p : list Write) (x : nat),
    all_of (fun w => negb (q (w_block w))) p = true ->
    in_plan p x = true -> q x = false.
Proof.
  intros q p x Ha H.
  assert (Hn : negb (q x) = true)
    by exact (a_plan_block_takes_the_conjunct (fun y => negb (q y)) p x Ha H).
  destruct (q x); [ discriminate Hn | reflexivity ].
Qed.

Lemma land_untouched :
  forall (m : Machine) (p : list Write) (n : nat) (md : Medium) (x : nat),
    in_plan p x = false -> land m n p md x = md x.
Proof.
  intros m p. induction p as [ | w r IH ]; intros n md x H.
  - reflexivity.
  - rewrite in_plan_cons in H. destruct (orb_split _ _ H) as [ Hw Hr ].
    destruct n as [ | k ]; [ reflexivity | ].
    simpl. rewrite (IH k _ x Hr). unfold place. rewrite Hw. reflexivity.
Qed.

Lemma nth_opt_is_in_the_plan :
  forall (p : list Write) (n : nat) (w : Write),
    nth_opt p n = Some w -> in_plan p (w_block w) = true.
Proof.
  intros p. induction p as [ | v r IH ]; intros n w H.
  - discriminate H.
  - destruct n as [ | k ].
    + simpl in H. injection H as H. rewrite H. rewrite in_plan_cons.
      rewrite nat_eqb_refl. reflexivity.
    + simpl in H. rewrite in_plan_cons. rewrite (IH k w H).
      destruct (Nat.eqb (w_block v) (w_block w)); reflexivity.
Qed.

Lemma land_torn_untouched :
  forall (m : Machine) (n g : nat) (p : list Write) (md : Medium) (x : nat),
    in_plan p x = false -> land_torn m n g p md x = md x.
Proof.
  intros m n g p md x H. unfold land_torn. destruct (nth_opt p n) eqn:E.
  - unfold place. destruct (Nat.eqb (w_block w) x) eqn:Eb.
    + assert (Hin : in_plan p (w_block w) = true)
        by exact (nth_opt_is_in_the_plan p n w E).
      rewrite (nat_eqb_true _ _ Eb) in Hin. rewrite Hin in H. discriminate H.
    + exact (land_untouched m p n md x H).
  - exact (land_untouched m p n md x H).
Qed.

(* S7 (R-10-010, reading 8): every retained snapshot root reads what it read
   before, at every crash point and every torn granule. Stated of an
   arbitrary medium, commit and retained set. *)
Theorem the_specification_leaves_every_retained_root_unmoved :
  forall (m : Machine) (md : Medium) (c : Commit),
    spares_the_retained m md c = true -> RetainedRootsUnmoved m md c.
Proof.
  intros m md c Hs i g x Hx. apply land_torn_untouched.
  destruct (in_plan (cm_plan c) x) eqn:E; [ | reflexivity ].
  rewrite (a_plan_block_takes_the_negated_conjunct
             (fun y => any_of (fun r => reaches m md r y) (cm_retained c))
             (cm_plan c) x Hs E) in Hx.
  discriminate Hx.
Qed.

(* S8: the general half of the crash-consistency obligation. Before the plan
   completes the current root is the previous one, and a commit that writes
   only blank blocks cannot have touched anything that root reaches, so the
   previous root covers only whole nodes at every crash point and every torn
   granule. Arbitrary medium, arbitrary allocator, arbitrary plan. *)
Theorem the_previous_root_survives_every_crash_point :
  forall (m : Machine) (md : Medium) (c : Commit) (i g : nat),
    covered m md (cm_old_root c) = true ->
    allocates_blank md c = true ->
    Nat.leb (count_of (cm_plan c)) i = false ->
    covered m (land_torn m i g (cm_plan c) md) (spec_sequencer c i) = true.
Proof.
  intros m md c i g Hc Ha Hi. unfold spec_sequencer. rewrite Hi.
  apply (cover_survives_a_write_off_the_cover m md); [ exact Hc | ].
  intros x Hx. apply land_torn_untouched.
  destruct (in_plan (cm_plan c) x) eqn:E; [ | reflexivity ].
  (* x is a plan block, so it is blank, so the old root does not reach it *)
  assert (Hb : blank (md x) = true)
    by exact (a_plan_block_takes_the_conjunct (fun y => blank (md y))
                (cm_plan c) x Ha E).
  rewrite (a_blank_block_is_out_of_every_cover m md (cm_old_root c) x Hc Hb)
    in Hx. discriminate Hx.
Qed.

(* S9: past the plan every crash point is one medium, so a single check
   settles all of them. `land` consumes the whole plan and stops, so the
   index of the crash stops mattering once it has. *)
Lemma land_stabilizes :
  forall (m : Machine) (p : list Write) (i : nat) (md : Medium),
    Nat.leb (count_of p) i = true -> land m i p md = land m (count_of p) p md.
Proof.
  intros m p. induction p as [ | w r IH ]; intros i md H.
  - destruct i as [ | k ]; reflexivity.
  - destruct i as [ | k ]; [ discriminate H | ].
    simpl in H. simpl. exact (IH k _ H).
Qed.

Lemma nth_opt_past_the_end :
  forall (p : list Write) (i : nat),
    Nat.leb (count_of p) i = true -> nth_opt p i = None.
Proof.
  intros p. induction p as [ | w r IH ]; intros i H.
  - destruct i; reflexivity.
  - destruct i as [ | k ]; [ discriminate H | ].
    simpl in H. simpl. exact (IH k H).
Qed.

Theorem past_the_plan_every_crash_point_is_one_medium :
  forall (m : Machine) (md : Medium) (p : list Write) (i g : nat),
    Nat.leb (count_of p) i = true ->
    land_torn m i g p md = land m (count_of p) p md.
Proof.
  intros m md p i g H. unfold land_torn.
  rewrite (nth_opt_past_the_end p i H). exact (land_stabilizes m p i md H).
Qed.

(* S10: and every block the plan writes is whole in that medium, so what a
   completed commit publishes is a root over nodes that all landed. *)
Lemma every_planned_block_is_whole :
  forall (m : Machine) (p : list Write) (md : Medium) (b : nat),
    in_plan p b = true -> complete (land m (count_of p) p md b) = true.
Proof.
  intros m p. induction p as [ | w r IH ]; intros md b H.
  - discriminate H.
  - rewrite in_plan_cons in H. simpl.
    destruct (in_plan r b) eqn:Er.
    + exact (IH _ b Er).
    + assert (Ew : Nat.eqb (w_block w) b = true).
      { destruct (Nat.eqb (w_block w) b); [ reflexivity | discriminate H ]. }
      rewrite (land_untouched m r (count_of r) _ b Er).
      unfold place. rewrite Ew. unfold complete. simpl.
      exact (nat_eqb_refl (node_granules m)).
Qed.

(* =========================================================================
   S11: the copy-on-write soundness direction, of an arbitrary machine,
   medium and commit under the admission predicate.

   This is what `admissible` gates. Before the plan completes the published
   root is the previous one, which S8 settles; past it the published root is
   the one the plan wrote, and the walk down that root is what the three
   conjuncts `admissible` carries are for: the publish is last, so the new
   root is a block the plan wrote and therefore whole; the plan writes only
   blank blocks, so nothing the old medium covered was disturbed; and every
   child of a newly written node either is another block the plan wrote or
   was already covered, so the walk terminates at whole nodes at every step
   down to the declared height.
   ========================================================================= *)

Definition landed (m : Machine) (c : Commit) (md : Medium) : Medium :=
  land m (count_of (cm_plan c)) (cm_plan c) md.

(* Which write of the plan a landed block came from, together with whatever
   conjunct the plan was known to satisfy at that write. The conjunct is a
   parameter because `kids_resolve` is a property of the whole write and not
   of its block number, so the block-level extraction lemmas above do not
   reach it. *)
Lemma land_places_a_planned_node :
  forall (m : Machine) (p : list Write) (Q : Write -> bool) (md : Medium) (x : nat),
    all_of Q p = true -> in_plan p x = true ->
    exists w : Write,
      Q w = true /\ land m (count_of p) p md x = whole_of m (w_node w) x.
Proof.
  intros m p Q. induction p as [ | v r IH ]; intros md x Hq H.
  - discriminate H.
  - simpl in Hq. destruct (andb_split _ _ Hq) as [ Hv Hr ].
    destruct (in_plan r x) eqn:Er.
    + destruct (IH (place md (w_block v) (whole_of m (w_node v) (w_block v))) x Hr Er)
        as [ w [ Hw Hl ] ].
      exists w. split; [ exact Hw | ]. simpl. exact Hl.
    + exists v. split; [ exact Hv | ].
      assert (Ex : w_block v = x).
      { apply nat_eqb_true. rewrite in_plan_cons in H. rewrite Er in H.
        rewrite (orb_false_right _) in H. exact H. }
      simpl. rewrite (land_untouched m r (count_of r) _ x Er).
      unfold place. rewrite Ex. rewrite nat_eqb_refl. reflexivity.
Qed.

Lemma last_opt_is_in_the_plan :
  forall (p : list Write) (w : Write),
    last_opt p = Some w -> in_plan p (w_block w) = true.
Proof.
  intros p. induction p as [ | v r IH ]; intros w H.
  - discriminate H.
  - destruct r as [ | u s ].
    + simpl in H. injection H as H. rewrite <- H. rewrite in_plan_cons.
      rewrite nat_eqb_refl. reflexivity.
    + assert (Hl : last_opt (cons u s) = Some w) by exact H.
      rewrite in_plan_cons. rewrite (IH w Hl).
      destruct (Nat.eqb (w_block v) (w_block w)); reflexivity.
Qed.

(* Reading 5 as a frame: a commit that writes only blank blocks disturbs
   nothing any covered root reaches, so every cover of the old medium is a
   cover of the medium the whole plan landed into. *)
Lemma a_cover_survives_the_whole_commit :
  forall (m : Machine) (md : Medium) (c : Commit) (b : nat),
    allocates_blank md c = true ->
    covered m md b = true ->
    covered m (landed m c md) b = true.
Proof.
  intros m md c b Ha Hc.
  apply (cover_survives_a_write_off_the_cover m md); [ exact Hc | ].
  intros x Hx. unfold landed. apply land_untouched.
  destruct (in_plan (cm_plan c) x) eqn:E; [ | reflexivity ].
  assert (Hb : blank (md x) = true)
    by exact (a_plan_block_takes_the_conjunct (fun y => blank (md y))
                (cm_plan c) x Ha E).
  rewrite (a_blank_block_is_out_of_every_cover m md b x Hc Hb) in Hx.
  discriminate Hx.
Qed.

(* Reading 7 in the medium the commit landed into: every child a newly
   written node names is either another block this commit wrote or a block
   the new medium still holds whole. *)
Lemma every_kid_of_a_planned_node_resolves :
  forall (m : Machine) (md : Medium) (c : Commit) (x k : nat),
    allocates_blank md c = true ->
    kids_resolve m md c = true ->
    in_plan (cm_plan c) x = true ->
    mem_of k (kids_of (landed m c md) x) = true ->
    orb (in_plan (cm_plan c) k) (covered m (landed m c md) k) = true.
Proof.
  intros m md c x k Ha Hk Hx Hm.
  destruct (land_places_a_planned_node m (cm_plan c)
              (fun w => all_of (fun y => orb (in_plan (cm_plan c) y)
                                             (covered m md y))
                               (node_kids (w_node w))) md x Hk Hx)
    as [ w [ Hw Hl ] ].
  assert (Hkids : kids_of (landed m c md) x = node_kids (w_node w)).
  { unfold kids_of. unfold landed. rewrite Hl. reflexivity. }
  rewrite Hkids in Hm.
  assert (Hres : orb (in_plan (cm_plan c) k) (covered m md k) = true)
    by exact (all_of_elim _ _ k Hw Hm).
  destruct (orb_true_split _ _ Hres) as [ A | B ].
  - rewrite A. reflexivity.
  - rewrite (a_cover_survives_the_whole_commit m md c k Ha B).
    destruct (in_plan (cm_plan c) k); reflexivity.
Qed.

(* The walk itself: a frontier every member of which is either a block the
   plan wrote or a block already covered to the remaining depth stays whole
   all the way down. The depth decreases at each step, which is why the
   bounded `covered_to` is what the invariant carries and `covered` is only
   its instance at the declared height. *)
Lemma the_frontier_stays_covered :
  forall (m : Machine) (md : Medium) (c : Commit) (fuel : nat) (l : list nat),
    allocates_blank md c = true ->
    kids_resolve m md c = true ->
    Nat.leb fuel (height m) = true ->
    all_of (fun x => orb (in_plan (cm_plan c) x)
                         (covered_to fuel (landed m c md) x)) l = true ->
    all_of (fun x => complete (landed m c md x)) (layers fuel (landed m c md) l)
      = true.
Proof.
  intros m md c fuel. induction fuel as [ | k IH ]; intros l Ha Hk Hf Hl.
  - simpl. apply all_of_intro. intros x Hx.
    assert (Hr := all_of_elim _ _ x Hl Hx).
    destruct (orb_true_split _ _ Hr) as [ A | B ].
    + exact (every_planned_block_is_whole m (cm_plan c) md x A).
    + unfold covered_to in B. simpl in B.
      destruct (andb_split _ _ B) as [ B1 _ ]. exact B1.
  - simpl.
    rewrite (all_of_app nat (fun x => complete (landed m c md x)) l
               (layers k (landed m c md)
                  (concat_of (map_over (kids_of (landed m c md)) l)))).
    apply andb_join.
    + apply all_of_intro. intros x Hx.
      assert (Hr := all_of_elim _ _ x Hl Hx).
      destruct (orb_true_split _ _ Hr) as [ A | B ].
      * exact (every_planned_block_is_whole m (cm_plan c) md x A).
      * unfold covered_to in B.
        change (layers (S k) (landed m c md) (cons x nil))
          with (app (cons x nil)
                 (layers k (landed m c md)
                    (concat_of (map_over (kids_of (landed m c md))
                                  (cons x nil))))) in B.
        rewrite (all_of_app nat (fun y => complete (landed m c md y))
                   (cons x nil) _) in B.
        destruct (andb_split _ _ B) as [ B1 _ ]. simpl in B1.
        destruct (andb_split _ _ B1) as [ B2 _ ]. exact B2.
    + apply (IH (concat_of (map_over (kids_of (landed m c md)) l)) Ha Hk
              (leb_of_succ k (height m) Hf)).
      apply all_of_intro. intros y Hy.
      destruct (mem_of_concat (kids_of (landed m c md)) l y Hy) as [ x [ Hx Hky ] ].
      assert (Hr := all_of_elim _ _ x Hl Hx).
      destruct (orb_true_split _ _ Hr) as [ A | B ].
      * assert (Hres := every_kid_of_a_planned_node_resolves m md c x y Ha Hk A Hky).
        destruct (orb_true_split _ _ Hres) as [ C | D ].
        { rewrite C. reflexivity. }
        { unfold covered in D. unfold reach_set in D.
          assert (Ey : covered_to k (landed m c md) y = true).
          { unfold covered_to.
            exact (covered_to_monotone (height m) k (landed m c md)
                     (fun z => complete (landed m c md z)) (cons y nil)
                     (leb_of_succ k (height m) Hf) D). }
          rewrite Ey. destruct (in_plan (cm_plan c) y); reflexivity. }
      * unfold covered_to in B.
        change (layers (S k) (landed m c md) (cons x nil))
          with (app (cons x nil)
                 (layers k (landed m c md)
                    (concat_of (map_over (kids_of (landed m c md))
                                  (cons x nil))))) in B.
        rewrite (all_of_app nat (fun z => complete (landed m c md z))
                   (cons x nil) _) in B.
        destruct (andb_split _ _ B) as [ _ B2 ].
        destruct (layers_of_app k (landed m c md)
                    (fun z => complete (landed m c md z))
                    (kids_of (landed m c md) x) nil B2) as [ B3 _ ].
        assert (Ey : covered_to k (landed m c md) y = true).
        { unfold covered_to.
          exact (layers_of_a_member k (landed m c md)
                   (fun z => complete (landed m c md z))
                   (kids_of (landed m c md) x) y Hky B3). }
        rewrite Ey. destruct (in_plan (cm_plan c) y); reflexivity.
Qed.

(* S11a: what a completed commit publishes is a root over nodes that all
   landed, of an arbitrary machine, medium and commit. *)
Theorem the_new_root_is_covered_when_the_plan_has_landed :
  forall (m : Machine) (md : Medium) (c : Commit),
    root_is_last c = true ->
    allocates_blank md c = true ->
    kids_resolve m md c = true ->
    covered m (landed m c md) (cm_new_root c) = true.
Proof.
  intros m md c Hr Ha Hk.
  assert (Hin : in_plan (cm_plan c) (cm_new_root c) = true).
  { unfold root_is_last in Hr.
    destruct (last_opt (cm_plan c)) as [ w | ] eqn:E.
    - rewrite <- (nat_eqb_true _ _ Hr).
      exact (last_opt_is_in_the_plan (cm_plan c) w E).
    - discriminate Hr. }
  unfold covered. unfold reach_set.
  apply (the_frontier_stays_covered m md c (height m) (cons (cm_new_root c) nil)
           Ha Hk (nat_leb_refl (height m))).
  simpl. rewrite Hin. reflexivity.
Qed.

(* S11 (R-10-036, R-16-003, readings 5 and 7): an admissible commit is crash
   consistent at every crash index and every torn granule. Arbitrary
   machine, arbitrary medium, arbitrary allocator, arbitrary plan, and the
   admission predicate is the hypothesis that gates it. Four constructions
   below fail one conjunct apiece; three of them are refuted of this
   obligation and the fourth is not, which is what separates R-10-010's
   retained-root obligation from this one. *)
Theorem an_admissible_commit_is_crash_consistent :
  forall (m : Machine) (md : Medium) (c : Commit),
    covered m md (cm_old_root c) = true ->
    admissible m md c = true ->
    CrashConsistent m md c spec_sequencer.
Proof.
  intros m md c Hold Hadm i g.
  destruct (andb_split _ _ Hadm) as [ Hroot R1 ].
  destruct (andb_split _ _ R1) as [ Hblank R2 ].
  destruct (andb_split _ _ R2) as [ _ Hkids ].
  destruct (Nat.leb (count_of (cm_plan c)) i) eqn:E.
  - unfold spec_sequencer. rewrite E.
    rewrite (past_the_plan_every_crash_point_is_one_medium m md (cm_plan c) i g E).
    exact (the_new_root_is_covered_when_the_plan_has_landed m md c
             Hroot Hblank Hkids).
  - exact (the_previous_root_survives_every_crash_point m md c i g Hold Hblank E).
Qed.

(* =========================================================================
   L1's logical content: R-10-003's one parametric index, generic over key
   type and verified once.

   Reading 11: the key type, its order, its equality and the five laws the
   index needs are fields of a record rather than a class the prelude does
   not carry, so an instance discharges them where the review gate can read
   the discharge. R-10-005's snapshot version field is L2's and is not
   modelled; what a key *is* stays the composition's, which is exactly what
   "generic over key type, verified once and instantiated per object class"
   asks for.
   ========================================================================= *)

Record KeyAlgebra : Type := {
  Key : Type;
  key_leb : Key -> Key -> bool;
  key_eqb : Key -> Key -> bool;
  key_eqb_refl : forall a : Key, key_eqb a a = true;
  key_eqb_true : forall a b : Key, key_eqb a b = true -> a = b;
  key_leb_total : forall a b : Key, orb (key_leb a b) (key_leb b a) = true;
  key_leb_trans : forall a b c : Key,
    key_leb a b = true -> key_leb b c = true -> key_leb a c = true;
  key_leb_antisym : forall a b : Key,
    key_leb a b = true -> key_leb b a = true -> key_eqb a b = true
}.

Definition Index (ka : KeyAlgebra) : Type := list (prod (Key ka) nat).

(* Ordered insertion with replace-on-equal: R-10-005's typed keys in one
   keyspace read at the layer below it, where a key is whatever the algebra
   says and a value is the index's payload. *)
Fixpoint ins (ka : KeyAlgebra) (k : Key ka) (v : nat) (ix : Index ka) : Index ka :=
  match ix with
  | nil => cons (pair k v) nil
  | cons e r =>
      if key_eqb ka k (fst e) then cons (pair k v) r
      else if key_leb ka k (fst e) then cons (pair k v) (cons e r)
      else cons e (ins ka k v r)
  end.

Fixpoint ins_all (ka : KeyAlgebra) (l : list (prod (Key ka) nat))
                 (ix : Index ka) : Index ka :=
  match l with
  | nil => ix
  | cons e r => ins_all ka r (ins ka (fst e) (snd e) ix)
  end.

Fixpoint look (ka : KeyAlgebra) (k : Key ka) (ix : Index ka) : option nat :=
  match ix with
  | nil => None
  | cons e r => if key_eqb ka k (fst e) then Some (snd e) else look ka k r
  end.

(* Strict increase, stated as "the head is strictly below everything after
   it" so that the insertion proof is one induction and not two. *)
Fixpoint ge_all (ka : KeyAlgebra) (k : Key ka) (ix : Index ka) : bool :=
  match ix with
  | nil => true
  | cons e r =>
      andb (andb (key_leb ka k (fst e)) (negb (key_eqb ka k (fst e))))
           (ge_all ka k r)
  end.

Fixpoint sorted (ka : KeyAlgebra) (ix : Index ka) : bool :=
  match ix with
  | nil => true
  | cons e r => andb (ge_all ka (fst e) r) (sorted ka r)
  end.

(* -------------------------------------------------------------------------
   The algebra's derived facts, each proved from the five laws and never
   from a carrier.
   ------------------------------------------------------------------------- *)

Lemma key_eqb_sym :
  forall (ka : KeyAlgebra) (a b : Key ka),
    key_eqb ka a b = true -> key_eqb ka b a = true.
Proof.
  intros ka a b H. rewrite (key_eqb_true ka a b H). exact (key_eqb_refl ka b).
Qed.

Lemma key_eqb_false_sym :
  forall (ka : KeyAlgebra) (a b : Key ka),
    key_eqb ka a b = false -> key_eqb ka b a = false.
Proof.
  intros ka a b H. destruct (key_eqb ka b a) eqn:E; [ | reflexivity ].
  rewrite (key_eqb_sym ka b a E) in H. discriminate H.
Qed.

Lemma key_not_leb_gives_leb :
  forall (ka : KeyAlgebra) (a b : Key ka),
    key_leb ka a b = false -> key_leb ka b a = true.
Proof.
  intros ka a b H.
  assert (Ht : orb (key_leb ka a b) (key_leb ka b a) = true)
    by exact (key_leb_total ka a b).
  rewrite H in Ht. simpl in Ht. exact Ht.
Qed.

Lemma ge_all_widen :
  forall (ka : KeyAlgebra) (j k : Key ka) (ix : Index ka),
    key_leb ka j k = true -> key_eqb ka j k = false ->
    ge_all ka k ix = true -> ge_all ka j ix = true.
Proof.
  intros ka j k ix. induction ix as [ | e r IH ]; intros Hl He Hg.
  - reflexivity.
  - simpl in Hg. destruct (andb_split _ _ Hg) as [ Hh Hr ].
    destruct (andb_split _ _ Hh) as [ Hkl Hke ].
    simpl. apply andb_join; [ | exact (IH Hl He Hr) ].
    apply andb_join.
    + exact (key_leb_trans ka j k (fst e) Hl Hkl).
    + destruct (key_eqb ka j (fst e)) eqn:Ej; [ | reflexivity ].
      (* j = fst e, and k <= fst e = j <= k forces key_eqb j k, refuted *)
      rewrite <- (key_eqb_true ka j (fst e) Ej) in Hkl.
      rewrite (key_leb_antisym ka j k Hl Hkl) in He. discriminate He.
Qed.

Lemma ins_keeps_ge_all :
  forall (ka : KeyAlgebra) (j k : Key ka) (v : nat) (ix : Index ka),
    key_leb ka j k = true -> key_eqb ka j k = false ->
    ge_all ka j ix = true -> ge_all ka j (ins ka k v ix) = true.
Proof.
  intros ka j k v ix. induction ix as [ | e r IH ]; intros Hl He Hg.
  - simpl. apply andb_join; [ apply andb_join | reflexivity ].
    + exact Hl.
    + rewrite He. reflexivity.
  - simpl in Hg. destruct (andb_split _ _ Hg) as [ Hh Hr ].
    simpl. destruct (key_eqb ka k (fst e)) eqn:Ek.
    + simpl. apply andb_join; [ | exact Hr ].
      apply andb_join; [ exact Hl | rewrite He; reflexivity ].
    + destruct (key_leb ka k (fst e)) eqn:El.
      * simpl. apply andb_join.
        { apply andb_join; [ exact Hl | rewrite He; reflexivity ]. }
        simpl. apply andb_join; [ exact Hh | exact Hr ].
      * simpl. apply andb_join; [ exact Hh | exact (IH Hl He Hr) ].
Qed.

(* S11 (R-10-003): insertion preserves the index's order, of an arbitrary
   key algebra and an arbitrary index. This is the "verified once" half of
   that entry: no instance appears in the statement or the proof. *)
Theorem inserting_preserves_the_order :
  forall (ka : KeyAlgebra) (k : Key ka) (v : nat) (ix : Index ka),
    sorted ka ix = true -> sorted ka (ins ka k v ix) = true.
Proof.
  intros ka k v ix. induction ix as [ | e r IH ]; intros Hs.
  - reflexivity.
  - simpl in Hs. destruct (andb_split _ _ Hs) as [ Hg Hr ].
    simpl. destruct (key_eqb ka k (fst e)) eqn:Ek.
    + simpl. apply andb_join; [ | exact Hr ].
      rewrite (key_eqb_true ka k (fst e) Ek). exact Hg.
    + destruct (key_leb ka k (fst e)) eqn:El.
      * simpl. apply andb_join.
        { apply andb_join.
          - apply andb_join; [ exact El | rewrite Ek; reflexivity ].
          - exact (ge_all_widen ka k (fst e) r El Ek Hg). }
        simpl. apply andb_join; [ exact Hg | exact Hr ].
      * simpl. apply andb_join; [ | exact (IH Hr) ].
        apply (ins_keeps_ge_all ka (fst e) k v r).
        { exact (key_not_leb_gives_leb ka k (fst e) El). }
        { exact (key_eqb_false_sym ka k (fst e) Ek). }
        { exact Hg. }
Qed.

Theorem inserting_a_list_preserves_the_order :
  forall (ka : KeyAlgebra) (l : list (prod (Key ka) nat)) (ix : Index ka),
    sorted ka ix = true -> sorted ka (ins_all ka l ix) = true.
Proof.
  intros ka l. induction l as [ | e r IH ]; intros ix Hs.
  - exact Hs.
  - simpl. exact (IH _ (inserting_preserves_the_order ka (fst e) (snd e) ix Hs)).
Qed.

(* S12 (R-10-003): what was written is what is read, and nothing else moves.
   The two halves are separate obligations, and the constructions below
   break one apiece. *)
Theorem the_key_just_written_reads_back :
  forall (ka : KeyAlgebra) (k : Key ka) (v : nat) (ix : Index ka),
    look ka k (ins ka k v ix) = Some v.
Proof.
  intros ka k v ix. induction ix as [ | e r IH ].
  - simpl. rewrite (key_eqb_refl ka k). reflexivity.
  - simpl. destruct (key_eqb ka k (fst e)) eqn:Ek.
    + simpl. rewrite (key_eqb_refl ka k). reflexivity.
    + destruct (key_leb ka k (fst e)) eqn:El.
      * simpl. rewrite (key_eqb_refl ka k). reflexivity.
      * simpl. rewrite Ek. exact IH.
Qed.

Theorem no_other_key_moves :
  forall (ka : KeyAlgebra) (k j : Key ka) (v : nat) (ix : Index ka),
    key_eqb ka j k = false -> look ka j (ins ka k v ix) = look ka j ix.
Proof.
  intros ka k j v ix Hjk. induction ix as [ | e r IH ].
  - simpl. rewrite Hjk. reflexivity.
  - simpl. destruct (key_eqb ka k (fst e)) eqn:Ek.
    + simpl. rewrite Hjk. rewrite <- (key_eqb_true ka k (fst e) Ek).
      rewrite Hjk. reflexivity.
    + destruct (key_leb ka k (fst e)) eqn:El.
      * simpl. rewrite Hjk. reflexivity.
      * simpl. destruct (key_eqb ka j (fst e)); [ reflexivity | exact IH ].
Qed.

(* S12a (R-10-003): the order two distinct keys arrived in does not change
   what the index answers at any key, of an arbitrary key algebra, an
   arbitrary index and an arbitrary query. This is the generality the demo's
   twenty conversions below do not carry: they decide the family and this
   decides the reason, and it follows from S12's two halves alone. *)
Theorem transposing_two_distinct_writes_answers_the_same_everywhere :
  forall (ka : KeyAlgebra) (a b : Key ka) (u v : nat) (ix : Index ka) (q : Key ka),
    key_eqb ka a b = false ->
    look ka q (ins ka b v (ins ka a u ix))
      = look ka q (ins ka a u (ins ka b v ix)).
Proof.
  intros ka a b u v ix q Hab.
  destruct (key_eqb ka q a) eqn:Eqa.
  - rewrite (key_eqb_true ka q a Eqa).
    rewrite (no_other_key_moves ka b a v (ins ka a u ix) Hab).
    rewrite (the_key_just_written_reads_back ka a u ix).
    rewrite (the_key_just_written_reads_back ka a u (ins ka b v ix)).
    reflexivity.
  - destruct (key_eqb ka q b) eqn:Eqb.
    + rewrite (key_eqb_true ka q b Eqb).
      rewrite (the_key_just_written_reads_back ka b v (ins ka a u ix)).
      rewrite (no_other_key_moves ka a b u (ins ka b v ix)
                 (key_eqb_false_sym ka a b Hab)).
      rewrite (the_key_just_written_reads_back ka b v ix). reflexivity.
    + rewrite (no_other_key_moves ka b q v (ins ka a u ix) Eqb).
      rewrite (no_other_key_moves ka a q u ix Eqa).
      rewrite (no_other_key_moves ka a q u (ins ka b v ix) Eqa).
      rewrite (no_other_key_moves ka b q v ix Eqb).
      reflexivity.
Qed.

(* -------------------------------------------------------------------------
   R-10-004's buffered updates, and the fallback the same entry names.
   ------------------------------------------------------------------------- *)

(* A node's message log beside the entries under it: the buffer is read
   first, which is what makes a buffered write visible before it is
   flushed. *)
Definition Buffered (ka : KeyAlgebra) : Type := prod (Index ka) (Index ka).

Definition blook (ka : KeyAlgebra) (k : Key ka) (bx : Buffered ka) : option nat :=
  match look ka k (fst bx) with
  | Some v => Some v
  | None => look ka k (snd bx)
  end.

Definition flush (ka : KeyAlgebra) (bx : Buffered ka) : Buffered ka :=
  pair nil (ins_all ka (fst bx) (snd bx)).

(* R-10-004's named fallback, the plain copy-on-write B+ tree with no
   message log: it reads the flushed side alone. It is an *admitted*
   alternative and not a refuted one, which is why it is exhibited beside
   the specification rather than refuted of it. *)
Definition plain_look (ka : KeyAlgebra) (k : Key ka) (bx : Buffered ka) : option nat :=
  look ka k (snd bx).

Theorem a_buffered_message_shadows_the_entry_beneath_it :
  forall (ka : KeyAlgebra) (k : Key ka) (v : nat) (ix1 ix2 : Index ka),
    look ka k ix1 = Some v -> blook ka k (pair ix1 ix2) = Some v.
Proof. intros ka k v ix1 ix2 H. unfold blook. simpl. rewrite H. reflexivity. Qed.

Theorem an_unbuffered_key_falls_through :
  forall (ka : KeyAlgebra) (k : Key ka) (ix1 ix2 : Index ka),
    look ka k ix1 = None -> blook ka k (pair ix1 ix2) = look ka k ix2.
Proof. intros ka k ix1 ix2 H. unfold blook. simpl. rewrite H. reflexivity. Qed.

Theorem a_flushed_node_has_an_empty_buffer :
  forall (ka : KeyAlgebra) (k : Key ka) (bx : Buffered ka),
    blook ka k (flush ka bx) = plain_look ka k (flush ka bx).
Proof. intros ka k bx. unfold blook. unfold plain_look. reflexivity. Qed.

(* -------------------------------------------------------------------------
   The node occupancy ceiling (gap b).
   ------------------------------------------------------------------------- *)

Fixpoint chunks {A : Type} (fuel n : nat) (l : list A) : list (list A) :=
  match fuel with
  | 0 => nil
  | S f =>
      match l with
      | nil => nil
      | cons _ _ => cons (take n l) (chunks f n (drop n l))
      end
  end.

Definition leaves {A : Type} (n : nat) (l : list A) : list (list A) :=
  chunks (count_of l) n l.

Lemma take_is_bounded :
  forall (A : Type) (n : nat) (l : list A), Nat.leb (count_of (take n l)) n = true.
Proof.
  intros A n. induction n as [ | k IH ]; intros l.
  - destruct l; reflexivity.
  - destruct l as [ | x r ]; [ reflexivity | simpl; exact (IH r) ].
Qed.

(* The chunking helper's own bound, named for what it is: a fact about
   `chunks` over an arbitrary list, and not yet a property of any node. *)
Lemma no_chunk_holds_more_than_the_bound :
  forall (A : Type) (fuel n : nat) (l : list A),
    all_of (fun c => Nat.leb (count_of c) n) (chunks fuel n l) = true.
Proof.
  intros A fuel. induction fuel as [ | f IH ]; intros n l.
  - reflexivity.
  - destruct l as [ | x r ]; [ reflexivity | ].
    simpl. apply andb_join.
    + exact (take_is_bounded A n (cons x r)).
    + exact (IH n (drop n (cons x r))).
Qed.

(* -------------------------------------------------------------------------
   And the occupancy obligation itself, over the nodes this file models
   (reading 12). A node is well formed when it holds no more keys than the
   declared fanout, names no more children than the declared fanout, and
   carries exactly one tag per child, which is R-10-022a's clause read as a
   shape rather than as a read. The *minimum* is not stated because no entry
   fixes one, which is gap b's other half.
   ------------------------------------------------------------------------- *)

Definition node_fits (m : Machine) (nd : Node) : bool :=
  andb (Nat.leb (count_of (node_keys nd)) (fanout m))
  (andb (Nat.leb (count_of (node_kids nd)) (fanout m))
        (Nat.eqb (count_of (node_tags nd)) (count_of (node_kids nd)))).

Definition leaf_holding (keys : list nat) : Node :=
  {| node_keys := keys; node_kids := nil; node_tags := nil |}.

Definition Builder : Type := Machine -> list nat -> list Node.

Definition spec_builder : Builder :=
  fun m keys => map_over leaf_holding (leaves (fanout m) keys).

Definition NoNodeOverflows (bd : Builder) : Prop :=
  forall (m : Machine) (keys : list nat),
    all_of (node_fits m) (bd m keys) = true.

(* S13 (R-10-003, R-10-022a, gap b): every node a build produces fits the
   declared fanout, of an arbitrary machine and an arbitrary key list. *)
Theorem the_specification_builder_overflows_no_node : NoNodeOverflows spec_builder.
Proof.
  intros m keys. unfold spec_builder.
  rewrite (all_of_map (list nat) Node (node_fits m) leaf_holding
             (leaves (fanout m) keys)).
  apply (all_of_mono (list nat) (fun ch => Nat.leb (count_of ch) (fanout m))
           (fun ch => node_fits m (leaf_holding ch))).
  - intros ch Hch. unfold node_fits. unfold leaf_holding. simpl.
    apply andb_join; [ exact Hch | reflexivity ].
  - unfold leaves.
    exact (no_chunk_holds_more_than_the_bound nat (count_of keys)
             (fanout m) keys).
Qed.

(* The build that cuts one key past the declared fanout: the same partition
   of the same keys, one key too wide. *)
Definition overflowing_builder : Builder :=
  fun m keys => map_over leaf_holding (chunks (count_of keys) (S (fanout m)) keys).

(* And the occupancy of a whole tree rather than of one node: every node a
   root reaches fits. This is what makes the bound a property of the tree. *)
Definition every_reached_node_fits (m : Machine) (md : Medium) (b : nat) : bool :=
  all_of (fun x => node_fits m (blk_node (md x))) (reach_set m md b).

(* =========================================================================
   R-10-022a: the tag is held by the node that references the extent.
   ========================================================================= *)

(* The tag the referring node holds for its i-th child. The `0` is the
   fallback a node with no tag at that position takes, and it is the one
   place a numeral stands in a definition on this side of the file. *)
Definition expects (nd : Node) (i : nat) : nat := nth_or (node_tags nd) i 0.

Definition Placement : Type := Medium -> Node -> nat -> nat -> bool.

Definition spec_placement (m : Machine) : Placement :=
  fun md nd i b => Nat.eqb (mac m (blk_content (md b))) (expects nd i).

(* The construction R-10-022a's own sentence excludes: the tag stored beside
   the ciphertext it authenticates, which verifies exactly the read that was
   made rather than the read that was meant. *)
Definition beside_placement (m : Machine) : Placement :=
  fun md _ _ b => Nat.eqb (mac m (blk_content (md b))) (blk_tag (md b)).

(* R-10-022a's own clause, stated of an arbitrary placement rather than as
   the specification's body read back: two media that agree on what a block
   *contains* answer alike, however they differ in what they store beside
   it. A placement satisfying this reads the referring node's tag and cannot
   be reading the block's own. *)
Definition ReadsTheReferrersTag (pl : Placement) : Prop :=
  forall (md1 md2 : Medium) (nd : Node) (i b : nat),
    blk_content (md1 b) = blk_content (md2 b) -> pl md1 nd i b = pl md2 nd i b.

(* S14 (R-10-022a, R-10-021): a device free to move a block cannot make a
   mis-placed one open, because what the reader compares against came from
   the node that referenced it. *)
Theorem the_specification_reads_the_referrers_tag :
  forall m : Machine, ReadsTheReferrersTag (spec_placement m).
Proof.
  intros m md1 md2 nd i b H. unfold spec_placement. rewrite H. reflexivity.
Qed.

(* The same clause read at one medium. This one is the unfolded body of
   `spec_placement`, so the theorem side of it carries no content and the
   refutation below is what is load-bearing; it is kept because it is the
   form a reader checks a mis-directed read against, and the obligation that
   an alternative construction can fail is the one above. *)
Definition RefusesAMisdirectedRead (m : Machine) (pl : Placement) : Prop :=
  forall (md : Medium) (nd : Node) (i b : nat),
    Nat.eqb (mac m (blk_content (md b))) (expects nd i) = false ->
    pl md nd i b = false.

Theorem the_specification_refuses_a_misdirected_read :
  forall m : Machine, RefusesAMisdirectedRead m (spec_placement m).
Proof. intros m md nd i b H. unfold spec_placement. exact H. Qed.

(* =========================================================================
   The demo composition, for R-05-165's uninhabited-domain mode and for the
   refutation witnesses. Every figure below is an arbitrary witness value
   and carries no composition claim (gap h).
   ========================================================================= *)

Definition demo : Machine := {|
  record_granules := 4;
  block_count := 6;
  fanout := 3;
  height := 2;
  node_granules := 4;
  fresh_block := fun i => Nat.add 10 i;
  root_block := 0;
  mac := fun c => S c
|}.

Example the_demo_machine_declares :
  record_granules demo = 4
  /\ block_count demo = 6
  /\ fanout demo = 3
  /\ height demo = 2
  /\ node_granules demo = 4
  /\ root_block demo = 0
  /\ fresh_block demo 0 = 10
  /\ fresh_block demo 1 = 11
  /\ mac demo 2 = 3 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))))))).

(* -------------------------------------------------------------------------
   The journal: six records over three transactions, one of which never
   commits, and two committed records writing one block so that the order is
   load-bearing rather than decorative.
   ------------------------------------------------------------------------- *)

Definition rec_of (t b v : nat) (cl : bool) : Rec :=
  {| rec_txn := t; rec_block := b; rec_value := v; rec_closes := cl;
     rec_len := record_granules demo; rec_landed := record_granules demo |}.

Definition demo_journal : list Rec :=
  cons (rec_of 1 1 11 false)
  (cons (rec_of 1 2 12 true)
  (cons (rec_of 2 3 13 false)
  (cons (rec_of 2 1 21 false)
  (cons (rec_of 2 1 22 true)
  (cons (rec_of 3 4 15 false) nil))))).

Definition demo_store : Store := fun b => b.

Definition store_view (rc : Recovery) (j : list Rec) : list nat :=
  map_over (rc j demo_store) (upto (block_count demo)).

Example the_journal_is_six_records_over_three_transactions :
  count_of demo_journal = 6
  /\ commits demo_journal 1 = true
  /\ commits demo_journal 2 = true
  /\ commits demo_journal 3 = false
  /\ all_of intact demo_journal = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example the_store_before_the_crash :
  store_view (fun _ s => s) demo_journal = cons 0 (cons 1 (cons 2 (cons 3
    (cons 4 (cons 5 nil))))) := eq_refl.

(* The recovered store, computed rather than described: the committed
   transactions' last writes stand and the open transaction's do not. *)
Example the_recovered_store :
  store_view spec_recover demo_journal
  = cons 0 (cons 22 (cons 12 (cons 13 (cons 4 (cons 5 nil))))) := eq_refl.

Example the_open_transaction_leaves_no_trace :
  touched demo_journal 4 = false /\ touched demo_journal 1 = true
  /\ spec_recover demo_journal demo_store 4 = 4 := conj eq_refl (conj eq_refl eq_refl).

(* -------------------------------------------------------------------------
   The crash-point family: recovery from every prefix, decided as one
   conversion over the cuts and again by the theorem that quantifies over
   the cut rather than enumerating it.
   ------------------------------------------------------------------------- *)

Example there_are_seven_crash_points :
  count_of (cuts demo_journal) = 7 := eq_refl.

Example the_store_at_every_crash_point :
  map_over (store_view spec_recover) (cuts demo_journal)
  = cons (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 nil))))))
    (cons (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 nil))))))
    (cons (cons 0 (cons 11 (cons 12 (cons 3 (cons 4 (cons 5 nil))))))
    (cons (cons 0 (cons 11 (cons 12 (cons 3 (cons 4 (cons 5 nil))))))
    (cons (cons 0 (cons 11 (cons 12 (cons 3 (cons 4 (cons 5 nil))))))
    (cons (cons 0 (cons 22 (cons 12 (cons 13 (cons 4 (cons 5 nil))))))
    (cons (cons 0 (cons 22 (cons 12 (cons 13 (cons 4 (cons 5 nil)))))) nil))))))
  := eq_refl.

(* S5 read at the demo: one conversion over the whole family. The theorem
   above already quantifies over the cut, so this is the same content
   computed rather than the family's only statement. *)
Example every_crash_point_recovers_honestly :
  all_of (honest_at spec_recover demo_store (block_count demo))
         (cuts demo_journal) = true := eq_refl.

(* And the family bites: the crash points are not all the same store, so
   the check above is a property of recovery rather than of a journal
   nothing happens in. *)
Example the_crash_points_are_not_all_alike :
  agrees_on (block_count demo) demo_store spec_recover spec_recover
            (take 2 demo_journal) (take 5 demo_journal) = false := eq_refl.

(* -------------------------------------------------------------------------
   The torn-write family, at every record and every granule below the
   record's declared length (gap a).
   ------------------------------------------------------------------------- *)

Definition torn_agrees (j : list Rec) (k g : nat) : bool :=
  agrees_on (block_count demo) demo_store spec_recover spec_recover
            (tear_at k g j) (take k j).

Definition torn_writes_at (j : list Rec) (k : nat) : bool :=
  all_of (fun g => torn_agrees j k g) (upto (record_granules demo)).

Example the_torn_family_is_twenty_four :
  count_of (concat_of (map_over (fun k => map_over (fun g => pair k g)
                                  (upto (record_granules demo)))
                       (upto (count_of demo_journal)))) = 24 := eq_refl.

(* S15 (R-10-001a, reading 2): a torn record is a cut and never a
   corruption, at every record and every granule. One conversion. *)
Example every_torn_write_recovers_as_the_cut_before_it :
  all_of (torn_writes_at demo_journal) (upto (count_of demo_journal)) = true
  := eq_refl.

(* S15a: the same twenty-four members as a quantifier over the two indices.
   It adds no generality over the conversion above and is not claimed to:
   the proof destructs the two indices into exactly the six and four cases
   the enumeration walks. What it does add is a *shape* a reader can hold
   against the family's own size, so a family that stopped covering its
   declared range is a failed `discriminate` rather than a shorter list.
   The generality on this side of the file lives in
   `the_specification_recovers_honestly_from_every_journal`, which quantifies
   over the journal itself. *)
Theorem no_torn_record_is_replayed :
  forall k g : nat,
    Nat.ltb k (count_of demo_journal) = true ->
    Nat.ltb g (record_granules demo) = true ->
    torn_agrees demo_journal k g = true.
Proof.
  intros k g. destruct k as [ | [ | [ | [ | [ | [ | k ] ] ] ] ] ];
    destruct g as [ | [ | [ | [ | g ] ] ] ];
    intros Hk Hg; first [ reflexivity | discriminate Hk | discriminate Hg ].
Qed.

(* And a torn record is observable rather than absorbed: tearing the record
   that closes the second transaction loses that transaction's writes. *)
Example a_torn_commit_record_loses_its_transaction :
  store_view spec_recover (tear_at 4 0 demo_journal)
  = cons 0 (cons 11 (cons 12 (cons 3 (cons 4 (cons 5 nil))))) := eq_refl.

(* -------------------------------------------------------------------------
   Gap e at the demo: the two arms, and the store each reaches from the same
   crashed journal. Both satisfy every obligation above; what separates them
   is the clause no entry states, so the disagreement below is a measurement
   of the gap and not a verdict on either arm.
   ------------------------------------------------------------------------- *)

Theorem the_two_recovery_readings_disagree :
  agrees_on (block_count demo) demo_store spec_recover sieve_recover
            (tear_at 2 0 demo_journal) (tear_at 2 0 demo_journal) = false.
Proof. reflexivity. Qed.

(* And the disagreement read as two stores rather than as a boolean, so what
   the choice costs is a figure: the skipping arm replays a record the crash
   never durably ordered, and the stopping arm loses one it did. *)
Example what_each_recovery_reading_reaches :
  store_view spec_recover (tear_at 2 0 demo_journal)
  = cons 0 (cons 11 (cons 12 (cons 3 (cons 4 (cons 5 nil)))))
  /\ map_over (sieve_recover (tear_at 2 0 demo_journal) demo_store)
       (upto (block_count demo))
  = cons 0 (cons 22 (cons 12 (cons 3 (cons 4 (cons 5 nil)))))
  /\ scan (tear_at 2 0 demo_journal) = take 2 demo_journal
  /\ count_of (sieve (tear_at 2 0 demo_journal)) = 5 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   The three recoveries the obligations exclude, refuted at the demo journal.
   Each is a recovery no discipline's own replay produces, so what refuses it
   is the named defect and not a different cut.
   ------------------------------------------------------------------------- *)

(* R-16-005 read from the other side: it gains a value at a block the
   journal never named. *)
Theorem the_zeroing_recovery_is_refuted :
  ~ LeavesUntouchedBlocks scan zeroing_recover.
Proof.
  intros H. specialize (H demo_journal demo_store 4 eq_refl). discriminate H.
Qed.

Example what_the_zeroing_recovery_reaches :
  map_over (zeroing_recover demo_journal demo_store) (upto (block_count demo))
  = cons 0 (cons 22 (cons 12 (cons 13 (cons 0 (cons 0 nil))))) := eq_refl.

(* R-16-005's committed half, refuted: it loses everything a closed
   transaction wrote. *)
Theorem the_stale_recovery_is_refuted :
  ~ LandsEveryCommittedWrite scan stale_recover.
Proof.
  intros H. specialize (H demo_journal demo_store 1 22 eq_refl). discriminate H.
Qed.

Example what_the_stale_recovery_reaches :
  map_over (stale_recover demo_journal demo_store) (upto (block_count demo))
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 nil))))) := eq_refl.

(* And the one that reads past its own discipline's cut. It breaks two
   obligations rather than one, and that is not an accident: a recovery
   computed from the journal that reads past the cut both admits work the
   cut refused and writes a block the cut never named, so the two failures
   are one act. What it keeps is the idempotence, which is why it is
   exhibited here rather than reported as a fifth defect. *)
Theorem the_unscanned_recovery_is_refuted :
  ~ ReadsOnlyWhatTheDisciplineAdmits scan unscanned_recover
  /\ ~ LeavesUntouchedBlocks scan unscanned_recover.
Proof.
  split.
  - intros H. specialize (H past_the_cut_journal probe_store 1). discriminate H.
  - intros H. specialize (H past_the_cut_journal probe_store 0 eq_refl).
    discriminate H.
Qed.

Example what_the_unscanned_recovery_reaches :
  map_over (unscanned_recover past_the_cut_journal probe_store) (upto 3)
  = cons 0 (cons 99 (cons 3 nil))
  /\ map_over (unscanned_recover (scan past_the_cut_journal) probe_store) (upto 3)
  = cons 1 (cons 11 (cons 3 nil))
  /\ map_over (spec_recover past_the_cut_journal probe_store) (upto 3)
  = cons 1 (cons 11 (cons 3 nil))
  /\ touched past_the_cut_journal 0 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   The replay family: a prefix replayed twice, a suffix replayed, and one
   record moved out of order.
   ------------------------------------------------------------------------- *)

Definition replay_agrees (j : list Rec) (j2 : list Rec) : bool :=
  agrees_on (block_count demo) demo_store spec_recover spec_recover j2 j.

(* S16 read at the demo: the general theorems above quantify over the
   journal, the store and the cut, so these two conversions are the same
   content computed at one journal rather than the only form it is stated
   in. Both derive from the general theorem, so a change to either side
   moves one of the two. *)
Example every_replayed_prefix_reaches_the_same_store :
  all_of (fun i => replay_agrees demo_journal (replay_prefix i demo_journal))
         (upto (S (count_of demo_journal))) = true := eq_refl.

Example every_replayed_suffix_reaches_the_same_store :
  all_of (fun i => replay_agrees demo_journal (replay_suffix i demo_journal))
         (upto (S (count_of demo_journal))) = true := eq_refl.

Theorem no_replayed_prefix_moves_the_store :
  forall i b : nat, Nat.ltb b (block_count demo) = true ->
    spec_recover (replay_prefix i demo_journal) demo_store b
      = spec_recover demo_journal demo_store b.
Proof.
  intros i b _.
  exact (replaying_a_prefix_reaches_the_same_store demo_journal demo_store i b
           eq_refl).
Qed.

Theorem no_replayed_suffix_moves_the_store :
  forall i b : nat, Nat.ltb b (block_count demo) = true ->
    spec_recover (replay_suffix i demo_journal) demo_store b
      = spec_recover demo_journal demo_store b.
Proof.
  intros i b _.
  exact (replaying_a_suffix_reaches_the_same_store demo_journal demo_store i b
           eq_refl).
Qed.

(* S16a: and a record moved out of order is not absorbed. The map is
   positional rather than a conjunction, so which transposition is
   observable is computed rather than claimed: it is the one that moves the
   later of the two committed records writing one block. *)
Example which_transpositions_are_observable :
  map_over (fun n => replay_agrees demo_journal (swap_at n demo_journal))
           (upto (before_last (count_of demo_journal)))
  = cons true (cons true (cons true (cons false (cons true nil)))) := eq_refl.

(* The twin: every transposition still recovers honestly, so what a
   reordering breaks is the content and never the atomicity. Two
   obligations, one construction separating them. *)
Example every_transposition_still_recovers_honestly :
  all_of (fun n => honest_at spec_recover demo_store (block_count demo)
                     (swap_at n demo_journal))
         (upto (before_last (count_of demo_journal))) = true := eq_refl.

(* -------------------------------------------------------------------------
   The medium, the commit, and the crash points of a copy-on-write write.
   ------------------------------------------------------------------------- *)

Definition leaf_node : Node :=
  {| node_keys := nil; node_kids := nil; node_tags := nil |}.

Definition node_over (kids tags : list nat) : Node :=
  {| node_keys := nil; node_kids := kids; node_tags := tags |}.

(* An interior node with its separator keys beside the children it names, so
   that the occupancy obligation reads a node the demo tree actually holds
   rather than one written for it. *)
Definition node_with (keys kids tags : list nat) : Node :=
  {| node_keys := keys; node_kids := kids; node_tags := tags |}.

Definition blank_block : Blk :=
  {| blk_node := leaf_node; blk_len := node_granules demo; blk_landed := 0;
     blk_content := 0; blk_tag := 0 |}.

Definition demo_medium : Medium := fun b =>
  if Nat.eqb b 0 then whole_of demo (node_with (cons 5 nil) (cons 1 (cons 2 nil))
                                       (cons 2 (cons 3 nil))) 0
  else if Nat.eqb b 1 then whole_of demo (leaf_holding (cons 1 nil)) 1
  else if Nat.eqb b 2 then whole_of demo (leaf_holding (cons 7 nil)) 2
  else if Nat.eqb b 3 then whole_of demo (node_with (cons 6 nil) (cons 4 nil)
                                            (cons 5 nil)) 3
  else if Nat.eqb b 4 then whole_of demo (leaf_holding (cons 8 nil)) 4
  else blank_block.

Example the_medium_holds_two_roots_and_a_blank_pool :
  reach_set demo demo_medium 0 = cons 0 (cons 1 (cons 2 nil))
  /\ reach_set demo demo_medium 3 = cons 3 (cons 4 nil)
  /\ covered demo demo_medium 0 = true
  /\ covered demo demo_medium 3 = true
  /\ blank (demo_medium 10) = true
  /\ blank (demo_medium 11) = true
  /\ blank (demo_medium 1) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

Example a_block_outside_a_root_is_not_reached :
  reaches demo demo_medium 0 4 = false /\ reaches demo demo_medium 3 4 = true
  /\ reaches demo demo_medium 0 1 = true := conj eq_refl (conj eq_refl eq_refl).

(* The commit: a new leaf at the allocator's first block and a new root at
   its second, sharing the unmodified sibling (reading 7). *)
Definition new_leaf : Write :=
  {| w_block := fresh_block demo 0; w_node := leaf_node |}.

Definition new_root : Write :=
  {| w_block := fresh_block demo 1;
     w_node := node_over (cons (fresh_block demo 0) (cons 2 nil))
                         (cons 11 (cons 3 nil)) |}.

Definition demo_commit : Commit := {|
  cm_plan := cons new_leaf (cons new_root nil);
  cm_new_root := fresh_block demo 1;
  cm_old_root := root_block demo;
  cm_retained := cons 3 nil
|}.

Example the_commit_is_admissible :
  root_is_last demo_commit = true
  /\ allocates_blank demo_medium demo_commit = true
  /\ spares_the_retained demo demo_medium demo_commit = true
  /\ kids_resolve demo demo_medium demo_commit = true
  /\ admissible demo demo_medium demo_commit = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example the_commit_shares_the_sibling_it_did_not_rewrite :
  in_plan (cm_plan demo_commit) 2 = false
  /\ in_plan (cm_plan demo_commit) 10 = true
  /\ covered demo demo_medium 2 = true := conj eq_refl (conj eq_refl eq_refl).

(* -------------------------------------------------------------------------
   The crash-point family of a copy-on-write commit: every crash index and
   every torn granule, decided as one conversion and again by the two
   theorems that quantify over the index.
   ------------------------------------------------------------------------- *)

Definition cow_row (md : Medium) (c : Commit) (sq : Sequencer) (i : nat) : bool :=
  all_of (fun g => covered demo (land_torn demo i g (cm_plan c) md) (sq c i))
         (upto (node_granules demo)).

Example every_crash_point_of_the_commit_covers_its_root :
  all_of (cow_row demo_medium demo_commit spec_sequencer)
         (upto (S (S (count_of (cm_plan demo_commit))))) = true := eq_refl.

(* S17 (R-10-036, R-16-003, readings 5 and 7): the demo commit is one
   instance of the general theorem and not a second proof of it. The two
   hypotheses are conversions at this composition: the previous root covers
   whole nodes, and the plan is admissible. *)
Theorem the_demo_commit_is_crash_consistent :
  CrashConsistent demo demo_medium demo_commit spec_sequencer.
Proof.
  exact (an_admissible_commit_is_crash_consistent demo demo_medium demo_commit
           eq_refl eq_refl).
Qed.

Theorem the_demo_commit_leaves_the_retained_root_unmoved :
  RetainedRootsUnmoved demo demo_medium demo_commit.
Proof.
  exact (the_specification_leaves_every_retained_root_unmoved demo demo_medium
           demo_commit eq_refl).
Qed.

(* =========================================================================
   The refuting constructions over the copy-on-write commit. Each is an
   alternative the register's own sentence excludes, and each is shown to
   satisfy the obligations it does not break, so what refuses it is the
   named defect rather than the shape of the construction.
   ========================================================================= *)

(* --- 1. The updater that rewrites a node in place. R-10-010's refcounted
       copy-on-write extent sharing read onto the allocator (reading 5) is
       what excludes it: it writes the block the previous root still
       reaches, so a crash in the middle of that write leaves the *previous*
       root over a half-written node. ------------------------------------ *)

Definition inplace_write : Write := {| w_block := 1; w_node := leaf_node |}.

Definition inplace_root : Write :=
  {| w_block := fresh_block demo 1;
     w_node := node_over (cons 1 (cons 2 nil)) (cons 2 (cons 3 nil)) |}.

Definition inplace_commit : Commit := {|
  cm_plan := cons inplace_write (cons inplace_root nil);
  cm_new_root := fresh_block demo 1;
  cm_old_root := root_block demo;
  cm_retained := cons 3 nil
|}.

Theorem the_inplace_updater_is_refuted :
  ~ CrashConsistent demo demo_medium inplace_commit spec_sequencer.
Proof. intros H. specialize (H 0 0). discriminate H. Qed.

Example the_inplace_updater_writes_a_block_that_is_not_blank :
  allocates_blank demo_medium inplace_commit = false
  /\ blank (demo_medium 1) = false := conj eq_refl eq_refl.

(* The twin: it publishes its root last, resolves every child, spares every
   retained root, and leaves them unmoved. What refuses it is the block it
   chose and nothing else about it. *)
Theorem the_inplace_updater_keeps_every_other_obligation :
  root_is_last inplace_commit = true
  /\ kids_resolve demo demo_medium inplace_commit = true
  /\ spares_the_retained demo demo_medium inplace_commit = true
  /\ RetainedRootsUnmoved demo demo_medium inplace_commit.
Proof.
  split; [ reflexivity | ]. split; [ reflexivity | ]. split; [ reflexivity | ].
  exact (the_specification_leaves_every_retained_root_unmoved demo demo_medium
           inplace_commit eq_refl).
Qed.

Example which_crash_points_the_inplace_updater_fails :
  map_over (cow_row demo_medium inplace_commit spec_sequencer)
           (upto (S (S (count_of (cm_plan inplace_commit)))))
  = cons false (cons true (cons true (cons true nil))) := eq_refl.

(* --- 2. The sequencer that publishes the root before its children have
       landed. The plan is the specification's own, so what is refuted here
       is the publish and not the write order. --------------------------- *)

Definition eager_sequencer : Sequencer :=
  fun c i => if Nat.ltb 0 i then cm_new_root c else cm_old_root c.

Theorem the_eager_publisher_is_refuted :
  ~ CrashConsistent demo demo_medium demo_commit eager_sequencer.
Proof. intros H. specialize (H 1 0). discriminate H. Qed.

(* The twin: it agrees with the specification's sequencer everywhere except
   inside the plan, so what refuses it is the window it opens and not a
   different root. *)
Example the_eager_publisher_agrees_outside_the_plan :
  eager_sequencer demo_commit 0 = spec_sequencer demo_commit 0
  /\ eager_sequencer demo_commit 2 = spec_sequencer demo_commit 2
  /\ eager_sequencer demo_commit 1 = cm_new_root demo_commit
  /\ spec_sequencer demo_commit 1 = cm_old_root demo_commit :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Example which_crash_points_the_eager_publisher_fails :
  map_over (cow_row demo_medium demo_commit eager_sequencer)
           (upto (S (S (count_of (cm_plan demo_commit)))))
  = cons true (cons false (cons true (cons true nil))) := eq_refl.

(* S18: and the publish is what carries the property, which is why the
   specification's sequencer names the new root only past the whole plan. *)
Theorem the_published_root_is_named_only_past_the_whole_plan :
  forall (c : Commit) (i : nat),
    Nat.leb (count_of (cm_plan c)) i = false -> spec_sequencer c i = cm_old_root c.
Proof. intros c i H. unfold spec_sequencer. rewrite H. reflexivity. Qed.

(* --- 3. The plan that publishes the root first. It breaks `root_is_last`
       and, under the specification's own sequencer, it is still crash
       consistent: the two are one discipline stated twice and either alone
       suffices, which is a separation worth stating rather than a
       redundancy worth deleting. ---------------------------------------- *)

Definition root_first_commit : Commit := {|
  cm_plan := cons new_root (cons new_leaf nil);
  cm_new_root := fresh_block demo 1;
  cm_old_root := root_block demo;
  cm_retained := cons 3 nil
|}.

Theorem the_root_first_plan_is_refused_by_the_conjunct :
  root_is_last root_first_commit = false
  /\ admissible demo demo_medium root_first_commit = false.
Proof. split; reflexivity. Qed.

Theorem the_root_first_plan_is_still_crash_consistent_under_the_specification :
  CrashConsistent demo demo_medium root_first_commit spec_sequencer.
Proof. intros i g. destruct i as [ | [ | k ] ]; reflexivity. Qed.

Example the_root_first_plan_keeps_every_other_conjunct :
  allocates_blank demo_medium root_first_commit = true
  /\ spares_the_retained demo demo_medium root_first_commit = true
  /\ kids_resolve demo demo_medium root_first_commit = true :=
  conj eq_refl (conj eq_refl eq_refl).

(* --- 4. The allocator that reuses a block only a *retained* snapshot root
       still reaches. It spares everything the current root reaches, so it
       is crash consistent; and it destroys the snapshot, which is the
       obligation R-10-010 owns (reading 8, gap f).

       It breaks two of the four conjuncts and not one, and that is forced
       rather than careless: a block a covered root reaches is complete, so
       it is not blank, so any commit reusing a live retained block also
       fails `allocates_blank`. `a_block_a_covered_root_reaches_is_never_blank`
       states that, so the pairing is a theorem here and not an accident of
       this witness. --------------------------------------------------- *)

Theorem a_block_a_covered_root_reaches_is_never_blank :
  forall (m : Machine) (md : Medium) (r x : nat),
    covered m md r = true -> reaches m md r x = true -> blank (md x) = false.
Proof.
  intros m md r x Hc Hr.
  destruct (blank (md x)) eqn:E; [ | reflexivity ].
  rewrite (a_blank_block_is_out_of_every_cover m md r x Hc E) in Hr.
  discriminate Hr.
Qed.

Definition reuse_write : Write := {| w_block := 4; w_node := leaf_node |}.

Definition reuse_root : Write :=
  {| w_block := fresh_block demo 1;
     w_node := node_over (cons 4 (cons 2 nil)) (cons 5 (cons 3 nil)) |}.

Definition retained_reuse_commit : Commit := {|
  cm_plan := cons reuse_write (cons reuse_root nil);
  cm_new_root := fresh_block demo 1;
  cm_old_root := root_block demo;
  cm_retained := cons 3 nil
|}.

Theorem the_retained_reuse_moves_a_retained_block :
  ~ RetainedRootsUnmoved demo demo_medium retained_reuse_commit.
Proof.
  intros H.
  assert (Hx : land_torn demo 0 0 (cm_plan retained_reuse_commit) demo_medium 4
               = demo_medium 4) by exact (H 0 0 4 eq_refl).
  assert (Hb : blk_landed (land_torn demo 0 0 (cm_plan retained_reuse_commit)
                             demo_medium 4) = blk_landed (demo_medium 4))
    by (rewrite Hx; reflexivity).
  discriminate Hb.
Qed.

(* The twin, and the separation: it is crash consistent under the
   specification's sequencer at every crash point and every torn granule,
   so the two obligations are not one obligation stated twice. *)
Theorem the_retained_reuse_is_crash_consistent_all_the_same :
  CrashConsistent demo demo_medium retained_reuse_commit spec_sequencer.
Proof. intros i g. destruct i as [ | [ | k ] ]; reflexivity. Qed.

Example the_retained_reuse_fails_the_two_conjuncts_a_live_block_costs :
  root_is_last retained_reuse_commit = true
  /\ kids_resolve demo demo_medium retained_reuse_commit = true
  /\ spares_the_retained demo demo_medium retained_reuse_commit = false
  /\ allocates_blank demo_medium retained_reuse_commit = false
  /\ blank (demo_medium 4) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example the_retained_root_reaches_the_reused_block :
  reaches demo demo_medium 3 4 = true /\ reaches demo demo_medium 0 4 = false :=
  conj eq_refl eq_refl.

(* =========================================================================
   The refuting constructions over the tag placement (R-10-022a).
   ========================================================================= *)

Theorem the_beside_placement_opens_a_misdirected_read :
  ~ RefusesAMisdirectedRead demo (beside_placement demo).
Proof.
  intros H. specialize (H demo_medium (blk_node (demo_medium 0)) 0 2 eq_refl).
  discriminate H.
Qed.

(* The same construction against the obligation that is not the
   specification's own body: one medium differing from the demo's in what
   block 1 stores *beside* its content, and the beside-placement answers
   differently at a block whose content did not move. That is R-10-022a's
   clause failing, rather than a check that happens to return false. *)
Definition retag (bk : Blk) (t : nat) : Blk :=
  {| blk_node := blk_node bk; blk_len := blk_len bk; blk_landed := blk_landed bk;
     blk_content := blk_content bk; blk_tag := t |}.

Definition retagged_medium : Medium :=
  place demo_medium 1 (retag (demo_medium 1) 9).

Example the_retagged_medium_moves_only_the_stored_tag :
  blk_content (retagged_medium 1) = blk_content (demo_medium 1)
  /\ blk_tag (retagged_medium 1) = 9
  /\ blk_tag (demo_medium 1) = 2
  /\ blk_node (retagged_medium 1) = blk_node (demo_medium 1)
  /\ blk_landed (retagged_medium 1) = blk_landed (demo_medium 1) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Theorem the_beside_placement_reads_the_block_s_own_tag :
  ~ ReadsTheReferrersTag (beside_placement demo).
Proof.
  intros H.
  specialize (H demo_medium retagged_medium (blk_node (demo_medium 0)) 0 1 eq_refl).
  discriminate H.
Qed.

(* The twin: the specification's placement answers the same at both media,
   because what it compares against never moved. *)
Example the_specification_placement_is_unmoved_by_the_retag :
  spec_placement demo demo_medium (blk_node (demo_medium 0)) 0 1
    = spec_placement demo retagged_medium (blk_node (demo_medium 0)) 0 1
  /\ spec_placement demo retagged_medium (blk_node (demo_medium 0)) 0 1 = true
  /\ beside_placement demo demo_medium (blk_node (demo_medium 0)) 0 1 = true
  /\ beside_placement demo retagged_medium (blk_node (demo_medium 0)) 0 1 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The twin: it opens the block that was meant, so what refuses it is where
   the tag was stored and not a check that fails. *)
Example the_beside_placement_opens_the_intended_read :
  beside_placement demo demo_medium (blk_node (demo_medium 0)) 0 1 = true
  /\ spec_placement demo demo_medium (blk_node (demo_medium 0)) 0 1 = true
  /\ spec_placement demo demo_medium (blk_node (demo_medium 0)) 0 2 = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* And a child the referring node holds no tag for never opens, which is the
   fallback in `expects` doing the one thing it is there to do. *)
Example a_child_with_no_tag_never_opens :
  spec_placement demo demo_medium leaf_node 0 1 = false
  /\ expects leaf_node 0 = 0
  /\ expects (blk_node (demo_medium 0)) 1 = 3 :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   The key-order family (R-10-003, R-10-005 read at the layer below it).
   ========================================================================= *)

Definition nat_keys : KeyAlgebra := {|
  Key := nat;
  key_leb := Nat.leb;
  key_eqb := Nat.eqb;
  key_eqb_refl := nat_eqb_refl;
  key_eqb_true := nat_eqb_true;
  key_leb_total := nat_leb_total;
  key_leb_trans := nat_leb_trans;
  key_leb_antisym := nat_leb_antisym
|}.

Fixpoint pairs_eqb (a b : list (prod nat nat)) : bool :=
  match a, b with
  | nil, nil => true
  | cons x r, cons y s =>
      andb (andb (Nat.eqb (fst x) (fst y)) (Nat.eqb (snd x) (snd y)))
           (pairs_eqb r s)
  | _, _ => false
  end.

Definition demo_index (l : list (prod nat nat)) : list (prod nat nat) :=
  ins_all nat_keys l nil.

Definition demo_entries : list (prod nat nat) :=
  cons (pair 3 30) (cons (pair 1 10) (cons (pair 4 40)
  (cons (pair 5 50) (cons (pair 2 20) nil)))).

Example the_index_is_the_sorted_keyspace :
  demo_index demo_entries
  = cons (pair 1 10) (cons (pair 2 20) (cons (pair 3 30)
    (cons (pair 4 40) (cons (pair 5 50) nil))))
  /\ sorted nat_keys (demo_index demo_entries) = true
  /\ sorted nat_keys demo_entries = false :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_index_answers_the_keys_it_was_given :
  look nat_keys 3 (demo_index demo_entries) = Some 30
  /\ look nat_keys 9 (demo_index demo_entries) = None
  /\ pairs_eqb (demo_index demo_entries) (demo_index demo_entries) = true
  /\ pairs_eqb (demo_index demo_entries) nil = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The four generators over an arbitrary key list, which is where generated
   inputs beat authored cases: a key order is exactly what a person
   enumerates badly. *)
Definition key_transpositions (l : list (prod nat nat)) : list (list (prod nat nat)) :=
  map_over (fun n => swap_at n l) (upto (before_last (count_of l))).

Definition key_deletions (l : list (prod nat nat)) : list (list (prod nat nat)) :=
  map_over (fun n => drop_at n l) (upto (count_of l)).

Definition key_suffixes (l : list (prod nat nat)) : list (list (prod nat nat)) :=
  map_over (fun n => suffix_at (S n) l) (upto (count_of l)).

Definition key_duplications (l : list (prod nat nat)) : list (list (prod nat nat)) :=
  map_over (fun n => insert_at n (pair 1 99) l) (upto (S (count_of l))).

Definition key_orders (l : list (prod nat nat)) : list (list (prod nat nat)) :=
  app (key_transpositions l)
      (app (key_deletions l) (app (key_suffixes l) (key_duplications l))).

Example the_key_order_family_is_twenty :
  count_of (key_orders demo_entries) = 20 := eq_refl.

Definition builds_the_same_index (l : list (prod nat nat)) : bool :=
  pairs_eqb (demo_index l) (demo_index demo_entries).

(* S19 (R-10-003): every permutation of a distinct-key list builds one
   index, so the index is a function of the key set and not of the order it
   arrived in. One conversion over the family. *)
Example every_permutation_builds_the_same_index :
  all_of builds_the_same_index (key_transpositions demo_entries) = true := eq_refl.

(* S19a: the same content as a quantifier over the transposition index. It
   adds no generality over the conversion above and is not claimed to: the
   proof destructs the index into exactly the four cases the family walks,
   and the *general* statement is
   `transposing_two_distinct_writes_answers_the_same_everywhere`, which
   quantifies over the key algebra, the index and the query. What is kept
   here is a form a reader holds against the family's declared range. *)
Theorem no_adjacent_transposition_moves_the_index :
  forall n : nat, Nat.ltb n (before_last (count_of demo_entries)) = true ->
    builds_the_same_index (swap_at n demo_entries) = true.
Proof.
  intros n. destruct n as [ | [ | [ | [ | n ] ] ] ];
    intros H; first [ reflexivity | discriminate H ].
Qed.

(* And the general theorem read at this instance, so the two are visibly the
   same property: writing two distinct keys in either order answers alike at
   every key of the demo index. *)
Example the_general_transposition_theorem_at_the_demo_keys :
  look nat_keys 3 (ins nat_keys 1 10 (ins nat_keys 3 30 (demo_index nil)))
    = look nat_keys 3 (ins nat_keys 3 30 (ins nat_keys 1 10 (demo_index nil)))
  /\ look nat_keys 1 (ins nat_keys 1 10 (ins nat_keys 3 30 (demo_index nil)))
    = look nat_keys 1 (ins nat_keys 3 30 (ins nat_keys 1 10 (demo_index nil)))
  /\ look nat_keys 9 (ins nat_keys 1 10 (ins nat_keys 3 30 (demo_index nil)))
    = look nat_keys 9 (ins nat_keys 3 30 (ins nat_keys 1 10 (demo_index nil))) :=
  conj eq_refl (conj eq_refl eq_refl).

(* The family bites: a deletion and a proper suffix each build a different
   index, so the check above is a property of the insertion and not of a
   comparison nothing can fail. *)
Example every_deletion_builds_a_different_index :
  all_of (fun l => negb (builds_the_same_index l)) (key_deletions demo_entries)
  = true := eq_refl.

Example every_proper_suffix_builds_a_different_index :
  all_of (fun l => negb (builds_the_same_index l)) (key_suffixes demo_entries)
  = true := eq_refl.

(* S19b: the duplicate arm is positional rather than uniform, and the
   position is computed rather than claimed: a duplicate inserted before the
   original loses and one inserted after it wins, which is the last-writer
   rule of an ordered insertion made visible. *)
Example the_duplicate_wins_exactly_where_it_arrives_late :
  map_over builds_the_same_index (key_duplications demo_entries)
  = cons true (cons true (cons false (cons false (cons false
    (cons false nil))))) := eq_refl.

Example the_duplicate_that_wins_is_the_later_one :
  look nat_keys 1 (demo_index (insert_at 0 (pair 1 99) demo_entries)) = Some 10
  /\ look nat_keys 1 (demo_index (insert_at 5 (pair 1 99) demo_entries)) = Some 99 :=
  conj eq_refl eq_refl.

(* S19c: and every member of every arm builds a sorted index, which is S11
   read at twenty concrete orders including the empty and singleton cases
   gap g leaves open. *)
Example every_key_order_builds_a_sorted_index :
  all_of (fun l => sorted nat_keys (demo_index l)) (key_orders demo_entries)
  = true := eq_refl.

Example the_empty_and_singleton_cases_are_admitted :
  demo_index nil = nil
  /\ sorted nat_keys (demo_index nil) = true
  /\ sorted nat_keys (demo_index (cons (pair 7 70) nil)) = true
  /\ demo_index (cons (pair 7 70) nil) = cons (pair 7 70) nil :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   The boundary keys at the node fanout (gap b).
   ------------------------------------------------------------------------- *)

Definition boundary_keys (n : nat) : list (prod nat nat) :=
  map_over (fun k => pair k k) (upto n).

Example the_leaves_at_the_fanout_boundary :
  map_over (fun n => count_of (leaves (fanout demo) (demo_index (boundary_keys n))))
           (upto 6)
  = cons 0 (cons 1 (cons 1 (cons 1 (cons 2 (cons 2 nil))))) := eq_refl.

Example no_leaf_at_any_boundary_overflows_the_fanout :
  all_of (fun n => all_of (fun c => Nat.leb (count_of c) (fanout demo))
                          (leaves (fanout demo) (demo_index (boundary_keys n))))
         (upto 6) = true := eq_refl.

(* The chunking that overflows the declared fanout, refuted at the boundary
   the fanout names. The twin: it is a chunking, so it partitions the same
   index and differs only in where it cuts. *)
Definition overflowing_leaves {A : Type} (n : nat) (l : list A) : list (list A) :=
  chunks (count_of l) (S n) l.

Theorem the_overflowing_chunking_is_refuted :
  all_of (fun c => Nat.leb (count_of c) (fanout demo))
         (overflowing_leaves (fanout demo) (demo_index (boundary_keys 4)))
  = false.
Proof. reflexivity. Qed.

Example the_overflowing_chunking_still_partitions_the_index :
  concat_of (overflowing_leaves (fanout demo) (demo_index (boundary_keys 4)))
  = demo_index (boundary_keys 4)
  /\ concat_of (leaves (fanout demo) (demo_index (boundary_keys 4)))
  = demo_index (boundary_keys 4) := conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   The occupancy obligation read at the nodes this file models (reading 12):
   the demo tree's own nodes, the nodes the commit publishes, a node builder
   refuted at the boundary, and two nodes failing one conjunct apiece so
   neither conjunct of `node_fits` is dead.
   ------------------------------------------------------------------------- *)

Example every_node_of_the_demo_tree_fits_the_declared_fanout :
  every_reached_node_fits demo demo_medium 0 = true
  /\ every_reached_node_fits demo demo_medium 3 = true
  /\ every_reached_node_fits demo (landed demo demo_commit demo_medium)
       (cm_new_root demo_commit) = true
  /\ map_over (fun x => node_fits demo (blk_node (demo_medium x)))
       (reach_set demo demo_medium 0) = cons true (cons true (cons true nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* One node too wide and one child with no tag: the two conjuncts of
   `node_fits` beside the whole node, so a conjunct that stopped deciding is
   a moved conversion rather than a silence. *)
Definition crowded_node : Node :=
  leaf_holding (cons 1 (cons 2 (cons 3 (cons 4 nil)))).

Definition untagged_node : Node :=
  node_with nil (cons 1 (cons 2 nil)) (cons 2 nil).

Example the_two_conjuncts_of_a_node_are_two :
  node_keys crowded_node = cons 1 (cons 2 (cons 3 (cons 4 nil)))
  /\ node_kids untagged_node = cons 1 (cons 2 nil)
  /\ node_tags untagged_node = cons 2 nil
  /\ node_keys untagged_node = nil
  /\ node_fits demo crowded_node = false
  /\ Nat.leb (count_of (node_keys crowded_node)) (fanout demo) = false
  /\ Nat.eqb (count_of (node_tags crowded_node))
             (count_of (node_kids crowded_node)) = true
  /\ node_fits demo untagged_node = false
  /\ Nat.leb (count_of (node_keys untagged_node)) (fanout demo) = true
  /\ Nat.eqb (count_of (node_tags untagged_node))
             (count_of (node_kids untagged_node)) = false
  /\ node_fits demo (blk_node (demo_medium 0)) = true
  /\ node_fits demo (w_node new_root) = true
  (* and a node holding exactly the declared fanout fits, which is the
     boundary the ceiling names *)
  /\ node_fits demo (leaf_holding (cons 1 (cons 2 (cons 3 nil)))) = true
  /\ node_fits demo (node_with nil (cons 1 (cons 2 (cons 3 nil)))
                       (cons 4 (cons 5 (cons 6 nil)))) = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))))))))))).

(* A medium whose tree carries a node one key too wide: it is fully landed
   and every block it reaches is complete, so what refuses it is the
   occupancy and not a torn write. *)
Definition crowded_medium : Medium :=
  place demo_medium 1 (whole_of demo crowded_node 1).

Theorem the_crowded_tree_overflows_the_fanout :
  every_reached_node_fits demo crowded_medium 0 = false
  /\ covered demo crowded_medium 0 = true
  /\ reach_set demo crowded_medium 0 = reach_set demo demo_medium 0.
Proof. split; [ reflexivity | split; reflexivity ]. Qed.

(* Which block the crowded medium replaced, read back: without this the
   overflow above is a property of the tree and not of the block it is at. *)
Example the_crowded_medium_replaces_one_block :
  blk_node (crowded_medium 1) = crowded_node
  /\ blk_content (crowded_medium 1) = 1
  /\ blk_node (crowded_medium 0) = blk_node (demo_medium 0)
  /\ blk_node (crowded_medium 2) = blk_node (demo_medium 2)
  /\ map_over (fun x => node_fits demo (blk_node (crowded_medium x)))
       (reach_set demo crowded_medium 0)
     = cons true (cons false (cons true nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* S13a: the builder that cuts one key past the declared fanout, refuted of
   the obligation and shown to partition the same keys. *)
Theorem the_overflowing_builder_is_refuted : ~ NoNodeOverflows overflowing_builder.
Proof. intros H. specialize (H demo (upto 4)). discriminate H. Qed.

Example the_overflowing_builder_still_partitions_the_keys :
  concat_of (map_over node_keys (overflowing_builder demo (upto 4))) = upto 4
  /\ concat_of (map_over node_keys (spec_builder demo (upto 4))) = upto 4
  /\ map_over (fun nd => count_of (node_keys nd)) (spec_builder demo (upto 4))
     = cons 3 (cons 1 nil)
  /\ map_over (fun nd => count_of (node_keys nd))
       (overflowing_builder demo (upto 4)) = cons 4 nil :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   R-10-004's buffered updates beside the fallback the same entry names.
   ------------------------------------------------------------------------- *)

Definition demo_buffer : Buffered nat_keys :=
  pair (cons (pair 3 33) nil) (demo_index demo_entries).

Example a_buffered_message_is_visible_before_it_is_flushed :
  blook nat_keys 3 demo_buffer = Some 33
  /\ plain_look nat_keys 3 demo_buffer = Some 30
  /\ blook nat_keys 4 demo_buffer = Some 40 :=
  conj eq_refl (conj eq_refl eq_refl).

(* The fallback is a fallback and not a defect: after the flush the two read
   alike, so what separates them is write amplification, which this file
   does not model and does not claim. *)
Example the_flush_reconciles_the_two_readers :
  map_over (fun k => blook nat_keys k (flush nat_keys demo_buffer)) (upto 6)
  = map_over (fun k => plain_look nat_keys k (flush nat_keys demo_buffer)) (upto 6)
  /\ blook nat_keys 3 (flush nat_keys demo_buffer) = Some 33 :=
  conj eq_refl eq_refl.

Example the_flushed_index_is_still_sorted :
  sorted nat_keys (snd (flush nat_keys demo_buffer)) = true := eq_refl.


(* =========================================================================
   What the seeded population found, and the statements its survivors named.

   A survivor of `run.py seed coq` is a site no statement above reaches, and
   the answer is a statement rather than a narrower population. What the
   first run named was of three kinds, and each is closed here by content
   rather than by a pin: the journal, the medium and every plan were
   *described* in prose and never *stated*, so their fields carried figures
   nothing read back; the four admission conjuncts were never exhibited
   failing one apiece, so three of them could have been disjunctions; and
   R-10-022a's tags were held by nodes no read ever presented, so the tag a
   node carries for a child decided nothing.
   ========================================================================= *)

(* --- The journal, stated field by field rather than described. R-10-002's
       transaction is a record's own `rec_txn` and R-10-036's commit is its
       `rec_closes`, so a journal whose fields nothing reads back is a
       journal whose shape no theorem below depends on. --------------- *)

Example the_journal_records_declare :
  map_over rec_txn demo_journal
    = cons 1 (cons 1 (cons 2 (cons 2 (cons 2 (cons 3 nil)))))
  /\ map_over rec_block demo_journal
    = cons 1 (cons 2 (cons 3 (cons 1 (cons 1 (cons 4 nil)))))
  /\ map_over rec_value demo_journal
    = cons 11 (cons 12 (cons 13 (cons 21 (cons 22 (cons 15 nil)))))
  /\ map_over rec_closes demo_journal
    = cons false (cons true (cons false (cons false (cons true (cons false nil)))))
  /\ map_over rec_len demo_journal
    = cons 4 (cons 4 (cons 4 (cons 4 (cons 4 (cons 4 nil))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* The open transaction is named and targeted, which is what makes
   `touched` a measurement of the recovery rather than of an empty set: a
   third transaction exists, it writes a block inside the address space, and
   no crash point admits it. *)
Example the_open_transaction_is_named_and_targeted :
  commits demo_journal 3 = false
  /\ all_of (fun p => negb (commits (scan p) 3)) (cuts demo_journal) = true
  /\ Nat.ltb 4 (block_count demo) = true := conj eq_refl (conj eq_refl eq_refl).

(* --- The medium, stated the same way. R-10-022a puts the tag in the
       referring node, so what a block holds and what its parent expects are
       two figures that must agree, and neither is readable off the other.
       ---------------------------------------------------------------- *)

Example the_medium_contents_and_tags :
  map_over (fun b => blk_content (demo_medium b)) (upto (block_count demo))
    = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 0 nil)))))
  /\ map_over (fun b => blk_tag (demo_medium b)) (upto (block_count demo))
    = cons 1 (cons 2 (cons 3 (cons 4 (cons 5 (cons 0 nil)))))
  /\ map_over (fun b => blk_landed (demo_medium b)) (upto (block_count demo))
    = cons 4 (cons 4 (cons 4 (cons 4 (cons 4 (cons 0 nil))))) :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_nodes_name_their_children_and_hold_their_tags :
  node_kids (blk_node (demo_medium 0)) = cons 1 (cons 2 nil)
  /\ node_tags (blk_node (demo_medium 0)) = cons 2 (cons 3 nil)
  /\ node_keys (blk_node (demo_medium 0)) = cons 5 nil
  /\ node_kids (blk_node (demo_medium 3)) = cons 4 nil
  /\ node_tags (blk_node (demo_medium 3)) = cons 5 nil
  /\ node_keys (blk_node (demo_medium 3)) = cons 6 nil
  /\ node_kids (blk_node (demo_medium 1)) = nil
  /\ node_keys (blk_node (demo_medium 1)) = cons 1 nil
  /\ node_keys (blk_node (demo_medium 2)) = cons 7 nil
  /\ node_keys (blk_node (demo_medium 4)) = cons 8 nil :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))))))).

(* S20 (R-10-022a): every tag a node holds opens exactly the child it names
   and nothing else, on both roots. This is what makes the tag placement a
   mechanism rather than a field: the current root's two children and the
   retained root's one open under the tags their parents carry, and each
   refuses the other's block. *)
Example every_node_tag_opens_exactly_its_own_child :
  spec_placement demo demo_medium (blk_node (demo_medium 0)) 0 1 = true
  /\ spec_placement demo demo_medium (blk_node (demo_medium 0)) 1 2 = true
  /\ spec_placement demo demo_medium (blk_node (demo_medium 0)) 0 2 = false
  /\ spec_placement demo demo_medium (blk_node (demo_medium 0)) 1 1 = false
  /\ spec_placement demo demo_medium (blk_node (demo_medium 3)) 0 4 = true
  /\ spec_placement demo demo_medium (blk_node (demo_medium 3)) 0 1 = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* A blank block opens under neither placement, which is the read side of
   reading 2: an unwritten block is refused rather than returned. *)
Example a_blank_block_opens_under_neither_placement :
  spec_placement demo demo_medium (blk_node (demo_medium 0)) 0
    (fresh_block demo 0) = false
  /\ beside_placement demo demo_medium leaf_node 0 (fresh_block demo 0) = false
  /\ blk_content blank_block = 0 /\ blk_tag blank_block = 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* --- Every plan, stated rather than described, and the tags the new root
       holds shown to open the children it names once the commit has
       landed. ---------------------------------------------------------- *)

Example the_commit_plans_name_their_blocks :
  w_block new_leaf = 10 /\ w_block new_root = 11
  /\ node_kids (w_node new_root) = cons 10 (cons 2 nil)
  /\ node_tags (w_node new_root) = cons 11 (cons 3 nil)
  /\ node_kids (w_node new_leaf) = nil :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example the_published_root_authenticates_the_children_it_names :
  spec_placement demo
    (land demo (count_of (cm_plan demo_commit)) (cm_plan demo_commit) demo_medium)
    (w_node new_root) 0 10 = true
  /\ spec_placement demo
    (land demo (count_of (cm_plan demo_commit)) (cm_plan demo_commit) demo_medium)
    (w_node new_root) 1 2 = true
  /\ spec_placement demo
    (land demo (count_of (cm_plan demo_commit)) (cm_plan demo_commit) demo_medium)
    (w_node new_root) 0 2 = false :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_refuting_plans_name_their_blocks :
  w_block inplace_write = 1
  /\ node_kids (w_node inplace_root) = cons 1 (cons 2 nil)
  /\ node_tags (w_node inplace_root) = cons 2 (cons 3 nil)
  /\ w_block reuse_write = 4
  /\ node_kids (w_node reuse_root) = cons 4 (cons 2 nil)
  /\ node_tags (w_node reuse_root) = cons 5 (cons 3 nil) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* The four constructions differ in their plan and never in what they
   retain, which is what makes them comparable at all: a separation drawn
   between two commits that also disagreed about the snapshot would be a
   separation about the snapshot. *)
Example every_construction_retains_the_same_snapshot_root :
  cm_retained demo_commit = cons 3 nil
  /\ cm_retained inplace_commit = cons 3 nil
  /\ cm_retained root_first_commit = cons 3 nil
  /\ cm_retained retained_reuse_commit = cons 3 nil
  /\ reach_set demo demo_medium 3 = cons 3 (cons 4 nil) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* And every one of them publishes the same root as the specification's own
   commit, so what separates them is the plan that reaches it and never the
   block it names. *)
Example every_construction_publishes_the_same_root :
  cm_new_root demo_commit = fresh_block demo 1
  /\ cm_new_root inplace_commit = cm_new_root demo_commit
  /\ cm_new_root root_first_commit = cm_new_root demo_commit
  /\ cm_new_root retained_reuse_commit = cm_new_root demo_commit
  /\ cm_old_root demo_commit = root_block demo :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* --- 5. The commit whose published root names a child nothing wrote.
       It allocates blank blocks, spares every retained root and publishes
       last, and reading 7's second disjunct is what it fails: the child is
       neither in the plan nor a node the medium already holds whole. ---- *)

Definition dangling_root : Write :=
  {| w_block := fresh_block demo 1;
     w_node := node_over (cons (fresh_block demo 0) (cons 9 nil))
                         (cons 11 (cons 1 nil)) |}.

Definition dangling_commit : Commit := {|
  cm_plan := cons new_leaf (cons dangling_root nil);
  cm_new_root := fresh_block demo 1;
  cm_old_root := root_block demo;
  cm_retained := cons 3 nil
|}.

Theorem the_dangling_child_is_refuted :
  ~ CrashConsistent demo demo_medium dangling_commit spec_sequencer.
Proof. intros H. specialize (H 2 0). discriminate H. Qed.

Theorem the_dangling_commit_keeps_every_other_conjunct :
  root_is_last dangling_commit = true
  /\ allocates_blank demo_medium dangling_commit = true
  /\ spares_the_retained demo demo_medium dangling_commit = true
  /\ kids_resolve demo demo_medium dangling_commit = false
  /\ RetainedRootsUnmoved demo demo_medium dangling_commit.
Proof.
  split; [ reflexivity | ]. split; [ reflexivity | ]. split; [ reflexivity | ].
  split; [ reflexivity | ].
  exact (the_specification_leaves_every_retained_root_unmoved demo demo_medium
           dangling_commit eq_refl).
Qed.

Example the_dangling_child_is_neither_written_nor_held_whole :
  node_kids (w_node dangling_root) = cons 10 (cons 9 nil)
  /\ node_tags (w_node dangling_root) = cons 11 (cons 1 nil)
  /\ in_plan (cm_plan dangling_commit) 9 = false
  /\ covered demo demo_medium 9 = false
  /\ blank (demo_medium 9) = true
  /\ cm_retained dangling_commit = cons 3 nil
  /\ cm_new_root dangling_commit = fresh_block demo 1 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

(* --- 6. The commit that writes nothing at all. R-10-036 commits a
       checkpoint as a single L0 transaction, and a plan with no writes
       publishes a root the commit never wrote: which is why `root_is_last`
       answers false there rather than by convention. ------------------- *)

Definition empty_commit : Commit := {|
  cm_plan := nil;
  cm_new_root := fresh_block demo 1;
  cm_old_root := root_block demo;
  cm_retained := cons 3 nil
|}.

Theorem an_empty_plan_publishes_a_root_it_never_wrote :
  spec_sequencer empty_commit 0 = cm_new_root empty_commit
  /\ covered demo (land_torn demo 0 0 (cm_plan empty_commit) demo_medium)
                  (spec_sequencer empty_commit 0) = false.
Proof. split; reflexivity. Qed.

Theorem the_empty_commit_is_refuted :
  ~ CrashConsistent demo demo_medium empty_commit spec_sequencer.
Proof. intros H. specialize (H 0 0). discriminate H. Qed.

Example the_empty_plan_is_refused_at_the_publish_conjunct :
  root_is_last empty_commit = false
  /\ count_of (cm_plan empty_commit) = 0
  /\ admissible demo demo_medium empty_commit = false
  /\ cm_retained empty_commit = cons 3 nil
  /\ cm_new_root empty_commit = cm_new_root demo_commit :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* --- The four admission conjuncts are four and not one, exhibited by a
       construction failing one apiece with the other three standing.
       Without this the middle conjunctions could each be a disjunction and
       nothing above would notice. ------------------------------------- *)

Example the_four_admission_conjuncts_are_independent :
  map_over (fun c => admissible demo demo_medium c)
           (cons demo_commit (cons empty_commit (cons inplace_commit
           (cons retained_reuse_commit (cons dangling_commit nil)))))
  = cons true (cons false (cons false (cons false (cons false nil))))
  /\ map_over (fun c => root_is_last c)
       (cons demo_commit (cons empty_commit (cons inplace_commit
       (cons retained_reuse_commit (cons dangling_commit nil)))))
  = cons true (cons false (cons true (cons true (cons true nil))))
  /\ map_over (fun c => allocates_blank demo_medium c)
       (cons demo_commit (cons empty_commit (cons inplace_commit
       (cons retained_reuse_commit (cons dangling_commit nil)))))
  = cons true (cons true (cons false (cons false (cons true nil))))
  /\ map_over (fun c => spares_the_retained demo demo_medium c)
       (cons demo_commit (cons empty_commit (cons inplace_commit
       (cons retained_reuse_commit (cons dangling_commit nil)))))
  = cons true (cons true (cons true (cons false (cons true nil))))
  /\ map_over (fun c => kids_resolve demo demo_medium c)
       (cons demo_commit (cons empty_commit (cons inplace_commit
       (cons retained_reuse_commit (cons dangling_commit nil)))))
  = cons true (cons true (cons true (cons true (cons false nil)))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* --- The duplicate arm's value, read back through the family that
       generates it rather than through a literal beside it. ------------ *)

Example the_duplicate_value_the_family_inserts :
  map_over (fun l => look nat_keys 1 (demo_index l))
           (key_duplications demo_entries)
  = cons (Some 10) (cons (Some 10) (cons (Some 99) (cons (Some 99)
    (cons (Some 99) (cons (Some 99) nil))))) := eq_refl.

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
Print Assumptions concat_of.
Print Assumptions upto.
Print Assumptions before_last.
Print Assumptions take.
Print Assumptions drop.
Print Assumptions nth_opt.
Print Assumptions last_opt.
Print Assumptions nth_or.
Print Assumptions only_if.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions orb_split.
Print Assumptions only_if_elim.
Print Assumptions nat_eqb_refl.
Print Assumptions nat_eqb_true.
Print Assumptions nat_leb_refl.
Print Assumptions nat_leb_total.
Print Assumptions nat_leb_trans.
Print Assumptions nat_leb_antisym.
Print Assumptions all_of_app.
Print Assumptions any_of_app.
Print Assumptions all_of_const.
Print Assumptions all_of_mono.
Print Assumptions mem_of.
Print Assumptions mem_of_head.
Print Assumptions mem_of_tail.
Print Assumptions all_of_elim.
Print Assumptions all_of_intro.
Print Assumptions all_of_agree.
Print Assumptions map_over_agree.
Print Assumptions mem_of_app.
Print Assumptions orb_false_right.
Print Assumptions orb_true_split.
Print Assumptions all_of_take.
Print Assumptions all_of_map.
Print Assumptions app_assoc_of.
Print Assumptions map_over_app.
Print Assumptions concat_of_app.
Print Assumptions app_of_take_and_drop.
Print Assumptions mem_of_concat.
Print Assumptions leb_of_succ.
Print Assumptions the_empty_conjunction_holds.
Print Assumptions the_empty_disjunction_fails.
Print Assumptions nothing_has_length_zero.
Print Assumptions the_index_set_of_three.
Print Assumptions before_last_of_nothing.
Print Assumptions a_cut_at_zero_keeps_nothing.
Print Assumptions the_index_past_the_end_is_none.
Print Assumptions the_fallback_is_taken_past_the_end.
Print Assumptions only_if_is_implication.
Print Assumptions membership_is_decided_and_not_assumed.
Print Assumptions concatenation_flattens_one_level.
Print Assumptions intact.
Print Assumptions Discipline.
Print Assumptions scan.
Print Assumptions sieve.
Print Assumptions keep_all.
Print Assumptions bite.
Print Assumptions AdmitsOnlyIntactRecords.
Print Assumptions IsIdempotent.
Print Assumptions StopsAtTheFirstTear.
Print Assumptions SkipsTheTornRecord.
Print Assumptions commits.
Print Assumptions Store.
Print Assumptions put.
Print Assumptions apply_all.
Print Assumptions Recovery.
Print Assumptions recover_under.
Print Assumptions spec_recover.
Print Assumptions sieve_recover.
Print Assumptions last_write.
Print Assumptions writes_committed.
Print Assumptions touched_under.
Print Assumptions touched.
Print Assumptions LeavesUntouchedBlocks.
Print Assumptions LandsEveryCommittedWrite.
Print Assumptions ReadsOnlyWhatTheDisciplineAdmits.
Print Assumptions ReplayIsIdempotent.
Print Assumptions apply_all_untouched.
Print Assumptions last_write_none.
Print Assumptions apply_all_last.
Print Assumptions last_write_some.
Print Assumptions scan_is_idempotent.
Print Assumptions sieve_is_idempotent.
Print Assumptions scan_admits_only_intact_records.
Print Assumptions sieve_admits_only_intact_records.
Print Assumptions a_discipline_leaves_untouched_blocks_alone.
Print Assumptions a_discipline_lands_every_committed_write.
Print Assumptions an_idempotent_discipline_reads_only_what_it_admits.
Print Assumptions an_honest_recovery_replays_idempotently.
Print Assumptions a_discipline_replays_idempotently.
Print Assumptions the_specification_leaves_untouched_blocks_alone.
Print Assumptions the_specification_lands_every_committed_write.
Print Assumptions the_specification_reads_only_what_the_discipline_admits.
Print Assumptions the_specification_replay_is_idempotent.
Print Assumptions the_stopping_arm_keeps_every_shared_obligation.
Print Assumptions the_skipping_arm_keeps_every_shared_obligation.
Print Assumptions the_stopping_arm_stops.
Print Assumptions the_skipping_arm_skips.
Print Assumptions whole_probe.
Print Assumptions torn_probe.
Print Assumptions the_probe_records_declare.
Print Assumptions probe_journal.
Print Assumptions past_the_cut_journal.
Print Assumptions probe_store.
Print Assumptions the_probe_store_and_journal_declare.
Print Assumptions the_stopping_arm_does_not_skip.
Print Assumptions the_skipping_arm_does_not_stop.
Print Assumptions the_whole_journal_admits_a_torn_record.
Print Assumptions the_whole_journal_is_still_idempotent.
Print Assumptions the_biting_discipline_is_not_idempotent.
Print Assumptions the_biting_discipline_still_admits_only_intact_records.
Print Assumptions what_the_four_disciplines_admit.
Print Assumptions zeroing_recover.
Print Assumptions stale_recover.
Print Assumptions unscanned_recover.
Print Assumptions the_zeroing_recovery_still_lands_every_committed_write.
Print Assumptions the_stale_recovery_keeps_every_other_obligation.
Print Assumptions the_unscanned_recovery_still_replays_idempotently.
Print Assumptions honest_at.
Print Assumptions the_specification_recovers_honestly_from_every_journal.
Print Assumptions scan_of_a_cut_is_carried_forward.
Print Assumptions no_later_crash_point_uncommits_a_transaction.
Print Assumptions cuts.
Print Assumptions tear.
Print Assumptions tear_at.
Print Assumptions replay_prefix.
Print Assumptions replay_suffix.
Print Assumptions scan_of_an_intact_journal.
Print Assumptions apply_all_app.
Print Assumptions apply_all_agrees.
Print Assumptions last_write_app.
Print Assumptions commits_app.
Print Assumptions writes_committed_app.
Print Assumptions the_commit_set_of_a_replay_is_the_journal_s.
Print Assumptions replaying_a_prefix_reaches_the_same_store.
Print Assumptions replaying_a_suffix_reaches_the_same_store.
Print Assumptions swap_at.
Print Assumptions drop_at.
Print Assumptions suffix_at.
Print Assumptions insert_at.
Print Assumptions agrees_on.
Print Assumptions Medium.
Print Assumptions complete.
Print Assumptions blank.
Print Assumptions a_blank_block_is_not_complete.
Print Assumptions kids_of.
Print Assumptions layers.
Print Assumptions reach_set.
Print Assumptions reaches.
Print Assumptions covered.
Print Assumptions covered_reaches_complete.
Print Assumptions covered_intro.
Print Assumptions a_blank_block_is_out_of_every_cover.
Print Assumptions layers_frame.
Print Assumptions cover_survives_a_write_off_the_cover.
Print Assumptions covered_to.
Print Assumptions layers_of_app.
Print Assumptions covered_to_monotone.
Print Assumptions layers_of_a_member.
Print Assumptions a_block_is_in_its_own_reach.
Print Assumptions a_covered_root_is_itself_whole.
Print Assumptions in_plan.
Print Assumptions place.
Print Assumptions whole_of.
Print Assumptions torn_of.
Print Assumptions land.
Print Assumptions land_torn.
Print Assumptions Sequencer.
Print Assumptions spec_sequencer.
Print Assumptions allocates_blank.
Print Assumptions spares_the_retained.
Print Assumptions root_is_last.
Print Assumptions kids_resolve.
Print Assumptions admissible.
Print Assumptions CrashConsistent.
Print Assumptions RetainedRootsUnmoved.
Print Assumptions in_plan_cons.
Print Assumptions a_plan_block_takes_the_conjunct.
Print Assumptions a_plan_block_takes_the_negated_conjunct.
Print Assumptions land_untouched.
Print Assumptions nth_opt_is_in_the_plan.
Print Assumptions land_torn_untouched.
Print Assumptions the_specification_leaves_every_retained_root_unmoved.
Print Assumptions the_previous_root_survives_every_crash_point.
Print Assumptions land_stabilizes.
Print Assumptions nth_opt_past_the_end.
Print Assumptions past_the_plan_every_crash_point_is_one_medium.
Print Assumptions every_planned_block_is_whole.
Print Assumptions landed.
Print Assumptions land_places_a_planned_node.
Print Assumptions last_opt_is_in_the_plan.
Print Assumptions a_cover_survives_the_whole_commit.
Print Assumptions every_kid_of_a_planned_node_resolves.
Print Assumptions the_frontier_stays_covered.
Print Assumptions the_new_root_is_covered_when_the_plan_has_landed.
Print Assumptions an_admissible_commit_is_crash_consistent.
Print Assumptions Index.
Print Assumptions ins.
Print Assumptions ins_all.
Print Assumptions look.
Print Assumptions ge_all.
Print Assumptions sorted.
Print Assumptions key_eqb_sym.
Print Assumptions key_eqb_false_sym.
Print Assumptions key_not_leb_gives_leb.
Print Assumptions ge_all_widen.
Print Assumptions ins_keeps_ge_all.
Print Assumptions inserting_preserves_the_order.
Print Assumptions inserting_a_list_preserves_the_order.
Print Assumptions the_key_just_written_reads_back.
Print Assumptions no_other_key_moves.
Print Assumptions transposing_two_distinct_writes_answers_the_same_everywhere.
Print Assumptions Buffered.
Print Assumptions blook.
Print Assumptions flush.
Print Assumptions plain_look.
Print Assumptions a_buffered_message_shadows_the_entry_beneath_it.
Print Assumptions an_unbuffered_key_falls_through.
Print Assumptions a_flushed_node_has_an_empty_buffer.
Print Assumptions chunks.
Print Assumptions leaves.
Print Assumptions take_is_bounded.
Print Assumptions no_chunk_holds_more_than_the_bound.
Print Assumptions node_fits.
Print Assumptions leaf_holding.
Print Assumptions Builder.
Print Assumptions spec_builder.
Print Assumptions NoNodeOverflows.
Print Assumptions the_specification_builder_overflows_no_node.
Print Assumptions overflowing_builder.
Print Assumptions every_reached_node_fits.
Print Assumptions expects.
Print Assumptions Placement.
Print Assumptions spec_placement.
Print Assumptions beside_placement.
Print Assumptions ReadsTheReferrersTag.
Print Assumptions the_specification_reads_the_referrers_tag.
Print Assumptions RefusesAMisdirectedRead.
Print Assumptions the_specification_refuses_a_misdirected_read.
Print Assumptions demo.
Print Assumptions the_demo_machine_declares.
Print Assumptions rec_of.
Print Assumptions demo_journal.
Print Assumptions demo_store.
Print Assumptions store_view.
Print Assumptions the_journal_is_six_records_over_three_transactions.
Print Assumptions the_store_before_the_crash.
Print Assumptions the_recovered_store.
Print Assumptions the_open_transaction_leaves_no_trace.
Print Assumptions there_are_seven_crash_points.
Print Assumptions the_store_at_every_crash_point.
Print Assumptions every_crash_point_recovers_honestly.
Print Assumptions the_crash_points_are_not_all_alike.
Print Assumptions torn_agrees.
Print Assumptions torn_writes_at.
Print Assumptions the_torn_family_is_twenty_four.
Print Assumptions every_torn_write_recovers_as_the_cut_before_it.
Print Assumptions no_torn_record_is_replayed.
Print Assumptions a_torn_commit_record_loses_its_transaction.
Print Assumptions the_two_recovery_readings_disagree.
Print Assumptions what_each_recovery_reading_reaches.
Print Assumptions the_zeroing_recovery_is_refuted.
Print Assumptions what_the_zeroing_recovery_reaches.
Print Assumptions the_stale_recovery_is_refuted.
Print Assumptions what_the_stale_recovery_reaches.
Print Assumptions the_unscanned_recovery_is_refuted.
Print Assumptions what_the_unscanned_recovery_reaches.
Print Assumptions replay_agrees.
Print Assumptions every_replayed_prefix_reaches_the_same_store.
Print Assumptions every_replayed_suffix_reaches_the_same_store.
Print Assumptions no_replayed_prefix_moves_the_store.
Print Assumptions no_replayed_suffix_moves_the_store.
Print Assumptions which_transpositions_are_observable.
Print Assumptions every_transposition_still_recovers_honestly.
Print Assumptions leaf_node.
Print Assumptions node_over.
Print Assumptions node_with.
Print Assumptions blank_block.
Print Assumptions demo_medium.
Print Assumptions the_medium_holds_two_roots_and_a_blank_pool.
Print Assumptions a_block_outside_a_root_is_not_reached.
Print Assumptions new_leaf.
Print Assumptions new_root.
Print Assumptions demo_commit.
Print Assumptions the_commit_is_admissible.
Print Assumptions the_commit_shares_the_sibling_it_did_not_rewrite.
Print Assumptions cow_row.
Print Assumptions every_crash_point_of_the_commit_covers_its_root.
Print Assumptions the_demo_commit_is_crash_consistent.
Print Assumptions the_demo_commit_leaves_the_retained_root_unmoved.
Print Assumptions inplace_write.
Print Assumptions inplace_root.
Print Assumptions inplace_commit.
Print Assumptions the_inplace_updater_is_refuted.
Print Assumptions the_inplace_updater_writes_a_block_that_is_not_blank.
Print Assumptions the_inplace_updater_keeps_every_other_obligation.
Print Assumptions which_crash_points_the_inplace_updater_fails.
Print Assumptions eager_sequencer.
Print Assumptions the_eager_publisher_is_refuted.
Print Assumptions the_eager_publisher_agrees_outside_the_plan.
Print Assumptions which_crash_points_the_eager_publisher_fails.
Print Assumptions the_published_root_is_named_only_past_the_whole_plan.
Print Assumptions root_first_commit.
Print Assumptions the_root_first_plan_is_refused_by_the_conjunct.
Print Assumptions the_root_first_plan_is_still_crash_consistent_under_the_specification.
Print Assumptions the_root_first_plan_keeps_every_other_conjunct.
Print Assumptions a_block_a_covered_root_reaches_is_never_blank.
Print Assumptions reuse_write.
Print Assumptions reuse_root.
Print Assumptions retained_reuse_commit.
Print Assumptions the_retained_reuse_moves_a_retained_block.
Print Assumptions the_retained_reuse_is_crash_consistent_all_the_same.
Print Assumptions the_retained_reuse_fails_the_two_conjuncts_a_live_block_costs.
Print Assumptions the_retained_root_reaches_the_reused_block.
Print Assumptions the_beside_placement_opens_a_misdirected_read.
Print Assumptions retag.
Print Assumptions retagged_medium.
Print Assumptions the_retagged_medium_moves_only_the_stored_tag.
Print Assumptions the_beside_placement_reads_the_block_s_own_tag.
Print Assumptions the_specification_placement_is_unmoved_by_the_retag.
Print Assumptions the_beside_placement_opens_the_intended_read.
Print Assumptions a_child_with_no_tag_never_opens.
Print Assumptions nat_keys.
Print Assumptions pairs_eqb.
Print Assumptions demo_index.
Print Assumptions demo_entries.
Print Assumptions the_index_is_the_sorted_keyspace.
Print Assumptions the_index_answers_the_keys_it_was_given.
Print Assumptions key_transpositions.
Print Assumptions key_deletions.
Print Assumptions key_suffixes.
Print Assumptions key_duplications.
Print Assumptions key_orders.
Print Assumptions the_key_order_family_is_twenty.
Print Assumptions builds_the_same_index.
Print Assumptions every_permutation_builds_the_same_index.
Print Assumptions no_adjacent_transposition_moves_the_index.
Print Assumptions the_general_transposition_theorem_at_the_demo_keys.
Print Assumptions every_deletion_builds_a_different_index.
Print Assumptions every_proper_suffix_builds_a_different_index.
Print Assumptions the_duplicate_wins_exactly_where_it_arrives_late.
Print Assumptions the_duplicate_that_wins_is_the_later_one.
Print Assumptions every_key_order_builds_a_sorted_index.
Print Assumptions the_empty_and_singleton_cases_are_admitted.
Print Assumptions boundary_keys.
Print Assumptions the_leaves_at_the_fanout_boundary.
Print Assumptions no_leaf_at_any_boundary_overflows_the_fanout.
Print Assumptions overflowing_leaves.
Print Assumptions the_overflowing_chunking_is_refuted.
Print Assumptions the_overflowing_chunking_still_partitions_the_index.
Print Assumptions every_node_of_the_demo_tree_fits_the_declared_fanout.
Print Assumptions crowded_node.
Print Assumptions untagged_node.
Print Assumptions the_two_conjuncts_of_a_node_are_two.
Print Assumptions crowded_medium.
Print Assumptions the_crowded_tree_overflows_the_fanout.
Print Assumptions the_crowded_medium_replaces_one_block.
Print Assumptions the_overflowing_builder_is_refuted.
Print Assumptions the_overflowing_builder_still_partitions_the_keys.
Print Assumptions demo_buffer.
Print Assumptions a_buffered_message_is_visible_before_it_is_flushed.
Print Assumptions the_flush_reconciles_the_two_readers.
Print Assumptions the_flushed_index_is_still_sorted.
Print Assumptions the_journal_records_declare.
Print Assumptions the_open_transaction_is_named_and_targeted.
Print Assumptions the_medium_contents_and_tags.
Print Assumptions the_nodes_name_their_children_and_hold_their_tags.
Print Assumptions every_node_tag_opens_exactly_its_own_child.
Print Assumptions a_blank_block_opens_under_neither_placement.
Print Assumptions the_commit_plans_name_their_blocks.
Print Assumptions the_published_root_authenticates_the_children_it_names.
Print Assumptions the_refuting_plans_name_their_blocks.
Print Assumptions every_construction_retains_the_same_snapshot_root.
Print Assumptions every_construction_publishes_the_same_root.
Print Assumptions dangling_root.
Print Assumptions dangling_commit.
Print Assumptions the_dangling_child_is_refuted.
Print Assumptions the_dangling_commit_keeps_every_other_conjunct.
Print Assumptions the_dangling_child_is_neither_written_nor_held_whole.
Print Assumptions empty_commit.
Print Assumptions an_empty_plan_publishes_a_root_it_never_wrote.
Print Assumptions the_empty_commit_is_refuted.
Print Assumptions the_empty_plan_is_refused_at_the_publish_conjunct.
Print Assumptions the_four_admission_conjuncts_are_independent.
Print Assumptions the_duplicate_value_the_family_inserts.
