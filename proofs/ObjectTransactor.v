(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ObjectTransactor.v

   Statement and reference model for the content-addressed object store, the
   system-integrity reader, and the A/B update transactor, expressed in
   [ApexTheorem.v](ApexTheorem.v)'s parameterized record style over
   [JournalIndex.v](JournalIndex.v) (see
   [object-transactor.md](../docs/implementation/contracts/object-transactor.md)).

   Governing obligations:
   - System-integrity reader and Merkle-DAG object store (R-06-001, R-06-003,
     R-06-005, R-10-001, R-10-001a, R-10-036a): immutable content-addressed
     objects named by hash with no schema version (canonical descriptor encoding
     under R-05-051a and R-05-051c), runtime verification of every read against
     both the requested content hash and reachability from the signed,
     boot-attested root, and root selection across at least two fixed-location
     copies per slot by taking the highest-version self-verifying candidate
     without reading any stored slot pointer.
   - Atomic A/B root flip, anti-rollback floor, and non-TCB storage staging
     (R-09-004, R-09-005, R-09-028, R-09-029, R-09-030, R-09-031, R-09-036a,
     R-10-002, R-10-002a, R-10-009, R-10-013, R-10-032, R-10-036, R-11-001,
     R-11-002, R-11-005, R-16-007): staging into the non-TCB four-layer storage
     stack ([JournalIndex.v](JournalIndex.v),
     [KeyspaceDomains.v](KeyspaceDomains.v)) cannot authorize an unverified or
     incomplete image; the transactor commits updates and rollbacks only when
     `verdict_backed` holds under an enrolled root (R-09-036a) and proof-checked
     admission (R-11-005), never mutates the running generation, never writes or
     re-seals the RoT anti-rollback counter (owned by
     [RotFirmware.v](RotFirmware.v)), and falls back to the retained predecessor
     on health failure when permitted by the anti-rollback floor.
   - Transfer and witnessed public commitment (R-13-001, R-13-008, R-13-009,
     R-13-023a, R-13-023b, R-13-023c): set-difference object transfer with
     per-object hash verification, checkpoint inclusion and consistency pinning
     at admission (R-13-023b), and an explicit counterexample (`R-13-023a`)
     showing that log inclusion of two signed variants does not establish
     uniform release selection.

   Key readings and open register boundaries:
   1. Merkle read-verify is split into two independent obligations—content-hash
      match and root reachability within `walk_depth`—each refuted while
      preserving the other.
   2. Root selection takes a candidate pointer argument that a compliant
      selector must ignore (R-10-001a), making pointer-reading selectors
      directly refutable.
   3. Journal staging is parameterized over [JournalIndex.v](JournalIndex.v)'s
      raw `Discipline` arms (`StopsAtTheFirstTear` vs. `SkipsTheTornRecord`) to
      demonstrate why journal commit membership alone cannot authorize an
      incomplete staged image (R-10-009).
   4. Open register boundaries remain parameterized: L0 commit representation
      (R-10-036), closed transactor operation enumeration and health-gate probe
      criteria (R-06-005, R-11-001), candidate floors exceeding a candidate's
      own security version (R-09-028, R-09-030), escalation into minimal
      recovery when the retained predecessor lies below the floor (R-09-029,
      R-11-002, R-16-007), and witness quorum-safety (R-13-023c, proved in
      [WitnessContinuity.v](WitnessContinuity.v)).

   Non-vacuity (R-05-163, R-05-165, R-05-166):
   - Every obligation is proved for the specification and refuted on generated
     journal crash/tear families (`cuts`, `tear_at`) and single-defect readers,
     selectors, flip operations, health gates, and non-monotone floor streams.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-051a R-05-051c R-05-163 R-05-165 R-05-166 R-06-001 R-06-003 R-06-005
      R-09-004 R-09-005 R-09-028 R-09-029 R-09-030 R-09-031 R-09-036a R-10-001 R-10-001a
      R-10-002 R-10-002a R-10-009 R-10-013 R-10-032 R-10-036 R-10-036a R-11-001 R-11-002
      R-11-005 R-13-001 R-13-008 R-13-009 R-13-023a R-13-023b R-13-023c R-16-007 R-16-008
      R-17-030v
   SHA256: 2e8bee9691781ff5f0bbdf77aeaf076f428c84ae5453f82ea929f6fc20ba9988
   (*| END derived |*)
   ========================================================================= *)

Require Import JournalIndex.

(* -------------------------------------------------------------------------
   The few helpers JournalIndex.v does not export. Everything else below
   comes from there: `all_of`, `any_of`, `count_of`, `map_over`, `concat_of`,
   `upto`, `take`, `drop`, `nth_opt`, `mem_of`, `only_if`, `andb_split`,
   `only_if_elim`, `nat_eqb_refl`, `nat_eqb_true`, `nat_leb_refl`,
   `nat_leb_trans` and `all_of_elim`.
   ------------------------------------------------------------------------- *)

(* The `0` is the sum of no children, a boundary rather than a magnitude. *)
Fixpoint sum_of (l : list nat) : nat :=
  match l with
  | nil => 0
  | cons x r => Nat.add x (sum_of r)
  end.

Lemma ltb_gives_leb : forall a b : nat, Nat.ltb a b = true -> Nat.leb a b = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b H.
  - reflexivity.
  - destruct b as [ | y ]; [ discriminate H | ]. exact (IH y H).
Qed.

Lemma ltb_false_gives_leb :
  forall a b : nat, Nat.ltb a b = false -> Nat.leb b a = true.
Proof.
  intros a. induction a as [ | x IH ]; intros b H.
  - destruct b as [ | y ]; [ reflexivity | discriminate H ].
  - destruct b as [ | y ]; [ reflexivity | ]. exact (IH y H).
Qed.

(* The generic member-by-index reading of a conjunction over a list. The
   exported `all_of_elim` is stated over `nat` and its membership test, and
   an object list has no such test without a decidable equality the prelude
   does not carry, so the index is what names a member here. *)
Lemma all_of_at :
  forall (A : Type) (p : A -> bool) (l : list A) (i : nat) (x : A),
    all_of p l = true -> nth_opt l i = Some x -> p x = true.
Proof.
  intros A p l. induction l as [ | y r IH ]; intros i x Hl Hn.
  - destruct i; discriminate Hn.
  - simpl in Hl. destruct (andb_split _ _ Hl) as [ Hy Hr ].
    destruct i as [ | k ].
    + simpl in Hn. congruence.
    + simpl in Hn. exact (IH k x Hr Hn).
Qed.

(* =========================================================================
   Objects, names, and the Merkle DAG (R-10-001, R-10-036a, R-13-009).

   An object is its bytes and the names of its children. Nothing else: no
   type, no schema version and no length, because R-10-036a says an object
   "is bytes named by their hash, carries no schema version, and is read by
   every generation alike".
   ========================================================================= *)

Record Obj : Type := {
  obj_bytes : nat;
  obj_kids : list nat
}.

(* A store answers a name with an object or with nothing. A total map would
   make absence unstatable, and absence is exactly what a crashed stage
   leaves behind. *)
Definition Objects : Type := nat -> option Obj.

(* =========================================================================
   The signed root (R-10-001, R-10-001a, R-09-030, R-09-036a).

   A candidate carries the Merkle root it publishes, its security version,
   the security-version floor it declares, the enrolled root it is signed
   under, its signature, and R-10-001a's own checksum beside that signature.
   ========================================================================= *)

Record SignedRoot : Type := {
  sr_root : nat;
  sr_version : nat;
  sr_floor : nat;
  sr_key : nat;
  sr_sig : nat;
  sr_sum : nat
}.

(* Reading 12: a generation is compared field by field, because a refutation
   has to compute and the prelude carries no decidable equality. *)
Definition sr_eqb (a b : SignedRoot) : bool :=
  andb (Nat.eqb (sr_root a) (sr_root b))
  (andb (Nat.eqb (sr_version a) (sr_version b))
  (andb (Nat.eqb (sr_floor a) (sr_floor b))
  (andb (Nat.eqb (sr_key a) (sr_key b))
  (andb (Nat.eqb (sr_sig a) (sr_sig b)) (Nat.eqb (sr_sum a) (sr_sum b)))))).

Lemma sr_eqb_refl : forall a : SignedRoot, sr_eqb a a = true.
Proof.
  intros a. unfold sr_eqb. repeat rewrite nat_eqb_refl. reflexivity.
Qed.

(* =========================================================================
   The composition: everything the register leaves open. Fields rather than
   Parameters, because a top-level Parameter prints as an assumption and
   fails the R-05-163 gate.
   ========================================================================= *)

Record Transactor : Type := {

  (* --- R-13-009's fixed-layout canonical encoding and R-06-003's hash, as
         the transactor sees them: two opaque functions and no format, no
         digest and no key (gap h) ---------------------------------------- *)

  encode_obj : Obj -> nat;
  content_hash : nat -> nat;

  (* --- reading 3: the declared bound that keeps the DAG walk structural -- *)

  walk_depth : nat;

  (* --- R-10-001a's root copies per slot, the count a composition constant
         with the entry's own floor of two (reading 5, gap g) -------------- *)

  root_copies : nat;

  (* --- the signed root's own bytes, its checksum, the enrolled root set
         R-09-036a makes the holder's, and the signature check ------------- *)

  encode_root : SignedRoot -> nat;
  checksum : nat -> nat;
  enrolled_root : nat -> bool;
  sig_ok : nat -> nat -> nat -> bool;

  (* --- R-11-005's proof-checked admission, which the plan's section 6
         stubs to a signature and hash check in the golden model; the
         on-device checker is verified separately ------------------------------------- *)

  admits : nat -> bool;

  (* --- R-11-001's health gate, whose content no entry states (gap d) ----- *)

  healthy : nat -> bool;

  (* --- R-13-023b's inclusion proof against a checkpoint, and the
         consistency proof against the pinned one; the reader that checks
         them is a composition field and the policy behind them is R-13-023c's ------------ *)

  included : nat -> nat -> bool;
  consistent : nat -> nat -> bool;
  (* Validated persisted-policy/epoch/transition evidence, including the
     witnessed certificate. Its bytes and quorum proof are verified in WitnessContinuity.v; inclusion and log consistency cannot establish this verdict. *)
  checkpoint_accepted : nat -> nat -> bool
}.

(* Reading 1: the name of an object is the hash of its encoding. *)
Definition address (t : Transactor) (o : Obj) : nat :=
  content_hash t (encode_obj t o).

(* Reading 5: R-10-001a's floor, stated as an obligation on a composition
   rather than as a count this file picks. *)
Definition two_copies_at_least (t : Transactor) : bool := Nat.leb 2 (root_copies t).

(* -------------------------------------------------------------------------
   The Merkle-DAG walk (reading 3).
   ------------------------------------------------------------------------- *)

Definition kids_at (st : Objects) (n : nat) : list nat :=
  match st n with
  | None => nil
  | Some o => obj_kids o
  end.

(* The `0` case reaches nothing further: a boundary and not a magnitude. *)
Fixpoint layer_walk (fuel : nat) (st : Objects) (l : list nat) : list nat :=
  match fuel with
  | 0 => l
  | S k => app l (layer_walk k st (concat_of (map_over (kids_at st) l)))
  end.

Definition reach_list (t : Transactor) (st : Objects) (root : nat) : list nat :=
  layer_walk (walk_depth t) st (cons root nil).

(* R-10-001's read-verify, at one name: the store holds something there and
   what it holds hashes to that name. *)
Definition present_and_named (t : Transactor) (st : Objects) (n : nat) : bool :=
  match st n with
  | None => false
  | Some o => Nat.eqb (address t o) n
  end.

(* And over a whole image: every name the root reaches is present and named.
   This is what the transactor checks before it commits, and it is what
   R-10-009 means by not trusting the journal. *)
Fixpoint walk_complete (fuel : nat) (st : Objects) (frontier : list nat) : bool :=
  match fuel with
  | 0 => all_of (fun n => if kids_at st n is nil then true else false) frontier
  | S k => walk_complete k st (concat_of (map_over (kids_at st) frontier))
  end.

Definition dag_intact (t : Transactor) (st : Objects) (root : nat) : bool :=
  andb (walk_complete (walk_depth t) st (cons root nil))
       (all_of (present_and_named t st) (reach_list t st root)).

(* =========================================================================
   The system-integrity reader (R-06-005, R-10-001).

   Reading 2: two obligations, stated apart because one construction
   satisfies either and fails the other.
   ========================================================================= *)

Definition Reader : Type := Transactor -> Objects -> nat -> nat -> option nat.

Definition spec_read (t : Transactor) (st : Objects) (root n : nat) : option nat :=
  if dag_intact t st root then
  if mem_of n (reach_list t st root)
  then match st n with
       | None => None
       | Some o => if Nat.eqb (address t o) n then Some (obj_bytes o) else None
       end
  else None
  else None.

(* Checking a leaf after following unverified parent links is insufficient:
   a corrupt parent can introduce an otherwise correctly named leaf. The
   cold audit authenticates the entire enumerated image before it releases
   bytes and refuses any unfinished child frontier. The path-local runtime
   reader below instead authenticates its explicit root-to-object witness;
   it does not assert completeness of unrelated subtrees. *)
Definition leaf_only_read (t : Transactor) (st : Objects) (root n : nat) : option nat :=
  if mem_of n (reach_list t st root)
  then match st n with
       | None => None
       | Some o => if Nat.eqb (address t o) n then Some (obj_bytes o) else None
       end
  else None.

(* The runtime witness is untrusted routing data. Authenticate each current
   object before inspecting its child links; the cold whole-image audit above
   retains its stronger completeness statement. See
   [the path contract](../docs/implementation/contracts/object-transactor.md#path-local-runtime-reader). *)
Fixpoint path_read_from (fuel : nat) (t : Transactor) (st : Objects)
                       (seen : list nat) (root target : nat)
                       (route : list nat) : option nat :=
  match fuel with
  | 0 => None
  | S remaining =>
      if mem_of root seen then None else
      match st root with
      | None => None
      | Some o =>
          if Nat.eqb (address t o) root then
          match route with
          | nil => if Nat.eqb root target then Some (obj_bytes o) else None
          | cons next rest =>
              if mem_of next (obj_kids o)
              then path_read_from remaining t st (cons root seen) next target rest
              else None
          end
          else None
      end
  end.

Definition path_read (t : Transactor) (st : Objects) (root target : nat)
                     (route : list nat) : option nat :=
  path_read_from (S (walk_depth t)) t st nil root target route.

Inductive AuthenticatedObjectPath (t : Transactor) (st : Objects)
    : nat -> nat -> list nat -> Prop :=
| authenticated_here : forall n o,
    st n = Some o -> address t o = n ->
    AuthenticatedObjectPath t st n n nil
| authenticated_step : forall root next target o rest,
    st root = Some o -> address t o = root ->
    mem_of next (obj_kids o) = true ->
    AuthenticatedObjectPath t st next target rest ->
    AuthenticatedObjectPath t st root target (cons next rest).

Lemma path_read_from_authenticates_every_link :
  forall fuel t st seen root target route b,
    path_read_from fuel t st seen root target route = Some b ->
    AuthenticatedObjectPath t st root target route /\
    exists o, st target = Some o /\ address t o = target /\ obj_bytes o = b.
Proof.
  intros fuel. induction fuel as [|remaining IH];
    intros t st seen root target route b H; [discriminate H|].
  cbn [path_read_from] in H.
  destruct (mem_of root seen); [discriminate H|].
  destruct (st root) as [o|] eqn:Ho; [|discriminate H].
  destruct (Nat.eqb (address t o) root) eqn:Ha; [|discriminate H].
  pose proof (nat_eqb_true _ _ Ha) as Ea.
  destruct route as [|next rest].
  - destruct (Nat.eqb root target) eqn:Ht; [|discriminate H].
    apply nat_eqb_true in Ht. subst root. inversion H; subst b.
    split.
    + apply authenticated_here with (o := o); assumption.
    + exists o. split; [exact Ho|]. split; [exact Ea|reflexivity].
  - destruct (mem_of next (obj_kids o)) eqn:Hnext; [|discriminate H].
    destruct (IH t st (cons root seen) next target rest b H) as [Hp Hn].
    split; [eapply authenticated_step; eassumption|exact Hn].
Qed.

(*| discharges: R-10-001 |*)
Theorem path_reader_authenticates_every_link :
  forall t st root target route b,
    path_read t st root target route = Some b ->
    AuthenticatedObjectPath t st root target route /\
    exists o, st target = Some o /\ address t o = target /\ obj_bytes o = b.
Proof.
  intros t st root target route b H.
  exact (path_read_from_authenticates_every_link
    (S (walk_depth t)) t st nil root target route b H).
Qed.

Lemma path_read_from_respects_depth :
  forall fuel t st seen root target route b,
    path_read_from fuel t st seen root target route = Some b ->
    Nat.leb (S (count_of route)) fuel = true.
Proof.
  intros fuel. induction fuel as [|remaining IH];
    intros t st seen root target route b H; [discriminate H|].
  cbn [path_read_from] in H.
  destruct (mem_of root seen); [discriminate H|].
  destruct (st root) as [o|]; [|discriminate H].
  destruct (Nat.eqb (address t o) root); [|discriminate H].
  destruct route as [|next rest]; [reflexivity|].
  destruct (mem_of next (obj_kids o)); [|discriminate H].
  exact (IH t st (cons root seen) next target rest b H).
Qed.

Definition ReadsOnlyAnIntactImage (rd : Reader) : Prop :=
  forall (t : Transactor) (st : Objects) (root n b : nat),
    rd t st root n = Some b -> dag_intact t st root = true.

(*| discharges: R-06-005, R-10-001 |*)
Theorem the_specification_authenticates_the_image_before_returning_bytes :
  ReadsOnlyAnIntactImage spec_read.
Proof.
  intros t st root n b H. unfold spec_read in H.
  destruct (dag_intact t st root); [reflexivity | discriminate H].
Qed.

(* The arm that believes the store: the bytes are returned without asking
   whether they hash to the name they were asked for. *)
Definition trusting_read (t : Transactor) (st : Objects) (root n : nat) : option nat :=
  if mem_of n (reach_list t st root)
  then match st n with
       | None => None
       | Some o => Some (obj_bytes o)
       end
  else None.

(* And the arm that checks the bytes and not the root, which is a
   content-addressed store with no attested root over it at all: R-10-001's
   "every read runtime-verified against the boot-attested root" is exactly
   what it drops. *)
Definition ambient_read (t : Transactor) (st : Objects) (root n : nat) : option nat :=
  match st n with
  | None => None
  | Some o => if Nat.eqb (address t o) n then Some (obj_bytes o) else None
  end.

Definition ReturnsOnlyTheNamedObject (rd : Reader) : Prop :=
  forall (t : Transactor) (st : Objects) (root n b : nat) (o : Obj),
    rd t st root n = Some b -> st n = Some o ->
    andb (Nat.eqb (address t o) n) (Nat.eqb (obj_bytes o) b) = true.

Definition ReadsNothingTheRootDoesNotReach (rd : Reader) : Prop :=
  forall (t : Transactor) (st : Objects) (root n b : nat),
    rd t st root n = Some b -> mem_of n (reach_list t st root) = true.

(* Whether a read answered at all, as a boolean, so that the positive case
   below computes rather than existentially quantifying over the bytes. *)
Definition answers (rd : Reader) (t : Transactor) (st : Objects)
                   (root n : nat) : bool :=
  if rd t st root n is None then false else true.

(* T1 (R-06-005, R-10-001). *)
(*| discharges: R-06-005, R-10-001 |*)
Theorem the_specification_read_returns_only_the_named_object :
  ReturnsOnlyTheNamedObject spec_read.
Proof.
  intros t st root n b o H Hs. unfold spec_read in H.
  destruct (dag_intact t st root); [ | discriminate H ].
  destruct (mem_of n (reach_list t st root)); [ | discriminate H ].
  rewrite Hs in H.
  destruct (Nat.eqb (address t o) n); [ | discriminate H ].
  injection H as H. rewrite H. exact (nat_eqb_refl b).
Qed.

(* T2 (R-10-001). *)
(*| discharges: R-10-001 |*)
Theorem the_specification_read_reads_nothing_the_root_does_not_reach :
  ReadsNothingTheRootDoesNotReach spec_read.
Proof.
  intros t st root n b H. unfold spec_read in H.
  destruct (dag_intact t st root); [ | discriminate H ].
  destruct (mem_of n (reach_list t st root)); [ reflexivity | discriminate H ].
Qed.

(* T3 (R-06-005): an intact image answers every name its root reaches, which
   is what stops the two obligations above from being met by a reader that
   refuses everything. *)
(*| discharges: R-06-005 |*)
Theorem an_intact_image_answers_every_reachable_name :
  forall (t : Transactor) (st : Objects) (root n : nat),
    dag_intact t st root = true -> mem_of n (reach_list t st root) = true ->
    answers spec_read t st root n = true.
Proof.
  intros t st root n Hd Hm. unfold answers, spec_read. rewrite Hd, Hm.
  unfold dag_intact in Hd. apply andb_split in Hd as [ _ Hall ].
  pose proof (all_of_elim (present_and_named t st) (reach_list t st root) n Hall Hm)
    as Hp.
  unfold present_and_named in Hp.
  destruct (st n) as [ o | ]; [ | discriminate Hp ].
  rewrite Hp. reflexivity.
Qed.

Theorem the_trusting_read_still_reads_nothing_the_root_does_not_reach :
  ReadsNothingTheRootDoesNotReach trusting_read.
Proof.
  intros t st root n b H. unfold trusting_read in H.
  destruct (mem_of n (reach_list t st root)); [ reflexivity | discriminate H ].
Qed.

Theorem the_ambient_read_still_returns_only_the_named_object :
  ReturnsOnlyTheNamedObject ambient_read.
Proof.
  intros t st root n b o H Hs. unfold ambient_read in H. rewrite Hs in H.
  destruct (Nat.eqb (address t o) n); [ | discriminate H ].
  injection H as H. rewrite H. exact (nat_eqb_refl b).
Qed.

(* =========================================================================
   Root selection (R-10-001a, reading 4).

   The selector is handed the stored pointer it must ignore, which is what
   makes the pointer-reading arm a construction rather than an absence.
   ========================================================================= *)

Fixpoint best_by (v : SignedRoot -> bool) (cs : list SignedRoot) : option SignedRoot :=
  match cs with
  | nil => None
  | cons x r =>
      if v x
      then match best_by v r with
           | None => Some x
           | Some b => if Nat.ltb (sr_version b) (sr_version x) then Some x else Some b
           end
      else best_by v r
  end.

Fixpoint first_by (v : SignedRoot -> bool) (cs : list SignedRoot) : option SignedRoot :=
  match cs with
  | nil => None
  | cons x r => if v x then Some x else first_by v r
  end.

(* R-10-001a's "verifies each candidate on its own bytes": the checksum the
   root carries beside its signature, the enrolled root R-09-036a makes the
   holder's, and the signature under it. *)
Definition root_verifies (t : Transactor) (sr : SignedRoot) : bool :=
  andb (Nat.eqb (checksum t (encode_root t sr)) (sr_sum sr))
  (andb (enrolled_root t (sr_key sr))
        (sig_ok t (sr_key sr) (encode_root t sr) (sr_sig sr))).

Definition Selector : Type :=
  Transactor -> list SignedRoot -> nat -> option SignedRoot.

Definition spec_select (t : Transactor) (cs : list SignedRoot)
                       (ptr : nat) : option SignedRoot :=
  best_by (root_verifies t) cs.

Definition pointer_select (t : Transactor) (cs : list SignedRoot)
                          (ptr : nat) : option SignedRoot :=
  match nth_opt cs ptr with
  | None => None
  | Some c => if root_verifies t c then Some c else None
  end.

Definition first_select (t : Transactor) (cs : list SignedRoot)
                        (ptr : nat) : option SignedRoot :=
  first_by (root_verifies t) cs.

Definition SelectsOnlyAVerifyingCopy (sel : Selector) : Prop :=
  forall (t : Transactor) (cs : list SignedRoot) (ptr : nat) (c : SignedRoot),
    sel t cs ptr = Some c -> root_verifies t c = true.

Definition IgnoresTheStoredPointer (sel : Selector) : Prop :=
  forall (t : Transactor) (cs : list SignedRoot) (p q : nat),
    sel t cs p = sel t cs q.

Definition TakesTheHighestVerifyingVersion (sel : Selector) : Prop :=
  forall (t : Transactor) (cs : list SignedRoot) (ptr i : nat) (c d : SignedRoot),
    sel t cs ptr = Some c -> nth_opt cs i = Some d -> root_verifies t d = true ->
    Nat.leb (sr_version d) (sr_version c) = true.

Lemma best_by_verifies :
  forall (v : SignedRoot -> bool) (cs : list SignedRoot) (c : SignedRoot),
    best_by v cs = Some c -> v c = true.
Proof.
  intros v cs. induction cs as [ | x r IH ]; intros c H.
  - discriminate H.
  - simpl in H. destruct (v x) eqn:Ex.
    + destruct (best_by v r) as [ b | ] eqn:Eb.
      * pose proof (IH b eq_refl) as Hb.
        destruct (Nat.ltb (sr_version b) (sr_version x)); congruence.
      * congruence.
    + exact (IH c H).
Qed.

Lemma best_by_none :
  forall (v : SignedRoot -> bool) (cs : list SignedRoot) (i : nat) (d : SignedRoot),
    best_by v cs = None -> nth_opt cs i = Some d -> v d = false.
Proof.
  intros v cs. induction cs as [ | x r IH ]; intros i d H Hn.
  - destruct i; discriminate Hn.
  - simpl in H. destruct (v x) eqn:Ex.
    + destruct (best_by v r) as [ b | ].
      * destruct (Nat.ltb (sr_version b) (sr_version x)); discriminate H.
      * discriminate H.
    + destruct i as [ | k ].
      * simpl in Hn. congruence.
      * simpl in Hn. exact (IH k d H Hn).
Qed.

Lemma best_by_upper :
  forall (v : SignedRoot -> bool) (cs : list SignedRoot) (c : SignedRoot)
         (i : nat) (d : SignedRoot),
    best_by v cs = Some c -> nth_opt cs i = Some d -> v d = true ->
    Nat.leb (sr_version d) (sr_version c) = true.
Proof.
  intros v cs. induction cs as [ | x r IH ]; intros c i d H Hn Hv.
  - destruct i; discriminate Hn.
  - simpl in H. destruct (v x) eqn:Ex.
    + destruct (best_by v r) as [ b | ] eqn:Eb.
      * destruct (Nat.ltb (sr_version b) (sr_version x)) eqn:El.
        -- injection H as H. rewrite <- H. destruct i as [ | k ].
           ++ simpl in Hn. injection Hn as Hn. rewrite <- Hn.
              exact (nat_leb_refl (sr_version x)).
           ++ simpl in Hn.
              exact (nat_leb_trans (sr_version d) (sr_version b) (sr_version x)
                       (IH b k d eq_refl Hn Hv) (ltb_gives_leb _ _ El)).
        -- injection H as H. rewrite <- H. destruct i as [ | k ].
           ++ simpl in Hn. injection Hn as Hn. rewrite <- Hn.
              exact (ltb_false_gives_leb _ _ El).
           ++ simpl in Hn. exact (IH b k d eq_refl Hn Hv).
      * injection H as H. rewrite <- H. destruct i as [ | k ].
        -- simpl in Hn. injection Hn as Hn. rewrite <- Hn.
           exact (nat_leb_refl (sr_version x)).
        -- simpl in Hn. rewrite (best_by_none v r k d Eb Hn) in Hv. discriminate Hv.
    + destruct i as [ | k ].
      * simpl in Hn. congruence.
      * simpl in Hn. exact (IH c k d H Hn Hv).
Qed.

Lemma first_by_verifies :
  forall (v : SignedRoot -> bool) (cs : list SignedRoot) (c : SignedRoot),
    first_by v cs = Some c -> v c = true.
Proof.
  intros v cs. induction cs as [ | x r IH ]; intros c H.
  - discriminate H.
  - simpl in H. destruct (v x) eqn:Ex.
    + congruence.
    + exact (IH c H).
Qed.

(* T4, T5 and T6 (R-10-001a). *)
(*| discharges: R-10-001a |*)
Theorem the_specification_select_takes_only_a_verifying_copy :
  SelectsOnlyAVerifyingCopy spec_select.
Proof.
  intros t cs ptr c H. unfold spec_select in H.
  exact (best_by_verifies (root_verifies t) cs c H).
Qed.

(*| discharges: R-10-001a |*)
Theorem the_specification_select_ignores_the_stored_pointer :
  IgnoresTheStoredPointer spec_select.
Proof. intros t cs p q. reflexivity. Qed.

(*| discharges: R-10-001a |*)
Theorem the_specification_select_takes_the_highest_verifying_version :
  TakesTheHighestVerifyingVersion spec_select.
Proof.
  intros t cs ptr i c d H Hn Hv. unfold spec_select in H.
  exact (best_by_upper (root_verifies t) cs c i d H Hn Hv).
Qed.

Theorem the_pointer_select_still_takes_only_a_verifying_copy :
  SelectsOnlyAVerifyingCopy pointer_select.
Proof.
  intros t cs ptr c H. unfold pointer_select in H.
  destruct (nth_opt cs ptr) as [ x | ]; [ | discriminate H ].
  destruct (root_verifies t x) eqn:E; [ | discriminate H ].
  congruence.
Qed.

Theorem the_first_verifying_select_still_takes_only_a_verifying_copy :
  SelectsOnlyAVerifyingCopy first_select.
Proof.
  intros t cs ptr c H. unfold first_select in H.
  exact (first_by_verifies (root_verifies t) cs c H).
Qed.

Theorem the_first_verifying_select_still_ignores_the_stored_pointer :
  IgnoresTheStoredPointer first_select.
Proof. intros t cs p q. reflexivity. Qed.

(* =========================================================================
   The A/B machine (R-06-005, R-09-028, R-09-031, R-11-001, R-11-002).

   Reading 5: two slots and one bit saying which is live, which is
   R-06-005's "two-slot" as a shape rather than as a count. The floor is
   read and never written (reading 6); the boot-attempt count R-09-028 pairs
   with it is the RoT's and is RotFirmware.v's, so no field here holds one.
   ========================================================================= *)

Record Ab : Type := {
  ab_b_live : bool;
  ab_slot_a : SignedRoot;
  ab_slot_b : SignedRoot;
  ab_floor : nat;
  ab_staged : bool;
  ab_admitted : bool;
  ab_retained : option SignedRoot (* previous live root, invalidated by restaging *)
}.

Definition live (ab : Ab) : SignedRoot :=
  if ab_b_live ab then ab_slot_b ab else ab_slot_a ab.

Definition spare (ab : Ab) : SignedRoot :=
  if ab_b_live ab then ab_slot_a ab else ab_slot_b ab.

(* R-09-030's bootable predicate, read of the generation the transactor has
   made live rather than of a candidate it is choosing between. *)
Definition bootable_now (ab : Ab) : bool :=
  Nat.leb (ab_floor ab) (sr_version (live ab)).

(* An operation on the machine. Reading and gap c: an arbitrary function,
   because no entry enumerates the transactor's transitions, and the four
   the plan's section 6 names are instances of this type rather than
   constructors of a closed one. *)
Definition Op : Type := Ab -> Ab.

(* The flip itself, shared by the commit and the fall-back because R-09-031
   says selection "is enacted ... as the same atomic two-slot flip an update
   takes". Both clear the staging flags, since after either the spare slot
   holds the generation the machine just left. *)
Definition toggle (ab : Ab) : Ab :=
  {| ab with
     ab_b_live := negb (ab_b_live ab);
     ab_staged := false;
     ab_admitted := false; ab_retained := Some (live ab) |}.

Lemma live_of_toggle : forall ab : Ab, live (toggle ab) = spare ab.
Proof.
  intros ab. unfold live, spare, toggle. destruct (ab_b_live ab); reflexivity.
Qed.

Lemma spare_of_toggle : forall ab : Ab, spare (toggle ab) = live ab.
Proof.
  intros ab. unfold live, spare, toggle. destruct (ab_b_live ab); reflexivity.
Qed.

Lemma floor_of_toggle : forall ab : Ab, ab_floor (toggle ab) = ab_floor ab.
Proof. intros ab. reflexivity. Qed.

(* -------------------------------------------------------------------------
   Transition one: stage. R-11-001's "the running base is never mutated" is
   the whole of what this owes, and it owes it because the spare slot is the
   only one it may write.
   ------------------------------------------------------------------------- *)

Definition stage (sr : SignedRoot) (ab : Ab) : Ab :=
  {| ab with
     ab_slot_a := if ab_b_live ab then sr else ab_slot_a ab;
     ab_slot_b := if ab_b_live ab then ab_slot_b ab else sr;
     ab_staged := true;
     ab_admitted := false; ab_retained := None |}.

(* The construction R-11-001's own sentence excludes: a stage that writes
   the slot the machine is running from. *)
Definition inplace_stage (sr : SignedRoot) (ab : Ab) : Ab :=
  {| ab with
     ab_slot_a := if ab_b_live ab then ab_slot_a ab else sr;
     ab_slot_b := if ab_b_live ab then sr else ab_slot_b ab;
     ab_staged := true;
     ab_admitted := false; ab_retained := None |}.

Lemma live_of_stage : forall (sr : SignedRoot) (ab : Ab), live (stage sr ab) = live ab.
Proof.
  intros sr ab. unfold live, stage. destruct (ab_b_live ab); reflexivity.
Qed.

Lemma spare_of_stage : forall (sr : SignedRoot) (ab : Ab), spare (stage sr ab) = sr.
Proof.
  intros sr ab. unfold spare, stage. destruct (ab_b_live ab); reflexivity.
Qed.

Lemma live_of_inplace_stage :
  forall (sr : SignedRoot) (ab : Ab), live (inplace_stage sr ab) = sr.
Proof.
  intros sr ab. unfold live, inplace_stage. destruct (ab_b_live ab); reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Transition two: verify. Five conjuncts, each owed by a different entry,
   and the computed table below shows each is independently falsifiable.
   ------------------------------------------------------------------------- *)

Definition stage_admissible (t : Transactor) (st : Objects) (ab : Ab) : bool :=
  andb (root_verifies t (spare ab))
  (andb (Nat.leb (ab_floor ab) (sr_version (spare ab)))
  (andb (Nat.leb (sr_floor (spare ab)) (sr_version (spare ab)))
  (andb (dag_intact t st (sr_root (spare ab)))
        (admits t (sr_root (spare ab)))))).

(* The same five as a list, so that a family of candidates reads as a table
   rather than as five separate checks. *)
Definition verify_conjuncts (t : Transactor) (st : Objects) (ab : Ab) : list bool :=
  cons (root_verifies t (spare ab))
  (cons (Nat.leb (ab_floor ab) (sr_version (spare ab)))
  (cons (Nat.leb (sr_floor (spare ab)) (sr_version (spare ab)))
  (cons (dag_intact t st (sr_root (spare ab)))
  (cons (admits t (sr_root (spare ab))) nil)))).

Definition verify (t : Transactor) (st : Objects) (ab : Ab) : Ab :=
  {| ab with ab_admitted := andb (ab_staged ab) (stage_admissible t st ab) |}.

(* Reading 7: the verdict field is backed where the verify step would have
   set it, which is the predicate the flip's safety is stated over. *)
Definition verdict_backed (t : Transactor) (st : Objects) (ab : Ab) : bool :=
  only_if (ab_admitted ab) (stage_admissible t st ab).

(* The verify step copies every slot field and the floor from the machine it
   was given, so the two lemmas below hold by conversion alone. *)
Lemma live_of_verify :
  forall (t : Transactor) (st : Objects) (ab : Ab), live (verify t st ab) = live ab.
Proof. intros t st ab. reflexivity. Qed.

Lemma stage_admissible_of_verify :
  forall (t : Transactor) (st : Objects) (ab : Ab),
    stage_admissible t st (verify t st ab) = stage_admissible t st ab.
Proof. intros t st ab. reflexivity. Qed.

Lemma admitted_of_verify :
  forall (t : Transactor) (st : Objects) (ab : Ab),
    ab_admitted (verify t st ab) = andb (ab_staged ab) (stage_admissible t st ab).
Proof. intros t st ab. reflexivity. Qed.

(* -------------------------------------------------------------------------
   Transition three: flip. R-06-005's atomic two-slot root flip, taken only
   for a stage the verify step admitted; refusing is the fail-closed
   polarity R-17-030v states, the running generation untouched.
   ------------------------------------------------------------------------- *)

Definition flip (ab : Ab) : Ab :=
  if andb (ab_staged ab) (ab_admitted ab) then toggle ab else ab.

(* The construction R-11-005 and R-06-005 exclude: a flip that commits
   whatever sits in the spare slot. *)
Definition eager_flip (ab : Ab) : Ab := toggle ab.

(* The construction R-10-032's "the A/B transactor re-seals nothing at
   commit" excludes: a flip that takes the candidate's declared floor as the
   new floor, which lets a signed generation declaring a lower floor undo a
   shipped security update. *)
Definition resealing_flip (ab : Ab) : Ab :=
  if andb (ab_staged ab) (ab_admitted ab)
  then {| ab with
          ab_b_live := negb (ab_b_live ab);
          ab_floor := sr_floor (spare ab);
          ab_staged := false;
          ab_admitted := false; ab_retained := Some (live ab) |}
  else ab.

(* And the one that separates the two floor obligations: R-09-028's own
   raise, performed by the transactor instead of by the RoT. It never
   lowers the floor and it writes one, which is what shows *monotone* and
   *not the transactor's to write* are two obligations and not one. The
   advance itself is RotFirmware.v's statement; this is the construction,
   not a second specification of it. *)
Definition raising_flip (ab : Ab) : Ab :=
  if andb (ab_staged ab) (ab_admitted ab)
  then {| ab with
          ab_b_live := negb (ab_b_live ab);
          ab_floor := if Nat.ltb (ab_floor ab) (sr_floor (spare ab))
                      then sr_floor (spare ab) else ab_floor ab;
          ab_staged := false;
          ab_admitted := false; ab_retained := Some (live ab) |}
  else ab.

(* -------------------------------------------------------------------------
   Transition four: the health-gated return. R-11-002's automatic path,
   which is R-09-031's same flip run backwards and bounded by the same
   floor.
   ------------------------------------------------------------------------- *)

Definition retained_matches (ab : Ab) : bool :=
  match ab_retained ab with None => false | Some sr => sr_eqb sr (spare ab) end.

Definition fallback_admissible (t : Transactor) (st : Objects) (ab : Ab) : bool :=
  andb (negb (ab_staged ab)) (andb (retained_matches ab) (stage_admissible t st ab)).

Definition fall_back (t : Transactor) (st : Objects) (ab : Ab) : Ab :=
  if fallback_admissible t st ab then toggle ab else ab.

Theorem fallback_checks_retention_and_authentication : forall t st ab,
  fallback_admissible t st ab = true ->
  ab_staged ab = false /\ retained_matches ab = true /\
  root_verifies t (spare ab) = true /\
  dag_intact t st (sr_root (spare ab)) = true /\ admits t (sr_root (spare ab)) = true.
Proof.
  intros t st ab H. unfold fallback_admissible in H.
  apply andb_split in H as [Hs H]. apply andb_split in H as [Hr H].
  unfold stage_admissible in H. apply andb_split in H as [Hv H].
  apply andb_split in H as [_ H]. apply andb_split in H as [_ H].
  apply andb_split in H as [Hd Ha].
  destruct (ab_staged ab); [ discriminate Hs | ].
  repeat split; assumption || reflexivity.
Qed.

Theorem restaging_cannot_be_used_as_a_predecessor : forall t st sr ab,
  fall_back t st (stage sr ab) = stage sr ab.
Proof. intros. reflexivity. Qed.

(* The construction R-09-030 excludes: a return that pins the predecessor
   whatever its security version. *)
Definition blind_fall_back (ab : Ab) : Ab := toggle ab.

(* Settling is what a healthy generation gets: the staging flags clear and
   nothing else moves. *)
Definition settle (ab : Ab) : Ab :=
  {| ab with ab_staged := false; ab_admitted := false |}.

(* Settling copies both slots and the live bit unchanged, so this one holds
   by conversion too. *)
Lemma live_of_settle : forall ab : Ab, live (settle ab) = live ab.
Proof. intros ab. reflexivity. Qed.

(* =========================================================================
   The obligations on an operation, and what each construction breaks.
   ========================================================================= *)

Definition LeavesTheRunningGenerationAlone (op : Op) : Prop :=
  forall ab : Ab, sr_eqb (live (op ab)) (live ab) = true.

Definition CommitsOnlyAnAdmittedStage (op : Op) : Prop :=
  forall ab : Ab,
    andb (ab_staged ab) (ab_admitted ab) = false ->
    sr_eqb (live (op ab)) (live ab) = true.

Definition WritesNoFloor (op : Op) : Prop :=
  forall ab : Ab, Nat.eqb (ab_floor (op ab)) (ab_floor ab) = true.

Definition NeverLowersTheFloor (op : Op) : Prop :=
  forall ab : Ab, Nat.leb (ab_floor ab) (ab_floor (op ab)) = true.

Definition KeepsTheLiveGenerationBootable (op : Op) : Prop :=
  forall ab : Ab, bootable_now ab = true -> bootable_now (op ab) = true.

Definition KeepsABackedMachineBootable (t : Transactor) (st : Objects)
                                       (op : Op) : Prop :=
  forall ab : Ab,
    verdict_backed t st ab = true -> bootable_now ab = true ->
    bootable_now (op ab) = true.

Definition PreservesBacking (t : Transactor) (st : Objects) (op : Op) : Prop :=
  forall ab : Ab, verdict_backed t st ab = true -> verdict_backed t st (op ab) = true.

(* An image the live root can actually be served from, which is the property
   R-10-009 puts between the transactor and the store beneath it. *)
Definition servable (t : Transactor) (st : Objects) (ab : Ab) : bool :=
  dag_intact t st (sr_root (live ab)).

(* T7 (R-11-001): staging does not touch the running generation. *)
(*| discharges: R-11-001 |*)
Theorem the_specification_stage_leaves_the_running_generation_alone :
  forall sr : SignedRoot, LeavesTheRunningGenerationAlone (stage sr).
Proof.
  intros sr ab. rewrite (live_of_stage sr ab). exact (sr_eqb_refl (live ab)).
Qed.

Theorem the_specification_verify_leaves_the_running_generation_alone :
  forall (t : Transactor) (st : Objects),
    LeavesTheRunningGenerationAlone (verify t st).
Proof.
  intros t st ab. rewrite (live_of_verify t st ab). exact (sr_eqb_refl (live ab)).
Qed.

(* T8 (R-11-005, R-06-005): the flip commits nothing the verify step
   refused, and refusing leaves the running generation exactly where it
   stood. *)
(*| discharges: R-11-005, R-06-005 |*)
Theorem the_specification_flip_commits_only_an_admitted_stage :
  CommitsOnlyAnAdmittedStage flip.
Proof.
  intros ab H. unfold flip. rewrite H. exact (sr_eqb_refl (live ab)).
Qed.

(* T9 (R-10-032, R-09-028): no transition of the transactor writes the
   floor, which is what makes the counter the RoT's alone. *)
(*| discharges: R-10-032 |*)
Theorem the_specification_transitions_write_no_floor :
  forall (t : Transactor) (st : Objects) (sr : SignedRoot),
    WritesNoFloor (stage sr) /\ WritesNoFloor (verify t st)
    /\ WritesNoFloor flip /\ WritesNoFloor (fall_back t st) /\ WritesNoFloor settle.
Proof.
  intros t st sr. split; [ | split; [ | split; [ | split ] ] ]; intros ab.
  - exact (nat_eqb_refl (ab_floor ab)).
  - exact (nat_eqb_refl (ab_floor ab)).
  - unfold flip. destruct (andb (ab_staged ab) (ab_admitted ab));
      exact (nat_eqb_refl (ab_floor ab)).
  - unfold fall_back. destruct (fallback_admissible t st ab);
      exact (nat_eqb_refl (ab_floor ab)).
  - exact (nat_eqb_refl (ab_floor ab)).
Qed.

(* T10 (R-09-028): and none of them lowers it, which is the weaker of the
   two and the one the raising construction below keeps. *)
(*| discharges: R-09-028 |*)
Theorem the_specification_flip_never_lowers_the_floor : NeverLowersTheFloor flip.
Proof.
  intros ab. unfold flip. destruct (andb (ab_staged ab) (ab_admitted ab));
    exact (nat_leb_refl (ab_floor ab)).
Qed.

(* T11 (R-09-030): the return verifies the retained predecessor and both floor guards
   at its own site, independently of the staged-admission verdict. *)
(*| discharges: R-09-030, R-11-002 |*)
Theorem the_specification_fall_back_keeps_the_live_generation_bootable :
  forall t st, KeepsTheLiveGenerationBootable (fall_back t st).
Proof.
  intros t st ab H. unfold fall_back.
  destruct (fallback_admissible t st ab) eqn:E; [ | exact H ].
  unfold fallback_admissible in E. apply andb_split in E as [_ E].
  apply andb_split in E as [_ E]. unfold stage_admissible in E.
  apply andb_split in E as [_ E]. apply andb_split in E as [Hfloor _].
  unfold bootable_now. rewrite live_of_toggle. rewrite floor_of_toggle. exact Hfloor.
Qed.

Theorem the_specification_stage_and_verify_keep_the_live_generation_bootable :
  forall (t : Transactor) (st : Objects) (sr : SignedRoot),
    KeepsTheLiveGenerationBootable (stage sr)
    /\ KeepsTheLiveGenerationBootable (verify t st).
Proof.
  intros t st sr. split.
  - intros ab H. unfold bootable_now. rewrite (live_of_stage sr ab). exact H.
  - intros ab H. unfold bootable_now. rewrite (live_of_verify t st ab). exact H.
Qed.

(* T12 (R-09-030, R-11-005): the flip's own safety, which is where reading 7
   is load-bearing. The flip reads a boolean field; what makes committing on
   it safe is that the verify step backs it, and the next theorem is that
   the specification's verify does. *)
(*| discharges: R-09-030, R-11-005 |*)
Theorem the_specification_flip_keeps_a_backed_machine_bootable :
  forall (t : Transactor) (st : Objects), KeepsABackedMachineBootable t st flip.
Proof.
  intros t st ab Hb Hboot. unfold flip.
  destruct (andb (ab_staged ab) (ab_admitted ab)) eqn:E; [ | exact Hboot ].
  destruct (andb_split _ _ E) as [ _ Ha ].
  unfold verdict_backed in Hb.
  assert (Hadm : stage_admissible t st ab = true) by exact (only_if_elim _ _ Hb Ha).
  unfold stage_admissible in Hadm.
  destruct (andb_split _ _ Hadm) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ Hfl _ ].
  unfold bootable_now. rewrite live_of_toggle. rewrite floor_of_toggle. exact Hfl.
Qed.

(* T13 (R-06-005, R-10-009): and the same backing is what makes the root the
   flip publishes one the store can serve, which is the whole content of
   *commits by flipping the signed root, not by trusting the journal*. *)
(*| discharges: R-06-005, R-10-009 |*)
Theorem the_specification_flip_makes_live_only_a_servable_root :
  forall (t : Transactor) (st : Objects) (ab : Ab),
    verdict_backed t st ab = true -> servable t st ab = true ->
    servable t st (flip ab) = true.
Proof.
  intros t st ab Hb Hs. unfold flip.
  destruct (andb (ab_staged ab) (ab_admitted ab)) eqn:E; [ | exact Hs ].
  destruct (andb_split _ _ E) as [ _ Ha ].
  unfold verdict_backed in Hb.
  assert (Hadm : stage_admissible t st ab = true) by exact (only_if_elim _ _ Hb Ha).
  unfold stage_admissible in Hadm.
  destruct (andb_split _ _ Hadm) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  destruct (andb_split _ _ H3) as [ Hdag _ ].
  unfold servable. rewrite live_of_toggle. exact Hdag.
Qed.

(* T14 (R-11-005): the specification's verify backs its own verdict, so a
   machine that has been through it satisfies the premise of T12 and T13. *)
(*| discharges: R-11-005 |*)
Theorem the_specification_verify_backs_its_own_verdict :
  forall (t : Transactor) (st : Objects) (ab : Ab),
    verdict_backed t st (verify t st ab) = true.
Proof.
  intros t st ab. unfold verdict_backed.
  rewrite admitted_of_verify, stage_admissible_of_verify.
  destruct (ab_staged ab); destruct (stage_admissible t st ab); reflexivity.
Qed.

(* T15: and every transition leaves a backed machine backed, which is what
   lets the run theorem below quantify over lists of them. Three of the four
   clear the verdict and one sets it from the check itself. *)
(*| discharges: R-11-005 |*)
Theorem the_specification_transitions_preserve_backing :
  forall (t : Transactor) (st : Objects) (sr : SignedRoot),
    PreservesBacking t st (stage sr) /\ PreservesBacking t st (verify t st)
    /\ PreservesBacking t st flip /\ PreservesBacking t st (fall_back t st)
    /\ PreservesBacking t st settle.
Proof.
  intros t st sr. split; [ | split; [ | split; [ | split ] ] ].
  - intros ab _. reflexivity.
  - intros ab _. exact (the_specification_verify_backs_its_own_verdict t st ab).
  - intros ab H. unfold flip.
    destruct (andb (ab_staged ab) (ab_admitted ab)); [ reflexivity | exact H ].
  - intros ab H. unfold fall_back.
    destruct (fallback_admissible t st ab); [ reflexivity | exact H ].
  - intros ab _. reflexivity.
Qed.
(* =========================================================================
   Runs. Gap c is that no entry enumerates the transactor's transitions, so
   what is stated here is a fold over an arbitrary list of operations and
   the four above are instances of it.
   ========================================================================= *)

Fixpoint run_of (ops : list Op) (ab : Ab) : Ab :=
  match ops with
  | nil => ab
  | cons f r => run_of r (f ab)
  end.

Fixpoint every_op (P : Op -> Prop) (ops : list Op) : Prop :=
  match ops with
  | nil => True
  | cons f r => and (P f) (every_op P r)
  end.

(* T16 (R-10-032): a run of operations that write no floor writes none. *)
(*| discharges: R-10-032 |*)
Theorem a_run_of_floor_free_operations_writes_no_floor :
  forall ops : list Op, every_op WritesNoFloor ops -> WritesNoFloor (run_of ops).
Proof.
  intros ops. induction ops as [ | f r IH ]; intros H ab.
  - exact (nat_eqb_refl (ab_floor ab)).
  - destruct H as [ Hf Hr ]. simpl.
    assert (Hx : ab_floor (run_of r (f ab)) = ab_floor (f ab))
      by exact (nat_eqb_true _ _ (IH Hr (f ab))).
    rewrite Hx. exact (Hf ab).
Qed.

(* T17 (R-09-030): and a run of the transactor's own operations on a backed,
   bootable machine leaves it bootable, which is the composition the four
   transitions are for. *)
(*| discharges: R-09-030 |*)
Theorem a_backed_run_keeps_the_live_generation_bootable :
  forall (t : Transactor) (st : Objects) (ops : list Op),
    every_op (PreservesBacking t st) ops ->
    every_op (KeepsABackedMachineBootable t st) ops ->
    forall ab : Ab,
      verdict_backed t st ab = true -> bootable_now ab = true ->
      bootable_now (run_of ops ab) = true.
Proof.
  intros t st ops. induction ops as [ | f r IH ]; intros Hb Hk ab Hab Hboot.
  - exact Hboot.
  - destruct Hb as [ Hbf Hbr ]. destruct Hk as [ Hkf Hkr ]. simpl.
    exact (IH Hbr Hkr (f ab) (Hbf ab Hab) (Hkf ab Hab Hboot)).
Qed.

(* =========================================================================
   The anti-rollback floor over time (R-09-028, R-09-030, reading 8).

   The floor is the RoT's counter as the transactor reads it, so what this
   file states is not the advance (RotFirmware.v's) but the consequence:
   under a monotone floor a generation once refused stays refused.
   ========================================================================= *)

Definition Floors : Type := nat -> nat.

Definition Monotone (f : Floors) : Prop :=
  forall i : nat, Nat.leb (f i) (f (S i)) = true.

Definition admissible_at (f : Floors) (i : nat) (sr : SignedRoot) : bool :=
  Nat.leb (f i) (sr_version sr).

Lemma monotone_reaches :
  forall (f : Floors) (k i : nat), Monotone f -> Nat.leb (f i) (f (Nat.add k i)) = true.
Proof.
  intros f k. induction k as [ | n IH ]; intros i H.
  - exact (nat_leb_refl (f i)).
  - simpl.
    exact (nat_leb_trans (f i) (f (Nat.add n i)) (f (S (Nat.add n i)))
             (IH i H) (H (Nat.add n i))).
Qed.

(* T18 (R-09-028, R-09-030): the anti-rollback property proper. *)
(*| discharges: R-09-028, R-09-030 |*)
Theorem a_refusal_under_a_monotone_floor_is_permanent :
  forall (f : Floors) (k i : nat) (sr : SignedRoot),
    Monotone f -> admissible_at f i sr = false ->
    admissible_at f (Nat.add k i) sr = false.
Proof.
  intros f k i sr Hm H. unfold admissible_at in H. unfold admissible_at.
  destruct (Nat.leb (f (Nat.add k i)) (sr_version sr)) eqn:E; [ | reflexivity ].
  rewrite (nat_leb_trans (f i) (f (Nat.add k i)) (sr_version sr)
             (monotone_reaches f k i Hm) E) in H.
  discriminate H.
Qed.

(* =========================================================================
   The health gate (R-11-001, R-11-002, R-16-008).

   Two obligations, because a gate that always returns loses every update
   and a gate that never returns loses the automatic rollback.
   ========================================================================= *)

Definition Gate : Type := Transactor -> Objects -> Ab -> Ab.

Definition spec_gate (t : Transactor) (st : Objects) (ab : Ab) : Ab :=
  if healthy t (sr_root (live ab)) then settle ab else fall_back t st ab.

(* The construction R-11-001's health-gated auto-rollback excludes: a gate
   that settles whatever booted. *)
Definition stubborn_gate (t : Transactor) (st : Objects) (ab : Ab) : Ab := settle ab.

(* The construction that loses the update instead: a gate that returns
   whether or not the generation is healthy. *)
Definition eager_gate (t : Transactor) (st : Objects) (ab : Ab) : Ab := fall_back t st ab.

(* And the one R-09-030 excludes: a gate that returns through the floor. *)
Definition reckless_gate (t : Transactor) (st : Objects) (ab : Ab) : Ab :=
  if healthy t (sr_root (live ab)) then settle ab else blind_fall_back ab.

Definition ReturnsOnAnUnhealthyGeneration (g : Gate) : Prop :=
  forall (t : Transactor) (st : Objects) (ab : Ab),
    healthy t (sr_root (live ab)) = false ->
    fallback_admissible t st ab = true ->
    sr_eqb (live (g t st ab)) (spare ab) = true.

Definition KeepsAHealthyGeneration (g : Gate) : Prop :=
  forall (t : Transactor) (st : Objects) (ab : Ab),
    healthy t (sr_root (live ab)) = true -> sr_eqb (live (g t st ab)) (live ab) = true.

Definition GateKeepsTheLiveGenerationBootable (g : Gate) : Prop :=
  forall (t : Transactor) (st : Objects) (ab : Ab),
    bootable_now ab = true -> bootable_now (g t st ab) = true.

(* T19 and T20 (R-11-001, R-11-002). *)
(*| discharges: R-11-001, R-11-002 |*)
Theorem the_specification_gate_returns_on_an_unhealthy_generation :
  ReturnsOnAnUnhealthyGeneration spec_gate.
Proof.
  intros t st ab Hh Hf. unfold spec_gate. rewrite Hh. unfold fall_back. rewrite Hf.
  rewrite live_of_toggle. exact (sr_eqb_refl (spare ab)).
Qed.

(*| discharges: R-11-001 |*)
Theorem the_specification_gate_keeps_a_healthy_generation :
  KeepsAHealthyGeneration spec_gate.
Proof.
  intros t st ab Hh. unfold spec_gate. rewrite Hh. rewrite live_of_settle.
  exact (sr_eqb_refl (live ab)).
Qed.

(* T21 (R-09-030): and it never returns below the floor, which is gap f's
   case: the return is refused and this file takes no third path. *)
(*| discharges: R-09-030 |*)
Theorem the_specification_gate_keeps_the_live_generation_bootable :
  GateKeepsTheLiveGenerationBootable spec_gate.
Proof.
  intros t st ab H. unfold spec_gate. destruct (healthy t (sr_root (live ab))).
  - unfold bootable_now. rewrite live_of_settle. exact H.
  - exact (the_specification_fall_back_keeps_the_live_generation_bootable t st ab H).
Qed.

Theorem the_stubborn_gate_still_keeps_a_healthy_generation :
  KeepsAHealthyGeneration stubborn_gate.
Proof.
  intros t st ab Hh. unfold stubborn_gate. rewrite live_of_settle.
  exact (sr_eqb_refl (live ab)).
Qed.

Theorem the_stubborn_gate_still_keeps_the_live_generation_bootable :
  GateKeepsTheLiveGenerationBootable stubborn_gate.
Proof.
  intros t st ab H. unfold stubborn_gate. unfold bootable_now.
  rewrite live_of_settle. exact H.
Qed.

Theorem the_eager_gate_still_returns_on_an_unhealthy_generation :
  ReturnsOnAnUnhealthyGeneration eager_gate.
Proof.
  intros t st ab Hh Hf. unfold eager_gate. unfold fall_back. rewrite Hf.
  rewrite live_of_toggle. exact (sr_eqb_refl (spare ab)).
Qed.

Theorem the_reckless_gate_still_returns_on_an_unhealthy_generation :
  ReturnsOnAnUnhealthyGeneration reckless_gate.
Proof.
  intros t st ab Hh Hf. unfold reckless_gate. rewrite Hh. unfold blind_fall_back.
  rewrite live_of_toggle. exact (sr_eqb_refl (spare ab)).
Qed.

(* =========================================================================
   Staging through the L0 journal, over an arbitrary recovery discipline
   (reading 9, gaps a and b; R-10-002, R-10-009, R-10-036, R-13-001,
   R-13-008).

   R-13-008 makes a transfer a set difference, so what is staged is the
   objects the destination lacks; R-10-036 commits them as a single L0
   transaction and names no mechanism, so the closing record is
   JournalIndex.v's own `rec_closes` flag on the last of them and no
   representation is asserted.
   ========================================================================= *)

Definition stage_rec (t : Transactor) (txn len : nat) (o : Obj) : Rec :=
  {| rec_txn := txn; rec_block := address t o; rec_value := obj_bytes o;
     rec_closes := false; rec_len := len; rec_landed := len |}.

Definition closing_rec (t : Transactor) (txn len : nat) (o : Obj) : Rec :=
  {| rec_txn := txn; rec_block := address t o; rec_value := obj_bytes o;
     rec_closes := true; rec_len := len; rec_landed := len |}.

Fixpoint stage_journal (t : Transactor) (txn len : nat) (os : list Obj) : list Rec :=
  match os with
  | nil => nil
  | cons o r =>
      match r with
      | nil => cons (closing_rec t txn len o) nil
      | cons _ _ => cons (stage_rec t txn len o) (stage_journal t txn len r)
      end
  end.

(* Whether a staged object is there after recovery under a given discipline,
   which is two questions and not one: some committed record of the surviving
   prefix wrote its name, and the value under that name is its bytes. A stale
   block that happens to hold the right bytes passes the second and fails the
   first, which is what the computed check below shows. *)
Definition present_under (t : Transactor) (cut : Discipline) (j : list Rec)
                         (o : Obj) : bool :=
  writes_committed (cut j) (commits (cut j)) (address t o).

Definition bytes_under (t : Transactor) (cut : Discipline) (j : list Rec)
                       (base : Store) (o : Obj) : bool :=
  Nat.eqb (recover_under cut j base (address t o)) (obj_bytes o).

Definition landed_under (t : Transactor) (cut : Discipline) (j : list Rec)
                        (base : Store) (o : Obj) : bool :=
  andb (present_under t cut j o) (bytes_under t cut j base o).

Definition every_object_landed (t : Transactor) (cut : Discipline) (j : list Rec)
                               (base : Store) (os : list Obj) : bool :=
  all_of (landed_under t cut j base) os.

(* What the journal itself says about the staging transaction, which is the
   verdict R-10-009 says the transactor does not take. *)
Definition journal_says_committed (cut : Discipline) (j : list Rec)
                                  (txn : nat) : bool :=
  commits (cut j) txn.

Fixpoint find_obj (t : Transactor) (n : nat) (os : list Obj) : option Obj :=
  match os with
  | nil => None
  | cons o r => if Nat.eqb (address t o) n then Some o else find_obj t n r
  end.

(* The store a recovery leaves: the prior objects, plus each staged object
   exactly where it landed. A staged object that did not land is absent
   rather than wrong, which is the shape a content-addressed store can have
   at all: bytes that do not hash to their name are unreachable through
   their name, so what a torn stage costs is presence. *)
Definition landed_view (t : Transactor) (cut : Discipline) (j : list Rec)
                       (base : Store) (os : list Obj) (prior : Objects) : Objects :=
  fun n => match find_obj t n os with
           | None => prior n
           | Some o => if landed_under t cut j base o then Some o else None
           end.

(* T22 (R-10-002, R-10-036): the landed test is discipline-agnostic and
   member-wise, so every obligation stated over it holds under an arbitrary
   discipline and neither of JournalIndex.v's arms is preferred here. *)
(*| discharges: R-10-002 |*)
Theorem every_discipline_admits_only_a_landed_generation :
  forall (t : Transactor) (cut : Discipline) (j : list Rec) (base : Store)
         (os : list Obj) (i : nat) (o : Obj),
    every_object_landed t cut j base os = true -> nth_opt os i = Some o ->
    landed_under t cut j base o = true.
Proof.
  intros t cut j base os i o H Hn.
  exact (all_of_at Obj (landed_under t cut j base) os i o H Hn).
Qed.

(* T23 (R-10-001, R-10-036a): a staged object the view answers is the object
   it was asked for, whichever discipline decided which of them landed. This
   is the content-addressing invariant of the view itself: the view cannot
   answer a name with bytes that do not hash to it. *)
(*| discharges: R-10-001, R-10-036a |*)
Theorem the_landed_view_names_every_staged_object_it_answers :
  forall (t : Transactor) (cut : Discipline) (j : list Rec) (base : Store)
         (os : list Obj) (prior : Objects) (n : nat) (o : Obj),
    find_obj t n os = Some o ->
    landed_view t cut j base os prior n = Some o ->
    Nat.eqb (address t o) n = true.
Proof.
  intros t cut j base os prior n o Hf _.
  revert Hf. induction os as [ | x r IH ]; intros Hf.
  - discriminate Hf.
  - simpl in Hf. destruct (Nat.eqb (address t x) n) eqn:E.
    + congruence.
    + exact (IH Hf).
Qed.
(* =========================================================================
   Witnessed public commitment (R-13-023a, R-13-023b, R-13-023c, R-17-030v,
   reading 10).

   The device-side half only: an inclusion proof for the base image's root
   and for every package identity the roster names, against a checkpoint
   consistent with the last one the device pinned. The policy that decides
   which checkpoints are acceptable is R-13-023c's (see [WitnessContinuity.v](WitnessContinuity.v)), and the reader
   that checks the proofs; both are fields here.
   ========================================================================= *)

Definition commitment_ok (t : Transactor) (pinned offered : nat)
                         (ids : list nat) : bool :=
  andb (checkpoint_accepted t pinned offered)
       (andb (consistent t pinned offered) (all_of (included t offered) ids)).

Definition Pinner : Type := Transactor -> nat -> nat -> nat.

Definition spec_pin (t : Transactor) (pinned offered : nat) : nat :=
  if checkpoint_accepted t pinned offered
  then if consistent t pinned offered then offered else pinned
  else pinned.

(* The construction R-13-023b's "refusing one inconsistent with it"
   excludes: a device that pins whatever checkpoint it was handed. *)
Definition trusting_pin (t : Transactor) (pinned offered : nat) : nat := offered.

Definition NeverPinsAnInconsistentCheckpoint (pn : Pinner) : Prop :=
  forall (t : Transactor) (pinned offered : nat),
    consistent t pinned offered = false -> pn t pinned offered = pinned.

Definition AdmitsOnlyLoggedIdentities : Prop :=
  forall (t : Transactor) (pinned offered : nat) (ids : list nat)
         (i n : nat),
    commitment_ok t pinned offered ids = true -> nth_opt ids i = Some n ->
    included t offered n = true.

(* T24 (R-13-023b): every identity an admitted roster names carries an
   inclusion proof against the checkpoint that was offered. *)
(*| discharges: R-13-023b |*)
Theorem the_commitment_check_admits_only_logged_identities :
  AdmitsOnlyLoggedIdentities.
Proof.
  intros t pinned offered ids i n H Hn. unfold commitment_ok in H.
  destruct (andb_split _ _ H) as [ _ Hlog ].
  destruct (andb_split _ _ Hlog) as [ _ Hi ].
  exact (all_of_at nat (included t offered) ids i n Hi Hn).
Qed.

(* T25 (R-13-023b, R-17-030v): and a checkpoint the pin refuses moves
   nothing, which is the fail-closed polarity R-17-030v states. *)
(*| discharges: R-13-023b, R-17-030v |*)
Theorem the_specification_pin_refuses_an_inconsistent_checkpoint :
  NeverPinsAnInconsistentCheckpoint spec_pin.
Proof.
  intros t pinned offered H. unfold spec_pin. rewrite H.
  destruct (checkpoint_accepted t pinned offered); reflexivity.
Qed.

(*| discharges: R-13-023b, R-13-023c, R-17-030v |*)
Theorem public_commitment_and_pinning_require_accepted_witness_evidence :
  forall (t : Transactor) (pinned offered : nat) (ids : list nat),
    checkpoint_accepted t pinned offered = false ->
    commitment_ok t pinned offered ids = false /\ spec_pin t pinned offered = pinned.
Proof.
  intros t pinned offered ids H. unfold commitment_ok, spec_pin. rewrite H.
  split; reflexivity.
Qed.

(* The full public admission path binds the candidate root itself, before
   the authenticated package roster, so a caller cannot omit the base image
   from the commitment check. `verify` is the local signature/hash/proof
   check; this wrapper is the public-update authorization consumed by flip.
   Authenticating the roster and checkpoint bytes remains the validator's
   interface obligation, not a property of a freely supplied list. *)
Definition verify_public (t : Transactor) (st : Objects) (ab : Ab)
    (pinned offered : nat) (packages : list nat) : Ab :=
  {| ab with
     ab_admitted := andb (ab_admitted (verify t st ab))
       (commitment_ok t pinned offered (cons (sr_root (spare ab)) packages)) |}.

(*| discharges: R-13-023b, R-13-023c, R-17-030v |*)
Theorem public_admission_binds_the_candidate_and_every_package :
  forall t st ab pinned offered packages,
  ab_admitted (verify_public t st ab pinned offered packages) = true ->
  ab_admitted (verify t st ab) = true /\
  checkpoint_accepted t pinned offered = true /\ consistent t pinned offered = true /\
  included t offered (sr_root (spare ab)) = true /\ all_of (included t offered) packages = true.
Proof.
  intros t st ab pinned offered packages H.
  change (andb (ab_admitted (verify t st ab))
    (commitment_ok t pinned offered (cons (sr_root (spare ab)) packages)) = true) in H.
  destruct (andb_split _ _ H) as [Hlocal Hpublic]. unfold commitment_ok in Hpublic.
  destruct (andb_split _ _ Hpublic) as [Hpolicy Hlog].
  destruct (andb_split _ _ Hlog) as [Hconsistent Hids].
  simpl in Hids. destruct (andb_split _ _ Hids) as [Hbase Hpackages].
  repeat split; assumption.
Qed.

Theorem public_admission_preserves_backing_and_the_floor :
  forall t st ab pinned offered packages,
  verdict_backed t st (verify_public t st ab pinned offered packages) = true /\
  ab_floor (verify_public t st ab pinned offered packages) = ab_floor ab.
Proof.
  intros t st ab pinned offered packages. split; [|reflexivity].
  change (only_if (andb (ab_admitted (verify t st ab))
    (commitment_ok t pinned offered (cons (sr_root (spare ab)) packages)))
    (stage_admissible t st ab) = true).
  rewrite admitted_of_verify.
  destruct (ab_staged ab); destruct (stage_admissible t st ab);
    destruct (commitment_ok t pinned offered (cons (sr_root (spare ab)) packages)); reflexivity.
Qed.

(* =========================================================================
   The demo composition (gap i). Every value below is a witness carrying no
   composition claim; the shape is what it is for.

   Two generations sharing two leaves: the base image is rooted at the name
   of an object naming leaves 7 and 9, and the successor at one naming leaf 7
   and two new leaves, which is R-13-008's set difference with the shared
   leaf transferred by nobody.
   ========================================================================= *)

Definition leaf_seven : Obj := {| obj_bytes := 7; obj_kids := nil |}.
Definition leaf_nine : Obj := {| obj_bytes := 9; obj_kids := nil |}.
Definition leaf_eleven : Obj := {| obj_bytes := 11; obj_kids := nil |}.
Definition leaf_thirteen : Obj := {| obj_bytes := 13; obj_kids := nil |}.

Definition base_root_obj : Obj :=
  {| obj_bytes := 1; obj_kids := cons 7 (cons 9 nil) |}.

Definition other_root_obj : Obj :=
  {| obj_bytes := 3; obj_kids := cons 7 (cons 9 nil) |}.

Definition next_root_obj : Obj :=
  {| obj_bytes := 2; obj_kids := cons 7 (cons 11 (cons 13 nil)) |}.

(* The demo encoding makes a parent's name cover its children's, which is
   the Merkle property at demo scale and nothing about any real digest. *)
Definition demo_encode_obj (o : Obj) : nat :=
  Nat.add (obj_bytes o) (sum_of (obj_kids o)).

Definition demo_hash (x : nat) : nat := x.

Definition demo_encode_root (sr : SignedRoot) : nat :=
  Nat.add (sr_root sr) (Nat.add (sr_version sr) (sr_floor sr)).

Definition demo_checksum (x : nat) : nat := x.

Definition demo_enrolled (k : nat) : bool := Nat.eqb k 3.

Definition demo_sig_ok (k m s : nat) : bool := Nat.eqb s (Nat.add m k).

(* R-11-005's verdict, which is a property of the artifact's proofs and not
   of whether the store holds its bytes: the two are separate conjuncts and
   the candidate family below has one failing each. *)
Definition demo_admits (n : nat) : bool :=
  orb (Nat.eqb n 17) (orb (Nat.eqb n 33) (Nat.eqb n 41)).

Definition demo_healthy (n : nat) : bool := negb (Nat.eqb n 33).

Definition demo_included (c n : nat) : bool :=
  andb (Nat.eqb c 70) (orb (Nat.eqb n 33) (Nat.eqb n 41)).

Definition demo_consistent (p o : nat) : bool := Nat.leb p o.

Definition demo_checkpoint_accepted (p o : nat) : bool := Nat.eqb o 70.

Definition demo_transactor : Transactor :=
  {| encode_obj := demo_encode_obj;
     content_hash := demo_hash;
     walk_depth := 2;
     root_copies := 2;
     encode_root := demo_encode_root;
     checksum := demo_checksum;
     enrolled_root := demo_enrolled;
     sig_ok := demo_sig_ok;
     admits := demo_admits;
     healthy := demo_healthy;
     included := demo_included;
     consistent := demo_consistent;
     checkpoint_accepted := demo_checkpoint_accepted |}.

Definition demo_objects : Objects := fun n =>
  if Nat.eqb n 7 then Some leaf_seven
  else if Nat.eqb n 9 then Some leaf_nine
  else if Nat.eqb n 17 then Some base_root_obj
  else if Nat.eqb n 19 then Some other_root_obj
  else None.

Definition missing_sibling_objects : Objects := fun n =>
  if Nat.eqb n 9 then None else demo_objects n.

Definition unverified_parent_objects : Objects := fun n =>
  if Nat.eqb n 17
  then Some {| obj_bytes := 2; obj_kids := cons 7 (cons 9 nil) |}
  else demo_objects n.

Example path_reads_the_root_and_its_authenticated_child :
  path_read demo_transactor demo_objects 17 17 nil = Some 1 /\
  path_read demo_transactor demo_objects 17 7 (cons 7 nil) = Some 7 :=
  conj eq_refl eq_refl.

Example runtime_path_does_not_read_an_unrelated_missing_sibling :
  path_read demo_transactor missing_sibling_objects 17 7 (cons 7 nil) = Some 7 /\
  spec_read demo_transactor missing_sibling_objects 17 7 = None :=
  conj eq_refl eq_refl.

Example runtime_path_refuses_parent_link_root_and_depth_substitutions :
  path_read demo_transactor unverified_parent_objects 17 7 (cons 7 nil) = None /\
  path_read demo_transactor demo_objects 17 5 (cons 5 nil) = None /\
  path_read demo_transactor demo_objects 19 7 (cons 9 nil) = None /\
  path_read_from 1 demo_transactor demo_objects nil 17 7 (cons 7 nil) = None :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

Definition cyclic_path_objects : Objects := fun n =>
  if Nat.eqb n 5
  then Some {| obj_bytes := 0; obj_kids := cons 5 nil |}
  else None.

Example runtime_path_refuses_a_revisited_authenticated_node :
  path_read demo_transactor cyclic_path_objects 5 5 (cons 5 nil) = None := eq_refl.

Definition chain_path_objects : Objects := fun n =>
  match n with
  | 0 => None
  | S 0 => Some {| obj_bytes := 1; obj_kids := nil |}
  | S (S previous) => Some {| obj_bytes := 1; obj_kids := cons (S previous) nil |}
  end.

Fixpoint descending_route (steps : nat) : list nat :=
  match steps with
  | 0 => nil
  | S previous => cons (S previous) (descending_route previous)
  end.

Example generated_path_lengths_return_exact_bytes :
  map_over (fun steps =>
    path_read {| demo_transactor with walk_depth := steps |}
      chain_path_objects (S steps) 1 (descending_route steps)) (upto 8)
  = map_over (fun _ => Some 1) (upto 8) := eq_refl.

Example generated_path_depth_exhaustion_refuses :
  map_over (fun steps =>
    path_read_from steps demo_transactor chain_path_objects nil
      (S steps) 1 (descending_route steps)) (upto 8)
  = map_over (fun _ => (None : option nat)) (upto 8) := eq_refl.

(* A store answering a name with bytes that do not hash to it. *)
Definition rogue_leaf : Obj := {| obj_bytes := 8; obj_kids := nil |}.

Definition rogue_objects : Objects := fun n =>
  if Nat.eqb n 9 then Some rogue_leaf else demo_objects n.

(* And one holding a well-named object no root reaches. *)
Definition stray_leaf : Obj := {| obj_bytes := 5; obj_kids := nil |}.

Definition strayed_objects : Objects := fun n =>
  if Nat.eqb n 5 then Some stray_leaf else demo_objects n.

Example the_demo_objects_are_named_by_their_own_encoding :
  map_over (address demo_transactor)
    (cons leaf_seven (cons leaf_nine (cons leaf_eleven (cons leaf_thirteen
    (cons base_root_obj (cons other_root_obj (cons next_root_obj nil)))))))
  = cons 7 (cons 9 (cons 11 (cons 13 (cons 17 (cons 19 (cons 33 nil))))))
  := eq_refl.

Example the_base_image_is_three_objects_and_the_successor_reaches_four :
  pair (reach_list demo_transactor demo_objects 17)
       (dag_intact demo_transactor demo_objects 17)
  = pair (cons 17 (cons 7 (cons 9 nil))) true := eq_refl.

Example the_rogue_store_is_not_intact_and_the_strayed_one_is :
  pair (dag_intact demo_transactor rogue_objects 17)
       (dag_intact demo_transactor strayed_objects 17)
  = pair false true := eq_refl.

(* -------------------------------------------------------------------------
   The signed roots. `sr_sum` is the checksum of the encoding and `sr_sig`
   the signature under the enrolled key, so a copy whose write tore after the
   signature and before the checksum is one field apart from a whole one.
   ------------------------------------------------------------------------- *)

Definition base_root : SignedRoot :=
  {| sr_root := 17; sr_version := 5; sr_floor := 4; sr_key := 3;
     sr_sig := 29; sr_sum := 26 |}.

Definition torn_copy : SignedRoot :=
  {| sr_root := 17; sr_version := 5; sr_floor := 4; sr_key := 3;
     sr_sig := 29; sr_sum := 0 |}.

Definition next_root : SignedRoot :=
  {| sr_root := 33; sr_version := 6; sr_floor := 5; sr_key := 3;
     sr_sig := 47; sr_sum := 44 |}.

Definition stale_root : SignedRoot :=
  {| sr_root := 17; sr_version := 2; sr_floor := 1; sr_key := 3;
     sr_sig := 23; sr_sum := 20 |}.

Definition overreaching_root : SignedRoot :=
  {| sr_root := 33; sr_version := 6; sr_floor := 9; sr_key := 3;
     sr_sig := 51; sr_sum := 48 |}.

Definition dangling_root : SignedRoot :=
  {| sr_root := 41; sr_version := 6; sr_floor := 4; sr_key := 3;
     sr_sig := 54; sr_sum := 51 |}.

Definition unadmitted_root : SignedRoot :=
  {| sr_root := 19; sr_version := 6; sr_floor := 4; sr_key := 3;
     sr_sig := 32; sr_sum := 29 |}.

Definition low_declared_root : SignedRoot :=
  {| sr_root := 33; sr_version := 6; sr_floor := 1; sr_key := 3;
     sr_sig := 43; sr_sum := 40 |}.

Definition opt_root (o : option SignedRoot) : option nat :=
  match o with
  | None => None
  | Some sr => Some (sr_root sr)
  end.

Definition demo_copies : list SignedRoot := cons torn_copy (cons base_root nil).

Definition lone_copy : list SignedRoot := cons torn_copy nil.

Definition low_first_copies : list SignedRoot :=
  cons stale_root (cons base_root nil).

Example which_roots_verify_on_their_own_bytes :
  map_over (root_verifies demo_transactor)
    (cons base_root (cons torn_copy (cons next_root (cons stale_root
    (cons overreaching_root (cons dangling_root (cons unadmitted_root
    (cons low_declared_root nil))))))))
  = cons true (cons false (cons true (cons true (cons true (cons true
    (cons true (cons true nil))))))) := eq_refl.

(* R-10-001a's own consequence, computed: a torn copy costs a copy where the
   composition carries two and costs the generation where it carries one,
   which is why that entry states a floor of two per slot. *)
(*| discharges: R-10-001a |*)
Example a_torn_copy_costs_a_copy_and_not_the_generation :
  pair (pair (two_copies_at_least demo_transactor)
             (opt_root (spec_select demo_transactor demo_copies 0)))
       (opt_root (spec_select demo_transactor lone_copy 0))
  = pair (pair true (Some 17)) None := eq_refl.

(* And what reading a stored pointer costs on the same two copies. *)
(*| discharges: R-10-001a |*)
Example the_stored_pointer_loses_what_the_enumeration_keeps :
  pair (opt_root (spec_select demo_transactor demo_copies 0))
       (opt_root (pointer_select demo_transactor demo_copies 0))
  = pair (Some 17) None := eq_refl.

(* The two selections reach a copy of the same root and not the same
   generation, which is why R-10-001a's rule is about the version and not
   about the name: a stale copy of the base image verifies on its own bytes
   exactly as the current one does. *)
Example both_selections_reach_a_copy_of_the_same_root :
  pair (opt_root (spec_select demo_transactor low_first_copies 0))
       (opt_root (first_select demo_transactor low_first_copies 0))
  = pair (Some 17) (Some 17) := eq_refl.

Example the_two_selections_differ_in_the_version_they_reach :
  pair (map_over sr_version (cons stale_root (cons base_root nil)))
       (pair (match spec_select demo_transactor low_first_copies 0 with
              | None => 0 | Some c => sr_version c end)
             (match first_select demo_transactor low_first_copies 0 with
              | None => 0 | Some c => sr_version c end))
  = pair (cons 2 (cons 5 nil)) (pair 5 2) := eq_refl.

Theorem the_pointer_select_is_refuted : ~ IgnoresTheStoredPointer pointer_select.
Proof.
  intros H. specialize (H demo_transactor demo_copies 0 1). discriminate H.
Qed.

Theorem the_first_verifying_select_is_refuted :
  ~ TakesTheHighestVerifyingVersion first_select.
Proof.
  intros H.
  specialize (H demo_transactor low_first_copies 0 1 stale_root base_root
                eq_refl eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_trusting_read_is_refuted : ~ ReturnsOnlyTheNamedObject trusting_read.
Proof.
  intros H.
  specialize (H demo_transactor rogue_objects 17 9 8 rogue_leaf eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_ambient_read_is_refuted : ~ ReadsNothingTheRootDoesNotReach ambient_read.
Proof.
  intros H.
  specialize (H demo_transactor strayed_objects 17 5 5 eq_refl). discriminate H.
Qed.

(* What each reader answers at the two names that separate them. *)
(*| discharges: R-06-005, R-10-001 |*)
Example what_the_three_readers_answer :
  pair (pair (spec_read demo_transactor rogue_objects 17 9)
             (trusting_read demo_transactor rogue_objects 17 9))
       (pair (spec_read demo_transactor strayed_objects 17 5)
             (ambient_read demo_transactor strayed_objects 17 5))
  = pair (pair None (Some 8)) (pair None (Some 5)) := eq_refl.
(* -------------------------------------------------------------------------
   The staged generation and its journal. Three new objects, one L0
   transaction, and the middle record torn by JournalIndex.v's own
   generator rather than by a record written out here.
   ------------------------------------------------------------------------- *)

Definition staged_objs : list Obj :=
  cons leaf_eleven (cons leaf_thirteen (cons next_root_obj nil)).

Definition demo_txn : nat := 1.
Definition demo_len : nat := 2.

Definition demo_base : Store := fun _ => 0.
Definition stale_base : Store := fun n => n.

Definition whole_j : list Rec :=
  stage_journal demo_transactor demo_txn demo_len staged_objs.

Definition torn_j : list Rec := tear_at 1 1 whole_j.

Example the_staging_journal_is_three_records_over_one_transaction :
  pair (pair (map_over rec_block whole_j) (map_over rec_value whole_j))
       (pair (map_over rec_closes whole_j) (map_over intact torn_j))
  = pair (pair (cons 11 (cons 13 (cons 33 nil)))
               (cons 11 (cons 13 (cons 2 nil))))
         (pair (cons false (cons false (cons true nil)))
               (cons true (cons false (cons true nil)))) := eq_refl.

Definition whole_view : Objects :=
  landed_view demo_transactor scan whole_j demo_base staged_objs demo_objects.

Definition scan_view : Objects :=
  landed_view demo_transactor scan torn_j demo_base staged_objs demo_objects.

Definition sieve_view : Objects :=
  landed_view demo_transactor sieve torn_j demo_base staged_objs demo_objects.

(* Reading 9 and gap b, machine-checked: the same crashed staging journal
   is an uncommitted transaction under the stopping arm and a committed one
   under the skipping arm, and under the skipping arm the transaction it
   reports committed is missing one of its objects. R-10-002a requires complete
   authenticated prefix redo; these raw comparisons implement neither its
   complete protocol nor an admitted suffix-salvage alternative. *)
(*| discharges: R-10-002, R-10-036 |*)
Example the_two_recovery_readings_disagree_about_the_stage :
  pair (journal_says_committed scan torn_j demo_txn)
       (journal_says_committed sieve torn_j demo_txn)
  = pair false true := eq_refl.

(*| discharges: R-10-009 |*)
Example what_each_recovery_reading_lands :
  pair (map_over (landed_under demo_transactor scan torn_j demo_base) staged_objs)
       (map_over (landed_under demo_transactor sieve torn_j demo_base) staged_objs)
  = pair (cons false (cons false (cons false nil)))
         (cons true (cons false (cons true nil))) := eq_refl.

(* And the presence conjunct is load-bearing: over a store whose untouched
   block happens to hold the staged object's own bytes, the byte test passes
   for an object no committed record wrote. *)
(*| discharges: R-10-009 |*)
Example the_presence_conjunct_catches_what_the_bytes_conjunct_does_not :
  pair (bytes_under demo_transactor sieve torn_j stale_base leaf_thirteen)
       (pair (present_under demo_transactor sieve torn_j leaf_thirteen)
             (landed_under demo_transactor sieve torn_j stale_base leaf_thirteen))
  = pair true (pair false false) := eq_refl.

(* The whole staging question at both arms: the journal's verdict, the
   store's completeness, and whether the successor root is servable. *)
(*| discharges: R-10-009, R-10-002 |*)
Example the_stage_is_complete_under_neither_arm_of_a_crashed_journal :
  pair (pair (every_object_landed demo_transactor scan torn_j demo_base staged_objs)
             (every_object_landed demo_transactor sieve torn_j demo_base staged_objs))
       (pair (dag_intact demo_transactor scan_view 33)
             (dag_intact demo_transactor sieve_view 33))
  = pair (pair false false) (pair false false) := eq_refl.

Example an_uncrashed_stage_lands_whole :
  pair (every_object_landed demo_transactor scan whole_j demo_base staged_objs)
       (dag_intact demo_transactor whole_view 33)
  = pair true true := eq_refl.

(* -------------------------------------------------------------------------
   The machine. Live is the base generation and the spare slot holds a
   retained generation below the floor, which is what makes an unguarded
   flip and an unguarded return both observable.
   ------------------------------------------------------------------------- *)

Definition demo_ab : Ab :=
  {| ab_b_live := false; ab_slot_a := base_root; ab_slot_b := stale_root;
     ab_floor := 4; ab_staged := false; ab_admitted := false; ab_retained := Some stale_root |}.

Definition staged_ab : Ab := stage next_root demo_ab.
Definition verified_ab : Ab := verify demo_transactor whole_view staged_ab.
Definition flipped_ab : Ab := flip verified_ab.

(* The machine the health-gated return leaves: the base generation live
   again, with the successor it refused retained in the spare slot at or
   above the floor, which is the state a gate that returns unconditionally
   is observable on. *)
Definition settled_ab : Ab := spec_gate demo_transactor whole_view flipped_ab.

(* The four transitions at the demo, read off the generation each leaves
   live: staging does not move it, verify admits, the flip commits the
   successor, and the health gate returns to the predecessor because
   `demo_healthy` refuses 33. *)
(*| discharges: R-11-001, R-06-005 |*)
Example the_four_transitions_at_the_demo :
  pair (pair (sr_root (live staged_ab)) (ab_admitted verified_ab))
       (pair (sr_root (live flipped_ab))
             (sr_root (live (spec_gate demo_transactor whole_view flipped_ab))))
  = pair (pair 17 true) (pair 33 17) := eq_refl.

Example the_floor_is_unmoved_across_the_whole_update :
  map_over ab_floor (cons demo_ab (cons staged_ab (cons verified_ab
    (cons flipped_ab (cons (spec_gate demo_transactor whole_view flipped_ab) nil)))))
  = cons 4 (cons 4 (cons 4 (cons 4 (cons 4 nil)))) := eq_refl.

Example every_state_of_the_update_is_bootable :
  map_over bootable_now (cons demo_ab (cons staged_ab (cons verified_ab
    (cons flipped_ab (cons (spec_gate demo_transactor whole_view flipped_ab) nil)))))
  = cons true (cons true (cons true (cons true (cons true nil)))) := eq_refl.

(* The five admission conjuncts, one candidate failing each and one failing
   none, so no conjunct of the verify step is dead. The fourth and fifth are
   two different questions about one root: whether the store can serve it,
   and whether the checker admitted its proofs. *)
(*| discharges: R-11-005, R-10-001, R-09-030 |*)
Example the_five_verify_conjuncts_are_independent :
  map_over (fun sr => verify_conjuncts demo_transactor whole_view (stage sr demo_ab))
    (cons next_root (cons torn_copy (cons stale_root (cons overreaching_root
    (cons dangling_root (cons unadmitted_root nil))))))
  = cons (cons true (cons true (cons true (cons true (cons true nil)))))
    (cons (cons false (cons true (cons true (cons true (cons true nil)))))
    (cons (cons true (cons false (cons true (cons true (cons true nil)))))
    (cons (cons true (cons true (cons false (cons true (cons true nil)))))
    (cons (cons true (cons true (cons true (cons false (cons true nil)))))
    (cons (cons true (cons true (cons true (cons true (cons false nil)))))
    nil))))) := eq_refl.

Example the_five_conjuncts_admit_exactly_the_candidate_that_passes_all_of_them :
  map_over (fun sr => ab_admitted (verify demo_transactor whole_view (stage sr demo_ab)))
    (cons next_root (cons torn_copy (cons stale_root (cons overreaching_root
    (cons dangling_root (cons unadmitted_root nil))))))
  = cons true (cons false (cons false (cons false (cons false (cons false nil)))))
  := eq_refl.

(* =========================================================================
   The refuting constructions at the machine.
   ========================================================================= *)

(* A stage that writes the running slot. R-11-001's "the running base is
   never mutated" is what it breaks; it writes no floor, which is what shows
   the two obligations are separate. *)
Theorem the_inplace_stage_is_refuted :
  ~ LeavesTheRunningGenerationAlone (inplace_stage next_root).
Proof. intros H. specialize (H demo_ab). discriminate H. Qed.

Theorem the_inplace_stage_still_writes_no_floor :
  forall sr : SignedRoot, WritesNoFloor (inplace_stage sr).
Proof. intros sr ab. exact (nat_eqb_refl (ab_floor ab)). Qed.

(*| discharges: R-11-001 |*)
Example the_inplace_stage_overwrites_the_generation_the_machine_is_running :
  pair (sr_root (live (stage next_root demo_ab)))
       (sr_root (live (inplace_stage next_root demo_ab)))
  = pair 17 33 := eq_refl.

(* A flip that commits whatever is staged. On a machine whose spare slot
   holds a retained generation below the floor, it commits one R-09-030 says
   is not bootable. *)
Theorem the_eager_flip_is_refuted : ~ CommitsOnlyAnAdmittedStage eager_flip.
Proof. intros H. specialize (H demo_ab eq_refl). discriminate H. Qed.

Theorem the_eager_flip_is_refuted_as_bootability_preserving :
  ~ KeepsABackedMachineBootable demo_transactor whole_view eager_flip.
Proof. intros H. specialize (H demo_ab eq_refl eq_refl). discriminate H. Qed.

Theorem the_eager_flip_still_writes_no_floor : WritesNoFloor eager_flip.
Proof. intros ab. exact (nat_eqb_refl (ab_floor ab)). Qed.

(*| discharges: R-09-030, R-11-005 |*)
Example the_eager_flip_commits_a_generation_below_the_floor :
  pair (pair (bootable_now (flip demo_ab)) (bootable_now (eager_flip demo_ab)))
       (pair (sr_root (live (eager_flip demo_ab)))
             (sr_version (live (eager_flip demo_ab))))
  = pair (pair true false) (pair 17 2) := eq_refl.

(* A flip that re-seals the floor from the candidate. `low_declared_root` is
   an admissible successor declaring a lower floor than the device holds, so
   this is a signed, admitted, proof-checked generation whose commit would
   un-fix a shipped security update. *)
Definition low_declared_ab : Ab :=
  verify demo_transactor whole_view (stage low_declared_root demo_ab).

Theorem the_resealing_flip_is_refuted_as_floor_free :
  ~ WritesNoFloor resealing_flip.
Proof. intros H. specialize (H low_declared_ab). discriminate H. Qed.

Theorem the_resealing_flip_is_refuted_as_monotone :
  ~ NeverLowersTheFloor resealing_flip.
Proof. intros H. specialize (H low_declared_ab). discriminate H. Qed.

Theorem the_resealing_flip_still_commits_only_an_admitted_stage :
  CommitsOnlyAnAdmittedStage resealing_flip.
Proof.
  intros ab H. unfold resealing_flip. rewrite H. exact (sr_eqb_refl (live ab)).
Qed.

(* And the construction that separates the two floor obligations: it
   performs R-09-028's own raise, so it never lowers the floor and it does
   write one, which R-10-032 says the transactor does not. *)
Theorem the_raising_flip_is_refuted_as_floor_free : ~ WritesNoFloor raising_flip.
Proof. intros H. specialize (H verified_ab). discriminate H. Qed.

Theorem the_raising_flip_never_lowers_the_floor : NeverLowersTheFloor raising_flip.
Proof.
  intros ab. unfold raising_flip.
  destruct (andb (ab_staged ab) (ab_admitted ab)); [ | exact (nat_leb_refl (ab_floor ab)) ].
  simpl. destruct (Nat.ltb (ab_floor ab) (sr_floor (spare ab))) eqn:E.
  - exact (ltb_gives_leb _ _ E).
  - exact (nat_leb_refl (ab_floor ab)).
Qed.

(*| discharges: R-10-032, R-09-028 |*)
Example what_the_three_flips_leave_the_floor_at :
  pair (map_over ab_floor (cons (flip low_declared_ab)
         (cons (resealing_flip low_declared_ab) (cons (raising_flip low_declared_ab) nil))))
       (map_over ab_floor (cons (flip verified_ab)
         (cons (resealing_flip verified_ab) (cons (raising_flip verified_ab) nil))))
  = pair (cons 4 (cons 1 (cons 4 nil))) (cons 4 (cons 5 (cons 5 nil))) := eq_refl.

(* A health gate that never returns, and one that returns through the floor.
   `stranded_ab` is gap f's case: the live generation is unhealthy and the
   retained predecessor is below the floor. *)
Definition stranded_ab : Ab :=
  {| ab_b_live := true; ab_slot_a := stale_root; ab_slot_b := next_root;
     ab_floor := 4; ab_staged := false; ab_admitted := false; ab_retained := Some stale_root |}.

Theorem the_stubborn_gate_is_refuted : ~ ReturnsOnAnUnhealthyGeneration stubborn_gate.
Proof.
  intros H. specialize (H demo_transactor whole_view flipped_ab eq_refl eq_refl).
  discriminate H.
Qed.

Theorem the_eager_gate_is_refuted : ~ KeepsAHealthyGeneration eager_gate.
Proof.
  intros H. specialize (H demo_transactor whole_view settled_ab eq_refl).
  vm_compute in H. discriminate H.
Qed.

Theorem the_reckless_gate_is_refuted :
  ~ GateKeepsTheLiveGenerationBootable reckless_gate.
Proof.
  intros H. specialize (H demo_transactor whole_view stranded_ab eq_refl). discriminate H.
Qed.

(*| discharges: R-11-001, R-09-030 |*)
Example what_the_four_gates_leave_live :
  pair (map_over (fun g => sr_root (live (g demo_transactor whole_view flipped_ab)))
         (cons spec_gate (cons stubborn_gate (cons eager_gate (cons reckless_gate nil)))))
       (map_over (fun g => bootable_now (g demo_transactor whole_view stranded_ab))
         (cons spec_gate (cons stubborn_gate (cons eager_gate (cons reckless_gate nil)))))
  = pair (cons 17 (cons 33 (cons 17 (cons 17 nil))))
         (cons true (cons true (cons true (cons false nil)))) := eq_refl.

(* Gap f as a computed check rather than a remark: with the retained
   predecessor below the floor, the specification's gate refuses the return
   and leaves the unhealthy generation live. R-16-007's boot counting into a
   minimal recovery state and R-09-029's signed recovery generation are
   where that case goes and neither is modelled here. *)
(*| discharges: R-11-002, R-09-030 |*)
Example a_predecessor_below_the_floor_is_not_returned_to :
  pair (pair (healthy demo_transactor (sr_root (live stranded_ab)))
             (sr_version (spare stranded_ab)))
       (sr_root (live (spec_gate demo_transactor whole_view stranded_ab)))
  = pair (pair false 2) 33 := eq_refl.

(* =========================================================================
   The journal-trusting transactor: the construction R-10-009's own sentence
   excludes, and the place the raw recovery-discipline comparison reaches an
   admission verdict.
   ========================================================================= *)

Definition journal_trusting_verify (cut : Discipline) (j : list Rec) (txn : nat)
                                   (ab : Ab) : Ab :=
  {| ab with ab_admitted := andb (ab_staged ab) (journal_says_committed cut j txn) |}.

(* Under the stopping arm the journal reports the stage uncommitted and the
   trusting transactor refuses; under the skipping arm it reports it
   committed and the trusting transactor flips to a root its own store
   cannot serve. The specification's verify refuses under both, because it
   reads the store rather than the journal's verdict. *)
(*| discharges: R-10-009, R-10-002 |*)
Example the_journal_trusting_verdict_moves_with_the_recovery_discipline :
  pair (pair (ab_admitted (journal_trusting_verify scan torn_j demo_txn staged_ab))
             (ab_admitted (journal_trusting_verify sieve torn_j demo_txn staged_ab)))
       (pair (ab_admitted (verify demo_transactor scan_view staged_ab))
             (ab_admitted (verify demo_transactor sieve_view staged_ab)))
  = pair (pair false true) (pair false false) := eq_refl.

(*| discharges: R-10-009 |*)
Example the_journal_trusting_flip_makes_live_an_unservable_root :
  pair (servable demo_transactor sieve_view
         (flip (journal_trusting_verify sieve torn_j demo_txn staged_ab)))
       (servable demo_transactor sieve_view
         (flip (verify demo_transactor sieve_view staged_ab)))
  = pair false true := eq_refl.

(* And the verdict that moved is not backed, which is the general statement
   the two computed pairs above are one instance of. *)
(*| discharges: R-10-009, R-11-005 |*)
Example the_journal_trusting_verdict_is_not_backed :
  pair (verdict_backed demo_transactor sieve_view
         (journal_trusting_verify sieve torn_j demo_txn staged_ab))
       (verdict_backed demo_transactor sieve_view
         (verify demo_transactor sieve_view staged_ab))
  = pair false true := eq_refl.

(* =========================================================================
   The floor stream's refutation and the transparency checks.
   ========================================================================= *)

Definition rising_floor : Floors := fun i => Nat.add 4 i.

Definition dipping_floor : Floors := fun i => if Nat.eqb i 0 then 4 else 1.

Theorem the_dipping_floor_is_not_monotone : ~ Monotone dipping_floor.
Proof. intros H. specialize (H 0). discriminate H. Qed.

(*| discharges: R-09-028, R-09-030 |*)
Example the_dipping_floor_re_admits_a_generation_it_already_refused :
  pair (map_over (fun i => admissible_at rising_floor i stale_root)
                 (upto 3))
       (map_over (fun i => admissible_at dipping_floor i stale_root)
                 (upto 3))
  = pair (cons false (cons false (cons false nil)))
         (cons false (cons true (cons true nil))) := eq_refl.

Definition demo_pin : nat := 70.
Definition demo_checkpoint : nat := 70.
Definition stale_checkpoint : nat := 60.

(* Reading 10, and the claim this file declines to make. R-13-023a's
   two-logged-variants construction: two distinct base-image identities both
   carry inclusion proofs against one accepted checkpoint, so the commitment
   check accepts either, and nothing here decides which one a publisher
   delivers to which device. That is exhibited as a pair the specification
   *accepts*, which is the honest form of a non-claim. *)
(*| discharges: R-13-023a |*)
Example public_commitment_accepts_two_logged_variants :
  pair (commitment_ok demo_transactor demo_pin demo_checkpoint (cons 33 nil))
       (commitment_ok demo_transactor demo_pin demo_checkpoint (cons 41 nil))
  = pair true true := eq_refl.

(*| discharges: R-13-023b, R-17-030v |*)
Example an_unlogged_identity_and_a_stale_checkpoint_are_both_refused :
  pair (pair (commitment_ok demo_transactor demo_pin demo_checkpoint (cons 19 nil))
             (commitment_ok demo_transactor demo_pin stale_checkpoint (cons 33 nil)))
       (pair (spec_pin demo_transactor demo_pin stale_checkpoint)
             (trusting_pin demo_transactor demo_pin stale_checkpoint))
  = pair (pair false false) (pair 70 60) := eq_refl.

Theorem the_trusting_pin_is_refuted : ~ NeverPinsAnInconsistentCheckpoint trusting_pin.
Proof.
  intros H. specialize (H demo_transactor demo_pin stale_checkpoint eq_refl).
  discriminate H.
Qed.

(* =========================================================================
   The crash-point family over the staging journal, generated by
   JournalIndex.v's own `cuts` rather than authored: at no crash point does
   the specification's verify admit an incomplete stage, under either arm.
   ========================================================================= *)

Definition stage_view_at (cut : Discipline) (j : list Rec) : Objects :=
  landed_view demo_transactor cut j demo_base staged_objs demo_objects.

Definition admits_at (cut : Discipline) (j : list Rec) : bool :=
  ab_admitted (verify demo_transactor (stage_view_at cut j) staged_ab).

Example there_are_four_crash_points_over_the_staging_journal :
  count_of (cuts whole_j) = 4 := eq_refl.

(*| discharges: R-10-036, R-10-002 |*)
Example no_crash_point_short_of_the_whole_stage_is_admitted :
  pair (map_over (admits_at scan) (cuts whole_j))
       (map_over (admits_at sieve) (cuts whole_j))
  = pair (cons false (cons false (cons false (cons true nil))))
         (cons false (cons false (cons false (cons true nil)))) := eq_refl.

(*| discharges: R-10-001a, R-10-002 |*)
Example no_torn_record_of_the_stage_is_admitted_under_either_arm :
  pair (map_over (fun k => admits_at scan (tear_at k 1 whole_j)) (upto 3))
       (map_over (fun k => admits_at sieve (tear_at k 1 whole_j)) (upto 3))
  = pair (cons false (cons false (cons false nil)))
         (cons false (cons false (cons false nil))) := eq_refl.

(* -------------------------------------------------------------------------
   R-05-166's inhabitation witnesses: one closed definition per record this
   file's statements quantify over, named for that record and ascribed at it.
   ------------------------------------------------------------------------- *)

Definition witness_Obj : Obj := base_root_obj.
Definition witness_SignedRoot : SignedRoot := base_root.
Definition witness_Transactor : Transactor := demo_transactor.
Definition witness_Ab : Ab := demo_ab.

(* The recovered leaf-only reader accepted a correctly named injected leaf
   through a corrupt root. Reachability in untrusted bytes is not authority. *)
Definition injected_parent : Obj := {| obj_bytes := 1; obj_kids := cons 5 nil |}.
Definition injected_objects : Objects := fun n =>
  if Nat.eqb n 17 then Some injected_parent else strayed_objects n.

Example a_corrupt_parent_cannot_authorize_its_injected_descendant :
  (leaf_only_read demo_transactor injected_objects 17 5,
   spec_read demo_transactor injected_objects 17 5) = (Some 5, None) := eq_refl.

Theorem the_leaf_only_reader_does_not_authenticate_the_image :
  ~ ReadsOnlyAnIntactImage leaf_only_read.
Proof.
  intros H. specialize (H demo_transactor injected_objects 17 5 5 eq_refl).
  discriminate H.
Qed.

(* A second stage invalidates the earlier admission. The positive four-step
   execution above inhabits the backing and bootability premises together. *)
Example restaging_cannot_reuse_a_previous_admission :
  (ab_admitted (stage dangling_root verified_ab),
   sr_root (live (flip (stage dangling_root verified_ab)))) = (false, 17) := eq_refl.

Example an_unwitnessed_consistent_checkpoint_cannot_be_pinned :
  (consistent demo_transactor 70 71,
   checkpoint_accepted demo_transactor 70 71,
   spec_pin demo_transactor 70 71) = (true, false, 70) := eq_refl.

Theorem the_update_run_has_inhabited_integrity_and_bootability_premises :
  verdict_backed demo_transactor whole_view verified_ab = true /\
  servable demo_transactor whole_view verified_ab = true /\
  bootable_now verified_ab = true /\
  ab_admitted verified_ab = true /\
  sr_root (live (flip verified_ab)) = 33.
Proof. repeat split; reflexivity. Qed.

Definition candidate_at_its_declared_floor : SignedRoot :=
  {| sr_root := 33; sr_version := 6; sr_floor := 6; sr_key := 3;
     sr_sig := 48; sr_sum := 45 |}.

Example the_declared_floor_boundary_is_inclusive :
  ab_admitted (verify demo_transactor whole_view
    (stage candidate_at_its_declared_floor demo_ab)) = true := eq_refl.

Example public_admission_rejects_an_unlogged_package_and_an_unaccepted_checkpoint :
  (ab_admitted (verify_public demo_transactor whole_view staged_ab 70 70 (cons 41 nil)),
   ab_admitted (verify_public demo_transactor whole_view staged_ab 70 70 (cons 19 nil)),
   ab_admitted (verify_public demo_transactor whole_view staged_ab 70 71 (cons 41 nil)))
  = (true, false, false) := eq_refl.

Example the_public_update_commits_the_bound_candidate_root :
  sr_root (live (flip (verify_public demo_transactor whole_view staged_ab 70 70 (cons 41 nil))))
  = 33 := eq_refl.

(* The old floor-only fallback accepted an unverified staged candidate.
   Retention and fresh authentication are now both required by the decision. *)
Definition floor_only_fallback (ab : Ab) : Ab :=
  if Nat.leb (ab_floor ab) (sr_version (spare ab)) then toggle ab else ab.

Example staging_an_unverified_root_cannot_launder_it_through_health_failure :
  root_verifies demo_transactor torn_copy = false /\
  live (floor_only_fallback (stage torn_copy flipped_ab)) = torn_copy /\
  live (spec_gate demo_transactor whole_view (stage torn_copy flipped_ab)) = next_root /\
  fallback_admissible demo_transactor whole_view flipped_ab = true /\
  live (spec_gate demo_transactor whole_view flipped_ab) = base_root.
Proof. repeat split; reflexivity. Qed.

Definition retained_torn_root : Ab :=
  {| ab_b_live := true; ab_slot_a := torn_copy; ab_slot_b := next_root;
     ab_floor := 4; ab_staged := false; ab_admitted := false;
     ab_retained := Some torn_copy |}.

Example a_retained_name_does_not_replace_authentication :
  retained_matches retained_torn_root = true /\
  fallback_admissible demo_transactor whole_view retained_torn_root = false /\
  live (spec_gate demo_transactor whole_view retained_torn_root) = next_root.
Proof. repeat split; reflexivity. Qed.

Definition with_walk_depth (t : Transactor) (depth : nat) : Transactor :=
  {| t with walk_depth := depth |}.

Definition only_successor_root : Objects := fun n =>
  if Nat.eqb n 33 then Some next_root_obj else None.

Theorem an_unfinished_bounded_walk_refuses_the_image : forall t st root,
  walk_complete (walk_depth t) st (cons root nil) = false -> dag_intact t st root = false.
Proof. intros t st root H. unfold dag_intact. rewrite H. reflexivity. Qed.

Example exhaustion_cannot_disguise_a_missing_descendant :
  all_of (present_and_named demo_transactor only_successor_root)
    (reach_list (with_walk_depth demo_transactor 0) only_successor_root 33) = true /\
  dag_intact (with_walk_depth demo_transactor 0) only_successor_root 33 = false /\
  ab_admitted (verify (with_walk_depth demo_transactor 0) only_successor_root staged_ab) = false /\
  dag_intact (with_walk_depth demo_transactor 0) whole_view 7 = true /\
  dag_intact demo_transactor whole_view 33 = true.
Proof. repeat split; reflexivity. Qed.
