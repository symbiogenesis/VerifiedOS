(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   LastEvent.v

   A last-event query separates trace order from the application's choice of
   relevant events. Tags, commit conditions and fallback values stay in clients.
   This prelude-only support is subject to R-05-163's assumption audit. The
   concrete examples for R-05-165 and R-05-166 distinguish the final selected
   event from the first and distinguish an absent event from a present one.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-05-163 R-05-165 R-05-166
   SHA256: 4c631348347cb256d8d909843632bc4849e204c51521af8b014dbaabd4d358c9
   (*| END derived |*)
   ========================================================================= *)

Fixpoint last_matching {Event Value : Type} (select : Event -> option Value)
    (events : list Event) : option Value :=
  match events with
  | nil => None
  | cons event rest =>
      match last_matching select rest with
      | Some value => Some value
      | None => select event
      end
  end.

Lemma last_matching_app :
  forall (Event Value : Type) (select : Event -> option Value)
         (before after : list Event),
    last_matching select (app before after) =
    match last_matching select after with
    | Some value => Some value
    | None => last_matching select before
    end.
Proof.
  intros Event Value select before. induction before as [|event rest IH]; intro after.
  - simpl. destruct (last_matching select after); reflexivity.
  - simpl. rewrite IH. destruct (last_matching select after); reflexivity.
Qed.

Lemma last_matching_none_cons :
  forall (Event Value : Type) (select : Event -> option Value)
         (event : Event) (rest : list Event),
    last_matching select (cons event rest) = None <->
    select event = None /\ last_matching select rest = None.
Proof.
  intros Event Value select event rest. simpl.
  destruct (last_matching select rest) as [value|] eqn:Hrest.
  - split.
    + intro H. discriminate H.
    + intros [_ H]. discriminate H.
  - split.
    + intro H. exact (conj H eq_refl).
    + intros [H _]. exact H.
Qed.

Lemma last_matching_none_app :
  forall (Event Value : Type) (select : Event -> option Value)
         (before after : list Event),
    last_matching select (app before after) = None <->
    last_matching select before = None /\ last_matching select after = None.
Proof.
  intros Event Value select before after. rewrite last_matching_app.
  destruct (last_matching select after) as [value|] eqn:Hafter.
  - split.
    + intro H. discriminate H.
    + intros [_ H]. discriminate H.
  - split.
    + intro H. exact (conj H eq_refl).
    + intros [H _]. exact H.
Qed.

Example the_last_selected_event_wins :
  last_matching (fun b : bool => Some b) (cons false (cons true nil)) = Some true.
Proof. reflexivity. Qed.

Example absence_is_distinct_from_a_selected_false :
  last_matching (fun b : bool => Some b) nil = None /\
  last_matching (fun b : bool => Some b) (cons false nil) = Some false.
Proof. split; reflexivity. Qed.
