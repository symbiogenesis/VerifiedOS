(* SPDX-License-Identifier: Apache-2.0 *)

(* =========================================================================
   Generated inputs for M4.4's kernel instance, as vectors.

   The consumers are two implementations this harness is not compiled
   against, which is what makes a line a differential rather than a
   self-check: the kernel C under kernel/ (host model), and the trace reader
   tools/vos/kernelrun.py that answers KernelInstance.v's three questions
   over a commit trace. Each line carries its inputs and the Gallina
   definitions' answers at them; a consumer recomputes the answers from the
   inputs alone and names the first column it disagrees on.

   Six families, each a walk over a declared domain:

     kx  the executive: CyclicExecutive.v's `slot_index_at` at every slot
         boundary and either side of it, `pairwise_disjoint`, `total_width`,
         and the in-frame conjunct of `slot_fits`, over generated frames.
     kc  the switch: PartitionContext.v's `canonical_post` at every
         component `Switch` pins, and the components `Rotation` pins, over
         every nameable and zeroized mask of a three-CSR roster, both of
         R-07-044's arms and both of R-07-037c's.
     kr  the revocation join: KernelInstance.v's `filtered`,
         `ImageIsSanitized` and `BurstCarriesNoStaleAuthority` over generated
         images and every bitmap over five bases.
     kq  completion: `SemanticCompletion` and the epoch reading it refuses,
         over all sixty-four completion records.
     ke  the extents: `extent_eqb`, `separated`, `compatible` and `within`
         over every ordered pair of a pool of extents, and
         `ExtentsAreReadable` over every assignment of that pool to the
         tenants of two frame shapes.
     kt  the trace reader: `WellFormedAttempts`, `AttemptsCover`,
         `RootIsThePartitions`, the three halves of `SwitchIsTotal`,
         `BurstWritesExactlyOnce`, the four clauses of `FrameIsTheTables` and
         `RunAnswersM44`, over traces built by operators from a correct run.
         The records are rendered in the normalized commit-trace grammar of
         differential-corpus.md section 4, so the reader parses a vector
         with the parser it reads an emulator's trace with.

   **The refuting constructions are generated, not listed.** PartitionContext.v
   names three: a restore truncated to the low registers, one dropping a
   validity tag, and one exempting a nameable CSR. Here each is an operator
   applied to the correct burst at several positions, beside the others the
   clause refuses, so a reader that accepts one is a named line.

   **Nothing here is a claim about a composition.** Every machine, frame,
   extent and image below is a probe: arbitrary witness values chosen so that
   each column can decide, in Probe.v's discipline. Numbers are small because
   `nat` is unary.

   **What a green run of a consumer means.** That the consumer computes what
   these definitions compute at every point of these domains. It is weaker
   than a proof, and it is not target evidence: no line here was produced by
   a compiled kernel on the emulator.

   An entry point in gallina.py's sense: it ends in a `Compute`, so it is
   compiled only by the run that reads it, never as another harness's
   support.
   ========================================================================= *)

From Stdlib Require Import String List Ascii.
Require Import PartitionContext.
Require Import BoundaryCost.
Require Import CyclicExecutive.
Require Import KernelInstance.
Require Import Probe.

Import ListNotations.
Open Scope string_scope.

Set Printing Width 100000.

(* -------------------------------------------------------------------------
   Rendering. The decimal renderer is Vectors.v's, restated because that
   harness is an entry point and cannot be Required without running it.
   ------------------------------------------------------------------------- *)

Definition kv_digit (n : nat) : ascii := ascii_of_nat (48 + n).

Fixpoint kv_nat (fuel n : nat) : string :=
  match fuel with
  | 0 => "?"
  | S f =>
      if Nat.ltb n 10
      then String (kv_digit n) EmptyString
      else append (kv_nat f (Nat.div n 10))
                  (String (kv_digit (Nat.modulo n 10)) EmptyString)
  end.

Definition ns (n : nat) : string := kv_nat 20 n.

Definition bs (b : bool) : string := if b then "1" else "0".

Definition os (o : option nat) : string :=
  match o with None => "n" | Some n => ns n end.

Definition hex_digit (n : nat) : ascii :=
  if Nat.ltb n 10 then ascii_of_nat (48 + n) else ascii_of_nat (55 + n).

(* Exactly `width` uppercase hexadecimal digits, most significant first. *)
Fixpoint hex_fixed (width n : nat) : string :=
  match width with
  | 0 => EmptyString
  | S w => append (hex_fixed w (Nat.div n 16))
                  (String (hex_digit (Nat.modulo n 16)) EmptyString)
  end.

Fixpoint join (sep : string) (l : list string) : string :=
  match l with
  | nil => EmptyString
  | cons x nil => x
  | cons x r => x ++ sep ++ join sep r
  end.

Definition words (l : list string) : string := join " " l.

(* =========================================================================
   kx: the executive.
   ========================================================================= *)

Definition kx_slot (wo : nat * nat) : Slot bool :=
  Build_Slot bool (fst wo) (snd wo) 0 100 true.

(* Width and offset pairs. Each list carries a slot that fits, one that
   overlaps a neighbour, one that ends past a 100-long frame, a zero-width
   slot, and one placed before its predecessor in time, so that list order
   and time order part. *)
Definition kx_reserved : list (nat * nat) :=
  [ (60, 0); (40, 0); (60, 10); (0, 0); (200, 0); (50, 120) ].

Definition kx_focus : list (nat * nat) :=
  [ (90, 60); (70, 60); (90, 55); (30, 60); (60, 140); (10, 0) ].

Definition kx_background : list (nat * nat) :=
  [ (50, 150); (35, 130); (50, 140); (10, 190); (20, 40); (60, 150) ].

Definition kx_majors : list nat := [100; 200].

(* Every slot boundary and one instant either side of it, plus both ends of
   the frame. Duplicates are kept rather than removed; they cost a column. *)
Definition kx_probes (mf : nat) (l : list (Slot bool)) : list nat :=
  List.app [0]
    (List.app
       (flat_map (fun s => [slot_offset s - 1; slot_offset s;
                            slot_offset s + slot_width s - 1;
                            slot_offset s + slot_width s]) l)
       [mf - 1; mf]).

Definition kx_pair (wo : nat * nat) : string := ns (fst wo) ++ " " ++ ns (snd wo).

Definition kx_line (mf : nat) (r f b : nat * nat) : string :=
  let fr := probe_frame mf (kx_slot r) (kx_slot f) (kx_slot b) in
  let sl := frame_slots fr in
  "kx " ++ ns mf ++ " " ++ kx_pair r ++ " " ++ kx_pair f ++ " " ++ kx_pair b ++ " ->"
    ++ " " ++ bs (pairwise_disjoint sl)
    (* the in-frame conjunct of `slot_fits`, one per slot in list order *)
    ++ " " ++ words (map (fun s => bs (Nat.leb (slot_offset s + slot_width s)
                                               (major_frame fr))) sl)
    ++ " " ++ ns (total_width sl)
    ++ " | " ++ words (map (fun t => ns t ++ ":" ++ os (slot_index_at sl 0 t))
                           (kx_probes mf sl)).

Definition kx_report : list string :=
  flat_map (fun mf =>
    flat_map (fun r =>
      flat_map (fun f => map (fun b => kx_line mf r f b) kx_background)
               kx_focus)
             kx_reserved)
           kx_majors.

(* =========================================================================
   kc: the switch and the rotation.
   ========================================================================= *)

(* The static arm's partition of the pending file, a composition constant
   R-07-044 does not further constrain; printed on every line so a consumer
   reads it rather than assuming it. *)
Definition kc_static_mask : nat := 5.

Definition kc_roster : list nat := [0; 1; 2].

Definition kc_machine (n z : nat) (sw rot : bool) : Machine := {|
  Csr := nat;
  csr_nameable := fun c => Nat.testbit n c;
  csr_zeroized := fun c => Nat.testbit z c;
  Word := nat;
  zero_word := 0;
  Pending := nat;
  pending_swapped := sw;
  pending_partition := fun p => Nat.land p kc_static_mask;
  rotation_swaps_pending := rot;
  fence_t_cost := 7;
  vmclear_cost := 5;
  opp_relock_cost := 3;
  drain_cost := 2
|}.

(* The successor and the predecessor differ at every component, so a
   consumer that reads the predecessor where the relation pins the successor
   is a column that differs. *)
Definition kc_succ (n z : nat) (sw rot : bool) (k : nat) : Context (kc_machine n z sw rot) :=
  Build_Context (kc_machine n z sw rot)
    (fun r => (r * 3 + k, Nat.odd (r + k)))
    (fun c => 10 + c + k)
    k.

Definition kc_pre (n z : nat) (sw rot : bool) (k : nat) : Context (kc_machine n z sw rot) :=
  Build_Context (kc_machine n z sw rot)
    (fun r => (200 + r, Nat.even (r + k)))
    (fun c => 90 + c)
    (k + 1).

Definition kc_reg (p : nat * bool) : string := ns (fst p) ++ "/" ++ bs (snd p).

Definition kc_line (n z : nat) (sw rot : bool) (k : nat) : string :=
  let m := kc_machine n z sw rot in
  let succ := kc_succ n z sw rot k in
  let pre := kc_pre n z sw rot k in
  let post := canonical_post m succ in
  "kc " ++ ns n ++ " " ++ ns z ++ " " ++ bs sw ++ " " ++ bs rot ++ " "
    ++ ns kc_static_mask ++ " " ++ ns (length kc_roster) ++ " " ++ ns (ctx_pending succ)
    ++ " " ++ ns (ctx_pending pre)
    ++ " succ " ++ words (map (fun r => kc_reg (ctx_reg succ r)) (seq 0 register_count))
    ++ " csr " ++ words (map (fun c => ns (ctx_csr succ c)) kc_roster)
    ++ " pre " ++ words (map (fun r => kc_reg (ctx_reg pre r)) (seq 0 register_count))
    ++ " csr " ++ words (map (fun c => ns (ctx_csr pre c)) kc_roster)
    ++ " ->"
    (* `Switch` pins every register, every nameable CSR and the pending
       component; what it does not pin is printed as `-`. *)
    ++ " S " ++ words (map (fun r => kc_reg (ctx_reg post r)) (seq 0 register_count))
    ++ " | " ++ words (map (fun c => if csr_nameable m c then ns (ctx_csr post c) else "-")
                           kc_roster)
    ++ " | " ++ ns (ctx_pending post)
    (* `Rotation` pins the registers (the same values), the restorable
       class, and the pending component on R-07-037c's arm only. *)
    ++ " R " ++ words (map (fun c => if andb (csr_nameable m c) (negb (csr_zeroized m c))
                                     then ns (ctx_csr succ c) else "-") kc_roster)
    ++ " | " ++ (if rotation_swaps_pending m then ns (pending_written m succ) else "-").

Definition kc_report : list string :=
  flat_map (fun n =>
    flat_map (fun z =>
      flat_map (fun sw =>
        flat_map (fun rot => map (fun k => kc_line n z sw rot k) [1; 6])
                 [false; true])
               [false; true])
             (seq 0 8))
           (seq 0 8).

(* =========================================================================
   The probe kernel the last three families read against. Its CSR roster
   carries one CSR the partition cannot name, so a write to it is a column.
   ========================================================================= *)

Definition kt_machine : Machine := {|
  Csr := nat;
  csr_nameable := fun c => Nat.ltb c 3;
  csr_zeroized := fun c => Nat.eqb c 1;
  Word := nat;
  zero_word := 0;
  Pending := nat;
  pending_swapped := true;
  pending_partition := fun p => p;
  rotation_swaps_pending := true;
  fence_t_cost := 7;
  vmclear_cost := 5;
  opp_relock_cost := 3;
  drain_cost := 2
|}.

Definition kt_composition : Composition := {|
  machine := kt_machine;
  boundary_inputs := demo_boundary_inputs;
  Tenant := nat;
  harmonic := fun _ _ => true;
  focus_majority := fun w total => Nat.leb total (w + w);
  rung_of_count := fun n => n;
  top_rung_capacity := 2;
  table_load_cost := 4
|}.

Definition kt_roster : list nat := [0; 1; 2; 3].

Lemma kt_roster_covers :
  forall c : nat, Nat.ltb c 3 = true -> any_of (fun d => Nat.eqb c d) kt_roster = true.
Proof.
  intros c H. destruct c as [ | [ | [ | c ] ] ]; try reflexivity.
  simpl in H. discriminate H.
Qed.

Definition kt_switch : Extent := {| ext_base := 10; ext_top := 20 |}.

(* Tenants 0 to 3 declare separated texts. Tenant 4's text meets the switch
   text and tenant 5's partially overlaps tenant 0's, so a frame naming
   either is one `ExtentsAreReadable` refuses. *)
Definition kt_text (t : nat) : Extent :=
  match t with
  | 0 => {| ext_base := 30; ext_top := 40 |}
  | 1 => {| ext_base := 50; ext_top := 60 |}
  | 2 => {| ext_base := 70; ext_top := 80 |}
  | 3 => {| ext_base := 90; ext_top := 100 |}
  | 4 => {| ext_base := 5; ext_top := 15 |}
  | _ => {| ext_base := 35; ext_top := 45 |}
  end.

Definition kt_kernel_at (w : nat) (sw : Extent) (tx : nat -> Extent) : Kernel := {|
  composition := kt_composition;
  word_eqb := Nat.eqb;
  word_eqb_sound := nat_eqb_sound;
  word_eqb_holds := nat_eqb_holds;
  csr_eqb := Nat.eqb;
  csr_eqb_sound := nat_eqb_sound;
  csr_roster := kt_roster;
  csr_roster_covers := kt_roster_covers;
  Scr := nat;
  Base := nat;
  base_of := fun v => v;
  switch_text := sw;
  text_of := tx;
  window_count := w
|}.

Definition kt_kernel (w : nat) : Kernel := kt_kernel_at w kt_switch kt_text.

Definition kt_astray : nat := 200.

(* Records in the normalized commit-trace grammar: `I pc insn` with the
   order dropped, `X reg tag value`, `S scr tag value`, `C csr value`. *)
Definition rec_str (r : TraceRecord nat nat nat) : string :=
  match r with
  | RecI _ p i => "I " ++ hex_fixed 16 p ++ " " ++ hex_fixed 8 i
  | RecX g t v => "X " ++ ns g ++ " " ++ bs t ++ " " ++ hex_fixed 16 v
  | RecS s t v => "S " ++ ns s ++ " " ++ bs t ++ " " ++ hex_fixed 16 v
  | RecC c v => "C " ++ hex_fixed 3 c ++ " " ++ hex_fixed 16 v
  | RecR a w t v => "R " ++ hex_fixed 16 a ++ " " ++ ns w ++ " " ++ bs t ++ " " ++ hex_fixed 16 v
  | RecW a w t v => "W " ++ hex_fixed 16 a ++ " " ++ ns w ++ " " ++ bs t ++ " " ++ hex_fixed 16 v
  | RecT i c => "T " ++ bs i ++ " " ++ ns c
  end.

Definition trace_str (l : list (TraceRecord nat nat nat)) : string :=
  match l with nil => "-" | _ => join ";" (map rec_str l) end.

Definition kt_i (p : nat) : TraceRecord nat nat nat := RecI 0 p 0.

(* =========================================================================
   kr: the revocation join over the probe kernel.
   ========================================================================= *)

(* Six image patterns over five bases. A value is its own base in the probe
   (`base_of` is the identity), and every value is below five, so every
   bitmap over five bases reaches every register. The first four tag about a
   third of the file; the last two tag one register alone, the first and the
   last of the witnessed range, because a check that skipped an end of the
   range agreed with every line of the first four (the mutation run over the
   kernel C found it). *)
Definition kr_image (i : nat) : Context (kmachine (kt_kernel 2)) :=
  Build_Context (kmachine (kt_kernel 2))
    (fun r => (Nat.modulo (r + i) 5,
               match i with
               | 4 => Nat.eqb r 1
               | 5 => Nat.eqb r 31
               | _ => Nat.eqb (Nat.modulo (r * (i + 1)) 3) 0
               end))
    (fun _ => 0)
    0.

Definition kr_line (i mask : nat) : string :=
  let k := kt_kernel 2 in
  let succ := kr_image i in
  let bm := fun b : nat => Nat.testbit mask b in
  "kr " ++ ns mask ++ " "
    ++ words (map (fun r => kc_reg (ctx_reg succ r)) observed_registers)
    ++ " ->"
    ++ " " ++ bs (ImageIsSanitized k bm succ)
    ++ " " ++ bs (BurstCarriesNoStaleAuthority k bm (image_burst k succ))
    ++ " " ++ bs (BurstCarriesNoStaleAuthority k bm (filtered_burst k bm succ))
    ++ " | " ++ words (map (fun r => bs (filtered k bm (snd (ctx_reg succ r))
                                                     (fst (ctx_reg succ r))))
                           observed_registers).

Definition kr_report : list string :=
  flat_map (fun i => map (kr_line i) (seq 0 32)) (seq 0 6).

(* =========================================================================
   kq: completion.
   ========================================================================= *)

Definition kq_record (n : nat) : Completion := {|
  bits_published := Nat.testbit n 0;
  epoch_advanced := Nat.testbit n 1;
  resident_roots_cleared := Nat.testbit n 2;
  saved_contexts_filtered := Nat.testbit n 3;
  loans_cancelled := Nat.testbit n 4;
  device_boundary_reached := Nat.testbit n 5
|}.

Definition kq_line (n : nat) : string :=
  let c := kq_record n in
  "kq " ++ words (map bs [bits_published c; epoch_advanced c; resident_roots_cleared c;
                         saved_contexts_filtered c; loans_cancelled c;
                         device_boundary_reached c])
    ++ " -> " ++ bs (SemanticCompletion c) ++ " " ++ bs (epoch_completion c).

Definition kq_report : list string := map kq_line (seq 0 64).

(* =========================================================================
   kt: the trace reader. Declarations first, so a reader builds its frame,
   roster and successor images from lines rather than from a transcription.
   ========================================================================= *)

Definition kt_slot (w o t : nat) : Slot nat := Build_Slot nat w o 0 100 t.

(* Five frames: the probe shape; one whose tenant holds a reserved slot and
   a background slot, so a reserved extent recurs in the table; one with two
   reserved slots, so the reserved band has an order of its own; and two
   whose declared extents are unreadable, one tenant's text meeting the
   switch text and one partially overlapping another tenant's, so the
   readability column is decided both ways. *)
Definition kt_frames : list (Frame nat) :=
  [ Build_Frame nat 200 0 [kt_slot 60 0 0]
      (Build_Band nat (kt_slot 90 60 1) [kt_slot 50 150 2])
  ; Build_Frame nat 200 0 [kt_slot 60 0 0]
      (Build_Band nat (kt_slot 90 60 1) [kt_slot 50 150 0])
  ; Build_Frame nat 200 0 [kt_slot 40 0 0; kt_slot 20 40 3]
      (Build_Band nat (kt_slot 90 60 1) [kt_slot 50 150 2])
  ; Build_Frame nat 200 0 [kt_slot 60 0 0]
      (Build_Band nat (kt_slot 90 60 4) [kt_slot 50 150 2])
  ; Build_Frame nat 200 0 [kt_slot 60 0 0]
      (Build_Band nat (kt_slot 90 60 5) [kt_slot 50 150 2]) ].

Definition ext_str (e : Extent) : string := ns (ext_base e) ++ ":" ++ ns (ext_top e).

Definition kt_decl_frame (fid : nat) (f : Frame nat) : string :=
  "kt d " ++ ns fid ++ " " ++ ns (length (reserved_band f)) ++ " "
    ++ ext_str kt_switch ++ " "
    ++ words (map (fun s => ns (slot_tenant s) ++ ":" ++ ext_str (kt_text (slot_tenant s)))
                  (frame_slots f)).

Definition kt_decl_roster : string :=
  "kt r " ++ words (map (fun c => ns c ++ ":" ++ bs (csr_nameable kt_machine c) ++ ":"
                                  ++ bs (csr_zeroized kt_machine c)) kt_roster).

Definition kt_succ (k : nat) : Context (kmachine (kt_kernel 2)) :=
  Build_Context (kmachine (kt_kernel 2))
    (fun r => (r * 3 + k, Nat.odd (r + k)))
    (fun c => 10 + c + k)
    0.

Definition kt_decl_succ (k : nat) : string :=
  let succ := kt_succ k in
  "kt s " ++ ns k ++ " " ++ words (map (fun r => kc_reg (ctx_reg succ r)) (seq 0 register_count))
    ++ " | " ++ words (map (fun c => ns (ctx_csr succ c)) kt_roster).

(* --- confinement ---------------------------------------------------------- *)

Definition kt_target (i : nat) : Target :=
  match i with 0 => RootTop | S j => WindowTop j end.

Definition kt_attempt (i : nat) : Attempt :=
  {| att_pc := 110 + 4 * i; att_result_register := 8 + i; att_target := kt_target i |}.

Definition kt_attempts (w : nat) : list Attempt := map kt_attempt (seq 0 (S w)).

Definition target_str (t : Target) : string :=
  match t with RootTop => "R" | WindowTop j => "W" ++ ns j end.

Definition att_str (a : Attempt) : string :=
  ns (att_pc a) ++ ":" ++ ns (att_result_register a) ++ ":" ++ target_str (att_target a).

Definition atts_str (l : list Attempt) : string :=
  match l with nil => "-" | _ => join "," (map att_str l) end.

Fixpoint drop_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | _, nil => nil
  | 0, cons _ r => r
  | S m, cons x r => cons x (drop_at m r)
  end.

Fixpoint set_at {A : Type} (n : nat) (v : A) (l : list A) : list A :=
  match n, l with
  | _, nil => nil
  | 0, cons _ r => cons v r
  | S m, cons x r => cons x (set_at m v r)
  end.

(* The declared attempt lists: the full one, each single deletion, and three
   ill-formed ones (a repeated site, the zero register, a register past the
   file). *)
Definition kt_attempt_variants (w : nat) : list (list Attempt) :=
  let full := kt_attempts w in
  List.app [full]
    (List.app (map (fun j => drop_at j full) (seq 0 (S w)))
      [ set_at 1 {| att_pc := 110; att_result_register := 9; att_target := kt_target 1 |} full
      ; set_at 0 {| att_pc := 110; att_result_register := 0; att_target := RootTop |} full
      ; set_at 0 {| att_pc := 110; att_result_register := 32; att_target := RootTop |} full ]).

(* One run over the full attempt list, each result tagged by one bit of
   `mask`: a set bit is a derivation that kept its tag. *)
Definition kt_confinement (w mask : nat) : list (TraceRecord nat nat nat) :=
  flat_map (fun i => [kt_i (110 + 4 * i); RecX (8 + i) (Nat.testbit mask i) 7])
           (seq 0 (S w)).

(* The trace operators: the attempt's write missing, redirected to an
   unrelated register, or arriving after the next instruction. *)
Definition kt_confinement_variants (w : nat) : list (list (TraceRecord nat nat nat)) :=
  List.app (map (kt_confinement w) (seq 0 (Nat.pow 2 (S w))))
    [ drop_at 1 (kt_confinement w 0)
    ; set_at 1 (RecX 20 false 7) (kt_confinement w 0)
    ; List.app [kt_i 110; kt_i 114; RecX 8 false 7] (drop_at 0 (drop_at 0 (kt_confinement w 0))) ].

Definition kt_c_line (w : nat) (l : list Attempt) (tr : list (TraceRecord nat nat nat)) : string :=
  let k := kt_kernel w in
  "kt c " ++ ns w ++ " " ++ atts_str l ++ " " ++ trace_str tr ++ " ->"
    ++ " " ++ bs (WellFormedAttempts l)
    ++ " " ++ bs (AttemptsCover k l)
    ++ " " ++ bs (RootIsThePartitions k l tr).

Definition kt_c_report : list string :=
  flat_map (fun w =>
    flat_map (fun l => map (kt_c_line w l) (kt_confinement_variants w))
             (kt_attempt_variants w))
           [0; 1; 2].

(* --- the restore burst ---------------------------------------------------- *)

Definition kt_burst_full (k : nat) : list (TraceRecord nat nat nat) :=
  full_burst (kt_kernel 2) (kt_succ k).

Definition kt_image (k : nat) : list (TraceRecord nat nat nat) :=
  image_burst (kt_kernel 2) (kt_succ k).

Definition kt_csrs (k : nat) : list (TraceRecord nat nat nat) :=
  csr_burst (kt_kernel 2) (kt_succ k).

Definition kt_regwrite (k r : nat) (flip_tag : bool) (delta : nat) : TraceRecord nat nat nat :=
  let p := ctx_reg (kt_succ k) r in
  RecX r (xorb flip_tag (snd p)) (fst p + delta).

Fixpoint firstn_of {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, _ => nil
  | _, nil => nil
  | S m, cons x r => cons x (firstn_of m r)
  end.

(* The operators over the correct burst. The first three families are
   PartitionContext.v's own refuting constructions: truncation to the low
   registers, a dropped validity tag, an exempted nameable CSR. *)
Definition kt_burst_variants (k : nat) : list (list (TraceRecord nat nat nat)) :=
  let image := kt_image k in
  let csrs := kt_csrs k in
  List.app [kt_burst_full k]
  (List.app (map (fun n => List.app (firstn_of n image) csrs) [1; 15; 30])
  (List.app (map (fun r => List.app (set_at (r - 1) (kt_regwrite k r true 0) image) csrs)
                 [1; 16; 31])
  (List.app (map (fun c => List.app image (drop_at c csrs)) [0; 1; 2])
  (List.app
    [ List.app (set_at 4 (kt_regwrite k 5 false 1) image) csrs
    ; List.app image (set_at 1 (RecC 1 (11 + k)) csrs)
    ; List.app (kt_burst_full k) [RecX 40 true 7]
    ; List.app (kt_burst_full k) [RecX 0 false 0]
    ; List.app (kt_burst_full k) [RecC 3 0]
    ; List.app (kt_burst_full k) [kt_regwrite k 5 false 0]
    ; List.app (kt_burst_full k) [RecC 0 (10 + k)]
    ; List.app [kt_regwrite k 5 false 1] (kt_burst_full k)
    ; List.app (kt_burst_full k) [RecS 31 true 7]
    ; List.app csrs image
    ; List.app (kt_burst_full k) [kt_i 12; RecX 5 false 0] ]
    nil)))).

Definition kt_b_line (k : nat) (b : list (TraceRecord nat nat nat)) : string :=
  let kk := kt_kernel 2 in
  let succ := kt_succ k in
  "kt b " ++ ns k ++ " " ++ trace_str b ++ " ->"
    ++ " " ++ bs (SwitchIsTotal kk succ b)
    ++ " " ++ bs (RegisterBurstTotal kk succ b)
    ++ " " ++ bs (CsrBurstTotal kk succ b)
    ++ " " ++ bs (BurstCarriesNothingElse kk b)
    ++ " " ++ bs (BurstWritesExactlyOnce kk b).

Definition kt_b_report : list string :=
  flat_map (fun k => map (kt_b_line k) (kt_burst_variants k)) [1; 2].

(* --- the frame ------------------------------------------------------------- *)

Fixpoint insert_all (x : nat) (l : list nat) : list (list nat) :=
  match l with
  | nil => [[x]]
  | cons y r => cons (cons x l) (map (cons y) (insert_all x r))
  end.

Fixpoint perms (l : list nat) : list (list nat) :=
  match l with
  | nil => [nil]
  | cons x r => flat_map (insert_all x) (perms r)
  end.

Definition kt_tenants (f : Frame nat) : list nat := map slot_tenant (frame_slots f).

(* One visit per tenant in the order given: a switch retire, then `dwell`
   retires inside the tenant's text. *)
Definition kt_visits (ts : list nat) (dwell : nat) : list nat :=
  flat_map (fun it =>
    cons (ext_base kt_switch + fst it)
      (map (fun j => ext_base (kt_text (snd it)) + j) (seq 0 dwell)))
    (combine (seq 0 (length ts)) ts).

Definition kt_pcs (l : list nat) : list (TraceRecord nat nat nat) := map kt_i l.

Definition kt_frame_variants (f : Frame nat) : list (list (TraceRecord nat nat nat)) :=
  let ts := kt_tenants f in
  let canonical := kt_visits ts 1 in
  List.app (map (fun p => kt_pcs (kt_visits p 1)) (perms ts))
    [ kt_pcs (kt_visits ts 3)
    ; kt_pcs (kt_visits (removelast ts) 1)
    ; kt_pcs (kt_visits (List.app ts (firstn_of 1 ts)) 1)
    ; kt_pcs (kt_visits (List.app (firstn_of 2 ts) (skipn 1 ts)) 1)
    ; kt_pcs (List.app canonical [kt_astray])
    ; kt_pcs (tl canonical)
    ; kt_pcs (List.app canonical [ext_base kt_switch])
    ; flat_map (fun p => [kt_i p; RecX 5 true p; RecC 0 p]) canonical ].

Definition kt_f_line (fid : nat) (f : Frame nat) (tr : list (TraceRecord nat nat nat)) : string :=
  let k := kt_kernel 2 in
  "kt f " ++ ns fid ++ " " ++ trace_str tr ++ " ->"
    ++ " " ++ bs (ExtentsAreReadable k f)
    ++ " " ++ bs (ReservedEnteredOnce k f tr)
    ++ " " ++ bs (SwitchesInTableOrder k f tr)
    ++ " " ++ bs (NoUnnamedSwitch k f tr)
    ++ " " ++ bs (FrameIsTheTables k f tr).

Definition kt_f_report : list string :=
  flat_map (fun fi => map (kt_f_line (fst fi) (snd fi)) (kt_frame_variants (snd fi)))
           (combine (seq 0 (length kt_frames)) kt_frames).

(* =========================================================================
   ke: the extent predicates partition.c restates, and the readability side
   condition over a declared frame, for the kernel C rather than the reader.
   The pool holds an extent equal to the switch text, one meeting it, one
   touching it, two touching each other and two partially overlapping, so
   every predicate is decided both ways.
   ========================================================================= *)

Definition ke_ext (b t : nat) : Extent := {| ext_base := b; ext_top := t |}.

Definition ke_pool : list Extent :=
  [ ke_ext 30 40; ke_ext 35 45; ke_ext 40 50; ke_ext 5 15; ke_ext 20 30; ke_ext 10 20 ].

(* An extent's two ends and one address below each. *)
Definition ke_probes (e : Extent) : list nat :=
  [ext_base e - 1; ext_base e; ext_top e - 1; ext_top e].

Definition ke_p_line (a b : Extent) : string :=
  "ke p " ++ ext_str a ++ " " ++ ext_str b ++ " ->"
    ++ " " ++ bs (extent_eqb a b)
    ++ " " ++ bs (separated a b)
    ++ " " ++ bs (compatible a b)
    ++ " | " ++ words (map (fun p => ns p ++ ":" ++ bs (within a p)) (ke_probes a)).

Definition ke_text (e0 e1 e2 : Extent) (t : nat) : Extent :=
  match t with 0 => e0 | 1 => e1 | _ => e2 end.

(* Two frame shapes over tenants 0 to 2: three tenants, and tenant 0 holding
   both the reserved slot and a background slot, so one extent recurs and
   is compatible with itself only by being equal. *)
Definition ke_shapes : list (list nat) := [[0; 1; 2]; [0; 1; 0]].

Definition ke_frame (ts : list nat) : Frame nat :=
  Build_Frame nat 200 0 [kt_slot 60 0 (nth 0 ts 0)]
    (Build_Band nat (kt_slot 90 60 (nth 1 ts 0)) [kt_slot 50 150 (nth 2 ts 0)]).

Definition ke_r_line (e0 e1 e2 : Extent) (ts : list nat) : string :=
  let k := kt_kernel_at 2 kt_switch (ke_text e0 e1 e2) in
  "ke r " ++ ext_str kt_switch ++ " " ++ ext_str e0 ++ " " ++ ext_str e1 ++ " "
    ++ ext_str e2 ++ " t " ++ words (map ns ts) ++ " -> "
    ++ bs (ExtentsAreReadable k (ke_frame ts)).

Definition ke_report : list string :=
  List.app (flat_map (fun a => map (ke_p_line a) ke_pool) ke_pool)
    (flat_map (fun ts =>
       flat_map (fun e0 =>
         flat_map (fun e1 => map (fun e2 => ke_r_line e0 e1 e2 ts) ke_pool) ke_pool)
         ke_pool)
       ke_shapes).

(* --- the joined verdict --------------------------------------------------- *)

Definition kt_frame0 : Frame nat := nth 0 kt_frames (Build_Frame nat 0 0 nil
                                        (Build_Band nat (kt_slot 0 0 0) nil)).

Definition kt_run_line (l : list Attempt) (conf burst frame : list (TraceRecord nat nat nat))
  : string :=
  let k := kt_kernel 2 in
  "kt run 0 2 1 " ++ atts_str l ++ " " ++ trace_str conf ++ " | " ++ trace_str burst ++ " | "
    ++ trace_str frame ++ " -> "
    ++ bs (RunAnswersM44 k kt_frame0 l (kt_succ 1) conf burst frame).

Definition kt_run_report : list string :=
  flat_map (fun l =>
    flat_map (fun conf =>
      flat_map (fun burst =>
        map (fun frame => kt_run_line l conf burst frame)
            [ kt_pcs (kt_visits (kt_tenants kt_frame0) 1)
            ; kt_pcs (kt_visits (rev (kt_tenants kt_frame0)) 1) ])
        [ kt_burst_full 1
        ; List.app (set_at 0 (kt_regwrite 1 1 true 0) (kt_image 1)) (kt_csrs 1) ])
      [ kt_confinement 2 0; kt_confinement 2 2 ])
    [ kt_attempts 2
    ; set_at 1 {| att_pc := 110; att_result_register := 9; att_target := kt_target 1 |}
        (kt_attempts 2) ].

Definition kt_report : list string :=
  List.app (map (fun fi => kt_decl_frame (fst fi) (snd fi))
                (combine (seq 0 (length kt_frames)) kt_frames))
  (List.app [kt_decl_roster; kt_decl_succ 1; kt_decl_succ 2]
  (List.app kt_c_report
  (List.app kt_b_report
  (List.app kt_f_report kt_run_report)))).

(* =========================================================================
   The walk.
   ========================================================================= *)

Definition kernel_report : list string :=
  List.app kx_report
  (List.app kc_report
  (List.app kr_report
  (List.app kq_report
  (List.app ke_report kt_report)))).

Compute kernel_report.
