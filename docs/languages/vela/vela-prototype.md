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
locals use `let` and exits use `return` or an expression body. Contracts, grades,
effects, loans and machine representations are unsupported and diagnosed,
never ignored.

The prototype accepts UTF-8 source with ASCII identifiers and `//` line comments.
Identifiers match `[A-Za-z_][A-Za-z0-9_]*`, excluding grammar and reserved extension
keywords; the latter produce unsupported-feature diagnostics. Decimal
literals match `[0-9]+`; leading zeros are permitted and normalized on emission.
Every file contains one named module and at least one function or constant. Every parameter
and return type is explicit. A function can call only previously declared
functions; recursion and forward calls are refused. Local bindings are immutable.

```text
module Example;
public Nat Twice(Nat x) => x + x;
public Nat Select(bool flag, Nat x) {
  let result = Twice(x: x);
  if (flag) { return result; } else { return 0; }
}
```

The accepted grammar is:

```text
file      := 'module' name ';' declaration+
declaration:= function | 'public' constant
function  := 'public' type name '(' parameters? ')' body
body      := block | '=>' expression ';'
parameters:= type name (',' type name)* ','?
type      := 'Nat' | 'bool'
block     := '{' binding* exit '}'
binding   := 'let' name '=' expression ';' | constant
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
not change the emitted application. Let bindings infer only their expression's
`Nat` or `bool` type. Duplicate functions, parameters, local bindings in an active
scope (including active parameters) and unbound values are errors. Function and
value namespaces are separate. Equality returns `bool`. Natural arithmetic,
equality and comparison map to `Corelib.Init.Nat.add`, `.mul`, `.eqb` and `.leb`.
Boolean equality maps to pure nested conditionals returning the Boolean
constructors. Types and constructors come from `Corelib.Init.Datatypes`.
Constants follow the [required-static contract](surface-grammar.md#required-static-constants):
their typed initializers evaluate from earlier constants and pure calls with
static arguments, under finite work and numeric bounds. Runtime parameters and
ordinary outer locals are refused before evaluation, including ignored or dead
dependencies. Constants denote evaluated values and cannot be reassigned or
called. Compiler-recorded constant symbols support the existing editor services.
Every user name is mapped to a generated identifier so Gallina keywords and
library names cannot capture source references. There is no raw Gallina escape.

Whole-source size, block/binding nesting, expression nesting and decimal-literal length have explicit
implementation limits, reported as limit diagnostics rather than acceptance.
These are host parser limits, not target resource bounds or integer widths.

## Command and publication

`python tools/run.py vela check SOURCE` parses and checks the complete file and
reports its prototype status. `python tools/run.py vela emit SOURCE` writes
Gallina to standard output; `--output FILE` publishes it through the shared
atomic writer only after complete validation. Reject overwriting the input,
including aliases. Do not create missing output parent directories implicitly.
Diagnostics identify the file, line and column, distinguishing syntax, name,
type, unsupported-feature, encoding, limit and I/O failures. Rejected source
produces no generated output. Atomic file publication preserves existing output
after a failed write; standard output cannot roll back bytes already consumed.

Deterministic output uses fully qualified CIC operations and SHA-256 provenance
for exact source bytes, without a correspondence theorem. Emit definitions only:
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
