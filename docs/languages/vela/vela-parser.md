# Vela development parser qualification

The [primary Vela design and examples](verification-strategy.md) explains the language;
this contract owns the development parser's bounded qualification and retirement.

The [complete development surface grammar](surface-grammar.md) extends syntax through
Q25i's separate entry point; the pure entry below remains the migration baseline.
The selected [familiar authoring migration](surface-grammar.md#familiar-authoring-migration)
is Q25z's conditional increment. Its new spellings are not accepted merely because
they appear in design examples; current parser fixtures and commands retain their
qualified scope until the grammar and affected consumers migrate together.

## Bounded increment

[Q25g](../../../PLAN.md#q-assessment-actions) commissions syntax-only Menhir parsing
of the [prototype grammar](vela-prototype.md#source-fragment), consuming the whole
file before separate resolution, typing, elaboration and Gallina emission.
Duplicate declarations and `true + 1` parse without a name/type verdict. Unsupported
extension keywords, invalid UTF-8, incomplete input and exhaustion give located refusals.

The authored OCaml grammar and AST types own syntax; actions construct located
syntax only. Nodes carry half-open original-source byte spans. Diagnostics use
one-based lines/columns, treating CRLF and bare CR as line endings. Keep decimal
spellings, including leading zeros, as strings without machine-integer bounds.
Comments may be UTF-8; identifiers are ASCII. Provenance hashes unnormalized bytes.

Use Menhir 20260209's code backend and the [Sail snapshot's](../../../tools/opam/sail.lock)
exact generator/OCaml compiler; refuse version mismatches. Native-lane build receipts
bind authored-input digests, tool identities, arguments and generated-file digests.
Fresh generations must be byte-identical. Track no generated parser/upstream runtime
source and link no Menhir runtime. Before incorporation, read the release's licence
and record output terms in [THIRD-PARTY.md](../../../THIRD-PARTY.md).

Input is bounded by the prototype's source-byte and literal-digit limits. The
native driver also bounds delimiter nesting and raw syntax-tree depth at 256 before exposing
an AST, and reports stack exhaustion as a limit refusal. Raw syntax counts groups
and file/function/block/return wrappers; the separate AST consumer retains the
prototype's expression and block/binding limits of 64. Independent migration
fixtures cover their individual boundaries and combined paths. The command wrapper
bounds process duration and reads source files with a bounded read. Refused input
publishes no AST. Success emits deterministic JSON containing the complete located
syntax tree and the exact source digest. A successful build alone is no parser
qualification verdict.

## Acceptance and commands

`python tools/run.py vela-parser build` generates and compiles the parser in the
native guest lane. `vela-parser parse SOURCE` emits its JSON syntax tree.
`vela-parser qualify` builds it and runs independent expected-tree fixtures,
whole-file positive/refusal cases, source spans, LF/CRLF/bare-CR positions,
UTF-8 comments and invalid encoding, decimal spelling, precedence and
associativity, incomplete editor input, excessive nesting and oversized input.
Fixtures must show that name and type errors parse as syntax. Qualification also
compares two fresh generations and records the inputs and available verdicts.
Focused local builds and helper tests may guide implementation; hosted execution
supplies acceptance. Guest CI runs qualification in its model lane using its
already installed Sail snapshot. Require Host CI on Windows and Ubuntu, dispatch
every Guest CI lane for the settled revision, and finish without waiting for
Guest CI; its pending parser verdict remains pending.

An independent reviewer compares grammar with the prototype contract and selects
expected trees independently of actions. Retain the Python prototype/tests. Q25g
qualifies executable development syntax only; checked parsing, lexer correctness,
source correspondence and the full frontend need separate evidence.

## Generated syntax campaigns

[Q25y](../../../PLAN.md#q-assessment-actions) qualifies reuse of the
[Menhir manual's](https://gallium.inria.fr/~fpottier/menhir/manual.html) seeded
sentence generation and interpreter/CST inspection after the exact locked Q25g
qualification. The [first-release delivery order](../../../PLAN.md#vela-first-release-delivery)
retains Q25w's concrete foundation priority. This campaign changes neither the
existing code backend/runtime closure nor Q25h's checked-parsing prerequisites.

Freeze the pure entry point, grammar/tool digests, deterministic seed set,
independent expected cases and numeric time, output, token and memory budgets
before implementation. `--random-seed`, `--random-sentence-length` and
`--random-sentence` generate terminal names; the length argument is a goal, not a
hard output bound. Enforce the declared bounds independently, and qualify a
small token-payload renderer before sending generated source through the actual
lexer and parser. Record terminal input, rendered source and selected entry so
a failure replays without random generation. No second grammar is introduced.

Interpreter acceptance and `--interpret-show-cst` can expose automaton and
production-action disagreements, but share the grammar's possible mistakes.
Retain independently selected expected ASTs, source spans and refusal cases.
Generate bounded whitespace, comment, newline and token-payload variants;
compare the expected syntax and exact-source binding while preserving resource
refusals. A deliberately wrong action or span must be detected by an independent
expected observation, not merely by comparing two grammar-derived trees.

Keep `--list-errors` and `.messages` exploration a separately priced follow-up
after an actual diagnostic-maintenance need. The manual warns that enumeration
can consume gigabytes; do not place it unbounded on every parser build. Retain
complete enumeration separately from selected replay cases, and use Menhir's
update/comparison facilities to detect stale state/message coverage. Truncation
or timeout establishes no completeness. Review diagnostic meaning independently
after grammar changes. This reading selects no runtime error-message API, table
backend or Menhir runtime dependency; such changes need their own qualification.

Freeze a named syntax interaction the existing hand-authored corpus does not
systematically vary, and the expected maintenance benefit, before implementation.
Retain a campaign only when it exercises that interaction reproducibly and
reduces explicit case construction or failure reduction under the same controls.
Acceptance preserves syntax/migration fixtures and deterministic regeneration,
demonstrates bounded replay and an independent seeded-defect kill, and records
the exact generator, grammar and rendered-input identities. Stop a campaign
whose bound or renderer cannot be qualified; generation alone supplies no result
about source meaning. Host helper checks and native Guest CI qualification
retain their existing owners and pending status. The
[generated-test boundary](tooling-protocols.md#generated-development-tests)
keeps these development results separate from proof and product acceptance.

## Promotion and retirement

[Q25h](../../../PLAN.md#q-assessment-actions) owns promotion and Python parser
retirement. It must qualify the exact generator and Rocq support-library closure
with the locked prover, preserving version checks, and name the checked parser
correctness/completeness theorems and their exact assumptions. A conflict-free
grammar and checked completeness evidence are required for that claim; source
spans, diagnostics and lexing need their own evidence. Any backend grammar view
must be generated from one owner and checked for drift.

Prefer released Rocq adaptations; otherwise qualify a reviewed upstream revision
or maintained fork with licence reading, reproducible pin and bounded semantic
comparison. Contribute qualified fixes upstream. Preserve meaningful release/version
checks; disabling them qualifies no pair. The [compatibility record](../../../tools/opam/certirocq-compatibility.md#native-trial-verdict)
identifies proof-command relocation and the remaining version issue.

Before switching the prototype, provide a supported build/runtime route on
Windows and Ubuntu; route the generated AST through separate resolution, typing
and emission; pass all existing independent translation, refusal, resource-limit
and atomic-publication fixtures; and add independently expected AST fixtures and
held-out source edits. Compare accepted translations and diagnostic categories,
disposition every difference, and exercise malformed input without output or
unbounded failure. Once these predicates pass, remove Python lexing/parsing and
its fallback, retaining Python orchestration only where useful. The full-language
frontend remains subject to [Q25d's interpretation and admission prerequisites](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows).

### Executable migration preparation

The prototype's Python syntax parser and the generated AST decoder feed the same
separate resolution, typing and Gallina emission consumer. The generated-tree
decoder checks the complete schema, exact source digest, spans and token spellings,
child containment and resource budgets before elaboration. It never invokes the
Python lexer or parser as a fallback.

`python tools/run.py vela-parser migration` builds and qualifies the syntax parser,
then compares both routes on independently categorized fixtures, source edits,
semantic diagnostic locations and resource boundaries. Accepted module identities
and complete emitted bytes must agree. Every difference is retained in
`migration.json` and produces a nonzero verdict; changed consumer, source,
toolchain or generated-parser bytes invalidate the report. Guest CI's model lane
runs this comparison and retains its verdict separately from syntax qualification.
Agreement supplies a migration prerequisite, with no checked-parser or
source-correspondence claim. The ordinary `vela` command continues to select Python
syntax until the complete promotion contract passes.

Whole-file syntax precedes semantics: a multiply-invalid file may report a later
syntax error before an earlier name/type error. Independent single-fault semantic
fixtures retain their categories and locations.

### Rocq support prerequisite

`python tools/run.py vela-parser support` authenticates the Menhir 20260209 release
archive, builds its Rocq support library in the existing locked proof switch and
runs the recursive kernel checker. An optional `--archive FILE` uses the same
authenticated bytes without downloading them. The bounded source adaptation moves
only the three late `Proof` commands identified in the
[same-prover compatibility record](../../../tools/opam/certirocq-compatibility.md#native-trial-verdict).
Source hashes guard both sides of that transformation. A diagnostic reference
deletes just those commands; its frozen public types, universes, executable bodies
and assumptions must match the candidate at the same prover. No source is installed
into the switch. The release's `Version.v` stays byte-identical, and positive and
negative guard clients test its release identity.

Guest CI's proofs lane runs this prerequisite and retains its qualification
receipt. The receipt names the theorem assumptions in an uninstantiated abstract
automaton context; it grants no concrete grammar's assumption or parser verdict.
The exact generator/library pair, Vela's generated Rocq grammar and checked
correctness/completeness, lexer and span evidence, extraction/runtime connection
and both host platforms' replacement route remain Q25h's outstanding predicates.
Support-library build and kernel evidence alone cannot retire Python parsing.
