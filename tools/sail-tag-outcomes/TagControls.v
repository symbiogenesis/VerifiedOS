(* SPDX-License-Identifier: Apache-2.0 *)
From SailStdpp Require Import Base ConcurrencyInterface ConcurrencyInterfaceBuiltins.
Require Import bindings_types bindings TagInterpreter.
From stdpp Require Import gmap bitvector.definitions.
Import ListNotations.
Local Open Scope Z_scope.
Local Open Scope stdpp_scope.
Module T := TagInterpreter.TagPlane bindings_types.Arch bindings_types.Interface.
Module I := bindings_types.Interface.
Definition word (z : Z) : mword 64 := bindings.to_bits_truncate 64 z.
Record frame := Frame {
  data_bytes : gmap Z Z;
  register_values : gmap Z Z;
  output_messages : list string
}.
Definition inhabited_frame := Frame (<[0 := 37]> empty) (<[4 := 91]> empty) ["preserved"%string].
Definition environment (status : option bool + unit) (read_ok : bool) T
  (oc : I.outcome (fun _ => exception) T) (f : frame) : option (T * frame) :=
  match oc in I.outcome _ T return option (T * frame) with
  | I.MemWrite _ _ => Some (status, f)
  | I.MemRead n _ => Some ((if read_ok then inl (Z_to_bv (8 * n) 0, None) else inr tt), f)
  | _ => None
  end.
Inductive observation := RTag (key : Z) (value : bool) | WTag (key : Z) (value : bool)
  | RData | WData | Other.
Definition observe (ev : I.iEvent (fun _ => exception)) : observation :=
  match ev with
  | I.IEvent oc response =>
    (match oc in I.outcome _ T return T -> observation with
     | I.TagRead key => fun value => RTag (uint key) value
     | I.TagWrite key value => fun _ => WTag (uint key) value
     | I.MemRead _ _ => fun _ => RData
     | I.MemWrite _ _ => fun _ => WData
     | _ => fun _ => Other
     end) response
  end.
Definition trace {X} status read_ok fuel (p : M X) tags :=
  match T.run (environment status read_ok) fuel p tags inhabited_frame with
  | None => None
  | Some r => Some (map observe (@T.events exception frame X r))
  end.
Definition final {X} status read_ok fuel (p : M X) tags :=
  match T.run (environment status read_ok) fuel p tags inhabited_frame with
  | None => None
  | Some r => Some (@T.returned exception frame X r, @T.final_tags exception frame X r, @T.final_frame exception frame X r)
  end.

Example raw_key_roundtrip :
  T.tag_get (T.tag_put (T.tag_put (empty : T.tagmap) (word 1) true) (word 8) false) (word 1) = true /\
  T.tag_get (T.tag_put (empty : T.tagmap) (word 0) true) (word 0) = true /\
  T.tag_get (T.tag_put (empty : T.tagmap) (word 18446744073709551615) true) (word 18446744073709551615) = true /\
  T.tag_get (T.tag_put (T.tag_put (empty : T.tagmap) (word 1) true) (word 1) false) (word 1) = false.
Proof. Timeout 10 vm_compute. repeat split; reflexivity. Qed.
Example absent_response_refused :
  ~ T.legal (environment (inl None) true) (I.TagRead (word 0)) true
    empty inhabited_frame empty inhabited_frame.
Proof. Timeout 10 vm_compute. discriminate. Qed.
Example discarded_write_refused :
  ~ T.legal (environment (inl None) true) (I.TagWrite (word 1) true) tt
    empty inhabited_frame empty inhabited_frame.
Proof. Timeout 10 vm_compute. discriminate. Qed.
Example changed_neighbor_refused :
  T.tag_get (T.tag_put (T.tag_put (empty : T.tagmap) (word 8) true) (word 1) false) (word 8) = true.
Proof. Timeout 10 vm_compute. reflexivity. Qed.
Example aligned_capability :
  trace (inl None) true 10 (__WriteRAM_Meta (word 8) 8 true) empty = Some [WTag 1 true].
Proof. Timeout 10 vm_compute. reflexivity. Qed.
Example partial_granule :
  trace (inl None) true 10 (__WriteRAM_Meta (word 7) 2 false) empty = Some [WTag 0 false; WTag 1 false].
Proof. Timeout 10 vm_compute. reflexivity. Qed.
Example multiple_granules :
  trace (inl None) true 10 (__WriteRAM_Meta (word 7) 18 false) empty =
  Some [WTag 0 false; WTag 1 false; WTag 2 false; WTag 3 false].
Proof. Timeout 10 vm_compute. reflexivity. Qed.
Example fixed_width_wraparound :
  trace (inl None) true 10 (__WriteRAM_Meta (word 18446744073709551615) 2 false) empty = Some [].
Proof. reflexivity. Qed.
Example actual_write_ok_variants :
  forall status, trace (inl status) true 10
    (write_ram Write_plain (Physaddr (word 7)) 2 (zeros 16) false) empty =
    Some [WData; WTag 0 false; WTag 1 false].
Proof. intros [b|]; [destruct b|]; vm_compute; reflexivity. Qed.
Example actual_write_refused :
  trace (inr tt) true 10
    (write_ram Write_plain (Physaddr (word 7)) 2 (zeros 16) false) empty = Some [WData].
Proof. Timeout 10 vm_compute. reflexivity. Qed.
Example actual_write_frames :
  final (inl (Some false)) true 10
    (write_ram Write_plain (Physaddr (word 8)) 8 (zeros 64) true) empty =
  Some (true, T.tag_put empty (word 1) true, inhabited_frame).
Proof. Timeout 10 vm_compute. reflexivity. Qed.
Example metadata_read_requested :
  trace (inl None) true 10 (read_ram Read_plain (Physaddr (word 8)) 8 true) empty =
  Some [RTag 1 false; RData].
Proof. Timeout 10 vm_compute. reflexivity. Qed.
Example metadata_read_unrequested :
  trace (inl None) true 10 (read_ram Read_plain (Physaddr (word 8)) 8 false) empty = Some [RData].
Proof. Timeout 10 vm_compute. reflexivity. Qed.
Example data_read_refusal_preserved :
  final (inl None) false 10 (read_ram Read_plain (Physaddr (word 8)) 8 true) empty = None /\
  final (inl None) false 10 (read_ram Read_plain (Physaddr (word 8)) 8 false) empty = None.
Proof. Timeout 10 vm_compute. split; reflexivity. Qed.
Example missing_or_extra_tag_refused :
  trace (inl None) true 10 (__WriteRAM_Meta (word 7) 2 false) empty <> Some [WTag 0 false] /\
  trace (inl None) true 10 (__WriteRAM_Meta (word 7) 2 false) empty <> Some [WTag 1 false; WTag 0 false] /\
  trace (inl None) true 10 (__WriteRAM_Meta (word 7) 2 false) empty <> Some [WTag 0 false; WTag 1 false; WTag 2 false].
Proof. Timeout 10 vm_compute. repeat split; discriminate. Qed.

Fail Check (Defs.write_tag_bool (E := exception) (word 1) true : M bool).
Fail Check (I.TagWrite (word 1) true : I.outcome (fun _ => exception) bool).
Example early_return_carries_write :
  @Defs.catch_early_return bool exception
    (Defs.bind (@Defs.write_tag_bool (bool + exception)%type (word 1) true)
       (fun _ => @Defs.early_return bool bool exception true)) =
  I.Next (I.TagWrite (word 1) true) (fun _ => I.Ret true).
Proof. reflexivity. Qed.
Example real_exception_is_caught :
  @Defs.try_catch bool exception exception
    (Defs.throw (Error_not_implemented "example"%string)) (fun _ => Defs.returnm true) = I.Ret true.
Proof. reflexivity. Qed.
Example tag_is_not_an_exception :
  @Defs.try_catch unit exception exception (Defs.write_tag_bool (word 1) true)
    (fun _ => Defs.fail "must not catch tag"%string) =
  I.Next (I.TagWrite (word 1) true) I.Ret.
Proof. reflexivity. Qed.
Example dummy_data_event_refused :
  trace (inl None) true 10 (__WriteRAM_Meta (word 8) 8 true) empty <> Some [WData].
Proof. Timeout 10 vm_compute. discriminate. Qed.