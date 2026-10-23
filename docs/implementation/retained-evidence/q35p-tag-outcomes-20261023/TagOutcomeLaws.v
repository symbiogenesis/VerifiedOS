(* SPDX-License-Identifier: Apache-2.0 *)
From stdpp Require Import gmap bitvector.definitions.
Require Import SailStdpp.Base SailStdpp.ConcurrencyInterface
  SailStdpp.ConcurrencyInterfaceBuiltins.

Module TagOutcomeLaws (A : Arch) (I : InterfaceT A).
Module D := Defs A I.

Definition tags := gmap Z bool.
Definition tag_get (s : tags) (key : mword 64) : bool :=
  default false (s !! bv_unsigned key).
Definition tag_put (s : tags) (key : mword 64) (value : bool) : tags :=
  <[bv_unsigned key := value]> s.

(* Interpret only tags. Every other request and its response stay in order
   in the residual computation, under the same fixed environment. *)
Fixpoint interpret {E : Type -> Type} {B}
    (m : I.iMon E B) (s : tags) : I.iMon E (B * tags) :=
  match m with
  | I.Ret b => I.Ret (b,s)
  | I.Next oc k0 =>
      let k := fun x s' => interpret (k0 x) s' in
      match oc in I.outcome _ T
          return (T -> tags -> I.iMon E (B * tags)) -> I.iMon E (B * tags) with
      | I.TagRead key => fun k => k (tag_get s key) s
      | I.TagWrite key value => fun k => k tt (tag_put s key value)
      | oc => fun k => I.Next oc (fun x => k x s)
      end k
  end.

Definition is_tag {E T} (oc : I.outcome E T) : bool :=
  match oc with I.TagRead _ | I.TagWrite _ _ => true | _ => false end.

Lemma absent_false s key :
  s !! bv_unsigned key = None -> tag_get s key = false.
Proof. 1: intros H. 1: unfold tag_get. 1: rewrite H. 1: reflexivity. Qed.

Lemma lookup_written s key value :
  tag_get (tag_put s key value) key = value.
Proof. 1: unfold tag_get, tag_put. 1: rewrite (lookup_insert_eq (s : gmap Z bool) (bv_unsigned key) value). 1: reflexivity. Qed.

Lemma neighbor_framed s key other value :
  bv_unsigned other <> bv_unsigned key ->
  tag_get (tag_put s key value) other = tag_get s other.
Proof. 1: intros H. 1: unfold tag_get, tag_put.
  1: rewrite (lookup_insert_ne (s : gmap Z bool) (bv_unsigned key) (bv_unsigned other) value); [reflexivity | congruence]. Qed.

Lemma read_bridge {E B} s key (k : bool -> D.monad E B) :
  interpret (D.bind (D.read_tag_bool key) k) s =
  interpret (k (tag_get s key)) s.
Proof. 1: reflexivity. Qed.

Lemma write_bridge {E B} s key value (k : unit -> D.monad E B) :
  interpret (D.bind (D.write_tag_bool key value) k) s =
  interpret (k tt) (tag_put s key value).
Proof. 1: reflexivity. Qed.

Lemma read_native {E} s key :
  interpret (@D.read_tag_bool E key) s =
  I.Ret (tag_get s key,s).
Proof. 1: reflexivity. Qed.

Lemma write_native {E} s key value :
  interpret (@D.write_tag_bool E key value) s =
  I.Ret (tt,tag_put s key value).
Proof. 1: reflexivity. Qed.

Lemma old_event_preserved {E B T} (oc : I.outcome E T)
    (k : T -> I.iMon E B) s :
  is_tag oc = false ->
  interpret (I.Next oc k) s =
  I.Next oc (fun x => interpret (k x) s).
Proof. 1: destruct oc; intros H; try discriminate; reflexivity. Qed.

Lemma read_try_catch {E1 E2 B} key
    (k : bool -> D.monad E1 B) (h : E1 -> D.monad E2 B) :
  D.try_catch (I.Next (I.TagRead key) k) h =
  I.Next (I.TagRead key) (fun x => D.try_catch (k x) h).
Proof. 1: reflexivity. Qed.

Lemma write_try_catch {E1 E2 B} key value
    (k : unit -> D.monad E1 B) (h : E1 -> D.monad E2 B) :
  D.try_catch (I.Next (I.TagWrite key value) k) h =
  I.Next (I.TagWrite key value) (fun x => D.try_catch (k x) h).
Proof. 1: reflexivity. Qed.

Lemma read_extra_map {E1 E2 B} (f : I.iMonExtraMap E1 E2)
    key (k : bool -> I.iMon E1 B) :
  I.map_extra_iMon f (I.Next (I.TagRead key) k) =
  I.Next (I.TagRead key) (fun x => I.map_extra_iMon f (k x)).
Proof. 1: reflexivity. Qed.

Lemma write_extra_map {E1 E2 B} (f : I.iMonExtraMap E1 E2)
    key value (k : unit -> I.iMon E1 B) :
  I.map_extra_iMon f (I.Next (I.TagWrite key value) k) =
  I.Next (I.TagWrite key value) (fun x => I.map_extra_iMon f (k x)).
Proof. 1: reflexivity. Qed.

Lemma tag_before_early_return {E B} s key value (result : B) :
  interpret (D.catch_early_return
    (D.bind (@D.write_tag_bool (B + E)%type key value)
      (fun _ => @D.early_return B B E result))) s =
  I.Ret (result,tag_put s key value).
Proof. 1: reflexivity. Qed.

Lemma read_write_read_clear {E} s key :
  interpret (@D.bind bool (bool * bool) E (D.read_tag_bool key)
    (fun before => D.bind (D.write_tag_bool key true)
      (fun _ => D.bind (D.read_tag_bool key)
        (fun after => D.bind (D.write_tag_bool key false)
          (fun _ => D.bind (D.read_tag_bool key)
            (fun cleared => D.returnm (after,cleared))))))) s =
  I.Ret ((true,false),tag_put (tag_put s key true) key false).
Proof. 1: cbn -[tag_get tag_put]. 1: rewrite !lookup_written. 1: reflexivity. Qed.
End TagOutcomeLaws.
