(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ResetTable.v

   Reset-table release checks for R-15-198 and R-15-198a, including the
   retained re-entry suffixes R-15-190b requires over image-derived and
   session-derived domains (R-15-189j, R-15-190a, R-15-247d, R-15-247f,
   R-15-247t; see [DischargeSequence.v](DischargeSequence.v)). The
   domain-to-island map comes from [MemoryPlan.v](MemoryPlan.v#PowerVector),
   which carries R-15-228's map.

   Four executable composition checks cover:
   1. Release of each island only after its own domains' ready and completion
      reads (`DomainReady`, `DomainComplete`), independent of other islands'
      domains and never gated on load (R-15-198, R-15-198a).
   2. Cold-path release coverage across all bound islands, with containment at
      every release point (R-15-189g) and latency constants attached per
      release prefix (R-09-006b).
   3. Staging order placing the shell and ahead-ordered islands before the
      inference island (R-02-003, R-15-198a, R-18-004a).
   4. Entropy start-up test ordering after `RotRailUp`, running under
      clock-spine lock and memory-controller bring-up (R-15-195) and extending
      its verdict before any entropy draw or island release (R-09-006a; see
      [RotFirmware.v](RotFirmware.v)).

   Composition parameters are record fields (R-05-163, R-05-164), with
   soundness/completeness equivalence theorems and concrete accepted and
   refused table witnesses (R-05-165, R-05-166).
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-02-003 R-05-163 R-05-164 R-05-165 R-05-166 R-09-006a R-09-006b R-15-247d
      R-15-247f R-15-247t R-15-189g R-15-189j R-15-190a R-15-190b R-15-195 R-15-198 R-15-198a
      R-15-228 R-18-004a
   SHA256: aadfc847ffe1702195047e77bed07589b517eb732a3f0443aa248e289a01436c
   (*| END derived |*)
   ========================================================================= *)

Require Import CyclicExecutive.
Require Import MemoryPlan.

(* -------------------------------------------------------------------------
   The step vocabulary: what R-15-198, R-15-198a and R-09-006a name.
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

(* True when p's first occurrence precedes q's first occurrence. False if
   either is absent or p = q (reading 1). *)
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

(* Precedence requires the later step to occur. *)
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
  all_of (fun st => if st is IslandRelease i then own_reads_before v s i else true) s.

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

(* T1 (R-15-198a): soundness and completeness of the per-walk release check. *)
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

(* T2 (R-15-198a, R-15-190b): soundness and completeness at every entry. *)
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

(* T1b (R-15-198a): soundness and completeness of release coverage. *)
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

(* Alternative rejected in reading 3: require every domain's reads before
   every island release, including domains belonging to other islands. *)
Definition all_reads_before (v : PowerVector) (s : list TableStep) (i : nat) : bool :=
  all_of (fun d => andb (step_precedes (DomainReady d) (IslandRelease i) s)
                        (step_precedes (DomainComplete d) (IslandRelease i) s))
         (upto v.(domain_count)).

Definition releases_follow_all_reads (v : PowerVector) (s : list TableStep) : bool :=
  all_of (fun st => if st is IslandRelease i then all_reads_before v s i else true) s.

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
  if t.(ahead_islands) is nil then false else true.

Definition staging_ok (t : ResetTable) (v : PowerVector) : bool :=
  andb (ahead_listed t)
       (all_of (fun a => staged_ahead_of v t.(table_steps) a t.(inference_island))
               t.(ahead_islands)).

(* T3 (R-15-198a): release and staging checks put every domain completion
   of an ahead island before the inference island's release (reading 5). *)
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
  if step_after RotRailUp s is Some y then step_eqb y EntropyTestsBegin else false.

Definition tests_run_under (s : list TableStep) : bool :=
  andb (andb (step_precedes EntropyTestsBegin ClockSpineLock s)
             (step_precedes ClockSpineLock EntropyVerdictExtended s))
       (andb (step_precedes EntropyTestsBegin MemoryControllerUp s)
             (step_precedes MemoryControllerUp EntropyVerdictExtended s)).

Definition verdict_before_draws (s : list TableStep) : bool :=
  only_if (step_occurs DrawsEntropy s)
          (step_precedes EntropyVerdictExtended DrawsEntropy s).

Definition verdict_before_releases (s : list TableStep) : bool :=
  all_of (fun st => if st is IslandRelease i
                    then step_precedes EntropyVerdictExtended (IslandRelease i) s
                    else true) s.

Definition entropy_ok (t : ResetTable) : bool :=
  andb (tests_begin_after_rot_rail t.(table_steps))
       (andb (tests_run_under t.(table_steps))
             (andb (verdict_before_draws t.(table_steps))
                   (verdict_before_releases t.(table_steps)))).

(* T4 (R-15-198a): every draw follows the entropy-verdict extension. *)
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

(* T5 (R-15-198a, R-09-006a): every island release follows the verdict.
   This models ordering, not the failed-test response deferred in item iv. *)
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

(* T6: staging and verdict-before-release put inference fills after the
   verdict. This prevents a positional interpretation of the requirement
   that all fills overlap the tests; see reading 6. *)
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

(* Combine the four implemented checks; reading 6 identifies the omitted
   R-15-198a concurrency clause. *)
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

Definition with_steps (t : ResetTable) (s : list TableStep) : ResetTable :=
  {| t with table_steps := s |}.

Definition with_entries (t : ResetTable) (es : list nat) : ResetTable :=
  {| t with entry_points := es |}.

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

(* R-05-163 and R-05-164: `run.py proofs` audits the complete native inventory. *)
