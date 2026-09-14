# Opening hardening obligations

This is the Post-M10 opening plan, prepared against the source and evidence
currently present. It does not assert that M10 has completed. The
[three-route ladder](../implementation/implementation-checklist.md#11-building-an-fpga-from-it-all)
and [synthesis provenance](../../rtl/synthesis-provenance.md) own the route
decisions. R-17-039a's fallbacks apply per block. An upstream methodology, a
configured parameter, a passing algebra test and a local whole-core refinement
are different evidence and cannot be substituted for one another.

## Actual coverage at entry

Route (a) closes through a local Rocq refinement plus correspondence to the
exact synthesis input. Route (b) is Sail-generated SystemVerilog plus commercial
FEV evidence, with the equivalence tool identified. Route (c) is a local
functional reference with differential evidence. A proposed route is not an
admitted rung: the table distinguishes the two.

| Block | Intended route | Artifact and current evidence | FEV and theorem coverage |
| --- | --- | --- | --- |
| C-class CHERI-CVA6 scalar core | (c), then (b); later Coq close separate | Pinned imported core and authored configuration; curation is incomplete. R1a's Sail/vector agreement covers capability algebra, not instruction execution or a whole core. R2/R3 remain the corpus and composed-image gates | No local FEV receipt or whole-core Rocq refinement |
| Alternative CHERI-Flute/Piccolo/Toooba scalar substrate | (c)/(b) candidate only | Named alternatives in the substrate list; no selected local realization in the RTL artifact | No local admitted rung |
| V-class Ara and its CHERI extension | (c), then (b) | Named reference under advance license review, with no gitlink or local implementation; M10 owns the capability-aware implementation and its per-class differential campaign | No local FEV receipt or refinement for the required extension |
| M-class Gemmini and its CHERI extension | (c), then (b) | Named reference under advance license review, with no gitlink or local implementation; M10 owns capability checks and the actual matrix/vector integration | No local FEV receipt or refinement for the required extension |
| FEC LDPC/polar datapaths | (c) initially | Substrate families named; no selected complete local core/interface and corpus result | No local FEV receipt or refinement |
| RoT scalar RV64 purecap core | R1c's planned (a) re-homing | Ibex/OpenTitan and CHERIoT-Ibex are functional references, not this RV64 core. The plan removes its authoring from M8b; its register route still needs the recorded owner act | No local core, emission correspondence or refinement; reference ISA evidence does not cover the bespoke format |
| Capability/tag DMA fabric | Curated reference (c), then authored (a) | The datapath's nested tag-controller edition is the reference identified in provenance section 4a. No completed local whole-fabric differential receipt follows from its pin or from RingContract's software-side model | No local FEV receipt, DSL refinement or emission correspondence |
| TDM NoC and island arbiters | (a) | Register contracts exist; U-03 owns the missing Sail arbitration model, followed by block authoring | No local circuit or refinement; no work-conserving substitute is admitted |
| Fixed-function memory sequencer | (a) | M0.16 supplies the Sail-side sequencer; R1c-ii supplies modeled/reference integration before physical qualification | U-24 owns the first circuit-to-Sail refinement; Q22d owns the emission boundary |
| Other fixed-function sequencers | (a) | Their model, reset and external-primitive contracts must be named separately at entry | No blanket proof follows from the memory-sequencer case |
| Ensemble link endpoint | (a), Q23g | Link declaration and RingContract are interface evidence; endpoint RTL and physical link qualification remain separate | No endpoint RTL refinement or physical guarantee |
| Boot ROM and UART device path | (c) reference before closing work | Mocha supplies source references; the authored UART character wrapper and DTB/error route have standalone simulation evidence. Core-facing integration, physical UART timing and Sail route alignment remain open. ROM measurement/scrambling machinery is not the platform's RoT boot proof | No complete local device/SoC corpus or refinement receipt |
| Block device | R1c-ii/M5.3 logical contract | No block-device RTL exists in the selected Mocha source. The authored logical PIO wrapper has standalone progress, tear and reset simulation evidence under its synchronous backend contract. Durable host-image and real-medium backends remain open | No imported device or local refinement to inherit |
| Authored capability packages and map/decode helpers | Bring-up support | Local lint and format-algebra/vector checks cover the named functions and declarations | No whole-core or SoC proof is conferred by these helpers |
| Dedicated masked crypto datapath and ineffective-fault countermeasure | Route needs a register act | Functional cryptographic references are software models. No dedicated masked circuit and exact emitted artifact are qualified | No artifact-level masking, detection or combined-security close |
| Optional immutable module and host socket | Q24's staged route | Q24a fixes the boundary; Q24c/Q24d statement work precedes prototype and physical evidence | No fabrication correspondence or physical qualification from a protocol proof |

The S-class sentinel's placement and core identity must be explicit in a
composition's roster; this table assigns it no inherited theorem merely from
the class name. No imported core currently has a local route-(b) receipt. No
authored circuit currently has both a closing refinement and checked emission
correspondence. The applicable hardware ceiling is therefore no higher than
R-01-002b's evidence tier, and an incomplete route-(c) campaign is not itself
evidence that G2 has been achieved. The software certificate premise admits no
corresponding relaxation (R-01-002a).

## Five fallbacks, applied to the covered blocks

| Rejection | Per-block application at this opening | Remaining obligation and ceiling |
| --- | --- | --- |
| PMP backstop | On the C-class scalar core, missing whole-core closure leaves R2's rvfi/BMC, the netlist audit, then Sail-SV/FEV and Isla evidence to establish the permitted rung. For the planned RoT core, the same conclusion must use that core's own RV64-purecap implementation and route. V/M/FEC engines receive no protection claim from the scalar core's receipt; their own access checks and interfaces need their own coverage | Every affected core stays at its actual admitted tier. More evidence about CHERI does not restore the deleted independent failure domain |
| IOMMU | On the DMA/tag fabric and every V/M/FEC or device path using it, the single-address-space translation argument stands. The capability check and in-flight revocation remain local fabric/endpoint obligations. The TDM NoC's ordering and isolation are separately modeled; a scalar algebra test supplies neither | The authored fabric must close on (a); until then use the actual differential/check-path evidence and retain revocation work. A hardware walker remains excluded by R-15-010's admission test, not a fallback introduced by delay |
| MTE | On C and RoT scalar accesses and on V/M/FEC/device accesses through the shared fabric, its probabilistic-evidence exclusion is unchanged. Temporal safety still needs the linear/affine discipline, revocation budget and deterministic load filter at every applicable access path | A costly sweep may trigger the already named deterministic full-width generation-tag design-space option. A late RTL refinement does not trigger it, and no current block gains a temporal-safety theorem from this exclusion |
| Shadow stack | C and RoT backward edges remain dependent on their own CHERI implementation evidence. The forward edge requires the CHERI-TAL typed-callee result; sentries and compose-time singleton devirtualization are the stated fallback while that theorem remains open. V/M/FEC engines and memory/link sequencers without call/return control flow have no independent backward-edge claim | A scalar receipt cannot establish a different core's sentry or return behavior. No software region protected by CHERI supplies a disjoint hedge against a CHERI logic fault |
| Initialization plane | C/RoT registers and memory handed to a new owner, V/M/FEC private state and all fabric/device/NoC buffers require their own eager-zeroization and lifecycle evidence. The memory sequencer's modeled clearing order is not physical erasure evidence; R5/R5a own that boundary. Endpoint/module replacement must also revoke and sweep the prior grant's state | Eager zeroize is the disjoint substitute for predecessor-data disclosure only. Native capability-tag correctness still depends on the relevant core/fabric path, and zero data alone proves neither an invalid tag nor physical erasure |

The five positions are retained as R-17-039a states them. None reintroduces a
mechanism or raises a block's tier. For a newly added block, its owner must
extend the coverage and applicability rows before claiming the inherited
fallback. A declaration that a block has no callable code or secret state
needs its actual interface/state inventory as evidence.

## Masking and reduction verification plan

1. **Freeze the shared statement and foundation.** The probing-model task
   owns `proofs/ProbingModel.v`: circuit and wire semantics, stable observations,
   glitch expansion, consecutive-register transition observations, probe order,
   adversary and the named composition notion. Review joint positive and
   rejected witnesses, including unmasked leakage, strictly stronger glitch
   observations and register reuse. U-20 qualifies the probabilistic foundation
   against the locked prover and exact R-05-163 assumptions. A parameterized
   model is useful statement work and does not qualify that foundation.
2. **Develop the two composition halves against that revision.** The arithmetic
   task must connect any reused cardinality theorem to its actual probability
   statement, then prove the required order, fresh-mask and pipeline claims.
   The Boolean task owns arbitrary-order PINI over the NI/SNI ladder for the
   selected HPC/DOM gadgets, including AES S-box and Keccak chi instances.
   Neither half inherits the other's theorem from sharing field vocabulary.
   Prove the algebra-to-circuit correspondence at the exact consumer.
3. **Construct and check the actual datapath.** Bind operation, order, width,
   gadgets, pipeline/register reuse, randomness consumption, mask renewal,
   reset and execution schedule to an exact circuit/netlist identity. The
   DRBG's computational fresh-randomness premise is separate from the entropy
   source's rate. Budget expansion and draw recording in the crypto slot;
   neither a bare LFSR nor an unbudgeted random source meets R-05-004a.
4. **Join detection and the selected countermeasure.** Q3c fixes the fault
   transition relation. U-19 supplies the signature/token construction model
   and detection target; the actual instrumented binary/ROM result remains
   separately required. The masked permutation building blocks must carry the
   R-17-058d fine-grained detection/error-correction countermeasure by
   construction, with area, latency and randomness costs included in the
   exploration. No conditional theorem supplies a missing countermeasure.
5. **Prove the combined reduction on those artifacts.** For every fault allowed
   by the single-fault-per-activation hypothesis, prove either effective
   detection with the required acceptance withheld, or confinement to one
   share's computation within the probing bound at unreduced order. Quantify
   over both interventions in one execution; prove the case split is exhaustive
   and binds the actual activation, fault and probe observations. Do not weaken
   the fault domain or silently subtract a probing order to fit a proof.
6. **Audit and attempt refutation.** Compile, enumerate assumptions and recheck
   the exact constants; apply model-derived positive cases and meaningful
   mutations at each join. Run execution-aware netlist checks and external
   combined-security tools as producer-side evidence. A failed mutant that
   never compiled is not a killed semantic mutant. The independent R-05-150
   statement review remains separate from tool success.

Until this chain reaches the actual artifact, R-17-058c continues to forbid a
combined-coverage claim. Multi-fault attacks, beyond-order collection and the
safe-error oracle remain at R-17-058b; no third silicon axiom is introduced.

## Characterization, rehearsal and first silicon

The FPGA rehearsal checks the harness: deterministic stimulus, trigger and
activation alignment, bounded capture buffers, record integrity, fault/probe
case labeling, analysis reproducibility and deliberate known-leak controls.
It cannot qualify the silicon leakage axiom. Record FPGA and silicon results
in separate artifact namespaces so no replay promotes one into the other.

Before first-silicon collection, the campaign must fix the chip/netlist/layout
revision, specimen and process/voltage/temperature/aging scope, sharing order,
probe class and positions, bandwidth and sampling setup, maximum traces,
stopping rule, analysis thresholds and held-out confirmation procedure.
Unspecified limits refuse the campaign; an analyst cannot choose a favorable
trace cutoff after examining candidate results. The protocol must reserve
storage and acquisition time for its maximum trace count.

Test in this order: acquisition calibration and negative/known-leak controls;
individual gadgets and mask-renewal/reset boundaries; transition-sensitive
register reuse and adjacent-structure activity; each whole secret operation;
then concurrent public activity and permitted fault/probe combinations. Each
stage carries its own micro-benchmark and whole-operation identities, mask and
reset policy, trace count, exclusions and uncertainty. A detected in-model
leak or failure of a control rejects the claimed configuration and returns it
to its circuit/model owner. Failed controls cannot be waived by clean
whole-operation statistics.

Execution-aware netlist checking addresses the model's netlist half. Physical
measurements can refute faithfulness but never establish the axiom for every
silicon behavior. Delay imbalance, coupling, layout effects, collection beyond
the order and the relationship between order and measurement cost remain the
R-17-058a residual. Shielding is attenuation evidence and supplies no theorem.

## Owners and unpriced prerequisites

| Work | Existing owner | Entry decision still owed |
| --- | --- | --- |
| Circuit/leakage/adversary statement | Post-M10 probing-model task; U-20 for the foundation | Independent statement review and a qualified probability interface |
| Arithmetic composition | Post-M10 arithmetic task | Source theorem match and missing probability/order connections |
| Boolean composition | Post-M10 Boolean task | Exact HPC/DOM instances and arbitrary-order interface |
| Protected-sequence fault statement | Q3c | Reviewed relation before fault coverage is claimed |
| Detection construction model and theorem target | U-19 | Final-binary/ROM detection remains outside its model result |
| Signature instrumentation and final-binary detection | Artifact-admission obligation; no implementing checklist cell | Opening finding: assign and price the emitter and binary validation work before implementation |
| Ineffective-fault countermeasure and masked circuit | No authoring-route entry or priced construction cell | Opening finding: a register act must name the crypto core's route, then assign and price circuit construction separately from the reduction |
| Combined theorem | Post-M10 reduction task | Accepted detection, countermeasure and composition premises |
| First circuit refinement and emission correspondence | U-23/U-24 and Q22d | Qualified DSL, exact circuit/Sail objects and emitted-input correspondence |
| Imported-core FEV campaigns | R-15-090 hardening obligation, after R2/R3 | Opening finding: allocate per-core FEV work and tool/evidence ownership; R2/R3 do not price the complete deferred campaign |
| Silicon leakage characterization | This opening protocol states the work; no priced execution cell or evidence provider | Opening finding: assign the laboratory/provider and a separately priced FPGA-rehearsal and first-silicon campaign before commissioning |
| Memory retention, discharge and all-copy key lifetime | R5, R5a, M9a | Specimen and laboratory evidence; none is supplied by the leakage rehearsal |

These gaps are not absorbed into the reduction estimate. The
[unassigned-proof map](unassigned-proof-map.md) owns U-19 through U-24 and
already records the missing crypto-route and binary-instrumentation scopes.
No supplier or laboratory has been commissioned by this plan.

## Acceptance predicate

The opening artifact is acceptable when every listed core and net-new block
has an actual-evidence row, all five fallbacks retain their per-block ceiling,
the reduction joins exact model and circuit obligations, characterization
distinguishes rehearsal from silicon and names its limits, and each missing
prerequisite has an existing owner or an indexed opening finding. Update the
affected rows when a real receipt changes coverage. No entry at this opening
confers M10 completion, hardware qualification or combined security.
