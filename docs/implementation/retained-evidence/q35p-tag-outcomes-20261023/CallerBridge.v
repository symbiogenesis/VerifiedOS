(* SPDX-License-Identifier: Apache-2.0 *)
From stdpp Require Import gmap bitvector.definitions.
Require Import SailStdpp.Base SailStdpp.ConcurrencyInterface SailStdpp.ConcurrencyInterfaceBuiltins.
Require Import Probe.bindings_types Probe.bindings TagQualification.TagOutcomeLaws.
Module L := TagOutcomeLaws bindings_types.Arch bindings_types.Interface.
Module I := bindings_types.Interface.
Module D := bindings_types.Defs.
Import ListNotations.
Open Scope Z_scope.

Definition raw_key (z : Z) : mword 64 := get_slice_int 64 z 0.
Definition act := (Z * bool)%type.
Fixpoint writes {B} (m : M B) : option (list act) :=
  match m with
  | I.Ret _ => Some []
  | I.Next oc k0 =>
      match oc in I.outcome _ T return (T -> M B) -> option (list act) with
      | I.TagWrite key value => fun k =>
          match writes (k tt) with
          | Some rest => Some ((bv_unsigned key,value)::rest)
          | None => None
          end
      | _ => fun _ => None
      end k0
  end.

Fixpoint expected (from to : Z) (n : nat) (meta : bool) : list act :=
  if from <=? to then
    match n with
    | O => []
    | S n => (bv_unsigned (raw_key from),meta)::expected (from+1) to n meta
    end
  else [].
Fixpoint expected_state (from to : Z) (n : nat) (meta : bool) (s : L.tags) : L.tags :=
  if from <=? to then
    match n with
    | O => s
    | S n => expected_state (from+1) to n meta (L.tag_put s (raw_key from) meta)
    end
  else s.

Lemma loop_events from to n meta :
  writes (D.foreach_ZM_up' from to 1 n tt
    (fun i _ => @D.write_tag_bool exception (raw_key i) meta)) =
  Some (expected from to n meta).
Proof.
  1: revert from; induction n; intros from; cbn [D.foreach_ZM_up' expected]; destruct (from <=? to) eqn:H.
  all: cbn [writes D.write_tag_bool D.bind I.iMon_bind].
  all: try reflexivity.
  1: rewrite IHn. 1: reflexivity.
Qed.

Lemma loop_state {B} from to n meta s (k : unit -> M B) :
  L.interpret (D.bind (D.foreach_ZM_up' from to 1 n tt
    (fun i _ => @D.write_tag_bool exception (raw_key i) meta)) k) s =
  L.interpret (k tt) (expected_state from to n meta s).
Proof.
  1: revert from s; induction n; intros from s; cbn [D.foreach_ZM_up' expected_state]; destruct (from <=? to) eqn:H.
  all: cbn [D.write_tag_bool D.bind I.iMon_bind L.interpret].
  all: try reflexivity.
  1: apply IHn.
Qed.

Definition endpoints addr width :=
  (uint (addr_to_tag_addr addr),
   uint (addr_to_tag_addr (add_vec_int addr (width-1)))).

Lemma metadata_events addr width meta :
  writes (__WriteRAM_Meta addr width meta) =
  let '(first,last) := endpoints addr width in
  Some (expected first last (S (Z.abs_nat (first-last))) meta).
Proof. 1: apply loop_events. Qed.

Lemma metadata_state {B} addr width meta s (k : unit -> M B) :
  L.interpret (D.bind (__WriteRAM_Meta addr width meta) k) s =
  let '(first,last) := endpoints addr width in
  L.interpret (k tt)
    (expected_state first last (S (Z.abs_nat (first-last))) meta s).
Proof. 1: apply loop_state. Qed.

Lemma metadata_read {B} addr width s (k : bool -> M B) :
  L.interpret (D.bind (__ReadRAM_Meta addr width) k) s =
  L.interpret (k (L.tag_get s (zero_extend' 64 (addr_to_tag_addr addr)))) s.
Proof. 1: reflexivity. Qed.

Definition resume_write {B} (m : M B) (r : option bool + unit) : option (M B) :=
  match m with
  | I.Ret _ => None
  | I.Next oc k0 =>
      match oc in I.outcome _ T return (T -> M B) -> option (M B) with
      | I.MemWrite _ _ => fun k => Some (k r)
      | _ => fun _ => None
      end k0
  end.

Lemma physical_write_response addr width data meta r :
  resume_write (write_ram Write_plain (Physaddr addr) width data meta) r =
  match r with
  | inl _ => Some (D.bind (__WriteRAM_Meta addr width meta) (fun _ => returnM true))
  | inr tt => Some (returnM false)
  end.
Proof. 1: destruct r as [r|[]]; reflexivity. Qed.

Definition head {B} (m : M B) : nat :=
  match m with
  | I.Ret _ => 0%nat
  | I.Next oc _ =>
      match oc with
      | I.TagRead _ => 1%nat
      | I.TagWrite _ _ => 2%nat
      | I.MemRead _ _ => 3%nat
      | I.MemWrite _ _ => 4%nat
      | _ => 5%nat
      end
  end.
Definition after_tag_read {B} (m : M B) (r : bool) : option (M B) :=
  match m with
  | I.Ret _ => None
  | I.Next oc k0 =>
      match oc in I.outcome _ T return (T -> M B) -> option (M B) with
      | I.TagRead _ => fun k => Some (k r)
      | _ => fun _ => None
      end k0
  end.
Definition after_read_refusal {B} (m : M B) : option (M B) :=
  match m with
  | I.Ret _ => None
  | I.Next oc k0 =>
      match oc in I.outcome _ T return (T -> M B) -> option (M B) with
      | I.MemRead _ _ => fun k => Some (k (inr tt))
      | _ => fun _ => None
      end k0
  end.

Lemma requested_read_first addr width :
  head (read_ram Read_plain (Physaddr addr) width true) = 1%nat.
Proof. 1: reflexivity. Qed.
Lemma unrequested_read_first addr width :
  head (read_ram Read_plain (Physaddr addr) width false) = 3%nat.
Proof. 1: reflexivity. Qed.
Lemma requested_read_then_data addr width response :
  option_map head (after_tag_read (read_ram Read_plain (Physaddr addr) width true) response) =
  Some 3%nat.
Proof. 1: reflexivity. Qed.
Lemma unrequested_read_refusal addr width :
  option_map head (after_read_refusal (read_ram Read_plain (Physaddr addr) width false)) =
  Some 5%nat.
Proof. 1: reflexivity. Qed.

Example aligned_capability :
  writes (__WriteRAM_Meta (raw_key 16) 8 true) = Some [(2,true)].
Proof. 1: vm_compute. 1: reflexivity. Qed.
Example partial_clear :
  writes (__WriteRAM_Meta (raw_key 17) 1 false) = Some [(2,false)].
Proof. 1: vm_compute. 1: reflexivity. Qed.
Example multi_clear :
  writes (__WriteRAM_Meta (raw_key 7) 10 false) =
  Some [(0,false);(1,false);(2,false)].
Proof. 1: vm_compute. 1: reflexivity. Qed.
Example wraparound_preserved :
  writes (__WriteRAM_Meta (raw_key (2^64-1)) 2 false) = Some [].
Proof. 1: reflexivity. Qed.
Example absent_zero : L.tag_get (∅ : L.tags) (raw_key 0) = false.
Proof. 1: reflexivity. Qed.
Example absent_max : L.tag_get (∅ : L.tags) (raw_key (2^64-1)) = false.
Proof. 1: reflexivity. Qed.
Example no_extra_granule_shift :
  L.tag_get (L.tag_put (∅ : L.tags) (raw_key 1) true) (raw_key 2) = false.
Proof. 1: vm_compute. 1: reflexivity. Qed.

Fail Definition changed_result_type key : M bool := D.write_tag_bool key true.
Fail Definition discarded_write key :
  (@D.write_tag_bool exception key true) = I.Ret tt := eq_refl.
Fail Definition unconstrained_read key :
  L.interpret (@D.read_tag_bool exception key) ∅ = I.Ret (true,∅) := eq_refl.
Fail Definition extra_shift_alias :
  L.tag_get (L.tag_put (∅ : L.tags) (raw_key 1) true) (raw_key 2) = true := eq_refl.
Fail Definition omitted_clear :
  writes (__WriteRAM_Meta (raw_key 7) 10 false) = Some [(0,false)] := eq_refl.
Fail Definition reordered_clear :
  writes (__WriteRAM_Meta (raw_key 7) 10 false) =
  Some [(2,false);(1,false);(0,false)] := eq_refl.


Definition after_read_zero {B} (m : M B) : option (M B) :=
  match m with
  | I.Ret _ => None
  | I.Next oc k0 =>
      match oc in I.outcome _ T return (T -> M B) -> option (M B) with
      | I.MemRead n _ => fun k => Some (k (inl (bv_0 (8*n)%N,None)))
      | _ => fun _ => None
      end k0
  end.
Definition returned_meta {width} (m : M (mword (8*width) * bool)) : option bool :=
  match m with I.Ret (_,meta) => Some meta | _ => None end.

Lemma requested_read_success_meta addr width response :
  option_bind (after_tag_read (read_ram Read_plain (Physaddr addr) width true) response)
    (fun m => option_bind (after_read_zero m) returned_meta) = Some response.
Proof. 1: reflexivity. Qed.
Lemma unrequested_read_success_default addr width :
  option_bind (after_read_zero (read_ram Read_plain (Physaddr addr) width false))
    returned_meta = Some false.
Proof. 1: reflexivity. Qed.
Lemma requested_read_refusal addr width response :
  option_bind (after_tag_read (read_ram Read_plain (Physaddr addr) width true) response)
    (fun m => option_map head (after_read_refusal m)) = Some 5%nat.
Proof. 1: reflexivity. Qed.

Fail Definition changed_neighbor :
  L.tag_get (L.tag_put (∅ : L.tags) (raw_key 1) true) (raw_key 2) = true := eq_refl.
Fail Definition added_clear :
  writes (__WriteRAM_Meta (raw_key 7) 10 false) =
  Some [(0,false);(1,false);(2,false);(3,false)] := eq_refl.
Fail Definition tag_as_exception key :
  (@D.throw unit exception (Error_not_implemented EmptyString)) =
  D.write_tag_bool key true := eq_refl.
Fail Definition dummy_data_write key value s n (req : I.WriteReq.t n)
  (k : (option bool + unit) -> I.iMon (fun _ => exception) (unit * L.tags)) :
  L.interpret (@D.write_tag_bool exception key value) s =
  I.Next (I.MemWrite n req) k := eq_refl.
