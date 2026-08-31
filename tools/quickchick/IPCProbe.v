(* SPDX-License-Identifier: Apache-2.0 *)

(* =========================================================================
   The composition both halves of the Gallina front are exercised over when
   the subject is EndpointIPC.v.

   It is here rather than in either harness for the reason Probe.v states of
   the other subject: Vectors.v enumerates a domain over it and Properties.v
   draws from one, and a probe that differed between the two would make the
   two halves answer different questions while reading as one instrument.

   **It is deliberately not `demo`.** EndpointIPC.v ships two machines of its
   own and pins their every declared quantity by conversion, so a harness
   built on `demo` would re-read the file's own `Example`s rather than its
   definitions: every column would already be decided by a statement in the
   artifact, and the generated input side would add nothing a reader could
   name. The machine below instantiates the same record at different field
   values, so each column is the definition evaluated somewhere the artifact
   never evaluates it. Two fields are moved on purpose and it is worth saying
   which and why:

     - `word_count` is 3 where the demo's is 4, so `message_ok`'s register
       conjunct changes sign at a different payload size from the one the
       artifact's own two checks straddle.
     - `badge_width` is 2 where the demo's is 3, so EndpointIPC.v's own
       `probe_badge`, which that file admits, is refused here. A width the
       artifact never admits is what makes `badge_ok` read its field rather
       than a constant.

   **Nothing here is a claim about a real composition.** Every magnitude is a
   field because the register leaves it to composition, which is gap h of
   EndpointIPC.v's own header; the values below are arbitrary witnesses
   chosen so that each conjunct can decide, and they carry no claim about
   what any composition will choose. Where the register does close a count
   outright the artifact already carries it as a literal with the entry that
   closes it named, and nothing here restates one.

   **The dead-arm discipline Probe.v states applies here too.** A column no
   input can tell from its absence reports a clause held that nothing holds,
   so the group, the label, the rotation and the pending file below are all
   chosen to be non-constant over the domain the harnesses walk: the group
   does not start at zero, so `advance`'s wrap decides; the label splits the
   partitions, so `SameLabelGroup` decides on one group and not on another;
   and the pending file is an inequality rather than the demo's equality, so
   `spec_delivery`, `unswapped_delivery` and `head_member_delivery` are three
   different functions rather than three spellings that agree.

   **What a green run of either half means, and what it does not.** It means
   the definitions EndpointIPC.v ships computed an answer at every point of a
   declared domain or at every draw of a declared range, and that the answers
   are the ones the file's theorems say they should be. It does not mean
   verified, and it is weaker than the proof gate rather than additional to
   it: nothing here is compiled to Wasm, lowered, or run on either emulator,
   no constant here reaches R-05-163's assumption enumeration, and the proof
   gate never compiles this file. A vector is evidence that a definition
   decides something; it is not evidence that the decision is right.

   Readings of EndpointIPC.v this probe takes, each a reviewable judgment
   rather than a neutral transcription:

   1. A probe machine is a witness and not a composition. Every magnitude
      below instantiates a field EndpointIPC.v's gap h leaves to composition,
      so a run of either half says what the definitions answer at one point
      of that space and says nothing about which point a composition will
      choose. A reader taking `word_count := 3` for a claim would be reading
      this file as the register.
   2. Moving two fields off the demo's values is the whole reason this file
      exists rather than the harnesses reading `demo`. It is a judgment
      because it trades away agreement with the artifact's own worked
      examples: a column here and an `Example` there answer differently by
      construction, and a reader comparing them will find they disagree.
   3. Readiness is one bit per endpoint, which is EndpointIPC.v's gap g and
      the weaker of the two readings R-07-029a's *meets no ready peer*
      carries. Both halves inherit it: the sixteen-state family and the drawn
      readiness index are both indices into a per-endpoint bit space, and a
      reading on which readiness were per offering peer would make neither
      domain the right one.
   4. The badge is a bit list of a declared width, which is gap a. The width
      here is 2 and the artifact's own is 3, so `badge_ok` is exercised on
      both sides of its own field; neither figure is a claim about how wide a
      badge is, and no entry says.
   5. Three of the five refusal costs sit exactly at the invocation's own
      bound and two sit below it. That is reading 13 of EndpointIPC.v given a
      domain: *within the invocation's own bounded cost* admits a refusal
      that spends the whole of it, so a probe on which no member reached the
      boundary would leave the weaker reading undecided by every input and a
      probe on which every member reached it would leave the strict reading
      undecided.

   Gaps reported, not closed. This file takes no decision the register owes
   and it closes none of EndpointIPC.v's own; what is recorded here is the
   two that bind the shape of the input side rather than only its values:

   a. Whether a notification word is per partition, per endpoint or per ring
      is unstated (EndpointIPC.v's gap f, owed at R-12-096 or R-08-032), so
      neither half walks a word domain at all: the obligations are exercised
      over an arbitrary carrier, which is the only shape available while the
      granularity is open.
   b. What a re-offer costs and how many are admitted is unstated
      (EndpointIPC.v's gap e, owed at R-07-042 or R-11-010), so the offer
      sequence below is a witness length and carries no claim. A later entry
      bounding the count would make the sequence's length a quantity to read
      off a field rather than one this file picks.
   ========================================================================= *)

Require Import EndpointIPC.

(* -------------------------------------------------------------------------
   Positions. A vector is text and a counterexample is read by a person, so
   every closed enumeration the register fixes needs an index. Each is the
   position the artifact's own `all_*` list holds the member at, and the
   out-of-range answer is the list's own length, which is the convention
   `index_of` already takes for a member no sequence numbers.
   ------------------------------------------------------------------------- *)

Definition ipc_inv_ix (i : Invocation) : nat := index_of i.

Definition ipc_opt_inv_ix (o : option Invocation) : nat :=
  match o with
  | None => count_of all_invocations
  | Some i => index_of i
  end.

Definition ipc_grp_ix (g : AbiGroup) : nat :=
  match g with
  | EndpointGroup => 0
  | NotificationGroup => 1
  | PartitionContextGroup => 2
  | RevocationGroup => 3
  end.

Definition ipc_nm_ix (c : Nameable) : nat :=
  match c with
  | NEndpoint => 0
  | NNotification => 1
  | NPartitionContext => 2
  | NGrantTable => 3
  | NScheduleTable => 4
  | NReplyObject => 5
  end.

Definition ipc_lc_ix (op : Lifecycle) : nat :=
  match op with LCreate => 0 | LDerive => 1 | LRevoke => 2 end.

Definition ipc_act_ix (a : Act) : nat :=
  match a with
  | ASend => 0
  | AReceive => 1
  | AYield => 2
  | AGrantRedeem => 3
  | ARevoke => 4
  | ANotifySignal => 5
  | ANotifyReceive => 6
  | AGrantMint => 7
  | AFocusRebind => 8
  | ARungSelect => 9
  | ASuspend => 10
  | ASynchronousException => 11
  | ARetype => 12
  | ACapSpaceOp => 13
  | ADerivationTreeOp => 14
  | ASubmissionQueueOpcode => 15
  | AReplyInvocation => 16
  end.

(* R-08-032's store and R-07-039's load, as the two positions that make the
   notification group empty. It is an index rather than a boolean because the
   medium is a choice between two named things and not the absence of one. *)
Definition ipc_medium_ix (m : Medium) : nat :=
  match m with ByStore => 0 | ByLoad => 1 end.

(* What an outcome carried, as two readings a text line can hold: whether a
   message crossed at all, and how many capability slots it named. The second
   is what makes a slot fault visible in the outcome rather than only in the
   admission check. *)
Definition ipc_crossed (o : option Message) : bool :=
  match o with None => false | Some _ => true end.

Definition ipc_carried_slots (o : option Message) : nat :=
  match o with None => 0 | Some msg => count_of msg.(msg_caps) end.

(* -------------------------------------------------------------------------
   The two cost functions. Three members sit exactly at R-07-029a's boundary
   and two sit below it, which is reading 13 of EndpointIPC.v given a domain:
   *within the invocation's own bounded cost* admits a refusal that spends the
   whole of it, so a probe on which no member reached the boundary would leave
   the reading undecided by every input.
   ------------------------------------------------------------------------- *)

Definition ipc_cost (i : Invocation) : nat :=
  match i with
  | Send => 5
  | Receive => 3
  | PollSiteYield => 1
  | GrantRedeem => 7
  | Revoke => 4
  end.

Definition ipc_refusal (i : Invocation) : nat :=
  match i with
  | Send => 2                    (* strictly below its invocation      *)
  | Receive => 3                 (* exactly at the boundary            *)
  | PollSiteYield => 1           (* exactly at the boundary            *)
  | GrantRedeem => 0             (* strictly below                     *)
  | Revoke => 4                  (* exactly at the boundary            *)
  end.

(* -------------------------------------------------------------------------
   The machine. Every field is the register's to leave open and this file's to
   witness; see gap h of EndpointIPC.v's header for the entry each is owed at.
   ------------------------------------------------------------------------- *)

Definition ipc_machine : Machine := {|
  partition_count := 5;
  endpoint_count := 4;           (* four endpoints, so readiness is 16 states *)
  word_count := 3;               (* moved off the demo's 4 on purpose         *)
  slot_count := 2;
  badge_width := 2;              (* moved off the demo's 3 on purpose         *)
  invocation_cost := ipc_cost;
  refusal_cost := ipc_refusal;
  group_members := cons 1 (cons 2 (cons 3 nil));
  label := fun u => if Nat.ltb u 4 then 0 else 1;
  pending_arm := true;
  pending := fun s b => Nat.ltb b s;
  pending_width := 3
|}.

(* The same composition on the other arm of R-07-044's disjunction, so the
   arm is a column rather than an assertion: everything but `pending_arm` is
   read back equal, which is what makes a comparison across the two a
   comparison of arms and not of compositions. *)
Definition ipc_machine_static : Machine := {|
  partition_count := 5;
  endpoint_count := 4;
  word_count := 3;
  slot_count := 2;
  badge_width := 2;
  invocation_cost := ipc_cost;
  refusal_cost := ipc_refusal;
  group_members := cons 1 (cons 2 (cons 3 nil));
  label := fun u => if Nat.ltb u 4 then 0 else 1;
  pending_arm := false;
  pending := fun s b => Nat.ltb b s;
  pending_width := 3
|}.

(* A group whose members do not share a label, which is what R-07-037d refuses
   at any cadence. It is here rather than in either harness because both walk
   it beside the composed group and a probe carrying only the admissible one
   would leave `SameLabelGroup` a constant-true column. *)
Definition ipc_mixed_group : list nat := cons 1 (cons 4 nil).

(* -------------------------------------------------------------------------
   The message and offer witnesses. `bulk` is EndpointIPC.v's own generator of
   an oversized payload and it is used here for both components, so the two
   budgets in `message_ok` are walked independently rather than together: a
   slot fault is a message inside the register budget and past the slot one,
   and no input that moved the two together could tell the conjuncts apart.
   ------------------------------------------------------------------------- *)

Definition ipc_message (w s : nat) : Message :=
  {| msg_regs := bulk w; msg_caps := bulk s |}.

Definition ipc_badge : Badge := cons true (cons false nil).

Definition ipc_offer (e : nat) (msg : Message) : Offer :=
  {| offer_from := 0; offer_at := e; offer_carries := msg;
     offer_badge := ipc_badge |}.

(* The offer the transfer family is walked with: one register and one slot,
   inside both budgets of the machine above. It is inside them on purpose, so
   that the family decides on the peer's readiness rather than on admission;
   the payload budgets are walked by a family of their own, where a message
   that is refused is the point rather than a confound. *)
Definition ipc_probe_message : Message := ipc_message 1 1.

Definition ipc_probe_offer (e : nat) : Offer := ipc_offer e ipc_probe_message.

(* An offer sequence that visits every endpoint of the machine once and then
   revisits the first, so `run_offers` and `outcomes_of` are walked over a
   sequence longer than the endpoint set: R-07-029a's re-offer is a repeat
   into an endpoint already offered to, and a sequence of distinct endpoints
   would not contain one. *)
Definition ipc_offers : list Offer :=
  cons (ipc_offer 0 (ipc_message 1 1))
  (cons (ipc_offer 1 (ipc_message 2 1))
  (cons (ipc_offer 2 (ipc_message 1 2))
  (cons (ipc_offer 3 (ipc_message 3 0))
  (cons (ipc_offer 0 (ipc_message 0 0)) nil)))).

(* R-12-096's two ring observations, built here so both halves name one shape.
   The consumer's decision reads a ring before arming and a ring after, and
   the two obligations over it are separate, so a harness that could only
   build one ring would collapse them. *)
Definition ipc_ring (p c : nat) : Ring :=
  {| produced := p; consumed := c |}.

(* The candidate inventories both halves score, which are EndpointIPC.v's own
   two generators run over its own inventory plus the inventory itself. The
   specification is last so that a run whose every candidate failed and whose
   specification passed is one line apart from a run where nothing decided. *)
Definition ipc_inventories : list (list Nameable) :=
  app inventory_deletions
  (app (inventory_insertions_of NGrantTable)
  (app (inventory_insertions_of NReplyObject)
  (app (inventory_insertions_of NEndpoint)
       (cons spec_inventory nil)))).

(* And the candidate surfaces, in the same shape: the two families R-07-031b
   refuses, the one reading 2 admits, and the specification's own sequence. *)
Definition ipc_surfaces : list (list Invocation) :=
  app (deletions_inv spec_surface)
  (app (insertions_inv spec_surface)
  (app (transpositions_inv spec_surface)
       (cons spec_surface nil))).

(* The five return paths EndpointIPC.v exhibits, walked as one list so that a
   clause that stopped deciding is a column that went constant. *)
Definition ipc_return_paths : list ReturnPath :=
  cons badge_return (cons reply_object_return (cons sealed_reply_return
  (cons composition_sealed_return (cons fifth_group_return nil)))).
