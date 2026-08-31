(* SPDX-License-Identifier: Apache-2.0 *)

(* =========================================================================
   The Gallina front's generated inputs, as vectors.

   The Wasm oracle (tools/wasm-oracle/, M1.5) runs Gallina components on a
   stock engine and nothing generates their inputs, so what it exercises is
   whatever a person thought to write down. This file is the input side, in
   the shape both earlier model-as-oracle rigs took: a domain is walked, the
   definitions under test are called at every point of it, and one line of
   text per point is printed. The vectors cross as text, so the Wasm side and
   this side are not compiled against each other's types and a disagreement
   names a line a person reads on both sides.

   It has two subjects and they are walked in two blocks. The first is
   CyclicExecutive.v's admission algebra, which is the whole of what
   R-11-006's interval arithmetic and R-11-009's switch duty decide about a
   frame. The second is EndpointIPC.v's capability lifecycle, endpoint
   transfer and message medium, which is what R-07-027a, R-07-029a, R-07-031
   and R-07-031b decide about an invocation. Every definition either block
   calls is decidable and computes, which is what makes a vector out of a
   proof artifact at all.

   **Why the second block exists, measured rather than asserted.** Before it,
   a seeded population over `proofs/EndpointIPC.v` was 249 mutants of which
   249 were killed by the prover and 0 moved a vector: the file's own
   conversions decided every site and this harness decided none, which is the
   finding M6.1a recorded of its own artifact a lane over. Widening the input
   side is what that finding asks for, and the block below is the widening.

   **The names of the second subject are qualified and its module is not
   imported.** Five of its names are already taken by the two modules
   imported unqualified above: CyclicExecutive.v defines `all_of`, `count_of`
   and an `Outcome`, and PartitionContext.v defines a `Machine` and a `demo`.
   An unqualified import of the second subject would silently shadow one or
   the other in the block above it. So every symbol of the IPC subject is
   spelled `EndpointIPC.x` below. That is verbose on purpose: a reader of a
   column can see which artifact it reads without leaving the line.

   Two things it is deliberately not. It is not a proof: nothing here is
   Required by anything in proofs/, and the proof gate never compiles it, so
   no constant here reaches R-05-163's assumption enumeration. And it is not
   the QuickChick harness: Properties.v beside this file is that, and it needs
   an install this repository has not made. What this supplies without that
   install is the enumerative half, and what the install adds is random
   generation and counterexample shrinking.

   It is compiled by tools/quickchick.py in the CertiRocq oracle's own switch,
   which is where the standard library is; the shipped proofs use the prelude
   alone and are compiled in the proof gate's switch, which carries no library
   at all.
   ========================================================================= *)

From Stdlib Require Import String List Ascii.
Require Import PartitionContext.
Require Import CyclicExecutive.
Require Import Probe.
Require EndpointIPC.
Require Import IPCProbe.

Import ListNotations.
Open Scope string_scope.

(* The printed list is one logical line and the reader of it is a text
   comparison, so it must not be wrapped at a terminal width. *)
Set Printing Width 100000.

(* -------------------------------------------------------------------------
   Rendering. A vector is text, so a nat has to become digits; the fuel is
   what makes the recursion structural, twenty digits being past any nat this
   file computes.
   ------------------------------------------------------------------------- *)

Definition digit_char (n : nat) : ascii := ascii_of_nat (48 + n).

Fixpoint nat_str (fuel n : nat) : string :=
  match fuel with
  | 0 => "?"
  | S f =>
      if Nat.ltb n 10
      then String (digit_char n) EmptyString
      else append (nat_str f (Nat.div n 10))
                  (String (digit_char (Nat.modulo n 10)) EmptyString)
  end.

Definition ns (n : nat) : string := nat_str 20 n.

Definition bs (b : bool) : string := if b then "1" else "0".

(* `slot_index_at` answers which slot owns an instant, and `None` where none
   does: R-07-036's non-work-conserving frame is exactly the instants that
   answer nothing, so the absence is a value the vector carries rather than a
   case it skips. *)
Definition os (o : option nat) : string :=
  match o with
  | None => "n"
  | Some n => ns n
  end.

(* -------------------------------------------------------------------------
   The domain. Four declared quantities per slot, three slots per frame, and
   two major-frame lengths: the grids below are named rather than drawn,
   because a slot's interesting values are its own boundaries and R1a's
   measurement is that a population off entropy alone misses exactly those.
   Each grid carries the value that fits, the value one unit past it, an
   overlap, a period that divides the major frame and one that does not.
   ------------------------------------------------------------------------- *)

Definition quad : Type := (nat * nat * nat * nat)%type.

Definition slot_of (q : quad) : Slot bool :=
  match q with
  | (w, o, b, p) => Build_Slot bool w o b p true
  end.

Definition q4 (q : quad) : string :=
  match q with
  | (w, o, b, p) => ns w ++ " " ++ ns o ++ " " ++ ns b ++ " " ++ ns p
  end.

Definition majors : list nat := [100; 200].

Definition reserved_grid : list quad :=
  [ (60, 0, 40, 100)
  ; (60, 0, 45, 100)
  ; (60, 0, 46, 100)
  ; (40, 0, 20, 50)
  ; (60, 10, 40, 100)
  ; (0, 0, 0, 100)
  ; (200, 0, 180, 200)
  ; (60, 0, 40, 7)
  ].

Definition focus_grid : list quad :=
  [ (90, 60, 70, 100)
  ; (90, 60, 75, 100)
  ; (90, 60, 76, 100)
  ; (70, 60, 50, 100)
  ; (90, 55, 70, 100)
  ; (140, 60, 120, 200)
  ; (90, 60, 70, 3)
  ; (30, 60, 10, 100)
  ].

(* The last row is here because a mutant survived without it, which is the
   measurement R1a made about its own sweep and this is the same one a lane
   over: `disjoint` is a disjunction of two `Nat.leb`s and every other row puts
   the background *after* the focus, so only the first disjunct was ever
   decided at equality and turning the second one strict changed no vector.
   This row ends exactly where a 60-offset focus begins and clears the
   40-wide reserved slot, which is what makes the second disjunct decide. *)
Definition background_grid : list quad :=
  [ (50, 150, 30, 100)
  ; (50, 140, 30, 100)
  ; (35, 130, 15, 100)
  ; (35, 165, 15, 100)
  ; (50, 150, 40, 100)
  ; (60, 150, 45, 50)
  ; (10, 190, 0, 100)
  ; (50, 150, 30, 9)
  ; (15, 45, 0, 100)
  ].

Definition frame_of (mf : nat) (r f b : quad) : Frame bool :=
  probe_frame mf (slot_of r) (slot_of f) (slot_of b).

(* -------------------------------------------------------------------------
   One vector. Every clause of the admission verdict is printed beside the
   verdict itself, so a defect in one conjunct is a line that differs in the
   field naming that conjunct rather than only in the answer.
   ------------------------------------------------------------------------- *)

Definition line_of (mf : nat) (r f b : quad) : string :=
  let fr := frame_of mf r f b in
  "ce " ++ ns mf ++ " " ++ q4 r ++ " " ++ q4 f ++ " " ++ q4 b ++ " ->"
    ++ " " ++ bs (admits probe_composition fr)
    ++ " " ++ bs (reserved_half probe_composition fr)
    ++ " " ++ bs (all_of (slot_fits probe_composition (major_frame fr))
                         (frame_slots fr))
    ++ " " ++ bs (pairwise_disjoint (frame_slots fr))
    ++ " " ++ ns (total_width (frame_slots fr))
    ++ " " ++ bs (FocusShaped probe_composition (discretionary_band fr))
    ++ " " ++ ns (count_of (frame_slots fr))
    ++ " " ++ ns (rung_change_cost probe_composition (discretionary_band fr))
    ++ " " ++ os (slot_index_at (frame_slots fr) 0 0)
    ++ " " ++ os (slot_index_at (frame_slots fr) 0 60)
    ++ " " ++ os (slot_index_at (frame_slots fr) 0 155)
    ++ " " ++ os (slot_index_at (frame_slots fr) 0 199).

Definition ce_report : list string :=
  flat_map (fun mf =>
    flat_map (fun r =>
      flat_map (fun f =>
        map (fun b => line_of mf r f b) background_grid)
        focus_grid)
      reserved_grid)
    majors.

(* =========================================================================
   The second subject: EndpointIPC.v's capability lifecycle, endpoint
   transfer and message medium (R-07-027a, R-07-029a, R-07-031, R-07-031b,
   R-07-037b through R-07-037d, R-04-008, R-08-032, R-12-096).

   Every family below is a walk over a domain the artifact itself does not
   walk, evaluated at IPCProbe.v's machine rather than at the artifact's own
   `demo`. Where a column would be constant over its family it is not a
   column: a clause no input can tell from its absence is the dead-arm shape
   Probe.v's header names, and a vector carrying one reports a clause held
   that nothing holds. The domains are sized off the machine's own fields and
   off the artifact's own lists wherever one exists, so a field that moves
   moves the domain with it rather than leaving a walk aimed at nothing.
   ========================================================================= *)

(* The endpoint set, and the number of readiness states over it. Both are read
   off the machine rather than written down, `two_pow` being the artifact's
   own count of the bit space a `Readiness` ranges over. *)
Definition ipc_endpoints : nat := EndpointIPC.endpoint_count ipc_machine.

Definition ipc_states : nat := EndpointIPC.two_pow ipc_endpoints.

(* -------------------------------------------------------------------------
   Family 1: the capability lifecycle, class by class and act by act
   (R-07-027a's second sentence, R-08-004d, R-11-024). The two obligations
   over a lifecycle map are twins that a single column could not tell apart,
   so the specification's map is printed beside the map that lets a table be
   revoked and the map that admits nothing at all. The revoke-only map is
   printed beside them because it discharges both obligations and disagrees
   with the specification's at cells neither obligation reads, which is
   EndpointIPC.v's gap j as a pair of columns rather than as a remark.
   ------------------------------------------------------------------------- *)

Definition lc_line (c : EndpointIPC.Nameable) (op : EndpointIPC.Lifecycle)
  : string :=
  "ipc lc " ++ ns (ipc_nm_ix c) ++ " " ++ ns (ipc_lc_ix op) ++ " ->"
    ++ " " ++ bs (EndpointIPC.is_object c)
    ++ " " ++ bs (EndpointIPC.is_table c)
    ++ " " ++ bs (EndpointIPC.spec_lifecycles c op)
    ++ " " ++ bs (EndpointIPC.revoke_only_lifecycle c op)
    ++ " " ++ bs (EndpointIPC.table_lifecycle c op)
    ++ " " ++ bs (EndpointIPC.frozen_lifecycle c op)
    ++ " " ++ ns (EndpointIPC.occurrences_nm c EndpointIPC.spec_inventory)
    ++ " " ++ bs (EndpointIPC.is_object
                    (EndpointIPC.spec_designation (ipc_nm_ix c)))
    ++ " " ++ bs (EndpointIPC.is_object
                    (EndpointIPC.table_designation (ipc_nm_ix c))).

(* -------------------------------------------------------------------------
   Family 2: the candidate inventories, with `inventory_ok`'s two conjuncts
   printed apart from the verdict (R-07-027a). A deletion breaks the
   occurrence conjunct and an inserted table breaks the object conjunct, so a
   run in which the verdict moved and neither conjunct did would be a run in
   which the two had become one.
   ------------------------------------------------------------------------- *)

Definition inv_line (n : nat) : string :=
  let l := nth n ipc_inventories (nil : list EndpointIPC.Nameable) in
  "ipc inv " ++ ns n ++ " ->"
    ++ " " ++ bs (EndpointIPC.inventory_ok l)
    ++ " " ++ bs (EndpointIPC.all_of EndpointIPC.is_object l)
    ++ " " ++ bs (EndpointIPC.all_of
                    (fun c => Nat.eqb (EndpointIPC.occurrences_nm c l) 1)
                    EndpointIPC.object_classes)
    ++ " " ++ ns (EndpointIPC.count_of l)
    ++ " " ++ ns (EndpointIPC.occurrences_nm EndpointIPC.NEndpoint l)
    ++ " " ++ ns (EndpointIPC.occurrences_nm EndpointIPC.NGrantTable l)
    ++ " " ++ ns (EndpointIPC.occurrences_nm EndpointIPC.NReplyObject l).

(* -------------------------------------------------------------------------
   Family 3: dispatch by the number and by nothing else (R-07-031b, R-07-030).
   The specification is read under two observations and the submission-queue
   construction under the same two, so the column that moves is the read of
   memory rather than a different table.
   ------------------------------------------------------------------------- *)

Definition dsp_line (n : nat) : string :=
  "ipc dsp " ++ ns n ++ " ->"
    ++ " " ++ ns (ipc_opt_inv_ix
                    (EndpointIPC.spec_dispatch EndpointIPC.quiet_memory n))
    ++ " " ++ ns (ipc_opt_inv_ix
                    (EndpointIPC.spec_dispatch EndpointIPC.loaded_memory n))
    ++ " " ++ ns (ipc_opt_inv_ix
                    (EndpointIPC.submission_queue_dispatch
                       EndpointIPC.quiet_memory n))
    ++ " " ++ ns (ipc_opt_inv_ix
                    (EndpointIPC.submission_queue_dispatch
                       EndpointIPC.loaded_memory n))
    ++ " " ++ ns (ipc_opt_inv_ix
                    (EndpointIPC.nth_inv EndpointIPC.spec_surface n)).

(* -------------------------------------------------------------------------
   Family 4: the candidate surfaces (R-07-031a, R-07-031b, reading 2). The
   deletions and the insertions are refused and the transpositions are not,
   and the occurrence counts are printed beside the verdict so that the reason
   is on the line rather than inferred from it.
   ------------------------------------------------------------------------- *)

Definition srf_line (n : nat) : string :=
  let l := nth n ipc_surfaces (nil : list EndpointIPC.Invocation) in
  "ipc srf " ++ ns n ++ " ->"
    ++ " " ++ bs (EndpointIPC.frozen_surface l)
    ++ " " ++ ns (EndpointIPC.count_of l)
    ++ " " ++ ns (EndpointIPC.occurrences_inv EndpointIPC.Send l)
    ++ " " ++ ns (EndpointIPC.occurrences_inv EndpointIPC.Revoke l)
    ++ " " ++ ns (ipc_opt_inv_ix (EndpointIPC.nth_inv l 0))
    ++ " " ++ ns (ipc_opt_inv_ix
                    (EndpointIPC.nth_inv l
                       (EndpointIPC.before_last (EndpointIPC.count_of l)))).

(* -------------------------------------------------------------------------
   Family 5: every boolean enumeration over the closed invocation set
   (R-07-031a). Thirty-two masks, of which exactly one admits all five; each
   member's own bit is printed, so a mask that stopped admitting a member is
   a column rather than a verdict.
   ------------------------------------------------------------------------- *)

Definition msk_line (n : nat) : string :=
  "ipc msk " ++ ns n ++ " ->"
    ++ " " ++ bs (EndpointIPC.surface_mask_ok n)
    ++ " " ++ bs (EndpointIPC.admits_of_mask n EndpointIPC.Send)
    ++ " " ++ bs (EndpointIPC.admits_of_mask n EndpointIPC.Receive)
    ++ " " ++ bs (EndpointIPC.admits_of_mask n EndpointIPC.PollSiteYield)
    ++ " " ++ bs (EndpointIPC.admits_of_mask n EndpointIPC.GrantRedeem)
    ++ " " ++ bs (EndpointIPC.admits_of_mask n EndpointIPC.Revoke).

(* -------------------------------------------------------------------------
   Family 6: the endpoint transfer over every readiness state of the machine
   and every endpoint of it (R-07-029a, R-07-037a). The five obligations are
   five columns and the four constructions that break one apiece are printed
   beside the specification at the same point, so what separates them is on
   the line: the queue depth, the caller's wait bit, the peer's runnable bit
   and the refusal itself.
   ------------------------------------------------------------------------- *)

Definition tr_line (r e : nat) : string :=
  let st := EndpointIPC.readiness_of r in
  let o := ipc_probe_offer e in
  let k := EndpointIPC.empty_kernel in
  let said := EndpointIPC.said EndpointIPC.spec_transfer k st o in
  "ipc tr " ++ ns r ++ " " ++ ns e ++ " ->"
    ++ " " ++ bs (st e)
    ++ " " ++ bs (EndpointIPC.is_refused said)
    ++ " " ++ bs (ipc_crossed (EndpointIPC.delivered said))
    ++ " " ++ ns (ipc_carried_slots (EndpointIPC.delivered said))
    ++ " " ++ bs (EndpointIPC.is_refused
                    (EndpointIPC.said EndpointIPC.queueing_transfer k st o))
    ++ " " ++ ns (EndpointIPC.count_of
                    (EndpointIPC.held
                       (EndpointIPC.after EndpointIPC.queueing_transfer k st o)))
    ++ " " ++ bs (EndpointIPC.waiting
                    (EndpointIPC.after EndpointIPC.blocking_transfer k st o)
                    (EndpointIPC.offer_from o))
    ++ " " ++ bs (EndpointIPC.runnable
                    (EndpointIPC.after EndpointIPC.waking_transfer k st o)
                    (EndpointIPC.offer_at o))
    ++ " " ++ bs (EndpointIPC.is_refused
                    (EndpointIPC.said EndpointIPC.deaf_transfer k st o))
    ++ " " ++ ns (EndpointIPC.count_of
                    (EndpointIPC.held
                       (EndpointIPC.after EndpointIPC.blocking_transfer k st o)))
    (* The twin of the two columns above: the waking construction clears the
       peer's runnable bit and leaves every other partition's alone, and the
       blocking construction sets the caller's wait bit and leaves every other
       partition's alone. Printing only the bit each one moves would leave the
       shape of the construction and not the named defect as what refuses it. *)
    ++ " " ++ bs (EndpointIPC.runnable
                    (EndpointIPC.after EndpointIPC.waking_transfer k st o)
                    (S (EndpointIPC.offer_at o)))
    ++ " " ++ bs (EndpointIPC.waiting
                    (EndpointIPC.after EndpointIPC.blocking_transfer k st o)
                    (S (EndpointIPC.offer_from o))).

(* -------------------------------------------------------------------------
   Family 7: the optimistic transfers, which cross to an unready peer at every
   endpoint below an index. The zeroth member is the specification's own
   behaviour and every later one breaks R-07-029a's first sentence, so the
   family is walked over the index rather than sampled at two points.

   It is walked at two readiness states and not one. At the all-unready state
   the construction and the specification part company, which is the
   refutation; at the all-ready state they agree, which is the twin that makes
   the crossing and not the construction's shape what refuses it. A family
   walked at the unready state alone would print a column that never agrees
   and could not tell the two apart.
   ------------------------------------------------------------------------- *)

Definition ipc_readiness_poles : list nat :=
  cons 0 (cons (EndpointIPC.before_last ipc_states) nil).

Definition opt_line (r k e : nat) : string :=
  let st := EndpointIPC.readiness_of r in
  let o := ipc_probe_offer e in
  "ipc opt " ++ ns r ++ " " ++ ns k ++ " " ++ ns e ++ " ->"
    ++ " " ++ bs (EndpointIPC.is_refused
                    (EndpointIPC.said (EndpointIPC.optimistic_at k)
                                      EndpointIPC.empty_kernel st o))
    ++ " " ++ bs (EndpointIPC.is_refused
                    (EndpointIPC.said EndpointIPC.spec_transfer
                                      EndpointIPC.empty_kernel st o))
    ++ " " ++ bs (st e)
    ++ " " ++ bs (ipc_crossed
                    (EndpointIPC.delivered
                       (EndpointIPC.said (EndpointIPC.optimistic_at k)
                                         EndpointIPC.empty_kernel st o))).

(* -------------------------------------------------------------------------
   Family 8: an offer sequence longer than the endpoint set, at every
   readiness state (R-07-029a's third accept clause, R-11-010, R-17-030x).
   What the specification leaves behind is nothing at every state; what the
   queueing construction leaves behind grows with the sequence.
   ------------------------------------------------------------------------- *)

Definition seq_line (r : nat) : string :=
  let st := EndpointIPC.readiness_of r in
  let k := EndpointIPC.empty_kernel in
  "ipc seq " ++ ns r ++ " ->"
    ++ " " ++ ns (EndpointIPC.count_of
                    (EndpointIPC.held
                       (EndpointIPC.run_offers EndpointIPC.spec_transfer k st
                                               ipc_offers)))
    ++ " " ++ ns (EndpointIPC.count_of
                    (EndpointIPC.held
                       (EndpointIPC.run_offers EndpointIPC.queueing_transfer k st
                                               ipc_offers)))
    ++ " " ++ bs (EndpointIPC.all_of EndpointIPC.is_refused
                    (EndpointIPC.outcomes_of EndpointIPC.spec_transfer k st
                                             ipc_offers))
    ++ " " ++ ns (EndpointIPC.count_of
                    (EndpointIPC.outcomes_of EndpointIPC.spec_transfer k st
                                             ipc_offers))
    ++ " " ++ bs (EndpointIPC.waiting
                    (EndpointIPC.run_offers EndpointIPC.blocking_transfer k st
                                            ipc_offers) 0).

(* -------------------------------------------------------------------------
   Family 9: the slot faults (R-07-031, R-07-029). The register budget and the
   capability-slot budget are walked independently, which is the whole of what
   this family is for: a slot fault is a message inside the first budget and
   past the second, and an input that moved the two together could not tell
   `message_ok`'s conjuncts apart. The three grants are read at the same
   message, at a slot the message names and at one it does not.
   ------------------------------------------------------------------------- *)

Definition msg_line (w s : nat) : string :=
  let msg := ipc_message w s in
  "ipc msg " ++ ns w ++ " " ++ ns s ++ " ->"
    ++ " " ++ bs (EndpointIPC.message_ok ipc_machine msg)
    ++ " " ++ bs (Nat.leb (EndpointIPC.count_of (EndpointIPC.msg_regs msg))
                          (EndpointIPC.word_count ipc_machine))
    ++ " " ++ bs (Nat.leb (EndpointIPC.count_of (EndpointIPC.msg_caps msg))
                          (EndpointIPC.slot_count ipc_machine))
    ++ " " ++ bs (EndpointIPC.message_ok EndpointIPC.demo msg)
    (* Slot 0 is named by every non-empty payload and slot 1 by every payload
       of two or more, so both columns decide across the grid. A slot the grid
       never reaches would be a column that is false down the family whatever
       `carried` did, which is the dead arm this walk exists to avoid. *)
    ++ " " ++ bs (EndpointIPC.carried msg 0)
    ++ " " ++ bs (EndpointIPC.carried msg 1)
    (* The three grants at a slot the payload may or may not name, and the
       ambient construction at the one slot it hands over regardless. That
       pair is what makes the mint and not a different table the defect. *)
    ++ " " ++ bs (EndpointIPC.spec_grant msg (fun _ => false) 1)
    ++ " " ++ bs (EndpointIPC.ambient_grant msg (fun _ => false) 1)
    ++ " " ++ bs (EndpointIPC.ambient_grant msg (fun _ => false) 0)
    ++ " " ++ bs (EndpointIPC.stingy_grant msg (fun _ => true) 1)
    ++ " " ++ bs (EndpointIPC.replacing_grant msg (fun _ => true) 1).

(* -------------------------------------------------------------------------
   Family 10: the badge space at every width up to one past the machine's own
   (R-07-031, R-15-007, gap a). The width is the gap, so this is a family
   rather than a figure: the generated space is counted, the declared power of
   two is printed beside it, and one badge of each width is offered to two
   machines whose declared widths differ.
   ------------------------------------------------------------------------- *)

Definition bdg_line (w : nat) : string :=
  let b := EndpointIPC.head_or (EndpointIPC.badges w) (nil : list bool) in
  "ipc bdg " ++ ns w ++ " ->"
    ++ " " ++ ns (EndpointIPC.count_of (EndpointIPC.badges w))
    ++ " " ++ ns (EndpointIPC.two_pow w)
    ++ " " ++ bs (EndpointIPC.all_of
                    (fun x => Nat.eqb (EndpointIPC.count_of x) w)
                    (EndpointIPC.badges w))
    ++ " " ++ ns (EndpointIPC.count_of b)
    ++ " " ++ bs (EndpointIPC.badge_ok ipc_machine b)
    ++ " " ++ bs (EndpointIPC.badge_ok EndpointIPC.demo b).

(* -------------------------------------------------------------------------
   Family 11: the composition-fixed rotation (R-07-037b). The specification's
   successor is printed beside the work-stealing construction under two
   observations, so the column that moves is the runtime read.
   ------------------------------------------------------------------------- *)

Definition rot_line (u : nat) : string :=
  "ipc rot " ++ ns u ++ " ->"
    ++ " " ++ ns (EndpointIPC.advance ipc_machine u)
    ++ " " ++ ns (EndpointIPC.advance EndpointIPC.demo u)
    ++ " " ++ ns (EndpointIPC.work_stealing_advance ipc_machine
                    EndpointIPC.quiet_memory u)
    ++ " " ++ ns (EndpointIPC.work_stealing_advance ipc_machine
                    EndpointIPC.loaded_memory u)
    ++ " " ++ ns (EndpointIPC.label ipc_machine u)
    ++ " " ++ ns (EndpointIPC.rotate_from
                    (EndpointIPC.group_members ipc_machine) u u).

(* -------------------------------------------------------------------------
   Family 12: the pending delivery (R-07-037c, R-07-044). Three deliveries at
   one point: the specification's, the one that performs no swap and so on the
   swap arm varies with the predecessor, and the one that hands every member
   the group head's file and so does not.

   **There is no static-arm column, and its absence is the point.** A column
   reading `spec_delivery` on both machines prints one bit twice, because that
   definition does not read `pending_arm` and the two probe machines share
   their interrupt file. Reading `unswapped_delivery` on the static machine
   instead moves the duplication rather than removing it: on that arm the
   construction *is* the specification, which EndpointIPC.v proves of every
   machine at `the_construction_is_the_specification_on_the_static_arm`, so
   that column is column one for a reason and no input can move the two
   apart. A column no input can move independently is the dead-arm shape this
   walk exists to refuse, so the arm is read back once in `ipc dec` and the
   place it decides anything is the swap-arm column against the successor's
   own row, which is where the file's own theorems say it decides.

   Each of the three deliveries is printed beside the row it is pinned to:
   the specification against the successor's row, the unswapped construction
   against the predecessor's, and the head-member construction against the
   group head's. **Each pair agrees on all 48 rows by conversion, and that is
   what the pair is for rather than a measurement it reports.** What parts a
   definition from its reference is an edit to the definition, not an input,
   so these three pairs detect a changed decider and nothing about the domain.
   What the domain decides is the references: the successor's row and the
   predecessor's differ on 20 of the 48, which is why the unswapped
   construction is a different function from the specification here and not
   two spellings of one.
   ------------------------------------------------------------------------- *)

Definition dlv_line (p s b : nat) : string :=
  "ipc dlv " ++ ns p ++ " " ++ ns s ++ " " ++ ns b ++ " ->"
    ++ " " ++ bs (EndpointIPC.spec_delivery ipc_machine p s b)
    ++ " " ++ bs (EndpointIPC.unswapped_delivery ipc_machine p s b)
    ++ " " ++ bs (EndpointIPC.head_member_delivery ipc_machine p s b)
    ++ " " ++ bs (EndpointIPC.pending ipc_machine s b)
    ++ " " ++ bs (EndpointIPC.pending ipc_machine p b)
    ++ " " ++ bs (EndpointIPC.pending ipc_machine
                    (EndpointIPC.head_or
                       (EndpointIPC.group_members ipc_machine) s) b).

(* -------------------------------------------------------------------------
   Family 13: the consumer's decision over two ring observations (R-12-096).
   The two obligations are separate and each construction breaks one, so the
   pre-arming ring and the post-arming ring are walked independently.
   ------------------------------------------------------------------------- *)

Definition rng_line (pb pn c : nat) : string :=
  let before := ipc_ring pb c in
  let now := ipc_ring pn c in
  "ipc rng " ++ ns pb ++ " " ++ ns pn ++ " " ++ ns c ++ " ->"
    ++ " " ++ bs (EndpointIPC.has_work before)
    ++ " " ++ bs (EndpointIPC.has_work now)
    ++ " " ++ bs (EndpointIPC.spec_decide before now)
    ++ " " ++ bs (EndpointIPC.naive_decide before now)
    ++ " " ++ bs (EndpointIPC.post_only_decide before now).

(* -------------------------------------------------------------------------
   Family 14: the notification word (R-12-096, R-08-032, R-07-039). The
   counting construction is walked over its own carrier, which is where its
   defect lives: signalling twice leaves a state signalling once does not.
   ------------------------------------------------------------------------- *)

Definition wrd_line (n : nat) : string :=
  "ipc wrd " ++ ns n ++ " ->"
    ++ " " ++ bs (EndpointIPC.counting_armed n)
    ++ " " ++ ns (EndpointIPC.counting_signal n)
    ++ " " ++ ns (EndpointIPC.counting_reset n)
    ++ " " ++ ns (EndpointIPC.counting_signal (EndpointIPC.counting_signal n))
    ++ " " ++ bs (EndpointIPC.counting_armed (EndpointIPC.counting_reset n)).

(* -------------------------------------------------------------------------
   Family 15: every act, numbered or not (R-07-031b, R-07-030, R-07-031a).
   The specification's cut is printed beside R-07-031b's own criterion for
   what may be numbered, the two trap surfaces that criterion admits, and the
   four numberings that add or drop a member. The two trap columns are here
   because gap i is open: they agree at fourteen acts and part at the three
   R-11-023 owes a carrier for, and a run in which they agreed everywhere
   would be a run in which the parameter had stopped being one.
   ------------------------------------------------------------------------- *)

Definition act_line (n : nat) : string :=
  let a := nth n EndpointIPC.all_acts EndpointIPC.ASend in
  "ipc act " ++ ns n ++ " ->"
    ++ " " ++ ns (ipc_act_ix a)
    ++ " " ++ bs (EndpointIPC.numbered_act a)
    ++ " " ++ bs (EndpointIPC.is_the_act_of_an_invocation a)
    ++ " " ++ bs (EndpointIPC.deleted_act a)
    ++ " " ++ bs (EndpointIPC.traps_act a)
    ++ " " ++ bs (EndpointIPC.traps_with_the_schedule_transitions a)
    ++ " " ++ bs (EndpointIPC.iouring_numbering a)
    ++ " " ++ bs (EndpointIPC.fifth_group_numbering a)
    ++ " " ++ bs (EndpointIPC.short_numbering a)
    ++ " " ++ bs (EndpointIPC.schedule_numbering a)
    ++ " " ++ bs (EndpointIPC.notification_numbering a).

(* -------------------------------------------------------------------------
   Family 16: the five invocations, their groups and their costs (R-07-029a,
   R-07-031a). The two bound readings are printed apart: `leb` is the reading
   the entry's words carry and `ltb` is the one that would refuse the
   boundary, and three members of this machine sit exactly on it.
   ------------------------------------------------------------------------- *)

Definition cst_line (n : nat) : string :=
  let i := nth n EndpointIPC.all_invocations EndpointIPC.Send in
  "ipc cst " ++ ns n ++ " ->"
    ++ " " ++ ns (EndpointIPC.index_of i)
    ++ " " ++ ns (ipc_grp_ix (EndpointIPC.group_of i))
    ++ " " ++ ns (ipc_act_ix (EndpointIPC.act_of i))
    ++ " " ++ ns (EndpointIPC.invocation_cost ipc_machine i)
    ++ " " ++ ns (EndpointIPC.refusal_cost ipc_machine i)
    ++ " " ++ ns (EndpointIPC.boundary_refusal ipc_machine i)
    (* `leb` of the composed refusal against its invocation holds of all five
       and so is a column that reads only this harness's own fields; it is not
       printed, a column no mutation of the artifact could move being a clause
       reported held that nothing holds. `ltb` is printed because it is the
       reading that would refuse the boundary, and three members of this
       machine sit exactly on it. *)
    ++ " " ++ bs (Nat.ltb (EndpointIPC.refusal_cost ipc_machine i)
                          (EndpointIPC.invocation_cost ipc_machine i))
    ++ " " ++ ns (EndpointIPC.retrying_refusal i)
    ++ " " ++ bs (Nat.leb (EndpointIPC.retrying_refusal i)
                          (EndpointIPC.invocation_cost ipc_machine i))
    ++ " " ++ ns (EndpointIPC.count_of
                    (EndpointIPC.members_of (EndpointIPC.group_of i))).

(* -------------------------------------------------------------------------
   Family 17: the four ABI groups, whose second member is empty by filtering
   rather than by omission (R-07-031a, reading 4). The census of the grouping
   that files the poll-site yield under the notification group is printed
   beside it, because a census over one total function is not a refutation of
   anything: what makes the emptiness a result is that a grouping which fills
   the group is expressible here and refused.
   ------------------------------------------------------------------------- *)

Definition grp_line (n : nat) : string :=
  let g := nth n EndpointIPC.all_groups EndpointIPC.EndpointGroup in
  "ipc grp " ++ ns n ++ " ->"
    ++ " " ++ ns (EndpointIPC.count_of (EndpointIPC.members_of g))
    ++ " " ++ ns (EndpointIPC.census EndpointIPC.group_of g)
    ++ " " ++ ns (EndpointIPC.census EndpointIPC.notifying_grouping g)
    ++ " " ++ ns (ipc_opt_inv_ix
                    (EndpointIPC.nth_inv (EndpointIPC.members_of g) 0))
    ++ " " ++ ns (ipc_opt_inv_ix
                    (EndpointIPC.nth_inv (EndpointIPC.members_of g) 1)).

(* -------------------------------------------------------------------------
   Family 18: the five return paths, clause by clause (R-07-027a, R-04-008,
   R-15-007). Four clauses and five paths, so a clause that stopped deciding
   is a column that went constant down the family.
   ------------------------------------------------------------------------- *)

Definition rp_line (n : nat) : string :=
  let p := nth n ipc_return_paths EndpointIPC.badge_return in
  "ipc rp " ++ ns n ++ " ->"
    ++ " " ++ ns (EndpointIPC.count_of (EndpointIPC.rp_classes p))
    ++ " " ++ ns (EndpointIPC.rp_otypes p)
    ++ " " ++ bs (EndpointIPC.rp_mints p)
    ++ " " ++ ns (ipc_act_ix (EndpointIPC.rp_act p))
    ++ " " ++ bs (EndpointIPC.numbered_act (EndpointIPC.rp_act p))
    ++ " " ++ bs (EndpointIPC.all_of EndpointIPC.is_object
                    (EndpointIPC.rp_classes p)).

(* -------------------------------------------------------------------------
   Family 19: the two notification halves, which are memory operations and so
   take no ABI number (R-08-032, R-07-039, reading 4).
   ------------------------------------------------------------------------- *)

Definition hlf_line (h : EndpointIPC.NotifyHalf) : string :=
  "ipc hlf " ++ ns (ipc_act_ix (EndpointIPC.act_of_half h)) ++ " ->"
    ++ " " ++ ns (ipc_medium_ix (EndpointIPC.medium_of h))
    ++ " " ++ bs (EndpointIPC.numbered_act (EndpointIPC.act_of_half h))
    ++ " " ++ bs (EndpointIPC.traps_act (EndpointIPC.act_of_half h))
    ++ " " ++ bs (EndpointIPC.iouring_numbering (EndpointIPC.act_of_half h)).

(* -------------------------------------------------------------------------
   And the machine's own declared quantities, in one line, so that a field
   this harness walks a domain off is read back rather than trusted. The two
   label groups are here because neither is a family: one is admissible and
   one crosses a label boundary, and both are needed for `SameLabelGroup` to
   be a column instead of a constant.
   ------------------------------------------------------------------------- *)

Definition dec_line : string :=
  "ipc dec ->"
    ++ " " ++ ns (EndpointIPC.partition_count ipc_machine)
    ++ " " ++ ns (EndpointIPC.endpoint_count ipc_machine)
    ++ " " ++ ns (EndpointIPC.word_count ipc_machine)
    ++ " " ++ ns (EndpointIPC.slot_count ipc_machine)
    ++ " " ++ ns (EndpointIPC.badge_width ipc_machine)
    ++ " " ++ ns (EndpointIPC.pending_width ipc_machine)
    ++ " " ++ bs (EndpointIPC.pending_arm ipc_machine)
    ++ " " ++ bs (EndpointIPC.pending_arm ipc_machine_static)
    ++ " " ++ ns (EndpointIPC.count_of
                    (EndpointIPC.group_members ipc_machine))
    ++ " " ++ bs (EndpointIPC.SameLabelGroup ipc_machine
                    (EndpointIPC.group_members ipc_machine))
    ++ " " ++ bs (EndpointIPC.SameLabelGroup ipc_machine ipc_mixed_group)
    ++ " " ++ ns (EndpointIPC.count_of EndpointIPC.all_invocations)
    ++ " " ++ ns (EndpointIPC.count_of EndpointIPC.object_classes)
    ++ " " ++ ns (EndpointIPC.count_of EndpointIPC.kernel_tables)
    ++ " " ++ bs (EndpointIPC.badge_ok ipc_machine ipc_badge)
    ++ " " ++ bs (EndpointIPC.badge_ok EndpointIPC.demo ipc_badge)
    ++ " " ++ bs (EndpointIPC.spec_signal
                    (EndpointIPC.spec_signal false))
    ++ " " ++ bs (EndpointIPC.spec_reset true)
    ++ " " ++ bs (EndpointIPC.armed_of (EndpointIPC.spec_reset true)).

(* -------------------------------------------------------------------------
   The walk. Every bound is read off the machine's own fields or off one of
   the artifact's own lists, so nothing here is a magnitude this harness
   chose: the payload grid runs one past each budget, the badge widths one
   past the declared one, and the rotation one past the group.
   ------------------------------------------------------------------------- *)

Definition ipc_report : list string :=
  List.app
    (flat_map (fun c => map (lc_line c) EndpointIPC.all_lifecycles)
              EndpointIPC.all_nameable)
  (List.app (map inv_line (seq 0 (length ipc_inventories)))
  (List.app (map dsp_line (seq 0 (S (S (EndpointIPC.count_of
                                          EndpointIPC.spec_surface)))))
  (List.app (map srf_line (seq 0 (length ipc_surfaces)))
  (List.app (map msk_line EndpointIPC.all_masks)
  (List.app (flat_map (fun r => map (tr_line r) (seq 0 ipc_endpoints))
                      (seq 0 ipc_states))
  (List.app (flat_map (fun r =>
               flat_map (fun k => map (opt_line r k) (seq 0 ipc_endpoints))
                        (seq 0 (S ipc_endpoints)))
               ipc_readiness_poles)
  (List.app (map seq_line (seq 0 ipc_states))
  (List.app (flat_map (fun w =>
               map (msg_line w)
                   (seq 0 (S (S (EndpointIPC.slot_count ipc_machine)))))
               (seq 0 (S (S (EndpointIPC.word_count ipc_machine)))))
  (List.app (map bdg_line (seq 0 (S (S (EndpointIPC.badge_width ipc_machine)))))
  (List.app (map rot_line
               (seq 0 (S (S (EndpointIPC.count_of
                               (EndpointIPC.group_members ipc_machine))))))
  (List.app (flat_map (fun p =>
               flat_map (fun s =>
                 map (dlv_line p s)
                     (seq 0 (EndpointIPC.pending_width ipc_machine)))
                 (seq 0 (S (EndpointIPC.pending_width ipc_machine))))
               (seq 0 (S (EndpointIPC.pending_width ipc_machine))))
  (List.app (flat_map (fun pb =>
               flat_map (fun pn => map (rng_line pb pn) (seq 0 3)) (seq 0 3))
               (seq 0 3))
  (List.app (map wrd_line (seq 0 4))
  (List.app (map act_line (seq 0 (EndpointIPC.count_of EndpointIPC.all_acts)))
  (List.app (map cst_line
               (seq 0 (EndpointIPC.count_of EndpointIPC.all_invocations)))
  (List.app (map grp_line
               (seq 0 (EndpointIPC.count_of EndpointIPC.all_groups)))
  (List.app (map rp_line (seq 0 (length ipc_return_paths)))
  (List.app (map hlf_line EndpointIPC.all_halves)
            (cons dec_line nil))))))))))))))))))).

Definition report : list string := List.app ce_report ipc_report.

Compute report.
