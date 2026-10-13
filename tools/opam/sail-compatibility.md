# Sail support compatibility qualification

The first bounded compatibility route selects the Sail 0.20.3 paired
`rocq-sail-stdpp` 0.20.3 source at
`e7b914cddc032e3676eebd87a808229828013e9c`, keeping Rocq 9.3.0,
Stdlib 9.2.0, stdpp/bitvector 1.13.0, OCaml 5.4.1 and Dune 3.24.2.
Its purpose is to remove artificial release waiting without downgrading the
prover or reducing the canonical machine term's guarantees. The
[canonical-term record](../../docs/assurance/canonical-machine-term.md#routes-that-take-the-five-out)
owns the distinct five-axiom removal and model emission obligations.

## Bounded contract and acceptance

This contract must be committed before the trial starts. Use only a private
source/build prefix in the assigned native lane. Do not install into, pin in,
or otherwise mutate a shared project switch. Record its before/after exports.
Read the exact source's licence and bind the release archive, upstream tree,
package metadata and every patch by SHA-256. Use the release paired with the
locked Sail, not a moving upstream branch.

The first stage runs the package's real Dune build with the locked dependency
versions and existing settings. It may repair package metadata or build syntax
only. It must record whether each patch changes a Gallina source, definition,
statement or compile flag. Preserve every existing flag. The package's own
build result is distinct from the consumer's strict compiler, exact-assumption
and kernel acceptance. Stop at the first source-level semantic incompatibility
rather than expand into an unpriced framework port. Do not downgrade a library,
suppress a diagnostic, add an admission or change an allowed assumption.

A successful package trial must reproduce the support library imports with the
locked compiler and recursive checker, including the positive `Eqdep` control.
The unchanged release is expected to retain the five previously measured Stdlib
axioms; a successful build does not authorize those axioms. Q35g's separately
reviewed axiom-removal patch may be qualified only with its frozen elaborated
comparison, complete strict closure, exact assumptions and unchanged consumer
semantics. The term's `Real` import and all term-side floating-point axioms
remain independently owned obligations.

Production carriage requires a deterministic recipe, immutable source/patch
identities, complete dependency resolution, hosted cold build and fresh
acceptance under the consumer's existing contracts, and a portable snapshot
exported and re-imported from that qualified hosted build. Keep `rocq.lock`
unchanged until that evidence exists. A released package that admits the locked
prover and satisfies the same consumer acceptance retires the local metadata
or source patch after repeating qualification.

The endpoint is either those checks with exact scope and evidence, or a recorded
refusal naming the first incompatibility and its separately scoped next action.
Neither endpoint claims the canonical term, machine logic or binary theorem
complete.

## Strict-source continuation contract

Q35n owns the next bounded trial over the same immutable paired release and
locked dependency versions. It may apply Q35g's recorded axiom-removal patch
and repair source syntax that the existing strict settings refuse. It may not
change compiler flags, suppress diagnostics, downgrade dependencies, add
admissions or widen the allowed assumptions. All sources, patches, tools,
logical mappings and results are hash-bound in its assigned native lane;
shared switch exports must remain byte-identical.

The strict source selection is the paired release's complete `src-stdpp`
module set. Stdlib, stdpp and bitvector retain their unchanged locked package
build settings; this trial commissions no dependency-source compatibility port.
Cold carriage must actually build the selected dependency packages, record
their complete resolution, source, flags and object identities, and include
every loaded dependency in the recursive kernel and exact-assumption checks.
Reports distinguish strict support-source compilation from dependency package
compilation and never claim that all installed sources passed the consumer's
strict flags.

Before a syntax repair, record the affected public declarations' elaborated
types, universes and executable definitions from the package's original build
settings, retaining its warnings. Those baseline outputs establish the reading
only, not strict acceptance. Compare the candidate reading byte for byte.
Q35g's previously approved import and proof changes use that patch's own
baseline, retaining its exact changed-declaration inventory and unchanged
executable-consumer readings. Any unexpected changed statement or executable
definition stops the trial and returns to its owner.

The focused endpoint is either a complete selected support closure compiled
without diagnostics under the consumer's existing settings, with exact
assumption and recursive kernel checks, or a retained refusal naming the first
incompatibility and a separately scoped next action. The term-import probe
without `Real` must exclude the five previously measured Stdlib axioms; the
`Eqdep` and `Real` positive controls must still report their independently
expected assumptions. A failed or partial closure supplies no carriage evidence.
The repair budget is twelve candidate strict checks or thirty active minutes,
whichever comes first, for this coherent repair; finish the current check at
the limit and retain its diagnostics before replanning.

Only a successful focused endpoint opens a deterministic hosted cold campaign
over those exact sources and patches, repeating the package build, frozen
readings, strict closure and controls. Production carriage retains the existing
passing hosted, snapshot export and independent re-import requirements above;
`rocq.lock` stays unchanged until they hold. Q35o owns the canonical emitter's
unused `Real` import, generated proof syntax and the matching record-update
spelling in support and backend. A grammar repair must retain its exact
notation expansion and frozen declaration readings. Q35b retains the
actual term compile, exact closure, compiled size and classification of its
already recorded floating-point axioms. Neither a support probe nor a pending
hosted result completes Q35b.

## Trial result

The 2026-10-12 trial starts at repository revision
`af95a7f287ce04a2977687e12d6cab659b81679d`, after committing this contract as
`bcd4bd6f`. Its private native prefix is
`/root/build/lane-rocq-compat-20261012/sail-compatibility`. The
[receipt](../../docs/implementation/retained-evidence/rocq-compat-20261012/receipt.json),
SHA-256 `8705df0cd027c2428388b5206ddad89ebd1086823c1c3e4394c9a06b19f035bb`,
records commands, actual source/archive/licence identities, executable hashes,
exits and diagnostic-log digests. It records no source patch or downgrade.
The generated retained-copy snapshot
[`rocq-compat-20261012/manifest.json`](../../docs/implementation/retained-evidence/rocq-compat-20261012/manifest.json),
SHA256 `009d5400b9a097291f8606858253fcbebee670a510bbbe8e49d8b7217425d19f`,
binds every indexed receipt, log, probe, switch export and licence copy by size
and SHA-256. The focused retained-evidence check verifies those unchanged bytes;
the snapshot supplies no production or proof acceptance.
The existing installed stdpp was copied into the private prefix; bitvector
was built and installed only there. The unchanged source's own opam metadata
admits Rocq 9.3.0, so selecting its immutable upstream commit provides a
candidate route around the published package's upper bound.

| Check | Observed result | Acceptance scope |
| --- | --- | --- |
| stdpp bitvector 1.13.0 Dune package build and private install | exit 0 | Exact dependency builds at the locked versions; retained confirmation reuses its private build outputs. |
| Sail support 0.20.3 `dune build -p rocq-sail-stdpp -j 2 @install @runtest` | exit 0, with upstream diagnostics | Actual completing package build and package tests; incremental after correcting private dependency-path layout, not cold evidence. |
| Term import probe and `Eqdep` control under the existing strict compiler flags | each exits 0 with no diagnostic | Imports from the private package build work; no changed theorem is qualified. |
| Each probe's recursive `rocqchk -silent -o` | each exits 0 and names the same five Stdlib axioms | Reproduces the known assumption conflict; not passing exact-set acceptance. |
| Direct `Print Assumptions` queries for those five declarations | exit 0, naming each axiom | Independently confirms the named assumption declarations. |
| Strict compile of unchanged `Inhabited.v` | exit 1 at line 12, `notation-for-abbreviation` | First strict source refusal: two deprecated `Notation` abbreviations require reviewed source compatibility work. |
| Shared proof-switch exports before/after | byte-identical, SHA-256 `3e70338fb77832f9e09ee8780cd10524e002420b1ca9aa5f56a15777765e1b32` | No shared package resolution changed. All inventoried upstream source bytes are unchanged. |

The release archive's SHA-512 matches the published checksum. Its SHA-256 is
`1a0e226608ac84add6cd1f61a11637ea9db5e00e1551b2070945310078c9e031`.
The stdpp 1.13.0 archive used by bitvector likewise matches its published
SHA-512; SHA-256
`c7bec4536187ff8dc401efae828f1f5d1d4e3f32f46eca907ffa98f829011d00`.
The exact Sail support `LICENSE` read is BSD-2-Clause, SHA-256
`9e52d88fe1802beb469e538b8c026ff5e7f9413ef06cd3ce898ee3928ae24df0`;
stdpp's `LICENSE` is BSD-3-Clause, SHA-256
`bc4fe79f9b7f78bc6e4e61e1f7c430b1e413b82de4aacb9355ade5e43bad2a69`.
Source trees and compiled libraries remain native trial inputs. The
[third-party record](../../THIRD-PARTY.md) owns intended distribution.

The bounded trial therefore closes the uncertainty about the package's real
builder at the current versions and removes the policy requirement to wait
for a release. It refuses production carriage. The next bounded source
qualification must eliminate strict source diagnostics, qualify Q35g's
five-axiom removal with frozen elaborated comparisons, and then run the full
consumer acceptance on hosted cold inputs. An opam pin/import of a production
snapshot, the full canonical term and a frozen semantic comparison were not
performed. `rocq.lock` stays unchanged.

## Reproduction

Use an empty assigned native prefix, a unique OS temporary directory for
diagnostics, and the unchanged project proof switch. Fetch the exact release
sources with `opam source rocq-sail-stdpp.0.20.3 --dir=PREFIX/coq-sail-0.20.3`
and `opam source rocq-stdpp-bitvector.1.13.0 --dir=PREFIX/stdpp-1.13.0`, checking
the archive digests above. Read the actual licence files before any carriage.
With the proof switch environment applied only to the child process:

1. In `PREFIX/stdpp-1.13.0`, run `dune build -p rocq-stdpp-bitvector -j 2 @install`,
   then `dune install rocq-stdpp-bitvector --prefix=PREFIX/private
   --libdir=PREFIX/private/lib`.
2. Copy the unchanged installed `lib/coq/user-contrib/stdpp` into the same private
   prefix, preserving the private `stdpp/bitvector` files. Set child `ROCQPATH`
   and `COQPATH` to `PREFIX/private/lib/coq/user-contrib`. A prefix containing
   bitvector alone shadows the installed `stdpp` root and fails; that is a path
   layout error, not a source incompatibility.
3. In `PREFIX/coq-sail-0.20.3`, run the package build and tests from the table.
   Compile the retained probes with `rocq c -q -w
   +default,-abstract-large-number -set 'Default Goal Selector=!'
   -disallow-sprop`, mapping the private stdpp, Dune-built `SailStdpp` and probe
   directories exactly as the receipt records. Check each compiled root with
   `rocqchk -silent -o` and the same logical mappings.
4. Confirm both export equality and unchanged source inventories. Retain strict
   diagnostics and the exact axiom names; do not interpret zero package or
   kernel exit as production qualification.

After source qualification, the immutable candidate pin is
`git+https://github.com/rems-project/coq-sail.git#e7b914cddc032e3676eebd87a808229828013e9c`,
with the paired version 0.20.3. Apply it only in the private qualification
recipe, retaining the locked dependency resolution. The candidate pin has
not been installed or accepted by this trial.

## Focused strict-source result

Q35n's 2026-10-13 private trial, at `07e2724f`, compiles all 29 selected
`src-stdpp` modules without diagnostics under the consumer's strict settings.
Its [receipt](../../docs/implementation/retained-evidence/q35n-20261013/receipt.json)
records nine syntax candidates, exact frozen comparisons and the selected
kernel controls. The dependency libraries retain their own recorded package
flags; this result claims no strict-source port of Stdlib, stdpp or bitvector.
No shared switch or snapshot changed, and production carriage remains open.

The immutable [syntax patch](../../docs/implementation/retained-evidence/q35n-20261013/sail-support-strict.patch),
SHA-256 `cee3710ee8b21c439885190e30cf0618fe68fb3a4071dd9991c2f5db37122477`,
applies after Q35g's recorded patch to the paired release. It preserves the
release's source symlinks and adds explicit original first-goal selection,
current abbreviation syntax, both kinds of hint database declarations and
nested-type induction registrations. It removes Values' unused deprecated
`Zeuclid` export. Record-update syntax uses the distinct `sail_update (r with
field := e)` keyword at level 0; the original bracket spelling conflicts with
stdpp's notation prefixes at level 0, while level 1 is refused by the strict
closed-notation diagnostic. The expansions and executable definitions stay
unchanged. Q35o owns the matching canonical backend spelling.

The [frozen-query inventory](../../docs/implementation/retained-evidence/q35n-20261013/frozen-query-inventory.json)
names the queries and public declarations. Its
[comparison](../../docs/implementation/retained-evidence/q35n-20261013/frozen-comparison.json)
records byte-identical elaborated types, universes and transparent bodies for
823 declarations across 21 modules, including Inhabited's two aliases.
Those are the inventory's counts; neither source-name enumeration nor a
frozen reading supplies proof acceptance by itself.

The three assumption probes and notation client compile without diagnostics and their recursive checker runs
exit 0. The kernel-context parser used by the proof gate reads exactly:

- `TermProbe`, which loads the canonical support imports without `Real`: no axioms.
- `ControlEqdep`: `Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq` alone.
- `ControlReal`: `Stdlib.Logic.FunctionalExtensionality.functional_extensionality_dep`,
  `Stdlib.Reals.ClassicalDedekindReals.sig_not_dec`,
  `Stdlib.Reals.ClassicalDedekindReals.sig_forall_dec` and
  `Stdlib.Logic.Classical_Prop.classic`.

The positive controls retain those assumptions deliberately; they are not an
addition to the project's allowed set. Source, object, tool and switch bytes
are bound in the retained identities and logs. The first baseline reproduction
also invoked the package's full `@runtest` locally by mistake. Its exit 0 is
retained as a diagnostic observation with no acceptance credit; subsequent
local work used builds and these selected controls only.

This focused endpoint opens the separately required hosted cold package,
controls, portable snapshot export and independent re-import campaign. It
neither installs the library into the shared proof switch nor completes Q35b's
actual term compile, exact closure or compiled size.

The notation client instantiates the new spelling and proves by reflexivity that
its result is the original record-field expansion; its kernel context names no
axiom. This catches an accepted but incorrectly spelled syntax template.

The actual canonical consumer has a separate [semantic compile refusal](../../docs/assurance/canonical-machine-term.md#9-the-whole-term-compile-refusal).
A successful source-only cold package/export/import campaign does not qualify
that consumer, authorize production carriage or permit a proof-switch lock
change while the refusal remains. Q35n's production-carriage part stays open.
