# Pure Vela translation prototype

## Commission and interpretation

[Q25e](../../PLAN.md#q-assessment-actions) commissions a bounded host development
tool: parse an explicitly typed, pure expression fragment and emit Gallina
definitions. The meaning of an accepted expression is its generated CIC term.
There is no independent source evaluator, reduction relation or semantic anchor.
`Nat` denotes mathematical naturals and `Bool` denotes booleans; neither denotes
a machine word, a storage layout or a CHERI permission.

This separately scoped fixture follows the [core design's narrower-fixture
rule](core-design.md#decision-and-reopening-evidence). It does not reopen the
returned-loan trial or commission the [held full-language frontend
rows](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows).
The full calculus still owes its interpretation commitment and register acts.
The Python parser and type checker are untrusted development tools. Their success
is not kernel acceptance, checked source correspondence, a `SourcePackage`,
metatheory, compiler qualification or final-binary admission.

## Source fragment

The prototype accepts UTF-8 source with ASCII identifiers and `//` line comments.
Every file contains one named module and at least one function. Every parameter
and return type is explicit. A function can call only previously declared
functions; recursion and forward calls are refused. Local bindings are immutable.

```text
module Example;
fn twice(x: Nat) -> Nat { x + x }
fn select(flag: Bool, x: Nat) -> Nat {
  let result = twice(x);
  if flag { result } else { 0 }
}
```

The accepted grammar is:

```text
file      := 'module' name ';' function+
function  := 'fn' name '(' parameters? ')' '->' type '{' expression '}'
parameters:= name ':' type (',' name ':' type)*
type      := 'Nat' | 'Bool'
expression:= 'let' name '=' expression ';' expression
           | 'if' expression '{' expression '}' 'else' '{' expression '}'
           | comparison
comparison:= sum (('==' | '<=') sum)?
sum       := product ('+' product)*
product   := atom ('*' atom)*
atom      := decimal | 'true' | 'false' | name
           | name '(' arguments? ')' | '(' expression ')'
arguments := expression (',' expression)*
```

Arithmetic and `<=` take naturals; equality takes two operands of the same type.
A condition is Boolean and both branches have the same type. Calls have the
declared arity and argument types. Let bindings infer only their expression's
`Nat` or `Bool` type. Duplicate functions, parameters, local bindings in an active
scope and unbound values are errors. Function and value namespaces are separate.
Every user name is mapped to a generated identifier so Gallina keywords and
library names cannot capture source references. There is no raw Gallina escape.

Whole-source size, expression nesting and decimal-literal length have explicit
implementation limits, reported as limit diagnostics rather than acceptance.
These are host parser limits, not target resource bounds or integer widths.

## Command and publication

`python tools/run.py vela check SOURCE` parses and checks the complete file and
reports its prototype status. `python tools/run.py vela emit SOURCE` writes
Gallina to standard output; `--output FILE` publishes it through the shared
atomic writer only after complete validation. Reject overwriting the input,
including aliases. Do not create missing output parent directories implicitly.
Diagnostics identify the file, line and column, distinguishing syntax, name,
type, unsupported-feature, encoding, limit and I/O failures. No partial output
is published after a rejected source or failed write.

Generated output is deterministic, uses fully qualified CIC library constants
for operations, and binds the exact source bytes with SHA-256. The digest is
provenance, not a semantic correspondence proof. The emitter generates definitions
only; no axioms, admitted obligations, proof scripts or machine-code escape exists.

## Acceptance

Land this contract and its priced checklist cell before implementation. A separate
reviewer reads the scope and independently authored expected translations.
Focused behavioral tests must cover the example, precedence, lexical scope,
both types and each operation, plus deterministic output, source binding and
name hygiene. Well-formed negative neighbors must fail on return type, condition,
branch, call, duplicate-name or resolution premises. Trailing input, unsupported
constructs, malformed/invalid UTF-8, excessive nesting and oversized literals
must produce bounded diagnostics. CLI tests must establish successful publication
and preservation of existing output on rejection, input aliases and write errors.

Host CI on Windows and Ubuntu supplies the integrated tool verdict. Dispatch
every Guest CI lane for the same settled revision and finish without waiting.
The translation tests do not establish that a kernel has accepted emitted terms;
a generated-term kernel replay is a separately identified follow-up unless hosted
evidence explicitly supplies it. Production language and whole-system migration
retain the [unified-source acceptance contract](unified-source-contract.md).
