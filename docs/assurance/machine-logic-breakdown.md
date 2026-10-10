# The machine logic's establishment breakdown

This is Q35c's source qualification and reviewed implementation breakdown for
the `machine-logic` key in [the foundation ledger](../hardware/cheri-foundation-map.md#foundation-ownership-ledger).
The inspection uses revision `b238c3c5f8c216efa85ec0f413868e810a6aeeb8` and the
isolated lane `q35c-20261010-logic`. It retains R-13-016's Katamaran route and
R-13-017's four theories over one annotated machine semantics. It establishes
no local logic, instruction rule, translation agreement or binary theorem.

**Disposition:** pinned Islaris cannot build unchanged in the locked proof
environment. The selected example's exact assumption audit is unavailable
because no compiled root exists; the audit attempts fail and supply no empty
closure. This is Q35c's permitted build-failure qualification, with the missing
work assigned below. Q35b's canonical-term compile and closure remain its own
prerequisites. Q35d's Stage 0 may precede the logic, under its existing stop and
reject conditions; its function proofs wait on the separately landed foundations.

The [Q35m dependency trial](machine-logic-dependency-trial.md) reproduces strict-source refusals in both required framework chains and records a separately scoped unpriced continuation. Complete framework audits remain unavailable; the separate equality-import probe exposes F-786. Q35k requires compatible, carried libraries and remains closed.

## 1. Source identities, terms and qualification

The [qualification receipt](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/receipt.json)
binds the source inventory, invocation arguments, working directories, logs,
prover/checker binaries and unchanged proof-switch exports. The
[source identities](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/source-identities.json)
name each inspected tracked source file's SHA-256. Qualification used native
sources and compiled libraries in `/root/build/lane-q35c-20261010-logic/q35c/`;
the fanout journal owns their retained output destinations on safe retirement.
No upstream source, gitlink, new switch lock or installed package is incorporated here.

| Subject | Exact source | Reading and disposition |
| --- | --- | --- |
| Islaris | [`rems-project/islaris` at `c978e10f50db5c40f0fdf113f5f76a779782c6f9`](https://github.com/rems-project/islaris/tree/c978e10f50db5c40f0fdf113f5f76a779782c6f9) | The selected immutable revision, obtained from upstream `HEAD` on 2026-10-10. `README.md`, `islaris.opam`, `dune-project`, build stanzas, `theories/adequacy.v`, `theories/opsem.v`, RISC-V architecture/specs and the selected example were read. This revision is a design and port input, refused as an unchanged foundation at the lock. |
| Isla trace language | [`rems-project/isla-lang` at `bda86c9f0bd28bbaa2481f50ddc986ede342805a`](https://github.com/rems-project/isla-lang/tree/bda86c9f0bd28bbaa2481f50ddc986ede342805a) | Islaris's `pin-depends` revision; its generated trace language is copied into Islaris's theory by its build. Source and package metadata were read; no build or semantic connection is claimed. |
| Katamaran | [`47bc545117348495f71aad9e20d5c9bb9ed3a757`](https://github.com/katamaran-project/katamaran/tree/47bc545117348495f71aad9e20d5c9bb9ed3a757) | The indexed gitlink, inspected with `git ls-files -s upstream`; its source was fetched at that exact revision into the native lane. `dune-project` version 0.2.0 bounds Coq below 9.1, Iris below 4.4 and stdpp below 1.12. `Iris/Instance.v` and `Iris/BinaryAdequacy.v` concern its own μSail relation. No build at 9.3 is inferred from the pin or these theorem names. |
| Sail-to-μSail producer | [`c9b1cd0234d7d4ee839b8d07bad7db601e6a5a40`](https://github.com/katamaran-project/sail-backend/tree/c9b1cd0234d7d4ee839b8d07bad7db601e6a5a40) | The indexed `upstream/sail-katamaran-backend` gitlink. Its usage document describes a Sail plugin, configuration and templates; unsupported translations remain explicitly reported. That producer supplies candidate μSail, not a theorem relating it to Sail's Rocq output. |
| Iris candidate | [`iris-4.5.0`, `b909adcc698a6c38f4c3b2645936bdd0d870d412`](https://gitlab.mpi-sws.org/iris/iris/-/tree/b909adcc698a6c38f4c3b2645936bdd0d870d412) | The released baseline selected for the one prospective instance below. Its published `rocq-iris` 4.5.0 package metadata admits Rocq 9.3 and stdpp 1.13.0. The tag's source `rocq-iris.opam` is development metadata with different bounds; it is not substituted for the published package's constraints. This selection does not qualify Islaris or Katamaran against that Iris release. |

### The actual licences

Islaris's `LICENSE`, SHA-256
`d43eeae8b2e1639534f8d095d3b3231f1fc193cfc172b98069adf41bf9684fb9`,
grants BSD-2-Clause terms to the Islaris developers' source.
`THIRD_PARTY_FILES.md`, SHA-256
`b07313f37d4d0b6c36ae55d01211d46275412f3419c656e22cef16216f9ed91a`,
contains `None`. The selected example and adequacy source also carry the
two-clause notice. The package metadata says `BSD-3-Clause`; that discrepancy
does not change the licence text actually read. No rights are inferred from the
PLDI artifact deposit's separate terms, and nothing from that deposit was fetched.

`isla-lang`'s `LICENSE`, SHA-256
`0faa544bb919253727d14e4048da0426f66c1db522726c9de28523050b789953`,
is BSD-2-Clause. Katamaran's `LICENSE`, SHA-256
`6b961710f8d256461e624d0659fbaade43505b2ae709f91c8f0c3e34a08d010a`,
has the two-condition BSD grant. The selected sail-backend tree has no tracked
standalone licence file; `default.nix`, `nanosail.nix` and `monads.nix` declare
`licenses.bsd2` for its three packages. [The accepted packaging-grant reading](../../THIRD-PARTY.md#proof-and-lowering-references)
records BSD-2-Clause terms at this pin and requires a redistribution notice using
`dune-project`'s authorship if vendored. This item incorporates none of its code.

Iris's `LICENSE` distinguishes BSD-3-Clause source, outside `docs/` and `tex/`,
from CC-BY-4.0 documentation; `LICENSE-CODE` was read at the selected tag.
The receipt retains those files' identities. The intended use is local source
qualification and proof-framework design. Redistribution of Islaris, isla-lang,
Katamaran or Iris source is not part of this act. Any subsequent incorporation
re-reads the actual files of its dependency closure and updates
[THIRD-PARTY.md](../../THIRD-PARTY.md).

### Exact attempted build and assumption audit

The locked environment reports Rocq 9.3.0, OCaml 5.4.1, Dune 3.24.2, stdpp
1.13.0 and no Iris, Lithium, RecordUpdate or isla-lang package. The switch export
before and after qualification is byte-identical, SHA-256
`3e70338fb77832f9e09ee8780cd10524e002420b1ca9aa5f56a15777765e1b32`.
The commands use the native source directory; none changes the locked switch.

| Attempt | Exit and deciding result |
| --- | --- |
| `opam install --switch=verifiedos-rocq-9.3.0-ocaml-5.4.1 --deps-only --dry-run --show-actions ./islaris rocq-core.9.3.0` | 20; the registered metadata has no `coq-lithium` package. No dependency installation was run. Independently, `islaris.opam` requires Coq 8.19.0 or `dev`, Lithium `dev.2024-09-11.0.7945a29d` or `dev`, RecordUpdate 0.3.3 or `dev`, and Dune exactly 3.9.1. It states no package solution at the lock. |
| `opam exec --switch=verifiedos-rocq-9.3.0-ocaml-5.4.1 -- make` in the pristine Islaris tree | 2; Dune refuses `dune-project` line 3, `(using coq 0.8)`, because the Coq build extension was deleted in Dune 3.24. No Rocq compilation or frontend generation occurs. |
| Locked `rocq c` over `SelectedExampleAudit.v`, with the gate's `STRICT` arguments and explicit source mappings | 1; cannot locate `riscv64_test` with prefix `isla.examples`. The requested queries are `Print Assumptions` of `isla.examples.riscv64_test.riscv_test` and `isla.examples.riscv64_test.riscv_test_adequate`. Neither query executes. |
| Locked `rocqchk -silent -o` over `isla.examples.riscv64_test`, with the same mappings and no admitted module | 1; cannot find the compiled library. There is no whole-environment context summary or accepted assumption reading. |

The requested audit client is [`/root/build/lane-q35c-20261010-logic/q35c/SelectedExampleAudit.v`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/SelectedExampleAudit.v), SHA256 `795424af1de229c4a0d5b9b981b7de5a327b1423ced420cba73ab801350b678a`.

The logs are [build](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/build.log),
[solver](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/solver.log),
[compiler audit](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/assumptions.log)
and [kernel audit](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/kernel.log).
The receipt records each exact argv, exit, duration and digest. These are focused
qualification attempts, not a local execution of VerifiedOS's proof or guest gates.

The separate [source review](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/source-review.json)
hashes the selected example and the local theory sources and records import text
and a lexical scan for assumption declarations. No matching local `Axiom`,
`Parameter`, `Admitted` or `Conjecture` appears in that reviewed source.
This scan does not elaborate imports, inspect external dependency implementations,
or enumerate the proof-term closure. The exact closure is **unavailable**,
represented by `null` and a failed audit status in the receipt, rather than `[]`.
R-05-163 and R-05-164 admission must be taken only after a successful fresh
compiler audit and whole-environment kernel reading.

**The selected Iris closure has separate positive evidence.** Iris 4.5.0's source
was built locally with `make-package iris -j2` under the locked prover and its
own compile flags, which suppress notation/projection warnings and leave Rocq
9.3 deprecations as warnings. The first source-build log is
[`/root/build/lane-q35c-20261010-logic/q35c/iris-build.log`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/iris-build.log), SHA256 `03e65e4fc4a69c4209f936e82c550fe58d587c0c4cfe48fde47e28be1fd52e60`; its shell wrapper did not preserve the exit
status. The receipt identifies the subsequent explicit incremental confirmation,
exit 0, as such: [`/root/build/lane-q35c-20261010-logic/q35c/iris-build-incremental.log`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/iris-build-incremental.log), SHA256 `47b67e4c0303bb3d3a19264993c88b1866eb7e06586228a4ff6b4b6d2a746440`.
The [strict import probe](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/IrisProbe.v)
loads `weakestpre` and `adequacy`; locked `rocq c` with the gate's strict flags
exits 0 and `Print Assumptions wp_adequacy` reports a closed global context.
Its [whole-environment kernel check](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/iris-kernel.log)
exits 0, naming no axiom, type-in-type, unsafe fixpoint or assumed positivity.
This qualifies only that stock-Iris import/adequacy closure. It does not compile
all Iris sources with the gate's strict flags, qualify the unavailable
Islaris/Lithium/Katamaran combination, or establish a local Sail-language instance.

### What the selected example proves about

`riscv_test_adequate` is an adequacy theorem over Islaris's `nsteps`, an
instruction-address-to-trace map and byte-memory/register maps constructed in
`examples/riscv64_test.v`. Its premises constrain the example's RISC-V system
registers, an aligned stack address and a non-wrapping memory region; its conclusion
is not-stuck execution and the specified final instruction-trap event, depending
on `x11`. That is a meaningful upstream unary-safety example with a trace result.
It does not quantify over the emitted `rv64d` definitions, CHERI capabilities,
the merged capability/integer register file, the purecap ABI, local attestation,
relational constant-time or cycle cost. Its `isla_adequacy` dependency establishes
safety for Islaris's trace semantics; naming that theorem supplies no adequacy of
the canonical Sail term.

The published Iris package constraints are retained as [`/root/build/lane-q35c-20261010-logic/q35c/iris-metadata.opam`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/iris-metadata.opam), SHA256 `2aa6fde505ddec258f651ba2f96a9cc598d3aa774e38ec3713f8287bd4db4474`.
The strict compiler output for the positive probe is [`/root/build/lane-q35c-20261010-logic/q35c/iris-strict-import.log`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/iris-strict-import.log), SHA256 `188ff29b8a0705f491438ebf47623e533fe60658944f3f1f58e1f9b5badb1bcf`.

The locked prover and installed package inventory are [`/root/build/lane-q35c-20261010-logic/q35c/prover-version.log`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/prover-version.log), SHA256 `bed18c6aed8995deb0f7988289c882981df1dc032ea306912c9b81bd96cd3907`
and [`/root/build/lane-q35c-20261010-logic/q35c/switch-inventory.log`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/switch-inventory.log), SHA256 `9817de3255df937ce2368f253164ebb40a7df96044c811191aa393029f05ed01`.
The byte-identical switch snapshots are [`/root/build/lane-q35c-20261010-logic/q35c/switch-before.export`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/switch-before.export), SHA256 `3e70338fb77832f9e09ee8780cd10524e002420b1ca9aa5f56a15777765e1b32`
and [`/root/build/lane-q35c-20261010-logic/q35c/switch-after.export`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/switch-after.export), SHA256 `3e70338fb77832f9e09ee8780cd10524e002420b1ca9aa5f56a15777765e1b32`; their command logs are
[`/root/build/lane-q35c-20261010-logic/q35c/switch-export-before.log`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/switch-export-before.log), SHA256 `73f7d708ddfeaa846af9ef6a9759e091a31ec9c2d32a6cf62dfb0f5bf1bf1d3a` and [`/root/build/lane-q35c-20261010-logic/q35c/switch-export-after.log`](../implementation/retained-evidence/root/build/lane-q35c-20261010-logic/q35c/switch-export-after.log), SHA256 `73f7d708ddfeaa846af9ef6a9759e091a31ec9c2d32a6cf62dfb0f5bf1bf1d3a`.

## 2. The one machine subject and required Isla interface

[Q35b's generation identity](canonical-machine-term.md#2-generation-identity)
is the common subject. It names primary-composition hart 0, the frozen
`verifiedos.json`, Sail 0.20.3 and the source/library/plugin identities. The
generation-identity section and its linked receipt own the output digests and
complete input inventory; every local consumer cites that owner or its own fresh
generation receipt.
This item does not regenerate that term, measure its compile, remove its axioms
or assign it an accepted closure. Q35b still owns the support-library carriage,
strict compile and exact closure; F-477's other-hart/composition question remains.

The machine step used by every theory must invoke the emitted `try_step`,
including its trapping/exception branches. Its per-step entry is used rather
than claiming unbounded execution of the emitted `loop`, which Q35b records as
bounded by 100. U-08 owns the leakage/cost projection in the term's vocabulary;
U-09 owns the measured magnitudes, and an unqualified magnitude stays symbolic.
Q35f's host hooks are silent machine-only bodies, so no theory infers a host's
terminal, persistence or scheduling behavior from them.

The required producer interface is an explicit, bounded result carrying:

- the exact final instruction bytes and address/slot grid, canonical generation
  identity, source and tool revisions, configuration, all constraints and the
  exact event/primitive vocabulary;
- a finite branch tree with register, memory, tag and exception effects, its
  coverage obligation and a distinction between producer failure and a genuine
  no-execution result;
- a kernel-checkable relation from each trace tree to the canonical `try_step`
  result for every entry state satisfying the stated precondition, including
  all defined exceptions and the leakage/cost projection;
- an independently replayable trace/refinement certificate. A solver result or
  a producer assertion is never that certificate. Any retained SMT fact takes
  R-05-017's pinned in-kernel reconstruction route.

The selected Islaris frontend invokes `isla-footprint` with a snapshot, entry
function `isla_footprint_no_init`, a TOML configuration, `--simplify-registers
--tree -s -x`, opcode bytes and optional reset constraints/linearization.
`frontend/decomp.ml` then parses the returned trace and emits Rocq files plus an
address table. `bin/isla-footprint` runs Isla's Rust producer against its
snapshot. The README's tested producer and snapshot pins are respectively
`b8e614bda4a20e42c37d8b216853653133d04322` and
`b58da9170470a422c9396983ac8f87f0a63ba6f8`. They identify the upstream example
interface, not a qualified producer for this frozen profile.

The upstream RISC-V TOML enables compressed instructions, uses `rv64imac`
assembly and the `PC`/integer-register scheme. That configuration does not
implement VerifiedOS's bundle-slot decode, CHERI tag effects or merged-register
discipline and is not reused as its profile. The existing `sail-isla` helper
qualification supplies finite helper evidence under its own contract; it does
not provide this complete instruction/trace connection. In particular a
producer's `Assume false` must not prove safety by deleting an executable
canonical branch. A missing branch, changed opcode, dropped tag, wrong offset
or wrong exception must fail the correspondence check.

## 3. Retained Katamaran route and one Iris instance

R-13-016 stays unchanged. The route is:

1. Emit the canonical machine term with Sail's own backend, under Q35b's identity.
2. Generate candidate μSail for the selected instruction subset using the pinned
   Sail backend, or author a translation under a separately reviewed producer
   contract. A changed producer needs its own licence and R-05-020 record.
3. Prove **`machine_muSail_agreement`**, a proposed constant, connecting μSail's
   register/memory/exception relation to the emitted `try_step` on the selected
   instruction family. Both directions preserve the entry-state relation,
   result, exact trap behavior, capability/tag/provenance effects and the shared
   leakage/cost observation over every finite prefix. State and observation
   representations are named definitions, with inhabited tagged entry states.
4. Katamaran proves per-instruction separation-logic contracts in that μSail
   instance. Its `Iris/Instance.v` adequacy/soundness results are reused only
   after their locked-prover qualification and the agreement transports each
   selected contract back to the canonical term.
5. Prove **`machine_trace_agreement`**, a proposed constant connecting the
   untrusted Isla trees to those canonical instruction effects; branch coverage
   is part of the theorem. The unary logic consumes the transported contracts,
   rather than treating a recorded Isla tree as authoritative ISA semantics.

No existing constant found in the inspected sources states either local
agreement. The μSail producer's output, Katamaran's adequacy over its own
`microsail_lang`, and Islaris's adequacy over `nsteps` each stop before this
connection. The whole-profile `machine-logic-agreement` work remains unpriced
and owned by the machine-logic hardening deliverable. A first finite agreement
for Q35d's instruction family must be separately scoped and priced by that owner
before its implementation opens; neither Q35c nor Q35k absorbs it.

The proposed common instance is **`verifiedos_machine_lang`** of Iris 4.5.0:
one primitive-step relation over the emitted term, one physical-memory/tag and
merged-register state interpretation, and one authoritative immutable code-image
resource indexed by final bytes and generation identity. Its unary theory
supplies stack/return-sentry ownership; its universal, relational and cost
theories consume the same interpretation and step relation. Concurrent or device
steps require the actual composition relation rather than inventing a second
Sail transcription. The first instance is hart 0 with the explicit ordinary
memory and scalar-instruction scope of Q35d, not a full multicore/device logic.

Iris 4.5.0 is the released baseline selected for Q35m's compatibility trial.
No Islaris/Lithium/Katamaran combination at that release is accepted by this
selection. Replacing it with a development pin or importing a new library set
requires the opam owner's carriage decision and renewed qualification. The
single-instance design, reuse of the emitted anchor and retirement of any
unconnected trace semantics are the three arguments the eventual R-05-020 record
must show, not merely assert.

A direct-over-term instruction-rule route is a possible different proposal.
It would still need the single term, four theories, exact-byte correspondence and
the R-05-020 arguments, but dropping Katamaran/μSail requires a reviewed amendment
to R-13-016 with its prose co-read. This breakdown does not adopt that alternative
or claim its presumed smaller setup cost.

## 4. Per-theory work and the first checkable increments

Each row describes mandatory establishment work; `unpriced` means no defensible
full-establishment figure, not zero effort or permission to start construction.
R-13-017 remains one logic and none of its four theories is waived by a unary
trial.

| Theory | Start | Owns and first checkable increment | Check | Join and cost |
| --- | --- | --- | --- | --- |
| Unary safety | Q35b's strictly compiled term/closure; Q35m's qualified libraries; separately landed selected-subset agreement; U-08's shared projection. | Q35k's finite ordinary-memory/scalar instance: step lifting, code/merged-register/tag ownership, trap treatment, ABI call/return resources and adequacy over `try_step`. First increment is a checked single `addi` step and a constructed tagged state, followed by the selected two-function rule family. | Proposed `machine_unary_adequacy` and `machine_unary_return_adequacy`; constructed legal and trapping entry states, bad opcode and missing-branch refutations; strict compilation, exact assumption audit and whole-environment kernel recheck. These names are delivery targets, not existing constants. | Q35l, Q35d, Q2b and U-26. Full establishment is unpriced; the checklist prices Q35k's conditional finite cell. |
| Universal capability/attestation contract | Landed unary interpretation and selected-subset agreement; Cerise `9eb72e675216d7c5473499f392b18049364db03a`, Cerisier `57ed584ae17eed308ae0fa554cf0dde9843112c1`, with nested dependency terms resolved as THIRD-PARTY.md requires; reviewed compartment, lifetime and attestation statements. | First increment transports one capability-derivation contract for `cincoffset` to the actual canonical clause, preserves tags/permissions/bounds and constructs a resource-invariant witness. Then extend to adversarial admitted contexts and attestation with the actual local key/seal policy. Cerise's abstract machine does not become the ISA by renaming it. | Canonical-step monotonicity and the client entailment hold for all admissible operands; authority-widening and invalid-tag variants are refused. Later universal-contract/attestation adequacy must quantify over the reviewed adversarial context, not only known Q35d callers. | `machine-logic` hardening owner, U-25, Q23c, Q2b and artifact admission. First increment and full establishment are unpriced pending concrete resource/attestation interface review. |
| Relational constant-time | Same unary interpretation and U-08 leakage projection; U-27's reviewed statement; public/secret labels, declassification and scheduler observations fixed by their owners. | First increment proves two `addi` steps from publicly related states have equal projected observations, and a secret-controlled branch is a distinguishing counterexample. The full theory composes loops and the admitted binary's actual termination/progress discipline. | Proposed `machine_relational_adequacy` relates both canonical executions and their full required leakage traces; a secret-dependent branch/address and omitted timing observation each fail. Unary not-stuck adequacy is insufficient. | U-27, the constant-time TAL metatheorem and unstructured binary CT proofs. Unpriced: neither a checked binary rule family nor the full labeled observation relation is supplied by inspected Islaris. |
| Syntax-directed cost | Same step relation/U-08 table; qualified magnitudes at U-09 or explicit symbols; U-28 and schedule/isolation contracts. | First increment proves the annotated `addi` step charges its named table constant; a read then distinguishes memory class. Loop composition carries a symbolic step/cycle sum and a declared bound, rather than interpreting wall-clock proof time as machine cost. | Proposed `machine_cost_adequacy` upper-bounds every allowed canonical execution by the syntax-directed charge. A too-small charge or changed memory-class tag fails; no numeric WCET conclusion precedes qualified magnitudes and the isolation join. | U-28, WCET tooling, per-binary bounds and on-device producer. Unpriced: cost projection/magnitudes and loop-rule interfaces remain open. |

StkTokens remains the linear/affine stack-discipline design input named by
R-13-017; no source mechanization or independently admitted fifth logic is
assumed. Q35k's first ABI resource model must preserve the actual stack capability
and return sentry. This supplies neither the general scoped-loan restoration
the foundation ledger assigns to `scoped-resources` nor a full stack security
theorem against arbitrary linked code.

## 5. Proposed finite cells and prerequisite boundaries

The following contracts support the separately adopted
[Q35m, Q35k and Q35l checklist cells](../implementation/implementation-checklist.md#q-assessment-actions),
which alone own their estimates. Each starts only after its contracted prerequisites are landed;
the foundation owner re-reads the resulting interfaces and reprices the finite
implementation scope before dispatch if those interfaces move it. Q35d's own
estimate continues to exclude all three cells and the unpriced agreement.

### Q35m · Trial the machine-logic dependencies at the locked prover

**Start:** this source/manifest/build-failure receipt; locked Rocq 9.3.0 and Dune
3.24.2, stdpp 1.13.0; released Iris 4.5.0; pinned Islaris/Katamaran; actual
Lithium/RecordUpdate/isla-lang dependency identities and licences selected by the
trial. Any private switch or source package remains outside the shared proof
switch; opam carriage is a separate owner decision.

**Owns:** one bounded compatibility trial that adapts the build/package interface
to the locked prover, keeping the selected example and adequacy statements and
definitions unchanged. It records every source/configuration diff and dependency
identity. It attempts both the Islaris selected-example closure and Katamaran's
Iris soundness/adequacy closure under the same selected Iris release. The trial
does not construct a μSail translation, weaken diagnostics/assumptions or port an
unbounded framework. Its attended cap is 12 h; a deeper API/semantic port found
beyond that cap is a named unpriced continuation for the foundation owner.

**Check:** either both unchanged-statement closures compile at the locked prover,
their exact compiler assumptions and whole-environment kernel summaries are read,
and the strict-import behavior and proposed carriage are recorded; or a named
incompatibility is reproduced and the qualified result is refusal with its next
owner. A port uses the frozen elaborated-reading comparison the proof-assistance
workflow requires. A successful non-strict library build alone is not acceptance.

**Join:** an accepted compatible/carried instance is Q35k's prerequisite;
a refusal leaves Q35k closed to implementation until separately commissioned
repair or an admitted route change. The checklist's estimate prices the trial
and its refusal endpoint, not guaranteed framework-port success.

### Q35k · Establish the first unary-safety increment over the canonical term

**Start:** Q35b's accepted strict compile and exact closure, Q35m's compatible
carried libraries, separately landed `machine_muSail_agreement` and
`machine_trace_agreement` for the selected family, and U-08's annotated projection.
The dependency port, first agreement proof and whole-profile translation remain
outside this cell. Missing prerequisites refuse dispatch rather than beginning a
direct-over-term route silently.

**Owns:** `verifiedos_machine_lang`, the physical byte/tag/merged-register
interpretation and code-image resource for primary-composition hart 0; the
transported instruction rules actually reached by the two Q35d functions after
decoding their exact released bytes; non-wrapping operand arithmetic, fault/trap
branches, ABI stack/return rules and `machine_unary_adequacy` with
`machine_unary_return_adequacy`. Function-specific disjointness contracts, their
loop proof and recompilation measurement remain at Q35d; memory representation
and law proofs are Q35l. The actual decode's instruction set is read from the
image, and source assembly pseudo-operations are not assumed ISA rules.

**Check:** each rule checks against the landed agreement; a constructed tagged
initial state inhabits the interpretation; a normal instruction and malformed
tag/opcode/trap case distinguish the result; call/return preserves the ABI's
stack and return-sentry resources; omitted canonical branch, false producer
constraint and bad byte are refused. Record the named constants' exact
assumptions, strict compiler result and whole-environment kernel result on hosted
fresh proof acceptance before placing the instance in `proofs/`.

**Join:** Q35l, Q35d's two contracts, U-26 and the later universal/relational/cost
increments reuse the same step interpretation. The checklist's conditional
engineering estimate is grounded in the two existing scalar functions and ABI;
it is not a measured port benefit or an estimate for R-13-017's full logic.

### Q35l · Establish the concrete byte-instance laws for the cold-path trial

**Start:** Q35k's canonical state/resource interpretation and rules; the compiled
slot/frame layout and byte/address identities Q35d binds; the actual Sail
read/store, tag-granule and capability-offset clauses; the purecap ABI's stack
and backward-edge return-sentry contract. Compiler carriers alone are insufficient.

**Owns:** byte/initialized-span ownership, ordinary integer field representation
and separate tagged capability-cell ownership; proposed `byte_read_sound`,
`byte_write_sound`, `cap_read_sound`, `cap_write_sound`,
`bounded_advance_sound` and `memory_frame_sound`. Read laws cover little-endian
32/64-bit fields and preserve the source/disjoint frame. Write laws cover the
loop-index stack stores and exact byte-store tag clearing, while capability
load/store laws preserve the saved `csp`, `cra` and frame-capability tags.
Bounded advance preserves provenance/permissions and states representability,
overflow, legal end pointers and legal dereferences separately. Memory framing
quantifies over tag granules as well as addressed bytes: byte-disjoint spans
sharing a tag granule do not justify preserving an unrelated capability tag.

**Check:** construct readable slot and exact frame capabilities with initialized
fields and correctly tagged stack/return cells. The first function reads only
its two record spans; the second reads the slot-count field and the first
`min slot_count VOS_MAX_SLOTS` records, without an artificial input bound on
`slot_count`, and writes only its declared stack frame. Refuse wrong-offset
reads, wrong stores, partial initialization, untagged, sealed or missing-permission faults,
wraparound and a purported frame law that ignores a shared tag granule. Empty
spans, last-byte/end-pointer cases and capability/tag restoration each have an
explicit witness. Audit every law at the exact canonical term and assumption
set; stronger scoped-loan/concurrency restoration is outside this finite instance.

**Join:** Q35d's two function contracts and future Q2b byte clients only where
their resource scope matches. The general byte-instance and scoped-resources
hardening obligations remain separate and cannot inherit completion from these
two functions' scope.

## 6. Review and acceptance boundary

The Tier-A review reads R-05-019b/020/023a/163/164, R-13-016/017 and their
prose against this breakdown. It must distinguish the source and build-failure
qualification from acceptance of a logic; retain the named Katamaran agreement
duty; review all proposed cost boundaries and witnesses; and accept the new
cells as an owner act. This record moves no register entry and offers no positive
R-05-163 verdict for the selected example.

Q35c's source identity, actual licence, attempted locked-prover build, required
Isla interface, selected example and failed audit status are recorded. The Iris
release/instance choice, each theory's first increment and consumer, and the
separate proposed cells are explicit. The outstanding **implementation** inputs
are Q35b's compile/closure, qualified/carried dependencies, the selected-subset
and full-profile agreement work, U-08's annotated projection, the unary increment
and byte laws. The remaining three theories and contextual/admission joins keep
their mandatory hardening owners and are unpriced where this inspection cannot
justify a range. Full gates run only on GitHub Actions under the settled-main
validation handoff; pending Guest CI is not represented as a pass here.
