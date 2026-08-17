(* =========================================================================
   ApexTheorem.v

   The machine-checked statement of the apex theorem T and the nine seam
   lemmas, interfaces aligned: day-one deliverable (iii) of R-18-003b,
   sub-deliverable (a) of R-18-031, row 1 of the crown-jewel inventory.

   What this file is. A statement artifact, not a proof development. Every
   constant is a Definition of sort Prop over the Vocabulary record, whose
   fields are the interfaces other crown-jewel rows author; binding a row
   is instantiating its fields. Nothing is admitted and nothing is
   axiomatized: the Print Assumptions commands at the end report every
   constant closed under the global context, which is R-05-163's gate
   holding over the declared set R-05-164 currently makes empty (no
   admission axiom, bootstrap root, or Ax-ledger entry is yet authored).
   The discharge of what is stated here is R-18-031(b), the linking
   theorem, in the one Iris-over-Sail program logic (R-05-158); this file
   precedes that development and is what it will import, so it depends on
   nothing beyond the Coq prelude.

   Read as the coverage checklist (R-18-031(a)): the record's Prop fields
   enumerate every side-property some seam consumes or concludes. A proof
   workstream lands by instantiating its field, and a field no workstream
   instantiates is an uncovered obligation with exactly one name.

   Decisions this statement takes, each a reviewable reading of the
   register rather than a neutral transcription:

   1. Execution is a function of the whole-system input. R-15-101 makes
      cycle-level timing and memory traffic a function of the instruction
      stream and architectural state alone, so the model carries no
      further source of nondeterminism for the observations T ranges
      over.
   2. The refinement tower conjoins four theorem rungs; the fifth,
      die-matches-RTL, is an element of Ax rather than a conjunct
      (R-05-158: "the last an axiom and the rest theorems"; R-05-162).
   3. NI joins timing and WCET joins isolation at the same premise, the
      one timing_isolation field, per R-17-041: "WCET soundness and
      timing-channel deletion share one non-interference proof".
   4. CT joins RTL and Sail at the tower's own rung: the third seam's
      second premise is the rtl_refines_sail field the tower conjoins,
      which is the rung R-05-160 names outright and R-17-042 books as
      "CT inherits the RTL and Sail residual".
   5. Crypto joins hardness at the AE property that AE joins
      non-interference on: the eighth seam concludes the
      ae_ind_cca_int_ctxt field the fifth consumes, the join R-17-049
      places at the primitive's functional specification (row 14) and
      R-10-025 composes.
   6. WCET joins isolation at the schedulability liveness consumes: the
      second seam concludes the composed_schedulability field the sixth
      consumes, the admission-proved schedule (R-11-017) being the one
      artifact both speak about.
   7. Attestation joins capability safety at the substrate: the ninth
      seam's second premise is the spatial_safety invariant, R-05-159's
      Cerise universal contract.
   8. Consent joins declassification at T's own D: the flows the seventh
      seam authorizes are the ones the release_* quotients forget, and
      its premise sits inside Ax (R-05-162's "human consent
      correctness"), carried by the ax_carries_consent field.
   9. The observation is three channels (value, timing, and the in-scope
      architectural channels), R-05-156's second element. Progress
      observations live inside the channels per R-08-027a, bound when
      row 2's policy model lands; "in-scope" is §17's scoping, so the
      analog power and EM observation is outside T (R-05-162, R-17-058a).

   The lemmas at the end are the statement's own non-vacuity witnesses
   (R-05-165, R-05-166): a model in which T is provable, so no premise
   is unsatisfiable and no quantifier domain is empty, and a model in
   which T is refutable, so the statement excludes something.
   ========================================================================= *)

(* -------------------------------------------------------------------------
   The vocabulary: every interface the statement quantifies over or
   abbreviates. Type and function fields are authored by the crown-jewel
   rows named beside them; Prop fields stand for the theorems and side
   properties the invariants, the tower, and the seams join.
   ------------------------------------------------------------------------- *)

Record Vocabulary : Type := {

  (* --- the composed image on the fabricated die (R-05-156) --------------- *)

  Input : Type;                          (* whole-system inputs                *)
  Trace : Type;                          (* executions of the composed image   *)
  exec : Input -> Trace;                 (* a function, per R-15-101 (decision
                                            1 above)                          *)

  (* --- compartments and the adversary quantifier (R-01-002, R-05-156) ---- *)

  Compartment : Type;
  tcb : Compartment -> Prop;             (* the §6 trusted set                 *)
  graph_permits : (Compartment -> Prop) -> Prop;
                                         (* the compose-time capability
                                            topology's admissible adversary
                                            sets (R-01-002)                   *)

  (* --- the compose-time policy P: crown-jewel row 2 (R-08-028) ----------- *)

  Policy : Type;
  policy : Policy;                       (* the register's P                   *)
  indist : Policy -> (Compartment -> Prop) -> Input -> Input -> Prop;
                                         (* two whole-system inputs
                                            indistinguishable to C under P    *)

  (* --- the observation: value, timing, in-scope architectural
         (R-05-156's second element; decision 9 above) ---------------------- *)

  ValueObs : Type;
  TimingObs : Type;
  ArchObs : Type;
  observe_value : (Compartment -> Prop) -> Trace -> ValueObs;
  observe_timing : (Compartment -> Prop) -> Trace -> TimingObs;
  observe_arch : (Compartment -> Prop) -> Trace -> ArchObs;

  (* --- D, the powerbox declassification set (R-05-156, R-05-162):
         equality modulo D is equality of the released quotients ------------ *)

  Declass : Type;
  D : Declass;
  release_value : Declass -> ValueObs -> ValueObs;
  release_timing : Declass -> TimingObs -> TimingObs;
  release_arch : Declass -> ArchObs -> ArchObs;

  (* --- the four unary invariants, the substrate every seam assumes
         (R-05-159) ------------------------------------------------------- *)

  spatial_safety : Prop;                 (* the Cerise universal contract      *)
  temporal_safety : Prop;                (* revocation with the CHERI-TAL
                                            linear-capability discipline      *)
  wx_exclusivity : Prop;                 (* no write-and-execute capability in
                                            the derivation forest             *)
  write_before_read : Prop;              (* definite initialization over
                                            eager-zeroized memory             *)

  (* --- the refinement tower's theorem rungs (R-05-158); the fifth rung,
         die-matches-RTL, is inside Ax (decision 2 above) ------------------- *)

  source_refines_spec : Prop;
  binary_refines_source_robustly : Prop;
  binary_against_sail : Prop;
  rtl_refines_sail : Prop;               (* also the third seam's premise
                                            (decision 4 above)               *)

  (* --- side properties the nine seams join (R-05-160); each field's
         authoring workstream is named in the seam definitions below -------- *)

  explicit_flow_noninterference : Prop;  (* the L3 flow theorem (R-08-026)     *)
  timing_isolation : Prop;               (* the §15 partitioning hardware's
                                            formal isolation semantics
                                            (R-08-027, rows 7 and 8)          *)
  partition_guarantee : Prop;            (* the one partition-level guarantee
                                            R-08-027 says the two compose
                                            into                              *)
  wcet_bounds_sound : Prop;              (* bounds read off typing derivations
                                            (R-05-102), magnitudes from
                                            row 15                            *)
  composed_schedulability : Prop;        (* the admission-proved schedule
                                            (R-11-017, row 11)                *)
  constant_time_typed : Prop;            (* CT over the row 5 leakage model
                                            (CJ-CT-SOUND)                     *)
  constant_time_on_die : Prop;           (* the same claim transported to the
                                            RTL of record                     *)
  cheri_tal_soundness : Prop;            (* well-typed implies safe over the
                                            row 6 Sail model (CJ-TAL-SOUND)   *)
  admission_type_check : Prop;           (* every admitted binary is
                                            well-typed (R-05-159's fourth
                                            carrier)                          *)
  admitted_binaries_safe : Prop;
  crypto_reductions : Prop;              (* the CJ-REDUCTION games over
                                            row 14's functional specs         *)
  ae_ind_cca_int_ctxt : Prop;            (* the AE property, concluded by seam
                                            eight, consumed by seam five
                                            (decision 5 above)                *)
  storage_noninterference : Prop;        (* the filesystem leaks nothing
                                            across domains (R-10-025)         *)
  verifiable_encryption : Prop;          (* R-10-025's composed claim          *)
  kernel_liveness : Prop;                (* CJ-KERNEL's progress half          *)
  progress_guarantee : Prop;             (* no liveness stall escapes the
                                            union (R-05-161); observable per
                                            R-08-027a                         *)
  declassified_flows_authorized : Prop;  (* every flow D releases is one a
                                            consent act authorized, D being
                                            this record's own D (decision 8
                                            above)                            *)
  attestation_chain : Prop;              (* the §9 measured chain              *)
  image_binding : Prop;                  (* the attested image is the composed
                                            image the proofs are about, which
                                            is what entitles exec to stand
                                            for it                            *)

  (* --- the boundary (R-05-162): Ax abbreviates the conjunction of the
         R-18-031(c) ledger, and the three of its elements that some seam
         or rung consumes are pinned inside it by the coercions below.
         Specification faithfulness and invasive physical attack are
         boundary elements no Prop of this statement can carry; they stay
         §17 residuals. --------------------------------------------------- *)

  die_matches_rtl : Prop;
  hardness_conjectures : Prop;           (* MLWE/MSIS, ECDLP/CDH (R-17-049)    *)
  consent_correctness : Prop;            (* the human half (R-17-013, R-17-013e) *)
  Ax : Prop;
  ax_carries_die_matches_rtl : Ax -> die_matches_rtl;
  ax_carries_hardness : Ax -> hardness_conjectures;
  ax_carries_consent : Ax -> consent_correctness
}.

(* -------------------------------------------------------------------------
   The apex theorem T (R-05-156), with its four elements in order: the
   quantifier over adversary sets C the graph permits; the
   value-and-timing-and-architectural observation; the modulo-D clause,
   as equality of released quotients; and the relative-to-Ax clause, as
   the leading implication.
   ------------------------------------------------------------------------- *)

Definition admissible (v : Vocabulary) (C : v.(Compartment) -> Prop) : Prop :=
  v.(graph_permits) C /\ (forall c, C c -> ~ v.(tcb) c).

Definition observation_equal_modulo_D
    (v : Vocabulary) (C : v.(Compartment) -> Prop)
    (t1 t2 : v.(Trace)) : Prop :=
     v.(release_value) v.(D) (v.(observe_value) C t1)
   = v.(release_value) v.(D) (v.(observe_value) C t2)
  /\ v.(release_timing) v.(D) (v.(observe_timing) C t1)
   = v.(release_timing) v.(D) (v.(observe_timing) C t2)
  /\ v.(release_arch) v.(D) (v.(observe_arch) C t1)
   = v.(release_arch) v.(D) (v.(observe_arch) C t2).

Definition T (v : Vocabulary) : Prop :=
  v.(Ax) ->
  forall C : v.(Compartment) -> Prop,
    admissible v C ->
    forall i1 i2 : v.(Input),
      v.(indist) v.(policy) C i1 i2 ->
      observation_equal_modulo_D v C (v.(exec) i1) (v.(exec) i2).

(* -------------------------------------------------------------------------
   The substrate (R-05-159) and the tower (R-05-158).
   ------------------------------------------------------------------------- *)

Definition substrate_invariants (v : Vocabulary) : Prop :=
  v.(spatial_safety) /\ v.(temporal_safety)
  /\ v.(wx_exclusivity) /\ v.(write_before_read).

Definition refinement_tower (v : Vocabulary) : Prop :=
  v.(source_refines_spec)
  /\ v.(binary_refines_source_robustly)
  /\ v.(binary_against_sail)
  /\ v.(rtl_refines_sail).

(* -------------------------------------------------------------------------
   The nine seam lemmas, exactly R-05-160's list in R-05-160's order.
   Each is the statement that its two sides meet at the named interface;
   the alignment (R-05-161: "each seam's conclusion is stated in the
   vocabulary of the next's premise") is exhibited by field reuse, not
   asserted in prose: reused fields are the interfaces shown to meet.
   ------------------------------------------------------------------------- *)

(* 1. NI joins timing (R-08-027, R-17-003). *)
Definition seam_ni_timing (v : Vocabulary) : Prop :=
  v.(explicit_flow_noninterference) /\ v.(timing_isolation)
  -> v.(partition_guarantee).

(* 2. WCET joins isolation (R-17-041); shares timing_isolation with seam 1
      and concludes what seam 6 consumes. *)
Definition seam_wcet_isolation (v : Vocabulary) : Prop :=
  v.(wcet_bounds_sound) /\ v.(timing_isolation)
  -> v.(composed_schedulability).

(* 3. CT joins RTL and Sail (R-17-042); the second premise is the tower's
      own rung. *)
Definition seam_ct_rtl_sail (v : Vocabulary) : Prop :=
  v.(constant_time_typed) /\ v.(rtl_refines_sail)
  -> v.(constant_time_on_die).

(* 4. CHERI-TAL joins Sail: soundness and the admission type-check are
      stated over the one row 6 model, this record's exec, which is the
      alignment; two models would be two Vocabulary values. *)
Definition seam_cheri_tal_sail (v : Vocabulary) : Prop :=
  v.(cheri_tal_soundness) /\ v.(admission_type_check)
  -> v.(admitted_binaries_safe).

(* 5. AE joins non-interference (R-10-025), at row 14's functional spec. *)
Definition seam_ae_noninterference (v : Vocabulary) : Prop :=
  v.(ae_ind_cca_int_ctxt) /\ v.(storage_noninterference)
  -> v.(verifiable_encryption).

(* 6. Liveness joins schedulability (R-17-043); consumes seam 2's
      conclusion. *)
Definition seam_liveness_schedulability (v : Vocabulary) : Prop :=
  v.(kernel_liveness) /\ v.(composed_schedulability)
  -> v.(progress_guarantee).

(* 7. Consent joins declassification, at T's own D; the premise is inside
      Ax (R-05-162), so within T's scope it is discharged by
      ax_carries_consent. *)
Definition seam_consent_declassification (v : Vocabulary) : Prop :=
  v.(consent_correctness) -> v.(declassified_flows_authorized).

(* 8. Crypto joins hardness (R-17-049); the hardness side is inside Ax,
      and the conclusion is seam 5's premise. *)
Definition seam_crypto_hardness (v : Vocabulary) : Prop :=
  v.(crypto_reductions) /\ v.(hardness_conjectures)
  -> v.(ae_ind_cca_int_ctxt).

(* 9. Attestation joins capability safety, the substrate's spatial_safety
      (R-05-159); concludes the image binding T's preamble needs. *)
Definition seam_attestation_capability_safety (v : Vocabulary) : Prop :=
  v.(attestation_chain) /\ v.(spatial_safety)
  -> v.(image_binding).

(* The list is closed by amendment to R-05-160; a tenth conjunct here
   without that amendment is a review-gate finding. *)
Definition seam_lemmas (v : Vocabulary) : Prop :=
  seam_ni_timing v
  /\ seam_wcet_isolation v
  /\ seam_ct_rtl_sail v
  /\ seam_cheri_tal_sail v
  /\ seam_ae_noninterference v
  /\ seam_liveness_schedulability v
  /\ seam_consent_declassification v
  /\ seam_crypto_hardness v
  /\ seam_attestation_capability_safety v.

(* -------------------------------------------------------------------------
   The composition meta-lemma (R-05-161): the four invariants and the nine
   seams, transported through the tower, entail T. Stated here; its proof
   is R-18-031(b), the linking theorem, discharged incrementally and last.
   Its coverage obligation (no attacker-observable channel, authorized
   flow, timing leak, liveness stall, or admitted binary escapes the
   union) is the written-and-reviewed argument R-05-161 requires beside
   this statement, not a further Prop of it.
   ------------------------------------------------------------------------- *)

Definition composition_meta_lemma (v : Vocabulary) : Prop :=
  substrate_invariants v /\ seam_lemmas v /\ refinement_tower v
  -> T v.

(* =========================================================================
   Non-vacuity witnesses (R-05-165, R-05-166). R-05-165 names the three
   ways a statement can verify emptily; the first witness closes the
   unsatisfiable-premise and uninhabited-domain cases, the second closes
   the refines-everything case. Both are proved outright: this file ships
   no admitted obligation.
   ========================================================================= *)

(* A one-point machine: every domain inhabited, every premise satisfiable,
   and T provable. *)
Definition trivial_vocabulary : Vocabulary := {|
  Input := unit;
  Trace := unit;
  exec := fun _ => tt;
  Compartment := unit;
  tcb := fun _ => False;
  graph_permits := fun _ => True;
  Policy := unit;
  policy := tt;
  indist := fun _ _ _ _ => True;
  ValueObs := unit;
  TimingObs := unit;
  ArchObs := unit;
  observe_value := fun _ _ => tt;
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
  attestation_chain := True;
  image_binding := True;
  die_matches_rtl := True;
  hardness_conjectures := True;
  consent_correctness := True;
  Ax := True;
  ax_carries_die_matches_rtl := fun _ => I;
  ax_carries_hardness := fun _ => I;
  ax_carries_consent := fun _ => I
|}.

Lemma statement_inhabitation_witness : T trivial_vocabulary.
Proof.
  intros _ C _ i1 i2 _.
  split; [reflexivity | split; reflexivity].
Qed.

(* T's premises are jointly satisfiable in that model, so the implication
   above is not proved from an empty antecedent. *)
Lemma premises_inhabited :
  admissible trivial_vocabulary (fun _ => True)
  /\ trivial_vocabulary.(indist) trivial_vocabulary.(policy)
       (fun _ => True) tt tt.
Proof.
  split; [split; [exact I | intros c _ contra; exact contra] | exact I].
Qed.

(* A one-bit leak: the input is the secret, the value observation reveals
   it, the policy calls the two inputs indistinguishable, and T is
   refutable. The distinguishing instance R-05-166 asks for: the
   specification rejects at least one implementation. *)
Definition leaky_vocabulary : Vocabulary := {|
  Input := bool;
  Trace := bool;
  exec := fun b => b;
  Compartment := unit;
  tcb := fun _ => False;
  graph_permits := fun _ => True;
  Policy := unit;
  policy := tt;
  indist := fun _ _ _ _ => True;
  ValueObs := bool;
  TimingObs := unit;
  ArchObs := unit;
  observe_value := fun _ t => t;
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
  attestation_chain := True;
  image_binding := True;
  die_matches_rtl := True;
  hardness_conjectures := True;
  consent_correctness := True;
  Ax := True;
  ax_carries_die_matches_rtl := fun _ => I;
  ax_carries_hardness := fun _ => I;
  ax_carries_consent := fun _ => I
|}.

Lemma statement_distinguishing_instance : ~ T leaky_vocabulary.
Proof.
  intros H.
  specialize (H I (fun _ => True)
                (conj I (fun _ _ contra => contra))
                true false I).
  destruct H as [Hvalue _].
  cbv in Hvalue.
  discriminate Hvalue.
Qed.

(* -------------------------------------------------------------------------
   R-05-163's assumption gate, run by tools/proof-gate.sh: the enumerated
   assumption set of every shipped constant is compared against the
   declared set, which R-05-164 reads from the register and which is
   empty today. "Closed under the global context" is that emptiness,
   checked mechanically; any other output fails the gate.
   ------------------------------------------------------------------------- *)

Print Assumptions T.
Print Assumptions composition_meta_lemma.
Print Assumptions seam_lemmas.
Print Assumptions statement_inhabitation_witness.
Print Assumptions premises_inhabited.
Print Assumptions statement_distinguishing_instance.
