(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   KeyspaceDomains.v

   The two storage layers above the journal and the index, as the register
   fixes them: R-10-002's L2, filesystem semantics following RefFS with
   (S)FSCQ, and its L3, the SFSCQ/DiskSec data-noninterference method;
   R-10-005's inodes, dirents, extents and xattrs as typed keys in one
   keyspace with the snapshot version a field *in* the key; R-10-005a's
   metadata and queries as views of that keyspace rather than a second
   database; R-10-005b's secondary indexes as instantiations of R-10-003's
   one parametric index, keyed by confidentiality domain and namespace
   identifier, carrying no capability in a key, spanning no domain,
   returning no capability the presented one does not derive, and updating
   in the same L0 transaction as the object and its metadata; R-10-005c's
   live query as a bounded, volatile subscription whose deltas are derived
   only after the committing transaction and whose overflow is one
   rescan-required marker rather than unbounded buffering or backpressure on
   commit; R-12-024a and R-12-024e's resolution and handoff over a delegated
   namespace capability; R-14-012a's private namespace as a manifest-derived
   typed view with no path-based capability lookup and no escape, read
   against R-08-001's deletion of global namespaces; R-10-022's per-extent
   AEAD keyed per confidentiality domain with keys resident only in the
   crypto core, R-10-022a's nonce and tag held by the referring index node,
   and R-10-023's separation of the tag from the dedup address; R-10-015's
   KDF-separated keyed dedup digest and R-10-016's cross-domain
   incomparability; R-10-017's refusal of convergent encryption and
   R-10-018's deletion of the compress-then-encrypt ratio oracle; R-10-027's
   per-domain subvolumes; R-10-014, R-10-032 and R-09-022 on crypto-erase
   and on what a lock is not; R-10-037 on what no restore returns; and
   R-08-021 through R-08-027a and R-05-156 on what an observation is and
   what shape the statement takes.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. Every quantity the register
   leaves to composition is a field of the Composition record, of the
   Sealing record, or of the Keyring record, rather than a literal or a
   top-level Parameter, which is what keeps the R-05-163 assumption gate
   green while leaving the decision where its owner can make it. Nothing is
   admitted and nothing is axiomatized: the Print Assumptions block at the
   end reports every shipped constant closed under the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. No constant here is compiled,
   lowered, or run on either emulator, and nothing here executes anywhere.
   The computed checks are decided inside the kernel by conversion and print
   nothing.

   The one Require, and why it is a dependency rather than a citation.
   `Require Import JournalIndex.` names the sibling artifact this file's
   own obligations are stated over, and it is load-bearing at two places
   R-10-005b puts it. That entry makes a secondary metadata index an
   *instantiation of the one parametric L1 index*, so `l2_keys` below is
   that file's `KeyAlgebra` record discharged at this key type and every
   index property comes from there: not one of
   `inserting_preserves_the_order`, `the_key_just_written_reads_back`,
   `no_other_key_moves` or
   `transposing_two_distinct_writes_answers_the_same_everywhere` is restated
   here, and each is instantiated at this key algebra by a single `exact` so
   that the sharing is a conversion rather than a sentence. That is what
   R-10-003's "verified once and instantiated per object class" costs when
   it is taken literally. Every name declared here is its own: nothing the
   imported file exports is shadowed, so the assumption block at the end
   audits the imported constants and not local twins of them, which is a
   hazard a `Require` carries and no gate reads.
   And the same entry makes the object, the metadata and the index update
   land *in the same L0 transaction*, so the atomicity obligation below is
   stated over that file's own `Rec`, `scan`, `commits`, `touched` and
   `cuts`, and the prepare-time deriver is refuted on that file's own
   six-record journal, whose third transaction never commits. Nothing beyond the Rocq prelude is
   reachable besides it, so Classical and FunctionalExtensionality are
   unavailable and every equality below is stated pointwise or over a
   decidable boolean for that reason: a volume, a store and an ambient
   directory are functions, and two of them are compared extent by extent or
   block by block rather than as functions.

   What is deferred, and to which item. R-10-007 and R-10-008 put this stack
   through CompCert-C with VST/Iris and M5.3 runs it on the emulator;
   nothing below states a refinement, a WCET or a compilation property. The
   AE half of R-10-025 is not here and is not this item's: that entry makes
   the verifiable-encryption claim a *composition*, the scheme's
   IND-CCA/INT-CTXT joined with the filesystem's non-interference at
   R-05-160's fifth seam, so no ciphertext byte is modelled, no cipher is
   named, R-10-024's freeze to AES-GCM appears nowhere, and what the
   filesystem holds of a sealed extent is a stored length, a nonce and a
   keyed digest.

   Freshness is a three-way split and this file carries the storage side of
   the third class. R-10-013b says the split "is three-way and not two":
   beside the low-rate platform state the counter keeps fresh and the bulk
   user data whose freshness is surrendered stands durable component state,
   "declared `Fresh` and carried by a freshness epoch rather than by the
   mutable volume's root". R-10-011's MUST NOT is scoped to the mutable
   user-data volume alone, so it surrenders freshness for one class of the
   three and not for this file's whole subject. R-10-035 puts a
   compartment's declared durable regions in the owning domain's subvolume,
   which is the keyspace below, so the storage side of R-10-013c and
   R-10-013e is owed here: the epoch root over the version of every declared
   `Fresh` region and of nothing else, the acknowledgement of a `Fresh`
   write at the seal and never at the data commit, the loss of an unsealed
   epoch's writes rather than their presentation as fresh, and the refusal
   of a region whose version does not verify against the sealed root. All
   four are stated below.

   What is *not* here is the counter and the crypto core, and neither is
   unowned. R-10-013c makes the epoch root a crypto-core operation beside
   seal/open, which R-10-025 puts outside this item; and R-10-013's
   freshness-epoch-root counter is M3.2's, shipped in RotFirmware.v with the
   sealed epoch as its only advancing event and the data commit refused, so
   the construction refuted below is that file's own commit-advancing twin
   seen from the storage side. That file is named and not Required: this
   file's one `Require` is JournalIndex.v's, and the seam between the two is
   the epoch boundary rather than a shared definition. The authoring
   constraint this file does
   keep is the restricted subset that lowering admits: no general recursion,
   every recursive function structural over a list or a finite index, and
   records and finite indices wherever a datatype is not owed.

   One inductive is owed and no second, and the licence is R-10-005c's alone.
   That entry writes "ordered add/remove deltas", which names what a delta
   *is* rather than sampling what one might be, and "overflow emits one
   rescan-required marker", which names the overflow answer and its
   cardinality; no entry of this register names a third delta form. So
   `Delta` carries three constructors, and R-10-005c is what closes it.
   R-10-005's typed key kinds get the opposite treatment for the opposite
   reason: that entry lists inodes, dirents, extents and xattrs as things L2
   represents and says nothing about the list being complete, and R-10-005b
   names a further typed thing beside them, so `kind_count` is a field of
   the Composition record and a kind is a finite index below it. What is
   read off the register is stated with its entry; what the register leaves
   open is a field. Gap a records that closing the kind enumeration is a
   register act nobody has performed.

   What this file does not do, against the word its own checklist cell
   carries. The M5.2 cell reads "Compose L2 semantics and L3
   confidentiality *host-side*", and "host-side" is the word that
   distinguishes it from M5.3's "run on the emulator". This file delivers
   the statement half and not the execution half: nothing below is compiled,
   extracted, lowered or run, on any host or any emulator, and the computed
   checks are decided inside the kernel by conversion and print nothing.
   What the execution half would take is the route the cell's own
   Wasm-parallel label points at: a QuickChick generator over `K2`, `Delta`
   and `Volume` in [tools/quickchick/](../tools/quickchick/), an extraction
   of the decidable predicates below to a runnable form, and a harness that
   runs them. Nothing here narrows that cell, and the completion note for it
   says the same rather than reading the verb down to what was done.

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. R-10-005's typed key kinds are a composition's roster and not a
      closed enumeration. The entry names inodes, dirents, extents and
      xattrs without saying the list is complete, and R-10-005b adds "typed
      attribute value" beside them, so `kind_count` is a field of the
      Composition record and a kind is a finite index below it, exactly as
      a supervised unit is an index below its roster count.
      `the_kind_roster_is_the_composition_s` exhibits a composition
      declaring five and a keyspace the four-kind one refuses, so nothing
      here is closed by fiat. Gap a records that closing it is a register
      act.
   2. A key is six components and its order is lexicographic over them.
      R-10-005b names the confidentiality domain, the stable namespace
      identifier, the typed attribute value and the object identity;
      R-10-005 adds the kind and puts the snapshot version *in* the key. The
      order over the six is this file's, no entry stating one, and what the
      index needs of it is exactly the five laws JournalIndex.v's record
      asks for.
   3. "O(1) writable snapshots" fixes a class and not a constant, and the
      constant is a field. With the version in the key there is nothing to
      copy, so a snapshot writes no entry; but a snapshot writing a fixed
      number of bookkeeping entries is O(1) too and the entry's own words
      admit it, so `AddsAtMostTheDeclaredConstant` reads
      `snapshot_cost` and never zero. Two obligations stand beside it:
      `KeepsEveryReadItAlreadyHad`, which is what makes a snapshot a
      snapshot, and `ChangesNoReadAtAll`, which is strictly stronger than
      R-10-005 states and is exhibited only so that the first is visibly the
      weaker one. Four constructions decide the three differently, and the
      copying snapshot is refuted of *every* declared constant rather than
      of the demo's.
   4. Non-interference is stated of an arbitrary observer and an arbitrary
      authority set as the two-state agreement R-05-156 makes T: two volumes
      agreeing on everything that authority set covers, and on the declared
      public shape of everything it does not, produce equal observations.
   5. What an observer holds is a key and not a label. Authorisation is
      therefore decided by `holds_key` over the composition's own domain
      roster, and R-10-022's per-domain keying enters as a hypothesis rather
      than as an assumption, which is what makes the shared-key construction
      below expressible at all.
   6. The declared public shape is presence, confidentiality domain and
      plaintext length. No entry of this register admits or denies that any
      of the three is observable, so the weakest reading is taken, the
      relation equates only volumes agreeing on them, and the theorem says
      nothing about hiding them. Gaps b, c and d record the three.
   7. R-10-018 is read onto the *stored length*: with no compressor on any
      path the stored length is a function of the declared length alone. It
      is that reading that makes the compress-then-encrypt ratio oracle an
      expressible construction rather than an absence nothing can refute.
   8. R-10-017 and R-10-023 are read onto the *nonce*. Neither entry states
      what a filesystem observes, and the observable form of both the
      convergent-key prohibition and the per-extent-random nonce is that
      equal plaintexts must not present equal stored forms; a nonce that is
      a function of the plaintext is exactly that leak.
   9. R-10-016 is read as a bounded separation the composition can decide,
      because the digest is a field and "incomparable across domains" is a
      property of the function rather than of a carrier. The confirmation-
      of-file clause is extracted from the bounded check rather than
      asserted beside it.
  10. Crypto-erase is a three-part recoverability predicate: a key is
      recoverable if it is resident in the crypto core, or if the sealing
      root still opens its wrapped blob. R-10-014 destroys the root and
      R-10-032 zeroizes residency, and the two are stated apart because
      R-10-032's lock is *not* an erase and a construction shows it.
  11. R-12-024e's "derived only from the namespace capability the caller
      delegated" is read as an attenuation: the object capability carries
      the cap's own domain and namespace and the entry's object identity, at
      rights no wider than the cap's. So minting is a rights property and
      reach is a keyspace property, and the two are separate obligations
      with a construction apiece.
  12. R-10-005b's "no capability is written into a key" is read as: the
      persisted keyspace is a function of what was written and never of the
      authority under which it was written. That is the half a proof can
      hold, and it is what makes R-10-037's "no restore resurrects an
      authority a revocation retired" observable here (gap f).
  13. Boolean rather than propositional wherever the witnesses must compute:
      selection, admission, derivability, agreement, separation and
      recoverability are decidable, so the generated families below are
      checked by conversion in the silent Example form rather than by a
      proof per member.
  14. Freshness is surrendered for one asset class of three and this file
      carries the storage side of a second. R-10-011's MUST NOT is scoped to
      "The mutable user-data volume" and gives its reason, that sealing its
      root would advance the counter at CoW-commit frequency; R-10-013b says
      the split "is three-way and not two" and puts durable component state
      beside it, "declared `Fresh` and carried by a freshness epoch rather
      than by the mutable volume's root". R-10-035 lands that class in this
      keyspace, so R-10-013c's epoch root, its acknowledgement at the seal
      and R-10-013e's refusal are owed here. A region is a finite index
      below `region_count` and its declaration is an arbitrary predicate,
      because R-10-013d makes both a per-compartment manifest declaration
      admission prices. What is not here is the counter and the crypto core:
      R-10-013's freshness-epoch-root counter is M3.2's and is shipped, so
      the commit-acknowledging construction below is that item's own
      commit-advancing twin seen from this side of the seam.

   The literals taken from the design, and there are two, both R-10-005c's.
   That entry's delta alphabet is adds, removes and the one rescan-required
   marker, so `Delta` carries three constructors and no fourth; and its
   overflow answer is *one* marker, so `AtMostOneMarker` compares a count
   against 1. Nothing else below is a count this file closes. In particular
   the typed key kinds are not: `kind_count` is a field, `k_inode` through
   `k_acl` are five witness *names* for indices carrying no closure claim,
   and the day an entry admits a fifth kind is a day this file needs no
   edit. Every other magnitude is a field too: the domain and namespace
   rosters, the kind roster, the snapshot's declared cost, the extent count,
   the plaintext span the bounded separation checks range over, the queue
   and result bounds, the transaction identifier and the three blocks its
   records occupy, the record's granule count, the live snapshot version,
   every key and dedup key, the nonce, the stored length and the digest, and
   the sealing root, residency and blob bits.

   How the refutations are generated. A refutation is a seeded weakening the
   theorem must reject, so the families below are produced over the
   specification's own structure rather than authored member by member. Over
   the entry list's insertion order: `k2_transpositions` transposes an
   adjacent pair, `k2_deletions` deletes one entry, `k2_suffixes` re-enters
   at a proper suffix and `k2_duplications` writes one key a second time,
   which is twenty orders, every one refused or admitted as one conversion
   and again as a theorem quantified over the index. Over the keyring: the
   three independent bits are enumerated exhaustively at eight states and
   every eraser is decided at every one of them. Over the volume: one twin
   volume per extent, differing in that extent's plaintext alone, held
   against five sealings at once, so the leak table is a family rather than
   a case. Over the delta stream and the batch: every prefix, which is every
   crash point, read through JournalIndex.v's own cuts. And over the domain
   roster and the plaintext span: the dedup separation is a grid the
   composition's own counts size. Beside every family the generic theorem
   quantifies over the index rather than enumerating. The hand-authored
   refutations are the ones no index generates, being alternative
   constructions rather than mutations of a list.

   What this file deliberately does not author, with the entry that owes
   each decision. A register gap is reported, not closed:

   a. Whether R-10-005's four typed kinds are a closed enumeration. The
      entry lists inodes, dirents, extents and xattrs without saying the
      list is closed, and R-10-005b adds "typed attribute value" without
      saying whether an attribute is a fifth kind or a component of the four.
      Nothing below closes it: the count is a field, a kind is an index, and
      `the_kind_roster_is_the_composition_s` exhibits a composition
      declaring five. Closing it is a register act, and M4.2b is the
      precedent, R-07-027a having had to close the object inventory at three
      classes before authoring could proceed. Owed at R-10-005.
   b. Whether the existence of a stored extent is observable to a reader who
      holds no key for its domain. Nothing in §10 says, and the weakest
      reading is taken. Owed at R-10-022 or R-10-012.
   c. Whether an extent's plaintext length is observable, and if not what
      bounds the leak. R-10-018 deletes the compress-then-encrypt ratio
      oracle and no entry states a padding, chunking or length-hiding
      obligation, so no bound is invented here: the length is public in the
      relation below and the theorem claims nothing about hiding it. This is
      the gap with the largest consequence of the nine, a file-length
      channel being the residual a disk-encryption design ordinarily books
      explicitly. Owed at R-10-022 or R-10-018.
   d. Whether the confidentiality-domain label of a stored extent is
      observable. R-10-022 keys per domain and R-10-005b keys the index per
      domain, and neither says whether the label a non-holder meets is
      itself hidden. Owed at R-10-022.
   e. Whether R-10-005c's rescan-required marker occupies a slot of the
      declared queue bound or stands beside it. The reading here puts it
      inside, which is the stronger constraint on the emitter and the weaker
      guarantee to the subscriber, and `BoundsTheQueue` therefore carries
      the hypothesis that the declared bound is at least one. Owed at
      R-10-005c.
   f. Whether a *recorded* right may be persisted into a key where a
      capability may not. R-10-005b forbids a capability in a key and
      R-10-037 forbids a restore that returns authority, while R-08-037a
      admits exactly one durable record that names rights and confers none.
      Whether an index key may carry the same is unstated, and the weakest
      reading is taken. Owed at R-10-005b or R-08-037a.
   g. What order R-10-005c's deltas are in. The entry says "ordered
      add/remove deltas" and names no order, so nothing below states one and
      the emitter is required only to deliver the stream's own prefix. Owed
      at R-10-005c.
   i. What a `Fresh` region's *version* is, and what unit a region is.
      R-10-013c computes one root over "the version of every `Fresh`
      region" without saying whether that version is a counter, a content
      digest, or R-10-005's own snapshot version; R-10-035 makes a region a
      typed region of a compartment's manifest without fixing its extent in
      the keyspace. So the version is an arbitrary map from a region index
      and nothing below reads its representation, only which versions reach
      the root. Owed at R-10-013c or R-10-035.
   h. Every composition magnitude. The domain, namespace and kind rosters,
      the snapshot's declared cost, the durable-region count, the extent
      count, the plaintext span, the queue and result bounds, the
      transaction and its three blocks, the granule count, the snapshot
      version, the whole of the sealing and the whole of the keyring are
      fields; the demo composition, sealing, volumes, keyspace, batch, delta
      stream, freshness declaration and alias table at the end instantiate
      them with arbitrary witness values that carry no composition claim,
      and so do the five names `k_inode` through `k_acl`.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary resolver, snapshotter, metadata reader,
   persister, writer, emitter, committer, deriver, resumer, path resolver,
   sealing, observer, eraser, epoch root, acknowledger or fresh reader,
   proved of the specification, and refuted of an alternative construction
   the register's own sentence excludes. Every refuting construction is also
   shown to satisfy the obligations it does not break, so what refuses it is
   the named defect and not its shape. Inhabitation is concrete: a keyspace
   of five entries over two domains, two namespaces and four kinds, beside a
   sixth entry at a fifth kind a composition declaring five admits and one
   declaring four does not; a capability that admits one query and not two
   others; a batch of three records over one transaction beside one that
   splits it and one that closes it early; a stream of five deltas against a
   queue of three; two volumes agreeing at one authority set and differing
   under it; five sealings of which four are refuted; four snapshotters
   deciding three obligations differently; three durable regions of which
   two are declared `Fresh`, held against three epoch roots; four epoch
   states against three readers; and eight keyring states of which four
   erasers decide differently.
   ========================================================================= *)

Require Import JournalIndex.

(* -------------------------------------------------------------------------
   The helpers JournalIndex.v does not already export. Everything it does
   export is used from there rather than restated: `all_of`, `any_of`,
   `count_of`, `map_over`, `upto`, `take`, `drop`, `mem_of`, `only_if` and
   the arithmetic lemmas over `Nat.leb` and `Nat.eqb` are that file's, and a
   second copy of any of them here would be a second definition the review
   gate would have to hold against the first.
   ------------------------------------------------------------------------- *)

Definition bool_eqb (a b : bool) : bool := if a then b else negb b.

Lemma bool_eqb_refl : forall a : bool, bool_eqb a a = true.
Proof. intros a. destruct a; reflexivity. Qed.

Lemma bool_eqb_true : forall a b : bool, bool_eqb a b = true -> a = b.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; reflexivity.
Qed.

Definition opt_eqb (a b : option nat) : bool :=
  match a, b with
  | None, None => true
  | Some x, Some y => Nat.eqb x y
  | _, _ => false
  end.

Lemma opt_eqb_refl : forall a : option nat, opt_eqb a a = true.
Proof. intros a. destruct a as [ x | ]; [ exact (nat_eqb_refl x) | reflexivity ]. Qed.

Fixpoint filter_of {A : Type} (p : A -> bool) (l : list A) : list A :=
  match l with
  | nil => nil
  | cons x r => if p x then cons x (filter_of p r) else filter_of p r
  end.

(* Every prefix of a list, from the empty one to the whole: the crash-point
   generator of JournalIndex.v taken off `Rec` so that a delta stream and a
   key order are cut the same way a journal is. *)
Definition prefixes {A : Type} (l : list A) : list (list A) :=
  map_over (fun i => take i l) (upto (S (count_of l))).

Lemma negb_true_elim : forall b : bool, negb b = true -> b = false.
Proof. intros b H. destruct b; [ discriminate H | reflexivity ]. Qed.

Lemma nat_eqb_sym : forall a b : nat, Nat.eqb a b = Nat.eqb b a.
Proof.
  intros a. induction a as [ | x IH ]; intros b.
  - destruct b; reflexivity.
  - destruct b as [ | y ]; [ reflexivity | simpl; exact (IH y) ].
Qed.

Lemma nat_strict_trans :
  forall a b c : nat,
    Nat.leb a b = true -> Nat.eqb a b = false ->
    Nat.leb b c = true -> Nat.eqb b c = false ->
    Nat.eqb a c = false.
Proof.
  intros a b c H1 E1 H2 E2. destruct (Nat.eqb a c) eqn:E; [ | reflexivity ].
  rewrite (nat_eqb_true a c E) in H1.
  rewrite (nat_leb_antisym b c H2 H1) in E2. discriminate E2.
Qed.

Lemma any_of_intro :
  forall (p : nat -> bool) (l : list nat) (x : nat),
    mem_of x l = true -> p x = true -> any_of p l = true.
Proof.
  intros p l. induction l as [ | y r IH ]; intros x Hm Hp.
  - discriminate Hm.
  - unfold mem_of in Hm. simpl in Hm. simpl.
    destruct (Nat.eqb y x) eqn:E.
    + rewrite (nat_eqb_true y x E). rewrite Hp. reflexivity.
    + simpl in Hm. rewrite (IH x Hm Hp). destruct (p y); reflexivity.
Qed.

Lemma any_of_false :
  forall (p : nat -> bool) (l : list nat),
    all_of (fun x => negb (p x)) l = true -> any_of p l = false.
Proof.
  intros p l. induction l as [ | y r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hy Hr ].
    simpl. rewrite (negb_true_elim _ Hy). simpl. exact (IH Hr).
Qed.

Lemma all_of_filter :
  forall (A : Type) (p : A -> bool) (l : list A), all_of p (filter_of p l) = true.
Proof.
  intros A p l. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. destruct (p x) eqn:E; [ simpl; rewrite E; exact IH | exact IH ].
Qed.

Lemma filter_of_app :
  forall (A : Type) (p : A -> bool) (l r : list A),
    filter_of p (app l r) = app (filter_of p l) (filter_of p r).
Proof.
  intros A p l. induction l as [ | x s IH ]; intros r.
  - reflexivity.
  - simpl. destruct (p x); [ simpl; rewrite IH; reflexivity | exact (IH r) ].
Qed.

Lemma filter_of_none :
  forall (A : Type) (p : A -> bool) (l : list A),
    all_of (fun x => negb (p x)) l = true -> filter_of p l = nil.
Proof.
  intros A p l. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    simpl. rewrite (negb_true_elim _ Hx). exact (IH Hr).
Qed.

Lemma filter_refines :
  forall (A : Type) (p q : A -> bool) (l : list A),
    (forall x : A, p x = true -> q x = true) ->
    filter_of p l = filter_of p (filter_of q l).
Proof.
  intros A p q l H. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. destruct (p x) eqn:Ep.
    + rewrite (H x Ep). simpl. rewrite Ep. rewrite IH. reflexivity.
    + destruct (q x); simpl; [ rewrite Ep; exact IH | exact IH ].
Qed.

Lemma count_of_app_one :
  forall (A : Type) (l : list A) (x : A),
    count_of (app l (cons x nil)) = S (count_of l).
Proof.
  intros A l x. induction l as [ | y r IH ];
    [ reflexivity | simpl; rewrite IH; reflexivity ].
Qed.

Lemma count_of_app_two :
  forall (A : Type) (l : list A) (x y : A),
    count_of (app l (cons x (cons y nil))) = S (S (count_of l)).
Proof.
  intros A l x y. induction l as [ | z r IH ];
    [ reflexivity | simpl; rewrite IH; reflexivity ].
Qed.

Lemma mem_upto_step :
  forall (a b : nat), Nat.leb a b = true -> Nat.eqb a b = false -> Nat.ltb a b = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b Hl He.
  - destruct b as [ | y ]; [ discriminate He | reflexivity ].
  - destruct b as [ | y ]; [ discriminate Hl | ].
    simpl in Hl. simpl in He. exact (IH y Hl He).
Qed.

Lemma mem_upto :
  forall (n x : nat), Nat.ltb x n = true -> mem_of x (upto n) = true.
Proof.
  intros n. induction n as [ | k IH ]; intros x H.
  - discriminate H.
  - simpl. rewrite mem_of_app. destruct (Nat.eqb x k) eqn:E.
    + rewrite (nat_eqb_true x k E). rewrite (mem_of_head k nil).
      destruct (mem_of k (upto k)); reflexivity.
    + rewrite (IH x (mem_upto_step x k H E)). reflexivity.
Qed.

(* The helpers' own floors, so that the day one of them stops deciding is
   the day it says so. *)
Example bools_compare_both_ways :
  cons (bool_eqb true true) (cons (bool_eqb true false)
  (cons (bool_eqb false true) (cons (bool_eqb false false) nil)))
  = cons true (cons false (cons false (cons true nil))) := eq_refl.

Example options_compare_both_ways :
  cons (opt_eqb None None) (cons (opt_eqb (Some 1) (Some 1))
  (cons (opt_eqb (Some 1) (Some 2)) (cons (opt_eqb (Some 1) None)
  (cons (opt_eqb None (Some 1)) nil))))
  = cons true (cons true (cons false (cons false (cons false nil)))) := eq_refl.

Example filtering_keeps_exactly_what_it_selects :
  filter_of (fun n => Nat.eqb n 2) (cons 1 (cons 2 (cons 2 (cons 3 nil))))
  = cons 2 (cons 2 nil)
  /\ filter_of (fun n => Nat.eqb n 9) (cons 1 (cons 2 nil)) = nil :=
  conj eq_refl eq_refl.

Example the_prefixes_of_three_are_four :
  prefixes (cons 1 (cons 2 (cons 3 nil)))
  = cons nil (cons (cons 1 nil) (cons (cons 1 (cons 2 nil))
    (cons (cons 1 (cons 2 (cons 3 nil))) nil))) := eq_refl.

(* =========================================================================
   The order the L1 index needs, over a key's own components.

   R-10-003 makes L1 one parametric index generic over key type, and
   JournalIndex.v carries that record with the five laws an instance must
   discharge. Nothing below re-proves an index property: what is here is the
   order on this key type and the discharge of those five laws at it, which
   is what "verified once and instantiated per object class" asks for.
   ========================================================================= *)

Fixpoint lex_leb (a b : list nat) : bool :=
  match a, b with
  | nil, _ => true
  | cons _ _, nil => false
  | cons x r, cons y s =>
      orb (andb (Nat.leb x y) (negb (Nat.eqb x y)))
          (andb (Nat.eqb x y) (lex_leb r s))
  end.

Fixpoint lex_eqb (a b : list nat) : bool :=
  match a, b with
  | nil, nil => true
  | cons x r, cons y s => andb (Nat.eqb x y) (lex_eqb r s)
  | _, _ => false
  end.

Lemma lex_eqb_refl : forall a : list nat, lex_eqb a a = true.
Proof.
  intros a. induction a as [ | x r IH ];
    [ reflexivity | simpl; rewrite nat_eqb_refl; exact IH ].
Qed.

Lemma lex_eqb_true : forall a b : list nat, lex_eqb a b = true -> a = b.
Proof.
  intros a. induction a as [ | x r IH ]; intros b H.
  - destruct b; [ reflexivity | discriminate H ].
  - destruct b as [ | y s ]; [ discriminate H | ].
    simpl in H. destruct (andb_split _ _ H) as [ A B ].
    rewrite (nat_eqb_true x y A). rewrite (IH s B). reflexivity.
Qed.

Lemma lex_leb_cons_elim :
  forall (x y : nat) (r s : list nat),
    lex_leb (cons x r) (cons y s) = true ->
    andb (Nat.leb x y) (negb (Nat.eqb x y)) = true
    \/ (Nat.eqb x y = true /\ lex_leb r s = true).
Proof.
  intros x y r s H. simpl in H.
  destruct (andb (Nat.leb x y) (negb (Nat.eqb x y))) eqn:E.
  - left. reflexivity.
  - simpl in H. right. destruct (andb_split _ _ H) as [ A B ]. split; assumption.
Qed.

Lemma lex_leb_cons_intro_lt :
  forall (x y : nat) (r s : list nat),
    Nat.leb x y = true -> Nat.eqb x y = false ->
    lex_leb (cons x r) (cons y s) = true.
Proof. intros x y r s H G. simpl. rewrite H. rewrite G. reflexivity. Qed.

Lemma lex_leb_cons_intro_eq :
  forall (x y : nat) (r s : list nat),
    Nat.eqb x y = true -> lex_leb r s = true ->
    lex_leb (cons x r) (cons y s) = true.
Proof.
  intros x y r s H G. simpl. rewrite H. rewrite G.
  destruct (Nat.leb x y); reflexivity.
Qed.

Lemma lex_leb_total : forall a b : list nat, orb (lex_leb a b) (lex_leb b a) = true.
Proof.
  intros a. induction a as [ | x r IH ]; intros b.
  - reflexivity.
  - destruct b as [ | y s ]; [ reflexivity | ].
    simpl. destruct (Nat.eqb x y) eqn:E.
    + rewrite (nat_eqb_sym y x). rewrite E.
      destruct (Nat.leb x y); destruct (Nat.leb y x); simpl; exact (IH s).
    + rewrite (nat_eqb_sym y x). rewrite E.
      destruct (Nat.leb x y) eqn:E1; destruct (Nat.leb y x) eqn:E2;
        simpl; try reflexivity.
      assert (Ht := nat_leb_total x y). rewrite E1 in Ht. rewrite E2 in Ht.
      discriminate Ht.
Qed.

Lemma lex_leb_trans :
  forall a b c : list nat, lex_leb a b = true -> lex_leb b c = true ->
    lex_leb a c = true.
Proof.
  intros a. induction a as [ | x r IH ]; intros b c H1 H2.
  - reflexivity.
  - destruct b as [ | y s ]; [ discriminate H1 | ].
    destruct c as [ | z t ]; [ discriminate H2 | ].
    destruct (lex_leb_cons_elim x y r s H1) as [ A1 | [ E1 G1 ] ];
      destruct (lex_leb_cons_elim y z s t H2) as [ A2 | [ E2 G2 ] ].
    + destruct (andb_split _ _ A1) as [ L1 N1 ].
      destruct (andb_split _ _ A2) as [ L2 N2 ].
      apply lex_leb_cons_intro_lt.
      * exact (nat_leb_trans x y z L1 L2).
      * exact (nat_strict_trans x y z L1 (negb_true_elim _ N1) L2
                 (negb_true_elim _ N2)).
    + destruct (andb_split _ _ A1) as [ L1 N1 ].
      rewrite <- (nat_eqb_true y z E2).
      exact (lex_leb_cons_intro_lt x y r t L1 (negb_true_elim _ N1)).
    + destruct (andb_split _ _ A2) as [ L2 N2 ].
      rewrite (nat_eqb_true x y E1).
      exact (lex_leb_cons_intro_lt y z r t L2 (negb_true_elim _ N2)).
    + apply lex_leb_cons_intro_eq.
      * rewrite (nat_eqb_true x y E1). exact E2.
      * exact (IH s t G1 G2).
Qed.

Lemma lex_leb_antisym :
  forall a b : list nat, lex_leb a b = true -> lex_leb b a = true ->
    lex_eqb a b = true.
Proof.
  intros a. induction a as [ | x r IH ]; intros b H1 H2.
  - destruct b; [ reflexivity | discriminate H2 ].
  - destruct b as [ | y s ]; [ discriminate H1 | ].
    destruct (lex_leb_cons_elim x y r s H1) as [ A1 | [ E1 G1 ] ];
      destruct (lex_leb_cons_elim y x s r H2) as [ A2 | [ E2 G2 ] ].
    + destruct (andb_split _ _ A1) as [ L1 N1 ].
      destruct (andb_split _ _ A2) as [ L2 _ ].
      rewrite (nat_leb_antisym x y L1 L2) in N1. discriminate N1.
    + destruct (andb_split _ _ A1) as [ _ N1 ].
      rewrite (nat_eqb_sym y x) in E2. rewrite E2 in N1. discriminate N1.
    + destruct (andb_split _ _ A2) as [ _ N2 ].
      rewrite (nat_eqb_sym x y) in E1. rewrite E1 in N2. discriminate N2.
    + simpl. rewrite E1. exact (IH s G1 G2).
Qed.

(* The order's own floor, and the reason each token of it is load-bearing:
   the empty signature is below everything, a longer one is above the empty
   one, a strictly smaller head wins outright, and an equal head defers to
   the tail. *)
Example the_lexicographic_order_decides :
  cons (lex_leb nil (cons 1 nil)) (cons (lex_leb (cons 1 nil) nil)
  (cons (lex_leb (cons 1 nil) (cons 2 nil)) (cons (lex_leb (cons 2 nil) (cons 1 nil))
  (cons (lex_leb (cons 2 (cons 0 nil)) (cons 1 (cons 9 nil)))
  (cons (lex_leb (cons 1 (cons 0 nil)) (cons 1 (cons 9 nil))) nil)))))
  = cons true (cons false (cons true (cons false (cons false (cons true nil)))))
  := eq_refl.

Example the_lexicographic_equality_decides :
  cons (lex_eqb nil (nil : list nat)) (cons (lex_eqb nil (cons 1 nil))
  (cons (lex_eqb (cons 1 nil) nil)
  (cons (lex_eqb (cons 1 (cons 0 nil)) (cons 1 (cons 9 nil)))
  (cons (lex_eqb (cons 1 (cons 9 nil)) (cons 1 (cons 9 nil))) nil))))
  = cons true (cons false (cons false (cons false (cons true nil)))) := eq_refl.

(* =========================================================================
   R-10-005's typed keys: four kinds in one keyspace, and the snapshot
   version a field *in* the key.
   ========================================================================= *)

(* Reading 1 and gap a. R-10-005 names inodes, dirents, extents and xattrs
   and does not say the list is closed; R-10-005b adds "typed attribute
   value" without saying whether an attribute is a fifth kind. No entry of
   this register closes the enumeration, so nothing here does either: a kind
   is a finite index below the composition's own `kind_count`, exactly as a
   supervised unit is an index below its roster count, and a composition
   that admits a fifth is expressible rather than excluded. Closing it at
   four is a register act and is owed at R-10-005; M4.2b is the precedent,
   R-07-027a having had to close the object inventory at three classes in
   the register before authoring could proceed. *)

(* Which kinds a composition admits, as the index set the checks range over. *)
Definition kinds_of (c_kind_count : nat) : list nat := upto c_kind_count.

(* A key names a kind the composition declares. Nothing below assumes it, so
   it is a stated obligation on a keyspace and never a hypothesis smuggled
   into a definition. *)
Definition kind_in_range (kc : nat) (k : nat) : bool := Nat.ltb k kc.

(* The four kinds R-10-005 names, and a fifth beside them. These are witness
   *names* for indices and carry no closure claim (gap h): what decides how
   many kinds a composition has is its own `kind_count`, and `k_acl` is here
   so that the fifth R-10-005b's "typed attribute value" might be is
   expressible rather than unnameable. *)
Definition k_inode : nat := 0.
Definition k_dirent : nat := 1.
Definition k_extent : nat := 2.
Definition k_xattr : nat := 3.
Definition k_acl : nat := 4.

Example the_named_kinds_are_five_distinct_indices :
  k_inode = 0 /\ k_dirent = 1 /\ k_extent = 2 /\ k_xattr = 3 /\ k_acl = 4
  /\ map_over (fun a => map_over (Nat.eqb a)
                 (cons k_inode (cons k_dirent (cons k_extent
                 (cons k_xattr (cons k_acl nil))))))
       (cons k_inode (cons k_dirent (cons k_extent
       (cons k_xattr (cons k_acl nil)))))
  = cons (cons true (cons false (cons false (cons false (cons false nil)))))
    (cons (cons false (cons true (cons false (cons false (cons false nil)))))
    (cons (cons false (cons false (cons true (cons false (cons false nil)))))
    (cons (cons false (cons false (cons false (cons true (cons false nil)))))
    (cons (cons false (cons false (cons false (cons false (cons true nil)))))
    nil)))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* Reading 2. The six components are the register's: R-10-005b names the
   confidentiality domain, the stable namespace identifier, the typed
   attribute value and the object identity, and R-10-005 adds the kind and
   puts the snapshot version *in* the key. The order over them is this
   file's, no entry stating one. *)
Record K2 : Type := {
  k_domain : nat;
  k_space : nat;
  k_kind : nat;
  k_object : nat;
  k_attr : nat;
  k_version : nat
}.

Definition ksig (k : K2) : list nat :=
  cons (k_domain k) (cons (k_space k) (cons (k_kind k)
  (cons (k_object k) (cons (k_attr k) (cons (k_version k) nil))))).

Definition k2_leb (a b : K2) : bool := lex_leb (ksig a) (ksig b).

Definition k2_eqb (a b : K2) : bool := lex_eqb (ksig a) (ksig b).

Lemma k2_eqb_refl : forall a : K2, k2_eqb a a = true.
Proof. intros a. unfold k2_eqb. exact (lex_eqb_refl (ksig a)). Qed.

Lemma k2_eqb_true : forall a b : K2, k2_eqb a b = true -> a = b.
Proof.
  intros a b H. unfold k2_eqb in H.
  assert (Hs : ksig a = ksig b) by exact (lex_eqb_true _ _ H).
  destruct a as [ ad asp ak ao aa av ]. destruct b as [ bd bsp bk bo ba bv ].
  unfold ksig in Hs. simpl in Hs.
  injection Hs as H1 H2 H3 H4 H5 H6.
  rewrite H1. rewrite H2. rewrite H3. rewrite H4. rewrite H5. rewrite H6.
  reflexivity.
Qed.

(* R-10-003's record, discharged at this key type. This instance is the
   whole of what "instantiated per object class" costs here: no index
   theorem is restated, JournalIndex.v's carrying every one of them. *)
Definition l2_keys : KeyAlgebra := {|
  Key := K2;
  key_leb := k2_leb;
  key_eqb := k2_eqb;
  key_eqb_refl := k2_eqb_refl;
  key_eqb_true := k2_eqb_true;
  key_leb_total := fun a b => lex_leb_total (ksig a) (ksig b);
  key_leb_trans := fun a b c => lex_leb_trans (ksig a) (ksig b) (ksig c);
  key_leb_antisym := fun a b => lex_leb_antisym (ksig a) (ksig b)
|}.

Definition Keyspace : Type := list (prod K2 nat).

(* -------------------------------------------------------------------------
   What the Require buys, checked rather than asserted. Each of the four is
   JournalIndex.v's own index theorem instantiated at this key algebra by a
   single `exact`, so "verified once and instantiated per object class" is a
   conversion here and not a sentence: no index property is re-proved, and
   nothing below carries a second copy of one. Every name in this file is
   its own, so nothing that file exports is shadowed and the assumption
   block below audits the imported constants rather than local twins of
   them.
   ------------------------------------------------------------------------- *)

Theorem the_l2_index_inherits_the_order_theorem :
  forall (k : K2) (v : nat) (ix : Index l2_keys),
    sorted l2_keys ix = true -> sorted l2_keys (ins l2_keys k v ix) = true.
Proof. exact (inserting_preserves_the_order l2_keys). Qed.

Theorem the_l2_index_inherits_the_read_back_theorem :
  forall (k : K2) (v : nat) (ix : Index l2_keys),
    look l2_keys k (ins l2_keys k v ix) = Some v.
Proof. exact (the_key_just_written_reads_back l2_keys). Qed.

Theorem the_l2_index_inherits_the_frame_theorem :
  forall (k j : K2) (v : nat) (ix : Index l2_keys),
    k2_eqb j k = false -> look l2_keys j (ins l2_keys k v ix) = look l2_keys j ix.
Proof. exact (no_other_key_moves l2_keys). Qed.

Theorem the_l2_index_inherits_the_transposition_theorem :
  forall (a b : K2) (u v : nat) (ix : Index l2_keys) (q : K2),
    k2_eqb a b = false ->
    look l2_keys q (ins l2_keys b v (ins l2_keys a u ix))
      = look l2_keys q (ins l2_keys a u (ins l2_keys b v ix)).
Proof. exact (transposing_two_distinct_writes_answers_the_same_everywhere l2_keys). Qed.

(* Every key of a keyspace names a kind the composition declares. Stated
   rather than assumed: it is a property of a keyspace an obligation can
   carry, and a keyspace naming a kind outside the roster is exhibited
   below rather than made unwritable. *)
Definition every_key_names_a_declared_kind (kc : nat) (ks : Keyspace) : bool :=
  all_of (fun e => kind_in_range kc (k_kind (fst e))) ks.

Definition mk_key (d sp kd ob av ve : nat) : K2 :=
  {| k_domain := d; k_space := sp; k_kind := kd; k_object := ob;
     k_attr := av; k_version := ve |}.

Fixpoint entries_eqb (a b : Keyspace) : bool :=
  match a, b with
  | nil, nil => true
  | cons x r, cons y s =>
      andb (andb (k2_eqb (fst x) (fst y)) (Nat.eqb (snd x) (snd y)))
           (entries_eqb r s)
  | _, _ => false
  end.

Definition at_version (ve : nat) (k : K2) : K2 :=
  {| k_domain := k_domain k; k_space := k_space k; k_kind := k_kind k;
     k_object := k_object k; k_attr := k_attr k; k_version := ve |}.

Definition at_attr (av : nat) (k : K2) : K2 :=
  {| k_domain := k_domain k; k_space := k_space k; k_kind := k_kind k;
     k_object := k_object k; k_attr := av; k_version := k_version k |}.

Definition in_domain (d : nat) (e : prod K2 nat) : bool :=
  Nat.eqb (k_domain (fst e)) d.

(* =========================================================================
   The composition: everything §10 leaves to a composition is a field here,
   never a literal and never a top-level Parameter.
   ========================================================================= *)

Record Composition : Type := {

  (* --- R-10-027's enumerated confidentiality domains, and R-10-005b's
         stable namespace identifiers ------------------------------------ *)

  domain_count : nat;
  space_count : nat;

  (* --- R-10-005's typed key kinds. The entry names four and closes
         nothing, and R-10-005b names a fifth candidate, so the count is a
         field and a kind is an index below it (reading 1, gap a) -------- *)

  kind_count : nat;

  (* --- R-10-005's "O(1) writable snapshots" as the entry states it: the
         class is fixed and the constant is not, so what a snapshot may add
         to the keyspace is a declared bound and never zero by fiat
         (reading 3) ----------------------------------------------------- *)

  snapshot_cost : nat;

  (* --- the extents the mutable volume spans ------------------------------ *)

  extent_count : nat;

  (* --- the plaintext values the bounded separation checks below range
         over. Not a magnitude of the design: the register fixes no
         plaintext alphabet, and this is the finite window a conversion can
         decide a separation over (gap h) -------------------------------- *)

  plain_span : nat;

  (* --- R-10-005c's composition-time queue and result bounds ------------- *)

  queue_bound : nat;
  result_bound : nat;

  (* --- the L0 transaction R-10-005b's object, metadata and index update
         land in, and the three blocks they occupy --------------------- *)

  batch_txn : nat;
  object_block : nat;
  meta_block : nat;
  index_block : nat;

  (* --- a record's declared length in write granules, which is
         JournalIndex.v's own gap a read at this layer ------------------- *)

  granules : nat;

  (* --- R-10-005's snapshot version the live generation writes at -------- *)

  live_version : nat;

  (* --- R-10-013b's third asset class: the durable regions a compartment
         declares in its manifest, which R-10-013d prices per compartment
         at admission, so the count is a field and a region is an index
         below it (reading 14) ------------------------------------------- *)

  region_count : nat
}.

(* =========================================================================
   R-10-005: one keyspace, and the snapshot a version field in the key.
   ========================================================================= *)

Definition Snapshotter : Type := Keyspace -> nat -> Keyspace.

(* Reading 3. With the version in the key a snapshot need copy nothing: the
   new generation's writes carry the new version and every older key stands
   where it was. What R-10-005 fixes is the *class*, "O(1) writable
   snapshots", and a snapshot writing a constant number of bookkeeping
   entries is O(1) and is admitted by those words. So the obligation is a
   declared constant and never zero, and `bookkeeping_snapshot` below is the
   construction an exact-zero reading would have refused and this entry does
   not. *)
Definition spec_snapshot : Snapshotter := fun ks _ => ks.

(* The bound R-10-005 states, with the constant a field. *)
Definition AddsAtMostTheDeclaredConstant (c : Composition)
                                         (sn : Snapshotter) : Prop :=
  forall (ks : Keyspace) (ve : nat),
    Nat.leb (count_of (sn ks ve)) (Nat.add (count_of ks) (snapshot_cost c))
      = true.

(* And the half that makes a snapshot a snapshot: every read the keyspace
   already answered still answers the same. This is the weaker of the two
   readings of "snapshot", and it is the one R-10-005's words carry. *)
Definition KeepsEveryReadItAlreadyHad (sn : Snapshotter) : Prop :=
  forall (ks : Keyspace) (ve : nat) (k : K2) (v : nat),
    look l2_keys k ks = Some v -> look l2_keys k (sn ks ve) = Some v.

(* Beside it the strictly stronger form, which is *not* claimed to be
   R-10-005's: a snapshot adding a bookkeeping entry at a fresh version
   changes what a key that read nothing now reads, and the entry admits
   that. It is stated so that the weaker obligation above is visibly the
   weaker one and not the only one expressible. *)
Definition ChangesNoReadAtAll (sn : Snapshotter) : Prop :=
  forall (ks : Keyspace) (ve : nat) (k : K2),
    look l2_keys k (sn ks ve) = look l2_keys k ks.

Lemma leb_add_right : forall a b : nat, Nat.leb a (Nat.add a b) = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b; [ reflexivity | simpl; exact (IH b) ].
Qed.

Lemma add_succ_right : forall a b : nat, Nat.add a (S b) = S (Nat.add a b).
Proof.
  intros a. induction a as [ | x IH ]; intros b;
    [ reflexivity | simpl; rewrite IH; reflexivity ].
Qed.

Lemma leb_succ_self_false : forall n : nat, Nat.leb (S n) n = false.
Proof.
  intros n. induction n as [ | k IH ]; [ reflexivity | simpl; exact IH ].
Qed.

Lemma count_of_app :
  forall (A : Type) (l r : list A),
    count_of (app l r) = Nat.add (count_of l) (count_of r).
Proof.
  intros A l. induction l as [ | x s IH ]; intros r;
    [ reflexivity | simpl; rewrite IH; reflexivity ].
Qed.

Theorem the_specification_snapshot_adds_at_most_the_declared_constant :
  forall c : Composition, AddsAtMostTheDeclaredConstant c spec_snapshot.
Proof.
  intros c ks ve. exact (leb_add_right (count_of ks) (snapshot_cost c)).
Qed.

Theorem the_specification_snapshot_keeps_every_read_it_already_had :
  KeepsEveryReadItAlreadyHad spec_snapshot.
Proof. intros ks ve k v H. exact H. Qed.

Theorem the_specification_snapshot_changes_no_read_at_all :
  ChangesNoReadAtAll spec_snapshot.
Proof. intros ks ve k. reflexivity. Qed.

(* The construction R-10-005's own sentence excludes: a snapshot taken by
   copying the keyspace at the new version, which is what putting the
   version anywhere but *in* the key would cost. Its cost is not a constant
   at all, and the theorem below says so of *every* declared constant rather
   than of the demo composition's. *)
Definition rekeyed (ve : nat) (ks : Keyspace) : Keyspace :=
  map_over (fun e => pair (at_version ve (fst e)) (snd e)) ks.

Definition copy_snapshot : Snapshotter := fun ks ve => app ks (rekeyed ve ks).

(* And the one that keeps the count and loses the older reads, which is the
   twin: two obligations, one construction apiece. *)
Definition rekey_snapshot : Snapshotter := fun ks ve => rekeyed ve ks.

(* The snapshotter the entry *admits* and an exact-zero obligation would
   have refused: it writes one bookkeeping entry at the new version and
   nothing else. It meets the declared bound wherever the composition
   declares at least one, keeps every read the keyspace already had, and
   fails the strong form, which is what makes the strong form visibly not
   R-10-005's. *)
Definition bookkeeping_snapshot (k : K2) : Snapshotter :=
  fun ks ve => app ks (cons (pair (at_version ve k) 0) nil).

Lemma leb_add_left_mono :
  forall a b n : nat,
    Nat.leb a b = true -> Nat.leb (Nat.add n a) (Nat.add n b) = true.
Proof.
  intros a b n. induction n as [ | k IH ]; intros H;
    [ exact H | simpl; exact (IH H) ].
Qed.

(* A keyspace of a declared size, so a cost that grows with the keyspace can
   be refuted of an arbitrary composition rather than of one witness. *)
Fixpoint pad (n : nat) (k : K2) : Keyspace :=
  match n with
  | 0 => nil
  | S m => cons (pair (at_attr m k) 0) (pad m k)
  end.

Lemma count_of_pad : forall (n : nat) (k : K2), count_of (pad n k) = n.
Proof.
  intros n. induction n as [ | m IH ]; intros k;
    [ reflexivity | simpl; rewrite (IH k); reflexivity ].
Qed.

Lemma count_of_rekeyed :
  forall (ve : nat) (ks : Keyspace), count_of (rekeyed ve ks) = count_of ks.
Proof.
  intros ve ks. unfold rekeyed. induction ks as [ | e r IH ];
    [ reflexivity | simpl; rewrite IH; reflexivity ].
Qed.

(* What the two witness keyspaces above actually hold, read back rather than
   left to the counts: a padding entry's value and attribute and the
   bookkeeping entry's value are figures the theorems over them do not
   otherwise constrain. *)
Example the_padding_and_the_bookkeeping_entry_declare :
  count_of (pad 3 (mk_key 0 0 0 0 0 0)) = 3
  /\ map_over (fun e => snd e) (pad 3 (mk_key 0 0 0 0 0 0))
     = cons 0 (cons 0 (cons 0 nil))
  /\ map_over (fun e => k_attr (fst e)) (pad 3 (mk_key 0 0 0 0 0 0))
     = cons 2 (cons 1 (cons 0 nil))
  /\ map_over (fun e => k_version (fst e)) (pad 3 (mk_key 0 0 0 0 0 0))
     = cons 0 (cons 0 (cons 0 nil))
  /\ bookkeeping_snapshot (mk_key 0 0 0 0 0 0) nil 1
     = cons (pair (mk_key 0 0 0 0 0 1) 0) nil
  /\ look l2_keys (mk_key 0 0 0 0 0 1)
       (bookkeeping_snapshot (mk_key 0 0 0 0 0 0) nil 1) = Some 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* =========================================================================
   R-10-005a: metadata is a view of the keyspace and never a second
   database.
   ========================================================================= *)

Definition Metadata : Type := K2 -> option nat.

Definition MetaReader : Type := Keyspace -> Metadata.

Definition spec_meta : MetaReader := fun ks k => look l2_keys k ks.

Definition IsAViewOfTheKeyspace (mr : MetaReader) : Prop :=
  forall (ks : Keyspace) (k : K2), mr ks k = look l2_keys k ks.

Theorem the_specification_metadata_is_a_view :
  IsAViewOfTheKeyspace spec_meta.
Proof. intros ks k. reflexivity. Qed.

(* R-10-005a's "no independent metadata database": a store beside the
   keyspace, consulted where the keyspace answers nothing. It never
   contradicts the keyspace, which is why it has to be refuted by the
   obligation rather than caught by a wrong answer. *)
Definition side_meta (side : Keyspace) : MetaReader :=
  fun ks k => match look l2_keys k ks with
              | Some v => Some v
              | None => look l2_keys k side
              end.

(* =========================================================================
   R-10-005b and R-12-024e: query admission, resolution, and what a
   resolution may hand back.
   ========================================================================= *)

Record NsCap : Type := {
  nc_domain : nat;
  nc_space : nat;
  nc_rights : nat
}.

Record ObjCap : Type := {
  oc_domain : nat;
  oc_space : nat;
  oc_object : nat;
  oc_rights : nat
}.

Record Query : Type := {
  q_domain : nat;
  q_space : nat;
  q_kind : nat;
  q_attr : nat
}.

(* R-12-024e's "derived only from the namespace capability the caller
   delegated", read as an attenuation: the object capability carries the
   cap's own domain and namespace and the entry's object identity, at rights
   no wider than the cap's. *)
Definition derivable (n : NsCap) (o : ObjCap) : bool :=
  andb (Nat.eqb (oc_domain o) (nc_domain n))
  (andb (Nat.eqb (oc_space o) (nc_space n))
        (Nat.leb (oc_rights o) (nc_rights n))).

(* R-10-005b's "the presented namespace capability is checked at query
   admission against that identifier". *)
Definition admits (n : NsCap) (q : Query) : bool :=
  andb (Nat.eqb (q_domain q) (nc_domain n)) (Nat.eqb (q_space q) (nc_space n)).

Definition selects (q : Query) (e : prod K2 nat) : bool :=
  andb (Nat.eqb (k_domain (fst e)) (q_domain q))
  (andb (Nat.eqb (k_space (fst e)) (q_space q))
  (andb (Nat.eqb (k_kind (fst e)) (q_kind q))
        (Nat.eqb (k_attr (fst e)) (q_attr q)))).

Definition grant (n : NsCap) (e : prod K2 nat) : ObjCap :=
  {| oc_domain := nc_domain n; oc_space := nc_space n;
     oc_object := k_object (fst e); oc_rights := nc_rights n |}.

Definition Resolver : Type := NsCap -> Query -> Keyspace -> list ObjCap.

Definition spec_resolve : Resolver :=
  fun n q ks => if admits n q
                then map_over (grant n) (filter_of (selects q) ks)
                else nil.

(* The three obligations, each of an arbitrary resolver. *)
Definition MintsNothing (rs : Resolver) : Prop :=
  forall (n : NsCap) (q : Query) (ks : Keyspace),
    all_of (derivable n) (rs n q ks) = true.

Definition AnswersOnlyTheAdmittedNamespace (rs : Resolver) : Prop :=
  forall (n : NsCap) (q : Query) (ks : Keyspace),
    admits n q = false -> rs n q ks = nil.

(* R-10-005b's "no index spans confidentiality domains", stated as the
   two-state agreement it is: two keyspaces agreeing on the cap's own domain
   answer alike, so nothing outside that domain reaches the answer. *)
Definition ObeysTheDomain (rs : Resolver) : Prop :=
  forall (n : NsCap) (q : Query) (ks1 ks2 : Keyspace),
    filter_of (in_domain (nc_domain n)) ks1
      = filter_of (in_domain (nc_domain n)) ks2 ->
    rs n q ks1 = rs n q ks2.

Theorem the_specification_mints_nothing : MintsNothing spec_resolve.
Proof.
  intros n q ks. unfold spec_resolve. destruct (admits n q); [ | reflexivity ].
  rewrite (all_of_map _ _ (derivable n) (grant n) (filter_of (selects q) ks)).
  apply all_of_const. intros e. unfold derivable. unfold grant. simpl.
  rewrite nat_eqb_refl. rewrite nat_eqb_refl. rewrite nat_leb_refl. reflexivity.
Qed.

Theorem the_specification_answers_only_the_admitted_namespace :
  AnswersOnlyTheAdmittedNamespace spec_resolve.
Proof. intros n q ks H. unfold spec_resolve. rewrite H. reflexivity. Qed.

Theorem the_specification_obeys_the_domain : ObeysTheDomain spec_resolve.
Proof.
  intros n q ks1 ks2 H. unfold spec_resolve.
  destruct (admits n q) eqn:Ea; [ | reflexivity ].
  assert (Hd : q_domain q = nc_domain n).
  { unfold admits in Ea. destruct (andb_split _ _ Ea) as [ A _ ].
    exact (nat_eqb_true _ _ A). }
  assert (Hsub : forall e : prod K2 nat,
            selects q e = true -> in_domain (nc_domain n) e = true).
  { intros e He. unfold selects in He. destruct (andb_split _ _ He) as [ A _ ].
    unfold in_domain. rewrite <- Hd. exact A. }
  rewrite (filter_refines _ (selects q) (in_domain (nc_domain n)) ks1 Hsub).
  rewrite (filter_refines _ (selects q) (in_domain (nc_domain n)) ks2 Hsub).
  rewrite H. reflexivity.
Qed.

(* --- The three constructions, one defect apiece. -------------------------- *)

(* R-10-005b's own words refused: an index that spans confidentiality
   domains, here a selection that drops the domain conjunct and keeps every
   other one. *)
Definition spanning_selects (q : Query) (e : prod K2 nat) : bool :=
  andb (Nat.eqb (k_space (fst e)) (q_space q))
  (andb (Nat.eqb (k_kind (fst e)) (q_kind q))
        (Nat.eqb (k_attr (fst e)) (q_attr q))).

Definition spanning_resolve : Resolver :=
  fun n q ks => if admits n q
                then map_over (grant n) (filter_of (spanning_selects q) ks)
                else nil.

(* R-12-024e's "mints nothing" refused: a resolution that hands back one
   right more than the caller presented. *)
Definition mint_grant (n : NsCap) (e : prod K2 nat) : ObjCap :=
  {| oc_domain := nc_domain n; oc_space := nc_space n;
     oc_object := k_object (fst e); oc_rights := S (nc_rights n) |}.

Definition mint_resolve : Resolver :=
  fun n q ks => if admits n q
                then map_over (mint_grant n) (filter_of (selects q) ks)
                else nil.

(* R-10-005b's admission check refused: a resolution that answers a query
   the presented capability does not admit, restricted all the same to the
   caller's own domain so that what refuses it is the missing check and not
   the reach. *)
Definition ambient_resolve : Resolver :=
  fun n q ks => map_over (grant n)
                  (filter_of (selects q) (filter_of (in_domain (nc_domain n)) ks)).

Theorem the_minting_resolver_is_refuted : ~ MintsNothing mint_resolve.
Proof.
  intros H.
  specialize (H {| nc_domain := 0; nc_space := 0; nc_rights := 0 |}
                {| q_domain := 0; q_space := 0; q_kind := k_inode; q_attr := 0 |}
                (cons (pair (mk_key 0 0 k_inode 1 0 0) 7) nil)).
  discriminate H.
Qed.

Theorem the_minting_resolver_keeps_every_other_obligation :
  AnswersOnlyTheAdmittedNamespace mint_resolve /\ ObeysTheDomain mint_resolve.
Proof.
  split.
  - intros n q ks H. unfold mint_resolve. rewrite H. reflexivity.
  - intros n q ks1 ks2 H. unfold mint_resolve.
    destruct (admits n q) eqn:Ea; [ | reflexivity ].
    assert (Hd : q_domain q = nc_domain n).
    { unfold admits in Ea. destruct (andb_split _ _ Ea) as [ A _ ].
      exact (nat_eqb_true _ _ A). }
    assert (Hsub : forall e : prod K2 nat,
              selects q e = true -> in_domain (nc_domain n) e = true).
    { intros e He. unfold selects in He. destruct (andb_split _ _ He) as [ A _ ].
      unfold in_domain. rewrite <- Hd. exact A. }
    rewrite (filter_refines _ (selects q) (in_domain (nc_domain n)) ks1 Hsub).
    rewrite (filter_refines _ (selects q) (in_domain (nc_domain n)) ks2 Hsub).
    rewrite H. reflexivity.
Qed.

Theorem the_ambient_resolver_is_refuted :
  ~ AnswersOnlyTheAdmittedNamespace ambient_resolve.
Proof.
  intros H.
  specialize (H {| nc_domain := 0; nc_space := 0; nc_rights := 0 |}
                {| q_domain := 0; q_space := 1; q_kind := k_inode; q_attr := 0 |}
                (cons (pair (mk_key 0 1 k_inode 1 0 0) 7) nil) eq_refl).
  discriminate H.
Qed.

Theorem the_ambient_resolver_keeps_every_other_obligation :
  MintsNothing ambient_resolve /\ ObeysTheDomain ambient_resolve.
Proof.
  split.
  - intros n q ks. unfold ambient_resolve.
    rewrite (all_of_map _ _ (derivable n) (grant n)
               (filter_of (selects q) (filter_of (in_domain (nc_domain n)) ks))).
    apply all_of_const. intros e. unfold derivable. unfold grant. simpl.
    rewrite nat_eqb_refl. rewrite nat_eqb_refl. rewrite nat_leb_refl. reflexivity.
  - intros n q ks1 ks2 H. unfold ambient_resolve. rewrite H. reflexivity.
Qed.

Theorem the_spanning_resolver_is_refuted : ~ ObeysTheDomain spanning_resolve.
Proof.
  intros H.
  specialize (H {| nc_domain := 0; nc_space := 0; nc_rights := 0 |}
                {| q_domain := 0; q_space := 0; q_kind := k_inode; q_attr := 0 |}
                nil (cons (pair (mk_key 1 0 k_inode 5 0 0) 7) nil) eq_refl).
  discriminate H.
Qed.

Theorem the_spanning_resolver_keeps_every_other_obligation :
  MintsNothing spanning_resolve /\ AnswersOnlyTheAdmittedNamespace spanning_resolve.
Proof.
  split.
  - intros n q ks. unfold spanning_resolve. destruct (admits n q); [ | reflexivity ].
    rewrite (all_of_map _ _ (derivable n) (grant n)
               (filter_of (spanning_selects q) ks)).
    apply all_of_const. intros e. unfold derivable. unfold grant. simpl.
    rewrite nat_eqb_refl. rewrite nat_eqb_refl. rewrite nat_leb_refl. reflexivity.
  - intros n q ks H. unfold spanning_resolve. rewrite H. reflexivity.
Qed.

(* The selection's own truth table, so that no conjunct of it is dead: an
   entry is selected exactly where all four components agree, and the
   spanning selection differs from it in exactly the domain column. *)
Definition demo_query : Query :=
  {| q_domain := 0; q_space := 0; q_kind := k_inode; q_attr := 4 |}.

Definition demo_selection_row : list (prod K2 nat) :=
  cons (pair (mk_key 0 0 k_inode 1 4 0) 10)
  (cons (pair (mk_key 1 0 k_inode 1 4 0) 11)
  (cons (pair (mk_key 0 1 k_inode 1 4 0) 12)
  (cons (pair (mk_key 0 0 k_dirent 1 4 0) 13)
  (cons (pair (mk_key 0 0 k_inode 1 5 0) 14) nil)))).

(* The row's own components, read back rather than left implicit: without
   this the row records only that its entries differ from the query and not
   in which component each of them differs, and a seeded change of the
   second entry's domain moves neither selection. *)
Example the_selection_row_declares :
  map_over (fun e => k_domain (fst e)) demo_selection_row
  = cons 0 (cons 1 (cons 0 (cons 0 (cons 0 nil))))
  /\ map_over (fun e => k_space (fst e)) demo_selection_row
  = cons 0 (cons 0 (cons 1 (cons 0 (cons 0 nil))))
  /\ map_over (fun e => k_kind (fst e)) demo_selection_row
  = cons 0 (cons 0 (cons 0 (cons 1 (cons 0 nil))))
  /\ map_over (fun e => k_object (fst e)) demo_selection_row
  = cons 1 (cons 1 (cons 1 (cons 1 (cons 1 nil))))
  /\ map_over (fun e => k_attr (fst e)) demo_selection_row
  = cons 4 (cons 4 (cons 4 (cons 4 (cons 5 nil))))
  /\ map_over (fun e => k_version (fst e)) demo_selection_row
  = cons 0 (cons 0 (cons 0 (cons 0 (cons 0 nil))))
  /\ map_over (fun e => snd e) demo_selection_row
  = cons 10 (cons 11 (cons 12 (cons 13 (cons 14 nil)))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl))))).

Example the_selection_reads_all_four_components :
  map_over (selects demo_query) demo_selection_row
  = cons true (cons false (cons false (cons false (cons false nil))))
  /\ map_over (spanning_selects demo_query) demo_selection_row
  = cons true (cons true (cons false (cons false (cons false nil)))) :=
  conj eq_refl eq_refl.

(* And admission reads both of its own, with the derivability check's rights
   comparison exercised *on* its boundary as well as either side of it: an
   equal-rights grant is derivable and one right more is not. *)
Example admission_reads_both_components :
  map_over (admits {| nc_domain := 0; nc_space := 0; nc_rights := 2 |})
    (cons {| q_domain := 0; q_space := 0; q_kind := k_inode; q_attr := 0 |}
    (cons {| q_domain := 1; q_space := 0; q_kind := k_inode; q_attr := 0 |}
    (cons {| q_domain := 0; q_space := 1; q_kind := k_inode; q_attr := 0 |} nil)))
  = cons true (cons false (cons false nil)) := eq_refl.

Example the_rights_comparison_is_exercised_on_its_boundary :
  map_over (fun r => derivable {| nc_domain := 0; nc_space := 0; nc_rights := 2 |}
                       {| oc_domain := 0; oc_space := 0; oc_object := 1;
                          oc_rights := r |})
           (upto 4)
  = cons true (cons true (cons true (cons false nil)))
  /\ derivable {| nc_domain := 0; nc_space := 0; nc_rights := 2 |}
       {| oc_domain := 1; oc_space := 0; oc_object := 1; oc_rights := 2 |} = false
  /\ derivable {| nc_domain := 0; nc_space := 0; nc_rights := 2 |}
       {| oc_domain := 0; oc_space := 1; oc_object := 1; oc_rights := 2 |} = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   R-10-005b's "no capability is written into a key", read as reading 12
   states it: the persisted keyspace is a function of what was written and
   never of the authority under which it was written.
   ========================================================================= *)

Definition Persister : Type := NsCap -> K2 -> nat -> Keyspace -> Keyspace.

Definition spec_persist : Persister := fun _ k v ks => ins l2_keys k v ks.

Definition WritesNoAuthority (pt : Persister) : Prop :=
  forall (n1 n2 : NsCap) (k : K2) (v : nat) (ks : Keyspace),
    pt n1 k v ks = pt n2 k v ks.

Theorem the_specification_writes_no_authority : WritesNoAuthority spec_persist.
Proof. intros n1 n2 k v ks. reflexivity. Qed.

(* The construction the same clause excludes: the presented capability's
   rights stamped into the key. Nothing about the write is wrong, and the
   defect is what a later read returns. *)
Definition stamped_persist : Persister :=
  fun n k v ks => ins l2_keys (at_attr (nc_rights n) k) v ks.

Theorem the_stamped_key_is_refuted : ~ WritesNoAuthority stamped_persist.
Proof.
  intros H.
  specialize (H {| nc_domain := 0; nc_space := 0; nc_rights := 2 |}
                {| nc_domain := 0; nc_space := 0; nc_rights := 1 |}
                (mk_key 0 0 k_inode 1 0 0) 7 nil).
  discriminate H.
Qed.

(* And the twin: what the stamping construction breaks is this obligation
   and not the index's own, the key it writes reading back exactly as
   JournalIndex.v's theorem says any key does. *)
Theorem the_stamped_key_still_reads_back :
  forall (n : NsCap) (k : K2) (v : nat) (ks : Keyspace),
    look l2_keys (at_attr (nc_rights n) k) (stamped_persist n k v ks) = Some v.
Proof.
  intros n k v ks. unfold stamped_persist.
  exact (the_key_just_written_reads_back l2_keys (at_attr (nc_rights n) k) v ks).
Qed.

(* R-10-037's own consequence, computed: a keyspace persisted under a
   capability that a revocation has since narrowed answers the *old* rights
   to whoever reads it back, which is a restore returning an authority the
   current epoch does not carry. *)
Example the_stamped_key_returns_the_retired_rights :
  map_over (fun e => k_attr (fst e))
    (stamped_persist {| nc_domain := 0; nc_space := 0; nc_rights := 2 |}
       (mk_key 0 0 k_inode 1 0 0) 7 nil)
  = cons 2 nil
  /\ map_over (fun e => k_attr (fst e))
       (spec_persist {| nc_domain := 0; nc_space := 0; nc_rights := 2 |}
          (mk_key 0 0 k_inode 1 0 0) 7 nil)
  = cons 0 nil := conj eq_refl eq_refl.

(* =========================================================================
   R-10-005b's "update atomically with the object and metadata in the same
   L0 transaction", stated over JournalIndex.v's own log.

   This is the half of the Require that is load-bearing rather than
   decorative: the transaction, the surviving prefix, the commit predicate
   and the crash points below are that file's, and the obligation here is
   what happens to *three* blocks under them.
   ========================================================================= *)

Record Batch : Type := {
  ba_object : nat;
  ba_meta : nat;
  ba_index : nat
}.

Definition rec3 (c : Composition) (t b v : nat) (cl : bool) : Rec :=
  {| rec_txn := t; rec_block := b; rec_value := v; rec_closes := cl;
     rec_len := granules c; rec_landed := granules c |}.

Definition Writer : Type := Composition -> Batch -> list Rec.

Definition spec_writer : Writer := fun c ba =>
  cons (rec3 c (batch_txn c) (object_block c) (ba_object ba) false)
  (cons (rec3 c (batch_txn c) (meta_block c) (ba_meta ba) false)
  (cons (rec3 c (batch_txn c) (index_block c) (ba_index ba) true) nil)).

(* The construction R-10-005b's own sentence excludes: the index update in a
   transaction of its own, which is what "in the same L0 transaction" is
   there to refuse. *)
Definition split_writer : Writer := fun c ba =>
  cons (rec3 c (batch_txn c) (object_block c) (ba_object ba) false)
  (cons (rec3 c (batch_txn c) (meta_block c) (ba_meta ba) true)
  (cons (rec3 c (S (batch_txn c)) (index_block c) (ba_index ba) true) nil)).

Definition OneTransaction (c : Composition) (wr : Writer) : Prop :=
  forall ba : Batch,
    all_of (fun r => Nat.eqb (rec_txn r) (batch_txn c)) (wr c ba) = true.

Theorem the_specification_writes_one_transaction :
  forall c : Composition, OneTransaction c spec_writer.
Proof.
  intros c ba. unfold spec_writer. simpl.
  rewrite nat_eqb_refl. reflexivity.
Qed.

(* The lemmas the all-or-nothing theorem rests on, each stated of an
   arbitrary journal rather than of the writer's own. *)
Lemma any_of_one_transaction :
  forall (t : nat) (p : list Rec) (cm : nat -> bool) (b : nat),
    all_of (fun r => Nat.eqb (rec_txn r) t) p = true ->
    any_of (fun r => andb (Nat.eqb (rec_block r) b) (cm (rec_txn r))) p
      = andb (cm t) (any_of (fun r => Nat.eqb (rec_block r) b) p).
Proof.
  intros t p. induction p as [ | r s IH ]; intros cm b H.
  - simpl. destruct (cm t); reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hr Hs ].
    simpl. rewrite (IH cm b Hs). rewrite (nat_eqb_true _ _ Hr).
    destruct (Nat.eqb (rec_block r) b); destruct (cm t);
      destruct (any_of (fun x => Nat.eqb (rec_block x) b) s); reflexivity.
Qed.

Lemma all_of_scan :
  forall (p : Rec -> bool) (j : list Rec),
    all_of p j = true -> all_of p (scan j) = true.
Proof.
  intros p j. induction j as [ | r t IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hr Ht ].
    simpl. destruct (intact r); [ simpl; rewrite Hr; exact (IH Ht) | reflexivity ].
Qed.

(* S: a journal carrying one transaction lands all of its blocks or none of
   them, at every crash point and of an arbitrary pair of blocks. This is
   R-10-005c's "index and objects are never observed mismatched" with the
   quantifier where the acceptance clause puts it. *)
Theorem one_transaction_lands_all_or_nothing :
  forall (t : nat) (j : list Rec) (b1 b2 : nat),
    all_of (fun r => Nat.eqb (rec_txn r) t) j = true ->
    any_of (fun r => Nat.eqb (rec_block r) b1) (scan j) = true ->
    any_of (fun r => Nat.eqb (rec_block r) b2) (scan j) = true ->
    touched j b1 = touched j b2.
Proof.
  intros t j b1 b2 H H1 H2.
  unfold touched. unfold touched_under. unfold writes_committed.
  rewrite (any_of_one_transaction t (scan j) (commits (scan j)) b1
             (all_of_scan _ j H)).
  rewrite (any_of_one_transaction t (scan j) (commits (scan j)) b2
             (all_of_scan _ j H)).
  rewrite H1. rewrite H2. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   R-10-005c's "index and objects are never observed mismatched" at the cuts
   where a mismatch is possible.

   The premise that both blocks are present in the surviving prefix would
   exclude every cut where the index has not landed, which is exactly where
   a mismatch could be seen; so the obligation below is the *disjunction*
   the entry's words carry, that at every cut either neither block is
   observed as updated or both are, stated over an arbitrary writer and an
   arbitrary cut. What gates it is a second property of the writer: the
   transaction is committed in a surviving prefix only where every block it
   names is in that prefix. A writer that closes its transaction before the
   index record has landed breaks that, and is refuted below.
   ------------------------------------------------------------------------- *)

Definition CommitsOnlyWithEveryBlock (c : Composition) (wr : Writer) : Prop :=
  forall (ba : Batch) (i : nat),
    commits (scan (take i (wr c ba))) (batch_txn c) = true ->
    andb (any_of (fun r => Nat.eqb (rec_block r) (object_block c))
                 (scan (take i (wr c ba))))
         (any_of (fun r => Nat.eqb (rec_block r) (index_block c))
                 (scan (take i (wr c ba)))) = true.

Definition NeverObservedApart (c : Composition) (wr : Writer) : Prop :=
  forall (ba : Batch) (i : nat),
    bool_eqb (touched (take i (wr c ba)) (object_block c))
             (touched (take i (wr c ba)) (index_block c)) = true.

Theorem the_object_and_the_index_are_never_observed_apart :
  forall (c : Composition) (wr : Writer),
    OneTransaction c wr -> CommitsOnlyWithEveryBlock c wr ->
    NeverObservedApart c wr.
Proof.
  intros c wr Hone Hall ba i.
  assert (Ht : all_of (fun r => Nat.eqb (rec_txn r) (batch_txn c))
                 (scan (take i (wr c ba))) = true)
    by exact (all_of_scan _ (take i (wr c ba))
                (all_of_take Rec _ i (wr c ba) (Hone ba))).
  unfold touched. unfold touched_under. unfold writes_committed.
  rewrite (any_of_one_transaction (batch_txn c) (scan (take i (wr c ba)))
             (commits (scan (take i (wr c ba)))) (object_block c) Ht).
  rewrite (any_of_one_transaction (batch_txn c) (scan (take i (wr c ba)))
             (commits (scan (take i (wr c ba)))) (index_block c) Ht).
  destruct (commits (scan (take i (wr c ba))) (batch_txn c)) eqn:E.
  - destruct (andb_split _ _ (Hall ba i E)) as [ A B ].
    rewrite A. rewrite B. reflexivity.
  - reflexivity.
Qed.

(* And a torn-free journal's own scan, so the specification's writer can be
   shown to meet the second premise by conversion at each of its four cuts
   rather than by a hypothesis about tearing. *)
Lemma rec3_is_intact :
  forall (c : Composition) (t b v : nat) (cl : bool), intact (rec3 c t b v cl) = true.
Proof.
  intros c t b v cl. unfold intact. simpl. exact (nat_eqb_refl (granules c)).
Qed.

Lemma the_specification_writer_is_intact :
  forall (c : Composition) (ba : Batch),
    all_of intact (spec_writer c ba) = true.
Proof.
  intros c ba. unfold spec_writer. simpl.
  rewrite (rec3_is_intact c (batch_txn c) (object_block c) (ba_object ba) false).
  rewrite (rec3_is_intact c (batch_txn c) (meta_block c) (ba_meta ba) false).
  rewrite (rec3_is_intact c (batch_txn c) (index_block c) (ba_index ba) true).
  reflexivity.
Qed.

(* A prefix carrying no closing record commits nothing, which is what makes
   the first two cuts of the specification's batch vacuous rather than
   argued. *)
Lemma commits_of_no_closing_record :
  forall (p : list Rec) (t : nat),
    all_of (fun r => negb (rec_closes r)) p = true -> commits p t = false.
Proof.
  intros p. induction p as [ | r s IH ]; intros t H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hr Hs ].
    unfold commits. simpl. rewrite (negb_true_elim _ Hr).
    destruct (Nat.eqb (rec_txn r) t); simpl; exact (IH t Hs).
Qed.

Theorem the_specification_writer_commits_only_with_every_block :
  forall c : Composition, CommitsOnlyWithEveryBlock c spec_writer.
Proof.
  intros c ba i H.
  assert (Hs : scan (take i (spec_writer c ba)) = take i (spec_writer c ba))
    by exact (scan_of_an_intact_journal (take i (spec_writer c ba))
                (all_of_take Rec intact i (spec_writer c ba)
                   (the_specification_writer_is_intact c ba))).
  rewrite Hs. rewrite Hs in H.
  destruct i as [ | [ | [ | k ] ] ].
  - discriminate H.
  - rewrite (commits_of_no_closing_record (take 1 (spec_writer c ba))
               (batch_txn c) eq_refl) in H. discriminate H.
  - rewrite (commits_of_no_closing_record (take 2 (spec_writer c ba))
               (batch_txn c) eq_refl) in H. discriminate H.
  - unfold spec_writer. simpl. apply andb_join.
    + rewrite (nat_eqb_refl (object_block c)). reflexivity.
    + rewrite (nat_eqb_refl (index_block c)).
      destruct (Nat.eqb (object_block c) (index_block c));
        destruct (Nat.eqb (meta_block c) (index_block c)); reflexivity.
Qed.

Theorem the_specification_writer_is_never_observed_apart :
  forall c : Composition, NeverObservedApart c spec_writer.
Proof.
  intros c.
  exact (the_object_and_the_index_are_never_observed_apart c spec_writer
           (the_specification_writes_one_transaction c)
           (the_specification_writer_commits_only_with_every_block c)).
Qed.

(* The writer that closes its transaction before the index record has
   landed: it carries one transaction, and at the cut where the closing
   record has landed and the index record has not, the object is observed
   updated and the index is not. That is the mismatch R-10-005c's
   acceptance clause names, and it is a defect of the *order* rather than of
   the transaction count, which is what makes it a second construction and
   not the split writer again. *)
Definition early_close_writer : Writer := fun c ba =>
  cons (rec3 c (batch_txn c) (object_block c) (ba_object ba) true)
  (cons (rec3 c (batch_txn c) (meta_block c) (ba_meta ba) false)
  (cons (rec3 c (batch_txn c) (index_block c) (ba_index ba) false) nil)).

Theorem the_early_close_writer_still_writes_one_transaction :
  forall c : Composition, OneTransaction c early_close_writer.
Proof.
  intros c ba. unfold early_close_writer. simpl.
  rewrite nat_eqb_refl. reflexivity.
Qed.

(* And the split writer breaks the premise rather than the conclusion, which
   is what makes it a refutation of the obligation and not of the theorem. *)
Lemma nat_eqb_succ_self : forall n : nat, Nat.eqb (S n) n = false.
Proof. intros n. induction n as [ | k IH ]; [ reflexivity | simpl; exact IH ]. Qed.

Theorem the_split_writer_is_refuted :
  forall c : Composition, ~ OneTransaction c split_writer.
Proof.
  intros c H. specialize (H {| ba_object := 0; ba_meta := 0; ba_index := 0 |}).
  destruct (andb_split _ _ H) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ H4 _ ].
  assert (Hc : Nat.eqb (S (batch_txn c)) (batch_txn c) = true) by exact H4.
  rewrite (nat_eqb_succ_self (batch_txn c)) in Hc. discriminate Hc.
Qed.

(* The twin: the split writer keeps every obligation JournalIndex.v states
   of a journal. Its records are intact, its two transactions each commit,
   and recovery lands every committed write; what it breaks is the clause
   that puts the three updates in *one* transaction, which is a different
   obligation from R-10-002's atomicity of a transaction. *)
Definition together (c : Composition) (j : list Rec) : bool :=
  bool_eqb (touched j (object_block c)) (touched j (index_block c)).

(* =========================================================================
   R-10-005c: the live query.
   ========================================================================= *)

(* The one closed enumeration, and R-10-005c is what closes it. The entry
   writes "ordered add/remove deltas", which names what a delta *is* rather
   than sampling what one might be, and a subscription to a query's result
   *set* has exactly two membership changes to report; and "overflow emits
   one rescan-required marker" names the overflow answer and its
   cardinality. No entry of this register names a third delta form. That is
   a stronger licence than R-10-005's kind list carries, which is why this
   is an inductive and a kind is a field. Gap g records that no entry states
   the order over them. *)
Inductive Delta : Type :=
| Added (k : K2)
| Removed (k : K2)
| Rescan.

Definition is_rescan (d : Delta) : bool :=
  match d with
  | Added _ => false
  | Removed _ => false
  | Rescan => true
  end.

Definition delta_eqb (a b : Delta) : bool :=
  match a, b with
  | Added x, Added y => k2_eqb x y
  | Removed x, Removed y => k2_eqb x y
  | Rescan, Rescan => true
  | _, _ => false
  end.

Definition Emitter : Type := nat -> list Delta -> list Delta.

(* Reading: the marker sits inside the declared bound rather than beside it
   (gap e), so an overflowing emission is the bound's first steps and then
   the one marker, and never one delta more than the bound admits. *)
Definition spec_emit : Emitter :=
  fun bound ds =>
    if Nat.leb (count_of ds) bound
    then ds
    else app (take (before_last bound) ds) (cons Rescan nil).

Definition BoundsTheQueue (em : Emitter) : Prop :=
  forall (bound : nat) (ds : list Delta),
    Nat.leb 1 bound = true -> Nat.leb (count_of (em bound ds)) bound = true.

Definition AtMostOneMarker (em : Emitter) : Prop :=
  forall (bound : nat) (ds : list Delta),
    all_of (fun d => negb (is_rescan d)) ds = true ->
    Nat.leb (count_of (filter_of is_rescan (em bound ds))) 1 = true.

Theorem the_specification_bounds_the_queue : BoundsTheQueue spec_emit.
Proof.
  intros bound ds Hb. destruct bound as [ | k ]; [ discriminate Hb | ].
  unfold spec_emit. destruct (Nat.leb (count_of ds) (S k)) eqn:E; [ exact E | ].
  rewrite (count_of_app_one Delta (take (before_last (S k)) ds) Rescan).
  simpl. exact (take_is_bounded Delta k ds).
Qed.

Theorem the_specification_emits_at_most_one_marker : AtMostOneMarker spec_emit.
Proof.
  intros bound ds H. unfold spec_emit.
  destruct (Nat.leb (count_of ds) bound).
  - rewrite (filter_of_none Delta is_rescan ds H). reflexivity.
  - rewrite (filter_of_app Delta is_rescan (take (before_last bound) ds)
               (cons Rescan nil)).
    rewrite (filter_of_none Delta is_rescan (take (before_last bound) ds)
               (all_of_take Delta _ (before_last bound) ds H)).
    reflexivity.
Qed.

(* The two constructions R-10-005c's own sentence excludes: one that buffers
   without bound, and one whose markers count the deltas it dropped, which
   publishes how many changes the domain committed. *)
Definition hoard_emit : Emitter := fun _ ds => ds.

Definition twin_marker_emit : Emitter :=
  fun bound ds =>
    if Nat.leb (count_of ds) bound
    then ds
    else app (take (before_last (before_last bound)) ds)
             (cons Rescan (cons Rescan nil)).

Theorem the_hoarding_emitter_is_refuted : ~ BoundsTheQueue hoard_emit.
Proof.
  intros H. specialize (H 1 (cons Rescan (cons Rescan nil)) eq_refl).
  discriminate H.
Qed.

Theorem the_hoarding_emitter_emits_no_marker_of_its_own :
  AtMostOneMarker hoard_emit.
Proof.
  intros bound ds H. unfold hoard_emit.
  rewrite (filter_of_none Delta is_rescan ds H). reflexivity.
Qed.

Theorem the_twin_marker_emitter_is_refuted : ~ AtMostOneMarker twin_marker_emit.
Proof.
  intros H.
  specialize (H 3 (cons (Added (mk_key 0 0 k_inode 1 0 0))
                  (cons (Added (mk_key 0 0 k_inode 2 0 0))
                  (cons (Added (mk_key 0 0 k_inode 3 0 0))
                  (cons (Added (mk_key 0 0 k_inode 4 0 0)) nil)))) eq_refl).
  discriminate H.
Qed.

(* The twin: what refuses the second emitter is the marker count and not the
   queue, its emission fitting the same declared bound the specification's
   does. Two obligations, and neither is the other stated twice. *)
Theorem the_twin_marker_emitter_still_bounds_the_queue :
  forall (bound : nat) (ds : list Delta),
    Nat.leb 2 bound = true ->
    Nat.leb (count_of (twin_marker_emit bound ds)) bound = true.
Proof.
  intros bound ds Hb. destruct bound as [ | k ]; [ discriminate Hb | ].
  destruct k as [ | j ]; [ discriminate Hb | ].
  unfold twin_marker_emit.
  destruct (Nat.leb (count_of ds) (S (S j))) eqn:E; [ exact E | ].
  rewrite (count_of_app_two Delta
             (take (before_last (before_last (S (S j)))) ds) Rescan Rescan).
  simpl. exact (take_is_bounded Delta j ds).
Qed.

(* R-10-005c's "rather than backpressuring commit", stated as the two-state
   agreement it is: what a commit does is not a function of how full the
   subscription's queue is. *)
Definition Committer : Type := nat -> Store -> Store.

Definition spec_commit (c : Composition) (ba : Batch) : Committer :=
  fun _ s => put s (object_block c) (ba_object ba).

Definition NeverBackpressuresTheCommit (cw : Committer) : Prop :=
  forall (o1 o2 : nat) (s : Store) (b : nat), cw o1 s b = cw o2 s b.

Theorem the_specification_never_backpressures_the_commit :
  forall (c : Composition) (ba : Batch),
    NeverBackpressuresTheCommit (spec_commit c ba).
Proof. intros c ba o1 o2 s b. reflexivity. Qed.

Definition backpressure_commit (c : Composition) (ba : Batch) : Committer :=
  fun o s => if Nat.leb (queue_bound c) o
             then s
             else put s (object_block c) (ba_object ba).

(* R-10-005c's "derived only after the committing L0 transaction", read off
   JournalIndex.v's own commit predicate over its own surviving prefix. *)
Definition Deriver : Type := list Rec -> list nat.

Definition spec_derive : Deriver :=
  fun j => filter_of (fun t => commits (scan j) t) (map_over rec_txn (scan j)).

Definition DerivesOnlyAfterTheCommit (dv : Deriver) : Prop :=
  forall j : list Rec, all_of (fun t => commits (scan j) t) (dv j) = true.

Theorem the_specification_derives_only_after_the_commit :
  DerivesOnlyAfterTheCommit spec_derive.
Proof.
  intros j. unfold spec_derive.
  exact (all_of_filter nat (fun t => commits (scan j) t) (map_over rec_txn (scan j))).
Qed.

(* The construction the same clause excludes: a deriver that reads the
   journal at prepare time, so an open transaction's changes leave the
   domain before the transaction that made them commits, and before a crash
   would have rolled them back. *)
Definition prepare_derive : Deriver := fun j => map_over rec_txn j.

(* Refuted on JournalIndex.v's own six-record journal, whose third
   transaction never commits. *)
Theorem the_prepare_time_deriver_is_refuted :
  ~ DerivesOnlyAfterTheCommit prepare_derive.
Proof. intros H. specialize (H demo_journal). discriminate H. Qed.

(* And the twin, computed rather than argued: the prepare-time deriver
   emits everything the specification emits and three transactions more,
   the third of them one no crash point ever commits. *)
Example the_prepare_time_deriver_emits_the_open_transaction :
  spec_derive demo_journal = cons 1 (cons 1 (cons 2 (cons 2 (cons 2 nil))))
  /\ prepare_derive demo_journal
     = cons 1 (cons 1 (cons 2 (cons 2 (cons 2 (cons 3 nil)))))
  /\ commits (scan demo_journal) 3 = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* R-10-005c's "a subscription is volatile and does not survive a crash, so
   recovery re-establishes it by rescan". *)
Definition Resumer : Type := list Delta -> list Delta.

Definition spec_resume : Resumer := fun _ => cons Rescan nil.

Definition SurvivesNoCrash (rs : Resumer) : Prop :=
  forall q : list Delta, rs q = cons Rescan nil.

Theorem the_specification_survives_no_crash : SurvivesNoCrash spec_resume.
Proof. intros q. reflexivity. Qed.

Definition replay_resume : Resumer := fun q => q.

Theorem the_replaying_resumer_is_refuted : ~ SurvivesNoCrash replay_resume.
Proof. intros H. specialize (H nil). discriminate H. Qed.

Theorem the_replaying_resumer_still_bounds_what_it_delivers :
  forall (bound : nat) (q : list Delta),
    Nat.leb (count_of q) bound = true ->
    Nat.leb (count_of (replay_resume q)) bound = true.
Proof. intros bound q H. exact H. Qed.

(* =========================================================================
   R-14-012a and R-08-001: a path is an app-local alias for a capability the
   manifest already placed in the graph, and there is no global directory
   for it to fall through to.
   ========================================================================= *)

Definition Aliases : Type := list (prod nat nat).

Definition Ambient : Type := nat -> option nat.

Definition PathResolver : Type := Aliases -> Ambient -> nat -> option nat.

Definition alias_look (al : Aliases) (n : nat) : option nat :=
  match filter_of (fun e => Nat.eqb (fst e) n) al with
  | nil => None
  | cons e _ => Some (snd e)
  end.

Definition spec_path : PathResolver := fun al _ n => alias_look al n.

(* The absence stated as a two-state agreement rather than as an absence:
   two ambient directories, one alias table, one answer. *)
Definition ReadsNoGlobalDirectory (pr : PathResolver) : Prop :=
  forall (al : Aliases) (g1 g2 : Ambient) (n : nat), pr al g1 n = pr al g2 n.

Theorem the_specification_reads_no_global_directory :
  ReadsNoGlobalDirectory spec_path.
Proof. intros al g1 g2 n. reflexivity. Qed.

(* R-14-012a's "namespace escape": a resolver that falls through to
   something the manifest did not place. *)
Definition escaping_path : PathResolver :=
  fun al gl n => match alias_look al n with
                 | Some o => Some o
                 | None => gl n
                 end.

Theorem the_escaping_resolver_is_refuted : ~ ReadsNoGlobalDirectory escaping_path.
Proof.
  intros H. specialize (H nil (fun _ => Some 1) (fun _ => None) 0). discriminate H.
Qed.

(* The twin: the escaping resolver answers every name the alias table
   carries exactly as the specification does, so what refuses it is the name
   the table does not carry and not a wrong answer to one it does. *)
Theorem the_escaping_resolver_agrees_on_every_declared_alias :
  forall (al : Aliases) (gl : Ambient) (n : nat) (o : nat),
    alias_look al n = Some o -> escaping_path al gl n = spec_path al gl n.
Proof.
  intros al gl n o H. unfold escaping_path. unfold spec_path. rewrite H. reflexivity.
Qed.

(* =========================================================================
   L3: the data-noninterference half (R-10-002's fourth layer, R-10-012,
   R-10-014 through R-10-018, R-10-022 through R-10-025, R-10-027, R-10-032,
   and R-08-021 through R-08-027a on what an observation is).

   Reading 5 and 6. The claim is stated of an arbitrary observer and an
   arbitrary authority set as a two-state agreement in R-05-156's own shape,
   and the AE half is not this file's: R-10-025 makes the property a
   composition of the scheme's IND-CCA/INT-CTXT with the filesystem's
   non-interference, so no ciphertext byte is modelled and the sealed form
   appears only through what the filesystem holds of it, a stored length, a
   nonce, and a keyed digest.
   ========================================================================= *)

Record Sealing : Type := {
  (* R-10-022's per-confidentiality-domain volume key, resident only in the
     crypto core; what the filesystem holds of it is which key an extent is
     under and never the key material. *)
  se_key : nat -> nat;
  (* R-10-015's dedup key, domain-separated by KDF from the volume key. *)
  se_dedup_key : nat -> nat;
  (* R-10-022's per-extent nonce. The second argument is the plaintext a
     convergent construction would read and the specification does not
     (reading 9). *)
  se_nonce : nat -> nat -> nat;
  (* The stored length. The first argument is the plaintext a compressing
     construction would read and R-10-018 removes (reading 8). *)
  se_stored : nat -> nat -> nat;
  (* R-10-015's keyed plaintext digest, computed in the core and handed over
     as an opaque tag. *)
  se_digest : nat -> nat -> nat
}.

(* One field replaced and every other kept, so that a refuting sealing
   differs from the specification in exactly the place its defect is. *)
Definition with_key (s : Sealing) (f : nat -> nat) : Sealing :=
  {| se_key := f; se_dedup_key := se_dedup_key s; se_nonce := se_nonce s;
     se_stored := se_stored s; se_digest := se_digest s |}.

Definition with_nonce (s : Sealing) (f : nat -> nat -> nat) : Sealing :=
  {| se_key := se_key s; se_dedup_key := se_dedup_key s; se_nonce := f;
     se_stored := se_stored s; se_digest := se_digest s |}.

Definition with_stored (s : Sealing) (f : nat -> nat -> nat) : Sealing :=
  {| se_key := se_key s; se_dedup_key := se_dedup_key s; se_nonce := se_nonce s;
     se_stored := f; se_digest := se_digest s |}.

Definition with_digest (s : Sealing) (f : nat -> nat -> nat) : Sealing :=
  {| se_key := se_key s; se_dedup_key := se_dedup_key s; se_nonce := se_nonce s;
     se_stored := se_stored s; se_digest := f |}.

Record Ext : Type := {
  ex_present : bool;
  ex_domain : nat;
  ex_len : nat;
  ex_plain : nat
}.

Definition Volume : Type := nat -> Ext.

Record Obs : Type := {
  ob_present : bool;
  ob_domain : nat;
  ob_stored : nat;
  ob_nonce : nat;
  ob_plain : option nat;
  ob_digest : option nat
}.

Definition obs_eqb (a b : Obs) : bool :=
  andb (bool_eqb (ob_present a) (ob_present b))
  (andb (Nat.eqb (ob_domain a) (ob_domain b))
  (andb (Nat.eqb (ob_stored a) (ob_stored b))
  (andb (Nat.eqb (ob_nonce a) (ob_nonce b))
  (andb (opt_eqb (ob_plain a) (ob_plain b))
        (opt_eqb (ob_digest a) (ob_digest b)))))).

Lemma obs_eqb_intro :
  forall o p : Obs,
    ob_present o = ob_present p -> ob_domain o = ob_domain p ->
    ob_stored o = ob_stored p -> ob_nonce o = ob_nonce p ->
    ob_plain o = ob_plain p -> ob_digest o = ob_digest p ->
    obs_eqb o p = true.
Proof.
  intros o p H1 H2 H3 H4 H5 H6. unfold obs_eqb.
  rewrite H1. rewrite H2. rewrite H3. rewrite H4. rewrite H5. rewrite H6.
  rewrite (bool_eqb_refl (ob_present p)). rewrite (nat_eqb_refl (ob_domain p)).
  rewrite (nat_eqb_refl (ob_stored p)). rewrite (nat_eqb_refl (ob_nonce p)).
  rewrite (opt_eqb_refl (ob_plain p)). rewrite (opt_eqb_refl (ob_digest p)).
  reflexivity.
Qed.

(* What an observer holds is a key and not a label (reading 5): whether it
   opens an extent is decided by whether some domain it is authorised for is
   under the same key. *)
Definition holds_key (c : Composition) (s : Sealing) (a : nat -> bool)
                     (k : nat) : bool :=
  any_of (fun d => andb (a d) (Nat.eqb (se_key s d) k)) (upto (domain_count c)).

Definition Observer : Type :=
  Composition -> Sealing -> (nat -> bool) -> Volume -> nat -> Obs.

Definition spec_obs : Observer :=
  fun c s a v i =>
    {| ob_present := ex_present (v i);
       ob_domain := ex_domain (v i);
       ob_stored := se_stored s (ex_plain (v i)) (ex_len (v i));
       ob_nonce := se_nonce s i (ex_plain (v i));
       ob_plain := if holds_key c s a (se_key s (ex_domain (v i)))
                   then Some (ex_plain (v i)) else None;
       ob_digest := if holds_key c s a (se_key s (ex_domain (v i)))
                    then Some (se_digest s (se_dedup_key s (ex_domain (v i)))
                                 (ex_plain (v i)))
                    else None |}.

(* Reading 7 and gaps b, c and d. Two extents an observer is not authorised
   for are equated where they agree on presence, domain and declared
   plaintext length: no entry of this register admits or denies that any of
   the three is public, so the weakest reading is taken and the theorem says
   nothing about hiding them. *)
Definition ext_agrees (a : nat -> bool) (e f : Ext) : bool :=
  if a (ex_domain e)
  then andb (bool_eqb (ex_present e) (ex_present f))
       (andb (Nat.eqb (ex_domain e) (ex_domain f))
       (andb (Nat.eqb (ex_len e) (ex_len f))
             (Nat.eqb (ex_plain e) (ex_plain f))))
  else andb (bool_eqb (ex_present e) (ex_present f))
       (andb (Nat.eqb (ex_domain e) (ex_domain f))
             (Nat.eqb (ex_len e) (ex_len f))).

Definition agree_at (c : Composition) (a : nat -> bool) (v w : Volume) : bool :=
  all_of (fun i => ext_agrees a (v i) (w i)) (upto (extent_count c)).

Lemma ext_agrees_shape :
  forall (a : nat -> bool) (e f : Ext),
    ext_agrees a e f = true ->
    ex_present e = ex_present f /\ ex_domain e = ex_domain f /\ ex_len e = ex_len f.
Proof.
  intros a e f H. unfold ext_agrees in H. destruct (a (ex_domain e)).
  - destruct (andb_split _ _ H) as [ A B ].
    destruct (andb_split _ _ B) as [ C D ].
    destruct (andb_split _ _ D) as [ E _ ].
    split; [ exact (bool_eqb_true _ _ A) | ].
    split; [ exact (nat_eqb_true _ _ C) | exact (nat_eqb_true _ _ E) ].
  - destruct (andb_split _ _ H) as [ A B ].
    destruct (andb_split _ _ B) as [ C D ].
    split; [ exact (bool_eqb_true _ _ A) | ].
    split; [ exact (nat_eqb_true _ _ C) | exact (nat_eqb_true _ _ D) ].
Qed.

Lemma ext_agrees_content :
  forall (a : nat -> bool) (e f : Ext),
    ext_agrees a e f = true -> a (ex_domain e) = true -> ex_plain e = ex_plain f.
Proof.
  intros a e f H Ha. unfold ext_agrees in H. rewrite Ha in H.
  destruct (andb_split _ _ H) as [ _ B ].
  destruct (andb_split _ _ B) as [ _ D ].
  destruct (andb_split _ _ D) as [ _ F ].
  exact (nat_eqb_true _ _ F).
Qed.

(* A volume whose extents name domains the composition enumerates. It is a
   well-formedness condition on the volume and not on the sealing, and it is
   a premise of the obligation rather than of the specification, so a
   refuting construction is held to the same domain roster the
   specification is. *)
Definition domains_in_range (c : Composition) (v : Volume) : Prop :=
  forall i : nat, mem_of (ex_domain (v i)) (upto (domain_count c)) = true.

(* The obligation, of an arbitrary observer, an arbitrary authority set and
   an arbitrary pair of volumes. *)
Definition Noninterferent (c : Composition) (s : Sealing) (ob : Observer) : Prop :=
  forall (a : nat -> bool) (v w : Volume) (i : nat),
    domains_in_range c v ->
    mem_of i (upto (extent_count c)) = true ->
    agree_at c a v w = true ->
    obs_eqb (ob c s a v i) (ob c s a w i) = true.

(* The three obligations on the sealing the statement rests on, each stated
   apart because a construction below breaks one apiece. *)
Definition LengthHidesTheContent (s : Sealing) : Prop :=
  forall p q l : nat, se_stored s p l = se_stored s q l.

Definition NonceIsPerExtent (s : Sealing) : Prop :=
  forall i p q : nat, se_nonce s i p = se_nonce s i q.

Definition keys_separated (c : Composition) (s : Sealing) : bool :=
  all_of (fun d => all_of (fun e =>
            only_if (Nat.eqb (se_key s d) (se_key s e)) (Nat.eqb d e))
          (upto (domain_count c))) (upto (domain_count c)).

Lemma separated_keys_are_injective :
  forall (c : Composition) (s : Sealing) (d e : nat),
    keys_separated c s = true ->
    mem_of d (upto (domain_count c)) = true ->
    mem_of e (upto (domain_count c)) = true ->
    Nat.eqb (se_key s d) (se_key s e) = true -> d = e.
Proof.
  intros c s d e H Hd He Hk.
  assert (Hr := all_of_elim _ _ d H Hd).
  assert (Hx := all_of_elim _ _ e Hr He).
  exact (nat_eqb_true d e (only_if_elim _ _ Hx Hk)).
Qed.

(* R-10-022's per-domain keying, read from the observer's side: a separated
   key opens exactly the domain it belongs to and nothing beside it. *)
Lemma the_key_opens_exactly_its_own_domain :
  forall (c : Composition) (s : Sealing) (a : nat -> bool) (d : nat),
    keys_separated c s = true ->
    mem_of d (upto (domain_count c)) = true ->
    holds_key c s a (se_key s d) = a d.
Proof.
  intros c s a d Hs Hd. unfold holds_key. destruct (a d) eqn:Ead.
  - apply (any_of_intro _ _ d Hd). rewrite Ead. rewrite nat_eqb_refl. reflexivity.
  - apply any_of_false. apply all_of_intro. intros e He.
    destruct (a e) eqn:Eae; [ | reflexivity ].
    destruct (Nat.eqb (se_key s e) (se_key s d)) eqn:Ek; [ | reflexivity ].
    rewrite (separated_keys_are_injective c s e d Hs He Hd Ek) in Eae.
    rewrite Eae in Ead. discriminate Ead.
Qed.

(* S: the specification's observation is non-interferent, of an arbitrary
   observer set, an arbitrary authority set, and an arbitrary pair of
   volumes agreeing on everything that authority set covers. *)
Theorem the_specification_is_noninterferent :
  forall (c : Composition) (s : Sealing) (a : nat -> bool) (v w : Volume) (i : nat),
    keys_separated c s = true ->
    LengthHidesTheContent s ->
    NonceIsPerExtent s ->
    domains_in_range c v ->
    mem_of i (upto (extent_count c)) = true ->
    agree_at c a v w = true ->
    obs_eqb (spec_obs c s a v i) (spec_obs c s a w i) = true.
Proof.
  intros c s a v w i Hk Hl Hn Hdr Hi Ha.
  assert (He : ext_agrees a (v i) (w i) = true)
    by exact (all_of_elim (fun j => ext_agrees a (v j) (w j))
                (upto (extent_count c)) i Ha Hi).
  destruct (ext_agrees_shape a (v i) (w i) He) as [ Hp [ Hd Hln ] ].
  assert (Hkv : holds_key c s a (se_key s (ex_domain (v i))) = a (ex_domain (v i)))
    by exact (the_key_opens_exactly_its_own_domain c s a (ex_domain (v i)) Hk (Hdr i)).
  assert (Hkw : holds_key c s a (se_key s (ex_domain (w i))) = a (ex_domain (v i))).
  { rewrite <- Hd. exact Hkv. }
  apply obs_eqb_intro; unfold spec_obs; simpl.
  - exact Hp.
  - exact Hd.
  - rewrite Hln. exact (Hl (ex_plain (v i)) (ex_plain (w i)) (ex_len (w i))).
  - exact (Hn i (ex_plain (v i)) (ex_plain (w i))).
  - rewrite Hkv. rewrite Hkw. destruct (a (ex_domain (v i))) eqn:Ea.
    + rewrite (ext_agrees_content a (v i) (w i) He Ea). reflexivity.
    + reflexivity.
  - rewrite Hkv. rewrite Hkw. destruct (a (ex_domain (v i))) eqn:Ea.
    + rewrite (ext_agrees_content a (v i) (w i) He Ea). rewrite Hd. reflexivity.
    + reflexivity.
Qed.

Corollary the_specification_meets_the_obligation :
  forall (c : Composition) (s : Sealing),
    keys_separated c s = true ->
    LengthHidesTheContent s ->
    NonceIsPerExtent s ->
    Noninterferent c s spec_obs.
Proof.
  intros c s Hk Hl Hn a v w i Hdr Hi Ha.
  exact (the_specification_is_noninterferent c s a v w i Hk Hl Hn Hdr Hi Ha).
Qed.

(* The two bounded readings of the same two hypotheses, so that a
   composition's own witness is a conversion rather than a proof, and so
   that the independence table below can be computed. *)
Definition length_hides_at (c : Composition) (s : Sealing) : bool :=
  all_of (fun p => all_of (fun q => all_of (fun l =>
            Nat.eqb (se_stored s p l) (se_stored s q l)) (upto (plain_span c)))
          (upto (plain_span c))) (upto (plain_span c)).

Definition nonce_per_extent_at (c : Composition) (s : Sealing) : bool :=
  all_of (fun i => all_of (fun p => all_of (fun q =>
            Nat.eqb (se_nonce s i p) (se_nonce s i q)) (upto (plain_span c)))
          (upto (plain_span c))) (upto (extent_count c)).

(* R-10-016's cross-domain incomparability, as the bounded check a
   composition can decide: no plaintext of one domain shares a keyed digest
   with any plaintext of another. *)
Definition dedup_separated (c : Composition) (s : Sealing) : bool :=
  all_of (fun d => all_of (fun e => all_of (fun p => all_of (fun q =>
            only_if (negb (Nat.eqb d e))
                    (negb (Nat.eqb (se_digest s (se_dedup_key s d) p)
                                   (se_digest s (se_dedup_key s e) q))))
          (upto (plain_span c))) (upto (plain_span c)))
          (upto (domain_count c))) (upto (domain_count c)).

(* R-10-015's "domain-separated by KDF from the volume key", as the same
   kind of bounded check: the dedup key of a domain is never that domain's
   volume key. *)
Definition dedup_key_is_its_own (c : Composition) (s : Sealing) : bool :=
  all_of (fun d => negb (Nat.eqb (se_dedup_key s d) (se_key s d)))
         (upto (domain_count c)).

(* R-10-016's acceptance clause, extracted from the bounded check: the same
   plaintext in two domains does not present the same digest, so a
   confirmation-of-file oracle across domains has nothing to compare. *)
Theorem no_cross_domain_confirmation_of_file :
  forall (c : Composition) (s : Sealing) (d e p : nat),
    dedup_separated c s = true ->
    mem_of d (upto (domain_count c)) = true ->
    mem_of e (upto (domain_count c)) = true ->
    mem_of p (upto (plain_span c)) = true ->
    Nat.eqb d e = false ->
    Nat.eqb (se_digest s (se_dedup_key s d) p)
            (se_digest s (se_dedup_key s e) p) = false.
Proof.
  intros c s d e p H Hd He Hp Hde.
  assert (H1 := all_of_elim _ _ d H Hd).
  assert (H2 := all_of_elim _ _ e H1 He).
  assert (H3 := all_of_elim _ _ p H2 Hp).
  assert (H4 := all_of_elim _ _ p H3 Hp).
  rewrite Hde in H4. simpl in H4.
  exact (negb_true_elim _ (only_if_elim _ _ H4 eq_refl)).
Qed.

(* =========================================================================
   R-10-014, R-10-032 and R-09-022: crypto-erase, and the two constructions
   that are not one.

   Reading 10. A key is recoverable if it is still resident in the crypto
   core, or if the sealing root still opens its wrapped blob. R-10-014
   destroys the root and R-10-032 zeroizes residency, and the two are stated
   apart because R-10-032's lock is not an erase.
   ========================================================================= *)

Record Keyring : Type := {
  kr_root_live : bool;
  kr_resident : nat -> bool;
  kr_blob : nat -> bool
}.

Definition recoverable (kr : Keyring) (d : nat) : bool :=
  orb (kr_resident kr d) (andb (kr_root_live kr) (kr_blob kr d)).

Definition Eraser : Type := Keyring -> Keyring.

Definition spec_erase : Eraser := fun kr =>
  {| kr_root_live := false; kr_resident := fun _ => false; kr_blob := kr_blob kr |}.

Definition LeavesNoKeyRecoverable (er : Eraser) : Prop :=
  forall (kr : Keyring) (d : nat), recoverable (er kr) d = false.

Definition NoKeyIsResident (er : Eraser) : Prop :=
  forall (kr : Keyring) (d : nat), kr_resident (er kr) d = false.

Definition NoBlobSurvives (er : Eraser) : Prop :=
  forall (kr : Keyring) (d : nat), kr_blob (er kr) d = false.

Theorem the_specification_leaves_no_key_recoverable :
  LeavesNoKeyRecoverable spec_erase.
Proof. intros kr d. reflexivity. Qed.

(* R-10-014's own words refused: a bulk overwrite of the wrapped blobs,
   which is the mechanism that entry declines by name. *)
Definition overwrite_erase : Eraser := fun kr =>
  {| kr_root_live := kr_root_live kr; kr_resident := kr_resident kr;
     kr_blob := fun _ => false |}.

(* R-10-032's lock, which zeroizes the core's residency and leaves the
   sealing root standing. It is a different obligation and not this one. *)
Definition lock_erase : Eraser := fun kr =>
  {| kr_root_live := kr_root_live kr; kr_resident := fun _ => false;
     kr_blob := kr_blob kr |}.

(* And the root destroyed with the After-First-Unlock copy forgotten. *)
Definition root_erase : Eraser := fun kr =>
  {| kr_root_live := false; kr_resident := kr_resident kr;
     kr_blob := kr_blob kr |}.

Theorem the_overwrite_erase_is_refuted : ~ LeavesNoKeyRecoverable overwrite_erase.
Proof.
  intros H.
  specialize (H {| kr_root_live := true; kr_resident := fun _ => true;
                   kr_blob := fun _ => true |} 0).
  discriminate H.
Qed.

Theorem the_overwrite_erase_still_removes_every_blob :
  NoBlobSurvives overwrite_erase.
Proof. intros kr d. reflexivity. Qed.

Theorem the_lock_is_refuted_as_an_erase : ~ LeavesNoKeyRecoverable lock_erase.
Proof.
  intros H.
  specialize (H {| kr_root_live := true; kr_resident := fun _ => false;
                   kr_blob := fun _ => true |} 0).
  discriminate H.
Qed.

Theorem the_lock_still_leaves_no_key_resident : NoKeyIsResident lock_erase.
Proof. intros kr d. reflexivity. Qed.

Theorem the_root_erase_is_refuted : ~ LeavesNoKeyRecoverable root_erase.
Proof.
  intros H.
  specialize (H {| kr_root_live := true; kr_resident := fun _ => true;
                   kr_blob := fun _ => false |} 0).
  discriminate H.
Qed.

Theorem the_root_erase_still_kills_the_sealing_root :
  forall kr : Keyring, kr_root_live (root_erase kr) = false.
Proof. intros kr. reflexivity. Qed.

(* The whole keyring state space, generated rather than authored: three
   independent bits are eight states and every one of them is decided. *)
Definition keyring_of (rt rs bl : bool) : Keyring :=
  {| kr_root_live := rt; kr_resident := fun _ => rs; kr_blob := fun _ => bl |}.

Definition all_keyrings : list Keyring :=
  cons (keyring_of false false false) (cons (keyring_of false false true)
  (cons (keyring_of false true false) (cons (keyring_of false true true)
  (cons (keyring_of true false false) (cons (keyring_of true false true)
  (cons (keyring_of true true false) (cons (keyring_of true true true)
  nil))))))).

Example there_are_eight_keyring_states : count_of all_keyrings = 8 := eq_refl.

(* And the eight are the whole product of the three bits and not eight states
   that happen to answer the tables below: each bit is read back in the
   enumeration's own order, so a state that shares its recoverability with a
   neighbour is still pinned to be the state it is. *)
Example the_eight_keyring_states_are_the_whole_product :
  map_over kr_root_live all_keyrings
  = cons false (cons false (cons false (cons false (cons true (cons true
    (cons true (cons true nil)))))))
  /\ map_over (fun kr => kr_resident kr 0) all_keyrings
  = cons false (cons false (cons true (cons true (cons false (cons false
    (cons true (cons true nil)))))))
  /\ map_over (fun kr => kr_blob kr 0) all_keyrings
  = cons false (cons true (cons false (cons true (cons false (cons true
    (cons false (cons true nil))))))) :=
  conj eq_refl (conj eq_refl eq_refl).

Example recoverability_reads_all_three_bits :
  map_over (fun kr => recoverable kr 0) all_keyrings
  = cons false (cons false (cons true (cons true (cons false (cons true
    (cons true (cons true nil))))))) := eq_refl.

Example which_eraser_leaves_which_state_recoverable :
  map_over (fun kr => recoverable (spec_erase kr) 0) all_keyrings
  = cons false (cons false (cons false (cons false (cons false (cons false
    (cons false (cons false nil)))))))
  /\ map_over (fun kr => recoverable (overwrite_erase kr) 0) all_keyrings
  = cons false (cons false (cons true (cons true (cons false (cons false
    (cons true (cons true nil)))))))
  /\ map_over (fun kr => recoverable (lock_erase kr) 0) all_keyrings
  = cons false (cons false (cons false (cons false (cons false (cons true
    (cons false (cons true nil)))))))
  /\ map_over (fun kr => recoverable (root_erase kr) 0) all_keyrings
  = cons false (cons false (cons true (cons true (cons false (cons false
    (cons true (cons true nil)))))))
  := conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Theorem every_keyring_state_is_erased :
  forall kr : Keyring, all_of (fun d => negb (recoverable (spec_erase kr) d))
                              (upto 8) = true.
Proof.
  intros kr. apply all_of_intro. intros d _. reflexivity.
Qed.

(* =========================================================================
   R-10-013b's third asset class: durable component state, declared `Fresh`
   and carried by a freshness epoch (R-10-013c, R-10-013e, R-10-035).

   Reading 14. R-10-011 surrenders freshness for the mutable user-data
   volume and R-10-013b says in as many words that the split is three-way,
   so the class R-10-035 lands in this keyspace is freshness-*protected*
   rather than surrendered. The storage side of it is four obligations: the
   epoch root reads the version of every declared `Fresh` region and of
   nothing else; a `Fresh` write is acknowledged at the seal and never at
   the data commit; an epoch that does not seal loses its writes rather than
   presenting them as fresh; and a region whose version does not verify
   against the sealed root is refused rather than returned. The counter that
   advances at the seal is R-10-013's and is RotFirmware.v's, and the root's
   computation is the crypto core's; what is here is which versions reach it
   and what a reader does either side of the boundary.
   ========================================================================= *)

(* A region is a finite index below the count a composition declares, the
   same idiom a kind and a domain take: R-10-013d makes the declaration per
   compartment and prices it at admission, so nothing here fixes how many
   there are or which of them are `Fresh`. *)
Definition Versions : Type := nat -> nat.

Definition Declaration : Type := nat -> bool.

Definition EpochRoot : Type := Declaration -> Versions -> nat.

Fixpoint sum_over (f : nat -> nat) (l : list nat) : nat :=
  match l with nil => 0 | cons x r => Nat.add (f x) (sum_over f r) end.

Lemma sum_over_agree :
  forall (f g : nat -> nat) (l : list nat),
    all_of (fun x => Nat.eqb (f x) (g x)) l = true -> sum_over f l = sum_over g l.
Proof.
  intros f g l. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split _ _ H) as [ Hx Hr ].
    simpl. rewrite (nat_eqb_true _ _ Hx). rewrite (IH Hr). reflexivity.
Qed.

(* R-10-013c's "one root over the version of every `Fresh` region". The sum
   is a witness for a function of exactly those versions and carries no
   claim about what the crypto core computes; what the obligations read is
   which versions reach the root, never which function it is. *)
Definition spec_epoch_root (c : Composition) : EpochRoot :=
  fun d v => sum_over (fun r => if d r then v r else 0) (upto (region_count c)).

(* The first half, stated as the two-state agreement it is: two version maps
   agreeing on every declared region seal the same root, so nothing outside
   the declared class reaches it and no epoch seals over state admission
   never priced. *)
Definition ReadsOnlyDeclaredVersions (c : Composition) (er : EpochRoot) : Prop :=
  forall (d : Declaration) (v w : Versions),
    all_of (fun r => only_if (d r) (Nat.eqb (v r) (w r)))
           (upto (region_count c)) = true ->
    er d v = er d w.

(* The one step of it, over the declaration bit as a variable: a region the
   manifest declares contributes its version and one it does not
   contributes nothing, so two version maps agreeing on the declared half
   contribute alike at every region. *)
Lemma declared_versions_agree :
  forall (b : bool) (a c : nat),
    only_if b (Nat.eqb a c) = true ->
    Nat.eqb (if b then a else 0) (if b then c else 0) = true.
Proof.
  intros b a c H. destruct b; [ simpl in H; exact H | exact (nat_eqb_refl 0) ].
Qed.

Theorem the_specification_epoch_root_reads_only_declared_versions :
  forall c : Composition, ReadsOnlyDeclaredVersions c (spec_epoch_root c).
Proof.
  intros c d v w H. unfold spec_epoch_root. apply sum_over_agree.
  apply all_of_intro. intros r Hr.
  exact (declared_versions_agree (d r) (v r) (w r) (all_of_elim _ _ r H Hr)).
Qed.

(* The second half, as the bounded check a composition can decide: the root
   moves when any declared region's version moves, so a `Fresh` write is
   covered by the epoch that seals over it rather than left outside it. *)
Definition bump_at (r : nat) (v : Versions) : Versions :=
  fun x => if Nat.eqb r x then S (v x) else v x.

Definition moves_with_every_declared_region (c : Composition) (d : Declaration)
                                            (v : Versions) (er : EpochRoot) : bool :=
  all_of (fun r => only_if (d r) (negb (Nat.eqb (er d v) (er d (bump_at r v)))))
         (upto (region_count c)).

(* The two constructions the entry's own sentence excludes, one half apiece.
   The first seals over a region the manifest did not declare, which is an
   epoch spent on state R-10-013d's admission never priced; the second seals
   over one declared region alone, so a `Fresh` write to any other is
   acknowledged by an epoch that does not cover it. *)
Definition nosy_epoch_root (c : Composition) : EpochRoot :=
  fun _ v => sum_over v (upto (region_count c)).

Definition partial_epoch_root : EpochRoot := fun d v => if d 0 then v 0 else 0.

(* -------------------------------------------------------------------------
   The epoch boundary itself: whether the data commit that carried a write
   has landed, and whether the RoT has sealed the root over it. The two are
   independent bits, and the four states are enumerated rather than sampled.
   ------------------------------------------------------------------------- *)

Record Epoch : Type := {
  ep_committed : bool;
  ep_sealed : bool
}.

Definition all_epochs : list Epoch :=
  cons {| ep_committed := false; ep_sealed := false |}
  (cons {| ep_committed := false; ep_sealed := true |}
  (cons {| ep_committed := true; ep_sealed := false |}
  (cons {| ep_committed := true; ep_sealed := true |} nil))).

Example the_epoch_states_are_the_whole_product :
  count_of all_epochs = 4
  /\ map_over ep_committed all_epochs
     = cons false (cons false (cons true (cons true nil)))
  /\ map_over ep_sealed all_epochs
     = cons false (cons true (cons false (cons true nil))) :=
  conj eq_refl (conj eq_refl eq_refl).

Definition Acknowledger : Type := Epoch -> bool.

Definition spec_ack : Acknowledger := fun e => ep_sealed e.

(* R-10-013c: "a `Fresh` write is acknowledged when its epoch seals". *)
Definition AcknowledgesOnlyAtTheSeal (ak : Acknowledger) : Prop :=
  forall e : Epoch, ep_sealed e = false -> ak e = false.

Theorem the_specification_acknowledges_only_at_the_seal :
  AcknowledgesOnlyAtTheSeal spec_ack.
Proof. intros e H. exact H. Qed.

(* The construction the same sentence excludes, and it is RotFirmware.v's own
   commit-advancing twin read from the storage side: the write is
   acknowledged when its data commit lands, so an epoch that never seals has
   already been reported fresh and the counter is asked to advance at
   commit frequency, which is R-10-011's objection. *)
Definition commit_ack : Acknowledger := fun e => orb (ep_sealed e) (ep_committed e).

Theorem the_commit_acknowledger_is_refuted : ~ AcknowledgesOnlyAtTheSeal commit_ack.
Proof.
  intros H. specialize (H {| ep_committed := true; ep_sealed := false |} eq_refl).
  discriminate H.
Qed.

(* The twin: it acknowledges every epoch the specification acknowledges, so
   what refuses it is the window it opens before the seal and never a write
   it loses. *)
Theorem the_commit_acknowledger_acknowledges_every_sealed_epoch :
  forall e : Epoch, spec_ack e = true -> commit_ack e = true.
Proof.
  intros e H. unfold spec_ack in H. unfold commit_ack. rewrite H. reflexivity.
Qed.

(* R-10-013c's last clause and R-10-013e together: a `Fresh` region is
   returned only where its epoch sealed and its version verifies against
   that sealed root. The verification is the crypto core's, so it enters as
   a boolean the reader is handed rather than as a computation here. *)
Definition FreshReader : Type := Epoch -> bool -> nat -> option nat.

Definition spec_fresh_read : FreshReader :=
  fun e ok x => if andb (ep_sealed e) ok then Some x else None.

Definition RefusesWhatItCannotProveFresh (rd : FreshReader) : Prop :=
  forall (e : Epoch) (ok : bool) (x : nat),
    andb (ep_sealed e) ok = false -> rd e ok x = None.

Theorem the_specification_refuses_what_it_cannot_prove_fresh :
  RefusesWhatItCannotProveFresh spec_fresh_read.
Proof. intros e ok x H. unfold spec_fresh_read. rewrite H. reflexivity. Qed.

(* Two constructions, one clause apiece. The first presents an unsealed
   epoch's writes as fresh, which is what R-10-013c's "an epoch that does
   not seal loses its writes" refuses; the second seals and returns a
   version that did not verify, which is R-10-013e's own refusal dropped. *)
Definition unsealed_read : FreshReader := fun _ ok x => if ok then Some x else None.

Definition unverified_read : FreshReader :=
  fun e _ x => if ep_sealed e then Some x else None.

Theorem the_unsealed_read_is_refuted : ~ RefusesWhatItCannotProveFresh unsealed_read.
Proof.
  intros H.
  specialize (H {| ep_committed := true; ep_sealed := false |} true 7 eq_refl).
  discriminate H.
Qed.

Theorem the_unsealed_read_still_refuses_an_unverified_version :
  forall (e : Epoch) (x : nat), unsealed_read e false x = None.
Proof. intros e x. reflexivity. Qed.

Theorem the_unverified_read_is_refuted :
  ~ RefusesWhatItCannotProveFresh unverified_read.
Proof.
  intros H.
  specialize (H {| ep_committed := true; ep_sealed := true |} false 7 eq_refl).
  discriminate H.
Qed.

Theorem the_unverified_read_still_loses_an_unsealed_epoch :
  forall (ok : bool) (x : nat),
    unverified_read {| ep_committed := true; ep_sealed := false |} ok x = None.
Proof. intros ok x. reflexivity. Qed.

(* The three readers over the four epoch states and both verification
   answers, computed: no two of them are one reader stated twice, and the
   column each construction breaks is the one it is named for. *)
Example which_reader_returns_which_epoch :
  map_over spec_ack all_epochs
    = cons false (cons true (cons false (cons true nil)))
  /\ map_over commit_ack all_epochs
    = cons false (cons true (cons true (cons true nil)))
  /\ map_over (fun e => spec_fresh_read e true 7) all_epochs
    = cons None (cons (Some 7) (cons None (cons (Some 7) nil)))
  /\ map_over (fun e => spec_fresh_read e false 7) all_epochs
    = cons None (cons None (cons None (cons None nil)))
  /\ map_over (fun e => unsealed_read e true 7) all_epochs
    = cons (Some 7) (cons (Some 7) (cons (Some 7) (cons (Some 7) nil)))
  /\ map_over (fun e => unverified_read e false 7) all_epochs
    = cons None (cons (Some 7) (cons None (cons (Some 7) nil))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* =========================================================================
   The demo composition, for R-05-165's uninhabited-domain mode and for the
   refutation witnesses. Every figure below is an arbitrary witness value
   and carries no composition claim (gap h).
   ========================================================================= *)

Definition l2_demo : Composition := {|
  domain_count := 3;
  space_count := 2;
  kind_count := 4;
  snapshot_cost := 1;
  extent_count := 4;
  plain_span := 6;
  queue_bound := 3;
  result_bound := 2;
  batch_txn := 7;
  object_block := 1;
  meta_block := 2;
  index_block := 3;
  granules := 4;
  live_version := 1;
  region_count := 3
|}.

Example the_demo_composition_declares :
  domain_count l2_demo = 3
  /\ space_count l2_demo = 2
  /\ kind_count l2_demo = 4
  /\ snapshot_cost l2_demo = 1
  /\ extent_count l2_demo = 4
  /\ plain_span l2_demo = 6
  /\ queue_bound l2_demo = 3
  /\ result_bound l2_demo = 2
  /\ batch_txn l2_demo = 7
  /\ object_block l2_demo = 1
  /\ meta_block l2_demo = 2
  /\ index_block l2_demo = 3
  /\ granules l2_demo = 4
  /\ live_version l2_demo = 1
  /\ region_count l2_demo = 3
  /\ kinds_of (kind_count l2_demo) = cons 0 (cons 1 (cons 2 (cons 3 nil))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl eq_refl)))))))))))))).

(* -------------------------------------------------------------------------
   The freshness declaration at the demo: three durable regions of which two
   are declared `Fresh` and one is not, so the class boundary is inside the
   roster rather than at its edge. Every figure is a witness value carrying
   no composition claim (gap h).
   ------------------------------------------------------------------------- *)

Definition demo_declaration : Declaration := fun r => Nat.ltb r 2.

Definition demo_versions : Versions := fun r => Nat.add 4 r.

Example the_freshness_declaration_declares :
  map_over demo_declaration (upto (region_count l2_demo))
    = cons true (cons true (cons false nil))
  /\ map_over demo_versions (upto (region_count l2_demo))
    = cons 4 (cons 5 (cons 6 nil))
  /\ spec_epoch_root l2_demo demo_declaration demo_versions = 9
  /\ nosy_epoch_root l2_demo demo_declaration demo_versions = 15
  /\ partial_epoch_root demo_declaration demo_versions = 4
  /\ partial_epoch_root (fun _ => false) demo_versions = 0 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* The specification's root moves with every declared region and with no
   undeclared one, which is the pair of halves stated apart above. *)
Example the_specification_epoch_root_covers_the_declared_class :
  moves_with_every_declared_region l2_demo demo_declaration demo_versions
    (spec_epoch_root l2_demo) = true
  /\ spec_epoch_root l2_demo demo_declaration (bump_at 2 demo_versions)
     = spec_epoch_root l2_demo demo_declaration demo_versions
  /\ spec_epoch_root l2_demo demo_declaration (bump_at 0 demo_versions) = 10
  /\ spec_epoch_root l2_demo demo_declaration (bump_at 1 demo_versions) = 10 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The root that seals over a region the manifest did not declare. *)
Theorem the_nosy_epoch_root_is_refuted :
  ~ ReadsOnlyDeclaredVersions l2_demo (nosy_epoch_root l2_demo).
Proof.
  intros H.
  specialize (H demo_declaration demo_versions (bump_at 2 demo_versions) eq_refl).
  discriminate H.
Qed.

(* The twin: it still moves with every declared region, so what refuses it
   is the undeclared one it also reads and not a region it misses. *)
Example the_nosy_epoch_root_still_covers_every_declared_region :
  moves_with_every_declared_region l2_demo demo_declaration demo_versions
    (nosy_epoch_root l2_demo) = true
  /\ nosy_epoch_root l2_demo demo_declaration (bump_at 2 demo_versions) = 16 :=
  conj eq_refl eq_refl.

(* And the root that seals over one declared region alone. *)
Theorem the_partial_epoch_root_is_refuted :
  moves_with_every_declared_region l2_demo demo_declaration demo_versions
    partial_epoch_root = false.
Proof. reflexivity. Qed.

(* The twin: it reads no undeclared version either, so what refuses it is
   the declared region it misses and not a region it should not have. *)
Example the_partial_epoch_root_reads_no_undeclared_version :
  partial_epoch_root demo_declaration (bump_at 2 demo_versions)
    = partial_epoch_root demo_declaration demo_versions
  /\ partial_epoch_root demo_declaration (bump_at 1 demo_versions)
    = partial_epoch_root demo_declaration demo_versions
  /\ partial_epoch_root demo_declaration (bump_at 0 demo_versions) = 5 :=
  conj eq_refl (conj eq_refl eq_refl).

(* And *which* region it consults, which the checks above leave open: it
   reads one named region's declaration bit and no other's, so a declaration
   that names only that region seals a root and one that names only its
   neighbour seals nothing. Without this the construction's defect is
   "it misses a declared region" without saying which one it keeps, and a
   seeded change of the index it reads moves nothing. *)
Example the_partial_epoch_root_consults_one_named_region :
  partial_epoch_root (fun r => Nat.eqb r 0) demo_versions = 4
  /\ partial_epoch_root (fun r => Nat.eqb r 1) demo_versions = 0
  /\ partial_epoch_root (fun r => Nat.eqb r 2) demo_versions = 0
  /\ spec_epoch_root l2_demo (fun r => Nat.eqb r 1) demo_versions = 5 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Definition demo_sealing : Sealing := {|
  se_key := fun d => Nat.add 5 d;
  se_dedup_key := fun d => Nat.add 1 d;
  se_nonce := fun i _ => Nat.add 20 i;
  se_stored := fun _ l => l;
  se_digest := fun k p => Nat.add (Nat.mul k 8) p
|}.

Example the_demo_sealing_declares :
  map_over (se_key demo_sealing) (upto (domain_count l2_demo))
  = cons 5 (cons 6 (cons 7 nil))
  /\ map_over (se_dedup_key demo_sealing) (upto (domain_count l2_demo))
  = cons 1 (cons 2 (cons 3 nil))
  /\ map_over (fun i => se_nonce demo_sealing i 0) (upto (extent_count l2_demo))
  = cons 20 (cons 21 (cons 22 (cons 23 nil)))
  /\ map_over (fun l => se_stored demo_sealing 3 l) (upto 4)
  = cons 0 (cons 1 (cons 2 (cons 3 nil)))
  /\ map_over (fun p => se_digest demo_sealing 1 p) (upto 3)
  = cons 8 (cons 9 (cons 10 nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* The four sealings the register's own sentences exclude, each one field of
   the specification's replaced and every other field kept, so that what
   refuses it is the named defect and not the construction's shape. *)

(* R-10-018: filesystem compression is out of scope, and its removal is what
   deletes the compress-then-encrypt ratio oracle. A stored length that is a
   function of the plaintext is that oracle. *)
Definition ratio_sealing : Sealing :=
  with_stored demo_sealing (fun p l => if Nat.leb p 1 then before_last l else l).

(* R-10-017 and R-10-023: a nonce that is a function of the plaintext makes
   equal plaintexts present equal stored forms, which is convergent
   encryption's leak whether or not a key is derived from the plaintext. *)
Definition convergent_sealing : Sealing :=
  with_nonce demo_sealing (fun _ p => p).

(* R-10-022 and R-10-027: one key across two confidentiality domains. *)
Definition shared_sealing : Sealing := with_key demo_sealing (fun _ => 5).

(* R-10-015 and R-10-016, and R-10-005a's "no bare cross-domain content hash
   of user data": a digest that reads no key at all. *)
Definition bare_sealing : Sealing := with_digest demo_sealing (fun _ p => p).

Example the_refuting_sealings_differ_in_one_field_each :
  map_over (fun p => se_stored ratio_sealing p 4) (upto (plain_span l2_demo))
  = cons 3 (cons 3 (cons 4 (cons 4 (cons 4 (cons 4 nil)))))
  /\ map_over (fun p => se_nonce convergent_sealing 1 p) (upto 3)
  = cons 0 (cons 1 (cons 2 nil))
  /\ map_over (se_key shared_sealing) (upto (domain_count l2_demo))
  = cons 5 (cons 5 (cons 5 nil))
  /\ map_over (fun p => se_digest bare_sealing 1 p) (upto 3)
  = cons 0 (cons 1 (cons 2 nil)) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Definition all_sealings : list Sealing :=
  cons demo_sealing (cons ratio_sealing (cons convergent_sealing
  (cons shared_sealing (cons bare_sealing nil)))).

Example there_are_five_sealings : count_of all_sealings = 5 := eq_refl.

(* The independence table: four obligations, five sealings, and each
   construction failing exactly one column. Without this the four could each
   be one of the others stated twice and nothing above would notice. *)
Example the_four_sealing_obligations_are_independent :
  map_over (keys_separated l2_demo) all_sealings
  = cons true (cons true (cons true (cons false (cons true nil))))
  /\ map_over (length_hides_at l2_demo) all_sealings
  = cons true (cons false (cons true (cons true (cons true nil))))
  /\ map_over (nonce_per_extent_at l2_demo) all_sealings
  = cons true (cons true (cons false (cons true (cons true nil))))
  /\ map_over (dedup_separated l2_demo) all_sealings
  = cons true (cons true (cons true (cons true (cons false nil))))
  /\ map_over (dedup_key_is_its_own l2_demo) all_sealings
  = cons true (cons true (cons true (cons true (cons true nil)))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* -------------------------------------------------------------------------
   The volumes, the authority set, and what agreement means at it.
   ------------------------------------------------------------------------- *)

Definition ext_of (pr : bool) (d l p : nat) : Ext :=
  {| ex_present := pr; ex_domain := d; ex_len := l; ex_plain := p |}.

Definition vol_a : Volume := fun i =>
  match i with
  | 0 => ext_of true 0 4 2
  | 1 => ext_of true 1 4 1
  | 2 => ext_of true 2 3 1
  | _ => ext_of false 2 0 0
  end.

Definition vol_b : Volume := fun i =>
  match i with
  | 0 => ext_of true 0 4 2
  | 1 => ext_of true 1 4 4
  | 2 => ext_of true 2 3 1
  | _ => ext_of false 2 0 0
  end.

Definition auth0 : nat -> bool := fun d => Nat.eqb d 0.

Example the_two_volumes_differ_in_one_unauthorised_extent :
  map_over (fun i => ex_domain (vol_a i)) (upto (extent_count l2_demo))
  = cons 0 (cons 1 (cons 2 (cons 2 nil)))
  /\ map_over (fun i => ex_plain (vol_a i)) (upto (extent_count l2_demo))
  = cons 2 (cons 1 (cons 1 (cons 0 nil)))
  /\ map_over (fun i => ex_plain (vol_b i)) (upto (extent_count l2_demo))
  = cons 2 (cons 4 (cons 1 (cons 0 nil)))
  /\ map_over auth0 (upto (domain_count l2_demo))
  = cons true (cons false (cons false nil))
  /\ agree_at l2_demo auth0 vol_a vol_b = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example the_volumes_declare_their_shape :
  map_over (fun i => ex_present (vol_a i)) (upto (extent_count l2_demo))
  = cons true (cons true (cons true (cons false nil)))
  /\ map_over (fun i => ex_len (vol_a i)) (upto (extent_count l2_demo))
  = cons 4 (cons 4 (cons 3 (cons 0 nil)))
  /\ map_over (fun i => ex_present (vol_b i)) (upto (extent_count l2_demo))
  = cons true (cons true (cons true (cons false nil)))
  /\ map_over (fun i => ex_len (vol_b i)) (upto (extent_count l2_demo))
  = cons 4 (cons 4 (cons 3 (cons 0 nil)))
  /\ map_over (fun i => ex_domain (vol_b i)) (upto (extent_count l2_demo))
  = cons 0 (cons 1 (cons 2 (cons 2 nil))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Lemma vol_a_is_in_range : domains_in_range l2_demo vol_a.
Proof. intros i. destruct i as [ | [ | [ | k ] ] ]; reflexivity. Qed.

Lemma vol_b_is_in_range : domains_in_range l2_demo vol_b.
Proof. intros i. destruct i as [ | [ | [ | k ] ] ]; reflexivity. Qed.

(* The agreement relation's own truth table, so that no conjunct of it is
   dead: under an authorised domain every one of the four components has to
   agree, and under an unauthorised one the plaintext is the one that need
   not. *)
Definition ext_row (e : Ext) : list Ext :=
  cons e
  (cons (ext_of (negb (ex_present e)) (ex_domain e) (ex_len e) (ex_plain e))
  (cons (ext_of (ex_present e) (S (ex_domain e)) (ex_len e) (ex_plain e))
  (cons (ext_of (ex_present e) (ex_domain e) (S (ex_len e)) (ex_plain e))
  (cons (ext_of (ex_present e) (ex_domain e) (ex_len e) (S (ex_plain e))) nil)))).

Example the_agreement_relation_reads_the_shape_and_not_the_content :
  map_over (ext_agrees auth0 (vol_a 0)) (ext_row (vol_a 0))
  = cons true (cons false (cons false (cons false (cons false nil))))
  /\ map_over (ext_agrees auth0 (vol_a 1)) (ext_row (vol_a 1))
  = cons true (cons false (cons false (cons false (cons true nil)))) :=
  conj eq_refl eq_refl.

(* -------------------------------------------------------------------------
   The generated leak family: one twin volume per extent, differing from the
   specification's in that extent's plaintext alone, held against every
   sealing at once. Column 0 is the authorised extent and is where the
   observation is *supposed* to move, which is what keeps the row from being
   satisfied by an observer that sees nothing at all.
   ------------------------------------------------------------------------- *)

Definition bump (i : nat) (v : Volume) : Volume :=
  fun j => if Nat.eqb i j
           then ext_of (ex_present (v j)) (ex_domain (v j)) (ex_len (v j))
                       (S (ex_plain (v j)))
           else v j.

Definition leak_row (ob : Observer) (s : Sealing) : list bool :=
  map_over (fun i => obs_eqb (ob l2_demo s auth0 vol_a i)
                             (ob l2_demo s auth0 (bump i vol_a) i))
           (upto (extent_count l2_demo)).

Example which_sealing_leaks_at_which_extent :
  map_over (leak_row spec_obs) all_sealings
  = cons (cons false (cons true (cons true (cons true nil))))
    (cons (cons false (cons false (cons false (cons true nil))))
    (cons (cons false (cons false (cons false (cons false nil))))
    (cons (cons false (cons false (cons false (cons false nil))))
    (cons (cons false (cons true (cons true (cons true nil)))) nil))))
  := eq_refl.

(* Each of the four constructions refuted of the obligation, and each shown
   to keep the three it does not break, so that the named defect and not the
   construction's shape is what refuses it. *)

Theorem the_compressing_sealing_is_refuted :
  ~ Noninterferent l2_demo ratio_sealing spec_obs.
Proof.
  intros H. specialize (H auth0 vol_a vol_b 1 vol_a_is_in_range eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_compressing_sealing_keeps_every_other_obligation :
  keys_separated l2_demo ratio_sealing = true
  /\ nonce_per_extent_at l2_demo ratio_sealing = true
  /\ dedup_separated l2_demo ratio_sealing = true
  /\ NonceIsPerExtent ratio_sealing.
Proof.
  split; [ reflexivity | ]. split; [ reflexivity | ]. split; [ reflexivity | ].
  intros i p q. reflexivity.
Qed.

Theorem the_convergent_sealing_is_refuted :
  ~ Noninterferent l2_demo convergent_sealing spec_obs.
Proof.
  intros H. specialize (H auth0 vol_a vol_b 1 vol_a_is_in_range eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_convergent_sealing_keeps_every_other_obligation :
  keys_separated l2_demo convergent_sealing = true
  /\ length_hides_at l2_demo convergent_sealing = true
  /\ dedup_separated l2_demo convergent_sealing = true
  /\ LengthHidesTheContent convergent_sealing.
Proof.
  split; [ reflexivity | ]. split; [ reflexivity | ]. split; [ reflexivity | ].
  intros p q l. reflexivity.
Qed.

Theorem the_shared_key_sealing_is_refuted :
  ~ Noninterferent l2_demo shared_sealing spec_obs.
Proof.
  intros H. specialize (H auth0 vol_a vol_b 1 vol_a_is_in_range eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_shared_key_sealing_keeps_every_other_obligation :
  length_hides_at l2_demo shared_sealing = true
  /\ nonce_per_extent_at l2_demo shared_sealing = true
  /\ dedup_separated l2_demo shared_sealing = true
  /\ LengthHidesTheContent shared_sealing /\ NonceIsPerExtent shared_sealing.
Proof.
  split; [ reflexivity | ]. split; [ reflexivity | ]. split; [ reflexivity | ].
  split.
  - intros p q l. reflexivity.
  - intros i p q. reflexivity.
Qed.

(* And the one that is not a refutation of *this* obligation, which is the
   twin the whole L3 section rests on: a digest computed without the domain
   key is a confirmation-of-file oracle across domains and is
   non-interferent all the same, because the digest reaches no observer that
   does not already hold the key. R-10-016 is therefore not R-10-002's L3
   theorem restated, and a proof of one is not a proof of the other. *)
Theorem the_bare_digest_is_noninterferent :
  Noninterferent l2_demo bare_sealing spec_obs.
Proof.
  apply the_specification_meets_the_obligation.
  - reflexivity.
  - intros p q l. reflexivity.
  - intros i p q. reflexivity.
Qed.

Theorem the_bare_digest_is_still_a_confirmation_oracle :
  dedup_separated l2_demo bare_sealing = false
  /\ Nat.eqb (se_digest bare_sealing (se_dedup_key bare_sealing 0) 3)
             (se_digest bare_sealing (se_dedup_key bare_sealing 1) 3) = true
  /\ Nat.eqb (se_digest demo_sealing (se_dedup_key demo_sealing 0) 3)
             (se_digest demo_sealing (se_dedup_key demo_sealing 1) 3) = false.
Proof. split; [ reflexivity | ]. split; reflexivity. Qed.

(* -------------------------------------------------------------------------
   And two observers rather than two sealings: the leak in the reader rather
   than in what it reads.
   ------------------------------------------------------------------------- *)

(* The plaintext returned whatever key the reader holds, which is the whole
   of what L3 exists to exclude. *)
Definition open_obs : Observer :=
  fun c s a v i =>
    {| ob_present := ex_present (v i);
       ob_domain := ex_domain (v i);
       ob_stored := se_stored s (ex_plain (v i)) (ex_len (v i));
       ob_nonce := se_nonce s i (ex_plain (v i));
       ob_plain := Some (ex_plain (v i));
       ob_digest := if holds_key c s a (se_key s (ex_domain (v i)))
                    then Some (se_digest s (se_dedup_key s (ex_domain (v i)))
                                 (ex_plain (v i)))
                    else None |}.

(* R-10-005a's "metadata identity forms no bare cross-domain content hash of
   user data", refused: the keyed digest published to a reader that holds no
   key for the domain. The plaintext never leaves, and the digest is enough:
   it moves with the content. *)
Definition digest_obs : Observer :=
  fun c s a v i =>
    {| ob_present := ex_present (v i);
       ob_domain := ex_domain (v i);
       ob_stored := se_stored s (ex_plain (v i)) (ex_len (v i));
       ob_nonce := se_nonce s i (ex_plain (v i));
       ob_plain := if holds_key c s a (se_key s (ex_domain (v i)))
                   then Some (ex_plain (v i)) else None;
       ob_digest := Some (se_digest s (se_dedup_key s (ex_domain (v i)))
                            (ex_plain (v i))) |}.

Theorem the_opening_observer_is_refuted :
  ~ Noninterferent l2_demo demo_sealing open_obs.
Proof.
  intros H. specialize (H auth0 vol_a vol_b 1 vol_a_is_in_range eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_publishing_observer_is_refuted :
  ~ Noninterferent l2_demo demo_sealing digest_obs.
Proof.
  intros H. specialize (H auth0 vol_a vol_b 1 vol_a_is_in_range eq_refl eq_refl).
  discriminate H.
Qed.

(* The twin for both: each agrees with the specification's observation on
   every extent the reader is authorised for, so what refuses it is the
   extent it is not authorised for and never a wrong answer to one it is. *)
Example the_leaky_observers_agree_where_the_reader_is_authorised :
  map_over (fun i => obs_eqb (spec_obs l2_demo demo_sealing auth0 vol_a i)
                             (open_obs l2_demo demo_sealing auth0 vol_a i))
           (upto (extent_count l2_demo))
  = cons true (cons false (cons false (cons false nil)))
  /\ map_over (fun i => obs_eqb (spec_obs l2_demo demo_sealing auth0 vol_a i)
                                (digest_obs l2_demo demo_sealing auth0 vol_a i))
             (upto (extent_count l2_demo))
  = cons true (cons false (cons false (cons false nil)))
  /\ leak_row open_obs demo_sealing
  = cons false (cons false (cons false (cons false nil)))
  /\ leak_row digest_obs demo_sealing
  = cons false (cons false (cons false (cons false nil))) :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* The observation's own comparison, field by field, so that no conjunct of
   `obs_eqb` is dead and a refutation above is a refutation of the field it
   names. *)
Definition obs_zero : Obs :=
  {| ob_present := true; ob_domain := 1; ob_stored := 4; ob_nonce := 21;
     ob_plain := Some 1; ob_digest := Some 17 |}.

Definition obs_row : list Obs :=
  cons obs_zero
  (cons {| ob_present := false; ob_domain := 1; ob_stored := 4; ob_nonce := 21;
           ob_plain := Some 1; ob_digest := Some 17 |}
  (cons {| ob_present := true; ob_domain := 2; ob_stored := 4; ob_nonce := 21;
           ob_plain := Some 1; ob_digest := Some 17 |}
  (cons {| ob_present := true; ob_domain := 1; ob_stored := 5; ob_nonce := 21;
           ob_plain := Some 1; ob_digest := Some 17 |}
  (cons {| ob_present := true; ob_domain := 1; ob_stored := 4; ob_nonce := 22;
           ob_plain := Some 1; ob_digest := Some 17 |}
  (cons {| ob_present := true; ob_domain := 1; ob_stored := 4; ob_nonce := 21;
           ob_plain := None; ob_digest := Some 17 |}
  (cons {| ob_present := true; ob_domain := 1; ob_stored := 4; ob_nonce := 21;
           ob_plain := Some 1; ob_digest := None |} nil)))))).

(* And the row's own fields, so that each variant differs from the first in
   exactly one of them: without this a seeded change of a second field in
   one variant leaves the comparison false for the wrong reason and the
   column it is supposed to exercise goes untested. *)
Example the_observation_row_differs_in_one_field_apiece :
  map_over ob_present obs_row
  = cons true (cons false (cons true (cons true (cons true (cons true
    (cons true nil))))))
  /\ map_over ob_domain obs_row
  = cons 1 (cons 1 (cons 2 (cons 1 (cons 1 (cons 1 (cons 1 nil))))))
  /\ map_over ob_stored obs_row
  = cons 4 (cons 4 (cons 4 (cons 5 (cons 4 (cons 4 (cons 4 nil))))))
  /\ map_over ob_nonce obs_row
  = cons 21 (cons 21 (cons 21 (cons 21 (cons 22 (cons 21 (cons 21 nil))))))
  /\ map_over ob_plain obs_row
  = cons (Some 1) (cons (Some 1) (cons (Some 1) (cons (Some 1) (cons (Some 1)
    (cons None (cons (Some 1) nil))))))
  /\ map_over ob_digest obs_row
  = cons (Some 17) (cons (Some 17) (cons (Some 17) (cons (Some 17)
    (cons (Some 17) (cons (Some 17) (cons None nil)))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Example the_observation_compares_every_field :
  map_over (obs_eqb obs_zero) obs_row
  = cons true (cons false (cons false (cons false (cons false (cons false
    (cons false nil)))))) := eq_refl.

(* =========================================================================
   The demo keyspace, and the generated families over the order it is built
   in. A key order is exactly what a person enumerates badly, so the
   permutations, deletions, proper suffixes and duplications below are
   generated over the entry list's own indices rather than authored.
   ========================================================================= *)

Definition l2_entries : Keyspace :=
  cons (pair (mk_key 0 0 k_inode 3 4 0) 30)
  (cons (pair (mk_key 0 0 k_dirent 1 4 0) 10)
  (cons (pair (mk_key 0 0 k_extent 4 4 0) 40)
  (cons (pair (mk_key 1 0 k_inode 5 4 0) 50)
  (cons (pair (mk_key 0 1 k_xattr 2 4 0) 20) nil)))).

Definition demo_keyspace : Keyspace := ins_all l2_keys l2_entries nil.

(* R-10-005's "one keyspace": the four typed kinds and both confidentiality
   domains sit in one index, sorted by the one order, answered by the one
   lookup. *)
Example the_one_keyspace_carries_all_four_kinds :
  map_over (fun e => snd e) demo_keyspace
  = cons 30 (cons 10 (cons 40 (cons 20 (cons 50 nil))))
  /\ map_over (fun e => k_kind (fst e)) demo_keyspace
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 0 nil))))
  /\ sorted l2_keys demo_keyspace = true
  /\ sorted l2_keys l2_entries = false
  /\ count_of demo_keyspace = 5 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Example the_keyspace_answers_the_keys_it_was_given :
  look l2_keys (mk_key 0 0 k_inode 3 4 0) demo_keyspace = Some 30
  /\ look l2_keys (mk_key 1 0 k_inode 5 4 0) demo_keyspace = Some 50
  /\ look l2_keys (mk_key 2 0 k_inode 5 4 0) demo_keyspace = None
  /\ look l2_keys (mk_key 0 0 k_inode 3 4 1) demo_keyspace = None :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   The kind roster is the composition's and not this file's (reading 1, gap
   a). The demo declares four, the demo keyspace names four, and a fifth is
   expressible: a composition declaring five admits a keyspace the
   four-kind one refuses, which is exactly what a *closed* enumeration would
   have made unwritable. Closing it is a register act, owed at R-10-005.
   ------------------------------------------------------------------------- *)

Definition acl_entry : prod K2 nat := pair (mk_key 0 0 k_acl 6 4 0) 60.

Definition five_kind_demo : Composition :=
  {| domain_count := domain_count l2_demo; space_count := space_count l2_demo;
     kind_count := S (kind_count l2_demo);
     snapshot_cost := snapshot_cost l2_demo;
     extent_count := extent_count l2_demo; plain_span := plain_span l2_demo;
     queue_bound := queue_bound l2_demo; result_bound := result_bound l2_demo;
     batch_txn := batch_txn l2_demo; object_block := object_block l2_demo;
     meta_block := meta_block l2_demo; index_block := index_block l2_demo;
     granules := granules l2_demo; live_version := live_version l2_demo;
     region_count := region_count l2_demo |}.

Example the_kind_roster_is_the_composition_s :
  every_key_names_a_declared_kind (kind_count l2_demo) demo_keyspace = true
  /\ every_key_names_a_declared_kind (kind_count l2_demo)
       (cons acl_entry demo_keyspace) = false
  /\ every_key_names_a_declared_kind (kind_count five_kind_demo)
       (cons acl_entry demo_keyspace) = true
  /\ kind_count five_kind_demo = 5
  /\ fst acl_entry = mk_key 0 0 4 6 4 0
  /\ snd acl_entry = 60
  /\ sorted l2_keys (ins_all l2_keys (cons acl_entry l2_entries) nil) = true
  /\ count_of (ins_all l2_keys (cons acl_entry l2_entries) nil) = 6
  /\ look l2_keys (fst acl_entry)
       (ins_all l2_keys (cons acl_entry l2_entries) nil) = Some 60
  /\ look l2_keys (fst acl_entry) demo_keyspace = None :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))))))).

(* And the obligation over an arbitrary composition and keyspace: a
   keyspace whose keys all name declared kinds is one every key of which
   does, which is the only thing a count can decide. It is stated so that
   the roster has a reader rather than being a field nothing consults. *)
Theorem every_key_of_an_in_range_keyspace_names_a_declared_kind :
  forall (c : Composition) (ks : Keyspace) (k : nat),
    every_key_names_a_declared_kind (kind_count c) ks = true ->
    mem_of k (map_over (fun x => k_kind (fst x)) ks) = true ->
    kind_in_range (kind_count c) k = true.
Proof.
  intros c ks k H Hm. unfold every_key_names_a_declared_kind in H.
  apply (all_of_elim (kind_in_range (kind_count c))
           (map_over (fun x => k_kind (fst x)) ks) k); [ | exact Hm ].
  rewrite (all_of_map (prod K2 nat) nat (kind_in_range (kind_count c))
             (fun x => k_kind (fst x)) ks).
  exact H.
Qed.

Example entries_compare_component_by_component :
  entries_eqb demo_keyspace demo_keyspace = true
  /\ entries_eqb demo_keyspace nil = false
  /\ entries_eqb nil demo_keyspace = false
  /\ entries_eqb (cons (pair (mk_key 0 0 k_inode 3 4 0) 30) nil)
                 (cons (pair (mk_key 0 0 k_inode 3 4 0) 31) nil) = false
  /\ entries_eqb (cons (pair (mk_key 0 0 k_inode 3 4 0) 30) nil)
                 (cons (pair (mk_key 0 0 k_dirent 3 4 0) 30) nil) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* The four generators, over the entry list's own indices. *)
Definition k2_transpositions (l : Keyspace) : list Keyspace :=
  map_over (fun n => swap_at n l) (upto (before_last (count_of l))).

Definition k2_deletions (l : Keyspace) : list Keyspace :=
  map_over (fun n => drop_at n l) (upto (count_of l)).

Definition k2_suffixes (l : Keyspace) : list Keyspace :=
  map_over (fun n => suffix_at (S n) l) (upto (count_of l)).

Definition k2_duplications (l : Keyspace) : list Keyspace :=
  map_over (fun n => insert_at n (pair (mk_key 0 0 k_inode 3 4 0) 99) l)
           (upto (S (count_of l))).

Definition k2_orders (l : Keyspace) : list Keyspace :=
  app (k2_transpositions l) (app (k2_deletions l)
      (app (k2_suffixes l) (k2_duplications l))).

Example the_l2_key_order_family_is_twenty :
  count_of (k2_transpositions l2_entries) = 4
  /\ count_of (k2_deletions l2_entries) = 5
  /\ count_of (k2_suffixes l2_entries) = 5
  /\ count_of (k2_duplications l2_entries) = 6
  /\ count_of (k2_orders l2_entries) = 20 :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

Definition builds_the_same_l2_index (l : Keyspace) : bool :=
  entries_eqb (ins_all l2_keys l nil) demo_keyspace.

(* One conversion apiece: every adjacent transposition of the insertion
   order builds the same index and no deletion or proper suffix does, which
   is what makes the index a function of the entry set and the order
   immaterial to it. *)
Example no_adjacent_transposition_moves_the_l2_index :
  all_of builds_the_same_l2_index (k2_transpositions l2_entries) = true := eq_refl.

Example every_deletion_builds_a_different_l2_index :
  all_of (fun l => negb (builds_the_same_l2_index l)) (k2_deletions l2_entries) = true
  := eq_refl.

Example every_proper_suffix_builds_a_different_l2_index :
  all_of (fun l => negb (builds_the_same_l2_index l)) (k2_suffixes l2_entries) = true
  := eq_refl.

(* The duplication family, which sortedness alone does not decide: an
   entry inserted a second time wins exactly where it arrives late, so the
   index is a function of the *last* write of a key and the family's own
   inserted value is read back through it rather than asserted beside it. *)
Example the_l2_duplicate_wins_exactly_where_it_arrives_late :
  map_over (fun l => look l2_keys (mk_key 0 0 k_inode 3 4 0) (ins_all l2_keys l nil))
           (k2_duplications l2_entries)
  = cons (Some 30) (cons (Some 99) (cons (Some 99) (cons (Some 99)
    (cons (Some 99) (cons (Some 99) nil))))) := eq_refl.

Theorem the_l2_duplicate_that_wins_is_the_later_one :
  forall n : nat,
    Nat.ltb 0 n = true ->
    Nat.ltb n (S (count_of l2_entries)) = true ->
    look l2_keys (mk_key 0 0 k_inode 3 4 0)
      (ins_all l2_keys
         (insert_at n (pair (mk_key 0 0 k_inode 3 4 0) 99) l2_entries) nil)
    = Some 99.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | [ | n ] ] ] ] ] ]; intros H1 H2;
    first [ reflexivity | discriminate H1 | discriminate H2 ].
Qed.

(* And the entry list's own components, read back rather than left implicit:
   the index's shape is decided by the keys and nothing above reads more
   than two of them. *)
Example the_demo_entries_declare :
  map_over (fun e => k_domain (fst e)) l2_entries
  = cons 0 (cons 0 (cons 0 (cons 1 (cons 0 nil))))
  /\ map_over (fun e => k_space (fst e)) l2_entries
  = cons 0 (cons 0 (cons 0 (cons 0 (cons 1 nil))))
  /\ map_over (fun e => k_object (fst e)) l2_entries
  = cons 3 (cons 1 (cons 4 (cons 5 (cons 2 nil))))
  /\ map_over (fun e => k_attr (fst e)) l2_entries
  = cons 4 (cons 4 (cons 4 (cons 4 (cons 4 nil))))
  /\ map_over (fun e => k_version (fst e)) l2_entries
  = cons 0 (cons 0 (cons 0 (cons 0 (cons 0 nil))))
  /\ map_over (fun e => snd e) l2_entries
  = cons 30 (cons 10 (cons 40 (cons 50 (cons 20 nil)))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* And the whole family builds a sorted index whatever it does to the
   contents, which is R-10-003's order property read at this instance. *)
Example every_l2_key_order_builds_a_sorted_index :
  all_of (fun l => sorted l2_keys (ins_all l2_keys l nil)) (k2_orders l2_entries)
  = true := eq_refl.

(* The same content as a bounded quantifier over the index rather than only
   as an enumeration. *)
Theorem no_transposition_in_range_moves_the_index :
  forall n : nat,
    Nat.ltb n (before_last (count_of l2_entries)) = true ->
    builds_the_same_l2_index (swap_at n l2_entries) = true.
Proof.
  intros n. destruct n as [ | [ | [ | [ | n ] ] ] ]; intros H;
    first [ reflexivity | discriminate H ].
Qed.

Theorem every_deletion_in_range_moves_the_index :
  forall n : nat,
    Nat.ltb n (count_of l2_entries) = true ->
    builds_the_same_l2_index (drop_at n l2_entries) = false.
Proof.
  intros n. destruct n as [ | [ | [ | [ | [ | n ] ] ] ] ]; intros H;
    first [ reflexivity | discriminate H ].
Qed.

(* -------------------------------------------------------------------------
   The snapshot's three obligations and the three constructions that break
   one apiece: one whose cost grows with the keyspace, one that loses the
   reads the keyspace already had, and one that keeps both and is admitted,
   which is what the entry's O(1) admits and an exact-zero reading would
   have refused.
   ------------------------------------------------------------------------- *)

Lemma look_app_left :
  forall (ka : KeyAlgebra) (k : Key ka) (v : nat) (l r : Index ka),
    look ka k l = Some v -> look ka k (app l r) = Some v.
Proof.
  intros ka k v l. induction l as [ | e s IH ]; intros r H.
  - discriminate H.
  - simpl in H. simpl. destruct (key_eqb ka k (fst e)); [ exact H | exact (IH r H) ].
Qed.

(* R-10-005's bound refused, and refused of *every* declared constant rather
   than of the demo's: a keyspace one entry wider than whatever a
   composition declares already doubles past it. *)
Theorem the_copying_snapshot_outgrows_every_declared_constant :
  forall (c : Composition) (k : K2),
    Nat.leb (count_of (copy_snapshot (pad (S (snapshot_cost c)) k)
                         (live_version c)))
            (Nat.add (count_of (pad (S (snapshot_cost c)) k)) (snapshot_cost c))
      = false.
Proof.
  intros c k. unfold copy_snapshot.
  rewrite (count_of_app (prod K2 nat) (pad (S (snapshot_cost c)) k)
             (rekeyed (live_version c) (pad (S (snapshot_cost c)) k))).
  rewrite (count_of_rekeyed (live_version c) (pad (S (snapshot_cost c)) k)).
  rewrite (count_of_pad (S (snapshot_cost c)) k). simpl.
  rewrite (add_succ_right (snapshot_cost c) (snapshot_cost c)).
  exact (leb_succ_self_false (Nat.add (snapshot_cost c) (snapshot_cost c))).
Qed.

Theorem the_copying_snapshot_is_refuted :
  forall c : Composition, ~ AddsAtMostTheDeclaredConstant c copy_snapshot.
Proof.
  intros c H.
  specialize (H (pad (S (snapshot_cost c)) (mk_key 0 0 0 0 0 0))
                (live_version c)).
  rewrite (the_copying_snapshot_outgrows_every_declared_constant c
             (mk_key 0 0 0 0 0 0)) in H.
  discriminate H.
Qed.

Theorem the_copying_snapshot_keeps_every_read_it_already_had :
  KeepsEveryReadItAlreadyHad copy_snapshot.
Proof.
  intros ks ve k v H. unfold copy_snapshot.
  exact (look_app_left l2_keys k v ks (rekeyed ve ks) H).
Qed.

Theorem the_rekeying_snapshot_is_refuted :
  ~ KeepsEveryReadItAlreadyHad rekey_snapshot.
Proof.
  intros H.
  specialize (H demo_keyspace (live_version l2_demo)
                (mk_key 0 0 k_inode 3 4 0) 30 eq_refl).
  discriminate H.
Qed.

Theorem the_rekeying_snapshot_keeps_the_declared_bound :
  forall c : Composition, AddsAtMostTheDeclaredConstant c rekey_snapshot.
Proof.
  intros c ks ve. unfold rekey_snapshot.
  rewrite (count_of_rekeyed ve ks).
  exact (leb_add_right (count_of ks) (snapshot_cost c)).
Qed.

(* And the snapshotter the entry admits: one bookkeeping entry, which meets
   the declared bound wherever the composition declares at least one, keeps
   every read the keyspace already had, and changes what a key that read
   nothing now reads. The last is what separates R-10-005's own reading from
   the stronger one, and it is why the bound is a field. *)
Theorem the_bookkeeping_snapshot_keeps_the_declared_bound :
  forall (c : Composition) (k : K2),
    Nat.leb 1 (snapshot_cost c) = true ->
    AddsAtMostTheDeclaredConstant c (bookkeeping_snapshot k).
Proof.
  intros c k Hb ks ve. unfold bookkeeping_snapshot.
  rewrite (count_of_app (prod K2 nat) ks (cons (pair (at_version ve k) 0) nil)).
  exact (leb_add_left_mono 1 (snapshot_cost c) (count_of ks) Hb).
Qed.

Theorem the_bookkeeping_snapshot_keeps_every_read_it_already_had :
  forall k : K2, KeepsEveryReadItAlreadyHad (bookkeeping_snapshot k).
Proof.
  intros k ks ve j v H. unfold bookkeeping_snapshot.
  exact (look_app_left l2_keys j v ks (cons (pair (at_version ve k) 0) nil) H).
Qed.

Theorem the_bookkeeping_snapshot_is_refuted :
  ~ ChangesNoReadAtAll (bookkeeping_snapshot (mk_key 0 0 0 0 0 0)).
Proof.
  intros H.
  specialize (H nil 1 (at_version 1 (mk_key 0 0 0 0 0 0))). discriminate H.
Qed.

(* The three obligations against the four snapshotters, computed: no two of
   them are one obligation stated twice. *)
Example the_three_snapshot_obligations_are_independent :
  map_over (fun sn => Nat.leb (count_of (sn demo_keyspace (live_version l2_demo)))
                              (Nat.add (count_of demo_keyspace)
                                       (snapshot_cost l2_demo)))
           (cons spec_snapshot (cons copy_snapshot (cons rekey_snapshot
           (cons (bookkeeping_snapshot (mk_key 0 0 0 0 0 0)) nil))))
  = cons true (cons false (cons true (cons true nil)))
  /\ map_over (fun sn => opt_eqb (look l2_keys (mk_key 0 0 k_inode 3 4 0)
                                    (sn demo_keyspace (live_version l2_demo)))
                                 (Some 30))
             (cons spec_snapshot (cons copy_snapshot (cons rekey_snapshot
             (cons (bookkeeping_snapshot (mk_key 0 0 0 0 0 0)) nil))))
  = cons true (cons true (cons false (cons true nil)))
  /\ map_over (fun sn => opt_eqb (look l2_keys
                                    (at_version (live_version l2_demo)
                                       (mk_key 0 0 0 0 0 0))
                                    (sn demo_keyspace (live_version l2_demo)))
                                 None)
             (cons spec_snapshot (cons copy_snapshot (cons rekey_snapshot
             (cons (bookkeeping_snapshot (mk_key 0 0 0 0 0 0)) nil))))
  = cons true (cons true (cons true (cons false nil))) :=
  conj eq_refl (conj eq_refl eq_refl).

(* -------------------------------------------------------------------------
   R-10-005a's second database, refuted and twinned.
   ------------------------------------------------------------------------- *)

Definition demo_side : Keyspace := cons (pair (mk_key 2 0 k_inode 9 0 0) 99) nil.

Theorem the_second_database_is_refuted :
  ~ IsAViewOfTheKeyspace (side_meta demo_side).
Proof.
  intros H. specialize (H nil (mk_key 2 0 k_inode 9 0 0)). discriminate H.
Qed.

Theorem the_second_database_never_contradicts_the_keyspace :
  forall (side ks : Keyspace) (k : K2) (v : nat),
    look l2_keys k ks = Some v -> side_meta side ks k = Some v.
Proof. intros side ks k v H. unfold side_meta. rewrite H. reflexivity. Qed.

Example the_second_database_answers_where_the_keyspace_does_not :
  spec_meta demo_keyspace (mk_key 2 0 k_inode 9 0 0) = None
  /\ side_meta demo_side demo_keyspace (mk_key 2 0 k_inode 9 0 0) = Some 99
  /\ spec_meta demo_keyspace (mk_key 0 0 k_inode 3 4 0) = Some 30
  /\ side_meta demo_side demo_keyspace (mk_key 0 0 k_inode 3 4 0) = Some 30 :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* -------------------------------------------------------------------------
   And the resolution read at the demo keyspace, where the spanning
   construction reaches a second domain and the specification does not.
   ------------------------------------------------------------------------- *)

Definition demo_cap : NsCap := {| nc_domain := 0; nc_space := 0; nc_rights := 2 |}.

Definition demo_inode_query : Query :=
  {| q_domain := 0; q_space := 0; q_kind := k_inode; q_attr := 4 |}.

Example the_resolution_stays_inside_the_presented_namespace :
  map_over oc_object (spec_resolve demo_cap demo_inode_query demo_keyspace)
  = cons 3 nil
  /\ map_over oc_object (spanning_resolve demo_cap demo_inode_query demo_keyspace)
  = cons 3 (cons 5 nil)
  /\ map_over oc_rights (mint_resolve demo_cap demo_inode_query demo_keyspace)
  = cons 3 nil
  /\ map_over oc_rights (spec_resolve demo_cap demo_inode_query demo_keyspace)
  = cons 2 nil :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* =========================================================================
   The batch at the demo composition, and the crash-point family over it.
   The cuts, the recovery and the store below are JournalIndex.v's; what is
   new is that three blocks are read at once.
   ========================================================================= *)

Definition demo_batch : Batch := {| ba_object := 11; ba_meta := 12; ba_index := 13 |}.

Definition l2_store : Store := fun b => b.

Definition l2_view (j : list Rec) : list nat :=
  map_over (fun b => spec_recover j l2_store b) (upto 5).

Example the_batch_is_three_records_in_one_transaction :
  count_of (spec_writer l2_demo demo_batch) = 3
  /\ map_over rec_txn (spec_writer l2_demo demo_batch) = cons 7 (cons 7 (cons 7 nil))
  /\ map_over rec_txn (split_writer l2_demo demo_batch) = cons 7 (cons 7 (cons 8 nil))
  /\ map_over rec_block (spec_writer l2_demo demo_batch) = cons 1 (cons 2 (cons 3 nil))
  /\ all_of intact (spec_writer l2_demo demo_batch) = true
  /\ all_of intact (split_writer l2_demo demo_batch) = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Example there_are_four_crash_points_over_the_batch :
  count_of (cuts (spec_writer l2_demo demo_batch)) = 4 := eq_refl.

(* R-10-005c's "index and objects are never observed mismatched", computed
   at every crash point of the batch, and the same row under the writer that
   splits the index into a transaction of its own. *)
Example the_object_and_the_index_move_together_at_every_crash_point :
  map_over (together l2_demo) (cuts (spec_writer l2_demo demo_batch))
  = cons true (cons true (cons true (cons true nil)))
  /\ map_over (together l2_demo) (cuts (split_writer l2_demo demo_batch))
  = cons true (cons true (cons false (cons true nil)))
  /\ all_of (together l2_demo) (cuts (spec_writer l2_demo demo_batch)) = true
  /\ all_of (together l2_demo) (cuts (split_writer l2_demo demo_batch)) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* And the mismatch is a store a reader can be standing in, not an abstract
   disagreement: at the split writer's third crash point the object and its
   metadata have landed and the index has not. *)
Example the_split_writer_leaves_a_reader_standing_in_the_mismatch :
  map_over l2_view (cuts (spec_writer l2_demo demo_batch))
  = cons (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil)))))
    (cons (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil)))))
    (cons (cons 0 (cons 1 (cons 2 (cons 3 (cons 4 nil)))))
    (cons (cons 0 (cons 11 (cons 12 (cons 13 (cons 4 nil))))) nil)))
  /\ l2_view (take 2 (split_writer l2_demo demo_batch))
  = cons 0 (cons 11 (cons 12 (cons 3 (cons 4 nil))))
  /\ l2_view (split_writer l2_demo demo_batch)
  = cons 0 (cons 11 (cons 12 (cons 13 (cons 4 nil)))) :=
  conj eq_refl (conj eq_refl eq_refl).

(* R-10-005c's mismatch as a refutation rather than a row: at the cut where
   the closing record has landed and the index record has not, the object is
   observed updated and the index is not. *)
Theorem the_early_close_writer_is_refuted :
  ~ NeverObservedApart l2_demo early_close_writer.
Proof. intros H. specialize (H demo_batch 1). discriminate H. Qed.

(* The twin: it carries one transaction, its records are intact, and by its
   last cut the object and the index have both landed. What refuses it is
   the window its commit record opens and nothing else about it. *)
Example the_early_close_writer_keeps_every_other_obligation :
  map_over rec_txn (early_close_writer l2_demo demo_batch)
    = cons 7 (cons 7 (cons 7 nil))
  /\ map_over rec_block (early_close_writer l2_demo demo_batch)
    = cons 1 (cons 2 (cons 3 nil))
  /\ map_over rec_value (early_close_writer l2_demo demo_batch)
    = cons 11 (cons 12 (cons 13 nil))
  /\ map_over rec_closes (early_close_writer l2_demo demo_batch)
    = cons true (cons false (cons false nil))
  /\ map_over rec_closes (spec_writer l2_demo demo_batch)
    = cons false (cons false (cons true nil))
  /\ all_of intact (early_close_writer l2_demo demo_batch) = true
  /\ map_over (together l2_demo) (cuts (early_close_writer l2_demo demo_batch))
    = cons true (cons false (cons false (cons true nil)))
  /\ together l2_demo (early_close_writer l2_demo demo_batch) = true
  /\ map_over (together l2_demo) (cuts (spec_writer l2_demo demo_batch))
    = cons true (cons true (cons true (cons true nil))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))))))).

(* The twin: the split writer breaks the clause that puts the three updates
   in *one* L0 transaction and breaks nothing JournalIndex.v states of a
   journal. Both of its transactions commit, its records are intact, and
   recovery lands every committed write; R-10-005b's atomicity is therefore
   not R-10-002's atomicity restated. *)
Example the_split_writer_keeps_every_obligation_of_the_layer_below :
  commits (scan (split_writer l2_demo demo_batch)) 7 = true
  /\ commits (scan (split_writer l2_demo demo_batch)) 8 = true
  /\ touched (split_writer l2_demo demo_batch) (object_block l2_demo) = true
  /\ touched (split_writer l2_demo demo_batch) (index_block l2_demo) = true
  /\ touched (take 2 (split_writer l2_demo demo_batch)) (object_block l2_demo) = true
  /\ touched (take 2 (split_writer l2_demo demo_batch)) (index_block l2_demo) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* =========================================================================
   The delta stream at the demo composition, and the emitter family over its
   own prefixes.
   ========================================================================= *)

Definition demo_deltas : list Delta :=
  cons (Added (mk_key 0 0 k_inode 3 4 0))
  (cons (Removed (mk_key 0 0 k_dirent 1 4 0))
  (cons (Added (mk_key 0 0 k_extent 4 4 0))
  (cons (Added (mk_key 0 1 k_xattr 2 4 0))
  (cons (Removed (mk_key 0 0 k_inode 3 4 0)) nil)))).

(* A delta's key, reached without a literal at the site: the fallback is a
   parameter, so nothing here fixes what a marker's key would be. *)
Definition delta_key (d : Delta) (dflt : K2) : K2 :=
  match d with
  | Added k => k
  | Removed k => k
  | Rescan => dflt
  end.

Definition is_added (d : Delta) : bool :=
  match d with
  | Added _ => true
  | Removed _ => false
  | Rescan => false
  end.

(* The stream's own contents, read back rather than counted: without this
   every statement about the emitter is a statement about how many deltas it
   delivers and none about which. *)
Example the_delta_stream_declares :
  map_over is_added demo_deltas
  = cons true (cons false (cons true (cons true (cons false nil))))
  /\ map_over is_rescan demo_deltas
  = cons false (cons false (cons false (cons false (cons false nil))))
  /\ map_over (fun d => k_domain (delta_key d (mk_key 0 0 k_inode 0 0 0)))
              demo_deltas
  = cons 0 (cons 0 (cons 0 (cons 0 (cons 0 nil))))
  /\ map_over (fun d => k_space (delta_key d (mk_key 0 0 k_inode 0 0 0)))
              demo_deltas
  = cons 0 (cons 0 (cons 0 (cons 1 (cons 0 nil))))
  /\ map_over (fun d => k_kind (delta_key d (mk_key 0 0 k_inode 0 0 0)))
              demo_deltas
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 0 nil))))
  /\ map_over (fun d => k_object (delta_key d (mk_key 0 0 k_inode 0 0 0)))
              demo_deltas
  = cons 3 (cons 1 (cons 4 (cons 2 (cons 3 nil))))
  /\ map_over (fun d => k_attr (delta_key d (mk_key 0 0 k_inode 0 0 0)))
              demo_deltas
  = cons 4 (cons 4 (cons 4 (cons 4 (cons 4 nil))))
  /\ map_over (fun d => k_version (delta_key d (mk_key 0 0 k_inode 0 0 0)))
              demo_deltas
  = cons 0 (cons 0 (cons 0 (cons 0 (cons 0 nil)))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl)))))).

(* And the version is R-10-005's own field rather than a component like the
   rest: a delta that names one snapshot version is a delta about a different
   key from one that names another, which is what makes the snapshot writable
   at all. Stated here because it is the one component no statement above
   reads. *)
Example a_delta_at_another_version_names_another_key :
  k2_eqb (mk_key 0 0 k_extent 4 4 0) (mk_key 0 0 k_extent 4 4 1) = false
  /\ look l2_keys (mk_key 0 0 k_extent 4 4 1) demo_keyspace = None
  /\ look l2_keys (mk_key 0 0 k_extent 4 4 0) demo_keyspace = Some 40 :=
  conj eq_refl (conj eq_refl eq_refl).

(* And what an overflowing emission delivers is the stream's own prefix and
   never a reordering or an invention of it, stated of an arbitrary bound
   and an arbitrary stream. *)
Theorem an_overflowing_emission_is_a_prefix_of_the_stream :
  forall (bound : nat) (ds : list Delta),
    Nat.leb (count_of ds) bound = false ->
    spec_emit bound ds = app (take (before_last bound) ds) (cons Rescan nil).
Proof. intros bound ds H. unfold spec_emit. rewrite H. reflexivity. Qed.

Example the_emitted_prefix_is_the_stream_own :
  spec_emit (queue_bound l2_demo) demo_deltas
  = cons (Added (mk_key 0 0 k_inode 3 4 0))
    (cons (Removed (mk_key 0 0 k_dirent 1 4 0)) (cons Rescan nil))
  /\ map_over is_added (spec_emit (queue_bound l2_demo) demo_deltas)
  = cons true (cons false (cons false nil)) :=
  conj eq_refl eq_refl.

Example the_delta_alphabet_is_three_and_the_marker_is_one_of_them :
  map_over is_rescan (cons (Added (mk_key 0 0 k_inode 3 4 0))
                     (cons (Removed (mk_key 0 0 k_inode 3 4 0))
                     (cons Rescan nil)))
  = cons false (cons false (cons true nil))
  /\ delta_eqb Rescan Rescan = true
  /\ delta_eqb (Added (mk_key 0 0 k_inode 3 4 0)) (Added (mk_key 0 0 k_inode 3 4 0))
     = true
  /\ delta_eqb (Added (mk_key 0 0 k_inode 3 4 0)) (Removed (mk_key 0 0 k_inode 3 4 0))
     = false
  /\ delta_eqb (Added (mk_key 0 0 k_inode 3 4 0)) (Added (mk_key 0 0 k_inode 4 4 0))
     = false
  /\ delta_eqb (Added (mk_key 0 0 k_inode 3 4 0)) Rescan = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Definition emit_counts (em : Emitter) : list nat :=
  map_over (fun ds => count_of (em (queue_bound l2_demo) ds)) (prefixes demo_deltas).

Definition marker_counts (em : Emitter) : list nat :=
  map_over (fun ds => count_of (filter_of is_rescan (em (queue_bound l2_demo) ds)))
           (prefixes demo_deltas).

Example the_emission_at_every_prefix_of_the_stream :
  emit_counts spec_emit = cons 0 (cons 1 (cons 2 (cons 3 (cons 3 (cons 3 nil)))))
  /\ marker_counts spec_emit
  = cons 0 (cons 0 (cons 0 (cons 0 (cons 1 (cons 1 nil)))))
  /\ emit_counts hoard_emit
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 4 (cons 5 nil)))))
  /\ marker_counts hoard_emit
  = cons 0 (cons 0 (cons 0 (cons 0 (cons 0 (cons 0 nil)))))
  /\ emit_counts twin_marker_emit
  = cons 0 (cons 1 (cons 2 (cons 3 (cons 3 (cons 3 nil)))))
  /\ marker_counts twin_marker_emit
  = cons 0 (cons 0 (cons 0 (cons 0 (cons 2 (cons 2 nil))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(* The bound is read *at* the bound and not only past it: a stream of
   exactly the declared length is delivered whole and is not truncated to
   make room for a marker it does not need. *)
Example the_emission_at_the_bound_is_not_truncated :
  spec_emit (queue_bound l2_demo) (take 3 demo_deltas) = take 3 demo_deltas
  /\ spec_emit (queue_bound l2_demo) (take 4 demo_deltas)
     = app (take 2 demo_deltas) (cons Rescan nil) :=
  conj eq_refl eq_refl.

(* R-10-005c's "rather than backpressuring commit", read on the boundary as
   well as either side of it: the specification's commit does not move with
   the occupancy and the backpressuring one stops exactly at the declared
   bound. *)
Definition commit_row (cw : Committer) : list nat :=
  map_over (fun o => cw o l2_store (object_block l2_demo)) (upto 5).

Example the_commit_does_not_read_the_subscription_queue :
  commit_row (spec_commit l2_demo demo_batch)
  = cons 11 (cons 11 (cons 11 (cons 11 (cons 11 nil))))
  /\ commit_row (backpressure_commit l2_demo demo_batch)
  = cons 11 (cons 11 (cons 11 (cons 1 (cons 1 nil)))) :=
  conj eq_refl eq_refl.

Theorem the_backpressuring_commit_is_refuted :
  ~ NeverBackpressuresTheCommit (backpressure_commit l2_demo demo_batch).
Proof.
  intros H. specialize (H 0 3 l2_store (object_block l2_demo)). discriminate H.
Qed.

Theorem the_backpressuring_commit_still_lands_the_write_when_it_lands_it :
  forall (o : nat), Nat.leb (queue_bound l2_demo) o = false ->
    backpressure_commit l2_demo demo_batch o l2_store (object_block l2_demo)
      = spec_commit l2_demo demo_batch o l2_store (object_block l2_demo).
Proof.
  intros o H. unfold backpressure_commit. rewrite H. reflexivity.
Qed.

(* R-10-005c's volatility, computed: recovery re-establishes a subscription
   by rescan and delivers no delta the crash may have rolled back. *)
Example the_subscription_does_not_survive_the_crash :
  spec_resume (take 2 demo_deltas) = cons Rescan nil
  /\ count_of (replay_resume (take 2 demo_deltas)) = 2
  /\ count_of (spec_resume (take 2 demo_deltas)) = 1 :=
  conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   R-14-012a at the demo: the alias table the manifest derives, and the
   ambient directory the specification does not have.
   ========================================================================= *)

Definition demo_aliases : Aliases :=
  cons (pair 0 30) (cons (pair 1 10) (cons (pair 2 40) nil)).

Definition demo_ambient : Ambient := fun n => Some (Nat.add 900 n).

Example the_alias_table_answers_its_own_names_and_no_others :
  map_over (fun n => spec_path demo_aliases demo_ambient n) (upto 5)
  = cons (Some 30) (cons (Some 10) (cons (Some 40) (cons None (cons None nil))))
  /\ map_over (fun n => escaping_path demo_aliases demo_ambient n) (upto 5)
  = cons (Some 30) (cons (Some 10) (cons (Some 40)
    (cons (Some 903) (cons (Some 904) nil))))
  /\ map_over (fun n => escaping_path demo_aliases (fun _ => None) n) (upto 5)
  = cons (Some 30) (cons (Some 10) (cons (Some 40) (cons None (cons None nil)))) :=
  conj eq_refl (conj eq_refl eq_refl).


(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared set
   R-05-164 currently makes empty, so `Closed under the global context` is
   that emptiness checked mechanically.
   ------------------------------------------------------------------------- *)

Print Assumptions bool_eqb.
Print Assumptions bool_eqb_refl.
Print Assumptions bool_eqb_true.
Print Assumptions opt_eqb.
Print Assumptions opt_eqb_refl.
Print Assumptions filter_of.
Print Assumptions prefixes.
Print Assumptions negb_true_elim.
Print Assumptions nat_eqb_sym.
Print Assumptions nat_strict_trans.
Print Assumptions any_of_intro.
Print Assumptions any_of_false.
Print Assumptions all_of_filter.
Print Assumptions filter_of_app.
Print Assumptions filter_of_none.
Print Assumptions filter_refines.
Print Assumptions count_of_app_one.
Print Assumptions count_of_app_two.
Print Assumptions mem_upto_step.
Print Assumptions mem_upto.
Print Assumptions bools_compare_both_ways.
Print Assumptions options_compare_both_ways.
Print Assumptions filtering_keeps_exactly_what_it_selects.
Print Assumptions the_prefixes_of_three_are_four.
Print Assumptions lex_leb.
Print Assumptions lex_eqb.
Print Assumptions lex_eqb_refl.
Print Assumptions lex_eqb_true.
Print Assumptions lex_leb_cons_elim.
Print Assumptions lex_leb_cons_intro_lt.
Print Assumptions lex_leb_cons_intro_eq.
Print Assumptions lex_leb_total.
Print Assumptions lex_leb_trans.
Print Assumptions lex_leb_antisym.
Print Assumptions the_lexicographic_order_decides.
Print Assumptions the_lexicographic_equality_decides.
Print Assumptions kinds_of.
Print Assumptions kind_in_range.
Print Assumptions k_inode.
Print Assumptions k_dirent.
Print Assumptions k_extent.
Print Assumptions k_xattr.
Print Assumptions k_acl.
Print Assumptions the_named_kinds_are_five_distinct_indices.
Print Assumptions ksig.
Print Assumptions k2_leb.
Print Assumptions k2_eqb.
Print Assumptions k2_eqb_refl.
Print Assumptions k2_eqb_true.
Print Assumptions l2_keys.
Print Assumptions Keyspace.
Print Assumptions the_l2_index_inherits_the_order_theorem.
Print Assumptions the_l2_index_inherits_the_read_back_theorem.
Print Assumptions the_l2_index_inherits_the_frame_theorem.
Print Assumptions the_l2_index_inherits_the_transposition_theorem.
Print Assumptions every_key_names_a_declared_kind.
Print Assumptions mk_key.
Print Assumptions entries_eqb.
Print Assumptions at_version.
Print Assumptions at_attr.
Print Assumptions in_domain.
Print Assumptions Snapshotter.
Print Assumptions spec_snapshot.
Print Assumptions AddsAtMostTheDeclaredConstant.
Print Assumptions KeepsEveryReadItAlreadyHad.
Print Assumptions ChangesNoReadAtAll.
Print Assumptions leb_add_right.
Print Assumptions add_succ_right.
Print Assumptions leb_succ_self_false.
Print Assumptions count_of_app.
Print Assumptions the_specification_snapshot_adds_at_most_the_declared_constant.
Print Assumptions the_specification_snapshot_keeps_every_read_it_already_had.
Print Assumptions the_specification_snapshot_changes_no_read_at_all.
Print Assumptions rekeyed.
Print Assumptions copy_snapshot.
Print Assumptions rekey_snapshot.
Print Assumptions bookkeeping_snapshot.
Print Assumptions leb_add_left_mono.
Print Assumptions pad.
Print Assumptions count_of_pad.
Print Assumptions count_of_rekeyed.
Print Assumptions the_padding_and_the_bookkeeping_entry_declare.
Print Assumptions Metadata.
Print Assumptions MetaReader.
Print Assumptions spec_meta.
Print Assumptions IsAViewOfTheKeyspace.
Print Assumptions the_specification_metadata_is_a_view.
Print Assumptions side_meta.
Print Assumptions derivable.
Print Assumptions admits.
Print Assumptions selects.
Print Assumptions grant.
Print Assumptions Resolver.
Print Assumptions spec_resolve.
Print Assumptions MintsNothing.
Print Assumptions AnswersOnlyTheAdmittedNamespace.
Print Assumptions ObeysTheDomain.
Print Assumptions the_specification_mints_nothing.
Print Assumptions the_specification_answers_only_the_admitted_namespace.
Print Assumptions the_specification_obeys_the_domain.
Print Assumptions spanning_selects.
Print Assumptions spanning_resolve.
Print Assumptions mint_grant.
Print Assumptions mint_resolve.
Print Assumptions ambient_resolve.
Print Assumptions the_minting_resolver_is_refuted.
Print Assumptions the_minting_resolver_keeps_every_other_obligation.
Print Assumptions the_ambient_resolver_is_refuted.
Print Assumptions the_ambient_resolver_keeps_every_other_obligation.
Print Assumptions the_spanning_resolver_is_refuted.
Print Assumptions the_spanning_resolver_keeps_every_other_obligation.
Print Assumptions demo_query.
Print Assumptions demo_selection_row.
Print Assumptions the_selection_row_declares.
Print Assumptions the_selection_reads_all_four_components.
Print Assumptions admission_reads_both_components.
Print Assumptions the_rights_comparison_is_exercised_on_its_boundary.
Print Assumptions Persister.
Print Assumptions spec_persist.
Print Assumptions WritesNoAuthority.
Print Assumptions the_specification_writes_no_authority.
Print Assumptions stamped_persist.
Print Assumptions the_stamped_key_is_refuted.
Print Assumptions the_stamped_key_still_reads_back.
Print Assumptions the_stamped_key_returns_the_retired_rights.
Print Assumptions rec3.
Print Assumptions Writer.
Print Assumptions spec_writer.
Print Assumptions split_writer.
Print Assumptions OneTransaction.
Print Assumptions the_specification_writes_one_transaction.
Print Assumptions any_of_one_transaction.
Print Assumptions all_of_scan.
Print Assumptions one_transaction_lands_all_or_nothing.
Print Assumptions CommitsOnlyWithEveryBlock.
Print Assumptions NeverObservedApart.
Print Assumptions the_object_and_the_index_are_never_observed_apart.
Print Assumptions rec3_is_intact.
Print Assumptions the_specification_writer_is_intact.
Print Assumptions commits_of_no_closing_record.
Print Assumptions the_specification_writer_commits_only_with_every_block.
Print Assumptions the_specification_writer_is_never_observed_apart.
Print Assumptions early_close_writer.
Print Assumptions the_early_close_writer_still_writes_one_transaction.
Print Assumptions nat_eqb_succ_self.
Print Assumptions the_split_writer_is_refuted.
Print Assumptions together.
Print Assumptions is_rescan.
Print Assumptions delta_eqb.
Print Assumptions Emitter.
Print Assumptions spec_emit.
Print Assumptions BoundsTheQueue.
Print Assumptions AtMostOneMarker.
Print Assumptions the_specification_bounds_the_queue.
Print Assumptions the_specification_emits_at_most_one_marker.
Print Assumptions hoard_emit.
Print Assumptions twin_marker_emit.
Print Assumptions the_hoarding_emitter_is_refuted.
Print Assumptions the_hoarding_emitter_emits_no_marker_of_its_own.
Print Assumptions the_twin_marker_emitter_is_refuted.
Print Assumptions the_twin_marker_emitter_still_bounds_the_queue.
Print Assumptions Committer.
Print Assumptions spec_commit.
Print Assumptions NeverBackpressuresTheCommit.
Print Assumptions the_specification_never_backpressures_the_commit.
Print Assumptions backpressure_commit.
Print Assumptions Deriver.
Print Assumptions spec_derive.
Print Assumptions DerivesOnlyAfterTheCommit.
Print Assumptions the_specification_derives_only_after_the_commit.
Print Assumptions prepare_derive.
Print Assumptions the_prepare_time_deriver_is_refuted.
Print Assumptions the_prepare_time_deriver_emits_the_open_transaction.
Print Assumptions Resumer.
Print Assumptions spec_resume.
Print Assumptions SurvivesNoCrash.
Print Assumptions the_specification_survives_no_crash.
Print Assumptions replay_resume.
Print Assumptions the_replaying_resumer_is_refuted.
Print Assumptions the_replaying_resumer_still_bounds_what_it_delivers.
Print Assumptions Aliases.
Print Assumptions Ambient.
Print Assumptions PathResolver.
Print Assumptions alias_look.
Print Assumptions spec_path.
Print Assumptions ReadsNoGlobalDirectory.
Print Assumptions the_specification_reads_no_global_directory.
Print Assumptions escaping_path.
Print Assumptions the_escaping_resolver_is_refuted.
Print Assumptions the_escaping_resolver_agrees_on_every_declared_alias.
Print Assumptions with_key.
Print Assumptions with_nonce.
Print Assumptions with_stored.
Print Assumptions with_digest.
Print Assumptions Volume.
Print Assumptions obs_eqb.
Print Assumptions obs_eqb_intro.
Print Assumptions holds_key.
Print Assumptions Observer.
Print Assumptions spec_obs.
Print Assumptions ext_agrees.
Print Assumptions agree_at.
Print Assumptions ext_agrees_shape.
Print Assumptions ext_agrees_content.
Print Assumptions domains_in_range.
Print Assumptions Noninterferent.
Print Assumptions LengthHidesTheContent.
Print Assumptions NonceIsPerExtent.
Print Assumptions keys_separated.
Print Assumptions separated_keys_are_injective.
Print Assumptions the_key_opens_exactly_its_own_domain.
Print Assumptions the_specification_is_noninterferent.
Print Assumptions the_specification_meets_the_obligation.
Print Assumptions length_hides_at.
Print Assumptions nonce_per_extent_at.
Print Assumptions dedup_separated.
Print Assumptions dedup_key_is_its_own.
Print Assumptions no_cross_domain_confirmation_of_file.
Print Assumptions recoverable.
Print Assumptions Eraser.
Print Assumptions spec_erase.
Print Assumptions LeavesNoKeyRecoverable.
Print Assumptions NoKeyIsResident.
Print Assumptions NoBlobSurvives.
Print Assumptions the_specification_leaves_no_key_recoverable.
Print Assumptions overwrite_erase.
Print Assumptions lock_erase.
Print Assumptions root_erase.
Print Assumptions the_overwrite_erase_is_refuted.
Print Assumptions the_overwrite_erase_still_removes_every_blob.
Print Assumptions the_lock_is_refuted_as_an_erase.
Print Assumptions the_lock_still_leaves_no_key_resident.
Print Assumptions the_root_erase_is_refuted.
Print Assumptions the_root_erase_still_kills_the_sealing_root.
Print Assumptions keyring_of.
Print Assumptions all_keyrings.
Print Assumptions there_are_eight_keyring_states.
Print Assumptions the_eight_keyring_states_are_the_whole_product.
Print Assumptions recoverability_reads_all_three_bits.
Print Assumptions which_eraser_leaves_which_state_recoverable.
Print Assumptions every_keyring_state_is_erased.
Print Assumptions Versions.
Print Assumptions Declaration.
Print Assumptions EpochRoot.
Print Assumptions sum_over.
Print Assumptions sum_over_agree.
Print Assumptions spec_epoch_root.
Print Assumptions ReadsOnlyDeclaredVersions.
Print Assumptions declared_versions_agree.
Print Assumptions the_specification_epoch_root_reads_only_declared_versions.
Print Assumptions bump_at.
Print Assumptions moves_with_every_declared_region.
Print Assumptions nosy_epoch_root.
Print Assumptions partial_epoch_root.
Print Assumptions all_epochs.
Print Assumptions the_epoch_states_are_the_whole_product.
Print Assumptions Acknowledger.
Print Assumptions spec_ack.
Print Assumptions AcknowledgesOnlyAtTheSeal.
Print Assumptions the_specification_acknowledges_only_at_the_seal.
Print Assumptions commit_ack.
Print Assumptions the_commit_acknowledger_is_refuted.
Print Assumptions the_commit_acknowledger_acknowledges_every_sealed_epoch.
Print Assumptions FreshReader.
Print Assumptions spec_fresh_read.
Print Assumptions RefusesWhatItCannotProveFresh.
Print Assumptions the_specification_refuses_what_it_cannot_prove_fresh.
Print Assumptions unsealed_read.
Print Assumptions unverified_read.
Print Assumptions the_unsealed_read_is_refuted.
Print Assumptions the_unsealed_read_still_refuses_an_unverified_version.
Print Assumptions the_unverified_read_is_refuted.
Print Assumptions the_unverified_read_still_loses_an_unsealed_epoch.
Print Assumptions which_reader_returns_which_epoch.
Print Assumptions l2_demo.
Print Assumptions the_demo_composition_declares.
Print Assumptions demo_declaration.
Print Assumptions demo_versions.
Print Assumptions the_freshness_declaration_declares.
Print Assumptions the_specification_epoch_root_covers_the_declared_class.
Print Assumptions the_nosy_epoch_root_is_refuted.
Print Assumptions the_nosy_epoch_root_still_covers_every_declared_region.
Print Assumptions the_partial_epoch_root_is_refuted.
Print Assumptions the_partial_epoch_root_reads_no_undeclared_version.
Print Assumptions the_partial_epoch_root_consults_one_named_region.
Print Assumptions demo_sealing.
Print Assumptions the_demo_sealing_declares.
Print Assumptions ratio_sealing.
Print Assumptions convergent_sealing.
Print Assumptions shared_sealing.
Print Assumptions bare_sealing.
Print Assumptions the_refuting_sealings_differ_in_one_field_each.
Print Assumptions all_sealings.
Print Assumptions there_are_five_sealings.
Print Assumptions the_four_sealing_obligations_are_independent.
Print Assumptions ext_of.
Print Assumptions vol_a.
Print Assumptions vol_b.
Print Assumptions auth0.
Print Assumptions the_two_volumes_differ_in_one_unauthorised_extent.
Print Assumptions the_volumes_declare_their_shape.
Print Assumptions vol_a_is_in_range.
Print Assumptions vol_b_is_in_range.
Print Assumptions ext_row.
Print Assumptions the_agreement_relation_reads_the_shape_and_not_the_content.
Print Assumptions bump.
Print Assumptions leak_row.
Print Assumptions which_sealing_leaks_at_which_extent.
Print Assumptions the_compressing_sealing_is_refuted.
Print Assumptions the_compressing_sealing_keeps_every_other_obligation.
Print Assumptions the_convergent_sealing_is_refuted.
Print Assumptions the_convergent_sealing_keeps_every_other_obligation.
Print Assumptions the_shared_key_sealing_is_refuted.
Print Assumptions the_shared_key_sealing_keeps_every_other_obligation.
Print Assumptions the_bare_digest_is_noninterferent.
Print Assumptions the_bare_digest_is_still_a_confirmation_oracle.
Print Assumptions open_obs.
Print Assumptions digest_obs.
Print Assumptions the_opening_observer_is_refuted.
Print Assumptions the_publishing_observer_is_refuted.
Print Assumptions the_leaky_observers_agree_where_the_reader_is_authorised.
Print Assumptions obs_zero.
Print Assumptions obs_row.
Print Assumptions the_observation_row_differs_in_one_field_apiece.
Print Assumptions the_observation_compares_every_field.
Print Assumptions l2_entries.
Print Assumptions demo_keyspace.
Print Assumptions the_one_keyspace_carries_all_four_kinds.
Print Assumptions the_keyspace_answers_the_keys_it_was_given.
Print Assumptions acl_entry.
Print Assumptions five_kind_demo.
Print Assumptions the_kind_roster_is_the_composition_s.
Print Assumptions every_key_of_an_in_range_keyspace_names_a_declared_kind.
Print Assumptions entries_compare_component_by_component.
Print Assumptions k2_transpositions.
Print Assumptions k2_deletions.
Print Assumptions k2_suffixes.
Print Assumptions k2_duplications.
Print Assumptions k2_orders.
Print Assumptions the_l2_key_order_family_is_twenty.
Print Assumptions builds_the_same_l2_index.
Print Assumptions no_adjacent_transposition_moves_the_l2_index.
Print Assumptions every_deletion_builds_a_different_l2_index.
Print Assumptions every_proper_suffix_builds_a_different_l2_index.
Print Assumptions the_l2_duplicate_wins_exactly_where_it_arrives_late.
Print Assumptions the_l2_duplicate_that_wins_is_the_later_one.
Print Assumptions the_demo_entries_declare.
Print Assumptions every_l2_key_order_builds_a_sorted_index.
Print Assumptions no_transposition_in_range_moves_the_index.
Print Assumptions every_deletion_in_range_moves_the_index.
Print Assumptions look_app_left.
Print Assumptions the_copying_snapshot_outgrows_every_declared_constant.
Print Assumptions the_copying_snapshot_is_refuted.
Print Assumptions the_copying_snapshot_keeps_every_read_it_already_had.
Print Assumptions the_rekeying_snapshot_is_refuted.
Print Assumptions the_rekeying_snapshot_keeps_the_declared_bound.
Print Assumptions the_bookkeeping_snapshot_keeps_the_declared_bound.
Print Assumptions the_bookkeeping_snapshot_keeps_every_read_it_already_had.
Print Assumptions the_bookkeeping_snapshot_is_refuted.
Print Assumptions the_three_snapshot_obligations_are_independent.
Print Assumptions demo_side.
Print Assumptions the_second_database_is_refuted.
Print Assumptions the_second_database_never_contradicts_the_keyspace.
Print Assumptions the_second_database_answers_where_the_keyspace_does_not.
Print Assumptions demo_cap.
Print Assumptions demo_inode_query.
Print Assumptions the_resolution_stays_inside_the_presented_namespace.
Print Assumptions demo_batch.
Print Assumptions l2_store.
Print Assumptions l2_view.
Print Assumptions the_batch_is_three_records_in_one_transaction.
Print Assumptions there_are_four_crash_points_over_the_batch.
Print Assumptions the_object_and_the_index_move_together_at_every_crash_point.
Print Assumptions the_split_writer_leaves_a_reader_standing_in_the_mismatch.
Print Assumptions the_early_close_writer_is_refuted.
Print Assumptions the_early_close_writer_keeps_every_other_obligation.
Print Assumptions the_split_writer_keeps_every_obligation_of_the_layer_below.
Print Assumptions demo_deltas.
Print Assumptions delta_key.
Print Assumptions is_added.
Print Assumptions the_delta_stream_declares.
Print Assumptions a_delta_at_another_version_names_another_key.
Print Assumptions an_overflowing_emission_is_a_prefix_of_the_stream.
Print Assumptions the_emitted_prefix_is_the_stream_own.
Print Assumptions the_delta_alphabet_is_three_and_the_marker_is_one_of_them.
Print Assumptions emit_counts.
Print Assumptions marker_counts.
Print Assumptions the_emission_at_every_prefix_of_the_stream.
Print Assumptions the_emission_at_the_bound_is_not_truncated.
Print Assumptions commit_row.
Print Assumptions the_commit_does_not_read_the_subscription_queue.
Print Assumptions the_backpressuring_commit_is_refuted.
Print Assumptions the_backpressuring_commit_still_lands_the_write_when_it_lands_it.
Print Assumptions the_subscription_does_not_survive_the_crash.
Print Assumptions demo_aliases.
Print Assumptions demo_ambient.
Print Assumptions the_alias_table_answers_its_own_names_and_no_others.
