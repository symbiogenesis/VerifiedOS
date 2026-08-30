(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   MModeFirmware.v

   The M-mode firmware, as the register fixes it: R-07-028's initialisation
   refinement over the composed capability graph, R-07-019's per-core
   partition-bounded root derivation and the quiescence that follows,
   R-07-024's one-entry resident inventory, R-14-002's W^X discharged at
   R-15-007l's permission encoding over R-15-007b's 32 codepoints,
   R-14-003's absent promotion primitive, R-15-075's absence of any region
   register, R-07-018 and R-07-023's permission-decides-not-mode reading,
   and R-05-091's no-ambient-state obligation over the firmware's
   statically planned state.

   What this file is. A statement artifact in ApexTheorem.v's idiom, not a
   proof development and not an implementation. Every quantity the register
   leaves to composition, to the profile freeze, or to another artifact is
   a field of the Machine record rather than a literal or a top-level
   Parameter, which is what keeps the R-05-163 assumption gate green while
   leaving the decision where its owner can make it. Nothing is admitted
   and nothing is axiomatized: the Print Assumptions block at the end
   reports every shipped constant closed under the global context.

   What the gate's green line means. Compiled, axiom-free, non-vacuous and
   enumerated, and it does not mean verified. No constant here is compiled,
   lowered, or run on either emulator, and nothing here executes anywhere.
   There is no firmware in this file: what is written down is the
   obligations a firmware discharges, each stated of an arbitrary installer,
   gate, decision or working set and refuted of an alternative construction.
   The computed checks are decided inside the kernel by conversion and print
   nothing.

   No Require. Nothing beyond the Coq prelude is reachable, so Classical
   and FunctionalExtensionality are unavailable and every state equality
   below is stated pointwise for that reason. A Require naming a sibling
   artifact would be admissible and there is none to name: PartitionContext
   .v speaks about the partition switch, which is R-07-015's obligation on
   the resident kernel and not on the firmware, and ApexTheorem.v's
   init_realizes_topology is a Prop field of a record this file does not
   share. The two meet at that field's intended reading and not at a
   definition, so a Require here would be a citation rather than a
   dependency.

   Readings of the register this statement takes, each a reviewable
   judgment rather than a neutral transcription:

   1. The composed capability graph is a list of edges and an edge is a
      holder, a region, and a permission codepoint. R-07-025 fixes the
      component graph and the capability distribution at build time,
      R-08-011 makes the slot plan the unit a capability is bounded to, and
      R-15-007b makes the permission field a 5-bit enumerated lattice, so
      those three coordinates are what an edge carries and nothing else is.
      Bounds are modelled as region identity because R-08-011 makes the
      region the plan's own unit; a sub-region bounds algebra is
      R-15-007a's and is not restated here.
   2. What the firmware installs has exactly three components. R-07-028
      names the capability distribution as running kernel state, R-07-019
      names the per-core root derivation and the residency, and no entry of
      section 7.4 or 7.5 names a fourth. The partition contexts (R-07-015)
      and the schedule table (R-11-024) are not components here: whether
      R-07-028's *running kernel state* reaches them is unstated, and gap b
      below reports it rather than deciding it.
   3. The installer is a relation and not a function. The obligations
      R-07-028 and R-07-019 state are per-component write obligations, and
      stating them relationally is what lets an alternative construction be
      exhibited and refuted rather than merely differing from an
      implementation this file chose. That is PartitionContext.v's fifth
      reading, taken here for the same reason.
   4. The permission decode is a field. R-15-007b enumerates the lattice
      *at freeze time* and no artifact in this repository carries the
      enumeration, so which codepoint names which set is the freeze's to
      say. What is stated is the obligation on any decode, and the demo
      decodes at the end are witness values carrying no freeze claim.
   5. R-14-002's absence is discharged at the encoding and confirmed at the
      distribution, in that order, which is that entry's own criterion.
      What makes the criterion a criterion rather than an approximation is
      that the finite check over the 32 codepoints is proved *sound and
      complete* for the universally quantified statement, so the check is
      the property rather than a test of it. The derivation-forest check is
      kept beside it and is shown to be strictly weaker: it passes on a
      machine whose encoding admits a Store-and-Execute codepoint, which is
      the redundancy the criterion names read from the other side.
   6. Mode is a single-constructor inductive. R-07-018's Accept is *there is
      no S-mode and no U-mode*, so the absence is stated by construction and
      its consequence, that a mode check separates nothing, is proved rather
      than asserted. That consequence is R-07-023's whole content: a
      compartment is refused because its PCC lacks the permission and not
      because a mode check fires, and here a mode check cannot fire because
      there is one mode.
   7. R-15-075's absence is stated in the shape of the decision. An access
      decision is a function of the capability and the region alone, with no
      region-table argument for a region register to be read from, and the
      Installed record carries no region-table component. Beside the
      structural absence the file states what a region table could do if one
      existed: it can only subtract, which is R-15-075's *strict subset*
      reading made checkable, and it is refuted as a decision because a
      subtraction is still a second mechanism to get right.
   8. The build-time check and the installed-state property are joined by
      R-07-028 and by nothing else. R-07-025's check runs over the composed
      graph and R-07-023's obligation is about the booted machine, and what
      carries the first to the second is the initialisation refinement.
      That join is this file's load-bearing theorem, and the construction
      beside it shows that without the refinement the build-time check says
      nothing about the machine that runs.
   9. Boolean rather than propositional wherever the witnesses must compute:
      the codepoint check, the graph checks, the inventory check and the
      root check are decidable, so the generated families below are checked
      by conversion in the silent Example form rather than by a proof per
      member.

   The literals taken from the design, and there are two. R-15-007b fixes
   the permission field at 5 bits and its enumeration as total over all 32
   codepoints, so Perm is five booleans and all_perms is generated over
   them; and R-07-024's criterion fixes the resident-code inventory at one
   entry, so inventory_ok compares against 1. Every other magnitude is a
   field: the decode, the node and region types with their decidable
   equalities, the kernel and firmware nodes, the core roster, and each
   core's partition.

   How the refutations are generated. A refutation is a seeded weakening
   the theorem must reject, so four generators produce families of them
   mechanically rather than a person authoring each. Over the permission
   field's own bits, a nested boolean generator yields the 32 codepoints the
   W^X check is decided over. Over the register's own residency names,
   `intruded` yields one weakening per kind other than the microkernel.
   Over the specification's own plan, `drop_at` deletes an edge and yields
   one weakening per position, and `insert_at` adds the unplanned edge and
   yields one per position. Beside them the generic theorems quantify over
   the edge rather than enumerating, so the added-edge and dropped-edge
   refutations are stated once for every plan and every edge rather than
   once for the demo's five. The hand-authored refutations below are the
   ones no generator produces, being alternative constructions rather than
   mutations of a list.

   What this file deliberately does not author, with the entry that owes
   each decision. A register gap is reported, not closed:

   a. Which codepoint names which permission set. R-15-007b enumerates the
      lattice at freeze time and no artifact in this repository carries the
      enumeration, so `decode` is a field and every obligation over it is
      stated of an arbitrary one. Owed at R-15-007b, or at whatever artifact
      the freeze lands in.
   b. What *running kernel state* comprises. R-07-028 obliges the firmware
      to instantiate exactly the composed cap graph as running kernel state
      and no entry says whether the partition contexts R-07-015 restores and
      the schedule table R-11-024 swaps are inside that phrase or beside it.
      This file states the distribution alone. Owed at R-07-028.
   c. What completes a core's root set. R-07-019 has the firmware derive
      each core's partition-bounded root capability and R-07-006 fixes the
      bound; R-15-007p makes the root a permission-split set over the
      partition, an execute-side authority over text extents and a
      store-side authority over data, and no artifact here distinguishes
      text from data at a region. So the bound is stated and the totality is
      stated only as *some root per core*, which is the weakest thing the
      entries fix. Owed at R-07-019 or R-15-007p.
   d. The resident-code inventory itself. R-07-024's criterion audits an
      enumeration no artifact carries: not the register, the spec, proofs/,
      the model, or corpus/. The Resident inductive below is over R-07-019's
      and R-07-024's own four names for what must not be resident plus
      R-07-020's one name for what is, and it is not an inventory. Owed at
      R-07-024. This is R-07-031a's shape one entry over, and R-07-031b is
      the precedent for how it closes.
   e. Where the firmware's own Tier-0 proof lands. R-05-091 puts the
      no-ambient-state obligation on the firmware as ordinary Tier-0 proof
      over its statically planned state, and no artifact here is that proof;
      what is below is the obligation stated and refuted, which is a
      statement and not a discharge.
   f. Every composition magnitude. The node and region types, the kernel and
      firmware nodes, the core roster and each core's partition are fields;
      the demo machines at the end instantiate them with arbitrary witness
      values that carry no composition claim.

   Non-vacuity (R-05-165, R-05-166). Every obligation below is stated as a
   property of an arbitrary installer, decode, gate, decision, promotion or
   working set, proved of the specification, and refuted of an alternative
   construction the register's own sentence excludes. Inhabitation is stated
   twice: canonically at every machine whose plan roots every core, and
   concretely at two machines whose every domain is inhabited, one whose
   encoding excludes W+X and one whose encoding admits it.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   Booleans and lists, defined here rather than imported: the prelude
   carries the list type and not the library over it, and importing a module
   to save a page would put its assumptions inside the R-05-163 gate's reach
   for no gain.
   ------------------------------------------------------------------------- *)

Definition bool_eqb (a b : bool) : bool := if a then b else negb b.

Lemma bool_eqb_refl : forall a : bool, bool_eqb a a = true.
Proof. intros [ | ]; reflexivity. Qed.

Lemma bool_eqb_sound : forall a b : bool, bool_eqb a b = true -> a = b.
Proof. intros [ | ] [ | ] H; try discriminate H; reflexivity. Qed.

Lemma andb_split : forall a b : bool, andb a b = true -> a = true /\ b = true.
Proof.
  intros a b H. destruct a; destruct b; simpl in H;
    try discriminate H; split; reflexivity.
Qed.

Lemma andb_join : forall a b : bool, a = true -> b = true -> andb a b = true.
Proof. intros a b Ha Hb. rewrite Ha. rewrite Hb. reflexivity. Qed.

Lemma orb_split : forall a b : bool, orb a b = true -> a = true \/ b = true.
Proof.
  intros [ | ] [ | ] H;
    try discriminate H; [ left | left | right ]; reflexivity.
Qed.

Lemma orb_true_right : forall a : bool, orb a true = true.
Proof. intros [ | ]; reflexivity. Qed.

Lemma negb_true : forall a : bool, negb a = true -> a = false.
Proof. intros [ | ] H; [ discriminate H | reflexivity ]. Qed.

(* A disjunct that cannot hold alone is absorbed, and a conjunct that always
   holds is absorbed. The two shapes are what the "what refutes it is the
   edge and not the construction" twins below are proved with. *)
Lemma orb_absorb : forall a b : bool, (b = true -> a = true) -> orb a b = a.
Proof. intros [ | ] [ | ] H; try reflexivity. discriminate (H eq_refl). Qed.

Lemma andb_absorb : forall a b : bool, (a = true -> b = true) -> andb a b = a.
Proof. intros [ | ] [ | ] H; try reflexivity. discriminate (H eq_refl). Qed.

Fixpoint all_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => true
  | cons x r => andb (p x) (all_of p r)
  end.

Fixpoint any_of {A : Type} (p : A -> bool) (l : list A) : bool :=
  match l with
  | nil => false
  | cons x r => orb (p x) (any_of p r)
  end.

Fixpoint count_of {A : Type} (l : list A) : nat :=
  match l with nil => 0 | cons _ r => S (count_of r) end.

Fixpoint map_over {A B : Type} (f : A -> B) (l : list A) : list B :=
  match l with nil => nil | cons x r => cons (f x) (map_over f r) end.

Fixpoint filter_of {A : Type} (p : A -> bool) (l : list A) : list A :=
  match l with
  | nil => nil
  | cons x r => if p x then cons x (filter_of p r) else filter_of p r
  end.

(* 0 through n-1, in that order: the index set the plan generators range
   over. *)
Fixpoint upto (n : nat) : list nat :=
  match n with
  | 0 => nil
  | S k => app (upto k) (cons k nil)
  end.

(* Delete the member at n: an edge the plan carries and the installer does
   not. *)
Fixpoint drop_at {A : Type} (n : nat) (l : list A) : list A :=
  match n, l with
  | 0, cons _ r => r
  | 0, nil => nil
  | S k, cons a r => cons a (drop_at k r)
  | S _, nil => nil
  end.

(* Insert x at n: an edge the installer carries and the plan does not. *)
Fixpoint insert_at {A : Type} (n : nat) (x : A) (l : list A) : list A :=
  match n, l with
  | 0, _ => cons x l
  | S k, cons a r => cons a (insert_at k x r)
  | S _, nil => cons x nil
  end.

Lemma all_of_mono :
  forall (A : Type) (p q : A -> bool) (l : list A),
    (forall x : A, p x = true -> q x = true) ->
    all_of p l = true -> all_of q l = true.
Proof.
  intros A p q l Himp. induction l as [ | x r IH ]; intros H.
  - reflexivity.
  - simpl in H. destruct (andb_split (p x) (all_of p r) H) as [ Hx Hr ].
    simpl. apply andb_join.
    + exact (Himp x Hx).
    + exact (IH Hr).
Qed.

Lemma all_of_of_forall :
  forall (A : Type) (q : A -> bool) (l : list A),
    (forall x : A, q x = true) -> all_of q l = true.
Proof.
  intros A q l H. induction l as [ | x r IH ].
  - reflexivity.
  - simpl. rewrite (H x). exact IH.
Qed.

(* A universal check over a list, read back at one member. This is what
   makes a finite check over an enumerated domain the property rather than
   a test of it, and it is used at three domains below: the 32 codepoints,
   the plan's edges, and the core roster. *)
Lemma all_of_member :
  forall (A : Type) (eqb : A -> A -> bool),
    (forall a b : A, eqb a b = true -> a = b) ->
    forall (q : A -> bool) (l : list A) (x : A),
      all_of q l = true -> any_of (eqb x) l = true -> q x = true.
Proof.
  intros A eqb sound q l. induction l as [ | y r IH ]; intros x Hall Hany.
  - discriminate Hany.
  - simpl in Hall. destruct (andb_split (q y) (all_of q r) Hall) as [ Hy Hr ].
    simpl in Hany. destruct (orb_split _ _ Hany) as [ He | Hrest ].
    + rewrite (sound x y He). exact Hy.
    + exact (IH x Hr Hrest).
Qed.

Lemma any_of_and_all_of :
  forall (A : Type) (p q : A -> bool) (l : list A),
    all_of q l = true -> any_of p l = true ->
    any_of (fun x => andb (q x) (p x)) l = true.
Proof.
  intros A p q l. induction l as [ | x r IH ]; intros Hall Hany.
  - discriminate Hany.
  - simpl in Hall. destruct (andb_split (q x) (all_of q r) Hall) as [ Hq Hr ].
    simpl in Hany. simpl. destruct (orb_split _ _ Hany) as [ Hp | Hrest ].
    + rewrite Hq. rewrite Hp. reflexivity.
    + rewrite (IH Hr Hrest). apply orb_true_right.
Qed.

(* =========================================================================
   The permission field: R-15-007b's 5-bit enumerated lattice, total over
   its 32 codepoints. The width and the totality are the design's; which
   set each codepoint names is the freeze's and is a field (reading 4).
   ========================================================================= *)

Inductive Perm : Type := Bits (b4 b3 b2 b1 b0 : bool).

Definition perm_eqb (p q : Perm) : bool :=
  match p, q with
  | Bits a4 a3 a2 a1 a0, Bits c4 c3 c2 c1 c0 =>
      andb (bool_eqb a4 c4)
      (andb (bool_eqb a3 c3)
      (andb (bool_eqb a2 c2)
      (andb (bool_eqb a1 c1) (bool_eqb a0 c0))))
  end.

Lemma perm_eqb_refl : forall p : Perm, perm_eqb p p = true.
Proof.
  intros [ b4 b3 b2 b1 b0 ].
  destruct b4; destruct b3; destruct b2; destruct b1; destruct b0; reflexivity.
Qed.

Lemma perm_eqb_sound : forall p q : Perm, perm_eqb p q = true -> p = q.
Proof.
  intros [ a4 a3 a2 a1 a0 ] [ c4 c3 c2 c1 c0 ] H. simpl in H.
  destruct (andb_split _ _ H) as [ H4 R4 ].
  destruct (andb_split _ _ R4) as [ H3 R3 ].
  destruct (andb_split _ _ R3) as [ H2 R2 ].
  destruct (andb_split _ _ R2) as [ H1 H0 ].
  rewrite (bool_eqb_sound a4 c4 H4). rewrite (bool_eqb_sound a3 c3 H3).
  rewrite (bool_eqb_sound a2 c2 H2). rewrite (bool_eqb_sound a1 c1 H1).
  rewrite (bool_eqb_sound a0 c0 H0). reflexivity.
Qed.

(* The enumeration, generated over the field's own bits rather than written
   out, so its size is a consequence of the width R-15-007b fixes. *)
Definition pair_of {A : Type} (f : bool -> A) : list A :=
  cons (f false) (cons (f true) nil).

Definition join_two {A : Type} (f : bool -> list A) : list A :=
  app (f false) (f true).

Definition all_perms : list Perm :=
  join_two (fun b4 => join_two (fun b3 => join_two (fun b2 => join_two (fun b1 =>
    pair_of (fun b0 => Bits b4 b3 b2 b1 b0))))).

Definition in_list (p : Perm) (l : list Perm) : bool := any_of (perm_eqb p) l.

(* R-15-007b's own figure, computed rather than claimed. *)
Example the_permission_field_has_thirty_two_codepoints :
  count_of all_perms = 32 := eq_refl.

Theorem every_codepoint_is_enumerated : forall p : Perm, in_list p all_perms = true.
Proof.
  intros [ b4 b3 b2 b1 b0 ].
  destruct b4; destruct b3; destruct b2; destruct b1; destruct b0; reflexivity.
Qed.

(* The three permissions this file's obligations quantify over. R-15-007l
   names the first two and R-15-003 the third; the rest of the lattice is
   the freeze's and no field here stands for it. *)
Record Authority : Type := {
  permit_store : bool;
  permit_execute : bool;
  access_system_registers : bool
}.

(* -------------------------------------------------------------------------
   The machine: everything the register leaves to composition or to the
   profile freeze. Fields rather than Parameters, because a top-level
   Parameter prints as an assumption and fails the R-05-163 gate.
   ------------------------------------------------------------------------- *)

Record Machine : Type := {

  (* --- R-15-007b's decode, enumerated at freeze time (gap a) ------------- *)

  decode : Perm -> Authority;

  (* --- the principals of the composed graph (R-07-025) ------------------ *)

  Node : Type;
  node_eqb : Node -> Node -> bool;
  node_eqb_refl : forall a : Node, node_eqb a a = true;
  node_eqb_sound : forall a b : Node, node_eqb a b = true -> a = b;

  kernel : Node;      (* R-07-020: the sole resident code               *)
  firmware : Node;    (* R-07-019: the boot/M-mode firmware             *)

  (* --- R-08-011's slot plan: the regions a capability is bounded to ----- *)

  Region : Type;
  region_eqb : Region -> Region -> bool;
  region_eqb_refl : forall a : Region, region_eqb a a = true;
  region_eqb_sound : forall a b : Region, region_eqb a b = true -> a = b;

  (* --- R-07-005's static partition of memory among the cores ------------ *)

  Core : Type;
  cores : list Core;
  partition_of : Core -> Region -> bool
}.

(* =========================================================================
   The composed capability graph (R-07-025, R-08-011), and the equality the
   refinement below is stated over.
   ========================================================================= *)

Record Edge (m : Machine) : Type := {
  edge_holder : m.(Node);
  edge_region : m.(Region);
  edge_perm : Perm
}.

Arguments edge_holder {m} _.
Arguments edge_region {m} _.
Arguments edge_perm {m} _.

Definition edge_eqb (m : Machine) (e f : Edge m) : bool :=
  andb (m.(node_eqb) (edge_holder e) (edge_holder f))
  (andb (m.(region_eqb) (edge_region e) (edge_region f))
        (perm_eqb (edge_perm e) (edge_perm f))).

Lemma edge_eqb_refl : forall (m : Machine) (e : Edge m), edge_eqb m e e = true.
Proof.
  intros m [ h r p ]. unfold edge_eqb. simpl.
  rewrite (m.(node_eqb_refl) h). rewrite (m.(region_eqb_refl) r).
  rewrite (perm_eqb_refl p). reflexivity.
Qed.

Lemma edge_eqb_sound :
  forall (m : Machine) (e f : Edge m), edge_eqb m e f = true -> e = f.
Proof.
  intros m [ h1 r1 p1 ] [ h2 r2 p2 ] H. unfold edge_eqb in H. simpl in H.
  destruct (andb_split _ _ H) as [ Hh Hrest ].
  destruct (andb_split _ _ Hrest) as [ Hr Hp ].
  rewrite (m.(node_eqb_sound) h1 h2 Hh).
  rewrite (m.(region_eqb_sound) r1 r2 Hr).
  rewrite (perm_eqb_sound p1 p2 Hp). reflexivity.
Qed.

Definition Graph (m : Machine) : Type := list (Edge m).

Definition holds (m : Machine) (e : Edge m) (g : Graph m) : bool :=
  any_of (edge_eqb m e) g.

Definition edge_authority (m : Machine) (e : Edge m) : Authority :=
  m.(decode) (edge_perm e).

Lemma every_member_holds :
  forall (m : Machine) (g : Graph m), all_of (fun e => holds m e g) g = true.
Proof.
  intros m g. induction g as [ | x r IH ].
  - reflexivity.
  - simpl. apply andb_join.
    + unfold holds. simpl. rewrite (edge_eqb_refl m x). reflexivity.
    + apply (all_of_mono (Edge m) (fun e => holds m e r)
               (fun e => holds m e (cons x r)) r).
      * intros e He. unfold holds in He. unfold holds. simpl.
        rewrite He. destruct (edge_eqb m e x); reflexivity.
      * exact IH.
Qed.

(* Two plans agree where every edge either carries in both or in neither.
   Stated over the concatenation so the check is symmetric, which is what
   makes it a comparison rather than an inclusion. *)
Definition graphs_agree (m : Machine) (g h : Graph m) : bool :=
  all_of (fun e => bool_eqb (holds m e g) (holds m e h)) (app g h).

(* =========================================================================
   R-14-002 and R-15-007l: W^X at the permission encoding, and the
   derivation-forest check kept beside it as the redundant confirmation
   R-14-002's own criterion names.
   ========================================================================= *)

Definition WxAtTheEncoding (d : Perm -> Authority) : Prop :=
  forall p : Perm, andb (permit_store (d p)) (permit_execute (d p)) = false.

(* R-14-002's criterion: the machine-checked part is a finite check over the
   32 codepoints rather than an enumeration of the composed distribution. *)
Definition wx_check (d : Perm -> Authority) : bool :=
  all_of (fun p => negb (andb (permit_store (d p)) (permit_execute (d p))))
         all_perms.

(* W1. The file's load-bearing theorem for section 14: the finite check is
   sound *and* complete for the quantified statement, so R-14-002's *machine
   -checked part* is the property itself and not an approximation of it.
   Completeness is what a soundness-only reading would leave out, and it is
   the half that says a passing check has missed nothing. *)
Theorem the_finite_check_decides_wx :
  forall d : Perm -> Authority, wx_check d = true <-> WxAtTheEncoding d.
Proof.
  intros d. split.
  - intros H p.
    assert (Hq := all_of_member Perm perm_eqb perm_eqb_sound
                    (fun q => negb (andb (permit_store (d q))
                                         (permit_execute (d q))))
                    all_perms p H (every_codepoint_is_enumerated p)).
    cbv beta in Hq. exact (negb_true _ Hq).
  - intros H. apply all_of_of_forall. intros p. rewrite (H p). reflexivity.
Qed.

(* The redundant confirmation, over the composed distribution rather than
   over the encoding (R-14-002's second sentence). *)
Definition no_wx_edge (m : Machine) (g : Graph m) : bool :=
  all_of (fun e => negb (andb (permit_store (edge_authority m e))
                              (permit_execute (edge_authority m e)))) g.

Definition WxOverTheDistribution (m : Machine) (g : Graph m) : Prop :=
  forall e : Edge m, holds m e g = true ->
    andb (permit_store (edge_authority m e))
         (permit_execute (edge_authority m e)) = false.

(* W2. The encoding carries every distribution, whatever the plan and
   whatever a capability's provenance, which is R-15-007l's *holding for
   every capability in every reachable state*. The confirmation is therefore
   redundant in the strict sense: it follows. *)
Theorem the_encoding_carries_every_distribution :
  forall (m : Machine) (g : Graph m),
    WxAtTheEncoding m.(decode) -> WxOverTheDistribution m g.
Proof.
  intros m g Hwx e _. exact (Hwx (edge_perm e)).
Qed.

(* W2a. And it needs no refinement to reach the booted machine: the
   statement quantifies over every edge, so the installed distribution is
   covered whatever the installer did. This is the asymmetry with R-07-023
   below, whose build-time check reaches the machine only through R-07-028. *)
Definition InstalledEdges (m : Machine) : Type := Edge m -> bool.

Theorem the_encoding_reaches_the_booted_machine :
  forall (m : Machine) (ins : InstalledEdges m),
    WxAtTheEncoding m.(decode) ->
    forall e : Edge m, ins e = true ->
      andb (permit_store (edge_authority m e))
           (permit_execute (edge_authority m e)) = false.
Proof.
  intros m ins Hwx e _. exact (Hwx (edge_perm e)).
Qed.

(* =========================================================================
   R-14-003: the promotion primitive an NX bit must be paired with never
   exists, which is what *the whole of W^X rather than the necessary half*
   asks for.
   ========================================================================= *)

Definition Promotion (m : Machine) : Type := Edge m -> Edge m.

Definition PromotesToWritableExecute (m : Machine) (f : Promotion m) : Prop :=
  exists e : Edge m,
    permit_store (edge_authority m e) = true
    /\ m.(region_eqb) (edge_region (f e)) (edge_region e) = true
    /\ permit_store (edge_authority m (f e)) = true
    /\ permit_execute (edge_authority m (f e)) = true.

(* W3 (R-14-003). *)
Theorem no_promotion_primitive_exists :
  forall (m : Machine) (f : Promotion m),
    WxAtTheEncoding m.(decode) -> ~ PromotesToWritableExecute m f.
Proof.
  intros m f Hwx [ e [ _ [ _ [ Hs Hx ] ] ] ].
  assert (H := Hwx (edge_perm (f e))).
  unfold edge_authority in Hs. unfold edge_authority in Hx.
  rewrite Hs in H. rewrite Hx in H. discriminate H.
Qed.

(* A promotion that re-stamps a capability with a target codepoint: the
   writable-to-executable primitive itself. It is refuted above at every
   machine whose encoding excludes W+X and exhibited below at one whose
   encoding does not, so what refuses it is the encoding and not the
   construction. *)
Definition promoting (m : Machine) (target : Perm) : Promotion m :=
  fun e => Build_Edge m (edge_holder e) (edge_region e) target.

(* =========================================================================
   R-07-024 and R-07-020: the resident-code inventory. The five names are
   R-07-019's, R-07-020's and R-07-024's own and this is not an inventory
   (gap d).
   ========================================================================= *)

Inductive Resident : Type :=
| Microkernel              (* R-07-020: the sole resident code            *)
| FirmwareHandler          (* R-07-019: the SMM-analog resident handler   *)
| HypervisorTenant         (* R-07-024                                    *)
| PrivilegedDaemon         (* R-07-024                                    *)
| PowerManagementFirmware. (* R-07-024                                    *)

Definition resident_eqb (a b : Resident) : bool :=
  match a, b with
  | Microkernel, Microkernel => true
  | FirmwareHandler, FirmwareHandler => true
  | HypervisorTenant, HypervisorTenant => true
  | PrivilegedDaemon, PrivilegedDaemon => true
  | PowerManagementFirmware, PowerManagementFirmware => true
  | _, _ => false
  end.

Lemma resident_eqb_sound : forall a b : Resident, resident_eqb a b = true -> a = b.
Proof.
  intros [ | | | | ] [ | | | | ] H; try discriminate H; reflexivity.
Qed.

Definition all_residents : list Resident :=
  cons Microkernel (cons FirmwareHandler (cons HypervisorTenant
  (cons PrivilegedDaemon (cons PowerManagementFirmware nil)))).

Definition occurs_resident (r : Resident) (l : list Resident) : bool :=
  any_of (resident_eqb r) l.

Definition spec_inventory : list Resident := cons Microkernel nil.

(* R-07-024's criterion is the count and R-07-020's is the occupant, and
   they are separate clauses because neither carries the other. *)
Definition InventoryHasOneEntry (l : list Resident) : Prop := count_of l = 1.

Definition TheKernelIsResident (l : list Resident) : Prop :=
  occurs_resident Microkernel l = true.

Definition inventory_ok (l : list Resident) : bool :=
  andb (Nat.eqb (count_of l) 1) (occurs_resident Microkernel l).

Example the_specification_inventory_is_admitted :
  inventory_ok spec_inventory = true := eq_refl.

Theorem the_specification_inventory_has_one_entry :
  InventoryHasOneEntry spec_inventory /\ TheKernelIsResident spec_inventory.
Proof. split; reflexivity. Qed.

(* The intrusion family, generated over the register's own residency names
   rather than authored: one weakening per kind other than the microkernel. *)
Definition intruded (r : Resident) : list Resident :=
  cons Microkernel (cons r nil).

Definition second_residents : list Resident :=
  filter_of (fun r => negb (resident_eqb r Microkernel)) all_residents.

Definition intrusions : list (list Resident) :=
  map_over intruded second_residents.

Example the_intrusion_family_is_the_four_other_kinds :
  second_residents = cons FirmwareHandler (cons HypervisorTenant
    (cons PrivilegedDaemon (cons PowerManagementFirmware nil))) := eq_refl.

Example the_intrusion_family_size : count_of intrusions = 4 := eq_refl.

Example every_intrusion_is_refused :
  all_of (fun l => negb (inventory_ok l)) intrusions = true := eq_refl.

(* The same content as a quantifier over the kind rather than an
   enumeration, so the family is refused for a reason rather than by a
   computation over the four members it happens to have. *)
Theorem no_second_resident_is_admitted :
  forall r : Resident, ~ InventoryHasOneEntry (intruded r).
Proof.
  intros r H. unfold InventoryHasOneEntry in H. unfold intruded in H.
  simpl in H. discriminate H.
Qed.

(* And the two clauses are independent: an inventory of one entry that is
   not the kernel passes R-07-024's count and fails R-07-020's occupant, so
   the count alone does not carry the second. *)
Theorem the_count_is_not_the_occupant :
  InventoryHasOneEntry (cons HypervisorTenant nil)
  /\ ~ TheKernelIsResident (cons HypervisorTenant nil).
Proof. split; [ reflexivity | intros H; discriminate H ]. Qed.

(* =========================================================================
   What the firmware installs. Three components, and reading 2 says why
   those three; there is no region-table component, which is reading 7's
   structural half of R-15-075.
   ========================================================================= *)

Record Installed (m : Machine) : Type := {
  ins_holds : Edge m -> bool;                  (* R-07-028's distribution   *)
  ins_resident : list Resident;                (* R-07-024's inventory      *)
  ins_roots : m.(Core) -> Edge m -> bool       (* R-07-019's per-core roots *)
}.

Arguments ins_holds {m} _ _.
Arguments ins_resident {m} _.
Arguments ins_roots {m} _ _ _.

(* Reading 3: a relation from the composed plan and a post-state, so an
   alternative construction is exhibitable rather than merely different. *)
Definition Installer (m : Machine) : Type := Graph m -> Installed m -> Prop.

(* -------------------------------------------------------------------------
   The obligations, each stated of an arbitrary installer.
   ------------------------------------------------------------------------- *)

(* R-07-028: the installed distribution is the composed one edge for edge.
   One clause carries both directions, being an equality of the two
   membership functions at every edge rather than a pair of inclusions. *)
Definition InstallsExactly (m : Machine) (I : Installer m) : Prop :=
  forall (g : Graph m) (st : Installed m), I g st ->
    forall e : Edge m, ins_holds st e = holds m e g.

(* The same obligation at one plan, which is what an alternative
   construction tailored to a plan is held against. *)
Definition InstallsExactlyOf (m : Machine) (g : Graph m) (I : Installer m) : Prop :=
  forall st : Installed m, I g st ->
    forall e : Edge m, ins_holds st e = holds m e g.

Lemma exact_everywhere_is_exact_at :
  forall (m : Machine) (I : Installer m) (g : Graph m),
    InstallsExactly m I -> InstallsExactlyOf m g I.
Proof. intros m I g H st Hst e. exact (H g st Hst e). Qed.

(* R-07-019 with R-07-006: no root is derived outside its core's partition.
   R-07-006's criterion is *the root capability's bounds are the
   partition's*. *)
Definition RootsAreBounded (m : Machine) (st : Installed m) : Prop :=
  forall (c : m.(Core)) (e : Edge m),
    ins_roots st c e = true -> m.(partition_of) c (edge_region e) = true.

(* R-07-019's other half, and the weakest thing the entries fix (gap c):
   every core the composition rosters has a root among the plan's edges. *)
Definition EveryCoreIsRooted (m : Machine) (g : Graph m) (st : Installed m) : Prop :=
  all_of (fun c => any_of (fun e => ins_roots st c e) g) m.(cores) = true.

(* R-07-019's quiescence, in both halves: the firmware holds no authority in
   what it installed, and no SMM-analog handler is resident. *)
Definition Quiescent (m : Machine) (st : Installed m) : Prop :=
  (forall e : Edge m, ins_holds st e = true ->
     m.(node_eqb) (edge_holder e) m.(firmware) = false)
  /\ occurs_resident FirmwareHandler (ins_resident st) = false.

(* R-07-023, over the booted machine: no compartment holds the
   system-register permission, which is R-07-020's *sole resident code
   holding the system-register permission* read at the installed state. *)
Definition OnlyTheKernelHoldsSystemRegisters (m : Machine) (st : Installed m) : Prop :=
  forall e : Edge m, ins_holds st e = true ->
    access_system_registers (edge_authority m e) = true ->
    m.(node_eqb) (edge_holder e) m.(kernel) = true.

(* -------------------------------------------------------------------------
   The composition-time checks (R-07-025), stated as booleans over the plan
   so a composition decides them.
   ------------------------------------------------------------------------- *)

Definition system_register_edges_are_the_kernels (m : Machine) (g : Graph m) : bool :=
  all_of (fun e => if access_system_registers (edge_authority m e)
                   then m.(node_eqb) (edge_holder e) m.(kernel)
                   else true) g.

Definition plan_names_no_firmware_edge (m : Machine) (g : Graph m) : bool :=
  all_of (fun e => negb (m.(node_eqb) (edge_holder e) m.(firmware))) g.

Definition plan_roots_every_core (m : Machine) (g : Graph m) : bool :=
  all_of (fun c => any_of (fun e => m.(partition_of) c (edge_region e)) g)
         m.(cores).

(* -------------------------------------------------------------------------
   The specification: the conjunction of the firmware's per-component write
   obligations, and nothing else.
   ------------------------------------------------------------------------- *)

Definition Handoff (m : Machine) : Installer m := fun g st =>
  (forall e : Edge m, ins_holds st e = holds m e g)
  /\ (forall (c : m.(Core)) (e : Edge m), ins_roots st c e = true ->
        andb (holds m e g) (m.(partition_of) c (edge_region e)) = true)
  /\ all_of (fun c => any_of (fun e => ins_roots st c e) g) m.(cores) = true
  /\ ins_resident st = spec_inventory.

(* =========================================================================
   F1 through F6: what the handoff discharges.
   ========================================================================= *)

(* F1 (R-07-028). *)
Theorem the_handoff_installs_exactly :
  forall m : Machine, InstallsExactly m (Handoff m).
Proof. intros m g st [ Hd _ ] e. exact (Hd e). Qed.

(* F2 (R-07-019, R-07-006). *)
Theorem the_handoff_roots_are_bounded :
  forall (m : Machine) (g : Graph m) (st : Installed m),
    Handoff m g st -> RootsAreBounded m st.
Proof.
  intros m g st [ _ [ Hr _ ] ] c e H.
  destruct (andb_split _ _ (Hr c e H)) as [ _ Hp ]. exact Hp.
Qed.

(* F3 (R-07-019). *)
Theorem the_handoff_roots_every_core :
  forall (m : Machine) (g : Graph m) (st : Installed m),
    Handoff m g st -> EveryCoreIsRooted m g st.
Proof. intros m g st [ _ [ _ [ Hc _ ] ] ]. exact Hc. Qed.

(* F4 (R-07-019, R-07-024). The quiescence *follows* from the refinement
   rather than being a further obligation: a firmware that installs exactly
   the plan holds nothing the plan does not name, so a plan naming no
   firmware edge leaves it with no authority at all. That is the entry's
   *then goes quiescent* read as a consequence of R-07-028. *)
Definition PlanNamesNoFirmwareEdge (m : Machine) (g : Graph m) : Prop :=
  forall e : Edge m, holds m e g = true ->
    m.(node_eqb) (edge_holder e) m.(firmware) = false.

Lemma the_boolean_firmware_check_is_sound :
  forall (m : Machine) (g : Graph m),
    plan_names_no_firmware_edge m g = true -> PlanNamesNoFirmwareEdge m g.
Proof.
  intros m g H e He.
  assert (Hq := all_of_member (Edge m) (edge_eqb m) (edge_eqb_sound m)
                  (fun x => negb (m.(node_eqb) (edge_holder x) m.(firmware)))
                  g e H He).
  cbv beta in Hq. exact (negb_true _ Hq).
Qed.

Theorem quiescence_follows_from_the_refinement :
  forall (m : Machine) (g : Graph m) (st : Installed m),
    Handoff m g st -> PlanNamesNoFirmwareEdge m g -> Quiescent m st.
Proof.
  intros m g st [ Hd [ _ [ _ Hi ] ] ] Hplan. split.
  - intros e He. apply Hplan. rewrite <- (Hd e). exact He.
  - rewrite Hi. reflexivity.
Qed.

(* F5 (R-07-025, R-07-028, R-07-023). The file's load-bearing theorem:
   R-07-028's Accept clause instantiated, *machine-checked at build time*
   joined by *machine-checked as installed*. What carries the composed
   graph's check to the booted machine is the initialisation refinement and
   nothing else, which reading 8 states and which the construction after it
   refutes. *)
Theorem the_build_time_check_becomes_an_installed_property :
  forall (m : Machine) (I : Installer m) (g : Graph m) (st : Installed m),
    InstallsExactly m I -> I g st ->
    system_register_edges_are_the_kernels m g = true ->
    OnlyTheKernelHoldsSystemRegisters m st.
Proof.
  intros m I g st Hexact Hstep Hcheck e He Hasr.
  assert (Hin : holds m e g = true).
  { rewrite <- (Hexact g st Hstep e). exact He. }
  assert (Hq := all_of_member (Edge m) (edge_eqb m) (edge_eqb_sound m)
                  (fun x => if access_system_registers (edge_authority m x)
                            then m.(node_eqb) (edge_holder x) m.(kernel)
                            else true)
                  g e Hcheck Hin).
  cbv beta in Hq. rewrite Hasr in Hq. exact Hq.
Qed.

(* F6 (R-14-002, R-15-007l, R-07-006). R-15-075's Accept says the three
   roles a locked-PMP backstop would serve each map onto a named CHERI
   mechanism. Two of the three are carried by results already proved here,
   composed rather than restated: immutable text and W^X is the encoding's,
   and the per-core physical-partition bound is the root bound's. The third,
   crown-jewel secret fencing, is the crypto core's own boundary and is not
   this file's to state. *)
Theorem the_two_pmp_roles_this_file_carries_are_carried :
  forall (m : Machine) (g : Graph m) (st : Installed m),
    WxAtTheEncoding m.(decode) -> Handoff m g st ->
    (forall e : Edge m, ins_holds st e = true ->
       andb (permit_store (edge_authority m e))
            (permit_execute (edge_authority m e)) = false)
    /\ RootsAreBounded m st.
Proof.
  intros m g st Hwx Hh. split.
  - exact (the_encoding_reaches_the_booted_machine m (ins_holds st) Hwx).
  - exact (the_handoff_roots_are_bounded m g st Hh).
Qed.

(* =========================================================================
   Inhabitation (R-05-165's unsatisfiable-premise and uninhabited-domain
   modes). The handoff is satisfiable at every machine whose plan roots
   every core, so no theorem above is proved from an empty antecedent, and
   the side condition is the plan's rather than the firmware's, which is
   what gap c reports.
   ========================================================================= *)

Definition canonical (m : Machine) (g : Graph m) : Installed m :=
  Build_Installed m
    (fun e => holds m e g)
    spec_inventory
    (fun c e => andb (holds m e g) (m.(partition_of) c (edge_region e))).

Theorem the_handoff_is_satisfiable :
  forall (m : Machine) (g : Graph m),
    plan_roots_every_core m g = true -> Handoff m g (canonical m g).
Proof.
  intros m g Hroot. split; [ | split; [ | split ] ].
  - intros e. reflexivity.
  - intros c e H. exact H.
  - apply (all_of_mono m.(Core)
            (fun c => any_of (fun e => m.(partition_of) c (edge_region e)) g)
            (fun c => any_of (fun e => ins_roots (canonical m g) c e) g)
            m.(cores)).
    + intros c Hc.
      exact (any_of_and_all_of (Edge m)
               (fun e => m.(partition_of) c (edge_region e))
               (fun e => holds m e g) g (every_member_holds m g) Hc).
    + exact Hroot.
  - reflexivity.
Qed.

(* And the plan side condition is not idle: a plan that roots no core admits
   no handoff at all, which is R-07-019's obligation landing on the
   composition rather than on the firmware. *)
Theorem an_unrooted_plan_admits_no_handoff :
  forall (m : Machine) (g : Graph m) (st : Installed m),
    Handoff m g st -> EveryCoreIsRooted m g st.
Proof. exact the_handoff_roots_every_core. Qed.

(* =========================================================================
   R-07-018 and R-07-023: permission decides, and mode cannot, because
   there is one mode.
   ========================================================================= *)

(* R-07-018's Accept, by construction: there is no S-mode and no U-mode. *)
Inductive Mode : Type := MachineMode.

Theorem the_platform_has_one_mode : forall a b : Mode, a = b.
Proof. intros [ ] [ ]. reflexivity. Qed.

Definition Gate (m : Machine) : Type := Perm -> Mode -> bool.

Definition spec_gate (m : Machine) : Gate m :=
  fun p _ => access_system_registers (m.(decode) p).

Definition DecidesOnThePermission (m : Machine) (gt : Gate m) : Prop :=
  forall (p : Perm) (md : Mode),
    gt p md = access_system_registers (m.(decode) p).

(* F7 (R-07-018, R-15-003). *)
Theorem the_specification_gate_decides_on_the_permission :
  forall m : Machine, DecidesOnThePermission m (spec_gate m).
Proof. intros m p md. reflexivity. Qed.

(* The alternative construction R-07-023 exists to exclude: a gate that
   consults the mode. *)
Definition mode_gate (m : Machine) : Gate m :=
  fun _ md => match md with MachineMode => true end.

(* F8 (R-07-023). The refutation is not that the mode gate answers
   differently: it is that it answers the same to everything. A mode check
   separates no two capabilities and no two modes, so *privilege escalation
   has no ring to target* is a property of this mode type rather than a
   claim about an attacker. *)
Theorem a_mode_check_separates_nothing :
  forall (m : Machine) (p q : Perm) (md1 md2 : Mode),
    mode_gate m p md1 = mode_gate m q md2.
Proof. intros m p q [ ] [ ]. reflexivity. Qed.

(* And the permission does separate: it is refuted as a gate exactly where
   some codepoint lacks the permission, so a decode naming the permission
   nowhere would make the two agree. That machine is exhibited below. *)
Theorem the_permission_gate_separates_where_the_decode_does :
  forall (m : Machine) (p : Perm),
    access_system_registers (m.(decode) p) = false ->
    ~ DecidesOnThePermission m (mode_gate m).
Proof.
  intros m p Hp H. assert (Hq := H p MachineMode).
  unfold mode_gate in Hq. rewrite Hp in Hq. discriminate Hq.
Qed.

(* =========================================================================
   R-15-075: no region register. Reading 7's structural half is the shape of
   the decision, which carries no region-table argument, and of the Installed
   record, which carries no region-table component. What is stated here is
   the consequence a table would have if one existed.
   ========================================================================= *)

Definition authorizes (m : Machine) (e : Edge m) (r : m.(Region)) : bool :=
  m.(region_eqb) (edge_region e) r.

Definition Decision (m : Machine) : Type := Edge m -> m.(Region) -> bool.

Definition spec_decision (m : Machine) : Decision m := authorizes m.

Definition DecidesOnTheCapabilityAlone (m : Machine) (d : Decision m) : Prop :=
  forall (e : Edge m) (r : m.(Region)), d e r = authorizes m e r.

Definition region_gated (m : Machine) (table : m.(Region) -> bool) : Decision m :=
  fun e r => andb (authorizes m e r) (table r).

(* F9 (R-15-075). *)
Theorem the_specification_decides_on_the_capability_alone :
  forall m : Machine, DecidesOnTheCapabilityAlone m (spec_decision m).
Proof. intros m e r. reflexivity. Qed.

(* F9a (R-15-075's *strict subset*, made checkable): a region table can only
   subtract. It grants nothing the capability does not already grant, which
   is why PMP is redundant surface rather than a second authority; and it is
   still a second decision to get right, which is why it is refuted as one. *)
Theorem a_region_table_only_subtracts :
  forall (m : Machine) (table : m.(Region) -> bool) (e : Edge m) (r : m.(Region)),
    region_gated m table e r = true -> authorizes m e r = true.
Proof.
  intros m table e r H. destruct (andb_split _ _ H) as [ Ha _ ]. exact Ha.
Qed.

(* And the subtraction is what refutes it, not the shape of the
   construction: the same relation with a table that refuses nothing decides
   on the capability alone. *)
Theorem the_region_table_needs_to_refuse :
  forall m : Machine,
    DecidesOnTheCapabilityAlone m (region_gated m (fun _ => true)).
Proof.
  intros m e r. unfold region_gated. apply andb_absorb. intros _. reflexivity.
Qed.

(* =========================================================================
   R-05-091: the no-ambient-state obligation over the firmware's statically
   planned state, carried as an ordinary property because the firmware is
   outside the admitted set and does not inherit the type-level rule. What
   is here is the obligation and not the Tier-0 proof that discharges it
   (gap e).
   ========================================================================= *)

Definition WorkingSet (m : Machine) : Type := Edge m -> bool.

Definition spec_working (m : Machine) (g : Graph m) : WorkingSet m :=
  fun e => holds m e g.

(* R-05-086's *no hidden singletons*, at the boundary R-05-091 puts it: every
   authority the firmware exercises is one the plan already fixed. *)
Definition NoAmbientAuthority (m : Machine) (g : Graph m) (w : WorkingSet m) : Prop :=
  forall e : Edge m, w e = true -> holds m e g = true.

(* F10 (R-05-091, R-05-086, R-05-087). *)
Theorem the_firmware_holds_only_planned_authority :
  forall (m : Machine) (g : Graph m), NoAmbientAuthority m g (spec_working m g).
Proof. intros m g e H. exact H. Qed.

Definition singleton_working (m : Machine) (g : Graph m) (hidden : Edge m)
  : WorkingSet m := fun e => orb (holds m e g) (edge_eqb m e hidden).

(* The hidden singleton is what refutes it and not the construction's shape:
   the same relation with a planned edge satisfies the obligation. *)
Theorem the_singleton_needs_to_be_unplanned :
  forall (m : Machine) (g : Graph m) (planned : Edge m),
    holds m planned g = true ->
    NoAmbientAuthority m g (singleton_working m g planned).
Proof.
  intros m g planned Hp e H. unfold singleton_working in H.
  destruct (orb_split _ _ H) as [ Hh | He ].
  - exact Hh.
  - rewrite (edge_eqb_sound m e planned He). exact Hp.
Qed.

Theorem a_hidden_singleton_is_refuted :
  forall (m : Machine) (g : Graph m) (hidden : Edge m),
    holds m hidden g = false ->
    ~ NoAmbientAuthority m g (singleton_working m g hidden).
Proof.
  intros m g hidden Hh H.
  assert (Hw : singleton_working m g hidden hidden = true).
  { unfold singleton_working. rewrite (edge_eqb_refl m hidden).
    apply orb_true_right. }
  rewrite (H hidden Hw) in Hh. discriminate Hh.
Qed.

(* R-05-086's *no lazily-initialized statics*, at the same boundary: what the
   firmware holds is a function of the plan and not of when it is asked. *)
Definition Lazy (m : Machine) : Type := nat -> Graph m -> WorkingSet m.

Definition spec_lazy (m : Machine) : Lazy m := fun _ g => spec_working m g.

Definition DoesNotDependOnTheCall (m : Machine) (l : Lazy m) : Prop :=
  forall (i j : nat) (g : Graph m) (e : Edge m), l i g e = l j g e.

Theorem the_specification_is_not_lazily_initialized :
  forall m : Machine, DoesNotDependOnTheCall m (spec_lazy m).
Proof. intros m i j g e. reflexivity. Qed.

Definition lazily_initialized (m : Machine) : Lazy m :=
  fun i g e => match i with 0 => false | S _ => holds m e g end.

Theorem a_lazily_initialized_static_is_refuted :
  forall (m : Machine) (g : Graph m) (e : Edge m),
    holds m e g = true -> ~ DoesNotDependOnTheCall m (lazily_initialized m).
Proof.
  intros m g e He H. assert (Hq := H 0 1 g e).
  unfold lazily_initialized in Hq. rewrite He in Hq. discriminate Hq.
Qed.

(* =========================================================================
   Refutation witnesses over the installer (R-05-166). Each is an
   alternative construction the register's own sentence excludes; each is a
   complete and deterministic specification rather than an underspecified
   one, so what refutes it is the named defect and not a gap in its
   statement; and each is shown to satisfy the obligation it does not break.
   ========================================================================= *)

(* An installer that adds an edge the graph does not carry: the
   *machine-checked at build time* half holding and the *as installed* half
   failing, which is exactly the gap R-07-028 exists to close. *)
Definition adding_installer (m : Machine) (extra : Edge m) : Installer m :=
  fun g st => forall e : Edge m,
    ins_holds st e = orb (holds m e g) (edge_eqb m e extra).

Definition added_state (m : Machine) (g : Graph m) (extra : Edge m)
  : Installed m :=
  Build_Installed m
    (fun e => orb (holds m e g) (edge_eqb m e extra))
    spec_inventory
    (fun c e => andb (holds m e g) (m.(partition_of) c (edge_region e))).

Lemma the_adding_installer_is_satisfiable :
  forall (m : Machine) (g : Graph m) (extra : Edge m),
    adding_installer m extra g (added_state m g extra).
Proof. intros m g extra e. reflexivity. Qed.

Theorem an_added_edge_refutes_the_refinement :
  forall (m : Machine) (g : Graph m) (extra : Edge m),
    holds m extra g = false -> ~ InstallsExactlyOf m g (adding_installer m extra).
Proof.
  intros m g extra Hx H.
  assert (Hq := H (added_state m g extra)
                  (the_adding_installer_is_satisfiable m g extra) extra).
  unfold added_state in Hq. simpl in Hq.
  rewrite (edge_eqb_refl m extra) in Hq. rewrite Hx in Hq. discriminate Hq.
Qed.

(* The added edge is what refutes it and not the shape: adding an edge the
   plan already carries installs exactly. *)
Theorem adding_a_planned_edge_still_refines :
  forall (m : Machine) (g : Graph m) (planned : Edge m),
    holds m planned g = true -> InstallsExactlyOf m g (adding_installer m planned).
Proof.
  intros m g planned Hp st Hst e. rewrite (Hst e).
  apply orb_absorb. intros He.
  rewrite (edge_eqb_sound m e planned He). exact Hp.
Qed.

(* An installer that drops an edge the graph does carry: the composed
   topology under-installed rather than over-installed, which R-07-028's
   *exactly* refuses in the other direction. *)
Definition dropping_installer (m : Machine) (omitted : Edge m) : Installer m :=
  fun g st => forall e : Edge m,
    ins_holds st e = andb (holds m e g) (negb (edge_eqb m e omitted)).

Definition dropped_state (m : Machine) (g : Graph m) (omitted : Edge m)
  : Installed m :=
  Build_Installed m
    (fun e => andb (holds m e g) (negb (edge_eqb m e omitted)))
    spec_inventory
    (fun c e => andb (holds m e g) (m.(partition_of) c (edge_region e))).

Lemma the_dropping_installer_is_satisfiable :
  forall (m : Machine) (g : Graph m) (omitted : Edge m),
    dropping_installer m omitted g (dropped_state m g omitted).
Proof. intros m g omitted e. reflexivity. Qed.

Theorem a_dropped_edge_refutes_the_refinement :
  forall (m : Machine) (g : Graph m) (omitted : Edge m),
    holds m omitted g = true ->
    ~ InstallsExactlyOf m g (dropping_installer m omitted).
Proof.
  intros m g omitted Ho H.
  assert (Hq := H (dropped_state m g omitted)
                  (the_dropping_installer_is_satisfiable m g omitted) omitted).
  unfold dropped_state in Hq. simpl in Hq.
  rewrite (edge_eqb_refl m omitted) in Hq. rewrite Ho in Hq. discriminate Hq.
Qed.

Theorem dropping_an_unplanned_edge_still_refines :
  forall (m : Machine) (g : Graph m) (absent : Edge m),
    holds m absent g = false -> InstallsExactlyOf m g (dropping_installer m absent).
Proof.
  intros m g absent Ha st Hst e. rewrite (Hst e).
  apply andb_absorb. intros Hh.
  destruct (edge_eqb m e absent) eqn:F.
  - rewrite (edge_eqb_sound m e absent F) in Hh. rewrite Ha in Hh.
    discriminate Hh.
  - reflexivity.
Qed.

(* An installer that derives a root wider than its core's partition bound:
   R-07-006's criterion is that the root capability's bounds are the
   partition's, so a root outside it is not that root. *)
Definition wide_root_installer (m : Machine) (wide : Edge m) : Installer m :=
  fun g st =>
    (forall e : Edge m, ins_holds st e = holds m e g)
    /\ (forall (c : m.(Core)) (e : Edge m),
          ins_roots st c e =
            orb (andb (holds m e g) (m.(partition_of) c (edge_region e)))
                (edge_eqb m e wide))
    /\ ins_resident st = spec_inventory.

Definition wide_root_state (m : Machine) (g : Graph m) (wide : Edge m)
  : Installed m :=
  Build_Installed m
    (fun e => holds m e g)
    spec_inventory
    (fun c e => orb (andb (holds m e g) (m.(partition_of) c (edge_region e)))
                    (edge_eqb m e wide)).

Lemma the_wide_root_installer_is_satisfiable :
  forall (m : Machine) (g : Graph m) (wide : Edge m),
    wide_root_installer m wide g (wide_root_state m g wide).
Proof.
  intros m g wide. split; [ | split ].
  - intros e. reflexivity.
  - intros c e. reflexivity.
  - reflexivity.
Qed.

Theorem a_wide_root_refutes_the_partition_bound :
  forall (m : Machine) (g : Graph m) (wide : Edge m) (c : m.(Core)),
    m.(partition_of) c (edge_region wide) = false ->
    ~ RootsAreBounded m (wide_root_state m g wide).
Proof.
  intros m g wide c Hw H.
  assert (Hr : ins_roots (wide_root_state m g wide) c wide = true).
  { unfold wide_root_state. simpl. rewrite (edge_eqb_refl m wide).
    apply orb_true_right. }
  rewrite (H c wide Hr) in Hw. discriminate Hw.
Qed.

(* An installer that leaves a resident handler: R-07-019's *goes quiescent
   with no SMM-analog resident handler* and R-07-024's one-entry inventory
   both refused by one construction, which is why the inventory is stated
   beside the refinement rather than derived from it. *)
Definition resident_handler_installer (m : Machine) : Installer m :=
  fun g st =>
    (forall e : Edge m, ins_holds st e = holds m e g)
    /\ ins_resident st = cons Microkernel (cons FirmwareHandler nil).

Definition resident_handler_state (m : Machine) (g : Graph m) : Installed m :=
  Build_Installed m
    (fun e => holds m e g)
    (cons Microkernel (cons FirmwareHandler nil))
    (fun c e => andb (holds m e g) (m.(partition_of) c (edge_region e))).

Lemma the_resident_handler_installer_is_satisfiable :
  forall (m : Machine) (g : Graph m),
    resident_handler_installer m g (resident_handler_state m g).
Proof. intros m g. split; [ intros e; reflexivity | reflexivity ]. Qed.

Theorem a_resident_handler_refutes_quiescence :
  forall (m : Machine) (g : Graph m),
    ~ Quiescent m (resident_handler_state m g)
    /\ ~ InventoryHasOneEntry (ins_resident (resident_handler_state m g)).
Proof.
  intros m g. split.
  - intros [ _ H ]. unfold resident_handler_state in H. simpl in H.
    discriminate H.
  - intros H. unfold InventoryHasOneEntry in H.
    unfold resident_handler_state in H. simpl in H. discriminate H.
Qed.

(* And it installs exactly, so R-07-028's refinement does not carry
   R-07-019's quiescence either: a firmware may instantiate the composed
   graph perfectly and stay resident. *)
Theorem the_resident_handler_installer_still_refines :
  forall m : Machine, InstallsExactly m (resident_handler_installer m).
Proof. intros m g st [ Hd _ ] e. exact (Hd e). Qed.

(* =========================================================================
   The demo machines, for R-05-165's uninhabited-domain mode and for the
   witnesses no generic statement reaches. Three nodes exercise every case
   the obligations distinguish, two regions give two disjoint partitions,
   and two decodes exercise both sides of R-15-007l. Every value here is an
   arbitrary witness and carries no composition or freeze claim (gap f).
   ========================================================================= *)

Inductive DemoNode : Type := DemoKernel | DemoFirmware | DemoApp.

Definition demo_node_eqb (a b : DemoNode) : bool :=
  match a, b with
  | DemoKernel, DemoKernel => true
  | DemoFirmware, DemoFirmware => true
  | DemoApp, DemoApp => true
  | _, _ => false
  end.

Lemma demo_node_eqb_refl : forall a : DemoNode, demo_node_eqb a a = true.
Proof. intros [ | | ]; reflexivity. Qed.

Lemma demo_node_eqb_sound :
  forall a b : DemoNode, demo_node_eqb a b = true -> a = b.
Proof. intros [ | | ] [ | | ] H; try discriminate H; reflexivity. Qed.

(* Bit 2 is the access-system-registers permission, bit 1 execute, bit 0
   store; bits 4 and 3 are the rest of the field the freeze spends and this
   file does not name. *)
Definition p_store : Perm := Bits false false false false true.
Definition p_exec : Perm := Bits false false false true false.
Definition p_sysreg : Perm := Bits false false true false false.
Definition p_both : Perm := Bits false false false true true.

(* A decode excluding W+X: the codepoint holding both bits takes the
   lattice's bottom element, which is R-15-007b's own disposition of the
   unassigned residue. *)
Definition wx_free_decode : Perm -> Authority := fun p =>
  match p with
  | Bits _ _ a x s =>
      if andb x s
      then {| permit_store := false; permit_execute := false;
              access_system_registers := false |}
      else {| permit_store := s; permit_execute := x;
              access_system_registers := a |}
  end.

(* A decode that assigns the combination: the encoding R-15-007l refuses. *)
Definition leaky_decode : Perm -> Authority := fun p =>
  match p with
  | Bits _ _ a x s =>
      {| permit_store := s; permit_execute := x; access_system_registers := a |}
  end.

Example the_specification_decode_passes_the_finite_check :
  wx_check wx_free_decode = true := eq_refl.

Example a_store_and_execute_codepoint_fails_the_finite_check :
  wx_check leaky_decode = false := eq_refl.

Definition demo (d : Perm -> Authority) : Machine := {|
  decode := d;
  Node := DemoNode;
  node_eqb := demo_node_eqb;
  node_eqb_refl := demo_node_eqb_refl;
  node_eqb_sound := demo_node_eqb_sound;
  kernel := DemoKernel;
  firmware := DemoFirmware;
  Region := bool;
  region_eqb := bool_eqb;
  region_eqb_refl := bool_eqb_refl;
  region_eqb_sound := bool_eqb_sound;
  Core := bool;
  cores := cons true (cons false nil);
  partition_of := fun c r => if c then r else negb r
|}.

Definition demo_wx : Machine := demo wx_free_decode.
Definition demo_leaky : Machine := demo leaky_decode.

(* The composed plan: each core's kernel instance holds the system-register
   authority and the store authority over its own region, and one
   compartment holds execute authority over the first. *)
Definition demo_graph (d : Perm -> Authority) : Graph (demo d) :=
  cons (Build_Edge (demo d) DemoKernel true p_sysreg)
  (cons (Build_Edge (demo d) DemoKernel false p_sysreg)
  (cons (Build_Edge (demo d) DemoKernel true p_store)
  (cons (Build_Edge (demo d) DemoKernel false p_store)
  (cons (Build_Edge (demo d) DemoApp true p_exec) nil)))).

Definition rogue_edge (d : Perm -> Authority) : Edge (demo d) :=
  Build_Edge (demo d) DemoApp true p_sysreg.

Definition firmware_edge (d : Perm -> Authority) : Edge (demo d) :=
  Build_Edge (demo d) DemoFirmware true p_store.

Definition planned_edge (d : Perm -> Authority) : Edge (demo d) :=
  Build_Edge (demo d) DemoKernel true p_sysreg.

(* The plan passes every composition-time check R-07-025 owes. *)
Example the_demo_plan_passes_the_build_time_checks :
  system_register_edges_are_the_kernels demo_wx (demo_graph wx_free_decode) = true
  /\ plan_names_no_firmware_edge demo_wx (demo_graph wx_free_decode) = true
  /\ plan_roots_every_core demo_wx (demo_graph wx_free_decode) = true :=
  conj eq_refl (conj eq_refl eq_refl).

Example the_rogue_and_firmware_edges_are_unplanned :
  holds demo_wx (rogue_edge wx_free_decode) (demo_graph wx_free_decode) = false
  /\ holds demo_wx (firmware_edge wx_free_decode) (demo_graph wx_free_decode) = false
  /\ holds demo_wx (planned_edge wx_free_decode) (demo_graph wx_free_decode) = true :=
  conj eq_refl (conj eq_refl eq_refl).

(* The handoff is satisfiable at the demo, so nothing above is proved from a
   premise nothing satisfies. *)
Theorem the_demo_handoff_holds :
  Handoff demo_wx (demo_graph wx_free_decode)
    (canonical demo_wx (demo_graph wx_free_decode)).
Proof. apply the_handoff_is_satisfiable. reflexivity. Qed.

(* =========================================================================
   The generated weakenings over the specification's own plan (R-05-166).
   Two generators produce one weakening per position each, and the theorems
   above quantify over the edge rather than over an index, so the families
   below check that the plan's own five and six members are all refused
   while the generic statements say why.
   ========================================================================= *)

Definition plan_deletions (m : Machine) (g : Graph m) : list (Graph m) :=
  map_over (fun n => drop_at n g) (upto (count_of g)).

Definition plan_insertions (m : Machine) (g : Graph m) (extra : Edge m)
  : list (Graph m) :=
  map_over (fun n => insert_at n extra g) (upto (S (count_of g))).

Example the_deletion_family_size :
  count_of (plan_deletions demo_wx (demo_graph wx_free_decode)) = 5 := eq_refl.

Example the_insertion_family_size :
  count_of (plan_insertions demo_wx (demo_graph wx_free_decode)
              (rogue_edge wx_free_decode)) = 6 := eq_refl.

Example every_deletion_of_the_plan_is_a_different_distribution :
  all_of (fun w => negb (graphs_agree demo_wx (demo_graph wx_free_decode) w))
         (plan_deletions demo_wx (demo_graph wx_free_decode)) = true := eq_refl.

Example every_insertion_into_the_plan_is_a_different_distribution :
  all_of (fun w => negb (graphs_agree demo_wx (demo_graph wx_free_decode) w))
         (plan_insertions demo_wx (demo_graph wx_free_decode)
            (rogue_edge wx_free_decode)) = true := eq_refl.

(* And the plan agrees with itself, so the check above measures the
   weakening rather than the check. *)
Example the_plan_agrees_with_itself :
  graphs_agree demo_wx (demo_graph wx_free_decode) (demo_graph wx_free_decode)
  = true := eq_refl.

(* The generated families instantiated at the refinement: an added edge and
   a dropped edge are refused for the reason the generic theorems give. *)
Theorem the_rogue_edge_refutes_the_refinement :
  ~ InstallsExactlyOf demo_wx (demo_graph wx_free_decode)
      (adding_installer demo_wx (rogue_edge wx_free_decode)).
Proof. apply an_added_edge_refutes_the_refinement. reflexivity. Qed.

Theorem a_planned_edge_dropped_refutes_the_refinement :
  ~ InstallsExactlyOf demo_wx (demo_graph wx_free_decode)
      (dropping_installer demo_wx (planned_edge wx_free_decode)).
Proof. apply a_dropped_edge_refutes_the_refinement. reflexivity. Qed.

(* =========================================================================
   Reading 8, made checkable rather than asserted. Without R-07-028's
   refinement the build-time check says nothing about the machine that runs:
   the plan passes R-07-023's check and the installed state still hands a
   compartment the system-register permission.
   ========================================================================= *)

Theorem without_the_refinement_the_build_time_check_says_nothing :
  system_register_edges_are_the_kernels demo_wx (demo_graph wx_free_decode) = true
  /\ adding_installer demo_wx (rogue_edge wx_free_decode)
       (demo_graph wx_free_decode)
       (added_state demo_wx (demo_graph wx_free_decode) (rogue_edge wx_free_decode))
  /\ ~ OnlyTheKernelHoldsSystemRegisters demo_wx
         (added_state demo_wx (demo_graph wx_free_decode)
            (rogue_edge wx_free_decode)).
Proof.
  split; [ reflexivity | ].
  split; [ exact (the_adding_installer_is_satisfiable demo_wx
                    (demo_graph wx_free_decode) (rogue_edge wx_free_decode)) | ].
  intros H.
  assert (Hin : ins_holds (added_state demo_wx (demo_graph wx_free_decode)
                             (rogue_edge wx_free_decode))
                  (rogue_edge wx_free_decode) = true) by reflexivity.
  assert (Hasr : access_system_registers
                   (edge_authority demo_wx (rogue_edge wx_free_decode)) = true)
    by reflexivity.
  assert (Hk := H (rogue_edge wx_free_decode) Hin Hasr).
  discriminate Hk.
Qed.

(* And the same construction with the firmware's own edge: an installer that
   instantiates the composed graph and keeps its own authority is refused by
   quiescence rather than by the refinement, which is why R-07-019 states
   both. *)
Theorem a_firmware_that_keeps_its_own_edge_is_refuted :
  ~ Quiescent demo_wx
      (added_state demo_wx (demo_graph wx_free_decode)
         (firmware_edge wx_free_decode)).
Proof.
  intros [ H _ ].
  assert (Hin : ins_holds (added_state demo_wx (demo_graph wx_free_decode)
                             (firmware_edge wx_free_decode))
                  (firmware_edge wx_free_decode) = true) by reflexivity.
  assert (Hf := H (firmware_edge wx_free_decode) Hin). discriminate Hf.
Qed.

(* =========================================================================
   Reading 5, made checkable rather than asserted. R-14-002's derivation
   -forest check is strictly weaker than its encoding check: the composed
   distribution passes on a machine whose encoding assigns the
   Store-and-Execute combination, so the confirmation confirms and does not
   decide. This is what *retained as a redundant confirmation* means read
   from the other side.
   ========================================================================= *)

Theorem the_distribution_check_is_not_the_encoding_check :
  no_wx_edge demo_leaky (demo_graph leaky_decode) = true
  /\ ~ WxAtTheEncoding demo_leaky.(decode).
Proof.
  split; [ reflexivity | ].
  intros H. assert (Hp := H p_both). discriminate Hp.
Qed.

(* On the same machine the promotion primitive R-14-003 says never exists
   does exist, so the two entries stand or fall together at the encoding. *)
Theorem the_promotion_primitive_exists_where_the_encoding_admits_it :
  PromotesToWritableExecute demo_leaky (promoting demo_leaky p_both).
Proof.
  exists (Build_Edge demo_leaky DemoKernel true p_store).
  split; [ reflexivity | ].
  split; [ reflexivity | ].
  split; reflexivity.
Qed.

(* And on the specification's decode neither holds: the encoding check
   passes and no promotion is possible, so the pair is a pair rather than
   two statements about the same names. *)
Theorem the_specification_encoding_excludes_both :
  WxAtTheEncoding demo_wx.(decode)
  /\ forall f : Promotion demo_wx, ~ PromotesToWritableExecute demo_wx f.
Proof.
  assert (Hwx : WxAtTheEncoding demo_wx.(decode)).
  { destruct (the_finite_check_decides_wx demo_wx.(decode)) as [ Hsound _ ].
    apply Hsound. reflexivity. }
  split; [ exact Hwx | ].
  intros f. exact (no_promotion_primitive_exists demo_wx f Hwx).
Qed.

(* R-15-007p's corollary, which R-07-019's singular *root capability* is the
   other side of: once W+X is unrepresentable a root set covering both a
   store need and an execute need has two distinct members, so the
   multi-rootedness falls out rather than being built. *)
Theorem the_root_set_has_two_members_where_both_authorities_are_needed :
  forall (m : Machine) (rt : Edge m -> bool) (es ex : Edge m),
    WxAtTheEncoding m.(decode) ->
    rt es = true -> permit_store (edge_authority m es) = true ->
    rt ex = true -> permit_execute (edge_authority m ex) = true ->
    es <> ex.
Proof.
  intros m rt es ex Hwx _ Hs _ Hx Heq.
  assert (H := Hwx (edge_perm es)).
  unfold edge_authority in Hs. unfold edge_authority in Hx.
  rewrite Hs in H. rewrite Heq in H. rewrite Hx in H. discriminate H.
Qed.

(* =========================================================================
   The remaining refutations at the demo: the mode gate, the region table,
   the hidden singleton, the lazily initialized static, and the wide root.
   ========================================================================= *)

Theorem the_mode_gate_is_refuted :
  ~ DecidesOnThePermission demo_wx (mode_gate demo_wx).
Proof.
  apply (the_permission_gate_separates_where_the_decode_does demo_wx p_store).
  reflexivity.
Qed.

(* And the specification's gate does separate the two, so the mode gate's
   constancy is a defect rather than an agreement. *)
Theorem the_permission_separates_the_kernel_from_a_compartment :
  spec_gate demo_wx p_sysreg MachineMode = true
  /\ spec_gate demo_wx p_store MachineMode = false.
Proof. split; reflexivity. Qed.

Theorem a_refusing_region_table_is_refuted :
  ~ DecidesOnTheCapabilityAlone demo_wx (region_gated demo_wx (fun _ => false)).
Proof.
  intros H.
  assert (Hq := H (Build_Edge demo_wx DemoKernel true p_store) true).
  discriminate Hq.
Qed.

Theorem the_demo_hidden_singleton_is_refuted :
  ~ NoAmbientAuthority demo_wx (demo_graph wx_free_decode)
      (singleton_working demo_wx (demo_graph wx_free_decode)
         (rogue_edge wx_free_decode)).
Proof. apply a_hidden_singleton_is_refuted. reflexivity. Qed.

Theorem the_demo_lazily_initialized_static_is_refuted :
  ~ DoesNotDependOnTheCall demo_wx (lazily_initialized demo_wx).
Proof.
  apply (a_lazily_initialized_static_is_refuted demo_wx
           (demo_graph wx_free_decode) (planned_edge wx_free_decode)).
  reflexivity.
Qed.

(* The wide root at the demo: core `true` owns region `true`, so a root over
   region `false` handed to it is outside its partition bound. *)
Definition demo_wide_edge : Edge demo_wx :=
  Build_Edge demo_wx DemoKernel false p_store.

Theorem the_demo_wide_root_is_refuted :
  ~ RootsAreBounded demo_wx
      (wide_root_state demo_wx (demo_graph wx_free_decode) demo_wide_edge).
Proof.
  apply (a_wide_root_refutes_the_partition_bound demo_wx
           (demo_graph wx_free_decode) demo_wide_edge true).
  reflexivity.
Qed.

(* And it installs exactly, so the refinement is silent about it: R-07-028
   and R-07-019 are two obligations and the first does not carry the
   second. *)
Theorem the_wide_root_installer_refines_exactly :
  InstallsExactly demo_wx (wide_root_installer demo_wx demo_wide_edge).
Proof. intros g st [ Hd _ ] e. exact (Hd e). Qed.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: every shipped
   constant's enumerated assumption set is compared against the declared set
   R-05-164 currently makes empty, so "Closed under the global context" is
   that emptiness checked mechanically.
   ------------------------------------------------------------------------- *)

Print Assumptions bool_eqb_refl.
Print Assumptions bool_eqb_sound.
Print Assumptions andb_split.
Print Assumptions andb_join.
Print Assumptions orb_split.
Print Assumptions orb_true_right.
Print Assumptions negb_true.
Print Assumptions orb_absorb.
Print Assumptions andb_absorb.
Print Assumptions all_of_mono.
Print Assumptions all_of_of_forall.
Print Assumptions all_of_member.
Print Assumptions any_of_and_all_of.
Print Assumptions all_perms.
Print Assumptions perm_eqb_refl.
Print Assumptions perm_eqb_sound.
Print Assumptions the_permission_field_has_thirty_two_codepoints.
Print Assumptions every_codepoint_is_enumerated.
Print Assumptions edge_eqb.
Print Assumptions edge_eqb_refl.
Print Assumptions edge_eqb_sound.
Print Assumptions holds.
Print Assumptions every_member_holds.
Print Assumptions graphs_agree.
Print Assumptions WxAtTheEncoding.
Print Assumptions wx_check.
Print Assumptions the_finite_check_decides_wx.
Print Assumptions no_wx_edge.
Print Assumptions WxOverTheDistribution.
Print Assumptions the_encoding_carries_every_distribution.
Print Assumptions the_encoding_reaches_the_booted_machine.
Print Assumptions PromotesToWritableExecute.
Print Assumptions no_promotion_primitive_exists.
Print Assumptions promoting.
Print Assumptions resident_eqb_sound.
Print Assumptions spec_inventory.
Print Assumptions inventory_ok.
Print Assumptions the_specification_inventory_is_admitted.
Print Assumptions the_specification_inventory_has_one_entry.
Print Assumptions the_intrusion_family_is_the_four_other_kinds.
Print Assumptions the_intrusion_family_size.
Print Assumptions every_intrusion_is_refused.
Print Assumptions no_second_resident_is_admitted.
Print Assumptions the_count_is_not_the_occupant.
Print Assumptions InstallsExactly.
Print Assumptions InstallsExactlyOf.
Print Assumptions exact_everywhere_is_exact_at.
Print Assumptions RootsAreBounded.
Print Assumptions EveryCoreIsRooted.
Print Assumptions Quiescent.
Print Assumptions OnlyTheKernelHoldsSystemRegisters.
Print Assumptions system_register_edges_are_the_kernels.
Print Assumptions plan_names_no_firmware_edge.
Print Assumptions plan_roots_every_core.
Print Assumptions Handoff.
Print Assumptions the_handoff_installs_exactly.
Print Assumptions the_handoff_roots_are_bounded.
Print Assumptions the_handoff_roots_every_core.
Print Assumptions the_boolean_firmware_check_is_sound.
Print Assumptions quiescence_follows_from_the_refinement.
Print Assumptions the_build_time_check_becomes_an_installed_property.
Print Assumptions the_two_pmp_roles_this_file_carries_are_carried.
Print Assumptions canonical.
Print Assumptions the_handoff_is_satisfiable.
Print Assumptions an_unrooted_plan_admits_no_handoff.
Print Assumptions the_platform_has_one_mode.
Print Assumptions spec_gate.
Print Assumptions DecidesOnThePermission.
Print Assumptions the_specification_gate_decides_on_the_permission.
Print Assumptions mode_gate.
Print Assumptions a_mode_check_separates_nothing.
Print Assumptions the_permission_gate_separates_where_the_decode_does.
Print Assumptions authorizes.
Print Assumptions DecidesOnTheCapabilityAlone.
Print Assumptions region_gated.
Print Assumptions the_specification_decides_on_the_capability_alone.
Print Assumptions a_region_table_only_subtracts.
Print Assumptions the_region_table_needs_to_refuse.
Print Assumptions NoAmbientAuthority.
Print Assumptions the_firmware_holds_only_planned_authority.
Print Assumptions singleton_working.
Print Assumptions the_singleton_needs_to_be_unplanned.
Print Assumptions a_hidden_singleton_is_refuted.
Print Assumptions DoesNotDependOnTheCall.
Print Assumptions the_specification_is_not_lazily_initialized.
Print Assumptions lazily_initialized.
Print Assumptions a_lazily_initialized_static_is_refuted.
Print Assumptions adding_installer.
Print Assumptions the_adding_installer_is_satisfiable.
Print Assumptions an_added_edge_refutes_the_refinement.
Print Assumptions adding_a_planned_edge_still_refines.
Print Assumptions dropping_installer.
Print Assumptions the_dropping_installer_is_satisfiable.
Print Assumptions a_dropped_edge_refutes_the_refinement.
Print Assumptions dropping_an_unplanned_edge_still_refines.
Print Assumptions wide_root_installer.
Print Assumptions the_wide_root_installer_is_satisfiable.
Print Assumptions a_wide_root_refutes_the_partition_bound.
Print Assumptions resident_handler_installer.
Print Assumptions the_resident_handler_installer_is_satisfiable.
Print Assumptions a_resident_handler_refutes_quiescence.
Print Assumptions the_resident_handler_installer_still_refines.
Print Assumptions wx_free_decode.
Print Assumptions leaky_decode.
Print Assumptions the_specification_decode_passes_the_finite_check.
Print Assumptions a_store_and_execute_codepoint_fails_the_finite_check.
Print Assumptions demo_graph.
Print Assumptions the_demo_plan_passes_the_build_time_checks.
Print Assumptions the_rogue_and_firmware_edges_are_unplanned.
Print Assumptions the_demo_handoff_holds.
Print Assumptions plan_deletions.
Print Assumptions plan_insertions.
Print Assumptions the_deletion_family_size.
Print Assumptions the_insertion_family_size.
Print Assumptions every_deletion_of_the_plan_is_a_different_distribution.
Print Assumptions every_insertion_into_the_plan_is_a_different_distribution.
Print Assumptions the_plan_agrees_with_itself.
Print Assumptions the_rogue_edge_refutes_the_refinement.
Print Assumptions a_planned_edge_dropped_refutes_the_refinement.
Print Assumptions without_the_refinement_the_build_time_check_says_nothing.
Print Assumptions a_firmware_that_keeps_its_own_edge_is_refuted.
Print Assumptions the_distribution_check_is_not_the_encoding_check.
Print Assumptions the_promotion_primitive_exists_where_the_encoding_admits_it.
Print Assumptions the_specification_encoding_excludes_both.
Print Assumptions the_root_set_has_two_members_where_both_authorities_are_needed.
Print Assumptions the_mode_gate_is_refuted.
Print Assumptions the_permission_separates_the_kernel_from_a_compartment.
Print Assumptions a_refusing_region_table_is_refuted.
Print Assumptions the_demo_hidden_singleton_is_refuted.
Print Assumptions the_demo_lazily_initialized_static_is_refuted.
Print Assumptions the_demo_wide_root_is_refuted.
Print Assumptions the_wide_root_installer_refines_exactly.
