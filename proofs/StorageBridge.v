(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   StorageBridge.v

   The bytes-to-record bridge M5.3 owes between the modeled block device
   (interfaces/block-device-contract.md) and the journal records
   JournalIndex.v and StorageRecovery.v consume, under the policy R-10-002a
   selects: complete authenticated prefix redo.

   What this file is. A specification of one journal frame layout over device
   bytes, a writer that seals transactions into frames, and a decoder that
   reads frames back into JournalIndex's `Rec`, with every payload and commit
   authenticated through an opener the composition binds to a domain key. The
   decoder is written against that opener and never holds a key (R-10-022);
   `gcm_opener` instantiates it with AesGcm.v's functional AES-GCM reference,
   the one cipher R-10-024 freezes. It implements no cipher and no binary
   corresponds to it: executable crypto and the executable storage path are
   separate joins, and the device contract requires this bridge's separate
   review before any device trace is presented as a JournalIndex record trace.

   The decoder, and what it refuses. Frames are read in position order from
   the start of the journal region, at most `journal_frames` of them. A blank
   frame ends the journal. A payload frame waits for its commit. A commit frame
   is authenticated on its own bytes under a nonce naming the generation and
   its position; when it authenticates, the transaction is known to have
   committed, and every payload it names must be present, in order, at the
   position the commit names, under the header the commit names, and open
   under the tag the commit holds. Any missing, torn, reordered, duplicated,
   misdirected or stale payload of an authentic commit is a refusal, never a
   partial replay or an uncommitted transaction (R-10-002a). The first frame
   that is neither blank, a waiting payload nor an authentic commit ends the
   authenticated prefix: independent suffix salvage is declined. Whether that
   end is ordinary loss of unacknowledged work or corruption of acknowledged
   work is decided against `acknowledged`, the count of transactions the
   durable checkpoint acknowledges, which this file takes as an authenticated
   input exactly as StorageRecovery takes its manifest. Fewer recovered
   transactions than acknowledged is a refusal (R-10-002a's fail-closed arm).
   The decoder emits only records that authenticated, so the raw arms of
   JournalIndex agree on everything it recovers; it never invents a torn or
   intact record to feed them.

   What stays open, and whose it is. The device contract requires this bridge
   to leave the record-verification and commit-representation decisions
   explicit:
   1. The layout is this file's reading, not a production format. One frame
      is one device block; the header's fields are one byte each, which bounds
      a journal at 256 positions; a payload's value is one byte, because
      JournalIndex's `rec_value` is a nat and a node image's encoding into it
      is that owner's decision.
   2. Commit representation. A commit frame carries each payload's position,
      target and tag, so the commit evidence binds the complete ordered
      payload, target addresses and content identities (R-10-002a), and a
      payload's tag is held by the record that references it rather than
      beside its ciphertext, which is R-10-022a's placement read onto the
      journal. The decoded closing flag is the last payload's. The commit frame
      carries its own tag; whether commit evidence may authenticate itself this
      way or must be referenced by the checkpoint is open.
   3. Nonce derivation. A nonce is the generation, the frame position and the
      frame kind. It is unique under one key only while a generation is never
      reused, which the checkpoint and journal-reuse boundary of R-10-002a must
      guarantee; that producer is owed, as is the checkpoint that supplies
      `acknowledged` and the generation.
   4. Refusal is a verdict about the affected store only. What a composition
      does with it (R-17-030zb) is outside this file.

   The acceptance this file carries is native compilation, an empty
   assumption closure, rocqchk, quantified properties of the decoder over an
   arbitrary opener, among them that every recovered transaction is within
   the payload bound and made only of openings the opener produced, and
   computed witnesses under the AES-GCM reference: an accepted two-transaction
   journal and its replayed store, eleven crash images the device's tear rule
   leaves as the journal is written, the low bit inverted in one byte of each
   field class the decoder reads, and misdirected, swapped, stale, wrong-key,
   wrong-generation, corrupted-commit and missing-payload cases. Finite
   witnesses are not a claim about every mask, bit or key.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-10-002a R-10-022 R-10-022a R-10-024 R-17-030zb
   SHA256: 8fd58a5b975c9796eab875178f3bb18d871f0ef24587568f0dd025acbdbca12d
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import List Bool Arith Lia.
Require Import JournalIndex.
Require Import StorageRecovery.
Require AesGcm.
Import ListNotations.

(* -------------------------------------------------------------------------
   Device bytes and the frame layout.
   ------------------------------------------------------------------------- *)

(* A medium byte as the modeled device holds it. *)
Definition bytes : Type := list nat.

Fixpoint bytes_eqb (a b : bytes) : bool :=
  match a, b with
  | [], [] => true
  | x :: a', y :: b' => Nat.eqb x y && bytes_eqb a' b'
  | _, _ => false
  end.

Lemma bytes_eqb_true : forall a b, bytes_eqb a b = true -> a = b.
Proof.
  induction a as [|x a IH]; intros [|y b] H; try discriminate; [reflexivity|].
  cbn in H. apply andb_true_iff in H as [Hx Hb].
  apply Nat.eqb_eq in Hx. subst y. f_equal. apply IH. exact Hb.
Qed.

Definition payload_kind : nat := 1.
Definition commit_kind : nat := 2.
Definition frame_header_bytes : nat := 16.
Definition frame_tag_bytes : nat := 16.
Definition frame_value_bytes : nat := 1.
Definition frame_entry_bytes : nat := 2 + frame_tag_bytes.
Definition frame_nonce_bytes : nat := 12.

(* The composition's journal geometry: the frame length, which is the device
   block length, the bounded record count and the bound on payloads per
   transaction. *)
Record Layout : Type := {
  frame_bytes : nat;
  journal_frames : nat;
  payload_limit : nat
}.

(* A layout this file's encoding can carry: a full commit fits one frame and
   every position fits its one-byte field. *)
Definition layout_fits (l : Layout) : bool :=
  (1 <=? payload_limit l)
  && (frame_header_bytes + frame_tag_bytes + payload_limit l * frame_entry_bytes <=? frame_bytes l)
  && (journal_frames l <=? 256).

Definition pad_to (n : nat) (b : bytes) : bytes := b ++ repeat 0 (n - length b).

Definition frame_at (l : Layout) (medium : bytes) (p : nat) : bytes :=
  firstn (frame_bytes l) (skipn (p * frame_bytes l) medium).

Definition frame_nonce (generation position kind : nat) : bytes :=
  generation :: position :: kind :: repeat 0 (frame_nonce_bytes - 3).

Definition payload_header (txn target : nat) : bytes :=
  pad_to frame_header_bytes [payload_kind; txn; target].

Definition commit_header (txn count : nat) : bytes :=
  pad_to frame_header_bytes [commit_kind; txn; count].

(* -------------------------------------------------------------------------
   The crypto core as the filesystem sees it (R-10-022): seal and open under a
   key it holds. Nonce, associated data, plaintext or ciphertext and tag are
   bytes.
   ------------------------------------------------------------------------- *)

Definition Opener : Type := bytes -> bytes -> bytes -> bytes -> option bytes.
Definition Sealer : Type := bytes -> bytes -> bytes -> bytes * bytes.

(* The AES-GCM reference at a 128-bit tag. `key_words` is FIPS 197's Nk; the
   key length is a composition parameter R-10-024 does not fix. *)
Definition gcm_opener (key_words : nat) (key : bytes) : Opener :=
  fun iv aad c t =>
    match AesGcm.gcm_open AesGcm.block_bits key_words (AesGcm.bytes_from key)
            (AesGcm.block_from iv) (AesGcm.block_from aad) (AesGcm.block_from c)
            (AesGcm.block_from t) with
    | Some m => Some (AesGcm.bytes_of m)
    | None => None
    end.

Definition gcm_sealer (key_words : nat) (key : bytes) : Sealer :=
  fun iv aad m =>
    let r := AesGcm.gcm_encrypt key_words (AesGcm.bytes_from key)
               (AesGcm.block_from iv) (AesGcm.block_from aad) (AesGcm.block_from m) in
    (AesGcm.bytes_of (fst r), AesGcm.bytes_of (snd r)).

(* -------------------------------------------------------------------------
   The writer. A payload frame is its header then its ciphertext; a commit
   frame is its header, its own tag, then one entry per payload in order.
   ------------------------------------------------------------------------- *)

Record Entry : Type := {
  entry_position : nat;
  entry_target : nat;
  entry_tag : bytes
}.

Definition encode_entry (e : Entry) : bytes :=
  entry_position e :: entry_target e :: entry_tag e.

Fixpoint decode_entries (count : nat) (b : bytes) : list Entry :=
  match count with
  | 0 => []
  | S k => {| entry_position := nth 0 b 0; entry_target := nth 1 b 0;
              entry_tag := firstn frame_tag_bytes (skipn 2 b) |}
           :: decode_entries k (skipn frame_entry_bytes b)
  end.

(* A transaction as the storage layer hands it to the journal: its number and
   its ordered (target block, value) writes. *)
Record Txn : Type := {
  txn_id : nat;
  txn_writes : list (nat * nat)
}.

Fixpoint seal_payloads (seal : Sealer) (g txn p : nat) (ws : list (nat * nat))
  : list bytes * list Entry :=
  match ws with
  | [] => ([], [])
  | (target, value) :: rest =>
      let hdr := payload_header txn target in
      let sealed := seal (frame_nonce g p payload_kind) hdr [value] in
      let tail := seal_payloads seal g txn (S p) rest in
      ((hdr ++ fst sealed) :: fst tail,
       {| entry_position := p; entry_target := target; entry_tag := snd sealed |} :: snd tail)
  end.

Definition seal_commit (seal : Sealer) (g txn p : nat) (es : list Entry) : bytes :=
  let hdr := commit_header txn (length es) in
  let body := flat_map encode_entry es in
  hdr ++ snd (seal (frame_nonce g p commit_kind) (hdr ++ body) []) ++ body.

Definition seal_txn (seal : Sealer) (g p : nat) (x : Txn) : list bytes :=
  let sealed := seal_payloads seal g (txn_id x) p (txn_writes x) in
  fst sealed ++ [seal_commit seal g (txn_id x) (p + length (txn_writes x)) (snd sealed)].

Fixpoint seal_journal (seal : Sealer) (g p : nat) (xs : list Txn) : list bytes :=
  match xs with
  | [] => []
  | x :: rest => seal_txn seal g p x ++ seal_journal seal g (p + S (length (txn_writes x))) rest
  end.

(* The journal region as the device holds it: each frame padded to a block,
   then blank blocks to the end of the region. *)
Definition journal_medium (l : Layout) (frames : list bytes) : bytes :=
  flat_map (pad_to (frame_bytes l)) frames
  ++ repeat 0 ((journal_frames l - length frames) * frame_bytes l).

(* -------------------------------------------------------------------------
   The decoder.
   ------------------------------------------------------------------------- *)

Definition blank_frame (f : bytes) : bool := forallb (Nat.eqb 0) f.

(* A payload frame read and waiting for its commit. *)
Record Pending : Type := {
  pending_position : nat;
  pending_header : bytes;
  pending_body : bytes
}.

Definition pending_of (p : nat) (f : bytes) : Pending :=
  {| pending_position := p; pending_header := firstn frame_header_bytes f;
     pending_body := firstn frame_value_bytes (skipn frame_header_bytes f) |}.

(* Every waiting payload against the authentic commit's entries, in order:
   same position, the header the entry names, and an opening under the tag the
   commit holds. Any disagreement is None. *)
Fixpoint open_payloads (open : Opener) (g txn : nat) (ps : list Pending) (es : list Entry)
  : option (list (nat * nat)) :=
  match ps, es with
  | [], [] => Some []
  | q :: ps', e :: es' =>
      if Nat.eqb (pending_position q) (entry_position e)
         && bytes_eqb (pending_header q) (payload_header txn (entry_target e))
      then match open (frame_nonce g (pending_position q) payload_kind) (pending_header q)
                      (pending_body q) (entry_tag e) with
           | Some [v] =>
               match open_payloads open g txn ps' es' with
               | Some ws => Some ((entry_target e, v) :: ws)
               | None => None
               end
           | _ => None
           end
      else None
  | _, _ => None
  end.

Definition commit_count (f : bytes) : nat := nth 2 f 0.
Definition commit_txn (f : bytes) : nat := nth 1 f 0.
Definition commit_tag (f : bytes) : bytes := firstn frame_tag_bytes (skipn frame_header_bytes f).
Definition commit_body (f : bytes) : bytes :=
  firstn (commit_count f * frame_entry_bytes) (skipn (frame_header_bytes + frame_tag_bytes) f).

Definition commit_admissible (l : Layout) (f : bytes) : bool :=
  (1 <=? commit_count f) && (commit_count f <=? payload_limit l)
  && bytes_eqb (firstn frame_header_bytes f) (commit_header (commit_txn f) (commit_count f)).

Inductive Walked : Type :=
| Ended (txns : list (nat * list (nat * nat)))
| CommittedPayloadRefused (position : nat).

Fixpoint walk (l : Layout) (open : Opener) (g : nat) (medium : bytes) (fuel p : nat)
    (pending : list Pending) (done : list (nat * list (nat * nat))) : Walked :=
  match fuel with
  | 0 => Ended (rev done)
  | S fuel' =>
      let f := frame_at l medium p in
      if blank_frame f then Ended (rev done)
      else if Nat.eqb (nth 0 f 0) payload_kind then
        if length pending <? payload_limit l
        then walk l open g medium fuel' (S p) (pending ++ [pending_of p f]) done
        else Ended (rev done)
      else if Nat.eqb (nth 0 f 0) commit_kind && commit_admissible l f then
        match open (frame_nonce g p commit_kind) (firstn frame_header_bytes f ++ commit_body f)
                   [] (commit_tag f) with
        | Some [] =>
            match open_payloads open g (commit_txn f) pending
                    (decode_entries (commit_count f) (commit_body f)) with
            | Some ws => walk l open g medium fuel' (S p) [] ((commit_txn f, ws) :: done)
            | None => CommittedPayloadRefused p
            end
        | _ => Ended (rev done)
        end
      else Ended (rev done)
  end.

Inductive Outcome : Type :=
| Recovered (txns : list (nat * list (nat * nat)))
| RefusedCommittedPayload (position : nat)
| RefusedAcknowledgedMissing (recovered acknowledged : nat).

Definition decode (l : Layout) (open : Opener) (g acknowledged : nat) (medium : bytes)
  : Outcome :=
  match walk l open g medium (journal_frames l) 0 [] [] with
  | CommittedPayloadRefused p => RefusedCommittedPayload p
  | Ended txns =>
      if length txns <? acknowledged
      then RefusedAcknowledgedMissing (length txns) acknowledged
      else Recovered txns
  end.

(* -------------------------------------------------------------------------
   The records JournalIndex and StorageRecovery consume. A decoded payload is
   a whole record of one granule; the last payload of a transaction closes it.
   ------------------------------------------------------------------------- *)

Fixpoint records_of (txn : nat) (ws : list (nat * nat)) : list Rec :=
  match ws with
  | [] => []
  | (b, v) :: rest =>
      {| rec_txn := txn; rec_block := b; rec_value := v;
         rec_closes := match rest with [] => true | _ => false end;
         rec_len := 1; rec_landed := 1 |} :: records_of txn rest
  end.

Definition decoded_records (txns : list (nat * list (nat * nat))) : list Rec :=
  flat_map (fun t => records_of (fst t) (snd t)) txns.

Definition manifest_of (l : Layout) (t : nat * list (nat * nat)) : TransactionManifest :=
  {| manifest_txn := fst t; manifest_records := records_of (fst t) (snd t);
     manifest_limit := payload_limit l |}.

Lemma records_of_intact : forall txn ws, all_of intact (records_of txn ws) = true.
Proof.
  intros txn ws. induction ws as [|[b v] rest IH]; [reflexivity|]. exact IH.
Qed.

Lemma records_of_belong : forall txn ws,
  all_of (fun r => (rec_txn r =? txn) && intact r) (records_of txn ws) = true.
Proof.
  intros txn ws. induction ws as [|[b v] rest IH]; [reflexivity|].
  change (((txn =? txn) && true)
          && all_of (fun r => (rec_txn r =? txn) && intact r) (records_of txn rest) = true).
  rewrite Nat.eqb_refl. exact IH.
Qed.

Lemma records_of_length : forall txn ws, length (records_of txn ws) = length ws.
Proof.
  intros txn ws. induction ws as [|[b v] rest IH]; [reflexivity|].
  cbn [records_of length]. rewrite IH. reflexivity.
Qed.

Lemma records_of_closes_only_at_end : forall txn ws,
  ws <> [] -> closes_only_at_end (records_of txn ws) = true.
Proof.
  intros txn ws. induction ws as [|[b v] rest IH]; intros Hne; [contradiction|].
  destruct rest as [|[b' v'] rest'].
  - reflexivity.
  - exact (IH ltac:(discriminate)).
Qed.

Lemma decoded_records_intact : forall txns, all_of intact (decoded_records txns) = true.
Proof.
  induction txns as [|t txns IH]; [reflexivity|].
  change (all_of intact (records_of (fst t) (snd t) ++ decoded_records txns) = true).
  rewrite all_of_app, records_of_intact, IH. reflexivity.
Qed.

(* A nonempty transaction within the payload bound is exactly one of
   StorageRecovery's well formed manifests. *)
Theorem a_decoded_transaction_is_a_wellformed_manifest : forall l t,
  snd t <> [] -> length (snd t) <= payload_limit l ->
  manifest_wellformed (manifest_of l t) = true.
Proof.
  intros l [txn ws] Hne Hle. cbn [fst snd] in Hne, Hle.
  unfold manifest_wellformed, manifest_of. cbn [manifest_records manifest_limit manifest_txn fst snd].
  rewrite records_of_length, records_of_belong, (records_of_closes_only_at_end txn ws Hne).
  apply Nat.leb_le in Hle. rewrite Hle. reflexivity.
Qed.

(* And StorageRecovery's complete-transaction recovery admits it, replaying
   exactly the transaction under either raw arm. *)
Theorem a_decoded_transaction_recovers_completely : forall l t s,
  snd t <> [] -> length (snd t) <= payload_limit l ->
  recover_complete (manifest_of l t) scan (records_of (fst t) (snd t)) s
  = Some (recover_under scan (records_of (fst t) (snd t)) s).
Proof.
  intros l t s Hne Hle. unfold recover_complete.
  rewrite (a_decoded_transaction_is_a_wellformed_manifest l t Hne Hle).
  pose proof (records_of_intact (fst t) (snd t)) as Hi.
  unfold complete_selected. rewrite (scan_of_an_intact_journal _ Hi), Hi.
  assert (E : records_equalb (records_of (fst t) (snd t))
                (manifest_records (manifest_of l t)) = true)
    by (apply records_equalb_exact; reflexivity).
  rewrite E. reflexivity.
Qed.

(* The decoder never presents a torn record, so the two raw recovery arms of
   JournalIndex agree on every journal it recovers. *)
Theorem decoded_records_do_not_choose_a_recovery_arm : forall txns s b,
  recover_under scan (decoded_records txns) s b = recover_under sieve (decoded_records txns) s b.
Proof.
  intros txns s b. apply intact_input_does_not_choose_a_recovery_arm.
  apply decoded_records_intact.
Qed.

(* -------------------------------------------------------------------------
   What every recovered transaction is, over an arbitrary opener: nonempty,
   within the payload bound, and made only of writes the opener produced at a
   payload frame of the journal region whose header names that transaction
   and target.
   ------------------------------------------------------------------------- *)

Definition opened_at (l : Layout) (open : Opener) (g : nat) (medium : bytes)
    (txn target value : nat) : Prop :=
  exists p tag, p < journal_frames l /\
    firstn frame_header_bytes (frame_at l medium p) = payload_header txn target /\
    open (frame_nonce g p payload_kind) (payload_header txn target)
         (firstn frame_value_bytes (skipn frame_header_bytes (frame_at l medium p))) tag
    = Some [value].

Definition sound_txn (l : Layout) (open : Opener) (g : nat) (medium : bytes)
    (t : nat * list (nat * nat)) : Prop :=
  snd t <> [] /\ length (snd t) <= payload_limit l /\
  forall target value, In (target, value) (snd t) -> opened_at l open g medium (fst t) target value.

Lemma decode_entries_length : forall n b, length (decode_entries n b) = n.
Proof.
  induction n as [|n IH]; intros b; [reflexivity|]. cbn [decode_entries length]. rewrite IH. reflexivity.
Qed.

Lemma open_payloads_sound : forall open g txn ps es ws,
  open_payloads open g txn ps es = Some ws ->
  length ws = length es /\
  forall target v, In (target, v) ws ->
    exists q tag, In q ps /\ pending_header q = payload_header txn target /\
      open (frame_nonce g (pending_position q) payload_kind) (pending_header q)
           (pending_body q) tag = Some [v].
Proof.
  intros open g txn ps. induction ps as [|q ps IH]; intros [|e es] ws H;
    cbn [open_payloads] in H.
  - inversion H; subst. split; [reflexivity|]. intros target v [].
  - discriminate H.
  - discriminate H.
  - destruct (Nat.eqb (pending_position q) (entry_position e)
              && bytes_eqb (pending_header q) (payload_header txn (entry_target e))) eqn:Ec;
      cbv beta iota in H; [|discriminate H].
    apply andb_true_iff in Ec as [_ Eh]. apply bytes_eqb_true in Eh.
    destruct (open (frame_nonce g (pending_position q) payload_kind) (pending_header q)
                   (pending_body q) (entry_tag e)) as [[|v [|v' rest]]|] eqn:Eo;
      cbv beta iota in H; try discriminate H.
    destruct (open_payloads open g txn ps es) as [ws'|] eqn:Er;
      cbv beta iota in H; [|discriminate H].
    inversion H; subst. destruct (IH es ws' Er) as [Hlen Hin]. split.
    + cbn [length]. rewrite Hlen. reflexivity.
    + intros target v0 [Hhd|Htl].
      * inversion Hhd; subst. exists q, (entry_tag e). split; [left; reflexivity|].
        split; [exact Eh|exact Eo].
      * destruct (Hin target v0 Htl) as [q' [tag [Hq' Hrest]]].
        exists q', tag. split; [right; exact Hq'|exact Hrest].
Qed.

Definition pending_read (l : Layout) (medium : bytes) (q : Pending) : Prop :=
  exists p, p < journal_frames l /\ q = pending_of p (frame_at l medium p).

Lemma walk_sound : forall l open g medium fuel p pending done txns,
  p + fuel = journal_frames l ->
  Forall (pending_read l medium) pending ->
  Forall (sound_txn l open g medium) done ->
  walk l open g medium fuel p pending done = Ended txns ->
  Forall (sound_txn l open g medium) txns.
Proof.
  intros l open g medium fuel. induction fuel as [|fuel IH];
    intros p pending done txns Hp Hpend Hdone H.
  - cbn in H. inversion H; subst. apply Forall_rev. exact Hdone.
  - cbn [walk] in H.
    set (f := frame_at l medium p) in H.
    destruct (blank_frame f); cbv beta iota in H.
    { inversion H; subst. apply Forall_rev. exact Hdone. }
    destruct (Nat.eqb (nth 0 f 0) payload_kind); cbv beta iota in H.
    + destruct (length pending <? payload_limit l); cbv beta iota in H.
      * eapply IH; [| |exact Hdone|exact H]; [lia|].
        apply Forall_app. split; [exact Hpend|]. constructor; [|constructor].
        unfold pending_read. exists p. split; [lia|reflexivity].
      * inversion H; subst. apply Forall_rev. exact Hdone.
    + destruct (Nat.eqb (nth 0 f 0) commit_kind && commit_admissible l f) eqn:Ec;
        cbv beta iota in H.
      2: { inversion H; subst. apply Forall_rev. exact Hdone. }
      destruct (open (frame_nonce g p commit_kind) (firstn frame_header_bytes f ++ commit_body f)
                     [] (commit_tag f)) as [[|x xs]|]; cbv beta iota in H.
      2, 3: (inversion H; subst; apply Forall_rev; exact Hdone).
      destruct (open_payloads open g (commit_txn f) pending
                  (decode_entries (commit_count f) (commit_body f))) as [ws|] eqn:Eo;
        cbv beta iota in H.
      2: discriminate H.
      apply andb_true_iff in Ec as [_ Ea]. unfold commit_admissible in Ea.
      apply andb_true_iff in Ea as [Ea _]. apply andb_true_iff in Ea as [Elo Ehi].
      apply Nat.leb_le in Elo. apply Nat.leb_le in Ehi.
      destruct (open_payloads_sound _ _ _ _ _ _ Eo) as [Hlen Hin].
      rewrite decode_entries_length in Hlen.
      eapply IH; [| | |exact H]; [lia|constructor|].
      constructor; [|exact Hdone].
      unfold sound_txn. split; [|split].
      * cbn [snd]. intros Hnil. rewrite Hnil in Hlen. cbn in Hlen. lia.
      * cbn [snd]. lia.
      * cbn [fst snd]. intros target value Htv.
        destruct (Hin target value Htv) as [q [tag [Hq [Hh Ho]]]].
        rewrite Forall_forall in Hpend. destruct (Hpend q Hq) as [p' [Hp' Heq]].
        subst q. cbn [pending_header pending_body pending_position pending_of] in Hh, Ho.
        unfold opened_at. exists p', tag. split; [exact Hp'|]. split; [exact Hh|].
        rewrite Hh in Ho. exact Ho.
Qed.

(* Every transaction a decode recovers is sound, whatever the opener. *)
Theorem every_recovered_transaction_is_authenticated_and_bounded :
  forall l open g acknowledged medium txns,
  decode l open g acknowledged medium = Recovered txns ->
  Forall (sound_txn l open g medium) txns.
Proof.
  intros l open g acknowledged medium txns H. unfold decode in H.
  destruct (walk l open g medium (journal_frames l) 0 [] []) as [done|p] eqn:Ew;
    cbv beta iota in H; [|discriminate H].
  destruct (length done <? acknowledged); cbv beta iota in H; [discriminate H|].
  inversion H; subst.
  eapply walk_sound; [| | |exact Ew]; [reflexivity|constructor|constructor].
Qed.

(* A recovery never falls short of the checkpoint's acknowledgement: fewer
   recovered transactions than acknowledged is a refusal. *)
Theorem a_recovery_keeps_every_acknowledged_transaction :
  forall l open g acknowledged medium txns,
  decode l open g acknowledged medium = Recovered txns -> acknowledged <= length txns.
Proof.
  intros l open g acknowledged medium txns H. unfold decode in H.
  destruct (walk l open g medium (journal_frames l) 0 [] []) as [done|p];
    cbv beta iota in H; [|discriminate H].
  destruct (length done <? acknowledged) eqn:E; cbv beta iota in H; [discriminate H|].
  inversion H; subst. apply Nat.ltb_ge in E. exact E.
Qed.

(* Each recovered transaction is admitted by StorageRecovery's complete
   recovery. *)
Theorem every_recovered_transaction_is_a_complete_manifest :
  forall l open g acknowledged medium txns s,
  decode l open g acknowledged medium = Recovered txns ->
  Forall (fun t => recover_complete (manifest_of l t) scan (records_of (fst t) (snd t)) s
                   = Some (recover_under scan (records_of (fst t) (snd t)) s)) txns.
Proof.
  intros l open g acknowledged medium txns s H.
  pose proof (every_recovered_transaction_is_authenticated_and_bounded _ _ _ _ _ _ H) as Hs.
  rewrite Forall_forall in *. intros t Ht. destruct (Hs t Ht) as [Hne [Hle _]].
  apply a_decoded_transaction_recovers_completely; assumption.
Qed.

(* -------------------------------------------------------------------------
   Computed witnesses under the AES-GCM reference. The layout is 128-byte
   frames, six of them, at most two payloads per transaction; the admitted
   device fixture's 64-byte blocks carry a one-payload commit. The key and the
   generation are this witness's inputs, standing for what the composition's
   crypto core and checkpoint supply. The journal holds transaction 8, two
   payloads and their commit at frames 0 to 2, then transaction 7, one payload
   and its commit at frames 3 and 4.

   The cases are chosen by fault and field class rather than enumerated over
   every byte, bit or mask: rocqchk rechecks each computed case by ordinary
   conversion, where one opening under the reference costs seconds.
   ------------------------------------------------------------------------- *)

Definition bridge_layout : Layout :=
  {| frame_bytes := 128; journal_frames := 6; payload_limit := 2 |}.

Definition bridge_key : bytes := seq 0 16.
Definition other_key : bytes := seq 1 16.
Definition bridge_generation : nat := 1.

Definition bridge_open : Opener := gcm_opener 4 bridge_key.
Definition bridge_seal : Sealer := gcm_sealer 4 bridge_key.

Definition bridge_txns : list Txn :=
  [ {| txn_id := 8; txn_writes := [(1, 21); (2, 22)] |};
    {| txn_id := 7; txn_writes := [(3, 11)] |} ].

Definition bridge_recovered : list (nat * list (nat * nat)) :=
  [(8, [(1, 21); (2, 22)]); (7, [(3, 11)])].

Definition bridge_frames : list bytes :=
  seal_journal bridge_seal bridge_generation 0 bridge_txns.

(* The written journal, computed once. The example after it holds the
   literal to the writer. *)
Definition bridge_medium : bytes :=
  Eval vm_compute in journal_medium bridge_layout bridge_frames.

Example the_medium_is_the_writer_s_journal :
  journal_medium bridge_layout bridge_frames = bridge_medium.
Proof. vm_compute. reflexivity. Qed.

Example the_layout_fits_the_encoding : layout_fits bridge_layout = true := eq_refl.

Example the_written_journal_recovers_both_transactions :
  decode bridge_layout bridge_open bridge_generation 2 bridge_medium = Recovered bridge_recovered.
Proof. vm_compute. reflexivity. Qed.

(* What those transactions replay to, block by block, under either raw arm. *)
Example the_recovered_transactions_replay_every_write :
  map (recover_under scan (decoded_records bridge_recovered) (fun _ => 0)) [0; 1; 2; 3]
  = [0; 21; 22; 11] /\
  map (recover_under sieve (decoded_records bridge_recovered) (fun _ => 0)) [0; 1; 2; 3]
  = [0; 21; 22; 11].
Proof. split; reflexivity. Qed.

(* The key and the generation are inputs of every opening: another key, or
   the right key read as another generation, authenticates no commit. *)
Example another_key_or_generation_authenticates_nothing :
  decode bridge_layout (gcm_opener 4 other_key) bridge_generation 1 bridge_medium
  = RefusedAcknowledgedMissing 0 1 /\
  decode bridge_layout bridge_open 2 1 bridge_medium = RefusedAcknowledgedMissing 0 1.
Proof. vm_compute. split; reflexivity. Qed.

(* Device faults at the byte level. *)
Definition replace_frame (l : Layout) (medium : bytes) (p : nat) (f : bytes) : bytes :=
  firstn (p * frame_bytes l) medium ++ pad_to (frame_bytes l) f
  ++ skipn (S p * frame_bytes l) medium.

(* The lowest bit of one byte inverted. *)
Definition flip_low (x : nat) : nat := if Nat.odd x then x - 1 else S x.

Definition flip_bit (medium : bytes) (offset : nat) : bytes :=
  firstn offset medium ++ [flip_low (nth offset medium 0)] ++ skipn (S offset) medium.

(* The device contract's tear rule, (old & ~m) | (new & m), one bit at a time
   over the eight bits of a byte: a set mask bit takes the new bit. *)
Fixpoint tear_bits (width old new mask : nat) : nat :=
  match width with
  | 0 => 0
  | S w => (if Nat.odd mask then Nat.b2n (Nat.odd new) else Nat.b2n (Nat.odd old))
           + 2 * tear_bits w (Nat.div2 old) (Nat.div2 new) (Nat.div2 mask)
  end.

Fixpoint tear_bytes (old new mask : bytes) : bytes :=
  match old, new, mask with
  | o :: old', n :: new', m :: mask' => tear_bits 8 o n m :: tear_bytes old' new' mask'
  | _, _, _ => []
  end.

Example the_tear_rule_takes_each_bit_from_its_mask :
  tear_bytes [0; 255; 165; 90] [255; 0; 255; 255] [165; 165; 0; 255] = [165; 90; 165; 255]
  := eq_refl.

(* A payload a device returns from the wrong block, two payloads swapped, and
   a payload sealed for the same position under the next generation: the
   commit authenticates, so each is a refusal of a known committed
   transaction, even where the checkpoint acknowledges nothing, rather than
   its partial replay. *)
Definition stale_payload : bytes :=
  payload_header 8 2 ++ fst (bridge_seal (frame_nonce 2 1 payload_kind) (payload_header 8 2) [22]).

Example misdirected_swapped_and_stale_payloads_are_refused :
  decode bridge_layout bridge_open bridge_generation 0
    (replace_frame bridge_layout bridge_medium 1 (frame_at bridge_layout bridge_medium 0))
  = RefusedCommittedPayload 2 /\
  decode bridge_layout bridge_open bridge_generation 0
    (replace_frame bridge_layout
       (replace_frame bridge_layout bridge_medium 1 (frame_at bridge_layout bridge_medium 0))
       0 (frame_at bridge_layout bridge_medium 1))
  = RefusedCommittedPayload 2 /\
  decode bridge_layout bridge_open bridge_generation 0
    (replace_frame bridge_layout bridge_medium 1 stale_payload)
  = RefusedCommittedPayload 2.
Proof. vm_compute. repeat split; reflexivity. Qed.

(* A corrupted commit is not evidence of commitment, and a missing payload
   ends the prefix before its commit: either way the transaction is lost as
   unacknowledged work, or refused when the checkpoint acknowledged it, and
   the intact transaction after it is not salvaged. *)
Example a_corrupted_commit_or_missing_payload_is_uncommitted_or_refused :
  let torn := flip_bit bridge_medium (2 * 128 + frame_header_bytes) in
  let missing := replace_frame bridge_layout bridge_medium 1 [] in
  decode bridge_layout bridge_open bridge_generation 0 torn = Recovered [] /\
  decode bridge_layout bridge_open bridge_generation 1 torn = RefusedAcknowledgedMissing 0 1 /\
  decode bridge_layout bridge_open bridge_generation 0 missing = Recovered [] /\
  decode bridge_layout bridge_open bridge_generation 1 missing = RefusedAcknowledgedMissing 0 1.
Proof. vm_compute. repeat split; reflexivity. Qed.

(* A payload that does not open under its authentic commit is a refusal even
   where the checkpoint acknowledges nothing. *)
Example a_torn_committed_payload_is_refused :
  decode bridge_layout bridge_open bridge_generation 0
    (flip_bit bridge_medium (1 * 128 + frame_header_bytes))
  = RefusedCommittedPayload 2.
Proof. vm_compute. reflexivity. Qed.

(* Generated: crash images the device's tear rule leaves while the journal is
   written frame by frame. Frames before `k` landed whole and frame `k` was in
   flight over a blank block, under the full mask and one non-prefix mask at
   each of the five frames, with the empty journal besides; a zero mask at
   frame `k` leaves the image the full mask leaves at frame `k - 1`. Each image
   is decoded against the acknowledgement a crash there can have, a
   transaction being acknowledged only after its commit is durable, and
   recovers exactly the transactions whose commit landed whole: none of these
   eleven images loses acknowledged work or publishes a partial transaction. *)
Definition split_mask : bytes := map (fun i => if Nat.even i then 165 else 90) (seq 0 128).

Definition crash_image (k : nat) (mask : bytes) : bytes :=
  journal_medium bridge_layout
    (map (frame_at bridge_layout bridge_medium) (seq 0 k)
     ++ [tear_bytes (repeat 0 128) (frame_at bridge_layout bridge_medium k) mask]).

(* The two commits are frames 2 and 4. *)
Definition commits_before (k : nat) : nat := if k <=? 2 then 0 else 1.

Definition expected_after_crash (k : nat) (whole : bool) : list (nat * list (nat * nat)) :=
  (if (3 <=? k) || ((k =? 2) && whole) then [(8, [(1, 21); (2, 22)])] else [])
  ++ (if (k =? 4) && whole then [(7, [(3, 11)])] else []).

Definition crash_cases : list (nat * bytes) :=
  (0, repeat 0 128) :: flat_map (fun k => [(k, repeat 255 128); (k, split_mask)]) (seq 0 5).

Example the_crash_family_has_eleven_members : length crash_cases = 11 := eq_refl.

Example each_crash_image_recovers_exactly_the_landed_commits :
  map (fun c => decode bridge_layout bridge_open bridge_generation (commits_before (fst c))
                  (crash_image (fst c) (snd c))) crash_cases
  = map (fun c => Recovered (expected_after_crash (fst c) (forallb (Nat.eqb 255) (snd c))))
        crash_cases.
Proof. vm_compute. reflexivity. Qed.

Definition is_refusal (o : Outcome) : bool :=
  match o with Recovered _ => false | _ => true end.

(* Generated: the low bit inverted in one byte of each field class the
   decoder reads in transaction 8's frames: the first payload's kind and
   value; the second payload's transaction, target and value; and the
   commit's kind, transaction, count, header padding, first tag byte, first
   entry's position and target, and last entry's last tag byte. Against an
   acknowledgement of one transaction, each is a refusal. *)
Definition field_offsets : list nat :=
  [0; 16] ++ [128 + 1; 128 + 2; 128 + 16]
  ++ [256 + 0; 256 + 1; 256 + 2; 256 + 3; 256 + 16; 256 + 32; 256 + 33; 256 + 32 + 2 * 18 - 1].

Example the_field_family_has_thirteen_members : length field_offsets = 13 := eq_refl.

Example inverting_a_field_s_low_bit_is_refused :
  forallb (fun o => is_refusal (decode bridge_layout bridge_open bridge_generation 1
                                        (flip_bit bridge_medium o)))
          field_offsets = true.
Proof. vm_compute. reflexivity. Qed.

Definition witness_Layout : Layout := bridge_layout.
Definition witness_Entry : Entry := {| entry_position := 0; entry_target := 1; entry_tag := [] |}.
Definition witness_Txn : Txn := {| txn_id := 8; txn_writes := [(1, 21); (2, 22)] |}.
Definition witness_Pending : Pending := pending_of 0 (frame_at bridge_layout bridge_medium 0).
