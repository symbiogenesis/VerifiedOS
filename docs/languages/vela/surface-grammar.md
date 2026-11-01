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
| Effects and tasks | Effect operations and resumption bounds, deep/shallow handlers, return/operation clauses, resume/dispose, async functions, scope/spawn/await/commit and on-cancel cleanup |
| Mathematical proofs | Definitions, theorem/lemma statements, proof blocks, assertions, calculations, quantifiers, inductive/coinductive declarations and constructors, universes and typed holes |
| Architecture and hardware | Machine/hardware containers, state/register declarations, transitions/rules, guards, next-state assignments and explicit schedules/cycles |

New syntax without a prior concrete spelling uses type-first declarations and
braced containers. Explicit generic expression application uses `::<...>` to
separate it from comparison. Nested type arguments close with individual `>`
tokens; shifts may use named operations. Generic arguments admit values and
lifetimes. A parenthesized generic value disambiguates relational expressions.
Lambdas use `=>`; function types use `->`. Quantifiers use typed binders followed
by `=>`. Proof commands end in semicolons. Architecture/hardware syntax supplies
no transition or circuit interpretation by itself.

## Acceptance and evidence

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
