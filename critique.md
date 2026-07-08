# Critique of the Specification

Overall: this is unusually internally disciplined for an early-stage spec — the admission-test framework and the "delete rather than defend" rule are applied consistently enough that most cheap contradictions are already gone.
What remains are contradictions in the *axioms*, a handful of hard technical inconsistencies the cross-reference machinery has papered over, and several places where the spec's own logic demands a simplification it doesn't take.

## Self-contradictory goals

**1. "Engineering is free" is double-booked.**
The axiom is invoked to force the expensive choices — re-proving seL4's design end-to-end in Coq rather than inheriting the Isabelle proof, [github](architectural-alternatives.md) re-proving VeriBetrFS's B^ε-tree in Coq/Iris, [github](verification-maximal-os.md) SSProve over EasyCrypt — and then suspended wherever schedule pressure appears: libcrux/HACL* as an explicit interim F*/Z3 widening, EasyCrypt adopted where it accelerates delivery, aiT and Binsec/Rel as unverified complements.
[github](verification-maximal-os.md) If engineering is free, interim widenings are incoherent — you'd simply wait for the Coq-native artifact.
If interim widenings are necessary, the axiom is false and the seL4/VeriBetrFS/SSProve re-proof decisions must be re-litigated under a real cost model, where inheriting Isabelle may win.
Right now the spec runs two cost models and picks per decision.

**3. Proof-gated updates versus hyper-security has an unpriced MTTR.**
Every fix to the most-attacked surface (RRC/NAS parsers) must re-derive a Narcissus parser, re-prove Tier-1 flow theorems, pass generation admission, and possibly clear delta re-certification when protocol behavior changes.
[github](verification-maximal-os.md) Patch latency = proof latency.
For a live remote zero-day, time-to-remediation is a first-class security property; the spec budgets detection latency (sentinel) but never remediation latency.
This is a genuine G1/G2-versus-process contradiction, and it's the same argument the spec itself deploys against fusing the radio (immutability belongs at the RF envelope because a fully fused radio could never patch its most-attacked surface) [github](verification-maximal-os.md) — applied one level up, it indicts proof-gating without a fast-path.

**5. Defense-in-depth admissibility is case law, not statute.**
The PMP backstop was admitted as a disjoint failure domain while MTE, shadow stacks, and Harvard split were rejected as redundant-with-CHERI — an inconsistency since resolved by dropping PMP too (redundant against formally-verified CHERI; the drop-PMP disposition, which articulates the missing criterion as *verify rather than hedge*).
The broader point stands: that criterion should be hoisted into a standing admission-test clause rather than left as per-case litigation.

---

## Internal contradictions

**6. Static composition + NI-over-a-fixed-graph vs. the powerbox.**
§7 mandates a fixed, machine-checked component graph with no dynamic privilege creation in the base, [github](verification-maximal-os.md) and §8 states non-interference as a theorem over that fixed graph [github](verification-maximal-os.md) — while §8 also routes dynamic grants through a trusted-UI powerbox [github](verification-maximal-os.md) and §12's service manager performs capability re-grant on restart.
[github](verification-maximal-os.md) Runtime user grants mutate the flow policy; either the NI theorem quantifies over all potential powerbox edges (weakening it to near-vacuity for user data) or every user-granted channel sits outside the proven policy — the dominant real-world leak path.
Worse, the powerbox and the supervision tree are authority-minting components that don't appear in the exhaustive TCB: [github](verification-maximal-os.md) a compromised init re-grants everything; a compromised compositor (Tier-1, non-TCB) spoofs consent UI.
"Secure-path UI" is asserted with no mechanism, and any mechanism puts the compositor or a sub-component into the consent TCB.

**15. seL4-NI lineage is thinner than implied.**
The upstream non-interference proof exists only for non-MCS, unicore, static-partition configurations and is the least-maintained layer of l4v.
NI over multikernel + purecap CHERI-C + powerbox dynamics is a new theorem wearing an old name; the maturity transfer claimed in §5/§8 applies to none of it.

**16. Anti-rollback for mutable user data is unworked.**
The user-data root sealed to the RoT with a monotonic counter implies counter updates at CoW-commit frequency; OTP counters can't sustain that and flash-backed counters need their own freshness story.
High-rate authenticated freshness is a known-hard problem the spec waves at in one clause.

---

## Gaps (not contradictions, but unbooked)

USB-PD negotiation is a firmware-controller function everywhere today and escapes the EC-dissolution list.

Capacitive touch controllers universally run tuned DSP firmware;the register-slave-scan claim implies a net-new raw-AFE + host-DSP co-design, unbooked.

Biometric matching (implied by the credential-vault language) has no compartment assignment.

The RRC/NAS crown jewel is really a *transcription* risk: hand-encoding 3GPP ASN.1 into Coq moves the vulnerability from the parser to your transcription of thousands of pages of grammar.

Finally, a document-engineering point that is itself a goal violation: §5 makes independent spec review a release gate, but 133 KB of multi-hundred-word single bullets with ten-deep cross-reference chains is engineered to defeat review; normative content needs decomposition into numbered atomic requirements.

---

## Low-hanging simplifications

The biggest: **TCB item 3 is oversized by its own logic.**
The system-integrity path needs only Merkle read-verify plus a two-slot atomic root flip and anti-rollback check — not the full L0–L3 journal/B^ε-tree/FS stack.
Move the entire four-layer filesystem wholly non-TCB and put a ~10× smaller verified reader/transactor in its place; this is a pure TCB shrink the spec's organizing principle demands.

Fifth: **ship v1 Wi-Fi-only.**
This deletes the eUICC (achieving literally zero foreign computers), carrier certification risk, the HARQ hard-real-time class, and AKA key hierarchy, while still demonstrating the dissolved-radio thesis against the 802.11 attack surface.

Sixth: defer the browser — it's the largest porting program in the roster and orthogonal to proving the OS thesis.

---

## Existing projects for open workstreams

- **hs-to-coq** (Penn): mechanically translate seL4's Haskell executable spec to Gallina — directly replaces the plan's hand-translated step, so the Coq trust base inherits the scrutinized upstream artifact rather than a fresh hand transcription.
- **RefinedC and CN** (both Coq/Iris-adjacent, CN already exercised against CHERI C): existing foundational C-verification front ends that substitute for inventing the Goose-for-C / CompCert-C-plus-VST(Iris) workstream; BlueRock's BRiCk is the industrial-scale reference point.
- **Katamaran**: separation logic over Sail for exactly the Cerise-style universal-contract statements — the missing tool between Isla and Islaris in your G3 stack.
- **Microkit + LionsOS + sDDF** (Trustworthy Systems): the nearest living whole-system relative of §7 static composition + §12 rings; you cite the sDDF idiom but not the composition tooling, which is directly harvestable for the init/composition artifact.
- **asn1scc** (ESA's open uPER compiler) + 3GPP's machine-readable .asn modules: build a small verified ASN.1→Narcissus front end consuming published modules, so the crown jewel shrinks to that compiler rather than hand transcription; asn1scc doubles as the differential oracle.
- **srsRAN/srsUE and OpenAirInterface UE** (cellular L2/L3 reference), **openwifi** (802.11 PHY/MAC — including open FPGA RTL usable under your open-RTL mandate; its FPGA fixed-function low-MAC meeting the 10 µs SIFS ACK turnaround is the firmware-free start-from for the §15 split-MAC link-layer timing sequencer), **GNSS-SDR**, **aff3ct** (FEC oracle): the radio stack currently has no named start-froms at all.
- **smoltcp, rustls (custom crypto provider), hickory-dns, roughenough**: the §12 network compartments, unnamed in the spec, are mostly assembled from these.
- **tiny-skia + cosmic-text/swash today, Linebender's CPU-renderer work as it matures**: the shared software-render substrate; note no viable no-JIT software 3D exists (llvmpipe JITs), so an RVV rasterizer is genuinely net-new.
- **wasmi** (pure-Rust interpreter) for the sanctioned plugin engines; **Boa/Nova** for the Servo JS gate.
- **Cranelift + Crocus-verified ISLE lowerings**: a pragmatic (SMT-trust) interim for the certifying Rust→CHERI compiler while the Coq-native one is built — same slot as Binsec/Rel and aiT in your interim taxonomy.
- **CompCert-CT** (Barthe/Blazy lineage) exists as a fork — worth naming as the concrete artifact §5 leans on.
- **CryptOpt** (PLDI 2023; Fiat-Crypto / MIT-Adelaide) — a randomized-search superoptimizer whose emitted assembly a **Coq-verified equivalence checker** validates back to the Fiat-Crypto spec, beating GCC/Clang at top optimization and at times hand-written asm.
  It is the concrete vehicle for field-arithmetic performance *without* a Jasmin-style verified backend — the trusted artifact is a small checker, not a second compiler (straight-line field arithmetic only; x86-64 today, CHERI-RISC-V retarget net-new).

---

## Radical rearchitecture candidates

**E. Physical bifurcation of the radio.**
Instead of coherence islands on one die absorbing the booked residuals (shared die power/thermal/refresh/PRAC coupling, shared mask set), put the radio stack on a second, identical, attested instance of the same die linked by a ring-over-SerDes — not a foreign computer, a second copy of the one computer.
It deletes the highest-value cross-domain residuals outright and simplifies the island machinery on the main die, at the cost of a package and the inter-die link becoming a new (but IDL-shaped, Narcissus-parsed) boundary.

---

## Goal-aligned refinements (cheaper proofs, cheaper performance, better tooling)

Two levers the goal function — *engineering is free; trust is the scarce resource* — rewards but the spec under-spends: buying back performance that costs no trust, and pulling *proof-production* tooling that costs no trust.
Each is the platform axiom taken one more turn, not a new principle.

### Performance that costs no trust

- **The off-device optimizer's aggressiveness ceiling is SMT-backed search, and the doctrine licenses it only halfway.** performance-recovery-todo.md already aims "unbounded offline search … at the hottest routines" under the §6 *a-compromised-analyzer-cannot-mint-a-certificate* theorem — but stops at the word "superoptimization."
  The same theorem admits the whole modern SMT-backed stack as untrusted, re-checked oracles: **Souper**-class SMT superoptimization, **egg**/equality-saturation rewrite search, and **Alive2**-style translation validation gating each peephole — none touching the trust base, because the emitted binary still carries the CHERI-TAL and constant-time certificates the §6 checker re-validates.
  This is the next section's *SMT-as-oracle* insight applied to codegen; naming the tools closes the gap between "superoptimization is allowed" and "the tools that perform it are allowed."

### The prover-lever left unpulled — proof *production* is not proof *checking*

- **The single-prover discipline governs the *checker*; the spec silently applies it to the *producer* too, taxing the engineering-free axiom exactly where it should spend freely.**
  The F\*/Z3 (libcrux/HACL\*) and EasyCrypt/Why3 anxieties (§5, §17) are correct *as checker choices* — those tools *check* the proof, so trusting them widens the trust base — but the converse rule the doctrine implies is never stated: a tool that only *finds* a proof the Coq kernel then re-checks widens nothing, exactly as "a compromised compiler cannot mint a valid certificate" (§6).
  Under that rule the fresh proof mass this design commits to — seL4's design re-proved in Coq, VeriBetrFS's B^ε-tree in Coq/Iris, RefFS, SFSCQ/DiskSec, the SSProve/FCF reductions, the Narcissus grammars, the CHERI-TAL soundness metatheorem, the Kami/Kôika refinement — is exactly where automation buys the most and costs nothing:
  - **SMTCoq** — imports Z3/CVC5/veriT proof *witnesses* and re-checks them *in the Coq kernel*, making SMT an untrusted oracle under the one checker: the constructive answer to the F\*/Z3 tension for the *discharge* (not the specification) half of the crypto work — SMT automation with no second checker in the trust base.
  - **CoqHammer / Sniper / itauto** — premise selection + external ATP + *in-kernel proof reconstruction*: the industrial lever for the fresh proof mass, trust-free by construction.
  - **Coq-Elpi + Hierarchy Builder + Equations + MetaCoq** — the metaprogramming/automation superset for the algebraic hierarchies of the reductions, the dependent pattern-matching of the parser and filesystem proofs, and the boilerplate of the per-key-type index instantiations (§10) — supersets *of Coq*, checked by the same kernel.
  The doctrine needs one sentence: **the single-prover rule binds the checker, not the producer; any prover, solver, or search that emits a Coq-kernel-checkable term is admissible and encouraged, and only a tool that would *replace* the kernel's check widens the trust base.**
  That sharpens the F\*/Z3-vs-Coq framing from "avoid the tool" to "avoid the tool *as checker* — use it freely *as oracle*, and prefer SMTCoq to pull even its output back under the one kernel."

- **The one place an alternate prover genuinely tempts, stated honestly.**
  The layer-3 reductions bottom out in lattice / number-theoretic mathematics (MLWE/MSIS, ECDLP) where Coq's libraries trail Lean 4's mathlib — a real friction, and the one spot "embrace an alternate prover" has teeth.
  But Lean-*as-checker* is the two-kernel cost §5 refuses, and Lean-*as-oracle* has no mature Lean→Coq proof transport today, so the answer stays Coq-native — mathcomp + Hierarchy Builder + Coq-Elpi — and the friction is a *tooling-maturity* cost the engineering-free axiom absorbs, not a reason to fork the checker.
  Worth stating so the trade is visible rather than implicit.

If you want, I can turn the contradiction list into issues with proposed normative text edits per item.
