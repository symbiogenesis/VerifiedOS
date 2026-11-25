(* SPDX-License-Identifier: Apache-2.0 *)
From SailStdpp Require Import Base ConcurrencyInterface.
Require Import TagInterpreter.
Import ListNotations.

Module OldOutcomes (A : Arch) (I : InterfaceT A).
Module T := TagInterpreter.TagPlane A I.

Section Execution.
Context {E Frame : Type}.
Variable old : forall Y, I.outcome (fun _ => E) Y -> Frame -> option (Y * Frame).

Definition old_event {Y} (oc : I.outcome (fun _ => E) Y) : Prop :=
  match oc with
  | I.TagRead _ => False
  | I.TagWrite _ _ => False
  | I.RegRead _ _ | I.RegWrite _ _ _ | I.MemRead _ _ | I.MemWrite _ _
  | I.InstrAnnounce _ | I.BranchAnnounce _ _ | I.Barrier _
  | I.CacheOp _ | I.TlbOp _ | I.TakeException _ | I.ReturnException _
  | I.TranslationStart _ | I.TranslationEnd _ | I.ExtraOutcome _
  | I.GenericFail _ | I.CycleCount | I.GetCycleCount | I.Choose _ | I.Discard
  | I.Message _ => True
  end.

Inductive tag_free {X} : I.iMon (fun _ => E) X -> Prop :=
| free_ret x : tag_free (I.Ret x)
| free_next {Y} (oc : I.outcome (fun _ => E) Y) (k : Y -> I.iMon (fun _ => E) X) :
    old_event oc -> (forall response, tag_free (k response)) ->
    tag_free (I.Next oc k).

Lemma tag_free_head X (program : I.iMon (fun _ => E) X) :
  tag_free program ->
  match program with
  | I.Ret _ => True
  | I.Next oc _ => old_event oc
  end.
Proof. destruct 1; cbn; auto. Qed.

Record old_answer (X : Type) := OldAnswer {
  result : X;
  frame_after : Frame;
  trace : list (I.iEvent (fun _ => E))
}.
Arguments OldAnswer {X}.
Arguments result {X}.
Arguments frame_after {X}.
Arguments trace {X}.

(* On tag-free computations, the original request goes directly to the environment.
   Its typed response selects the continuation and accompanies the request in the trace. *)
Fixpoint run_old {X} (fuel : nat) (program : I.iMon (fun _ => E) X)
    (frame : Frame) : option (old_answer X) :=
  match fuel with
  | O => None
  | S remaining =>
    match program with
    | I.Ret x => Some (OldAnswer x frame [])
    | I.Next oc k =>
      match old _ oc frame with
      | None => None
      | Some (response, next_frame) =>
        match run_old remaining (k response) next_frame with
        | None => None
        | Some r => Some (OldAnswer (result r) (frame_after r)
                            (I.IEvent oc response :: trace r))
        end
      end
    end
  end.

Lemma old_step_preserved Y (oc : I.outcome (fun _ => E) Y) tags frame :
  old_event oc ->
  T.step old oc tags frame =
  match old Y oc frame with
  | Some (response, next_frame) => Some (response, tags, next_frame)
  | None => None
  end.
Proof. destruct oc; cbn [old_event]; intro H; solve [contradiction | reflexivity]. Qed.

Theorem tag_free_run_preserved X fuel (program : I.iMon (fun _ => E) X) tags frame :
  tag_free program ->
  T.run old fuel program tags frame =
  match run_old fuel program frame with
  | Some r => Some (@T.Answer E Frame X (result r) tags (frame_after r) (trace r))
  | None => None
  end.
Proof.
  revert program frame.
  induction fuel as [|remaining IH]; intros program frame Hfree.
  - reflexivity.
  - destruct Hfree as [x | Y oc k H_old H_free].
    + reflexivity.
    + cbn [T.run run_old].
      rewrite old_step_preserved by exact H_old.
      destruct (old Y oc frame) as [[response next_frame] |].
      * rewrite IH by exact (H_free response).
        destruct (run_old remaining (k response) next_frame); reflexivity.
      * reflexivity.
Qed.
End Execution.

Definition messages : I.iMon (fun _ => unit) bool :=
  I.Next (I.Message "first"%string)
    (fun _ => I.Next (I.Message "second"%string) (fun _ => I.Ret true)).

Definition message_handler {Y} (oc : I.outcome (fun _ => unit) Y) (frame : nat)
    : option (Y * nat) :=
  match oc in I.outcome _ Y return option (Y * nat) with
  | I.Message _ => Some (tt, S frame)
  | _ => None
  end.

Lemma messages_free : tag_free messages.
Proof. repeat constructor. Qed.

Example messages_keep_order tags :
  T.run (@message_handler) (S (S (S O))) messages tags O =
  Some (@T.Answer unit nat bool true tags (S (S O))
    [I.IEvent (I.Message "first"%string) tt; I.IEvent (I.Message "second"%string) tt]).
Proof. rewrite tag_free_run_preserved by exact messages_free. reflexivity. Qed.

Definition one_message {Y} (oc : I.outcome (fun _ => unit) Y) (frame : nat)
    : option (Y * nat) :=
  match frame with
  | O => message_handler oc frame
  | S _ => None
  end.

Example second_message_refusal tags :
  T.run (@one_message) (S (S (S O))) messages tags O = None.
Proof. rewrite tag_free_run_preserved by exact messages_free. reflexivity. Qed.

Example message_fuel_exhaustion tags :
  T.run (@message_handler) (S (S O)) messages tags O = None.
Proof. rewrite tag_free_run_preserved by exact messages_free. reflexivity. Qed.

Example tag_read_excluded key :
  ~ tag_free (I.Next (I.TagRead key) (@I.Ret (fun _ => unit) bool)).
Proof. intro H. exact (tag_free_head _ _ H). Qed.

Example tag_write_excluded key :
  ~ tag_free (I.Next (I.TagWrite key true) (@I.Ret (fun _ => unit) unit)).
Proof. intro H. exact (tag_free_head _ _ H). Qed.
End OldOutcomes.
