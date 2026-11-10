# Contained compiler port decisions

Q39 owns the contained compiler's locked switch, compatibility port and acceptance
predicate in the [project plan](../../PLAN.md). The
Rocq 9.3.0 port compiles and its frozen-reading comparison passes. Complete
kernel qualification, classification, final stability, target replay and manifest
restaging remain open. The interrupted audits and bounded diagnostic below
supply no kernel acceptance. The project proof switch's lock is unchanged;
F-565 and F-525 remain standing.

## Candidate selection

The upstream pairing, Rocq 9.1.0 with OCaml 4.14.2 and Menhir 20260209,
completed the compiler build but failed its complete all-`FILES` kernel audit
with exit 129 in `MenhirLibParser.Inter.ValidSafe.safe_is_validator`, reporting
`Modops.ModuleTypingError`. A parser-only diagnostic reproduces the failure.
This pairing supplies no passing kernel acceptance.

The selected candidate is the Rocq 9.3.0 compatibility port with the locked
OCaml 4.14.4 and Menhir 20260209 releases. Its portable lock contains released packages only. Q39
requires two independent clean qualifications, including the independent
lock-import build, before accepting that compiler.

## Repair and frozen-reading verdict

The thirteen compatibility-port files are committed at contained revision
`7093854d8ce8799826618024ee4847cf248766ea`; `make -k -j2 proof` passes. The
register-exclusion proofs use existing `preg_notin_charact` and `preg_of_not_PC`
lemmas while preserving declarations, transparent bodies, net transparency
settings, hypotheses, admissions and compiler flags.

The exact frozen comparison passes for 1,606 declarations across those thirteen
modules, 197 generic parser declarations with 105 transparent or inductive bodies,
and the three changed transparent bodies instantiated with `Parser.Aut`. The
generic query also instantiates the interpreter with arbitrary
`A : MenhirLib.Automaton.T`. Both readings use the same Rocq 9.1 prover identity
and printing settings, with zero exact differences.

The baseline was reconstructed from immutable pre-edit
`d08768db051ebb5cbe92ea24eeacbd63b9eaf84a` and its compiled-object checkpoint;
no pre-edit sealed print is claimed. Reader-only source uses `Zmod_0_r` in two
proof-script occurrences where the Rocq 9.3 build uses `Z.mod_0_r`, without a
statement or definition change. The native comparison receipt is
`/root/build/lane-checklist-20261010-c/q39/frozen-readings/frozen-comparison.json`,
SHA-256 `baab4b5975b5e3caa86ba62b7ff480d84a5066c999a6e6e2713d7390b9c9c928`.
This comparison supplies no separate clean-build, kernel or target verdict.

## Focused simulator dependency for compiler replay

Q39's HELLO and large-argument replay consume a focused simulator-build receipt.
The producer configures the current verifiedos profile and builds only the
explicit `sail_riscv_sim` CMake target with its normal dependencies. Its distinct
schema and profile identify successful configure and target-build stages, exact
commands, model-file population and digests, profile digest, simulator digest,
and actual Sail, CMake and C++ tool identities. Inputs and tools must match
before and after the build in the exclusive native lane. No `ctest` or complete
model verdict is represented.

The reader binds unique configure/build arguments to the recorded absolute roots
and retained CMake cache, CMake's selected Sail and C++ executables to their
measured identities, and the generated schema and validation log to their hashes.
It refuses missing or malformed identities, failed stages and command/cache/schema
drift. Original roots remain evidence identities after retirement; current model
bytes are checked without requiring the retired checkout to exist. General target
readers retain their complete-build contracts.

The bounded [fixed-package boot fixture](contracts/boot-roster.md#fixed-package-image-observation)
may also use this dependency for its finite translated-layout observations.
Validate the focused receipt before and after execution, binding the current
model, profile, native tools, logs and simulator. This use establishes only that
fixture's observations on the source-bound simulator. It supplies no complete
model verdict, qualified compiler, real-roster admission or final target acceptance.
Other target consumers retain their complete-build receipt requirements.

The reviewed implementation at VerifiedOS
`603bcd302fb194ae19886240134636b13ad16f49` has passing focused controls. Its
accepted focused build passes configure and the simulator target; the native
receipt is
`/root/build/lane-checklist-20261010-c/q39/simulator-dependency-2/simulator-build.json`,
SHA-256 `4b6e41da6f446e6e312397cc7fdb2b6c398c4ec6bceb2740533ca002f9139b0c`.
Tests are explicitly unrun. HELLO's actual execution and three controls, the
typed large-argument replay and a passing compiler kernel-bound receipt remain
required. Complete model acceptance belongs to GitHub Actions.

## Preserve signed images while refreshing compiler bindings

`chain-stage --preserve-images` recompiles every chain unit through the rebuilt
compiler and refuses any stream difference before writing. It preserves existing
image, key and header bytes, re-derives payload layouts and verifies retained
signatures with OpenSSL. Only successful joins may update source, include,
compiler and freeze identities. Missing or invalid artifacts, signatures or
layouts refuse publication. Unchanged image bytes alone establish no join.

VerifiedOS `528ebbda807cba456e268e191ec28fafdde26bb4` checks signer identity
before publication and actual OpenSSL executable and linked-library identities
before and after verification in both staging routes. All nineteen focused
chain cases pass, including signer/verifier drift controls that require refusal
without staged writes. This route supplies no new boot-chain execution or timing
verdict. Actual manifest refresh remains conditional on a passing compiler
kernel-bound build receipt.

## Complete qualification and source matching

Each independent qualification runs a complete `coqchk -o` over all 215 roots
independently derived from that tree's Make `FILES` and `COQINCLUDES`, preserving
recursive dependency scope. Before any metadata query or audit, the seal binds
the original receipt, stage logs, archives, source and generated object populations,
the copied population, lock, actual `coqc`, `coqtop`, `coqchk`, OCaml and Menhir
executables, producer, matcher and installed prover-library source/object inputs.
The copied population must match its authenticated compilation baseline. A
snapshot taken after an operation cannot replace its missing initial snapshot.

Each actual prover executable must report the locked release; another release
or an unknown format refuses acceptance. Each individual query's outputs are
captured and every sealed input checked immediately afterward and before the
next query. Later queries may not alter earlier outputs. The kernel run and
classification also require unchanged inputs. Only explicitly recorded new
query and audit outputs are allowed.

The matcher classifies every loaded axiom by its exact qualified declared source
name and retains the complete admission census, including module refinements,
apostrophes, `Module Import`, Program obligations and anonymous admitted goals.
Generated names require actual compiler-emitted metadata and exact source
locations. Missing, ambiguous or inconsistent metadata, unsafe summary entries,
unmatched names or input drift refuse qualification. Compilation stages and a
fresh kernel stage retain their distinct producer identities and actual commands,
logs, exits and timings; a corrected helper cannot relabel an old receipt.

The standard-mode infrastructure is
`ec5b8250bb9b895a3162375e8ac80cda2ccdcbee`, with thirty-one passing focused
controls. Its tool-state probe binds 10,248 installed-library files and reports
Rocq 9.3.0 for the compiler, query tool and checker. The
[query-binding census](evidence/q39-20261010-query-binding-census.json) retains
candidate outcomes, the exact source comparison and tool identities. These
infrastructure controls supply no compiler kernel or target verdict.

The standard-mode and VM-mode candidates preserve the same 1,430 non-helper
compiler/proof files and complete qualification scope. A successful pair must
come from two genuine complete original producers: do not mix revisions or modes,
pass an old seal through a newer helper, or relabel standard-mode execution as
VM-mode. Q39's compiler campaigns, argument replay, HELLO reproduction/refusals
and manifest restaging must use the actually accepted rebuilt digest. Both
independent qualifications and the hosted handoff remain required.

## Public compiler-report bindings

Both compiler-diff report routes check compiler identity before their campaign
and again before successful JSON or component publication. They reread native
provenance so source drift or an invalid partial receipt refuses publication.
An ordinary executable with both receipts absent is supported only while its
executable identity and receipt absence remain unchanged. This detects persistent
drift in the trusted exclusive lane; it claims no race-free executable pinning.
HELLO's description and wrong-compiler diagnostic name Q39's locked rebuilt
compiler.

The reviewed repair at VerifiedOS
`7e72e607a8ec3f1bca84d8de202b3c79837e58ff` passes twenty-one compiler-diff cases
and four HELLO cases, including actual child-written drift refusals and unchanged
present/absent-receipt positives across both routes. Focused Ruff and strict
Linux/Windows Ty checks pass. These controls supply no compiler kernel or
actual target-replay verdict.

## Locked checker VM configuration

The selected VM infrastructure is
`6409d0ed65fd07de4fb37aa9c8f7a9d5c317cc9d`, with forty-six passing focused
controls. Its explicit `-bytecode-compiler yes` selection is bound in the seal,
actual complete checker command, qualification and final build receipts. Missing,
old, duplicated, extra or mismatched settings, changed commands and globally
unsupported/disabled/ignored-option diagnostics refuse qualification, including
at exit 0. All standard-mode input, query and classification guards remain.
The project proof switch and its gates retain their existing settings.

The exact Rocq V9.3.0
[checker entry](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/coqchk_main.ml),
[safe checking](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/safe_checking.ml)
and [safe typing](https://github.com/rocq-prover/rocq/blob/V9.3.0/kernel/safe_typing.ml)
match installed package archive SHA-256
`3f0fc283e8644394aa9c7a6e3995b6d9ebbe1e6dda712bf431f9c372dcef95ad`.
The option rebuilds bytecode from checked declarations rather than trusting
serialized `vmlibrary` bytes, and retains module checking. VM compiler/runtime
correctness contributes to conversion trust; the option changes no proof
statement, guard, universe check, admission or dependency scope.

The positive library and lawful VM-cast equality pass; the mismatched serialized
bytecode fixture is rejected at `Evil.evil_false` with exit 129. The control
receipt digests are respectively
`f8cf1596076d5870513023e37c379b3ba051d8dfddf4bc5454d305ae47613e05`
and `4d5c964e3ddc5690161ab65afd58a07b7ce6de2a0c32781452346610035339b1`.
These finite controls supply no whole-compiler verdict or measured speedup.

`Typeops.check_cast` sends explicit VM casts to `Vconv.vm_conv`; default casts,
ordinary final type checks and module-subtype comparisons use closure conversion.
`Vconv.vm_conv_gen` can warn and use ordinary conversion for an individual
bytecode compilation exception. The profile records the selected option, not a
claim that every comparison executes in the VM. The source manifest digest is
`477f1f7c498607acd2d171c56ac6625444d694a3695964464a12e714b2efb849`.

<a id="investigate-future-audit-reuse-without-interrupting-current-runs"></a>
## Audit reuse boundary

The private `test/verifiedos-q39/qualify.py` can validate and reuse authenticated
completed compilation in a distinct qualification tree, then enumerate/query
again and launch a complete checker. It does not resume an interrupted checker.
The exact [Rocq 9.3 checker entry](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/coqchk_main.ml)
has no save/resume option; its
[library checker](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/checkLibrary.ml)
keeps the checked environment in memory. The
[release manual](https://rocq-prover.org/doc/V9.3.0/refman/practical-tools/coq-commands.html#compiled-libraries-checker-rocqchk)
states that checking does not mark proof objects as checked. A progress-log prefix
is neither a complete verdict nor a persisted validation certificate.

Q43's [reuse contract](contracts/contained-compiler-reuse.md) owns validated
compilation/whole-set reuse and cold operation. The contained compiler needs its
own validator because its declared axioms and admission census differ from the
project proof gate. Pending or interrupted audits cannot seed complete reuse,
and Q39 still requires its two independent complete qualifications. Portable
receipts alone authorize no reuse.

Separately completed dependency checks would require unchanged-byte evidence for
every skipped dependency, complete source-name classification and admission
census, and joint universe/dependency consistency. Unconditional `-admit` or
`-norec` is not equivalent full checking. No resumable checker, dependency-frontier
sharding, speed factor or automatic proof repair is accepted by this record.
Connected-component parallelism cannot split one expensive constant; profiling
and any prover/compiler change require their own bounded scope.

<a id="shelve-the-incomplete-audits-after-checkpoint-and-release-triage"></a>
## Interrupted-audit state

The [terminal bundle](retained-evidence/q39/interrupted-audits-20261012/README.md)
records identity-bound SIGTERM of all four original standard/VM checkers. All
four original producers finish at exit 1 with genuine fresh-kernel return code
`-15`. Completed builds, archives, objects, original helpers, locked switches and
bound source worktrees remain at their native paths. Their in-memory checker
environments are lost. The original seven-stage receipts remain `passed: false`
and `kernel: null`; separate qualification receipts record the interruptions.
No complete kernel, classification, final stability or resumable checkpoint is
accepted. Q39 and Q43 remain open, including firmware provenance blockers.

The [bounded source and activity triage](retained-evidence/q39/shelving-triage-20261012/README.md)
identifies kernel closure reduction/conversion under `check_structure_field`.
That establishes activity, not forward progress, a termination bound or an
infinite loop. A last `checking cst:` line is printed before checking its type
and body; module/subtyping work may continue without another line. A single
register sample cannot identify the current call stack or remaining work.

The frozen [CompCert 3.18 comparison](https://github.com/AbsInt/CompCert/compare/7b1f02b09954b9b916eb2a91d283c9b5355bf172...14d616046360a0b2611ebdfc2f98368af402e1f7)
leaves the parser grammar, validator-completeness source and Menhir generation
file unchanged. The contained immutable `VERSION` records 3.17; the comparison
does not establish equality with its customized sources. The bounded development
review identifies no matching fix. No release upgrade, port or proof repair is
selected. Native compilation bytes and sealed dependencies must remain at their
bound paths; public metadata is not their backup.

A resumed effort requires a bounded diagnosis and a new complete qualified pair
under the unchanged acceptance predicate before classification, final stability,
target replay and restaging. A changed prover or compiler requires separately
qualified source/toolchain identities. Publication and hosted validation retain
the repository handoff requirements; pending or interrupted checks supply no
passing evidence.

## Relocated input readiness

The read-only 2026-11-09 inventory matches the retained VM candidates' catalog-bound
files, listed population and installed-library seal entries, tool identities, and
the explicitly mapped helper and lock bytes. The restored private worktree retains
the catalog's revision and is clean. The local `plan-next-20261109` handoff retains
the inventory and its native report identity; no private source is exported.

The historical absolute host helper and lock paths are absent. Matching their
relocated bytes does not satisfy the existing path-bound reuse validator or change
any historical receipt. An authenticated relocation connection remains required
before reuse; a complete kernel audit, its diagnosis and target qualification
remain open. This inventory runs no compiler, query or checker.

Read-only inspection of the sealed locked profiler and checker sources identifies
no supported unfinished-event capture route. The handoff retains those source
identities and the observation's limits; no new diagnostic or root-cause verdict
is supplied.

### Explicit relocated-path verification

The `compiler-relocation` host command verifies the remaining helper/lock path
connection without invoking the private reuse validator. Its trusted input is an
explicit SHA-256 for the retained candidate catalog, supplied independently of
the relocation mapping. The catalog selects one named candidate and authenticates
its exact pre-query compilation seal, including the original native root. Neither
the mapping nor a newly edited seal can replace that digest binding.

The closed mapping has `schema: "verifiedos-contained-compiler-relocation/1"`,
`candidate`, and `files`, an object mapping each historical absolute helper/lock
path to its explicit restored absolute path. Coverage must equal every helper
and the lock named by that seal; missing or additional paths refuse. Every mapped
file must match its seal-owned SHA-256. Unsupported seal/catalog shapes,
substituted candidates, corrupt seals, malformed/duplicate JSON keys, linked or
escaping restored paths, and any input drift before return refuse the whole
operation. There is no prefix replacement, inferred fallback or receipt rewrite.

A successful report binds catalog, seal, mapping, verifier and every mapped file
identity. It states only that these exact historical helper/lock bytes are
available at those explicit restored locations. It performs no population or
library rescan, compilation, query, checker, qualification, copying or cache
publication. This standalone report supplies no compilation reuse, complete
kernel qualification, target acceptance or checker resume. The separately
reviewed status connection below supplies the bounded compilation-only check.

Acceptance requires independent fixture controls for exact coverage, positive
mapping, catalog/seal/candidate and mapped-byte substitutions, malformed inputs
and final recheck drift, followed by a read-only run against the real retained
VM seal and restored helper/lock files. Preserve historical receipts and useful
prior output on refusal; retain only metadata mapping/report outputs in the
assigned lane. The integrator records focused local checks and leaves hosted
acceptance to the user.


### Read-only relocated-compilation status

The [bounded status connection](contracts/contained-compiler-reuse.md#bounded-relocated-compilation-status-connection)
is implemented in public revision `bd420567e2abc7b4023df775e219ddb0958a47d1`
and private helper revision `37c154a7a51123008aa940150cefaf8674e55662`.
The private validator parses exactly the catalog/seal/mapping bytes whose
identities it binds, independently repeats mapping validation, preserves all
existing compilation/source/tool/library checks and rechecks the connection
before return. It admits only explicit read-only compilation-tier status;
execution, priming, cold bypass, profile requests and implicit index lookup refuse.

The final native run revalidates the real retained `vm-clean-rebuild-1` candidate
using exactly the committed four-helper driver deployed in its assigned guest
lane. It reports compilation `reused` and `inputs_stable: true`; queries, kernel
and classification remain `not_run`. The original receipt remains SHA-256
`fdd3e16a7268cf07338ce44df6d0c91a8838e2ad7a496ad459be266b0f79577b`,
and the original raw seal remains
`efccc80f0186b5686753cf9e9620ea66f8a5ca978fad6cd8d9b7143321564828`.
Both are unchanged after the run. The local handoff retains the exact connection,
mapping, deployment/driver identities, command inputs and final status metadata;
no contained compiler source, object, executable or installed library is exported.
The native deployment contains only the four reviewed helper scripts.

Focused public connection and controller controls, private positive/refusal
controls including transient mapping substitution/restoration, original-path
regressions and public typing/import checks pass. These checks establish this
finite status boundary, without a complete compiler qualification or target
verdict. No compilation, proof query, kernel audit, staging or cache publication
runs. Q39 and Q43 retain their actual complete-qualification/default-reuse joins.

The supported entry is an isolated public checkout. The controller's
[native-path validation](../../tools/vos/compiler_build.py#Settings.validate)
requires the compiler source, helper, opam and native output roots to be outside
that invoking checkout. The explicitly selected restored private Git source is
outside a dedicated public lane, and the successful status above uses that route.
Direct invocation from the primary checkout refuses that same source because it
resides below the primary's `out/migration-retained/` directory. Direct primary
invocation is not a qualification prerequisite: subsequent work uses its assigned
public lane and integrates its public changes into local `main` through the
ordinary fan-out handoff. No source move, copy, path alias or containment
relaxation is needed for this route.

The [continuation handoff](contracts/contained-compiler-reuse.md#continuation-from-an-isolated-public-lane)
separates that satisfied placement condition from Q39's unresolved diagnostic and
qualification inputs. Historical status arguments refer to a retired lane and
are provenance, not a current launch command. A new invocation binds its own
absolute paths and revalidates every retained input; neither the supported lane
route nor a compilation-tier status closes Q39 or Q43.

## Bounded Parser diagnostic

The [Parser diagnostic manifest](retained-evidence/q39/bounded-parser-profile-20261013/manifest.json),
SHA256 `813cb9697c5284b13ff8686e99d03441de54baae658db32b4919901470a31d8e`,
binds the isolated profiling attempt and verifier. The checker is interrupted
with SIGINT and exits at -2 after 85.034 seconds; all 14,490 sealed input identities
match before and after. The last printed declaration is
`Complete.Valid.is_validator_forall_items`. Buffered, truncated profiling output
identifies no active unfinished event, cause, forward progress or nontermination.
This diagnostic supplies no kernel acceptance and justifies no unbounded restart.
