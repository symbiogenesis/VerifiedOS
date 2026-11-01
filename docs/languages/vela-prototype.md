# Pure Vela translation prototype

## Commission and interpretation

[Q25e and Q25f](../../PLAN.md#q-assessment-actions) commission a bounded host development
tool: parse an explicitly typed, pure function fragment and emit Gallina
definitions. The meaning of an accepted expression is its generated CIC term.
There is no independent source evaluator, reduction relation or semantic anchor.
`Nat` denotes mathematical naturals and `bool` denotes booleans; neither denotes
a machine word, a storage layout or a CHERI permission.

This separately scoped fixture follows the [core design's narrower-fixture
rule](core-design.md#decision-and-reopening-evidence). It does not reopen the
returned-loan trial or commission the [held full-language frontend
rows](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows).
The full calculus still owes its interpretation commitment and register acts.
The Python parser and type checker are untrusted development tools. Their success
is not kernel acceptance, checked source correspondence, a `SourcePackage`,
metatheory, compiler qualification or final-binary admission.

## Development parser goal

The selected development direction is a
[Menhir-generated parser](verification-strategy.md#development-parser-and-grammar)
for the proposed Vela surface, producing located syntax before separate checking
and elaboration. This prototype currently uses a handwritten parser that combines
checking and emission. Its replacement requires the
[plan's `vela-parser` qualification](../../PLAN.md#vela-whole-system-authoring-proposal)
and an independently reviewed migration contract; the goal alone changes no
accepted syntax or assurance claim. Keep the current examples and rejection cases
as migration fixtures.

## Source fragment

The supported fragment follows the [proposed Vela surface](verification-strategy.md#an-ideal-surface):
public declarations put the return type before the operation name, parameters put
the type before the binding, immutable locals use `let`, and function exits use
`return`. This is a subset of that surface rather than a separate expression-language
syntax. Contracts, grades, effects, loans and machine representations remain outside
this prototype; their presence is diagnosed rather than ignored.

The prototype accepts UTF-8 source with ASCII identifiers and `//` line comments.
Identifiers match `[A-Za-z_][A-Za-z0-9_]*`, excluding grammar and reserved extension
keywords; the latter produce unsupported-feature diagnostics. Decimal
literals match `[0-9]+`; leading zeros are permitted and normalized on emission.
Every file contains one named module and at least one function. Every parameter
and return type is explicit. A function can call only previously declared
functions; recursion and forward calls are refused. Local bindings are immutable.

```text
module Example;
public Nat Twice(Nat x) { return x + x; }
public Nat Select(bool flag, Nat x) {
  let result = Twice(x);
  if (flag) { return result; } else { return 0; }
}
```

The accepted grammar is:

```text
file      := 'module' name ';' function+
function  := 'public' type name '(' parameters? ')' block
parameters:= type name (',' type name)*
type      := 'Nat' | 'bool'
block     := '{' binding* exit '}'
binding   := 'let' name '=' expression ';'
exit      := 'return' expression ';'
           | 'if' '(' expression ')' block 'else' block
expression:= comparison
comparison:= sum (('==' | '<=') sum)?
sum       := product ('+' product)*
product   := atom ('*' atom)*
atom      := decimal | 'true' | 'false' | name
           | name '(' arguments? ')' | '(' expression ')'
arguments := expression (',' expression)*
```

Arithmetic and `<=` take naturals; equality takes two operands of the same type.
A condition is Boolean and every reachable branch explicitly returns the declared
function result type. Statements after a terminal return or conditional are
refused, and a block without a terminal result is a syntax error. Calls have the
declared arity and argument types. Let bindings infer only their expression's
`Nat` or `bool` type. Duplicate functions, parameters, local bindings in an active
scope (including active parameters) and unbound values are errors. Function and
value namespaces are separate. Equality returns `bool`. Natural arithmetic,
equality and comparison map to `Corelib.Init.Nat.add`, `.mul`, `.eqb` and `.leb`.
Boolean equality maps to pure nested conditionals returning the Boolean
constructors. Types and constructors come from `Corelib.Init.Datatypes`.
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

Generated output is deterministic, uses fully qualified CIC library constants
for operations, and binds the exact source bytes with SHA-256. The digest is
provenance, not a semantic correspondence proof. The emitter generates definitions
only; no axioms, admitted obligations, proof scripts or machine-code escape exists.

## Acceptance

Land this contract and its priced checklist cells before implementation. A separate
reviewer reads the scope and independently authored expected translations.
Focused behavioral tests must cover the example, precedence, lexical scope,
both types and each operation, plus deterministic output, source binding and
name hygiene. Well-formed negative neighbors must fail on return type, condition,
branch, call, duplicate-name or resolution premises. Trailing input, unsupported
constructs, malformed/invalid UTF-8, excessive nesting and oversized literals
must produce bounded diagnostics. Surface-conformance cases use the same declaration,
parameter, return and control-flow spellings as the design dossier. Reject the old
`fn`, colon-typed parameter, arrow-return and implicit-expression-body forms, along
with missing returns and unreachable trailing statements. CLI tests must establish successful publication
and preservation of existing output on rejection, input aliases and write errors.

Host CI on Windows and Ubuntu supplies the integrated tool verdict. Dispatch
every Guest CI lane for the same settled revision and finish without waiting.
The translation tests do not establish that a kernel has accepted emitted terms;
a generated-term kernel replay is a separately identified follow-up unless hosted
evidence explicitly supplies it. Production language and whole-system migration
retain the [unified-source acceptance contract](unified-source-contract.md).

## Try the prototype

From the repository root on Windows:

```console
python tools/run.py vela check tools/vela/examples/pure.vela
python tools/run.py vela emit tools/vela/examples/pure.vela --output out/Pure.v
```

Use `python3` on Linux. The output directory must already exist; omit `--output`
to print the definitions. The [example](../../tools/vela/examples/pure.vela)
defines a cube and a Boolean selection over its result. For example, its intended
`Choose(true, 1)` result is true and `Choose(true, 2)` is false. Emission produces
a `Vela_Oracle` module containing `f_Cube` and `f_Choose`; executing them requires
the separately identified kernel replay, rather than an evaluator in this tool.
