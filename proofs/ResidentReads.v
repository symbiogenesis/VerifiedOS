(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ResidentReads.v

   Bounded reservation reference for resident-window reads (R-10-006a,
   R-10-006b).

   Models one charged immutable backing, two independent holder slots, and one
   outstanding request per holder. Admission, current authority,
   boot/generation epoch, expiry, exact identity/window bounds, and finite
   request sequences are executable checks. Completion invokes an abstract
   verifier on the retained bytes and root without assuming verifier correctness
   or digest injectivity; a positive fixture verifier compares against
   independently specified byte and root values.

   Journals enumerate writes to abstract cells. Retirement takes barrier
   completion as an external Boolean input. Q44 still requires correspondence
   to the service and its concrete writes, models of replacement, renewal and
   crash recovery, and target WCET evidence.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-10-006a R-10-006b
   SHA256: 85f17ff41c76f5c615207dadeeea5de186f839aebc9785a8680033d6f38f91b2
   (*| END derived |*)
   ========================================================================= *)

From Stdlib Require Import Bool List Arith Lia.
Import ListNotations.
Local Open Scope nat_scope.

Inductive RootKind : Type := SystemImage | UserData.

Record Identity : Type := {
  owner : nat; domain : nat; object_id : nat; version : nat;
  root_kind : RootKind; generation : nat; root_digest : list nat
}.
Record Resident : Type := {
  resident_identity : Identity; resident_bytes : list nat; accepting : bool
}.
Record Handle : Type := {
  token : nat; boot_epoch : nat; holder : nat; handle_identity : Identity;
  window_start : nat; window_length : nat
}.
Record Reservation : Type := { reserved_handle : Handle; expires : nat }.
Record Request : Type := {
  request_handle : Handle; caller_domain : nat; supplied_identity : Identity;
  offset : nat; count : nat; request_sequence : nat
}.
Record Session : Type := {
  sequence : nat; pending : option Request; response : option (list nat);
  reads : nat; authentications : nat
}.
Record Common : Type := {
  backing : option Resident;
  reservations : nat -> option Reservation;
  authority : nat -> bool;
  next_token : nat; clock : nat; current_boot : nat; current_generation : nat;
  common_counter : nat
}.
Record State : Type := { common : Common; sessions : nat -> Session }.
Record Bounds : Type := {
  byte_bound : nat; read_bound : nat; retention_bound : nat; counter_bound : nat
}.

Definition identity_eq_dec (x y : Identity) : {x = y} + {x <> y}.
Proof. repeat decide equality. Defined.
Definition handle_eq_dec (x y : Handle) : {x = y} + {x <> y}.
Proof. decide equality; try apply identity_eq_dec; repeat decide equality. Defined.

Definition set {A : Type} (f : nat -> A) (i : nat) (v : A) : nat -> A :=
  fun j => if Nat.eq_dec j i then v else f j.
Definition set_session (s : State) (h : nat) (v : Session) : State :=
  {| common := common s; sessions := set (sessions s) h v |}.
Definition set_common (s : State) (c : Common) : State :=
  {| common := c; sessions := sessions s |}.
Definition with_response (s : Session) (r : option (list nat)) : Session :=
  {| sequence := sequence s; pending := pending s; response := r;
     reads := reads s; authentications := authentications s |}.
Definition clear_pending (s : Session) : Session :=
  {| sequence := sequence s; pending := None; response := None;
     reads := reads s; authentications := authentications s |}.
Definition interval (start length total : nat) : bool :=
  (start + length <=? total).
Definition slice (bytes : list nat) (start length : nat) : list nat :=
  firstn length (skipn start bytes).
Definition current_root (c : Common) (id : Identity) : bool :=
  match root_kind id with
  | SystemImage => generation id =? current_generation c
  | UserData => true
  end.
Definition bounds_ok (b : Bounds) : bool :=
  (0 <? byte_bound b) && (byte_bound b <=? 64) &&
  (0 <? read_bound b) && (read_bound b <=? byte_bound b) &&
  (0 <? retention_bound b) && (retention_bound b <=? counter_bound b) &&
  (counter_bound b <=? 255).

(* Admission requires a nonempty published backing within the byte budget,
   with each stored value in the byte range. *)
Definition resident_ok (b : Bounds) (r : Resident) : bool :=
  bounds_ok b && accepting r && (0 <? length (resident_bytes r)) &&
  (length (resident_bytes r) <=? byte_bound b) &&
  forallb (fun byte => byte <? 256) (resident_bytes r).

Definition live (c : Common) (h : Handle) (d : nat) (id : Identity) : bool :=
  match reservations c (holder h), backing c with
  | Some held, Some r =>
      if handle_eq_dec h (reserved_handle held) then
      if identity_eq_dec (handle_identity h) (resident_identity r) then
      if identity_eq_dec id (handle_identity h) then
        (holder h <? 2) && accepting r && authority c (holder h) &&
        (d =? domain (handle_identity h)) &&
        (boot_epoch h =? current_boot c) && (clock c <? expires held) &&
        current_root c (handle_identity h)
      else false else false else false
  | _, _ => false
  end.

Definition admit (b : Bounds) (s : State) (h d : nat) (id : Identity)
                 (start length : nat) : State * option Handle :=
  let c := common s in
  match backing c, reservations c h with
  | Some r, None =>
    if identity_eq_dec id (resident_identity r) then
    if resident_ok b r && (h <? 2) && authority c h && (d =? domain id) &&
       current_root c id && (0 <? length) &&
       interval start length (List.length (resident_bytes r)) &&
       (clock c + retention_bound b <=? counter_bound b) &&
       (next_token c <? counter_bound b) then
      let handle := {| token := S (next_token c); boot_epoch := current_boot c;
        holder := h; handle_identity := id; window_start := start;
        window_length := length |} in
      let held := {| reserved_handle := handle;
                     expires := clock c + retention_bound b |} in
      (set_common s {| backing := backing c;
        reservations := set (reservations c) h (Some held);
        authority := authority c; next_token := S (next_token c);
        clock := clock c; current_boot := current_boot c;
        current_generation := current_generation c; common_counter := common_counter c |},
       Some handle)
    else (s, None) else (s, None)
  | _, _ => (s, None)
  end.

Inductive Cell : Type :=
  | CommonCounter | CommonReservation (h : nat) | CommonBacking
  | PrivateSequence (h : nat) | PrivatePending (h : nat)
  | PrivateReads (h : nat) | PrivateAuthentications (h : nat)
  | RequestPublication (h : nat) | ResponsePublication (h : nat).
Definition is_common (cell : Cell) : bool :=
  match cell with
  | CommonCounter | CommonReservation _ | CommonBacking => true
  | _ => false
  end.
Definition no_common (writes : list Cell) : Prop :=
  Forall (fun cell => is_common cell = false) writes.
Record Outcome : Type := {
  after : State; payload : option (list nat); journal : list Cell
}.
Record Begun : Type := {
  begun_state : State; accepted : bool; begin_journal : list Cell
}.

Definition begin_read (b : Bounds) (s : State) (h : Handle) (d : nat)
                      (id : Identity) (off len : nat) : Begun :=
  if holder h <? 2 then
    let p := sessions s (holder h) in
    let cleared := set_session s (holder h) (with_response p None) in
    let writes := [ResponsePublication (holder h)] in
    match pending p with
    | Some _ => {| begun_state := cleared; accepted := false; begin_journal := writes |}
    | None =>
      if live (common s) h d id && (len <=? read_bound b) &&
         interval off len (window_length h) && (sequence p <? counter_bound b) then
        let q := {| request_handle := h; caller_domain := d; supplied_identity := id;
                    offset := off; count := len; request_sequence := S (sequence p) |} in
        {| begun_state := set_session s (holder h)
            {| sequence := S (sequence p); pending := Some q; response := None;
               reads := reads p; authentications := authentications p |};
           accepted := true;
           begin_journal := writes ++ [PrivateSequence (holder h); PrivatePending (holder h);
                                       RequestPublication (holder h)] |}
      else {| begun_state := cleared; accepted := false; begin_journal := writes |}
    end
  else {| begun_state := s; accepted := false; begin_journal := [] |}.

(* A matched completion checks current authority and the holder before calling
   the supplied verifier on the backing bytes and root. Verifier soundness is
   a separate obligation. *)
Definition complete (verify : list nat -> list nat -> bool)
                    (s : State) (h seq : nat) : Outcome :=
  let unchanged := {| after := s; payload := None; journal := [] |} in
  if h <? 2 then
    let p := sessions s h in
    match pending p with
    | None => unchanged
    | Some q =>
      if seq =? request_sequence q then
        let cleared := set_session s h (clear_pending p) in
        let writes := [ResponsePublication h; PrivatePending h; RequestPublication h] in
        let refused := {| after := cleared; payload := None; journal := writes |} in
        if live (common s) (request_handle q) (caller_domain q) (supplied_identity q) &&
           (holder (request_handle q) =? h) then
          match backing (common s) with
          | None => refused
          | Some r =>
            let checked := {| sequence := sequence p; pending := None; response := None;
               reads := reads p; authentications := S (authentications p) |} in
            if verify (resident_bytes r) (root_digest (resident_identity r)) then
              let bytes := slice (resident_bytes r)
                (window_start (request_handle q) + offset q) (count q) in
              {| after := set_session s h
                   {| sequence := sequence p; pending := None; response := Some bytes;
                      reads := S (reads p); authentications := S (authentications p) |};
                 payload := Some bytes;
                 journal := writes ++ [PrivateAuthentications h; PrivateReads h;
                                        ResponsePublication h] |}
            else {| after := set_session s h checked; payload := None;
                    journal := writes ++ [PrivateAuthentications h] |}
          end
        else refused
      else unchanged
    end
  else unchanged.

Definition read_once (verify : list nat -> list nat -> bool) (b : Bounds)
                     (s : State) (h : Handle) (d : nat) (id : Identity)
                     (off len : nat) : Outcome :=
  let begun := begin_read b s h d id off len in
  if accepted begun then
    let done := complete verify (begun_state begun) (holder h)
                 (sequence (sessions (begun_state begun) (holder h))) in
    {| after := after done; payload := payload done;
       journal := begin_journal begun ++ journal done |}
  else {| after := begun_state begun; payload := None; journal := begin_journal begun |}.

Fixpoint repeat_reads (verify : list nat -> list nat -> bool) (b : Bounds)
                      (n : nat) (s : State) (h : Handle) : State * list Cell :=
  match n with
  | 0 => (s, [])
  | S k =>
    let done := read_once verify b s h (domain (handle_identity h))
                  (handle_identity h) 0 (window_length h) in
    let rest := repeat_reads verify b k (after done) h in
    (fst rest, journal done ++ snd rest)
  end.

Definition revoke (s : State) (h : nat) : State :=
  let c := common s in
  set_common s {| backing := backing c; reservations := reservations c;
    authority := set (authority c) h false; next_token := next_token c;
    clock := clock c; current_boot := current_boot c;
    current_generation := current_generation c; common_counter := common_counter c |}.
Definition at_clock (s : State) (now : nat) : State :=
  let c := common s in
  set_common s {| backing := backing c; reservations := reservations c;
    authority := authority c; next_token := next_token c; clock := now;
    current_boot := current_boot c; current_generation := current_generation c;
    common_counter := common_counter c |}.

(* One transition closes admission and cancels both holders. Retirement keeps
   the closed backing charged until the supplied barrier result permits release. *)
Definition cancel_reservations (s : State) : State :=
  let c := common s in
  {| common := {| backing := option_map (fun r =>
        {| resident_identity := resident_identity r; resident_bytes := resident_bytes r;
           accepting := false |}) (backing c);
       reservations := fun _ => None; authority := authority c;
       next_token := next_token c; clock := clock c; current_boot := current_boot c;
       current_generation := current_generation c; common_counter := common_counter c |};
     sessions := fun h => clear_pending (sessions s h) |}.
Definition retire (s : State) (barrier_completed : bool) : State :=
  let closed := cancel_reservations s in
  if barrier_completed then
    let c := common closed in
    set_common closed {| backing := None; reservations := reservations c;
      authority := authority c; next_token := next_token c; clock := clock c;
      current_boot := current_boot c; current_generation := current_generation c;
      common_counter := common_counter c |}
  else closed.

(* Read-only lifetime observation, supplied an independent admission-time byte
   expectation. Changing bytes while identity stays fixed must still fail it. *)
Definition retained_identity (c : Common) (id : Identity) (expected : list nat) : Prop :=
  exists r, backing c = Some r /\ resident_identity r = id /\ resident_bytes r = expected.
Definition retains (s : State) (expected : list nat) : Prop :=
  (forall h held, h < 2 -> reservations (common s) h = Some held ->
     retained_identity (common s) (handle_identity (reserved_handle held)) expected) /\
  (forall h q, h < 2 -> pending (sessions s h) = Some q ->
     retained_identity (common s) (handle_identity (request_handle q)) expected).
Definition window_inside (c : Common) (h : Handle) : Prop :=
  exists r, backing c = Some r /\ resident_identity r = handle_identity h /\
    window_start h + window_length h <= length (resident_bytes r).

(* The following proofs establish framing, exact completion, sequence bounds
   and retirement behavior directly from the executable definitions. Record
   fields supply no preservation or safety conclusions. *)
Lemma set_same : forall (A : Type) (f : nat -> A) h v, set f h v h = v.
Proof. intros. unfold set. destruct (Nat.eq_dec h h); congruence. Qed.
Lemma set_other : forall (A : Type) (f : nat -> A) h v k,
  k <> h -> set f h v k = f k.
Proof. intros. unfold set. destruct (Nat.eq_dec k h); congruence. Qed.

Theorem begin_common_frame : forall b s h d id off len,
  common (begun_state (begin_read b s h d id off len)) = common s.
Proof.
  intros. unfold begin_read. destruct (holder h <? 2); [|reflexivity].
  destruct (pending (sessions s (holder h)));
    repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    reflexivity.
Qed.
Theorem complete_common_frame : forall verify s h seq,
  common (after (complete verify s h seq)) = common s.
Proof.
  intros. unfold complete. destruct (h <? 2); [|reflexivity].
  destruct (pending (sessions s h)); [|reflexivity].
  repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    destruct (backing (common s));
    repeat match goal with |- context [if ?b then _ else _] => destruct b end; reflexivity.
Qed.

Theorem begin_no_common_writes : forall b s h d id off len,
  no_common (begin_journal (begin_read b s h d id off len)).
Proof.
  intros. unfold begin_read. destruct (holder h <? 2);
    [destruct (pending (sessions s (holder h)))|];
    repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    repeat constructor.
Qed.
Theorem complete_no_common_writes : forall verify s h seq,
  no_common (journal (complete verify s h seq)).
Proof.
  intros. unfold complete. destruct (h <? 2);
    [destruct (pending (sessions s h))|];
    repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    try destruct (backing (common s));
    repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    repeat constructor.
Qed.
Theorem read_common_frame : forall verify b s h d id off len,
  common (after (read_once verify b s h d id off len)) = common s.
Proof.
  intros. unfold read_once. destruct (accepted (begin_read b s h d id off len)); simpl.
  - rewrite complete_common_frame. apply begin_common_frame.
  - apply begin_common_frame.
Qed.
Theorem read_no_common_writes : forall verify b s h d id off len,
  no_common (journal (read_once verify b s h d id off len)).
Proof.
  intros. unfold read_once. destruct (accepted (begin_read b s h d id off len)); simpl.
  - apply Forall_app. split; [apply begin_no_common_writes|apply complete_no_common_writes].
  - apply begin_no_common_writes.
Qed.
Theorem repeat_fixed_reservation : forall verify b n s h,
  common (fst (repeat_reads verify b n s h)) = common s /\
  no_common (snd (repeat_reads verify b n s h)).
Proof.
  intros verify b n. induction n as [|n IH]; intros s h; simpl.
  - split; [reflexivity|constructor].
  - destruct (IH (after (read_once verify b s h (domain (handle_identity h))
                      (handle_identity h) 0 (window_length h))) h) as [Hframe Hwrites].
    split.
    + rewrite Hframe. apply read_common_frame.
    + apply Forall_app. split; [apply read_no_common_writes|exact Hwrites].
Qed.

Theorem admission_installs_exact_window : forall b s h d id start len s' handle,
  admit b s h d id start len = (s', Some handle) ->
  exists r held,
    backing (common s') = Some r /\ resident_identity r = id /\
    handle_identity handle = id /\ holder handle = h /\
    window_start handle = start /\ window_length handle = len /\
    start + len <= length (resident_bytes r) /\ 0 < len /\
    h < 2 /\ d = domain id /\ authority (common s') h = true /\
    reservations (common s') h = Some held /\ reserved_handle held = handle /\
    token handle <= counter_bound b /\ expires held <= counter_bound b /\
    window_inside (common s') handle.
Proof.
  intros b s h d id start len s' handle H.
  unfold admit in H. destruct (backing (common s)) as [r|] eqn:Hr;
    [|discriminate]. destruct (reservations (common s) h); [discriminate|].
  destruct (identity_eq_dec id (resident_identity r)) as [Hid|Hid]; [|discriminate].
  match type of H with context [if ?test then _ else _] => destruct test eqn:Hadmit end;
    [|discriminate].
  inversion H; subst s' handle; clear H. repeat rewrite andb_true_iff in Hadmit.
  destruct Hadmit as [[[[[[[[Hresident Hholder] Hauth] Hdomain] Hroot] Hlen] Hwindow] Hexpiry] Htoken].
  apply Nat.ltb_lt in Hholder. apply Nat.ltb_lt in Hlen.
  apply Nat.ltb_lt in Htoken. apply Nat.eqb_eq in Hdomain.
  apply Nat.leb_le in Hexpiry. unfold interval in Hwindow. apply Nat.leb_le in Hwindow.
  exists r, {| reserved_handle := {| token := S (next_token (common s));
    boot_epoch := current_boot (common s); holder := h; handle_identity := id;
    window_start := start; window_length := len |};
    expires := clock (common s) + retention_bound b |}.
  simpl. rewrite set_same. repeat split; auto; try lia.
  exists r. repeat split; auto.
Qed.

Theorem begin_stores_bounded_request : forall b s h d id off len,
  accepted (begin_read b s h d id off len) = true ->
  exists q,
    pending (sessions (begun_state (begin_read b s h d id off len)) (holder h)) = Some q /\
    request_handle q = h /\ caller_domain q = d /\ supplied_identity q = id /\
    offset q = off /\ count q = len /\ off + len <= window_length h /\
    len <= read_bound b /\ live (common s) h d id = true /\
    request_sequence q = S (sequence (sessions s (holder h))) /\
    request_sequence q <= counter_bound b /\
    sequence (sessions (begun_state (begin_read b s h d id off len)) (holder h)) =
      request_sequence q.
Proof.
  intros b s h d id off len H. unfold begin_read in *.
  destruct (holder h <? 2); [|discriminate].
  destruct (pending (sessions s (holder h))); [discriminate|].
  match type of H with context [if ?test then _ else _] => destruct test eqn:Hok end;
    [|discriminate].
  apply andb_true_iff in Hok. destruct Hok as [Hok Hseq].
  apply andb_true_iff in Hok. destruct Hok as [Hok Hrange].
  apply andb_true_iff in Hok. destruct Hok as [Hlive Hlen].
  apply Nat.ltb_lt in Hseq. apply Nat.leb_le in Hlen.
  unfold interval in Hrange. apply Nat.leb_le in Hrange.
  exists {| request_handle := h; caller_domain := d; supplied_identity := id;
    offset := off; count := len; request_sequence := S (sequence (sessions s (holder h))) |}.
  simpl. rewrite set_same. simpl. repeat split; auto; lia.
Qed.

Theorem sequence_exhaustion_refuses : forall b s h d id off len,
  counter_bound b <= sequence (sessions s (holder h)) ->
  accepted (begin_read b s h d id off len) = false.
Proof.
  intros b s h d id off len H. destruct (accepted (begin_read b s h d id off len)) eqn:Hbegin;
    [|reflexivity]. apply begin_stores_bounded_request in Hbegin.
  destruct Hbegin as [q [_ [_ [_ [_ [_ [_ [_ [_ [_ [Hseq [Hbound _]]]]]]]]]]]]. lia.
Qed.

Theorem completion_exact : forall verify s h seq bytes,
  payload (complete verify s h seq) = Some bytes ->
  exists q r,
    pending (sessions s h) = Some q /\ seq = request_sequence q /\ h < 2 /\
    holder (request_handle q) = h /\
    live (common s) (request_handle q) (caller_domain q) (supplied_identity q) = true /\
    backing (common s) = Some r /\
    verify (resident_bytes r) (root_digest (resident_identity r)) = true /\
    bytes = slice (resident_bytes r) (window_start (request_handle q) + offset q) (count q).
Proof.
  intros verify s h seq bytes H. unfold complete in H.
  destruct (h <? 2) eqn:Hholder; [|discriminate].
  destruct (pending (sessions s h)) as [q|] eqn:Hpending; [|discriminate].
  destruct (seq =? request_sequence q) eqn:Hseq; [|discriminate].
  destruct (live (common s) (request_handle q) (caller_domain q) (supplied_identity q) &&
            (holder (request_handle q) =? h)) eqn:Hlive; [|discriminate].
  destruct (backing (common s)) as [r|] eqn:Hr; [|discriminate].
  destruct (verify (resident_bytes r) (root_digest (resident_identity r))) eqn:Hverify;
    [|discriminate]. inversion H; subst bytes.
  apply Nat.ltb_lt in Hholder. apply Nat.eqb_eq in Hseq.
  apply andb_true_iff in Hlive. destruct Hlive as [Hlive Heq].
  apply Nat.eqb_eq in Heq. exists q, r. repeat split; auto.
Qed.

Theorem stale_completion_unchanged : forall verify s h seq q,
  pending (sessions s h) = Some q -> seq <> request_sequence q ->
  after (complete verify s h seq) = s /\
  payload (complete verify s h seq) = None /\ journal (complete verify s h seq) = [].
Proof.
  intros. unfold complete. destruct (h <? 2); [|repeat split; reflexivity].
  rewrite H. destruct (seq =? request_sequence q) eqn:Hseq;
    [apply Nat.eqb_eq in Hseq; contradiction|repeat split; reflexivity].
Qed.

Theorem current_authority_refuses : forall verify s h seq q,
  pending (sessions s h) = Some q ->
  live (common s) (request_handle q) (caller_domain q) (supplied_identity q) = false ->
  payload (complete verify s h seq) = None.
Proof.
  intros. unfold complete. destruct (h <? 2); [|reflexivity].
  rewrite H. destruct (seq =? request_sequence q); [|reflexivity].
  rewrite H0. reflexivity.
Qed.
Theorem failed_authentication_refuses : forall verify s h seq r,
  backing (common s) = Some r ->
  verify (resident_bytes r) (root_digest (resident_identity r)) = false ->
  payload (complete verify s h seq) = None.
Proof.
  intros. unfold complete. destruct (h <? 2); [|reflexivity].
  destruct (pending (sessions s h)); [|reflexivity].
  repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    rewrite ?H, ?H0; reflexivity.
Qed.

Theorem retirement_cancels : forall s barrier h,
  reservations (common (retire s barrier)) h = None /\
  pending (sessions (retire s barrier) h) = None /\
  sequence (sessions (retire s barrier) h) = sequence (sessions s h).
Proof. intros. unfold retire. destruct barrier; repeat split; reflexivity. Qed.
Theorem unavailable_barrier_keeps_backing : forall s r,
  backing (common s) = Some r ->
  backing (common (retire s false)) =
    Some {| resident_identity := resident_identity r; resident_bytes := resident_bytes r;
            accepting := false |}.
Proof. intros. unfold retire, cancel_reservations, set_common; simpl. rewrite H. reflexivity. Qed.

(* A matched completion can only remove its holder's pending request. Other
   sessions and the entire common state remain framed, even on refusal. *)
Theorem completion_removes_or_preserves_pending : forall verify s h seq k,
  pending (sessions (after (complete verify s h seq)) k) = None \/
  pending (sessions (after (complete verify s h seq)) k) = pending (sessions s k).
Proof.
  intros. unfold complete. destruct (h <? 2); [|right; reflexivity].
  destruct (pending (sessions s h)); [|right; reflexivity].
  destruct (seq =? request_sequence r); [|right; reflexivity].
  destruct (Nat.eq_dec k h) as [Heq|Hneq].
  - subst k. repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      destruct (backing (common s));
      repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      simpl; rewrite set_same; simpl;
      repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      left; reflexivity.
  - repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      destruct (backing (common s));
      repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      simpl; rewrite set_other by exact Hneq;
      repeat match goal with |- context [if ?b then _ else _] => destruct b end;
      right; reflexivity.
Qed.
Theorem completion_retains : forall verify s h seq expected,
  retains s expected -> retains (after (complete verify s h seq)) expected.
Proof.
  intros verify s h seq expected [Hheld Hpending]. split.
  - intros. rewrite complete_common_frame in *. eapply Hheld; eauto.
  - intros k q Hk Hq. destruct (completion_removes_or_preserves_pending verify s h seq k)
      as [Hnone|Hsame].
    + rewrite Hnone in Hq. discriminate.
    + rewrite Hsame in Hq. unfold retained_identity.
      rewrite complete_common_frame. apply (Hpending k q Hk Hq).
Qed.
Theorem begun_request_within_backing : forall b s h d id off len,
  window_inside (common s) h ->
  accepted (begin_read b s h d id off len) = true ->
  exists q r,
    pending (sessions (begun_state (begin_read b s h d id off len)) (holder h)) = Some q /\
    backing (common (begun_state (begin_read b s h d id off len))) = Some r /\
    resident_identity r = handle_identity (request_handle q) /\
    window_start (request_handle q) + offset q + count q <= length (resident_bytes r).
Proof.
  intros b s h d id off len [r [Hr [Hid Hwindow]]] Hbegin.
  destruct (begin_stores_bounded_request b s h d id off len Hbegin)
    as [q [Hq [Hhandle [_ [_ [Hoff [Hlen [Hrange _]]]]]]]].
  exists q, r. rewrite begin_common_frame. repeat split; auto.
  - rewrite Hhandle. exact Hid.
  - rewrite Hhandle, Hoff, Hlen. lia.
Qed.

(* The exact completion theorem is about any state. This corollary supplies its
   non-forged pending-request provenance from executable begin, and admission's
   window theorem supplies window_inside. It assumes no preservation conclusion. *)
Theorem admitted_completion_within_window : forall verify b s h d id off len seq bytes,
  window_inside (common s) h ->
  accepted (begin_read b s h d id off len) = true ->
  payload (complete verify (begun_state (begin_read b s h d id off len)) (holder h) seq) = Some bytes ->
  exists r,
    backing (common s) = Some r /\ resident_identity r = handle_identity h /\
    window_start h + off + len <= length (resident_bytes r) /\
    bytes = slice (resident_bytes r) (window_start h + off) len.
Proof.
  intros verify b s h d id off len seq bytes Hwindow Hbegin Hdone.
  destruct (begin_stores_bounded_request b s h d id off len Hbegin)
    as [q [Hq [Hhandle [_ [_ [Hoff [Hlen [Hrange _]]]]]]]].
  destruct (completion_exact verify (begun_state (begin_read b s h d id off len))
             (holder h) seq bytes Hdone)
    as [actual [r [Hactual [_ [_ [_ [_ [Hr [_ Hbytes]]]]]]]]].
  rewrite Hq in Hactual. inversion Hactual; subst actual.
  rewrite begin_common_frame in Hr.
  destruct Hwindow as [old [Hold [Hid Hbound]]].
  rewrite Hr in Hold. inversion Hold; subst old.
  exists r. repeat split; auto.
  - lia.
  - rewrite Hhandle, Hoff, Hlen in Hbytes. exact Hbytes.
Qed.

Definition fixture_bounds : Bounds :=
  {| byte_bound := 8; read_bound := 3; retention_bound := 4; counter_bound := 15 |}.
Definition fixture_identity (kind : RootKind) : Identity :=
  {| owner := 1; domain := 7; object_id := 1; version := 1;
     root_kind := kind; generation := 1; root_digest := [11; 22] |}.
Definition fixture_resident (kind : RootKind) : Resident :=
  {| resident_identity := fixture_identity kind; resident_bytes := [97; 98; 99]; accepting := true |}.
Definition empty_session : Session :=
  {| sequence := 0; pending := None; response := None; reads := 0; authentications := 0 |}.
Definition initial (kind : RootKind) : State :=
  {| common := {| backing := Some (fixture_resident kind); reservations := fun _ => None;
     authority := fun _ => true; next_token := 0; clock := 0; current_boot := 0;
     current_generation := 1; common_counter := 0 |}; sessions := fun _ => empty_session |}.
Definition fixture_handle (kind : RootKind) (h : nat) : Handle :=
  {| token := S h; boot_epoch := 0; holder := h; handle_identity := fixture_identity kind;
     window_start := h; window_length := 3 - h |}.
Definition fixture_reservation (kind : RootKind) (h : nat) : Reservation :=
  {| reserved_handle := fixture_handle kind h; expires := 4 |}.
Definition one_holder (kind : RootKind) : State :=
  fst (admit fixture_bounds (initial kind) 0 7 (fixture_identity kind) 0 3).
Definition two_holders (kind : RootKind) : State :=
  fst (admit fixture_bounds (one_holder kind) 1 7 (fixture_identity kind) 1 2).
Definition fixture_verify (bytes digest : list nat) : bool :=
  if list_eq_dec Nat.eq_dec bytes [97; 98; 99] then
    if list_eq_dec Nat.eq_dec digest [11; 22] then true else false else false.
Definition read_fixture (kind : RootKind) (s : State) (h off len : nat) : Outcome :=
  read_once fixture_verify fixture_bounds s (fixture_handle kind h) 7 (fixture_identity kind) off len.
Definition two_pending (kind : RootKind) : State :=
  begun_state (begin_read fixture_bounds
    (begun_state (begin_read fixture_bounds (two_holders kind)
      (fixture_handle kind 0) 7 (fixture_identity kind) 0 3))
    (fixture_handle kind 1) 7 (fixture_identity kind) 0 2).
Definition with_bytes (s : State) (bytes : list nat) : State :=
  let c := common s in
  set_common s {| backing := option_map (fun r => {| resident_identity := resident_identity r;
    resident_bytes := bytes; accepting := accepting r |}) (backing c);
    reservations := reservations c; authority := authority c; next_token := next_token c;
    clock := clock c; current_boot := current_boot c; current_generation := current_generation c;
    common_counter := common_counter c |}.

Definition witness_Identity : Identity := fixture_identity UserData.
Definition witness_Resident : Resident := fixture_resident UserData.
Definition witness_Handle : Handle := fixture_handle UserData 0.
Definition witness_Reservation : Reservation := fixture_reservation UserData 0.
Definition witness_Request : Request := {| request_handle := witness_Handle;
  caller_domain := 7; supplied_identity := witness_Identity; offset := 0; count := 3;
  request_sequence := 1 |}.
Definition witness_Session : Session := empty_session.
Definition witness_Common : Common := common (two_holders UserData).
Definition witness_State : State := two_holders UserData.
Definition witness_Bounds : Bounds := fixture_bounds.
Definition witness_Outcome : Outcome := read_fixture UserData (two_holders UserData) 0 0 3.
Definition witness_Begun : Begun := begin_read fixture_bounds (two_holders UserData)
  (fixture_handle UserData 0) 7 (fixture_identity UserData) 0 3.

(* Both root kinds use the same transitions. The fixture verifier has explicit
   independent expected bytes and root; it is not a SHA-256 implementation. *)
Example two_independent_admissions : forall kind,
  admit fixture_bounds (initial kind) 0 7 (fixture_identity kind) 0 3 =
    (one_holder kind, Some (fixture_handle kind 0)) /\
  admit fixture_bounds (one_holder kind) 1 7 (fixture_identity kind) 1 2 =
    (two_holders kind, Some (fixture_handle kind 1)).
Proof. intros []; vm_compute; split; reflexivity. Qed.
Example exact_independent_payloads : forall kind,
  payload (read_fixture kind (two_holders kind) 0 0 3) = Some [97; 98; 99] /\
  payload (read_fixture kind (two_holders kind) 1 0 2) = Some [98; 99] /\
  payload (read_fixture kind (two_holders kind) 0 3 0) = Some [].
Proof. intros []; vm_compute; repeat split; reflexivity. Qed.
Example two_accepted_transfers : forall kind,
  payload (complete fixture_verify (two_pending kind) 0 1) = Some [97; 98; 99] /\
  payload (complete fixture_verify (two_pending kind) 1 1) = Some [98; 99].
Proof. intros []; vm_compute; split; reflexivity. Qed.
Example repeated_reads_with_fixed_admissions : forall kind,
  let s := fst (repeat_reads fixture_verify fixture_bounds 3 (two_holders kind) (fixture_handle kind 0)) in
  let t := fst (repeat_reads fixture_verify fixture_bounds 3 s (fixture_handle kind 1)) in
  reads (sessions t 0) = 3 /\ reads (sessions t 1) = 3 /\
  response (sessions t 0) = Some [97; 98; 99] /\ response (sessions t 1) = Some [98; 99] /\
  next_token (common t) = 2.
Proof. intros []; vm_compute; repeat split; reflexivity. Qed.
Example revoked_inflight_read_refuses : forall kind,
  payload (complete fixture_verify (revoke (two_pending kind) 0) 0 1) = None /\
  payload (complete fixture_verify (revoke (two_pending kind) 0) 1 1) = Some [98; 99].
Proof. intros []; vm_compute; split; reflexivity. Qed.
Example expired_inflight_read_refuses : forall kind,
  payload (complete fixture_verify (at_clock (two_pending kind) 4) 0 1) = None.
Proof. intros []; vm_compute; reflexivity. Qed.
Example corrupt_retained_bytes_refuse_authentication : forall kind,
  payload (complete fixture_verify (with_bytes (two_pending kind) [0; 0; 0]) 0 1) = None /\
  payload (complete fixture_verify (with_bytes (two_pending kind) [0; 0; 0]) 1 1) = None.
Proof. intros []; vm_compute; split; reflexivity. Qed.
Example omitted_authentication_serves_wrong_bytes : forall kind,
  payload (complete (fun _ _ => true) (with_bytes (two_pending kind) [0; 0; 0]) 0 1) = Some [0; 0; 0].
Proof. intros []; vm_compute; reflexivity. Qed.
Example wrong_domain_refuses : forall kind,
  payload (read_once fixture_verify fixture_bounds (two_holders kind)
    (fixture_handle kind 0) 8 (fixture_identity kind) 0 3) = None.
Proof. intros []; vm_compute; reflexivity. Qed.
Example wrong_version_and_root_refuse : forall kind,
  let wrong_version := {| owner := 1; domain := 7; object_id := 1; version := 2;
    root_kind := kind; generation := 1; root_digest := [11; 22] |} in
  let wrong_root := {| owner := 1; domain := 7; object_id := 1; version := 1;
    root_kind := kind; generation := 1; root_digest := [22; 11] |} in
  payload (read_once fixture_verify fixture_bounds (two_holders kind)
    (fixture_handle kind 0) 7 wrong_version 0 3) = None /\
  payload (read_once fixture_verify fixture_bounds (two_holders kind)
    (fixture_handle kind 0) 7 wrong_root 0 3) = None.
Proof. intros []; vm_compute; split; reflexivity. Qed.
Example outside_window_refuses : forall kind,
  payload (read_fixture kind (two_holders kind) 1 1 2) = None.
Proof. intros []; vm_compute; reflexivity. Qed.
Example stale_completion_keeps_successor : forall kind,
  let first := read_fixture kind (two_holders kind) 0 0 3 in
  let successor := begun_state (begin_read fixture_bounds (after first)
    (fixture_handle kind 0) 7 (fixture_identity kind) 0 3) in
  after (complete fixture_verify successor 0 1) = successor /\
  journal (complete fixture_verify successor 0 1) = [] /\
  payload (complete fixture_verify successor 0 2) = Some [97; 98; 99].
Proof. intros []; vm_compute; repeat split; reflexivity. Qed.
Example expired_system_generation_refuses :
  let s := two_pending SystemImage in
  let c := common s in
  let changed := set_common s {| backing := backing c; reservations := reservations c;
    authority := authority c; next_token := next_token c; clock := clock c;
    current_boot := current_boot c; current_generation := 2; common_counter := common_counter c |} in
  payload (complete fixture_verify changed 0 1) = None.
Proof. vm_compute; reflexivity. Qed.
Example retirement_does_not_wait_for_holders : forall kind,
  payload (complete fixture_verify (retire (two_pending kind) false) 0 1) = None /\
  payload (complete fixture_verify (retire (two_pending kind) false) 1 1) = None /\
  backing (common (retire (two_pending kind) false)) =
    Some {| resident_identity := fixture_identity kind; resident_bytes := [97; 98; 99]; accepting := false |}.
Proof. intros []; vm_compute; repeat split; reflexivity. Qed.

Lemma fixture_retains_reservations_and_transfers : forall kind,
  retains (two_pending kind) [97; 98; 99].
Proof.
  intros kind. split; intros h value Hh Hvalue;
    assert (h = 0 \/ h = 1) as Hcases by lia; destruct Hcases; subst h;
    destruct kind; vm_compute in Hvalue; inversion Hvalue; subst value;
    unfold retained_identity; eexists; repeat split; vm_compute; reflexivity.
Qed.
Theorem same_identity_mutation_breaks_live_retention : forall kind,
  ~ retains (with_bytes (two_pending kind) [0; 0; 0]) [97; 98; 99].
Proof.
  intros kind [Hheld _].
  assert (reservations (common (with_bytes (two_pending kind) [0; 0; 0])) 0 =
          Some (fixture_reservation kind 0)) as Hreservation.
  { destruct kind; vm_compute; reflexivity. }
  specialize (Hheld 0 (fixture_reservation kind 0) ltac:(lia) Hreservation).
  destruct Hheld as [r [Hr [_ Hbytes]]]. destruct kind; vm_compute in Hr;
    inversion Hr; subst r; discriminate Hbytes.
Qed.
Theorem retained_transfer_mutation_is_detected_without_reservation : forall kind,
  let changed := with_bytes (two_pending kind) [0; 0; 0] in
  let c := common changed in
  let no_reservations := set_common changed {| backing := backing c;
    reservations := fun _ => None; authority := authority c; next_token := next_token c;
    clock := clock c; current_boot := current_boot c; current_generation := current_generation c;
    common_counter := common_counter c |} in
  ~ retains no_reservations [97; 98; 99].
Proof.
  intros kind changed c no_reservations [_ Hpending].
  specialize (Hpending 0 {| request_handle := fixture_handle kind 0; caller_domain := 7;
    supplied_identity := fixture_identity kind; offset := 0; count := 3; request_sequence := 1 |} ltac:(lia)).
  destruct kind; vm_compute in Hpending.
  -
    specialize (Hpending (eq_refl _)). destruct Hpending as [r [Hr [_ Hbytes]]].
    inversion Hr; subst r; discriminate Hbytes.
  - specialize (Hpending (eq_refl _)). destruct Hpending as [r [Hr [_ Hbytes]]].
    inversion Hr; subst r; discriminate Hbytes.
Qed.
Theorem common_increment_then_decrement_is_rejected : forall writes,
  ~ no_common ([CommonCounter; CommonCounter] ++ writes).
Proof. intros writes H. inversion H. discriminate. Qed.
Theorem refused_begin_preserves_pending : forall b s h d id off len q,
  pending (sessions s (holder h)) = Some q ->
  pending (sessions (begun_state (begin_read b s h d id off len)) (holder h)) = Some q.
Proof.
  intros. unfold begin_read. destruct (holder h <? 2); [|exact H].
  rewrite H. simpl. rewrite set_same. exact H.
Qed.
Theorem complete_preserves_sequences : forall verify s h seq k,
  sequence (sessions (after (complete verify s h seq)) k) = sequence (sessions s k).
Proof.
  intros. unfold complete. destruct (h <? 2); [|reflexivity].
  destruct (pending (sessions s h)); [|reflexivity].
  destruct (seq =? request_sequence r); [|reflexivity].
  repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    destruct (backing (common s));
    repeat match goal with |- context [if ?b then _ else _] => destruct b end;
    simpl; unfold set; destruct (Nat.eq_dec k h); subst; reflexivity.
Qed.

(* Explicit close, renewal, crash, and fresh-token readmission lifecycle
   transitions and proofs (Q44). *)
Definition close_reservation (s : State) (h : Handle) : State * bool :=
  let c := common s in
  if holder h <? 2 then
    match reservations c (holder h) with
    | Some held =>
      if handle_eq_dec h (reserved_handle held) then
        ({| common := {| backing := backing c;
                         reservations := set (reservations c) (holder h) None;
                         authority := authority c;
                         next_token := next_token c;
                         clock := clock c;
                         current_boot := current_boot c;
                         current_generation := current_generation c;
                         common_counter := common_counter c |};
            sessions := set (sessions s) (holder h) (clear_pending (sessions s (holder h))) |},
         true)
      else (s, false)
    | None => (s, false)
    end
  else (s, false).

Definition renew_reservation (b : Bounds) (s : State) (h : Handle)
                             (d : nat) (id : Identity) : State * bool :=
  let c := common s in
  if live c h d id && (clock c + retention_bound b <=? counter_bound b) then
    match reservations c (holder h) with
    | Some held =>
      if expires held <? clock c + retention_bound b then
        let updated := {| reserved_handle := reserved_handle held;
                          expires := clock c + retention_bound b |} in
        (set_common s {| backing := backing c;
                         reservations := set (reservations c) (holder h) (Some updated);
                         authority := authority c;
                         next_token := next_token c;
                         clock := clock c;
                         current_boot := current_boot c;
                         current_generation := current_generation c;
                         common_counter := common_counter c |},
         true)
      else (s, false)
    | None => (s, false)
    end
  else (s, false).

Definition crash (s : State) : State :=
  let c := common s in
  {| common := {| backing := option_map (fun r =>
        {| resident_identity := resident_identity r; resident_bytes := resident_bytes r;
           accepting := false |}) (backing c);
       reservations := fun _ => None; authority := authority c;
       next_token := next_token c; clock := clock c;
       current_boot := S (current_boot c);
       current_generation := current_generation c; common_counter := common_counter c |};
     sessions := fun h => clear_pending (sessions s h) |}.

Theorem close_preserves_backing_and_peer : forall s h s' ok,
  close_reservation s h = (s', ok) ->
  backing (common s') = backing (common s) /\
  next_token (common s') = next_token (common s) /\
  authority (common s') = authority (common s) /\
  clock (common s') = clock (common s) /\
  current_boot (common s') = current_boot (common s) /\
  current_generation (common s') = current_generation (common s) /\
  common_counter (common s') = common_counter (common s) /\
  (forall k, sequence (sessions s' k) = sequence (sessions s k)) /\
  (forall k, k <> holder h ->
     reservations (common s') k = reservations (common s) k /\
     sessions s' k = sessions s k).
Proof.
  intros s h s' ok H. unfold close_reservation in H.
  destruct (holder h <? 2);
    [destruct (reservations (common s) (holder h)) as [held|]|].
  - destruct (handle_eq_dec h (reserved_handle held));
      inversion H; subst s' ok; clear H; simpl;
      repeat split; try reflexivity;
      try (intros k; unfold set; destruct (Nat.eq_dec k (holder h)); [subst; reflexivity|reflexivity]);
      try (rewrite set_other by assumption; reflexivity).
  - inversion H; subst s' ok; clear H; repeat split; try reflexivity;
      intros; reflexivity.
  - inversion H; subst s' ok; clear H; repeat split; try reflexivity;
      intros; reflexivity.
Qed.

Theorem close_invalidates_handle : forall s h s',
  close_reservation s h = (s', true) ->
  holder h < 2 /\
  reservations (common s') (holder h) = None /\
  pending (sessions s' (holder h)) = None /\
  (forall d id, live (common s') h d id = false) /\
  (forall verify seq, payload (complete verify s' (holder h) seq) = None) /\
  (forall b d id off len, accepted (begin_read b s' h d id off len) = false).
Proof.
  intros s h s' H. unfold close_reservation in H.
  destruct (holder h <? 2) eqn:Hslot; [|discriminate].
  destruct (reservations (common s) (holder h)) as [held|]; [|discriminate].
  destruct (handle_eq_dec h (reserved_handle held)); [|discriminate].
  inversion H; subst s'; clear H.
  apply Nat.ltb_lt in Hslot.
  repeat split.
  - exact Hslot.
  - simpl. apply set_same.
  - simpl. rewrite set_same. reflexivity.
  - intros d id. unfold live. simpl. rewrite set_same. reflexivity.
  - intros verify seq. unfold complete. simpl. rewrite set_same.
    destruct (holder h <? 2); reflexivity.
  - intros b d id off len. unfold begin_read.
    destruct (holder h <? 2); [|reflexivity].
    simpl. rewrite set_same. simpl.
    unfold live. simpl. rewrite set_same. reflexivity.
Qed.

Theorem close_refusal_preserves_state : forall s h s',
  close_reservation s h = (s', false) ->
  s' = s.
Proof.
  intros s h s' H. unfold close_reservation in H.
  destruct (holder h <? 2);
    [destruct (reservations (common s) (holder h))|];
    [destruct (handle_eq_dec h (reserved_handle r))| |];
    inversion H; reflexivity.
Qed.

Theorem renew_preserves_sessions_and_peer : forall b s h d id s',
  renew_reservation b s h d id = (s', true) ->
  sessions s' = sessions s /\
  backing (common s') = backing (common s) /\
  next_token (common s') = next_token (common s) /\
  authority (common s') = authority (common s) /\
  clock (common s') = clock (common s) /\
  current_boot (common s') = current_boot (common s) /\
  current_generation (common s') = current_generation (common s) /\
  common_counter (common s') = common_counter (common s) /\
  (forall k, k <> holder h -> reservations (common s') k = reservations (common s) k) /\
  live (common s') h d id = true /\
  exists held held',
    reservations (common s) (holder h) = Some held /\
    reservations (common s') (holder h) = Some held' /\
    reserved_handle held' = reserved_handle held /\
    expires held < expires held' /\
    expires held' = clock (common s) + retention_bound b /\
    expires held' <= counter_bound b.
Proof.
  intros b s h d id s' H. unfold renew_reservation in H.
  destruct (live (common s) h d id && (clock (common s) + retention_bound b <=? counter_bound b))
    eqn:Hguard; [|discriminate].
  apply andb_true_iff in Hguard. destruct Hguard as [Hlive Hbound].
  apply Nat.leb_le in Hbound.
  destruct (reservations (common s) (holder h)) as [held|] eqn:Hres; [|discriminate].
  destruct (expires held <? clock (common s) + retention_bound b) eqn:Hext; [|discriminate].
  apply Nat.ltb_lt in Hext.
  inversion H; subst s'; clear H.
  assert (Hlive_copy : live (common s) h d id = true) by exact Hlive.
  unfold live in Hlive_copy. rewrite Hres in Hlive_copy.
  destruct (backing (common s)) as [r|] eqn:Hback; [|discriminate].
  destruct (handle_eq_dec h (reserved_handle held)) as [Hhandle|]; [|discriminate].
  destruct (identity_eq_dec (handle_identity h) (resident_identity r)) as [Hid1|]; [|discriminate].
  destruct (identity_eq_dec id (handle_identity h)) as [Hid2|]; [|discriminate].
  repeat rewrite andb_true_iff in Hlive_copy.
  destruct Hlive_copy as [[[[[[Hholder Hacc] Hauth] Hdom] Hboot] Hclk] Hroot].
  apply Nat.ltb_lt in Hclk.
  assert (Hnew_clk : (clock (common s) <? clock (common s) + retention_bound b) = true).
  { apply Nat.ltb_lt. lia. }
  repeat split; try reflexivity.
  - intros k Hk. simpl. apply set_other. exact Hk.
  - unfold live. simpl. rewrite set_same. simpl.
    destruct (handle_eq_dec h (reserved_handle held)); [|contradiction].
    destruct (identity_eq_dec (handle_identity h) (resident_identity r)); [|contradiction].
    destruct (identity_eq_dec id (handle_identity h)); [|contradiction].
    unfold current_root in Hroot |- *. simpl.
    repeat rewrite andb_true_iff. repeat split; assumption.
  - exists held, {| reserved_handle := reserved_handle held;
                    expires := clock (common s) + retention_bound b |}.
    simpl. rewrite set_same. repeat split; try reflexivity; lia.
Qed.

Theorem renew_refusal_preserves_state : forall b s h d id s',
  renew_reservation b s h d id = (s', false) ->
  s' = s.
Proof.
  intros b s h d id s' H. unfold renew_reservation in H.
  destruct (live (common s) h d id && (clock (common s) + retention_bound b <=? counter_bound b));
    [destruct (reservations (common s) (holder h)) as [held|]|];
    [destruct (expires held <? clock (common s) + retention_bound b)| |];
    inversion H; reflexivity.
Qed.

Theorem crash_invalidates_all_and_preserves_sequences : forall s,
  current_boot (common (crash s)) = S (current_boot (common s)) /\
  (forall k, reservations (common (crash s)) k = None) /\
  (forall k, pending (sessions (crash s) k) = None) /\
  (forall k, sequence (sessions (crash s) k) = sequence (sessions s k)) /\
  (forall h d id, live (common (crash s)) h d id = false) /\
  (forall verify k seq, payload (complete verify (crash s) k seq) = None) /\
  (forall b h d id off len, accepted (begin_read b (crash s) h d id off len) = false) /\
  (forall r, backing (common s) = Some r ->
     backing (common (crash s)) =
       Some {| resident_identity := resident_identity r;
               resident_bytes := resident_bytes r;
               accepting := false |}) /\
  (backing (common s) = None -> backing (common (crash s)) = None) /\
  (forall b h d id start len, admit b (crash s) h d id start len = (crash s, None)).
Proof.
  intros s. repeat split; try reflexivity.
  - intros verify k seq. unfold complete, crash. simpl.
    destruct (k <? 2); reflexivity.
  - intros b h d id off len. unfold begin_read, crash. simpl.
    destruct (holder h <? 2); [|reflexivity].
    unfold live. simpl. reflexivity.
  - intros r Hr. unfold crash. simpl. rewrite Hr. reflexivity.
  - intros Hnone. unfold crash. simpl. rewrite Hnone. reflexivity.
  - intros b h d id start len. unfold admit, crash. simpl.
    destruct (backing (common s)) as [r|]; [|reflexivity].
    simpl. destruct (identity_eq_dec id (resident_identity r)); [|reflexivity].
    unfold resident_ok. simpl. rewrite andb_false_r. reflexivity.
Qed.

Theorem readmit_after_close_allocates_fresh_token : forall b s h d id start len s' s'' h',
  token h <= next_token (common s) ->
  close_reservation s h = (s', true) ->
  admit b s' (holder h) d id start len = (s'', Some h') ->
  token h < token h' /\
  h <> h' /\
  close_reservation s'' h = (s'', false) /\
  (forall d' id', live (common s'') h d' id' = false).
Proof.
  intros b s h d id start len s' s'' h' Htok Hclose Hadmit.
  pose proof (close_preserves_backing_and_peer s h s' true Hclose)
    as [_ [Hnext _]].
  pose proof (close_invalidates_handle s h s' Hclose)
    as [Hslot [Hres' _]].
  unfold admit in Hadmit.
  destruct (backing (common s')) as [r|] eqn:Hback'; [|discriminate].
  rewrite Hres' in Hadmit.
  destruct (identity_eq_dec id (resident_identity r)); [|discriminate].
  match type of Hadmit with context [if ?test then _ else _] => destruct test; [|discriminate] end.
  inversion Hadmit; subst s'' h'; clear Hadmit.
  assert (Hfresh : token h < S (next_token (common s'))).
  { rewrite Hnext. lia. }
  assert (Hneq : h <> {| token := S (next_token (common s'));
                          boot_epoch := current_boot (common s');
                          holder := holder h;
                          handle_identity := id;
                          window_start := start;
                          window_length := len |}).
  { intro Heq. assert (Htok_eq : token h = S (next_token (common s')))
      by (rewrite Heq; reflexivity). lia. }
  repeat split.
  - exact Hfresh.
  - exact Hneq.
  - unfold close_reservation. simpl.
    destruct (holder h <? 2) eqn:Hslot_b;
      [|apply Nat.ltb_lt in Hslot; rewrite Hslot in Hslot_b; discriminate].
    rewrite set_same.
    match goal with
    | |- (if handle_eq_dec h ?rhs then _ else _) = _ =>
        destruct (handle_eq_dec h rhs) as [Heq|Hne]; [exfalso; apply Hneq; exact Heq|reflexivity]
    end.
  - intros d' id'. unfold live. simpl.
    rewrite set_same.
    match goal with
    | |- (if handle_eq_dec h ?rhs then _ else _) = _ =>
        destruct (handle_eq_dec h rhs) as [Heq|Hne]; [exfalso; apply Hneq; exact Heq|reflexivity]
    end.
Qed.

Example close_preserves_peer_and_allows_readmit_witness : forall kind,
  let closed := close_reservation (two_pending kind) (fixture_handle kind 0) in
  let s1 := fst closed in
  let readmitted := admit fixture_bounds s1 0 7 (fixture_identity kind) 0 3 in
  let s2 := fst readmitted in
  snd closed = true /\
  reservations (common s1) 0 = None /\
  pending (sessions s1 0) = None /\
  close_reservation s1 (fixture_handle kind 0) = (s1, false) /\
  live (common s1) (fixture_handle kind 0) 7 (fixture_identity kind) = false /\
  payload (complete fixture_verify s1 1 1) = Some [98; 99] /\
  (exists h_new,
     snd readmitted = Some h_new /\
     token h_new = 3 /\
     close_reservation s2 (fixture_handle kind 0) = (s2, false) /\
     live (common s2) (fixture_handle kind 0) 7 (fixture_identity kind) = false /\
     payload (read_once fixture_verify fixture_bounds s2 h_new 7 (fixture_identity kind) 0 3) =
       Some [97; 98; 99]).
Proof.
  intros []; vm_compute; repeat split; try reflexivity.
  - eexists; repeat split; reflexivity.
  - eexists; repeat split; reflexivity.
Qed.

Example renew_extends_pending_transfer_witness : forall kind,
  let at3 := at_clock (two_pending kind) 3 in
  let renewed := renew_reservation fixture_bounds at3 (fixture_handle kind 0) 7 (fixture_identity kind) in
  let s1 := fst renewed in
  snd renewed = true /\
  renew_reservation fixture_bounds s1 (fixture_handle kind 0) 7 (fixture_identity kind) = (s1, false) /\
  renew_reservation fixture_bounds (at_clock (two_pending kind) 4) (fixture_handle kind 0) 7 (fixture_identity kind) =
    (at_clock (two_pending kind) 4, false) /\
  payload (complete fixture_verify (at_clock s1 5) 0 1) = Some [97; 98; 99] /\
  payload (complete fixture_verify (at_clock s1 5) 1 1) = None.
Proof.
  intros []; vm_compute; repeat split; reflexivity.
Qed.

Example crash_retains_backing_and_sequences_witness : forall kind,
  let crashed := crash (two_pending kind) in
  current_boot (common crashed) = 1 /\
  reservations (common crashed) 0 = None /\
  reservations (common crashed) 1 = None /\
  pending (sessions crashed 0) = None /\
  pending (sessions crashed 1) = None /\
  sequence (sessions crashed 0) = 1 /\
  sequence (sessions crashed 1) = 1 /\
  backing (common crashed) =
    Some {| resident_identity := fixture_identity kind;
            resident_bytes := [97; 98; 99];
            accepting := false |} /\
  live (common crashed) (fixture_handle kind 0) 7 (fixture_identity kind) = false /\
  payload (complete fixture_verify crashed 0 1) = None /\
  payload (complete fixture_verify crashed 1 1) = None /\
  admit fixture_bounds crashed 0 7 (fixture_identity kind) 0 3 = (crashed, None).
Proof.
  intros []; vm_compute; repeat split; reflexivity.
Qed.

(* =========================================================================
   Two-Slot Predecessor Replacement & Backing Reuse (Q44)
   ========================================================================= *)

Inductive BackingSlot : Type := SlotCurrent | SlotPredecessor.

Definition backing_slot_eq_dec (x y : BackingSlot) : {x = y} + {x <> y}.
Proof. decide equality. Defined.

Record TwoSlotCommon : Type := {
  current_backing : option Resident;
  predecessor_backing : option Resident;
  ts_reservations : nat -> option Reservation;
  ts_authority : nat -> bool;
  ts_next_token : nat;
  ts_clock : nat;
  ts_current_boot : nat;
  ts_current_generation : nat;
  ts_common_counter : nat
}.

Record TwoSlotState : Type := {
  ts_common : TwoSlotCommon;
  ts_sessions : nat -> Session
}.

Record TwoSlotOutcome : Type := {
  ts_after : TwoSlotState;
  ts_payload : option (list nat);
  ts_journal : list Cell
}.

Record TwoSlotBegun : Type := {
  ts_begun_state : TwoSlotState;
  ts_accepted : bool;
  ts_begin_journal : list Cell
}.

Definition ts_set_session (s : TwoSlotState) (h : nat) (v : Session) : TwoSlotState :=
  {| ts_common := ts_common s; ts_sessions := set (ts_sessions s) h v |}.

Definition ts_set_common (s : TwoSlotState) (c : TwoSlotCommon) : TwoSlotState :=
  {| ts_common := c; ts_sessions := ts_sessions s |}.

Definition close_resident (r : Resident) : Resident :=
  {| resident_identity := resident_identity r;
     resident_bytes := resident_bytes r;
     accepting := false |}.

Definition root_kind_eqb (a b : RootKind) : bool :=
  match a, b with
  | SystemImage, SystemImage => true
  | UserData, UserData => true
  | _, _ => false
  end.

Definition slot_backing (c : TwoSlotCommon) (id : Identity) : option Resident :=
  match current_backing c with
  | Some r =>
      if identity_eq_dec id (resident_identity r) then Some r
      else match predecessor_backing c with
           | Some rp => if identity_eq_dec id (resident_identity rp) then Some rp else None
           | None => None
           end
  | None =>
      match predecessor_backing c with
      | Some rp => if identity_eq_dec id (resident_identity rp) then Some rp else None
      | None => None
      end
  end.

Definition ts_current_root (c : TwoSlotCommon) (id : Identity) : bool :=
  match root_kind id with
  | SystemImage => generation id =? ts_current_generation c
  | UserData => true
  end.

Definition ts_live (c : TwoSlotCommon) (h : Handle) (d : nat) (id : Identity) : bool :=
  match ts_reservations c (holder h), slot_backing c (handle_identity h) with
  | Some held, Some r =>
      if handle_eq_dec h (reserved_handle held) then
      if identity_eq_dec (handle_identity h) (resident_identity r) then
      if identity_eq_dec id (handle_identity h) then
        (holder h <? 2) && accepting r && ts_authority c (holder h) &&
        (d =? domain (handle_identity h)) &&
        (boot_epoch h =? ts_current_boot c) && (ts_clock c <? expires held) &&
        ts_current_root c (handle_identity h)
      else false else false else false
  | _, _ => false
  end.

Definition ts_publish_initial (b : Bounds) (s : TwoSlotState) (r : Resident)
  : TwoSlotState * bool :=
  let c := ts_common s in
  match current_backing c, predecessor_backing c with
  | None, None =>
      if resident_ok b r && ts_current_root c (resident_identity r) then
        (ts_set_common s
          {| current_backing := Some r;
             predecessor_backing := None;
             ts_reservations := ts_reservations c;
             ts_authority := ts_authority c;
             ts_next_token := ts_next_token c;
             ts_clock := ts_clock c;
             ts_current_boot := ts_current_boot c;
             ts_current_generation := ts_current_generation c;
             ts_common_counter := ts_common_counter c |}, true)
      else (s, false)
  | _, _ => (s, false)
  end.

Definition ts_replace_cow (b : Bounds) (s : TwoSlotState) (r_new : Resident)
  : TwoSlotState * bool :=
  let c := ts_common s in
  match current_backing c, predecessor_backing c with
  | Some r_cur, None =>
      let id_cur := resident_identity r_cur in
      let id_new := resident_identity r_new in
      let gen_ok :=
        match root_kind id_new with
        | SystemImage => generation id_new =? S (ts_current_generation c)
        | UserData => true
        end in
      if accepting r_cur && resident_ok b r_new &&
         (owner id_new =? owner id_cur) &&
         (domain id_new =? domain id_cur) &&
         (object_id id_new =? object_id id_cur) &&
         root_kind_eqb (root_kind id_new) (root_kind id_cur) &&
         (version id_cur <? version id_new) &&
         gen_ok then
        let next_gen :=
          match root_kind id_new with
          | SystemImage => S (ts_current_generation c)
          | UserData => ts_current_generation c
          end in
        (ts_set_common s
          {| current_backing := Some r_new;
             predecessor_backing := Some r_cur;
             ts_reservations := ts_reservations c;
             ts_authority := ts_authority c;
             ts_next_token := ts_next_token c;
             ts_clock := ts_clock c;
             ts_current_boot := ts_current_boot c;
             ts_current_generation := next_gen;
             ts_common_counter := ts_common_counter c |}, true)
      else (s, false)
  | _, _ => (s, false)
  end.

Definition ts_admit (b : Bounds) (s : TwoSlotState) (h d : nat) (id : Identity)
                    (start length : nat) : TwoSlotState * option Handle :=
  let c := ts_common s in
  match current_backing c, ts_reservations c h with
  | Some r, None =>
    if identity_eq_dec id (resident_identity r) then
    if resident_ok b r && (h <? 2) && ts_authority c h && (d =? domain id) &&
       ts_current_root c id && (0 <? length) &&
       interval start length (List.length (resident_bytes r)) &&
       (ts_clock c + retention_bound b <=? counter_bound b) &&
       (ts_next_token c <? counter_bound b) then
      let handle := {| token := S (ts_next_token c); boot_epoch := ts_current_boot c;
        holder := h; handle_identity := id; window_start := start;
        window_length := length |} in
      let held := {| reserved_handle := handle;
                     expires := ts_clock c + retention_bound b |} in
      (ts_set_common s {| current_backing := current_backing c;
        predecessor_backing := predecessor_backing c;
        ts_reservations := set (ts_reservations c) h (Some held);
        ts_authority := ts_authority c; ts_next_token := S (ts_next_token c);
        ts_clock := ts_clock c; ts_current_boot := ts_current_boot c;
        ts_current_generation := ts_current_generation c;
        ts_common_counter := ts_common_counter c |},
       Some handle)
    else (s, None) else (s, None)
  | _, _ => (s, None)
  end.

Definition ts_begin_read (b : Bounds) (s : TwoSlotState) (h : Handle) (d : nat)
                         (id : Identity) (off len : nat) : TwoSlotBegun :=
  if holder h <? 2 then
    let p := ts_sessions s (holder h) in
    let cleared := ts_set_session s (holder h) (with_response p None) in
    let writes := [ResponsePublication (holder h)] in
    match pending p with
    | Some _ => {| ts_begun_state := cleared; ts_accepted := false; ts_begin_journal := writes |}
    | None =>
      if ts_live (ts_common s) h d id && (len <=? read_bound b) &&
         interval off len (window_length h) && (sequence p <? counter_bound b) then
        let q := {| request_handle := h; caller_domain := d; supplied_identity := id;
                    offset := off; count := len; request_sequence := S (sequence p) |} in
        {| ts_begun_state := ts_set_session s (holder h)
            {| sequence := S (sequence p); pending := Some q; response := None;
               reads := reads p; authentications := authentications p |};
           ts_accepted := true;
           ts_begin_journal := writes ++ [PrivateSequence (holder h); PrivatePending (holder h);
                                          RequestPublication (holder h)] |}
      else {| ts_begun_state := cleared; ts_accepted := false; ts_begin_journal := writes |}
    end
  else {| ts_begun_state := s; ts_accepted := false; ts_begin_journal := [] |}.

Definition ts_complete (verify : list nat -> list nat -> bool)
                       (s : TwoSlotState) (h seq : nat) : TwoSlotOutcome :=
  let unchanged := {| ts_after := s; ts_payload := None; ts_journal := [] |} in
  if h <? 2 then
    let p := ts_sessions s h in
    match pending p with
    | None => unchanged
    | Some q =>
      if seq =? request_sequence q then
        let cleared := ts_set_session s h (clear_pending p) in
        let writes := [ResponsePublication h; PrivatePending h; RequestPublication h] in
        let refused := {| ts_after := cleared; ts_payload := None; ts_journal := writes |} in
        if ts_live (ts_common s) (request_handle q) (caller_domain q) (supplied_identity q) &&
           (holder (request_handle q) =? h) then
          match slot_backing (ts_common s) (handle_identity (request_handle q)) with
          | None => refused
          | Some r =>
            let checked := {| sequence := sequence p; pending := None; response := None;
               reads := reads p; authentications := S (authentications p) |} in
            if verify (resident_bytes r) (root_digest (resident_identity r)) then
              let bytes := slice (resident_bytes r)
                (window_start (request_handle q) + offset q) (count q) in
              {| ts_after := ts_set_session s h
                   {| sequence := sequence p; pending := None; response := Some bytes;
                      reads := S (reads p); authentications := S (authentications p) |};
                 ts_payload := Some bytes;
                 ts_journal := writes ++ [PrivateAuthentications h; PrivateReads h;
                                          ResponsePublication h] |}
            else {| ts_after := ts_set_session s h checked; ts_payload := None;
                    ts_journal := writes ++ [PrivateAuthentications h] |}
          end
        else refused
      else unchanged
    end
  else unchanged.

Definition ts_read_once (verify : list nat -> list nat -> bool) (b : Bounds)
                        (s : TwoSlotState) (h : Handle) (d : nat) (id : Identity)
                        (off len : nat) : TwoSlotOutcome :=
  let begun := ts_begin_read b s h d id off len in
  if ts_accepted begun then
    let done := ts_complete verify (ts_begun_state begun) (holder h)
                 (sequence (ts_sessions (ts_begun_state begun) (holder h))) in
    {| ts_after := ts_after done; ts_payload := ts_payload done;
       ts_journal := ts_begin_journal begun ++ ts_journal done |}
  else {| ts_after := ts_begun_state begun; ts_payload := None;
          ts_journal := ts_begin_journal begun |}.

Definition ts_retire_predecessor (s : TwoSlotState) (barrier_completed : bool)
  : TwoSlotState :=
  let c := ts_common s in
  match predecessor_backing c with
  | None => s
  | Some rp =>
      let pred_id := resident_identity rp in
      let next_pred :=
        if barrier_completed then None else Some (close_resident rp) in
      let next_res := fun h =>
        match ts_reservations c h with
        | Some held =>
            if identity_eq_dec (handle_identity (reserved_handle held)) pred_id
            then None else Some held
        | None => None
        end in
      let next_sess := fun h =>
        let sess := ts_sessions s h in
        match pending sess with
        | Some q =>
            if identity_eq_dec (handle_identity (request_handle q)) pred_id
            then clear_pending sess else sess
        | None => sess
        end in
      {| ts_common :=
           {| current_backing := current_backing c;
              predecessor_backing := next_pred;
              ts_reservations := next_res;
              ts_authority := ts_authority c;
              ts_next_token := ts_next_token c;
              ts_clock := ts_clock c;
              ts_current_boot := ts_current_boot c;
              ts_current_generation := ts_current_generation c;
              ts_common_counter := ts_common_counter c |};
         ts_sessions := next_sess |}
  end.

Definition ts_retire_owner (s : TwoSlotState) (barrier_completed : bool) : TwoSlotState :=
  let c := ts_common s in
  {| ts_common :=
       {| current_backing :=
            if barrier_completed then None
            else option_map close_resident (current_backing c);
          predecessor_backing :=
            if barrier_completed then None
            else option_map close_resident (predecessor_backing c);
          ts_reservations := fun _ => None;
          ts_authority := ts_authority c;
          ts_next_token := ts_next_token c;
          ts_clock := ts_clock c;
          ts_current_boot := ts_current_boot c;
          ts_current_generation := ts_current_generation c;
          ts_common_counter := ts_common_counter c |};
     ts_sessions := fun h => clear_pending (ts_sessions s h) |}.

Definition ts_crash (s : TwoSlotState) : TwoSlotState :=
  let c := ts_common s in
  {| ts_common :=
       {| current_backing := option_map close_resident (current_backing c);
          predecessor_backing := option_map close_resident (predecessor_backing c);
          ts_reservations := fun _ => None;
          ts_authority := ts_authority c;
          ts_next_token := ts_next_token c;
          ts_clock := ts_clock c;
          ts_current_boot := S (ts_current_boot c);
          ts_current_generation := ts_current_generation c;
          ts_common_counter := ts_common_counter c |};
     ts_sessions := fun h => clear_pending (ts_sessions s h) |}.

Theorem ts_replace_refuses_when_predecessor_occupied : forall b s r_pred r_new,
  predecessor_backing (ts_common s) = Some r_pred ->
  ts_replace_cow b s r_new = (s, false).
Proof.
  intros b s r_pred r_new Hpred.
  unfold ts_replace_cow. rewrite Hpred.
  destruct (current_backing (ts_common s)); reflexivity.
Qed.

Theorem ts_replace_preserves_predecessor_transfer_and_admits_successor :
  forall b s r_cur r_new s',
    current_backing (ts_common s) = Some r_cur ->
    ts_replace_cow b s r_new = (s', true) ->
    current_backing (ts_common s') = Some r_new /\
    predecessor_backing (ts_common s') = Some r_cur /\
    resident_identity r_cur <> resident_identity r_new /\
    (forall h d start len,
       ts_admit b s' h d (resident_identity r_cur) start len = (s', None)) /\
    (forall verify h_pred q,
       root_kind (resident_identity r_cur) = UserData ->
       h_pred < 2 ->
       pending (ts_sessions s h_pred) = Some q ->
       holder (request_handle q) = h_pred ->
       handle_identity (request_handle q) = resident_identity r_cur ->
       ts_live (ts_common s) (request_handle q) (caller_domain q) (supplied_identity q) = true ->
       verify (resident_bytes r_cur) (root_digest (resident_identity r_cur)) = true ->
       ts_payload (ts_complete verify s' h_pred (request_sequence q)) =
         Some (slice (resident_bytes r_cur) (window_start (request_handle q) + offset q) (count q))) /\
    (forall h_cur start_cur len_cur,
       h_cur < 2 ->
       ts_reservations (ts_common s) h_cur = None ->
       ts_authority (ts_common s) h_cur = true ->
       0 < len_cur ->
       start_cur + len_cur <= length (resident_bytes r_new) ->
       ts_clock (ts_common s) + retention_bound b <= counter_bound b ->
       ts_next_token (ts_common s) < counter_bound b ->
       exists s'' handle_new,
         ts_admit b s' h_cur (domain (resident_identity r_new)) (resident_identity r_new)
           start_cur len_cur = (s'', Some handle_new) /\
         handle_identity handle_new = resident_identity r_new /\
         ts_live (ts_common s'') handle_new
           (domain (resident_identity r_new)) (resident_identity r_new) = true).
Proof.
  intros b s r_cur r_new s' Hcur Hrep.
  unfold ts_replace_cow in Hrep. rewrite Hcur in Hrep.
  destruct (predecessor_backing (ts_common s)) eqn:Hpred; [discriminate|].
  match type of Hrep with
  | (if ?test then _ else _) = _ => destruct test eqn:Hcond
  end; [|discriminate].
  inversion Hrep; subst s'; clear Hrep.
  repeat rewrite andb_true_iff in Hcond.
  destruct Hcond as [[[[[[[Hacc Hres_new] Howner] Hdom] Hobj] Hkind] Hver] Hgen].
  apply Nat.ltb_lt in Hver.
  assert (Hneq_id : resident_identity r_cur <> resident_identity r_new).
  { intro Heq. assert (version (resident_identity r_cur) = version (resident_identity r_new))
      by (rewrite Heq; reflexivity). lia. }
  assert (Hroot_new :
    ts_current_root
      {| current_backing := Some r_new;
         predecessor_backing := Some r_cur;
         ts_reservations := ts_reservations (ts_common s);
         ts_authority := ts_authority (ts_common s);
         ts_next_token := ts_next_token (ts_common s);
         ts_clock := ts_clock (ts_common s);
         ts_current_boot := ts_current_boot (ts_common s);
         ts_current_generation :=
           match root_kind (resident_identity r_new) with
           | SystemImage => S (ts_current_generation (ts_common s))
           | UserData => ts_current_generation (ts_common s)
           end;
         ts_common_counter := ts_common_counter (ts_common s) |}
      (resident_identity r_new) = true).
  { unfold ts_current_root. simpl.
    destruct (root_kind (resident_identity r_new)); [exact Hgen|reflexivity]. }
  split; [reflexivity|].
  split; [reflexivity|].
  split; [exact Hneq_id|].
  split; [|split].
  - intros h d start len. unfold ts_admit. simpl.
    destruct (ts_reservations (ts_common s) h); [reflexivity|].
    destruct (identity_eq_dec (resident_identity r_cur) (resident_identity r_new));
      [contradiction|reflexivity].
  - intros verify h_pred q Huser Hhp Hq Hholder Hid_q Hlive Hver_ok.
    unfold ts_complete. simpl.
    assert (Hhp_b : (h_pred <? 2) = true) by (apply Nat.ltb_lt; exact Hhp).
    rewrite Hhp_b, Hq, Nat.eqb_refl.
    assert (Hslot_s : slot_backing (ts_common s) (handle_identity (request_handle q)) = Some r_cur).
    { unfold slot_backing. rewrite Hcur, Hid_q.
      destruct (identity_eq_dec (resident_identity r_cur) (resident_identity r_cur));
        [reflexivity|contradiction]. }
    assert (Hslot_s' :
      slot_backing
        {| current_backing := Some r_new;
           predecessor_backing := Some r_cur;
           ts_reservations := ts_reservations (ts_common s);
           ts_authority := ts_authority (ts_common s);
           ts_next_token := ts_next_token (ts_common s);
           ts_clock := ts_clock (ts_common s);
           ts_current_boot := ts_current_boot (ts_common s);
           ts_current_generation :=
             match root_kind (resident_identity r_new) with
             | SystemImage => S (ts_current_generation (ts_common s))
             | UserData => ts_current_generation (ts_common s)
             end;
           ts_common_counter := ts_common_counter (ts_common s) |}
        (handle_identity (request_handle q)) = Some r_cur).
    { unfold slot_backing. simpl. rewrite Hid_q.
      destruct (identity_eq_dec (resident_identity r_cur) (resident_identity r_new));
        [contradiction|].
      destruct (identity_eq_dec (resident_identity r_cur) (resident_identity r_cur));
        [reflexivity|contradiction]. }
    assert (Hlive' :
      ts_live
        {| current_backing := Some r_new;
           predecessor_backing := Some r_cur;
           ts_reservations := ts_reservations (ts_common s);
           ts_authority := ts_authority (ts_common s);
           ts_next_token := ts_next_token (ts_common s);
           ts_clock := ts_clock (ts_common s);
           ts_current_boot := ts_current_boot (ts_common s);
           ts_current_generation :=
             match root_kind (resident_identity r_new) with
             | SystemImage => S (ts_current_generation (ts_common s))
             | UserData => ts_current_generation (ts_common s)
             end;
           ts_common_counter := ts_common_counter (ts_common s) |}
        (request_handle q) (caller_domain q) (supplied_identity q) = true).
    { unfold ts_live in Hlive |- *. simpl. rewrite Hslot_s in Hlive. rewrite Hslot_s'.
      destruct (ts_reservations (ts_common s) (holder (request_handle q))) as [held|]; [|discriminate].
      destruct (handle_eq_dec (request_handle q) (reserved_handle held)); [|discriminate].
      destruct (identity_eq_dec (handle_identity (request_handle q)) (resident_identity r_cur));
        [|discriminate].
      destruct (identity_eq_dec (supplied_identity q) (handle_identity (request_handle q)));
        [|discriminate].
      unfold ts_current_root in *. simpl. rewrite Hid_q, Huser in Hlive |- *. exact Hlive. }
    rewrite Hlive', Hholder, Nat.eqb_refl. simpl. rewrite Hslot_s', Hver_ok. reflexivity.
  - intros h_cur start_cur len_cur Hh Hnone Hauth Hlen_pos Hbounds Hexp Htok.
    assert (Hbounds_ok : bounds_ok b = true).
    { unfold resident_ok in Hres_new.
      repeat rewrite andb_true_iff in Hres_new.
      destruct Hres_new as [[[[Hbok _] _] _] _]. exact Hbok. }
    assert (Hret_pos : 0 < retention_bound b).
    { unfold bounds_ok in Hbounds_ok.
      repeat rewrite andb_true_iff in Hbounds_ok.
      destruct Hbounds_ok as [[[[[[_ _] _] _] Hrp] _] _].
      apply Nat.ltb_lt in Hrp. exact Hrp. }
    unfold ts_admit. simpl. rewrite Hnone.
    destruct (identity_eq_dec (resident_identity r_new) (resident_identity r_new));
      [|contradiction].
    assert (Hadmit_cond :
      (resident_ok b r_new && (h_cur <? 2) && ts_authority (ts_common s) h_cur &&
       (domain (resident_identity r_new) =? domain (resident_identity r_new)) &&
       ts_current_root
         {| current_backing := Some r_new;
            predecessor_backing := Some r_cur;
            ts_reservations := ts_reservations (ts_common s);
            ts_authority := ts_authority (ts_common s);
            ts_next_token := ts_next_token (ts_common s);
            ts_clock := ts_clock (ts_common s);
            ts_current_boot := ts_current_boot (ts_common s);
            ts_current_generation :=
              match root_kind (resident_identity r_new) with
              | SystemImage => S (ts_current_generation (ts_common s))
              | UserData => ts_current_generation (ts_common s)
              end;
            ts_common_counter := ts_common_counter (ts_common s) |}
         (resident_identity r_new) && (0 <? len_cur) &&
       interval start_cur len_cur (length (resident_bytes r_new)) &&
       (ts_clock (ts_common s) + retention_bound b <=? counter_bound b) &&
       (ts_next_token (ts_common s) <? counter_bound b)) = true).
    { repeat rewrite andb_true_iff. repeat split.
      - exact Hres_new.
      - apply Nat.ltb_lt; exact Hh.
      - exact Hauth.
      - apply Nat.eqb_refl.
      - exact Hroot_new.
      - apply Nat.ltb_lt; exact Hlen_pos.
      - unfold interval. apply Nat.leb_le; exact Hbounds.
      - apply Nat.leb_le; exact Hexp.
      - apply Nat.ltb_lt; exact Htok. }
    rewrite Hadmit_cond.
    eexists _, _. repeat split; try reflexivity.
    unfold ts_live. simpl. rewrite set_same.
    unfold slot_backing. simpl.
    repeat match goal with
    | |- context [if ?d then _ else _] => destruct d; [|contradiction]
    end.
    assert (Hacc_new : accepting r_new = true).
    { unfold resident_ok in Hres_new.
      repeat rewrite andb_true_iff in Hres_new.
      destruct Hres_new as [[[[_ Ha] _] _] _]. exact Ha. }
    repeat rewrite andb_true_iff. repeat split.
    + apply Nat.ltb_lt; exact Hh.
    + exact Hacc_new.
    + exact Hauth.
    + apply Nat.eqb_refl.
    + apply Nat.eqb_refl.
    + apply Nat.ltb_lt. lia.
    + exact Hroot_new.
Qed.

Theorem ts_retire_predecessor_preserves_current_peer :
  forall s r_cur r_pred barrier_completed,
    current_backing (ts_common s) = Some r_cur ->
    predecessor_backing (ts_common s) = Some r_pred ->
    resident_identity r_cur <> resident_identity r_pred ->
    let s' := ts_retire_predecessor s barrier_completed in
    current_backing (ts_common s') = Some r_cur /\
    predecessor_backing (ts_common s') =
      (if barrier_completed then None else Some (close_resident r_pred)) /\
    ts_next_token (ts_common s') = ts_next_token (ts_common s) /\
    ts_authority (ts_common s') = ts_authority (ts_common s) /\
    ts_clock (ts_common s') = ts_clock (ts_common s) /\
    ts_current_boot (ts_common s') = ts_current_boot (ts_common s) /\
    ts_current_generation (ts_common s') = ts_current_generation (ts_common s) /\
    (forall k, sequence (ts_sessions s' k) = sequence (ts_sessions s k)) /\
    (forall k held,
       ts_reservations (ts_common s) k = Some held ->
       handle_identity (reserved_handle held) = resident_identity r_cur ->
       ts_reservations (ts_common s') k = Some held) /\
    (forall k q,
       pending (ts_sessions s k) = Some q ->
       handle_identity (request_handle q) = resident_identity r_cur ->
       ts_sessions s' k = ts_sessions s k) /\
    (forall h d id,
       handle_identity h = resident_identity r_cur ->
       ts_live (ts_common s') h d id = ts_live (ts_common s) h d id) /\
    (forall k held,
       ts_reservations (ts_common s) k = Some held ->
       handle_identity (reserved_handle held) = resident_identity r_pred ->
       ts_reservations (ts_common s') k = None) /\
    (forall k q,
       pending (ts_sessions s k) = Some q ->
       handle_identity (request_handle q) = resident_identity r_pred ->
       pending (ts_sessions s' k) = None) /\
    (forall h d id,
       handle_identity h = resident_identity r_pred ->
       ts_live (ts_common s') h d id = false).
Proof.
  intros s r_cur r_pred barrier_completed Hcur Hpred Hneq s'.
  subst s'. unfold ts_retire_predecessor. rewrite Hpred.
  repeat split; simpl; try reflexivity.
  - exact Hcur.
  - intros k. destruct (pending (ts_sessions s k)); [|reflexivity].
    destruct (identity_eq_dec (handle_identity (request_handle r)) (resident_identity r_pred));
      reflexivity.
  - intros k held Hk Hid. rewrite Hk.
    destruct (identity_eq_dec (handle_identity (reserved_handle held)) (resident_identity r_pred));
      [congruence|reflexivity].
  - intros k q Hq Hid. rewrite Hq.
    destruct (identity_eq_dec (handle_identity (request_handle q)) (resident_identity r_pred));
      [congruence|reflexivity].
  - intros h d id Hid. unfold ts_live. simpl.
    unfold slot_backing. simpl. rewrite Hcur, Hpred, Hid.
    destruct (identity_eq_dec (resident_identity r_cur) (resident_identity r_cur));
      [|contradiction].
    destruct (ts_reservations (ts_common s) (holder h)) as [held|]; [|reflexivity].
    destruct (identity_eq_dec (handle_identity (reserved_handle held)) (resident_identity r_pred))
      as [Heq_p|Hne_p].
    + destruct (handle_eq_dec h (reserved_handle held)) as [Heq_h|];
        [rewrite Heq_h in Hid; congruence|reflexivity].
    + reflexivity.
  - intros k held Hk Hid. rewrite Hk.
    destruct (identity_eq_dec (handle_identity (reserved_handle held)) (resident_identity r_pred));
      [reflexivity|contradiction].
  - intros k q Hq Hid. rewrite Hq.
    destruct (identity_eq_dec (handle_identity (request_handle q)) (resident_identity r_pred));
      [reflexivity|contradiction].
  - intros h d id Hid. unfold ts_live. simpl.
    destruct (ts_reservations (ts_common s) (holder h)) as [held|]; [|reflexivity].
    destruct (identity_eq_dec (handle_identity (reserved_handle held)) (resident_identity r_pred))
      as [Heq_p|Hne_p]; [reflexivity|].
    destruct (slot_backing _ _); [|reflexivity].
    destruct (handle_eq_dec h (reserved_handle held)) as [Heq_h|];
      [rewrite Heq_h in Hid; contradiction|reflexivity].
Qed.

Theorem ts_retire_predecessor_quarantine_blocks_third_version :
  forall b s r_pred r_third,
    predecessor_backing (ts_common s) = Some r_pred ->
    let s_q := ts_retire_predecessor s false in
    predecessor_backing (ts_common s_q) = Some (close_resident r_pred) /\
    ts_replace_cow b s_q r_third = (s_q, false) /\
    predecessor_backing (ts_common (ts_retire_predecessor s true)) = None.
Proof.
  intros b s r_pred r_third Hpred s_q.
  assert (Hq : predecessor_backing (ts_common s_q) = Some (close_resident r_pred)).
  { subst s_q. unfold ts_retire_predecessor. rewrite Hpred. reflexivity. }
  repeat split.
  - exact Hq.
  - eapply ts_replace_refuses_when_predecessor_occupied. exact Hq.
  - unfold ts_retire_predecessor. rewrite Hpred. reflexivity.
Qed.

Theorem ts_begin_and_complete_no_common_writes : forall verify b s h h_slot d id off len seq,
  ts_common (ts_begun_state (ts_begin_read b s h d id off len)) = ts_common s /\
  no_common (ts_begin_journal (ts_begin_read b s h d id off len)) /\
  ts_common (ts_after (ts_complete verify s h_slot seq)) = ts_common s /\
  no_common (ts_journal (ts_complete verify s h_slot seq)) /\
  ts_common (ts_after (ts_read_once verify b s h d id off len)) = ts_common s /\
  no_common (ts_journal (ts_read_once verify b s h d id off len)).
Proof.
  intros verify b s h h_slot d id off len seq.
  assert (Hbf : forall b0 s0 h0 d0 id0 off0 len0,
    ts_common (ts_begun_state (ts_begin_read b0 s0 h0 d0 id0 off0 len0)) = ts_common s0).
  { intros. unfold ts_begin_read. destruct (holder h0 <? 2); [|reflexivity].
    destruct (pending (ts_sessions s0 (holder h0)));
      repeat match goal with |- context [if ?t then _ else _] => destruct t end;
      reflexivity. }
  assert (Hbj : forall b0 s0 h0 d0 id0 off0 len0,
    no_common (ts_begin_journal (ts_begin_read b0 s0 h0 d0 id0 off0 len0))).
  { intros. unfold ts_begin_read. destruct (holder h0 <? 2);
      [destruct (pending (ts_sessions s0 (holder h0)))|];
      repeat match goal with |- context [if ?t then _ else _] => destruct t end;
      repeat constructor. }
  assert (Hcf : forall verify0 s0 h0 seq0,
    ts_common (ts_after (ts_complete verify0 s0 h0 seq0)) = ts_common s0).
  { intros. unfold ts_complete. destruct (h0 <? 2); [|reflexivity].
    destruct (pending (ts_sessions s0 h0)); [|reflexivity].
    repeat match goal with |- context [if ?t then _ else _] => destruct t end;
      try destruct (slot_backing (ts_common s0) _);
      repeat match goal with |- context [if ?t then _ else _] => destruct t end;
      reflexivity. }
  assert (Hcj : forall verify0 s0 h0 seq0,
    no_common (ts_journal (ts_complete verify0 s0 h0 seq0))).
  { intros. unfold ts_complete. destruct (h0 <? 2);
      [destruct (pending (ts_sessions s0 h0))|];
      repeat match goal with |- context [if ?t then _ else _] => destruct t end;
      try destruct (slot_backing (ts_common s0) _);
      repeat match goal with |- context [if ?t then _ else _] => destruct t end;
      repeat constructor. }
  repeat split.
  - apply Hbf.
  - apply Hbj.
  - apply Hcf.
  - apply Hcj.
  - unfold ts_read_once. destruct (ts_accepted (ts_begin_read b s h d id off len)); simpl.
    + rewrite Hcf. apply Hbf.
    + apply Hbf.
  - unfold ts_read_once. destruct (ts_accepted (ts_begin_read b s h d id off len)); simpl.
    + apply Forall_app. split; [apply Hbj|apply Hcj].
    + apply Hbj.
Qed.

Theorem ts_crash_closes_both_slots_and_preserves_sequences : forall s,
  ts_current_boot (ts_common (ts_crash s)) = S (ts_current_boot (ts_common s)) /\
  (forall r, current_backing (ts_common s) = Some r ->
     current_backing (ts_common (ts_crash s)) = Some (close_resident r)) /\
  (current_backing (ts_common s) = None ->
     current_backing (ts_common (ts_crash s)) = None) /\
  (forall r, predecessor_backing (ts_common s) = Some r ->
     predecessor_backing (ts_common (ts_crash s)) = Some (close_resident r)) /\
  (predecessor_backing (ts_common s) = None ->
     predecessor_backing (ts_common (ts_crash s)) = None) /\
  (forall k, ts_reservations (ts_common (ts_crash s)) k = None) /\
  (forall k, pending (ts_sessions (ts_crash s) k) = None) /\
  (forall k, sequence (ts_sessions (ts_crash s) k) = sequence (ts_sessions s k)) /\
  (forall h d id, ts_live (ts_common (ts_crash s)) h d id = false) /\
  (forall verify k seq, ts_payload (ts_complete verify (ts_crash s) k seq) = None) /\
  (forall b h d id off len, ts_accepted (ts_begin_read b (ts_crash s) h d id off len) = false) /\
  (forall b h d id start len, ts_admit b (ts_crash s) h d id start len = (ts_crash s, None)) /\
  (forall b r_new, ts_replace_cow b (ts_crash s) r_new = (ts_crash s, false)).
Proof.
  intros s. repeat split; try reflexivity.
  - intros r Hr. unfold ts_crash. simpl. rewrite Hr. reflexivity.
  - intros Hnone. unfold ts_crash. simpl. rewrite Hnone. reflexivity.
  - intros r Hr. unfold ts_crash. simpl. rewrite Hr. reflexivity.
  - intros Hnone. unfold ts_crash. simpl. rewrite Hnone. reflexivity.
  - intros verify k seq. unfold ts_complete, ts_crash. simpl.
    destruct (k <? 2); reflexivity.
  - intros b h d id off len. unfold ts_begin_read, ts_crash. simpl.
    destruct (holder h <? 2); [|reflexivity].
    unfold ts_live. simpl. reflexivity.
  - intros b h d id start len. unfold ts_admit, ts_crash. simpl.
    destruct (current_backing (ts_common s)) as [r|]; [|reflexivity].
    simpl. destruct (identity_eq_dec id (resident_identity r)); [|reflexivity].
    unfold resident_ok. simpl. rewrite andb_false_r. reflexivity.
  - intros b r_new. unfold ts_replace_cow, ts_crash. simpl.
    destruct (current_backing (ts_common s)) as [r_cur|]; [|reflexivity].
    destruct (predecessor_backing (ts_common s)); reflexivity.
Qed.

Definition ts_initial (kind : RootKind) : TwoSlotState :=
  {| ts_common := {| current_backing := None;
                     predecessor_backing := None;
                     ts_reservations := fun _ => None;
                     ts_authority := fun _ => true;
                     ts_next_token := 0;
                     ts_clock := 0;
                     ts_current_boot := 0;
                     ts_current_generation := 1;
                     ts_common_counter := 0 |};
     ts_sessions := fun _ => empty_session |}.

Definition ts_fixture_identity_v (kind : RootKind) (ver gen : nat) (digest : list nat) : Identity :=
  {| owner := 1; domain := 7; object_id := 1; version := ver;
     root_kind := kind; generation := gen; root_digest := digest |}.

Definition ts_fixture_resident_v (kind : RootKind) (ver gen : nat)
                                 (digest bytes : list nat) : Resident :=
  {| resident_identity := ts_fixture_identity_v kind ver gen digest;
     resident_bytes := bytes;
     accepting := true |}.

Definition ts_fixture_verify (bytes digest : list nat) : bool :=
  if list_eq_dec Nat.eq_dec bytes [97; 98; 99] then
    if list_eq_dec Nat.eq_dec digest [11; 22] then true else false
  else if list_eq_dec Nat.eq_dec bytes [100; 101; 102] then
    if list_eq_dec Nat.eq_dec digest [33; 44] then true else false
  else if list_eq_dec Nat.eq_dec bytes [103; 104; 105] then
    if list_eq_dec Nat.eq_dec digest [55; 66] then true else false
  else false.

Definition witness_TwoSlotCommon : TwoSlotCommon :=
  ts_common (fst (ts_publish_initial fixture_bounds (ts_initial UserData)
    (ts_fixture_resident_v UserData 1 1 [11; 22] [97; 98; 99]))).
Definition witness_TwoSlotState : TwoSlotState :=
  fst (ts_publish_initial fixture_bounds (ts_initial UserData)
    (ts_fixture_resident_v UserData 1 1 [11; 22] [97; 98; 99])).
Definition witness_TwoSlotBegun : TwoSlotBegun :=
  let s1 := witness_TwoSlotState in
  let adm := ts_admit fixture_bounds s1 0 7 (ts_fixture_identity_v UserData 1 1 [11; 22]) 0 3 in
  match snd adm with
  | Some h => ts_begin_read fixture_bounds (fst adm) h 7 (ts_fixture_identity_v UserData 1 1 [11; 22]) 0 3
  | None => {| ts_begun_state := s1; ts_accepted := false; ts_begin_journal := [] |}
  end.
Definition witness_TwoSlotOutcome : TwoSlotOutcome :=
  ts_complete ts_fixture_verify (ts_begun_state witness_TwoSlotBegun) 0 1.

Example ts_userdata_cow_quarantine_and_reuse_witness :
  let id1 := ts_fixture_identity_v UserData 1 1 [11; 22] in
  let id2 := ts_fixture_identity_v UserData 2 1 [33; 44] in
  let r1 := ts_fixture_resident_v UserData 1 1 [11; 22] [97; 98; 99] in
  let r2 := ts_fixture_resident_v UserData 2 1 [33; 44] [100; 101; 102] in
  let r3 := ts_fixture_resident_v UserData 3 1 [55; 66] [103; 104; 105] in
  let pub := ts_publish_initial fixture_bounds (ts_initial UserData) r1 in
  let s1 := fst pub in
  let adm0 := ts_admit fixture_bounds s1 0 7 id1 0 3 in
  let s2 := fst adm0 in
  let h0 := {| token := 1; boot_epoch := 0; holder := 0; handle_identity := id1;
               window_start := 0; window_length := 3 |} in
  let beg0 := ts_begin_read fixture_bounds s2 h0 7 id1 0 3 in
  let s3 := ts_begun_state beg0 in
  let cow := ts_replace_cow fixture_bounds s3 r2 in
  let s4 := fst cow in
  let pred_done := ts_complete ts_fixture_verify s4 0 1 in
  let s5 := ts_after pred_done in
  let adm1 := ts_admit fixture_bounds s5 1 7 id2 1 2 in
  let s6 := fst adm1 in
  let h1 := {| token := 2; boot_epoch := 0; holder := 1; handle_identity := id2;
               window_start := 1; window_length := 2 |} in
  let beg1 := ts_begin_read fixture_bounds s6 h1 7 id2 0 2 in
  let s7 := ts_begun_state beg1 in
  let refuse_v3_occupied := ts_replace_cow fixture_bounds s7 r3 in
  let s_quar := ts_retire_predecessor s7 false in
  let refuse_v3_quarantine := ts_replace_cow fixture_bounds s_quar r3 in
  let s_rel := ts_retire_predecessor s_quar true in
  let cur_done := ts_complete ts_fixture_verify s_rel 1 1 in
  let s8 := ts_after cur_done in
  let reuse_v3 := ts_replace_cow fixture_bounds s8 r3 in
  let s9 := fst reuse_v3 in
  snd pub = true /\
  snd adm0 = Some h0 /\
  ts_accepted beg0 = true /\
  snd cow = true /\
  current_backing (ts_common s4) = Some r2 /\
  predecessor_backing (ts_common s4) = Some r1 /\
  ts_payload pred_done = Some [97; 98; 99] /\
  snd adm1 = Some h1 /\
  ts_accepted beg1 = true /\
  snd refuse_v3_occupied = false /\
  predecessor_backing (ts_common s_quar) = Some (close_resident r1) /\
  ts_reservations (ts_common s_quar) 0 = None /\
  snd refuse_v3_quarantine = false /\
  predecessor_backing (ts_common s_rel) = None /\
  ts_payload cur_done = Some [101; 102] /\
  snd reuse_v3 = true /\
  current_backing (ts_common s9) = Some r3 /\
  predecessor_backing (ts_common s9) = Some r2.
Proof.
  vm_compute. repeat split; reflexivity.
Qed.

Example ts_system_image_cow_generation_and_crash_witness :
  let id1 := ts_fixture_identity_v SystemImage 1 1 [11; 22] in
  let id2 := ts_fixture_identity_v SystemImage 2 2 [33; 44] in
  let r1 := ts_fixture_resident_v SystemImage 1 1 [11; 22] [97; 98; 99] in
  let r2 := ts_fixture_resident_v SystemImage 2 2 [33; 44] [100; 101; 102] in
  let r3 := ts_fixture_resident_v SystemImage 3 3 [55; 66] [103; 104; 105] in
  let pub := ts_publish_initial fixture_bounds (ts_initial SystemImage) r1 in
  let s1 := fst pub in
  let adm0 := ts_admit fixture_bounds s1 0 7 id1 0 3 in
  let s2 := fst adm0 in
  let h0 := {| token := 1; boot_epoch := 0; holder := 0; handle_identity := id1;
               window_start := 0; window_length := 3 |} in
  let beg0 := ts_begin_read fixture_bounds s2 h0 7 id1 0 3 in
  let s3 := ts_begun_state beg0 in
  let cow := ts_replace_cow fixture_bounds s3 r2 in
  let s4 := fst cow in
  let pred_refused := ts_complete ts_fixture_verify s4 0 1 in
  let s5 := ts_after pred_refused in
  let adm1 := ts_admit fixture_bounds s5 1 7 id2 0 3 in
  let s6 := fst adm1 in
  let h1 := {| token := 2; boot_epoch := 0; holder := 1; handle_identity := id2;
               window_start := 0; window_length := 3 |} in
  let succ_read := ts_read_once ts_fixture_verify fixture_bounds s6 h1 7 id2 0 3 in
  let s7 := ts_after succ_read in
  let crashed := ts_crash s7 in
  snd pub = true /\
  snd adm0 = Some h0 /\
  ts_accepted beg0 = true /\
  snd cow = true /\
  ts_current_generation (ts_common s4) = 2 /\
  ts_payload pred_refused = None /\
  snd adm1 = Some h1 /\
  ts_payload succ_read = Some [100; 101; 102] /\
  ts_current_boot (ts_common crashed) = 1 /\
  current_backing (ts_common crashed) = Some (close_resident r2) /\
  predecessor_backing (ts_common crashed) = Some (close_resident r1) /\
  ts_reservations (ts_common crashed) 0 = None /\
  ts_reservations (ts_common crashed) 1 = None /\
  pending (ts_sessions crashed 0) = None /\
  pending (ts_sessions crashed 1) = None /\
  sequence (ts_sessions crashed 0) = 1 /\
  sequence (ts_sessions crashed 1) = 1 /\
  ts_admit fixture_bounds crashed 0 7 id2 0 3 = (crashed, None) /\
  ts_replace_cow fixture_bounds crashed r3 = (crashed, false).
Proof.
  vm_compute. repeat split; reflexivity.
Qed.

