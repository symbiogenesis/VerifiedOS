(* SPDX-License-Identifier: Apache-2.0 *)
(* =========================================================================
   ComposedNonInterference.v

   The machine-checked statement of the ensemble's composed non-interference
   obligation: R-17-014a's fourth dimension, the one T at a single member
   does not reach. A statement artifact beside ApexTheorem.v, not a proof
   development and not an extension of it.

   What this file is. It imports ApexTheorem.v and adds nothing to it: no
   field on the Vocabulary record, no tenth conjunct to R-05-160's closed
   seam list, no obligation inside T, and no axiom. T's statement is
   unmoved, so crown-jewel row 1 and the field bindings it publishes are
   unchanged by this file's existence. What it adds is one record beside
   T, `Ensemble`, and one Prop over that record, `composed_noninterference`,
   which is a theorem *target*: nothing here proves it, and nothing here
   claims to discharge R-17-014a, whose record stays open until a proof
   lands (R-18-031).

   Why a target and not a theorem. R-17-014a says the composition is
   "carried by no per-member theorem", and that sentence is machine-checked
   below rather than asserted: `composition_is_carried_by_no_per_member_theorem`
   refutes the uniform implication from N member instances of T to the
   composed conclusion. The gap it exhibits is the whole content of the
   target, so a future edit that closes the gap by definition breaks that
   lemma here rather than at the capstone.

   Decisions this statement takes, each a reviewable reading of the register
   rather than a neutral transcription:

   1. A member is a whole machine under the register alone (R-02-003a,
      R-15-228b), so a member *is* a Vocabulary and the ensemble carries
      `member : Member -> Vocabulary`. N is the cardinality of `Member`,
      left open: the statement is over an ensemble of any size, and the
      two instances below are two-member ones.
   2. The ensemble's whole-system input is its own (R-05-156a read across
      the ensemble), and each member meets it twice: `exogenous` is the
      member's own share of that input, `delivered` is what the member
      actually runs on, and the two are separate fields related by nothing.
      That gap is where the wire lives and is the single most reviewable
      decision in this file: relating them would make the target follow
      from the member theorems in one line, which is R-05-165's second
      vacuity mode wearing a composition, and the instance at the end is
      what proves the gap is really there.
   3. The composed execution is not a field. It is
      `ensemble_trace e i m := (member m).(exec) (delivered i m)`, a
      definition over fields the record already carries, because the
      composed image's behaviour is the members' own executions reached
      through the wire and a second owner for that fact could drift from
      the first.
   4. A link's two endpoints are one boundary and not two. `Link` carries
      `near`/`far` members and one endpoint compartment at each end, and
      `wire_boundary` is the single predicate over that single link which
      names the untrusted-wire class R-17-003d adds to the isolation
      model's boundary classes.
   5. The wire is an adversarial channel the policy permits, and "permits"
      is ApexTheorem's own `admissible` rather than a second notion: the
      composed target quantifies only over adversary sets that are
      admissible at every member (graph-permitted and outside the TCB,
      R-01-002) *and* contain each link's endpoint compartment. The
      entitlement is R-12-007a's, and it is an upper bound and not an
      equality: a peer compromised inside an accepted session reaches no
      more than a compromised local ring peer behind the same table
      reaches, because a frame names indices into the receiving member's
      own table, validated there before eligibility, and encodes no
      capability, address or authority. The ring proof's Byzantine peer
      (R-12-008) is the wire's peer, so the wire enters as an adversary at
      the receiving member and never as a channel with authority of its
      own. The converse containment is stated by neither entry and is not
      claimed here.
   6. The link carries two conjuncts and no third, which is R-17-014a's
      upper bound and not more: `link_schedule` stands for R-15-228d's
      slot table and `link_session` for R-12-015d's session, the two the
      entry names, and "and nothing more" forbids a third. The two-machine
      attestation relation R-17-061b names is that session and not a third
      field: R-17-061b states outright that the relation "is stated at
      R-12-015d", so a separate field for it would be a second owner of
      one fact. Both are opaque Props here, which is the standing
      R-17-049d gives an unauthored model: the reference model Q23c owns
      will instantiate them, and nothing is credited until it does.
   6a. Those two conjuncts are inert as stated, and this file reports that
      rather than trading on the appearance of a contribution. Each is an
      opaque `Link -> Prop` occurring in the record declaration, in
      `link_contribution` and in the instance literals, and in no
      definition the target's conclusion mentions, so nothing carries
      either into that conclusion.
      `link_premise_carries_vacuity_and_not_contribution` below is that
      claim machine-checked: an ensemble whose `link_session` is False
      satisfies the target outright while its wire still carries the near
      member's own quantity into the far member's observable slot. The
      statement therefore meets R-17-014a's upper bound by making the
      named contribution empty, which is R-05-165's second mode standing
      in the target's own premise. That is a reported gap and not a
      decision taken here: no register entry relates what a link delivers
      to a member to what the sending member's execution placed on the
      wire in that slot. R-15-228b fixes what a frame is, R-15-228d the
      slot it occupies, R-12-007a the indices it names and R-12-015d the
      session that authenticates it, and none of the four states that
      transfer, so the schedule and the session have nothing here to bear
      on. The act owed is a register act rather than a Gallina one: an
      Accept clause at R-17-003d, or an entry beside R-12-007a, stating
      the relation between a member's delivered input and the sending
      member's trace at the link's slots. A field asserting that relation
      here would decide by fiat what the register has not, exactly as
      decision 8 declines to for the label question, so the target is
      stated with the link premise the register supports and this file
      names what that premise is worth.
   7. Ensemble indistinguishability is stated over the members' *exogenous*
      inputs at the members' own policies, deliberately not over the
      delivered ones. Stating it over the delivered inputs is the accident
      that would make this target provable from decision 2's projection
      alone.
   8. Label, the compose-time confidentiality label, is an opaque
      interface exactly as `Policy` and `indist` are in ApexTheorem.v,
      owed by row 2's policy model (R-08-028), which is unauthored
      (R-15-211). `endpoints_share_a_label` is defined here and is not
      a premise of the target, because no register entry decides what
      relation a link's two endpoint labels must stand in: R-15-228b,
      R-15-228d, R-12-007a, R-12-015d and R-17-003d state the frame
      grammar, the slot table, the index-only payload and the session, and
      none of them states a label relation across the wire. The
      predicate is stated so that the question has a name and an instance,
      and it is left out of the target so that this file does not decide by
      fiat what the register has not decided.
   9. No new axiom class. `ensemble_Ax` is per-member Ax and nothing else:
      an ensemble is N attested copies of one mask set, so the residuals
      R-17-061b enumerates do not multiply and none is added here
      (R-05-162). The Print Assumptions commands at the end report every
      constant closed under the global context, R-05-163's gate over the
      declared set R-05-164 currently makes empty.
   10. This is not a second reading of *hyper-secure*. T is that reading
      (R-05-157); what this file states is what the same reading costs
      across a wire, and it makes no informal claim beyond the target
      below.

   The lemmas at the end are the statement's own non-vacuity witnesses
   (R-05-165, R-05-166): every quantifier domain inhabited, the premises
   jointly satisfiable, the target provable in one model, and, in another,
   an instance the target rejects whose two endpoints sit at different
   labels. One lemma there is not a witness and claims no entry: the third
   instance reports decision 6a's gap.
   (*| BEGIN derived: cited entries |*)
   Owner: docs/requirements-register.md
   Requirements: R-01-002 R-02-003a R-05-156a R-05-157 R-05-160 R-05-162 R-05-163 R-05-164
      R-05-165 R-05-166 R-08-028 R-12-007a R-12-008 R-12-015d R-15-211 R-15-228b R-15-228d
      R-17-003d R-17-014a R-17-049d R-17-061b R-18-031
   SHA256: c6a9bb26845f4ef4a070606a029bab248bb60aa89bb3b970d042ab7faf78fddc
   (*| END derived |*)
   ========================================================================= *)

Require Import ApexTheorem.

(* -------------------------------------------------------------------------
   The ensemble: N members, each a whole machine under T's own vocabulary,
   and the links that join them. Every field is an interface some other
   workstream authors; binding one is instantiating it, exactly as it is
   for the apex record.
   ------------------------------------------------------------------------- *)

Record Ensemble : Type := {

  (* --- the members (R-02-003a, R-15-228b; decision 1) -------------------- *)

  Member : Type;                          (* N is this type's cardinality     *)
  member : Member -> Vocabulary;          (* each member is one whole machine *)

  (* --- the ensemble's whole-system input, met twice (R-05-156a;
         decision 2): what the member is handed from outside, and what it
         actually runs on. Nothing in this record relates the two. ---------- *)

  EnsInput : Type;
  exogenous : EnsInput -> forall m : Member, (member m).(Input);
  delivered : EnsInput -> forall m : Member, (member m).(Input);

  (* --- the links, each with two endpoints and one boundary (R-15-228b,
         R-17-003d; decision 4) -------------------------------------------- *)

  Link : Type;
  near : Link -> Member;
  far : Link -> Member;
  near_endpoint : forall l : Link, (member (near l)).(Compartment);
  far_endpoint : forall l : Link, (member (far l)).(Compartment);

  (* --- what the link carries: the two R-17-014a names and no third, each
         opaque and, as decision 6a reports, reaching nothing the target's
         conclusion mentions (R-17-014a; decisions 6 and 6a) --------------- *)

  link_schedule : Link -> Prop;           (* R-15-228d's slot table           *)
  link_session : Link -> Prop;            (* R-12-015d's session, which is
                                             R-17-061b's two-machine
                                             attestation relation             *)

  (* --- the compose-time confidentiality label: row 2's interface
         (R-08-028), unauthored (R-15-211); decision 8 ---------------------- *)

  Label : Type;
  label : forall m : Member, (member m).(Compartment) -> Label
}.

(* An ensemble adversary is one compartment set per member, each stated in
   that member's own compartment space. *)
Definition ensemble_adversary (e : Ensemble) : Type :=
  forall m : e.(Member), (e.(member) m).(Compartment) -> Prop.

(* -------------------------------------------------------------------------
   The N member instances of T, and the boundary the ensemble adds.
   ------------------------------------------------------------------------- *)

(* Decision 9: per-member Ax, no ensemble class beside it. *)
Definition ensemble_Ax (e : Ensemble) : Prop :=
  forall m : e.(Member), Ax (e.(member) m).

(* The N member instances of T's statement, each taken whole (R-17-014a). *)
Definition members_hold (e : Ensemble) : Prop :=
  forall m : e.(Member), T (e.(member) m).

(* Decision 4: one predicate over one link, naming both of its endpoints as
   the same boundary of the untrusted-wire class (R-17-003d). *)
Definition wire_boundary (e : Ensemble) (A : ensemble_adversary e)
    (l : e.(Link)) : Prop :=
  A (e.(near) l) (e.(near_endpoint) l) /\ A (e.(far) l) (e.(far_endpoint) l).

(* Decision 5: the wire is an adversarial channel the policy permits. The
   permission is ApexTheorem's own `admissible` at each member, so it is
   graph-permits-and-not-TCB and not a second notion; the coverage clause is
   what makes this adversary the wire's. *)
Definition ensemble_admissible (e : Ensemble) (A : ensemble_adversary e) : Prop :=
  (forall m : e.(Member), admissible (e.(member) m) (A m))
  /\ (forall l : e.(Link), wire_boundary e A l).

(* Decision 6: two conjuncts, and a third here would be a finding. Decision
   6a: neither reaches the conclusion below, and the lemma at the end of the
   file is that sentence machine-checked. *)
Definition link_contribution (e : Ensemble) : Prop :=
  forall l : e.(Link), e.(link_schedule) l /\ e.(link_session) l.

(* Decision 7: over `exogenous`, at each member's own policy. *)
Definition ensemble_indist (e : Ensemble) (A : ensemble_adversary e)
    (i1 i2 : e.(EnsInput)) : Prop :=
  forall m : e.(Member),
    (e.(member) m).(indist) (e.(member) m).(policy) (A m)
      (e.(exogenous) i1 m) (e.(exogenous) i2 m).

(* Decision 3: the composed execution, defined rather than declared. *)
Definition ensemble_trace (e : Ensemble) (i : e.(EnsInput)) (m : e.(Member))
  : (e.(member) m).(Trace) :=
  (e.(member) m).(exec) (e.(delivered) i m).

Definition ensemble_observation_equal_modulo_D
    (e : Ensemble) (A : ensemble_adversary e) (i1 i2 : e.(EnsInput)) : Prop :=
  forall m : e.(Member),
    observation_equal_modulo_D (e.(member) m) (A m)
      (ensemble_trace e i1 m) (ensemble_trace e i2 m).

(* Decision 8: stated so the question has a name, and left out of the target
   below because the register does not decide it. *)
Definition endpoints_share_a_label (e : Ensemble) (l : e.(Link)) : Prop :=
  e.(label) (e.(near) l) (e.(near_endpoint) l)
  = e.(label) (e.(far) l) (e.(far_endpoint) l).

(* -------------------------------------------------------------------------
   The theorem target (R-17-014a). Its premises are the N member instances
   of T, the per-member Ax, and each link's two conjuncts; its quantifier
   ranges over the admissible adversary sets that cover every wire; its
   conclusion is each member's own observation equality modulo that member's
   own D. No proof of it is claimed as a discharge of R-17-014a, whose
   record stays open. The three instances below are not discharges either:
   one at which the target holds, one at which it fails, and one at which
   it holds only because the link premise is false.
   ------------------------------------------------------------------------- *)

Definition composed_noninterference (e : Ensemble) : Prop :=
  ensemble_Ax e ->
  members_hold e ->
  link_contribution e ->
  forall A : ensemble_adversary e,
    ensemble_admissible e A ->
    forall i1 i2 : e.(EnsInput),
      ensemble_indist e A i1 i2 ->
      ensemble_observation_equal_modulo_D e A i1 i2.

(* =========================================================================
   Non-vacuity witnesses (R-05-165, R-05-166). R-05-165's three modes, in
   order: uninhabited domains, unsatisfiable premises, and a statement that
   excludes nothing. Everything below is proved outright; this file ships no
   admitted obligation.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   A two-member, one-link ensemble of one-point machines, over which the
   target is provable.
   ------------------------------------------------------------------------- *)

Definition trivial_ensemble : Ensemble := {|
  Member := bool;
  member := fun _ => trivial_vocabulary;
  EnsInput := unit;
  exogenous := fun _ _ => tt;
  delivered := fun _ _ => tt;
  Link := unit;
  near := fun _ => false;
  far := fun _ => true;
  near_endpoint := fun _ => tt;
  far_endpoint := fun _ => tt;
  link_schedule := fun _ => True;
  link_session := fun _ => True;
  Label := unit;
  label := fun _ _ => tt
|}.

(* R-05-166's decidable half: the record this file's theorems quantify over,
   inhabited by a closed top-level definition ascribed at it. *)
Definition witness_Ensemble : Ensemble := trivial_ensemble.

(* -------------------------------------------------------------------------
   A two-member, one-link ensemble that leaks across the wire. Both members
   are the same machine, which is what an ensemble is (R-17-061b: N attested
   copies of one mask set), so `member` is constant and each member's own
   types reduce.

   The machine: an input is a pair, the member's own quantity and the
   quantity its wire slot holds. Its policy calls two inputs
   indistinguishable to C when their wire quantities agree and, if C holds
   the member's inner compartment, their own quantities agree too; its value
   observation is the wire quantity alone. T holds of it: the policy's first
   conjunct is exactly what the observation reveals.
   ------------------------------------------------------------------------- *)

Definition wire_member_vocabulary : Vocabulary := {|
  Input := (bool * bool)%type;           (* (own quantity, wire quantity)     *)
  Trace := (bool * bool)%type;
  exec := fun x => x;
  Compartment := bool;                   (* false: inner; true: wire endpoint *)
  tcb := fun _ => False;
  graph_permits := fun _ => True;
  Policy := unit;
  policy := tt;
  indist := fun _ C x y => snd x = snd y /\ (C false -> fst x = fst y);
  ValueObs := bool;
  TimingObs := unit;
  ArchObs := unit;
  observe_value := fun _ t => snd t;
  observe_timing := fun _ _ => tt;
  observe_arch := fun _ _ => tt;
  Declass := unit;
  D := tt;
  release_value := fun _ o => o;
  release_timing := fun _ o => o;
  release_arch := fun _ o => o;
  spatial_safety := True;
  temporal_safety := True;
  wx_exclusivity := True;
  write_before_read := True;
  source_refines_spec := True;
  binary_refines_source_robustly := True;
  binary_against_sail := True;
  rtl_refines_sail := True;
  explicit_flow_noninterference := True;
  timing_isolation := True;
  partition_guarantee := True;
  wcet_bounds_sound := True;
  composed_schedulability := True;
  constant_time_typed := True;
  constant_time_on_die := True;
  cheri_tal_soundness := True;
  admission_type_check := True;
  admitted_binaries_safe := True;
  crypto_reductions := True;
  ae_ind_cca_int_ctxt := True;
  storage_noninterference := True;
  verifiable_encryption := True;
  kernel_liveness := True;
  progress_guarantee := True;
  declassified_flows_authorized := True;
  init_realizes_topology := True;
  attestation_chain := True;
  image_binding := True;
  die_matches_rtl := True;
  hardness_conjectures := True;
  consent_correctness := True;
  Ax_machine := True;
  Ax_hardness := True;
  Ax_human := True;
  ax_machine_carries_die_matches_rtl := fun _ => I;
  ax_hardness_carries_conjectures := fun _ => I;
  ax_human_carries_consent := fun _ => I
|}.

(* The near member (false) holds the secret as its own quantity and its wire
   slot is clear; the far member (true) is handed nothing from outside. The
   wire puts the near member's own quantity into the far member's wire slot,
   which is the whole difference between `exogenous` and `delivered`, and
   the endpoints sit at different labels: the label here is the member, so
   the two ends of the one link disagree. *)
Definition leaky_ensemble : Ensemble := {|
  Member := bool;
  member := fun _ => wire_member_vocabulary;
  EnsInput := bool;
  exogenous := fun i m => if m then (false, false) else (i, false);
  delivered := fun i m => if m then (false, i) else (i, false);
  Link := unit;
  near := fun _ => false;
  far := fun _ => true;
  near_endpoint := fun _ => true;
  far_endpoint := fun _ => true;
  link_schedule := fun _ => True;
  link_session := fun _ => True;
  Label := bool;
  label := fun m _ => m
|}.

(* The adversary that is the wire: at each member it is that member's own
   endpoint compartment and nothing else, which is admissible there and
   covers the link. *)
Definition leaky_adversary : ensemble_adversary leaky_ensemble :=
  fun _ c => c = true.

(* -------------------------------------------------------------------------
   R-05-165's first mode: no quantifier of the target ranges over an empty
   domain in either instance.
   ------------------------------------------------------------------------- *)

(*| discharges: R-05-165 |*)
Lemma quantifier_domains_inhabited :
  inhabited trivial_ensemble.(Member) /\ inhabited trivial_ensemble.(Link)
  /\ inhabited trivial_ensemble.(EnsInput)
  /\ inhabited leaky_ensemble.(Member) /\ inhabited leaky_ensemble.(Link)
  /\ inhabited leaky_ensemble.(EnsInput).
Proof.
  exact (conj (inhabits true)
          (conj (inhabits tt)
            (conj (inhabits tt)
              (conj (inhabits true)
                (conj (inhabits tt) (inhabits true)))))).
Qed.

(* -------------------------------------------------------------------------
   R-05-165's second mode: the target's premises are jointly satisfiable,
   the wire-covering adversary set among them, so the implication below is
   not proved from an empty antecedent.
   ------------------------------------------------------------------------- *)

(*| discharges: R-05-165, R-05-166 |*)
Lemma composed_premises_inhabited :
  ensemble_Ax trivial_ensemble
  /\ members_hold trivial_ensemble
  /\ link_contribution trivial_ensemble
  /\ ensemble_admissible trivial_ensemble (fun _ _ => True)
  /\ ensemble_indist trivial_ensemble (fun _ _ => True) tt tt.
Proof.
  split; [| split; [| split; [| split]]].
  - intros m. repeat split.
  - intros m. exact statement_inhabitation_witness.
  - intros l. split; exact I.
  - split.
    + intros m. split; [exact I | intros c _ contra; exact contra].
    + intros l. split; exact I.
  - intros m. exact I.
Qed.

(*| discharges: R-05-165, R-05-166 |*)
Lemma composed_noninterference_inhabitation_witness :
  composed_noninterference trivial_ensemble.
Proof.
  intros _ _ _ A _ i1 i2 _ m.
  split; [reflexivity | split; reflexivity].
Qed.

(* -------------------------------------------------------------------------
   R-05-165's third mode, and R-05-166's distinguishing instance: an
   ensemble the target rejects. Every member's own T holds there, every
   link's schedule and session hold, the adversary is admissible at both
   members and covers the link, and the ensemble's exogenous inputs are
   indistinguishable to it; the composed conclusion fails all the same,
   because the wire carried the near member's own quantity into the far
   member's observable slot. The target therefore excludes something, and
   what it excludes is exactly R-17-014a's fourth dimension.
   ------------------------------------------------------------------------- *)

(*| discharges: R-05-165, R-05-166 |*)
Lemma leaky_members_hold : members_hold leaky_ensemble.
Proof.
  intros m _ C _ x y [Hwire _].
  split; [exact Hwire | split; reflexivity].
Qed.

(*| discharges: R-05-165, R-05-166 |*)
Lemma leaky_wire_is_permitted :
  ensemble_admissible leaky_ensemble leaky_adversary.
Proof.
  split.
  - intros m. split; [exact I | intros c _ contra; exact contra].
  - intros l. split; reflexivity.
Qed.

(*| discharges: R-05-165, R-05-166 |*)
Lemma composed_noninterference_distinguishing_instance :
  ~ composed_noninterference leaky_ensemble.
Proof.
  intros H.
  assert (Hind : ensemble_indist leaky_ensemble leaky_adversary true false).
  { intros m; destruct m; cbn; (split; [reflexivity | intro Hc; discriminate Hc]). }
  specialize (H (fun _ => conj I (conj I I)) leaky_members_hold
                (fun _ => conj I I) leaky_adversary leaky_wire_is_permitted
                true false Hind).
  destruct (H true) as [Hvalue _].
  cbv in Hvalue.
  discriminate Hvalue.
Qed.

(* R-17-014a's own sentence, machine-checked: the composition is carried by
   no per-member theorem. The uniform implication from the N member
   instances of T to the composed conclusion is refutable, so the target
   above is a real obligation and not an unfolding of its own premises. *)
(*| discharges: R-05-165, R-05-166 |*)
Lemma composition_is_carried_by_no_per_member_theorem :
  ~ (forall e : Ensemble, members_hold e -> composed_noninterference e).
Proof.
  intros H.
  exact (composed_noninterference_distinguishing_instance
           (H leaky_ensemble leaky_members_hold)).
Qed.

(* -------------------------------------------------------------------------
   Decision 6a, machine-checked: what the link premise is worth here. The
   ensemble below is `leaky_ensemble` with one field changed, its session
   made unsatisfiable, and nothing else; the wire still carries the near
   member's own quantity into the far member's observable slot. The target
   holds of it, and holds for the only reason available, that
   `link_contribution` is unsatisfiable there. So the two conjuncts
   R-17-014a names as the link's contribution confer vacuity where they
   fail and, being opaque Props no definition the conclusion mentions
   reads, reach the conclusion nowhere they hold. This is R-05-165's second
   mode standing in the target's own premise, and closing it is the
   register act decision 6a names, not an edit to this file.

   This lemma carries no discharge annotation, unlike every other lemma
   here: it books a gap rather than answering an entry.
   ------------------------------------------------------------------------- *)

Definition vacuous_ensemble : Ensemble := {|
  Member := bool;
  member := fun _ => wire_member_vocabulary;
  EnsInput := bool;
  exogenous := fun i m => if m then (false, false) else (i, false);
  delivered := fun i m => if m then (false, i) else (i, false);
  Link := unit;
  near := fun _ => false;
  far := fun _ => true;
  near_endpoint := fun _ => true;
  far_endpoint := fun _ => true;
  link_schedule := fun _ => True;
  link_session := fun _ => False;
  Label := bool;
  label := fun m _ => m
|}.

Definition vacuous_adversary : ensemble_adversary vacuous_ensemble :=
  fun _ c => c = true.

Lemma link_premise_carries_vacuity_and_not_contribution :
  composed_noninterference vacuous_ensemble
  /\ ensemble_indist vacuous_ensemble vacuous_adversary true false
  /\ ~ ensemble_observation_equal_modulo_D
         vacuous_ensemble vacuous_adversary true false.
Proof.
  split; [| split].
  - intros _ _ Hlink. destruct (Hlink tt) as [_ Hbad]. destruct Hbad.
  - intros m; destruct m; cbn; (split; [reflexivity | intro Hc; discriminate Hc]).
  - intros H. destruct (H true) as [Hvalue _]. cbv in Hvalue.
    discriminate Hvalue.
Qed.

(* -------------------------------------------------------------------------
   The endpoint-label predicate decides something and is still not a premise
   (decision 8): it holds at one instance and fails at the other, and the
   instance the target rejects is the one whose two endpoints sit at
   different labels. Whether a link's endpoints must share a label is a
   question for the register, not for this file.
   ------------------------------------------------------------------------- *)

(*| discharges: R-05-165, R-05-166 |*)
Lemma endpoint_labels_decide_something :
  endpoints_share_a_label trivial_ensemble tt
  /\ ~ endpoints_share_a_label leaky_ensemble tt.
Proof.
  split.
  - reflexivity.
  - intros Hc. cbv in Hc. discriminate Hc.
Qed.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by `run.py proofs`: the enumerated
   assumption set of every constant above is compared against the declared
   set R-05-164 reads from the register, which is empty today. "Closed under
   the global context" is that emptiness, checked mechanically.
   ------------------------------------------------------------------------- *)

Print Assumptions composed_noninterference.
Print Assumptions quantifier_domains_inhabited.
Print Assumptions composed_premises_inhabited.
Print Assumptions composed_noninterference_inhabitation_witness.
Print Assumptions leaky_members_hold.
Print Assumptions leaky_wire_is_permitted.
Print Assumptions composed_noninterference_distinguishing_instance.
Print Assumptions composition_is_carried_by_no_per_member_theorem.
Print Assumptions link_premise_carries_vacuity_and_not_contribution.
Print Assumptions endpoint_labels_decide_something.
