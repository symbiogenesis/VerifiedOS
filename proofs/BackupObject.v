(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   BackupObject.v

   Canonical wire formats, export boundary, restore state machine, and
   fresh-install initializer invariants for `RecoverySecret-v1` and
   `BackupObject-v1` (see
   [backup-migration.md](../docs/implementation/contracts/backup-migration.md)).

   Governing obligations:
   - Backup object and recovery secret wire formats (R-10-038, R-05-051a,
     R-05-051b): total serializers and parsers for `RecoverySecret-v1`
     (32 raw key bytes <-> exact 64 uppercase ASCII hex digits) and the
     `BackupObject-v1` descriptor family (`backup-envelope-v1`,
     `backup-plaintext-v1`, `backup-region-v1`, `backup-chunk-v1`,
     `backup-proof-v1`), with machine-checked round-trip and whole-language
     canonicity theorems rejecting trailing bytes, lowercase hex, alternate
     lengths, unsorted or duplicate region IDs, and non-contiguous chunks.
   - Export boundary and fresh-state exclusion (R-10-039): `ExportView`
     admits only `Rollbackable` regions whose schema is recursively `DataOnly`,
     excluding `Fresh`, `ConsentStore`, `KeyHandle`, `CredentialHandle`, and
     `SealedObject` regions by construction, while receiving `Fresh`
     initializers construct unenrolled post-restore scopes that deny stale or
     spent authority.
   - Non-vacuity and assumption hygiene (R-05-163, R-05-164, R-05-165,
     R-05-166): closed axiom-free proofs, closed witnesses for every carrier
     record, and concrete accepting and refusing boundary examples.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-051a R-05-051b R-05-163 R-05-164 R-05-165 R-05-166 R-10-038 R-10-039
   SHA256: 32157cacc617e31e2938927af1bfdbc5b5cc16040c12fdf32753fe3b5aa9c0bd
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Require Import ProofSupport.

Open Scope list_scope.

(* -------------------------------------------------------------------------
   Shared byte and fixed-width unsigned big-endian integer codecs.
   ------------------------------------------------------------------------- *)

Definition byte_ok (b : nat) : bool := Nat.ltb b 256.

Definition bytes_ok (bs : list nat) : bool := all_of byte_ok bs.

Fixpoint pow256 (w : nat) : nat :=
  match w with
  | 0 => 1
  | S k => 256 * pow256 k
  end.

Fixpoint fits_u_be (w n : nat) : bool :=
  match w with
  | 0 => Nat.eqb n 0
  | S k => fits_u_be k (n / 256)
  end.

Fixpoint le_digits_fixed (w n : nat) : list nat :=
  match w with
  | 0 => nil
  | S k => (n mod 256) :: le_digits_fixed k (n / 256)
  end.

Fixpoint le_val (ds : list nat) : nat :=
  match ds with
  | nil => 0
  | d :: rest => d + 256 * le_val rest
  end.

Definition write_u_be (w n : nat) : option (list nat) :=
  if fits_u_be w n then Some (rev (le_digits_fixed w n)) else None.

Fixpoint take_bytes (n : nat) (bs : list nat) : option (list nat * list nat) :=
  match n with
  | 0 => Some (nil, bs)
  | S k =>
      match bs with
      | nil => None
      | b :: rest =>
          match take_bytes k rest with
          | None => None
          | Some (front, back) => Some (b :: front, back)
          end
      end
  end.

Definition read_u_be (w : nat) (bs : list nat) : option (nat * list nat) :=
  match take_bytes w bs with
  | None => None
  | Some (ds, rest) =>
      if bytes_ok ds then Some (le_val (rev ds), rest) else None
  end.

Definition write_fixed_bytes (w : nat) (xs : list nat) : option (list nat) :=
  if andb (Nat.eqb (count_of xs) w) (bytes_ok xs) then Some xs else None.

Definition read_fixed_bytes (w : nat) (bs : list nat) : option (list nat * list nat) :=
  match take_bytes w bs with
  | None => None
  | Some (xs, rest) =>
      if bytes_ok xs then Some (xs, rest) else None
  end.

Lemma some_pair_eq : forall (A B : Type) (a c : A) (b d : B),
  Some (a, b) = Some (c, d) -> a = c /\ b = d.
Proof.
  intros A B a c b d H. injection H as H1 H2. split; assumption.
Qed.

Lemma count_of_cons : forall (A : Type) (x : A) (l : list A),
  count_of (x :: l) = S (count_of l).
Proof. intros A x l. reflexivity. Qed.

Lemma count_of_rev : forall (A : Type) (l : list A),
  count_of (rev l) = count_of l.
Proof.
  intros A l. induction l as [|x xs IH].
  - reflexivity.
  - simpl. rewrite count_of_app. rewrite IH. simpl. lia.
Qed.

Lemma bytes_ok_cons : forall x xs,
  bytes_ok (x :: xs) = andb (byte_ok x) (bytes_ok xs).
Proof. intros x xs. reflexivity. Qed.

Lemma bytes_ok_app : forall xs ys,
  bytes_ok (xs ++ ys) = andb (bytes_ok xs) (bytes_ok ys).
Proof.
  intros xs ys. unfold bytes_ok. apply all_of_app_eq.
Qed.

Lemma bytes_ok_rev : forall xs,
  bytes_ok (rev xs) = bytes_ok xs.
Proof.
  intros xs. induction xs as [|x r IH].
  - reflexivity.
  - simpl. rewrite bytes_ok_app. rewrite IH.
    unfold bytes_ok. simpl. rewrite andb_true_r. apply andb_comm.
Qed.

Lemma take_bytes_exact : forall xs ys,
  take_bytes (count_of xs) (xs ++ ys) = Some (xs, ys).
Proof.
  induction xs as [|x xs IH]; intros ys.
  - reflexivity.
  - rewrite count_of_cons. simpl. rewrite IH. reflexivity.
Qed.

Lemma take_bytes_split : forall n bs xs ys,
  take_bytes n bs = Some (xs, ys) -> bs = xs ++ ys /\ count_of xs = n.
Proof.
  induction n as [|k IH]; intros bs xs ys H.
  - simpl in H. destruct (some_pair_eq _ _ _ _ _ _ H) as [H1 H2].
    subst. split; reflexivity.
  - destruct bs as [|b rest]; [discriminate |].
    simpl in H. destruct (take_bytes k rest) as [[front back]|] eqn:E; [|discriminate].
    destruct (some_pair_eq _ _ _ _ _ _ H) as [H1 H2].
    destruct (IH rest front back E) as [Hb Hc].
    subst. split; [reflexivity | simpl; lia].
Qed.

Lemma le_digits_fixed_count : forall w n,
  count_of (le_digits_fixed w n) = w.
Proof.
  induction w as [|k IH]; intros n.
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.

Lemma le_digits_fixed_ok : forall w n,
  bytes_ok (le_digits_fixed w n) = true.
Proof.
  induction w as [|k IH]; intros n.
  - reflexivity.
  - cbn [le_digits_fixed]. rewrite bytes_ok_cons. unfold byte_ok.
    assert (Hm : Nat.ltb (n mod 256) 256 = true).
    { apply Nat.ltb_lt. apply Nat.mod_upper_bound. lia. }
    rewrite Hm. rewrite IH. reflexivity.
Qed.

Lemma le_val_le_digits_fixed : forall w n,
  n < pow256 w -> le_val (le_digits_fixed w n) = n.
Proof.
  induction w as [|k IH]; intros n Hlt.
  - cbn [pow256] in Hlt. cbn [le_digits_fixed le_val]. lia.
  - cbn [pow256] in Hlt. cbn [le_digits_fixed le_val].
    assert (Hq : n / 256 < pow256 k).
    { apply Nat.Div0.div_lt_upper_bound; lia. }
    rewrite (IH (n / 256) Hq).
    pose proof (Nat.div_mod_eq n 256) as Hd. lia.
Qed.

Lemma le_digits_fixed_le_val : forall ds w,
  count_of ds = w -> bytes_ok ds = true -> le_digits_fixed w (le_val ds) = ds.
Proof.
  induction ds as [|d rest IH]; intros w Hc Hok.
  - subst w. reflexivity.
  - destruct w as [|k]; [simpl in Hc; discriminate |].
    simpl in Hc. injection Hc as Hc.
    rewrite bytes_ok_cons in Hok. apply andb_split in Hok. destruct Hok as [Hd Hr].
    unfold byte_ok in Hd. apply Nat.ltb_lt in Hd.
    cbn [le_digits_fixed le_val].
    assert (Hmod : (d + 256 * le_val rest) mod 256 = d).
    { rewrite Nat.mul_comm. rewrite Nat.Div0.mod_add. apply Nat.mod_small. exact Hd. }
    assert (Hdiv : (d + 256 * le_val rest) / 256 = le_val rest).
    { rewrite Nat.mul_comm. rewrite Nat.div_add by lia.
      rewrite Nat.div_small by exact Hd. reflexivity. }
    rewrite Hmod, Hdiv. rewrite (IH k Hc Hr). reflexivity.
Qed.

Lemma le_val_lt_pow256 : forall ds w,
  count_of ds = w -> bytes_ok ds = true -> le_val ds < pow256 w.
Proof.
  induction ds as [|d rest IH]; intros w Hc Hok.
  - subst w. simpl. lia.
  - destruct w as [|k]; [simpl in Hc; discriminate |].
    simpl in Hc. injection Hc as Hc.
    rewrite bytes_ok_cons in Hok. apply andb_split in Hok. destruct Hok as [Hd Hr].
    unfold byte_ok in Hd. apply Nat.ltb_lt in Hd.
    pose proof (IH k Hc Hr) as Hrest.
    simpl. lia.
Qed.

Lemma fits_u_be_lt : forall w n,
  fits_u_be w n = true -> n < pow256 w.
Proof.
  induction w as [|k IH]; intros n H.
  - cbn [fits_u_be] in H. apply nat_eqb_true in H. subst n. cbn [pow256]. lia.
  - cbn [fits_u_be] in H. cbn [pow256].
    pose proof (IH (n / 256) H) as Hq.
    pose proof (Nat.div_mod_eq n 256) as Hd.
    pose proof (Nat.mod_upper_bound n 256 ltac:(lia)) as Hm.
    lia.
Qed.

Lemma lt_fits_u_be : forall w n,
  n < pow256 w -> fits_u_be w n = true.
Proof.
  induction w as [|k IH]; intros n H.
  - cbn [pow256] in H. cbn [fits_u_be]. apply Nat.eqb_eq. lia.
  - cbn [pow256] in H. cbn [fits_u_be].
    apply IH. apply Nat.Div0.div_lt_upper_bound; lia.
Qed.

Lemma write_u_be_length : forall w n enc,
  write_u_be w n = Some enc -> count_of enc = w.
Proof.
  intros w n enc H. unfold write_u_be in H.
  destruct (fits_u_be w n); [|discriminate].
  injection H as H. subst enc.
  rewrite count_of_rev. apply le_digits_fixed_count.
Qed.

Lemma write_u_be_ok : forall w n enc,
  write_u_be w n = Some enc -> bytes_ok enc = true.
Proof.
  intros w n enc H. unfold write_u_be in H.
  destruct (fits_u_be w n); [|discriminate].
  injection H as H. subst enc.
  rewrite bytes_ok_rev. apply le_digits_fixed_ok.
Qed.

Lemma read_write_u_be : forall w n enc back,
  write_u_be w n = Some enc ->
  read_u_be w (enc ++ back) = Some (n, back).
Proof.
  intros w n enc back Hw. unfold write_u_be in Hw.
  destruct (fits_u_be w n) eqn:Hlt; [|discriminate].
  injection Hw as Hw. subst enc.
  unfold read_u_be.
  pose proof (le_digits_fixed_count w n) as Hc.
  rewrite <- (count_of_rev _ (le_digits_fixed w n)) in Hc.
  rewrite <- Hc at 1. rewrite take_bytes_exact.
  rewrite bytes_ok_rev. rewrite le_digits_fixed_ok.
  rewrite rev_involutive.
  apply fits_u_be_lt in Hlt. rewrite (le_val_le_digits_fixed w n Hlt).
  reflexivity.
Qed.

Lemma write_read_u_be : forall w bs n back,
  read_u_be w bs = Some (n, back) ->
  exists enc, bs = enc ++ back /\ write_u_be w n = Some enc.
Proof.
  intros w bs n back H. unfold read_u_be in H.
  destruct (take_bytes w bs) as [[ds rest]|] eqn:ET; [|discriminate].
  destruct (bytes_ok ds) eqn:EB; [|discriminate].
  destruct (some_pair_eq _ _ _ _ _ _ H) as [Hv Hb].
  destruct (take_bytes_split w bs ds rest ET) as [Hs Hc].
  exists ds. split; [subst; reflexivity |].
  unfold write_u_be.
  assert (Hrc : count_of (rev ds) = w) by (rewrite count_of_rev; exact Hc).
  assert (Hrok : bytes_ok (rev ds) = true) by (rewrite bytes_ok_rev; exact EB).
  subst n.
  pose proof (le_val_lt_pow256 (rev ds) w Hrc Hrok) as Hlt.
  apply lt_fits_u_be in Hlt. rewrite Hlt.
  rewrite (le_digits_fixed_le_val (rev ds) w Hrc Hrok).
  rewrite rev_involutive. reflexivity.
Qed.

Lemma read_write_fixed_bytes : forall w xs enc back,
  write_fixed_bytes w xs = Some enc ->
  read_fixed_bytes w (enc ++ back) = Some (xs, back).
Proof.
  intros w xs enc back Hw. unfold write_fixed_bytes in Hw.
  destruct (andb (Nat.eqb (count_of xs) w) (bytes_ok xs)) eqn:E; [|discriminate].
  apply andb_split in E. destruct E as [Ec Eok].
  apply nat_eqb_true in Ec. injection Hw as Hw. subst enc.
  unfold read_fixed_bytes. rewrite <- Ec. rewrite take_bytes_exact.
  rewrite Eok. reflexivity.
Qed.

Lemma write_read_fixed_bytes : forall w bs xs back,
  read_fixed_bytes w bs = Some (xs, back) ->
  exists enc, bs = enc ++ back /\ write_fixed_bytes w xs = Some enc.
Proof.
  intros w bs xs back H. unfold read_fixed_bytes in H.
  destruct (take_bytes w bs) as [[ds rest]|] eqn:ET; [|discriminate].
  destruct (bytes_ok ds) eqn:EB; [|discriminate].
  destruct (some_pair_eq _ _ _ _ _ _ H) as [Hx Hb].
  destruct (take_bytes_split w bs ds rest ET) as [Hs Hc].
  exists ds. split; [subst; reflexivity |].
  unfold write_fixed_bytes. subst xs.
  rewrite Hc. rewrite nat_eqb_refl. rewrite EB. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   RecoverySecret-v1: 32 key bytes <-> exact 64 uppercase ASCII hex digits.
   ------------------------------------------------------------------------- *)

Record RecoverySecret : Type := {
  rs_bytes : list nat
}.

Definition rs_wf (rs : RecoverySecret) : bool :=
  andb (Nat.eqb (count_of (rs_bytes rs)) 32) (bytes_ok (rs_bytes rs)).

Definition encode_nibble_upper (n : nat) : nat :=
  if Nat.ltb n 10 then 48 + n else 55 + n.

Definition decode_nibble_upper (c : nat) : option nat :=
  if andb (Nat.leb 48 c) (Nat.leb c 57) then Some (c - 48)
  else if andb (Nat.leb 65 c) (Nat.leb c 70) then Some (c - 55)
  else None.

Lemma decode_encode_nibble_upper : forall n,
  n < 16 -> decode_nibble_upper (encode_nibble_upper n) = Some n.
Proof.
  intros n Hlt. unfold encode_nibble_upper, decode_nibble_upper.
  destruct (Nat.ltb n 10) eqn:E.
  - apply Nat.ltb_lt in E.
    assert (H1 : Nat.leb 48 (48 + n) = true) by (apply Nat.leb_le; lia).
    assert (H2 : Nat.leb (48 + n) 57 = true) by (apply Nat.leb_le; lia).
    rewrite H1, H2. simpl. f_equal. lia.
  - apply Nat.ltb_ge in E.
    assert (H1 : Nat.leb (55 + n) 57 = false) by (apply Nat.leb_gt; lia).
    assert (H2 : Nat.leb 65 (55 + n) = true) by (apply Nat.leb_le; lia).
    assert (H3 : Nat.leb (55 + n) 70 = true) by (apply Nat.leb_le; lia).
    rewrite H1, H2, H3. rewrite andb_false_r. simpl. f_equal. lia.
Qed.

Lemma encode_decode_nibble_upper : forall c n,
  decode_nibble_upper c = Some n -> encode_nibble_upper n = c /\ n < 16.
Proof.
  intros c n H. unfold decode_nibble_upper in H.
  destruct (andb (Nat.leb 48 c) (Nat.leb c 57)) eqn:E1.
  - apply andb_split in E1. destruct E1 as [Ha Hb].
    apply Nat.leb_le in Ha. apply Nat.leb_le in Hb.
    injection H as H. subst n.
    unfold encode_nibble_upper.
    assert (Hl : Nat.ltb (c - 48) 10 = true) by (apply Nat.ltb_lt; lia).
    rewrite Hl. split; lia.
  - destruct (andb (Nat.leb 65 c) (Nat.leb c 70)) eqn:E2; [|discriminate].
    apply andb_split in E2. destruct E2 as [Ha Hb].
    apply Nat.leb_le in Ha. apply Nat.leb_le in Hb.
    injection H as H. subst n.
    unfold encode_nibble_upper.
    assert (Hl : Nat.ltb (c - 55) 10 = false) by (apply Nat.ltb_ge; lia).
    rewrite Hl. split; lia.
Qed.

Fixpoint encode_hex_bytes (bs : list nat) : list nat :=
  match bs with
  | nil => nil
  | b :: rest =>
      encode_nibble_upper (b / 16) ::
      encode_nibble_upper (b mod 16) ::
      encode_hex_bytes rest
  end.

Fixpoint decode_hex_bytes (cs : list nat) : option (list nat) :=
  match cs with
  | nil => Some nil
  | hi :: lo :: rest =>
      match decode_nibble_upper hi, decode_nibble_upper lo, decode_hex_bytes rest with
      | Some h, Some l, Some bs => Some ((h * 16 + l) :: bs)
      | _, _, _ => None
      end
  | _ :: nil => None
  end.

Lemma encode_hex_bytes_count : forall bs,
  count_of (encode_hex_bytes bs) = 2 * count_of bs.
Proof.
  induction bs as [|b rest IH].
  - reflexivity.
  - simpl. rewrite IH. lia.
Qed.

Lemma decode_hex_bytes_encode : forall bs,
  bytes_ok bs = true -> decode_hex_bytes (encode_hex_bytes bs) = Some bs.
Proof.
  induction bs as [|b rest IH]; intros Hok.
  - reflexivity.
  - rewrite bytes_ok_cons in Hok. apply andb_split in Hok. destruct Hok as [Hb Hr].
    unfold byte_ok in Hb. apply Nat.ltb_lt in Hb.
    assert (Hhi : b / 16 < 16) by (apply Nat.Div0.div_lt_upper_bound; lia).
    assert (Hlo : b mod 16 < 16) by (apply Nat.mod_upper_bound; lia).
    cbn [encode_hex_bytes decode_hex_bytes]. rewrite (decode_encode_nibble_upper (b / 16) Hhi).
    rewrite (decode_encode_nibble_upper (b mod 16) Hlo).
    rewrite (IH Hr).
    f_equal. f_equal. pose proof (Nat.div_mod_eq b 16) as Hd. lia.
Qed.

Fixpoint decode_hex_pairs (n : nat) (cs : list nat) : option (list nat) :=
  match n with
  | 0 => match cs with nil => Some nil | _ :: _ => None end
  | S k =>
      match cs with
      | hi :: lo :: rest =>
          match decode_nibble_upper hi, decode_nibble_upper lo, decode_hex_pairs k rest with
          | Some h, Some l, Some bs => Some ((h * 16 + l) :: bs)
          | _, _, _ => None
          end
      | _ => None
      end
  end.

Lemma decode_hex_pairs_encode : forall bs,
  bytes_ok bs = true ->
  decode_hex_pairs (count_of bs) (encode_hex_bytes bs) = Some bs.
Proof.
  induction bs as [|b rest IH]; intros Hok.
  - reflexivity.
  - rewrite bytes_ok_cons in Hok. apply andb_split in Hok. destruct Hok as [Hb Hr].
    unfold byte_ok in Hb. apply Nat.ltb_lt in Hb.
    assert (Hhi : b / 16 < 16) by (apply Nat.Div0.div_lt_upper_bound; lia).
    assert (Hlo : b mod 16 < 16) by (apply Nat.mod_upper_bound; lia).
    cbn [count_of encode_hex_bytes decode_hex_pairs]. rewrite (decode_encode_nibble_upper (b / 16) Hhi).
    rewrite (decode_encode_nibble_upper (b mod 16) Hlo).
    rewrite (IH Hr).
    f_equal. f_equal. pose proof (Nat.div_mod_eq b 16) as Hd. lia.
Qed.

Lemma encode_decode_hex_pairs : forall n cs bs,
  decode_hex_pairs n cs = Some bs ->
  encode_hex_bytes bs = cs /\ count_of bs = n /\ bytes_ok bs = true.
Proof.
  induction n as [|k IH]; intros cs bs H.
  - destruct cs as [|x xs]; [|discriminate].
    simpl in H. injection H as H. subst bs. repeat split; reflexivity.
  - destruct cs as [|hi [|lo rest]]; [discriminate | discriminate |].
    simpl in H.
    destruct (decode_nibble_upper hi) as [h|] eqn:E1; [|discriminate].
    destruct (decode_nibble_upper lo) as [l|] eqn:E2; [|discriminate].
    destruct (decode_hex_pairs k rest) as [bs'|] eqn:E3; [|discriminate].
    injection H as H. subst bs.
    destruct (encode_decode_nibble_upper hi h E1) as [Heh Hhl].
    destruct (encode_decode_nibble_upper lo l E2) as [Hel Hll].
    destruct (IH rest bs' E3) as [Henc [Hcnt Hok]].
    assert (Hbyte : h * 16 + l < 256) by lia.
    assert (Hdiv : (h * 16 + l) / 16 = h).
    { rewrite Nat.div_add_l by lia. rewrite Nat.div_small by exact Hll. lia. }
    assert (Hmod : (h * 16 + l) mod 16 = l).
    { rewrite Nat.add_comm. rewrite Nat.Div0.mod_add.
      apply Nat.mod_small. exact Hll. }
    repeat split.
    + cbn [encode_hex_bytes]. rewrite Hdiv, Hmod, Heh, Hel, Henc. reflexivity.
    + simpl. lia.
    + rewrite bytes_ok_cons. unfold byte_ok.
      assert (Hltb : Nat.ltb (h * 16 + l) 256 = true) by (apply Nat.ltb_lt; exact Hbyte).
      rewrite Hltb, Hok. reflexivity.
Qed.

Definition encode_recovery_secret (rs : RecoverySecret) : option (list nat) :=
  if rs_wf rs then Some (encode_hex_bytes (rs_bytes rs)) else None.

Definition decode_recovery_secret (cs : list nat) : option RecoverySecret :=
  if Nat.eqb (count_of cs) 64 then
    match decode_hex_pairs 32 cs with
    | Some bs => Some {| rs_bytes := bs |}
    | None => None
    end
  else None.

(*| discharges: R-10-038 |*)
Theorem recovery_secret_encode_length : forall rs cs,
  encode_recovery_secret rs = Some cs -> count_of cs = 64.
Proof.
  intros rs cs H. unfold encode_recovery_secret in H.
  destruct (rs_wf rs) eqn:E; [|discriminate].
  unfold rs_wf in E. apply andb_split in E. destruct E as [Hc _].
  apply nat_eqb_true in Hc. injection H as H. subst cs.
  rewrite encode_hex_bytes_count, Hc. reflexivity.
Qed.

(*| discharges: R-05-051a |*)
Theorem recovery_secret_decode_of_encode : forall rs cs,
  encode_recovery_secret rs = Some cs -> decode_recovery_secret cs = Some rs.
Proof.
  intros rs cs H. unfold encode_recovery_secret in H.
  destruct (rs_wf rs) eqn:E; [|discriminate].
  unfold rs_wf in E. apply andb_split in E. destruct E as [Hc Hok].
  apply nat_eqb_true in Hc. injection H as H. subst cs.
  unfold decode_recovery_secret.
  rewrite encode_hex_bytes_count, Hc.
  change (Nat.eqb (2 * 32) 64) with true.
  rewrite <- Hc. rewrite (decode_hex_pairs_encode (rs_bytes rs) Hok).
  destruct rs. reflexivity.
Qed.

(*| discharges: R-05-051a, R-05-051b |*)
Theorem recovery_secret_encode_of_decode : forall cs rs,
  decode_recovery_secret cs = Some rs -> encode_recovery_secret rs = Some cs.
Proof.
  intros cs rs H. unfold decode_recovery_secret in H.
  destruct (Nat.eqb (count_of cs) 64); [|discriminate].
  destruct (decode_hex_pairs 32 cs) as [bs|] eqn:E; [|discriminate].
  injection H as H. subst rs.
  destruct (encode_decode_hex_pairs 32 cs bs E) as [Henc [Hc Hok]].
  unfold encode_recovery_secret, rs_wf. simpl.
  rewrite Hc. rewrite nat_eqb_refl. rewrite Hok. simpl.
  rewrite Henc. reflexivity.
Qed.

(*| discharges: R-05-051a |*)
Theorem recovery_secret_canonicity : forall cs1 cs2 rs,
  decode_recovery_secret cs1 = Some rs ->
  decode_recovery_secret cs2 = Some rs ->
  cs1 = cs2.
Proof.
  intros cs1 cs2 rs H1 H2.
  pose proof (recovery_secret_encode_of_decode cs1 rs H1) as E1.
  pose proof (recovery_secret_encode_of_decode cs2 rs H2) as E2.
  congruence.
Qed.

Theorem recovery_secret_encode_injective : forall rs1 rs2 cs,
  encode_recovery_secret rs1 = Some cs ->
  encode_recovery_secret rs2 = Some cs ->
  rs1 = rs2.
Proof.
  intros rs1 rs2 cs H1 H2.
  pose proof (recovery_secret_decode_of_encode rs1 cs H1) as D1.
  pose proof (recovery_secret_decode_of_encode rs2 cs H2) as D2.
  congruence.
Qed.

(*| discharges: R-05-051b |*)
Theorem recovery_secret_refuses_trailing_bytes : forall rs cs extra,
  encode_recovery_secret rs = Some cs -> extra <> nil ->
  decode_recovery_secret (cs ++ extra) = None.
Proof.
  intros rs cs extra Henc Hne.
  pose proof (recovery_secret_encode_length rs cs Henc) as Hlen.
  unfold decode_recovery_secret.
  rewrite count_of_app, Hlen.
  assert (Hneq : Nat.eqb (64 + count_of extra) 64 = false).
  { destruct extra as [|x xs]; [contradiction |].
    cbn [count_of]. apply Nat.eqb_neq. lia. }
  rewrite Hneq. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   BackupObject-v1 profile and region/plaintext/proof/chunk/envelope records.
   ------------------------------------------------------------------------- *)

Record BackupProfile : Type := {
  bp_magic : list nat;
  bp_version : nat;
  bp_profile_id : nat;
  bp_chunk_size : nat;
  bp_max_regions : nat;
  bp_max_chunks : nat;
  bp_digest_bytes : nat;
  bp_nonce_bytes : nat;
  bp_tag_bytes : nat
}.

Definition every (xs : list bool) : bool := all_of (fun b => b) xs.

Definition backup_profile_wf (p : BackupProfile) : bool :=
  every (Nat.eqb (count_of (bp_magic p)) 8 ::
         bytes_ok (bp_magic p) ::
         fits_u_be 4 (bp_version p) ::
         fits_u_be 4 (bp_profile_id p) ::
         Nat.ltb 0 (bp_chunk_size p) ::
         fits_u_be 4 (bp_chunk_size p) ::
         fits_u_be 4 (bp_max_regions p) ::
         fits_u_be 4 (bp_max_chunks p) ::
         Nat.eqb (bp_digest_bytes p) 32 ::
         Nat.eqb (bp_nonce_bytes p) 12 ::
         Nat.eqb (bp_tag_bytes p) 16 :: nil).

Record BackupRegion : Type := {
  br_region_id : nat;
  br_schema_id : nat;
  br_schema_gen : nat;
  br_payload_len : nat;
  br_first_chunk : nat;
  br_chunk_count : nat
}.

Definition region_wf (r : BackupRegion) : bool :=
  every (fits_u_be 4 (br_region_id r) ::
         fits_u_be 4 (br_schema_id r) ::
         fits_u_be 4 (br_schema_gen r) ::
         fits_u_be 8 (br_payload_len r) ::
         fits_u_be 4 (br_first_chunk r) ::
         fits_u_be 4 (br_chunk_count r) :: nil).

Definition write_region (r : BackupRegion) : option (list nat) :=
  match write_u_be 4 (br_region_id r),
        write_u_be 4 (br_schema_id r),
        write_u_be 4 (br_schema_gen r),
        write_u_be 8 (br_payload_len r),
        write_u_be 4 (br_first_chunk r),
        write_u_be 4 (br_chunk_count r) with
  | Some b1, Some b2, Some b3, Some b4, Some b5, Some b6 =>
      Some (b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6)
  | _, _, _, _, _, _ => None
  end.

Definition read_region (bs : list nat) : option (BackupRegion * list nat) :=
  match read_u_be 4 bs with
  | None => None
  | Some (rid, r1) =>
      match read_u_be 4 r1 with
      | None => None
      | Some (sid, r2) =>
          match read_u_be 4 r2 with
          | None => None
          | Some (sgen, r3) =>
              match read_u_be 8 r3 with
              | None => None
              | Some (plen, r4) =>
                  match read_u_be 4 r4 with
                  | None => None
                  | Some (fc, r5) =>
                      match read_u_be 4 r5 with
                      | None => None
                      | Some (cc, back) =>
                          Some ({| br_region_id := rid;
                                   br_schema_id := sid;
                                   br_schema_gen := sgen;
                                   br_payload_len := plen;
                                   br_first_chunk := fc;
                                   br_chunk_count := cc |}, back)
                      end
                  end
              end
          end
      end
  end.

Lemma read_write_region : forall r enc back,
  write_region r = Some enc ->
  read_region (enc ++ back) = Some (r, back).
Proof.
  intros r enc back H. unfold write_region in H.
  destruct (write_u_be 4 (br_region_id r)) as [b1|] eqn:E1; [|discriminate].
  destruct (write_u_be 4 (br_schema_id r)) as [b2|] eqn:E2; [|discriminate].
  destruct (write_u_be 4 (br_schema_gen r)) as [b3|] eqn:E3; [|discriminate].
  destruct (write_u_be 8 (br_payload_len r)) as [b4|] eqn:E4; [|discriminate].
  destruct (write_u_be 4 (br_first_chunk r)) as [b5|] eqn:E5; [|discriminate].
  destruct (write_u_be 4 (br_chunk_count r)) as [b6|] eqn:E6; [|discriminate].
  injection H as H. subst enc.
  unfold read_region.
  repeat rewrite <- app_assoc.
  rewrite (read_write_u_be 4 (br_region_id r) b1 _ E1).
  rewrite (read_write_u_be 4 (br_schema_id r) b2 _ E2).
  rewrite (read_write_u_be 4 (br_schema_gen r) b3 _ E3).
  rewrite (read_write_u_be 8 (br_payload_len r) b4 _ E4).
  rewrite (read_write_u_be 4 (br_first_chunk r) b5 _ E5).
  rewrite (read_write_u_be 4 (br_chunk_count r) b6 back E6).
  destruct r. reflexivity.
Qed.

Lemma write_read_region : forall bs r back,
  read_region bs = Some (r, back) ->
  exists enc, bs = enc ++ back /\ write_region r = Some enc.
Proof.
  intros bs r back H. unfold read_region in H.
  destruct (read_u_be 4 bs) as [[rid r1]|] eqn:E1; [|discriminate].
  destruct (read_u_be 4 r1) as [[sid r2]|] eqn:E2; [|discriminate].
  destruct (read_u_be 4 r2) as [[sgen r3]|] eqn:E3; [|discriminate].
  destruct (read_u_be 8 r3) as [[plen r4]|] eqn:E4; [|discriminate].
  destruct (read_u_be 4 r4) as [[fc r5]|] eqn:E5; [|discriminate].
  destruct (read_u_be 4 r5) as [[cc tail]|] eqn:E6; [|discriminate].
  destruct (some_pair_eq _ _ _ _ _ _ H) as [Hr Hb]. subst r tail.
  destruct (write_read_u_be 4 bs rid r1 E1) as [b1 [Hb1 Hw1]].
  destruct (write_read_u_be 4 r1 sid r2 E2) as [b2 [Hb2 Hw2]].
  destruct (write_read_u_be 4 r2 sgen r3 E3) as [b3 [Hb3 Hw3]].
  destruct (write_read_u_be 8 r3 plen r4 E4) as [b4 [Hb4 Hw4]].
  destruct (write_read_u_be 4 r4 fc r5 E5) as [b5 [Hb5 Hw5]].
  destruct (write_read_u_be 4 r5 cc back E6) as [b6 [Hb6 Hw6]].
  exists (b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6). split.
  - subst. repeat rewrite <- app_assoc. reflexivity.
  - unfold write_region. simpl. rewrite Hw1, Hw2, Hw3, Hw4, Hw5, Hw6. reflexivity.
Qed.

Fixpoint write_regions (rs : list BackupRegion) : option (list nat) :=
  match rs with
  | nil => Some nil
  | r :: rest =>
      match write_region r, write_regions rest with
      | Some b1, Some b2 => Some (b1 ++ b2)
      | _, _ => None
      end
  end.

Fixpoint read_regions (k : nat) (bs : list nat) : option (list BackupRegion * list nat) :=
  match k with
  | 0 => Some (nil, bs)
  | S j =>
      match read_region bs with
      | None => None
      | Some (r, rest) =>
          match read_regions j rest with
          | None => None
          | Some (rs, back) => Some (r :: rs, back)
          end
      end
  end.

Lemma read_write_regions : forall rs enc back,
  write_regions rs = Some enc ->
  read_regions (count_of rs) (enc ++ back) = Some (rs, back).
Proof.
  induction rs as [|r rest IH]; intros enc back H.
  - simpl in H. injection H as H. subst enc. reflexivity.
  - simpl in H.
    destruct (write_region r) as [b1|] eqn:E1; [|discriminate].
    destruct (write_regions rest) as [b2|] eqn:E2; [|discriminate].
    injection H as H. subst enc.
    rewrite count_of_cons. simpl. rewrite <- app_assoc.
    rewrite (read_write_region r b1 (b2 ++ back) E1).
    rewrite (IH b2 back eq_refl). reflexivity.
Qed.

Lemma write_read_regions : forall k bs rs back,
  read_regions k bs = Some (rs, back) ->
  exists enc, bs = enc ++ back /\ write_regions rs = Some enc /\ count_of rs = k.
Proof.
  induction k as [|j IH]; intros bs rs back H.
  - simpl in H. destruct (some_pair_eq _ _ _ _ _ _ H) as [H1 H2].
    subst. exists nil. repeat split; reflexivity.
  - simpl in H.
    destruct (read_region bs) as [[r rest]|] eqn:E1; [|discriminate].
    destruct (read_regions j rest) as [[rs' tail]|] eqn:E2; [|discriminate].
    destruct (some_pair_eq _ _ _ _ _ _ H) as [H1 H2]. subst.
    destruct (write_read_region bs r rest E1) as [b1 [Hb1 Hw1]].
    destruct (IH rest rs' back E2) as [b2 [Hb2 [Hw2 Hc2]]].
    exists (b1 ++ b2). repeat split.
    + subst. rewrite <- app_assoc. reflexivity.
    + simpl. rewrite Hw1, Hw2. reflexivity.
    + simpl. lia.
Qed.

Definition region_coverage_ok (chunk_size : nat) (r : BackupRegion) : bool :=
  if Nat.eqb (br_payload_len r) 0 then Nat.eqb (br_chunk_count r) 0
  else andb (Nat.ltb 0 (br_chunk_count r))
            (andb (Nat.ltb ((br_chunk_count r - 1) * chunk_size) (br_payload_len r))
                  (Nat.leb (br_payload_len r) (br_chunk_count r * chunk_size))).

Fixpoint region_catalog_wf_aux (chunk_size prev_id next_chunk : nat)
    (has_prev : bool) (rs : list BackupRegion) (total_chunks : nat) : bool :=
  match rs with
  | nil => Nat.eqb next_chunk total_chunks
  | r :: rest =>
      andb (if has_prev then Nat.ltb prev_id (br_region_id r) else true)
           (andb (Nat.eqb (br_first_chunk r) next_chunk)
                 (andb (region_coverage_ok chunk_size r)
                       (region_catalog_wf_aux chunk_size (br_region_id r)
                          (next_chunk + br_chunk_count r) true rest total_chunks)))
  end.

Definition region_catalog_wf (chunk_size total_chunks : nat) (rs : list BackupRegion) : bool :=
  region_catalog_wf_aux chunk_size 0 0 false rs total_chunks.

Record BackupPlaintext : Type := {
  pt_export_gen : nat;
  pt_source_profile : nat;
  pt_regions : list BackupRegion;
  pt_chunk_size : nat;
  pt_chunk_count : nat;
  pt_merkle_root : list nat
}.

Definition plaintext_wf (p : BackupProfile) (pt : BackupPlaintext) : bool :=
  every (backup_profile_wf p ::
         fits_u_be 8 (pt_export_gen pt) ::
         fits_u_be 4 (pt_source_profile pt) ::
         Nat.leb (count_of (pt_regions pt)) (bp_max_regions p) ::
         Nat.eqb (pt_chunk_size pt) (bp_chunk_size p) ::
         Nat.leb (pt_chunk_count pt) (bp_max_chunks p) ::
         region_catalog_wf (pt_chunk_size pt) (pt_chunk_count pt) (pt_regions pt) ::
         Nat.eqb (count_of (pt_merkle_root pt)) (bp_digest_bytes p) ::
         bytes_ok (pt_merkle_root pt) :: nil).

Definition write_plaintext (p : BackupProfile) (pt : BackupPlaintext) : option (list nat) :=
  if plaintext_wf p pt then
    match write_u_be 8 (pt_export_gen pt),
          write_u_be 4 (pt_source_profile pt),
          write_u_be 4 (count_of (pt_regions pt)),
          write_regions (pt_regions pt),
          write_u_be 4 (pt_chunk_size pt),
          write_u_be 4 (pt_chunk_count pt),
          write_fixed_bytes (bp_digest_bytes p) (pt_merkle_root pt) with
    | Some b1, Some b2, Some b3, Some b4, Some b5, Some b6, Some b7 =>
        Some (b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6 ++ b7)
    | _, _, _, _, _, _, _ => None
    end
  else None.

Definition read_plaintext (p : BackupProfile) (bs : list nat) : option BackupPlaintext :=
  if backup_profile_wf p then
    match read_u_be 8 bs with
    | None => None
    | Some (egen, r1) =>
        match read_u_be 4 r1 with
        | None => None
        | Some (sprof, r2) =>
            match read_u_be 4 r2 with
            | None => None
            | Some (rcnt, r3) =>
                if Nat.leb rcnt (bp_max_regions p) then
                  match read_regions rcnt r3 with
                  | None => None
                  | Some (regs, r4) =>
                      match read_u_be 4 r4 with
                      | None => None
                      | Some (csize, r5) =>
                          match read_u_be 4 r5 with
                          | None => None
                          | Some (ccnt, r6) =>
                              match read_fixed_bytes (bp_digest_bytes p) r6 with
                              | Some (mroot, nil) =>
                                  let cand := {| pt_export_gen := egen;
                                                 pt_source_profile := sprof;
                                                 pt_regions := regs;
                                                 pt_chunk_size := csize;
                                                 pt_chunk_count := ccnt;
                                                 pt_merkle_root := mroot |} in
                                  if plaintext_wf p cand then Some cand else None
                              | _ => None
                              end
                          end
                      end
                  end
                else None
            end
        end
    end
  else None.

Lemma every_cons : forall x xs,
  every (x :: xs) = andb x (every xs).
Proof. intros x xs. reflexivity. Qed.

Lemma backup_profile_wf_bounds : forall p,
  backup_profile_wf p = true ->
  count_of (bp_magic p) = 8 /\
  bytes_ok (bp_magic p) = true /\
  bp_version p < pow256 4 /\
  bp_profile_id p < pow256 4 /\
  0 < bp_chunk_size p /\
  bp_chunk_size p < pow256 4 /\
  bp_max_regions p < pow256 4 /\
  bp_max_chunks p < pow256 4 /\
  bp_digest_bytes p = 32 /\
  bp_nonce_bytes p = 12 /\
  bp_tag_bytes p = 16.
Proof.
  intros p H. unfold backup_profile_wf in H.
  repeat (rewrite every_cons in H; apply andb_split in H; destruct H as [? H]).
  apply nat_eqb_true in H0.
  apply fits_u_be_lt in H2, H3, H5, H6, H7.
  apply Nat.ltb_lt in H4.
  apply nat_eqb_true in H8, H9, H10.
  repeat split; assumption.
Qed.

Lemma plaintext_wf_profile : forall p pt,
  plaintext_wf p pt = true -> backup_profile_wf p = true.
Proof.
  intros p pt H. unfold plaintext_wf in H.
  rewrite every_cons in H. apply andb_split in H. destruct H as [Hp _]. exact Hp.
Qed.

(*| discharges: R-05-051a |*)
Theorem plaintext_parse_of_serialize : forall p pt enc,
  write_plaintext p pt = Some enc ->
  read_plaintext p enc = Some pt.
Proof.
  intros p pt enc Hw. unfold write_plaintext in Hw.
  destruct (plaintext_wf p pt) eqn:Hwf; [|discriminate].
  destruct (write_u_be 8 (pt_export_gen pt)) as [b1|] eqn:E1; [|discriminate].
  destruct (write_u_be 4 (pt_source_profile pt)) as [b2|] eqn:E2; [|discriminate].
  destruct (write_u_be 4 (count_of (pt_regions pt))) as [b3|] eqn:E3; [|discriminate].
  destruct (write_regions (pt_regions pt)) as [b4|] eqn:E4; [|discriminate].
  destruct (write_u_be 4 (pt_chunk_size pt)) as [b5|] eqn:E5; [|discriminate].
  destruct (write_u_be 4 (pt_chunk_count pt)) as [b6|] eqn:E6; [|discriminate].
  destruct (write_fixed_bytes (bp_digest_bytes p) (pt_merkle_root pt)) as [b7|] eqn:E7;
    [|discriminate].
  injection Hw as Hw. subst enc.
  unfold read_plaintext. rewrite (plaintext_wf_profile p pt Hwf).
  repeat rewrite <- app_assoc.
  rewrite (read_write_u_be 8 _ b1 _ E1).
  rewrite (read_write_u_be 4 _ b2 _ E2).
  rewrite (read_write_u_be 4 _ b3 _ E3).
  assert (Hmr : Nat.leb (count_of (pt_regions pt)) (bp_max_regions p) = true).
  { unfold plaintext_wf in Hwf.
    do 3 (rewrite every_cons in Hwf; apply andb_split in Hwf; destruct Hwf as [_ Hwf]).
    rewrite every_cons in Hwf. apply andb_split in Hwf. destruct Hwf as [Hr _]. exact Hr. }
  rewrite Hmr.
  rewrite (read_write_regions (pt_regions pt) b4 _ E4).
  rewrite (read_write_u_be 4 _ b5 _ E5).
  rewrite (read_write_u_be 4 _ b6 _ E6).
  rewrite <- (app_nil_r b7) at 1.
  rewrite (read_write_fixed_bytes (bp_digest_bytes p) _ b7 nil E7).
  destruct pt. simpl in *. rewrite Hwf. reflexivity.
Qed.

(*| discharges: R-05-051a, R-05-051b |*)
Theorem plaintext_serialize_of_parse : forall p bs pt,
  read_plaintext p bs = Some pt ->
  write_plaintext p pt = Some bs.
Proof.
  intros p bs pt H. unfold read_plaintext in H.
  destruct (backup_profile_wf p) eqn:Hp; [|discriminate].
  destruct (read_u_be 8 bs) as [[egen r1]|] eqn:E1; [|discriminate].
  destruct (read_u_be 4 r1) as [[sprof r2]|] eqn:E2; [|discriminate].
  destruct (read_u_be 4 r2) as [[rcnt r3]|] eqn:E3; [|discriminate].
  destruct (Nat.leb rcnt (bp_max_regions p)) eqn:EL; [|discriminate].
  destruct (read_regions rcnt r3) as [[regs r4]|] eqn:E4; [|discriminate].
  destruct (read_u_be 4 r4) as [[csize r5]|] eqn:E5; [|discriminate].
  destruct (read_u_be 4 r5) as [[ccnt r6]|] eqn:E6; [|discriminate].
  destruct (read_fixed_bytes (bp_digest_bytes p) r6) as [[mroot tail]|] eqn:E7;
    [|discriminate].
  destruct tail as [|x xs]; [|discriminate].
  destruct (plaintext_wf p _) eqn:Hwf; [|discriminate].
  injection H as H. subst pt.
  destruct (write_read_u_be 8 bs egen r1 E1) as [b1 [Hb1 Hw1]].
  destruct (write_read_u_be 4 r1 sprof r2 E2) as [b2 [Hb2 Hw2]].
  destruct (write_read_u_be 4 r2 rcnt r3 E3) as [b3 [Hb3 Hw3]].
  destruct (write_read_regions rcnt r3 regs r4 E4) as [b4 [Hb4 [Hw4 Hc4]]].
  destruct (write_read_u_be 4 r4 csize r5 E5) as [b5 [Hb5 Hw5]].
  destruct (write_read_u_be 4 r5 ccnt r6 E6) as [b6 [Hb6 Hw6]].
  destruct (write_read_fixed_bytes (bp_digest_bytes p) r6 mroot nil E7)
    as [b7 [Hb7 Hw7]].
  rewrite app_nil_r in Hb7.
  unfold write_plaintext. rewrite Hwf. simpl.
  rewrite Hw1, Hw2, Hc4, Hw3, Hw4, Hw5, Hw6, Hw7.
  subst. repeat rewrite <- app_assoc. reflexivity.
Qed.

(*| discharges: R-05-051a |*)
Theorem plaintext_canonicity : forall p bs1 bs2 pt,
  read_plaintext p bs1 = Some pt ->
  read_plaintext p bs2 = Some pt ->
  bs1 = bs2.
Proof.
  intros p bs1 bs2 pt H1 H2.
  pose proof (plaintext_serialize_of_parse p bs1 pt H1) as W1.
  pose proof (plaintext_serialize_of_parse p bs2 pt H2) as W2.
  congruence.
Qed.

Theorem plaintext_encode_injective : forall p pt1 pt2 enc,
  write_plaintext p pt1 = Some enc ->
  write_plaintext p pt2 = Some enc ->
  pt1 = pt2.
Proof.
  intros p pt1 pt2 enc H1 H2.
  pose proof (plaintext_parse_of_serialize p pt1 enc H1) as D1.
  pose proof (plaintext_parse_of_serialize p pt2 enc H2) as D2.
  congruence.
Qed.

(*| discharges: R-05-051b |*)
Theorem plaintext_refuses_trailing_bytes : forall p pt enc extra,
  write_plaintext p pt = Some enc -> extra <> nil ->
  read_plaintext p (enc ++ extra) = None.
Proof.
  intros p pt enc extra Hw Hne. unfold write_plaintext in Hw.
  destruct (plaintext_wf p pt) eqn:Hwf; [|discriminate].
  destruct (write_u_be 8 (pt_export_gen pt)) as [b1|] eqn:E1; [|discriminate].
  destruct (write_u_be 4 (pt_source_profile pt)) as [b2|] eqn:E2; [|discriminate].
  destruct (write_u_be 4 (count_of (pt_regions pt))) as [b3|] eqn:E3; [|discriminate].
  destruct (write_regions (pt_regions pt)) as [b4|] eqn:E4; [|discriminate].
  destruct (write_u_be 4 (pt_chunk_size pt)) as [b5|] eqn:E5; [|discriminate].
  destruct (write_u_be 4 (pt_chunk_count pt)) as [b6|] eqn:E6; [|discriminate].
  destruct (write_fixed_bytes (bp_digest_bytes p) (pt_merkle_root pt)) as [b7|] eqn:E7;
    [|discriminate].
  injection Hw as Hw. subst enc.
  unfold read_plaintext. rewrite (plaintext_wf_profile p pt Hwf).
  repeat rewrite <- app_assoc.
  rewrite (read_write_u_be 8 _ b1 _ E1).
  rewrite (read_write_u_be 4 _ b2 _ E2).
  rewrite (read_write_u_be 4 _ b3 _ E3).
  assert (Hmr : Nat.leb (count_of (pt_regions pt)) (bp_max_regions p) = true).
  { unfold plaintext_wf in Hwf.
    do 3 (rewrite every_cons in Hwf; apply andb_split in Hwf; destruct Hwf as [_ Hwf]).
    rewrite every_cons in Hwf. apply andb_split in Hwf. destruct Hwf as [Hr _]. exact Hr. }
  rewrite Hmr.
  rewrite (read_write_regions (pt_regions pt) b4 _ E4).
  rewrite (read_write_u_be 4 _ b5 _ E5).
  rewrite (read_write_u_be 4 _ b6 _ E6).
  rewrite (read_write_fixed_bytes (bp_digest_bytes p) _ b7 extra E7).
  destruct extra as [|x xs]; [contradiction | reflexivity].
Qed.

(* -------------------------------------------------------------------------
   backup-proof-v1, backup-chunk-v1, and backup-envelope-v1.
   ------------------------------------------------------------------------- *)

Record BackupProof : Type := {
  bpf_siblings : list (list nat)
}.

Fixpoint write_digests (w : nat) (ds : list (list nat)) : option (list nat) :=
  match ds with
  | nil => Some nil
  | d :: rest =>
      match write_fixed_bytes w d, write_digests w rest with
      | Some b1, Some b2 => Some (b1 ++ b2)
      | _, _ => None
      end
  end.

Fixpoint read_digests (k w : nat) (bs : list nat) : option (list (list nat) * list nat) :=
  match k with
  | 0 => Some (nil, bs)
  | S j =>
      match read_fixed_bytes w bs with
      | None => None
      | Some (d, rest) =>
          match read_digests j w rest with
          | None => None
          | Some (ds, back) => Some (d :: ds, back)
          end
      end
  end.

Lemma read_write_digests : forall w ds enc back,
  write_digests w ds = Some enc ->
  read_digests (count_of ds) w (enc ++ back) = Some (ds, back).
Proof.
  intros w. induction ds as [|d rest IH]; intros enc back H.
  - simpl in H. injection H as H. subst enc. reflexivity.
  - simpl in H.
    destruct (write_fixed_bytes w d) as [b1|] eqn:E1; [|discriminate].
    destruct (write_digests w rest) as [b2|] eqn:E2; [|discriminate].
    injection H as H. subst enc.
    rewrite count_of_cons. simpl. rewrite <- app_assoc.
    rewrite (read_write_fixed_bytes w d b1 (b2 ++ back) E1).
    rewrite (IH b2 back eq_refl). reflexivity.
Qed.

Lemma write_read_digests : forall k w bs ds back,
  read_digests k w bs = Some (ds, back) ->
  exists enc, bs = enc ++ back /\ write_digests w ds = Some enc /\ count_of ds = k.
Proof.
  induction k as [|j IH]; intros w bs ds back H.
  - simpl in H. destruct (some_pair_eq _ _ _ _ _ _ H) as [H1 H2].
    subst. exists nil. repeat split; reflexivity.
  - simpl in H.
    destruct (read_fixed_bytes w bs) as [[d rest]|] eqn:E1; [|discriminate].
    destruct (read_digests j w rest) as [[ds' tail]|] eqn:E2; [|discriminate].
    destruct (some_pair_eq _ _ _ _ _ _ H) as [H1 H2]. subst.
    destruct (write_read_fixed_bytes w bs d rest E1) as [b1 [Hb1 Hw1]].
    destruct (IH w rest ds' back E2) as [b2 [Hb2 [Hw2 Hc2]]].
    exists (b1 ++ b2). repeat split.
    + subst. rewrite <- app_assoc. reflexivity.
    + simpl. rewrite Hw1, Hw2. reflexivity.
    + simpl. lia.
Qed.

Definition write_proof (p : BackupProfile) (depth : nat) (pf : BackupProof)
  : option (list nat) :=
  if Nat.eqb (count_of (bpf_siblings pf)) depth
  then write_digests (bp_digest_bytes p) (bpf_siblings pf)
  else None.

Definition read_proof (p : BackupProfile) (depth : nat) (bs : list nat)
  : option (BackupProof * list nat) :=
  match read_digests depth (bp_digest_bytes p) bs with
  | None => None
  | Some (ds, back) => Some ({| bpf_siblings := ds |}, back)
  end.

Lemma read_write_proof : forall p depth pf enc back,
  write_proof p depth pf = Some enc ->
  read_proof p depth (enc ++ back) = Some (pf, back).
Proof.
  intros p depth pf enc back H. unfold write_proof in H.
  destruct (Nat.eqb (count_of (bpf_siblings pf)) depth) eqn:E; [|discriminate].
  apply nat_eqb_true in E.
  unfold read_proof. rewrite <- E.
  rewrite (read_write_digests (bp_digest_bytes p) (bpf_siblings pf) enc back H).
  destruct pf. reflexivity.
Qed.

Lemma write_read_proof : forall p depth bs pf back,
  read_proof p depth bs = Some (pf, back) ->
  exists enc, bs = enc ++ back /\ write_proof p depth pf = Some enc.
Proof.
  intros p depth bs pf back H. unfold read_proof in H.
  destruct (read_digests depth (bp_digest_bytes p) bs) as [[ds rest]|] eqn:E;
    [|discriminate].
  destruct (some_pair_eq _ _ _ _ _ _ H) as [Hp Hb]. subst pf rest.
  destruct (write_read_digests depth (bp_digest_bytes p) bs ds back E)
    as [enc [Hb [Hw Hc]]].
  exists enc. split; [exact Hb |].
  unfold write_proof. simpl. rewrite Hc. rewrite nat_eqb_refl. exact Hw.
Qed.

Record BackupChunk : Type := {
  bc_chunk_index : nat;
  bc_region_id : nat;
  bc_region_offset : nat;
  bc_ciphertext : list nat;
  bc_tag : list nat;
  bc_proof : BackupProof
}.

Definition chunk_wf (p : BackupProfile) (depth : nat) (c : BackupChunk) : bool :=
  every (fits_u_be 4 (bc_chunk_index c) ::
         fits_u_be 4 (bc_region_id c) ::
         fits_u_be 8 (bc_region_offset c) ::
         Nat.ltb 0 (count_of (bc_ciphertext c)) ::
         Nat.leb (count_of (bc_ciphertext c)) (bp_chunk_size p) ::
         bytes_ok (bc_ciphertext c) ::
         Nat.eqb (count_of (bc_tag c)) (bp_tag_bytes p) ::
         bytes_ok (bc_tag c) ::
         Nat.eqb (count_of (bpf_siblings (bc_proof c))) depth :: nil).

Definition write_chunk (p : BackupProfile) (depth : nat) (c : BackupChunk)
  : option (list nat) :=
  if chunk_wf p depth c then
    match write_u_be 4 (bc_chunk_index c),
          write_u_be 4 (bc_region_id c),
          write_u_be 8 (bc_region_offset c),
          write_u_be 4 (count_of (bc_ciphertext c)),
          write_fixed_bytes (count_of (bc_ciphertext c)) (bc_ciphertext c),
          write_fixed_bytes (bp_tag_bytes p) (bc_tag c),
          write_proof p depth (bc_proof c) with
    | Some b1, Some b2, Some b3, Some b4, Some b5, Some b6, Some b7 =>
        Some (b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6 ++ b7)
    | _, _, _, _, _, _, _ => None
    end
  else None.

Definition read_chunk (p : BackupProfile) (depth : nat) (bs : list nat)
  : option (BackupChunk * list nat) :=
  match read_u_be 4 bs with
  | None => None
  | Some (cidx, r1) =>
      match read_u_be 4 r1 with
      | None => None
      | Some (rid, r2) =>
          match read_u_be 8 r2 with
          | None => None
          | Some (roff, r3) =>
              match read_u_be 4 r3 with
              | None => None
              | Some (plen, r4) =>
                  if andb (Nat.ltb 0 plen) (Nat.leb plen (bp_chunk_size p)) then
                    match read_fixed_bytes plen r4 with
                    | None => None
                    | Some (ct, r5) =>
                        match read_fixed_bytes (bp_tag_bytes p) r5 with
                        | None => None
                        | Some (tag, r6) =>
                            match read_proof p depth r6 with
                            | None => None
                            | Some (pf, back) =>
                                let ch := {| bc_chunk_index := cidx;
                                             bc_region_id := rid;
                                             bc_region_offset := roff;
                                             bc_ciphertext := ct;
                                             bc_tag := tag;
                                             bc_proof := pf |} in
                                if chunk_wf p depth ch then Some (ch, back) else None
                            end
                        end
                    end
                  else None
              end
          end
      end
  end.

Lemma chunk_wf_plen : forall p depth c,
  chunk_wf p depth c = true ->
  0 < count_of (bc_ciphertext c) /\ count_of (bc_ciphertext c) <= bp_chunk_size p.
Proof.
  intros p depth c H. unfold chunk_wf in H.
  do 3 (rewrite every_cons in H; apply andb_split in H; destruct H as [_ H]).
  rewrite every_cons in H. apply andb_split in H. destruct H as [H1 H].
  rewrite every_cons in H. apply andb_split in H. destruct H as [H2 _].
  apply Nat.ltb_lt in H1. apply Nat.leb_le in H2. split; assumption.
Qed.

Lemma read_write_chunk : forall p depth c enc back,
  write_chunk p depth c = Some enc ->
  read_chunk p depth (enc ++ back) = Some (c, back).
Proof.
  intros p depth c enc back H. unfold write_chunk in H.
  destruct (chunk_wf p depth c) eqn:Hwf; [|discriminate].
  destruct (write_u_be 4 (bc_chunk_index c)) as [b1|] eqn:E1; [|discriminate].
  destruct (write_u_be 4 (bc_region_id c)) as [b2|] eqn:E2; [|discriminate].
  destruct (write_u_be 8 (bc_region_offset c)) as [b3|] eqn:E3; [|discriminate].
  destruct (write_u_be 4 (count_of (bc_ciphertext c))) as [b4|] eqn:E4; [|discriminate].
  destruct (write_fixed_bytes (count_of (bc_ciphertext c)) (bc_ciphertext c))
    as [b5|] eqn:E5; [|discriminate].
  destruct (write_fixed_bytes (bp_tag_bytes p) (bc_tag c)) as [b6|] eqn:E6;
    [|discriminate].
  destruct (write_proof p depth (bc_proof c)) as [b7|] eqn:E7; [|discriminate].
  injection H as H. subst enc.
  unfold read_chunk. repeat rewrite <- app_assoc.
  rewrite (read_write_u_be 4 _ b1 _ E1).
  rewrite (read_write_u_be 4 _ b2 _ E2).
  rewrite (read_write_u_be 8 _ b3 _ E3).
  rewrite (read_write_u_be 4 _ b4 _ E4).
  destruct (chunk_wf_plen p depth c Hwf) as [Hpos Hmax].
  assert (Hposb : Nat.ltb 0 (count_of (bc_ciphertext c)) = true) by (apply Nat.ltb_lt; exact Hpos).
  assert (Hmaxb : Nat.leb (count_of (bc_ciphertext c)) (bp_chunk_size p) = true)
    by (apply Nat.leb_le; exact Hmax).
  rewrite Hposb, Hmaxb. simpl.
  rewrite (read_write_fixed_bytes (count_of (bc_ciphertext c)) _ b5 _ E5).
  rewrite (read_write_fixed_bytes (bp_tag_bytes p) _ b6 _ E6).
  rewrite (read_write_proof p depth _ b7 back E7).
  destruct c. simpl in *. rewrite Hwf. reflexivity.
Qed.

Lemma write_read_chunk : forall p depth bs c back,
  read_chunk p depth bs = Some (c, back) ->
  exists enc, bs = enc ++ back /\ write_chunk p depth c = Some enc.
Proof.
  intros p depth bs c back H. unfold read_chunk in H.
  destruct (read_u_be 4 bs) as [[cidx r1]|] eqn:E1; [|discriminate].
  destruct (read_u_be 4 r1) as [[rid r2]|] eqn:E2; [|discriminate].
  destruct (read_u_be 8 r2) as [[roff r3]|] eqn:E3; [|discriminate].
  destruct (read_u_be 4 r3) as [[plen r4]|] eqn:E4; [|discriminate].
  destruct (andb (Nat.ltb 0 plen) (Nat.leb plen (bp_chunk_size p))) eqn:EL;
    [|discriminate].
  destruct (read_fixed_bytes plen r4) as [[ct r5]|] eqn:E5; [|discriminate].
  destruct (read_fixed_bytes (bp_tag_bytes p) r5) as [[tag r6]|] eqn:E6; [|discriminate].
  destruct (read_proof p depth r6) as [[pf tail]|] eqn:E7; [|discriminate].
  destruct (chunk_wf p depth _) eqn:Hwf; [|discriminate].
  destruct (some_pair_eq _ _ _ _ _ _ H) as [Hc Hb]. subst c tail.
  destruct (write_read_u_be 4 bs cidx r1 E1) as [b1 [Hb1 Hw1]].
  destruct (write_read_u_be 4 r1 rid r2 E2) as [b2 [Hb2 Hw2]].
  destruct (write_read_u_be 8 r2 roff r3 E3) as [b3 [Hb3 Hw3]].
  destruct (write_read_u_be 4 r3 plen r4 E4) as [b4 [Hb4 Hw4]].
  destruct (write_read_fixed_bytes plen r4 ct r5 E5) as [b5 [Hb5 Hw5]].
  destruct (write_read_fixed_bytes (bp_tag_bytes p) r5 tag r6 E6) as [b6 [Hb6 Hw6]].
  destruct (write_read_proof p depth r6 pf back E7) as [b7 [Hb7 Hw7]].
  assert (Hclen : count_of ct = plen).
  { unfold write_fixed_bytes in Hw5.
    destruct (andb (Nat.eqb (count_of ct) plen) (bytes_ok ct)) eqn:Elen; [|discriminate].
    apply andb_split in Elen. destruct Elen as [El _].
    apply nat_eqb_true in El. exact El. }
  exists (b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6 ++ b7). split.
  - subst. repeat rewrite <- app_assoc. reflexivity.
  - unfold write_chunk. rewrite Hwf. simpl.
    rewrite Hclen, Hw1, Hw2, Hw3, Hw4, Hw5, Hw6, Hw7. reflexivity.
Qed.

Lemma write_chunk_nonempty : forall p depth c enc,
  write_chunk p depth c = Some enc -> enc <> nil.
Proof.
  intros p depth c enc H. unfold write_chunk in H.
  destruct (chunk_wf p depth c); [|discriminate].
  destruct (write_u_be 4 (bc_chunk_index c)) as [b1|] eqn:E1; [|discriminate].
  destruct (write_u_be 4 (bc_region_id c)) as [b2|]; [|discriminate].
  destruct (write_u_be 8 (bc_region_offset c)) as [b3|]; [|discriminate].
  destruct (write_u_be 4 (count_of (bc_ciphertext c))) as [b4|]; [|discriminate].
  destruct (write_fixed_bytes (count_of (bc_ciphertext c)) (bc_ciphertext c)) as [b5|];
    [|discriminate].
  destruct (write_fixed_bytes (bp_tag_bytes p) (bc_tag c)) as [b6|]; [|discriminate].
  destruct (write_proof p depth (bc_proof c)) as [b7|]; [|discriminate].
  injection H as H. subst enc.
  pose proof (write_u_be_length 4 (bc_chunk_index c) b1 E1) as Hlen.
  destruct b1 as [|x xs]; [simpl in Hlen; discriminate | discriminate].
Qed.

Fixpoint write_chunks_seq (p : BackupProfile) (depth expected_idx : nat)
    (cs : list BackupChunk) : option (list nat) :=
  match cs with
  | nil => Some nil
  | c :: rest =>
      if Nat.eqb (bc_chunk_index c) expected_idx then
        match write_chunk p depth c, write_chunks_seq p depth (S expected_idx) rest with
        | Some b1, Some b2 => Some (b1 ++ b2)
        | _, _ => None
        end
      else None
  end.

Fixpoint read_chunks_seq_fuel (fuel : nat) (p : BackupProfile) (depth expected_idx : nat)
    (bs : list nat) : option (list BackupChunk) :=
  match bs with
  | nil => Some nil
  | _ :: _ =>
      match fuel with
      | 0 => None
      | S f =>
          match read_chunk p depth bs with
          | None => None
          | Some (c, rest) =>
              if Nat.eqb (bc_chunk_index c) expected_idx then
                match read_chunks_seq_fuel f p depth (S expected_idx) rest with
                | None => None
                | Some cs => Some (c :: cs)
                end
              else None
          end
      end
  end.

Lemma read_write_chunks_seq : forall p depth idx cs enc fuel,
  count_of enc <= fuel ->
  write_chunks_seq p depth idx cs = Some enc ->
  read_chunks_seq_fuel fuel p depth idx enc = Some cs.
Proof.
  intros p depth idx cs. revert idx.
  induction cs as [|c rest IH]; intros idx enc fuel Hfuel Hw.
  - simpl in Hw. injection Hw as Hw. subst enc.
    destruct fuel; reflexivity.
  - simpl in Hw.
    destruct (Nat.eqb (bc_chunk_index c) idx) eqn:Eidx; [|discriminate].
    destruct (write_chunk p depth c) as [b1|] eqn:E1; [|discriminate].
    destruct (write_chunks_seq p depth (S idx) rest) as [b2|] eqn:E2; [|discriminate].
    injection Hw as Hw. subst enc.
    pose proof (write_chunk_nonempty p depth c b1 E1) as Hne.
    destruct b1 as [|x xs]; [contradiction |].
    destruct fuel as [|f].
    { rewrite count_of_app in Hfuel. simpl in Hfuel. lia. }
    simpl.
    change (x :: xs ++ b2) with ((x :: xs) ++ b2).
    rewrite (read_write_chunk p depth c (x :: xs) b2 E1).
    rewrite Eidx.
    assert (Hf2 : count_of b2 <= f).
    { rewrite count_of_app in Hfuel. simpl in Hfuel. lia. }
    rewrite (IH (S idx) b2 f Hf2 E2). reflexivity.
Qed.

Lemma write_read_chunks_seq : forall fuel p depth idx bs cs,
  read_chunks_seq_fuel fuel p depth idx bs = Some cs ->
  write_chunks_seq p depth idx cs = Some bs.
Proof.
  induction fuel as [|f IH]; intros p depth idx bs cs H.
  - destruct bs; [|discriminate]. simpl in H. injection H as H. subst cs. reflexivity.
  - destruct bs as [|b0 r0].
    + simpl in H. injection H as H. subst cs. reflexivity.
    + simpl in H.
      destruct (read_chunk p depth (b0 :: r0)) as [[c rest]|] eqn:E1; [|discriminate].
      destruct (Nat.eqb (bc_chunk_index c) idx) eqn:Eidx; [|discriminate].
      destruct (read_chunks_seq_fuel f p depth (S idx) rest) as [cs'|] eqn:E2; [|discriminate].
      injection H as H. subst cs.
      destruct (write_read_chunk p depth (b0 :: r0) c rest E1) as [b1 [Hb1 Hw1]].
      pose proof (IH p depth (S idx) rest cs' E2) as Hw2.
      simpl. rewrite Eidx, Hw1, Hw2, Hb1. reflexivity.
Qed.

Record BackupEnvelope : Type := {
  be_total_extent : nat;
  be_manifest_nonce : list nat;
  be_enc_manifest : list nat;
  be_manifest_tag : list nat;
  be_chunks : list BackupChunk
}.

Definition envelope_wf (p : BackupProfile) (e : BackupEnvelope) : bool :=
  every (backup_profile_wf p ::
         fits_u_be 8 (be_total_extent e) ::
         Nat.eqb (count_of (be_manifest_nonce e)) (bp_nonce_bytes p) ::
         bytes_ok (be_manifest_nonce e) ::
         fits_u_be 4 (count_of (be_enc_manifest e)) ::
         bytes_ok (be_enc_manifest e) ::
         Nat.eqb (count_of (be_manifest_tag e)) (bp_tag_bytes p) ::
         bytes_ok (be_manifest_tag e) ::
         Nat.leb (count_of (be_chunks e)) (bp_max_chunks p) :: nil).

Definition write_envelope (p : BackupProfile) (depth : nat) (e : BackupEnvelope)
  : option (list nat) :=
  if envelope_wf p e then
    match write_fixed_bytes 8 (bp_magic p),
          write_u_be 4 (bp_version p),
          write_u_be 4 (bp_profile_id p),
          write_u_be 8 (be_total_extent e),
          write_fixed_bytes (bp_nonce_bytes p) (be_manifest_nonce e),
          write_u_be 4 (count_of (be_enc_manifest e)),
          write_fixed_bytes (count_of (be_enc_manifest e)) (be_enc_manifest e),
          write_fixed_bytes (bp_tag_bytes p) (be_manifest_tag e),
          write_chunks_seq p depth 0 (be_chunks e) with
    | Some b1, Some b2, Some b3, Some b4, Some b5,
      Some b6, Some b7, Some b8, Some b9 =>
        let raw := b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6 ++ b7 ++ b8 ++ b9 in
        if Nat.eqb (count_of raw) (be_total_extent e) then Some raw else None
    | _, _, _, _, _, _, _, _, _ => None
    end
  else None.

Definition read_envelope (p : BackupProfile) (depth : nat) (bs : list nat)
  : option BackupEnvelope :=
  if backup_profile_wf p then
    match read_fixed_bytes 8 bs with
    | None => None
    | Some (magic, r1) =>
        if list_eqb Nat.eqb magic (bp_magic p) then
          match read_u_be 4 r1 with
          | None => None
          | Some (ver, r2) =>
              if Nat.eqb ver (bp_version p) then
                match read_u_be 4 r2 with
                | None => None
                | Some (prof, r3) =>
                    if Nat.eqb prof (bp_profile_id p) then
                      match read_u_be 8 r3 with
                      | None => None
                      | Some (ext, r4) =>
                          if Nat.eqb ext (count_of bs) then
                            match read_fixed_bytes (bp_nonce_bytes p) r4 with
                            | None => None
                            | Some (nonce, r5) =>
                                match read_u_be 4 r5 with
                                | None => None
                                | Some (mlen, r6) =>
                                    match read_fixed_bytes mlen r6 with
                                    | None => None
                                    | Some (mct, r7) =>
                                        match read_fixed_bytes (bp_tag_bytes p) r7 with
                                        | None => None
                                        | Some (mtag, r8) =>
                                            match read_chunks_seq_fuel (count_of r8) p depth 0 r8 with
                                            | None => None
                                            | Some chunks =>
                                                let cand := {| be_total_extent := ext;
                                                               be_manifest_nonce := nonce;
                                                               be_enc_manifest := mct;
                                                               be_manifest_tag := mtag;
                                                               be_chunks := chunks |} in
                                                if envelope_wf p cand then Some cand else None
                                            end
                                        end
                                    end
                                end
                            end
                          else None
                      end
                    else None
                end
              else None
          end
        else None
    end
  else None.

Lemma envelope_wf_profile : forall p e,
  envelope_wf p e = true -> backup_profile_wf p = true.
Proof.
  intros p e H. unfold envelope_wf in H.
  rewrite every_cons in H. apply andb_split in H. destruct H as [Hp _]. exact Hp.
Qed.

(*| discharges: R-05-051a |*)
Theorem envelope_parse_of_serialize : forall p depth e enc,
  write_envelope p depth e = Some enc ->
  read_envelope p depth enc = Some e.
Proof.
  intros p depth e enc Hw. unfold write_envelope in Hw.
  destruct (envelope_wf p e) eqn:Hwf; [|discriminate].
  destruct (write_fixed_bytes 8 (bp_magic p)) as [b1|] eqn:E1; [|discriminate].
  destruct (write_u_be 4 (bp_version p)) as [b2|] eqn:E2; [|discriminate].
  destruct (write_u_be 4 (bp_profile_id p)) as [b3|] eqn:E3; [|discriminate].
  destruct (write_u_be 8 (be_total_extent e)) as [b4|] eqn:E4; [|discriminate].
  destruct (write_fixed_bytes (bp_nonce_bytes p) (be_manifest_nonce e))
    as [b5|] eqn:E5; [|discriminate].
  destruct (write_u_be 4 (count_of (be_enc_manifest e))) as [b6|] eqn:E6; [|discriminate].
  destruct (write_fixed_bytes (count_of (be_enc_manifest e)) (be_enc_manifest e))
    as [b7|] eqn:E7; [|discriminate].
  destruct (write_fixed_bytes (bp_tag_bytes p) (be_manifest_tag e))
    as [b8|] eqn:E8; [|discriminate].
  destruct (write_chunks_seq p depth 0 (be_chunks e)) as [b9|] eqn:E9; [|discriminate].
  destruct (Nat.eqb (count_of (b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6 ++ b7 ++ b8 ++ b9))
                    (be_total_extent e)) eqn:Hext; [|discriminate].
  injection Hw as Hw. subst enc.
  unfold read_envelope. rewrite (envelope_wf_profile p e Hwf).
  repeat rewrite <- app_assoc.
  rewrite (read_write_fixed_bytes 8 _ b1 _ E1).
  rewrite (list_eqb_refl _ Nat.eqb nat_eqb_refl).
  rewrite (read_write_u_be 4 _ b2 _ E2). rewrite nat_eqb_refl.
  rewrite (read_write_u_be 4 _ b3 _ E3). rewrite nat_eqb_refl.
  rewrite (read_write_u_be 8 _ b4 _ E4).
  assert (Hext' : Nat.eqb (be_total_extent e)
                    (count_of (b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6 ++ b7 ++ b8 ++ b9)) = true).
  { rewrite nat_eqb_sym. repeat rewrite <- app_assoc in Hext. exact Hext. }
  repeat rewrite <- app_assoc in Hext'. rewrite Hext'.
  rewrite (read_write_fixed_bytes (bp_nonce_bytes p) _ b5 _ E5).
  rewrite (read_write_u_be 4 _ b6 _ E6).
  rewrite (read_write_fixed_bytes (count_of (be_enc_manifest e)) _ b7 _ E7).
  rewrite (read_write_fixed_bytes (bp_tag_bytes p) _ b8 _ E8).
  rewrite (read_write_chunks_seq p depth 0 (be_chunks e) b9 (count_of b9) (Nat.le_refl _) E9).
  destruct e. simpl in *. rewrite Hwf. reflexivity.
Qed.

(*| discharges: R-05-051a, R-05-051b |*)
Theorem envelope_serialize_of_parse : forall p depth bs e,
  read_envelope p depth bs = Some e ->
  write_envelope p depth e = Some bs.
Proof.
  intros p depth bs e H. unfold read_envelope in H.
  destruct (backup_profile_wf p) eqn:Hp; [|discriminate].
  destruct (read_fixed_bytes 8 bs) as [[magic r1]|] eqn:E1; [|discriminate].
  destruct (list_eqb Nat.eqb magic (bp_magic p)) eqn:Emag; [|discriminate].
  destruct (read_u_be 4 r1) as [[ver r2]|] eqn:E2; [|discriminate].
  destruct (Nat.eqb ver (bp_version p)) eqn:Ever; [|discriminate].
  destruct (read_u_be 4 r2) as [[prof r3]|] eqn:E3; [|discriminate].
  destruct (Nat.eqb prof (bp_profile_id p)) eqn:Eprof; [|discriminate].
  destruct (read_u_be 8 r3) as [[ext r4]|] eqn:E4; [|discriminate].
  destruct (Nat.eqb ext (count_of bs)) eqn:Eext; [|discriminate].
  destruct (read_fixed_bytes (bp_nonce_bytes p) r4) as [[nonce r5]|] eqn:E5; [|discriminate].
  destruct (read_u_be 4 r5) as [[mlen r6]|] eqn:E6; [|discriminate].
  destruct (read_fixed_bytes mlen r6) as [[mct r7]|] eqn:E7; [|discriminate].
  destruct (read_fixed_bytes (bp_tag_bytes p) r7) as [[mtag r8]|] eqn:E8; [|discriminate].
  destruct (read_chunks_seq_fuel (count_of r8) p depth 0 r8) as [chunks|] eqn:E9;
    [|discriminate].
  destruct (envelope_wf p _) eqn:Hwf; [|discriminate].
  injection H as H. subst e.
  assert (Hmagic : magic = bp_magic p)
    by (exact (list_eqb_sound _ Nat.eqb nat_eqb_true magic (bp_magic p) Emag)).
  apply nat_eqb_true in Ever. apply nat_eqb_true in Eprof. apply nat_eqb_true in Eext.
  destruct (write_read_fixed_bytes 8 bs magic r1 E1) as [b1 [Hb1 Hw1]].
  destruct (write_read_u_be 4 r1 ver r2 E2) as [b2 [Hb2 Hw2]].
  destruct (write_read_u_be 4 r2 prof r3 E3) as [b3 [Hb3 Hw3]].
  destruct (write_read_u_be 8 r3 ext r4 E4) as [b4 [Hb4 Hw4]].
  destruct (write_read_fixed_bytes (bp_nonce_bytes p) r4 nonce r5 E5) as [b5 [Hb5 Hw5]].
  destruct (write_read_u_be 4 r5 mlen r6 E6) as [b6 [Hb6 Hw6]].
  destruct (write_read_fixed_bytes mlen r6 mct r7 E7) as [b7 [Hb7 Hw7]].
  destruct (write_read_fixed_bytes (bp_tag_bytes p) r7 mtag r8 E8) as [b8 [Hb8 Hw8]].
  pose proof (write_read_chunks_seq (count_of r8) p depth 0 r8 chunks E9) as Hw9.
  assert (Hmlen : count_of mct = mlen).
  { unfold write_fixed_bytes in Hw7.
    destruct (andb (Nat.eqb (count_of mct) mlen) (bytes_ok mct)) eqn:Em; [|discriminate].
    apply andb_split in Em. destruct Em as [El _]. apply nat_eqb_true in El. exact El. }
  assert (Hraw : bs = b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6 ++ b7 ++ b8 ++ r8).
  { subst. repeat rewrite <- app_assoc. reflexivity. }
  unfold write_envelope. rewrite Hwf. simpl.
  rewrite <- Hmagic, <- Ever, <- Eprof, Hmlen.
  rewrite Hw1, Hw2, Hw3, Hw4, Hw5, Hw6, Hw7, Hw8, Hw9.
  rewrite <- Hraw. rewrite Eext. rewrite nat_eqb_refl. reflexivity.
Qed.

(*| discharges: R-05-051a |*)
Theorem envelope_canonicity : forall p depth bs1 bs2 e,
  read_envelope p depth bs1 = Some e ->
  read_envelope p depth bs2 = Some e ->
  bs1 = bs2.
Proof.
  intros p depth bs1 bs2 e H1 H2.
  pose proof (envelope_serialize_of_parse p depth bs1 e H1) as W1.
  pose proof (envelope_serialize_of_parse p depth bs2 e H2) as W2.
  congruence.
Qed.

Theorem envelope_encode_injective : forall p depth e1 e2 enc,
  write_envelope p depth e1 = Some enc ->
  write_envelope p depth e2 = Some enc ->
  e1 = e2.
Proof.
  intros p depth e1 e2 enc H1 H2.
  pose proof (envelope_parse_of_serialize p depth e1 enc H1) as D1.
  pose proof (envelope_parse_of_serialize p depth e2 enc H2) as D2.
  congruence.
Qed.

(*| discharges: R-05-051b |*)
Theorem envelope_refuses_trailing_bytes : forall p depth e enc extra,
  write_envelope p depth e = Some enc -> extra <> nil ->
  read_envelope p depth (enc ++ extra) = None.
Proof.
  intros p depth e enc extra Hw Hne. unfold write_envelope in Hw.
  destruct (envelope_wf p e) eqn:Hwf; [|discriminate].
  destruct (write_fixed_bytes 8 (bp_magic p)) as [b1|] eqn:E1; [|discriminate].
  destruct (write_u_be 4 (bp_version p)) as [b2|] eqn:E2; [|discriminate].
  destruct (write_u_be 4 (bp_profile_id p)) as [b3|] eqn:E3; [|discriminate].
  destruct (write_u_be 8 (be_total_extent e)) as [b4|] eqn:E4; [|discriminate].
  destruct (write_fixed_bytes (bp_nonce_bytes p) (be_manifest_nonce e))
    as [b5|] eqn:E5; [|discriminate].
  destruct (write_u_be 4 (count_of (be_enc_manifest e))) as [b6|] eqn:E6; [|discriminate].
  destruct (write_fixed_bytes (count_of (be_enc_manifest e)) (be_enc_manifest e))
    as [b7|] eqn:E7; [|discriminate].
  destruct (write_fixed_bytes (bp_tag_bytes p) (be_manifest_tag e))
    as [b8|] eqn:E8; [|discriminate].
  destruct (write_chunks_seq p depth 0 (be_chunks e)) as [b9|] eqn:E9; [|discriminate].
  destruct (Nat.eqb (count_of (b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6 ++ b7 ++ b8 ++ b9))
                    (be_total_extent e)) eqn:Hext; [|discriminate].
  injection Hw as Hw. subst enc.
  unfold read_envelope. rewrite (envelope_wf_profile p e Hwf).
  repeat rewrite <- app_assoc.
  rewrite (read_write_fixed_bytes 8 _ b1 _ E1).
  rewrite (list_eqb_refl _ Nat.eqb nat_eqb_refl).
  rewrite (read_write_u_be 4 _ b2 _ E2). rewrite nat_eqb_refl.
  rewrite (read_write_u_be 4 _ b3 _ E3). rewrite nat_eqb_refl.
  rewrite (read_write_u_be 8 _ b4 _ E4).
  apply nat_eqb_true in Hext.
  assert (Hdiff : Nat.eqb (be_total_extent e)
                    (count_of (b1 ++ b2 ++ b3 ++ b4 ++ b5 ++ b6 ++ b7 ++ b8 ++ b9 ++ extra)) = false).
  { apply Nat.eqb_neq.
    repeat rewrite count_of_app.
    repeat rewrite count_of_app in Hext.
    destruct extra as [|x xs]; [contradiction | simpl; lia]. }
  rewrite Hdiff. reflexivity.
Qed.

(* -------------------------------------------------------------------------
   ExportView: Rollbackable + DataOnly regions only (R-10-039).
   ------------------------------------------------------------------------- *)

Inductive RegionKind : Type :=
| RK_Rollbackable
| RK_Fresh
| RK_ConsentStore
| RK_KeyHandle
| RK_CredentialHandle
| RK_SealedObject.

Definition region_kind_eqb (a b : RegionKind) : bool :=
  match a, b with
  | RK_Rollbackable, RK_Rollbackable => true
  | RK_Fresh, RK_Fresh => true
  | RK_ConsentStore, RK_ConsentStore => true
  | RK_KeyHandle, RK_KeyHandle => true
  | RK_CredentialHandle, RK_CredentialHandle => true
  | RK_SealedObject, RK_SealedObject => true
  | _, _ => false
  end.

Inductive SchemaClass : Type :=
| SC_Scalar
| SC_Bytes
| SC_Product (a b : SchemaClass)
| SC_Variant (a b : SchemaClass)
| SC_BoundedList (elem : SchemaClass)
| SC_Pointer
| SC_Capability
| SC_Key
| SC_NonceState
| SC_ExecState
| SC_ConnState
| SC_SealedHandle
| SC_CredentialHandle.

Fixpoint is_data_only (s : SchemaClass) : bool :=
  match s with
  | SC_Scalar => true
  | SC_Bytes => true
  | SC_Product a b => andb (is_data_only a) (is_data_only b)
  | SC_Variant a b => andb (is_data_only a) (is_data_only b)
  | SC_BoundedList elem => is_data_only elem
  | SC_Pointer => false
  | SC_Capability => false
  | SC_Key => false
  | SC_NonceState => false
  | SC_ExecState => false
  | SC_ConnState => false
  | SC_SealedHandle => false
  | SC_CredentialHandle => false
  end.

Record SourceRegion : Type := {
  sr_id : nat;
  sr_kind : RegionKind;
  sr_schema : SchemaClass;
  sr_schema_id : nat;
  sr_schema_gen : nat;
  sr_payload : list nat
}.

Record ExportableEntry : Type := {
  ee_id : nat;
  ee_schema_id : nat;
  ee_schema_gen : nat;
  ee_payload : list nat
}.

Definition is_exportable_region (r : SourceRegion) : bool :=
  andb (region_kind_eqb (sr_kind r) RK_Rollbackable) (is_data_only (sr_schema r)).

Fixpoint build_export_view (rs : list SourceRegion) : list ExportableEntry :=
  match rs with
  | nil => nil
  | r :: rest =>
      if is_exportable_region r then
        {| ee_id := sr_id r;
           ee_schema_id := sr_schema_id r;
           ee_schema_gen := sr_schema_gen r;
           ee_payload := sr_payload r |} :: build_export_view rest
      else build_export_view rest
  end.

Definition entry_matches_source (e : ExportableEntry) (r : SourceRegion) : Prop :=
  ee_id e = sr_id r /\
  ee_schema_id e = sr_schema_id r /\
  ee_schema_gen e = sr_schema_gen r /\
  ee_payload e = sr_payload r /\
  sr_kind r = RK_Rollbackable /\
  is_data_only (sr_schema r) = true.

(*| discharges: R-10-039 |*)
Theorem export_view_only_rollbackable_data_only : forall rs e,
  Member e (build_export_view rs) ->
  exists r, Member r rs /\ entry_matches_source e r.
Proof.
  induction rs as [|r rest IH]; intros e Hm.
  - contradiction Hm.
  - simpl in Hm. destruct (is_exportable_region r) eqn:E.
    + destruct Hm as [Heq | Hrest].
      * exists r. split; [left; reflexivity |].
        unfold is_exportable_region in E. apply andb_split in E.
        destruct E as [Ek Ed].
        destruct (sr_kind r) eqn:Hk; try discriminate Ek.
        subst e. repeat split; try reflexivity; assumption.
      * destruct (IH e Hrest) as [r0 [Hr0 Hm0]].
        exists r0. split; [right; exact Hr0 | exact Hm0].
    + destruct (IH e Hm) as [r0 [Hr0 Hm0]].
      exists r0. split; [right; exact Hr0 | exact Hm0].
Qed.

Theorem export_view_excludes_forbidden_kinds : forall r,
  sr_kind r = RK_Fresh \/
  sr_kind r = RK_ConsentStore \/
  sr_kind r = RK_KeyHandle \/
  sr_kind r = RK_CredentialHandle \/
  sr_kind r = RK_SealedObject ->
  build_export_view (r :: nil) = nil.
Proof.
  intros r Hk. unfold build_export_view, is_exportable_region.
  destruct Hk as [H | [H | [H | [H | H]]]]; rewrite H; reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Restore state machine and Fresh-install initializer invariants (R-10-038,
   R-10-039).
   ------------------------------------------------------------------------- *)

Inductive RestorePhase : Type :=
| RP_Idle
| RP_Authorized
| RP_ManifestAuthenticated
| RP_Planned
| RP_Staging
| RP_Complete
| RP_Committed
| RP_Discarded.

Inductive PlanArm : Type :=
| PA_SameSchema
| PA_CheckedMigration
| PA_Discard
| PA_Unsupported.

Definition plan_arm_supported (a : PlanArm) : bool :=
  match a with
  | PA_SameSchema => true
  | PA_CheckedMigration => true
  | PA_Discard => true
  | PA_Unsupported => false
  end.

Record RestoreMachine : Type := {
  rm_phase : RestorePhase;
  rm_region_writes : nat;
  rm_staged_chunks : nat;
  rm_expected_chunks : nat;
  rm_live_profile_gen : nat;
  rm_staged_gen : nat;
  rm_consent_consumed : bool
}.

Definition rm_init (live_gen : nat) : RestoreMachine :=
  {| rm_phase := RP_Idle;
     rm_region_writes := 0;
     rm_staged_chunks := 0;
     rm_expected_chunks := 0;
     rm_live_profile_gen := live_gen;
     rm_staged_gen := 0;
     rm_consent_consumed := false |}.

Definition rm_authorize (m : RestoreMachine) (cred_ok consent_ok : bool) : RestoreMachine :=
  match rm_phase m with
  | RP_Idle =>
      if andb cred_ok consent_ok then
        {| rm_phase := RP_Authorized;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := 0;
           rm_expected_chunks := 0;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := 0;
           rm_consent_consumed := false |}
      else
        {| rm_phase := RP_Discarded;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := 0;
           rm_expected_chunks := 0;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := 0;
           rm_consent_consumed := false |}
  | _ => m
  end.

Definition rm_auth_manifest (m : RestoreMachine) (auth_ok : bool)
    (staged_gen expected_chunks : nat) : RestoreMachine :=
  match rm_phase m with
  | RP_Authorized =>
      if auth_ok then
        {| rm_phase := RP_ManifestAuthenticated;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := 0;
           rm_expected_chunks := expected_chunks;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := staged_gen;
           rm_consent_consumed := rm_consent_consumed m |}
      else
        {| rm_phase := RP_Discarded;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := 0;
           rm_expected_chunks := 0;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := 0;
           rm_consent_consumed := rm_consent_consumed m |}
  | _ => m
  end.

Definition rm_plan (m : RestoreMachine) (arms : list PlanArm) : RestoreMachine :=
  match rm_phase m with
  | RP_ManifestAuthenticated =>
      if all_of plan_arm_supported arms then
        {| rm_phase := RP_Planned;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := 0;
           rm_expected_chunks := rm_expected_chunks m;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := rm_staged_gen m;
           rm_consent_consumed := rm_consent_consumed m |}
      else
        {| rm_phase := RP_Discarded;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := 0;
           rm_expected_chunks := 0;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := 0;
           rm_consent_consumed := rm_consent_consumed m |}
  | _ => m
  end.

Definition rm_stage_chunk (m : RestoreMachine) (aead_ok merkle_ok : bool) : RestoreMachine :=
  match rm_phase m with
  | RP_Planned =>
      if andb aead_ok merkle_ok then
        {| rm_phase := RP_Staging;
           rm_region_writes := S (rm_region_writes m);
           rm_staged_chunks := S (rm_staged_chunks m);
           rm_expected_chunks := rm_expected_chunks m;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := rm_staged_gen m;
           rm_consent_consumed := rm_consent_consumed m |}
      else
        {| rm_phase := RP_Discarded;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := 0;
           rm_expected_chunks := 0;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := 0;
           rm_consent_consumed := rm_consent_consumed m |}
  | RP_Staging =>
      if andb aead_ok merkle_ok then
        {| rm_phase := RP_Staging;
           rm_region_writes := S (rm_region_writes m);
           rm_staged_chunks := S (rm_staged_chunks m);
           rm_expected_chunks := rm_expected_chunks m;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := rm_staged_gen m;
           rm_consent_consumed := rm_consent_consumed m |}
      else
        {| rm_phase := RP_Discarded;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := 0;
           rm_expected_chunks := 0;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := 0;
           rm_consent_consumed := rm_consent_consumed m |}
  | _ => m
  end.

Definition rm_complete (m : RestoreMachine) : RestoreMachine :=
  match rm_phase m with
  | RP_Planned =>
      if Nat.eqb (rm_expected_chunks m) 0 then
        {| rm_phase := RP_Complete;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := rm_staged_chunks m;
           rm_expected_chunks := rm_expected_chunks m;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := rm_staged_gen m;
           rm_consent_consumed := rm_consent_consumed m |}
      else
        {| rm_phase := RP_Discarded;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := 0;
           rm_expected_chunks := 0;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := 0;
           rm_consent_consumed := rm_consent_consumed m |}
  | RP_Staging =>
      if Nat.eqb (rm_staged_chunks m) (rm_expected_chunks m) then
        {| rm_phase := RP_Complete;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := rm_staged_chunks m;
           rm_expected_chunks := rm_expected_chunks m;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := rm_staged_gen m;
           rm_consent_consumed := rm_consent_consumed m |}
      else
        {| rm_phase := RP_Discarded;
           rm_region_writes := rm_region_writes m;
           rm_staged_chunks := 0;
           rm_expected_chunks := 0;
           rm_live_profile_gen := rm_live_profile_gen m;
           rm_staged_gen := 0;
           rm_consent_consumed := rm_consent_consumed m |}
  | _ => m
  end.

Definition rm_commit (m : RestoreMachine) : RestoreMachine :=
  match rm_phase m with
  | RP_Complete =>
      {| rm_phase := RP_Committed;
         rm_region_writes := rm_region_writes m;
         rm_staged_chunks := rm_staged_chunks m;
         rm_expected_chunks := rm_expected_chunks m;
         rm_live_profile_gen := rm_staged_gen m;
         rm_staged_gen := rm_staged_gen m;
         rm_consent_consumed := true |}
  | _ => m
  end.

Definition rm_fail (m : RestoreMachine) : RestoreMachine :=
  {| rm_phase := RP_Discarded;
     rm_region_writes := rm_region_writes m;
     rm_staged_chunks := 0;
     rm_expected_chunks := 0;
     rm_live_profile_gen := rm_live_profile_gen m;
     rm_staged_gen := 0;
     rm_consent_consumed := rm_consent_consumed m |}.

(*| discharges: R-10-038 |*)
Theorem zero_writes_before_staging : forall live_gen cred consent auth sgen nchunks arms,
  let m0 := rm_init live_gen in
  let m1 := rm_authorize m0 cred consent in
  let m2 := rm_auth_manifest m1 auth sgen nchunks in
  let m3 := rm_plan m2 arms in
  rm_region_writes m0 = 0 /\
  rm_region_writes m1 = 0 /\
  rm_region_writes m2 = 0 /\
  rm_region_writes m3 = 0.
Proof.
  intros live_gen cred consent auth sgen nchunks arms.
  cbv zeta.
  destruct cred, consent, auth;
    cbn [andb rm_init rm_authorize rm_auth_manifest rm_plan rm_phase rm_region_writes rm_staged_chunks rm_expected_chunks rm_live_profile_gen rm_staged_gen rm_consent_consumed];
    try destruct (all_of plan_arm_supported arms);
    repeat split; reflexivity.
Qed.

Theorem unsupported_plan_discards_with_zero_writes : forall live_gen sgen nchunks arms,
  Member PA_Unsupported arms ->
  let m := rm_plan (rm_auth_manifest (rm_authorize (rm_init live_gen) true true) true sgen nchunks) arms in
  rm_phase m = RP_Discarded /\ rm_region_writes m = 0.
Proof.
  intros live_gen sgen nchunks arms Hun.
  assert (Hall : all_of plan_arm_supported arms = false).
  { destruct (all_of plan_arm_supported arms) eqn:E; [|reflexivity].
    pose proof (all_of_member _ plan_arm_supported arms PA_Unsupported E Hun) as Hbad.
    discriminate Hbad. }
  cbv zeta.
  cbn [andb rm_init rm_authorize rm_auth_manifest rm_plan rm_phase rm_region_writes].
  rewrite Hall. split; reflexivity.
Qed.

Theorem fail_preserves_live_generation : forall m,
  rm_live_profile_gen (rm_fail m) = rm_live_profile_gen m.
Proof. intros m. reflexivity. Qed.

(* -------------------------------------------------------------------------
   Fresh-install initializers and denial witnesses (R-10-039).
   ------------------------------------------------------------------------- *)

Inductive FreshClass : Type :=
| FC_SpentPayment
| FC_ConsumedToken
| FC_OneTimeOp
| FC_AttemptCounter
| FC_RevocationList
| FC_OtherFresh.

Record FreshInitState : Type := {
  fi_class : FreshClass;
  fi_enrolled : bool;
  fi_reconciled : bool;
  fi_epoch : nat;
  fi_attempts_remaining : nat;
  fi_spent_tokens : list nat
}.

Definition fresh_install_init (cls : FreshClass) (epoch : nat) : FreshInitState :=
  {| fi_class := cls;
     fi_enrolled := false;
     fi_reconciled := false;
     fi_epoch := epoch;
     fi_attempts_remaining := 0;
     fi_spent_tokens := nil |}.

Definition can_spend_or_use_token (st : FreshInitState) (tok : nat) : bool :=
  andb (fi_enrolled st) (andb (fi_reconciled st) (negb (mem_nat tok (fi_spent_tokens st)))).

Definition can_attempt_guess (st : FreshInitState) : bool :=
  andb (fi_enrolled st) (Nat.ltb 0 (fi_attempts_remaining st)).

(*| discharges: R-10-039 |*)
Theorem fresh_install_denies_old_authority : forall cls epoch tok,
  can_spend_or_use_token (fresh_install_init cls epoch) tok = false /\
  can_attempt_guess (fresh_install_init cls epoch) = false.
Proof.
  intros cls epoch tok. split; reflexivity.
Qed.

(* -------------------------------------------------------------------------
   Closed witnesses and boundary examples (R-05-165, R-05-166).
   ------------------------------------------------------------------------- *)

Definition witness_RecoverySecret : RecoverySecret :=
  {| rs_bytes :=
       0::1::2::3::4::5::6::7::8::9::10::11::12::13::14::15::
       16::17::18::19::20::21::22::23::24::25::26::27::28::29::30::31::nil |}.

Definition witness_BackupProfile : BackupProfile :=
  {| bp_magic := 86::79::83::66::75::48::48::49::nil; (* "VOSBK001" *)
     bp_version := 1;
     bp_profile_id := 1;
     bp_chunk_size := 64;
     bp_max_regions := 16;
     bp_max_chunks := 64;
     bp_digest_bytes := 32;
     bp_nonce_bytes := 12;
     bp_tag_bytes := 16 |}.

Definition witness_BackupRegion : BackupRegion :=
  {| br_region_id := 1;
     br_schema_id := 10;
     br_schema_gen := 1;
     br_payload_len := 4;
     br_first_chunk := 0;
     br_chunk_count := 1 |}.

Definition witness_BackupPlaintext : BackupPlaintext :=
  {| pt_export_gen := 7;
     pt_source_profile := 1;
     pt_regions := witness_BackupRegion :: nil;
     pt_chunk_size := 64;
     pt_chunk_count := 1;
     pt_merkle_root := repeat_of 32 170 |}.

Definition witness_BackupProof : BackupProof :=
  {| bpf_siblings := nil |}.

Definition witness_BackupChunk : BackupChunk :=
  {| bc_chunk_index := 0;
     bc_region_id := 1;
     bc_region_offset := 0;
     bc_ciphertext := 1::2::3::4::nil;
     bc_tag := repeat_of 16 187;
     bc_proof := witness_BackupProof |}.

Definition witness_BackupEnvelope : BackupEnvelope :=
  {| be_total_extent := 180;
     be_manifest_nonce := repeat_of 12 17;
     be_enc_manifest := repeat_of 84 34;
     be_manifest_tag := repeat_of 16 51;
     be_chunks := witness_BackupChunk :: nil |}.

Definition witness_SourceRegion : SourceRegion :=
  {| sr_id := 1;
     sr_kind := RK_Rollbackable;
     sr_schema := SC_Product SC_Scalar SC_Bytes;
     sr_schema_id := 10;
     sr_schema_gen := 1;
     sr_payload := 1::2::3::4::nil |}.

Definition witness_ExportableEntry : ExportableEntry :=
  {| ee_id := 1;
     ee_schema_id := 10;
     ee_schema_gen := 1;
     ee_payload := 1::2::3::4::nil |}.

Definition witness_RestoreMachine : RestoreMachine := rm_init 1.

Definition witness_FreshInitState : FreshInitState := fresh_install_init FC_SpentPayment 1.

Example recovery_secret_round_trips_leading_zeros :
  exists hex,
    encode_recovery_secret witness_RecoverySecret = Some hex /\
    count_of hex = 64 /\
    decode_recovery_secret hex = Some witness_RecoverySecret.
Proof.
  eexists. repeat split; reflexivity.
Qed.

Example recovery_secret_refuses_lowercase_and_short :
  decode_recovery_secret (repeat_of 64 97) = None /\
  decode_recovery_secret (repeat_of 63 48) = None.
Proof. split; reflexivity. Qed.

Example backup_profile_is_wf :
  backup_profile_wf witness_BackupProfile = true.
Proof. reflexivity. Qed.

Example plaintext_round_trips_and_refuses_unsorted :
  (exists enc,
    write_plaintext witness_BackupProfile witness_BackupPlaintext = Some enc /\
    read_plaintext witness_BackupProfile enc = Some witness_BackupPlaintext) /\
  write_plaintext witness_BackupProfile
    {| pt_export_gen := 7;
       pt_source_profile := 1;
       pt_regions :=
         {| br_region_id := 2; br_schema_id := 10; br_schema_gen := 1;
            br_payload_len := 4; br_first_chunk := 0; br_chunk_count := 1 |} ::
         {| br_region_id := 2; br_schema_id := 10; br_schema_gen := 1;
            br_payload_len := 4; br_first_chunk := 1; br_chunk_count := 1 |} :: nil;
       pt_chunk_size := 64;
       pt_chunk_count := 2;
       pt_merkle_root := repeat_of 32 170 |} = None.
Proof.
  split; [eexists; split; reflexivity | reflexivity].
Qed.

Example export_view_filters_excluded_kinds :
  let mixed :=
    witness_SourceRegion ::
    {| sr_id := 2; sr_kind := RK_Fresh; sr_schema := SC_Bytes;
       sr_schema_id := 20; sr_schema_gen := 1; sr_payload := 9::nil |} ::
    {| sr_id := 3; sr_kind := RK_ConsentStore; sr_schema := SC_Bytes;
       sr_schema_id := 21; sr_schema_gen := 1; sr_payload := 8::nil |} ::
    {| sr_id := 4; sr_kind := RK_KeyHandle; sr_schema := SC_Key;
       sr_schema_id := 22; sr_schema_gen := 1; sr_payload := 7::nil |} ::
    {| sr_id := 5; sr_kind := RK_CredentialHandle; sr_schema := SC_CredentialHandle;
       sr_schema_id := 23; sr_schema_gen := 1; sr_payload := 6::nil |} ::
    {| sr_id := 6; sr_kind := RK_SealedObject; sr_schema := SC_SealedHandle;
       sr_schema_id := 24; sr_schema_gen := 1; sr_payload := 5::nil |} ::
    {| sr_id := 7; sr_kind := RK_Rollbackable; sr_schema := SC_Product SC_Scalar SC_Key;
       sr_schema_id := 25; sr_schema_gen := 1; sr_payload := 4::nil |} :: nil in
  build_export_view mixed = witness_ExportableEntry :: nil.
Proof. reflexivity. Qed.

Example fresh_initializers_deny_all_classes :
  can_spend_or_use_token (fresh_install_init FC_SpentPayment 5) 42 = false /\
  can_spend_or_use_token (fresh_install_init FC_ConsumedToken 5) 42 = false /\
  can_spend_or_use_token (fresh_install_init FC_OneTimeOp 5) 42 = false /\
  can_attempt_guess (fresh_install_init FC_AttemptCounter 5) = false /\
  can_spend_or_use_token (fresh_install_init FC_RevocationList 5) 42 = false /\
  can_spend_or_use_token (fresh_install_init FC_OtherFresh 5) 42 = false.
Proof. repeat split; reflexivity. Qed.

Example envelope_round_trips_and_refuses_trailing :
  exists enc,
    write_envelope witness_BackupProfile 0 witness_BackupEnvelope = Some enc /\
    read_envelope witness_BackupProfile 0 enc = Some witness_BackupEnvelope /\
    read_envelope witness_BackupProfile 0 (enc ++ (0 :: nil)) = None.
Proof.
  eexists. repeat split; reflexivity.
Qed.
