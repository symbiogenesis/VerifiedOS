# Hardware, ISA, capability and interconnect proof reuse

This inventory records upstream proof subjects and their fit to VerifiedOS at
revision `40c48830e11d2af3807d2431f7fc42ec9ce83bf3`. Source and license readings
are dated 2026-09-10. A published mechanization is evidence about its stated
machine, parameters and assumptions; it is not a proof of this repository's
machine. No upstream proof is replayed by this research lane, and no source code
is incorporated by this document.

The selection favors published, inspectable mechanizations and established
project proof suites. Entries explicitly marked partial are useful research
leads, not gold-standard completed proofs. Version information describes the
inspected upstream environment, not a compatibility result with this project's
installed Rocq. License dispositions follow the current [third-party
policy](../../../THIRD-PARTY.md); permissive terms alone do not make a proof usable.

## Local obligations, including completed work

The [register](../../requirements-register.md), [crown jewels](../crown-jewels.md)
and [implementation checklist](../../implementation/implementation-checklist.md) own the current
obligations and status. The following mapping is a research index, not a second
completion ledger.

| Local subject | Existing artifact and remaining connection | Candidate entries |
| --- | --- | --- |
| Capability encoding, R-15-007a/R-15-007b; M0.6f | The model and helper-property suite exist, but the frozen-width representation theorem, including the malformed set, remains open. | HW-01, HW-02, HW-03, HW-04 |
| Capability safety and adversarial code, R-13-016/R-13-017, CJ-CERISE | The canonical Sail connection, universal contract and concrete memory laws remain the foundation work identified in the [foundation map](../../hardware/cheri-foundation-map.md). | HW-03, HW-04, HW-05, HW-06 |
| Functional RTL refinement, R-01-003/R-05-019b/R-05-158, CJ-RTL-SAIL | RTL elaboration and the R1/R2 bring-up and comparison work do not establish the closing unbounded theorem. | HW-07, HW-08, HW-09, HW-10, HW-11, HW-12, HW-16 |
| ECC, tag integrity and atomic commit, R-15-175 through R-15-181a | Modeled memory behavior and bring-up exist; the concrete SECDED/DECTED implementation, fault model, fixed latency and RTL connection remain distinct obligations. | HW-13, HW-14 |
| NoC and bank isolation, R-15-211/R-15-222a/R-15-223/R-15-228, CJ-ISOL | The isolation model is unauthored. M0.14's latency classes and M0.16's sequencer do not supply it. [PartitionContext.v](../../../proofs/PartitionContext.v) reasons about context state, not arbitrary NoC executions. | HW-09, HW-15; the negative findings below |
| Attestation and hardware/software boundary, R-05-082/R-05-160, CJ-HAL | [RotFirmware.v](../../../proofs/RotFirmware.v), [RomVerifier.v](../../../proofs/RomVerifier.v) and other statement artifacts do not supply peripheral RTL refinement or a physical sensor theorem. | HW-06, HW-09 |

## Capability and ISA proofs

### HW-01: Sail CHERI-RISC-V compressed-capability helper properties

**Standing: established, already partly reused here.** The CTSRD-CHERI
[artifact](https://github.com/CTSRD-CHERI/sail-cheri-riscv-verif/tree/4da8fd10)
provides SMT-checkable helper properties in
[cap_properties.sail](https://github.com/CTSRD-CHERI/sail-cheri-riscv-verif/blob/4da8fd10/cap_properties.sail).
The [README](https://github.com/CTSRD-CHERI/sail-cheri-riscv-verif/blob/4da8fd10/README.md)
distinguishes those results from whole-ISA proofs still under development and
records Sail `63343363` with ISA `929cf11`; it supports Sail SMT and Isla checks.
Authorship and funding notices are in its
[BSD-2-Clause LICENSE](https://github.com/CTSRD-CHERI/sail-cheri-riscv-verif/blob/4da8fd10/LICENSE),
already retained locally as [LICENCE.cheri-verif](../../../model/LICENCE.cheri-verif).

**Reuse:** preserve the existing
[transcription](../../../model/model/unit_tests/cap_properties.sail), whose exact
widths and toolchain differ from upstream. This is the nearest source-language
precedent for R-15-007a. A helper SMT result does not establish the requested
round-trip and malformed-set characterization for the local bounds encoding.
Importing the upstream file again supplies no missing theorem. Further reuse
requires a property-by-property comparison against the local Sail definitions.

### HW-02: CHERIoT Sail encoding and monotonicity properties

**Standing: inspectable Sail property suite.** The paper-cited edition
`43dead94f190f87b1bb18a7fe46add98ec97803c` contains
[properties/props.sail](https://github.com/CHERIoT-Platform/cheriot-sail/blob/43dead94f190f87b1bb18a7fe46add98ec97803c/properties/props.sail),
including `prop_decEnc`, `prop_andperms`, `prop_setbounds` and
`prop_setbounds_monotonic`. It is an independent source of representation
questions worth asking of R-15-007a. The
[LICENSE](https://github.com/CHERIoT-Platform/cheriot-sail/blob/43dead94f190f87b1bb18a7fe46add98ec97803c/LICENSE)
is BSD-2-Clause outside the explicitly separate prover snapshots, naming
Microsoft and the CHERI Sail contributors. Retain that full notice for any
adaptation. A compatible Sail/compiler/solver combination is not replayed here.

**Reuse:** adapt statements after semantic review. CHERIoT's address, exponent,
mantissas, permission compression and roots differ from this profile. Moreover,
the source comments out the `$property` marker on `prop_base_lteq_top`; the
presence of a function must not be reported as a proved universal property.
This matters directly to the local malformed-encoding obligation. No direct
import is justified by the shared word "CHERI".

### HW-03: CHERI-MIPS capability monotonicity

**Standing: published architecture-scale mechanization in Isabelle.** Thomas
Bauereiss developed the capability proof; Kyndylan Nienhuis developed the
`Word_Extra` library, with Bauereiss contributions. The
[artifact at 38d00591864abe3bd03d1fcd9efcb0a77921593a](https://github.com/CTSRD-CHERI/sail-cheri-mips-proofs/tree/38d00591864abe3bd03d1fcd9efcb0a77921593a)
separates abstract monotonicity in `proof/Properties.thy` from instruction-local
obligations and the architecture instance in
[CHERI_MIPS_Properties.thy](https://github.com/CTSRD-CHERI/sail-cheri-mips-proofs/blob/38d00591864abe3bd03d1fcd9efcb0a77921593a/proof/CHERI_MIPS_Properties.thy).
It records Isabelle 2019, Sail `63343363`, Lem `a839114` and ISA `4d8457c1`.
The [LICENCE](https://github.com/CTSRD-CHERI/sail-cheri-mips-proofs/blob/38d00591864abe3bd03d1fcd9efcb0a77921593a/LICENCE)
is BSD-2-Clause for the proof, with dependency-specific licenses in `lib/` and
`sail-cheri-mips/`.

**Reuse:** use the abstract/local decomposition as a rigorous reference for
R-13-016 and the profile's capability safety. The proof is for CHERI-MIPS and
its exact semantics; the local Sail-emitted Rocq term is a different subject.
Transport requires an explicit relation and newly discharged instruction
obligations. Its generated lemmas were subsequently edited by hand; blindly
rerunning the old generator is specifically discouraged upstream.

### HW-04: Morello reachable-capability monotonicity

**Standing: peer-reviewed architecture-scale proof.** Thomas Bauereiss, Brian
Campbell, Thomas Sewell, Alasdair Armstrong, Lawrence Esswood, Ian Stark, Graeme
Barnes, Robert N. M. Watson and Peter Sewell, *Verified Security for the Morello
Capability-enhanced Prototype Arm Architecture*, ESOP 2022. The
[source](https://github.com/CTSRD-CHERI/sail-morello-proofs/tree/7ef5abd132998f9d9969b6d23b6c7d57f01c5275)
contains `morello_monotonicity` in
[CHERI_Monotonicity.thy](https://github.com/CTSRD-CHERI/sail-morello-proofs/blob/7ef5abd132998f9d9969b6d23b6c7d57f01c5275/CHERI_Monotonicity.thy).
Dependencies include Isabelle 2020, compatible AFP `Word_Lib`, Sail `5d18bd95`,
the Morello model and the CHERI abstraction. Generated lemmas are checked by
Isabelle. The [LICENCE](https://github.com/CTSRD-CHERI/sail-morello-proofs/blob/7ef5abd132998f9d9969b6d23b6c7d57f01c5275/LICENCE)
is BSD-2-Clause, copyright Bauereiss and Sewell.

**Reuse:** strong exemplar for R-13-016 and R-15-007a's architecture-level
context, especially instruction, memory-access and fetch proof decomposition.
It proves a Morello security property, not this bounds representation or RTL.
The foreign logic, architecture-specific invariant and canonical-Sail bridge
make this a substantial adaptation. The smaller Sail helper properties beside
the Isabelle proof are potential statement-level inputs, not local witnesses.

### HW-05: Cerise universal contract and sentry encapsulation

**Standing: published Rocq/Iris mechanization and existing project pin.** Aïna
Linn Georges, Armaël Guéneau, Thomas Van Strydonck, Amin Timany, Alix Trieu,
Dominique Devriese and Lars Birkedal, [*Cerise: Program Verification on a
Capability Machine in the Presence of Untrusted Code*](https://cs.au.dk/~timany/publications/pub_pages/2023-cerise-jacm/).
At `9eb72e675216d7c5473499f392b18049364db03a`,
[theories/fundamental.v](https://github.com/logsem/cerise/blob/9eb72e675216d7c5473499f392b18049364db03a/theories/fundamental.v)
and the adequacy examples provide the universal-contract machinery. The
`opam` file selects Coq 8.20.0, Iris 4.3.0 and stdpp 1.11.0, plus
`machine_utils`. Its [LICENSE](https://github.com/logsem/cerise/blob/9eb72e675216d7c5473499f392b18049364db03a/LICENSE)
is BSD-3-Clause except `extra/`, whose separate terms must remain separate.

**Reuse:** this is the principal same-language precedent for CJ-CERISE and
R-13-016. It supplies reasoning about arbitrary unknown code and sentries on
its abstract capability machine. Uncompressed abstract capabilities, encoding
parameters, memory semantics and its instruction set are not the frozen Sail
term. The [foundation map](../../hardware/cheri-foundation-map.md) correctly retains that
missing connection. Importing only the fundamental theorem would import its
subject and premises, not eliminate them.

### HW-06: Cerisier attestation and modeled trusted sensor

**Standing: Rocq/Iris artifact for the 2026
[Cerisier paper](https://arxiv.org/abs/2604.13638), extending Cerise.** Authors:
June Rousseau, Denis Carnier, Thomas Van Strydonck, Steven Keuchel, Dominique
Devriese and Lars Birkedal. The
edition `57ed584ae17eed308ae0fa554cf0dde9843112c1` provides
`cerisier_universal_contract` in
[theories/logrel/fundamental.v](https://github.com/logsem/cerisier/blob/57ed584ae17eed308ae0fa554cf0dde9843112c1/theories/logrel/fundamental.v),
plus mutual-attestation, secure outsourced computation and trusted-memory
readout adequacy proofs. Its README records Coq 8.18.0, stdpp 1.9.0 and Iris
4.1.0. The [LICENSE](https://github.com/logsem/cerisier/blob/57ed584ae17eed308ae0fa554cf0dde9843112c1/LICENSE)
is BSD-3-Clause outside `extra/`. Attribute the paper and Cerisier contributors
as well as preserving the source notices in any later incorporation.

**Reuse:** directly relevant to R-13-016 and R-05-160's attestation/capability
seam, but not to physical sensor fidelity. Its explicit assumption audit is
particularly valuable: instruction/permission encoding laws, idealized
injective hash functions, additional hash algebra for mutual attestation and
functional extensionality in case studies. These do not silently become
theorems about SHA-256, collision resistance or the project's RoT. Reuse needs
the canonical machine bridge and a cryptographic interpretation of the hash
assumptions. The [README](https://github.com/logsem/cerisier/blob/57ed584ae17eed308ae0fa554cf0dde9843112c1/README.md)
documents `make assumptions`; no local replay is claimed.

## Hardware refinement and reusable circuit proofs

### HW-07: Kami modular refinement and pipeline/FIFO examples

**Standing: peer-reviewed Coq hardware framework.** Joonwon Choi, Muralidaran
Vijayaraghavan, Benjamin Sherman, Adam Chlipala and Arvind,
[*Kami*, ICFP 2017](https://adam.chlipala.net/papers/KamiICFP17/).
The MIT edition `3f9c603aaff3ea35ca6deb880a49ac2a9e62738b` includes
`fetchDecode_refines_fetchNDecode` and cache/fetch refinements in
[Kami/Ex/ProcFDCorrect.v](https://github.com/mit-plv/kami/blob/3f9c603aaff3ea35ca6deb880a49ac2a9e62738b/Kami/Ex/ProcFDCorrect.v),
plus `FifoCorrect.v`, `SimpleFifoCorrect.v` and `RefinementFacts.v`.
The README specifies Coq 8.12.x and separately describes Bluespec extraction.
The actual [LICENSE](https://github.com/mit-plv/kami/blob/3f9c603aaff3ea35ca6deb880a49ac2a9e62738b/LICENSE)
is MIT, copyright 2017 CSAIL, Massachusetts Institute of Technology.

**Reuse:** strong permissible starting point for the closing CJ-RTL-SAIL route
and reusable buffer/refinement lemmas. The example processor is not CVA6-CHERI,
and a theorem over Kami semantics does not cover Verilog emission, synthesis,
the local ISA, timing or noninterference automatically. Select an actual block,
instantiate its preconditions and connect its observations to the canonical
Sail model before import. The separately maintained SiFive rewrite is not the
same library edition and should not be mixed into this dependency closure.

### HW-08: Kôika verified rule-to-circuit compiler

**Standing: kernel-checkable Coq compiler theorem.** Clément Pit-Claudel and
Thomas Bourgeat are the package authors. At
`8921e30434d9e351c49df84c9aa14e72b0456ad0`,
[`compiler_correct`](https://github.com/mit-plv/koika/blob/8921e30434d9e351c49df84c9aa14e72b0456ad0/coq/CompilerCorrectness/Correctness.v)
relates interpretation of a typed scheduled rule cycle to the compiled
register-output circuits. The statement exposes the external-function
interpretation and correctness-typed local optimizer; these are real inputs.
`koika.opam` requires Coq at least 8.18 or its stated Ltac2 alternative.
The [LICENSE](https://github.com/mit-plv/koika/blob/8921e30434d9e351c49df84c9aa14e72b0456ad0/LICENSE)
contains LGPL 2.1 text; it does not settle the only/or-later election, as the
existing third-party reading already records.

**Reuse:** excellent comparator for CJ-RTL-SAIL's compiler leg and scheduled
hardware semantics. It does not prove imported SystemVerilog correct or prove
an ISA refinement for an arbitrary generated circuit. The current tracked-tree
license policy and unsolved semantic joins rule out a direct import. Retain
as a reference and compare against Kami at the closing-route decision.

### HW-09: Silver Oak AES, FIFO and hardware/software proofs

**Standing: Coq proof-of-concept with concrete component theorems.** The Project
Oak authors' [PLARCH 2023 presentation](https://pldi23.sigplan.org/details/plarch-2023-papers/23/Silver-Oak-Hardware-Software-Co-Design-and-Co-Verification-in-Coq)
describes Cava AES and Bedrock2 driver co-verification. At
`cccfdb4e19c5906256d2ed4487bf1a0aa2fab99e`,
[AES256Equivalence.v](https://github.com/project-oak/silveroak/blob/cccfdb4e19c5906256d2ed4487bf1a0aa2fab99e/silveroak-opentitan/aes/Impl/AES256Equivalence.v)
contains `full_cipher_equiv` and `full_cipher_inverse`;
[FifoProperties.v](https://github.com/project-oak/silveroak/blob/cccfdb4e19c5906256d2ed4487bf1a0aa2fab99e/cava2/Components/FifoProperties.v)
contains `fifo_invariant_preserved`, `fifo_output_correct`,
`fifo_invariant_at_reset` and `fifo_correctness`. The root README specifies Coq
8.13.0. [LICENSE](https://github.com/project-oak/silveroak/blob/cccfdb4e19c5906256d2ed4487bf1a0aa2fab99e/LICENSE)
and those source headers state Apache-2.0, copyright Project Oak Authors.

**Reuse:** high-value permissible examples for CJ-HAL, CJ-RTL-SAIL and
R-05-059's functional layer. FIFO capacity assumes more than one entry and a
specific handshake specification. The project explicitly does not verify the
Cava-to-SystemVerilog infrastructure. Neither AES functional correctness nor
FIFO correctness proves masking, glitch resistance, the local AES-GCM
representation, or the NoC's timing noninterference. These are adapters and
proof patterns, not interchangeable local theorem constants.

### HW-10: CHERIoT-Ibex observational RTL/Sail verification

**Standing: substantial published verification, with an artifact qualification
gap.** Louis-Emile Ploix, Alasdair Armstrong, Tom Melham, Ray Lin, Haolong Wang
and Anastasia Courtney, [*Comprehensive Formal Verification of Observational
Correctness for the CHERIoT-Ibex Processor*](https://arxiv.org/abs/2502.04738),
2025. The paper describes unbounded SVA proof using Jasper, memory-trace
equivalence, a compressed-capability data-type invariant and bounded-response
premises for liveness. At the project's pin
`930feb298af5bf7d9aa0baeaa21732ff84a2f066`,
[dv/formal/README.md](https://github.com/microsoft/cheriot-ibex/blob/930feb298af5bf7d9aa0baeaa21732ff84a2f066/dv/formal/README.md)
instead says there is currently no liveness and exposes `prove_no_liveness`.
It excludes stack zeroing and reservation/revocation. This discrepancy needs
resolution before claiming the pinned artifact replays the paper's whole result.

**Reuse:** the closest concrete CHERI RTL-to-Sail methodology for R1/R2 and
CJ-RTL-SAIL. It needs the lowRISC Sail fork, `psgen`, Nix and JasperGold, with
reset and clock-gating configuration changes. The
[Apache-2.0 LICENSE](https://github.com/microsoft/cheriot-ibex/blob/930feb298af5bf7d9aa0baeaa21732ff84a2f066/LICENSE)
permits source reuse with its notices. RV32 CHERIoT, its modified specification,
microarchitecture-specific invariants and unchecked Sail-to-SV translation
do not discharge the frozen RV64 CVA6 theorem or its Rocq proof endpoint.

### HW-11: VeriCHERI security properties and representability invariant

**Standing: published method with a partial public artifact.** Anna Lena Duque
Antón, Johannes Müller, Philipp Schmitz, Tobias Jauch, Alex Wezel, Lucas
Deutschmann, Mohammad Rahmani Fadiheh, Dominik Stoffel and Wolfgang Kunz,
[*VeriCHERI: Exhaustive Formal Security Verification of CHERI at the
RTL*](https://arxiv.org/abs/2407.18679), ICCAD 2024. The
[author repository](https://github.com/RPTU-EIS/VeriCHERI) describes monotonicity
functions and a representability-invariant property sketch under
`CHERIoT-invariants/`. That is narrower than a turnkey release of the paper's
entire verification environment. The inspected public README and root listing
do not supply a reuse grant or replay environment. A full package/file-header
license audit remains required; absence of a root license alone is not a
conclusion about every file's terms.

**Reuse:** reference for security-property decomposition, R-15-007a and
CJ-RTL-SAIL's hyperproperty half. No code is copied. The paper's CHERIoT RTL
subject and its assumptions must be distinguished from the functional
observational equivalence in HW-10 and from VerifiedOS noninterference.
This entry is a qualified lead, not a claim that an importable completed proof
was located. The dated branch reading has no immutable artifact pin here.

### HW-12: RISC-V Formal instruction and interface checks

**Standing: established solver-based verification framework.** Claire Xenia
Wolf and contributors. At `c992aa61fdfe0846c5ed90324c596202a1c69b76`,
[checks/rvfi_insn_check.sv](https://github.com/YosysHQ/riscv-formal/blob/c992aa61fdfe0846c5ed90324c596202a1c69b76/checks/rvfi_insn_check.sv)
connects RVFI retirement observations with generated instruction specifications,
including [insns/insn_add.v](https://github.com/YosysHQ/riscv-formal/blob/c992aa61fdfe0846c5ed90324c596202a1c69b76/insns/insn_add.v).
[COPYING](https://github.com/YosysHQ/riscv-formal/blob/c992aa61fdfe0846c5ed90324c596202a1c69b76/COPYING)
and the check's own header grant ISC-style permissive terms, copyright 2017
Wolf. The applicable Yosys/SymbiYosys/solver versions and proof depth are
configuration-specific and not replayed here.

**Reuse:** appropriate for R2's BMC smoke and retirement-interface obligations.
Local RVFI-DII testing already has its own protocol provenance. Plain RVFI
integer register/memory fields do not describe tags, local permissions,
revocation or the canonical Sail semantics. A passing instruction check is not
an unbounded complete processor theorem; extending the interface and proving
state continuity remain work. Do not duplicate the existing harness merely to
record this reference.

## ECC and interconnect

### HW-13: Infotheo Hamming and linear error-correcting-code proofs

**Standing: published Rocq/MathComp library.** Initial authors Reynald Affeldt,
Manabu Hagiwara and Jonas Senizergues, with the contributors credited in the
[repository](https://github.com/affeldt-aist/infotheo). At
`de3a127c5fcb4a5d121225e22003936098c4136a`,
[ecc_classic/hamming_code.v](https://github.com/affeldt-aist/infotheo/blob/de3a127c5fcb4a5d121225e22003936098c4136a/ecc_classic/hamming_code.v)
proves `hamming_min_dist`, `hamming_repair_img` and `hamming_MD_decoding`;
`linearcode.v` and `reed_solomon.v` provide broader coding algebra. The current
package requires MathComp at least 2.4.0 and analysis at least 1.12.0 among its
dependencies. Its [LICENSE](https://github.com/affeldt-aist/infotheo/blob/de3a127c5fcb4a5d121225e22003936098c4136a/LICENSE)
contains LGPL 2.1; both source and
[opam](https://github.com/affeldt-aist/infotheo/blob/de3a127c5fcb4a5d121225e22003936098c4136a/rocq-infotheo.opam)
explicitly elect **LGPL-2.1-or-later**.

**Reuse:** gold-standard same-language mathematical reference for
R-15-175/R-15-178a/R-15-181a. A distance-three Hamming theorem is not the
project's extended SECDED implementation or its separate DECTED tag code.
Physical interleaving, error-distribution assumptions, atomic data/tag writes
and fixed latency lie outside these statements. The current policy against
reciprocal tracked source prevents direct copying; the mathematical argument
and possible separately contained library use need an explicit future choice.

### HW-14: OpenTitan SECDED formal assertions and generator

**Standing: established hardware project proof suite.** The lowRISC
contributors' [SECDED generator documentation](https://opentitan.org/book/util/design/index.html)
describes generated RTL, assertions and formal targets. At local upstream pin
`629146ef`,
[prim_secded_39_32_assert_fpv.sv](https://github.com/lowRISC/opentitan/blob/629146ef/hw/ip/prim/fpv/vip/prim_secded_39_32_assert_fpv.sv)
contains `SingleErrorCorrect_A`, single/double detection and syndrome properties,
under `MaxTwoErrors_M`, which assumes at most two injected errors.
[util/design/secded_gen.py](https://github.com/lowRISC/opentitan/blob/629146ef/util/design/secded_gen.py)
generates the assertion family. Both file headers name Apache-2.0 and lowRISC
contributors, under the root
[LICENSE](https://github.com/lowRISC/opentitan/blob/629146ef/LICENSE).

**Reuse:** nearest permissible verification-IP template for the data-code half
of R-15-175/R-15-179/R-15-181a. The inspected instance is 39/32, not the local
266/256 codeword or the independent validity-tag DECTED plane. Instantiate and
reprove the intended generator output, preserve the fault assumptions, and
connect error status to local fail-stop behavior. This source inspection does
not establish any target's solver success, nor fixed latency, in-transit
coverage or atomic memory commit. Use the existing gitlink when that RTL is
implemented rather than copying third-party RTL into `rtl/`.

### HW-15: GeNoC generic network correctness and deadlock prevention

**Standing: published ACL2 mechanization.** Freek Verbeek and Julien Schmaltz,
*Formal Validation of Deadlock Prevention in Networks-on-Chips*, ACL2 Workshop
2009, building on GeNoC by Julien Schmaltz and Dominique Borrione. The
[community-book artifact](https://github.com/acl2/acl2/tree/4cc2d5df172c792988a8031d8955686fad38d186/books/workshops/2009/verbeek-schmaltz/verbeek)
includes generic routing, scheduling and synchronization obligations, plus a
circuit-switched instance. `genoc-is-correct` is in
[generic-modules/GeNoC.lisp](https://github.com/acl2/acl2/blob/4cc2d5df172c792988a8031d8955686fad38d186/books/workshops/2009/verbeek-schmaltz/verbeek/generic-modules/GeNoC.lisp).
The [Readme.lsp permission field](https://github.com/acl2/acl2/blob/4cc2d5df172c792988a8031d8955686fad38d186/books/workshops/2009/verbeek-schmaltz/verbeek/Readme.lsp)
explicitly states **GPL-2.0-or-later**, copyright 2009 Verbeek and Schmaltz.
The collection-level `books/LICENSE` delegates terms to individual books.

**Reuse:** reference for functional delivery and progress obligations inside
R-15-211/R-15-228's future NoC model. ACL2 functional instantiation provides a
useful example of proving a generic network theorem once and discharging
concrete scheduler/routing constraints. It does not establish TDM timing
noninterference, bank isolation, capability tags or local failure semantics.
The artifact's ACL2 release compatibility is not replayed. Its reciprocal
license and foreign proof logic rule out direct source integration under the
present project policy.

### HW-16: riscv-coq execution and semantic-composition lemmas

**Standing: established Coq RISC-V ecosystem library.** MIT authors and
contributors; edition `fa95ba9007846d0af8294fe2e277c81e829b5fbb`.
[src/riscv/Utility/runsToNonDet.v](https://github.com/mit-plv/riscv-coq/blob/fa95ba9007846d0af8294fe2e277c81e829b5fbb/src/riscv/Utility/runsToNonDet.v)
contains `runsTo_trans`, `runsTo_weaken` and `runsTo_det_step` over a
parameterized state/step relation. The `Platform/` directory has explicit
minimal and MMIO machine instances. The actual
[LICENSE.txt](https://github.com/mit-plv/riscv-coq/blob/fa95ba9007846d0af8294fe2e277c81e829b5fbb/LICENSE.txt)
is **BSD-3-Clause**, copyright 2017-2018 MIT; the institution name is not an MIT
license election. It depends on `coqutil`; local version compatibility is not
measured.

**Reuse:** possible small generic lemmas for the R-05-019b/CJ-RTL-SAIL
composition layer once its relation exists. The RISC-V machine instances and
decoder are not authoritative substitutes for Sail. No present local
obligation is discharged simply by importing this file, and adding the whole
library for unused generic lemmas would not be a drop-in integration. The
existing Bedrock2 lineage is an integration precedent, not proof that this
capability machine already has the same connection.

## Negative findings and concrete next uses

The strongest immediately useful hardware result is an inventory of exact
proof subjects and their gaps. No newly located hardware proof meets the
drop-in condition of matching a local statement, having a compatible dependency
closure, preserving project licensing, and replaying over the local definitions.
The helper suite in HW-01 is already incorporated with attribution; repeating
that import would obscure rather than close its remaining obligations.

For the missing NoC model, functional delivery, FIFO safety and a static schedule
are separate from noninterference. None of the inspected artifacts proves the
project's shared-island, per-core, non-work-conserving rotation, atomic-RMW slot
bound and tagged-ring observations together. HW-15 is a network proof template;
HW-09 supplies a component invariant. They do not discharge CJ-ISOL. The
physical read/write/refresh/discharge constants, gain-cell retention and
synchronizer reliability still require the measurements the register names.

For ECC, HW-13 separates coding algebra from HW-14's RTL fault-injection
assertions. Neither supplies the independent DECTED tag code, the local
malformed-word fail-stop policy, nor proof that a refresh or discharge commits
data and validity atomically. A modeled trusted sensor in HW-06 also does not
prove transducer accuracy. Likewise, HW-09's AES functionality leaves the
glitch- and transition-extended probing model and masking composition under
R-15-053a/CJ-LEAK open.

Practical reuse order is: extend the local capability-property comparison with
HW-02's questions; use HW-10's state-invariant and observation decomposition
when implementing RTL refinement; use the already pinned OpenTitan assertion
generator at the concrete ECC milestone; and evaluate Kami/Silver Oak for a
named newly authored hardware block with an explicit Sail bridge. Each next
use must record the actual imported files, dependency notices, theorem
assumptions and replay command. This inventory itself changes no requirement,
completion claim, upstream pin or proof assumption.
