# Fixed package layer comparison

Status: **fixed packages selected; cost qualification open**. R-13-028 selects
[the fixed-package contract](../contracts/fixed-packages.md). Q31 in
[the project plan](../../../PLAN.md) measures that default against explicitly
constructed roster-wide optimization. Missing measurements supply no performance
claim and do not put unchanged packages back through mandatory lowering.
The [architectural disposition](../../background/architectural-alternatives.md#a-fixed-package-layer-with-a-declared-contract-deferred-to-the-comparison-r-13-028-names)
records the same boundary.

## 1. Default and optional optimization

A fixed package binds its source closure, interface and resource contract,
immutable code-and-rodata, writable initializer, derivation template,
correspondence theorem and required hyperproperty objects. Ordinary composition
maps those objects without rewriting or re-lowering them, then performs the
roster's placement, scheduling, capability-wiring, handler-graph and global
resource checks. Concrete-layout CHERI-TAL bindings are fresh for every generation.
Package-local CIC verdicts are reusable only through the authenticated checked-set
interface in [the contract](../contracts/fixed-packages.md#reusing-checked-proofs-across-generations).

The comparison arm constructs explicitly named replacement artifacts to exploit
cross-package merging or specialization. Their new bytes and contracts require
fresh applicable evidence. It is an optional construction act, not an implicit
pass over every package during an ordinary install. The comparison reports the
whole replacement closure rather than treating unchanged semantic package names
as proof that its code or certificates stayed unchanged.

Native installation remains a signed generation committed by the A/B transactor
and activated at the next boot (R-13-001a). Neither arm mutates a running native
image, fills a pre-proved empty compartment slot (R-13-001b), adds runtime binding,
or trusts the producer. The per-install work is divided by what is actually
reused: object hashing and generation-level checks still cover the roster.

## 2. Placement and optimization boundaries

The first executable path translates all regions of one package by one common
base. That preserves code-to-data displacements and the package-relative region
geometry. The package's proof must establish that this placement contract fits
its actual instructions; a metadata assertion is not that proof. Two-layout
qualification uses two translations permitted by the declared memory classes,
alignment and address bounds. Independently moving code or data needs the
separately proved capability-relative ABI in R-13-028.

The frozen dictionary (R-15-036i) can encode roster-invariant bytes. R-15-036l's
call/address comparison remains relevant to their size, but composition cannot
patch an admitted fixed object's instructions to take another arm. PC-relative
internal code is one implementation of common-translation invariance; a different
producer must supply its own corresponding placement evidence. TAL-067 and
TAL-068 still require a derivation bound to the final concrete layout.

Package-local dead elimination keeps the contract's exports, scheduled entries
and interrupt roots. Outlining and tail merging retain R-15-036o's compartment
boundary. Shared service compartments remain separately constructed packages
with export worlds. Cross-package identical-function merging and removal of
exports unused by one roster can spend additional bytes or proof work; Q31
measures those terms rather than assuming their magnitude.

Fixed region contracts retain their memory classes, relative bank geometry,
reservation intervals and resource bounds. The generation places their declared
spans and verifies that actual wiring and resources satisfy the contracts.
Changes outside a proof's admitted premises require a new contract, artifact or
checking context; they are not accepted as a cache hit.

## 3. The contract a package fixes ahead of its roster

[The fixed-package contract](../contracts/fixed-packages.md) owns the executable
interface. This table traces the package and composition responsibilities to
the existing obligations; it does not supply their implementation or proofs.

| Clause | Owner | The package fixes | The composition still chooses |
| --- | --- | --- | --- |
| Interface world: imports, exports, IDL types and labels | R-12-013a, IDL-029, IDL-030, R-05-117 | The typed boundary, every cross-compartment edge as a sentry named in the import and export tables | Which exporter satisfies each import, and the wired sentry capability |
| Internal compartment graph and per-library sub-manifests | R-13-024, R-08-034, R-14-006 | The nodes and edges inside the package and each node's authority ceiling | Nothing; the graph is the package's |
| Bounded pools: capacity, element type, exhaustion action, lifecycle | R-08-046, R-08-047 | Every capacity and every declared action | Placement of the pool's backing inside the island |
| Region extents and live ranges as exported reservation intervals | R-08-011, R-08-018a | The intra-package colouring and the reserved span it charges | The island and base at which the span is placed |
| Memory class per region and per code object | R-15-247j, R-15-247 | The class assignment the bounds were derived under | Nothing without re-lowering; a different class is a different fixed-layer object |
| Declared interleave of the package's internal objects across banks | R-08-012a | The relative bank pattern its objects assume | The bank set that pattern is mapped onto |
| WCET per operating point, as cost annotations on the derivation | R-11-015, R-11-017 | The per-activation bounds under the fixed class assignment | The slot width, offset and rung the bounds are placed in |
| Ring depths, device windows and standing reservations the package needs | R-11-010, R-12-005, R-11-008 | Each depth and each window's extent | The schedule slot and NoC reservation that serve them |
| Tier and the secret-labeled set | R-13-011, R-13-020 | Which certificates the package carries | Nothing |
| Dead-elimination roots | R-13-010a | The export table and the scheduled and interrupt entries as the reachability roots | Nothing; an export no roster member imports remains resident |
| The versions the proofs are stated against | R-11-005, R-11-005b, R-05-135b | The spec-set, model, descriptor and profile versions in the certificate header | Nothing; a rev is a new fixed-layer object |

## 4. Objects and work at a generation boundary

| Object or act | Fixed-package default | Optional roster-wide optimization |
| --- | --- | --- |
| Source closure and interface/resource contract | Fixed, content-bound inputs | Names the complete affected replacement closure |
| Code-and-rodata and writable initializer | Existing bytes mapped unchanged | New replacement bytes need fresh evidence |
| CHERI-TAL derivation | Template bound and checked at each concrete layout | Bound and checked for the replacement layout |
| Source-correspondence and hyperproperty objects | Fixed objects; authenticated verdict reuse under exact context equality | Changed objects or context require actual checking |
| Capability wiring and handler graph | Fresh for each roster | Fresh for the optimized roster |
| Placement, initialization, schedule and global resources | Fresh roster checks over declared package spans | Fresh checks against the replacement contracts |
| Generation root, checked-set root and signature | New transaction commits all roots together | The same transaction and failure rules apply |

## 5. Artifact, store and checked-state identity

The artifact identity hashes a canonical manifest containing the digests of the
actual code, initializer, proof/template and required hyperproperty objects,
together with the source closure, contract and version bindings. A hash over
producer inputs alone is a build lookup key: two nondeterministic but valid
outputs can share those inputs and still have distinct artifact identities.
The content-addressed store verifies the actual objects and never silently
repairs corrupt bytes under an existing name.

A prior successful check is reusable only from the current admitted generation's
authenticated checked-set root. The trusted admission adapter obtains that root
from admitted state; a package, downloaded receipt, composer or candidate
signature cannot nominate it. Restoration authenticates the complete prior set.
Its exact reuse key includes the artifact/proof/source/contract identities and
specification/model/profile/decoder, checker, CIC environment, assumptions, tier,
policy and resource context. A changed member requires the actual checker.

Package-local successes are staged until the complete new generation passes.
Failed package checks, fresh TAL/wiring/global checks or interrupted composition
publish no successor checked set. The existing authenticated transaction commits
its root with the generation and applies the same rollback and recovery rules.
A returned candidate set is not independently admitted state.

The transparency name commits to the source closure and interface/resource
contract, the common package identity R-13-023b names. Publishers may additionally
commit the realized artifact hash. R-13-026 keeps mandatory reproducibility at
the base image and checker bootstrap; fixed packages gain no implicit requirement
that two valid producers emit identical bytes. Descriptor and semantic-version
steps retain R-11-005b's compatibility and re-admission rules.

## 6. Construction, composition and installation

Package construction lowers the exact closure against its contract, performs
package-local elimination and optimization, emits the fixed objects and their
evidence, and assigns the actual output identity. Local construction and fetching
are equivalent inputs to admission (R-13-001c, R-13-027).

Composition selects those fixed artifacts, checks imports and export contracts,
places their declared spans, constructs wiring and the handler graph, obtains a
concrete-layout TAL binding and the roster's resource/scheduling evidence, then
prepares the signed generation. No unchanged package producer is invoked merely
because the roster changed.

Installation rehashes every named object. It checks each fresh layout and the
whole generation, and invokes package-local CIC checking for objects with no
matching authenticated prior verdict. A changed package therefore changes its
construction and package-local checking work; the roster-wide hashing, typing,
placement and global checks remain. The resident toolchain's pool and activation
budgets still apply, proof search is not an install step, and activation still
pays a boot and durable-state restoration. No current measurement establishes
end-to-end latency on the device.

## 7. Qualification and evidence boundary

Q31 remains open until the real backend, composed roster and M6.10 path supply
revision-bound costs and proof connections. Host artifact/store and coordinator
controls establish their tested boundary; they do not instantiate the missing
native correspondence producer, TAL profile/checker or CIC consumer in
[the production handoff](../contracts/production-admission.md).

| Quantity or obligation | Required evidence |
| --- | --- |
| Cross-package merging and unused exports | Freeze S2/S3 counts split at the package boundary and actual retained bytes for both arms |
| Encoded size and cycles | Actual package-relative instruction strata and the R-15-036l/R-15-036p freeze measurements |
| Schedule and capacity | The same roster's admission artifact, slack, reserved spans and padding per island under both arms |
| Changed-package installation | Source/producer/checker observations separating construction, package-local proof work and fresh roster checks, plus Q9's actual turnaround |
| Correspondence and placement | A theorem over fixed bytes with contract premises, the actual common-translation or capability-relative placement lemma, and the wiring/linking connection to the installed objects |
| Concrete TAL binding | One actual package bound and checked at two permitted layouts under TAL-067/TAL-068 |
| Reuse across reboot | Authentication of persisted prior checked state; exact-context invalidation; unchanged-object reuse and changed-package checking with fresh TAL/wiring/global checks |
| Failure atomicity | Failed or interrupted checks preserve the admitted generation and checked-set root; an unsatisfied import refuses composition |
| Transparency and reproducibility | Source/contract package-name binding, optional artifact commitment and unchanged base/checker reproducibility obligations |

An unknown coefficient remains open. An optimization may be retained only with
its measured benefit, complete replacement identity and required fresh evidence;
qualification supplies no authority to rewrite default package objects silently.

## 8. Prior art read against the boundary

Each source is a published reading and none is inspected, pinned or qualified here; a record in [the proof reuse inventory](../../assurance/proof-reuse.md) is owed before any import.

| Source | What it establishes | What it does not supply here |
| --- | --- | --- |
| Glew and Morrisett, [*Type-Safe Linking and Modular Assembly Language*](https://dl.acm.org/doi/10.1145/292540.292563), POPL 1999 | A TAL object file is a heap with an import interface and an export interface, and linking preserves type safety when the interfaces agree; a fragment checked against a fixed import interface reaches only the labels that interface names | CHERI capabilities, the concrete-layout binding TAL-068 requires, and any timing or memory-plan clause |
| Feng, Ni, Shao and Guo, [*An Open Framework for Foundational Proof-Carrying Code*](https://flint.cs.yale.edu/publications/ocap.html), TLDI 2007 | Modules certified separately in different logics link into one certified system through a common assembly-level interface, which is the tier mixing R-13-011 already performs at the manifest | A Coq statement over this profile, and the wiring table as the linking act |
| Kang, Kim, Hur, Dreyer and Vafeiadis, [*Lightweight Verification of Separate Compilation*](https://sf.snu.ac.kr/sepcompcert/), POPL 2016; Zhang, Wang, Wu, Koenig and Shao, [*Fully Composable and Adequate Verified Compilation with Direct Refinements between Open Modules*](https://dl.acm.org/doi/10.1145/3632914), POPL 2024 | A verified compiler's correctness can be stated per separately compiled module and composed at link time, the open-module form giving a direct refinement between native semantics; this is the shape a fixed correspondence theorem over one package would take | The CHERI backend, robust preservation (R-05-024) and the platform's linking act |
| Beringer and Appel, [*Verified Software Units*](https://link.springer.com/chapter/10.1007/978-3-030-72019-3_5), ESOP 2021 | Separately verified compilation units compose at their specification interface, with subsumption letting a client expect a weaker specification than the unit proves | Binary-level statements and anything below C |
| seL4 [Microkit](https://docs.sel4.systems/projects/microkit/manual/latest/) | Each protection domain is a separately built ELF and a system description file names the domains, channels and memory regions; one tool packages them into a bootable image | Proof-carrying artifacts, admission, and the memory plan and schedule this design composes; the images are trusted, not checked |
| Oxide [Hubris](https://hubris.oxide.computer/reference/), with [the build description](https://cliffle.com/blog/from-hubris-to-bits/) | Tasks are compiled separately, laid out at build time from a declared memory map and relinked against their allocated partition, a shipped instance of per-component placement chosen after per-component build | Capability wiring in place of relinking, and any proof |
| [CHERIoT compartments](https://github.com/CHERIoT-Platform/cheriot-rtos/blob/main/docs/architecture.md) and [CHERIoT-Audit](https://cheriot.org/rtos/firmware/auditing/2024/03/01/cheriot-audit.html) | Compartments are linked separately with import and export tables, the loader supplies a capability only where linker metadata instructs it, and the linked image carries a report of what compartments hold and how they communicate; this is the import-table and wiring shape R-13-003 adopts | A verified loader, a verified reader, and a contract fixed ahead of the image |
| [Tock's application credentials](https://book.tockos.org/trd/trd-appid) and [binary format](https://book.tockos.org/doc/tock_binary_format) | Separately built applications carry credentials in a footer over the integrity region, and a kernel-side checker decides which to load, credentials being a summary the kernel verifies and never trusted content | Proof-carrying admission, static composition, and the placement this design fixes at composition |
| [Fuchsia component manifests](https://fuchsia.dev/fuchsia-src/concepts/components/v2/component_manifests) | A package carries a compiled manifest declaring the capabilities a component offers, uses and routes, and static children cannot be created or destroyed at runtime; the manifest is the contract the framework composes | Proofs, admission, and the bounded resources this design's manifest declares |
| Nix [content-addressed derivations](https://wiki.nixos.org/wiki/Ca-derivations) | Naming an output by its content rather than its inputs lets a downstream build be skipped when the upstream's bytes did not change, and loses that cutoff wherever the output is not bit-reproducible | The proof objects, the authenticated verdict-reuse interface, and the platform's already content-addressed store |
| LLVM [ThinLTO](https://clang.llvm.org/docs/ThinLTO.html) | Whole-program analysis over per-module summaries with per-module backends and a cache recovers much of monolithic link-time optimization's cross-module gain incrementally | A verified form, and the merge transforms R-13-010b names; it suggests an optional optimization over package summaries, not a qualified implementation here |
| Hahn, Reineke and Wilhelm, [*Towards Compositionality in Execution Time Analysis: Definition and Challenges*](https://embedded.cs.uni-saarland.de/publications/TowardsCompositionality.pdf) | A decomposition is timing-compositional only where local bounds combine into an upper bound on the whole, and the interdependencies of current processors defeat that in general | The property itself, which here rests on the fixed per-class constants and the non-work-conserving frame rather than on an analysis |

## 9. Decision boundary

R-13-028 has selected fixed packages. Q31 measures their costs and the explicit
optimization arm rather than deciding whether ordinary installs may reuse them.
The comparison supplies no benchmark result, modular correspondence theorem,
native checker acceptance or resident end-to-end result. Their owners and
acceptance boundaries remain in [the project plan](../../../PLAN.md) and
[the fixed-package contract](../contracts/fixed-packages.md).
