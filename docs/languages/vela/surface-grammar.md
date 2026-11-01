# Vela development surface grammar

This is the syntax contract for [Q25i](../../../PLAN.md#q-assessment-actions).
The [language design](verification-strategy.md#an-ideal-surface) and
[whole-system contract](unified-source-contract.md#authoring-end-state) own the
required features and their meanings. This increment accepts located syntax;
resolution, resource checking, proofs, compilation and admission remain separate.

## Entry points and compatibility

One authored Menhir grammar owns two entry points. The existing `file` entry and
schema 1 preserve the pure prototype and its migration comparison. The new
`surface_file` entry, selected with `vela-parser parse --surface SOURCE`, emits
schema 2 and a `surface_file` node with a module name and declarations. It has no
translation fallback. Pure translation continues to reject wider constructs.
All syntax nodes and names carry original-byte, half-open spans; numeric literals
retain their spelling. The existing UTF-8, source-byte, literal-digit, delimiter,
syntax-depth, duration and output bounds apply to both entries.

## Required syntax

The surface entry must express the following features. Grammar actions only
construct syntax, including syntactically valid programs with semantic errors.

| Area | Syntax acceptance |
| --- | --- |
| Modules and abstraction | Qualified module names, imports, aliases, namespaces, public/private declarations, interfaces/traits and implementations, abstract signatures and definitions |
| Data and dependency | Records, structs, tagged unions, fields, constructors, named views, generic types and applications, typed ghost indices, region and capture parameters, grade parameters and annotations |
| Types and resources | Qualified and applied types, ownership, shared/exclusive loans and place-named lifetimes, ghost/tracked/scoped modifiers, function types with captures and effects, dependent binders and universe syntax |
| Contracts | Requires, ensures, restores, where, effects, invariants and decreasing measures; old/final are ordinary calls |
| Expressions | Literal spellings and representation suffixes, qualified access, nested calls, indexing and ranges, unary/arithmetic/comparison/logical operators, implication, pattern tests, explicit generic application, tuples, lambdas and named holes |
| Control | Immutable/mutable and typed locals, assignments, blocks, returns, if/else, bounded-loop syntax, exhaustive-match syntax, break/continue and explicit propagation |
| Grades | Domain carrier/zero/one/add/mul/admits/interpret/laws declarations and parameter use grades |
| Effects and tasks | Effect operations and resumption bounds, deep/shallow handlers, return/operation clauses, resume/dispose/rehandle, async functions, scope/spawn/await/commit and on-cancel cleanup |
| Mathematical proofs | Definitions, theorem/lemma statements, proof blocks, assertions, calculations, quantifiers, inductive/coinductive declarations and constructors, universes and typed holes |
| Architecture and hardware | Machine/hardware containers, state/register declarations, transitions/rules, guards, next-state assignments and explicit schedules/cycles |

New syntax without a prior concrete spelling uses type-first declarations and
braced containers. Explicit generic expression application uses `::<...>` to
separate it from comparison. Nested type arguments close with individual `>`
tokens; shifts may use named operations. Generic arguments admit values and
lifetimes. A parenthesized generic value disambiguates relational expressions.
Loop bodies use braces. A function type returning another function type puts that
result in parentheses. Lambdas use `=>`; function types use `->`. Quantifiers use
typed binders followed by `=>`. Proof commands end in semicolons. Architecture/hardware
syntax supplies no transition or circuit interpretation by itself.

Type-first local and callback annotations use bounded lexical lookahead to
distinguish a qualified, applied or parenthesized type followed by a binder from
an expression.
This classification consults token shape, with no symbol table or type judgment.
It preserves the original lexeme positions and the pure entry's tokenization.

The following spellings select previously unspecified mathematical and machine
syntax. `Type<u>` names a universe-indexed type, and `effect E` is a generic
effect parameter. `rehandle` takes the same body-and-clauses shape as `handle`.
Inductive/coinductive constructors may add `: TYPE` before their semicolon to
state result indices, for example `Nil() : Vec<T, 0>;`.

```text
module Syntax.Examples;
universe u;
public definition Nat Twice(Nat x) = x + x;
public inductive Natural { Zero(); Succ(Natural predecessor); }
public coinductive Stream<T> { More(T head, Stream<T> tail); }
public lemma Reflexive(Nat n): forall (Nat x) => x == x
    proof { assert n == n; ?step; }
public theorem Witness(): exists (Nat n) => n == 0;
public machine Counter {
    state Nat value = 0;
    transition Step() when (value < 10) { next value = value + 1; }
}
public hardware RegisterCounter {
    register u64 count = 0;
    rule Tick() when (count < 10) { next count = count + 1; }
    schedule Main { Tick; }
    cycle 1;
}
```

Proof holes and theorem signatures parse without establishing a theorem. The
[authored surface example](../../../tools/vela/examples/surface.vela) combines
dependent data, contracts, loans and task cleanup;
the independent qualification fixtures exercise every feature row above.

## Acceptance and evidence

### Composable type and resource syntax

The [graded foundation](graded-foundation.md#functions-and-application) and
[borrow rules](core-design.md#loans-and-control-flow) use the same parameter,
data and elimination forms throughout the surface:

- Callable types accept the declaration parameter telescope, including optional
  names, grades and nested ownership modifiers: `Fn(Nat n, byte x @ q) -> Vec<byte, n>`.
  Every callable parameter is a located `parameter` node with `name`, `type` and
  `grade` fields; an unnamed argument has a null name. A lambda parameter accepts
  the same optional use grade, for example `(byte x @ q) => x`. Type-use demands
  remain inferred under the foundation's rules, not a second authored annotation.
- `()` is the unit type and value; `(T, U)` and `(x, y)` are product types and
  values. Parentheses around one type or value only group it. Products contain
  at least two components and may nest. Type, value and pattern nodes preserve
  their distinct roles (`unit_type`, `unit`, `unit_pattern`, `tuple_type`,
  `tuple`, `tuple_pattern`). A product pattern uses existing binding patterns:
  `case (let owner, let receipt): ...`. Local elimination uses
  `let (let owner, let receipt) = value;`, with an explicit pattern node;
  `var` supports the same shape. A bare `_` is a `wildcard_pattern`, whose
  permission to discard a resource is an elaboration obligation.
  In generic arguments, bare parentheses retain their existing value-expression
  meaning. Prefix a structural type argument with `type`, as in
  `Result<type (owned Packet, tracked Receipt), Error>`; this also accepts other
  type forms and avoids guessing whether `(a, b)` names types or values.
- Parametric aliases reuse the existing generic telescope:
  `alias Callback<grade q : NatExact> = Fn(byte x @ q) -> byte;`.
  Named dependent records supply dependent pairs, and indexed unions supply
  outcome-dependent resources. `Box`, `Result`, `Option`, cells, guards and
  protocol tokens remain ordinary library types and operations; they acquire
  no special parser authority or implicit disposal.

Qualification must compose these forms with place-named loans, captures,
restoration, nested reborrows, typestate transitions, dynamic-borrow conflict
branches and cleanup. Independent AST assertions must distinguish parameter
names from their dependent result indices, attach grades to the correct binder,
and retain nested pattern/type roles and original byte spans. Refusal fixtures
cover incomplete binders/grades, malformed products and patterns, and nesting
exhaustion. Semantic mistakes, including duplication, dropping a tracked token,
stale snapshot use and borrowing across suspension, still parse: this entry
supplies syntax for a future checker, not memory-safety acceptance.

### Native qualification

Menhir's code backend must generate with `--strict --infer --explain`, with no
unresolved conflicts and no unchecked runtime dependency. Preserve exact locked
generator/compiler checks and fresh-generation comparison. Use independently
authored fixtures covering every row, nested combinations, expected AST roles,
precedence and byte spans. Reject malformed declarations, incomplete input,
trailing tokens and exhaustion without an AST. Lex comments and literals without
changing delimiters or keyword interpretation inside them.

`vela-parser qualify` must run both the retained pure cases and the surface cases,
bind all fixture inputs into its receipt, and retain separate syntax verdicts.
Focused native builds and helper tests may diagnose candidates; hosted exact-version
qualification owns acceptance. Require Host CI on Windows and Ubuntu and dispatch
every Guest CI lane for the settled revision, recording pending guest evidence.
Q25g/Q25h retain their own acceptance and migration predicates. No parser theorem,
lexer correctness, full-language elaboration or machine/hardware replacement is
claimed by this increment.
