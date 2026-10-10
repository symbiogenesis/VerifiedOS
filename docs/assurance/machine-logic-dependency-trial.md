# Machine-logic dependency trial

Q35m meets the refusal endpoint of the
[bounded dependency contract](machine-logic-breakdown.md#5-proposed-finite-cells-and-prerequisite-boundaries).
The selected Islaris and Katamaran closures do not qualify under the locked
Rocq 9.3.0 compiler settings. Direct compilation, independently of Dune,
reproduces source-level diagnostic refusals in mandatory dependencies of both
frameworks. No framework port, machine-language instance or binary theorem is
accepted. Q35k remains closed to implementation.

The private prefix is `/root/build/lane-solve-20261010-c/q35m`. The trial starts
from repository revision `4e2590b1993e3db408cd1fdb1afa8ce70e502d0d` and uses its
unchanged proof lock. The
[receipt](../implementation/retained-evidence/root/build/lane-solve-20261010-c/q35m/evidence/receipt.json)
records exact command arguments, native working directories, exit codes,
durations, source and executable identities, the strict settings read from the
gate, and the identical before/after switch exports. The
[source inventory](../implementation/retained-evidence/root/build/lane-solve-20261010-c/q35m/evidence/source-identities.json)
hashes every indexed file of each selected source. Exact compiler assumption
closures and frozen elaborated comparisons for the two frameworks are `null`,
meaning unavailable, rather than empty sets or passing comparisons.

## Sources and licence readings

These are source qualification inputs held in the native prefix. They are not
vendored dependencies, installed packages or additions to the shared switch.
The trial uses the upstream statements and definitions byte-for-byte: every
before/after `git diff HEAD` is empty.

| Input | Immutable revision and reason | Actual licence read |
| --- | --- | --- |
| Islaris | [`c978e10f50db5c40f0fdf113f5f76a779782c6f9`](https://github.com/rems-project/islaris/tree/c978e10f50db5c40f0fdf113f5f76a779782c6f9), frozen by Q35c | `LICENSE`: BSD-2-Clause; `THIRD_PARTY_FILES.md`: `None`. The package's BSD-3-Clause label does not replace its actual licence text. |
| Katamaran | [`47bc545117348495f71aad9e20d5c9bb9ed3a757`](https://github.com/katamaran-project/katamaran/tree/47bc545117348495f71aad9e20d5c9bb9ed3a757), the indexed gitlink and Q35c's interface | `LICENSE`: BSD-2-Clause. |
| isla-lang | [`bda86c9f0bd28bbaa2481f50ddc986ede342805a`](https://github.com/rems-project/isla-lang/tree/bda86c9f0bd28bbaa2481f50ddc986ede342805a), Islaris's `pin-depends` | `LICENSE`: BSD-2-Clause. Its generated `isla_lang.v` is not produced by this refusal trial. |
| Lithium | [RefinedC `7945a29d1647970709a9b5ad2ffc53c757e130cc`](https://gitlab.mpi-sws.org/iris/refinedc/-/tree/7945a29d1647970709a9b5ad2ffc53c757e130cc), resolving exactly Islaris's `dev.2024-09-11.0.7945a29d` requirement | Root `LICENSE`: BSD-3-Clause for the selected `theories/lithium` source. The RefinedC frontend, Caesium development and Linux examples are not used. |
| RecordUpdate | [`50e45e9f4ed52840427c3bfddc9037a645d9bf19`](https://github.com/tchajed/coq-record-update/tree/50e45e9f4ed52840427c3bfddc9037a645d9bf19), upstream `v0.3.3`, required by both Islaris and pinned Lithium | `LICENSE`: MIT, including retention of its copyright and permission notice when copied. |
| Iris | [`b909adcc698a6c38f4c3b2645936bdd0d870d412`](https://gitlab.mpi-sws.org/iris/iris/-/tree/b909adcc698a6c38f4c3b2645936bdd0d870d412), release 4.5.0 selected by the landed trial contract | `LICENSE` and `LICENSE-CODE`: BSD-3-Clause for code; `LICENSE-DOCS`: CC-BY-4.0 for `docs/` and `tex/`. Those documentation trees are not redistributed. |

Each licence's exact SHA-256 is in the source inventory. The new dependency
readings are Lithium root `LICENSE`,
`9f12b4d76683118c79a24bd853b5477eed4a1aa1c20d884e07474900331ece74`,
and RecordUpdate `LICENSE`,
`86bc18f7c5d1a7d65fc58b5cdbb31bd965f3815efe83e8556c1a875270678ae4`.
Only the authored runner, probes, receipts and logs are deliverables. Source
trees, licences, compiled libraries and private-prefix build products stay
native; no upstream source or patch is redistributed in this delivery.
Carriage of any dependency remains the opam/foundation owner's separate act.

The locked inventory is Rocq 9.3.0, OCaml 5.4.1, Dune 3.24.2 and stdpp 1.13.0.
It contains no installed Iris, Lithium, RecordUpdate or Equations. All Iris
imports below explicitly map to the single selected native Iris 4.5.0 tree.
There is no substitution of a newer Lithium API or a second Iris release.

## Reproduced incompatibilities

The compatibility adaptation is an explicit source-directory-to-logical-library
mapping passed directly to `rocq c` and `rocqchk`. It bypasses the removed Dune
Coq extension without editing an upstream build file, source declaration,
notation, proof or compiler setting. The receipt retains every mapping.

| Attempt under the gate's strict flags | Exit and deciding diagnostic |
| --- | --- |
| RecordUpdate `src/RecordSet.v` | 1; its postfix notation at line 90 emits `postfix-notation-not-level-1`. |
| Lithium `theories/lithium/base.v` | 1; line 1 emits `deprecated-from-Coq`. |
| Islaris `theories/base.v` | 1; line 56 emits `deprecated-from-Coq`. |
| Katamaran `theories/Notations.v` | 1; its reserved postfix notation at line 55 emits `postfix-notation-not-level-1`. |
| Katamaran `theories/Prelude.v` | 1; the refused `Katamaran.Notations` library is unavailable. |
| Katamaran `theories/Iris/Instance.v` and `theories/Iris/BinaryAdequacy.v` | Each exits 1; the required `Equations` library is unavailable. The latter successfully passes its preceding `Program.Equality` import. |
| Islaris selected-example compiler query and recursive kernel check | Each exits 1; `isla.examples.riscv64_test` has no compiled library. No query result or kernel summary for that root exists. |
| Katamaran instance/binary-adequacy compiler query and recursive kernel check | Each exits 1; `Katamaran.Iris.Instance` has no compiled library. No query result or kernel summary for those roots exists. |

The failure of Islaris's base and Lithium's base occurs before their Iris
imports. Katamaran's notation failure occurs without an Iris import. These are
strict-source refusals that changing Dune or supplying an installed library
cannot by itself resolve. The missing Equations package is an additional
unfulfilled input, not evidence that its API is incompatible with Rocq 9.3.
No stdpp-unstable/bitvector, Ott/frontend or Equations closure is qualified;
the earlier mandatory source failures already decide refusal.

The compiler flags are `-q -w +default,-abstract-large-number -set
Default Goal Selector=! -disallow-sprop`. A warning suppressed by an upstream
build is not accepted under these settings. The
[source-policy reading](../implementation/retained-evidence/root/build/lane-solve-20261010-c/q35m/evidence/source-policy.json)
also invokes the existing gate's `pinned_overrides`: it reports Islaris's
`Default Proof Using` and goal-selector settings, and Lithium's corresponding
settings plus its source-level warning configuration. The trial removes none
of them, relaxes no diagnostic and adds no admission or axiom.

### The Program.Equality import's separate assumption conflict

An authored probe repeats only the mandatory `Program.Equality` import from
Katamaran's frozen binary-adequacy source and asks Rocq about
`Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq`. Its strict compiler exits 0, but
`Print Assumptions` names that axiom. Its recursive `rocqchk -silent -o` also
exits 0 and names the same axiom in the whole-environment context summary:

`Stdlib.Logic.Eqdep.Eq_rect_eq.eq_rect_eq`.

This is a reproduced dependency-import conflict with the existing exact-set
policy, not a complete assumption audit of Katamaran. A zero kernel exit does
not accept an undeclared context axiom. R-05-163 and R-05-164 supply no permission
to add it to a development-local allowlist. The continuation must resolve this
import through a reviewed source route that preserves the required statements;
adding an assumption is not a compatibility fix.

### The separate stock-Iris result

The native Iris 4.5.0 source was built with its published `make-package iris
-j2` builder under the locked switch, with no installation. That build exits 0
using upstream flags and emits Rocq deprecation warnings. The receipt's
incremental confirmation exits 0; it is labelled as a confirmation, not a cold
build. It supplies no strict-source build verdict.

The authored `IrisProbe.v` imports `weakestpre` and `adequacy` from that tree.
Its strict compiler exits 0 with `wp_adequacy` closed under the global context.
Its recursive kernel check exits 0 and reports no axiom, type-in-type, unsafe
fixpoint or assumed positivity. This result is limited to the stock import
and adequacy closure, matching the separately qualified scope in Q35c. It
qualifies neither Islaris/Lithium nor Katamaran and establishes no canonical
Sail-language interpretation.

## Frozen-reading and acceptance boundary

No upstream statement or definition was edited. The two requested framework
roots cannot be strictly compiled at the base, so their elaborated types,
reachable declarations and exact assumption closures cannot be read or compared
at the locked prover. The failed compiler and kernel queries are retained.
The receipt explicitly records both frozen comparisons as unavailable.
Source-byte equality and the separately checked Iris closure do not fill this
gap. There is no accepted port or theorem-repair claim.

This endpoint satisfies Q35m's priced trial contract. It does not satisfy
Q35k's prerequisite for compatible, carried libraries. The
[machine-logic establishment breakdown](machine-logic-breakdown.md) still owns
the canonical-term, selected-subset agreement, resource instance and four-theory
work; none is discharged by this receipt.

## Separately scoped unpriced continuation

The machine-logic foundation owner and opam carriage owner must review and price
one source-compatibility continuation before dispatch. Its identified work is:

- Resolve the namespace deprecations in the exact Islaris and Lithium sources,
  the postfix-notation diagnostics in exact RecordUpdate and Katamaran, and the
  source-level pinned-setting conflicts, keeping the compiler settings fixed.
- Resolve the `Program.Equality` dependency's undeclared axiom and select the
  remaining Equations, stdpp-unstable/bitvector and isla-lang generation inputs
  with their actual licences and exact identities. No API port depth is measured
  by the early failures above, so deeper API work is neither asserted necessary
  nor included in a numerical estimate.
- Establish the frozen elaborated readings required by the
  [proof-assistance workflow](proof-assistance.md#statement-freeze), compile both
  complete selected closures under unchanged strict settings, enumerate their
  exact assumptions and read their recursive kernel summaries. Any changed
  frozen meaning returns to its owner instead of being accepted as a repair.
- Decide carriage separately and take fresh hosted acceptance over the settled
  inputs. Only an accepted compatible/carried result opens Q35k.

This is unpriced source-compatibility work, not an extension of Q35m's bounded
trial estimate. It authorizes no shared-switch change, framework replacement,
semantic weakening, μSail translation or new assurance assumption.

## Reproduction and evidence

The authored [trial client](../../tools/machine-logic-trial/trial.py) uses the
existing locked Python tool environment and adds no package. Prepare an empty
assigned native prefix with one source directory per table row. For each row,
use its upstream repository URL and full revision:

```sh
git init /root/build/lane-<assigned>/q35m/<source-name>
git -C /root/build/lane-<assigned>/q35m/<source-name> fetch --depth=1 <upstream-url> <full-revision>
git -C /root/build/lane-<assigned>/q35m/<source-name> checkout --detach FETCH_HEAD
```

Source names are `islaris`, `katamaran`, `isla-lang`, `lithium`, `record-update`
and `iris`; Lithium's repository is RefinedC. Islaris and Katamaran are fetched
at their frozen revisions. The original Lithium acquisition fetched RefinedC's
history and resolved its pinned abbreviation to the full revision above;
RecordUpdate resolved `v0.3.3` to its full revision. The client checks all six
HEAD identities before compiling anything.

Build only the private stock Iris package using the locked switch:

```sh
opam exec --switch=verifiedos-rocq-9.3.0-ocaml-5.4.1 -- sh ./make-package iris -j2
```

That command's working directory is the assigned prefix's `iris` directory.
Run the client in the Linux guest with the assigned checkout and prefix:

```sh
<lane-root>/venv-linux/bin/python <assigned-checkout>/tools/machine-logic-trial/trial.py --checkout <assigned-checkout> --prefix <lane-root>/q35m
```

It records focused qualification attempts, not a local execution of the host,
guest or proof gate suites. Exit 0 from the client means evidence capture
finished with an unchanged switch; it does not mean that a framework passed.
The receipt contains each individual verdict. Retain `evidence/*.json`,
`evidence/*.log`, `evidence/*.export` and authored `evidence/*.v`; compiled
`.vo`/`.vos`/`.vok`, generated auxiliary files and all upstream source stay
native. The exact native prefix and hashes in the receipt preserve their
identities independently of retirement.

The generated [evidence catalog](../../tools/machine-logic-trial/evidence.json)
binds every retained copy's original absolute native path to its SHA-256. The
client generates it after closing the final receipt; the existing focused
`retained_evidence` tests check those bindings against the indexed copies.
Reproduction generates a new catalog for its new native prefix, timestamps
and receipt bytes rather than pretending to reproduce this run's hashes.
