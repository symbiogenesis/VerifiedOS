# Pure Vela translation prototype

Start with the [primary Vela design and examples](verification-strategy.md).
This document specifies the implemented pure fragment and its development commands.
The opt-in [mathematical elaborator](elaboration-prototype.md) adds generics,
dependent types, higher-order inference and explicit proof terms through the
existing native surface parser. The pure command below retains its narrow scope.

## Commission and interpretation

[Q25e/Q25f](../../../PLAN.md#q-assessment-actions) commission a bounded host tool
translating explicitly typed pure functions to Gallina. Accepted expressions mean
their generated CIC terms, with no independent evaluator, reduction relation or
semantic anchor. `Nat` and `bool` denote mathematical naturals and booleans, not
machine words, layouts or CHERI permissions.

The [narrower-fixture rule](core-design.md#decision-and-reopening-evidence) keeps
this separate from the returned-loan trial and [held full-frontend rows](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows).
The full calculus retains its interpretation/register duties. Untrusted Python
parsing/checking supplies no kernel acceptance, checked source correspondence,
`SourcePackage`, metatheory, compiler qualification or binary admission.

## Development parser goal

The [Menhir development route](verification-strategy.md#development-parser-and-grammar)
produces located syntax before separate checking/elaboration. Python syntax and
the strict generated-AST decoder feed shared resolution, typing and emission.
Replacement requires the [plan's qualification](../../../PLAN.md#vela-whole-system-authoring-proposal)
and [parser/migration contract](vela-parser.md).

`python tools/run.py vela-parser parse SOURCE` exercises generated syntax;
`vela-parser qualify` checks independent AST fixtures/regeneration;
`vela-parser migration` compares source edits and independently expected
acceptance/refusal categories, retaining all differences. `vela` uses Python
syntax until Q25h passes. Retain current examples/refusals as migration fixtures.

## Source fragment

This subset follows the [proposed surface](verification-strategy.md#an-ideal-surface):
return types precede operation names, parameter types precede bindings, immutable
locals use `let` with an optional type, required-static values use typed `const`, and exits use `return`
or an expression body. Contracts, grades,
effects, loans and machine representations are unsupported and diagnosed,
never ignored.

The prototype accepts UTF-8 source with ASCII identifiers and `//` line comments.
Identifiers match `[A-Za-z_][A-Za-z0-9_]*`, excluding grammar and reserved extension
keywords; the latter produce unsupported-feature diagnostics. Decimal
literals match `[0-9](?:_?[0-9])*`; underscores separate digits, while leading
zeros are permitted. Separators and leading zeros normalize on emission; their
authored spelling and source locations remain intact in syntax. The
[separator contract](authoring-tools.md#numeric-separators) owns the digit bounds
and wider surface's hexadecimal, binary and representation-suffix rules.
Every file contains one named module and at least one function or constant.
Declarations are resolved in source order. Every parameter and return type is
explicit. A function can call only earlier functions; recursion and forward calls
are refused. Local bindings are immutable.

```text
module Example;
public const Nat Twice(Nat x) => x + x;
public const Nat Limit = Twice(x: 8);
public Nat Scale(const Nat factor, Nat value) {
  const Nat multiplier = Twice(factor);
  return multiplier * value;
}
public Nat Runtime(Nat value) => Scale(factor: Limit, value: value);
public Nat Select(bool flag, Nat x) {
  const Nat fallback = Twice(x: 0);
  let result = Twice(x: x);
  if (flag) { return result; } else { return fallback; }
}
```

The accepted grammar is:

```text
file      := 'module' name ';' declaration+
declaration:= function | 'public' constant
function  := 'public' 'const'? type name '(' parameters? ')' body
body      := block | '=>' expression ';'
parameters:= parameter (',' parameter)* ','?
parameter := 'const'? type name
type      := 'Nat' | 'bool'
block     := '{' binding* exit '}'
binding   := 'let' type? name '=' expression ';'
           | type name '=' expression ';' | constant
constant  := 'const' type name '=' expression ';'
exit      := 'return' expression ';'
           | 'if' '(' expression ')' block 'else' block
expression:= comparison
comparison:= sum (('==' | '<=') sum)?
sum       := product ('+' product)*
product   := atom ('*' atom)*
atom      := decimal | 'true' | 'false' | name
           | name '(' arguments? ')' | '(' expression ')'
arguments := argument (',' argument)* ','?
argument  := (name ':')? expression
```

Arithmetic and `<=` take naturals; equality takes two operands of the same type.
A condition is Boolean and every reachable branch returns the declared
function result type. An expression body checks exactly like a single return;
its expression is evaluated once. Optional trailing commas apply to nonempty
parameter and argument lists, never to grouping. Statements after a terminal
return or conditional are refused, and a block without a terminal result is a syntax error. Calls have the
declared arity and argument types. A positional prefix may be followed by a
labeled suffix; each label must name the next declared parameter. Reordered,
duplicate or unknown labels, omitted arguments and positional arguments after a
label are refused. Labels preserve once-only left-to-right evaluation and do
not change the emitted application. Local annotations must match the initializer's
`Nat` or `bool` type exactly; unannotated locals infer it. Bare typed locals are
immutable too and receive advisory `VELA104`, preferring an explicit `let`.
Duplicate functions, parameters, local bindings in an active
scope (including active parameters) and unbound values are errors. Function and
value namespaces are separate. Equality returns `bool`. Natural arithmetic,
equality and comparison map to `Corelib.Init.Nat.add`, `.mul`, `.eqb` and `.leb`.
Boolean equality maps to pure nested conditionals returning the Boolean
constructors. Types and constructors come from `Corelib.Init.Datatypes`.
Constants follow the [required-static contract](surface-grammar.md#required-static-constants):
their typed initializers evaluate from earlier constants and pure calls with
static arguments, under finite work and numeric bounds. The supported constant
types are `Nat` and `bool`. Unmarked runtime parameters and
ordinary outer locals are refused before evaluation, including ignored or dead
dependencies. Constants denote evaluated values and cannot be reassigned or
called. Compiler-recorded constant symbols support the existing editor services.
An ordinary local inside a pure function evaluated with static arguments belongs
to that evaluation; it is not an outer runtime dependency. Constants with machine
types such as `usize` require the wider selected-target interpretation and are
outside this pure prototype.

The function modifier records constant-evaluation support without restricting
runtime calls. A static parameter is checked symbolically in its definition and
requires a static argument at every call. Instantiation substitutes that argument
and computes the required local constants, leaving ordinary data arguments in
their original order. Forwarding a static parameter preserves its availability;
neither a ghost binder nor a runtime local acquires that availability implicitly.
Logical template definitions may retain symbolic static expressions; this host
prototype establishes no target erasure or source-correspondence theorem.

Every user name is mapped to a generated identifier so Gallina keywords and
library names cannot capture source references. There is no raw Gallina escape.

Whole-source size, block/binding nesting, expression nesting and decimal-literal length have explicit
implementation limits, reported as limit diagnostics rather than acceptance.
These are host parser limits, not target resource bounds or integer widths.

## Extended pure expressions

Q25ac in [the plan](../../../PLAN.md#q-assessment-actions) commissions an
expression increment over the source fragment above. Both the Python route and
the native pure entry accept `!`, `&&`, `||`, `!=`, `<`, `>`, `>=` and binary
`-`, using the existing wider surface's spellings and precedence. From weakest
to strongest, precedence is `||`, `&&`, a single comparison (`==`, `!=`, `<`,
`<=`, `>`, `>=`), left-associative `+`/`-`, left-associative `*`, prefix `!`,
then atoms/calls/grouping. Comparisons do not chain; parentheses are required.
Repeated negation is permitted within the existing expression bounds. Unary
minus, division, remainder and machine integer types remain outside this increment.

`!`, `&&` and `||` require Boolean operands. Equality and inequality require
two operands of the same supported type; ordering and subtraction require
naturals. Subtraction saturates at zero: `2 - 5` is `0`. Emission uses existing
`Corelib.Init.Nat.sub`, `.ltb` and `.leb`, Boolean equality's once-only bindings,
and Boolean conditionals for negation and short-circuit logic. Reversed ordering
must preserve left-to-right once-only operand evaluation through fresh bindings.
All generated binders remain disjoint from mapped source names.

Both logical operands undergo name/type and required-static dependency checks,
including dead operands. Evaluation and emitted conditionals evaluate the left
operand once and evaluate the right only when needed. Thus
`false && (huge * huge == 0)` can avoid a static arithmetic limit, while
`false && runtimeFlag` still cannot initialize a required-static constant.
Existing work, depth, output and numeric budgets apply; no new evaluator or
browser-side interpretation is introduced.

Acceptance requires independently expected terms and values for every operator,
mixed precedence/associativity, nested negation, Nat underflow, both equality
types, named calls, static parameters and short-circuit limit behavior. Semantic
negative neighbors must reach the intended type/name/static-dependency refusal;
malformed/chained operators, unary minus and excessive depth remain refused.
Native AST controls cover exact operator/operand spans, trivia, Unicode and
newlines, and reject omitted, substituted or extra source tokens. Retain existing
translations and migration controls. Formatting must preserve token/comment
order and reparsed meaning, be idempotent and space prefix negation correctly;
compiler facts and existing LSP operations must remain usable.

The [playground](playground.md#extended-expression-examples) exposes examples and
console suggestions through the same compiler and bounded worker. Focused real
HTTP/worker controls cover new values, Gallina and semantic refusals. Exercise
browser editing, formatting, compilation and console evaluation when browser
infrastructure is available; record its absence explicitly otherwise. Run focused
host tests, Python validation and corpus checks, then record the local revision
and full recommended hosted selection through `fanout`. The user owns Host CI
and Guest CI, including native generation and kernel replay; no pending verdict
counts as qualification or production acceptance.

## Command and publication

`python tools/run.py vela check SOURCE` parses and checks the complete file,
preserves the exact source bytes and runs advisory lints before reporting
its prototype status. The [authoring-tools contract](authoring-tools.md) owns the
StyleCop-inspired style, documentation, lint policy and publication checks.
`vela fmt SOURCE` applies formatting explicitly; `vela fmt SOURCE --check` and
`vela lint SOURCE` leave source unchanged. Normal compiler commands accept
`--format check` for read-only style enforcement, `--format off` to state the
source-preserving default, or `--format write` to opt into canonical formatting.
`--no-lint` disables optional lints; repeatable `--allow ID` and
`--deny ID` control individual findings without disabling language checks.
`vela lint --preview-bindings SOURCE` prints a rechecked candidate containing
only the suggested `let ` insertions, preserving original comments and newlines
and leaving the input file unchanged. Its [source-bound preview contract](authoring-tools.md#lint-policy)
keeps annotation checking, allow/deny policy and semantic comparison explicit.

`python tools/run.py vela emit SOURCE` uses the same default authoring passes and
writes Gallina to standard output; `--output FILE` publishes it through the shared
atomic writer only after complete validation. Reject overwriting the input,
including aliases. Do not create missing output parent directories implicitly.
Explicit source rewriting requires an unchanged regular file and a completely
checked formatted candidate; library and language-server calls never rewrite.
Diagnostics identify the file, line and column, distinguishing syntax, name,
type, unsupported-feature, encoding, limit and I/O failures. Rejected source
produces no generated output. Atomic file publication preserves existing output
after a failed write; standard output cannot roll back bytes already consumed.

Deterministic output uses fully qualified CIC operations and SHA-256 provenance
for the exact authored bytes, or post-format bytes after an explicit formatting write,
without a correspondence theorem. Emit definitions only:
no axioms, admissions, proof scripts or machine-code escape.

## Acceptance

Land this contract and its priced checklist cells before implementation. A separate
reviewer reads the scope and independently authored expected translations.
Focused behavioral tests must cover the example, precedence, lexical scope,
both types and each operation, plus deterministic output, source binding and
name hygiene. Well-formed negative neighbors must fail on return type, condition,
branch, call, duplicate-name or resolution premises. Trailing input, unsupported
constructs, malformed/invalid UTF-8, excessive nesting and oversized literals
must produce bounded diagnostics. Surface-conformance cases use the same declaration,
parameter, return and control-flow spellings as the design dossier. Cover expression
bodies and equivalent return blocks, trailing commas and malformed adjacent forms
through both syntax routes, with unchanged terms apart from exact source provenance.
Reject `fn`, colon-typed parameter, arrow-return and undelimited expression
body forms, along with missing returns and unreachable trailing statements. CLI tests must establish successful publication
and preservation of existing output on rejection, input aliases and write errors.

Host CI on Windows and Ubuntu supplies the integrated tool verdict. Dispatch
every Guest CI lane for the same settled revision and finish without waiting.
The translation tests do not establish that a kernel has accepted emitted terms;
a generated-term kernel replay is a separately identified follow-up unless hosted
evidence explicitly supplies it. Production language and whole-system migration
retain the [unified-source acceptance contract](unified-source-contract.md).

## Try the prototype

From the repository root on Windows (use `python3` on Linux):

```console
python tools/run.py vela check tools/vela/examples/pure.vela
python tools/run.py vela emit tools/vela/examples/pure.vela --output out/Pure.v
```

Create the output directory first, or omit `--output` to print definitions.
The [example](../../../tools/vela/examples/pure.vela) defines a cube and Boolean
selection: intended `Choose(true, 1)` is true, `Choose(true, 2)` false. Output is
module `Vela_Oracle` with `f_Cube`/`f_Choose`; execution requires the separate kernel
replay, since this tool has no evaluator.
