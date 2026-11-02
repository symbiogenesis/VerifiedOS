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

### Dependent elimination and library interfaces

The foundation's [dependent elimination](graded-foundation.md#dependent-data-and-elimination)
uses the existing record, union and pattern forms. An expression match has one
or more expression arms, each terminated by a semicolon:

```text
definition Vec<byte, packet.Length> Contents(Packed<byte> packet) =
    match (packet) as whole : Vec<byte, whole.Length> {
        case Packed(let length, let bytes) => bytes;
    };
```

Both expression matches and the existing statement matches accept the optional
`as NAME : TYPE` motive. The name binds the scrutinee in the result type; branch
substitution and resource compatibility remain checking obligations. A located
`match_motive` node records its `name` and `type`. A match without an annotation
has a null `motive`. Expression matches use `match_expression` and
`expression_case` nodes with `pattern` and `value` fields; statement matches keep
their `match` and `case` nodes and colon-delimited statement arms. Incomplete
motives and mixed arm delimiters are refused. Expression
matches compose with calls, operators, lambdas, proofs and nested matches.

Ordinary fields accept the same optional `@ GRADE` as record and constructor
parameters, before an optional initializer. Their `grade` field is null when
omitted. Thus a graded box or retained callback environment can use either record
or struct presentation without a special storage primitive.

Implementation declarations reuse the generic telescope and declaration
contracts: `impl<T, grade q : NatExact> Dup<Box<T, q>> where Repeatable(T, q) { ... }`.
Their `generics` and `contracts` fields contain the same located nodes as other
declarations. Generic binding, instance coherence and the supplied laws are
elaboration obligations. A callable implementation target is parenthesized,
for example `impl (Fn() -> Nat effects(Read)) where Law() { ... }`, so its effect
bound stays distinct from implementation contracts.

Callable types reuse that telescope too, for example
`Fn<region 'loan>(scoped ref<'loan> T value) -> ()`. Their optional contracts are
explicitly delimited after captures and effects:

```text
alias Update<T> = Fn<region 'loan>(scoped ref<'loan> T value) -> ()
    with { requires Valid(value); restores Valid(value); };
```

The `with` block contains existing declaration contracts, each terminated by a
semicolon. `function_type` nodes expose `generics` and `contracts` arrays, empty
when omitted. Local binders, loan ancestry, scoped escape, callable invocation
laws and closure disposal require checking; syntax alone grants none of them.
The delimiters distinguish a callback's contract from its enclosing operation's
contract without name resolution or a second contract language.

Independent fixtures must distinguish the motive binder from branch binders,
retain dependent indices, field grades, locally bound regions and contract
ownership, and check original UTF-8 byte spans. Include malformed neighbors and
syntax-valid examples with incompatible branches, escaping loans or invalid
grade/resource use. Retain strict generation, pure migration and every existing
feature row. These extensions keep ancillary boxes, cells, guards and protocols
as ordinary library definitions over shared syntax.

### Resource contracts and lexical handler capabilities

Effect operations reuse declaration contracts after their optional resumption
bound and before the terminating semicolon. Their `effect_operation` nodes expose
a `contracts` array, empty when omitted. The reply type, parameter grades,
resumption allowance and resource transitions remain separate syntax fields:

```text
effect Exchange<T> {
    owned T Replace(owned T replacement @ NatExact(1)) resumes(0..1)
        requires Available(replacement)
        ensures Returned(result)
        restores Closed(result)
        effects writes(Storage);
}
```

Struct, interface, trait, machine and hardware containers accept the same
declaration contracts between their generic telescope and opening brace. Their
`contracts` arrays distinguish container laws from member contracts, for example
`trait Repeatable<T, grade q : NatExact> where Admits(T, q) { ... }` and
`struct LocalCell<T> invariant Closed(self) { ... }`. These forms only preserve
proposed obligations; proving invariant preservation, lawful grades and operation
effects remains an elaboration duty.

The [handler lookup rules](handlers-async.md#handler-lookup-capture-and-return)
permit an explicit name for the perform capability of a handler instance:
`handle (body()) as chosen { ... }`. The optional `as NAME` follows the handled
expression and also applies to `handle shallow` and `rehandle`. Each `handle` or
`rehandle` node has a nullable `capability` field holding the located name. Existing
unnamed handlers retain null. Qualified calls such as `chosen.Choose()` reuse
ordinary call/member syntax, without adding another operation primitive.

The capability's intended scope is the handled expression; the handler's clauses
are checked without that capability. Nested bindings, shadowing, forwarding to an
outer capability and rehandling retain distinct syntax identities. Parsing neither
resolves those bindings nor permits an escaping capability, duplicate resumption
or open invariant across capture. Lexical selection, frame identity, `Dup`,
`Dispose` and restoration remain checking obligations under the linked rules.

Independent fixtures must assert operation/container/member contract ownership,
dependent reply indices, parameter-grade and resumption-bound attachment, named
and unnamed handler associations, and original UTF-8 byte spans. Compose these
forms with loans, guarded updates, indexed outcomes, shallow rehandling and explicit
disposal. Refuse incomplete contract expressions and capability binders without
publishing an AST. Syntactically valid violations of capability scope or resource
rules must still parse. Retain every existing qualification and migration case.

### Type-valued computations and uniform library laws

Type parameters may state a kind using the existing type syntax:
`Box<T : Type<u>, grade q : NatExact>`. A type-mode `generic_parameter`
keeps its `type` field null for a bare binder and records the kind when supplied.
Associated types likewise accept an optional `: TYPE` kind before contracts and
their optional definition; `associated_type.kind_annotation` is null when absent.
Universe formation, conversion and dependent substitution remain checking duties.
Parenthesize a callable kind so its effects stay distinct from declaration contracts.

Explicit `type TYPE` expressions inject structural types into ordinary definitions,
calls and dependent matches. A `type_expression` has a `type` field containing the
located type node. For example, an ordinary type family can return
`match (flag) { case true => type (T, T); case false => type (); }`.
Like lambdas and quantifiers, these forms occupy a complete expression; group them
when used as operator operands. Parenthesize a callable payload, as in
`type (Fn(T value) -> T effects(Read))`, to delimit its effects.
This reuses callable, product and library types
instead of introducing separate type-level function or box primitives.
Bare Boolean, string, character and named-hole generic arguments use their existing
expression nodes, alongside numbers, lifetimes and parenthesized expressions.
Named arguments remain unresolved syntax; this introduces no stable-value judgment.

A callable value may reuse the complete callable type before `=>`:

```text
FnOnce<region 'loan>(scoped ref<'loan> T value @ NatExact(1)) -> T
    captures Environment effects(Read)
    with { requires Open(value); restores Closed(value); }
    => Read(in value)
```

The `typed_lambda` node contains `signature` (the existing `function_type`) and
`body`; its parameters, grades, local regions, captures, effects and contracts
therefore have the same syntax as a callable annotation. Existing inferred lambdas
retain their current nodes. Naming parameters, capture completeness, repeatability,
loan escape and per-call resource transitions require elaboration.

Union, inductive and coinductive declarations accept ordinary declaration contracts
between their generic telescope and body. Constructors accept them after the
optional result type. Pure `definition` and `predicate` declarations accept them
after their parameter telescope and before `=` (or a predicate's terminating
semicolon). Associated types accept them before an optional `=` definition.
Each of these nodes exposes a `contracts` array, empty when omitted. Thus domain
laws, graded storage, indexed outcomes and type families share the existing
contract language; their laws do not acquire parser authority.
Effects following a bare callable constructor result still belong to that callable;
parenthesize the result to attach an effects contract to the constructor itself.

Independent fixtures must compose kinded binders, type-valued matches, explicit
callable signatures, scoped loans and graded library resources. Assert contract
ownership, signature/body roles, dependent indices, literal spellings and original
UTF-8 byte spans. Refuse incomplete kinds, type expressions, callable signatures
and contracts without an AST; syntax-valid erasure, ownership and grade violations
must still parse. Retain strict generation and every existing migration and syntax
case. These forms establish no type-system, borrow-checker or erasure theorem.

### Local grades, domain members and disposal clauses

Local value bindings reuse the parameter and field use-grade annotation:
`let value @ q = Make();`, `var T value @ q = Make();` and
`T value @ q = Make();`. The existing `let`, `var` and `typed_local` nodes
expose a nullable `grade` field alongside `type` and `value`. Both inferred and
explicitly typed bindings accept the same grade expression. Product-pattern
bindings retain their existing form; component modalities belong in their data
types. Checking the binding's allowance, evaluation effects and subsequent uses
remains subject to the [graded foundation](graded-foundation.md#functions-and-application).
In particular, zero demand does not erase an effectful initializer.

The domain roles `carrier`, `zero`, `one`, `add`, `mul`, `admits`, `interpret`
and `laws` are contextual member names after a dot. Ordinary paths, type paths
and member expressions can therefore refer to a domain dictionary without new
operator or projection primitives:

```text
definition NatExact.carrier AddZero(NatExact.carrier value) =
    NatExact.add(value, NatExact.zero);
```

These names preserve the existing located path/member AST forms. They remain
reserved at the start of a name; this extension does not alter domain-entry
syntax or establish dictionary sealing, domain laws or an interpretation.
Domains also reuse the existing generic telescope and declaration contracts,
for example `domain Product<A : GradeDomain, B : GradeDomain>
where Compatible(A, B) { carrier (A.carrier, B.carrier); ... }`.
Their `generics` and `contracts` arrays are empty when omitted. Compatible product
domains therefore need no separate grammar primitive or assumed algebraic law.

Handlers accept an explicit disposal clause, using the same expression or block
body as their operation and return clauses:

```text
handle (Run()) as chosen {
    Choose() with k => resume k(true),
    return value => value,
    dispose reason => { Cleanup(reason); return (); },
}
```

A `disposal_clause` has a located `name` for the disposal-reason binder and a
`body`. It composes with deep/shallow handlers and rehandlers, sharing their
comma-delimited clause list. The [handler lifecycle](handlers-async.md#handler-lookup-capture-and-return)
owns its intended resource context and lexical restrictions: the handler's own
perform capability is absent in its clauses. A disposal clause describes the
declared disposal graph; capture and ordinary return do not invoke it. Parsing neither
invokes cleanup nor supplies a resource-restoration proof; duplicate clauses,
unbound capabilities and invalid disposal bodies still parse as semantic errors.
The existing `dispose continuation` computation retains its separate syntax.

Annotation lookahead must accept callable types inside generic local and lambda
annotations, including nested results, loan modifiers, grades and effects.
Arrows in these types must not close generic argument lists. Independent fixtures
must distinguish local allowance, initializer and lambda-parameter grades, domain
member/path spans, and operation/return/disposal clause ownership. Include nested
handlers, syntax-valid resource violations, malformed neighboring spellings and
bounded-lookahead exhaustion. Retain every prior syntax and pure migration case.

### Computed types and uniform elimination

The stable type-valued computations of the [graded foundation](graded-foundation.md#stable-telescope-and-dependency-bookkeeping)
can appear wherever a type is expected, through `type[EXPR]`. A `computed_type`
node stores the ordinary expression in its `value` field. This delimited form
reuses calls, dependent matches, local indices and library operations:

```text
definition Type<u> Select<T : Type<u>>(bool pair) =
    match (pair) { case true => type (T, T); case false => type T; };
alias Selected<T : Type<u>, ghost bool pair> where Stable(pair) =
    type[Select::<T>(pair)];
operation type[Select::<T>(pair)] Read<T : Type<u>>(bool pair);
```

Computed types also work directly as generic arguments, as in
`Box<type[Select::<T>(flag)]>`, and in fields, parameters, callable signatures,
local annotations and lambda annotations. The existing `type TYPE` expression
injects structural types into values; `type[EXPR]` uses a type-valued expression
as a type. Parsing establishes neither stability nor purity, universe formation,
conversion, erasure or resource availability. Effectful or ill-kinded type
expressions remain syntax-valid inputs for the future checker.

Aliases accept existing declaration contracts after their generic telescope and
before `=`. Effect families accept them before their opening brace. Their
`contracts` arrays are empty when omitted and distinct from operation or callable
contracts. Grade-domain laws, capture requirements and family invariants therefore
reuse the same contract language as records and other library definitions.

An empty sum's value eliminator uses `match (impossible) as whole : T {}`.
Its `match_expression` node has an empty `cases` array and the existing optional
motive. Like lambdas and type injection, an empty value match occupies a complete
expression; group it when applying operators or postfix operations. A semicolon
distinguishes an empty-match expression statement from the retained bare empty
statement match. Nonempty expression matches keep their existing syntax.
Whether the scrutinee has an empty type and which resources can
reach that branch are checking obligations; syntax supplies no inhabitant or
proof. String and character literal patterns reuse their lexical spelling in
`string_pattern` and `character_pattern` nodes, with the same `value` field as
their expression literals; they introduce no decoding or equality operation.

Independent fixtures must compose computed types with kinded parameters,
dependent results, scoped loans, local grades and callable contracts. Assert
expression/type roles, alias/family/member contract ownership, empty-match motive
and statement/expression boundaries, literal pattern spellings and original UTF-8 byte spans.
Retain malformed-neighbor refusals, bounded nesting, semantic-error positives,
all earlier surface cases and pure migration behavior.

### Shared operators and local elimination

Parenthesized symbolic operators are ordinary expression atoms. Every binary
operator in the surface precedence table, plus unary `!` and `~`, accepts this
form: `(+)`, `(%)`, `(&)`, `(==>)` and `(!)` are examples. A located `operator`
node retains its located `name`; its span includes parentheses while the name's
span covers only the symbol. Unary and binary uses share `(-)`, `(*)` and `(&)`;
elaboration determines the selected operation and arity under the pointer/loan
rules below. Operator values compose with calls,
members, generic application, tuples, lambdas, computed types and ordinary
declaration contracts. Grade-domain entries use these same expressions, including
their existing `(+)` and `(*)` spellings, without a separate domain-value grammar.
Assignment, range, propagation and keyword computations are not operator values.

Local elimination reuses constructor and recursive patterns:
`let Some(let value) = optional;` and
`var Ready((let owner, let receipt)) = outcome;`. Qualified constructors and
explicit empty argument lists are accepted. A single parenthesized pattern groups
it, producing `group_pattern` with a `pattern` child; products still require at
least two components. Grouping works in local elimination, match arms and pattern
tests. Local pattern bindings retain `let_pattern`/`var_pattern` with `pattern`
and `value` fields. A bare local name retains the existing inferred binding form;
a local constructor pattern requires parentheses, as in `let Ready() = outcome;`.
Component grades remain in their data types. Refutability, constructor arity,
exhaustiveness, ownership and resource disposal are elaboration obligations, so
syntactically valid mistakes still parse.

The grammar shares operator productions between binary expressions and operator
values, and shares recursive type-modifier construction across ordinary,
callable, generic and local-annotation types. Preserve precedence, associativity,
contract ownership, every child in syntax-depth accounting and the pure entry's
schema. Independent fixtures must assert operator and nested pattern roles,
original UTF-8 byte spans, higher-order application and domain compatibility;
exercise every operator spelling and malformed neighboring forms, syntax-valid
resource mistakes and nesting limits. Retain every earlier syntax and migration
fixture and strict conflict-free generation.

Equivalent grammar refactors share named-type application, parenthesized type
construction, literal payloads, binary-expression construction, generic-binder
construction and typed local initializers across their existing contexts.
Generic binders retain all six explicit modes and their name/type roles; typed
initializers share their fields and children while the enclosing statement or
expression binding owns its node kind and span. No helper adds a syntax node.
Context-specific tokens and AST roles remain explicit: local
annotations retain lexical disambiguation, literal patterns retain pattern kinds,
and the pure entry retains schema 1. Preserve the exact accepted/refused language,
JSON fields, original byte spans and syntax-depth accounting. Compare every
retained positive fixture's complete JSON before and after, retain all refusal
and migration cases, and independently check composed types, literal roles,
quantifiers, lambda boundaries, all generic-binder modes and typed initializer
roles/spans under strict conflict-free generation. Compose erased indices, grade
parameters, callable captures and library-defined resource types in these cases;
syntax-valid name, domain and resource mistakes must remain accepted syntax.

### Expression-local bindings

An ordinary expression may bind a shared subexpression with
`let NAME = EXPR in EXPR`, including the existing optional type and use-grade
annotations. Recursive local patterns use the same constructor/product/group
forms as statement elimination. For example, a type family can compute
`let chosen = Select(flag) in chosen`; a computed type can use
`type[let chosen = Select(flag) in chosen]`. A contract or match arm can bind a
library result without a new type-family, borrow or protocol primitive.

A located `let_expression` contains a `binding` (the existing `let` or
`let_pattern` node) and a `body`. The binding covers `let` through its initializer;
the outer node includes the body. The binder's scope is the body, not the
initializer; name resolution, refutability, grades, effects and resource disposal
remain checking obligations. Bindings associate to the right and occupy a full
expression, like lambdas and quantifiers. Group them for postfix/operator use.
Statement bindings keep their semicolon and existing AST. The pure entry and its
migration contract stay unchanged.

Independent fixtures must compose nested bindings with dependent types, callable
contracts, grades, constructor patterns, matches and lambdas; distinguish
initializer/body and binder scopes in the AST and preserve UTF-8 byte spans.
Refuse missing initializers, delimiters and bodies; keep syntax-valid resource
errors accepted. Preserve nesting limits, strict conflict-free generation and
every existing surface and pure qualification case.

### Explicit values, loans and absence

The [permanent exclusions](verification-strategy.md#permanent-language-exclusions)
fix the semantic design. This syntax-only increment preserves the distinctions
needed to check them; no grammar action performs conversion, proves exhaustive
matching, grants write authority or repairs a missing argument modifier.

Ordinary type-first parameters pass values. Extend the shared type-modifier and
prefix-expression productions with `out`, alongside `in` and `ref`, retaining
modifier order, optional place-named lifetime and original byte spans. The AST
uses the existing `modified_type` and `unary` nodes. `out` is a keyword in the
surface entry only; preserve the frozen pure entry's token classification.
Add prefix `*` (dereference) and `&` (address/loan derivation) through the shared
unary production, keeping multiplication, bitwise conjunction and parenthesized
operator values distinct. Prefixes associate right; postfix indexing/calls bind
more tightly. Pointer arithmetic uses the existing additive and indexing forms.
Named library types carry pointer representations; no C declarator or `T*` type
suffix is introduced. `->` remains a function-type arrow.

Member calls retain ordinary member/call syntax. The
[receiver rule](verification-strategy.md#permanent-language-exclusions) supplies
the selected declaration's receiver loan, including a named view such as
`ref self.Tail`; other arguments retain explicit loan modifiers. Resolution,
once-only receiver evaluation, argument order and overlap remain semantic
obligations. A call rejected for an overlapping argument or an ineligible receiver
still parses; the parser neither chooses a view nor delays a loan.

`let`, `var` and unmarked type-first locals retain distinct existing AST roles;
unmarked locals mean immutable bindings. `Option<T>`, `Some(value)`, `None()` and
their constructor patterns use ordinary library syntax. Reserve bare `null` in
the surface lexer and refuse it as syntax, without changing pure tokenization.
Refuse `T?` annotations, null-forgiving postfix `!`, `??` and `?.`. Existing
postfix `?` denotes explicit propagation; prefix `?name` remains a named hole.
Propagation followed by member access uses `(Read()?).Value`. Its former
contiguous spelling `Read()?.Value` is now refused; the retained fixture is
replaced with an independently checked grouped tree. This is an intentional
syntax restriction, not an unchanged-tree claim for that replaced spelling.
The parser still accepts incomplete option matches, immutable writes, mistyped
arithmetic, missing/mismatched loan modifiers and forbidden sharing as located
syntax so the future semantic consumer can report the appropriate obligation.

Use the symbol families consistently:

| Symbols | Syntax roles |
| --- | --- |
| `(...)` | Calls, parameter telescopes, grouping, products and parenthesized operator values; grammar context fixes the role |
| `{...}` | Declaration/statement/proof bodies, match arms, handler clauses and explicitly introduced callable contracts |
| `[...]` | Indexing; `type[...]` explicitly introduces a computed type |
| `<...>`, `::<...>` | Type/generic parameters and arguments; explicit generic expression application |
| `->`, `=>`, `==>`, `<==>` | Callable result, lambda/quantifier/match/handler body, implication and equivalence respectively |
| `\|`, `\|\|`, `&`, `&&`, `^`, `~` | Bitwise and Boolean operators with separate fixed precedence; prefix `&` derives an address/loan |
| `*`, `+`, `-` | Multiplication and additive operators; prefix `*` dereferences a pointer and prefix `-` negates |
| `@`, `'place`, `?`, `?name` | Use grade, lifetime identity, propagation and named hole respectively |

Independent fixtures must check default/explicit binding roles, nested
`Option<Option<T>>` and exhaustive constructor matches, value/`in`/`ref`/`out`/
`owned` signatures and arguments, `out` lifetime annotations, unary versus binary
`*`/`&`, pointer arithmetic/indexing, operator values and original UTF-8 spans.
Refuse malformed adjacent forms, C pointer declarators, nullable/null-forgiving
spellings, missing unary operands and chained nonassociative comparisons.
Keep semantically invalid neighbors as positive syntax fixtures, including
partial matches, implicit conversion attempts, immutable reassignment and
overlapping/shared-mutation attempts. Their acceptance is no semantic verdict.
Retain strict conflict-free generation, byte-identical regeneration, every
surface and pure fixture, pure migration and the native qualification below.

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
