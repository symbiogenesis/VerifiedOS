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
Reuse requires an authenticated object population produced by those compilation
stages. When that population cannot be authenticated, repeat both independent
clean builds under the repaired driver, recording objects after compilation and
before any query or kernel audit. A fresh audit alone cannot establish an object's
origin in an earlier compilation. The inspected original driver has no such
object population, so these two builds require the clean-rebuild fallback.

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

## Finish query-tool and individual-query bindings

The independent review of contained infrastructure revision
`74ce7b36064f0a13d89f362fd89c6da8f065e73f` confirms the fresh compilation seal,
pre-query copy comparison, installed-library population and measured query/checker
executables. Its three-candidate scope stopped with twenty-one focused controls
and both 215-root production preflights passing. No fresh acceptance build has
started. All 1,430 tracked non-helper files remain byte-identical to the frozen
proof-port source at `7093854d8ce8799826618024ee4847cf248766ea`.

Two gaps still prevent acceptance. `coqtop` and `coqchk` are measured but their
reported releases are not required to match the locked prover. Discovery and
location queries run consecutively before their input/output guard, allowing a
later query to change discovery evidence before its first recorded snapshot.

The integrator commissions at most two infrastructure candidates or eight active
repair minutes, whichever comes first, to close exactly these gaps in the same
owned helpers and focused controls. Preserve all prior candidate censuses and
budgets. Require each actual prover executable, including `coqtop` and `coqchk`,
to report the locked prover release before it can supply a query or verdict.
Unknown version formats and another release refuse acceptance. Capture each
individual query's outputs and recheck every sealed input immediately afterward
and before the next query. Later queries must not alter any earlier output.
Controls must refuse a stable checker or query tool from another release and
location-query changes to discovery source or log bytes. No proof, compiler,
package or flag change is authorized.

Independent review precedes the fresh clean builds. The second build uses the
already independently imported `q39-replay` switch, with its recorded lock import
and unchanged closure verified again. The original interrupted build in that
switch remains recorded. Q39 requires the independent lock-import switch and a
clean compiler build; it does not require reinstalling the unchanged switch for
each infrastructure retry. The final receipt must state this switch history.

The two-candidate query-binding scope stopped at a control-fixture failure: its
empty-report subtest leaves the fake `coqtop` report empty when the subsequent
`coqchk` subtest begins, so the earlier refusal masks the expected checker
refusal. The production query-release and input/output controls pass. One
fixture-only candidate, bounded to three active minutes, may restore the original
fake report in `finally`, normalize only the two owned Python helpers to LF, and
rerun the same thirty-one focused controls. No production logic or other source
change is authorized. Preserve both preceding candidate outcomes and obtain
independent review of the immutable result before acceptance builds start.

The fixture-only candidate passed all thirty-one focused controls in 3.209 s.
The actual final tool-state probe passed in 5.4693 s over 10,248 installed-library
files, with the compiler, query tool and checker each reporting Rocq 9.3.0.
The final infrastructure revision is
`ec5b8250bb9b895a3162375e8ac80cda2ccdcbee`; both reviewers read the release and
individual-query guards and found the identified gaps closed. This qualifies
the infrastructure for the two fresh acceptance builds, without supplying a
compiler-build, kernel or target-replay verdict. The
[query-binding census](evidence/q39-20261010-query-binding-census.json) retains
the failed candidates, fixture correction, exact source comparison and tool
probe identities. Q39 remains open until its separate acceptance predicates pass.

## Finish public compiler-report bindings

The independent review of VerifiedOS revision
`69760b670f6f49cebee75ea95c05b47a7037d66e` found that compiler-diff's program
and native component routes capture the producer identity before their campaign
but do not recheck it before publishing. Persistent executable, source receipt,
input receipt or lock drift can leave a successful report carrying the earlier
identity. The same review found HELLO's docstring and wrong-compiler diagnostic
still naming the old accepted compiler, contrary to Q39's explicit predicate.

The worker owns a narrow public-tool repair in its dedicated VerifiedOS lane.
Both compiler-diff routes must refuse changed compiler identities before any
successful report or component output is published, rereading the native
provenance so source drift or an invalid partial receipt refuses too. An ordinary
executable with both receipts absent remains an explicit supported case; its
executable identity and continued receipt absence must still hold. Add focused
positive and executable, receipt, source and lock drift controls for both routes.
This before-and-after check detects persistent drift in the trusted exclusive
lane; it makes no race-free executable-pinning claim. Restate HELLO's docstring
and refusal diagnostic to name Q39's locked rebuilt compiler, with a focused
wrong-compiler check.

Private helpers, compiler sources, packages, proof statements, audit flags and
the running sealed kernel audits remain unchanged. This repair lies within Q39's
existing report-identity and diagnostic ownership. Its focused checks and
independent review precede the final actual compiler campaign and HELLO replay.

The repair at VerifiedOS revision
`7e72e607a8ec3f1bca84d8de202b3c79837e58ff` passed twenty-one focused
compiler-diff cases and four HELLO cases, including fourteen actual child-written
drift refusals and four unchanged present/absent-receipt positives across the two
report routes. The refusal controls require no successful JSON or component
record to be published. Focused Ruff and strict Linux/Windows Ty passed; the only
additional HELLO edit is an annotation-only cast after its existing successful
shape and model-population guards. The integrator and independent reviewer read
the immutable repair and found both reported gaps closed, with no further material
regression. These tool-control verdicts supply no compiler kernel or target-replay
verdict. Both fresh sealed compiler audits remain pending.

## Interpret pending checker observations

A bounded read-only review of the frozen compiler revision and
[Rocq 9.3.0's checker](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/mod_checking.ml#L56)
clarifies the repeated final log line. `checking cst:` is emitted before the
declaration's type and proof body are checked; module-expression and subtyping
work can also proceed without another log message. The last emitted name is
therefore not a conclusive current stack location. The named Menhir lemma is
instantiated for the generated parser automaton, rather than a runtime parsing
operation. Static reading supplies neither a nontermination diagnosis nor a
completion estimate.

The integrator independently read the same frozen Menhir sources and the official
checker source, retaining its SHA-256
`d1f8d33290ee837ec30d2a75bbc9f752016f4cb3ddf0bc24847b09df6d52548b`.
No prover execution, source change or audit adjustment followed this diagnostic.
Only the actual complete kernel verdicts can satisfy the pending acceptance
predicate.

## Bound native register inspection

Both fresh kernel auditors remain active without a verdict, and a native debugger
is unavailable. The integrator commissions one diagnostic probe candidate, bounded
to ten active implementation minutes, outside every repository and worktree.
It may use the existing native C compiler to build a Linux register reader, first
tested against an explicitly owned disposable process. It must verify the target
identity, briefly attach, read registers and detach on every path; it may write no
inferior memory, insert no breakpoint and call no inferior function. A bounded
timeout and a post-detach running-state check are required. Remove temporary probe
source after its use and retain the source/binary digests and observations.

The integrator reviews the source and disposable-process result before the compiler
worker may take one observation from one reverified session-owned auditor. The
observation is limited to registers, executable mappings and static symbol lookup.
It supplies no kernel verdict, nontermination diagnosis or completion estimate.
Proof sources, helper sources, packages, audit flags and root scope remain frozen;
both complete audits continue afterward. A missing tool or failed probe closes this
diagnostic without installing anything or changing acceptance.

The first diagnostic candidate stopped at a malformed PowerShell here-string
terminator, before creating source or a binary. Native preflight confirmed
`aarch64` and the existing GCC 15.2.0, but no disposable-process test or auditor
attachment occurred. The recorded interval was 19:56:21–20:00:31 UTC on
2026-10-11. Its empty, uniquely owned Temp directory is retained. This closes
that candidate without a diagnostic or acceptance verdict; both sealed audits
continue unchanged.

## Replan the diagnostic launcher once

The first register-probe candidate failed before any native source existed because
its PowerShell launcher was malformed. That launcher failure supplies no evidence
about the proposed probe. One separate candidate, bounded to eight active
implementation minutes, may correct the launcher using absolute Temp paths and
explicit UTF-8 file APIs, then compile and test the register reader. Preserve the
first stopped outcome. A second failure closes this diagnostic without another
candidate or installation.

All register-inspection constraints above remain in force. The worker must return
the exact source and disposable-process evidence for independent review before
any auditor observation is authorized. A compiler worker may attach to no auditor
until the integrator gives a concrete instruction naming its reverified identity.
Proofs, compiler sources, packages, execution flags, root scope and both running
sealed audits remain unchanged.

The launcher replan passed in its single candidate within 20:11:25–20:15:21 UTC.
Its source digest is
`d41ec6d40792c625f19535dfd7f2fdb1b5f1281cdc23a0661cbc31858aa7a5a7`
and native binary digest is
`510b1c817f1551395a1cade991aeeea27dc91e14944279d05f18b595255f7c62`.
Normal and forced post-attach failure controls both detached successfully, verified
the disposable child running with `TracerPid=0`, and retired that owned child.
The timeout fallback and monotonic-clock failure handling were statically reviewed;
no fault-injection verdict is claimed. Both independent source readers found no
material issue within the trusted exclusive lane's stated process-identity bounds.

After rechecking the session-owned auditor's PID, start ticks, driver lineage,
UID, native architecture, executable digest against its compile seal and untraced
running state, the compiler worker made one authorized observation. It exited 0
in 0.015051400 s, detached, and verified the same target running and untraced;
the other auditor and both drivers retained their identities and running states.
This diagnostic briefly stopped and resumed one auditor, so its timing includes
that scheduling perturbation. Neither a kernel verdict nor a current call stack,
nontermination diagnosis or completion estimate follows from the register sample.
The observation's retained JSON digest is
`8083d04e6c0d518265621c304c4c67548438521f3a678b893f7281350bd60e0c`.

The compile source has been removed after digest and Temp ownership checks; the
binary, six logs and recorded source digest remain. Static symbol lookup places
the single sampled instruction in a list-append routine. That point observation
does not identify its callers or bound the remaining work.

## Validate the locked checker's VM option

The integrator and independent reviewer read the exact Rocq V9.3.0
[checker entry](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/coqchk_main.ml),
[safe-checking](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/safe_checking.ml)
and [safe-typing](https://github.com/rocq-prover/rocq/blob/V9.3.0/kernel/safe_typing.ml)
sources. The actual downloaded package archive,
SHA-256 `3f0fc283e8644394aa9c7a6e3995b6d9ebbe1e6dda712bf431f9c372dcef95ad`,
contains identical copies, and both installed switches' package metadata names
that archive. The default checker disables VM conversion. Its optional
`-bytecode-compiler yes` recompiles bytecode from the declarations about to be
checked, does not read serialized `vmlibrary` bytes, and retains module checking.
The VM compiler and runtime then contribute to conversion correctness. The
kernel's flag comparison identifies this setting as one that does not change the
theory; this static reading supplies no independent metatheory or timing verdict.
The source-comparison receipt digest is
`17adcb2facd9113edb4685854c99bfea1e583bd81bf109b5ed7ad5223775305f`.

Before choosing this setting for Q39, commission one Temp-only control candidate,
bounded to eight active implementation minutes. Use the existing locked checker
and compiler, with no package change, to check an honest positive library and the
upstream mismatched serialized-bytecode negative fixture. The latter must be
refused even with the VM enabled, establishing that the actual selected executable
does not accept that false proof through stored bytecode. Record every command,
exit, executable and fixture digest, and obtain independent review. A missing tool,
failed control or exhausted budget stops this configuration experiment. Neither
control supplies a compiler whole-environment verdict.

The two running auditors, their sources, flags, roots, seals and installed inputs
remain unchanged during this experiment. No compiler helper edit, full replacement
audit or termination is yet authorized. Any subsequent checker configuration act
needs its own landed scope, new pre-query seals and complete audits of both clean
builds; it may skip no root or recursive dependency, change no proof statement,
weaken no guard or universe check, and admit no module.

The control candidate passed in 20:29:13–20:32:06 UTC. The honest library's
VM-enabled checker exited 0. The mismatched fixture compiled and its false proof
reported no assumptions, but the same checker rejected `Evil.evil_false` at the
actual type conversion with exit 129. Its retained receipt digest is
`f8cf1596076d5870513023e37c379b3ba051d8dfddf4bc5454d305ae47613e05`.
Executable and fixture digests remained unchanged across the commands; no auditor
was accessed. This is a targeted rejection control, not a compiler verdict.

The honest positive defines a computed Boolean but has no explicit VM cast.
Before selecting the option, one supplemental positive fixture, bounded to three
active minutes, may compile a lawful VM-cast equality over that immutable honest
library and kernel-check it with the same actual VM-enabled checker. It must pass,
and any disabled-bytecode or ignored-option warning refuses the setting. Preserve
the first control's artifacts unchanged and record this supplement separately.
No helper, package, running audit or proof-source change is authorized by this
supplement. A failure closes the configuration experiment.

The supplemental lawful VM-cast equality passed compilation and its VM-enabled
kernel check in 20:35:41–20:37:22 UTC. The actual checker checked its honest
`Defs` dependency and `VMGood.vm_good`, reported success, and emitted no disabled
or ignored-mode warning. Its separate receipt digest is
`4d5c964e3ddc5690161ab65afd58a07b7ce6de2a0c32781452346610035339b1`.
The integrator and independent reviewer read both control scripts, fixtures,
commands and logs, verified their supplied digests and preserved prior-control
and tool identities, and found the positive/support gap closed. This supplies
finite implementation controls while retaining VM implementation trust; it
supplies no whole-compiler verdict or speed measurement.

## Select VM reduction for complete compiler audits

The integrator selects the locked checker's supported
`-bytecode-compiler yes` setting for the next two complete compiler audits.
The reason is to use the release's checked bytecode reconstruction and VM
conversion for the same proof obligations, after verifying its package sources,
lawful computational positive and stored-bytecode mismatch rejection. The running
default-mode audits provide no completed verdict or remaining-work estimate.
This act changes the conversion implementation and its recorded trust, rather
than any proof statement, guard, universe check, admission or dependency scope.
The project proof switch and its gates retain their existing settings.

Commission one infrastructure candidate, bounded to ten active implementation
minutes, in the separately provisioned private worker checkout based on
`ec5b8250bb9b895a3162375e8ac80cda2ccdcbee`. Own only
`test/verifiedos-q39/build.py`, `qualify.py` and `test_audit.py`; leave the matcher,
all proof and executable compiler sources, installed switches, lock, compilation
flags and old worker checkout unchanged. Require an explicit selected argument
and the exact canonical option pair in the raw receipt before sealing. A new seal
schema/profile must bind that selection, and a missing, old, mismatched, duplicated
or extra setting must refuse qualification rather than acquire a default.

The actual kernel command must contain the measured checker, existing `-o`, the
sealed exact option pair, every unchanged independently derived Make include flag,
and all 215 roots with their recursive dependencies. Require its complete returned
command to equal that expected command before a successful receipt is published.
Record the selection in the fresh kernel, qualification and final build receipts.
Refuse unsupported, disabled-bytecode or ignored-option diagnostics even at exit 0.
Keep every existing before/after input, object, installed-library, tool, helper,
query and classification guard and all unsafe-axiom refusals. Retain the thirty-one
existing focused controls and add positive selection joins and actual refusal
controls for old/missing/mismatched settings, altered commands and false-success
support diagnostics. Independent immutable review precedes acceptance builds.
A failure or exhausted budget stops this infrastructure candidate.

After that review, require two entirely new export, configure, clean, depend,
proof, extraction and compiler builds, one in each unchanged locked switch, with
new immediate post-compilation pre-query seals and distinct output and
qualification trees. Record the replay switch's earlier independent lock import
and unchanged closure honestly; do not reinstall it or relabel an old seal. All
non-helper source bytes must remain equal to the frozen compiler source. Both
fresh complete kernel verdicts, exact axiom classification and stable-input
verdicts must pass before strict consumer positives, final compiler campaigns,
argument replays, HELLO acceptance or target restaging. The existing default-mode
audits and original records remain unchanged until a separately authorized
session-owned retirement act; no verdict is inferred for them.

The infrastructure candidate `6409d0ed65fd07de4fb37aa9c8f7a9d5c317cc9d`
passed all forty-six focused controls, including the thirty-one retained controls.
Its subsequent source census stopped at native Git exit 128 because the integrator
had provisioned the new checkout with a Windows-only administrative link. This
was a worktree-launch failure, not a compiler or kernel verdict. The candidate
stopped within its implementation budget; no replacement build started.

The integrator repaired the new lane's links to the repository's required relative
form and verified clean, matching committed identities from Windows and WSL.
Git's repair also normalized two other administrative links; the integrator
restored their original Windows link strings and file attributes, then verified
their unchanged clean source revisions. The source census may now retry as a
read-only check of the immutable candidate. This administrative correction does
not authorize another helper candidate or change any running audit input.

The integrator and independent reviewer read the immutable three-file delta and
found no material issue. The reviewer completed the read-only review in
20:57:12–20:58:37 UTC without running checks or accessing auditors. The integrator
also read the forty-six-control log, whose digest is
`6fe79bc4641c9eb291084d82946db84d037f7ea20b7b3812171f81e7a0fbfac8`.
The actual locked release's disabled-bytecode warning is refused by the candidate.
The exact non-helper census and both fresh complete build/kernel verdicts remain
separate prerequisites; these reviews do not supply those verdicts.

The read-only census passed in 21:01:05–21:01:12 UTC. All 1,430 non-helper
files in the committed candidate are byte-identical to `7093854d` and `ec5b8250`;
their hash-population digest remains
`6ca03a541963bd75204b6631c76fb76d2beb9d79c01bbfbafc5a642f70811214`.
The census receipt digest is
`249684c1572bdffe51833fecf92dc9c65a226dad4f68dd33fce333b52b4519ca`.
It records a conservative implementation-time upper bound of 236.44 seconds:
the exact stop clock was not captured, but implementation and its failed census
launcher had stopped before 20:50:07 UTC. Administrative repair and the separate
read-only retry are excluded from that stopped implementation interval.

The census and immutable reviews satisfy the prerequisites for the two new
acceptance builds above. Run them from immutable `6409d0ed`, in the assigned
`vm-clean-rebuild-1` and `vm-clean-rebuild-2` trees and their distinct
`vm-qualified-build-1` and `vm-qualified-build-2` trees, with the explicit selected
mode. Preserve every old raw receipt and audit. A build, seal, kernel,
classification or input-stability failure stops acceptance; it does not authorize
an automatic source, helper, package or scope repair.

## Prepare retirement of the default-mode audits

The two new selected-mode builds have passed all seven compilation stages and
created fresh mode-bound seals; their complete kernel verdicts remain pending.
Retirement was prepared to stop retaining duplicate active execution; its
invocation was rejected as recorded below. These incomplete runs supply no
passing evidence.
The preparation preserves original seals, inputs and logs and requires the
existing producers to record any genuine interruption without relabeling a
receipt. The execution contract below belongs to that unexecuted preparation;
the current decision at the end preserves both eligible pairs.

The read-only identity snapshot at 21:27:07 UTC has digest
`0e29902628b4ca5e3cb7e1fe58339d5216cf78c32bcda9f5d066f9b2089c5357`.
It verifies owned default checker PIDs 454208 and 454207, both start tick 1205640,
under drivers 446861 and 446896 with start ticks 1156594 and 1156826 respectively.
Each checker executable matches its original seal; each full 250-token command
matches the earlier capture. Both original and copied build receipts remain
`passed: false`, and neither fresh-kernel receipt exists.

Commission one Temp-only retirement program, bounded to five active preparation
and execution minutes, with immutable integrator review before signals. Open a
Linux PID descriptor for each exact checker and revalidate its start tick, parent,
owner, executable and full argument digest against that snapshot immediately
before signaling. Send at most one SIGTERM through each verified descriptor.
If a process has exited or its fresh result exists, retain its actual result and
do not signal it. Do not signal a driver, escalate to SIGKILL, attach to an
inferior, or touch either selected-mode audit. Read the existing producers'
completion results with bounded waits and record their real kernel/driver exits.
Any identity mismatch or failed signal stops this retirement act.

The integrator reviewed the immutable retirement program, digest
`adf08797560172dc9061492f1f47c3823861b0149becbe610d81a67d29177956`.
Automatic approval review rejected its invocation before process creation because
SIGTERM would irreversibly discard the two audits' in-progress computation and
the user had not explicitly authorized terminating them. No program launched,
signal was sent, or receipt changed. The integrator requested explicit user
authorization; elapsed time is not approval. Both selected-mode audits continue
unchanged, and no workaround or indirect termination is authorized.

## Read the selected conversion paths

A separate five-minute read-only review of the exact locked package, completed
by 21:29:11 UTC, distinguishes its conversion paths. `Typeops.check_cast` sends
explicit VM casts to `Vconv.vm_conv`; default casts use closure conversion.
Ordinary final type checks and module-subtype comparisons also use closure
conversion. Enabling the selected VM option therefore does not replace every
conversion performed by the complete checker.

`Vconv.vm_conv_gen` can handle a bytecode compilation exception by warning and
performing ordinary conversion for that individual comparison. This retains the
check and leaves the global selected option enabled; it is distinct from a
globally unsupported, disabled or ignored option. The selected profile records
the option, not a claim that every comparison executed in the VM. No helper or
running audit input changes follow from this reading.

The source manifest has digest
`477f1f7c498607acd2d171c56ac6625444d694a3695964464a12e714b2efb849`.
The reviewer rehashed its package archive, and the integrator verified the copied
source digests and read the cited conversion, cast, constant and subtyping paths.
Neither reviewer accessed active audit processes or logs. The last emitted
constant name identifies no current conversion path, expensive operation or
completion time.

## Preserve active inputs during eligible-lane retirement

While any original compiler audit remains active, preserve its public C
checkout, private source worktree, branch and native inputs. The user has
delegated the termination decision; the current decision below preserves both
eligible pairs. An active lane is not eligible for retirement, and preserving it
requires no process termination or workaround.

The separate five-minute read-only lifecycle review, completed at 21:57:08 UTC
against immutable integration revision `09f72839`, confirms that
[fanout](../../tools/fanout.md) integrates and retires only explicitly selected
lanes. Every public C commit is already an ancestor of integration `main`.
Select only stopped, clean and integrated A, B and D for the final batch while C
remains active; revalidate their ownership, containment and retained outputs
before retirement. C remains integrator-owned and must not be relabeled as a
host-managed worktree. Preserve the active private source lane as well; retire
other private lanes only after their separate eligibility checks.

This permits safe retirement of eligible lanes while active C inputs remain
preserved. It changes no Q39 acceptance predicate: both selected complete kernels,
exact assumption classification, input stability, compiler campaigns, argument
replays, HELLO acceptance and tracked manifest restaging still require actual
passing evidence. Publish all session commits on `main`, require both Host CI
platforms, and dispatch every Guest CI lane with the required cold policy.
Record the revision, run identifiers and pending guest status without waiting for
Guest CI.

If C remains retained, HELLO's recipe records the actual accepted compiler,
simulator and explicit stage paths beneath
`/root/build/lane-checklist-20261010-c/`; do not substitute a prospective native
retirement destination. Final evidence must name the retained C and private
inputs and state each superseded audit's genuine available result. A pending
verdict supplies no passing evidence, and eligible-lane retirement supplies no
claim that C was cleaned. If all active C audits finish, determine C's eligibility
again before selecting it.

## Select the first fully qualified complete pair

The five-minute read-only eligibility review, completed at 22:31:37 UTC, finds
no mode-specific gap between the sealed `ec5b825` standard-mode pair and the
`6409d0ed` VM-mode pair. Both retain the same 1,430 non-helper compiler and proof
files, complete roots and recursive dependencies, installed-library and tool
binding, individual query guards, exact assumption classification and post-audit
stability. The matcher is unchanged. The public reader at `5c7f1b21` requires
successful source-bound native qualification and locked tool identities, without
requiring the VM profile or newer qualification schema.

Select the first pair whose two original native producers genuinely finish the
complete kernel, classification and stability checks successfully. This decision
avoids an additional wait for a duplicate complete pair after equivalent required
evidence exists. At this decision no passing pair has been reported. Do not mix
source revisions or modes, substitute the older unsealed runs, pass an `ec5b825`
seal through a newer helper, or relabel an actual standard-mode run as VM-mode.
Keep each original producer's schema, helper/source revision, actual argv, seal,
logs and executable digests. The VM controls remain evidence for that supported
configuration; they supply no complete-compiler verdict or timing claim.

After selecting a genuinely qualified pair, record that choice and execute every
remaining Q39 campaign, argument replay, HELLO reproduction and refusal control,
manifest restaging and focused test against its actual compiler. Update HELLO's
pin only to the accepted rebuilt digest. The selected pair changes no normative
acceptance predicate and authorizes no termination or mutation of another run.
Preserve every still-active public, native and private input until eligible.

The prepared fanout journal's audit deferral must describe only the unselected
pair. If its existing description no longer matches the settled selection,
initialize a fresh final journal with the correct explicit eligible lanes and
deferrals; retain the preparation journal and its genuine state. Publish only
`main`, require Host CI and dispatch the complete cold Guest CI handoff under the
existing completion contract.

## Keep both eligible audit pairs running

On 12 October 2026 the user delegated the pending SIGTERM decision to the
integrator. Keep the original `ec5b825` standard-mode pair and `6409d0ed` VM-mode
pair running under the first fully qualified complete-pair rule above. The
prepared retirement program remains unexecuted; this decision sends no signals
and changes no producer, helper, source or package input.

Both original pairs remain eligible. The observation at 01:32:16 UTC reports
standard checker PIDs 454207 and 454208 active after 7:44:20, and VM checker PIDs
463353 and 463354 active after 4:20:21 and 4:20:20. Each VM checker's measured CPU
time closely tracks its elapsed time. There is no demonstrated throughput benefit
from discarding the older pair's in-progress computation, while retaining it
preserves another eligible route to the same required evidence. These timings
establish no completion estimate or passing verdict.

Preserve all original inputs, seals, logs and genuine available results. Neither
pair is selected or accepted while its complete qualification remains pending.
The active-input retention rules and final acceptance, publication and hosted
validation handoff remain unchanged.

## Investigate future audit reuse without interrupting current runs

On 12 October 2026 the user asked whether future audits could become substantially
faster, and whether existing incremental functionality could preserve progress
after stopping an audit. Two read-only scouts inspected static sources in dedicated
lanes `checklist-20261012-cache-e` and `checklist-20261012-speed-f`, each based on
VerifiedOS `3d4733cc` and bounded to ten active minutes. Neither scout ran a gate,
build, benchmark or live-process diagnostic. The integrator exported only the
three helper sources from the immutable `ec5b825` and `6409d0ed` commits into Temp;
the export archive digests are respectively
`99ee7c35e717a9b673c35d74420ffdfcb3b6c706e2a37c3d7e188c336e5a8ea0` and
`b69ed3445bd1552ad1dd17676145f2141d273d9ef4c0ff14ff739f6c9429d33f`.

The existing standalone `test/verifiedos-q39/qualify.py` accepts `--original`,
`--out`, `--lock`, `--opam-root` and `--switch`. It can validate and reuse the
authenticated seven completed compilation stages, proof objects and compiler in
a distinct qualification tree. It refuses an existing output destination, repeats
enumeration and queries, and launches a new complete checker. It writes
`fresh-kernel.json` only after that checker returns. This capability preserves
completed compilation work; it does not resume the current checker.

The exact [Rocq 9.3 checker entry](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/coqchk_main.ml)
has no save or resume option. Its
[library checker](https://github.com/rocq-prover/rocq/blob/V9.3.0/checker/checkLibrary.ml)
keeps the checked environment in memory and processes the required libraries
sequentially. The [release manual](https://rocq-prover.org/doc/V9.3.0/refman/practical-tools/coq-commands.html#compiled-libraries-checker-rocqchk)
states that checking does not mark the proof objects as checked. An interrupted
whole audit therefore loses its in-memory kernel-check progress. A progress-log
prefix supplies neither a complete verdict nor a persisted validation certificate.
Retain both eligible original pairs: their multi-hour checker computation cannot
be recovered through ordinary incremental compilation. This investigation changes
no process, helper, source, package, seal or acceptance predicate.

The preferred future optimization is reuse of completed compiler audit evidence.
The [project proof gate](../../tools/vos/cli/proofs.py) already validates successful
native receipts against source and object bytes, resolved dependency closures,
gate implementation, tool executables, installed libraries and process context.
An unchanged whole-set hit reuses the earlier kernel verdict; a changed module or
object invalidates its transitive consumers. Portable receipts alone authorize no
reuse. The [cache contract](../../tools/README.md#current-evidence-and-generated-documentation)
and [hosted policy](../../tools/ci/README.md) keep cold checks separate. The contained
compiler needs its own validator and receipt before it can adopt this mechanism:
its declared axioms and complete admitted-lemma census differ from the project
proof gate. Pending audits cannot seed that cache, and Q39 still requires both
independent complete qualifications.

For resumable future checking, persist separately completed module or dependency
checks with their bound inputs, then validate coverage and the joint environment
before accepting the combined audit. Rocq documents splitting checks with
`-admit` and warns about replacement between invocations. An equivalent wrapper
must bind every skipped dependency to completed evidence over unchanged bytes,
retain the full source-name axiom classification and admission census, check joint
universe/dependency consistency, and refuse any missing check, peer failure or
input drift. Unconditionally adding `-admit` or `-norec` is not equivalent full
checking. No such incremental compiler contract or implementation is accepted by
this investigation.

Existing project-proof parallelism keeps connected changed dependency components
together. It cannot accelerate a connected component by increasing the worker
limit, and naive recursive checks repeat shared dependencies. A finer dependency
schedule could help independent ready checks, but the existing checker CLI cannot
split one expensive constant. For cold audits, obtain a separately scoped profile
using the supported checker `-profile` option before choosing conversion or proof
representation changes. The [exact cast implementation](https://github.com/rocq-prover/rocq/blob/V9.3.0/kernel/typeops.ml)
routes VM and ordinary casts differently, so enabling VM conversion is not a
universal acceleration. The current VM pair supplies no measured speedup or
completion estimate. No speed factor, cache acceptance or new proof repair is
claimed here; the current qualification and final handoff remain required.

## Shelve the incomplete audits after checkpoint and release triage

On 12 October 2026 the user proposed shelving the current audits, asked whether
newer Rocq or CompCert versions contained a fix, and conditioned a pause on
confidence that the checker was making progress. The bounded read-only triage
retains its [source comparisons, identities and emission timing](retained-evidence/q39/shelving-triage-20261012/README.md).
The current log prefix supplies no accepted resumable checkpoint. Successful
compilation remains a separate reusable phase: the private validator has actually
authenticated the VM compilation candidates, while standard-candidate eligibility
still requires revalidation. Native bytes and every sealed dependency must remain
at their bound paths; the public metadata is not their backup.

The official [Rocq releases](https://github.com/rocq-prover/rocq/releases/tag/V9.3.0)
still name 9.3.0 as newest. The release branch adds a documentation correction;
no matching fix was identified in the bounded development review.
[CompCert 3.18](https://github.com/AbsInt/CompCert/releases/tag/v3.18) is newer, but
the [exact upstream comparison](https://github.com/AbsInt/CompCert/compare/7b1f02b09954b9b916eb2a91d283c9b5355bf172...14d616046360a0b2611ebdfc2f98368af402e1f7)
leaves the parser grammar, validator-completeness source and Menhir generation
file unchanged. The contained compiler's immutable `VERSION` records 3.17; this
comparison does not establish equality with its customized sources. No release
upgrade, port or proof repair is selected by this investigation.

A bounded passive task-clock sample of original standard checker 454207 ran for
eight seconds without signals, ptrace, target-memory writes or a debugger pause.
Its identity and executable were checked before and after; the kernel sample
buffer lost no observations. Exact ELF metadata resolves the sampled activity to
kernel closure reduction and conversion under `check_structure_field`. The
sample establishes activity, not forward progress, a termination bound or an
infinite-loop diagnosis. The earlier single `CList.append_loop` observation does
not locate the current hotspot.

The user then instructed the integrator to commit the dirty edits and decide
whether to pause or stop the runs. **Stop the four original checker processes
after committing this evidence.** Activity has been demonstrated, but the user's
condition for preserving the computations by pausing has not been established.
The unchanged checkpoint and absence of a qualified fix justify shelving these
unbounded attempts for a separately scoped diagnosis; they do not prove a loop.
Preserve the completed compilation and every original native input and output.
Use the reviewed checker identities and PID-bound descriptors, signal only the
checkers, and let their original drivers record genuine interrupted exits.

The integrator committed the pending triage as `82fceaca` before sending any
signal. At 07:25:15 UTC the reviewed PID-bound descriptors sent `SIGTERM` to
checkers 454208, 454207, 463354 and 463353; every identity matched the retained
handoff and every checker was running immediately before the action. No driver
or wrapper was signalled. All four original producers then finished at exit 1,
each writing the genuine fresh-kernel return code `-15`. The
[terminal bundle](retained-evidence/q39/interrupted-audits-20261012/README.md)
retains the action journal and original terminal receipts. Completed builds,
archives, objects, original helpers, locked switches and their bound source
worktrees remain at their existing native paths. The interrupted checkers'
in-memory environments are lost and supply no resumable kernel checkpoint.

An interrupted checker supplies no kernel acceptance. The original seven-stage
receipts remain unchanged with `passed: false` and `kernel: null`; actual failed
kernel execution is recorded separately by the original qualification driver.
Exact classification and final stability remain unperformed. Q39 and Q43 remain
open, the firmware provenance blockers remain, and the acceptance handoff has
not passed. A resumed effort needs a bounded diagnostic and a new complete
qualification attempt under the unchanged acceptance predicate. A changed prover
or compiler requires separately qualified source/toolchain identities rather than
reuse of the interrupted in-memory environment.
