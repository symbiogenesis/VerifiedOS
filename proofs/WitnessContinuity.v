(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   WitnessContinuity.v

   The witness-policy reference model and its continuity argument, as the
   register fixes them: R-13-023c's machine-checked safety argument that
   within each policy epoch every pair of acceptable quorums shares an
   honest witness whose authenticated history prevents inconsistent
   accepted checkpoints, over the witness identities and keys, the
   persistent state, the recovery discipline and the policy transitions
   that entry puts inside the policy rather than beside it; R-13-023b's
   pinned checkpoint and its refusal of an inconsistent one; R-13-023a's
   statement that witnessed public commitment establishes neither uniform
   release selection nor the absence of targeted software; and R-17-030v's
   fail-closed seam, where a checkpoint failing the policy stops the
   install and leaves the running generation untouched.

   What this file is. A reference model with proofs of quorum and history
   safety under explicit external assumptions, not an implementation.
   Every quantity a policy or
   a deployment fixes is a field of a record rather than a literal or a
   top-level Parameter, which is what keeps the R-05-163 assumption gate
   green while leaving the decision where its owner can make it. Nothing is
   admitted and nothing is axiomatized: the Print Assumptions block at the
   end reports every shipped constant closed under the global context.

   What the gate's green line means. The stated model theorems are compiled,
   axiom-free, non-vacuous and enumerated. No signature is checked, no
   hash is computed, no Merkle path is walked, no byte is parsed and no
   external witness is contacted. Authentication enters as a hypothesis on
   a deployment and never as a proved property of a primitive.

   What this file does not author, with the owner of each decision.

   a. Every cryptographic foundation. Unforgeability is the hypothesis
      `Unforgeable` below, quantified over in every theorem that uses it
      and discharged nowhere here; the unassigned-proof map's row 27 prices
      one qualified symbolic-authentication foundation at U-20, and this
      file deliberately does not axiomatize what that slice owes. The same
      goes for inclusion and consistency proofs: a checkpoint is a list of
      logged names, prefix stands for a checked consistency proof and
      membership for a checked inclusion proof, exactly as Q22b's bounded
      model stands them, and M6.2c owns the reader that decides them over
      fixed-layout bytes.
   b. The local evidence validator and the update transaction. M6.2c owns
      the bounded reader and its refinement against this model, and M5.4
      consumes its decision. Nothing below parses, bounds an input, or
      writes a durable pin.
   c. Production witness operation. External witness behaviour is an
      assumption of this local proof, which R-13-023c's third acceptance
      clause says outright, and no theorem here claims a deployment
      satisfies it.

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. An identity is a position in the policy's key roster, and the roster
      is the population. R-13-023c puts the witness identities and keys
      inside the policy, so the roster is one field and the population is
      its length rather than a second field a policy could contradict.
      Distinct identities are distinct by construction; what remains a
      checked obligation is that distinct identities hold distinct keys,
      which `wellformedb` carries and `enrolled_keys_identify_witnesses`
      states. `duplicated_keys_let_one_holder_fill_two_slots` is the
      construction that obligation excludes.
   2. An acceptable quorum is any set of at least K enrolled identities.
      R-13-023c's acceptance clause fixes a flat policy admitting every
      size-K subset, and a larger accepted set contains a size-K one, so
      the counted form is the same acceptance set and needs no separate
      minimal-quorum step. The count is over distinct accepted signer
      positions rather than over signatures, so a repeated signature
      contributes once.
   3. The safety condition is stated without natural subtraction and
      proved equal to the register's own spelling.
      `safe_matches_the_register_spelling` holds `population + f < 2K`
      against `f < 2K - population`, which are the same predicate because
      truncation makes the register's right-hand side zero exactly where
      the left-hand comparison already fails.
   4. Availability is not a term in any safety statement. It is a separate
      predicate over a responsive set, `availableb`, and the two are shown
      independent in both directions. `withholding_bound_is_sufficient` is
      the qualification's `N - f - o >= K` as a theorem, and
      `lowering_the_threshold_to_restore_progress_can_break_safety` is why
      a threshold is never reduced to buy progress.
   5. The durable discipline is a state machine and its no-fork property
      is derived rather than assumed. An honest witness separates the
      volatile proposal from the durable record and from the authenticated
      antirollback anchor; `Inv` is the inductive invariant, and the chain
      property every deployment theorem needs is `honest_run_never_forks`,
      proved of the machine rather than postulated of a witness.
   6. Storage loss and rollback are adversarial actions inside the model,
      not assumptions outside it. `Damage` sets the failing store to any
      value at any point, and the anchor is what the specification
      consults. The `anchored` flag carries both readings so the tolerant
      one can be refuted rather than merely omitted, which is what
      `rollback_is_refused_and_tolerating_it_forks` does.
   7. A terminal transition is a statement a witness signs and a closure it
      persists, so the old epoch closes inside the same machine. Sealing
      freezes the trusted record, which is `sealed_run_keeps_its_trusted`,
      and every statement a sealed identity ever released is a prefix of
      the anchor, which is what carries `old_epoch_cannot_pass_the_anchor`.
   8. The cross-epoch conclusion the client can check is comparability,
      and the stronger conclusion needs a deployment hypothesis. A client
      checks two certificates; that gives every accepted old checkpoint a
      prefix of the anchor and every accepted new checkpoint comparable
      with it. `new_epoch_extends_the_anchor` is the sharper reading and
      takes `AnchoredChain`, the hypothesis that the destination population
      starts at the anchor, which is a deployment fact rather than a
      certificate's content.

   The certificate decision follows Q22b's qualified model: policies are
   well formed, every signature binds the complete policy and statement,
   and repeated or non-qualifying signatures refuse the whole certificate.
   `counted_certificateb` isolates the weaker cardinality predicate used
   by the intersection calculation; it is never a client admission rule.
   `certified_implies_counted` connects them. Authentication hypotheses
   range over the supplied certificates, not every constructible value
   with its symbolic authentication flag set. The complete safety premises
   have constructed deployment witnesses below, beyond record inhabitation.

   Residual retained rather than closed. Selective delivery of
   independently valid variants stays exactly where R-13-023a puts it: one
   accepted checkpoint can carry two admissible package identities, a
   recipient can be given either, and no predicate in this file selects
   between them. `one_checkpoint_carries_two_valid_variants` exhibits the
   pair; nothing below is a monitor, a release-selection policy, or a
   source-availability claim, and no theorem here narrows that residual.

   Non-vacuity (R-05-165, R-05-166). Every record this file's theorems
   quantify over carries a closed inhabitant named for it. Every policy
   and history claim is stated over an arbitrary deployment, proved of the
   specification, and refuted of an alternative construction: a policy the
   intersection condition rejects, a witness that reads its failing store
   instead of its anchor, a transition carried by shared-prefix signatures
   alone, and a roster whose keys are not distinct. Whether a refuted
   construction is a telling one is a reading, discharged at R-05-150's
   review gate and booked under R-17-016 rather than claimed here.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-150 R-05-163 R-05-164 R-05-165 R-05-166 R-13-023a R-13-023b R-13-023c
      R-17-016 R-17-030v
   SHA256: de5b2396a1d09060dc71dfad72baad6de08e7fc8b3d09e4f7496de411abdac6d
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Import ListNotations.

(* =========================================================================
   Part 1. A finite index domain and its counting lemmas.

   The population is an interval of natural numbers and a set of identities
   is a boolean predicate on it, so every cardinality below is the length
   of a filter and every counting step is an induction with no stdlib
   ordering theory behind it. `upto` rather than `seq` because the whole
   argument then needs no list lemma this file does not prove.
   ========================================================================= *)

Fixpoint upto (n : nat) : list nat :=
  match n with 0 => [] | S m => m :: upto m end.

Lemma in_upto : forall n x, In x (upto n) -> x < n.
Proof.
  induction n as [| m IH]; intros x H; simpl in H; [contradiction |].
  destruct H as [H | H]; [lia |]. apply IH in H. lia.
Qed.

(* How many identities below n a predicate holds of. *)
Definition card (n : nat) (q : nat -> bool) : nat := length (filter q (upto n)).

Lemma card_le : forall n q, card n q <= n.
Proof.
  intros n q. unfold card. induction n as [| m IH]; simpl; [lia |].
  destruct (q m); simpl; lia.
Qed.

Lemma card_all : forall n r, (forall i, i < n -> r i = true) -> card n r = n.
Proof.
  unfold card. intros n r. induction n as [| m IH]; intro H; simpl; [reflexivity |].
  assert (Hm : r m = true) by (apply H; lia).
  rewrite Hm. simpl. rewrite IH; [reflexivity |]. intros i Hi. apply H. lia.
Qed.

Lemma card_none : forall n r, (forall i, i < n -> r i = false) -> card n r = 0.
Proof.
  unfold card. intros n r. induction n as [| m IH]; intro H; simpl; [reflexivity |].
  assert (Hm : r m = false) by (apply H; lia).
  rewrite Hm. rewrite IH; [reflexivity |]. intros i Hi. apply H. lia.
Qed.

Lemma card_complement : forall n p q,
  (forall i, i < n -> q i = negb (p i)) -> card n p + card n q = n.
Proof.
  unfold card. intros n p q. induction n as [| m IH]; intro H; simpl; [reflexivity |].
  assert (Hq : q m = negb (p m)) by (apply H; lia).
  assert (Hm : forall i, i < m -> q i = negb (p i)) by (intros i Hi; apply H; lia).
  specialize (IH Hm). rewrite Hq. destruct (p m); simpl; lia.
Qed.

Lemma card_ge : forall n a, card n (fun i => a <=? i) = n - a.
Proof.
  intros n a. unfold card. induction n as [| m IH].
  - cbn [upto filter length]. lia.
  - cbn [upto filter]. destruct (Nat.leb_spec a m) as [H | H];
      cbn [length]; rewrite IH; lia.
Qed.

Lemma ltb_negb : forall i b, negb (i <? b) = (b <=? i).
Proof. intros i b. symmetry. apply Nat.leb_antisym. Qed.

Lemma card_lt : forall n b, b <= n -> card n (fun i => i <? b) = b.
Proof.
  intros n b Hb.
  assert (H : card n (fun i => i <? b) + card n (fun i => b <=? i) = n).
  { apply card_complement. intros i _. symmetry. apply ltb_negb. }
  rewrite card_ge in H. lia.
Qed.

(* Inclusion and exclusion over two predicates, which is the whole of the
   quorum-intersection count. *)
Lemma card_meet_join : forall n p q,
  card n (fun i => p i && q i) + card n (fun i => p i || q i) = card n p + card n q.
Proof.
  intros n p q. unfold card. generalize (upto n); intro l.
  induction l as [| a l IH]; simpl; [reflexivity |].
  destruct (p a); destruct (q a); simpl; lia.
Qed.

(* Removing a fault set costs at most its own size. *)
Lemma card_minus_bad : forall n r bad,
  card n r <= card n (fun i => r i && negb (bad i)) + card n bad.
Proof.
  intros n r bad. unfold card. generalize (upto n); intro l.
  induction l as [| a l IH]; simpl; [lia |].
  destruct (r a); destruct (bad a); simpl; lia.
Qed.

Lemma card_pos_member : forall n q, 0 < card n q -> exists i, i < n /\ q i = true.
Proof.
  intros n q H. unfold card in H.
  destruct (filter q (upto n)) as [| x rest] eqn:E; simpl in H; [lia |].
  assert (Hin : In x (filter q (upto n))) by (rewrite E; left; reflexivity).
  apply filter_In in Hin as [Hl Hq].
  exists x. split; [apply in_upto; exact Hl | exact Hq].
Qed.

(* =========================================================================
   Part 2. Checkpoints, and what consistency means over them.

   A checkpoint is the complete list of logged names a log history holds,
   which is Q22b's own representation: prefix stands for a verified
   consistency proof and membership for a verified inclusion proof. Nothing
   here computes a Merkle path; M6.2c owns the reader that does.
   ========================================================================= *)

Definition Checkpoint : Type := list nat.

Fixpoint prefixb (a b : Checkpoint) : bool :=
  match a, b with
  | [], _ => true
  | _ :: _, [] => false
  | x :: xs, y :: ys => (x =? y) && prefixb xs ys
  end.

Definition extendsb (new old : Checkpoint) : bool := prefixb old new.
Definition comparableb (a b : Checkpoint) : bool := prefixb a b || prefixb b a.

Fixpoint memb (x : nat) (l : list nat) : bool :=
  match l with [] => false | y :: ys => (x =? y) || memb x ys end.

(* R-13-023b's inclusion obligation at this model's level of detail. *)
Definition includedb (c : Checkpoint) (name : nat) : bool := memb name c.

Lemma prefixb_refl : forall a, prefixb a a = true.
Proof.
  induction a as [| x xs IH]; simpl; [reflexivity |].
  rewrite Nat.eqb_refl, IH. reflexivity.
Qed.

Lemma prefixb_trans : forall b a c,
  prefixb a b = true -> prefixb b c = true -> prefixb a c = true.
Proof.
  induction b as [| y ys IH]; intros [| x xs] [| z zs] Hab Hbc; simpl in *;
    try reflexivity; try discriminate.
  apply andb_true_iff in Hab as [Hx Hab]. apply andb_true_iff in Hbc as [Hy Hbc].
  apply Nat.eqb_eq in Hx. apply Nat.eqb_eq in Hy. subst.
  rewrite Nat.eqb_refl. simpl. exact (IH xs zs Hab Hbc).
Qed.

Lemma two_prefixes_comparable : forall c a b,
  prefixb a c = true -> prefixb b c = true -> comparableb a b = true.
Proof.
  unfold comparableb.
  induction c as [| z zs IH]; intros [| x xs] [| y ys] Ha Hb; simpl in *;
    try reflexivity; try discriminate.
  apply andb_true_iff in Ha as [Hx Ha]. apply andb_true_iff in Hb as [Hy Hb].
  apply Nat.eqb_eq in Hx. apply Nat.eqb_eq in Hy. subst.
  rewrite Nat.eqb_refl. simpl. exact (IH xs ys Ha Hb).
Qed.

Lemma comparableb_cases : forall a b,
  comparableb a b = true -> prefixb a b = true \/ prefixb b a = true.
Proof. intros a b H. apply orb_true_iff in H. exact H. Qed.

(* =========================================================================
   Part 3. The policy: what a deployment fixes, as fields.
   ========================================================================= *)

Record Policy : Type := {
  pol_scope : nat;          (* the trust scope the population is named under *)
  pol_epoch : nat;
  pol_keys : list nat;      (* one enrolled verification key per identity;
                               the identity is its position (reading 1)      *)
  pol_threshold : nat;      (* K                                             *)
  pol_faults : nat          (* f, the Byzantine bound for this epoch         *)
}.

Definition population (p : Policy) : nat := length (pol_keys p).
Definition enrolled_key (p : Policy) (i : nat) : nat := nth i (pol_keys p) 0.

Fixpoint distinctb (l : list nat) : bool :=
  match l with [] => true | x :: xs => negb (memb x xs) && distinctb xs end.

Definition wellformedb (p : Policy) : bool :=
  (1 <=? pol_threshold p) && (pol_threshold p <=? population p)
  && (pol_faults p <? population p) && distinctb (pol_keys p).

(* R-13-023c's honest-intersection condition, stated without natural
   subtraction (reading 3). *)
Definition safeb (p : Policy) : bool :=
  population p + pol_faults p <? 2 * pol_threshold p.

(* The register's own spelling, `2K - N > f`, kept beside it so the two can
   be held together rather than trusted to agree. *)
Definition register_safeb (p : Policy) : bool :=
  pol_faults p <? 2 * pol_threshold p - population p.

(*| discharges: R-13-023c |*)
Theorem safe_matches_the_register_spelling :
  forall p : Policy, safeb p = register_safeb p.
Proof.
  intros p. unfold safeb, register_safeb.
  apply eq_iff_eq_true. rewrite !Nat.ltb_lt. lia.
Qed.

Lemma In_memb_true : forall x l, In x l -> memb x l = true.
Proof.
  intros x l. induction l as [| y ys IH]; simpl; [contradiction |].
  intros [H | H].
  - apply orb_true_iff. left. apply Nat.eqb_eq. symmetry. exact H.
  - apply orb_true_iff. right. apply IH. exact H.
Qed.

Lemma distinct_nth_injective : forall l i j,
  distinctb l = true -> i < length l -> j < length l ->
  nth i l 0 = nth j l 0 -> i = j.
Proof.
  induction l as [| x xs IH]; intros i j Hd Hi Hj He; simpl in *; [lia |].
  apply andb_true_iff in Hd as [Hx Hd].
  destruct (memb x xs) eqn:Hm; simpl in Hx; [discriminate Hx |].
  destruct i as [| i']; destruct j as [| j'].
  - reflexivity.
  - assert (Hin : In x xs) by (rewrite He; apply nth_In; lia).
    apply In_memb_true in Hin. congruence.
  - assert (Hin : In x xs) by (rewrite <- He; apply nth_In; lia).
    apply In_memb_true in Hin. congruence.
  - f_equal. apply IH; [exact Hd | lia | lia | exact He].
Qed.

(*| discharges: R-13-023c |*)
Theorem enrolled_keys_identify_witnesses : forall (p : Policy) (i j : nat),
  wellformedb p = true -> i < population p -> j < population p ->
  enrolled_key p i = enrolled_key p j -> i = j.
Proof.
  intros p i j Hw Hi Hj He. unfold wellformedb in Hw.
  apply andb_true_iff in Hw as [_ Hd].
  unfold enrolled_key, population in *.
  apply (distinct_nth_injective (pol_keys p) i j Hd Hi Hj He).
Qed.

(* =========================================================================
   Part 4. Statements, transitions, and co-signatures.

   A statement is what a witness signs and what a certificate binds: the
   trust scope and epoch that name the policy, the checkpoint, and the
   optional terminal transition that closes the epoch. Decidable equality
   is derived rather than hand-written, so the exact-binding checks below
   compare whole statements and not a chosen subset of their fields.
   ========================================================================= *)

Record Transition : Type := {
  tr_old : Policy;
  tr_new : Policy;
  tr_anchor : Checkpoint
}.

Record Statement : Type := {
  st_scope : nat;
  st_epoch : nat;
  st_checkpoint : Checkpoint;
  st_terminal : option Transition
}.

Definition checkpoint_eq_dec : forall a b : Checkpoint, {a = b} + {a <> b} :=
  list_eq_dec Nat.eq_dec.

Definition policy_eq_dec (x y : Policy) : {x = y} + {x <> y}.
Proof. decide equality; auto using Nat.eq_dec, checkpoint_eq_dec. Defined.

Definition transition_eq_dec (x y : Transition) : {x = y} + {x <> y}.
Proof. decide equality; auto using checkpoint_eq_dec, policy_eq_dec. Defined.

Definition statement_eq_dec (x y : Statement) : {x = y} + {x <> y}.
Proof.
  decide equality; auto using Nat.eq_dec, checkpoint_eq_dec.
  decide equality. apply transition_eq_dec.
Defined.

Definition policy_eqb (x y : Policy) : bool :=
  if policy_eq_dec x y then true else false.
Definition statement_eqb (x y : Statement) : bool :=
  if statement_eq_dec x y then true else false.
Definition checkpoint_eqb (x y : Checkpoint) : bool :=
  if checkpoint_eq_dec x y then true else false.

Lemma statement_eqb_eq : forall x y, statement_eqb x y = true <-> x = y.
Proof.
  intros x y. unfold statement_eqb. destruct (statement_eq_dec x y);
    split; intro H; try discriminate; auto.
Qed.

(* The two statement shapes a policy epoch carries: an ordinary checkpoint
   statement, and the terminal statement that closes the epoch. *)
Definition plain (p : Policy) (c : Checkpoint) : Statement :=
  {| st_scope := pol_scope p; st_epoch := pol_epoch p; st_checkpoint := c;
     st_terminal := None |}.

Definition sealed_statement (p : Policy) (tr : Transition) : Statement :=
  {| st_scope := pol_scope p; st_epoch := pol_epoch p;
     st_checkpoint := tr_anchor tr; st_terminal := Some tr |}.

Definition bindsb (p : Policy) (s : Statement) : bool :=
  (st_scope s =? pol_scope p) && (st_epoch s =? pol_epoch p).

(* A continuous transition binds both whole policies, one trust scope and
   consecutive epochs. *)
Definition continuousb (tr : Transition) : bool :=
  safeb (tr_old tr) && safeb (tr_new tr)
  && (pol_scope (tr_new tr) =? pol_scope (tr_old tr))
  && (pol_epoch (tr_new tr) =? S (pol_epoch (tr_old tr))).

Definition terminal_bindsb (p : Policy) (tr : Transition) (c : Checkpoint) : bool :=
  policy_eqb (tr_old tr) p && continuousb tr && checkpoint_eqb (tr_anchor tr) c.

Record Signature : Type := {
  sig_policy : Policy;
  sig_signer : nat;         (* the identity's position in the roster *)
  sig_key : nat;            (* the key the signature was verified under *)
  sig_statement : Statement;
  sig_authentic : bool      (* an ideal verifier's verdict, never a check *)
}.

(* Every condition R-13-023b's criterion puts on a contributing signature:
   it verifies, it names this exact policy, its signer is enrolled, the key
   it verified under is that identity's enrolled key, and it binds this
   exact statement. *)
Definition sig_okb (p : Policy) (s : Statement) (g : Signature) : bool :=
  sig_authentic g
  && policy_eqb (sig_policy g) p
  && (sig_signer g <? population p)
  && (sig_key g =? enrolled_key p (sig_signer g))
  && statement_eqb (sig_statement g) s.

(* The quorum a certificate exhibits: the identities that contributed a
   qualifying signature. A repeated signature contributes its position
   once, and a foreign or wrong-key signature contributes nothing
   (reading 2). *)
Definition accepted (p : Policy) (s : Statement) (gs : list Signature) : nat -> bool :=
  fun i => existsb (fun g => sig_okb p s g && (sig_signer g =? i)) gs.

Definition counted_certificateb (p : Policy) (s : Statement)
  (gs : list Signature) : bool :=
  safeb p && (pol_threshold p <=? card (population p) (accepted p s gs)).

(* Q22b rejects duplicate signers and every non-qualifying signature.
   Its Python constructor checks policy validity before certificates can
   be formed; the total Gallina decision checks that same boundary here. *)
Definition certifiedb (p : Policy) (s : Statement)
  (gs : list Signature) : bool :=
  wellformedb p && bindsb p s
  && distinctb (map sig_signer gs) && forallb (sig_okb p s) gs
  && counted_certificateb p s gs.

(*| discharges: R-13-023b |*)
Theorem certified_implies_counted : forall p s gs,
  certifiedb p s gs = true -> counted_certificateb p s gs = true.
Proof.
  intros p s gs H. unfold certifiedb in H.
  apply andb_true_iff in H as [_ H]. exact H.
Qed.

Lemma accepted_has_a_signature : forall p s gs i,
  accepted p s gs i = true ->
  exists g, In g gs /\ sig_okb p s g = true /\ sig_signer g = i.
Proof.
  intros p s gs i H. unfold accepted in H.
  apply existsb_exists in H as [g [Hin Hg]].
  apply andb_true_iff in Hg as [Hok Heq]. apply Nat.eqb_eq in Heq.
  exists g. split; [exact Hin | split; [exact Hok | exact Heq]].
Qed.

(* =========================================================================
   Part 5. Honest intersection, over an arbitrary population.

   This is R-13-023c's own sentence as a theorem: within one epoch, every
   pair of acceptable quorums shares a witness the fault set does not
   contain. The population, the threshold and the fault bound are the
   policy's fields, so the statement quantifies over every flat policy
   rather than over an enumerated grid.
   ========================================================================= *)

(*| discharges: R-13-023c |*)
Theorem honest_intersection :
  forall (p : Policy) (bad : nat -> bool) (s1 s2 : Statement)
         (gs1 gs2 : list Signature),
    card (population p) bad <= pol_faults p ->
    certifiedb p s1 gs1 = true ->
    certifiedb p s2 gs2 = true ->
    exists i, i < population p
              /\ accepted p s1 gs1 i = true
              /\ accepted p s2 gs2 i = true
              /\ bad i = false.
Proof.
  intros p bad s1 s2 gs1 gs2 Hbad H1 H2.
  apply certified_implies_counted in H1, H2.
  apply andb_true_iff in H1 as [Hsafe H1]. apply andb_true_iff in H2 as [_ H2].
  apply Nat.leb_le in H1. apply Nat.leb_le in H2.
  unfold safeb in Hsafe. apply Nat.ltb_lt in Hsafe.
  pose proof (card_le (population p)
    (fun i => accepted p s1 gs1 i || accepted p s2 gs2 i)) as Hjoin.
  pose proof (card_meet_join (population p)
    (accepted p s1 gs1) (accepted p s2 gs2)) as Hmj.
  pose proof (card_minus_bad (population p)
    (fun i => accepted p s1 gs1 i && accepted p s2 gs2 i) bad) as Hmb.
  cbv beta in Hmb.
  assert (Hpos : 0 < card (population p)
    (fun i => accepted p s1 gs1 i && accepted p s2 gs2 i && negb (bad i))) by lia.
  apply card_pos_member in Hpos as [i [Hi Hh]].
  apply andb_true_iff in Hh as [Hm Hb].
  apply andb_true_iff in Hm as [Ha Hbb].
  exists i. split; [exact Hi | split; [exact Ha | split; [exact Hbb |]]].
  destruct (bad i); [discriminate Hb | reflexivity].
Qed.

(* =========================================================================
   Part 6. The durable witness, its anchor, and what a crash can do.

   R-13-023c's second acceptance clause is a state machine, so it is stated
   as one: the volatile proposal, the failing store, and the authenticated
   antirollback anchor the specification consults. `anchored` carries both
   readings of what "current state" means (reading 6): the specification is
   `anchored = true`, which consults the anchor, and `anchored = false` is
   the construction that trusts the store alone and is refuted below.
   ========================================================================= *)

Record Durable : Type := {
  dur_checkpoint : Checkpoint;
  dur_serial : nat;
  dur_terminal : option Transition
}.

Record WState : Type := {
  ws_trusted : Durable;          (* the authenticated antirollback anchor *)
  ws_stored : option Durable;    (* the failing store, losable and rollable *)
  ws_pending : option Durable    (* the volatile proposal *)
}.

Record Evidence : Type := {
  ev_policy : Policy;
  ev_signer : nat;
  ev_record : Durable;
  ev_authentic : bool
}.

Definition durable_eq_dec (x y : Durable) : {x = y} + {x <> y}.
Proof.
  decide equality; auto using Nat.eq_dec, checkpoint_eq_dec.
  decide equality. apply transition_eq_dec.
Defined.

Definition durable_eqb (x y : Durable) : bool :=
  if durable_eq_dec x y then true else false.

(* What an identity would sign if it released now. *)
Definition statement_of (p : Policy) (d : Durable) : Statement :=
  {| st_scope := pol_scope p; st_epoch := pol_epoch p;
     st_checkpoint := dur_checkpoint d; st_terminal := dur_terminal d |}.

Definition set_pending (w : WState) (o : option Durable) : WState :=
  {| ws_trusted := ws_trusted w; ws_stored := ws_stored w; ws_pending := o |}.

(* The specification consults the anchor and quarantines a store that does
   not match it; the tolerant reading takes the store as given. *)
Definition current (anchored : bool) (w : WState) : option Durable :=
  match ws_stored w with
  | None => None
  | Some r =>
      if anchored
      then (if durable_eqb r (ws_trusted w) then Some (ws_trusted w) else None)
      else Some r
  end.

Lemma current_true_is_trusted : forall w cur,
  current true w = Some cur -> cur = ws_trusted w.
Proof.
  intros w cur H. unfold current in H.
  destruct (ws_stored w) as [r |]; [| discriminate].
  destruct (durable_eqb r (ws_trusted w)); [| discriminate]. congruence.
Qed.

Definition successor (cur : Durable) (s : Statement) : Durable :=
  {| dur_checkpoint := st_checkpoint s; dur_serial := S (dur_serial cur);
     dur_terminal := st_terminal s |}.

(* Preparation checks consistency and binding; it persists nothing. *)
Definition prepare (anchored : bool) (p : Policy) (w : WState) (s : Statement)
  : option WState :=
  match current anchored w with
  | None => None
  | Some cur =>
      if bindsb p s then
        (if statement_eqb s (statement_of p cur)
         then Some (set_pending w (Some cur))
         else match dur_terminal cur with
              | Some _ => None
              | None =>
                  if prefixb (dur_checkpoint cur) (st_checkpoint s) then
                    (match st_terminal s with
                     | None => Some (set_pending w (Some (successor cur s)))
                     | Some tr =>
                         if terminal_bindsb p tr (st_checkpoint s)
                         then Some (set_pending w (Some (successor cur s)))
                         else None
                     end)
                  else None
              end)
      else None
  end.

(* Commit persists the whole successor and advances the anchor atomically. *)
Definition commit (anchored : bool) (w : WState) : option WState :=
  match current anchored w, ws_pending w with
  | Some _, Some pend =>
      Some {| ws_trusted := pend; ws_stored := Some pend;
              ws_pending := ws_pending w |}
  | _, _ => None
  end.

(* Release is enabled only where the prepared record is the durable one. *)
Definition release (anchored : bool) (p : Policy) (w : WState)
  : option (WState * Statement) :=
  match current anchored w, ws_pending w with
  | Some cur, Some pend =>
      if durable_eqb cur pend
      then Some (set_pending w None, statement_of p cur)
      else None
  | _, _ => None
  end.

Inductive Action : Type :=
| Prepare (s : Statement)
| Commit
| Release
| Crash
| Damage (o : option Durable)      (* storage loss and rollback, adversarial *)
| Recover (e : Evidence).

Definition step (anchored : bool) (p : Policy) (i : nat) (w : WState) (a : Action)
  : option (WState * option Statement) :=
  match a with
  | Prepare s =>
      match prepare anchored p w s with
      | Some w2 => Some (w2, None)
      | None => None
      end
  | Commit =>
      match commit anchored w with
      | Some w2 => Some (w2, None)
      | None => None
      end
  | Release =>
      match release anchored p w with
      | Some (w2, s) => Some (w2, Some s)
      | None => None
      end
  | Crash => Some (set_pending w None, None)
  | Damage o =>
      Some ({| ws_trusted := ws_trusted w; ws_stored := o;
               ws_pending := ws_pending w |}, None)
  | Recover e =>
      if ev_authentic e && policy_eqb (ev_policy e) p && (ev_signer e =? i)
         && durable_eqb (ev_record e) (ws_trusted w)
      then Some ({| ws_trusted := ws_trusted w; ws_stored := Some (ev_record e);
                    ws_pending := None |}, None)
      else None
  end.

(* A refused action is a no-op, which is Q22b's own schedule discipline:
   each rejected operation leaves the remaining actions decidable. *)
Fixpoint run_state (anchored : bool) (p : Policy) (i : nat) (w : WState)
  (acts : list Action) : WState :=
  match acts with
  | [] => w
  | a :: rest =>
      match step anchored p i w a with
      | None => run_state anchored p i w rest
      | Some (w2, _) => run_state anchored p i w2 rest
      end
  end.

Fixpoint run_out (anchored : bool) (p : Policy) (i : nat) (w : WState)
  (acts : list Action) : list Statement :=
  match acts with
  | [] => []
  | a :: rest =>
      match step anchored p i w a with
      | None => run_out anchored p i w rest
      | Some (w2, None) => run_out anchored p i w2 rest
      | Some (w2, Some s) => s :: run_out anchored p i w2 rest
      end
  end.

(* =========================================================================
   Part 7. The inductive invariant, and the chain it gives.
   ========================================================================= *)

Definition Inv (w : WState) : Prop :=
  match ws_pending w with
  | None => True
  | Some pend =>
      prefixb (dur_checkpoint (ws_trusted w)) (dur_checkpoint pend) = true
      /\ (dur_terminal (ws_trusted w) <> None -> pend = ws_trusted w)
  end.

Lemma prepare_keeps_trusted : forall anchored p w s w2,
  prepare anchored p w s = Some w2 -> ws_trusted w2 = ws_trusted w.
Proof.
  intros anchored p w s w2 H. unfold prepare in H.
  destruct (current anchored w) as [cur |]; [| discriminate].
  destruct (bindsb p s); [| discriminate].
  destruct (statement_eqb s (statement_of p cur));
    [injection H as H; subst w2; reflexivity |].
  destruct (dur_terminal cur); [discriminate |].
  destruct (prefixb (dur_checkpoint cur) (st_checkpoint s)); [| discriminate].
  destruct (st_terminal s) as [tr |];
    [| injection H as H; subst w2; reflexivity].
  destruct (terminal_bindsb p tr (st_checkpoint s));
    [injection H as H; subst w2; reflexivity | discriminate].
Qed.

Lemma prepare_preserves_inv : forall p w s w2,
  Inv w -> prepare true p w s = Some w2 -> Inv w2.
Proof.
  intros p w s w2 Hinv H. unfold prepare in H.
  destruct (current true w) as [cur |] eqn:Ec; [| discriminate].
  apply current_true_is_trusted in Ec. subst cur.
  destruct (bindsb p s); [| discriminate].
  destruct (statement_eqb s (statement_of p (ws_trusted w))) eqn:Es.
  - injection H as H. subst w2. unfold Inv. simpl.
    split; [apply prefixb_refl | intros _; reflexivity].
  - destruct (dur_terminal (ws_trusted w)) eqn:Et; [discriminate |].
    destruct (prefixb (dur_checkpoint (ws_trusted w)) (st_checkpoint s)) eqn:Ep;
      [| discriminate].
    destruct (st_terminal s) as [tr |];
      [destruct (terminal_bindsb p tr (st_checkpoint s)); [| discriminate] |];
      injection H as H; subst w2; unfold Inv; simpl;
      (split; [exact Ep | intros Hc; congruence]).
Qed.

Lemma commit_result : forall anchored w w2,
  commit anchored w = Some w2 ->
  exists pend, ws_pending w = Some pend /\ ws_trusted w2 = pend
               /\ ws_pending w2 = Some pend.
Proof.
  intros anchored w w2 H. unfold commit in H.
  destruct (current anchored w) as [cur |]; [| discriminate].
  destruct (ws_pending w) as [pend |] eqn:Ep; [| discriminate].
  injection H as H. subst w2. exists pend. repeat split; reflexivity.
Qed.

Lemma step_preserves_inv : forall p i w a w2 o,
  Inv w -> step true p i w a = Some (w2, o) -> Inv w2.
Proof.
  intros p i w a w2 o Hinv H. destruct a; simpl in H.
  - destruct (prepare true p w s) as [wp |] eqn:Ep; [| discriminate].
    injection H as H1 H2. subst wp.
    exact (prepare_preserves_inv p w s w2 Hinv Ep).
  - destruct (commit true w) as [wc |] eqn:Ec; [| discriminate].
    injection H as H1 H2. subst wc.
    apply commit_result in Ec as [pend [_ [Ht Hp]]].
    unfold Inv. rewrite Hp, Ht. split; [apply prefixb_refl | intros _; reflexivity].
  - destruct (release true p w) as [[wr s] |] eqn:Er; [| discriminate].
    injection H as H1 H2. subst wr. unfold release in Er.
    destruct (current true w) as [cur |], (ws_pending w) as [pend |];
      try discriminate.
    destruct (durable_eqb cur pend); [| discriminate].
    injection Er as Er1 Er2. subst w2. exact I.
  - injection H as H1 H2. subst w2. exact I.
  - injection H as H1 H2. subst w2. exact Hinv.
  - destruct (ev_authentic e && policy_eqb (ev_policy e) p && (ev_signer e =? i)
              && durable_eqb (ev_record e) (ws_trusted w)); [| discriminate].
    injection H as H1 H2. subst w2. exact I.
Qed.

Lemma step_trusted_extends : forall p i w a w2 o,
  Inv w -> step true p i w a = Some (w2, o) ->
  prefixb (dur_checkpoint (ws_trusted w)) (dur_checkpoint (ws_trusted w2)) = true.
Proof.
  intros p i w a w2 o Hinv H. destruct a; simpl in H.
  - destruct (prepare true p w s) as [wp |] eqn:Ep; [| discriminate].
    injection H as H1 H2. subst wp.
    apply prepare_keeps_trusted in Ep. rewrite Ep. apply prefixb_refl.
  - destruct (commit true w) as [wc |] eqn:Ec; [| discriminate].
    injection H as H1 H2. subst wc.
    apply commit_result in Ec as [pend [Hw [Ht _]]].
    unfold Inv in Hinv. rewrite Hw in Hinv. destruct Hinv as [Hpre _].
    rewrite Ht. exact Hpre.
  - destruct (release true p w) as [[wr s] |] eqn:Er; [| discriminate].
    injection H as H1 H2. subst wr. unfold release in Er.
    destruct (current true w) as [cur |], (ws_pending w) as [pend |];
      try discriminate.
    destruct (durable_eqb cur pend); [| discriminate].
    injection Er as Er1 Er2. subst w2. simpl. apply prefixb_refl.
  - injection H as H1 H2. subst w2. simpl. apply prefixb_refl.
  - injection H as H1 H2. subst w2. simpl. apply prefixb_refl.
  - destruct (ev_authentic e && policy_eqb (ev_policy e) p && (ev_signer e =? i)
              && durable_eqb (ev_record e) (ws_trusted w)); [| discriminate].
    injection H as H1 H2. subst w2. simpl. apply prefixb_refl.
Qed.

Lemma step_emits : forall p i w a w2 s,
  step true p i w a = Some (w2, Some s) ->
  s = statement_of p (ws_trusted w) /\ ws_trusted w2 = ws_trusted w.
Proof.
  intros p i w a w2 s H. destruct a; simpl in H.
  - destruct (prepare true p w s0); discriminate.
  - destruct (commit true w); discriminate.
  - destruct (release true p w) as [[wr s1] |] eqn:Er; [| discriminate].
    injection H as H1 H2. subst wr s1. unfold release in Er.
    destruct (current true w) as [cur |] eqn:Ec; [| discriminate].
    apply current_true_is_trusted in Ec. subst cur.
    destruct (ws_pending w) as [pend |]; [| discriminate].
    destruct (durable_eqb (ws_trusted w) pend); [| discriminate].
    injection Er as Er1 Er2. subst w2. split; [congruence | reflexivity].
  - discriminate.
  - discriminate.
  - destruct (ev_authentic e && policy_eqb (ev_policy e) p && (ev_signer e =? i)
              && durable_eqb (ev_record e) (ws_trusted w)); discriminate.
Qed.

Lemma step_sealed_keeps_trusted : forall p i w a w2 o,
  Inv w -> dur_terminal (ws_trusted w) <> None ->
  step true p i w a = Some (w2, o) -> ws_trusted w2 = ws_trusted w.
Proof.
  intros p i w a w2 o Hinv Hseal H. destruct a; simpl in H.
  - destruct (prepare true p w s) as [wp |] eqn:Ep; [| discriminate].
    injection H as H1 H2. subst wp. apply prepare_keeps_trusted in Ep. exact Ep.
  - destruct (commit true w) as [wc |] eqn:Ec; [| discriminate].
    injection H as H1 H2. subst wc.
    apply commit_result in Ec as [pend [Hw [Ht _]]].
    unfold Inv in Hinv. rewrite Hw in Hinv. destruct Hinv as [_ Hsame].
    rewrite Ht. exact (Hsame Hseal).
  - destruct (release true p w) as [[wr s] |] eqn:Er; [| discriminate].
    injection H as H1 H2. subst wr. unfold release in Er.
    destruct (current true w) as [cur |], (ws_pending w) as [pend |];
      try discriminate.
    destruct (durable_eqb cur pend); [| discriminate].
    injection Er as Er1 Er2. subst w2. reflexivity.
  - injection H as H1 H2. subst w2. reflexivity.
  - injection H as H1 H2. subst w2. reflexivity.
  - destruct (ev_authentic e && policy_eqb (ev_policy e) p && (ev_signer e =? i)
              && durable_eqb (ev_record e) (ws_trusted w)); [| discriminate].
    injection H as H1 H2. subst w2. reflexivity.
Qed.

(* =========================================================================
   Part 8. What a whole run of the machine can and cannot release.

   The load-bearing property: an identity that follows this machine, under
   any schedule at all, including crashes and arbitrary storage damage,
   never releases two incomparable checkpoints, and once it has released a
   terminal statement every statement it ever released is a prefix of that
   statement's anchor.
   ========================================================================= *)

Lemma run_trusted_extends : forall acts p i w,
  Inv w ->
  prefixb (dur_checkpoint (ws_trusted w))
          (dur_checkpoint (ws_trusted (run_state true p i w acts))) = true.
Proof.
  induction acts as [| a rest IH]; intros p i w Hinv; simpl; [apply prefixb_refl |].
  destruct (step true p i w a) as [[w2 o] |] eqn:E.
  - apply (prefixb_trans (dur_checkpoint (ws_trusted w2))).
    + exact (step_trusted_extends p i w a w2 o Hinv E).
    + apply IH. exact (step_preserves_inv p i w a w2 o Hinv E).
  - apply IH. exact Hinv.
Qed.

Lemma run_out_prefix_final : forall acts p i w s,
  Inv w -> In s (run_out true p i w acts) ->
  prefixb (st_checkpoint s)
          (dur_checkpoint (ws_trusted (run_state true p i w acts))) = true.
Proof.
  induction acts as [| a rest IH]; intros p i w s Hinv Hin; simpl in *;
    [contradiction |].
  destruct (step true p i w a) as [[w2 [s0 |]] |] eqn:E.
  - destruct (step_emits p i w a w2 s0 E) as [He Ht].
    destruct Hin as [Hs | Hin].
    + subst s0. rewrite He. simpl. rewrite <- Ht.
      apply run_trusted_extends. exact (step_preserves_inv p i w a w2 (Some s) Hinv E).
    + apply IH; [exact (step_preserves_inv p i w a w2 (Some s0) Hinv E) | exact Hin].
  - apply IH; [exact (step_preserves_inv p i w a w2 None Hinv E) | exact Hin].
  - apply IH; [exact Hinv | exact Hin].
Qed.

Lemma run_out_extends_initial : forall acts p i w s,
  Inv w -> In s (run_out true p i w acts) ->
  prefixb (dur_checkpoint (ws_trusted w)) (st_checkpoint s) = true.
Proof.
  induction acts as [| a rest IH]; intros p i w s Hinv Hin; simpl in *;
    [contradiction |].
  destruct (step true p i w a) as [[w2 [s0 |]] |] eqn:E.
  - destruct (step_emits p i w a w2 s0 E) as [He Ht].
    destruct Hin as [Hs | Hin].
    + subst s0. rewrite He. simpl. apply prefixb_refl.
    + apply (prefixb_trans (dur_checkpoint (ws_trusted w2))).
      * exact (step_trusted_extends p i w a w2 (Some s0) Hinv E).
      * exact (IH p i w2 s (step_preserves_inv p i w a w2 (Some s0) Hinv E) Hin).
  - apply (prefixb_trans (dur_checkpoint (ws_trusted w2))).
    + exact (step_trusted_extends p i w a w2 None Hinv E).
    + exact (IH p i w2 s (step_preserves_inv p i w a w2 None Hinv E) Hin).
  - exact (IH p i w s Hinv Hin).
Qed.

(* T1 (R-13-023c). One honest identity's authenticated history is a chain,
   whatever schedule of proposals, commits, crashes, storage damage and
   recoveries it runs. *)
(*| discharges: R-13-023c |*)
Theorem honest_run_never_forks : forall p i w acts s t,
  Inv w -> In s (run_out true p i w acts) -> In t (run_out true p i w acts) ->
  comparableb (st_checkpoint s) (st_checkpoint t) = true.
Proof.
  intros p i w acts s t Hinv Hs Ht.
  apply (two_prefixes_comparable
    (dur_checkpoint (ws_trusted (run_state true p i w acts))));
    apply run_out_prefix_final; assumption.
Qed.

Lemma run_sealed_keeps_its_trusted : forall acts p i w,
  Inv w -> dur_terminal (ws_trusted w) <> None ->
  ws_trusted (run_state true p i w acts) = ws_trusted w.
Proof.
  induction acts as [| a rest IH]; intros p i w Hinv Hseal; simpl; [reflexivity |].
  destruct (step true p i w a) as [[w2 o] |] eqn:E.
  - assert (Hi2 : Inv w2) by exact (step_preserves_inv p i w a w2 o Hinv E).
    assert (Ht : ws_trusted w2 = ws_trusted w)
      by exact (step_sealed_keeps_trusted p i w a w2 o Hinv Hseal E).
    assert (Hs2 : dur_terminal (ws_trusted w2) <> None) by (rewrite Ht; exact Hseal).
    rewrite (IH p i w2 Hi2 Hs2). exact Ht.
  - apply IH; assumption.
Qed.

Lemma run_terminal_release_fixes_statement : forall acts p i w s,
  Inv w -> In s (run_out true p i w acts) -> st_terminal s <> None ->
  statement_of p (ws_trusted (run_state true p i w acts)) = s.
Proof.
  induction acts as [| a rest IH]; intros p i w s Hinv Hin Hterm; simpl in *;
    [contradiction |].
  destruct (step true p i w a) as [[w2 [s0 |]] |] eqn:E.
  - destruct (step_emits p i w a w2 s0 E) as [He Ht].
    destruct Hin as [Hs | Hin].
    + subst s0. assert (Hi2 : Inv w2)
        by exact (step_preserves_inv p i w a w2 (Some s) Hinv E).
      assert (Hs2 : dur_terminal (ws_trusted w2) <> None).
      { rewrite Ht. rewrite He in Hterm. simpl in Hterm. exact Hterm. }
      rewrite (run_sealed_keeps_its_trusted rest p i w2 Hi2 Hs2).
      rewrite Ht, He. reflexivity.
    + apply IH; [exact (step_preserves_inv p i w a w2 (Some s0) Hinv E)
                | exact Hin | exact Hterm].
  - apply IH; [exact (step_preserves_inv p i w a w2 None Hinv E)
              | exact Hin | exact Hterm].
  - apply IH; [exact Hinv | exact Hin | exact Hterm].
Qed.

Lemma run_terminal_release_freezes : forall acts p i w s,
  Inv w -> In s (run_out true p i w acts) -> st_terminal s <> None ->
  dur_checkpoint (ws_trusted (run_state true p i w acts)) = st_checkpoint s.
Proof.
  intros acts p i w s Hi Hs Ht.
  exact (f_equal st_checkpoint
    (run_terminal_release_fixes_statement acts p i w s Hi Hs Ht)).
Qed.

(* Terminal closure fixes the entire destination policy, not only its
   checkpoint; two disjoint successor populations cannot acquire seals
   for different replacements from the same honest identity. *)
(*| discharges: R-13-023c |*)
Theorem terminal_releases_are_identical : forall p i w acts s t,
  Inv w -> In s (run_out true p i w acts) -> st_terminal s <> None ->
  In t (run_out true p i w acts) -> st_terminal t <> None -> s = t.
Proof.
  intros p i w acts s t Hi Hs Hst Ht Htt.
  rewrite <- (run_terminal_release_fixes_statement acts p i w s Hi Hs Hst).
  exact (run_terminal_release_fixes_statement acts p i w t Hi Ht Htt).
Qed.

(* T2 (R-13-023c's transition clause). A sealed identity releases nothing
   past the anchor it sealed, before or after the seal. *)
(*| discharges: R-13-023c |*)
Theorem sealed_releases_are_anchor_prefixes : forall p i w acts seal s,
  Inv w -> In seal (run_out true p i w acts) -> st_terminal seal <> None ->
  In s (run_out true p i w acts) ->
  prefixb (st_checkpoint s) (st_checkpoint seal) = true.
Proof.
  intros p i w acts seal s Hinv Hseal Hterm Hs.
  rewrite <- (run_terminal_release_freezes acts p i w seal Hinv Hseal Hterm).
  apply run_out_prefix_final; assumption.
Qed.

(* =========================================================================
   Part 9. The deployment, and what a certificate lets a client conclude.

   Five hypotheses separate what this file proves from what it assumes.
   `Unforgeable` is the cryptographic assumption, stated and never
   discharged here; the other four are discharged of the machine of
   Part 6 by the theorems beneath them, so a deployment whose honest
   identities run that machine satisfies them rather than being asked to.
   Byzantine identities are quantified over: their releases are an
   arbitrary relation `rogue`, constrained by nothing.
   ========================================================================= *)

Definition Releases : Type := nat -> Statement -> Prop.

(* An authentic signature binding a statement was released by its signer,
   for an identity outside the fault set. This is the whole cryptographic
   premise, and U-20 owns the foundation that would discharge it. *)
Definition Unforgeable (p : Policy) (bad : nat -> bool) (rel : Releases)
  (received : list Signature) : Prop :=
  forall s g, In g received ->
    sig_okb p s g = true -> bad (sig_signer g) = false ->
    rel (sig_signer g) s.

Definition HonestChain (bad : nat -> bool) (rel : Releases) : Prop :=
  forall i s t, bad i = false -> rel i s -> rel i t ->
    comparableb (st_checkpoint s) (st_checkpoint t) = true.

Definition SealedChain (bad : nat -> bool) (rel : Releases) : Prop :=
  forall i seal s, bad i = false -> rel i seal -> st_terminal seal <> None ->
    rel i s -> prefixb (st_checkpoint s) (st_checkpoint seal) = true.

Definition TerminalChain (bad : nat -> bool) (rel : Releases) : Prop :=
  forall i s t, bad i = false -> rel i s -> st_terminal s <> None ->
    rel i t -> st_terminal t <> None -> s = t.

Definition AnchoredChain (bad : nat -> bool) (rel : Releases)
  (a : Checkpoint) : Prop :=
  forall i s, bad i = false -> rel i s -> prefixb a (st_checkpoint s) = true.

(* One deployment: an initial state and a schedule per honest identity, and
   an arbitrary relation for the faulty ones. *)
Definition deployment (p : Policy) (bad : nat -> bool) (start : nat -> WState)
  (sched : nat -> list Action) (rogue : Releases) : Releases :=
  fun i s => if bad i then rogue i s
             else In s (run_out true p i (start i) (sched i)).

(*| discharges: R-13-023c |*)
Theorem deployment_is_an_honest_chain :
  forall p bad start sched rogue,
    (forall i, Inv (start i)) ->
    HonestChain bad (deployment p bad start sched rogue).
Proof.
  intros p bad start sched rogue Hinv i s t Hb Hs Ht.
  unfold deployment in Hs, Ht. rewrite Hb in Hs, Ht.
  exact (honest_run_never_forks p i (start i) (sched i) s t (Hinv i) Hs Ht).
Qed.

(*| discharges: R-13-023c |*)
Theorem deployment_is_a_sealed_chain :
  forall p bad start sched rogue,
    (forall i, Inv (start i)) ->
    SealedChain bad (deployment p bad start sched rogue).
Proof.
  intros p bad start sched rogue Hinv i seal s Hb Hseal Hterm Hs.
  unfold deployment in Hseal, Hs. rewrite Hb in Hseal, Hs.
  exact (sealed_releases_are_anchor_prefixes p i (start i) (sched i) seal s
           (Hinv i) Hseal Hterm Hs).
Qed.

(*| discharges: R-13-023c |*)
Theorem deployment_has_unique_terminal_statements :
  forall p bad start sched rogue,
    (forall i, Inv (start i)) ->
    TerminalChain bad (deployment p bad start sched rogue).
Proof.
  intros p bad start sched rogue Hinv i s t Hb Hs Hst Ht Htt.
  unfold deployment in Hs, Ht. rewrite Hb in Hs, Ht.
  exact (terminal_releases_are_identical p i (start i) (sched i)
    s t (Hinv i) Hs Hst Ht Htt).
Qed.

(*| discharges: R-13-023c |*)
Theorem deployment_started_at_an_anchor_is_anchored :
  forall p bad start sched rogue a,
    (forall i, Inv (start i)) ->
    (forall i, dur_checkpoint (ws_trusted (start i)) = a) ->
    AnchoredChain bad (deployment p bad start sched rogue) a.
Proof.
  intros p bad start sched rogue a Hinv Hstart i s Hb Hs.
  unfold deployment in Hs. rewrite Hb in Hs.
  rewrite <- (Hstart i).
  exact (run_out_extends_initial (sched i) p i (start i) s (Hinv i) Hs).
Qed.

(* T3 (R-13-023c). Within one qualifying epoch, no two accepted
   checkpoints are incompatible. *)
(*| discharges: R-13-023c, R-13-023b |*)
Theorem accepted_checkpoints_are_compatible :
  forall (p : Policy) (bad : nat -> bool) (rel : Releases)
         (s1 s2 : Statement) (gs1 gs2 : list Signature),
    card (population p) bad <= pol_faults p ->
    Unforgeable p bad rel gs1 ->
    Unforgeable p bad rel gs2 ->
    HonestChain bad rel ->
    certifiedb p s1 gs1 = true ->
    certifiedb p s2 gs2 = true ->
    comparableb (st_checkpoint s1) (st_checkpoint s2) = true.
Proof.
  intros p bad rel s1 s2 gs1 gs2 Hbad Hunf1 Hunf2 Hchain H1 H2.
  destruct (honest_intersection p bad s1 s2 gs1 gs2 Hbad H1 H2)
    as [i [_ [Ha1 [Ha2 Hb]]]].
  apply accepted_has_a_signature in Ha1 as [g1 [Hin1 [Hok1 Hsig1]]].
  apply accepted_has_a_signature in Ha2 as [g2 [Hin2 [Hok2 Hsig2]]].
  apply (Hchain i); [exact Hb | | ].
  - rewrite <- Hsig1. apply (Hunf1 s1 g1);
      [exact Hin1 | exact Hok1 | rewrite Hsig1; exact Hb].
  - rewrite <- Hsig2. apply (Hunf2 s2 g2);
      [exact Hin2 | exact Hok2 | rewrite Hsig2; exact Hb].
Qed.

(* T4 (R-13-023c's transition clause). Once a terminal quorum has sealed an
   anchor, no old-epoch certificate reaches past it. This is the argument
   Q22b names and does not complete. *)
(*| discharges: R-13-023c |*)
Theorem old_epoch_cannot_pass_the_anchor :
  forall (old : Policy) (bad : nat -> bool) (rel : Releases) (tr : Transition)
         (seals : list Signature) (s : Statement) (gs : list Signature),
    card (population old) bad <= pol_faults old ->
    Unforgeable old bad rel seals ->
    Unforgeable old bad rel gs ->
    SealedChain bad rel ->
    certifiedb old (sealed_statement old tr) seals = true ->
    certifiedb old s gs = true ->
    prefixb (st_checkpoint s) (tr_anchor tr) = true.
Proof.
  intros old bad rel tr seals s gs Hbad Hunf1 Hunf2 Hsealed Hseal Hs.
  destruct (honest_intersection old bad (sealed_statement old tr) s seals gs
              Hbad Hseal Hs) as [i [_ [Ha1 [Ha2 Hb]]]].
  apply accepted_has_a_signature in Ha1 as [g1 [Hin1 [Hok1 Hsig1]]].
  apply accepted_has_a_signature in Ha2 as [g2 [Hin2 [Hok2 Hsig2]]].
  assert (Hr1 : rel i (sealed_statement old tr)).
  { rewrite <- Hsig1. apply (Hunf1 (sealed_statement old tr) g1);
      [exact Hin1 | exact Hok1 | rewrite Hsig1; exact Hb]. }
  assert (Hr2 : rel i s).
  { rewrite <- Hsig2. apply (Hunf2 s g2);
      [exact Hin2 | exact Hok2 | rewrite Hsig2; exact Hb]. }
  apply (Hsealed i (sealed_statement old tr) s);
    [exact Hb | exact Hr1 | discriminate | exact Hr2].
Qed.

(* T5 (R-13-023c). Across a bound transition, no accepted old-epoch
   checkpoint and accepted new-epoch checkpoint are incompatible. The
   client checks the certificates under the explicit deployment premises. *)
(*| discharges: R-13-023c |*)
Theorem cross_epoch_histories_are_compatible :
  forall (tr : Transition) (bad_old bad_new : nat -> bool)
         (rel_old rel_new : Releases)
         (seals new_anchor_sigs : list Signature)
         (s_old s_new : Statement) (gs_old gs_new : list Signature),
    card (population (tr_old tr)) bad_old <= pol_faults (tr_old tr) ->
    card (population (tr_new tr)) bad_new <= pol_faults (tr_new tr) ->
    Unforgeable (tr_old tr) bad_old rel_old seals ->
    Unforgeable (tr_old tr) bad_old rel_old gs_old ->
    Unforgeable (tr_new tr) bad_new rel_new new_anchor_sigs ->
    Unforgeable (tr_new tr) bad_new rel_new gs_new ->
    SealedChain bad_old rel_old ->
    HonestChain bad_new rel_new ->
    certifiedb (tr_old tr) (sealed_statement (tr_old tr) tr) seals = true ->
    certifiedb (tr_new tr) (plain (tr_new tr) (tr_anchor tr)) new_anchor_sigs = true ->
    certifiedb (tr_old tr) s_old gs_old = true ->
    certifiedb (tr_new tr) s_new gs_new = true ->
    comparableb (st_checkpoint s_old) (st_checkpoint s_new) = true.
Proof.
  intros tr bad_old bad_new rel_old rel_new seals new_anchor_sigs
         s_old s_new gs_old gs_new Hbo Hbn Huos Huo Huna Hun Hso Hcn Hseal Hanchor
         Hold Hnew.
  assert (Hpre : prefixb (st_checkpoint s_old) (tr_anchor tr) = true)
    by exact (old_epoch_cannot_pass_the_anchor (tr_old tr) bad_old rel_old tr
                seals s_old gs_old Hbo Huos Huo Hso Hseal Hold).
  assert (Hcmp : comparableb (tr_anchor tr) (st_checkpoint s_new) = true).
  { exact (accepted_checkpoints_are_compatible (tr_new tr) bad_new rel_new
             (plain (tr_new tr) (tr_anchor tr)) s_new new_anchor_sigs gs_new
             Hbn Huna Hun Hcn Hanchor Hnew). }
  apply comparableb_cases in Hcmp as [Hc | Hc].
  - unfold comparableb. apply orb_true_iff. left.
    exact (prefixb_trans (tr_anchor tr) (st_checkpoint s_old)
             (st_checkpoint s_new) Hpre Hc).
  - exact (two_prefixes_comparable (tr_anchor tr) (st_checkpoint s_old)
             (st_checkpoint s_new) Hpre Hc).
Qed.

(* Even at a shared anchor, distinct successor policies cannot both obtain
   valid terminal quorums under the same old-epoch deployment assumptions. *)
(*| discharges: R-13-023c |*)
Theorem accepted_terminal_transitions_are_identical :
  forall p bad rel tr1 tr2 gs1 gs2,
    card (population p) bad <= pol_faults p ->
    Unforgeable p bad rel gs1 -> Unforgeable p bad rel gs2 ->
    TerminalChain bad rel ->
    certifiedb p (sealed_statement p tr1) gs1 = true ->
    certifiedb p (sealed_statement p tr2) gs2 = true -> tr1 = tr2.
Proof.
  intros p bad rel tr1 tr2 gs1 gs2 Hb Hu1 Hu2 Hterm Hc1 Hc2.
  destruct (honest_intersection p bad (sealed_statement p tr1)
    (sealed_statement p tr2) gs1 gs2 Hb Hc1 Hc2)
    as [i [_ [Ha1 [Ha2 Hi]]]].
  apply accepted_has_a_signature in Ha1 as [g1 [Hin1 [Hok1 Hsig1]]].
  apply accepted_has_a_signature in Ha2 as [g2 [Hin2 [Hok2 Hsig2]]].
  assert (Hr1 : rel i (sealed_statement p tr1)).
  { rewrite <- Hsig1. apply (Hu1 _ g1);
      [exact Hin1 | exact Hok1 | rewrite Hsig1; exact Hi]. }
  assert (Hr2 : rel i (sealed_statement p tr2)).
  { rewrite <- Hsig2. apply (Hu2 _ g2);
      [exact Hin2 | exact Hok2 | rewrite Hsig2; exact Hi]. }
  assert (He : sealed_statement p tr1 = sealed_statement p tr2).
  { apply (Hterm i); try assumption; discriminate. }
  injection He. trivial.
Qed.

(* T5a. The sharper reading, which needs the deployment fact that the
   destination population starts at the anchor (reading 8). *)
(*| discharges: R-13-023c |*)
Theorem new_epoch_extends_the_anchor :
  forall (tr : Transition) (bad_old bad_new : nat -> bool)
         (rel_old rel_new : Releases) (seals : list Signature)
         (s_old s_new : Statement) (gs_old gs_new : list Signature),
    card (population (tr_old tr)) bad_old <= pol_faults (tr_old tr) ->
    Unforgeable (tr_old tr) bad_old rel_old seals ->
    Unforgeable (tr_old tr) bad_old rel_old gs_old ->
    Unforgeable (tr_new tr) bad_new rel_new gs_new ->
    SealedChain bad_old rel_old ->
    AnchoredChain bad_new rel_new (tr_anchor tr) ->
    certifiedb (tr_old tr) (sealed_statement (tr_old tr) tr) seals = true ->
    certifiedb (tr_old tr) s_old gs_old = true ->
    certifiedb (tr_new tr) s_new gs_new = true ->
    card (population (tr_new tr)) bad_new <= pol_faults (tr_new tr) ->
    prefixb (st_checkpoint s_old) (st_checkpoint s_new) = true.
Proof.
  intros tr bad_old bad_new rel_old rel_new seals s_old s_new gs_old gs_new
         Hbo Huos Huo Hun Hso Han Hseal Hold Hnew Hbn.
  assert (Hpre : prefixb (st_checkpoint s_old) (tr_anchor tr) = true)
    by exact (old_epoch_cannot_pass_the_anchor (tr_old tr) bad_old rel_old tr
                seals s_old gs_old Hbo Huos Huo Hso Hseal Hold).
  assert (Hext : prefixb (tr_anchor tr) (st_checkpoint s_new) = true).
  { destruct (honest_intersection (tr_new tr) bad_new s_new s_new gs_new gs_new
                Hbn Hnew Hnew) as [i [_ [Ha [_ Hb]]]].
    apply accepted_has_a_signature in Ha as [g [Hin [Hok Hsig]]].
    apply (Han i); [exact Hb |].
    rewrite <- Hsig. apply (Hun s_new g);
      [exact Hin | exact Hok | rewrite Hsig; exact Hb]. }
  exact (prefixb_trans (tr_anchor tr) (st_checkpoint s_old)
           (st_checkpoint s_new) Hpre Hext).
Qed.

(* =========================================================================
   Part 10. Availability, stated separately from safety (reading 4).

   No safety statement above mentions a responsive set. This part states
   what availability is, shows the two properties are independent in both
   directions, and gives the qualification's sufficient responsive count as
   a theorem over an arbitrary policy.
   ========================================================================= *)

Definition availableb (p : Policy) (responsive : nat -> bool) : bool :=
  pol_threshold p <=? card (population p) responsive.

(* Q22b's `N - f - o >= K`: if every faulty identity withholds and o
   further honest ones are unavailable, the rest still reach the
   threshold. *)
(*| discharges: R-13-023c |*)
Theorem withholding_bound_is_sufficient : forall (p : Policy) (o : nat),
  pol_faults p + o + pol_threshold p <= population p ->
  availableb p (fun i => (pol_faults p + o) <=? i) = true.
Proof.
  intros p o H. unfold availableb. rewrite card_ge. apply Nat.leb_le. lia.
Qed.

(* =========================================================================
   Part 11. What a client decides, and what a refusal leaves alone.

   R-13-023b's fail-closed line is that a checkpoint failing the policy
   stops the install and leaves the running generation untouched
   (R-17-030v). Every decision below is a total function on the client
   state, so that a refusal has a statable result rather than none.
   ========================================================================= *)

Definition transition_okb (p : Policy) (pinned : Checkpoint) (tr : Transition)
  (seals fresh_sigs : list Signature) : bool :=
  policy_eqb (tr_old tr) p && continuousb tr
  && prefixb pinned (tr_anchor tr)
  && certifiedb p (sealed_statement p tr) seals
  && certifiedb (tr_new tr) (plain (tr_new tr) (tr_anchor tr)) fresh_sigs.

(* The reading Q22b refutes: ordinary old-epoch signatures on the shared
   prefix, with no terminal closure of the old epoch. *)
Definition prefix_only_transition_okb (p : Policy) (pinned : Checkpoint)
  (tr : Transition) (old_sigs fresh_sigs : list Signature) : bool :=
  policy_eqb (tr_old tr) p && continuousb tr
  && prefixb pinned (tr_anchor tr)
  && certifiedb p (plain p (tr_anchor tr)) old_sigs
  && certifiedb (tr_new tr) (plain (tr_new tr) (tr_anchor tr)) fresh_sigs.

Record Rebootstrap : Type := {
  rb_old : Policy;
  rb_new : Policy;
  rb_anchor : Checkpoint;
  rb_assumptions : list nat;   (* the stated replacement trust assumptions *)
  rb_authentic : bool          (* the authenticated decision, an assumption *)
}.

Definition rebootstrap_okb (seen : list nat) (p : Policy) (rb : Rebootstrap)
  (gs : list Signature) : bool :=
  policy_eqb (rb_old rb) p && rb_authentic rb
  && negb (length (rb_assumptions rb) =? 0)
  && negb (memb (pol_scope (rb_new rb)) seen)
  && certifiedb (rb_new rb) (plain (rb_new rb) (rb_anchor rb)) gs.

Record Client : Type := {
  cl_policy : Policy;
  cl_pinned : Checkpoint;
  cl_continuity : bool;        (* whether the population-wide claim survives *)
  cl_seen : list nat           (* every trust scope this client has used *)
}.

Definition client_transition (c : Client) (tr : Transition)
  (seals fresh_sigs : list Signature) : Client :=
  if transition_okb (cl_policy c) (cl_pinned c) tr seals fresh_sigs
  then {| cl_policy := tr_new tr; cl_pinned := tr_anchor tr;
          cl_continuity := cl_continuity c; cl_seen := cl_seen c |}
  else c.

Definition client_rebootstrap (c : Client) (rb : Rebootstrap)
  (gs : list Signature) : Client :=
  if rebootstrap_okb (cl_seen c) (cl_policy c) rb gs
  then {| cl_policy := rb_new rb; cl_pinned := rb_anchor rb;
          cl_continuity := false;
          cl_seen := pol_scope (rb_new rb) :: cl_seen c |}
  else c.

(*| discharges: R-17-030v |*)
Theorem refused_transition_changes_nothing : forall c tr seals fresh_sigs,
  transition_okb (cl_policy c) (cl_pinned c) tr seals fresh_sigs = false ->
  client_transition c tr seals fresh_sigs = c.
Proof.
  intros c tr seals fresh_sigs H. unfold client_transition. rewrite H. reflexivity.
Qed.

(*| discharges: R-17-030v |*)
Theorem refused_rebootstrap_changes_nothing : forall c rb gs,
  rebootstrap_okb (cl_seen c) (cl_policy c) rb gs = false ->
  client_rebootstrap c rb gs = c.
Proof.
  intros c rb gs H. unfold client_rebootstrap. rewrite H. reflexivity.
Qed.

(* A bound transition keeps the continuity claim; an authenticated
   rebootstrap surrenders it, whatever else it satisfies. *)
(*| discharges: R-13-023c |*)
Theorem transition_keeps_the_continuity_claim : forall c tr seals fresh_sigs,
  cl_continuity (client_transition c tr seals fresh_sigs) = cl_continuity c.
Proof.
  intros c tr seals fresh_sigs. unfold client_transition.
  destruct (transition_okb (cl_policy c) (cl_pinned c) tr seals fresh_sigs);
    reflexivity.
Qed.

(*| discharges: R-13-023c |*)
Theorem rebootstrap_surrenders_the_continuity_claim : forall c rb gs,
  rebootstrap_okb (cl_seen c) (cl_policy c) rb gs = true ->
  cl_continuity (client_rebootstrap c rb gs) = false.
Proof.
  intros c rb gs H. unfold client_rebootstrap. rewrite H. reflexivity.
Qed.

(* A trust scope a client has already used is refused, which is what stops
   an A to B to A replacement path from laundering the surrendered claim. *)
(*| discharges: R-13-023c |*)
Theorem a_reused_trust_scope_is_refused : forall seen p rb gs,
  memb (pol_scope (rb_new rb)) seen = true ->
  rebootstrap_okb seen p rb gs = false.
Proof.
  intros seen p rb gs H. unfold rebootstrap_okb. rewrite H. simpl.
  rewrite ! andb_false_r. reflexivity.
Qed.

(*| discharges: R-13-023c |*)
Theorem an_accepted_rebootstrap_records_its_scope : forall c rb gs,
  rebootstrap_okb (cl_seen c) (cl_policy c) rb gs = true ->
  memb (pol_scope (rb_new rb)) (cl_seen (client_rebootstrap c rb gs)) = true.
Proof.
  intros c rb gs H. unfold client_rebootstrap. rewrite H. simpl.
  rewrite Nat.eqb_refl. reflexivity.
Qed.

(* =========================================================================
   Part 12. Constructed witnesses: what the specification admits.

   The positive instances come out of the machine rather than being
   asserted: `co_sign` runs an honest identity through prepare, commit and
   release and takes the statement it released, so an accepted certificate
   below is one honest witnesses could produce.
   ========================================================================= *)

Definition fresh_at (anchor : Checkpoint) : WState :=
  {| ws_trusted := {| dur_checkpoint := anchor; dur_serial := 0;
                      dur_terminal := None |};
     ws_stored := Some {| dur_checkpoint := anchor; dur_serial := 0;
                          dur_terminal := None |};
     ws_pending := None |}.

Lemma fresh_at_inv : forall a, Inv (fresh_at a).
Proof. intros a. unfold Inv, fresh_at. simpl. exact I. Qed.

Definition co_sign (p : Policy) (i : nat) (anchor : Checkpoint)
  (s : Statement) : list Signature :=
  match run_out true p i (fresh_at anchor) [Prepare s; Commit; Release] with
  | [out] => [ {| sig_policy := p; sig_signer := i;
                  sig_key := enrolled_key p i; sig_statement := out;
                  sig_authentic := true |} ]
  | _ => []
  end.

Definition demo_policy : Policy :=
  {| pol_scope := 1; pol_epoch := 0; pol_keys := [10; 11; 12; 13];
     pol_threshold := 3; pol_faults := 1 |}.

Definition base_c : Checkpoint := [100].
Definition left_c : Checkpoint := [100; 201].
Definition right_c : Checkpoint := [100; 202].
Definition demo_statement : Statement := plain demo_policy left_c.

Definition demo_sigs : list Signature :=
  co_sign demo_policy 0 base_c demo_statement
  ++ co_sign demo_policy 1 base_c demo_statement
  ++ co_sign demo_policy 2 base_c demo_statement.

Example the_demo_policy_is_wellformed_and_safe :
  wellformedb demo_policy = true /\ safeb demo_policy = true.
Proof. split; reflexivity. Qed.

(* R-05-165's inhabitation, taken at the predicate the whole file is about:
   three honest witnesses produce a certificate the specification accepts,
   so no theorem above is discharged from a premise nothing satisfies. *)
Example an_honest_quorum_is_accepted :
  length demo_sigs = 3
  /\ card (population demo_policy) (accepted demo_policy demo_statement demo_sigs) = 3
  /\ certifiedb demo_policy demo_statement demo_sigs = true
  /\ counted_certificateb demo_policy demo_statement demo_sigs = true.
Proof. repeat split; reflexivity. Qed.

(* One signature per binding failure R-13-023b's criterion names, each
   substituted for the third good one. *)
Definition sig_at (i : nat) (s : Statement) : Signature :=
  {| sig_policy := demo_policy; sig_signer := i;
     sig_key := enrolled_key demo_policy i; sig_statement := s;
     sig_authentic := true |}.

Definition good0 : Signature := sig_at 0 demo_statement.
Definition good1 : Signature := sig_at 1 demo_statement.
Definition good2 : Signature := sig_at 2 demo_statement.
Definition foreign_signer : Signature :=
  {| sig_policy := demo_policy; sig_signer := 9; sig_key := 99;
     sig_statement := demo_statement; sig_authentic := true |}.
Definition wrong_key : Signature :=
  {| sig_policy := demo_policy; sig_signer := 2; sig_key := 99;
     sig_statement := demo_statement; sig_authentic := true |}.
Definition unauthenticated : Signature :=
  {| sig_policy := demo_policy; sig_signer := 2;
     sig_key := enrolled_key demo_policy 2; sig_statement := demo_statement;
     sig_authentic := false |}.
Definition other_statement : Signature := sig_at 2 (plain demo_policy right_c).
Definition other_policy : Signature :=
  {| sig_policy := {| pol_scope := 1; pol_epoch := 1;
                      pol_keys := [10; 11; 12; 13]; pol_threshold := 3;
                      pol_faults := 1 |};
     sig_signer := 2; sig_key := 12; sig_statement := demo_statement;
     sig_authentic := true |}.

(*| discharges: R-13-023b |*)
Theorem every_binding_failure_costs_its_signer :
  certifiedb demo_policy demo_statement [good0; good1; good2] = true
  /\ certifiedb demo_policy demo_statement [good0; good1; good0] = false
  /\ certifiedb demo_policy demo_statement [good0; good1; foreign_signer] = false
  /\ certifiedb demo_policy demo_statement [good0; good1; wrong_key] = false
  /\ certifiedb demo_policy demo_statement [good0; good1; unauthenticated] = false
  /\ certifiedb demo_policy demo_statement [good0; good1; other_statement] = false
  /\ certifiedb demo_policy demo_statement [good0; good1; other_policy] = false.
Proof. repeat split; reflexivity. Qed.

(* An extra malformed or repeated signature refuses the whole certificate,
   even if the remaining signatures already reach the threshold. *)
(*| discharges: R-13-023b |*)
Theorem padded_certificates_are_refused :
  counted_certificateb demo_policy demo_statement (demo_sigs ++ [wrong_key]) = true
  /\ certifiedb demo_policy demo_statement (demo_sigs ++ [wrong_key]) = false
  /\ certifiedb demo_policy demo_statement (demo_sigs ++ [good0]) = false.
Proof. repeat split; reflexivity. Qed.

(* Reading 1's refuting construction: without distinct enrolled keys, one
   key holder reaches the threshold on its own. *)
Definition duplicated_keys : Policy :=
  {| pol_scope := 1; pol_epoch := 0; pol_keys := [10; 10; 12];
     pol_threshold := 2; pol_faults := 0 |}.

Definition dup_statement : Statement := plain duplicated_keys left_c.

Definition dup_sigs : list Signature :=
  [ {| sig_policy := duplicated_keys; sig_signer := 0; sig_key := 10;
       sig_statement := dup_statement; sig_authentic := true |};
    {| sig_policy := duplicated_keys; sig_signer := 1; sig_key := 10;
       sig_statement := dup_statement; sig_authentic := true |} ].

(*| discharges: R-13-023c |*)
Theorem duplicated_keys_let_one_holder_fill_two_slots :
  wellformedb duplicated_keys = false
  /\ safeb duplicated_keys = true
  /\ counted_certificateb duplicated_keys dup_statement dup_sigs = true
  /\ certifiedb duplicated_keys dup_statement dup_sigs = false
  /\ card (population duplicated_keys)
          (accepted duplicated_keys dup_statement dup_sigs) = 2.
Proof. repeat split; reflexivity. Qed.

(* =========================================================================
   Part 13. The intersection condition is tight, over every policy.

   `honest_intersection` needs `safeb`; this says the condition is not
   merely sufficient. Where a wellformed policy fails it, two acceptable
   quorums exist whose every shared member lies in a fault set the policy's
   own bound admits, so the honest witness R-13-023c's sentence requires is
   not there to be found.
   ========================================================================= *)

(*| discharges: R-13-023c |*)
Theorem the_intersection_condition_is_tight : forall p : Policy,
  wellformedb p = true -> safeb p = false ->
  exists q1 q2 bad : nat -> bool,
    pol_threshold p <= card (population p) q1
    /\ pol_threshold p <= card (population p) q2
    /\ card (population p) bad <= pol_faults p
    /\ (forall i, i < population p -> q1 i = true -> q2 i = true -> bad i = true).
Proof.
  intros p Hw Hs.
  unfold wellformedb in Hw.
  apply andb_true_iff in Hw as [Hw _]. apply andb_true_iff in Hw as [Hw _].
  apply andb_true_iff in Hw as [_ Hkn]. apply Nat.leb_le in Hkn.
  assert (Hge : 2 * pol_threshold p <= population p + pol_faults p).
  { unfold safeb in Hs.
    destruct (Nat.ltb_spec (population p + pol_faults p) (2 * pol_threshold p));
      [discriminate Hs | lia]. }
  exists (fun i => i <? pol_threshold p).
  exists (fun i => population p - pol_threshold p <=? i).
  exists (fun i => (i <? pol_threshold p)
                   && (population p - pol_threshold p <=? i)).
  assert (Hq1 : card (population p) (fun i => i <? pol_threshold p)
                = pol_threshold p) by (apply card_lt; exact Hkn).
  assert (Hq2 : card (population p)
                  (fun i => population p - pol_threshold p <=? i)
                = pol_threshold p) by (rewrite card_ge; lia).
  assert (Hbad : card (population p)
                   (fun i => (i <? pol_threshold p)
                             && (population p - pol_threshold p <=? i))
                 <= pol_faults p).
  { destruct (Nat.leb_spec (population p) (2 * pol_threshold p)) as [Hc | Hc].
    - pose proof (card_meet_join (population p)
        (fun i => i <? pol_threshold p)
        (fun i => population p - pol_threshold p <=? i)) as Hmj.
      cbv beta in Hmj.
      assert (Hjoin : card (population p)
                (fun i => (i <? pol_threshold p)
                          || (population p - pol_threshold p <=? i))
              = population p).
      { apply card_all. intros i Hi.
        destruct (Nat.ltb_spec i (pol_threshold p)) as [H1 | H1]; [reflexivity |].
        apply orb_true_iff. right. apply Nat.leb_le. lia. }
      rewrite Hjoin, Hq1, Hq2 in Hmj. lia.
    - assert (Hzero : card (population p)
                (fun i => (i <? pol_threshold p)
                          && (population p - pol_threshold p <=? i)) = 0).
      { apply card_none. intros i Hi.
        destruct (Nat.ltb_spec i (pol_threshold p)) as [H1 | H1]; simpl;
          [| reflexivity].
        destruct (Nat.leb_spec (population p - pol_threshold p) i) as [H2 | H2];
          [exfalso; lia | reflexivity]. }
      rewrite Hzero. lia. }
  split; [lia | split; [lia | split; [exact Hbad |]]].
  intros i _ H1 H2. cbv beta in H1, H2 |- *. rewrite H1, H2. reflexivity.
Qed.

(* =========================================================================
   Part 14. The 1-of-2 counterexample.

   R-13-023c's acceptance clause names it: two honest witnesses signing
   different extensions of a common checkpoint for different fresh clients.
   Both signatures authenticate, each reaches the declared threshold on its
   own, and the two checkpoints are incomparable; what refuses them is the
   intersection condition and nothing else.
   ========================================================================= *)

Definition one_of_two : Policy :=
  {| pol_scope := 2; pol_epoch := 0; pol_keys := [20; 21];
     pol_threshold := 1; pol_faults := 0 |}.

Definition split_left : Checkpoint := [301].
Definition split_right : Checkpoint := [302].
Definition left_stmt : Statement := plain one_of_two split_left.
Definition right_stmt : Statement := plain one_of_two split_right.
Definition split_left_sigs : list Signature := co_sign one_of_two 0 [] left_stmt.
Definition split_right_sigs : list Signature := co_sign one_of_two 1 [] right_stmt.

(*| discharges: R-13-023c |*)
Theorem one_of_two_is_refused_and_the_fork_is_real :
  wellformedb one_of_two = true
  /\ safeb one_of_two = false
  /\ length split_left_sigs = 1
  /\ length split_right_sigs = 1
  /\ forallb sig_authentic (split_left_sigs ++ split_right_sigs) = true
  /\ (pol_threshold one_of_two
      <=? card (population one_of_two)
            (accepted one_of_two left_stmt split_left_sigs)) = true
  /\ (pol_threshold one_of_two
      <=? card (population one_of_two)
            (accepted one_of_two right_stmt split_right_sigs)) = true
  /\ comparableb split_left split_right = false
  /\ certifiedb one_of_two left_stmt split_left_sigs = false
  /\ certifiedb one_of_two right_stmt split_right_sigs = false.
Proof. repeat split; reflexivity. Qed.

(* =========================================================================
   Part 15. The rollback counterexample.

   The specification quarantines a store that does not match the anchor, so
   an identity whose durable state is rolled back releases nothing until
   authenticated recovery. The alternative construction is the one that
   trusts the store: it is the same schedule at `anchored = false`, and it
   releases two incomparable checkpoints from one honest identity.
   ========================================================================= *)

Definition latest_after_left : Durable :=
  {| dur_checkpoint := left_c; dur_serial := 1; dur_terminal := None |}.
Definition stale_record : Durable :=
  {| dur_checkpoint := base_c; dur_serial := 0; dur_terminal := None |}.
Definition left2_c : Checkpoint := [100; 201; 203].

Definition evidence_of (d : Durable) (ok : bool) : Evidence :=
  {| ev_policy := demo_policy; ev_signer := 0; ev_record := d;
     ev_authentic := ok |}.

Definition rollback_schedule : list Action :=
  [Prepare (plain demo_policy left_c); Commit; Release;
   Damage (Some stale_record);
   Prepare (plain demo_policy right_c); Commit; Release].

(*| discharges: R-13-023c |*)
Theorem rollback_is_refused_and_tolerating_it_forks :
  map st_checkpoint
      (run_out true demo_policy 0 (fresh_at base_c) rollback_schedule) = [left_c]
  /\ map st_checkpoint
      (run_out false demo_policy 0 (fresh_at base_c) rollback_schedule)
     = [left_c; right_c]
  /\ comparableb left_c right_c = false.
Proof. repeat split; reflexivity. Qed.

(*| discharges: R-13-023c |*)
Theorem every_crash_cut_keeps_the_history :
  run_out true demo_policy 0 (fresh_at base_c)
    [Prepare (plain demo_policy left_c); Crash; Release] = []
  /\ run_out true demo_policy 0 (fresh_at base_c)
    [Prepare (plain demo_policy left_c); Commit; Crash;
     Prepare (plain demo_policy right_c); Commit; Release] = []
  /\ map st_checkpoint (run_out true demo_policy 0 (fresh_at base_c)
    [Prepare (plain demo_policy left_c); Commit; Crash; Release;
     Prepare (plain demo_policy left_c); Commit; Release]) = [left_c].
Proof. repeat split; reflexivity. Qed.

(*| discharges: R-13-023c |*)
Theorem only_authenticated_latest_recovery_restores_signing :
  map st_checkpoint (run_out true demo_policy 0 (fresh_at base_c)
    [Prepare (plain demo_policy left_c); Commit; Release; Damage None;
     Recover (evidence_of latest_after_left true);
     Prepare (plain demo_policy left2_c); Commit; Release])
  = [left_c; left2_c]
  /\ map st_checkpoint (run_out true demo_policy 0 (fresh_at base_c)
    [Prepare (plain demo_policy left_c); Commit; Release; Damage None;
     Recover (evidence_of stale_record true);
     Prepare (plain demo_policy left2_c); Commit; Release]) = [left_c]
  /\ map st_checkpoint (run_out true demo_policy 0 (fresh_at base_c)
    [Prepare (plain demo_policy left_c); Commit; Release; Damage None;
     Recover (evidence_of latest_after_left false);
     Prepare (plain demo_policy left2_c); Commit; Release]) = [left_c].
Proof. repeat split; reflexivity. Qed.

(* =========================================================================
   Part 16. The shared-prefix disjoint-transition counterexample.

   Two independently safe populations can both sign one shared prefix and
   then extend it differently, so an ordinary shared-prefix certificate is
   not a transition. The bound transition requires the old epoch's terminal
   quorum, and a sealed old identity then refuses to continue.
   ========================================================================= *)

Definition old_pol : Policy :=
  {| pol_scope := 7; pol_epoch := 0; pol_keys := [30; 31; 32; 33];
     pol_threshold := 3; pol_faults := 1 |}.
Definition new_pol : Policy :=
  {| pol_scope := 7; pol_epoch := 1; pol_keys := [40; 41; 42; 43];
     pol_threshold := 3; pol_faults := 1 |}.
Definition anchor_c : Checkpoint := [100].
Definition change : Transition :=
  {| tr_old := old_pol; tr_new := new_pol; tr_anchor := anchor_c |}.
Definition old_fork : Checkpoint := [100; 401].
Definition new_fork : Checkpoint := [100; 402].

Definition quorum_of (p : Policy) (anchor : Checkpoint) (s : Statement)
  : list Signature :=
  co_sign p 0 anchor s ++ co_sign p 1 anchor s ++ co_sign p 2 anchor s.

Definition old_prefix_sigs : list Signature :=
  quorum_of old_pol anchor_c (plain old_pol anchor_c).
Definition new_anchor_sigs : list Signature :=
  quorum_of new_pol anchor_c (plain new_pol anchor_c).
Definition seal_sigs : list Signature :=
  quorum_of old_pol anchor_c (sealed_statement old_pol change).
Definition old_fork_sigs : list Signature :=
  quorum_of old_pol anchor_c (plain old_pol old_fork).
Definition new_fork_sigs : list Signature :=
  quorum_of new_pol anchor_c (plain new_pol new_fork).

(*| discharges: R-13-023c |*)
Theorem shared_prefix_transition_is_refused_and_forks :
  continuousb change = true
  /\ prefix_only_transition_okb old_pol [] change old_prefix_sigs new_anchor_sigs
     = true
  /\ transition_okb old_pol [] change old_prefix_sigs new_anchor_sigs = false
  /\ transition_okb old_pol [] change seal_sigs new_anchor_sigs = true
  /\ certifiedb old_pol (plain old_pol old_fork) old_fork_sigs = true
  /\ certifiedb new_pol (plain new_pol new_fork) new_fork_sigs = true
  /\ comparableb old_fork new_fork = false.
Proof. repeat split; reflexivity. Qed.

(*| discharges: R-13-023c |*)
Theorem a_sealed_old_witness_refuses_to_continue :
  map st_checkpoint (run_out true old_pol 0 (fresh_at anchor_c)
    [Prepare (sealed_statement old_pol change); Commit; Release;
     Prepare (plain old_pol old_fork); Commit; Release]) = [anchor_c]
  /\ map st_checkpoint (run_out true old_pol 0 (fresh_at anchor_c)
    [Prepare (sealed_statement old_pol change); Commit; Release;
     Prepare (sealed_statement old_pol change); Commit; Release])
     = [anchor_c; anchor_c]
  /\ certifiedb old_pol (plain old_pol old_fork)
       (co_sign old_pol 3 anchor_c (plain old_pol old_fork)) = false.
Proof. repeat split; reflexivity. Qed.

Definition terminal_record : Durable :=
  {| dur_checkpoint := anchor_c; dur_serial := 1;
     dur_terminal := Some change |}.
Definition terminal_recovery : Evidence :=
  {| ev_policy := old_pol; ev_signer := 0; ev_record := terminal_record;
     ev_authentic := true |}.
Definition alternative_destination : Policy :=
  {| pol_scope := 7; pol_epoch := 1; pol_keys := [70; 71; 72; 73];
     pol_threshold := 3; pol_faults := 1 |}.
Definition alternative_change : Transition :=
  {| tr_old := old_pol; tr_new := alternative_destination;
     tr_anchor := anchor_c |}.

(* Recovery restores closure as well as the checkpoint. A different
   destination at that same checkpoint is refused after recovery too. *)
(*| discharges: R-13-023c |*)
Theorem terminal_recovery_preserves_the_exact_destination :
  run_out true old_pol 0 (fresh_at anchor_c)
    [Prepare (sealed_statement old_pol change); Commit; Release;
     Damage None; Recover terminal_recovery;
     Prepare (plain old_pol old_fork); Commit; Release;
     Prepare (sealed_statement old_pol alternative_change); Commit; Release;
     Prepare (sealed_statement old_pol change); Commit; Release]
  = [sealed_statement old_pol change; sealed_statement old_pol change]
  /\ continuousb alternative_change = true
  /\ change <> alternative_change.
Proof. repeat split; try reflexivity. discriminate. Qed.

(*| discharges: R-17-030v |*)
Theorem a_transition_below_the_pin_is_refused :
  transition_okb old_pol old_fork change seal_sigs new_anchor_sigs = false
  /\ client_transition
       {| cl_policy := old_pol; cl_pinned := old_fork; cl_continuity := true;
          cl_seen := [7] |} change seal_sigs new_anchor_sigs
     = {| cl_policy := old_pol; cl_pinned := old_fork; cl_continuity := true;
          cl_seen := [7] |}.
Proof. split; reflexivity. Qed.

(*| discharges: R-13-023c |*)
Theorem a_bound_transition_moves_policy_and_pin_together :
  client_transition
    {| cl_policy := old_pol; cl_pinned := []; cl_continuity := true;
       cl_seen := [7] |} change seal_sigs new_anchor_sigs
  = {| cl_policy := new_pol; cl_pinned := anchor_c; cl_continuity := true;
       cl_seen := [7] |}.
Proof. reflexivity. Qed.

(* =========================================================================
   Part 17. Availability, and the rebootstrap that gives up the claim.
   ========================================================================= *)

Definition unanimous_three : Policy :=
  {| pol_scope := 3; pol_epoch := 0; pol_keys := [50; 51; 52];
     pol_threshold := 3; pol_faults := 1 |}.
Definition lowered_three : Policy :=
  {| pol_scope := 3; pol_epoch := 0; pol_keys := [50; 51; 52];
     pol_threshold := 2; pol_faults := 1 |}.

(*| discharges: R-13-023c |*)
Theorem safety_and_availability_are_independent :
  safeb unanimous_three = true
  /\ availableb unanimous_three (fun i => i <? 2) = false
  /\ safeb one_of_two = false
  /\ availableb one_of_two (fun i => i <? 1) = true.
Proof. repeat split; reflexivity. Qed.

(* Why a threshold is never reduced to restore progress: the same
   responsive set that the unanimous policy cannot satisfy is satisfied by
   a lowered threshold whose policy the intersection condition refuses. *)
(*| discharges: R-13-023c |*)
Theorem lowering_the_threshold_to_restore_progress_can_break_safety :
  pol_keys unanimous_three = pol_keys lowered_three
  /\ pol_faults unanimous_three = pol_faults lowered_three
  /\ availableb unanimous_three (fun i => i <? 2) = false
  /\ availableb lowered_three (fun i => i <? 2) = true
  /\ safeb unanimous_three = true
  /\ safeb lowered_three = false.
Proof. repeat split; reflexivity. Qed.

Definition replacement_pol : Policy :=
  {| pol_scope := 8; pol_epoch := 0; pol_keys := [60; 61; 62];
     pol_threshold := 3; pol_faults := 1 |}.

Definition replacement : Rebootstrap :=
  {| rb_old := demo_policy; rb_new := replacement_pol; rb_anchor := right_c;
     rb_assumptions := [70]; rb_authentic := true |}.

Definition replacement_sigs : list Signature :=
  quorum_of replacement_pol right_c (plain replacement_pol right_c).

Definition pinned_client : Client :=
  {| cl_policy := demo_policy; cl_pinned := left_c; cl_continuity := true;
     cl_seen := [1] |}.

(*| discharges: R-13-023c |*)
Theorem rebootstrap_is_explicit_and_surrenders_the_old_claim :
  prefixb left_c right_c = false
  /\ rebootstrap_okb (cl_seen pinned_client) (cl_policy pinned_client)
       replacement replacement_sigs = true
  /\ client_rebootstrap pinned_client replacement replacement_sigs
     = {| cl_policy := replacement_pol; cl_pinned := right_c;
          cl_continuity := false; cl_seen := [8; 1] |}
  /\ rebootstrap_okb (cl_seen pinned_client) (cl_policy pinned_client)
       {| rb_old := demo_policy; rb_new := replacement_pol;
          rb_anchor := right_c; rb_assumptions := [70];
          rb_authentic := false |} replacement_sigs = false
  /\ rebootstrap_okb (cl_seen pinned_client) (cl_policy pinned_client)
       {| rb_old := demo_policy; rb_new := replacement_pol;
          rb_anchor := right_c; rb_assumptions := [];
          rb_authentic := true |} replacement_sigs = false.
Proof. repeat split; reflexivity. Qed.

(* =========================================================================
   Part 18. The residual R-13-023a keeps.

   One accepted checkpoint carries two admissible package identities. The
   policy decides that both are committed and decides nothing about which
   a recipient is given, which is exactly the selective-delivery residual
   R-13-023a books and no theorem here narrows.
   ========================================================================= *)

Definition both_variants : Checkpoint := [100; 401; 402].
Definition both_statement : Statement := plain demo_policy both_variants.
Definition both_sigs : list Signature :=
  quorum_of demo_policy base_c both_statement.

(*| discharges: R-13-023a |*)
Theorem one_checkpoint_carries_two_valid_variants :
  certifiedb demo_policy both_statement both_sigs = true
  /\ includedb both_variants 401 = true
  /\ includedb both_variants 402 = true
  /\ 401 <> 402.
Proof. repeat split; try reflexivity. discriminate. Qed.

(* =========================================================================
   Part 19. Jointly inhabited authentication and deployment assumptions.

   Record construction alone cannot show that a safety theorem's premises
   are satisfiable. These witnesses construct actual serialized histories,
   certificates released by those histories, and every external premise
   of the within-epoch and cross-epoch theorems together. The authentication
   assumption is restricted to received evidence: setting a freely built
   signature's symbolic flag does not make it a deployment's release.
   ========================================================================= *)

Lemma released_certificates_are_unforgeable : forall p bad rel gs,
  (forall g, In g gs -> rel (sig_signer g) (sig_statement g)) ->
  Unforgeable p bad rel gs.
Proof.
  intros p bad rel gs Hr s g Hin Hok _.
  unfold sig_okb in Hok. apply andb_true_iff in Hok as [_ Hs].
  apply statement_eqb_eq in Hs. rewrite <- Hs. apply Hr. exact Hin.
Qed.

Definition no_faults : nat -> bool := fun _ => false.
Definition no_rogue_releases : Releases := fun _ _ => False.
Definition early_statement : Statement := plain demo_policy base_c.
Definition early_sigs : list Signature :=
  quorum_of demo_policy base_c early_statement.
Definition demo_schedule : list Action :=
  [Prepare early_statement; Commit; Release;
   Prepare demo_statement; Commit; Release].
Definition demo_deployment : Releases :=
  deployment demo_policy no_faults (fun _ => fresh_at base_c)
    (fun _ => demo_schedule) no_rogue_releases.

(*| discharges: R-13-023c |*)
Theorem safety_premises_are_jointly_inhabited :
  card (population demo_policy) no_faults <= pol_faults demo_policy
  /\ Unforgeable demo_policy no_faults demo_deployment early_sigs
  /\ Unforgeable demo_policy no_faults demo_deployment demo_sigs
  /\ HonestChain no_faults demo_deployment
  /\ certifiedb demo_policy early_statement early_sigs = true
  /\ certifiedb demo_policy demo_statement demo_sigs = true
  /\ st_checkpoint early_statement <> st_checkpoint demo_statement.
Proof.
  split; [cbv; lia |].
  split.
  { apply released_certificates_are_unforgeable. intros g Hin.
    cbv in Hin. destruct Hin as [<- | [<- | [<- | []]]];
      cbv; auto. }
  split.
  { apply released_certificates_are_unforgeable. intros g Hin.
    cbv in Hin. destruct Hin as [<- | [<- | [<- | []]]];
      cbv; auto. }
  split.
  { apply deployment_is_an_honest_chain. intro i. apply fresh_at_inv. }
  repeat split; try reflexivity. discriminate.
Qed.

(* Applying the general theorem to two different, accepted checkpoints;
   the conclusion is obtained using all its exhibited premises. *)
Example inhabited_within_epoch_application :
  comparableb base_c left_c = true.
Proof.
  destruct safety_premises_are_jointly_inhabited
    as [Hb [Hu1 [Hu2 [Hchain [Hc1 [Hc2 _]]]]]].
  exact (accepted_checkpoints_are_compatible demo_policy no_faults
    demo_deployment early_statement demo_statement early_sigs demo_sigs
    Hb Hu1 Hu2 Hchain Hc1 Hc2).
Qed.

Definition old_demo_schedule : list Action :=
  [Prepare (plain old_pol anchor_c); Commit; Release;
   Prepare (sealed_statement old_pol change); Commit; Release].
Definition new_demo_schedule : list Action :=
  [Prepare (plain new_pol anchor_c); Commit; Release;
   Prepare (plain new_pol new_fork); Commit; Release].
Definition old_demo_deployment : Releases :=
  deployment old_pol no_faults (fun _ => fresh_at anchor_c)
    (fun _ => old_demo_schedule) no_rogue_releases.
Definition new_demo_deployment : Releases :=
  deployment new_pol no_faults (fun _ => fresh_at anchor_c)
    (fun _ => new_demo_schedule) no_rogue_releases.

(*| discharges: R-13-023c |*)
Theorem cross_epoch_premises_are_jointly_inhabited :
  card (population old_pol) no_faults <= pol_faults old_pol
  /\ card (population new_pol) no_faults <= pol_faults new_pol
  /\ Unforgeable old_pol no_faults old_demo_deployment seal_sigs
  /\ Unforgeable old_pol no_faults old_demo_deployment old_prefix_sigs
  /\ Unforgeable new_pol no_faults new_demo_deployment new_anchor_sigs
  /\ Unforgeable new_pol no_faults new_demo_deployment new_fork_sigs
  /\ SealedChain no_faults old_demo_deployment
  /\ TerminalChain no_faults old_demo_deployment
  /\ HonestChain no_faults new_demo_deployment
  /\ AnchoredChain no_faults new_demo_deployment anchor_c
  /\ certifiedb old_pol (sealed_statement old_pol change) seal_sigs = true
  /\ certifiedb old_pol (plain old_pol anchor_c) old_prefix_sigs = true
  /\ certifiedb new_pol (plain new_pol anchor_c) new_anchor_sigs = true
  /\ certifiedb new_pol (plain new_pol new_fork) new_fork_sigs = true
  /\ transition_okb old_pol [] change seal_sigs new_anchor_sigs = true.
Proof.
  split; [cbv; lia |]. split; [cbv; lia |].
  split.
  { apply released_certificates_are_unforgeable. intros g Hin.
    cbv in Hin. destruct Hin as [<- | [<- | [<- | []]]]; cbv; auto. }
  split.
  { apply released_certificates_are_unforgeable. intros g Hin.
    cbv in Hin. destruct Hin as [<- | [<- | [<- | []]]]; cbv; auto. }
  split.
  { apply released_certificates_are_unforgeable. intros g Hin.
    cbv in Hin. destruct Hin as [<- | [<- | [<- | []]]]; cbv; auto. }
  split.
  { apply released_certificates_are_unforgeable. intros g Hin.
    cbv in Hin. destruct Hin as [<- | [<- | [<- | []]]]; cbv; auto. }
  split.
  { apply deployment_is_a_sealed_chain. intro i. apply fresh_at_inv. }
  split.
  { apply deployment_has_unique_terminal_statements.
    intro i. apply fresh_at_inv. }
  split.
  { apply deployment_is_an_honest_chain. intro i. apply fresh_at_inv. }
  split.
  { apply deployment_started_at_an_anchor_is_anchored;
      intro i; [apply fresh_at_inv | reflexivity]. }
  repeat split; reflexivity.
Qed.

Example inhabited_cross_epoch_application :
  comparableb anchor_c new_fork = true.
Proof.
  destruct cross_epoch_premises_are_jointly_inhabited as
    [Hbo [Hbn [Hus [Huo [Hua [Hun [Hseal [_ [Hchain [_
      [Hcs [Hco [Hca [Hcn _]]]]]]]]]]]]]].
  exact (cross_epoch_histories_are_compatible change no_faults no_faults
    old_demo_deployment new_demo_deployment seal_sigs new_anchor_sigs
    (plain old_pol anchor_c) (plain new_pol new_fork)
    old_prefix_sigs new_fork_sigs Hbo Hbn Hus Huo Hua Hun Hseal Hchain
    Hcs Hca Hco Hcn).
Qed.

(* =========================================================================
   R-05-166's inhabitation witnesses: one closed definition per record this
   file's statements quantify over, named for that record and ascribed at
   it. The prover decides inhabitation by type-checking the ascription, so
   `run.py proofs` reads a name rather than approximating a type judgement.
   ========================================================================= *)

Definition witness_Policy : Policy := demo_policy.
Definition witness_Transition : Transition := change.
Definition witness_Statement : Statement := demo_statement.
Definition witness_Signature : Signature := good0.
Definition witness_Durable : Durable := latest_after_left.
Definition witness_WState : WState := fresh_at base_c.
Definition witness_Evidence : Evidence := evidence_of latest_after_left true.
Definition witness_Client : Client := pinned_client.
Definition witness_Rebootstrap : Rebootstrap := replacement.

(* =========================================================================
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared
   set R-05-164 currently makes empty, so "Closed under the global context"
   is that emptiness checked mechanically.
   ========================================================================= *)

Print Assumptions safe_matches_the_register_spelling.
Print Assumptions enrolled_keys_identify_witnesses.
Print Assumptions certified_implies_counted.
Print Assumptions honest_intersection.
Print Assumptions honest_run_never_forks.
Print Assumptions sealed_releases_are_anchor_prefixes.
Print Assumptions terminal_releases_are_identical.
Print Assumptions deployment_is_an_honest_chain.
Print Assumptions deployment_is_a_sealed_chain.
Print Assumptions deployment_has_unique_terminal_statements.
Print Assumptions deployment_started_at_an_anchor_is_anchored.
Print Assumptions accepted_checkpoints_are_compatible.
Print Assumptions old_epoch_cannot_pass_the_anchor.
Print Assumptions accepted_terminal_transitions_are_identical.
Print Assumptions cross_epoch_histories_are_compatible.
Print Assumptions new_epoch_extends_the_anchor.
Print Assumptions withholding_bound_is_sufficient.
Print Assumptions refused_transition_changes_nothing.
Print Assumptions refused_rebootstrap_changes_nothing.
Print Assumptions transition_keeps_the_continuity_claim.
Print Assumptions rebootstrap_surrenders_the_continuity_claim.
Print Assumptions a_reused_trust_scope_is_refused.
Print Assumptions an_accepted_rebootstrap_records_its_scope.
Print Assumptions the_intersection_condition_is_tight.
Print Assumptions an_honest_quorum_is_accepted.
Print Assumptions every_binding_failure_costs_its_signer.
Print Assumptions padded_certificates_are_refused.
Print Assumptions duplicated_keys_let_one_holder_fill_two_slots.
Print Assumptions one_of_two_is_refused_and_the_fork_is_real.
Print Assumptions rollback_is_refused_and_tolerating_it_forks.
Print Assumptions every_crash_cut_keeps_the_history.
Print Assumptions only_authenticated_latest_recovery_restores_signing.
Print Assumptions shared_prefix_transition_is_refused_and_forks.
Print Assumptions a_sealed_old_witness_refuses_to_continue.
Print Assumptions terminal_recovery_preserves_the_exact_destination.
Print Assumptions a_transition_below_the_pin_is_refused.
Print Assumptions a_bound_transition_moves_policy_and_pin_together.
Print Assumptions safety_and_availability_are_independent.
Print Assumptions lowering_the_threshold_to_restore_progress_can_break_safety.
Print Assumptions rebootstrap_is_explicit_and_surrenders_the_old_claim.
Print Assumptions one_checkpoint_carries_two_valid_variants.
Print Assumptions safety_premises_are_jointly_inhabited.
Print Assumptions inhabited_within_epoch_application.
Print Assumptions cross_epoch_premises_are_jointly_inhabited.
Print Assumptions inhabited_cross_epoch_application.
