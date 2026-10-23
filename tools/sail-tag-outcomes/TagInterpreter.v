(* SPDX-License-Identifier: Apache-2.0 *)
(* Executable raw-key tag legality. The old-event handler is fixed on both sides;
   it is not assumed to implement the machine correctly. *)
From SailStdpp Require Import Base ConcurrencyInterface ConcurrencyInterfaceBuiltins.
From stdpp Require Import gmap.
Import ListNotations.
Local Open Scope Z_scope.
Local Open Scope stdpp_scope.

Module TagPlane (A : Arch) (I : InterfaceT A).
Module D := Defs A I.
Definition tagmap := gmap Z bool.
Definition tag_get (tags : tagmap) (key : mword 64) : bool :=
  default false (tags !! uint key).
Definition tag_put (tags : tagmap) (key : mword 64) (value : bool) : tagmap :=
  <[uint key := value]> tags.

Section Execution.
Context {E Frame : Type}.
Variable old : forall T, I.outcome (fun _ => E) T -> Frame -> option (T * Frame).

Definition step {T} (oc : I.outcome (fun _ => E) T) (tags : tagmap) (frame : Frame)
  : option (T * tagmap * Frame) :=
  match oc in I.outcome _ T return option (T * tagmap * Frame) with
  | I.TagRead key => Some (tag_get tags key, tags, frame)
  | I.TagWrite key value => Some (tt, tag_put tags key value, frame)
  | other => match old _ other frame with
             | Some (response, frame') => Some (response, tags, frame')
             | None => None
             end
  end.

Definition legal {T} (oc : I.outcome (fun _ => E) T) response tags frame tags' frame' :=
  step oc tags frame = Some (response, tags', frame').

Record answer (X : Type) := Answer {
  returned : X;
  final_tags : tagmap;
  final_frame : Frame;
  events : list (I.iEvent (fun _ => E))
}.
Arguments Answer {X}.
Arguments returned {X}.
Arguments final_tags {X}.
Arguments final_frame {X}.
Arguments events {X}.
Definition push {X} ev (result : option (answer X)) :=
  match result with
  | None => None
  | Some r => Some (Answer (returned r) (final_tags r) (final_frame r) (ev :: events r))
  end.

Fixpoint run {X} (fuel : nat) (program : I.iMon (fun _ => E) X)
  (tags : tagmap) (frame : Frame) : option (answer X) :=
  match fuel with
  | O => None
  | S fuel =>
    match program with
    | I.Ret x => Some (Answer x tags frame [])
    | I.Next oc k =>
      match step oc tags frame with
      | None => None
      | Some (response, tags', frame') =>
        push (I.IEvent oc response) (run fuel (k response) tags' frame')
      end
    end
  end.

Lemma legal_read tags key frame :
  legal (I.TagRead key) (tag_get tags key) tags frame tags frame.
Proof. reflexivity. Qed.
Lemma legal_write tags key value frame :
  legal (I.TagWrite key value) tt tags frame (tag_put tags key value) frame.
Proof. reflexivity. Qed.
Lemma read_is_constrained tags key frame response tags' frame' :
  legal (I.TagRead key) response tags frame tags' frame' ->
  response = tag_get tags key /\ tags' = tags /\ frame' = frame.
Proof. unfold legal, step. intro H. inversion H. auto. Qed.
Lemma write_is_exact tags key value frame response tags' frame' :
  legal (I.TagWrite key value) response tags frame tags' frame' ->
  response = tt /\ tags' = tag_put tags key value /\ frame' = frame.
Proof. unfold legal, step. intro H. inversion H. auto. Qed.
Lemma read_bridge X fuel tags frame key (k : bool -> D.monad E X) :
  run (S fuel) (D.bind (D.read_tag_bool key) k) tags frame =
  push (I.IEvent (I.TagRead key) (tag_get tags key))
       (run fuel (k (tag_get tags key)) tags frame).
Proof. reflexivity. Qed.
Lemma write_bridge X fuel tags frame key value (k : unit -> D.monad E X) :
  run (S fuel) (D.bind (D.write_tag_bool key value) k) tags frame =
  push (I.IEvent (I.TagWrite key value) tt)
       (run fuel (k tt) (tag_put tags key value) frame).
Proof. reflexivity. Qed.
End Execution.

Lemma tag_put_same tags key value : tag_get (tag_put tags key value) key = value.
Proof. unfold tag_get, tag_put, tagmap in *. rewrite lookup_insert_eq. reflexivity. Qed.
Lemma tag_put_other tags key neighbor value : uint key <> uint neighbor ->
  tag_get (tag_put tags key value) neighbor = tag_get tags neighbor.
Proof. intro H. unfold tag_get, tag_put, tagmap in *. rewrite lookup_insert_ne; congruence. Qed.
Lemma absent_false key : tag_get (empty : tagmap) key = false.
Proof. unfold tag_get, tagmap in *. rewrite lookup_empty. reflexivity. Qed.

Lemma try_catch_read X E1 E2 key (k : bool -> D.monad E1 X) (h : E1 -> D.monad E2 X) :
  D.try_catch (I.Next (I.TagRead key) k) h =
  I.Next (I.TagRead key) (fun response => D.try_catch (k response) h).
Proof. reflexivity. Qed.
Lemma try_catch_write X E1 E2 key value (k : unit -> D.monad E1 X) (h : E1 -> D.monad E2 X) :
  D.try_catch (I.Next (I.TagWrite key value) k) h =
  I.Next (I.TagWrite key value) (fun response => D.try_catch (k response) h).
Proof. reflexivity. Qed.
Lemma map_extra_read X out1 out2 key (k : bool -> I.iMon out1 X) (f : I.iMonExtraMap out1 out2) :
  I.map_extra_iMon f (I.Next (I.TagRead key) k) =
  I.Next (I.TagRead key) (fun response => I.map_extra_iMon f (k response)).
Proof. reflexivity. Qed.
Lemma map_extra_write X out1 out2 key value (k : unit -> I.iMon out1 X) (f : I.iMonExtraMap out1 out2) :
  I.map_extra_iMon f (I.Next (I.TagWrite key value) k) =
  I.Next (I.TagWrite key value) (fun response => I.map_extra_iMon f (k response)).
Proof. reflexivity. Qed.
Lemma lift_write R E key value :
  @D.liftR unit R E (D.write_tag_bool key value) =
  I.Next (I.TagWrite key value) I.Ret.
Proof. reflexivity. Qed.
End TagPlane.