(* SPDX-License-Identifier: Apache-2.0 *)
From SailStdpp Require Import Base ConcurrencyInterface ConcurrencyInterfaceTypes ConcurrencyInterfaceBuiltins TypeCasts.
From stdpp Require Import gmap bitvector.definitions.
Require Import rv64d_types rv64d TagInterpreter TagConservativity CanonicalPhysicalCallerBridge.
Import ListNotations.

Module I := CanonicalPhysicalCallerBridge.I.
Module D := CanonicalPhysicalCallerBridge.D.
Module T := CanonicalPhysicalCallerBridge.T.
Module CanonicalOldOutcomes := TagConservativity.OldOutcomes rv64d_types.Arch rv64d_types.Interface.
Local Open Scope string_scope.
Local Open Scope Z_scope.

Definition non_tag_event {E : Type} (ev : I.iEvent (fun _ => E)) : Prop :=
  match ev with
  | I.IEvent (I.TagRead _) _ => False
  | I.IEvent (I.TagWrite _ _) _ => False
  | _ => True
  end.

Lemma bridge_step_eq_old_step {E Frame Y : Type}
  (old : forall Response, I.outcome (fun _ => E) Response -> Frame -> option (Response * Frame))
  (oc : I.outcome (fun _ => E) Y) (tags : T.tagmap) (frame : Frame) :
  T.step old oc tags frame = CanonicalOldOutcomes.T.step old oc tags frame.
Proof. reflexivity. Qed.

Lemma bridge_run_eq_old_run {E Frame X : Type}
  (old : forall Response, I.outcome (fun _ => E) Response -> Frame -> option (Response * Frame))
  (fuel : nat) (program : I.iMon (fun _ => E) X)
  (tags : T.tagmap) (frame : Frame) :
  T.run old fuel program tags frame =
  match CanonicalOldOutcomes.T.run old fuel program tags frame with
  | Some a => Some (@T.Answer E Frame X
                      (@CanonicalOldOutcomes.T.returned E Frame X a)
                      (@CanonicalOldOutcomes.T.final_tags E Frame X a)
                      (@CanonicalOldOutcomes.T.final_frame E Frame X a)
                      (@CanonicalOldOutcomes.T.events E Frame X a))
  | None => None
  end.
Proof.
  revert program tags frame.
  induction fuel as [|remaining IH]; intros program tags frame.
  - reflexivity.
  - destruct program as [x | Y oc k].
    + reflexivity.
    + cbn [T.run CanonicalOldOutcomes.T.run].
      rewrite bridge_step_eq_old_step.
      destruct (CanonicalOldOutcomes.T.step old oc tags frame) as [[[response tags'] frame'] |].
      * rewrite IH.
        destruct (CanonicalOldOutcomes.T.run old remaining (k response) tags' frame'); reflexivity.
      * reflexivity.
Qed.

Theorem bridge_tag_free_run_preserved {E Frame X : Type}
  (old : forall Response, I.outcome (fun _ => E) Response -> Frame -> option (Response * Frame))
  (fuel : nat) (program : I.iMon (fun _ => E) X)
  (tags : T.tagmap) (frame : Frame) :
  CanonicalOldOutcomes.tag_free program ->
  T.run old fuel program tags frame =
  match CanonicalOldOutcomes.run_old old fuel program frame with
  | Some r => Some (@T.Answer E Frame X
                      (@CanonicalOldOutcomes.result E Frame X r)
                      tags
                      (@CanonicalOldOutcomes.frame_after E Frame X r)
                      (@CanonicalOldOutcomes.trace E Frame X r))
  | None => None
  end.
Proof.
  intro Hfree.
  rewrite bridge_run_eq_old_run.
  rewrite CanonicalOldOutcomes.tag_free_run_preserved by exact Hfree.
  destruct (CanonicalOldOutcomes.run_old old fuel program frame); reflexivity.
Qed.

Lemma tag_free_run_preserves_tags {E Frame X : Type}
  (old : forall Response, I.outcome (fun _ => E) Response -> Frame -> option (Response * Frame))
  (fuel : nat) (program : I.iMon (fun _ => E) X)
  (tags : T.tagmap) (frame : Frame) (ans : T.answer X) :
  CanonicalOldOutcomes.tag_free program ->
  T.run old fuel program tags frame = Some ans ->
  @T.final_tags E Frame X ans = tags.
Proof.
  intros Hfree Hrun.
  rewrite bridge_tag_free_run_preserved in Hrun by exact Hfree.
  destruct (CanonicalOldOutcomes.run_old old fuel program frame) as [r |].
  - inversion Hrun. reflexivity.
  - discriminate.
Qed.

Lemma tag_free_run_old_no_tag_events {E Frame X : Type}
  (old : forall Response, I.outcome (fun _ => E) Response -> Frame -> option (Response * Frame))
  (fuel : nat) (program : I.iMon (fun _ => E) X)
  (frame : Frame) (r : CanonicalOldOutcomes.old_answer X) :
  CanonicalOldOutcomes.tag_free program ->
  CanonicalOldOutcomes.run_old old fuel program frame = Some r ->
  forall ev, In ev (@CanonicalOldOutcomes.trace E Frame X r) -> non_tag_event ev.
Proof.
  revert program frame r.
  induction fuel as [|remaining IH]; intros program frame r Hfree Hrun ev Hin.
  - discriminate.
  - destruct Hfree as [x | Y oc k Hold Hk].
    + inversion Hrun. subst. contradiction.
    + cbn [CanonicalOldOutcomes.run_old] in Hrun.
      destruct (old Y oc frame) as [[response next_frame] |] eqn:Hstep; [| discriminate].
      destruct (CanonicalOldOutcomes.run_old old remaining (k response) next_frame) as [r' |] eqn:Htail;
        [| discriminate].
      inversion Hrun. subst. cbn in Hin.
      destruct Hin as [Heq | Htail_in].
      * subst ev. destruct oc; cbn [CanonicalOldOutcomes.old_event] in Hold;
          solve [contradiction | exact I].
      * exact (IH (k response) next_frame r' (Hk response) Htail ev Htail_in).
Qed.

Lemma tag_free_run_no_tag_events {E Frame X : Type}
  (old : forall Response, I.outcome (fun _ => E) Response -> Frame -> option (Response * Frame))
  (fuel : nat) (program : I.iMon (fun _ => E) X)
  (tags : T.tagmap) (frame : Frame) (ans : T.answer X) :
  CanonicalOldOutcomes.tag_free program ->
  T.run old fuel program tags frame = Some ans ->
  forall ev, In ev (@T.events E Frame X ans) -> non_tag_event ev.
Proof.
  intros Hfree Hrun ev Hin.
  rewrite bridge_tag_free_run_preserved in Hrun by exact Hfree.
  destruct (CanonicalOldOutcomes.run_old old fuel program frame) as [r |] eqn:Hold;
    [| discriminate].
  inversion Hrun. subst.
  exact (tag_free_run_old_no_tag_events old fuel program frame r Hfree Hold ev Hin).
Qed.

Lemma read_data_tag_free addr width kind meta :
  CanonicalOldOutcomes.tag_free (read_data addr width kind meta).
Proof.
  destruct (read_data_exact_reply addr width kind meta) as [resume [Heq [Hok Herr]]].
  rewrite Heq.
  apply CanonicalOldOutcomes.free_next.
  - exact I.
  - intros [[bits req_tag] | err].
    + destruct (Hok bits req_tag) as [data [_ Hret]].
      rewrite Hret. apply CanonicalOldOutcomes.free_ret.
    + destruct err.
      cbv [rv64d_types.Arch.abort].
      rewrite Herr.
      apply CanonicalOldOutcomes.free_next.
      * exact I.
      * intros [].
Qed.

Lemma finish_read_tag_free addr width kind meta :
  CanonicalOldOutcomes.tag_free (finish_read addr width kind meta).
Proof.
  unfold finish_read.
  destruct (read_access kind) as [access | [line message]].
  - apply read_data_tag_free.
  - unfold internal_error, throw. cbn [D.bind I.iMon_bind].
    apply CanonicalOldOutcomes.free_next.
    + exact I.
    + intro access. apply read_data_tag_free.
Qed.

Lemma read_ram_no_meta_eq kind addr width :
  read_ram kind (Physaddr addr) width false = finish_read addr width kind default_meta.
Proof. apply read_ram_request_order. Qed.

Lemma read_ram_no_meta_tag_free kind addr width :
  CanonicalOldOutcomes.tag_free (read_ram kind (Physaddr addr) width false).
Proof.
  rewrite read_ram_no_meta_eq. apply finish_read_tag_free.
Qed.

Theorem read_ram_no_meta_run_preserved {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel kind addr width tags frame :
  T.run old fuel (read_ram kind (Physaddr addr) width false) tags frame =
  match CanonicalOldOutcomes.run_old old fuel (finish_read addr width kind default_meta) frame with
  | Some r => Some (@T.Answer exception Frame (mword (8 * width) * bool)
                      (@CanonicalOldOutcomes.result exception Frame (mword (8 * width) * bool) r)
                      tags
                      (@CanonicalOldOutcomes.frame_after exception Frame (mword (8 * width) * bool) r)
                      (@CanonicalOldOutcomes.trace exception Frame (mword (8 * width) * bool) r))
  | None => None
  end.
Proof.
  rewrite read_ram_no_meta_eq.
  apply bridge_tag_free_run_preserved.
  apply finish_read_tag_free.
Qed.

Lemma read_ram_no_meta_preserves_tags {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel kind addr width tags frame ans :
  T.run old fuel (read_ram kind (Physaddr addr) width false) tags frame = Some ans ->
  @T.final_tags exception Frame (mword (8 * width) * bool) ans = tags.
Proof.
  apply tag_free_run_preserves_tags.
  apply read_ram_no_meta_tag_free.
Qed.

Lemma read_ram_no_meta_no_tag_events {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel kind addr width tags frame ans :
  T.run old fuel (read_ram kind (Physaddr addr) width false) tags frame = Some ans ->
  forall ev, In ev (@T.events exception Frame (mword (8 * width) * bool) ans) -> non_tag_event ev.
Proof.
  apply tag_free_run_no_tag_events.
  apply read_ram_no_meta_tag_free.
Qed.

Lemma read_data_mem_read_ok {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel addr width kind meta tags frame bits req_tag frame' :
  old _ (I.MemRead (Z.to_N width) (I.ReadReq.make (Z.to_N width) addr kind None tt false)) frame =
    Some (inl (bits, req_tag), frame') ->
  exists data,
    bv_unsigned data = bv_unsigned bits /\
    T.run old (S (S fuel)) (read_data addr width kind meta) tags frame =
    Some (@T.Answer exception Frame (mword (8 * width) * bool) (data, meta) tags frame'
            [I.IEvent (I.MemRead (Z.to_N width)
                         (I.ReadReq.make (Z.to_N width) addr kind None tt false))
               (inl (bits, req_tag))]).
Proof.
  intro Hold.
  destruct (read_data_exact_reply addr width kind meta) as [resume [Heq [Hok _]]].
  destruct (Hok bits req_tag) as [data [Hbits Hret]].
  exists data. split.
  - exact Hbits.
  - rewrite Heq. cbn [T.run T.step]. rewrite Hold.
    rewrite Hret. reflexivity.
Qed.

Lemma read_data_mem_read_err {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel addr width kind meta tags frame frame' :
  old _ (I.MemRead (Z.to_N width) (I.ReadReq.make (Z.to_N width) addr kind None tt false)) frame =
    Some (inr tt, frame') ->
  old _ (I.GenericFail "exit") frame' = None ->
  T.run old (S (S (S fuel))) (read_data addr width kind meta) tags frame = None.
Proof.
  intros Hmem Hfail.
  destruct (read_data_exact_reply addr width kind meta) as [resume [Heq [_ Herr]]].
  rewrite Heq. cbn [T.run T.step]. rewrite Hmem.
  rewrite Herr. cbn [T.run T.step]. rewrite Hfail. reflexivity.
Qed.

Lemma read_ram_no_meta_step_mem_read {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel kind access addr width tags frame :
  read_access kind = inl access ->
  exists resume,
    (forall bits request_tag, exists data,
      bv_unsigned data = bv_unsigned bits /\
      resume (inl (bits, request_tag)) = I.Ret (data, default_meta)) /\
    resume (inr tt) =
      I.Next (I.GenericFail "exit") (fun impossible => match impossible with end) /\
    T.run old (S fuel) (read_ram kind (Physaddr addr) width false) tags frame =
    match old _ (I.MemRead (Z.to_N width) (I.ReadReq.make (Z.to_N width) addr access None tt false)) frame with
    | None => None
    | Some (response, frame') =>
      T.push
        (I.IEvent (I.MemRead (Z.to_N width)
                     (I.ReadReq.make (Z.to_N width) addr access None tt false))
           response)
        (T.run old fuel (resume response) tags frame')
    end.
Proof.
  intro Hkind.
  rewrite read_ram_no_meta_eq.
  unfold finish_read. rewrite Hkind.
  destruct (read_data_exact_reply addr width access default_meta) as [resume [Heq [Hok Herr]]].
  exists resume. repeat split; try assumption.
  rewrite Heq. cbn [T.run T.step].
  destruct (old _ (I.MemRead (Z.to_N width) (I.ReadReq.make (Z.to_N width) addr access None tt false)) frame)
    as [[response frame'] |]; reflexivity.
Qed.

Lemma read_ram_no_meta_ok {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel kind access addr width tags frame bits req_tag frame' :
  read_access kind = inl access ->
  old _ (I.MemRead (Z.to_N width) (I.ReadReq.make (Z.to_N width) addr access None tt false)) frame =
    Some (inl (bits, req_tag), frame') ->
  exists data,
    bv_unsigned data = bv_unsigned bits /\
    T.run old (S (S fuel)) (read_ram kind (Physaddr addr) width false) tags frame =
    Some (@T.Answer exception Frame (mword (8 * width) * bool) (data, default_meta) tags frame'
            [I.IEvent (I.MemRead (Z.to_N width)
                         (I.ReadReq.make (Z.to_N width) addr access None tt false))
               (inl (bits, req_tag))]).
Proof.
  intros Hkind Hold.
  rewrite read_ram_no_meta_eq.
  unfold finish_read. rewrite Hkind.
  apply read_data_mem_read_ok. exact Hold.
Qed.

Lemma read_ram_no_meta_err {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel kind access addr width tags frame frame' :
  read_access kind = inl access ->
  old _ (I.MemRead (Z.to_N width) (I.ReadReq.make (Z.to_N width) addr access None tt false)) frame =
    Some (inr tt, frame') ->
  old _ (I.GenericFail "exit") frame' = None ->
  T.run old (S (S (S fuel))) (read_ram kind (Physaddr addr) width false) tags frame = None.
Proof.
  intros Hkind Hmem Hfail.
  rewrite read_ram_no_meta_eq.
  unfold finish_read. rewrite Hkind.
  eapply read_data_mem_read_err; eassumption.
Qed.

Lemma write_data_refusal_no_meta addr width kind data meta :
  exists bits : bv (8 * Z.to_N width)%N, exists resume,
    bv_unsigned bits = bv_unsigned data /\
    write_data addr width kind data meta =
      I.Next (I.MemWrite (Z.to_N width)
                (I.WriteReq.make (Z.to_N width) addr kind bits None tt None)) resume /\
    resume (inr tt) = I.Ret false.
Proof.
  destruct (write_data_exact_reply addr width kind data meta) as [bits [resume [Hbits [Heq [_ Herr]]]]].
  exists bits, resume. auto.
Qed.

Lemma write_data_refusal_run {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel addr width kind data meta tags frame frame' :
  exists bits : bv (8 * Z.to_N width)%N,
    bv_unsigned bits = bv_unsigned data /\
    (old _ (I.MemWrite (Z.to_N width)
              (I.WriteReq.make (Z.to_N width) addr kind bits None tt None)) frame =
       Some (inr tt, frame') ->
     T.run old (S (S fuel)) (write_data addr width kind data meta) tags frame =
     Some (@T.Answer exception Frame bool false tags frame'
             [I.IEvent (I.MemWrite (Z.to_N width)
                         (I.WriteReq.make (Z.to_N width) addr kind bits None tt None))
                (inr tt)])).
Proof.
  destruct (write_data_refusal_no_meta addr width kind data meta)
    as [bits [resume [Hbits [Heq Herr]]]].
  exists bits. split.
  - exact Hbits.
  - intro Hold.
    rewrite Heq. cbn [T.run T.step]. rewrite Hold.
    rewrite Herr. reflexivity.
Qed.

Lemma write_ram_refusal_run {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel kind access addr width data meta tags frame frame' :
  write_access kind = inl access ->
  exists bits : bv (8 * Z.to_N width)%N,
    bv_unsigned bits = bv_unsigned data /\
    (old _ (I.MemWrite (Z.to_N width)
              (I.WriteReq.make (Z.to_N width) addr access bits None tt None)) frame =
       Some (inr tt, frame') ->
     T.run old (S (S fuel)) (write_ram kind (Physaddr addr) width data meta) tags frame =
     Some (@T.Answer exception Frame bool false tags frame'
             [I.IEvent (I.MemWrite (Z.to_N width)
                         (I.WriteReq.make (Z.to_N width) addr access bits None tt None))
                (inr tt)])).
Proof.
  intro Hkind.
  rewrite write_ram_request_order, Hkind.
  apply write_data_refusal_run.
Qed.

Lemma read_ram_with_meta_head_tag_read kind addr width :
  read_ram kind (Physaddr addr) width true =
  I.Next (I.TagRead (tag_key addr)) (finish_read addr width kind).
Proof. apply read_ram_request_order. Qed.

Lemma read_ram_with_meta_not_tag_free kind addr width :
  ~ CanonicalOldOutcomes.tag_free (read_ram kind (Physaddr addr) width true).
Proof.
  intro Hfree.
  rewrite read_ram_with_meta_head_tag_read in Hfree.
  exact (CanonicalOldOutcomes.tag_free_head _ _ Hfree).
Qed.

Lemma read_ram_meta_not_tag_free addr width :
  ~ CanonicalOldOutcomes.tag_free (__ReadRAM_Meta addr width).
Proof.
  intro Hfree.
  exact (CanonicalOldOutcomes.tag_free_head _ _ Hfree).
Qed.

Lemma write_ram_meta_zero_not_tag_free meta :
  ~ CanonicalOldOutcomes.tag_free (__WriteRAM_Meta (zeros 64) 1 meta).
Proof.
  intro Hfree.
  apply CanonicalOldOutcomes.tag_free_head in Hfree.
  vm_compute in Hfree.
  exact Hfree.
Qed.

Lemma read_ram_with_meta_ok {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel kind access addr width tags frame bits req_tag frame' :
  read_access kind = inl access ->
  old _ (I.MemRead (Z.to_N width) (I.ReadReq.make (Z.to_N width) addr access None tt false)) frame =
    Some (inl (bits, req_tag), frame') ->
  exists data,
    bv_unsigned data = bv_unsigned bits /\
    T.run old (S (S (S fuel))) (read_ram kind (Physaddr addr) width true) tags frame =
    Some (@T.Answer exception Frame (mword (8 * width) * bool)
            (data, T.tag_get tags (tag_key addr)) tags frame'
            [I.IEvent (I.TagRead (tag_key addr)) (T.tag_get tags (tag_key addr));
             I.IEvent (I.MemRead (Z.to_N width)
                          (I.ReadReq.make (Z.to_N width) addr access None tt false))
                (inl (bits, req_tag))]).
Proof.
  intros Hkind Hold.
  destruct (read_data_mem_read_ok old fuel addr width access (T.tag_get tags (tag_key addr))
              tags frame bits req_tag frame' Hold)
    as [data [Hbits Hrun]].
  exists data. split.
  - exact Hbits.
  - rewrite read_ram_tag_interpretation.
    unfold finish_read. rewrite Hkind, Hrun.
    reflexivity.
Qed.

Lemma read_ram_with_meta_err {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel kind access addr width tags frame frame' :
  read_access kind = inl access ->
  old _ (I.MemRead (Z.to_N width) (I.ReadReq.make (Z.to_N width) addr access None tt false)) frame =
    Some (inr tt, frame') ->
  old _ (I.GenericFail "exit") frame' = None ->
  T.run old (S (S (S (S fuel)))) (read_ram kind (Physaddr addr) width true) tags frame = None.
Proof.
  intros Hkind Hmem Hfail.
  rewrite read_ram_tag_interpretation.
  unfold finish_read. rewrite Hkind.
  erewrite read_data_mem_read_err; [reflexivity | exact Hmem | exact Hfail].
Qed.

Lemma write_data_ok_step {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel addr width kind data meta tags frame frame' :
  exists bits : bv (8 * Z.to_N width)%N,
    bv_unsigned bits = bv_unsigned data /\
    (forall status : option bool,
       old _ (I.MemWrite (Z.to_N width)
                (I.WriteReq.make (Z.to_N width) addr kind bits None tt None)) frame =
         Some (inl status, frame') ->
       T.run old (S fuel) (write_data addr width kind data meta) tags frame =
       T.push
         (I.IEvent (I.MemWrite (Z.to_N width)
                      (I.WriteReq.make (Z.to_N width) addr kind bits None tt None))
            (inl status))
         (T.run old fuel (D.bind (__WriteRAM_Meta addr width meta) (fun _ => I.Ret true)) tags frame')).
Proof.
  destruct (write_data_exact_reply addr width kind data meta)
    as [bits [resume [Hbits [Heq [Hok _]]]]].
  exists bits. split.
  - exact Hbits.
  - intros status Hold.
    rewrite Heq. cbn [T.run T.step]. rewrite Hold, Hok. reflexivity.
Qed.

Lemma write_ram_ok_step {Frame : Type}
  (old : forall Response, I.outcome (fun _ => exception) Response -> Frame -> option (Response * Frame))
  fuel kind access addr width data meta tags frame frame' :
  write_access kind = inl access ->
  exists bits : bv (8 * Z.to_N width)%N,
    bv_unsigned bits = bv_unsigned data /\
    (forall status : option bool,
       old _ (I.MemWrite (Z.to_N width)
                (I.WriteReq.make (Z.to_N width) addr access bits None tt None)) frame =
         Some (inl status, frame') ->
       T.run old (S fuel) (write_ram kind (Physaddr addr) width data meta) tags frame =
       T.push
         (I.IEvent (I.MemWrite (Z.to_N width)
                      (I.WriteReq.make (Z.to_N width) addr access bits None tt None))
            (inl status))
         (T.run old fuel (D.bind (__WriteRAM_Meta addr width meta) (fun _ => I.Ret true)) tags frame')).
Proof.
  intro Hkind.
  rewrite write_ram_request_order, Hkind.
  apply write_data_ok_step.
Qed.

Local Open Scope stdpp_scope.

Definition canon_word (z : Z) : mword 64 := to_bits_truncate 64 z.

Record canon_frame := CanonFrame {
  canon_data_bytes : gmap Z Z;
  canon_register_values : gmap Z Z;
  canon_output_messages : list string
}.

Definition canon_inhabited_frame : canon_frame :=
  CanonFrame (<[0 := 37]> empty) (<[4 := 91]> empty) ["preserved"%string].

Definition canon_environment (status : option bool + unit) (read_ok : bool) Resp
  (oc : I.outcome (fun _ => exception) Resp) (f : canon_frame) : option (Resp * canon_frame) :=
  match oc in I.outcome _ Resp return option (Resp * canon_frame) with
  | I.MemWrite _ _ => Some (status, f)
  | I.MemRead n _ => Some ((if read_ok then inl (Z_to_bv (8 * n) 0, None) else inr tt), f)
  | _ => None
  end.

Inductive canon_observation :=
| CanonRTag (key : Z) (value : bool)
| CanonWTag (key : Z) (value : bool)
| CanonRData
| CanonWData
| CanonOther.

Definition canon_observe (ev : I.iEvent (fun _ => exception)) : canon_observation :=
  match ev with
  | I.IEvent oc response =>
    (match oc in I.outcome _ Resp return Resp -> canon_observation with
     | I.TagRead key => fun value => CanonRTag (uint key) value
     | I.TagWrite key value => fun _ => CanonWTag (uint key) value
     | I.MemRead _ _ => fun _ => CanonRData
     | I.MemWrite _ _ => fun _ => CanonWData
     | _ => fun _ => CanonOther
     end) response
  end.

Definition canon_trace {X} status read_ok fuel (p : M X) tags :=
  match T.run (canon_environment status read_ok) fuel p tags canon_inhabited_frame with
  | None => None
  | Some r => Some (map canon_observe (@T.events exception canon_frame X r))
  end.

Definition canon_final {X} status read_ok fuel (p : M X) tags :=
  match T.run (canon_environment status read_ok) fuel p tags canon_inhabited_frame with
  | None => None
  | Some r => Some (@T.returned exception canon_frame X r,
                    @T.final_tags exception canon_frame X r,
                    @T.final_frame exception canon_frame X r)
  end.

Example canon_aligned_capability_meta :
  canon_trace (inl None) true 10 (__WriteRAM_Meta (canon_word 8) 8 true) empty =
    Some [CanonWTag 1 true] /\
  canon_trace (inl None) true 10 (__WriteRAM_Meta (canon_word 8) 8 false) empty =
    Some [CanonWTag 1 false].
Proof. Timeout 10 vm_compute. split; reflexivity. Qed.

Example canon_aligned_capability_write_ram :
  forall (status : option bool) (meta : bool),
    let tags0 := T.tag_put (T.tag_put (T.tag_put empty (canon_word 0) true)
                                       (canon_word 1) (negb meta))
                           (canon_word 2) true in
    let expected_tags := T.tag_put tags0 (canon_word 1) meta in
    canon_trace (inl status) true 10
      (write_ram Write_plain (Physaddr (canon_word 8)) 8 (zeros 64) meta) tags0 =
      Some [CanonWData; CanonWTag 1 meta] /\
    canon_final (inl status) true 10
      (write_ram Write_plain (Physaddr (canon_word 8)) 8 (zeros 64) meta) tags0 =
      Some (true, expected_tags, canon_inhabited_frame) /\
    T.tag_get expected_tags (canon_word 0) = true /\
    T.tag_get expected_tags (canon_word 1) = meta /\
    T.tag_get expected_tags (canon_word 2) = true.
Proof.
  Timeout 10 (intros [b|] meta; [destruct b|]; destruct meta;
              vm_compute; repeat split; reflexivity).
Qed.

Example canon_partial_granule_meta :
  canon_trace (inl None) true 10 (__WriteRAM_Meta (canon_word 7) 2 false) empty =
  Some [CanonWTag 0 false; CanonWTag 1 false].
Proof. Timeout 10 vm_compute. reflexivity. Qed.

Example canon_partial_granule_write_ram :
  let tags0 := T.tag_put (T.tag_put (T.tag_put empty (canon_word 0) true)
                                     (canon_word 1) true)
                         (canon_word 2) true in
  let expected_tags :=
    T.tag_put (T.tag_put tags0 (canon_word 0) false) (canon_word 1) false in
  canon_trace (inl None) true 10
    (write_ram Write_plain (Physaddr (canon_word 7)) 2 (zeros 16) false) tags0 =
    Some [CanonWData; CanonWTag 0 false; CanonWTag 1 false] /\
  canon_final (inl None) true 10
    (write_ram Write_plain (Physaddr (canon_word 7)) 2 (zeros 16) false) tags0 =
    Some (true, expected_tags, canon_inhabited_frame) /\
  T.tag_get expected_tags (canon_word 0) = false /\
  T.tag_get expected_tags (canon_word 1) = false /\
  T.tag_get expected_tags (canon_word 2) = true.
Proof. Timeout 10 vm_compute. repeat split; reflexivity. Qed.

Example canon_multiple_granules_meta :
  canon_trace (inl None) true 10 (__WriteRAM_Meta (canon_word 7) 18 false) empty =
  Some [CanonWTag 0 false; CanonWTag 1 false; CanonWTag 2 false; CanonWTag 3 false].
Proof. Timeout 10 vm_compute. reflexivity. Qed.

Example canon_multiple_granules_write_ram :
  let tags0 :=
    T.tag_put (T.tag_put (T.tag_put (T.tag_put (T.tag_put empty (canon_word 0) true)
                                                (canon_word 1) true)
                                     (canon_word 2) true)
                          (canon_word 3) true)
              (canon_word 4) true in
  let expected_tags :=
    T.tag_put (T.tag_put (T.tag_put (T.tag_put tags0 (canon_word 0) false)
                                     (canon_word 1) false)
                          (canon_word 2) false)
              (canon_word 3) false in
  canon_trace (inl None) true 10
    (write_ram Write_plain (Physaddr (canon_word 7)) 18 (zeros 144) false) tags0 =
    Some [CanonWData; CanonWTag 0 false; CanonWTag 1 false; CanonWTag 2 false; CanonWTag 3 false] /\
  canon_final (inl None) true 10
    (write_ram Write_plain (Physaddr (canon_word 7)) 18 (zeros 144) false) tags0 =
    Some (true, expected_tags, canon_inhabited_frame) /\
  T.tag_get expected_tags (canon_word 0) = false /\
  T.tag_get expected_tags (canon_word 1) = false /\
  T.tag_get expected_tags (canon_word 2) = false /\
  T.tag_get expected_tags (canon_word 3) = false /\
  T.tag_get expected_tags (canon_word 4) = true.
Proof. Timeout 10 vm_compute. repeat split; reflexivity. Qed.

Example canon_fixed_width_wraparound_meta :
  canon_trace (inl None) true 10
    (__WriteRAM_Meta (canon_word 18446744073709551615) 2 false) empty = Some [].
Proof. reflexivity. Qed.

Example canon_fixed_width_wraparound_write_ram :
  forall tags,
    canon_final (inl None) true 10
      (write_ram Write_plain (Physaddr (canon_word 18446744073709551615)) 2 (zeros 16) false) tags =
    Some (true, tags, canon_inhabited_frame).
Proof. intro tags. reflexivity. Qed.

Example canon_metadata_read_present_vs_absent :
  let tags_set := T.tag_put empty (canon_word 1) true in
  let project (r : option (mword (8 * 8) * bool * T.tagmap * canon_frame)) :=
    option_map (fun '((data, tag), tags', f') => (bv_unsigned data, tag, tags', f')) r in
  canon_trace (inl None) true 10
    (read_ram Read_plain (Physaddr (canon_word 8)) 8 true) tags_set =
    Some [CanonRTag 1 true; CanonRData] /\
  canon_trace (inl None) true 10
    (read_ram Read_plain (Physaddr (canon_word 8)) 8 true) empty =
    Some [CanonRTag 1 false; CanonRData] /\
  project (canon_final (inl None) true 10
             (read_ram Read_plain (Physaddr (canon_word 8)) 8 true) tags_set) =
    Some (0, true, tags_set, canon_inhabited_frame) /\
  project (canon_final (inl None) true 10
             (read_ram Read_plain (Physaddr (canon_word 8)) 8 true) empty) =
    Some (0, false, empty, canon_inhabited_frame) /\
  canon_final (inl None) true 10
    (read_ram Read_plain (Physaddr (canon_word 8)) 8 true) tags_set <>
  canon_final (inl None) true 10
    (read_ram Read_plain (Physaddr (canon_word 8)) 8 true) empty.
Proof. Timeout 10 vm_compute. repeat split; [reflexivity.. | intro H; inversion H]. Qed.

Example canon_early_return_carries_write :
  @D.catch_early_return bool exception
    (D.bind (@D.write_tag_bool (bool + exception)%type (canon_word 1) true)
       (fun _ => @D.early_return bool bool exception true)) =
  I.Next (I.TagWrite (canon_word 1) true) (fun _ => I.Ret true).
Proof. reflexivity. Qed.

Example canon_early_return_carries_read :
  @D.catch_early_return bool exception
    (D.bind (@D.read_tag_bool (bool + exception)%type (canon_word 1))
       (fun tag => @D.early_return bool bool exception tag)) =
  I.Next (I.TagRead (canon_word 1)) (fun tag => I.Ret tag).
Proof. reflexivity. Qed.

Example canon_real_exception_is_caught :
  @D.try_catch bool exception exception
    (D.throw (Error_not_implemented "example"%string)) (fun _ => D.returnm true) =
  I.Ret true.
Proof. reflexivity. Qed.

Example canon_write_tag_is_not_an_exception :
  @D.try_catch unit exception exception (D.write_tag_bool (canon_word 1) true)
    (fun _ => D.fail "must not catch tag"%string) =
  I.Next (I.TagWrite (canon_word 1) true) I.Ret.
Proof. reflexivity. Qed.

Example canon_read_tag_is_not_an_exception :
  @D.try_catch bool exception exception (D.read_tag_bool (canon_word 1))
    (fun _ => D.fail "must not catch tag"%string) =
  I.Next (I.TagRead (canon_word 1)) I.Ret.
Proof. reflexivity. Qed.

Example canon_missing_reordered_extra_tag_refused :
  canon_trace (inl None) true 10 (__WriteRAM_Meta (canon_word 7) 2 false) empty <>
    Some [CanonWTag 0 false] /\
  canon_trace (inl None) true 10 (__WriteRAM_Meta (canon_word 7) 2 false) empty <>
    Some [CanonWTag 1 false; CanonWTag 0 false] /\
  canon_trace (inl None) true 10 (__WriteRAM_Meta (canon_word 7) 2 false) empty <>
    Some [CanonWTag 0 false; CanonWTag 1 false; CanonWTag 2 false].
Proof. Timeout 10 vm_compute. repeat split; discriminate. Qed.

Example canon_absent_response_refused :
  ~ T.legal (canon_environment (inl None) true) (I.TagRead (canon_word 0)) true
    empty canon_inhabited_frame empty canon_inhabited_frame.
Proof. Timeout 10 vm_compute. discriminate. Qed.

Example canon_discarded_write_refused :
  ~ T.legal (canon_environment (inl None) true) (I.TagWrite (canon_word 1) true) tt
    empty canon_inhabited_frame empty canon_inhabited_frame.
Proof. Timeout 10 vm_compute. discriminate. Qed.

Fail Check (D.write_tag_bool (E := exception) (canon_word 1) true : M bool).
Fail Check (I.TagWrite (canon_word 1) true : I.outcome (fun _ => exception) bool).
