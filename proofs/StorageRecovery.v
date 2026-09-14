(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   Policy-independent storage recovery, under the contract committed in
   docs/implementation/storage-recovery-policy.md before implementation.

   JournalIndex owns Rec, Store, scan, sieve and replay. KeyspaceDomains owns
   the L2 object/metadata/index writer. The register does not choose between
   stopping at a tear and skipping it; this file selects neither. It proves
   intact-input agreement, a finite selected-record bound and exact manifest
   completeness before publication, independently of the discipline.

   R-10-002 and R-10-036 require the L0 transaction boundary; R-10-005c requires
   matching object/index visibility. A closing flag alone is insufficient.
   The expected manifest below is an AUTHENTICATED INPUT of the future byte
   decoder, not an assertion that rec_landed authenticates arbitrary torn
   bytes. Its identity, ordered records and bound must be checked against the
   durable checkpoint by that adapter. The decoder, complete-block hashes,
   disk persistence, checkpoint/ack ordering and selected recovery arm remain
   M5.3 obligations. This source neither derives authentication from equality
   nor implements the decoder. Its refusal applies to a presented complete
   transaction; absence of a transaction and recovery escalation remain the
   policy owner's decisions.

   The acceptance predicate is native compilation, empty global assumption
   closure, rocqchk, named record inhabitation, quantified completeness and
   agreement proofs, and computed missing/reordered/duplicated/torn payload
   refusals beside an accepted transaction. The exact contract document also
   records the target crash-half predicate and its outstanding producers.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-10-002 R-10-005c R-10-036
   SHA256: 70805f02f331bc7fb95fc0a398d5f2094bf9a58b5477651ec5701890b249a5a1
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import List Bool Arith Lia.
Require Import JournalIndex.
Require KeyspaceDomains.
Import ListNotations.

Lemma sieve_of_an_intact_journal : forall j,
  all_of intact j = true -> sieve j = j.
Proof.
  induction j as [|r rs IH]; intros H; [reflexivity|].
  cbn in H. apply andb_true_iff in H as [Hr Hrs].
  cbn. rewrite Hr, (IH Hrs). reflexivity.
Qed.

(*| discharges: R-10-002, R-10-036 |*)
Theorem intact_input_does_not_choose_a_recovery_arm : forall j s b,
  all_of intact j = true ->
  recover_under scan j s b = recover_under sieve j s b.
Proof.
  intros j s b H. unfold recover_under.
  rewrite (scan_of_an_intact_journal j H), (sieve_of_an_intact_journal j H).
  reflexivity.
Qed.

Theorem equal_selection_gives_equal_recovery : forall a z j s b,
  a j = z j -> recover_under a j s b = recover_under z j s b.
Proof. intros a z j s b H. unfold recover_under. rewrite H. reflexivity. Qed.

Lemma scan_selected_record_bound : forall j, length (scan j) <= length j.
Proof.
  induction j as [|r rs IH]; cbn; [lia|].
  destruct (intact r); cbn; lia.
Qed.

Lemma sieve_selected_record_bound : forall j, length (sieve j) <= length j.
Proof.
  induction j as [|r rs IH]; cbn; [lia|].
  destruct (intact r); cbn; lia.
Qed.

(* Both arms process at most the declared finite input population. This is
   a record bound, not a cycle bound or a proof that commits' repeated scans
   are linear time. An implementation must supply its own WCET refinement. *)
Theorem both_arms_respect_the_input_bound : forall j limit,
  length j <= limit -> length (scan j) <= limit /\ length (sieve j) <= limit.
Proof.
  intros j limit H. pose proof (scan_selected_record_bound j).
  pose proof (sieve_selected_record_bound j). lia.
Qed.

Definition recovery_record_eq_dec : forall a b : Rec, {a = b} + {a <> b}.
Proof. decide equality; [apply Nat.eq_dec|apply Nat.eq_dec|decide equality|apply Nat.eq_dec|apply Nat.eq_dec|apply Nat.eq_dec]. Defined.

Definition records_equalb (a b : list Rec) : bool :=
  if list_eq_dec recovery_record_eq_dec a b then true else false.

Lemma records_equalb_exact : forall a b, records_equalb a b = true <-> a = b.
Proof.
  intros a b. unfold records_equalb.
  destruct (list_eq_dec recovery_record_eq_dec a b); split; intros H;
    try reflexivity; try assumption; try discriminate; contradiction.
Qed.

Record TransactionManifest : Type := {
  manifest_txn : nat;
  manifest_records : list Rec;
  manifest_limit : nat
}.

Fixpoint closes_only_at_end (rs : list Rec) : bool :=
  match rs with
  | [] => false
  | r :: tail => match tail with
                 | [] => rec_closes r
                 | _ :: _ => negb (rec_closes r) && closes_only_at_end tail
                 end
  end.

Definition manifest_wellformed (m : TransactionManifest) : bool :=
  (length (manifest_records m) <=? manifest_limit m) &&
  all_of (fun r => (rec_txn r =? manifest_txn m) && intact r) (manifest_records m) &&
  closes_only_at_end (manifest_records m).

Definition complete_selected (m : TransactionManifest) (rs : list Rec) : bool :=
  all_of intact rs && records_equalb rs (manifest_records m).

Theorem a_wellformed_manifest_has_only_intact_records_of_its_transaction : forall m,
  manifest_wellformed m = true ->
  all_of (fun r => (rec_txn r =? manifest_txn m) && intact r) (manifest_records m) = true.
Proof.
  intros m H. unfold manifest_wellformed in H.
  repeat rewrite andb_true_iff in H. tauto.
Qed.

Theorem a_terminal_manifest_is_nonempty : forall rs,
  closes_only_at_end rs = true -> rs <> [].
Proof. intros [|r rs] H; [discriminate H|discriminate]. Qed.

Theorem a_nonfinal_record_cannot_close_the_transaction : forall r tail,
  tail <> [] -> closes_only_at_end (r :: tail) = true ->
  rec_closes r = false /\ closes_only_at_end tail = true.
Proof.
  intros r [|s rest] Hnonempty H; [contradiction|].
  change (negb (rec_closes r) && closes_only_at_end (s :: rest) = true) in H.
  apply andb_true_iff in H as [Hfirst Htail]. apply negb_true_iff in Hfirst.
  split; assumption.
Qed.

Definition recover_complete (m : TransactionManifest) (cut : Discipline)
    (j : list Rec) (s : Store) : option Store :=
  if manifest_wellformed m && complete_selected m (cut j)
  then Some (recover_under cut j s) else None.

Lemma complete_selected_is_exact : forall m rs,
  complete_selected m rs = true -> rs = manifest_records m.
Proof.
  intros m rs H. apply andb_true_iff in H as [_ H].
  apply records_equalb_exact. exact H.
Qed.

(* The theorem mentions the original authenticated manifest, not just the
   surviving records. A terminal commit with absent payload cannot satisfy it. *)
(*| discharges: R-10-036, R-10-005c |*)
Theorem admitted_recovery_contains_the_complete_ordered_transaction :
  forall m cut j s out, recover_complete m cut j s = Some out ->
  cut j = manifest_records m /\
  (forall b, out b = apply_all (manifest_records m)
                    (commits (manifest_records m)) s b).
Proof.
  intros m cut j s out H. unfold recover_complete in H.
  destruct (manifest_wellformed m && complete_selected m (cut j)) eqn:E;
    [|discriminate].
  apply andb_true_iff in E as [_ E].
  apply complete_selected_is_exact in E. inversion H; subst out.
  split; [exact E|]. intros b. unfold recover_under. rewrite E. reflexivity.
Qed.

Theorem a_missing_manifest_member_refuses_publication : forall m cut j s r,
  In r (manifest_records m) -> ~ In r (cut j) -> recover_complete m cut j s = None.
Proof.
  intros m cut j s r Hpresent Hmissing. unfold recover_complete.
  destruct (manifest_wellformed m && complete_selected m (cut j)) eqn:E;
    [|reflexivity].
  apply andb_true_iff in E as [_ E]. apply complete_selected_is_exact in E.
  rewrite E in Hmissing. contradiction.
Qed.

Theorem any_changed_order_or_population_is_refused : forall m cut j s,
  cut j <> manifest_records m -> recover_complete m cut j s = None.
Proof.
  intros m cut j s Hneq. unfold recover_complete.
  destruct (manifest_wellformed m && complete_selected m (cut j)) eqn:E;
    [|reflexivity].
  apply andb_true_iff in E as [_ E]. apply complete_selected_is_exact in E.
  contradiction.
Qed.

Theorem a_successful_manifest_bounds_every_replayed_record : forall m cut j s out,
  recover_complete m cut j s = Some out -> length (cut j) <= manifest_limit m.
Proof.
  intros m cut j s out H. pose proof
    (admitted_recovery_contains_the_complete_ordered_transaction m cut j s out H) as [Heq _].
  unfold recover_complete in H.
  destruct (manifest_wellformed m && complete_selected m (cut j)) eqn:E; [|discriminate].
  apply andb_true_iff in E as [E _]. unfold manifest_wellformed in E.
  repeat rewrite andb_true_iff in E. destruct E as [[E _] _].
  apply Nat.leb_le in E. rewrite Heq. exact E.
Qed.

Theorem complete_recovery_preserves_unwritten_blocks : forall m cut j s out b,
  recover_complete m cut j s = Some out -> touched_under cut j b = false -> out b = s b.
Proof.
  intros m cut j s out b H Hu. unfold recover_complete in H.
  destruct (manifest_wellformed m && complete_selected m (cut j)); [|discriminate].
  inversion H; subst out. apply a_discipline_leaves_untouched_blocks_alone. exact Hu.
Qed.

(* Reuse the actual L2 writer, including every crash prefix. The proof is
   arm independent because these prefixes are intact, not because all torn
   journals are claimed to agree. Arbitrary byte tears still need the adapter. *)
(*| discharges: R-10-005c, R-10-036 |*)
Theorem the_l2_writer_has_arm_independent_crash_prefix_replay : forall c ba n s b,
  recover_under scan (take n (KeyspaceDomains.spec_writer c ba)) s b =
  recover_under sieve (take n (KeyspaceDomains.spec_writer c ba)) s b.
Proof.
  intros c ba n s b. apply intact_input_does_not_choose_a_recovery_arm.
  apply all_of_take. apply KeyspaceDomains.the_specification_writer_is_intact.
Qed.

Definition recovery_payload : Rec :=
  {| rec_txn := 2; rec_block := 1; rec_value := 11; rec_closes := false;
     rec_len := 2; rec_landed := 2 |}.
Definition recovery_terminal : Rec :=
  {| rec_txn := 2; rec_block := 2; rec_value := 22; rec_closes := true;
     rec_len := 2; rec_landed := 2 |}.
Definition recovery_manifest : TransactionManifest :=
  {| manifest_txn := 2; manifest_records := [recovery_payload; recovery_terminal];
     manifest_limit := 2 |}.
Definition recovery_blank : Store := fun _ => 0.
Definition recovery_answer (m : TransactionManifest) (cut : Discipline) j b : option nat :=
  match recover_complete m cut j recovery_blank with None => None | Some s => Some (s b) end.

Example the_manifest_is_inhabited_and_the_complete_transaction_lands :
  manifest_wellformed recovery_manifest = true /\
  recovery_answer recovery_manifest scan (manifest_records recovery_manifest) 1 = Some 11 /\
  recovery_answer recovery_manifest sieve (manifest_records recovery_manifest) 2 = Some 22.
Proof. repeat split; reflexivity. Qed.

Example a_surviving_commit_marker_does_not_supply_its_missing_payload :
  commits [recovery_terminal] 2 = true /\
  recovery_answer recovery_manifest sieve [recovery_terminal] 1 = None.
Proof. split; reflexivity. Qed.

Example reordered_duplicate_and_torn_payloads_are_refused :
  recovery_answer recovery_manifest scan [recovery_terminal; recovery_payload] 1 = None /\
  recovery_answer recovery_manifest sieve [recovery_payload; recovery_payload; recovery_terminal] 1 = None /\
  recovery_answer recovery_manifest scan (tear_at 0 1 (manifest_records recovery_manifest)) 1 = None /\
  recovery_answer recovery_manifest sieve (tear_at 0 1 (manifest_records recovery_manifest)) 1 = None.
Proof. repeat split; reflexivity. Qed.

(* JournalIndex's own counterexample is retained; manifest completeness
   does not retroactively make the two raw recoveries equivalent. *)
Theorem raw_recovery_arms_remain_observably_distinct : spec_recover <> sieve_recover.
Proof.
  intros H.
  assert (E : spec_recover (tear_at 2 0 demo_journal) demo_store 1 =
              sieve_recover (tear_at 2 0 demo_journal) demo_store 1).
  { rewrite H. reflexivity. }
  discriminate E.
Qed.

Definition witness_TransactionManifest : TransactionManifest := recovery_manifest.
