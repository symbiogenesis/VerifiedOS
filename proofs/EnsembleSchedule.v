(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   EnsembleSchedule.v

   R-11-017a's fourth output, stated as a field of the admission artifact
   the register already has a record for: on a member of an ensemble
   (R-02-003a) the artifact R-11-017 emits carries that member's ensemble
   link slot tables, each slot's instant against the member's own origin
   (R-11-014a), its direction and its guard band, one frame length per link
   (R-15-228d), the leader link's leap slot at its re-alignment cadence
   (R-15-196a), the leader tree, the declared oscillator tolerances and the
   skew bound, and the digest each end binds into the session's context
   (R-12-015d). Beside the record sit the three checks R-11-017a names, the
   composer's own: that the two views of one link agree, that every guard
   band is at or above the skew bound plus that link's latency bound, and
   that the cadence times both members' declared tolerance lies inside the
   guard band. Beside those sits R-11-014b's chain term over a link hop,
   computed from the operands the ensemble schedule states rather than
   declared.

   The Require is load-bearing rather than decorative. CyclicExecutive.v
   carries Composition, Slot, Band, Frame, Ladder and admits; R-11-017a puts
   the link server's slots, the endpoint's encode and decode latencies, the
   crypto core's per-frame operations and the endpoint's window grants into
   the member's own R-11-006 interval arithmetic "as ordinary tasks and
   grants", so this file adds no second admission check and every member's
   cores are admitted by that file's `admits` and by nothing else. A link
   task that does not fit its slot is therefore refused by R-11-006's own
   arithmetic, which is the reading gap f records and
   `a_link_task_that_does_not_fit_its_slot_is_refused` exhibits.

   What this file is. A statement artifact in ApexTheorem.v's idiom.
   Nothing is admitted, nothing is axiomatized, and no magnitude is
   invented: every quantity is a field, and the demo emission at the end
   instantiates the fields with arbitrary witness values that carry no
   composition claim (gap a).

   What this file does not do. It emits nothing. R-11-017a's emission is an
   act of the composition tool, whose frame synthesizer is R-11-015b's
   untrusted evidence-producing machinery and is unbuilt: no schedule
   emitter exists in this tree, M6.10 owns the on-device composition act
   that would carry one, and the first three outputs of R-11-017 are owed
   elsewhere (gaps e and g). What is stated here is the fourth output's
   shape and the refusals an emitter is measured against, which is the half
   R-02-003a names as the third of the five artifacts an ensemble is
   admitted only when they exist.

   What the gate's green line means. Compiled, axiom-free, witnessed and
   enumerated. It does not mean verified: nothing here is run on either
   emulator, no frame is encoded, no digest is computed by any hash, and the
   computed checks below are decided inside the kernel by conversion and
   print nothing.

   Readings of the register this statement takes, each a reviewable judgment
   rather than a neutral transcription:

   1. The fourth output extends the existing record and does not replace it.
      R-11-017a says the artifact R-11-017 emits "carries a fourth output",
      so `Emission` below holds the member schedules whose cores are
      CyclicExecutive.v's own `Frame`s, and the link tables, the leaps and
      the skew declaration beside them. A second schedule record would be a
      second owner of the frame geometry R-11-023's invariance is stated
      over.
   2. Two views of one link, and two readers of them. R-11-017a has one
      composition act emit every member's artifact and the ensemble schedule
      together, "so the two tables of one link are two views of one table",
      and separately has each member's admission refuse "its own artifact".
      The check this file states is the composer's, which reads both views
      of one link; a member's own admission reads its own view. That
      distinction is what makes `views_agree` a composer's self-check rather
      than a runtime exchange, and R-11-017a's "no runtime exchange
      establishes or amends a slot" is why no other reader exists.
   3. The leap window is an absence and not a reservation list. R-15-196a
      makes the leap "a kernel-owned idle slot between rotations that
      belongs to no partition and that the executive reserves on every core
      of the member at the same absolute instant", so that "no partition's
      slot straddles the step". A reservation carried as a fourth band would
      be a second way of saying what the absence of an overlapping slot
      already says, so `core_admits_the_leap` decides the window by finding
      no slot of that core across it. That the instant is one and the same
      on every core is structural: `leap_instant` is one field.
   4. A slot's absolute instant is its frame's phase offset plus its own
      offset. R-11-014a gives each core one composition-fixed phase offset
      against one platform-wide origin, and CyclicExecutive.v's `admits`
      reads slot offsets inside the frame and never adds the phase. The leap
      is stated against the member's own origin, so the comparison here adds
      the phase and the containment is stated against each core's own frame
      span. Gap c records what that leaves undecided.
   5. The leader tree is a parent index strictly below the child's.
      R-15-196a fixes "a composition-fixed leader tree carried in every
      attested devicetree", the root taking no leap and every other member
      being follower on exactly one link. Presented as a parent index the
      check compares with `Nat.ltb`, acyclicity is decided by conversion and
      no reachability relation is needed; any tree admits such a numbering
      and the numbering is the composition's. `the_leader_tree_is_acyclic`
      and `member_zero_is_not_a_follower` are what that presentation buys.
   6. The digest is a function of the link's table. R-12-015d has the
      session's context bind "the digest of the link's slot table each end
      holds", so an end holding a different table is refused at
      establishment. `link_digest_ok` holds each end's declared digest to
      one function of one table, which is why both ends bind one value
      (`both_ends_bind_one_digest`). That a different table yields a
      different digest is a property of the hash and not of this statement,
      and it is owed at R-12-015d's construction rather than claimed here;
      `a_constant_digest_binds_nothing` is the construction that shows the
      digest check does not carry the agreement check.
   7. R-11-014b's on-die hop term is a declared quantity here and its link
      hop term is computed. That entry states the whole chain arithmetic,
      "computed from the frame offsets and the per-hop slot periods over the
      R-07-007 edges, a pinned core (R-11-011) contributing its poll-loop
      period in place of a frame offset"; what Q23d owns is the one clause
      that reads "an ensemble link hop being one more edge kind whose
      per-hop term is its slot period plus its guard band". So `on_die_hop`
      carries its term as a number this file does not derive, and
      `link_hop_term` is the only term computed below. Restating the on-die
      arithmetic would be a second owner of R-11-014b's own sentence.
   8. The link hop's guard term is the worst guard band the link's own table
      states. R-11-014b wants a worst-case end-to-end bound and R-11-017a
      makes the guard band a per-slot field, so the per-hop term takes the
      maximum over the link's slots rather than a per-slot value a chain
      does not name.

   Two readings the register leaves open, both carried and neither decided
   here:

   9. Which slots carry the guard-band floor. R-15-196a states it of "every
      receive slot of a link table"; R-11-017a refuses an artifact "where a
      guard band on any of its links is below the composition's skew bound
      plus that link's latency bound", which over a field set that gives
      every slot a guard band reads as every slot. Both scopes are exhibited
      (`receive_only`, `every_slot`) and every statement below quantifies
      over an arbitrary scope. The question turns out not to need a register
      act: `the_two_guard_scopes_agree_on_an_agreeing_link` proves the two
      readings are the same check on any link whose two views agree, because
      agreement pairs each slot with a slot of the opposite direction at the
      same guard band, so the union of the receive slots of the two views is
      every slot of both. They differ only on a link the composer already
      refuses, which is
      `the_scopes_differ_only_on_a_link_the_composer_refuses`.
   10. The derived bound and measured qualification are distinct inputs.
      R-15-196a requires a bound derived from tolerances and cadence, with
      a measured pair exceeding that bound failing qualification. The
      qualified_emission_admits entry point checks the attested bound equals
      the derivation, checks the measurement against it, and uses the derived
      bound for every guard. The parameterized declared arm below is retained
      as a refuting alternative, not an unresolved register interpretation.

   What this file deliberately does not author, with the entry or item that
   owes each:

   a. Every magnitude. The frame length, the latency bound, the slot period,
      the cadence, the tolerances, the guard bands, the skew bound and the
      digests are fields. The link contract's constant table carries one row
      per constant with its owner and no number, and R-17-041's magnitudes
      are unauthored, so no value below carries a composition claim.
   b. The relation between a link's declared slot period and the instants
      its table lists. R-11-017a's per-slot field set is instant, direction
      and guard band and carries no period; the slot period is the link's,
      stated by the ensemble schedule and read by R-11-014b's chain term. No
      entry says whether the declared period must be the spacing the
      instants exhibit, so `lt_period` is declared here and checked against
      nothing. Whether the emitter owes that self-check is a register act
      this file reports and does not take.
   c. How the leap window recurs. R-15-196a puts one leap per re-alignment
      cadence and R-11-017a states the cadence in slots of the leader link,
      while a core's frame repeats at a major frame stated in spine cycles.
      No entry relates the two, so the check below decides one window
      against one frame span per core and says nothing about later
      repetitions.
   d. The actual measured qualification observation, independently of the
      derived bound. The normative wrapper checks their required relation.
   e. The composition tool's emission. R-11-015b makes frame construction a
      composition-tool duty discharged by search, and no such tool exists in
      this tree.
   f. R-11-006's interval arithmetic itself, which is CyclicExecutive.v's,
      and R-11-017's first three outputs, the OPP assignment, the TDM NoC
      schedule and the watchdog windows, which this file neither states nor
      restates.
   g. The digest function. `demo_digest` is an arbitrary witness function
      standing where a hash belongs, exactly as CyclicExecutive.v's harmonic
      predicate stands where a composition constant belongs.
   h. Everything the link itself is. The frame grammar, the code, the
      endpoint's registers and the session are R-15-228b through R-15-228e's
      and R-12-015d's; `lt_frame_length` is carried because R-15-228d makes
      every slot of a link carry the link's one frame length, and no field
      below reads a frame's contents.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary guard scope, skew rule, digest function, chain
   term or retenanting, proved of the specification, and refuted of an
   alternative construction the register's own sentence excludes.
   Inhabitation is concrete: a two-member, one-link emission that is
   admitted, and computed checks in the silent Example form for each of the
   refusals R-11-017a and R-15-196a name, each seeded so that it fails the
   one conjunct it is about.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-02-003a R-05-163 R-05-165 R-05-166 R-07-007 R-11-006 R-11-011 R-11-014a
      R-11-014b R-11-015b R-11-017 R-11-017a R-11-023 R-12-015d R-15-196a R-15-228b R-15-228d
      R-15-228e R-17-041
   SHA256: c292ee500f2ed793bcf7c074db6103e977bb391cbd11c9c2ef20524c9b3be291
   (*| END derived |*)
   ========================================================================= *)

Require Import CyclicExecutive.

(* -------------------------------------------------------------------------
   Boolean and arithmetic facts the prelude carries the types but not the
   library for, on CyclicExecutive.v's own ground: importing a module to
   save a dozen lines would put its assumptions inside the R-05-163 gate's
   reach for no gain.
   ------------------------------------------------------------------------- *)

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof.
  intros a b H. destruct a, b; try discriminate H; split; reflexivity.
Qed.

Lemma andb_pair_swap :
  forall a b c d : bool, andb (andb a b) (andb c d) = andb (andb a c) (andb b d).
Proof. intros a b c d. destruct a, b, c, d; reflexivity. Qed.

Lemma leb_refl : forall a : nat, Nat.leb a a = true.
Proof. induction a as [ | a IH ]; simpl; [ reflexivity | exact IH ]. Qed.

Lemma leb_trans :
  forall a b c : nat, Nat.leb a b = true -> Nat.leb b c = true -> Nat.leb a c = true.
Proof.
  induction a as [ | a IH ]; intros b c Hab Hbc.
  - reflexivity.
  - destruct b as [ | b ]; [ discriminate Hab | ].
    destruct c as [ | c ]; [ discriminate Hbc | ].
    exact (IH b c Hab Hbc).
Qed.

Lemma leb_add_r : forall a b : nat, Nat.leb a (a + b) = true.
Proof. induction a as [ | a IH ]; intros b; [ reflexivity | simpl; apply IH ]. Qed.

Lemma max_left : forall a b : nat, Nat.leb a (Nat.max a b) = true.
Proof.
  induction a as [ | a IH ]; intros b.
  - reflexivity.
  - destruct b as [ | b ]; simpl; [ apply leb_refl | apply IH ].
Qed.

Lemma max_right : forall a b : nat, Nat.leb b (Nat.max a b) = true.
Proof.
  induction a as [ | a IH ]; intros b.
  - simpl. apply leb_refl.
  - destruct b as [ | b ]; simpl; [ reflexivity | apply IH ].
Qed.

Lemma eqb_eq : forall a b : nat, Nat.eqb a b = true -> a = b.
Proof.
  induction a as [ | a IH ]; intros [ | b ] H; try discriminate H.
  - reflexivity.
  - rewrite (IH b H). reflexivity.
Qed.

Lemma plus_zero_r : forall a : nat, a + 0 = a.
Proof. induction a as [ | a IH ]; [ reflexivity | simpl; rewrite IH; reflexivity ]. Qed.

Lemma plus_succ_r : forall a b : nat, a + S b = S (a + b).
Proof. induction a as [ | a IH ]; intros b; [ reflexivity | simpl; rewrite IH; reflexivity ]. Qed.

(* -------------------------------------------------------------------------
   List helpers beside CyclicExecutive.v's own `all_of`, which this file
   reuses rather than restating.
   ------------------------------------------------------------------------- *)

Fixpoint InList {A : Type} (x : A) (l : list A) : Prop :=
  match l with
  | nil => False
  | cons y r => y = x \/ InList x r
  end.

Fixpoint nth_of {A : Type} (l : list A) (n : nat) : option A :=
  match l with
  | nil => None
  | cons x r => match n with
                | 0 => Some x
                | S k => nth_of r k
                end
  end.

Lemma all_of_cons :
  forall (A : Type) (p : A -> bool) (x : A) (l : list A),
    all_of p (cons x l) = andb (p x) (all_of p l).
Proof. reflexivity. Qed.

Lemma all_of_member :
  forall (A : Type) (p : A -> bool) (l : list A) (x : A),
    all_of p l = true -> InList x l -> p x = true.
Proof.
  intros A p l. induction l as [ | y r IH ]; intros x Hall Hin.
  - destruct Hin.
  - simpl in Hall. destruct (andb_split _ _ Hall) as [ Hy Hr ].
    destruct Hin as [ Heq | Hin ].
    + rewrite <- Heq. exact Hy.
    + exact (IH x Hr Hin).
Qed.

Lemma all_of_weaken :
  forall (A : Type) (p q : A -> bool) (l : list A),
    (forall x : A, p x = true -> q x = true) ->
    all_of p l = true -> all_of q l = true.
Proof.
  intros A p q l Himp. induction l as [ | y r IH ]; intros Hall.
  - reflexivity.
  - simpl in Hall. destruct (andb_split _ _ Hall) as [ Hy Hr ].
    simpl. rewrite (Himp y Hy). exact (IH Hr).
Qed.

(* -------------------------------------------------------------------------
   R-11-017a's per-slot field set, which is the same three the link
   contract's slot-table register carries and no fourth: the slot's instant
   in the member's own spine cycles against the member's own origin
   (R-11-014a), its direction, and its guard band. There is no per-slot
   length field, R-15-228d having every slot of a link carry the link's one
   frame length, which is a field of the link and not of a slot.
   ------------------------------------------------------------------------- *)

Inductive Direction : Type := Transmit | Receive.

Definition opposite (d : Direction) : Direction :=
  match d with Transmit => Receive | Receive => Transmit end.

Definition dir_eqb (d1 d2 : Direction) : bool :=
  match d1, d2 with
  | Transmit, Transmit => true
  | Receive, Receive => true
  | Transmit, Receive => false
  | Receive, Transmit => false
  end.

Record LinkSlot : Type := {
  ls_instant : nat;
  ls_direction : Direction;
  ls_guard : nat
}.

(* One endpoint's view of one link's table, with the digest that end binds
   into the session's context (R-12-015d). *)
Record LinkView : Type := {
  lv_slots : list LinkSlot;
  lv_digest : nat
}.

Record LinkTable : Type := {
  lt_near_member : nat;          (* an index into the emission's members    *)
  lt_far_member : nat;
  lt_frame_length : nat;         (* R-15-228d's one frame length per link   *)
  lt_latency : nat;              (* the link's latency bound, an attested
                                    devicetree constant (R-15-196a)         *)
  lt_period : nat;               (* the link's slot period the ensemble
                                    schedule states (R-11-017a); gap b      *)
  lt_cadence : nat;              (* the re-alignment cadence, in slots      *)
  lt_asserted_bound : nat;       (* carried so that the asserting arm of
                                    R-11-014b's chain term is expressible
                                    and refutable; no admitted definition
                                    below reads it                          *)
  lt_near : LinkView;
  lt_far : LinkView
}.

(* R-15-196a's leader tree, as reading 5 presents it. *)
Inductive LeaderRole : Type :=
| Root : LeaderRole
| Follower : nat -> nat -> LeaderRole.

(* The leap slot: which member steps, when, and for how long. Which link it
   reads is that member's leader link and which cadence it runs at is that
   link's, so neither is a field here. *)
Record Leap : Type := {
  leap_member : nat;
  leap_instant : nat;
  leap_width : nat
}.

Record MemberSchedule (T : Type) : Type := {
  ms_cores : list (Frame T);     (* one major frame per core                *)
  ms_crypto_core : nat;          (* an index into ms_cores                  *)
  ms_verify_slot : nat;          (* an index into that core's frame_slots:
                                    the slot that verifies the leader link's
                                    frame (R-15-196a, R-15-228e)            *)
  ms_tolerance : nat;            (* the member's declared oscillator
                                    tolerance                               *)
  ms_role : LeaderRole
}.

Arguments ms_cores {T} _.
Arguments ms_crypto_core {T} _.
Arguments ms_verify_slot {T} _.
Arguments ms_tolerance {T} _.
Arguments ms_role {T} _.

Record Emission (T : Type) : Type := {
  em_members : list (MemberSchedule T);
  em_links : list LinkTable;
  em_leaps : list Leap;
  em_declared_skew : nat         (* reading 10's declared arm: the skew
                                    bound as an attested devicetree
                                    constant                                *)
}.

Arguments em_members {T} _.
Arguments em_links {T} _.
Arguments em_leaps {T} _.
Arguments em_declared_skew {T} _.

(* -------------------------------------------------------------------------
   Members a link names, and the tolerances a drift reads. A link naming a
   member the emission does not carry is refused; the total lookup below is
   read only behind that refusal.
   ------------------------------------------------------------------------- *)

Definition tolerance_of {T : Type} (e : Emission T) (i : nat) : nat :=
  match nth_of (em_members e) i with
  | Some m => ms_tolerance m
  | None => 0
  end.

Definition member_named {T : Type} (e : Emission T) (i : nat) : bool :=
  match nth_of (em_members e) i with
  | Some _ => true
  | None => false
  end.

Definition link_members_named {T : Type} (e : Emission T) (t : LinkTable) : bool :=
  andb (member_named e (lt_near_member t)) (member_named e (lt_far_member t)).

(* -------------------------------------------------------------------------
   Reading 10's two arms. `link_drift` is R-15-196a's own operand list, the
   leap cadence times both members' declared oscillator tolerance.
   ------------------------------------------------------------------------- *)

Definition link_drift {T : Type} (e : Emission T) (t : LinkTable) : nat :=
  lt_cadence t * (tolerance_of e (lt_near_member t) + tolerance_of e (lt_far_member t)).

Fixpoint skew_over {T : Type} (e : Emission T) (ls : list LinkTable) : nat :=
  match ls with
  | nil => 0
  | cons t r => Nat.max (link_drift e t) (skew_over e r)
  end.

(* The arm R-15-196a's own sentence states: derived from declared operands
   and never asserted, one bound for the composition, so the worst link's. *)
Definition skew_derived {T : Type} (e : Emission T) : nat := skew_over e (em_links e).

(* The asserted alternative used only to distinguish a weakened checker.
   Qualification must separately check measured skew against the derived bound. *)
Definition skew_declared {T : Type} (e : Emission T) : nat := em_declared_skew e.

Lemma drift_below_skew_over :
  forall (T : Type) (e : Emission T) (ls : list LinkTable) (t : LinkTable),
    InList t ls -> Nat.leb (link_drift e t) (skew_over e ls) = true.
Proof.
  intros T e ls. induction ls as [ | u r IH ]; intros t Hin.
  - destruct Hin.
  - simpl. destruct Hin as [ Heq | Hin ].
    + rewrite <- Heq. apply max_left.
    + apply (leb_trans _ (skew_over e r)); [ exact (IH t Hin) | apply max_right ].
Qed.

(* -------------------------------------------------------------------------
   Reading 9's two scopes, and the guard-band floor over one of them.
   ------------------------------------------------------------------------- *)

Definition GuardScope : Type := LinkSlot -> bool.

Definition every_slot : GuardScope := fun _ => true.
Definition receive_only : GuardScope := fun s => dir_eqb (ls_direction s) Receive.

Definition slot_guard_ok (scope : GuardScope) (floor : nat) (s : LinkSlot) : bool :=
  orb (negb (scope s)) (Nat.leb floor (ls_guard s)).

Definition view_guard_ok (scope : GuardScope) (floor : nat) (v : LinkView) : bool :=
  all_of (slot_guard_ok scope floor) (lv_slots v).

Definition link_guard_ok (scope : GuardScope) (skew : nat) (t : LinkTable) : bool :=
  andb (view_guard_ok scope (skew + lt_latency t) (lt_near t))
       (view_guard_ok scope (skew + lt_latency t) (lt_far t)).

Lemma every_slot_guard :
  forall (floor : nat) (s : LinkSlot),
    slot_guard_ok every_slot floor s = Nat.leb floor (ls_guard s).
Proof. reflexivity. Qed.

(* R-11-017a's second refusal: the cadence times both members' declared
   tolerance lies inside the guard band. *)
Definition slot_cadence_ok (drift : nat) (s : LinkSlot) : bool :=
  Nat.leb drift (ls_guard s).

Definition link_cadence_ok {T : Type} (e : Emission T) (t : LinkTable) : bool :=
  andb (all_of (slot_cadence_ok (link_drift e t)) (lv_slots (lt_near t)))
       (all_of (slot_cadence_ok (link_drift e t)) (lv_slots (lt_far t))).

(* -------------------------------------------------------------------------
   The composer's self-check that the two views of one link agree
   (R-11-017a): the same slots at the same instants with the same guard
   bands, each end's direction the other's opposite.
   ------------------------------------------------------------------------- *)

Fixpoint slots_agree (a b : list LinkSlot) : bool :=
  match a with
  | nil => match b with nil => true | cons _ _ => false end
  | cons x xs =>
      match b with
      | nil => false
      | cons y ys =>
          andb (Nat.eqb (ls_instant x) (ls_instant y))
               (andb (Nat.eqb (ls_guard x) (ls_guard y))
                     (andb (dir_eqb (ls_direction x) (opposite (ls_direction y)))
                           (slots_agree xs ys)))
      end
  end.

Definition views_agree (t : LinkTable) : bool :=
  slots_agree (lv_slots (lt_near t)) (lv_slots (lt_far t)).

(* R-12-015d's binding: each end's declared digest is the digest of the
   link's table, so the two ends bind one value. *)
Definition link_digest_ok (dg : LinkTable -> nat) (t : LinkTable) : bool :=
  andb (Nat.eqb (lv_digest (lt_near t)) (dg t))
       (Nat.eqb (lv_digest (lt_far t)) (dg t)).

Definition link_ok {T : Type} (e : Emission T) (scope : GuardScope)
                   (skew : nat) (dg : LinkTable -> nat) (t : LinkTable) : bool :=
  andb (link_members_named e t)
       (andb (views_agree t)
             (andb (link_guard_ok scope skew t)
                   (andb (link_cadence_ok e t)
                         (link_digest_ok dg t)))).

(* -------------------------------------------------------------------------
   The leap slot (R-15-196a, R-11-017a): an idle window on every core of the
   member at the same absolute instant, placed after the crypto core's slot
   that verifies the frame whose landing it reads.
   ------------------------------------------------------------------------- *)

Definition slot_clear_of {T : Type} (a w ph : nat) (s : Slot T) : bool :=
  orb (Nat.leb (a + w) (ph + slot_offset s))
      (Nat.leb (ph + slot_offset s + slot_width s) a).

Definition core_admits_the_leap {T : Type} (lp : Leap) (f : Frame T) : bool :=
  andb (Nat.leb (phase_offset f) (leap_instant lp))
       (andb (Nat.leb (leap_instant lp + leap_width lp)
                      (phase_offset f + major_frame f))
             (all_of (@slot_clear_of T (leap_instant lp) (leap_width lp)
                                     (phase_offset f))
                     (frame_slots f))).

Definition leap_covers_every_core {T : Type} (lp : Leap) (m : MemberSchedule T) : bool :=
  andb (Nat.ltb 0 (leap_width lp))
       (all_of (@core_admits_the_leap T lp) (ms_cores m)).

Definition verifying_end {T : Type} (m : MemberSchedule T) : option nat :=
  match nth_of (ms_cores m) (ms_crypto_core m) with
  | None => None
  | Some f =>
      match nth_of (frame_slots f) (ms_verify_slot m) with
      | None => None
      | Some s => Some (phase_offset f + slot_offset s + slot_width s)
      end
  end.

Definition leap_follows_the_verifying_slot {T : Type}
    (lp : Leap) (m : MemberSchedule T) : bool :=
  match verifying_end m with
  | None => false
  | Some x => Nat.leb x (leap_instant lp)
  end.

Definition leap_check {T : Type} (lp : Leap) (m : MemberSchedule T) : bool :=
  andb (leap_covers_every_core lp m) (leap_follows_the_verifying_slot lp m).

(* -------------------------------------------------------------------------
   The leader tree, and the one leap a follower takes.
   ------------------------------------------------------------------------- *)

Fixpoint leaps_of (i : nat) (ls : list Leap) : nat :=
  match ls with
  | nil => 0
  | cons lp r => if Nat.eqb (leap_member lp) i then S (leaps_of i r) else leaps_of i r
  end.

Fixpoint leap_of (i : nat) (ls : list Leap) : option Leap :=
  match ls with
  | nil => None
  | cons lp r => if Nat.eqb (leap_member lp) i then Some lp else leap_of i r
  end.

Definition joins (t : LinkTable) (i p : nat) : bool :=
  orb (andb (Nat.eqb (lt_near_member t) i) (Nat.eqb (lt_far_member t) p))
      (andb (Nat.eqb (lt_near_member t) p) (Nat.eqb (lt_far_member t) i)).

Definition leader_link_ok {T : Type} (e : Emission T) (i p l : nat) : bool :=
  andb (Nat.ltb p i)
       (match nth_of (em_links e) l with
        | None => false
        | Some t => joins t i p
        end).

Definition member_leap_ok {T : Type} (e : Emission T) (i : nat)
                          (m : MemberSchedule T) : bool :=
  match ms_role m with
  | Root => Nat.eqb (leaps_of i (em_leaps e)) 0
  | Follower p l =>
      andb (Nat.eqb (leaps_of i (em_leaps e)) 1)
           (andb (leader_link_ok e i p l)
                 (match leap_of i (em_leaps e) with
                  | None => false
                  | Some lp => leap_check lp m
                  end))
  end.

(* R-11-017a puts the link's own work into the member's R-11-006 interval
   arithmetic as ordinary tasks and grants, so the only check a member's
   cores receive here is CyclicExecutive.v's own. *)
Definition member_ok (c : Composition) (e : Emission (Tenant c)) (i : nat)
                     (m : MemberSchedule (Tenant c)) : bool :=
  andb (all_of (admits c) (ms_cores m)) (member_leap_ok e i m).

Fixpoint members_ok (c : Composition) (e : Emission (Tenant c)) (i : nat)
                    (ms : list (MemberSchedule (Tenant c))) : bool :=
  match ms with
  | nil => true
  | cons m r => andb (member_ok c e i m) (members_ok c e (S i) r)
  end.

Lemma members_ok_cons :
  forall (c : Composition) (e : Emission (Tenant c)) (i : nat)
         (m : MemberSchedule (Tenant c)) (r : list (MemberSchedule (Tenant c))),
    members_ok c e i (cons m r) = andb (member_ok c e i m) (members_ok c e (S i) r).
Proof. reflexivity. Qed.

Fixpoint roots_of {T : Type} (ms : list (MemberSchedule T)) : nat :=
  match ms with
  | nil => 0
  | cons m r => match ms_role m with
                | Root => S (roots_of r)
                | Follower _ _ => roots_of r
                end
  end.

Definition emission_admits (c : Composition) (scope : GuardScope)
                           (rule : Emission (Tenant c) -> nat)
                           (dg : LinkTable -> nat)
                           (e : Emission (Tenant c)) : bool :=
  andb (Nat.eqb (roots_of (em_members e)) 1)
       (andb (all_of (link_ok e scope (rule e) dg) (em_links e))
             (members_ok c e 0 (em_members e))).

(* -------------------------------------------------------------------------
   R-11-014b's chain term over a link hop (reading 7), derived from the
   operands the ensemble schedule states.
   ------------------------------------------------------------------------- *)

Inductive Hop : Type :=
| on_die_hop : nat -> Hop        (* R-11-014b's own arithmetic over the frame
                                    offsets and the per-hop slot periods,
                                    carried as the quantity that entry
                                    derives and this file does not          *)
| link_hop : nat -> Hop.         (* one more edge kind, by link index       *)

Fixpoint max_guard (l : list LinkSlot) : nat :=
  match l with
  | nil => 0
  | cons s r => Nat.max (ls_guard s) (max_guard r)
  end.

Definition link_hop_term {T : Type} (e : Emission T) (i : nat) : option nat :=
  match nth_of (em_links e) i with
  | None => None
  | Some t => Some (lt_period t
                    + Nat.max (max_guard (lv_slots (lt_near t)))
                              (max_guard (lv_slots (lt_far t))))
  end.

(* The construction R-11-014b's "derived ... and never asserted" excludes: a
   per-hop term read off a declared field. *)
Definition asserted_link_hop_term {T : Type} (e : Emission T) (i : nat) : option nat :=
  match nth_of (em_links e) i with
  | None => None
  | Some t => Some (lt_asserted_bound t)
  end.

Fixpoint chain_bound {T : Type} (e : Emission T) (hs : list Hop) : option nat :=
  match hs with
  | nil => Some 0
  | cons h r =>
      match h with
      | on_die_hop x =>
          match chain_bound e r with
          | None => None
          | Some b => Some (x + b)
          end
      | link_hop i =>
          match link_hop_term e i with
          | None => None
          | Some a =>
              match chain_bound e r with
              | None => None
              | Some b => Some (a + b)
              end
          end
      end
  end.

Definition chain_admits {T : Type} (e : Emission T) (hs : list Hop)
                        (deadline : nat) : bool :=
  match chain_bound e hs with
  | None => false
  | Some b => Nat.leb b deadline
  end.

(* What "derived" means, stated so that an asserting construction can be
   refuted at exactly this quantifier: a term that is a function of the
   operands R-11-017a names and of nothing else. *)
Definition OperandDetermined {T : Type} (f : Emission T -> nat -> option nat) : Prop :=
  forall (e1 e2 : Emission T) (i : nat) (t1 t2 : LinkTable),
    nth_of (em_links e1) i = Some t1 ->
    nth_of (em_links e2) i = Some t2 ->
    lt_period t1 = lt_period t2 ->
    lv_slots (lt_near t1) = lv_slots (lt_near t2) ->
    lv_slots (lt_far t1) = lv_slots (lt_far t2) ->
    f e1 i = f e2 i.

(* -------------------------------------------------------------------------
   Retenanting a member, which is R-11-023's act carried to the fourth
   output: the compositor permutes the slot-to-tenant map and the geometry
   the rung fixed does not move.
   ------------------------------------------------------------------------- *)

Fixpoint retenant_cores {T : Type} (rts dts : list T) (cs : list (Frame T))
  : list (Frame T) :=
  match cs with
  | nil => nil
  | cons f r => cons (reassign_frame rts dts f) (retenant_cores rts dts r)
  end.

Definition retenant_member {T : Type} (rts dts : list T) (m : MemberSchedule T)
  : MemberSchedule T :=
  Build_MemberSchedule T (retenant_cores rts dts (ms_cores m)) (ms_crypto_core m)
                       (ms_verify_slot m) (ms_tolerance m) (ms_role m).

Definition MemberOccupancyBlind (T : Type) (chk : MemberSchedule T -> bool) : Prop :=
  forall (rts dts : list T) (m : MemberSchedule T),
    chk (retenant_member rts dts m) = chk m.

Lemma retenant_cores_cons :
  forall (T : Type) (rts dts : list T) (f : Frame T) (r : list (Frame T)),
    retenant_cores rts dts (cons f r)
    = cons (reassign_frame rts dts f) (retenant_cores rts dts r).
Proof. reflexivity. Qed.

Lemma ms_cores_retenant :
  forall (T : Type) (rts dts : list T) (m : MemberSchedule T),
    ms_cores (retenant_member rts dts m) = retenant_cores rts dts (ms_cores m).
Proof. reflexivity. Qed.

Lemma ms_crypto_core_retenant :
  forall (T : Type) (rts dts : list T) (m : MemberSchedule T),
    ms_crypto_core (retenant_member rts dts m) = ms_crypto_core m.
Proof. reflexivity. Qed.

Lemma ms_verify_slot_retenant :
  forall (T : Type) (rts dts : list T) (m : MemberSchedule T),
    ms_verify_slot (retenant_member rts dts m) = ms_verify_slot m.
Proof. reflexivity. Qed.

Lemma same_geometry_sym :
  forall (T : Type) (l1 l2 : list (Slot T)), SameGeometry l1 l2 -> SameGeometry l2 l1.
Proof.
  intros T l1 l2 H. induction H as [ | s t r1 r2 Hw Ho Hb Hp Hrest IH ].
  - apply SG_nil.
  - apply SG_cons; try (symmetry; assumption). exact IH.
Qed.

Lemma same_geometry_clear :
  forall (T : Type) (a w ph : nat) (l1 l2 : list (Slot T)),
    SameGeometry l1 l2 ->
    all_of (@slot_clear_of T a w ph) l1 = all_of (@slot_clear_of T a w ph) l2.
Proof.
  intros T a w ph l1 l2 H.
  induction H as [ | s u r1 r2 Hw Ho Hb Hp Hrest IH ].
  - reflexivity.
  - repeat rewrite all_of_cons. rewrite IH. unfold slot_clear_of.
    rewrite Hw. rewrite Ho. reflexivity.
Qed.

Lemma same_geometry_nth_some :
  forall (T : Type) (l1 l2 : list (Slot T)),
    SameGeometry l1 l2 ->
    forall (k : nat) (s : Slot T),
      nth_of l1 k = Some s ->
      exists u : Slot T, nth_of l2 k = Some u
                         /\ slot_offset u = slot_offset s
                         /\ slot_width u = slot_width s.
Proof.
  intros T l1 l2 H. induction H as [ | x y r1 r2 Hw Ho Hb Hp Hrest IH ]; intros k s Hk.
  - discriminate Hk.
  - destruct k as [ | k ].
    + simpl in Hk. injection Hk as Hk. rewrite <- Hk.
      exists y. split; [ reflexivity | split; symmetry; assumption ].
    + exact (IH k s Hk).
Qed.

Lemma same_geometry_nth_none :
  forall (T : Type) (l1 l2 : list (Slot T)),
    SameGeometry l1 l2 ->
    forall k : nat, nth_of l1 k = None -> nth_of l2 k = None.
Proof.
  intros T l1 l2 H. induction H as [ | x y r1 r2 Hw Ho Hb Hp Hrest IH ]; intros k Hk.
  - reflexivity.
  - destruct k as [ | k ]; [ discriminate Hk | exact (IH k Hk) ].
Qed.

Lemma nth_of_retenant_cores :
  forall (T : Type) (rts dts : list T) (cs : list (Frame T)) (k : nat),
    nth_of (retenant_cores rts dts cs) k
    = match nth_of cs k with
      | None => None
      | Some f => Some (reassign_frame rts dts f)
      end.
Proof.
  intros T rts dts cs. induction cs as [ | f r IH ]; intros k.
  - reflexivity.
  - destruct k as [ | k ].
    + reflexivity.
    + simpl. apply IH.
Qed.

Lemma core_admits_the_leap_same_geometry :
  forall (T : Type) (lp : Leap) (f g : Frame T),
    major_frame f = major_frame g ->
    phase_offset f = phase_offset g ->
    SameGeometry (frame_slots f) (frame_slots g) ->
    core_admits_the_leap lp f = core_admits_the_leap lp g.
Proof.
  intros T lp f g Hm Hp Hgeo.
  unfold core_admits_the_leap. rewrite Hm. rewrite Hp.
  rewrite (same_geometry_clear T (leap_instant lp) (leap_width lp)
                               (phase_offset g) (frame_slots f) (frame_slots g) Hgeo).
  reflexivity.
Qed.

Lemma reassign_frame_keeps_the_leap :
  forall (T : Type) (rts dts : list T) (lp : Leap) (f : Frame T),
    core_admits_the_leap lp (reassign_frame rts dts f) = core_admits_the_leap lp f.
Proof.
  intros T rts dts lp f.
  apply core_admits_the_leap_same_geometry.
  - reflexivity.
  - reflexivity.
  - apply frame_slots_reassign_same_geometry.
Qed.

Lemma leap_covers_retenanted :
  forall (T : Type) (rts dts : list T) (lp : Leap) (m : MemberSchedule T),
    leap_covers_every_core lp (retenant_member rts dts m)
    = leap_covers_every_core lp m.
Proof.
  intros T rts dts lp m. unfold leap_covers_every_core.
  rewrite ms_cores_retenant.
  assert (Hall : forall cs : list (Frame T),
            all_of (@core_admits_the_leap T lp) (retenant_cores rts dts cs)
            = all_of (@core_admits_the_leap T lp) cs).
  { intros cs. induction cs as [ | f r IH ].
    - reflexivity.
    - rewrite retenant_cores_cons. repeat rewrite all_of_cons.
      rewrite reassign_frame_keeps_the_leap. rewrite IH. reflexivity. }
  rewrite Hall. reflexivity.
Qed.

Lemma verifying_end_retenanted :
  forall (T : Type) (rts dts : list T) (m : MemberSchedule T),
    verifying_end (retenant_member rts dts m) = verifying_end m.
Proof.
  intros T rts dts m. unfold verifying_end.
  rewrite ms_cores_retenant. rewrite ms_crypto_core_retenant.
  rewrite ms_verify_slot_retenant. rewrite nth_of_retenant_cores.
  destruct (nth_of (ms_cores m) (ms_crypto_core m)) as [ f | ].
  - assert (Hsym : SameGeometry (frame_slots f)
                                (frame_slots (reassign_frame rts dts f)))
      by (apply same_geometry_sym; apply frame_slots_reassign_same_geometry).
    destruct (nth_of (frame_slots f) (ms_verify_slot m)) as [ s | ] eqn:Es.
    + destruct (same_geometry_nth_some T (frame_slots f)
                 (frame_slots (reassign_frame rts dts f)) Hsym
                 (ms_verify_slot m) s Es) as [ u [ Hu [ Ho Hw ] ] ].
      rewrite Hu. simpl. rewrite Ho. rewrite Hw. reflexivity.
    + rewrite (same_geometry_nth_none T (frame_slots f)
                 (frame_slots (reassign_frame rts dts f)) Hsym
                 (ms_verify_slot m) Es).
      reflexivity.
  - reflexivity.
Qed.

(* =========================================================================
   The obligations.
   ========================================================================= *)

(* O1 (R-11-017a). An admitted emission's every link has agreeing views,
   which is the composer's self-check read back off the verdict. *)
(*| discharges: R-11-017a |*)
Theorem an_admitted_emission_agrees_on_every_link :
  forall (c : Composition) (scope : GuardScope)
         (rule : Emission (Tenant c) -> nat) (dg : LinkTable -> nat)
         (e : Emission (Tenant c)) (t : LinkTable),
    emission_admits c scope rule dg e = true ->
    InList t (em_links e) ->
    views_agree t = true.
Proof.
  intros c scope rule dg e t H Hin.
  unfold emission_admits in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ Hlinks _ ].
  assert (Hok : link_ok e scope (rule e) dg t = true)
    by (exact (all_of_member LinkTable (link_ok e scope (rule e) dg)
                             (em_links e) t Hlinks Hin)).
  unfold link_ok in Hok.
  destruct (andb_split _ _ Hok) as [ _ Hok1 ].
  destruct (andb_split _ _ Hok1) as [ Hag _ ].
  exact Hag.
Qed.

(* O2 (R-11-017a, R-15-196a). An admitted emission's every link meets the
   guard-band floor and the cadence bound, at whatever scope and skew rule
   the composition was checked under. *)
(*| discharges: R-11-017a, R-15-196a |*)
Theorem an_admitted_emission_meets_the_guard_floor :
  forall (c : Composition) (scope : GuardScope)
         (rule : Emission (Tenant c) -> nat) (dg : LinkTable -> nat)
         (e : Emission (Tenant c)) (t : LinkTable),
    emission_admits c scope rule dg e = true ->
    InList t (em_links e) ->
    link_guard_ok scope (rule e) t = true /\ link_cadence_ok e t = true.
Proof.
  intros c scope rule dg e t H Hin.
  unfold emission_admits in H.
  destruct (andb_split _ _ H) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ Hlinks _ ].
  assert (Hok : link_ok e scope (rule e) dg t = true)
    by (exact (all_of_member LinkTable (link_ok e scope (rule e) dg)
                             (em_links e) t Hlinks Hin)).
  unfold link_ok in Hok.
  destruct (andb_split _ _ Hok) as [ _ Hok1 ].
  destruct (andb_split _ _ Hok1) as [ _ Hok2 ].
  destruct (andb_split _ _ Hok2) as [ Hguard Hok3 ].
  destruct (andb_split _ _ Hok3) as [ Hcad _ ].
  split; [ exact Hguard | exact Hcad ].
Qed.

(* O3 (R-12-015d). Each end's declared digest is one function of one link
   table, so the two ends bind one value into the session's context. That a
   different table yields a different value is the hash's property and is
   owed at R-12-015d's construction (reading 6). *)
(*| discharges: R-12-015d |*)
Theorem both_ends_bind_one_digest :
  forall (dg : LinkTable -> nat) (t : LinkTable),
    link_digest_ok dg t = true ->
    lv_digest (lt_near t) = lv_digest (lt_far t).
Proof.
  intros dg t H. unfold link_digest_ok in H.
  destruct (andb_split _ _ H) as [ Hn Hf ].
  rewrite (eqb_eq _ _ Hn). rewrite (eqb_eq _ _ Hf). reflexivity.
Qed.

Lemma members_ok_member :
  forall (c : Composition) (e : Emission (Tenant c))
         (ms : list (MemberSchedule (Tenant c))) (base i : nat)
         (m : MemberSchedule (Tenant c)),
    members_ok c e base ms = true ->
    nth_of ms i = Some m ->
    member_ok c e (i + base) m = true.
Proof.
  intros c e ms. induction ms as [ | x r IH ]; intros base i m Hall Hi.
  - discriminate Hi.
  - rewrite members_ok_cons in Hall.
    destruct (andb_split _ _ Hall) as [ Hx Hr ].
    destruct i as [ | i ].
    + simpl in Hi. injection Hi as Hi. rewrite <- Hi. exact Hx.
    + simpl in Hi.
      assert (Hrec : member_ok c e (i + S base) m = true)
        by (exact (IH (S base) i m Hr Hi)).
      rewrite (plus_succ_r i base) in Hrec. exact Hrec.
Qed.

(* O4 (R-11-017a, R-15-196a). An admitted follower's leap is an idle window
   on every core of the member and is placed after the crypto core's slot
   that verifies the frame it reads. *)
(*| discharges: R-11-017a, R-15-196a |*)
Theorem an_admitted_follower_leaps_after_the_verifying_slot :
  forall (c : Composition) (scope : GuardScope) (rule : Emission (Tenant c) -> nat)
         (dg : LinkTable -> nat) (e : Emission (Tenant c)) (i : nat)
         (m : MemberSchedule (Tenant c)) (p l : nat) (lp : Leap),
    emission_admits c scope rule dg e = true ->
    nth_of (em_members e) i = Some m ->
    ms_role m = Follower p l ->
    leap_of i (em_leaps e) = Some lp ->
    leap_covers_every_core lp m = true
    /\ leap_follows_the_verifying_slot lp m = true.
Proof.
  intros c scope rule dg e i m p l lp Hadm Hi Hrole Hleap.
  unfold emission_admits in Hadm.
  destruct (andb_split _ _ Hadm) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ Hms ].
  assert (Hm : member_ok c e (i + 0) m = true)
    by (exact (members_ok_member c e (em_members e) 0 i m Hms Hi)).
  rewrite (plus_zero_r i) in Hm.
  unfold member_ok in Hm.
  destruct (andb_split _ _ Hm) as [ _ Hlp ].
  unfold member_leap_ok in Hlp. rewrite Hrole in Hlp.
  destruct (andb_split _ _ Hlp) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ _ H3 ].
  rewrite Hleap in H3. unfold leap_check in H3.
  destruct (andb_split _ _ H3) as [ Hcov Hfol ].
  split; [ exact Hcov | exact Hfol ].
Qed.

(* O5 (R-15-196a). A follower's leader is a strictly earlier member, which
   is reading 5's numbering made a verdict. *)
(*| discharges: R-15-196a |*)
Theorem the_leader_tree_is_acyclic :
  forall (c : Composition) (scope : GuardScope) (rule : Emission (Tenant c) -> nat)
         (dg : LinkTable -> nat) (e : Emission (Tenant c)) (i : nat)
         (m : MemberSchedule (Tenant c)) (p l : nat),
    emission_admits c scope rule dg e = true ->
    nth_of (em_members e) i = Some m ->
    ms_role m = Follower p l ->
    Nat.ltb p i = true.
Proof.
  intros c scope rule dg e i m p l Hadm Hi Hrole.
  unfold emission_admits in Hadm.
  destruct (andb_split _ _ Hadm) as [ _ H1 ].
  destruct (andb_split _ _ H1) as [ _ Hms ].
  assert (Hm : member_ok c e (i + 0) m = true)
    by (exact (members_ok_member c e (em_members e) 0 i m Hms Hi)).
  rewrite (plus_zero_r i) in Hm.
  unfold member_ok in Hm.
  destruct (andb_split _ _ Hm) as [ _ Hlp ].
  unfold member_leap_ok in Hlp. rewrite Hrole in Hlp.
  destruct (andb_split _ _ Hlp) as [ _ H2 ].
  destruct (andb_split _ _ H2) as [ Hlink _ ].
  unfold leader_link_ok in Hlink.
  destruct (andb_split _ _ Hlink) as [ Hlt _ ].
  exact Hlt.
Qed.

(* O5b (R-15-196a). The root of the tree takes no leap, read off the
   numbering: the first member cannot be a follower. *)
(*| discharges: R-15-196a |*)
Theorem member_zero_is_not_a_follower :
  forall (c : Composition) (scope : GuardScope) (rule : Emission (Tenant c) -> nat)
         (dg : LinkTable -> nat) (e : Emission (Tenant c))
         (m : MemberSchedule (Tenant c)) (p l : nat),
    emission_admits c scope rule dg e = true ->
    nth_of (em_members e) 0 = Some m ->
    ms_role m <> Follower p l.
Proof.
  intros c scope rule dg e m p l Hadm Hi Hrole.
  assert (Hlt : Nat.ltb p 0 = true)
    by (exact (the_leader_tree_is_acyclic c scope rule dg e 0 m p l Hadm Hi Hrole)).
  discriminate Hlt.
Qed.

(* -------------------------------------------------------------------------
   Reading 9: the two guard scopes are one check on a link the composer
   admits, and differ only on one it refuses.
   ------------------------------------------------------------------------- *)

Lemma pair_scopes_agree :
  forall (floor : nat) (x y : LinkSlot),
    Nat.eqb (ls_guard x) (ls_guard y) = true ->
    dir_eqb (ls_direction x) (opposite (ls_direction y)) = true ->
    andb (slot_guard_ok receive_only floor x) (slot_guard_ok receive_only floor y)
    = andb (slot_guard_ok every_slot floor x) (slot_guard_ok every_slot floor y).
Proof.
  intros floor x y Hg Hd.
  destruct x as [ ix dx gx ], y as [ iy dy gy ].
  assert (Hg2 : gx = gy) by (exact (eqb_eq gx gy Hg)).
  destruct dx, dy; simpl in Hd; try discriminate Hd;
    unfold slot_guard_ok, receive_only, every_slot; simpl; rewrite Hg2;
    destruct (Nat.leb floor gy); reflexivity.
Qed.

Lemma scopes_agree_on_agreeing_views :
  forall (floor : nat) (a b : list LinkSlot),
    slots_agree a b = true ->
    andb (all_of (slot_guard_ok receive_only floor) a)
         (all_of (slot_guard_ok receive_only floor) b)
    = andb (all_of (slot_guard_ok every_slot floor) a)
           (all_of (slot_guard_ok every_slot floor) b).
Proof.
  intros floor a. induction a as [ | x xs IH ]; intros b Hag.
  - destruct b as [ | y ys ]; [ reflexivity | discriminate Hag ].
  - destruct b as [ | y ys ]; [ discriminate Hag | ].
    simpl in Hag.
    destruct (andb_split _ _ Hag) as [ Hi Hrest1 ].
    destruct (andb_split _ _ Hrest1) as [ Hg Hrest2 ].
    destruct (andb_split _ _ Hrest2) as [ Hd Hrest ].
    repeat rewrite all_of_cons.
    rewrite (andb_pair_swap (slot_guard_ok receive_only floor x)
                            (all_of (slot_guard_ok receive_only floor) xs)
                            (slot_guard_ok receive_only floor y)
                            (all_of (slot_guard_ok receive_only floor) ys)).
    rewrite (andb_pair_swap (slot_guard_ok every_slot floor x)
                            (all_of (slot_guard_ok every_slot floor) xs)
                            (slot_guard_ok every_slot floor y)
                            (all_of (slot_guard_ok every_slot floor) ys)).
    rewrite (pair_scopes_agree floor x y Hg Hd).
    rewrite (IH ys Hrest).
    reflexivity.
Qed.

(* O6 (R-11-017a, R-15-196a). The register's two readings of which slots
   carry the guard-band floor are the same check on every link the
   composer's agreement check admits, so no register act is owed to choose
   between them. *)
(*| discharges: R-11-017a, R-15-196a |*)
Theorem the_two_guard_scopes_agree_on_an_agreeing_link :
  forall (skew : nat) (t : LinkTable),
    views_agree t = true ->
    link_guard_ok receive_only skew t = link_guard_ok every_slot skew t.
Proof.
  intros skew t Hag. unfold link_guard_ok, view_guard_ok.
  exact (scopes_agree_on_agreeing_views (skew + lt_latency t)
           (lv_slots (lt_near t)) (lv_slots (lt_far t)) Hag).
Qed.

(* -------------------------------------------------------------------------
   Reading 10: what each arm of the skew bound costs.
   ------------------------------------------------------------------------- *)

(* O7 (R-15-196a, R-11-017a). On the arm R-15-196a's own sentence states,
   the cadence refusal R-11-017a lists separately is implied by its
   guard-band refusal, because the skew bound already dominates every link's
   drift. *)
(*| discharges: R-15-196a, R-11-017a |*)
Theorem on_the_derived_arm_the_cadence_check_is_implied :
  forall (T : Type) (e : Emission T) (t : LinkTable),
    InList t (em_links e) ->
    link_guard_ok every_slot (skew_derived e) t = true ->
    link_cadence_ok e t = true.
Proof.
  intros T e t Hin Hguard.
  assert (Hdrift : Nat.leb (link_drift e t) (skew_derived e) = true)
    by (exact (drift_below_skew_over T e (em_links e) t Hin)).
  assert (Hstep : forall s : LinkSlot,
            slot_guard_ok every_slot (skew_derived e + lt_latency t) s = true ->
            slot_cadence_ok (link_drift e t) s = true).
  { intros s Hs. rewrite every_slot_guard in Hs. unfold slot_cadence_ok.
    apply (leb_trans _ (skew_derived e + lt_latency t)).
    - apply (leb_trans _ (skew_derived e)).
      + exact Hdrift.
      + apply leb_add_r.
    - exact Hs. }
  unfold link_guard_ok, view_guard_ok in Hguard.
  destruct (andb_split _ _ Hguard) as [ Hnear Hfar ].
  unfold link_cadence_ok.
  rewrite (all_of_weaken LinkSlot
             (slot_guard_ok every_slot (skew_derived e + lt_latency t))
             (slot_cadence_ok (link_drift e t))
             (lv_slots (lt_near t)) Hstep Hnear).
  rewrite (all_of_weaken LinkSlot
             (slot_guard_ok every_slot (skew_derived e + lt_latency t))
             (slot_cadence_ok (link_drift e t))
             (lv_slots (lt_far t)) Hstep Hfar).
  reflexivity.
Qed.

(* -------------------------------------------------------------------------
   R-11-014b's link hop term, derived rather than asserted.
   ------------------------------------------------------------------------- *)

(* O8 (R-11-014b, R-11-017a). The per-hop term across a link is a function
   of the link's declared slot period and of the guard bands its own table
   states, and of nothing else. *)
(*| discharges: R-11-014b, R-11-017a |*)
Theorem the_link_hop_term_is_derived :
  forall T : Type, OperandDetermined (@link_hop_term T).
Proof.
  intros T. unfold OperandDetermined. intros e1 e2 i t1 t2 H1 H2 Hp Hn Hf.
  unfold link_hop_term. rewrite H1. rewrite H2.
  rewrite Hp. rewrite Hn. rewrite Hf. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   R-11-023's invariance carried to the fourth output: the leap window is
   decided by the declared geometry and never by who occupies a slot.
   ------------------------------------------------------------------------- *)

(* O9 (R-11-023, R-15-196a). *)
(*| discharges: R-11-023, R-15-196a |*)
Theorem the_leap_check_is_occupancy_blind :
  forall (T : Type) (lp : Leap), MemberOccupancyBlind T (@leap_check T lp).
Proof.
  intros T lp. unfold MemberOccupancyBlind. intros rts dts m. unfold leap_check.
  rewrite (leap_covers_retenanted T rts dts lp m).
  unfold leap_follows_the_verifying_slot.
  rewrite (verifying_end_retenanted T rts dts m).
  reflexivity.
Qed.

(* =========================================================================
   A two-member, one-link emission whose every domain is inhabited, for
   R-05-165's uninhabited-domain mode and for the refutation witnesses.
   Every magnitude below is an arbitrary witness value and carries no
   composition claim (gap a). The cores are authored here rather than taken
   from CyclicExecutive.v's demo frames because that file's rungs fill their
   major frame exactly, leaving no window a kernel-owned idle slot could
   occupy.
   ========================================================================= *)

(* Two cores of one member. `demo_composition`'s full boundary cost
   is what each slot's declared bound is checked against, so a slot's bound
   plus that constant fits its width or the frame is refused. *)

Definition core_zero_reserved : Slot bool := Build_Slot bool 30 0 10 200 true.
Definition core_zero_focus : Slot bool := Build_Slot bool 60 50 40 200 false.
Definition core_zero_link : Slot bool := Build_Slot bool 40 130 20 200 true.

(* The link server's own slot is `core_zero_link`: R-11-017a puts it in the
   member's interval arithmetic as an ordinary task, so it is a slot of an
   ordinary frame and carries no mark of its own. *)
Definition core_zero : Frame bool :=
  Build_Frame bool 200 0 (cons core_zero_reserved nil)
    (Build_Band bool core_zero_focus (cons core_zero_link nil)).

Definition core_one_reserved : Slot bool := Build_Slot bool 30 0 10 200 true.
Definition core_one_focus : Slot bool := Build_Slot bool 60 50 40 200 false.

(* The crypto core's slot that verifies the leader link's frame. It is index
   2 of `frame_slots core_one`, the reserved band's one slot coming first
   and the band's focus second. Its declared bound plus the full boundary
   cost CyclicExecutive.v's own check charges exactly fills its width,
   which is where that constant is load-bearing here rather than merely
   present: one unit more is refused, and
   `a_link_task_that_does_not_fit_its_slot_is_refused` is that unit. *)
Definition core_one_verify : Slot bool := Build_Slot bool 50 110 30 200 true.

Definition core_one : Frame bool :=
  Build_Frame bool 200 0 (cons core_one_reserved nil)
    (Build_Band bool core_one_focus (cons core_one_verify nil)).

Definition demo_cores : list (Frame bool) := cons core_zero (cons core_one nil).

Definition root_member : MemberSchedule bool := {|
  ms_cores := demo_cores;
  ms_crypto_core := 1;
  ms_verify_slot := 2;
  ms_tolerance := 3;
  ms_role := Root
|}.

Definition follower_member : MemberSchedule bool := {|
  ms_cores := demo_cores;
  ms_crypto_core := 1;
  ms_verify_slot := 2;
  ms_tolerance := 5;
  ms_role := Follower 0 0
|}.

(* The digest: an arbitrary witness function standing where a hash belongs
   (gap g). It reads the table's own declared quantities, which is the
   whole of what `link_digest_ok` needs of it. *)
Definition demo_digest (t : LinkTable) : nat :=
  lt_period t + lt_frame_length t
  + max_guard (lv_slots (lt_near t)) + max_guard (lv_slots (lt_far t)).

Definition near_slots : list LinkSlot :=
  cons {| ls_instant := 0; ls_direction := Transmit; ls_guard := 42 |}
       (cons {| ls_instant := 100; ls_direction := Receive; ls_guard := 42 |} nil).

Definition far_slots : list LinkSlot :=
  cons {| ls_instant := 0; ls_direction := Receive; ls_guard := 42 |}
       (cons {| ls_instant := 100; ls_direction := Transmit; ls_guard := 42 |} nil).

Definition demo_link : LinkTable := {|
  lt_near_member := 0;
  lt_far_member := 1;
  lt_frame_length := 256;
  lt_latency := 10;
  lt_period := 100;
  lt_cadence := 4;
  lt_asserted_bound := 0;
  lt_near := {| lv_slots := near_slots; lv_digest := 440 |};
  lt_far := {| lv_slots := far_slots; lv_digest := 440 |}
|}.

Definition demo_leap : Leap := {|
  leap_member := 1;
  leap_instant := 170;
  leap_width := 20
|}.

Definition demo_emission : Emission bool := {|
  em_members := cons root_member (cons follower_member nil);
  em_links := cons demo_link nil;
  em_leaps := cons demo_leap nil;
  em_declared_skew := 20
|}.

(* The computed checks, in the silent form the gate requires: an Example
   proved by eq_refl is decided by the kernel and prints nothing. *)

Example demo_emission_admits_on_the_derived_arm :
  emission_admits demo_composition every_slot skew_derived demo_digest demo_emission
  = true := eq_refl.

Example demo_emission_admits_on_the_declared_arm :
  emission_admits demo_composition every_slot skew_declared demo_digest demo_emission
  = true := eq_refl.

Example demo_emission_admits_under_the_receive_only_scope :
  emission_admits demo_composition receive_only skew_derived demo_digest demo_emission
  = true := eq_refl.

(* The guard band is exactly the floor, so the check is load-bearing rather
   than merely present: one unit less is refused below. *)
Example the_derived_skew_is_the_worst_links_drift :
  skew_derived demo_emission = 32 := eq_refl.

(*| discharges: R-15-196a |*)
Theorem the_two_skew_rules_disagree :
  skew_derived demo_emission <> skew_declared demo_emission.
Proof. intro H. cbv in H. discriminate H. Qed.

(* =========================================================================
   The refusals R-11-017a and R-15-196a name, each seeded so that it fails
   the one conjunct it is about and passes the others.
   ========================================================================= *)

(* 1. A seeded disagreement between the two views of one link. The far end's
      second slot sits one cycle later than the near end's. *)
Definition disagreeing_far_slots : list LinkSlot :=
  cons {| ls_instant := 0; ls_direction := Receive; ls_guard := 42 |}
       (cons {| ls_instant := 101; ls_direction := Transmit; ls_guard := 42 |} nil).

Definition disagreeing_link : LinkTable := {|
  lt_near_member := 0;
  lt_far_member := 1;
  lt_frame_length := 256;
  lt_latency := 10;
  lt_period := 100;
  lt_cadence := 4;
  lt_asserted_bound := 0;
  lt_near := {| lv_slots := near_slots; lv_digest := 440 |};
  lt_far := {| lv_slots := disagreeing_far_slots; lv_digest := 440 |}
|}.

Definition disagreeing_emission : Emission bool := {|
  em_members := cons root_member (cons follower_member nil);
  em_links := cons disagreeing_link nil;
  em_leaps := cons demo_leap nil;
  em_declared_skew := 20
|}.

Example a_seeded_disagreement_is_refused_at_emission :
  views_agree disagreeing_link = false
  /\ link_guard_ok every_slot (skew_derived disagreeing_emission)
                   disagreeing_link = true
  /\ link_cadence_ok disagreeing_emission disagreeing_link = true
  /\ link_digest_ok demo_digest disagreeing_link = true
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     disagreeing_emission = false
  := conj eq_refl (conj eq_refl (conj eq_refl (conj eq_refl eq_refl))).

(* 2. A guard band one cycle below the skew bound plus the link's latency
      bound, on both views so that the agreement check still passes. *)
Definition narrow_near_slots : list LinkSlot :=
  cons {| ls_instant := 0; ls_direction := Transmit; ls_guard := 41 |}
       (cons {| ls_instant := 100; ls_direction := Receive; ls_guard := 42 |} nil).

Definition narrow_far_slots : list LinkSlot :=
  cons {| ls_instant := 0; ls_direction := Receive; ls_guard := 41 |}
       (cons {| ls_instant := 100; ls_direction := Transmit; ls_guard := 42 |} nil).

Definition narrow_link : LinkTable := {|
  lt_near_member := 0;
  lt_far_member := 1;
  lt_frame_length := 256;
  lt_latency := 10;
  lt_period := 100;
  lt_cadence := 4;
  lt_asserted_bound := 0;
  lt_near := {| lv_slots := narrow_near_slots; lv_digest := 440 |};
  lt_far := {| lv_slots := narrow_far_slots; lv_digest := 440 |}
|}.

Definition narrow_emission : Emission bool := {|
  em_members := cons root_member (cons follower_member nil);
  em_links := cons narrow_link nil;
  em_leaps := cons demo_leap nil;
  em_declared_skew := 20
|}.

Example a_guard_band_below_the_floor_is_refused :
  views_agree narrow_link = true
  /\ link_cadence_ok narrow_emission narrow_link = true
  /\ link_guard_ok every_slot (skew_derived narrow_emission) narrow_link = false
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     narrow_emission = false
  := conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* 3. A leap cadence whose drift falls outside the guard band. On the
      declared arm the cadence refusal is the only one that fires, which is
      reading 10's independence; on the derived arm the same emission is
      refused twice over, because the derived bound rises with the cadence
      and takes the guard-band floor with it. *)
Definition out_of_band_link : LinkTable := {|
  lt_near_member := 0;
  lt_far_member := 1;
  lt_frame_length := 256;
  lt_latency := 10;
  lt_period := 100;
  lt_cadence := 6;
  lt_asserted_bound := 0;
  lt_near := {| lv_slots := near_slots; lv_digest := 440 |};
  lt_far := {| lv_slots := far_slots; lv_digest := 440 |}
|}.

Definition out_of_band_emission : Emission bool := {|
  em_members := cons root_member (cons follower_member nil);
  em_links := cons out_of_band_link nil;
  em_leaps := cons demo_leap nil;
  em_declared_skew := 20
|}.

Example a_leap_cadence_outside_the_band_is_refused :
  link_cadence_ok out_of_band_emission out_of_band_link = false
  /\ emission_admits demo_composition every_slot skew_declared demo_digest
                     out_of_band_emission = false
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     out_of_band_emission = false
  := conj eq_refl (conj eq_refl eq_refl).

(* Reading 10's other half: on the declared arm the cadence check decides
   something the guard-band check does not. *)
(*| discharges: R-11-017a |*)
Example on_the_declared_arm_the_cadence_check_is_independent :
  link_guard_ok every_slot (skew_declared out_of_band_emission) out_of_band_link = true
  /\ link_cadence_ok out_of_band_emission out_of_band_link = false
  := conj eq_refl eq_refl.

(* 4. A leap slot that does not cover every core: one core of the member
      runs a partition's slot across the window, which is exactly what
      R-15-196a's "no partition's slot straddles the step" excludes. *)
Definition core_zero_busy_link : Slot bool := Build_Slot bool 40 160 20 200 true.

Definition core_zero_busy : Frame bool :=
  Build_Frame bool 200 0 (cons core_zero_reserved nil)
    (Build_Band bool core_zero_focus (cons core_zero_busy_link nil)).

Definition busy_follower : MemberSchedule bool := {|
  ms_cores := cons core_zero_busy (cons core_one nil);
  ms_crypto_core := 1;
  ms_verify_slot := 2;
  ms_tolerance := 5;
  ms_role := Follower 0 0
|}.

Definition uncovered_emission : Emission bool := {|
  em_members := cons root_member (cons busy_follower nil);
  em_links := cons demo_link nil;
  em_leaps := cons demo_leap nil;
  em_declared_skew := 20
|}.

Example a_leap_that_misses_a_core_is_refused :
  all_of (admits demo_composition) (ms_cores busy_follower) = true
  /\ leap_follows_the_verifying_slot demo_leap busy_follower = true
  /\ leap_covers_every_core demo_leap busy_follower = false
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     uncovered_emission = false
  := conj eq_refl (conj eq_refl (conj eq_refl eq_refl)).

(* A leap of no width covers every core for free, which is why the window
   carries a width conjunct of its own. *)
Definition zero_width_leap : Leap := {|
  leap_member := 1;
  leap_instant := 170;
  leap_width := 0
|}.

Definition zero_width_emission : Emission bool := {|
  em_members := cons root_member (cons follower_member nil);
  em_links := cons demo_link nil;
  em_leaps := cons zero_width_leap nil;
  em_declared_skew := 20
|}.

Example a_leap_of_no_width_is_refused :
  leap_covers_every_core zero_width_leap follower_member = false
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     zero_width_emission = false
  := conj eq_refl eq_refl.

(* 5. A leap slot placed before the crypto core's slot that verifies the
      frame whose landing it reads. The window sits in a gap free on every
      core, so only the ordering conjunct fires. *)
Definition early_leap : Leap := {|
  leap_member := 1;
  leap_instant := 30;
  leap_width := 15
|}.

Definition early_emission : Emission bool := {|
  em_members := cons root_member (cons follower_member nil);
  em_links := cons demo_link nil;
  em_leaps := cons early_leap nil;
  em_declared_skew := 20
|}.

Example a_leap_before_the_verifying_slot_is_refused :
  leap_covers_every_core early_leap follower_member = true
  /\ leap_follows_the_verifying_slot early_leap follower_member = false
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     early_emission = false
  := conj eq_refl (conj eq_refl eq_refl).

(* The verifying slot is looked up and the lookup is fail-closed: a member
   naming a slot its crypto core does not carry takes no leap. *)
Definition unfound_verify_follower : MemberSchedule bool := {|
  ms_cores := demo_cores;
  ms_crypto_core := 1;
  ms_verify_slot := 3;
  ms_tolerance := 5;
  ms_role := Follower 0 0
|}.

Definition unfound_verify_emission : Emission bool := {|
  em_members := cons root_member (cons unfound_verify_follower nil);
  em_links := cons demo_link nil;
  em_leaps := cons demo_leap nil;
  em_declared_skew := 20
|}.

Example a_verifying_slot_that_is_not_there_is_refused :
  verifying_end unfound_verify_follower = None
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     unfound_verify_emission = false
  := conj eq_refl eq_refl.

(* R-11-017a's third refusal, which this file states by not stating it: the
   link's own work is ordinary slots of the member's own frames, so a link
   task whose declared bound plus the full boundary cost overruns its
   slot is refused by R-11-006's interval arithmetic and by nothing added
   here (reading 1, gap f). *)
Definition core_one_overlong_verify : Slot bool := Build_Slot bool 50 110 31 200 true.

Definition core_one_overlong : Frame bool :=
  Build_Frame bool 200 0 (cons core_one_reserved nil)
    (Build_Band bool core_one_focus (cons core_one_overlong_verify nil)).

Definition overlong_follower : MemberSchedule bool := {|
  ms_cores := cons core_zero (cons core_one_overlong nil);
  ms_crypto_core := 1;
  ms_verify_slot := 2;
  ms_tolerance := 5;
  ms_role := Follower 0 0
|}.

Definition overlong_emission : Emission bool := {|
  em_members := cons root_member (cons overlong_follower nil);
  em_links := cons demo_link nil;
  em_leaps := cons demo_leap nil;
  em_declared_skew := 20
|}.

Example a_link_task_that_does_not_fit_its_slot_is_refused :
  admits demo_composition core_one_overlong = false
  /\ leap_check demo_leap overlong_follower = true
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     overlong_emission = false
  := conj eq_refl (conj eq_refl eq_refl).

(* A link naming a member the emission does not carry, refused rather than
   read through a default tolerance. *)
Definition unnamed_member_link : LinkTable := {|
  lt_near_member := 0;
  lt_far_member := 7;
  lt_frame_length := 256;
  lt_latency := 10;
  lt_period := 100;
  lt_cadence := 4;
  lt_asserted_bound := 0;
  lt_near := {| lv_slots := near_slots; lv_digest := 440 |};
  lt_far := {| lv_slots := far_slots; lv_digest := 440 |}
|}.

Definition unnamed_member_emission : Emission bool := {|
  em_members := cons root_member (cons follower_member nil);
  em_links := cons unnamed_member_link nil;
  em_leaps := cons demo_leap nil;
  em_declared_skew := 20
|}.

Example a_link_naming_no_member_is_refused :
  link_members_named unnamed_member_emission unnamed_member_link = false
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     unnamed_member_emission = false
  := conj eq_refl eq_refl.

(* Two roots, and a root that leaps: R-15-196a's tree has one root taking no
   leap, and both departures are refused. *)
Definition second_root : MemberSchedule bool := {|
  ms_cores := demo_cores;
  ms_crypto_core := 1;
  ms_verify_slot := 2;
  ms_tolerance := 5;
  ms_role := Root
|}.

Definition two_root_emission : Emission bool := {|
  em_members := cons root_member (cons second_root nil);
  em_links := cons demo_link nil;
  em_leaps := nil;
  em_declared_skew := 20
|}.

Definition root_leap : Leap := {|
  leap_member := 0;
  leap_instant := 170;
  leap_width := 20
|}.

Definition leaping_root_emission : Emission bool := {|
  em_members := cons root_member (cons follower_member nil);
  em_links := cons demo_link nil;
  em_leaps := cons root_leap (cons demo_leap nil);
  em_declared_skew := 20
|}.

Example a_tree_with_two_roots_is_refused :
  roots_of (em_members two_root_emission) = 2
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     two_root_emission = false
  := conj eq_refl eq_refl.

Example a_root_that_leaps_is_refused :
  roots_of (em_members leaping_root_emission) = 1
  /\ leaps_of 0 (em_leaps leaping_root_emission) = 1
  /\ emission_admits demo_composition every_slot skew_derived demo_digest
                     leaping_root_emission = false
  := conj eq_refl (conj eq_refl eq_refl).

(* Reading 9's other half: the two scopes differ only where the composer's
   agreement check already refuses. Both views name a transmit slot, so
   `receive_only` reaches neither and `every_slot` reaches both. *)
Definition scope_split_link : LinkTable := {|
  lt_near_member := 0;
  lt_far_member := 1;
  lt_frame_length := 256;
  lt_latency := 0;
  lt_period := 100;
  lt_cadence := 4;
  lt_asserted_bound := 0;
  lt_near := {| lv_slots := cons {| ls_instant := 0;
                                    ls_direction := Transmit;
                                    ls_guard := 20 |} nil;
                lv_digest := 0 |};
  lt_far := {| lv_slots := cons {| ls_instant := 0;
                                   ls_direction := Transmit;
                                   ls_guard := 42 |} nil;
               lv_digest := 0 |}
|}.

(*| discharges: R-15-196a, R-11-017a |*)
Example the_scopes_differ_only_on_a_link_the_composer_refuses :
  views_agree scope_split_link = false
  /\ link_guard_ok every_slot 42 scope_split_link = false
  /\ link_guard_ok receive_only 42 scope_split_link = true
  := conj eq_refl (conj eq_refl eq_refl).

(* =========================================================================
   The chain, and the difference between a derived bound and an asserted
   one (R-11-014b).
   ========================================================================= *)

Definition demo_chain : list Hop :=
  cons (on_die_hop 30) (cons (link_hop 0) (cons (on_die_hop 20) nil)).

Example the_link_hop_contributes_its_period_and_its_guard_band :
  link_hop_term demo_emission 0 = Some 142 := eq_refl.

Example the_chain_bound_is_computed_from_its_hops :
  chain_bound demo_emission demo_chain = Some 192 := eq_refl.

(* R-11-014b refuses a chain whose derived bound exceeds the deadline its
   declaration carries, and the boundary is where the check is load-bearing
   rather than merely present. *)
Example one_cycle_of_chain_bound_decides :
  chain_admits demo_emission demo_chain 192 = true
  /\ chain_admits demo_emission demo_chain 191 = false
  := conj eq_refl eq_refl.

(* A chain naming a link the emission does not carry is refused rather than
   bounded by a default. *)
Example a_chain_over_an_unnamed_link_is_refused :
  chain_bound demo_emission (cons (link_hop 4) nil) = None
  /\ chain_admits demo_emission (cons (link_hop 4) nil) 1000 = false
  := conj eq_refl eq_refl.

(* The two emissions that differ in the asserted field alone. *)
Definition asserted_link_a : LinkTable := {|
  lt_near_member := 0;
  lt_far_member := 1;
  lt_frame_length := 256;
  lt_latency := 10;
  lt_period := 100;
  lt_cadence := 4;
  lt_asserted_bound := 0;
  lt_near := {| lv_slots := near_slots; lv_digest := 440 |};
  lt_far := {| lv_slots := far_slots; lv_digest := 440 |}
|}.

Definition asserted_link_b : LinkTable := {|
  lt_near_member := 0;
  lt_far_member := 1;
  lt_frame_length := 256;
  lt_latency := 10;
  lt_period := 100;
  lt_cadence := 4;
  lt_asserted_bound := 1;
  lt_near := {| lv_slots := near_slots; lv_digest := 440 |};
  lt_far := {| lv_slots := far_slots; lv_digest := 440 |}
|}.

Definition asserted_emission_a : Emission bool := {|
  em_members := cons root_member (cons follower_member nil);
  em_links := cons asserted_link_a nil;
  em_leaps := cons demo_leap nil;
  em_declared_skew := 20
|}.

Definition asserted_emission_b : Emission bool := {|
  em_members := cons root_member (cons follower_member nil);
  em_links := cons asserted_link_b nil;
  em_leaps := cons demo_leap nil;
  em_declared_skew := 20
|}.

(* R-11-014b's "derived ... and never asserted", made a refusal: a per-hop
   term read off a declared field moves where the operands do not. *)
Theorem the_asserted_chain_term_is_refuted :
  ~ OperandDetermined (@asserted_link_hop_term bool).
Proof.
  intros H. unfold OperandDetermined in H.
  specialize (H asserted_emission_a asserted_emission_b 0
                asserted_link_a asserted_link_b
                eq_refl eq_refl eq_refl eq_refl eq_refl).
  cbv in H. discriminate H.
Qed.

(* =========================================================================
   Refutation witnesses (R-05-166). Each is an alternative construction the
   register's own sentence excludes, so the obligations above exclude
   something rather than agreeing with this file's definitions.
   ========================================================================= *)

(* A digest that is not a function of the link's table. It passes the digest
   check at both ends of a link whose two views disagree, so the digest
   check does not carry the agreement check and R-11-017a states both. *)
Definition constant_digest : LinkTable -> nat := fun _ => 0.

Definition constant_digest_link : LinkTable := {|
  lt_near_member := 0;
  lt_far_member := 1;
  lt_frame_length := 256;
  lt_latency := 10;
  lt_period := 100;
  lt_cadence := 4;
  lt_asserted_bound := 0;
  lt_near := {| lv_slots := near_slots; lv_digest := 0 |};
  lt_far := {| lv_slots := disagreeing_far_slots; lv_digest := 0 |}
|}.

Theorem a_constant_digest_binds_nothing :
  link_digest_ok constant_digest constant_digest_link = true
  /\ views_agree constant_digest_link = false.
Proof. split; reflexivity. Qed.

(* And the converse, so that neither check stands in for the other: a link
   whose two views agree and whose declared digests are not the table's. *)
Definition mis_digested_link : LinkTable := {|
  lt_near_member := 0;
  lt_far_member := 1;
  lt_frame_length := 256;
  lt_latency := 10;
  lt_period := 100;
  lt_cadence := 4;
  lt_asserted_bound := 0;
  lt_near := {| lv_slots := near_slots; lv_digest := 441 |};
  lt_far := {| lv_slots := far_slots; lv_digest := 441 |}
|}.

Theorem the_agreement_check_does_not_carry_the_digest :
  views_agree mis_digested_link = true
  /\ link_digest_ok demo_digest mis_digested_link = false.
Proof. split; reflexivity. Qed.

(* A leap check that reads a slot's tenant. R-11-023 has the interval
   arithmetic quantify over widths and offsets and never occupants, and the
   fourth output's own checks are held to the same rule, so this one is not
   the check. *)
Definition leap_check_by_tenant {T : Type} (tenant_ok : T -> bool) (lp : Leap)
                                (m : MemberSchedule T) : bool :=
  andb (leap_check lp m)
       (all_of (fun f : Frame T =>
                  tenant_ok (slot_tenant (band_focus (discretionary_band f))))
               (ms_cores m)).

Theorem a_tenant_reading_leap_check_is_refuted :
  ~ MemberOccupancyBlind bool (leap_check_by_tenant (fun t : bool => t) demo_leap).
Proof.
  intros H. unfold MemberOccupancyBlind in H.
  specialize (H (cons true nil) (cons true (cons true nil)) follower_member).
  cbv in H. discriminate H.
Qed.

(* A guard-band floor that does not read the skew bound. It admits the
   narrow link the floor R-11-017a states refuses, which is what makes the
   floor's operands content rather than decoration. *)
Theorem a_weaker_guard_floor_admits_what_this_one_refuses :
  link_guard_ok every_slot (skew_derived narrow_emission) narrow_link = false
  /\ link_guard_ok every_slot 0 narrow_link = true.
Proof. split; reflexivity. Qed.

(* =========================================================================
   R-05-166's inhabitation witnesses: one closed definition per record this
   file's statements quantify over, named for that record and ascribed at
   it. A record this file reaches through its Require is witnessed in the
   file that declares it.
   ========================================================================= *)

Definition witness_LinkSlot : LinkSlot :=
  {| ls_instant := 0; ls_direction := Transmit; ls_guard := 42 |}.
Definition witness_LinkView : LinkView :=
  {| lv_slots := near_slots; lv_digest := 440 |}.
Definition witness_LinkTable : LinkTable := demo_link.
Definition witness_Leap : Leap := demo_leap.
Definition witness_MemberSchedule : MemberSchedule bool := follower_member.
Definition witness_Emission : Emission bool := demo_emission.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, as in the artifacts beside this one.
   ------------------------------------------------------------------------- *)

Print Assumptions andb_split.
Print Assumptions andb_pair_swap.
Print Assumptions leb_refl.
Print Assumptions leb_trans.
Print Assumptions leb_add_r.
Print Assumptions max_left.
Print Assumptions max_right.
Print Assumptions eqb_eq.
Print Assumptions plus_zero_r.
Print Assumptions plus_succ_r.
Print Assumptions all_of_cons.
Print Assumptions all_of_member.
Print Assumptions all_of_weaken.
Print Assumptions nth_of.
Print Assumptions tolerance_of.
Print Assumptions link_members_named.
Print Assumptions link_drift.
Print Assumptions skew_derived.
Print Assumptions skew_declared.
Print Assumptions drift_below_skew_over.
Print Assumptions every_slot.
Print Assumptions receive_only.
Print Assumptions slot_guard_ok.
Print Assumptions link_guard_ok.
Print Assumptions every_slot_guard.
Print Assumptions link_cadence_ok.
Print Assumptions slots_agree.
Print Assumptions views_agree.
Print Assumptions link_digest_ok.
Print Assumptions link_ok.
Print Assumptions slot_clear_of.
Print Assumptions core_admits_the_leap.
Print Assumptions leap_covers_every_core.
Print Assumptions verifying_end.
Print Assumptions leap_follows_the_verifying_slot.
Print Assumptions leap_check.
Print Assumptions leader_link_ok.
Print Assumptions member_leap_ok.
Print Assumptions member_ok.
Print Assumptions members_ok.
Print Assumptions roots_of.
Print Assumptions emission_admits.
Print Assumptions max_guard.
Print Assumptions link_hop_term.
Print Assumptions asserted_link_hop_term.
Print Assumptions chain_bound.
Print Assumptions chain_admits.
Print Assumptions retenant_cores.
Print Assumptions retenant_member.
Print Assumptions same_geometry_sym.
Print Assumptions same_geometry_clear.
Print Assumptions same_geometry_nth_some.
Print Assumptions same_geometry_nth_none.
Print Assumptions nth_of_retenant_cores.
Print Assumptions core_admits_the_leap_same_geometry.
Print Assumptions reassign_frame_keeps_the_leap.
Print Assumptions leap_covers_retenanted.
Print Assumptions verifying_end_retenanted.
Print Assumptions an_admitted_emission_agrees_on_every_link.
Print Assumptions an_admitted_emission_meets_the_guard_floor.
Print Assumptions both_ends_bind_one_digest.
Print Assumptions members_ok_member.
Print Assumptions an_admitted_follower_leaps_after_the_verifying_slot.
Print Assumptions the_leader_tree_is_acyclic.
Print Assumptions member_zero_is_not_a_follower.
Print Assumptions pair_scopes_agree.
Print Assumptions scopes_agree_on_agreeing_views.
Print Assumptions the_two_guard_scopes_agree_on_an_agreeing_link.
Print Assumptions on_the_derived_arm_the_cadence_check_is_implied.
Print Assumptions the_link_hop_term_is_derived.
Print Assumptions the_leap_check_is_occupancy_blind.
Print Assumptions demo_emission_admits_on_the_derived_arm.
Print Assumptions demo_emission_admits_on_the_declared_arm.
Print Assumptions demo_emission_admits_under_the_receive_only_scope.
Print Assumptions the_derived_skew_is_the_worst_links_drift.
Print Assumptions the_two_skew_rules_disagree.
Print Assumptions a_seeded_disagreement_is_refused_at_emission.
Print Assumptions a_guard_band_below_the_floor_is_refused.
Print Assumptions a_leap_cadence_outside_the_band_is_refused.
Print Assumptions on_the_declared_arm_the_cadence_check_is_independent.
Print Assumptions a_leap_that_misses_a_core_is_refused.
Print Assumptions a_leap_of_no_width_is_refused.
Print Assumptions a_leap_before_the_verifying_slot_is_refused.
Print Assumptions a_verifying_slot_that_is_not_there_is_refused.
Print Assumptions a_link_task_that_does_not_fit_its_slot_is_refused.
Print Assumptions a_link_naming_no_member_is_refused.
Print Assumptions a_tree_with_two_roots_is_refused.
Print Assumptions a_root_that_leaps_is_refused.
Print Assumptions the_scopes_differ_only_on_a_link_the_composer_refuses.
Print Assumptions the_link_hop_contributes_its_period_and_its_guard_band.
Print Assumptions the_chain_bound_is_computed_from_its_hops.
Print Assumptions one_cycle_of_chain_bound_decides.
Print Assumptions a_chain_over_an_unnamed_link_is_refused.
Print Assumptions the_asserted_chain_term_is_refuted.
Print Assumptions a_constant_digest_binds_nothing.
Print Assumptions the_agreement_check_does_not_carry_the_digest.
Print Assumptions a_tenant_reading_leap_check_is_refuted.
Print Assumptions a_weaker_guard_floor_admits_what_this_one_refuses.

(* The normative qualification wrapper keeps the derived bound and the physical
   qualification observation separate. R-15-196a requires both; its measured
   acceptance clause does not authorize replacement of the derived operand. *)
Definition with_derived_bound {T : Type} (e : Emission T) : Emission T := {|
  em_members := em_members e; em_links := em_links e; em_leaps := em_leaps e;
  em_declared_skew := skew_derived e |}.
Definition qualified_emission_admits (c : Composition) (dg : LinkTable -> nat)
    (e : Emission (Tenant c)) (measured_skew : nat) : bool :=
  andb (Nat.eqb (em_declared_skew e) (skew_derived e))
    (andb (Nat.leb measured_skew (skew_derived e))
      (emission_admits c every_slot skew_derived dg e)).
Theorem qualification_uses_the_derived_bound : forall c dg e measured,
  qualified_emission_admits c dg e measured = true ->
  em_declared_skew e = skew_derived e /\
  Nat.leb measured (skew_derived e) = true /\
  emission_admits c every_slot skew_derived dg e = true.
Proof.
  intros c dg e measured H; unfold qualified_emission_admits in H.
  apply andb_split in H as [Hbound Hrest].
  apply andb_split in Hrest as [Hmeasure Hbase].
  apply eqb_eq in Hbound; repeat split; assumption.
Qed.
Example the_qualified_reference_emission_is_accepted :
  qualified_emission_admits demo_composition demo_digest
    (with_derived_bound demo_emission) 20 = true := eq_refl.
Example an_asserted_bound_cannot_replace_derivation :
  emission_admits demo_composition every_slot skew_declared demo_digest demo_emission = true /\
  qualified_emission_admits demo_composition demo_digest demo_emission 20 = false.
Proof. split; reflexivity. Qed.
Example a_measured_pair_above_the_bound_fails_qualification :
  qualified_emission_admits demo_composition demo_digest
    (with_derived_bound demo_emission) 33 = false := eq_refl.
Example the_six_required_schedule_refusals_reach_the_qualified_entry :
  qualified_emission_admits demo_composition demo_digest
    (with_derived_bound disagreeing_emission) 20 = false /\
  qualified_emission_admits demo_composition demo_digest
    (with_derived_bound narrow_emission) 20 = false /\
  qualified_emission_admits demo_composition demo_digest
    (with_derived_bound out_of_band_emission) 20 = false /\
  qualified_emission_admits demo_composition demo_digest
    (with_derived_bound uncovered_emission) 20 = false /\
  qualified_emission_admits demo_composition demo_digest
    (with_derived_bound early_emission) 20 = false /\
  qualified_emission_admits demo_composition demo_digest
    (with_derived_bound overlong_emission) 20 = false.
Proof. repeat split; reflexivity. Qed.
(* A verified frame is a trusted crypto-core result, not a client approval bit.
   This is the bounded decision at an already admitted leap window; connecting
   it to the boot kernel's exclusive origin-store capability remains a join. *)
Definition leap_magnitude (bound reading : nat) (frame_verified : bool) : option nat :=
  if frame_verified then if Nat.leb reading bound then Some reading else None else None.
Theorem unverified_frames_never_supply_a_leap : forall bound reading,
  leap_magnitude bound reading false = None.
Proof. reflexivity. Qed.
Theorem a_leap_magnitude_never_exceeds_its_bound : forall bound reading amount,
  leap_magnitude bound reading true = Some amount ->
  amount = reading /\ Nat.leb amount bound = true.
Proof.
  intros bound reading amount H; unfold leap_magnitude in H.
  destruct (Nat.leb reading bound) eqn:E; try discriminate.
  injection H as H; subst; split; [reflexivity | exact E].
Qed.
Example verified_unverified_and_excessive_magnitudes_are_distinguished :
  leap_magnitude 32 20 true = Some 20 /\
  leap_magnitude 32 20 false = None /\ leap_magnitude 32 33 true = None.
Proof. repeat split; reflexivity. Qed.
Print Assumptions qualification_uses_the_derived_bound.
Print Assumptions unverified_frames_never_supply_a_leap.
Print Assumptions a_leap_magnitude_never_exceeds_its_bound.
