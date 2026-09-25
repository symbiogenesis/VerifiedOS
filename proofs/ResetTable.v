(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ResetTable.v

   The release points of R-15-198's power and reset sequence table, as
   R-15-198a fixes them: the table releases islands at fixed points rather
   than at one, each island's release step following the ready indications
   and completion reads of the domains bound to that island and of no other
   island's; the table orders the shell and telephony islands' fills and
   releases ahead of the inference island's; and the RoT's start-up entropy
   health tests (R-09-006a) begin at the first step after the RoT's own
   rail is up and run concurrently with the clock-spine lock and the
   memory-controller bring-up, the verdict's extension ordered before the
   first step that draws entropy. The same entry has the tests run
   concurrently with every image-derived fill and re-verification as well,
   which this file does not state (reading 6). R-15-198 makes mode
   transitions, standby exit and deep-sleep wake re-entries into suffixes
   of the same table, and R-15-190b puts every re-execution of the chain
   the RoT sequences at such a suffix, so the release obligation is stated
   at every entry point the table declares and not on the cold path alone.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation: the release-point schema
   Q33 owns and four composition checks over it, with admitted tables
   computed and every malformed table the entry names refused. The checks
   are the release check at every entry point, the cold path's release of
   every island a domain is bound to, the staging order, and the entropy
   clauses. The island a domain is bound to is read from MemoryPlan.v's
   `PowerVector`, the same binding its label checks read, so the table
   carries no second copy of R-15-228's map. Every quantity the register
   leaves to composition is a field of the ResetTable record; nothing is
   admitted and nothing is axiomatized, and the Print Assumptions block at
   the end reports every shipped constant closed under the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. No shipped composition
   carries a reset table, so no constant here is read from one, emitted
   into an attested devicetree, lowered into the RoT firmware, or run on
   either emulator. The computed checks are decided inside the kernel by
   conversion and print nothing.

   What is not stated here, and who owns it.

   i.   The rest of the table. Its schema in the composition and its
        devicetree emission, each step's hardware ready indication and
        watchdog-bounded timeout, the release step's own among them, the
        dependency order among steps other than the release points, the
        absence of a cycle, and entry points that are suffixes of the table
        are the table's own authoring, crown-jewel row 12 (R-15-198), which
        the unassigned proof map prices as a separate slice. The step
        vocabulary below carries what R-15-198a's clauses read and no more.
   ii.  R-15-247d's discharge and admission order, which rides the same
        table as crown-jewel row 26 and is stated in DischargeSequence.v
        over a step vocabulary of its own, not linked to this file's.
   iii. R-09-006b's constant. Each release point is where one of its
        figures attaches, the cold-boot, wake-to-interactive and
        inference-ready instants being prefixes of the table through a
        release, and no term of that sum is stated here.
   iv.  R-15-190b's chain-execution clause and the lowering of the staged
        release into M3.5's firmware and M7.1's composed image, which boot
        through it; R-15-189g's containment at every release point, which
        reads the mode an early-released island runs; the inference members
        R-18-004a states unmet until the inference island's release, which
        the product gate reads off the table; and R-09-006a's failure half,
        no key derived, no material unsealed, no quote completed and the
        boot refused, which is the RoT firmware's (RotFirmware.v, M3.5).

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. The table is a list of steps the RoT walks in order, and a step
      follows another when it stands later in the walk, read over first
      occurrences as DischargeSequence.v's reading 6 reads them:
      `step_precedes p q l` is false where either step is absent, so a
      deleted read is a refusal rather than a silence and an early release
      is refused even where a later one would be in order.
   2. A domain's two reads are its ready indication and its completion
      read, `DomainReady` and `DomainComplete`, whatever the completion
      completes: an image-derived domain's fill or in-place re-verification
      verdict (R-15-190a, R-15-190b) or a session-derived domain's discharge
      confirmation (R-15-189j, R-15-247f). That is R-15-198a's own pair of
      nouns and it keeps the lowering of each kind of completion out of the
      schema (item iv).
   3. "And of no other island's" limits what a release waits for, and a
      walk cannot state it as an obligation on positions: the inference
      island's release stands after the shell island's reads in the walk,
      which R-15-198a's own ordering clause requires. So it is stated as
      what the check does not demand: the release check reads only the
      domains bound to the released island, and the one-release-point
      reading, every domain's reads ahead of every release, is constructed
      below and shown refusing the staged table the specification admits.
      "Rather than at one" is therefore carried by the staging order and
      not by the release check, which admits the table releasing every
      island at one point: the islands ordered ahead are a non-empty list
      (reading 5) and each is released before the inference island, so an
      admitted table has at least two release steps.
   4. The release obligation holds at every declared entry point. R-15-198
      makes re-entries suffixes of the table and R-15-190b makes every
      re-execution the RoT sequences one, so a release standing in the
      suffix a re-entry walks must find its own island's reads inside that
      suffix: a re-entry entered past a domain's re-verification would
      release the island onto an extent whose verdict nobody read, which
      R-15-190b refuses (no extent is released to a requester unverified)
      and R-15-198a refuses (never served from an extent whose verdict is
      pending). The cold path is the whole table, entry 0, and the table
      declares its other entries. An entry past the table's end enters an
      empty walk, which releases nothing and which the check admits;
      refusing an entry that is not a suffix is item i's.
   5. The islands ordered ahead and the inference island are fields.
      R-15-198a names the roles and no shipped composition binds them, and
      the first release targets a laptop (R-02-003) whose composition may
      carry no telephony island, so the islands ordered ahead are a list
      and the inference island one index. The list must not be empty:
      R-15-198a names the shell island without condition, and its
      wake-to-interactive instant is the table's prefix through the shell
      island's release, so a table declaring no island ahead is refused
      rather than read as unstaged. The order is read on the whole table:
      each island ordered ahead is released before the inference island is
      released and before any of its fills completes, a fill being an
      image-derived domain's completion read, the label read from the
      vector. Its own fills precede its own release by the release
      obligation, so the two together put its fills and its release ahead
      of the inference island's release, which is proved below rather than
      asserted. And every island a domain of the vector is bound to has a
      release step on the cold path, R-15-198a speaking of each island's
      release step: the release check reads only the releases that stand,
      so without that clause a release deleted from the walk would leave
      its island's domains unread by every check.
   6. The entropy clauses are read on the cold path. R-15-198a begins the
      tests at the first step after the RoT's own rail is up, and a
      re-entry from a running mode does not walk that step, the RoT being
      the one core no mode collapses; whether a re-entry re-runs the
      start-up tests is not stated by the register (reported). On the
      whole table the tests begin at the step immediately after the first
      `RotRailUp`; the clock-spine lock and the memory-controller bring-up
      each stand between the tests beginning and the verdict's extension,
      which is the tests running under those steps rather than ahead of
      them; the verdict's extension stands before the first
      `DrawsEntropy`; and it stands before every island's release. The
      last is R-09-006a's "before the first draw any measured stage can
      make" read at the table: a released island's kernels are measured
      stages that can draw, and RotFirmware.v's C3 reads the same entry as
      the verdict extended before every stage runs. That none of the fills
      and re-verifications draws is structural: a draw is its own step and
      a completion read is not one. R-15-198a's third concurrency term,
      the tests running concurrently with every image-derived fill and
      re-verification, is not stated. With the verdict before every
      release and each island ahead released before the inference island's
      fills, every admitted table puts those fills after the verdict,
      which is proved below, and R-15-190b has an island's measured M-mode
      stage run its re-verification before any kernel of that island is
      released. So that term, the verdict-before-release order and the
      staging order cannot all be read positionally in one walk
      (reported), and the check admits a fill on either side of the
      verdict.
   7. Nothing here is gated on a load. R-15-198a's release point is gated
      on a ready indication under the watchdog-bounded timeout and never on
      a load; the release step's own ready indication and timeout are item
      i's, as every step's are, and the schema carries no quantity a load
      could be.
   8. Boolean rather than propositional wherever the witnesses must
      compute, with the release and coverage checks proved sound and
      complete against their obligations, so a check answering false
      refutes the table rather than reporting that a decision procedure
      moved.

   The literals taken from the design: none. The step order of the demo
   tables below is a witness value and carries no composition claim.

   Non-vacuity (R-05-165, R-05-166). The release and coverage obligations
   are stated of an arbitrary table and vector and proved of their checks
   in both directions. Inhabitation is concrete: a staged table the checks
   admit, with a re-entry it declares; a second admitted table confirming
   a session-derived domain ahead of the staging; and a third, admitted
   over a vector binding one domain to an island no role names. Beside
   them fourteen refused tables, each refused by one check with the other
   three holding: over the held vector the release check refusing three,
   the staging check three and the entropy checks seven, five of which
   fail one entropy clause each so that every clause is separated from
   the others by a table of its own; and the coverage check one, the
   staged table over the three-island vector. A table releasing no island
   is refused by the coverage and staging checks both, and the whole check
   is computed to refuse every one of these tables. The one-release-point
   reading refuses the admitted table, and three generated families over
   the admitted table's cold path have their verdicts computed: of the
   sixteen deletions the release check refuses exactly the eight that
   remove a released island's read and the coverage check exactly the two
   that remove a release, and of the fifteen adjacent transpositions the
   release check refuses exactly one, the one moving the inference release
   ahead of its last read.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-02-003 R-05-163 R-05-164 R-05-165 R-05-166 R-09-006a R-09-006b R-15-247d
      R-15-247f R-15-247t R-15-189g R-15-189j R-15-190a R-15-190b R-15-195 R-15-198 R-15-198a
      R-15-228 R-18-004a
   SHA256: 4569eeeeed93b1ecaa2ee34fab9096ff86d603eca0746071f7e0e35900bd3d79
   (*| END derived |*)
   ========================================================================= *)

Require Import CyclicExecutive.
Require Import MemoryPlan.

(* -------------------------------------------------------------------------
   The step vocabulary: what R-15-198, R-15-198a and R-09-006a name, and no
   more (item i).
   ------------------------------------------------------------------------- *)

Inductive TableStep : Type :=
| RotRailUp                   (* the RoT's own rail up, R-15-198's first
                                 dependency                                  *)
| EntropyTestsBegin           (* R-09-006a's start-up health tests begin     *)
| ClockSpineLock              (* R-15-195's PLL lock, the clock-spine step   *)
| MemoryControllerUp          (* the memory-controller bring-up              *)
| DomainReady (d : nat)       (* a gating domain's ready indication          *)
| DomainComplete (d : nat)    (* a gating domain's completion read
                                 (reading 2)                                 *)
| EntropyVerdictExtended      (* the tests' verdict measured into the chain  *)
| DrawsEntropy                (* a step that draws: a key derived, material
                                 unsealed, a quote completed                 *)
| IslandRelease (i : nat).    (* R-15-198a's release point for island i      *)

Definition step_eqb (a b : TableStep) : bool :=
  match a, b with
  | RotRailUp, RotRailUp => true
  | EntropyTestsBegin, EntropyTestsBegin => true
  | ClockSpineLock, ClockSpineLock => true
  | MemoryControllerUp, MemoryControllerUp => true
  | DomainReady d, DomainReady e => Nat.eqb d e
  | DomainComplete d, DomainComplete e => Nat.eqb d e
  | EntropyVerdictExtended, EntropyVerdictExtended => true
  | DrawsEntropy, DrawsEntropy => true
  | IslandRelease i, IslandRelease j => Nat.eqb i j
  | _, _ => false
  end.

Lemma step_eqb_refl : forall s : TableStep, step_eqb s s = true.
Proof. intros s. destruct s; simpl; try reflexivity; apply eqb_refl. Qed.

Lemma step_eqb_true : forall a b : TableStep, step_eqb a b = true -> a = b.
Proof.
  intros a b. destruct a; destruct b; simpl; intros H; try discriminate H;
    try reflexivity; rewrite (eqb_true _ _ H); reflexivity.
Qed.

Fixpoint step_occurs (s : TableStep) (l : list TableStep) : bool :=
  match l with
  | nil => false
  | cons x r => orb (step_eqb s x) (step_occurs s r)
  end.

(* Answers at whichever of p and q the walk meets first; false where either
   is absent (reading 1). *)
Fixpoint step_precedes (p q : TableStep) (l : list TableStep) : bool :=
  match l with
  | nil => false
  | cons x r =>
      if step_eqb q x then false
      else if step_eqb p x then step_occurs q r
      else step_precedes p q r
  end.

(* The walk re-entered at the step with index n. *)
Fixpoint suffix_from {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, _ => l
  | S k, cons _ r => suffix_from k r
  | S _, nil => nil
  end.

(* The step immediately after the first occurrence of p. *)
Fixpoint step_after (p : TableStep) (l : list TableStep) : option TableStep :=
  match l with
  | nil => None
  | cons x r =>
      if step_eqb p x
      then match r with cons y _ => Some y | nil => None end
      else step_after p r
  end.

Lemma all_of_steps :
  forall (p : TableStep -> bool) (l : list TableStep) (x : TableStep),
    all_of p l = true -> step_occurs x l = true -> p x = true.
Proof.
  intros p l x. induction l as [ | y r IH ]; intros Hall Hocc.
  - discriminate Hocc.
  - simpl in Hall. destruct (andb_split _ _ Hall) as [ Hy Hr ].
    revert Hocc. simpl. destruct (step_eqb x y) eqn:E; simpl; intros Hocc.
    + rewrite (step_eqb_true x y E). exact Hy.
    + exact (IH Hr Hocc).
Qed.

Lemma all_of_steps_intro :
  forall (p : TableStep -> bool) (l : list TableStep),
    (forall x : TableStep, step_occurs x l = true -> p x = true) ->
    all_of p l = true.
Proof.
  intros p l. induction l as [ | y r IH ]; intros H.
  - reflexivity.
  - simpl. apply andb_join.
    + apply H. simpl. rewrite step_eqb_refl. reflexivity.
    + apply IH. intros x Hx. apply H. simpl. rewrite Hx.
      destruct (step_eqb x y); reflexivity.
Qed.

Lemma all_of_members :
  forall (p : nat -> bool) (l : list nat) (e : nat),
    all_of p l = true -> any_of (Nat.eqb e) l = true -> p e = true.
Proof.
  intros p l e. induction l as [ | y r IH ]; intros Hall Hmem.
  - discriminate Hmem.
  - simpl in Hall. destruct (andb_split _ _ Hall) as [ Hy Hr ].
    revert Hmem. simpl. destruct (Nat.eqb e y) eqn:E; simpl; intros Hmem.
    + rewrite (eqb_true _ _ E). exact Hy.
    + exact (IH Hr Hmem).
Qed.

Lemma all_of_members_intro :
  forall (p : nat -> bool) (l : list nat),
    (forall e : nat, any_of (Nat.eqb e) l = true -> p e = true) ->
    all_of p l = true.
Proof.
  intros p l. induction l as [ | y r IH ]; intros H.
  - reflexivity.
  - simpl. apply andb_join.
    + apply H. simpl. rewrite eqb_refl. reflexivity.
    + apply IH. intros e He. apply H. simpl. rewrite He.
      destruct (Nat.eqb e y); reflexivity.
Qed.

(* What a step preceding another says of each of the two. *)
Lemma step_precedes_occurs :
  forall (p q : TableStep) (l : list TableStep),
    step_precedes p q l = true -> step_occurs q l = true.
Proof.
  intros p q l. induction l as [ | x r IH ]; intros H.
  - discriminate H.
  - revert H. simpl.
    destruct (step_eqb q x); simpl.
    + intros H. discriminate H.
    + destruct (step_eqb p x); simpl; intros H.
      * exact H.
      * exact (IH H).
Qed.

Lemma step_precedes_occurs_left :
  forall (p q : TableStep) (l : list TableStep),
    step_precedes p q l = true -> step_occurs p l = true.
Proof.
  intros p q l. induction l as [ | x r IH ]; intros H.
  - discriminate H.
  - revert H. simpl.
    destruct (step_eqb q x); simpl.
    + intros H. discriminate H.
    + destruct (step_eqb p x); simpl; intros H.
      * reflexivity.
      * exact (IH H).
Qed.

(* First occurrences order transitively. *)
Lemma step_precedes_trans :
  forall (p q s : TableStep) (l : list TableStep),
    step_precedes p q l = true -> step_precedes q s l = true ->
    step_precedes p s l = true.
Proof.
  intros p q s l. induction l as [ | x r IH ]; intros H1 H2.
  - discriminate H1.
  - revert H1 H2. simpl.
    destruct (step_eqb q x); simpl.
    + intros H1. discriminate H1.
    + destruct (step_eqb s x); simpl.
      * intros _ H2. discriminate H2.
      * destruct (step_eqb p x); simpl; intros H1 H2.
        -- exact (step_precedes_occurs q s r H2).
        -- exact (IH H1 H2).
Qed.

(* -------------------------------------------------------------------------
   The table: what the register leaves to composition (readings 4 and 5).
   ------------------------------------------------------------------------- *)

Record ResetTable : Type := {

  (* --- R-15-198's walk, in the order the RoT takes it ----------------- *)

  table_steps : list TableStep;

  (* --- the suffixes a re-entry enters at (reading 4); the cold path is
         entry 0 and is not declared here --------------------------------- *)

  entry_points : list nat;

  (* --- R-15-198a's roles (reading 5) --------------------------------- *)

  ahead_islands : list nat;
  inference_island : nat
}.

Definition entries_of (t : ResetTable) : list nat := cons 0 t.(entry_points).

(* -------------------------------------------------------------------------
   R-15-198a's release points (readings 1 to 5).
   ------------------------------------------------------------------------- *)

(* The reads a release of island i follows: its own domains' two reads, and
   no other island's (reading 3). *)
Definition own_reads_before (v : PowerVector) (s : list TableStep) (i : nat) : bool :=
  all_of (fun d => only_if (Nat.eqb (v.(domain_island) d) i)
                           (andb (step_precedes (DomainReady d) (IslandRelease i) s)
                                 (step_precedes (DomainComplete d) (IslandRelease i) s)))
         (upto v.(domain_count)).

Definition releases_follow_own_reads (v : PowerVector) (s : list TableStep) : bool :=
  all_of (fun st => match st with
                    | IslandRelease i => own_reads_before v s i
                    | _ => true
                    end) s.

(* The composition check, at the cold path and at every declared entry. *)
Definition release_points_ok (t : ResetTable) (v : PowerVector) : bool :=
  all_of (fun e => releases_follow_own_reads v (suffix_from e t.(table_steps)))
         (entries_of t).

Definition ReleasesFollowOwnReads (v : PowerVector) (s : list TableStep) : Prop :=
  forall i d : nat,
    step_occurs (IslandRelease i) s = true ->
    Nat.ltb d v.(domain_count) = true ->
    v.(domain_island) d = i ->
    step_precedes (DomainReady d) (IslandRelease i) s = true
    /\ step_precedes (DomainComplete d) (IslandRelease i) s = true.

Definition ReleasePointsFollowOwnReads (t : ResetTable) (v : PowerVector) : Prop :=
  forall e : nat,
    any_of (Nat.eqb e) (entries_of t) = true ->
    ReleasesFollowOwnReads v (suffix_from e t.(table_steps)).

(* T1 (R-15-198a): the walk's check decides its obligation in both
   directions. *)
(*| discharges: R-15-198a |*)
Lemma releases_follow_own_reads_sound :
  forall (v : PowerVector) (s : list TableStep),
    releases_follow_own_reads v s = true -> ReleasesFollowOwnReads v s.
Proof.
  intros v s H i d Hocc Hd Hisl. unfold releases_follow_own_reads in H.
  assert (Hi := all_of_steps _ s (IslandRelease i) H Hocc). cbv beta iota in Hi.
  unfold own_reads_before in Hi.
  assert (Hc := all_of_upto _ v.(domain_count) d Hi Hd). cbv beta in Hc.
  apply andb_split. apply (only_if_elim _ _ Hc).
  rewrite Hisl. apply eqb_refl.
Qed.

(*| discharges: R-15-198a |*)
Lemma releases_follow_own_reads_complete :
  forall (v : PowerVector) (s : list TableStep),
    ReleasesFollowOwnReads v s -> releases_follow_own_reads v s = true.
Proof.
  intros v s H. unfold releases_follow_own_reads.
  apply all_of_steps_intro. intros x Hx.
  destruct x as [ | | | | d | d | | | i ]; try reflexivity.
  cbv beta iota. unfold own_reads_before.
  apply all_of_upto_intro. intros d Hd. cbv beta.
  apply only_if_intro. intros Hisl.
  destruct (H i d Hx Hd (eqb_true _ _ Hisl)) as [ Hr Hc ].
  apply andb_join; [ exact Hr | exact Hc ].
Qed.

(* T2 (R-15-198a, R-15-190b): and so does the table's, at every entry. *)
(*| discharges: R-15-198a, R-15-190b |*)
Theorem release_points_ok_sound :
  forall (t : ResetTable) (v : PowerVector),
    release_points_ok t v = true -> ReleasePointsFollowOwnReads t v.
Proof.
  intros t v H e He. apply releases_follow_own_reads_sound.
  exact (all_of_members
           (fun e => releases_follow_own_reads v (suffix_from e t.(table_steps)))
           (entries_of t) e H He).
Qed.

(*| discharges: R-15-198a, R-15-190b |*)
Theorem release_points_ok_complete :
  forall (t : ResetTable) (v : PowerVector),
    ReleasePointsFollowOwnReads t v -> release_points_ok t v = true.
Proof.
  intros t v H. unfold release_points_ok.
  apply all_of_members_intro. intros e He. cbv beta.
  apply releases_follow_own_reads_complete. exact (H e He).
Qed.

(* The cold path releases every island a domain of the vector is bound to
   (reading 5). *)
Definition islands_released_ok (t : ResetTable) (v : PowerVector) : bool :=
  all_of (fun d => step_occurs (IslandRelease (v.(domain_island) d)) t.(table_steps))
         (upto v.(domain_count)).

Definition EveryBoundIslandIsReleased (t : ResetTable) (v : PowerVector) : Prop :=
  forall d : nat,
    Nat.ltb d v.(domain_count) = true ->
    step_occurs (IslandRelease (v.(domain_island) d)) t.(table_steps) = true.

(* T1b (R-15-198a): the coverage check decides its obligation in both
   directions. *)
(*| discharges: R-15-198a |*)
Lemma islands_released_ok_sound :
  forall (t : ResetTable) (v : PowerVector),
    islands_released_ok t v = true -> EveryBoundIslandIsReleased t v.
Proof.
  intros t v H d Hd. unfold islands_released_ok in H.
  exact (all_of_upto _ v.(domain_count) d H Hd).
Qed.

(*| discharges: R-15-198a |*)
Lemma islands_released_ok_complete :
  forall (t : ResetTable) (v : PowerVector),
    EveryBoundIslandIsReleased t v -> islands_released_ok t v = true.
Proof.
  intros t v H. unfold islands_released_ok.
  apply all_of_upto_intro. intros d Hd. exact (H d Hd).
Qed.

(* The one-release-point reading reading 3 refutes: every release follows
   every domain's reads, its own island's or not. *)
Definition all_reads_before (v : PowerVector) (s : list TableStep) (i : nat) : bool :=
  all_of (fun d => andb (step_precedes (DomainReady d) (IslandRelease i) s)
                        (step_precedes (DomainComplete d) (IslandRelease i) s))
         (upto v.(domain_count)).

Definition releases_follow_all_reads (v : PowerVector) (s : list TableStep) : bool :=
  all_of (fun st => match st with
                    | IslandRelease i => all_reads_before v s i
                    | _ => true
                    end) s.

(* -------------------------------------------------------------------------
   R-15-198a's staging order (readings 3 and 5).
   ------------------------------------------------------------------------- *)

(* An island's fills: the completion reads of its image-derived domains. *)
Definition fill_of (v : PowerVector) (i d : nat) : bool :=
  andb (Nat.eqb (v.(domain_island) d) i) (negb (session_derived v d)).

Definition staged_ahead_of (v : PowerVector) (s : list TableStep) (a n : nat) : bool :=
  andb (step_precedes (IslandRelease a) (IslandRelease n) s)
       (all_of (fun d => only_if (fill_of v n d)
                                 (step_precedes (IslandRelease a) (DomainComplete d) s))
               (upto v.(domain_count))).

(* The shell island is named without condition (reading 5). *)
Definition ahead_listed (t : ResetTable) : bool :=
  match t.(ahead_islands) with nil => false | cons _ _ => true end.

Definition staging_ok (t : ResetTable) (v : PowerVector) : bool :=
  andb (ahead_listed t)
       (all_of (fun a => staged_ahead_of v t.(table_steps) a t.(inference_island))
               t.(ahead_islands)).

(* T3 (R-15-198a): with the release obligation on the cold path, the
   staging check puts every fill of an island ordered ahead before the
   inference island's release, reading 5 proved rather than asserted. *)
(*| discharges: R-15-198a |*)
Theorem the_ahead_fills_precede_the_inference_release :
  forall (t : ResetTable) (v : PowerVector) (a d : nat),
    release_points_ok t v = true ->
    staging_ok t v = true ->
    any_of (Nat.eqb a) t.(ahead_islands) = true ->
    Nat.ltb d v.(domain_count) = true ->
    v.(domain_island) d = a ->
    step_precedes (DomainComplete d) (IslandRelease t.(inference_island))
                  t.(table_steps) = true.
Proof.
  intros t v a d Hrel Hst Ha Hd Hisl. unfold staging_ok in Hst.
  destruct (andb_split _ _ Hst) as [ _ Hall ].
  assert (Hahead := all_of_members _ t.(ahead_islands) a Hall Ha). cbv beta in Hahead.
  unfold staged_ahead_of in Hahead.
  destruct (andb_split _ _ Hahead) as [ Hrr _ ].
  assert (Hcold := release_points_ok_sound t v Hrel 0 eq_refl).
  destruct (Hcold a d (step_precedes_occurs_left _ _ _ Hrr) Hd Hisl) as [ _ Hown ].
  exact (step_precedes_trans _ _ _ _ Hown Hrr).
Qed.

(* -------------------------------------------------------------------------
   R-15-198a's entropy clauses, on the cold path (reading 6).
   ------------------------------------------------------------------------- *)

Definition tests_begin_after_rot_rail (s : list TableStep) : bool :=
  match step_after RotRailUp s with
  | Some y => step_eqb y EntropyTestsBegin
  | None => false
  end.

Definition tests_run_under (s : list TableStep) : bool :=
  andb (andb (step_precedes EntropyTestsBegin ClockSpineLock s)
             (step_precedes ClockSpineLock EntropyVerdictExtended s))
       (andb (step_precedes EntropyTestsBegin MemoryControllerUp s)
             (step_precedes MemoryControllerUp EntropyVerdictExtended s)).

Definition verdict_before_draws (s : list TableStep) : bool :=
  only_if (step_occurs DrawsEntropy s)
          (step_precedes EntropyVerdictExtended DrawsEntropy s).

Definition verdict_before_releases (s : list TableStep) : bool :=
  all_of (fun st => match st with
                    | IslandRelease i => step_precedes EntropyVerdictExtended (IslandRelease i) s
                    | _ => true
                    end) s.

Definition entropy_ok (t : ResetTable) : bool :=
  andb (tests_begin_after_rot_rail t.(table_steps))
       (andb (tests_run_under t.(table_steps))
             (andb (verdict_before_draws t.(table_steps))
                   (verdict_before_releases t.(table_steps)))).

(* T4 (R-15-198a): an admitted table draws nothing before the verdict is
   extended, which is R-15-198a's own ordering clause. *)
(*| discharges: R-15-198a |*)
Theorem an_admitted_table_draws_after_the_verdict :
  forall t : ResetTable,
    entropy_ok t = true ->
    step_occurs DrawsEntropy t.(table_steps) = true ->
    step_precedes EntropyVerdictExtended DrawsEntropy t.(table_steps) = true.
Proof.
  intros t H Hdraw. unfold entropy_ok in H.
  destruct (andb_split _ _ H) as [ _ Hrest ].
  destruct (andb_split _ _ Hrest) as [ _ Hrest2 ].
  destruct (andb_split _ _ Hrest2) as [ Hv _ ].
  unfold verdict_before_draws in Hv.
  exact (only_if_elim _ _ Hv Hdraw).
Qed.

(* T5 (R-15-198a, R-09-006a): and releases no island before it. This claims
   R-09-006a's ordering half at the table, read as RotFirmware.v's C3 reads
   it at the chain, and nothing of its failure half (item iv). *)
(*| discharges: R-15-198a, R-09-006a |*)
Theorem an_admitted_table_releases_no_island_before_the_verdict :
  forall (t : ResetTable) (i : nat),
    entropy_ok t = true ->
    step_occurs (IslandRelease i) t.(table_steps) = true ->
    step_precedes EntropyVerdictExtended (IslandRelease i) t.(table_steps) = true.
Proof.
  intros t i H Hocc. unfold entropy_ok in H.
  destruct (andb_split _ _ H) as [ _ Hrest ].
  destruct (andb_split _ _ Hrest) as [ _ Hrest2 ].
  destruct (andb_split _ _ Hrest2) as [ _ Hrel ].
  unfold verdict_before_releases in Hrel.
  exact (all_of_steps _ _ (IslandRelease i) Hrel Hocc).
Qed.

(* T6: what reading 6 reports. With the verdict before every release and
   the staging order, every image-derived fill of the inference island
   stands after the verdict, so no admitted table whose inference island
   has one runs the tests concurrently with all of its fills. *)
Theorem the_inference_fills_follow_the_verdict :
  forall (t : ResetTable) (v : PowerVector) (a d : nat),
    staging_ok t v = true ->
    entropy_ok t = true ->
    any_of (Nat.eqb a) t.(ahead_islands) = true ->
    Nat.ltb d v.(domain_count) = true ->
    fill_of v t.(inference_island) d = true ->
    step_precedes EntropyVerdictExtended (DomainComplete d) t.(table_steps) = true.
Proof.
  intros t v a d Hst Hent Ha Hd Hfill. unfold staging_ok in Hst.
  destruct (andb_split _ _ Hst) as [ _ Hall ].
  assert (Hahead := all_of_members _ t.(ahead_islands) a Hall Ha). cbv beta in Hahead.
  unfold staged_ahead_of in Hahead.
  destruct (andb_split _ _ Hahead) as [ Hrr Hfills ].
  assert (Hf := all_of_upto _ v.(domain_count) d Hfills Hd). cbv beta in Hf.
  assert (Hfirst := only_if_elim _ _ Hf Hfill).
  assert (Hv := an_admitted_table_releases_no_island_before_the_verdict t a Hent
                  (step_precedes_occurs_left _ _ _ Hrr)).
  exact (step_precedes_trans _ _ _ _ Hv Hfirst).
Qed.

(* The whole of R-15-198a's schema check. *)
Definition reset_table_ok (t : ResetTable) (v : PowerVector) : bool :=
  andb (release_points_ok t v)
       (andb (islands_released_ok t v) (andb (staging_ok t v) (entropy_ok t))).

(* -------------------------------------------------------------------------
   The demo table, over MemoryPlan.v's `held_vector`: four domains, the
   first bound to island 0 and the other three to island 1. The first is
   island 0's first-class macro, outside R-15-247t's label; the demo plan's
   holdings derive the labels of the other three (the arenas' domain 1
   session-derived, the weights' domain 2 and the payload's domain 3
   image-derived). Island 0 is the one island ordered ahead and island 1
   the inference island. The table brings the RoT up, begins the tests,
   locks the spine, brings the memory controller up, reads island 0's
   domain, extends the verdict, draws, releases island 0, and then reads
   island 1's domains, the weights last, before releasing island 1. It
   declares one re-entry, at island 1's first read, which walks island 1's
   reads and release alone; standing after the cold path's draw, its
   suffix walks no entropy step and takes no side on whether a re-entry
   re-runs the start-up tests (reading 6). Every figure is a witness
   value.
   ------------------------------------------------------------------------- *)

Definition demo_steps : list TableStep :=
  cons RotRailUp (cons EntropyTestsBegin (cons ClockSpineLock
  (cons MemoryControllerUp (cons (DomainReady 0) (cons (DomainComplete 0)
  (cons EntropyVerdictExtended (cons DrawsEntropy (cons (IslandRelease 0)
  (cons (DomainReady 1) (cons (DomainComplete 1) (cons (DomainReady 3)
  (cons (DomainComplete 3) (cons (DomainReady 2) (cons (DomainComplete 2)
  (cons (IslandRelease 1) nil))))))))))))))).

Definition with_steps (t : ResetTable) (s : list TableStep) : ResetTable := {|
  table_steps := s;
  entry_points := t.(entry_points);
  ahead_islands := t.(ahead_islands);
  inference_island := t.(inference_island)
|}.

Definition with_entries (t : ResetTable) (es : list nat) : ResetTable := {|
  table_steps := t.(table_steps);
  entry_points := es;
  ahead_islands := t.(ahead_islands);
  inference_island := t.(inference_island)
|}.

Definition demo_table : ResetTable := {|
  table_steps := demo_steps;
  entry_points := cons 9 nil;
  ahead_islands := cons 0 nil;
  inference_island := 1
|}.

(* The malformed tables, each one defect away from the demo's. *)

(* The inference island released before its weights' verdict is read. *)
Definition early_release_table : ResetTable := with_steps demo_table (swap_at 14 demo_steps).

(* A re-entry entered past the arenas' and the payload's reads. *)
Definition late_entry_table : ResetTable := with_entries demo_table (cons 9 (cons 13 nil)).

(* A release not gated on its own domain's ready indication. *)
Definition unready_table : ResetTable := with_steps demo_table (drop_at 9 demo_steps).

(* The inference island read and released ahead of island 0, read on the
   cold path alone, the table declaring no re-entry. *)
Definition inference_first_steps : list TableStep :=
  cons RotRailUp (cons EntropyTestsBegin (cons ClockSpineLock
  (cons MemoryControllerUp (cons (DomainReady 1) (cons (DomainComplete 1)
  (cons (DomainReady 3) (cons (DomainComplete 3) (cons (DomainReady 2)
  (cons (DomainComplete 2) (cons EntropyVerdictExtended (cons DrawsEntropy
  (cons (IslandRelease 1) (cons (DomainReady 0) (cons (DomainComplete 0)
  (cons (IslandRelease 0) nil))))))))))))))).

Definition inference_first_table : ResetTable :=
  with_entries (with_steps demo_table inference_first_steps) nil.

(* A draw taken before the verdict is extended. *)
Definition early_draw_table : ResetTable := with_steps demo_table (swap_at 6 demo_steps).

(* The tests begun after the clock-spine lock. *)
Definition late_tests_table : ResetTable := with_steps demo_table (swap_at 1 demo_steps).

(* The tests run ahead of the table rather than under it: the verdict
   extended before the spine locks. *)
Definition serialized_steps : list TableStep :=
  cons RotRailUp (cons EntropyTestsBegin (cons EntropyVerdictExtended
  (cons ClockSpineLock (cons MemoryControllerUp (cons (DomainReady 0)
  (cons (DomainComplete 0) (cons DrawsEntropy (cons (IslandRelease 0)
  (cons (DomainReady 1) (cons (DomainComplete 1) (cons (DomainReady 3)
  (cons (DomainComplete 3) (cons (DomainReady 2) (cons (DomainComplete 2)
  (cons (IslandRelease 1) nil))))))))))))))).

Definition serialized_table : ResetTable := with_steps demo_table serialized_steps.

(* The tests under the spine lock and not under the controller bring-up:
   the verdict extended between the two. *)
Definition verdict_between_steps : list TableStep :=
  cons RotRailUp (cons EntropyTestsBegin (cons ClockSpineLock
  (cons EntropyVerdictExtended (cons MemoryControllerUp (cons (DomainReady 0)
  (cons (DomainComplete 0) (cons DrawsEntropy (cons (IslandRelease 0)
  (cons (DomainReady 1) (cons (DomainComplete 1) (cons (DomainReady 3)
  (cons (DomainComplete 3) (cons (DomainReady 2) (cons (DomainComplete 2)
  (cons (IslandRelease 1) nil))))))))))))))).

(* And the other way round, under the controller and not under the spine,
   which only a table bringing the controller up first can express; that
   order is R-15-198's dependency order broken, which this schema does not
   check (item i). *)
Definition controller_first_steps : list TableStep :=
  cons RotRailUp (cons EntropyTestsBegin (cons MemoryControllerUp
  (cons EntropyVerdictExtended (cons ClockSpineLock (cons (DomainReady 0)
  (cons (DomainComplete 0) (cons DrawsEntropy (cons (IslandRelease 0)
  (cons (DomainReady 1) (cons (DomainComplete 1) (cons (DomainReady 3)
  (cons (DomainComplete 3) (cons (DomainReady 2) (cons (DomainComplete 2)
  (cons (IslandRelease 1) nil))))))))))))))).

(* The tests begun before the spine lock and not at the first step after
   the RoT's rail, a domain's ready indication standing between; read on
   the cold path alone, the table declaring no re-entry. *)
Definition late_begin_steps : list TableStep :=
  cons RotRailUp (cons (DomainReady 0) (cons EntropyTestsBegin
  (cons ClockSpineLock (cons MemoryControllerUp (cons (DomainComplete 0)
  (cons EntropyVerdictExtended (cons DrawsEntropy (cons (IslandRelease 0)
  (cons (DomainReady 1) (cons (DomainComplete 1) (cons (DomainReady 3)
  (cons (DomainComplete 3) (cons (DomainReady 2) (cons (DomainComplete 2)
  (cons (IslandRelease 1) nil))))))))))))))).

Definition late_begin_table : ResetTable :=
  with_entries (with_steps demo_table late_begin_steps) nil.

(* Island 0 released after its own reads and before the verdict is
   extended, the tests still running under the spine and the controller
   and the verdict still ahead of the draw. *)
Definition release_before_verdict_steps : list TableStep :=
  cons RotRailUp (cons EntropyTestsBegin (cons ClockSpineLock
  (cons MemoryControllerUp (cons (DomainReady 0) (cons (DomainComplete 0)
  (cons (IslandRelease 0) (cons EntropyVerdictExtended (cons DrawsEntropy
  (cons (DomainReady 1) (cons (DomainComplete 1) (cons (DomainReady 3)
  (cons (DomainComplete 3) (cons (DomainReady 2) (cons (DomainComplete 2)
  (cons (IslandRelease 1) nil))))))))))))))).

Definition release_before_verdict_table : ResetTable :=
  with_steps demo_table release_before_verdict_steps.

(* An admitted variant: the inference island's session-derived domain
   confirmed ahead of island 0's release, its image-derived fills after it.
   A discharge confirmation is no fill (reading 5), so the staging order
   does not move it. Read on the cold path alone. *)
Definition session_first_steps : list TableStep :=
  cons RotRailUp (cons EntropyTestsBegin (cons ClockSpineLock
  (cons MemoryControllerUp (cons (DomainReady 0) (cons (DomainComplete 0)
  (cons (DomainReady 1) (cons (DomainComplete 1) (cons EntropyVerdictExtended
  (cons DrawsEntropy (cons (IslandRelease 0) (cons (DomainReady 3)
  (cons (DomainComplete 3) (cons (DomainReady 2) (cons (DomainComplete 2)
  (cons (IslandRelease 1) nil))))))))))))))).

Definition session_first_table : ResetTable :=
  with_entries (with_steps demo_table session_first_steps) nil.

(* The one-release-point table: every island released after every read,
   read on the cold path alone. *)
Definition one_point_steps : list TableStep :=
  cons RotRailUp (cons EntropyTestsBegin (cons ClockSpineLock
  (cons MemoryControllerUp (cons (DomainReady 0) (cons (DomainComplete 0)
  (cons (DomainReady 1) (cons (DomainComplete 1) (cons (DomainReady 3)
  (cons (DomainComplete 3) (cons (DomainReady 2) (cons (DomainComplete 2)
  (cons EntropyVerdictExtended (cons DrawsEntropy (cons (IslandRelease 0)
  (cons (IslandRelease 1) nil))))))))))))))).

Definition one_point_table : ResetTable :=
  with_entries (with_steps demo_table one_point_steps) nil.

(* The same walk with no island declared ahead (reading 5). *)
Definition one_point_unstaged_table : ResetTable := {|
  table_steps := one_point_steps;
  entry_points := nil;
  ahead_islands := nil;
  inference_island := 1
|}.

(* A walk releasing no island at all, with no island declared ahead. *)
Definition no_release_steps : list TableStep :=
  cons RotRailUp (cons EntropyTestsBegin (cons ClockSpineLock
  (cons MemoryControllerUp (cons (DomainReady 0) (cons (DomainComplete 0)
  (cons EntropyVerdictExtended (cons DrawsEntropy nil))))))).

Definition no_release_table : ResetTable := {|
  table_steps := no_release_steps;
  entry_points := nil;
  ahead_islands := nil;
  inference_island := 1
|}.

(* A vector binding the bulk payload's domain to a third island, which no
   role names, with the held vector's labels and power; and the demo walk
   with that island's release appended after island 1's. *)
Definition third_island_of_domain (d : nat) : nat :=
  match d with 0 => 0 | 3 => 2 | _ => 1 end.

Definition third_island_vector : PowerVector := {|
  domain_count := 4;
  mode_count := 2;
  label_of := derived_demo_labels;
  domain_island := third_island_of_domain;
  island_resident := resident_islands;
  power_of := held_vector_power
|}.

Definition third_island_steps : list TableStep :=
  cons RotRailUp (cons EntropyTestsBegin (cons ClockSpineLock
  (cons MemoryControllerUp (cons (DomainReady 0) (cons (DomainComplete 0)
  (cons EntropyVerdictExtended (cons DrawsEntropy (cons (IslandRelease 0)
  (cons (DomainReady 1) (cons (DomainComplete 1) (cons (DomainReady 3)
  (cons (DomainComplete 3) (cons (DomainReady 2) (cons (DomainComplete 2)
  (cons (IslandRelease 1) (cons (IslandRelease 2) nil)))))))))))))))).

Definition third_island_table : ResetTable := with_steps demo_table third_island_steps.

(* R1 (R-15-198a, R-15-190b, R-09-006a): the staged table is admitted,
   computed rather than claimed, at the cold path and at its re-entry. *)
(*| discharges: R-15-198a, R-15-190b, R-09-006a |*)
Example the_staged_table_is_admitted :
  release_points_ok demo_table held_vector = true
  /\ islands_released_ok demo_table held_vector = true
  /\ staging_ok demo_table held_vector = true
  /\ entropy_ok demo_table = true
  /\ reset_table_ok demo_table held_vector = true
  /\ suffix_from 9 demo_steps
     = cons (DomainReady 1) (cons (DomainComplete 1) (cons (DomainReady 3)
       (cons (DomainComplete 3) (cons (DomainReady 2) (cons (DomainComplete 2)
       (cons (IslandRelease 1) nil)))))) :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(*| discharges: R-15-198a, R-15-190b |*)
Theorem the_staged_table_meets_the_release_obligation :
  ReleasePointsFollowOwnReads demo_table held_vector
  /\ EveryBoundIslandIsReleased demo_table held_vector.
Proof.
  split.
  - exact (release_points_ok_sound demo_table held_vector eq_refl).
  - exact (islands_released_ok_sound demo_table held_vector eq_refl).
Qed.

(* R2 (R-15-198a): releasing an island before its own domains' reads is
   refused, and the refusal is the release check's alone. *)
(*| discharges: R-15-198a |*)
Example a_table_releasing_before_its_own_reads_is_refused :
  release_points_ok early_release_table held_vector = false
  /\ islands_released_ok early_release_table held_vector = true
  /\ staging_ok early_release_table held_vector = true
  /\ entropy_ok early_release_table = true
  /\ release_points_ok unready_table held_vector = false
  /\ islands_released_ok unready_table held_vector = true
  /\ staging_ok unready_table held_vector = true
  /\ entropy_ok unready_table = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))))).

(*| discharges: R-15-198a |*)
Theorem the_early_release_table_breaks_the_release_obligation :
  ~ ReleasePointsFollowOwnReads early_release_table held_vector.
Proof.
  intros H. destruct (H 0 eq_refl 1 2 eq_refl eq_refl eq_refl) as [ _ Hc ].
  cbv in Hc. discriminate Hc.
Qed.

(* R3 (R-15-198a, R-15-190b): a re-entry entered past a domain's reads is
   refused, the cold path and the declared re-entry of the same table
   being admitted. *)
(*| discharges: R-15-198a, R-15-190b |*)
Example a_reentry_past_its_domains_reads_is_refused :
  release_points_ok late_entry_table held_vector = false
  /\ releases_follow_own_reads held_vector demo_steps = true
  /\ releases_follow_own_reads held_vector (suffix_from 9 demo_steps) = true
  /\ releases_follow_own_reads held_vector (suffix_from 13 demo_steps) = false
  /\ islands_released_ok late_entry_table held_vector = true
  /\ staging_ok late_entry_table held_vector = true
  /\ entropy_ok late_entry_table = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl eq_refl))))).

(*| discharges: R-15-198a, R-15-190b |*)
Theorem the_late_entry_table_breaks_the_release_obligation :
  ~ ReleasePointsFollowOwnReads late_entry_table held_vector.
Proof.
  intros H. destruct (H 13 eq_refl 1 1 eq_refl eq_refl eq_refl) as [ Hr _ ].
  cbv in Hr. discriminate Hr.
Qed.

(* R4 (R-15-198a): the staging order, refused where the inference island
   goes first, every release there following its own reads. *)
(*| discharges: R-15-198a |*)
Example a_table_staging_the_inference_island_first_is_refused :
  staging_ok inference_first_table held_vector = false
  /\ release_points_ok inference_first_table held_vector = true
  /\ islands_released_ok inference_first_table held_vector = true
  /\ entropy_ok inference_first_table = true :=
  conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* R9 (R-15-198a): an island a domain is bound to and the table never
   releases is refused, and the refusal is the coverage check's alone: the
   release check reads only the releases that stand, and no role names the
   island. The same walk with that island's release appended is admitted. *)
(*| discharges: R-15-198a |*)
Example a_bound_island_never_released_is_refused :
  islands_released_ok demo_table third_island_vector = false
  /\ release_points_ok demo_table third_island_vector = true
  /\ staging_ok demo_table third_island_vector = true
  /\ entropy_ok demo_table = true
  /\ reset_table_ok demo_table third_island_vector = false
  /\ reset_table_ok third_island_table third_island_vector = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

(*| discharges: R-15-198a |*)
Theorem the_unreleased_island_breaks_the_coverage_obligation :
  ~ EveryBoundIslandIsReleased demo_table third_island_vector.
Proof.
  intros H. specialize (H 3 eq_refl). cbv in H. discriminate H.
Qed.

(* The four entropy clauses and the release clause of one walk, in the
   order reading 6 states them: the tests begun at the first step after
   the RoT's rail, the tests under the spine lock, the tests under the
   controller bring-up, the verdict before every draw, and the verdict
   before every release. *)
Definition entropy_clauses (s : list TableStep) : list bool :=
  cons (tests_begin_after_rot_rail s)
  (cons (andb (step_precedes EntropyTestsBegin ClockSpineLock s)
              (step_precedes ClockSpineLock EntropyVerdictExtended s))
  (cons (andb (step_precedes EntropyTestsBegin MemoryControllerUp s)
              (step_precedes MemoryControllerUp EntropyVerdictExtended s))
  (cons (verdict_before_draws s)
  (cons (verdict_before_releases s) nil)))).

(* A table the entropy checks refuse and the other three checks admit. *)
Definition refused_by_entropy_alone (t : ResetTable) : bool :=
  andb (negb (entropy_ok t))
       (andb (release_points_ok t held_vector)
             (andb (islands_released_ok t held_vector) (staging_ok t held_vector))).

Definition verdict_between_table : ResetTable := with_steps demo_table verdict_between_steps.

Definition controller_first_table : ResetTable := with_steps demo_table controller_first_steps.

(* R5 (R-15-198a, R-09-006a): the entropy clauses. Seven tables are refused
   by the entropy checks alone. Five of them fail one clause each, a
   different one apiece, so every clause is separated from the others by a
   table of its own: the draw before the verdict, the tests begun one step
   late but still under both, the verdict between the spine lock and the
   controller, the controller brought up first, and island 0 released
   before the verdict. The tests begun after the spine lock and the tests
   run ahead of the table each fail two. *)
(*| discharges: R-15-198a, R-09-006a |*)
Example the_entropy_clauses_each_refuse_their_table :
  map_over (fun t => entropy_clauses t.(table_steps))
           (cons early_draw_table (cons late_begin_table
           (cons verdict_between_table (cons controller_first_table
           (cons release_before_verdict_table
           (cons late_tests_table (cons serialized_table nil)))))))
  = cons (cons true (cons true (cons true (cons false (cons true nil)))))
    (cons (cons false (cons true (cons true (cons true (cons true nil)))))
    (cons (cons true (cons true (cons false (cons true (cons true nil)))))
    (cons (cons true (cons false (cons true (cons true (cons true nil)))))
    (cons (cons true (cons true (cons true (cons true (cons false nil)))))
    (cons (cons false (cons false (cons true (cons true (cons true nil)))))
    (cons (cons true (cons false (cons false (cons true (cons true nil))))) nil))))))
  /\ map_over refused_by_entropy_alone
              (cons early_draw_table (cons late_begin_table
              (cons verdict_between_table (cons controller_first_table
              (cons release_before_verdict_table
              (cons late_tests_table (cons serialized_table nil)))))))
  = cons true (cons true (cons true (cons true (cons true (cons true (cons true nil))))))
  /\ entropy_clauses demo_steps
     = cons true (cons true (cons true (cons true (cons true nil)))) :=
  conj eq_refl (conj eq_refl eq_refl).

(* R10: what T6 states, on the admitted table. The weights' domain is an
   image-derived fill of the inference island and stands after the verdict,
   outside the tests' window. *)
Example the_admitted_table_fills_the_inference_island_after_the_verdict :
  fill_of held_vector 1 2 = true
  /\ step_precedes EntropyVerdictExtended (DomainComplete 2) demo_steps = true
  /\ step_precedes (DomainComplete 2) EntropyVerdictExtended demo_steps = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* R6 (R-15-198a): reading 3. The one-release-point reading refuses the
   staged table the specification admits, and the release check admits the
   table that releases every island at one point, so it demands no other
   island's reads; that table is refused by the staging order instead, its
   inference fills standing ahead of island 0's release. *)
(*| discharges: R-15-198a |*)
Example the_one_point_reading_refuses_the_staged_table :
  releases_follow_all_reads held_vector demo_steps = false
  /\ releases_follow_own_reads held_vector demo_steps = true
  /\ releases_follow_all_reads held_vector one_point_steps = true
  /\ release_points_ok one_point_table held_vector = true
  /\ islands_released_ok one_point_table held_vector = true
  /\ entropy_ok one_point_table = true
  /\ step_precedes (IslandRelease 0) (IslandRelease 1) one_point_steps = true
  /\ staging_ok one_point_table held_vector = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))))).

(* R6b (R-15-198a): and "rather than at one" rests on the staging roles.
   The one-point walk with no island declared ahead passes the release,
   coverage and entropy checks, and the non-empty list refuses it; a walk
   releasing no island at all is refused by the coverage check as well. *)
(*| discharges: R-15-198a |*)
Example a_table_with_no_island_ahead_is_refused :
  ahead_listed one_point_unstaged_table = false
  /\ staging_ok one_point_unstaged_table held_vector = false
  /\ release_points_ok one_point_unstaged_table held_vector = true
  /\ islands_released_ok one_point_unstaged_table held_vector = true
  /\ entropy_ok one_point_unstaged_table = true
  /\ islands_released_ok no_release_table held_vector = false
  /\ staging_ok no_release_table held_vector = false
  /\ release_points_ok no_release_table held_vector = true
  /\ entropy_ok no_release_table = true :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl
    (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))))))).

(* R11 (R-15-198a): and the whole check refuses every malformed table over
   the held vector, each of the four checks carrying its own refusals. *)
(*| discharges: R-15-198a |*)
Example the_whole_check_refuses_every_malformed_table :
  map_over (fun t => reset_table_ok t held_vector)
           (cons early_release_table (cons unready_table (cons late_entry_table
           (cons inference_first_table (cons one_point_table
           (cons one_point_unstaged_table (cons no_release_table
           (cons early_draw_table (cons late_begin_table
           (cons verdict_between_table (cons controller_first_table
           (cons release_before_verdict_table (cons late_tests_table
           (cons serialized_table nil))))))))))))))
  = cons false (cons false (cons false (cons false (cons false (cons false
    (cons false (cons false (cons false (cons false (cons false (cons false
    (cons false (cons false nil))))))))))))) := eq_refl.

(* R8 (R-15-198a): the staging order reads fills and not every completion.
   The inference island's session-derived domain confirmed ahead of island
   0's release is admitted; the same table with that domain labelled
   image-derived is refused, so the label read from the vector decides. *)
(*| discharges: R-15-198a |*)
Example a_confirmation_ahead_of_the_staging_is_no_fill :
  reset_table_ok session_first_table held_vector = true
  /\ staging_ok session_first_table kind_read_vector = true
  /\ staging_ok session_first_table mislabelled_vector = false :=
  conj eq_refl (conj eq_refl eq_refl).

(* R7 (R-15-198a): the generated families over the staged table's cold
   path. Of its sixteen deletions the release check refuses exactly the
   eight removing a released island's read and the coverage check exactly
   the two removing a release, and of its fifteen adjacent transpositions
   the release check refuses exactly the one moving the inference release
   ahead of its last read. *)
(*| discharges: R-15-198a |*)
Example the_deletions_refused_are_the_reads :
  map_over (fun k => releases_follow_own_reads held_vector (drop_at k demo_steps))
           (upto 16)
  = cons true (cons true (cons true (cons true (cons false (cons false
    (cons true (cons true (cons true (cons false (cons false (cons false
    (cons false (cons false (cons false (cons true nil))))))))))))))) := eq_refl.

(*| discharges: R-15-198a |*)
Example the_deletions_the_coverage_refuses_are_the_releases :
  map_over (fun k => islands_released_ok (with_steps demo_table (drop_at k demo_steps))
                                         held_vector)
           (upto 16)
  = cons true (cons true (cons true (cons true (cons true (cons true
    (cons true (cons true (cons false (cons true (cons true (cons true
    (cons true (cons true (cons true (cons false nil))))))))))))))) := eq_refl.

(*| discharges: R-15-198a |*)
Example the_transpositions_refused_are_one :
  map_over (fun k => releases_follow_own_reads held_vector (swap_at k demo_steps))
           (upto 15)
  = cons true (cons true (cons true (cons true (cons true (cons true
    (cons true (cons true (cons true (cons true (cons true (cons true
    (cons true (cons true (cons false nil)))))))))))))) := eq_refl.

(* The helpers' own floors. *)
Example the_walk_helpers_on_short_lists :
  step_precedes RotRailUp DrawsEntropy (cons RotRailUp (cons DrawsEntropy nil)) = true
  /\ step_precedes DrawsEntropy RotRailUp (cons RotRailUp (cons DrawsEntropy nil)) = false
  /\ step_precedes RotRailUp DrawsEntropy (cons RotRailUp nil) = false
  /\ step_after RotRailUp (cons RotRailUp nil) = None
  /\ suffix_from 3 (cons RotRailUp nil) = nil
  /\ step_eqb (DomainReady 1) (DomainComplete 1) = false :=
  conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl)))).

Definition witness_ResetTable : ResetTable := demo_table.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared set
   R-05-164 currently makes empty.
   ------------------------------------------------------------------------- *)

Print Assumptions TableStep.
Print Assumptions step_eqb.
Print Assumptions step_eqb_refl.
Print Assumptions step_eqb_true.
Print Assumptions step_occurs.
Print Assumptions step_precedes.
Print Assumptions suffix_from.
Print Assumptions step_after.
Print Assumptions all_of_steps.
Print Assumptions all_of_steps_intro.
Print Assumptions all_of_members.
Print Assumptions all_of_members_intro.
Print Assumptions step_precedes_occurs.
Print Assumptions step_precedes_occurs_left.
Print Assumptions step_precedes_trans.
Print Assumptions ResetTable.
Print Assumptions entries_of.
Print Assumptions own_reads_before.
Print Assumptions releases_follow_own_reads.
Print Assumptions release_points_ok.
Print Assumptions ReleasesFollowOwnReads.
Print Assumptions ReleasePointsFollowOwnReads.
Print Assumptions releases_follow_own_reads_sound.
Print Assumptions releases_follow_own_reads_complete.
Print Assumptions release_points_ok_sound.
Print Assumptions release_points_ok_complete.
Print Assumptions islands_released_ok.
Print Assumptions EveryBoundIslandIsReleased.
Print Assumptions islands_released_ok_sound.
Print Assumptions islands_released_ok_complete.
Print Assumptions all_reads_before.
Print Assumptions releases_follow_all_reads.
Print Assumptions fill_of.
Print Assumptions staged_ahead_of.
Print Assumptions ahead_listed.
Print Assumptions staging_ok.
Print Assumptions the_ahead_fills_precede_the_inference_release.
Print Assumptions tests_begin_after_rot_rail.
Print Assumptions tests_run_under.
Print Assumptions verdict_before_draws.
Print Assumptions verdict_before_releases.
Print Assumptions entropy_ok.
Print Assumptions an_admitted_table_draws_after_the_verdict.
Print Assumptions an_admitted_table_releases_no_island_before_the_verdict.
Print Assumptions the_inference_fills_follow_the_verdict.
Print Assumptions reset_table_ok.
Print Assumptions demo_steps.
Print Assumptions with_steps.
Print Assumptions with_entries.
Print Assumptions demo_table.
Print Assumptions early_release_table.
Print Assumptions late_entry_table.
Print Assumptions unready_table.
Print Assumptions inference_first_steps.
Print Assumptions inference_first_table.
Print Assumptions early_draw_table.
Print Assumptions late_tests_table.
Print Assumptions serialized_steps.
Print Assumptions serialized_table.
Print Assumptions verdict_between_steps.
Print Assumptions controller_first_steps.
Print Assumptions late_begin_steps.
Print Assumptions late_begin_table.
Print Assumptions release_before_verdict_steps.
Print Assumptions release_before_verdict_table.
Print Assumptions session_first_steps.
Print Assumptions session_first_table.
Print Assumptions one_point_steps.
Print Assumptions one_point_table.
Print Assumptions one_point_unstaged_table.
Print Assumptions no_release_steps.
Print Assumptions no_release_table.
Print Assumptions third_island_of_domain.
Print Assumptions third_island_vector.
Print Assumptions third_island_steps.
Print Assumptions third_island_table.
Print Assumptions the_staged_table_is_admitted.
Print Assumptions the_staged_table_meets_the_release_obligation.
Print Assumptions a_table_releasing_before_its_own_reads_is_refused.
Print Assumptions the_early_release_table_breaks_the_release_obligation.
Print Assumptions a_reentry_past_its_domains_reads_is_refused.
Print Assumptions the_late_entry_table_breaks_the_release_obligation.
Print Assumptions a_table_staging_the_inference_island_first_is_refused.
Print Assumptions a_bound_island_never_released_is_refused.
Print Assumptions the_unreleased_island_breaks_the_coverage_obligation.
Print Assumptions entropy_clauses.
Print Assumptions refused_by_entropy_alone.
Print Assumptions verdict_between_table.
Print Assumptions controller_first_table.
Print Assumptions the_entropy_clauses_each_refuse_their_table.
Print Assumptions the_admitted_table_fills_the_inference_island_after_the_verdict.
Print Assumptions the_one_point_reading_refuses_the_staged_table.
Print Assumptions a_table_with_no_island_ahead_is_refused.
Print Assumptions the_whole_check_refuses_every_malformed_table.
Print Assumptions a_confirmation_ahead_of_the_staging_is_no_fill.
Print Assumptions the_deletions_refused_are_the_reads.
Print Assumptions the_deletions_the_coverage_refuses_are_the_releases.
Print Assumptions the_transpositions_refused_are_one.
Print Assumptions the_walk_helpers_on_short_lists.
