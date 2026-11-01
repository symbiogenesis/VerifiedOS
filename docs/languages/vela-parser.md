# Vela development parser qualification

## Bounded increment

[Q25g](../../PLAN.md#q-assessment-actions) commissions a syntax-only Menhir
development parser for the [pure prototype's source fragment](vela-prototype.md#source-fragment).
Its accepted language is that fragment's grammar, with whole-file consumption.
Name resolution, typing, elaboration and Gallina emission stay separate. In
particular, a duplicate declaration or `true + 1` parses successfully: syntax
acceptance supplies no name or type verdict. Unsupported extension keywords,
invalid UTF-8, incomplete input and resource exhaustion produce located refusals.

The authored OCaml grammar and syntax-tree types are the syntax owners for this
increment. Actions construct located syntax only. Every node carries a half-open
byte-offset span into the original source; diagnostics use one-based lines and
columns, treating CRLF and bare CR as line endings. Decimal spellings remain
strings, including leading zeros, so parsing imposes no machine-integer bound.
UTF-8 comments are allowed; identifiers remain ASCII. Source bytes are never
normalized before computing provenance.

The code backend of Menhir 20260209 is the selected bounded route. Its generator
and OCaml compiler come from the existing [Sail snapshot](../../tools/opam/sail.lock).
The build refuses a different generator or compiler version. Build products live
in the native lane, with the authored input digests, tool identities, generation
arguments and generated-file digests in a receipt. Repeated generation in fresh
directories must produce identical parser bytes. No generated parser or upstream
runtime source is tracked. This route links no Menhir runtime library. Read the
selected release's own licence and record its output terms in
[THIRD-PARTY.md](../../THIRD-PARTY.md) before incorporation.

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

An independent reviewer reads the grammar against the prototype contract and
selects expected trees independently of grammar actions. Preserve the existing
Python prototype and its tests during this increment. Q25g closes the executable
development increment only, without a checked-parser, lexer-correctness,
source-correspondence or full-language frontend claim.

## Promotion and retirement

[Q25h](../../PLAN.md#q-assessment-actions) owns promotion and Python parser
retirement. It must qualify the exact generator and Rocq support-library closure
with the locked prover, preserving version checks, and name the checked parser
correctness/completeness theorems and their exact assumptions. A conflict-free
grammar and checked completeness evidence are required for that claim; source
spans, diagnostics and lexing need their own evidence. Any backend grammar view
must be generated from one owner and checked for drift.

Prefer a released support library carrying the required Rocq adaptations. If none
does, a reviewed upstream revision or a separately maintained fork may supply
them, with its own licence reading, reproducible source pin and bounded semantic
comparison. Contribute necessary fixes upstream when their qualification is ready.
Release stamping must keep generator/library version checks meaningful; disabling
them does not qualify a pair. The [existing compatibility record](../../tools/opam/certirocq-compatibility.md#native-trial-verdict)
identifies the upstream proof-command relocation and the remaining version issue.

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

Syntax is now consumed completely before semantic checking, so a multiply-invalid
file can report a later syntax error before an earlier name or type error. That
diagnostic priority is the syntax-first frontend's selected behavior; independent
single-fault semantic fixtures retain their categories and locations.

### Rocq support prerequisite

`python tools/run.py vela-parser support` authenticates the Menhir 20260209 release
archive, builds its Rocq support library in the existing locked proof switch and
runs the recursive kernel checker. An optional `--archive FILE` uses the same
authenticated bytes without downloading them. The bounded source adaptation moves
only the three late `Proof` commands identified in the
[same-prover compatibility record](../../tools/opam/certirocq-compatibility.md#native-trial-verdict).
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
