# Contained compiler port decisions

Q39 owns the contained compiler's locked switch, compatibility port and acceptance
predicate in the [implementation checklist](implementation-checklist.md). This
record commissions a bounded follow-up under that predicate; it changes no proof
statement, executable definition, hypothesis, admitted lemma or compiler flag.

## Candidate selection

The upstream pairing, Rocq 9.1.0 with OCaml 4.14.2 and Menhir 20260209,
completed the compiler build. Its complete all-`FILES` kernel audit failed
with exit 129 in the generated parser's
`MenhirLibParser.Inter.ValidSafe.safe_is_validator` with
`Modops.ModuleTypingError`; a parser-only diagnostic reproduced the failure.
The failure is retained and the pairing supplies no passing kernel acceptance.

The next candidate is the bounded Rocq 9.3.0 port with the same OCaml and
Menhir releases. Its portable lock contains released packages only. The
independent lock-import clean build and the complete whole-environment audit
must pass before this candidate is accepted. The proof switch's lock stays
unchanged, and the standing kernel findings F-565 and F-525 remain standing.

## Follow-up after the initial repair budget

The initial twelve-candidate repair budget stopped after candidate 12. That check
exited 2 after 57.94 seconds. Its existing-lemma strategy closed
`regset_rel_return_from_builtin`; the next failure was the unchanged register
exclusion assertion in `nextinstr_pc_return_builtin_value` at
`security/Recomposition.v:5901`. The diagnostic is retained at
`/root/build/lane-checklist-20261010-c/q39/port-candidate-12.log`.

The stopped source is based on contained revision
`d08768db051ebb5cbe92ea24eeacbd63b9eaf84a`, with the bounded working patch.
`security/Recomposition.v` has SHA-256
`2cc945af9cd3801d31c19e0fc577ecb8f7e5c981fd01c6c92927f27299c2c680`.

The integrator commissions at most two further candidates or eight active repair
minutes, whichever comes first, applying the demonstrated `preg_notin_charact`
and `preg_of_not_PC` strategy to that second assertion. Active time includes
candidate editing and check waits. The earlier census remains part of the record;
this is a scoped follow-up within Q39's existing port allowance. A new unrelated
failure ends this follow-up and returns to the integrator before any further edit.

The decision is justified by the successful preceding proof and the identical
exclusion pattern at the new failure. It uses existing lemmas and preserves the
frozen declaration. No new assumption, admission, global hint or relaxed compiler
flag is authorized. Exact elaborated types and transparent bodies must still
compare with the frozen baseline under the same prover identity. A comparison
difference ends the repair and returns to the requirement owner.

The final acceptance remains Q39's clean lock-import build, complete environment
kernel reading and axiom classification, output comparisons, target replay,
manifest identities and hosted handoff. A successful candidate check supplies no
substitute for those checks.

## Follow-up for the remaining repeated assertions

The first follow-up used one candidate, candidate 13, and stopped at its new
failure. The check exited 2 after 82.76 seconds. It closed the second standalone
exclusion lemma and reached the same assertion pattern in `step_E0_strong` at
`security/Recomposition.v:8869`.

The integrator read the remaining six `H'` assertion bodies at lines 8863, 8884,
8905, 8988, 9009 and 9115 of that stopped source, whose SHA-256 is
`02fba81e5ab76720b83384acf88dbc15125f8a267789002559d5beb5739cb889`.
Each asserts `preg_notin PC (destroyed_by_builtin ef)` or its `ef0` variant and
uses the same failing expansion. The other `destruct orb` sites at lines 5818
and 5828 belong to already compiled lemmas and are outside this repair.

A further scope permits at most two candidates or eight active repair minutes,
whichever comes first, replacing only those six assertion bodies with the
existing general-characterization/not-PC strategy now demonstrated twice.
Preserve the original net transparency-setting effects as well as the frozen
declarations, definitions, hypotheses, admissions and compiler flags. The reason
for batching these sites is their matching propositions and proof pattern; the
integrator has read the sites rather than assuming every Boolean case is the same.

Retain both earlier censuses and the complete diff. A new unrelated failure ends
this scope before another edit. Exact frozen comparison and all Q39 acceptance
checks remain required.

## Repair and frozen-reading verdict

Candidate 14, the first candidate in the six-site scope, completed `make -k -j2
proof` with exit 0 after 95.11 seconds. The thirteen compatibility-port files
are committed at contained revision `7093854d8ce8799826618024ee4847cf248766ea`.

The exact frozen comparison passed for 1,606 declarations across those thirteen
modules, 197 generic parser declarations with 105 transparent or inductive bodies,
and the three changed transparent bodies instantiated with `Parser.Aut`. The
generic query instantiates the interpreter with an arbitrary
`A : MenhirLib.Automaton.T`; it preserves the generic reading rather than
substituting only the compiler's actual automaton. Both readings use the same
Rocq 9.1 prover identity and printing settings, with zero exact differences.

The printed baseline was reconstructed after repair from the immutable pre-edit
`d08768db051ebb5cbe92ea24eeacbd63b9eaf84a` source and compiled-object checkpoint.
No pre-edit sealed print is claimed. The candidate's reader-only source uses the
old spelling `Zmod_0_r` in two proof-script occurrences where the Rocq 9.3 build
uses `Z.mod_0_r`; its exact private diff and digest are recorded. No statement or
definition changes for that reader.

The first generic-print probe failed with a Rocq 9.1 printer anomaly. Two
read-only query configurations, bounded to five active diagnostic minutes,
were authorized to recover the complete reading without changing source,
packages or the frozen comparison. The second configuration succeeded in
2.99 seconds. The failed probe remains retained; no omitted generic declaration
or body is accepted. The native comparison receipt is
`/root/build/lane-checklist-20261010-c/q39/frozen-readings/frozen-comparison.json`,
SHA-256 `baab4b5975b5e3caa86ba62b7ff480d84a5066c999a6e6e2713d7390b9c9c928`.
This verdict does not supply the separate clean builds, kernel audit or target
acceptance.

## Focused simulator dependency for compiler replay

The integrator commissions an explicit focused simulator-build receipt for
Q39's HELLO and large-argument replay. S6's integrated model changes make older
model receipts stale. The existing HELLO reader checks source and simulator
digests but accepts a shape that does not establish which build stages ran.
The full model suite belongs on GitHub Actions, so fabricating a complete
`configure`/`build`/`ctest` receipt is not an available solution.

The focused producer must configure the current verifiedos profile and build
only the explicit `sail_riscv_sim` CMake target with its normal dependencies.
Its distinct schema and profile name must identify successful configure and
target-build stages, the exact commands, the model-file population and digests,
the profile configuration digest, simulator digest, and the actual Sail, CMake
and C++ tool identities. It must compare inputs and tools before and after the
build in the exclusive native lane and refuse a changed input or failed stage.
No `ctest` success or full model acceptance is represented.

The HELLO reader must distinguish this focused receipt from a complete model
receipt, reject missing or malformed identities and unsuccessful stages, and
bind the supplied simulator and current model bytes. A complete receipt retains
its existing complete-stage meaning. Add focused positive and refusal controls
for the new route. HELLO's real execution and all three controls, and the typed
large-argument replay, remain required. General target readers keep their
complete-build contracts; this narrow dependency route changes no production
gate or Q39 output predicate.

The integrator and independent reviewer found two gaps in the first focused
reader: command options were present without joining their source/build paths,
and the measured default C++ binary could differ from CMake's inherited `CXX`
selection. The repair at VerifiedOS revision
`603bcd302fb194ae19886240134636b13ad16f49` binds unique configure/build arguments
to the recorded original absolute roots and the retained CMake cache, and binds
CMake's selected Sail and C++ executables to the measured identities. It also
hashes the generated schema and profile-validation log. Original roots remain
historical identities after worktree retirement; the consumer checks current
model bytes without requiring the retired checkout to exist.

Both reviewers read the repair and found those gaps closed. Focused controls
refuse inconsistent command roots, selected C++ identity, schema and native
cache/schema drift. A fresh producer run is required under the repaired reader;
the first build's receipt is retained as historical evidence and is not relabeled
as satisfying the repaired contract. This is why final target evidence waits for
the fresh dependency verdict.

The fresh focused build passed configure in 42.83 seconds and the explicit
simulator target in 284.12 seconds. Its native receipt is
`/root/build/lane-checklist-20261010-c/q39/simulator-dependency-2/simulator-build.json`,
SHA-256 `4b6e41da6f446e6e312397cc7fdb2b6c398c4ec6bceb2740533ca002f9139b0c`.
Tests remain explicitly unrun and full model acceptance remains pending. Compiler
replay still requires the compiler's separate passing kernel-bound build receipt.

## Preserve signed images while refreshing compiler bindings

Q39 already owns re-staging the current target manifests after output comparison.
The chain's ordinary staging command generates disposable signing keys and new
images, which would change otherwise unchanged acceptance inputs. The integrator
therefore commissions a narrow `chain-stage --preserve-images` route under that
existing re-staging predicate.

The route must recompile every chain unit through the rebuilt compiler and refuse
any stream difference before writing. It must retain every existing image, key
and header byte, re-derive the current payload layouts, and recheck the existing
signatures with OpenSSL. Only successful joins may refresh current source,
include, compiler and freeze identities. A missing or invalid retained artifact,
signature or layout refuses the refresh; neither a copied manifest nor unchanged
image bytes alone establish it. Add a positive refresh and refusal controls,
including changed compiled output, while retaining ordinary staging behavior.

This decision preserves the signed-image inputs whose target behavior was already
measured while binding them to the actually rebuilt producer. Dated receipts stay
unchanged; this route supplies no new boot-chain execution or timing verdict.

The independent review found that the first implementation moved the ordinary
route's final signer identity checks ahead of signature verification. That could
miss OpenSSL changes during verification. The repair at VerifiedOS revision
`528ebbda807cba456e268e191ec28fafdde26bb4` restores signer checks before publication
and checks the actual OpenSSL executable and linked-library identities before
and after verification for both routes. Focused controls change the signer or
verifier identity during verification and require refusal without staged writes;
all nineteen focused chain cases passed. The actual manifest refresh remains
conditional on the compiler's passing kernel-bound build receipt.

## Correct exact source matching without replacing build evidence

A read-only preflight of the whole-environment matcher failed on six of the
215 actual Make `FILES` roots before the running kernel audits completed.
`UnionFind`, `Kildall` and `Allocation` contain module refinements or apostrophes
the lexical scanner misreads; generated `Parser` uses `Module Import Gram`;
`Backtranslation` has a Program definition with admitted obligations; and
`CapAsmgen` has anonymous admitted goals. A partial admission count supplies
no complete census or acceptance. The native preflight is retained at
`/root/build/lane-checklist-20261010-c/q39/lexical-preflight.json`.

The integrator commissions a separate infrastructure repair of at most three
matcher candidates or fifteen active repair minutes, whichever comes first.
Editing and candidate-check waits count; the existing fourteen proof candidates
and their budgets stay recorded. The worker resumes its dedicated contained
source worktree at `7093854d8ce8799826618024ee4847cf248766ea`, owning only the
matcher, its focused controls and a qualification producer. No proof, executable
compiler source, statement, definition, assumption, admission, package or flag
may change. A new unsupported declaration form returns to the integrator.

Each loaded axiom must still match its exact qualified declared source name,
and every admission must enter the census. Generated obligation and anonymous
goal names require actual compiler-emitted declaration metadata and exact source
locations, rather than guessed numbering or omitted declarations. Focused
controls must cover the six encountered forms and refusal of missing, ambiguous
or inconsistent metadata. The complete 215-root preflight and the eventual exact
kernel-summary match remain separate required checks.

The running drivers already imported the defective matcher. Their original
receipts and logs remain immutable, including any later matching failure after a
kernel exit of zero. A file edit, injected live-process change or relabeled receipt
cannot qualify those builds. The corrected producer may create a distinct native
qualification tree from an untouched original build, explicitly recording reuse
and the original matching failure. It must bind the original receipt and archive,
all real successful configure/clean/depend/proof/extraction/compiler/kernel
stages, actual binary, source and object population, recorded lock and tool roles,
and the complete kernel log to the corrected matcher and its exact classification.
Every source, object, log, receipt and tool input is checked before and after the
join in the exclusive lane. Only the known matcher failure may be recovered;
another failed stage, absent kernel verdict, changed input, unsafe summary entry
or unmatched name refuses qualification.

The new tree retains the source and native inputs required by the existing strict
compiler provenance reader. Its new successful receipt describes this explicit
post-build qualification and references the unchanged original failure; it makes
no claim of a new compilation or kernel run. Add positive and refusal controls
for this join, including failed kernel, failed compilation, changed object/log,
wrong lock/tool and incomplete classification. Both independent clean builds
still require this actual acceptance before target replay or manifest refresh.

## Bind a fresh kernel audit to its complete inputs

The independent review of contained infrastructure revision
`8a77ca71cd539375ef3cefa18110c0041c02b66e` found three acceptance gaps. The
original build driver records proof-object existence without their pre-audit
digests. The qualification producer snapshots its copy only after metadata
queries, allowing a query-time object change to become its baseline. It measures
`coqc` but executes an unmeasured `coqtop`, and measures its own producer and
matcher only after classification. The first matcher scope stopped after three
candidates; its complete 215-root, sixty-admission census remains useful feedback,
but that producer supplies no accepted qualification.

The integrator commissions at most three infrastructure candidates or twenty
active repair minutes, whichever comes first, for those input bindings. Editing
and focused-control waits count. Full kernel-audit execution is a separate
required acceptance step, not a repair candidate. The worker owns only
`test/verifiedos-q39/audit.py`, `qualify.py`, `test_audit.py` and, if needed, the
native build driver. Proof sources, executable compiler sources, packages, flags
and the fourteen proof candidates remain unchanged. A new unrelated failure
returns to the integrator before another edit.

The existing kernel runs cannot retrospectively acquire pre-audit object hashes.
Preserve their real logs and verdicts unchanged. If no suitable pre-audit input
snapshot exists, the integrator may end only these session-owned kernel child
processes, allowing their drivers to record the resulting unsuccessful stages.
Their successful export, configure, clean, dependency, proof, extraction and
compiler stages may be reused in distinct qualification trees. An interrupted
audit is not a successful kernel stage and no original receipt is relabeled.

Each independent qualification must instead run a fresh complete `coqchk -o`
over all 215 roots independently re-derived from that tree's Make `FILES` and
`COQINCLUDES`. Preserve the existing flags and recursive dependency scope. Before
launching any metadata query or audit, bind the original receipt, stage logs,
archive, source and generated object population, copied population, lock, actual
`coqc`, `coqtop`, `coqchk`, OCaml and Menhir executables, producer and matcher.
Include installed prover-library source and object inputs outside the build tree.
Compare the copy against its original baseline before queries; allow only
explicitly recorded new query and audit outputs. Recheck every input after queries,
the kernel run and classification, refusing any drift. A snapshot taken after
the operation cannot replace its missing initial snapshot.

The successful new receipt must distinguish reused compilation stages from its
fresh kernel stage, record the actual command, log, exit and timing, and bind
complete input populations and their unchanged verdict. The exact final kernel
summary must still classify every loaded axiom against its declared source name,
reject unsafe entries and unmatched names, and retain the complete admission
census. Both independent clean builds require this fresh acceptance; the existing
strict compiler consumer and all target acceptance predicates remain unchanged.

Add focused controls for object replacement before qualification, changes in the
copy during metadata queries, changes to installed library inputs, `coqtop`,
`coqchk`, producer or matcher, and mismatched Make enumeration. Keep original
failed receipts immutable and refuse publication after any failed or changed
input. The reason for rerunning the full audit is the missing original object
binding, rather than a change to the proof or its acceptance scope.
