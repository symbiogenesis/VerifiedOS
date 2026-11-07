# The Language Workflow and Artifact Comparison Contract

> Q20a's non-normative comparison protocol. Start with the [primary Vela design and examples](verification-strategy.md); its [language product contract](verification-strategy.md#language-product-contract) supplies the objective. [PLAN.md](../../../PLAN.md) owns execution state and the [requirements register](../../requirements-register.md) governs obligations. The inspection below lacks the copying implementations, qualified CHERI instance and complete artifact connections needed to run this trial; this contract records no productivity, performance or production result.

## Commissioning disposition

Q19c, Q20b and Q20c are canceled in [PLAN.md](../../../PLAN.md); their roles below belong to the retained protocol. Re-entry needs a concrete consumer blocked by the existing route, checked foundations, a usable environment, priced missing work and a finite stop threshold in a new suffixed checklist item. Q2b/Q3b, M1, M6 and M7 retain their backend, proof, admission and final-artifact duties.

The [whole-system proposal](extensions/unified-source-contract.md) separately covers proof, ISA and hardware authorship and Sail retirement. This software trial targets the pinned Sail model; it qualifies neither a replacement model nor a hardware backend.

## First-release qualification and adoption

The [bounded first release](first-release.md#release-boundary) follows
[its own delivery sequence](../../../PLAN.md#vela-first-release-delivery).
Q19c/Q20b/Q20c remain canceled; this sequence neither reruns nor changes their
frozen experiment. Separate three decisions:

| Decision | Acceptance and stop rule |
| --- | --- |
| Technical feasibility | Construct checked concrete primitive/representation laws and a source-connected useful component at its declared endpoint. Missing laws, vacuous entry states or exhausted investigation budgets stop dependent implementation and produce a named blocking result. A weaker endpoint cannot satisfy the gate. |
| Recurring developer value | An independent client, a contract change, a representation change and a semantics-preserving refactor measure authoring, annotation, review and repair effort separately. Record diagnostics and checking latency, resource costs and unsupported patterns; hidden manual rewrites or repeated proof reconstruction count against the result. Freeze the compared tasks, baseline and material-benefit criterion before observing results. |
| Product adoption | Record establishment, shared maintenance, per-client costs and measured target envelopes. Projected amortization states its workload and uncertainty; the first two small clients need not repay all foundational work. The decision must name an independently reviewed useful benefit and acceptable recurring cost, with no reduction of any mandatory guarantee. |

Every candidate must preserve correctness, authority, confidentiality, declared
termination/progress and hard admission limits. Performance comparisons use the
same endpoint and target. A selected optimization may trade code size, cycles or
reserved space within a separately reviewed envelope; report each affected case
and dimension, including regressions. Missing target measurements give no
performance verdict. Never require a universal improvement across every metric
as a substitute for the product's actual limits, and never average a safety or
hard-budget failure into a passing score.

The table under [accounting thresholds](#accounting-and-decision-thresholds)
continues to govern only the canceled Q20 experiment and any explicit replay of
that exact protocol. Its two-client break-even and Pareto-style optimization
conditions are not first-release funding or acceptance requirements. A new
comparison freezes its own subject, evidence endpoint, workloads and envelope
before execution; safety and independent-intent requirements are unchanged.

### Representation-transfer comparison

The independent package trial's representation-change probe starts with ordinary
Rocq relations, explicit transport lemmas and generalized rewriting over a pure
value representation the client actually needs. Freeze the public laws, baseline
and repeated proof steps before comparing automation. Reprove the changed
instance laws and replay the generic client theorem unchanged; record handwritten
transport, generated terms, review and repair separately. Concrete CHERI memory,
ownership and primitive-operation laws retain their foundation owners.

The [CoqEAL/Trocq candidates](verification-strategy.md#existing-tooling-and-implementation-owners)
become an implementation option only when that baseline exposes recurring work
worth automating and a new checklist item prices the selected package's exact
prover/plugin closure, port, licence reading and maintenance. Keep the locked
prover and assumption policy. Stop the candidate at its declared budget, an
unresolved compatibility/assumption boundary or failure to meet its predeclared
maintenance-benefit criterion; retain the native transport and useful checked
lemmas. A generated proof must concern the same relations and client laws, with
no strengthened precondition or weakened result. This comparison belongs to the
first-release package trial and does not reopen Q19c/Q20b/Q20c.

## Clients and baseline evidence

**P, parser destination initialization**, is Q2b's copy-once ring-descriptor check with generic bounded fill of its fixed destination. **S, private service staging**, is M7.1's held-out sequential disjoint copy into private staging under M6.4's declaration. Q2b and M7.1 own the implementations and independent baselines; Q19c owns the generic interface, proofs and concrete instance; Q20b owns the single held-out adaptation record shared by both trials.

Inspection revision: `e6391c6aacb5a89141250d133f8875efa41a994e`. The table describes evidence at that revision. Before comparison, freeze fresh immutable revisions and content digests for every implementation. Record a missing implementation as `unavailable`, never with its statement's revision.

| Input at the inspection revision | What can be read | What it does not supply | Trial status and owner |
| --- | --- | --- | --- |
| [DescriptorCheck.v](../../../tools/bedrock2-lowering/DescriptorCheck.v), `Descriptor.descriptor_check`, `spec_of_descriptor_check`, `descriptor_check_br2fn_ok` | A read-only header check, an unchanged byte-array/frame postcondition and its Rupicola-to-Bedrock2 relation | No destination initialization, byte copy, CHERI memory theorem or final-image correspondence | P implementation baseline unavailable; Q2b owns the extension |
| [The lowering recipe and evidence](../../../tools/bedrock2-lowering/README.md), [emitted-output digests](../../../tools/bedrock2-lowering/DIGESTS.md) | A reproducible host experiment with a recorded boundary audit | Its C printer and recorded backend experiment do not establish a current CHERI byte endpoint; the older backend observation is not a claim about every later revision | Historical evidence only; Q2b checks the actual producer at entry |
| [CopyRingService.v](../../../proofs/CopyRingService.v), `copy_once`, `StaysInsideTheValidatedExtent`, `ReadsTheSourceOnce`, `DoesNotVaryWithTheSecondImage`, `RefusesAnOverlongLength` | A statement over `buffer` and `copy_run`, including a rejected rereading copier | `buffer` carries natural-number length and datum, not byte memory; `cr_reads` is a model field, not a measured load count. No implementation of staging or atomic byte snapshot follows | S implementation baseline unavailable; M7.1 owns realization |
| [The ring declaration](../../../interfaces/ring-reference.json), [RingContract.v](../../../proofs/RingContract.v), and `CopyRingService.svc_op_record` | Generated encoding and capacity inputs; the service's staging and slack fields | Demo values are no composed device or staging-lifetime decision | Freeze actual selected declaration and composition at trial entry; M6.4/M7.1 retain ownership |
| [Q1's product gate](../../implementation/contracts/product-gate.md) | Product limits, clock separation and report rejection rules | No ratified physical envelope or measurements for these components | Apply relevant limits only at the endpoint that can decide them |

The [foundation map](../../hardware/cheri-foundation-map.md) assigns missing representation, primitive and machine connections; trial entry requires their checked artifacts. The [core design](core-design.md) scopes wider source mechanisms, and the [compiler-route contract](compiler-route-contract.md) owns route comparison and conditional amendments. This protocol selects no route or changed compiler duty.

### Freeze and independence

Before adapting P, Q2b freezes its manual baseline's operational definition, intended behavior, executable implementation, theorem subjects and assumptions at the candidate's endpoint. Author it independently of generated output; a transcription is invalid. Historic effort without contemporaneous logs stays unknown. Recreating a known solution measures reconstruction or maintenance, not original authoring.

Before adapting S, Q19c freezes and hashes the interface, generic theorem statements, concrete instance, qualified environment and review. M7.1 may independently develop S's baseline, but S supplies no pre-freeze API feedback. If it does, classify S as another development client and keep the held-out trial unopened until an independently reviewed Q20a amendment names a fresh consumer, owner, baseline and budget. Renaming S, concealing feedback or choosing a replacement after seeing results is invalid.

Name the experiment author, baseline author and a reviewer who authored neither the compared implementation nor its expected-behavior checks. Review the frozen cases and cost ledger under [the checklist conventions](../../../PLAN.md#checklist-conventions). Q19 or the existing compiler owner qualifies newly incorporated upstreams from their pinned licences and dependency notices; this contract imports no code.

## Operational subset and observations

The pilot uses sequential, total, bounded byte-buffer code: fixed destination capacity, runtime length, erased bounds evidence, explicit failures and a callback-shaped scoped loan. Each candidate has one authoritative executable definition and independently reviewed behavior. Generated implementations, representations and proofs have named provenance and are regenerated rather than hand-repaired.

Retain runtime branch inputs, including lengths and result discriminants. The representation relation specifies byte order, integer widths/overflow, capability provenance/bounds/permissions, initialization, layout and abstract-owner/concrete-byte correspondence. Its laws connect to the admitted CHERI semantics; a generic byte model or printer-assigned capability meaning cannot supply that connection.

For both clients freeze declaration-owned capacity `C`, a stable readable source extent, an exclusive destination of capacity `C` and their disjointness witness. Check representations of `C`, indices and lengths, receiver-relative bounds and symbolic overflow cases too large to execute. Derive target input sizes from the frozen owner rather than duplicate layout constants.

### P: composed positive client

P combines the selected mechanisms in one executable definition and theorem under this behavior contract; the steps define neither implementation syntax nor existing code:

1. Enter a scoped callback with the destination owner, the stable source read authority and a runtime length `n`. Validate `n` against the source extent and `C` before using it for a source access, destination index or pointer calculation.
2. Fill the entire destination with zero using a total repeatable callback returning the zero byte. The callback captures only stable public values, holds no competing destination loan and has no allocation or external effect. Its invocation count follows the destination bound, while capture and write permissions are proved separately.
3. If the length is rejected, return the declared invalid result with the initialized destination owner restored. Otherwise copy the selected source prefix into the private destination once, then check the staged header using the existing descriptor-check interpretation. Every validation read after copying is from the private destination.
4. Return success carrying the runtime `n`, its bound witness and the initialized destination owner, or invalid carrying the same initialized owner and the appropriate failure evidence. The original scoped loan cannot escape in either result. No branch changes destination capacity. The success result does not claim session-table validation that `DescriptorCheck` leaves to the receiver at use.

Every exit preserves source and unrelated frame, fully initializes the destination and restores ownership exactly once. For admitted `n`, the destination contains the sampled prefix followed by zeros, even on an invalid header, and status agrees with `Descriptor.descriptor_check` on that prefix. A rejected length leaves an all-zero destination and reads no source byte. Reconcile any different failure writes before freezing; candidates must implement the same program.

This exercises R-05-124's destination initialization, R-12-012a's receiver validation and selected descriptor encodings. Complete parser, session-validation, cross-compartment initialization, Byzantine-peer and atomic-snapshot theorems remain outside this immutable-source sequential pilot.

### S: held-out staging client

S applies the frozen generic disjoint-copy interface to private staging. Before adaptation, its baseline fixes M7.1's selected lifetime, capacity, initial state, result and exact failure status against `svc_op_record`; the statement artifact leaves these choices open. Freeze accepted payload extent `d` separately from storage capacity `C`, prove `d <= C` and test both boundaries: staging slack permits no larger payload. Starting with an initialized destination, copy admitted `n` bytes, preserve its suffix, source and unrelated frame, and return the owner on success and error. Rejected lengths/extents produce the declared refusal with no source read or destination write.

The successful payload is the first acquired source prefix. Vary a modeled later image while fixing that prefix to check `copy_once`'s abstract behavior. Adversarial atomic snapshots, concurrent SPSC, publication, notification, cancellation, DMA and revocation require separately owned connection evidence.

Compare each client only with its matching baseline, preserving P/S's different initialization behavior. Shared generic operations must support both without client-specific CHERI facts in the generic theorem.

## Selected composition and rejection cases

Every selected row below must compose in P. Missing mechanisms make the trial unavailable until their implementation is separately owned and priced. These prospective cases and isolated feature examples supply no executable evidence for P.

| Interaction in P | Positive obligation | Well-formed negative neighbor and intended failure |
| --- | --- | --- |
| Stable indices and erasure | Use runtime `n`, fixed `C` and an erased `n <= C` witness in the bounded copy; retain the success/error tag | Erase `n` while branching on it, or retain the bound witness after changing the bound: reject at phase or stale-bound obligation |
| Mutation and dependency | Fill and copy change contents while preserving destination shape; old content facts are consumed | Use a pre-fill content snapshot to justify the final payload: reject at memory representation or functional postcondition |
| Scoped loans and results | Both callback result branches return the full owner and end the loan | Return the loan in the error payload, or propagate error without the owner: reject at escape or restoration obligation |
| Reusable callable, effects and count | Invoke the zero-byte callback at the proved loop indices with permitted captures and no external effect | Invoke a consuming callable twice; conceal a captured destination write or allocation; alias its capture with the exclusive output: reject respectively at usage, effect or disjointness obligation |
| Typestate and branch joins | The fill establishes whole initialization before either exit; the result's variant has its own bound and status facts | Skip one fill iteration yet claim whole initialization, read an uninitialized byte, or claim a successful parsed result on error: reject at initialization or branch postcondition |
| Name and instance resolution | Rename locals, qualify the buffer operation and import an unrelated module while retaining the same resolved constants | Silently select another representation or effect instance: require preserved meaning or explicit ambiguity, never stale acceptance |
| Dependent computation and automation | Compute bounded cases and replay equation lemmas and the exact transitive assumption audit | Add global UIP, leave a generated obligation open, or produce an executable term stuck on the selected concrete input: fail the relevant assumption, completeness or computation check |

The last row uses only Q19b's qualified definition mechanism, with no new kernel conversion rule. A proved equality principle for the selected decidable index is permitted; a global axiom is not. Saved proof-search reconstructions replay without the search service.

Straight-line borrow inference, a loan returned beyond the callback, disjoint-field and nested reborrow inference, resizing, suspension, cancellation, handlers, concurrency, general grades and a new frontend are **unavailable in this pilot**. General isolation, observation-policy and binary-leakage composition are **outside its source claim**. Q21's separately priced eventual-core trial decides those mechanisms. SPSC, DMA and atomic snapshots are **inapplicable to the sequential slice**, not established absences of the full system.

### Expected behavior, witnesses and mutations

Before candidate proofs are authored, an independent reviewer freezes expected bytes/status and checks from the client contract and format, without evaluating the candidate as its own oracle. Supply inhabited entry states satisfying the actual theorem hypotheses and these classes for each baseline/candidate pair:

- Empty input, a single byte, exactly full input, and one beyond the declared capacity; S additionally tests `d` and `d + 1` independently of `C` and `C + 1`, including nonzero declared staging slack. P additionally covers every operation variant and every truncated field position the descriptor declaration admits.
- The last valid and first invalid index, malformed tag, direction, content and optional-deadline discriminants, and a flag outside the declared set. Retain distinct bytes at distinguishable positions to expose swapped reads or stores.
- Receiver-relative offset/length boundaries and arithmetic wraparound, proved at the selected word width. If a case is too large to execute, retain the proof case and report target execution as unavailable rather than allocate a different smaller substitute.
- Destination residue distinct from source bytes; nonempty frames around both buffers; adjacent disjoint ranges; and an overlap variant that is rejected at disjointness. Verify source and frame bytes on every exit.

Freeze wrong-store, off-by-one, omitted-fill, bad failure-result and second-image variants that are syntactically valid and reach the intended obligation. Distinguish malformed/stillborn construction, intended kill, unrelated failure, timeout, unsupported and survivor. Parse/type/compile failures elsewhere supply no ownership/specification evidence; any required survivor prevents success.

Use [oracle, seed and QuickChick](../../../tools/README.md#the-three-generators-and-what-each-answers) where supported; retain independent specification review and keep test guards out of theorem premises. Name each guarantee's theorem. Removing a required frame-preservation theorem while retaining operation laws must make P's frame-requiring client fail for that omission. Profile flags and source ownership alone establish no adversarial-context isolation.

### Change and weakening probes

Change P's accepted bound from `C` to `C - 1` at unchanged nonzero capacity. Entry needs a concrete well-formed descriptor accepted at `n = C` under the frozen declaration and representation hypotheses; otherwise revise and independently review the probe before entry. The old success claim and cached feedback must become stale or fail before repair. Independently review the new behavior and expected table, regenerate implementation, renew affected source/representation/artifact evidence and record all source, contract, glue and proof edits. Apply the same change to the baseline before comparing repair cost.

Remove S's successful copied-prefix equality while retaining bounds, initialization, frame and status. A wrong-store implementation can satisfy that weaker postcondition, but the independent expected-byte check must reject its output on a nonuniform source. Otherwise record a specification gap and refuse success; inhabitance, proof completion and memory safety cannot close it.

Separately test a semantics-preserving local rename and helper extraction, an unrelated import, and an instance representation change preserving public laws. After reproving changed instance laws, replay the generic theorem unchanged. Separate saved-term replay from tactic/search rediscovery; retain search seed, limit and reconstructed proof. Changed source maps, resolved constants, representations, contracts or dependencies invalidate affected evidence despite identical-looking goals. New holes, admissions or undeclared assumptions fail R-05-018a/R-05-018b acceptance under the exact R-05-163 declaration.

## Measurement record and sampling

Q20b's machine-readable record has a generated reading view. Its owner must implement or select a supported recorder; the fields below are not an existing host-checker tool. Retain each measurement's raw log, units, predicate, instrument revision and uncertainty. Missing values are `unknown`, inapplicable axes `n/a`; neither means zero.

| Record family | Required identity or observation |
| --- | --- |
| Trial | Contract and review revision, P/S identity and development/held-out status, named authors/reviewer, entry decision and case-selection record |
| Source | Baseline/candidate source closure and commit; operational definition and independent behavior; representation and erasure; source maps, resolved names, elaboration/desugaring and imported contracts |
| Proof | Exact Rocq, libraries and plugins with configuration; interface and instance digests; theorem constants and transitive assumptions; batch, assumption and `rocqchk` evidence; search seeds and limits |
| Target | Profile, pinned Sail term and model configuration; compiler, optimizer, assembler, linker and composer revisions/options; ABI, link context and layout; memory classes and slot configuration; final image and evidence digests |
| Effort | Setup, learning, authoring, review, diagnostic investigation, regeneration, proof repair and shared maintenance event records; source/contract/glue/proof diffs; duplicate operational implementation |
| Host measurements | Diagnostic latency; cold and warm batch/kernel replay elapsed time, CPU and maximum resident memory; active worker count, machine and cache state |
| Target measurements | Per-case code bytes, stack and peak storage, allocation/runtime support, memory accesses and target cycles, with their individual derivation or instrument |
| Decisions | Every positive and negative result, first intended obligation, mutation class, change invalidation, specification-gap status, endpoint-qualified cost comparison and decision |

Use monotonic elapsed intervals and UTC event ordering. Each effort event has one actor, workstream owner, category, start/end and identifier. Pause active authoring during unattended builds; charge failure diagnosis separately. Preserve overlaps rather than sum them into wall time. Record successful, failed and abandoned agent attempts and all review, including the integrator's.

Observe authoring and the held-out adaptation once, retaining original logs; learned repetition is no independent sample. Time each exact batch artifact with one cold run, one unreported warm-up and five retained warm runs. Replay the frozen positive/edit/negative diagnostic sequence five times per workflow, alternating workflow order each round. Report raw durations, nearest-rank p95, median, maximum and source/environment identities. Avoid competing builds; record interruptions and rerun only the affected round, labelling both observations.

Diagnostic latency runs from submission of the completed edit to source-bound feedback on its first unsatisfied obligation. Record prompt stale/unfinished messages separately; they resolve no obligation. Timeouts retain their status, never cached success. Neither latency nor batch timing supplies batch proof acceptance or attended-authoring estimates.

Use C#/Dafny and Rust/Verus comparators only where their qualified subsets express the same bounded algorithm and behavior. Record unsupported features, manual restoration and proof endpoint. Weaker endpoints permit navigation, error-location and latency comparisons, but no authoring-productivity claim against stronger CHERI evidence. This contract commissions no installation, port or language server.

## Accounting and decision thresholds

Freeze these contract-owned selection thresholds before Q20b/Q20c. They are experimental rules, not measurements or predictions. An amendment restarts affected comparisons under a new protocol identity and preserves the prior outcome.

| Parameter | Threshold | Ground and interpretation |
| --- | --- | --- |
| Correctness and evidence | Every selected positive meets its exact endpoint; every required negative fails at its intended obligation; zero new admitted assumptions, stale acceptances or undetected selected weakening | The claimed guarantee is conjunctive; averaging safety failures would remove its meaning |
| Interactive diagnostic latency | p95 at most 2 s for the frozen incremental sequence | The pilot tests feedback usable within a local edit loop. Slow batch proofs remain separately measured, so an expensive kernel replay does not masquerade as an interactive result |
| Replay limit | Each warm replay completes within 10 min and each cold replay within 30 min | Bounds the experiment's usable edit/rebuild loop. A timeout leaves that attempt undecided and supplies no proof rejection; repeated limit failure rejects workflow adoption |
| Held-out recurring effort | Candidate upper bound at most 0.90 times the matched baseline lower bound, including learning, adaptation, review and the specified maintenance probes | A predeclared margin makes a nominal difference inside recording uncertainty insufficient for expansion; this is no forecast of a saving |
| Full accounting boundary | Conservative `NetSaved` strictly positive at the selected evidence endpoint | Both selected clients must repay all attributable setup and shared work within this bounded pilot before expansion is credited |
| Native footprint and runtime support | No larger declared stack or peak storage, no new allocation or undeclared runtime support, and unchanged hard resource bounds versus the matching manual baseline | The comparison cannot buy speed by consuming a larger admitted resource envelope |
| Native code and cycles | Final code size and each measured case's target cycles at most 1.05 times its matching manual baseline; no applicable hard bound regresses | A bounded experimental tolerance for competitive output, with failures exposed per dimension rather than hidden in a combined score |
| Selected optimization | Optimized cycles no greater than the same candidate's unoptimized cycles on any selected case, and total optimized code bytes no greater | This bounded trial retains only an optimization that preserves both dimensions; a deliberate trade needs a separately reviewed comparison |

Account from the first attributable qualification/interface event until P, S and the change probes reach the selected endpoint. Q20b closes source-workflow accounting; Q20c extends that ledger to final artifacts without inheriting a production saving. Further consumers, future targets and imagined edits earn no adoption credit.

Use the strategy's [break-even equation](verification-strategy.md#where-time-might-be-saved) without adding another overlapping savings formula. The ledger assigns its terms as follows:

| Term or shared cost | Unique owner and treatment |
| --- | --- |
| Library/interface establishment `L` | Q19c; include attributable Q19a/Q19b qualification and initial learning here or at its original owner with a cross-reference, never at both |
| Shared maintenance `M` | The owner changing the common interface/tooling; client repair stays in that client's event series |
| Concrete instance `P_j` | Checked foundation owners identified by Q2c and Q19c's concrete instance work, attributed once to the actual endpoint; the foundation map's scoping cost is distinct from implementation cost |
| Baseline client effort `B_i` | Q2b for P, M7.1 for S; include the matched source, proof, review and maintenance work and baseline-specific prerequisites |
| Candidate client effort `A_i` | Q20b's adaptation and maintenance events, including its learning, glue and review; S's one adaptation is the same record Q19c consumes |
| Representation, lowering and final evidence | Q2b, Q3b, applicable M1 compiler/optimizer owners and artifact-validation owners; Q20c joins their actual evidence and counts only its own integration effort again |

Separately record each route's full establishment, remaining work from the frozen revision and recurring maintenance. Count common foundations once with a transparent allocation/cancellation rule. Retain baseline sunk costs when charging candidate setup; another owner's newly needed source-to-byte work is not sunk. Missing historic records leave full-establishment comparison unknown; report observed recurring work separately.

Keep human attended hours, summed agent-session hours, machine elapsed time, CPU time and calendar duration separate, without conversion. State each break-even/adoption claim's effort series and endpoint; attended-work savings require complete attended records. Conservative saving uses baseline lower bounds and candidate/setup/maintenance upper bounds; absent credible bounds, report unknown. Declare the counting predicate for duplicate executable files and changed operational lines. An accepted candidate has no manually maintained second executable implementation.

Correctness/evidence failure rejects integration. A complete comparison missing an effort/native threshold rejects expansion at that endpoint while preserving useful component proofs. Missing artifacts/logs, unsupported interactions or insufficient timing leave it **unopened or undecided**, without favoring another route. Later-consumer projections are separate scenarios with unknown costs and cannot reduce checklist estimates.

## Target and production artifact protocol

Freeze an actual CHERI target and producer closure capable of P and S, subject to the provisional profile and existing compiler duties. Record actual revisions, full options, representation, ABI, code/data placement, memory classes, linked environment and schedule; missing fields block comparison.

Use identical target, backend and environment for each manual/generated pair, including malformed/refused inputs. Compare optimized output with the retained unoptimized artifact from the same source closure, changing only eligible optimization switches. Different backends belong to the [compiler-route comparison](compiler-route-contract.md), outside this same-backend measurement.

Separately measure executable code bytes, stack, per-class peak storage, runtime/allocation support and source/destination/capability memory traffic. Record functional model behavior per executable vector. Model cycles require an actual timing-annotated instrument, not retirements, host runtime or an unqualified counter; otherwise cycle comparison is unavailable. Replay deterministic cases from recorded initial states and require identical results and supported cycle counts; investigate disagreements. Worst-case claims need exhaustive finite coverage or a checked bound. Label sampled maxima and symbolic overflow cases accurately; neither is measured worst-case execution.

Q20c entry requires accepted Q20b workflow, usable Q2b/Q3b implementation/connections, reviewed Q3c fault model where used, the functional backend, applicable M1.3/M1.3a optimization evidence and assembly/link/image validation and admission artifacts. R-05-020/R-05-023a/R-05-024/R-05-026 retain their exact logic, source correspondence, adversarial-context and tier duties. Bounded emission/source ownership cannot waive them, and Q20c's integration budget builds no missing compiler, logic or certificate machinery.

Promote the exact final optimized image exercised, binding fresh source correspondence, assembly/link/image validation, admission, resource and applicable security evidence to its bytes and source closure. Changed-byte, relocation, linked-contract and compiler-configuration variants must invalidate affected evidence and fail until renewal. A digest establishes identity only. Retain accepted bytes without recompilation, patching or rewriting.

Apply [Q1's limits](../../implementation/contracts/product-gate.md#2-the-limits) to composed-system claims, keeping `host_elapsed`, `target_model_cycles`, `fpga_observed` and `silicon_measured` separate. Host proof timings establish no device latency, energy or quality limit; converting model cycles to wall time needs latency and operating-point evidence. Component trials ratify no proposed Q1 envelope or unexercised product workload.

## Contract acceptance and remaining gates

Q20a contract acceptance requires a consistent executable protocol for its clients, baseline freeze, composed/negative cases, behavior/weakening probes, source/evidence identities, sampling, cost allocation and thresholds, conditional on the stated prerequisites. `python tools/check.py` checks document consistency, not protocol execution or semantics.

Review must establish that independent expected-byte checks detect the weakening, negatives reach their intended obligations from well-formed inputs, and entries inhabit their theorem premises. Check all exits together and reconcile source/IR boundaries with Q21 and foundation owners. A reasoned rejection identifying an unresolved interaction is an acceptable design outcome.

Successful Q20b supplies **source-verified workflow evidence**; a complete source-to-image relation adds **artifact-connected evidence**. **Production-qualified** additionally requires Q20c's complete applicable admission, resource, security and target record. Hardware refinement and silicon measurement remain separate. This contract closes no implementation or proof prerequisite.
